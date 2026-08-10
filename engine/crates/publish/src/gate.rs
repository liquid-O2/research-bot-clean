//! `StageGate`: the [`crate::verify::GateRecomputer`] seam's concrete
//! implementation (design brief §D "Sol condition 5"; amendment v2 §A1,
//! §A9, §A10, ruling E14).
//!
//! # Scope and the leaf contract this module freezes
//!
//! [`crate::verify::verify_publication`]'s own doc comment says gate-quantity
//! recomputation is "EVENTS.4 work against `metrics`'s typed session-recall /
//! evaluation-registry inputs" and that this crate "never implements it
//! itself" — this module is that EVENTS.4 wiring, built exclusively against
//! `metrics`'s public API (types and pure functions only; this module never
//! re-derives a scientific rule `metrics` already encodes).
//!
//! **Escalation (recorded, not silently guessed):** as of this module, no
//! prior spec pins the exact leaf name/schema for anything beyond
//! `session_recall.tsv` (A1's schema is exact and verbatim; that one is
//! reproduced here without alteration) and `evaluation_registry.tsv` (frozen
//! by the run-scheduler wave, `cli/src/run.rs`). The already-published
//! `truth_relation_projection.parquet` (A10) carries only a `signal_id ->
//! related_episode_ids` union (ruling E16) and a bare `(plateau_last_group_ordinal,
//! plateau_bar_ordinal, plateau_end_ts_ns)` per truth — it does **not** carry
//! the per-signal confirmation clock (`confirmation_group_ordinal`,
//! `causal_visible_ts_ns`/`causal_visible_bar_ordinal`), the truth's
//! `plateau_last_ns`, or the stream identity (`policy_name`/`reversal_bps`)
//! that `metrics::capture::classify` needs to reproduce CONV §8 rules 3-6
//! source-free. Rather than silently approximate (barred by the workspace's
//! own no-early-surrender / research-fidelity rules), this module freezes
//! FIVE new required leaves that carry exactly what `metrics`'s own public
//! types need, using those types' own field lists verbatim so a writer never
//! has to guess a shape independently:
//!
//! - `session_recall.tsv` (A1, unchanged): `year, ordinal, hits, truths`.
//! - `capture_truths.tsv`: one row per [`metrics::truth::TruthRow`] (every
//!   field, plus the session key), filtered to the gate authority
//!   `anchor_bps = 40` (amendment §A3).
//! - `capture_candidates.tsv`: one row per (stream, candidate) pair, the
//!   fields of [`metrics::capture::RelationEdge`] and
//!   [`metrics::capture::CandidateOutcome`] combined (they share
//!   `session`/`stream`/`candidate_id`) — the exact raw input
//!   `metrics::capture::classify` classifies. Per that module's own scope
//!   note, the keyed exact-match + fragment-overlap join (CONV §8 rules 1-2)
//!   is resolved upstream and carried here as `related_episode_ids`; this
//!   module reclassifies rules 3-6 (post-plateau/scorable/timely/dedup) plus
//!   every tally, exactly matching `metrics::capture`'s own documented input
//!   contract.
//! - `stream_summary.tsv`: the published, PER-STREAM claim this module
//!   checks its own reclassification against — [`metrics::capture::CaptureCounts`]
//!   verbatim (every field), plus the pooled truth-population's
//!   [`metrics::truth::pooled_ambiguity_count`], the pinned estimator's
//!   [`metrics::bank::EstimatorVerdict`], and an `on_frontier` flag
//!   ([`metrics::frontier::non_dominated`]). Exactly one row is flagged
//!   `is_gate = true`: the single registered stream whose per-session hit
//!   counts feed `session_recall.tsv` and whose `EstimatorVerdict` is
//!   cross-checked against a live re-invocation of the pinned Python
//!   estimator (A1) — every other row's `EstimatorVerdict` is CONSUMED as
//!   published input to the bank recomputation (A9: "LCB value is an INPUT
//!   ... metrics ... accepts its result"), never independently re-invoked
//!   (that would require a per-stream `session_recall`-shaped table this
//!   design does not register).
//! - `proposal_bank.tsv`: the published [`metrics::bank::ProposalBank`]
//!   (state, eligible count, and every member [`metrics::frontier::StreamPoint`]
//!   in ranked order), reconstructed and compared for exact `PartialEq`
//!   equality against [`metrics::bank::build_bank`]'s own output over the
//!   (reclassified, not merely republished) `stream_summary.tsv` rows.
//!
//! This is a scope decision, not settled design authority — flagged
//! prominently for architect reconciliation with whatever
//! `cli/src/metrics_cmd.rs` (the concurrent stage-1-metrics wiring wave,
//! never touched by this module) independently lands on. Coordination
//! happens *only* through `metrics`'s public types, per the task's own
//! constraint; this module's leaf contract is the concrete shape a writer
//! must match to be accepted.
//!
//! # Source-freedom
//!
//! [`StageGate::recompute`] opens only files under the `dir` it is given —
//! including the pinned estimator law file itself (ruling E21e; closes
//! Sol#7 P1 and Opus#P3-2): `stage1 run` publishes
//! `crate::receipt::ESTIMATOR_LAWS_LEAF_NAME` (`estimator_laws.py`) as a
//! declared, sha-pinned manifest leaf INSIDE `dir`, and this module's
//! [`StageGate::invoke_estimator`] resolves and sha-verifies ONLY that
//! in-directory copy against `crate::receipt::ESTIMATOR_LAWS_SHA256` before
//! every invocation — never a fixed external path (no archive hardcode, no
//! `/workspace`-wide search). A publication copied to a clean host with the
//! archive absent remains fully verifiable from `--dir` alone. This module
//! never opens the corpus or the preserved event publication.

use crate::error::{PublishError, Result};
use crate::hash::{hash_file_bytes, hex32, parse_hex32};
use crate::manifest::LeafRecord;
use crate::receipt::{ESTIMATOR_LAWS_LEAF_NAME, ESTIMATOR_LAWS_SHA256, RunReceipt};
use crate::verify::GateRecomputer;
use arrow_array::{Array, StringArray};
use metrics::bank::{
    BankState, EstimatorVerdict, ProposalBank, StreamLcb, build_bank, is_eligible,
};
use metrics::capture::{CandidateOutcome, CaptureCounts, RelationEdge, TruthOutcome, classify};
use metrics::frontier::{StreamPoint, compare_recall, non_dominated};
use metrics::regime::{Tercile, TrendRangeState};
use metrics::regime_slice::{
    BandResult, BandState, NetMoveResult, NetMoveState, RegimeBar, RegimePopulationCuts, SumState,
    WindowStat, build_regime_slices,
};
use metrics::session::{SessionId, SessionType, StreamId};
use metrics::session_recall::{SessionRecallRow, pooled_totals, session_recall_rows};
use metrics::truth::{Side, TruthRow, pooled_ambiguity_count};
use parquet::arrow::arrow_reader::ParquetRecordBatchReaderBuilder;
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use std::fmt::Write as _;
use std::fs::File;
use std::path::Path;

/// A1's frozen leaf name, reproduced verbatim.
pub const SESSION_RECALL_LEAF: &str = "session_recall.tsv";
/// This module's own leaf name.
pub const STREAM_SUMMARY_LEAF: &str = "stream_summary.tsv";
/// This module's own leaf name.
pub const PROPOSAL_BANK_LEAF: &str = "proposal_bank.tsv";
/// `cli/src/run.rs`'s already-frozen leaf name, read (not written) here for
/// the session roster.
pub const EVALUATION_REGISTRY_LEAF: &str = "evaluation_registry.tsv";
/// `cli/src/run.rs`'s already-frozen leaf name (ruling E18): the SOLE
/// source this module now reads for `TruthRow`/`RelationEdge`/
/// `CandidateOutcome` (module doc "Source-freedom" — recomputed from the
/// SAME `CANDIDATE`/`TRUTH` rows `cli::metrics_cmd` reads, never from a
/// second, separately-published copy).
pub const TRUTH_RELATION_PROJECTION_LEAF: &str = "truth_relation_projection.parquet";

/// A1, verbatim.
const SESSION_RECALL_HEADER: &str = "year\tordinal\thits\ttruths";
const STREAM_SUMMARY_HEADER: &str = "policy_name\treversal_bps\tis_gate\tregistration_order\t\
    confirmed_truths\tunique_timely_hits\tduplicate_timely_candidates\tconflicting_candidates\t\
    exact_not_post_plateau_candidates\tpost_plateau_not_scorable_candidates\tlate_candidates\t\
    unmatched_event_scorable_candidates\tunmatched_close_non_scorable_candidates\tdelay_0_hits\t\
    delay_1_hits\tdelay_2_hits\tmiss_no_exact_relation\tmiss_conflicting_relation_only\t\
    miss_exact_not_post_plateau\tmiss_post_plateau_not_scorable\tmiss_post_plateau_late\t\
    ambiguity_count\tlcb_canonical\tpasses_floor\ton_frontier";
const PROPOSAL_BANK_HEADER: &str = "state\teligible_count\tfrontier_count\tmember_rank\t\
    policy_name\treversal_bps\thits\ttruths_denominator\tburden\tregistration_order";

/// The gate authority anchor scale (amendment §A3). Ruling E18's
/// `TRUTH`/`CANDIDATE` rows carry no per-row `anchor_bps` column —
/// `cli::run` only ever populates [`TRUTH_RELATION_PROJECTION_LEAF`] from
/// `assignments.tsv`/`truth_coverage.tsv` rows already filtered to
/// `anchor_bps = 40` (`TRUTH_RELATION_ANCHOR_BPS` in `cli/main.rs`) — so
/// this constant is used only to POPULATE `TruthRow::anchor_bps`, never to
/// filter an incoming column.
const GATE_ANCHOR_BPS: u16 = 40;

/// The frozen full-development-corpus truth denominator
/// (`registered_conventions_extract_v1.md` §8): asserted only when this
/// run's `session_count` (from the receipt) is the full 1,003-session
/// registry — a smaller rehearsal/benchmark run is never held to this exact
/// constant.
const FULL_CORPUS_SESSION_COUNT: u64 = 1_003;
const FULL_CORPUS_TRUTH_DENOMINATOR: u64 = 8_914;

/// The gate-verifier's own driver script (module doc "Source-freedom"): NOT
/// the pinned law file, never sha-checked itself (it is this crate's own
/// compiled-in tooling, embedded at compile time like every other
/// compiled-in pin in `crate::receipt`) — it only dynamically loads the
/// sha-verified `estimator_laws.py` by path and calls its frozen function.
const ESTIMATOR_DRIVER_SCRIPT: &str = include_str!("gate_estimator_driver.py");

/// Every leaf name this module requires under `--dir`, for a caller (e.g.
/// `cli/src/verify_cmd.rs`) building the full required-leaf-set passed to
/// [`crate::verify::verify_publication`]. [`TRUTH_RELATION_PROJECTION_LEAF`]
/// is NOT listed here: it is `cli::run`'s own leaf, already required by
/// that caller's own leaf inventory (`cli/src/run.rs`'s
/// `FAMILY_LEAF_STEMS`/`regimes`/`event_index`/`truth_relation_projection`
/// loop) — this module only reads it, never re-registers it.
#[must_use]
pub fn required_leaf_names() -> [&'static str; 3] {
    [SESSION_RECALL_LEAF, STREAM_SUMMARY_LEAF, PROPOSAL_BANK_LEAF]
}

fn gate_error(detail: impl Into<String>) -> PublishError {
    PublishError::GateMismatch {
        detail: detail.into(),
    }
}

/// Ruling E22(f): "Verifier error Display carries typed mismatch categories
/// only — never embedded scientific values (exposure-incident hygiene)."
/// Every published-vs-recomputed content check in this module reports its
/// failure through [`gate_content_mismatch`] rather than interpolating the
/// compared values (hit/duplicate/miss counts, recall/burden/LCB numbers,
/// `CaptureCounts`/`StreamPoint`/`EstimatorVerdict`/`ProposalBank` values)
/// directly into the error text — `stage1 verify-stage1` prints
/// [`PublishError`]'s `Display` straight to stdout (`cli::verify_cmd`), so a
/// scientific value embedded here would leak a real-day result during the
/// result-blindness embargo. [`Mismatch`] is the one (today) fixed category
/// every content check falls under; this is a real Rust type (not
/// free-form prose) specifically so a call site cannot smuggle a value in
/// where a category belongs.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Mismatch {
    /// A published leaf's per-row content disagreed with this module's own
    /// independent, source-free recomputation over the identical input row.
    Content,
}

impl Mismatch {
    const fn tag(self) -> &'static str {
        match self {
            Self::Content => "CONTENT_MISMATCH",
        }
    }
}

/// Builds a [`PublishError::GateMismatch`] naming WHAT kind of thing
/// disagreed ([`Mismatch`]) and WHERE (`leaf`, `coordinate`, `fields`) —
/// never the scientific values themselves (module doc / E22(f)).
/// `coordinate` must identify the disagreeing ROW ONLY (a stream/session
/// identity, a leaf-relative description, or a line number) and `fields`
/// must name the disagreeing COLUMN(S) ONLY (by name) — neither parameter
/// may itself carry a compared value.
fn gate_content_mismatch(
    leaf: &'static str,
    coordinate: impl std::fmt::Display,
    fields: &str,
) -> PublishError {
    gate_error(format!(
        "{} [{leaf}] {coordinate}: field(s) `{fields}` disagree between the published leaf and \
         this module's own source-free recomputation",
        Mismatch::Content.tag()
    ))
}

fn checked_add(a: u64, b: u64) -> Result<u64> {
    a.checked_add(b).ok_or(PublishError::ArithmeticOverflow)
}

/// Sums every field of `delta` into `acc` (all 17 [`CaptureCounts`] fields
/// are plain additive tallies — pooling a stream's per-session
/// [`CaptureCounts`] into one run-wide total is exactly field-wise addition).
fn add_counts(acc: CaptureCounts, delta: &CaptureCounts) -> Result<CaptureCounts> {
    Ok(CaptureCounts {
        confirmed_truths: checked_add(acc.confirmed_truths, delta.confirmed_truths)?,
        unique_timely_hits: checked_add(acc.unique_timely_hits, delta.unique_timely_hits)?,
        duplicate_timely_candidates: checked_add(
            acc.duplicate_timely_candidates,
            delta.duplicate_timely_candidates,
        )?,
        conflicting_candidates: checked_add(
            acc.conflicting_candidates,
            delta.conflicting_candidates,
        )?,
        exact_not_post_plateau_candidates: checked_add(
            acc.exact_not_post_plateau_candidates,
            delta.exact_not_post_plateau_candidates,
        )?,
        post_plateau_not_scorable_candidates: checked_add(
            acc.post_plateau_not_scorable_candidates,
            delta.post_plateau_not_scorable_candidates,
        )?,
        late_candidates: checked_add(acc.late_candidates, delta.late_candidates)?,
        unmatched_event_scorable_candidates: checked_add(
            acc.unmatched_event_scorable_candidates,
            delta.unmatched_event_scorable_candidates,
        )?,
        unmatched_close_non_scorable_candidates: checked_add(
            acc.unmatched_close_non_scorable_candidates,
            delta.unmatched_close_non_scorable_candidates,
        )?,
        delay_0_hits: checked_add(acc.delay_0_hits, delta.delay_0_hits)?,
        delay_1_hits: checked_add(acc.delay_1_hits, delta.delay_1_hits)?,
        delay_2_hits: checked_add(acc.delay_2_hits, delta.delay_2_hits)?,
        miss_no_exact_relation: checked_add(
            acc.miss_no_exact_relation,
            delta.miss_no_exact_relation,
        )?,
        miss_conflicting_relation_only: checked_add(
            acc.miss_conflicting_relation_only,
            delta.miss_conflicting_relation_only,
        )?,
        miss_exact_not_post_plateau: checked_add(
            acc.miss_exact_not_post_plateau,
            delta.miss_exact_not_post_plateau,
        )?,
        miss_post_plateau_not_scorable: checked_add(
            acc.miss_post_plateau_not_scorable,
            delta.miss_post_plateau_not_scorable,
        )?,
        miss_post_plateau_late: checked_add(
            acc.miss_post_plateau_late,
            delta.miss_post_plateau_late,
        )?,
    })
}

// ---------------------------------------------------------------------
// Tiny shared tab-column cursor (mirrors `pubread::rows::Cols`; duplicated
// locally per this workspace's own convention -- see `cli/main.rs`'s
// `hex32`/`parse_days` doc comments -- rather than depending on `pubread`
// for a dozen lines).
// ---------------------------------------------------------------------

struct Row<'a> {
    parts: std::str::Split<'a, char>,
    leaf: &'static str,
    line_number: usize,
}

impl<'a> Row<'a> {
    fn new(line: &'a str, leaf: &'static str, line_number: usize) -> Self {
        Self {
            parts: line.split('\t'),
            leaf,
            line_number,
        }
    }

    fn fail(&self, column: &'static str, detail: impl std::fmt::Display) -> PublishError {
        gate_error(format!(
            "{}:{}: column `{column}`: {detail}",
            self.leaf, self.line_number
        ))
    }

    fn raw(&mut self, column: &'static str) -> Result<&'a str> {
        self.parts
            .next()
            .ok_or_else(|| self.fail(column, "missing"))
    }

    fn string(&mut self, column: &'static str) -> Result<String> {
        self.raw(column).map(str::to_owned)
    }

    fn u16(&mut self, column: &'static str) -> Result<u16> {
        let raw = self.raw(column)?;
        raw.parse()
            .map_err(|_| self.fail(column, format!("not a u16: `{raw}`")))
    }

    fn u32(&mut self, column: &'static str) -> Result<u32> {
        let raw = self.raw(column)?;
        raw.parse()
            .map_err(|_| self.fail(column, format!("not a u32: `{raw}`")))
    }

    fn u64(&mut self, column: &'static str) -> Result<u64> {
        let raw = self.raw(column)?;
        raw.parse()
            .map_err(|_| self.fail(column, format!("not a u64: `{raw}`")))
    }

    fn usize(&mut self, column: &'static str) -> Result<usize> {
        let raw = self.raw(column)?;
        raw.parse()
            .map_err(|_| self.fail(column, format!("not a usize: `{raw}`")))
    }

    fn opt_usize(&mut self, column: &'static str) -> Result<Option<usize>> {
        let raw = self.raw(column)?;
        if raw == "NA" {
            return Ok(None);
        }
        raw.parse()
            .map(Some)
            .map_err(|_| self.fail(column, format!("not a usize: `{raw}`")))
    }

    fn opt_u64(&mut self, column: &'static str) -> Result<Option<u64>> {
        let raw = self.raw(column)?;
        if raw == "NA" {
            return Ok(None);
        }
        raw.parse()
            .map(Some)
            .map_err(|_| self.fail(column, format!("not a u64: `{raw}`")))
    }

    /// Reads a `(policy_name, reversal_bps)` column pair as one
    /// [`StreamId`] (ruling E22(a)/(b)'s fail-closed `StreamId::from_wire`)
    /// — every leaf's stream identity columns go through this, never a bare
    /// `.string("policy_name")` + `.u16("reversal_bps")` pair, so a `UNION`
    /// row's `reversal_bps = "NA"` is never mistaken for a malformed number.
    fn stream_id(
        &mut self,
        policy_column: &'static str,
        reversal_column: &'static str,
    ) -> Result<StreamId> {
        let policy_name = self.raw(policy_column)?.to_owned();
        let reversal_bps = self.raw(reversal_column)?.to_owned();
        StreamId::from_wire(&policy_name, &reversal_bps)
            .map_err(|error| self.fail(reversal_column, error))
    }

    fn bool(&mut self, column: &'static str) -> Result<bool> {
        match self.raw(column)? {
            "true" => Ok(true),
            "false" => Ok(false),
            other => Err(self.fail(column, format!("not a bool: `{other}`"))),
        }
    }

    fn finish(mut self) -> Result<()> {
        if self.parts.next().is_some() {
            return Err(gate_error(format!(
                "{}:{}: extra trailing column(s)",
                self.leaf, self.line_number
            )));
        }
        Ok(())
    }
}

/// Reads `dir/leaf_name`, checks its header, and returns every non-empty
/// data line paired with its 1-based line number (header is line 1).
fn read_leaf_lines(
    dir: &Path,
    leaf_name: &'static str,
    expected_header: &'static str,
) -> Result<Vec<(usize, String)>> {
    let path = dir.join(leaf_name);
    let text = std::fs::read_to_string(&path).map_err(|source| PublishError::Io {
        path: path.clone(),
        source,
    })?;
    let mut lines = text.lines();
    let header = lines
        .next()
        .ok_or_else(|| gate_error(format!("{leaf_name}: empty file")))?;
    if header != expected_header {
        return Err(gate_error(format!(
            "{leaf_name}: unexpected header `{header}`, expected `{expected_header}`"
        )));
    }
    Ok(lines
        .enumerate()
        .filter(|(_, line)| !line.is_empty())
        .map(|(offset, line)| (offset + 2, line.to_owned()))
        .collect())
}

fn write_leaf_text(dir: &Path, leaf_name: &'static str, text: &str) -> Result<LeafRecord> {
    let path = dir.join(leaf_name);
    crate::atomic::write_atomic(&path, text.as_bytes())?;
    let (bytes, sha256) = hash_file_bytes(&path)?;
    let rows = text.lines().count().saturating_sub(1) as u64;
    Ok(LeafRecord {
        name: leaf_name.to_owned(),
        rows,
        bytes,
        sha256,
    })
}

// ---------------------------------------------------------------------
// session_recall.tsv (A1, unchanged schema)
// ---------------------------------------------------------------------

/// Writes `session_recall.tsv` (A1's exact schema) and returns its manifest
/// [`LeafRecord`].
///
/// # Errors
///
/// Returns an error if the file cannot be written.
pub fn write_session_recall_leaf(dir: &Path, rows: &[SessionRecallRow]) -> Result<LeafRecord> {
    let mut text = String::from(SESSION_RECALL_HEADER);
    text.push('\n');
    for row in rows {
        writeln!(
            text,
            "{}\t{}\t{}\t{}",
            row.year, row.ordinal, row.hits, row.truths
        )
        .expect("writing to a String cannot fail");
    }
    write_leaf_text(dir, SESSION_RECALL_LEAF, &text)
}

/// Reads `session_recall.tsv` (A1's exact schema).
///
/// # Errors
///
/// Returns an error if the file is missing, malformed, or a row does not
/// parse as `year\tordinal\thits\ttruths`.
pub fn read_session_recall_leaf(dir: &Path) -> Result<Vec<SessionRecallRow>> {
    let lines = read_leaf_lines(dir, SESSION_RECALL_LEAF, SESSION_RECALL_HEADER)?;
    lines
        .into_iter()
        .map(|(line_number, line)| {
            let mut row = Row::new(&line, SESSION_RECALL_LEAF, line_number);
            let year = row.u16("year")?;
            let ordinal = row.u32("ordinal")?;
            let hits = row.u64("hits")?;
            let truths = row.u64("truths")?;
            row.finish()?;
            Ok(SessionRecallRow {
                year,
                ordinal,
                hits,
                truths,
            })
        })
        .collect()
}

// ---------------------------------------------------------------------
// truth_relation_projection.parquet (ruling E18: TRUTH + CANDIDATE rows,
// `cli::run`'s own leaf, read here — never written)
// ---------------------------------------------------------------------

/// Reads an all-`Utf8`-column parquet leaf (`cli::run`'s leaf-schema
/// convention) into its column names plus every row as owned strings. Local
/// duplicate of `cli::metrics_cmd`'s own identical helper (this workspace's
/// established convention: small local duplication across sibling
/// leaf-consuming modules rather than a shared-but-thin abstraction).
fn read_utf8_parquet(path: &Path) -> Result<(Vec<String>, Vec<Vec<String>>)> {
    let file = File::open(path).map_err(|source| PublishError::Io {
        path: path.to_path_buf(),
        source,
    })?;
    let builder = ParquetRecordBatchReaderBuilder::try_new(file).map_err(|error| {
        gate_error(format!(
            "reading parquet schema for {}: {error}",
            path.display()
        ))
    })?;
    let columns: Vec<String> = builder
        .schema()
        .fields()
        .iter()
        .map(|field| field.name().clone())
        .collect();
    let reader = builder.build().map_err(|error| {
        gate_error(format!(
            "building parquet reader for {}: {error}",
            path.display()
        ))
    })?;

    let mut rows = Vec::new();
    for batch in reader {
        let batch = batch.map_err(|error| {
            gate_error(format!(
                "reading a row group of {}: {error}",
                path.display()
            ))
        })?;
        let string_columns: Vec<&StringArray> = (0..batch.num_columns())
            .map(|i| {
                batch
                    .column(i)
                    .as_any()
                    .downcast_ref::<StringArray>()
                    .ok_or_else(|| {
                        gate_error(format!(
                            "{}: column {i} is not Utf8 (violates the all-Utf8 leaf convention)",
                            path.display()
                        ))
                    })
            })
            .collect::<Result<_>>()?;
        for r in 0..batch.num_rows() {
            rows.push(
                string_columns
                    .iter()
                    .map(|column| column.value(r).to_owned())
                    .collect(),
            );
        }
    }
    Ok((columns, rows))
}

fn column_index(columns: &[String]) -> HashMap<&str, usize> {
    columns
        .iter()
        .enumerate()
        .map(|(i, c)| (c.as_str(), i))
        .collect()
}

fn col_value<'a>(row: &'a [String], col: &HashMap<&str, usize>, name: &str) -> Result<&'a str> {
    let idx = *col.get(name).ok_or_else(|| {
        gate_error(format!(
            "expected column `{name}` is absent from this leaf's schema"
        ))
    })?;
    row.get(idx)
        .map(String::as_str)
        .ok_or_else(|| gate_error(format!("row has no value at column `{name}` (index {idx})")))
}

