//! Per-anchor seed data and the family-file common prefix (design authority:
//! `docs/specs/label_kernel_design_v1.md` §"Registered anchor resolution"
//! and `docs/specs/label_probe_schema_v1.md` §"Family-file common prefix").

use crate::frame::SessionFrame;

/// Registered nanoseconds-per-minute bar duration (CONV §3).
const NANOSECONDS_PER_BAR: i64 = 60_000_000_000;

/// Truth/signal side (CONV §5 `EpisodeExtremeSide`, wire codes `"LOW"` /
/// `"HIGH"`). `Low` = a confirmed low pivot (turn upward expected — the
/// favorable direction is UP); `High` = a confirmed high pivot (favorable
/// direction DOWN).
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Side {
    Low,
    High,
}

impl Side {
    /// Parses the registered wire code (`"LOW"` / `"HIGH"`, CONV §5). `None`
    /// for anything else.
    #[must_use]
    pub fn from_wire(value: &str) -> Option<Self> {
        match value {
            "LOW" => Some(Self::Low),
            "HIGH" => Some(Self::High),
            _ => None,
        }
    }
}

/// One event-signal row's seed data, as consumed by the per-slot anchor
/// resolution (pinned rules 2-4): the signal identity, the favorable-
/// direction side, the anchor price, the signal's own seed bar, and its
/// causal-availability timestamp.
#[derive(Clone, Copy, Debug)]
pub struct SignalSeed {
    pub signal_id: [u8; 32],
    pub extreme_side: Side,
    /// Anchor price `P` (pinned rule 4): `pivot_price_u6`.
    pub pivot_price_u6: i64,
    /// The signal's own seed bar (pinned rule 2): `pivot_last_bar_ordinal`.
    pub pivot_last_bar_ordinal: u64,
    pub causal_visible_ts_ns: i64,
}

/// One action-clock slot: the end of the first (`D1`), second (`D2`), or
/// third (`D3`) completed one-minute bar after the signal's seed bar
/// (`docs/specs/selection_action_window_d3_amendment_v1.md`).
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Slot {
    D1,
    D2,
    D3,
}

impl Slot {
    /// All three slots, in the schema's row order (`label_probe_schema_v1.md`
    /// "Family-file common prefix").
    pub const ALL: [Self; 3] = [Self::D1, Self::D2, Self::D3];

    /// The registered slot-clock offset in whole one-minute bars past the
    /// seed bar (`k` in `cutoff_k_ts`, pinned rule 2).
    #[must_use]
    pub const fn k(self) -> i64 {
        match self {
            Self::D1 => 1,
            Self::D2 => 2,
            Self::D3 => 3,
        }
    }

    /// The wire string for the family-file `slot` column.
    #[must_use]
    pub const fn wire(self) -> &'static str {
        match self {
            Self::D1 => "D1",
            Self::D2 => "D2",
            Self::D3 => "D3",
        }
    }
}

/// How a slot's forward window terminated (`label_probe_schema_v1.md`
/// "Family-file common prefix"; precedence `DecisionUnavailable >
/// NotVisible > SourceCensored > WideBreaker > OfficialCloseTruncated >
/// Complete`).
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum WindowFrontier {
    DecisionUnavailable,
    NotVisible,
    SourceCensored,
    WideBreaker,
    OfficialCloseTruncated,
    Complete,
}

impl WindowFrontier {
    /// The `SCREAMING_SNAKE` wire string for the `window_frontier` column.
    #[must_use]
    pub const fn wire(self) -> &'static str {
        match self {
            Self::DecisionUnavailable => "DECISION_UNAVAILABLE",
            Self::NotVisible => "NOT_VISIBLE",
            Self::SourceCensored => "SOURCE_CENSORED",
            Self::WideBreaker => "WIDE_BREAKER",
            Self::OfficialCloseTruncated => "OFFICIAL_CLOSE_TRUNCATED",
            Self::Complete => "COMPLETE",
        }
    }
}

