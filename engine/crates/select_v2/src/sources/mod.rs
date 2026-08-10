//! **The SOURCES layer: six calendar-bounded token readers.**
//!
//! The `corpus` crate decodes exactly one modality (IWM stock quotes) and its
//! `QuoteGroups` keep only midpoints — the raw bid/ask/size state that families
//! D1/B2/E2/E3 need is dropped. This module is the replacement: thin, typed,
//! streaming parquet readers over all six token corpora, retaining raw fields.
//!
//! Three properties hold for every reader here:
//!
//! 1. **Calendar-bounded.** Every constructor takes a
//!    [`crate::calendar::DayScope`], which only [`crate::calendar::admit`] can
//!    mint, and it only mints for the 1,003 registry sessions. A path is formed
//!    *from* the scope, so an unadmitted day is refused before any filesystem
//!    call. This is what seals 2026 and the 2020-2021 warmup across all six
//!    corpora at once.
//! 2. **Frame B in, frame B out.** Token parquet timestamps are naive-ET
//!    (frame B). The RTH filter is the scope's own half-open frame-B window,
//!    applied before any conversion. Nothing here produces frame A except
//!    through [`corpus::SessionClock`].
//! 3. **u6 prices.** Every price is normalized to dollars x 1,000,000, the
//!    same fixed point `corpus` uses, so the two on-disk encodings compare
//!    directly.
//!
//! ## Measured on-disk profiles (2026 excluded from every scan)
//!
//! Schema signatures were sampled at three days per year per corpus,
//! 2020-2025:
//!
//! | corpus | profiles seen | price encoding |
//! |---|---|---|
//! | `stock_quotes` | 2 (registry `source_profile`) | `Int32` cents / `Float64` dollars |
//! | `stock_trades` | 1 | `Float64` dollars |
//! | `options_prints` IWM | 1 compact | `Int32` cents, strike `Int32` mills |
//! | `options_prints` RUTW | 1 wide | `Float64` dollars, strike `Float64` dollars |
//! | `option_quotes` IWM | 2 (compact -> wide during 2024) | as above |
//! | `option_quotes` RUTW | 1 wide | as above |
//!
//! Because sampling is not proof over 1,383 files, the readers **detect the
//! profile from the file's own arrow schema at open** and refuse anything
//! outside the admitted set, naming the path. The one exception is
//! `stock_quotes`, whose profile is authoritative in the registry row (and is
//! *not* chronologically monotone: 2025-12-30 is `cent_int32` while 2025-12-31
//! is `dollar_float64`).
//!
//! ## The `mid` column is never read
//!
//! Measured: in the `CentInt32` profile the vendor `mid` column is
//! `bid + ask` (a SUM: 20208 + 20211 = 40419), while in the `DollarFloat64`
//! profile it is the true midpoint ((175.35 + 175.39) / 2 = 175.37). The same
//! split exists in `option_quotes`. Midpoints in this crate are always computed
//! as `(bid_u6 + ask_u6) / 2`.

pub mod option_quotes;
pub mod options_prints;
pub mod rutw;
pub mod stock_quotes;
pub mod stock_trades;

use crate::calendar::DayScope;
use crate::error::{Result, SelectV2Error};
use arrow_array::{
    Array, Date32Array, DictionaryArray, Float64Array, Int8Array, Int32Array, Int64Array,
    LargeStringArray, RecordBatch, StringArray, TimestampMillisecondArray, UInt32Array,
    types::UInt32Type,
};
use arrow_schema::{DataType, TimeUnit};
use parquet::arrow::arrow_reader::ParquetRecordBatchReaderBuilder;
use parquet::file::statistics::Statistics;
use std::fs::File;
use std::path::{Path, PathBuf};

/// Rows decoded per parquet batch. Matches `corpus`'s own decode batch size.
pub const DECODE_BATCH_ROWS: usize = 65_536;

/// Default token corpora root in this workspace.
pub const DEFAULT_TOKENS_ROOT: &str = "/workspace/data/tokens";

/// Resolves the six corpus roots under one token tree.
#[derive(Clone, Debug)]
pub struct TokenRoots {
    root: PathBuf,
}

impl TokenRoots {
    /// Wraps a token tree root (`/workspace/data/tokens`).
    pub fn new(root: impl Into<PathBuf>) -> Self {
        Self { root: root.into() }
    }

