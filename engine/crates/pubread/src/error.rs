use std::fmt;
use std::io;
use std::path::PathBuf;

/// Everything that can go wrong pinning, verifying, or streaming the
/// publication. Fail-closed: every variant means "do not trust this data."
#[derive(Debug)]
pub enum PubReadError {
    /// A file could not be opened or read.
    Io { path: PathBuf, source: io::Error },
    /// `manifest.tsv`'s plain sha256 does not match the caller's pin. The
    /// manifest on disk is not the one the caller intended to trust, so
    /// nothing else in the directory is read.
    ManifestDigestMismatch {
        expected: [u8; 32],
        actual: [u8; 32],
    },
    /// `manifest.tsv` does not parse as the `field\tvalue` table this reader
    /// expects, or its leaf table is incomplete (a `leaf_<name>_*` group is
    /// missing one of its five members).
    ManifestMalformed { detail: String },
    /// `name` has no entry in the manifest's leaf table.
    UnknownLeaf { name: String },
    /// Streaming a leaf's bytes did not reproduce what the manifest recorded
    /// for it (byte size, sha256, and/or row count).
    LeafVerificationFailed { name: String, detail: String },
    /// A streaming-progress interval must be strictly positive.
    ProgressIntervalZero,
    /// A leaf file's header row does not match the column layout its typed
    /// reader expects.
    LeafHeaderMismatch {
        path: PathBuf,
        expected: &'static str,
        actual: String,
    },
    /// A data row failed to parse into its typed representation (wrong
    /// column count, a column that doesn't parse as its declared type).
    RowMalformed {
        path: PathBuf,
        line_number: u64,
        detail: String,
    },
}

impl fmt::Display for PubReadError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io { path, source } => write!(f, "I/O error on {}: {source}", path.display()),
            Self::ManifestDigestMismatch { expected, actual } => write!(
                f,
                "manifest sha256 mismatch: expected {}, got {}",
                crate::digest::hex32(expected),
                crate::digest::hex32(actual)
            ),
            Self::ManifestMalformed { detail } => write!(f, "manifest.tsv malformed: {detail}"),
            Self::UnknownLeaf { name } => write!(f, "no such leaf in manifest: {name}"),
            Self::LeafVerificationFailed { name, detail } => {
                write!(f, "leaf verification failed for {name}: {detail}")
            }
            Self::ProgressIntervalZero => write!(f, "progress interval must be nonzero"),
            Self::LeafHeaderMismatch {
                path,
                expected,
                actual,
            } => write!(
                f,
                "header mismatch in {}: expected `{expected}`, got `{actual}`",
                path.display()
            ),
            Self::RowMalformed {
                path,
                line_number,
                detail,
            } => {
                write!(f, "{}:{line_number}: {detail}", path.display())
            }
        }
    }
}

impl std::error::Error for PubReadError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Io { source, .. } => Some(source),
            _ => None,
        }
    }
}

pub type Result<T> = std::result::Result<T, PubReadError>;