/// The ten-column family-file common prefix for one `(signal, slot)` pair
/// (`label_probe_schema_v1.md` "Family-file common prefix"): `day` is
/// supplied separately by [`SlotRow::format_prefix`] (it is the same for
/// every row in a day's family file, so it is not stored per row here).
#[derive(Clone, Debug)]
pub struct SlotRow {
    pub signal_id: [u8; 32],
    pub slot: Slot,
    pub seed_bar_ordinal: u64,
    pub cutoff_ts_ns: i64,
    pub slot_available: bool,
    pub visible_at_slot: bool,
    pub window_left: Option<usize>,
    pub window_end: Option<usize>,
    pub window_frontier: WindowFrontier,
}

impl SlotRow {
    /// Computes the common prefix for one `(signal, slot)` pair against
    /// `nominal_end_ns` (`frame.session_end_ns` for F-EXT/F-PASS/F-ORD; the
    /// per-horizon nominal end for F-TERM, whose own common prefix uses the
    /// CLOSE horizon — i.e. `frame.session_end_ns` again).
    ///
    /// Exact algorithm, pinned rules 2-6:
    /// - `cutoff_ts_ns = session_start_ns + (seed_bar_ordinal + slot.k()) *
    ///   60e9`; `slot_available = cutoff_ts_ns < session_end_ns`;
    ///   `visible_at_slot = causal_visible_ts_ns <= cutoff_ts_ns`.
    /// - Unavailable or not-yet-visible rows carry no window (both `NA`).
    /// - Otherwise `left = end_position(cutoff)`, `requested_end =
    ///   min(nominal_end_ns, session_end_ns)`, `end =
    ///   end_position(min(requested_end, first_breaker_start_after(cutoff)))`;
    ///   frontier is `SourceCensored` if the window is empty, else
    ///   `WideBreaker` if a breaker starts strictly after cutoff and before
    ///   `requested_end`, else `OfficialCloseTruncated` if `nominal_end_ns >
    ///   session_end_ns`, else `Complete`.
    ///
    /// O(log n): two [`SessionFrame::end_position`] descents plus one
    /// [`SessionFrame::first_breaker_start_after`] descent, `n` =
    /// `frame.group_count()`.
    ///
    /// # Panics
    ///
    /// Panics if `seed.pivot_last_bar_ordinal + slot.k()` or the resulting
    /// nanosecond offset overflows `i64` — unreachable for any registered
    /// session (bar ordinals are bounded by `expected_bar_count`, at most a
    /// few hundred).
    #[must_use]
    pub fn compute(
        frame: &SessionFrame,
        seed: &SignalSeed,
        slot: Slot,
        nominal_end_ns: i64,
    ) -> Self {
        let seed_bar_ordinal = seed.pivot_last_bar_ordinal;
        let bars_after_start = i64::try_from(seed_bar_ordinal)
            .expect("pivot_last_bar_ordinal fits in i64")
            .checked_add(slot.k())
            .expect("seed_bar_ordinal + slot offset overflowed i64");
        let cutoff_ts_ns = bars_after_start
            .checked_mul(NANOSECONDS_PER_BAR)
            .and_then(|offset| frame.session_start_ns.checked_add(offset))
            .expect("cutoff_ts_ns arithmetic overflowed i64");

        let slot_available = cutoff_ts_ns < frame.session_end_ns;
        let visible_at_slot = seed.causal_visible_ts_ns <= cutoff_ts_ns;

        let (window_left, window_end, window_frontier) = if !slot_available {
            (None, None, WindowFrontier::DecisionUnavailable)
        } else if !visible_at_slot {
            (None, None, WindowFrontier::NotVisible)
        } else {
            let left = frame.end_position(cutoff_ts_ns);
            let requested_end_ns = nominal_end_ns.min(frame.session_end_ns);
            let breaker_start = frame.first_breaker_start_after(cutoff_ts_ns);
            let observed_end_ns =
                breaker_start.map_or(requested_end_ns, |start| start.min(requested_end_ns));
            let end = frame.end_position(observed_end_ns);
            let frontier = if left >= end {
                WindowFrontier::SourceCensored
            } else if breaker_start.is_some_and(|start| start < requested_end_ns) {
                WindowFrontier::WideBreaker
            } else if nominal_end_ns > frame.session_end_ns {
                WindowFrontier::OfficialCloseTruncated
            } else {
                WindowFrontier::Complete
            };
            (Some(left), Some(end), frontier)
        };

        Self {
            signal_id: seed.signal_id,
            slot,
            seed_bar_ordinal,
            cutoff_ts_ns,
            slot_available,
            visible_at_slot,
            window_left,
            window_end,
            window_frontier,
        }
    }

