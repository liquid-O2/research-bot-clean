//! Truth capture (design brief §C: "truth capture (CONV §8 rule verbatim:
//! keyed match + fragment overlap + post-plateau + scorable + delay ≤ 2)").
//!
//! The keyed-exact-match + fragment-overlap join (CONV §8 rules 1-2) is
//! **not** performed here: it is resolved upstream into [`RelationEdge`]
//! (mirrors `labels::f_prox::SignalRelation`'s "already-resolved" contract
//! and amendment §A10's `truth_relation_projection.parquet` plan). This
//! module implements CONV §8 rules 3-6 verbatim (post-plateau, scorable,
//! timely delay ≤ 2, dedup earliest-timely) plus the full registered
//! candidate-assignment / truth-miss-reason taxonomy (CONV §6c), reproduced
//! from the archived adequacy engine's own logic:
//! `archive/rust/iwm_atlas_v2/src/intrabar_event_adequacy.rs:1996-2059`
//! (preliminary classification), `:2261-2294` (dedup: sort candidates timely
//! for the same truth by `(visible_ts_ns, confirmation_group_ordinal,
//! registration_ordinal)` ascending, earliest wins), `:2217-2234` +
//! `:2473-2506` (unhit-truth miss-reason classification via the `r / e / p /
//! s` relation-candidate filters). Wire codes verified verbatim against
//! `archive/rust/iwm_atlas_v2/src/intrabar_event_publication.rs:541-574`.
//!
//! The dedup tie-break deliberately **diverges** from the archived engine's
//! own last-resort field, which was the row's `candidate_id` digest
//! (`intrabar_event_adequacy.rs:2283-2290`). `research/review_records/
//! events23_sol_adversarial.md` finding 4 rejected that as a non-scientific
//! hash tie-break (CONV §8 rule 6 / house rule "scientific choices never
//! tie-break by hash/ID", `AGENTS.md`); the consolidated review ledger
//! (`events23_consolidated_ledger.md`, lane L1) requires the frozen
//! candidate registration/file order instead -- see [`RelationEdge::
//! registration_ordinal`].
//!
//! # Input contract
//!
//! [`classify`] takes `truths`, `edges`, and `outcomes` already filtered to
//! **one** `(session, stream)` pair (the Wiring phase's per-session,
//! per-stream run loop is the natural place to slice these); `session` and
//! `stream` are passed explicitly and every row is checked against them
//! (never silently ignored on a mismatch).
//!
//! Both `edges` and `outcomes` are at the REGISTERED CANDIDATE grain:
//! `assignments.tsv`'s own `(stream, candidate_id)` row
//! (`engine/crates/pubread/src/leaves/assignments.rs`) -- never `signal_id`.
//! Ruling E16 records that a signal legitimately appears as a member of more
//! than one candidate row (stream-scoped `related_episode_ids` per
//! candidate); collapsing this module's input to signal grain either
//! fabricates a spurious duplicate (two candidates sharing a member signal
//! collide into one row) or silently erases a candidate's own burden
//! (`events23_sol_adversarial.md` finding 1, P0). E16's deduplicated
//! per-signal relation union is a distinct construction confined to
//! `labels::f_prox` and must never be substituted for this candidate-grain
//! relation set.
//!
//! `edges` and `outcomes` must each carry exactly one row per emitted
//! `candidate_id` for this `(session, stream)` -- including candidates with
//! zero truth relation (mirrors `assignments.tsv`'s "one row per candidate"
//! contract) -- so that burden (false-positive) counts are complete.
//! [`classify`] enforces candidate-key-set equality between `edges` and
//! `outcomes` in **both** directions: an edge with no matching outcome is
//! [`CaptureError::MissingOutcome`], and an outcome with no matching edge is
//! [`CaptureError::MissingRelationEdge`] (`events23_sol_adversarial.md`
//! finding 3) -- never a silent burden drop.

use crate::session::{SessionId, StreamId};
use crate::truth::TruthRow;
use std::collections::{HashMap, HashSet};
use std::fmt;

/// Registered timely-delay ceiling (CONV §8 rule 5, CONV Appendix
/// `MAX_TIMELY_DELAY_BARS`).
pub const MAX_TIMELY_DELAY_BARS: u32 = 2;

/// A registered candidate row's resolved relation to the truth-episode
/// population for one `(session, stream)` (CONV §8 rules 1-2, already
/// applied upstream): `related_episode_ids.len()` is `0` (no relation), `1`
/// (unambiguous), or `n > 1` (this candidate's own keyed match is itself
/// ambiguous across truths -- CONV §6c `PreliminaryState::Conflict`).
///
/// Keyed by `candidate_id`, `assignments.tsv`'s own `(stream, candidate)`
/// grain -- **not** `signal_id` (ruling E16, wave-4 P0; see the module
/// doc's "Input contract" section). `member_signal_ids` and
/// `related_episode_ids` mirror `assignments.tsv`'s own columns of the same
/// name verbatim (`engine/crates/pubread/src/leaves/assignments.rs`);
/// `member_signal_ids` is carried for provenance / downstream
/// recomputation and is not itself consulted by this module's arithmetic
/// (E16's per-signal union over these member sets is confined to
/// `labels::f_prox`).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RelationEdge {
    pub session: SessionId,
    pub stream: StreamId,
    pub candidate_id: [u8; 32],
    /// Frozen registration/file ordinal: this candidate row's position
    /// among `assignments.tsv` rows for this `(session, stream)` (never a
    /// digest) -- the ONLY tie-break authority CONV §8 rule 6 and the house
    /// rule "scientific choices never tie-break by hash/ID" permit. See
    /// [`resolve_winners`].
    pub registration_ordinal: u64,
    /// This candidate's own member signals (`assignments.tsv`
    /// `member_signal_ids`; `"NA"` parses as an empty list upstream).
    pub member_signal_ids: Vec<[u8; 32]>,
    pub related_episode_ids: Vec<[u8; 32]>,
}

/// One candidate row's own causal-availability clock (CONV §4), keyed by
/// `candidate_id` to the [`RelationEdge`] of the same
/// `(session, stream, candidate_id)`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CandidateOutcome {
    pub session: SessionId,
    pub stream: StreamId,
    pub candidate_id: [u8; 32],
    pub confirmation_group_ordinal: u64,
    pub visible_ts_ns: i64,
    /// `None` iff this candidate's clock has no minute-bar ordinal at all
    /// (CONV §4 `event_scorable`'s first conjunct).
    pub visible_bar_ordinal: Option<u64>,
    pub session_end_ns: i64,
}

