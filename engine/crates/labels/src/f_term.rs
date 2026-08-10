//! F-TERM — terminal-moves family (signed move from the anchor to the last
//! scientific group at-or-before each horizon boundary: 15/30/60/120 minutes
//! and close). Design authority: `docs/specs/label_kernel_design_v1.md`
//! §"Families (EVENTS.2 wave)" ("F-TERM — terminal moves") and
//! `docs/specs/label_probe_schema_v1.md` §"`f_term.tsv` (family F-TERM)".
//!
//! This family's own common prefix uses the CLOSE-horizon window (its
//! `nominal_end_ns` is `frame.session_end_ns`, exactly like F-EXT's), per
//! `label_probe_schema_v1.md` "Family-file common prefix". Each of the five
//! horizons then re-derives its OWN nominal end from the row's `cutoff_ts_ns`
//! and locates its own terminal group independently.

use crate::anchor::{Side, SignalSeed, Slot, SlotRow};
use crate::frame::SessionFrame;
use std::fs::File;
use std::io::{self, BufWriter, Write};
use std::path::Path;

/// Registered one-minute bar duration in nanoseconds (CONV §3), used to turn
/// a horizon's whole-minute offset into a nanosecond `nominal_end_ns`.
const NANOSECONDS_PER_BAR: i64 = 60_000_000_000;

/// The five registered F-TERM horizons, in the schema's column order
/// (`docs/specs/label_probe_schema_v1.md` "`f_term.tsv`").
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Horizon {
    M15,
    M30,
    M60,
    M120,
    Close,
}

impl Horizon {
    const ALL: [Self; 5] = [Self::M15, Self::M30, Self::M60, Self::M120, Self::Close];

    /// Whole-minute offset from the slot's own cutoff; `None` for `CLOSE`,
    /// whose nominal end is the session's official close directly.
    const fn minutes(self) -> Option<i64> {
        match self {
            Self::M15 => Some(15),
            Self::M30 => Some(30),
            Self::M60 => Some(60),
            Self::M120 => Some(120),
            Self::Close => None,
        }
    }

    /// The wire label used in the `term_<H>_*` column names.
    const fn wire(self) -> &'static str {
        match self {
            Self::M15 => "15M",
            Self::M30 => "30M",
            Self::M60 => "60M",
            Self::M120 => "120M",
            Self::Close => "CLOSE",
        }
    }

    /// `nominal_end_ns` for this horizon (`label_probe_schema_v1.md`
    /// "`f_term.tsv`"): `cutoff_ts_ns + H` for the four timed horizons, or the
    /// session's own official close for `CLOSE`.
    ///
    /// # Panics
    ///
    /// Panics if the offset arithmetic overflows `i64` — unreachable for any
    /// registered session (cutoffs are bounded by the session clock, at most
    /// a few hundred one-minute bars).
    fn nominal_end_ns(self, cutoff_ts_ns: i64, session_end_ns: i64) -> i64 {
        match self.minutes() {
            None => session_end_ns,
            Some(minutes) => minutes
                .checked_mul(NANOSECONDS_PER_BAR)
                .and_then(|offset| cutoff_ts_ns.checked_add(offset))
                .expect("horizon offset arithmetic overflowed i64"),
        }
    }
}

/// The ten-column common prefix shared by every family file
/// (`docs/specs/label_probe_schema_v1.md` "Family-file common prefix"),
/// matching [`SlotRow::format_prefix`]'s own column order exactly.
const PREFIX_HEADER: &str = "day\tsignal_id\tslot\tseed_bar_ordinal\tcutoff_ts_ns\tslot_available\tvisible_at_slot\twindow_left\twindow_end\twindow_frontier";