    /// The tree root itself.
    #[must_use]
    pub fn root(&self) -> &Path {
        &self.root
    }

    /// IWM NBBO stock quotes — also the `corpus` crate's corpus root.
    #[must_use]
    pub fn stock_quotes(&self) -> PathBuf {
        self.root.join("stock_quotes").join("IWM")
    }

    /// IWM stock prints.
    #[must_use]
    pub fn stock_trades(&self) -> PathBuf {
        self.root.join("stock_trades").join("IWM")
    }

    /// IWM option prints (62 columns; full 1,003-session coverage).
    #[must_use]
    pub fn options_prints(&self) -> PathBuf {
        self.root.join("options_prints").join("IWM")
    }

    /// IWM option NBBO quotes (starts 2022-11-01 — the F-12 era mask).
    #[must_use]
    pub fn option_quotes(&self) -> PathBuf {
        self.root.join("option_quotes").join("IWM")
    }

    /// RUTW option prints.
    #[must_use]
    pub fn rutw_options_prints(&self) -> PathBuf {
        self.root.join("RUTW").join("options_prints")
    }

    /// RUTW option NBBO quotes.
    #[must_use]
    pub fn rutw_option_quotes(&self) -> PathBuf {
        self.root.join("RUTW").join("option_quotes")
    }
}

impl Default for TokenRoots {
    fn default() -> Self {
        Self::new(DEFAULT_TOKENS_ROOT)
    }
}

/// `<corpus_root>/<YYYY>/<YYYY-MM-DD>.parquet` for an ADMITTED session.
#[must_use]
pub fn day_file(corpus_root: &Path, scope: &DayScope) -> PathBuf {
    corpus_root
        .join(scope.year())
        .join(format!("{}.parquet", scope.day()))
}

/// Every parquet shard for an admitted session, covering both on-disk layouts
/// measured in this tree:
///
/// * flat — `<root>/<YYYY>/<day>.parquet` (IWM option quotes through mid-2024,
///   all prints corpora);
/// * per-expiry sharded — `<root>/<YYYY>/<day>/exp<YYYY-MM-DD>.parquet` (IWM
///   option quotes from late 2024, all RUTW option quotes).
///
/// Shards are returned in sorted order so a pass over them is deterministic.
///
/// # Errors
///
/// [`SelectV2Error::ModalityAbsent`] if neither layout exists for the session,
/// or [`SelectV2Error::Io`] if the shard directory cannot be listed.
pub fn day_shards(
    corpus_root: &Path,
    scope: &DayScope,
    modality: &'static str,
) -> Result<Vec<PathBuf>> {
    let flat = day_file(corpus_root, scope);
    if flat.is_file() {
        return Ok(vec![flat]);
    }
    let sharded = corpus_root.join(scope.year()).join(scope.day());
    if sharded.is_dir() {
        let mut shards: Vec<PathBuf> = std::fs::read_dir(&sharded)
            .map_err(|source| SelectV2Error::Io {
                path: sharded.clone(),
                source,
            })?
            .filter_map(|entry| entry.ok().map(|entry| entry.path()))
            .filter(|path| path.extension().is_some_and(|ext| ext == "parquet"))
            .collect();
        shards.sort();
        if !shards.is_empty() {
            return Ok(shards);
        }
    }
    Err(SelectV2Error::ModalityAbsent {
        modality,
        day: scope.day().to_owned(),
        path: flat,
    })
}

/// Opens a parquet file with arrow metadata skipped (the corpus convention).
///
/// # Errors
///
/// [`SelectV2Error::Io`] if the file cannot be opened or its footer read.
pub fn open_builder(path: &Path) -> Result<ParquetRecordBatchReaderBuilder<File>> {
    let file = File::open(path).map_err(|source| SelectV2Error::Io {
        path: path.to_path_buf(),
        source,
    })?;
    let options = parquet::arrow::arrow_reader::ArrowReaderOptions::new().with_skip_arrow_metadata(true);
    ParquetRecordBatchReaderBuilder::try_new_with_options(file, options).map_err(|source| {
        SelectV2Error::Io {
            path: path.to_path_buf(),
            source: std::io::Error::other(source),
        }
    })
}

