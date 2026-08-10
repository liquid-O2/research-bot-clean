//! Fresh-sibling-directory atomic publish (design brief §D as amended by
//! A10: "Publication is written to a fresh sibling temp dir and atomically
//! renamed on completion") and the file-level temp+rename primitive it's
//! built from.

use crate::error::{PublishError, Result};
use std::collections::HashSet;
use std::io;
use std::path::{Path, PathBuf};

/// Writes `contents` to a temp file next to `path` and renames it into
/// place. `rename` is atomic within one filesystem (POSIX), so a concurrent
/// reader never observes a partially written `path`.
///
/// # Errors
///
/// Returns [`PublishError::InvalidPath`] if `path` has no file name to
/// derive a sibling temp name from, or [`PublishError::Io`] if the temp
/// file can't be written or the rename fails.
pub fn write_atomic(path: &Path, contents: &[u8]) -> Result<()> {
    let file_name = path
        .file_name()
        .ok_or_else(|| PublishError::InvalidPath(path.to_path_buf()))?;
    let parent = path.parent().unwrap_or_else(|| Path::new("."));
    let tmp_path = parent.join(format!(".{}.tmp", file_name.to_string_lossy()));
    std::fs::write(&tmp_path, contents).map_err(|source| PublishError::Io {
        path: tmp_path.clone(),
        source,
    })?;
    std::fs::rename(&tmp_path, path).map_err(|source| PublishError::Io {
        path: path.to_path_buf(),
        source,
    })?;
    Ok(())
}

/// A fresh sibling staging directory for one publication, atomically
/// renamed to its final name on [`PublishStaging::commit`].
#[derive(Debug)]
pub struct PublishStaging {
    staging_dir: PathBuf,
    final_dir: PathBuf,
}

impl PublishStaging {
    /// Creates a fresh sibling staging directory next to `final_dir` (same
    /// parent directory, so [`PublishStaging::commit`]'s rename is atomic on
    /// one filesystem). Fails closed:
    ///
    /// - if `final_dir` already exists, this never silently overwrites a
    ///   prior publication;
    /// - if a staging directory from a previous, uncommitted attempt is
    ///   still present, this never silently reuses or deletes it — an
    ///   operator must look at it first (see [`PublishStaging::abandon`] for
    ///   an explicit, opt-in cleanup).
    ///
    /// # Errors
    ///
    /// Returns [`PublishError::FinalDirExists`], [`PublishError::InvalidPath`]
    /// (no file name/parent to derive a sibling from), [`PublishError::StagingDirExists`],
    /// or [`PublishError::Io`] if the staging directory cannot be created fresh.
    pub fn begin(final_dir: impl Into<PathBuf>) -> Result<Self> {
        let final_dir = final_dir.into();
        if final_dir.exists() {
            return Err(PublishError::FinalDirExists(final_dir));
        }
        let file_name = final_dir
            .file_name()
            .ok_or_else(|| PublishError::InvalidPath(final_dir.clone()))?;
        let parent = final_dir
            .parent()
            .ok_or_else(|| PublishError::InvalidPath(final_dir.clone()))?;
        let staging_dir = parent.join(format!("{}.publish-staging", file_name.to_string_lossy()));
        std::fs::create_dir(&staging_dir).map_err(|source| {
            if source.kind() == io::ErrorKind::AlreadyExists {
                PublishError::StagingDirExists(staging_dir.clone())
            } else {
                PublishError::Io {
                    path: staging_dir.clone(),
                    source,
                }
            }
        })?;
        Ok(Self {
            staging_dir,
            final_dir,
        })
    }

    /// The staging directory every leaf, the manifest, and the receipt must
    /// be written into.
    #[must_use]
    pub fn dir(&self) -> &Path {
        &self.staging_dir
    }

