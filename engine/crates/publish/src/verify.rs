//! Source-free verifier core (design brief §D as amended by A10): leaf sha
//! recheck + receipt pin/identity checks + a mandatory gate-quantity
//! recomputation. [`verify_publication`] consumes ONLY `dir` — nothing here
//! opens the corpus, the preserved event publication, or any other path
//! outside `dir`; the four pinned fields it checks the receipt against are
//! this crate's own compiled-in constants (`crate::receipt::CONTRACT_VERSION`
//! and friends), never a re-read of any external file.
//!
//! [`verify_publication`] is the one ACCEPTING entry point (Sol#2 minimal
//! fix): it requires the manifest to name exactly the caller's registered
//! required leaf inventory (Opus#F4), requires the receipt to carry exactly
//! one manifest leaf entry with sane identity fields (Sol#8), and requires a
//! [`GateRecomputer`] to run and succeed — there is no longer an `Ok` path
//! for "no gate was wired." Gate-quantity recomputation itself (recall, LCB
//! inputs, d1/d2 split, burden, duplicates, conflicts, ambiguity, frontier,
//! proposal bank — design brief §C, Sol condition 5) is implemented by
//! [`crate::gate::StageGate`] (built exclusively against `metrics`'s public
//! types/functions, per that module's own doc comment for the full leaf
//! contract and its recorded escalations) and wired through the
//! [`GateRecomputer`] seam this module defines; this module itself never
//! implements the recomputation, only the seam and the generic leaf/receipt
//! checks around it. [`inspect_leaf_checksums`] is the separate, deliberately
//! non-accepting diagnostic that only rechecks leaf bytes (Sol#2).

use crate::error::{PublishError, Result};
use crate::hash::{hash_file_bytes, hex32};
use crate::manifest::{LeafRecord, read_manifest};
use crate::receipt::{RECEIPT_LEAF_NAME, RunReceipt};
use parquet::file::reader::FileReader;
use std::collections::BTreeSet;
use std::fs::File;
use std::path::Path;

/// The typed seam EVENTS.4 plugs `metrics`'s gate-quantity recomputation
/// into. An implementation must recompute every gate quantity strictly from
/// files under `dir` (never an external read, to stay source-free) and
/// compare them to the frozen scientific gate.
pub trait GateRecomputer {
    /// # Errors
    ///
    /// Returns an error describing the first gate quantity that fails to
    /// reproduce exactly.
    fn recompute(&self, dir: &Path) -> Result<()>;
}

/// What [`verify_publication`] found. Reaching `Ok` means every leaf
/// rechecked, the required leaf-name inventory matched exactly, the receipt
/// pinned and identified this run correctly, and the supplied
/// [`GateRecomputer`] ran and succeeded — this crate no longer has a
/// success shape that skips gate recomputation.
#[derive(Debug)]
pub struct VerificationReport {
    /// How many leaves `manifest.tsv` named (every one of them matched, or
    /// this call would have returned an error instead).
    pub leaves_checked: usize,
}

/// What [`inspect_leaf_checksums`] found. Deliberately a distinct type from
/// [`VerificationReport`]: this is NOT an acceptance result.
#[derive(Debug)]
pub struct LeafInspectionReport {
    /// How many leaves `manifest.tsv` named and had their row
    /// count/byte size/sha256 rechecked.
    pub leaves_checked: usize,
}

