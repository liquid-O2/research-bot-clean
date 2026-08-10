use std::fmt;
use std::io;
use std::path::PathBuf;

/// Everything that can go wrong writing or verifying a stage-1 publication.
/// Fail-closed: every variant means "do not trust/complete this publish."
#[derive(Debug)]
pub enum PublishError {
    /// A file or directory could not be created, opened, read, or renamed.
    Io { path: PathBuf, source: io::Error },
    /// The `parquet` crate rejected a schema, write, or read.
    Parquet(parquet::errors::ParquetError),
    /// `run_receipt.json` could not be encoded, or did not decode as its
    /// exact fixed schema.
    ReceiptMalformed { detail: String },
    /// A field pinned in `run_receipt.json` (contract version, an input
    /// authority sha, or the estimator sha) does not match this build's
    /// compiled-in pin.
    ReceiptPinMismatch { detail: String },
    /// `manifest.tsv` does not parse as the `name\trows\tbytes\tsha256`
    /// table this crate writes.
    ManifestMalformed { detail: String },
    /// A leaf's file extension is not one this crate knows how to
    /// recompute a row count for (only `.parquet` and `.tsv` are known).
    UnknownLeafKind { path: PathBuf },
    /// Recomputing a leaf's bytes from disk did not reproduce what the
    /// manifest recorded for it (row count, byte size, and/or sha256).
    LeafVerificationFailed { name: String, detail: String },
    /// `manifest.tsv`, `run_receipt.json`, or a leaf the manifest names is
    /// absent from the directory being read.
    LeafMissing { name: String },
    /// A parquet leaf's tracked row count (the sum of rows handed to
    /// `LeafWriter::write_session`) disagrees with the finished file's own
    /// footer row count. An internal consistency guard; never expected to
    /// fire.
    RowCountMismatch {
        name: String,
        tracked: u64,
        footer: i64,
    },
    /// An exact arithmetic step overflowed, or a value (e.g. a row count)
    /// was outside the domain this crate is willing to trust.
    ArithmeticOverflow,
    /// The atomic-publish target directory already exists; publishing never
    /// silently overwrites a prior publication.
    FinalDirExists(PathBuf),
    /// A staging directory from a previous, uncommitted publish attempt is
    /// still present; this crate never silently reuses or deletes it.
    StagingDirExists(PathBuf),
    /// A path has no file name or parent component to derive a sibling
    /// staging/temp path from.
    InvalidPath(PathBuf),
    /// A `manifest.tsv` row named a leaf with anything other than a single
    /// normal path component (a separator, `.`, `..`, or an absolute path).
    LeafNameInvalid { name: String },
    /// `manifest.tsv` named the same leaf more than once.
    LeafNameDuplicate { name: String },
    /// A leaf's canonicalized path (after resolving symlinks) is not
    /// contained under the canonicalized `--dir` the verifier was given.
    LeafEscapesDirectory { name: String },
    /// The staging directory is not a complete publication: `manifest.tsv`
    /// and `run_receipt.json` must both be present before commit, and the
    /// manifest must name exactly the files staged (no unlisted staged
    /// file, no manifest-named file missing from staging).
    StagingNotCovered { detail: String },
    /// The manifest's leaf-name set does not exactly equal the caller's
    /// registered required inventory: some required leaf is missing, or an
    /// extra unlisted scientific leaf is present.
    RequiredLeafSetMismatch {
        missing: Vec<String>,
        extra: Vec<String>,
    },
    /// `run_receipt.json`'s `executable_sha256`/`git_commit`/`session_count`
    /// fields (the per-run identity fields, never compiled pins) fail their
    /// own shape/presence/expected-value checks.
    ReceiptIdentityInvalid { detail: String },
    /// `manifest.tsv` does not name exactly one `run_receipt.json` leaf.
    ReceiptLeafCountInvalid { count: usize },
    /// No [`crate::verify::GateRecomputer`] was supplied to
    /// [`crate::verify::verify_publication`]: a publication can never be
    /// accepted as verified without gate-quantity recomputation (fail-closed
    /// default; see [`crate::verify::inspect_leaf_checksums`] for the
    /// separate, non-accepting checksum-only diagnostic).
    GateRecomputationNotAccepted,
    /// A `LeafWriter::write_session` call's session ordinal did not strictly
    /// increase over the previous call, breaking the registered
    /// session-ordinal order the writer requires.
    SessionOutOfOrder { name: String, ordinal: u32 },
    /// A parquet leaf's companion session-index count did not equal the
    /// caller's expected total session count at `finish()`.
    SessionIndexCountMismatch {
        name: String,
        expected: u64,
        actual: u64,
    },
    /// `crate::gate::StageGate` (the A10/Sol#2 `GateRecomputer`) found a
    /// gate-specific leaf malformed, a source-free reclassification that
    /// disagreed with a published gate leaf, or a pinned-estimator
    /// invocation failure. Carries a human-readable detail naming exactly
    /// what disagreed or failed — never a silent pass.
    GateMismatch { detail: String },
    /// A single parquet row group's own footer-recorded `total_byte_size`
    /// (the approximate decoded byte size of that one session's batch)
    /// exceeded the documented per-session streaming bound before this
    /// crate attempted to decode it (EVENTS.4 P0 memory-safety fix): a
    /// coarse, typed, fail-closed guard against ever relying on the
    /// container OOM killer (`AGENTS.md` compute law) — checked from
    /// already-parsed footer metadata, never by decoding first and
    /// measuring after the fact.
    SessionBatchTooLarge {
        path: PathBuf,
        row_group: usize,
        approx_decoded_bytes: i64,
        limit_bytes: i64,
    },
    /// Two independently-written per-leaf artifacts that are supposed to
    /// describe the SAME session sequence in the SAME order (a parquet
    /// leaf's own `<leaf_stem>_session_index.tsv` companion vs.
    /// `evaluation_registry.tsv`'s dense roster) disagreed at some position
    /// — never trusted to align on faith (streaming per-session
    /// consumption's own precondition).
    SessionLeafMisaligned { leaf_stem: String, detail: String },
}

