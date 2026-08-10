//! `h1_quality` — per-action data-quality state, as of each cutoff.
//!
//! This family answers "how much should the other families' numbers be trusted
//! at this instant?" — how long the tape went silent, how stale the standing
//! quote is, whether only wide quotes were available, and whether the quote
//! rate is anywhere near this session's own norm.
//!
//! ## FLAG: `schema_era_flag` is unobservable in-pass
//!
//! [`FamilyEmitter`] shows a family three things — a [`QuoteEvent`], a
//! [`TradeEvent`] and an [`ActionCutoff`] — and none of them names the reader
//! profile that decoded the file. `select_v2::sources` resolves the schema
//! profile per file, but that resolution is not carried onto the events, so a
//! family cannot see which era it is reading. The column is therefore emitted
//! `NaN` for every row, exactly as the lane specification directs for this
//! case, and it is the one always-absent column here that does **not** carry
//! the `_d` suffix: it is not waiting on daily context, it is waiting on the
//! event stream to expose the profile. Closing it needs a field on
//! [`QuoteEvent`]/[`TradeEvent`] or a session-level hook on the trait — both
//! outside this lane's ownership.
//!
//! ## "Wide-only", not "wide"
//!
//! `wide_only_share_5m` is deliberately not `d1_liquidity_cost`'s
//! `wide_share_15m` at a shorter horizon. It is the share of **minutes** in
//! which *every* quote was wider than 50 bps — that is, minutes in which no
//! tight quote was available at all. That is a data-availability fact, which is
//! what this family is for; the share of individual wide quotes is a cost fact,
//! and lives in D1.
//!
//! ## Absence
//!
//! A window with no minute of data is `NaN`, never `0.0`. The three modality
//! masks need trailing sessions and the options/RUTW/greeks corpora, neither of
//! which this stock-tape pass reads; they are declared
//! [`AsOfRule::PriorSessionsOnly`], emitted `NaN`, and carry the `_d` suffix
//! the daily-context post-pass selects on.

use super::{AsOfRule, ColSpec, FamilyEmitter, FamilyRows, QuoteEvent, TradeEvent, Unit};
use crate::book::ActionCutoff;
use crate::error::{Result, SelectV2Error};
use std::collections::VecDeque;

/// Registered name.
pub const NAME: &str = "h1_quality";

/// Milliseconds in one minute bar.
const MS_PER_MINUTE: i64 = 60_000;
/// Nanoseconds in one minute bar.
const NS_PER_MINUTE: i64 = 60_000_000_000;
/// Milliseconds in one second.
const MS_PER_SECOND: f64 = 1_000.0;
/// Long window, in minutes.
const LONG_WINDOW_MIN: i64 = 15;
/// Short window, in minutes.
const SHORT_WINDOW_MIN: i64 = 5;
/// Sealed minutes retained: the 15-minute window plus the live one.
const RING_MINUTES: usize = 15;
/// `spread_bps > 50` without a division: `spread * 200 > mid`.
const WIDE_SPREAD_FACTOR: i64 = 200;