/// Row groups whose `timestamp` statistics can overlap the session's frame-B
/// RTH window. Falls back to "keep everything" when statistics are absent —
/// pruning is a speed lever, never a correctness one.
#[must_use]
pub fn rth_row_groups(
    builder: &ParquetRecordBatchReaderBuilder<File>,
    timestamp_column: usize,
    scope: &DayScope,
) -> Vec<usize> {
    let metadata = builder.metadata();
    let open_ms = scope.open_ms_b();
    let close_ms = scope.close_ms_b();
    let mut keep = Vec::with_capacity(metadata.num_row_groups());
    for index in 0..metadata.num_row_groups() {
        let group = metadata.row_group(index);
        let Some(Statistics::Int64(stats)) = group.column(timestamp_column).statistics() else {
            return (0..metadata.num_row_groups()).collect();
        };
        match (stats.min_opt(), stats.max_opt()) {
            (Some(&min), Some(&max)) => {
                if max >= open_ms && min < close_ms {
                    keep.push(index);
                }
            }
            _ => return (0..metadata.num_row_groups()).collect(),
        }
    }
    keep
}

/// An integer column whose on-disk width varies by profile.
pub(crate) enum IntCol<'a> {
    I8(&'a Int8Array),
    I32(&'a Int32Array),
    I64(&'a Int64Array),
    U32(&'a UInt32Array),
}

impl IntCol<'_> {
    pub(crate) fn is_null(&self, row: usize) -> bool {
        match self {
            Self::I8(values) => values.is_null(row),
            Self::I32(values) => values.is_null(row),
            Self::I64(values) => values.is_null(row),
            Self::U32(values) => values.is_null(row),
        }
    }

    pub(crate) fn value(&self, row: usize) -> i64 {
        match self {
            Self::I8(values) => i64::from(values.value(row)),
            Self::I32(values) => i64::from(values.value(row)),
            Self::I64(values) => values.value(row),
            Self::U32(values) => i64::from(values.value(row)),
        }
    }
}

/// A price column: integer minor units, or `Float64` dollars.
pub(crate) enum PriceCol<'a> {
    /// Integer cents; u6 = value x 10,000.
    CentI32(&'a Int32Array),
    /// Integer cents in a 64-bit column.
    CentI64(&'a Int64Array),
    /// Integer mills (strike convention); u6 = value x 1,000.
    MillI32(&'a Int32Array),
    /// Dollars; u6 = round(value x 1,000,000).
    DollarF64(&'a Float64Array),
}

impl PriceCol<'_> {
    pub(crate) fn is_null(&self, row: usize) -> bool {
        match self {
            Self::CentI32(values) | Self::MillI32(values) => values.is_null(row),
            Self::CentI64(values) => values.is_null(row),
            Self::DollarF64(values) => values.is_null(row),
        }
    }

    /// Normalizes to u6 (dollars x 1,000,000).
    ///
    /// # Errors
    ///
    /// [`SelectV2Error::ContentMismatch`] if the value cannot be represented.
    pub(crate) fn u6(&self, row: usize, path: &Path) -> Result<i64> {
        match self {
            Self::CentI32(values) => i64::from(values.value(row))
                .checked_mul(10_000)
                .ok_or(SelectV2Error::Arithmetic("PriceCol::u6 cents")),
            Self::CentI64(values) => values
                .value(row)
                .checked_mul(10_000)
                .ok_or(SelectV2Error::Arithmetic("PriceCol::u6 cents")),
            Self::MillI32(values) => i64::from(values.value(row))
                .checked_mul(1_000)
                .ok_or(SelectV2Error::Arithmetic("PriceCol::u6 mills")),
            Self::DollarF64(values) => dollars_to_u6(values.value(row), path),
        }
    }
}

/// Text column: plain, large, or dictionary-encoded UTF-8.
pub(crate) enum TextCol<'a> {
    Utf8(&'a StringArray),
    LargeUtf8(&'a LargeStringArray),
    Dict32(&'a DictionaryArray<UInt32Type>, &'a StringArray),
}

impl TextCol<'_> {
    pub(crate) fn is_null(&self, row: usize) -> bool {
        match self {
            Self::Utf8(values) => values.is_null(row),
            Self::LargeUtf8(values) => values.is_null(row),
            Self::Dict32(keys, _) => keys.is_null(row),
        }
    }

    pub(crate) fn value(&self, row: usize) -> &str {
        match self {
            Self::Utf8(values) => values.value(row),
            Self::LargeUtf8(values) => values.value(row),
            Self::Dict32(keys, dictionary) => {
                dictionary.value(usize::try_from(keys.keys().value(row)).unwrap_or(0))
            }
        }
    }
}

/// A calendar-date column: `Date32` days-since-epoch, or an ISO text date.
pub(crate) enum DateCol<'a> {
    Date32(&'a Date32Array),
    Text(TextCol<'a>),
}

impl DateCol<'_> {
    pub(crate) fn is_null(&self, row: usize) -> bool {
        match self {
            Self::Date32(values) => values.is_null(row),
            Self::Text(values) => values.is_null(row),
        }
    }

    /// Days since the Unix epoch.
    ///
    /// # Errors
    ///
    /// [`SelectV2Error::ContentMismatch`] if a text date is not ISO
    /// `YYYY-MM-DD`.
    pub(crate) fn day_ordinal(&self, row: usize, path: &Path) -> Result<i32> {
        match self {
            Self::Date32(values) => Ok(values.value(row)),
            Self::Text(values) => {
                let text = values.value(row);
                let civil = corpus::CivilDate::parse(text).map_err(|_| {
                    SelectV2Error::ContentMismatch {
                        path: path.to_path_buf(),
                        detail: format!("expiration {text} is not an ISO civil date"),
                    }
                })?;
                i32::try_from(civil.unix_day_ordinal()).map_err(|_| {
                    SelectV2Error::ContentMismatch {
                        path: path.to_path_buf(),
                        detail: format!("expiration {text} does not fit a day ordinal"),
                    }
                })
            }
        }
    }
}

/// Scales dollars to u6, refusing anything that is not within half a u6 unit
/// of an integer (a corrupt or wrongly-scaled column, not a real price).
///
/// # Errors
///
/// [`SelectV2Error::ContentMismatch`] on a non-finite or unrepresentable value.
pub(crate) fn dollars_to_u6(value: f64, path: &Path) -> Result<i64> {
    const I64_LIMIT: f64 = 9_223_372_036_854_775_808.0;
    let scaled = value * 1_000_000.0;
    if !value.is_finite() || !scaled.is_finite() || !(-I64_LIMIT..I64_LIMIT).contains(&scaled) {
        return Err(SelectV2Error::ContentMismatch {
            path: path.to_path_buf(),
            detail: format!("price {value} does not normalize to u6"),
        });
    }
    // Checked into the exactly-representable i64 range immediately above.
    #[allow(clippy::cast_possible_truncation)]
    Ok(scaled.round_ties_even() as i64)
}

pub(crate) fn typed<'a, T: Array + 'static>(
    batch: &'a RecordBatch,
    index: usize,
    path: &Path,
    what: &'static str,
) -> Result<&'a T> {
    batch
        .column(index)
        .as_any()
        .downcast_ref::<T>()
        .ok_or_else(|| SelectV2Error::SchemaMismatch {
            path: path.to_path_buf(),
            detail: format!(
                "column {index} ({what}) is {:?}, not the admitted arrow type",
                batch.column(index).data_type()
            ),
        })
}

pub(crate) fn timestamp_col<'a>(
    batch: &'a RecordBatch,
    index: usize,
    path: &Path,
) -> Result<&'a TimestampMillisecondArray> {
    match batch.column(index).data_type() {
        DataType::Timestamp(TimeUnit::Millisecond, None) => {}
        other => {
            return Err(SelectV2Error::SchemaMismatch {
                path: path.to_path_buf(),
                detail: format!(
                    "column {index} is {other:?}; token timestamps must be naive \
                     millisecond (frame B) with no timezone"
                ),
            });
        }
    }
    typed::<TimestampMillisecondArray>(batch, index, path, "timestamp")
}

pub(crate) fn int_col<'a>(batch: &'a RecordBatch, index: usize, path: &Path) -> Result<IntCol<'a>> {
    Ok(match batch.column(index).data_type() {
        DataType::Int8 => IntCol::I8(typed(batch, index, path, "int8")?),
        DataType::Int32 => IntCol::I32(typed(batch, index, path, "int32")?),
        DataType::Int64 => IntCol::I64(typed(batch, index, path, "int64")?),
        DataType::UInt32 => IntCol::U32(typed(batch, index, path, "uint32")?),
        other => {
            return Err(SelectV2Error::SchemaMismatch {
                path: path.to_path_buf(),
                detail: format!("column {index} is {other:?}, not an admitted integer type"),
            });
        }
    })
}