    /// Formats the ten common-prefix columns — `day  signal_id  slot
    /// seed_bar_ordinal  cutoff_ts_ns  slot_available  visible_at_slot
    /// window_left  window_end  window_frontier` — tab-separated, no
    /// trailing newline (`label_probe_schema_v1.md` "Formatting rules"; `day`
    /// is passed in since it is constant across every row in a day's file).
    ///
    /// O(1) (a fixed 32-byte digest hex-encode plus a handful of
    /// integer/enum fields).
    #[must_use]
    pub fn format_prefix(&self, day: &str) -> String {
        format!(
            "{day}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}",
            hex32(&self.signal_id),
            self.slot.wire(),
            self.seed_bar_ordinal,
            self.cutoff_ts_ns,
            bool_wire(self.slot_available),
            bool_wire(self.visible_at_slot),
            opt_usize_wire(self.window_left),
            opt_usize_wire(self.window_end),
            self.window_frontier.wire(),
        )
    }
}

/// The ten-column family-file common prefix's own header row, verbatim
/// (`docs/specs/label_probe_schema_v1.md` "Family-file common prefix") —
/// every family's own header starts with exactly these ten column names.
/// Published standalone as `event_index.parquet`'s schema (design brief §D:
/// "signal → anchor bookkeeping"): the one place this ten-column resolution
/// is recorded per `(signal, slot)` without any family's own value columns.
pub const COMMON_PREFIX_HEADER: &str = "day\tsignal_id\tslot\tseed_bar_ordinal\tcutoff_ts_ns\tslot_available\tvisible_at_slot\twindow_left\twindow_end\twindow_frontier";

/// Computes every `(signal, slot)` common-prefix row ([`SlotRow::compute`] +
/// [`SlotRow::format_prefix`]) as a tab-joined line, no header, no trailing
/// newline, in the schema's row order (signals in `seeds` order, slots `D1,
/// D2, D3`) — the `event_index.parquet` row source (design brief §D:
/// "signal → anchor bookkeeping"). Every family module recomputes this same
/// resolution against its own `nominal_end_ns` (`frame.session_end_ns` for
/// every family in this catalog); this is the one place it is published on
/// its own, decoupled from any family's value columns.
///
/// O(`seeds.len()` · log n), `n` = `frame.group_count()`.
#[must_use]
pub fn common_prefix_rows(frame: &SessionFrame, seeds: &[SignalSeed]) -> Vec<String> {
    let mut out = Vec::with_capacity(seeds.len() * Slot::ALL.len());
    for seed in seeds {
        for slot in Slot::ALL {
            let row = SlotRow::compute(frame, seed, slot, frame.session_end_ns);
            out.push(row.format_prefix(frame.day));
        }
    }
    out
}

/// Hex-encodes a 32-byte digest as 64 lowercase hex characters
/// (`label_probe_schema_v1.md` "Formatting rules"). O(1) (a fixed 32 bytes).
#[must_use]
fn hex32(digest: &[u8; 32]) -> String {
    use std::fmt::Write as _;
    digest
        .iter()
        .fold(String::with_capacity(64), |mut out, byte| {
            write!(out, "{byte:02x}").expect("writing to a String cannot fail");
            out
        })
}