fn parse_field<T: std::str::FromStr>(
    row: &[String],
    col: &HashMap<&str, usize>,
    name: &str,
) -> Result<T>
where
    T::Err: std::fmt::Display,
{
    let raw = col_value(row, col, name)?;
    raw.parse::<T>().map_err(|error| {
        gate_error(format!(
            "column `{name}` value `{raw}` failed to parse: {error}"
        ))
    })
}

fn parse_hex_list_col(
    row: &[String],
    col: &HashMap<&str, usize>,
    name: &str,
) -> Result<Vec<[u8; 32]>> {
    let raw = col_value(row, col, name)?;
    if raw == "NA" || raw.is_empty() {
        return Ok(Vec::new());
    }
    raw.split(',')
        .map(|piece| {
            parse_hex32(piece).ok_or_else(|| {
                gate_error(format!(
                    "column `{name}`: not a 64-hex-char digest: `{piece}`"
                ))
            })
        })
        .collect()
}

fn parse_opt_u64_col(
    row: &[String],
    col: &HashMap<&str, usize>,
    name: &str,
) -> Result<Option<u64>> {
    let raw = col_value(row, col, name)?;
    if raw == "NA" {
        return Ok(None);
    }
    raw.parse::<u64>().map(Some).map_err(|error| {
        gate_error(format!(
            "column `{name}` value `{raw}` is not a u64: {error}"
        ))
    })
}

fn parse_bool_col(row: &[String], col: &HashMap<&str, usize>, name: &str) -> Result<bool> {
    match col_value(row, col, name)? {
        "true" => Ok(true),
        "false" => Ok(false),
        other => Err(gate_error(format!(
            "column `{name}`: unexpected boolean wire value `{other}`"
        ))),
    }
}

/// EVENTS.4 P0 memory-safety fix ("stream one session's row group at a
/// time, never the whole leaf" — the crash this closes: a real 1,003
/// -session publication's `truth_relation_projection.parquet` decodes to
/// ~41.9M rows, and materializing every row as owned `String`s at once was
/// observed to inflate a ~4.92 GiB decoded-content file to a ~51.4 GiB RSS
/// that got `SIGKILLed` with zero progress output). The leaf's own
/// `<leaf_stem>_session_index.tsv` companion (`publish::parquet_leaf::
/// LeafWriter`'s own convention: `ordinal, day, rows`, one entry per
/// `write_session` call, in strictly increasing ordinal order) records
/// exactly which row group (if any — a zero-row session opens none) each
/// session landed in; combined with `evaluation_registry.tsv`'s own dense
/// `0..N` roster order, this is enough to visit every session's row group
/// exactly once, in roster order, without ever touching a second session's
/// data at the same time.
///
/// Reads [`TRUTH_RELATION_PROJECTION_LEAF`]'s `TRUTH` rows into
/// [`TruthRow`]s. `side`/`price_u6`/`continuity_ordinal`/
/// `coincident_ambiguities` are inert sentinels on every `TruthRow` (mirrors
/// `cli::metrics_cmd`'s own documented Escalation 4: none of these are
/// consulted by [`classify`]).
///
/// # Errors
///
/// Returns an error if the leaf is missing/malformed, its session-index
/// companion disagrees with `evaluation_registry.tsv`'s own roster order, a
/// row group's approximate decoded size exceeds
/// [`MAX_SESSION_ROW_GROUP_DECODED_BYTES`], or any column fails to parse as
/// its registered type.
#[allow(
    clippy::too_many_lines,
    reason = "one linear leaf-to-typed-rows pass, mirrors the function it replaces"
)]
fn read_truth_relation_projection(
    dir: &Path,
    eval_rows: &[EvalRegistryRow],
) -> Result<Vec<TruthRow>> {
    let path = dir.join(TRUTH_RELATION_PROJECTION_LEAF);
    let columns = read_leaf_columns(&path)?;
    let col = column_index(&columns);
    let plan = leaf_row_group_plan(dir, "truth_relation_projection", eval_rows)?;

    let mut truths = Vec::new();
    let telemetry = SessionTelemetry::new(
        "verify-stage1: truth_relation_projection (truths)",
        session_count_u32(eval_rows.len())?,
    );
    for (position, (eval_row, plan_entry)) in eval_rows.iter().zip(&plan).enumerate() {
        let ordinal = session_count_u32(position)?;
        telemetry.begin(ordinal, &eval_row.day);
        let rows = read_leaf_session_rows(&path, *plan_entry)?;
        for row in &rows {
            let row_kind = col_value(row, &col, "row_kind")?;
            if row_kind == "TRUTH" {
                truths.push(parse_truth_row_at(row, &col, eval_row.session)?);
            } else if row_kind != "SIGNAL_RELATION" && row_kind != "CANDIDATE" {
                return Err(gate_error(format!(
                    "unexpected row_kind `{row_kind}` in {}",
                    path.display()
                )));
            }
        }
        telemetry.done(ordinal, &eval_row.day);
    }
    Ok(truths)
}

/// Parses one `TRUTH` row (see [`read_truth_relation_projection`]'s doc).
fn parse_truth_row_at(
    row: &[String],
    col: &HashMap<&str, usize>,
    session: SessionId,
) -> Result<TruthRow> {
    let episode_id_raw = col_value(row, col, "episode_id")?;
    let episode_id = parse_hex32(episode_id_raw).ok_or_else(|| {
        gate_error(format!(
            "TRUTH row episode_id `{episode_id_raw}` is not a 64-hex digest"
        ))
    })?;
    let plateau_last_group_ordinal: u64 = parse_field(row, col, "plateau_last_group_ordinal")?;
    let plateau_bar_ordinal: i64 = parse_field(row, col, "plateau_bar_ordinal")?;
    let plateau_last_ns: i64 = parse_field(row, col, "plateau_end_ts_ns")?;
    Ok(TruthRow {
        episode_id,
        session,
        anchor_bps: GATE_ANCHOR_BPS,
        continuity_ordinal: 0,
        side: Side::Low,
        price_u6: 0,
        plateau_last_group_ordinal,
        plateau_bar_ordinal,
        plateau_last_ns,
        coincident_ambiguities: 0,
    })
}

/// Parses one `CANDIDATE` row's stream identity only (the cheap discovery
/// pass, [`discover_stream_universe`]) — never the row's other, much
/// larger, fields.
fn parse_candidate_stream_id(row: &[String], col: &HashMap<&str, usize>) -> Result<StreamId> {
    let stream_policy_name = col_value(row, col, "stream_policy_name")?;
    let stream_reversal_bps = col_value(row, col, "stream_reversal_bps")?;
    StreamId::from_wire(stream_policy_name, stream_reversal_bps)
        .map_err(|error| gate_error(format!("CANDIDATE row: {error}")))
}

/// Parses one `CANDIDATE` row in full into its `(RelationEdge,
/// CandidateOutcome)` pair (the classification pass,
/// [`reclassify_all_streams`]), cross-checking the published
/// `event_scorable` fact against the independent CONV §4 recomputation.
fn parse_candidate_full(
    row: &[String],
    col: &HashMap<&str, usize>,
    day: &str,
    session: SessionId,
) -> Result<(RelationEdge, CandidateOutcome)> {
    let stream = parse_candidate_stream_id(row, col)?;
    let candidate_id_raw = col_value(row, col, "candidate_id")?;
    let candidate_id = parse_hex32(candidate_id_raw).ok_or_else(|| {
        gate_error(format!(
            "CANDIDATE row candidate_id `{candidate_id_raw}` is not a 64-hex digest"
        ))
    })?;
    let member_signal_ids = parse_hex_list_col(row, col, "member_signal_ids")?;
    let related_episode_ids = parse_hex_list_col(row, col, "related_episode_ids")?;
    let registration_ordinal: u64 = parse_field(row, col, "registration_ordinal")?;
    let confirmation_group_ordinal: u64 = parse_field(row, col, "confirmation_group_ordinal")?;
    let visible_ts_ns: i64 = parse_field(row, col, "visible_ts_ns")?;
    let visible_bar_ordinal = parse_opt_u64_col(row, col, "visible_bar_ordinal")?;
    let session_end_ns: i64 = parse_field(row, col, "session_end_ns")?;
    let published_event_scorable = parse_bool_col(row, col, "event_scorable")?;

    let edge = RelationEdge {
        session,
        stream: stream.clone(),
        candidate_id,
        registration_ordinal,
        member_signal_ids,
        related_episode_ids,
    };
    let outcome = CandidateOutcome {
        session,
        stream,
        candidate_id,
        confirmation_group_ordinal,
        visible_ts_ns,
        visible_bar_ordinal,
        session_end_ns,
    };
    if outcome.event_scorable() != published_event_scorable {
        return Err(gate_error(format!(
            "{TRUTH_RELATION_PROJECTION_LEAF}: candidate {} (day {day}) published \
             event_scorable={} disagrees with the recomputed CONV §4 predicate ({})",
            hex32(&candidate_id),
            published_event_scorable,
            outcome.event_scorable()
        )));
    }
    Ok((edge, outcome))
}

/// Fallible `usize -> u32` used for session ordinals/counts throughout this
/// module's streaming passes (the roster is always far below `u32::MAX`;
/// this exists only so every call site fails closed via
/// [`PublishError::ArithmeticOverflow`] instead of panicking).
fn session_count_u32(value: usize) -> Result<u32> {
    u32::try_from(value).map_err(|_| PublishError::ArithmeticOverflow)
}

/// Reads `path`'s parquet schema (column names) only — no row group is
/// opened or decoded. Cheap, footer-only I/O; called once per streaming
/// pass rather than once per session.
fn read_leaf_columns(path: &Path) -> Result<Vec<String>> {
    let file = File::open(path).map_err(|source| PublishError::Io {
        path: path.to_path_buf(),
        source,
    })?;
    let builder = ParquetRecordBatchReaderBuilder::try_new(file).map_err(|error| {
        gate_error(format!(
            "reading parquet schema for {}: {error}",
            path.display()
        ))
    })?;
    Ok(builder
        .schema()
        .fields()
        .iter()
        .map(|field| field.name().clone())
        .collect())
}

/// Reads one session's rows from `path` per `plan_entry` ([`None`] — this
/// leaf recorded zero rows for the session, per [`leaf_row_group_plan`] —
/// yields an empty `Vec` without touching the file at all).
fn read_leaf_session_rows(path: &Path, plan_entry: Option<usize>) -> Result<Vec<Vec<String>>> {
    match plan_entry {
        Some(row_group) => Ok(read_utf8_parquet_row_group(path, row_group)?.1),
        None => Ok(Vec::new()),
    }
}

/// Reads `<leaf_stem>_session_index.tsv` and verifies its rows correspond,
/// position for position, to `eval_rows`' own dense run-ordinal order
/// (`evaluation_registry.tsv`'s `ordinal`/`day` columns, already validated
/// dense and unique by [`read_evaluation_registry`]) — two independently
/// written files are never trusted to align on faith. Returns, per roster
/// position, the row group this leaf actually wrote for that session
/// (`None` for a session this leaf recorded zero rows for —
/// `publish::parquet_leaf::LeafWriter` never opens a row group for an empty
/// `write_session` call, Sol#12).
///
/// # Errors
///
/// Returns [`PublishError::SessionLeafMisaligned`] if the two session
/// sequences disagree in length or at any position.
fn leaf_row_group_plan(
    dir: &Path,
    leaf_stem: &str,
    eval_rows: &[EvalRegistryRow],
) -> Result<Vec<Option<usize>>> {
    let index = read_session_index(dir, leaf_stem)?;
    if index.len() != eval_rows.len() {
        return Err(PublishError::SessionLeafMisaligned {
            leaf_stem: leaf_stem.to_owned(),
            detail: format!(
                "{leaf_stem}_session_index.tsv has {} session rows, {EVALUATION_REGISTRY_LEAF} \
                 has {}",
                index.len(),
                eval_rows.len()
            ),
        });
    }
    let mut plan = Vec::with_capacity(index.len());
    let mut next_row_group = 0usize;
    for (position, (entry, eval_row)) in index.iter().zip(eval_rows).enumerate() {
        let expected_ordinal = session_count_u32(position)?;
        if entry.ordinal != expected_ordinal || entry.day != eval_row.day {
            return Err(PublishError::SessionLeafMisaligned {
                leaf_stem: leaf_stem.to_owned(),
                detail: format!(
                    "position {position}: session index has (ordinal={}, day={}), \
                     {EVALUATION_REGISTRY_LEAF} has (ordinal={expected_ordinal}, day={})",
                    entry.ordinal, entry.day, eval_row.day
                ),
            });
        }
        if entry.rows > 0 {
            plan.push(Some(next_row_group));
            next_row_group += 1;
        } else {
            plan.push(None);
        }
    }
    Ok(plan)
}

/// Per-session stderr progress for this module's own streaming
/// consumption passes (`AGENTS.md` compute law: "every long job emits
/// per-session progress (done/total, rate, ETA) ... no silent multi-hour
/// phase, ever" — applied to a leaf CONSUMER exactly as
/// `labels::scheduler::Telemetry` already applies it to `stage1 run`'s own
/// writer scheduler). This module's own passes are sequential/
/// single-threaded, so a plain counter suffices — no atomics needed.
struct SessionTelemetry<'a> {
    label: &'a str,
    total: u32,
    completed: std::cell::Cell<u32>,
    start: std::time::Instant,
}

impl<'a> SessionTelemetry<'a> {
    fn new(label: &'a str, total: u32) -> Self {
        eprintln!("{label}: starting, total={total} session(s)");
        Self {
            label,
            total,
            completed: std::cell::Cell::new(0),
            start: std::time::Instant::now(),
        }
    }

    fn begin(&self, ordinal: u32, day: &str) {
        eprintln!(
            "{}: begin ordinal={ordinal} day={day} total={}",
            self.label, self.total
        );
    }

    fn done(&self, ordinal: u32, day: &str) {
        let completed = self.completed.get() + 1;
        self.completed.set(completed);
        let total = self.total;
        let elapsed_secs = self.start.elapsed().as_secs_f64().max(1e-9);
        let rate = f64::from(completed) / elapsed_secs;
        let remaining = total.saturating_sub(completed);
        let eta_secs = if rate > 0.0 {
            f64::from(remaining) / rate
        } else {
            f64::INFINITY
        };
        eprintln!(
            "{}: done ordinal={ordinal} day={day} done={completed}/{total} rate={rate:.3}/s \
             eta={eta_secs:.1}s",
            self.label
        );
    }
}

/// EVENTS.4 P0 memory-safety fix, pass 1 of 2 (see
/// [`read_truth_relation_projection`]'s doc for the shared streaming
/// rationale): the cheap discovery pass over
/// [`TRUTH_RELATION_PROJECTION_LEAF`] that [`reclassify_all_streams`] (pass
/// 2) needs before it can classify anything — the candidate-stream universe
/// in first-seen (registration) order across the whole leaf (`CANDIDATE`
/// rows' `stream_policy_name`/`stream_reversal_bps` pair only, never the
/// rest of a `CANDIDATE` row's larger fields in this pass). Streams one
/// session's row group at a time exactly like
/// [`read_truth_relation_projection`], and is run right alongside it so the
/// leaf is opened/scanned once per pass, not once per extracted quantity.
///
/// # Errors
///
/// Returns an error under the same conditions as
/// [`read_truth_relation_projection`].
fn discover_stream_universe(dir: &Path, eval_rows: &[EvalRegistryRow]) -> Result<Vec<StreamId>> {
    let path = dir.join(TRUTH_RELATION_PROJECTION_LEAF);
    let columns = read_leaf_columns(&path)?;
    let col = column_index(&columns);
    let plan = leaf_row_group_plan(dir, "truth_relation_projection", eval_rows)?;

    let mut seen: HashSet<StreamId> = HashSet::new();
    let mut discovered: Vec<StreamId> = Vec::new();
    let telemetry = SessionTelemetry::new(
        "verify-stage1: truth_relation_projection (streams)",
        session_count_u32(eval_rows.len())?,
    );
    for (position, (eval_row, plan_entry)) in eval_rows.iter().zip(&plan).enumerate() {
        let ordinal = session_count_u32(position)?;
        telemetry.begin(ordinal, &eval_row.day);
        let rows = read_leaf_session_rows(&path, *plan_entry)?;
        for row in &rows {
            if col_value(row, &col, "row_kind")? == "CANDIDATE" {
                let stream = parse_candidate_stream_id(row, &col)?;
                if seen.insert(stream.clone()) {
                    discovered.push(stream);
                }
            }
        }
        telemetry.done(ordinal, &eval_row.day);
    }
    Ok(discovered)
}

// ---------------------------------------------------------------------
// stream_summary.tsv (published claim: CaptureCounts + ambiguity + verdict
// + frontier flag, per stream)
// ---------------------------------------------------------------------

/// One published `stream_summary.tsv` row (module doc "scope").
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StreamSummaryRow {
    pub stream: StreamId,
    /// Exactly one row across the whole leaf must set this `true` (the
    /// registered EVENTS-gate stream; module doc "scope").
    pub is_gate: bool,
    pub registration_order: u64,
    pub counts: CaptureCounts,
    /// The pooled truth population's [`pooled_ambiguity_count`] — a
    /// property of the truth population, not of this stream, so every row
    /// carries the same value (mirrors `evaluation_registry.tsv`'s repeated
    /// per-row constants).
    pub ambiguity_count: u64,
    pub verdict: EstimatorVerdict,
    pub on_frontier: bool,
}

/// Writes `stream_summary.tsv`. Returns its manifest [`LeafRecord`].
///
/// # Errors
///
/// Returns an error if the file cannot be written.
pub fn write_stream_summary_leaf(dir: &Path, rows: &[StreamSummaryRow]) -> Result<LeafRecord> {
    let mut text = String::from(STREAM_SUMMARY_HEADER);
    text.push('\n');
    for row in rows {
        let c = &row.counts;
        writeln!(
            text,
            "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}",
            row.stream.policy_name(),
            row.stream.reversal_bps_wire(),
            row.is_gate,
            row.registration_order,
            c.confirmed_truths,
            c.unique_timely_hits,
            c.duplicate_timely_candidates,
            c.conflicting_candidates,
            c.exact_not_post_plateau_candidates,
            c.post_plateau_not_scorable_candidates,
            c.late_candidates,
            c.unmatched_event_scorable_candidates,
            c.unmatched_close_non_scorable_candidates,
            c.delay_0_hits,
            c.delay_1_hits,
            c.delay_2_hits,
            c.miss_no_exact_relation,
            c.miss_conflicting_relation_only,
            c.miss_exact_not_post_plateau,
            c.miss_post_plateau_not_scorable,
            c.miss_post_plateau_late,
            row.ambiguity_count,
            row.verdict.lcb_canonical,
            row.verdict.passes_floor,
            row.on_frontier,
        )
        .expect("writing to a String cannot fail");
    }
    write_leaf_text(dir, STREAM_SUMMARY_LEAF, &text)
}

