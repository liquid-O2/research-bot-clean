//! Reader for the SELECT.4 action book (spine + clustermap), schema-pinned.
//!
//! Layout at `/workspace/artifacts/runs/select4_action_book_v1/`:
//!
//! * `book_o<START>_<END>.book.parquet` — the 54-column action spine, one row
//!   per `(day, cutoff_bar_ordinal, side)`; 41 shards, 773,661 actions total,
//!   the shard name carrying the 0-based session-ordinal range it covers.
//! * `book_o<START>_<END>.book.clustermap.parquet` — the 10-column constituent
//!   map, 26,549,829 rows total.
//!
//! ## There is no `action_cutoff_ns` column
//!
//! Checked against the shard's own schema: the 54 columns carry
//! `cutoff_bar_ordinal` (1-based) and `act_set_first_visibility_ns` /
//! `act_set_last_visibility_ns` (frame A), but no cutoff instant. The cutoff is
//! therefore DERIVED:
//!
//! ```text
//! cutoff_ns_A = registry.session_start_ns + cutoff_bar_ordinal * 60e9
//! ```
//!
//! and the derivation was measured, not assumed: over all 19,450 rows of shard
//! `o00000_00025`, `cutoff_bar_ordinal == floor((last_visibility_ns -
//! session_start_ns) / BAR_NS) + 1` held 19,450/19,450, i.e. every constituent
//! of an action is strictly inside the bar the ordinal names, and the cutoff is
//! that bar's close. The reader re-checks this invariant per row and refuses on
//! violation, so a book rebuild that changes the convention cannot pass
//! silently.
//!
//! Frame discipline: the derived cutoff is produced in BOTH frames from the
//! same ordinal — frame A off `session_start_ns` for joins against the book,
//! frame B off `SessionClock::open_b` for comparison against raw tape
//! timestamps. They are never mixed.

use crate::calendar::{DayScope, admit_ordinal};
use crate::error::{Result, SelectV2Error};
use crate::sources::{DECODE_BATCH_ROWS, open_builder, pin_column_names, typed};
use arrow_array::{Int64Array, StringArray};
use parquet::arrow::ProjectionMask;
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

/// Default action-book directory in this workspace.
pub const DEFAULT_BOOK_DIR: &str = "/workspace/artifacts/runs/select4_action_book_v1";

/// The 54 pinned spine columns.
pub const ACTION_BOOK_COLUMNS: [&str; 54] = [
    "action_id",
    "day",
    "session_ordinal",
    "cutoff_bar_ordinal",
    "side",
    "fold_ordinal",
    "fold_kind",
    "fold_disposition",
    "sealed_60m_state",
    "sealed_60m_frac_u6",
    "sealed_60m_move_u6",
    "sealed_60m_price_u6",
    "term_net_cent_15m",
    "term_net_cent_30m",
    "term_net_cent_60m",
    "term_net_cent_120m",
    "term_net_cent_close",
    "mfe_frac_u6_15m",
    "mfe_frac_u6_30m",
    "mfe_frac_u6_60m",
    "mfe_frac_u6_120m",
    "mfe_frac_u6_close",
    "mae_frac_u6_15m",
    "mae_frac_u6_30m",
    "mae_frac_u6_60m",
    "mae_frac_u6_120m",
    "mae_frac_u6_close",
    "giveback_frac_u6_15m",
    "giveback_frac_u6_30m",
    "giveback_frac_u6_60m",
    "giveback_frac_u6_120m",
    "giveback_frac_u6_close",
    "fav_occupancy_bars_15m",
    "fav_occupancy_bars_30m",
    "fav_occupancy_bars_60m",
    "fav_occupancy_bars_120m",
    "fav_occupancy_bars_close",
    "t_first_net_positive_bars",
    "t_mfe_bars",
    "act_set_n_constituents",
    "act_set_slot_mix",
    "act_set_stream_counts",
    "act_set_lag_min",
    "act_set_lag_median",
    "act_set_lag_max",
    "act_set_reversal_bps_n",
    "act_set_reversal_bps_min",
    "act_set_reversal_bps_median",
    "act_set_reversal_bps_max",
    "act_set_first_visibility_ns",
    "act_set_last_visibility_ns",
    "act_set_entry_price_u6_min",
    "act_set_entry_price_u6_median",
    "act_set_entry_price_u6_max",
];

