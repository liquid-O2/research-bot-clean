//! The publish crate's own manifest: `name\trows\tbytes\tsha256`, one row
//! per leaf, sorted by name, written LAST and atomically (design brief §D:
//! "one `manifest.tsv` (name, rows, bytes, sha256; written last, atomic
//! rename)"). Distinct from `pubread::PinnedPublication`'s manifest reader,
//! which pins the OLD, external REL037 event-publication's `field\tvalue`
//! manifest — this is the NEW publication's own leaf table, a plain
//! columnar TSV.

use crate::atomic::write_atomic;
use crate::error::{PublishError, Result};
use crate::hash::{hex32, parse_hex32};
use std::collections::HashSet;
use std::fmt::Write as _;
use std::path::{Component, Path, PathBuf};

const MANIFEST_HEADER: &str = "name\trows\tbytes\tsha256";

/// One leaf's manifest entry: file name (with extension), row count, byte
/// size, plain sha256.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct LeafRecord {
    pub name: String,
    pub rows: u64,
    pub bytes: u64,
    pub sha256: [u8; 32],
}

/// Accumulates [`LeafRecord`]s during a publish run and writes
/// `dir/manifest.tsv` once, last.
#[derive(Default)]
pub struct ManifestBuilder {
    leaves: Vec<LeafRecord>,
}

impl ManifestBuilder {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Registers one finished leaf. Call only after the leaf's file is
    /// fully written to disk — this builder never revisits a leaf once
    /// registered, it only records what the caller reports.
    pub fn push(&mut self, record: LeafRecord) {
        self.leaves.push(record);
    }

    /// How many leaves have been registered so far.
    #[must_use]
    pub fn len(&self) -> usize {
        self.leaves.len()
    }

    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.leaves.is_empty()
    }

    /// Writes `dir/manifest.tsv`: header, then one row per leaf sorted by
    /// name, atomically (temp file + rename within `dir`, via
    /// [`write_atomic`]). Call this LAST — after every other leaf in the
    /// publication (including `run_receipt.json`) has been written to
    /// `dir` — so the manifest's presence is the publication's own
    /// completeness signal (a directory missing `manifest.tsv` is an
    /// incomplete/abandoned publish attempt, never a valid one).
    ///
    /// # Errors
    ///
    /// Returns an error if the manifest file cannot be written.
    pub fn write(mut self, dir: &Path) -> Result<PathBuf> {
        self.leaves.sort_by(|a, b| a.name.cmp(&b.name));
        let mut text = String::from(MANIFEST_HEADER);
        text.push('\n');
        for leaf in &self.leaves {
            writeln!(
                text,
                "{}\t{}\t{}\t{}",
                leaf.name,
                leaf.rows,
                leaf.bytes,
                hex32(&leaf.sha256)
            )
            .expect("writing to a String cannot fail");
        }
        let path = dir.join("manifest.tsv");
        write_atomic(&path, text.as_bytes())?;
        Ok(path)
    }
}

/// Restricts a manifest leaf name to a single normal path component: no
/// separators, no `.`/`..`, no absolute path (Sol#9). `dir.join(name)` can
/// then never step outside `dir` by construction — a manifest row named
/// `../outside.tsv` or `/etc/passwd` is rejected here, before any file is
/// ever opened.
fn validate_leaf_name(name: &str) -> Result<()> {
    let mut components = Path::new(name).components();
    match (components.next(), components.next()) {
        (Some(Component::Normal(_)), None) => Ok(()),
        _ => Err(PublishError::LeafNameInvalid {
            name: name.to_owned(),
        }),
    }
}

