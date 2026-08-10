//! `a1_clock` — the 12 calendar/clock columns (plan Part V, A1).
//!
//! Every column here is a function of two things the action book already
//! carries: the action's `cutoff_bar_ordinal` and its civil `day`. Nothing is
//! read from the tape, which is why the family's [`AsOfRule`] is
//! [`AsOfRule::BookSummaryAtCutoff`] throughout — there is no instant at which
//! it *could* see post-cutoff data.
//!
//! ## Three conventions, stated once
//!
//! * **`minute_of_session` is the cutoff's own bar ordinal.** The book's
//!   ordinal is 1-based and the cutoff is that bar's *close*, so ordinal `k`
//!   means "exactly `k` minutes have elapsed since the 09:30 open". The value
//!   is therefore minutes-since-open at the as-of instant, not a bar index.
//! * **The sin/cos phase is normalized by the session's TRUE width**, taken
//!   from that session's own registry row (390 bars normally, 210 on the nine
//!   early closes) — never a 390 constant. The phase is consequently
//!   *fraction of session elapsed*, so 13:00 on a half day and 16:00 on a full
//!   day share a phase; `early_close_flag` is what separates them, and
//!   `bars_to_close` carries the absolute remaining width.
//! * **The weekday and the OPEX week come from the day string alone.**
//!   `corpus::CivilDate` is the workspace's one civil-calendar authority, so
//!   the Unix day ordinal it produces is what the weekday is derived from; no
//!   second date arithmetic is introduced here. 1970-01-01 was a Thursday,
//!   which pins `(ordinal + 3) mod 7 == 0` to Monday.
//!
//! ## Divergence from the plan's prose, flagged
//!
//! Plan Part V line 161 lists "OPEX week/day flags" and "days-since-year-start"
//! for a 12-wide A1. The 12 columns enumerated in this lane's specification
//! carry the OPEX *week* flag only and no day-of-year column, and 12 is what
//! the enumeration sums to. This file implements the enumeration; the two
//! prose extras are absent, not silently folded into another column.

use super::{AsOfRule, ColSpec, FamilyEmitter, FamilyRows, QuoteEvent, TradeEvent, Unit};
use crate::book::ActionCutoff;
use crate::calendar;
use crate::error::{Result, SelectV2Error};
use std::f64::consts::TAU;

/// Registered name.
pub const NAME: &str = "a1_clock";

/// Months in the seasonal cycle the month sin/cos wrap.
const MONTHS_IN_YEAR: i64 = 12;

/// Registered width of a non-shortened session, in 1-minute bars. Used ONLY to
/// name the early-close flag's threshold; the phase denominator is always the
/// session's own registry width.
const FULL_SESSION_BARS: i64 = 390;

/// Weekday index of 1970-01-01 (a Thursday) under a Monday-0 convention.
const EPOCH_WEEKDAY_MONDAY_ZERO: i64 = 3;

/// Monday-0 index of Friday.
const FRIDAY: i64 = 4;

/// The 12 columns, in emission order.
const COLUMNS: [ColSpec; 12] = [
    ColSpec::new(
        "minute_of_session",
        Unit::Bars,
        AsOfRule::BookSummaryAtCutoff,
    ),
    ColSpec::new("sin_minute", Unit::Ratio, AsOfRule::BookSummaryAtCutoff),
    ColSpec::new("cos_minute", Unit::Ratio, AsOfRule::BookSummaryAtCutoff),
    ColSpec::new("bars_to_close", Unit::Bars, AsOfRule::BookSummaryAtCutoff),
    ColSpec::new("early_close_flag", Unit::Flag, AsOfRule::BookSummaryAtCutoff),
    ColSpec::new("dow_mon", Unit::Flag, AsOfRule::BookSummaryAtCutoff),
    ColSpec::new("dow_tue", Unit::Flag, AsOfRule::BookSummaryAtCutoff),
    ColSpec::new("dow_wed", Unit::Flag, AsOfRule::BookSummaryAtCutoff),
    ColSpec::new("dow_thu", Unit::Flag, AsOfRule::BookSummaryAtCutoff),
    ColSpec::new("month_sin", Unit::Ratio, AsOfRule::BookSummaryAtCutoff),
    ColSpec::new("month_cos", Unit::Ratio, AsOfRule::BookSummaryAtCutoff),
    ColSpec::new("opex_week_flag", Unit::Flag, AsOfRule::BookSummaryAtCutoff),
];

