//! The pinned reader itself: manifest-sha pin, leaf table, and per-leaf
//! checksum verification.

use crate::digest::{hash_and_count_lines, hex32, parse_hex32};
use crate::error::{PubReadError, Result};
use crate::leaves::{AssignmentReader, DayRootReader, EventSignalReader, TruthCoverageReader};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

/// One leaf's entry in the manifest's leaf table: the five
/// `leaf_<name>_{schema_root,row_count,sequence_root,byte_size,sha256}`
/// fields, decoded.
#[derive(Clone, Copy, Debug)]
pub struct LeafMeta {
    pub schema_root: [u8; 32],
    pub row_count: u64,
    pub sequence_root: [u8; 32],
    pub byte_size: u64,
    pub sha256: [u8; 32],
}

/// Progress emitted by the shared streaming leaf verifier.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct LeafVerificationProgress {
    pub name: String,
    pub verified_bytes: u64,
    pub manifest_bytes: u64,
}

/// A pinned, sha256-verified handle onto one event-publication directory
/// (`manifest.tsv` + its leaf files).
///
/// [`PinnedPublication::open`] validates exactly two things: that
/// `manifest.tsv`'s own bytes hash to the caller's pin, and that its leaf
/// table parses. No other manifest field is checked — the recorded producer
/// identities (`kernel_law_sha256`, `rustc_version`, and so on) are carried
/// as opaque strings via [`PinnedPublication::recorded`]. Per-leaf content
/// is verified only when [`PinnedPublication::verify_leaf`] or
/// [`PinnedPublication::verify_all`] is called.
#[derive(Debug)]
pub struct PinnedPublication {
    dir: PathBuf,
    fields: BTreeMap<String, String>,
    leaves: BTreeMap<String, LeafMeta>,
}

const LEAF_SUFFIXES: [&str; 5] = [
    "_schema_root",
    "_row_count",
    "_sequence_root",
    "_byte_size",
    "_sha256",
];
const PROGRESS_INTERVAL_BYTES: u64 = 256 << 20;

#[derive(Default)]
struct PartialLeaf {
    schema_root: Option<[u8; 32]>,
    row_count: Option<u64>,
    sequence_root: Option<[u8; 32]>,
    byte_size: Option<u64>,
    sha256: Option<[u8; 32]>,
}

fn malformed(detail: impl Into<String>) -> PubReadError {
    PubReadError::ManifestMalformed {
        detail: detail.into(),
    }
}

/// Groups every `leaf_<name>_<suffix>` field by `<name>` and decodes each
/// group into a [`LeafMeta`]. Fields that start with `leaf_` but don't end
/// in one of the five known suffixes (e.g. the unrelated `leaf_set_id`
/// field) are left alone — this function only ever builds the leaf table,
/// never validates the rest of the manifest.
fn build_leaf_table(fields: &BTreeMap<String, String>) -> Result<BTreeMap<String, LeafMeta>> {
    let mut partials: BTreeMap<&str, PartialLeaf> = BTreeMap::new();
    for (key, value) in fields {
        let Some(rest) = key.strip_prefix("leaf_") else {
            continue;
        };
        let Some((name, suffix)) = LEAF_SUFFIXES
            .iter()
            .find_map(|suffix| rest.strip_suffix(suffix).map(|name| (name, *suffix)))
        else {
            continue;
        };
        let partial = partials.entry(name).or_default();
        match suffix {
            "_schema_root" => {
                partial.schema_root =
                    Some(parse_hex32(value).ok_or_else(|| {
                        malformed(format!("leaf_{name}{suffix} is not a digest"))
                    })?);
            }
            "_row_count" => {
                partial.row_count = Some(
                    value
                        .parse()
                        .map_err(|_| malformed(format!("leaf_{name}{suffix} is not a u64")))?,
                );
            }
            "_sequence_root" => {
                partial.sequence_root =
                    Some(parse_hex32(value).ok_or_else(|| {
                        malformed(format!("leaf_{name}{suffix} is not a digest"))
                    })?);
            }
            "_byte_size" => {
                partial.byte_size = Some(
                    value
                        .parse()
                        .map_err(|_| malformed(format!("leaf_{name}{suffix} is not a u64")))?,
                );
            }
            "_sha256" => {
                partial.sha256 =
                    Some(parse_hex32(value).ok_or_else(|| {
                        malformed(format!("leaf_{name}{suffix} is not a digest"))
                    })?);
            }
            _ => unreachable!("suffix drawn from LEAF_SUFFIXES"),
        }
    }

    partials
        .into_iter()
        .map(|(name, p)| {
            let meta = LeafMeta {
                schema_root: p
                    .schema_root
                    .ok_or_else(|| malformed(format!("leaf_{name}_schema_root missing")))?,
                row_count: p
                    .row_count
                    .ok_or_else(|| malformed(format!("leaf_{name}_row_count missing")))?,
                sequence_root: p
                    .sequence_root
                    .ok_or_else(|| malformed(format!("leaf_{name}_sequence_root missing")))?,
                byte_size: p
                    .byte_size
                    .ok_or_else(|| malformed(format!("leaf_{name}_byte_size missing")))?,
                sha256: p
                    .sha256
                    .ok_or_else(|| malformed(format!("leaf_{name}_sha256 missing")))?,
            };
            Ok((format!("{name}.tsv"), meta))
        })
        .collect()
}