/// The 10 pinned clustermap columns.
pub const CLUSTERMAP_COLUMNS: [&str; 10] = [
    "action_id",
    "day",
    "session_ordinal",
    "slot",
    "side",
    "physical_cluster_id",
    "governing_candidate_id",
    "governing_stream",
    "governing_signal_id",
    "constituent_digest",
];

/// Spine leaves decoded for the emitters: the five identity columns
/// (`action_id`, `day`, `session_ordinal`, `cutoff_bar_ordinal`, `side`) and
/// the whole `act_set_*` constituent summary, which family B1 reads as-of the
/// cutoff. `act_set_slot_mix` and `act_set_stream_counts` are deliberately NOT
/// projected: they are per-row strings, and the d1/d2/d3 slot-reachability
/// columns that would have consumed them were deleted by finding F-18.
///
/// The order here is the order the projected batch presents, because
/// [`ProjectionMask::roots`] keeps schema order regardless of the index order
/// handed to it — so this array doubles as the decode index map below.
const SPINE_PROJECTION: [usize; 18] = [
    0, 1, 2, 3, 4, 39, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53,
];

/// Which extreme of the session an action leans against.
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
pub enum Side {
    High,
    Low,
}

impl Side {
    fn parse(text: &str, path: &Path) -> Result<Self> {
        match text {
            "HIGH" => Ok(Self::High),
            "LOW" => Ok(Self::Low),
            other => Err(SelectV2Error::ContentMismatch {
                path: path.to_path_buf(),
                detail: format!("side {other:?} is neither HIGH nor LOW"),
            }),
        }
    }

    /// `0.0` for `HIGH`, `1.0` for `LOW` — the emitter-facing encoding.
    #[must_use]
    pub const fn as_f32(self) -> f32 {
        match self {
            Self::High => 0.0,
            Self::Low => 1.0,
        }
    }
}

/// The action's own constituent summary, exactly as the SELECT.4 spine
/// recorded it — the `act_set_*` block of the 54 pinned columns.
///
/// This is a **book summary**, not tape: it describes the constituent signals
/// that produced the action, all of which the spine's own causality invariant
/// pins strictly before the cutoff (re-checked per row in [`load_shard`]).
/// Family B1 therefore reads it under [`crate::families::AsOfRule::BookSummaryAtCutoff`],
/// not under a tape rule.
///
/// Every field is `Option` because the spine declares all eleven columns
/// nullable. **Measured over all 41 shards / 773,661 rows: zero nulls in every
/// one of them.** A `None` reaching a family is therefore a book rebuild that
/// changed its contract, not a routine value — which is why absence is carried
/// as `None` and surfaces as `NaN`, never as `0`.
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct ActSetSummary {
    /// `act_set_n_constituents` — constituent signals behind the action.
    pub n_constituents: Option<i64>,
    /// `act_set_lag_min` — bars between a constituent and its confirmation.
    /// Measured over the whole book: `lag_min` is 1 or 2 (753,688 / 19,973),
    /// `lag_median` is 1 or 2 (354,797 / 418,864), `lag_max` is 1 or 2
    /// (17,282 / 756,379). The TOL2 contract admits 0 as well; the frozen book
    /// contains none.
    pub lag_min: Option<i64>,
    /// `act_set_lag_median` — the representative lag B1 reports as `lag_bars`.
    pub lag_median: Option<i64>,
    /// `act_set_lag_max`.
    pub lag_max: Option<i64>,
    /// `act_set_reversal_bps_n` — how many constituents the reversal
    /// min/median/max were taken over. Measured: never 0 in the frozen book,
    /// so the three order statistics below are always backed by observations.
    pub reversal_bps_n: Option<i64>,
    /// `act_set_reversal_bps_min`, already in basis points.
    pub reversal_bps_min: Option<i64>,
    /// `act_set_reversal_bps_median`, already in basis points.
    pub reversal_bps_median: Option<i64>,
    /// `act_set_reversal_bps_max`, already in basis points.
    pub reversal_bps_max: Option<i64>,
    /// `act_set_entry_price_u6_min` — u6 dollars.
    pub entry_price_u6_min: Option<i64>,
    /// `act_set_entry_price_u6_median` — u6 dollars.
    pub entry_price_u6_median: Option<i64>,
    /// `act_set_entry_price_u6_max` — u6 dollars.
    pub entry_price_u6_max: Option<i64>,
}

