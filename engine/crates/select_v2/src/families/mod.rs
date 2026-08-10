//! The family-emitter contract.
//!
//! A family is a bounded set of columns computed inside ONE streaming pass over
//! a session, evaluated strictly as-of each action's cutoff. Two properties are
//! structural rather than conventional:
//!
//! * **Hard width cap.** [`MAX_FAMILY_COLUMNS`] is checked when a family joins
//!   the pass and again when it emits. A family cannot widen at runtime.
//! * **As-of by construction.** The driver calls [`FamilyEmitter::on_cutoff`]
//!   the instant the tape crosses a cutoff, BEFORE feeding it the event that
//!   crossed it. The family snapshots its own state there. It therefore cannot
//!   observe post-cutoff data even if it wanted to — which is why
//!   [`FamilyEmitter::emit`] takes the cutoff list only to align and check the
//!   rows it already produced, never to compute them.

pub mod session_state;
pub mod a1_clock;
pub mod a2_session_state;
pub mod b1_turn_geometry;
pub mod b2_pivot_micro;
pub mod c1_vol_state;
pub mod c2_trend_path;
pub mod d1_liquidity_cost;
pub mod e1_tape_flow;
pub mod e2_gt_intent;
pub mod e3_raid_sonar;
pub mod h1_quality;

use crate::book::ActionCutoff;
use crate::error::{Result, SelectV2Error};

/// Hard per-family column cap (plan Part III, "enforced in code, not prose").
pub const MAX_FAMILY_COLUMNS: usize = 64;

/// The unit a column is expressed in. Kept typed so a downstream mix-up is a
/// compile-time-visible fact rather than a naming convention.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Unit {
    Bps,
    Dollars,
    Shares,
    Count,
    Ratio,
    Seconds,
    Bars,
    Flag,
    Ordinal,
}

/// How far back from its action's cutoff a column is allowed to see.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum AsOfRule {
    /// Reads only tape strictly before the cutoff instant.
    StrictlyBeforeCutoff,
    /// Reads only strictly-prior sessions (trailing context).
    PriorSessionsOnly,
    /// Derived from the action book's own pre-cutoff summary.
    BookSummaryAtCutoff,
}

/// One emitted column.
#[derive(Clone, Copy, Debug)]
pub struct ColSpec {
    pub name: &'static str,
    pub unit: Unit,
    pub as_of: AsOfRule,
}

impl ColSpec {
    #[must_use]
    pub const fn new(name: &'static str, unit: Unit, as_of: AsOfRule) -> Self {
        Self { name, unit, as_of }
    }
}

/// One NBBO update, frame B.
#[derive(Clone, Copy, Debug)]
pub struct QuoteEvent {
    pub ts_ms_b: i64,
    pub bid_u6: i64,
    pub ask_u6: i64,
    pub bid_shares: i64,
    pub ask_shares: i64,
}

impl QuoteEvent {
    /// True midpoint in u6, computed from the two sides.
    #[must_use]
    pub const fn mid_u6(&self) -> i64 {
        i64::midpoint(self.bid_u6, self.ask_u6)
    }

    /// `ask - bid` in u6.
    #[must_use]
    pub const fn spread_u6(&self) -> i64 {
        self.ask_u6 - self.bid_u6
    }
}

/// One print, frame B. `quote_present` false means the vendor attached no NBBO
/// state to this print — absent, not zero.
#[derive(Clone, Copy, Debug)]
pub struct TradeEvent {
    pub ts_ms_b: i64,
    pub price_u6: i64,
    pub size: i64,
    pub exchange: i64,
    pub condition: i64,
    pub sequence: i64,
    pub bid_u6: i64,
    pub ask_u6: i64,
    pub bid_shares: i64,
    pub ask_shares: i64,
    pub quote_present: bool,
}

/// Rows a family produced: row-major `f32`, `rows x columns`.
#[derive(Clone, Debug, Default)]
pub struct FamilyRows {
    pub columns: usize,
    pub values: Vec<f32>,
}