impl PinnedPublication {
    /// Reads `dir/manifest.tsv`, verifies its plain sha256 equals
    /// `manifest_sha`, and parses its leaf table.
    ///
    /// # Errors
    ///
    /// [`PubReadError::Io`] if the manifest can't be read;
    /// [`PubReadError::ManifestDigestMismatch`] if its sha256 doesn't match
    /// `manifest_sha`; [`PubReadError::ManifestMalformed`] if it isn't a
    /// `field\tvalue` table or its leaf table is incomplete.
    pub fn open(dir: &Path, manifest_sha: [u8; 32]) -> Result<Self> {
        let manifest_path = dir.join("manifest.tsv");
        let text = std::fs::read_to_string(&manifest_path).map_err(|source| PubReadError::Io {
            path: manifest_path.clone(),
            source,
        })?;

        let actual: [u8; 32] = Sha256::digest(text.as_bytes()).into();
        if actual != manifest_sha {
            return Err(PubReadError::ManifestDigestMismatch {
                expected: manifest_sha,
                actual,
            });
        }

        let mut lines = text.lines();
        let header = lines.next().ok_or_else(|| malformed("empty manifest"))?;
        if header != "field\tvalue" {
            return Err(malformed(format!("unexpected header: `{header}`")));
        }

        let mut fields = BTreeMap::new();
        for (offset, line) in lines.enumerate() {
            let (name, value) = line.split_once('\t').ok_or_else(|| {
                malformed(format!(
                    "row {} is not `field\\tvalue`: `{line}`",
                    offset + 2
                ))
            })?;
            fields.insert(name.to_owned(), value.to_owned());
        }

        let leaves = build_leaf_table(&fields)?;

        Ok(Self {
            dir: dir.to_path_buf(),
            fields,
            leaves,
        })
    }

    /// Looks up a raw manifest field by name (e.g. `"rustc_version"`,
    /// `"kernel_law_sha256"`). These are recorded producer identities this
    /// crate never validates; callers that care about one look it up
    /// explicitly and decide for themselves.
    #[must_use]
    pub fn recorded(&self, field: &str) -> Option<&str> {
        self.fields.get(field).map(String::as_str)
    }

    /// The leaf table entry for `name` (e.g. `"day_roots.tsv"`).
    #[must_use]
    pub fn leaf(&self, name: &str) -> Option<&LeafMeta> {
        self.leaves.get(name)
    }

    /// Every leaf name (with `.tsv` extension) in the manifest's leaf table.
    pub fn leaf_names(&self) -> impl Iterator<Item = &str> {
        self.leaves.keys().map(String::as_str)
    }

    /// Streams `dir/name`, verifying its byte size, plain sha256, and row
    /// count (line count minus the header line) against what the manifest
    /// recorded for it. Never buffers the whole file.
    ///
    /// # Errors
    ///
    /// [`PubReadError::UnknownLeaf`] if `name` isn't in the leaf table;
    /// [`PubReadError::Io`] if the file can't be read;
    /// [`PubReadError::LeafVerificationFailed`] if any of the three checks
    /// disagrees with the manifest.
    pub fn verify_leaf(&self, name: &str) -> Result<()> {
        self.verify_leaf_with_progress(name, |_| {})
    }

