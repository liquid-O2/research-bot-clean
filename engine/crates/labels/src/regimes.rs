//! Regime streams — realized-vol / range-variance-proxy / band-and-net-move /
//! liquidity-quality / session-clock family, one row per `(session, completed
//! bar)`, prefix-causal by construction (design authority:
//! `docs/specs/events3_design_v1.md` §B, `docs/specs/events3_formula_addendum_v1.md`
//! §1, **corrected/extended by** `docs/specs/events3_design_amendment_v2.md`
//! §A8 (`range_valid_count_<W>`) and ruling E7 (bar-close scalar =
//! `floor((m_lo + m_hi) / 2)` of the representative group, midpointed rather
//! than `AMBIGUOUS_CLOSE`-excluded for regression/stream consumers)). Exact
//! schema (columns, states, formulas — read before this module):
//! `docs/specs/family_schemas/regimes_schema_v1.md`.
//!
//! Unlike every other label family this is **not** per-`(signal, slot)`: there
//! is no anchor, no window frontier, no `NA`-row rule. Every bar in
//! `[0, expected_bar_count)` gets a row unconditionally.
//!
//! `SessionFrame`'s own scientific-path projection (out of this wave's
//! assigned-file scope, see `frame.rs`) discards every `WideOnly`/
//! `Unresolved` group during `SessionFrame::build`, so the liquidity columns
//! (`wide_only_group_count`, `unresolved_group_count`,
//! `distinct_scientific_midpoint_count`) are not derivable from the frame
//! alone. [`compute`]/[`write_tsv`] therefore take the session's raw
//! `corpus::SessionData` (for `.groups`, the complete unfiltered table) IN
//! ADDITION TO the `SessionFrame` (for `close_u6`/`high_u6`/`low_u6` and the
//! derived breaker table) — see the schema doc's "Data-access note" escalation
//! and the implementation report.

use crate::frame::SessionFrame;
use corpus::{QuoteGroups, QuoteKind, SessionData};
use std::fmt::Write as _;
use std::fs::File;
use std::io::{self, BufWriter, Write as _};
use std::path::Path;

/// Registered one-minute bar duration in nanoseconds (CONV §3), matching
/// every other family module's own local copy.
const NANOSECONDS_PER_BAR: i64 = 60_000_000_000;

/// The three registered realized-vol / range-variance-proxy window sizes, in
/// whole one-minute bars (addendum §1), in column order.
pub const WINDOWS: [i64; 3] = [5, 15, 60];

/// The fixed band / net-move horizon, in whole one-minute bars (addendum
/// §1).
pub const BAND_NET_MOVE_BARS: i64 = 30;

/// The registered early-close bar count (CONV §3): the nine half-day
/// sessions run exactly this many one-minute bars, every other session runs
/// 390.
const EARLY_CLOSE_BAR_COUNT: u16 = 210;

// ============================== Typed states ==============================

/// Overflow guard for every `i128`-accumulated, `i64`-published sum in this
/// family (schema "Typed states, exhaustive list").
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SumState {
    Ok,
    Overflow,
}

impl SumState {
    /// The wire string for a `*_state` column.
    #[must_use]
    pub const fn wire(self) -> &'static str {
        match self {
            Self::Ok => "OK",
            Self::Overflow => "OVERFLOW",
        }
    }
}

/// One realized-vol or range-variance-proxy window's published pair
/// (`rv_sum_sq_<W>`/`rv_count_<W>` or `range_sum_sq_<W>`/
/// `range_valid_count_<W>`, schema "Realized-vol family" / "Range-variance-
/// proxy family"): `sum_sq` is `None` iff `state == Overflow`; `count` is
/// always present (`0` is legitimate, never a failure).
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct WindowStat {
    pub state: SumState,
    pub sum_sq: Option<i64>,
    pub count: i64,
}

/// `band_u6_30`'s typed state (schema "Band / net-move").
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum BandState {
    Ok,
    Overflow,
    /// Zero valid (non-`NO_QUOTE`) bars anywhere in the causal window.
    NoData,
}

impl BandState {
    #[must_use]
    pub const fn wire(self) -> &'static str {
        match self {
            Self::Ok => "OK",
            Self::Overflow => "OVERFLOW",
            Self::NoData => "NO_DATA",
        }
    }
}

/// `band_u6_30`'s published pair.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct BandResult {
    pub state: BandState,
    pub value_u6: Option<i64>,
}

/// `net_move_u6_30`'s typed state (schema "Band / net-move").
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum NetMoveState {
    Ok,
    Overflow,
    /// `b < 30`: bar `b − 30` does not exist.
    InsufficientHistory,
    /// Either endpoint bar's `close_u6` is `NO_QUOTE`.
    NoQuote,
}

impl NetMoveState {
    #[must_use]
    pub const fn wire(self) -> &'static str {
        match self {
            Self::Ok => "OK",
            Self::Overflow => "OVERFLOW",
            Self::InsufficientHistory => "INSUFFICIENT_HISTORY",
            Self::NoQuote => "NO_QUOTE",
        }
    }
}

/// `net_move_u6_30`'s published pair.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct NetMoveResult {
    pub state: NetMoveState,
    pub value_u6: Option<i64>,
}

/// One complete `(session, bar)` row (schema "Value columns"): the in-memory
/// type consumed directly by `metrics`/`publish` without a TSV round-trip.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct RegimeRow {
    pub bar_ordinal: i64,
    /// Realized-vol windows, aligned index-for-index with [`WINDOWS`].
    pub rv: [WindowStat; 3],
    /// Range-variance-proxy windows, aligned index-for-index with
    /// [`WINDOWS`].
    pub range: [WindowStat; 3],
    pub band_u6_30: BandResult,
    pub net_move_u6_30: NetMoveResult,
    pub scientific_group_count: i64,
    pub wide_only_group_count: i64,
    pub unresolved_group_count: i64,
    pub distinct_scientific_midpoint_count: i64,
    pub in_breaker: bool,
    pub bars_remaining: i64,
    pub early_close: bool,
}