/// One action's as-of boundary. Everything a family may read must sit strictly
/// before [`Self::cutoff_ns_b`] on the frame-B tape.
#[derive(Clone, Debug)]
pub struct ActionCutoff {
    pub action_id: String,
    pub day: &'static str,
    pub session_ordinal: u32,
    /// 1-based; the cutoff is the close of this bar.
    pub cutoff_bar_ordinal: i32,
    pub side: Side,
    /// Derived cutoff instant, true UTC (frame A).
    pub cutoff_ns_a: i64,
    /// Derived cutoff instant, naive-ET (frame B) — compare tape against this.
    pub cutoff_ns_b: i64,
    /// Frame-A instant of the action's earliest constituent.
    pub first_visibility_ns: i64,
    /// Frame-A instant of the action's latest constituent.
    pub last_visibility_ns: i64,
    /// The spine's own `act_set_*` constituent summary for this action.
    pub act_set: ActSetSummary,
}

impl ActionCutoff {
    /// Nanoseconds between the action's earliest and latest constituent. Both
    /// endpoints are frame A, so the difference is same-frame and lawful.
    ///
    /// **Measured over all 773,661 book rows: this is exactly 0 for every
    /// action** — zero rows with a positive span, zero with a negative one.
    /// Every action's constituents therefore carry one shared visibility
    /// instant in the frozen book, and any B1 column derived from this span is
    /// a constant until the book is rebuilt with per-constituent instants.
    #[must_use]
    pub const fn visibility_span_ns(&self) -> i64 {
        self.last_visibility_ns - self.first_visibility_ns
    }
}

/// Every action, grouped by session ordinal and ordered inside a session by
/// `(cutoff_bar_ordinal, side)` so a streaming pass consumes them in tape order.
#[derive(Clone, Debug, Default)]
pub struct ActionBook {
    by_session: BTreeMap<u32, Vec<ActionCutoff>>,
    actions: usize,
}

impl ActionBook {
    /// Total actions loaded.
    #[must_use]
    pub const fn len(&self) -> usize {
        self.actions
    }

    #[must_use]
    pub const fn is_empty(&self) -> bool {
        self.actions == 0
    }

    /// Sessions present, ascending.
    pub fn session_ordinals(&self) -> impl Iterator<Item = u32> + '_ {
        self.by_session.keys().copied()
    }

    /// This session's actions, in tape order. Empty slice when the session
    /// carries none — observed-zero, distinct from the session being absent.
    #[must_use]
    pub fn cutoffs_for(&self, session_ordinal: u32) -> &[ActionCutoff] {
        self.by_session
            .get(&session_ordinal)
            .map_or(&[], Vec::as_slice)
    }
}

