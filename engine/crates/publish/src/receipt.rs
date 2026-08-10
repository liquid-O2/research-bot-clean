//! `run_receipt.json`: input authority shas, executable sha, git commit,
//! argv, contract version, and the estimator sha pin (design brief §D; EVENTS.3
//! design amendment v2 §A1). Every "pin" field here is compiled into this
//! crate as a constant, never hand-copied by a caller — see the
//! module-level constants below, sourced from `corpus`/`pubread` themselves
//! or from the frozen truth-authority spec.

use crate::error::{PublishError, Result};
use crate::hash::parse_hex32;
use crate::json::{Value, json_string, json_string_array, parse_object};
use crate::manifest::LeafRecord;
use sha2::{Digest as _, Sha256};
use std::fmt::Write as _;
use std::path::{Path, PathBuf};

/// The manifest leaf name `run_receipt.json` is registered under (Sol#8):
/// the receipt is a required manifest leaf like any other, never a
/// side-channel file outside the manifest's coverage.
pub const RECEIPT_LEAF_NAME: &str = "run_receipt.json";

/// The frozen row-count convention for a JSON-document leaf (Sol#8): exactly
/// `1`, regardless of the object's own field count. The manifest's
/// byte-size/sha256 columns are what actually pin the receipt's content;
/// this row count only satisfies the "every leaf has a row count" shape.
pub const RECEIPT_LEAF_ROWS: u64 = 1;

/// This crate's publication contract version. Bumped whenever the leaf
/// set, manifest schema, or receipt schema changes in a way that could
/// break an old verifier against a new publication (or vice versa) —
/// independent of this crate's own Cargo version.
pub const CONTRACT_VERSION: &str = "events3-stage1-publish-v1";

/// The corpus's pinned input-authority digest, re-exported so the receipt
/// writer never hand-copies it.
pub const CORPUS_REGISTRY_SHA256: &str = corpus::EXPECTED_REGISTRY_SHA256;

/// The preserved event-publication's pinned manifest digest, re-exported so
/// the receipt writer never hand-copies it.
pub const EVENT_PUBLICATION_MANIFEST_SHA256: &str = pubread::EXPECTED_MANIFEST_SHA256;

/// Pinned sha256 of `review_protocol_v1/estimator_laws.py` (the frozen
/// Python `year_stratified_session_block_lcb` bootstrap; EVENTS.3 design
/// amendment v2 §A1, `docs/specs/iwm_event_stage_truth_authority_freeze_v4.md`
/// §5.2.4). Rust never reimplements the bootstrap; every receipt cites this
/// file identity so the verifier can check it without touching the file
/// itself.
pub const ESTIMATOR_LAWS_SHA256: &str =
    "fbd1b573a21f0f9a23cc378f7340106d2f16f09236b263fcfadfcaf1227e7708";

/// Manifest leaf name the pinned estimator's own bytes are published under
/// (ruling E21e; closes Sol#7 P1 and Opus#P3-2): `stage1 run` copies the
/// sha-verified source file's exact bytes into `dir/estimator_laws.py` as a
/// declared leaf (never re-derived, never regenerated); `stage1 metrics` and
/// the verifier's `StageGate` invoke ONLY this in-directory copy,
/// re-verifying its sha256 against [`ESTIMATOR_LAWS_SHA256`] before every
/// invocation. Neither ever reads an external path (no `/workspace`-wide
/// search, no archive hardcode) — a publication copied to a clean host with
/// the archive absent remains fully verifiable and metrics-computable from
/// `--dir` alone.
pub const ESTIMATOR_LAWS_LEAF_NAME: &str = "estimator_laws.py";

/// The frozen row-count convention for [`ESTIMATOR_LAWS_LEAF_NAME`] (mirrors
/// [`RECEIPT_LEAF_ROWS`]): a single opaque file, never tabular — the
/// manifest's byte-size/sha256 columns (which must equal
/// [`ESTIMATOR_LAWS_SHA256`] exactly, since the leaf is copied verbatim from
/// the sha-verified source) are what actually pin its content.
pub const ESTIMATOR_LAWS_LEAF_ROWS: u64 = 1;

/// The receipt written into every stage-1 publication directory
/// (`run_receipt.json`).
///
/// The four pinned fields (`contract_version`, `corpus_registry_sha256`,
/// `event_publication_manifest_sha256`, `estimator_laws_sha256`) are never
/// caller-supplied: [`RunReceipt::new`] always fills them from this crate's
/// own compiled-in constants, so a caller cannot construct a receipt that
/// pins the wrong thing. The remaining fields describe THIS run (which
/// binary, which commit, how it was invoked, how many sessions) and are
/// expected to differ from run to run — amendment v2 §A12 explicitly
/// excludes `run_receipt.json` from the cross-worker-count byte-equality
/// law for exactly this reason ("argv differs").
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RunReceipt {
    pub contract_version: String,
    pub git_commit: String,
    pub executable_sha256: String,
    pub argv: Vec<String>,
    pub session_count: u64,
    pub corpus_registry_sha256: String,
    pub event_publication_manifest_sha256: String,
    pub estimator_laws_sha256: String,
}

