//! **THE ONE CLOCK BOUNDARY** — the typed session clock every frame-B to
//! frame-A conversion in this workspace goes through (R-HALT-44 items 1, 4,
//! 5 and 6(a)/(b)).
//!
//! # Why this type exists
//!
//! R-HALT-42 was a timezone P0: a naive-ET wall-clock tape
//! ([`FrameB`]) was binary-searched against a true-UTC-epoch cutoff
//! ([`FrameA`]). Both are `i64` nanoseconds, so the comparison type-checked,
//! hashed cleanly, and moved every entry fill 4-5 hours into the FUTURE of
//! its own decision instant. Row counts, schemas and shas cannot see a defect
//! of this class.
//!
//! R-HALT-44 adopted architecture (b): the shared raw decoder and its RTH
//! window stay in FRAME B — that is the native frame of all six token
//! corpora and of four already-correct pipelines — and the retained tape is
//! converted to FRAME A **exactly once**, at one boundary, immediately before
//! the entry-quote index is built.
//!
//! # The registry is the only clock authority
//!
//! There is no DST calculation here. The authenticated
//! [`RegistryEntry`] already carries the true-UTC image of the same 09:30 ET
//! anchor (`session_start_ns`), so the sole conversion is
//!
//! ```text
//! ts_A = session_start_ns + (ts_B - open_B)
//! ```
//!
//! exact and checked, and it CANNOT disagree with [`crate::load_session`],
//! which is built on this same primitive. A second clock authority (an
//! Energy-Policy-Act DST table) is precisely what this type removes.
//!
//! # `expected_bar_count` is derived INSIDE
//!
//! Nine pinned sessions are 210-bar early closes and 994 are 390-bar. The
//! width is read from the session's own registry row here and a caller's
//! value is never accepted — an early close that inherits a 390-bar window
//! admits 180 minutes of post-close tape as decision-time quotes.
//!
//! # The six fail-closed boundary conditions
//!
//! [`SessionClock::convert_sequence`] refuses unless ALL of:
//!
//! 1. the clock's day is the requested day;
//! 2. `session_end_ns - session_start_ns == expected_bar_count * BAR_NS`
//!    (checked at construction);
//! 3. every retained `ts_B` lies in the half-open frame-B session window;
//! 4. every converted `ts_A` lies in `[session_start_ns, session_end_ns)`;
//! 5. `ts_A - session_start_ns == ts_B - open_B` exactly, under CHECKED
//!    integer arithmetic;
//! 6. conversion preserves row count, sequence, and timestamp order.
//!
//! Every one of these is a refusal, never a clamp: R-HALT-44(a) (the firing
//! law) BANS saturating or clamping arithmetic in any comparison a guard
//! depends on, because twice in this rebuild a clamp turned the target defect
//! into silence.

use crate::error::{CorpusError, Result};
use crate::registry::{self, RegistryEntry};

/// One RTH bar, in nanoseconds.
pub const BAR_NS: i64 = 60_000_000_000;
/// Nanoseconds per millisecond — the raw tape is stamped in ms.
pub const NANOSECONDS_PER_MILLISECOND: i64 = 1_000_000;
/// Nanoseconds per microsecond.
pub const NANOSECONDS_PER_MICROSECOND: i64 = 1_000;
/// Milliseconds in one civil day.
pub const MILLISECONDS_PER_DAY: i64 = 86_400_000;
/// Nanoseconds in one civil day.
pub const NANOSECONDS_PER_DAY: i64 = MILLISECONDS_PER_DAY * NANOSECONDS_PER_MILLISECOND;
/// 09:30 local ET, as an offset from local midnight, in milliseconds. The
/// source timestamps are wall-clock milliseconds in that same local
/// convention, so this offset is DST-free BY CONSTRUCTION — which is exactly
/// why frame B needs no timezone table.
pub const WALL_OPEN_OFFSET_MS: i64 = 9 * 3_600_000 + 30 * 60_000;
const AMERICA_NEW_YORK: &str = "America/New_York";

/// A Gregorian date without instant or ordering semantics.
///
/// ```compile_fail
/// use corpus::{CivilDate, FrameA};
/// let date = CivilDate::parse("2024-03-08").unwrap();
/// let instant = FrameA::from_published_utc_epoch_ns(0);
/// let _ = date == instant;
/// ```
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct CivilDate {
    year: u16,
    month: u8,
    day: u8,
}

impl CivilDate {
    /// Parses one canonical Gregorian `YYYY-MM-DD` date.
    pub fn parse(value: &str) -> Result<Self> {
        let malformed = || CorpusError::MalformedCivilDate {
            value: value.to_owned(),
        };
        if value.len() != 10
            || value.as_bytes().get(4) != Some(&b'-')
            || value.as_bytes().get(7) != Some(&b'-')
        {
            return Err(malformed());
        }
        let year: u16 = value
            .get(0..4)
            .ok_or_else(malformed)?
            .parse()
            .map_err(|_| malformed())?;
        let month: u8 = value
            .get(5..7)
            .ok_or_else(malformed)?
            .parse()
            .map_err(|_| malformed())?;
        let day: u8 = value
            .get(8..10)
            .ok_or_else(malformed)?
            .parse()
            .map_err(|_| malformed())?;
        let maximum_day = match month {
            2 if leap_year(year) => 29,
            2 => 28,
            4 | 6 | 9 | 11 => 30,
            1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
            _ => return Err(malformed()),
        };
        if day == 0 || day > maximum_day {
            return Err(malformed());
        }
        Ok(Self { year, month, day })
    }

