//! IWM NBBO stock quotes — **RAW retention**.
//!
//! `corpus::load_session` keeps only group midpoints. Families D1
//! (`liquidity_cost`), B2 (`pivot_micro`), E2 (`gt_intent`) and E3
//! (`raid_sonar`) need the raw two-sided book state, so this reader retains
//! bid, ask, both displayed sizes and the derived spread, streaming rather
//! than materializing (a session carries ~11-14M RTH rows: `raw_rth_row_count`
//! is 14,141,301 for 2022-01-03 and 10,950,039 for 2025-12-30).
//!
//! Sizes are normalized to **shares** through `corpus::nbbo_size_to_shares`,
//! which folds the F-34 lot/share era break at 2025-11-03 at the reader
//! boundary, so no family sees a 100x scale step in the last 41 sessions.
//!
//! The price profile is taken from the session's own registry row and then
//! cross-checked against the file's arrow schema; the two disagreeing is a
//! refusal, not a fallback. (The profile is not chronologically monotone:
//! 2025-12-30 is `cent_int32`, 2025-12-31 is `dollar_float64`.)

use crate::calendar::DayScope;
use crate::error::{Result, SelectV2Error};
use crate::sources::{
    DECODE_BATCH_ROWS, IntCol, int_col, open_builder, pin_column_names, price_col,
    rth_row_groups, timestamp_col,
};
use arrow_array::{Array, RecordBatch};
use corpus::SourceProfile;
use parquet::arrow::ProjectionMask;
use parquet::arrow::arrow_reader::ParquetRecordBatchReader;
use std::path::{Path, PathBuf};

/// The 16 columns the stock-quote corpus carries, pinned by name.
pub const STOCK_QUOTE_COLUMNS: [&str; 16] = [
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

/// The five leaves actually decoded: `timestamp`, `bid_size`, `bid`,
/// `ask_size`, `ask`. The vendor `mid` is deliberately NOT read — it is
/// `bid + ask` in the `CentInt32` profile and the true midpoint in the
/// `DollarFloat64` one.
const PROJECTION: [usize; 5] = [0, 1, 3, 5, 7];

/// One decoded, RTH-filtered slab of raw NBBO state. Column-parallel; row `i`
/// of every vector is the same quote.
#[derive(Clone, Debug, Default)]
pub struct StockQuoteBatch {
    /// Naive-ET (frame B) milliseconds, as they sit on the tape.
    pub ts_ms_b: Vec<i64>,
    pub bid_u6: Vec<i64>,
    pub ask_u6: Vec<i64>,
    /// Displayed size in SHARES (F-34 era normalized).
    pub bid_shares: Vec<i64>,
    pub ask_shares: Vec<i64>,
}

impl StockQuoteBatch {
    #[must_use]
    pub fn len(&self) -> usize {
        self.ts_ms_b.len()
    }

    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.ts_ms_b.is_empty()
    }

    /// True midpoint in u6, computed — never read from the vendor column.
    #[must_use]
    pub fn mid_u6(&self, row: usize) -> i64 {
        i64::midpoint(self.bid_u6[row], self.ask_u6[row])
    }

    /// `ask - bid` in u6.
    #[must_use]
    pub fn spread_u6(&self, row: usize) -> i64 {
        self.ask_u6[row] - self.bid_u6[row]
    }

    fn clear(&mut self) {
        self.ts_ms_b.clear();
        self.bid_u6.clear();
        self.ask_u6.clear();
        self.bid_shares.clear();
        self.ask_shares.clear();
    }
}

/// Streaming raw NBBO reader for one admitted session.
pub struct StockQuoteReader {
    inner: ParquetRecordBatchReader,
    path: PathBuf,
    profile: SourceProfile,
    day: &'static str,
    open_ms: i64,
    close_ms: i64,
    rth_rows: u64,
    skipped_null_rows: u64,
    finished: bool,
}

impl StockQuoteReader {
    /// Opens the reader for a civil day, going through the calendar wall.
    ///
    /// # Errors
    ///
    /// [`SelectV2Error::DayOutsideCalendar`] before any path is formed if the
    /// day is not one of the 1,003 registry sessions; otherwise the errors of
    /// [`Self::for_scope`].
    pub fn for_day(day: &str, corpus_root: &Path) -> Result<Self> {
        let scope = crate::calendar::admit(day)?;
        Self::for_scope(&scope, corpus_root)
    }