/// Runs the source-free verifier over a published stage-1 directory and
/// decides whether it is ACCEPTED:
///
/// 1. Reads `dir/manifest.tsv`, recomputes every named leaf's row count,
///    byte size, and sha256 straight from the file under `dir`, and
///    requires exact equality with what the manifest recorded (rejecting a
///    leaf name that is not a single normal path component under `dir`, a
///    duplicate name, or a leaf whose canonicalized path escapes `dir` —
///    Sol#9).
/// 2. Requires the manifest's leaf-name set to equal `required_leaves`
///    exactly: errors naming every missing or extra scientific leaf
///    (Opus#F4).
/// 3. Requires the manifest to name exactly one `run_receipt.json` leaf
///    (Sol#8).
/// 4. Reads `dir/run_receipt.json` and checks its four pinned fields
///    (contract version, corpus registry sha, event-publication manifest
///    sha, estimator sha) against this crate's own compiled-in pins, and
///    its per-run identity fields (`executable_sha256` syntax, `git_commit`
///    presence, `session_count == expected_session_count`) (Sol#8).
/// 5. Requires `gate` to be `Some` and to succeed — `None` is a typed error,
///    never a silent `Ok` (Sol#2): a publication can never be accepted as
///    verified without gate-quantity recomputation.
///
/// Never reads anything outside `dir` (and this build's own compiled-in
/// constants) — the smoke test this enables (per amendment v2 §A10) is
/// running the verifier against a copy of `dir` with the original event
/// publication and corpus absent.
///
/// # Errors
///
/// Returns the first [`PublishError`] encountered: a missing/malformed
/// manifest or receipt, a leaf that doesn't reproduce its manifest entry, a
/// leaf-name-set mismatch, a receipt pin/identity mismatch,
/// [`PublishError::GateRecomputationNotAccepted`] if `gate` is `None`, or
/// whatever `gate` returns.
pub fn verify_publication(
    dir: &Path,
    required_leaves: &BTreeSet<String>,
    expected_session_count: u64,
    gate: Option<&dyn GateRecomputer>,
) -> Result<VerificationReport> {
    let leaves = read_and_verify_leaves(dir)?;

    check_required_leaf_set(&leaves, required_leaves)?;

    let receipt_leaf_count = leaves
        .iter()
        .filter(|leaf| leaf.name == RECEIPT_LEAF_NAME)
        .count();
    if receipt_leaf_count != 1 {
        return Err(PublishError::ReceiptLeafCountInvalid {
            count: receipt_leaf_count,
        });
    }

    let receipt = RunReceipt::read_from(dir)?;
    receipt.check_pins()?;
    receipt.check_identity(expected_session_count)?;

    match gate {
        Some(recomputer) => recomputer.recompute(dir)?,
        None => return Err(PublishError::GateRecomputationNotAccepted),
    }

    Ok(VerificationReport {
        leaves_checked: leaves.len(),
    })
}

/// Checksum-only inspection (Sol#2 minimal fix): recomputes every
/// manifest-named leaf's row count, byte size, and sha256 straight from the
/// file under `dir` and requires exact agreement — nothing else. This is
/// deliberately NOT a verification/acceptance path: unlike
/// [`verify_publication`], it does not check the required leaf-name-set
/// inventory, does not check the receipt's pins or per-run identity, and
/// never runs gate recomputation. A directory that "passes" this call has
/// not been verified or accepted; use [`verify_publication`] for that.
///
/// # Errors
///
/// Returns the first [`PublishError`] encountered rechecking the manifest's
/// leaves (see [`verify_publication`]'s leaf-checking errors).
pub fn inspect_leaf_checksums(dir: &Path) -> Result<LeafInspectionReport> {
    let leaves = read_and_verify_leaves(dir)?;
    Ok(LeafInspectionReport {
        leaves_checked: leaves.len(),
    })
}

/// Shared by [`verify_publication`] and [`inspect_leaf_checksums`]: reads
/// `dir/manifest.tsv` (name-shape/duplicate validation lives in
/// [`read_manifest`]) and rechecks every named leaf's bytes.
fn read_and_verify_leaves(dir: &Path) -> Result<Vec<LeafRecord>> {
    let manifest_path = dir.join("manifest.tsv");
    if !manifest_path.is_file() {
        return Err(PublishError::LeafMissing {
            name: "manifest.tsv".to_owned(),
        });
    }
    let leaves = read_manifest(&manifest_path)?;
    for leaf in &leaves {
        verify_one_leaf(dir, leaf)?;
    }
    Ok(leaves)
}

