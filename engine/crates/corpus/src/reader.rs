//! Direct parquet reader for one session's NBBO quotes.
//!
//! Ported from the proven decoder in
//! `archive/rust/iwm_atlas_v2/src/compact_parquet.rs`
//! (`decode_registered_compact_file` and friends). The quote-parsing and
//! -scaling semantics — price normalization to a fixed-point "u6" scale
//! (dollars × 1,000,000), regular-trading-hours (RTH) session-clock
//! filtering, and per-millisecond NBBO grouping with tight/wide spread
//! classification — are ported exactly. What's gone is the old code's
//! closure-hashing identity envelope (`source_authority_identity` and
//! friends), its law-validation machinery, and its `development-probe`
//! telemetry surface: none of that changes what a quote *is*, only how the
//! old build re-derived trust in its own binary.
//!
//! One difference in representation: the old `OwnedCompactGroupColumns` also
//! stored a `group_ordinal: Vec<i64>` column, but `group_ordinal[i]` was
//! always exactly `i` (each group is pushed once, in order). [`QuoteGroups`]
//! drops it — the position in every parallel column already is the ordinal.

use crate::error::{CorpusError, Result};
use crate::registry::{RegistryEntry, SourceProfile};
use arrow_array::{
    Array, Float64Array, Int32Array, Int64Array, RecordBatch, TimestampMillisecondArray,
};
use arrow_schema::{DataType, TimeUnit};
use parquet::arrow::ProjectionMask;
use parquet::arrow::arrow_reader::{ArrowReaderOptions, ParquetRecordBatchReaderBuilder};
use parquet::basic::Repetition;
use sha2::{Digest, Sha256};
use std::fs::File;
use std::io::{self, Read};
use std::path::{Path, PathBuf};
use std::time::Instant;

/// The source parquet carries 16 columns; only the first 9 are raw NBBO
/// fields (the rest — `d_bid_size`, `mid`, `spread_bps`, ...— are the
/// vendor's own precomputed derivatives). Only the first 9 are projected out
/// of the file; the schema check below still validates all 16, so a drift
/// anywhere in the source schema is still caught.
const RAW_FIELD_COUNT: usize = 9;
const DECODE_BATCH_ROWS: usize = 65_536;
/// The RTH window and the frame-B -> frame-A conversion are NOT restated
/// here: this reader consumes [`crate::SessionClock`], the workspace's one
/// clock authority (R-HALT-44 item 4, "reader.rs uses it too"). A second
/// implementation of the same 09:30 anchor is exactly what that ruling
/// removes.
use crate::session_clock::{FrameA, FrameB, SessionClock};
/// A quote is "scientific" (tight) when its spread is at most 50 bps of the
/// bid+ask total, i.e. `spread / mid <= 50bps` restated to avoid division.
const MAX_SCIENTIFIC_SPREAD_BPS: i128 = 50;
/// Sanity ceiling on a normalized u6 price ($1,000,000/share); guards against
/// a corrupt or misinterpreted price column rather than any real quote.
const MAX_NORMALIZED_NBBO_PRICE_U6: i64 = 1_000_000_000_000;

const ALL_FIELDS: [&str; 16] = [
    "timestamp",
    "bid_size",
    "bid_exchange",
    "bid",
    "bid_condition",
    "ask_size",
    "ask_exchange",
    "ask",
    "ask_condition",
    "d_bid_size",
    "d_ask_size",
    "bid_px_chg",
    "ask_px_chg",
    "dt_prev_ms",
    "mid",
    "spread_bps",
];

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum StockQuoteDomain {
    Premarket,
    Rth,
    AfterHours,
    OutsideDomain,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum StockQuoteState {
    Normal,
    Locked,
    Crossed,
    BidOnly,
    AskOnly,
    BothSidesAbsent,
    Invalid,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Ord, PartialOrd)]
pub enum RawQuoteScalar {
    I32(i32),
    I64(i64),
    F64Bits(u64),
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ClosedI64 {
    pub min: i64,
    pub max: i64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ClosedU64 {
    pub min: u64,
    pub max: u64,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct FullDayQuoteMember {
    pub row_ordinal: u64,
    pub event_time_b: FrameB,
    pub event_time_a: FrameA,
    pub bid_u6: Option<i64>,
    pub ask_u6: Option<i64>,
    pub bid_size_shares: Option<u64>,
    pub ask_size_shares: Option<u64>,
    pub bid_exchange: Option<i64>,
    pub ask_exchange: Option<i64>,
    pub bid_condition: Option<i64>,
    pub ask_condition: Option<i64>,
    pub d_bid_size: Option<RawQuoteScalar>,
    pub d_ask_size: Option<RawQuoteScalar>,
    pub bid_px_chg: Option<RawQuoteScalar>,
    pub ask_px_chg: Option<RawQuoteScalar>,
    pub dt_prev_ms: Option<RawQuoteScalar>,
    pub raw_spread_bps_bits: u64,
    pub source_profile: SourceProfile,
    pub state: StockQuoteState,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PostSetQuoteState {
    pub bid_price_u6: Option<ClosedI64>,
    pub ask_price_u6: Option<ClosedI64>,
    pub bid_size_shares: Option<ClosedU64>,
    pub ask_size_shares: Option<ClosedU64>,
    pub two_sided_price_u6: Option<ClosedI64>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct FullDayQuoteBatch {
    pub event_time_b: FrameB,
    pub event_time_a: FrameA,
    pub source_rows: std::ops::Range<u64>,
    pub domain: StockQuoteDomain,
    pub members: Vec<FullDayQuoteMember>,
    pub post_set: PostSetQuoteState,
}

#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct FullDayQuoteCensus {
    pub physical_rows: u64,
    pub ordinary_rows: u64,
    pub batch_count: u64,
    pub null_trailer_rows: u64,
    pub premarket_rows: u64,
    pub rth_rows: u64,
    pub after_hours_rows: u64,
    pub outside_domain_rows: u64,
    pub normal_rows: u64,
    pub locked_rows: u64,
    pub crossed_rows: u64,
    pub bid_only_rows: u64,
    pub ask_only_rows: u64,
    pub both_sides_absent_rows: u64,
    pub invalid_rows: u64,
    pub compact_rows: u64,
    pub wide_rows: u64,
    pub derivative_null_mask_counts: [u64; 32],
}

#[derive(Debug)]
pub struct FullDaySessionSummary {
    pub day: &'static str,
    pub legacy_rth: SessionData,
    pub census: FullDayQuoteCensus,
}

#[derive(Debug)]
pub enum FullDayQuoteItem {
    Batch(FullDayQuoteBatch),
    NullTrailer { row_ordinal: u64 },
}

#[derive(Debug)]
pub enum FullDayStreamError<E> {
    Corpus(CorpusError),
    Emit(E),
}

impl<E: std::fmt::Display> std::fmt::Display for FullDayStreamError<E> {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Corpus(error) => write!(f, "corpus refused: {error}"),
            Self::Emit(error) => write!(f, "emit refused: {error}"),
        }
    }
}
impl<E: std::fmt::Debug + std::fmt::Display + 'static> std::error::Error for FullDayStreamError<E> {}

/// What kind of clean NBBO quote (if any) a group resolved to.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum QuoteKind {
    /// Exactly one scientific (tight-spread) midpoint: the unambiguous quote.
    SingleScientific,
    /// More than one distinct scientific midpoint at the same millisecond
    /// (multiple exchanges disagreed): ambiguous.
    MultiScientific,
    /// No scientific midpoint, but at least one wide-spread midpoint.
    WideOnly,
    /// No valid member at all: every raw tick in the group was rejected.
    Unresolved,
}

/// Per-group quality bits, mirroring
/// `archive/rust/iwm_atlas_v2/src/scientific_path.rs` exactly.
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct QualityFlags(pub u32);

impl QualityFlags {
    pub const LOCKED: u32 = 1 << 0;
    pub const WIDE_SPREAD: u32 = 1 << 1;
    pub const MIXED_REJECTED: u32 = 1 << 2;
    pub const REJECTED_ONLY: u32 = 1 << 3;
    pub const MIXED_SCIENTIFIC_WIDE: u32 = 1 << 4;
    pub const WIDE_ONLY: u32 = 1 << 5;

    #[must_use]
    pub const fn contains(self, flag: u32) -> bool {
        self.0 & flag == flag
    }
}

/// Complete equal-millisecond NBBO group projection for one session, in
/// causal (timestamp) order. Every millisecond that had at least one raw
/// tick during regular trading hours gets a row, including rejected-only and
/// wide-only ones — downstream consumers decide what to do with those, this
/// reader doesn't discard information.
///
/// The two `*_offsets` arrays are CSR (compressed-sparse-row) offsets into
/// their matching `*_u6` array: group `i`'s midpoints are
/// `midpoints_u6[offsets[i]..offsets[i + 1]]`, deduplicated and sorted
/// ascending. Each has exactly `len() + 1` entries.
#[derive(Debug)]
pub struct QuoteGroups {
    pub ts_ns: Vec<i64>,
    pub raw_member_count: Vec<u32>,
    pub structurally_valid_count: Vec<u32>,
    pub scientific_member_count: Vec<u32>,
    pub wide_member_count: Vec<u32>,
    pub rejected_member_count: Vec<u32>,
    pub has_locked_member: Vec<bool>,
    pub kind: Vec<QuoteKind>,
    pub quality: Vec<QualityFlags>,
    pub scientific_midpoint_offsets: Vec<u32>,
    pub scientific_midpoints_u6: Vec<i64>,
    pub wide_midpoint_offsets: Vec<u32>,
    pub wide_midpoints_u6: Vec<i64>,
}

/// A derived `Default` would break the documented CSR invariant: every
/// offsets array carries `len() + 1` entries, so the empty projection has
/// `[0]`, never `[]`. The 2026-08-05 production probe caught exactly that —
/// `QuoteGroupAccumulator::default()` built offsets one short on every real
/// session while fixture-constructed groups satisfied the invariant by hand.
impl Default for QuoteGroups {
    fn default() -> Self {
        Self::with_capacity(0)
    }
}

impl QuoteGroups {
    fn with_capacity(groups: usize) -> Self {
        Self {
            ts_ns: Vec::with_capacity(groups),
            raw_member_count: Vec::with_capacity(groups),
            structurally_valid_count: Vec::with_capacity(groups),
            scientific_member_count: Vec::with_capacity(groups),
            wide_member_count: Vec::with_capacity(groups),
            rejected_member_count: Vec::with_capacity(groups),
            has_locked_member: Vec::with_capacity(groups),
            kind: Vec::with_capacity(groups),
            quality: Vec::with_capacity(groups),
            scientific_midpoint_offsets: vec![0],
            scientific_midpoints_u6: Vec::new(),
            wide_midpoint_offsets: vec![0],
            wide_midpoints_u6: Vec::new(),
        }
    }

