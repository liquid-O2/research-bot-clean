//! **SELECT v2** — clean-slate selection engine.
//!
//! Three things live here, in dependency order:
//!
//! * [`calendar`] — the wall. A civil day is readable iff it is one of the
//!   1,003 frozen registry sessions, so 2026 and the 2020-2021 warmup are
//!   sealed for all six token corpora by construction rather than by review.
//! * [`sources`] — six thin, calendar-bounded, streaming parquet readers with
//!   RAW field retention, RTH filtering in frame B and u6 prices.
//! * [`session_pass`] — one streaming walk per session that serves every
//!   stock-side family at once and emits the PP1 1-second path panel.
//!
//! [`book`] reads the SELECT.4 action book to get each session's action
//! cutoffs; [`families`] is the emitter contract those cutoffs drive.
//!
//! This crate never modifies `corpus`; it reuses its registry, its
//! `SessionClock` (the sole lawful frame boundary) and its source-profile enum.

pub mod book;
pub mod calendar;
pub mod emit_cli;
pub mod error;
pub mod f4_pilot;
pub mod families;
pub mod session_pass;
pub mod sources;

pub use calendar::{CALENDAR_SESSION_COUNT, DayScope, admit, admit_ordinal, is_readable};
pub use error::{Result, SelectV2Error};
