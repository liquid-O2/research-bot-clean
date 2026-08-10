//! Probe CLI input writers: per-day `day_meta.tsv`/`day_signals.tsv`/
//! `day_groups.tsv` (design authority: `docs/specs/label_probe_schema_v1.md`
//! "Probe invocation", items 1-3), the truth-relation dumps `day_truths.tsv`/
//! `day_truth_relations.tsv` (amendment §A3/§A10, ruling E10 — see
//! [`resolve_truth_rows`] and [`build_truth_relation_day`]),
//! [`parse_seeds`] (turns a day's verbatim `event_signals.tsv` line slice
//! into the [`crate::anchor::SignalSeed`]s the label kernels consume), and
//! [`write_family_files`] (wires those seeds — plus the `RankSeed`/`DirSeed`
//! extensions and the truth-relation day — into every EVENTS.2 + EVENTS.3
//! label-family `write_tsv` function, plus `regimes.tsv`).

use crate::anchor::{Side, SignalSeed};
use crate::f_prox::{EpisodeProjection, SignalRelation, TruthRelationDay};
use crate::frame::SessionFrame;
use corpus::{QuoteKind, SessionData};
use std::collections::HashMap;
use std::fmt::Write as _;
use std::fs::File;
use std::io::{self, BufWriter, Write};
use std::path::Path;

/// Registered nanoseconds-per-minute bar duration (CONV §3). Duplicated
/// locally: every other module in this crate keeps its own copy rather than
/// exposing `anchor.rs`'s private constant.
const NANOSECONDS_PER_BAR: i64 = 60_000_000_000;

/// The registered 40-column `event_signals.tsv` header
/// (`registered_conventions_extract_v1.md` §4), verbatim. `day_signals.tsv`
/// carries this exact header (`label_probe_schema_v1.md` item 2:
/// "identical 40-column header").
const EVENT_SIGNALS_HEADER: &str = "ordinal\tday\tsignal_id\tphysical_event_id\tpolicy_id\tpolicy_name\treversal_bps\tcausal_run_prefix_root\tcontinuity_ordinal\textreme_side\tpivot_price_u6\tpivot_evidence_root\tpivot_fragment_count\tpivot_fragments\tpivot_first_ts_ns\tpivot_last_ts_ns\tpivot_last_bar_ordinal\tconfirmation_state_position\tconfirmation_group_ordinal\tconfirmation_ts_ns\tcausal_visible_ts_ns\tconfirmation_bar_ordinal\tcausal_visible_bar_ordinal\tpivot_retouch_order_uncertain\torigin_to_visible_delay_bars_min\torigin_to_visible_delay_bars_max\tlatency_from_pivot_ns_min\tlatency_from_pivot_ns_max\tlatency_from_pivot_groups_min\tlatency_from_pivot_groups_max\tthreshold_level_u6\tconfirmation_price_low_u6\tconfirmation_price_high_u6\tconfirmation_crossing_count\tconfirmation_crossing_set_root\tconfirmation_group_root\tovershoot_low_u6\tovershoot_high_u6\tconfirmation_kind\tconfirmation_quality_mask";

/// `kind_code` per `label_probe_schema_v1.md` item 3: `0 SingleScientific, 1
/// MultiScientific, 2 WideOnly, 3 Unresolved` — the same order as
/// [`QuoteKind`]'s own variants.
#[must_use]
const fn kind_code(kind: QuoteKind) -> u8 {
    match kind {
        QuoteKind::SingleScientific => 0,
        QuoteKind::MultiScientific => 1,
        QuoteKind::WideOnly => 2,
        QuoteKind::Unresolved => 3,
    }
}

/// Writes `day_meta.tsv`, `day_signals.tsv`, and `day_groups.tsv` into
/// `day_dir` (created if absent) for one session, exactly per
/// `label_probe_schema_v1.md` "Probe invocation" items 1-3.
///
/// `seeds_raw_lines` is the day's verbatim `event_signals.tsv` line slice, in
/// original publication order — no parsing, no reordering, no
/// reformatting: the downstream comparator requires byte-exact output, and
/// this is the one file whose bytes must match the pinned publication
/// exactly.
///
/// O(`session.groups.len()` + `seeds_raw_lines.len()`): one pass to emit
/// each file; no per-line parsing.
///
/// # Errors
///
/// Returns an [`io::Error`] if `day_dir` cannot be created, or any of the
/// three files cannot be written.
pub fn write_probe_inputs(
    day_dir: &Path,
    session: &SessionData,
    seeds_raw_lines: &[String],
) -> io::Result<()> {
    std::fs::create_dir_all(day_dir)?;
    write_day_meta(day_dir, session)?;
    write_day_signals(day_dir, seeds_raw_lines)?;
    write_day_groups(day_dir, session)?;
    Ok(())
}

fn write_day_meta(day_dir: &Path, session: &SessionData) -> io::Result<()> {
    let mut out = File::create(day_dir.join("day_meta.tsv"))?;
    writeln!(
        out,
        "day\tsession_start_ns\tsession_end_ns\texpected_bar_count"
    )?;
    writeln!(
        out,
        "{}\t{}\t{}\t{}",
        session.day, session.session_start_ns, session.session_end_ns, session.expected_bar_count
    )
}

