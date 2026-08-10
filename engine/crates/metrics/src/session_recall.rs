//! `session_recall.tsv` row construction (amendment §A1, superseding design
//! brief §C's "per-(year, five-session-block) session-block table"):
//! "exactly 1,003 rows `year, ordinal, hits, truths` (within-year calendar
//! ordinal; zero-truth and zero-event sessions included; rows re-sum to
//! pooled hits / 8,914). The frozen Python
//! `year_stratified_session_block_lcb` builds its own blocks -- Rust NEVER
//! pre-blocks."
//!
//! This module therefore does exactly one thing: for **one candidate
//! stream**, turn a full session roster plus that stream's per-session
//! hit/truth counts into the flat, unblocked row set the pinned Python LCB
//! estimator consumes as its own raw input. It never groups sessions into
//! blocks -- that is the frozen estimator's job, and any block-level table
//! this crate might build for audit purposes belongs in a separately named
//! `block_audit.tsv`, never mistaken for the LCB input (amendment §A1).
//! Block-audit construction is out of scope for this module: the amendment
//! only prohibits conflating it with the LCB input, it does not require
//! `metrics` to build one.

use crate::session::SessionId;
use std::collections::{HashMap, HashSet};
use std::fmt;

/// One `session_recall.tsv` row for one candidate stream (A1).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SessionRecallRow {
    pub year: u16,
    /// Within-year calendar ordinal (A1) -- NOT a global 0..1002 ordinal.
    pub ordinal: u32,
    pub hits: u64,
    pub truths: u64,
}

/// A session repeated in the roster passed to [`session_recall_rows`]: A1
/// requires **exactly one** row per session, so a repeat is a typed error,
/// never a silent overwrite or duplicate emission.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct DuplicateSessionError(pub SessionId);

impl fmt::Display for DuplicateSessionError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "session year={} ordinal={} appears more than once in the roster",
            self.0.year, self.0.ordinal
        )
    }
}

impl std::error::Error for DuplicateSessionError {}

/// Builds the `session_recall.tsv` rows for one candidate stream (A1):
/// exactly one row per entry in `sessions`, in `sessions` order, with
/// `hits`/`truths` taken from the two maps (missing entries default to `0`
/// -- "zero-truth and zero-event sessions included", never dropped).
///
/// `sessions` is the caller's full accepted-session roster (in production,
/// all 1,003 development sessions); this function does not itself assert a
/// particular length -- that check belongs to the caller/wiring layer, which
/// owns the actual registry.
///
/// # Errors
///
/// Returns [`DuplicateSessionError`] if `sessions` repeats a `SessionId` (A1
/// requires exactly one row per session, so a repeat can never be silently
/// collapsed or duplicated).
#[allow(clippy::implicit_hasher)]
pub fn session_recall_rows(
    sessions: &[SessionId],
    truths_by_session: &HashMap<SessionId, u64>,
    hits_by_session: &HashMap<SessionId, u64>,
) -> Result<Vec<SessionRecallRow>, DuplicateSessionError> {
    let mut seen: HashSet<SessionId> = HashSet::with_capacity(sessions.len());
    let mut rows = Vec::with_capacity(sessions.len());
    for &session in sessions {
        if !seen.insert(session) {
            return Err(DuplicateSessionError(session));
        }
        rows.push(SessionRecallRow {
            year: session.year,
            ordinal: session.ordinal,
            hits: hits_by_session.get(&session).copied().unwrap_or(0),
            truths: truths_by_session.get(&session).copied().unwrap_or(0),
        });
    }
    Ok(rows)
}

/// Sums `hits` and `truths` across every row (A1: "rows re-sum to pooled
/// hits / 8,914" -- the property this function lets a caller check against
/// the known pooled totals). O(n).
#[must_use]
pub fn pooled_totals(rows: &[SessionRecallRow]) -> (u64, u64) {
    rows.iter().fold((0, 0), |(hits, truths), row| {
        (hits + row.hits, truths + row.truths)
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn session(year: u16, ordinal: u32) -> SessionId {
        SessionId { year, ordinal }
    }

    #[test]
    fn every_roster_session_gets_exactly_one_row_zero_filled_when_absent() {
        let sessions = vec![session(2022, 0), session(2022, 1), session(2023, 0)];
        let mut truths = HashMap::new();
        truths.insert(session(2022, 0), 3);
        truths.insert(session(2023, 0), 1);
        let mut hits = HashMap::new();
        hits.insert(session(2022, 0), 2);
        // session(2022, 1) has zero truths and zero hits -- must still
        // appear as its own row, not be dropped.

        let rows = session_recall_rows(&sessions, &truths, &hits).expect("rows");
        assert_eq!(rows.len(), 3);
        assert_eq!(
            rows[0],
            SessionRecallRow {
                year: 2022,
                ordinal: 0,
                hits: 2,
                truths: 3,
            }
        );
        assert_eq!(
            rows[1],
            SessionRecallRow {
                year: 2022,
                ordinal: 1,
                hits: 0,
                truths: 0,
            }
        );
        assert_eq!(
            rows[2],
            SessionRecallRow {
                year: 2023,
                ordinal: 0,
                hits: 0,
                truths: 1,
            }
        );
    }

    #[test]
    fn rows_resum_to_the_pooled_totals() {
        let sessions = vec![session(2022, 0), session(2022, 1), session(2023, 0)];
        let mut truths = HashMap::new();
        truths.insert(session(2022, 0), 3);
        truths.insert(session(2022, 1), 5);
        truths.insert(session(2023, 0), 1);
        let mut hits = HashMap::new();
        hits.insert(session(2022, 0), 2);
        hits.insert(session(2022, 1), 4);
        hits.insert(session(2023, 0), 1);

        let rows = session_recall_rows(&sessions, &truths, &hits).expect("rows");
        assert_eq!(pooled_totals(&rows), (7, 9));
    }

    #[test]
    fn duplicate_session_in_the_roster_is_a_typed_error() {
        let sessions = vec![session(2022, 0), session(2022, 0)];
        let error = session_recall_rows(&sessions, &HashMap::new(), &HashMap::new()).unwrap_err();
        assert_eq!(error.0, session(2022, 0));
    }

    #[test]
    fn empty_roster_produces_empty_rows_and_zero_pooled_totals() {
        let rows = session_recall_rows(&[], &HashMap::new(), &HashMap::new()).expect("rows");
        assert!(rows.is_empty());
        assert_eq!(pooled_totals(&rows), (0, 0));
    }
}