/// Reads `stream_summary.tsv`.
///
/// # Errors
///
/// Returns an error if the file is missing or malformed.
pub fn read_stream_summary_leaf(dir: &Path) -> Result<Vec<StreamSummaryRow>> {
    let lines = read_leaf_lines(dir, STREAM_SUMMARY_LEAF, STREAM_SUMMARY_HEADER)?;
    lines
        .into_iter()
        .map(|(line_number, line)| {
            let mut row = Row::new(&line, STREAM_SUMMARY_LEAF, line_number);
            let stream = row.stream_id("policy_name", "reversal_bps")?;
            let is_gate = row.bool("is_gate")?;
            let registration_order = row.u64("registration_order")?;
            let confirmed_truths = row.u64("confirmed_truths")?;
            let unique_timely_hits = row.u64("unique_timely_hits")?;
            let duplicate_timely_candidates = row.u64("duplicate_timely_candidates")?;
            let conflicting_candidates = row.u64("conflicting_candidates")?;
            let exact_not_post_plateau_candidates = row.u64("exact_not_post_plateau_candidates")?;
            let post_plateau_not_scorable_candidates =
                row.u64("post_plateau_not_scorable_candidates")?;
            let late_candidates = row.u64("late_candidates")?;
            let unmatched_event_scorable_candidates =
                row.u64("unmatched_event_scorable_candidates")?;
            let unmatched_close_non_scorable_candidates =
                row.u64("unmatched_close_non_scorable_candidates")?;
            let delay_0_hits = row.u64("delay_0_hits")?;
            let delay_1_hits = row.u64("delay_1_hits")?;
            let delay_2_hits = row.u64("delay_2_hits")?;
            let miss_no_exact_relation = row.u64("miss_no_exact_relation")?;
            let miss_conflicting_relation_only = row.u64("miss_conflicting_relation_only")?;
            let miss_exact_not_post_plateau = row.u64("miss_exact_not_post_plateau")?;
            let miss_post_plateau_not_scorable = row.u64("miss_post_plateau_not_scorable")?;
            let miss_post_plateau_late = row.u64("miss_post_plateau_late")?;
            let ambiguity_count = row.u64("ambiguity_count")?;
            let lcb_canonical = row.string("lcb_canonical")?;
            let passes_floor = row.bool("passes_floor")?;
            let on_frontier = row.bool("on_frontier")?;
            row.finish()?;
            Ok(StreamSummaryRow {
                stream,
                is_gate,
                registration_order,
                counts: CaptureCounts {
                    confirmed_truths,
                    unique_timely_hits,
                    duplicate_timely_candidates,
                    conflicting_candidates,
                    exact_not_post_plateau_candidates,
                    post_plateau_not_scorable_candidates,
                    late_candidates,
                    unmatched_event_scorable_candidates,
                    unmatched_close_non_scorable_candidates,
                    delay_0_hits,
                    delay_1_hits,
                    delay_2_hits,
                    miss_no_exact_relation,
                    miss_conflicting_relation_only,
                    miss_exact_not_post_plateau,
                    miss_post_plateau_not_scorable,
                    miss_post_plateau_late,
                },
                ambiguity_count,
                verdict: EstimatorVerdict {
                    lcb_canonical,
                    passes_floor,
                },
                on_frontier,
            })
        })
        .collect()
}

// ---------------------------------------------------------------------
// proposal_bank.tsv (metrics::bank::ProposalBank, verbatim)
// ---------------------------------------------------------------------

/// Writes `proposal_bank.tsv`: one row per member [`StreamPoint`] (ranked
/// order), or exactly one placeholder row (`member_rank = NA`) if `bank` has
/// no members (never zero rows — a leaf must always be non-empty so the
/// state itself is never lost).
///
/// # Errors
///
/// Returns an error if the file cannot be written.
pub fn write_proposal_bank_leaf(dir: &Path, bank: &ProposalBank) -> Result<LeafRecord> {
    let (state, frontier_count) = match &bank.state {
        BankState::Selected => ("SELECTED".to_owned(), None),
        BankState::Insufficient { frontier_count, .. } => {
            ("BANK_INSUFFICIENT".to_owned(), Some(*frontier_count))
        }
    };
    let frontier_count_text = frontier_count.map_or_else(|| "NA".to_owned(), |v| v.to_string());

    let mut text = String::from(PROPOSAL_BANK_HEADER);
    text.push('\n');
    if bank.streams.is_empty() {
        writeln!(
            text,
            "{state}\t{}\t{frontier_count_text}\tNA\tNA\tNA\tNA\tNA\tNA\tNA",
            bank.eligible_count
        )
        .expect("writing to a String cannot fail");
    } else {
        for (rank, point) in bank.streams.iter().enumerate() {
            writeln!(
                text,
                "{state}\t{}\t{frontier_count_text}\t{rank}\t{}\t{}\t{}\t{}\t{}\t{}",
                bank.eligible_count,
                point.stream.policy_name(),
                point.stream.reversal_bps_wire(),
                point.hits,
                point.truths_denominator,
                point.burden,
                point.registration_order,
            )
            .expect("writing to a String cannot fail");
        }
    }
    write_leaf_text(dir, PROPOSAL_BANK_LEAF, &text)
}

/// Reads `proposal_bank.tsv`.
///
/// # Errors
///
/// Returns an error if the file is missing, malformed, has zero data rows,
/// or names an unrecognized `state`.
///
/// # Panics
///
/// Never in practice: `eligible_count` is always set in the same branch as
/// `state_text` (the loop's first assignment), so by the time `state_text`
/// is `Some` (checked just above each `.expect`), `eligible_count` is too.
pub fn read_proposal_bank_leaf(dir: &Path) -> Result<ProposalBank> {
    let lines = read_leaf_lines(dir, PROPOSAL_BANK_LEAF, PROPOSAL_BANK_HEADER)?;
    let mut streams = Vec::new();
    let mut state_text: Option<String> = None;
    let mut eligible_count: Option<usize> = None;
    let mut frontier_count: Option<Option<usize>> = None;

    for (line_number, line) in lines {
        let mut row = Row::new(&line, PROPOSAL_BANK_LEAF, line_number);
        let state = row.string("state")?;
        let this_eligible = row.usize("eligible_count")?;
        let this_frontier = row.opt_usize("frontier_count")?;
        let member_rank = row.opt_usize("member_rank")?;
        // `policy_name`/`reversal_bps` serve double duty here: on a
        // placeholder (no-member) row both are the literal text `NA`
        // (module doc); on a real member row they are this stream's own
        // wire identity, which — since ruling E22(a) — may ITSELF be the
        // legitimate `("UNION", "NA")` pair. Reading them as raw text and
        // deferring to `StreamId::from_wire` only in the `member_rank =
        // Some` branch below (rather than `Row::opt_string`/`opt_u16`,
        // which would misparse a genuine UNION member's `NA` reversal_bps
        // as "no value") keeps the two `NA` meanings from colliding.
        let policy_name_raw = row.raw("policy_name")?.to_owned();
        let reversal_bps_raw = row.raw("reversal_bps")?.to_owned();
        let hits = row.opt_u64("hits")?;
        let truths_denominator = row.opt_u64("truths_denominator")?;
        let burden = row.opt_u64("burden")?;
        let registration_order = row.opt_u64("registration_order")?;

        if let Some(existing) = &state_text
            && *existing != state
        {
            return Err(row.fail(
                "state",
                format!("disagrees with an earlier row's `{existing}`"),
            ));
        }
        state_text = Some(state);
        eligible_count = Some(this_eligible);
        frontier_count = Some(this_frontier);

        if let Some(rank) = member_rank {
            let stream = StreamId::from_wire(&policy_name_raw, &reversal_bps_raw)
                .map_err(|error| row.fail("policy_name/reversal_bps", error))?;
            let hits = hits.ok_or_else(|| row.fail("hits", "missing for a member row"))?;
            let truths_denominator = truths_denominator
                .ok_or_else(|| row.fail("truths_denominator", "missing for a member row"))?;
            let burden = burden.ok_or_else(|| row.fail("burden", "missing for a member row"))?;
            let registration_order = registration_order
                .ok_or_else(|| row.fail("registration_order", "missing for a member row"))?;
            row.finish()?;
            streams.push((
                rank,
                StreamPoint {
                    stream,
                    hits,
                    truths_denominator,
                    burden,
                    registration_order,
                },
            ));
        } else {
            row.finish()?;
        }
    }

    let state_text = state_text.ok_or_else(|| gate_error("proposal_bank.tsv: no data rows"))?;
    streams.sort_by_key(|(rank, _)| *rank);
    let streams: Vec<StreamPoint> = streams.into_iter().map(|(_, point)| point).collect();

    let state = match state_text.as_str() {
        "SELECTED" => BankState::Selected,
        "BANK_INSUFFICIENT" => {
            let frontier_count = frontier_count.flatten().ok_or_else(|| {
                gate_error("proposal_bank.tsv: BANK_INSUFFICIENT row missing frontier_count")
            })?;
            BankState::Insufficient {
                eligible_count: eligible_count.expect("set alongside state_text"),
                frontier_count,
                members: streams.clone(),
            }
        }
        other => {
            return Err(gate_error(format!(
                "proposal_bank.tsv: unrecognized state `{other}`"
            )));
        }
    };

    Ok(ProposalBank {
        state,
        streams,
        eligible_count: eligible_count.expect("set alongside state_text"),
    })
}

// ---------------------------------------------------------------------
// evaluation_registry.tsv (already-frozen leaf, `cli/src/run.rs`): the FULL
// E20 schema/constants are parsed and validated here (Sol#5 P0 fix), not
// just the four roster columns a prior version consulted.
// ---------------------------------------------------------------------

/// `cli/src/run.rs`'s exact, frozen `evaluation_registry.tsv` header (E20
/// ratified schema) — required verbatim, not merely as a prefix, so a
/// wholesale schema drift (dropped/reordered/renamed column) is caught
/// rather than silently misread.
const EVALUATION_REGISTRY_FULL_HEADER: &str = "ordinal\tday\tyear\twithin_year_ordinal\t\
    block_scheme\ttie_rule\tmax_timely_delay_bars\ttruth_denominator_40bps\t\
    truth_denominator_20bps\tstream_identity_key";

/// `cli::run::EVAL_BLOCK_SCHEME`, duplicated per this codebase's own small-
/// constant convention (matches `cli::metrics_cmd::BLOCK_SCHEME_NAME`).
const EVAL_BLOCK_SCHEME: &str = "year_stratified_five_session_blocks_within_year_calendar_ordinal";
/// `cli::run::EVAL_TIE_RULE`.
const EVAL_TIE_RULE: &str = "earlier_registration_order_never_hash";
/// `cli::run::EVAL_MAX_TIMELY_DELAY_BARS`.
const EVAL_MAX_TIMELY_DELAY_BARS: u32 = 2;
/// `cli::run::EVAL_TRUTH_DENOMINATOR_20BPS` (the 40bps constant is
/// [`FULL_CORPUS_TRUTH_DENOMINATOR`], reused rather than duplicated since
/// both name the identical registered value).
const EVAL_TRUTH_DENOMINATOR_20BPS: u64 = 34_325;
/// `cli::run::EVAL_STREAM_IDENTITY_KEY`.
const EVAL_STREAM_IDENTITY_KEY: &str = "policy_name,reversal_bps";

/// One `evaluation_registry.tsv` data row, fully parsed and checked against
/// every E20-ratified per-row constant (Sol#5 P0: "validate the complete
/// E20 schema and constant values").
struct EvalRegistryRow {
    day: String,
    session: SessionId,
}

/// Reads and validates `evaluation_registry.tsv` (Sol#5 P0 fix): exact
/// header match, every row's six E20-ratified constant columns checked
/// against their frozen values, the `ordinal` column required to be exactly
/// `0, 1, 2, ...` in file order (dense run ordinal), every `day` required
/// unique, and every `(year, within_year_ordinal)` pair required unique
/// (catches a relabeled/duplicated roster even before any frozen-calendar
/// comparison). Does NOT compare against the frozen 1,003-session calendar
/// itself — that is [`check_full_roster_matches_frozen_calendar`]'s job,
/// gated on `session_count == 1,003` (a genuine rehearsal subset cannot be
/// held to it).
///
/// # Errors
///
/// Returns an error naming the first structural, constant-value, density,
/// or uniqueness violation found.
fn read_evaluation_registry(dir: &Path) -> Result<Vec<EvalRegistryRow>> {
    let lines = read_leaf_lines(
        dir,
        EVALUATION_REGISTRY_LEAF,
        EVALUATION_REGISTRY_FULL_HEADER,
    )?;
    let mut seen_days: HashSet<String> = HashSet::new();
    let mut seen_sessions: HashSet<SessionId> = HashSet::new();
    let mut out = Vec::with_capacity(lines.len());
    for (expected_ordinal, (line_number, line)) in lines.into_iter().enumerate() {
        let mut row = Row::new(&line, EVALUATION_REGISTRY_LEAF, line_number);
        let ordinal = row.u64("ordinal")?;
        let day = row.string("day")?;
        let year = row.u16("year")?;
        let within_year_ordinal = row.u32("within_year_ordinal")?;
        let block_scheme = row.string("block_scheme")?;
        let tie_rule = row.string("tie_rule")?;
        let max_timely_delay_bars = row.u32("max_timely_delay_bars")?;
        let truth_denominator_40bps = row.u64("truth_denominator_40bps")?;
        let truth_denominator_20bps = row.u64("truth_denominator_20bps")?;
        let stream_identity_key = row.string("stream_identity_key")?;
        row.finish()?;

        if ordinal != expected_ordinal as u64 {
            return Err(gate_error(format!(
                "{EVALUATION_REGISTRY_LEAF}:{line_number}: `ordinal` is {ordinal}, expected the \
                 dense run ordinal {expected_ordinal}"
            )));
        }
        if block_scheme != EVAL_BLOCK_SCHEME {
            return Err(gate_error(format!(
                "{EVALUATION_REGISTRY_LEAF}:{line_number}: `block_scheme` is `{block_scheme}`, \
                 expected the frozen `{EVAL_BLOCK_SCHEME}`"
            )));
        }
        if tie_rule != EVAL_TIE_RULE {
            return Err(gate_error(format!(
                "{EVALUATION_REGISTRY_LEAF}:{line_number}: `tie_rule` is `{tie_rule}`, expected \
                 the frozen `{EVAL_TIE_RULE}`"
            )));
        }
        if max_timely_delay_bars != EVAL_MAX_TIMELY_DELAY_BARS {
            return Err(gate_error(format!(
                "{EVALUATION_REGISTRY_LEAF}:{line_number}: `max_timely_delay_bars` is \
                 {max_timely_delay_bars}, expected the frozen {EVAL_MAX_TIMELY_DELAY_BARS}"
            )));
        }
        if truth_denominator_40bps != FULL_CORPUS_TRUTH_DENOMINATOR {
            return Err(gate_error(format!(
                "{EVALUATION_REGISTRY_LEAF}:{line_number}: `truth_denominator_40bps` is \
                 {truth_denominator_40bps}, expected the frozen {FULL_CORPUS_TRUTH_DENOMINATOR}"
            )));
        }
        if truth_denominator_20bps != EVAL_TRUTH_DENOMINATOR_20BPS {
            return Err(gate_error(format!(
                "{EVALUATION_REGISTRY_LEAF}:{line_number}: `truth_denominator_20bps` is \
                 {truth_denominator_20bps}, expected the frozen {EVAL_TRUTH_DENOMINATOR_20BPS}"
            )));
        }
        if stream_identity_key != EVAL_STREAM_IDENTITY_KEY {
            return Err(gate_error(format!(
                "{EVALUATION_REGISTRY_LEAF}:{line_number}: `stream_identity_key` is \
                 `{stream_identity_key}`, expected the frozen `{EVAL_STREAM_IDENTITY_KEY}`"
            )));
        }
        if !seen_days.insert(day.clone()) {
            return Err(gate_error(format!(
                "{EVALUATION_REGISTRY_LEAF}:{line_number}: day `{day}` appears more than once"
            )));
        }
        let session = SessionId {
            year,
            ordinal: within_year_ordinal,
        };
        if !seen_sessions.insert(session) {
            return Err(gate_error(format!(
                "{EVALUATION_REGISTRY_LEAF}:{line_number}: session year={year} \
                 ordinal={within_year_ordinal} appears more than once (relabeled/duplicated \
                 roster)"
            )));
        }
        out.push(EvalRegistryRow { day, session });
    }
    Ok(out)
}

/// The frozen 1,003-session development calendar (AGENTS.md: "1,003
/// accepted development sessions 2022–2025"), derived — with ZERO runtime
/// filesystem access — from `corpus::all_sessions()`'s own compiled-in,
/// sha-pinned embedded registry, using the IDENTICAL within-year-ordinal
/// assignment `cli::run::full_registry_within_year_ordinals` uses (ascending
/// calendar-day order, 0-based sequential index per calendar year). This is
/// the compiled-in, source-free embedded authority Sol#5's minimal fix names
/// ("or an equivalently source-free embedded authority"): the corpus crate's
/// registry text is `include_str!`-embedded at compile time, so consulting
/// it here reads no path under `--dir` and no path outside the compiled
/// binary — the same category of pin as this crate's own `ESTIMATOR_LAWS_SHA256`.
fn frozen_development_calendar() -> BTreeMap<String, SessionId> {
    let mut counts: HashMap<u16, u32> = HashMap::new();
    let mut out = BTreeMap::new();
    for entry in corpus::all_sessions() {
        let year: u16 = entry.day[..4]
            .parse()
            .expect("registered day starts with a 4-digit year");
        let counter = counts.entry(year).or_insert(0);
        out.insert(
            entry.day.to_owned(),
            SessionId {
                year,
                ordinal: *counter,
            },
        );
        *counter += 1;
    }
    out
}

/// E21(d): "the full-run roster equals the frozen 1,003-session development
/// calendar ... subsets are typed non-accepting rehearsals." Requires exact
/// equality (as a `day -> SessionId` map, both directions) between `rows`
/// and [`frozen_development_calendar`] — never merely a row/truth count.
/// Only called once the caller has confirmed `session_count` equals
/// [`FULL_CORPUS_SESSION_COUNT`]; a genuine subset run cannot pass this by
/// construction and must not be asked to.
///
/// # Errors
///
/// Returns an error naming a mismatched day, a mismatched `SessionId` for an
/// otherwise-present day, or a size disagreement.
fn check_full_roster_matches_frozen_calendar(rows: &[EvalRegistryRow]) -> Result<()> {
    let frozen = frozen_development_calendar();
    let published: BTreeMap<&str, SessionId> = rows
        .iter()
        .map(|row| (row.day.as_str(), row.session))
        .collect();
    if published.len() != frozen.len() {
        return Err(gate_error(format!(
            "{EVALUATION_REGISTRY_LEAF}: {} distinct days published, expected the frozen \
             {} distinct days of the 1,003-session development calendar",
            published.len(),
            frozen.len()
        )));
    }
    for (day, session) in &published {
        match frozen.get(*day) {
            None => {
                return Err(gate_error(format!(
                    "{EVALUATION_REGISTRY_LEAF}: day `{day}` is not a member of the frozen \
                     1,003-session development calendar"
                )));
            }
            Some(frozen_session) if frozen_session != session => {
                return Err(gate_error(format!(
                    "{EVALUATION_REGISTRY_LEAF}: day `{day}` is published as year={} \
                     ordinal={}, but the frozen calendar assigns year={} ordinal={}",
                    session.year, session.ordinal, frozen_session.year, frozen_session.ordinal
                )));
            }
            Some(_) => {}
        }
    }
    Ok(())
}

// ---------------------------------------------------------------------
// StageGate: the GateRecomputer implementation
// ---------------------------------------------------------------------

/// The concrete [`GateRecomputer`] this workspace wires into
/// [`crate::verify::verify_publication`] for `stage1 verify-stage1 --dir`.
/// Carries no path/instance state: the pinned estimator is always resolved
/// as the declared in-directory leaf ([`Self::invoke_estimator`]), never a
/// caller-supplied or fixed external path (ruling E21e).
pub struct StageGate;

impl Default for StageGate {
    fn default() -> Self {
        Self::production()
    }
}

impl StageGate {
    /// The production instance.
    #[must_use]
    pub fn production() -> Self {
        Self
    }