/// Builds the full `f_term.tsv` header: the common prefix plus six value
/// columns per horizon (`price_lo_u6 price_hi_u6 move_lo_u6 move_hi_u6
/// group_kind state`) for each of the five horizons in schema order —
/// derived from [`Horizon::ALL`]/[`Horizon::wire`] rather than hand-
/// duplicated, so the header can never drift from the horizon list itself.
#[must_use]
pub fn header() -> String {
    use std::fmt::Write as _;

    let mut out = PREFIX_HEADER.to_owned();
    for horizon in Horizon::ALL {
        let h = horizon.wire();
        write!(
            out,
            "\tterm_{h}_price_lo_u6\tterm_{h}_price_hi_u6\tterm_{h}_move_lo_u6\tterm_{h}_move_hi_u6\tterm_{h}_group_kind\tterm_{h}_state"
        )
        .expect("writing to a String cannot fail");
    }
    out
}

/// The six-column all-`NA` placeholder for one horizon on a row whose common
/// prefix is `DECISION_UNAVAILABLE`/`NOT_VISIBLE` — every column, including
/// `state`, is `NA` there (`label_probe_schema_v1.md` "Family-file common
/// prefix"). Distinct from a per-horizon `SOURCE_CENSORED`, whose `state`
/// column IS populated (schema "`f_term.tsv`": "group columns NA when
/// `SOURCE_CENSORED`").
const NA_ROW_HORIZON: &str = "NA\tNA\tNA\tNA\tNA\tNA";

/// The shared per-row inputs to [`format_horizon`], factored out of a long
/// argument list so every horizon reuses the one
/// [`SessionFrame::first_breaker_start_after`] descent computed once by
/// [`format_values`].
struct HorizonContext {
    side: Side,
    pivot_price_u6: i64,
    cutoff_ts_ns: i64,
    window_left: usize,
    breaker_start: Option<i64>,
}

/// Computes and formats one horizon's six value columns (`price_lo_u6
/// price_hi_u6 move_lo_u6 move_hi_u6 group_kind state`).
///
/// Algorithm (`label_kernel_design_v1.md` "F-TERM — terminal moves",
/// `label_probe_schema_v1.md` "`f_term.tsv`"): the terminal group is the LAST
/// scientific group with `ts_ns < min(nominal_end_ns, session_end_ns,
/// first_breaker_start_after(cutoff))` and index ≥ `window_left`; if none
/// exists the state is `SOURCE_CENSORED` (group columns `NA`). Otherwise the
/// state is `WIDE_BREAKER` if a breaker starts strictly after the cutoff and
/// before the requested end, `CLOSE_TRUNCATED` if the nominal end exceeds the
/// official close, else `ATTAINED` (CONV §6b `FrontierKind` trigger order,
/// mirrored exactly).
///
/// Cost: O(log n) — one [`SessionFrame::end_position`] descent (the
/// `first_breaker_start_after` descent is shared across all five horizons by
/// the caller), `n` = `frame.group_count()`. No per-anchor scan.
fn format_horizon(frame: &SessionFrame, ctx: &HorizonContext, horizon: Horizon) -> String {
    let nominal_end_ns = horizon.nominal_end_ns(ctx.cutoff_ts_ns, frame.session_end_ns);
    let requested_end_ns = nominal_end_ns.min(frame.session_end_ns);
    let bound = ctx
        .breaker_start
        .map_or(requested_end_ns, |start| start.min(requested_end_ns));
    let terminal_end_position = frame.end_position(bound);

    if terminal_end_position <= ctx.window_left {
        return "NA\tNA\tNA\tNA\tNA\tSOURCE_CENSORED".to_owned();
    }

    let terminal_index = terminal_end_position - 1;
    let price_lo = frame.m_lo[terminal_index];
    let price_hi = frame.m_hi[terminal_index];
    let (move_lo, move_hi) = match ctx.side {
        Side::Low => (price_lo - ctx.pivot_price_u6, price_hi - ctx.pivot_price_u6),
        Side::High => (ctx.pivot_price_u6 - price_hi, ctx.pivot_price_u6 - price_lo),
    };
    let state = if ctx
        .breaker_start
        .is_some_and(|start| start < requested_end_ns)
    {
        "WIDE_BREAKER"
    } else if nominal_end_ns > frame.session_end_ns {
        "CLOSE_TRUNCATED"
    } else {
        "ATTAINED"
    };

    format!(
        "{price_lo}\t{price_hi}\t{move_lo}\t{move_hi}\t{}\t{state}",
        frame.kind[terminal_index].wire()
    )
}