/// The spine shards under `dir`, ascending by the ordinal range in the name.
///
/// # Errors
///
/// [`SelectV2Error::Io`] if the directory cannot be listed, or
/// [`SelectV2Error::Config`] if it holds no spine shard.
pub fn spine_shards(dir: &Path) -> Result<Vec<(u32, u32, PathBuf)>> {
    let mut shards = Vec::new();
    for entry in std::fs::read_dir(dir).map_err(|source| SelectV2Error::Io {
        path: dir.to_path_buf(),
        source,
    })? {
        let path = entry
            .map_err(|source| SelectV2Error::Io {
                path: dir.to_path_buf(),
                source,
            })?
            .path();
        let Some(name) = path.file_name().and_then(std::ffi::OsStr::to_str) else {
            continue;
        };
        let Some(rest) = name.strip_prefix("book_o") else {
            continue;
        };
        let Some(range) = rest.strip_suffix(".book.parquet") else {
            continue;
        };
        let Some((start, end)) = range.split_once('_') else {
            continue;
        };
        let (Ok(start), Ok(end)) = (start.parse::<u32>(), end.parse::<u32>()) else {
            continue;
        };
        shards.push((start, end, path));
    }
    if shards.is_empty() {
        return Err(SelectV2Error::Config(format!(
            "{} holds no book_o*.book.parquet spine shard",
            dir.display()
        )));
    }
    shards.sort();
    Ok(shards)
}

/// Loads the whole action book.
///
/// # Errors
///
/// As [`load_sessions`].
pub fn load(dir: &Path) -> Result<ActionBook> {
    load_sessions(dir, None)
}

/// Loads only the shards covering `wanted` session ordinals (all when `None`).
///
/// # Errors
///
/// [`SelectV2Error::SchemaMismatch`] if a shard is not the pinned 54-column
/// spine, [`SelectV2Error::ContentMismatch`] if the derived-cutoff invariant
/// fails, or [`SelectV2Error::Io`].
pub fn load_sessions(dir: &Path, wanted: Option<&[u32]>) -> Result<ActionBook> {
    let mut book = ActionBook::default();
    for (start, end, path) in spine_shards(dir)? {
        if let Some(wanted) = wanted
            && !wanted.iter().any(|ordinal| *ordinal >= start && *ordinal < end)
        {
            continue;
        }
        load_shard(&path, wanted, &mut book)?;
    }
    for actions in book.by_session.values_mut() {
        actions.sort_by(|left, right| {
            left.cutoff_bar_ordinal
                .cmp(&right.cutoff_bar_ordinal)
                .then(left.side.cmp(&right.side))
                .then(left.action_id.cmp(&right.action_id))
        });
    }
    Ok(book)
}