fn write_day_signals(day_dir: &Path, seeds_raw_lines: &[String]) -> io::Result<()> {
    let mut out = BufWriter::new(File::create(day_dir.join("day_signals.tsv"))?);
    writeln!(out, "{EVENT_SIGNALS_HEADER}")?;
    for line in seeds_raw_lines {
        writeln!(out, "{line}")?;
    }
    out.flush()
}

fn write_day_groups(day_dir: &Path, session: &SessionData) -> io::Result<()> {
    let mut out = BufWriter::new(File::create(day_dir.join("day_groups.tsv"))?);
    writeln!(out, "ts_ns\tkind_code\tscientific_midpoints")?;
    for index in 0..session.groups.len() {
        let midpoints = session.groups.scientific_midpoints(index);
        let joined = midpoints
            .iter()
            .map(i64::to_string)
            .collect::<Vec<_>>()
            .join(",");
        writeln!(
            out,
            "{}\t{}\t{joined}",
            session.groups.ts_ns[index],
            kind_code(session.groups.kind[index])
        )?;
    }
    out.flush()
}

/// Decodes a 64-lowercase-hex-character digest column into 32 bytes
/// (`label_probe_schema_v1.md` "Formatting rules": "Digests: 64 lowercase hex
/// chars"). `None` on any length or non-hex-digit mismatch. O(1) (fixed 64
/// chars).
#[must_use]
fn parse_hex32(value: &str) -> Option<[u8; 32]> {
    if value.len() != 64 || !value.is_ascii() {
        return None;
    }
    let mut out = [0_u8; 32];
    for (index, byte) in out.iter_mut().enumerate() {
        *byte = u8::from_str_radix(&value[index * 2..index * 2 + 2], 16).ok()?;
    }
    Some(out)
}

/// Hex-encodes a 32-byte digest as 64 lowercase hex characters
/// (`label_probe_schema_v1.md` "Formatting rules"). Duplicated locally: every
/// module in this crate that needs it keeps its own copy. O(1).
#[must_use]
fn hex32(digest: &[u8; 32]) -> String {
    digest
        .iter()
        .fold(String::with_capacity(64), |mut out, byte| {
            write!(out, "{byte:02x}").expect("writing to a String cannot fail");
            out
        })
}

/// Parses a day's verbatim `event_signals.tsv` line slice (the same
/// `seeds_raw_lines` passed to [`write_probe_inputs`], in original
/// publication order, which becomes `day_signals.tsv`'s row order) into
/// [`SignalSeed`]s: pulls the five columns the label kernels need —
/// `signal_id` (column 2), `extreme_side` (9), `pivot_price_u6` (10),
/// `pivot_last_bar_ordinal` (16), `causal_visible_ts_ns` (20) — by fixed
/// index into [`EVENT_SIGNALS_HEADER`]'s registered column order.
///
/// O(`seeds_raw_lines.len()`): one tab-split pass per line, five column
/// reads. This is not the byte-exact passthrough path (that is
/// [`write_day_signals`]) — it only extracts the typed fields the kernels
/// use, so the returned `Vec` preserves row order but not row text.
///
/// # Panics
///
/// Panics if a line has fewer than 21 tab-separated fields, or if
/// `signal_id`, `extreme_side`, `pivot_price_u6`, `pivot_last_bar_ordinal`,
/// or `causal_visible_ts_ns` fail to parse as their registered
/// digest/enum/integer type. Unreachable for any row of the pinned,
/// sha-verified REL037 event publication (`docs/engine_rebuild_r1_design.md`
/// "What is reused").
#[must_use]
pub fn parse_seeds(seeds_raw_lines: &[String]) -> Vec<SignalSeed> {
    seeds_raw_lines
        .iter()
        .map(|line| {
            let columns: Vec<&str> = line.split('\t').collect();
            let field = |index: usize, name: &str| -> &str {
                columns.get(index).unwrap_or_else(|| {
                    panic!("event_signals.tsv row missing column `{name}` (index {index}): {line}")
                })
            };
            let signal_id_hex = field(2, "signal_id");
            let extreme_side_wire = field(9, "extreme_side");
            let pivot_price_u6_raw = field(10, "pivot_price_u6");
            let pivot_last_bar_ordinal_raw = field(16, "pivot_last_bar_ordinal");
            let causal_visible_ts_ns_raw = field(20, "causal_visible_ts_ns");
            SignalSeed {
                signal_id: parse_hex32(signal_id_hex).unwrap_or_else(|| {
                    panic!("signal_id is not 64 lowercase hex chars: {signal_id_hex}")
                }),
                extreme_side: Side::from_wire(extreme_side_wire)
                    .unwrap_or_else(|| panic!("extreme_side is not LOW/HIGH: {extreme_side_wire}")),
                pivot_price_u6: pivot_price_u6_raw.parse().unwrap_or_else(|_| {
                    panic!("pivot_price_u6 is not an i64: {pivot_price_u6_raw}")
                }),
                pivot_last_bar_ordinal: pivot_last_bar_ordinal_raw.parse().unwrap_or_else(|_| {
                    panic!("pivot_last_bar_ordinal is not a u64: {pivot_last_bar_ordinal_raw}")
                }),
                causal_visible_ts_ns: causal_visible_ts_ns_raw.parse().unwrap_or_else(|_| {
                    panic!("causal_visible_ts_ns is not an i64: {causal_visible_ts_ns_raw}")
                }),
            }
        })
        .collect()
}

// ============================================================================
// Truth-relation dumps (amendment §A3/§A10, ruling E10)
// ============================================================================

