//! `session_state_stub` — the 4-column demo family.
//!
//! Not a Part V family: it is the smallest emitter that exercises every hook
//! (quote, trade, cutoff, emit) with values a probe can check by hand, so the
//! session pass can be verified before any real family is written. Its columns
//! are exactly the state a leakage harness would perturb, which makes an
//! as-of violation visible as a changed number rather than a silent one.

use super::{AsOfRule, ColSpec, FamilyEmitter, FamilyRows, QuoteEvent, TradeEvent, Unit};
use crate::book::ActionCutoff;
use crate::error::{Result, SelectV2Error};

/// Registered name.
pub const NAME: &str = "session_state_stub";

const COLUMNS: [ColSpec; 4] = [
    ColSpec::new(
        "minute_of_session",
        Unit::Bars,
        AsOfRule::StrictlyBeforeCutoff,
    ),
    ColSpec::new("quotes_so_far", Unit::Count, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new("trades_so_far", Unit::Count, AsOfRule::StrictlyBeforeCutoff),
    ColSpec::new(
        "mid_at_cutoff_dollars",
        Unit::Dollars,
        AsOfRule::StrictlyBeforeCutoff,
    ),
];

/// Counts what it has been shown and snapshots at each cutoff.
#[derive(Debug, Default)]
pub struct SessionStateStub {
    quotes: u64,
    trades: u64,
    last_mid_u6: Option<i64>,
    rows: Vec<f32>,
}

impl FamilyEmitter for SessionStateStub {
    fn name(&self) -> &'static str {
        NAME
    }

    fn columns(&self) -> &[ColSpec] {
        &COLUMNS
    }

    fn on_quote(&mut self, quote: &QuoteEvent) {
        self.quotes += 1;
        self.last_mid_u6 = Some(quote.mid_u6());
    }

    fn on_trade(&mut self, _trade: &TradeEvent) {
        self.trades += 1;
    }

    fn on_cutoff(&mut self, cutoff: &ActionCutoff) {
        self.rows.push(as_f32(i64::from(cutoff.cutoff_bar_ordinal)));
        // Counts are exact well past 2^24 in u64; the f32 image saturates in
        // precision above ~16.8M, which is why the census reports the exact
        // u64 alongside. Documented, not hidden.
        self.rows.push(as_f32_u64(self.quotes));
        self.rows.push(as_f32_u64(self.trades));
        self.rows
            .push(self.last_mid_u6.map_or(f32::NAN, u6_to_f32));
    }

    fn emit(&mut self, cutoffs: &[ActionCutoff]) -> Result<FamilyRows> {
        let expected = cutoffs.len() * COLUMNS.len();
        if self.rows.len() != expected {
            return Err(SelectV2Error::ContentMismatch {
                path: std::path::PathBuf::from(NAME),
                detail: format!(
                    "produced {} values for {} cutoffs x {} columns",
                    self.rows.len(),
                    cutoffs.len(),
                    COLUMNS.len()
                ),
            });
        }
        Ok(FamilyRows {
            columns: COLUMNS.len(),
            values: std::mem::take(&mut self.rows),
        })
    }
}

/// u6 fixed point to dollars. The narrowing is the declared output type.
#[allow(clippy::cast_possible_truncation, clippy::cast_precision_loss)]
#[must_use]
pub fn u6_to_f32(value: i64) -> f32 {
    (value as f64 / 1_000_000.0) as f32
}

#[allow(clippy::cast_precision_loss, clippy::cast_possible_truncation)]
fn as_f32(value: i64) -> f32 {
    value as f32
}

#[allow(clippy::cast_precision_loss)]
fn as_f32_u64(value: u64) -> f32 {
    value as f32
}
