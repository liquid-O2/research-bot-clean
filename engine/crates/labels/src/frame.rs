//! Per-session evaluation frame: the scientific-path group projection, the
//! derived wide-breaker table, and the shared [`ExtremaTree`] query
//! structure. Design authority: `docs/specs/label_kernel_design_v1.md`
//! §"Evaluation frame" and its pinned "Registered anchor resolution" rules
//! 6-7.

use crate::extrema::ExtremaTree;
use corpus::{QuoteKind, SessionData};

/// Exact state of one scientific-path evaluation group (pinned rule 7):
/// `Scalar` when the group's deduplicated-sorted scientific midpoints are a
/// single distinct value, `Heterogeneous` when more than one exchange
/// disagreed at that millisecond (intra-group order uncertain).
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum GroupKind {
    Scalar,
    Heterogeneous,
}

impl GroupKind {
    /// The wire string used by every family-file `*_group_kind` column
    /// (`docs/specs/label_probe_schema_v1.md`).
    #[must_use]
    pub const fn wire(self) -> &'static str {
        match self {
            Self::Scalar => "SCALAR",
            Self::Heterogeneous => "HETEROGENEOUS",
        }
    }
}

/// One maximal wide-only run over the complete ordered group sequence
/// (pinned rule 6): `start_ns` is the first wide-only group's timestamp;
/// `end_ns` is the closing scientific group's own timestamp, or
/// `session_end_ns` if the run is still active at the end of the session.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Breaker {
    pub start_ns: i64,
    pub end_ns: i64,
}

/// Derives the breaker table from the complete ordered group sequence (all
/// four [`QuoteKind`]s — pinned rule 6, matching the archived
/// `derive_breakers`): a breaker is a maximal run of `WideOnly` groups; a
/// `SingleScientific`/`MultiScientific` group closes an active run at its own
/// timestamp; `Unresolved` (rejected-only) groups neither open, close, nor
/// split a run; a run still active at the end of the sequence closes at
/// `session_end_ns`.
///
/// O(n): one pass over the group sequence, no lookback, no lookahead.
///
/// # Panics
///
/// Panics if `ts_ns.len() != kind.len()`.
fn derive_breakers(ts_ns: &[i64], kind: &[QuoteKind], session_end_ns: i64) -> Vec<Breaker> {
    assert_eq!(
        ts_ns.len(),
        kind.len(),
        "ts_ns and kind must have equal length"
    );
    let mut breakers = Vec::new();
    let mut active_start: Option<i64> = None;
    for (index, group_kind) in kind.iter().enumerate() {
        match group_kind {
            QuoteKind::SingleScientific | QuoteKind::MultiScientific => {
                if let Some(start_ns) = active_start.take() {
                    breakers.push(Breaker {
                        start_ns,
                        end_ns: ts_ns[index],
                    });
                }
            }
            QuoteKind::WideOnly => {
                if active_start.is_none() {
                    active_start = Some(ts_ns[index]);
                }
            }
            QuoteKind::Unresolved => {}
        }
    }
    if let Some(start_ns) = active_start {
        breakers.push(Breaker {
            start_ns,
            end_ns: session_end_ns,
        });
    }
    breakers
}

/// The per-session evaluation frame (design doc "Evaluation frame"): the
/// scientific-path group projection (`ts_ns`/`m_lo`/`m_hi`/`kind`, pinned
/// rule 7), the derived breaker table (pinned rule 6), and the shared
/// [`ExtremaTree`] over `(m_hi, m_lo)`, all built once per session.
pub struct SessionFrame {
    pub day: &'static str,
    pub session_start_ns: i64,
    pub session_end_ns: i64,
    pub expected_bar_count: u16,
    /// Scientific-path group timestamps, ascending.
    pub ts_ns: Vec<i64>,
    /// First (minimum) deduplicated-sorted scientific midpoint per group.
    pub m_lo: Vec<i64>,
    /// Last (maximum) deduplicated-sorted scientific midpoint per group.
    pub m_hi: Vec<i64>,
    pub kind: Vec<GroupKind>,
    breakers: Vec<Breaker>,
    extrema: ExtremaTree,
}

