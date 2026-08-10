//! **F4 option-book pilot** — what the raw option-QUOTE tape adds over
//! `options_prints` + thetadata `AllGreeks`.
//!
//! This is a PILOT, not a family. It emits at `(session, minute_index)` grain
//! for a hand-picked session list so the three questions the lane exists to
//! answer can be measured rather than argued:
//!
//! 1. **Bid-ask IV width** — the dealer-uncertainty stream, in volatility
//!    points, per near-money strike bucket.
//! 2. **Book depth dynamics** — displayed size, its imbalance, and its
//!    withdrawal/refill signature between prints. `AllGreeks` carries `bid`
//!    and `ask` but **no sizes at all**, so this is structurally unavailable
//!    anywhere else.
//! 3. **Sub-minute IV innovation** — `AllGreeks` is a 1-minute ladder; the
//!    quote tape is tick-level. Within-bar dispersion of the ATM IV proxy is
//!    therefore unavailable anywhere else by construction.
//!
//! ## Grain and the as-of join
//!
//! One row per **0-based minute index** `m` in `0..bar_count`. Row `m` holds
//! the state accumulated *inside* minute `m`, which closes at
//! `open_b + (m + 1) * 60s`. The action book's `cutoff_bar_ordinal` `k` is
//! 1-based and its cutoff instant is `open_b + k * 60s`, so an action may read
//! minute indices `0..=k-1` and the newest lawful row is `m = k - 1`. The join
//! is therefore `minute_index == cutoff_bar_ordinal - 1` — never `== k`, which
//! would read the bar the cutoff opens.
//!
//! ## The IV: a real Black-76 inversion, because the closed form FAILED
//!
//! The first build used the Brenner-Subrahmanyam ATM straddle approximation
//! (`straddle ~= sqrt(2/pi) * S * sigma * sqrt(T)`) to avoid an inversion. It
//! was **measured against the vendor `AllGreeks` IV on 2023-04-17 and refused**:
//! Pearson -0.37, Spearman -0.02. The cause is structural, not a coding slip —
//! the approximation needs `K ~= F`, and for a 0DTE contract in the afternoon
//! the $1 IWM strike grid is a large multiple of `sigma * sqrt(T)`, so the
//! nearest listed strike is over half a standard deviation off ATM and the
//! straddle there is materially richer than the ATM one.
//!
//! What is emitted instead:
//!
//! * the **forward comes from put-call parity** at the ATM strike,
//!   `F = K + (C_mid - P_mid)`, so no rate or dividend assumption enters and
//!   the underlying is not needed for the option arithmetic at all;
//! * prices are **undiscounted Black-76** (`r = 0` over a horizon of hours);
//! * `sigma` is recovered by **safeguarded Newton inside a bisection bracket**
//!   on `[1e-4, 5.0]`, seeded from the tenor's last accepted `sigma`.
//!
//! Re-measured on the same session against the same vendor column, restricted
//! to the 288 of 389 minutes where the **vendor's own IV reprices the vendor's
//! own straddle to within one cent**: Pearson **+0.9971**, Spearman +0.9908,
//! median relative error **0.49%**. On the 58 minutes that disagree by over 5%
//! the vendor's IV misprices its own quotes by a median of 6.4 cents — i.e.
//! every disagreement is a vendor fit that failed, not an error here.
//!
//! `T` runs to the expiry's **16:00 ET** instant in the tape's own naive-ET
//! frame (16:15 was measured too and fits the vendor worse), floored at
//! [`MIN_T_MS`] so the last minutes of a 0DTE contract cannot divide by zero.
//! The floor binds inside the final 15 minutes and those rows are marked by
//! `f4_dte_days == 0` plus the minute index.
//!
//! Per-strike widths invert the OTM leg's bid and its ask **separately**, so
//! `f4_iv_width_wing_minus_atm` differences two true quoted IV widths rather
//! than two vega-scaled dollar spreads.
//!
//! ## Absence
//!
//! Every column is `NaN` when its input was absent — no minute is folded into
//! the previous minute's value, and no missing depth is written as `0`.
//! `f4_nm_contracts` is the observed-coverage column that separates the two.
#![allow(
    clippy::cast_possible_truncation,
    clippy::cast_precision_loss,
    clippy::cast_sign_loss,
    clippy::cast_possible_wrap,
    clippy::similar_names
)]

use crate::calendar::DayScope;
use crate::error::{Result, SelectV2Error};
use crate::session_pass::pp1_path;
use crate::sources::option_quotes::{OptionQuoteBatch, OptionQuoteReader};
use crate::sources::options_prints::Right;
use crate::sources::{DECODE_BATCH_ROWS, open_builder};
use arrow_array::{Array, Float32Array, Int32Array, RecordBatch};
use arrow_schema::{DataType, Field, Schema};
use parquet::arrow::ProjectionMask;
use parquet::basic::{Compression, ZstdLevel};
use parquet::file::properties::WriterProperties;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Instant;

/// Near-money band in log-moneyness: a strike is in scope iff
/// `|ln(K / S)| <= 0.015` (about +/- $3 on a $200 underlying).
pub const NEAR_BAND_LN: f64 = 0.015;
/// Inner bucket: `|ln(K / S)| <= 0.005` is "ATM", the rest of the band is
/// "wing". The two buckets are what `f4_iv_width_wing_minus_atm` differences.
pub const ATM_BUCKET_LN: f64 = 0.005;
/// `1 / sqrt(2 * pi)` — the standard normal density at its mode.
const INV_SQRT_2PI: f64 = 0.398_942_280_401_432_7;
/// Inversion bracket. Below the floor a quote has no recoverable volatility;
/// above the cap the quote is not an option price.
const SIGMA_LO: f64 = 1e-4;
const SIGMA_HI: f64 = 5.0;
/// Newton/bisection iterations. Seeded from the last accepted `sigma`, three
/// are typical; 24 is the safety bound, and the bracket guarantees progress.
const INVERT_ITERS: usize = 24;
/// Milliseconds in a 365-day year, the `T` denominator.
const MS_PER_YEAR: f64 = 365.0 * 24.0 * 3_600.0 * 1_000.0;
/// Floor on time to expiry. A 0DTE contract at 15:59 has minutes of life and
/// `1 / sqrt(T)` would otherwise diverge; the floor makes the column bounded
/// and the floor itself is reported.
pub const MIN_T_MS: f64 = 15.0 * 60.0 * 1_000.0;
/// Naive-ET milliseconds past midnight of the 16:00 expiry instant.
const EXPIRY_CLOSE_MS: i64 = 16 * 3_600 * 1_000;
/// Milliseconds per day.
const MS_PER_DAY: i64 = 86_400_000;
/// Strike grid quantum in u6 dollars ($0.25). Every listed IWM and RUTW strike
/// measured in this tree is a multiple of it; anything else is counted as
/// off-grid and skipped rather than folded into a neighbour.
const STRIKE_STEP_U6: i64 = 250_000;
/// Strike slots: `$0 .. $10,000` on the $0.25 grid, which covers IWM (~$200)
/// and RUTW (~$2,000) with one layout.
const STRIKE_SLOTS: usize = 40_000;
/// Tenors carried at once. The corpus holds the front one or two expirations
/// per session (measured); more than this is a corpus change, not a routine
/// day, and is refused.
const MAX_TENORS: usize = 4;

