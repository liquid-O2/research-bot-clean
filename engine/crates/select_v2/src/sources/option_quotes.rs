//! Option NBBO quotes (IWM and RUTW) — straight column projection.
//!
//! 728 GB across both roots; per the plan's data-priority inversion this pass
//! is DEFERRED and never blocks a family. The reader exists so that quote-side
//! state (option spread and displayed depth), which prints and `AllGreeks`
//! cannot give, is reachable when its lane runs.
//!
//! Two on-disk *layouts* were measured and both are handled:
//!
//! * flat — `<root>/<YYYY>/<day>.parquet` (IWM through mid-2024);
//! * per-expiry sharded — `<root>/<YYYY>/<day>/exp<YYYY-MM-DD>.parquet`
//!   (IWM from late 2024, all RUTW).
//!
//! Coverage starts 2022-11-01 for IWM — the F-12 era mask. An earlier
//! registered day is [`SelectV2Error::ModalityAbsent`], which is distinct from
//! being outside the calendar.
//!
//! The vendor `mid` column is not read: it is `bid + ask` in the compact
//! profile and the true midpoint in the wide one.

use crate::calendar::DayScope;
use crate::error::{Result, SelectV2Error};
use crate::sources::options_prints::Right;
use crate::sources::{
    DECODE_BATCH_ROWS, IntCol, date_col, day_shards, int_col, open_builder, pin_column_names,
    price_col, strike_col, text_col, timestamp_col,
};
use arrow_array::{Array, RecordBatch};
use parquet::arrow::ProjectionMask;
use parquet::arrow::arrow_reader::ParquetRecordBatchReader;
use std::path::{Path, PathBuf};

/// The 19 pinned column names of the option-quote corpora.
pub const OPTION_QUOTE_COLUMNS: [&str; 19] = [
    "symbol",
    "expiration",
    "strike",
    "right",
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
    "dt_prev_contract_ms",
    "mid",
];

/// Decoded leaves: `expiration`, `strike`, `right`, `timestamp`, `bid_size`,
/// `bid`, `ask_size`, `ask`.
const PROJECTION: [usize; 8] = [1, 2, 3, 4, 5, 7, 9, 11];
const TIMESTAMP_LEAF: usize = 4;

/// The first session on which IWM option quotes exist (finding F-12).
pub const OPTION_QUOTE_FIRST_DAY: &str = "2022-11-01";

/// One RTH-filtered slab of option NBBO state.
#[derive(Clone, Debug, Default)]
pub struct OptionQuoteBatch {
    /// Naive-ET (frame B) milliseconds.
    pub ts_ms_b: Vec<i64>,
    /// Expiration as days since the Unix epoch.
    pub expiration_day: Vec<i32>,
    pub strike_u6: Vec<i64>,
    pub right: Vec<Right>,
    pub bid_u6: Vec<i64>,
    pub ask_u6: Vec<i64>,
    pub bid_size: Vec<i64>,
    pub ask_size: Vec<i64>,
}

impl OptionQuoteBatch {
    #[must_use]
    pub fn len(&self) -> usize {
        self.ts_ms_b.len()
    }

    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.ts_ms_b.is_empty()
    }

    /// True midpoint in u6, computed — never the vendor column.
    #[must_use]
    pub fn mid_u6(&self, row: usize) -> i64 {
        i64::midpoint(self.bid_u6[row], self.ask_u6[row])
    }

    fn clear(&mut self) {
        self.ts_ms_b.clear();
        self.expiration_day.clear();
        self.strike_u6.clear();
        self.right.clear();
        self.bid_u6.clear();
        self.ask_u6.clear();
        self.bid_size.clear();
        self.ask_size.clear();
    }
}

/// Streaming option-quote reader; chains this session's shards in sorted order.
pub struct OptionQuoteReader {
    shards: Vec<PathBuf>,
    next_shard: usize,
    inner: Option<ParquetRecordBatchReader>,
    path: PathBuf,
    open_ms: i64,
    close_ms: i64,
    rth_rows: u64,
}

impl OptionQuoteReader {
    /// Opens the corpus for a civil day through the calendar wall.
    ///
    /// # Errors
    ///
    /// [`SelectV2Error::DayOutsideCalendar`] before any path is formed for an
    /// unregistered day; otherwise the errors of [`Self::for_scope`].
    pub fn for_day(day: &str, corpus_root: &Path) -> Result<Self> {
        let scope = crate::calendar::admit(day)?;
        Self::for_scope(&scope, corpus_root)
    }

    /// Opens the reader for an already-admitted session.
    ///
    /// # Errors
    ///
    /// [`SelectV2Error::ModalityAbsent`] for a registered day the corpus does
    /// not cover, [`SelectV2Error::Io`] or [`SelectV2Error::SchemaMismatch`].
    pub fn for_scope(scope: &DayScope, corpus_root: &Path) -> Result<Self> {
        let shards = day_shards(corpus_root, scope, "option_quotes")?;
        let path = shards[0].clone();
        Ok(Self {
            shards,
            next_shard: 0,
            inner: None,
            path,
            open_ms: scope.open_ms_b(),
            close_ms: scope.close_ms_b(),
            rth_rows: 0,
        })
    }