impl SessionFrame {
    /// Builds the frame from one decoded session: derives the breaker table
    /// from the complete group sequence, filters to the scientific-path
    /// projection (groups with ≥ 1 scientific midpoint, pinned rule 7), and
    /// builds the shared [`ExtremaTree`] once.
    ///
    /// O(n) time and memory, `n` = `session.groups.len()`.
    ///
    /// # Panics
    ///
    /// Panics if `session` has zero scientific-path groups (every accepted
    /// development session has at least one — see `corpus::load_session`'s
    /// own content-mismatch checks).
    #[must_use]
    pub fn build(session: &SessionData) -> Self {
        let breakers = derive_breakers(
            &session.groups.ts_ns,
            &session.groups.kind,
            session.session_end_ns,
        );

        let mut ts_ns = Vec::new();
        let mut m_lo = Vec::new();
        let mut m_hi = Vec::new();
        let mut kind = Vec::new();
        for (index, &group_ts_ns) in session.groups.ts_ns.iter().enumerate() {
            let midpoints = session.groups.scientific_midpoints(index);
            let Some(&first) = midpoints.first() else {
                continue;
            };
            let last = *midpoints
                .last()
                .expect("nonempty midpoints slice has a last element");
            ts_ns.push(group_ts_ns);
            m_lo.push(first);
            m_hi.push(last);
            kind.push(if midpoints.len() == 1 {
                GroupKind::Scalar
            } else {
                GroupKind::Heterogeneous
            });
        }
        assert!(
            !ts_ns.is_empty(),
            "SessionFrame::build: session {} has zero scientific-path groups",
            session.day
        );

        let extrema = ExtremaTree::build(&m_hi, &m_lo);
        Self {
            day: session.day,
            session_start_ns: session.session_start_ns,
            session_end_ns: session.session_end_ns,
            expected_bar_count: session.expected_bar_count,
            ts_ns,
            m_lo,
            m_hi,
            kind,
            breakers,
            extrema,
        }
    }

    /// Number of scientific-path groups in the frame.
    #[must_use]
    pub fn group_count(&self) -> usize {
        self.ts_ns.len()
    }

    /// The shared [`ExtremaTree`] over `(m_hi, m_lo)`, built once per
    /// session and reused by every family kernel and every anchor.
    #[must_use]
    pub fn extrema(&self) -> &ExtremaTree {
        &self.extrema
    }

    /// The derived breaker table: ordered ascending and non-overlapping by
    /// construction (each run is closed, directly or at the session end,
    /// before the next one can open).
    #[must_use]
    pub fn breakers(&self) -> &[Breaker] {
        &self.breakers
    }

    /// The first breaker whose `start_ns` is STRICTLY greater than `t`
    /// (pinned rule 6; `t == start_ns` does not match). O(log n) by binary
    /// search — `breakers()` is sorted ascending by construction.
    #[must_use]
    pub fn first_breaker_start_after(&self, t: i64) -> Option<i64> {
        let index = self
            .breakers
            .partition_point(|breaker| breaker.start_ns <= t);
        self.breakers.get(index).map(|breaker| breaker.start_ns)
    }

    /// The exclusive end position for a half-open window ending at `bound`:
    /// the count of scientific-path groups whose timestamp is strictly less
    /// than `bound` (registered `end_position`, CONV §3). A group exactly at
    /// `bound` is excluded when `bound` is used as a window's exclusive end,
    /// and included when the very same value is used as a window's (also
    /// half-open) inclusive left bound — both are this one function. O(log
    /// n) by binary search — `ts_ns` is ascending by construction.
    #[must_use]
    pub fn end_position(&self, bound: i64) -> usize {
        self.ts_ns.partition_point(|&ts| ts < bound)
    }