impl CandidateOutcome {
    /// CONV §4 "scorable" predicate: `visible_bar_ordinal.is_some() &&
    /// visible_ts_ns < session_end_ns`
    /// (`archive/rust/iwm_atlas_v2/src/intrabar_event_adequacy.rs:1390-1392`).
    #[must_use]
    pub const fn event_scorable(&self) -> bool {
        self.visible_bar_ordinal.is_some() && self.visible_ts_ns < self.session_end_ns
    }
}

/// Registered candidate-assignment states (CONV §6c
/// `IntrabarCandidateAssignmentState`; wire codes verbatim from
/// `intrabar_event_publication.rs:543-562`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CandidateAssignmentState {
    /// The earliest timely candidate for its truth (dedup winner).
    UniqueTimelyHit,
    /// Timely for its truth, but not the earliest (dedup loser).
    DuplicateTimely,
    /// `related_episode_ids.len() > 1`: this candidate's own keyed match is
    /// ambiguous across more than one truth.
    ConflictingTruthMemberships,
    /// Exactly one relation, but not strictly after the truth's plateau
    /// (CONV §8 rule 3).
    ExactNotPostPlateau,
    /// Post-plateau, but not scorable (CONV §8 rule 4).
    PostPlateauExactNotScorable,
    /// Post-plateau, scorable, but `delay_bars > MAX_TIMELY_DELAY_BARS`.
    PostPlateauExactLate,
    /// Zero relation, scorable.
    UnmatchedEventScorable,
    /// Zero relation, not scorable (near the session close).
    UnmatchedCloseNonScorable,
}

impl CandidateAssignmentState {
    #[must_use]
    pub const fn wire(self) -> &'static str {
        match self {
            Self::UniqueTimelyHit => "UNIQUE_TIMELY_HIT",
            Self::DuplicateTimely => "DUPLICATE_TIMELY",
            Self::ConflictingTruthMemberships => "CONFLICTING_TRUTH_MEMBERSHIPS",
            Self::ExactNotPostPlateau => "EXACT_NOT_POST_PLATEAU",
            Self::PostPlateauExactNotScorable => "POST_PLATEAU_EXACT_NOT_SCORABLE",
            Self::PostPlateauExactLate => "POST_PLATEAU_EXACT_LATE",
            Self::UnmatchedEventScorable => "UNMATCHED_EVENT_SCORABLE",
            Self::UnmatchedCloseNonScorable => "UNMATCHED_CLOSE_NON_SCORABLE",
        }
    }
}

/// The five registered truth-miss reasons (CONV §6c
/// `IntrabarTruthMissReason`; wire codes verbatim from
/// `intrabar_event_publication.rs:566-574`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TruthMissReason {
    /// No candidate ever had an exact (keyed-match + fragment-overlap)
    /// relation to this truth.
    NoExactRelation,
    /// Every candidate that did relate to this truth was itself
    /// [`CandidateAssignmentState::ConflictingTruthMemberships`].
    ConflictingRelationOnly,
    /// A non-conflicting relation exists, but none is post-plateau.
    ExactNotPostPlateau,
    /// A post-plateau relation exists, but none is scorable.
    PostPlateauExactNotScorable,
    /// A post-plateau, scorable relation exists, but every one is late
    /// (`delay_bars > MAX_TIMELY_DELAY_BARS`).
    PostPlateauExactLate,
}

impl TruthMissReason {
    #[must_use]
    pub const fn wire(self) -> &'static str {
        match self {
            Self::NoExactRelation => "NO_EXACT_RELATION",
            Self::ConflictingRelationOnly => "CONFLICTING_RELATION_ONLY",
            Self::ExactNotPostPlateau => "EXACT_NOT_POST_PLATEAU",
            Self::PostPlateauExactNotScorable => "POST_PLATEAU_EXACT_NOT_SCORABLE",
            Self::PostPlateauExactLate => "POST_PLATEAU_EXACT_LATE",
        }
    }
}

/// One truth's final capture outcome.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TruthCaptureOutcome {
    Hit {
        candidate_id: [u8; 32],
        delay_bars: u32,
    },
    Miss(TruthMissReason),
}

/// [`TruthCaptureOutcome`] for one truth, in the same order as the input
/// `truths` slice.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TruthOutcome {
    pub episode_id: [u8; 32],
    pub outcome: TruthCaptureOutcome,
}

/// [`CandidateAssignmentState`] for one candidate, in the same order as the
/// input `edges` slice.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct CandidateAssignment {
    pub candidate_id: [u8; 32],
    pub state: CandidateAssignmentState,
    /// `Some` for every state except [`CandidateAssignmentState::ConflictingTruthMemberships`],
    /// [`CandidateAssignmentState::UnmatchedEventScorable`], and
    /// [`CandidateAssignmentState::UnmatchedCloseNonScorable`] (states with
    /// no single related truth to measure a delay against).
    pub delay_bars: Option<u32>,
}

/// Pooled counts for one `(session, stream)` capture computation (design
/// brief §C: recall inputs, duplicates, conflicts, delay distribution).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct CaptureCounts {
    pub confirmed_truths: u64,
    pub unique_timely_hits: u64,
    pub duplicate_timely_candidates: u64,
    pub conflicting_candidates: u64,
    pub exact_not_post_plateau_candidates: u64,
    pub post_plateau_not_scorable_candidates: u64,
    pub late_candidates: u64,
    pub unmatched_event_scorable_candidates: u64,
    pub unmatched_close_non_scorable_candidates: u64,
    pub delay_0_hits: u64,
    pub delay_1_hits: u64,
    pub delay_2_hits: u64,
    pub miss_no_exact_relation: u64,
    pub miss_conflicting_relation_only: u64,
    pub miss_exact_not_post_plateau: u64,
    pub miss_post_plateau_not_scorable: u64,
    pub miss_post_plateau_late: u64,
}

