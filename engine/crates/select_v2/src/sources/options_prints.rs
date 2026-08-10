//! Option prints (IWM and RUTW) — straight column projection.
//!
//! 62 columns on disk with full 1,003-session coverage. Per the data-priority
//! inversion this is the primary option source: it already carries
//! `implied_vol`, the greek ladder, `underlying_price`, `moneyness`, `prem`,
//! the greek FLOW columns and native `sweep_id`/`sweep_n`/`sweep_size`, so the
//! F1/F2 families are mostly a column read rather than a 728 GB quote pass.
//!
//! Two on-disk profiles were measured, and both are admitted by schema
//! detection at open:
//!
//! * **compact** (IWM) — `symbol`/`right` dictionary-encoded, `expiration`
//!   `Date32`, `strike` `Int32` mills, `size` `Int32`, `price` `Int32` cents;
//! * **wide** (RUTW) — those five as `LargeUtf8`/`Float64`/`Int64` dollars.

use crate::calendar::DayScope;
use crate::error::{Result, SelectV2Error};
use crate::sources::{
    DECODE_BATCH_ROWS, IntCol, date_col, day_file, float_col, int_col, open_builder,
    pin_column_names, price_col, rth_row_groups, strike_col, text_col, timestamp_col,
};
use arrow_array::{Array, RecordBatch};
use parquet::arrow::ProjectionMask;
use parquet::arrow::arrow_reader::ParquetRecordBatchReader;
use std::path::{Path, PathBuf};

/// The 62 pinned column names of the option-print corpora.
pub const OPTION_PRINT_COLUMNS: [&str; 62] = [
    "symbol",
    "expiration",
    "strike",
    "right",
    "timestamp",
    "sequence",
    "ext_condition1",
    "ext_condition2",
    "ext_condition3",
    "ext_condition4",
    "condition",
    "size",
    "exchange",
    "price",
    "delta",
    "theta",
    "vega",
    "rho",
    "epsilon",
    "lambda",
    "gamma",
    "vanna",
    "charm",
    "vomma",
    "veta",
    "vera",
    "speed",
    "zomma",
    "color",
    "ultima",
    "d1",
    "d2",
    "dual_delta",
    "dual_gamma",
    "implied_vol",
    "iv_error",
    "underlying_timestamp",
    "underlying_price",
    "side",
    "bid",
    "bid_size",
    "bid_exchange",
    "ask",
    "ask_size",
    "ask_exchange",
    "quote_timestamp",
    "dt_prev_contract_ms",
    "sweep_id",
    "sweep_n",
    "sweep_size",
    "sweep_exchanges",
    "dt_prev_any_ms",
    "dte",
    "moneyness",
    "prem",
    "delta_flow",
    "gamma_flow",
    "vanna_flow",
    "speed_flow",
    "zomma_flow",
    "charm_flow",
    "vomma_flow",
];

/// The 25 leaves decoded, in file order.
const PROJECTION: [usize; 25] = [
    1, 2, 3, 4, 11, 13, 14, 20, 21, 22, 34, 37, 38, 39, 42, 47, 48, 49, 52, 53, 54, 55, 56, 57, 60,
];

/// File index of the `timestamp` leaf, used for row-group pruning.
const TIMESTAMP_LEAF: usize = 4;

/// Contract right. Anything the vendor writes that is neither call nor put is
/// kept as [`Right::Other`] rather than folded into one of them.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum Right {
    Call = 0,
    Put = 1,
    Other = 2,
}

impl Right {
    /// Parses a vendor right token. Unknown tokens become [`Right::Other`]
    /// rather than being folded into call or put.
    #[must_use]
    pub fn parse_public(text: &str) -> Self {
        Self::parse(text)
    }

    fn parse(text: &str) -> Self {
        match text {
            "CALL" | "C" | "call" => Self::Call,
            "PUT" | "P" | "put" => Self::Put,
            _ => Self::Other,
        }
    }
}

/// One RTH-filtered slab of option prints. Column-parallel; absent floats are
/// `NaN`, absent integers are [`i64::MIN`].
#[derive(Clone, Debug, Default)]
pub struct OptionPrintBatch {
    /// Naive-ET (frame B) milliseconds.
    pub ts_ms_b: Vec<i64>,
    /// Expiration as days since the Unix epoch.
    pub expiration_day: Vec<i32>,
    /// Strike in u6 dollars.
    pub strike_u6: Vec<i64>,
    pub right: Vec<Right>,
    pub size: Vec<i64>,
    /// Print price in u6 dollars (per share, not per contract).
    pub price_u6: Vec<i64>,
    pub delta: Vec<f64>,
    pub gamma: Vec<f64>,
    pub vanna: Vec<f64>,
    pub charm: Vec<f64>,
    pub implied_vol: Vec<f64>,
    pub underlying_price: Vec<f64>,
    /// Vendor aggressor tag.
    pub side: Vec<i64>,
    pub bid_u6: Vec<i64>,
    pub ask_u6: Vec<i64>,
    pub sweep_id: Vec<i64>,
    pub sweep_n: Vec<i64>,
    pub sweep_size: Vec<i64>,
    pub dte: Vec<i64>,
    pub moneyness: Vec<f64>,
    pub prem: Vec<f64>,
    pub delta_flow: Vec<f64>,
    pub gamma_flow: Vec<f64>,
    pub vanna_flow: Vec<f64>,
    pub charm_flow: Vec<f64>,
}