/// One resolved truth episode row for this day's `day_truths.tsv` dump: the
/// `plateau_last_group_ordinal → plateau_bar_ordinal/plateau_end_ts_ns`
/// mapping established by the infra-wave provenance verification (see
/// [`crate::f_prox::TruthRelationDay`]'s doc comment for the full
/// group-ordinal provenance chain: `plateau_last_group_ordinal` indexes the
/// day's COMPLETE ordered group sequence, i.e. it is exactly a
/// `corpus::SessionData.groups`/`day_groups.tsv` row position).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TruthRow {
    pub episode_id: [u8; 32],
    pub plateau_last_group_ordinal: u64,
    /// `(plateau_end_ts_ns - session_start_ns) / 60_000_000_000` (CONV §3
    /// official minute index, floor division on a non-negative numerator).
    pub plateau_bar_ordinal: i64,
    /// The native timestamp of the group at `plateau_last_group_ordinal`
    /// (`session.groups.ts_ns[plateau_last_group_ordinal]`) — the truth-side
    /// clock is stamped at the plateau's NATIVE timestamp (CONV §4/§8),
    /// never the causal-visible `+1ms` convention the signal side uses.
    pub plateau_end_ts_ns: i64,
}

/// Resolves [`TruthRow`]s for every truth episode relevant to this day, from
/// the day's own `episode_id → plateau_last_group_ordinal` map (built by the
/// caller from `pubread::TruthCoverageReader` rows at `anchor_bps = 40`,
/// deduplicated by `episode_id`) and this day's already-loaded
/// `corpus::SessionData` (the same one the caller used to build the
/// `SessionFrame`).
///
/// Returns rows sorted ascending by `episode_id` (byte order) — deterministic
/// regardless of the caller's map iteration order (this crate's own
/// byte-determinism law: scientific dumps never depend on hash iteration
/// order).
///
/// O(`plateau_last_group_ordinal_by_episode.len()` log(same)): one
/// `session.groups.ts_ns` index per episode plus a final sort.
///
/// # Errors
///
/// Returns `Err` (never a silent `NA`/guess) if any `plateau_last_group_ordinal`
/// does not index an existing group in `session.groups` — unreachable for any
/// registered publication against its own pinned corpus day, but a real,
/// typed failure mode rather than a panic in a batch job.
#[allow(
    clippy::implicit_hasher,
    reason = "this crate always uses the standard hasher for its own internal maps; \
              generalizing over BuildHasher adds a type parameter with no caller need"
)]
pub fn resolve_truth_rows(
    session: &SessionData,
    plateau_last_group_ordinal_by_episode: &HashMap<[u8; 32], u64>,
) -> Result<Vec<TruthRow>, String> {
    let mut rows: Vec<TruthRow> = plateau_last_group_ordinal_by_episode
        .iter()
        .map(|(&episode_id, &ordinal)| {
            let index = usize::try_from(ordinal).map_err(|_| {
                format!(
                    "day {}: episode {} plateau_last_group_ordinal {ordinal} does not fit usize",
                    session.day,
                    hex32(&episode_id)
                )
            })?;
            let ts_ns = *session.groups.ts_ns.get(index).ok_or_else(|| {
                format!(
                    "day {}: episode {} plateau_last_group_ordinal {ordinal} is out of range \
                     for {} groups (registered-publication invariant violated — never guessed)",
                    session.day,
                    hex32(&episode_id),
                    session.groups.ts_ns.len()
                )
            })?;
            let plateau_bar_ordinal = (ts_ns - session.session_start_ns) / NANOSECONDS_PER_BAR;
            Ok(TruthRow {
                episode_id,
                plateau_last_group_ordinal: ordinal,
                plateau_bar_ordinal,
                plateau_end_ts_ns: ts_ns,
            })
        })
        .collect::<Result<_, String>>()?;
    rows.sort_by_key(|row| row.episode_id);
    Ok(rows)
}

/// Writes `day_truths.tsv` (amendment §A10): `episode_id`,
/// `plateau_last_group_ordinal`, `plateau_bar_ordinal`, `plateau_end_ts_ns`,
/// one row per truth episode, in `truths`' own order (ascending `episode_id`
/// per [`resolve_truth_rows`]).
///
/// # Errors
///
/// Returns an [`io::Error`] if `day_dir` cannot be created or the file cannot
/// be written.
pub fn write_day_truths(day_dir: &Path, truths: &[TruthRow]) -> io::Result<()> {
    std::fs::create_dir_all(day_dir)?;
    let mut out = BufWriter::new(File::create(day_dir.join("day_truths.tsv"))?);
    writeln!(
        out,
        "episode_id\tplateau_last_group_ordinal\tplateau_bar_ordinal\tplateau_end_ts_ns"
    )?;
    for row in truths {
        writeln!(
            out,
            "{}\t{}\t{}\t{}",
            hex32(&row.episode_id),
            row.plateau_last_group_ordinal,
            row.plateau_bar_ordinal,
            row.plateau_end_ts_ns
        )?;
    }
    out.flush()
}

