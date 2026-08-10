//! F-ORD — ordering-state family (favorable-first / adverse-first / dual-
//! touch derivation at the four registered anchor scales, pure O(1) from
//! F-PASS outputs plus the window frontier). Design authority:
//! `docs/specs/label_kernel_design_v1.md` §"Families (EVENTS.2 wave)"
//! ("F-ORD — ordering states") and `docs/specs/label_probe_schema_v1.md`
//! §"`f_ord.tsv` (family F-ORD)".
//!
//! [`ord_state_at`] derives its state purely from
//! [`crate::f_pass::passage_at_threshold`]'s outcome plus the window
//! frontier — no new scans, exactly per the design doc.

use crate::anchor::{SignalSeed, Slot, SlotRow, WindowFrontier};
use crate::f_pass::{self, TouchState};
use crate::frame::SessionFrame;
use std::fmt::Write as _;
use std::fs::File;
use std::io::{self, BufWriter, Write as _};
use std::path::Path;

/// The four registered anchor scales (CONV §2
/// `INTRABAR_TARGET_ANCHOR_SCALES_BPS`), in column order.
pub const ANCHOR_SCALES_BPS: [u16; 4] = [5, 10, 20, 40];

/// One anchor scale's ordering state (`docs/specs/label_probe_schema_v1.md`
/// "`f_ord.tsv`"). `NeitherCloseTruncated` is reserved: F-ORD's own window
/// always uses the CLOSE-bounded nominal end (like F-PASS/F-EXT), so
/// [`WindowFrontier::OfficialCloseTruncated`] never actually arises for this
/// family in practice — the variant exists so [`ord_state_at`]'s match on
/// [`WindowFrontier`] stays exhaustive and schema-faithful.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum OrdState {
    FavorableFirst,
    AdverseFirst,
    SameGroupAmbiguous,
    NeitherComplete,
    NeitherWideBreaker,
    NeitherCloseTruncated,
    NeitherSourceCensored,
    OutOfDomain,
    Na,
}

impl OrdState {
    /// The wire string for `ord_<N>_state`.
    #[must_use]
    pub const fn wire(self) -> &'static str {
        match self {
            Self::FavorableFirst => "FAVORABLE_FIRST",
            Self::AdverseFirst => "ADVERSE_FIRST",
            Self::SameGroupAmbiguous => "SAME_GROUP_AMBIGUOUS",
            Self::NeitherComplete => "NEITHER_COMPLETE",
            Self::NeitherWideBreaker => "NEITHER_WIDE_BREAKER",
            Self::NeitherCloseTruncated => "NEITHER_CLOSE_TRUNCATED",
            Self::NeitherSourceCensored => "NEITHER_SOURCE_CENSORED",
            Self::OutOfDomain => "OUT_OF_DOMAIN",
            Self::Na => "NA",
        }
    }
}

/// Derives one anchor scale's `ord_<N>_state`, purely from
/// [`f_pass::passage_at_threshold`]'s outcome plus the window frontier
/// (design doc "F-ORD": "no new scans"). `window_left`/`window_end` absent
/// (the `DECISION_UNAVAILABLE`/`NOT_VISIBLE` rows) yields [`OrdState::Na`]
/// directly — total over every row, no panics.
///
/// Precedence, per the schema: an out-of-domain level outranks everything;
/// otherwise a real touch on either side outranks censoring ("favorable/
/// adverse-first outrank censoring — a touch before the censor is a
/// touch"); only when neither side touched does the window frontier itself
/// qualify the `NEITHER_*` variant.
///
/// O(log n) (one [`f_pass::passage_at_threshold`] call).
#[must_use]
pub fn ord_state_at(
    frame: &SessionFrame,
    seed: &SignalSeed,
    frontier: WindowFrontier,
    window_left: Option<usize>,
    window_end: Option<usize>,
    bps: u16,
) -> OrdState {
    let (Some(window_left), Some(window_end)) = (window_left, window_end) else {
        return OrdState::Na;
    };

    let result = f_pass::passage_at_threshold(
        frame,
        seed.extreme_side,
        seed.pivot_price_u6,
        bps,
        window_left,
        window_end,
    );
    if result.fav.state == TouchState::OutOfDomain || result.adv.state == TouchState::OutOfDomain {
        return OrdState::OutOfDomain;
    }
    match (result.fav.index, result.adv.index) {
        (Some(f), Some(a)) if f == a => OrdState::SameGroupAmbiguous,
        (Some(f), Some(a)) if f < a => OrdState::FavorableFirst,
        (Some(_) | None, Some(_)) => OrdState::AdverseFirst,
        (Some(_), None) => OrdState::FavorableFirst,
        (None, None) => match frontier {
            WindowFrontier::Complete => OrdState::NeitherComplete,
            WindowFrontier::WideBreaker => OrdState::NeitherWideBreaker,
            WindowFrontier::SourceCensored => OrdState::NeitherSourceCensored,
            WindowFrontier::OfficialCloseTruncated => OrdState::NeitherCloseTruncated,
            WindowFrontier::DecisionUnavailable | WindowFrontier::NotVisible => OrdState::Na,
        },
    }
}

