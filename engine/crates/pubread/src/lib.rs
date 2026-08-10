//! Pinned reader for the existing REL037 event publication
//! (`artifacts/runs/e1_rel037_verified_event/event_publication/`).
//!
//! # Integrity model
//!
//! Two independent checks, both plain sha256 content hashing:
//!
//! 1. [`PinnedPublication::open`] hashes `manifest.tsv` itself and compares
//!    it to the caller's pin. If that doesn't match, nothing else in the
//!    directory is trusted.
//! 2. [`PinnedPublication::verify_leaf`] (or [`PinnedPublication::verify_all`]
//!    for every leaf, in parallel) streams a leaf file and compares its byte
//!    size, sha256, and row count to what the manifest recorded for it.
//!
//! No other manifest field is validated. The producer's other recorded
//! identities (`kernel_law_sha256`, `rustc_version`, and so on) are carried
//! as opaque strings, reachable via [`PinnedPublication::recorded`], for
//! callers that want to inspect or log them — this reader takes no position
//! on them. No closure-salted identity, no schema-root recomputation: a leaf
//! is valid iff its bytes match its own manifest entry.
//!
//! # Typed streaming readers
//!
//! [`PinnedPublication::day_roots`], [`PinnedPublication::event_signals`],
//! [`PinnedPublication::assignments`], and
//! [`PinnedPublication::truth_coverage`] each return a hand-written,
//! serde-free `Iterator` that parses one line at a time — never the whole
//! file (`event_signals.tsv` and `assignments.tsv` are 14 GB and 21 GB).
//! Every column is typed; see `crate::leaves` and `crate::rows` for the
//! parsing conventions (`"NA"` as null, hex digests as `[u8; 32]`,
//! enum-shaped columns carried as `String`).

mod digest;
mod error;
mod leaves;
mod manifest;
mod rows;

pub use digest::{StreamDigest, stream_digest_with_progress};
pub use error::{PubReadError, Result};
pub use leaves::{
    Assignment, AssignmentReader, DayRoot, DayRootReader, EventSignal, EventSignalReader,
    TruthCoverage, TruthCoverageReader,
};
pub use manifest::{LeafMeta, PinnedPublication};

/// Pinned sha256 of `manifest.tsv` in the verified REL037 event publication
/// (`artifacts/runs/e1_rel037_verified_event/event_publication/`). External
/// input authority pin (`docs/engine_rebuild_r1_design.md`).
pub const EXPECTED_MANIFEST_SHA256: &str =
    "29bed27c5d1f99af16dd915466ee24283f9a701c60e0601169e02bbb0e86c578";
