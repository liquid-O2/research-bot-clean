//! `e1_tape_flow` — the signed structure of the stock print tape.
//!
//! Everything here is a function of prints classified by **one** aggressor law
//! (below) and accumulated into **absolute-minute buckets**. Both choices are
//! structural, not stylistic:
//!
//! * **The aggressor law is defined once**, in [`aggressor_sign`], and the two
//!   sibling flow families (`e2_gt_intent`, `e3_raid_sonar`) import it rather
//!   than restating it. Three copies of a sign convention is three chances for
//!   it to drift; the corpus has already paid for that class of defect.
//! * **Minute buckets are exact here, not a rounding.** A cutoff is
//!   `session_open + bar_ordinal * 60 s` (`calendar::DayScope::cutoff_ns_b`
//!   over `corpus::BAR_NS`), and the session open is 09:30:00.000 in frame B,
//!   so every cutoff lands on an exact absolute-minute boundary. A trailing
//!   `K`-minute window at a cutoff is therefore *exactly* the last `K` complete
//!   buckets — no partial bucket, no edge approximation. Bucketing by
//!   `ts_ms.div_euclid(60_000)` needs no session anchor, which is what lets the
//!   family answer before it has ever been shown a cutoff.
//!
//! ## The aggressor law (binding for E1, E2 and E3)
//!
//! ```text
//! price > prevailing mid  => BUY        (+1)
//! price < prevailing mid  => SELL       (-1)
//! price == prevailing mid => UNRESOLVED
//! quote_present == false  => UNRESOLVED
//! malformed NBBO          => UNRESOLVED
//! ```
//!
//! UNRESOLVED is a third state with its own columns
//! ([`unresolved_share_15m`](COLUMNS)), never folded into zero and never
//! silently dropped: absence is not zero. The comparison is done as
//! `2 * price` against `bid + ask` so the mid is never rounded — an exact
//! integer test with no tie manufactured by truncation.
//!
//! ## As-of discipline for session-relative classifications
//!
//! `large_print_share_15m` needs a "top decile" and `block_count_15m` needs a
//! "session median". Both are resolved **at the print's own arrival**, against
//! the size distribution of prints strictly before it ([`SizeQuantiles`]).
//! The alternative — re-labelling the whole 15-minute window at every cutoff
//! against the cutoff-time decile — was rejected on two grounds: it is
//! `O(window)` per cutoff where the perf law asks for `O(1)`, and it makes a
//! print's "largeness" a moving property of when you ask rather than a fact
//! about the tape. Recorded as an ambiguity resolution.
//!
//! ## Cost
//!
//! Per print: one sign test, four quantile-pointer nudges, one sweep-state
//! step, ~20 bucket adds. Per quote: nothing (this family reads prints only;
//! the print carries its own prevailing NBBO). Per cutoff: at most 30 bucket
//! reads per window family — bounded, independent of session size.

// Numeric module: every cast below is bounded by construction (ring index,
// histogram bin, share count, f64->f32 narrowing) and each site says why.
#![allow(
    clippy::cast_precision_loss,
    clippy::cast_possible_truncation,
    clippy::cast_possible_wrap,
    clippy::cast_sign_loss
)]

use super::{AsOfRule, ColSpec, FamilyEmitter, FamilyRows, QuoteEvent, TradeEvent, Unit};
use crate::book::ActionCutoff;
use crate::error::{Result, SelectV2Error};

/// Registered name.
pub const NAME: &str = "e1_tape_flow";

/// One bar, in the tape's millisecond unit. Mirrors `corpus::BAR_NS`.
pub const BAR_MS: i64 = 60_000;

/// Ring slots, as a minute count. The longest window any flow family reads is
/// 30 minutes; 64 leaves room for the current partial minute and the one extra
/// minute the Kyle regression needs to open its first return.
pub const RING_MINUTES: i64 = 64;

/// [`RING_MINUTES`] as a slot count.
pub const RING: usize = RING_MINUTES as usize;

/// Maximum gap between consecutive prints of one sweep run.
pub const SWEEP_GAP_MS: i64 = 50;

/// Prints in a run before it can be called a sweep.
pub const SWEEP_MIN_PRINTS: u32 = 3;

/// A round lot. Below it a print is an odd lot.
pub const ROUND_LOT: i64 = 100;

/// Multiple of the session-so-far median size that makes a print a block.
pub const BLOCK_MULTIPLE: i64 = 10;

// ---------------------------------------------------------------------------
// The aggressor law
// ---------------------------------------------------------------------------

/// Which side lifted. `Unresolved` is a state, not a zero.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Sign {
    Buy,
    Sell,
    /// The print carried no usable NBBO, or executed exactly at the mid. We do
    /// not know which side was the aggressor and we refuse to guess.
    Unresolved,
}

impl Sign {
    /// `+1` / `-1` for hard signs; `0` **only** as an arithmetic identity for
    /// callers that have already excluded unresolved prints from their
    /// denominator. Never use this to fold unresolved flow into a net.
    #[must_use]
    pub const fn as_i64(self) -> i64 {
        match self {
            Self::Buy => 1,
            Self::Sell => -1,
            Self::Unresolved => 0,
        }
    }

    /// True for `Buy`/`Sell`.
    #[must_use]
    pub const fn is_hard(self) -> bool {
        !matches!(self, Self::Unresolved)
    }
}

/// **The aggressor law.** See the module header; this is the only place it is
/// written down, and E2/E3 call it rather than restate it.
///
/// A malformed NBBO (non-positive side, or a crossed book) is `Unresolved`:
/// the vendor attached something, but not a book we can take a side from.
#[must_use]
pub const fn aggressor_sign(trade: &TradeEvent) -> Sign {
    if !trade.quote_present {
        return Sign::Unresolved;
    }
    if trade.bid_u6 <= 0 || trade.ask_u6 <= 0 || trade.ask_u6 < trade.bid_u6 {
        return Sign::Unresolved;
    }
    // 2*price vs bid+ask is exactly `price vs mid` with no rounding, so a tie
    // is a real at-the-mid print and never a truncation artefact. IWM prices
    // are ~2e8 in u6; doubling stays four orders inside i64.
    let twice = trade.price_u6.saturating_mul(2);
    let sum = trade.bid_u6.saturating_add(trade.ask_u6);
    if twice > sum {
        Sign::Buy
    } else if twice < sum {
        Sign::Sell
    } else {
        Sign::Unresolved
    }
}

// ---------------------------------------------------------------------------
// Shared primitives (E2 and E3 import these)
// ---------------------------------------------------------------------------

/// Absolute minute index of a frame-B millisecond. Anchor-free: the session
/// open is an exact minute in frame B, so these buckets are bar-aligned
/// without the family ever being told when the session opened.
#[must_use]
pub const fn minute_of(ts_ms: i64) -> i64 {
    ts_ms.div_euclid(BAR_MS)
}