/// Errors naming every leaf `required` expects but `leaves` doesn't name,
/// and every leaf `leaves` names but `required` doesn't expect (Opus#F4): a
/// manifest that silently omits a scientific leaf, or that carries an extra
/// unregistered one, is never a match for the frozen inventory.
fn check_required_leaf_set(leaves: &[LeafRecord], required: &BTreeSet<String>) -> Result<()> {
    let present: BTreeSet<&str> = leaves.iter().map(|leaf| leaf.name.as_str()).collect();
    let missing: Vec<String> = required
        .iter()
        .filter(|name| !present.contains(name.as_str()))
        .cloned()
        .collect();
    let extra: Vec<String> = present
        .iter()
        .filter(|name| !required.contains(**name))
        .map(|name| (*name).to_owned())
        .collect();
    if missing.is_empty() && extra.is_empty() {
        Ok(())
    } else {
        Err(PublishError::RequiredLeafSetMismatch { missing, extra })
    }
}

fn verify_one_leaf(dir: &Path, leaf: &LeafRecord) -> Result<()> {
    let path = dir.join(&leaf.name);
    if !path.is_file() {
        return Err(PublishError::LeafMissing {
            name: leaf.name.clone(),
        });
    }

    // Canonical containment check (Sol#9): `leaf.name` is already
    // restricted to a single normal path component by `read_manifest`, so
    // no textual `..`/absolute path can direct `dir.join(&leaf.name)`
    // outside `dir` — this additionally guards against a leaf name that is
    // itself a symlink resolving outside `dir`, checked before any byte of
    // it is read.
    let dir_canon = dir.canonicalize().map_err(|source| PublishError::Io {
        path: dir.to_path_buf(),
        source,
    })?;
    let leaf_canon = path.canonicalize().map_err(|source| PublishError::Io {
        path: path.clone(),
        source,
    })?;
    if !leaf_canon.starts_with(&dir_canon) {
        return Err(PublishError::LeafEscapesDirectory {
            name: leaf.name.clone(),
        });
    }

    let (bytes, sha256) = hash_file_bytes(&path)?;
    let rows = recompute_rows(&path)?;

    let mut problems = Vec::new();
    if rows != leaf.rows {
        problems.push(format!("rows: manifest={} actual={rows}", leaf.rows));
    }
    if bytes != leaf.bytes {
        problems.push(format!("bytes: manifest={} actual={bytes}", leaf.bytes));
    }
    if sha256 != leaf.sha256 {
        problems.push(format!(
            "sha256: manifest={} actual={}",
            hex32(&leaf.sha256),
            hex32(&sha256)
        ));
    }
    if problems.is_empty() {
        Ok(())
    } else {
        Err(PublishError::LeafVerificationFailed {
            name: leaf.name.clone(),
            detail: problems.join("; "),
        })
    }
}

/// Recomputes a leaf's row count from its own bytes under `dir`: parquet
/// leaves from the file's own footer `num_rows`, TSV leaves from newline
/// count minus the header line (the same convention `pubread` and this
/// crate's manifest both use), JSON leaves (`run_receipt.json`, Sol#8) from
/// the frozen JSON-document row-count convention
/// (`crate::receipt::RECEIPT_LEAF_ROWS`, always `1`), and the pinned
/// estimator law file (`estimator_laws.py`, ruling E21e) from its own frozen
/// single-file row-count convention (`crate::receipt::ESTIMATOR_LAWS_LEAF_ROWS`,
/// always `1`) — the manifest's byte-size/sha256 columns, not this row
/// count, are what actually pin a JSON/`.py` leaf's content.
fn recompute_rows(path: &Path) -> Result<u64> {
    match path.extension().and_then(std::ffi::OsStr::to_str) {
        Some("parquet") => parquet_row_count(path),
        Some("tsv") => crate::hash::count_tsv_rows(path),
        Some("json") => Ok(crate::receipt::RECEIPT_LEAF_ROWS),
        Some("py") => Ok(crate::receipt::ESTIMATOR_LAWS_LEAF_ROWS),
        _ => Err(PublishError::UnknownLeafKind {
            path: path.to_path_buf(),
        }),
    }
}

