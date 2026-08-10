//! Typed refusals for the SELECT v2 sources layer.

use std::fmt;
use std::path::PathBuf;

/// Everything this crate refuses on, named.
#[derive(Debug)]
pub enum SelectV2Error {
    /// **THE CALENDAR WALL.** The requested civil day is not one of the 1,003
    /// registry sessions, so no reader in this crate will construct a path for
    /// it. This is what mechanically seals 2026 (and the 2020-2021 warmup) for
    /// all six token corpora, not just the stock quotes the registry was
    /// originally written for.
    DayOutsideCalendar { day: String, detail: &'static str },
    /// A refusal raised by the `corpus` crate (registry digest, clock, decode).
    Corpus(corpus::CorpusError),
    /// The day is registry-admissible but this corpus has no file for it.
    /// Distinct from [`Self::DayOutsideCalendar`]: absent is not out-of-bounds.
    ModalityAbsent {
        modality: &'static str,
        day: String,
        path: PathBuf,
    },
    Io {
        path: PathBuf,
        source: std::io::Error,
    },
    /// A parquet file's schema is not one of this reader's admitted profiles.
    SchemaMismatch { path: PathBuf, detail: String },
    /// Schema matched but the decoded content contradicts a pinned invariant.
    ContentMismatch { path: PathBuf, detail: String },
    /// A family declared more than [`crate::families::MAX_FAMILY_COLUMNS`].
    FamilyTooWide {
        family: &'static str,
        columns: usize,
    },
    /// `--families` named something the registry does not build.
    UnknownFamily(String),
    /// Checked arithmetic refused; the site is named.
    Arithmetic(&'static str),
    /// A CLI/driver configuration the run cannot honour.
    Config(String),
}

impl fmt::Display for SelectV2Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::DayOutsideCalendar { day, detail } => write!(
                f,
                "calendar wall: {day} is not one of the 1,003 registry sessions ({detail})"
            ),
            Self::Corpus(source) => write!(f, "corpus: {source}"),
            Self::ModalityAbsent {
                modality,
                day,
                path,
            } => write!(
                f,
                "modality {modality} is absent for registered session {day} (no {})",
                path.display()
            ),
            Self::Io { path, source } => write!(f, "io on {}: {source}", path.display()),
            Self::SchemaMismatch { path, detail } => {
                write!(f, "schema mismatch in {}: {detail}", path.display())
            }
            Self::ContentMismatch { path, detail } => {
                write!(f, "content mismatch in {}: {detail}", path.display())
            }
            Self::FamilyTooWide { family, columns } => write!(
                f,
                "family {family} declares {columns} columns, over the hard cap of {}",
                crate::families::MAX_FAMILY_COLUMNS
            ),
            Self::UnknownFamily(name) => write!(f, "unknown family {name}"),
            Self::Arithmetic(site) => write!(f, "checked arithmetic refused at {site}"),
            Self::Config(detail) => write!(f, "configuration: {detail}"),
        }
    }
}

impl std::error::Error for SelectV2Error {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::Corpus(source) => Some(source),
            Self::Io { source, .. } => Some(source),
            _ => None,
        }
    }
}

impl From<corpus::CorpusError> for SelectV2Error {
    fn from(value: corpus::CorpusError) -> Self {
        Self::Corpus(value)
    }
}

/// This crate's result alias.
pub type Result<T> = std::result::Result<T, SelectV2Error>;