/// The `f_ord.tsv` header: the ten-column common prefix
/// (`crate::anchor::SlotRow::format_prefix`) followed by one `ord_<N>_state`
/// column per [`ANCHOR_SCALES_BPS`] entry.
#[must_use]
pub fn header() -> String {
    let mut out = String::from(
        "day\tsignal_id\tslot\tseed_bar_ordinal\tcutoff_ts_ns\tslot_available\t\
         visible_at_slot\twindow_left\twindow_end\twindow_frontier",
    );
    for n in ANCHOR_SCALES_BPS {
        write!(out, "\tord_{n}_state").expect("writing to a String cannot fail");
    }
    out
}

/// Appends one anchor scale's `ord_<N>_state` column, tab-prefixed.
fn push_ord_column(line: &mut String, state: OrdState) {
    write!(line, "\t{}", state.wire()).expect("writing to a String cannot fail");
}

/// Computes every `(signal, slot)` row as one tab-joined line, no header, no
/// trailing newline: one row per `(signal, slot)`, slots in order `D1, D2,
/// D3` (slot-minor), signals in the order given by `seeds` — which the
/// caller must already have in `day_signals.tsv` publication order
/// (`docs/specs/label_probe_schema_v1.md` "Family-file common prefix").
/// Reusable in-memory (e.g. for parquet publication) without going through
/// [`write_tsv`]'s file.
///
/// [`ord_state_at`] is total over every row (including
/// `DECISION_UNAVAILABLE`/`NOT_VISIBLE`, which it maps to [`OrdState::Na`]),
/// so every row is produced uniformly.
///
/// O(`seeds.len()` × 3 slots × 4 anchor scales), each O(log n).
#[must_use]
pub fn rows(frame: &SessionFrame, seeds: &[SignalSeed]) -> Vec<String> {
    let mut out = Vec::with_capacity(seeds.len() * Slot::ALL.len());
    for seed in seeds {
        for slot in Slot::ALL {
            let row = SlotRow::compute(frame, seed, slot, frame.session_end_ns);
            let mut line = row.format_prefix(frame.day);
            for bps in ANCHOR_SCALES_BPS {
                let state = ord_state_at(
                    frame,
                    seed,
                    row.window_frontier,
                    row.window_left,
                    row.window_end,
                    bps,
                );
                push_ord_column(&mut line, state);
            }
            out.push(line);
        }
    }
    out
}