fn parquet_row_count(path: &Path) -> Result<u64> {
    let file = File::open(path).map_err(|source| PublishError::Io {
        path: path.to_path_buf(),
        source,
    })?;
    let reader = parquet::file::reader::SerializedFileReader::new(file)?;
    let num_rows = reader.metadata().file_metadata().num_rows();
    u64::try_from(num_rows).map_err(|_| PublishError::ArithmeticOverflow)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::atomic::PublishStaging;
    use crate::manifest::ManifestBuilder;
    use crate::parquet_leaf::LeafWriter;
    use crate::receipt::RunReceipt;
    use arrow_array::{Int64Array, RecordBatch};
    use arrow_schema::{DataType, Field, Schema};
    use std::fmt::Write as _;
    use std::path::PathBuf;
    use std::sync::Arc;

    fn scratch_final_dir(label: &str) -> PathBuf {
        let parent = std::env::temp_dir().join(format!(
            "publish_verify_test_{label}_{}_{:?}",
            std::process::id(),
            std::thread::current().id()
        ));
        std::fs::create_dir_all(&parent).expect("mkdir scratch parent");
        parent.join("publication")
    }

    /// The exact leaf-name inventory [`build_sample_publication`] produces:
    /// one parquet leaf, its companion session-index leaf (Sol#12), one
    /// hand-written TSV leaf, and the receipt (Sol#8).
    fn sample_required_leaves() -> BTreeSet<String> {
        [
            "labels_sample.parquet",
            "labels_sample_session_index.tsv",
            "evaluation_registry.tsv",
            RECEIPT_LEAF_NAME,
        ]
        .into_iter()
        .map(str::to_owned)
        .collect()
    }

    struct AlwaysOkGate;
    impl GateRecomputer for AlwaysOkGate {
        fn recompute(&self, dir: &Path) -> Result<()> {
            // A real EVENTS.4 implementation would recompute gate
            // quantities from files under `dir`; this stand-in only proves
            // the seam is wired, so it just confirms `dir` is reachable.
            if dir.is_dir() {
                Ok(())
            } else {
                Err(PublishError::LeafMissing {
                    name: "dir".to_owned(),
                })
            }
        }
    }

    /// Builds one small, complete, valid publication (one parquet leaf +
    /// its session-index companion, one hand-written TSV leaf, a manifest,
    /// and a receipt) inside a fresh atomic-published directory, and
    /// returns its final path. Exactly one session (`session_count = 1`,
    /// matching [`sample_required_leaves`]).
    fn build_sample_publication(final_dir: &Path) -> PathBuf {
        let staging = PublishStaging::begin(final_dir).expect("begin staging");
        let dir = staging.dir().to_path_buf();

        let schema = Arc::new(Schema::new(vec![Field::new(
            "value_u6",
            DataType::Int64,
            false,
        )]));
        let mut writer =
            LeafWriter::create(&dir, "labels_sample", Arc::clone(&schema)).expect("create writer");
        writer
            .write_session(
                1,
                "2022-01-03",
                &RecordBatch::try_new(
                    Arc::clone(&schema),
                    vec![Arc::new(Int64Array::from(vec![1, 2, 3]))],
                )
                .expect("batch"),
            )
            .expect("write session");
        let finished = writer.finish(1).expect("finish parquet leaf");

        let tsv_path = dir.join("evaluation_registry.tsv");
        std::fs::write(&tsv_path, "field\tvalue\na\t1\nb\t2\n").expect("write tsv leaf");
        let (tsv_bytes, tsv_sha256) = hash_file_bytes(&tsv_path).expect("hash tsv leaf");

        let mut manifest = ManifestBuilder::new();
        manifest.push(finished.leaf);
        manifest.push(finished.session_index);
        manifest.push(LeafRecord {
            name: "evaluation_registry.tsv".to_owned(),
            rows: 2,
            bytes: tsv_bytes,
            sha256: tsv_sha256,
        });

        let receipt = RunReceipt::new("commit123", "a".repeat(64), vec!["stage1".to_owned()], 1);
        receipt.write_to(&dir).expect("write receipt");
        manifest.push(receipt.leaf_record());
        manifest.write(&dir).expect("write manifest last");

        staging.commit().expect("commit")
    }

    /// Rewrites `receipt` to disk AND re-patches `manifest.tsv`'s receipt
    /// row to match its new bytes exactly — a fully self-consistent forged
    /// publication, so a leaf-checksum recheck alone cannot catch the
    /// problem. Used to exercise `check_pins`/`check_identity` on their own
    /// merits, distinct from the ordinary "tampered after the manifest was
    /// written" case.
    fn rewrite_receipt_and_repatch_manifest(dir: &Path, receipt: &RunReceipt) {
        receipt.write_to(dir).expect("rewrite receipt");
        let manifest_path = dir.join("manifest.tsv");
        let mut leaves = read_manifest(&manifest_path).expect("read manifest");
        leaves.retain(|leaf| leaf.name != RECEIPT_LEAF_NAME);
        let mut manifest = ManifestBuilder::new();
        for leaf in leaves {
            manifest.push(leaf);
        }
        manifest.push(receipt.leaf_record());
        manifest.write(dir).expect("rewrite manifest");
    }

    #[test]
    fn a_freshly_built_publication_is_accepted_with_a_wired_gate() {
        let final_dir = scratch_final_dir("clean");
        let published = build_sample_publication(&final_dir);

        let gate = AlwaysOkGate;
        let report = verify_publication(&published, &sample_required_leaves(), 1, Some(&gate))
            .expect("verify");
        assert_eq!(report.leaves_checked, 4);

        std::fs::remove_dir_all(published.parent().expect("parent")).ok();
    }

    /// Sol#2 minimal fix: absence of a `GateRecomputer` is a typed error,
    /// never the old `Ok(NotWired)` acceptance.
    #[test]
    fn sol2_gate_absent_is_a_typed_error_not_an_ok_notwired_result() {
        let final_dir = scratch_final_dir("gate_required");
        let published = build_sample_publication(&final_dir);

        let error = verify_publication(&published, &sample_required_leaves(), 1, None)
            .expect_err("must not accept without a gate");
        assert!(matches!(error, PublishError::GateRecomputationNotAccepted));

        std::fs::remove_dir_all(published.parent().expect("parent")).ok();
    }

    /// Sol#2: the checksum-only diagnostic is a distinct, non-accepting
    /// function — no required-leaf-set check, no receipt checks, no gate.
    #[test]
    fn inspect_leaf_checksums_is_a_separate_non_accepting_diagnostic() {
        let final_dir = scratch_final_dir("diagnostic");
        let published = build_sample_publication(&final_dir);

        let report = inspect_leaf_checksums(&published).expect("inspect");
        assert_eq!(report.leaves_checked, 4);

        std::fs::remove_dir_all(published.parent().expect("parent")).ok();
    }

    #[test]
    fn verify_publication_never_needs_anything_outside_dir() {
        // A disconnected scratch directory unrelated to any corpus or event
        // publication path: if `verify_publication` needed an external
        // read, this would fail regardless of the copied directory's own
        // content.
        let final_dir = scratch_final_dir("source_free");
        let published = build_sample_publication(&final_dir);

        // Move the whole publication to an entirely different scratch
        // location to demonstrate nothing ties it to its original parent.
        let moved_parent = std::env::temp_dir().join(format!(
            "publish_verify_moved_{}_{:?}",
            std::process::id(),
            std::thread::current().id()
        ));
        std::fs::create_dir_all(&moved_parent).expect("mkdir moved parent");
        let moved = moved_parent.join("publication");
        std::fs::rename(&published, &moved).expect("move publication");

        let gate = AlwaysOkGate;
        let report = verify_publication(&moved, &sample_required_leaves(), 1, Some(&gate))
            .expect("verify after move");
        assert_eq!(report.leaves_checked, 4);

        std::fs::remove_dir_all(published.parent().expect("parent")).ok();
        std::fs::remove_dir_all(&moved_parent).ok();
    }

    #[test]
    fn tampering_with_a_leaf_after_manifest_is_written_is_caught() {
        let final_dir = scratch_final_dir("tamper_leaf");
        let published = build_sample_publication(&final_dir);

        // Flip a byte in the TSV leaf's content after the manifest was
        // written — the manifest's recorded sha256/bytes now disagree.
        let leaf_path = published.join("evaluation_registry.tsv");
        std::fs::write(&leaf_path, "field\tvalue\na\t999\nb\t2\n").expect("tamper");

        let gate = AlwaysOkGate;
        let error = verify_publication(&published, &sample_required_leaves(), 1, Some(&gate))
            .expect_err("must fail");
        assert!(
            matches!(error, PublishError::LeafVerificationFailed { name, .. } if name == "evaluation_registry.tsv")
        );

        std::fs::remove_dir_all(published.parent().expect("parent")).ok();
    }

    /// Sol#8's concrete failure scenario: change only a per-run identity
    /// field (`executable_sha256`) and `session_count`, leaving the four
    /// compiled pins intact, without touching `manifest.tsv`. Now that the
    /// receipt is itself a required manifest leaf, this is caught as an
    /// ordinary leaf checksum mismatch — the recorded executable/session
    /// identity IS bound to the published bytes.
    #[test]
    fn sol8_tampering_with_non_pinned_receipt_fields_is_caught_via_the_manifest_leaf() {
        let final_dir = scratch_final_dir("tamper_receipt_identity");
        let published = build_sample_publication(&final_dir);

        let mut receipt = RunReceipt::read_from(&published).expect("read receipt");
        receipt.executable_sha256 = "not-a-sha-at-all".to_owned();
        receipt.session_count = 0;
        receipt
            .write_to(&published)
            .expect("rewrite tampered receipt (manifest left untouched)");

        let gate = AlwaysOkGate;
        let error = verify_publication(&published, &sample_required_leaves(), 1, Some(&gate))
            .expect_err("must fail");
        assert!(
            matches!(error, PublishError::LeafVerificationFailed { name, .. } if name == RECEIPT_LEAF_NAME)
        );

        std::fs::remove_dir_all(published.parent().expect("parent")).ok();
    }

    /// Sol#8: even a fully self-consistent forged manifest (receipt bytes
    /// and its manifest row rewritten together) cannot survive
    /// `check_pins`.
    #[test]
    fn tampering_with_the_receipts_estimator_pin_is_caught_even_in_a_self_consistent_manifest() {
        let final_dir = scratch_final_dir("tamper_pin_consistent");
        let published = build_sample_publication(&final_dir);

        let mut receipt = RunReceipt::read_from(&published).expect("read receipt");
        receipt.estimator_laws_sha256 = "1".repeat(64);
        rewrite_receipt_and_repatch_manifest(&published, &receipt);

        let gate = AlwaysOkGate;
        let error = verify_publication(&published, &sample_required_leaves(), 1, Some(&gate))
            .expect_err("must fail");
        assert!(matches!(error, PublishError::ReceiptPinMismatch { .. }));

        std::fs::remove_dir_all(published.parent().expect("parent")).ok();
    }

    /// Sol#8: same self-consistent-forgery construction, but for the
    /// per-run identity field `session_count` against the caller's expected
    /// value — `check_identity`'s own job, distinct from `check_pins`.
    #[test]
    fn sol8_session_count_mismatch_is_caught_even_in_a_self_consistent_manifest() {
        let final_dir = scratch_final_dir("tamper_session_count_consistent");
        let published = build_sample_publication(&final_dir);

        let mut receipt = RunReceipt::read_from(&published).expect("read receipt");
        receipt.session_count = 999;
        rewrite_receipt_and_repatch_manifest(&published, &receipt);

        let gate = AlwaysOkGate;
        let error = verify_publication(&published, &sample_required_leaves(), 1, Some(&gate))
            .expect_err("must fail");
        assert!(matches!(error, PublishError::ReceiptIdentityInvalid { .. }));

        std::fs::remove_dir_all(published.parent().expect("parent")).ok();
    }

    /// Sol#8's "exactly-one-receipt" assertion, exercised through the
    /// general duplicate-leaf-name rejection (Sol#9) a caller bug would hit
    /// first if it ever registered `run_receipt.json` twice.
    #[test]
    fn sol8_a_duplicated_receipt_manifest_row_is_rejected() {
        let final_dir = scratch_final_dir("duplicate_receipt_row");
        let published = build_sample_publication(&final_dir);

        let manifest_path = published.join("manifest.tsv");
        let mut text = std::fs::read_to_string(&manifest_path).expect("read manifest");
        let receipt_row = text
            .lines()
            .find(|line| line.starts_with(RECEIPT_LEAF_NAME))
            .expect("receipt row present")
            .to_owned();
        text.push_str(&receipt_row);
        text.push('\n');
        std::fs::write(&manifest_path, text).expect("duplicate the receipt row");

        let gate = AlwaysOkGate;
        let error = verify_publication(&published, &sample_required_leaves(), 1, Some(&gate))
            .expect_err("must fail");
        assert!(
            matches!(error, PublishError::LeafNameDuplicate { name } if name == RECEIPT_LEAF_NAME)
        );

        std::fs::remove_dir_all(published.parent().expect("parent")).ok();
    }

    #[test]
    fn a_directory_missing_manifest_is_an_incomplete_publish() {
        let final_dir = scratch_final_dir("missing_manifest");
        let published = build_sample_publication(&final_dir);
        std::fs::remove_file(published.join("manifest.tsv")).expect("remove manifest");

        let gate = AlwaysOkGate;
        let error = verify_publication(&published, &sample_required_leaves(), 1, Some(&gate))
            .expect_err("must fail");
        assert!(matches!(error, PublishError::LeafMissing { name } if name == "manifest.tsv"));

        std::fs::remove_dir_all(published.parent().expect("parent")).ok();
    }

    /// Opus#F4: a manifest that omits a required scientific leaf — while
    /// every leaf it DOES name still checks out perfectly — must not verify
    /// clean.
    #[test]
    fn opus_f4_a_manifest_omitting_a_required_leaf_is_rejected() {
        let final_dir = scratch_final_dir("omitted_leaf");
        let published = build_sample_publication(&final_dir);

        let manifest_path = published.join("manifest.tsv");
        let text = std::fs::read_to_string(&manifest_path).expect("read manifest");
        let patched = text
            .lines()
            .filter(|line| !line.starts_with("evaluation_registry.tsv"))
            .fold(String::new(), |mut acc, line| {
                writeln!(acc, "{line}").expect("writing to a String cannot fail");
                acc
            });
        std::fs::write(&manifest_path, patched).expect("omit a leaf from the manifest");

        let gate = AlwaysOkGate;
        let error = verify_publication(&published, &sample_required_leaves(), 1, Some(&gate))
            .expect_err("must fail");
        match error {
            PublishError::RequiredLeafSetMismatch { missing, extra } => {
                assert_eq!(missing, vec!["evaluation_registry.tsv".to_owned()]);
                assert!(extra.is_empty());
            }
            other => panic!("expected RequiredLeafSetMismatch, got {other:?}"),
        }

        std::fs::remove_dir_all(published.parent().expect("parent")).ok();
    }

    /// Opus#F4, the mirror case: an extra, unregistered leaf sitting in the
    /// manifest (e.g. a wiring bug that writes and registers something
    /// nobody asked for) must also be rejected.
    #[test]
    fn opus_f4_a_manifest_naming_an_unregistered_extra_leaf_is_rejected() {
        let final_dir = scratch_final_dir("extra_leaf");
        let published = build_sample_publication(&final_dir);

        let extra_path = published.join("surprise.tsv");
        std::fs::write(&extra_path, "field\tvalue\nz\t9\n").expect("write extra leaf");
        let (bytes, sha256) = hash_file_bytes(&extra_path).expect("hash extra leaf");
        let manifest_path = published.join("manifest.tsv");
        let mut leaves = read_manifest(&manifest_path).expect("read manifest");
        leaves.push(LeafRecord {
            name: "surprise.tsv".to_owned(),
            rows: 1,
            bytes,
            sha256,
        });
        let mut manifest = ManifestBuilder::new();
        for leaf in leaves {
            manifest.push(leaf);
        }
        manifest
            .write(&published)
            .expect("rewrite manifest with an extra leaf");

        let gate = AlwaysOkGate;
        let error = verify_publication(&published, &sample_required_leaves(), 1, Some(&gate))
            .expect_err("must fail");
        match error {
            PublishError::RequiredLeafSetMismatch { missing, extra } => {
                assert!(missing.is_empty());
                assert_eq!(extra, vec!["surprise.tsv".to_owned()]);
            }
            other => panic!("expected RequiredLeafSetMismatch, got {other:?}"),
        }

        std::fs::remove_dir_all(published.parent().expect("parent")).ok();
    }

    /// Sol#9's concrete scenario: a manifest row naming a leaf that climbs
    /// outside `dir` via `..`, paired with a real sibling file whose bytes
    /// match the injected row exactly. It must never be opened at all —
    /// rejected at manifest-parse time, before any read outside `dir`.
    #[test]
    fn sol9_a_manifest_row_climbing_outside_dir_is_rejected_before_anything_is_opened() {
        let final_dir = scratch_final_dir("escape_dotdot");
        let published = build_sample_publication(&final_dir);

        // A real file living next to the publication directory that the
        // escaping row's bytes/sha would match, if it were ever opened.
        let outside_path = published.parent().expect("parent").join("outside.tsv");
        std::fs::write(&outside_path, "secret\tvalue\nx\t1\n").expect("write outside file");
        let (bytes, sha256) = hash_file_bytes(&outside_path).expect("hash outside file");

        let manifest_path = published.join("manifest.tsv");
        let mut text = std::fs::read_to_string(&manifest_path).expect("read manifest");
        writeln!(text, "../outside.tsv\t1\t{bytes}\t{}", hex32(&sha256))
            .expect("writing to a String cannot fail");
        std::fs::write(&manifest_path, text).expect("inject escaping row");

        let gate = AlwaysOkGate;
        let error = verify_publication(&published, &sample_required_leaves(), 1, Some(&gate))
            .expect_err("must fail");
        assert!(
            matches!(error, PublishError::LeafNameInvalid { name } if name == "../outside.tsv")
        );

        std::fs::remove_file(&outside_path).ok();
        std::fs::remove_dir_all(published.parent().expect("parent")).ok();
    }

    /// Defense-in-depth companion to Sol#9's textual-escape case: a valid
    /// single-component leaf name whose file is a symlink resolving outside
    /// `dir` must be rejected by the canonical containment check, even
    /// though name-shape validation alone cannot see it.
    #[test]
    #[cfg(unix)]
    fn sol9_a_leaf_name_that_is_a_symlink_escaping_dir_is_rejected() {
        let final_dir = scratch_final_dir("escape_symlink");
        let published = build_sample_publication(&final_dir);

        let outside_path = published
            .parent()
            .expect("parent")
            .join("outside_via_symlink.tsv");
        std::fs::write(&outside_path, "secret\tvalue\nx\t1\n").expect("write outside file");
        let (bytes, sha256) = hash_file_bytes(&outside_path).expect("hash outside file");

        let escape_name = "escape.tsv";
        std::os::unix::fs::symlink(&outside_path, published.join(escape_name))
            .expect("create symlink leaf");

        let manifest_path = published.join("manifest.tsv");
        let mut text = std::fs::read_to_string(&manifest_path).expect("read manifest");
        writeln!(text, "{escape_name}\t1\t{bytes}\t{}", hex32(&sha256))
            .expect("writing to a String cannot fail");
        std::fs::write(&manifest_path, text).expect("inject symlink row");

        let gate = AlwaysOkGate;
        let error = verify_publication(&published, &sample_required_leaves(), 1, Some(&gate))
            .expect_err("must fail");
        assert!(
            matches!(error, PublishError::LeafEscapesDirectory { name } if name == escape_name)
        );

        std::fs::remove_file(&outside_path).ok();
        std::fs::remove_dir_all(published.parent().expect("parent")).ok();
    }
}