impl CaptureCounts {
    /// The one frozen FP-burden scalar (design brief §C "FP burden"; A9
    /// "the one frozen burden scalar"): count of candidates that never
    /// related to any truth **and** were scorable (a candidate that could,
    /// in principle, have been timely for some truth, but related to none).
    ///
    /// Non-scorable unmatched candidates
    /// (`unmatched_close_non_scorable_candidates`, fired too close to the
    /// session close to ever be timely) are excluded from this scalar: they
    /// could never have captured a truth even with a relation, so counting
    /// them as "false-positive burden" would penalize streams for
    /// end-of-session bookkeeping rather than genuine false alarms. This is
    /// an architect-owned judgment call, not pinned by the amendment text
    /// verbatim -- flagged as an escalation, not a silent guess.
    #[must_use]
    pub const fn burden(&self) -> u64 {
        self.unmatched_event_scorable_candidates
    }
}

/// Everything that can go wrong classifying one `(session, stream)` group:
/// every variant means the input rows violated the documented contract (a
/// data-integrity defect upstream), never a silent drop.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum CaptureError {
    RelationEdgeSessionMismatch([u8; 32]),
    RelationEdgeStreamMismatch([u8; 32]),
    CandidateOutcomeSessionMismatch([u8; 32]),
    CandidateOutcomeStreamMismatch([u8; 32]),
    DuplicateRelationEdge([u8; 32]),
    DuplicateCandidateOutcome([u8; 32]),
    DuplicateTruthEpisode([u8; 32]),
    /// An edge (candidate row) has no matching outcome row.
    MissingOutcome([u8; 32]),
    /// An outcome (candidate row) has no matching edge row: the edge
    /// projection is incomplete (`events23_sol_adversarial.md` finding 3) --
    /// never silently treated as zero burden.
    MissingRelationEdge([u8; 32]),
    UnknownRelatedEpisode {
        candidate_id: [u8; 32],
        episode_id: [u8; 32],
    },
    DelayArithmeticOverflow {
        candidate_id: [u8; 32],
    },
}

impl fmt::Display for CaptureError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::RelationEdgeSessionMismatch(id) => {
                write!(f, "relation edge {} has the wrong session", hex32(id))
            }
            Self::RelationEdgeStreamMismatch(id) => {
                write!(f, "relation edge {} has the wrong stream", hex32(id))
            }
            Self::CandidateOutcomeSessionMismatch(id) => {
                write!(f, "candidate outcome {} has the wrong session", hex32(id))
            }
            Self::CandidateOutcomeStreamMismatch(id) => {
                write!(f, "candidate outcome {} has the wrong stream", hex32(id))
            }
            Self::DuplicateRelationEdge(id) => {
                write!(f, "candidate {} has more than one relation edge", hex32(id))
            }
            Self::DuplicateCandidateOutcome(id) => {
                write!(f, "candidate {} has more than one outcome", hex32(id))
            }
            Self::DuplicateTruthEpisode(id) => {
                write!(f, "episode {} appears more than once in truths", hex32(id))
            }
            Self::MissingOutcome(id) => {
                write!(
                    f,
                    "candidate {} has a relation edge but no outcome",
                    hex32(id)
                )
            }
            Self::MissingRelationEdge(id) => {
                write!(
                    f,
                    "candidate {} has an outcome but no relation edge",
                    hex32(id)
                )
            }
            Self::UnknownRelatedEpisode {
                candidate_id,
                episode_id,
            } => write!(
                f,
                "candidate {} relates to episode {}, absent from truths",
                hex32(candidate_id),
                hex32(episode_id)
            ),
            Self::DelayArithmeticOverflow { candidate_id } => write!(
                f,
                "candidate {} delay-bars arithmetic overflowed",
                hex32(candidate_id)
            ),
        }
    }
}

impl std::error::Error for CaptureError {}

fn hex32(digest: &[u8; 32]) -> String {
    use std::fmt::Write as _;
    digest
        .iter()
        .fold(String::with_capacity(64), |mut out, byte| {
            write!(out, "{byte:02x}").expect("writing to a String cannot fail");
            out
        })
}

/// The full CONV §8 classification of one `(session, stream)` group.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CaptureResult {
    pub truth_outcomes: Vec<TruthOutcome>,
    pub candidate_assignments: Vec<CandidateAssignment>,
    pub counts: CaptureCounts,
}

/// Internal, pre-dedup classification of one candidate against the truth it
/// singly relates to (or none/many).
#[derive(Clone, Copy)]
enum Preliminary {
    Timely {
        episode_id: [u8; 32],
        delay_bars: u32,
    },
    Late {
        delay_bars: u32,
    },
    ExactNotPostPlateau,
    PostPlateauExactNotScorable,
    ConflictingTruthMemberships,
    UnmatchedEventScorable,
    UnmatchedCloseNonScorable,
}

/// The read-only lookups shared by every step after preliminary
/// classification (bundled to keep helper-function signatures under
/// `clippy::pedantic`'s argument-count lint).
struct Joins<'a> {
    edges: &'a [RelationEdge],
    outcomes: &'a [CandidateOutcome],
    outcome_index: HashMap<[u8; 32], usize>,
    preliminary: Vec<Preliminary>,
}

impl Joins<'_> {
    fn outcome_for(&self, candidate_id: &[u8; 32]) -> &CandidateOutcome {
        let position = *self
            .outcome_index
            .get(candidate_id)
            .expect("every edge's candidate_id was resolved while building outcome_index");
        &self.outcomes[position]
    }
}

/// Builds the `episode_id -> index` lookup for `truths`, rejecting a
/// duplicate `episode_id`.
fn index_truths(truths: &[TruthRow]) -> Result<HashMap<[u8; 32], usize>, CaptureError> {
    let mut index = HashMap::with_capacity(truths.len());
    for (position, truth) in truths.iter().enumerate() {
        if index.insert(truth.episode_id, position).is_some() {
            return Err(CaptureError::DuplicateTruthEpisode(truth.episode_id));
        }
    }
    Ok(index)
}