    /// Resolves `dir.join(ESTIMATOR_LAWS_LEAF_NAME)` (the declared leaf a
    /// real `stage1 run` publishes), sha-verifies it against
    /// [`ESTIMATOR_LAWS_SHA256`], writes this crate's own compiled-in driver
    /// script to a scratch temp file, invokes `python3` on it, and parses its
    /// two-line stdout contract (module doc "`gate_estimator_driver.py`").
    /// Never reads any path outside `dir` (ruling E21e; closes Sol#7 P1 and
    /// Opus#P3-2's archive/`/workspace`-wide dependency at verify time).
    ///
    /// # Errors
    ///
    /// Returns [`PublishError::GateMismatch`] if the in-directory estimator
    /// file is absent or its sha256 does not match the pin, `python3` cannot
    /// be spawned, the driver exits nonzero, or its stdout does not parse as
    /// exactly two lines.
    #[allow(
        clippy::unused_self,
        reason = "kept as a method (not an associated function) for call-site symmetry with the \
                  rest of this crate's GateRecomputer seam, which is always invoked through a \
                  StageGate value; StageGate is a marker type today but is the natural place to \
                  carry future per-instance configuration"
    )]
    fn invoke_estimator(&self, dir: &Path, session_recall_path: &Path) -> Result<EstimatorVerdict> {
        let estimator_path = dir.join(ESTIMATOR_LAWS_LEAF_NAME);
        let (_, sha256) = hash_file_bytes(&estimator_path)?;
        if hex32(&sha256) != ESTIMATOR_LAWS_SHA256 {
            return Err(gate_error(format!(
                "{ESTIMATOR_LAWS_LEAF_NAME} at {} does not match the pinned sha256 \
                 {ESTIMATOR_LAWS_SHA256} (got {})",
                estimator_path.display(),
                hex32(&sha256)
            )));
        }

        let driver_path = std::env::temp_dir().join(format!(
            "stage1_gate_estimator_driver_{}_{:?}.py",
            std::process::id(),
            std::thread::current().id()
        ));
        std::fs::write(&driver_path, ESTIMATOR_DRIVER_SCRIPT).map_err(|source| {
            PublishError::Io {
                path: driver_path.clone(),
                source,
            }
        })?;

        let output = std::process::Command::new("python3")
            .arg(&driver_path)
            .arg(&estimator_path)
            .arg(session_recall_path)
            .output();
        let _ = std::fs::remove_file(&driver_path);
        let output = output.map_err(|source| {
            gate_error(format!(
                "failed to invoke python3 for the pinned estimator: {source}"
            ))
        })?;

        if !output.status.success() {
            return Err(gate_error(format!(
                "pinned estimator invocation failed (status {}): {}",
                output.status,
                String::from_utf8_lossy(&output.stderr)
            )));
        }
        let stdout = String::from_utf8_lossy(&output.stdout);
        let mut out_lines = stdout.lines();
        let lcb_canonical = out_lines
            .next()
            .ok_or_else(|| gate_error("pinned estimator produced no stdout"))?
            .to_owned();
        let verdict_line = out_lines
            .next()
            .ok_or_else(|| gate_error("pinned estimator produced only one stdout line"))?;
        let passes_floor = match verdict_line {
            "PASS" => true,
            "FAIL" => false,
            _other => {
                // E22(f): never echo the estimator's raw second stdout line
                // -- if its output shape ever drifted, that line could
                // itself carry a scientific value.
                return Err(gate_error(
                    "pinned estimator's second stdout line was neither PASS nor FAIL",
                ));
            }
        };
        Ok(EstimatorVerdict {
            lcb_canonical,
            passes_floor,
        })
    }
}

/// Groups `truths` (from [`read_truth_relation_projection`]) by session and
/// computes the pooled truth population's [`pooled_ambiguity_count`].
/// `anchor_bps` is not separately checked here — `read_truth_relation_projection`
/// already populates it as the fixed [`GATE_ANCHOR_BPS`] constant, since
/// ruling E18's `TRUTH` rows carry no per-row `anchor_bps` column to
/// disagree with it in the first place.
fn group_truths_by_session(truths: &[TruthRow]) -> (HashMap<SessionId, Vec<TruthRow>>, u64, u64) {
    let mut by_session: HashMap<SessionId, Vec<TruthRow>> = HashMap::new();
    for truth in truths {
        by_session.entry(truth.session).or_default().push(*truth);
    }
    let ambiguity_count = pooled_ambiguity_count(truths);
    let pooled_truths_count = truths.len() as u64;
    (by_session, ambiguity_count, pooled_truths_count)
}

// ---------------------------------------------------------------------
// Sol#3 P0 fix: the candidate stream universe and A9 tie order must be
// derived from the projection itself, never trusted from
// `stream_summary.tsv`'s own row set/`registration_order` column.
// (`discover_stream_universe` itself now lives with the rest of the
// streaming `TRUTH_RELATION_PROJECTION_LEAF` consumption above, next to
// `read_truth_relation_projection` — first-seen order over `CANDIDATE` rows
// in row-group/file order, ruling E18's "registration ordinal = file
// order".)
// ---------------------------------------------------------------------

/// Requires `published_streams` to name EXACTLY the `discovered` stream
/// universe (one row per stream, no omission, no unbacked extra stream) and
/// every row's `registration_order` to equal the dense (0-based) first-seen
/// order `discovered` itself encodes — never the published order taken on
/// faith (Sol#3 P0: "the candidate stream universe and A9 tie order are
/// self-authorized by `stream_summary.tsv`").
///
/// # Errors
///
/// Returns an error naming a duplicate published stream, a missing/extra
/// stream relative to the discovered universe, or a `registration_order`
/// that disagrees with the recomputed dense first-seen order.
fn check_stream_universe(
    published_streams: &[StreamSummaryRow],
    discovered: &[StreamId],
) -> Result<()> {
    let mut published_set: BTreeSet<StreamId> = BTreeSet::new();
    for row in published_streams {
        if !published_set.insert(row.stream.clone()) {
            return Err(gate_error(format!(
                "{STREAM_SUMMARY_LEAF}: stream {:?} appears in more than one row",
                row.stream
            )));
        }
    }
    let discovered_set: BTreeSet<StreamId> = discovered.iter().cloned().collect();
    if published_set != discovered_set {
        let missing: Vec<&StreamId> = discovered_set.difference(&published_set).collect();
        let extra: Vec<&StreamId> = published_set.difference(&discovered_set).collect();
        return Err(gate_error(format!(
            "{STREAM_SUMMARY_LEAF}'s stream set disagrees with the candidate stream universe \
             discovered from {TRUTH_RELATION_PROJECTION_LEAF}'s own CANDIDATE rows: missing \
             from {STREAM_SUMMARY_LEAF}={missing:?}, present in {STREAM_SUMMARY_LEAF} but \
             backed by no candidate row={extra:?}"
        )));
    }
    let expected_order: HashMap<&StreamId, u64> = discovered
        .iter()
        .enumerate()
        .map(|(index, stream)| (stream, index as u64))
        .collect();
    for row in published_streams {
        let expected = *expected_order
            .get(&row.stream)
            .expect("set equality was just checked above");
        if row.registration_order != expected {
            return Err(gate_error(format!(
                "{STREAM_SUMMARY_LEAF}: stream {:?} registration_order is {}, but the recomputed \
                 dense first-seen order over {TRUTH_RELATION_PROJECTION_LEAF} is {expected}",
                row.stream, row.registration_order
            )));
        }
    }
    Ok(())
}

/// E21(c) / Opus#P3-1: re-derives the registered EVENTS-gate stream as the
/// BEST floor-eligible published stream by the frozen tie order `(recall
/// desc, burden asc, registration_order asc)` — the identical rule A9's own
/// proposal-bank ranking applies ([`metrics::bank::build_bank`]'s internal
/// `rank`), evaluated here over every published stream's recomputed
/// [`StreamPoint`]/[`EstimatorVerdict`] pair. Never consults the published
/// `is_gate` flag (closes Opus#P3-1: "verifier takes the gate-stream
/// identity from the published `is_gate` flag rather than re-deriving it
/// source-free").
///
/// Returns `None` iff no published stream is floor-eligible (E21(a)'s
/// failure condition) — the caller turns that into the terminal
/// non-acceptance error; this function never itself decides acceptance.
fn best_eligible_stream(
    published_streams: &[StreamSummaryRow],
    points: &[StreamPoint],
) -> Option<StreamId> {
    let mut eligible: Vec<&StreamPoint> = published_streams
        .iter()
        .zip(points.iter())
        .filter(|(published, point)| is_eligible(point, &published.verdict))
        .map(|(_, point)| point)
        .collect();
    eligible.sort_by(|a, b| {
        compare_recall(b, a)
            .then_with(|| a.burden.cmp(&b.burden))
            .then_with(|| a.registration_order.cmp(&b.registration_order))
    });
    eligible.first().map(|point| point.stream.clone())
}

/// Reclassifies every published stream over every roster session
/// (`metrics::capture::classify`, pooled via [`add_counts`]), tallies the
/// gate stream's per-session hit counts along the way, and (Sol#2
/// adjudicated scope) accumulates every stream's own full `TruthOutcome`
/// sequence — the exact input [`check_regime_slices`] needs to recompute
/// A8's regime-sliced capture per stream without a second reclassification
/// pass.
/// [`reclassify_all_streams`]'s result: pooled [`CaptureCounts`] per stream,
/// the gate stream's own per-session hit counts, and every stream's full
/// [`TruthOutcome`] sequence (Sol#2's regime-slice recompute input).
type ReclassifiedStreams = (
    BTreeMap<StreamId, CaptureCounts>,
    HashMap<SessionId, u64>,
    HashMap<StreamId, Vec<TruthOutcome>>,
);

/// EVENTS.4 P0 memory-safety fix, pass 2 of 2 (see
/// [`read_truth_relation_projection`]'s doc for the shared streaming
/// rationale): re-opens [`TRUTH_RELATION_PROJECTION_LEAF`] and streams it a
/// SECOND time, again one session's row group at a time, but now
/// session-major/stream-minor (the loop nesting [`reclassify_all_streams`]
/// replaces was stream-major/session-minor, over a fully pre-grouped
/// all-sessions map) — for each session, this session's own `CANDIDATE`
/// rows are bucketed by stream ONCE, every published stream is classified
/// against that one session's own bucket (empty edges/outcomes for a stream
/// with no candidates that session, exactly as before), and the bucket is
/// dropped before the next session's row group is read. This reordering
/// does not change any accumulated result: every `(session, stream)` pair
/// is still classified exactly once, and each stream's own pooled
/// [`CaptureCounts`]/`TruthOutcome` sequence is still built by folding
/// sessions in roster order — the only thing that changed is which loop is
/// outermost, not the visitation set or per-stream sequence order.
fn reclassify_all_streams(
    dir: &Path,
    eval_rows: &[EvalRegistryRow],
    truths_by_session: &HashMap<SessionId, Vec<TruthRow>>,
    published_streams: &[StreamSummaryRow],
    gate_stream: &StreamId,
) -> Result<ReclassifiedStreams> {
    let path = dir.join(TRUTH_RELATION_PROJECTION_LEAF);
    let columns = read_leaf_columns(&path)?;
    let col = column_index(&columns);
    let plan = leaf_row_group_plan(dir, "truth_relation_projection", eval_rows)?;

    let empty_truths: Vec<TruthRow> = Vec::new();
    let empty_edges: Vec<RelationEdge> = Vec::new();
    let empty_outcomes: Vec<CandidateOutcome> = Vec::new();
    let mut hits_by_session: HashMap<SessionId, u64> = HashMap::new();
    let mut counts_by_stream: BTreeMap<StreamId, CaptureCounts> = published_streams
        .iter()
        .map(|published| (published.stream.clone(), CaptureCounts::default()))
        .collect();
    let mut truth_outcomes_by_stream: HashMap<StreamId, Vec<TruthOutcome>> = published_streams
        .iter()
        .map(|published| (published.stream.clone(), Vec::new()))
        .collect();

    let telemetry = SessionTelemetry::new(
        "verify-stage1: truth_relation_projection (reclassify)",
        session_count_u32(eval_rows.len())?,
    );
    for (position, (eval_row, plan_entry)) in eval_rows.iter().zip(&plan).enumerate() {
        let ordinal = session_count_u32(position)?;
        telemetry.begin(ordinal, &eval_row.day);
        let session = eval_row.session;
        let rows = read_leaf_session_rows(&path, *plan_entry)?;

        // This session's own CANDIDATE rows, bucketed by stream — dropped
        // once this session's stream loop below finishes.
        let mut edges_by_stream: HashMap<StreamId, Vec<RelationEdge>> = HashMap::new();
        let mut outcomes_by_stream: HashMap<StreamId, Vec<CandidateOutcome>> = HashMap::new();
        for row in &rows {
            if col_value(row, &col, "row_kind")? == "CANDIDATE" {
                let (edge, outcome) = parse_candidate_full(row, &col, &eval_row.day, session)?;
                edges_by_stream
                    .entry(edge.stream.clone())
                    .or_default()
                    .push(edge);
                outcomes_by_stream
                    .entry(outcome.stream.clone())
                    .or_default()
                    .push(outcome);
            }
        }

        let truths = truths_by_session.get(&session).unwrap_or(&empty_truths);
        for published in published_streams {
            let stream = &published.stream;
            let edges = edges_by_stream
                .get(stream)
                .map_or(&empty_edges, |edges| edges);
            let outcomes = outcomes_by_stream
                .get(stream)
                .map_or(&empty_outcomes, |outcomes| outcomes);
            let result = classify(session, stream, truths, edges, outcomes).map_err(|error| {
                gate_error(format!(
                    "reclassifying stream {stream:?} session {session:?}: {error}"
                ))
            })?;
            let pooled = counts_by_stream
                .get_mut(stream)
                .expect("counts_by_stream was seeded above for every published stream");
            *pooled = add_counts(*pooled, &result.counts)?;
            if stream == gate_stream {
                let session_hits = result
                    .truth_outcomes
                    .iter()
                    .filter(|outcome| {
                        matches!(
                            outcome.outcome,
                            metrics::capture::TruthCaptureOutcome::Hit { .. }
                        )
                    })
                    .count() as u64;
                hits_by_session.insert(session, session_hits);
            }
            truth_outcomes_by_stream
                .get_mut(stream)
                .expect("truth_outcomes_by_stream was seeded above for every published stream")
                .extend(result.truth_outcomes);
        }
        telemetry.done(ordinal, &eval_row.day);
    }
    Ok((counts_by_stream, hits_by_session, truth_outcomes_by_stream))
}

/// Cross-checks every published `stream_summary.tsv` row against its
/// independently-reclassified counterpart (capture counts per stream, d1/d2
/// delay split, burden, duplicates, conflicts, ambiguity — design brief §C,
/// ruling E14).
fn check_stream_summary(
    published_streams: &[StreamSummaryRow],
    counts_by_stream: &BTreeMap<StreamId, CaptureCounts>,
    ambiguity_count: u64,
) -> Result<()> {
    for published in published_streams {
        let recomputed = counts_by_stream
            .get(&published.stream)
            .expect("every published stream was just classified above");
        if *recomputed != published.counts {
            return Err(gate_content_mismatch(
                STREAM_SUMMARY_LEAF,
                format!("stream {}", published.stream),
                "capture counts (CaptureCounts, every field)",
            ));
        }
        if published.ambiguity_count != ambiguity_count {
            return Err(gate_content_mismatch(
                STREAM_SUMMARY_LEAF,
                format!(
                    "stream {} (pooled over {TRUTH_RELATION_PROJECTION_LEAF})",
                    published.stream
                ),
                "ambiguity_count",
            ));
        }
    }
    Ok(())
}

/// `session_recall.tsv` re-derivation + re-summing check (A1): rebuilds it
/// from the reclassification above and requires exact `(year, ordinal)`-keyed
/// agreement with the published file, then (on a full-corpus run) the frozen
/// 8,914 pooled-truths check.
fn check_session_recall(
    dir: &Path,
    roster: &[SessionId],
    truths_totals_by_session: &HashMap<SessionId, u64>,
    hits_by_session: &HashMap<SessionId, u64>,
    session_count: u64,
) -> Result<()> {
    let recomputed_session_recall =
        session_recall_rows(roster, truths_totals_by_session, hits_by_session)
            .map_err(|error| gate_error(format!("re-deriving session_recall.tsv: {error}")))?;
    let published_session_recall = read_session_recall_leaf(dir)?;

    let mut recomputed_by_key: BTreeMap<(u16, u32), SessionRecallRow> = BTreeMap::new();
    for row in &recomputed_session_recall {
        recomputed_by_key.insert((row.year, row.ordinal), *row);
    }
    let mut published_by_key: BTreeMap<(u16, u32), SessionRecallRow> = BTreeMap::new();
    for row in &published_session_recall {
        if published_by_key
            .insert((row.year, row.ordinal), *row)
            .is_some()
        {
            return Err(gate_error(format!(
                "{SESSION_RECALL_LEAF}: session year={} ordinal={} appears more than once",
                row.year, row.ordinal
            )));
        }
    }
    if recomputed_by_key != published_by_key {
        return Err(gate_error(format!(
            "{SESSION_RECALL_LEAF} does not reproduce the source-free recomputation from \
             {TRUTH_RELATION_PROJECTION_LEAF}: expected {} rows keyed \
             (year, ordinal), published carries {} rows (content and/or count disagree)",
            recomputed_by_key.len(),
            published_by_key.len(),
        )));
    }

    let (_pooled_hits, pooled_truths) = pooled_totals(&published_session_recall);
    if session_count == FULL_CORPUS_SESSION_COUNT && pooled_truths != FULL_CORPUS_TRUTH_DENOMINATOR
    {
        return Err(gate_content_mismatch(
            SESSION_RECALL_LEAF,
            "pooled (full-corpus run)",
            "pooled truths vs the frozen full-corpus truth denominator",
        ));
    }
    Ok(())
}

/// Builds one [`StreamPoint`] per published stream from the recomputed
/// [`CaptureCounts`] (recall/burden inputs) plus the published
/// `registration_order` (a caller-assigned tie-break authority, never
/// recomputed).
fn build_stream_points(
    published_streams: &[StreamSummaryRow],
    counts_by_stream: &BTreeMap<StreamId, CaptureCounts>,
) -> Vec<StreamPoint> {
    published_streams
        .iter()
        .map(|row| {
            let counts = counts_by_stream.get(&row.stream).expect("classified above");
            StreamPoint {
                stream: row.stream.clone(),
                hits: counts.unique_timely_hits,
                truths_denominator: counts.confirmed_truths,
                burden: counts.burden(),
                registration_order: row.registration_order,
            }
        })
        .collect()
}

/// Frontier check (recall vs burden, non-dominated set over streams):
/// requires every published `on_frontier` flag to match
/// `metrics::frontier::non_dominated`'s own recomputed membership.
fn check_frontier(published_streams: &[StreamSummaryRow], points: &[StreamPoint]) -> Result<()> {
    let frontier = non_dominated(points);
    let frontier_streams: std::collections::BTreeSet<StreamId> =
        frontier.iter().map(|point| point.stream.clone()).collect();
    for (published, point) in published_streams.iter().zip(points.iter()) {
        let recomputed_on_frontier = frontier_streams.contains(&point.stream);
        if published.on_frontier != recomputed_on_frontier {
            return Err(gate_content_mismatch(
                STREAM_SUMMARY_LEAF,
                format!("stream {}", published.stream),
                "on_frontier",
            ));
        }
    }
    Ok(())
}

/// Proposal-bank check (A9): consumes the published `EstimatorVerdict` rows
/// as input (never independently re-invoked per-stream, module doc),
/// recomputes the selection via `metrics::bank::build_bank` over the
/// (reclassified) points, and requires exact equality with the published
/// `proposal_bank.tsv`.
///
/// Returns the recomputed [`ProposalBank`] (already proven equal to
/// `proposal_bank.tsv`) so the caller can inspect its `state` for E21(b)'s
/// terminal-acceptance requirement without a second `build_bank` call.
fn check_bank(
    dir: &Path,
    published_streams: &[StreamSummaryRow],
    points: &[StreamPoint],
) -> Result<ProposalBank> {
    let candidates: Vec<StreamLcb> = points
        .iter()
        .zip(published_streams.iter())
        .map(|(point, published)| StreamLcb {
            point: point.clone(),
            verdict: published.verdict.clone(),
        })
        .collect();
    let recomputed_bank =
        build_bank(&candidates).map_err(|error| gate_error(format!("build_bank: {error}")))?;
    let published_bank = read_proposal_bank_leaf(dir)?;
    if recomputed_bank != published_bank {
        return Err(gate_content_mismatch(
            PROPOSAL_BANK_LEAF,
            "whole leaf",
            "proposal bank selection (state and/or ranked member set) vs \
             metrics::bank::build_bank over the reclassified stream summary",
        ));
    }
    Ok(recomputed_bank)
}

// ---------------------------------------------------------------------
// Sol#2 (adjudicated scope): the quantities `StageGate::recompute` did not
// yet recompute — regime-sliced capture (A8), the `metrics_frontier.tsv`/
// `metrics_bank.tsv`/`metrics_estimator_verdicts.tsv` diagnostic leaves, and
// an event_index/labels join smoke. Capture/session_recall recomputation
// was already verified sound (Opus) and is unchanged above; a
// checksum-only leaf is not a verified leaf.
// ---------------------------------------------------------------------

const METRICS_REGIME_SLICE_LEAF: &str = "metrics_regime_slice.tsv";
const METRICS_REGIME_SLICE_HEADER: &str =
    "policy_name\treversal_bps\tvol_tercile\ttrend_range\tsession_type\ttruths\thits\tstate";
const METRICS_REGIME_UNRESOLVED_LEAF: &str = "metrics_regime_unresolved.tsv";
const METRICS_REGIME_UNRESOLVED_HEADER: &str = "policy_name\treversal_bps\tno_regime_row\t\
    unresolved_rv\tunresolved_band\tunresolved_net_move\ttotal";
const METRICS_FRONTIER_LEAF: &str = "metrics_frontier.tsv";
const METRICS_FRONTIER_HEADER: &str = "policy_name\treversal_bps\thits\ttruths_denominator\t\
    burden\tregistration_order\tnon_dominated";
const METRICS_BANK_LEAF: &str = "metrics_bank.tsv";
const METRICS_BANK_HEADER: &str = "state\teligible_count\tfrontier_count\tpolicy_name\t\
    reversal_bps\thits\ttruths_denominator\tburden\tregistration_order";
const METRICS_ESTIMATOR_VERDICTS_LEAF: &str = "metrics_estimator_verdicts.tsv";
const METRICS_ESTIMATOR_VERDICTS_HEADER: &str =
    "policy_name\treversal_bps\tlcb_canonical\tpasses_floor\testimator_path\testimator_sha256";

/// `cli::run`'s own label-family leaf stems (local duplicate per this
/// crate's established convention — see `cli::verify_cmd`'s identically-
/// named constant).
const FAMILY_LEAF_STEMS: [&str; 11] = [
    "ext", "pass", "term", "ord", "dwell", "cfa", "qprim", "ctrl", "rank", "dir", "prox",
];

