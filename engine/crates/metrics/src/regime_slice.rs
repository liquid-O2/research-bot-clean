//! Regime-sliced capture (design brief §C: "regime-sliced capture (recall x
//! vol-regime tercile x trend/range state x session type from B)"; amendment
//! §A8: "As-of bar for every truth and every hit = the TRUTH PLATEAU bar").
//!
//! This module joins a truth population (with a stream's already-computed
//! [`crate::capture::TruthOutcome`]s) against a per-`(session, bar)` regime
//! population, and cross-tabulates truths/hits over the full
//! `3 (vol tercile) x 3 (trend/range) x 2 (session type)` = 18-cell grid,
//! always publishing every cell -- "Zero-support cells publish `truths=0,
//! hits=0, state=NO_SUPPORT`" (A8).
//!
//! [`RegimeBar`] preserves each underlying regime quantity's OWN typed
//! `OK`/`OVERFLOW`/`NO_DATA`/`INSUFFICIENT_HISTORY`/`NO_QUOTE` state,
//! mirroring `labels::regimes::{SumState, WindowStat, BandState,
//! BandResult, NetMoveState, NetMoveResult}` field-for-field and
//! state-for-state (this crate has zero dependency on `labels` by design,
//! see the crate doc -- the wiring layer that builds a `RegimeBar` from a
//! published `RegimeRow` is an EVENTS.4 deliverable, not this crate's). A
//! bare fabricated `i64` (for example `0`) can never stand in for a
//! genuinely absent quantity: every axis a truth's final cell depends on
//! (the vol/RV rate, the band value, the net-move value) is checked for its
//! OWN validity, independently, before that truth is classified. A truth
//! missing any required axis is never silently dropped -- it is excluded
//! from the 18 cells and counted under the SPECIFIC typed reason
//! ([`RegimeUnresolvedCounts`]), never conflated into one opaque bucket.

use crate::capture::{TruthCaptureOutcome, TruthOutcome};
use crate::regime::{
    Tercile, TrendRangeState, classify_tercile, classify_trend_range, compare_rate, tercile_cuts,
};
use crate::session::{SessionId, SessionType};
use crate::truth::TruthRow;
use std::collections::{HashMap, HashSet};

/// `rv_sum_sq_15`'s OK/OVERFLOW state (mirrors `labels::regimes::SumState`
/// exactly).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SumState {
    Ok,
    Overflow,
}

/// `rv_sum_sq_15`/`rv_count_15`'s published pair (mirrors
/// `labels::regimes::WindowStat` exactly): `sum_sq` is `None` iff `state ==
/// Overflow`; `count` is always present (`0` is legitimate, never itself a
/// failure).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct WindowStat {
    pub state: SumState,
    pub sum_sq: Option<i64>,
    pub count: i64,
}

/// `band_u6_30`'s typed state (mirrors `labels::regimes::BandState`
/// exactly).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BandState {
    Ok,
    Overflow,
    /// Zero valid (non-`NO_QUOTE`) bars anywhere in the causal window.
    NoData,
}

/// `band_u6_30`'s published pair (mirrors `labels::regimes::BandResult`
/// exactly).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct BandResult {
    pub state: BandState,
    pub value_u6: Option<i64>,
}

/// `net_move_u6_30`'s typed state (mirrors `labels::regimes::NetMoveState`
/// exactly).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NetMoveState {
    Ok,
    Overflow,
    /// `b < 30`: bar `b - 30` does not exist.
    InsufficientHistory,
    /// Either endpoint bar's `close_u6` is `NO_QUOTE`.
    NoQuote,
}

/// `net_move_u6_30`'s published pair (mirrors
/// `labels::regimes::NetMoveResult` exactly).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NetMoveResult {
    pub state: NetMoveState,
    pub value_u6: Option<i64>,
}

