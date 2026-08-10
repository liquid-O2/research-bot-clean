//! `a2_session_state` — the 22 session-state columns (plan Part V, A2), and
//! the **shared 1-minute tape** that A2 and C2 (`c2_trend_path`) both stream
//! into. Both families belong to the same build lane; the tape lives here
//! because A2 is the one that needs every field of it, and C2 imports it
//! rather than keeping a second, drifting copy of the same bar arithmetic.
//!
//! ## The as-of rule, restated in this file's terms
//!
//! The driver announces a cutoff BEFORE delivering the event that crossed it,
//! so at [`FamilyEmitter::on_cutoff`] this family has seen exactly the events
//! strictly before `cutoff_ns_b`. For the cutoff of 1-based bar ordinal `k`
//! that is exactly session minutes `0 .. k-1`, all complete. The row is a
//! snapshot of state accumulated from those and nothing else.
//!
//! ## Where the session anchor comes from
//!
//! Families are handed events and cutoffs, never a `DayScope`, so the tape is
//! accumulated against the **absolute** frame-B minute (`ts_ms_b / 60_000`),
//! which needs no anchor at all. The open is recovered at the first cutoff
//! from the cutoff itself: the book's `cutoff_ns_b` IS `open_b + ordinal *
//! BAR_NS`, so `open_minute = cutoff_minute - ordinal` exactly, in one frame,
//! with no second 09:30 derivation. Session minute `s` is then
//! `absolute_minute - open_minute`.
//!
//! ## Conventions that apply to every column here and in C2
//!
//! * **`_bps` means log-bps**: `10_000 * ln(now / then)`. Log bps are additive
//!   across adjacent windows, which is what makes C2's path efficiency exact
//!   rather than approximate. The one deliberate exception is
//!   `mid_bps_off_open`, which is the linear `10_000 * (mid - open) / open`;
//!   the column list mandates both it and `signed_net_move_bps`, so they are
//!   emitted as the linear and the log image of the same displacement and
//!   differ only in second order.
//! * **A fixed-length window is all-or-nothing.** `first30_range_bps`,
//!   `last30_range_bps` and every C2 window are NaN until the full window has
//!   elapsed since the open. A range computed over 7 minutes is a different
//!   quantity from one computed over 30, and silently substituting it would
//!   make the column mean two things. Running session-to-date quantities
//!   (counts, intensities, RV-so-far) are of course available from the start.
//! * **NaN is typed absence and is the only non-number emitted.** Every value
//!   goes through [`finite`], so no +/-inf can leave the family even if an
//!   intermediate divides by zero.
//! * **Four columns are permanently NaN by design** — `gap_at_open_bps`,
//!   `rv_vs_20d_ratio`, `vol_sofar_vs_seasonal`, `range_vs_atr_ratio`. Each
//!   needs prior-session context that this in-pass, single-session emitter
//!   cannot see; the python `daily_context` step fills them. They are declared
//!   [`AsOfRule::PriorSessionsOnly`] so the reason is in the schema, not only
//!   in prose, and they keep their real names so the downstream join needs no
//!   rename.
//!
//! ## Quotes the tape refuses
//!
//! A quote with a non-positive bid or ask has no usable midpoint; it is
//! counted in [`MinuteTape::unusable_quotes`] and skipped, so a one-sided book
//! cannot set a session low of half the ask.

use super::{AsOfRule, ColSpec, FamilyEmitter, FamilyRows, QuoteEvent, TradeEvent, Unit};
use crate::book::{ActionCutoff, Side};
use crate::error::{Result, SelectV2Error};

/// Registered name.
pub const NAME: &str = "a2_session_state";

/// Milliseconds in one 1-minute bar.
pub const MS_PER_MINUTE: i64 = 60_000;

/// Basis points per unit of log return.
pub const BPS: f64 = 10_000.0;

/// The fixed opening window `first30_range_bps` measures.
const FIRST_WINDOW_MINUTES: i64 = 30;

/// The trailing window `last30_range_bps` measures.
const LAST_WINDOW_MINUTES: i64 = 30;

/// How recently a new session extreme counts as an expansion.
const EXPANSION_LOOKBACK_MINUTES: i64 = 5;