    #[must_use]
    pub fn len(&self) -> usize {
        self.ts_ns.len()
    }

    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.ts_ns.is_empty()
    }

    /// The scientific (tight-spread) midpoints observed in group `index`,
    /// deduplicated and sorted ascending.
    #[must_use]
    pub fn scientific_midpoints(&self, index: usize) -> &[i64] {
        let start = self.scientific_midpoint_offsets[index] as usize;
        let stop = self.scientific_midpoint_offsets[index + 1] as usize;
        &self.scientific_midpoints_u6[start..stop]
    }

    /// The wide-spread midpoints observed in group `index`, deduplicated and
    /// sorted ascending.
    #[must_use]
    pub fn wide_midpoints(&self, index: usize) -> &[i64] {
        let start = self.wide_midpoint_offsets[index] as usize;
        let stop = self.wide_midpoint_offsets[index + 1] as usize;
        &self.wide_midpoints_u6[start..stop]
    }
}

/// One authenticated, decoded session: the registry's session-clock metadata
/// plus its complete NBBO quote-group projection.
#[derive(Debug)]
pub struct SessionData {
    pub day: &'static str,
    pub session_start_ns: i64,
    pub session_end_ns: i64,
    pub expected_bar_count: u16,
    pub source_sha256: &'static str,
    pub groups: QuoteGroups,
}

/// Authenticated timestamp-only projection for one registered session.
/// Complexity: `O(source bytes + rows)` time and `O(complete groups)` memory.
#[derive(Debug, Eq, PartialEq)]
pub struct SessionGroupTimes {
    pub day: &'static str,
    pub session_start_ns: i64,
    pub session_end_ns: i64,
    pub expected_bar_count: u16,
    pub source_sha256: &'static str,
    pub ts_ns: Vec<i64>,
}

/// Producer timing for the two independently projected timestamp-reader phases.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SessionGroupTimesMeasurement {
    pub source_authentication_ns: u64,
    pub timestamp_decode_ns: u64,
}

impl SessionData {
    /// Number of clean per-millisecond NBBO quotes in this session (one row
    /// per group, regardless of resolution kind).
    #[must_use]
    pub fn quote_count(&self) -> usize {
        self.groups.len()
    }
}

#[derive(Debug, Default)]
struct PendingGroup {
    timestamp_ms: Option<i64>,
    raw_member_count: u32,
    structurally_valid_count: u32,
    scientific_member_count: u32,
    wide_member_count: u32,
    rejected_member_count: u32,
    has_locked_member: bool,
    scientific_midpoints_u6: Vec<i64>,
    wide_midpoints_u6: Vec<i64>,
}

impl PendingGroup {
    fn clear(&mut self) {
        self.timestamp_ms = None;
        self.raw_member_count = 0;
        self.structurally_valid_count = 0;
        self.scientific_member_count = 0;
        self.wide_member_count = 0;
        self.rejected_member_count = 0;
        self.has_locked_member = false;
        self.scientific_midpoints_u6.clear();
        self.wide_midpoints_u6.clear();
    }
}

fn increment(counter: &mut u32) -> Result<()> {
    *counter = counter
        .checked_add(1)
        .ok_or(CorpusError::ArithmeticOverflow)?;
    Ok(())
}

enum SignedColumn<'a> {
    I32(&'a Int32Array),
    I64(&'a Int64Array),
}

impl SignedColumn<'_> {
    fn is_null(&self, row: usize) -> bool {
        match self {
            Self::I32(values) => values.is_null(row),
            Self::I64(values) => values.is_null(row),
        }
    }

    fn value(&self, row: usize) -> i64 {
        match self {
            Self::I32(values) => i64::from(values.value(row)),
            Self::I64(values) => values.value(row),
        }
    }
}

enum PriceColumn<'a> {
    CentI32(&'a Int32Array),
    DollarF64(&'a Float64Array),
}

impl PriceColumn<'_> {
    fn is_null(&self, row: usize) -> bool {
        match self {
            Self::CentI32(values) => values.is_null(row),
            Self::DollarF64(values) => values.is_null(row),
        }
    }

    fn normalized_u6(&self, row: usize, path: &Path) -> Result<i64> {
        match self {
            Self::CentI32(values) => i64::from(values.value(row))
                .checked_mul(10_000)
                .ok_or(CorpusError::ArithmeticOverflow),
            Self::DollarF64(values) => normalize_float_price_u6(values.value(row), path),
        }
    }
}

struct RawBatch<'a> {
    timestamp: &'a TimestampMillisecondArray,
    bid_size: SignedColumn<'a>,
    bid: PriceColumn<'a>,
    bid_condition: &'a Int64Array,
    ask_size: SignedColumn<'a>,
    ask: PriceColumn<'a>,
    ask_condition: &'a Int64Array,
}

impl<'a> RawBatch<'a> {
    fn from_batch(batch: &'a RecordBatch, profile: SourceProfile, path: &Path) -> Result<Self> {
        if batch.num_columns() != RAW_FIELD_COUNT {
            return Err(CorpusError::SchemaMismatch {
                path: path.to_path_buf(),
            });
        }
        let timestamp = typed_array::<TimestampMillisecondArray>(batch, 0, path)?;
        let bid_condition = typed_array::<Int64Array>(batch, 4, path)?;
        let ask_condition = typed_array::<Int64Array>(batch, 8, path)?;
        let (bid_size, bid, ask_size, ask) = match profile {
            SourceProfile::CentInt32 => (
                SignedColumn::I32(typed_array::<Int32Array>(batch, 1, path)?),
                PriceColumn::CentI32(typed_array::<Int32Array>(batch, 3, path)?),
                SignedColumn::I32(typed_array::<Int32Array>(batch, 5, path)?),
                PriceColumn::CentI32(typed_array::<Int32Array>(batch, 7, path)?),
            ),
            SourceProfile::DollarFloat64 => (
                SignedColumn::I64(typed_array::<Int64Array>(batch, 1, path)?),
                PriceColumn::DollarF64(typed_array::<Float64Array>(batch, 3, path)?),
                SignedColumn::I64(typed_array::<Int64Array>(batch, 5, path)?),
                PriceColumn::DollarF64(typed_array::<Float64Array>(batch, 7, path)?),
            ),
        };
        Ok(Self {
            timestamp,
            bid_size,
            bid,
            bid_condition,
            ask_size,
            ask,
            ask_condition,
        })
    }

    /// `(all 9 raw fields null, at least one of the 9 is null)`.
    fn null_pattern(&self, row: usize) -> (bool, bool) {
        let nulls = [
            self.timestamp.is_null(row),
            self.bid_size.is_null(row),
            self.bid.is_null(row),
            self.bid_condition.is_null(row),
            self.ask_size.is_null(row),
            self.ask.is_null(row),
            self.ask_condition.is_null(row),
        ];
        (
            nulls.iter().all(|value| *value),
            nulls.iter().any(|value| *value),
        )
    }
}

fn typed_array<'a, T: Array + 'static>(
    batch: &'a RecordBatch,
    index: usize,
    path: &Path,
) -> Result<&'a T> {
    batch
        .column(index)
        .as_any()
        .downcast_ref::<T>()
        .ok_or_else(|| CorpusError::SchemaMismatch {
            path: path.to_path_buf(),
        })
}

fn expected_type(profile: SourceProfile, index: usize) -> DataType {
    if index == 0 {
        return DataType::Timestamp(TimeUnit::Millisecond, None);
    }
    match profile {
        SourceProfile::CentInt32 => match index {
            1 | 3 | 5 | 7 | 9 | 10 | 11 | 12 | 14 => DataType::Int32,
            2 | 4 | 6 | 8 | 13 => DataType::Int64,
            15 => DataType::Float64,
            _ => unreachable!("validated schema index"),
        },
        SourceProfile::DollarFloat64 => match index {
            1 | 2 | 4 | 5 | 6 | 8 | 9 | 10 | 13 => DataType::Int64,
            3 | 7 | 11 | 12 | 14 | 15 => DataType::Float64,
            _ => unreachable!("validated schema index"),
        },
    }
}

fn validate_schema(
    builder: &ParquetRecordBatchReaderBuilder<File>,
    profile: SourceProfile,
    path: &Path,
) -> Result<()> {
    let parquet_schema = builder.parquet_schema();
    let root = parquet_schema.root_schema();
    let parquet_fields = root.get_fields();
    if root.get_basic_info().has_repetition()
        || parquet_schema.num_columns() != ALL_FIELDS.len()
        || parquet_fields.len() != ALL_FIELDS.len()
        || builder.schema().fields().len() != ALL_FIELDS.len()
    {
        return Err(CorpusError::SchemaMismatch {
            path: path.to_path_buf(),
        });
    }
    for (index, ((parquet_field, arrow_field), expected_name)) in parquet_fields
        .iter()
        .zip(builder.schema().fields())
        .zip(ALL_FIELDS)
        .enumerate()
    {
        if !parquet_field.is_primitive()
            || !parquet_field.get_basic_info().has_repetition()
            || parquet_field.get_basic_info().repetition() != Repetition::OPTIONAL
            || parquet_field.name() != expected_name
            || arrow_field.name() != expected_name
            || arrow_field.data_type() != &expected_type(profile, index)
        {
            return Err(CorpusError::SchemaMismatch {
                path: path.to_path_buf(),
            });
        }
    }
    let total_rows = builder.metadata().file_metadata().num_rows();
    if total_rows <= 0 {
        return Err(CorpusError::DecodeFailed {
            path: path.to_path_buf(),
            detail: "parquet file has no rows",
        });
    }
    Ok(())
}

/// Proxy for one ULP at `value`'s magnitude, used as a float→fixed-point
/// rounding tolerance. `f64` has 52 explicit mantissa bits.
fn float_ulp_proxy(value: f64) -> f64 {
    if value == 0.0 {
        0.0
    } else {
        (value.abs().log2().floor() - 52.0).exp2()
    }
}

