//! Stage-1 publication utilities (design brief §D, amended by A10/A12, and
//! by the EVENTS.2+3 consolidated fix batch's L2/L7 lane): the pinned
//! parquet leaf writer, this crate's own manifest, the
//! fresh-sibling-directory atomic publish helper, the `run_receipt.json`
//! writer/reader, and the source-free verifier core.
//!
//! This crate does not itself run the stage-1 pipeline or decide what goes
//! in each leaf — that's the run scheduler (`stage1 run`, a later wave) and
//! `metrics` (gate quantities, a concurrent wave). What's here is meant to
//! be reused by both:
//!
//! 1. [`atomic::PublishStaging::begin`] a fresh sibling staging directory
//!    for the run's final publication path.
//! 2. For each parquet leaf, [`parquet_leaf::LeafWriter::create`] once,
//!    [`parquet_leaf::LeafWriter::write_session`] each session in strictly
//!    increasing session-ordinal order (the run scheduler's single writer
//!    thread, per A11, is what makes this byte-deterministic) — including a
//!    session that contributes zero rows to this leaf, which still gets an
//!    explicit `rows = 0` row in the leaf's own companion session-index
//!    leaf rather than being silently skipped (Sol#12) — then
//!    [`parquet_leaf::LeafWriter::finish`] into a [`parquet_leaf::FinishedLeaf`]
//!    (the parquet leaf's own [`manifest::LeafRecord`] plus its
//!    session-index companion's). For any hand-written TSV leaf (e.g.
//!    `metrics`'s small, human-auditable tables), hash it and build a
//!    [`manifest::LeafRecord`] directly.
//! 3. Register every [`manifest::LeafRecord`] — every parquet leaf, its
//!    session-index companion, and every hand-written TSV leaf — with a
//!    [`manifest::ManifestBuilder`].
//! 4. Write [`receipt::RunReceipt`] into the staging directory, and also
//!    register its own manifest leaf record
//!    ([`receipt::RunReceipt::leaf_record`]) with the same builder — the
//!    receipt is a required manifest leaf like any other (Sol#8), never a
//!    side channel the manifest doesn't cover.
//! 5. Write the manifest LAST ([`manifest::ManifestBuilder::write`]) — its
//!    presence is the publication's completeness signal.
//! 6. [`atomic::PublishStaging::commit`] to make the whole publication
//!    appear atomically at its final path — this now fails closed unless
//!    the staging directory is itself a complete publication (manifest and
//!    receipt present, manifest coverage of staging contents exact in both
//!    directions, Sol#13); staging evidence is retained on any failure.
//! 7. Later, [`verify::verify_publication`] source-freely rechecks every
//!    leaf, requires the manifest to name exactly the caller's registered
//!    required leaf inventory (Opus#F4), requires exactly one receipt leaf
//!    with sane pinned + per-run identity fields (Sol#8), and requires a
//!    [`verify::GateRecomputer`] to run and succeed — absence is a typed
//!    error, never a silent accept (Sol#2). [`verify::inspect_leaf_checksums`]
//!    is the separate, non-accepting checksum-only diagnostic.
//!
//! # Workspace wiring note
//!
//! This crate is not yet a member of the workspace `Cargo.toml`
//! (`engine/Cargo.toml`) — the wiring/scheduler agent adds the one-line
//! member entry (the `metrics` crate agent touches that same file
//! concurrently, so this crate deliberately does not).

pub mod atomic;
pub mod error;
pub mod gate;
pub mod hash;
mod json;
pub mod manifest;
pub mod parquet_leaf;
pub mod receipt;
pub mod verify;

pub use atomic::{PublishStaging, write_atomic};
pub use error::{PublishError, Result};
pub use gate::StageGate;
pub use hash::{hex32, parse_hex32};
pub use manifest::{LeafRecord, ManifestBuilder, read_manifest};
pub use parquet_leaf::{FinishedLeaf, LeafWriter};
pub use receipt::{
    RECEIPT_LEAF_NAME, RECEIPT_LEAF_ROWS, RunReceipt, current_argv, executable_sha256,
};
pub use verify::{
    GateRecomputer, LeafInspectionReport, VerificationReport, inspect_leaf_checksums,
    verify_publication,
};