/// Reads and parses `path` (a `manifest.tsv` this crate wrote).
///
/// # Errors
///
/// Returns [`PublishError::Io`] if the file can't be read;
/// [`PublishError::ManifestMalformed`] if its header doesn't match or any
/// row is malformed (wrong column count, non-numeric rows/bytes, or a
/// sha256 that isn't 64 lowercase hex characters); [`PublishError::LeafNameInvalid`]
/// if a row's leaf name is not a single normal path component (Sol#9); or
/// [`PublishError::LeafNameDuplicate`] if the same leaf name appears twice.
pub fn read_manifest(path: &Path) -> Result<Vec<LeafRecord>> {
    let text = std::fs::read_to_string(path).map_err(|source| PublishError::Io {
        path: path.to_path_buf(),
        source,
    })?;
    let mut lines = text.lines();
    let header = lines
        .next()
        .ok_or_else(|| PublishError::ManifestMalformed {
            detail: "empty manifest.tsv".to_owned(),
        })?;
    if header != MANIFEST_HEADER {
        return Err(PublishError::ManifestMalformed {
            detail: format!("unexpected header: `{header}`"),
        });
    }
    let mut leaves = Vec::new();
    let mut seen_names: HashSet<String> = HashSet::new();
    for (offset, line) in lines.enumerate() {
        let row_number = offset + 2; // header is row 1
        let fields: Vec<&str> = line.split('\t').collect();
        if fields.len() != 4 {
            return Err(PublishError::ManifestMalformed {
                detail: format!(
                    "row {row_number} has {} columns, expected 4: `{line}`",
                    fields.len()
                ),
            });
        }
        validate_leaf_name(fields[0])?;
        if !seen_names.insert(fields[0].to_owned()) {
            return Err(PublishError::LeafNameDuplicate {
                name: fields[0].to_owned(),
            });
        }
        let rows: u64 = fields[1]
            .parse()
            .map_err(|_| PublishError::ManifestMalformed {
                detail: format!("row {row_number}: rows `{}` is not a u64", fields[1]),
            })?;
        let bytes: u64 = fields[2]
            .parse()
            .map_err(|_| PublishError::ManifestMalformed {
                detail: format!("row {row_number}: bytes `{}` is not a u64", fields[2]),
            })?;
        let sha256 = parse_hex32(fields[3]).ok_or_else(|| PublishError::ManifestMalformed {
            detail: format!(
                "row {row_number}: sha256 `{}` is not 64 hex characters",
                fields[3]
            ),
        })?;
        leaves.push(LeafRecord {
            name: fields[0].to_owned(),
            rows,
            bytes,
            sha256,
        });
    }
    Ok(leaves)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn scratch_dir(label: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "publish_manifest_test_{label}_{}_{:?}",
            std::process::id(),
            std::thread::current().id()
        ));
        std::fs::create_dir_all(&dir).expect("mkdir scratch");
        dir
    }

    fn sample_leaf(name: &str, byte: u8) -> LeafRecord {
        LeafRecord {
            name: name.to_owned(),
            rows: 100,
            bytes: 12345,
            sha256: [byte; 32],
        }
    }

    #[test]
    fn round_trip_sorts_by_name_and_preserves_every_field() {
        let dir = scratch_dir("roundtrip");
        let mut builder = ManifestBuilder::new();
        builder.push(sample_leaf("regimes.parquet", 0x02));
        builder.push(sample_leaf("labels_dwell.parquet", 0x01));
        assert_eq!(builder.len(), 2);
        assert!(!builder.is_empty());
        let path = builder.write(&dir).expect("write manifest");

        let leaves = read_manifest(&path).expect("read manifest");
        assert_eq!(leaves.len(), 2);
        // Sorted by name: "labels_dwell.parquet" < "regimes.parquet".
        assert_eq!(leaves[0].name, "labels_dwell.parquet");
        assert_eq!(leaves[0].sha256, [0x01; 32]);
        assert_eq!(leaves[1].name, "regimes.parquet");
        assert_eq!(leaves[1].sha256, [0x02; 32]);
        assert_eq!(leaves[0].rows, 100);
        assert_eq!(leaves[0].bytes, 12345);

        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn write_is_atomic_via_rename_no_temp_file_left_behind() {
        let dir = scratch_dir("atomic_write");
        let mut builder = ManifestBuilder::new();
        builder.push(sample_leaf("only_leaf.tsv", 0xaa));
        let path = builder.write(&dir).expect("write manifest");
        assert!(path.is_file());
        let leftovers: Vec<_> = std::fs::read_dir(&dir)
            .expect("read_dir")
            .filter_map(std::result::Result::ok)
            .filter(|entry| entry.file_name().to_string_lossy().ends_with(".tmp"))
            .collect();
        assert!(leftovers.is_empty());

        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn rejects_wrong_header() {
        let dir = scratch_dir("bad_header");
        let path = dir.join("manifest.tsv");
        std::fs::write(&path, "wrong\theader\n").expect("write");
        let error = read_manifest(&path).expect_err("must reject");
        assert!(matches!(error, PublishError::ManifestMalformed { .. }));
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn rejects_a_tampered_row_with_the_wrong_column_count() {
        let dir = scratch_dir("bad_columns");
        let path = dir.join("manifest.tsv");
        std::fs::write(&path, format!("{MANIFEST_HEADER}\nname_only\n")).expect("write");
        let error = read_manifest(&path).expect_err("must reject");
        assert!(matches!(error, PublishError::ManifestMalformed { .. }));
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn rejects_a_tampered_sha256_that_is_not_hex64() {
        let dir = scratch_dir("bad_sha");
        let path = dir.join("manifest.tsv");
        std::fs::write(
            &path,
            format!("{MANIFEST_HEADER}\nleaf.tsv\t1\t2\tnot-a-digest\n"),
        )
        .expect("write");
        let error = read_manifest(&path).expect_err("must reject");
        assert!(matches!(error, PublishError::ManifestMalformed { .. }));
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn sol9_rejects_a_leaf_name_that_climbs_outside_the_directory() {
        let dir = scratch_dir("escape_parent");
        let path = dir.join("manifest.tsv");
        std::fs::write(
            &path,
            format!(
                "{MANIFEST_HEADER}\n../outside.tsv\t1\t2\t{}\n",
                "a".repeat(64)
            ),
        )
        .expect("write");
        let error = read_manifest(&path).expect_err("must reject");
        assert!(
            matches!(error, PublishError::LeafNameInvalid { name } if name == "../outside.tsv")
        );
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn rejects_a_leaf_name_with_a_separator_or_an_absolute_path() {
        let dir = scratch_dir("escape_variants");
        for bad_name in ["sub/leaf.tsv", "/etc/passwd", ".", ".."] {
            let path = dir.join("manifest.tsv");
            std::fs::write(
                &path,
                format!("{MANIFEST_HEADER}\n{bad_name}\t1\t2\t{}\n", "a".repeat(64)),
            )
            .expect("write");
            let error = read_manifest(&path).expect_err("must reject");
            assert!(
                matches!(error, PublishError::LeafNameInvalid { .. }),
                "expected LeafNameInvalid for `{bad_name}`, got {error:?}"
            );
        }
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn rejects_a_duplicate_leaf_name() {
        let dir = scratch_dir("dup_name");
        let path = dir.join("manifest.tsv");
        std::fs::write(
            &path,
            format!(
                "{MANIFEST_HEADER}\nleaf.tsv\t1\t2\t{}\nleaf.tsv\t3\t4\t{}\n",
                "a".repeat(64),
                "b".repeat(64)
            ),
        )
        .expect("write");
        let error = read_manifest(&path).expect_err("must reject");
        assert!(matches!(error, PublishError::LeafNameDuplicate { name } if name == "leaf.tsv"));
        std::fs::remove_dir_all(&dir).ok();
    }
}