    /// Opens the reader for an already-admitted session.
    ///
    /// # Errors
    ///
    /// [`SelectV2Error::Io`] if the file is unreadable, or
    /// [`SelectV2Error::SchemaMismatch`] if the 16-column schema or the
    /// registry-declared price profile does not hold.
    pub fn for_scope(scope: &DayScope, corpus_root: &Path) -> Result<Self> {
        let entry = scope.entry();
        // The registry's own relative path, not a reconstructed one.
        let path = corpus_root.join(entry.source_relative_path);
        let builder = open_builder(&path)?;
        pin_column_names(&builder, &STOCK_QUOTE_COLUMNS, &path)?;
        check_profile(&builder, entry.source_profile, &path)?;
        let groups = rth_row_groups(&builder, 0, scope);
        let projection = ProjectionMask::roots(builder.parquet_schema(), PROJECTION);
        let inner = builder
            .with_row_groups(groups)
            .with_projection(projection)
            .with_batch_size(DECODE_BATCH_ROWS)
            .build()
            .map_err(|source| SelectV2Error::Io {
                path: path.clone(),
                source: std::io::Error::other(source),
            })?;
        Ok(Self {
            inner,
            path,
            profile: entry.source_profile,
            day: entry.day,
            open_ms: scope.open_ms_b(),
            close_ms: scope.close_ms_b(),
            rth_rows: 0,
            skipped_null_rows: 0,
            finished: false,
        })
    }

    /// RTH rows emitted so far. After a full pass this equals the registry's
    /// `raw_rth_row_count` for the session.
    #[must_use]
    pub const fn rth_rows(&self) -> u64 {
        self.rth_rows
    }

    /// Rows skipped because the projected NBBO fields were null. Counted, not
    /// silently folded into zero.
    #[must_use]
    pub const fn skipped_null_rows(&self) -> u64 {
        self.skipped_null_rows
    }

    /// The file this reader is decoding.
    #[must_use]
    pub fn path(&self) -> &Path {
        &self.path
    }

    /// The registry-declared price encoding this session was decoded under.
    #[must_use]
    pub const fn profile(&self) -> SourceProfile {
        self.profile
    }

    fn decode(&mut self, batch: &RecordBatch, out: &mut StockQuoteBatch) -> Result<()> {
        let timestamp = timestamp_col(batch, 0, &self.path)?;
        let bid_size = int_col(batch, 1, &self.path)?;
        let bid = price_col(batch, 2, &self.path)?;
        let ask_size = int_col(batch, 3, &self.path)?;
        let ask = price_col(batch, 4, &self.path)?;
        for row in 0..batch.num_rows() {
            if timestamp.is_null(row)
                || bid.is_null(row)
                || ask.is_null(row)
                || IntCol::is_null(&bid_size, row)
                || IntCol::is_null(&ask_size, row)
            {
                self.skipped_null_rows += 1;
                continue;
            }
            let ts_ms = timestamp.value(row);
            if ts_ms < self.open_ms || ts_ms >= self.close_ms {
                continue;
            }
            self.rth_rows += 1;
            out.ts_ms_b.push(ts_ms);
            out.bid_u6.push(bid.u6(row, &self.path)?);
            out.ask_u6.push(ask.u6(row, &self.path)?);
            out.bid_shares.push(shares(&bid_size, row, self.day));
            out.ask_shares.push(shares(&ask_size, row, self.day));
        }
        Ok(())
    }

    /// Decodes the next non-empty RTH slab into `out`, reusing its capacity.
    ///
    /// # Errors
    ///
    /// Decode, schema or arithmetic refusals from the underlying file.
    pub fn next_into(&mut self, out: &mut StockQuoteBatch) -> Result<bool> {
        out.clear();
        if self.finished {
            return Ok(false);
        }
        loop {
            let Some(batch) = self.inner.next() else {
                self.finished = true;
                return Ok(false);
            };
            let batch = batch.map_err(|source| SelectV2Error::Io {
                path: self.path.clone(),
                source: std::io::Error::other(source),
            })?;
            self.decode(&batch, out)?;
            if !out.is_empty() {
                return Ok(true);
            }
        }
    }
}

impl Iterator for StockQuoteReader {
    type Item = Result<StockQuoteBatch>;

    fn next(&mut self) -> Option<Self::Item> {
        let mut out = StockQuoteBatch::default();
        match self.next_into(&mut out) {
            Ok(true) => Some(Ok(out)),
            Ok(false) => None,
            Err(error) => Some(Err(error)),
        }
    }
}

fn shares(size: &IntCol<'_>, row: usize, day: &str) -> i64 {
    let raw = size.value(row);
    if raw < 0 {
        return raw;
    }
    // `raw` is non-negative here, so the u64 round trip is lossless.
    #[allow(clippy::cast_sign_loss, clippy::cast_possible_wrap)]
    {
        corpus::nbbo_size_to_shares(raw as u64, day) as i64
    }
}

fn check_profile(
    builder: &parquet::arrow::arrow_reader::ParquetRecordBatchReaderBuilder<std::fs::File>,
    profile: SourceProfile,
    path: &Path,
) -> Result<()> {
    use arrow_schema::DataType;
    let schema = builder.schema();
    let bid = schema.field(3).data_type();
    let ask = schema.field(7).data_type();
    let admitted = match profile {
        SourceProfile::CentInt32 => &DataType::Int32,
        SourceProfile::DollarFloat64 => &DataType::Float64,
    };
    if bid != admitted || ask != admitted {
        return Err(SelectV2Error::SchemaMismatch {
            path: path.to_path_buf(),
            detail: format!(
                "registry declares {profile:?} but bid/ask are {bid:?}/{ask:?}"
            ),
        });
    }
    Ok(())
}
