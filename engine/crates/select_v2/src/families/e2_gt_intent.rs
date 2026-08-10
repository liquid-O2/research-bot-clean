//! `e2_gt_intent` — game-theoretic intent, hard-signed only.
//!
//! Distilled from the G1/G3/G4/G5 rulings (feature book, "GAME-THEORETIC
//! PARTICIPANT-STRUCTURE RULINGS G1-G7"). The refused vocabulary is refused
//! here too, structurally rather than by review:
//!
//! * **No PIN, no "informed probability".** Latent participant types are not
//!   identified by anything in this corpus. Every column below is a measured
//!   flow or quote statistic with a descriptive name.
//! * **"Precedence", never "leader".** [`precedence_1ms`](COLUMNS) counts how
//!   often a same-direction NBBO move was already on the tape before a hard
//!   print. It says nothing about who moved first in any causal sense.
//! * **Kyle-lambda is descriptive.** A per-class ordinary least squares slope
//!   of one-minute mid returns on same-minute signed volume, no standard
//!   errors claimed, no structural interpretation attached.
//!
//! ## The two falsifiers that shaped the code (G5)
//!
//! G5 requires a same-timestamp falsifier because *the quote channel can
//! mechanically lead its own print*. The driver delivers a quote before a print
//! stamped at the same millisecond, so a naive "was there a move just before
//! this print" would score the print's own book update as precedence. Both
//! [`precedence_1ms`](COLUMNS) and [`preprint_fade_1ms`](COLUMNS) therefore read
//! only quotes with a **strictly earlier millisecond** than the print. The
//! 1 ms bin then spans exactly the quotes stamped at `t - 1`, and the
//! same-millisecond channel artefact cannot enter any lag bin.
//!
//! ## Windows
//!
//! Cutoffs are exact minute boundaries (see `e1_tape_flow`), so every trailing
//! window here is an exact count of complete minute buckets. The Kyle
//! regression reads at most 30 one-minute points plus the mid that opened the
//! first of them — 31 minutes, inside the 64-slot ring.
//!
//! ## Cost
//!
//! Per quote: one spread-histogram nudge with an incremental median pointer,
//! two monotone-max pushes, four monotone lag cursors, one time-integral step.
//! All `O(1)` amortized — no per-quote window scan anywhere, which is what
//! keeps 11-14M quotes affordable. Per cutoff: at most 30 buckets per window
//! and four 30-point regressions.

// Numeric module: every cast below is bounded by construction (ring index,
// histogram bin, share count, f64->f32 narrowing) and each site says why.
#![allow(
    clippy::cast_precision_loss,
    clippy::cast_possible_truncation,
    clippy::cast_possible_wrap,
    clippy::cast_sign_loss,
    clippy::struct_field_names
)]

use super::e1_tape_flow::{
    BAR_MS, Ring, Sign, SizeQuantiles, SweepDetector, aggressor_sign, cutoff_ms, minute_of, narrow,
    ratio,
};
use super::{AsOfRule, ColSpec, FamilyEmitter, FamilyRows, QuoteEvent, TradeEvent, Unit};
use crate::book::ActionCutoff;
use crate::error::{Result, SelectV2Error};
use std::collections::VecDeque;

/// Registered name.
pub const NAME: &str = "e2_gt_intent";

/// One quote tick, in u6. IWM quotes on the one-cent Reg NMS Rule 612 minimum
/// increment for quotations at or above $1.00. Named once so a future
/// sub-penny quoting regime is a one-line change with one place to re-measure.
pub const TICK_U6: i64 = 10_000;

/// Lag bins, milliseconds. Fixed by G4/G5 ("{1,10,100}ms" grid; no new grids).
pub const LAGS_MS: [i64; 3] = [1, 10, 100];

/// Fraction of displayed size that must disappear to count as a fade.
pub const FADE_DECLINE: f64 = 0.25;

/// Minutes of one-minute points in the Kyle regression window.
pub const KYLE_MINUTES: i64 = 30;

/// Minutes in the imbalance-autocorrelation window (the column name carries a
/// `_5m` suffix from the plan; the estimator window is the 15 minutes the
/// specification's parenthetical names — see the module report).
pub const PERSISTENCE_MINUTES: i64 = 15;

/// Hard ceiling on `effort_vs_result_15m`, so a zero net move is a large
/// number rather than an infinity.
pub const EFFORT_CAP: f64 = 1e4;

/// Duration histogram: 8 bins per octave from 1 ms, so 128 bins reach 65.5 s.
/// Bin resolution is 2^(1/8) = 9.05%, which is the stated precision of every
/// median this family reports.
pub const DUR_BINS: usize = 128;
const DUR_PER_OCTAVE: f64 = 8.0;

/// Spread histogram, in ticks. 64 bins covers every spread IWM shows in RTH;
/// anything wider saturates the last bin and is reported as such.
const SPREAD_BINS: usize = 64;

/// Run-length histogram: exact 1..=63, with 64-and-longer in the last bin.
const RUN_BINS: usize = 64;

/// Bars either side of a session extreme that count as "at the extreme".
const EXTREME_BPS: f64 = 5.0;

/// Bin index of a duration in milliseconds. Shared with `e3_raid_sonar` so
/// both families report medians on one scale.
#[must_use]
pub fn duration_bin(ms: f64) -> usize {
    if ms.is_nan() || ms <= 0.0 {
        return 0;
    }
    let bin = (ms.log2() * DUR_PER_OCTAVE).floor();
    if bin <= 0.0 {
        0
    } else if bin >= (DUR_BINS - 1) as f64 {
        DUR_BINS - 1
    } else {
        bin as usize
    }
}

/// Geometric centre of a duration bin, in milliseconds.
#[must_use]
pub fn duration_value(bin: usize) -> f64 {
    (2.0_f64).powf((bin as f64 + 0.5) / DUR_PER_OCTAVE)
}

/// Median of a histogram, or `None` when it is empty.
#[must_use]
pub fn histogram_median(counts: &[u64], value: impl Fn(usize) -> f64) -> Option<f64> {
    let total: u64 = counts.iter().sum();
    if total == 0 {
        return None;
    }
    let target = total.div_ceil(2);
    let mut seen = 0_u64;
    for (bin, count) in counts.iter().enumerate() {
        seen += *count;
        if seen >= target {
            return Some(value(bin));
        }
    }
    None
}

// ---------------------------------------------------------------------------
// Incremental 15-minute spread median
// ---------------------------------------------------------------------------

/// The trailing-15-minute median quoted spread, in ticks, maintained with an
/// incremental pointer so it is exact after **every** quote rather than
/// recomputed on a schedule.
///
/// A per-quote 64-bin scan would be 900M operations a session; a once-a-minute
/// recomputation would be a different quantity from the one specified. The
/// pointer walk is `O(1)` amortized and gives the same value a full scan would.
#[derive(Clone, Debug)]
struct RollingSpread {
    minutes: VecDeque<(i64, [u32; SPREAD_BINS])>,
    aggregate: [u32; SPREAD_BINS],
    total: u64,
    pointer: usize,
    below: u64,
    /// The minute the back of `minutes` holds, so the common case — another
    /// quote in the minute we are already in — never probes the deque.
    current_minute: i64,
}