/// Builds the `candidate_id -> index` lookup for `outcomes`, checking every
/// row's `(session, stream)` and rejecting a duplicate `candidate_id`.
fn index_outcomes(
    session: SessionId,
    stream: &StreamId,
    outcomes: &[CandidateOutcome],
) -> Result<HashMap<[u8; 32], usize>, CaptureError> {
    let mut index = HashMap::with_capacity(outcomes.len());
    for (position, outcome) in outcomes.iter().enumerate() {
        if outcome.session != session {
            return Err(CaptureError::CandidateOutcomeSessionMismatch(
                outcome.candidate_id,
            ));
        }
        if outcome.stream != *stream {
            return Err(CaptureError::CandidateOutcomeStreamMismatch(
                outcome.candidate_id,
            ));
        }
        if index.insert(outcome.candidate_id, position).is_some() {
            return Err(CaptureError::DuplicateCandidateOutcome(
                outcome.candidate_id,
            ));
        }
    }
    Ok(index)
}

/// Validates every edge's `(session, stream)` and uniqueness, then builds
/// the reverse `episode_id -> candidate indices` index used by the unhit-
/// truth `r` filter.
fn index_edges(
    session: SessionId,
    stream: &StreamId,
    edges: &[RelationEdge],
) -> Result<HashMap<[u8; 32], Vec<usize>>, CaptureError> {
    let mut related_candidates: HashMap<[u8; 32], Vec<usize>> = HashMap::new();
    let mut seen_candidates: HashSet<[u8; 32]> = HashSet::with_capacity(edges.len());
    for (position, edge) in edges.iter().enumerate() {
        if edge.session != session {
            return Err(CaptureError::RelationEdgeSessionMismatch(edge.candidate_id));
        }
        if edge.stream != *stream {
            return Err(CaptureError::RelationEdgeStreamMismatch(edge.candidate_id));
        }
        if !seen_candidates.insert(edge.candidate_id) {
            return Err(CaptureError::DuplicateRelationEdge(edge.candidate_id));
        }
        for episode_id in &edge.related_episode_ids {
            related_candidates
                .entry(*episode_id)
                .or_default()
                .push(position);
        }
    }
    Ok(related_candidates)
}

/// Requires that every outcome's `candidate_id` also appears among `edges`
/// (the reverse of the edge-without-outcome check in [`classify`]'s main
/// loop): the candidate-grain input contract requires `edges` to carry a
/// (possibly zero-relation) row for every emitted candidate, so an
/// outcome-only key means the edge projection itself is incomplete
/// (`events23_sol_adversarial.md` finding 3 -- "a scorable outcome with no
/// relation-edge row is silently dropped from burden"). Never silently
/// dropped: a typed [`CaptureError::MissingRelationEdge`] instead.
fn require_edge_for_every_outcome(
    edges: &[RelationEdge],
    outcomes: &[CandidateOutcome],
) -> Result<(), CaptureError> {
    let edge_ids: HashSet<[u8; 32]> = edges.iter().map(|edge| edge.candidate_id).collect();
    for outcome in outcomes {
        if !edge_ids.contains(&outcome.candidate_id) {
            return Err(CaptureError::MissingRelationEdge(outcome.candidate_id));
        }
    }
    Ok(())
}

/// Classifies one candidate (CONV §8 rules 3-5; archive
/// `intrabar_event_adequacy.rs:2010-2051`).
fn classify_candidate(
    edge: &RelationEdge,
    outcome: &CandidateOutcome,
    truths: &[TruthRow],
    truth_index: &HashMap<[u8; 32], usize>,
) -> Result<Preliminary, CaptureError> {
    Ok(match edge.related_episode_ids.as_slice() {
        [] if outcome.event_scorable() => Preliminary::UnmatchedEventScorable,
        [] => Preliminary::UnmatchedCloseNonScorable,
        [_first, _second, ..] => Preliminary::ConflictingTruthMemberships,
        [episode_id] => {
            let truth_position =
                *truth_index
                    .get(episode_id)
                    .ok_or(CaptureError::UnknownRelatedEpisode {
                        candidate_id: edge.candidate_id,
                        episode_id: *episode_id,
                    })?;
            let truth = &truths[truth_position];
            let post_plateau = outcome.confirmation_group_ordinal
                > truth.plateau_last_group_ordinal
                && outcome.visible_ts_ns > truth.plateau_last_ns;
            if !post_plateau {
                Preliminary::ExactNotPostPlateau
            } else if !outcome.event_scorable() {
                Preliminary::PostPlateauExactNotScorable
            } else {
                let visible_bar = outcome
                    .visible_bar_ordinal
                    .expect("event_scorable() guarantees Some");
                let delay_bars = i64::try_from(visible_bar)
                    .ok()
                    .and_then(|v| v.checked_sub(truth.plateau_bar_ordinal))
                    .and_then(|d| u32::try_from(d).ok())
                    .ok_or(CaptureError::DelayArithmeticOverflow {
                        candidate_id: edge.candidate_id,
                    })?;
                if delay_bars <= MAX_TIMELY_DELAY_BARS {
                    Preliminary::Timely {
                        episode_id: *episode_id,
                        delay_bars,
                    }
                } else {
                    Preliminary::Late { delay_bars }
                }
            }
        }
    })
}

/// Dedup (CONV §8 rule 6): earliest-timely wins per truth, tie-break
/// `(visible_ts_ns, confirmation_group_ordinal, registration_ordinal)`
/// ascending. The archived engine's own last-resort field
/// (`archive/rust/iwm_atlas_v2/src/intrabar_event_adequacy.rs:2283-2290`)
/// was the candidate's own digest; `events23_sol_adversarial.md` finding 4
/// rejected that as a non-scientific hash tie-break -- CONV §8 rule 6 and
/// the house rule "scientific choices never tie-break by hash/ID" require
/// the frozen candidate registration/file order instead (never a digest).
fn resolve_winners(joins: &Joins<'_>) -> HashMap<[u8; 32], usize> {
    let mut timely_by_truth: HashMap<[u8; 32], Vec<usize>> = HashMap::new();
    for (position, prelim) in joins.preliminary.iter().enumerate() {
        if let Preliminary::Timely { episode_id, .. } = prelim {
            timely_by_truth
                .entry(*episode_id)
                .or_default()
                .push(position);
        }
    }
    let mut winner_by_truth = HashMap::with_capacity(timely_by_truth.len());
    for (episode_id, mut candidates) in timely_by_truth {
        candidates.sort_by_key(|&position| {
            let outcome = joins.outcome_for(&joins.edges[position].candidate_id);
            (
                outcome.visible_ts_ns,
                outcome.confirmation_group_ordinal,
                joins.edges[position].registration_ordinal,
            )
        });
        winner_by_truth.insert(episode_id, candidates[0]);
    }
    winner_by_truth
}