    /// Atomically publishes: renames the staging directory to `final_dir`.
    /// Fails closed if `final_dir` sprang into existence since `begin`
    /// (never overwrite), and fails closed (Sol#13) if the staging directory
    /// is not itself a complete publication first — see
    /// [`PublishStaging::check_ready_to_commit`]. Both directories must
    /// share a filesystem for the rename to be atomic — the caller's
    /// responsibility (publish under the same artifacts root as
    /// `final_dir`'s parent).
    ///
    /// On any error (including a not-ready-to-commit staging directory) the
    /// staging directory is left exactly as it was — never removed here —
    /// so it remains as evidence for the caller to inspect (see
    /// [`PublishStaging::abandon`] for an explicit, opt-in cleanup once
    /// that evidence has been looked at).
    ///
    /// # Errors
    ///
    /// Returns [`PublishError::FinalDirExists`], [`PublishError::LeafMissing`]
    /// (staging is missing `manifest.tsv` or `run_receipt.json`),
    /// [`PublishError::StagingNotCovered`] (the manifest and the staged
    /// files disagree on what's present), or [`PublishError::Io`] if the
    /// rename fails.
    pub fn commit(self) -> Result<PathBuf> {
        if self.final_dir.exists() {
            return Err(PublishError::FinalDirExists(self.final_dir));
        }
        self.check_ready_to_commit()?;
        std::fs::rename(&self.staging_dir, &self.final_dir).map_err(|source| PublishError::Io {
            path: self.final_dir.clone(),
            source,
        })?;
        Ok(self.final_dir)
    }

    /// Fails closed (Sol#13) unless the staging directory is a complete
    /// publication: `manifest.tsv` and `run_receipt.json` are both present,
    /// and the manifest names exactly the files staged (never fewer, never
    /// more) — an earlier error path that skipped receipt/manifest
    /// finalization, or that wrote a leaf without ever registering it in
    /// the manifest, must never reach the atomic rename that makes the
    /// final publication name mean "completed."
    fn check_ready_to_commit(&self) -> Result<()> {
        let manifest_path = self.staging_dir.join("manifest.tsv");
        if !manifest_path.is_file() {
            return Err(PublishError::LeafMissing {
                name: "manifest.tsv".to_owned(),
            });
        }
        let receipt_path = self.staging_dir.join("run_receipt.json");
        if !receipt_path.is_file() {
            return Err(PublishError::LeafMissing {
                name: "run_receipt.json".to_owned(),
            });
        }

        let leaves = crate::manifest::read_manifest(&manifest_path)?;
        let manifest_names: HashSet<&str> = leaves.iter().map(|leaf| leaf.name.as_str()).collect();

        let mut staged_names: HashSet<String> = HashSet::new();
        for entry in std::fs::read_dir(&self.staging_dir).map_err(|source| PublishError::Io {
            path: self.staging_dir.clone(),
            source,
        })? {
            let entry = entry.map_err(|source| PublishError::Io {
                path: self.staging_dir.clone(),
                source,
            })?;
            let name = entry.file_name().to_string_lossy().into_owned();
            if name == "manifest.tsv" {
                continue; // the manifest never lists itself.
            }
            staged_names.insert(name);
        }

        let mut unlisted: Vec<&str> = staged_names
            .iter()
            .map(String::as_str)
            .filter(|name| !manifest_names.contains(name))
            .collect();
        unlisted.sort_unstable();
        if !unlisted.is_empty() {
            return Err(PublishError::StagingNotCovered {
                detail: format!(
                    "staged file(s) not listed in manifest.tsv: {}",
                    unlisted.join(", ")
                ),
            });
        }

        let mut missing: Vec<&str> = manifest_names
            .iter()
            .copied()
            .filter(|name| !staged_names.contains(*name))
            .collect();
        missing.sort_unstable();
        if !missing.is_empty() {
            return Err(PublishError::StagingNotCovered {
                detail: format!(
                    "manifest.tsv names file(s) missing from staging: {}",
                    missing.join(", ")
                ),
            });
        }

        Ok(())
    }