/// One `(session, bar)`'s regime quantities (design brief §B / formula
/// addendum §1): the minimal projection A8's slicing needs -- the
/// realized-variance rate pair, the trailing-30-bar band/net-move pair
/// (each with its OWN typed state, never a bare fabricated number), and
/// this bar's session's type (denormalized per bar for a simple join key).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct RegimeBar {
    pub session: SessionId,
    pub bar_ordinal: u32,
    pub rv_15: WindowStat,
    pub band_u6_30: BandResult,
    pub net_move_u6_30: NetMoveResult,
    pub session_type: SessionType,
}

impl RegimeBar {
    /// `Some((rv_sum_sq_15, rv_count_15))` iff this bar is "count-valid"
    /// (A8) for the vol-rate axis: `state == Ok` (a defined `sum_sq`) AND
    /// `count > 0` (a rate needs at least one valid diff -- an `Ok` sum
    /// over zero diffs is `0`, but still no defined rate). `None`
    /// otherwise -- never a fabricated rate.
    #[must_use]
    pub fn rv_pair(&self) -> Option<(i64, i64)> {
        match self.rv_15.state {
            SumState::Ok if self.rv_15.count > 0 => {
                self.rv_15.sum_sq.map(|sum_sq| (sum_sq, self.rv_15.count))
            }
            _ => None,
        }
    }

    /// `Some(band_u6_30)` iff `state == Ok`. `None` for `NO_DATA` and
    /// `OVERFLOW` alike -- never a fabricated band value.
    #[must_use]
    pub fn band_value(&self) -> Option<i64> {
        match self.band_u6_30.state {
            BandState::Ok => self.band_u6_30.value_u6,
            BandState::Overflow | BandState::NoData => None,
        }
    }

    /// `Some(net_move_u6_30)` iff `state == Ok`. `None` for
    /// `INSUFFICIENT_HISTORY`, `NO_QUOTE`, and `OVERFLOW` alike -- never a
    /// fabricated net-move value.
    #[must_use]
    pub fn net_move_value(&self) -> Option<i64> {
        match self.net_move_u6_30.state {
            NetMoveState::Ok => self.net_move_u6_30.value_u6,
            NetMoveState::Overflow | NetMoveState::InsufficientHistory | NetMoveState::NoQuote => {
                None
            }
        }
    }
}

/// The frozen population tercile cuts (A8), computed once over the full
/// development-distribution population and reused for every truth/hit
/// classification.
#[derive(Clone, Copy, Debug)]
pub struct RegimePopulationCuts {
    vol_rate_lower: (i64, i64),
    vol_rate_upper: (i64, i64),
    band_lower: i64,
    band_upper: i64,
}

impl RegimePopulationCuts {
    /// Builds the cuts from the full regime-bar population (A8: "population
    /// = all 1,003 x per-session bars' `rv_sum_sq_15` (count-valid rows
    /// only)" for the vol-rate axis; the same order-statistic rule applied
    /// to the raw `band_u6_30` population for the COMPRESSED axis). The
    /// two populations are built INDEPENDENTLY, each from that quantity's
    /// OWN valid rows only ([`RegimeBar::rv_pair`] /
    /// [`RegimeBar::band_value`]) -- a bar can be count-valid for one axis
    /// and not the other (for example an overflowed `band_u6_30` never
    /// contributes to the band population, even on a bar whose
    /// `rv_sum_sq_15` is perfectly valid, and vice versa). `None` iff
    /// either population is empty (no valid bar at all for that axis).
    #[must_use]
    pub fn build(population: &[RegimeBar]) -> Option<Self> {
        let vol_population: Vec<(i64, i64)> =
            population.iter().filter_map(RegimeBar::rv_pair).collect();
        let (vol_rate_lower, vol_rate_upper) =
            tercile_cuts(&vol_population, |a, b| compare_rate(a.0, a.1, b.0, b.1))?;

        let band_population: Vec<i64> = population
            .iter()
            .filter_map(RegimeBar::band_value)
            .collect();
        let (band_lower, band_upper) = tercile_cuts(&band_population, i64::cmp)?;

        Some(Self {
            vol_rate_lower,
            vol_rate_upper,
            band_lower,
            band_upper,
        })
    }