/// The 13 candidate columns plus 2 coverage columns, in emitted order.
pub const F4_PILOT_COLUMNS: [&str; 15] = [
    // --- dealer uncertainty (quote-derived) ---
    "f4_atm_iv_width",
    "f4_atm_iv_mid",
    "f4_nm_rel_spread",
    "f4_iv_width_wing_minus_atm",
    // --- book depth: sizes exist ONLY in this corpus ---
    "f4_nm_depth_total",
    "f4_nm_depth_imb",
    "f4_nm_depth_fade",
    "f4_nm_depth_min_over_mean",
    // --- sub-minute innovation: 1-min AllGreeks cannot express these ---
    "f4_quote_rev_per_s",
    "f4_submin_iv_sd",
    "f4_submin_iv_range",
    "f4_submin_iv_chg",
    "f4_spread_flicker",
    // --- coverage ---
    "f4_nm_contracts",
    "f4_dte_days",
];

/// Emitted width.
pub const F4_PILOT_WIDTH: usize = F4_PILOT_COLUMNS.len();

/// One quoted side of one contract.
#[derive(Clone, Copy, Debug, Default)]
struct Leg {
    bid_u6: i64,
    ask_u6: i64,
    bid_size: i64,
    ask_size: i64,
    live: bool,
}

impl Leg {
    /// True mid in dollars, or `None` when the quote is one-sided or crossed —
    /// `(0 + ask) / 2` is not a price.
    fn mid(self) -> Option<f64> {
        if !self.live || self.bid_u6 <= 0 || self.ask_u6 < self.bid_u6 {
            return None;
        }
        Some((self.bid_u6 as f64 + self.ask_u6 as f64) / 2_000_000.0)
    }

    fn spread(self) -> Option<f64> {
        if !self.live || self.bid_u6 <= 0 || self.ask_u6 < self.bid_u6 {
            return None;
        }
        Some((self.ask_u6 - self.bid_u6) as f64 / 1_000_000.0)
    }

    fn depth(self) -> i64 {
        if !self.live {
            return 0;
        }
        let bid = if self.bid_size == i64::MIN { 0 } else { self.bid_size };
        let ask = if self.ask_size == i64::MIN { 0 } else { self.ask_size };
        bid + ask
    }
}

/// Both legs at one strike.
#[derive(Clone, Copy, Debug, Default)]
struct StrikeState {
    call: Leg,
    put: Leg,
}

/// Streaming accumulators for one minute, one tenor.
#[derive(Clone, Copy, Debug)]
struct BarAccum {
    /// Near-money quote revisions inside the minute.
    revisions: u64,
    /// Size withdrawn with no price change (the "fade" leg of fade/refill).
    fade_withdrawn: f64,
    /// All size movement with no price change.
    fade_total: f64,
    /// Tick-resolution ATM straddle IV proxy samples.
    iv_n: u64,
    iv_sum: f64,
    iv_sq: f64,
    iv_min: f64,
    iv_max: f64,
    iv_first: f64,
    iv_last: f64,
    /// 1 Hz near-money aggregate depth samples.
    depth_n: u64,
    depth_sum: f64,
    depth_min: f64,
    /// 1 Hz near-money mean relative spread samples.
    rs_n: u64,
    rs_sum: f64,
    rs_sq: f64,
}

impl Default for BarAccum {
    fn default() -> Self {
        Self {
            revisions: 0,
            fade_withdrawn: 0.0,
            fade_total: 0.0,
            iv_n: 0,
            iv_sum: 0.0,
            iv_sq: 0.0,
            iv_min: f64::INFINITY,
            iv_max: f64::NEG_INFINITY,
            iv_first: f64::NAN,
            iv_last: f64::NAN,
            depth_n: 0,
            depth_sum: 0.0,
            depth_min: f64::INFINITY,
            rs_n: 0,
            rs_sum: 0.0,
            rs_sq: 0.0,
        }
    }
}

impl BarAccum {
    fn reset(&mut self) {
        *self = Self::default();
    }

    fn observe_iv(&mut self, iv: f64) {
        if !iv.is_finite() {
            return;
        }
        if self.iv_n == 0 {
            self.iv_first = iv;
        }
        self.iv_n += 1;
        self.iv_sum += iv;
        self.iv_sq += iv * iv;
        self.iv_min = self.iv_min.min(iv);
        self.iv_max = self.iv_max.max(iv);
        self.iv_last = iv;
    }

    /// Sample standard deviation; `NaN` below two samples (one sample has no
    /// dispersion — that is not-applicable, not zero).
    fn iv_sd(&self) -> f64 {
        if self.iv_n < 2 {
            return f64::NAN;
        }
        let n = self.iv_n as f64;
        let mean = self.iv_sum / n;
        let var = (self.iv_sq / n - mean * mean).max(0.0) * n / (n - 1.0);
        var.sqrt()
    }

    fn rs_sd(&self) -> f64 {
        if self.rs_n < 2 {
            return f64::NAN;
        }
        let n = self.rs_n as f64;
        let mean = self.rs_sum / n;
        let var = (self.rs_sq / n - mean * mean).max(0.0) * n / (n - 1.0);
        var.sqrt()
    }
}

/// Everything carried for one expiration.
struct Tenor {
    exp_day: i32,
    /// Expiry instant in the tape's own naive-ET millisecond frame.
    expiry_ms_b: i64,
    strikes: Vec<StrikeState>,
    accum: BarAccum,
    /// The $0.25-grid slot currently nearest the underlying.
    atm_slot: usize,
    atm_valid: bool,
    /// Last accepted ATM sigma — the Newton seed. A seeded inversion converges
    /// in about three iterations; a cold one needs the whole bracket.
    last_sigma: f64,
}

impl Tenor {
    fn new(exp_day: i32) -> Self {
        Self {
            exp_day,
            expiry_ms_b: i64::from(exp_day) * MS_PER_DAY + EXPIRY_CLOSE_MS,
            strikes: vec![StrikeState::default(); STRIKE_SLOTS],
            accum: BarAccum::default(),
            atm_slot: 0,
            atm_valid: false,
            last_sigma: f64::NAN,
        }
    }

    /// `sqrt(T)` in year units at a tape instant, floored.
    fn sqrt_t(&self, ts_ms: i64) -> f64 {
        let remaining = ((self.expiry_ms_b - ts_ms) as f64).max(MIN_T_MS);
        (remaining / MS_PER_YEAR).sqrt()
    }

