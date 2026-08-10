//! F-PASS — first-passage ladder family (11 IWM-bps thresholds, both
//! directions: first-passage index/time and competing-risk ordering).
//! Design authority: `docs/specs/label_kernel_design_v1.md` §"Families
//! (EVENTS.2 wave)" ("F-PASS — first-passage ladder") and
//! `docs/specs/label_probe_schema_v1.md` §"`f_pass.tsv` (family F-PASS)".
//!
//! Kernel cost per anchor: 11 thresholds × 2 sides = 22
//! [`crate::extrema::ExtremaTree`] descent queries, each O(log n) — matching
//! the design doc's declared "22 descent queries + O(1) merge per anchor,
//! O(log n) each". [`passage_at_threshold`] is reused verbatim by
//! `crate::f_ord` (design doc: "no new scans").

use crate::anchor::{Side, SignalSeed, Slot, SlotRow, WindowFrontier};
use crate::frame::{GroupKind, SessionFrame};
use std::fmt::Write as _;
use std::fs::File;
use std::io::{self, BufWriter, Write as _};
use std::path::Path;

/// The registered eleven-value bps ladder (CONV §2
/// `INTRABAR_TARGET_SCALES_BPS`), in ladder order — the column order for
/// every `fp_*` group in `f_pass.tsv`.
pub const LADDER_BPS: [u16; 11] = [5, 10, 15, 20, 30, 40, 60, 80, 120, 160, 240];

/// One threshold side's first-passage touch state
/// (`docs/specs/label_probe_schema_v1.md` "`f_pass.tsv`"): `Exact` /
/// `IntervalAmbiguous` come from the touched group's [`GroupKind`] (CONV §7
/// tie rule); `NotTouched` when no group in the window crosses the level;
/// `OutOfDomain` when the level itself is non-positive (CONV §2: "the lower
/// band must stay > 0").
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TouchState {
    Exact,
    IntervalAmbiguous,
    NotTouched,
    OutOfDomain,
}

impl TouchState {
    /// The wire string for `fp_fav_<N>_state` / `fp_adv_<N>_state`.
    #[must_use]
    pub const fn wire(self) -> &'static str {
        match self {
            Self::Exact => "EXACT",
            Self::IntervalAmbiguous => "INTERVAL_AMBIGUOUS",
            Self::NotTouched => "NOT_TOUCHED",
            Self::OutOfDomain => "OUT_OF_DOMAIN",
        }
    }
}

/// One threshold side's full first-passage result: the touched group's
/// index/timestamp (`None` unless [`TouchState::Exact`] or
/// [`TouchState::IntervalAmbiguous`]) plus its state.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ThresholdTouch {
    pub index: Option<usize>,
    pub ts_ns: Option<i64>,
    pub state: TouchState,
}

impl ThresholdTouch {
    const fn out_of_domain() -> Self {
        Self {
            index: None,
            ts_ns: None,
            state: TouchState::OutOfDomain,
        }
    }

    const fn not_touched() -> Self {
        Self {
            index: None,
            ts_ns: None,
            state: TouchState::NotTouched,
        }
    }
}

/// `fp_first_<N>` — competing-risk resolution between the favorable and
/// adverse touches at one threshold (`docs/specs/label_probe_schema_v1.md`
/// "`f_pass.tsv`").
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum FirstState {
    FavorableFirst,
    AdverseFirst,
    SameGroup,
    Neither,
    Na,
}

impl FirstState {
    /// The wire string for `fp_first_<N>`.
    #[must_use]
    pub const fn wire(self) -> &'static str {
        match self {
            Self::FavorableFirst => "FAVORABLE_FIRST",
            Self::AdverseFirst => "ADVERSE_FIRST",
            Self::SameGroup => "SAME_GROUP",
            Self::Neither => "NEITHER",
            Self::Na => "NA",
        }
    }
}

/// One threshold's complete first-passage outcome: both sides' touches plus
/// the competing-risk `fp_first_<N>` derivation.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PassageResult {
    pub fav: ThresholdTouch,
    pub adv: ThresholdTouch,
    pub first: FirstState,
}