/// Scales a dollar price to the u6 fixed-point scale (`* 1_000_000`),
/// requiring the result to round-trip to within float rounding error of an
/// exact integer — a `DollarFloat64` price that doesn't is treated as
/// undecodable rather than silently truncated.
fn normalize_float_price_u6(value: f64, path: &Path) -> Result<i64> {
    const I64_LIMIT: f64 = 9_223_372_036_854_775_808.0;
    let scaled = value * 1_000_000.0;
    if !value.is_finite() || !scaled.is_finite() {
        return Err(CorpusError::DecodeFailed {
            path: path.to_path_buf(),
            detail: "non-finite price",
        });
    }
    let nearest = scaled.round_ties_even();
    let tolerance = 2.0 * float_ulp_proxy(scaled).max(float_ulp_proxy(nearest));
    if !nearest.is_finite()
        || !(-I64_LIMIT..I64_LIMIT).contains(&nearest)
        || (scaled - nearest).abs() > tolerance
    {
        return Err(CorpusError::DecodeFailed {
            path: path.to_path_buf(),
            detail: "price does not normalize to an exact u6 integer",
        });
    }
    // `nearest` is finite and checked into the exact i64-representable range above.
    #[allow(clippy::cast_possible_truncation)]
    Ok(nearest as i64)
}

fn add_member(
    group: &mut PendingGroup,
    bid_size: i64,
    bid_u6: i64,
    bid_condition: i64,
    ask_size: i64,
    ask_u6: i64,
    ask_condition: i64,
) -> Result<()> {
    increment(&mut group.raw_member_count)?;
    let structurally_valid = bid_condition == 0
        && ask_condition == 0
        && bid_size > 0
        && ask_size > 0
        && (1..=MAX_NORMALIZED_NBBO_PRICE_U6).contains(&bid_u6)
        && (1..=MAX_NORMALIZED_NBBO_PRICE_U6).contains(&ask_u6)
        && ask_u6 >= bid_u6
        && (bid_u6 + ask_u6) % 2 == 0;
    if !structurally_valid {
        increment(&mut group.rejected_member_count)?;
        return Ok(());
    }
    increment(&mut group.structurally_valid_count)?;
    group.has_locked_member |= bid_u6 == ask_u6;
    let total = i128::from(bid_u6) + i128::from(ask_u6);
    let spread = i128::from(ask_u6) - i128::from(bid_u6);
    let midpoint = i64::try_from(total / 2).map_err(|_| CorpusError::ArithmeticOverflow)?;
    if spread * 20_000 <= MAX_SCIENTIFIC_SPREAD_BPS * total {
        increment(&mut group.scientific_member_count)?;
        group.scientific_midpoints_u6.push(midpoint);
    } else {
        increment(&mut group.wide_member_count)?;
        group.wide_midpoints_u6.push(midpoint);
    }
    Ok(())
}

fn finish_pending_group(
    pending: &mut PendingGroup,
    output: &mut QuoteGroups,
    entry: RegistryEntry,
    clock: &SessionClock,
    path: &Path,
) -> Result<()> {
    let Some(timestamp_ms) = pending.timestamp_ms else {
        return Ok(());
    };
    let expected_groups =
        usize::try_from(entry.complete_group_count).map_err(|_| CorpusError::ArithmeticOverflow)?;
    if output.len() >= expected_groups {
        return Err(CorpusError::ContentMismatch {
            path: path.to_path_buf(),
            detail: "decoded more groups than the registry's complete_group_count",
        });
    }
    // THE SOLE CONVERSION, through the one clock authority: it re-checks
    // that this instant is inside the frame-B window and that its frame-A
    // image is inside `[session_start, session_end)` under checked integer
    // arithmetic (boundary conditions 3-5).
    let ts_ns = clock
        .to_frame_a(FrameB::from_naive_et_ms(timestamp_ms)?)?
        .ns();
    push_pending_group(pending, ts_ns, output)
}

/// Classify and append one completed millisecond group. This is THE single
/// classification authority (kind/quality/midpoint dedup) shared by the file
/// decoder above and [`QuoteGroupAccumulator`]; the caller owns the frame
/// conversion that produced `ts_ns` and any registry count check.
fn push_pending_group(
    pending: &mut PendingGroup,
    ts_ns: i64,
    output: &mut QuoteGroups,
) -> Result<()> {
    pending.scientific_midpoints_u6.sort_unstable();
    pending.scientific_midpoints_u6.dedup();
    pending.wide_midpoints_u6.sort_unstable();
    pending.wide_midpoints_u6.dedup();

    let kind = if pending.scientific_midpoints_u6.len() == 1 {
        QuoteKind::SingleScientific
    } else if pending.scientific_midpoints_u6.len() > 1 {
        QuoteKind::MultiScientific
    } else if pending.wide_member_count > 0 {
        QuoteKind::WideOnly
    } else {
        QuoteKind::Unresolved
    };

    let mut quality = 0_u32;
    quality |= u32::from(pending.has_locked_member) * QualityFlags::LOCKED;
    quality |= u32::from(pending.wide_member_count > 0) * QualityFlags::WIDE_SPREAD;
    quality |= u32::from(pending.structurally_valid_count > 0 && pending.rejected_member_count > 0)
        * QualityFlags::MIXED_REJECTED;
    quality |=
        u32::from(pending.structurally_valid_count == 0 && pending.rejected_member_count > 0)
            * QualityFlags::REJECTED_ONLY;
    quality |= u32::from(pending.scientific_member_count > 0 && pending.wide_member_count > 0)
        * QualityFlags::MIXED_SCIENTIFIC_WIDE;
    quality |= u32::from(pending.scientific_member_count == 0 && pending.wide_member_count > 0)
        * QualityFlags::WIDE_ONLY;

    output.ts_ns.push(ts_ns);
    output.raw_member_count.push(pending.raw_member_count);
    output
        .structurally_valid_count
        .push(pending.structurally_valid_count);
    output
        .scientific_member_count
        .push(pending.scientific_member_count);
    output.wide_member_count.push(pending.wide_member_count);
    output
        .rejected_member_count
        .push(pending.rejected_member_count);
    output.has_locked_member.push(pending.has_locked_member);
    output.kind.push(kind);
    output.quality.push(QualityFlags(quality));
    output
        .scientific_midpoints_u6
        .extend_from_slice(&pending.scientific_midpoints_u6);
    output.scientific_midpoint_offsets.push(
        u32::try_from(output.scientific_midpoints_u6.len())
            .map_err(|_| CorpusError::ArithmeticOverflow)?,
    );
    output
        .wide_midpoints_u6
        .extend_from_slice(&pending.wide_midpoints_u6);
    output.wide_midpoint_offsets.push(
        u32::try_from(output.wide_midpoints_u6.len())
            .map_err(|_| CorpusError::ArithmeticOverflow)?,
    );
    pending.clear();
    Ok(())
}

/// Incremental builder of the [`QuoteGroups`] projection from an ALREADY
/// DECODED raw NBBO row stream, for callers that hold the session's rows and
/// must not pay a second parquet decode (the emission loader's F02 staging).
///
/// It reuses the module's single classification authority verbatim
/// ([`add_member`] + [`push_pending_group`]): structural validity, the
/// scientific/wide spread split, midpoint dedup, kind and quality bits are
/// decided by exactly the code the file decoder runs. The caller owns what the
/// file decoder owns upstream of classification: row admission (the RTH
/// window), price normalization to u6, the frame-B→A conversion that produces
/// each group's `ts_ns`, and millisecond grouping keys fed in nondecreasing
/// order.
#[derive(Debug, Default)]
pub struct QuoteGroupAccumulator {
    pending: PendingGroup,
    output: QuoteGroups,
    current_ts_ns: i64,
}

impl QuoteGroupAccumulator {
    #[must_use]
    pub fn with_capacity(groups: usize) -> Self {
        Self {
            pending: PendingGroup::default(),
            output: QuoteGroups::with_capacity(groups),
            current_ts_ns: 0,
        }
    }

    /// Add one raw member row. `group_key_ms` is the raw millisecond stamp the
    /// decoder groups on; `group_ts_ns` is its frame-A image (identical for
    /// every member of one group). Prices are the caller's u6 normalization; a
    /// row whose price failed normalization is fed with `0`, which the
    /// classification authority rejects exactly as an out-of-range price.
    ///
    /// # Errors
    ///
    /// Propagates the classification authority's checked-arithmetic refusals.
    #[allow(clippy::too_many_arguments)]
    pub fn add_raw_member(
        &mut self,
        group_key_ms: i64,
        group_ts_ns: i64,
        bid_size: i64,
        bid_u6: i64,
        bid_condition: i64,
        ask_size: i64,
        ask_u6: i64,
        ask_condition: i64,
    ) -> Result<()> {
        if self
            .pending
            .timestamp_ms
            .is_some_and(|current| current != group_key_ms)
        {
            push_pending_group(&mut self.pending, self.current_ts_ns, &mut self.output)?;
        }
        if self.pending.timestamp_ms.is_none() {
            self.pending.timestamp_ms = Some(group_key_ms);
            self.current_ts_ns = group_ts_ns;
        }
        add_member(
            &mut self.pending,
            bid_size,
            bid_u6,
            bid_condition,
            ask_size,
            ask_u6,
            ask_condition,
        )
    }

    /// Flush the trailing group and return the completed projection.
    ///
    /// # Errors
    ///
    /// Propagates the classification authority's checked-arithmetic refusals.
    pub fn finish(mut self) -> Result<QuoteGroups> {
        if self.pending.timestamp_ms.is_some() {
            push_pending_group(&mut self.pending, self.current_ts_ns, &mut self.output)?;
        }
        Ok(self.output)
    }
}

