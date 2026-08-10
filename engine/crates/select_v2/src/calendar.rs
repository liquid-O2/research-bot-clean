//! **The calendar wall.**
//!
//! Every reader in this crate takes a [`DayScope`], and the only way to build
//! a `DayScope` is [`admit`], which refuses any civil day that is not one of
//! the 1,003 sessions in the frozen `corpus` registry. Because a path is only
//! ever formed *from* an admitted scope, no reader can construct — let alone
//! open — a 2026 or 2020-2021 path. The old wall existed only inside the
//! stock-quote registry lookup; here it is the type-level precondition of all
//! six corpora.
//!
//! The scope also carries the session's [`corpus::SessionClock`], which is the
//! workspace's sole lawful naive-ET (frame B) <-> UTC (frame A) boundary. Token
//! parquet timestamps are frame B; the action book's `session_start_ns` is
//! frame A. Nothing in this crate converts between them by hand.

use crate::error::{Result, SelectV2Error};
use corpus::{RegistryEntry, SessionClock};

/// Size of the frozen development calendar.
pub const CALENDAR_SESSION_COUNT: usize = 1_003;

/// Seconds in one 1-minute bar, i.e. the PP1 slots one bar spans.
pub const SECONDS_PER_BAR: i64 = 60;

/// One admitted session: the registry row, its clock, and the frame-B RTH
/// window in the tape's own millisecond unit.
#[derive(Clone, Debug)]
pub struct DayScope {
    entry: RegistryEntry,
    clock: SessionClock,
    session_ordinal: usize,
}

impl DayScope {
    /// The registry row for this session.
    #[must_use]
    pub const fn entry(&self) -> RegistryEntry {
        self.entry
    }

    /// The session's clock — the only lawful frame boundary.
    #[must_use]
    pub const fn clock(&self) -> &SessionClock {
        &self.clock
    }

    /// `YYYY-MM-DD`.
    #[must_use]
    pub const fn day(&self) -> &'static str {
        self.entry.day
    }

    /// 0-based position in the 1,003-session calendar. This is the same
    /// `session_ordinal` the action book carries.
    #[must_use]
    pub const fn session_ordinal(&self) -> usize {
        self.session_ordinal
    }

    /// Frame-B 09:30 ET open, in the tape's millisecond unit.
    #[must_use]
    pub const fn open_ms_b(&self) -> i64 {
        self.clock.open_b_ms()
    }

    /// Frame-B official close (exclusive), in milliseconds.
    #[must_use]
    pub const fn close_ms_b(&self) -> i64 {
        self.clock.close_b_ms()
    }

    /// Whether a raw tape millisecond falls in the half-open frame-B RTH
    /// window. Applied in frame B *before* any conversion.
    #[must_use]
    pub const fn contains_ms_b(&self, ts_ms: i64) -> bool {
        ts_ms >= self.open_ms_b() && ts_ms < self.close_ms_b()
    }

    /// Registered bar count: 390 for a full session, 210 for the nine
    /// early closes. Never a caller's constant.
    #[must_use]
    pub const fn bar_count(&self) -> u16 {
        self.entry.expected_bar_count
    }

    /// PP1 grid width in 1-second slots: this session's true width, taken from
    /// its own registry row (23,400 full / 12,600 early close).
    #[must_use]
    pub const fn pp1_width(&self) -> usize {
        (self.entry.expected_bar_count as usize) * 60
    }

    /// The year directory this session's files live under.
    #[must_use]
    pub fn year(&self) -> &'static str {
        &self.entry.day[..4]
    }

    /// Frame-A (true UTC) cutoff instant for a 1-based bar ordinal, i.e. the
    /// close of bar `ordinal`.
    ///
    /// # Errors
    ///
    /// [`SelectV2Error::Arithmetic`] on overflow, or
    /// [`SelectV2Error::Config`] if the ordinal is outside `1..=bar_count`.
    pub fn cutoff_ns_a(&self, bar_ordinal: i64) -> Result<i64> {
        self.checked_cutoff(self.entry.session_start_ns, bar_ordinal)
    }

    /// Frame-B cutoff instant for a 1-based bar ordinal — the value the
    /// streaming pass compares raw tape timestamps against.
    ///
    /// # Errors
    ///
    /// As [`Self::cutoff_ns_a`].
    pub fn cutoff_ns_b(&self, bar_ordinal: i64) -> Result<i64> {
        self.checked_cutoff(self.clock.open_b().ns(), bar_ordinal)
    }

    fn checked_cutoff(&self, anchor_ns: i64, bar_ordinal: i64) -> Result<i64> {
        if bar_ordinal < 1 || bar_ordinal > i64::from(self.entry.expected_bar_count) {
            return Err(SelectV2Error::Config(format!(
                "{}: cutoff bar ordinal {bar_ordinal} outside 1..={}",
                self.entry.day, self.entry.expected_bar_count
            )));
        }
        bar_ordinal
            .checked_mul(corpus::BAR_NS)
            .and_then(|offset| anchor_ns.checked_add(offset))
            .ok_or(SelectV2Error::Arithmetic("DayScope::checked_cutoff"))
    }
}

/// **The wall.** Admits a civil day iff it is one of the 1,003 registry
/// sessions; refuses everything else with [`SelectV2Error::DayOutsideCalendar`].
///
/// # Errors
///
/// [`SelectV2Error::DayOutsideCalendar`] when the string is malformed or the
/// day has no registry row (which is every 2026 and 2020-2021 day), or
/// [`SelectV2Error::Corpus`] if the session's own registry row fails its
/// clock invariant.
pub fn admit(day: &str) -> Result<DayScope> {
    if day.len() != 10 || day.as_bytes()[4] != b'-' || day.as_bytes()[7] != b'-' {
        return Err(SelectV2Error::DayOutsideCalendar {
            day: day.to_owned(),
            detail: "not a YYYY-MM-DD civil day",
        });
    }
    let sessions = corpus::all_sessions();
    let index = sessions
        .binary_search_by(|entry| entry.day.cmp(day))
        .map_err(|_| SelectV2Error::DayOutsideCalendar {
            day: day.to_owned(),
            detail: "no row in the frozen 1,003-session registry",
        })?;
    let entry = sessions[index];
    Ok(DayScope {
        entry,
        clock: SessionClock::from_entry(entry)?,
        session_ordinal: index,
    })
}

/// Admits by 0-based calendar ordinal.
///
/// # Errors
///
/// [`SelectV2Error::DayOutsideCalendar`] if the ordinal is past the calendar.
pub fn admit_ordinal(ordinal: usize) -> Result<DayScope> {
    let sessions = corpus::all_sessions();
    let entry = sessions
        .get(ordinal)
        .ok_or_else(|| SelectV2Error::DayOutsideCalendar {
            day: format!("#{ordinal}"),
            detail: "ordinal past the 1,003-session calendar",
        })?;
    Ok(DayScope {
        entry: *entry,
        clock: SessionClock::from_entry(*entry)?,
        session_ordinal: ordinal,
    })
}

/// Whether a civil day is readable at all. Cheap, allocation-free, and the
/// honest predicate for "is this inside the wall".
#[must_use]
pub fn is_readable(day: &str) -> bool {
    corpus::all_sessions()
        .binary_search_by(|entry| entry.day.cmp(day))
        .is_ok()
}

/// The whole admitted calendar, ascending.
#[must_use]
pub fn sessions() -> &'static [RegistryEntry] {
    corpus::all_sessions()
}