impl RunReceipt {
    /// Builds a receipt for this run. `git_commit` and `executable_sha256`
    /// are the caller's own process identity (typically a
    /// `build.rs`-embedded `env!("GIT_COMMIT")` and [`executable_sha256`]
    /// called from the running binary — the same convention `cli::main`
    /// already uses for its ledger rows); `argv` is the exact invocation
    /// (e.g. [`current_argv`]); `session_count` is how many sessions this
    /// run covered (1,003 for the full run, fewer for a rehearsal).
    #[must_use]
    pub fn new(
        git_commit: impl Into<String>,
        executable_sha256: impl Into<String>,
        argv: Vec<String>,
        session_count: u64,
    ) -> Self {
        Self {
            contract_version: CONTRACT_VERSION.to_owned(),
            git_commit: git_commit.into(),
            executable_sha256: executable_sha256.into(),
            argv,
            session_count,
            corpus_registry_sha256: CORPUS_REGISTRY_SHA256.to_owned(),
            event_publication_manifest_sha256: EVENT_PUBLICATION_MANIFEST_SHA256.to_owned(),
            estimator_laws_sha256: ESTIMATOR_LAWS_SHA256.to_owned(),
        }
    }

    /// Renders this receipt as pretty-printed JSON (2-space indent, fixed
    /// key order matching the struct's field order). Hand-rolled
    /// (`crate::json`): no `serde`/`serde_json` is vendored in this
    /// workspace and this crate's one JSON artifact is small and
    /// fixed-shape enough not to need one.
    #[must_use]
    pub fn to_json(&self) -> String {
        let fields: [(&str, String); 8] = [
            ("contract_version", json_string(&self.contract_version)),
            ("git_commit", json_string(&self.git_commit)),
            ("executable_sha256", json_string(&self.executable_sha256)),
            ("argv", json_string_array(&self.argv)),
            ("session_count", self.session_count.to_string()),
            (
                "corpus_registry_sha256",
                json_string(&self.corpus_registry_sha256),
            ),
            (
                "event_publication_manifest_sha256",
                json_string(&self.event_publication_manifest_sha256),
            ),
            (
                "estimator_laws_sha256",
                json_string(&self.estimator_laws_sha256),
            ),
        ];
        let mut out = String::from("{\n");
        for (index, (key, value)) in fields.iter().enumerate() {
            let comma = if index + 1 < fields.len() { "," } else { "" };
            writeln!(out, "  \"{key}\": {value}{comma}").expect("writing to a String cannot fail");
        }
        out.push_str("}\n");
        out
    }

    /// Parses `text` as this exact schema.
    ///
    /// # Errors
    ///
    /// Returns [`PublishError::ReceiptMalformed`] if `text` isn't a JSON
    /// object, a required field is missing or the wrong shape (string vs.
    /// number vs. string array), or there's trailing content after the
    /// object.
    pub fn from_json(text: &str) -> Result<Self> {
        let malformed = |detail: String| PublishError::ReceiptMalformed { detail };
        let map = parse_object(text).map_err(malformed)?;

        let string_field = |key: &str| -> Result<String> {
            match map.get(key) {
                Some(Value::String(value)) => Ok(value.clone()),
                Some(_) => Err(malformed(format!("field `{key}` is not a string"))),
                None => Err(malformed(format!("missing field `{key}`"))),
            }
        };
        let number_field = |key: &str| -> Result<u64> {
            match map.get(key) {
                Some(Value::Number(value)) => Ok(*value),
                Some(_) => Err(malformed(format!("field `{key}` is not a number"))),
                None => Err(malformed(format!("missing field `{key}`"))),
            }
        };
        let string_array_field = |key: &str| -> Result<Vec<String>> {
            match map.get(key) {
                Some(Value::StringArray(value)) => Ok(value.clone()),
                Some(_) => Err(malformed(format!("field `{key}` is not a string array"))),
                None => Err(malformed(format!("missing field `{key}`"))),
            }
        };

        Ok(Self {
            contract_version: string_field("contract_version")?,
            git_commit: string_field("git_commit")?,
            executable_sha256: string_field("executable_sha256")?,
            argv: string_array_field("argv")?,
            session_count: number_field("session_count")?,
            corpus_registry_sha256: string_field("corpus_registry_sha256")?,
            event_publication_manifest_sha256: string_field("event_publication_manifest_sha256")?,
            estimator_laws_sha256: string_field("estimator_laws_sha256")?,
        })
    }

