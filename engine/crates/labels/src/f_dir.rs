//! F-DIR — direction / reversal / confirmation-persistence / false-break /
//! reclaim state machine. Design authority: `docs/specs/events3_design_v1.md`
//! §A "F-DIR" and `docs/specs/events3_design_amendment_v2.md` §A7 (F7)
//! "F-DIR exact state machine", VERBATIM, applied in the amendment's own
//! stated precedence order (`CONTINUATION` beats `REVERSAL` beats
//! `FALSE_BREAK` beats `RECLAIM` beats `CONFIRM_PERSIST`). Schema:
//! `docs/specs/family_schemas/f_dir_schema_v1.md` (full state-derivation
//! rationale, including the typed completions beyond the five named states,
//! is documented there — this module implements it).
//!
//! Every trigger is an exact function of already-registered F-PASS/F-DWELL
//! quantities, recomputed here directly from the shared [`SessionFrame`] /
//! [`crate::extrema::ExtremaTree`] primitives: the `N*`-scale touches reuse
//! [`crate::f_pass::passage_at_threshold`] **verbatim** (the same "shared
//! primitive, no new scans" reuse `crate::f_ord` already does); the
//! break/reclaim-count and final-bar-sign quantities are recomputed by a
//! small, self-contained bar-clock sweep below — `crate::f_dwell` is itself
//! an EVENTS.3 placeholder in this same wave (not yet implemented by its own
//! agent), so this module cannot and does not depend on it, per the task's
//! own instruction to recompute from shared primitives rather than parse
//! another family's output.
//!
//! ## Input gap (escalation — recorded in the task report)
//!
//! [`SignalSeed`] (`crate::anchor`) does not carry `reversal_bps`, required
//! to resolve `N*`, and this family's edit scope excludes `anchor.rs`.
//! [`DirSeed`] extends [`SignalSeed`] locally, the same pattern
//! `crate::f_rank::RankSeed` uses.

use crate::anchor::{Side, SignalSeed, Slot, SlotRow, WindowFrontier};
use crate::f_pass::{self, TouchState};
use crate::frame::{GroupKind, SessionFrame};
use std::fmt::Write as _;
use std::fs::File;
use std::io::{self, BufWriter, Write as _};
use std::path::Path;

/// One 1-minute bar's duration in nanoseconds (CONV §3).
const BAR_NS: i64 = 60_000_000_000;

/// [`SignalSeed`] plus the one extra `event_signals.tsv` column this family
/// needs: `reversal_bps` (registered header column index 6, 0-based).
#[derive(Clone, Copy, Debug)]
pub struct DirSeed {
    pub seed: SignalSeed,
    pub reversal_bps: u64,
}

/// Parses a day's verbatim `event_signals.tsv` line slice into [`DirSeed`]s:
/// reuses [`crate::probe::parse_seeds`] for the five columns every family
/// needs, then reads `reversal_bps` by fixed index off the same lines.
///
/// # Panics
///
/// Panics under the same conditions as [`crate::probe::parse_seeds`], plus if
/// `reversal_bps` (column 6) fails to parse as a `u64`.
#[must_use]
pub fn parse_dir_seeds(seeds_raw_lines: &[String]) -> Vec<DirSeed> {
    let base = crate::probe::parse_seeds(seeds_raw_lines);
    seeds_raw_lines
        .iter()
        .zip(base)
        .map(|(line, seed)| {
            let columns: Vec<&str> = line.split('\t').collect();
            let reversal_bps_raw = columns[6];
            DirSeed {
                seed,
                reversal_bps: reversal_bps_raw
                    .parse()
                    .unwrap_or_else(|_| panic!("reversal_bps is not a u64: {reversal_bps_raw}")),
            }
        })
        .collect()
}

/// `dir_state` (`docs/specs/family_schemas/f_dir_schema_v1.md`): the
/// amendment's five named states plus the typed completions the schema doc
/// documents (`NEITHER_*` mirrors `crate::f_ord::OrdState`'s own precedent
/// exactly; `INCONCLUSIVE`/`OUT_OF_DOMAIN`/`NO_LADDER_RUNG`/`NA` are the
/// forced, non-arbitrary completions needed for a total function).
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum DirState {
    Continuation,
    Reversal,
    FalseBreak,
    Reclaim,
    ConfirmPersist,
    Inconclusive,
    NeitherComplete,
    NeitherWideBreaker,
    NeitherCloseTruncated,
    NeitherSourceCensored,
    OutOfDomain,
    NoLadderRung,
    Na,
}

impl DirState {
    /// The wire string for `dir_state`.
    #[must_use]
    pub const fn wire(self) -> &'static str {
        match self {
            Self::Continuation => "CONTINUATION",
            Self::Reversal => "REVERSAL",
            Self::FalseBreak => "FALSE_BREAK",
            Self::Reclaim => "RECLAIM",
            Self::ConfirmPersist => "CONFIRM_PERSIST",
            Self::Inconclusive => "INCONCLUSIVE",
            Self::NeitherComplete => "NEITHER_COMPLETE",
            Self::NeitherWideBreaker => "NEITHER_WIDE_BREAKER",
            Self::NeitherCloseTruncated => "NEITHER_CLOSE_TRUNCATED",
            Self::NeitherSourceCensored => "NEITHER_SOURCE_CENSORED",
            Self::OutOfDomain => "OUT_OF_DOMAIN",
            Self::NoLadderRung => "NO_LADDER_RUNG",
            Self::Na => "NA",
        }
    }
}