    /// The `(year, month, day)` Gregorian components.
    #[must_use]
    pub const fn components(self) -> (u16, u8, u8) {
        (self.year, self.month, self.day)
    }

    /// Constructs a Gregorian date from an Arrow/Unix `Date32` day ordinal.
    ///
    /// This is the inverse of [`CivilDate::unix_day_ordinal`] and keeps
    /// date-only Arrow sources inside the workspace's one civil-calendar
    /// authority. Ordinals whose year cannot be represented by this type
    /// refuse rather than wrap.
    pub fn from_unix_day_ordinal(ordinal: i32) -> Result<Self> {
        let mut remaining = i64::from(ordinal);
        let mut year = 1970_i64;
        if remaining >= 0 {
            loop {
                let civil_year =
                    u16::try_from(year).map_err(|_| CorpusError::ArithmeticOverflow)?;
                let year_days = if leap_year(civil_year) {
                    366_i64
                } else {
                    365_i64
                };
                if remaining < year_days {
                    break;
                }
                remaining = remaining
                    .checked_sub(year_days)
                    .ok_or(CorpusError::ArithmeticOverflow)?;
                year = year.checked_add(1).ok_or(CorpusError::ArithmeticOverflow)?;
            }
        } else {
            while remaining < 0 {
                year = year.checked_sub(1).ok_or(CorpusError::ArithmeticOverflow)?;
                let civil_year =
                    u16::try_from(year).map_err(|_| CorpusError::ArithmeticOverflow)?;
                let year_days = if leap_year(civil_year) {
                    366_i64
                } else {
                    365_i64
                };
                remaining = remaining
                    .checked_add(year_days)
                    .ok_or(CorpusError::ArithmeticOverflow)?;
            }
        }
        let year = u16::try_from(year).map_err(|_| CorpusError::ArithmeticOverflow)?;
        let mut month = 1_u8;
        loop {
            let month_days = match month {
                2 if leap_year(year) => 29_i64,
                2 => 28_i64,
                4 | 6 | 9 | 11 => 30_i64,
                1 | 3 | 5 | 7 | 8 | 10 | 12 => 31_i64,
                _ => return Err(CorpusError::ArithmeticOverflow),
            };
            if remaining < month_days {
                break;
            }
            remaining = remaining
                .checked_sub(month_days)
                .ok_or(CorpusError::ArithmeticOverflow)?;
            month = month
                .checked_add(1)
                .ok_or(CorpusError::ArithmeticOverflow)?;
        }
        let day = u8::try_from(
            remaining
                .checked_add(1)
                .ok_or(CorpusError::ArithmeticOverflow)?,
        )
        .map_err(|_| CorpusError::ArithmeticOverflow)?;
        Ok(Self { year, month, day })
    }

    /// Days from 1970-01-01 in the same convention as Arrow `Date32`.
    #[must_use]
    pub fn unix_day_ordinal(self) -> i64 {
        self.ordinal()
    }

    fn ordinal(self) -> i64 {
        let preceding_year_days: i64 = if self.year >= 1970 {
            (1970..self.year)
                .map(|year| if leap_year(year) { 366_i64 } else { 365_i64 })
                .sum()
        } else {
            -(self.year..1970)
                .map(|year| if leap_year(year) { 366_i64 } else { 365_i64 })
                .sum::<i64>()
        };
        let preceding_month_days: i64 = (1..self.month)
            .map(|month| match month {
                2 if leap_year(self.year) => 29_i64,
                2 => 28_i64,
                4 | 6 | 9 | 11 => 30_i64,
                _ => 31_i64,
            })
            .sum();
        preceding_year_days + preceding_month_days + i64::from(self.day) - 1
    }
}

impl std::fmt::Display for CivilDate {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{:04}-{:02}-{:02}", self.year, self.month, self.day)
    }
}

/// Arrow time units accepted for already zone-aware source instants.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum DirectTimeUnit {
    /// Epoch milliseconds.
    Millisecond,
    /// Epoch microseconds.
    Microsecond,
    /// Epoch nanoseconds.
    Nanosecond,
}

/// A zone-aware source instant already normalized to UTC.
///
/// ```compile_fail
/// use corpus::{DirectInstant, DirectTimeUnit, FrameB};
/// let instant = DirectInstant::from_arrow_epoch(0, DirectTimeUnit::Nanosecond, "America/New_York").unwrap();
/// let raw = FrameB::from_naive_et_ns(0);
/// let _ = instant == raw;
/// ```
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct DirectInstant(i64);

impl DirectInstant {
    /// Admits an Arrow epoch instant with the registered timezone metadata.
    pub fn from_arrow_epoch(value: i64, unit: DirectTimeUnit, timezone: &str) -> Result<Self> {
        if timezone != AMERICA_NEW_YORK {
            return Err(CorpusError::InvalidDirectInstantTimezone {
                timezone: timezone.to_owned(),
            });
        }
        let multiplier = match unit {
            DirectTimeUnit::Millisecond => NANOSECONDS_PER_MILLISECOND,
            DirectTimeUnit::Microsecond => NANOSECONDS_PER_MICROSECOND,
            DirectTimeUnit::Nanosecond => 1,
        };
        value
            .checked_mul(multiplier)
            .map(Self)
            .ok_or(CorpusError::ArithmeticOverflow)
    }
}