    /// Serializes to JSON ([`RunReceipt::to_json`]) and writes
    /// `dir/run_receipt.json` atomically (temp file + rename within `dir`,
    /// via [`crate::atomic::write_atomic`]).
    ///
    /// # Errors
    ///
    /// Returns an I/O error if the write fails.
    pub fn write_to(&self, dir: &Path) -> Result<PathBuf> {
        let path = dir.join("run_receipt.json");
        crate::atomic::write_atomic(&path, self.to_json().as_bytes())?;
        Ok(path)
    }

    /// Reads and parses `dir/run_receipt.json`.
    ///
    /// # Errors
    ///
    /// Returns [`PublishError::LeafMissing`] if the file doesn't exist, an
    /// I/O error if it can't be read, or [`PublishError::ReceiptMalformed`]
    /// if it doesn't parse as this exact schema.
    pub fn read_from(dir: &Path) -> Result<Self> {
        let path = dir.join("run_receipt.json");
        if !path.is_file() {
            return Err(PublishError::LeafMissing {
                name: "run_receipt.json".to_owned(),
            });
        }
        let text = std::fs::read_to_string(&path).map_err(|source| PublishError::Io {
            path: path.clone(),
            source,
        })?;
        Self::from_json(&text)
    }

    /// Checks this receipt's four pinned fields against the running
    /// binary's own compiled-in pins — never against any external file.
    /// This is the "receipt pin checks" half of the source-free verifier
    /// (`crate::verify`).
    ///
    /// # Errors
    ///
    /// Returns [`PublishError::ReceiptPinMismatch`] naming every field that
    /// disagrees.
    pub fn check_pins(&self) -> Result<()> {
        let mut problems = Vec::new();
        if self.contract_version != CONTRACT_VERSION {
            problems.push(format!(
                "contract_version: pinned={CONTRACT_VERSION} receipt={}",
                self.contract_version
            ));
        }
        if self.corpus_registry_sha256 != CORPUS_REGISTRY_SHA256 {
            problems.push(format!(
                "corpus_registry_sha256: pinned={CORPUS_REGISTRY_SHA256} receipt={}",
                self.corpus_registry_sha256
            ));
        }
        if self.event_publication_manifest_sha256 != EVENT_PUBLICATION_MANIFEST_SHA256 {
            problems.push(format!(
                "event_publication_manifest_sha256: pinned={EVENT_PUBLICATION_MANIFEST_SHA256} receipt={}",
                self.event_publication_manifest_sha256
            ));
        }
        if self.estimator_laws_sha256 != ESTIMATOR_LAWS_SHA256 {
            problems.push(format!(
                "estimator_laws_sha256: pinned={ESTIMATOR_LAWS_SHA256} receipt={}",
                self.estimator_laws_sha256
            ));
        }
        if problems.is_empty() {
            Ok(())
        } else {
            Err(PublishError::ReceiptPinMismatch {
                detail: problems.join("; "),
            })
        }
    }

    /// Builds this receipt's own manifest [`LeafRecord`] (Sol#8): name
    /// [`RECEIPT_LEAF_NAME`], the frozen [`RECEIPT_LEAF_ROWS`] row count, and
    /// the byte size/sha256 of exactly the bytes [`RunReceipt::write_to`]
    /// writes. Computed directly from [`RunReceipt::to_json`] rather than by
    /// re-reading the file, so a caller can register it with the
    /// [`crate::manifest::ManifestBuilder`] without an extra round trip —
    /// the two are byte-identical by construction because both serialize
    /// through the same `to_json()`.
    #[must_use]
    pub fn leaf_record(&self) -> LeafRecord {
        let bytes = self.to_json().into_bytes();
        let sha256 = Sha256::digest(&bytes).into();
        LeafRecord {
            name: RECEIPT_LEAF_NAME.to_owned(),
            rows: RECEIPT_LEAF_ROWS,
            bytes: bytes.len() as u64,
            sha256,
        }
    }

    /// Checks this receipt's per-run identity fields — the ones
    /// [`RunReceipt::check_pins`] deliberately leaves alone because they are
    /// expected to differ from run to run (Sol#8):
    ///
    /// - `executable_sha256` must be syntactically a sha256 digest (64
    ///   lowercase hex characters).
    /// - `git_commit` must be present (non-empty).
    /// - `session_count` must equal `expected_session_count` when the caller
    ///   is asserting a specific run size (e.g. `1_003` for the full run, or
    ///   a rehearsal's smaller day count).
    ///
    /// # Errors
    ///
    /// Returns [`PublishError::ReceiptIdentityInvalid`] naming every field
    /// that disagrees.
    pub fn check_identity(&self, expected_session_count: u64) -> Result<()> {
        let mut problems = Vec::new();
        if parse_hex32(&self.executable_sha256).is_none() {
            problems.push(format!(
                "executable_sha256 is not a 64-character lowercase hex sha256: `{}`",
                self.executable_sha256
            ));
        }
        if self.git_commit.trim().is_empty() {
            problems.push("git_commit is empty".to_owned());
        }
        if self.session_count != expected_session_count {
            problems.push(format!(
                "session_count: expected={expected_session_count} receipt={}",
                self.session_count
            ));
        }
        if problems.is_empty() {
            Ok(())
        } else {
            Err(PublishError::ReceiptIdentityInvalid {
                detail: problems.join("; "),
            })
        }
    }
}