// ============================== Bar-close primitives ==============================

/// One bar's resolved price primitives (schema "Bar-level primitives", not
/// published directly): `close_u6` carries forward from the last scientific
/// group anywhere before `bar_end_ns` (`None` only before the session's
/// first-ever scientific group); `high_u6`/`low_u6` are the bar's OWN
/// scientific groups only, `None` together whenever the bar itself has zero
/// of them (no carry-forward).
#[derive(Clone, Copy, Debug)]
struct BarPrice {
    close_u6: Option<i64>,
    high_u6: Option<i64>,
    low_u6: Option<i64>,
    /// Count of frame-index (scientific-path) groups in this bar's own span
    /// — the same range used to resolve `high_u6`/`low_u6`, so
    /// `scientific_group_count > 0` iff `high_u6.is_some()` by construction.
    scientific_group_count: i64,
}

/// `bar_start_ns(b)` / `bar_end_ns(b)` for the registered one-minute grid
/// (CONV §3), from `session_start_ns`.
///
/// # Panics
///
/// Panics on `i64` overflow — unreachable for any registered session (`b` is
/// bounded by `expected_bar_count`, at most a few hundred).
fn bar_bound_ns(session_start_ns: i64, bars_after_start: i64) -> i64 {
    bars_after_start
        .checked_mul(NANOSECONDS_PER_BAR)
        .and_then(|offset| session_start_ns.checked_add(offset))
        .expect("bar boundary arithmetic overflowed i64 for a registered session")
}

/// Resolves every bar's `close_u6`/`high_u6`/`low_u6` and its own
/// `scientific_group_count` (schema "Bar-level primitives"), from the
/// [`SessionFrame`]'s scientific-path projection only.
///
/// O(`bar_count` · log n), `n` = `frame.group_count()`: one
/// [`SessionFrame::end_position`] descent per bar boundary (the previous
/// bar's own end index is reused as the next bar's start index, so exactly
/// `bar_count` descents total, not `2 · bar_count`).
///
/// # Panics
///
/// Panics if a resolved group's `(m_lo + m_hi) / 2` midpoint does not fit
/// `i64` — unreachable for any registered price (many orders of magnitude
/// under `i64::MAX / 2`).
fn resolve_bar_prices(frame: &SessionFrame, bar_count: usize) -> Vec<BarPrice> {
    let mut out = Vec::with_capacity(bar_count);
    let mut start_idx = frame.end_position(frame.session_start_ns);
    for b in 0..bar_count {
        let b_i64 = i64::try_from(b).expect("bar ordinal fits i64");
        let end_ns = bar_bound_ns(frame.session_start_ns, b_i64 + 1);
        let end_idx = frame.end_position(end_ns);

        let scientific_group_count =
            i64::try_from(end_idx - start_idx).expect("bar group count fits i64");
        let (high_u6, low_u6) = if end_idx > start_idx {
            let high = frame.m_hi[start_idx..end_idx]
                .iter()
                .copied()
                .max()
                .expect("nonempty range has a max");
            let low = frame.m_lo[start_idx..end_idx]
                .iter()
                .copied()
                .min()
                .expect("nonempty range has a min");
            (Some(high), Some(low))
        } else {
            (None, None)
        };
        let close_u6 = if end_idx == 0 {
            None
        } else {
            let g = end_idx - 1;
            let mid = i128::midpoint(i128::from(frame.m_lo[g]), i128::from(frame.m_hi[g]));
            Some(
                i64::try_from(mid)
                    .expect("group midpoint average fits i64 for any registered price"),
            )
        };

        out.push(BarPrice {
            close_u6,
            high_u6,
            low_u6,
            scientific_group_count,
        });
        start_idx = end_idx;
    }
    out
}

// ============================== Liquidity / breaker passes ==============================

/// One bar's raw-group liquidity tally (schema "Liquidity / quality per
/// bar"): `wide_only_group_count`/`unresolved_group_count`/
/// `distinct_scientific_midpoint_count`, computed against the session's
/// COMPLETE unfiltered quote-group table (`corpus::SessionData.groups`), not
/// the scientific-only frame projection.
#[derive(Clone, Copy, Debug, Default)]
struct BarLiquidity {
    wide_only_groups: i64,
    unresolved_groups: i64,
    distinct_scientific_midpoints: i64,
}

/// Resolves every bar's liquidity tally with one linear merge pass over
/// `groups.ts_ns` (ascending, causal order per `QuoteGroups`'s own
/// invariant) against the ascending bar boundaries.
///
/// O(`groups.len()` + `bar_count` · log(max per-bar group count)): one
/// forward pass over the complete group table (never revisited), plus one
/// sort+dedup of each bar's own collected scientific midpoints (bounded by
/// that bar's own group count, never the session total).
///
/// # Panics
///
/// Panics if a bar's own group count does not fit `i64` — unreachable (a
/// one-minute bar holds at most 60,000 millisecond-groups).
fn resolve_bar_liquidity(
    groups: &QuoteGroups,
    session_start_ns: i64,
    bar_count: usize,
) -> Vec<BarLiquidity> {
    let mut out = Vec::with_capacity(bar_count);
    let mut group_index = 0_usize;
    let total_groups = groups.len();
    let mut scratch: Vec<i64> = Vec::new();
    for b in 0..bar_count {
        let b_i64 = i64::try_from(b).expect("bar ordinal fits i64");
        let end_ns = bar_bound_ns(session_start_ns, b_i64 + 1);

        let mut wide_only_groups: i64 = 0;
        let mut unresolved_groups: i64 = 0;
        scratch.clear();
        while group_index < total_groups && groups.ts_ns[group_index] < end_ns {
            match groups.kind[group_index] {
                QuoteKind::SingleScientific | QuoteKind::MultiScientific => {
                    scratch.extend_from_slice(groups.scientific_midpoints(group_index));
                }
                QuoteKind::WideOnly => {
                    wide_only_groups = wide_only_groups
                        .checked_add(1)
                        .expect("wide_only_groups fits i64 for one bar");
                }
                QuoteKind::Unresolved => {
                    unresolved_groups = unresolved_groups
                        .checked_add(1)
                        .expect("unresolved_groups fits i64 for one bar");
                }
            }
            group_index += 1;
        }
        scratch.sort_unstable();
        scratch.dedup();
        out.push(BarLiquidity {
            wide_only_groups,
            unresolved_groups,
            distinct_scientific_midpoints: i64::try_from(scratch.len())
                .expect("distinct midpoint count fits i64 for one bar"),
        });
    }
    out
}

