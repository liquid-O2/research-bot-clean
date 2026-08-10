//! `b1_turn_geometry` — **16 columns**: the shape of the turn an action leans
//! on, read as-of its cutoff.
//!
//! Half of the family is the action's own constituent summary carried by the
//! SELECT.4 spine ([`crate::book::ActSetSummary`], as-of rule
//! [`AsOfRule::BookSummaryAtCutoff`]); the other half is 1-minute bar geometry
//! accumulated from the raw NBBO stream ([`AsOfRule::StrictlyBeforeCutoff`]).
//! No d1/d2/d3 slot-reachability columns: **deleted by finding F-18** — they
//! were the old decision-ladder/cap machinery, meaningless under the uncapped
//! ruling, with unproven as-of semantics.
//!
//! ## The price series is the computed midpoint
//!
//! Every geometric column here is a function of `(bid + ask) / 2` in u6, never
//! of the vendor `mid` column (which is a SUM in the `CentInt32` profile) and
//! never of the print tape. B1 ignores prints entirely: turn geometry is a
//! quote-side object, and using two different price series for the pivot in B1
//! and B2 would make the two families disagree about where the pivot is.
//!
//! ## Session extremes, bars and windows
//!
//! * The **session extreme** on a side is the running max (`HIGH`) or min
//!   (`LOW`) of the midpoint over every RTH quote the family has been shown,
//!   which — by the driver's announce-then-deliver ordering — is exactly the
//!   tape strictly before the cutoff.
//! * A **bar** is an absolute wall-minute, keyed `ts_ms.div_euclid(60_000)`.
//!   Frame-B 09:30 is a whole minute, so this grid is the session's own bar
//!   grid with no second anchor: the cutoff of 1-based bar `n` is the close of
//!   the bar whose key is `cutoff_ms / 60_000 - 1`, and bars `1..=n` are
//!   complete at that instant.
//! * A trailing window of `w` minutes is the `w` bar keys ending at (and
//!   including) the cutoff bar, which is complete. Bars with no quote are
//!   ABSENT: they contribute nothing and are not counted as zero.
//!
//! ## Exact definitions of the four columns that could be read two ways
//!
//! * `overshoot_bps` — how far the last 30 minutes ran past where the tape sits
//!   now, on the action's side. Let `E30` be the max (`HIGH`) or min (`LOW`)
//!   midpoint over bar keys `[k-29, k]` and `M` the midpoint at the cutoff:
//!   `HIGH -> (E30 - M) / M * 1e4`, `LOW -> (M - E30) / M * 1e4`. Non-negative
//!   whenever the cutoff midpoint falls inside the window, which is every
//!   session without a >30-minute quote gap. It differs from
//!   `pivot_dist_from_session_extreme_bps` only in window: 30 bars versus the
//!   whole session so far.
//! * `envelope_width_bps` vs `entry_price_spread_bps` — the same numerator
//!   (`act_set_entry_price_u6_max - act_set_entry_price_u6_min`) over two
//!   different denominators: the tape midpoint at the cutoff, and the action's
//!   own `act_set_entry_price_u6_median`. The first is `NaN` when no quote has
//!   been seen yet; the second is always defined from the book alone.
//! * `retest_count_30m` — bar keys in `[k-29, k]` whose observed midpoint range
//!   intersects `E * (1 +/- 5bps)`, where `E` is the same-side SESSION extreme
//!   (not the 30-minute one). One count per bar, not per quote.
//! * `same_side_confirm_density_60m` — how many previously announced actions of
//!   the SAME side sit within 60 bars of this one (`n - n_prev <= 59`).
//!   Measured over the first 100 sessions of the book, no `(session, bar, side)`
//!   key repeats, so this counts distinct earlier bars.
//!
//! ## Three columns are constants in the FROZEN book (measured, not predicted)
//!
//! Measured over all 41 shards / 773,661 actions:
//!
//! | quantity | measurement |
//! |---|---|
//! | `act_set_entry_price_u6_max - _min` | 0 on 773,661/773,661 rows, largest 0 u6 |
//! | `act_set_last_visibility_ns - _first` | 0 on 773,661/773,661 rows |
//!
//! So `envelope_width_bps`, `entry_price_spread_bps` and `visibility_span_ms`
//! all emit a constant 0.0 under the current action book: every action's
//! constituents share one entry price and one visibility instant. They are
//! computed, emitted and named honestly rather than dropped — the arithmetic is
//! correct and will carry real signal the moment the book records per-
//! constituent prices or instants — but a fit stage must treat them as
//! zero-variance today, and `b1_b2_contract.rs` asserts the degeneracy so a
//! book rebuild that ends it is visible instead of silent.
//!
//! ## `lag_bars` is `act_set_lag_median`
//!
//! The spine carries three lag fields (`act_set_lag_min`, `_median`, `_max`).
//! B1 reports the median as `lag_bars`, the representative of the three;
//! measured over all 773,661 book rows the median is 1 (354,797) or 2
//! (418,864), never the 0 the TOL2 contract also admits.
//!
//! ## Cost
//!
//! Per quote: one midpoint, two extreme compares, one bar-slot advance (a
//! division only when the wall-minute changes) and two bar min/max updates —
//! `O(1)`, roughly ten operations. Per cutoff: three bounded scans of at most
//! 30 bar slots and one 60-entry deque prune — `O(1)` with a small constant, no
//! term growing in the ~11-14M quotes of a session. Prints are not read.