/// `true`/`false`, per the schema's boolean formatting rule.
#[must_use]
const fn bool_wire(value: bool) -> &'static str {
    if value { "true" } else { "false" }
}

/// Plain decimal, or `NA` when absent (schema formatting rule).
#[must_use]
fn opt_usize_wire(value: Option<usize>) -> String {
    value.map_or_else(|| "NA".to_owned(), |v| v.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::frame::{Breaker, GroupKind};

    const BAR_NS: i64 = NANOSECONDS_PER_BAR;

    fn seed(pivot_last_bar_ordinal: u64, causal_visible_ts_ns: i64) -> SignalSeed {
        SignalSeed {
            signal_id: [0xab; 32],
            extreme_side: Side::Low,
            pivot_price_u6: 100,
            pivot_last_bar_ordinal,
            causal_visible_ts_ns,
        }
    }

    // ----------------------- Side -----------------------

    #[test]
    fn side_from_wire_parses_registered_codes_only() {
        assert_eq!(Side::from_wire("LOW"), Some(Side::Low));
        assert_eq!(Side::from_wire("HIGH"), Some(Side::High));
        assert_eq!(Side::from_wire("low"), None);
        assert_eq!(Side::from_wire(""), None);
    }

    // ------------------- cutoff availability -------------------

    #[test]
    fn slot_availability_close_truncates_at_the_early_close_bar_count() {
        // Early-close (210-bar) session clock.
        let session_end_ns = 210 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![0, session_end_ns - 1],
            vec![100, 100],
            vec![100, 100],
            vec![GroupKind::Scalar, GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(208, 0);

        // d1 cutoff = 209 bars: strictly before the 210-bar close.
        let d1 = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        assert!(d1.slot_available);
        assert_eq!(d1.cutoff_ts_ns, 209 * BAR_NS);
        assert_ne!(d1.window_frontier, WindowFrontier::DecisionUnavailable);

        // d2 cutoff = 210 bars == session_end_ns: not strictly before, so
        // close-truncated-unavailable.
        let d2 = SlotRow::compute(&frame, &s, Slot::D2, frame.session_end_ns);
        assert!(!d2.slot_available);
        assert_eq!(d2.window_frontier, WindowFrontier::DecisionUnavailable);
        assert_eq!(d2.window_left, None);
        assert_eq!(d2.window_end, None);

        // d3 cutoff = 211 bars, past the close: unavailable too.
        let d3 = SlotRow::compute(&frame, &s, Slot::D3, frame.session_end_ns);
        assert!(!d3.slot_available);
        assert_eq!(d3.window_frontier, WindowFrontier::DecisionUnavailable);
    }

    #[test]
    fn not_visible_when_causal_visible_ts_is_after_the_cutoff() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS],
            vec![100, 100],
            vec![100, 100],
            vec![GroupKind::Scalar; 2],
            Vec::new(),
        );
        // cutoff (d1) = 1 bar; visible strictly after it.
        let s = seed(0, BAR_NS + 1);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        assert!(row.slot_available);
        assert!(!row.visible_at_slot);
        assert_eq!(row.window_frontier, WindowFrontier::NotVisible);
        assert_eq!(row.window_left, None);
        assert_eq!(row.window_end, None);
    }

    // ------------------- window boundary inclusivity -------------------

    #[test]
    fn window_left_includes_a_group_exactly_at_the_cutoff() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS, 2 * BAR_NS],
            vec![100, 100, 100],
            vec![100, 100, 100],
            vec![GroupKind::Scalar; 3],
            Vec::new(),
        );
        // seed_bar_ordinal = 0, slot D1 => cutoff = BAR_NS, exactly the
        // second group's timestamp.
        let s = seed(0, 0);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        assert_eq!(row.cutoff_ts_ns, BAR_NS);
        // The group at ts == cutoff (index 1) is INCLUDED: it IS window_left.
        assert_eq!(row.window_left, Some(1));
        assert_eq!(row.window_frontier, WindowFrontier::Complete);
    }

    #[test]
    fn window_end_excludes_a_group_exactly_at_the_nominal_end() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS, 2 * BAR_NS],
            vec![100, 100, 100],
            vec![100, 100, 100],
            vec![GroupKind::Scalar; 3],
            Vec::new(),
        );
        let s = seed(0, 0);
        // nominal_end_ns == the third group's own timestamp exactly.
        let row = SlotRow::compute(&frame, &s, Slot::D1, 2 * BAR_NS);
        assert_eq!(row.window_left, Some(1));
        // window = [1, 2): the group at ts == nominal_end (index 2) is
        // excluded from the count, even though it exists.
        assert_eq!(row.window_end, Some(2));
        assert_eq!(row.window_frontier, WindowFrontier::Complete);
    }

    // ------------------------- frontier states -------------------------

    #[test]
    fn source_censored_when_the_window_is_empty() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS, 2 * BAR_NS],
            vec![100, 100, 100],
            vec![100, 100, 100],
            vec![GroupKind::Scalar; 3],
            Vec::new(),
        );
        let s = seed(0, 0);
        // nominal_end_ns == cutoff_ts_ns: the window is degenerate/empty.
        let row = SlotRow::compute(&frame, &s, Slot::D1, BAR_NS);
        assert_eq!(row.window_frontier, WindowFrontier::SourceCensored);
        assert_eq!(row.window_left, row.window_end);
    }

    #[test]
    fn wide_breaker_frontier_when_a_breaker_starts_before_the_requested_end() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS, 5 * BAR_NS],
            vec![100, 100, 100],
            vec![100, 100, 100],
            vec![GroupKind::Scalar; 3],
            vec![Breaker {
                start_ns: 2 * BAR_NS,
                end_ns: 4 * BAR_NS,
            }],
        );
        let s = seed(0, 0);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        assert_eq!(row.window_frontier, WindowFrontier::WideBreaker);
    }

    #[test]
    fn complete_when_no_censor_applies() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS, 5 * BAR_NS],
            vec![100, 100, 100],
            vec![100, 100, 100],
            vec![GroupKind::Scalar; 3],
            Vec::new(),
        );
        let s = seed(0, 0);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        assert_eq!(row.window_frontier, WindowFrontier::Complete);
        assert_eq!(row.window_left, Some(1));
        assert_eq!(row.window_end, Some(3));
    }

    // ------------------------- formatting -------------------------

    #[test]
    fn format_prefix_has_exactly_ten_tab_separated_columns() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS],
            vec![100, 100],
            vec![100, 100],
            vec![GroupKind::Scalar; 2],
            Vec::new(),
        );
        let s = seed(0, 0);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        let line = row.format_prefix("2022-01-03");
        let columns: Vec<&str> = line.split('\t').collect();
        assert_eq!(columns.len(), 10);
        assert_eq!(columns[0], "2022-01-03");
        assert_eq!(columns[1].len(), 64);
        assert_eq!(columns[2], "D1");
        assert_eq!(columns[9], "COMPLETE");
    }

    #[test]
    fn format_prefix_renders_na_for_absent_windows() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0],
            vec![100],
            vec![100],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        // visible strictly after the cutoff: NOT_VISIBLE, windows absent.
        let s = seed(0, BAR_NS + 1);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        let line = row.format_prefix("2022-01-03");
        let columns: Vec<&str> = line.split('\t').collect();
        assert_eq!(columns[7], "NA");
        assert_eq!(columns[8], "NA");
        assert_eq!(columns[9], "NOT_VISIBLE");
    }
}