/// A cutoff's frame-B instant in milliseconds.
#[must_use]
pub const fn cutoff_ms(cutoff: &ActionCutoff) -> i64 {
    cutoff.cutoff_ns_b.div_euclid(1_000_000)
}

/// `f64 -> f32` that refuses to emit an infinity. An overflowing or non-finite
/// value becomes `NaN` — declared absence — because a `+inf` in a feature leaf
/// is indistinguishable downstream from a genuine extreme.
#[must_use]
pub fn narrow(value: f64) -> f32 {
    if value.is_finite() && value.abs() <= f64::from(f32::MAX) {
        value as f32
    } else {
        f32::NAN
    }
}

/// A guarded ratio. A zero or non-finite denominator is absence (`NaN`), never
/// zero and never an infinity.
#[must_use]
pub fn ratio(numerator: f64, denominator: f64) -> f32 {
    if denominator == 0.0 || !denominator.is_finite() {
        return f32::NAN;
    }
    narrow(numerator / denominator)
}

/// A fixed-size ring of per-minute accumulators, indexed by absolute minute.
///
/// Slots for minutes the tape skipped are cleared as the ring advances, so a
/// quiet minute reads as an observed zero rather than as stale data from 64
/// minutes ago.
#[derive(Clone, Debug)]
pub struct Ring<T> {
    slots: Vec<T>,
    current: i64,
    started: bool,
}

impl<T: Default + Clone> Default for Ring<T> {
    fn default() -> Self {
        Self::new()
    }
}

impl<T: Default + Clone> Ring<T> {
    /// An empty ring. Slots are allocated on first use so the whole emitter
    /// stays `const`-constructible (see the `E1TapeFlow` constant).
    #[must_use]
    pub const fn new() -> Self {
        Self {
            slots: Vec::new(),
            current: 0,
            started: false,
        }
    }

    /// The most recent minute the ring has been advanced to.
    #[must_use]
    pub const fn current(&self) -> i64 {
        self.current
    }

    /// Whether any minute has been seen.
    #[must_use]
    pub const fn started(&self) -> bool {
        self.started
    }

    fn index(minute: i64) -> usize {
        (minute.rem_euclid(RING_MINUTES)) as usize
    }

    /// Advances to `minute`, clearing every slot in between. Never moves
    /// backwards: the driver merges quotes and prints in timestamp order, so a
    /// backwards step would be a driver defect, and clamping is the safe
    /// reading of one.
    pub fn advance_to(&mut self, minute: i64) {
        if self.slots.is_empty() {
            self.slots.resize(RING, T::default());
        }
        if !self.started {
            self.started = true;
            self.current = minute;
            for slot in &mut self.slots {
                *slot = T::default();
            }
            return;
        }
        if minute <= self.current {
            return;
        }
        if minute - self.current >= RING_MINUTES {
            for slot in &mut self.slots {
                *slot = T::default();
            }
        } else {
            let mut step = self.current + 1;
            while step <= minute {
                self.slots[Self::index(step)] = T::default();
                step += 1;
            }
        }
        self.current = minute;
    }

    /// The accumulator for the current minute.
    pub fn current_mut(&mut self) -> &mut T {
        if self.slots.is_empty() {
            self.slots.resize(RING, T::default());
        }
        let index = Self::index(self.current);
        &mut self.slots[index]
    }

    /// The accumulator for `minute`, advancing the ring if `minute` is ahead of
    /// it. `None` once `minute` has fallen out of the ring.
    ///
    /// Needed by time-integral columns, which credit an interval to the minute
    /// it elapsed in — and that minute can already be behind the ring's head if
    /// a print advanced the ring before the next quote closed the interval.
    pub fn slot_mut(&mut self, minute: i64) -> Option<&mut T> {
        self.advance_to(minute);
        if minute > self.current || self.current - minute >= RING_MINUTES {
            return None;
        }
        let index = Self::index(minute);
        self.slots.get_mut(index)
    }

    /// The accumulator for `minute`, or `None` if it has fallen out of the ring
    /// or has not happened yet.
    #[must_use]
    pub fn get(&self, minute: i64) -> Option<&T> {
        if !self.started || self.slots.is_empty() {
            return None;
        }
        if minute > self.current || self.current - minute >= RING_MINUTES {
            return None;
        }
        self.slots.get(Self::index(minute))
    }

    /// Folds the `window` complete minutes ending at `end_minute` inclusive.
    pub fn fold_window<A>(&self, end_minute: i64, window: i64, seed: A, mut step: impl FnMut(A, &T) -> A) -> A {
        let mut accumulator = seed;
        let mut offset = 0_i64;
        while offset < window {
            if let Some(slot) = self.get(end_minute - offset) {
                accumulator = step(accumulator, slot);
            }
            offset += 1;
        }
        accumulator
    }
}

// ---------------------------------------------------------------------------
// Session-so-far print-size distribution
// ---------------------------------------------------------------------------

/// Bins: `0..2048` are exact share counts, `2050..3072` cover 2048 shares and
/// up in 1,024-share steps. IWM's median and decile print sizes live two
/// orders inside the exact region, so every quantile this family reads is
/// exact, not binned.
const SIZE_BINS: usize = 3072;
const SIZE_EXACT: i64 = 2048;

/// The four quantiles tracked, as exact `(numerator, denominator)` fractions.
const QUANTILES: [(u64, u64); 4] = [(1, 4), (1, 2), (3, 4), (9, 10)];

/// Index of the median inside [`QUANTILES`].
const Q_MEDIAN: usize = 1;
/// Index of the top decile inside [`QUANTILES`].
const Q_DECILE: usize = 3;

/// Minimum prints before quartile classes are distinguishable at all.
const MIN_FOR_QUARTILE: u64 = 4;
/// Minimum prints before a top decile is distinguishable at all.
const MIN_FOR_DECILE: u64 = 10;

fn size_bin(size: i64) -> usize {
    if size <= 0 {
        0
    } else if size < SIZE_EXACT {
        size as usize
    } else {
        SIZE_EXACT as usize + ((size >> 10).min(1023) as usize)
    }
}

fn size_bin_lower(bin: usize) -> i64 {
    if bin < SIZE_EXACT as usize {
        bin as i64
    } else {
        ((bin - SIZE_EXACT as usize) as i64) << 10
    }
}

/// Session-so-far print-size quantiles, maintained exactly and incrementally.
///
/// Each tracked quantile keeps a bin pointer and the count strictly below it.
/// An insertion nudges the pointer by the few bins the new sample moved the
/// target, so the quantile is the exact histogram quantile after every print
/// at `O(1)` amortized — not a periodic recomputation and not a sketch.
#[derive(Clone, Debug)]
pub struct SizeQuantiles {
    bins: Vec<u32>,
    total: u64,
    pointer: [usize; 4],
    below: [u64; 4],
}

impl Default for SizeQuantiles {
    fn default() -> Self {
        Self::new()
    }
}