    /// The ATM strike in dollars with its four quoted prices, or `None` when
    /// either leg is not two-sided.
    fn atm_quote(&self) -> Option<AtmQuote> {
        if !self.atm_valid {
            return None;
        }
        let state = self.strikes[self.atm_slot];
        let (call, put) = (state.call, state.put);
        if !call.live || !put.live {
            return None;
        }
        if call.bid_u6 <= 0 || put.bid_u6 <= 0 || call.ask_u6 < call.bid_u6 || put.ask_u6 < put.bid_u6
        {
            return None;
        }
        let dollars = |value: i64| value as f64 / 1_000_000.0;
        Some(AtmQuote {
            strike: self.atm_slot as f64 * 0.25,
            call_bid: dollars(call.bid_u6),
            call_ask: dollars(call.ask_u6),
            put_bid: dollars(put.bid_u6),
            put_ask: dollars(put.ask_u6),
        })
    }

    /// The ATM straddle IV triple `(bid, mid, ask)` in volatility points, and
    /// the parity forward, at a tape instant. `None` when the ATM strike is not
    /// two-sided or the straddle carries no time value.
    fn atm_iv(&self, ts_ms: i64, seed: f64) -> Option<(f64, f64, f64, f64)> {
        let quote = self.atm_quote()?;
        let sqrt_t = self.sqrt_t(ts_ms);
        let forward = quote.forward();
        let strike = quote.strike;
        let bid = invert_straddle(quote.straddle_bid(), forward, strike, sqrt_t, seed);
        let mid = invert_straddle(quote.straddle_mid(), forward, strike, sqrt_t, seed);
        let ask = invert_straddle(quote.straddle_ask(), forward, strike, sqrt_t, seed);
        Some((bid, mid, ask, forward))
    }
}

/// The ATM strike's four quoted prices, in dollars.
#[derive(Clone, Copy, Debug)]
struct AtmQuote {
    strike: f64,
    call_bid: f64,
    call_ask: f64,
    put_bid: f64,
    put_ask: f64,
}

impl AtmQuote {
    /// Put-call parity forward, `K + (C_mid - P_mid)`. Undiscounted: over a
    /// horizon of hours the discount factor is within a tenth of a basis point
    /// of one, and using it would import a rate assumption the tape does not
    /// carry.
    fn forward(self) -> f64 {
        let call_mid = f64::midpoint(self.call_bid, self.call_ask);
        let put_mid = f64::midpoint(self.put_bid, self.put_ask);
        self.strike + call_mid - put_mid
    }

    fn straddle_bid(self) -> f64 {
        self.call_bid + self.put_bid
    }

    fn straddle_ask(self) -> f64 {
        self.call_ask + self.put_ask
    }

    fn straddle_mid(self) -> f64 {
        f64::midpoint(self.straddle_bid(), self.straddle_ask())
    }
}

/// Standard normal CDF — Zelen & Severo, Abramowitz & Stegun 26.2.17, whose
/// absolute error is below `7.5e-8`. That is three orders finer than the
/// `f32` cell this pilot writes and two finer than the `1e-5` volatility the
/// inversion resolves.
fn norm_cdf(x: f64) -> f64 {
    const B: [f64; 5] = [
        0.319_381_530,
        -0.356_563_782,
        1.781_477_937,
        -1.821_255_978,
        1.330_274_429,
    ];
    const P: f64 = 0.231_641_9;
    let negative = x < 0.0;
    let x = x.abs();
    let t = 1.0 / (1.0 + P * x);
    let poly = t * (B[0] + t * (B[1] + t * (B[2] + t * (B[3] + t * B[4]))));
    let upper = INV_SQRT_2PI * (-0.5 * x * x).exp() * poly;
    if negative { upper } else { 1.0 - upper }
}

fn norm_pdf(x: f64) -> f64 {
    INV_SQRT_2PI * (-0.5 * x * x).exp()
}

fn d1_of(forward: f64, strike: f64, vol: f64) -> f64 {
    ((forward / strike).ln() + 0.5 * vol * vol) / vol
}

/// Undiscounted Black-76 straddle.
fn straddle_price(forward: f64, strike: f64, sigma: f64, sqrt_t: f64) -> f64 {
    let vol = sigma * sqrt_t;
    if vol <= 0.0 {
        return (forward - strike).abs();
    }
    let d1 = d1_of(forward, strike, vol);
    let d2 = d1 - vol;
    2.0f64.mul_add(
        strike.mul_add(-norm_cdf(d2), forward * norm_cdf(d1)),
        strike - forward,
    )
}

/// Undiscounted Black-76 call or put.
fn option_price(forward: f64, strike: f64, sigma: f64, sqrt_t: f64, call: bool) -> f64 {
    let vol = sigma * sqrt_t;
    if vol <= 0.0 {
        return if call {
            (forward - strike).max(0.0)
        } else {
            (strike - forward).max(0.0)
        };
    }
    let d1 = d1_of(forward, strike, vol);
    let d2 = d1 - vol;
    if call {
        strike.mul_add(-norm_cdf(d2), forward * norm_cdf(d1))
    } else {
        strike.mul_add(norm_cdf(-d2), -(forward * norm_cdf(-d1)))
    }
}

/// `d(price) / d(sigma)` for one option; the straddle's is twice this.
fn option_vega(forward: f64, strike: f64, sigma: f64, sqrt_t: f64) -> f64 {
    let vol = sigma * sqrt_t;
    if vol <= 0.0 {
        return 0.0;
    }
    forward * norm_pdf(d1_of(forward, strike, vol)) * sqrt_t
}

/// Safeguarded Newton inside a bisection bracket. Returns `NaN` — never a
/// bracket endpoint — when the target is at or below intrinsic (no recoverable
/// time value) or above the price at [`SIGMA_HI`].
fn invert(
    target: f64,
    intrinsic: f64,
    sqrt_t: f64,
    seed: f64,
    price: impl Fn(f64) -> f64,
    vega: impl Fn(f64) -> f64,
) -> f64 {
    if !target.is_finite() || !sqrt_t.is_finite() || sqrt_t <= 0.0 {
        return f64::NAN;
    }
    if target <= intrinsic + 1e-9 || price(SIGMA_HI) < target {
        return f64::NAN;
    }
    let (mut lo, mut hi) = (SIGMA_LO, SIGMA_HI);
    let mut sigma = if seed.is_finite() {
        seed.clamp(lo, hi)
    } else {
        0.25
    };
    for _ in 0..INVERT_ITERS {
        let err = price(sigma) - target;
        if err.abs() < 1e-9 {
            return sigma;
        }
        if err > 0.0 {
            hi = sigma;
        } else {
            lo = sigma;
        }
        let slope = vega(sigma);
        let next = if slope > 1e-12 {
            sigma - err / slope
        } else {
            f64::NAN
        };
        sigma = if next.is_finite() && next > lo && next < hi {
            next
        } else {
            f64::midpoint(lo, hi)
        };
    }
    sigma
}