// The projection, the per-row causality re-check and the `act_set_*` decode
// are ONE linear function on purpose: they are the single place the spine's
// column order is interpreted, and splitting them would let the index map
// drift away from the projection that produced it.
#[allow(clippy::too_many_lines)]
fn load_shard(path: &Path, wanted: Option<&[u32]>, book: &mut ActionBook) -> Result<()> {
    let builder = open_builder(path)?;
    pin_column_names(&builder, &ACTION_BOOK_COLUMNS, path)?;
    let projection = ProjectionMask::roots(builder.parquet_schema(), SPINE_PROJECTION);
    let reader = builder
        .with_projection(projection)
        .with_batch_size(DECODE_BATCH_ROWS)
        .build()
        .map_err(|source| SelectV2Error::Io {
            path: path.to_path_buf(),
            source: std::io::Error::other(source),
        })?;
    let mut scope_cache: Option<DayScope> = None;
    for batch in reader {
        let batch = batch.map_err(|source| SelectV2Error::Io {
            path: path.to_path_buf(),
            source: std::io::Error::other(source),
        })?;
        let action_id = typed::<StringArray>(&batch, 0, path, "action_id")?;
        let day = typed::<StringArray>(&batch, 1, path, "day")?;
        let session_ordinal = typed::<Int64Array>(&batch, 2, path, "session_ordinal")?;
        let cutoff_bar = typed::<Int64Array>(&batch, 3, path, "cutoff_bar_ordinal")?;
        let side = typed::<StringArray>(&batch, 4, path, "side")?;
        // The `act_set_*` block, in projected-batch order (see SPINE_PROJECTION).
        let n_constituents = typed::<Int64Array>(&batch, 5, path, "act_set_n_constituents")?;
        let lag_min = typed::<Int64Array>(&batch, 6, path, "act_set_lag_min")?;
        let lag_median = typed::<Int64Array>(&batch, 7, path, "act_set_lag_median")?;
        let lag_max = typed::<Int64Array>(&batch, 8, path, "act_set_lag_max")?;
        let reversal_n = typed::<Int64Array>(&batch, 9, path, "act_set_reversal_bps_n")?;
        let reversal_min = typed::<Int64Array>(&batch, 10, path, "act_set_reversal_bps_min")?;
        let reversal_median = typed::<Int64Array>(&batch, 11, path, "act_set_reversal_bps_median")?;
        let reversal_max = typed::<Int64Array>(&batch, 12, path, "act_set_reversal_bps_max")?;
        let first_visibility = typed::<Int64Array>(&batch, 13, path, "first_visibility_ns")?;
        let last_visibility = typed::<Int64Array>(&batch, 14, path, "last_visibility_ns")?;
        let entry_min = typed::<Int64Array>(&batch, 15, path, "act_set_entry_price_u6_min")?;
        let entry_median = typed::<Int64Array>(&batch, 16, path, "act_set_entry_price_u6_median")?;
        let entry_max = typed::<Int64Array>(&batch, 17, path, "act_set_entry_price_u6_max")?;
        for row in 0..batch.num_rows() {
            let ordinal_i64 = session_ordinal.value(row);
            let ordinal = u32::try_from(ordinal_i64).map_err(|_| {
                SelectV2Error::ContentMismatch {
                    path: path.to_path_buf(),
                    detail: format!("session_ordinal {ordinal_i64} is not a calendar ordinal"),
                }
            })?;
            if let Some(wanted) = wanted
                && !wanted.contains(&ordinal)
            {
                continue;
            }
            let scope = match &scope_cache {
                Some(scope) if scope.session_ordinal() == ordinal as usize => scope,
                _ => {
                    scope_cache = Some(admit_ordinal(ordinal as usize)?);
                    scope_cache.as_ref().expect("just assigned")
                }
            };
            if scope.day() != day.value(row) {
                return Err(SelectV2Error::ContentMismatch {
                    path: path.to_path_buf(),
                    detail: format!(
                        "book row says ordinal {ordinal} is {}, registry says {}",
                        day.value(row),
                        scope.day()
                    ),
                });
            }
            let bar_ordinal = cutoff_bar.value(row);
            let cutoff_ns_a = scope.cutoff_ns_a(bar_ordinal)?;
            let cutoff_ns_b = scope.cutoff_ns_b(bar_ordinal)?;
            let last = last_visibility.value(row);
            // As-of invariant, re-checked per row: every constituent's last
            // visibility must land STRICTLY BEFORE the cutoff-bar boundary.
            // Equality with `bar_ordinal - 1` is the common case but NOT the
            // invariant — an action whose constituents last updated in an
            // earlier bar (measured: 2023-06-05 bar 17 with last visibility in
            // bar 15) is causal and lawful. Only visibility AT or AFTER the
            // cutoff boundary is a leak and refuses.
            let derived = (last - scope.entry().session_start_ns).div_euclid(corpus::BAR_NS) + 1;
            if derived > bar_ordinal {
                return Err(SelectV2Error::ContentMismatch {
                    path: path.to_path_buf(),
                    detail: format!(
                        "{}: cutoff_bar_ordinal {bar_ordinal} but last visibility lands in bar \
                         {derived} (at/after the cutoff boundary) — causality violated",
                        action_id.value(row)
                    ),
                });
            }
            let bar_ordinal_i32 =
                i32::try_from(bar_ordinal).map_err(|_| SelectV2Error::ContentMismatch {
                    path: path.to_path_buf(),
                    detail: format!("cutoff_bar_ordinal {bar_ordinal} out of range"),
                })?;
            book.by_session
                .entry(ordinal)
                .or_default()
                .push(ActionCutoff {
                    action_id: action_id.value(row).to_owned(),
                    day: scope.day(),
                    session_ordinal: ordinal,
                    cutoff_bar_ordinal: bar_ordinal_i32,
                    side: Side::parse(side.value(row), path)?,
                    cutoff_ns_a,
                    cutoff_ns_b,
                    first_visibility_ns: first_visibility.value(row),
                    last_visibility_ns: last,
                    act_set: ActSetSummary {
                        n_constituents: nullable(n_constituents, row),
                        lag_min: nullable(lag_min, row),
                        lag_median: nullable(lag_median, row),
                        lag_max: nullable(lag_max, row),
                        reversal_bps_n: nullable(reversal_n, row),
                        reversal_bps_min: nullable(reversal_min, row),
                        reversal_bps_median: nullable(reversal_median, row),
                        reversal_bps_max: nullable(reversal_max, row),
                        entry_price_u6_min: nullable(entry_min, row),
                        entry_price_u6_median: nullable(entry_median, row),
                        entry_price_u6_max: nullable(entry_max, row),
                    },
                });
            book.actions += 1;
        }
    }
    Ok(())
}