/// Builds the final per-candidate assignments, promoting each
/// [`Preliminary::Timely`] to [`CandidateAssignmentState::UniqueTimelyHit`]
/// or [`CandidateAssignmentState::DuplicateTimely`] per `winner_by_truth`,
/// and tallies every count that is a pure function of one candidate.
fn build_candidate_assignments(
    joins: &Joins<'_>,
    winner_by_truth: &HashMap<[u8; 32], usize>,
    counts: &mut CaptureCounts,
) -> Vec<CandidateAssignment> {
    let mut assignments = Vec::with_capacity(joins.edges.len());
    for (position, edge) in joins.edges.iter().enumerate() {
        let (state, delay_bars) = match &joins.preliminary[position] {
            Preliminary::Timely {
                episode_id,
                delay_bars,
            } if winner_by_truth.get(episode_id) == Some(&position) => {
                counts.unique_timely_hits += 1;
                match *delay_bars {
                    0 => counts.delay_0_hits += 1,
                    1 => counts.delay_1_hits += 1,
                    2 => counts.delay_2_hits += 1,
                    _ => unreachable!("Timely guarantees delay_bars <= MAX_TIMELY_DELAY_BARS"),
                }
                (CandidateAssignmentState::UniqueTimelyHit, Some(*delay_bars))
            }
            Preliminary::Timely { delay_bars, .. } => {
                counts.duplicate_timely_candidates += 1;
                (CandidateAssignmentState::DuplicateTimely, Some(*delay_bars))
            }
            Preliminary::Late { delay_bars } => {
                counts.late_candidates += 1;
                (
                    CandidateAssignmentState::PostPlateauExactLate,
                    Some(*delay_bars),
                )
            }
            Preliminary::ExactNotPostPlateau => {
                counts.exact_not_post_plateau_candidates += 1;
                (CandidateAssignmentState::ExactNotPostPlateau, None)
            }
            Preliminary::PostPlateauExactNotScorable => {
                counts.post_plateau_not_scorable_candidates += 1;
                (CandidateAssignmentState::PostPlateauExactNotScorable, None)
            }
            Preliminary::ConflictingTruthMemberships => {
                counts.conflicting_candidates += 1;
                (CandidateAssignmentState::ConflictingTruthMemberships, None)
            }
            Preliminary::UnmatchedEventScorable => {
                counts.unmatched_event_scorable_candidates += 1;
                (CandidateAssignmentState::UnmatchedEventScorable, None)
            }
            Preliminary::UnmatchedCloseNonScorable => {
                counts.unmatched_close_non_scorable_candidates += 1;
                (CandidateAssignmentState::UnmatchedCloseNonScorable, None)
            }
        };
        assignments.push(CandidateAssignment {
            candidate_id: edge.candidate_id,
            state,
            delay_bars,
        });
    }
    assignments
}

/// Classifies one unhit truth's miss reason via the registered `r / e / p /
/// s` relation-candidate filters (archive
/// `intrabar_event_adequacy.rs:2217-2234,2473-2506`), and tallies the
/// matching `miss_*` count.
fn classify_unhit_truth(
    truth: &TruthRow,
    joins: &Joins<'_>,
    related_candidates: &HashMap<[u8; 32], Vec<usize>>,
    counts: &mut CaptureCounts,
) -> TruthMissReason {
    let related = related_candidates
        .get(&truth.episode_id)
        .map_or(&[][..], Vec::as_slice);
    let nonconflicting: Vec<usize> = related
        .iter()
        .copied()
        .filter(|&position| joins.edges[position].related_episode_ids.len() == 1)
        .collect();
    let post_plateau: Vec<usize> = nonconflicting
        .iter()
        .copied()
        .filter(|&position| {
            let outcome = joins.outcome_for(&joins.edges[position].candidate_id);
            outcome.confirmation_group_ordinal > truth.plateau_last_group_ordinal
                && outcome.visible_ts_ns > truth.plateau_last_ns
        })
        .collect();
    let any_scorable = post_plateau.iter().any(|&position| {
        joins
            .outcome_for(&joins.edges[position].candidate_id)
            .event_scorable()
    });

    if related.is_empty() {
        counts.miss_no_exact_relation += 1;
        TruthMissReason::NoExactRelation
    } else if nonconflicting.is_empty() {
        counts.miss_conflicting_relation_only += 1;
        TruthMissReason::ConflictingRelationOnly
    } else if post_plateau.is_empty() {
        counts.miss_exact_not_post_plateau += 1;
        TruthMissReason::ExactNotPostPlateau
    } else if !any_scorable {
        counts.miss_post_plateau_not_scorable += 1;
        TruthMissReason::PostPlateauExactNotScorable
    } else {
        counts.miss_post_plateau_late += 1;
        TruthMissReason::PostPlateauExactLate
    }
}

/// Builds the final per-truth outcomes (hit via `winner_by_truth`, else the
/// registered miss-reason classification).
fn build_truth_outcomes(
    truths: &[TruthRow],
    joins: &Joins<'_>,
    winner_by_truth: &HashMap<[u8; 32], usize>,
    related_candidates: &HashMap<[u8; 32], Vec<usize>>,
    counts: &mut CaptureCounts,
) -> Vec<TruthOutcome> {
    let mut truth_outcomes = Vec::with_capacity(truths.len());
    for truth in truths {
        let outcome = if let Some(&winner_position) = winner_by_truth.get(&truth.episode_id) {
            let Preliminary::Timely { delay_bars, .. } = joins.preliminary[winner_position] else {
                unreachable!("winner_by_truth only ever indexes a Preliminary::Timely entry");
            };
            TruthCaptureOutcome::Hit {
                candidate_id: joins.edges[winner_position].candidate_id,
                delay_bars,
            }
        } else {
            TruthCaptureOutcome::Miss(classify_unhit_truth(
                truth,
                joins,
                related_candidates,
                counts,
            ))
        };
        truth_outcomes.push(TruthOutcome {
            episode_id: truth.episode_id,
            outcome,
        });
    }
    truth_outcomes
}