fn invert_straddle(target: f64, forward: f64, strike: f64, sqrt_t: f64, seed: f64) -> f64 {
    invert(
        target,
        (forward - strike).abs(),
        sqrt_t,
        seed,
        |sigma| straddle_price(forward, strike, sigma, sqrt_t),
        |sigma| 2.0 * option_vega(forward, strike, sigma, sqrt_t),
    )
}

fn invert_option(
    target: f64,
    forward: f64,
    strike: f64,
    sqrt_t: f64,
    seed: f64,
    call: bool,
) -> f64 {
    let intrinsic = if call {
        (forward - strike).max(0.0)
    } else {
        (strike - forward).max(0.0)
    };
    invert(
        target,
        intrinsic,
        sqrt_t,
        seed,
        |sigma| option_price(forward, strike, sigma, sqrt_t, call),
        |sigma| option_vega(forward, strike, sigma, sqrt_t),
    )
}

/// What one pilot session measured.
#[derive(Clone, Debug)]
pub struct F4PilotOutcome {
    pub day: &'static str,
    pub session_ordinal: usize,
    /// RTH rows the reader emitted (the decode denominator).
    pub rth_rows: u64,
    /// Rows that fell inside the near-money band of a carried tenor.
    pub near_money_rows: u64,
    /// Rows skipped because PP1 had no underlying for that second.
    pub no_spot_rows: u64,
    /// Rows whose strike was not on the $0.25 grid.
    pub off_grid_rows: u64,
    /// Compressed bytes of this session's shards.
    pub source_bytes: u64,
    pub shards: usize,
    /// Distinct expirations carried.
    pub tenors: usize,
    /// Days to expiry of the emitted tenor.
    pub dte_t1: i32,
    /// Minutes whose ATM straddle IV proxy was computable.
    pub bars_with_atm: usize,
    pub bar_count: usize,
    pub decode_secs: f64,
    pub total_secs: f64,
}

impl F4PilotOutcome {
    #[must_use]
    pub fn rows_per_sec(&self) -> f64 {
        if self.decode_secs <= 0.0 {
            return 0.0;
        }
        self.rth_rows as f64 / self.decode_secs
    }

    #[must_use]
    pub fn mib_per_sec(&self) -> f64 {
        if self.decode_secs <= 0.0 {
            return 0.0;
        }
        self.source_bytes as f64 / 1_048_576.0 / self.decode_secs
    }
}

/// Where a pilot session reads from and writes to.
#[derive(Clone, Debug)]
pub struct F4PilotConfig {
    /// `<tokens>/option_quotes/IWM` or `<tokens>/RUTW/option_quotes`.
    pub quotes_root: PathBuf,
    /// Root holding `pp1/sNNNN.parquet` (the emitted 1-second mid panel).
    pub pp1_root: PathBuf,
    /// Output root; leaves land in `<out>/f4_pilot/sNNNN.parquet`.
    pub out_dir: PathBuf,
    /// Decode and discard — the isolation measurement for the cost projection.
    pub decode_only: bool,
}

/// Reads the session's PP1 mid column and forward-fills it into a per-second
/// underlying series. Forward fill is lawful here (and only here): PP1's own
/// `NaN` means "no quote in that second", and the last observed NBBO mid is
/// the correct as-of underlying for a quote stamped inside a quiet second.
fn load_spot(pp1_root: &Path, ordinal: usize, width: usize) -> Result<Vec<f64>> {
    let path = pp1_path(pp1_root, ordinal);
    let builder = open_builder(&path)?;
    let names: Vec<String> = builder
        .schema()
        .fields()
        .iter()
        .map(|field| field.name().clone())
        .collect();
    let mid = names
        .iter()
        .position(|name| name == "mid")
        .ok_or_else(|| SelectV2Error::SchemaMismatch {
            path: path.clone(),
            detail: format!("PP1 has no `mid` column (has {names:?})"),
        })?;
    let projection = ProjectionMask::roots(builder.parquet_schema(), [mid]);
    let mut reader = builder
        .with_projection(projection)
        .with_batch_size(DECODE_BATCH_ROWS)
        .build()
        .map_err(|source| SelectV2Error::Io {
            path: path.clone(),
            source: std::io::Error::other(source),
        })?;
    let mut spot = Vec::with_capacity(width);
    let mut last = f64::NAN;
    while let Some(batch) = reader.next() {
        let batch = batch.map_err(|source| SelectV2Error::Io {
            path: path.clone(),
            source: std::io::Error::other(source),
        })?;
        let column = batch
            .column(0)
            .as_any()
            .downcast_ref::<Float32Array>()
            .ok_or_else(|| SelectV2Error::SchemaMismatch {
                path: path.clone(),
                detail: "PP1 `mid` is not float32".to_owned(),
            })?;
        for row in 0..column.len() {
            let value = if column.is_null(row) {
                f64::NAN
            } else {
                f64::from(column.value(row))
            };
            if value.is_finite() && value > 0.0 {
                last = value;
            }
            spot.push(last);
        }
    }
    if spot.len() != width {
        return Err(SelectV2Error::ContentMismatch {
            path,
            detail: format!("PP1 has {} slots, this session's width is {width}", spot.len()),
        });
    }
    Ok(spot)
}

/// The `$0.25`-grid slot of a u6 strike, or `None` when it is off-grid or out
/// of range.
fn strike_slot(strike_u6: i64) -> Option<usize> {
    if strike_u6 <= 0 || strike_u6 % STRIKE_STEP_U6 != 0 {
        return None;
    }
    let slot = (strike_u6 / STRIKE_STEP_U6) as usize;
    (slot < STRIKE_SLOTS).then_some(slot)
}