use super::{AsOfRule, ColSpec, FamilyEmitter, FamilyRows, QuoteEvent, TradeEvent, Unit};
use crate::book::{ActionCutoff, Side};
use crate::error::{Result, SelectV2Error};

/// Registered name.
pub const NAME: &str = "b1_turn_geometry";

/// Milliseconds in one bar. The bar grid is absolute wall-minutes.
const MS_PER_BAR: i64 = 60_000;
/// Half-width of the retest band, in basis points.
const RETEST_BAND_BPS: i64 = 5;
/// Trailing window for `retest_count_30m` and `overshoot_bps`, in bars.
const WINDOW_30M_BARS: i64 = 30;
/// Trailing window for `same_side_confirm_density_60m`, in bars.
const WINDOW_60M_BARS: i64 = 60;
/// Bars a session can hold (390 full, 210 early close). Only a growth hint.
const MAX_BARS: usize = 512;

const COLUMNS: [ColSpec; 16] = [
    ColSpec::new("reversal_bps_n", Unit::Count, AsOfRule::BookSummaryAtCutoff),
    ColSpec::new("reversal_bps_min", Unit::Bps, AsOfRule::BookSummaryAtCutoff),
    ColSpec::new(
        "reversal_bps_median",
        Unit::Bps,
        AsOfRule::BookSummaryAtCutoff,
    ),
    ColSpec::new("reversal_bps_max", Unit::Bps, AsOfRule::BookSummaryAtCutoff),
    ColSpec::new("lag_bars", Unit::Bars, AsOfRule::BookSummaryAtCutoff),
    // bps per bar; `Unit` has no compound rate, and Bps is the magnitude.
    ColSpec::new(
        "confirm_velocity_bps_per_bar",
        Unit::Bps,
        AsOfRule::BookSummaryAtCutoff,
    ),
    ColSpec::new("overshoot_bps", Unit::Bps, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new(
        "envelope_width_bps",
        Unit::Bps,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "entry_price_spread_bps",
        Unit::Bps,
        AsOfRule::BookSummaryAtCutoff,
    ),
    ColSpec::new(
        "pivot_dist_from_session_extreme_bps",
        Unit::Bps,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "bars_since_session_extreme_same_side",
        Unit::Bars,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new("retest_count_30m", Unit::Count, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new(
        "same_side_confirm_density_60m",
        Unit::Count,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new(
        "opp_extreme_dist_bps",
        Unit::Bps,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new("constituents_n", Unit::Count, AsOfRule::BookSummaryAtCutoff),
    // `Unit` carries no millisecond variant; Seconds is its only duration kind
    // and the column name carries the scale. Measured over the whole book this
    // span is exactly 0 for all 773,661 actions (see
    // `ActionCutoff::visibility_span_ns`), so the column is a constant until
    // the book records per-constituent instants.
    ColSpec::new(
        "visibility_span_ms",
        Unit::Seconds,
        AsOfRule::BookSummaryAtCutoff,
    ),
];

/// One bar's observed midpoint range. An unseen bar keeps the inverted
/// sentinel, so [`Self::seen`] distinguishes ABSENT from a zero-width bar.
#[derive(Clone, Copy, Debug)]
struct BarMid {
    min: i64,
    max: i64,
}

impl BarMid {
    const EMPTY: Self = Self {
        min: i64::MAX,
        max: i64::MIN,
    };

    const fn seen(self) -> bool {
        self.min <= self.max
    }
}

/// A running session extreme and the bar it was last set in.
#[derive(Clone, Copy, Debug)]
struct Extreme {
    mid_u6: i64,
    bar_key: i64,
}

/// The 16-column turn-geometry emitter.
#[derive(Clone, Debug, Default)]
pub struct B1TurnGeometry {
    /// Bar key of `bars[0]`; `None` until the first quote arrives.
    base_key: Option<i64>,
    bars: Vec<BarMid>,
    /// Cached bar slot, so the wall-minute division runs once per minute.
    cur_slot: usize,
    cur_bar_end_ms: i64,
    last_mid_u6: Option<i64>,
    session_high: Option<Extreme>,
    session_low: Option<Extreme>,
    /// Bar ordinals of previously announced `HIGH`/`LOW` cutoffs, ascending,
    /// pruned to the trailing 60 bars.
    prior_high: Vec<i64>,
    prior_low: Vec<i64>,
    rows: Vec<f32>,
}

impl B1TurnGeometry {
    /// Bar slot for a quote, allocating forward. The division only runs when
    /// the wall-minute changes.
    fn slot_for_write(&mut self, ts_ms: i64) -> usize {
        if ts_ms < self.cur_bar_end_ms && self.base_key.is_some() {
            return self.cur_slot;
        }
        let key = ts_ms.div_euclid(MS_PER_BAR);
        let base = if let Some(base) = self.base_key {
            base
        } else {
            self.bars.reserve(MAX_BARS);
            self.base_key = Some(key);
            key
        };
        // A tape that ran backwards would underflow the slot; the merged pass
        // is non-decreasing, so clamp rather than invent a negative index.
        let slot = usize::try_from(key - base).unwrap_or(0);
        if slot >= self.bars.len() {
            self.bars.resize(slot + 1, BarMid::EMPTY);
        }
        self.cur_slot = slot;
        self.cur_bar_end_ms = (key + 1) * MS_PER_BAR;
        slot
    }

    /// Observed midpoint range of a bar key, or `None` when that bar is
    /// outside the session's observed span (ABSENT, not empty).
    fn bar_at(&self, key: i64) -> Option<BarMid> {
        let base = self.base_key?;
        let slot = usize::try_from(key - base).ok()?;
        let bar = *self.bars.get(slot)?;
        bar.seen().then_some(bar)
    }

    /// Same-side extreme of the midpoint over the trailing `WINDOW_30M_BARS`
    /// bars ending at `cutoff_key`.
    fn window_extreme(&self, cutoff_key: i64, side: Side) -> Option<i64> {
        let mut best: Option<i64> = None;
        for key in (cutoff_key - WINDOW_30M_BARS + 1)..=cutoff_key {
            let Some(bar) = self.bar_at(key) else { continue };
            let candidate = match side {
                Side::High => bar.max,
                Side::Low => bar.min,
            };
            best = Some(match (best, side) {
                (None, _) => candidate,
                (Some(current), Side::High) => current.max(candidate),
                (Some(current), Side::Low) => current.min(candidate),
            });
        }
        best
    }

    /// Bars in the trailing 30 whose midpoint range touches `extreme_u6` to
    /// within +/- 5bps.
    fn retest_count(&self, cutoff_key: i64, extreme_u6: i64) -> f32 {
        if extreme_u6 <= 0 {
            return f32::NAN;
        }
        // 5bps of a ~$200 midpoint is ~1e5 in u6; the product stays far inside
        // i64 and needs no float round trip.
        let tolerance = extreme_u6 * RETEST_BAND_BPS / 10_000;
        let (low, high) = (extreme_u6 - tolerance, extreme_u6 + tolerance);
        let mut count = 0_u32;
        for key in (cutoff_key - WINDOW_30M_BARS + 1)..=cutoff_key {
            let Some(bar) = self.bar_at(key) else { continue };
            if bar.min <= high && bar.max >= low {
                count += 1;
            }
        }
        f32::from(u16::try_from(count).unwrap_or(u16::MAX))
    }

    /// Prior same-side cutoffs inside the trailing 60 bars, then records this
    /// one. The deque is ascending, so the prune is a front trim.
    fn confirm_density(&mut self, ordinal: i64, side: Side) -> f32 {
        let prior = match side {
            Side::High => &mut self.prior_high,
            Side::Low => &mut self.prior_low,
        };
        let cutoff_key = ordinal - WINDOW_60M_BARS + 1;
        let keep = prior.partition_point(|earlier| *earlier < cutoff_key);
        prior.drain(..keep);
        let density = prior.len();
        prior.push(ordinal);
        f32::from(u16::try_from(density).unwrap_or(u16::MAX))
    }
}

impl FamilyEmitter for B1TurnGeometry {
    fn name(&self) -> &'static str {
        NAME
    }

    fn columns(&self) -> &[ColSpec] {
        &COLUMNS
    }

    fn on_quote(&mut self, quote: &QuoteEvent) {
        let mid = quote.mid_u6();
        let slot = self.slot_for_write(quote.ts_ms_b);
        let key = self.base_key.unwrap_or(0) + i64::try_from(slot).unwrap_or(0);
        let bar = &mut self.bars[slot];
        bar.min = bar.min.min(mid);
        bar.max = bar.max.max(mid);
        self.last_mid_u6 = Some(mid);
        match self.session_high {
            Some(current) if current.mid_u6 >= mid => {}
            _ => {
                self.session_high = Some(Extreme {
                    mid_u6: mid,
                    bar_key: key,
                });
            }
        }
        match self.session_low {
            Some(current) if current.mid_u6 <= mid => {}
            _ => {
                self.session_low = Some(Extreme {
                    mid_u6: mid,
                    bar_key: key,
                });
            }
        }
    }

    /// B1 is a quote-side family. Prints carry no turn geometry, and reading
    /// them would only add cost to the hottest loop in the pass.
    fn on_trade(&mut self, _trade: &TradeEvent) {}

    fn on_cutoff(&mut self, cutoff: &ActionCutoff) {
        let ordinal = i64::from(cutoff.cutoff_bar_ordinal);
        // The cutoff is the CLOSE of bar `ordinal`, so the last complete bar is
        // the wall-minute immediately before the cutoff instant.
        let cutoff_key = cutoff.cutoff_ns_b.div_euclid(1_000_000).div_euclid(MS_PER_BAR) - 1;
        let (same, opposite) = match cutoff.side {
            Side::High => (self.session_high, self.session_low),
            Side::Low => (self.session_low, self.session_high),
        };
        let mid = self.last_mid_u6;
        let act = cutoff.act_set;

        // Every read of `self` happens before the row is appended, so the whole
        // row is a pure function of state that predates the cutoff.
        let window_extreme = self.window_extreme(cutoff_key, cutoff.side);
        let retest = same.map_or(f32::NAN, |extreme| {
            self.retest_count(cutoff_key, extreme.mid_u6)
        });
        let density = self.confirm_density(ordinal, cutoff.side);
        let envelope = match (act.entry_price_u6_max, act.entry_price_u6_min) {
            (Some(high), Some(low)) => Some(high - low),
            _ => None,
        };

        let values = [
            // -- the action's own constituent summary -----------------------
            opt(act.reversal_bps_n),
            opt(act.reversal_bps_min),
            opt(act.reversal_bps_median),
            opt(act.reversal_bps_max),
            opt(act.lag_median),
            // Confirmation velocity: the median reversal spread over the bars
            // it took to confirm. A lag of 0 (admitted by TOL2, absent from
            // this book) would divide by zero, so the divisor floors at one.
            match (act.reversal_bps_median, act.lag_median) {
                (Some(reversal), Some(lag)) => finite(as_f64(reversal) / as_f64(lag.max(1))),
                _ => f32::NAN,
            },
            // -- bar geometry ------------------------------------------------
            match (window_extreme, mid) {
                (Some(extreme), Some(mid)) => bps(signed_gap(extreme, mid, cutoff.side), mid),
                _ => f32::NAN,
            },
            match (envelope, mid) {
                (Some(width), Some(mid)) => bps(width, mid),
                _ => f32::NAN,
            },
            match (envelope, act.entry_price_u6_median) {
                (Some(width), Some(median)) => bps(width, median),
                _ => f32::NAN,
            },
            match (same, mid) {
                (Some(extreme), Some(mid)) => bps((extreme.mid_u6 - mid).abs(), mid),
                _ => f32::NAN,
            },
            same.map_or(f32::NAN, |extreme| {
                finite(as_f64(cutoff_key - extreme.bar_key))
            }),
            retest,
            density,
            match (opposite, mid) {
                (Some(extreme), Some(mid)) => bps((extreme.mid_u6 - mid).abs(), mid),
                _ => f32::NAN,
            },
            // -- summary tail -------------------------------------------------
            opt(act.n_constituents),
            finite(as_f64(cutoff.visibility_span_ns()) / 1_000_000.0),
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

/// Distance from the midpoint out to a same-side extreme, signed so that a
/// positive value always means "the extreme is further out than here".
const fn signed_gap(extreme_u6: i64, mid_u6: i64, side: Side) -> i64 {
    match side {
        Side::High => extreme_u6 - mid_u6,
        Side::Low => mid_u6 - extreme_u6,
    }
}

/// `delta / reference` in basis points. A non-positive reference is an
/// undefined ratio, reported as ABSENT rather than as an infinity.
fn bps(delta_u6: i64, reference_u6: i64) -> f32 {
    if reference_u6 <= 0 {
        return f32::NAN;
    }
    finite(as_f64(delta_u6) / as_f64(reference_u6) * 10_000.0)
}

/// An absent book cell stays absent in the leaf.
fn opt(value: Option<i64>) -> f32 {
    value.map_or(f32::NAN, |value| finite(as_f64(value)))
}

/// The one narrowing site, and the structural guard that no `+/-inf` can leave
/// this family: a non-finite `f64` becomes `NaN`, which downstream reads as
/// absent.
#[allow(clippy::cast_possible_truncation)]
fn finite(value: f64) -> f32 {
    if value.is_finite() {
        value as f32
    } else {
        f32::NAN
    }
}

/// u6 magnitudes are ~2e8 and counts are ~1e3; both are exact in `f64`.
#[allow(clippy::cast_precision_loss)]
const fn as_f64(value: i64) -> f64 {
    value as f64
}

#[cfg(test)]
mod tests {
    use super::{B1TurnGeometry, COLUMNS, NAME};
    use crate::book::{ActSetSummary, ActionCutoff, Side};
    use crate::calendar;
    use crate::families::{FamilyEmitter, QuoteEvent};

    const DAY: &str = "2022-03-01";
    /// A ~$200 book, one cent wide, so every hand-checked basis point below is
    /// a round number of u6 over `200_010_000`.
    const BID: i64 = 200_000_000;
    const ASK: i64 = 200_020_000;

    fn act_set() -> ActSetSummary {
        ActSetSummary {
            n_constituents: Some(40),
            lag_min: Some(1),
            lag_median: Some(2),
            lag_max: Some(2),
            reversal_bps_n: Some(40),
            reversal_bps_min: Some(1),
            reversal_bps_median: Some(6),
            reversal_bps_max: Some(20),
            entry_price_u6_min: Some(200_000_000),
            entry_price_u6_median: Some(200_050_000),
            entry_price_u6_max: Some(200_100_000),
        }
    }

    /// A cutoff on a REAL registered session, so the frame-B instant is the one
    /// the book would carry.
    fn cutoff(bar_ordinal: i32, side: Side, act: ActSetSummary) -> ActionCutoff {
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
            first_visibility_ns: 1_646_000_000_000_000_000,
            last_visibility_ns: 1_646_000_000_000_000_000,
            act_set: act,
        }
    }

    /// A quote `offset_ms` after this session's frame-B open.
    fn quote(offset_ms: i64, bid_u6: i64, ask_u6: i64) -> QuoteEvent {
        let scope = calendar::admit(DAY).expect("registered session");
        QuoteEvent {
            ts_ms_b: scope.open_ms_b() + offset_ms,
            bid_u6,
            ask_u6,
            bid_shares: 500,
            ask_shares: 500,
        }
    }

    fn row(values: &[f32], index: usize) -> &[f32] {
        &values[index * COLUMNS.len()..(index + 1) * COLUMNS.len()]
    }

    fn near(got: f32, want: f32, what: &str) {
        assert!(
            (got - want).abs() < 1e-3,
            "{what}: got {got}, want {want}"
        );
    }

    #[test]
    fn the_family_declares_its_sixteen_columns_in_order() {
        let family = B1TurnGeometry::default();
        assert_eq!(family.name(), NAME);
        let names: Vec<&str> = family.columns().iter().map(|spec| spec.name).collect();
        assert_eq!(
            names,
            vec![
                "reversal_bps_n",
                "reversal_bps_min",
                "reversal_bps_median",
                "reversal_bps_max",
                "lag_bars",
                "confirm_velocity_bps_per_bar",
                "overshoot_bps",
                "envelope_width_bps",
                "entry_price_spread_bps",
                "pivot_dist_from_session_extreme_bps",
                "bars_since_session_extreme_same_side",
                "retest_count_30m",
                "same_side_confirm_density_60m",
                "opp_extreme_dist_bps",
                "constituents_n",
                "visibility_span_ms",
            ]
        );
        assert!(
            !names.iter().any(|name| name.starts_with("d1_")
                || name.starts_with("d2_")
                || name.starts_with("d3_")),
            "F-18 deleted the slot-reachability columns"
        );
    }

    /// Four bars, each one quote, hand-computed end to end.
    ///
    /// ```text
    /// bar 1  mid 200_010_000
    /// bar 2  mid 200_110_000   <- session HIGH
    /// bar 3  mid 199_910_000   <- session LOW
    /// bar 4  mid 200_010_000   <- midpoint at the cutoff
    /// ```
    #[test]
    fn a_four_bar_tape_produces_hand_checked_geometry() {
        let mut family = B1TurnGeometry::default();
        family.on_quote(&quote(0, BID, ASK));
        family.on_quote(&quote(60_000, BID + 100_000, ASK + 100_000));
        family.on_quote(&quote(120_000, BID - 100_000, ASK - 100_000));
        family.on_quote(&quote(180_000, BID, ASK));
        let action = cutoff(4, Side::High, act_set());
        family.on_cutoff(&action);
        let rows = family.emit(std::slice::from_ref(&action)).expect("emit");
        assert_eq!(rows.rows(), 1);
        let values = row(&rows.values, 0);

        near(values[0], 40.0, "reversal_bps_n");
        near(values[1], 1.0, "reversal_bps_min");
        near(values[2], 6.0, "reversal_bps_median");
        near(values[3], 20.0, "reversal_bps_max");
        near(values[4], 2.0, "lag_bars = act_set_lag_median");
        // 6 bps of reversal confirmed over 2 bars.
        near(values[5], 3.0, "confirm_velocity_bps_per_bar");
        // The 30-bar window holds every bar, so the window HIGH is the session
        // HIGH: (200_110_000 - 200_010_000) / 200_010_000 * 1e4.
        near(values[6], 4.999_75, "overshoot_bps");
        // 100_000 u6 of entry envelope over the cutoff midpoint...
        near(values[7], 4.999_75, "envelope_width_bps");
        // ...and over the action's own median entry price.
        near(values[8], 4.998_75, "entry_price_spread_bps");
        near(values[9], 4.999_75, "pivot_dist_from_session_extreme_bps");
        // HIGH was set in bar 2; the cutoff closes bar 4.
        near(values[10], 2.0, "bars_since_session_extreme_same_side");
        // Band is 200_110_000 +/- 100_055 = [200_009_945, 200_210_055].
        // Bars 1, 2 and 4 fall inside it; bar 3 (199_910_000) does not.
        near(values[11], 3.0, "retest_count_30m");
        near(values[12], 0.0, "same_side_confirm_density_60m");
        near(values[13], 4.999_75, "opp_extreme_dist_bps");
        near(values[14], 40.0, "constituents_n");
        // Measured across the whole book: first and last visibility coincide.
        near(values[15], 0.0, "visibility_span_ms");
        assert!(
            values.iter().all(|value| value.is_finite()),
            "no column may be +/-inf: {values:?}"
        );
    }

    /// The `LOW` machine is the mirror image, and the opposite extreme swaps.
    #[test]
    fn the_low_side_mirrors_the_high_side() {
        let mut family = B1TurnGeometry::default();
        family.on_quote(&quote(0, BID, ASK));
        family.on_quote(&quote(60_000, BID + 100_000, ASK + 100_000));
        family.on_quote(&quote(120_000, BID - 100_000, ASK - 100_000));
        family.on_quote(&quote(180_000, BID, ASK));
        let action = cutoff(4, Side::Low, act_set());
        family.on_cutoff(&action);
        let rows = family.emit(std::slice::from_ref(&action)).expect("emit");
        let values = row(&rows.values, 0);
        // Same-side is now the LOW at bar 3, one bar before the cutoff bar.
        near(values[10], 1.0, "bars_since_session_extreme_same_side");
        near(values[9], 4.999_75, "pivot_dist_from_session_extreme_bps");
        near(values[13], 4.999_75, "opp_extreme_dist_bps");
        // Band around 199_910_000 is +/- 99_955 = [199_810_045, 200_009_955];
        // bars 1 and 4 sit at 200_010_000, 45 u6 above the top of the band, so
        // only bar 3 retests.
        near(values[11], 1.0, "retest_count_30m");
    }

    /// Density counts earlier SAME-side actions inside the trailing 60 bars,
    /// and nothing else. The window is `n - n_prev <= 59`, so this walks the
    /// boundary from both sides: 59 bars back is inside it, 60 bars back is
    /// not, and the interleaved `LOW` action is never counted at all.
    #[test]
    fn confirm_density_counts_only_prior_same_side_actions_in_the_window() {
        let mut family = B1TurnGeometry::default();
        family.on_quote(&quote(0, BID, ASK));
        let first = cutoff(1, Side::High, act_set());
        let other = cutoff(2, Side::Low, act_set());
        // 59 bars after bar 1 -- the last ordinal still inside the window.
        let at_edge = cutoff(60, Side::High, act_set());
        // 60 bars after bar 1, so bar 1 falls out and only bar 60 remains.
        let past_edge = cutoff(61, Side::High, act_set());
        // 69 bars after bar 61: every earlier HIGH is now outside.
        let far = cutoff(130, Side::High, act_set());
        for action in [&first, &other, &at_edge, &past_edge, &far] {
            family.on_cutoff(action);
        }
        let actions = vec![first, other, at_edge, past_edge, far];
        let rows = family.emit(&actions).expect("emit");
        assert_eq!(rows.rows(), 5);
        near(row(&rows.values, 0)[12], 0.0, "the first HIGH has no history");
        near(row(&rows.values, 1)[12], 0.0, "the LOW has no prior LOW");
        near(row(&rows.values, 2)[12], 1.0, "bar 60 still sees bar 1 at 59 back");
        near(row(&rows.values, 3)[12], 1.0, "bar 61 drops bar 1 and keeps bar 60");
        near(row(&rows.values, 4)[12], 0.0, "bar 130 sees no HIGH inside 60 bars");
    }

    /// Absence is not zero: with no tape and no book summary every column is
    /// `NaN`, and none of them is an infinity.
    #[test]
    fn an_empty_tape_and_an_empty_summary_are_absent_not_zero() {
        let mut family = B1TurnGeometry::default();
        let action = cutoff(30, Side::High, ActSetSummary::default());
        family.on_cutoff(&action);
        let rows = family.emit(std::slice::from_ref(&action)).expect("emit");
        let values = row(&rows.values, 0);
        for (index, value) in values.iter().enumerate() {
            if index == 12 {
                // Density is an observed count over announced actions, which is
                // genuinely zero here rather than absent.
                near(*value, 0.0, "same_side_confirm_density_60m");
                continue;
            }
            if index == 15 {
                // Visibility span is a book difference, defined even when the
                // summary is empty.
                near(*value, 0.0, "visibility_span_ms");
                continue;
            }
            assert!(value.is_nan(), "column {index} should be absent, got {value}");
        }
    }

    /// A degenerate zero book would divide by zero. The guard turns that into
    /// absence, never `+/-inf`, which is what the integration test asserts over
    /// a real session.
    #[test]
    fn a_zero_reference_price_yields_absence_not_infinity() {
        let mut family = B1TurnGeometry::default();
        family.on_quote(&quote(0, 0, 0));
        let action = cutoff(1, Side::High, act_set());
        family.on_cutoff(&action);
        let rows = family.emit(std::slice::from_ref(&action)).expect("emit");
        let values = row(&rows.values, 0);
        assert!(values[6].is_nan(), "overshoot_bps over a zero mid");
        assert!(values[7].is_nan(), "envelope_width_bps over a zero mid");
        assert!(values[9].is_nan(), "pivot_dist over a zero mid");
        assert!(
            values.iter().all(|value| !value.is_infinite()),
            "no column may be +/-inf: {values:?}"
        );
    }

    /// The width contract: a row per announced cutoff, refused otherwise.
    #[test]
    fn emit_refuses_a_row_count_that_disagrees_with_the_cutoff_list() {
        let mut family = B1TurnGeometry::default();
        let action = cutoff(1, Side::High, act_set());
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