    /// Streams one leaf through the shared verifier and reports verified bytes.
    /// Complexity: `O(leaf bytes)` time and `O(1)` memory.
    pub fn verify_leaf_with_progress<F>(&self, name: &str, mut progress: F) -> Result<()>
    where
        F: FnMut(LeafVerificationProgress),
    {
        let meta = self
            .leaves
            .get(name)
            .ok_or_else(|| PubReadError::UnknownLeaf {
                name: name.to_owned(),
            })?;
        let path = self.dir.join(name);
        let (byte_size, sha256, newline_count) =
            hash_and_count_lines(&path, PROGRESS_INTERVAL_BYTES, |verified_bytes| {
                progress(LeafVerificationProgress {
                    name: name.to_owned(),
                    verified_bytes,
                    manifest_bytes: meta.byte_size,
                });
            })?;
        let row_count = newline_count.saturating_sub(1);

        let mut problems = Vec::new();
        if byte_size != meta.byte_size {
            problems.push(format!(
                "byte_size: manifest={} actual={byte_size}",
                meta.byte_size
            ));
        }
        if sha256 != meta.sha256 {
            problems.push(format!(
                "sha256: manifest={} actual={}",
                hex32(&meta.sha256),
                hex32(&sha256)
            ));
        }
        if row_count != meta.row_count {
            problems.push(format!(
                "row_count: manifest={} actual={row_count}",
                meta.row_count
            ));
        }

        if problems.is_empty() {
            Ok(())
        } else {
            Err(PubReadError::LeafVerificationFailed {
                name: name.to_owned(),
                detail: problems.join("; "),
            })
        }
    }

    /// Runs [`PinnedPublication::verify_leaf`] over every leaf in parallel
    /// (one rayon task per leaf).
    ///
    /// # Errors
    ///
    /// The first [`PubReadError`] any leaf's verification produces.
    pub fn verify_all(&self) -> Result<()> {
        use rayon::prelude::*;
        let names: Vec<&str> = self.leaf_names().collect();
        names.par_iter().try_for_each(|name| self.verify_leaf(name))
    }

    /// A streaming, typed reader over `day_roots.tsv`.
    ///
    /// # Errors
    ///
    /// [`PubReadError::Io`] if the file can't be opened;
    /// [`PubReadError::LeafHeaderMismatch`] if its header doesn't match the
    /// expected column layout.
    pub fn day_roots(&self) -> Result<DayRootReader> {
        DayRootReader::open(&self.dir.join("day_roots.tsv"))
    }

    /// A streaming, typed reader over `event_signals.tsv`.
    ///
    /// # Errors
    ///
    /// Same as [`PinnedPublication::day_roots`].
    pub fn event_signals(&self) -> Result<EventSignalReader> {
        EventSignalReader::open(&self.dir.join("event_signals.tsv"))
    }

    /// A streaming, typed reader over `assignments.tsv`.
    ///
    /// # Errors
    ///
    /// Same as [`PinnedPublication::day_roots`].
    pub fn assignments(&self) -> Result<AssignmentReader> {
        AssignmentReader::open(&self.dir.join("assignments.tsv"))
    }