impl FamilyRows {
    #[must_use]
    pub fn rows(&self) -> usize {
        self.values.len().checked_div(self.columns).unwrap_or(0)
    }
}

/// A per-session feature family.
pub trait FamilyEmitter: Send {
    /// Stable family name; also the output subdirectory.
    fn name(&self) -> &'static str;

    /// The columns this family emits. Must be at most [`MAX_FAMILY_COLUMNS`].
    fn columns(&self) -> &[ColSpec];

    /// Called once per NBBO update, in tape order.
    fn on_quote(&mut self, quote: &QuoteEvent);

    /// Called once per print, in tape order.
    fn on_trade(&mut self, trade: &TradeEvent);

    /// Called the moment the tape crosses `cutoff`, before the crossing event
    /// is delivered. The family appends one row for this action here.
    fn on_cutoff(&mut self, cutoff: &ActionCutoff);

    /// Finalizes the session. `cutoffs` is the same list, in the same order,
    /// the driver announced through [`Self::on_cutoff`].
    ///
    /// # Errors
    ///
    /// [`SelectV2Error::ContentMismatch`] if the family produced a row count or
    /// width that disagrees with what it declared.
    fn emit(&mut self, cutoffs: &[ActionCutoff]) -> Result<FamilyRows>;
}

/// Refuses a family that declares more than the hard cap.
///
/// # Errors
///
/// [`SelectV2Error::FamilyTooWide`].
pub fn check_width(family: &dyn FamilyEmitter) -> Result<()> {
    let columns = family.columns().len();
    if columns > MAX_FAMILY_COLUMNS {
        return Err(SelectV2Error::FamilyTooWide {
            family: family.name(),
            columns,
        });
    }
    Ok(())
}

/// Every family this build can emit.
#[must_use]
pub fn registered_families() -> &'static [&'static str] {
    &[
        session_state::NAME,
        a1_clock::NAME,
        a2_session_state::NAME,
        b1_turn_geometry::NAME,
        b2_pivot_micro::NAME,
        c1_vol_state::NAME,
        c2_trend_path::NAME,
        d1_liquidity_cost::NAME,
        e1_tape_flow::NAME,
        e2_gt_intent::NAME,
        e3_raid_sonar::NAME,
        h1_quality::NAME,
    ]
}

/// Builds a family by name.
///
/// # Errors
///
/// [`SelectV2Error::UnknownFamily`] for a name outside
/// [`registered_families`], or [`SelectV2Error::FamilyTooWide`].
pub fn build(name: &str) -> Result<Box<dyn FamilyEmitter>> {
    let family: Box<dyn FamilyEmitter> = match name {
        session_state::NAME => Box::new(session_state::SessionStateStub::default()),
        a1_clock::NAME => Box::new(a1_clock::A1Clock),
        a2_session_state::NAME => Box::new(a2_session_state::A2SessionState),
        b1_turn_geometry::NAME => Box::new(b1_turn_geometry::B1TurnGeometry::default()),
        b2_pivot_micro::NAME => Box::new(b2_pivot_micro::B2PivotMicro::default()),
        c1_vol_state::NAME => Box::new(c1_vol_state::C1VolState::default()),
        c2_trend_path::NAME => Box::new(c2_trend_path::C2TrendPath),
        d1_liquidity_cost::NAME => Box::new(d1_liquidity_cost::D1LiquidityCost::default()),
        e1_tape_flow::NAME => Box::new(e1_tape_flow::E1TapeFlow),
        e2_gt_intent::NAME => Box::new(e2_gt_intent::E2GtIntent),
        e3_raid_sonar::NAME => Box::new(e3_raid_sonar::E3RaidSonar),
        h1_quality::NAME => Box::new(h1_quality::H1Quality::default()),
        other => return Err(SelectV2Error::UnknownFamily(other.to_owned())),
    };
    check_width(family.as_ref())?;
    Ok(family)
}