impl fmt::Display for PublishError {
    #[allow(
        clippy::too_many_lines,
        reason = "one flat match over every fail-closed variant this crate defines; splitting \
                  it would scatter each variant's message away from its sibling"
    )]
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io { path, source } => write!(f, "I/O error on {}: {source}", path.display()),
            Self::Parquet(source) => write!(f, "parquet error: {source}"),
            Self::ReceiptMalformed { detail } => write!(f, "run_receipt.json malformed: {detail}"),
            Self::ReceiptPinMismatch { detail } => {
                write!(f, "run_receipt.json pin mismatch: {detail}")
            }
            Self::ManifestMalformed { detail } => write!(f, "manifest.tsv malformed: {detail}"),
            Self::UnknownLeafKind { path } => {
                write!(
                    f,
                    "don't know how to verify this leaf kind: {}",
                    path.display()
                )
            }
            Self::LeafVerificationFailed { name, detail } => {
                write!(f, "leaf verification failed for {name}: {detail}")
            }
            Self::LeafMissing { name } => {
                write!(f, "expected file is missing from the publication: {name}")
            }
            Self::RowCountMismatch {
                name,
                tracked,
                footer,
            } => write!(
                f,
                "{name}: tracked row count {tracked} disagrees with parquet footer row count {footer}"
            ),
            Self::ArithmeticOverflow => write!(f, "exact arithmetic overflowed"),
            Self::FinalDirExists(path) => write!(
                f,
                "publish target already exists, refusing to overwrite: {}",
                path.display()
            ),
            Self::StagingDirExists(path) => write!(
                f,
                "stale staging directory from a previous, uncommitted publish attempt: {}",
                path.display()
            ),
            Self::InvalidPath(path) => write!(
                f,
                "path has no file name/parent to derive a sibling path from: {}",
                path.display()
            ),
            Self::LeafNameInvalid { name } => write!(
                f,
                "manifest leaf name `{name}` is not a single normal path component"
            ),
            Self::LeafNameDuplicate { name } => {
                write!(f, "manifest.tsv names leaf `{name}` more than once")
            }
            Self::LeafEscapesDirectory { name } => write!(
                f,
                "leaf `{name}` resolves outside the verified directory (symlink escape)"
            ),
            Self::StagingNotCovered { detail } => {
                write!(
                    f,
                    "staging directory is not a complete publication: {detail}"
                )
            }
            Self::RequiredLeafSetMismatch { missing, extra } => write!(
                f,
                "manifest leaf set disagrees with the required inventory: missing={missing:?} extra={extra:?}"
            ),
            Self::ReceiptIdentityInvalid { detail } => {
                write!(f, "run_receipt.json identity fields invalid: {detail}")
            }
            Self::ReceiptLeafCountInvalid { count } => write!(
                f,
                "manifest.tsv must name exactly one run_receipt.json leaf, found {count}"
            ),
            Self::GateRecomputationNotAccepted => write!(
                f,
                "no GateRecomputer was supplied: gate-quantity recomputation is required for acceptance"
            ),
            Self::SessionOutOfOrder { name, ordinal } => write!(
                f,
                "{name}: session ordinal {ordinal} did not strictly increase over the previous write_session call"
            ),
            Self::SessionIndexCountMismatch {
                name,
                expected,
                actual,
            } => write!(
                f,
                "{name}: session index has {actual} entries, expected exactly {expected}"
            ),
            Self::GateMismatch { detail } => write!(f, "gate recomputation mismatch: {detail}"),
            Self::SessionBatchTooLarge {
                path,
                row_group,
                approx_decoded_bytes,
                limit_bytes,
            } => write!(
                f,
                "{}: row group {row_group}'s approximate decoded size ({approx_decoded_bytes} \
                 bytes) exceeds the {limit_bytes}-byte per-session streaming guard \
                 (fail-closed: never rely on the container OOM killer)",
                path.display()
            ),
            Self::SessionLeafMisaligned { leaf_stem, detail } => {
                write!(f, "{leaf_stem}: session ordering misaligned: {detail}")
            }
        }
    }
}

impl std::error::Error for PublishError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Io { source, .. } => Some(source),
            Self::Parquet(source) => Some(source),
            _ => None,
        }
    }
}

impl From<parquet::errors::ParquetError> for PublishError {
    fn from(source: parquet::errors::ParquetError) -> Self {
        Self::Parquet(source)
    }
}

pub type Result<T> = std::result::Result<T, PublishError>;
