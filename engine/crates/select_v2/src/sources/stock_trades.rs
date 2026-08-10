//! IWM stock prints (the tape) — straight column projection.
//!
//! The corpus carries 24 columns; ten are decoded: the trade instant, the
//! sequence, the condition, the size, the venue, the print price, and the NBBO
//! state the vendor attached to the print (both sides' price and displayed
//! size). Those last four make the E1 tick/quote-rule aggressor classification
//! and the E2 display-execution gap computable without a second join.
//!
//! Measured over 18 sampled days spanning 2020-2025, this corpus has a single
//! schema signature (prices `Float64` dollars, sizes `Int64`); the reader still
//! detects the encoding from the file's own schema and refuses anything outside
//! the admitted set.

use crate::calendar::DayScope;
use crate::error::{Result, SelectV2Error};
use crate::sources::{
    DECODE_BATCH_ROWS, IntCol, day_file, int_col, open_builder, pin_column_names, price_col,
    rth_row_groups, timestamp_col,
};
use arrow_array::{Array, RecordBatch};
use parquet::arrow::ProjectionMask;
use parquet::arrow::arrow_reader::ParquetRecordBatchReader;
use std::path::{Path, PathBuf};

/// The 24 pinned column names of the stock-print corpus.
pub const STOCK_TRADE_COLUMNS: [&str; 24] = [
    "trade_timestamp",
    "quote_timestamp",
    "sequence",
    "ext_condition1",
    "ext_condition2",
    "ext_condition3",
    "ext_condition4",
    "condition",
    "size",
    "exchange",
    "price",
    "bid_size",
    "bid_exchange",
    "bid",
    "bid_condition",
    "ask_size",
    "ask_exchange",
    "ask",
    "ask_condition",
    "dt_prev_ms",
    "mid",
    "price_lag_1",
    // BANNED FROM DECODE (catalog_final_v2 §1 law 3): `price_lead_1` is a
    // FUTURE-looking vendor field. It stays in the schema pin (drift detection)
    // and must never enter PROJECTION; the guard test below enforces it.
    "price_lead_1",
    "spread_bps",
];

#[cfg(test)]
mod lead_ban {
    #[test]
    fn future_field_never_projected() {
        let lead_idx = super::STOCK_TRADE_COLUMNS
            .iter()
            .position(|c| *c == "price_lead_1")
            .expect("schema pin must keep the banned column visible");
        assert!(
            !super::PROJECTION.contains(&lead_idx),
            "price_lead_1 is future data and must never be decoded"
        );
    }
}

/// Decoded leaves: `trade_timestamp`, `sequence`, `condition`, `size`,
/// `exchange`, `price`, `bid_size`, `bid`, `ask_size`, `ask`.
const PROJECTION: [usize; 10] = [0, 2, 7, 8, 9, 10, 11, 13, 15, 17];

/// One RTH-filtered slab of prints. Column-parallel.
#[derive(Clone, Debug, Default)]
pub struct StockTradeBatch {
    /// Naive-ET (frame B) milliseconds.
    pub ts_ms_b: Vec<i64>,
    pub sequence: Vec<i64>,
    pub condition: Vec<i64>,
    pub size: Vec<i64>,
    pub exchange: Vec<i64>,
    pub price_u6: Vec<i64>,
    /// The NBBO the vendor attached to the print. `quote_present[i]` is false
    /// when that state was null — absent, which is not the same as zero.
    pub bid_u6: Vec<i64>,
    pub ask_u6: Vec<i64>,
    pub bid_shares: Vec<i64>,
    pub ask_shares: Vec<i64>,
    pub quote_present: Vec<bool>,
}

impl StockTradeBatch {
    #[must_use]
    pub fn len(&self) -> usize {
        self.ts_ms_b.len()
    }

    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.ts_ms_b.is_empty()
    }

    fn clear(&mut self) {
        self.ts_ms_b.clear();
        self.sequence.clear();
        self.condition.clear();
        self.size.clear();
        self.exchange.clear();
        self.price_u6.clear();
        self.bid_u6.clear();
        self.ask_u6.clear();
        self.bid_shares.clear();
        self.ask_shares.clear();
        self.quote_present.clear();
    }
}

