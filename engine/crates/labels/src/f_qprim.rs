//! F-QPRIM — quantile/censoring primitives (per ladder rung, per side: the
//! timestamp at which that F-PASS threshold was first attained, or the
//! window's own censoring timestamp when it was not). Design authority:
//! `docs/specs/events3_design_amendment_v2.md` §A7 (F7) "F-QPRIM censor
//! rule" (wins all conflicts) and
//! `docs/specs/family_schemas/f_qprim_schema_v1.md`.
//!
//! Reuses [`crate::f_pass::passage_at_threshold`] verbatim for every rung's
//! touch — no new [`crate::extrema::ExtremaTree`] descent beyond the 22
//! F-PASS already performs per anchor (design doc "no new scans"). The only
//! new computation is the row's own observed window-end timestamp (the
//! censor fallback), one shared [`SessionFrame::first_breaker_start_after`]
//! descent per row.

use crate::anchor::{SignalSeed, Slot, SlotRow, WindowFrontier};
use crate::f_pass::{self, LADDER_BPS, ThresholdTouch, TouchState};
use crate::frame::SessionFrame;
use std::fmt::Write as _;
use std::fs::File;
use std::io::{self, BufWriter, Write as _};
use std::path::Path;

/// The row's own observed window-end timestamp (`f_qprim_schema_v1.md`
/// "Exact rule"): `min(session_end_ns, first_breaker_start_after(cutoff))`
/// when a breaker starts strictly after `cutoff_ts_ns` and at/before
/// `session_end_ns`, else `session_end_ns` itself. This is the same
/// `requested_end_ns`/`observed_end_ns` arithmetic `SlotRow::compute`
/// performs internally for the unbounded-horizon window (`nominal_end_ns =
/// session_end_ns`), re-derived here against the public [`SessionFrame`]
/// primitives since that internal value is not otherwise exposed.
///
/// O(log n): one [`SessionFrame::first_breaker_start_after`] descent.
#[must_use]
fn window_end_ns(frame: &SessionFrame, cutoff_ts_ns: i64) -> i64 {
    let breaker_start = frame.first_breaker_start_after(cutoff_ts_ns);
    breaker_start.map_or(frame.session_end_ns, |start| {
        start.min(frame.session_end_ns)
    })
}

/// `attain_or_censor_ts_ns` for one side's already-computed [`ThresholdTouch`]
/// (amendment A7, exact two-branch rule): the touch's own timestamp if
/// touched (`Exact`/`IntervalAmbiguous`), else `window_end_ns` — `NotTouched`
/// and `OutOfDomain` are deliberately not distinguished here (the touch
/// STATE itself, which does distinguish them, remains available via the join
/// to `f_pass.tsv`).
///
/// O(1).
#[must_use]
fn attain_or_censor_ts_ns(touch: &ThresholdTouch, window_end_ns: i64) -> i64 {
    match touch.state {
        TouchState::Exact | TouchState::IntervalAmbiguous => touch
            .ts_ns
            .expect("a touched ThresholdTouch always carries its ts_ns"),
        TouchState::NotTouched | TouchState::OutOfDomain => window_end_ns,
    }
}

/// The `f_qprim.tsv` header: the ten-column common prefix followed by two
/// `qp_<side>_<N>_attain_or_censor_ts_ns` columns per [`LADDER_BPS`] entry, in
/// ladder order (`f_qprim_schema_v1.md` "Value columns").
#[must_use]
pub fn header() -> String {
    let mut out = String::from(
        "day\tsignal_id\tslot\tseed_bar_ordinal\tcutoff_ts_ns\tslot_available\t\
         visible_at_slot\twindow_left\twindow_end\twindow_frontier",
    );
    for n in LADDER_BPS {
        write!(
            out,
            "\tqp_fav_{n}_attain_or_censor_ts_ns\tqp_adv_{n}_attain_or_censor_ts_ns"
        )
        .expect("writing to a String cannot fail");
    }
    out
}