/// Writes `day_truth_relations.tsv` (amendment §A3/§A10): `signal_id`,
/// `related_episode_ids` (comma-joined hex, ascending; `NA` when the signal
/// has no relation edge at `anchor_bps = 40` — `relation_count = 0`), one row
/// per signal, in `seeds`' own order (`day_signals.tsv` publication order).
///
/// `relation_edges` is the day's `signal_id → related_episode_ids` map,
/// built by the caller from `pubread::AssignmentReader` rows at
/// `anchor_bps = 40` (see [`crate::f_prox::TruthRelationDay`]'s doc comment,
/// step 1, for the exact population contract — this dump publishes the same
/// edges [`build_truth_relation_day`] resolves into
/// [`crate::f_prox::SignalRelation`]s).
///
/// # Errors
///
/// Returns an [`io::Error`] if `day_dir` cannot be created or the file cannot
/// be written.
#[allow(
    clippy::implicit_hasher,
    reason = "this crate always uses the standard hasher for its own internal maps; \
              generalizing over BuildHasher adds a type parameter with no caller need"
)]
pub fn write_day_truth_relations(
    day_dir: &Path,
    seeds: &[SignalSeed],
    relation_edges: &HashMap<[u8; 32], Vec<[u8; 32]>>,
) -> io::Result<()> {
    std::fs::create_dir_all(day_dir)?;
    let mut out = BufWriter::new(File::create(day_dir.join("day_truth_relations.tsv"))?);
    writeln!(out, "signal_id\trelated_episode_ids")?;
    for seed in seeds {
        let joined = relation_edges.get(&seed.signal_id).and_then(|episode_ids| {
            if episode_ids.is_empty() {
                None
            } else {
                let mut sorted = episode_ids.clone();
                sorted.sort_unstable();
                Some(sorted.iter().map(hex32).collect::<Vec<_>>().join(","))
            }
        });
        match joined {
            Some(value) => writeln!(out, "{}\t{value}", hex32(&seed.signal_id))?,
            None => writeln!(out, "{}\tNA", hex32(&seed.signal_id))?,
        }
    }
    out.flush()
}

/// Builds this day's [`TruthRelationDay`] from the day's raw relation edges
/// (`signal_id → related_episode_ids`, `anchor_bps = 40`, from
/// `pubread::AssignmentReader`) and its resolved [`TruthRow`]s (from
/// [`resolve_truth_rows`]). `truth_extreme_price_u6` is always `None` in the
/// resulting [`EpisodeProjection`]s — the one still-open A10 data-access gap
/// (see [`EpisodeProjection`]'s own doc comment); `plateau_bar_ordinal` /
/// `plateau_end_ts_ns` are fully populated (the infra-wave-verified
/// derivable pair).
///
/// O(`relation_edges.len()`): one `HashMap` lookup per signal into a
/// pre-built `episode_id → TruthRow` index.
///
/// # Errors
///
/// Returns `Err` (never a silent first-pick or panic) if a signal's SINGLE
/// related episode is not present in `truths` (a registered-publication
/// invariant violation) or if a `relation_count` does not fit `u32`.
#[allow(
    clippy::implicit_hasher,
    reason = "this crate always uses the standard hasher for its own internal maps; \
              generalizing over BuildHasher adds a type parameter with no caller need"
)]
pub fn build_truth_relation_day(
    relation_edges: &HashMap<[u8; 32], Vec<[u8; 32]>>,
    truths: &[TruthRow],
) -> Result<TruthRelationDay, String> {
    let truth_by_episode: HashMap<[u8; 32], &TruthRow> =
        truths.iter().map(|row| (row.episode_id, row)).collect();

    let mut relations = HashMap::with_capacity(relation_edges.len());
    for (&signal_id, episode_ids) in relation_edges {
        let relation = match episode_ids.len() {
            0 => SignalRelation::NoTruthRelation,
            1 => {
                let episode_id = episode_ids[0];
                let row = truth_by_episode.get(&episode_id).ok_or_else(|| {
                    format!(
                        "signal {} relates to episode {} which is not in this day's \
                         truth_coverage.tsv at anchor_bps=40 (registered-publication \
                         invariant violated)",
                        hex32(&signal_id),
                        hex32(&episode_id)
                    )
                })?;
                SignalRelation::Single(EpisodeProjection {
                    episode_id,
                    plateau_last_group_ordinal: row.plateau_last_group_ordinal,
                    plateau_bar_ordinal: row.plateau_bar_ordinal,
                    plateau_end_ts_ns: row.plateau_end_ts_ns,
                    truth_extreme_price_u6: None,
                })
            }
            n => {
                let relation_count = u32::try_from(n).map_err(|_| {
                    format!(
                        "signal {} has {n} related episodes: does not fit u32",
                        hex32(&signal_id)
                    )
                })?;
                SignalRelation::MultiRelation { relation_count }
            }
        };
        relations.insert(signal_id, relation);
    }
    Ok(TruthRelationDay::new(relations))
}

// ============================================================================
// Family-file wiring
// ============================================================================

