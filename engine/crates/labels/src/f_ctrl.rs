//! F-CTRL — trend-scanning + triple-barrier controls (EVENTS.3 §11.3). Design
//! authority: `docs/specs/events3_design_v1.md` (F-CTRL, brief-level scope)
//! and `docs/specs/events3_formula_addendum_v1.md` §2 (exact numerics),
//! **CORRECTED by** `docs/specs/events3_design_amendment_v2.md` §A6
//! (trend-scanning `first_forward_bar` + censoring; A6 wins any conflict with
//! addendum §2). Schema (this family's own architect-reviewable appendix to
//! `label_probe_schema_v1.md`): `docs/specs/family_schemas/f_ctrl_schema_v1.md`
//! — read it for the exact column list and state precedence; this module
//! implements it verbatim.
//!
//! Kernel cost per anchor: 9 triple-barrier cells, each one
//! [`crate::f_pass::passage_at_threshold`] call (≤ 2
//! [`crate::extrema::ExtremaTree`] descents) plus one
//! [`crate::frame::SessionFrame::end_position`] descent for its own
//! `V`-bounded window end — all O(log n) — plus up to 4 trend-scanning
//! windows sharing a single, monotonically-extended cache of ≤ 40 (`=
//! max(L)`, never a function of window size) bar-close
//! [`crate::frame::SessionFrame::end_position`] descents, plus one shared
//! [`crate::frame::SessionFrame::first_breaker_start_after`] descent per row.
//! O(log n) per anchor overall — never an O(window) scan.

use crate::anchor::{Side, SignalSeed, Slot, SlotRow, WindowFrontier};
use crate::f_pass::{self, ThresholdTouch, TouchState};
use crate::frame::SessionFrame;
use std::fmt::Write as _;
use std::fs::File;
use std::io::{self, BufWriter, Write as _};
use std::path::Path;

/// Registered one-minute bar duration in nanoseconds (CONV §3), matching
/// every other family module's own local copy (`anchor.rs`'s constant is
/// private to that module).
const NANOSECONDS_PER_BAR: i64 = 60_000_000_000;

/// The three registered triple-barrier bps thresholds (ladder subset;
/// addendum §2), in column order.
pub const BARRIER_BPS: [u16; 3] = [20, 40, 80];

/// The three registered triple-barrier vertical horizons, in whole
/// one-minute bars (addendum §2), in column order.
pub const VERTICAL_BARS: [i64; 3] = [30, 60, 120];

/// The four registered trend-scanning forward-window lengths, in whole
/// one-minute bars (addendum §2 / amendment §A6), in column order.
pub const TREND_BARS: [i64; 4] = [5, 10, 20, 40];

// ============================== Triple barrier ==============================

/// One triple-barrier cell's outcome state
/// (`docs/specs/family_schemas/f_ctrl_schema_v1.md` §A, precedence order
/// documented there): an out-of-domain level outranks everything; a real
/// touch on either side outranks censoring; only when neither side touched
/// does the cell's own window frontier qualify the outcome.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum BarrierState {
    OutOfDomain,
    FavFirst,
    AdvFirst,
    SameGroupAmbiguous,
    SourceCensored,
    WideBreaker,
    OfficialCloseTruncated,
    Vertical,
}

impl BarrierState {
    /// The wire string for `tb_<N>_<V>_state`.
    #[must_use]
    pub const fn wire(self) -> &'static str {
        match self {
            Self::OutOfDomain => "OUT_OF_DOMAIN",
            Self::FavFirst => "FAV_FIRST",
            Self::AdvFirst => "ADV_FIRST",
            Self::SameGroupAmbiguous => "SAME_GROUP_AMBIGUOUS",
            Self::SourceCensored => "SOURCE_CENSORED",
            Self::WideBreaker => "WIDE_BREAKER",
            Self::OfficialCloseTruncated => "OFFICIAL_CLOSE_TRUNCATED",
            Self::Vertical => "VERTICAL",
        }
    }
}

/// One triple-barrier cell's full published row (`f_ctrl_schema_v1.md` §A):
/// the state plus the winning touch's group index/timestamp/kind (touch
/// states only) or the `VERTICAL` terminal signed move interval (`VERTICAL`
/// only) — the other payload is always all-`NA` for a given state.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct BarrierResult {
    pub state: BarrierState,
    pub touch_index: Option<usize>,
    pub touch_ts_ns: Option<i64>,
    pub touch_group_kind: Option<&'static str>,
    pub term_move_lo_u6: Option<i64>,
    pub term_move_hi_u6: Option<i64>,
    pub term_group_kind: Option<&'static str>,
}

impl BarrierResult {
    /// A state with no touch/terminal payload (every non-touch, non-`VERTICAL`
    /// state: `OUT_OF_DOMAIN`, `SOURCE_CENSORED`, `WIDE_BREAKER`,
    /// `OFFICIAL_CLOSE_TRUNCATED`).
    const fn bare(state: BarrierState) -> Self {
        Self {
            state,
            touch_index: None,
            touch_ts_ns: None,
            touch_group_kind: None,
            term_move_lo_u6: None,
            term_move_hi_u6: None,
            term_group_kind: None,
        }
    }

    /// A touch state (`FAV_FIRST`/`ADV_FIRST`/`SAME_GROUP_AMBIGUOUS`): reuses
    /// the winning [`ThresholdTouch`]'s already-resolved index/timestamp/kind
    /// verbatim — no re-derivation, no new scan.
    ///
    /// # Panics
    ///
    /// Panics if `touch` carries no index/timestamp — unreachable for any
    /// caller here, which only ever passes the `fav`/`adv` touch that
    /// [`compute_barrier_cell`]'s own index-tuple match has just proven is
    /// `Some`.
    fn touch(state: BarrierState, touch: &ThresholdTouch) -> Self {
        let index = touch
            .index
            .expect("a touching BarrierState's ThresholdTouch always carries an index");
        let ts_ns = touch
            .ts_ns
            .expect("a touching BarrierState's ThresholdTouch always carries a timestamp");
        Self {
            state,
            touch_index: Some(index),
            touch_ts_ns: Some(ts_ns),
            touch_group_kind: Some(touch_group_kind_wire(touch.state)),
            term_move_lo_u6: None,
            term_move_hi_u6: None,
            term_group_kind: None,
        }
    }