/// A **frame-B** instant: naive local ET wall time, no offset, as it is
/// stamped in the six token corpora.
///
/// It is deliberately NOT comparable with [`FrameA`] and carries no
/// arithmetic with it: the whole R-HALT-42 defect was that both were bare
/// `i64`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct FrameB(i64);

impl FrameB {
    /// Wraps a naive-ET nanosecond value. Cheap and total: raw tape IS
    /// frame B, so admitting it needs no proof.
    #[must_use]
    pub const fn from_naive_et_ns(ns: i64) -> Self {
        Self(ns)
    }

    /// Wraps a naive-ET millisecond value (the raw parquet stamp).
    ///
    /// # Errors
    ///
    /// [`CorpusError::ArithmeticOverflow`] if the nanosecond value does not
    /// fit `i64`.
    pub fn from_naive_et_ms(ms: i64) -> Result<Self> {
        ms.checked_mul(NANOSECONDS_PER_MILLISECOND)
            .map(Self)
            .ok_or(CorpusError::ArithmeticOverflow)
    }

    /// The underlying naive-ET nanoseconds.
    #[must_use]
    pub const fn ns(self) -> i64 {
        self.0
    }
}

/// A **frame-A** instant: true UTC epoch nanoseconds.
///
/// ```compile_fail
/// use corpus::{FrameA, FrameB};
/// let utc = FrameA::from_published_utc_epoch_ns(0);
/// let eastern = FrameB::from_naive_et_ns(0);
/// let _ = utc == eastern;
/// ```
///
/// There is no public constructor from a bare `i64`. The ONLY way to obtain
/// one from tape is [`SessionClock::to_frame_a`], while an already-normalized
/// source instant enters through [`FrameA::from_direct_instant`].
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct FrameA(i64);

impl FrameA {
    /// The underlying UTC-epoch nanoseconds.
    #[must_use]
    pub const fn ns(self) -> i64 {
        self.0
    }

    /// The frame-A image of a value that is ALREADY frame A by provenance —
    /// a published `cutoff_ts_ns`, which the event publication writes in true
    /// UTC epoch nanoseconds.
    ///
    /// Named so that every such admission is greppable and reviewable; it is
    /// never used on tape.
    #[must_use]
    pub const fn from_published_utc_epoch_ns(ns: i64) -> Self {
        Self(ns)
    }

    /// Admits one validated, already-normalized direct source instant.
    #[must_use]
    pub const fn from_direct_instant(instant: DirectInstant) -> Self {
        Self(instant.0)
    }
}

/// The typed clock of ONE authenticated registry session.
#[derive(Clone, Copy, Debug)]
pub struct SessionClock {
    entry: RegistryEntry,
    civil_date: CivilDate,
    open_b_ns: i64,
    close_b_ns: i64,
}

impl SessionClock {
    /// Builds the clock for `day` from the frozen registry.
    ///
    /// # Errors
    ///
    /// [`CorpusError::UnknownSession`] if `day` is not registered, or
    /// [`CorpusError::ClockViolation`] if the registry row's own span
    /// disagrees with its `expected_bar_count` (boundary condition 2).
    pub fn for_day(day: &str) -> Result<Self> {
        Self::from_entry(registry::lookup(day)?)
    }

    /// Builds the clock from an already-looked-up registry entry.
    ///
    /// # Errors
    ///
    /// [`CorpusError::ClockViolation`] if the entry's session span is not
    /// exactly `expected_bar_count * BAR_NS` (boundary condition 2), or
    /// [`CorpusError::ArithmeticOverflow`]/[`CorpusError::ClockViolation`] if
    /// the day string is malformed or the frame-B window overflows.
    pub fn from_entry(entry: RegistryEntry) -> Result<Self> {
        let span_ns = entry
            .session_end_ns
            .checked_sub(entry.session_start_ns)
            .ok_or(CorpusError::ArithmeticOverflow)?;
        let expected_span_ns = i64::from(entry.expected_bar_count)
            .checked_mul(BAR_NS)
            .ok_or(CorpusError::ArithmeticOverflow)?;
        if span_ns != expected_span_ns {
            return Err(CorpusError::ClockViolation {
                day: entry.day.to_owned(),
                detail: format!(
                    "registry session span is {span_ns}ns but expected_bar_count \
                     {} implies {expected_span_ns}ns",
                    entry.expected_bar_count
                ),
            });
        }
        let civil_date = CivilDate::parse(entry.day)?;
        let open_b_ns = civil_date
            .ordinal()
            .checked_mul(MILLISECONDS_PER_DAY)
            .and_then(|midnight_ms| midnight_ms.checked_add(WALL_OPEN_OFFSET_MS))
            .and_then(|open_ms| open_ms.checked_mul(NANOSECONDS_PER_MILLISECOND))
            .ok_or(CorpusError::ArithmeticOverflow)?;
        let close_b_ns = open_b_ns
            .checked_add(expected_span_ns)
            .ok_or(CorpusError::ArithmeticOverflow)?;
        Ok(Self {
            entry,
            civil_date,
            open_b_ns,
            close_b_ns,
        })
    }