/// Classifies one `(session, stream)` group per CONV §8 (rules 3-6) plus the
/// full CONV §6c taxonomy. See the module doc for the input contract.
///
/// Declared complexity: O(`truths.len()` + `edges.len()` · log(max relation
/// fan-out)) -- one hash lookup per edge/outcome (amortized O(1)), one sort
/// per truth of its own timely candidates (bounded by real-scale relation
/// multiplicity, never by the full session), one linear scan of the
/// reverse relation index per unhit truth.
///
/// # Errors
///
/// Returns [`CaptureError`] if any input row's `(session, stream)` does not
/// match the ones passed in, any `candidate_id`/`episode_id` is duplicated
/// where uniqueness is required, an edge relates to an episode absent from
/// `truths`, an edge has no matching outcome, an outcome has no matching
/// edge, or delay-bar arithmetic overflows.
pub fn classify(
    session: SessionId,
    stream: &StreamId,
    truths: &[TruthRow],
    edges: &[RelationEdge],
    outcomes: &[CandidateOutcome],
) -> Result<CaptureResult, CaptureError> {
    let truth_index = index_truths(truths)?;
    let outcome_index = index_outcomes(session, stream, outcomes)?;
    let related_candidates = index_edges(session, stream, edges)?;
    require_edge_for_every_outcome(edges, outcomes)?;

    let mut preliminary = Vec::with_capacity(edges.len());
    for edge in edges {
        let outcome_position = *outcome_index
            .get(&edge.candidate_id)
            .ok_or(CaptureError::MissingOutcome(edge.candidate_id))?;
        preliminary.push(classify_candidate(
            edge,
            &outcomes[outcome_position],
            truths,
            &truth_index,
        )?);
    }

    let joins = Joins {
        edges,
        outcomes,
        outcome_index,
        preliminary,
    };

    let winner_by_truth = resolve_winners(&joins);
    let mut counts = CaptureCounts {
        confirmed_truths: truths.len() as u64,
        ..CaptureCounts::default()
    };
    let candidate_assignments = build_candidate_assignments(&joins, &winner_by_truth, &mut counts);
    let truth_outcomes = build_truth_outcomes(
        truths,
        &joins,
        &winner_by_truth,
        &related_candidates,
        &mut counts,
    );

    Ok(CaptureResult {
        truth_outcomes,
        candidate_assignments,
        counts,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::truth::Side;

    const SESSION: SessionId = SessionId {
        year: 2022,
        ordinal: 0,
    };

    fn stream() -> StreamId {
        StreamId::new("reversal_confirm", 40)
    }

    fn truth(
        episode_id: [u8; 32],
        plateau_bar: i64,
        plateau_group: u64,
        plateau_ns: i64,
    ) -> TruthRow {
        TruthRow {
            episode_id,
            session: SESSION,
            anchor_bps: 40,
            continuity_ordinal: 0,
            side: Side::Low,
            price_u6: 1_000_000,
            plateau_last_group_ordinal: plateau_group,
            plateau_bar_ordinal: plateau_bar,
            plateau_last_ns: plateau_ns,
            coincident_ambiguities: 0,
        }
    }

    /// `registration_ordinal` is the third argument; tests that don't
    /// exercise the tie-break pass `0` for every candidate unless a
    /// specific registration order is under test.
    fn edge(
        candidate_id: [u8; 32],
        registration_ordinal: u64,
        related: &[[u8; 32]],
    ) -> RelationEdge {
        RelationEdge {
            session: SESSION,
            stream: stream(),
            candidate_id,
            registration_ordinal,
            member_signal_ids: Vec::new(),
            related_episode_ids: related.to_vec(),
        }
    }

    fn outcome(
        candidate_id: [u8; 32],
        confirmation_group_ordinal: u64,
        visible_ts_ns: i64,
        visible_bar_ordinal: Option<u64>,
        session_end_ns: i64,
    ) -> CandidateOutcome {
        CandidateOutcome {
            session: SESSION,
            stream: stream(),
            candidate_id,
            confirmation_group_ordinal,
            visible_ts_ns,
            visible_bar_ordinal,
            session_end_ns,
        }
    }

    fn id(byte: u8) -> [u8; 32] {
        [byte; 32]
    }

    // ------------------------- simple unique hit -------------------------

    #[test]
    fn single_timely_candidate_is_a_unique_hit_with_the_right_delay() {
        let t = truth(id(1), 10, 100, 1_000);
        let e = edge(id(2), 0, &[id(1)]);
        let o = outcome(id(2), 101, 1_001, Some(11), 1_000_000);
        let result = classify(SESSION, &stream(), &[t], &[e], &[o]).expect("classify");

        assert_eq!(
            result.truth_outcomes[0].outcome,
            TruthCaptureOutcome::Hit {
                candidate_id: id(2),
                delay_bars: 1,
            }
        );
        assert_eq!(
            result.candidate_assignments[0].state,
            CandidateAssignmentState::UniqueTimelyHit
        );
        assert_eq!(result.candidate_assignments[0].delay_bars, Some(1));
        assert_eq!(result.counts.unique_timely_hits, 1);
        assert_eq!(result.counts.delay_1_hits, 1);
        assert_eq!(result.counts.delay_0_hits, 0);
    }

    // ------------------------- dedup / duplicate -------------------------

    #[test]
    fn dedup_earliest_visible_ts_wins_the_later_one_is_a_duplicate() {
        let t = truth(id(1), 10, 100, 1_000);
        // Candidate A arrives later (visible_ts 2_000), candidate B earlier
        // (visible_ts 1_500); both timely (delay 1 and 0 respectively).
        let e_a = edge(id(2), 0, &[id(1)]);
        let e_b = edge(id(3), 1, &[id(1)]);
        let o_a = outcome(id(2), 101, 2_000, Some(11), 1_000_000);
        let o_b = outcome(id(3), 101, 1_500, Some(10), 1_000_000);
        let result =
            classify(SESSION, &stream(), &[t], &[e_a, e_b], &[o_a, o_b]).expect("classify");

        // B (index 1) is earlier -> winner.
        assert_eq!(
            result.candidate_assignments[0].state,
            CandidateAssignmentState::DuplicateTimely
        );
        assert_eq!(
            result.candidate_assignments[1].state,
            CandidateAssignmentState::UniqueTimelyHit
        );
        assert_eq!(
            result.truth_outcomes[0].outcome,
            TruthCaptureOutcome::Hit {
                candidate_id: id(3),
                delay_bars: 0,
            }
        );
        assert_eq!(result.counts.unique_timely_hits, 1);
        assert_eq!(result.counts.duplicate_timely_candidates, 1);
    }

    #[test]
    fn dedup_tie_break_on_visible_ts_falls_to_confirmation_group_ordinal_next() {
        let t = truth(id(1), 10, 100, 1_000);
        // Same visible_ts_ns; A has the higher confirmation_group_ordinal so
        // B (lower) wins, regardless of registration_ordinal or candidate id.
        let e_a = edge(id(9), 0, &[id(1)]);
        let e_b = edge(id(2), 1, &[id(1)]);
        let o_a = outcome(id(9), 200, 1_500, Some(10), 1_000_000);
        let o_b = outcome(id(2), 150, 1_500, Some(10), 1_000_000);
        let result =
            classify(SESSION, &stream(), &[t], &[e_a, e_b], &[o_a, o_b]).expect("classify");
        assert_eq!(
            result.truth_outcomes[0].outcome,
            TruthCaptureOutcome::Hit {
                candidate_id: id(2),
                delay_bars: 0,
            }
        );
    }

    #[test]
    fn dedup_tie_break_uses_registration_ordinal_never_digest_order() {
        // Sol#4 (P1) concrete failure scenario: two candidates tie on both
        // visible_ts_ns and confirmation_group_ordinal. Candidate `id(2)`
        // has the lexicographically SMALLER digest (a digest tie-break
        // would pick it) but registers SECOND (registration_ordinal 1);
        // candidate `id(9)` has the larger digest but registers FIRST
        // (registration_ordinal 0) -- the frozen file order, the only
        // permitted tie-break authority.
        let t = truth(id(1), 10, 100, 1_000);
        let e_smaller_digest_later_registration = edge(id(2), 1, &[id(1)]);
        let e_larger_digest_earlier_registration = edge(id(9), 0, &[id(1)]);
        let o_a = outcome(id(2), 150, 1_500, Some(10), 1_000_000);
        let o_b = outcome(id(9), 150, 1_500, Some(10), 1_000_000);
        let result = classify(
            SESSION,
            &stream(),
            &[t],
            &[
                e_smaller_digest_later_registration,
                e_larger_digest_earlier_registration,
            ],
            &[o_a, o_b],
        )
        .expect("classify");

        // Registration order picks id(9) (registration_ordinal 0); a digest
        // tie-break would instead have picked id(2) (the smaller digest).
        assert_eq!(
            result.truth_outcomes[0].outcome,
            TruthCaptureOutcome::Hit {
                candidate_id: id(9),
                delay_bars: 0,
            }
        );
        assert_eq!(
            result.candidate_assignments[1].state,
            CandidateAssignmentState::UniqueTimelyHit
        );
        assert_eq!(
            result.candidate_assignments[0].state,
            CandidateAssignmentState::DuplicateTimely
        );
    }

    // ------------------------- delay boundary -------------------------

    #[test]
    fn delay_of_three_is_late_not_timely() {
        let t = truth(id(1), 10, 100, 1_000);
        let e = edge(id(2), 0, &[id(1)]);
        let o = outcome(id(2), 101, 1_001, Some(13), 1_000_000);
        let result = classify(SESSION, &stream(), &[t], &[e], &[o]).expect("classify");
        assert_eq!(
            result.candidate_assignments[0].state,
            CandidateAssignmentState::PostPlateauExactLate
        );
        assert_eq!(
            result.truth_outcomes[0].outcome,
            TruthCaptureOutcome::Miss(TruthMissReason::PostPlateauExactLate)
        );
        assert_eq!(result.counts.late_candidates, 1);
        assert_eq!(result.counts.miss_post_plateau_late, 1);
    }

    // ------------------------- unmatched (burden) -------------------------

    #[test]
    fn unmatched_scorable_candidate_counts_toward_burden() {
        let t = truth(id(1), 10, 100, 1_000);
        let e = edge(id(2), 0, &[]);
        let o = outcome(id(2), 5, 500, Some(3), 1_000_000);
        let result = classify(SESSION, &stream(), &[t], &[e], &[o]).expect("classify");
        assert_eq!(
            result.candidate_assignments[0].state,
            CandidateAssignmentState::UnmatchedEventScorable
        );
        assert_eq!(result.counts.burden(), 1);
        assert_eq!(
            result.truth_outcomes[0].outcome,
            TruthCaptureOutcome::Miss(TruthMissReason::NoExactRelation)
        );
    }

    #[test]
    fn unmatched_close_non_scorable_candidate_does_not_count_toward_burden() {
        let e = edge(id(2), 0, &[]);
        // visible_ts_ns == session_end_ns: not scorable (CONV §4/§10).
        let o = outcome(id(2), 5, 1_000_000, Some(3), 1_000_000);
        let result = classify(SESSION, &stream(), &[], &[e], &[o]).expect("classify");
        assert_eq!(
            result.candidate_assignments[0].state,
            CandidateAssignmentState::UnmatchedCloseNonScorable
        );
        assert_eq!(result.counts.burden(), 0);
        assert_eq!(result.counts.unmatched_close_non_scorable_candidates, 1);
    }

    // ------------------------- registered candidate grain (Sol#1 P0) -----

    #[test]
    fn a_shared_member_signal_across_two_candidates_never_collides_at_candidate_grain() {
        // Sol#1 (P0) concrete failure scenario, verbatim: in one stream,
        // candidate C1 has members {s1,s2} and relates to truth T;
        // candidate C2 has sole member {s1} and no relation. At registered
        // candidate grain this is one timely candidate for T plus one
        // unmatched scorable candidate (hit 1, duplicate 0, burden 1) -- a
        // signal-keyed representation would either fabricate a spurious
        // duplicate (emitting s1 twice) or erase C2's burden (E16's
        // per-signal union making s1 related to T). Neither happens here:
        // C1 and C2 are distinct candidate rows even though they share
        // member signal s1.
        let truth_t = truth(id(1), 10, 100, 1_000);
        let s1 = id(50);
        let s2 = id(51);
        let c1 = RelationEdge {
            session: SESSION,
            stream: stream(),
            candidate_id: id(2),
            registration_ordinal: 0,
            member_signal_ids: vec![s1, s2],
            related_episode_ids: vec![id(1)],
        };
        let c2 = RelationEdge {
            session: SESSION,
            stream: stream(),
            candidate_id: id(3),
            registration_ordinal: 1,
            member_signal_ids: vec![s1],
            related_episode_ids: vec![],
        };
        let o1 = outcome(id(2), 101, 1_001, Some(11), 1_000_000);
        let o2 = outcome(id(3), 5, 500, Some(3), 1_000_000);

        let result =
            classify(SESSION, &stream(), &[truth_t], &[c1, c2], &[o1, o2]).expect("classify");

        assert_eq!(
            result.truth_outcomes[0].outcome,
            TruthCaptureOutcome::Hit {
                candidate_id: id(2),
                delay_bars: 1,
            }
        );
        assert_eq!(result.counts.unique_timely_hits, 1);
        assert_eq!(result.counts.duplicate_timely_candidates, 0);
        assert_eq!(result.counts.burden(), 1);
        assert_eq!(
            result.candidate_assignments[0].state,
            CandidateAssignmentState::UniqueTimelyHit
        );
        assert_eq!(
            result.candidate_assignments[1].state,
            CandidateAssignmentState::UnmatchedEventScorable
        );
    }

    // ------------------------- conflict -------------------------

    #[test]
    fn candidate_related_to_two_truths_is_conflicting_and_never_a_hit() {
        let t1 = truth(id(1), 10, 100, 1_000);
        let t2 = truth(id(2), 10, 100, 1_000);
        let e = edge(id(3), 0, &[id(1), id(2)]);
        let o = outcome(id(3), 101, 1_001, Some(11), 1_000_000);
        let result = classify(SESSION, &stream(), &[t1, t2], &[e], &[o]).expect("classify");
        assert_eq!(
            result.candidate_assignments[0].state,
            CandidateAssignmentState::ConflictingTruthMemberships
        );
        assert_eq!(result.counts.conflicting_candidates, 1);
        // Both truths miss: their only relation is the conflicting candidate.
        for outcome in &result.truth_outcomes {
            assert_eq!(
                outcome.outcome,
                TruthCaptureOutcome::Miss(TruthMissReason::ConflictingRelationOnly)
            );
        }
    }

    // ------------------------- no exact relation -------------------------

    #[test]
    fn truth_with_no_related_candidate_at_all_is_no_exact_relation() {
        let t = truth(id(1), 10, 100, 1_000);
        let result = classify(SESSION, &stream(), &[t], &[], &[]).expect("classify");
        assert_eq!(
            result.truth_outcomes[0].outcome,
            TruthCaptureOutcome::Miss(TruthMissReason::NoExactRelation)
        );
        assert_eq!(result.counts.miss_no_exact_relation, 1);
    }

    // ------------------------- not post-plateau -------------------------

    #[test]
    fn candidate_at_or_before_the_plateau_is_exact_not_post_plateau() {
        let t = truth(id(1), 10, 100, 1_000);
        // confirmation_group_ordinal (100) is NOT strictly greater than the
        // truth's plateau_last_group_ordinal (100).
        let e = edge(id(2), 0, &[id(1)]);
        let o = outcome(id(2), 100, 1_001, Some(11), 1_000_000);
        let result = classify(SESSION, &stream(), &[t], &[e], &[o]).expect("classify");
        assert_eq!(
            result.candidate_assignments[0].state,
            CandidateAssignmentState::ExactNotPostPlateau
        );
        assert_eq!(
            result.truth_outcomes[0].outcome,
            TruthCaptureOutcome::Miss(TruthMissReason::ExactNotPostPlateau)
        );
    }

    // ------------------------- post-plateau, not scorable -------------------------

    #[test]
    fn post_plateau_candidate_with_no_bar_ordinal_is_not_scorable() {
        let t = truth(id(1), 10, 100, 1_000);
        let e = edge(id(2), 0, &[id(1)]);
        let o = outcome(id(2), 101, 1_001, None, 1_000_000);
        let result = classify(SESSION, &stream(), &[t], &[e], &[o]).expect("classify");
        assert_eq!(
            result.candidate_assignments[0].state,
            CandidateAssignmentState::PostPlateauExactNotScorable
        );
        assert_eq!(
            result.truth_outcomes[0].outcome,
            TruthCaptureOutcome::Miss(TruthMissReason::PostPlateauExactNotScorable)
        );
    }

    // ------------------------- error contract -------------------------

    #[test]
    fn edge_referencing_an_unknown_episode_is_a_typed_error_not_a_panic() {
        let e = edge(id(2), 0, &[id(99)]);
        let o = outcome(id(2), 101, 1_001, Some(11), 1_000_000);
        let error = classify(SESSION, &stream(), &[], &[e], &[o]).unwrap_err();
        assert_eq!(
            error,
            CaptureError::UnknownRelatedEpisode {
                candidate_id: id(2),
                episode_id: id(99),
            }
        );
    }

    #[test]
    fn edge_with_no_matching_outcome_is_a_typed_error() {
        let t = truth(id(1), 10, 100, 1_000);
        let e = edge(id(2), 0, &[id(1)]);
        let error = classify(SESSION, &stream(), &[t], &[e], &[]).unwrap_err();
        assert_eq!(error, CaptureError::MissingOutcome(id(2)));
    }

    #[test]
    fn outcome_with_no_relation_edge_row_is_a_typed_error_not_a_silent_burden_drop() {
        // Sol#3 (P1) concrete failure scenario, verbatim: pass truths=[],
        // edges=[], and one scorable outcome. The candidate-grain input
        // contract requires `edges` to carry a (possibly zero-relation) row
        // for every emitted candidate, so an outcome-only key means the
        // edge projection itself is incomplete -- a typed error, never
        // success with burden 0 and the outcome silently dropped.
        let o = outcome(id(2), 5, 500, Some(3), 1_000_000);
        let error = classify(SESSION, &stream(), &[], &[], &[o]).unwrap_err();
        assert_eq!(error, CaptureError::MissingRelationEdge(id(2)));
    }
}