    /// The `VERTICAL` state: the terminal signed move interval from the last
    /// scientific-path group in the cell's own window, identical convention
    /// to `f_term.tsv`'s `term_<H>_move_lo/hi_u6` (`f_ctrl_schema_v1.md` §A).
    fn vertical(
        frame: &SessionFrame,
        side: Side,
        pivot_price_u6: i64,
        terminal_index: usize,
    ) -> Self {
        let price_lo = frame.m_lo[terminal_index];
        let price_hi = frame.m_hi[terminal_index];
        let (move_lo, move_hi) = match side {
            Side::Low => (price_lo - pivot_price_u6, price_hi - pivot_price_u6),
            Side::High => (pivot_price_u6 - price_hi, pivot_price_u6 - price_lo),
        };
        Self {
            state: BarrierState::Vertical,
            touch_index: None,
            touch_ts_ns: None,
            touch_group_kind: None,
            term_move_lo_u6: Some(move_lo),
            term_move_hi_u6: Some(move_hi),
            term_group_kind: Some(frame.kind[terminal_index].wire()),
        }
    }
}

/// Maps a touching [`TouchState`] to the `_group_kind` wire string
/// (`SCALAR`/`HETEROGENEOUS`, `frame::GroupKind`'s own wire values) —
/// `Exact` came from a `Scalar` group, `IntervalAmbiguous` from a
/// `Heterogeneous` one (CONV §7 tie rule, mirrored verbatim by
/// `f_pass::group_touch_state`, which this reuses transitively).
///
/// # Panics
///
/// Panics on [`TouchState::NotTouched`] / [`TouchState::OutOfDomain`] —
/// unreachable here: every call site only passes the touch of an
/// already-confirmed touching state.
#[must_use]
fn touch_group_kind_wire(state: TouchState) -> &'static str {
    match state {
        TouchState::Exact => "SCALAR",
        TouchState::IntervalAmbiguous => "HETEROGENEOUS",
        TouchState::NotTouched | TouchState::OutOfDomain => {
            unreachable!("touch_group_kind_wire called on a non-touching TouchState: {state:?}")
        }
    }
}

/// Computes one triple-barrier cell (`f_ctrl_schema_v1.md` §A): resolves the
/// cell's own `V`-bounded window (breaker/close-censored, sharing
/// `ctx.breaker_start`), scans it via [`f_pass::passage_at_threshold`]
/// (identical inclusive touch logic to F-PASS, "no new scans"), then applies
/// the registered precedence (out-of-domain > touch > censoring) exactly
/// like `f_ord::ord_state_at`'s established index-tuple dispatch.
///
/// O(log n): one [`SessionFrame::end_position`] descent plus
/// [`f_pass::passage_at_threshold`]'s own ≤ 2 descents.
fn compute_barrier_cell(ctx: &RowContext<'_>, bps: u16, v_bars: i64) -> BarrierResult {
    let nominal_end_ns = ctx
        .cutoff_ts_ns
        .checked_add(
            v_bars
                .checked_mul(NANOSECONDS_PER_BAR)
                .expect("vertical horizon arithmetic overflowed i64"),
        )
        .expect("vertical horizon arithmetic overflowed i64");
    let (window_end, frontier) = cell_frontier(
        ctx.frame,
        ctx.window_left,
        nominal_end_ns,
        ctx.breaker_start,
    );

    let result = f_pass::passage_at_threshold(
        ctx.frame,
        ctx.side,
        ctx.pivot_price_u6,
        bps,
        ctx.window_left,
        window_end,
    );

    if result.fav.state == TouchState::OutOfDomain || result.adv.state == TouchState::OutOfDomain {
        return BarrierResult::bare(BarrierState::OutOfDomain);
    }
    match (result.fav.index, result.adv.index) {
        (Some(f), Some(a)) if f == a => {
            BarrierResult::touch(BarrierState::SameGroupAmbiguous, &result.fav)
        }
        (Some(f), Some(a)) if f < a => BarrierResult::touch(BarrierState::FavFirst, &result.fav),
        (Some(_) | None, Some(_)) => BarrierResult::touch(BarrierState::AdvFirst, &result.adv),
        (Some(_), None) => BarrierResult::touch(BarrierState::FavFirst, &result.fav),
        (None, None) => match frontier {
            WindowFrontier::Complete => {
                BarrierResult::vertical(ctx.frame, ctx.side, ctx.pivot_price_u6, window_end - 1)
            }
            WindowFrontier::WideBreaker => BarrierResult::bare(BarrierState::WideBreaker),
            WindowFrontier::OfficialCloseTruncated => {
                BarrierResult::bare(BarrierState::OfficialCloseTruncated)
            }
            WindowFrontier::SourceCensored => BarrierResult::bare(BarrierState::SourceCensored),
            WindowFrontier::DecisionUnavailable | WindowFrontier::NotVisible => {
                unreachable!("cell_frontier never returns a row-level-only frontier")
            }
        },
    }
}

/// Resolves one cell's own `[window_left, window_end)` and
/// [`WindowFrontier`], generalizing `SlotRow::compute`'s window-resolution
/// rule (`label_probe_schema_v1.md` "Family-file common prefix") to an
/// arbitrary per-cell `nominal_end_ns` instead of the row's own
/// close-bounded one. Shared by every triple-barrier cell (`V`-bounded).
///
/// O(log n): one [`SessionFrame::end_position`] descent (`breaker_start` is
/// computed once per row by the caller and passed in, not re-queried here).
fn cell_frontier(
    frame: &SessionFrame,
    window_left: usize,
    nominal_end_ns: i64,
    breaker_start: Option<i64>,
) -> (usize, WindowFrontier) {
    let requested_end_ns = nominal_end_ns.min(frame.session_end_ns);
    let bound = breaker_start.map_or(requested_end_ns, |start| start.min(requested_end_ns));
    let window_end = frame.end_position(bound);
    let frontier = if window_left >= window_end {
        WindowFrontier::SourceCensored
    } else if breaker_start.is_some_and(|start| start < requested_end_ns) {
        WindowFrontier::WideBreaker
    } else if nominal_end_ns > frame.session_end_ns {
        WindowFrontier::OfficialCloseTruncated
    } else {
        WindowFrontier::Complete
    };
    (window_end, frontier)
}