    /// The session this clock speaks for.
    #[must_use]
    pub const fn day(&self) -> &'static str {
        self.entry.day
    }

    /// The authenticated source day as a non-instant civil date.
    #[must_use]
    pub const fn civil_date(&self) -> CivilDate {
        self.civil_date
    }

    /// The session's own registry entry.
    #[must_use]
    pub const fn entry(&self) -> RegistryEntry {
        self.entry
    }

    /// The session's bar count, read from ITS OWN registry row — never from a
    /// caller (390 on 994 sessions, 210 on the nine early closes).
    #[must_use]
    pub const fn expected_bar_count(&self) -> u16 {
        self.entry.expected_bar_count
    }

    /// Frame-B 09:30 ET open.
    #[must_use]
    pub const fn open_b(&self) -> FrameB {
        FrameB(self.open_b_ns)
    }

    /// Frame-B official close: `open_b + expected_bar_count * BAR_NS`.
    #[must_use]
    pub const fn close_b(&self) -> FrameB {
        FrameB(self.close_b_ns)
    }

    /// Frame-B 09:30 ET open, in milliseconds (the raw tape's own unit).
    #[must_use]
    pub const fn open_b_ms(&self) -> i64 {
        self.open_b_ns / NANOSECONDS_PER_MILLISECOND
    }

    /// Frame-B official close, in milliseconds.
    #[must_use]
    pub const fn close_b_ms(&self) -> i64 {
        self.close_b_ns / NANOSECONDS_PER_MILLISECOND
    }

    /// Frame-A session start (the registry's true-UTC image of `open_b`).
    #[must_use]
    pub const fn session_start_a(&self) -> FrameA {
        FrameA(self.entry.session_start_ns)
    }

    /// Frame-A session end (exclusive).
    #[must_use]
    pub const fn session_end_a(&self) -> FrameA {
        FrameA(self.entry.session_end_ns)
    }

    /// Whether `ts_b` is inside the half-open frame-B RTH window — the
    /// premarket/postmarket filter, applied in FRAME B **before** any
    /// conversion (R-HALT-44 item 6(a)).
    #[must_use]
    pub const fn contains_b(&self, ts_b: FrameB) -> bool {
        ts_b.0 >= self.open_b_ns && ts_b.0 < self.close_b_ns
    }

    /// Whether `ts_a` is inside `[session_start, session_end)`.
    #[must_use]
    pub const fn contains_a(&self, ts_a: FrameA) -> bool {
        ts_a.0 >= self.entry.session_start_ns && ts_a.0 < self.entry.session_end_ns
    }

    /// Converts a frame-B instant on this clock's authenticated civil day.
    ///
    /// This is `event_B + (session_start_A - open_B)` under checked integer
    /// arithmetic. It deliberately has no RTH filter.
    pub fn to_frame_a_same_civil_day(&self, ts_b: FrameB) -> Result<FrameA> {
        let civil_start_b_ns = self
            .open_b_ns
            .checked_sub(WALL_OPEN_OFFSET_MS * NANOSECONDS_PER_MILLISECOND)
            .ok_or(CorpusError::ArithmeticOverflow)?;
        let civil_end_b_ns = civil_start_b_ns
            .checked_add(NANOSECONDS_PER_DAY)
            .ok_or(CorpusError::ArithmeticOverflow)?;
        if ts_b.0 < civil_start_b_ns || ts_b.0 >= civil_end_b_ns {
            return Err(CorpusError::WrongCivilDay {
                expected: self.civil_date.to_string(),
                actual_timestamp_ns: ts_b.0,
            });
        }
        let offset_ns = self
            .entry
            .session_start_ns
            .checked_sub(self.open_b_ns)
            .ok_or(CorpusError::ArithmeticOverflow)?;
        ts_b.0
            .checked_add(offset_ns)
            .map(FrameA)
            .ok_or(CorpusError::ArithmeticOverflow)
    }

    /// **THE SOLE RTH CONVERSION**: same-civil-day conversion followed by
    /// enforcement of the registered half-open frame-B session window.
    ///
    /// # Errors
    ///
    /// [`CorpusError::ClockViolation`] naming the violated condition, or
    /// [`CorpusError::ArithmeticOverflow`].
    pub fn to_frame_a(&self, ts_b: FrameB) -> Result<FrameA> {
        let converted = self.to_frame_a_same_civil_day(ts_b)?;
        if !self.contains_b(ts_b) {
            return Err(CorpusError::OutsideRth {
                day: self.entry.day.to_owned(),
                timestamp_ns: ts_b.0,
            });
        }
        let ts_a = converted.0;
        // Condition 4: the frame-A image is inside the frame-A session.
        if !self.contains_a(converted) {
            return Err(CorpusError::ClockViolation {
                day: self.entry.day.to_owned(),
                detail: format!(
                    "converted frame-A instant {ts_a} is outside [{}, {})",
                    self.entry.session_start_ns, self.entry.session_end_ns
                ),
            });
        }
        // Condition 5: exact offset equality, re-derived from the RESULT
        // rather than from the value just added -- a transposition or a
        // double conversion is caught here.
        let back_offset_ns = ts_a
            .checked_sub(self.entry.session_start_ns)
            .ok_or(CorpusError::ArithmeticOverflow)?;
        let event_offset_ns = ts_b
            .0
            .checked_sub(self.open_b_ns)
            .ok_or(CorpusError::ArithmeticOverflow)?;
        if back_offset_ns != event_offset_ns {
            return Err(CorpusError::ClockViolation {
                day: self.entry.day.to_owned(),
                detail: format!(
                    "offset equality violated: ts_A - session_start = {back_offset_ns}, \
                     ts_B - open_B = {event_offset_ns}"
                ),
            });
        }
        Ok(converted)
    }

    /// Converts a whole retained tape, enforcing ALL SIX boundary conditions
    /// (`day` is condition 1, checked against `requested_day`).
    ///
    /// # Errors
    ///
    /// [`CorpusError::ClockViolation`] naming the violated condition.
    pub fn convert_sequence(&self, requested_day: &str, tape_b: &[FrameB]) -> Result<Vec<FrameA>> {
        // Condition 1: this clock is the requested day's clock.
        if requested_day != self.entry.day {
            return Err(CorpusError::ClockViolation {
                day: self.entry.day.to_owned(),
                detail: format!(
                    "clock is for {} but {requested_day} was requested",
                    self.entry.day
                ),
            });
        }
        let mut out: Vec<FrameA> = Vec::with_capacity(tape_b.len());
        for (index, ts_b) in tape_b.iter().enumerate() {
            // Condition 6a: order preserved -- the frame-B tape must already
            // be non-decreasing, and the conversion is monotone, so a
            // violation here is an input defect and refuses.
            if index > 0 && tape_b[index - 1].0 > ts_b.0 {
                return Err(CorpusError::ClockViolation {
                    day: self.entry.day.to_owned(),
                    detail: format!(
                        "frame-B tape is not non-decreasing at row {index}: {} then {}",
                        tape_b[index - 1].0,
                        ts_b.0
                    ),
                });
            }
            out.push(self.to_frame_a(*ts_b)?);
        }
        // Condition 6b: row count preserved.
        if out.len() != tape_b.len() {
            return Err(CorpusError::ClockViolation {
                day: self.entry.day.to_owned(),
                detail: format!(
                    "conversion changed the row count: {} in, {} out",
                    tape_b.len(),
                    out.len()
                ),
            });
        }
        // Condition 6c: order preserved in the CONVERTED tape, re-checked on
        // the output rather than inferred from the input's monotonicity.
        for pair in out.windows(2) {
            if pair[0].0 > pair[1].0 {
                return Err(CorpusError::ClockViolation {
                    day: self.entry.day.to_owned(),
                    detail: format!(
                        "converted frame-A tape is not non-decreasing: {} then {}",
                        pair[0].0, pair[1].0
                    ),
                });
            }
        }
        Ok(out)
    }
}

