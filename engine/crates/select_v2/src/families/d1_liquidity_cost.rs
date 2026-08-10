//! `d1_liquidity_cost` — NBBO cost and depth state, as of each cutoff.
//!
//! ## Why the medians are histograms
//!
//! Measured on 2022-03-01: **16,984,301 RTH quotes in one session**, ~42,500 per
//! minute. A 15-minute window therefore holds ~640,000 spreads, so neither
//! storing them nor sorting them per action is affordable — 778 actions x a
//! 640k sort is three orders over the whole per-session budget. Spreads are
//! instead accumulated into a per-minute histogram at 0.01 bps resolution and
//! merged across the window at each cutoff, which makes the per-quote cost a
//! single increment and the per-cutoff cost a fixed 2,049-bucket scan.
//!
//! The median is reported at its bucket's **lower edge**, so the estimate is
//! deterministic, never above the true median, and exact to within 0.01 bps.
//! Buckets cover 0..20.48 bps; a window whose median exceeds that saturates at
//! [`SATURATION_BPS`] rather than reporting a number it cannot resolve.
//! `wide_share_15m` does not depend on the histogram — it is an exact integer
//! test — so the saturation ceiling cannot distort the wide-quote census.
//!
//! ## The hot path is integer
//!
//! At 16.6M quotes per session the whole family gets tens of nanoseconds per
//! event, so `on_quote` avoids floating point except for one multiply:
//!
//! * "is this quote wide?" is `spread_u6 * 200 > mid_u6`, which is exactly
//!   `spread_bps > 50` with no division;
//! * the histogram index is `spread_u6 * inv_mid`, where `inv_mid` is
//!   recomputed only when the midpoint itself changes. Caching on the midpoint
//!   is exact, not approximate: the reciprocal is a pure function of the value
//!   it is keyed on.
//!
//! The per-cutoff row is likewise cached on `cutoff_ns_b` and invalidated by
//! any event, so the several actions sharing one cutoff instant merge their
//! windows once. That is exact for the same reason: the row is a pure function
//! of family state, and only an event can change it.
//!
//! ## Absence and infinities
//!
//! A window with no quote yields `NaN`, never `0.0`. Every ratio guards its
//! denominator, and [`narrow`] turns any non-finite intermediate into `NaN`, so
//! no emitted cell can carry a signed infinity. Three columns need trailing
//! sessions (`depth_vs_20d_d`, `exp_rt_cost_bps_d`, `cost_over_move_d`); they
//! are declared [`AsOfRule::PriorSessionsOnly`], emitted `NaN`, and carry the
//! `_d` suffix the daily-context post-pass selects on.

use super::{AsOfRule, ColSpec, FamilyEmitter, FamilyRows, QuoteEvent, TradeEvent, Unit};
use crate::book::ActionCutoff;
use crate::error::{Result, SelectV2Error};
use std::collections::VecDeque;

/// Registered name.
pub const NAME: &str = "d1_liquidity_cost";

/// Milliseconds in one minute bar.
const MS_PER_MINUTE: i64 = 60_000;
/// Nanoseconds in one minute bar.
const NS_PER_MINUTE: i64 = 60_000_000_000;
/// Seconds in one minute bar.
const SECONDS_PER_MINUTE: f64 = 60.0;
/// Basis points in one unit ratio.
const BPS: f64 = 10_000.0;
/// Long window, in minutes.
const LONG_WINDOW_MIN: i64 = 15;
/// Short window, in minutes.
const SHORT_WINDOW_MIN: i64 = 5;
/// Sealed minutes retained: the 15-minute window plus the live one.
const RING_MINUTES: usize = 15;

/// Resolved histogram buckets, each [`HIST_RESOLUTION_BPS`] wide.
const HIST_VALUE_BUCKETS: usize = 2_048;
/// Bucket width, in bps.
const HIST_RESOLUTION_BPS: f64 = 0.01;
/// Index of the single overflow bucket.
const HIST_OVERFLOW: usize = HIST_VALUE_BUCKETS;
/// Histogram length including the overflow bucket.
const HIST_LEN: usize = HIST_VALUE_BUCKETS + 1;
/// The value a median that lands in the overflow bucket reports.
#[allow(clippy::cast_precision_loss)]
pub const SATURATION_BPS: f64 = HIST_VALUE_BUCKETS as f64 * HIST_RESOLUTION_BPS;

/// `spread_bps > 50` without a division: `spread * 200 > mid`.
const WIDE_SPREAD_FACTOR: i64 = 200;