/// `N*` = the nearest (smallest) ladder rung `>= reversal_bps`
/// (`events3_design_amendment_v2.md` §A7); `None` when `reversal_bps > 240`
/// (no rung qualifies — [`DirState::NoLadderRung`]). O(1) (fixed
/// eleven-entry ladder, already ascending).
#[must_use]
pub fn nearest_rung_at_least(reversal_bps: u64) -> Option<u16> {
    f_pass::LADDER_BPS
        .into_iter()
        .find(|&n| u64::from(n) >= reversal_bps)
}

/// One valid bar's ternary sign of `dir·(close_u6 − P)`
/// (`events3_formula_addendum_v1.md` §4 `above_ns`/`below_ns` convention).
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum BarSign {
    Favorable,
    At,
    Adverse,
}

/// A Scalar representative group's own scalar "close" price is `m_lo`
/// (`== m_hi` for a Scalar group by construction, `f_dwell` schema's "Bar
/// walk" law, `events3_design_amendment_v2.md` ruling E17) — never a
/// midpoint; the midpoint is reserved for magnitude-robust consumers only
/// (E7). Callers must not invoke this for a `Heterogeneous` group. O(1).
fn bar_sign(frame: &SessionFrame, side: Side, pivot_price_u6: i64, group_index: usize) -> BarSign {
    let close = frame.m_lo[group_index];
    debug_assert_eq!(
        close, frame.m_hi[group_index],
        "a Scalar group's m_lo must equal its m_hi"
    );
    let raw = close - pivot_price_u6;
    let signed = match side {
        Side::Low => raw,
        Side::High => -raw,
    };
    match signed.cmp(&0) {
        std::cmp::Ordering::Greater => BarSign::Favorable,
        std::cmp::Ordering::Less => BarSign::Adverse,
        std::cmp::Ordering::Equal => BarSign::At,
    }
}

/// Resolves one bar's representative sign under F-DWELL's exclusion law
/// (`docs/specs/family_schemas/f_dwell_schema_v1.md` "Bar walk", ruling E17):
/// `None` — excluded from the sign sequence, i.e. the bar neither breaks nor
/// extends a run, exactly like F-DWELL's `NO_QUOTE`/`AMBIGUOUS_CLOSE` bars —
/// when there is no candidate group, when the candidate group's index is
/// `< window_left` (the representative would predate the window's own left
/// edge: no pre-window carry-forward), or when the candidate group's kind is
/// `Heterogeneous` (kind-based ambiguity, mirroring `f_pass.tsv`'s
/// `Scalar -> EXACT` / `Heterogeneous -> INTERVAL_AMBIGUOUS` precedent —
/// never resolved to a fabricated single price). Only a genuine Scalar
/// representative at/after `window_left` yields `Some` sign. O(1).
fn representative_bar_sign(
    frame: &SessionFrame,
    side: Side,
    pivot_price_u6: i64,
    group_index: Option<usize>,
    window_left: usize,
) -> Option<BarSign> {
    let g = group_index?;
    if g < window_left {
        return None;
    }
    if frame.kind[g] == GroupKind::Heterogeneous {
        return None;
    }
    Some(bar_sign(frame, side, pivot_price_u6, g))
}

/// Session-wide, bar-indexed representative-group lookup: `out[b]` = index of
/// the last scientific-path group with `ts_ns < bar_end(b)` (the session-
/// wide, UNCLAMPED form of F-DWELL's representative-close rule,
/// `events3_design_amendment_v2.md` §A5), or `None` (`NO_QUOTE`) if no such
/// group exists. Built ONCE per session by a single forward sweep
/// (`bar_end(b)` is nondecreasing in `b`, `frame.ts_ns` is sorted ascending)
/// — O(bar count + `frame.group_count()`), never re-scanned per anchor.
/// Callers reclip the final in-window bar against their own `window_end_ns`
/// themselves (see [`bar_break_reclaim_and_final_sign`]); every other bar's
/// `bar_end(b) <= window_end_ns` always holds for a well-formed window, so
/// this table's unclamped value is already correct for them.
///
/// The bar count is derived from `(session_end_ns - session_start_ns) /
/// BAR_NS` rather than `frame.expected_bar_count` — exactly equal for any
/// registered session (CONV §3: `expected_bar_count` is defined as that same
/// quotient), and robust for synthetic/unit-test frames built via
/// `SessionFrame::from_parts_for_test`, which does not set
/// `expected_bar_count` at all.
fn session_bar_last_group(frame: &SessionFrame) -> Vec<Option<usize>> {
    let bar_count = (frame.session_end_ns - frame.session_start_ns) / BAR_NS;
    let bar_count = usize::try_from(bar_count).expect("session bar count fits in usize");
    let mut out = Vec::with_capacity(bar_count);
    let mut pos = 0usize;
    for b in 0..bar_count {
        let b_i64 = i64::try_from(b).expect("bar ordinal fits in i64");
        let bar_end = frame.session_start_ns + (b_i64 + 1) * BAR_NS;
        while pos < frame.group_count() && frame.ts_ns[pos] < bar_end {
            pos += 1;
        }
        out.push(if pos > 0 { Some(pos - 1) } else { None });
    }
    out
}

/// The window's observed end timestamp, re-derived from public
/// [`SessionFrame`] methods exactly as [`SlotRow::compute`] derives it
/// internally for the CLOSE-bounded nominal end this family uses (like
/// F-PASS/F-ORD): `min(session_end_ns, first_breaker_start_after(cutoff))`.
/// O(log n).
fn observed_window_end_ns(frame: &SessionFrame, cutoff_ts_ns: i64) -> i64 {
    frame
        .first_breaker_start_after(cutoff_ts_ns)
        .map_or(frame.session_end_ns, |start| {
            start.min(frame.session_end_ns)
        })
}

