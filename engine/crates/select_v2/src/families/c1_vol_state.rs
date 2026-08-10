//! `c1_vol_state` — intraday realized-volatility state, as of each cutoff.
//!
//! ## The estimator base: 1-minute log-mid returns
//!
//! Every intraday column here is a function of one series: the last NBBO
//! midpoint inside each 1-minute bar. Bars are keyed by the **absolute** minute
//! `ts_ms_b / 60_000` rather than by an offset from the session open, which is
//! exact rather than convenient: frame-B 09:30 ET is 570 whole minutes past a
//! midnight that is itself a whole multiple of 1,440 minutes, so absolute-minute
//! bins coincide with session-minute bins with no anchor to pass in and no
//! second 09:30 constant to drift from `corpus`'s. The same identity makes a
//! cutoff — `open_b + k * 60e9` — land exactly on an absolute-minute boundary,
//! so the cutoff at minute `M` is the *open* of minute `M` and the last bar the
//! family may read is `M - 1`.
//!
//! A return is taken between **consecutive present bars**: a minute with no
//! two-sided quote produces no bar, and the return then spans the gap rather
//! than being forward-filled into a fabricated zero. `rv_*_bps` is
//! `sqrt(sum r^2) * 1e4` over the returns whose later endpoint falls inside the
//! window — a window total, not an annualisation.
//!
//! ## Absence
//!
//! A one-sided NBBO (`bid_u6 <= 0` or `ask_u6 <= 0`) has no midpoint;
//! `(0 + ask) / 2` is not a price, so such quotes are skipped for the mid
//! series. A window holding no return yields `NaN` (not-applicable), never
//! `0.0` — `0.0` is reserved for the measured fact that prices did not move.
//! Every ratio whose denominator is zero is `NaN` too, so no cell can carry a
//! signed infinity; [`narrow`] enforces that at the emit boundary.
//!
//! ## Prior-session columns
//!
//! Ten columns need trailing-session context (daily vol estimators, HAR terms,
//! percentiles, ATR, the realized kernel). They are declared
//! [`AsOfRule::PriorSessionsOnly`], emitted `NaN` in-pass, and named with a
//! `_d` suffix so the daily-context post-pass can find them by suffix alone.
//! `har_rv_w_d` / `har_rv_m_d` carry both markers: `_w`/`_m` is the HAR horizon,
//! `_d` the fill marker.
//!
//! The integration test at the bottom of this file covers all three families of
//! this lane (`c1_vol_state`, `d1_liquidity_cost`, `h1_quality`) in one real
//! session pass.

use super::{AsOfRule, ColSpec, FamilyEmitter, FamilyRows, QuoteEvent, TradeEvent, Unit};
use crate::book::ActionCutoff;
use crate::error::{Result, SelectV2Error};
use std::collections::VecDeque;

/// Registered name.
pub const NAME: &str = "c1_vol_state";

/// Milliseconds in one minute bar.
const MS_PER_MINUTE: i64 = 60_000;
/// Nanoseconds in one minute bar.
const NS_PER_MINUTE: i64 = 60_000_000_000;
/// Basis points in one unit ratio.
const BPS: f64 = 10_000.0;
/// Minute bars retained: the 120-minute window needs 121 closes.
const RING_BARS: usize = 121;
/// Realized-vol windows, in minutes, in emitted order.
const RV_WINDOWS_MIN: [i64; 5] = [5, 15, 30, 60, 120];
/// Semivariance / vol-of-vol lookback, in minutes.
const SEMIVAR_WINDOW_MIN: i64 = 30;
/// Vol-of-vol sub-window width, in minutes.
const VOV_SUB_MIN: i64 = 5;
/// Sub-windows inside the vol-of-vol span (`30 / 5`).
const VOV_SUBS: usize = 6;
/// Bar-range window, in minutes.
const RANGE_WINDOW_MIN: i64 = 15;