    /// A streaming, typed reader over `truth_coverage.tsv`.
    ///
    /// # Errors
    ///
    /// Same as [`PinnedPublication::day_roots`].
    pub fn truth_coverage(&self) -> Result<TruthCoverageReader> {
        TruthCoverageReader::open(&self.dir.join("truth_coverage.tsv"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::EXPECTED_MANIFEST_SHA256;
    use crate::digest::parse_hex32;

    /// The real, pinned publication this crate reads. Tests skip (rather
    /// than fail) if it isn't mounted in this environment.
    fn publication_dir() -> PathBuf {
        PathBuf::from("/workspace/artifacts/runs/e1_rel037_verified_event/event_publication")
    }

    fn pinned_sha() -> [u8; 32] {
        parse_hex32(EXPECTED_MANIFEST_SHA256).expect("EXPECTED_MANIFEST_SHA256 is a valid digest")
    }

    /// Opens the real publication, or returns `None` to signal "skip" if the
    /// read-only artifacts mount isn't present in this environment.
    fn open_real() -> Option<PinnedPublication> {
        let dir = publication_dir();
        if !dir.is_dir() {
            eprintln!("skipping: publication dir {} is not mounted", dir.display());
            return None;
        }
        Some(
            PinnedPublication::open(&dir, pinned_sha())
                .expect("real publication opens with the correct pin"),
        )
    }

    #[test]
    fn open_succeeds_with_the_correct_pin_and_fails_with_a_wrong_one() {
        let dir = publication_dir();
        if !dir.is_dir() {
            eprintln!("skipping: publication dir {} is not mounted", dir.display());
            return;
        }
        PinnedPublication::open(&dir, pinned_sha()).expect("correct pin opens");

        let mut wrong = pinned_sha();
        wrong[0] ^= 0xff;
        let err = PinnedPublication::open(&dir, wrong).expect_err("wrong pin must fail");
        assert!(matches!(err, PubReadError::ManifestDigestMismatch { .. }));
    }

    #[test]
    fn verify_leaf_passes_for_day_roots() {
        let Some(publication) = open_real() else {
            return;
        };
        publication
            .verify_leaf("day_roots.tsv")
            .expect("day_roots.tsv verifies against the manifest");
    }

    #[test]
    fn unknown_leaf_name_is_rejected() {
        let Some(publication) = open_real() else {
            return;
        };
        assert!(matches!(
            publication.verify_leaf("not_a_real_leaf.tsv"),
            Err(PubReadError::UnknownLeaf { .. })
        ));
    }

    #[test]
    fn leaf_progress_matches_plain_verification_and_cannot_change_result() {
        use crate::digest::stream_digest_with_progress;

        let root =
            std::env::temp_dir().join(format!("pubread_progress_contract_{}", std::process::id()));
        std::fs::create_dir_all(&root).expect("progress root");
        let path = root.join("tiny.tsv");
        std::fs::write(&path, b"header\na\nb\nc\nd\n").expect("small progress leaf");

        let plain = stream_digest_with_progress(&path, 4, |_| {}).expect("plain digest");
        let mut thresholds = Vec::new();
        let mut unrelated_state = 0_u64;
        let observed = stream_digest_with_progress(&path, 4, |bytes| {
            unrelated_state ^= bytes.rotate_left(7);
            thresholds.push(bytes);
        })
        .expect("state-mutating callback digest");
        assert_eq!(observed, plain);
        assert_eq!(thresholds, [4, 8, 12, plain.bytes]);
        assert_eq!(
            thresholds
                .iter()
                .filter(|&&value| value == plain.bytes)
                .count(),
            1
        );
        assert!(
            thresholds
                .windows(2)
                .all(|pair| pair[0] < pair[1] && pair[1] - pair[0] <= 4)
        );
        assert_eq!((plain.bytes, plain.newline_count), (15, 5));
        assert_ne!(unrelated_state, 0);
        assert!(matches!(
            stream_digest_with_progress(&path, 0, |_| {}),
            Err(PubReadError::ProgressIntervalZero)
        ));

        let zero = "0".repeat(64);
        let manifest = format!(
            "field\tvalue\nleaf_tiny_schema_root\t{zero}\nleaf_tiny_row_count\t4\nleaf_tiny_sequence_root\t{zero}\nleaf_tiny_byte_size\t{}\nleaf_tiny_sha256\t{}\n",
            plain.bytes,
            hex32(&plain.sha256)
        );
        std::fs::write(root.join("manifest.tsv"), &manifest).expect("fixture manifest");
        let pin: [u8; 32] = Sha256::digest(manifest.as_bytes()).into();
        let publication = PinnedPublication::open(&root, pin).expect("pinned fixture opens");
        publication
            .verify_leaf("tiny.tsv")
            .expect("plain leaf verifies");
        let mut updates = Vec::new();
        let mut callback_state = 0_u64;
        publication
            .verify_leaf_with_progress("tiny.tsv", |update| {
                callback_state = callback_state.wrapping_add(update.verified_bytes);
                updates.push(update);
            })
            .expect("progress leaf verifies");
        assert_eq!(updates.len(), 1);
        assert_eq!(
            updates[0],
            LeafVerificationProgress {
                name: "tiny.tsv".to_owned(),
                verified_bytes: plain.bytes,
                manifest_bytes: plain.bytes,
            }
        );
        assert_eq!(callback_state, plain.bytes);

        let mut tampered = std::fs::read(&path).expect("read fixture");
        tampered[7] ^= 1;
        std::fs::write(&path, tampered).expect("tamper fixture");
        let no_callback = publication
            .verify_leaf("tiny.tsv")
            .expect_err("plain tamper refusal");
        let mut tamper_state = 0_u64;
        let with_callback = publication
            .verify_leaf_with_progress("tiny.tsv", |update| {
                tamper_state = tamper_state.wrapping_add(update.verified_bytes);
            })
            .expect_err("callback tamper refusal");
        assert_eq!(format!("{no_callback:?}"), format!("{with_callback:?}"));
        assert!(matches!(
            no_callback,
            PubReadError::LeafVerificationFailed { .. }
        ));
        assert_eq!(tamper_state, plain.bytes);
        std::fs::remove_dir_all(root).expect("remove progress root");
    }

    #[test]
    fn day_roots_yields_exactly_1003_rows() {
        let Some(publication) = open_real() else {
            return;
        };
        let rows: Vec<_> = publication
            .day_roots()
            .expect("reader opens")
            .map(|row| row.expect("row parses"))
            .collect();
        assert_eq!(rows.len(), 1_003);
        assert_eq!(rows[0].day, "2022-01-03");
        assert_eq!(rows[rows.len() - 1].day, "2025-12-31");
        assert!(
            rows.windows(2)
                .all(|pair| pair[0].ordinal + 1 == pair[1].ordinal),
            "day_roots ordinals must be contiguous ascending"
        );
    }

    #[test]
    fn event_signals_first_1000_rows_are_day_monotone_and_parseable() {
        let Some(publication) = open_real() else {
            return;
        };
        let rows: Vec<_> = publication
            .event_signals()
            .expect("reader opens")
            .take(1_000)
            .map(|row| row.expect("row parses"))
            .collect();
        assert_eq!(rows.len(), 1_000);
        assert!(
            rows.windows(2)
                .all(|pair| pair[0].ordinal <= pair[1].ordinal),
            "event_signals rows must be grouped in non-decreasing day-ordinal order"
        );
        for row in &rows {
            assert!(!row.day.is_empty());
            assert!(
                matches!(row.extreme_side.as_str(), "HIGH" | "LOW"),
                "unexpected extreme_side: {}",
                row.extreme_side
            );
            assert!(row.pivot_fragment_count > 0);
        }
    }

    #[test]
    fn assignments_first_1000_rows_parse() {
        let Some(publication) = open_real() else {
            return;
        };
        let rows: Vec<_> = publication
            .assignments()
            .expect("reader opens")
            .take(1_000)
            .map(|row| row.expect("row parses"))
            .collect();
        assert_eq!(rows.len(), 1_000);
        for row in &rows {
            assert!(
                matches!(row.anchor_bps, 20 | 40),
                "unexpected anchor_bps: {}",
                row.anchor_bps
            );
            assert!(!row.state.is_empty());
        }
    }

    /// Streams and checksums all ~35 GB across the 12 leaves — correct, but
    /// too slow for the default `cargo test` gate. Run explicitly with
    /// `cargo test --release -p pubread -- --ignored verify_all`.
    #[test]
    #[ignore = "streams all ~35 GB of leaf files"]
    fn verify_all_leaves_matches_the_manifest() {
        let Some(publication) = open_real() else {
            return;
        };
        publication
            .verify_all()
            .expect("every leaf verifies against the manifest");
    }

    #[test]
    fn truth_coverage_first_1000_rows_parse_and_hit_xor_miss() {
        let Some(publication) = open_real() else {
            return;
        };
        let rows: Vec<_> = publication
            .truth_coverage()
            .expect("reader opens")
            .take(1_000)
            .map(|row| row.expect("row parses"))
            .collect();
        assert_eq!(rows.len(), 1_000);
        for row in &rows {
            assert_ne!(
                row.hit_candidate_id.is_some(),
                row.miss_reason.is_some(),
                "a truth episode is a hit xor a miss"
            );
        }
    }
}