/// The exact registered bps→distance formula (CONV §2, pinned rule 8):
/// `distance_u6 = ceil(anchor_u6 * bps / 10_000)`, floored at a minimum of 1,
/// computed as the integer identity `(numerator + 9_999) / 10_000` in `i128`
/// arithmetic (no floating-point price math anywhere, per the design doc).
///
/// O(1).
///
/// # Panics
///
/// Panics if the `i128` distance does not fit back into `i64` — unreachable
/// for any registered IWM anchor price against the fixed bps ladder above
/// (anchor prices are many orders of magnitude under `i64::MAX / 240`).
#[must_use]
pub fn threshold_distance_u6(anchor_u6: i64, bps: u16) -> i64 {
    let numerator = i128::from(anchor_u6) * i128::from(bps);
    let distance = ((numerator + 9_999) / 10_000).max(1);
    i64::try_from(distance)
        .expect("threshold distance fits in i64 for any registered anchor price/bps pair")
}

/// Favorable/adverse threshold price levels at `distance_u6` from
/// `anchor_u6`, by direction shorthand (`docs/specs/label_probe_schema_v1.md`
/// "Direction shorthand": LOW → favorable is UP, i.e. `anchor + distance`;
/// HIGH → mirror). O(1).
fn favorable_adverse_levels(side: Side, anchor_u6: i64, distance_u6: i64) -> (i64, i64) {
    let up = anchor_u6
        .checked_add(distance_u6)
        .expect("anchor + distance overflowed i64 for a registered anchor price");
    let down = anchor_u6
        .checked_sub(distance_u6)
        .expect("anchor - distance overflowed i64 for a registered anchor price");
    match side {
        Side::Low => (up, down),
        Side::High => (down, up),
    }
}

/// [`TouchState::Exact`] for a [`GroupKind::Scalar`] touched group, else
/// [`TouchState::IntervalAmbiguous`] (CONV §7 tie rule).
fn group_touch_state(frame: &SessionFrame, index: usize) -> TouchState {
    match frame.kind[index] {
        GroupKind::Scalar => TouchState::Exact,
        GroupKind::Heterogeneous => TouchState::IntervalAmbiguous,
    }
}

/// Leftmost group in `[window_left, window_end)` with `frame.m_hi[g] >=
/// level` (an "upward" touch), or [`TouchState::NotTouched`] if none. O(log
/// n) via [`crate::extrema::ExtremaTree::first_at_or_above`] plus an O(1)
/// window-end check (the tree only knows a lower bound, so a global match
/// past `window_end` is explicitly discarded rather than counted).
fn touch_up(
    frame: &SessionFrame,
    level: i64,
    window_left: usize,
    window_end: usize,
) -> ThresholdTouch {
    if window_left >= window_end {
        return ThresholdTouch::not_touched();
    }
    match frame.extrema().first_at_or_above(window_left, level) {
        Some(index) if index < window_end => ThresholdTouch {
            index: Some(index),
            ts_ns: Some(frame.ts_ns[index]),
            state: group_touch_state(frame, index),
        },
        _ => ThresholdTouch::not_touched(),
    }
}

/// Symmetric to [`touch_up`]: leftmost group in `[window_left, window_end)`
/// with `frame.m_lo[g] <= level` (a "downward" touch).
fn touch_down(
    frame: &SessionFrame,
    level: i64,
    window_left: usize,
    window_end: usize,
) -> ThresholdTouch {
    if window_left >= window_end {
        return ThresholdTouch::not_touched();
    }
    match frame.extrema().first_at_or_below(window_left, level) {
        Some(index) if index < window_end => ThresholdTouch {
            index: Some(index),
            ts_ns: Some(frame.ts_ns[index]),
            state: group_touch_state(frame, index),
        },
        _ => ThresholdTouch::not_touched(),
    }
}

/// `fp_first_<N>` derivation (`docs/specs/label_probe_schema_v1.md`
/// "`f_pass.tsv`"): `Na` when either side is [`TouchState::OutOfDomain`] or
/// the window itself is empty; else the earlier-indexed side, `SameGroup` on
/// an index tie, `Neither` when neither side touched.
fn first_state(fav: ThresholdTouch, adv: ThresholdTouch, window_empty: bool) -> FirstState {
    if window_empty || fav.state == TouchState::OutOfDomain || adv.state == TouchState::OutOfDomain
    {
        return FirstState::Na;
    }
    match (fav.index, adv.index) {
        (Some(f), Some(a)) if f == a => FirstState::SameGroup,
        (Some(f), Some(a)) if f < a => FirstState::FavorableFirst,
        (Some(_) | None, Some(_)) => FirstState::AdverseFirst,
        (Some(_), None) => FirstState::FavorableFirst,
        (None, None) => FirstState::Neither,
    }
}

