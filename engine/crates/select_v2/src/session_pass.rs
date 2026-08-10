//! **The streaming session pass** — one walk over a session's stock tape that
//! serves every stock-side family at once, plus PP1 as a side product.
//!
//! For one admitted session the driver:
//!
//! 1. opens the RAW stock-quote and stock-print readers (calendar-bounded, RTH
//!    filtered, u6, sizes in shares);
//! 2. merges them in frame-B timestamp order — quotes before prints on a tie,
//!    so a print is always classified against the NBBO state that preceded it;
//! 3. announces every action cutoff the instant the tape crosses it, BEFORE
//!    delivering the crossing event, which is what makes the as-of rule
//!    structural rather than conventional;
//! 4. maintains the PP1 grid;
//! 5. writes one PP1 parquet and one parquet per family.
//!
//! ## PP1
//!
//! A 1-second path panel of `(bid, ask, mid)` as `f32` dollars, one row per
//! slot, `bar_count * 60` slots — 23,400 for a full session and 12,600 for the
//! nine 210-bar early closes, taken from each session's own registry row rather
//! than a constant. 23,400 x 3 x 4 B = 280,800 B uncompressed per full session,
//! ~282 MB over the 1,003-session corpus.
//!
//! A slot holds the LAST quote that fell inside that second, and `NaN` when no
//! quote did. It is deliberately not forward-filled: a forward fill is
//! derivable from this panel, the reverse is not, and folding a genuinely
//! quote-less second into the previous second's price would make absence
//! indistinguishable from a stale-but-real quote. `mid` is computed as
//! `(bid + ask) / 2` — the vendor `mid` column means different things in the
//! two source profiles and is never read.

use crate::book::ActionCutoff;
use crate::calendar::DayScope;
use crate::error::{Result, SelectV2Error};
use crate::families::{FamilyEmitter, QuoteEvent, TradeEvent, check_width};
use crate::sources::stock_quotes::{StockQuoteBatch, StockQuoteReader};
use crate::sources::stock_trades::{StockTradeBatch, StockTradeReader};
use arrow_array::{Float32Array, RecordBatch, StringArray};
use arrow_schema::{DataType, Field, Schema};
use parquet::arrow::ArrowWriter;
use parquet::basic::{Compression, ZstdLevel};
use parquet::file::properties::WriterProperties;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Instant;

/// zstd level for emitted leaves. 3 is the fast end of the useful range; the
/// budget figure quoted for PP1 is the uncompressed one.
const ZSTD_LEVEL: i32 = 3;

/// The PP1 1-second path panel for one session.
#[derive(Clone, Debug)]
pub struct Pp1Grid {
    width: usize,
    bid: Vec<f32>,
    ask: Vec<f32>,
    mid: Vec<f32>,
    filled: usize,
}

impl Pp1Grid {
    /// Allocates the grid at this session's true width.
    #[must_use]
    pub fn for_scope(scope: &DayScope) -> Self {
        let width = scope.pp1_width();
        Self {
            width,
            bid: vec![f32::NAN; width],
            ask: vec![f32::NAN; width],
            mid: vec![f32::NAN; width],
            filled: 0,
        }
    }

    /// Slots in the grid.
    #[must_use]
    pub const fn width(&self) -> usize {
        self.width
    }

    /// Slots that saw at least one quote.
    #[must_use]
    pub const fn filled(&self) -> usize {
        self.filled
    }

    /// Slots with no quote at all — observed absence, reported not hidden.
    #[must_use]
    pub const fn empty_slots(&self) -> usize {
        self.width - self.filled
    }

    #[must_use]
    pub fn bid(&self) -> &[f32] {
        &self.bid
    }

    #[must_use]
    pub fn ask(&self) -> &[f32] {
        &self.ask
    }

    #[must_use]
    pub fn mid(&self) -> &[f32] {
        &self.mid
    }

    fn observe(&mut self, slot: usize, quote: &QuoteEvent) {
        if slot >= self.width {
            return;
        }
        if self.bid[slot].is_nan() {
            self.filled += 1;
        }
        self.bid[slot] = u6_to_f32(quote.bid_u6);
        self.ask[slot] = u6_to_f32(quote.ask_u6);
        self.mid[slot] = u6_to_f32(quote.mid_u6());
    }
}