/// The 22 emitted columns, in emitted order.
const COLUMNS: [ColSpec; 22] = [
    ColSpec::new("rv_5m_bps", Unit::Bps, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("rv_15m_bps", Unit::Bps, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("rv_30m_bps", Unit::Bps, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("rv_60m_bps", Unit::Bps, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("rv_120m_bps", Unit::Bps, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new(
        "semivar_up_over_down_30m",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new("vol_of_vol_30m", Unit::Bps, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("atr14_d", Unit::Bps, AsOfRule::PriorSessionsOnly),
    ColSpec::new("yz_vol_yday_d", Unit::Bps, AsOfRule::PriorSessionsOnly),
    ColSpec::new("yz_vol_5d_d", Unit::Bps, AsOfRule::PriorSessionsOnly),
    ColSpec::new("yz_vol_20d_d", Unit::Bps, AsOfRule::PriorSessionsOnly),
    ColSpec::new("har_rv_d", Unit::Bps, AsOfRule::PriorSessionsOnly),
    ColSpec::new("har_rv_w_d", Unit::Bps, AsOfRule::PriorSessionsOnly),
    ColSpec::new("har_rv_m_d", Unit::Bps, AsOfRule::PriorSessionsOnly),
    ColSpec::new(
        "rv_percentile_60d_d",
        Unit::Ratio,
        AsOfRule::PriorSessionsOnly,
    ),
    ColSpec::new("rk_daily_d", Unit::Bps, AsOfRule::PriorSessionsOnly),
    ColSpec::new(
        "intraday_minute_vol_percentile_d",
        Unit::Ratio,
        AsOfRule::PriorSessionsOnly,
    ),
    ColSpec::new(
        "rv_5m_over_rv_60m",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "downmove_vol_share_30m",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "bar_range_mean_15m_bps",
        Unit::Bps,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "bar_range_max_15m_bps",
        Unit::Bps,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "consec_expanding_ranges",
        Unit::Count,
        AsOfRule::StrictlyBeforeCutoff,
    ),
];

/// One 1-minute bar of the NBBO midpoint series.
#[derive(Clone, Copy, Debug)]
struct MinuteBar {
    /// Absolute minute, `ts_ms_b / 60_000`.
    minute: i64,
    last_mid_u6: i64,
    high_mid_u6: i64,
    low_mid_u6: i64,
}

impl MinuteBar {
    /// This bar's high-low range in bps of its own midpoint level. `None` when
    /// the level is not a usable price.
    fn range_bps(&self) -> Option<f64> {
        let high = as_f64(self.high_mid_u6);
        let low = as_f64(self.low_mid_u6);
        let level = f64::midpoint(high, low);
        if level > 0.0 {
            Some((high - low) / level * BPS)
        } else {
            None
        }
    }
}

/// Rolling 121-bar midpoint ring; every column is a pure function of it.
#[derive(Debug, Default)]
pub struct C1VolState {
    bars: VecDeque<MinuteBar>,
    rows: Vec<f32>,
}

impl FamilyEmitter for C1VolState {
    fn name(&self) -> &'static str {
        NAME
    }

    fn columns(&self) -> &[ColSpec] {
        &COLUMNS
    }

    fn on_quote(&mut self, quote: &QuoteEvent) {
        // A one-sided NBBO has no midpoint. Absent, not zero.
        if quote.bid_u6 <= 0 || quote.ask_u6 <= 0 {
            return;
        }
        let mid = quote.mid_u6();
        let minute = quote.ts_ms_b.div_euclid(MS_PER_MINUTE);
        match self.bars.back_mut() {
            Some(bar) if bar.minute == minute => {
                bar.last_mid_u6 = mid;
                bar.high_mid_u6 = bar.high_mid_u6.max(mid);
                bar.low_mid_u6 = bar.low_mid_u6.min(mid);
            }
            _ => {
                // The driver merges quotes and prints by timestamp, so minutes
                // are non-decreasing; a violation would be a driver regression,
                // not a data shape this family should paper over.
                debug_assert!(
                    self.bars.back().is_none_or(|bar| bar.minute < minute),
                    "minute bars must arrive in tape order"
                );
                if self.bars.len() == RING_BARS {
                    self.bars.pop_front();
                }
                self.bars.push_back(MinuteBar {
                    minute,
                    last_mid_u6: mid,
                    high_mid_u6: mid,
                    low_mid_u6: mid,
                });
            }
        }
    }

    /// Prints carry no NBBO midpoint of their own; the mid series is the quote
    /// series by construction.
    fn on_trade(&mut self, _trade: &TradeEvent) {}

    fn on_cutoff(&mut self, cutoff: &ActionCutoff) {
        let row = self.snapshot(cutoff.cutoff_ns_b.div_euclid(NS_PER_MINUTE));
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

/// The window aggregates read out of the bar ring at one cutoff.
struct Snapshot {
    /// `r^2` per return, and the age in minutes of the return's later endpoint.
    squares: [f64; RING_BARS],
    ages: [i64; RING_BARS],
    negative: [bool; RING_BARS],
    returns: usize,
    /// Per-bar range in bps, oldest first, for bars strictly before the cutoff.
    ranges: [f64; RING_BARS],
    range_ages: [i64; RING_BARS],
    bars: usize,
}

impl C1VolState {
    /// Reads the ring as of the open of absolute minute `cutoff_minute`.
    fn snapshot(&self, cutoff_minute: i64) -> [f32; COLUMNS.len()] {
        let scan = self.scan(cutoff_minute);
        let mut row = [f32::NAN; COLUMNS.len()];

        // 0..5 — realized vol over each window.
        let mut rv = [None; RV_WINDOWS_MIN.len()];
        for (slot, window) in RV_WINDOWS_MIN.iter().enumerate() {
            rv[slot] = scan.sum_squares(*window).map(|ss| ss.sqrt() * BPS);
            row[slot] = opt(rv[slot]);
        }

        // 5, 6, 18 — the 30-minute semivariance split and its vol-of-vol.
        let (up, down, hits) = scan.semivariance(SEMIVAR_WINDOW_MIN);
        row[5] = if hits == 0 || down <= 0.0 {
            f32::NAN
        } else {
            narrow(up / down)
        };
        row[6] = opt(scan.vol_of_vol());
        row[18] = if hits == 0 || up + down <= 0.0 {
            f32::NAN
        } else {
            narrow(down / (up + down))
        };

        // 7..17 — prior-session context, filled by the daily-context post-pass.
        // Left at the `NaN` the row was initialised with, deliberately.

        // 17 — short-window vol relative to the hour.
        row[17] = match (rv[0], rv[3]) {
            (Some(short), Some(hour)) if hour > 0.0 => narrow(short / hour),
            _ => f32::NAN,
        };

        // 19..22 — bar-range shape.
        let (range_mean, range_max) = scan.range_stats(RANGE_WINDOW_MIN);
        row[19] = opt(range_mean);
        row[20] = opt(range_max);
        row[21] = scan.consecutive_expansions().map_or(f32::NAN, narrow_u32);
        row
    }

    /// One pass over the ring, keeping only bars that closed strictly before
    /// the cutoff.
    fn scan(&self, cutoff_minute: i64) -> Snapshot {
        let mut scan = Snapshot {
            squares: [0.0; RING_BARS],
            ages: [0; RING_BARS],
            negative: [false; RING_BARS],
            returns: 0,
            ranges: [0.0; RING_BARS],
            range_ages: [0; RING_BARS],
            bars: 0,
        };
        let mut previous_mid: Option<i64> = None;
        for bar in &self.bars {
            // The driver announces a cutoff before delivering the event that
            // reached it, so this never trims a bar in practice; it is here so
            // that an ordering regression drops data rather than leaking it.
            if bar.minute >= cutoff_minute {
                break;
            }
            let age = cutoff_minute - bar.minute;
            if let Some(previous) = previous_mid
                && previous > 0
                && bar.last_mid_u6 > 0
            {
                let ret = (as_f64(bar.last_mid_u6) / as_f64(previous)).ln();
                if ret.is_finite() {
                    scan.squares[scan.returns] = ret * ret;
                    scan.ages[scan.returns] = age;
                    scan.negative[scan.returns] = ret < 0.0;
                    scan.returns += 1;
                }
            }
            previous_mid = Some(bar.last_mid_u6);
            if let Some(range) = bar.range_bps() {
                scan.ranges[scan.bars] = range;
                scan.range_ages[scan.bars] = age;
                scan.bars += 1;
            }
        }
        scan
    }
}

impl Snapshot {
    /// `sum r^2` over returns whose later endpoint is within `window` minutes.
    /// `None` when the window holds no return at all.
    fn sum_squares(&self, window: i64) -> Option<f64> {
        let mut total = 0.0;
        let mut hits = 0_usize;
        for index in 0..self.returns {
            if self.ages[index] <= window {
                total += self.squares[index];
                hits += 1;
            }
        }
        (hits > 0).then_some(total)
    }

    /// `(up sum of squares, down sum of squares, return count)` over `window`.
    fn semivariance(&self, window: i64) -> (f64, f64, usize) {
        let (mut up, mut down, mut hits) = (0.0, 0.0, 0_usize);
        for index in 0..self.returns {
            if self.ages[index] <= window {
                if self.negative[index] {
                    down += self.squares[index];
                } else {
                    up += self.squares[index];
                }
                hits += 1;
            }
        }
        (up, down, hits)
    }

    /// Sample standard deviation of the six disjoint 5-minute realized vols
    /// inside the 30-minute span. `None` with fewer than two populated
    /// sub-windows, where a spread is not defined.
    fn vol_of_vol(&self) -> Option<f64> {
        let mut sums = [0.0_f64; VOV_SUBS];
        let mut hits = [0_usize; VOV_SUBS];
        for index in 0..self.returns {
            let age = self.ages[index];
            if (1..=SEMIVAR_WINDOW_MIN).contains(&age) {
                let slot = usize::try_from((age - 1) / VOV_SUB_MIN).unwrap_or(VOV_SUBS);
                if slot < VOV_SUBS {
                    sums[slot] += self.squares[index];
                    hits[slot] += 1;
                }
            }
        }
        let mut values = [0.0_f64; VOV_SUBS];
        let mut populated = 0_usize;
        for slot in 0..VOV_SUBS {
            if hits[slot] > 0 {
                values[populated] = sums[slot].sqrt() * BPS;
                populated += 1;
            }
        }
        if populated < 2 {
            return None;
        }
        let count = as_f64_usize(populated);
        let mean = values[..populated].iter().sum::<f64>() / count;
        let variance = values[..populated]
            .iter()
            .map(|value| (value - mean) * (value - mean))
            .sum::<f64>()
            / (count - 1.0);
        Some(variance.sqrt())
    }

    /// `(mean, max)` bar range in bps over bars within `window` minutes.
    fn range_stats(&self, window: i64) -> (Option<f64>, Option<f64>) {
        let mut total = 0.0;
        let mut largest = f64::NEG_INFINITY;
        let mut hits = 0_usize;
        for index in 0..self.bars {
            if self.range_ages[index] <= window {
                total += self.ranges[index];
                largest = largest.max(self.ranges[index]);
                hits += 1;
            }
        }
        if hits == 0 {
            return (None, None);
        }
        (Some(total / as_f64_usize(hits)), Some(largest))
    }

    /// Length of the strictly-increasing run of bar ranges ending at the last
    /// bar before the cutoff. `None` with fewer than two bars, where no pair
    /// has been observed — distinct from an observed run of zero.
    fn consecutive_expansions(&self) -> Option<u32> {
        if self.bars < 2 {
            return None;
        }
        let mut run = 0_u32;
        let mut index = self.bars - 1;
        while index >= 1 && self.ranges[index] > self.ranges[index - 1] {
            run += 1;
            index -= 1;
        }
        Some(run)
    }
}

/// Narrows an intermediate to the emitted `f32`. A non-finite value — an
/// overflow, or an infinity that slipped past a zero-denominator guard —
/// becomes `NaN`: the leaf contract admits absence, never a signed infinity.
#[allow(clippy::cast_possible_truncation)]
fn narrow(value: f64) -> f32 {
    if !value.is_finite() {
        return f32::NAN;
    }
    let narrowed = value as f32;
    if narrowed.is_finite() {
        narrowed
    } else {
        f32::NAN
    }
}

/// `None` is absence, and absence is `NaN`.
fn opt(value: Option<f64>) -> f32 {
    value.map_or(f32::NAN, narrow)
}

/// Counts below `2^24` are exact in `f32`; a run cannot exceed 121.
fn narrow_u32(value: u32) -> f32 {
    narrow(f64::from(value))
}

/// u6 fixed point as an `f64` count of micro-dollars. Exact: u6 prices are far
/// below `2^53`.
#[allow(clippy::cast_precision_loss)]
fn as_f64(value: i64) -> f64 {
    value as f64
}

/// Window counts are bounded by 121; the `f64` image is exact.
#[allow(clippy::cast_precision_loss)]
fn as_f64_usize(value: usize) -> f64 {
    value as f64
}

#[cfg(test)]
mod tests {
    use super::{COLUMNS, C1VolState, MS_PER_MINUTE, NAME, NS_PER_MINUTE};
    use crate::book::{ActionCutoff, Side};
    use crate::families::{AsOfRule, FamilyEmitter, QuoteEvent};

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

    /// A two-sided quote whose midpoint is exactly `mid_u6`.
    fn quote(minute: i64, second: i64, mid_u6: i64) -> QuoteEvent {
        QuoteEvent {
            ts_ms_b: minute * MS_PER_MINUTE + second * 1_000,
            bid_u6: mid_u6 - CENT / 2,
            ask_u6: mid_u6 + CENT / 2,
            bid_shares: 100,
            ask_shares: 100,
        }
    }

    /// Feeds one quote per listed minute and reads the row at `cutoff_minute`.
    fn row_for(mids: &[(i64, i64)], cutoff_minute: i64) -> Vec<f32> {
        let mut family = C1VolState::default();
        for (minute, mid) in mids {
            family.on_quote(&quote(*minute, 30, *mid));
        }
        family.on_cutoff(&cutoff_at(cutoff_minute));
        let rows = family.emit(&[cutoff_at(cutoff_minute)]).expect("one row");
        assert_eq!(rows.columns, COLUMNS.len());
        rows.values
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

    /// **The shown-to-fail test.** A tape whose midpoint never moves has zero
    /// realized volatility — every log return is `ln(1) = 0`, so `sqrt(0) = 0`.
    /// The value is an observed zero, NOT absence: a window that saw returns
    /// and measured no movement is a different fact from a window that saw no
    /// return at all, which is `NaN` (covered by
    /// `an_empty_window_is_absent_not_zero`).
    ///
    /// This assertion was first written as `assert!(rv != 0.0)` and run: it
    /// failed with `left: 0.0, right: 0.0` at this line, proving the test
    /// executes the estimator and can distinguish its output. The assertion was
    /// then corrected to the true expectation below.
    /// Exact comparison is the assertion: an observed zero must be bit-exactly
    /// zero, or it is not distinguishable from a tiny real measurement.
    #[allow(clippy::float_cmp)]
    #[test]
    fn rv_on_a_constant_tape_is_zero() {
        let flat: Vec<(i64, i64)> = (100..110).map(|minute| (minute, TWO_HUNDRED)).collect();
        let row = row_for(&flat, 110);
        for window in ["rv_5m_bps", "rv_15m_bps", "rv_30m_bps", "rv_60m_bps", "rv_120m_bps"] {
            let value = column(&row, window);
            assert_eq!(value, 0.0, "{window} on a constant tape must be zero");
        }
        // A flat tape has no up and no down variance, so the two 30-minute
        // splits are undefined rather than zero.
        assert!(column(&row, "semivar_up_over_down_30m").is_nan());
        assert!(column(&row, "downmove_vol_share_30m").is_nan());
        // Every bar is a single price, so every range is exactly zero.
        assert_eq!(column(&row, "bar_range_mean_15m_bps"), 0.0);
        assert_eq!(column(&row, "bar_range_max_15m_bps"), 0.0);
        // No range ever exceeds its predecessor.
        assert_eq!(column(&row, "consec_expanding_ranges"), 0.0);
    }

    /// One 1-cent up-move over one minute: `ln(200.01 / 200.00) * 1e4`.
    /// `ln(1.00005) = 4.99987500...e-5`, so the window total is 0.4999875 bps.
    #[test]
    fn rv_matches_a_hand_computed_single_return() {
        let row = row_for(&[(100, TWO_HUNDRED), (101, TWO_HUNDRED + CENT)], 102);
        let expected = (200.01_f64 / 200.00_f64).ln() * 10_000.0;
        close(column(&row, "rv_5m_bps"), expected, 1e-4);
        close(column(&row, "rv_5m_bps"), 0.499_987_5, 1e-4);
        // Only one return exists, so every window holds exactly it.
        for window in ["rv_15m_bps", "rv_30m_bps", "rv_60m_bps", "rv_120m_bps"] {
            close(column(&row, window), expected, 1e-4);
        }
        // ...which makes the short-over-hour ratio exactly one.
        close(column(&row, "rv_5m_over_rv_60m"), 1.0, 1e-6);
        // One up return, no down return: the ratio's denominator is zero.
        assert!(column(&row, "semivar_up_over_down_30m").is_nan());
        close(column(&row, "downmove_vol_share_30m"), 0.0, 0.0);
    }

    /// Up one cent then back down one cent. `|ln(200.01/200.00)|` and
    /// `|ln(200.00/200.01)|` are equal, so the up and down sums of squares are
    /// equal: the ratio is 1 and the down share is exactly a half.
    #[test]
    fn semivariance_splits_the_signed_returns() {
        let row = row_for(
            &[
                (100, TWO_HUNDRED),
                (101, TWO_HUNDRED + CENT),
                (102, TWO_HUNDRED),
            ],
            103,
        );
        close(column(&row, "semivar_up_over_down_30m"), 1.0, 1e-6);
        close(column(&row, "downmove_vol_share_30m"), 0.5, 1e-6);
        // Two equal-magnitude returns: sqrt(2 r^2) = sqrt(2) * |r|.
        let single = (200.01_f64 / 200.00_f64).ln().abs() * 10_000.0;
        close(column(&row, "rv_5m_bps"), single * 2.0_f64.sqrt(), 1e-4);
    }

    /// A bar's range is its own high-low spread over its own midpoint level:
    /// high $200.10, low $199.90 gives level $200.00 and `0.20 / 200 * 1e4`
    /// = 10 bps exactly.
    #[test]
    fn bar_range_is_relative_to_the_bars_own_level() {
        let mut family = C1VolState::default();
        family.on_quote(&quote(100, 10, TWO_HUNDRED - 10 * CENT));
        family.on_quote(&quote(100, 20, TWO_HUNDRED + 10 * CENT));
        family.on_quote(&quote(100, 30, TWO_HUNDRED));
        family.on_cutoff(&cutoff_at(101));
        let rows = family.emit(&[cutoff_at(101)]).expect("one row");
        close(column(&rows.values, "bar_range_mean_15m_bps"), 10.0, 1e-3);
        close(column(&rows.values, "bar_range_max_15m_bps"), 10.0, 1e-3);
        // A single bar is one range: no pair has been observed.
        assert!(column(&rows.values, "consec_expanding_ranges").is_nan());
    }

    /// Ranges of 2, 4 and 6 cents run strictly upward across three bars, which
    /// is two expansions; a fourth, narrower bar resets the run to zero.
    #[test]
    fn consecutive_expansions_count_the_backward_run() {
        let mut family = C1VolState::default();
        for (minute, half_width) in [(100_i64, 1_i64), (101, 2), (102, 3)] {
            family.on_quote(&quote(minute, 10, TWO_HUNDRED - half_width * CENT));
            family.on_quote(&quote(minute, 20, TWO_HUNDRED + half_width * CENT));
        }
        family.on_cutoff(&cutoff_at(103));
        let mut cutoffs = vec![cutoff_at(103)];
        // A fourth, narrower bar ends the run.
        family.on_quote(&quote(103, 10, TWO_HUNDRED));
        family.on_quote(&quote(103, 20, TWO_HUNDRED + CENT));
        family.on_cutoff(&cutoff_at(104));
        cutoffs.push(cutoff_at(104));
        let rows = family.emit(&cutoffs).expect("two rows");
        assert_eq!(rows.rows(), 2);
        let first = &rows.values[..COLUMNS.len()];
        let second = &rows.values[COLUMNS.len()..];
        close(column(first, "consec_expanding_ranges"), 2.0, 0.0);
        close(column(second, "consec_expanding_ranges"), 0.0, 0.0);
    }

    /// Two 5-minute sub-windows carrying realized vols of `v` and `0` have a
    /// sample standard deviation of `v / sqrt(2)`.
    #[test]
    fn vol_of_vol_is_the_spread_across_five_minute_sub_windows() {
        let mut mids = vec![(100_i64, TWO_HUNDRED)];
        // Ages 6..10 at a cutoff of 111: one move inside the older sub-window.
        mids.push((101, TWO_HUNDRED));
        mids.push((102, TWO_HUNDRED));
        mids.push((103, TWO_HUNDRED));
        mids.push((104, TWO_HUNDRED));
        mids.push((105, TWO_HUNDRED + CENT));
        // Ages 1..5: a flat sub-window.
        for minute in 106..=110 {
            mids.push((minute, TWO_HUNDRED + CENT));
        }
        let row = row_for(&mids, 111);
        let moved = (200.01_f64 / 200.00_f64).ln().abs() * 10_000.0;
        // Recent sub-window is flat (0 bps); the older one carries `moved`.
        close(column(&row, "vol_of_vol_30m"), moved / 2.0_f64.sqrt(), 1e-4);
    }

    /// A window with no return at all is absent, not zero — the distinction the
    /// constant-tape test is the other half of.
    #[test]
    fn an_empty_window_is_absent_not_zero() {
        let row = row_for(&[(100, TWO_HUNDRED)], 101);
        for window in ["rv_5m_bps", "rv_15m_bps", "rv_120m_bps"] {
            assert!(column(&row, window).is_nan(), "{window} must be absent");
        }
        // ...and a family shown nothing at all emits an all-absent row.
        let empty = row_for(&[], 101);
        assert!(empty.iter().all(|value| value.is_nan()));
    }

    /// A one-sided NBBO carries no midpoint and must not enter the mid series;
    /// if it did, `(0 + 200.01)/2 = 100.005` would register as a -69% return.
    /// Exact comparison is the assertion: an observed zero must be bit-exactly
    /// zero, or it is not distinguishable from a tiny real measurement.
    #[allow(clippy::float_cmp)]
    #[test]
    fn a_one_sided_quote_is_skipped_rather_than_halved() {
        let mut family = C1VolState::default();
        family.on_quote(&quote(100, 10, TWO_HUNDRED));
        family.on_quote(&QuoteEvent {
            ts_ms_b: 101 * MS_PER_MINUTE,
            bid_u6: 0,
            ask_u6: TWO_HUNDRED + CENT,
            bid_shares: 0,
            ask_shares: 100,
        });
        family.on_quote(&quote(102, 10, TWO_HUNDRED));
        family.on_cutoff(&cutoff_at(103));
        let rows = family.emit(&[cutoff_at(103)]).expect("one row");
        // Two present bars, both at $200.00: one return, and it is zero.
        assert_eq!(column(&rows.values, "rv_5m_bps"), 0.0);
    }

    /// The `_d` suffix is the contract the daily-context post-pass reads: every
    /// prior-session column carries it, and every column carrying it is left
    /// absent by this pass.
    #[test]
    fn prior_session_columns_are_exactly_the_d_suffixed_ones() {
        let row = row_for(&[(100, TWO_HUNDRED), (101, TWO_HUNDRED + CENT)], 102);
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
        assert_eq!(prior, 10, "the daily-context post-pass owns ten columns");
    }

    #[test]
    fn the_declared_width_is_what_gets_emitted() {
        assert_eq!(COLUMNS.len(), 22);
        assert!(COLUMNS.len() <= crate::families::MAX_FAMILY_COLUMNS);
        let mut names: Vec<&str> = COLUMNS.iter().map(|spec| spec.name).collect();
        names.sort_unstable();
        names.dedup();
        assert_eq!(names.len(), COLUMNS.len(), "column names must be unique");
    }

    /// A row count that disagrees with the cutoff list is a refusal, not a
    /// silently short leaf.
    #[test]
    fn emit_refuses_a_row_count_that_does_not_match_the_cutoffs() {
        let mut family = C1VolState::default();
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

/// The lane's integration check: one real session pass over 2022-03-01 with
/// this lane's three families, asserting the contracts that only real data can
/// falsify. Kept in this file because the lane owns exactly these three
/// emitters.
#[cfg(test)]
mod integration {
    use crate::book;
    use crate::calendar;
    use crate::families::{AsOfRule, FamilyEmitter};
    use crate::session_pass::{SessionPassConfig, run_session};
    use crate::sources::TokenRoots;

    const DAY: &str = "2022-03-01";
    const LANE: [&str; 3] = ["c1_vol_state", "d1_liquidity_cost", "h1_quality"];
    /// `h1_quality`'s schema-era flag is `NaN` for a reason the name cannot
    /// carry: [`crate::families::FamilyEmitter`] never shows a family which
    /// reader profile produced an event, so the era is unobservable in-pass.
    /// Named here so the assertion below states the exception instead of
    /// hiding it.
    const NAN_WITHOUT_D_SUFFIX: [&str; 1] = ["schema_era_flag"];

    #[test]
    fn the_lane_emits_one_finite_row_per_action_on_a_real_session() {
        let scope = calendar::admit(DAY).expect("2022-03-01 is a registry session");
        let ordinal = u32::try_from(scope.session_ordinal()).expect("ordinal fits u32");

        // The absolute-minute binning every window in this lane rests on is
        // only exact because a cutoff lands on a whole minute. Checked, not
        // assumed.
        assert_eq!(
            scope.open_ms_b() % 60_000,
            0,
            "frame-B open is not on a minute boundary"
        );

        let loaded = book::load_sessions(
            std::path::Path::new(book::DEFAULT_BOOK_DIR),
            Some(&[ordinal]),
        )
        .expect("action book");
        let cutoffs = loaded.cutoffs_for(ordinal).to_vec();
        assert!(cutoffs.len() > 100, "not enough actions to be evidence");
        for cutoff in &cutoffs {
            assert_eq!(cutoff.cutoff_ns_b % 60_000_000_000, 0);
        }

        let roots = TokenRoots::default();
        let config = SessionPassConfig {
            stock_quotes_root: roots.stock_quotes(),
            stock_trades_root: roots.stock_trades(),
            out_dir: std::path::PathBuf::from("/workspace/artifacts/cache/select_v2_test_out")
                .join("r3_lane"),
            write_pp1: false,
            write_families: false,
        };
        let mut families: Vec<Box<dyn FamilyEmitter>> = LANE
            .iter()
            .map(|name| crate::families::build(name).expect("registered family"))
            .collect();
        let outcome = run_session(&scope, &cutoffs, &mut families, &config).expect("pass");
        assert!(outcome.quote_rows > 0 && outcome.trade_rows > 0);

        for family in &mut families {
            let name = family.name();
            let specs: Vec<(&'static str, AsOfRule)> = family
                .columns()
                .iter()
                .map(|spec| (spec.name, spec.as_of))
                .collect();
            let rows = family.emit(&cutoffs).expect("emit");

            // Contract 1: one row per action, at the declared width.
            assert_eq!(rows.columns, specs.len(), "{name} width");
            assert_eq!(rows.rows(), cutoffs.len(), "{name} rows != cutoffs");

            // Contract 2: no cell is a signed infinity.
            for (index, value) in rows.values.iter().enumerate() {
                assert!(
                    !value.is_infinite(),
                    "{name} column {} row {} is {value}",
                    specs[index % specs.len()].0,
                    index / specs.len()
                );
            }

            // Contract 3: the always-absent columns are exactly the
            // prior-session ones plus the named, reasoned exceptions.
            for (column, (column_name, as_of)) in specs.iter().enumerate() {
                let all_nan = (0..rows.rows())
                    .all(|row| rows.values[row * rows.columns + column].is_nan());
                let expected_absent = *as_of == AsOfRule::PriorSessionsOnly
                    || NAN_WITHOUT_D_SUFFIX.contains(column_name);
                if expected_absent {
                    assert!(all_nan, "{name}.{column_name} must be left to python");
                    assert!(
                        column_name.ends_with("_d")
                            || NAN_WITHOUT_D_SUFFIX.contains(column_name),
                        "{name}.{column_name} is absent but not marked `_d`"
                    );
                } else {
                    assert!(
                        !all_nan,
                        "{name}.{column_name} is an in-pass column but never computed a value"
                    );
                }
            }
        }
    }
}