/// Computes the full first-passage outcome for one anchor at one bps
/// threshold `bps`, over the caller's already-resolved window
/// `[window_left, window_end)` (design doc "F-PASS"; pinned rule 8 for the
/// bps→distance formula; schema "Direction shorthand" for level/series
/// selection). Shared verbatim by `crate::f_ord` (design doc: "no new
/// scans") — callers must have already excluded the
/// `DECISION_UNAVAILABLE`/`NOT_VISIBLE` rows, whose value columns are `NA`
/// by a different, row-level rule (`docs/specs/label_probe_schema_v1.md`
/// "Family-file common prefix"), not by anything this function computes.
///
/// O(log n): at most two [`crate::extrema::ExtremaTree`] descent queries.
#[must_use]
pub fn passage_at_threshold(
    frame: &SessionFrame,
    side: Side,
    anchor_u6: i64,
    bps: u16,
    window_left: usize,
    window_end: usize,
) -> PassageResult {
    let distance_u6 = threshold_distance_u6(anchor_u6, bps);
    let (fav_level, adv_level) = favorable_adverse_levels(side, anchor_u6, distance_u6);

    let fav = if fav_level <= 0 {
        ThresholdTouch::out_of_domain()
    } else {
        match side {
            Side::Low => touch_up(frame, fav_level, window_left, window_end),
            Side::High => touch_down(frame, fav_level, window_left, window_end),
        }
    };
    let adv = if adv_level <= 0 {
        ThresholdTouch::out_of_domain()
    } else {
        match side {
            Side::Low => touch_down(frame, adv_level, window_left, window_end),
            Side::High => touch_up(frame, adv_level, window_left, window_end),
        }
    };

    let first = first_state(fav, adv, window_left >= window_end);
    PassageResult { fav, adv, first }
}

/// The `f_pass.tsv` header: the ten-column common prefix
/// (`crate::anchor::SlotRow::format_prefix`) followed by seven columns per
/// [`LADDER_BPS`] entry, in ladder order
/// (`docs/specs/label_probe_schema_v1.md` "`f_pass.tsv`").
#[must_use]
pub fn header() -> String {
    let mut out = String::from(
        "day\tsignal_id\tslot\tseed_bar_ordinal\tcutoff_ts_ns\tslot_available\t\
         visible_at_slot\twindow_left\twindow_end\twindow_frontier",
    );
    for n in LADDER_BPS {
        write!(
            out,
            "\tfp_fav_{n}_index\tfp_fav_{n}_ts_ns\tfp_fav_{n}_state\t\
             fp_adv_{n}_index\tfp_adv_{n}_ts_ns\tfp_adv_{n}_state\tfp_first_{n}"
        )
        .expect("writing to a String cannot fail");
    }
    out
}

/// Appends one side's three columns (`index`, `ts_ns`, `state`), tab-prefixed.
fn push_touch_columns(line: &mut String, touch: &ThresholdTouch) {
    match (touch.index, touch.ts_ns) {
        (Some(index), Some(ts_ns)) => write!(line, "\t{index}\t{ts_ns}\t{}", touch.state.wire()),
        _ => write!(line, "\tNA\tNA\t{}", touch.state.wire()),
    }
    .expect("writing to a String cannot fail");
}

/// Appends one threshold's full seven value columns (`fp_fav_*`, `fp_adv_*`,
/// `fp_first_*`) to `line`.
fn push_passage_columns(line: &mut String, result: &PassageResult) {
    push_touch_columns(line, &result.fav);
    push_touch_columns(line, &result.adv);
    write!(line, "\t{}", result.first.wire()).expect("writing to a String cannot fail");
}