pub(crate) fn float_col<'a>(
    batch: &'a RecordBatch,
    index: usize,
    path: &Path,
) -> Result<&'a Float64Array> {
    typed::<Float64Array>(batch, index, path, "float64")
}

/// A price column, profile-detected: `Int32`/`Int64` are cents,
/// `Float64` is dollars.
pub(crate) fn price_col<'a>(
    batch: &'a RecordBatch,
    index: usize,
    path: &Path,
) -> Result<PriceCol<'a>> {
    Ok(match batch.column(index).data_type() {
        DataType::Int32 => PriceCol::CentI32(typed(batch, index, path, "cent int32")?),
        DataType::Int64 => PriceCol::CentI64(typed(batch, index, path, "cent int64")?),
        DataType::Float64 => PriceCol::DollarF64(typed(batch, index, path, "dollar float64")?),
        other => {
            return Err(SelectV2Error::SchemaMismatch {
                path: path.to_path_buf(),
                detail: format!("column {index} is {other:?}, not an admitted price type"),
            });
        }
    })
}

/// A strike column: `Int32` mills (IWM compact profile) or `Float64`/`Int64`
/// dollars (RUTW and the late IWM option-quote profile).
pub(crate) fn strike_col<'a>(
    batch: &'a RecordBatch,
    index: usize,
    path: &Path,
) -> Result<PriceCol<'a>> {
    Ok(match batch.column(index).data_type() {
        DataType::Int32 => PriceCol::MillI32(typed(batch, index, path, "mill int32")?),
        DataType::Float64 => PriceCol::DollarF64(typed(batch, index, path, "dollar float64")?),
        other => {
            return Err(SelectV2Error::SchemaMismatch {
                path: path.to_path_buf(),
                detail: format!("column {index} is {other:?}, not an admitted strike type"),
            });
        }
    })
}