/// Runs one pilot session end to end.
///
/// # Errors
///
/// Any reader, PP1 or write refusal; [`SelectV2Error::ContentMismatch`] if the
/// session carries more than [`MAX_TENORS`] expirations (a corpus change).
#[allow(clippy::too_many_lines)]
pub fn run_session(scope: &DayScope, config: &F4PilotConfig) -> Result<F4PilotOutcome> {
    let started = Instant::now();
    let bar_count = scope.bar_count() as usize;
    let width = scope.pp1_width();
    let spot = load_spot(&config.pp1_root, scope.session_ordinal(), width)?;
    let session_day = corpus::CivilDate::parse(scope.day())
        .map_err(SelectV2Error::Corpus)?
        .unix_day_ordinal() as i32;

    let mut reader = OptionQuoteReader::for_scope(scope, &config.quotes_root)?;
    let shards = reader.shards().len();
    let source_bytes: u64 = reader
        .shards()
        .iter()
        .filter_map(|path| std::fs::metadata(path).ok().map(|meta| meta.len()))
        .sum();

    let open_ms = scope.open_ms_b();
    let mut tenors: Vec<Tenor> = Vec::with_capacity(MAX_TENORS);
    // Row-major `bar_count x F4_PILOT_WIDTH`, all NaN until a bar closes.
    let mut out = vec![f32::NAN; bar_count * F4_PILOT_WIDTH];
    let mut batch = OptionQuoteBatch::default();
    let mut cur_bar: usize = 0;
    let mut cur_sec: i64 = -1;
    let mut spot_now = f64::NAN;
    let (mut near_money_rows, mut no_spot_rows, mut off_grid_rows) = (0_u64, 0_u64, 0_u64);
    let mut decode_secs = 0.0_f64;

    loop {
        let decode_started = Instant::now();
        let live = reader.next_into(&mut batch)?;
        decode_secs += decode_started.elapsed().as_secs_f64();
        if !live {
            break;
        }
        if config.decode_only {
            continue;
        }
        for row in 0..batch.len() {
            let right = batch.right[row];
            if matches!(right, Right::Other) {
                continue;
            }
            let ts_ms = batch.ts_ms_b[row];
            let since_open = ts_ms - open_ms;
            let bar = (since_open / 60_000) as usize;
            let sec = since_open / 1_000;

            if bar > cur_bar {
                let stop = bar.min(bar_count);
                for index in cur_bar..stop {
                    close_bar(&mut out, index, &mut tenors, spot_now, open_ms, session_day);
                }
                cur_bar = stop;
                if cur_bar >= bar_count {
                    break;
                }
            }
            if sec != cur_sec {
                cur_sec = sec;
                spot_now = spot.get(sec.max(0) as usize).copied().unwrap_or(f64::NAN);
                if spot_now.is_finite() {
                    for tenor in &mut tenors {
                        retarget_atm(tenor, spot_now);
                        sample_second(tenor, spot_now);
                    }
                }
            }
            if !spot_now.is_finite() {
                no_spot_rows += 1;
                continue;
            }

            let strike_u6 = batch.strike_u6[row];
            let Some(slot) = strike_slot(strike_u6) else {
                off_grid_rows += 1;
                continue;
            };
            let strike = strike_u6 as f64 / 1_000_000.0;
            if (strike / spot_now).ln().abs() > NEAR_BAND_LN {
                continue;
            }

            let exp_day = batch.expiration_day[row];
            if exp_day == i32::MIN || exp_day < session_day {
                continue;
            }
            let index = match tenors.iter().position(|tenor| tenor.exp_day == exp_day) {
                Some(index) => index,
                None => {
                    if tenors.len() >= MAX_TENORS {
                        return Err(SelectV2Error::ContentMismatch {
                            path: config.quotes_root.join(scope.day()),
                            detail: format!(
                                "session carries more than {MAX_TENORS} expirations; the \
                                 measured corpus holds the front one or two"
                            ),
                        });
                    }
                    let mut tenor = Tenor::new(exp_day);
                    retarget_atm(&mut tenor, spot_now);
                    tenors.push(tenor);
                    tenors.len() - 1
                }
            };
            near_money_rows += 1;

            let tenor = &mut tenors[index];
            let next = Leg {
                bid_u6: batch.bid_u6[row],
                ask_u6: batch.ask_u6[row],
                bid_size: batch.bid_size[row],
                ask_size: batch.ask_size[row],
                live: true,
            };
            let state = &mut tenor.strikes[slot];
            let leg = match right {
                Right::Call => &mut state.call,
                _ => &mut state.put,
            };
            // Fade/refill: size movement with the quoted PRICE unchanged is
            // pure displayed-liquidity behaviour, which is the whole point of
            // reading this corpus. A size move that accompanies a price move is
            // a re-quote and is deliberately excluded.
            if leg.live && leg.bid_u6 == next.bid_u6 && leg.ask_u6 == next.ask_u6 {
                let delta = (next.depth() - leg.depth()) as f64;
                if delta != 0.0 {
                    tenor.accum.fade_total += delta.abs();
                    if delta < 0.0 {
                        tenor.accum.fade_withdrawn += -delta;
                    }
                }
            }
            *leg = next;
            tenor.accum.revisions += 1;
            // Tick-resolution IV sampling, and only at the ATM strike: that is
            // the sub-minute innovation stream a 1-minute ladder cannot hold.
            if tenor.atm_valid && slot == tenor.atm_slot {
                let seed = tenor.last_sigma;
                if let Some(quote) = tenor.atm_quote() {
                    let sigma = invert_straddle(
                        quote.straddle_mid(),
                        quote.forward(),
                        quote.strike,
                        tenor.sqrt_t(ts_ms),
                        seed,
                    );
                    if sigma.is_finite() {
                        tenor.last_sigma = sigma;
                        tenor.accum.observe_iv(sigma);
                    }
                }
            }
        }
    }
    for index in cur_bar..bar_count {
        close_bar(&mut out, index, &mut tenors, spot_now, open_ms, session_day);
    }

    let dte_t1 = tenors
        .iter()
        .map(|tenor| tenor.exp_day)
        .min()
        .map_or(-1, |exp| exp - session_day);
    let atm_column = column_index("f4_atm_iv_mid");
    let bars_with_atm = (0..bar_count)
        .filter(|bar| out[bar * F4_PILOT_WIDTH + atm_column].is_finite())
        .count();

    if !config.decode_only {
        write_leaf(scope, &config.out_dir, &out, bar_count)?;
    }
    Ok(F4PilotOutcome {
        day: scope.day(),
        session_ordinal: scope.session_ordinal(),
        rth_rows: reader.rth_rows(),
        near_money_rows,
        no_spot_rows,
        off_grid_rows,
        source_bytes,
        shards,
        tenors: tenors.len(),
        dte_t1,
        bars_with_atm,
        bar_count,
        decode_secs,
        total_secs: started.elapsed().as_secs_f64(),
    })
}

fn column_index(name: &str) -> usize {
    F4_PILOT_COLUMNS
        .iter()
        .position(|column| *column == name)
        .unwrap_or(0)
}