/// Resolves every bar's `in_breaker` flag (schema "Liquidity / quality per
/// bar"): half-open overlap of the bar's own span with any breaker interval
/// from the frame's derived breaker table (CONV §8's overlap test).
///
/// O(`bar_count` + `frame.breakers().len()`): one merge pass over both
/// ascending, non-overlapping sequences (a breaker pointer only ever
/// advances).
fn resolve_in_breaker(frame: &SessionFrame, bar_count: usize) -> Vec<bool> {
    let breakers = frame.breakers();
    let mut out = Vec::with_capacity(bar_count);
    let mut breaker_index = 0_usize;
    for b in 0..bar_count {
        let b_i64 = i64::try_from(b).expect("bar ordinal fits i64");
        let start_ns = bar_bound_ns(frame.session_start_ns, b_i64);
        let end_ns = bar_bound_ns(frame.session_start_ns, b_i64 + 1);
        while breaker_index < breakers.len() && breakers[breaker_index].end_ns <= start_ns {
            breaker_index += 1;
        }
        let overlaps = breaker_index < breakers.len() && breakers[breaker_index].start_ns < end_ns;
        out.push(overlaps);
    }
    out
}

// ============================== Windowed statistics ==============================

/// `rv_sum_sq_<W>`/`rv_count_<W>` at bar `b` (schema "Realized-vol family"):
/// Σ `d_i²` over `i ∈ [max(1, b−W+1), b]`, valid diffs only (`close_u6[i]`
/// AND `close_u6[i−1]` both present), `i128`-accumulated.
///
/// O(`W`).
fn rv_window_stat(prices: &[BarPrice], b: usize, w: i64) -> WindowStat {
    let b_i64 = i64::try_from(b).expect("bar ordinal fits i64");
    let lower = (b_i64 - w + 1).max(1);
    let mut sum: i128 = 0;
    let mut count: i64 = 0;
    let mut i = lower;
    while i <= b_i64 {
        let cur = usize::try_from(i).expect("window index fits usize");
        if let (Some(c1), Some(c0)) = (prices[cur].close_u6, prices[cur - 1].close_u6) {
            let d = i128::from(c1) - i128::from(c0);
            sum += d * d;
            count += 1;
        }
        i += 1;
    }
    match i64::try_from(sum) {
        Ok(value) => WindowStat {
            state: SumState::Ok,
            sum_sq: Some(value),
            count,
        },
        Err(_) => WindowStat {
            state: SumState::Overflow,
            sum_sq: None,
            count,
        },
    }
}

/// `range_sum_sq_<W>`/`range_valid_count_<W>` at bar `b` (schema
/// "Range-variance-proxy family"): Σ `(high_u6[i] − low_u6[i])²` over `i ∈
/// [max(0, b−W+1), b]`, valid bars only, `i128`-accumulated.
///
/// O(`W`).
fn range_window_stat(prices: &[BarPrice], b: usize, w: i64) -> WindowStat {
    let b_i64 = i64::try_from(b).expect("bar ordinal fits i64");
    let lower = (b_i64 - w + 1).max(0);
    let mut sum: i128 = 0;
    let mut count: i64 = 0;
    let mut i = lower;
    while i <= b_i64 {
        let idx = usize::try_from(i).expect("window index fits usize");
        if let (Some(high), Some(low)) = (prices[idx].high_u6, prices[idx].low_u6) {
            let d = i128::from(high) - i128::from(low);
            sum += d * d;
            count += 1;
        }
        i += 1;
    }
    match i64::try_from(sum) {
        Ok(value) => WindowStat {
            state: SumState::Ok,
            sum_sq: Some(value),
            count,
        },
        Err(_) => WindowStat {
            state: SumState::Overflow,
            sum_sq: None,
            count,
        },
    }
}

/// `band_u6_30` at bar `b` (schema "Band / net-move"): `max(high_u6) −
/// min(low_u6)` over valid bars in `i ∈ [max(0, b−29), b]`.
///
/// O(`BAND_NET_MOVE_BARS`).
fn band_at(prices: &[BarPrice], b: usize) -> BandResult {
    let b_i64 = i64::try_from(b).expect("bar ordinal fits i64");
    let lower = (b_i64 - BAND_NET_MOVE_BARS + 1).max(0);
    let mut max_high: Option<i64> = None;
    let mut min_low: Option<i64> = None;
    let mut i = lower;
    while i <= b_i64 {
        let idx = usize::try_from(i).expect("window index fits usize");
        if let (Some(high), Some(low)) = (prices[idx].high_u6, prices[idx].low_u6) {
            max_high = Some(max_high.map_or(high, |m| m.max(high)));
            min_low = Some(min_low.map_or(low, |m| m.min(low)));
        }
        i += 1;
    }
    match (max_high, min_low) {
        (Some(high), Some(low)) => match high.checked_sub(low) {
            Some(value) => BandResult {
                state: BandState::Ok,
                value_u6: Some(value),
            },
            None => BandResult {
                state: BandState::Overflow,
                value_u6: None,
            },
        },
        _ => BandResult {
            state: BandState::NoData,
            value_u6: None,
        },
    }
}