    /// The per-expiry shards this session is spread over.
    #[must_use]
    pub fn shards(&self) -> &[PathBuf] {
        &self.shards
    }

    /// RTH quotes emitted so far, across all shards.
    #[must_use]
    pub const fn rth_rows(&self) -> u64 {
        self.rth_rows
    }

    fn open_next_shard(&mut self, scope_open: i64, scope_close: i64) -> Result<bool> {
        let Some(path) = self.shards.get(self.next_shard).cloned() else {
            return Ok(false);
        };
        self.next_shard += 1;
        let builder = open_builder(&path)?;
        pin_column_names(&builder, &OPTION_QUOTE_COLUMNS, &path)?;
        // Row-group pruning needs a scope; reconstruct the window inline since
        // the two bounds are all it uses.
        let groups = {
            let metadata = builder.metadata();
            let mut keep = Vec::with_capacity(metadata.num_row_groups());
            let mut usable = true;
            for index in 0..metadata.num_row_groups() {
                let column = metadata.row_group(index).column(TIMESTAMP_LEAF);
                if let Some(parquet::file::statistics::Statistics::Int64(stats)) =
                    column.statistics()
                {
                    match (stats.min_opt(), stats.max_opt()) {
                        (Some(&min), Some(&max)) => {
                            if max >= scope_open && min < scope_close {
                                keep.push(index);
                            }
                        }
                        _ => usable = false,
                    }
                } else {
                    usable = false;
                }
                if !usable {
                    break;
                }
            }
            if usable {
                keep
            } else {
                (0..metadata.num_row_groups()).collect()
            }
        };
        let projection = ProjectionMask::roots(builder.parquet_schema(), PROJECTION);
        let reader = builder
            .with_row_groups(groups)
            .with_projection(projection)
            .with_batch_size(DECODE_BATCH_ROWS)
            .build()
            .map_err(|source| SelectV2Error::Io {
                path: path.clone(),
                source: std::io::Error::other(source),
            })?;
        self.path = path;
        self.inner = Some(reader);
        Ok(true)
    }

    fn decode(&mut self, batch: &RecordBatch, out: &mut OptionQuoteBatch) -> Result<()> {
        let expiration = date_col(batch, 0, &self.path)?;
        let strike = strike_col(batch, 1, &self.path)?;
        let right = text_col(batch, 2, &self.path)?;
        let timestamp = timestamp_col(batch, 3, &self.path)?;
        let bid_size = int_col(batch, 4, &self.path)?;
        let bid = price_col(batch, 5, &self.path)?;
        let ask_size = int_col(batch, 6, &self.path)?;
        let ask = price_col(batch, 7, &self.path)?;
        for row in 0..batch.num_rows() {
            if timestamp.is_null(row) || bid.is_null(row) || ask.is_null(row) {
                continue;
            }
            let ts_ms = timestamp.value(row);
            if ts_ms < self.open_ms || ts_ms >= self.close_ms {
                continue;
            }
            self.rth_rows += 1;
            out.ts_ms_b.push(ts_ms);
            out.expiration_day.push(if expiration.is_null(row) {
                i32::MIN
            } else {
                expiration.day_ordinal(row, &self.path)?
            });
            out.strike_u6.push(if strike.is_null(row) {
                i64::MIN
            } else {
                strike.u6(row, &self.path)?
            });
            out.right.push(if right.is_null(row) {
                Right::Other
            } else {
                Right::parse_public(right.value(row))
            });
            out.bid_u6.push(bid.u6(row, &self.path)?);
            out.ask_u6.push(ask.u6(row, &self.path)?);
            out.bid_size.push(if IntCol::is_null(&bid_size, row) {
                i64::MIN
            } else {
                bid_size.value(row)
            });
            out.ask_size.push(if IntCol::is_null(&ask_size, row) {
                i64::MIN
            } else {
                ask_size.value(row)
            });
        }
        Ok(())
    }

    /// Decodes the next non-empty RTH slab into `out`, crossing shards.
    ///
    /// # Errors
    ///
    /// Decode, schema or arithmetic refusals from the underlying files.
    pub fn next_into(&mut self, out: &mut OptionQuoteBatch) -> Result<bool> {
        out.clear();
        let (open, close) = (self.open_ms, self.close_ms);
        loop {
            if self.inner.is_none() && !self.open_next_shard(open, close)? {
                return Ok(false);
            }
            let Some(reader) = self.inner.as_mut() else {
                return Ok(false);
            };
            let Some(batch) = reader.next() else {
                self.inner = None;
                continue;
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

impl Iterator for OptionQuoteReader {
    type Item = Result<OptionQuoteBatch>;

    fn next(&mut self) -> Option<Self::Item> {
        let mut out = OptionQuoteBatch::default();
        match self.next_into(&mut out) {
            Ok(true) => Some(Ok(out)),
            Ok(false) => None,
            Err(error) => Some(Err(error)),
        }
    }
}