impl SizeQuantiles {
    /// An empty distribution.
    #[must_use]
    pub const fn new() -> Self {
        Self {
            bins: Vec::new(),
            total: 0,
            pointer: [0; 4],
            below: [0; 4],
        }
    }

    /// Prints observed so far.
    #[must_use]
    pub const fn total(&self) -> u64 {
        self.total
    }

    /// Adds one print size. Call this **after** classifying that print, so a
    /// print is never measured against a distribution that contains itself.
    pub fn insert(&mut self, size: i64) {
        if self.bins.is_empty() {
            self.bins.resize(SIZE_BINS, 0);
        }
        let bin = size_bin(size);
        self.bins[bin] += 1;
        self.total += 1;
        for index in 0..QUANTILES.len() {
            if bin < self.pointer[index] {
                self.below[index] += 1;
            }
            self.rebalance(index);
        }
    }

    fn rebalance(&mut self, index: usize) {
        let (numerator, denominator) = QUANTILES[index];
        // ceil(p * total): the smallest rank that satisfies the quantile.
        let target = self
            .total
            .saturating_mul(numerator)
            .div_ceil(denominator)
            .max(1);
        while self.below[index] + u64::from(self.bins[self.pointer[index]]) < target
            && self.pointer[index] + 1 < SIZE_BINS
        {
            self.below[index] += u64::from(self.bins[self.pointer[index]]);
            self.pointer[index] += 1;
        }
        while self.pointer[index] > 0 && self.below[index] >= target {
            self.pointer[index] -= 1;
            self.below[index] -= u64::from(self.bins[self.pointer[index]]);
        }
    }

    fn threshold(&self, index: usize) -> i64 {
        size_bin_lower(self.pointer[index])
    }

    /// Session-so-far median print size, or `None` while it is undefined.
    #[must_use]
    pub fn median(&self) -> Option<i64> {
        (self.total >= MIN_FOR_QUARTILE).then(|| self.threshold(Q_MEDIAN))
    }

    /// 0-based size quartile class of `size` against the prints before it, or
    /// `None` while four classes are not yet distinguishable.
    #[must_use]
    pub fn quartile_class(&self, size: i64) -> Option<usize> {
        if self.total < MIN_FOR_QUARTILE {
            return None;
        }
        if size <= self.threshold(0) {
            Some(0)
        } else if size <= self.threshold(1) {
            Some(1)
        } else if size <= self.threshold(2) {
            Some(2)
        } else {
            Some(3)
        }
    }

    /// Whether `size` is in the session-so-far top decile, or `None` while a
    /// decile is undefined.
    #[must_use]
    pub fn is_large(&self, size: i64) -> Option<bool> {
        (self.total >= MIN_FOR_DECILE).then(|| size >= self.threshold(Q_DECILE))
    }

    /// Whether `size` is at least [`BLOCK_MULTIPLE`] times the session-so-far
    /// median, or `None` while the median is undefined.
    #[must_use]
    pub fn is_block(&self, size: i64) -> Option<bool> {
        self.median()
            .map(|median| median > 0 && size >= median.saturating_mul(BLOCK_MULTIPLE))
    }
}

// ---------------------------------------------------------------------------
// Sweep detection
// ---------------------------------------------------------------------------

/// What a print contributed to sweep accounting.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SweepHit {
    /// True on the print that made the run qualify — count it once, here.
    pub qualified: bool,
    /// Shares to add to sweep volume.
    pub volume: i64,
    /// Side of the run.
    pub sign: Sign,
}

/// Stock prints carry no native sweep identifier (finding F-16), so a sweep is
/// defined in-spec: **at least three same-sign prints, each within 50 ms of the
/// previous, spanning at least two exchanges.**
///
/// The run is committed the instant it qualifies, at that print's minute, and
/// later prints in the same run add volume without a second count. Committing
/// only at run *close* would leave a qualified-but-open sweep invisible to a
/// cutoff that has already seen it; committing at every print would count it
/// repeatedly. An unresolved print breaks the run — a burst whose middle we
/// cannot side is not evidence of one-sided aggression.
#[derive(Clone, Copy, Debug)]
pub struct SweepDetector {
    sign: Sign,
    last_ts_ms: i64,
    prints: u32,
    first_exchange: i64,
    multi_exchange: bool,
    volume: i64,
    qualified: bool,
}

impl Default for SweepDetector {
    fn default() -> Self {
        Self::new()
    }
}

impl SweepDetector {
    /// An idle detector.
    #[must_use]
    pub const fn new() -> Self {
        Self {
            sign: Sign::Unresolved,
            last_ts_ms: i64::MIN,
            prints: 0,
            first_exchange: i64::MIN,
            multi_exchange: false,
            volume: 0,
            qualified: false,
        }
    }

    fn restart(&mut self, trade: &TradeEvent, sign: Sign) {
        self.sign = sign;
        self.last_ts_ms = trade.ts_ms_b;
        self.prints = 1;
        self.first_exchange = trade.exchange;
        self.multi_exchange = false;
        self.volume = trade.size.max(0);
        self.qualified = false;
    }

    /// Feeds one print. Returns what to record, if anything.
    pub fn observe(&mut self, trade: &TradeEvent, sign: Sign) -> Option<SweepHit> {
        if !sign.is_hard() {
            // Break the run: we cannot assert the burst stayed one-sided.
            self.sign = Sign::Unresolved;
            self.prints = 0;
            self.qualified = false;
            return None;
        }
        let continues = self.sign == sign
            && self.prints > 0
            && trade.ts_ms_b.saturating_sub(self.last_ts_ms) <= SWEEP_GAP_MS;
        if !continues {
            self.restart(trade, sign);
            return None;
        }
        self.prints += 1;
        self.last_ts_ms = trade.ts_ms_b;
        if trade.exchange != self.first_exchange {
            self.multi_exchange = true;
        }
        if self.qualified {
            return Some(SweepHit {
                qualified: false,
                volume: trade.size.max(0),
                sign,
            });
        }
        self.volume = self.volume.saturating_add(trade.size.max(0));
        if self.prints >= SWEEP_MIN_PRINTS && self.multi_exchange {
            self.qualified = true;
            return Some(SweepHit {
                qualified: true,
                volume: self.volume,
                sign,
            });
        }
        None
    }
}

// ---------------------------------------------------------------------------
// Columns
// ---------------------------------------------------------------------------

