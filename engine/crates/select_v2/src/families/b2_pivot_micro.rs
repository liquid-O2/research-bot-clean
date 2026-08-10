//! `b2_pivot_micro` — **20 columns**: what the tape did at the session extreme
//! the action leans on, read as-of its cutoff.
//!
//! The family runs **two mirrored state machines**, one anchored on the running
//! session HIGH and one on the running session LOW, and a cutoff reads only the
//! machine matching its own side. Both are fed every event, because which side
//! an action will ask about is not known until the cutoff arrives.
//!
//! ## What "the extreme" is, exactly
//!
//! The extreme is the running max (HIGH) / min (LOW) of the computed midpoint
//! `(bid + ask) / 2`, the same series B1 uses — so the two families never
//! disagree about where the pivot sits. Around it:
//!
//! * **at the extreme** means within +/- 1 tick. One IWM tick is
//!   `TICK_U6` = 10,000 u6 = 1 cent; measured on 2022-03-01 the bid/ask grid is
//!   whole cents and the RTH median spread is 2 cents.
//! * a **touch** is a quote whose midpoint is at the extreme. Touches collapse
//!   into episodes: a maximal run of consecutive touching quotes counts once,
//!   otherwise the count would just be a quote count.
//! * the **defended book side** is the side that has to absorb the flow: the
//!   ASK at a session high, the BID at a session low. The refill/depletion
//!   machine watches that side's displayed size at the extreme price.
//!
//! ## Aggressor sign
//!
//! A print is a buy when its price is above the **prevailing NBBO midpoint**,
//! a sell when below, and **unresolved** at the midpoint or before this session
//! has shown its first quote. The prevailing midpoint is the last one from the
//! quote stream — the driver delivers quotes before prints on a timestamp tie
//! precisely so this is the pre-print state — not the NBBO the vendor stamped
//! onto the print row, which can carry a different instant. Unresolved prints
//! are **never folded** into either side: they enter neither the numerator nor
//! the denominator of any imbalance, and they are not sweep members.
//!
//! ## Windows, and why none of them can see past the cutoff
//!
//! Every window is a trailing range of absolute wall-minute bar keys ending at
//! the cutoff bar `k = cutoff_ms / 60_000 - 1`, which is complete at the cutoff.
//! Two columns are anchored on a past event instead, and both are clipped:
//!
//! * `spread_widen_ratio_at_extreme` — the widest spread in the seconds
//!   `[touch - 120, touch + 120]`, **intersected with everything strictly
//!   before the cutoff**. The nominal window is symmetric; the causal one is
//!   only as long as the tape has actually run. Divided by the session median
//!   spread, taken from a histogram quantized to 1e-3 dollars (exact for a
//!   1-cent price grid, where every spread is a whole number of buckets).
//! * `aggr_imb_post_extreme_5m` — bars `[E+1, min(E+5, k)]` where `E` is the bar
//!   the current extreme was set in. It is ABSENT (not zero) when the extreme
//!   was set in the cutoff bar itself and there is no "after" yet.
//!   `aggr_imb_pre_extreme_5m` is the disjoint `[E-4, E]`.
//!
//! ## Resets
//!
//! `absorbed_volume_at_extreme_15m`, `post_extreme_range_bps` and
//! `largest_print_at_extreme_shares` describe the CURRENT extreme, so a new
//! extreme resets them — absorption means volume that traded without the price
//! making progress. The reset is `O(1)`: each bar's absorbed bucket carries the
//! epoch it was written under, and a bar written under a stale epoch reads as
//! zero rather than being cleared. The counting columns (refills, depletions,
//! rejections, touches, dwell) are plain 15-minute rolling counts of events
//! that happened at the then-current extreme; they are history and are not
//! rewritten when the extreme moves.
//!
//! ## Cost
//!
//! Per quote: one midpoint, one spread, two cached slot advances (a division
//! only when the wall-minute or wall-second changes), four shared array
//! increments, and ~6 compares in each of the two side machines — `O(1)`,
//! roughly 35 operations, every touched line resident in L1 because the indices
//! only move once a second. Per print: one sign compare, three bar
//! accumulations, a 50 ms sweep window whose length is bounded by the burst,
//! and two extreme tests. Per cutoff: bounded scans of at most 15 bar slots,
//! 241 second slots, one 4,097-bin and one 4,096-bin histogram median, and a
//! median over at most 390 per-bar quote counts — `O(1)`, no term growing in
//! the ~11-14M quotes of a session.

use super::{AsOfRule, ColSpec, FamilyEmitter, FamilyRows, QuoteEvent, TradeEvent, Unit};
use crate::book::{ActionCutoff, Side};
use crate::error::{Result, SelectV2Error};

/// Registered name.
pub const NAME: &str = "b2_pivot_micro";

/// One IWM price tick in u6 dollars. Measured: the bid/ask grid is whole cents.
const TICK_U6: i64 = 10_000;
const MS_PER_BAR: i64 = 60_000;
const MS_PER_SEC: i64 = 1_000;
const WINDOW_15M: i64 = 15;
const WINDOW_5M: i64 = 5;
const WINDOW_2M: i64 = 2;
/// A defended touch is rejected when price moves this far away in time.
const REJECT_BPS: i64 = 3;
const REJECT_WINDOW_MS: i64 = 60_000;
/// Size must come back to half the pre-depletion peak inside this window.
const REFILL_WINDOW_MS: i64 = 2_000;
/// A sweep is >= 3 same-sign prints inside this window across >= 2 exchanges.
const SWEEP_WINDOW_MS: i64 = 50;
const SWEEP_MIN_PRINTS: usize = 3;
const SWEEP_MIN_EXCHANGES: usize = 2;
/// Bars after the last touch that `tick_reversal_speed_bps_per_min` measures.
const REVERSAL_BARS: i64 = 3;
/// Half-width of the spread window around the last touch, in seconds.
const SPREAD_WINDOW_SECS: i64 = 120;
/// Spread histogram resolution: 1e-3 dollars (0.1 cent) per bucket.
const SPREAD_BUCKET_U6: i64 = 1_000;
/// Buckets cover $0.000 .. $4.095; anything wider lands in the overflow bin.
const SPREAD_BUCKETS: usize = 4_096;
/// Quote-life histogram: 1 ms bins covering 0..2,046 ms plus an overflow bin.
const LIFE_BINS: usize = 2_048;
/// Ring of per-bar quote-life histograms. Only bars `k-1` and `k` are read, so
/// four blocks is two more than the contract needs.
const LIFE_RING: usize = 4;
/// Growth hints only; nothing here is a bound on the session.
const MAX_BARS: usize = 512;
const MAX_SECS: usize = 24_000;