/// `net_move_u6_30` at bar `b` (schema "Band / net-move"): `close_u6[b] −
/// close_u6[b−30]`, a fixed lag-30 difference (not a windowed quantity).
///
/// O(1).
fn net_move_at(prices: &[BarPrice], b: usize) -> NetMoveResult {
    let b_i64 = i64::try_from(b).expect("bar ordinal fits i64");
    if b_i64 < BAND_NET_MOVE_BARS {
        return NetMoveResult {
            state: NetMoveState::InsufficientHistory,
            value_u6: None,
        };
    }
    let lag_idx = usize::try_from(b_i64 - BAND_NET_MOVE_BARS).expect("lag index fits usize");
    match (prices[b].close_u6, prices[lag_idx].close_u6) {
        (Some(cur), Some(prev)) => match cur.checked_sub(prev) {
            Some(value) => NetMoveResult {
                state: NetMoveState::Ok,
                value_u6: Some(value),
            },
            None => NetMoveResult {
                state: NetMoveState::Overflow,
                value_u6: None,
            },
        },
        _ => NetMoveResult {
            state: NetMoveState::NoQuote,
            value_u6: None,
        },
    }
}

// ============================== Public API ==============================

/// Computes the complete regime-stream table for one session: one
/// [`RegimeRow`] per bar in `[0, frame.expected_bar_count)`
/// (`docs/specs/family_schemas/regimes_schema_v1.md`).
///
/// `session` and `frame` must describe the SAME session (`session.groups`
/// is the complete unfiltered quote-group table `frame`'s scientific-path
/// projection was itself filtered from) — see the module doc comment's
/// data-access note.
///
/// O(`bar_count` · log n + `session.groups.len()` + `bar_count` ·
/// `max(WINDOWS)`), `n` = `frame.group_count()` — see each private helper's
/// own doc comment for its share of this budget.
///
/// # Panics
///
/// Panics if `frame.expected_bar_count` (bounded by construction to 210 or
/// 390 for any registered session) or a bar ordinal derived from it does not
/// fit `i64` — unreachable for any registered session.
#[must_use]
pub fn compute(session: &SessionData, frame: &SessionFrame) -> Vec<RegimeRow> {
    let bar_count = usize::from(frame.expected_bar_count);
    let prices = resolve_bar_prices(frame, bar_count);
    let liquidity = resolve_bar_liquidity(&session.groups, frame.session_start_ns, bar_count);
    let in_breaker = resolve_in_breaker(frame, bar_count);
    let early_close = frame.expected_bar_count == EARLY_CLOSE_BAR_COUNT;

    (0..bar_count)
        .map(|b| {
            let bar_ordinal = i64::try_from(b).expect("bar ordinal fits i64");
            let rv = WINDOWS.map(|w| rv_window_stat(&prices, b, w));
            let range = WINDOWS.map(|w| range_window_stat(&prices, b, w));
            RegimeRow {
                bar_ordinal,
                rv,
                range,
                band_u6_30: band_at(&prices, b),
                net_move_u6_30: net_move_at(&prices, b),
                scientific_group_count: prices[b].scientific_group_count,
                wide_only_group_count: liquidity[b].wide_only_groups,
                unresolved_group_count: liquidity[b].unresolved_groups,
                distinct_scientific_midpoint_count: liquidity[b].distinct_scientific_midpoints,
                in_breaker: in_breaker[b],
                bars_remaining: i64::from(frame.expected_bar_count) - 1 - bar_ordinal,
                early_close,
            }
        })
        .collect()
}

/// The `regimes.tsv` header (`docs/specs/family_schemas/regimes_schema_v1.md`
/// "Value columns").
#[must_use]
pub fn header() -> String {
    let mut out = String::from("day\tbar_ordinal");
    for w in WINDOWS {
        write!(out, "\trv_sum_sq_{w}\trv_sum_sq_{w}_state\trv_count_{w}")
            .expect("writing to a String cannot fail");
    }
    for w in WINDOWS {
        write!(
            out,
            "\trange_sum_sq_{w}\trange_sum_sq_{w}_state\trange_valid_count_{w}"
        )
        .expect("writing to a String cannot fail");
    }
    out.push_str(
        "\tband_u6_30\tband_u6_30_state\tnet_move_u6_30\tnet_move_u6_30_state\t\
         scientific_group_count\twide_only_group_count\tunresolved_group_count\t\
         distinct_scientific_midpoint_count\tin_breaker\tbars_remaining\tearly_close",
    );
    out
}

/// `true`/`false`, per the schema's boolean formatting rule.
const fn bool_wire(value: bool) -> &'static str {
    if value { "true" } else { "false" }
}

/// Appends one `WindowStat`'s three columns (`value`, `state`, `count`),
/// tab-prefixed.
fn push_window_stat(line: &mut String, stat: &WindowStat) {
    match stat.sum_sq {
        Some(value) => write!(line, "\t{value}\t{}\t{}", stat.state.wire(), stat.count),
        None => write!(line, "\tNA\t{}\t{}", stat.state.wire(), stat.count),
    }
    .expect("writing to a String cannot fail");
}

/// Formats one complete row (`day` + all value columns), no trailing
/// newline.
///
/// # Panics
///
/// Never in practice: the internal `expect`s guard `write!` onto an
/// in-memory `String`, which cannot fail.
#[must_use]
pub fn format_row(day: &str, row: &RegimeRow) -> String {
    let mut line = format!("{day}\t{}", row.bar_ordinal);
    for stat in &row.rv {
        push_window_stat(&mut line, stat);
    }
    for stat in &row.range {
        push_window_stat(&mut line, stat);
    }
    match row.band_u6_30.value_u6 {
        Some(value) => write!(line, "\t{value}\t{}", row.band_u6_30.state.wire()),
        None => write!(line, "\tNA\t{}", row.band_u6_30.state.wire()),
    }
    .expect("writing to a String cannot fail");
    match row.net_move_u6_30.value_u6 {
        Some(value) => write!(line, "\t{value}\t{}", row.net_move_u6_30.state.wire()),
        None => write!(line, "\tNA\t{}", row.net_move_u6_30.state.wire()),
    }
    .expect("writing to a String cannot fail");
    write!(
        line,
        "\t{}\t{}\t{}\t{}\t{}\t{}\t{}",
        row.scientific_group_count,
        row.wide_only_group_count,
        row.unresolved_group_count,
        row.distinct_scientific_midpoint_count,
        bool_wire(row.in_breaker),
        row.bars_remaining,
        bool_wire(row.early_close),
    )
    .expect("writing to a String cannot fail");
    line
}

