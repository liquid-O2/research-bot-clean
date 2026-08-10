//! `c2_trend_path` — the trend/path columns (plan Part V, C2).
//!
//! C2 streams the same 1-minute tape A2 does; see
//! [`crate::families::a2_session_state`] for the anchor recovery, the log-bps
//! convention and the all-or-nothing window rule, all of which apply verbatim
//! here. It imports [`MinuteTape`] rather than keeping a second copy of that
//! arithmetic, so the two families cannot drift apart in what "the last 30
//! minutes" means.
//!
//! ## Width: 15 columns, and the specification says 16 — FLAGGED
//!
//! The lane specification heads C2 with `(16)` and then enumerates:
//! `ret_5m/15m/30m/60m/120m_bps` (5), `move_over_rv30`/`move_over_rv60` (2),
//! `path_efficiency_30m`/`_60m` (2), `max_drawup_60m_bps`/
//! `max_drawdown_60m_bps` (2), `vwap_slope_15m_bps` (1),
//! `mins_since_opp_extreme` (1), `newhigh_count_30m`/`newlow_count_30m` (2).
//! That sums to **15**, and plan Part V line 166 enumerates the same 15 under
//! the same `(16)` heading. A1 (12) and A2 (22) both sum to their headline, so
//! the mismatch is C2's alone and reads as an arithmetic slip in the header
//! rather than a missing column with a name. This file emits exactly the 15
//! enumerated columns: inventing a sixteenth would put a column with no
//! definition into the panel, and padding one with NaN would put a column with
//! no meaning there.
//!
//! ## Two definitions the specification leaves to the implementer
//!
//! * **`mins_since_opp_extreme`** — "time since opposite extreme". C2 has no
//!   side of its own, but the action does: `ActionCutoff::side` says which
//!   extreme the action leans against. The opposite extreme is therefore the
//!   other one, and this column is the minutes since the session last extended
//!   it — for a `HIGH`-side action, the minutes since the session low was last
//!   extended. That is the reading that uses information actually present;
//!   defining it as "the older of the two extremes" would have made it a
//!   deterministic function of A2's `mins_since_high`/`mins_since_low` and
//!   carried no new signal.
//! * **`max_drawup_60m_bps` / `max_drawdown_60m_bps`** are non-negative
//!   depths, both in log-bps, measured over the close-to-close path of the
//!   last 60 minutes (61 points, the window's opening mid included). Intra-bar
//!   extremes are deliberately NOT used: the order of the high and the low
//!   inside one minute is unknown, and assuming one would manufacture a path
//!   the tape never showed.
//!
//! ## Path efficiency is exact, not approximate
//!
//! Because every return here is a log return, the net move over a window is
//! exactly the sum of that window's 1-minute returns, so
//! `|net| / sum(|1-minute moves|)` is bounded by 1 by construction rather than
//! by rounding luck. Both the numerator and the denominator are taken from the
//! same bar slice, so no window can be half-formed.

use super::a2_session_state::{BPS, MinuteTape, count_f64, finite, ln_ratio, log_bps};
use super::{AsOfRule, ColSpec, FamilyEmitter, FamilyRows, QuoteEvent, TradeEvent, Unit};
use crate::book::{ActionCutoff, Side};
use crate::error::{Result, SelectV2Error};

/// Registered name.
pub const NAME: &str = "c2_trend_path";

/// The return windows, in minutes, in emission order.
const RETURN_WINDOWS: [i64; 5] = [5, 15, 30, 60, 120];

/// The window `move_over_rv30`, `path_efficiency_30m` and the new-extreme
/// counts measure.
const SHORT_WINDOW: i64 = 30;

/// The window `move_over_rv60`, `path_efficiency_60m` and the drawup/drawdown
/// pair measure.
const LONG_WINDOW: i64 = 60;

/// The window `vwap_slope_15m_bps` measures.
const VWAP_WINDOW: i64 = 15;

