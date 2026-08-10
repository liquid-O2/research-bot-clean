//! `e3_raid_sonar` — the RAID/sonar framework, adapted to L1 and typed
//! **ADAPTED** because that is what the data supports.
//!
//! The framework is a level-2 construction. We have the NBBO and the tape, so
//! every column below is either L1-native or an explicitly named adaptation.
//! Per finding F-15 the three "wall distance / age / side" columns are **not**
//! here: resting size away from the touch is invisible in L1, and a
//! zero-by-construction distance is a different quantity, not an adaptation.
//!
//! ## The lambda mapping (the thing to check first)
//!
//! The specification is `p <- lambda * p + signed_shares` per print, with
//! `lambda` "from half-life 30 s / 5 m vs the session's mean print spacing".
//! Turning a half-life `H` into a per-event decay needs a spacing:
//!
//! ```text
//! constant-lambda form:  lambda_bar = 0.5 ^ (mean_spacing_seconds / H)
//! implemented form:      lambda(dt) = 0.5 ^ (dt_seconds / H)
//! ```
//!
//! We implement the second. Three reasons, in order of weight:
//!
//! 1. **The first leaks.** A *session* mean spacing is only known at the close.
//!    A session-so-far mean is as-of but makes `lambda` drift with an estimator
//!    that is wild over the first minute and irrelevant after the tenth.
//! 2. **They agree by construction.** `lambda(dt)` composes exactly over
//!    consecutive events, so a stretch of tape whose spacing equals its mean
//!    decays by exactly `lambda_bar` per print. The implemented form *is* the
//!    specified recursion with the realised spacing substituted for its mean.
//! 3. **It is well defined at a cutoff.** The pressure is decayed to the cutoff
//!    instant, not left standing at the last print — so a quiet minute reads as
//!    decayed pressure rather than stale pressure.
//!
//! The measured session mean spacing and the `lambda_bar` it implies are
//! reported with the lane, not asserted here.
//!
//! ## Unresolved prints
//!
//! An unresolved print (see `e1_tape_flow::aggressor_sign`) advances time but
//! contributes no increment. It is **not** treated as a zero-signed print: the
//! unresolved mass has its own columns in E1 and E2, and folding it into the
//! pressure as a zero would claim we saw balanced flow when we saw unsigned
//! flow. Decay composes over time, so skipping the increment leaves the decay
//! exact.

// Numeric module: every cast below is bounded by construction (histogram bin,
// share count, millisecond duration, f64->f32 narrowing).
#![allow(
    clippy::cast_precision_loss,
    clippy::cast_possible_truncation,
    clippy::cast_possible_wrap,
    clippy::cast_sign_loss
)]

use super::e1_tape_flow::{Ring, Sign, aggressor_sign, cutoff_ms, minute_of, narrow, ratio};
use super::e2_gt_intent::{DUR_BINS, TICK_U6, duration_bin, duration_value, histogram_median};
use super::{AsOfRule, ColSpec, FamilyEmitter, FamilyRows, QuoteEvent, TradeEvent, Unit};
use crate::book::ActionCutoff;
use crate::error::{Result, SelectV2Error};

/// Registered name.
pub const NAME: &str = "e3_raid_sonar";

/// Fast pressure half-life, seconds.
pub const HALF_LIFE_FAST_S: f64 = 30.0;

/// Slow pressure half-life, seconds (5 minutes).
pub const HALF_LIFE_SLOW_S: f64 = 300.0;

/// A best price must stand this long before prints into it count as absorbed.
///
/// **This threshold does not fire on IWM L1 data, and that is a measurement,
/// not a guess.** Over 2022-03-01 the pass saw 506,161 best-price episodes:
/// longest 5,228 ms, mean 92.5 ms, 4,757 over 1 s, **zero over 30 s**. The
/// NBBO touch reprices far faster than the level-2 intuition the 30-second
/// figure comes from, so with this constant
/// [`absorbed_volume_touch_15m`](COLUMNS), [`absorption_rate_5m`](COLUMNS) and
/// [`post_absorption_move_bps`](COLUMNS) are 0, 0 and absent on every action.
///
/// The value is left at the specified 30 s rather than quietly retuned: the
/// threshold is a specification input, and picking a replacement is a spec
/// decision with a re-emission cost, not an implementation detail. The
/// measurement that any replacement should be argued from is the episode
/// distribution above, and the fact is asserted in
/// `e1_tape_flow`'s integration test so it cannot drift unnoticed.
// Architect ruling 2026-08-07 (typed ADAPTED, catalog law): the course's 30 s
// "standing level" is futures-DOM intuition. Measured on IWM NBBO
// (2022-03-01): 506,161 touch-hold episodes, mean 92.5 ms, longest 5,228 ms,
// zero >= 30 s — the 30 s threshold made three columns constants. 1 s is the
// IWM-native translation the distribution supports (~4,757 episodes/session).
pub const STANDING_MS: i64 = 1_000;

/// A depleted touch has this long to be restored before the episode lapses.
pub const REFILL_WINDOW_MS: i64 = 2_000;