/// Writes `regimes.tsv` for one session: one row per completed bar, ascending
/// `bar_ordinal` (`docs/specs/family_schemas/regimes_schema_v1.md`).
///
/// `session` and `frame` must describe the SAME session (see [`compute`]'s
/// doc comment).
///
/// O(same as [`compute`]) + O(`bar_count`) for serialization.
///
/// # Errors
///
/// Returns an [`io::Error`] if `out_path` cannot be created or written.
pub fn write_tsv(session: &SessionData, frame: &SessionFrame, out_path: &Path) -> io::Result<()> {
    let rows = compute(session, frame);
    let mut out = BufWriter::new(File::create(out_path)?);
    writeln!(out, "{}", header())?;
    for row in &rows {
        writeln!(out, "{}", format_row(frame.day, row))?;
    }
    out.flush()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::frame::{Breaker, GroupKind};
    use corpus::QualityFlags;

    const BAR_NS: i64 = NANOSECONDS_PER_BAR;

    /// Builds a minimal [`SessionData`] with a hand-specified raw group
    /// table (ALL kinds, exactly as `corpus::load_session` would decode
    /// them) — every `QuoteGroups` field [`compute`]/its helpers don't touch
    /// is zeroed/defaulted, since `SessionData`/`QuoteGroups` have zero
    /// private fields and are constructible by field literal from anywhere
    /// in this crate.
    fn make_session(
        session_start_ns: i64,
        session_end_ns: i64,
        expected_bar_count: u16,
        entries: &[(i64, QuoteKind, &[i64])],
    ) -> SessionData {
        let n = entries.len();
        let mut ts_ns = Vec::with_capacity(n);
        let mut kind = Vec::with_capacity(n);
        let mut scientific_midpoint_offsets = vec![0_u32];
        let mut scientific_midpoints_u6 = Vec::new();
        for &(ts, k, mids) in entries {
            ts_ns.push(ts);
            kind.push(k);
            scientific_midpoints_u6.extend_from_slice(mids);
            scientific_midpoint_offsets.push(
                u32::try_from(scientific_midpoints_u6.len())
                    .expect("test fixture midpoint count fits u32"),
            );
        }
        SessionData {
            day: "TEST",
            session_start_ns,
            session_end_ns,
            expected_bar_count,
            source_sha256: "test",
            groups: QuoteGroups {
                ts_ns,
                raw_member_count: vec![0; n],
                structurally_valid_count: vec![0; n],
                scientific_member_count: vec![0; n],
                wide_member_count: vec![0; n],
                rejected_member_count: vec![0; n],
                has_locked_member: vec![false; n],
                kind,
                quality: vec![QualityFlags::default(); n],
                scientific_midpoint_offsets,
                scientific_midpoints_u6,
                wide_midpoint_offsets: vec![0; n + 1],
                wide_midpoints_u6: Vec::new(),
            },
        }
    }

    /// Builds a [`SessionFrame`] directly from a scientific-path-only group
    /// list (`ts_ns`, `m_lo`, `m_hi` all equal per group — i.e. every group is
    /// `Scalar`), with `expected_bar_count` set as given (the shared
    /// `from_parts_for_test` helper hardcodes it to 0, but the field is
    /// `pub`, so tests overwrite it directly).
    fn scalar_frame(
        session_start_ns: i64,
        session_end_ns: i64,
        expected_bar_count: u16,
        prices: &[(i64, i64)],
        breakers: Vec<Breaker>,
    ) -> SessionFrame {
        let ts_ns: Vec<i64> = prices.iter().map(|&(ts, _)| ts).collect();
        let values: Vec<i64> = prices.iter().map(|&(_, v)| v).collect();
        let mut frame = SessionFrame::from_parts_for_test(
            session_start_ns,
            session_end_ns,
            ts_ns,
            values.clone(),
            values.clone(),
            vec![GroupKind::Scalar; values.len()],
            breakers,
        );
        frame.expected_bar_count = expected_bar_count;
        frame
    }

    /// A session with zero scientific-path groups at all (every bar
    /// `NO_QUOTE`/liquidity-desert) is never constructed here: every real
    /// registered session has at least one scientific-path group
    /// (`SessionFrame::build`'s own panic invariant), so at least one
    /// `(ts, price)` pair is always supplied.

    // ------------------------- rv windows across NO_QUOTE bars -------------------------

    #[test]
    fn rv_window_excludes_diffs_touching_leading_no_quote_bars() {
        // Bars 0,1,2 have no scientific group at all (leading NO_QUOTE);
        // bar 3's own group is the session's first-ever quote (close=1000);
        // bar 4 close=1010, bar 5 close=1005. session_end at 6 bars.
        let session = make_session(
            0,
            6 * BAR_NS,
            6,
            &[
                (3 * BAR_NS, QuoteKind::SingleScientific, &[1000]),
                (4 * BAR_NS, QuoteKind::SingleScientific, &[1010]),
                (5 * BAR_NS, QuoteKind::SingleScientific, &[1005]),
            ],
        );
        let frame = scalar_frame(
            0,
            6 * BAR_NS,
            6,
            &[(3 * BAR_NS, 1000), (4 * BAR_NS, 1010), (5 * BAR_NS, 1005)],
            Vec::new(),
        );
        let rows = compute(&session, &frame);
        assert_eq!(rows.len(), 6);

        // Bars 0..=3: close is NO_QUOTE through bar 2, first defined at bar
        // 3 (carry-forward starts there); no valid diff can exist yet
        // (every diff needs BOTH endpoints defined) -> rv_count_5 == 0 at
        // bar 3.
        assert_eq!(rows[3].rv[0].count, 0); // W=5
        assert_eq!(rows[3].rv[0].sum_sq, Some(0));

        // Bar 4: one valid diff (bar3->bar4 = 1010-1000=10, sq=100); bar
        // 2->3 diff still invalid (bar 2 is NO_QUOTE).
        assert_eq!(rows[4].rv[0].count, 1);
        assert_eq!(rows[4].rv[0].sum_sq, Some(100));

        // Bar 5: two valid diffs: (1010-1000)^2=100, (1005-1010)^2=25 -> 125.
        assert_eq!(rows[5].rv[0].count, 2);
        assert_eq!(rows[5].rv[0].sum_sq, Some(125));
    }

    #[test]
    fn rv_window_causal_cap_at_session_start_holds_fewer_than_w_diffs() {
        // 4 bars, all quoted; W=60 at bar 3 can only ever see diffs for
        // i in [1,3] (capped at 1, not b-60+1 which would be negative).
        let session = make_session(
            0,
            4 * BAR_NS,
            4,
            &[
                (0, QuoteKind::SingleScientific, &[100]),
                (BAR_NS, QuoteKind::SingleScientific, &[110]),
                (2 * BAR_NS, QuoteKind::SingleScientific, &[105]),
                (3 * BAR_NS, QuoteKind::SingleScientific, &[120]),
            ],
        );
        let frame = scalar_frame(
            0,
            4 * BAR_NS,
            4,
            &[
                (0, 100),
                (BAR_NS, 110),
                (2 * BAR_NS, 105),
                (3 * BAR_NS, 120),
            ],
            Vec::new(),
        );
        let rows = compute(&session, &frame);
        // W=60 column is WINDOWS[2].
        assert_eq!(rows[3].rv[2].count, 3);
        // diffs: 10^2 + (-5)^2 + 15^2 = 100+25+225=350.
        assert_eq!(rows[3].rv[2].sum_sq, Some(350));
    }

    #[test]
    fn rv_sum_sq_overflow_is_a_typed_state_not_a_silent_wraparound() {
        // A single huge close jump: d ~ 4e9, d^2 ~ 1.6e19 > i64::MAX.
        let session = make_session(
            0,
            2 * BAR_NS,
            2,
            &[
                (0, QuoteKind::SingleScientific, &[0]),
                (BAR_NS, QuoteKind::SingleScientific, &[8_000_000_000]),
            ],
        );
        let frame = scalar_frame(
            0,
            2 * BAR_NS,
            2,
            &[(0, 0), (BAR_NS, 8_000_000_000)],
            Vec::new(),
        );
        let rows = compute(&session, &frame);
        assert_eq!(rows[1].rv[0].state, SumState::Overflow);
        assert_eq!(rows[1].rv[0].sum_sq, None);
        assert_eq!(rows[1].rv[0].count, 1);
    }

    // ------------------------- range_sum_sq / range_valid_count -------------------------

    #[test]
    fn range_window_excludes_a_bar_with_no_scientific_group_of_its_own() {
        // Bar 0: high=110/low=90 (range=20, sq=400). Bar 1: NO scientific
        // group at all (range NO_QUOTE), even though close carries forward.
        // Bar 2: high=105/low=95 (range=10, sq=100).
        let session = make_session(
            0,
            3 * BAR_NS,
            3,
            &[
                (10, QuoteKind::SingleScientific, &[90]),
                (20, QuoteKind::MultiScientific, &[90, 110]),
                (2 * BAR_NS + 10, QuoteKind::SingleScientific, &[95]),
                (2 * BAR_NS + 20, QuoteKind::MultiScientific, &[95, 105]),
            ],
        );
        // Frame's own scientific-path projection needs m_lo/m_hi per group;
        // build it directly (not via scalar_frame) since bar 0/2 groups are
        // heterogeneous-shaped for the range but we only need m_lo/m_hi
        // bounds, so encode each raw group as one frame entry with its own
        // lo/hi.
        let frame = {
            let mut f = SessionFrame::from_parts_for_test(
                0,
                3 * BAR_NS,
                vec![10, 20, 2 * BAR_NS + 10, 2 * BAR_NS + 20],
                vec![90, 90, 95, 95],
                vec![90, 110, 95, 105],
                vec![
                    GroupKind::Scalar,
                    GroupKind::Heterogeneous,
                    GroupKind::Scalar,
                    GroupKind::Heterogeneous,
                ],
                Vec::new(),
            );
            f.expected_bar_count = 3;
            f
        };
        let rows = compute(&session, &frame);
        assert_eq!(rows[0].range[0].count, 1); // W=5
        assert_eq!(rows[0].range[0].sum_sq, Some(400));
        assert_eq!(rows[1].scientific_group_count, 0);
        assert_eq!(rows[1].range[0].count, 1); // only bar 0 contributes in [max(0,1-4),1]
        assert_eq!(rows[2].range[0].count, 2); // bars 0 and 2 (bar 1 excluded)
        assert_eq!(rows[2].range[0].sum_sq, Some(400 + 100));
    }

    // ------------------------- band / net-move -------------------------

    #[test]
    fn band_u6_30_hand_computed_across_a_short_causal_window() {
        // 3 quoted bars: highs/lows (110/90), (130/70), (105/95).
        // band at bar 2 = max(110,130,105) - min(90,70,95) = 130-70=60.
        let session = make_session(
            0,
            3 * BAR_NS,
            3,
            &[
                (0, QuoteKind::MultiScientific, &[90, 110]),
                (BAR_NS, QuoteKind::MultiScientific, &[70, 130]),
                (2 * BAR_NS, QuoteKind::MultiScientific, &[95, 105]),
            ],
        );
        let frame = {
            let mut f = SessionFrame::from_parts_for_test(
                0,
                3 * BAR_NS,
                vec![0, BAR_NS, 2 * BAR_NS],
                vec![90, 70, 95],
                vec![110, 130, 105],
                vec![GroupKind::Heterogeneous; 3],
                Vec::new(),
            );
            f.expected_bar_count = 3;
            f
        };
        let rows = compute(&session, &frame);
        assert_eq!(rows[2].band_u6_30.state, BandState::Ok);
        assert_eq!(rows[2].band_u6_30.value_u6, Some(60));
        // At bar 0, only that bar contributes: band = 110-90=20.
        assert_eq!(rows[0].band_u6_30.value_u6, Some(20));
    }

    #[test]
    fn band_u6_30_no_data_when_the_causal_window_has_zero_valid_bars() {
        // A session-wide liquidity desert (zero scientific groups ever) is
        // unreachable through `compute` for any REAL session
        // (`SessionFrame::build` panics on zero scientific-path groups), so
        // `band_at`'s `NoData` branch is exercised directly against a
        // synthetic all-`NO_QUOTE` bar array instead of through `compute`.
        let prices: Vec<BarPrice> = vec![BarPrice {
            close_u6: None,
            high_u6: None,
            low_u6: None,
            scientific_group_count: 0,
        }];
        let band = band_at(&prices, 0);
        assert_eq!(band.state, BandState::NoData);
        assert_eq!(band.value_u6, None);
    }

    #[test]
    fn net_move_u6_30_insufficient_history_before_bar_30() {
        let session = make_session(
            0,
            5 * BAR_NS,
            5,
            &[(0, QuoteKind::SingleScientific, &[1000])],
        );
        let frame = scalar_frame(0, 5 * BAR_NS, 5, &[(0, 1000)], Vec::new());
        let rows = compute(&session, &frame);
        for row in &rows {
            assert_eq!(row.net_move_u6_30.state, NetMoveState::InsufficientHistory);
            assert_eq!(row.net_move_u6_30.value_u6, None);
        }
    }

    #[test]
    fn net_move_u6_30_hand_computed_at_exactly_lag_30() {
        // 31 bars; close constant 1000 at bar 0, jumps to 1200 at bar 30.
        let session = make_session(
            0,
            31 * BAR_NS,
            31,
            &[
                (0, QuoteKind::SingleScientific, &[1000]),
                (30 * BAR_NS, QuoteKind::SingleScientific, &[1200]),
            ],
        );
        let frame = scalar_frame(
            0,
            31 * BAR_NS,
            31,
            &[(0, 1000), (30 * BAR_NS, 1200)],
            Vec::new(),
        );
        let rows = compute(&session, &frame);
        assert_eq!(rows[30].net_move_u6_30.state, NetMoveState::Ok);
        // close[30]=1200, close[0]=1000 -> 200.
        assert_eq!(rows[30].net_move_u6_30.value_u6, Some(200));
    }

    #[test]
    fn net_move_u6_30_no_quote_when_the_lag_endpoint_predates_the_first_quote() {
        // First-ever quote arrives at bar 31 (so bar 1's lag endpoint, bar
        // 1-30 doesn't apply -- use bar 31: lag endpoint = bar 1, which is
        // NO_QUOTE since the first quote is at bar 31).
        let session = make_session(
            0,
            32 * BAR_NS,
            32,
            &[(31 * BAR_NS, QuoteKind::SingleScientific, &[1000])],
        );
        let frame = scalar_frame(0, 32 * BAR_NS, 32, &[(31 * BAR_NS, 1000)], Vec::new());
        let rows = compute(&session, &frame);
        assert_eq!(rows[31].net_move_u6_30.state, NetMoveState::NoQuote);
    }

    // ------------------------- breaker overlap flag -------------------------

    #[test]
    fn in_breaker_flags_only_bars_whose_span_overlaps_a_breaker() {
        // Breaker spans [90_000ms, 150_000ms) inside a 6-bar (0..360_000ms)
        // session at BAR_NS = 60_000_000_000ns = 60_000ms per bar. So
        // breaker = bar1(60k-120k) partial + bar2(120k-180k) partial.
        // bar 0 [0,60k): no overlap. bar1 [60k,120k): breaker starts at 90k
        // < 120k -> overlap. bar2 [120k,180k): breaker end 150k > 120k ->
        // overlap. bar3 [180k,240k): breaker ended at 150k <= 180k -> none.
        let breaker_start_ns = 90_000 * 1_000_000; // 90_000 ms
        let breaker_end_ns = 150_000 * 1_000_000; // 150_000 ms
        let session = make_session(
            0,
            6 * BAR_NS,
            6,
            &[(0, QuoteKind::SingleScientific, &[1000])],
        );
        let frame = scalar_frame(
            0,
            6 * BAR_NS,
            6,
            &[(0, 1000)],
            vec![Breaker {
                start_ns: breaker_start_ns,
                end_ns: breaker_end_ns,
            }],
        );
        let rows = compute(&session, &frame);
        assert!(!rows[0].in_breaker);
        assert!(rows[1].in_breaker);
        assert!(rows[2].in_breaker);
        assert!(!rows[3].in_breaker);
        assert!(!rows[4].in_breaker);
        assert!(!rows[5].in_breaker);
    }

    #[test]
    fn in_breaker_false_for_every_bar_on_a_no_breaker_day() {
        let session = make_session(
            0,
            3 * BAR_NS,
            3,
            &[(0, QuoteKind::SingleScientific, &[1000])],
        );
        let frame = scalar_frame(0, 3 * BAR_NS, 3, &[(0, 1000)], Vec::new());
        let rows = compute(&session, &frame);
        assert!(rows.iter().all(|r| !r.in_breaker));
    }

    // ------------------------- early-close bar count / clock -------------------------

    #[test]
    fn early_close_session_emits_exactly_210_rows_with_the_registered_clock() {
        let session = make_session(
            0,
            210 * BAR_NS,
            210,
            &[(0, QuoteKind::SingleScientific, &[1000])],
        );
        let frame = scalar_frame(0, 210 * BAR_NS, 210, &[(0, 1000)], Vec::new());
        let rows = compute(&session, &frame);
        assert_eq!(rows.len(), 210);
        assert!(rows.iter().all(|r| r.early_close));
        assert_eq!(rows[0].bar_ordinal, 0);
        assert_eq!(rows[0].bars_remaining, 209);
        assert_eq!(rows[209].bar_ordinal, 209);
        assert_eq!(rows[209].bars_remaining, 0);
    }

    #[test]
    fn normal_session_early_close_is_false() {
        let session = make_session(
            0,
            390 * BAR_NS,
            390,
            &[(0, QuoteKind::SingleScientific, &[1000])],
        );
        let frame = scalar_frame(0, 390 * BAR_NS, 390, &[(0, 1000)], Vec::new());
        let rows = compute(&session, &frame);
        assert_eq!(rows.len(), 390);
        assert!(rows.iter().all(|r| !r.early_close));
    }

    // ------------------------- liquidity counts (wide/unresolved/distinct) -------------------------

    #[test]
    fn liquidity_counts_hand_computed_with_distinct_midpoint_dedup_across_groups() {
        // Bar 0 (span [0, BAR_NS)) has: 1 SingleScientific group with
        // midpoint [100]; 1 MultiScientific group with midpoints [100, 105]
        // (100 repeats -> dedup across groups); 2 WideOnly groups; 1
        // Unresolved group.
        let session = make_session(
            0,
            2 * BAR_NS,
            2,
            &[
                (10, QuoteKind::SingleScientific, &[100]),
                (20, QuoteKind::MultiScientific, &[100, 105]),
                (30, QuoteKind::WideOnly, &[]),
                (40, QuoteKind::WideOnly, &[]),
                (50, QuoteKind::Unresolved, &[]),
            ],
        );
        let frame = scalar_frame(0, 2 * BAR_NS, 2, &[(10, 100), (20, 100)], Vec::new());
        let rows = compute(&session, &frame);
        assert_eq!(rows[0].wide_only_group_count, 2);
        assert_eq!(rows[0].unresolved_group_count, 1);
        // distinct scientific midpoints across the bar: {100, 105} -> 2
        // (NOT 100+105 double counted, and NOT the frame's own
        // scientific_group_count of 2 groups).
        assert_eq!(rows[0].distinct_scientific_midpoint_count, 2);
        assert_eq!(rows[1].wide_only_group_count, 0);
        assert_eq!(rows[1].unresolved_group_count, 0);
        assert_eq!(rows[1].distinct_scientific_midpoint_count, 0);
    }

    // ------------------------- write_tsv shape -------------------------

    #[test]
    fn write_tsv_header_and_rows_have_the_registered_column_count() {
        let session = make_session(
            0,
            3 * BAR_NS,
            3,
            &[(0, QuoteKind::SingleScientific, &[1000])],
        );
        let frame = scalar_frame(0, 3 * BAR_NS, 3, &[(0, 1000)], Vec::new());
        let path = std::env::temp_dir().join(format!(
            "regimes_test_write_tsv_shape_{}.tsv",
            std::process::id()
        ));
        write_tsv(&session, &frame, &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        std::fs::remove_file(&path).ok();

        let mut lines = content.lines();
        let header_line = lines.next().expect("header line");
        let header_cols: Vec<&str> = header_line.split('\t').collect();
        // day, bar_ordinal (2) + 3*3 rv + 3*3 range (18) + band(2) +
        // net_move(2) + 5 liq + bars_remaining + early_close (7) = 31.
        assert_eq!(header_cols.len(), 2 + 9 + 9 + 2 + 2 + 5 + 2);
        assert_eq!(header_cols[0], "day");
        assert_eq!(header_cols[1], "bar_ordinal");
        assert_eq!(header_cols[header_cols.len() - 1], "early_close");

        let rows: Vec<&str> = lines.collect();
        assert_eq!(rows.len(), 3);
        for row in &rows {
            assert_eq!(row.split('\t').count(), header_cols.len());
        }
        // Row order is ascending bar_ordinal.
        assert_eq!(rows[0].split('\t').nth(1), Some("0"));
        assert_eq!(rows[1].split('\t').nth(1), Some("1"));
        assert_eq!(rows[2].split('\t').nth(1), Some("2"));
    }

    // ------------------------------ real day (smoke) --------------------------------

    #[test]
    fn real_session_regime_table_has_expected_bar_count_rows_and_no_panics() {
        let root = std::path::PathBuf::from("/workspace/data/tokens/stock_quotes/IWM");
        if !root.is_dir() {
            eprintln!("skipping: corpus root {} is not mounted", root.display());
            return;
        }
        let session = corpus::load_session("2022-01-03", &root).expect("real session decodes");
        let frame = SessionFrame::build(&session);
        let rows = compute(&session, &frame);
        assert_eq!(rows.len(), usize::from(session.expected_bar_count));
        // Row-count identity (schema "Row count identity"): every row
        // present, ascending.
        for (index, row) in rows.iter().enumerate() {
            assert_eq!(row.bar_ordinal, i64::try_from(index).unwrap());
        }
        // By the end of a real trading day, some bar must have had at
        // least one scientific-path group (frame is nonempty by
        // construction), so close-derived quantities can't ALL be
        // NO_QUOTE-equivalent for the whole day.
        assert!(rows.iter().any(|r| r.scientific_group_count > 0));
    }
}