    #[must_use]
    fn classify_vol(&self, sum: i64, count: i64) -> Tercile {
        classify_tercile(
            &(sum, count),
            &self.vol_rate_lower,
            &self.vol_rate_upper,
            |a, b| compare_rate(a.0, a.1, b.0, b.1),
        )
    }

    #[must_use]
    fn classify_band(&self, band: i64) -> Tercile {
        classify_tercile(&band, &self.band_lower, &self.band_upper, i64::cmp)
    }
}

/// One regime-slice cell's cross-tab key.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct RegimeSliceKey {
    pub vol_tercile: Tercile,
    pub trend_range: TrendRangeState,
    pub session_type: SessionType,
}

/// One cell of the 18-cell regime-slice grid.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct RegimeSliceCell {
    pub key: RegimeSliceKey,
    pub truths: u64,
    pub hits: u64,
}

impl RegimeSliceCell {
    /// A8: "Zero-support cells publish `truths=0, hits=0,
    /// state=NO_SUPPORT`." Non-empty cells report their `trend_range` axis
    /// wire value.
    #[must_use]
    pub const fn state_wire(&self) -> &'static str {
        if self.truths == 0 {
            "NO_SUPPORT"
        } else {
            self.key.trend_range.wire()
        }
    }
}

/// Why one truth's plateau bar could not be classified into any of the 18
/// [`RegimeSliceCell`]s -- always all four counters published (`0` is
/// legitimate, same "always publish" convention as the 18 cells
/// themselves), never conflated into one opaque total (AGENTS.md "Typed
/// states, never silent drops"). Checked in this fixed precedence per
/// truth (a missing row is checked before any axis; RV before band before
/// net-move, matching each quantity's dependency order into the final
/// cell), so exactly one counter is incremented per unresolved truth --
/// the SPECIFIC axis that was the blocker, never the ones that were
/// already valid.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub struct RegimeUnresolvedCounts {
    /// No regime row at all for this truth's `(session, plateau_bar)` --
    /// missing from `regime_by_session_bar`, or the plateau bar ordinal
    /// does not fit `u32`.
    pub no_regime_row: u64,
    /// A regime row was found, but `rv_sum_sq_15`/`rv_count_15` is not
    /// count-valid ([`RegimeBar::rv_pair`] is `None`).
    pub unresolved_rv: u64,
    /// `rv` was valid but `band_u6_30` is not ([`RegimeBar::band_value`]
    /// is `None`).
    pub unresolved_band: u64,
    /// `rv` and `band` were both valid but `net_move_u6_30` is not
    /// ([`RegimeBar::net_move_value`] is `None`) -- for example every
    /// early-plateau bar before bar 30 (`INSUFFICIENT_HISTORY`).
    pub unresolved_net_move: u64,
}

impl RegimeUnresolvedCounts {
    /// The total count of truths excluded from every cell, across all four
    /// typed reasons.
    #[must_use]
    pub const fn total(&self) -> u64 {
        self.no_regime_row + self.unresolved_rv + self.unresolved_band + self.unresolved_net_move
    }
}

/// [`build_regime_slices`]'s full result: every one of the 18 cells (always
/// published, per A8), plus the SPECIFIC typed reason for every truth that
/// could not be regime-classified at all.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RegimeSliceResult {
    /// Exactly 18 cells: `Tercile::ALL x TrendRangeState::ALL x
    /// SessionType::ALL`, in that nested order.
    pub cells: Vec<RegimeSliceCell>,
    pub unresolved: RegimeUnresolvedCounts,
}