/// Computes and formats all thirty F-TERM value columns (six per horizon,
/// five horizons) for one `(signal, slot)` row, given its already-computed
/// (CLOSE-horizon) common prefix.
///
/// Cost: O(log n) — one shared [`SessionFrame::first_breaker_start_after`]
/// descent plus five independent [`format_horizon`] calls, `n` =
/// `frame.group_count()`.
fn format_values(frame: &SessionFrame, seed: &SignalSeed, prefix: &SlotRow) -> String {
    let Some(window_left) = prefix.window_left else {
        return Horizon::ALL.map(|_| NA_ROW_HORIZON).join("\t");
    };
    let ctx = HorizonContext {
        side: seed.extreme_side,
        pivot_price_u6: seed.pivot_price_u6,
        cutoff_ts_ns: prefix.cutoff_ts_ns,
        window_left,
        breaker_start: frame.first_breaker_start_after(prefix.cutoff_ts_ns),
    };
    Horizon::ALL
        .into_iter()
        .map(|horizon| format_horizon(frame, &ctx, horizon))
        .collect::<Vec<_>>()
        .join("\t")
}

/// Computes every `(signal, slot)` row as one tab-joined line, no header,
/// no trailing newline, in the schema's row order: signals in `seeds` order,
/// slots `D1, D2, D3` (`docs/specs/label_probe_schema_v1.md` "Family-file
/// common prefix"). Reusable in-memory (e.g. for parquet publication)
/// without going through [`write_tsv`]'s file.
///
/// For F-TERM the common prefix is computed against the CLOSE-horizon window
/// (`nominal_end_ns = frame.session_end_ns`, schema "Family-file common
/// prefix"); each horizon's own nominal end is re-derived independently in
/// [`format_values`].
///
/// O(`seeds.len()` · log n): one [`SlotRow::compute`] descent plus the five
/// O(log n) horizon computations above per row, `n` = `frame.group_count()`.
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