impl OptionPrintBatch {
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
        self.expiration_day.clear();
        self.strike_u6.clear();
        self.right.clear();
        self.size.clear();
        self.price_u6.clear();
        self.delta.clear();
        self.gamma.clear();
        self.vanna.clear();
        self.charm.clear();
        self.implied_vol.clear();
        self.underlying_price.clear();
        self.side.clear();
        self.bid_u6.clear();
        self.ask_u6.clear();
        self.sweep_id.clear();
        self.sweep_n.clear();
        self.sweep_size.clear();
        self.dte.clear();
        self.moneyness.clear();
        self.prem.clear();
        self.delta_flow.clear();
        self.gamma_flow.clear();
        self.vanna_flow.clear();
        self.charm_flow.clear();
    }
}

/// Streaming option-print reader for one admitted session.
pub struct OptionPrintReader {
    inner: ParquetRecordBatchReader,
    path: PathBuf,
    open_ms: i64,
    close_ms: i64,
    rth_rows: u64,
    finished: bool,
}

impl OptionPrintReader {
    /// Opens the IWM or RUTW print corpus for a civil day through the wall.
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
        pin_column_names(&builder, &OPTION_PRINT_COLUMNS, &path)?;
        let groups = rth_row_groups(&builder, TIMESTAMP_LEAF, scope);
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

    #[allow(clippy::too_many_lines)] // 25 columns decoded row-wise; splitting
    // it would only move the same straight-line work behind a second call.
    fn decode(&mut self, batch: &RecordBatch, out: &mut OptionPrintBatch) -> Result<()> {
        let expiration = date_col(batch, 0, &self.path)?;
        let strike = strike_col(batch, 1, &self.path)?;
        let right = text_col(batch, 2, &self.path)?;
        let timestamp = timestamp_col(batch, 3, &self.path)?;
        let size = int_col(batch, 4, &self.path)?;
        let price = price_col(batch, 5, &self.path)?;
        let delta = float_col(batch, 6, &self.path)?;
        let gamma = float_col(batch, 7, &self.path)?;
        let vanna = float_col(batch, 8, &self.path)?;
        let charm = float_col(batch, 9, &self.path)?;
        let implied_vol = float_col(batch, 10, &self.path)?;
        let underlying_price = float_col(batch, 11, &self.path)?;
        let aggressor = int_col(batch, 12, &self.path)?;
        let bid = price_col(batch, 13, &self.path)?;
        let ask = price_col(batch, 14, &self.path)?;
        let sweep_id = int_col(batch, 15, &self.path)?;
        let sweep_n = int_col(batch, 16, &self.path)?;
        let sweep_size = int_col(batch, 17, &self.path)?;
        let dte = int_col(batch, 18, &self.path)?;
        let moneyness = float_col(batch, 19, &self.path)?;
        let prem = float_col(batch, 20, &self.path)?;
        let delta_flow = float_col(batch, 21, &self.path)?;
        let gamma_flow = float_col(batch, 22, &self.path)?;
        let vanna_flow = float_col(batch, 23, &self.path)?;
        let charm_flow = float_col(batch, 24, &self.path)?;

        for row in 0..batch.num_rows() {
            if timestamp.is_null(row) {
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
                Right::parse(right.value(row))
            });
            out.size.push(nullable_int(&size, row));
            out.price_u6.push(if price.is_null(row) {
                i64::MIN
            } else {
                price.u6(row, &self.path)?
            });
            out.delta.push(nullable_float(delta, row));
            out.gamma.push(nullable_float(gamma, row));
            out.vanna.push(nullable_float(vanna, row));
            out.charm.push(nullable_float(charm, row));
            out.implied_vol.push(nullable_float(implied_vol, row));
            out.underlying_price
                .push(nullable_float(underlying_price, row));
            out.side.push(nullable_int(&aggressor, row));
            out.bid_u6.push(if bid.is_null(row) {
                i64::MIN
            } else {
                bid.u6(row, &self.path)?
            });
            out.ask_u6.push(if ask.is_null(row) {
                i64::MIN
            } else {
                ask.u6(row, &self.path)?
            });
            out.sweep_id.push(nullable_int(&sweep_id, row));
            out.sweep_n.push(nullable_int(&sweep_n, row));
            out.sweep_size.push(nullable_int(&sweep_size, row));
            out.dte.push(nullable_int(&dte, row));
            out.moneyness.push(nullable_float(moneyness, row));
            out.prem.push(nullable_float(prem, row));
            out.delta_flow.push(nullable_float(delta_flow, row));
            out.gamma_flow.push(nullable_float(gamma_flow, row));
            out.vanna_flow.push(nullable_float(vanna_flow, row));
            out.charm_flow.push(nullable_float(charm_flow, row));
        }
        Ok(())
    }

    /// Decodes the next non-empty RTH slab into `out`.
    ///
    /// # Errors
    ///
    /// Decode, schema or arithmetic refusals from the underlying file.
    pub fn next_into(&mut self, out: &mut OptionPrintBatch) -> Result<bool> {
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

impl Iterator for OptionPrintReader {
    type Item = Result<OptionPrintBatch>;

    fn next(&mut self) -> Option<Self::Item> {
        let mut out = OptionPrintBatch::default();
        match self.next_into(&mut out) {
            Ok(true) => Some(Ok(out)),
            Ok(false) => None,
            Err(error) => Some(Err(error)),
        }
    }
}

fn nullable_int(column: &IntCol<'_>, row: usize) -> i64 {
    if column.is_null(row) {
        i64::MIN
    } else {
        column.value(row)
    }
}

fn nullable_float(column: &arrow_array::Float64Array, row: usize) -> f64 {
    if column.is_null(row) {
        f64::NAN
    } else {
        column.value(row)
    }
}