/// Fraction of the peak that must disappear to open a depletion episode.
pub const DEPLETION_FRACTION: f64 = 0.5;

/// Fraction of the lost size that must come back to count as a refill.
pub const REFILL_FRACTION: f64 = 0.5;

/// Per-quote weight of the touch-size-pressure EMA (specified, not derived).
pub const TOUCH_ALPHA: f64 = 0.2;

/// Instability, in ticks, the composite gate requires.
pub const INSTABILITY_GATE_TICKS: i64 = 2;

/// Session pressure percentile the composite gate requires.
pub const PRESSURE_GATE_PCTILE: f64 = 0.80;

/// How far after an absorption episode the follow-through is measured.
pub const POST_ABSORPTION_MS: i64 = 120_000;

/// Magnitude histogram: bin 0 is "below one share", then 8 bins per octave to
/// 2^24 shares.
const MAG_BINS: usize = 200;
const MAG_PER_OCTAVE: f64 = 8.0;

fn magnitude_bin(magnitude: f64) -> usize {
    if magnitude.is_nan() || magnitude < 1.0 {
        return 0;
    }
    let bin = 1.0 + (magnitude.log2() * MAG_PER_OCTAVE).floor();
    if bin >= (MAG_BINS - 1) as f64 {
        MAG_BINS - 1
    } else {
        bin as usize
    }
}

fn magnitude_lower(bin: usize) -> f64 {
    if bin == 0 {
        0.0
    } else {
        (2.0_f64).powf((bin - 1) as f64 / MAG_PER_OCTAVE)
    }
}

/// Per-event decay factor for a half-life, exact in elapsed time.
#[must_use]
pub fn decay(elapsed_ms: i64, half_life_s: f64) -> f64 {
    if elapsed_ms <= 0 || half_life_s <= 0.0 {
        return 1.0;
    }
    (0.5_f64).powf(elapsed_ms as f64 / 1_000.0 / half_life_s)
}

/// Session-so-far distribution of `|pressure_fast|`, sampled once per hard
/// print. Backs both the percentile column and the composite gate's p80.
#[derive(Clone, Debug)]
struct MagnitudeHistogram {
    bins: Vec<u32>,
    total: u64,
}

impl MagnitudeHistogram {
    const fn new() -> Self {
        Self {
            bins: Vec::new(),
            total: 0,
        }
    }

    fn observe(&mut self, magnitude: f64) {
        if self.bins.is_empty() {
            self.bins.resize(MAG_BINS, 0);
        }
        self.bins[magnitude_bin(magnitude)] += 1;
        self.total += 1;
    }

    /// Fraction of prior samples at or below `magnitude`, counting half of its
    /// own bin. `None` while nothing has been sampled.
    fn percentile(&self, magnitude: f64) -> Option<f64> {
        if self.total == 0 {
            return None;
        }
        let target = magnitude_bin(magnitude);
        let below: u64 = self.bins[..target].iter().map(|c| u64::from(*c)).sum();
        let here = f64::from(self.bins[target]);
        Some((below as f64 + 0.5 * here) / self.total as f64)
    }

    /// Lower edge of the bin holding the `p`-quantile. `None` while empty.
    fn quantile_lower(&self, p: f64) -> Option<f64> {
        if self.total == 0 {
            return None;
        }
        let target = (self.total as f64 * p).ceil().max(1.0);
        let mut seen = 0_u64;
        for (bin, count) in self.bins.iter().enumerate() {
            seen += u64::from(*count);
            if seen as f64 >= target {
                return Some(magnitude_lower(bin));
            }
        }
        Some(magnitude_lower(MAG_BINS - 1))
    }
}

/// One side's standing-best episode and its depletion state.
#[derive(Clone, Copy, Debug)]
struct Touch {
    price_u6: i64,
    since_ms: i64,
    peak_shares: i64,
    last_shares: i64,
    depleted_at_ms: i64,
    depleted_shares: i64,
    rejections: u32,
    absorbed: i64,
    pending_rejections: u32,
}

impl Touch {
    const fn new() -> Self {
        Self {
            price_u6: i64::MIN,
            since_ms: 0,
            peak_shares: 0,
            last_shares: 0,
            depleted_at_ms: i64::MIN,
            depleted_shares: 0,
            rejections: 0,
            absorbed: 0,
            pending_rejections: 0,
        }
    }

    const fn open(&self) -> bool {
        self.price_u6 != i64::MIN
    }

    const fn age_ms(&self, now_ms: i64) -> i64 {
        if self.open() { now_ms - self.since_ms } else { 0 }
    }
}

/// A follow-through measurement waiting for its two minutes to elapse.
#[derive(Clone, Copy, Debug)]
struct PendingMove {
    due_ms: i64,
    reference_u6: i64,
    /// `+1` when the absorbing side was the bid, `-1` when it was the ask, so a
    /// positive reading always means the defended side won.
    direction: f64,
}

// ---------------------------------------------------------------------------
// Columns
// ---------------------------------------------------------------------------