/// The per-session constants A1 needs, resolved once from the first cutoff.
#[derive(Clone, Copy, Debug)]
struct SessionCalendar {
    /// This session's registered width in 1-minute bars (390, or 210 on an
    /// early close). Registry-sourced, never a caller's constant.
    bar_count: i64,
    /// Monday-0 weekday.
    weekday: i64,
    /// 1-based Gregorian month.
    month: i64,
    /// The civil day falls in the Mon-Fri week of the month's third Friday.
    opex_week: bool,
}

impl SessionCalendar {
    /// Resolves the session's calendar facts from the cutoff's own identity.
    ///
    /// The bar count comes from the frozen registry row the book row already
    /// agreed with; the day fields come from `corpus::CivilDate`.
    fn resolve(cutoff: &ActionCutoff) -> Result<Self> {
        let ordinal = usize::try_from(cutoff.session_ordinal).map_err(|_| {
            SelectV2Error::Config(format!(
                "{}: session ordinal {} is not addressable",
                cutoff.action_id, cutoff.session_ordinal
            ))
        })?;
        let entry =
            calendar::sessions()
                .get(ordinal)
                .ok_or_else(|| SelectV2Error::DayOutsideCalendar {
                    day: format!("#{ordinal}"),
                    detail: "ordinal past the 1,003-session calendar",
                })?;
        if entry.day != cutoff.day {
            return Err(SelectV2Error::ContentMismatch {
                path: std::path::PathBuf::from(NAME),
                detail: format!(
                    "cutoff {} says ordinal {ordinal} is {}, registry says {}",
                    cutoff.action_id, cutoff.day, entry.day
                ),
            });
        }
        let date = corpus::CivilDate::parse(cutoff.day)?;
        let (_, month, day_of_month) = date.components();
        let day_ordinal = date.unix_day_ordinal();
        let weekday = (day_ordinal + EPOCH_WEEKDAY_MONDAY_ZERO).rem_euclid(7);
        Ok(Self {
            bar_count: i64::from(entry.expected_bar_count),
            weekday,
            month: i64::from(month),
            opex_week: opex_week(day_ordinal, i64::from(day_of_month)),
        })
    }
}

/// Whether `day_of_month` sits in the Mon-Fri week of its month's third
/// Friday. `day_ordinal` is the same day's Unix day ordinal, which is what
/// fixes the weekday of the 1st.
fn opex_week(day_ordinal: i64, day_of_month: i64) -> bool {
    let first_of_month = day_ordinal - (day_of_month - 1);
    let weekday_of_first = (first_of_month + EPOCH_WEEKDAY_MONDAY_ZERO).rem_euclid(7);
    let first_friday = 1 + (FRIDAY - weekday_of_first).rem_euclid(7);
    let third_friday = first_friday + 14;
    day_of_month >= third_friday - 4 && day_of_month <= third_friday
}

/// The clock family. Holds one session's calendar facts and one row per
/// announced cutoff.
#[derive(Clone, Debug)]
pub struct A1Clock {
    session: Option<SessionCalendar>,
    /// The first refusal met while resolving the session, surfaced by
    /// [`FamilyEmitter::emit`] rather than swallowed at `on_cutoff`, whose
    /// signature cannot return.
    refusal: Option<String>,
    rows: Vec<f32>,
}