/// The 8 emitted columns, in emitted order.
const COLUMNS: [ColSpec; 8] = [
    ColSpec::new(
        "options_present_flag_d",
        Unit::Flag,
        AsOfRule::PriorSessionsOnly,
    ),
    ColSpec::new(
        "rutw_present_flag_d",
        Unit::Flag,
        AsOfRule::PriorSessionsOnly,
    ),
    ColSpec::new(
        "greeks_present_flag_d",
        Unit::Flag,
        AsOfRule::PriorSessionsOnly,
    ),
    ColSpec::new(
        "token_gap_seconds_max_15m",
        Unit::Seconds,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "last_quote_staleness_ms",
        Unit::Seconds,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "wide_only_share_5m",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    // Always `NaN`: the event stream does not expose the reader profile. See
    // the FLAG in this module's header.
    ColSpec::new("schema_era_flag", Unit::Flag, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new(
        "quote_rate_vs_session_med_5m",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
];

/// One minute of tape-quality state.
#[derive(Clone, Copy, Debug)]
struct MinuteAgg {
    /// Absolute minute, `ts_ms_b / 60_000`.
    minute: i64,
    quotes: u64,
    /// Quotes wider than 50 bps of their own midpoint.
    wide: u64,
    /// Largest inter-event silence closing inside this minute, in ms.
    max_gap_ms: i64,
}

impl MinuteAgg {
    const fn new(minute: i64) -> Self {
        Self {
            minute,
            quotes: 0,
            wide: 0,
            max_gap_ms: 0,
        }
    }
}

/// Rolling 16-minute quality state plus the session's own quote-rate norm.
#[derive(Debug)]
pub struct H1Quality {
    /// Sealed minutes, oldest first; at most [`RING_MINUTES`].
    ring: VecDeque<MinuteAgg>,
    live: MinuteAgg,
    started: bool,
    first_event_ms: Option<i64>,
    first_minute: Option<i64>,
    last_event_ms: Option<i64>,
    last_quote_ms: Option<i64>,
    /// Per-minute quote counts, one entry per sealed minute.
    session_quotes: Vec<f64>,
    /// Every minute strictly below this is already in [`Self::session_quotes`].
    sealed_through: i64,
    session_dirty: bool,
    session_quote_median: Option<f64>,
    sort_scratch: Vec<f64>,
    rows: Vec<f32>,
}

impl Default for H1Quality {
    fn default() -> Self {
        Self {
            ring: VecDeque::with_capacity(RING_MINUTES),
            live: MinuteAgg::new(i64::MIN),
            started: false,
            first_event_ms: None,
            first_minute: None,
            last_event_ms: None,
            last_quote_ms: None,
            session_quotes: Vec::with_capacity(400),
            sealed_through: i64::MIN,
            session_dirty: true,
            session_quote_median: None,
            sort_scratch: Vec::with_capacity(400),
            rows: Vec::new(),
        }
    }
}

impl FamilyEmitter for H1Quality {
    fn name(&self) -> &'static str {
        NAME
    }

    fn columns(&self) -> &[ColSpec] {
        &COLUMNS
    }

    fn on_quote(&mut self, quote: &QuoteEvent) {
        self.observe(quote.ts_ms_b);
        self.live.quotes += 1;
        // Exactly `spread_bps > 50`, by integer arithmetic.
        let spread = quote.ask_u6 - quote.bid_u6;
        let mid = i64::midpoint(quote.bid_u6, quote.ask_u6);
        if spread.saturating_mul(WIDE_SPREAD_FACTOR) > mid {
            self.live.wide += 1;
        }
        self.last_quote_ms = Some(quote.ts_ms_b);
    }

    fn on_trade(&mut self, trade: &TradeEvent) {
        // Prints are tape too: a silence in the print stream is a token gap
        // whether or not quotes kept flowing.
        self.observe(trade.ts_ms_b);
    }

    fn on_cutoff(&mut self, cutoff: &ActionCutoff) {
        let minute = cutoff.cutoff_ns_b.div_euclid(NS_PER_MINUTE);
        self.seal_complete_minutes(minute);
        let row = self.snapshot(minute, cutoff.cutoff_ns_b.div_euclid(1_000_000));
        self.rows.extend_from_slice(&row);
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

impl H1Quality {
    /// The common per-event path: roll the minute, then close the gap that ends
    /// at this event.
    fn observe(&mut self, ts_ms: i64) {
        let minute = ts_ms.div_euclid(MS_PER_MINUTE);
        if minute != self.live.minute {
            self.roll_to(minute);
        }
        if self.first_event_ms.is_none() {
            self.first_event_ms = Some(ts_ms);
            self.first_minute = Some(minute);
        }
        if let Some(previous) = self.last_event_ms {
            // The gap is attributed to the minute the silence ENDED in, so a
            // silence that spans a window edge is visible from inside it.
            let gap = ts_ms - previous;
            if gap > self.live.max_gap_ms {
                self.live.max_gap_ms = gap;
            }
        }
        self.last_event_ms = Some(ts_ms);
    }

    /// Closes the live minute and opens `minute`.
    fn roll_to(&mut self, minute: i64) {
        if self.started {
            let finished = std::mem::replace(&mut self.live, MinuteAgg::new(minute));
            self.record_session(finished);
            self.ring.push_back(finished);
            if self.ring.len() > RING_MINUTES {
                self.ring.pop_front();
            }
        } else {
            self.live = MinuteAgg::new(minute);
            self.started = true;
        }
    }

    /// Adds a completed minute to the session-long vector, once.
    fn record_session(&mut self, agg: MinuteAgg) {
        if agg.minute < self.sealed_through || agg.quotes == 0 {
            return;
        }
        self.session_quotes.push(as_f64_u64(agg.quotes));
        self.sealed_through = agg.minute + 1;
        self.session_dirty = true;
    }

    /// The live minute is complete once the cutoff has moved past it.
    fn seal_complete_minutes(&mut self, cutoff_minute: i64) {
        if self.started && self.live.minute < cutoff_minute {
            self.record_session(self.live);
        }
    }

    /// Median per-minute quote count over the session so far.
    fn session_quote_median(&mut self) -> Option<f64> {
        if self.session_dirty {
            self.session_quote_median = median_of(&self.session_quotes, &mut self.sort_scratch);
            self.session_dirty = false;
        }
        self.session_quote_median
    }

    /// Minutes of elapsed session inside a `window`-minute lookback.
    fn span_minutes(&self, cutoff_minute: i64, window: i64) -> Option<f64> {
        let first = self.first_minute?;
        let span = window.min(cutoff_minute - first);
        (span > 0).then(|| as_f64(span))
    }

    fn snapshot(&mut self, cutoff_minute: i64, cutoff_ms: i64) -> [f32; COLUMNS.len()] {
        let (mut gap_max_ms, mut quotes_short) = (i64::MIN, 0_u64);
        let (mut wide_only_minutes, mut present_short_minutes) = (0_u64, 0_u64);
        let mut saw_window_minute = false;

        for agg in self.ring.iter().chain(std::iter::once(&self.live)) {
            // Saturating: see `d1_liquidity_cost` -- the untouched sentinel is
            // `i64::MIN` and must not overflow the age subtraction.
            let age = cutoff_minute.saturating_sub(agg.minute);
            if !(1..=LONG_WINDOW_MIN).contains(&age) {
                continue;
            }
            saw_window_minute = true;
            if agg.max_gap_ms > gap_max_ms {
                gap_max_ms = agg.max_gap_ms;
            }
            if age <= SHORT_WINDOW_MIN {
                quotes_short += agg.quotes;
                if agg.quotes > 0 {
                    present_short_minutes += 1;
                    if agg.wide == agg.quotes {
                        wide_only_minutes += 1;
                    }
                }
            }
        }

        // The silence still running at the cutoff is a gap too — and the one
        // most likely to matter. Only its part inside the window counts.
        let window_start_ms = (cutoff_minute - LONG_WINDOW_MIN) * MS_PER_MINUTE;
        let trailing_ms = match (self.first_event_ms, self.last_event_ms) {
            (Some(first), Some(last)) => {
                let from = last.max(window_start_ms).max(first);
                Some((cutoff_ms - from).max(0))
            }
            _ => None,
        };
        let gap_seconds = match trailing_ms {
            Some(trailing) => Some(as_f64(trailing.max(gap_max_ms.max(0))) / MS_PER_SECOND),
            None if saw_window_minute => Some(as_f64(gap_max_ms.max(0)) / MS_PER_SECOND),
            None => None,
        };

        let median = self.session_quote_median();
        let mut row = [f32::NAN; COLUMNS.len()];
        // row[0..3] — the modality masks, filled by the daily-context post-pass.
        row[3] = opt(gap_seconds);
        row[4] = opt(self
            .last_quote_ms
            .map(|last| as_f64((cutoff_ms - last).max(0))));
        row[5] = opt((present_short_minutes > 0)
            .then(|| as_f64_u64(wide_only_minutes) / as_f64_u64(present_short_minutes)));
        // row[6] `schema_era_flag` — unobservable in-pass; see the module FLAG.
        row[7] = opt(
            match (self.span_minutes(cutoff_minute, SHORT_WINDOW_MIN), median) {
                (Some(span), Some(median)) if median > 0.0 => {
                    Some(as_f64_u64(quotes_short) / span / median)
                }
                _ => None,
            },
        );
        row
    }
}

/// Lower median of `values`, using `scratch` so no allocation happens per
/// cutoff.
fn median_of(values: &[f64], scratch: &mut Vec<f64>) -> Option<f64> {
    if values.is_empty() {
        return None;
    }
    scratch.clear();
    scratch.extend_from_slice(values);
    scratch.sort_by(f64::total_cmp);
    Some(scratch[(scratch.len() - 1) / 2])
}

/// Narrows an intermediate to the emitted `f32`, mapping any non-finite value
/// to `NaN`: the leaf contract admits absence, never a signed infinity.
#[allow(clippy::cast_possible_truncation)]
fn narrow(value: f64) -> f32 {
    if !value.is_finite() {
        return f32::NAN;
    }
    let narrowed = value as f32;
    if narrowed.is_finite() { narrowed } else { f32::NAN }
}

/// `None` is absence, and absence is `NaN`.
fn opt(value: Option<f64>) -> f32 {
    value.map_or(f32::NAN, narrow)
}

/// Millisecond offsets within a session are far below `2^53`.
#[allow(clippy::cast_precision_loss)]
fn as_f64(value: i64) -> f64 {
    value as f64
}

/// Per-minute quote counts reach ~4.3e4, well below `2^53`.
#[allow(clippy::cast_precision_loss)]
fn as_f64_u64(value: u64) -> f64 {
    value as f64
}

#[cfg(test)]
mod tests {
    use super::{COLUMNS, H1Quality, MS_PER_MINUTE, NAME, NS_PER_MINUTE};
    use crate::book::{ActionCutoff, Side};
    use crate::families::{AsOfRule, FamilyEmitter, QuoteEvent, TradeEvent};

    /// $200.00 in u6.
    const TWO_HUNDRED: i64 = 200_000_000;
    /// One cent in u6.
    const CENT: i64 = 10_000;

    fn cutoff_at(minute: i64) -> ActionCutoff {
        ActionCutoff {
            action_id: format!("test-{minute}"),
            day: "2022-03-01",
            session_ordinal: 0,
            cutoff_bar_ordinal: 1,
            side: Side::High,
            cutoff_ns_a: minute * NS_PER_MINUTE,
            cutoff_ns_b: minute * NS_PER_MINUTE,
            first_visibility_ns: 0,
            last_visibility_ns: 0,
            act_set: crate::book::ActSetSummary::default(),
        }
    }

    fn quote_ms(ts_ms: i64, spread_u6: i64) -> QuoteEvent {
        QuoteEvent {
            ts_ms_b: ts_ms,
            bid_u6: TWO_HUNDRED - spread_u6 / 2,
            ask_u6: TWO_HUNDRED + spread_u6 / 2,
            bid_shares: 500,
            ask_shares: 500,
        }
    }

    fn trade_ms(ts_ms: i64) -> TradeEvent {
        TradeEvent {
            ts_ms_b: ts_ms,
            price_u6: TWO_HUNDRED,
            size: 100,
            exchange: 1,
            condition: 0,
            sequence: 1,
            bid_u6: TWO_HUNDRED - CENT / 2,
            ask_u6: TWO_HUNDRED + CENT / 2,
            bid_shares: 500,
            ask_shares: 500,
            quote_present: true,
        }
    }

    fn column(row: &[f32], name: &str) -> f32 {
        let index = COLUMNS
            .iter()
            .position(|spec| spec.name == name)
            .unwrap_or_else(|| panic!("{name} is not a {NAME} column"));
        row[index]
    }

    fn close(actual: f32, expected: f64, tolerance: f64) {
        assert!(
            f64::from(actual).is_finite(),
            "expected {expected}, got {actual}"
        );
        assert!(
            (f64::from(actual) - expected).abs() <= tolerance,
            "expected {expected} +- {tolerance}, got {actual}"
        );
    }

    fn row_after(family: &mut H1Quality, minute: i64) -> Vec<f32> {
        family.on_cutoff(&cutoff_at(minute));
        family.emit(&[cutoff_at(minute)]).expect("one row").values
    }

    /// Quotes at :00, :10 and :40 leave a 30-second silence, the largest in the
    /// window; the cutoff at the next minute adds a 20-second trailing gap,
    /// which does not beat it.
    #[test]
    fn the_largest_silence_in_the_window_is_hand_computable() {
        let mut family = H1Quality::default();
        family.on_quote(&quote_ms(100 * MS_PER_MINUTE, CENT));
        family.on_quote(&quote_ms(100 * MS_PER_MINUTE + 10_000, CENT));
        family.on_quote(&quote_ms(100 * MS_PER_MINUTE + 40_000, CENT));
        let row = row_after(&mut family, 101);
        close(column(&row, "token_gap_seconds_max_15m"), 30.0, 1e-6);
        // The cutoff is 20 s after the last quote.
        close(column(&row, "last_quote_staleness_ms"), 20_000.0, 0.0);
    }

    /// A silence still running at the cutoff is the gap that matters most, and
    /// it wins when it is the longest.
    #[test]
    fn the_trailing_silence_counts_as_a_gap() {
        let mut family = H1Quality::default();
        family.on_quote(&quote_ms(100 * MS_PER_MINUTE, CENT));
        family.on_quote(&quote_ms(100 * MS_PER_MINUTE + 5_000, CENT));
        // Cutoff two minutes later: 115 s of silence since the last event.
        let row = row_after(&mut family, 102);
        close(column(&row, "token_gap_seconds_max_15m"), 115.0, 1e-6);
        close(column(&row, "last_quote_staleness_ms"), 115_000.0, 0.0);
    }

    /// Prints are tape: a gap closed by a print is a gap.
    #[test]
    fn a_print_closes_a_token_gap_but_not_quote_staleness() {
        let mut family = H1Quality::default();
        family.on_quote(&quote_ms(100 * MS_PER_MINUTE, CENT));
        family.on_trade(&trade_ms(100 * MS_PER_MINUTE + 25_000));
        family.on_trade(&trade_ms(100 * MS_PER_MINUTE + 30_000));
        let row = row_after(&mut family, 101);
        // Longest silence is quote->print, 25 s; trailing is 30 s and wins.
        close(column(&row, "token_gap_seconds_max_15m"), 30.0, 1e-6);
        // The last QUOTE is 60 s old even though prints kept arriving.
        close(column(&row, "last_quote_staleness_ms"), 60_000.0, 0.0);
    }

    /// "Wide-only" is a per-minute availability fact: a minute counts only when
    /// EVERY quote in it was wide. One tight quote rescues the minute.
    #[test]
    fn wide_only_counts_minutes_with_no_tight_quote_at_all() {
        let mut family = H1Quality::default();
        // Minute 100: every quote wide (a $2.00 spread is 100 bps).
        family.on_quote(&quote_ms(100 * MS_PER_MINUTE, 200 * CENT));
        family.on_quote(&quote_ms(100 * MS_PER_MINUTE + 1_000, 200 * CENT));
        // Minute 101: wide, then one tight quote.
        family.on_quote(&quote_ms(101 * MS_PER_MINUTE, 200 * CENT));
        family.on_quote(&quote_ms(101 * MS_PER_MINUTE + 1_000, CENT));
        // Minute 102: all tight.
        family.on_quote(&quote_ms(102 * MS_PER_MINUTE, CENT));
        let row = row_after(&mut family, 103);
        // One of three present minutes was wide-only.
        close(column(&row, "wide_only_share_5m"), 1.0 / 3.0, 1e-6);
    }

    /// The rate is measured against this session's own median minute, so a
    /// session of identical minutes reports exactly one.
    #[test]
    fn the_quote_rate_is_relative_to_the_sessions_own_median_minute() {
        let mut family = H1Quality::default();
        for minute in 100..110 {
            for second in 0..10 {
                family.on_quote(&quote_ms(minute * MS_PER_MINUTE + second * 1_000, CENT));
            }
        }
        let row = row_after(&mut family, 110);
        close(column(&row, "quote_rate_vs_session_med_5m"), 1.0, 1e-6);

        // Double the rate in the last five minutes and the ratio doubles: the
        // median of 10 quiet + 5 busy minutes is still the quiet minute.
        let mut family = H1Quality::default();
        for minute in 100..110 {
            for second in 0..10 {
                family.on_quote(&quote_ms(minute * MS_PER_MINUTE + second * 1_000, CENT));
            }
        }
        for minute in 110..115 {
            for tick in 0..20 {
                family.on_quote(&quote_ms(minute * MS_PER_MINUTE + tick * 500, CENT));
            }
        }
        let row = row_after(&mut family, 115);
        close(column(&row, "quote_rate_vs_session_med_5m"), 2.0, 1e-6);
    }

    /// **The `schema_era_flag` FLAG, asserted rather than asserted-in-prose.**
    /// It is `NaN` because no event carries the reader profile. If a future
    /// change puts the profile on the event stream, this test is the thing that
    /// should fail and force the column to be computed.
    #[test]
    fn schema_era_is_absent_because_the_event_stream_cannot_show_it() {
        let mut family = H1Quality::default();
        family.on_quote(&quote_ms(100 * MS_PER_MINUTE, CENT));
        let row = row_after(&mut family, 101);
        assert!(column(&row, "schema_era_flag").is_nan());
        // ...and it is the ONLY always-absent column here without a `_d` marker.
        let unmarked_absent: Vec<&str> = COLUMNS
            .iter()
            .enumerate()
            .filter(|(index, spec)| row[*index].is_nan() && !spec.name.ends_with("_d"))
            .map(|(_, spec)| spec.name)
            .collect();
        assert_eq!(unmarked_absent, vec!["schema_era_flag"]);
    }

    /// A family shown nothing emits absence, not zero.
    #[test]
    fn an_untouched_family_emits_an_all_absent_row() {
        let mut family = H1Quality::default();
        let row = row_after(&mut family, 101);
        assert!(row.iter().all(|value| value.is_nan()));
    }

    /// Only the trailing 15 minutes are in scope for the gap census.
    #[test]
    fn windows_do_not_reach_past_their_horizon() {
        let mut family = H1Quality::default();
        family.on_quote(&quote_ms(100 * MS_PER_MINUTE, CENT));
        for minute in 101..=124 {
            family.on_quote(&quote_ms(minute * MS_PER_MINUTE, CENT));
        }
        let row = row_after(&mut family, 125);
        // Every minute in the window carried a quote at :00, so the largest
        // silence is exactly one minute.
        close(column(&row, "token_gap_seconds_max_15m"), 60.0, 1e-6);
        // No minute was wide-only.
        close(column(&row, "wide_only_share_5m"), 0.0, 0.0);
    }

    /// A window that predates the session's first event does not stretch the
    /// gap: silence before the tape started is not a tape gap.
    #[test]
    fn silence_before_the_first_event_is_not_a_gap() {
        let mut family = H1Quality::default();
        family.on_quote(&quote_ms(100 * MS_PER_MINUTE + 30_000, CENT));
        let row = row_after(&mut family, 101);
        // 30 s from the first (and only) event to the cutoff, not 90 s.
        close(column(&row, "token_gap_seconds_max_15m"), 30.0, 1e-6);
    }

    #[test]
    fn prior_session_columns_are_exactly_the_d_suffixed_ones() {
        let mut family = H1Quality::default();
        family.on_quote(&quote_ms(100 * MS_PER_MINUTE, CENT));
        let row = row_after(&mut family, 101);
        let mut prior = 0_usize;
        for (index, spec) in COLUMNS.iter().enumerate() {
            let is_prior = spec.as_of == AsOfRule::PriorSessionsOnly;
            assert_eq!(
                is_prior,
                spec.name.ends_with("_d"),
                "{} disagrees with its as-of rule",
                spec.name
            );
            if is_prior {
                assert!(row[index].is_nan(), "{} must be left to python", spec.name);
                prior += 1;
            }
        }
        assert_eq!(prior, 3, "the daily-context post-pass owns three columns");
    }

    #[test]
    fn the_declared_width_is_what_gets_emitted() {
        assert_eq!(COLUMNS.len(), 8);
        assert!(COLUMNS.len() <= crate::families::MAX_FAMILY_COLUMNS);
        let mut names: Vec<&str> = COLUMNS.iter().map(|spec| spec.name).collect();
        names.sort_unstable();
        names.dedup();
        assert_eq!(names.len(), COLUMNS.len(), "column names must be unique");
    }

    #[test]
    fn emit_refuses_a_row_count_that_does_not_match_the_cutoffs() {
        let mut family = H1Quality::default();
        family.on_cutoff(&cutoff_at(101));
        let refusal = family
            .emit(&[cutoff_at(101), cutoff_at(102)])
            .expect_err("one row for two cutoffs must refuse");
        assert!(matches!(
            refusal,
            crate::error::SelectV2Error::ContentMismatch { .. }
        ));
    }
}