/// Days since the Unix epoch for a `"YYYY-MM-DD"` day string, matching the
/// registry's own `session_start_ns` derivation. Moved here from
/// `reader.rs` so the clock, not each consumer, owns the civil calendar.
///
/// # Errors
///
/// [`CorpusError::MalformedCivilDate`] on a malformed day string.
pub fn civil_day_ordinal(day: &str) -> Result<i64> {
    Ok(CivilDate::parse(day)?.ordinal())
}

const fn leap_year(year: u16) -> bool {
    year.is_multiple_of(4) && (!year.is_multiple_of(100) || year.is_multiple_of(400))
}

#[cfg(test)]
mod tests {
    //! Every guard here ships with the counterfixture the FIRING LAW
    //! (R-HALT-44(a)) requires: an OLD-CONSTRUCTION instance it must REJECT
    //! plus an innocent instance it must ACCEPT. Passing on correct input
    //! proves nothing.

    use super::{BAR_NS, CivilDate, FrameA, FrameB, SessionClock, civil_day_ordinal};
    use crate::error::CorpusError;
    use crate::registry;

    /// One EDT full day, one EST full day, one 210-bar early close — the
    /// three pinned fixture sessions R-HALT-44 item 6(e) requires.
    const EDT_FULL_DAY: &str = "2024-05-24";
    const EST_FULL_DAY: &str = "2024-01-16";
    const EARLY_CLOSE: &str = "2024-07-03";

    fn clock(day: &str) -> SessionClock {
        SessionClock::for_day(day).expect("registered session")
    }

    #[test]
    fn the_three_fixture_sessions_are_the_shapes_they_are_pinned_for() {
        assert_eq!(clock(EDT_FULL_DAY).expected_bar_count(), 390);
        assert_eq!(clock(EST_FULL_DAY).expected_bar_count(), 390);
        assert_eq!(
            clock(EARLY_CLOSE).expected_bar_count(),
            210,
            "the early-close fixture must actually be an early close"
        );
    }