fn parse_sum_state(s: &str) -> Result<SumState> {
    match s {
        "OK" => Ok(SumState::Ok),
        "OVERFLOW" => Ok(SumState::Overflow),
        other => Err(gate_error(format!(
            "unexpected SumState wire value `{other}`"
        ))),
    }
}

fn parse_band_state(s: &str) -> Result<BandState> {
    match s {
        "OK" => Ok(BandState::Ok),
        "OVERFLOW" => Ok(BandState::Overflow),
        "NO_DATA" => Ok(BandState::NoData),
        other => Err(gate_error(format!(
            "unexpected BandState wire value `{other}`"
        ))),
    }
}

fn parse_net_move_state(s: &str) -> Result<NetMoveState> {
    match s {
        "OK" => Ok(NetMoveState::Ok),
        "OVERFLOW" => Ok(NetMoveState::Overflow),
        "INSUFFICIENT_HISTORY" => Ok(NetMoveState::InsufficientHistory),
        "NO_QUOTE" => Ok(NetMoveState::NoQuote),
        other => Err(gate_error(format!(
            "unexpected NetMoveState wire value `{other}`"
        ))),
    }
}

fn parse_opt_i64_col(
    row: &[String],
    col: &HashMap<&str, usize>,
    name: &str,
) -> Result<Option<i64>> {
    let raw = col_value(row, col, name)?;
    if raw == "NA" {
        return Ok(None);
    }
    raw.parse::<i64>().map(Some).map_err(|error| {
        gate_error(format!(
            "column `{name}` value `{raw}` is not an i64: {error}"
        ))
    })
}

/// Reads `regimes.parquet` into the [`RegimeBar`] population (A8), mirroring
/// `cli::metrics_cmd::read_regimes` field-for-field — this module's own
/// independent read of the SAME leaf, not a second invented shape.
fn read_regimes(dir: &Path, day_to_session: &HashMap<String, SessionId>) -> Result<Vec<RegimeBar>> {
    let path = dir.join("regimes.parquet");
    let (columns, rows) = read_utf8_parquet(&path)?;
    let col = column_index(&columns);
    let mut out = Vec::with_capacity(rows.len());
    for row in &rows {
        let day = col_value(row, &col, "day")?;
        let session = *day_to_session.get(day).ok_or_else(|| {
            gate_error(format!(
                "regimes.parquet references day `{day}` absent from {EVALUATION_REGISTRY_LEAF}"
            ))
        })?;
        let bar_ordinal: u32 = parse_field(row, &col, "bar_ordinal")?;
        let rv_15 = WindowStat {
            state: parse_sum_state(col_value(row, &col, "rv_sum_sq_15_state")?)?,
            sum_sq: parse_opt_i64_col(row, &col, "rv_sum_sq_15")?,
            count: parse_field(row, &col, "rv_count_15")?,
        };
        let band_u6_30 = BandResult {
            state: parse_band_state(col_value(row, &col, "band_u6_30_state")?)?,
            value_u6: parse_opt_i64_col(row, &col, "band_u6_30")?,
        };
        let net_move_u6_30 = NetMoveResult {
            state: parse_net_move_state(col_value(row, &col, "net_move_u6_30_state")?)?,
            value_u6: parse_opt_i64_col(row, &col, "net_move_u6_30")?,
        };
        let early_close = parse_bool_col(row, &col, "early_close")?;
        out.push(RegimeBar {
            session,
            bar_ordinal,
            rv_15,
            band_u6_30,
            net_move_u6_30,
            session_type: if early_close {
                SessionType::EarlyClose
            } else {
                SessionType::Normal
            },
        });
    }
    Ok(out)
}