/// Cross-tabulates `truths` (with their stream-specific `truth_outcomes`)
/// over the 18-cell regime-slice grid, as-of each truth's own plateau bar
/// (A8).
///
/// Declared complexity: O(`truths.len()` + `regime_by_session_bar.len()`
/// log(...)) -- the cuts are built once by the caller
/// ([`RegimePopulationCuts::build`], O(n log n) in the regime population
/// size) and reused here; this function itself is one hash lookup per truth
/// plus 18 cell materializations.
#[must_use]
#[allow(clippy::implicit_hasher)]
pub fn build_regime_slices(
    truths: &[TruthRow],
    truth_outcomes: &[TruthOutcome],
    regime_by_session_bar: &HashMap<(SessionId, u32), RegimeBar>,
    cuts: &RegimePopulationCuts,
) -> RegimeSliceResult {
    let hit_episodes: HashSet<[u8; 32]> = truth_outcomes
        .iter()
        .filter(|outcome| matches!(outcome.outcome, TruthCaptureOutcome::Hit { .. }))
        .map(|outcome| outcome.episode_id)
        .collect();

    let mut tallies: HashMap<RegimeSliceKey, (u64, u64)> = HashMap::new();
    let mut unresolved = RegimeUnresolvedCounts::default();

    for truth in truths {
        let regime = u32::try_from(truth.plateau_bar_ordinal)
            .ok()
            .and_then(|bar_ordinal| regime_by_session_bar.get(&(truth.session, bar_ordinal)));
        let Some(regime) = regime else {
            unresolved.no_regime_row += 1;
            continue;
        };

        let Some((rv_sum_sq, rv_count)) = regime.rv_pair() else {
            unresolved.unresolved_rv += 1;
            continue;
        };
        let Some(band_value) = regime.band_value() else {
            unresolved.unresolved_band += 1;
            continue;
        };
        let Some(net_move_value) = regime.net_move_value() else {
            unresolved.unresolved_net_move += 1;
            continue;
        };

        let vol_tercile = cuts.classify_vol(rv_sum_sq, rv_count);
        let band_tercile = cuts.classify_band(band_value);
        let trend_range = classify_trend_range(net_move_value, band_value, band_tercile);
        let key = RegimeSliceKey {
            vol_tercile,
            trend_range,
            session_type: regime.session_type,
        };

        let entry = tallies.entry(key).or_insert((0, 0));
        entry.0 += 1;
        if hit_episodes.contains(&truth.episode_id) {
            entry.1 += 1;
        }
    }

    let mut cells = Vec::with_capacity(18);
    for vol_tercile in Tercile::ALL {
        for trend_range in TrendRangeState::ALL {
            for session_type in SessionType::ALL {
                let key = RegimeSliceKey {
                    vol_tercile,
                    trend_range,
                    session_type,
                };
                let (truths_n, hits_n) = tallies.get(&key).copied().unwrap_or((0, 0));
                cells.push(RegimeSliceCell {
                    key,
                    truths: truths_n,
                    hits: hits_n,
                });
            }
        }
    }

    RegimeSliceResult { cells, unresolved }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::capture::TruthMissReason;
    use crate::truth::Side;

    fn session(ordinal: u32) -> SessionId {
        SessionId {
            year: 2022,
            ordinal,
        }
    }

    fn truth(episode_id: [u8; 32], session: SessionId, plateau_bar: i64) -> TruthRow {
        TruthRow {
            episode_id,
            session,
            anchor_bps: 40,
            continuity_ordinal: 0,
            side: Side::Low,
            price_u6: 1_000_000,
            plateau_last_group_ordinal: 0,
            plateau_bar_ordinal: plateau_bar,
            plateau_last_ns: 0,
            coincident_ambiguities: 0,
        }
    }

    fn hit(episode_id: [u8; 32]) -> TruthOutcome {
        TruthOutcome {
            episode_id,
            outcome: TruthCaptureOutcome::Hit {
                candidate_id: [1; 32],
                delay_bars: 0,
            },
        }
    }

    fn miss(episode_id: [u8; 32]) -> TruthOutcome {
        TruthOutcome {
            episode_id,
            outcome: TruthCaptureOutcome::Miss(TruthMissReason::NoExactRelation),
        }
    }

    /// A fully valid regime bar: `rv`/`band`/`net_move` all `Ok`, matching
    /// the shape every real registered bar at or beyond bar 30 with at
    /// least one valid diff/window has.
    fn regime(
        session: SessionId,
        bar_ordinal: u32,
        rv_sum_sq_15: i64,
        rv_count_15: i64,
        band_u6_30: i64,
        net_move_u6_30: i64,
        session_type: SessionType,
    ) -> RegimeBar {
        RegimeBar {
            session,
            bar_ordinal,
            rv_15: WindowStat {
                state: SumState::Ok,
                sum_sq: Some(rv_sum_sq_15),
                count: rv_count_15,
            },
            band_u6_30: BandResult {
                state: BandState::Ok,
                value_u6: Some(band_u6_30),
            },
            net_move_u6_30: NetMoveResult {
                state: NetMoveState::Ok,
                value_u6: Some(net_move_u6_30),
            },
            session_type,
        }
    }

    #[test]
    fn result_always_has_exactly_eighteen_cells() {
        let cuts =
            RegimePopulationCuts::build(&[regime(session(0), 0, 1, 1, 1, 0, SessionType::Normal)])
                .expect("non-empty population");
        let result = build_regime_slices(&[], &[], &HashMap::new(), &cuts);
        assert_eq!(result.cells.len(), 18);
        // Every cell is zero-support with no data at all.
        assert!(
            result
                .cells
                .iter()
                .all(|cell| cell.truths == 0 && cell.hits == 0)
        );
        assert!(
            result
                .cells
                .iter()
                .all(|cell| cell.state_wire() == "NO_SUPPORT")
        );
        assert_eq!(result.unresolved.total(), 0);
    }

    #[test]
    fn a_truth_is_sliced_by_its_own_plateau_bar_not_by_a_later_bar() {
        let s = session(0);
        // Population: three bars, used to build meaningful tercile cuts.
        let population = vec![
            regime(s, 0, 100, 10, 90, 100, SessionType::Normal), // low vol rate, TREND
            regime(s, 1, 1_000, 10, 60, 5, SessionType::Normal), // mid vol rate, RANGE (small move, mid band)
            regime(s, 2, 10_000, 10, 30, 5, SessionType::Normal), // high vol rate, COMPRESSED (small move, low band)
        ];
        let cuts = RegimePopulationCuts::build(&population).expect("non-empty");

        // The truth's plateau bar is bar 0 (TREND, low vol), even though
        // bar 2 (a *later* bar) has very different quantities -- proves the
        // as-of join uses the plateau bar, not some other bar.
        let t = truth([1; 32], s, 0);
        let outcomes = vec![hit([1; 32])];
        let mut regime_by_bar = HashMap::new();
        for bar in &population {
            regime_by_bar.insert((bar.session, bar.bar_ordinal), *bar);
        }

        let result = build_regime_slices(&[t], &outcomes, &regime_by_bar, &cuts);
        let populated: Vec<&RegimeSliceCell> =
            result.cells.iter().filter(|cell| cell.truths > 0).collect();
        assert_eq!(populated.len(), 1);
        assert_eq!(populated[0].truths, 1);
        assert_eq!(populated[0].hits, 1);
        assert_eq!(populated[0].key.vol_tercile, Tercile::Low);
        assert_eq!(populated[0].key.trend_range, TrendRangeState::Trend);
        assert_eq!(populated[0].key.session_type, SessionType::Normal);
        assert_eq!(result.unresolved.total(), 0);
    }

    #[test]
    fn a_miss_still_counts_toward_the_cells_truths_but_not_its_hits() {
        let s = session(0);
        let population = vec![regime(s, 0, 100, 10, 50, 5, SessionType::Normal)];
        let cuts = RegimePopulationCuts::build(&population).expect("non-empty");
        let t = truth([1; 32], s, 0);
        let outcomes = vec![miss([1; 32])];
        let mut regime_by_bar = HashMap::new();
        regime_by_bar.insert((s, 0), population[0]);

        let result = build_regime_slices(&[t], &outcomes, &regime_by_bar, &cuts);
        let populated: Vec<&RegimeSliceCell> =
            result.cells.iter().filter(|cell| cell.truths > 0).collect();
        assert_eq!(populated.len(), 1);
        assert_eq!(populated[0].truths, 1);
        assert_eq!(populated[0].hits, 0);
    }

    #[test]
    fn truth_with_no_resolvable_regime_row_is_unresolved_not_dropped_silently() {
        let s = session(0);
        let population = vec![regime(s, 0, 100, 10, 50, 5, SessionType::Normal)];
        let cuts = RegimePopulationCuts::build(&population).expect("non-empty");
        // Plateau bar 7 has no entry in regime_by_bar at all.
        let t = truth([1; 32], s, 7);
        let outcomes = vec![hit([1; 32])];
        let regime_by_bar = HashMap::new();

        let result = build_regime_slices(&[t], &outcomes, &regime_by_bar, &cuts);
        assert_eq!(result.unresolved.no_regime_row, 1);
        assert_eq!(result.unresolved.total(), 1);
        assert!(result.cells.iter().all(|cell| cell.truths == 0));
    }

    #[test]
    fn negative_plateau_bar_ordinal_is_unresolved_not_a_panic() {
        let s = session(0);
        let population = vec![regime(s, 0, 100, 10, 50, 5, SessionType::Normal)];
        let cuts = RegimePopulationCuts::build(&population).expect("non-empty");
        let t = truth([1; 32], s, -1);
        let outcomes = vec![hit([1; 32])];
        let mut regime_by_bar = HashMap::new();
        regime_by_bar.insert((s, 0), population[0]);

        let result = build_regime_slices(&[t], &outcomes, &regime_by_bar, &cuts);
        assert_eq!(result.unresolved.no_regime_row, 1);
    }

    // ------------------- typed-state axis gaps (Sol#6 / Opus#F2) -------------------

    #[test]
    fn early_plateau_bar_before_30_has_valid_rv_and_band_but_net_move_is_unresolved_typed_on_the_missing_axis_only()
     {
        let s = session(0);
        // The under-test bar (bar 5, a real early-plateau bar): rv AND band
        // are both perfectly valid, but net_move is INSUFFICIENT_HISTORY
        // (bar < 30) -- exactly the common early-plateau shape both
        // findings called out.
        let early_bar = RegimeBar {
            session: s,
            bar_ordinal: 5,
            rv_15: WindowStat {
                state: SumState::Ok,
                sum_sq: Some(100),
                count: 3,
            },
            band_u6_30: BandResult {
                state: BandState::Ok,
                value_u6: Some(50),
            },
            net_move_u6_30: NetMoveResult {
                state: NetMoveState::InsufficientHistory,
                value_u6: None,
            },
            session_type: SessionType::Normal,
        };
        // A separate, fully-valid population bar to build meaningful cuts
        // from (the under-test bar's own rv/band are ALSO valid, so cuts
        // could be built from it alone, but a second bar makes the cut
        // ranks non-degenerate).
        let population = vec![
            early_bar,
            regime(s, 40, 9_999, 10, 999, 1, SessionType::Normal),
        ];
        let cuts = RegimePopulationCuts::build(&population).expect("non-empty");

        let t = truth([1; 32], s, 5);
        let outcomes = vec![hit([1; 32])];
        let mut regime_by_bar = HashMap::new();
        regime_by_bar.insert((s, 5), early_bar);

        let result = build_regime_slices(&[t], &outcomes, &regime_by_bar, &cuts);

        // Typed on the missing axis ONLY -- never rv, never band (both
        // were valid), never the generic "no regime row" bucket (a row WAS
        // found).
        assert_eq!(result.unresolved.unresolved_net_move, 1);
        assert_eq!(result.unresolved.no_regime_row, 0);
        assert_eq!(result.unresolved.unresolved_rv, 0);
        assert_eq!(result.unresolved.unresolved_band, 0);
        assert_eq!(result.unresolved.total(), 1);
        // Never fabricated into a cell.
        assert!(result.cells.iter().all(|cell| cell.truths == 0));
    }

    #[test]
    fn all_na_bar_is_unresolved_rv_first_never_fabricated_into_any_cell() {
        let s = session(0);
        // A liquidity-desert bar: rv OVERFLOW (no defined sum), band
        // NO_DATA, net_move NO_QUOTE -- every axis is simultaneously
        // invalid. RV is checked first, so this must land under
        // `unresolved_rv`, not band or net_move.
        let all_na_bar = RegimeBar {
            session: s,
            bar_ordinal: 9,
            rv_15: WindowStat {
                state: SumState::Overflow,
                sum_sq: None,
                count: 2,
            },
            band_u6_30: BandResult {
                state: BandState::NoData,
                value_u6: None,
            },
            net_move_u6_30: NetMoveResult {
                state: NetMoveState::NoQuote,
                value_u6: None,
            },
            session_type: SessionType::Normal,
        };
        // Cuts are built from an UNRELATED, fully-valid baseline population
        // (the all-NA bar itself could never contribute valid rows to
        // either population, so it is deliberately excluded from the
        // population passed to `build`).
        let population = vec![regime(s, 0, 100, 10, 50, 5, SessionType::Normal)];
        let cuts = RegimePopulationCuts::build(&population).expect("non-empty");

        let t = truth([1; 32], s, 9);
        let outcomes = vec![hit([1; 32])];
        let mut regime_by_bar = HashMap::new();
        regime_by_bar.insert((s, 9), all_na_bar);

        let result = build_regime_slices(&[t], &outcomes, &regime_by_bar, &cuts);
        assert_eq!(result.unresolved.unresolved_rv, 1);
        assert_eq!(result.unresolved.unresolved_band, 0);
        assert_eq!(result.unresolved.unresolved_net_move, 0);
        assert_eq!(result.unresolved.total(), 1);
        assert!(result.cells.iter().all(|cell| cell.truths == 0));
    }

    #[test]
    fn overflowed_band_bar_is_excluded_from_the_band_tercile_cut_population() {
        let s = session(0);
        // Five bars with distinct, spread-out band values and perfectly
        // valid rv -- enough for non-degenerate tercile cut ranks.
        let baseline: Vec<RegimeBar> = (0..5)
            .map(|i| regime(s, i, 100, 1, 10 * i64::from(i + 1), 1, SessionType::Normal))
            .collect();
        let cuts_without_overflow =
            RegimePopulationCuts::build(&baseline).expect("non-empty baseline");

        // A sixth bar whose band is OVERFLOW (rv still perfectly valid) --
        // if the band population wrongly included it, adding it would
        // change the band tercile cut ranks (n shifts from 5 to 6); if
        // correctly excluded, the band cuts are byte-identical.
        let mut with_overflow = baseline.clone();
        with_overflow.push(RegimeBar {
            session: s,
            bar_ordinal: 5,
            rv_15: WindowStat {
                state: SumState::Ok,
                sum_sq: Some(100),
                count: 1,
            },
            band_u6_30: BandResult {
                state: BandState::Overflow,
                value_u6: None,
            },
            net_move_u6_30: NetMoveResult {
                state: NetMoveState::Ok,
                value_u6: Some(1),
            },
            session_type: SessionType::Normal,
        });
        let cuts_with_overflow =
            RegimePopulationCuts::build(&with_overflow).expect("non-empty with overflow");

        // Same module: private fields are directly visible to this nested
        // test module, so the band cuts (unaffected by rv-population size
        // changes) can be compared directly.
        assert_eq!(
            cuts_without_overflow.band_lower,
            cuts_with_overflow.band_lower
        );
        assert_eq!(
            cuts_without_overflow.band_upper,
            cuts_with_overflow.band_upper
        );
    }
}