/// Repoints a tenor's ATM slot at the listed strike nearest the underlying,
/// searching outward on the `$0.25` grid for one that is two-sided on BOTH
/// legs. Falls back to `atm_valid = false` rather than to a one-sided strike.
fn retarget_atm(tenor: &mut Tenor, spot: f64) {
    let centre = (spot / 0.25).round() as i64;
    // Which side of the rounded centre the spot really sits on decides which
    // of the two equal-offset candidates is nearer; searching `+offset` first
    // unconditionally would pick the farther listed strike about half the time.
    let below_first = spot < centre as f64 * 0.25;
    tenor.atm_valid = false;
    // +/- 16 grid steps is +/- $4, which spans the near-money band on IWM and
    // reaches the next listed strike on RUTW's coarser ladder.
    for offset in 0..=16_i64 {
        let ordered = if below_first {
            [centre - offset, centre + offset]
        } else {
            [centre + offset, centre - offset]
        };
        for (rank, slot) in ordered.into_iter().enumerate() {
            if offset == 0 && rank == 1 {
                break;
            }
            if slot <= 0 || slot as usize >= STRIKE_SLOTS {
                continue;
            }
            let slot = slot as usize;
            let state = tenor.strikes[slot];
            if state.call.live && state.put.live {
                tenor.atm_slot = slot;
                tenor.atm_valid = true;
                return;
            }
        }
    }
}

/// The near-money grid-slot span for a spot, clamped to the array.
fn near_span(spot: f64) -> (usize, usize) {
    let lo = ((spot * (-NEAR_BAND_LN).exp()) / 0.25).floor().max(1.0) as usize;
    let hi = (((spot * NEAR_BAND_LN.exp()) / 0.25).ceil() as usize).min(STRIKE_SLOTS - 1);
    (lo.min(hi), hi)
}

/// 1 Hz aggregate sample: near-money displayed depth and mean relative spread.
/// Depth is aggregated at 1 Hz rather than per row because the band itself
/// moves with the underlying; a per-row incremental total would drift as
/// strikes entered and left it.
fn sample_second(tenor: &mut Tenor, spot: f64) {
    let (lo, hi) = near_span(spot);
    let mut depth = 0_i64;
    let mut rs_sum = 0.0_f64;
    let mut rs_n = 0_u32;
    for slot in lo..=hi {
        let state = tenor.strikes[slot];
        depth += state.call.depth() + state.put.depth();
        let strike = slot as f64 * 0.25;
        let leg = if strike >= spot { state.call } else { state.put };
        if let (Some(spread), Some(mid)) = (leg.spread(), leg.mid()) {
            if mid > 0.0 {
                rs_sum += spread / mid;
                rs_n += 1;
            }
        }
    }
    if depth > 0 {
        let depth = depth as f64;
        tenor.accum.depth_n += 1;
        tenor.accum.depth_sum += depth;
        tenor.accum.depth_min = tenor.accum.depth_min.min(depth);
    }
    if rs_n > 0 {
        let mean = rs_sum / f64::from(rs_n);
        tenor.accum.rs_n += 1;
        tenor.accum.rs_sum += mean;
        tenor.accum.rs_sq += mean * mean;
    }
}

/// Writes minute `bar`'s row from the front tenor's bar-close state plus its
/// within-bar accumulators, then resets every tenor's accumulators.
fn close_bar(
    out: &mut [f32],
    bar: usize,
    tenors: &mut [Tenor],
    spot: f64,
    open_ms: i64,
    session_day: i32,
) {
    let base = bar * F4_PILOT_WIDTH;
    // The front tenor is the emitted one; later tenors still accumulate so a
    // follow-on lane can widen without a second corpus pass.
    let front = tenors
        .iter()
        .enumerate()
        .min_by_key(|(_, tenor)| tenor.exp_day)
        .map(|(index, _)| index);
    if let (Some(index), true) = (front, spot.is_finite()) {
        let close_ms = open_ms + (bar as i64 + 1) * 60_000;
        let tenor = &tenors[index];
        let sqrt_t = tenor.sqrt_t(close_ms);
        let (iv_bid, iv_mid, iv_ask, forward) = tenor
            .atm_iv(close_ms, tenor.last_sigma)
            .unwrap_or((f64::NAN, f64::NAN, f64::NAN, f64::NAN));

        let (lo, hi) = near_span(spot);
        let mut bid_depth = 0_i64;
        let mut ask_depth = 0_i64;
        let mut contracts = 0_u32;
        let mut rs_sum = 0.0_f64;
        let mut rs_n = 0_u32;
        let (mut atm_w_sum, mut atm_w_n) = (0.0_f64, 0_u32);
        let (mut wing_w_sum, mut wing_w_n) = (0.0_f64, 0_u32);
        for slot in lo..=hi {
            let state = tenor.strikes[slot];
            for leg in [state.call, state.put] {
                if leg.live {
                    contracts += 1;
                    bid_depth += if leg.bid_size == i64::MIN { 0 } else { leg.bid_size };
                    ask_depth += if leg.ask_size == i64::MIN { 0 } else { leg.ask_size };
                }
            }
            let strike = slot as f64 * 0.25;
            // The OTM leg is the liquid one at every strike; using it on both
            // sides keeps the two buckets comparable.
            let call = strike >= spot;
            let leg = if call { state.call } else { state.put };
            let (Some(spread), Some(mid)) = (leg.spread(), leg.mid()) else {
                continue;
            };
            if mid > 0.0 {
                rs_sum += spread / mid;
                rs_n += 1;
            }
            // The TRUE quoted IV width at this strike: invert the leg's bid and
            // its ask separately. A vega-scaled dollar spread was the earlier
            // build and it inherited the approximation this file's header
            // records as refused.
            if forward.is_finite() {
                let bid = invert_option(
                    leg.bid_u6 as f64 / 1_000_000.0,
                    forward,
                    strike,
                    sqrt_t,
                    iv_mid,
                    call,
                );
                let ask = invert_option(
                    leg.ask_u6 as f64 / 1_000_000.0,
                    forward,
                    strike,
                    sqrt_t,
                    iv_mid,
                    call,
                );
                let width = ask - bid;
                if width.is_finite() && width >= 0.0 {
                    if (strike / spot).ln().abs() <= ATM_BUCKET_LN {
                        atm_w_sum += width;
                        atm_w_n += 1;
                    } else {
                        wing_w_sum += width;
                        wing_w_n += 1;
                    }
                }
            }
        }

        let accum = tenor.accum;
        let total_depth = bid_depth + ask_depth;
        let values: [f64; F4_PILOT_WIDTH] = [
            iv_ask - iv_bid,
            iv_mid,
            if rs_n > 0 { rs_sum / f64::from(rs_n) } else { f64::NAN },
            if atm_w_n > 0 && wing_w_n > 0 {
                wing_w_sum / f64::from(wing_w_n) - atm_w_sum / f64::from(atm_w_n)
            } else {
                f64::NAN
            },
            if contracts > 0 { total_depth as f64 } else { f64::NAN },
            if total_depth > 0 {
                (bid_depth - ask_depth) as f64 / total_depth as f64
            } else {
                f64::NAN
            },
            if accum.fade_total > 0.0 {
                accum.fade_withdrawn / accum.fade_total
            } else {
                f64::NAN
            },
            if accum.depth_n > 0 && accum.depth_sum > 0.0 {
                accum.depth_min / (accum.depth_sum / accum.depth_n as f64)
            } else {
                f64::NAN
            },
            accum.revisions as f64 / 60.0,
            accum.iv_sd(),
            if accum.iv_n >= 2 {
                accum.iv_max - accum.iv_min
            } else {
                f64::NAN
            },
            if accum.iv_n >= 2 {
                accum.iv_last - accum.iv_first
            } else {
                f64::NAN
            },
            accum.rs_sd(),
            f64::from(contracts),
            f64::from(tenor.exp_day - session_day),
        ];
        for (offset, value) in values.iter().enumerate() {
            out[base + offset] = narrow(*value);
        }
    }
    for tenor in tenors.iter_mut() {
        tenor.accum.reset();
    }
}