/// The 16 emitted columns, in emitted order.
const COLUMNS: [ColSpec; 16] = [
    ColSpec::new("spread_bps_now", Unit::Bps, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new(
        "spread_bps_med_5m",
        Unit::Bps,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "spread_bps_med_15m",
        Unit::Bps,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "depth_bid_shares",
        Unit::Shares,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "depth_ask_shares",
        Unit::Shares,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new("depth_log_imb", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("depth_vs_20d_d", Unit::Ratio, AsOfRule::PriorSessionsOnly),
    ColSpec::new(
        "flicker_rate_5m",
        Unit::Count,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "eff_spread_proxy_bps_15m",
        Unit::Bps,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new("exp_rt_cost_bps_d", Unit::Bps, AsOfRule::PriorSessionsOnly),
    ColSpec::new("cost_over_move_d", Unit::Ratio, AsOfRule::PriorSessionsOnly),
    ColSpec::new(
        "locked_crossed_share_15m",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new("wide_share_15m", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new(
        "quote_updates_per_min_15m",
        Unit::Count,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "spread_widening_5m_ratio",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "depth_total_vs_session_med",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
];

/// One minute of quote and print activity.
#[derive(Debug)]
struct MinuteAgg {
    /// Absolute minute, `ts_ms_b / 60_000`.
    minute: i64,
    quotes: u64,
    /// Quotes with `bid >= ask`.
    locked_crossed: u64,
    /// Quotes wider than 50 bps of their own midpoint.
    wide: u64,
    /// Quotes whose bid or ask price differed from the previous quote's.
    flicker: u64,
    /// Sum of `bid_shares + ask_shares` across this minute's quotes.
    depth_total: i64,
    /// Quotes that entered [`Self::spread_hist`].
    spread_samples: u64,
    /// Prints that entered [`Self::eff_hist`].
    eff_samples: u64,
    spread_hist: Box<[u32]>,
    eff_hist: Box<[u32]>,
}

impl MinuteAgg {
    fn new(minute: i64) -> Self {
        Self {
            minute,
            quotes: 0,
            locked_crossed: 0,
            wide: 0,
            flicker: 0,
            depth_total: 0,
            spread_samples: 0,
            eff_samples: 0,
            spread_hist: vec![0_u32; HIST_LEN].into_boxed_slice(),
            eff_hist: vec![0_u32; HIST_LEN].into_boxed_slice(),
        }
    }

    /// Mean total displayed depth over this minute's quotes.
    fn mean_depth(&self) -> Option<f64> {
        (self.quotes > 0).then(|| as_f64(self.depth_total) / as_f64_u64(self.quotes))
    }
}

/// Rolling 16-minute quote/print state plus session-long depth and rate context.
#[derive(Debug)]
pub struct D1LiquidityCost {
    /// Sealed minutes, oldest first; at most [`RING_MINUTES`].
    ring: VecDeque<MinuteAgg>,
    /// The minute currently being filled.
    live: MinuteAgg,
    /// Whether [`Self::live`] has ever been fed.
    started: bool,
    /// First minute that carried a quote — the denominator's left edge.
    first_minute: Option<i64>,
    last_bid_u6: i64,
    last_ask_u6: i64,
    last_bid_shares: i64,
    last_ask_shares: i64,
    has_quote: bool,
    /// Previous quote's prices, for the flicker test.
    previous_bid_u6: i64,
    previous_ask_u6: i64,
    /// Cached reciprocal: bucket index per unit of `spread_u6` at `inv_mid_for`.
    inv_mid: f64,
    inv_mid_for: i64,
    /// Last quote midpoint, the fallback prevailing mid for a print with no
    /// attached NBBO.
    last_mid_u6: i64,
    /// Per-minute mean displayed depth, one entry per sealed minute.
    session_depth: Vec<f64>,
    /// Every minute strictly below this is already in the session vectors.
    sealed_through: i64,
    session_dirty: bool,
    session_depth_median: Option<f64>,
    /// Scratch merge buffers, reused across cutoffs.
    merge_short: Vec<u32>,
    merge_long: Vec<u32>,
    merge_eff: Vec<u32>,
    sort_scratch: Vec<f64>,
    /// Row cache, keyed on the cutoff instant, invalidated by any event.
    cached_key: Option<i64>,
    cached_row: [f32; COLUMNS.len()],
    rows: Vec<f32>,
}

impl Default for D1LiquidityCost {
    fn default() -> Self {
        Self {
            ring: VecDeque::with_capacity(RING_MINUTES),
            live: MinuteAgg::new(i64::MIN),
            started: false,
            first_minute: None,
            last_bid_u6: 0,
            last_ask_u6: 0,
            last_bid_shares: 0,
            last_ask_shares: 0,
            has_quote: false,
            previous_bid_u6: i64::MIN,
            previous_ask_u6: i64::MIN,
            inv_mid: 0.0,
            inv_mid_for: 0,
            last_mid_u6: 0,
            session_depth: Vec::with_capacity(400),
            sealed_through: i64::MIN,
            session_dirty: true,
            session_depth_median: None,
            merge_short: vec![0; HIST_LEN],
            merge_long: vec![0; HIST_LEN],
            merge_eff: vec![0; HIST_LEN],
            sort_scratch: Vec::with_capacity(400),
            cached_key: None,
            cached_row: [f32::NAN; COLUMNS.len()],
            rows: Vec::new(),
        }
    }
}

impl FamilyEmitter for D1LiquidityCost {
    fn name(&self) -> &'static str {
        NAME
    }

    fn columns(&self) -> &[ColSpec] {
        &COLUMNS
    }

    fn on_quote(&mut self, quote: &QuoteEvent) {
        self.cached_key = None;
        let minute = quote.ts_ms_b.div_euclid(MS_PER_MINUTE);
        if minute != self.live.minute {
            self.roll_to(minute);
        }
        if self.first_minute.is_none() {
            self.first_minute = Some(minute);
        }

        let bid = quote.bid_u6;
        let ask = quote.ask_u6;
        let spread = ask - bid;
        let mid = i64::midpoint(bid, ask);

        self.live.quotes += 1;
        self.live.depth_total += quote.bid_shares + quote.ask_shares;
        if bid >= ask {
            self.live.locked_crossed += 1;
        }
        // Exactly `spread_bps > 50`, by integer arithmetic.
        if spread.saturating_mul(WIDE_SPREAD_FACTOR) > mid {
            self.live.wide += 1;
        }
        if bid != self.previous_bid_u6 || ask != self.previous_ask_u6 {
            self.live.flicker += 1;
            self.previous_bid_u6 = bid;
            self.previous_ask_u6 = ask;
        }
        if mid > 0 {
            if mid != self.inv_mid_for {
                // One bucket index per unit of `spread_u6` at this midpoint.
                self.inv_mid = BPS / (as_f64(mid) * HIST_RESOLUTION_BPS);
                self.inv_mid_for = mid;
            }
            let bucket = bucket_of_scaled(as_f64(spread) * self.inv_mid);
            self.live.spread_hist[bucket] += 1;
            self.live.spread_samples += 1;
            self.last_mid_u6 = mid;
        }

        self.last_bid_u6 = bid;
        self.last_ask_u6 = ask;
        self.last_bid_shares = quote.bid_shares;
        self.last_ask_shares = quote.ask_shares;
        self.has_quote = true;
    }

    fn on_trade(&mut self, trade: &TradeEvent) {
        self.cached_key = None;
        let minute = trade.ts_ms_b.div_euclid(MS_PER_MINUTE);
        if minute != self.live.minute {
            self.roll_to(minute);
        }
        // The prevailing midpoint is the NBBO the vendor attached to the print
        // when it attached one; otherwise the last quote this family was shown,
        // which the driver guarantees preceded the print. With neither, the
        // print contributes nothing — absent, not a zero deviation.
        let mid = if trade.quote_present && trade.bid_u6 > 0 && trade.ask_u6 > 0 {
            i64::midpoint(trade.bid_u6, trade.ask_u6)
        } else {
            self.last_mid_u6
        };
        if mid <= 0 {
            return;
        }
        let deviation = (trade.price_u6 - mid).abs();
        let eff_bps = 2.0 * as_f64(deviation) * BPS / as_f64(mid);
        self.live.eff_hist[bucket_of_scaled(eff_bps / HIST_RESOLUTION_BPS)] += 1;
        self.live.eff_samples += 1;
    }

    fn on_cutoff(&mut self, cutoff: &ActionCutoff) {
        let key = cutoff.cutoff_ns_b;
        if self.cached_key != Some(key) {
            let minute = key.div_euclid(NS_PER_MINUTE);
            self.seal_complete_minutes(minute);
            self.cached_row = self.snapshot(minute);
            self.cached_key = Some(key);
        }
        let row = self.cached_row;
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

impl D1LiquidityCost {
    /// Closes the live minute and opens `minute`.
    fn roll_to(&mut self, minute: i64) {
        if self.started {
            self.record_live();
            let finished = std::mem::replace(&mut self.live, MinuteAgg::new(minute));
            self.ring.push_back(finished);
            if self.ring.len() > RING_MINUTES {
                self.ring.pop_front();
            }
        } else {
            self.live = MinuteAgg::new(minute);
            self.started = true;
        }
    }

    /// Adds the live minute to the session-long depth vector, at most once.
    fn record_live(&mut self) {
        let (minute, quotes) = (self.live.minute, self.live.quotes);
        if minute < self.sealed_through || quotes == 0 {
            return;
        }
        if let Some(depth) = self.live.mean_depth() {
            self.session_depth.push(depth);
        }
        self.sealed_through = minute + 1;
        self.session_dirty = true;
    }

    /// The live minute is complete once the cutoff has moved past it, so its
    /// statistics join the session context here rather than waiting for the
    /// next event — which may be minutes away, or may never come.
    fn seal_complete_minutes(&mut self, cutoff_minute: i64) {
        if self.started && self.live.minute < cutoff_minute {
            self.record_live();
        }
    }

    /// Median per-minute mean depth over the session so far.
    fn session_depth_median(&mut self) -> Option<f64> {
        if self.session_dirty {
            self.session_depth_median = median_of(&self.session_depth, &mut self.sort_scratch);
            self.session_dirty = false;
        }
        self.session_depth_median
    }

    /// Minutes of elapsed session inside a `window`-minute lookback — the
    /// denominator a rate is measured against. Silence counts; a window that
    /// predates the session's first quote does not.
    fn span_minutes(&self, cutoff_minute: i64, window: i64) -> Option<f64> {
        let first = self.first_minute?;
        let span = window.min(cutoff_minute - first);
        (span > 0).then(|| as_f64(span))
    }

    /// Merges the window histograms and counters, then builds the row.
    fn snapshot(&mut self, cutoff_minute: i64) -> [f32; COLUMNS.len()] {
        self.merge_short.fill(0);
        self.merge_long.fill(0);
        self.merge_eff.fill(0);
        let (mut quotes_long, mut locked_long, mut wide_long) = (0_u64, 0_u64, 0_u64);
        let (mut short_samples, mut long_samples, mut eff_samples) = (0_u64, 0_u64, 0_u64);
        let mut flicker_short = 0_u64;

        for agg in self.ring.iter().chain(std::iter::once(&self.live)) {
            // Saturating: an untouched family's live minute is the `i64::MIN`
            // sentinel, and `cutoff - i64::MIN` overflows. Saturation puts it
            // far outside every window, which is exactly where it belongs.
            let age = cutoff_minute.saturating_sub(agg.minute);
            if !(1..=LONG_WINDOW_MIN).contains(&age) {
                continue;
            }
            quotes_long += agg.quotes;
            locked_long += agg.locked_crossed;
            wide_long += agg.wide;
            long_samples += agg.spread_samples;
            eff_samples += agg.eff_samples;
            add_into(&mut self.merge_long, &agg.spread_hist);
            add_into(&mut self.merge_eff, &agg.eff_hist);
            if age <= SHORT_WINDOW_MIN {
                flicker_short += agg.flicker;
                short_samples += agg.spread_samples;
                add_into(&mut self.merge_short, &agg.spread_hist);
            }
        }

        let med_short = histogram_median_bps(&self.merge_short, short_samples);
        let med_long = histogram_median_bps(&self.merge_long, long_samples);
        let eff_median = histogram_median_bps(&self.merge_eff, eff_samples);

        let mid = i64::midpoint(self.last_bid_u6, self.last_ask_u6);
        let spread_now = (self.has_quote && mid > 0)
            .then(|| as_f64(self.last_ask_u6 - self.last_bid_u6) * BPS / as_f64(mid));

        let depth_total = self.last_bid_shares + self.last_ask_shares;
        let depth_median = self.session_depth_median();

        let mut row = [f32::NAN; COLUMNS.len()];
        row[0] = opt(spread_now);
        row[1] = opt(med_short);
        row[2] = opt(med_long);
        row[3] = if self.has_quote {
            narrow(as_f64(self.last_bid_shares))
        } else {
            f32::NAN
        };
        row[4] = if self.has_quote {
            narrow(as_f64(self.last_ask_shares))
        } else {
            f32::NAN
        };
        row[5] = if self.has_quote && self.last_bid_shares > 0 && self.last_ask_shares > 0 {
            narrow((as_f64(self.last_bid_shares) / as_f64(self.last_ask_shares)).ln())
        } else {
            f32::NAN
        };
        // row[6] `depth_vs_20d_d` — prior sessions, left absent.
        row[7] = opt(self
            .span_minutes(cutoff_minute, SHORT_WINDOW_MIN)
            .map(|span| as_f64_u64(flicker_short) / (span * SECONDS_PER_MINUTE)));
        row[8] = opt(eff_median);
        // row[9] `exp_rt_cost_bps_d`, row[10] `cost_over_move_d` — prior sessions.
        row[11] = opt((quotes_long > 0)
            .then(|| as_f64_u64(locked_long) / as_f64_u64(quotes_long)));
        row[12] =
            opt((quotes_long > 0).then(|| as_f64_u64(wide_long) / as_f64_u64(quotes_long)));
        row[13] = opt(self
            .span_minutes(cutoff_minute, LONG_WINDOW_MIN)
            .map(|span| as_f64_u64(quotes_long) / span));
        row[14] = opt(match (med_short, med_long) {
            (Some(short), Some(long)) if long > 0.0 => Some(short / long),
            _ => None,
        });
        row[15] = opt(match depth_median {
            Some(median) if median > 0.0 && self.has_quote => {
                Some(as_f64(depth_total) / median)
            }
            _ => None,
        });
        row
    }
}

/// Accumulates `source` into `target`.
fn add_into(target: &mut [u32], source: &[u32]) {
    for (slot, count) in target.iter_mut().zip(source.iter()) {
        *slot += *count;
    }
}

/// Bucket for an already-scaled value (value in bucket widths). Negative and
/// `NaN` inputs clamp to bucket 0 — a crossed market has a negative spread, and
/// it is `locked_crossed_share_15m` that reports it, not the median.
#[allow(
    clippy::cast_possible_truncation,
    clippy::cast_sign_loss,
    clippy::cast_precision_loss
)]
fn bucket_of_scaled(scaled: f64) -> usize {
    // `NaN` fails every comparison and lands in bucket 0 with the negatives.
    if scaled > 0.0 {
        if scaled >= HIST_VALUE_BUCKETS as f64 {
            HIST_OVERFLOW
        } else {
            scaled as usize
        }
    } else {
        0
    }
}

/// Lower edge, in bps, of the bucket holding the `ceil(total / 2)`-th sample.
/// `None` when the window holds no sample; [`SATURATION_BPS`] when the median
/// lands in the overflow bucket, where the true value is unresolvable.
fn histogram_median_bps(hist: &[u32], total: u64) -> Option<f64> {
    if total == 0 {
        return None;
    }
    let target = total.div_ceil(2);
    let mut cumulative = 0_u64;
    for (index, count) in hist.iter().enumerate() {
        cumulative += u64::from(*count);
        if cumulative >= target {
            if index >= HIST_VALUE_BUCKETS {
                return Some(SATURATION_BPS);
            }
            return Some(as_f64_usize(index) * HIST_RESOLUTION_BPS);
        }
    }
    None
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

/// u6 prices and share counts are far below `2^53`; the `f64` image is exact.
#[allow(clippy::cast_precision_loss)]
fn as_f64(value: i64) -> f64 {
    value as f64
}

/// Per-session quote counts reach ~1.7e7, well below `2^53`.
#[allow(clippy::cast_precision_loss)]
fn as_f64_u64(value: u64) -> f64 {
    value as f64
}

/// Bucket indices are bounded by 2,049.
#[allow(clippy::cast_precision_loss)]
fn as_f64_usize(value: usize) -> f64 {
    value as f64
}

#[cfg(test)]
mod tests {
    use super::{
        COLUMNS, D1LiquidityCost, HIST_RESOLUTION_BPS, MS_PER_MINUTE, NAME, NS_PER_MINUTE,
        SATURATION_BPS,
    };
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

    /// A quote centred on `mid_u6` with a `spread_u6`-wide NBBO.
    fn quote(minute: i64, second: i64, mid_u6: i64, spread_u6: i64) -> QuoteEvent {
        QuoteEvent {
            ts_ms_b: minute * MS_PER_MINUTE + second * 1_000,
            bid_u6: mid_u6 - spread_u6 / 2,
            ask_u6: mid_u6 + spread_u6 / 2,
            bid_shares: 500,
            ask_shares: 500,
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

    fn row_after(family: &mut D1LiquidityCost, minute: i64) -> Vec<f32> {
        family.on_cutoff(&cutoff_at(minute));
        family.emit(&[cutoff_at(minute)]).expect("one row").values
    }

    /// A one-cent NBBO around $200.00 is `0.01 / 200 * 1e4 = 0.5` bps exactly.
    /// The median is reported at its bucket's lower edge, and 0.5 is a bucket
    /// boundary at 0.01 bps resolution, so the expectation is exactly 0.5.
    #[test]
    fn spread_median_and_now_are_hand_computable() {
        let mut family = D1LiquidityCost::default();
        for second in 0..10 {
            family.on_quote(&quote(100, second, TWO_HUNDRED, CENT));
        }
        let row = row_after(&mut family, 101);
        close(column(&row, "spread_bps_now"), 0.5, 1e-6);
        close(column(&row, "spread_bps_med_5m"), 0.5, HIST_RESOLUTION_BPS);
        close(column(&row, "spread_bps_med_15m"), 0.5, HIST_RESOLUTION_BPS);
        // Ten identical quotes over one minute of elapsed session.
        close(column(&row, "quote_updates_per_min_15m"), 10.0, 1e-6);
        // Nothing was locked, crossed or wide -- observed zero, not absence.
        close(column(&row, "locked_crossed_share_15m"), 0.0, 0.0);
        close(column(&row, "wide_share_15m"), 0.0, 0.0);
        // A single spread level: 5m and 15m medians agree exactly.
        close(column(&row, "spread_widening_5m_ratio"), 1.0, 1e-6);
    }

    /// The median splits the sample: five quotes at 0.5 bps and four at 1.0 bps
    /// put the 5th of 9 in the 0.5 bps bucket.
    #[test]
    fn the_median_is_the_lower_median_of_the_window() {
        let mut family = D1LiquidityCost::default();
        for second in 0..5 {
            family.on_quote(&quote(100, second, TWO_HUNDRED, CENT));
        }
        for second in 5..9 {
            family.on_quote(&quote(100, second, TWO_HUNDRED, 2 * CENT));
        }
        let row = row_after(&mut family, 101);
        close(column(&row, "spread_bps_med_15m"), 0.5, HIST_RESOLUTION_BPS);

        // One more wide quote moves the 5th of 10 to the 1.0 bps bucket.
        let mut family = D1LiquidityCost::default();
        for second in 0..5 {
            family.on_quote(&quote(100, second, TWO_HUNDRED, 2 * CENT));
        }
        for second in 5..10 {
            family.on_quote(&quote(100, second, TWO_HUNDRED, CENT));
        }
        let row = row_after(&mut family, 101);
        close(column(&row, "spread_bps_med_15m"), 0.5, HIST_RESOLUTION_BPS);
    }

    /// `spread * 200 > mid` is exactly `spread_bps > 50`. At $200.00 the
    /// boundary is a $1.00 spread: $1.00 is 50 bps and is NOT wide, $1.01 is.
    #[test]
    fn the_wide_test_is_exact_at_its_boundary() {
        let mut family = D1LiquidityCost::default();
        family.on_quote(&quote(100, 0, TWO_HUNDRED, 100 * CENT));
        let row = row_after(&mut family, 101);
        close(column(&row, "wide_share_15m"), 0.0, 0.0);

        let mut family = D1LiquidityCost::default();
        family.on_quote(&quote(100, 0, TWO_HUNDRED, 101 * CENT));
        let row = row_after(&mut family, 101);
        close(column(&row, "wide_share_15m"), 1.0, 0.0);
    }

    /// A locked market has `bid == ask`, a crossed one `bid > ask`; both count,
    /// and a normal quote does not.
    #[test]
    fn locked_and_crossed_quotes_are_both_counted() {
        let mut family = D1LiquidityCost::default();
        family.on_quote(&quote(100, 0, TWO_HUNDRED, CENT));
        family.on_quote(&quote(100, 1, TWO_HUNDRED, 0));
        family.on_quote(&QuoteEvent {
            ts_ms_b: 100 * MS_PER_MINUTE + 2_000,
            bid_u6: TWO_HUNDRED + CENT,
            ask_u6: TWO_HUNDRED,
            bid_shares: 500,
            ask_shares: 500,
        });
        family.on_quote(&quote(100, 3, TWO_HUNDRED, CENT));
        let row = row_after(&mut family, 101);
        close(column(&row, "locked_crossed_share_15m"), 0.5, 1e-6);
    }

    /// Flicker counts NBBO *price* changes per second. Four price changes over
    /// one elapsed minute is 4 / 60 per second; a size-only update is not a
    /// price change and must not count.
    #[test]
    fn flicker_counts_price_changes_not_size_changes() {
        let mut family = D1LiquidityCost::default();
        // First quote is itself a change from "no quote".
        family.on_quote(&quote(100, 0, TWO_HUNDRED, CENT));
        family.on_quote(&quote(100, 10, TWO_HUNDRED + CENT, CENT));
        family.on_quote(&quote(100, 20, TWO_HUNDRED, CENT));
        family.on_quote(&quote(100, 30, TWO_HUNDRED + CENT, CENT));
        // Same prices, different displayed size: not a price change.
        family.on_quote(&QuoteEvent {
            ts_ms_b: 100 * MS_PER_MINUTE + 40_000,
            bid_u6: TWO_HUNDRED + CENT / 2,
            ask_u6: TWO_HUNDRED + CENT + CENT / 2,
            bid_shares: 9_999,
            ask_shares: 9_999,
        });
        let row = row_after(&mut family, 101);
        close(column(&row, "flicker_rate_5m"), 4.0 / 60.0, 1e-6);
    }

    /// The effective-spread proxy is `2 * |price - mid| / mid * 1e4`. A print a
    /// half-cent from a $200.00 mid gives `2 * 0.005 / 200 * 1e4 = 0.5` bps.
    #[test]
    fn effective_spread_proxy_is_twice_the_signed_distance_to_the_mid() {
        let mut family = D1LiquidityCost::default();
        family.on_quote(&quote(100, 0, TWO_HUNDRED, CENT));
        for second in 1..5 {
            family.on_trade(&TradeEvent {
                ts_ms_b: 100 * MS_PER_MINUTE + second * 1_000,
                price_u6: TWO_HUNDRED + CENT / 2,
                size: 100,
                exchange: 1,
                condition: 0,
                sequence: second,
                bid_u6: TWO_HUNDRED - CENT / 2,
                ask_u6: TWO_HUNDRED + CENT / 2,
                bid_shares: 500,
                ask_shares: 500,
                quote_present: true,
            });
        }
        let row = row_after(&mut family, 101);
        close(
            column(&row, "eff_spread_proxy_bps_15m"),
            0.5,
            HIST_RESOLUTION_BPS,
        );
    }

    /// A print with no attached NBBO falls back to the last quote midpoint the
    /// driver already delivered, rather than being dropped or scored against a
    /// zero mid.
    #[test]
    fn a_print_without_an_attached_quote_uses_the_prevailing_mid() {
        let mut family = D1LiquidityCost::default();
        family.on_quote(&quote(100, 0, TWO_HUNDRED, CENT));
        family.on_trade(&TradeEvent {
            ts_ms_b: 100 * MS_PER_MINUTE + 1_000,
            price_u6: TWO_HUNDRED + CENT / 2,
            size: 100,
            exchange: 1,
            condition: 0,
            sequence: 1,
            bid_u6: 0,
            ask_u6: 0,
            bid_shares: 0,
            ask_shares: 0,
            quote_present: false,
        });
        let row = row_after(&mut family, 101);
        close(
            column(&row, "eff_spread_proxy_bps_15m"),
            0.5,
            HIST_RESOLUTION_BPS,
        );
    }

    /// Depth columns read the last NBBO; the imbalance is `ln(bid / ask)`.
    /// 1,000 bid against 500 ask is `ln(2) = 0.693147`.
    #[test]
    fn depth_imbalance_is_the_log_ratio_of_the_two_sides() {
        let mut family = D1LiquidityCost::default();
        family.on_quote(&QuoteEvent {
            ts_ms_b: 100 * MS_PER_MINUTE,
            bid_u6: TWO_HUNDRED - CENT / 2,
            ask_u6: TWO_HUNDRED + CENT / 2,
            bid_shares: 1_000,
            ask_shares: 500,
        });
        let row = row_after(&mut family, 101);
        close(column(&row, "depth_bid_shares"), 1_000.0, 0.0);
        close(column(&row, "depth_ask_shares"), 500.0, 0.0);
        close(column(&row, "depth_log_imb"), std::f64::consts::LN_2, 1e-6);
        // The only sealed minute averaged 1,500 total, and the last quote shows
        // 1,500: the ratio is exactly one.
        close(column(&row, "depth_total_vs_session_med"), 1.0, 1e-6);
    }

    /// A one-sided book has no log-imbalance; zero shares is not a ratio.
    #[test]
    fn a_zero_depth_side_is_absent_not_infinite() {
        let mut family = D1LiquidityCost::default();
        family.on_quote(&QuoteEvent {
            ts_ms_b: 100 * MS_PER_MINUTE,
            bid_u6: TWO_HUNDRED - CENT / 2,
            ask_u6: TWO_HUNDRED + CENT / 2,
            bid_shares: 0,
            ask_shares: 500,
        });
        let row = row_after(&mut family, 101);
        assert!(column(&row, "depth_log_imb").is_nan());
        assert!(row.iter().all(|value| !value.is_infinite()));
    }

    /// Only the trailing 15 minutes are in scope: a quote 20 minutes old is
    /// outside every window, and the row falls back to absence.
    #[test]
    fn windows_do_not_reach_past_their_horizon() {
        let mut family = D1LiquidityCost::default();
        family.on_quote(&quote(100, 0, TWO_HUNDRED, CENT));
        // Drive the ring forward well past the 15-minute horizon.
        for minute in 101..125 {
            family.on_quote(&quote(minute, 0, TWO_HUNDRED, CENT));
        }
        let far = row_after(&mut family, 140);
        assert!(
            column(&far, "spread_bps_med_15m").is_nan(),
            "a 15-minute-old window must not see a 16-minute-old quote"
        );
        // ...but the last NBBO is still the last NBBO: state, not a window.
        close(column(&far, "spread_bps_now"), 0.5, 1e-6);
    }

    /// An empty window is absent, not zero, and produces no infinity anywhere.
    #[test]
    fn an_untouched_family_emits_an_all_absent_row() {
        let mut family = D1LiquidityCost::default();
        let row = row_after(&mut family, 101);
        assert!(row.iter().all(|value| value.is_nan()));
    }

    /// The row cache must be invalidated by an event: two cutoffs separated by
    /// a quote cannot share a row.
    /// Exact comparison is the assertion: a reused cache row must be
    /// bit-identical, not merely close.
    #[allow(clippy::float_cmp)]
    #[test]
    fn the_row_cache_is_invalidated_by_an_event() {
        let mut family = D1LiquidityCost::default();
        family.on_quote(&quote(100, 0, TWO_HUNDRED, CENT));
        family.on_cutoff(&cutoff_at(101));
        // A second action at the same instant reuses the cache -- same values.
        family.on_cutoff(&cutoff_at(101));
        family.on_quote(&quote(101, 0, TWO_HUNDRED, 4 * CENT));
        family.on_cutoff(&cutoff_at(102));
        let cutoffs = vec![cutoff_at(101), cutoff_at(101), cutoff_at(102)];
        let rows = family.emit(&cutoffs).expect("three rows");
        assert_eq!(rows.rows(), 3);
        let first = &rows.values[..COLUMNS.len()];
        let second = &rows.values[COLUMNS.len()..2 * COLUMNS.len()];
        let third = &rows.values[2 * COLUMNS.len()..];
        assert_eq!(column(first, "spread_bps_now"), column(second, "spread_bps_now"));
        close(column(third, "spread_bps_now"), 2.0, 1e-6);
    }

    /// The saturation ceiling is a declared number, not an accident.
    #[test]
    fn the_histogram_ceiling_is_declared() {
        assert!((SATURATION_BPS - 20.48).abs() < 1e-9);
        let mut family = D1LiquidityCost::default();
        // A $10.00 spread on a $200 mid is 500 bps, far above the ceiling.
        family.on_quote(&quote(100, 0, TWO_HUNDRED, 1_000 * CENT));
        let row = row_after(&mut family, 101);
        close(column(&row, "spread_bps_med_15m"), SATURATION_BPS, 1e-5);
        // The wide census does NOT go through the histogram, so it is exact.
        close(column(&row, "wide_share_15m"), 1.0, 0.0);
    }

    #[test]
    fn prior_session_columns_are_exactly_the_d_suffixed_ones() {
        let mut family = D1LiquidityCost::default();
        family.on_quote(&quote(100, 0, TWO_HUNDRED, CENT));
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
        assert_eq!(COLUMNS.len(), 16);
        assert!(COLUMNS.len() <= crate::families::MAX_FAMILY_COLUMNS);
        let mut names: Vec<&str> = COLUMNS.iter().map(|spec| spec.name).collect();
        names.sort_unstable();
        names.dedup();
        assert_eq!(names.len(), COLUMNS.len(), "column names must be unique");
    }

    #[test]
    fn emit_refuses_a_row_count_that_does_not_match_the_cutoffs() {
        let mut family = D1LiquidityCost::default();
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