/// Where a pass reads from and writes to.
#[derive(Clone, Debug)]
pub struct SessionPassConfig {
    /// `<tokens>/stock_quotes/IWM`.
    pub stock_quotes_root: PathBuf,
    /// `<tokens>/stock_trades/IWM`.
    pub stock_trades_root: PathBuf,
    /// Output root; PP1 lands in `<out>/pp1`, families in `<out>/families/<name>`.
    pub out_dir: PathBuf,
    /// Emit the PP1 panel.
    pub write_pp1: bool,
    /// Emit family leaves.
    pub write_families: bool,
}

/// What one session's pass measured.
#[derive(Clone, Debug)]
pub struct SessionPassOutcome {
    pub day: &'static str,
    pub session_ordinal: usize,
    pub quote_rows: u64,
    pub trade_rows: u64,
    pub actions: usize,
    pub pp1_width: usize,
    pub pp1_filled: usize,
    pub elapsed_secs: f64,
}

impl SessionPassOutcome {
    /// Rows decoded per second across both stock corpora.
    #[must_use]
    pub fn rows_per_sec(&self) -> f64 {
        if self.elapsed_secs <= 0.0 {
            return 0.0;
        }
        // Counts are corpus-scale (~10^7); f64 holds them exactly.
        #[allow(clippy::cast_precision_loss)]
        {
            (self.quote_rows + self.trade_rows) as f64 / self.elapsed_secs
        }
    }
}