// ============================== Trend scanning ==============================

/// One trend-scanning window's censoring/completion state
/// (`f_ctrl_schema_v1.md` §B).
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TrendState {
    WideBreaker,
    OfficialCloseTruncated,
    NoQuote,
    Overflow,
    Complete,
}

impl TrendState {
    /// The wire string for `trend_<L>_state`.
    #[must_use]
    pub const fn wire(self) -> &'static str {
        match self {
            Self::WideBreaker => "WIDE_BREAKER",
            Self::OfficialCloseTruncated => "OFFICIAL_CLOSE_TRUNCATED",
            Self::NoQuote => "NO_QUOTE",
            Self::Overflow => "OVERFLOW",
            Self::Complete => "COMPLETE",
        }
    }
}

/// The registered control sign (addendum §2 / amendment §A6):
/// `sign(n·Σxy − Σx·Σy)`.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TrendSign {
    Up,
    Down,
    Flat,
}

impl TrendSign {
    /// The wire string for `trend_<L>_sign`.
    #[must_use]
    pub const fn wire(self) -> &'static str {
        match self {
            Self::Up => "UP",
            Self::Down => "DOWN",
            Self::Flat => "FLAT",
        }
    }
}

/// One trend-scanning window's full published row (`f_ctrl_schema_v1.md`
/// §B): the OLS sufficient statistics `n, sum_y, sum_xy, sum_y2` plus the
/// registered sign, published only when `state == Complete`.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct TrendResult {
    pub state: TrendState,
    pub n: Option<i64>,
    pub sum_y: Option<i64>,
    pub sum_xy: Option<i64>,
    pub sum_y2: Option<i64>,
    pub sign: Option<TrendSign>,
}

impl TrendResult {
    const fn censored(state: TrendState) -> Self {
        Self {
            state,
            n: None,
            sum_y: None,
            sum_xy: None,
            sum_y2: None,
            sign: None,
        }
    }

    /// Computes the full OLS sufficient-statistic contract for one complete
    /// `L`-bar window from its already-resolved bar closes (`closes[0..l]`,
    /// `closes[0]` = the baseline `close_u6[first_forward_bar]`): `x_i = i`,
    /// `y_i = closes[i] - closes[0]` (addendum §2, amendment §A6). `i128`
    /// accumulation guards `sum_y`/`sum_xy`/`sum_y2` against silent overflow
    /// — [`TrendState::Overflow`] (all `NA`) if any does not fit `i64`.
    ///
    /// # Panics
    ///
    /// Panics if `closes.len() != l as usize` — an internal-invariant bug in
    /// [`compute_trend_row`], the only caller, never a data condition.
    #[allow(
        clippy::similar_names,
        reason = "sum_y/sum_xy/sum_y2 are the registered addendum §2 column names verbatim; \
                  renaming them internally would sever the doc/schema traceability"
    )]
    fn from_closes(l: i64, closes: &[i64]) -> Self {
        assert_eq!(
            closes.len(),
            usize::try_from(l).expect("l is a small positive constant"),
            "from_closes: caller must supply exactly l resolved bar closes"
        );
        let base = closes[0];
        let mut sum_y: i128 = 0;
        let mut sum_xy: i128 = 0;
        let mut sum_y2: i128 = 0;
        for (i, &close) in closes.iter().enumerate() {
            let y = i128::from(close) - i128::from(base);
            let x = i128::try_from(i).expect("window index fits in i128");
            sum_y += y;
            sum_xy += x * y;
            sum_y2 += y * y;
        }
        let (Ok(sum_y_i64), Ok(sum_xy_i64), Ok(sum_y2_i64)) = (
            i64::try_from(sum_y),
            i64::try_from(sum_xy),
            i64::try_from(sum_y2),
        ) else {
            return Self::censored(TrendState::Overflow);
        };
        let sum_x: i128 = i128::from(l) * i128::from(l - 1) / 2;
        let numerator = i128::from(l) * sum_xy - sum_x * sum_y;
        let sign = match numerator.cmp(&0) {
            std::cmp::Ordering::Greater => TrendSign::Up,
            std::cmp::Ordering::Less => TrendSign::Down,
            std::cmp::Ordering::Equal => TrendSign::Flat,
        };
        Self {
            state: TrendState::Complete,
            n: Some(l),
            sum_y: Some(sum_y_i64),
            sum_xy: Some(sum_xy_i64),
            sum_y2: Some(sum_y2_i64),
            sign: Some(sign),
        }
    }
}

/// `close_u6[bar_ordinal]` (`f_ctrl_schema_v1.md` §B, formula addendum §1):
/// the representative price of the LAST scientific-path group with `ts_ns <
/// bar_end_ns(bar_ordinal)`; `None` (`NO_QUOTE`) if no such group exists
/// anywhere in the frame. The representative price is `(m_lo + m_hi) / 2`
/// (`i128`, floor) — exact for a `Scalar` group, the schema doc's documented
/// reading ("m-mid") for a `Heterogeneous` one.
///
/// O(log n): one [`SessionFrame::end_position`] descent.
///
/// # Panics
///
/// Panics if `bar_ordinal` arithmetic overflows `i64`, or if the resolved
/// group's midpoint average does not fit `i64` — unreachable for any
/// registered session (bar ordinals are bounded by `expected_bar_count`;
/// prices are many orders of magnitude under `i64::MAX / 2`).
fn bar_close_u6(frame: &SessionFrame, bar_ordinal: i64) -> Option<i64> {
    let bar_end_ns = bar_ordinal
        .checked_add(1)
        .and_then(|b| b.checked_mul(NANOSECONDS_PER_BAR))
        .and_then(|offset| frame.session_start_ns.checked_add(offset))
        .expect("bar_end_ns arithmetic overflowed i64");
    let position = frame.end_position(bar_end_ns);
    if position == 0 {
        return None;
    }
    let index = position - 1;
    let mid = i128::midpoint(i128::from(frame.m_lo[index]), i128::from(frame.m_hi[index]));
    Some(i64::try_from(mid).expect("group midpoint average fits in i64 for any registered price"))
}