/// Computes every `(signal, slot)` row (common prefix + value columns) as
/// one tab-joined line, no header, no trailing newline: one row per
/// `(signal, slot)`, slots in order `D1, D2, D3` (slot-minor), signals in
/// the order given by `seeds` — which the caller must already have in
/// `day_signals.tsv` publication order (`docs/specs/label_probe_schema_v1.md`
/// "Family-file common prefix"). This is the same per-row text
/// [`write_tsv`] writes to disk, reusable in-memory (e.g. for parquet
/// publication) without going through a file.
///
/// Rows whose window frontier is `DECISION_UNAVAILABLE`/`NOT_VISIBLE` carry
/// literal `NA` in all 77 value columns (the schema's row-level rule); every
/// other row (including `SOURCE_CENSORED`, whose window is simply empty)
/// computes all 11 ladder thresholds against the resolved
/// `[window_left, window_end)` via [`passage_at_threshold`].
///
/// O(`seeds.len()` × 3 slots × 11 thresholds), each threshold O(log n).
///
/// # Panics
///
/// Panics if a row's window frontier is neither `DECISION_UNAVAILABLE` nor
/// `NOT_VISIBLE` yet its `window_left`/`window_end` are absent —
/// unreachable per `SlotRow::compute`'s own invariant (those two frontiers
/// are the only ones that leave the window unset).
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
                    line.push_str("\tNA\tNA\tNA\tNA\tNA\tNA\tNA");
                }
            } else {
                let window_left = row
                    .window_left
                    .expect("window present when slot available and visible");
                let window_end = row
                    .window_end
                    .expect("window present when slot available and visible");
                for bps in LADDER_BPS {
                    let result = passage_at_threshold(
                        frame,
                        seed.extreme_side,
                        seed.pivot_price_u6,
                        bps,
                        window_left,
                        window_end,
                    );
                    push_passage_columns(&mut line, &result);
                }
            }
            out.push(line);
        }
    }
    out
}