/// Runs one session end to end.
///
/// `cutoffs` must be this session's actions in tape order — that is what
/// [`crate::book::load_sessions`] returns.
///
/// # Errors
///
/// [`SelectV2Error::FamilyTooWide`] if a family declares over the cap,
/// [`SelectV2Error::ContentMismatch`] if a family's row count disagrees with
/// the cutoff list, or any source/IO refusal.
// The tape walk, the cutoff announcement and the two emit steps are ONE
// linear driver on purpose: the ordering between them -- announce every
// reached cutoff BEFORE delivering the event that reached it -- is the as-of
// rule itself, and splitting the loop out would hide the single place that
// ordering is decided.
#[allow(clippy::too_many_lines)]
pub fn run_session(
    scope: &DayScope,
    cutoffs: &[ActionCutoff],
    families: &mut [Box<dyn FamilyEmitter>],
    config: &SessionPassConfig,
) -> Result<SessionPassOutcome> {
    let started = Instant::now();
    for family in families.iter() {
        check_width(family.as_ref())?;
    }
    for cutoff in cutoffs {
        if cutoff.day != scope.day() {
            return Err(SelectV2Error::Config(format!(
                "cutoff {} does not belong to session {}",
                cutoff.action_id,
                scope.day()
            )));
        }
    }

    let mut quotes = StockQuoteReader::for_scope(scope, &config.stock_quotes_root)?;
    let mut trades = StockTradeReader::for_scope(scope, &config.stock_trades_root)?;
    let mut grid = Pp1Grid::for_scope(scope);
    let open_ms = scope.open_ms_b();

    let mut quote_batch = StockQuoteBatch::default();
    let mut trade_batch = StockTradeBatch::default();
    let mut quote_index = 0_usize;
    let mut trade_index = 0_usize;
    let mut quotes_live = quotes.next_into(&mut quote_batch)?;
    let mut trades_live = trades.next_into(&mut trade_batch)?;
    let mut next_cutoff = 0_usize;

    loop {
        if quotes_live && quote_index >= quote_batch.len() {
            quotes_live = quotes.next_into(&mut quote_batch)?;
            quote_index = 0;
            continue;
        }
        if trades_live && trade_index >= trade_batch.len() {
            trades_live = trades.next_into(&mut trade_batch)?;
            trade_index = 0;
            continue;
        }
        let quote_ts = if quotes_live {
            Some(quote_batch.ts_ms_b[quote_index])
        } else {
            None
        };
        let trade_ts = if trades_live {
            Some(trade_batch.ts_ms_b[trade_index])
        } else {
            None
        };
        // Quotes win a tie: a print must be classified against the NBBO that
        // preceded it, never the one stamped at the same millisecond after it.
        let take_quote = match (quote_ts, trade_ts) {
            (Some(quote), Some(trade)) => quote <= trade,
            (Some(_), None) => true,
            (None, Some(_)) => false,
            (None, None) => break,
        };
        let ts_ms = if take_quote {
            quote_ts.unwrap_or_default()
        } else {
            trade_ts.unwrap_or_default()
        };
        let event_ns = ts_ms
            .checked_mul(1_000_000)
            .ok_or(SelectV2Error::Arithmetic("session_pass ms->ns"))?;

        // Announce every cutoff the tape has reached BEFORE delivering the
        // event that reached it. This is the as-of rule, structurally.
        while next_cutoff < cutoffs.len() && cutoffs[next_cutoff].cutoff_ns_b <= event_ns {
            for family in families.iter_mut() {
                family.on_cutoff(&cutoffs[next_cutoff]);
            }
            next_cutoff += 1;
        }

        if take_quote {
            let quote = QuoteEvent {
                ts_ms_b: ts_ms,
                bid_u6: quote_batch.bid_u6[quote_index],
                ask_u6: quote_batch.ask_u6[quote_index],
                bid_shares: quote_batch.bid_shares[quote_index],
                ask_shares: quote_batch.ask_shares[quote_index],
            };
            if config.write_pp1 {
                let slot = usize::try_from((ts_ms - open_ms).div_euclid(1_000)).unwrap_or(usize::MAX);
                grid.observe(slot, &quote);
            }
            for family in families.iter_mut() {
                family.on_quote(&quote);
            }
            quote_index += 1;
        } else {
            let trade = TradeEvent {
                ts_ms_b: ts_ms,
                price_u6: trade_batch.price_u6[trade_index],
                size: trade_batch.size[trade_index],
                exchange: trade_batch.exchange[trade_index],
                condition: trade_batch.condition[trade_index],
                sequence: trade_batch.sequence[trade_index],
                bid_u6: trade_batch.bid_u6[trade_index],
                ask_u6: trade_batch.ask_u6[trade_index],
                bid_shares: trade_batch.bid_shares[trade_index],
                ask_shares: trade_batch.ask_shares[trade_index],
                quote_present: trade_batch.quote_present[trade_index],
            };
            for family in families.iter_mut() {
                family.on_trade(&trade);
            }
            trade_index += 1;
        }
    }

    // Cutoffs at or after the session's last event still get their row, from
    // the end-of-tape state.
    while next_cutoff < cutoffs.len() {
        for family in families.iter_mut() {
            family.on_cutoff(&cutoffs[next_cutoff]);
        }
        next_cutoff += 1;
    }

    let ordinal = scope.session_ordinal();
    if config.write_pp1 {
        write_pp1(&config.out_dir, ordinal, scope.day(), &grid)?;
    }
    if config.write_families {
        for family in families.iter_mut() {
            let name = family.name();
            let width = family.columns().len();
            let specs: Vec<&'static str> = family.columns().iter().map(|spec| spec.name).collect();
            let rows = family.emit(cutoffs)?;
            if rows.columns != width || rows.rows() != cutoffs.len() {
                return Err(SelectV2Error::ContentMismatch {
                    path: PathBuf::from(name),
                    detail: format!(
                        "emitted {}x{} for {} actions x {width} declared columns",
                        rows.rows(),
                        rows.columns,
                        cutoffs.len()
                    ),
                });
            }
            write_family(&config.out_dir, ordinal, name, &specs, cutoffs, &rows)?;
        }
    }

    Ok(SessionPassOutcome {
        day: scope.day(),
        session_ordinal: ordinal,
        quote_rows: quotes.rth_rows(),
        trade_rows: trades.rth_rows(),
        actions: cutoffs.len(),
        pp1_width: grid.width(),
        pp1_filled: grid.filled(),
        elapsed_secs: started.elapsed().as_secs_f64(),
    })
}

/// `<out>/pp1/sNNNN.parquet`.
#[must_use]
pub fn pp1_path(out_dir: &Path, session_ordinal: usize) -> PathBuf {
    out_dir
        .join("pp1")
        .join(format!("s{session_ordinal:04}.parquet"))
}

/// `<out>/families/<family>/sNNNN.parquet`.
#[must_use]
pub fn family_path(out_dir: &Path, family: &str, session_ordinal: usize) -> PathBuf {
    out_dir
        .join("families")
        .join(family)
        .join(format!("s{session_ordinal:04}.parquet"))
}