impl RollingSpread {
    const WINDOW: i64 = 15;

    const fn new() -> Self {
        Self {
            minutes: VecDeque::new(),
            aggregate: [0; SPREAD_BINS],
            total: 0,
            pointer: 0,
            below: 0,
            current_minute: i64::MIN,
        }
    }

    /// The median spread in ticks over the retained window, or `None` while
    /// nothing has been observed.
    const fn median_ticks(&self) -> Option<usize> {
        if self.total == 0 {
            None
        } else {
            Some(self.pointer)
        }
    }

    fn roll_to(&mut self, minute: i64) {
        while self
            .minutes
            .front()
            .is_some_and(|(front, _)| *front <= minute - Self::WINDOW)
        {
            if let Some((_, counts)) = self.minutes.pop_front() {
                for (bin, count) in counts.iter().enumerate() {
                    self.aggregate[bin] -= *count;
                    self.total -= u64::from(*count);
                    if bin < self.pointer {
                        self.below -= u64::from(*count);
                    }
                }
            }
        }
        if self.minutes.back().is_none_or(|(back, _)| *back != minute) {
            self.minutes.push_back((minute, [0; SPREAD_BINS]));
        }
        self.rebalance();
    }

    fn observe(&mut self, minute: i64, bin: usize) {
        if minute != self.current_minute {
            self.roll_to(minute);
            self.current_minute = minute;
        }
        if let Some((_, counts)) = self.minutes.back_mut() {
            counts[bin] += 1;
        }
        self.aggregate[bin] += 1;
        self.total += 1;
        if bin < self.pointer {
            self.below += 1;
        }
        self.rebalance();
    }

    fn rebalance(&mut self) {
        if self.total == 0 {
            self.pointer = 0;
            self.below = 0;
            return;
        }
        let target = self.total.div_ceil(2);
        while self.below + u64::from(self.aggregate[self.pointer]) < target
            && self.pointer + 1 < SPREAD_BINS
        {
            self.below += u64::from(self.aggregate[self.pointer]);
            self.pointer += 1;
        }
        while self.pointer > 0 && self.below >= target {
            self.pointer -= 1;
            self.below -= u64::from(self.aggregate[self.pointer]);
        }
    }
}

// ---------------------------------------------------------------------------
// Recent-quote ring with monotone lag cursors
// ---------------------------------------------------------------------------

/// One retained NBBO snapshot.
///
/// Prices and sizes are `i32`, not `i64`: this struct is written once per quote
/// on a ~17M-quote stream, so its width is memory bandwidth. A u6 price of a
/// $200 ETF is 2e8 and a displayed size is thousands — both an order inside
/// `i32`. A value that does not fit becomes 0, which fails [`Self::usable`] and
/// is therefore read as an unrepresentable book rather than a wrong number.
#[derive(Clone, Copy, Debug)]
struct QuoteSnap {
    ts_ms: i64,
    bid_u6: i32,
    ask_u6: i32,
    bid_shares: i32,
    ask_shares: i32,
}

impl QuoteSnap {
    fn new(ts_ms: i64, bid_u6: i64, ask_u6: i64, bid_shares: i64, ask_shares: i64) -> Self {
        Self {
            ts_ms,
            bid_u6: i32::try_from(bid_u6).unwrap_or(0),
            ask_u6: i32::try_from(ask_u6).unwrap_or(0),
            bid_shares: i32::try_from(bid_shares.max(0)).unwrap_or(i32::MAX),
            ask_shares: i32::try_from(ask_shares.max(0)).unwrap_or(i32::MAX),
        }
    }

    fn mid_u6(&self) -> i64 {
        i64::midpoint(i64::from(self.bid_u6), i64::from(self.ask_u6))
    }

    const fn usable(&self) -> bool {
        self.bid_u6 > 0 && self.ask_u6 > 0 && self.ask_u6 >= self.bid_u6
    }

    fn side(&self, ask_side: bool) -> (i64, i64) {
        if ask_side {
            (i64::from(self.ask_u6), i64::from(self.ask_shares))
        } else {
            (i64::from(self.bid_u6), i64::from(self.bid_shares))
        }
    }
}

/// What one print needs to know about the NBBO just before it.
#[derive(Clone, Copy, Debug, Default)]
struct Probe {
    /// The NBBO prevailing strictly before the print's own millisecond.
    prevailing: Option<QuoteSnap>,
    /// Mid strictly before `now - LAGS_MS[lag]`, absent when the snapshot at
    /// that boundary carried no usable book.
    lagged_mid: [Option<i64>; 3],
    lagged_seen: [bool; 3],
    /// Peak displayed size at the prevailing best price, per lag bin.
    same_price_max: [Option<i64>; 3],
}

/// The last ~100 ms of NBBO snapshots — everything any lag bin can reach.
///
/// **The quote path only writes; all the reading happens on the print path.**
/// An earlier version advanced four monotone lag cursors on every quote, which
/// measured as the single largest cost in this family (0.338 s of 0.470 s per
/// session) — 17M quotes of bookkeeping to serve 355k prints. Prints are 2% of
/// the events, so [`Self::probe`] answers all four questions in one backward
/// walk over the retained window at the moment a print actually asks. Same
/// values, ~50x fewer visits.
#[derive(Clone, Debug)]
struct RecentQuotes {
    /// Power-of-two circular buffer: an absolute index resolves with one mask.
    slots: Vec<QuoteSnap>,
    mask: i64,
    base: i64,
    next: i64,
}

impl RecentQuotes {
    /// Initial capacity. The retained window is the longest lag bin, 100 ms,
    /// which held ~73 quotes on the measured session; 1,024 leaves an order of
    /// burst headroom before the buffer has to grow.
    const INITIAL: usize = 1_024;
    /// The longest lag bin, and therefore the retention horizon.
    const RETAIN_MS: i64 = 100;

    const fn new() -> Self {
        Self {
            slots: Vec::new(),
            mask: 0,
            base: 0,
            next: 0,
        }
    }

    fn at(&self, absolute: i64) -> Option<&QuoteSnap> {
        if absolute < self.base || absolute >= self.next {
            return None;
        }
        self.slots.get((absolute & self.mask) as usize)
    }

