//! The frozen 1,003-session accepted-session registry.
//!
//! `registry/accepted_compact_sessions.tsv` is byte-for-byte the file the old
//! `iwm_atlas_v2` build used at
//! `archive/rust/iwm_atlas_v2/accepted_compact_sessions.tsv`. It is embedded
//! into the binary at compile time (`include_str!`) so authentication and
//! session lookup never depend on where the crate happens to run. Its plain
//! sha256 is the corpus's pinned input authority
//! (`docs/engine_rebuild_r1_design.md`, "Integrity model").
//!
//! Every row also carries five closure/identity provenance columns from the
//! old build's law-validation machinery (`official_binding_id`,
//! `source_parent_id`, `coverage_authority_id`, `dependency_code_root`,
//! `accepted_day_summary_id`, `accepted_day_summary_blob_sha256`). Nothing
//! here needs them to locate, authenticate, or decode a session's quotes, so
//! they are parsed only far enough to be skipped.

use crate::error::{CorpusError, Result};
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

/// Pinned sha256 of `accepted_compact_sessions.tsv`. This is the corpus's
/// input authority: if this doesn't match, the embedded registry asset was
/// edited or corrupted and nothing it says should be trusted.
pub const EXPECTED_REGISTRY_SHA256: &str =
    "233dc10ab4c0973a8caa92792757a322bbff102296f0e7ffb71c6d78810bcaed";

const REGISTRY_TSV: &str = include_str!("../registry/accepted_compact_sessions.tsv");

const REGISTRY_HEADER: &str = concat!(
    "day\tsession_start_ns\tsession_end_ns\texpected_bar_count\tsource_relative_path\t",
    "official_binding_id\tsource_sha256\tsource_size_bytes\tsource_profile\t",
    "raw_rth_row_count\tcomplete_group_count\tsource_parent_id\tcoverage_authority_id\t",
    "dependency_code_root\taccepted_day_summary_id\taccepted_day_summary_blob_sha256"
);
const REGISTRY_COLUMNS: usize = 16;

/// Raw tick price encoding of one session's source parquet.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SourceProfile {
    /// `bid`/`ask` are `Int32` integer cents; scaled to u6 by `* 10_000`.
    CentInt32,
    /// `bid`/`ask` are `Float64` dollars; scaled to u6 by rounding `* 1_000_000`.
    DollarFloat64,
}

/// One registry-pinned session: everything needed to locate, authenticate,
/// and decode its NBBO quote parquet. Borrowed from the embedded registry
/// text, so this is `Copy` and free to pass around.
#[derive(Clone, Copy, Debug)]
pub struct RegistryEntry {
    pub day: &'static str,
    pub session_start_ns: i64,
    pub session_end_ns: i64,
    pub expected_bar_count: u16,
    pub source_relative_path: &'static str,
    pub source_sha256: &'static str,
    pub source_size_bytes: u64,
    pub source_profile: SourceProfile,
    pub raw_rth_row_count: u64,
    pub complete_group_count: u64,
}

fn parse_entry(line: &'static str) -> RegistryEntry {
    let fields: Vec<&'static str> = line.split('\t').collect();
    assert_eq!(
        fields.len(),
        REGISTRY_COLUMNS,
        "registry row has {} columns, expected {REGISTRY_COLUMNS}: {line}",
        fields.len()
    );
    let day = fields[0];
    let session_start_ns: i64 = fields[1]
        .parse()
        .unwrap_or_else(|_| panic!("row {day}: bad session_start_ns"));
    let session_end_ns: i64 = fields[2]
        .parse()
        .unwrap_or_else(|_| panic!("row {day}: bad session_end_ns"));
    let expected_bar_count: u16 = fields[3]
        .parse()
        .unwrap_or_else(|_| panic!("row {day}: bad expected_bar_count"));
    let source_relative_path = fields[4];
    // fields[5] = official_binding_id: closure-identity provenance, unused.
    let source_sha256 = fields[6];
    let source_size_bytes: u64 = fields[7]
        .parse()
        .unwrap_or_else(|_| panic!("row {day}: bad source_size_bytes"));
    let source_profile = match fields[8] {
        "cent_int32" => SourceProfile::CentInt32,
        "dollar_float64" => SourceProfile::DollarFloat64,
        other => panic!("row {day}: unknown source_profile {other}"),
    };
    let raw_rth_row_count: u64 = fields[9]
        .parse()
        .unwrap_or_else(|_| panic!("row {day}: bad raw_rth_row_count"));
    let complete_group_count: u64 = fields[10]
        .parse()
        .unwrap_or_else(|_| panic!("row {day}: bad complete_group_count"));
    // fields[11..16] = source_parent_id, coverage_authority_id,
    // dependency_code_root, accepted_day_summary_id,
    // accepted_day_summary_blob_sha256: closure-identity provenance, unused.

    assert_eq!(
        session_end_ns - session_start_ns,
        i64::from(expected_bar_count) * 60_000_000_000,
        "row {day}: session bounds disagree with expected_bar_count"
    );

    RegistryEntry {
        day,
        session_start_ns,
        session_end_ns,
        expected_bar_count,
        source_relative_path,
        source_sha256,
        source_size_bytes,
        source_profile,
        raw_rth_row_count,
        complete_group_count,
    }
}