/// Checks whether `l` whole forward bars from the row's `first_forward_bar`
/// fit fully inside the close/breaker-bounded window (amendment §A6);
/// `Ok(())` if so, else the typed censoring reason.
///
/// O(1) given the shared `breaker_start` (no descent of its own).
fn bars_available(
    cutoff_ts_ns: i64,
    session_end_ns: i64,
    breaker_start: Option<i64>,
    l: i64,
) -> Result<(), TrendState> {
    let nominal_end_ns = cutoff_ts_ns
        .checked_add(
            l.checked_mul(NANOSECONDS_PER_BAR)
                .expect("trend horizon arithmetic overflowed i64"),
        )
        .expect("trend horizon arithmetic overflowed i64");
    let requested_end_ns = nominal_end_ns.min(session_end_ns);
    let bound = breaker_start.map_or(requested_end_ns, |start| start.min(requested_end_ns));
    let available_bars = (bound - cutoff_ts_ns) / NANOSECONDS_PER_BAR;
    if available_bars >= l {
        Ok(())
    } else if breaker_start.is_some_and(|start| start < requested_end_ns) {
        Err(TrendState::WideBreaker)
    } else {
        Err(TrendState::OfficialCloseTruncated)
    }
}

/// Computes all four trend-scanning windows for one row (`f_ctrl_schema_v1.md`
/// §B): shares one growing `closes` cache across ascending `L` (`TREND_BARS`
/// is ascending), so each bar close is resolved at most once regardless of
/// how many `L`s need it.
///
/// O(≤ 40) [`bar_close_u6`] descents total (the constant `40 = max(L)`, never
/// a function of window size) plus O(1) work per `L`.
fn compute_trend_row(ctx: &RowContext<'_>) -> Vec<TrendResult> {
    let offset = ctx.cutoff_ts_ns - ctx.frame.session_start_ns;
    debug_assert_eq!(
        offset % NANOSECONDS_PER_BAR,
        0,
        "cutoff_ts_ns must be bar-aligned (SlotRow::compute's own invariant)"
    );
    let first_forward_bar = offset / NANOSECONDS_PER_BAR;

    let baseline = bar_close_u6(ctx.frame, first_forward_bar);
    let mut closes: Vec<i64> = Vec::new();
    if let Some(base) = baseline {
        closes.push(base);
    }

    TREND_BARS
        .into_iter()
        .map(|l| {
            match bars_available(
                ctx.cutoff_ts_ns,
                ctx.frame.session_end_ns,
                ctx.breaker_start,
                l,
            ) {
                Err(state) => TrendResult::censored(state),
                Ok(()) if baseline.is_none() => TrendResult::censored(TrendState::NoQuote),
                Ok(()) => {
                    let l_usize = usize::try_from(l).expect("L is a small positive constant");
                    while closes.len() < l_usize {
                        let next_bar = first_forward_bar
                            + i64::try_from(closes.len())
                                .expect("closes.len() fits in i64 for L <= 40");
                        let close = bar_close_u6(ctx.frame, next_bar).expect(
                            "close_u6 is defined for every later bar once the baseline bar has a \
                             quote (SessionFrame::end_position is non-decreasing in its bound)",
                        );
                        closes.push(close);
                    }
                    TrendResult::from_closes(l, &closes[..l_usize])
                }
            }
        })
        .collect()
}

// ============================== Shared row context ==============================

/// Bundles the per-row values shared by every triple-barrier cell and every
/// trend-scanning window: the resolved cutoff/side/anchor price, the row's
/// own `window_left` (common to all 9 barrier cells — it depends only on
/// `cutoff_ts_ns`, never on `V`), and the ONE shared breaker query
/// (`SessionFrame::first_breaker_start_after`, computed once and reused by
/// all 13 sub-computations — matching `f_term::HorizonContext`'s sharing
/// pattern).
struct RowContext<'a> {
    frame: &'a SessionFrame,
    side: Side,
    pivot_price_u6: i64,
    cutoff_ts_ns: i64,
    window_left: usize,
    breaker_start: Option<i64>,
}

// ============================== TSV assembly ==============================

/// The ten-column common prefix, identical to every other family file.
const PREFIX_HEADER: &str = "day\tsignal_id\tslot\tseed_bar_ordinal\tcutoff_ts_ns\tslot_available\tvisible_at_slot\twindow_left\twindow_end\twindow_frontier";

/// The `f_ctrl.tsv` header: the common prefix, 9 × 7 triple-barrier columns
/// (`N` major, `V` minor), then 4 × 6 trend-scanning columns
/// (`f_ctrl_schema_v1.md`).
#[must_use]
pub fn header() -> String {
    let mut out = PREFIX_HEADER.to_owned();
    for bps in BARRIER_BPS {
        for v in VERTICAL_BARS {
            write!(
                out,
                "\ttb_{bps}_{v}_state\ttb_{bps}_{v}_touch_index\ttb_{bps}_{v}_touch_ts_ns\t\
                 tb_{bps}_{v}_touch_group_kind\ttb_{bps}_{v}_term_move_lo_u6\t\
                 tb_{bps}_{v}_term_move_hi_u6\ttb_{bps}_{v}_term_group_kind"
            )
            .expect("writing to a String cannot fail");
        }
    }
    for l in TREND_BARS {
        write!(
            out,
            "\ttrend_{l}_state\ttrend_{l}_n\ttrend_{l}_sum_y\ttrend_{l}_sum_xy\t\
             trend_{l}_sum_y2\ttrend_{l}_sign"
        )
        .expect("writing to a String cannot fail");
    }
    out
}