/// Recomputes A8's 18-cell regime slice plus the 4-reason unresolved tally
/// for every published stream (from the already-reclassified
/// `truth_outcomes_by_stream`) and requires exact agreement with
/// `metrics_regime_slice.tsv`/`metrics_regime_unresolved.tsv` (Sol#2:
/// regime-sliced capture was previously checksum-only, never recomputed).
#[allow(
    clippy::too_many_lines,
    reason = "one linear read-both-leaves-then-compare-per-stream pass; splitting further would \
              scatter the exact per-leaf parse/compare pairing this function's own correctness \
              depends on"
)]
fn check_regime_slices(
    dir: &Path,
    all_truths: &[TruthRow],
    published_streams: &[StreamSummaryRow],
    truth_outcomes_by_stream: &HashMap<StreamId, Vec<TruthOutcome>>,
    regime_by_session_bar: &HashMap<(SessionId, u32), RegimeBar>,
    cuts: &RegimePopulationCuts,
) -> Result<()> {
    type CellKey = (&'static str, &'static str, &'static str);
    let mut published_cells: HashMap<StreamId, HashMap<CellKey, (u64, u64, String)>> =
        HashMap::new();
    for (line_number, line) in
        read_leaf_lines(dir, METRICS_REGIME_SLICE_LEAF, METRICS_REGIME_SLICE_HEADER)?
    {
        let mut row = Row::new(&line, METRICS_REGIME_SLICE_LEAF, line_number);
        let stream = row.stream_id("policy_name", "reversal_bps")?;
        let vol_tercile = row.string("vol_tercile")?;
        let trend_range = row.string("trend_range")?;
        let session_type = row.string("session_type")?;
        let truths = row.u64("truths")?;
        let hits = row.u64("hits")?;
        let state = row.string("state")?;
        row.finish()?;
        let key = wire_cell_key(&vol_tercile, &trend_range, &session_type).ok_or_else(|| {
            gate_error(format!(
                "{METRICS_REGIME_SLICE_LEAF}:{line_number}: unrecognized cell key \
                 ({vol_tercile}, {trend_range}, {session_type})"
            ))
        })?;
        if published_cells
            .entry(stream.clone())
            .or_default()
            .insert(key, (truths, hits, state))
            .is_some()
        {
            return Err(gate_error(format!(
                "{METRICS_REGIME_SLICE_LEAF}:{line_number}: stream {stream:?} publishes cell \
                 {key:?} more than once"
            )));
        }
    }

    let mut published_unresolved: HashMap<StreamId, (u64, u64, u64, u64, u64)> = HashMap::new();
    for (line_number, line) in read_leaf_lines(
        dir,
        METRICS_REGIME_UNRESOLVED_LEAF,
        METRICS_REGIME_UNRESOLVED_HEADER,
    )? {
        let mut row = Row::new(&line, METRICS_REGIME_UNRESOLVED_LEAF, line_number);
        let stream = row.stream_id("policy_name", "reversal_bps")?;
        let no_regime_row = row.u64("no_regime_row")?;
        let unresolved_rv = row.u64("unresolved_rv")?;
        let unresolved_band = row.u64("unresolved_band")?;
        let unresolved_net_move = row.u64("unresolved_net_move")?;
        let total = row.u64("total")?;
        row.finish()?;
        if published_unresolved
            .insert(
                stream.clone(),
                (
                    no_regime_row,
                    unresolved_rv,
                    unresolved_band,
                    unresolved_net_move,
                    total,
                ),
            )
            .is_some()
        {
            return Err(gate_error(format!(
                "{METRICS_REGIME_UNRESOLVED_LEAF}:{line_number}: stream {stream:?} appears more \
                 than once"
            )));
        }
    }

    for published in published_streams {
        let stream = &published.stream;
        let truth_outcomes = truth_outcomes_by_stream
            .get(stream)
            .expect("every published stream was reclassified above");
        let recomputed =
            build_regime_slices(all_truths, truth_outcomes, regime_by_session_bar, cuts);

        let published_stream_cells = published_cells.get(stream).ok_or_else(|| {
            gate_error(format!(
                "{METRICS_REGIME_SLICE_LEAF}: stream {stream:?} publishes zero regime-slice \
                 cells"
            ))
        })?;
        if published_stream_cells.len() != 18 {
            return Err(gate_error(format!(
                "{METRICS_REGIME_SLICE_LEAF}: stream {stream:?} publishes \
                 {} cells, expected exactly 18",
                published_stream_cells.len()
            )));
        }
        for cell in &recomputed.cells {
            let key = (
                cell.key.vol_tercile.wire(),
                cell.key.trend_range.wire(),
                cell.key.session_type.wire(),
            );
            let expected = (cell.truths, cell.hits, cell.state_wire().to_owned());
            match published_stream_cells.get(&key) {
                Some(actual) if *actual == expected => {}
                Some(_) => {
                    return Err(gate_content_mismatch(
                        METRICS_REGIME_SLICE_LEAF,
                        format!("stream {stream}, cell {key:?}"),
                        "truths/hits/state",
                    ));
                }
                None => {
                    return Err(gate_error(format!(
                        "{METRICS_REGIME_SLICE_LEAF}: stream {stream:?} is missing published \
                         cell {key:?}"
                    )));
                }
            }
        }

        let expected_unresolved = (
            recomputed.unresolved.no_regime_row,
            recomputed.unresolved.unresolved_rv,
            recomputed.unresolved.unresolved_band,
            recomputed.unresolved.unresolved_net_move,
            recomputed.unresolved.total(),
        );
        let actual_unresolved = published_unresolved.get(stream).ok_or_else(|| {
            gate_error(format!(
                "{METRICS_REGIME_UNRESOLVED_LEAF}: stream {stream:?} publishes no row"
            ))
        })?;
        if *actual_unresolved != expected_unresolved {
            return Err(gate_content_mismatch(
                METRICS_REGIME_UNRESOLVED_LEAF,
                format!("stream {stream}"),
                "no_regime_row/unresolved_rv/unresolved_band/unresolved_net_move/total",
            ));
        }
    }
    Ok(())
}

/// Maps a published cell's three wire strings to the fixed `&'static str`
/// triple [`Tercile`]/[`TrendRangeState`]/[`SessionType`]'s own `.wire()`
/// values use, so [`check_regime_slices`] can key both sides' maps
/// identically without parsing the wire strings back into enums.
fn wire_cell_key(vol_tercile: &str, trend_range: &str, session_type: &str) -> Option<CellKey> {
    let vol_tercile = Tercile::ALL
        .iter()
        .map(|t| t.wire())
        .find(|wire| *wire == vol_tercile)?;
    let trend_range = TrendRangeState::ALL
        .iter()
        .map(|t| t.wire())
        .find(|wire| *wire == trend_range)?;
    let session_type = SessionType::ALL
        .iter()
        .map(|t| t.wire())
        .find(|wire| *wire == session_type)?;
    Some((vol_tercile, trend_range, session_type))
}

type CellKey = (&'static str, &'static str, &'static str);

/// Recomputes the `metrics_frontier.tsv` diagnostic leaf from the same
/// recomputed `points`/`non_dominated` membership [`check_frontier`] already
/// uses for `stream_summary.tsv`'s `on_frontier` column, and requires exact
/// agreement (Sol#2: this leaf was previously checksum-only).
fn check_metrics_frontier_leaf(dir: &Path, points: &[StreamPoint]) -> Result<()> {
    let frontier = non_dominated(points);
    let frontier_streams: BTreeSet<StreamId> =
        frontier.iter().map(|point| point.stream.clone()).collect();
    let mut published: HashMap<StreamId, (u64, u64, u64, u64, bool)> = HashMap::new();
    for (line_number, line) in read_leaf_lines(dir, METRICS_FRONTIER_LEAF, METRICS_FRONTIER_HEADER)?
    {
        let mut row = Row::new(&line, METRICS_FRONTIER_LEAF, line_number);
        let stream = row.stream_id("policy_name", "reversal_bps")?;
        let hits = row.u64("hits")?;
        let truths_denominator = row.u64("truths_denominator")?;
        let burden = row.u64("burden")?;
        let registration_order = row.u64("registration_order")?;
        let non_dominated_flag = row.bool("non_dominated")?;
        row.finish()?;
        if published
            .insert(
                stream.clone(),
                (
                    hits,
                    truths_denominator,
                    burden,
                    registration_order,
                    non_dominated_flag,
                ),
            )
            .is_some()
        {
            return Err(gate_error(format!(
                "{METRICS_FRONTIER_LEAF}: stream {stream:?} appears more than once"
            )));
        }
    }
    for point in points {
        let expected = (
            point.hits,
            point.truths_denominator,
            point.burden,
            point.registration_order,
            frontier_streams.contains(&point.stream),
        );
        let actual = published.get(&point.stream).ok_or_else(|| {
            gate_error(format!(
                "{METRICS_FRONTIER_LEAF}: stream {:?} publishes no row",
                point.stream
            ))
        })?;
        if *actual != expected {
            return Err(gate_content_mismatch(
                METRICS_FRONTIER_LEAF,
                format!("stream {}", point.stream),
                "hits/truths_denominator/burden/registration_order/non_dominated",
            ));
        }
    }
    if published.len() != points.len() {
        return Err(gate_error(format!(
            "{METRICS_FRONTIER_LEAF}: publishes {} stream rows, expected exactly {}",
            published.len(),
            points.len()
        )));
    }
    Ok(())
}

/// Recomputes the `metrics_bank.tsv` diagnostic leaf's content against the
/// SAME `recomputed_bank` [`check_bank`] already proved equal to
/// `proposal_bank.tsv` (Sol#2: an attacker could otherwise corrupt this
/// `metrics_`-prefixed copy while leaving `proposal_bank.tsv` internally
/// consistent).
fn check_metrics_bank_leaf(dir: &Path, recomputed_bank: &ProposalBank) -> Result<()> {
    let lines = read_leaf_lines(dir, METRICS_BANK_LEAF, METRICS_BANK_HEADER)?;
    let (expected_state, expected_frontier_count) = match &recomputed_bank.state {
        BankState::Selected => ("SELECTED", recomputed_bank.streams.len()),
        BankState::Insufficient { frontier_count, .. } => ("BANK_INSUFFICIENT", *frontier_count),
    };
    let mut published_members: Vec<StreamPoint> = Vec::new();
    for (line_number, line) in &lines {
        let mut row = Row::new(line, METRICS_BANK_LEAF, *line_number);
        let state = row.string("state")?;
        let eligible_count = row.u64("eligible_count")?;
        let frontier_count = row.u64("frontier_count")?;
        // No `member_rank` column exists on this leaf (unlike
        // `proposal_bank.tsv`): a wholly-empty bank publishes exactly one
        // placeholder row with the literal `policy_name = "NA"`; `policy_name`
        // itself is the switch (never `"NA"` for a real stream, including
        // the UNION identity, whose `policy_name` is the literal `"UNION"`),
        // so reading it as raw text before deciding avoids misreading a
        // genuine UNION member's `reversal_bps = "NA"` as "no member here".
        let policy_name_raw = row.raw("policy_name")?.to_owned();
        let reversal_bps_raw = row.raw("reversal_bps")?.to_owned();
        let hits = row.opt_u64("hits")?;
        let truths_denominator = row.opt_u64("truths_denominator")?;
        let burden = row.opt_u64("burden")?;
        let registration_order = row.opt_u64("registration_order")?;
        if state != expected_state {
            return Err(gate_content_mismatch(
                METRICS_BANK_LEAF,
                format!("line {line_number}"),
                "state",
            ));
        }
        let recomputed_eligible_count = u64::try_from(recomputed_bank.eligible_count)
            .map_err(|_| PublishError::ArithmeticOverflow)?;
        if eligible_count != recomputed_eligible_count {
            return Err(gate_content_mismatch(
                METRICS_BANK_LEAF,
                format!("line {line_number}"),
                "eligible_count",
            ));
        }
        let recomputed_frontier_count =
            u64::try_from(expected_frontier_count).map_err(|_| PublishError::ArithmeticOverflow)?;
        if frontier_count != recomputed_frontier_count {
            return Err(gate_content_mismatch(
                METRICS_BANK_LEAF,
                format!("line {line_number}"),
                "frontier_count",
            ));
        }
        if policy_name_raw != "NA" {
            let stream = StreamId::from_wire(&policy_name_raw, &reversal_bps_raw)
                .map_err(|error| row.fail("policy_name/reversal_bps", error))?;
            let hits = hits.ok_or_else(|| {
                gate_error(format!(
                    "{METRICS_BANK_LEAF}:{line_number}: missing hits for a member row"
                ))
            })?;
            let truths_denominator = truths_denominator.ok_or_else(|| {
                gate_error(format!(
                    "{METRICS_BANK_LEAF}:{line_number}: missing truths_denominator for a member row"
                ))
            })?;
            let burden = burden.ok_or_else(|| {
                gate_error(format!(
                    "{METRICS_BANK_LEAF}:{line_number}: missing burden for a member row"
                ))
            })?;
            let registration_order = registration_order.ok_or_else(|| {
                gate_error(format!(
                    "{METRICS_BANK_LEAF}:{line_number}: missing registration_order for a member row"
                ))
            })?;
            published_members.push(StreamPoint {
                stream,
                hits,
                truths_denominator,
                burden,
                registration_order,
            });
        }
        row.finish()?;
    }
    if published_members != recomputed_bank.streams {
        return Err(gate_content_mismatch(
            METRICS_BANK_LEAF,
            "ranked member list",
            "policy_name/reversal_bps/hits/truths_denominator/burden/registration_order (member \
             set and/or order)",
        ));
    }
    Ok(())
}

/// Cross-checks `metrics_estimator_verdicts.tsv`'s per-stream verdict
/// against `stream_summary.tsv`'s own published verdict for that stream
/// (Sol#2: "estimator-verdict equality") — both leaves are meant to carry
/// the identical [`EstimatorVerdict`] the real `stage1 metrics` estimator
/// invocation produced for that stream; an honest run never disagrees.
fn check_metrics_estimator_verdicts_leaf(
    dir: &Path,
    published_streams: &[StreamSummaryRow],
) -> Result<()> {
    let mut published: HashMap<StreamId, EstimatorVerdict> = HashMap::new();
    for (line_number, line) in read_leaf_lines(
        dir,
        METRICS_ESTIMATOR_VERDICTS_LEAF,
        METRICS_ESTIMATOR_VERDICTS_HEADER,
    )? {
        let mut row = Row::new(&line, METRICS_ESTIMATOR_VERDICTS_LEAF, line_number);
        let stream = row.stream_id("policy_name", "reversal_bps")?;
        let lcb_canonical = row.string("lcb_canonical")?;
        let passes_floor = row.bool("passes_floor")?;
        let _estimator_path = row.string("estimator_path")?;
        let _estimator_sha256 = row.string("estimator_sha256")?;
        row.finish()?;
        if published
            .insert(
                stream.clone(),
                EstimatorVerdict {
                    lcb_canonical,
                    passes_floor,
                },
            )
            .is_some()
        {
            return Err(gate_error(format!(
                "{METRICS_ESTIMATOR_VERDICTS_LEAF}: stream {stream:?} appears more than once"
            )));
        }
    }
    for row in published_streams {
        let actual = published.get(&row.stream).ok_or_else(|| {
            gate_error(format!(
                "{METRICS_ESTIMATOR_VERDICTS_LEAF}: stream {:?} publishes no row",
                row.stream
            ))
        })?;
        if *actual != row.verdict {
            return Err(gate_content_mismatch(
                METRICS_ESTIMATOR_VERDICTS_LEAF,
                format!("stream {} (vs {STREAM_SUMMARY_LEAF})", row.stream),
                "lcb_canonical/passes_floor",
            ));
        }
    }
    Ok(())
}

// ---------------------------------------------------------------------
// Sol#2: event_index/labels join smoke -- sample-based row-count + key-
// consistency check per family leaf, source-free from `--dir`.
// ---------------------------------------------------------------------

/// One `<leaf_stem>_session_index.tsv` data row.
struct SessionIndexEntry {
    ordinal: u32,
    day: String,
    rows: u64,
}

/// Reads a parquet leaf's own companion `<leaf_stem>_session_index.tsv`
/// (`ordinal\tday\trows`, `publish::parquet_leaf::LeafWriter`'s own
/// convention) — a small dedicated parser rather than the shared
/// `'static`-keyed [`Row`]/[`read_leaf_lines`] helpers, since `leaf_stem`
/// here is a runtime-built name (one of the 12 family or `event_index`
/// leaves).
fn read_session_index(dir: &Path, leaf_stem: &str) -> Result<Vec<SessionIndexEntry>> {
    let name = format!("{leaf_stem}_session_index.tsv");
    let path = dir.join(&name);
    let text = std::fs::read_to_string(&path).map_err(|source| PublishError::Io {
        path: path.clone(),
        source,
    })?;
    let mut lines = text.lines();
    let header = lines
        .next()
        .ok_or_else(|| gate_error(format!("{name}: empty file")))?;
    if header != "ordinal\tday\trows" {
        return Err(gate_error(format!(
            "{name}: unexpected header `{header}`, expected `ordinal\\tday\\trows`"
        )));
    }
    lines
        .filter(|line| !line.is_empty())
        .map(|line| {
            let mut parts = line.split('\t');
            let ordinal: u32 = parts
                .next()
                .ok_or_else(|| gate_error(format!("{name}: row missing `ordinal`")))?
                .parse()
                .map_err(|_| gate_error(format!("{name}: `ordinal` is not a u32")))?;
            let day = parts
                .next()
                .ok_or_else(|| gate_error(format!("{name}: row missing `day`")))?
                .to_owned();
            let rows: u64 = parts
                .next()
                .ok_or_else(|| gate_error(format!("{name}: row missing `rows`")))?
                .parse()
                .map_err(|_| gate_error(format!("{name}: `rows` is not a u64")))?;
            Ok(SessionIndexEntry { ordinal, day, rows })
        })
        .collect()
}

/// `f_cfa`'s own registered "deviation from the standard three-row
/// convention" (`f_cfa_schema_v1.md` "Row shape"; `labels::f_cfa::rows`'s
/// own doc comment): **four** rows per signal (`D1, D2, D3, PASS`), not the
/// three every other family (and `event_index` itself) publishes — so its
/// row count is legitimately `4/3` of `event_index`'s, never equal to it.
const FOUR_ROW_FAMILY_STEM: &str = "cfa";

/// The exact multiplier [`FOUR_ROW_FAMILY_STEM`] applies to `event_index`'s
/// row count (4 rows per signal vs `event_index`'s 3). `None` iff
/// `event_index_rows` is not itself a multiple of 3 (the "3 rows per
/// signal" assumption the ratio depends on would already be violated).
fn expected_family_row_count(stem: &str, event_index_rows: u64) -> Option<u64> {
    if stem == FOUR_ROW_FAMILY_STEM {
        if event_index_rows.is_multiple_of(3) {
            Some((event_index_rows / 3) * 4)
        } else {
            None
        }
    } else {
        Some(event_index_rows)
    }
}

/// Row-count join smoke (exhaustive, cheap — TSV companion files only):
/// requires `event_index.parquet` and every `labels_<family>.parquet` to
/// carry a per-session row-count sequence in the exact registered ratio to
/// `event_index`'s own (same ordinal/day order; `1:1` for every family
/// except [`FOUR_ROW_FAMILY_STEM`]'s registered `4:3`) via their own
/// `_session_index.tsv` companions. Returns `event_index`'s own session
/// index (reused by [`check_event_index_key_sample`] to pick a sample).
fn check_event_index_row_counts(dir: &Path) -> Result<Vec<SessionIndexEntry>> {
    let event_index = read_session_index(dir, "event_index")?;
    for stem in FAMILY_LEAF_STEMS {
        let leaf_stem = format!("labels_{stem}");
        let family = read_session_index(dir, &leaf_stem)?;
        if family.len() != event_index.len() {
            return Err(gate_error(format!(
                "{leaf_stem}_session_index.tsv has {} session rows, event_index_session_index.tsv \
                 has {} (event_index/labels join smoke)",
                family.len(),
                event_index.len()
            )));
        }
        for (e, f) in event_index.iter().zip(family.iter()) {
            if e.ordinal != f.ordinal || e.day != f.day {
                return Err(gate_error(format!(
                    "{leaf_stem}_session_index.tsv session (ordinal={}, day={}) disagrees with \
                     event_index_session_index.tsv's (ordinal={}, day={}) at the same position",
                    f.ordinal, f.day, e.ordinal, e.day
                )));
            }
            let expected = expected_family_row_count(stem, e.rows).ok_or_else(|| {
                gate_error(format!(
                    "{leaf_stem}.parquet: event_index.parquet's {} rows for day {} (ordinal {}) \
                     is not evenly divisible by 3 (required for the registered 4:3 row-count \
                     ratio)",
                    e.rows, f.day, f.ordinal
                ))
            })?;
            if f.rows != expected {
                return Err(gate_error(format!(
                    "{leaf_stem}.parquet has {} rows for day {} (ordinal {}), expected {expected} \
                     from event_index.parquet's {} rows (event_index/labels join smoke row-count \
                     mismatch)",
                    f.rows, f.day, f.ordinal, e.rows
                )));
            }
        }
    }
    Ok(event_index)
}

/// The per-session-batch decoded-byte guard (EVENTS.4 P0 memory-safety fix,
/// `docs/specs/events3_design_amendment_v2.md` E19's "peak memory must be a
/// function of workers + reorder window, never corpus size", generalized to
/// every streaming consumer, not just `stage1 run`'s own scheduler). Chosen
/// from the real crashed publication's own measured shape: the single
/// largest `truth_relation_projection.parquet` row group (one session) was
/// ~76.6 MiB of footer-recorded decoded content, and the whole file's
/// decoded content (4.92 GiB) inflated to the ~51.4 GiB RSS that got
/// `SIGKILLed` — an empirically observed ~10.5x String/Vec materialization
/// multiplier. `512 MiB` leaves ~6.7x headroom over the largest real session
/// while keeping the worst-case *projected* transient RSS for one guarded
/// session (`512 MiB * 10.5 ~= 5.4 GiB`) safely under the 8 GiB target even
/// before accounting for the (small, bounded) rest of this process's own
/// resident state. A session anywhere near this bound is a genuine anomaly
/// worth failing closed on, never silently decoding further.
const MAX_SESSION_ROW_GROUP_DECODED_BYTES: i64 = 512 * 1024 * 1024;

/// Reads exactly one row group of an all-Utf8 parquet leaf (local variant of
/// [`read_utf8_parquet`] restricted to `row_group` — the sample-based
/// reading strategy Sol#2's minimal fix names, avoiding a full-file
/// materialization of every family leaf at real-scale row counts; EVENTS.4
/// P0 memory-safety fix reuses this exact same primitive as the one
/// session-at-a-time reader for `truth_relation_projection.parquet`).
/// Checks the row group's own footer-recorded `total_byte_size` against
/// [`MAX_SESSION_ROW_GROUP_DECODED_BYTES`] BEFORE decoding anything (cheap:
/// the footer is already parsed by the time this check runs) — a coarse
/// typed guard, never a decode-then-measure-after-the-fact approach.
///
/// # Errors
///
/// Returns [`PublishError::SessionBatchTooLarge`] if the row group's decoded
/// size exceeds the guard, or an I/O/parquet error opening/decoding it.
fn read_utf8_parquet_row_group(
    path: &Path,
    row_group: usize,
) -> Result<(Vec<String>, Vec<Vec<String>>)> {
    let file = File::open(path).map_err(|source| PublishError::Io {
        path: path.to_path_buf(),
        source,
    })?;
    let builder = ParquetRecordBatchReaderBuilder::try_new(file).map_err(|error| {
        gate_error(format!(
            "reading parquet schema for {}: {error}",
            path.display()
        ))
    })?;
    let approx_decoded_bytes = builder.metadata().row_group(row_group).total_byte_size();
    if approx_decoded_bytes > MAX_SESSION_ROW_GROUP_DECODED_BYTES {
        return Err(PublishError::SessionBatchTooLarge {
            path: path.to_path_buf(),
            row_group,
            approx_decoded_bytes,
            limit_bytes: MAX_SESSION_ROW_GROUP_DECODED_BYTES,
        });
    }
    let builder = builder.with_row_groups(vec![row_group]);
    let columns: Vec<String> = builder
        .schema()
        .fields()
        .iter()
        .map(|field| field.name().clone())
        .collect();
    let reader = builder.build().map_err(|error| {
        gate_error(format!(
            "building parquet reader for {} row group {row_group}: {error}",
            path.display()
        ))
    })?;
    let mut rows = Vec::new();
    for batch in reader {
        let batch = batch.map_err(|error| {
            gate_error(format!(
                "reading row group {row_group} of {}: {error}",
                path.display()
            ))
        })?;
        let string_columns: Vec<&StringArray> = (0..batch.num_columns())
            .map(|i| {
                batch
                    .column(i)
                    .as_any()
                    .downcast_ref::<StringArray>()
                    .ok_or_else(|| {
                        gate_error(format!(
                            "{}: column {i} is not Utf8 (violates the all-Utf8 leaf convention)",
                            path.display()
                        ))
                    })
            })
            .collect::<Result<_>>()?;
        for r in 0..batch.num_rows() {
            rows.push(
                string_columns
                    .iter()
                    .map(|column| column.value(r).to_owned())
                    .collect(),
            );
        }
    }
    Ok((columns, rows))
}

/// Sample-based key-consistency join smoke (Sol#2): for a small, bounded
/// sample of sessions that actually carry rows (first, middle, last —
/// fewer if fewer exist; a wholly empty run has nothing to sample and the
/// row-count smoke above already proved every leaf agrees at zero), reads
/// ONLY that session's own row group from `event_index.parquet` and every
/// `labels_<family>.parquet` and requires their `(day, signal_id, slot)` key
/// sequences to match exactly, position for position (every family leaf is
/// built from the SAME per-session anchor traversal as `event_index`, so an
/// honest publication's keys are identical in the same order).
fn check_event_index_key_sample(dir: &Path, event_index: &[SessionIndexEntry]) -> Result<()> {
    let nonzero_positions: Vec<usize> = event_index
        .iter()
        .enumerate()
        .filter(|(_, entry)| entry.rows > 0)
        .map(|(index, _)| index)
        .collect();
    if nonzero_positions.is_empty() {
        return Ok(());
    }
    let mut sample_positions: BTreeSet<usize> = BTreeSet::new();
    sample_positions.insert(nonzero_positions[0]);
    sample_positions.insert(nonzero_positions[nonzero_positions.len() - 1]);
    sample_positions.insert(nonzero_positions[nonzero_positions.len() / 2]);

    let event_index_path = dir.join("event_index.parquet");
    for &position in &sample_positions {
        // The row-group index among ONLY the nonzero-row sessions written
        // to this leaf so far (a zero-row `write_session` call never opens
        // a row group -- `publish::parquet_leaf::LeafWriter` doc).
        let row_group = event_index[..position]
            .iter()
            .filter(|entry| entry.rows > 0)
            .count();
        let entry = &event_index[position];

        let (event_columns, event_rows) =
            read_utf8_parquet_row_group(&event_index_path, row_group)?;
        let event_col = column_index(&event_columns);
        let event_keys: Vec<(String, String, String)> = event_rows
            .iter()
            .map(|row| {
                Ok::<_, PublishError>((
                    col_value(row, &event_col, "day")?.to_owned(),
                    col_value(row, &event_col, "signal_id")?.to_owned(),
                    col_value(row, &event_col, "slot")?.to_owned(),
                ))
            })
            .collect::<Result<_>>()?;

        for stem in FAMILY_LEAF_STEMS {
            let leaf_stem = format!("labels_{stem}");
            let family_path = dir.join(format!("{leaf_stem}.parquet"));
            let (family_columns, family_rows) =
                read_utf8_parquet_row_group(&family_path, row_group)?;
            let family_col = column_index(&family_columns);
            let family_keys: Vec<(String, String, String)> = family_rows
                .iter()
                .map(|row| {
                    Ok::<_, PublishError>((
                        col_value(row, &family_col, "day")?.to_owned(),
                        col_value(row, &family_col, "signal_id")?.to_owned(),
                        col_value(row, &family_col, "slot")?.to_owned(),
                    ))
                })
                .collect::<Result<_>>()?;
            // `FOUR_ROW_FAMILY_STEM`'s registered extra `PASS` row per
            // signal (module doc) carries no counterpart in `event_index`
            // at all -- excluded before the position-for-position
            // comparison, never compared against.
            let comparable_family_keys: Vec<(String, String, String)> =
                if stem == FOUR_ROW_FAMILY_STEM {
                    family_keys
                        .into_iter()
                        .filter(|(_, _, slot)| slot != "PASS")
                        .collect()
                } else {
                    family_keys
                };
            if event_keys != comparable_family_keys {
                return Err(gate_error(format!(
                    "{leaf_stem}.parquet row group {row_group} (day {}, ordinal {}) has \
                     (day, signal_id, slot) keys disagreeing with event_index.parquet's own keys \
                     for that session (event_index/labels join smoke key-consistency failure)",
                    entry.day, entry.ordinal
                )));
            }
        }
    }
    Ok(())
}

impl GateRecomputer for StageGate {
    #[allow(
        clippy::too_many_lines,
        reason = "one linear source-free gate recomputation pass; splitting further would scatter \
                  the E21 terminal-acceptance ordering (diagnostic reproduction, then acceptance) \
                  this function's own doc/tests rely on reading top-to-bottom"
    )]
    fn recompute(&self, dir: &Path) -> Result<()> {
        let receipt = RunReceipt::read_from(dir)?;

        // Sol#5 P0 fix: full E20 schema/constant/uniqueness validation, not
        // just 4-of-10 columns loosely prefix-matched.
        let eval_rows = read_evaluation_registry(dir)?;
        if eval_rows.len() as u64 != receipt.session_count {
            return Err(gate_error(format!(
                "{EVALUATION_REGISTRY_LEAF} has {} session rows, but run_receipt.json's \
                 session_count is {}",
                eval_rows.len(),
                receipt.session_count
            )));
        }
        let is_full_roster = receipt.session_count == FULL_CORPUS_SESSION_COUNT;
        if is_full_roster {
            check_full_roster_matches_frozen_calendar(&eval_rows)?;
        }
        let roster: Vec<SessionId> = eval_rows.iter().map(|row| row.session).collect();
        let day_to_session: HashMap<String, SessionId> = eval_rows
            .iter()
            .map(|row| (row.day.clone(), row.session))
            .collect();

        // EVENTS.4 P0 memory-safety fix: `truth_relation_projection.parquet`
        // is streamed one session's row group at a time by both functions
        // below (never the whole ~40M-row leaf materialized at once — see
        // `read_truth_relation_projection`'s doc for the crash this
        // replaces). `day_to_session` is no longer needed for this leaf
        // (session identity now comes straight from `eval_rows`, in the
        // same dense order the leaf's own session-index companion is
        // checked against); it is kept for `read_regimes` below.
        let truths = read_truth_relation_projection(dir, &eval_rows)?;
        let (truths_by_session, ambiguity_count, pooled_truths_count) =
            group_truths_by_session(&truths);
        if receipt.session_count == FULL_CORPUS_SESSION_COUNT
            && pooled_truths_count != FULL_CORPUS_TRUTH_DENOMINATOR
        {
            return Err(gate_error(format!(
                "{TRUTH_RELATION_PROJECTION_LEAF}: full-corpus run \
                 (session_count={FULL_CORPUS_SESSION_COUNT}) carries {pooled_truths_count} \
                 truths, expected the frozen {FULL_CORPUS_TRUTH_DENOMINATOR}"
            )));
        }

        // Sol#3 P0 fix: the candidate stream universe (and its dense
        // registration order) is discovered from the projection itself,
        // never trusted from `stream_summary.tsv`'s own row set.
        let discovered_streams = discover_stream_universe(dir, &eval_rows)?;

        let published_streams = read_stream_summary_leaf(dir)?;
        check_stream_universe(&published_streams, &discovered_streams)?;

        let gate_rows: Vec<&StreamSummaryRow> =
            published_streams.iter().filter(|row| row.is_gate).collect();
        if gate_rows.len() != 1 {
            return Err(gate_error(format!(
                "{STREAM_SUMMARY_LEAF}: exactly one row must have is_gate=true, found {}",
                gate_rows.len()
            )));
        }
        let gate_stream = gate_rows[0].stream.clone();

        let mut truths_totals_by_session: HashMap<SessionId, u64> = HashMap::new();
        for &session in &roster {
            truths_totals_by_session.insert(
                session,
                truths_by_session.get(&session).map_or(0, Vec::len) as u64,
            );
        }

        let (counts_by_stream, hits_by_session, truth_outcomes_by_stream) = reclassify_all_streams(
            dir,
            &eval_rows,
            &truths_by_session,
            &published_streams,
            &gate_stream,
        )?;

        check_stream_summary(&published_streams, &counts_by_stream, ambiguity_count)?;
        check_session_recall(
            dir,
            &roster,
            &truths_totals_by_session,
            &hits_by_session,
            receipt.session_count,
        )?;

        // Pinned-estimator re-invocation (A1): re-invoke on the PUBLISHED
        // session_recall.tsv and require exact unrounded agreement with the
        // gate stream's published EstimatorVerdict.
        let recomputed_verdict = self.invoke_estimator(dir, &dir.join(SESSION_RECALL_LEAF))?;
        if recomputed_verdict != gate_rows[0].verdict {
            return Err(gate_content_mismatch(
                SESSION_RECALL_LEAF,
                format!("gate stream {gate_stream}"),
                "pinned-estimator re-invocation lcb_canonical/passes_floor",
            ));
        }

        let points = build_stream_points(&published_streams, &counts_by_stream);
        check_frontier(&published_streams, &points)?;
        let recomputed_bank = check_bank(dir, &published_streams, &points)?;

        // Sol#2 (adjudicated scope): quantities `StageGate::recompute` did
        // not yet recompute -- regime-sliced capture (A8), the
        // `metrics_frontier.tsv`/`metrics_bank.tsv`/
        // `metrics_estimator_verdicts.tsv` diagnostic leaves, and the
        // event_index/labels join smoke. A checksum-only leaf is not a
        // verified leaf.
        let regime_bars = read_regimes(dir, &day_to_session)?;
        let cuts = RegimePopulationCuts::build(&regime_bars).ok_or_else(|| {
            gate_error("regimes.parquet has zero rows; cannot build A8 tercile cuts")
        })?;
        let regime_by_session_bar: HashMap<(SessionId, u32), RegimeBar> = regime_bars
            .iter()
            .map(|bar| ((bar.session, bar.bar_ordinal), *bar))
            .collect();
        check_regime_slices(
            dir,
            &truths,
            &published_streams,
            &truth_outcomes_by_stream,
            &regime_by_session_bar,
            &cuts,
        )?;
        check_metrics_frontier_leaf(dir, &points)?;
        check_metrics_bank_leaf(dir, &recomputed_bank)?;
        check_metrics_estimator_verdicts_leaf(dir, &published_streams)?;
        let event_index_session_index = check_event_index_row_counts(dir)?;
        check_event_index_key_sample(dir, &event_index_session_index)?;

        // ---- E21 terminal acceptance: distinct from every reproducibility
        // check above -- a publication can reproduce every leaf exactly and
        // still not be ACCEPTED as a completed EVENTS milestone (Sol#4 P0
        // fix's "separate diagnostic reproduction from terminal
        // acceptance"). ----

        // E21(c) / Opus#P3-1: re-derive the gate stream as the best
        // floor-eligible stream by the frozen tie order, and require the
        // published `is_gate` flag to actually name it -- never trusted on
        // its own.
        let registered_gate_stream = best_eligible_stream(&published_streams, &points);
        match &registered_gate_stream {
            None => {
                return Err(gate_error(
                    "EVENTS terminal acceptance (E21a): no published candidate stream satisfies \
                     both the integer recall floor (5*hits >= 4*truths_denominator) and the \
                     pinned estimator's passes_floor=true; verify-stage1 cannot accept",
                ));
            }
            Some(best) if *best != gate_stream => {
                return Err(gate_error(format!(
                    "EVENTS terminal acceptance (E21c / Opus#P3-1): {STREAM_SUMMARY_LEAF}'s \
                     published is_gate stream {gate_stream:?} disagrees with the registered \
                     best-eligible stream {best:?} (recall desc, burden asc, registration order \
                     asc); the verifier never trusts the published flag for terminal acceptance"
                )));
            }
            Some(_) => {}
        }

        // E21(b): a non-Selected bank verifies but does not accept.
        if !matches!(recomputed_bank.state, BankState::Selected) {
            return Err(gate_error(format!(
                "EVENTS terminal acceptance (E21b): the recomputed proposal bank state is \
                 {}, not SELECTED; BANK_INSUFFICIENT verifies but does not accept",
                recomputed_bank.state.wire()
            )));
        }

        // E21(d): a subset roster is a typed, non-accepting rehearsal.
        if !is_full_roster {
            return Err(gate_error(format!(
                "EVENTS terminal acceptance (E21d): this run's session_count is \
                 {}, not the frozen {FULL_CORPUS_SESSION_COUNT}-session development calendar; \
                 this is a non-accepting rehearsal, not a terminal EVENTS-stage acceptance",
                receipt.session_count
            )));
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::LeafWriter;
    use crate::atomic::PublishStaging;
    use arrow_array::RecordBatch;
    use arrow_schema::{DataType, Field, Schema, SchemaRef};
    use std::path::PathBuf;
    use std::sync::{Arc, Mutex};

    /// This module's tests spawn a real `python3` subprocess and build
    /// on-disk fixtures under a shared scratch root; this sandbox's default
    /// (highly parallel, `nproc`-wide) `cargo test` concurrency, combined
    /// with other concurrent agents' own cargo/filesystem activity in this
    /// same workspace, was observed to intermittently corrupt/lose
    /// freshly-written fixture files purely from resource contention (not a
    /// bug in the recomputation logic itself — every test here passes
    /// reliably under `--test-threads=1`). Serializing just this module's
    /// own tests removes that self-inflicted contention without forcing the
    /// whole crate's test suite to run single-threaded.
    static SERIAL: Mutex<()> = Mutex::new(());

    fn serial_guard() -> std::sync::MutexGuard<'static, ()> {
        SERIAL
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
    }

    /// Under this crate's own `target/` tree rather than `std::env::temp_dir()`
    /// (`/tmp`) or the shared `/workspace/scratchpad`: this sandbox's `/tmp`
    /// and `/workspace/scratchpad` are shared with, and periodically swept
    /// by, unrelated concurrent tooling (observed directly: parallel test
    /// runs intermittently lost freshly-written fixture files mid-test, and
    /// `/workspace/scratchpad` itself was observed to disappear between two
    /// otherwise-adjacent commands) — `target/` is this crate's own build
    /// output, touched only by `cargo` invocations against this workspace.
    fn test_scratch_root() -> PathBuf {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/gate_test_scratch");
        std::fs::create_dir_all(&root).expect("mkdir gate test scratch root");
        root
    }

    fn scratch_dir(label: &str) -> PathBuf {
        test_scratch_root().join(format!(
            "publish_gate_test_{label}_{}_{:?}",
            std::process::id(),
            std::thread::current().id()
        ))
    }

    /// Verbatim `cli::run`'s full `truth_relation_projection.parquet`
    /// header (base 9 columns + ruling-E18's 10 `CANDIDATE` extra columns +
    /// SELECT.1 L5 fix-batch's one additive `physical_event_id` column) —
    /// this module's tests build REAL fixtures of `cli::run`'s own leaf
    /// (module doc "Source-freedom"), never a second invented shape. This
    /// module never reads `physical_event_id`'s value (gate reconciliation
    /// has no use for it); it is present only so this test fixture's schema
    /// keeps matching the real leaf's column set, and every existing
    /// `trp_row`/`candidate_row` call defaults it to `"NA"` automatically
    /// (see [`trp_row`]'s own doc comment).
    const TEST_TRP_HEADER: [&str; 20] = [
        "day",
        "row_kind",
        "episode_id",
        "plateau_last_group_ordinal",
        "plateau_bar_ordinal",
        "plateau_end_ts_ns",
        "signal_id",
        "related_episode_ids",
        "relation_count",
        "stream_policy_name",
        "stream_reversal_bps",
        "candidate_id",
        "member_signal_ids",
        "registration_ordinal",
        "confirmation_group_ordinal",
        "visible_ts_ns",
        "visible_bar_ordinal",
        "session_end_ns",
        "event_scorable",
        "physical_event_id",
    ];

    /// Builds one row against [`TEST_TRP_HEADER`] by name (`"NA"` for every
    /// unnamed column) — avoids hand-counting `NA` columns per row kind.
    fn trp_row(pairs: &[(&str, String)]) -> Vec<String> {
        let mut row = vec!["NA".to_owned(); TEST_TRP_HEADER.len()];
        for (name, value) in pairs {
            let idx = TEST_TRP_HEADER
                .iter()
                .position(|column| column == name)
                .unwrap_or_else(|| panic!("unknown truth_relation_projection column `{name}`"));
            row[idx] = value.clone();
        }
        row
    }

    fn truth_row(
        day: &str,
        episode_byte: u8,
        plateau_group: u64,
        plateau_bar: i64,
        plateau_ns: i64,
    ) -> Vec<String> {
        trp_row(&[
            ("day", day.to_owned()),
            ("row_kind", "TRUTH".to_owned()),
            ("episode_id", hex32(&[episode_byte; 32])),
            ("plateau_last_group_ordinal", plateau_group.to_string()),
            ("plateau_bar_ordinal", plateau_bar.to_string()),
            ("plateau_end_ts_ns", plateau_ns.to_string()),
        ])
    }

    #[allow(
        clippy::too_many_arguments,
        reason = "one explicit fixture-building helper"
    )]
    fn candidate_row(
        day: &str,
        stream: &StreamId,
        candidate_byte: u8,
        registration_ordinal: u64,
        related: &[[u8; 32]],
        confirmation_group_ordinal: u64,
        visible_ts_ns: i64,
        visible_bar_ordinal: Option<u64>,
        session_end_ns: i64,
        event_scorable: bool,
    ) -> Vec<String> {
        let related_text = if related.is_empty() {
            "NA".to_owned()
        } else {
            related.iter().map(hex32).collect::<Vec<_>>().join(",")
        };
        trp_row(&[
            ("day", day.to_owned()),
            ("row_kind", "CANDIDATE".to_owned()),
            ("related_episode_ids", related_text),
            ("relation_count", related.len().to_string()),
            ("stream_policy_name", stream.policy_name().to_owned()),
            ("stream_reversal_bps", stream.reversal_bps_wire()),
            ("candidate_id", hex32(&[candidate_byte; 32])),
            ("registration_ordinal", registration_ordinal.to_string()),
            (
                "confirmation_group_ordinal",
                confirmation_group_ordinal.to_string(),
            ),
            ("visible_ts_ns", visible_ts_ns.to_string()),
            (
                "visible_bar_ordinal",
                visible_bar_ordinal.map_or_else(|| "NA".to_owned(), |v| v.to_string()),
            ),
            ("session_end_ns", session_end_ns.to_string()),
            ("event_scorable", event_scorable.to_string()),
        ])
    }

    /// Writes a real `truth_relation_projection.parquet` fixture (module
    /// doc "Source-freedom": this module's tests build the SAME leaf
    /// `cli::run` produces, never a second invented shape) — one row group
    /// per `(ordinal, day, rows)` entry in `sessions`, in ordinal order.
    fn write_truth_relation_projection_fixture(
        dir: &Path,
        sessions: &[(u32, &str, Vec<Vec<String>>)],
    ) {
        let schema: SchemaRef = Arc::new(Schema::new(
            TEST_TRP_HEADER
                .iter()
                .map(|name| Field::new(*name, DataType::Utf8, false))
                .collect::<Vec<_>>(),
        ));
        let mut writer = LeafWriter::create(dir, "truth_relation_projection", Arc::clone(&schema))
            .expect("create truth_relation_projection writer");
        for (ordinal, day, rows) in sessions {
            let ncols = schema.fields().len();
            let mut columns: Vec<Vec<&str>> =
                (0..ncols).map(|_| Vec::with_capacity(rows.len())).collect();
            for row in rows {
                for (column, value) in columns.iter_mut().zip(row) {
                    column.push(value.as_str());
                }
            }
            let arrays: Vec<arrow_array::ArrayRef> = columns
                .into_iter()
                .map(|column| Arc::new(StringArray::from(column)) as arrow_array::ArrayRef)
                .collect();
            let batch = RecordBatch::try_new(Arc::clone(&schema), arrays).expect("build batch");
            writer
                .write_session(*ordinal, day, &batch)
                .expect("write truth_relation_projection session");
        }
        let session_count = sessions.len() as u64;
        writer
            .finish(session_count)
            .expect("finish truth_relation_projection");
    }

    /// One small, fully hand-verified fixture: 2 sessions, 1 truth (session
    /// (2022,0)), one gate stream with a single timely hit on that truth,
    /// zero candidates in session (2022,1) (a genuine zero-event session,
    /// included per A1). Writes every gate leaf plus the `evaluation_registry.tsv`
    /// roster and `run_receipt.json` this module needs, and returns the
    /// directory.
    fn build_fixture(label: &str) -> PathBuf {
        let dir = scratch_dir(label);
        std::fs::create_dir_all(&dir).expect("mkdir fixture dir");

        // evaluation_registry.tsv: every E20-ratified constant column must
        // carry its real frozen value now (Sol#5 P0 fix validates all six).
        std::fs::write(
            dir.join(EVALUATION_REGISTRY_LEAF),
            format!(
                "{EVALUATION_REGISTRY_FULL_HEADER}\n\
                 0\t2022-01-03\t2022\t0\t{EVAL_BLOCK_SCHEME}\t{EVAL_TIE_RULE}\t\
                 {EVAL_MAX_TIMELY_DELAY_BARS}\t{FULL_CORPUS_TRUTH_DENOMINATOR}\t\
                 {EVAL_TRUTH_DENOMINATOR_20BPS}\t{EVAL_STREAM_IDENTITY_KEY}\n\
                 1\t2022-01-04\t2022\t1\t{EVAL_BLOCK_SCHEME}\t{EVAL_TIE_RULE}\t\
                 {EVAL_MAX_TIMELY_DELAY_BARS}\t{FULL_CORPUS_TRUTH_DENOMINATOR}\t\
                 {EVAL_TRUTH_DENOMINATOR_20BPS}\t{EVAL_STREAM_IDENTITY_KEY}\n"
            ),
        )
        .expect("write evaluation_registry.tsv");

        let gate_stream = StreamId::new("reversal_confirm", 40);
        write_truth_relation_projection_fixture(
            &dir,
            &[
                (
                    0,
                    "2022-01-03",
                    vec![
                        truth_row("2022-01-03", 0x01, 100, 10, 1_000),
                        candidate_row(
                            "2022-01-03",
                            &gate_stream,
                            0x02,
                            0,
                            &[[0x01; 32]],
                            101,
                            1_001,
                            Some(11),
                            1_000_000,
                            true,
                        ),
                    ],
                ),
                (1, "2022-01-04", Vec::new()),
            ],
        );

        let counts = CaptureCounts {
            confirmed_truths: 1,
            unique_timely_hits: 1,
            delay_1_hits: 1,
            ..CaptureCounts::default()
        };
        let gate_row = StreamSummaryRow {
            stream: gate_stream,
            is_gate: true,
            registration_order: 0,
            counts,
            ambiguity_count: 0,
            verdict: EstimatorVerdict {
                lcb_canonical: "PLACEHOLDER".to_owned(),
                passes_floor: false,
            },
            on_frontier: true,
        };
        write_stream_summary_leaf(&dir, std::slice::from_ref(&gate_row))
            .expect("write stream_summary.tsv");

        let session_recall = vec![
            SessionRecallRow {
                year: 2022,
                ordinal: 0,
                hits: 1,
                truths: 1,
            },
            SessionRecallRow {
                year: 2022,
                ordinal: 1,
                hits: 0,
                truths: 0,
            },
        ];
        write_session_recall_leaf(&dir, &session_recall).expect("write session_recall.tsv");

        let bank = ProposalBank {
            state: BankState::Insufficient {
                eligible_count: 0,
                frontier_count: 0,
                members: Vec::new(),
            },
            streams: Vec::new(),
            eligible_count: 0,
        };
        write_proposal_bank_leaf(&dir, &bank).expect("write proposal_bank.tsv");

        let receipt = RunReceipt::new("deadbeef", "a".repeat(64), vec!["stage1".to_owned()], 2);
        receipt.write_to(&dir).expect("write receipt");

        write_estimator_laws_fixture(&dir);
        write_sol2_fixture_leaves(
            &dir,
            &gate_row.stream,
            &[(0, "2022-01-03"), (1, "2022-01-04")],
            1,
        );

        dir
    }

    /// Builds a fixed-column all-`Utf8` schema (test-only convenience,
    /// mirrors `write_truth_relation_projection_fixture`'s own schema
    /// construction).
    fn utf8_schema(columns: &[&str]) -> SchemaRef {
        Arc::new(Schema::new(
            columns
                .iter()
                .map(|name| Field::new(*name, DataType::Utf8, false))
                .collect::<Vec<_>>(),
        ))
    }

    /// Builds one `RecordBatch` of all-`Utf8` columns from `rows` (each row
    /// a `Vec<String>` matching `schema`'s column order) — zero rows is a
    /// valid, well-formed empty batch.
    fn utf8_batch(schema: &SchemaRef, rows: &[Vec<String>]) -> RecordBatch {
        let ncols = schema.fields().len();
        let mut columns: Vec<Vec<&str>> =
            (0..ncols).map(|_| Vec::with_capacity(rows.len())).collect();
        for row in rows {
            for (column, value) in columns.iter_mut().zip(row) {
                column.push(value.as_str());
            }
        }
        let arrays: Vec<arrow_array::ArrayRef> = columns
            .into_iter()
            .map(|column| Arc::new(StringArray::from(column)) as arrow_array::ArrayRef)
            .collect();
        RecordBatch::try_new(Arc::clone(schema), arrays).expect("build batch")
    }

    /// TEST-ONLY: writes the minimal, valid, self-consistent Sol#2-required
    /// leaves every `StageGate::recompute` fixture now needs beyond the
    /// original five gate leaves: `regimes.parquet` (one bar per session, at
    /// `bar_ordinal` 0 — deliberately NOT any fixture truth's own
    /// `plateau_bar_ordinal`, so every truth honestly resolves as
    /// `no_regime_row`-unresolved rather than requiring a hand-verified
    /// regime-slice cell), a zero-row `event_index.parquet` plus all 11
    /// `labels_<family>.parquet` leaves (whose row-count/key-sample join
    /// smoke trivially agrees at zero rows per session), and the two
    /// per-stream diagnostic leaves whose content does NOT depend on the
    /// pinned estimator's real verdict (`metrics_regime_slice.tsv`,
    /// `metrics_regime_unresolved.tsv` — `total_truth_count` is the
    /// fixture's total pooled truth count, every one of which is
    /// unresolved by construction). [`fix_up_gate_verdict`] separately
    /// writes the leaves whose content DOES depend on the real verdict/bank
    /// (`metrics_frontier.tsv`, `metrics_bank.tsv`,
    /// `metrics_estimator_verdicts.tsv`).
    fn write_sol2_fixture_leaves(
        dir: &Path,
        stream: &StreamId,
        sessions: &[(u32, &str)],
        total_truth_count: u64,
    ) {
        let regime_columns = [
            "day",
            "bar_ordinal",
            "rv_sum_sq_15_state",
            "rv_sum_sq_15",
            "rv_count_15",
            "band_u6_30_state",
            "band_u6_30",
            "net_move_u6_30_state",
            "net_move_u6_30",
            "early_close",
        ];
        let regime_schema = utf8_schema(&regime_columns);
        let mut regime_writer = LeafWriter::create(dir, "regimes", Arc::clone(&regime_schema))
            .expect("create regimes writer");
        for (ordinal, day) in sessions {
            let row = vec![
                (*day).to_owned(),
                "0".to_owned(),
                "OK".to_owned(),
                "100".to_owned(),
                "5".to_owned(),
                "OK".to_owned(),
                "50".to_owned(),
                "OK".to_owned(),
                "10".to_owned(),
                "false".to_owned(),
            ];
            let batch = utf8_batch(&regime_schema, std::slice::from_ref(&row));
            regime_writer
                .write_session(*ordinal, day, &batch)
                .expect("write regimes session");
        }
        regime_writer
            .finish(sessions.len() as u64)
            .expect("finish regimes");

        let common_prefix_columns = [
            "day",
            "signal_id",
            "slot",
            "seed_bar_ordinal",
            "cutoff_ts_ns",
            "slot_available",
            "visible_at_slot",
            "window_left",
            "window_end",
            "window_frontier",
        ];
        let common_schema = utf8_schema(&common_prefix_columns);
        let mut leaf_stems = vec!["event_index".to_owned()];
        leaf_stems.extend(
            FAMILY_LEAF_STEMS
                .iter()
                .map(|stem| format!("labels_{stem}")),
        );
        for leaf_stem in &leaf_stems {
            let mut writer = LeafWriter::create(dir, leaf_stem, Arc::clone(&common_schema))
                .unwrap_or_else(|error| panic!("create {leaf_stem} writer: {error:?}"));
            for (ordinal, day) in sessions {
                let batch = utf8_batch(&common_schema, &[]);
                writer
                    .write_session(*ordinal, day, &batch)
                    .unwrap_or_else(|error| panic!("write {leaf_stem} session: {error:?}"));
            }
            writer
                .finish(sessions.len() as u64)
                .unwrap_or_else(|error| panic!("finish {leaf_stem}: {error:?}"));
        }

        let mut regime_slice_text = String::from(METRICS_REGIME_SLICE_HEADER);
        regime_slice_text.push('\n');
        for vol_tercile in Tercile::ALL {
            for trend_range in TrendRangeState::ALL {
                for session_type in SessionType::ALL {
                    writeln!(
                        regime_slice_text,
                        "{}\t{}\t{}\t{}\t{}\t0\t0\tNO_SUPPORT",
                        stream.policy_name(),
                        stream.reversal_bps_wire(),
                        vol_tercile.wire(),
                        trend_range.wire(),
                        session_type.wire(),
                    )
                    .expect("writing to a String cannot fail");
                }
            }
        }
        std::fs::write(dir.join(METRICS_REGIME_SLICE_LEAF), regime_slice_text)
            .expect("write metrics_regime_slice.tsv");

        let regime_unresolved_text = format!(
            "{METRICS_REGIME_UNRESOLVED_HEADER}\n{}\t{}\t{total_truth_count}\t0\t0\t0\t\
             {total_truth_count}\n",
            stream.policy_name(),
            stream.reversal_bps_wire(),
        );
        std::fs::write(
            dir.join(METRICS_REGIME_UNRESOLVED_LEAF),
            regime_unresolved_text,
        )
        .expect("write metrics_regime_unresolved.tsv");
    }

    /// TEST-ONLY: seeds `dir/estimator_laws.py` with the real, sha-verified
    /// pinned estimator content, mirroring what a real `stage1 run`
    /// publishes as a declared leaf (ruling E21e) — every fixture
    /// `StageGate::recompute`/`invoke_estimator` runs against needs one,
    /// since [`StageGate::invoke_estimator`] resolves ONLY this in-directory
    /// copy, never an external path (module doc "Source-freedom"). The
    /// source bytes embedded here are test scaffolding only — production code
    /// (`StageGate`) never reads an external source path.
    fn write_estimator_laws_fixture(dir: &Path) {
        const TEST_ESTIMATOR_SOURCE: &[u8] =
            include_bytes!("../tests/fixtures/estimator_laws.py");
        let target = dir.join(ESTIMATOR_LAWS_LEAF_NAME);
        std::fs::write(&target, TEST_ESTIMATOR_SOURCE)
            .expect("write bundled estimator_laws.py fixture into dir");
        let (_, sha256) = hash_file_bytes(&target)
            .expect("hash the bundled estimator source for test fixture setup");
        assert_eq!(
            hex32(&sha256),
            ESTIMATOR_LAWS_SHA256,
            "test fixture source must match the pinned sha256"
        );
    }

    /// Re-invokes the pinned estimator directly (bypassing `StageGate`) to
    /// learn the REAL `EstimatorVerdict` for `session_recall.tsv` inside
    /// `dir`, and rewrites the fixture's `stream_summary.tsv` gate row to
    /// carry it — every positive test needs this, since the placeholder
    /// verdict `build_fixture` writes is deliberately wrong (it is
    /// overwritten by whichever test needs a passing estimator check).
    /// Rewrites the fixture's gate row with the REAL pinned-estimator
    /// verdict (the placeholder `build_fixture` writes is deliberately
    /// wrong), then recomputes `on_frontier` and the actual
    /// `proposal_bank.tsv` from the now-correct `stream_summary.tsv` rows
    /// via the same `metrics::frontier`/`metrics::bank` functions
    /// `StageGate` itself uses — every positive test needs this, since a
    /// hand-written placeholder bank would otherwise disagree with the real
    /// recomputation.
    #[allow(
        clippy::too_many_lines,
        reason = "one linear test-fixture-setup pass (rewrite the verdict, then every leaf that \
                  depends on it); splitting further would scatter fixtures that must stay \
                  mutually consistent"
    )]
    fn fix_up_gate_verdict(dir: &Path) {
        let gate = StageGate::production();
        let verdict = gate
            .invoke_estimator(dir, &dir.join(SESSION_RECALL_LEAF))
            .expect("invoke real estimator for fixture setup");
        let mut rows = read_stream_summary_leaf(dir).expect("read stream_summary.tsv");
        for row in &mut rows {
            if row.is_gate {
                row.verdict = verdict.clone();
            }
        }

        let counts_by_stream: BTreeMap<StreamId, CaptureCounts> = rows
            .iter()
            .map(|row| (row.stream.clone(), row.counts))
            .collect();
        let points = build_stream_points(&rows, &counts_by_stream);
        let frontier = non_dominated(&points);
        let frontier_streams: std::collections::BTreeSet<StreamId> =
            frontier.iter().map(|point| point.stream.clone()).collect();
        for (row, point) in rows.iter_mut().zip(points.iter()) {
            row.on_frontier = frontier_streams.contains(&point.stream);
        }
        write_stream_summary_leaf(dir, &rows).expect("rewrite stream_summary.tsv");

        let candidates: Vec<StreamLcb> = points
            .iter()
            .zip(rows.iter())
            .map(|(point, row)| StreamLcb {
                point: point.clone(),
                verdict: row.verdict.clone(),
            })
            .collect();
        let bank = build_bank(&candidates).expect("build_bank for fixture setup");
        write_proposal_bank_leaf(dir, &bank).expect("rewrite proposal_bank.tsv");

        // Sol#2: the diagnostic leaves whose content DOES depend on the
        // real verdict/bank -- write them here, now that both are known,
        // matching what `cli::metrics_cmd::run_metrics_inner` would have
        // published from the SAME `points`/`bank` values.
        let mut frontier_text = String::from(METRICS_FRONTIER_HEADER);
        frontier_text.push('\n');
        for point in &points {
            writeln!(
                frontier_text,
                "{}\t{}\t{}\t{}\t{}\t{}\t{}",
                point.stream.policy_name(),
                point.stream.reversal_bps_wire(),
                point.hits,
                point.truths_denominator,
                point.burden,
                point.registration_order,
                frontier_streams.contains(&point.stream),
            )
            .expect("writing to a String cannot fail");
        }
        std::fs::write(dir.join(METRICS_FRONTIER_LEAF), frontier_text)
            .expect("write metrics_frontier.tsv");

        let (bank_state_wire, bank_eligible, bank_frontier) = match &bank.state {
            BankState::Selected => ("SELECTED", bank.eligible_count, bank.streams.len()),
            BankState::Insufficient {
                eligible_count,
                frontier_count,
                ..
            } => ("BANK_INSUFFICIENT", *eligible_count, *frontier_count),
        };
        let mut bank_text = String::from(METRICS_BANK_HEADER);
        bank_text.push('\n');
        if bank.streams.is_empty() {
            writeln!(
                bank_text,
                "{bank_state_wire}\t{bank_eligible}\t{bank_frontier}\tNA\tNA\tNA\tNA\tNA\tNA"
            )
            .expect("writing to a String cannot fail");
        } else {
            for point in &bank.streams {
                writeln!(
                    bank_text,
                    "{bank_state_wire}\t{bank_eligible}\t{bank_frontier}\t{}\t{}\t{}\t{}\t{}\t{}",
                    point.stream.policy_name(),
                    point.stream.reversal_bps_wire(),
                    point.hits,
                    point.truths_denominator,
                    point.burden,
                    point.registration_order,
                )
                .expect("writing to a String cannot fail");
            }
        }
        std::fs::write(dir.join(METRICS_BANK_LEAF), bank_text).expect("write metrics_bank.tsv");

        let mut estimator_verdicts_text = String::from(METRICS_ESTIMATOR_VERDICTS_HEADER);
        estimator_verdicts_text.push('\n');
        for row in &rows {
            writeln!(
                estimator_verdicts_text,
                "{}\t{}\t{}\t{}\ttest-fixture-path\t{}",
                row.stream.policy_name(),
                row.stream.reversal_bps_wire(),
                row.verdict.lcb_canonical,
                row.verdict.passes_floor,
                "0".repeat(64),
            )
            .expect("writing to a String cannot fail");
        }
        std::fs::write(
            dir.join(METRICS_ESTIMATOR_VERDICTS_LEAF),
            estimator_verdicts_text,
        )
        .expect("write metrics_estimator_verdicts.tsv");
    }

    #[test]
    fn a_correct_fixture_passes_recompute() {
        // A single-stream fixture can never reach genuine E21 terminal
        // ACCEPT (E21b requires a >=3-member SELECTED bank; E21d requires
        // the full 1,003-session calendar) -- but every reproducibility
        // check ("verifies") must still pass cleanly first, so the ONLY
        // error `recompute` can return here is the terminal-acceptance
        // one, never a leaf-mismatch (Sol#4 P0 fix's "separate diagnostic
        // reproduction from terminal acceptance").
        let _guard = serial_guard();
        let dir = build_fixture("happy_path");
        fix_up_gate_verdict(&dir);

        let gate = StageGate::production();
        let error = gate
            .recompute(&dir)
            .expect_err("a 2-session, single-stream fixture can never reach full EVENTS accept");
        assert!(matches!(error, PublishError::GateMismatch { .. }));
        assert!(
            error.to_string().contains("EVENTS terminal acceptance"),
            "a correctly-built fixture must fail ONLY at the terminal-acceptance phase, never at \
             an earlier reproducibility check: {error}"
        );

        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn a_tampered_recall_row_is_caught() {
        let _guard = serial_guard();
        let dir = build_fixture("tampered_recall_row");
        fix_up_gate_verdict(&dir);

        // Flip session (2022, 0)'s published hits from 1 to 0: the
        // independent recomputation (from capture_truths/capture_candidates)
        // still says 1, so this must be caught.
        std::fs::write(
            dir.join(SESSION_RECALL_LEAF),
            "year\tordinal\thits\ttruths\n2022\t0\t0\t1\n2022\t1\t0\t0\n",
        )
        .expect("tamper session_recall.tsv");

        let gate = StageGate::production();
        let error = gate
            .recompute(&dir)
            .expect_err("a tampered recall row must be caught");
        assert!(matches!(error, PublishError::GateMismatch { .. }));
        let message = error.to_string();
        assert!(
            message.contains(SESSION_RECALL_LEAF),
            "error should name the offending leaf: {message}"
        );

        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn a_1002_row_table_short_of_the_roster_is_caught() {
        // The fixture's roster has 2 sessions; dropping one row here plays
        // the same role a 1,002-row table would at full scale (missing
        // exactly one registered session).
        let _guard = serial_guard();
        let dir = build_fixture("short_table");
        fix_up_gate_verdict(&dir);

        std::fs::write(
            dir.join(SESSION_RECALL_LEAF),
            "year\tordinal\thits\ttruths\n2022\t0\t1\t1\n",
        )
        .expect("write a session_recall.tsv short one row");

        let gate = StageGate::production();
        let error = gate
            .recompute(&dir)
            .expect_err("a session_recall.tsv missing a registered session must be caught");
        assert!(matches!(error, PublishError::GateMismatch { .. }));

        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn a_fabricated_bank_is_caught() {
        let _guard = serial_guard();
        let dir = build_fixture("fabricated_bank");
        fix_up_gate_verdict(&dir);

        // The only stream (the gate stream) has recall 1/1 = 1.0 and burden
        // 0; whatever its real passes_floor turns out to be, a bank
        // claiming BankState::Selected with a fabricated member disagrees
        // with metrics::bank::build_bank's own single-candidate-can-never-
        // reach-Selected arithmetic (Selected requires a >=3-member
        // frontier) -- so this published bank can never be reproduced.
        let fabricated = ProposalBank {
            state: BankState::Selected,
            streams: vec![StreamPoint {
                stream: StreamId::new("reversal_confirm", 40),
                hits: 1,
                truths_denominator: 1,
                burden: 0,
                registration_order: 0,
            }],
            eligible_count: 1,
        };
        write_proposal_bank_leaf(&dir, &fabricated).expect("write a fabricated bank");

        let gate = StageGate::production();
        let error = gate
            .recompute(&dir)
            .expect_err("a fabricated bank selection must be caught");
        assert!(matches!(error, PublishError::GateMismatch { .. }));
        let message = error.to_string();
        assert!(
            message.contains(PROPOSAL_BANK_LEAF),
            "error should name the offending leaf: {message}"
        );

        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn a_manifest_omitting_session_recall_is_rejected_by_verify_publication() {
        use crate::manifest::ManifestBuilder;
        use crate::receipt::RECEIPT_LEAF_NAME;
        use crate::verify::verify_publication;

        let _guard = serial_guard();
        let final_dir = scratch_dir("manifest_omits_session_recall_final");
        let staging = PublishStaging::begin(&final_dir).expect("begin staging");
        let staging_dir = staging.dir().to_path_buf();

        // Build the same fixture leaves directly into the staging dir, but
        // never register session_recall.tsv with the manifest (nor write
        // it) -- a writer that silently drops the A1 leaf.
        std::fs::write(
            staging_dir.join(EVALUATION_REGISTRY_LEAF),
            "ordinal\tday\tyear\twithin_year_ordinal\tblock_scheme\ttie_rule\t\
             max_timely_delay_bars\ttruth_denominator_40bps\ttruth_denominator_20bps\t\
             stream_identity_key\n0\t2022-01-03\t2022\t0\tscheme\ttie\t2\t8914\t34325\tkey\n",
        )
        .expect("write evaluation_registry.tsv");
        let eval_bytes = std::fs::read(staging_dir.join(EVALUATION_REGISTRY_LEAF)).expect("read");
        let eval_record = LeafRecord {
            name: EVALUATION_REGISTRY_LEAF.to_owned(),
            rows: 1,
            bytes: eval_bytes.len() as u64,
            sha256: {
                use sha2::{Digest as _, Sha256};
                Sha256::digest(&eval_bytes).into()
            },
        };

        let stream_summary_record =
            write_stream_summary_leaf(&staging_dir, &[]).expect("write stream_summary.tsv");
        let bank_record = write_proposal_bank_leaf(
            &staging_dir,
            &ProposalBank {
                state: BankState::Insufficient {
                    eligible_count: 0,
                    frontier_count: 0,
                    members: Vec::new(),
                },
                streams: Vec::new(),
                eligible_count: 0,
            },
        )
        .expect("write proposal_bank.tsv");

        let receipt = RunReceipt::new("deadbeef", "a".repeat(64), vec!["stage1".to_owned()], 1);
        receipt.write_to(&staging_dir).expect("write receipt");

        let mut manifest = ManifestBuilder::new();
        manifest.push(eval_record);
        manifest.push(stream_summary_record);
        manifest.push(bank_record);
        manifest.push(receipt.leaf_record());
        // session_recall.tsv deliberately never written or registered.
        manifest.write(&staging_dir).expect("write manifest");

        let published = staging.commit().expect("commit");

        let mut required: std::collections::BTreeSet<String> = required_leaf_names()
            .into_iter()
            .map(str::to_owned)
            .collect();
        required.insert(EVALUATION_REGISTRY_LEAF.to_owned());
        required.insert(RECEIPT_LEAF_NAME.to_owned());

        let gate = StageGate::production();
        let error = verify_publication(&published, &required, 1, Some(&gate))
            .expect_err("a manifest omitting session_recall.tsv must be rejected");
        match error {
            PublishError::RequiredLeafSetMismatch { missing, .. } => {
                assert!(missing.contains(&SESSION_RECALL_LEAF.to_owned()));
            }
            other => panic!("expected RequiredLeafSetMismatch, got {other:?}"),
        }

        std::fs::remove_dir_all(published.parent().expect("parent")).ok();
    }

    #[test]
    fn external_read_absent_the_gate_still_verifies_from_dir_alone() {
        // Mirrors `verify.rs`'s own `verify_publication_never_needs_anything_outside_dir`
        // test: move the whole fixture (including its in-directory
        // `estimator_laws.py` copy) to a disconnected scratch location,
        // proving no coupling to its original build path, to any external
        // corpus/event-publication path, OR to the archive path the pinned
        // estimator source used to be read from at verify time (ruling
        // E21e; closes Sol#7 P1 and Opus#P3-2) -- `StageGate` has no code
        // path left that could read outside `dir`.
        let _guard = serial_guard();
        let dir = build_fixture("external_read_absent");
        fix_up_gate_verdict(&dir);

        let moved_parent = test_scratch_root().join(format!(
            "publish_gate_test_moved_{}_{:?}",
            std::process::id(),
            std::thread::current().id()
        ));
        std::fs::create_dir_all(&moved_parent).expect("mkdir moved parent");
        let moved = moved_parent.join("gate_fixture");
        std::fs::rename(&dir, &moved).expect("move fixture");

        let gate = StageGate::production();
        let error = gate
            .recompute(&moved)
            .expect_err("a 2-session, single-stream fixture can never reach full EVENTS accept");
        // The point of this test is source-freedom, not terminal
        // acceptance: the failure must be the (expected, small-fixture)
        // terminal-acceptance shortfall, never an I/O error caused by
        // reading something at the fixture's OLD, now-nonexistent path.
        assert!(
            error.to_string().contains("EVENTS terminal acceptance"),
            "recompute must reproduce every leaf purely from the moved dir's own leaves and fail \
             only at terminal acceptance: {error}"
        );

        std::fs::remove_dir_all(&moved_parent).ok();
    }

    #[test]
    fn a_tampered_in_dir_estimator_law_file_is_rejected_before_invocation() {
        let _guard = serial_guard();
        let dir = build_fixture("tampered_estimator_sha");
        // Deliberately do NOT fix up the verdict: a tampered in-directory
        // estimator copy must fail on the sha check before ever getting to
        // the verdict comparison.

        // Overwrite the real copy `build_fixture` seeded with a tampered
        // stand-in AT THE SAME declared-leaf path -- `StageGate` (ruling
        // E21e) resolves ONLY `dir.join(ESTIMATOR_LAWS_LEAF_NAME)`, never a
        // caller-supplied path, so this is the only way to exercise the
        // sha-verification failure path now.
        std::fs::write(
            dir.join(ESTIMATOR_LAWS_LEAF_NAME),
            b"print('not the pinned estimator')\n",
        )
        .expect("tamper the in-directory estimator_laws.py copy");

        let gate = StageGate::production();
        let error = gate
            .recompute(&dir)
            .expect_err("a tampered in-directory estimator_laws.py must be rejected by its sha256");
        assert!(matches!(error, PublishError::GateMismatch { .. }));
        assert!(error.to_string().contains("sha256"));

        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn zero_event_and_zero_truth_sessions_are_included_not_dropped() {
        // Session (2022, 1) in `build_fixture` has zero truths and zero
        // candidates for any stream; the happy-path test already asserts
        // the whole recompute succeeds with that session present as an
        // explicit (hits=0, truths=0) row -- this test asserts it
        // specifically, directly against the recomputed row set.
        let _guard = serial_guard();
        let dir = build_fixture("zero_event_session");
        fix_up_gate_verdict(&dir);

        let eval_rows = read_evaluation_registry(&dir).expect("read evaluation_registry.tsv");
        let roster: Vec<SessionId> = eval_rows.iter().map(|row| row.session).collect();
        assert_eq!(roster.len(), 2);
        let truths = read_truth_relation_projection(&dir, &eval_rows).expect("read truths");
        let mut truths_by_session: BTreeMap<SessionId, Vec<TruthRow>> = BTreeMap::new();
        for t in &truths {
            truths_by_session.entry(t.session).or_default().push(*t);
        }
        let mut totals: HashMap<SessionId, u64> = HashMap::new();
        for &s in &roster {
            totals.insert(s, truths_by_session.get(&s).map_or(0, Vec::len) as u64);
        }
        let hits: HashMap<SessionId, u64> = HashMap::new();
        let rows = session_recall_rows(&roster, &totals, &hits).expect("rows");
        assert_eq!(rows.len(), 2);
        assert_eq!(rows[1].hits, 0);
        assert_eq!(rows[1].truths, 0);

        std::fs::remove_dir_all(&dir).ok();
    }

    // ---- Sol#3/#4/#5 P0 + Opus#P3-1 + E21: one dedicated test per finding
    // (task requirement: "Tests per finding incl. Sol#3's omitted-stream
    // scenario, Sol#4's sub-floor-PASS scenario (must now FAIL), Sol#5's
    // relabeled-roster scenario."). ----

    #[test]
    fn a_stream_omitted_from_stream_summary_is_caught() {
        // Sol#3 P0: the projection's own CANDIDATE rows name TWO distinct
        // streams for the same session, but `stream_summary.tsv` publishes
        // only one of them -- the candidate stream universe must be
        // discovered from the projection, never trusted as "whatever
        // stream_summary.tsv happened to list."
        let _guard = serial_guard();
        let dir = scratch_dir("omitted_stream");
        std::fs::create_dir_all(&dir).expect("mkdir fixture dir");

        std::fs::write(
            dir.join(EVALUATION_REGISTRY_LEAF),
            format!(
                "{EVALUATION_REGISTRY_FULL_HEADER}\n\
                 0\t2022-01-03\t2022\t0\t{EVAL_BLOCK_SCHEME}\t{EVAL_TIE_RULE}\t\
                 {EVAL_MAX_TIMELY_DELAY_BARS}\t{FULL_CORPUS_TRUTH_DENOMINATOR}\t\
                 {EVAL_TRUTH_DENOMINATOR_20BPS}\t{EVAL_STREAM_IDENTITY_KEY}\n"
            ),
        )
        .expect("write evaluation_registry.tsv");

        let stream_a = StreamId::new("reversal_confirm", 40);
        let stream_b = StreamId::new("union_confirm", 40);
        write_truth_relation_projection_fixture(
            &dir,
            &[(
                0,
                "2022-01-03",
                vec![
                    candidate_row(
                        "2022-01-03",
                        &stream_a,
                        0x01,
                        0,
                        &[],
                        11,
                        100,
                        Some(1),
                        1_000,
                        true,
                    ),
                    candidate_row(
                        "2022-01-03",
                        &stream_b,
                        0x02,
                        0,
                        &[],
                        12,
                        100,
                        Some(1),
                        1_000,
                        true,
                    ),
                ],
            )],
        );

        // stream_summary.tsv omits stream_b entirely.
        let published = StreamSummaryRow {
            stream: stream_a,
            is_gate: true,
            registration_order: 0,
            counts: CaptureCounts::default(),
            ambiguity_count: 0,
            verdict: EstimatorVerdict {
                lcb_canonical: "0".to_owned(),
                passes_floor: false,
            },
            on_frontier: false,
        };
        write_stream_summary_leaf(&dir, std::slice::from_ref(&published))
            .expect("write stream_summary.tsv");

        let receipt = RunReceipt::new("deadbeef", "a".repeat(64), vec!["stage1".to_owned()], 1);
        receipt.write_to(&dir).expect("write receipt");

        let gate = StageGate::production();
        let error = gate
            .recompute(&dir)
            .expect_err("a stream omitted from stream_summary.tsv must be caught");
        assert!(matches!(error, PublishError::GateMismatch { .. }));
        let message = error.to_string();
        assert!(
            message.contains(STREAM_SUMMARY_LEAF),
            "error should name the offending leaf: {message}"
        );
        assert!(
            message.contains("union_confirm"),
            "error should name the omitted stream: {message}"
        );

        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn a_sub_floor_recall_stream_now_fails_terminal_acceptance() {
        // Sol#4 P0 (+ Opus#P3-1 + E21a/c): a stream with 0 hits / 1 truth
        // (0% recall, far below the frozen 80% floor) used to be able to
        // reach a `[PASS] verify-stage1` as long as its OWN
        // `session_recall.tsv`/`stream_summary.tsv` reproduced internally
        // -- terminal acceptance now requires at least one floor-eligible
        // stream (E21a) and requires the published `is_gate` flag to
        // actually name the registered best-eligible stream (E21c /
        // Opus#P3-1), never trusted on its own. This publication is
        // otherwise fully self-consistent (every reproducibility check
        // above the terminal-acceptance phase passes) and must still be
        // rejected.
        let _guard = serial_guard();
        let dir = scratch_dir("sub_floor_recall");
        std::fs::create_dir_all(&dir).expect("mkdir fixture dir");

        std::fs::write(
            dir.join(EVALUATION_REGISTRY_LEAF),
            format!(
                "{EVALUATION_REGISTRY_FULL_HEADER}\n\
                 0\t2022-01-03\t2022\t0\t{EVAL_BLOCK_SCHEME}\t{EVAL_TIE_RULE}\t\
                 {EVAL_MAX_TIMELY_DELAY_BARS}\t{FULL_CORPUS_TRUTH_DENOMINATOR}\t\
                 {EVAL_TRUTH_DENOMINATOR_20BPS}\t{EVAL_STREAM_IDENTITY_KEY}\n"
            ),
        )
        .expect("write evaluation_registry.tsv");

        let stream = StreamId::new("reversal_confirm", 40);
        // Two truths: episode 1 is captured by the sole candidate (a
        // timely hit, identical mechanics to `build_fixture`'s own
        // verified single-hit case); episode 2 has NO relating candidate
        // at all (an honest `miss_no_exact_relation`). Recall = 1/2 = 50%,
        // clearly below the frozen 80% floor -- and the stream is still
        // genuinely discoverable from the projection's own CANDIDATE rows
        // (Sol#3), unlike a zero-candidate fixture would be.
        write_truth_relation_projection_fixture(
            &dir,
            &[(
                0,
                "2022-01-03",
                vec![
                    truth_row("2022-01-03", 0x01, 100, 10, 1_000),
                    truth_row("2022-01-03", 0x02, 200, 10, 1_000),
                    candidate_row(
                        "2022-01-03",
                        &stream,
                        0x03,
                        0,
                        &[[0x01; 32]],
                        101,
                        1_001,
                        Some(11),
                        1_000_000,
                        true,
                    ),
                ],
            )],
        );

        let counts = CaptureCounts {
            confirmed_truths: 2,
            unique_timely_hits: 1,
            delay_1_hits: 1,
            miss_no_exact_relation: 1,
            ..CaptureCounts::default()
        };
        let gate_row = StreamSummaryRow {
            stream: stream.clone(),
            is_gate: true,
            registration_order: 0,
            counts,
            ambiguity_count: 0,
            verdict: EstimatorVerdict {
                lcb_canonical: "PLACEHOLDER".to_owned(),
                passes_floor: false,
            },
            on_frontier: true,
        };
        write_stream_summary_leaf(&dir, std::slice::from_ref(&gate_row))
            .expect("write stream_summary.tsv");

        let session_recall = vec![SessionRecallRow {
            year: 2022,
            ordinal: 0,
            hits: 1,
            truths: 2,
        }];
        write_session_recall_leaf(&dir, &session_recall).expect("write session_recall.tsv");

        let bank = ProposalBank {
            state: BankState::Insufficient {
                eligible_count: 0,
                frontier_count: 0,
                members: Vec::new(),
            },
            streams: Vec::new(),
            eligible_count: 0,
        };
        write_proposal_bank_leaf(&dir, &bank).expect("write proposal_bank.tsv");

        let receipt = RunReceipt::new("deadbeef", "a".repeat(64), vec!["stage1".to_owned()], 1);
        receipt.write_to(&dir).expect("write receipt");

        write_estimator_laws_fixture(&dir);
        write_sol2_fixture_leaves(&dir, &stream, &[(0, "2022-01-03")], 2);

        // Recall alone (1/2 = 50%) already fails A9's
        // `5*hits >= 4*truths_denominator` floor regardless of the real
        // pinned estimator's `passes_floor` arithmetic, so this fixture's
        // sub-floor-ness does not depend on the estimator's real output --
        // `fix_up_gate_verdict` is still needed so the (mandatory)
        // sha-verified re-invocation cross-check agrees with the published
        // verdict.
        fix_up_gate_verdict(&dir);

        let gate = StageGate::production();
        let error = gate
            .recompute(&dir)
            .expect_err("a sub-floor-recall stream must now fail terminal acceptance");
        assert!(matches!(error, PublishError::GateMismatch { .. }));
        assert!(
            error.to_string().contains("EVENTS terminal acceptance"),
            "must fail specifically at terminal acceptance, never an earlier reproducibility \
             check: {error}"
        );

        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn a_relabeled_full_roster_is_caught() {
        // Sol#5 P0 (+ E21d): a full 1,003-session `evaluation_registry.tsv`
        // whose day -> (year, within_year_ordinal) mapping has been
        // relabeled relative to the frozen development calendar -- every
        // row is still internally well-formed (unique day, unique
        // SessionId, dense run ordinal, every E20 constant column correct),
        // so only an exact comparison against the compiled-in frozen
        // calendar (never a bare row/truth count) can catch this.
        let _guard = serial_guard();
        let dir = scratch_dir("relabeled_full_roster");
        std::fs::create_dir_all(&dir).expect("mkdir fixture dir");

        let sessions = corpus::all_sessions();
        let mut counts: BTreeMap<u16, u32> = BTreeMap::new();
        let mut assigned: Vec<(String, u16, u32)> = Vec::with_capacity(sessions.len());
        for entry in sessions {
            let year: u16 = entry.day[..4]
                .parse()
                .expect("registered day starts with a 4-digit year");
            let counter = counts.entry(year).or_insert(0);
            assigned.push((entry.day.to_owned(), year, *counter));
            *counter += 1;
        }
        // Relabel row 1 to row 0's year with a clearly-wrong ordinal: still
        // unique (no internal collision), still dense-ordinal, but wrong
        // relative to the frozen calendar.
        assigned[1].1 = assigned[0].1;
        assigned[1].2 = 999_999;

        let mut text = String::from(EVALUATION_REGISTRY_FULL_HEADER);
        text.push('\n');
        for (ordinal, (day, year, within_year_ordinal)) in assigned.iter().enumerate() {
            writeln!(
                text,
                "{ordinal}\t{day}\t{year}\t{within_year_ordinal}\t{EVAL_BLOCK_SCHEME}\t\
                 {EVAL_TIE_RULE}\t{EVAL_MAX_TIMELY_DELAY_BARS}\t{FULL_CORPUS_TRUTH_DENOMINATOR}\t\
                 {EVAL_TRUTH_DENOMINATOR_20BPS}\t{EVAL_STREAM_IDENTITY_KEY}"
            )
            .expect("writing to a String cannot fail");
        }
        std::fs::write(dir.join(EVALUATION_REGISTRY_LEAF), text)
            .expect("write evaluation_registry.tsv");

        let receipt = RunReceipt::new(
            "deadbeef",
            "a".repeat(64),
            vec!["stage1".to_owned()],
            sessions.len() as u64,
        );
        receipt.write_to(&dir).expect("write receipt");

        let gate = StageGate::production();
        let error = gate
            .recompute(&dir)
            .expect_err("a relabeled full-corpus roster must be caught");
        assert!(matches!(error, PublishError::GateMismatch { .. }));
        let message = error.to_string();
        assert!(
            message.contains(EVALUATION_REGISTRY_LEAF),
            "error should name the offending leaf: {message}"
        );

        std::fs::remove_dir_all(&dir).ok();
    }
}