/// Parses the embedded registry text. Panics on malformation: the embedded
/// asset is fixed at compile time, so malformation here is a build defect,
/// not a runtime input to fail closed on gracefully.
fn parse_registry() -> Vec<RegistryEntry> {
    let mut lines = REGISTRY_TSV.lines();
    let header = lines.next().expect("embedded registry is not empty");
    assert_eq!(
        header, REGISTRY_HEADER,
        "embedded registry header drifted from the frozen schema"
    );
    let entries: Vec<RegistryEntry> = lines.map(parse_entry).collect();
    assert!(!entries.is_empty(), "embedded registry has no sessions");
    for pair in entries.windows(2) {
        assert!(
            pair[0].day < pair[1].day,
            "registry days are not strictly sorted: {} >= {}",
            pair[0].day,
            pair[1].day
        );
    }
    entries
}

fn registry() -> &'static [RegistryEntry] {
    static REGISTRY: OnceLock<Vec<RegistryEntry>> = OnceLock::new();
    REGISTRY.get_or_init(parse_registry)
}

/// Receipt from a successful [`authenticate_registry`] call.
#[derive(Clone, Debug)]
pub struct RegistryReceipt {
    pub sha256: String,
    pub session_count: usize,
    pub corpus_root: PathBuf,
}

/// Verifies the embedded session registry's plain sha256 against the pinned
/// digest, then sanity-checks that `corpus_root` looks like the `IWM` quote
/// tree the registry describes (it exists, is a directory, and has a
/// subdirectory for every year the registry references).
///
/// This does not hash every session's source parquet — that happens once per
/// file in [`crate::load_session`], where the file is opened anyway.
///
/// # Errors
///
/// Returns [`CorpusError::RegistryDigestMismatch`] if the embedded registry
/// text no longer hashes to [`EXPECTED_REGISTRY_SHA256`], or
/// [`CorpusError::InvalidCorpusRoot`] if `corpus_root` is missing, is not a
/// directory, or is missing a year directory the registry references.
pub fn authenticate_registry(corpus_root: &Path) -> Result<RegistryReceipt> {
    let digest = format!("{:x}", Sha256::digest(REGISTRY_TSV.as_bytes()));
    if digest != EXPECTED_REGISTRY_SHA256 {
        return Err(CorpusError::RegistryDigestMismatch {
            expected: EXPECTED_REGISTRY_SHA256,
            actual: digest,
        });
    }

    let entries = registry();
    let root_metadata = std::fs::metadata(corpus_root)
        .map_err(|_| CorpusError::InvalidCorpusRoot(corpus_root.to_path_buf()))?;
    if !root_metadata.is_dir() {
        return Err(CorpusError::InvalidCorpusRoot(corpus_root.to_path_buf()));
    }
    let mut years: Vec<&str> = entries.iter().map(|entry| &entry.day[..4]).collect();
    years.sort_unstable();
    years.dedup();
    for year in years {
        let year_dir = corpus_root.join(year);
        if !year_dir.is_dir() {
            return Err(CorpusError::InvalidCorpusRoot(year_dir));
        }
    }

    Ok(RegistryReceipt {
        sha256: digest,
        session_count: entries.len(),
        corpus_root: corpus_root.to_path_buf(),
    })
}

/// Looks up one session's registry entry by day (`"YYYY-MM-DD"`).
///
/// # Errors
///
/// Returns [`CorpusError::UnknownSession`] if `day` has no registry entry.
pub fn lookup(day: &str) -> Result<RegistryEntry> {
    registry()
        .binary_search_by(|entry| entry.day.cmp(day))
        .map(|index| registry()[index])
        .map_err(|_| CorpusError::UnknownSession(day.to_owned()))
}

/// All 1,003 registered sessions in ascending day order.
#[must_use]
pub fn all_sessions() -> &'static [RegistryEntry] {
    registry()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn embedded_registry_matches_the_pinned_digest() {
        let digest = format!("{:x}", Sha256::digest(REGISTRY_TSV.as_bytes()));
        assert_eq!(digest, EXPECTED_REGISTRY_SHA256);
    }

    #[test]
    fn registry_has_1003_sessions_spanning_2022_through_2025() {
        let entries = registry();
        assert_eq!(entries.len(), 1_003);
        assert_eq!(entries[0].day, "2022-01-03");
        assert_eq!(entries[entries.len() - 1].day, "2025-12-31");
    }

    #[test]
    fn lookup_finds_a_known_day_and_rejects_an_unknown_one() {
        let entry = lookup("2022-01-03").expect("known session");
        assert_eq!(entry.source_relative_path, "2022/2022-01-03.parquet");
        assert_eq!(entry.source_profile, SourceProfile::CentInt32);
        assert!(lookup("2019-01-02").is_err());
    }
}