    fn push(&mut self, snap: QuoteSnap) {
        if self.slots.is_empty() {
            self.slots.resize(Self::INITIAL, snap);
            self.mask = Self::INITIAL as i64 - 1;
        }
        // Grow rather than drop: silently evicting the oldest snapshot would
        // shorten the 100 ms lag bin without saying so.
        if self.next - self.base >= self.slots.len() as i64 {
            let retained: Vec<QuoteSnap> = (self.base..self.next)
                .filter_map(|index| self.at(index).copied())
                .collect();
            let capacity = self.slots.len() * 2;
            self.slots.resize(capacity, snap);
            self.mask = capacity as i64 - 1;
            for (offset, item) in retained.into_iter().enumerate() {
                let slot = ((self.base + offset as i64) & self.mask) as usize;
                self.slots[slot] = item;
            }
        }
        let slot = (self.next & self.mask) as usize;
        self.slots[slot] = snap;
        self.next += 1;

        // Keep every snapshot inside the horizon, plus the ONE before it — that
        // is the book prevailing when the longest window opened, which
        // `lagged_mid[2]` needs.
        let horizon = snap.ts_ms - Self::RETAIN_MS;
        while self.next - self.base > 1
            && self
                .at(self.base + 1)
                .is_some_and(|older| older.ts_ms < horizon)
        {
            self.base += 1;
        }
    }

    /// One backward walk answering everything a print asks of the quote stream.
    ///
    /// Snapshots stamped at `now_ms` itself are skipped before anything is
    /// recorded — the G5 same-timestamp falsifier, applied once, here, so no
    /// lag bin can be contaminated by the print's own book update.
    fn probe(&self, now_ms: i64, ask_side: bool) -> Probe {
        let mut out = Probe::default();
        let mut price = i64::MIN;
        let mut index = self.next - 1;
        while index >= self.base {
            let Some(snap) = self.at(index).copied() else {
                break;
            };
            index -= 1;
            if snap.ts_ms >= now_ms {
                continue;
            }
            if out.prevailing.is_none() {
                out.prevailing = Some(snap);
                if snap.usable() {
                    price = snap.side(ask_side).0;
                }
            }
            let mut oldest_bin_closed = false;
            for (lag, window_ms) in LAGS_MS.iter().enumerate() {
                if snap.ts_ms < now_ms - *window_ms {
                    // Outside this bin: the latest such snapshot is the one the
                    // bin measures the move from.
                    if !out.lagged_seen[lag] {
                        out.lagged_seen[lag] = true;
                        if snap.usable() {
                            out.lagged_mid[lag] = Some(snap.mid_u6());
                        }
                    }
                    if lag + 1 == LAGS_MS.len() {
                        oldest_bin_closed = true;
                    }
                } else if price != i64::MIN && snap.usable() {
                    let (snap_price, shares) = snap.side(ask_side);
                    if snap_price == price {
                        out.same_price_max[lag] =
                            Some(out.same_price_max[lag].map_or(shares, |peak: i64| peak.max(shares)));
                    }
                }
            }
            // Nothing older than the longest bin can contribute to any answer.
            if oldest_bin_closed {
                break;
            }
        }
        out
    }
}

// ---------------------------------------------------------------------------
// Columns
// ---------------------------------------------------------------------------