/// The 22 columns, in emission order.
const COLUMNS: [ColSpec; 22] = [
    ColSpec::new("gap_at_open_bps", Unit::Bps, AsOfRule::PriorSessionsOnly),
    ColSpec::new(
        "session_range_so_far_bps",
        Unit::Bps,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new("pos_in_range", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("highs_count", Unit::Count, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("lows_count", Unit::Count, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("mins_since_high", Unit::Bars, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("mins_since_low", Unit::Bars, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("vwap_dist_bps", Unit::Bps, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("rv_sofar_bps", Unit::Bps, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("rv_vs_20d_ratio", Unit::Ratio, AsOfRule::PriorSessionsOnly),
    ColSpec::new(
        "signed_net_move_bps",
        Unit::Bps,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "tol2_confirms_sofar",
        Unit::Count,
        AsOfRule::BookSummaryAtCutoff,
    ),
    ColSpec::new(
        "opp_side_confirms_sofar",
        Unit::Count,
        AsOfRule::BookSummaryAtCutoff,
    ),
    ColSpec::new("first30_range_bps", Unit::Bps, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("last30_range_bps", Unit::Bps, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new(
        "vol_sofar_vs_seasonal",
        Unit::Ratio,
        AsOfRule::PriorSessionsOnly,
    ),
    ColSpec::new(
        "minutes_since_last_cutoff_same_side",
        Unit::Bars,
        AsOfRule::BookSummaryAtCutoff,
    ),
    ColSpec::new("range_vs_atr_ratio", Unit::Ratio, AsOfRule::PriorSessionsOnly),
    ColSpec::new(
        "quote_intensity_1m_vs_session",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "trade_intensity_1m_vs_session",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new("mid_bps_off_open", Unit::Bps, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new(
        "range_expansion_flag",
        Unit::Flag,
        AsOfRule::StrictlyBeforeCutoff,
    ),
];

/// One sealed minute of the session.
///
/// `high_u6`/`low_u6` are extremes of the **midpoint**, not of the bid or ask,
/// so they are directly comparable with `close_u6` and with the session
/// extremes. A minute in which no usable quote arrived is still pushed, with
/// the previous minute's close carried into all three prices and `observed`
/// false — the bar sequence stays dense (index arithmetic is then exact) while
/// the absence stays visible.
#[derive(Clone, Copy, Debug)]
pub struct MinuteBar {
    /// Last midpoint observed inside the minute, u6.
    pub close_u6: i64,
    /// Highest midpoint inside the minute, u6.
    pub high_u6: i64,
    /// Lowest midpoint inside the minute, u6.
    pub low_u6: i64,
    /// `ln(close / previous close)`; the previous close of the first bar is
    /// the session's opening mid. Exactly `0.0` for a carried bar.
    pub ret_ln: f64,
    /// Cumulative session trade VWAP at this bar's close, u6; `None` until the
    /// session's first sized print.
    pub vwap_u6: Option<i64>,
    /// Usable quotes inside the minute.
    pub quotes: u32,
    /// Prints inside the minute.
    pub trades: u32,
    /// This minute extended the session high.
    pub new_high: bool,
    /// This minute extended the session low.
    pub new_low: bool,
    /// At least one usable quote landed in this minute.
    pub observed: bool,
}

/// The minute currently being accumulated.
#[derive(Clone, Copy, Debug)]
struct OpenBar {
    minute_abs: i64,
    close_u6: i64,
    high_u6: i64,
    low_u6: i64,
    quotes: u32,
    trades: u32,
    new_high: bool,
    new_low: bool,
    observed: bool,
}

impl OpenBar {
    /// A minute that has seen nothing yet, standing at `carry_u6`.
    const fn carried(minute_abs: i64, carry_u6: i64) -> Self {
        Self {
            minute_abs,
            close_u6: carry_u6,
            high_u6: carry_u6,
            low_u6: carry_u6,
            quotes: 0,
            trades: 0,
            new_high: false,
            new_low: false,
            observed: false,
        }
    }
}

/// The streaming 1-minute tape: O(1) per event, O(window) per cutoff.
///
/// Bars are keyed by ABSOLUTE frame-B minute while streaming and only
/// translated to session minutes once [`Self::anchor_and_seal`] has recovered
/// the open from a cutoff. `bars` is dense from [`Self::first_minute_abs`],
/// which is what makes every window lookup index arithmetic rather than a
/// search.
#[derive(Clone, Debug)]
pub struct MinuteTape {
    open_minute_abs: Option<i64>,
    first_minute_abs: Option<i64>,
    bars: Vec<MinuteBar>,
    open_bar: Option<OpenBar>,
    open_mid_u6: Option<i64>,
    last_mid_u6: Option<i64>,
    session_high_u6: i64,
    session_low_u6: i64,
    high_minute_abs: i64,
    low_minute_abs: i64,
    new_high_bars: u32,
    new_low_bars: u32,
    /// i128 so a fat-finger print cannot overflow the notional accumulator;
    /// a full session is ~6e15 u6-share, three orders inside i64, but the
    /// wider accumulator removes the question rather than arguing it.
    notional_u6: i128,
    volume: i128,
    quotes: u64,
    trades: u64,
    unusable_quotes: u64,
    carried_bars: u32,
    rv_sum_squares: f64,
}

impl Default for MinuteTape {
    fn default() -> Self {
        Self::new()
    }
}

impl MinuteTape {
    /// An empty tape.
    #[must_use]
    pub const fn new() -> Self {
        Self {
            open_minute_abs: None,
            first_minute_abs: None,
            bars: Vec::new(),
            open_bar: None,
            open_mid_u6: None,
            last_mid_u6: None,
            session_high_u6: 0,
            session_low_u6: 0,
            high_minute_abs: 0,
            low_minute_abs: 0,
            new_high_bars: 0,
            new_low_bars: 0,
            notional_u6: 0,
            volume: 0,
            quotes: 0,
            trades: 0,
            unusable_quotes: 0,
            carried_bars: 0,
            rv_sum_squares: 0.0,
        }
    }

    /// Folds one NBBO update in. Quotes with a non-positive side are counted
    /// and skipped — a one-sided book has no midpoint.
    pub fn on_quote(&mut self, quote: &QuoteEvent) {
        if quote.bid_u6 <= 0 || quote.ask_u6 <= 0 {
            self.unusable_quotes += 1;
            return;
        }
        let mid = quote.mid_u6();
        let minute_abs = quote.ts_ms_b.div_euclid(MS_PER_MINUTE);
        if self.open_bar.is_none() {
            self.first_minute_abs = Some(minute_abs);
            self.open_mid_u6 = Some(mid);
            self.session_high_u6 = mid;
            self.session_low_u6 = mid;
            self.high_minute_abs = minute_abs;
            self.low_minute_abs = minute_abs;
            self.open_bar = Some(OpenBar::carried(minute_abs, mid));
        } else {
            self.seal_before(minute_abs);
        }
        // The opening quote ESTABLISHES the extremes; it does not extend them,
        // so it is not counted as a new-extreme minute.
        let extends_high = mid > self.session_high_u6;
        let extends_low = mid < self.session_low_u6;
        if extends_high {
            self.session_high_u6 = mid;
            self.high_minute_abs = minute_abs;
        }
        if extends_low {
            self.session_low_u6 = mid;
            self.low_minute_abs = minute_abs;
        }
        self.quotes += 1;
        self.last_mid_u6 = Some(mid);
        let Some(open) = self.open_bar.as_mut() else {
            return;
        };
        open.quotes = open.quotes.saturating_add(1);
        if open.observed {
            open.high_u6 = open.high_u6.max(mid);
            open.low_u6 = open.low_u6.min(mid);
        } else {
            open.observed = true;
            open.high_u6 = mid;
            open.low_u6 = mid;
        }
        open.close_u6 = mid;
        if extends_high && !open.new_high {
            open.new_high = true;
            self.new_high_bars += 1;
        }
        if extends_low && !open.new_low {
            open.new_low = true;
            self.new_low_bars += 1;
        }
    }

    /// Folds one print in. Zero- or negative-priced/sized prints are counted
    /// in the print count but kept out of the VWAP, where they would be a
    /// fabricated price rather than a small one.
    pub fn on_trade(&mut self, trade: &TradeEvent) {
        self.trades += 1;
        if trade.price_u6 > 0 && trade.size > 0 {
            self.notional_u6 += i128::from(trade.price_u6) * i128::from(trade.size);
            self.volume += i128::from(trade.size);
        }
        let minute_abs = trade.ts_ms_b.div_euclid(MS_PER_MINUTE);
        self.seal_before(minute_abs);
        if let Some(open) = self.open_bar.as_mut()
            && open.minute_abs == minute_abs
        {
            open.trades = open.trades.saturating_add(1);
        }
    }

    /// Recovers the session open from the cutoff itself and seals every minute
    /// strictly before it, so the bar sequence is complete as of the cutoff.
    /// Returns the cutoff's minutes-after-open, i.e. its bar ordinal.
    ///
    /// `cutoff_ns_b` is `open_b + ordinal * BAR_NS` by the book reader's own
    /// derivation, so the subtraction below is exact and stays inside frame B.
    pub fn anchor_and_seal(&mut self, cutoff: &ActionCutoff) -> i64 {
        let cutoff_minute_abs = cutoff.cutoff_ns_b.div_euclid(corpus::BAR_NS);
        let ordinal = i64::from(cutoff.cutoff_bar_ordinal);
        self.open_minute_abs = Some(cutoff_minute_abs - ordinal);
        self.seal_before(cutoff_minute_abs);
        ordinal
    }

    /// Seals every minute strictly before `minute_abs`, padding quote-less
    /// minutes with carried bars, and leaves an open bar at `minute_abs`.
    /// A no-op before the session's first usable quote, when there is no price
    /// to carry and therefore no bar to seal.
    fn seal_before(&mut self, minute_abs: i64) {
        loop {
            let Some(open) = self.open_bar.take() else {
                return;
            };
            if open.minute_abs >= minute_abs {
                self.open_bar = Some(open);
                return;
            }
            let next_minute = open.minute_abs + 1;
            let carry = open.close_u6;
            self.push_bar(open);
            self.open_bar = Some(OpenBar::carried(next_minute, carry));
        }
    }

    fn push_bar(&mut self, open: OpenBar) {
        let previous_close = self
            .bars
            .last()
            .map_or_else(|| self.open_mid_u6.unwrap_or(open.close_u6), |bar| bar.close_u6);
        let ret_ln = ln_ratio(open.close_u6, previous_close);
        self.rv_sum_squares += ret_ln * ret_ln;
        if !open.observed {
            self.carried_bars += 1;
        }
        let vwap_u6 = self.current_vwap_u6();
        self.bars.push(MinuteBar {
            close_u6: open.close_u6,
            high_u6: open.high_u6,
            low_u6: open.low_u6,
            ret_ln,
            vwap_u6,
            quotes: open.quotes,
            trades: open.trades,
            new_high: open.new_high,
            new_low: open.new_low,
            observed: open.observed,
        });
    }

    /// Cumulative session trade VWAP, u6; `None` before the first sized print.
    #[must_use]
    pub fn current_vwap_u6(&self) -> Option<i64> {
        if self.volume <= 0 {
            return None;
        }
        i64::try_from(self.notional_u6 / self.volume).ok()
    }

    /// Session opening mid (the first usable midpoint), u6.
    #[must_use]
    pub const fn open_mid_u6(&self) -> Option<i64> {
        self.open_mid_u6
    }

    /// The last midpoint seen strictly before the cutoff, u6.
    #[must_use]
    pub const fn last_mid_u6(&self) -> Option<i64> {
        self.last_mid_u6
    }

    /// Session high/low of the midpoint so far, u6; `None` before the first
    /// usable quote — absent, not zero.
    #[must_use]
    pub const fn extremes_u6(&self) -> Option<(i64, i64)> {
        if self.open_mid_u6.is_none() {
            return None;
        }
        Some((self.session_high_u6, self.session_low_u6))
    }

    /// Minutes the session has extended its high / low.
    #[must_use]
    pub const fn new_extreme_counts(&self) -> (u32, u32) {
        (self.new_high_bars, self.new_low_bars)
    }

    /// Usable quotes and prints folded in so far.
    #[must_use]
    pub const fn event_counts(&self) -> (u64, u64) {
        (self.quotes, self.trades)
    }

    /// Quotes skipped for having a non-positive side. Observed, not hidden.
    #[must_use]
    pub const fn unusable_quotes(&self) -> u64 {
        self.unusable_quotes
    }

    /// Minutes sealed with no usable quote at all.
    #[must_use]
    pub const fn carried_bars(&self) -> u32 {
        self.carried_bars
    }

    /// Realized volatility of 1-minute log mid returns since the open, in bps.
    #[must_use]
    pub fn rv_sofar_bps(&self) -> f64 {
        self.rv_sum_squares.sqrt() * BPS
    }

    /// The bar covering session minute `session_minute` (0-based, so bar
    /// ordinal `k` is session minute `k - 1`).
    #[must_use]
    pub fn bar_at(&self, session_minute: i64) -> Option<&MinuteBar> {
        let (open, first) = (self.open_minute_abs?, self.first_minute_abs?);
        let index = (open + session_minute) - first;
        usize::try_from(index).ok().and_then(|i| self.bars.get(i))
    }

    /// The mid exactly `minutes_after_open` minutes after the open: the
    /// opening mid at 0, otherwise the close of the bar that ends there.
    #[must_use]
    pub fn price_at(&self, minutes_after_open: i64) -> Option<i64> {
        if minutes_after_open < 0 {
            return None;
        }
        if minutes_after_open == 0 {
            // Only lawful when the tape actually started at the open; a late
            // first quote is absence, not an opening print.
            return (self.first_minute_abs? == self.open_minute_abs?)
                .then_some(self.open_mid_u6)
                .flatten();
        }
        self.bar_at(minutes_after_open - 1).map(|bar| bar.close_u6)
    }

    /// Cumulative session VWAP as of `minutes_after_open`, u6.
    #[must_use]
    pub fn vwap_at(&self, minutes_after_open: i64) -> Option<i64> {
        if minutes_after_open <= 0 {
            return None;
        }
        self.bar_at(minutes_after_open - 1).and_then(|bar| bar.vwap_u6)
    }

    /// The `minutes` complete bars ending `minutes_after_open` minutes after
    /// the open, i.e. session minutes `[k - minutes, k - 1]`. `None` unless
    /// EVERY one of them exists — a fixed window is all-or-nothing.
    #[must_use]
    pub fn window(&self, minutes_after_open: i64, minutes: i64) -> Option<&[MinuteBar]> {
        if minutes <= 0 {
            return None;
        }
        let start_minute = minutes_after_open - minutes;
        if start_minute < 0 {
            return None;
        }
        let (open, first) = (self.open_minute_abs?, self.first_minute_abs?);
        let start = usize::try_from((open + start_minute) - first).ok()?;
        let end = start.checked_add(usize::try_from(minutes).ok()?)?;
        self.bars.get(start..end)
    }

    /// Complete minutes since the session high was last extended, as of a
    /// cutoff `minutes_after_open` minutes into the session. `0` means the
    /// extreme is in the most recently completed minute.
    #[must_use]
    pub fn minutes_since_high(&self, minutes_after_open: i64) -> Option<i64> {
        self.minutes_since(self.high_minute_abs, minutes_after_open)
    }

    /// Complete minutes since the session low was last extended.
    #[must_use]
    pub fn minutes_since_low(&self, minutes_after_open: i64) -> Option<i64> {
        self.minutes_since(self.low_minute_abs, minutes_after_open)
    }

    fn minutes_since(&self, extreme_minute_abs: i64, minutes_after_open: i64) -> Option<i64> {
        self.open_mid_u6?;
        let open = self.open_minute_abs?;
        Some(((minutes_after_open - 1) - (extreme_minute_abs - open)).max(0))
    }
}

/// Highest high and lowest low over a run of bars.
#[must_use]
pub fn range_u6(bars: &[MinuteBar]) -> Option<(i64, i64)> {
    let first = bars.first()?;
    let mut high = first.high_u6;
    let mut low = first.low_u6;
    for bar in &bars[1..] {
        high = high.max(bar.high_u6);
        low = low.min(bar.low_u6);
    }
    Some((high, low))
}

/// `ln(now / then)` for two u6 prices; `0.0` if either is non-positive, which
/// callers gate on before using the result.
#[must_use]
pub fn ln_ratio(now_u6: i64, then_u6: i64) -> f64 {
    if now_u6 <= 0 || then_u6 <= 0 {
        return 0.0;
    }
    // u6 prices are ~2e8 for IWM; f64 holds them exactly.
    #[allow(clippy::cast_precision_loss)]
    {
        (now_u6 as f64 / then_u6 as f64).ln()
    }
}

/// `10_000 * ln(now / then)` — the crate's log-bps. NaN when either price is
/// absent or non-positive.
#[must_use]
pub fn log_bps(now_u6: Option<i64>, then_u6: Option<i64>) -> f64 {
    match (now_u6, then_u6) {
        (Some(now), Some(then)) if now > 0 && then > 0 => ln_ratio(now, then) * BPS,
        _ => f64::NAN,
    }
}

/// An `i64` count as `f64`.
#[must_use]
#[allow(clippy::cast_precision_loss)]
pub fn count_f64(value: i64) -> f64 {
    value as f64
}

/// Narrows to the emitted `f32`, mapping every non-finite intermediate to NaN.
/// This is what makes "no +/-inf ever leaves a family" structural: a divide by
/// zero upstream lands as typed absence, not as an infinity a downstream mean
/// would silently poison.
#[must_use]
#[allow(clippy::cast_possible_truncation)]
pub fn finite(value: f64) -> f32 {
    if value.is_finite() {
        value as f32
    } else {
        f32::NAN
    }
}

/// Session state at each action's cutoff.
#[derive(Clone, Debug)]
pub struct A2SessionState {
    tape: MinuteTape,
    /// Cutoffs already announced this session, by side. Incremented AFTER the
    /// row is written, so a row counts only strictly prior actions.
    prior_high: u32,
    prior_low: u32,
    /// Bar ordinal of the last announced cutoff on each side.
    last_high_ordinal: Option<i64>,
    last_low_ordinal: Option<i64>,
    rows: Vec<f32>,
}

impl Default for A2SessionState {
    fn default() -> Self {
        Self::new()
    }
}

impl A2SessionState {
    /// A fresh emitter for one session.
    #[must_use]
    pub const fn new() -> Self {
        Self {
            tape: MinuteTape::new(),
            prior_high: 0,
            prior_low: 0,
            last_high_ordinal: None,
            last_low_ordinal: None,
            rows: Vec::new(),
        }
    }

    /// The tape this emitter accumulated — the probe surface the tests and the
    /// census read.
    #[must_use]
    pub const fn tape(&self) -> &MinuteTape {
        &self.tape
    }
}

/// Value-namespace constructor for `families::build`, which currently spells
/// the family as the unit-struct expression `Box::new(a2_session_state::
/// A2SessionState)`. `mod.rs` belongs to another lane, so the emitter supplies
/// the value that expression needs rather than forcing an edit there. Once
/// `build` says `A2SessionState::default()`, delete this const.
#[allow(non_upper_case_globals)]
pub const A2SessionState: A2SessionState = A2SessionState::new();

impl FamilyEmitter for A2SessionState {
    fn name(&self) -> &'static str {
        NAME
    }

    fn columns(&self) -> &[ColSpec] {
        &COLUMNS
    }

    fn on_quote(&mut self, quote: &QuoteEvent) {
        self.tape.on_quote(quote);
    }

    fn on_trade(&mut self, trade: &TradeEvent) {
        self.tape.on_trade(trade);
    }

    // One straight-line snapshot: every column is written in declared order in
    // one place, so a reader checks the row against COLUMNS by reading down.
    #[allow(clippy::too_many_lines)]
    fn on_cutoff(&mut self, cutoff: &ActionCutoff) {
        let minutes = self.tape.anchor_and_seal(cutoff);
        let mid = self.tape.last_mid_u6();
        let open = self.tape.open_mid_u6();
        let extremes = self.tape.extremes_u6();

        let session_range = extremes.map_or(f64::NAN, |(high, low)| {
            log_bps(Some(high), Some(low))
        });
        let position = match (mid, extremes) {
            (Some(mid), Some((high, low))) if high > low => {
                count_f64(mid - low) / count_f64(high - low)
            }
            _ => f64::NAN,
        };
        let (high_bars, low_bars) = self.tape.new_extreme_counts();
        let since_high = self.tape.minutes_since_high(minutes);
        let since_low = self.tape.minutes_since_low(minutes);
        let vwap_distance = log_bps(mid, self.tape.current_vwap_u6());
        let net_move = log_bps(mid, open);

        let (same_side, opposite_side, last_same_side) = match cutoff.side {
            Side::High => (self.prior_high, self.prior_low, self.last_high_ordinal),
            Side::Low => (self.prior_low, self.prior_high, self.last_low_ordinal),
        };
        let since_same_side = last_same_side.map_or(f64::NAN, |previous| {
            count_f64(minutes - previous)
        });

        let first_window = self
            .tape
            .window(FIRST_WINDOW_MINUTES, FIRST_WINDOW_MINUTES)
            .and_then(range_u6);
        let last_window = self
            .tape
            .window(minutes, LAST_WINDOW_MINUTES)
            .and_then(range_u6);
        let first_range = first_window.map_or(f64::NAN, |(high, low)| {
            log_bps(Some(high), Some(low))
        });
        let last_range = last_window.map_or(f64::NAN, |(high, low)| {
            log_bps(Some(high), Some(low))
        });

        let (quotes, trades) = self.tape.event_counts();
        let latest = self.tape.window(minutes, 1).and_then(<[MinuteBar]>::first);
        let quote_intensity = intensity(latest.map(|bar| bar.quotes), quotes, minutes);
        let trade_intensity = intensity(latest.map(|bar| bar.trades), trades, minutes);

        let off_open = match (mid, open) {
            (Some(mid), Some(open)) if open > 0 => BPS * count_f64(mid - open) / count_f64(open),
            _ => f64::NAN,
        };
        let expansion = match (since_high, since_low) {
            (Some(high), Some(low)) => {
                f64::from(u8::from(high.min(low) < EXPANSION_LOOKBACK_MINUTES))
            }
            _ => f64::NAN,
        };

        self.rows.extend_from_slice(&[
            f32::NAN, // gap_at_open_bps: needs the prior session's close.
            finite(session_range),
            finite(position),
            finite(f64::from(high_bars)),
            finite(f64::from(low_bars)),
            finite(since_high.map_or(f64::NAN, count_f64)),
            finite(since_low.map_or(f64::NAN, count_f64)),
            finite(vwap_distance),
            finite(self.tape.rv_sofar_bps()),
            f32::NAN, // rv_vs_20d_ratio: trailing-20d same-time median.
            finite(net_move),
            finite(f64::from(same_side)),
            finite(f64::from(opposite_side)),
            finite(first_range),
            finite(last_range),
            f32::NAN, // vol_sofar_vs_seasonal: seasonal volume curve.
            finite(since_same_side),
            f32::NAN, // range_vs_atr_ratio: trailing ATR.
            finite(quote_intensity),
            finite(trade_intensity),
            finite(off_open),
            finite(expansion),
        ]);

        match cutoff.side {
            Side::High => {
                self.prior_high += 1;
                self.last_high_ordinal = Some(minutes);
            }
            Side::Low => {
                self.prior_low += 1;
                self.last_low_ordinal = Some(minutes);
            }
        }
    }

    fn emit(&mut self, cutoffs: &[ActionCutoff]) -> Result<FamilyRows> {
        let expected = cutoffs.len() * COLUMNS.len();
        if self.rows.len() != expected {
            return Err(SelectV2Error::ContentMismatch {
                path: std::path::PathBuf::from(NAME),
                detail: format!(
                    "produced {} values for {} cutoffs x {} columns",
                    self.rows.len(),
                    cutoffs.len(),
                    COLUMNS.len()
                ),
            });
        }
        Ok(FamilyRows {
            columns: COLUMNS.len(),
            values: std::mem::take(&mut self.rows),
        })
    }
}

/// Last-minute event count over the session's mean per-minute rate.
fn intensity(last_minute: Option<u32>, total: u64, minutes: i64) -> f64 {
    let Some(last_minute) = last_minute else {
        return f64::NAN;
    };
    if total == 0 || minutes <= 0 {
        return f64::NAN;
    }
    // Session counts are ~1e7 at most; the f64 images are exact.
    #[allow(clippy::cast_precision_loss)]
    let mean = total as f64 / count_f64(minutes);
    if mean <= 0.0 {
        return f64::NAN;
    }
    f64::from(last_minute) / mean
}

#[cfg(test)]
pub(crate) mod test_support {
    //! One tiny driver shared by the A2 and C2 tests. It reproduces the
    //! production ordering rule — announce every reached cutoff BEFORE
    //! delivering the event that reached it — because that ordering is the
    //! as-of rule, and a test that got it wrong would be testing a different
    //! contract from the one `session_pass` ships.

    use crate::book::{ActionCutoff, Side};
    use crate::calendar::{self, DayScope};
    use crate::families::{FamilyEmitter, QuoteEvent, TradeEvent};
    use crate::sources::stock_quotes::{StockQuoteBatch, StockQuoteReader};
    use crate::sources::stock_trades::{StockTradeBatch, StockTradeReader};
    use crate::sources::TokenRoots;

    /// A cutoff built through the production calendar, so its frame-B instant
    /// is the one the book reader would derive.
    pub fn cutoff_for(scope: &DayScope, bar_ordinal: i32, side: Side) -> ActionCutoff {
        let ordinal = i64::from(bar_ordinal);
        ActionCutoff {
            action_id: format!("{}-{bar_ordinal}-{side:?}", scope.day()),
            day: scope.day(),
            session_ordinal: u32::try_from(scope.session_ordinal()).expect("in range"),
            cutoff_bar_ordinal: bar_ordinal,
            side,
            cutoff_ns_a: scope.cutoff_ns_a(ordinal).expect("in range"),
            cutoff_ns_b: scope.cutoff_ns_b(ordinal).expect("in range"),
            first_visibility_ns: 0,
            last_visibility_ns: 0,
            act_set: crate::book::ActSetSummary::default(),
        }
    }

    /// A quote `second` seconds after the open at the given mid, in cents,
    /// with a one-cent book around it.
    pub fn quote_at(scope: &DayScope, second: i64, mid_cents: i64) -> QuoteEvent {
        let mid_u6 = mid_cents * 10_000;
        QuoteEvent {
            ts_ms_b: scope.open_ms_b() + second * 1_000,
            bid_u6: mid_u6 - 5_000,
            ask_u6: mid_u6 + 5_000,
            bid_shares: 100,
            ask_shares: 100,
        }
    }

    /// A print `second` seconds after the open.
    pub fn trade_at(scope: &DayScope, second: i64, price_cents: i64, size: i64) -> TradeEvent {
        TradeEvent {
            ts_ms_b: scope.open_ms_b() + second * 1_000,
            price_u6: price_cents * 10_000,
            size,
            exchange: 4,
            condition: 0,
            sequence: second,
            bid_u6: price_cents * 10_000 - 5_000,
            ask_u6: price_cents * 10_000 + 5_000,
            bid_shares: 100,
            ask_shares: 100,
            quote_present: true,
        }
    }

    /// Drives one family over a synthetic tape, announcing cutoffs exactly as
    /// `session_pass::run_session` does.
    pub fn drive(
        family: &mut dyn FamilyEmitter,
        quotes: &[QuoteEvent],
        trades: &[TradeEvent],
        cutoffs: &[ActionCutoff],
    ) -> Vec<f32> {
        let mut next = 0_usize;
        let (mut q, mut t) = (0_usize, 0_usize);
        loop {
            let quote_ts = quotes.get(q).map(|quote| quote.ts_ms_b);
            let trade_ts = trades.get(t).map(|trade| trade.ts_ms_b);
            let take_quote = match (quote_ts, trade_ts) {
                (Some(quote), Some(trade)) => quote <= trade,
                (Some(_), None) => true,
                (None, Some(_)) => false,
                (None, None) => break,
            };
            let ts_ms = if take_quote {
                quote_ts.unwrap_or_default()
            } else {
                trade_ts.unwrap_or_default()
            };
            let event_ns = ts_ms * 1_000_000;
            while next < cutoffs.len() && cutoffs[next].cutoff_ns_b <= event_ns {
                family.on_cutoff(&cutoffs[next]);
                next += 1;
            }
            if take_quote {
                family.on_quote(&quotes[q]);
                q += 1;
            } else {
                family.on_trade(&trades[t]);
                t += 1;
            }
        }
        while next < cutoffs.len() {
            family.on_cutoff(&cutoffs[next]);
            next += 1;
        }
        family.emit(cutoffs).expect("emit").values
    }

    /// Drives one family over the REAL stock tape of a registered day, with
    /// the REAL action cutoffs, through the production readers.
    pub fn drive_real_session(family: &mut dyn FamilyEmitter, day: &str) -> (Vec<f32>, usize) {
        let roots = TokenRoots::default();
        let scope = calendar::admit(day).expect("registered session");
        let ordinal = u32::try_from(scope.session_ordinal()).expect("in range");
        let book = crate::book::load_sessions(
            std::path::Path::new(crate::book::DEFAULT_BOOK_DIR),
            Some(&[ordinal]),
        )
        .expect("action book");
        let cutoffs: Vec<ActionCutoff> = book.cutoffs_for(ordinal).to_vec();
        assert!(!cutoffs.is_empty(), "{day} carries no actions");

        let mut quotes = StockQuoteReader::for_scope(&scope, &roots.stock_quotes()).expect("quotes");
        let mut trades = StockTradeReader::for_scope(&scope, &roots.stock_trades()).expect("trades");
        let mut quote_batch = StockQuoteBatch::default();
        let mut trade_batch = StockTradeBatch::default();
        let mut quotes_live = quotes.next_into(&mut quote_batch).expect("decode");
        let mut trades_live = trades.next_into(&mut trade_batch).expect("decode");
        let (mut q, mut t, mut next) = (0_usize, 0_usize, 0_usize);
        loop {
            if quotes_live && q >= quote_batch.len() {
                quotes_live = quotes.next_into(&mut quote_batch).expect("decode");
                q = 0;
                continue;
            }
            if trades_live && t >= trade_batch.len() {
                trades_live = trades.next_into(&mut trade_batch).expect("decode");
                t = 0;
                continue;
            }
            let quote_ts = quotes_live.then(|| quote_batch.ts_ms_b[q]);
            let trade_ts = trades_live.then(|| trade_batch.ts_ms_b[t]);
            let take_quote = match (quote_ts, trade_ts) {
                (Some(quote), Some(trade)) => quote <= trade,
                (Some(_), None) => true,
                (None, Some(_)) => false,
                (None, None) => break,
            };
            let ts_ms = if take_quote {
                quote_ts.unwrap_or_default()
            } else {
                trade_ts.unwrap_or_default()
            };
            let event_ns = ts_ms * 1_000_000;
            while next < cutoffs.len() && cutoffs[next].cutoff_ns_b <= event_ns {
                family.on_cutoff(&cutoffs[next]);
                next += 1;
            }
            if take_quote {
                family.on_quote(&QuoteEvent {
                    ts_ms_b: ts_ms,
                    bid_u6: quote_batch.bid_u6[q],
                    ask_u6: quote_batch.ask_u6[q],
                    bid_shares: quote_batch.bid_shares[q],
                    ask_shares: quote_batch.ask_shares[q],
                });
                q += 1;
            } else {
                family.on_trade(&TradeEvent {
                    ts_ms_b: ts_ms,
                    price_u6: trade_batch.price_u6[t],
                    size: trade_batch.size[t],
                    exchange: trade_batch.exchange[t],
                    condition: trade_batch.condition[t],
                    sequence: trade_batch.sequence[t],
                    bid_u6: trade_batch.bid_u6[t],
                    ask_u6: trade_batch.ask_u6[t],
                    bid_shares: trade_batch.bid_shares[t],
                    ask_shares: trade_batch.ask_shares[t],
                    quote_present: trade_batch.quote_present[t],
                });
                t += 1;
            }
        }
        while next < cutoffs.len() {
            family.on_cutoff(&cutoffs[next]);
            next += 1;
        }
        let rows = family.emit(&cutoffs).expect("emit");
        assert_eq!(rows.rows(), cutoffs.len(), "one row per announced cutoff");
        (rows.values, cutoffs.len())
    }
}

#[cfg(test)]
mod tests {
    use super::test_support::{cutoff_for, drive, quote_at, trade_at};
    use super::{A2SessionState, COLUMNS, MinuteTape, NAME};
    use crate::book::Side;
    use crate::calendar;
    use crate::families::{FamilyEmitter, QuoteEvent};

    const DEV_DAY: &str = "2022-03-01";

    fn row(values: &[f32], index: usize) -> &[f32] {
        &values[index * COLUMNS.len()..(index + 1) * COLUMNS.len()]
    }

    #[test]
    fn column_names_and_width_are_the_declared_twenty_two() {
        let family = A2SessionState::default();
        assert_eq!(family.name(), NAME);
        let names: Vec<&str> = family.columns().iter().map(|spec| spec.name).collect();
        assert_eq!(
            names,
            vec![
                "gap_at_open_bps",
                "session_range_so_far_bps",
                "pos_in_range",
                "highs_count",
                "lows_count",
                "mins_since_high",
                "mins_since_low",
                "vwap_dist_bps",
                "rv_sofar_bps",
                "rv_vs_20d_ratio",
                "signed_net_move_bps",
                "tol2_confirms_sofar",
                "opp_side_confirms_sofar",
                "first30_range_bps",
                "last30_range_bps",
                "vol_sofar_vs_seasonal",
                "minutes_since_last_cutoff_same_side",
                "range_vs_atr_ratio",
                "quote_intensity_1m_vs_session",
                "trade_intensity_1m_vs_session",
                "mid_bps_off_open",
                "range_expansion_flag",
            ]
        );
        assert_eq!(family.columns().len(), 22);
    }

    #[test]
    fn the_four_python_filled_columns_are_absent_not_zero() {
        let scope = calendar::admit(DEV_DAY).expect("registered");
        let quotes: Vec<QuoteEvent> = (0..600)
            .map(|second| quote_at(&scope, second, 20_000 + second % 7))
            .collect();
        let cutoffs = [cutoff_for(&scope, 5, Side::High)];
        let mut family = A2SessionState::default();
        let values = drive(&mut family, &quotes, &[], &cutoffs);
        for (index, name) in [
            (0, "gap_at_open_bps"),
            (9, "rv_vs_20d_ratio"),
            (15, "vol_sofar_vs_seasonal"),
            (17, "range_vs_atr_ratio"),
        ] {
            assert!(values[index].is_nan(), "{name} must be typed absence");
        }
    }

    #[test]
    fn range_position_and_extremes_track_a_measured_tape() {
        let scope = calendar::admit(DEV_DAY).expect("registered");
        // Minute 0 opens at 200.00 and rises to 200.10; minute 1 falls back to
        // 200.05 and never makes a new extreme after that.
        let mut quotes = Vec::new();
        quotes.push(quote_at(&scope, 0, 20_000));
        quotes.push(quote_at(&scope, 30, 20_010));
        quotes.push(quote_at(&scope, 90, 20_005));
        for second in 2..10 {
            quotes.push(quote_at(&scope, second * 60 + 5, 20_005));
        }
        let cutoffs = [cutoff_for(&scope, 10, Side::High)];
        let mut family = A2SessionState::default();
        let values = drive(&mut family, &quotes, &[], &cutoffs);
        let values = row(&values, 0);
        // Range = 10_000 * ln(200.10 / 200.00) = 4.9988 bps.
        let expected_range = 10_000.0 * (20_010.0_f64 / 20_000.0).ln();
        assert!(
            (f64::from(values[1]) - expected_range).abs() < 1e-3,
            "session_range_so_far_bps was {}",
            values[1]
        );
        // Mid is 200.05, halfway between 200.00 and 200.10.
        assert!((values[2] - 0.5).abs() < 1e-6, "pos_in_range");
        // One new high (200.10 in minute 0), zero new lows.
        assert!((values[3] - 1.0).abs() < 1e-6, "highs_count");
        assert!((values[4] - 0.0).abs() < 1e-6, "lows_count");
        // The high was set in minute 0; the cutoff closes minute 9.
        assert!((values[5] - 9.0).abs() < 1e-6, "mins_since_high");
        assert!((values[6] - 9.0).abs() < 1e-6, "mins_since_low");
        // 9 minutes after a 5-minute lookback, so no expansion.
        assert!((values[21] - 0.0).abs() < 1e-6, "range_expansion_flag");
    }

    #[test]
    fn confirm_counts_come_from_the_announced_cutoffs_and_exclude_self() {
        let scope = calendar::admit(DEV_DAY).expect("registered");
        let quotes: Vec<QuoteEvent> = (0..40)
            .map(|minute| quote_at(&scope, minute * 60 + 1, 20_000))
            .collect();
        let cutoffs = [
            cutoff_for(&scope, 5, Side::High),
            cutoff_for(&scope, 9, Side::Low),
            cutoff_for(&scope, 17, Side::High),
        ];
        let mut family = A2SessionState::default();
        let values = drive(&mut family, &quotes, &[], &cutoffs);
        // First HIGH: no prior action at all.
        assert!((row(&values, 0)[11] - 0.0).abs() < 1e-6, "same-side #1");
        assert!((row(&values, 0)[12] - 0.0).abs() < 1e-6, "opp-side #1");
        assert!(row(&values, 0)[16].is_nan(), "no prior same-side cutoff");
        // The LOW sees one prior HIGH as an opposite-side confirmation.
        assert!((row(&values, 1)[11] - 0.0).abs() < 1e-6, "same-side #2");
        assert!((row(&values, 1)[12] - 1.0).abs() < 1e-6, "opp-side #2");
        // The second HIGH sees one same-side and one opposite-side prior.
        assert!((row(&values, 2)[11] - 1.0).abs() < 1e-6, "same-side #3");
        assert!((row(&values, 2)[12] - 1.0).abs() < 1e-6, "opp-side #3");
        assert!(
            (row(&values, 2)[16] - 12.0).abs() < 1e-6,
            "17 - 5 minutes since the last HIGH"
        );
    }

    #[test]
    fn fixed_windows_are_absent_until_they_have_fully_elapsed() {
        let scope = calendar::admit(DEV_DAY).expect("registered");
        let quotes: Vec<QuoteEvent> = (0..40)
            .map(|minute| quote_at(&scope, minute * 60 + 1, 20_000 + minute))
            .collect();
        let early = [cutoff_for(&scope, 29, Side::High)];
        let mut family = A2SessionState::default();
        let values = drive(&mut family, &quotes, &[], &early);
        assert!(values[13].is_nan(), "first30 before minute 30");
        assert!(values[14].is_nan(), "last30 before minute 30");

        let late = [cutoff_for(&scope, 30, Side::High)];
        let mut family = A2SessionState::default();
        let values = drive(&mut family, &quotes, &[], &late);
        assert!(values[13].is_finite(), "first30 at minute 30");
        assert!(values[14].is_finite(), "last30 at minute 30");
        assert!(
            (values[13] - values[14]).abs() < 1e-6,
            "at minute 30 the first and last 30-minute windows are the same bars"
        );
    }

    #[test]
    fn vwap_distance_is_absent_before_the_first_print_and_signed_after_it() {
        let scope = calendar::admit(DEV_DAY).expect("registered");
        let quotes: Vec<QuoteEvent> = (0..12)
            .map(|minute| quote_at(&scope, minute * 60 + 1, 20_100))
            .collect();
        let cutoffs = [cutoff_for(&scope, 3, Side::High)];
        let mut family = A2SessionState::default();
        let values = drive(&mut family, &quotes, &[], &cutoffs);
        assert!(values[7].is_nan(), "no prints yet");

        // One print at 200.00 while the mid stands at 201.00: the mid is ABOVE
        // the VWAP, so the distance is positive.
        let trades = [trade_at(&scope, 30, 20_000, 500)];
        let mut family = A2SessionState::default();
        let values = drive(&mut family, &quotes, &trades, &cutoffs);
        let expected = 10_000.0 * (20_100.0_f64 / 20_000.0).ln();
        assert!(
            (f64::from(values[7]) - expected).abs() < 1e-3,
            "vwap_dist_bps was {}",
            values[7]
        );
    }

    #[test]
    fn a_quote_with_a_dead_side_is_counted_and_skipped() {
        let scope = calendar::admit(DEV_DAY).expect("registered");
        let mut quotes = vec![quote_at(&scope, 0, 20_000)];
        // A one-sided book: the midpoint would be 100.00 and would set an
        // absurd session low if it were admitted.
        quotes.push(QuoteEvent {
            ts_ms_b: scope.open_ms_b() + 10_000,
            bid_u6: 0,
            ask_u6: 200_000_000,
            bid_shares: 0,
            ask_shares: 100,
        });
        quotes.push(quote_at(&scope, 20, 20_002));
        let cutoffs = [cutoff_for(&scope, 2, Side::High)];
        let mut family = A2SessionState::default();
        let values = drive(&mut family, &quotes, &[], &cutoffs);
        let expected = 10_000.0 * (20_002.0_f64 / 20_000.0).ln();
        assert!(
            (f64::from(values[1]) - expected).abs() < 1e-3,
            "the dead-sided quote leaked into the session range: {}",
            values[1]
        );
    }

    #[test]
    fn a_quote_less_minute_is_carried_dense_not_dropped() {
        let scope = calendar::admit(DEV_DAY).expect("registered");
        // Quotes in minute 0 and minute 4 only; minutes 1-3 are empty.
        let quotes = vec![
            quote_at(&scope, 10, 20_000),
            quote_at(&scope, 4 * 60 + 10, 20_020),
        ];
        let cutoffs = [cutoff_for(&scope, 6, Side::High)];
        let mut family = A2SessionState::default();
        let values = drive(&mut family, &quotes, &[], &cutoffs);
        assert!(values.iter().all(|value| !value.is_infinite()));
        let tape = family.tape();
        // Minutes 1-3 are carried, and so is minute 5: the cutoff of bar 6
        // seals through minute 5 and nothing quoted after minute 4.
        assert_eq!(tape.carried_bars(), 4, "minutes 1, 2, 3 and 5 were carried");
        // Bar 3 carries minute 0's close; bar 4 holds the new print.
        assert_eq!(tape.bar_at(3).map(|bar| bar.close_u6), Some(200_000_000));
        assert_eq!(tape.bar_at(4).map(|bar| bar.close_u6), Some(200_200_000));
    }

    #[test]
    fn the_open_anchor_is_recovered_from_the_cutoff_itself() {
        let scope = calendar::admit(DEV_DAY).expect("registered");
        let mut tape = MinuteTape::new();
        tape.on_quote(&quote_at(&scope, 5, 20_000));
        let cutoff = cutoff_for(&scope, 7, Side::Low);
        assert_eq!(tape.anchor_and_seal(&cutoff), 7);
        // Session minute 0 is the open minute, so its bar exists and every
        // later index lines up with the wall clock.
        assert!(tape.bar_at(0).is_some());
        assert_eq!(tape.price_at(0), Some(200_000_000));
        assert!(tape.bar_at(7).is_none(), "minute 7 is not complete yet");
    }

    #[test]
    fn every_announced_cutoff_gets_one_row_even_with_an_empty_tape() {
        let scope = calendar::admit(DEV_DAY).expect("registered");
        let cutoffs = [
            cutoff_for(&scope, 1, Side::High),
            cutoff_for(&scope, 2, Side::Low),
        ];
        let mut family = A2SessionState::default();
        let values = drive(&mut family, &[], &[], &cutoffs);
        assert_eq!(values.len(), cutoffs.len() * COLUMNS.len());
        assert!(
            values.iter().all(|value| !value.is_infinite()),
            "an empty tape must produce absence, never an infinity"
        );
    }

    #[test]
    fn real_session_emits_one_finite_or_absent_row_per_action() {
        let mut family = A2SessionState::default();
        let (values, cutoff_count) = super::test_support::drive_real_session(&mut family, DEV_DAY);
        assert_eq!(values.len(), cutoff_count * COLUMNS.len());
        assert!(
            values.iter().all(|value| !value.is_infinite()),
            "a real session produced an infinity"
        );
        let tape = family.tape();
        let (quotes, trades) = tape.event_counts();
        assert!(quotes > 1_000_000, "only {quotes} usable quotes on {DEV_DAY}");
        assert!(trades > 100_000, "only {trades} prints on {DEV_DAY}");
        // Every emitted row must carry a real session range: the tape is
        // dense enough that this column is never absent after minute 1.
        for index in 0..cutoff_count {
            assert!(
                row(&values, index)[1].is_finite(),
                "row {index} has no session range"
            );
        }
    }
}