    /// The DST signature, from the registry alone: the frame-A image of the
    /// same 09:30 ET wall open differs between EDT and EST by exactly one
    /// hour. This is what makes a frame-B/frame-A confusion a 4h error on
    /// one day and a 5h error on the other.
    #[test]
    fn the_registry_carries_the_dst_shift_and_the_clock_needs_no_timezone_table() {
        let edt = clock(EDT_FULL_DAY);
        let est = clock(EST_FULL_DAY);
        let edt_offset = edt.session_start_a().ns() - edt.open_b().ns();
        let est_offset = est.session_start_a().ns() - est.open_b().ns();
        assert_eq!(edt_offset, 4 * 3_600_000_000_000);
        assert_eq!(est_offset, 5 * 3_600_000_000_000);
        assert_eq!(est_offset - edt_offset, 3_600_000_000_000);
    }

    /// The innocent fixture: a real quote instant converts, round-trips, and
    /// lands inside the frame-A session.
    #[test]
    fn an_in_window_instant_converts_exactly_and_lands_in_the_frame_a_session() {
        for day in [EDT_FULL_DAY, EST_FULL_DAY, EARLY_CLOSE] {
            let clock = clock(day);
            for offset_ns in [0, BAR_NS, 37 * BAR_NS + 12_345] {
                let ts_b = FrameB::from_naive_et_ns(clock.open_b().ns() + offset_ns);
                let ts_a = clock.to_frame_a(ts_b).expect("in-window instant converts");
                assert_eq!(ts_a.ns(), clock.session_start_a().ns() + offset_ns);
                assert!(clock.contains_a(ts_a));
            }
        }
    }

    /// **THE COUNTERFIXTURE FOR THE R-HALT-42 DEFECT ITSELF.** The old
    /// construction compared a frame-B tape instant against a frame-A cutoff
    /// as if they were the same number. Here that same instant is shown to
    /// be 4-5 hours EARLIER than its own frame-A image — i.e. a quote the old
    /// code accepted as "strictly before the cutoff" is, in real time, struck
    /// AFTER it. The guard must fail on this, and does.
    #[test]
    fn the_old_construction_reads_a_frame_b_instant_hours_before_its_own_frame_a_image() {
        for (day, expected_error_hours) in [(EDT_FULL_DAY, 4_i64), (EST_FULL_DAY, 5)] {
            let clock = clock(day);
            let offset_ns = expected_error_hours * 3_600_000_000_000;
            assert_eq!(
                clock.session_start_a().ns() - clock.open_b().ns(),
                offset_ns
            );

            // A decision one bar after the open. Its published cutoff is
            // frame A, as the event publication writes it.
            let cutoff_a_ns = clock.session_start_a().ns() + BAR_NS;

            // THE OLD RULE, verbatim: take the last frame-B tape instant
            // strictly below the cutoff's NUMERIC value. On this tape that
            // instant exists and is well inside the session.
            let selected_b_ns = cutoff_a_ns - 1;
            assert!(
                clock.contains_b(FrameB::from_naive_et_ns(selected_b_ns)),
                "the old rule really did select an in-session quote -- it just selected the \
                 WRONG one"
            );

            // In REAL TIME that quote is struck 4h (EDT) / 5h (EST) AFTER the
            // decision instant: the lookahead R-HALT-42 measured on 99.7% of
            // rows, and the reason the tripwire must be direction-aware.
            let real_time = clock
                .to_frame_a(FrameB::from_naive_et_ns(selected_b_ns))
                .expect("in-window");
            let true_lag_ns = cutoff_a_ns - real_time.ns();
            assert_eq!(true_lag_ns, 1 - offset_ns);
            assert!(
                true_lag_ns < 0,
                "the old construction fills AFTER its own decision instant"
            );

            // A saturating tripwire (`cutoff.saturating_sub(quote)`) reports
            // this as a perfect zero-lag fill -- which is exactly how it
            // stayed silent. Checked subtraction reports the direction.
            assert_eq!(cutoff_a_ns.saturating_sub(real_time.ns()), true_lag_ns);
            assert!(
                u64::try_from(true_lag_ns).is_err(),
                "an unsigned/clamped lag cannot represent this defect at all"
            );
        }
    }

    /// Boundary condition 3, both edges, with its counterfixture: a
    /// premarket instant and a post-close instant must REFUSE, not convert.
    #[test]
    fn premarket_and_postmarket_instants_refuse_instead_of_converting() {
        let clock = clock(EARLY_CLOSE);
        let premarket = FrameB::from_naive_et_ns(clock.open_b().ns() - 1);
        let at_close = FrameB::from_naive_et_ns(clock.close_b().ns());
        let post_close = FrameB::from_naive_et_ns(clock.close_b().ns() + BAR_NS);
        for (label, ts_b) in [
            ("premarket", premarket),
            ("the close itself (half-open)", at_close),
            ("postmarket", post_close),
        ] {
            let refused = clock.to_frame_a(ts_b);
            assert!(
                matches!(refused, Err(CorpusError::OutsideRth { .. })),
                "{label} must be refused, not converted"
            );
        }
        // The innocent instance: one nanosecond inside the close.
        assert!(
            clock
                .to_frame_a(FrameB::from_naive_et_ns(clock.close_b().ns() - 1))
                .is_ok()
        );
    }