/// Computes every `(signal, slot)` row as one tab-joined line, no header, no
/// trailing newline, slots in order `D1, D2, D3` (slot-minor), signals in
/// the order given by `seeds` — which the caller must already have in
/// `day_signals.tsv` publication order (`docs/specs/label_probe_schema_v1.md`
/// "Family-file common prefix"). Reusable in-memory (e.g. for parquet
/// publication) without going through [`write_tsv`]'s file.
///
/// Rows whose window frontier is `DECISION_UNAVAILABLE`/`NOT_VISIBLE` carry
/// literal `NA` in all 22 value columns (the schema's row-level rule); every
/// other row (including `SOURCE_CENSORED`) computes all 11 ladder rungs
/// against the resolved `[window_left, window_end)` via
/// [`f_pass::passage_at_threshold`], exactly mirroring `f_pass.tsv`'s own
/// precedent.
///
/// O(`seeds.len()` × 3 slots × 11 rungs), each rung O(log n) (reused from
/// F-PASS) plus one shared O(log n) [`window_end_ns`] descent per row.
///
/// # Panics
///
/// Panics if a row's window frontier is neither `DECISION_UNAVAILABLE` nor
/// `NOT_VISIBLE` yet its `window_left`/`window_end` are absent —
/// unreachable per `SlotRow::compute`'s own invariant.
#[must_use]
pub fn rows(frame: &SessionFrame, seeds: &[SignalSeed]) -> Vec<String> {
    let mut out = Vec::with_capacity(seeds.len() * Slot::ALL.len());
    for seed in seeds {
        for slot in Slot::ALL {
            let row = SlotRow::compute(frame, seed, slot, frame.session_end_ns);
            let mut line = row.format_prefix(frame.day);
            if matches!(
                row.window_frontier,
                WindowFrontier::DecisionUnavailable | WindowFrontier::NotVisible
            ) {
                for _ in LADDER_BPS {
                    line.push_str("\tNA\tNA");
                }
            } else {
                let window_left = row
                    .window_left
                    .expect("window present when slot available and visible");
                let window_end = row
                    .window_end
                    .expect("window present when slot available and visible");
                let censor_ts_ns = window_end_ns(frame, row.cutoff_ts_ns);
                for bps in LADDER_BPS {
                    let result = f_pass::passage_at_threshold(
                        frame,
                        seed.extreme_side,
                        seed.pivot_price_u6,
                        bps,
                        window_left,
                        window_end,
                    );
                    write!(
                        line,
                        "\t{}\t{}",
                        attain_or_censor_ts_ns(&result.fav, censor_ts_ns),
                        attain_or_censor_ts_ns(&result.adv, censor_ts_ns)
                    )
                    .expect("writing to a String cannot fail");
                }
            }
            out.push(line);
        }
    }
    out
}