const COLUMNS: [ColSpec; 20] = [
    ColSpec::new(
        "absorbed_volume_at_extreme_15m",
        Unit::Shares,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "refill_count_extreme_15m",
        Unit::Count,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "defense_rejections_15m",
        Unit::Count,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "spread_widen_ratio_at_extreme",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "quote_burst_ratio_2m",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new("sweep_prints_5m", Unit::Count, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new(
        "aggr_imb_pre_extreme_5m",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "aggr_imb_post_extreme_5m",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    // bps per minute; `Unit` carries no compound rate and Bps is the magnitude.
    ColSpec::new(
        "tick_reversal_speed_bps_per_min",
        Unit::Bps,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "extreme_touch_count_15m",
        Unit::Count,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "time_at_extreme_s_15m",
        Unit::Seconds,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "post_extreme_range_bps",
        Unit::Bps,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new("last_touch_age_s", Unit::Seconds, AsOfRule::StrictlyBeforeCutoff),
    // Minutes; `Unit::Seconds` is the enum's only duration kind and the column
    // name carries the scale.
    ColSpec::new(
        "extreme_price_age_min",
        Unit::Seconds,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "vol_at_extreme_share_15m",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "quote_life_ms_median_2m",
        Unit::Seconds,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new("bbo_flips_2m", Unit::Count, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new(
        "depletion_events_15m",
        Unit::Count,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "largest_print_at_extreme_shares",
        Unit::Shares,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "two_sided_activity_ratio_2m",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
];

/// Side-independent per-bar tape state.
#[derive(Clone, Copy, Debug, Default)]
struct BarStats {
    quotes: u32,
    /// Midpoint direction reversals.
    flips: u32,
    sweeps: u32,
    /// Shares of prints classified as buys / sells. Unresolved prints are in
    /// neither, by construction.
    buy_shares: i64,
    sell_shares: i64,
    /// Shares of every print with a known size, resolved or not.
    total_shares: i64,
    last_mid_u6: i64,
    seen_mid: bool,
}

/// One print inside the 50 ms sweep window.
#[derive(Clone, Copy, Debug)]
struct SweepPrint {
    ts_ms: i64,
    sign: i8,
    exchange: i64,
}

/// Everything both side machines share: one bar grid, one second grid, one
/// spread distribution, one quote-life ring, one sweep window.
#[derive(Clone, Debug, Default)]
struct Shared {
    base_key: Option<i64>,
    bars: Vec<BarStats>,
    cur_slot: usize,
    cur_bar_end_ms: i64,
    base_sec: Option<i64>,
    /// Widest spread seen in each wall-second; `i64::MIN` is ABSENT.
    secs: Vec<i64>,
    cur_sec_slot: usize,
    cur_sec_end_ms: i64,
    /// Session spread distribution, `SPREAD_BUCKETS` + 1 overflow bin.
    spread_hist: Vec<u32>,
    life_hist: Vec<u32>,
    life_key: [i64; LIFE_RING],
    prev_quote_ts_ms: Option<i64>,
    prev_bar_key: i64,
    prev_quote_slot: usize,
    prev_mid_u6: Option<i64>,
    last_dir: i8,
    last_mid_u6: Option<i64>,
    sweep_window: Vec<SweepPrint>,
}

impl Shared {
    fn new() -> Self {
        Self {
            bars: Vec::with_capacity(MAX_BARS),
            secs: Vec::with_capacity(MAX_SECS),
            spread_hist: vec![0; SPREAD_BUCKETS + 1],
            life_hist: vec![0; LIFE_RING * LIFE_BINS],
            life_key: [i64::MIN; LIFE_RING],
            sweep_window: Vec::with_capacity(16),
            ..Self::default()
        }
    }

    /// Bar slot for an event, allocating forward. The division runs once per
    /// wall-minute, not once per quote.
    fn bar_slot(&mut self, ts_ms: i64) -> usize {
        if ts_ms < self.cur_bar_end_ms && self.base_key.is_some() {
            return self.cur_slot;
        }
        let key = ts_ms.div_euclid(MS_PER_BAR);
        let base = if let Some(base) = self.base_key {
            base
        } else {
            self.base_key = Some(key);
            key
        };
        let slot = usize::try_from(key - base).unwrap_or(0);
        if slot >= self.bars.len() {
            self.bars.resize(slot + 1, BarStats::default());
        }
        self.cur_slot = slot;
        self.cur_bar_end_ms = (key + 1) * MS_PER_BAR;
        slot
    }

    /// Records the widest spread of each wall-second and the session spread
    /// distribution. A crossed market (negative spread) is real and lands in
    /// bucket 0 rather than being dropped.
    fn observe_spread(&mut self, ts_ms: i64, spread_u6: i64) {
        if ts_ms >= self.cur_sec_end_ms || self.base_sec.is_none() {
            let key = ts_ms.div_euclid(MS_PER_SEC);
            let base = if let Some(base) = self.base_sec {
                base
            } else {
                self.base_sec = Some(key);
                key
            };
            let slot = usize::try_from(key - base).unwrap_or(0);
            if slot >= self.secs.len() {
                self.secs.resize(slot + 1, i64::MIN);
            }
            self.cur_sec_slot = slot;
            self.cur_sec_end_ms = (key + 1) * MS_PER_SEC;
        }
        let cell = &mut self.secs[self.cur_sec_slot];
        *cell = (*cell).max(spread_u6);
        let bucket = usize::try_from(spread_u6.max(0) / SPREAD_BUCKET_U6)
            .unwrap_or(SPREAD_BUCKETS)
            .min(SPREAD_BUCKETS);
        self.spread_hist[bucket] += 1;
    }

    /// Records how long the previous quote stood, against the bar it stood in.
    fn observe_life(&mut self, bar_key: i64, gap_ms: i64) {
        let block = usize::try_from(bar_key.rem_euclid(
            i64::try_from(LIFE_RING).unwrap_or(1),
        ))
        .unwrap_or(0);
        if self.life_key[block] != bar_key {
            self.life_key[block] = bar_key;
            self.life_hist[block * LIFE_BINS..(block + 1) * LIFE_BINS].fill(0);
        }
        let bin = usize::try_from(gap_ms.max(0))
            .unwrap_or(LIFE_BINS - 1)
            .min(LIFE_BINS - 1);
        self.life_hist[block * LIFE_BINS + bin] += 1;
    }

    /// Buy `+1`, sell `-1`, unresolved `0` — at the midpoint, or before this
    /// session has shown a quote at all.
    fn classify(&self, price_u6: i64) -> i8 {
        match self.last_mid_u6 {
            Some(mid) if price_u6 > mid => 1,
            Some(mid) if price_u6 < mid => -1,
            _ => 0,
        }
    }

    /// Adds a resolved print to the 50 ms window and counts a sweep when the
    /// window holds >= 3 same-sign prints across >= 2 named exchanges. A
    /// detected sweep consumes its window, so one burst counts once.
    fn observe_sweep(&mut self, ts_ms: i64, slot: usize, sign: i8, exchange: i64) {
        self.sweep_window
            .retain(|print| ts_ms - print.ts_ms <= SWEEP_WINDOW_MS);
        self.sweep_window.push(SweepPrint {
            ts_ms,
            sign,
            exchange,
        });
        let mut prints = 0_usize;
        let mut exchanges: Vec<i64> = Vec::with_capacity(SWEEP_MIN_EXCHANGES + 1);
        for print in &self.sweep_window {
            if print.sign != sign {
                continue;
            }
            prints += 1;
            // A null venue (`i64::MIN` from the reader) is ABSENT and cannot
            // stand for a distinct exchange.
            if print.exchange != i64::MIN && !exchanges.contains(&print.exchange) {
                exchanges.push(print.exchange);
            }
        }
        if prints >= SWEEP_MIN_PRINTS && exchanges.len() >= SWEEP_MIN_EXCHANGES {
            self.bars[slot].sweeps += 1;
            self.sweep_window.clear();
        }
    }

    fn bar_at(&self, key: i64) -> Option<BarStats> {
        let base = self.base_key?;
        let slot = usize::try_from(key - base).ok()?;
        self.bars.get(slot).copied()
    }

    /// The last midpoint recorded at or before `key`, walking back over bars
    /// that carried no quote. Bounded by the session's allocated bar count.
    fn last_mid_at_or_before(&self, key: i64) -> Option<i64> {
        let base = self.base_key?;
        let mut probe = key;
        while probe >= base {
            if let Some(bar) = self.bar_at(probe)
                && bar.seen_mid
            {
                return Some(bar.last_mid_u6);
            }
            probe -= 1;
        }
        None
    }

    /// Session median spread in u6, from the quantized histogram. The reported
    /// value is the bucket's lower edge, which is exact whenever spreads sit on
    /// the 1-cent grid. `None` when no spread has been observed.
    fn median_spread_u6(&self) -> Option<i64> {
        let total: u64 = self.spread_hist.iter().map(|count| u64::from(*count)).sum();
        if total == 0 {
            return None;
        }
        let target = total / 2;
        let mut seen = 0_u64;
        for (bucket, count) in self.spread_hist.iter().enumerate() {
            seen += u64::from(*count);
            if seen > target {
                return Some(i64::try_from(bucket).unwrap_or(0) * SPREAD_BUCKET_U6);
            }
        }
        None
    }

    /// Median quote life over bars `[k-1, k]`, in milliseconds. `None` when the
    /// window held no quote, or when the median lands in the overflow bin — a
    /// median past 2,046 ms is reported ABSENT rather than clamped to a number
    /// the histogram cannot actually resolve.
    fn median_quote_life_ms(&self, cutoff_key: i64) -> Option<f64> {
        let ring = i64::try_from(LIFE_RING).unwrap_or(1);
        let mut merged = [0_u32; LIFE_BINS];
        let mut total = 0_u64;
        for key in (cutoff_key - WINDOW_2M + 1)..=cutoff_key {
            let block = usize::try_from(key.rem_euclid(ring)).unwrap_or(0);
            if self.life_key[block] != key {
                continue;
            }
            for (bin, count) in self.life_hist[block * LIFE_BINS..(block + 1) * LIFE_BINS]
                .iter()
                .enumerate()
            {
                merged[bin] += *count;
                total += u64::from(*count);
            }
        }
        if total == 0 {
            return None;
        }
        let target = total / 2;
        let mut seen = 0_u64;
        for (bin, count) in merged.iter().enumerate() {
            seen += u64::from(*count);
            if seen > target {
                if bin == LIFE_BINS - 1 {
                    return None;
                }
                // `bin` is below 2,048, so the u32 image is exact.
                return Some(f64::from(u32::try_from(bin).unwrap_or(u32::MAX)));
            }
        }
        None
    }
}

/// Per-bar state of one side machine.
#[derive(Clone, Copy, Debug, Default)]
struct SideBar {
    /// Epoch the absorbed shares were written under. A bar carrying a stale
    /// epoch reads as zero, which is how a new extreme resets absorption in
    /// `O(1)`.
    absorbed_epoch: u32,
    absorbed_shares: i64,
    touch_episodes: u32,
    dwell_ms: i64,
    at_extreme_shares: i64,
    refills: u32,
    depletions: u32,
    rejections: u32,
}

/// One NBBO update as the side machines consume it: both sides of the book,
/// the shared bar coordinates, and where the previous quote stood.
#[derive(Clone, Copy, Debug)]
struct SideQuote {
    ts_ms: i64,
    bar_key: i64,
    slot: usize,
    mid_u6: i64,
    high_px_u6: i64,
    high_shares: i64,
    low_px_u6: i64,
    low_shares: i64,
    /// `(instant, bar slot)` of the previous QUOTE, for dwell accounting.
    previous: Option<(i64, usize)>,
}

/// One side's extreme, and everything that happened at it.
#[derive(Clone, Debug)]
struct SideMachine {
    is_high: bool,
    bars: Vec<SideBar>,
    extreme_u6: Option<i64>,
    extreme_set_ms: i64,
    extreme_set_key: i64,
    /// Bumped on every new extreme; `0` means no extreme has formed yet, which
    /// no `SideBar::absorbed_epoch` default can collide with.
    epoch: u32,
    since_max_u6: i64,
    since_min_u6: i64,
    largest_print_shares: i64,
    in_touch: bool,
    last_touch_ms: Option<i64>,
    last_touch_mid_u6: i64,
    last_touch_key: i64,
    /// An armed touch awaiting a rejection, or its 60 s expiry.
    pending_touch_ms: Option<i64>,
    /// Largest displayed size seen at the extreme on the defended side since
    /// the level was established or last refilled.
    level_peak_shares: i64,
    /// `(instant, pre-depletion peak)` of a depletion awaiting its refill.
    pending_depletion: Option<(i64, i64)>,
}

impl SideMachine {
    fn new(side: Side) -> Self {
        Self {
            is_high: matches!(side, Side::High),
            bars: Vec::with_capacity(MAX_BARS),
            extreme_u6: None,
            extreme_set_ms: 0,
            extreme_set_key: 0,
            epoch: 0,
            since_max_u6: 0,
            since_min_u6: 0,
            largest_print_shares: 0,
            in_touch: false,
            last_touch_ms: None,
            last_touch_mid_u6: 0,
            last_touch_key: 0,
            pending_touch_ms: None,
            level_peak_shares: 0,
            pending_depletion: None,
        }
    }

    fn bar_mut(&mut self, slot: usize) -> &mut SideBar {
        if slot >= self.bars.len() {
            self.bars.resize(slot + 1, SideBar::default());
        }
        &mut self.bars[slot]
    }

    fn bar_at(&self, base: i64, key: i64) -> Option<SideBar> {
        let slot = usize::try_from(key - base).ok()?;
        self.bars.get(slot).copied()
    }

    /// True when a price sits within one tick of the current extreme.
    fn at_extreme(&self, price_u6: i64) -> bool {
        self.extreme_u6
            .is_some_and(|extreme| (price_u6 - extreme).abs() <= TICK_U6)
    }

    /// Whether this midpoint has rejected the extreme by at least 3bps in the
    /// direction that defends it.
    fn rejected(&self, mid_u6: i64) -> bool {
        let Some(extreme) = self.extreme_u6 else {
            return false;
        };
        let margin = extreme.abs() * REJECT_BPS / 10_000;
        if self.is_high {
            mid_u6 <= extreme - margin
        } else {
            mid_u6 >= extreme + margin
        }
    }

    /// A quote, as both side machines see it.
    fn on_quote(&mut self, quote: &SideQuote) {
        let SideQuote {
            ts_ms,
            bar_key,
            slot,
            mid_u6,
            high_px_u6,
            high_shares,
            low_px_u6,
            low_shares,
            previous,
        } = *quote;
        // The DEFENDED side of the book: the ask at a high, the bid at a low.
        let (book_px_u6, book_shares) = if self.is_high {
            (high_px_u6, high_shares)
        } else {
            (low_px_u6, low_shares)
        };
        // Dwell is charged to the bar the PREVIOUS quote stood in, for the time
        // it stood there, and only while that quote was at the extreme.
        if self.in_touch
            && let Some((prev_ts, prev_slot)) = previous
        {
            self.bar_mut(prev_slot).dwell_ms += ts_ms - prev_ts;
        }

        let is_new_extreme = match self.extreme_u6 {
            None => true,
            Some(extreme) => {
                if self.is_high {
                    mid_u6 > extreme
                } else {
                    mid_u6 < extreme
                }
            }
        };
        if is_new_extreme {
            self.extreme_u6 = Some(mid_u6);
            self.extreme_set_ms = ts_ms;
            self.extreme_set_key = bar_key;
            self.epoch += 1;
            self.since_max_u6 = mid_u6;
            self.since_min_u6 = mid_u6;
            self.largest_print_shares = 0;
            // A new level: the old level's peak, pending depletion and armed
            // touch all described a price that no longer exists.
            self.level_peak_shares = 0;
            self.pending_depletion = None;
            self.pending_touch_ms = None;
            self.in_touch = false;
        }
        self.since_max_u6 = self.since_max_u6.max(mid_u6);
        self.since_min_u6 = self.since_min_u6.min(mid_u6);

        if self.at_extreme(mid_u6) {
            if !self.in_touch {
                self.in_touch = true;
                self.bar_mut(slot).touch_episodes += 1;
            }
            self.last_touch_ms = Some(ts_ms);
            self.last_touch_mid_u6 = mid_u6;
            self.last_touch_key = bar_key;
            // Re-arm on every touch: an episode is defended from its last
            // touch, not its first.
            self.pending_touch_ms = Some(ts_ms);
        } else {
            self.in_touch = false;
            if let Some(armed) = self.pending_touch_ms {
                if ts_ms - armed > REJECT_WINDOW_MS {
                    self.pending_touch_ms = None;
                } else if self.rejected(mid_u6) {
                    self.bar_mut(slot).rejections += 1;
                    self.pending_touch_ms = None;
                }
            }
        }

        // Refill / depletion on the defended side of the book.
        if self.at_extreme(book_px_u6) {
            let shares = book_shares.max(0);
            if let Some((depleted_at, peak)) = self.pending_depletion {
                if ts_ms - depleted_at > REFILL_WINDOW_MS {
                    self.pending_depletion = None;
                    self.level_peak_shares = shares;
                } else if shares * 2 >= peak {
                    self.bar_mut(slot).refills += 1;
                    self.pending_depletion = None;
                    self.level_peak_shares = shares;
                }
            } else if self.level_peak_shares > 0 && shares * 2 <= self.level_peak_shares {
                self.bar_mut(slot).depletions += 1;
                self.pending_depletion = Some((ts_ms, self.level_peak_shares));
            } else {
                self.level_peak_shares = self.level_peak_shares.max(shares);
            }
        } else {
            // The defended price left the extreme; nothing about the old level
            // is still being observed.
            self.level_peak_shares = 0;
            self.pending_depletion = None;
        }
    }

    /// A print. Only prints at the extreme touch this machine.
    fn on_trade(&mut self, slot: usize, price_u6: i64, shares: i64, shares_known: bool) {
        if !shares_known || !self.at_extreme(price_u6) {
            return;
        }
        let epoch = self.epoch;
        let bar = self.bar_mut(slot);
        if bar.absorbed_epoch == epoch {
            bar.absorbed_shares += shares;
        } else {
            bar.absorbed_epoch = epoch;
            bar.absorbed_shares = shares;
        }
        bar.at_extreme_shares += shares;
        self.largest_print_shares = self.largest_print_shares.max(shares);
    }
}

/// The 20-column pivot-microstructure emitter.
#[derive(Clone, Debug)]
pub struct B2PivotMicro {
    shared: Shared,
    high: SideMachine,
    low: SideMachine,
    /// Reused across cutoffs so the per-bar quote-count median allocates once.
    scratch: Vec<u32>,
    rows: Vec<f32>,
}

impl Default for B2PivotMicro {
    fn default() -> Self {
        Self {
            shared: Shared::new(),
            high: SideMachine::new(Side::High),
            low: SideMachine::new(Side::Low),
            scratch: Vec::with_capacity(MAX_BARS),
            rows: Vec::new(),
        }
    }
}

impl FamilyEmitter for B2PivotMicro {
    fn name(&self) -> &'static str {
        NAME
    }

    fn columns(&self) -> &[ColSpec] {
        &COLUMNS
    }

    fn on_quote(&mut self, quote: &QuoteEvent) {
        let ts_ms = quote.ts_ms_b;
        let mid = quote.mid_u6();
        let spread = quote.spread_u6();
        // The PREVIOUS QUOTE's slot, which a print between the two quotes may
        // already have advanced `cur_slot` past — so it is tracked separately.
        let previous = self
            .shared
            .prev_quote_ts_ms
            .map(|prev_ts| (prev_ts, self.shared.prev_quote_slot));
        let prev_bar_key = self.shared.prev_bar_key;
        let prev_ts = self.shared.prev_quote_ts_ms;

        let slot = self.shared.bar_slot(ts_ms);
        let bar_key = self.shared.base_key.unwrap_or(0) + i64::try_from(slot).unwrap_or(0);
        {
            let bar = &mut self.shared.bars[slot];
            bar.quotes += 1;
            bar.last_mid_u6 = mid;
            bar.seen_mid = true;
        }
        self.shared.observe_spread(ts_ms, spread);
        if let Some(prev_ts) = prev_ts {
            self.shared.observe_life(prev_bar_key, ts_ms - prev_ts);
        }
        // A flip is a reversal of the midpoint's direction of travel, not every
        // price change: flat quotes carry no direction and cannot flip one.
        if let Some(prev_mid) = self.shared.prev_mid_u6 {
            let direction = match mid.cmp(&prev_mid) {
                std::cmp::Ordering::Greater => 1_i8,
                std::cmp::Ordering::Less => -1_i8,
                std::cmp::Ordering::Equal => 0,
            };
            if direction != 0 {
                if self.shared.last_dir != 0 && direction != self.shared.last_dir {
                    self.shared.bars[slot].flips += 1;
                }
                self.shared.last_dir = direction;
            }
        }
        self.shared.prev_mid_u6 = Some(mid);
        self.shared.last_mid_u6 = Some(mid);
        self.shared.prev_quote_ts_ms = Some(ts_ms);
        self.shared.prev_bar_key = bar_key;
        self.shared.prev_quote_slot = slot;

        // The ask defends a high; the bid defends a low. Each machine picks
        // its own side out of the same event.
        let event = SideQuote {
            ts_ms,
            bar_key,
            slot,
            mid_u6: mid,
            high_px_u6: quote.ask_u6,
            high_shares: quote.ask_shares,
            low_px_u6: quote.bid_u6,
            low_shares: quote.bid_shares,
            previous,
        };
        self.high.on_quote(&event);
        self.low.on_quote(&event);
    }

    fn on_trade(&mut self, trade: &TradeEvent) {
        let slot = self.shared.bar_slot(trade.ts_ms_b);
        let sign = self.shared.classify(trade.price_u6);
        // The reader encodes a null size as `i64::MIN`. Absent is not zero: an
        // unsized print joins no total and no imbalance.
        let shares_known = trade.size >= 0;
        let shares = if shares_known { trade.size } else { 0 };
        if shares_known {
            let bar = &mut self.shared.bars[slot];
            bar.total_shares += shares;
            match sign {
                1 => bar.buy_shares += shares,
                -1 => bar.sell_shares += shares,
                _ => {}
            }
        }
        if sign != 0 {
            self.shared
                .observe_sweep(trade.ts_ms_b, slot, sign, trade.exchange);
        }
        self.high
            .on_trade(slot, trade.price_u6, shares, shares_known);
        self.low.on_trade(slot, trade.price_u6, shares, shares_known);
    }

    #[allow(clippy::too_many_lines)]
    fn on_cutoff(&mut self, cutoff: &ActionCutoff) {
        let cutoff_ms = cutoff.cutoff_ns_b.div_euclid(1_000_000);
        let cutoff_key = cutoff_ms.div_euclid(MS_PER_BAR) - 1;
        let machine = match cutoff.side {
            Side::High => &self.high,
            Side::Low => &self.low,
        };
        let base = self.shared.base_key;
        let mid_now = self.shared.last_mid_u6;

        // -- side windows ---------------------------------------------------
        let mut absorbed = 0_i64;
        let mut refills = 0_u32;
        let mut depletions = 0_u32;
        let mut rejections = 0_u32;
        let mut touches = 0_u32;
        let mut dwell_ms = 0_i64;
        let mut at_extreme_shares = 0_i64;
        if let Some(base) = base {
            for key in (cutoff_key - WINDOW_15M + 1)..=cutoff_key {
                let Some(bar) = machine.bar_at(base, key) else {
                    continue;
                };
                if bar.absorbed_epoch == machine.epoch && machine.epoch != 0 {
                    absorbed += bar.absorbed_shares;
                }
                refills += bar.refills;
                depletions += bar.depletions;
                rejections += bar.rejections;
                touches += bar.touch_episodes;
                dwell_ms += bar.dwell_ms;
                at_extreme_shares += bar.at_extreme_shares;
            }
        }

        // -- shared windows -------------------------------------------------
        let mut total_shares_15m = 0_i64;
        for key in (cutoff_key - WINDOW_15M + 1)..=cutoff_key {
            if let Some(bar) = self.shared.bar_at(key) {
                total_shares_15m += bar.total_shares;
            }
        }
        let mut sweeps = 0_u32;
        for key in (cutoff_key - WINDOW_5M + 1)..=cutoff_key {
            if let Some(bar) = self.shared.bar_at(key) {
                sweeps += bar.sweeps;
            }
        }
        let mut quotes_2m = 0_u64;
        let mut flips_2m = 0_u32;
        let mut buy_2m = 0_i64;
        let mut sell_2m = 0_i64;
        for key in (cutoff_key - WINDOW_2M + 1)..=cutoff_key {
            if let Some(bar) = self.shared.bar_at(key) {
                quotes_2m += u64::from(bar.quotes);
                flips_2m += bar.flips;
                buy_2m += bar.buy_shares;
                sell_2m += bar.sell_shares;
            }
        }

        // Session median per-bar quote count, over the bars actually observed.
        self.scratch.clear();
        if let Some(base) = base {
            for (slot, bar) in self.shared.bars.iter().enumerate() {
                let key = base + i64::try_from(slot).unwrap_or(0);
                if key <= cutoff_key {
                    self.scratch.push(bar.quotes);
                }
            }
        }
        let median_quotes = median_u32(&mut self.scratch);

        // -- the two anchored windows ---------------------------------------
        let spread_ratio = spread_widen_ratio(&self.shared, machine, cutoff_ms);
        let pre_imbalance = imbalance_over(
            &self.shared,
            machine.extreme_u6.map(|_| machine.extreme_set_key),
            -(WINDOW_5M - 1),
            0,
            cutoff_key,
        );
        let post_imbalance = imbalance_over(
            &self.shared,
            machine.extreme_u6.map(|_| machine.extreme_set_key),
            1,
            WINDOW_5M,
            cutoff_key,
        );

        // -- reversal speed after the last touch ----------------------------
        let reversal_speed = machine.last_touch_ms.and_then(|_| {
            let end = (machine.last_touch_key + REVERSAL_BARS).min(cutoff_key);
            let elapsed = end - machine.last_touch_key;
            if elapsed <= 0 || machine.last_touch_mid_u6 <= 0 {
                return None;
            }
            let after = self.shared.last_mid_at_or_before(end)?;
            // Positive means the tape moved AWAY from the extreme, i.e. the
            // touch was rejected; negative means it pressed further into it.
            let moved = if machine.is_high {
                machine.last_touch_mid_u6 - after
            } else {
                after - machine.last_touch_mid_u6
            };
            Some(as_f64(moved) / as_f64(machine.last_touch_mid_u6) * 10_000.0 / as_f64(elapsed))
        });

        let values = [
            finite(as_f64(absorbed)),
            finite(f64::from(refills)),
            finite(f64::from(rejections)),
            spread_ratio.map_or(f32::NAN, finite),
            match median_quotes {
                Some(median) if median > 0.0 => {
                    finite(as_f64_u64(quotes_2m) / as_f64(WINDOW_2M) / median)
                }
                _ => f32::NAN,
            },
            finite(f64::from(sweeps)),
            pre_imbalance.map_or(f32::NAN, finite),
            post_imbalance.map_or(f32::NAN, finite),
            reversal_speed.map_or(f32::NAN, finite),
            finite(f64::from(touches)),
            finite(as_f64(dwell_ms) / 1_000.0),
            match (machine.extreme_u6, mid_now) {
                (Some(_), Some(mid)) if mid > 0 => finite(
                    as_f64(machine.since_max_u6 - machine.since_min_u6) / as_f64(mid) * 10_000.0,
                ),
                _ => f32::NAN,
            },
            machine
                .last_touch_ms
                .map_or(f32::NAN, |touch| finite(as_f64(cutoff_ms - touch) / 1_000.0)),
            machine.extreme_u6.map_or(f32::NAN, |_| {
                finite(as_f64(cutoff_ms - machine.extreme_set_ms) / 60_000.0)
            }),
            if total_shares_15m > 0 {
                finite(as_f64(at_extreme_shares) / as_f64(total_shares_15m))
            } else {
                f32::NAN
            },
            self.shared
                .median_quote_life_ms(cutoff_key)
                .map_or(f32::NAN, finite),
            finite(f64::from(flips_2m)),
            finite(f64::from(depletions)),
            machine
                .extreme_u6
                .map_or(f32::NAN, |_| finite(as_f64(machine.largest_print_shares))),
            {
                let (low, high) = (buy_2m.min(sell_2m), buy_2m.max(sell_2m));
                if high > 0 {
                    finite(as_f64(low) / as_f64(high))
                } else {
                    f32::NAN
                }
            },
        ];
        self.rows.extend_from_slice(&values);
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

/// Widest spread within +/- 120 s of the last touch, clipped to the tape that
/// exists strictly before the cutoff, over the session median spread.
fn spread_widen_ratio(shared: &Shared, machine: &SideMachine, cutoff_ms: i64) -> Option<f64> {
    let touch_ms = machine.last_touch_ms?;
    let base_sec = shared.base_sec?;
    let median = shared.median_spread_u6()?;
    if median <= 0 {
        return None;
    }
    let touch_sec = touch_ms.div_euclid(MS_PER_SEC);
    // The cutoff instant itself is excluded, so the last readable wall-second
    // is the one before it.
    let last_sec = cutoff_ms.div_euclid(MS_PER_SEC) - 1;
    let first = touch_sec - SPREAD_WINDOW_SECS;
    let last = (touch_sec + SPREAD_WINDOW_SECS).min(last_sec);
    let mut widest = i64::MIN;
    for sec in first..=last {
        let Ok(slot) = usize::try_from(sec - base_sec) else {
            continue;
        };
        if let Some(observed) = shared.secs.get(slot)
            && *observed != i64::MIN
        {
            widest = widest.max(*observed);
        }
    }
    if widest == i64::MIN {
        return None;
    }
    Some(as_f64(widest) / as_f64(median))
}

/// Aggressor imbalance over bars `[anchor + from, anchor + to]`, clipped at the
/// cutoff bar. `None` when there is no anchor, no window left after clipping,
/// or no resolved shares in it — all three are ABSENT, not zero.
fn imbalance_over(
    shared: &Shared,
    anchor: Option<i64>,
    from: i64,
    to: i64,
    cutoff_key: i64,
) -> Option<f64> {
    let anchor = anchor?;
    let first = anchor + from;
    let last = (anchor + to).min(cutoff_key);
    if first > last {
        return None;
    }
    let mut buys = 0_i64;
    let mut sells = 0_i64;
    for key in first..=last {
        if let Some(bar) = shared.bar_at(key) {
            buys += bar.buy_shares;
            sells += bar.sell_shares;
        }
    }
    let total = buys + sells;
    if total <= 0 {
        return None;
    }
    Some(as_f64(buys - sells) / as_f64(total))
}

/// Median of a scratch buffer, destroying its order. For an even count this is
/// the upper of the two middles — a stated convention, not a rounding.
fn median_u32(values: &mut [u32]) -> Option<f64> {
    if values.is_empty() {
        return None;
    }
    let middle = values.len() / 2;
    let (_, median, _) = values.select_nth_unstable(middle);
    Some(f64::from(*median))
}

/// The one narrowing site, and the structural guard that no `+/-inf` can leave
/// this family.
#[allow(clippy::cast_possible_truncation)]
fn finite(value: f64) -> f32 {
    if value.is_finite() {
        value as f32
    } else {
        f32::NAN
    }
}

/// u6 magnitudes are ~2e8 and share counts are ~1e7; both are exact in `f64`.
#[allow(clippy::cast_precision_loss)]
const fn as_f64(value: i64) -> f64 {
    value as f64
}

#[allow(clippy::cast_precision_loss)]
const fn as_f64_u64(value: u64) -> f64 {
    value as f64
}

#[cfg(test)]
mod tests {
    use super::{B2PivotMicro, COLUMNS, NAME};
    use crate::book::{ActSetSummary, ActionCutoff, Side};
    use crate::calendar;
    use crate::families::{FamilyEmitter, QuoteEvent, TradeEvent};

    const DAY: &str = "2022-03-01";
    const BID: i64 = 200_000_000;
    const ASK: i64 = 200_020_000;
    /// The midpoint of `BID`/`ASK`, and therefore the session extreme in every
    /// tape below that opens with that quote.
    const MID: i64 = 200_010_000;

    fn cutoff(bar_ordinal: i32, side: Side) -> ActionCutoff {
        let scope = calendar::admit(DAY).expect("registered session");
        let ordinal = i64::from(bar_ordinal);
        ActionCutoff {
            action_id: format!("{DAY}-{bar_ordinal}-{side:?}"),
            day: scope.day(),
            session_ordinal: u32::try_from(scope.session_ordinal()).expect("in range"),
            cutoff_bar_ordinal: bar_ordinal,
            side,
            cutoff_ns_a: scope.cutoff_ns_a(ordinal).expect("in range"),
            cutoff_ns_b: scope.cutoff_ns_b(ordinal).expect("in range"),
            first_visibility_ns: 0,
            last_visibility_ns: 0,
            act_set: ActSetSummary::default(),
        }
    }

    fn quote(offset_ms: i64, bid_u6: i64, ask_u6: i64, ask_shares: i64) -> QuoteEvent {
        let scope = calendar::admit(DAY).expect("registered session");
        QuoteEvent {
            ts_ms_b: scope.open_ms_b() + offset_ms,
            bid_u6,
            ask_u6,
            bid_shares: 1_000,
            ask_shares,
        }
    }

    fn print(offset_ms: i64, price_u6: i64, size: i64, exchange: i64) -> TradeEvent {
        let scope = calendar::admit(DAY).expect("registered session");
        TradeEvent {
            ts_ms_b: scope.open_ms_b() + offset_ms,
            price_u6,
            size,
            exchange,
            condition: 0,
            sequence: 0,
            bid_u6: BID,
            ask_u6: ASK,
            bid_shares: 1_000,
            ask_shares: 1_000,
            quote_present: true,
        }
    }

    /// Runs a tape and returns the single emitted row.
    fn run(
        quotes: &[QuoteEvent],
        prints: &[TradeEvent],
        bar_ordinal: i32,
        side: Side,
    ) -> Vec<f32> {
        let mut family = B2PivotMicro::default();
        // Feed in tape order, quotes first on a tie, exactly as the driver does.
        let mut q = 0;
        let mut p = 0;
        while q < quotes.len() || p < prints.len() {
            let take_quote = match (quotes.get(q), prints.get(p)) {
                (Some(quote), Some(print)) => quote.ts_ms_b <= print.ts_ms_b,
                (Some(_), None) => true,
                _ => false,
            };
            if take_quote {
                family.on_quote(&quotes[q]);
                q += 1;
            } else {
                family.on_trade(&prints[p]);
                p += 1;
            }
        }
        let action = cutoff(bar_ordinal, side);
        family.on_cutoff(&action);
        let rows = family
            .emit(std::slice::from_ref(&action))
            .expect("one row for one cutoff");
        assert_eq!(rows.columns, COLUMNS.len());
        rows.values
    }

    fn near(got: f32, want: f32, what: &str) {
        assert!((got - want).abs() < 1e-3, "{what}: got {got}, want {want}");
    }

    #[test]
    fn the_family_declares_its_twenty_columns_in_order() {
        let family = B2PivotMicro::default();
        assert_eq!(family.name(), NAME);
        let names: Vec<&str> = family.columns().iter().map(|spec| spec.name).collect();
        assert_eq!(
            names,
            vec![
                "absorbed_volume_at_extreme_15m",
                "refill_count_extreme_15m",
                "defense_rejections_15m",
                "spread_widen_ratio_at_extreme",
                "quote_burst_ratio_2m",
                "sweep_prints_5m",
                "aggr_imb_pre_extreme_5m",
                "aggr_imb_post_extreme_5m",
                "tick_reversal_speed_bps_per_min",
                "extreme_touch_count_15m",
                "time_at_extreme_s_15m",
                "post_extreme_range_bps",
                "last_touch_age_s",
                "extreme_price_age_min",
                "vol_at_extreme_share_15m",
                "quote_life_ms_median_2m",
                "bbo_flips_2m",
                "depletion_events_15m",
                "largest_print_at_extreme_shares",
                "two_sided_activity_ratio_2m",
            ]
        );
        assert_eq!(names.len(), 20);
    }

    /// The refill machine, hand-walked on the HIGH side (which watches the ASK).
    ///
    /// ```text
    /// t=0     ask 1,000 shares  -> level peak 1,000
    /// t=1000  ask   400 shares  -> 400*2 <= 1,000, a depletion
    /// t=2000  ask   600 shares  -> 600*2 >= 1,000 inside 2 s, a refill
    /// ```
    #[test]
    fn a_half_depletion_restored_inside_two_seconds_is_one_refill() {
        let values = run(
            &[
                quote(0, BID, ASK, 1_000),
                quote(1_000, BID, ASK, 400),
                quote(2_000, BID, ASK, 600),
            ],
            &[],
            2,
            Side::High,
        );
        near(values[1], 1.0, "refill_count_extreme_15m");
        near(values[17], 1.0, "depletion_events_15m");
        // One unbroken touch run at the extreme.
        near(values[9], 1.0, "extreme_touch_count_15m");
        // Two 1-second gaps while the midpoint sat at the extreme.
        near(values[10], 2.0, "time_at_extreme_s_15m");
        // The cutoff closes bar 2 at open + 120 s; the last touch was at 2 s.
        near(values[12], 118.0, "last_touch_age_s");
        near(values[13], 2.0, "extreme_price_age_min");
        // The midpoint never moved off the extreme.
        near(values[11], 0.0, "post_extreme_range_bps");
        near(values[16], 0.0, "bbo_flips_2m");
        // A constant 2-cent spread: the widest in the window IS the median.
        near(values[3], 1.0, "spread_widen_ratio_at_extreme");
        // Both inter-quote gaps are 1,000 ms.
        near(values[15], 1_000.0, "quote_life_ms_median_2m");
        // Bar 1 saw 3 quotes and is the only observed bar, so the median is 3;
        // bars 1 and 2 hold 3 quotes between them, i.e. 1.5 a bar.
        near(values[4], 0.5, "quote_burst_ratio_2m");
        // No prints at all: observed zero at the extreme, absent as a share.
        near(values[0], 0.0, "absorbed_volume_at_extreme_15m");
        near(values[18], 0.0, "largest_print_at_extreme_shares");
        assert!(values[14].is_nan(), "vol_at_extreme_share_15m without prints");
        assert!(values[6].is_nan(), "aggr_imb_pre_extreme_5m without prints");
        assert!(
            values.iter().all(|value| !value.is_infinite()),
            "no column may be +/-inf: {values:?}"
        );
    }

    /// The same depletion, restored three seconds later — outside the two
    /// second window, so it is NOT a refill. This is the test that was written
    /// asserting a nonzero refill first, watched fail, and then corrected.
    #[test]
    fn a_restore_after_the_two_second_window_is_not_a_refill() {
        let values = run(
            &[
                quote(0, BID, ASK, 1_000),
                quote(1_000, BID, ASK, 400),
                quote(4_000, BID, ASK, 900),
            ],
            &[],
            2,
            Side::High,
        );
        near(values[1], 0.0, "refill_count_extreme_15m");
        // The depletion itself still happened, and is still counted.
        near(values[17], 1.0, "depletion_events_15m");
    }

    /// A touch, a 3bps rejection inside 60 s, then a second touch.
    #[test]
    fn a_touch_rejected_by_three_bps_is_one_defense_and_two_episodes() {
        // 3bps of 200_010_000 is 60_003 u6; the second quote drops the midpoint
        // 100_000 u6, well past it.
        let values = run(
            &[
                quote(0, BID, ASK, 1_000),
                quote(1_000, BID - 100_000, ASK - 100_000, 1_000),
                quote(2_000, BID, ASK, 1_000),
            ],
            &[],
            2,
            Side::High,
        );
        near(values[2], 1.0, "defense_rejections_15m");
        near(values[9], 2.0, "extreme_touch_count_15m");
        // Down then up: one direction reversal.
        near(values[16], 1.0, "bbo_flips_2m");
        // The midpoint ranged 100_000 u6 under a 200_010_000 midpoint.
        near(values[11], 4.999_75, "post_extreme_range_bps");
    }

    /// Three same-sign prints inside 50 ms across three venues: one sweep, and
    /// every share of it absorbed at the extreme.
    #[test]
    fn three_same_sign_prints_across_venues_inside_fifty_ms_are_one_sweep() {
        let values = run(
            &[quote(0, BID, ASK, 1_000)],
            &[
                print(10, ASK, 100, 1),
                print(11, ASK, 100, 2),
                print(12, ASK, 100, 3),
            ],
            2,
            Side::High,
        );
        near(values[5], 1.0, "sweep_prints_5m");
        // ASK is 10_000 u6 above the extreme: exactly one tick, so at it.
        near(values[0], 300.0, "absorbed_volume_at_extreme_15m");
        near(values[18], 100.0, "largest_print_at_extreme_shares");
        near(values[14], 1.0, "vol_at_extreme_share_15m");
        // Every resolved share was a buy.
        near(values[6], 1.0, "aggr_imb_pre_extreme_5m");
        // Nothing traded after the extreme bar, so the other side is absent.
        assert!(values[7].is_nan(), "aggr_imb_post_extreme_5m");
        near(values[19], 0.0, "two_sided_activity_ratio_2m");
    }

    /// A print exactly at the midpoint is unresolved and must not be folded
    /// into either side of the imbalance — while still counting as volume.
    #[test]
    fn an_at_midpoint_print_is_unresolved_and_never_folded() {
        let values = run(
            &[quote(0, BID, ASK, 1_000)],
            &[print(10, MID, 500, 1)],
            2,
            Side::High,
        );
        assert!(
            values[6].is_nan(),
            "an unresolved print cannot make an imbalance, got {}",
            values[6]
        );
        assert!(values[19].is_nan(), "two_sided_activity_ratio_2m");
        // It is still volume, and it still traded at the extreme.
        near(values[14], 1.0, "vol_at_extreme_share_15m");
        near(values[0], 500.0, "absorbed_volume_at_extreme_15m");
        near(values[5], 0.0, "sweep_prints_5m");
    }

    /// A new extreme resets absorption, the largest print and the post-extreme
    /// range — they describe the CURRENT extreme, not the session.
    #[test]
    fn a_new_extreme_resets_the_current_level_accumulators() {
        let values = run(
            &[
                quote(0, BID, ASK, 1_000),
                // 200_000 u6 higher: a new HIGH, twenty ticks up.
                quote(1_000, BID + 200_000, ASK + 200_000, 1_000),
            ],
            &[print(10, ASK, 700, 1)],
            2,
            Side::High,
        );
        near(values[0], 0.0, "absorbed_volume_at_extreme_15m after a new high");
        near(values[18], 0.0, "largest_print_at_extreme_shares after a new high");
        // The 700-share print is still session volume, but none of it sits at
        // the new extreme.
        // The share of volume that printed at the THEN-current extreme is
        // history and is not rewritten when the extreme moves; only the
        // current-level accumulators above reset.
        near(values[14], 1.0, "vol_at_extreme_share_15m");
        near(values[11], 0.0, "post_extreme_range_bps");
    }

    /// The LOW machine watches the BID and mirrors the HIGH machine exactly.
    #[test]
    fn the_low_machine_mirrors_the_high_machine_on_the_bid() {
        let mut family = B2PivotMicro::default();
        family.on_quote(&QuoteEvent {
            bid_shares: 1_000,
            ..quote(0, BID, ASK, 1_000)
        });
        family.on_quote(&QuoteEvent {
            bid_shares: 400,
            ..quote(1_000, BID, ASK, 1_000)
        });
        family.on_quote(&QuoteEvent {
            bid_shares: 600,
            ..quote(2_000, BID, ASK, 1_000)
        });
        let action = cutoff(2, Side::Low);
        family.on_cutoff(&action);
        let values = family
            .emit(std::slice::from_ref(&action))
            .expect("emit")
            .values;
        near(values[1], 1.0, "refill_count_extreme_15m on the LOW side");
        near(values[17], 1.0, "depletion_events_15m on the LOW side");
    }

    /// Absence is not zero: with no tape, every derived ratio is `NaN` and
    /// nothing is an infinity.
    #[test]
    fn an_empty_tape_is_absent_not_zero() {
        let values = run(&[], &[], 30, Side::High);
        assert_eq!(values.len(), COLUMNS.len());
        for (index, value) in values.iter().enumerate() {
            assert!(!value.is_infinite(), "column {index} is infinite");
        }
        assert!(values[3].is_nan(), "spread_widen_ratio_at_extreme");
        assert!(values[4].is_nan(), "quote_burst_ratio_2m");
        assert!(values[6].is_nan(), "aggr_imb_pre_extreme_5m");
        assert!(values[11].is_nan(), "post_extreme_range_bps");
        assert!(values[12].is_nan(), "last_touch_age_s");
        assert!(values[13].is_nan(), "extreme_price_age_min");
        assert!(values[14].is_nan(), "vol_at_extreme_share_15m");
        assert!(values[15].is_nan(), "quote_life_ms_median_2m");
        assert!(values[18].is_nan(), "largest_print_at_extreme_shares");
        // Counts over an empty window are observed zeros.
        near(values[1], 0.0, "refill_count_extreme_15m");
        near(values[5], 0.0, "sweep_prints_5m");
        near(values[16], 0.0, "bbo_flips_2m");
    }

    /// A print whose size the vendor did not carry is absent, not a zero-share
    /// print: it joins no total and no imbalance.
    #[test]
    fn a_null_sized_print_is_absent_from_every_total() {
        let values = run(
            &[quote(0, BID, ASK, 1_000)],
            &[TradeEvent {
                size: i64::MIN,
                ..print(10, ASK, 0, 1)
            }],
            2,
            Side::High,
        );
        near(values[0], 0.0, "absorbed_volume_at_extreme_15m");
        assert!(values[14].is_nan(), "vol_at_extreme_share_15m");
        assert!(values[6].is_nan(), "aggr_imb_pre_extreme_5m");
    }

    #[test]
    fn emit_refuses_a_row_count_that_disagrees_with_the_cutoff_list() {
        let mut family = B2PivotMicro::default();
        let action = cutoff(1, Side::High);
        family.on_cutoff(&action);
        let refusal = family
            .emit(&[action.clone(), action])
            .expect_err("one row against two cutoffs must refuse");
        assert!(matches!(
            refusal,
            crate::error::SelectV2Error::ContentMismatch { .. }
        ));
    }
}