    /// Abandons this staging attempt, removing the staging directory and
    /// everything written into it — for a caller that hit an error mid
    /// publish and wants a clean retry rather than a permanently stale
    /// directory blocking [`PublishStaging::begin`]. Never called
    /// implicitly (there is no `Drop` impl): a crash or an unhandled error
    /// leaves the staging directory in place as evidence, on purpose.
    ///
    /// # Errors
    ///
    /// Returns [`PublishError::Io`] if the directory cannot be removed.
    pub fn abandon(self) -> Result<()> {
        std::fs::remove_dir_all(&self.staging_dir).map_err(|source| PublishError::Io {
            path: self.staging_dir.clone(),
            source,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::manifest::{LeafRecord, ManifestBuilder};
    use crate::receipt::RunReceipt;

    fn scratch_dir(label: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "publish_atomic_test_{label}_{}_{:?}",
            std::process::id(),
            std::thread::current().id()
        ));
        std::fs::create_dir_all(&dir).expect("mkdir scratch parent");
        dir
    }

    /// Writes `leaf_name` into `staging`'s directory, then a receipt and a
    /// manifest that fully covers both (the "complete publication" shape
    /// [`PublishStaging::commit`] now requires) — the receipt is itself a
    /// required manifest leaf (Sol#8).
    fn write_complete_staging(staging: &PublishStaging, leaf_name: &str, leaf_bytes: &[u8]) {
        let dir = staging.dir();
        let leaf_path = dir.join(leaf_name);
        std::fs::write(&leaf_path, leaf_bytes).expect("write leaf");
        let (bytes, sha256) = crate::hash::hash_file_bytes(&leaf_path).expect("hash leaf");

        let mut manifest = ManifestBuilder::new();
        manifest.push(LeafRecord {
            name: leaf_name.to_owned(),
            rows: 1,
            bytes,
            sha256,
        });
        let receipt = RunReceipt::new("commit123", "deadbeef", vec!["stage1".to_owned()], 1);
        receipt.write_to(dir).expect("write receipt");
        manifest.push(receipt.leaf_record());
        manifest.write(dir).expect("write manifest");
    }

    #[test]
    fn write_atomic_roundtrips_and_leaves_no_temp_file_behind() {
        let dir = scratch_dir("write_atomic");
        let path = dir.join("thing.txt");
        write_atomic(&path, b"first").expect("first write");
        assert_eq!(std::fs::read(&path).expect("read"), b"first");
        // A second write must cleanly replace the first (rename overwrites).
        write_atomic(&path, b"second").expect("second write");
        assert_eq!(std::fs::read(&path).expect("read"), b"second");

        let leftovers: Vec<_> = std::fs::read_dir(&dir)
            .expect("read_dir")
            .filter_map(std::result::Result::ok)
            .filter(|entry| entry.file_name().to_string_lossy().ends_with(".tmp"))
            .collect();
        assert!(leftovers.is_empty(), "no .tmp file should remain");

        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn staging_begin_commit_moves_content_into_the_final_dir() {
        let parent = scratch_dir("staging_ok");
        let final_dir = parent.join("publication");

        let staging = PublishStaging::begin(&final_dir).expect("begin");
        write_complete_staging(&staging, "leaf.txt", b"leaf bytes");

        let committed = staging.commit().expect("commit");
        assert_eq!(committed, final_dir);
        assert!(final_dir.is_dir());
        assert_eq!(
            std::fs::read(final_dir.join("leaf.txt")).expect("read leaf"),
            b"leaf bytes"
        );
        // The staging path itself must be gone (renamed away, not copied).
        assert!(!parent.join("publication.publish-staging").exists());

        std::fs::remove_dir_all(&parent).ok();
    }

    #[test]
    fn sol13_commit_rejects_staging_missing_the_manifest_and_keeps_the_staging_dir() {
        let parent = scratch_dir("staging_no_manifest");
        let final_dir = parent.join("publication");

        let staging = PublishStaging::begin(&final_dir).expect("begin");
        let staging_path = staging.dir().to_path_buf();
        // An earlier error path wrote one leaf but never reached
        // receipt/manifest finalization.
        std::fs::write(staging.dir().join("leaf.txt"), b"leaf bytes").expect("write leaf");

        let error = staging.commit().expect_err("must refuse to commit");
        assert!(matches!(error, PublishError::LeafMissing { name } if name == "manifest.tsv"));
        // Evidence retained: nothing was deleted, and final_dir never appeared.
        assert!(staging_path.is_dir(), "staging dir must remain as evidence");
        assert!(staging_path.join("leaf.txt").is_file());
        assert!(
            !final_dir.exists(),
            "an incomplete staging must never reach the final name"
        );

        std::fs::remove_dir_all(&parent).ok();
    }

    #[test]
    fn sol13_commit_rejects_staging_missing_the_receipt_and_keeps_the_staging_dir() {
        let parent = scratch_dir("staging_no_receipt");
        let final_dir = parent.join("publication");

        let staging = PublishStaging::begin(&final_dir).expect("begin");
        let staging_path = staging.dir().to_path_buf();
        let leaf_path = staging.dir().join("leaf.txt");
        std::fs::write(&leaf_path, b"leaf bytes").expect("write leaf");
        let (bytes, sha256) = crate::hash::hash_file_bytes(&leaf_path).expect("hash");
        let mut manifest = ManifestBuilder::new();
        manifest.push(LeafRecord {
            name: "leaf.txt".to_owned(),
            rows: 1,
            bytes,
            sha256,
        });
        manifest
            .write(staging.dir())
            .expect("write manifest without a receipt");

        let error = staging.commit().expect_err("must refuse to commit");
        assert!(matches!(error, PublishError::LeafMissing { name } if name == "run_receipt.json"));
        assert!(staging_path.is_dir(), "staging dir must remain as evidence");

        std::fs::remove_dir_all(&parent).ok();
    }

    #[test]
    fn sol13_commit_rejects_a_staged_leaf_the_manifest_never_lists() {
        let parent = scratch_dir("staging_unlisted_leaf");
        let final_dir = parent.join("publication");

        let staging = PublishStaging::begin(&final_dir).expect("begin");
        let staging_path = staging.dir().to_path_buf();
        write_complete_staging(&staging, "leaf_one.txt", b"leaf one");
        // A second leaf lands on disk (e.g. a partially wired writer) but is
        // never registered with the manifest that was already written.
        std::fs::write(staging.dir().join("leaf_two.txt"), b"leaf two").expect("write extra leaf");

        let error = staging.commit().expect_err("must refuse to commit");
        assert!(
            matches!(error, PublishError::StagingNotCovered { detail } if detail.contains("leaf_two.txt"))
        );
        assert!(staging_path.is_dir(), "staging dir must remain as evidence");
        assert!(!final_dir.exists());

        std::fs::remove_dir_all(&parent).ok();
    }

    #[test]
    fn sol13_commit_rejects_a_manifest_entry_missing_from_disk() {
        let parent = scratch_dir("staging_missing_from_disk");
        let final_dir = parent.join("publication");

        let staging = PublishStaging::begin(&final_dir).expect("begin");
        let staging_path = staging.dir().to_path_buf();
        write_complete_staging(&staging, "leaf.txt", b"leaf bytes");
        // The registered leaf is deleted after the manifest named it.
        std::fs::remove_file(staging.dir().join("leaf.txt")).expect("remove leaf");

        let error = staging.commit().expect_err("must refuse to commit");
        assert!(
            matches!(error, PublishError::StagingNotCovered { detail } if detail.contains("leaf.txt"))
        );
        assert!(staging_path.is_dir(), "staging dir must remain as evidence");

        std::fs::remove_dir_all(&parent).ok();
    }

    #[test]
    fn begin_refuses_to_overwrite_an_existing_final_dir() {
        let parent = scratch_dir("staging_final_exists");
        let final_dir = parent.join("publication");
        std::fs::create_dir_all(&final_dir).expect("pre-create final_dir");

        let error = PublishStaging::begin(&final_dir).expect_err("must refuse");
        assert!(matches!(error, PublishError::FinalDirExists(path) if path == final_dir));

        std::fs::remove_dir_all(&parent).ok();
    }

    #[test]
    fn begin_refuses_to_reuse_a_stale_staging_dir() {
        let parent = scratch_dir("staging_stale");
        let final_dir = parent.join("publication");
        let stale_staging = parent.join("publication.publish-staging");
        std::fs::create_dir_all(&stale_staging).expect("simulate a crashed prior attempt");

        let error = PublishStaging::begin(&final_dir).expect_err("must refuse");
        assert!(matches!(error, PublishError::StagingDirExists(path) if path == stale_staging));

        std::fs::remove_dir_all(&parent).ok();
    }

    #[test]
    fn abandon_removes_the_staging_dir_without_touching_final() {
        let parent = scratch_dir("staging_abandon");
        let final_dir = parent.join("publication");
        let staging = PublishStaging::begin(&final_dir).expect("begin");
        let staging_path = staging.dir().to_path_buf();
        std::fs::write(staging.dir().join("partial.txt"), b"oops").expect("write");

        staging.abandon().expect("abandon");
        assert!(!staging_path.exists());
        assert!(!final_dir.exists(), "abandon must never create final_dir");

        std::fs::remove_dir_all(&parent).ok();
    }
}