const COLUMNS: [ColSpec; 18] = [
    ColSpec::new("pressure_fast", Unit::Shares, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("pressure_slow", Unit::Shares, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new(
        "pressure_pctile_session",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new("instability_ticks", Unit::Count, AsOfRule::StrictlyBeforeCutoff),
    // A decayed sum with a 60 s half-life, not a normalized mean — see the
    // note in `on_quote`.
    ColSpec::new("instability_ema_1m", Unit::Count, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("touch_size_pressure", Unit::Shares, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new(
        "refill_count_touch_15m",
        Unit::Count,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "absorbed_volume_touch_15m",
        Unit::Shares,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "defense_hold_max_s_15m",
        Unit::Seconds,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "defense_rejection_count_15m",
        Unit::Count,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "pressure_x_instability_flag",
        Unit::Flag,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "pressure_sign_agreement",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new("absorption_rate_5m", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("depletion_events_5m", Unit::Count, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("touch_hold_age_s", Unit::Seconds, AsOfRule::StrictlyBeforeCutoff),
    // The frozen column name reports milliseconds; the `Unit` enum has no
    // millisecond variant and lives in `mod.rs`, which this lane does not own.
    // The name is authoritative for the magnitude — flagged, not silently
    // rescaled.
    ColSpec::new(
        "refill_speed_med_ms_15m",
        Unit::Seconds,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "post_absorption_move_bps",
        Unit::Bps,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new("sonar_composite", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
];

/// One minute of sonar accumulators.
#[derive(Clone, Debug)]
struct Bucket {
    // Hot fields first: these are the ones a per-quote or per-print step
    // touches, and keeping them contiguous keeps the common path to one or two
    // cache lines of a struct the histogram makes half a kilobyte wide.
    instability_max_ticks: i64,
    total_volume: i64,
    absorbed: i64,
    defense_hold_max_ms: i64,
    refills: u32,
    depletions: u32,
    rejections: u32,
    refill_ms: [u32; DUR_BINS],
}

impl Default for Bucket {
    fn default() -> Self {
        Self {
            instability_max_ticks: 0,
            total_volume: 0,
            absorbed: 0,
            defense_hold_max_ms: 0,
            refills: 0,
            depletions: 0,
            rejections: 0,
            refill_ms: [0; DUR_BINS],
        }
    }
}

/// Pressure, instability and touch-defence structure for one session.
#[derive(Clone, Debug)]
pub struct RaidSonar {
    ring: Ring<Bucket>,
    magnitudes: MagnitudeHistogram,

    pressure_fast: f64,
    pressure_slow: f64,
    pressure_at_ms: i64,

    instability_sum: f64,
    instability_at_ms: i64,
    last_spread_ticks: i64,

    touch_size_pressure: f64,

    bid: Touch,
    ask: Touch,
    last_mid_u6: i64,
    last_quote_ms: i64,

    pending: Vec<PendingMove>,
    post_absorption_bps: f64,

    rows: Vec<f32>,
}

impl Default for RaidSonar {
    fn default() -> Self {
        Self::new()
    }
}

/// Value-namespace constructor for `families::build`; see the note on
/// `e1_tape_flow::E1TapeFlow`. `mod.rs` is another lane's file.
#[allow(non_upper_case_globals)]
pub const E3RaidSonar: RaidSonar = RaidSonar::new();

impl RaidSonar {
    /// A fresh emitter for one session.
    #[must_use]
    pub const fn new() -> Self {
        Self {
            ring: Ring::new(),
            magnitudes: MagnitudeHistogram::new(),
            pressure_fast: 0.0,
            pressure_slow: 0.0,
            pressure_at_ms: i64::MIN,
            instability_sum: 0.0,
            instability_at_ms: i64::MIN,
            last_spread_ticks: i64::MIN,
            touch_size_pressure: 0.0,
            bid: Touch::new(),
            ask: Touch::new(),
            last_mid_u6: i64::MIN,
            last_quote_ms: i64::MIN,
            pending: Vec::new(),
            post_absorption_bps: f64::NAN,
            rows: Vec::new(),
        }
    }

    /// Decays both pressures to `now_ms`. Composable, so calling this at every
    /// event and again at the cutoff gives the same answer as calling it once.
    fn decay_pressure_to(&mut self, now_ms: i64) {
        if self.pressure_at_ms == i64::MIN {
            self.pressure_at_ms = now_ms;
            return;
        }
        let elapsed = now_ms - self.pressure_at_ms;
        if elapsed <= 0 {
            return;
        }
        self.pressure_fast *= decay(elapsed, HALF_LIFE_FAST_S);
        self.pressure_slow *= decay(elapsed, HALF_LIFE_SLOW_S);
        self.pressure_at_ms = now_ms;
    }

    fn decay_instability_to(&mut self, now_ms: i64) {
        if self.instability_at_ms == i64::MIN {
            self.instability_at_ms = now_ms;
            return;
        }
        let elapsed = now_ms - self.instability_at_ms;
        if elapsed <= 0 {
            return;
        }
        self.instability_sum *= decay(elapsed, 60.0);
        self.instability_at_ms = now_ms;
    }

    /// Resolves every follow-through measurement whose two minutes have elapsed
    /// by `now_ms`, using the mid observed at resolution time.
    fn resolve_pending(&mut self, now_ms: i64, mid_u6: i64) {
        if self.pending.is_empty() || mid_u6 == i64::MIN {
            return;
        }
        let mut kept: Vec<PendingMove> = Vec::with_capacity(self.pending.len());
        for item in std::mem::take(&mut self.pending) {
            if item.due_ms > now_ms {
                kept.push(item);
                continue;
            }
            if item.reference_u6 > 0 {
                let move_bps = (mid_u6 - item.reference_u6) as f64 / item.reference_u6 as f64 * 1e4;
                self.post_absorption_bps = item.direction * move_bps;
            }
        }
        self.pending = kept;
    }

    fn window_sum<A>(&self, end_minute: i64, minutes: i64, seed: A, step: impl FnMut(A, &Bucket) -> A) -> A {
        self.ring.fold_window(end_minute, minutes, seed, step)
    }
}

impl FamilyEmitter for RaidSonar {
    fn name(&self) -> &'static str {
        NAME
    }

    fn columns(&self) -> &[ColSpec] {
        &COLUMNS
    }

    #[allow(clippy::too_many_lines)]
    fn on_quote(&mut self, quote: &QuoteEvent) {
        let ts = quote.ts_ms_b;
        if quote.bid_u6 <= 0 || quote.ask_u6 <= 0 || quote.ask_u6 < quote.bid_u6 {
            return;
        }
        let minute = minute_of(ts);
        self.ring.advance_to(minute);
        let mid = i64::midpoint(quote.bid_u6, quote.ask_u6);

        // Instability: the tick change in spread against the previous quote.
        // The accumulator is the decayed SUM `s <- lambda*s + |dticks|`, the
        // same shape as `pressure_fast`, deliberately not a normalized mean:
        // a decayed sum composes exactly over skipped zero observations, so a
        // quote that did not move the spread can be skipped entirely and still
        // give the value a per-quote update would. A normalized mean does not
        // have that property, and most quotes do not move the spread.
        let ticks = (quote.ask_u6 - quote.bid_u6).div_euclid(TICK_U6);
        if self.last_spread_ticks != i64::MIN {
            let delta = (ticks - self.last_spread_ticks).abs();
            if delta > 0 {
                if let Some(bucket) = self.ring.slot_mut(minute) {
                    bucket.instability_max_ticks = bucket.instability_max_ticks.max(delta);
                }
                self.decay_instability_to(ts);
                self.instability_sum += delta as f64;
            }
        }
        self.last_spread_ticks = ticks;

        // Touch-size pressure: the EMA of best-size changes on the side the
        // fast pressure is pushing into. Only same-price changes count — a
        // price move is a different quantity, not a size change.
        //
        // The pressured SIDE is the sign of the pressure, and decay is a
        // multiplication by a positive number, so the sign is decay-invariant:
        // the quote path reads it undecayed and correctly. Decaying here
        // instead would cost two `powf` on every one of ~17M quotes to reach
        // an answer that cannot change.
        let ask_side = self.pressure_fast >= 0.0;
        let (previous_price, previous_shares) = if ask_side {
            (self.ask.price_u6, self.ask.last_shares)
        } else {
            (self.bid.price_u6, self.bid.last_shares)
        };
        let (now_price, now_shares) = if ask_side {
            (quote.ask_u6, quote.ask_shares.max(0))
        } else {
            (quote.bid_u6, quote.bid_shares.max(0))
        };
        if previous_price == now_price {
            let delta = (now_shares - previous_shares) as f64;
            self.touch_size_pressure += TOUCH_ALPHA * (delta - self.touch_size_pressure);
        }

        // Both sides are stepped through `&mut`. `Touch` is 72 bytes; copying
        // it in and back out per side was ~5 GB of memory traffic a session
        // for no reason.
        step_touch(
            &mut self.bid,
            &mut self.ring,
            &mut self.pending,
            self.last_mid_u6,
            false,
            minute,
            ts,
            quote.bid_u6,
            quote.bid_shares.max(0),
        );
        step_touch(
            &mut self.ask,
            &mut self.ring,
            &mut self.pending,
            self.last_mid_u6,
            true,
            minute,
            ts,
            quote.ask_u6,
            quote.ask_shares.max(0),
        );

        self.last_mid_u6 = mid;
        self.last_quote_ms = ts;
        self.resolve_pending(ts, mid);
    }

    fn on_trade(&mut self, trade: &TradeEvent) {
        let ts = trade.ts_ms_b;
        let size = trade.size.max(0);
        let sign = aggressor_sign(trade);
        let minute = minute_of(ts);
        if let Some(bucket) = self.ring.slot_mut(minute) {
            bucket.total_volume += size;
        }

        // Decay always; increment only for a hard sign.
        self.decay_pressure_to(ts);
        if sign.is_hard() {
            let signed = (sign.as_i64() * size) as f64;
            self.pressure_fast += signed;
            self.pressure_slow += signed;
            self.magnitudes.observe(self.pressure_fast.abs());

            // A hard sell hits the bid; a hard buy hits the ask.
            let ask_side = sign == Sign::Buy;
            let touch = if ask_side { self.ask } else { self.bid };
            if touch.open() {
                let mut touch = touch;
                touch.pending_rejections += 1;
                if touch.age_ms(ts) >= STANDING_MS {
                    touch.absorbed += size;
                    if let Some(bucket) = self.ring.slot_mut(minute) {
                        bucket.absorbed += size;
                    }
                }
                if ask_side {
                    self.ask = touch;
                } else {
                    self.bid = touch;
                }
            }
        }
    }

    #[allow(clippy::too_many_lines)]
    fn on_cutoff(&mut self, cutoff: &ActionCutoff) {
        let instant = cutoff_ms(cutoff);
        self.ring.advance_to(minute_of(instant));
        self.decay_pressure_to(instant);
        self.decay_instability_to(instant);
        let last_mid = self.last_mid_u6;
        self.resolve_pending(instant, last_mid);
        let end = minute_of(instant) - 1;

        self.rows.push(narrow(self.pressure_fast));
        self.rows.push(narrow(self.pressure_slow));

        let percentile = self.magnitudes.percentile(self.pressure_fast.abs());
        self.rows
            .push(percentile.map_or(f32::NAN, narrow));

        let instability = self
            .window_sum(end, 1, 0_i64, |acc, bucket| {
                acc.max(bucket.instability_max_ticks)
            });
        self.rows.push(narrow(instability as f64));
        self.rows.push(narrow(self.instability_sum));
        self.rows.push(narrow(self.touch_size_pressure));

        let refills = self.window_sum(end, 15, 0_u64, |acc, bucket| acc + u64::from(bucket.refills));
        self.rows.push(narrow(refills as f64));

        let absorbed_quarter = self.window_sum(end, 15, 0_i64, |acc, bucket| acc + bucket.absorbed);
        self.rows.push(narrow(absorbed_quarter as f64));

        // The longest defended hold in the window, including the episode still
        // open at the cutoff if it has already been defended.
        let mut hold_ms = self.window_sum(end, 15, 0_i64, |acc, bucket| {
            acc.max(bucket.defense_hold_max_ms)
        });
        for touch in [self.bid, self.ask] {
            if touch.open() && touch.rejections > 0 {
                hold_ms = hold_ms.max(touch.age_ms(instant));
            }
        }
        self.rows.push(narrow(hold_ms as f64 / 1_000.0));

        let rejections =
            self.window_sum(end, 15, 0_u64, |acc, bucket| acc + u64::from(bucket.rejections));
        self.rows.push(narrow(rejections as f64));

        let gate = self.magnitudes.quantile_lower(PRESSURE_GATE_PCTILE);
        self.rows.push(match gate {
            None => f32::NAN,
            Some(threshold) => {
                let fired = self.pressure_fast.abs() > threshold
                    && instability >= INSTABILITY_GATE_TICKS;
                if fired { 1.0 } else { 0.0 }
            }
        });

        let sign_fast = signum(self.pressure_fast);
        let sign_slow = signum(self.pressure_slow);
        self.rows.push(narrow(sign_fast * sign_slow));

        let (recent_absorbed, recent_volume) =
            self.window_sum(end, 5, (0_i64, 0_i64), |acc, bucket| {
                (acc.0 + bucket.absorbed, acc.1 + bucket.total_volume)
            });
        self.rows
            .push(ratio(recent_absorbed as f64, recent_volume as f64));

        let depletions =
            self.window_sum(end, 5, 0_u64, |acc, bucket| acc + u64::from(bucket.depletions));
        self.rows.push(narrow(depletions as f64));

        // The hold age of the side the fast pressure is pushing into; with no
        // pressure at all, the longer-standing of the two.
        let age_ms = if self.pressure_fast > 0.0 {
            self.ask.open().then(|| self.ask.age_ms(instant))
        } else if self.pressure_fast < 0.0 {
            self.bid.open().then(|| self.bid.age_ms(instant))
        } else {
            let bid = self.bid.open().then(|| self.bid.age_ms(instant));
            let ask = self.ask.open().then(|| self.ask.age_ms(instant));
            match (bid, ask) {
                (Some(bid), Some(ask)) => Some(bid.max(ask)),
                (some, None) | (None, some) => some,
            }
        };
        self.rows
            .push(age_ms.map_or(f32::NAN, |ms| narrow(ms as f64 / 1_000.0)));

        let mut refill_hist = [0_u64; DUR_BINS];
        let mut offset = 0_i64;
        while offset < 15 {
            if let Some(bucket) = self.ring.get(end - offset) {
                for (bin, count) in bucket.refill_ms.iter().enumerate() {
                    refill_hist[bin] += u64::from(*count);
                }
            }
            offset += 1;
        }
        self.rows.push(
            histogram_median(&refill_hist, duration_value).map_or(f32::NAN, narrow),
        );

        self.rows.push(narrow(self.post_absorption_bps));

        // sign(pressure) * percentile * ln(1 + refills). One diagnostic column,
        // absent whenever the percentile it multiplies is absent.
        self.rows.push(match percentile {
            None => f32::NAN,
            Some(percentile) => {
                narrow(sign_fast * percentile * (1.0 + refills as f64).ln())
            }
        });
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

/// Files a closing standing-best episode. A free function so the caller can
/// hold `&mut Touch` and `&mut Ring` at once without copying either.
fn close_touch_into(
    touch: &Touch,
    ring: &mut Ring<Bucket>,
    pending: &mut Vec<PendingMove>,
    last_mid_u6: i64,
    ask_side: bool,
    now_ms: i64,
) {
    if !touch.open() {
        return;
    }
    let held = now_ms - touch.since_ms;
    if touch.rejections > 0
        && held > 0
        && let Some(bucket) = ring.slot_mut(minute_of(now_ms))
    {
        bucket.defense_hold_max_ms = bucket.defense_hold_max_ms.max(held);
    }
    if touch.absorbed > 0 && last_mid_u6 != i64::MIN {
        pending.push(PendingMove {
            due_ms: now_ms + POST_ABSORPTION_MS,
            reference_u6: last_mid_u6,
            direction: if ask_side { -1.0 } else { 1.0 },
        });
    }
}

/// Advances one side's touch state for one quote: episode roll-over, pending
/// rejections, depletion opening and refill/lapse resolution.
#[allow(clippy::too_many_arguments)]
fn step_touch(
    touch: &mut Touch,
    ring: &mut Ring<Bucket>,
    pending: &mut Vec<PendingMove>,
    last_mid_u6: i64,
    ask_side: bool,
    minute: i64,
    ts: i64,
    price: i64,
    shares: i64,
) {
    if touch.price_u6 != price {
        close_touch_into(touch, ring, pending, last_mid_u6, ask_side, ts);
        *touch = Touch {
            price_u6: price,
            since_ms: ts,
            peak_shares: shares,
            last_shares: shares,
            ..Touch::new()
        };
        return;
    }

    // The level held through whatever hit it since the last quote.
    if touch.pending_rejections > 0 {
        let count = touch.pending_rejections;
        if let Some(bucket) = ring.slot_mut(minute) {
            bucket.rejections += count;
        }
        touch.rejections += count;
        touch.pending_rejections = 0;
    }

    if touch.depleted_at_ms == i64::MIN {
        touch.peak_shares = touch.peak_shares.max(shares);
        if touch.peak_shares > 0 && (shares as f64) <= DEPLETION_FRACTION * touch.peak_shares as f64
        {
            touch.depleted_at_ms = ts;
            touch.depleted_shares = shares;
            if let Some(bucket) = ring.slot_mut(minute) {
                bucket.depletions += 1;
            }
        }
    } else {
        let latency = ts - touch.depleted_at_ms;
        let restored = touch.depleted_shares as f64
            + REFILL_FRACTION * (touch.peak_shares - touch.depleted_shares) as f64;
        if latency > REFILL_WINDOW_MS {
            // Lapsed. The size may well come back later, but "restored within
            // 2 s" is the specified object and this is not it — an observed
            // non-refill. The level is genuinely thinner, so the peak resets to
            // what is actually there. The window is tested BEFORE the
            // restoration, or a late refill would be counted as a timely one.
            touch.depleted_at_ms = i64::MIN;
            touch.peak_shares = shares;
        } else if (shares as f64) >= restored {
            let bin = duration_bin(latency as f64);
            if let Some(bucket) = ring.slot_mut(minute) {
                bucket.refills += 1;
                bucket.refill_ms[bin] += 1;
            }
            touch.depleted_at_ms = i64::MIN;
            touch.peak_shares = shares;
        }
    }
    touch.last_shares = shares;
}

fn signum(value: f64) -> f64 {
    if value > 0.0 {
        1.0
    } else if value < 0.0 {
        -1.0
    } else {
        0.0
    }
}

#[cfg(test)]
mod tests {
    // Every float compared for equality below is an exact small-integer ratio
    // (0/n or n/n) or an exactly representable constant, not an accumulated
    // sum. Equality is the assertion being made, so a tolerance would weaken
    // it rather than harden it.
    #![allow(clippy::float_cmp)]

    use super::*;
    use crate::book::Side;
    use crate::families::e1_tape_flow::BAR_MS;

    const BID: i64 = 199_990_000;
    const ASK: i64 = 200_010_000;

    fn quote_at(ts_ms: i64, bid_shares: i64, ask_shares: i64) -> QuoteEvent {
        QuoteEvent {
            ts_ms_b: ts_ms,
            bid_u6: BID,
            ask_u6: ASK,
            bid_shares,
            ask_shares,
        }
    }

    fn quote_priced(ts_ms: i64, bid_u6: i64, ask_u6: i64, bid_shares: i64, ask_shares: i64) -> QuoteEvent {
        QuoteEvent {
            ts_ms_b: ts_ms,
            bid_u6,
            ask_u6,
            bid_shares,
            ask_shares,
        }
    }

    fn print_at(ts_ms: i64, price_u6: i64, size: i64) -> TradeEvent {
        TradeEvent {
            ts_ms_b: ts_ms,
            price_u6,
            size,
            exchange: 4,
            condition: 0,
            sequence: 0,
            bid_u6: BID,
            ask_u6: ASK,
            bid_shares: 100,
            ask_shares: 100,
            quote_present: true,
        }
    }

    fn cutoff_at(bar: i32) -> ActionCutoff {
        ActionCutoff {
            action_id: format!("t-{bar}"),
            day: "2022-03-01",
            session_ordinal: 0,
            cutoff_bar_ordinal: bar,
            side: Side::High,
            cutoff_ns_a: 0,
            cutoff_ns_b: i64::from(bar) * BAR_MS * 1_000_000,
            first_visibility_ns: 0,
            last_visibility_ns: 0,
            act_set: crate::book::ActSetSummary::default(),
        }
    }

    fn column(rows: &FamilyRows, name: &str) -> f32 {
        let index = COLUMNS.iter().position(|c| c.name == name).expect("column");
        rows.values[index]
    }

    /// The lambda mapping, checked on paper: one 1,000-share buy, read exactly
    /// one fast half-life later, must be 500 shares.
    #[test]
    fn pressure_decays_by_exactly_one_half_per_half_life() {
        let mut family = RaidSonar::new();
        family.on_quote(&quote_at(0, 100, 100));
        family.on_trade(&print_at(1_000, ASK, 1_000)); // hard buy
        // Read at 31 s: 30 s after the print, which is one fast half-life and
        // one tenth of a slow one.
        let cutoff = ActionCutoff {
            cutoff_ns_b: 31_000 * 1_000_000,
            ..cutoff_at(1)
        };
        family.on_cutoff(&cutoff);
        let rows = family.emit(std::slice::from_ref(&cutoff)).expect("emit");
        assert!(
            (column(&rows, "pressure_fast") - 500.0).abs() < 1e-3,
            "fast {}",
            column(&rows, "pressure_fast")
        );
        let expected_slow = 1_000.0 * 0.5_f64.powf(30.0 / 300.0);
        assert!(
            (f64::from(column(&rows, "pressure_slow")) - expected_slow).abs() < 1e-2,
            "slow {}",
            column(&rows, "pressure_slow")
        );
        // Fast and slow are both positive here, so they agree.
        assert!((column(&rows, "pressure_sign_agreement") - 1.0).abs() < 1e-9);
    }

    /// Decay composes: splitting the interval must not change the answer.
    #[test]
    fn decay_composes_over_split_intervals() {
        let one_step = decay(30_000, HALF_LIFE_FAST_S);
        let two_steps = decay(10_000, HALF_LIFE_FAST_S) * decay(20_000, HALF_LIFE_FAST_S);
        assert!((one_step - two_steps).abs() < 1e-12);
        assert!((one_step - 0.5).abs() < 1e-12);
    }

    /// An unresolved print advances the clock but adds nothing — it is not a
    /// zero-signed print.
    #[test]
    fn unresolved_prints_decay_without_incrementing() {
        let mid = i64::midpoint(BID, ASK);
        let mut family = RaidSonar::new();
        family.on_quote(&quote_at(0, 100, 100));
        family.on_trade(&print_at(1_000, ASK, 1_000));
        // Two at-the-mid prints, which the aggressor law cannot side.
        family.on_trade(&print_at(2_000, mid, 5_000));
        family.on_trade(&print_at(3_000, mid, 5_000));
        let cutoff = ActionCutoff {
            cutoff_ns_b: 31_000 * 1_000_000,
            ..cutoff_at(1)
        };
        family.on_cutoff(&cutoff);
        let rows = family.emit(std::slice::from_ref(&cutoff)).expect("emit");
        // Still exactly half of the one hard print, 30 s on.
        assert!((column(&rows, "pressure_fast") - 500.0).abs() < 1e-3);
    }

    /// Depletion then restoration inside two seconds is a refill; the same
    /// restoration a second too late is not.
    #[test]
    fn refill_needs_half_back_within_two_seconds() {
        let mut family = RaidSonar::new();
        family.on_quote(&quote_at(0, 10_000, 100)); // bid peak 10,000
        family.on_quote(&quote_at(500, 4_000, 100)); // 40% left -> depleted
        family.on_quote(&quote_at(1_000, 7_000, 100)); // 4,000 + 0.5*6,000 = 7,000
        let cutoff = cutoff_at(1);
        family.on_cutoff(&cutoff);
        let rows = family.emit(std::slice::from_ref(&cutoff)).expect("emit");
        assert!((column(&rows, "refill_count_touch_15m") - 1.0).abs() < 1e-9);
        assert!((column(&rows, "depletion_events_5m") - 1.0).abs() < 1e-9);
        // 500 ms latency lands in the bin whose centre is within 10% of 500.
        let median = f64::from(column(&rows, "refill_speed_med_ms_15m"));
        assert!((median - 500.0).abs() / 500.0 < 0.10, "median {median}");

        // Too late: the same restoration 2,001 ms after the depletion.
        let mut late = RaidSonar::new();
        late.on_quote(&quote_at(0, 10_000, 100));
        late.on_quote(&quote_at(500, 4_000, 100));
        late.on_quote(&quote_at(2_600, 7_000, 100));
        let cutoff = cutoff_at(1);
        late.on_cutoff(&cutoff);
        let rows = late.emit(std::slice::from_ref(&cutoff)).expect("emit");
        assert!((column(&rows, "refill_count_touch_15m") - 0.0).abs() < 1e-9);
        assert!((column(&rows, "depletion_events_5m") - 1.0).abs() < 1e-9);
        assert!(column(&rows, "refill_speed_med_ms_15m").is_nan());
    }

    /// A price move is not a refill: the depletion episode is voided, not
    /// resolved, when the level breaks.
    #[test]
    fn a_broken_level_is_not_a_refill() {
        let mut family = RaidSonar::new();
        family.on_quote(&quote_priced(0, BID, ASK, 10_000, 100));
        family.on_quote(&quote_priced(500, BID, ASK, 4_000, 100));
        // The bid drops a tick with a big size at the NEW price.
        family.on_quote(&quote_priced(1_000, BID - TICK_U6, ASK, 20_000, 100));
        let cutoff = cutoff_at(1);
        family.on_cutoff(&cutoff);
        let rows = family.emit(std::slice::from_ref(&cutoff)).expect("emit");
        assert!((column(&rows, "refill_count_touch_15m") - 0.0).abs() < 1e-9);
    }

    /// Absorption needs the level to have stood `STANDING_MS` (1 s — the
    /// measured IWM-native ruling, 2026-08-07) already.
    #[test]
    fn absorption_requires_a_one_second_standing_best() {
        let mut family = RaidSonar::new();
        family.on_quote(&quote_at(0, 10_000, 10_000));
        // A hard sell into a 500 ms-old bid: too young to be absorption.
        family.on_trade(&print_at(500, BID, 700));
        // A hard sell into the same bid at 1.5 s: absorbed.
        family.on_trade(&print_at(1_500, BID, 300));
        let cutoff = cutoff_at(1);
        family.on_cutoff(&cutoff);
        let rows = family.emit(std::slice::from_ref(&cutoff)).expect("emit");
        assert!(
            (column(&rows, "absorbed_volume_touch_15m") - 300.0).abs() < 1e-9,
            "{}",
            column(&rows, "absorbed_volume_touch_15m")
        );
        // 300 absorbed out of 1,000 printed.
        assert!((column(&rows, "absorption_rate_5m") - 0.3).abs() < 1e-6);
    }

    /// A hit that the level survives is a rejection; the hold is only counted
    /// once the level has been defended at least once.
    #[test]
    fn rejections_are_only_counted_when_the_level_holds() {
        let mut family = RaidSonar::new();
        family.on_quote(&quote_at(0, 10_000, 10_000));
        family.on_trade(&print_at(1_000, BID, 100));
        // The bid is still there at the next quote: the hit was rejected.
        family.on_quote(&quote_at(2_000, 9_900, 10_000));
        let cutoff = cutoff_at(1);
        family.on_cutoff(&cutoff);
        let rows = family.emit(std::slice::from_ref(&cutoff)).expect("emit");
        assert!((column(&rows, "defense_rejection_count_15m") - 1.0).abs() < 1e-9);
        // The open episode has been defended, so its age counts as the hold.
        assert!(column(&rows, "defense_hold_max_s_15m") >= 59.0);

        // Now a hit the level does NOT survive.
        let mut broken = RaidSonar::new();
        broken.on_quote(&quote_priced(0, BID, ASK, 10_000, 10_000));
        broken.on_trade(&print_at(1_000, BID, 100));
        broken.on_quote(&quote_priced(2_000, BID - TICK_U6, ASK, 10_000, 10_000));
        let cutoff = cutoff_at(1);
        broken.on_cutoff(&cutoff);
        let rows = broken.emit(std::slice::from_ref(&cutoff)).expect("emit");
        assert!((column(&rows, "defense_rejection_count_15m") - 0.0).abs() < 1e-9);
    }

    #[test]
    fn magnitude_percentile_is_bounded_and_ordered() {
        let mut histogram = MagnitudeHistogram::new();
        for step in 1..=1000_i64 {
            histogram.observe(step as f64);
        }
        let low = histogram.percentile(2.0).expect("low");
        let high = histogram.percentile(900.0).expect("high");
        assert!((0.0..=1.0).contains(&low));
        assert!((0.0..=1.0).contains(&high));
        assert!(low < high);
        let gate = histogram.quantile_lower(0.80).expect("gate");
        assert!(gate > 100.0 && gate < 1000.0, "gate {gate}");
    }

    #[test]
    fn no_column_is_ever_infinite_on_a_thin_tape() {
        let mut family = RaidSonar::new();
        family.on_quote(&quote_at(100, 100, 100));
        family.on_trade(&print_at(1_000, ASK, 100));
        let cutoff = cutoff_at(1);
        family.on_cutoff(&cutoff);
        let rows = family.emit(std::slice::from_ref(&cutoff)).expect("emit");
        for (index, value) in rows.values.iter().enumerate() {
            assert!(
                value.is_finite() || value.is_nan(),
                "{} is infinite",
                COLUMNS[index].name
            );
        }
    }
}