fn decode(file: File, path: &Path, entry: RegistryEntry) -> Result<QuoteGroups> {
    let map_parquet_err = |source: parquet::errors::ParquetError| CorpusError::Io {
        path: path.to_path_buf(),
        source: io::Error::other(source),
    };
    let map_arrow_err = |source: arrow_schema::ArrowError| CorpusError::Io {
        path: path.to_path_buf(),
        source: io::Error::other(source),
    };
    let options = ArrowReaderOptions::new().with_skip_arrow_metadata(true);
    let builder = ParquetRecordBatchReaderBuilder::try_new_with_options(file, options)
        .map_err(map_parquet_err)?;
    validate_schema(&builder, entry.source_profile, path)?;
    let projection = ProjectionMask::roots(builder.parquet_schema(), 0..RAW_FIELD_COUNT);
    let reader = builder
        .with_projection(projection)
        .with_batch_size(DECODE_BATCH_ROWS)
        .build()
        .map_err(map_parquet_err)?;

    let expected_groups =
        usize::try_from(entry.complete_group_count).map_err(|_| CorpusError::ArithmeticOverflow)?;
    let mut output = QuoteGroups::with_capacity(expected_groups);
    // The frame-B RTH window comes from the session clock, which derives
    // `expected_bar_count` from this session's OWN registry row -- never a
    // caller's constant, so a 210-bar early close closes when it closed.
    let clock = SessionClock::from_entry(entry)?;
    let wall_open_ms = clock.open_b_ms();
    let wall_end_ms = clock.close_b_ms();

    let mut pending = PendingGroup::default();
    let mut last_timestamp_ms: Option<i64> = None;
    let mut all_null_rows = 0_u64;
    let mut rth_rows = 0_u64;

    for batch in reader {
        let batch = batch.map_err(map_arrow_err)?;
        let raw = RawBatch::from_batch(&batch, entry.source_profile, path)?;
        for row in 0..batch.num_rows() {
            let (all_null, any_null) = raw.null_pattern(row);
            if all_null {
                all_null_rows = all_null_rows
                    .checked_add(1)
                    .ok_or(CorpusError::ArithmeticOverflow)?;
                continue;
            }
            if any_null {
                return Err(CorpusError::DecodeFailed {
                    path: path.to_path_buf(),
                    detail: "row mixes null and non-null NBBO fields",
                });
            }
            let timestamp_ms = raw.timestamp.value(row);
            if last_timestamp_ms.is_some_and(|previous| timestamp_ms < previous) {
                return Err(CorpusError::OutOfOrder {
                    path: path.to_path_buf(),
                });
            }
            last_timestamp_ms = Some(timestamp_ms);
            if timestamp_ms < wall_open_ms || timestamp_ms >= wall_end_ms {
                continue;
            }
            rth_rows = rth_rows
                .checked_add(1)
                .ok_or(CorpusError::ArithmeticOverflow)?;
            if pending
                .timestamp_ms
                .is_some_and(|current| current != timestamp_ms)
            {
                finish_pending_group(&mut pending, &mut output, entry, &clock, path)?;
            }
            if pending.timestamp_ms.is_none() {
                pending.timestamp_ms = Some(timestamp_ms);
            }
            add_member(
                &mut pending,
                raw.bid_size.value(row),
                raw.bid.normalized_u6(row, path)?,
                raw.bid_condition.value(row),
                raw.ask_size.value(row),
                raw.ask.normalized_u6(row, path)?,
                raw.ask_condition.value(row),
            )?;
        }
    }
    finish_pending_group(&mut pending, &mut output, entry, &clock, path)?;

    let raw_sum = output
        .raw_member_count
        .iter()
        .try_fold(0_u64, |sum, &value| sum.checked_add(u64::from(value)))
        .ok_or(CorpusError::ArithmeticOverflow)?;
    if all_null_rows != 1
        || rth_rows != entry.raw_rth_row_count
        || output.len() != expected_groups
        || raw_sum != entry.raw_rth_row_count
    {
        return Err(CorpusError::ContentMismatch {
            path: path.to_path_buf(),
            detail: "decoded row/group totals disagree with the registry",
        });
    }
    Ok(output)
}

/// Decodes the complete native group clock without decoding quote values.
/// Complexity: `O(rows)` time and `O(complete groups)` memory.
fn decode_group_times(
    file: File,
    path: &Path,
    entry: RegistryEntry,
    batch_rows: usize,
) -> Result<Vec<i64>> {
    let map_parquet_err = |source: parquet::errors::ParquetError| CorpusError::Io {
        path: path.to_path_buf(),
        source: io::Error::other(source),
    };
    let map_arrow_err = |source: arrow_schema::ArrowError| CorpusError::Io {
        path: path.to_path_buf(),
        source: io::Error::other(source),
    };
    let options = ArrowReaderOptions::new().with_skip_arrow_metadata(true);
    let builder = ParquetRecordBatchReaderBuilder::try_new_with_options(file, options)
        .map_err(map_parquet_err)?;
    validate_schema(&builder, entry.source_profile, path)?;
    let projection = ProjectionMask::roots(builder.parquet_schema(), 0..ALL_FIELDS.len());
    let reader = builder
        .with_projection(projection)
        .with_batch_size(batch_rows)
        .build()
        .map_err(map_parquet_err)?;

    let clock = SessionClock::from_entry(entry)?;
    let wall_open_ms = clock.open_b_ms();
    let wall_end_ms = clock.close_b_ms();
    let expected_groups =
        usize::try_from(entry.complete_group_count).map_err(|_| CorpusError::ArithmeticOverflow)?;
    let mut groups = Vec::with_capacity(expected_groups);
    let mut last_timestamp_ms = None;
    let mut current_group_ms = None;
    let mut all_null_rows = 0_u64;
    let mut rth_rows = 0_u64;

    for batch in reader {
        let batch = batch.map_err(map_arrow_err)?;
        if batch.num_columns() != ALL_FIELDS.len() {
            return Err(CorpusError::SchemaMismatch {
                path: path.to_path_buf(),
            });
        }
        let timestamp = typed_array::<TimestampMillisecondArray>(&batch, 0, path)?;
        for row in 0..batch.num_rows() {
            if timestamp.is_null(row) {
                let all_null = batch.columns().iter().all(|column| column.is_null(row));
                if !all_null {
                    return Err(CorpusError::DecodeFailed {
                        path: path.to_path_buf(),
                        detail: "PARTIAL_NULL_SENTINEL",
                    });
                }
                all_null_rows = all_null_rows
                    .checked_add(1)
                    .ok_or(CorpusError::ArithmeticOverflow)?;
                continue;
            }
            let timestamp_ms = timestamp.value(row);
            if last_timestamp_ms.is_some_and(|previous| timestamp_ms < previous) {
                return Err(CorpusError::OutOfOrder {
                    path: path.to_path_buf(),
                });
            }
            last_timestamp_ms = Some(timestamp_ms);
            if timestamp_ms < wall_open_ms || timestamp_ms >= wall_end_ms {
                continue;
            }
            rth_rows = rth_rows
                .checked_add(1)
                .ok_or(CorpusError::ArithmeticOverflow)?;
            if current_group_ms == Some(timestamp_ms) {
                continue;
            }
            groups.push(
                clock
                    .to_frame_a(FrameB::from_naive_et_ms(timestamp_ms)?)?
                    .ns(),
            );
            current_group_ms = Some(timestamp_ms);
        }
    }
    if all_null_rows != 1 {
        return Err(CorpusError::ContentMismatch {
            path: path.to_path_buf(),
            detail: "SENTINEL_COUNT",
        });
    }
    if rth_rows != entry.raw_rth_row_count {
        return Err(CorpusError::ContentMismatch {
            path: path.to_path_buf(),
            detail: "RTH_ROW_COUNT",
        });
    }
    if groups.len() != expected_groups {
        return Err(CorpusError::ContentMismatch {
            path: path.to_path_buf(),
            detail: "COMPLETE_GROUP_COUNT",
        });
    }
    Ok(groups)
}