/// The 15 columns, in emission order.
const COLUMNS: [ColSpec; 15] = [
    ColSpec::new("ret_5m_bps", Unit::Bps, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("ret_15m_bps", Unit::Bps, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("ret_30m_bps", Unit::Bps, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("ret_60m_bps", Unit::Bps, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("ret_120m_bps", Unit::Bps, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("move_over_rv30", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("move_over_rv60", Unit::Ratio, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new(
        "path_efficiency_30m",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "path_efficiency_60m",
        Unit::Ratio,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "max_drawup_60m_bps",
        Unit::Bps,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "max_drawdown_60m_bps",
        Unit::Bps,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "vwap_slope_15m_bps",
        Unit::Bps,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "mins_since_opp_extreme",
        Unit::Bars,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "newhigh_count_30m",
        Unit::Count,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "newlow_count_30m",
        Unit::Count,
        AsOfRule::StrictlyBeforeCutoff,
    ),
];

/// What one window of bars says about the path through it.
#[derive(Clone, Copy, Debug)]
struct WindowPath {
    /// Net log-bps move across the window.
    net_bps: f64,
    /// Sum of the absolute 1-minute log-bps moves.
    variation_bps: f64,
    /// Realized volatility of the window's 1-minute returns, log-bps.
    rv_bps: f64,
    /// Minutes that extended the session high / low inside the window.
    new_highs: u32,
    new_lows: u32,
}

impl WindowPath {
    /// Measures the `minutes` complete bars ending `minutes_after_open` into
    /// the session. `None` unless the whole window is present.
    fn measure(tape: &MinuteTape, minutes_after_open: i64, minutes: i64) -> Option<Self> {
        let bars = tape.window(minutes_after_open, minutes)?;
        let mut net = 0.0_f64;
        let mut variation = 0.0_f64;
        let mut sum_squares = 0.0_f64;
        let mut new_highs = 0_u32;
        let mut new_lows = 0_u32;
        for bar in bars {
            net += bar.ret_ln;
            variation += bar.ret_ln.abs();
            sum_squares += bar.ret_ln * bar.ret_ln;
            new_highs += u32::from(bar.new_high);
            new_lows += u32::from(bar.new_low);
        }
        Some(Self {
            net_bps: net * BPS,
            variation_bps: variation * BPS,
            rv_bps: sum_squares.sqrt() * BPS,
            new_highs,
            new_lows,
        })
    }

    /// `|net| / rv` — how far the window travelled per unit of its own
    /// volatility. NaN when the window did not move at all.
    fn move_over_rv(self) -> f64 {
        if self.rv_bps <= 0.0 {
            return f64::NAN;
        }
        self.net_bps.abs() / self.rv_bps
    }

    /// `|net| / total variation`, in `[0, 1]`. NaN for a window with no
    /// 1-minute movement at all — undefined, not perfectly efficient.
    fn efficiency(self) -> f64 {
        if self.variation_bps <= 0.0 {
            return f64::NAN;
        }
        self.net_bps.abs() / self.variation_bps
    }
}

/// Largest run-up and largest run-down of the close-to-close path over the
/// `window` minutes ending `minutes_after_open` into the session, both
/// non-negative log-bps. `None` unless every point of the path exists.
fn drawup_drawdown(tape: &MinuteTape, minutes_after_open: i64, window: i64) -> Option<(f64, f64)> {
    let start = minutes_after_open - window;
    if start < 0 {
        return None;
    }
    let base = tape.price_at(start)?;
    let (mut lowest, mut highest) = (0.0_f64, 0.0_f64);
    let (mut drawup, mut drawdown) = (0.0_f64, 0.0_f64);
    for step in 0..=window {
        let level = ln_ratio(tape.price_at(start + step)?, base) * BPS;
        lowest = lowest.min(level);
        highest = highest.max(level);
        drawup = drawup.max(level - lowest);
        drawdown = drawdown.max(highest - level);
    }
    Some((drawup, drawdown))
}

/// Trend and path shape at each action's cutoff.
#[derive(Clone, Debug)]
pub struct C2TrendPath {
    tape: MinuteTape,
    rows: Vec<f32>,
}

impl Default for C2TrendPath {
    fn default() -> Self {
        Self::new()
    }
}

impl C2TrendPath {
    /// A fresh emitter for one session.
    #[must_use]
    pub const fn new() -> Self {
        Self {
            tape: MinuteTape::new(),
            rows: Vec::new(),
        }
    }

    /// The tape this emitter accumulated.
    #[must_use]
    pub const fn tape(&self) -> &MinuteTape {
        &self.tape
    }
}

/// Value-namespace constructor for `families::build`, which currently spells
/// the family as the unit-struct expression `Box::new(c2_trend_path::
/// C2TrendPath)`. `mod.rs` belongs to another lane, so the emitter supplies
/// the value that expression needs rather than forcing an edit there. Once
/// `build` says `C2TrendPath::default()`, delete this const.
#[allow(non_upper_case_globals)]
pub const C2TrendPath: C2TrendPath = C2TrendPath::new();

impl FamilyEmitter for C2TrendPath {
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

    fn on_cutoff(&mut self, cutoff: &ActionCutoff) {
        let minutes = self.tape.anchor_and_seal(cutoff);
        let short = WindowPath::measure(&self.tape, minutes, SHORT_WINDOW);
        let long = WindowPath::measure(&self.tape, minutes, LONG_WINDOW);
        let path = drawup_drawdown(&self.tape, minutes, LONG_WINDOW);
        // The opposite extreme is the one the action does NOT lean against.
        let opposite = match cutoff.side {
            Side::High => self.tape.minutes_since_low(minutes),
            Side::Low => self.tape.minutes_since_high(minutes),
        };

        for window in RETURN_WINDOWS {
            let net = WindowPath::measure(&self.tape, minutes, window)
                .map_or(f64::NAN, |measured| measured.net_bps);
            self.rows.push(finite(net));
        }
        self.rows.extend_from_slice(&[
            finite(short.map_or(f64::NAN, WindowPath::move_over_rv)),
            finite(long.map_or(f64::NAN, WindowPath::move_over_rv)),
            finite(short.map_or(f64::NAN, WindowPath::efficiency)),
            finite(long.map_or(f64::NAN, WindowPath::efficiency)),
            finite(path.map_or(f64::NAN, |(drawup, _)| drawup)),
            finite(path.map_or(f64::NAN, |(_, drawdown)| drawdown)),
            finite(log_bps(
                self.tape.vwap_at(minutes),
                self.tape.vwap_at(minutes - VWAP_WINDOW),
            )),
            finite(opposite.map_or(f64::NAN, count_f64)),
            finite(short.map_or(f64::NAN, |measured| f64::from(measured.new_highs))),
            finite(short.map_or(f64::NAN, |measured| f64::from(measured.new_lows))),
        ]);
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
    use super::super::a2_session_state::test_support::{cutoff_for, drive, quote_at, trade_at};
    use super::{C2TrendPath, COLUMNS, NAME};
    use crate::book::Side;
    use crate::calendar::{self, DayScope};
    use crate::families::{FamilyEmitter, QuoteEvent};

    const DEV_DAY: &str = "2022-03-01";

    fn row(values: &[f32], index: usize) -> &[f32] {
        &values[index * COLUMNS.len()..(index + 1) * COLUMNS.len()]
    }

    /// One quote per minute at the given mid, in cents, one second into each
    /// minute so every bar closes on its own price.
    fn ladder(scope: &DayScope, mids: &[i64]) -> Vec<QuoteEvent> {
        mids.iter()
            .enumerate()
            .map(|(minute, mid)| {
                quote_at(
                    scope,
                    i64::try_from(minute).expect("small") * 60 + 1,
                    *mid,
                )
            })
            .collect()
    }

    #[test]
    fn column_names_and_width_are_the_enumerated_fifteen() {
        let family = C2TrendPath::default();
        assert_eq!(family.name(), NAME);
        let names: Vec<&str> = family.columns().iter().map(|spec| spec.name).collect();
        assert_eq!(
            names,
            vec![
                "ret_5m_bps",
                "ret_15m_bps",
                "ret_30m_bps",
                "ret_60m_bps",
                "ret_120m_bps",
                "move_over_rv30",
                "move_over_rv60",
                "path_efficiency_30m",
                "path_efficiency_60m",
                "max_drawup_60m_bps",
                "max_drawdown_60m_bps",
                "vwap_slope_15m_bps",
                "mins_since_opp_extreme",
                "newhigh_count_30m",
                "newlow_count_30m",
            ]
        );
        assert_eq!(
            family.columns().len(),
            15,
            "the specification's enumeration is 15 columns; its (16) header is a slip"
        );
    }

    #[test]
    fn reversing_the_tape_flips_every_return_sign() {
        let scope = calendar::admit(DEV_DAY).expect("registered");
        let rising: Vec<i64> = (0..10).map(|minute| 20_000 + minute * 2).collect();
        let falling: Vec<i64> = rising.iter().rev().copied().collect();
        let cutoffs = [cutoff_for(&scope, 8, Side::High)];

        let mut up = C2TrendPath::default();
        let up_values = drive(&mut up, &ladder(&scope, &rising), &[], &cutoffs);
        let mut down = C2TrendPath::default();
        let down_values = drive(&mut down, &ladder(&scope, &falling), &[], &cutoffs);

        assert!(up_values[0] > 0.0, "a rising tape must return positive");
        assert!(down_values[0] < 0.0, "a falling tape must return negative");
        // Log returns are exactly antisymmetric under path reversal.
        assert!(
            (up_values[0] + down_values[0]).abs() < 1e-3,
            "ret_5m {} and {} are not mirror images",
            up_values[0],
            down_values[0]
        );
    }

    #[test]
    fn a_return_is_the_measured_log_move_over_its_own_window() {
        let scope = calendar::admit(DEV_DAY).expect("registered");
        // Minute 0 closes at 200.00, minute 7 at 200.14.
        let mids: Vec<i64> = (0..10).map(|minute| 20_000 + minute * 2).collect();
        let cutoffs = [cutoff_for(&scope, 8, Side::High)];
        let mut family = C2TrendPath::default();
        let values = drive(&mut family, &ladder(&scope, &mids), &[], &cutoffs);
        // The cutoff of bar 8 stands at minute 8; 5 minutes back is minute 3,
        // i.e. the close of bar 2 (200.04) against the close of bar 7 (200.14).
        let expected = 10_000.0 * (20_014.0_f64 / 20_004.0).ln();
        assert!(
            (f64::from(values[0]) - expected).abs() < 1e-3,
            "ret_5m_bps was {}, expected {expected}",
            values[0]
        );
    }

    #[test]
    fn windows_that_precede_the_open_are_absent() {
        let scope = calendar::admit(DEV_DAY).expect("registered");
        let mids: Vec<i64> = (0..40).map(|minute| 20_000 + minute).collect();
        let quotes = ladder(&scope, &mids);
        // At minute 20 the 5- and 15-minute windows exist; 30, 60 and 120 do
        // not, and neither does anything built on the 30-minute window.
        let cutoffs = [cutoff_for(&scope, 20, Side::Low)];
        let mut family = C2TrendPath::default();
        let values = drive(&mut family, &quotes, &[], &cutoffs);
        assert!(values[0].is_finite(), "ret_5m");
        assert!(values[1].is_finite(), "ret_15m");
        for (index, name) in [
            (2, "ret_30m"),
            (3, "ret_60m"),
            (4, "ret_120m"),
            (5, "move_over_rv30"),
            (6, "move_over_rv60"),
            (7, "path_efficiency_30m"),
            (8, "path_efficiency_60m"),
            (9, "max_drawup_60m"),
            (10, "max_drawdown_60m"),
            (13, "newhigh_count_30m"),
            (14, "newlow_count_30m"),
        ] {
            assert!(values[index].is_nan(), "{name} must be absent at minute 20");
        }
    }

    #[test]
    fn path_efficiency_is_one_on_a_monotone_path_and_less_on_a_zigzag() {
        let scope = calendar::admit(DEV_DAY).expect("registered");
        let straight: Vec<i64> = (0..40).map(|minute| 20_000 + minute).collect();
        let zigzag: Vec<i64> = (0..40)
            .map(|minute| 20_000 + minute + if minute % 2 == 0 { 0 } else { 12 })
            .collect();
        let cutoffs = [cutoff_for(&scope, 32, Side::High)];

        let mut family = C2TrendPath::default();
        let values = drive(&mut family, &ladder(&scope, &straight), &[], &cutoffs);
        assert!(
            (values[7] - 1.0).abs() < 1e-5,
            "a monotone path is perfectly efficient, got {}",
            values[7]
        );

        let mut family = C2TrendPath::default();
        let values = drive(&mut family, &ladder(&scope, &zigzag), &[], &cutoffs);
        assert!(
            values[7] > 0.0 && values[7] < 0.5,
            "a zigzag path must be inefficient, got {}",
            values[7]
        );
    }

    #[test]
    fn drawup_and_drawdown_are_non_negative_depths_of_the_same_path() {
        let scope = calendar::admit(DEV_DAY).expect("registered");
        // Rise 100 cents over 30 minutes, then give back 40.
        let mut mids: Vec<i64> = (0..=30).map(|minute| 20_000 + minute * 10).collect();
        mids.extend((1..=30).map(|minute| 20_300 - minute * 4));
        let cutoffs = [cutoff_for(&scope, 61, Side::High)];
        let mut family = C2TrendPath::default();
        let values = drive(&mut family, &ladder(&scope, &mids), &[], &cutoffs);
        let drawup = f64::from(values[9]);
        let drawdown = f64::from(values[10]);
        assert!(drawup > 0.0 && drawdown > 0.0);
        // The 60-minute window ending at minute 61 is the closes of bars 0-60:
        // it opens at 200.00, tops at 203.00 in bar 30 and ends at 201.80.
        let expected_up = 10_000.0 * (20_300.0_f64 / 20_000.0).ln();
        let expected_down = 10_000.0 * (20_300.0_f64 / 20_180.0).ln();
        assert!(
            (drawup - expected_up).abs() < 1e-2,
            "max_drawup was {drawup}, expected {expected_up}"
        );
        assert!(
            (drawdown - expected_down).abs() < 1e-2,
            "max_drawdown was {drawdown}, expected {expected_down}"
        );
    }

    #[test]
    fn the_opposite_extreme_is_chosen_by_the_actions_own_side() {
        let scope = calendar::admit(DEV_DAY).expect("registered");
        // Opens at 201.00, tops at 202.00 in minute 1, then grinds down to a
        // session low of 200.00 in minute 20 — below the open, so the low is
        // genuinely extended there — and flattens above it afterwards.
        let mut mids = vec![20_100, 20_200];
        mids.extend((2..=20).map(|minute| 20_200 - minute * 10));
        mids.extend((21..40).map(|_| 20_050));
        let quotes = ladder(&scope, &mids);
        let cutoffs = [
            cutoff_for(&scope, 35, Side::High),
            cutoff_for(&scope, 35, Side::Low),
        ];
        let mut family = C2TrendPath::default();
        let values = drive(&mut family, &quotes, &[], &cutoffs);
        // A HIGH-side action looks back at the LOW (minute 20 -> 14 complete
        // minutes ago at a cutoff closing minute 34).
        assert!(
            (row(&values, 0)[12] - 14.0).abs() < 1e-6,
            "HIGH side must measure the low, got {}",
            row(&values, 0)[12]
        );
        // A LOW-side action looks back at the HIGH (minute 1).
        assert!(
            (row(&values, 1)[12] - 33.0).abs() < 1e-6,
            "LOW side must measure the high, got {}",
            row(&values, 1)[12]
        );
    }

    #[test]
    fn vwap_slope_needs_a_vwap_at_both_ends_of_its_window() {
        let scope = calendar::admit(DEV_DAY).expect("registered");
        let mids: Vec<i64> = (0..40).map(|_| 20_000).collect();
        let quotes = ladder(&scope, &mids);
        let cutoffs = [cutoff_for(&scope, 20, Side::High)];

        // No prints at all: absent at both ends.
        let mut family = C2TrendPath::default();
        let values = drive(&mut family, &quotes, &[], &cutoffs);
        assert!(values[11].is_nan(), "no prints, no VWAP slope");

        // A print at minute 1 (inside the trailing end) and one at minute 18
        // (after it) move the cumulative VWAP up, so the slope is positive.
        let trades = [
            trade_at(&scope, 90, 20_000, 1_000),
            trade_at(&scope, 18 * 60 + 30, 20_400, 9_000),
        ];
        let mut family = C2TrendPath::default();
        let values = drive(&mut family, &quotes, &trades, &cutoffs);
        assert!(
            values[11] > 0.0,
            "a higher-priced later print must lift the VWAP, got {}",
            values[11]
        );
    }

    #[test]
    fn new_extreme_counts_are_confined_to_the_thirty_minute_window() {
        let scope = calendar::admit(DEV_DAY).expect("registered");
        // Highs in minutes 1-5 (topping at 200.25), then flat below that top,
        // then three genuine new highs in minutes 34-36.
        let mut mids: Vec<i64> = (0..=5).map(|minute| 20_000 + minute * 5).collect();
        mids.extend((6..34).map(|_| 20_020));
        mids.extend((34..=36).map(|minute| 20_025 + (minute - 33) * 5));
        mids.extend((37..40).map(|_| 20_040));
        let cutoffs = [cutoff_for(&scope, 38, Side::Low)];
        let mut family = C2TrendPath::default();
        let values = drive(&mut family, &ladder(&scope, &mids), &[], &cutoffs);
        // Window covers minutes 8..37, so only the three late new highs count.
        assert!(
            (values[13] - 3.0).abs() < 1e-6,
            "newhigh_count_30m was {}",
            values[13]
        );
        assert!((values[14] - 0.0).abs() < 1e-6, "newlow_count_30m");
    }

    #[test]
    fn every_announced_cutoff_gets_one_row_even_with_an_empty_tape() {
        let scope = calendar::admit(DEV_DAY).expect("registered");
        let cutoffs = [
            cutoff_for(&scope, 3, Side::High),
            cutoff_for(&scope, 240, Side::Low),
        ];
        let mut family = C2TrendPath::default();
        let values = drive(&mut family, &[], &[], &cutoffs);
        assert_eq!(values.len(), cutoffs.len() * COLUMNS.len());
        assert!(values.iter().all(|value| value.is_nan()));
    }

    #[test]
    fn real_session_emits_one_finite_or_absent_row_per_action() {
        let mut family = C2TrendPath::default();
        let (values, cutoff_count) =
            super::super::a2_session_state::test_support::drive_real_session(&mut family, DEV_DAY);
        assert_eq!(values.len(), cutoff_count * COLUMNS.len());
        assert!(
            values.iter().all(|value| !value.is_infinite()),
            "a real session produced an infinity"
        );
        // Path efficiency is a bounded ratio wherever it is defined at all.
        let mut measured = 0_usize;
        for index in 0..cutoff_count {
            for column in [7, 8] {
                let value = row(&values, index)[column];
                if value.is_nan() {
                    continue;
                }
                measured += 1;
                assert!(
                    (0.0..=1.0).contains(&value),
                    "row {index} column {column} efficiency {value} escaped [0, 1]"
                );
            }
        }
        assert!(measured > 0, "no path-efficiency value was defined at all");
    }
}