impl Default for A1Clock {
    fn default() -> Self {
        Self::new()
    }
}

/// Value-namespace constructor for `families::build`, which currently spells
/// the family as the unit-struct expression `Box::new(a1_clock::A1Clock)`.
/// `mod.rs` belongs to another lane, so the emitter supplies the value that
/// expression needs rather than forcing an edit there. Once `build` says
/// `A1Clock::default()`, delete this const.
#[allow(non_upper_case_globals)]
pub const A1Clock: A1Clock = A1Clock::new();

impl A1Clock {
    /// A fresh emitter for one session.
    #[must_use]
    pub const fn new() -> Self {
        Self {
            session: None,
            refusal: None,
            rows: Vec::new(),
        }
    }

    /// Resolves (once) and returns this session's calendar facts.
    fn session_for(&mut self, cutoff: &ActionCutoff) -> Option<SessionCalendar> {
        if let Some(session) = self.session {
            return Some(session);
        }
        if self.refusal.is_some() {
            return None;
        }
        match SessionCalendar::resolve(cutoff) {
            Ok(session) => {
                self.session = Some(session);
                Some(session)
            }
            Err(error) => {
                self.refusal = Some(error.to_string());
                None
            }
        }
    }
}

impl FamilyEmitter for A1Clock {
    fn name(&self) -> &'static str {
        NAME
    }

    fn columns(&self) -> &[ColSpec] {
        &COLUMNS
    }

    fn on_quote(&mut self, _quote: &QuoteEvent) {}

    fn on_trade(&mut self, _trade: &TradeEvent) {}

    fn on_cutoff(&mut self, cutoff: &ActionCutoff) {
        let Some(session) = self.session_for(cutoff) else {
            // The session could not be resolved; the row is typed absence and
            // `emit` will refuse with the recorded reason.
            self.rows.extend_from_slice(&[f32::NAN; COLUMNS.len()]);
            return;
        };
        let minute = i64::from(cutoff.cutoff_bar_ordinal);
        // Fraction of THIS session elapsed, not of a 390-bar constant.
        let phase = TAU * ratio(minute, session.bar_count);
        let month_phase = TAU * ratio(session.month - 1, MONTHS_IN_YEAR);
        self.rows.extend_from_slice(&[
            whole(minute),
            finite(phase.sin()),
            finite(phase.cos()),
            whole(session.bar_count - minute),
            flag(session.bar_count < FULL_SESSION_BARS),
            flag(session.weekday == 0),
            flag(session.weekday == 1),
            flag(session.weekday == 2),
            flag(session.weekday == 3),
            finite(month_phase.sin()),
            finite(month_phase.cos()),
            flag(session.opex_week),
        ]);
    }

    fn emit(&mut self, cutoffs: &[ActionCutoff]) -> Result<FamilyRows> {
        if let Some(detail) = self.refusal.take() {
            return Err(SelectV2Error::ContentMismatch {
                path: std::path::PathBuf::from(NAME),
                detail,
            });
        }
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

/// `numerator / denominator` as `f64`; `0.0` when the denominator is zero,
/// which the registry makes impossible for a real session.
fn ratio(numerator: i64, denominator: i64) -> f64 {
    if denominator == 0 {
        return 0.0;
    }
    // Bar ordinals and months are small integers; the f64 images are exact.
    #[allow(clippy::cast_precision_loss)]
    {
        numerator as f64 / denominator as f64
    }
}

/// A small integer as `f32`. Bar ordinals are at most 390, far inside the
/// 24-bit mantissa, so the image is exact.
#[allow(clippy::cast_precision_loss)]
fn whole(value: i64) -> f32 {
    value as f32
}

/// `1.0` / `0.0` — a one-hot or boolean flag column.
fn flag(value: bool) -> f32 {
    if value { 1.0 } else { 0.0 }
}

/// Narrows to the emitted `f32`, mapping any non-finite intermediate to NaN so
/// no +/-inf can ever leave the family. Sin/cos are bounded by construction;
/// the guard is a structural one, not a hope.
#[allow(clippy::cast_possible_truncation)]
fn finite(value: f64) -> f32 {
    if value.is_finite() {
        value as f32
    } else {
        f32::NAN
    }
}

#[cfg(test)]
mod tests {
    use super::{A1Clock, COLUMNS, NAME, opex_week};
    use crate::book::{ActionCutoff, Side};
    use crate::calendar;
    use crate::families::FamilyEmitter;

    /// Builds a cutoff for a REAL registered session through the production
    /// calendar, so the cutoff instants are the ones the book would carry.
    fn cutoff_for(day: &str, bar_ordinal: i32, side: Side) -> ActionCutoff {
        let scope = calendar::admit(day).expect("registered session");
        let ordinal = i64::from(bar_ordinal);
        ActionCutoff {
            action_id: format!("{day}-{bar_ordinal}-{side:?}"),
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

    fn row(values: &[f32], index: usize) -> &[f32] {
        &values[index * COLUMNS.len()..(index + 1) * COLUMNS.len()]
    }

    #[test]
    fn column_names_and_width_are_the_declared_twelve() {
        let family = A1Clock::default();
        assert_eq!(family.name(), NAME);
        let names: Vec<&str> = family.columns().iter().map(|spec| spec.name).collect();
        assert_eq!(
            names,
            vec![
                "minute_of_session",
                "sin_minute",
                "cos_minute",
                "bars_to_close",
                "early_close_flag",
                "dow_mon",
                "dow_tue",
                "dow_wed",
                "dow_thu",
                "month_sin",
                "month_cos",
                "opex_week_flag",
            ]
        );
        assert_eq!(family.columns().len(), 12);
    }

    #[test]
    fn a_full_session_row_carries_the_measured_weekday_and_width() {
        // 2022-03-01 is a Tuesday, a 390-bar session, and NOT an OPEX week
        // (March 2022's third Friday is the 18th).
        let cutoffs = [cutoff_for("2022-03-01", 90, Side::High)];
        let mut family = A1Clock::default();
        family.on_cutoff(&cutoffs[0]);
        let rows = family.emit(&cutoffs).expect("emit");
        assert_eq!(rows.rows(), 1);
        let values = row(&rows.values, 0);
        assert!((values[0] - 90.0).abs() < 1e-6, "minute_of_session");
        assert!((values[3] - 300.0).abs() < 1e-6, "bars_to_close = 390 - 90");
        assert!((values[4] - 0.0).abs() < 1e-6, "not an early close");
        assert!((values[5] - 0.0).abs() < 1e-6, "not Monday");
        assert!((values[6] - 1.0).abs() < 1e-6, "Tuesday");
        assert!((values[11] - 0.0).abs() < 1e-6, "not OPEX week");
        // Phase is 2*pi*90/390 of the session's own width.
        let expected = std::f64::consts::TAU * 90.0 / 390.0;
        assert!((f64::from(values[1]) - expected.sin()).abs() < 1e-6);
        assert!((f64::from(values[2]) - expected.cos()).abs() < 1e-6);
    }

    #[test]
    fn an_early_close_normalizes_by_its_own_width_and_flags_itself() {
        // 2022-11-25 is one of the nine 210-bar early closes; it is also a
        // Friday, so every day-of-week one-hot is zero.
        let scope = calendar::admit("2022-11-25").expect("registered");
        assert_eq!(scope.bar_count(), 210, "fixture assumes the early close");
        let cutoffs = [cutoff_for("2022-11-25", 105, Side::Low)];
        let mut family = A1Clock::default();
        family.on_cutoff(&cutoffs[0]);
        let rows = family.emit(&cutoffs).expect("emit");
        let values = row(&rows.values, 0);
        assert!((values[3] - 105.0).abs() < 1e-6, "bars_to_close = 210 - 105");
        assert!((values[4] - 1.0).abs() < 1e-6, "early_close_flag");
        for (index, name) in ["dow_mon", "dow_tue", "dow_wed", "dow_thu"]
            .iter()
            .enumerate()
        {
            assert!(
                (values[5 + index] - 0.0).abs() < 1e-6,
                "Friday must leave {name} at zero"
            );
        }
        // Half of a 210-bar session is phase pi: sin ~ 0, cos ~ -1.
        assert!(f64::from(values[1]).abs() < 1e-6, "sin(pi)");
        assert!((f64::from(values[2]) + 1.0).abs() < 1e-6, "cos(pi)");
    }

    #[test]
    fn opex_week_is_the_third_fridays_monday_through_friday() {
        // March 2022: 1st is a Tuesday, first Friday the 4th, third the 18th.
        let ordinal_of_first = corpus::CivilDate::parse("2022-03-01")
            .expect("valid")
            .unix_day_ordinal();
        assert!(!opex_week(ordinal_of_first + 12, 13), "Sunday the 13th");
        assert!(opex_week(ordinal_of_first + 13, 14), "Monday the 14th");
        assert!(opex_week(ordinal_of_first + 17, 18), "Friday the 18th");
        assert!(!opex_week(ordinal_of_first + 18, 19), "Saturday the 19th");
        // May 2022: 1st is a Sunday, first Friday the 6th, third the 20th.
        let may_first = corpus::CivilDate::parse("2022-05-01")
            .expect("valid")
            .unix_day_ordinal();
        assert!(!opex_week(may_first + 12, 13), "Friday the 13th is week two");
        assert!(opex_week(may_first + 15, 16), "Monday the 16th");
        assert!(opex_week(may_first + 19, 20), "Friday the 20th");
    }

    #[test]
    fn month_phase_wraps_the_calendar_year() {
        let january = cutoff_for("2022-01-03", 1, Side::High);
        let july = cutoff_for("2022-07-01", 1, Side::High);
        let mut first = A1Clock::default();
        first.on_cutoff(&january);
        let january_rows = first.emit(std::slice::from_ref(&january)).expect("emit");
        let mut second = A1Clock::default();
        second.on_cutoff(&july);
        let july_rows = second.emit(std::slice::from_ref(&july)).expect("emit");
        // January is phase 0; July is phase pi, i.e. the opposite point.
        assert!(january_rows.values[9].abs() < 1e-6, "sin(0)");
        assert!((january_rows.values[10] - 1.0).abs() < 1e-6, "cos(0)");
        assert!(july_rows.values[9].abs() < 1e-6, "sin(pi)");
        assert!((july_rows.values[10] + 1.0).abs() < 1e-6, "cos(pi)");
    }

    #[test]
    fn every_announced_cutoff_gets_exactly_one_finite_row() {
        let cutoffs: Vec<ActionCutoff> = (1..=32)
            .map(|bar| {
                cutoff_for(
                    "2022-03-01",
                    bar,
                    if bar % 2 == 0 { Side::High } else { Side::Low },
                )
            })
            .collect();
        let mut family = A1Clock::default();
        for cutoff in &cutoffs {
            family.on_cutoff(cutoff);
        }
        let rows = family.emit(&cutoffs).expect("emit");
        assert_eq!(rows.rows(), cutoffs.len());
        assert_eq!(rows.columns, COLUMNS.len());
        assert!(
            rows.values.iter().all(|value| value.is_finite()),
            "A1 reads no tape, so no column can be absent or infinite"
        );
    }

    #[test]
    fn a_row_count_that_disagrees_with_the_cutoff_list_refuses() {
        let cutoffs = [cutoff_for("2022-03-01", 5, Side::High)];
        let mut family = A1Clock::default();
        // Never announced: emit must refuse rather than pad.
        assert!(family.emit(&cutoffs).is_err());
    }
}