/// Writes `f_qprim.tsv` for every `(signal, slot)` row ([`rows`]).
///
/// # Errors
///
/// Returns an [`io::Error`] if `out_path` cannot be created or written.
pub fn write_tsv(frame: &SessionFrame, seeds: &[SignalSeed], out_path: &Path) -> io::Result<()> {
    let mut out = BufWriter::new(File::create(out_path)?);
    writeln!(out, "{}", header())?;
    for line in rows(frame, seeds) {
        writeln!(out, "{line}")?;
    }
    out.flush()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::anchor::Side;
    use crate::frame::{Breaker, GroupKind};

    const BAR_NS: i64 = 60_000_000_000;

    fn seed(
        side: Side,
        pivot_last_bar_ordinal: u64,
        causal_visible_ts_ns: i64,
        pivot_price_u6: i64,
    ) -> SignalSeed {
        SignalSeed {
            signal_id: [0xef; 32],
            extreme_side: side,
            pivot_price_u6,
            pivot_last_bar_ordinal,
            causal_visible_ts_ns,
        }
    }

    // ------------------------- window_end_ns -------------------------

    #[test]
    fn window_end_ns_is_session_end_with_no_breaker() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0],
            vec![100],
            vec![100],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        assert_eq!(window_end_ns(&frame, BAR_NS), 10 * BAR_NS);
    }

    #[test]
    fn window_end_ns_clamps_to_a_breaker_strictly_after_cutoff() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0],
            vec![100],
            vec![100],
            vec![GroupKind::Scalar],
            vec![Breaker {
                start_ns: 3 * BAR_NS,
                end_ns: 5 * BAR_NS,
            }],
        );
        assert_eq!(window_end_ns(&frame, BAR_NS), 3 * BAR_NS);
    }

    // --------------------- attain_or_censor_ts_ns: hand cases ---------------------

    #[test]
    fn touched_uses_the_touch_ts_ns_not_the_censor() {
        let touch = ThresholdTouch {
            index: Some(2),
            ts_ns: Some(2 * BAR_NS),
            state: TouchState::Exact,
        };
        assert_eq!(attain_or_censor_ts_ns(&touch, 99 * BAR_NS), 2 * BAR_NS);
    }

    #[test]
    fn interval_ambiguous_touch_also_uses_its_own_ts_ns() {
        let touch = ThresholdTouch {
            index: Some(1),
            ts_ns: Some(BAR_NS),
            state: TouchState::IntervalAmbiguous,
        };
        assert_eq!(attain_or_censor_ts_ns(&touch, 99 * BAR_NS), BAR_NS);
    }

    #[test]
    fn not_touched_falls_back_to_the_censor_ts() {
        let touch = ThresholdTouch {
            index: None,
            ts_ns: None,
            state: TouchState::NotTouched,
        };
        assert_eq!(attain_or_censor_ts_ns(&touch, 7 * BAR_NS), 7 * BAR_NS);
    }

    #[test]
    fn out_of_domain_also_falls_back_to_the_censor_ts() {
        // A7's rule is a strict touched/not-touched binary: OUT_OF_DOMAIN is
        // not touched, so it too falls back to the window's own censor ts.
        let touch = ThresholdTouch {
            index: None,
            ts_ns: None,
            state: TouchState::OutOfDomain,
        };
        assert_eq!(attain_or_censor_ts_ns(&touch, 7 * BAR_NS), 7 * BAR_NS);
    }

    // --------------------------- write_tsv: row shape ---------------------------

    fn temp_out_path(name: &str) -> std::path::PathBuf {
        std::env::temp_dir().join(format!("f_qprim_test_{}_{name}.tsv", std::process::id()))
    }

    #[test]
    fn write_tsv_header_has_the_exact_expected_column_count() {
        let header = header();
        let columns: Vec<&str> = header.split('\t').collect();
        // 10 common-prefix columns + 11 rungs * 2 columns each.
        assert_eq!(columns.len(), 10 + 11 * 2);
        assert_eq!(columns[9], "window_frontier");
        assert_eq!(columns[10], "qp_fav_5_attain_or_censor_ts_ns");
        assert_eq!(columns[11], "qp_adv_5_attain_or_censor_ts_ns");
        assert_eq!(
            columns[columns.len() - 1],
            "qp_adv_240_attain_or_censor_ts_ns"
        );
    }

    #[test]
    fn write_tsv_decision_unavailable_row_is_all_na() {
        // Same slot geometry as the analogous f_pass/f_ord tests.
        let session_end_ns = 3 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![0],
            vec![100],
            vec![100],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(Side::Low, 1, 0, 1_000_000);
        let path = temp_out_path("decision_unavailable");
        write_tsv(&frame, std::slice::from_ref(&s), &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        assert_eq!(lines.next(), Some(header().as_str()));
        let d1 = lines.next().expect("D1 row");
        let d2 = lines.next().expect("D2 row");
        let d3 = lines.next().expect("D3 row");
        assert_eq!(lines.next(), None);

        let d2_cols: Vec<&str> = d2.split('\t').collect();
        assert_eq!(d2_cols[9], "DECISION_UNAVAILABLE");
        assert!(d2_cols[10..].iter().all(|&c| c == "NA"));
        let d3_cols: Vec<&str> = d3.split('\t').collect();
        assert_eq!(d3_cols[9], "DECISION_UNAVAILABLE");
        assert!(d3_cols[10..].iter().all(|&c| c == "NA"));
        let d1_cols: Vec<&str> = d1.split('\t').collect();
        assert_ne!(d1_cols[9], "DECISION_UNAVAILABLE");

        std::fs::remove_file(&path).ok();
    }

    // Mandatory edge test: censor ts equals window end for untouched rungs.
    #[test]
    fn write_tsv_untouched_rung_censor_ts_equals_the_window_end() {
        // One group sitting exactly AT the anchor price: since every
        // ladder threshold's distance is >= 1 (CONV §2), a group with
        // m_lo == m_hi == P touches neither side at any rung. No breaker
        // => the censor ts is exactly session_end_ns.
        let session_end_ns = 20 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![0, BAR_NS],
            vec![1_000_000, 1_000_000],
            vec![1_000_000, 1_000_000],
            vec![GroupKind::Scalar; 2],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let path = temp_out_path("untouched_rung");
        write_tsv(&frame, std::slice::from_ref(&s), &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        lines.next(); // header
        let d1 = lines.next().expect("D1 row");
        let d1_cols: Vec<&str> = d1.split('\t').collect();
        assert_eq!(d1_cols[9], "COMPLETE");
        // qp_fav_5 (columns 10,11): the window's group sits exactly at P
        // (m_hi == m_lo == 1_000_000), so no rung's fav/adv level (always
        // >= 1 u6 away from P) is ever crossed: both fav and adv are
        // NOT_TOUCHED, so both columns must equal session_end_ns exactly.
        assert_eq!(d1_cols[10], session_end_ns.to_string());
        assert_eq!(d1_cols[11], session_end_ns.to_string());
        // Every other rung too (all thresholds share the same fate here).
        assert!(
            d1_cols[10..]
                .iter()
                .all(|&c| c == session_end_ns.to_string())
        );

        std::fs::remove_file(&path).ok();
    }

    #[test]
    fn write_tsv_untouched_rung_censor_ts_equals_a_breaker_start_when_one_applies() {
        // Same group geometry, but a breaker starts strictly after the
        // cutoff: the censor ts must equal the breaker's own start, not the
        // session end.
        let session_end_ns = 20 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![0, BAR_NS],
            vec![1_000_000, 1_000_000],
            vec![1_000_000, 1_000_000],
            vec![GroupKind::Scalar; 2],
            vec![Breaker {
                start_ns: 5 * BAR_NS,
                end_ns: 8 * BAR_NS,
            }],
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let path = temp_out_path("untouched_rung_breaker");
        write_tsv(&frame, std::slice::from_ref(&s), &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        lines.next();
        let d1 = lines.next().expect("D1 row");
        let d1_cols: Vec<&str> = d1.split('\t').collect();
        assert_eq!(d1_cols[9], "WIDE_BREAKER");
        assert_eq!(d1_cols[10], (5 * BAR_NS).to_string());
        assert_eq!(d1_cols[11], (5 * BAR_NS).to_string());

        std::fs::remove_file(&path).ok();
    }

    #[test]
    fn write_tsv_touched_rung_reports_its_own_touch_ts_not_the_censor() {
        // g1 (ts=BAR_NS) touches the 5bps favorable level exactly, well
        // before the session end.
        let session_end_ns = 20 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![0, BAR_NS],
            vec![100, 999_600],
            vec![100, 1_000_500],
            vec![GroupKind::Scalar; 2],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let path = temp_out_path("touched_rung");
        write_tsv(&frame, std::slice::from_ref(&s), &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        lines.next();
        let d1 = lines.next().expect("D1 row");
        let d1_cols: Vec<&str> = d1.split('\t').collect();
        // window_left = end_position(cutoff=BAR_NS) = 1 (g1 included).
        assert_eq!(d1_cols[7], "1");
        // qp_fav_5: touched at g1's own ts (BAR_NS), not the session end.
        assert_eq!(d1_cols[10], BAR_NS.to_string());
        assert_ne!(d1_cols[10], session_end_ns.to_string());
        // qp_adv_5: never touched (adverse level 999_500 vs m_lo 999_600).
        assert_eq!(d1_cols[11], session_end_ns.to_string());

        std::fs::remove_file(&path).ok();
    }
}