/// `f64` to the emitted `f32`, with every non-finite value collapsed to `NaN`
/// so no cell can carry a signed infinity.
fn narrow(value: f64) -> f32 {
    if value.is_finite() { value as f32 } else { f32::NAN }
}

fn write_leaf(scope: &DayScope, out_dir: &Path, values: &[f32], bar_count: usize) -> Result<()> {
    let mut fields = Vec::with_capacity(F4_PILOT_WIDTH + 2);
    fields.push(Field::new("session_ordinal", DataType::Int32, false));
    fields.push(Field::new("minute_index", DataType::Int32, false));
    for name in F4_PILOT_COLUMNS {
        fields.push(Field::new(name, DataType::Float32, true));
    }
    let schema = Arc::new(Schema::new(fields));
    let mut arrays: Vec<arrow_array::ArrayRef> = Vec::with_capacity(F4_PILOT_WIDTH + 2);
    arrays.push(Arc::new(Int32Array::from(vec![
        scope.session_ordinal() as i32;
        bar_count
    ])));
    arrays.push(Arc::new(Int32Array::from(
        (0..bar_count as i32).collect::<Vec<i32>>(),
    )));
    for column in 0..F4_PILOT_WIDTH {
        arrays.push(Arc::new(Float32Array::from(
            (0..bar_count)
                .map(|row| values[row * F4_PILOT_WIDTH + column])
                .collect::<Vec<f32>>(),
        )));
    }
    let path = out_dir
        .join("f4_pilot")
        .join(format!("s{:04}.parquet", scope.session_ordinal()));
    let batch = RecordBatch::try_new(Arc::clone(&schema), arrays).map_err(|source| {
        SelectV2Error::ContentMismatch {
            path: path.clone(),
            detail: source.to_string(),
        }
    })?;
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|source| SelectV2Error::Io {
            path: parent.to_path_buf(),
            source,
        })?;
    }
    let properties = WriterProperties::builder()
        .set_compression(Compression::ZSTD(
            ZstdLevel::try_new(3).map_err(|source| SelectV2Error::Config(source.to_string()))?,
        ))
        .set_key_value_metadata(Some(vec![parquet::file::metadata::KeyValue::new(
            "select_v2_day".to_owned(),
            scope.day().to_owned(),
        )]))
        .build();
    let file = std::fs::File::create(&path).map_err(|source| SelectV2Error::Io {
        path: path.clone(),
        source,
    })?;
    let mut writer = parquet::arrow::ArrowWriter::try_new(file, schema, Some(properties))
        .map_err(|source| SelectV2Error::Io {
            path: path.clone(),
            source: std::io::Error::other(source),
        })?;
    writer.write(&batch).map_err(|source| SelectV2Error::Io {
        path: path.clone(),
        source: std::io::Error::other(source),
    })?;
    writer.close().map_err(|source| SelectV2Error::Io {
        path,
        source: std::io::Error::other(source),
    })?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Every inversion this file performs must return the volatility that
    /// produced the price, over the whole region the 0DTE pilot visits.
    #[test]
    fn inversion_round_trips_over_the_pilot_region() {
        let forward = 178.82_f64;
        let (mut recovered, mut degenerate) = (0_u32, 0_u32);
        // Strikes inside the near-money band this pilot actually reads. Some of
        // them price to pure intrinsic at 15 minutes and low volatility — a
        // real property of a 0DTE book, not a gap in the grid — and those must
        // come back NaN instead of a fabricated volatility.
        for strike in [177.0, 178.0, 178.75, 179.0, 180.0] {
            for sigma in [0.15, 0.28, 0.55, 1.20] {
                for minutes in [15.0, 30.0, 90.0, 390.0] {
                    let sqrt_t = (minutes * 60_000.0 / MS_PER_YEAR).sqrt();
                    let price = straddle_price(forward, strike, sigma, sqrt_t);
                    let back = invert_straddle(price, forward, strike, sqrt_t, f64::NAN);
                    if price - (forward - strike).abs() <= 1e-9 {
                        assert!(
                            back.is_nan(),
                            "K={strike} sigma={sigma} m={minutes} has no time value \
                             but inverted to {back}"
                        );
                        degenerate += 1;
                        continue;
                    }
                    // The inversion converges to 1e-9 in PRICE, so the volatility
                    // it can pin down is `1e-9 / vega` — asserting a flat 1e-6
                    // everywhere would be asserting something the arithmetic
                    // cannot deliver on a nearly vega-less deep wing.
                    let straddle_vega = 2.0 * option_vega(forward, strike, sigma, sqrt_t);
                    let tolerance = (1e-9 / straddle_vega).max(1e-6);
                    assert!(
                        (back - sigma).abs() < tolerance,
                        "straddle K={strike} sigma={sigma} m={minutes}: got {back} \
                         (tolerance {tolerance:e}, vega {straddle_vega:e})"
                    );
                    for call in [true, false] {
                        let leg = option_price(forward, strike, sigma, sqrt_t, call);
                        let legs = invert_option(leg, forward, strike, sqrt_t, f64::NAN, call);
                        let leg_tolerance =
                            (1e-9 / option_vega(forward, strike, sigma, sqrt_t)).max(1e-6);
                        assert!(
                            legs.is_nan() || (legs - sigma).abs() < leg_tolerance,
                            "leg call={call} K={strike} sigma={sigma} m={minutes}: got {legs}"
                        );
                    }
                    recovered += 1;
                }
            }
        }
        assert!(recovered >= 60, "only {recovered} of 80 grid points recovered");
        assert!(degenerate >= 1, "the no-time-value branch was never exercised");
    }

    /// A straddle quoted at exactly its intrinsic value carries no volatility.
    /// The inversion must say so with `NaN` rather than returning a bracket
    /// endpoint that would look like a real 0.0001 or 5.0 volatility.
    #[test]
    fn no_time_value_yields_nan_not_a_bracket_endpoint() {
        let sqrt_t = (15.0 * 60_000.0 / MS_PER_YEAR).sqrt();
        let (forward, strike) = (178.82_f64, 170.0_f64);
        let intrinsic = forward - strike;
        assert!(invert_straddle(intrinsic, forward, strike, sqrt_t, f64::NAN).is_nan());
        assert!(invert_straddle(intrinsic - 0.5, forward, strike, sqrt_t, f64::NAN).is_nan());
        // and a price no volatility in the bracket can reach is also NaN
        assert!(invert_straddle(1e9, forward, strike, sqrt_t, f64::NAN).is_nan());
    }

    /// The bracket is only safe because the straddle rises with volatility.
    #[test]
    fn straddle_price_is_monotone_in_sigma() {
        let sqrt_t = (30.0 * 60_000.0 / MS_PER_YEAR).sqrt();
        let mut previous = f64::NEG_INFINITY;
        for step in 1..=200 {
            let price = straddle_price(178.82, 179.0, f64::from(step) * 0.02, sqrt_t);
            assert!(price > previous, "not monotone at step {step}");
            previous = price;
        }
    }

    /// **The measured failure, kept executable.** The first build of this file
    /// used the Brenner-Subrahmanyam closed form and was refused against the
    /// vendor IV (Pearson -0.37). The refusal reproduces here, and the bounds
    /// below are the COMPUTED error surface at `F = 178.82`, `sigma = 0.30`,
    /// not round numbers: the closed form errs 9.75% one strike off the forward
    /// at 30 minutes, 19.14% at 15 minutes, and 198% one further strike out at
    /// 15 minutes, while the inversion is exact to `1e-6` at every one of them.
    /// The error also has to shrink with time to expiry — that direction IS the
    /// structural claim. If anyone reintroduces the shortcut, this goes red.
    #[test]
    fn closed_form_proxy_fails_where_the_inversion_is_exact() {
        const BS_COEFFICIENT: f64 = 0.797_884_560_802_865_4; // sqrt(2 / pi)
        let (forward, sigma) = (178.82_f64, 0.30_f64);
        let proxy_error = |strike: f64, minutes: f64| {
            let sqrt_t = (minutes * 60_000.0 / MS_PER_YEAR).sqrt();
            let price = straddle_price(forward, strike, sigma, sqrt_t);
            let inverted = invert_straddle(price, forward, strike, sqrt_t, f64::NAN);
            assert!(
                (inverted - sigma).abs() < 1e-6,
                "inversion drifted at K={strike} m={minutes}: {inverted}"
            );
            let proxy = price / (BS_COEFFICIENT * forward * sqrt_t);
            (proxy - sigma).abs() / sigma
        };
        let at_30 = proxy_error(179.0, 30.0);
        let at_15 = proxy_error(179.0, 15.0);
        let at_15_wide = proxy_error(179.5, 15.0);
        let at_full_day = proxy_error(179.0, 390.0);
        assert!(at_30 > 0.05, "30-minute error collapsed to {at_30}");
        assert!(at_15 > 0.15, "15-minute error collapsed to {at_15}");
        assert!(at_15_wide > 1.0, "wide-strike error collapsed to {at_15_wide}");
        assert!(
            at_15 > at_30 && at_30 > at_full_day,
            "the proxy error must grow as T shrinks; got {at_full_day} -> {at_30} -> {at_15}"
        );
    }

    #[test]
    fn norm_cdf_matches_known_values() {
        assert!((norm_cdf(0.0) - 0.5).abs() < 1e-9);
        assert!((norm_cdf(1.959_963_985) - 0.975).abs() < 1e-7);
        assert!((norm_cdf(-1.959_963_985) - 0.025).abs() < 1e-7);
        assert!((norm_cdf(6.0) - 1.0).abs() < 1e-8);
    }

    /// An off-grid strike is skipped and counted, never folded into a neighbour.
    #[test]
    fn strike_slot_refuses_off_grid_strikes() {
        assert_eq!(strike_slot(176_000_000), Some(704));
        assert_eq!(strike_slot(176_250_000), Some(705));
        assert_eq!(strike_slot(176_100_000), None);
        assert_eq!(strike_slot(0), None);
        assert_eq!(strike_slot(-1), None);
        assert_eq!(strike_slot(20_000_000_000), None);
    }

    #[test]
    fn near_span_brackets_the_declared_band() {
        let spot = 200.0_f64;
        let (lo, hi) = near_span(spot);
        let (low_strike, high_strike) = (lo as f64 * 0.25, hi as f64 * 0.25);
        assert!(low_strike <= spot * (-NEAR_BAND_LN).exp());
        assert!(high_strike >= spot * NEAR_BAND_LN.exp());
        // and it is a BAND, not the whole ladder
        assert!(hi - lo < 40, "span {lo}..{hi} is wider than the +/-1.5% band");
    }

    /// Guards the ordering fix: with the spot between two listed strikes the
    /// nearer one must win. Searching `+offset` first unconditionally picked
    /// the farther strike whenever the spot sat below the rounded centre.
    #[test]
    fn atm_retarget_picks_the_nearer_listed_strike() {
        let mut tenor = Tenor::new(19_500);
        let live = Leg {
            bid_u6: 100_000,
            ask_u6: 120_000,
            bid_size: 10,
            ask_size: 10,
            live: true,
        };
        for slot in [704_usize, 708_usize] {
            tenor.strikes[slot].call = live;
            tenor.strikes[slot].put = live;
        }
        retarget_atm(&mut tenor, 176.40);
        assert!(tenor.atm_valid);
        assert_eq!(tenor.atm_slot, 704, "should pick $176.00, not $177.00");
        retarget_atm(&mut tenor, 176.60);
        assert_eq!(tenor.atm_slot, 708, "should pick $177.00, not $176.00");
    }

    /// A one-sided or crossed quote has no midpoint and must not produce one.
    #[test]
    fn one_sided_quotes_have_no_mid_and_no_iv() {
        let mut tenor = Tenor::new(19_500);
        let one_sided = Leg {
            bid_u6: 0,
            ask_u6: 120_000,
            bid_size: 0,
            ask_size: 10,
            live: true,
        };
        assert!(one_sided.mid().is_none());
        assert!(one_sided.spread().is_none());
        tenor.strikes[704].call = one_sided;
        tenor.strikes[704].put = one_sided;
        tenor.atm_slot = 704;
        tenor.atm_valid = true;
        assert!(tenor.atm_quote().is_none());
    }

    /// Absence is never zero: a bar with no samples yields NaN dispersion, not
    /// a fabricated 0.0.
    #[test]
    fn empty_bar_dispersion_is_nan_not_zero() {
        let mut accum = BarAccum::default();
        assert!(accum.iv_sd().is_nan());
        assert!(accum.rs_sd().is_nan());
        accum.observe_iv(0.30);
        assert!(accum.iv_sd().is_nan(), "one sample has no dispersion");
        accum.observe_iv(0.32);
        assert!(accum.iv_sd() > 0.0);
    }
}