/// Writes `f_pass.tsv` for one session ([`rows`]).
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
    use crate::frame::{Breaker, GroupKind};

    const BAR_NS: i64 = 60_000_000_000;

    fn seed(
        side: Side,
        pivot_last_bar_ordinal: u64,
        causal_visible_ts_ns: i64,
        pivot_price_u6: i64,
    ) -> SignalSeed {
        SignalSeed {
            signal_id: [0xab; 32],
            extreme_side: side,
            pivot_price_u6,
            pivot_last_bar_ordinal,
            causal_visible_ts_ns,
        }
    }

    // ------------------------ threshold_distance_u6 ------------------------

    #[test]
    fn distance_matches_hand_computed_ceiling() {
        // numerator = 333_333 * 7 = 2_333_331; ceil(2_333_331 / 10_000) = 234
        // (234 * 10_000 = 2_340_000 >= 2_333_331; 233 * 10_000 = 2_330_000 < it).
        assert_eq!(threshold_distance_u6(333_333, 7), 234);
    }

    #[test]
    fn distance_is_exact_hundredths_for_a_round_anchor() {
        // anchor = 1_000_000 => anchor/10_000 = 100 exactly, so distance = N * 100.
        for &n in &LADDER_BPS {
            assert_eq!(threshold_distance_u6(1_000_000, n), i64::from(n) * 100);
        }
    }

    // --------------------- passage_at_threshold: core cases ---------------------

    #[test]
    fn passage_touches_in_the_very_first_window_group() {
        // 2 groups; window = [1, 2) (only the group at BAR_NS).
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS],
            vec![100, 999_600],
            vec![100, 1_000_500],
            vec![GroupKind::Scalar, GroupKind::Scalar],
            Vec::new(),
        );
        // Favorable (LOW = up) level at 5bps: 1_000_000 + 500 = 1_000_500,
        // exactly the first (only) window group's m_hi.
        let result = passage_at_threshold(&frame, Side::Low, 1_000_000, 5, 1, 2);
        assert_eq!(
            result.fav,
            ThresholdTouch {
                index: Some(1),
                ts_ns: Some(BAR_NS),
                state: TouchState::Exact,
            }
        );
        // Adverse level 999_500; the group's m_lo is 999_600, which does not
        // cross it.
        assert_eq!(result.adv, ThresholdTouch::not_touched());
        assert_eq!(result.first, FirstState::FavorableFirst);
    }

    #[test]
    fn passage_window_empty_is_not_touched_and_first_is_na() {
        // window_left == window_end == 2: SOURCE_CENSORED (empty window).
        let frame = SessionFrame::from_parts_for_test(
            0,
            5 * BAR_NS,
            vec![0, BAR_NS],
            vec![100, 100],
            vec![100, 100],
            vec![GroupKind::Scalar; 2],
            Vec::new(),
        );
        let result = passage_at_threshold(&frame, Side::Low, 1_000_000, 5, 2, 2);
        assert_eq!(result.fav, ThresholdTouch::not_touched());
        assert_eq!(result.adv, ThresholdTouch::not_touched());
        assert_eq!(result.first, FirstState::Na);
    }

    #[test]
    fn passage_same_group_dual_touch_scalar() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS],
            vec![100, 998_000],
            vec![100, 1_002_000],
            vec![GroupKind::Scalar, GroupKind::Scalar],
            Vec::new(),
        );
        // fav level 1_000_500 <= m_hi 1_002_000; adv level 999_500 >= m_lo
        // 998_000: both cross in the SAME group (index 1).
        let result = passage_at_threshold(&frame, Side::Low, 1_000_000, 5, 1, 2);
        assert_eq!(
            result.fav,
            ThresholdTouch {
                index: Some(1),
                ts_ns: Some(BAR_NS),
                state: TouchState::Exact,
            }
        );
        assert_eq!(
            result.adv,
            ThresholdTouch {
                index: Some(1),
                ts_ns: Some(BAR_NS),
                state: TouchState::Exact,
            }
        );
        assert_eq!(result.first, FirstState::SameGroup);
    }

    #[test]
    fn passage_heterogeneous_group_touch_is_interval_ambiguous() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS],
            vec![100, 999_990],
            vec![100, 1_000_500],
            vec![GroupKind::Scalar, GroupKind::Heterogeneous],
            Vec::new(),
        );
        // fav level 1_000_500 == m_hi exactly, in a Heterogeneous group.
        let result = passage_at_threshold(&frame, Side::Low, 1_000_000, 5, 1, 2);
        assert_eq!(
            result.fav,
            ThresholdTouch {
                index: Some(1),
                ts_ns: Some(BAR_NS),
                state: TouchState::IntervalAmbiguous,
            }
        );
        // adv level 999_500; m_lo 999_990 does not cross it.
        assert_eq!(result.adv, ThresholdTouch::not_touched());
        assert_eq!(result.first, FirstState::FavorableFirst);
    }

    #[test]
    fn passage_breaker_censored_window_excludes_a_touch_beyond_it() {
        // Groups at 0, BAR_NS, 5*BAR_NS; a breaker from 2*BAR_NS to 4*BAR_NS.
        // D1 cutoff = BAR_NS => window_left = 1 (end_position(BAR_NS)).
        // breaker_start_after(BAR_NS) = 2*BAR_NS < session_end(10*BAR_NS) =>
        // observed end = 2*BAR_NS => window_end = end_position(2*BAR_NS) = 2.
        // So only group index 1 is in-window; group index 2 (which WOULD
        // touch favorable) is correctly excluded by the breaker censor.
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
        // window = [1, 2) as derived above.
        let result = passage_at_threshold(&frame, Side::Low, 1_000_000, 5, 1, 2);
        // Favorable level 1_000_500: group 1's m_hi is 999_000 (no touch);
        // group 2's m_hi (2_000_000) WOULD touch but is beyond window_end.
        assert_eq!(result.fav, ThresholdTouch::not_touched());
        // Adverse level 999_500: group 1's m_lo is 998_000 <= it: touched.
        assert_eq!(
            result.adv,
            ThresholdTouch {
                index: Some(1),
                ts_ns: Some(BAR_NS),
                state: TouchState::Exact,
            }
        );
        assert_eq!(result.first, FirstState::AdverseFirst);
    }

    #[test]
    fn passage_out_of_domain_adverse_level_tiny_price_huge_bps() {
        // anchor = 1 u6, N = 240: distance = max(1, ceil(240/10_000)) = 1.
        // adverse level (LOW => P - distance) = 1 - 1 = 0 <= 0: OUT_OF_DOMAIN.
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0],
            vec![0],
            vec![5],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let result = passage_at_threshold(&frame, Side::Low, 1, 240, 0, 1);
        assert_eq!(result.adv.state, TouchState::OutOfDomain);
        assert_eq!(result.adv.index, None);
        // Favorable level (P + distance) = 2, well in-domain; the single
        // group's m_hi = 5 touches it.
        assert_eq!(
            result.fav,
            ThresholdTouch {
                index: Some(0),
                ts_ns: Some(0),
                state: TouchState::Exact,
            }
        );
        // Either side OUT_OF_DOMAIN => fp_first is NA even though the
        // favorable side touched.
        assert_eq!(result.first, FirstState::Na);
    }

    #[test]
    fn passage_high_side_mirrors_direction() {
        // HIGH: favorable = DOWN (m_lo <= P - distance), adverse = UP
        // (m_hi >= P + distance).
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS],
            vec![100, 999_000],
            vec![100, 1_000_600],
            vec![GroupKind::Scalar, GroupKind::Scalar],
            Vec::new(),
        );
        let result = passage_at_threshold(&frame, Side::High, 1_000_000, 5, 1, 2);
        // fav level = 999_500 (down); m_lo = 999_000 <= it: touched.
        assert_eq!(result.fav.state, TouchState::Exact);
        assert_eq!(result.fav.index, Some(1));
        // adv level = 1_000_500 (up); m_hi = 1_000_600 >= it: touched.
        assert_eq!(result.adv.state, TouchState::Exact);
        assert_eq!(result.adv.index, Some(1));
        assert_eq!(result.first, FirstState::SameGroup);
    }

    // --------------------------- write_tsv: row shape ---------------------------

    fn temp_out_path(name: &str) -> std::path::PathBuf {
        std::env::temp_dir().join(format!("f_pass_test_{}_{name}.tsv", std::process::id()))
    }

    #[test]
    fn write_tsv_header_has_the_exact_expected_column_count() {
        let header = header();
        let columns: Vec<&str> = header.split('\t').collect();
        // 10 common-prefix columns + 11 thresholds * 7 columns each.
        assert_eq!(columns.len(), 10 + 11 * 7);
        assert_eq!(columns[0], "day");
        assert_eq!(columns[9], "window_frontier");
        assert_eq!(columns[10], "fp_fav_5_index");
        assert_eq!(columns[16], "fp_first_5");
        assert_eq!(columns[columns.len() - 1], "fp_first_240");
    }

    #[test]
    fn write_tsv_decision_unavailable_row_is_all_na() {
        // session_end at 3 bars; seed_bar_ordinal = 1 => D1 cutoff = 2*BAR_NS
        // (< session_end: available), D2 cutoff = 3*BAR_NS == session_end
        // (not strictly before: DECISION_UNAVAILABLE), D3 cutoff = 4*BAR_NS
        // (past session_end: DECISION_UNAVAILABLE too).
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
        // D1 (cutoff = 1*BAR_NS < 3*BAR_NS) is available.
        let d1_cols: Vec<&str> = d1.split('\t').collect();
        assert_ne!(d1_cols[9], "DECISION_UNAVAILABLE");

        std::fs::remove_file(&path).ok();
    }

    #[test]
    fn write_tsv_not_visible_at_d1_then_visible_at_d2() {
        // seed_bar_ordinal = 0 => D1 cutoff = BAR_NS, D2 cutoff = 2*BAR_NS.
        // causal_visible_ts_ns = BAR_NS + 1: strictly after D1's cutoff (not
        // visible yet) but at/before D2's cutoff (visible).
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

        // D2: window_left = end_position(2*BAR_NS) = 2 (group index 2 IS the
        // cutoff group, included); window covers [2, 3).
        let d2_cols: Vec<&str> = d2.split('\t').collect();
        assert_eq!(d2_cols[9], "COMPLETE");
        assert_eq!(d2_cols[7], "2"); // window_left
        assert_eq!(d2_cols[8], "3"); // window_end
        // fp_fav_5_index / ts_ns / state (columns 10, 11, 12): the group at
        // index 2 touches the 5bps favorable level exactly.
        assert_eq!(d2_cols[10], "2");
        assert_eq!(d2_cols[11], (2 * BAR_NS).to_string());
        assert_eq!(d2_cols[12], "EXACT");

        std::fs::remove_file(&path).ok();
    }
}