/// Sha256 of the currently running executable's own file on disk (same
/// convention as `cli::main::executable_sha256`), for callers that want to
/// self-hash without re-deriving the logic.
///
/// # Errors
///
/// Returns an error if `std::env::current_exe()` or reading it fails.
pub fn executable_sha256() -> std::io::Result<String> {
    let path = std::env::current_exe()?;
    let bytes = std::fs::read(path)?;
    Ok(format!("{:x}", Sha256::digest(&bytes)))
}

/// The exact process invocation (`std::env::args()`), for populating
/// [`RunReceipt::new`]'s `argv`.
#[must_use]
pub fn current_argv() -> Vec<String> {
    std::env::args().collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn scratch_dir(label: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "publish_receipt_test_{label}_{}_{:?}",
            std::process::id(),
            std::thread::current().id()
        ));
        std::fs::create_dir_all(&dir).expect("mkdir scratch");
        dir
    }

    fn sample_receipt() -> RunReceipt {
        RunReceipt::new(
            "abc123",
            "deadbeef",
            vec!["stage1".to_owned(), "run".to_owned()],
            1_003,
        )
    }

    #[test]
    fn new_always_fills_the_pinned_fields_from_this_crates_constants() {
        let receipt = sample_receipt();
        assert_eq!(receipt.contract_version, CONTRACT_VERSION);
        assert_eq!(receipt.corpus_registry_sha256, CORPUS_REGISTRY_SHA256);
        assert_eq!(
            receipt.event_publication_manifest_sha256,
            EVENT_PUBLICATION_MANIFEST_SHA256
        );
        assert_eq!(receipt.estimator_laws_sha256, ESTIMATOR_LAWS_SHA256);
        assert_eq!(receipt.git_commit, "abc123");
        assert_eq!(receipt.executable_sha256, "deadbeef");
        assert_eq!(receipt.session_count, 1_003);
        receipt.check_pins().expect("freshly built receipt pins");
    }

    #[test]
    fn json_round_trip_via_disk_preserves_every_field() {
        let dir = scratch_dir("roundtrip");
        let receipt = sample_receipt();
        let path = receipt.write_to(&dir).expect("write");
        assert!(path.is_file());

        let read_back = RunReceipt::read_from(&dir).expect("read");
        assert_eq!(read_back, receipt);

        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn the_written_json_contains_every_schema_field_by_name() {
        let dir = scratch_dir("schema");
        sample_receipt().write_to(&dir).expect("write");
        let text = std::fs::read_to_string(dir.join("run_receipt.json")).expect("read text");
        for field in [
            "contract_version",
            "git_commit",
            "executable_sha256",
            "argv",
            "session_count",
            "corpus_registry_sha256",
            "event_publication_manifest_sha256",
            "estimator_laws_sha256",
        ] {
            assert!(text.contains(field), "missing field `{field}` in {text}");
        }
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn read_from_a_directory_with_no_receipt_is_leaf_missing() {
        let dir = scratch_dir("missing");
        let error = RunReceipt::read_from(&dir).expect_err("must fail");
        assert!(matches!(error, PublishError::LeafMissing { name } if name == "run_receipt.json"));
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn check_pins_rejects_a_tampered_estimator_sha() {
        let mut receipt = sample_receipt();
        receipt.estimator_laws_sha256 = "0".repeat(64);
        let error = receipt.check_pins().expect_err("must reject");
        assert!(matches!(error, PublishError::ReceiptPinMismatch { .. }));
    }

    #[test]
    fn check_pins_rejects_a_tampered_contract_version() {
        let mut receipt = sample_receipt();
        receipt.contract_version = "some-other-contract".to_owned();
        let error = receipt.check_pins().expect_err("must reject");
        assert!(matches!(error, PublishError::ReceiptPinMismatch { .. }));
    }

    #[test]
    fn malformed_json_is_rejected() {
        let dir = scratch_dir("malformed");
        std::fs::write(dir.join("run_receipt.json"), b"{ not json").expect("write");
        let error = RunReceipt::read_from(&dir).expect_err("must fail");
        assert!(matches!(error, PublishError::ReceiptMalformed { .. }));
        std::fs::remove_dir_all(&dir).ok();
    }
}