/// Wiring point for every label-family output file: the four EVENTS.2
/// families (`f_ext.tsv`, `f_pass.tsv`, `f_term.tsv`, `f_ord.tsv`), the seven
/// EVENTS.3 families (`f_dwell.tsv`, `f_cfa.tsv`, `f_qprim.tsv`, `f_rank.tsv`,
/// `f_dir.tsv`, `f_ctrl.tsv`, `f_prox.tsv`), and `regimes.tsv` — design
/// authority `docs/specs/label_probe_schema_v1.md` (the four EVENTS.2
/// sections) plus each family's own `docs/specs/family_schemas/*.md`.
///
/// Parses `seeds_raw_lines` three ways (the [`SignalSeed`] every family
/// needs, plus [`crate::f_rank::RankSeed`]/[`crate::f_dir::DirSeed`]'s own
/// extra `event_signals.tsv` columns — E8's infra-wave wiring deliverable) and
/// calls each family's `write_tsv` once against the same `frame`, writing
/// `<day_dir>/<family>.tsv`. `truth` is F-PROX's per-day pre-joined relation
/// lookup (see [`TruthRelationDay`]'s doc comment); `session` is this day's
/// raw `corpus::SessionData`, needed only by `regimes.tsv` (the liquidity
/// columns are not derivable from the scientific-path-only `SessionFrame`
/// alone — see `crate::regimes`'s own module doc comment).
///
/// O(`seeds.len()` · log n) per family, `n` = `frame.group_count()` — see
/// each family module's own `write_tsv` doc comment for its exact query
/// count; this function adds no further per-row work beyond the three parses
/// (each O(`seeds_raw_lines.len()`)).
///
/// # Errors
///
/// Returns an [`io::Error`] if `day_dir` cannot be created or any of the
/// twelve files cannot be written.
pub fn write_family_files(
    day_dir: &Path,
    session: &SessionData,
    frame: &SessionFrame,
    seeds_raw_lines: &[String],
    truth: &TruthRelationDay,
) -> io::Result<()> {
    std::fs::create_dir_all(day_dir)?;
    let seeds = parse_seeds(seeds_raw_lines);
    let rank_seeds = crate::f_rank::parse_rank_seeds(seeds_raw_lines);
    let dir_seeds = crate::f_dir::parse_dir_seeds(seeds_raw_lines);

    crate::f_ext::write_tsv(frame, &seeds, &day_dir.join("f_ext.tsv"))?;
    crate::f_pass::write_tsv(frame, &seeds, &day_dir.join("f_pass.tsv"))?;
    crate::f_term::write_tsv(frame, &seeds, &day_dir.join("f_term.tsv"))?;
    crate::f_ord::write_tsv(frame, &seeds, &day_dir.join("f_ord.tsv"))?;
    crate::f_dwell::write_tsv(frame, &seeds, &day_dir.join("f_dwell.tsv"))?;
    crate::f_cfa::write_tsv(frame, &seeds, &day_dir.join("f_cfa.tsv"))?;
    crate::f_qprim::write_tsv(frame, &seeds, &day_dir.join("f_qprim.tsv"))?;
    crate::f_ctrl::write_tsv(frame, &seeds, &day_dir.join("f_ctrl.tsv"))?;
    crate::f_rank::write_tsv(frame, &rank_seeds, &day_dir.join("f_rank.tsv"))?;
    crate::f_dir::write_tsv(frame, &dir_seeds, &day_dir.join("f_dir.tsv"))?;
    crate::f_prox::write_tsv(frame, &seeds, truth, &day_dir.join("f_prox.tsv"))?;
    crate::regimes::write_tsv(session, frame, &day_dir.join("regimes.tsv"))?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use corpus::load_session;
    use std::path::PathBuf;

    fn corpus_root() -> PathBuf {
        PathBuf::from("/workspace/data/tokens/stock_quotes/IWM")
    }

    #[test]
    fn write_probe_inputs_produces_the_three_registered_files() {
        let root = corpus_root();
        if !root.is_dir() {
            eprintln!("skipping: corpus root {} is not mounted", root.display());
            return;
        }
        let session = load_session("2022-01-03", &root).expect("real session decodes");

        let day_dir =
            std::env::temp_dir().join(format!("labels_probe_test_{}", std::process::id()));
        std::fs::remove_dir_all(&day_dir).ok();

        let raw_lines = vec![
            "0\t2022-01-03\tabc\t".to_owned() + &"0".repeat(20),
            "1\t2022-01-03\tdef\t".to_owned() + &"0".repeat(20),
        ];
        write_probe_inputs(&day_dir, &session, &raw_lines).expect("writes probe inputs");

        let meta =
            std::fs::read_to_string(day_dir.join("day_meta.tsv")).expect("day_meta.tsv exists");
        let mut meta_lines = meta.lines();
        assert_eq!(
            meta_lines.next(),
            Some("day\tsession_start_ns\tsession_end_ns\texpected_bar_count")
        );
        assert_eq!(
            meta_lines.next(),
            Some(
                format!(
                    "{}\t{}\t{}\t{}",
                    session.day,
                    session.session_start_ns,
                    session.session_end_ns,
                    session.expected_bar_count
                )
                .as_str()
            )
        );
        assert_eq!(meta_lines.next(), None);

        let signals = std::fs::read_to_string(day_dir.join("day_signals.tsv"))
            .expect("day_signals.tsv exists");
        let mut signal_lines = signals.lines();
        assert_eq!(signal_lines.next(), Some(EVENT_SIGNALS_HEADER));
        assert_eq!(signal_lines.next(), Some(raw_lines[0].as_str()));
        assert_eq!(signal_lines.next(), Some(raw_lines[1].as_str()));
        assert_eq!(signal_lines.next(), None);

        let groups =
            std::fs::read_to_string(day_dir.join("day_groups.tsv")).expect("day_groups.tsv exists");
        let mut group_lines = groups.lines();
        assert_eq!(
            group_lines.next(),
            Some("ts_ns\tkind_code\tscientific_midpoints")
        );
        let first_group_row = group_lines.next().expect("at least one group row");
        let columns: Vec<&str> = first_group_row.split('\t').collect();
        assert_eq!(columns.len(), 3);
        assert_eq!(columns[0], session.groups.ts_ns[0].to_string());
        assert_eq!(columns[1], kind_code(session.groups.kind[0]).to_string());
        assert_eq!(group_lines.count() + 1, session.groups.len());

        std::fs::remove_dir_all(&day_dir).ok();
    }

    #[test]
    fn kind_code_matches_the_registered_wire_order() {
        assert_eq!(kind_code(QuoteKind::SingleScientific), 0);
        assert_eq!(kind_code(QuoteKind::MultiScientific), 1);
        assert_eq!(kind_code(QuoteKind::WideOnly), 2);
        assert_eq!(kind_code(QuoteKind::Unresolved), 3);
    }

    /// Builds one syntactically-valid 40-column `event_signals.tsv` row with
    /// the five columns [`parse_seeds`] reads set to the given values, and
    /// every other column a harmless placeholder (`parse_seeds` never reads
    /// them).
    fn raw_signal_line(
        signal_id_hex: &str,
        extreme_side: &str,
        pivot_price_u6: i64,
        pivot_last_bar_ordinal: u64,
        causal_visible_ts_ns: i64,
    ) -> String {
        let mut columns = vec!["0".to_owned(); 40];
        columns[1] = "2022-01-03".to_owned();
        columns[2] = signal_id_hex.to_owned();
        columns[9] = extreme_side.to_owned();
        columns[10] = pivot_price_u6.to_string();
        columns[16] = pivot_last_bar_ordinal.to_string();
        columns[20] = causal_visible_ts_ns.to_string();
        columns[23] = "false".to_owned();
        columns.join("\t")
    }

    #[test]
    fn parse_hex32_round_trips_a_lowercase_digest() {
        let hex = "ab".repeat(32);
        let decoded = parse_hex32(&hex).expect("valid 64-hex-char digest decodes");
        assert_eq!(decoded, [0xab_u8; 32]);
        assert_eq!(parse_hex32("ab"), None); // too short
        assert_eq!(parse_hex32(&"zz".repeat(32)), None); // not hex
    }

    #[test]
    fn parse_seeds_extracts_the_five_registered_columns_in_row_order() {
        let signal_id_hex = "11".repeat(32);
        let line_a = raw_signal_line(&signal_id_hex, "LOW", 100_000_000, 5, 12_345);
        let signal_id_hex_b = "22".repeat(32);
        let line_b = raw_signal_line(&signal_id_hex_b, "HIGH", 200_000_000, 9, 67_890);

        let seeds = parse_seeds(&[line_a, line_b]);
        assert_eq!(seeds.len(), 2);

        assert_eq!(seeds[0].signal_id, [0x11_u8; 32]);
        assert_eq!(seeds[0].extreme_side, Side::Low);
        assert_eq!(seeds[0].pivot_price_u6, 100_000_000);
        assert_eq!(seeds[0].pivot_last_bar_ordinal, 5);
        assert_eq!(seeds[0].causal_visible_ts_ns, 12_345);

        assert_eq!(seeds[1].signal_id, [0x22_u8; 32]);
        assert_eq!(seeds[1].extreme_side, Side::High);
        assert_eq!(seeds[1].pivot_price_u6, 200_000_000);
        assert_eq!(seeds[1].pivot_last_bar_ordinal, 9);
        assert_eq!(seeds[1].causal_visible_ts_ns, 67_890);
    }

    #[test]
    #[should_panic(expected = "extreme_side is not LOW/HIGH")]
    fn parse_seeds_panics_on_an_unregistered_extreme_side_code() {
        let line = raw_signal_line(&"33".repeat(32), "SIDEWAYS", 100, 0, 0);
        let _ = parse_seeds(&[line]);
    }

    #[test]
    fn write_family_files_emits_all_twelve_family_files_with_the_registered_shapes() {
        let root = corpus_root();
        if !root.is_dir() {
            eprintln!("skipping: corpus root {} is not mounted", root.display());
            return;
        }
        let session = load_session("2022-01-03", &root).expect("real session decodes");
        let frame = SessionFrame::build(&session);

        let line = raw_signal_line(&"44".repeat(32), "LOW", frame.m_lo[0].max(1), 0, 0);
        let raw_lines = vec![line];
        let truth = TruthRelationDay::new(HashMap::new());

        let day_dir = std::env::temp_dir().join(format!(
            "labels_write_family_files_test_{}",
            std::process::id()
        ));
        std::fs::remove_dir_all(&day_dir).ok();

        write_family_files(&day_dir, &session, &frame, &raw_lines, &truth)
            .expect("writes all twelve family files");

        // (file name, expected total column count: 10-column common prefix
        // plus that family's own value columns, EXCEPT regimes.tsv which has
        // its own 2-column prefix and is one-row-per-bar, not per-anchor).
        // (file name, expected total column count, expected row count). Every
        // family is 1 signal x 3 slots = 3 rows, EXCEPT f_cfa.tsv, whose own
        // schema adds a fourth `PASS` row per signal (`crate::f_cfa`'s own
        // "Row shape" deviation).
        let anchor_family_expectations = [
            ("f_ext.tsv", 10 + 12, 3),
            ("f_pass.tsv", 10 + 11 * 7, 3),
            ("f_term.tsv", 10 + 5 * 6, 3),
            ("f_ord.tsv", 10 + 4, 3),
            ("f_dwell.tsv", 10 + 10, 3),
            ("f_cfa.tsv", 10 + 13, 4),
            ("f_qprim.tsv", 10 + 11 * 2, 3),
            ("f_ctrl.tsv", 10 + 9 * 7 + 4 * 6, 3),
            ("f_rank.tsv", 10 + 3, 3),
            ("f_dir.tsv", 10 + 2, 3),
            ("f_prox.tsv", 10 + 13, 3),
        ];
        for (file_name, expected_columns, expected_rows) in anchor_family_expectations {
            let content = std::fs::read_to_string(day_dir.join(file_name))
                .unwrap_or_else(|error| panic!("{file_name} exists: {error}"));
            let mut lines = content.lines();
            lines
                .next()
                .unwrap_or_else(|| panic!("{file_name} has a header line"));
            let rows: Vec<&str> = lines.collect();
            assert_eq!(
                rows.len(),
                expected_rows,
                "{file_name}: unexpected row count"
            );
            for row in rows {
                assert_eq!(
                    row.split('\t').count(),
                    expected_columns,
                    "{file_name}: unexpected column count"
                );
            }
        }

        // regimes.tsv: one row per bar (390 for a normal session), its own
        // 2-column prefix (day, bar_ordinal) + the family's value columns.
        let regimes_content =
            std::fs::read_to_string(day_dir.join("regimes.tsv")).expect("regimes.tsv exists");
        let mut regimes_lines = regimes_content.lines();
        let regimes_header = regimes_lines.next().expect("regimes.tsv has a header");
        assert_eq!(
            regimes_header.split('\t').count(),
            2 + 9 + 9 + 2 + 2 + 5 + 2
        );
        assert_eq!(
            regimes_lines.count(),
            usize::from(session.expected_bar_count)
        );

        std::fs::remove_dir_all(&day_dir).ok();
    }

    // ------------------------- truth-relation dumps -------------------------

    #[test]
    fn resolve_truth_rows_computes_bar_ordinal_and_ts_from_the_group_ordinal() {
        let session = SessionData {
            day: "2022-01-03",
            session_start_ns: 0,
            session_end_ns: 10 * NANOSECONDS_PER_BAR,
            expected_bar_count: 10,
            source_sha256: "test",
            groups: corpus::QuoteGroups {
                ts_ns: vec![0, 3 * NANOSECONDS_PER_BAR, 3 * NANOSECONDS_PER_BAR + 1],
                raw_member_count: vec![1; 3],
                structurally_valid_count: vec![1; 3],
                scientific_member_count: vec![1; 3],
                wide_member_count: vec![0; 3],
                rejected_member_count: vec![0; 3],
                has_locked_member: vec![false; 3],
                kind: vec![corpus::QuoteKind::SingleScientific; 3],
                quality: vec![corpus::QualityFlags::default(); 3],
                scientific_midpoint_offsets: vec![0, 1, 2, 3],
                scientific_midpoints_u6: vec![1_000_000, 1_000_000, 1_000_000],
                wide_midpoint_offsets: vec![0; 4],
                wide_midpoints_u6: Vec::new(),
            },
        };
        let episode_id = [0xab; 32];
        let map: HashMap<[u8; 32], u64> = [(episode_id, 1_u64)].into_iter().collect();
        let rows = resolve_truth_rows(&session, &map).expect("resolves");
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0].episode_id, episode_id);
        assert_eq!(rows[0].plateau_last_group_ordinal, 1);
        assert_eq!(rows[0].plateau_end_ts_ns, 3 * NANOSECONDS_PER_BAR);
        assert_eq!(rows[0].plateau_bar_ordinal, 3);
    }

    #[test]
    fn resolve_truth_rows_errors_loudly_on_an_out_of_range_ordinal() {
        let session = SessionData {
            day: "2022-01-03",
            session_start_ns: 0,
            session_end_ns: 10 * NANOSECONDS_PER_BAR,
            expected_bar_count: 10,
            source_sha256: "test",
            groups: corpus::QuoteGroups {
                ts_ns: vec![0],
                raw_member_count: vec![1],
                structurally_valid_count: vec![1],
                scientific_member_count: vec![1],
                wide_member_count: vec![0],
                rejected_member_count: vec![0],
                has_locked_member: vec![false],
                kind: vec![corpus::QuoteKind::SingleScientific],
                quality: vec![corpus::QualityFlags::default()],
                scientific_midpoint_offsets: vec![0, 1],
                scientific_midpoints_u6: vec![1_000_000],
                wide_midpoint_offsets: vec![0, 0],
                wide_midpoints_u6: Vec::new(),
            },
        };
        let map: HashMap<[u8; 32], u64> = [([0xab; 32], 5_u64)].into_iter().collect();
        assert!(resolve_truth_rows(&session, &map).is_err());
    }

    #[test]
    fn write_day_truths_writes_the_registered_header_and_rows() {
        let truths = vec![
            TruthRow {
                episode_id: [0x02; 32],
                plateau_last_group_ordinal: 7,
                plateau_bar_ordinal: 3,
                plateau_end_ts_ns: 180_000_000_000,
            },
            TruthRow {
                episode_id: [0x01; 32],
                plateau_last_group_ordinal: 2,
                plateau_bar_ordinal: 1,
                plateau_end_ts_ns: 60_000_000_000,
            },
        ];
        let day_dir = std::env::temp_dir().join(format!("day_truths_test_{}", std::process::id()));
        std::fs::remove_dir_all(&day_dir).ok();
        write_day_truths(&day_dir, &truths).expect("writes day_truths.tsv");
        let content = std::fs::read_to_string(day_dir.join("day_truths.tsv")).expect("exists");
        let mut lines = content.lines();
        assert_eq!(
            lines.next(),
            Some("episode_id\tplateau_last_group_ordinal\tplateau_bar_ordinal\tplateau_end_ts_ns")
        );
        let row0: Vec<&str> = lines.next().expect("row 0").split('\t').collect();
        assert_eq!(row0[0], hex32(&[0x02; 32]));
        assert_eq!(row0[1], "7");
        assert_eq!(row0[2], "3");
        assert_eq!(row0[3], "180000000000");
        assert!(lines.next().is_some());
        assert_eq!(lines.next(), None);
        std::fs::remove_dir_all(&day_dir).ok();
    }

    #[test]
    fn write_day_truth_relations_emits_na_for_unrelated_and_zero_edge_signals() {
        let seeds = vec![
            SignalSeed {
                signal_id: [0x01; 32],
                extreme_side: Side::Low,
                pivot_price_u6: 1_000_000,
                pivot_last_bar_ordinal: 0,
                causal_visible_ts_ns: 0,
            },
            SignalSeed {
                signal_id: [0x02; 32],
                extreme_side: Side::Low,
                pivot_price_u6: 1_000_000,
                pivot_last_bar_ordinal: 0,
                causal_visible_ts_ns: 0,
            },
            SignalSeed {
                signal_id: [0x03; 32],
                extreme_side: Side::Low,
                pivot_price_u6: 1_000_000,
                pivot_last_bar_ordinal: 0,
                causal_visible_ts_ns: 0,
            },
        ];
        let relation_edges: HashMap<[u8; 32], Vec<[u8; 32]>> = [
            ([0x01; 32], vec![[0xaa; 32], [0xbb; 32]]),
            ([0x02; 32], Vec::new()), // "NA" parsed to an empty list
                                      // 0x03 has no row at all.
        ]
        .into_iter()
        .collect();

        let day_dir =
            std::env::temp_dir().join(format!("day_truth_relations_test_{}", std::process::id()));
        std::fs::remove_dir_all(&day_dir).ok();
        write_day_truth_relations(&day_dir, &seeds, &relation_edges)
            .expect("writes day_truth_relations.tsv");
        let content =
            std::fs::read_to_string(day_dir.join("day_truth_relations.tsv")).expect("exists");
        let mut lines = content.lines();
        assert_eq!(lines.next(), Some("signal_id\trelated_episode_ids"));
        let row0: Vec<&str> = lines.next().expect("row 0").split('\t').collect();
        assert_eq!(row0[0], hex32(&[0x01; 32]));
        assert_eq!(
            row0[1],
            format!("{},{}", hex32(&[0xaa; 32]), hex32(&[0xbb; 32]))
        );
        let row1: Vec<&str> = lines.next().expect("row 1").split('\t').collect();
        assert_eq!(row1[1], "NA");
        let row2: Vec<&str> = lines.next().expect("row 2").split('\t').collect();
        assert_eq!(row2[1], "NA");
        assert_eq!(lines.next(), None);
        std::fs::remove_dir_all(&day_dir).ok();
    }

    #[test]
    fn build_truth_relation_day_resolves_single_multi_and_none() {
        let episode_id = [0xaa; 32];
        let truths = vec![TruthRow {
            episode_id,
            plateau_last_group_ordinal: 42,
            plateau_bar_ordinal: 5,
            plateau_end_ts_ns: 300_000_000_000,
        }];
        let relation_edges: HashMap<[u8; 32], Vec<[u8; 32]>> = [
            ([0x01; 32], vec![episode_id]),
            ([0x02; 32], vec![[0xbb; 32], [0xcc; 32]]),
            ([0x03; 32], Vec::new()),
        ]
        .into_iter()
        .collect();

        let day = build_truth_relation_day(&relation_edges, &truths).expect("builds");

        match day.relation_for(&[0x01; 32]) {
            SignalRelation::Single(projection) => {
                assert_eq!(projection.episode_id, episode_id);
                assert_eq!(projection.plateau_last_group_ordinal, 42);
                assert_eq!(projection.plateau_bar_ordinal, 5);
                assert_eq!(projection.plateau_end_ts_ns, 300_000_000_000);
                assert_eq!(projection.truth_extreme_price_u6, None);
            }
            other => panic!("expected Single, got {other:?}"),
        }
        assert_eq!(
            day.relation_for(&[0x02; 32]),
            SignalRelation::MultiRelation { relation_count: 2 }
        );
        assert_eq!(
            day.relation_for(&[0x03; 32]),
            SignalRelation::NoTruthRelation
        );
        assert_eq!(
            day.relation_for(&[0x04; 32]),
            SignalRelation::NoTruthRelation
        );
    }

    #[test]
    fn build_truth_relation_day_errors_on_an_unregistered_related_episode() {
        let relation_edges: HashMap<[u8; 32], Vec<[u8; 32]>> =
            [([0x01; 32], vec![[0xaa; 32]])].into_iter().collect();
        let result = build_truth_relation_day(&relation_edges, &[]);
        assert!(result.is_err());
    }
}
