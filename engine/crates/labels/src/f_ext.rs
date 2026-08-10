//! F-EXT — extrema family (remaining MFE/MAE, post-extreme giveback, and
//! retained fraction). Design authority:
//! `docs/specs/label_kernel_design_v1.md` §"Families (EVENTS.2 wave)"
//! ("F-EXT — extrema") and `docs/specs/label_probe_schema_v1.md`
//! §"`f_ext.tsv` (family F-EXT)".
//!
//! For this unbounded-horizon family `nominal_end_ns` is the official close
//! itself (`label_kernel_design_v1.md` pinned rule 5), so every row's window
//! is computed against `frame.session_end_ns`.

use crate::anchor::{Side, SignalSeed, Slot, SlotRow};
use crate::frame::SessionFrame;
use std::fs::File;
use std::io::{self, BufWriter, Write};
use std::path::Path;

/// The full `f_ext.tsv` header: the ten-column common prefix
/// (`SlotRow::format_prefix`) plus the twelve F-EXT value columns, in the
/// exact order pinned by `docs/specs/label_probe_schema_v1.md` "`f_ext.tsv`".
pub const HEADER: &str = "day\tsignal_id\tslot\tseed_bar_ordinal\tcutoff_ts_ns\tslot_available\tvisible_at_slot\twindow_left\twindow_end\twindow_frontier\tmfe_u6\tmfe_group_index\tmfe_ts_ns\tmfe_group_kind\tmae_u6\tmae_group_index\tmae_ts_ns\tmae_group_kind\tgiveback_u6\tgiveback_group_index\tgiveback_ts_ns\tretained_u6";

/// The twelve `NA` placeholders for a row whose common-prefix frontier is
/// `DECISION_UNAVAILABLE`, `NOT_VISIBLE`, or `SOURCE_CENSORED`
/// (`label_probe_schema_v1.md` "Family-file common prefix": every F-EXT
/// value column is `NA` in all three cases — F-EXT defines no column that
/// survives `SOURCE_CENSORED`, unlike F-TERM's per-horizon `state`).
const NA_VALUES: &str = "NA\tNA\tNA\tNA\tNA\tNA\tNA\tNA\tNA\tNA\tNA\tNA";