/// Writes `f_ord.tsv` for every `(signal, slot)` row ([`rows`]).
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
            signal_id: [0xcd; 32],
            extreme_side: side,
            pivot_price_u6,
            pivot_last_bar_ordinal,
            causal_visible_ts_ns,
        }
    }

    // ----------------------------- ord_state_at -----------------------------

    #[test]
    fn na_when_window_is_absent() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0],
            vec![100],
            vec![100],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let state = ord_state_at(
            &frame,
            &s,
            WindowFrontier::DecisionUnavailable,
            None,
            None,
            5,
        );
        assert_eq!(state, OrdState::Na);
        let state = ord_state_at(&frame, &s, WindowFrontier::NotVisible, None, None, 5);
        assert_eq!(state, OrdState::Na);
    }

    #[test]
    fn favorable_first_when_only_favorable_touches() {
        // Same frame/window as f_pass's "very first window group" case.
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS],
            vec![100, 999_600],
            vec![100, 1_000_500],
            vec![GroupKind::Scalar, GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let state = ord_state_at(&frame, &s, WindowFrontier::Complete, Some(1), Some(2), 5);
        assert_eq!(state, OrdState::FavorableFirst);
    }

    #[test]
    fn adverse_first_when_only_adverse_touches() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS],
            vec![100, 999_400],
            vec![100, 999_900],
            vec![GroupKind::Scalar, GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        // fav level 1_000_500 vs m_hi 999_900: no touch.
        // adv level 999_500 vs m_lo 999_400: touched.
        let state = ord_state_at(&frame, &s, WindowFrontier::Complete, Some(1), Some(2), 5);
        assert_eq!(state, OrdState::AdverseFirst);
    }

    #[test]
    fn same_group_ambiguous_on_a_dual_touch() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS],
            vec![100, 998_000],
            vec![100, 1_002_000],
            vec![GroupKind::Scalar, GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let state = ord_state_at(&frame, &s, WindowFrontier::Complete, Some(1), Some(2), 5);
        assert_eq!(state, OrdState::SameGroupAmbiguous);
    }

    #[test]
    fn out_of_domain_outranks_a_real_favorable_touch() {
        // Same as f_pass's OUT_OF_DOMAIN case: anchor = 1, N = 240 puts the
        // adverse level at 0 (<=0), even though favorable clearly touches.
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0],
            vec![0],
            vec![5],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1);
        let state = ord_state_at(&frame, &s, WindowFrontier::Complete, Some(0), Some(1), 240);
        assert_eq!(state, OrdState::OutOfDomain);
    }

    #[test]
    fn neither_complete_when_nothing_touches_and_frontier_is_complete() {
        // N = 240: fav level 1_024_000, adv level 976_000; the group sits
        // strictly inside the band, touching neither.
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0],
            vec![999_900],
            vec![1_000_100],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let state = ord_state_at(&frame, &s, WindowFrontier::Complete, Some(0), Some(1), 240);
        assert_eq!(state, OrdState::NeitherComplete);
    }

    #[test]
    fn neither_source_censored_when_the_window_is_empty() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            5 * BAR_NS,
            vec![0, BAR_NS],
            vec![100, 100],
            vec![100, 100],
            vec![GroupKind::Scalar; 2],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        // window_left == window_end == 2: an empty window (SOURCE_CENSORED).
        let state = ord_state_at(
            &frame,
            &s,
            WindowFrontier::SourceCensored,
            Some(2),
            Some(2),
            5,
        );
        assert_eq!(state, OrdState::NeitherSourceCensored);
    }

    #[test]
    fn breaker_touch_before_the_censor_outranks_the_wide_breaker_frontier() {
        // Same breaker geometry as f_pass's breaker test: adverse touches
        // before the breaker, favorable would only touch after it.
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS, 5 * BAR_NS],
            vec![100, 998_000, 1_999_000],
            vec![100, 999_000, 2_000_000],
            vec![GroupKind::Scalar; 3],
            vec![Breaker {
                start_ns: 2 * BAR_NS,
                end_ns: 4 * BAR_NS,
            }],
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let state = ord_state_at(&frame, &s, WindowFrontier::WideBreaker, Some(1), Some(2), 5);
        assert_eq!(state, OrdState::AdverseFirst);
    }

    #[test]
    fn neither_wide_breaker_when_nothing_touches_before_the_censor() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS, 5 * BAR_NS],
            vec![100, 999_800, 1_999_000],
            vec![100, 999_000, 2_000_000],
            vec![GroupKind::Scalar; 3],
            vec![Breaker {
                start_ns: 2 * BAR_NS,
                end_ns: 4 * BAR_NS,
            }],
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        // fav level 1_000_500 vs m_hi 999_000: no touch.
        // adv level 999_500 vs m_lo 999_800: no touch either.
        let state = ord_state_at(&frame, &s, WindowFrontier::WideBreaker, Some(1), Some(2), 5);
        assert_eq!(state, OrdState::NeitherWideBreaker);
    }

    #[test]
    fn neither_close_truncated_reserved_variant_is_reachable() {
        // Never produced by write_tsv for this family (nominal_end_ns is
        // always session_end_ns), but the schema reserves the wire string
        // and `ord_state_at`'s frontier match must stay exhaustive.
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0],
            vec![999_900],
            vec![1_000_100],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let state = ord_state_at(
            &frame,
            &s,
            WindowFrontier::OfficialCloseTruncated,
            Some(0),
            Some(1),
            240,
        );
        assert_eq!(state, OrdState::NeitherCloseTruncated);
    }

    // --------------------------- write_tsv: row shape ---------------------------

    fn temp_out_path(name: &str) -> std::path::PathBuf {
        std::env::temp_dir().join(format!("f_ord_test_{}_{name}.tsv", std::process::id()))
    }

    #[test]
    fn write_tsv_header_has_the_exact_expected_column_count() {
        let header = header();
        let columns: Vec<&str> = header.split('\t').collect();
        assert_eq!(columns.len(), 10 + 4);
        assert_eq!(columns[9], "window_frontier");
        assert_eq!(columns[10], "ord_5_state");
        assert_eq!(columns[11], "ord_10_state");
        assert_eq!(columns[12], "ord_20_state");
        assert_eq!(columns[13], "ord_40_state");
    }

    #[test]
    fn write_tsv_decision_unavailable_row_is_all_na() {
        // Same slot geometry as the analogous f_pass test.
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

    #[test]
    fn write_tsv_not_visible_at_d1_then_visible_at_d2() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS, 2 * BAR_NS],
            vec![100, 100, 999_600],
            vec![100, 100, 1_000_500],
            vec![GroupKind::Scalar; 3],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, BAR_NS + 1, 1_000_000);
        let path = temp_out_path("not_visible_then_visible");
        write_tsv(&frame, std::slice::from_ref(&s), &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        lines.next(); // header
        let d1 = lines.next().expect("D1 row");
        let d2 = lines.next().expect("D2 row");

        let d1_cols: Vec<&str> = d1.split('\t').collect();
        assert_eq!(d1_cols[9], "NOT_VISIBLE");
        assert!(d1_cols[10..].iter().all(|&c| c == "NA"));

        let d2_cols: Vec<&str> = d2.split('\t').collect();
        assert_eq!(d2_cols[9], "COMPLETE");
        assert_eq!(d2_cols[7], "2");
        assert_eq!(d2_cols[8], "3");
        // The group at index 2 touches the 5bps favorable level exactly and
        // nothing else in-window touches adverse: FAVORABLE_FIRST.
        assert_eq!(d2_cols[10], "FAVORABLE_FIRST");

        std::fs::remove_file(&path).ok();
    }
}