    /// **THE EARLY-CLOSE COUNTERFIXTURE.** The old construction used a
    /// hardcoded 390-bar window. On this 210-bar session that window runs 180
    /// minutes past the official close; an instant in that gap must be
    /// refused by the clock and would have been ACCEPTED by the old one.
    #[test]
    fn the_early_close_clock_refuses_what_the_390_bar_window_admitted() {
        let clock = clock(EARLY_CLOSE);
        let old_close_b_ns = clock.open_b().ns() + 390 * BAR_NS;
        assert_eq!(old_close_b_ns - clock.close_b().ns(), 180 * BAR_NS);
        let post_close_ts = FrameB::from_naive_et_ns(clock.close_b().ns() + BAR_NS);
        assert!(
            post_close_ts.ns() < old_close_b_ns,
            "the old 390-bar window admitted this instant"
        );
        assert!(
            clock.to_frame_a(post_close_ts).is_err(),
            "the expected_bar_count window must refuse it"
        );
    }

    #[test]
    fn convert_sequence_enforces_the_day_the_row_count_and_the_order() {
        let clock = clock(EDT_FULL_DAY);
        let tape: Vec<FrameB> = (0..8)
            .map(|k| FrameB::from_naive_et_ns(clock.open_b().ns() + k * BAR_NS))
            .collect();
        let converted = clock
            .convert_sequence(EDT_FULL_DAY, &tape)
            .expect("innocent tape converts");
        assert_eq!(converted.len(), tape.len());
        assert!(converted.windows(2).all(|pair| pair[0] < pair[1]));

        // Condition 1: the wrong day's clock refuses.
        assert!(clock.convert_sequence(EST_FULL_DAY, &tape).is_err());

        // Condition 6: a non-monotone tape refuses rather than being sorted
        // into silence.
        let mut scrambled = tape.clone();
        scrambled.swap(2, 5);
        assert!(clock.convert_sequence(EDT_FULL_DAY, &scrambled).is_err());

        // Condition 3, inside a sequence: one postmarket row poisons the
        // whole conversion instead of being dropped.
        let mut with_post_close = tape.clone();
        with_post_close.push(FrameB::from_naive_et_ns(clock.close_b().ns() + 1));
        assert!(
            clock
                .convert_sequence(EDT_FULL_DAY, &with_post_close)
                .is_err()
        );
    }

    /// Boundary condition 2, with its counterfixture: a registry row whose
    /// span disagrees with its own `expected_bar_count` must refuse at
    /// construction.
    #[test]
    fn a_session_whose_span_disagrees_with_its_bar_count_refuses_at_construction() {
        let mut entry = registry::lookup(EARLY_CLOSE).expect("registered");
        // The old defect's shape: a 210-bar session carrying a 390-bar span.
        entry.session_end_ns = entry.session_start_ns + 390 * BAR_NS;
        let refused = SessionClock::from_entry(entry);
        assert!(matches!(refused, Err(CorpusError::ClockViolation { .. })));
        // Innocent: the untouched row builds.
        assert!(SessionClock::for_day(EARLY_CLOSE).is_ok());
    }

    #[test]
    fn every_registered_session_builds_a_clock_and_agrees_with_the_registry() {
        for entry in registry::all_sessions() {
            let clock = SessionClock::from_entry(*entry).expect("every pinned session");
            assert_eq!(clock.session_start_a().ns(), entry.session_start_ns);
            assert_eq!(clock.session_end_a().ns(), entry.session_end_ns);
            assert_eq!(
                clock.close_b().ns() - clock.open_b().ns(),
                i64::from(entry.expected_bar_count) * BAR_NS
            );
            // The UTC offset is always 4h or 5h -- never anything else, and
            // never zero (which is what a frame confusion would look like).
            let offset = clock.session_start_a().ns() - clock.open_b().ns();
            assert!(
                offset == 4 * 3_600_000_000_000 || offset == 5 * 3_600_000_000_000,
                "{}: offset {offset}",
                entry.day
            );
        }
    }

    #[test]
    fn civil_day_ordinal_rejects_malformed_days() {
        assert!(civil_day_ordinal("1970-01-01").is_ok_and(|value| value == 0));
        assert!(civil_day_ordinal("2024-02-29").is_ok());
        assert!(civil_day_ordinal("2023-02-29").is_err());
        assert!(civil_day_ordinal("2024-13-01").is_err());
        assert!(civil_day_ordinal("2024-1-1").is_err());
        assert!(civil_day_ordinal("").is_err());
    }

    #[test]
    fn unix_day_ordinal_round_trips_epoch_leap_and_pre_epoch_dates() {
        for (ordinal, expected) in [
            (-1, "1969-12-31"),
            (0, "1970-01-01"),
            (1, "1970-01-02"),
            (19_781, "2024-02-28"),
            (19_782, "2024-02-29"),
            (19_783, "2024-03-01"),
        ] {
            let date = CivilDate::from_unix_day_ordinal(ordinal).expect("valid Date32 ordinal");
            assert_eq!(date.to_string(), expected);
            assert_eq!(date.unix_day_ordinal(), i64::from(ordinal));
        }
    }

    #[test]
    fn a_published_cutoff_is_admitted_as_frame_a_only_through_the_named_door() {
        let clock = clock(EDT_FULL_DAY);
        let cutoff = FrameA::from_published_utc_epoch_ns(clock.session_start_a().ns() + BAR_NS);
        assert!(clock.contains_a(cutoff));
    }