/// Computes and formats the twelve F-EXT value columns for one `(signal,
/// slot)` row, given its already-computed common prefix.
///
/// Algorithm (`label_kernel_design_v1.md` "F-EXT — extrema",
/// `label_probe_schema_v1.md` "`f_ext.tsv`"): over the window `[left, end)`,
/// the raw favorable extreme `F` (max of the favorable series, leftmost
/// attaining index) and raw adverse extreme `A` (min of the adverse series,
/// leftmost) give `mfe_u6 = max(0, favorable_move)`, `mae_u6 = max(0,
/// adverse_move)`; the post-extreme giveback re-queries the adverse-
/// direction extremum over `[mfe_group_index, end)` (one extra range
/// query) against the RAW `F` (not the floored `mfe_u6`); `retained_u6 =
/// max(0, mfe_u6 − giveback_u6)`.
///
/// Cost: O(log n) — four [`crate::extrema::ExtremaTree`] range queries
/// (favorable extreme, adverse extreme, giveback value, giveback index is
/// returned by the same query), `n` = `frame.group_count()`. No per-anchor
/// scan.
#[allow(
    clippy::similar_names,
    reason = "mfe_u6/mae_u6 are the registered schema column-name prefixes \
              (max favorable/adverse excursion); renaming would break \
              traceability to label_probe_schema_v1.md"
)]
fn format_values(frame: &SessionFrame, seed: &SignalSeed, prefix: &SlotRow) -> String {
    let (Some(left), Some(end)) = (prefix.window_left, prefix.window_end) else {
        return NA_VALUES.to_owned();
    };
    if left >= end {
        return NA_VALUES.to_owned();
    }
    let last = end - 1;
    let tree = frame.extrema();
    let anchor_u6 = seed.pivot_price_u6;

    // Raw favorable/adverse extremes over the full window, leftmost
    // attaining index (pinned rule 7 / CONV §7 first-attainment tie rule).
    let (fav_value, fav_index, adv_value, adv_index) = match seed.extreme_side {
        Side::Low => {
            let fav = tree.range_max(left, last);
            let adv = tree.range_min(left, last);
            (fav.value, fav.first_index, adv.value, adv.first_index)
        }
        Side::High => {
            let fav = tree.range_min(left, last);
            let adv = tree.range_max(left, last);
            (fav.value, fav.first_index, adv.value, adv.first_index)
        }
    };

    let (mfe_u6, mae_u6) = match seed.extreme_side {
        Side::Low => (
            (fav_value - anchor_u6).max(0),
            (anchor_u6 - adv_value).max(0),
        ),
        Side::High => (
            (anchor_u6 - fav_value).max(0),
            (adv_value - anchor_u6).max(0),
        ),
    };

    // Giveback: adverse-direction extremum over [fav_index, end) only — the
    // post-extreme rebound, never the whole-window adverse extreme.
    let (giveback_value, giveback_index) = match seed.extreme_side {
        Side::Low => {
            let g = tree.range_min(fav_index, last);
            (g.value, g.first_index)
        }
        Side::High => {
            let g = tree.range_max(fav_index, last);
            (g.value, g.first_index)
        }
    };
    let giveback_u6 = match seed.extreme_side {
        Side::Low => (fav_value - giveback_value).max(0),
        Side::High => (giveback_value - fav_value).max(0),
    };
    let retained_u6 = (mfe_u6 - giveback_u6).max(0);

    format!(
        "{mfe_u6}\t{fav_index}\t{}\t{}\t{mae_u6}\t{adv_index}\t{}\t{}\t{giveback_u6}\t{giveback_index}\t{}\t{retained_u6}",
        frame.ts_ns[fav_index],
        frame.kind[fav_index].wire(),
        frame.ts_ns[adv_index],
        frame.kind[adv_index].wire(),
        frame.ts_ns[giveback_index],
    )
}

/// Computes every `(signal, slot)` row as one tab-joined line (common prefix
/// plus value columns, no header, no trailing newline), in the schema's row
/// order: signals in `seeds` order, slots `D1, D2, D3`
/// (`docs/specs/label_probe_schema_v1.md` "Family-file common prefix"). This
/// is the same per-row text [`write_tsv`] writes to disk, exposed so an
/// in-memory publisher (e.g. the run scheduler's parquet leaf writer) can
/// reuse the exact kernel without going through a file.
///
/// O(`seeds.len()` · log n): one [`SlotRow::compute`] descent plus the
/// O(log n) value computation above per row, `n` = `frame.group_count()`.
#[must_use]
pub fn rows(frame: &SessionFrame, seeds: &[SignalSeed]) -> Vec<String> {
    let mut out = Vec::with_capacity(seeds.len() * Slot::ALL.len());
    for seed in seeds {
        for slot in Slot::ALL {
            let prefix = SlotRow::compute(frame, seed, slot, frame.session_end_ns);
            let values = format_values(frame, seed, &prefix);
            out.push(format!("{}\t{values}", prefix.format_prefix(frame.day)));
        }
    }
    out
}