/// Writes `f_term.tsv` for every `(signal, slot)` row ([`rows`]).
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
    use crate::frame::GroupKind;

    const BAR_NS: i64 = 60_000_000_000;

    fn seed(
        side: Side,
        pivot_price_u6: i64,
        pivot_last_bar_ordinal: u64,
        causal_visible_ts_ns: i64,
    ) -> SignalSeed {
        SignalSeed {
            signal_id: [0x22; 32],
            extreme_side: side,
            pivot_price_u6,
            pivot_last_bar_ordinal,
            causal_visible_ts_ns,
        }
    }

    // ------------- direct format_horizon tests (algorithm-level) -------------

    #[test]
    fn terminal_group_is_the_very_first_window_group() {
        // Only g1 (ts = 1 bar) sits in [window_left, horizon bound); g0 is
        // before the window, g2 is far past the horizon.
        let frame = SessionFrame::from_parts_for_test(
            0,
            25 * BAR_NS,
            vec![0, BAR_NS, 20 * BAR_NS],
            vec![999, 90, 999],
            vec![999, 110, 999],
            vec![GroupKind::Scalar; 3],
            Vec::new(),
        );
        let ctx = HorizonContext {
            side: Side::Low,
            pivot_price_u6: 100,
            cutoff_ts_ns: BAR_NS,
            window_left: 1,
            breaker_start: None,
        };
        // nominal_end = cutoff + 15 bars = 16 bars; bound = min(16B, 25B) =
        // 16B; terminal group = last group with ts < 16B => g1 itself.
        let out = format_horizon(&frame, &ctx, Horizon::M15);
        assert_eq!(out, "90\t110\t-10\t10\tSCALAR\tATTAINED");
    }

    #[test]
    fn horizon_past_the_close_is_close_truncated_while_close_itself_is_attained() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            100 * BAR_NS,
            vec![95 * BAR_NS, 98 * BAR_NS],
            vec![999, 130],
            vec![999, 140],
            vec![GroupKind::Scalar; 2],
            Vec::new(),
        );
        let ctx = HorizonContext {
            side: Side::Low,
            pivot_price_u6: 100,
            cutoff_ts_ns: 90 * BAR_NS,
            window_left: 0,
            breaker_start: None,
        };
        // 120M: nominal_end = 90+120 = 210 bars, way past the 100-bar
        // close => bound clamps to the close (100 bars); terminal = g1.
        let m120 = format_horizon(&frame, &ctx, Horizon::M120);
        assert_eq!(m120, "130\t140\t30\t40\tSCALAR\tCLOSE_TRUNCATED");

        // CLOSE: nominal_end == session_end_ns exactly (not strictly past
        // it): the identical terminal group is ATTAINED, not truncated.
        let close = format_horizon(&frame, &ctx, Horizon::Close);
        assert_eq!(close, "130\t140\t30\t40\tSCALAR\tATTAINED");
    }

    #[test]
    fn short_horizon_source_censored_while_close_horizon_attains() {
        // The only group in the frame arrives after the 15-minute horizon
        // boundary but well before the close.
        let frame = SessionFrame::from_parts_for_test(
            0,
            100 * BAR_NS,
            vec![20 * BAR_NS],
            vec![120],
            vec![150],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let ctx = HorizonContext {
            side: Side::Low,
            pivot_price_u6: 100,
            cutoff_ts_ns: 0,
            window_left: 0,
            breaker_start: None,
        };
        let m15 = format_horizon(&frame, &ctx, Horizon::M15);
        assert_eq!(m15, "NA\tNA\tNA\tNA\tNA\tSOURCE_CENSORED");

        let close = format_horizon(&frame, &ctx, Horizon::Close);
        assert_eq!(close, "120\t150\t20\t50\tSCALAR\tATTAINED");
    }

    #[test]
    fn breaker_censors_the_close_horizon_but_not_a_shorter_one() {
        // Breaker starts at 30 bars: it falls after the 15M horizon's own
        // boundary (15 bars) but before the CLOSE horizon's (100 bars), so
        // it censors CLOSE only.
        let frame = SessionFrame::from_parts_for_test(
            0,
            100 * BAR_NS,
            vec![10 * BAR_NS, 50 * BAR_NS],
            vec![90, 999],
            vec![120, 999],
            vec![GroupKind::Scalar; 2],
            Vec::new(),
        );
        let ctx = HorizonContext {
            side: Side::Low,
            pivot_price_u6: 100,
            cutoff_ts_ns: 0,
            window_left: 0,
            breaker_start: Some(30 * BAR_NS),
        };
        let m15 = format_horizon(&frame, &ctx, Horizon::M15);
        assert_eq!(m15, "90\t120\t-10\t20\tSCALAR\tATTAINED");

        let close = format_horizon(&frame, &ctx, Horizon::Close);
        assert_eq!(close, "90\t120\t-10\t20\tSCALAR\tWIDE_BREAKER");
    }

    #[test]
    fn heterogeneous_terminal_group_reports_heterogeneous_kind() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            100 * BAR_NS,
            vec![10 * BAR_NS],
            vec![90],
            vec![110],
            vec![GroupKind::Heterogeneous],
            Vec::new(),
        );
        let ctx = HorizonContext {
            side: Side::Low,
            pivot_price_u6: 100,
            cutoff_ts_ns: 0,
            window_left: 0,
            breaker_start: None,
        };
        let out = format_horizon(&frame, &ctx, Horizon::Close);
        let columns: Vec<&str> = out.split('\t').collect();
        assert_eq!(columns[4], "HETEROGENEOUS");
        assert_eq!(columns[5], "ATTAINED");
    }

    // ------------------- row-level (format_values) tests -------------------

    #[test]
    fn window_empty_yields_source_censored_for_every_horizon() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS],
            vec![100, 100],
            vec![100, 100],
            vec![GroupKind::Scalar; 2],
            Vec::new(),
        );
        // D1 cutoff = 2 bars: both groups sit before it, and none exist
        // between it and the close.
        let s = seed(Side::Low, 100, 1, 0);
        let prefix = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        assert_eq!(prefix.window_left, prefix.window_end);
        let values = format_values(&frame, &s, &prefix);
        let expected = Horizon::ALL
            .map(|_| "NA\tNA\tNA\tNA\tNA\tSOURCE_CENSORED")
            .join("\t");
        assert_eq!(values, expected);
    }

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
        let s = seed(Side::Low, 100, 0, 0); // D2 cutoff == session_end_ns.
        let prefix = SlotRow::compute(&frame, &s, Slot::D2, frame.session_end_ns);
        let values = format_values(&frame, &s, &prefix);
        let expected = Horizon::ALL.map(|_| NA_ROW_HORIZON).join("\t");
        assert_eq!(values, expected);
    }

    #[test]
    fn not_visible_at_d1_but_visible_at_d2_with_all_horizons_close_truncated_except_close() {
        // session_end_ns is only 3 bars past D2's cutoff, so every timed
        // horizon (15/30/60/120 min) is truncated to the close, and all
        // five horizons resolve to the SAME terminal group.
        let frame = SessionFrame::from_parts_for_test(
            0,
            5 * BAR_NS,
            vec![0, 2 * BAR_NS, 4 * BAR_NS],
            vec![999, 120, 250],
            vec![999, 140, 300],
            vec![GroupKind::Scalar; 3],
            Vec::new(),
        );
        let s = seed(Side::Low, 100, 0, BAR_NS + 1);

        let d1_prefix = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        assert_eq!(
            format_values(&frame, &s, &d1_prefix),
            Horizon::ALL.map(|_| NA_ROW_HORIZON).join("\t")
        );

        let d2_prefix = SlotRow::compute(&frame, &s, Slot::D2, frame.session_end_ns);
        assert_eq!(d2_prefix.window_left, Some(1));
        let d2_values = format_values(&frame, &s, &d2_prefix);
        // Terminal group for every horizon = index 2 (ts = 4 bars): price
        // 250/300, move -100+? => move_lo=250-100=150, move_hi=300-100=200.
        let truncated = "250\t300\t150\t200\tSCALAR\tCLOSE_TRUNCATED";
        let attained = "250\t300\t150\t200\tSCALAR\tATTAINED";
        let expected = [truncated, truncated, truncated, truncated, attained].join("\t");
        assert_eq!(d2_values, expected);
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
            std::env::temp_dir().join(format!("f_term_write_tsv_test_{}.tsv", std::process::id()));
        write_tsv(&frame, &seeds, &out_path).expect("writes f_term.tsv");
        let content = std::fs::read_to_string(&out_path).expect("f_term.tsv exists");
        std::fs::remove_file(&out_path).ok();

        let expected_header = header();
        let mut lines = content.lines();
        assert_eq!(lines.next(), Some(expected_header.as_str()));
        let d1 = lines.next().expect("D1 row");
        let d2 = lines.next().expect("D2 row");
        let d3 = lines.next().expect("D3 row");
        assert_eq!(lines.next(), None);

        assert!(d1.contains("\tD1\t"));
        assert!(d2.contains("\tD2\t"));
        assert!(d3.contains("\tD3\t"));
        // 10 prefix + 30 value columns = 40.
        assert_eq!(d1.split('\t').count(), 40);
        assert_eq!(expected_header.split('\t').count(), 40);
    }
}