fn write_pp1(out_dir: &Path, ordinal: usize, day: &str, grid: &Pp1Grid) -> Result<()> {
    let schema = Arc::new(Schema::new(vec![
        Field::new("bid", DataType::Float32, true),
        Field::new("ask", DataType::Float32, true),
        Field::new("mid", DataType::Float32, true),
    ]));
    let batch = RecordBatch::try_new(
        Arc::clone(&schema),
        vec![
            Arc::new(Float32Array::from(grid.bid.clone())),
            Arc::new(Float32Array::from(grid.ask.clone())),
            Arc::new(Float32Array::from(grid.mid.clone())),
        ],
    )
    .map_err(|source| SelectV2Error::ContentMismatch {
        path: pp1_path(out_dir, ordinal),
        detail: source.to_string(),
    })?;
    write_leaf(&pp1_path(out_dir, ordinal), &schema, &batch, day)
}

fn write_family(
    out_dir: &Path,
    ordinal: usize,
    family: &str,
    columns: &[&'static str],
    cutoffs: &[ActionCutoff],
    rows: &crate::families::FamilyRows,
) -> Result<()> {
    let mut fields = Vec::with_capacity(columns.len() + 1);
    fields.push(Field::new("action_id", DataType::Utf8, false));
    for name in columns {
        fields.push(Field::new(*name, DataType::Float32, true));
    }
    let schema = Arc::new(Schema::new(fields));
    let mut arrays: Vec<arrow_array::ArrayRef> = Vec::with_capacity(columns.len() + 1);
    arrays.push(Arc::new(StringArray::from_iter_values(
        cutoffs.iter().map(|cutoff| cutoff.action_id.as_str()),
    )));
    for column in 0..rows.columns {
        let values: Vec<f32> = (0..rows.rows())
            .map(|row| rows.values[row * rows.columns + column])
            .collect();
        arrays.push(Arc::new(Float32Array::from(values)));
    }
    let path = family_path(out_dir, family, ordinal);
    let batch = RecordBatch::try_new(Arc::clone(&schema), arrays).map_err(|source| {
        SelectV2Error::ContentMismatch {
            path: path.clone(),
            detail: source.to_string(),
        }
    })?;
    let day = cutoffs.first().map_or("", |cutoff| cutoff.day);
    write_leaf(&path, &schema, &batch, day)
}

fn write_leaf(path: &Path, schema: &Arc<Schema>, batch: &RecordBatch, day: &str) -> Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|source| SelectV2Error::Io {
            path: parent.to_path_buf(),
            source,
        })?;
    }
    let properties = WriterProperties::builder()
        .set_compression(Compression::ZSTD(
            ZstdLevel::try_new(ZSTD_LEVEL).map_err(|source| SelectV2Error::Config(source.to_string()))?,
        ))
        .set_key_value_metadata(Some(vec![parquet::file::metadata::KeyValue::new(
            "select_v2_day".to_owned(),
            day.to_owned(),
        )]))
        .build();
    let file = std::fs::File::create(path).map_err(|source| SelectV2Error::Io {
        path: path.to_path_buf(),
        source,
    })?;
    let mut writer =
        ArrowWriter::try_new(file, Arc::clone(schema), Some(properties)).map_err(|source| {
            SelectV2Error::Io {
                path: path.to_path_buf(),
                source: std::io::Error::other(source),
            }
        })?;
    writer.write(batch).map_err(|source| SelectV2Error::Io {
        path: path.to_path_buf(),
        source: std::io::Error::other(source),
    })?;
    writer.close().map_err(|source| SelectV2Error::Io {
        path: path.to_path_buf(),
        source: std::io::Error::other(source),
    })?;
    Ok(())
}

/// u6 fixed point to `f32` dollars. IWM quotes sit on 1-cent ticks around
/// $200, where `f32`'s 24-bit mantissa resolves ~1.2e-5 dollars — three orders
/// finer than a tick. The narrowing is the declared PP1 cell type.
#[allow(clippy::cast_possible_truncation, clippy::cast_precision_loss)]
#[must_use]
pub fn u6_to_f32(value: i64) -> f32 {
    (value as f64 / 1_000_000.0) as f32
}