/// F-DWELL's `break_reclaim_count` (sign changes of `dir·(close_u6[bar] −
/// P)` across consecutive valid bars — `NO_QUOTE`/`AMBIGUOUS_CLOSE`/
/// pre-`window_left` bars excluded, per [`representative_bar_sign`]) plus the
/// final valid bar's sign, over one anchor's own window `[cutoff_ts_ns,
/// window_end_ns)` on the one-minute bar clock. The final-sign half of the
/// pair is `None` whenever every bar in range is excluded — genuinely
/// reachable under the E17 exclusion law even when the caller already knows
/// at least one `N*` side touched (the touching group can itself be the sole
/// group of an otherwise-all-excluded window, e.g. a single Heterogeneous
/// representative bar): callers must NOT treat that as "no answer" and must
/// still consult `dir_state_at`'s `RECLAIM` test on the raw touch indices,
/// exactly as the oracle's `_walk_bars_fast`/`dir_state_and_n_star` do
/// (`break_reclaim_count = 0`, `final_sign = None` is a normal, total
/// result, never a sentinel for "caller must special-case this").
///
/// O(bars in the anchor's own window) — a small, bounded loop (at most
/// `expected_bar_count`, a few hundred), reusing the whole-session
/// `session_bar_last_group` table for every bar except the final (possibly
/// partial) one, which is reclipped via one fresh
/// [`SessionFrame::end_position`] call (O(log n)). Never an
/// `O(group_count)` scan per anchor.
fn bar_break_reclaim_and_final_sign(
    frame: &SessionFrame,
    side: Side,
    pivot_price_u6: i64,
    cutoff_bar: i64,
    window_end_ns: i64,
    window_left: usize,
    session_bar_last_group: &[Option<usize>],
) -> (u64, Option<BarSign>) {
    let last_bar = (window_end_ns - 1 - frame.session_start_ns).div_euclid(BAR_NS);
    if last_bar < cutoff_bar {
        return (0, None);
    }

    let mut break_reclaim_count = 0u64;
    let mut previous_sign: Option<BarSign> = None;
    let mut final_sign: Option<BarSign> = None;

    let mut b = cutoff_bar;
    while b <= last_bar {
        let group_index = if b == last_bar {
            frame.end_position(window_end_ns).checked_sub(1)
        } else {
            let idx = usize::try_from(b).expect("bar ordinal fits in usize");
            session_bar_last_group.get(idx).copied().flatten()
        };
        if let Some(sign) =
            representative_bar_sign(frame, side, pivot_price_u6, group_index, window_left)
        {
            if previous_sign.is_some_and(|prev| prev != sign) {
                break_reclaim_count += 1;
            }
            previous_sign = Some(sign);
            final_sign = Some(sign);
        }
        b += 1;
    }
    (break_reclaim_count, final_sign)
}

/// Derives one anchor's `(dir_n_star_bps, dir_state)` pair
/// (`docs/specs/family_schemas/f_dir_schema_v1.md`), applying the amendment's
/// precedence order (`CONTINUATION` beats `REVERSAL` beats `FALSE_BREAK`
/// beats `RECLAIM` beats `CONFIRM_PERSIST`; checked in exactly that order —
/// the first matching predicate wins).
///
/// O(log n) when neither `N*` side touches or exactly one does; O(bars in
/// the window) when both touch (the bar-clock consult).
///
/// # Panics
///
/// Never in practice: the one internal `expect` guards a division by the
/// `BAR_NS` constant, which is never zero.
#[must_use]
pub fn dir_state_at(
    frame: &SessionFrame,
    seed: &SignalSeed,
    reversal_bps: u64,
    row: &SlotRow,
    session_bar_last_group: &[Option<usize>],
) -> (Option<u16>, DirState) {
    let (Some(window_left), Some(window_end)) = (row.window_left, row.window_end) else {
        return (None, DirState::Na);
    };
    let Some(n_star) = nearest_rung_at_least(reversal_bps) else {
        return (None, DirState::NoLadderRung);
    };

    let result = f_pass::passage_at_threshold(
        frame,
        seed.extreme_side,
        seed.pivot_price_u6,
        n_star,
        window_left,
        window_end,
    );
    if result.fav.state == TouchState::OutOfDomain || result.adv.state == TouchState::OutOfDomain {
        return (Some(n_star), DirState::OutOfDomain);
    }

    let fav_touched = matches!(
        result.fav.state,
        TouchState::Exact | TouchState::IntervalAmbiguous
    );
    let adv_touched = matches!(
        result.adv.state,
        TouchState::Exact | TouchState::IntervalAmbiguous
    );

    if fav_touched && !adv_touched {
        return (Some(n_star), DirState::Continuation);
    }
    if adv_touched && !fav_touched {
        return (Some(n_star), DirState::Reversal);
    }
    if !fav_touched && !adv_touched {
        let state = match row.window_frontier {
            WindowFrontier::Complete => DirState::NeitherComplete,
            WindowFrontier::WideBreaker => DirState::NeitherWideBreaker,
            WindowFrontier::SourceCensored => DirState::NeitherSourceCensored,
            WindowFrontier::OfficialCloseTruncated => DirState::NeitherCloseTruncated,
            WindowFrontier::DecisionUnavailable | WindowFrontier::NotVisible => DirState::Na,
        };
        return (Some(n_star), state);
    }

    // Both touched: consult the bar clock. `final_sign` is `None` whenever
    // every bar in range is excluded (E17) — a normal outcome, NOT a reason
    // to skip the RECLAIM test below (which depends only on the raw touch
    // indices, not on the bar walk), exactly matching the oracle's
    // unconditional FALSE_BREAK > RECLAIM > CONFIRM_PERSIST > INCONCLUSIVE
    // precedence (`f_dir.py::dir_state_and_n_star`).
    let cutoff_bar = (row.cutoff_ts_ns - frame.session_start_ns)
        .checked_div(BAR_NS)
        .expect("BAR_NS is nonzero");
    let window_end_ns = observed_window_end_ns(frame, row.cutoff_ts_ns);
    let (break_reclaim_count, final_sign) = bar_break_reclaim_and_final_sign(
        frame,
        seed.extreme_side,
        seed.pivot_price_u6,
        cutoff_bar,
        window_end_ns,
        window_left,
        session_bar_last_group,
    );

    if break_reclaim_count >= 2 && final_sign == Some(BarSign::Adverse) {
        return (Some(n_star), DirState::FalseBreak);
    }
    let adv_index = result
        .adv
        .index
        .expect("adv touched (Exact/IntervalAmbiguous) always carries an index");
    let fav_index = result
        .fav
        .index
        .expect("fav touched (Exact/IntervalAmbiguous) always carries an index");
    if adv_index < fav_index {
        return (Some(n_star), DirState::Reclaim);
    }
    if final_sign == Some(BarSign::Favorable) {
        return (Some(n_star), DirState::ConfirmPersist);
    }
    (Some(n_star), DirState::Inconclusive)
}

