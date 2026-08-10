//! Typed streaming row readers, one module per leaf this crate parses
//! beyond raw bytes. Every reader is a hand-written, serde-free,
//! tab-splitting `Iterator` built on the shared cursor in
//! [`crate::rows`] — see that module for the `"NA"`-as-null and digest
//! conventions every leaf follows.

mod assignments;
mod day_roots;
mod event_signals;
mod truth_coverage;

pub use assignments::{Assignment, AssignmentReader};
pub use day_roots::{DayRoot, DayRootReader};
pub use event_signals::{EventSignal, EventSignalReader};
pub use truth_coverage::{TruthCoverage, TruthCoverageReader};