const COLUMNS: [ColSpec; 21] = [
    ColSpec::new("signed_vol_imb_1m", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("signed_vol_imb_5m", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("signed_vol_imb_15m", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("signed_vol_imb_30m", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new(
        "trade_intensity_vs_session_5m",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new("large_print_share_15m", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("large_print_imb_15m", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("block_count_15m", Unit::Count, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new(
        "buys_vwap_minus_sells_vwap_bps_15m",
        Unit::Bps,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new("upticks_share_5m", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("print_rate_accel", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("cvd_shares", Unit::Shares, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("cvd_slope_15m", Unit::Shares, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("cvd_over_volume", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("unresolved_share_15m", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("sweep_count_5m", Unit::Count, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("sweep_volume_share_5m", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("largest_print_z_15m", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("prints_at_bid_share_15m", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("prints_at_ask_share_15m", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("odd_lot_share_15m", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
];

/// One minute of print accumulators.
#[derive(Clone, Copy, Debug, Default)]
struct Bucket {
    signed_volume: i64,
    total_volume: i64,
    unresolved_volume: i64,
    prints: u32,
    unresolved_prints: u32,
    buy_shares: i64,
    buy_notional: f64,
    sell_shares: i64,
    sell_notional: f64,
    all_notional: f64,
    upticks: u32,
    downticks: u32,
    large_prints: u32,
    large_signed_volume: i64,
    large_volume: i64,
    blocks: u32,
    at_bid: u32,
    at_ask: u32,
    quoted_prints: u32,
    odd_lots: u32,
    sweeps: u32,
    sweep_volume: i64,
    size_sum: f64,
    size_sumsq: f64,
    size_max: i64,
}

/// Signed-flow, print-size and sweep structure of one session's stock tape.
#[derive(Clone, Debug)]
pub struct TapeFlow {
    ring: Ring<Bucket>,
    sizes: SizeQuantiles,
    sweeps: SweepDetector,
    last_price_u6: i64,
    cvd_shares: i64,
    session_volume: i64,
    session_prints: u64,
    rows: Vec<f32>,
}

impl Default for TapeFlow {
    fn default() -> Self {
        Self::new()
    }
}

/// Value-namespace constructor for `families::build`, which spells the family
/// as the unit-struct expression `Box::new(e1_tape_flow::E1TapeFlow)`.
/// `mod.rs` belongs to another lane, so the emitter supplies the value that
/// expression needs instead of forcing an edit there — the same shape
/// `a1_clock` and `c2_trend_path` already use. A `const` is copied at each use
/// site, so every session gets its own state. Once `build` says
/// `TapeFlow::default()`, delete this.
#[allow(non_upper_case_globals)]
pub const E1TapeFlow: TapeFlow = TapeFlow::new();

impl TapeFlow {
    /// A fresh emitter for one session.
    #[must_use]
    pub const fn new() -> Self {
        Self {
            ring: Ring::new(),
            sizes: SizeQuantiles::new(),
            sweeps: SweepDetector::new(),
            last_price_u6: i64::MIN,
            cvd_shares: 0,
            session_volume: 0,
            session_prints: 0,
            rows: Vec::new(),
        }
    }
}

/// Everything a window fold accumulates. One pass over the buckets fills it.
#[derive(Clone, Copy, Debug, Default)]
struct Window {
    signed_volume: i64,
    total_volume: i64,
    unresolved_volume: i64,
    prints: u64,
    unresolved_prints: u64,
    buy_shares: i64,
    buy_notional: f64,
    sell_shares: i64,
    sell_notional: f64,
    all_notional: f64,
    upticks: u64,
    downticks: u64,
    large_prints: u64,
    large_signed_volume: i64,
    large_volume: i64,
    blocks: u64,
    at_bid: u64,
    at_ask: u64,
    quoted_prints: u64,
    odd_lots: u64,
    sweeps: u64,
    sweep_volume: i64,
    size_sum: f64,
    size_sumsq: f64,
    size_max: i64,
}

impl Window {
    fn absorb(mut self, bucket: &Bucket) -> Self {
        self.signed_volume += bucket.signed_volume;
        self.total_volume += bucket.total_volume;
        self.unresolved_volume += bucket.unresolved_volume;
        self.prints += u64::from(bucket.prints);
        self.unresolved_prints += u64::from(bucket.unresolved_prints);
        self.buy_shares += bucket.buy_shares;
        self.buy_notional += bucket.buy_notional;
        self.sell_shares += bucket.sell_shares;
        self.sell_notional += bucket.sell_notional;
        self.all_notional += bucket.all_notional;
        self.upticks += u64::from(bucket.upticks);
        self.downticks += u64::from(bucket.downticks);
        self.large_prints += u64::from(bucket.large_prints);
        self.large_signed_volume += bucket.large_signed_volume;
        self.large_volume += bucket.large_volume;
        self.blocks += u64::from(bucket.blocks);
        self.at_bid += u64::from(bucket.at_bid);
        self.at_ask += u64::from(bucket.at_ask);
        self.quoted_prints += u64::from(bucket.quoted_prints);
        self.odd_lots += u64::from(bucket.odd_lots);
        self.sweeps += u64::from(bucket.sweeps);
        self.sweep_volume += bucket.sweep_volume;
        self.size_sum += bucket.size_sum;
        self.size_sumsq += bucket.size_sumsq;
        self.size_max = self.size_max.max(bucket.size_max);
        self
    }
}

impl TapeFlow {
    fn window(&self, end_minute: i64, minutes: i64) -> Window {
        self.ring
            .fold_window(end_minute, minutes, Window::default(), Window::absorb)
    }
}

impl FamilyEmitter for TapeFlow {
    fn name(&self) -> &'static str {
        NAME
    }

    fn columns(&self) -> &[ColSpec] {
        &COLUMNS
    }

    fn on_quote(&mut self, _quote: &QuoteEvent) {
        // Prints carry their own prevailing NBBO, so this family reads none.
        // The quote-side objects live in `e2_gt_intent` and `e3_raid_sonar`.
    }

    fn on_trade(&mut self, trade: &TradeEvent) {
        let size = trade.size.max(0);
        let sign = aggressor_sign(trade);
        let large = self.sizes.is_large(size);
        let block = self.sizes.is_block(size);
        self.sizes.insert(size);

        let price = trade.price_u6;
        let previous = self.last_price_u6;
        self.last_price_u6 = price;

        let hit = self.sweeps.observe(trade, sign);

        self.ring.advance_to(minute_of(trade.ts_ms_b));
        let notional = (price as f64 / 1_000_000.0) * size as f64;
        let bucket = self.ring.current_mut();
        bucket.prints += 1;
        bucket.total_volume += size;
        bucket.all_notional += notional;
        bucket.size_sum += size as f64;
        bucket.size_sumsq += (size as f64) * (size as f64);
        bucket.size_max = bucket.size_max.max(size);
        if size < ROUND_LOT {
            bucket.odd_lots += 1;
        }
        if previous != i64::MIN {
            if price > previous {
                bucket.upticks += 1;
            } else if price < previous {
                bucket.downticks += 1;
            }
        }
        if trade.quote_present && trade.bid_u6 > 0 && trade.ask_u6 > 0 {
            bucket.quoted_prints += 1;
            if price == trade.bid_u6 {
                bucket.at_bid += 1;
            }
            if price == trade.ask_u6 {
                bucket.at_ask += 1;
            }
        }
        match sign {
            Sign::Buy => {
                bucket.signed_volume += size;
                bucket.buy_shares += size;
                bucket.buy_notional += notional;
            }
            Sign::Sell => {
                bucket.signed_volume -= size;
                bucket.sell_shares += size;
                bucket.sell_notional += notional;
            }
            Sign::Unresolved => {
                bucket.unresolved_prints += 1;
                bucket.unresolved_volume += size;
            }
        }
        if large == Some(true) {
            bucket.large_prints += 1;
            bucket.large_volume += size;
            bucket.large_signed_volume += sign.as_i64() * size;
        }
        if block == Some(true) {
            bucket.blocks += 1;
        }
        if let Some(hit) = hit {
            if hit.qualified {
                bucket.sweeps += 1;
            }
            bucket.sweep_volume += hit.volume;
        }

        self.cvd_shares += sign.as_i64() * size;
        self.session_volume += size;
        self.session_prints += 1;
    }

    #[allow(clippy::too_many_lines)]
    fn on_cutoff(&mut self, cutoff: &ActionCutoff) {
        let instant = cutoff_ms(cutoff);
        self.ring.advance_to(minute_of(instant));
        // The cutoff is the START of `minute_of(instant)`, so the window is the
        // complete minutes below it. Exact, no partial bucket.
        let end = minute_of(instant) - 1;

        let w1 = self.window(end, 1);
        let w5 = self.window(end, 5);
        let w15 = self.window(end, 15);
        let w30 = self.window(end, 30);

        self.rows.push(ratio(w1.signed_volume as f64, w1.total_volume as f64));
        self.rows.push(ratio(w5.signed_volume as f64, w5.total_volume as f64));
        self.rows.push(ratio(w15.signed_volume as f64, w15.total_volume as f64));
        self.rows.push(ratio(w30.signed_volume as f64, w30.total_volume as f64));

        // Session-so-far rate uses elapsed bars: a cutoff at bar N is exactly N
        // minutes after the open, so no session anchor is needed here either.
        let elapsed = f64::from(cutoff.cutoff_bar_ordinal.max(0));
        let session_rate = if elapsed > 0.0 {
            self.session_prints as f64 / elapsed
        } else {
            0.0
        };
        self.rows.push(ratio(w5.prints as f64 / 5.0, session_rate));

        self.rows.push(ratio(w15.large_prints as f64, w15.prints as f64));
        self.rows
            .push(ratio(w15.large_signed_volume as f64, w15.large_volume as f64));
        self.rows.push(narrow(w15.blocks as f64));

        // Both sides must have traded for a difference of VWAPs to exist; the
        // window's own all-print VWAP is the bps reference, so the column needs
        // no quote and no external price level.
        let vwap_spread = if w15.buy_shares > 0 && w15.sell_shares > 0 && w15.total_volume > 0 {
            let buy_vwap = w15.buy_notional / w15.buy_shares as f64;
            let sell_vwap = w15.sell_notional / w15.sell_shares as f64;
            let reference = w15.all_notional / w15.total_volume as f64;
            ratio((buy_vwap - sell_vwap) * 10_000.0, reference)
        } else {
            f32::NAN
        };
        self.rows.push(vwap_spread);

        // Zero-ticks are neither up nor down; they leave the denominator.
        self.rows
            .push(ratio(w5.upticks as f64, (w5.upticks + w5.downticks) as f64));
        self.rows
            .push(ratio(w5.prints as f64 / 5.0, w15.prints as f64 / 15.0));

        self.rows.push(narrow(self.cvd_shares as f64));
        self.rows.push(narrow(w15.signed_volume as f64 / 15.0));
        self.rows
            .push(ratio(self.cvd_shares as f64, self.session_volume as f64));
        self.rows
            .push(ratio(w15.unresolved_prints as f64, w15.prints as f64));

        self.rows.push(narrow(w5.sweeps as f64));
        self.rows
            .push(ratio(w5.sweep_volume as f64, w5.total_volume as f64));

        let z = if w15.prints >= 2 {
            let count = w15.prints as f64;
            let mean = w15.size_sum / count;
            let variance = (w15.size_sumsq / count) - mean * mean;
            if variance > 0.0 {
                ratio(w15.size_max as f64 - mean, variance.sqrt())
            } else {
                f32::NAN
            }
        } else {
            f32::NAN
        };
        self.rows.push(z);

        self.rows
            .push(ratio(w15.at_bid as f64, w15.quoted_prints as f64));
        self.rows
            .push(ratio(w15.at_ask as f64, w15.quoted_prints as f64));
        self.rows.push(ratio(w15.odd_lots as f64, w15.prints as f64));
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

#[cfg(test)]
mod tests {
    // Every float compared for equality below is an exact small-integer ratio
    // (0/n or n/n) or an exactly representable constant, not an accumulated
    // sum. Equality is the assertion being made, so a tolerance would weaken
    // it rather than harden it.
    #![allow(clippy::float_cmp)]

    use super::*;
    use crate::book::Side;

    /// A print with a symmetric one-cent NBBO around `mid_u6`.
    pub(super) fn print_at(ts_ms: i64, price_u6: i64, size: i64, mid_u6: i64) -> TradeEvent {
        TradeEvent {
            ts_ms_b: ts_ms,
            price_u6,
            size,
            exchange: 4,
            condition: 0,
            sequence: 0,
            bid_u6: mid_u6 - 5_000,
            ask_u6: mid_u6 + 5_000,
            bid_shares: 100,
            ask_shares: 100,
            quote_present: true,
        }
    }

    pub(super) fn cutoff_at(bar: i32) -> ActionCutoff {
        ActionCutoff {
            action_id: format!("t-{bar}"),
            day: "2022-03-01",
            session_ordinal: 0,
            cutoff_bar_ordinal: bar,
            side: Side::High,
            cutoff_ns_a: 0,
            // Bar `n` closes `n` minutes after an exact-minute open; minute 0
            // here stands in for that open.
            cutoff_ns_b: i64::from(bar) * BAR_MS * 1_000_000,
            first_visibility_ns: 0,
            last_visibility_ns: 0,
            act_set: crate::book::ActSetSummary::default(),
        }
    }

    #[test]
    fn aggressor_law_has_three_states_and_never_rounds() {
        let mid = 200_000_000;
        // Half a cent above the mid: a buy, and only exact arithmetic sees it.
        assert_eq!(aggressor_sign(&print_at(0, mid + 5_000, 100, mid)), Sign::Buy);
        assert_eq!(aggressor_sign(&print_at(0, mid - 5_000, 100, mid)), Sign::Sell);
        assert_eq!(
            aggressor_sign(&print_at(0, mid, 100, mid)),
            Sign::Unresolved,
            "at-the-mid is unresolved, not a zero-signed buy"
        );
        // An odd-sum book: bid+ask = 2*mid+1, so the true mid is a half-unit
        // above `mid`. A print at `mid` must be a SELL; a rounded mid would
        // call it a tie.
        let mut odd = print_at(0, mid, 100, mid);
        odd.ask_u6 += 1;
        assert_eq!(aggressor_sign(&odd), Sign::Sell);

        let mut absent = print_at(0, mid + 5_000, 100, mid);
        absent.quote_present = false;
        assert_eq!(aggressor_sign(&absent), Sign::Unresolved);

        let mut crossed = print_at(0, mid + 5_000, 100, mid);
        crossed.bid_u6 = crossed.ask_u6 + 1;
        assert_eq!(aggressor_sign(&crossed), Sign::Unresolved);
    }

    #[test]
    fn size_quantiles_match_a_hand_distribution() {
        let mut quantiles = SizeQuantiles::new();
        // 1..=100, so the exact quantiles are known by hand.
        for size in 1..=100_i64 {
            quantiles.insert(size);
        }
        assert_eq!(quantiles.total(), 100);
        assert_eq!(quantiles.median(), Some(50));
        // p90 of 1..=100 is the 90th smallest, i.e. 90.
        assert_eq!(quantiles.is_large(90), Some(true));
        assert_eq!(quantiles.is_large(89), Some(false));
        // Quartile edges: 25 / 50 / 75.
        assert_eq!(quantiles.quartile_class(25), Some(0));
        assert_eq!(quantiles.quartile_class(26), Some(1));
        assert_eq!(quantiles.quartile_class(50), Some(1));
        assert_eq!(quantiles.quartile_class(51), Some(2));
        assert_eq!(quantiles.quartile_class(75), Some(2));
        assert_eq!(quantiles.quartile_class(76), Some(3));
        // Blocks are 10x the median.
        assert_eq!(quantiles.is_block(500), Some(true));
        assert_eq!(quantiles.is_block(499), Some(false));
    }

    #[test]
    fn quantiles_are_undefined_before_they_are_distinguishable() {
        let mut quantiles = SizeQuantiles::new();
        assert_eq!(quantiles.quartile_class(100), None);
        assert_eq!(quantiles.is_large(100), None);
        quantiles.insert(100);
        quantiles.insert(200);
        quantiles.insert(300);
        assert_eq!(quantiles.quartile_class(100), None, "3 prints cannot make 4 classes");
        quantiles.insert(400);
        assert_eq!(quantiles.quartile_class(100), Some(0));
        assert_eq!(quantiles.is_large(400), None, "4 prints cannot make a decile");
    }

    #[test]
    fn sweep_needs_three_prints_two_exchanges_and_fifty_milliseconds() {
        let mid = 200_000_000;
        let buy = |ts: i64, exchange: i64| {
            let mut trade = print_at(ts, mid + 5_000, 100, mid);
            trade.exchange = exchange;
            trade
        };
        // Three prints, one exchange -> no sweep.
        let mut detector = SweepDetector::new();
        assert!(detector.observe(&buy(0, 4), Sign::Buy).is_none());
        assert!(detector.observe(&buy(10, 4), Sign::Buy).is_none());
        assert!(detector.observe(&buy(20, 4), Sign::Buy).is_none());

        // Three prints, two exchanges, inside the gap -> one sweep of 300.
        let mut detector = SweepDetector::new();
        assert!(detector.observe(&buy(0, 4), Sign::Buy).is_none());
        assert!(detector.observe(&buy(10, 8), Sign::Buy).is_none());
        let hit = detector.observe(&buy(20, 8), Sign::Buy).expect("qualifies");
        assert!(hit.qualified);
        assert_eq!(hit.volume, 300);
        // A fourth print adds volume but not a second count.
        let hit = detector.observe(&buy(30, 8), Sign::Buy).expect("extends");
        assert!(!hit.qualified);
        assert_eq!(hit.volume, 100);

        // A 51 ms gap restarts the run.
        let mut detector = SweepDetector::new();
        assert!(detector.observe(&buy(0, 4), Sign::Buy).is_none());
        assert!(detector.observe(&buy(51, 8), Sign::Buy).is_none());
        assert!(detector.observe(&buy(61, 8), Sign::Buy).is_none());

        // An unresolved print in the middle breaks the run.
        let mut detector = SweepDetector::new();
        assert!(detector.observe(&buy(0, 4), Sign::Buy).is_none());
        assert!(
            detector
                .observe(&print_at(5, mid, 100, mid), Sign::Unresolved)
                .is_none()
        );
        assert!(detector.observe(&buy(10, 8), Sign::Buy).is_none());
        assert!(detector.observe(&buy(20, 8), Sign::Buy).is_none());
    }

    #[test]
    fn ring_clears_skipped_minutes_instead_of_reading_stale_ones() {
        let mut ring: Ring<Bucket> = Ring::new();
        ring.advance_to(10);
        ring.current_mut().prints = 7;
        ring.advance_to(11);
        assert_eq!(ring.get(10).map(|b| b.prints), Some(7));
        assert_eq!(ring.get(11).map(|b| b.prints), Some(0));
        // Jump a full ring: the old minute 10 must not reappear at 10 + RING.
        ring.advance_to(10 + RING as i64);
        assert_eq!(ring.get(10 + RING as i64).map(|b| b.prints), Some(0));
        assert_eq!(ring.get(10).map(|b| b.prints), None, "fallen out of the ring");
    }

    /// A hand tape: one buy of 300 and one sell of 100 in minute 0, read at the
    /// close of bar 1. Every number below is checkable on paper.
    #[test]
    fn hand_tape_imbalance_and_shares() {
        let mid = 200_000_000;
        let mut family = TapeFlow::new();
        family.on_trade(&print_at(1_000, mid + 5_000, 300, mid));
        family.on_trade(&print_at(2_000, mid - 5_000, 100, mid));
        family.on_trade(&print_at(3_000, mid, 200, mid)); // at the mid: unresolved
        let cutoff = cutoff_at(1);
        family.on_cutoff(&cutoff);
        let rows = family.emit(std::slice::from_ref(&cutoff)).expect("emit");
        assert_eq!(rows.columns, COLUMNS.len());
        assert_eq!(rows.rows(), 1);

        let column = |name: &str| {
            let index = COLUMNS.iter().position(|c| c.name == name).expect("column");
            rows.values[index]
        };
        // signed = +300 - 100 = +200; total volume = 600 (the unresolved 200
        // stays in the denominator).
        assert!((column("signed_vol_imb_1m") - 200.0 / 600.0).abs() < 1e-6);
        assert!((column("cvd_shares") - 200.0).abs() < 1e-6);
        assert!((column("cvd_over_volume") - 200.0 / 600.0).abs() < 1e-6);
        // 1 of 3 prints is unresolved.
        assert!((column("unresolved_share_15m") - 1.0 / 3.0).abs() < 1e-6);
        // Ticks: up (mid+5000 -> mid-5000 is a downtick, then mid is an uptick).
        assert!((column("upticks_share_5m") - 0.5).abs() < 1e-6);
        // All three prints are round lots of >= 100.
        assert!((column("odd_lot_share_15m") - 0.0).abs() < 1e-6);
        // buy VWAP - sell VWAP = one cent = 10_000 u6 = $0.01 on a $200 mid.
        let expected_bps = 0.01 / (mid as f64 / 1e6) * 10_000.0;
        assert!((f64::from(column("buys_vwap_minus_sells_vwap_bps_15m")) - expected_bps).abs() < 0.5);
    }

    #[test]
    fn quiet_minutes_read_as_zero_not_as_stale_flow() {
        let mid = 200_000_000;
        let mut family = TapeFlow::new();
        family.on_trade(&print_at(1_000, mid + 5_000, 300, mid));
        // Nothing at all for two minutes, then read at the close of bar 3.
        let cutoff = cutoff_at(3);
        family.on_cutoff(&cutoff);
        let rows = family.emit(std::slice::from_ref(&cutoff)).expect("emit");
        let column = |name: &str| {
            let index = COLUMNS.iter().position(|c| c.name == name).expect("column");
            rows.values[index]
        };
        // Minute 2 is empty -> no prints -> absence, not a carried-forward
        // imbalance.
        assert!(column("signed_vol_imb_1m").is_nan());
        // The 15 minute window still holds minute 0.
        assert!((column("signed_vol_imb_15m") - 1.0).abs() < 1e-6);
        assert!(column("cvd_shares") > 299.0);
    }

    #[test]
    fn no_column_is_ever_infinite() {
        let mid = 200_000_000;
        let mut family = TapeFlow::new();
        // A single print, so several denominators are zero or degenerate.
        family.on_trade(&print_at(1_000, mid + 5_000, 100, mid));
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

/// Integration over one real registered session, plus the corpus measurements
/// the three flow families rest on (minute-aligned cutoffs, the quote tick
/// grid, and the print spacing behind `e3_raid_sonar`'s lambda mapping).
#[cfg(test)]
mod integration {
    // See the note in `tests`: the equality assertions here are on exact zeros
    // that the measurement above proves are structural.
    #![allow(clippy::float_cmp)]

    use super::{Sign, aggressor_sign};
    use crate::book;
    use crate::calendar;
    use crate::families::{ColSpec, FamilyEmitter, FamilyRows, QuoteEvent, TradeEvent};
    use crate::session_pass::{SessionPassConfig, run_session};
    use crate::sources::TokenRoots;
    use std::sync::{Arc, Mutex};

    const DAY: &str = "2022-03-01";
    const LANE: [&str; 3] = ["e1_tape_flow", "e2_gt_intent", "e3_raid_sonar"];
    /// The quote tick this lane assumes, in u6.
    const ASSUMED_TICK_U6: i64 = 10_000;

    /// What the session actually contained. Not a feature family — a measuring
    /// instrument that rides the same pass, so every number in the lane report
    /// is computed rather than assumed.
    #[derive(Clone, Debug, Default)]
    struct Census {
        quotes: u64,
        prints: u64,
        buys: u64,
        sells: u64,
        unresolved: u64,
        first_print_ms: i64,
        last_print_ms: i64,
        off_grid_spreads: u64,
        min_positive_spread_u6: i64,
        crossed_or_empty: u64,
        /// Best-price hold durations, to test whether a "standing best" of the
        /// length `e3_raid_sonar::STANDING_MS` asks for exists at all on IWM.
        bid_price_u6: i64,
        bid_since_ms: i64,
        ask_price_u6: i64,
        ask_since_ms: i64,
        holds: u64,
        hold_max_ms: i64,
        holds_over_1s: u64,
        holds_over_30s: u64,
        hold_sum_ms: i64,
    }

    impl Census {
        fn close_hold(&mut self, since_ms: i64, now_ms: i64) {
            let held = now_ms - since_ms;
            if held < 0 {
                return;
            }
            self.holds += 1;
            self.hold_sum_ms += held;
            self.hold_max_ms = self.hold_max_ms.max(held);
            if held >= 1_000 {
                self.holds_over_1s += 1;
            }
            if held >= 30_000 {
                self.holds_over_30s += 1;
            }
        }
    }

    #[derive(Debug)]
    struct CensusEmitter(Arc<Mutex<Census>>);

    impl FamilyEmitter for CensusEmitter {
        fn name(&self) -> &'static str {
            "census_probe"
        }
        fn columns(&self) -> &[ColSpec] {
            &[]
        }
        fn on_quote(&mut self, quote: &QuoteEvent) {
            let mut census = self.0.lock().expect("census");
            census.quotes += 1;
            if quote.bid_u6 <= 0 || quote.ask_u6 <= 0 || quote.ask_u6 < quote.bid_u6 {
                census.crossed_or_empty += 1;
                return;
            }
            let spread = quote.ask_u6 - quote.bid_u6;
            if spread % ASSUMED_TICK_U6 != 0 {
                census.off_grid_spreads += 1;
            }
            if spread > 0 && (census.min_positive_spread_u6 == 0 || spread < census.min_positive_spread_u6)
            {
                census.min_positive_spread_u6 = spread;
            }
            let ts = quote.ts_ms_b;
            if census.bid_price_u6 != quote.bid_u6 {
                if census.bid_price_u6 != 0 {
                    let since = census.bid_since_ms;
                    census.close_hold(since, ts);
                }
                census.bid_price_u6 = quote.bid_u6;
                census.bid_since_ms = ts;
            }
            if census.ask_price_u6 != quote.ask_u6 {
                if census.ask_price_u6 != 0 {
                    let since = census.ask_since_ms;
                    census.close_hold(since, ts);
                }
                census.ask_price_u6 = quote.ask_u6;
                census.ask_since_ms = ts;
            }
        }
        fn on_trade(&mut self, trade: &TradeEvent) {
            let mut census = self.0.lock().expect("census");
            census.prints += 1;
            if census.first_print_ms == 0 {
                census.first_print_ms = trade.ts_ms_b;
            }
            census.last_print_ms = trade.ts_ms_b;
            match aggressor_sign(trade) {
                Sign::Buy => census.buys += 1,
                Sign::Sell => census.sells += 1,
                Sign::Unresolved => census.unresolved += 1,
            }
        }
        fn on_cutoff(&mut self, _cutoff: &book::ActionCutoff) {}
        fn emit(&mut self, _cutoffs: &[book::ActionCutoff]) -> crate::error::Result<FamilyRows> {
            Ok(FamilyRows::default())
        }
    }

    #[test]
    #[allow(clippy::too_many_lines)]
    fn the_flow_lane_emits_one_bounded_row_per_action_on_a_real_session() {
        let scope = calendar::admit(DAY).expect("2022-03-01 is a registry session");
        let ordinal = u32::try_from(scope.session_ordinal()).expect("ordinal fits u32");

        // Every trailing window in this lane is a whole number of absolute
        // minute buckets. That is only exact because a cutoff lands on a minute
        // boundary. Measured here, never assumed.
        assert_eq!(
            scope.open_ms_b() % super::BAR_MS,
            0,
            "frame-B open is not on a minute boundary"
        );

        let loaded =
            book::load_sessions(std::path::Path::new(book::DEFAULT_BOOK_DIR), Some(&[ordinal]))
                .expect("action book");
        let cutoffs = loaded.cutoffs_for(ordinal).to_vec();
        assert!(cutoffs.len() > 100, "not enough actions to be evidence");
        for cutoff in &cutoffs {
            assert_eq!(
                cutoff.cutoff_ns_b % (super::BAR_MS * 1_000_000),
                0,
                "cutoff {} is not on a minute boundary",
                cutoff.action_id
            );
        }

        let roots = TokenRoots::default();
        let config = SessionPassConfig {
            stock_quotes_root: roots.stock_quotes(),
            stock_trades_root: roots.stock_trades(),
            out_dir: std::path::PathBuf::from("/workspace/artifacts/cache/select_v2_test_out")
                .join("r4_lane"),
            write_pp1: false,
            write_families: false,
        };
        let census = Arc::new(Mutex::new(Census::default()));
        let mut families: Vec<Box<dyn FamilyEmitter>> = LANE
            .iter()
            .map(|name| crate::families::build(name).expect("registered family"))
            .collect();
        families.push(Box::new(CensusEmitter(Arc::clone(&census))));

        let outcome = run_session(&scope, &cutoffs, &mut families, &config).expect("pass");
        assert!(outcome.quote_rows > 0 && outcome.trade_rows > 0);

        let measured = census.lock().expect("census").clone();
        let span_s = (measured.last_print_ms - measured.first_print_ms) as f64 / 1_000.0;
        let spacing_s = span_s / (measured.prints.max(1) - 1).max(1) as f64;
        println!("--- {DAY} census ---");
        println!("quotes\t{}", measured.quotes);
        println!("prints\t{}", measured.prints);
        println!(
            "sign_buy/sell/unresolved\t{}/{}/{}",
            measured.buys, measured.sells, measured.unresolved
        );
        println!("crossed_or_empty_quotes\t{}", measured.crossed_or_empty);
        println!(
            "spreads_off_the_1c_grid\t{}\tmin_positive_spread_u6\t{}",
            measured.off_grid_spreads, measured.min_positive_spread_u6
        );
        println!("mean_print_spacing_s\t{spacing_s:.6}");
        println!(
            "best_price_holds\t{}\tmax_ms\t{}\tmean_ms\t{:.1}\tover_1s\t{}\tover_30s\t{}",
            measured.holds,
            measured.hold_max_ms,
            measured.hold_sum_ms as f64 / measured.holds.max(1) as f64,
            measured.holds_over_1s,
            measured.holds_over_30s
        );
        println!(
            "lambda_bar_30s\t{:.9}\tlambda_bar_300s\t{:.9}",
            0.5_f64.powf(spacing_s / 30.0),
            0.5_f64.powf(spacing_s / 300.0)
        );

        // The quote tick grid is a corpus convention, not a constant we get to
        // pick. If this session ever quotes off the one-cent grid, the lane's
        // tick-denominated columns need re-measuring before they mean anything.
        assert_eq!(
            measured.off_grid_spreads, 0,
            "quoted spreads left the one-cent grid; e2_gt_intent::TICK_U6 must be re-measured"
        );
        assert!(
            measured.unresolved > 0,
            "an unresolved bucket that is never populated is not evidence it is separate"
        );

        // **MEASURED, 2022-03-01: the NBBO touch never stands for 30 seconds**
        // (506,161 episodes, longest 5,228 ms, mean 92.5 ms, 4,757 over 1 s,
        // zero over 30 s) — which made the course's 30 s standing threshold a
        // dead constant on L1 data. Architect ruling 2026-08-07 re-typed the
        // threshold as the IWM-native `STANDING_MS = 1_000` (ADAPTED), which
        // this distribution makes genuinely reachable (~4,757 episodes/day).
        // Pinned both ways: the 1 s threshold must be LIVE on a real session,
        // and the 30 s reading stays impossible so the ruling's basis is
        // re-checked every run.
        assert!(
            measured.hold_max_ms >= super::super::e3_raid_sonar::STANDING_MS,
            "no best price stood {} ms on a real session: the absorption \
             block is dead again and its three columns need re-reading",
            super::super::e3_raid_sonar::STANDING_MS
        );
        assert_eq!(measured.holds_over_30s, 0);

        for family in &mut families {
            let name = family.name();
            if name == "census_probe" {
                continue;
            }
            let specs: Vec<&'static str> = family.columns().iter().map(|spec| spec.name).collect();
            let rows = family.emit(&cutoffs).expect("emit");
            assert_eq!(rows.columns, specs.len(), "{name} width");
            assert_eq!(rows.rows(), cutoffs.len(), "{name} rows != cutoffs");

            let mut absent = vec![0_usize; specs.len()];
            let mut nonzero = vec![0_usize; specs.len()];
            for (index, value) in rows.values.iter().enumerate() {
                let column = index % rows.columns;
                assert!(
                    value.is_finite() || value.is_nan(),
                    "{name}.{} is +/-inf at row {}",
                    specs[column],
                    index / rows.columns
                );
                if value.is_nan() {
                    absent[column] += 1;
                } else if *value != 0.0 {
                    nonzero[column] += 1;
                }
                if specs[column] == "unresolved_share_15m" && value.is_finite() {
                    assert!(
                        (0.0..=1.0).contains(value),
                        "unresolved_share_15m = {value} outside [0,1]"
                    );
                }
                if specs[column] == "unresolved_volume_share_15m" && value.is_finite() {
                    assert!((0.0..=1.0).contains(value));
                }
                if specs[column] == "pressure_pctile_session" && value.is_finite() {
                    assert!((0.0..=1.0).contains(value));
                }
                // Under the 1 s STANDING_MS ruling the absorption block is
                // LIVE (the hold assertion above proves reachability), so the
                // columns are bounded, never asserted constant.
                if specs[column] == "absorbed_volume_touch_15m" && value.is_finite() {
                    assert!(
                        *value >= 0.0,
                        "absorbed volume went negative: {value}"
                    );
                }
                if specs[column] == "post_absorption_move_bps" {
                    assert!(
                        value.is_nan() || value.is_finite(),
                        "post-absorption follow-through is non-finite: {value}"
                    );
                }
            }
            println!("--- {name} column\tabsent\tnonzero  of {} rows ---", cutoffs.len());
            for (column, count) in absent.iter().enumerate() {
                println!("{}\t{}\t{}", specs[column], count, nonzero[column]);
            }
            // The unresolved bucket is populated on this session, so its share
            // column is an observation on every action, never an absence.
            if let Some(column) = specs.iter().position(|s| *s == "unresolved_share_15m") {
                assert_eq!(absent[column], 0, "unresolved_share_15m went absent");
            }
        }
    }
}