/// The `f_dir.tsv` header: the ten-column common prefix followed by
/// `dir_n_star_bps`, `dir_state` (`docs/specs/family_schemas/
/// f_dir_schema_v1.md`).
#[must_use]
pub fn header() -> String {
    "day\tsignal_id\tslot\tseed_bar_ordinal\tcutoff_ts_ns\tslot_available\t\
     visible_at_slot\twindow_left\twindow_end\twindow_frontier\t\
     dir_n_star_bps\tdir_state"
        .to_owned()
}

/// Computes every `(signal, slot)` row as one tab-joined line, no header, no
/// trailing newline: one row per `(signal, slot)`, slots in order `D1, D2,
/// D3` (slot-minor), signals in the order given by `seeds`. Reusable
/// in-memory (e.g. for parquet publication) without going through
/// [`write_tsv`]'s file.
///
/// O(`seeds.len()` × 3 slots × (log n or bars-in-window)) plus one
/// O(`expected_bar_count` + `frame.group_count()`) session-wide sweep.
///
/// # Panics
///
/// Never in practice: the internal `expect` guards a `write!` onto an
/// in-memory `String`, which cannot fail.
#[must_use]
pub fn rows(frame: &SessionFrame, seeds: &[DirSeed]) -> Vec<String> {
    let bar_table = session_bar_last_group(frame);
    let mut out = Vec::with_capacity(seeds.len() * Slot::ALL.len());
    for dir_seed in seeds {
        for slot in Slot::ALL {
            let row = SlotRow::compute(frame, &dir_seed.seed, slot, frame.session_end_ns);
            let mut line = row.format_prefix(frame.day);
            let (n_star, state) = dir_state_at(
                frame,
                &dir_seed.seed,
                dir_seed.reversal_bps,
                &row,
                &bar_table,
            );
            match n_star {
                Some(n) => write!(line, "\t{n}\t{}", state.wire()),
                None => write!(line, "\tNA\t{}", state.wire()),
            }
            .expect("writing to a String cannot fail");
            out.push(line);
        }
    }
    out
}