/// Appends one triple-barrier cell's 7 value columns, tab-prefixed.
fn push_barrier_columns(line: &mut String, r: &BarrierResult) {
    write!(line, "\t{}", r.state.wire()).expect("writing to a String cannot fail");
    match (r.touch_index, r.touch_ts_ns, r.touch_group_kind) {
        (Some(index), Some(ts_ns), Some(kind)) => write!(line, "\t{index}\t{ts_ns}\t{kind}"),
        _ => write!(line, "\tNA\tNA\tNA"),
    }
    .expect("writing to a String cannot fail");
    match (r.term_move_lo_u6, r.term_move_hi_u6, r.term_group_kind) {
        (Some(lo), Some(hi), Some(kind)) => write!(line, "\t{lo}\t{hi}\t{kind}"),
        _ => write!(line, "\tNA\tNA\tNA"),
    }
    .expect("writing to a String cannot fail");
}

/// Appends one trend-scanning window's 6 value columns, tab-prefixed.
fn push_trend_columns(line: &mut String, r: &TrendResult) {
    write!(line, "\t{}", r.state.wire()).expect("writing to a String cannot fail");
    for value in [r.n, r.sum_y, r.sum_xy, r.sum_y2] {
        match value {
            Some(v) => write!(line, "\t{v}"),
            None => write!(line, "\tNA"),
        }
        .expect("writing to a String cannot fail");
    }
    match r.sign {
        Some(sign) => write!(line, "\t{}", sign.wire()),
        None => write!(line, "\tNA"),
    }
    .expect("writing to a String cannot fail");
}

/// Computes every `(signal, slot)` row as one tab-joined line, no header, no
/// trailing newline: one row per `(signal, slot)`, slots in order `D1, D2,
/// D3` (slot-minor), signals in the order given by `seeds`
/// (`docs/specs/label_probe_schema_v1.md` "Family-file common prefix").
/// Reusable in-memory (e.g. for parquet publication) without going through
/// [`write_tsv`]'s file.
///
/// Rows whose window frontier is `DECISION_UNAVAILABLE`/`NOT_VISIBLE` carry
/// literal `NA` in all 87 value columns (`f_ctrl_schema_v1.md`'s row-level
/// rule); every other row computes all 9 triple-barrier cells and all 4
/// trend-scanning windows independently.
///
/// O(`seeds.len()` × 3 slots × (9 barrier cells + ≤ 40 bar-close descents)),
/// each descent O(log n) — see the module doc comment for the full budget.
///
/// # Panics
///
/// Panics if a row's window frontier is neither `DECISION_UNAVAILABLE` nor
/// `NOT_VISIBLE` yet its `window_left` is absent — unreachable per
/// `SlotRow::compute`'s own invariant.
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
                for _ in 0..(BARRIER_BPS.len() * VERTICAL_BARS.len()) {
                    line.push_str("\tNA\tNA\tNA\tNA\tNA\tNA\tNA");
                }
                for _ in TREND_BARS {
                    line.push_str("\tNA\tNA\tNA\tNA\tNA\tNA");
                }
            } else {
                let ctx = RowContext {
                    frame,
                    side: seed.extreme_side,
                    pivot_price_u6: seed.pivot_price_u6,
                    cutoff_ts_ns: row.cutoff_ts_ns,
                    window_left: row
                        .window_left
                        .expect("window present when slot available and visible"),
                    breaker_start: frame.first_breaker_start_after(row.cutoff_ts_ns),
                };
                for bps in BARRIER_BPS {
                    for v in VERTICAL_BARS {
                        let result = compute_barrier_cell(&ctx, bps, v);
                        push_barrier_columns(&mut line, &result);
                    }
                }
                for result in compute_trend_row(&ctx) {
                    push_trend_columns(&mut line, &result);
                }
            }
            out.push(line);
        }
    }
    out
}