const COLUMNS: [ColSpec; 28] = [
    ColSpec::new("kyle_lambda_q1", Unit::Bps, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("kyle_lambda_q2", Unit::Bps, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("kyle_lambda_q3", Unit::Bps, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("kyle_lambda_q4", Unit::Bps, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("arrival_buy_rate_5m", Unit::Count, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("arrival_sell_rate_5m", Unit::Count, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new(
        "arrival_unresolved_rate_5m",
        Unit::Count,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new("arrival_asym_lo", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("arrival_asym_hi", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("cvd_hard_lo", Unit::Shares, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("cvd_hard_hi", Unit::Shares, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("precedence_1ms", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("precedence_10ms", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("precedence_100ms", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new(
        "display_exec_gap_bid_15m",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "display_exec_gap_ask_15m",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new("preprint_fade_1ms", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("preprint_fade_10ms", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("preprint_fade_100ms", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new(
        "patience_at_extremes_ratio",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "quote_to_trade_ratio_5m",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "resiliency_halflife_s_15m",
        Unit::Seconds,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "imbalance_persistence_5m",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new("effort_vs_result_15m", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new(
        "aggression_runlength_med_15m",
        Unit::Count,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new("two_sided_sweep_flag_5m", Unit::Flag, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new(
        "lambda_ratio_q4_over_q1",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "unresolved_volume_share_15m",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
];

/// One minute of intent accumulators.
#[derive(Clone, Debug)]
struct Bucket {
    // Hot fields first: `quotes`, the two displayed-size integrals and
    // `mid_close_u6` are touched on every one of ~17M quotes, so they are kept
    // contiguous rather than scattered across the ~2 KB the histograms make
    // this struct.
    quotes: u32,
    mid_close_u6: i64,
    /// Time integral of displayed size, in share-seconds.
    bid_share_seconds: f64,
    ask_share_seconds: f64,
    signed_volume: i64,
    total_volume: i64,
    unresolved_volume: i64,
    /// Hard sell shares (into the bid) and hard buy shares (into the ask).
    exec_into_bid: i64,
    exec_into_ask: i64,
    buy_prints: u32,
    sell_prints: u32,
    unresolved_prints: u32,
    fade_obs: u32,
    buy_sweeps: u32,
    sell_sweeps: u32,
    /// Signed hard volume per session-so-far size quartile — the Kyle regressor.
    class_signed_volume: [i64; 4],
    precedence_buy_hits: [u32; 3],
    precedence_buy_obs: [u32; 3],
    precedence_sell_hits: [u32; 3],
    precedence_sell_obs: [u32; 3],
    fade_hits: [u32; 3],
    patience_extreme: [u32; DUR_BINS],
    patience_other: [u32; DUR_BINS],
    resiliency: [u32; DUR_BINS],
    runs: [u32; RUN_BINS],
}

impl Default for Bucket {
    fn default() -> Self {
        Self {
            class_signed_volume: [0; 4],
            buy_prints: 0,
            sell_prints: 0,
            unresolved_prints: 0,
            signed_volume: 0,
            total_volume: 0,
            unresolved_volume: 0,
            quotes: 0,
            exec_into_bid: 0,
            exec_into_ask: 0,
            bid_share_seconds: 0.0,
            ask_share_seconds: 0.0,
            precedence_buy_hits: [0; 3],
            precedence_buy_obs: [0; 3],
            precedence_sell_hits: [0; 3],
            precedence_sell_obs: [0; 3],
            fade_hits: [0; 3],
            fade_obs: 0,
            mid_close_u6: i64::MIN,
            patience_extreme: [0; DUR_BINS],
            patience_other: [0; DUR_BINS],
            resiliency: [0; DUR_BINS],
            runs: [0; RUN_BINS],
            buy_sweeps: 0,
            sell_sweeps: 0,
        }
    }
}

/// One side's best-quote episode.
#[derive(Clone, Copy, Debug)]
struct Episode {
    price_u6: i64,
    since_ms: i64,
}

impl Episode {
    const fn new() -> Self {
        Self {
            price_u6: i64::MIN,
            since_ms: 0,
        }
    }
}

/// Game-theoretic intent columns for one session.
#[derive(Clone, Debug)]
pub struct GtIntent {
    ring: Ring<Bucket>,
    sizes: SizeQuantiles,
    sweeps: SweepDetector,
    recent: RecentQuotes,
    spread: RollingSpread,

    // Time-integral state.
    last_quote_ms: i64,
    last_bid_shares: i64,
    last_ask_shares: i64,

    // Best-quote episodes and session extremes.
    bid_episode: Episode,
    ask_episode: Episode,
    session_high_u6: i64,
    session_low_u6: i64,

    // Resiliency episode.
    widened_since_ms: i64,
    widened_reference: usize,
    last_spread_ticks: i64,

    // Aggression runs.
    run_sign: Sign,
    run_length: u32,

    // Session-so-far scalars.
    cvd_hard: i64,
    unresolved_volume: i64,

    rows: Vec<f32>,
}

impl Default for GtIntent {
    fn default() -> Self {
        Self::new()
    }
}

/// Value-namespace constructor for `families::build`; see the note on
/// `e1_tape_flow::E1TapeFlow`. `mod.rs` is another lane's file.
#[allow(non_upper_case_globals)]
pub const E2GtIntent: GtIntent = GtIntent::new();

impl GtIntent {
    /// A fresh emitter for one session.
    #[must_use]
    pub const fn new() -> Self {
        Self {
            ring: Ring::new(),
            sizes: SizeQuantiles::new(),
            sweeps: SweepDetector::new(),
            recent: RecentQuotes::new(),
            spread: RollingSpread::new(),
            last_quote_ms: i64::MIN,
            last_bid_shares: 0,
            last_ask_shares: 0,
            bid_episode: Episode::new(),
            ask_episode: Episode::new(),
            session_high_u6: i64::MIN,
            session_low_u6: i64::MAX,
            widened_since_ms: i64::MIN,
            widened_reference: 0,
            last_spread_ticks: -1,
            run_sign: Sign::Unresolved,
            run_length: 0,
            cvd_hard: 0,
            unresolved_volume: 0,
            rows: Vec::new(),
        }
    }

    /// Credits displayed size to the minutes it was actually displayed in,
    /// splitting at every minute boundary between the last quote and `to_ms`.
    fn integrate_display(&mut self, to_ms: i64) {
        if self.last_quote_ms == i64::MIN || to_ms <= self.last_quote_ms {
            return;
        }
        let mut from = self.last_quote_ms;
        while from < to_ms {
            let minute = minute_of(from);
            let boundary = (minute + 1) * BAR_MS;
            let end = boundary.min(to_ms);
            let seconds = (end - from) as f64 / 1_000.0;
            let bid = self.last_bid_shares as f64;
            let ask = self.last_ask_shares as f64;
            if let Some(bucket) = self.ring.slot_mut(minute) {
                bucket.bid_share_seconds += seconds * bid;
                bucket.ask_share_seconds += seconds * ask;
            }
            from = end;
        }
        self.last_quote_ms = to_ms;
    }

    /// Closes one side's best-quote episode and files its lifetime against the
    /// session extremes as they stood when it ended.
    fn close_episode(&mut self, episode: Episode, ts_ms: i64) {
        if episode.price_u6 == i64::MIN {
            return;
        }
        let lifetime = (ts_ms - episode.since_ms) as f64;
        if lifetime <= 0.0 {
            return;
        }
        let price = episode.price_u6 as f64;
        let tolerance = price * EXTREME_BPS / 10_000.0;
        let near_high = self.session_high_u6 != i64::MIN
            && (price - self.session_high_u6 as f64).abs() <= tolerance;
        let near_low = self.session_low_u6 != i64::MAX
            && (price - self.session_low_u6 as f64).abs() <= tolerance;
        let bin = duration_bin(lifetime);
        let minute = minute_of(ts_ms);
        if let Some(bucket) = self.ring.slot_mut(minute) {
            if near_high || near_low {
                bucket.patience_extreme[bin] += 1;
            } else {
                bucket.patience_other[bin] += 1;
            }
        }
    }

    fn close_run(&mut self, ts_ms: i64) {
        if self.run_length == 0 {
            return;
        }
        let bin = (self.run_length.min(RUN_BINS as u32) - 1) as usize;
        let minute = minute_of(ts_ms);
        if let Some(bucket) = self.ring.slot_mut(minute) {
            bucket.runs[bin] += 1;
        }
        self.run_length = 0;
        self.run_sign = Sign::Unresolved;
    }
}

/// One trailing window's folded totals.
#[derive(Clone, Copy, Debug, Default)]
struct Window {
    buy_prints: u64,
    sell_prints: u64,
    unresolved_prints: u64,
    total_volume: i64,
    unresolved_volume: i64,
    quotes: u64,
    exec_into_bid: i64,
    exec_into_ask: i64,
    bid_share_seconds: f64,
    ask_share_seconds: f64,
    precedence_buy_hits: [u64; 3],
    precedence_buy_obs: [u64; 3],
    precedence_sell_hits: [u64; 3],
    precedence_sell_obs: [u64; 3],
    fade_hits: [u64; 3],
    fade_obs: u64,
    buy_sweeps: u64,
    sell_sweeps: u64,
}

impl Window {
    fn absorb(mut self, bucket: &Bucket) -> Self {
        self.buy_prints += u64::from(bucket.buy_prints);
        self.sell_prints += u64::from(bucket.sell_prints);
        self.unresolved_prints += u64::from(bucket.unresolved_prints);
        self.total_volume += bucket.total_volume;
        self.unresolved_volume += bucket.unresolved_volume;
        self.quotes += u64::from(bucket.quotes);
        self.exec_into_bid += bucket.exec_into_bid;
        self.exec_into_ask += bucket.exec_into_ask;
        self.bid_share_seconds += bucket.bid_share_seconds;
        self.ask_share_seconds += bucket.ask_share_seconds;
        for lag in 0..3 {
            self.precedence_buy_hits[lag] += u64::from(bucket.precedence_buy_hits[lag]);
            self.precedence_buy_obs[lag] += u64::from(bucket.precedence_buy_obs[lag]);
            self.precedence_sell_hits[lag] += u64::from(bucket.precedence_sell_hits[lag]);
            self.precedence_sell_obs[lag] += u64::from(bucket.precedence_sell_obs[lag]);
            self.fade_hits[lag] += u64::from(bucket.fade_hits[lag]);
        }
        self.fade_obs += u64::from(bucket.fade_obs);
        self.buy_sweeps += u64::from(bucket.buy_sweeps);
        self.sell_sweeps += u64::from(bucket.sell_sweeps);
        self
    }
}

/// Simple OLS slope of `y` on `x` from summed moments. Descriptive only: no
/// standard error is claimed and none is emitted (G1).
///
/// Returns `None` for fewer than two points or a degenerate regressor.
#[must_use]
pub fn ols_slope(count: u64, sum_x: f64, sum_y: f64, sum_cross: f64, sum_square: f64) -> Option<f64> {
    if count < 2 {
        return None;
    }
    let n = count as f64;
    let denominator = n * sum_square - sum_x * sum_x;
    if denominator == 0.0 || !denominator.is_finite() {
        return None;
    }
    let slope = (n * sum_cross - sum_x * sum_y) / denominator;
    slope.is_finite().then_some(slope)
}

/// Two-proportion z of a buy-versus-sell count asymmetry. Descriptive.
fn asymmetry_z(buy_hits: u64, buy_obs: u64, sell_hits: u64, sell_obs: u64) -> f32 {
    if buy_obs == 0 || sell_obs == 0 {
        return f32::NAN;
    }
    let p_buy = buy_hits as f64 / buy_obs as f64;
    let p_sell = sell_hits as f64 / sell_obs as f64;
    let pooled = (buy_hits + sell_hits) as f64 / (buy_obs + sell_obs) as f64;
    let variance = pooled * (1.0 - pooled) * (1.0 / buy_obs as f64 + 1.0 / sell_obs as f64);
    if variance <= 0.0 {
        return f32::NAN;
    }
    narrow((p_buy - p_sell) / variance.sqrt())
}

impl GtIntent {
    fn window(&self, end_minute: i64, minutes: i64) -> Window {
        self.ring
            .fold_window(end_minute, minutes, Window::default(), Window::absorb)
    }

    fn mid_close(&self, minute: i64) -> Option<f64> {
        self.ring
            .get(minute)
            .filter(|bucket| bucket.mid_close_u6 != i64::MIN)
            .map(|bucket| bucket.mid_close_u6 as f64)
    }

    /// One-minute mid return in bps, or `None` when either endpoint is absent.
    fn minute_return_bps(&self, minute: i64) -> Option<f64> {
        let close = self.mid_close(minute)?;
        let open = self.mid_close(minute - 1)?;
        (open > 0.0).then(|| (close - open) / open * 10_000.0)
    }

    fn kyle_lambda(&self, end_minute: i64, class: usize) -> Option<f64> {
        let (mut count, mut sx, mut sy, mut sxy, mut sxx) = (0_u64, 0.0, 0.0, 0.0, 0.0);
        let mut offset = 0_i64;
        while offset < KYLE_MINUTES {
            let minute = end_minute - offset;
            offset += 1;
            let Some(bucket) = self.ring.get(minute) else {
                continue;
            };
            let Some(y) = self.minute_return_bps(minute) else {
                continue;
            };
            let x = bucket.class_signed_volume[class] as f64;
            count += 1;
            sx += x;
            sy += y;
            sxy += x * y;
            sxx += x * x;
        }
        ols_slope(count, sx, sy, sxy, sxx)
    }

    fn duration_median(
        &self,
        end_minute: i64,
        minutes: i64,
        pick: impl Fn(&Bucket) -> &[u32; DUR_BINS],
    ) -> Option<f64> {
        let mut counts = [0_u64; DUR_BINS];
        let mut offset = 0_i64;
        while offset < minutes {
            if let Some(bucket) = self.ring.get(end_minute - offset) {
                for (bin, count) in pick(bucket).iter().enumerate() {
                    counts[bin] += u64::from(*count);
                }
            }
            offset += 1;
        }
        histogram_median(&counts, duration_value)
    }
}

impl FamilyEmitter for GtIntent {
    fn name(&self) -> &'static str {
        NAME
    }

    fn columns(&self) -> &[ColSpec] {
        &COLUMNS
    }

    fn on_quote(&mut self, quote: &QuoteEvent) {
        let ts = quote.ts_ms_b;
        // Close the displayed-size integral at this quote before its own sizes
        // take effect, so each interval is credited to the size that was
        // actually displayed during it.
        self.integrate_display(ts);

        let usable = quote.bid_u6 > 0 && quote.ask_u6 > 0 && quote.ask_u6 >= quote.bid_u6;
        let minute = minute_of(ts);
        if let Some(bucket) = self.ring.slot_mut(minute) {
            bucket.quotes += 1;
            if usable {
                bucket.mid_close_u6 = i64::midpoint(quote.bid_u6, quote.ask_u6);
            }
        }

        if usable {
            let mid = i64::midpoint(quote.bid_u6, quote.ask_u6);
            self.session_high_u6 = self.session_high_u6.max(mid);
            self.session_low_u6 = self.session_low_u6.min(mid);

            if self.bid_episode.price_u6 != quote.bid_u6 {
                let closing = self.bid_episode;
                self.close_episode(closing, ts);
                self.bid_episode = Episode {
                    price_u6: quote.bid_u6,
                    since_ms: ts,
                };
            }
            if self.ask_episode.price_u6 != quote.ask_u6 {
                let closing = self.ask_episode;
                self.close_episode(closing, ts);
                self.ask_episode = Episode {
                    price_u6: quote.ask_u6,
                    since_ms: ts,
                };
            }

            // Resiliency: judge this quote against the median of the quotes
            // strictly before it, then fold it in.
            let ticks = (quote.ask_u6 - quote.bid_u6).div_euclid(TICK_U6);
            let bin = ticks.clamp(0, (SPREAD_BINS - 1) as i64) as usize;
            if let Some(median) = self.spread.median_ticks() {
                if self.widened_since_ms == i64::MIN {
                    if median >= 1 && ticks >= 2 * median as i64 && self.last_spread_ticks >= 0 {
                        self.widened_since_ms = ts;
                        self.widened_reference = median;
                    }
                } else if ticks <= self.widened_reference as i64 {
                    let recovery = (ts - self.widened_since_ms) as f64;
                    let recovery_bin = duration_bin(recovery);
                    if let Some(bucket) = self.ring.slot_mut(minute) {
                        bucket.resiliency[recovery_bin] += 1;
                    }
                    self.widened_since_ms = i64::MIN;
                }
            }
            self.spread.observe(minute, bin);
            self.last_spread_ticks = ticks;

        }

        self.recent.push(QuoteSnap::new(
            ts,
            quote.bid_u6,
            quote.ask_u6,
            quote.bid_shares,
            quote.ask_shares,
        ));
        self.last_quote_ms = ts;
        self.last_bid_shares = quote.bid_shares.max(0);
        self.last_ask_shares = quote.ask_shares.max(0);
    }

    #[allow(clippy::too_many_lines)]
    fn on_trade(&mut self, trade: &TradeEvent) {
        let ts = trade.ts_ms_b;
        let size = trade.size.max(0);
        let sign = aggressor_sign(trade);
        let class = self.sizes.quartile_class(size);
        self.sizes.insert(size);

        let hit = self.sweeps.observe(trade, sign);

        // Aggression runs: an unresolved print ends the run rather than
        // extending it, because we cannot assert the burst stayed one-sided.
        if sign.is_hard() && self.run_sign == sign && self.run_length > 0 {
            self.run_length += 1;
        } else {
            self.close_run(ts);
            if sign.is_hard() {
                self.run_sign = sign;
                self.run_length = 1;
            }
        }

        // Precedence and fade both read strictly-earlier-millisecond quotes,
        // and both come out of one backward walk over the retained window.
        let mut precedence = [false; 3];
        let mut precedence_seen = [false; 3];
        let mut fade = [false; 3];
        let mut fade_seen = false;
        if sign.is_hard() {
            // A hard buy executes into the ask; mirrored for a hard sell.
            let ask_side = sign == Sign::Buy;
            let probe = self.recent.probe(ts, ask_side);
            if let Some(now) = probe.prevailing.filter(QuoteSnap::usable) {
                for (lag, before) in probe.lagged_mid.iter().enumerate() {
                    let Some(before) = before else {
                        continue;
                    };
                    precedence_seen[lag] = true;
                    let move_u6 = now.mid_u6() - *before;
                    precedence[lag] = match sign {
                        Sign::Buy => move_u6 > 0,
                        Sign::Sell => move_u6 < 0,
                        Sign::Unresolved => false,
                    };
                }
                let (_, current) = now.side(ask_side);
                if current > 0 {
                    fade_seen = true;
                    for (lag, slot) in fade.iter_mut().enumerate() {
                        // No same-price quote inside the window means the
                        // displayed size did not change, which is an observed
                        // non-decline — not an absence.
                        let peak = probe.same_price_max[lag].unwrap_or(current).max(current);
                        *slot = (current as f64) <= (1.0 - FADE_DECLINE) * peak as f64;
                    }
                }
            }
        }

        let Some(bucket) = self.ring.slot_mut(minute_of(ts)) else {
            return;
        };
        bucket.total_volume += size;
        match sign {
            Sign::Buy => {
                bucket.buy_prints += 1;
                bucket.signed_volume += size;
                bucket.exec_into_ask += size;
            }
            Sign::Sell => {
                bucket.sell_prints += 1;
                bucket.signed_volume -= size;
                bucket.exec_into_bid += size;
            }
            Sign::Unresolved => {
                bucket.unresolved_prints += 1;
                bucket.unresolved_volume += size;
            }
        }
        if let (Some(class), true) = (class, sign.is_hard()) {
            bucket.class_signed_volume[class] += sign.as_i64() * size;
        }
        for (lag, seen) in precedence_seen.iter().enumerate() {
            if !*seen {
                continue;
            }
            match sign {
                Sign::Buy => {
                    bucket.precedence_buy_obs[lag] += 1;
                    if precedence[lag] {
                        bucket.precedence_buy_hits[lag] += 1;
                    }
                }
                Sign::Sell => {
                    bucket.precedence_sell_obs[lag] += 1;
                    if precedence[lag] {
                        bucket.precedence_sell_hits[lag] += 1;
                    }
                }
                Sign::Unresolved => {}
            }
        }
        if fade_seen {
            bucket.fade_obs += 1;
            for (lag, faded) in fade.iter().enumerate() {
                if *faded {
                    bucket.fade_hits[lag] += 1;
                }
            }
        }
        if let Some(hit) = hit.filter(|hit| hit.qualified) {
            match hit.sign {
                Sign::Buy => bucket.buy_sweeps += 1,
                Sign::Sell => bucket.sell_sweeps += 1,
                Sign::Unresolved => {}
            }
        }

        self.cvd_hard += sign.as_i64() * size;
        if !sign.is_hard() {
            self.unresolved_volume += size;
        }
    }

    #[allow(clippy::too_many_lines)]
    fn on_cutoff(&mut self, cutoff: &ActionCutoff) {
        let instant = cutoff_ms(cutoff);
        // Complete the displayed-size integral up to the cutoff so the last
        // minute in the window is whole. Nothing after the cutoff is read.
        self.integrate_display(instant);
        self.ring.advance_to(minute_of(instant));
        let end = minute_of(instant) - 1;

        let w5 = self.window(end, 5);
        let w15 = self.window(end, 15);

        let mut lambda = [f64::NAN; 4];
        for (class, slot) in lambda.iter_mut().enumerate() {
            *slot = self.kyle_lambda(end, class).unwrap_or(f64::NAN);
        }
        for value in lambda {
            self.rows.push(narrow(value));
        }

        self.rows.push(narrow(w5.buy_prints as f64 / 5.0));
        self.rows.push(narrow(w5.sell_prints as f64 / 5.0));
        self.rows.push(narrow(w5.unresolved_prints as f64 / 5.0));

        // Worst-case asymmetry interval: the unresolved arrivals are handed
        // entirely to one side and then entirely to the other. They never leave
        // the denominator (G1: unknowns stay in the immutable denominator).
        let arrivals = (w5.buy_prints + w5.sell_prints + w5.unresolved_prints) as f64;
        let net = w5.buy_prints as f64 - w5.sell_prints as f64;
        self.rows
            .push(ratio(net - w5.unresolved_prints as f64, arrivals));
        self.rows
            .push(ratio(net + w5.unresolved_prints as f64, arrivals));

        self.rows
            .push(narrow((self.cvd_hard - self.unresolved_volume) as f64));
        self.rows
            .push(narrow((self.cvd_hard + self.unresolved_volume) as f64));

        for lag in 0..LAGS_MS.len() {
            self.rows.push(asymmetry_z(
                w15.precedence_buy_hits[lag],
                w15.precedence_buy_obs[lag],
                w15.precedence_sell_hits[lag],
                w15.precedence_sell_obs[lag],
            ));
        }

        self.rows
            .push(ratio(w15.exec_into_bid as f64, w15.bid_share_seconds));
        self.rows
            .push(ratio(w15.exec_into_ask as f64, w15.ask_share_seconds));

        for lag in 0..LAGS_MS.len() {
            self.rows
                .push(ratio(w15.fade_hits[lag] as f64, w15.fade_obs as f64));
        }

        let extreme = self.duration_median(end, 30, |bucket| &bucket.patience_extreme);
        let other = self.duration_median(end, 30, |bucket| &bucket.patience_other);
        self.rows.push(match (extreme, other) {
            (Some(extreme), Some(other)) => ratio(extreme, other),
            _ => f32::NAN,
        });

        self.rows.push(ratio(
            w5.quotes as f64,
            (w5.buy_prints + w5.sell_prints + w5.unresolved_prints) as f64,
        ));

        self.rows.push(
            self.duration_median(end, 15, |bucket| &bucket.resiliency)
                .map_or(f32::NAN, |ms| narrow(ms / 1_000.0)),
        );

        // Lag-1 autocorrelation of the one-minute signed imbalance series.
        // Minutes with no prints have no imbalance and leave the series; they
        // are not zeros.
        let mut series: Vec<f64> = Vec::new();
        let mut offset = PERSISTENCE_MINUTES - 1;
        while offset >= 0 {
            let minute = end - offset;
            offset -= 1;
            let Some(bucket) = self.ring.get(minute) else {
                series.push(f64::NAN);
                continue;
            };
            if bucket.total_volume == 0 {
                series.push(f64::NAN);
            } else {
                series.push(bucket.signed_volume as f64 / bucket.total_volume as f64);
            }
        }
        self.rows.push(lag_one_autocorrelation(&series));

        // Effort: the summed magnitude of each minute's net imbalance, as a
        // share of the window's volume. Result: the window's mid move in bps.
        let mut effort = 0.0_f64;
        let mut volume = 0.0_f64;
        let mut offset = 0_i64;
        while offset < 15 {
            if let Some(bucket) = self.ring.get(end - offset) {
                effort += (bucket.signed_volume as f64).abs();
                volume += bucket.total_volume as f64;
            }
            offset += 1;
        }
        let result = match (self.mid_close(end), self.mid_close(end - 15)) {
            (Some(close), Some(open)) if open > 0.0 => Some(((close - open) / open * 1e4).abs()),
            _ => None,
        };
        self.rows.push(match result {
            _ if volume == 0.0 => f32::NAN,
            None => f32::NAN,
            Some(0.0) => narrow(EFFORT_CAP),
            Some(result) => narrow((effort / volume / result).min(EFFORT_CAP)),
        });

        let mut runs = [0_u64; RUN_BINS];
        let mut offset = 0_i64;
        while offset < 15 {
            if let Some(bucket) = self.ring.get(end - offset) {
                for (bin, count) in bucket.runs.iter().enumerate() {
                    runs[bin] += u64::from(*count);
                }
            }
            offset += 1;
        }
        self.rows.push(
            histogram_median(&runs, |bin| (bin + 1) as f64).map_or(f32::NAN, narrow),
        );

        self.rows
            .push(if w5.buy_sweeps > 0 && w5.sell_sweeps > 0 {
                1.0
            } else {
                0.0
            });

        self.rows.push(if lambda[0] == 0.0 {
            f32::NAN
        } else {
            narrow(lambda[3] / lambda[0])
        });

        self.rows
            .push(ratio(w15.unresolved_volume as f64, w15.total_volume as f64));
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

/// Lag-1 autocorrelation over a series that may carry `NaN` gaps. A pair is
/// used only when both of its points exist; the mean is over the points that
/// take part in at least one pair.
fn lag_one_autocorrelation(series: &[f64]) -> f32 {
    let mut pairs: Vec<(f64, f64)> = Vec::new();
    for window in series.windows(2) {
        if window[0].is_finite() && window[1].is_finite() {
            pairs.push((window[0], window[1]));
        }
    }
    if pairs.len() < 2 {
        return f32::NAN;
    }
    let count = (pairs.len() * 2) as f64;
    let mean = pairs.iter().map(|(a, b)| a + b).sum::<f64>() / count;
    let covariance: f64 = pairs.iter().map(|(a, b)| (a - mean) * (b - mean)).sum();
    let variance: f64 = pairs
        .iter()
        .map(|(a, b)| (a - mean).powi(2) + (b - mean).powi(2))
        .sum::<f64>()
        / 2.0;
    if variance <= 0.0 {
        return f32::NAN;
    }
    narrow(covariance / variance)
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

    fn quote_at(ts_ms: i64, bid_u6: i64, ask_u6: i64, bid_shares: i64, ask_shares: i64) -> QuoteEvent {
        QuoteEvent {
            ts_ms_b: ts_ms,
            bid_u6,
            ask_u6,
            bid_shares,
            ask_shares,
        }
    }

    fn print_at(ts_ms: i64, price_u6: i64, size: i64, bid_u6: i64, ask_u6: i64) -> TradeEvent {
        TradeEvent {
            ts_ms_b: ts_ms,
            price_u6,
            size,
            exchange: 4,
            condition: 0,
            sequence: 0,
            bid_u6,
            ask_u6,
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

    /// The Kyle accumulator against a hardcoded 20-point expectation.
    ///
    /// x = 1..=20, y = 3x + 7 with a deterministic zig-zag of +/-1 (`-1` on odd
    /// x, `+1` on even x). Every moment below was computed independently in
    /// exact rational arithmetic, not read back off this implementation:
    /// n=20, Sx=210, Sy=770, Sxy=10090, Sxx=2870, so the slope is
    /// (20*10090 - 210*770) / (20*2870 - 210^2) = 40100/13300 = 401/133.
    #[test]
    fn kyle_accumulator_matches_a_hardcoded_twenty_point_slope() {
        let (mut n, mut sx, mut sy, mut sxy, mut sxx) = (0_u64, 0.0, 0.0, 0.0, 0.0);
        for step in 1..=20_i64 {
            let x = step as f64;
            let y = 3.0 * x + 7.0 + if step % 2 == 0 { 1.0 } else { -1.0 };
            n += 1;
            sx += x;
            sy += y;
            sxy += x * y;
            sxx += x * x;
        }
        assert_eq!(n, 20);
        assert!((sx - 210.0).abs() < 1e-9);
        assert!((sy - 770.0).abs() < 1e-9);
        assert!((sxy - 10_090.0).abs() < 1e-9);
        assert!((sxx - 2_870.0).abs() < 1e-9);
        let slope = ols_slope(n, sx, sy, sxy, sxx).expect("slope");
        let expected = 401.0 / 133.0;
        assert!(
            (slope - expected).abs() < 1e-12,
            "slope {slope} != {expected}"
        );
        assert!((slope - 3.015_037_593_984_962_5).abs() < 1e-12);
        // Degenerate cases are absence, never a zero slope.
        assert!(ols_slope(1, 1.0, 1.0, 1.0, 1.0).is_none());
        assert!(ols_slope(5, 5.0, 5.0, 5.0, 5.0).is_none());
    }

    /// **Shown-to-fail anchor.** `preprint_fade` must read only the window
    /// BEFORE the print. This tape puts the whole decline AFTER it.
    #[test]
    fn preprint_fade_is_zero_when_the_decline_happens_after_the_print() {
        let (bid, ask) = (199_990_000_i64, 200_010_000_i64);
        let mut family = GtIntent::new();
        // A flat, deep ask for 100 ms before the print: no decline at all.
        for step in 0..10 {
            family.on_quote(&quote_at(1_000 + step * 10, bid, ask, 5_000, 5_000));
        }
        // The hard buy lands with the ask still at full size.
        family.on_trade(&print_at(1_101, ask, 100, bid, ask));
        // Only NOW does the ask collapse, well past the print.
        for step in 0..10 {
            family.on_quote(&quote_at(1_110 + step * 10, bid, ask, 5_000, 200));
        }
        let cutoff = cutoff_at(1);
        family.on_cutoff(&cutoff);
        let rows = family.emit(std::slice::from_ref(&cutoff)).expect("emit");
        for name in ["preprint_fade_1ms", "preprint_fade_10ms", "preprint_fade_100ms"] {
            assert_eq!(
                column(&rows, name),
                0.0,
                "{name} saw a decline that happened after the print"
            );
        }
    }

    /// The mirror of the anchor: a real pre-print decline must be found.
    #[test]
    fn preprint_fade_finds_a_decline_that_happens_before_the_print() {
        let (bid, ask) = (199_990_000_i64, 200_010_000_i64);
        let mut family = GtIntent::new();
        family.on_quote(&quote_at(1_000, bid, ask, 5_000, 5_000));
        // The ask drains to 10% of its peak, all inside the 100 ms window and
        // 1 ms before the print.
        family.on_quote(&quote_at(1_090, bid, ask, 5_000, 500));
        family.on_trade(&print_at(1_091, ask, 100, bid, ask));
        let cutoff = cutoff_at(1);
        family.on_cutoff(&cutoff);
        let rows = family.emit(std::slice::from_ref(&cutoff)).expect("emit");
        assert_eq!(column(&rows, "preprint_fade_100ms"), 1.0);
        // The 5,000-share peak is 91 ms old, so the 10 ms and 1 ms windows can
        // only see the already-drained 500. A window that never held the peak
        // reports no fade rather than inheriting the longer window's answer.
        assert_eq!(column(&rows, "preprint_fade_10ms"), 0.0);
        assert_eq!(column(&rows, "preprint_fade_1ms"), 0.0);
    }

    #[test]
    fn a_price_change_is_not_a_size_decline() {
        let (bid, ask) = (199_990_000_i64, 200_010_000_i64);
        let mut family = GtIntent::new();
        family.on_quote(&quote_at(1_000, bid, ask, 5_000, 5_000));
        // The ask MOVES UP with a small size. Same-price history is void, so
        // the 500 shares at the new price are not a decline from 5,000 at the
        // old one.
        family.on_quote(&quote_at(1_050, bid, ask + TICK_U6, 5_000, 500));
        family.on_trade(&print_at(1_060, ask + TICK_U6, 100, bid, ask + TICK_U6));
        let cutoff = cutoff_at(1);
        family.on_cutoff(&cutoff);
        let rows = family.emit(std::slice::from_ref(&cutoff)).expect("emit");
        assert_eq!(column(&rows, "preprint_fade_100ms"), 0.0);
    }

    #[test]
    fn precedence_ignores_the_prints_own_millisecond() {
        let (bid, ask) = (199_990_000_i64, 200_010_000_i64);
        let mut family = GtIntent::new();
        family.on_quote(&quote_at(1_000, bid, ask, 100, 100));
        // The book jumps up in the SAME millisecond as the print. If that
        // counted, every print would look preceded by its own quote.
        family.on_quote(&quote_at(1_100, bid + TICK_U6, ask + TICK_U6, 100, 100));
        family.on_trade(&print_at(
            1_100,
            ask + TICK_U6,
            100,
            bid + TICK_U6,
            ask + TICK_U6,
        ));
        let cutoff = cutoff_at(1);
        family.on_cutoff(&cutoff);
        let rows = family.emit(std::slice::from_ref(&cutoff)).expect("emit");
        // One buy, no sells: the two-proportion z has no comparison group.
        assert!(column(&rows, "precedence_1ms").is_nan());
    }

    #[test]
    fn display_integral_credits_each_minute_it_was_displayed_in() {
        let (bid, ask) = (199_990_000_i64, 200_010_000_i64);
        let mut family = GtIntent::new();
        // 1,000 shares on the bid from 30 s into minute 0 until 30 s into
        // minute 1: 30 s in each.
        family.on_quote(&quote_at(30_000, bid, ask, 1_000, 1_000));
        family.on_quote(&quote_at(90_000, bid, ask, 1_000, 1_000));
        let cutoff = cutoff_at(1);
        family.on_cutoff(&cutoff);
        let _ = family.emit(std::slice::from_ref(&cutoff)).expect("emit");
        // Minute 0 holds 30 s x 1,000 shares = 30,000 share-seconds.
        let minute_zero = family.ring.get(0).expect("minute 0");
        assert!(
            (minute_zero.bid_share_seconds - 30_000.0).abs() < 1e-6,
            "{}",
            minute_zero.bid_share_seconds
        );
    }

    #[test]
    fn arrival_asymmetry_brackets_the_unresolved_mass() {
        let (bid, ask) = (199_990_000_i64, 200_010_000_i64);
        let mid = i64::midpoint(bid, ask);
        let mut family = GtIntent::new();
        family.on_quote(&quote_at(100, bid, ask, 100, 100));
        family.on_trade(&print_at(1_000, ask, 100, bid, ask)); // buy
        family.on_trade(&print_at(2_000, bid, 100, bid, ask)); // sell
        family.on_trade(&print_at(3_000, mid, 100, bid, ask)); // unresolved
        family.on_trade(&print_at(4_000, mid, 100, bid, ask)); // unresolved
        let cutoff = cutoff_at(1);
        family.on_cutoff(&cutoff);
        let rows = family.emit(std::slice::from_ref(&cutoff)).expect("emit");
        // net = 0, unresolved = 2, total = 4 -> [-0.5, +0.5].
        assert!((column(&rows, "arrival_asym_lo") + 0.5).abs() < 1e-6);
        assert!((column(&rows, "arrival_asym_hi") - 0.5).abs() < 1e-6);
        assert!((column(&rows, "arrival_buy_rate_5m") - 0.2).abs() < 1e-6);
        assert!((column(&rows, "arrival_unresolved_rate_5m") - 0.4).abs() < 1e-6);
        // The hard CVD is zero but the band is 400 shares wide.
        assert!((column(&rows, "cvd_hard_lo") + 200.0).abs() < 1e-6);
        assert!((column(&rows, "cvd_hard_hi") - 200.0).abs() < 1e-6);
    }

    #[test]
    fn aggression_runs_are_broken_by_unresolved_prints() {
        let (bid, ask) = (199_990_000_i64, 200_010_000_i64);
        let mid = i64::midpoint(bid, ask);
        let mut family = GtIntent::new();
        family.on_quote(&quote_at(100, bid, ask, 100, 100));
        // Three buys, one unresolved, three buys: two runs of 3, median 3.
        for step in 0..3 {
            family.on_trade(&print_at(1_000 + step, ask, 100, bid, ask));
        }
        family.on_trade(&print_at(2_000, mid, 100, bid, ask));
        for step in 0..3 {
            family.on_trade(&print_at(3_000 + step, ask, 100, bid, ask));
        }
        // A sell closes the second run.
        family.on_trade(&print_at(4_000, bid, 100, bid, ask));
        let cutoff = cutoff_at(1);
        family.on_cutoff(&cutoff);
        let rows = family.emit(std::slice::from_ref(&cutoff)).expect("emit");
        assert!((column(&rows, "aggression_runlength_med_15m") - 3.0).abs() < 1e-6);
    }

    #[test]
    fn no_column_is_ever_infinite_on_a_thin_tape() {
        let (bid, ask) = (199_990_000_i64, 200_010_000_i64);
        let mut family = GtIntent::new();
        family.on_quote(&quote_at(100, bid, ask, 100, 100));
        family.on_trade(&print_at(1_000, ask, 100, bid, ask));
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

    #[test]
    fn rolling_spread_median_matches_a_full_scan() {
        let mut rolling = RollingSpread::new();
        let mut expected: Vec<usize> = Vec::new();
        for step in 0..200_u32 {
            let bin = ((step * 7) % 5) as usize;
            rolling.observe(0, bin);
            expected.push(bin);
            expected.sort_unstable();
            let target = expected.len().div_ceil(2);
            assert_eq!(
                rolling.median_ticks(),
                Some(expected[target - 1]),
                "after {} observations",
                step + 1
            );
        }
    }
}