/// Writes `f_dir.tsv` for every `(signal, slot)` row ([`rows`]).
///
/// # Errors
///
/// Returns an [`io::Error`] if `out_path` cannot be created or written.
pub fn write_tsv(frame: &SessionFrame, seeds: &[DirSeed], out_path: &Path) -> io::Result<()> {
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

    fn seed(side: Side, pivot_last_bar_ordinal: u64, causal_visible_ts_ns: i64) -> SignalSeed {
        SignalSeed {
            signal_id: [0x11; 32],
            extreme_side: side,
            pivot_price_u6: 1_000_000,
            pivot_last_bar_ordinal,
            causal_visible_ts_ns,
        }
    }

    /// Builds a frame with one Scalar group per bar, `prices[i]` at bar
    /// ordinal `i` (`m_lo == m_hi == prices[i]`), so every bar's
    /// representative close is exactly `prices[i]` and bar arithmetic is
    /// trivial to hand-verify. `session_end_bars` = `expected_bar_count`.
    fn one_group_per_bar_frame(prices: &[i64], session_end_bars: i64) -> SessionFrame {
        let bar_count = i64::try_from(prices.len()).expect("test bar count fits in i64");
        let ts_ns: Vec<i64> = (0..bar_count).map(|i| i * BAR_NS).collect();
        SessionFrame::from_parts_for_test(
            0,
            session_end_bars * BAR_NS,
            ts_ns,
            prices.to_vec(),
            prices.to_vec(),
            vec![GroupKind::Scalar; prices.len()],
            Vec::new(),
        )
    }

    // --------------------------- nearest_rung_at_least ---------------------------

    #[test]
    fn nearest_rung_hand_computed() {
        assert_eq!(nearest_rung_at_least(5), Some(5));
        assert_eq!(nearest_rung_at_least(7), Some(10));
        assert_eq!(nearest_rung_at_least(240), Some(240));
        assert_eq!(nearest_rung_at_least(241), None);
    }

    // ----------------------------- bar_sign / representative_bar_sign ---------------------------

    #[test]
    fn bar_sign_scalar_close_is_m_lo_not_a_midpoint() {
        // Scalar representative close = m_lo (== m_hi by construction) — E17
        // struck the (m_lo + m_hi) / 2 midpoint from this family entirely (the
        // midpoint stays reserved for magnitude-robust consumers, e.g.
        // F-CTRL / the regime streams' close_u6, per E7).
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0],
            vec![1_000_000],
            vec![1_000_000],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        assert_eq!(bar_sign(&frame, Side::Low, 999_000, 0), BarSign::Favorable);
        assert_eq!(bar_sign(&frame, Side::Low, 1_000_000, 0), BarSign::At);
        assert_eq!(bar_sign(&frame, Side::Low, 1_001_000, 0), BarSign::Adverse);
    }

    #[test]
    fn representative_bar_sign_excludes_a_heterogeneous_representative() {
        // A Heterogeneous representative is AMBIGUOUS_CLOSE (E1/E17): excluded
        // exactly like NO_QUOTE, never signed via its midpoint.
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0],
            vec![990_000],
            vec![1_010_000],
            vec![GroupKind::Heterogeneous],
            Vec::new(),
        );
        assert_eq!(
            representative_bar_sign(&frame, Side::Low, 1_000_000, Some(0), 0),
            None
        );
    }

    #[test]
    fn representative_bar_sign_window_left_guard_excludes_a_pre_window_group() {
        // The candidate group's index (0) predates the window's own left edge
        // (window_left = 1): excluded, no pre-window carry-forward (E17).
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0],
            vec![994_000],
            vec![994_000],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        assert_eq!(
            representative_bar_sign(&frame, Side::Low, 1_000_000, Some(0), 1),
            None
        );
    }

    // ------------------------- session_bar_last_group -------------------------

    #[test]
    fn session_bar_last_group_hand_computed() {
        // Groups at ts=0, 90e9 (bar1.5), 250e9 (bar4.17); 5 bars.
        let frame = SessionFrame::from_parts_for_test(
            0,
            5 * BAR_NS,
            vec![0, 90_000_000_000, 250_000_000_000],
            vec![100, 200, 300],
            vec![100, 200, 300],
            vec![GroupKind::Scalar; 3],
            Vec::new(),
        );
        let table = session_bar_last_group(&frame);
        assert_eq!(table.len(), 5);
        // bar0 = [0, 60e9): last group with ts<60e9 is group 0 (ts=0).
        assert_eq!(table[0], Some(0));
        // bar1 = [60e9, 120e9): last group with ts<120e9 is group 1 (ts=90e9).
        assert_eq!(table[1], Some(1));
        // bar2 = [120e9, 180e9): still group 1 (no new group yet).
        assert_eq!(table[2], Some(1));
        // bar3 = [180e9, 240e9): still group 1 (group 2 is at 250e9, not <240e9).
        assert_eq!(table[3], Some(1));
        // bar4 = [240e9, 300e9): last group with ts<300e9 is group 2 (ts=250e9).
        assert_eq!(table[4], Some(2));
    }

    #[test]
    fn session_bar_last_group_leading_no_quote_bars() {
        // First group at ts = 150e9 (bar 2.5): bars 0 and 1 are NO_QUOTE.
        let frame = SessionFrame::from_parts_for_test(
            0,
            5 * BAR_NS,
            vec![150_000_000_000],
            vec![100],
            vec![100],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let table = session_bar_last_group(&frame);
        assert_eq!(table[0], None);
        assert_eq!(table[1], None);
        assert_eq!(table[2], Some(0));
    }

    // ---------------------- dir_state_at: the five named states ----------------------

    #[test]
    fn continuation_when_favorable_touches_and_adverse_never_does() {
        // reversal_bps=40 (exact ladder rung) => N*=40 => distance=4000 at
        // anchor 1_000_000 => fav level 1_004_000, adv level 996_000.
        // seed_bar_ordinal=0 => D1 cutoff_bar=1 (window starts at bar1).
        let prices = vec![
            1_000_000, // bar0 (before window)
            1_000_000, // bar1 (window start, neutral)
            1_005_000, // bar2: favorable N* touch
            1_002_000, 1_002_000, 1_002_000, 1_002_000, 1_002_000, 1_002_000,
            1_002_000, // bar3-9
        ];
        let frame = one_group_per_bar_frame(&prices, 10);
        let s = seed(Side::Low, 0, 0);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        let bar_table = session_bar_last_group(&frame);
        let (n_star, state) = dir_state_at(&frame, &s, 40, &row, &bar_table);
        assert_eq!(n_star, Some(40));
        assert_eq!(state, DirState::Continuation);
    }

    #[test]
    fn reversal_when_adverse_touches_and_favorable_never_does() {
        let prices = vec![
            1_000_000, // bar0
            1_000_000, // bar1 (window start)
            994_000,   // bar2: adverse N* touch (<=996_000)
            998_000, 998_000, 998_000, 998_000, 998_000, 998_000, 998_000,
        ];
        let frame = one_group_per_bar_frame(&prices, 10);
        let s = seed(Side::Low, 0, 0);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        let bar_table = session_bar_last_group(&frame);
        let (n_star, state) = dir_state_at(&frame, &s, 40, &row, &bar_table);
        assert_eq!(n_star, Some(40));
        assert_eq!(state, DirState::Reversal);
    }

    #[test]
    fn false_break_when_both_touch_with_at_least_two_sign_changes_ending_adverse() {
        // bar1: 1_005_000 (fav touch, sign=Fav); bar2: 1_006_000 (Fav, no
        // change); bar3: 994_000 (adv touch, sign=Adv, CHANGE 1); bar4:
        // 1_001_000 (Fav, CHANGE 2); bar5: 999_000 (Adv, CHANGE 3);
        // bar6-9: 998_000 (Adv, no change). break_reclaim_count=3, final
        // sign=Adverse.
        let prices = vec![
            1_000_000, // bar0
            1_005_000, // bar1
            1_006_000, // bar2
            994_000,   // bar3
            1_001_000, // bar4
            999_000,   // bar5
            998_000, 998_000, 998_000, 998_000, // bar6-9
        ];
        let frame = one_group_per_bar_frame(&prices, 10);
        let s = seed(Side::Low, 0, 0);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        let bar_table = session_bar_last_group(&frame);
        let (n_star, state) = dir_state_at(&frame, &s, 40, &row, &bar_table);
        assert_eq!(n_star, Some(40));
        assert_eq!(state, DirState::FalseBreak);
    }

    #[test]
    fn reclaim_when_adverse_touches_first_and_favorable_touches_later() {
        // bar1: 994_000 (adv touch, index=1); bar2-8: 998_000 (Adv, no
        // change); bar9: 1_005_000 (fav touch, index=9, final bar).
        // break_reclaim_count=1 (<2): FALSE_BREAK does not fire.
        let prices = vec![
            1_000_000, // bar0
            994_000,   // bar1
            998_000, 998_000, 998_000, 998_000, 998_000, 998_000, 998_000,   // bar2-8
            1_005_000, // bar9
        ];
        let frame = one_group_per_bar_frame(&prices, 10);
        let s = seed(Side::Low, 0, 0);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        let bar_table = session_bar_last_group(&frame);
        let (n_star, state) = dir_state_at(&frame, &s, 40, &row, &bar_table);
        assert_eq!(n_star, Some(40));
        assert_eq!(state, DirState::Reclaim);
    }

    #[test]
    fn confirm_persist_when_both_touch_and_final_bar_sign_is_favorable() {
        // bar1: 1_005_000 (fav touch, index=1, sign=Fav); bar2: 994_000 (adv
        // touch, index=2, sign=Adv, CHANGE1); bar3-9: 1_002_000 (Fav,
        // CHANGE2 at bar3, then no more). break_reclaim_count=2, but final
        // sign is Favorable, not Adverse: FALSE_BREAK does not fire.
        // adv_index(2) < fav_index(1) is false, so RECLAIM does not fire.
        // Final sign favorable: CONFIRM_PERSIST.
        let prices = vec![
            1_000_000, // bar0
            1_005_000, // bar1
            994_000,   // bar2
            1_002_000, 1_002_000, 1_002_000, 1_002_000, 1_002_000, 1_002_000,
            1_002_000, // bar3-9
        ];
        let frame = one_group_per_bar_frame(&prices, 10);
        let s = seed(Side::Low, 0, 0);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        let bar_table = session_bar_last_group(&frame);
        let (n_star, state) = dir_state_at(&frame, &s, 40, &row, &bar_table);
        assert_eq!(n_star, Some(40));
        assert_eq!(state, DirState::ConfirmPersist);
    }

    #[test]
    fn inconclusive_when_both_touch_but_no_named_state_resolves() {
        // bar1: 1_005_000 (fav touch, index=1, Fav); bar2-8: 1_001_000 (Fav,
        // no change); bar9: 994_000 (adv touch, index=9, Adv, CHANGE1: only
        // 1 change, final bar). break_reclaim_count=1 (<2): no FALSE_BREAK.
        // adv_index(9) < fav_index(1): false, no RECLAIM. Final sign
        // Adverse, not Favorable: no CONFIRM_PERSIST. => INCONCLUSIVE.
        let prices = vec![
            1_000_000, // bar0
            1_005_000, // bar1
            1_001_000, 1_001_000, 1_001_000, 1_001_000, 1_001_000, 1_001_000,
            1_001_000, // bar2-8
            994_000,   // bar9
        ];
        let frame = one_group_per_bar_frame(&prices, 10);
        let s = seed(Side::Low, 0, 0);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        let bar_table = session_bar_last_group(&frame);
        let (n_star, state) = dir_state_at(&frame, &s, 40, &row, &bar_table);
        assert_eq!(n_star, Some(40));
        assert_eq!(state, DirState::Inconclusive);
    }

    // ------------------------- E17: exclusion law end-to-end -------------------------

    #[test]
    fn heterogeneous_representative_is_excluded_forensic_case_a_shape() {
        // Forensic Case A shape (ruling E17): a single-bar window whose one
        // group is Heterogeneous, wide enough to register BOTH an N*
        // favorable and adverse touch (interval-ambiguous on each side) —
        // driving `dir_state_at` into the "both touched: consult bar clock"
        // branch. Pre-fix, Rust signed this bar via the group's midpoint and
        // produced a real (wrong) state; post-fix the bar is AMBIGUOUS_CLOSE,
        // excluded from the sign sequence exactly like NO_QUOTE, so the bar
        // clock finds zero valid bars and the only correct total-function
        // answer is INCONCLUSIVE (matches the oracle on all diverging rows).
        let frame = SessionFrame::from_parts_for_test(
            0,
            2 * BAR_NS,
            vec![BAR_NS],
            vec![990_000],
            vec![1_010_000],
            vec![GroupKind::Heterogeneous],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        // D1 cutoff = BAR_NS; window = [BAR_NS, 2*BAR_NS) — exactly one bar.
        assert_eq!(row.window_left, Some(0));
        assert_eq!(row.window_end, Some(1));
        assert_eq!(row.window_frontier, WindowFrontier::Complete);
        let bar_table = session_bar_last_group(&frame);
        let (n_star, state) = dir_state_at(&frame, &s, 40, &row, &bar_table);
        assert_eq!(n_star, Some(40));
        assert_eq!(state, DirState::Inconclusive);
    }

    #[test]
    fn window_left_guard_prevents_the_leading_empty_bar_from_inheriting_a_pre_cutoff_group() {
        // g0 (ts=0) predates the window entirely; the window's own groups are
        // g1 (favorable touch) and g2 (adverse touch). The window's first bar
        // (cutoff_bar) has no group of its own, so the whole-session
        // `session_bar_last_group` table's UNCLAMPED lookup for that bar
        // resolves to g0 (index 0 < window_left = 1). Without the E17 guard,
        // that stale pre-window group would be wrongly signed (g0's price is
        // adverse), inserting a spurious extra sign change and flipping the
        // result to FALSE_BREAK (break_reclaim_count=2, final adverse); with
        // the guard, that leading bar is excluded (NO_QUOTE-like), leaving
        // break_reclaim_count=1 and the correct answer, INCONCLUSIVE.
        let ts_ns = vec![0, 3 * BAR_NS, 5 * BAR_NS];
        let m = vec![994_000, 1_005_000, 994_000];
        let frame = SessionFrame::from_parts_for_test(
            0,
            6 * BAR_NS,
            ts_ns,
            m.clone(),
            m,
            vec![GroupKind::Scalar; 3],
            Vec::new(),
        );
        // seed_bar_ordinal=1, D1 => cutoff_bar=2, cutoff_ts_ns=2*BAR_NS.
        let s = seed(Side::Low, 1, 0);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        assert_eq!(row.window_left, Some(1)); // g0 (index 0) predates the window.
        assert_eq!(row.window_end, Some(3));
        let bar_table = session_bar_last_group(&frame);
        // Sanity: the whole-session table's raw (unclamped) value for the
        // leading window bar (index 2) is indeed the stale pre-window group.
        assert_eq!(bar_table[2], Some(0));
        let (n_star, state) = dir_state_at(&frame, &s, 40, &row, &bar_table);
        assert_eq!(n_star, Some(40));
        assert_eq!(state, DirState::Inconclusive);
    }

    #[test]
    fn reclaim_is_reachable_even_when_the_bar_walk_excludes_every_bar() {
        // Regression for a residual rust/oracle divergence found on the
        // 22-day conformance re-run after the E17 fix: g0 (Heterogeneous,
        // adverse-only touch, index 0) and g1 (Heterogeneous, favorable-only
        // touch, index 1) are each the sole representative of their own bar,
        // so the bar walk excludes BOTH (AMBIGUOUS_CLOSE) — final_sign=None,
        // break_reclaim_count=0. The oracle's dir_state_and_n_star still
        // checks RECLAIM (adv.index < fav.index) unconditionally, off the
        // raw touch indices, not off the bar walk's final_sign — so the
        // correct answer is RECLAIM, not INCONCLUSIVE (an earlier, now-fixed
        // version of dir_state_at short-circuited to INCONCLUSIVE whenever
        // the bar walk found zero valid bars, which is wrong: E17's
        // exclusion law made "both N* levels touched, zero valid bars" a
        // real, reachable case, and RECLAIM must still be checked).
        let frame = SessionFrame::from_parts_for_test(
            0,
            3 * BAR_NS,
            vec![BAR_NS, 2 * BAR_NS],
            vec![990_000, 1_003_000],
            vec![997_000, 1_010_000],
            vec![GroupKind::Heterogeneous, GroupKind::Heterogeneous],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        assert_eq!(row.window_left, Some(0));
        assert_eq!(row.window_end, Some(2));
        let bar_table = session_bar_last_group(&frame);
        let (n_star, state) = dir_state_at(&frame, &s, 40, &row, &bar_table);
        assert_eq!(n_star, Some(40));
        assert_eq!(state, DirState::Reclaim);
    }

    // --------------------------- typed completions ---------------------------

    #[test]
    fn neither_complete_when_price_never_touches_either_n_star_level() {
        let prices = vec![1_000_000, 1_001_000, 1_002_000, 999_000, 1_000_500];
        let frame = one_group_per_bar_frame(&prices, 5);
        let s = seed(Side::Low, 0, 0);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        let bar_table = session_bar_last_group(&frame);
        let (n_star, state) = dir_state_at(&frame, &s, 40, &row, &bar_table);
        assert_eq!(n_star, Some(40));
        assert_eq!(state, DirState::NeitherComplete);
    }

    #[test]
    fn neither_wide_breaker_when_a_breaker_censors_before_either_level_touches() {
        let ts_ns = vec![0, BAR_NS, 5 * BAR_NS];
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            ts_ns,
            vec![100, 999_800, 1_999_000],
            vec![100, 999_000, 2_000_000],
            vec![GroupKind::Scalar; 3],
            vec![Breaker {
                start_ns: 2 * BAR_NS,
                end_ns: 4 * BAR_NS,
            }],
        );
        let s = seed(Side::Low, 0, 0);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        assert_eq!(row.window_frontier, WindowFrontier::WideBreaker);
        let bar_table = session_bar_last_group(&frame);
        let (_, state) = dir_state_at(&frame, &s, 5, &row, &bar_table);
        assert_eq!(state, DirState::NeitherWideBreaker);
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
        // seed_bar_ordinal such that D1 cutoff == session_end: empty window.
        let s = seed(Side::Low, 4, 0);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        // D1 cutoff = 5*BAR_NS > session_end (4 bars * ... wait recompute:
        // session_end = 5*BAR_NS here actually not applicable; use a window
        // that's empty in GROUP terms but still slot_available/visible.
        let _ = row;
        let frame2 = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS, 2 * BAR_NS],
            vec![100, 100, 100],
            vec![100, 100, 100],
            vec![GroupKind::Scalar; 3],
            Vec::new(),
        );
        let s2 = seed(Side::Low, 0, 0);
        // D1 cutoff = BAR_NS; use nominal_end = BAR_NS (degenerate window).
        let row2 = SlotRow::compute(&frame2, &s2, Slot::D1, BAR_NS);
        assert_eq!(row2.window_frontier, WindowFrontier::SourceCensored);
        let bar_table2 = session_bar_last_group(&frame2);
        let (_, state) = dir_state_at(&frame2, &s2, 5, &row2, &bar_table2);
        assert_eq!(state, DirState::NeitherSourceCensored);
    }

    #[test]
    fn out_of_domain_outranks_a_real_touch() {
        // Same construction as f_pass's own OUT_OF_DOMAIN case: anchor=1,
        // N=240 puts the adverse level at 0.
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0],
            vec![0],
            vec![5],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0);
        let s = SignalSeed {
            pivot_price_u6: 1,
            ..s
        };
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        let bar_table = session_bar_last_group(&frame);
        let (n_star, state) = dir_state_at(&frame, &s, 240, &row, &bar_table);
        assert_eq!(n_star, Some(240));
        assert_eq!(state, DirState::OutOfDomain);
    }

    #[test]
    fn no_ladder_rung_when_reversal_bps_exceeds_the_ladder_max() {
        let frame = one_group_per_bar_frame(&[1_000_000, 1_000_000], 5);
        let s = seed(Side::Low, 0, 0);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        let bar_table = session_bar_last_group(&frame);
        let (n_star, state) = dir_state_at(&frame, &s, 241, &row, &bar_table);
        assert_eq!(n_star, None);
        assert_eq!(state, DirState::NoLadderRung);
    }

    #[test]
    fn na_when_row_is_decision_unavailable_or_not_visible() {
        let frame = one_group_per_bar_frame(&[1_000_000, 1_000_000, 1_000_000], 3);
        // seed_bar_ordinal near the session end: D2/D3 are unavailable.
        let s = seed(Side::Low, 1, 0);
        let row_d2 = SlotRow::compute(&frame, &s, Slot::D2, frame.session_end_ns);
        assert_eq!(row_d2.window_frontier, WindowFrontier::DecisionUnavailable);
        let bar_table = session_bar_last_group(&frame);
        let (n_star, state) = dir_state_at(&frame, &s, 40, &row_d2, &bar_table);
        assert_eq!(n_star, None);
        assert_eq!(state, DirState::Na);

        let s_not_visible = seed(Side::Low, 0, BAR_NS + 1);
        let row_d1 = SlotRow::compute(&frame, &s_not_visible, Slot::D1, frame.session_end_ns);
        assert_eq!(row_d1.window_frontier, WindowFrontier::NotVisible);
        let (n_star2, state2) = dir_state_at(&frame, &s_not_visible, 40, &row_d1, &bar_table);
        assert_eq!(n_star2, None);
        assert_eq!(state2, DirState::Na);
    }

    // --------------------------------- write_tsv ---------------------------------

    fn temp_out_path(name: &str) -> std::path::PathBuf {
        std::env::temp_dir().join(format!("f_dir_test_{}_{name}.tsv", std::process::id()))
    }

    #[test]
    fn write_tsv_header_has_the_exact_expected_column_count() {
        let header = header();
        let columns: Vec<&str> = header.split('\t').collect();
        assert_eq!(columns.len(), 12);
        assert_eq!(columns[9], "window_frontier");
        assert_eq!(columns[10], "dir_n_star_bps");
        assert_eq!(columns[11], "dir_state");
    }

    #[test]
    fn write_tsv_produces_three_rows_with_a_reachable_continuation_state() {
        let prices = vec![
            1_000_000, 1_000_000, 1_005_000, 1_002_000, 1_002_000, 1_002_000, 1_002_000, 1_002_000,
            1_002_000, 1_002_000,
        ];
        let frame = one_group_per_bar_frame(&prices, 10);
        let seeds = vec![DirSeed {
            seed: seed(Side::Low, 0, 0),
            reversal_bps: 40,
        }];
        let path = temp_out_path("continuation");
        write_tsv(&frame, &seeds, &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        assert_eq!(lines.next(), Some(header().as_str()));
        let d1 = lines.next().expect("D1 row");
        lines.next(); // D2
        lines.next(); // D3
        assert_eq!(lines.next(), None);

        let d1_cols: Vec<&str> = d1.split('\t').collect();
        assert_eq!(d1_cols[10], "40");
        assert_eq!(d1_cols[11], "CONTINUATION");

        std::fs::remove_file(&path).ok();
    }

    #[test]
    fn write_tsv_decision_unavailable_row_is_na() {
        let frame = one_group_per_bar_frame(&[1_000_000, 1_000_000, 1_000_000], 3);
        let seeds = vec![DirSeed {
            seed: seed(Side::Low, 1, 0),
            reversal_bps: 40,
        }];
        let path = temp_out_path("decision_unavailable");
        write_tsv(&frame, &seeds, &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        lines.next(); // header
        lines.next(); // D1
        let d2 = lines.next().expect("D2 row");
        let d2_cols: Vec<&str> = d2.split('\t').collect();
        assert_eq!(d2_cols[9], "DECISION_UNAVAILABLE");
        assert_eq!(d2_cols[10], "NA");
        assert_eq!(d2_cols[11], "NA");
        std::fs::remove_file(&path).ok();
    }
}
