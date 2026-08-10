use std::fmt;
use std::io;
use std::path::PathBuf;

/// Everything that can go wrong reading a session or authenticating the
/// registry. Fail-closed: every variant maps to "do not trust this data."
#[derive(Debug)]
pub enum CorpusError {
    /// `corpus_root` is missing, not a directory, or does not look like the
    /// `IWM` NBBO quote tree the registry describes.
    InvalidCorpusRoot(PathBuf),
    /// The embedded registry's sha256 no longer matches the pinned digest.
    /// This means the registry asset in this build was edited or corrupted.
    RegistryDigestMismatch {
        expected: &'static str,
        actual: String,
    },
    /// `day` has no entry in the frozen session registry.
    UnknownSession(String),
    /// The on-disk source file's size or content digest differs from what
    /// the registry recorded for this day.
    SourceAuthenticationFailed { path: PathBuf },
    /// The parquet file could not be opened or read.
    Io { path: PathBuf, source: io::Error },
    /// The parquet schema (column names, types, or count) does not match the
    /// registry's declared source profile.
    SchemaMismatch { path: PathBuf },
    /// A row mixed null and non-null fields, or a value could not be decoded
    /// (non-finite price, non-representable scaled price, and so on).
    DecodeFailed { path: PathBuf, detail: &'static str },
    /// Quote timestamps were not non-decreasing within the file.
    OutOfOrder { path: PathBuf },
    /// The decoded content disagrees with the registry's row/group counts
    /// for this day (wrong file, truncated file, or a semantics drift).
    ContentMismatch { path: PathBuf, detail: &'static str },
    /// An exact arithmetic step overflowed; the input is out of the domain
    /// this reader is willing to trust.
    ArithmeticOverflow,
    /// A civil date was not a canonical valid Gregorian `YYYY-MM-DD` value.
    MalformedCivilDate { value: String },
    /// A frame-B instant did not name this clock's authenticated source day.
    WrongCivilDay {
        expected: String,
        actual_timestamp_ns: i64,
    },
    /// Zone-aware Arrow metadata did not declare the registered direct clock.
    InvalidDirectInstantTimezone { timezone: String },
    /// A frame-B instant is outside this session's half-open RTH window.
    OutsideRth { day: String, timestamp_ns: i64 },
    /// A [`crate::SessionClock`] boundary condition was violated (R-HALT-44
    /// item 5): wrong day, a span disagreeing with `expected_bar_count`, an
    /// instant outside its own frame's session window, or a conversion that
    /// did not preserve the exact offset, the row count, or the order.
    ClockViolation { day: String, detail: String },
}

impl fmt::Display for CorpusError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidCorpusRoot(path) => {
                write!(
                    f,
                    "corpus root is not a valid IWM quote tree: {}",
                    path.display()
                )
            }
            Self::RegistryDigestMismatch { expected, actual } => write!(
                f,
                "session registry sha256 mismatch: expected {expected}, got {actual}"
            ),
            Self::UnknownSession(day) => write!(f, "session {day} is not in the registry"),
            Self::SourceAuthenticationFailed { path } => {
                write!(f, "source file authentication failed: {}", path.display())
            }
            Self::Io { path, source } => {
                write!(f, "I/O error reading {}: {source}", path.display())
            }
            Self::SchemaMismatch { path } => {
                write!(f, "parquet schema mismatch: {}", path.display())
            }
            Self::DecodeFailed { path, detail } => {
                write!(f, "decode failed for {}: {detail}", path.display())
            }
            Self::OutOfOrder { path } => {
                write!(f, "quote timestamps are not monotone: {}", path.display())
            }
            Self::ContentMismatch { path, detail } => {
                write!(
                    f,
                    "decoded content mismatch for {}: {detail}",
                    path.display()
                )
            }
            Self::ArithmeticOverflow => write!(f, "exact arithmetic overflowed"),
            Self::MalformedCivilDate { value } => {
                write!(f, "malformed civil date: {value}")
            }
            Self::WrongCivilDay {
                expected,
                actual_timestamp_ns,
            } => write!(
                f,
                "frame-B instant {actual_timestamp_ns} is not on authenticated civil day {expected}"
            ),
            Self::InvalidDirectInstantTimezone { timezone } => write!(
                f,
                "direct instant timezone metadata is not America/New_York: {timezone}"
            ),
            Self::OutsideRth { day, timestamp_ns } => write!(
                f,
                "frame-B instant {timestamp_ns} is outside the RTH window for {day}"
            ),
            Self::ClockViolation { day, detail } => {
                write!(f, "session clock boundary violated for {day}: {detail}")
            }
        }
    }
}

impl std::error::Error for CorpusError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Io { source, .. } => Some(source),
            _ => None,
        }
    }
}

pub type Result<T> = std::result::Result<T, CorpusError>;