    /// Test-only constructor: builds a frame directly from its already-
    /// computed parts, bypassing [`corpus::SessionData`] decoding entirely,
    /// so unit tests can exercise cutoff/window logic against small
    /// synthetic sessions.
    #[cfg(test)]
    pub(crate) fn from_parts_for_test(
        session_start_ns: i64,
        session_end_ns: i64,
        ts_ns: Vec<i64>,
        m_lo: Vec<i64>,
        m_hi: Vec<i64>,
        kind: Vec<GroupKind>,
        breakers: Vec<Breaker>,
    ) -> Self {
        let extrema = ExtremaTree::build(&m_hi, &m_lo);
        Self {
            day: "TEST",
            session_start_ns,
            session_end_ns,
            expected_bar_count: 0,
            ts_ns,
            m_lo,
            m_hi,
            kind,
            breakers,
            extrema,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ------------------------- breaker derivation -------------------------

    #[test]
    fn derive_breakers_transparent_through_rejected_only_groups() {
        let ts = vec![100, 200, 300];
        let kind = vec![
            QuoteKind::WideOnly,
            QuoteKind::Unresolved,
            QuoteKind::WideOnly,
        ];
        let breakers = derive_breakers(&ts, &kind, 1000);
        assert_eq!(
            breakers,
            vec![Breaker {
                start_ns: 100,
                end_ns: 1000
            }]
        );
    }

    #[test]
    fn derive_breakers_run_closed_by_a_scientific_group() {
        let ts = vec![100, 200, 300];
        let kind = vec![
            QuoteKind::WideOnly,
            QuoteKind::WideOnly,
            QuoteKind::SingleScientific,
        ];
        let breakers = derive_breakers(&ts, &kind, 1000);
        assert_eq!(
            breakers,
            vec![Breaker {
                start_ns: 100,
                end_ns: 300
            }]
        );
    }

    #[test]
    fn derive_breakers_tail_run_closes_at_session_end() {
        let ts = vec![100, 200];
        let kind = vec![QuoteKind::SingleScientific, QuoteKind::WideOnly];
        let breakers = derive_breakers(&ts, &kind, 1000);
        assert_eq!(
            breakers,
            vec![Breaker {
                start_ns: 200,
                end_ns: 1000
            }]
        );
    }

    #[test]
    fn derive_breakers_empty_on_a_no_breaker_day() {
        let ts = vec![100, 200, 300];
        let kind = vec![
            QuoteKind::SingleScientific,
            QuoteKind::MultiScientific,
            QuoteKind::Unresolved,
        ];
        let breakers = derive_breakers(&ts, &kind, 1000);
        assert!(breakers.is_empty());
    }

    #[test]
    fn derive_breakers_multiple_runs_are_ordered_and_non_overlapping() {
        let ts = vec![100, 200, 300, 400, 500];
        let kind = vec![
            QuoteKind::WideOnly,
            QuoteKind::SingleScientific,
            QuoteKind::WideOnly,
            QuoteKind::WideOnly,
            QuoteKind::MultiScientific,
        ];
        let breakers = derive_breakers(&ts, &kind, 1000);
        assert_eq!(
            breakers,
            vec![
                Breaker {
                    start_ns: 100,
                    end_ns: 200
                },
                Breaker {
                    start_ns: 300,
                    end_ns: 500
                }
            ]
        );
        assert!(
            breakers
                .windows(2)
                .all(|pair| pair[0].end_ns <= pair[1].start_ns)
        );
    }

    // ------------------------- query structures ----------------------------

    #[test]
    fn first_breaker_start_after_is_strict() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            1_000,
            vec![0],
            vec![100],
            vec![100],
            vec![GroupKind::Scalar],
            vec![Breaker {
                start_ns: 500,
                end_ns: 600,
            }],
        );
        // `t == start_ns` must not match: strictness is load-bearing (pinned
        // rule 6).
        assert_eq!(frame.first_breaker_start_after(500), None);
        assert_eq!(frame.first_breaker_start_after(499), Some(500));
        assert_eq!(frame.first_breaker_start_after(600), None);
    }

    #[test]
    fn end_position_boundary_is_half_open() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            1_000,
            vec![100, 200, 300],
            vec![10, 10, 10],
            vec![10, 10, 10],
            vec![GroupKind::Scalar; 3],
            Vec::new(),
        );
        // A group exactly at the bound is not < bound: excluded as an end.
        assert_eq!(frame.end_position(200), 1);
        // Strictly past it, the group at 200 is now counted.
        assert_eq!(frame.end_position(201), 2);
    }

    // ------------------------------ real day --------------------------------

    #[test]
    fn real_session_frame_matches_scientific_group_count_and_breakers_are_well_formed() {
        let root = std::path::PathBuf::from("/workspace/data/tokens/stock_quotes/IWM");
        if !root.is_dir() {
            eprintln!("skipping: corpus root {} is not mounted", root.display());
            return;
        }
        let session = corpus::load_session("2022-01-03", &root).expect("real session decodes");
        let expected_scientific_groups = session
            .groups
            .kind
            .iter()
            .filter(|kind| {
                matches!(
                    kind,
                    QuoteKind::SingleScientific | QuoteKind::MultiScientific
                )
            })
            .count();

        let frame = SessionFrame::build(&session);
        assert!(frame.group_count() > 0);
        assert_eq!(frame.group_count(), expected_scientific_groups);

        let breakers = frame.breakers();
        assert!(
            breakers
                .windows(2)
                .all(|pair| pair[0].end_ns <= pair[1].start_ns),
            "breakers must be ordered and non-overlapping"
        );
        assert!(
            breakers.iter().all(|b| b.start_ns < b.end_ns),
            "each breaker must be a nonempty interval"
        );
    }
}