/// Writes `f_ext.tsv` for every `(signal, slot)` row ([`rows`]).
///
/// # Errors
///
/// Returns an [`io::Error`] if `out_path` cannot be created or written.
pub fn write_tsv(frame: &SessionFrame, seeds: &[SignalSeed], out_path: &Path) -> io::Result<()> {
    let mut out = BufWriter::new(File::create(out_path)?);
    writeln!(out, "{HEADER}")?;
    for line in rows(frame, seeds) {
        writeln!(out, "{line}")?;
    }
    out.flush()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::anchor::WindowFrontier;
    use crate::frame::{Breaker, GroupKind};

    const BAR_NS: i64 = 60_000_000_000;

    fn seed(
        side: Side,
        pivot_price_u6: i64,
        pivot_last_bar_ordinal: u64,
        causal_visible_ts_ns: i64,
    ) -> SignalSeed {
        SignalSeed {
            signal_id: [0x11; 32],
            extreme_side: side,
            pivot_price_u6,
            pivot_last_bar_ordinal,
            causal_visible_ts_ns,
        }
    }

    fn values_for(frame: &SessionFrame, s: &SignalSeed, slot: Slot) -> (SlotRow, String) {
        let prefix = SlotRow::compute(frame, s, slot, frame.session_end_ns);
        let values = format_values(frame, s, &prefix);
        (prefix, values)
    }

    // ---- passage/extremum in the very first window group ----

    #[test]
    fn mfe_attained_in_the_very_first_window_group() {
        // Groups: g0 before cutoff (irrelevant), g1..g3 in the window.
        // D1 cutoff = 1 bar => window_left = 1 (g1 itself), and the raw
        // favorable extreme (max hi) is attained AT g1 — the very first
        // group of the window.
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS, 2 * BAR_NS, 3 * BAR_NS],
            vec![95, 190, 80, 110],
            vec![100, 200, 150, 120],
            vec![GroupKind::Scalar; 4],
            Vec::new(),
        );
        let s = seed(Side::Low, 100, 0, 0);
        let (prefix, values) = values_for(&frame, &s, Slot::D1);
        assert_eq!(prefix.window_left, Some(1));
        assert_eq!(prefix.window_end, Some(4));

        // F = max(hi[1..=3]) = 200 @ index 1 (== window_left).
        // mfe_u6 = 200 - 100 = 100.
        // A = min(lo[1..=3]) = 80 @ index 2. mae_u6 = max(0, 100-80) = 20.
        // Giveback range = [1, 3] (same as full window since fav_index ==
        // left): G = min(lo[1..=3]) = 80 @ index 2 (same as A).
        // giveback_u6 = max(0, 200-80) = 120. retained_u6 = max(0,100-120)=0.
        assert_eq!(
            values,
            format!(
                "100\t1\t{}\tSCALAR\t20\t2\t{}\tSCALAR\t120\t2\t{}\t0",
                BAR_NS,
                2 * BAR_NS,
                2 * BAR_NS
            )
        );
    }

    // ---- window empty (SOURCE_CENSORED) ----

    #[test]
    fn window_empty_yields_source_censored_and_all_na_values() {
        // Both groups sit strictly before the cutoff, and no group exists
        // between the cutoff and the close: the window is empty.
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS],
            vec![100, 100],
            vec![100, 100],
            vec![GroupKind::Scalar; 2],
            Vec::new(),
        );
        let s = seed(Side::Low, 100, 1, 0); // D1 cutoff = 2 bars.
        let (prefix, values) = values_for(&frame, &s, Slot::D1);
        assert_eq!(prefix.window_frontier, WindowFrontier::SourceCensored);
        assert_eq!(prefix.window_left, prefix.window_end);
        assert_eq!(values, NA_VALUES);
    }

    // ---- slot close-truncated (DECISION_UNAVAILABLE) ----

    #[test]
    fn slot_close_truncated_is_decision_unavailable_all_na() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            2 * BAR_NS,
            vec![0, BAR_NS],
            vec![100, 100],
            vec![100, 100],
            vec![GroupKind::Scalar; 2],
            Vec::new(),
        );
        // D2 cutoff = 2 bars == session_end_ns: not strictly before it.
        let s = seed(Side::Low, 100, 0, 0);
        let (prefix, values) = values_for(&frame, &s, Slot::D2);
        assert_eq!(prefix.window_frontier, WindowFrontier::DecisionUnavailable);
        assert_eq!(values, NA_VALUES);
    }

    // ---- not yet visible at D1, visible at D2 ----

    #[test]
    fn not_visible_at_d1_but_visible_at_d2() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS, 2 * BAR_NS, 3 * BAR_NS],
            vec![95, 130, 150, 140],
            vec![100, 140, 180, 160],
            vec![GroupKind::Scalar; 4],
            Vec::new(),
        );
        // Visible strictly after D1's cutoff (1 bar) but at-or-before D2's
        // cutoff (2 bars).
        let s = seed(Side::Low, 100, 0, BAR_NS + 1);

        let (d1_prefix, d1_values) = values_for(&frame, &s, Slot::D1);
        assert_eq!(d1_prefix.window_frontier, WindowFrontier::NotVisible);
        assert_eq!(d1_values, NA_VALUES);

        let (d2_prefix, d2_values) = values_for(&frame, &s, Slot::D2);
        assert!(d2_prefix.visible_at_slot);
        assert_eq!(d2_prefix.window_left, Some(2));
        assert_eq!(d2_prefix.window_end, Some(4));
        // F = max(hi[2..=3]) = 180 @ index 2. mfe_u6 = 80.
        // A = min(lo[2..=3]) = 140 @ index 3. mae_u6 = max(0,100-140) = 0.
        // Giveback range = [2,3]: G = min(lo[2..=3]) = 140 @ index 3 (same).
        // giveback_u6 = max(0,180-140) = 40. retained_u6 = max(0,80-40)=40.
        assert_eq!(
            d2_values,
            format!(
                "80\t2\t{}\tSCALAR\t0\t3\t{}\tSCALAR\t40\t3\t{}\t40",
                2 * BAR_NS,
                3 * BAR_NS,
                3 * BAR_NS
            )
        );
    }

    // ---- same-group favorable+adverse touch ----

    #[test]
    fn same_group_favorable_and_adverse_touch() {
        // g1's own range spans both the favorable and adverse extremes.
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS, 2 * BAR_NS],
            vec![95, 10, 140],
            vec![100, 300, 150],
            vec![GroupKind::Scalar; 3],
            Vec::new(),
        );
        let s = seed(Side::Low, 100, 0, 0); // D1 cutoff = 1 bar => left = 1.
        let (prefix, values) = values_for(&frame, &s, Slot::D1);
        assert_eq!(prefix.window_left, Some(1));
        assert_eq!(prefix.window_end, Some(3));
        // F = max(hi[1..=2]) = 300 @ 1. A = min(lo[1..=2]) = 10 @ 1: SAME
        // group as the favorable extreme.
        // mfe_u6 = 200, mae_u6 = max(0,100-10) = 90.
        // Giveback range = [1,2]: G = min(lo[1..=2]) = 10 @ 1 (same group
        // again). giveback_u6 = max(0,300-10) = 290. retained = max(0,200-290)=0.
        assert_eq!(
            values,
            format!("200\t1\t{BAR_NS}\tSCALAR\t90\t1\t{BAR_NS}\tSCALAR\t290\t1\t{BAR_NS}\t0")
        );
    }

    // ---- heterogeneous-group touch ----

    #[test]
    fn heterogeneous_group_touch_reports_heterogeneous_kind() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS, 2 * BAR_NS],
            vec![95, 90, 80],
            vec![100, 250, 90],
            vec![
                GroupKind::Scalar,
                GroupKind::Heterogeneous,
                GroupKind::Scalar,
            ],
            Vec::new(),
        );
        let s = seed(Side::Low, 100, 0, 0); // D1 cutoff = 1 bar => left = 1.
        let (_prefix, values) = values_for(&frame, &s, Slot::D1);
        // F = max(hi[1..=2]) = 250 @ index 1 (the Heterogeneous group).
        let columns: Vec<&str> = values.split('\t').collect();
        assert_eq!(columns[1], "1"); // mfe_group_index
        assert_eq!(columns[3], "HETEROGENEOUS"); // mfe_group_kind
    }

    // ---- breaker-censored window ----

    #[test]
    fn breaker_censored_window_excludes_groups_past_the_breaker() {
        // A breaker starting just after g2 must exclude g3/g4's much larger
        // (and otherwise dominant) extremes from every F-EXT computation.
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS, 2 * BAR_NS, 3 * BAR_NS, 4 * BAR_NS],
            vec![95, 90, 290, 130, 10],
            vec![100, 150, 300, 140, 500],
            vec![GroupKind::Scalar; 5],
            vec![Breaker {
                start_ns: 2 * BAR_NS + 1,
                end_ns: 5 * BAR_NS,
            }],
        );
        let s = seed(Side::Low, 100, 0, 0); // D1 cutoff = 1 bar => left = 1.
        let (prefix, values) = values_for(&frame, &s, Slot::D1);
        assert_eq!(prefix.window_frontier, WindowFrontier::WideBreaker);
        // Observed window = [1, 3) (g3/g4, with hi 140/500, are excluded).
        assert_eq!(prefix.window_left, Some(1));
        assert_eq!(prefix.window_end, Some(3));
        // F = max(hi[1..=2]) = 300 @ 2. mfe_u6 = 200.
        // A = min(lo[1..=2]) = 90 @ 1. mae_u6 = max(0,100-90) = 10.
        // Giveback range = [2,2]: G = lo[2] = 290. giveback_u6=max(0,300-290)=10.
        // retained_u6 = max(0,200-10) = 190.
        assert_eq!(
            values,
            format!(
                "200\t2\t{}\tSCALAR\t10\t1\t{}\tSCALAR\t10\t2\t{}\t190",
                2 * BAR_NS,
                BAR_NS,
                2 * BAR_NS
            )
        );
    }

    // ---- giveback after the favorable extreme ----

    #[test]
    fn giveback_after_favorable_extreme_uses_the_post_extreme_range_only() {
        // The whole-window adverse minimum (lo=10) sits BEFORE the
        // favorable extreme; the correct post-extreme minimum (lo=150,
        // tie broken leftmost) sits strictly after it. A giveback that
        // wrongly reused the whole-window adverse extreme would report
        // giveback_u6 = 250-10 = 240 instead of the correct 250-150 = 100.
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS, 2 * BAR_NS, 3 * BAR_NS, 4 * BAR_NS, 5 * BAR_NS],
            vec![999, 10, 150, 180, 150, 200],
            vec![999, 120, 250, 140, 90, 200],
            vec![GroupKind::Scalar; 6],
            Vec::new(),
        );
        let s = seed(Side::Low, 100, 0, 0); // D1 cutoff = 1 bar => left = 1.
        let (prefix, values) = values_for(&frame, &s, Slot::D1);
        assert_eq!(prefix.window_left, Some(1));
        assert_eq!(prefix.window_end, Some(6));

        // F = max(hi[1..=5]) = 250 @ index 2 (interior: not left, not last).
        // A = min(lo[1..=5]) = 10 @ index 1. mae_u6 = max(0,100-10) = 90.
        // Giveback range = [2,5]: min(lo[2..=5]) = 150, leftmost tie @ 2.
        // giveback_u6 = max(0, 250-150) = 100.
        // retained_u6 = max(0, 150 - 100) = 50.
        assert_eq!(
            values,
            format!(
                "150\t2\t{}\tSCALAR\t90\t1\t{}\tSCALAR\t100\t2\t{}\t50",
                2 * BAR_NS,
                BAR_NS,
                2 * BAR_NS
            )
        );
    }

    // ---------------------------- write_tsv ----------------------------

    #[test]
    fn write_tsv_emits_the_header_and_one_row_per_signal_times_slot() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS, 2 * BAR_NS],
            vec![95, 90, 80],
            vec![100, 150, 200],
            vec![GroupKind::Scalar; 3],
            Vec::new(),
        );
        let seeds = vec![seed(Side::Low, 100, 0, 0)];

        let out_path =
            std::env::temp_dir().join(format!("f_ext_write_tsv_test_{}.tsv", std::process::id()));
        write_tsv(&frame, &seeds, &out_path).expect("writes f_ext.tsv");
        let content = std::fs::read_to_string(&out_path).expect("f_ext.tsv exists");
        std::fs::remove_file(&out_path).ok();

        let mut lines = content.lines();
        assert_eq!(lines.next(), Some(HEADER));
        let d1 = lines.next().expect("D1 row");
        let d2 = lines.next().expect("D2 row");
        let d3 = lines.next().expect("D3 row");
        assert_eq!(lines.next(), None);

        assert!(d1.starts_with("TEST\t"));
        assert!(d1.contains("\tD1\t"));
        assert!(d2.contains("\tD2\t"));
        assert!(d3.contains("\tD3\t"));
        // 10 prefix + 12 value columns.
        assert_eq!(d1.split('\t').count(), 22);
    }
}