/// Writes `f_ctrl.tsv` for every `(signal, slot)` row ([`rows`]).
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

    const BAR_NS: i64 = NANOSECONDS_PER_BAR;

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

    // ============================ triple barrier ============================

    #[test]
    fn barrier_fav_first_within_v_window() {
        // P = 1_000_000; N=20bps => distance=2000; fav(LOW,up)=1_002_000,
        // adv(down)=998_000. Group at cutoff touches favorable only.
        let frame = SessionFrame::from_parts_for_test(
            0,
            200 * BAR_NS,
            vec![10 * BAR_NS],
            vec![999_000],
            vec![1_002_500],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let ctx = RowContext {
            frame: &frame,
            side: Side::Low,
            pivot_price_u6: 1_000_000,
            cutoff_ts_ns: 10 * BAR_NS,
            window_left: 0,
            breaker_start: None,
        };
        let result = compute_barrier_cell(&ctx, 20, 30);
        assert_eq!(result.state, BarrierState::FavFirst);
        assert_eq!(result.touch_index, Some(0));
        assert_eq!(result.touch_ts_ns, Some(10 * BAR_NS));
        assert_eq!(result.touch_group_kind, Some("SCALAR"));
        assert_eq!(result.term_move_lo_u6, None);
    }

    #[test]
    fn barrier_adv_first() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            200 * BAR_NS,
            vec![10 * BAR_NS],
            vec![997_000],
            vec![999_000],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let ctx = RowContext {
            frame: &frame,
            side: Side::Low,
            pivot_price_u6: 1_000_000,
            cutoff_ts_ns: 10 * BAR_NS,
            window_left: 0,
            breaker_start: None,
        };
        let result = compute_barrier_cell(&ctx, 20, 30);
        assert_eq!(result.state, BarrierState::AdvFirst);
        assert_eq!(result.touch_index, Some(0));
    }

    #[test]
    fn barrier_same_group_ambiguous_is_always_heterogeneous() {
        // A single Heterogeneous group whose m_lo <= adv_level(998_000) AND
        // m_hi >= fav_level(1_002_000) simultaneously: impossible for a
        // Scalar group (single value can't be on both sides of P at once).
        let frame = SessionFrame::from_parts_for_test(
            0,
            200 * BAR_NS,
            vec![10 * BAR_NS],
            vec![997_000],
            vec![1_003_000],
            vec![GroupKind::Heterogeneous],
            Vec::new(),
        );
        let ctx = RowContext {
            frame: &frame,
            side: Side::Low,
            pivot_price_u6: 1_000_000,
            cutoff_ts_ns: 10 * BAR_NS,
            window_left: 0,
            breaker_start: None,
        };
        let result = compute_barrier_cell(&ctx, 20, 30);
        assert_eq!(result.state, BarrierState::SameGroupAmbiguous);
        assert_eq!(result.touch_index, Some(0));
        assert_eq!(result.touch_group_kind, Some("HETEROGENEOUS"));
    }

    #[test]
    fn barrier_vertical_publishes_terminal_move_interval_at_exact_v_boundary() {
        // cutoff = 10 bars, V = 30 => nominal_end = 40 bars, session_end =
        // 200 bars (plenty). Groups flat at P (no touch) inside the window,
        // plus a group EXACTLY at the nominal end (40 bars) that WOULD touch
        // favorable if included -- it must be excluded (half-open window).
        let frame = SessionFrame::from_parts_for_test(
            0,
            200 * BAR_NS,
            vec![10 * BAR_NS, 39 * BAR_NS, 40 * BAR_NS],
            vec![1_000_000, 1_000_000, 999_000],
            vec![1_000_000, 1_000_000, 1_999_000],
            vec![GroupKind::Scalar; 3],
            Vec::new(),
        );
        let ctx = RowContext {
            frame: &frame,
            side: Side::Low,
            pivot_price_u6: 1_000_000,
            cutoff_ts_ns: 10 * BAR_NS,
            window_left: 0,
            breaker_start: None,
        };
        let result = compute_barrier_cell(&ctx, 20, 30);
        assert_eq!(result.state, BarrierState::Vertical);
        // Terminal group = index 1 (ts = 39 bars), excluding the boundary
        // group at exactly 40 bars.
        assert_eq!(result.term_move_lo_u6, Some(0));
        assert_eq!(result.term_move_hi_u6, Some(0));
        assert_eq!(result.term_group_kind, Some("SCALAR"));
    }

    #[test]
    fn barrier_official_close_truncated_when_v_exceeds_remaining_session() {
        // session_end at 20 bars; cutoff at 10 bars; V = 30 => nominal_end =
        // 40 bars, past the 20-bar close. No breaker, neither level touched.
        let frame = SessionFrame::from_parts_for_test(
            0,
            20 * BAR_NS,
            vec![10 * BAR_NS],
            vec![1_000_000],
            vec![1_000_000],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let ctx = RowContext {
            frame: &frame,
            side: Side::Low,
            pivot_price_u6: 1_000_000,
            cutoff_ts_ns: 10 * BAR_NS,
            window_left: 0,
            breaker_start: None,
        };
        let result = compute_barrier_cell(&ctx, 20, 30);
        assert_eq!(result.state, BarrierState::OfficialCloseTruncated);
        assert_eq!(result.term_move_lo_u6, None);
    }

    #[test]
    fn barrier_wide_breaker_when_breaker_interposes_before_neither_touches() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            200 * BAR_NS,
            vec![10 * BAR_NS],
            vec![1_000_000],
            vec![1_000_000],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let ctx = RowContext {
            frame: &frame,
            side: Side::Low,
            pivot_price_u6: 1_000_000,
            cutoff_ts_ns: 10 * BAR_NS,
            window_left: 0,
            breaker_start: Some(15 * BAR_NS), // before nominal_end (40 bars)
        };
        let result = compute_barrier_cell(&ctx, 20, 30);
        assert_eq!(result.state, BarrierState::WideBreaker);
    }

    #[test]
    fn barrier_touch_before_breaker_outranks_the_censor() {
        // The favorable touch happens at index 0 (before the breaker at 15
        // bars); the breaker exists but must not override an actual touch.
        let frame = SessionFrame::from_parts_for_test(
            0,
            200 * BAR_NS,
            vec![10 * BAR_NS],
            vec![999_000],
            vec![1_002_500],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let ctx = RowContext {
            frame: &frame,
            side: Side::Low,
            pivot_price_u6: 1_000_000,
            cutoff_ts_ns: 10 * BAR_NS,
            window_left: 0,
            breaker_start: Some(15 * BAR_NS),
        };
        let result = compute_barrier_cell(&ctx, 20, 30);
        assert_eq!(result.state, BarrierState::FavFirst);
    }

    #[test]
    fn barrier_source_censored_when_the_v_bounded_window_is_empty() {
        // No group at all inside [cutoff, nominal_end); a later group exists
        // but well past this V's own bound.
        let frame = SessionFrame::from_parts_for_test(
            0,
            200 * BAR_NS,
            vec![100 * BAR_NS],
            vec![1_000_000],
            vec![1_000_000],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let ctx = RowContext {
            frame: &frame,
            side: Side::Low,
            pivot_price_u6: 1_000_000,
            cutoff_ts_ns: 10 * BAR_NS,
            window_left: 0,
            breaker_start: None,
        };
        // V = 30 => nominal_end = 40 bars; the only group (100 bars) is well
        // past it, so window_end_V = 0 = window_left: empty.
        let result = compute_barrier_cell(&ctx, 20, 30);
        assert_eq!(result.state, BarrierState::SourceCensored);
    }

    #[test]
    fn barrier_out_of_domain_outranks_a_favorable_touch() {
        // anchor = 1 u6, N = 80: distance = max(1, ceil(80/10_000)) = 1;
        // adverse level (LOW => P - distance) = 1 - 1 = 0 <= 0: OUT_OF_DOMAIN,
        // even though the favorable side (P + 1 = 2) touches.
        let frame = SessionFrame::from_parts_for_test(
            0,
            200 * BAR_NS,
            vec![10 * BAR_NS],
            vec![0],
            vec![5],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let ctx = RowContext {
            frame: &frame,
            side: Side::Low,
            pivot_price_u6: 1,
            cutoff_ts_ns: 10 * BAR_NS,
            window_left: 0,
            breaker_start: None,
        };
        let result = compute_barrier_cell(&ctx, 80, 30);
        assert_eq!(result.state, BarrierState::OutOfDomain);
        assert_eq!(result.touch_index, None);
    }

    // ============================ trend scanning ============================

    #[test]
    fn trend_first_forward_bar_is_the_bar_starting_at_cutoff_not_skipped() {
        // Hand-computed L=5 OLS sufficient statistics using bar closes at
        // the cutoff bar itself (NOT cutoff_bar + 1): closes =
        // [1000, 1010, 1005, 1020, 1000] at bars 10..14 (cutoff = bar 10).
        // y = [0, 10, 5, 20, 0]; x = [0,1,2,3,4].
        // sum_y = 35; sum_xy = 0+10+10+60+0 = 80; sum_y2 = 0+100+25+400+0=525.
        // sum_x = 10 (=L(L-1)/2); numerator = 5*80 - 10*35 = 400-350 = 50 > 0
        // => UP.
        let frame = SessionFrame::from_parts_for_test(
            0,
            200 * BAR_NS,
            vec![
                10 * BAR_NS,
                11 * BAR_NS,
                12 * BAR_NS,
                13 * BAR_NS,
                14 * BAR_NS,
            ],
            vec![1000, 1010, 1005, 1020, 1000],
            vec![1000, 1010, 1005, 1020, 1000],
            vec![GroupKind::Scalar; 5],
            Vec::new(),
        );
        let ctx = RowContext {
            frame: &frame,
            side: Side::Low,
            pivot_price_u6: 1_000_000,
            cutoff_ts_ns: 10 * BAR_NS,
            window_left: 0,
            breaker_start: None,
        };
        let results = compute_trend_row(&ctx);
        let l5 = &results[0]; // TREND_BARS[0] == 5
        assert_eq!(l5.state, TrendState::Complete);
        assert_eq!(l5.n, Some(5));
        assert_eq!(l5.sum_y, Some(35));
        assert_eq!(l5.sum_xy, Some(80));
        assert_eq!(l5.sum_y2, Some(525));
        assert_eq!(l5.sign, Some(TrendSign::Up));
    }

    #[test]
    fn trend_exact_l_boundary_is_complete_one_ns_short_is_truncated() {
        let groups_ts = vec![
            10 * BAR_NS,
            11 * BAR_NS,
            12 * BAR_NS,
            13 * BAR_NS,
            14 * BAR_NS,
        ];
        let prices = vec![100, 100, 100, 100, 100];

        // Exactly enough: session_end = cutoff + 5 bars precisely.
        let frame_exact = SessionFrame::from_parts_for_test(
            0,
            15 * BAR_NS,
            groups_ts.clone(),
            prices.clone(),
            prices.clone(),
            vec![GroupKind::Scalar; 5],
            Vec::new(),
        );
        let ctx_exact = RowContext {
            frame: &frame_exact,
            side: Side::Low,
            pivot_price_u6: 1_000_000,
            cutoff_ts_ns: 10 * BAR_NS,
            window_left: 0,
            breaker_start: None,
        };
        let results_exact = compute_trend_row(&ctx_exact);
        assert_eq!(results_exact[0].state, TrendState::Complete);

        // One ns short of enough: OFFICIAL_CLOSE_TRUNCATED.
        let frame_short = SessionFrame::from_parts_for_test(
            0,
            15 * BAR_NS - 1,
            groups_ts,
            prices.clone(),
            prices,
            vec![GroupKind::Scalar; 5],
            Vec::new(),
        );
        let ctx_short = RowContext {
            frame: &frame_short,
            side: Side::Low,
            pivot_price_u6: 1_000_000,
            cutoff_ts_ns: 10 * BAR_NS,
            window_left: 0,
            breaker_start: None,
        };
        let results_short = compute_trend_row(&ctx_short);
        assert_eq!(results_short[0].state, TrendState::OfficialCloseTruncated);
        assert_eq!(results_short[0].n, None);
    }

    #[test]
    fn trend_breaker_mid_window_censors_longer_l_but_not_a_shorter_one() {
        // Breaker at cutoff + 7 bars: L=5 (needs bars 10..14, i.e. up to 5
        // bars past cutoff) fits before it; L=10/20/40 do not.
        let frame = SessionFrame::from_parts_for_test(
            0,
            200 * BAR_NS,
            vec![
                10 * BAR_NS,
                11 * BAR_NS,
                12 * BAR_NS,
                13 * BAR_NS,
                14 * BAR_NS,
            ],
            vec![100, 100, 100, 100, 100],
            vec![100, 100, 100, 100, 100],
            vec![GroupKind::Scalar; 5],
            Vec::new(),
        );
        let ctx = RowContext {
            frame: &frame,
            side: Side::Low,
            pivot_price_u6: 1_000_000,
            cutoff_ts_ns: 10 * BAR_NS,
            window_left: 0,
            breaker_start: Some(17 * BAR_NS), // cutoff + 7 bars
        };
        let results = compute_trend_row(&ctx);
        assert_eq!(results[0].state, TrendState::Complete); // L=5
        assert_eq!(results[1].state, TrendState::WideBreaker); // L=10
        assert_eq!(results[2].state, TrendState::WideBreaker); // L=20
        assert_eq!(results[3].state, TrendState::WideBreaker); // L=40
    }

    #[test]
    fn trend_no_quote_when_the_baseline_bar_has_no_prior_scientific_group() {
        // cutoff = bar 0 (first_forward_bar = 0); the only group is at bar
        // 2's start, strictly after bar 0's own end -- no group qualifies
        // for the baseline bar.
        let frame = SessionFrame::from_parts_for_test(
            0,
            200 * BAR_NS,
            vec![2 * BAR_NS],
            vec![100],
            vec![100],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let ctx = RowContext {
            frame: &frame,
            side: Side::Low,
            pivot_price_u6: 1_000_000,
            cutoff_ts_ns: 0,
            window_left: 0,
            breaker_start: None,
        };
        let results = compute_trend_row(&ctx);
        for result in &results {
            assert_eq!(result.state, TrendState::NoQuote);
            assert_eq!(result.n, None);
        }
    }

    #[test]
    fn trend_sum_overflow_is_a_typed_state_not_a_silent_wraparound() {
        // Bars 0..3 flat at 1; bar 4 jumps to 4_000_000_000: y_4 ~ 4e9,
        // y_4^2 ~ 1.6e19 > i64::MAX (~9.22e18) -- overflow guaranteed even
        // with i128 accumulation of a single term.
        let frame = SessionFrame::from_parts_for_test(
            0,
            200 * BAR_NS,
            vec![
                10 * BAR_NS,
                11 * BAR_NS,
                12 * BAR_NS,
                13 * BAR_NS,
                14 * BAR_NS,
            ],
            vec![1, 1, 1, 1, 4_000_000_000],
            vec![1, 1, 1, 1, 4_000_000_000],
            vec![GroupKind::Scalar; 5],
            Vec::new(),
        );
        let ctx = RowContext {
            frame: &frame,
            side: Side::Low,
            pivot_price_u6: 1_000_000,
            cutoff_ts_ns: 10 * BAR_NS,
            window_left: 0,
            breaker_start: None,
        };
        let results = compute_trend_row(&ctx);
        assert_eq!(results[0].state, TrendState::Overflow);
        assert_eq!(results[0].sum_y2, None);
        assert_eq!(results[0].sign, None);
    }

    #[test]
    fn trend_sign_hand_computed_down_and_flat() {
        // DOWN: strictly decreasing closes.
        let frame_down = SessionFrame::from_parts_for_test(
            0,
            200 * BAR_NS,
            vec![
                10 * BAR_NS,
                11 * BAR_NS,
                12 * BAR_NS,
                13 * BAR_NS,
                14 * BAR_NS,
            ],
            vec![100, 90, 80, 70, 60],
            vec![100, 90, 80, 70, 60],
            vec![GroupKind::Scalar; 5],
            Vec::new(),
        );
        let ctx_down = RowContext {
            frame: &frame_down,
            side: Side::Low,
            pivot_price_u6: 1_000_000,
            cutoff_ts_ns: 10 * BAR_NS,
            window_left: 0,
            breaker_start: None,
        };
        assert_eq!(compute_trend_row(&ctx_down)[0].sign, Some(TrendSign::Down));

        // FLAT: constant closes (numerator exactly zero).
        let frame_flat = SessionFrame::from_parts_for_test(
            0,
            200 * BAR_NS,
            vec![
                10 * BAR_NS,
                11 * BAR_NS,
                12 * BAR_NS,
                13 * BAR_NS,
                14 * BAR_NS,
            ],
            vec![100, 100, 100, 100, 100],
            vec![100, 100, 100, 100, 100],
            vec![GroupKind::Scalar; 5],
            Vec::new(),
        );
        let ctx_flat = RowContext {
            frame: &frame_flat,
            side: Side::Low,
            pivot_price_u6: 1_000_000,
            cutoff_ts_ns: 10 * BAR_NS,
            window_left: 0,
            breaker_start: None,
        };
        assert_eq!(compute_trend_row(&ctx_flat)[0].sign, Some(TrendSign::Flat));
    }

    // ============================ row/write_tsv level ============================

    #[test]
    fn write_tsv_decision_unavailable_row_is_all_na() {
        // session_end at 3 bars; seed_bar_ordinal = 1 => D1 cutoff = 2 bars
        // (available), D2 cutoff = 3 bars == session_end (DECISION_UNAVAILABLE).
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
        let s = seed(Side::Low, 1_000_000, 1, 0);
        let path = std::env::temp_dir().join(format!(
            "f_ctrl_test_decision_unavailable_{}.tsv",
            std::process::id()
        ));
        write_tsv(&frame, std::slice::from_ref(&s), &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        std::fs::remove_file(&path).ok();

        let mut lines = content.lines();
        assert_eq!(lines.next(), Some(header().as_str()));
        let d1 = lines.next().expect("D1 row");
        let d2 = lines.next().expect("D2 row");
        let d3 = lines.next().expect("D3 row");
        assert_eq!(lines.next(), None);

        let d1_cols: Vec<&str> = d1.split('\t').collect();
        assert_ne!(d1_cols[9], "DECISION_UNAVAILABLE");

        let d2_cols: Vec<&str> = d2.split('\t').collect();
        assert_eq!(d2_cols[9], "DECISION_UNAVAILABLE");
        assert!(d2_cols[10..].iter().all(|&c| c == "NA"));

        let d3_cols: Vec<&str> = d3.split('\t').collect();
        assert_eq!(d3_cols[9], "DECISION_UNAVAILABLE");
        assert!(d3_cols[10..].iter().all(|&c| c == "NA"));
    }

    #[test]
    fn write_tsv_header_and_row_have_97_columns() {
        let header_line = header();
        let columns: Vec<&str> = header_line.split('\t').collect();
        assert_eq!(columns.len(), 10 + 9 * 7 + 4 * 6);
        assert_eq!(columns[0], "day");
        assert_eq!(columns[9], "window_frontier");
        assert_eq!(columns[10], "tb_20_30_state");
        assert_eq!(columns[columns.len() - 1], "trend_40_sign");

        let frame = SessionFrame::from_parts_for_test(
            0,
            200 * BAR_NS,
            vec![
                10 * BAR_NS,
                11 * BAR_NS,
                12 * BAR_NS,
                13 * BAR_NS,
                14 * BAR_NS,
            ],
            vec![100, 100, 100, 100, 100],
            vec![100, 100, 100, 100, 100],
            vec![GroupKind::Scalar; 5],
            Vec::new(),
        );
        let s = seed(Side::Low, 1_000_000, 9, 0);
        let path =
            std::env::temp_dir().join(format!("f_ctrl_test_shape_{}.tsv", std::process::id()));
        write_tsv(&frame, std::slice::from_ref(&s), &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        std::fs::remove_file(&path).ok();

        let mut lines = content.lines();
        lines.next(); // header
        let rows: Vec<&str> = lines.collect();
        assert_eq!(rows.len(), 3);
        for row in rows {
            assert_eq!(row.split('\t').count(), columns.len());
        }
    }
}