    #[test]
    fn civil_date_is_canonical_unordered_date_data() {
        let date = super::CivilDate::parse("2024-02-29").expect("leap day");
        assert_eq!(date.components(), (2024, 2, 29));
        assert_eq!(date.to_string(), "2024-02-29");
        assert!(super::CivilDate::parse("2023-02-29").is_err());
    }

    #[test]
    fn same_civil_day_accepts_extended_context_but_rth_refuses_it() {
        let clock = clock(EDT_FULL_DAY);
        for timestamp in [clock.open_b().ns() - 1, clock.close_b().ns()] {
            let frame_b = FrameB::from_naive_et_ns(timestamp);
            assert!(clock.to_frame_a_same_civil_day(frame_b).is_ok());
            assert!(matches!(
                clock.to_frame_a(frame_b),
                Err(CorpusError::OutsideRth { .. })
            ));
        }
        let next_day = FrameB::from_naive_et_ns(clock.open_b().ns() + super::NANOSECONDS_PER_DAY);
        assert!(matches!(
            clock.to_frame_a_same_civil_day(next_day),
            Err(CorpusError::WrongCivilDay { .. })
        ));
    }

    #[test]
    fn same_civil_day_preserves_submillisecond_equal_time_sequence() {
        let clock = clock(EST_FULL_DAY);
        let tape = [
            FrameB::from_naive_et_ns(clock.open_b().ns() + 7),
            FrameB::from_naive_et_ns(clock.open_b().ns() + 7),
            FrameB::from_naive_et_ns(clock.open_b().ns() + 8),
        ];
        let converted =
            tape.map(|instant| clock.to_frame_a_same_civil_day(instant).expect("same day"));
        assert_eq!(converted[0].ns(), clock.session_start_a().ns() + 7);
        assert_eq!(converted[0], converted[1]);
        assert!(converted[1] < converted[2]);
    }

    #[test]
    fn direct_arrow_instant_validates_metadata_and_units_once() {
        let clock = clock(EDT_FULL_DAY);
        let milliseconds = clock.session_start_a().ns() / super::NANOSECONDS_PER_MILLISECOND;
        let direct = super::DirectInstant::from_arrow_epoch(
            milliseconds,
            super::DirectTimeUnit::Millisecond,
            "America/New_York",
        )
        .expect("registered direct instant");
        assert_eq!(FrameA::from_direct_instant(direct), clock.session_start_a());
        assert!(matches!(
            super::DirectInstant::from_arrow_epoch(0, super::DirectTimeUnit::Nanosecond, "UTC"),
            Err(CorpusError::InvalidDirectInstantTimezone { .. })
        ));
        assert!(matches!(
            super::DirectInstant::from_arrow_epoch(
                i64::MAX,
                super::DirectTimeUnit::Millisecond,
                "America/New_York"
            ),
            Err(CorpusError::ArithmeticOverflow)
        ));
    }

    #[test]
    fn authenticated_registry_pins_every_development_dst_boundary_and_early_close() {
        const HOUR_NS: i64 = 3_600_000_000_000;
        const BOUNDARIES: [(&str, i64, &str, i64); 8] = [
            ("2022-03-11", 5, "2022-03-14", 4),
            ("2022-11-04", 4, "2022-11-07", 5),
            ("2023-03-10", 5, "2023-03-13", 4),
            ("2023-11-03", 4, "2023-11-06", 5),
            ("2024-03-08", 5, "2024-03-11", 4),
            ("2024-11-01", 4, "2024-11-04", 5),
            ("2025-03-07", 5, "2025-03-10", 4),
            ("2025-10-31", 4, "2025-11-03", 5),
        ];
        for (before_day, before_hours, after_day, after_hours) in BOUNDARIES {
            for (day, expected_hours) in [(before_day, before_hours), (after_day, after_hours)] {
                let clock = clock(day);
                let open_image = clock
                    .to_frame_a(clock.open_b())
                    .expect("registered open converts");
                assert_eq!(
                    open_image.ns() - clock.open_b().ns(),
                    expected_hours * HOUR_NS,
                    "{day}"
                );
                assert_ne!(
                    open_image.ns() + HOUR_NS,
                    clock.session_start_a().ns(),
                    "a one-hour-mutated mapping must not match registry authority for {day}"
                );
            }
        }

        assert_eq!(
            clock("2024-03-08").session_start_a().ns(),
            1_709_908_200_000_000_000
        );
        assert_eq!(
            clock("2024-03-11").session_start_a().ns(),
            1_710_163_800_000_000_000
        );

        let early_closes: Vec<&str> = registry::all_sessions()
            .iter()
            .filter(|entry| entry.expected_bar_count == 210)
            .map(|entry| entry.day)
            .collect();
        assert_eq!(
            early_closes,
            vec![
                "2022-11-25",
                "2023-07-03",
                "2023-11-24",
                "2024-07-03",
                "2024-11-29",
                "2024-12-24",
                "2025-07-03",
                "2025-11-28",
                "2025-12-24",
            ]
        );
        for day in early_closes {
            let clock = clock(day);
            assert_eq!(clock.expected_bar_count(), 210);
            assert_eq!(clock.close_b().ns() - clock.open_b().ns(), 210 * BAR_NS);
        }
    }
}