/// Streaming print reader for one admitted session.
pub struct StockTradeReader {
    inner: ParquetRecordBatchReader,
    path: PathBuf,
    day: &'static str,
    open_ms: i64,
    close_ms: i64,
    rth_rows: u64,
    finished: bool,
}

impl StockTradeReader {
    /// Opens the reader for a civil day, going through the calendar wall.
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
    /// [`SelectV2Error::Io`] or [`SelectV2Error::SchemaMismatch`].
    pub fn for_scope(scope: &DayScope, corpus_root: &Path) -> Result<Self> {
        let path = day_file(corpus_root, scope);
        let builder = open_builder(&path)?;
        pin_column_names(&builder, &STOCK_TRADE_COLUMNS, &path)?;
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
            day: scope.day(),
            open_ms: scope.open_ms_b(),
            close_ms: scope.close_ms_b(),
            rth_rows: 0,
            finished: false,
        })
    }

    /// RTH prints emitted so far.
    #[must_use]
    pub const fn rth_rows(&self) -> u64 {
        self.rth_rows
    }

    /// The file this reader is decoding.
    #[must_use]
    pub fn path(&self) -> &Path {
        &self.path
    }

    fn decode(&mut self, batch: &RecordBatch, out: &mut StockTradeBatch) -> Result<()> {
        let timestamp = timestamp_col(batch, 0, &self.path)?;
        let sequence = int_col(batch, 1, &self.path)?;
        let condition = int_col(batch, 2, &self.path)?;
        let size = int_col(batch, 3, &self.path)?;
        let exchange = int_col(batch, 4, &self.path)?;
        let price = price_col(batch, 5, &self.path)?;
        let bid_size = int_col(batch, 6, &self.path)?;
        let bid = price_col(batch, 7, &self.path)?;
        let ask_size = int_col(batch, 8, &self.path)?;
        let ask = price_col(batch, 9, &self.path)?;
        for row in 0..batch.num_rows() {
            if timestamp.is_null(row) || price.is_null(row) {
                continue;
            }
            let ts_ms = timestamp.value(row);
            if ts_ms < self.open_ms || ts_ms >= self.close_ms {
                continue;
            }
            self.rth_rows += 1;
            out.ts_ms_b.push(ts_ms);
            out.sequence.push(nullable(&sequence, row));
            out.condition.push(nullable(&condition, row));
            out.size.push(nullable(&size, row));
            out.exchange.push(nullable(&exchange, row));
            out.price_u6.push(price.u6(row, &self.path)?);
            let present = !bid.is_null(row)
                && !ask.is_null(row)
                && !IntCol::is_null(&bid_size, row)
                && !IntCol::is_null(&ask_size, row);
            out.quote_present.push(present);
            if present {
                out.bid_u6.push(bid.u6(row, &self.path)?);
                out.ask_u6.push(ask.u6(row, &self.path)?);
                out.bid_shares.push(shares(&bid_size, row, self.day));
                out.ask_shares.push(shares(&ask_size, row, self.day));
            } else {
                out.bid_u6.push(0);
                out.ask_u6.push(0);
                out.bid_shares.push(0);
                out.ask_shares.push(0);
            }
        }
        Ok(())
    }

    /// Decodes the next non-empty RTH slab into `out`.
    ///
    /// # Errors
    ///
    /// Decode, schema or arithmetic refusals from the underlying file.
    pub fn next_into(&mut self, out: &mut StockTradeBatch) -> Result<bool> {
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

impl Iterator for StockTradeReader {
    type Item = Result<StockTradeBatch>;

    fn next(&mut self) -> Option<Self::Item> {
        let mut out = StockTradeBatch::default();
        match self.next_into(&mut out) {
            Ok(true) => Some(Ok(out)),
            Ok(false) => None,
            Err(error) => Some(Err(error)),
        }
    }
}

fn nullable(column: &IntCol<'_>, row: usize) -> i64 {
    if column.is_null(row) {
        i64::MIN
    } else {
        column.value(row)
    }
}

fn shares(size: &IntCol<'_>, row: usize, day: &str) -> i64 {
    let raw = size.value(row);
    if raw < 0 {
        return raw;
    }
    #[allow(clippy::cast_sign_loss, clippy::cast_possible_wrap)]
    {
        corpus::nbbo_size_to_shares(raw as u64, day) as i64
    }
}