fn hash_file(path: &Path) -> Result<String> {
    let mut file = File::open(path).map_err(|source| CorpusError::Io {
        path: path.to_path_buf(),
        source,
    })?;
    let mut hasher = Sha256::new();
    let mut buffer = vec![0_u8; 64 * 1024].into_boxed_slice();
    loop {
        let count = file.read(&mut buffer).map_err(|source| CorpusError::Io {
            path: path.to_path_buf(),
            source,
        })?;
        if count == 0 {
            break;
        }
        hasher.update(&buffer[..count]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

/// Resolves and authenticates the one registry-authorized session source.
/// Complexity: `O(source bytes)` time and `O(1)` memory.
fn authenticated_source_path(day: &str, corpus_root: &Path) -> Result<(RegistryEntry, PathBuf)> {
    let entry = crate::registry::lookup(day)?;
    let path: PathBuf = corpus_root.join(entry.source_relative_path);
    let metadata = std::fs::metadata(&path).map_err(|source| CorpusError::Io {
        path: path.clone(),
        source,
    })?;
    if metadata.len() != entry.source_size_bytes || hash_file(&path)? != entry.source_sha256 {
        return Err(CorpusError::SourceAuthenticationFailed { path });
    }
    Ok((entry, path))
}

fn authenticated_entry_path(entry: RegistryEntry, corpus_root: &Path) -> Result<PathBuf> {
    let path = corpus_root.join(entry.source_relative_path);
    let metadata = std::fs::metadata(&path).map_err(|source| CorpusError::Io {
        path: path.clone(),
        source,
    })?;
    if metadata.len() != entry.source_size_bytes || hash_file(&path)? != entry.source_sha256 {
        return Err(CorpusError::SourceAuthenticationFailed { path });
    }
    Ok(path)
}

fn raw_i64(
    batch: &RecordBatch,
    index: usize,
    profile: SourceProfile,
    row: usize,
    path: &Path,
) -> Result<Option<i64>> {
    match profile {
        SourceProfile::CentInt32 if matches!(index, 1 | 3 | 5 | 7 | 9 | 10 | 11 | 12 | 14) => {
            let values = typed_array::<Int32Array>(batch, index, path)?;
            Ok((!values.is_null(row)).then(|| i64::from(values.value(row))))
        }
        SourceProfile::DollarFloat64 if matches!(index, 1 | 2 | 4 | 5 | 6 | 8 | 9 | 10 | 13) => {
            let values = typed_array::<Int64Array>(batch, index, path)?;
            Ok((!values.is_null(row)).then(|| values.value(row)))
        }
        SourceProfile::CentInt32 | SourceProfile::DollarFloat64 => {
            let values = typed_array::<Int64Array>(batch, index, path)?;
            Ok((!values.is_null(row)).then(|| values.value(row)))
        }
    }
}

fn raw_scalar(
    batch: &RecordBatch,
    index: usize,
    profile: SourceProfile,
    row: usize,
    path: &Path,
) -> Result<Option<RawQuoteScalar>> {
    match expected_type(profile, index) {
        DataType::Int32 => Ok(typed_array::<Int32Array>(batch, index, path)?
            .is_null(row)
            .then_some(())
            .and(None)
            .or_else(|| {
                Some(RawQuoteScalar::I32(
                    typed_array::<Int32Array>(batch, index, path)
                        .ok()?
                        .value(row),
                ))
            })),
        DataType::Int64 => Ok(typed_array::<Int64Array>(batch, index, path)?
            .is_null(row)
            .then_some(())
            .and(None)
            .or_else(|| {
                Some(RawQuoteScalar::I64(
                    typed_array::<Int64Array>(batch, index, path)
                        .ok()?
                        .value(row),
                ))
            })),
        DataType::Float64 => Ok(typed_array::<Float64Array>(batch, index, path)?
            .is_null(row)
            .then_some(())
            .and(None)
            .or_else(|| {
                Some(RawQuoteScalar::F64Bits(
                    typed_array::<Float64Array>(batch, index, path)
                        .ok()?
                        .value(row)
                        .to_bits(),
                ))
            })),
        _ => Err(CorpusError::SchemaMismatch {
            path: path.to_path_buf(),
        }),
    }
}

/// Classifies one same-civil-day stock-tape instant against the registered
/// 04:00--20:00 (or early-close 04:00--17:00) stock session domains.
pub fn stock_quote_domain(clock: &SessionClock, time_b: FrameB) -> Result<StockQuoteDomain> {
    clock.to_frame_a_same_civil_day(time_b)?;
    let four_am = clock.open_b().ns() - (5_i64 * 60 * 60 + 30 * 60) * 1_000_000_000;
    let after_open = if clock.expected_bar_count() == 210 {
        clock.close_b().ns()
    } else {
        clock.open_b().ns() + 6_i64 * 60 * 60 * 1_000_000_000 + 30_i64 * 60 * 1_000_000_000
    };
    let after_close = after_open + 4_i64 * 60 * 60 * 1_000_000_000;
    let domain = if time_b.ns() >= four_am && time_b.ns() < clock.open_b().ns() {
        StockQuoteDomain::Premarket
    } else if clock.contains_b(time_b) {
        StockQuoteDomain::Rth
    } else if time_b.ns() >= after_open && time_b.ns() < after_close {
        StockQuoteDomain::AfterHours
    } else {
        StockQuoteDomain::OutsideDomain
    };
    Ok(domain)
}

fn quote_state(
    bid: Option<i64>,
    ask: Option<i64>,
    bid_size: Option<u64>,
    ask_size: Option<u64>,
    invalid: bool,
) -> StockQuoteState {
    if invalid {
        return StockQuoteState::Invalid;
    }
    match (bid, ask, bid_size, ask_size) {
        (Some(b), Some(a), Some(_), Some(_)) if b < a => StockQuoteState::Normal,
        (Some(b), Some(a), Some(_), Some(_)) if b == a => StockQuoteState::Locked,
        (Some(_), Some(_), Some(_), Some(_)) => StockQuoteState::Crossed,
        (Some(_), None, Some(_), _) => StockQuoteState::BidOnly,
        (None, Some(_), _, Some(_)) => StockQuoteState::AskOnly,
        (None, None, _, _) => StockQuoteState::BothSidesAbsent,
        _ => StockQuoteState::Invalid,
    }
}

fn post_set(members: &[FullDayQuoteMember]) -> PostSetQuoteState {
    let mut bid_price = None;
    let mut ask_price = None;
    let mut bid_size = None;
    let mut ask_size = None;
    let mut hull = None;
    for member in members {
        if member.state == StockQuoteState::Invalid {
            continue;
        }
        if let Some(value) = member.bid_u6 {
            bid_price = Some(match bid_price {
                Some(ClosedI64 { min, max }) => ClosedI64 {
                    min: min.min(value),
                    max: max.max(value),
                },
                None => ClosedI64 {
                    min: value,
                    max: value,
                },
            });
        }
        if let Some(value) = member.ask_u6 {
            ask_price = Some(match ask_price {
                Some(ClosedI64 { min, max }) => ClosedI64 {
                    min: min.min(value),
                    max: max.max(value),
                },
                None => ClosedI64 {
                    min: value,
                    max: value,
                },
            });
        }
        if let Some(value) = member.bid_size_shares {
            bid_size = Some(match bid_size {
                Some(ClosedU64 { min, max }) => ClosedU64 {
                    min: min.min(value),
                    max: max.max(value),
                },
                None => ClosedU64 {
                    min: value,
                    max: value,
                },
            });
        }
        if let Some(value) = member.ask_size_shares {
            ask_size = Some(match ask_size {
                Some(ClosedU64 { min, max }) => ClosedU64 {
                    min: min.min(value),
                    max: max.max(value),
                },
                None => ClosedU64 {
                    min: value,
                    max: value,
                },
            });
        }
        if matches!(
            member.state,
            StockQuoteState::Normal | StockQuoteState::Locked
        ) {
            if let (Some(b), Some(a)) = (member.bid_u6, member.ask_u6) {
                hull = Some(match hull {
                    Some(ClosedI64 { min, max }) => ClosedI64 {
                        min: min.min(b),
                        max: max.max(a),
                    },
                    None => ClosedI64 { min: b, max: a },
                });
            }
        }
    }
    PostSetQuoteState {
        bid_price_u6: bid_price,
        ask_price_u6: ask_price,
        bid_size_shares: bid_size,
        ask_size_shares: ask_size,
        two_sided_price_u6: hull,
    }
}

fn member_compare(left: &FullDayQuoteMember, right: &FullDayQuoteMember) -> std::cmp::Ordering {
    let profile = |value: SourceProfile| match value {
        SourceProfile::CentInt32 => 0_u8,
        SourceProfile::DollarFloat64 => 1_u8,
    };
    left.event_time_b
        .cmp(&right.event_time_b)
        .then(left.event_time_a.cmp(&right.event_time_a))
        .then(left.bid_u6.cmp(&right.bid_u6))
        .then(left.ask_u6.cmp(&right.ask_u6))
        .then(left.bid_size_shares.cmp(&right.bid_size_shares))
        .then(left.ask_size_shares.cmp(&right.ask_size_shares))
        .then(left.bid_exchange.cmp(&right.bid_exchange))
        .then(left.ask_exchange.cmp(&right.ask_exchange))
        .then(left.bid_condition.cmp(&right.bid_condition))
        .then(left.ask_condition.cmp(&right.ask_condition))
        .then(left.d_bid_size.cmp(&right.d_bid_size))
        .then(left.d_ask_size.cmp(&right.d_ask_size))
        .then(left.bid_px_chg.cmp(&right.bid_px_chg))
        .then(left.ask_px_chg.cmp(&right.ask_px_chg))
        .then(left.dt_prev_ms.cmp(&right.dt_prev_ms))
        .then(left.raw_spread_bps_bits.cmp(&right.raw_spread_bps_bits))
        .then(profile(left.source_profile).cmp(&profile(right.source_profile)))
        .then((left.state as u8).cmp(&(right.state as u8)))
        .then(left.row_ordinal.cmp(&right.row_ordinal))
}

/// Authenticates, decodes, and streams the complete registered native quote day.
/// First civil day on which the stock-quote feed reports NBBO sizes in **shares**.
///
/// Finding F-34. The raw `bid_size`/`ask_size` columns are round lots for
/// 2022-01-03 through 2025-10-31 and shares from 2025-11-03 onward — verified by
/// binary search over the corpus: median size 5-10 with 0% divisible by 100 in the
/// lot era, median 300 with 100% divisible by 100 in the share era. 962 of the
/// 1,003 development sessions are lots; the last 41 are shares.
///
/// The break sits inside the frozen denominator, so it is normalized here at the
/// reader boundary rather than in each family: every consumer must see one unit
/// across the whole development set, or a 100x scale step in the final 41 sessions
/// becomes a year-inversion against a certification floor. It is a typed schema
/// era exactly like the option-quote-absence era.
pub const SHARE_ERA_FIRST_DAY: &str = "2025-11-03";

/// Normalizes a raw NBBO size to shares for the session's era.
///
/// Lot-era sizes are multiplied by the 100-share round lot; share-era sizes pass
/// through. Civil-day strings are ISO `YYYY-MM-DD`, so lexicographic comparison is
/// chronological.
#[must_use]
pub fn nbbo_size_to_shares(raw: u64, day: &str) -> u64 {
    if day >= SHARE_ERA_FIRST_DAY {
        raw
    } else {
        raw.saturating_mul(100)
    }
}

pub fn stream_full_day_session<E>(
    day: &str,
    corpus_root: &Path,
    emit: impl FnMut(FullDayQuoteItem) -> std::result::Result<(), E>,
) -> std::result::Result<FullDaySessionSummary, FullDayStreamError<E>> {
    crate::authenticate_registry(corpus_root).map_err(FullDayStreamError::Corpus)?;
    stream_full_day_registered_entry(
        crate::lookup(day).map_err(FullDayStreamError::Corpus)?,
        corpus_root,
        emit,
    )
}

/// Fixture seam sharing the authenticated registered full-day decoder.
#[doc(hidden)]
pub fn stream_full_day_registered_entry<E>(
    entry: RegistryEntry,
    corpus_root: &Path,
    mut emit: impl FnMut(FullDayQuoteItem) -> std::result::Result<(), E>,
) -> std::result::Result<FullDaySessionSummary, FullDayStreamError<E>> {
    let path = authenticated_entry_path(entry, corpus_root).map_err(FullDayStreamError::Corpus)?;
    let file = File::open(&path).map_err(|source| {
        FullDayStreamError::Corpus(CorpusError::Io {
            path: path.clone(),
            source,
        })
    })?;
    let options = ArrowReaderOptions::new().with_skip_arrow_metadata(true);
    let builder =
        ParquetRecordBatchReaderBuilder::try_new_with_options(file, options).map_err(|source| {
            FullDayStreamError::Corpus(CorpusError::Io {
                path: path.clone(),
                source: io::Error::other(source),
            })
        })?;
    validate_schema(&builder, entry.source_profile, &path).map_err(FullDayStreamError::Corpus)?;
    let reader = builder
        .with_batch_size(DECODE_BATCH_ROWS)
        .build()
        .map_err(|source| {
            FullDayStreamError::Corpus(CorpusError::Io {
                path: path.clone(),
                source: io::Error::other(source),
            })
        })?;
    let clock = SessionClock::from_entry(entry).map_err(FullDayStreamError::Corpus)?;
    let mut legacy = QuoteGroups::with_capacity(
        usize::try_from(entry.complete_group_count)
            .map_err(|_| FullDayStreamError::Corpus(CorpusError::ArithmeticOverflow))?,
    );
    let mut pending = PendingGroup::default();
    let mut members = Vec::new();
    let mut current: Option<(i64, u64, StockQuoteDomain, FrameB, FrameA)> = None;
    let mut census = FullDayQuoteCensus::default();
    let mut last = None;
    let mut trailer = None;
    let mut row_ordinal = 0_u64;
    for batch in reader {
        let batch = batch.map_err(|source| {
            FullDayStreamError::Corpus(CorpusError::Io {
                path: path.clone(),
                source: io::Error::other(source),
            })
        })?;
        let timestamp = typed_array::<TimestampMillisecondArray>(&batch, 0, &path)
            .map_err(FullDayStreamError::Corpus)?;
        for row in 0..batch.num_rows() {
            let ordinal = row_ordinal;
            row_ordinal = row_ordinal
                .checked_add(1)
                .ok_or(FullDayStreamError::Corpus(CorpusError::ArithmeticOverflow))?;
            census.physical_rows = census
                .physical_rows
                .checked_add(1)
                .ok_or(FullDayStreamError::Corpus(CorpusError::ArithmeticOverflow))?;
            let all_null = batch.columns().iter().all(|column| column.is_null(row));
            if all_null {
                if trailer.is_some() {
                    return Err(FullDayStreamError::Corpus(CorpusError::DecodeFailed {
                        path: path.clone(),
                        detail: "MULTIPLE_TRAILER",
                    }));
                }
                trailer = Some(ordinal);
                census.null_trailer_rows = 1;
                continue;
            }
            // The sentinel's POSITION is not a law. This stream used to refuse any
            // ordinary row after it with `TRAILER_NOT_FINAL`, on the assumption
            // that the all-null row trails the session. Every one of the 1,508
            // IWM stock-quote files on disk carries its sentinel at row 0 instead,
            // so this stream could not read a single real session — it refused
            // 22.6 million rows of 2022-06-01 at the second physical row, and the
            // fixtures that covered it had been written to the assumed convention
            // rather than the observed one.
            //
            // The two older readers in this file (`all_null_rows != 1`) never had
            // the constraint and always accepted the real corpus. What is actually
            // registered is a COUNT: exactly one sentinel per file, enforced at the
            // end of the stream. That is what is kept.
            if (0..9)
                .chain(14..16)
                .any(|index| batch.column(index).is_null(row))
            {
                return Err(FullDayStreamError::Corpus(CorpusError::DecodeFailed {
                    path: path.clone(),
                    detail: "ORDINARY_NULL",
                }));
            }
            let timestamp_ms = timestamp.value(row);
            if last.is_some_and(|value| timestamp_ms < value) {
                return Err(FullDayStreamError::Corpus(CorpusError::OutOfOrder {
                    path: path.clone(),
                }));
            }
            last = Some(timestamp_ms);
            let time_b =
                FrameB::from_naive_et_ms(timestamp_ms).map_err(FullDayStreamError::Corpus)?;
            let time_a = clock
                .to_frame_a_same_civil_day(time_b)
                .map_err(FullDayStreamError::Corpus)?;
            let domain = stock_quote_domain(&clock, time_b).map_err(FullDayStreamError::Corpus)?;
            if current.is_some_and(|(time, _, _, _, _)| time != timestamp_ms) {
                let (_, start, domain, event_time_b, event_time_a) = current
                    .take()
                    .ok_or(FullDayStreamError::Corpus(CorpusError::ArithmeticOverflow))?;
                members.sort_by(member_compare);
                let post_set = post_set(&members);
                emit(FullDayQuoteItem::Batch(FullDayQuoteBatch {
                    event_time_b,
                    event_time_a,
                    source_rows: start..ordinal,
                    domain,
                    members: std::mem::take(&mut members),
                    post_set,
                }))
                .map_err(FullDayStreamError::Emit)?;
                census.batch_count = census
                    .batch_count
                    .checked_add(1)
                    .ok_or(FullDayStreamError::Corpus(CorpusError::ArithmeticOverflow))?;
            }
            if current.is_none() {
                current = Some((timestamp_ms, ordinal, domain, time_b, time_a));
            }
            let price = |index| -> Option<i64> {
                match entry.source_profile {
                    SourceProfile::CentInt32 => typed_array::<Int32Array>(&batch, index, &path)
                        .ok()
                        .and_then(|values| {
                            (!values.is_null(row))
                                .then(|| i64::from(values.value(row)).checked_mul(10_000))
                                .flatten()
                        }),
                    SourceProfile::DollarFloat64 => {
                        typed_array::<Float64Array>(&batch, index, &path)
                            .ok()
                            .and_then(|values| {
                                (!values.is_null(row))
                                    .then(|| {
                                        normalize_float_price_u6(values.value(row), &path).ok()
                                    })
                                    .flatten()
                            })
                    }
                }
            };
            let size = |index| -> Option<u64> {
                raw_i64(&batch, index, entry.source_profile, row, &path)
                    .ok()
                    .flatten()
                    .and_then(|value| {
                        if value < 0 {
                            None
                        } else {
                            // CORPUS-03: the physical dtype is ORTHOGONAL to the
                            // round-lot era, and this branch used to multiply
                            // `cent_int32` sizes by 100 on top of the day-keyed
                            // normalization below — a 100x double-scale on 364 of
                            // the 1,003 registered sessions.
                            //
                            // Measured on adjacent sessions of opposite dtype:
                            // 2022-09-29 (int32) median 6, 2022-09-30 (int64)
                            // median 7, both 0% divisible by 100 — plain lots in
                            // both. And 2025-11-28 is int32 AND share-era, median
                            // 400 with 100% divisible by 100, so the dtype branch
                            // inflated data that was already in shares.
                            //
                            // Sizes are lots-or-shares by DAY, never by dtype.
                            u64::try_from(value).ok()
                        }
                    })
            };
            let raw_bid = price(3);
            let raw_ask = price(7);
            let raw_bid_size = size(1);
            let raw_ask_size = size(5);
            let bid = raw_bid.filter(|value| *value > 0);
            let ask = raw_ask.filter(|value| *value > 0);
            // F-34: normalize the era's unit to shares before anything downstream
            // sees it. `entry.day` is the registered civil day for this file.
            let bid_size = raw_bid_size
                .filter(|value| *value > 0)
                .map(|value| nbbo_size_to_shares(value, entry.day));
            let ask_size = raw_ask_size
                .filter(|value| *value > 0)
                .map(|value| nbbo_size_to_shares(value, entry.day));
            let invalid = raw_bid.is_none() && !batch.column(3).is_null(row)
                || raw_ask.is_none() && !batch.column(7).is_null(row)
                || raw_bid_size.is_none() && !batch.column(1).is_null(row)
                || raw_ask_size.is_none() && !batch.column(5).is_null(row)
                || raw_bid.is_some_and(|value| value < 0 || value > MAX_NORMALIZED_NBBO_PRICE_U6)
                || raw_ask.is_some_and(|value| value < 0 || value > MAX_NORMALIZED_NBBO_PRICE_U6);
            let state = quote_state(bid, ask, bid_size, ask_size, invalid);
            let mask = [9, 10, 11, 12, 13]
                .iter()
                .enumerate()
                .try_fold(0_usize, |value, (bit, index)| {
                    Ok::<_, CorpusError>(
                        value | (usize::from(batch.column(*index).is_null(row)) << bit),
                    )
                })
                .map_err(FullDayStreamError::Corpus)?;
            census.derivative_null_mask_counts[mask] = census.derivative_null_mask_counts[mask]
                .checked_add(1)
                .ok_or(FullDayStreamError::Corpus(CorpusError::ArithmeticOverflow))?;
            let member = FullDayQuoteMember {
                row_ordinal: ordinal,
                event_time_b: time_b,
                event_time_a: time_a,
                bid_u6: bid,
                ask_u6: ask,
                bid_size_shares: bid_size,
                ask_size_shares: ask_size,
                bid_exchange: raw_i64(&batch, 2, entry.source_profile, row, &path)
                    .map_err(FullDayStreamError::Corpus)?,
                ask_exchange: raw_i64(&batch, 6, entry.source_profile, row, &path)
                    .map_err(FullDayStreamError::Corpus)?,
                bid_condition: raw_i64(&batch, 4, entry.source_profile, row, &path)
                    .map_err(FullDayStreamError::Corpus)?,
                ask_condition: raw_i64(&batch, 8, entry.source_profile, row, &path)
                    .map_err(FullDayStreamError::Corpus)?,
                d_bid_size: raw_scalar(&batch, 9, entry.source_profile, row, &path)
                    .map_err(FullDayStreamError::Corpus)?,
                d_ask_size: raw_scalar(&batch, 10, entry.source_profile, row, &path)
                    .map_err(FullDayStreamError::Corpus)?,
                bid_px_chg: raw_scalar(&batch, 11, entry.source_profile, row, &path)
                    .map_err(FullDayStreamError::Corpus)?,
                ask_px_chg: raw_scalar(&batch, 12, entry.source_profile, row, &path)
                    .map_err(FullDayStreamError::Corpus)?,
                dt_prev_ms: raw_scalar(&batch, 13, entry.source_profile, row, &path)
                    .map_err(FullDayStreamError::Corpus)?,
                raw_spread_bps_bits: typed_array::<Float64Array>(&batch, 15, &path)
                    .map_err(FullDayStreamError::Corpus)?
                    .value(row)
                    .to_bits(),
                source_profile: entry.source_profile,
                state,
            };
            census.ordinary_rows = census
                .ordinary_rows
                .checked_add(1)
                .ok_or(FullDayStreamError::Corpus(CorpusError::ArithmeticOverflow))?;
            match domain {
                StockQuoteDomain::Premarket => census.premarket_rows += 1,
                StockQuoteDomain::Rth => census.rth_rows += 1,
                StockQuoteDomain::AfterHours => census.after_hours_rows += 1,
                StockQuoteDomain::OutsideDomain => census.outside_domain_rows += 1,
            };
            match state {
                StockQuoteState::Normal => census.normal_rows += 1,
                StockQuoteState::Locked => census.locked_rows += 1,
                StockQuoteState::Crossed => census.crossed_rows += 1,
                StockQuoteState::BidOnly => census.bid_only_rows += 1,
                StockQuoteState::AskOnly => census.ask_only_rows += 1,
                StockQuoteState::BothSidesAbsent => census.both_sides_absent_rows += 1,
                StockQuoteState::Invalid => census.invalid_rows += 1,
            };
            if entry.source_profile == SourceProfile::CentInt32 {
                census.compact_rows += 1
            } else {
                census.wide_rows += 1
            };
            if domain == StockQuoteDomain::Rth {
                if pending
                    .timestamp_ms
                    .is_some_and(|value| value != timestamp_ms)
                {
                    finish_pending_group(&mut pending, &mut legacy, entry, &clock, &path)
                        .map_err(FullDayStreamError::Corpus)?;
                }
                if pending.timestamp_ms.is_none() {
                    pending.timestamp_ms = Some(timestamp_ms);
                }
                let raw_bid_size = raw_i64(&batch, 1, entry.source_profile, row, &path)
                    .map_err(FullDayStreamError::Corpus)?
                    .ok_or(FullDayStreamError::Corpus(CorpusError::DecodeFailed {
                        path: path.clone(),
                        detail: "RTH_NULL",
                    }))?;
                let raw_ask_size = raw_i64(&batch, 5, entry.source_profile, row, &path)
                    .map_err(FullDayStreamError::Corpus)?
                    .ok_or(FullDayStreamError::Corpus(CorpusError::DecodeFailed {
                        path: path.clone(),
                        detail: "RTH_NULL",
                    }))?;
                add_member(
                    &mut pending,
                    raw_bid_size,
                    bid.unwrap_or(0),
                    member.bid_condition.unwrap_or(0),
                    raw_ask_size,
                    ask.unwrap_or(0),
                    member.ask_condition.unwrap_or(0),
                )
                .map_err(FullDayStreamError::Corpus)?;
            }
            members.push(member);
        }
    }
    if trailer.is_none() || census.null_trailer_rows != 1 {
        return Err(FullDayStreamError::Corpus(CorpusError::ContentMismatch {
            path: path.clone(),
            detail: "SENTINEL_COUNT",
        }));
    }
    if census.ordinary_rows != 0
        && (0..5).any(|bit| {
            census
                .derivative_null_mask_counts
                .iter()
                .enumerate()
                .filter(|(mask, _)| mask & (1 << bit) != 0)
                .map(|(_, count)| *count)
                .sum::<u64>()
                != 1
        })
    {
        return Err(FullDayStreamError::Corpus(CorpusError::ContentMismatch {
            path: path.clone(),
            detail: "DERIVATIVE_NULL_SENTINELS",
        }));
    }
    if let Some((_, start, domain, event_time_b, event_time_a)) = current {
        members.sort_by(member_compare);
        // The sentinel LEADS every real file (all 1,508), so `trailer` is
        // `Some(0)` and `trailer.unwrap_or(..)` made this final flush emit
        // `start..0` — a REVERSED range whose `len()` is 0. The last batch of
        // every session silently reported zero source rows.
        //
        // The mid-stream emit at :1377 was always correct (`start..ordinal`);
        // only this flush carried the trailing-sentinel assumption. The end of
        // the final batch is the row counter, always — the sentinel's position
        // has nothing to do with it.
        let stop = row_ordinal;
        let post_set = post_set(&members);
        emit(FullDayQuoteItem::Batch(FullDayQuoteBatch {
            event_time_b,
            event_time_a,
            source_rows: start..stop,
            domain,
            members,
            post_set,
        }))
        .map_err(FullDayStreamError::Emit)?;
        census.batch_count = census
            .batch_count
            .checked_add(1)
            .ok_or(FullDayStreamError::Corpus(CorpusError::ArithmeticOverflow))?;
    }
    emit(FullDayQuoteItem::NullTrailer {
        row_ordinal: trailer.unwrap_or(0),
    })
    .map_err(FullDayStreamError::Emit)?;
    finish_pending_group(&mut pending, &mut legacy, entry, &clock, &path)
        .map_err(FullDayStreamError::Corpus)?;
    if census.rth_rows != entry.raw_rth_row_count
        || legacy.len()
            != usize::try_from(entry.complete_group_count)
                .map_err(|_| FullDayStreamError::Corpus(CorpusError::ArithmeticOverflow))?
    {
        return Err(FullDayStreamError::Corpus(CorpusError::ContentMismatch {
            path,
            detail: "FULL_DAY_LEGACY_COUNTS",
        }));
    }
    Ok(FullDaySessionSummary {
        day: entry.day,
        legacy_rth: SessionData {
            day: entry.day,
            session_start_ns: entry.session_start_ns,
            session_end_ns: entry.session_end_ns,
            expected_bar_count: entry.expected_bar_count,
            source_sha256: entry.source_sha256,
            groups: legacy,
        },
        census,
    })
}

/// Authenticates and decodes one registered session's NBBO quotes.
///
/// `corpus_root` is the `IWM` directory containing `<year>/<day>.parquet`
/// files (see the crate-level docs). The source file's size and content
/// sha256 are checked against the registry entry before decoding — this is
/// the per-session half of the corpus's plain-sha256 integrity model; the
/// registry's own digest is checked separately by
/// [`crate::authenticate_registry`].
///
/// # Errors
///
/// Returns [`CorpusError::UnknownSession`] if `day` is not registered,
/// [`CorpusError::SourceAuthenticationFailed`] if the on-disk file's size or
/// digest differs from the registry, or a decode/schema/order/content error
/// if the parquet payload doesn't match the registry's declared shape.
pub fn load_session(day: &str, corpus_root: &Path) -> Result<SessionData> {
    match stream_full_day_session(day, corpus_root, |_| Ok::<(), std::convert::Infallible>(())) {
        Ok(summary) => Ok(summary.legacy_rth),
        Err(FullDayStreamError::Corpus(error)) => Err(error),
        Err(FullDayStreamError::Emit(never)) => match never {},
    }
}

/// Authenticates and projects one registered session's native group clock.
/// Complexity: `O(source bytes + rows)` time and `O(complete groups)` memory.
pub fn load_group_times_measured(
    day: &str,
    corpus_root: &Path,
) -> Result<(SessionGroupTimes, SessionGroupTimesMeasurement)> {
    load_group_times_measured_with_batch_size(day, corpus_root, DECODE_BATCH_ROWS)
}

/// Test seam for proving that reader chunking cannot change group-clock bytes.
/// Complexity: `O(source bytes + rows)` time and `O(complete groups)` memory.
fn load_group_times_measured_with_batch_size(
    day: &str,
    corpus_root: &Path,
    batch_rows: usize,
) -> Result<(SessionGroupTimes, SessionGroupTimesMeasurement)> {
    if batch_rows == 0 {
        return Err(CorpusError::ArithmeticOverflow);
    }
    let authentication_started = Instant::now();
    let (entry, path) = authenticated_source_path(day, corpus_root)?;
    let source_authentication_ns = u64::try_from(authentication_started.elapsed().as_nanos())
        .map_err(|_| CorpusError::ArithmeticOverflow)?;
    let file = File::open(&path).map_err(|source| CorpusError::Io {
        path: path.clone(),
        source,
    })?;
    let decode_started = Instant::now();
    let ts_ns = decode_group_times(file, &path, entry, batch_rows)?;
    let timestamp_decode_ns = u64::try_from(decode_started.elapsed().as_nanos())
        .map_err(|_| CorpusError::ArithmeticOverflow)?;
    Ok((
        SessionGroupTimes {
            day: entry.day,
            session_start_ns: entry.session_start_ns,
            session_end_ns: entry.session_end_ns,
            expected_bar_count: entry.expected_bar_count,
            source_sha256: entry.source_sha256,
            ts_ns,
        },
        SessionGroupTimesMeasurement {
            source_authentication_ns,
            timestamp_decode_ns,
        },
    ))
}

/// Authenticates and projects one registered session's native group clock.
/// Complexity: `O(source bytes + rows)` time and `O(complete groups)` memory.
pub fn load_group_times(day: &str, corpus_root: &Path) -> Result<SessionGroupTimes> {
    load_group_times_measured(day, corpus_root).map(|(times, _)| times)
}

/// Testable batch seam for the timestamp-only structural projection.
/// Complexity: `O(source bytes + rows)` time and `O(complete groups)` memory.
pub fn load_group_times_with_batch_size(
    day: &str,
    corpus_root: &Path,
    batch_rows: usize,
) -> Result<SessionGroupTimes> {
    if batch_rows == 0 {
        return Err(CorpusError::DecodeFailed {
            path: corpus_root.to_path_buf(),
            detail: "BATCH_ROWS_ZERO",
        });
    }
    load_group_times_measured_with_batch_size(day, corpus_root, batch_rows).map(|(times, _)| times)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::registry;
    use std::path::PathBuf;

    /// The CSR invariant holds from DEFAULT construction, not only from
    /// `with_capacity`: offsets carry `len() + 1` entries at every group
    /// count, including zero. Failed before the 2026-08-05 manual `Default`
    /// (derived Default seeded `[]`, so every real-session projection came
    /// out one offset short and the F02 materializer refused `WrongRowCount`).
    #[test]
    fn default_accumulator_offsets_carry_the_leading_zero() {
        let empty = QuoteGroupAccumulator::default()
            .finish()
            .expect("empty finish");
        assert_eq!(empty.len(), 0);
        assert_eq!(empty.scientific_midpoint_offsets, vec![0]);
        assert_eq!(empty.wide_midpoint_offsets, vec![0]);

        let mut accumulator = QuoteGroupAccumulator::default();
        // Two members in one millisecond group, then one in a later group.
        accumulator
            .add_raw_member(1_000, 1_000_000_000, 100, 200_000_000, 0, 100, 200_010_000, 0)
            .expect("member 1");
        accumulator
            .add_raw_member(1_000, 1_000_000_000, 100, 200_000_000, 0, 100, 200_010_000, 0)
            .expect("member 2");
        accumulator
            .add_raw_member(2_000, 2_000_000_000, 100, 200_020_000, 0, 100, 200_030_000, 0)
            .expect("member 3");
        let groups = accumulator.finish().expect("finish");
        assert_eq!(groups.len(), 2);
        assert_eq!(groups.scientific_midpoint_offsets.len(), groups.len() + 1);
        assert_eq!(groups.wide_midpoint_offsets.len(), groups.len() + 1);
    }

    fn corpus_root() -> PathBuf {
        PathBuf::from("/workspace/data/tokens/stock_quotes/IWM")
    }

    // IWM traded in the low-to-mid $200s on 2022-01-03; u6 scale is dollars *
    // 1_000_000. A wide but scale-correct band (checked against the real file
    // directly, not the orchestrator's initial $30-60 guess, which was the
    // wrong order of magnitude for this ticker/date) catches a scaling
    // regression without being brittle to the exact tick range.
    const PLAUSIBLE_MIN_U6: i64 = 100_000_000; // $100
    const PLAUSIBLE_MAX_U6: i64 = 500_000_000; // $500

    /// The one real-corpus test the task requires: load 2022-01-03 and check
    /// the decoded quote stream is sane. Skips (rather than fails) if the
    /// read-only corpus mount isn't present in this environment.
    #[test]
    fn loads_a_real_session_with_monotone_timestamps_and_plausible_prices() {
        let root = corpus_root();
        if !root.is_dir() {
            eprintln!("skipping: corpus root {} is not mounted", root.display());
            return;
        }
        registry::authenticate_registry(&root).expect("registry authenticates");

        let session = load_session("2022-01-03", &root).expect("real session decodes");
        assert_eq!(session.day, "2022-01-03");
        assert_eq!(session.expected_bar_count, 390);

        let groups = &session.groups;
        assert!(
            session.quote_count() > 0,
            "session must have at least one quote group"
        );
        assert_eq!(
            groups.len() as u64,
            registry::lookup("2022-01-03").unwrap().complete_group_count
        );

        assert!(
            groups.ts_ns.windows(2).all(|pair| pair[0] <= pair[1]),
            "group timestamps must be monotone"
        );
        assert!(
            groups
                .ts_ns
                .iter()
                .all(|&ts| ts >= session.session_start_ns && ts < session.session_end_ns)
        );

        let mut checked_any = false;
        for index in 0..groups.len() {
            for &mid in groups
                .scientific_midpoints(index)
                .iter()
                .chain(groups.wide_midpoints(index))
            {
                assert!(
                    (PLAUSIBLE_MIN_U6..=PLAUSIBLE_MAX_U6).contains(&mid),
                    "midpoint {mid} (u6) out of plausible range for IWM"
                );
                checked_any = true;
            }
        }
        assert!(
            checked_any,
            "expected at least one resolved midpoint in the session"
        );
    }

    #[test]
    fn group_times_matches_full_decoder_across_profiles_density_and_clocks() {
        use arrow_array::{ArrayRef, Float64Array};
        use arrow_schema::{Field, Schema};
        use parquet::arrow::ArrowWriter;
        use parquet::file::properties::{EnabledStatistics, WriterProperties};
        use std::sync::Arc;

        fn write_clock_fixture(path: &Path, timestamps: &[Option<i64>], partial_null: bool) {
            let fields = ALL_FIELDS
                .iter()
                .enumerate()
                .map(|(index, name)| {
                    Field::new(*name, expected_type(SourceProfile::CentInt32, index), true)
                })
                .collect::<Vec<_>>();
            let schema = Arc::new(Schema::new(fields));
            let columns = (0..ALL_FIELDS.len())
                .map(|index| -> ArrayRef {
                    if index == 0 {
                        return Arc::new(TimestampMillisecondArray::from(timestamps.to_vec()));
                    }
                    let present = timestamps
                        .iter()
                        .map(|timestamp| {
                            if timestamp.is_some() || (partial_null && index == 1) {
                                Some(index as i64 + 1)
                            } else {
                                None
                            }
                        })
                        .collect::<Vec<_>>();
                    match expected_type(SourceProfile::CentInt32, index) {
                        DataType::Int32 => Arc::new(Int32Array::from(
                            present
                                .iter()
                                .map(|value| value.map(|item| item as i32))
                                .collect::<Vec<_>>(),
                        )),
                        DataType::Int64 => Arc::new(Int64Array::from(present)),
                        DataType::Float64 => Arc::new(Float64Array::from(
                            present
                                .iter()
                                .map(|value| value.map(|item| item as f64))
                                .collect::<Vec<_>>(),
                        )),
                        other => panic!("unexpected fixture type {other:?}"),
                    }
                })
                .collect::<Vec<_>>();
            let batch = RecordBatch::try_new(Arc::clone(&schema), columns).expect("fixture batch");
            let file = File::create(path).expect("fixture parquet");
            let properties = WriterProperties::builder()
                .set_statistics_enabled(EnabledStatistics::None)
                .build();
            let mut writer = ArrowWriter::try_new(file, schema, Some(properties))
                .expect("fixture writer without footer null statistics");
            writer.write(&batch).expect("fixture rows");
            writer.close().expect("fixture footer");
        }

        fn entry(raw_rows: u64, groups: u64) -> RegistryEntry {
            let clock = SessionClock::for_day("2024-03-11").expect("EDT clock");
            RegistryEntry {
                day: "2024-03-11",
                session_start_ns: clock.session_start_a().ns(),
                session_end_ns: clock.session_end_a().ns(),
                expected_bar_count: 390,
                source_relative_path: "fixture.parquet",
                source_sha256: "fixture",
                source_size_bytes: 0,
                source_profile: SourceProfile::CentInt32,
                raw_rth_row_count: raw_rows,
                complete_group_count: groups,
            }
        }

        let root = corpus_root();
        if !root.is_dir() {
            eprintln!("GROUP_TIMES_CORPUS_UNAVAILABLE root={}", root.display());
            return;
        }
        for day in [
            "2024-05-10",
            "2025-09-15",
            "2022-01-06",
            "2024-03-08",
            "2024-03-11",
            "2024-11-29",
        ] {
            let full = load_session(day, &root).expect("full session decodes");
            let times = load_group_times(day, &root).expect("group times decode");
            assert_eq!(times.day, full.day);
            assert_eq!(times.session_start_ns, full.session_start_ns);
            assert_eq!(times.session_end_ns, full.session_end_ns);
            assert_eq!(times.expected_bar_count, full.expected_bar_count);
            assert_eq!(times.source_sha256, full.source_sha256);
            assert_eq!(times.ts_ns, full.groups.ts_ns);
        }

        let (small, _) = load_group_times_measured_with_batch_size("2024-05-10", &root, 4_097)
            .expect("small-batch group times decode");
        let (large, _) = load_group_times_measured_with_batch_size("2024-05-10", &root, 65_537)
            .expect("large-batch group times decode");
        assert_eq!(small, large);

        let clock = SessionClock::for_day("2024-03-11").expect("EDT clock");
        let open_ms = clock.open_b().ns() / 1_000_000;
        let fixture_root = std::env::temp_dir().join(format!(
            "corpus_group_times_contract_{}",
            std::process::id()
        ));
        std::fs::create_dir_all(&fixture_root).expect("fixture root");

        let valid_path = fixture_root.join("valid.parquet");
        write_clock_fixture(
            &valid_path,
            &[None, Some(open_ms), Some(open_ms + 1)],
            false,
        );
        assert_eq!(
            decode_group_times(
                File::open(&valid_path).expect("valid fixture"),
                &valid_path,
                entry(2, 2),
                1,
            )
            .expect("full-schema timestamp projection"),
            vec![
                clock
                    .to_frame_a(FrameB::from_naive_et_ms(open_ms).expect("open frame B"))
                    .expect("open frame A")
                    .ns(),
                clock
                    .to_frame_a(FrameB::from_naive_et_ms(open_ms + 1).expect("next frame B"))
                    .expect("next frame A")
                    .ns(),
            ]
        );

        let partial_path = fixture_root.join("partial-null.parquet");
        write_clock_fixture(&partial_path, &[None, Some(open_ms)], true);
        assert!(matches!(
            decode_group_times(
                File::open(&partial_path).expect("partial fixture"),
                &partial_path,
                entry(1, 1),
                1,
            ),
            Err(CorpusError::DecodeFailed {
                detail: "PARTIAL_NULL_SENTINEL",
                ..
            })
        ));

        let duplicate_path = fixture_root.join("duplicate-sentinel.parquet");
        write_clock_fixture(&duplicate_path, &[None, None, Some(open_ms)], false);
        assert!(matches!(
            decode_group_times(
                File::open(&duplicate_path).expect("duplicate fixture"),
                &duplicate_path,
                entry(1, 1),
                1,
            ),
            Err(CorpusError::ContentMismatch {
                detail: "SENTINEL_COUNT",
                ..
            })
        ));

        let order_path = fixture_root.join("out-of-order.parquet");
        write_clock_fixture(
            &order_path,
            &[None, Some(open_ms + 1), Some(open_ms)],
            false,
        );
        assert!(matches!(
            decode_group_times(
                File::open(&order_path).expect("order fixture"),
                &order_path,
                entry(2, 2),
                1,
            ),
            Err(CorpusError::OutOfOrder { .. })
        ));

        let close_ms = clock.close_b().ns() / 1_000_000;
        for (label, malformed_ms) in [
            (
                "utc-as-naive",
                vec![
                    clock.session_start_a().ns() / 1_000_000,
                    clock.session_end_a().ns() / 1_000_000 - 1,
                ],
            ),
            (
                "double-converted",
                vec![open_ms + 8 * 3_600_000, close_ms - 1 + 8 * 3_600_000],
            ),
            (
                "one-hour-early",
                vec![open_ms - 3_600_000, close_ms - 1 - 3_600_000],
            ),
            (
                "four-hours-late",
                vec![open_ms + 4 * 3_600_000, close_ms - 1 + 4 * 3_600_000],
            ),
            (
                "five-hours-late",
                vec![open_ms + 5 * 3_600_000, close_ms - 1 + 5 * 3_600_000],
            ),
        ] {
            let path = fixture_root.join(format!("{label}.parquet"));
            write_clock_fixture(
                &path,
                &[None, Some(malformed_ms[0]), Some(malformed_ms[1])],
                false,
            );
            assert!(matches!(
                decode_group_times(
                    File::open(&path).expect("clock fixture"),
                    &path,
                    entry(2, 2),
                    1,
                ),
                Err(CorpusError::ContentMismatch {
                    detail: "RTH_ROW_COUNT",
                    ..
                })
            ));
        }
        std::fs::remove_dir_all(fixture_root).expect("remove clock fixtures");
    }
}