pub(crate) fn text_col<'a>(
    batch: &'a RecordBatch,
    index: usize,
    path: &Path,
) -> Result<TextCol<'a>> {
    Ok(match batch.column(index).data_type() {
        DataType::Utf8 => TextCol::Utf8(typed(batch, index, path, "utf8")?),
        DataType::LargeUtf8 => TextCol::LargeUtf8(typed(batch, index, path, "large utf8")?),
        DataType::Dictionary(key, value)
            if key.as_ref() == &DataType::UInt32 && value.as_ref() == &DataType::Utf8 =>
        {
            let dictionary =
                typed::<DictionaryArray<UInt32Type>>(batch, index, path, "dictionary utf8")?;
            let values = dictionary
                .values()
                .as_any()
                .downcast_ref::<StringArray>()
                .ok_or_else(|| SelectV2Error::SchemaMismatch {
                    path: path.to_path_buf(),
                    detail: format!("column {index} dictionary values are not utf8"),
                })?;
            TextCol::Dict32(dictionary, values)
        }
        other => {
            return Err(SelectV2Error::SchemaMismatch {
                path: path.to_path_buf(),
                detail: format!("column {index} is {other:?}, not an admitted text type"),
            });
        }
    })
}

pub(crate) fn date_col<'a>(
    batch: &'a RecordBatch,
    index: usize,
    path: &Path,
) -> Result<DateCol<'a>> {
    if matches!(batch.column(index).data_type(), DataType::Date32) {
        return Ok(DateCol::Date32(typed(batch, index, path, "date32")?));
    }
    Ok(DateCol::Text(text_col(batch, index, path)?))
}

/// Pins a file's column names against the corpus's expected schema.
///
/// # Errors
///
/// [`SelectV2Error::SchemaMismatch`] on any count or name drift.
pub fn pin_column_names(
    builder: &ParquetRecordBatchReaderBuilder<File>,
    expected: &[&str],
    path: &Path,
) -> Result<()> {
    let schema = builder.schema();
    if schema.fields().len() != expected.len() {
        return Err(SelectV2Error::SchemaMismatch {
            path: path.to_path_buf(),
            detail: format!(
                "file has {} columns, this reader pins {}",
                schema.fields().len(),
                expected.len()
            ),
        });
    }
    for (index, (field, name)) in schema.fields().iter().zip(expected).enumerate() {
        if field.name() != name {
            return Err(SelectV2Error::SchemaMismatch {
                path: path.to_path_buf(),
                detail: format!("column {index} is {:?}, pinned as {name}", field.name()),
            });
        }
    }
    Ok(())
}
