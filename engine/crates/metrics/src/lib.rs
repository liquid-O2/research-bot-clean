//! Stage-1 gate metrics: truth capture, regime slicing, frontier
//! non-domination, and the proposal bank. Design authority:
//! `docs/specs/events3_design_v1.md` §C, as amended (and superseded on
//! conflict) by `docs/specs/events3_design_amendment_v2.md` §§A1, A8, A9;
//! the capture rule itself is `docs/specs/registered_conventions_extract_v1.md`
//! §8, verbatim.
//!
//! # Scope and non-scope
//!
//! This crate computes gate quantities from typed input rows; it has **zero**
//! dependency on `labels`, `pubread`, or `corpus`. Wiring these typed inputs
//! from the real published leaves (`truth_coverage.tsv`, the A10
//! `truth_relation_projection.parquet` leaf, `event_index.parquet`,
//! `regimes.parquet`) is a Wiring-phase / EVENTS.4 deliverable, not this
//! crate's. This crate also does not write any TSV/parquet leaf itself
//! (that is the `publish` crate's job, per design brief §D) and does not
//! compute the LCB (that is the pinned Python estimator's job, per A1/A9 --
//! this crate only emits/consumes its input and output).
//!
//! # Modules
//!
//! - [`session`]: shared session/stream identity types.
//! - [`truth`]: the truth-row input type (CONV §8 population).
//! - [`capture`]: CONV §8 truth capture (keyed relation edges are an input;
//!   post-plateau/scorable/timely-delay/dedup are computed here).
//! - [`session_recall`]: A1's `session_recall.tsv` row construction (never
//!   pre-blocks).
//! - [`regime`]: A8's tercile-cut order statistic + tie rule, and the exact
//!   TREND/COMPRESSED/RANGE predicate.
//! - [`regime_slice`]: A8's 18-cell regime-sliced capture cross-tab.
//! - [`frontier`]: recall-vs-burden non-domination.
//! - [`bank`]: A9's eligibility-first proposal bank selection.

pub mod bank;
pub mod capture;
pub mod frontier;
pub mod regime;
pub mod regime_slice;
pub mod session;
pub mod session_recall;
pub mod truth;

pub use bank::{
    BankError, BankState, EstimatorVerdict, InvalidLcbCanonicalError,
    MismatchedTruthsDenominatorError, ProposalBank, StreamLcb, best_eligible_stream, build_bank,
    is_eligible as bank_is_eligible,
};
pub use capture::{
    CandidateAssignment, CandidateAssignmentState, CandidateOutcome, CaptureCounts, CaptureError,
    CaptureResult, RelationEdge, TruthCaptureOutcome, TruthMissReason, TruthOutcome,
    classify as classify_capture,
};
pub use frontier::{StreamPoint, compare_recall, dominates, non_dominated};
pub use regime::{
    Tercile, TrendRangeState, classify_tercile, classify_trend_range, compare_rate, tercile_cuts,
};
pub use regime_slice::{
    RegimeBar, RegimePopulationCuts, RegimeSliceCell, RegimeSliceKey, RegimeSliceResult,
    build_regime_slices,
};
pub use session::{SessionId, SessionType, StreamId, StreamIdParseError};
pub use session_recall::{
    DuplicateSessionError, SessionRecallRow, pooled_totals, session_recall_rows,
};
pub use truth::{Side, TruthRow, pooled_ambiguity_count};