/// A nullable spine cell. `None` is ABSENT, never folded into `0` — the whole
/// point of carrying [`ActSetSummary`] as options.
fn nullable(column: &Int64Array, row: usize) -> Option<i64> {
    if arrow_array::Array::is_null(column, row) {
        None
    } else {
        Some(column.value(row))
    }
}

/// One constituent row of the clustermap.
#[derive(Clone, Debug)]
pub struct Constituent {
    pub action_id: String,
    pub session_ordinal: u32,
    pub slot: String,
    pub governing_stream: String,
    pub physical_cluster_id: String,
}

/// Streams the clustermap shard beside a spine shard, keeping only `wanted`
/// sessions (all when `None`). The clustermap is ~200 MB per shard, so this
/// deliberately streams instead of loading the whole 26.5M-row map.
///
/// # Errors
///
/// [`SelectV2Error::SchemaMismatch`] if the shard is not the pinned 10-column
/// clustermap, or [`SelectV2Error::Io`].
pub fn clustermap_for_shard(
    spine_shard: &Path,
    wanted: Option<&[u32]>,
) -> Result<Vec<Constituent>> {
    let path = PathBuf::from(
        spine_shard
            .to_string_lossy()
            .replace(".book.parquet", ".book.clustermap.parquet"),
    );
    let builder = open_builder(&path)?;
    pin_column_names(&builder, &CLUSTERMAP_COLUMNS, &path)?;
    let projection = ProjectionMask::roots(builder.parquet_schema(), [0, 2, 3, 5, 7]);
    let reader = builder
        .with_projection(projection)
        .with_batch_size(DECODE_BATCH_ROWS)
        .build()
        .map_err(|source| SelectV2Error::Io {
            path: path.clone(),
            source: std::io::Error::other(source),
        })?;
    let mut out = Vec::new();
    for batch in reader {
        let batch = batch.map_err(|source| SelectV2Error::Io {
            path: path.clone(),
            source: std::io::Error::other(source),
        })?;
        let action_id = typed::<StringArray>(&batch, 0, &path, "action_id")?;
        let session_ordinal = typed::<Int64Array>(&batch, 1, &path, "session_ordinal")?;
        let slot = typed::<StringArray>(&batch, 2, &path, "slot")?;
        let cluster = typed::<StringArray>(&batch, 3, &path, "physical_cluster_id")?;
        let stream = typed::<StringArray>(&batch, 4, &path, "governing_stream")?;
        for row in 0..batch.num_rows() {
            let ordinal = u32::try_from(session_ordinal.value(row)).unwrap_or(u32::MAX);
            if let Some(wanted) = wanted
                && !wanted.contains(&ordinal)
            {
                continue;
            }
            out.push(Constituent {
                action_id: action_id.value(row).to_owned(),
                session_ordinal: ordinal,
                slot: slot.value(row).to_owned(),
                governing_stream: stream.value(row).to_owned(),
                physical_cluster_id: cluster.value(row).to_owned(),
            });
        }
    }
    Ok(out)
}
