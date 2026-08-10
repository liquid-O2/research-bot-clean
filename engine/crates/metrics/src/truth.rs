//! Truth-row input type (design brief §C / A10: the metrics-facing
//! projection of the preserved truth authority, `truth_coverage.tsv`, CONV
//! §8). Wiring to the real leaf (or A10's new `truth_relation_projection`
//! leaf) happens in the Wiring phase / EVENTS.4; this module only defines
//! the clean typed shape every capture/regime-slicing function consumes.

use crate::session::SessionId;

/// Truth/signal side (CONV §5 `EpisodeExtremeSide`, wire codes `"LOW"` /
/// `"HIGH"`). Duplicated locally (not imported from `labels::anchor::Side`):
/// metrics has zero dependency on the label kernels or `pubread` -- every
/// input arrives as one of this crate's own typed rows, wired in later.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Side {
    Low,
    High,
}

/// One confirmed truth episode (CONV §8: "Only `ConfirmedTurn` episodes are
/// truths"), at one `anchor_bps` authority (`20` or `40`; the gate authority
/// is `40`, A3). Population size at `anchor_bps = 40` is the registered
/// 8,914 (CONV §8).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TruthRow {
    pub episode_id: [u8; 32],
    pub session: SessionId,
    pub anchor_bps: u16,
    /// Exact-match key component 1/3 (CONV §8 rule 1).
    pub continuity_ordinal: u32,
    /// Exact-match key component 2/3.
    pub side: Side,
    /// Exact-match key component 3/3 (`pivot_price_u6` of a matching
    /// signal must equal this).
    pub price_u6: i64,
    /// Raw provenance reference: a **group** ordinal, not a bar ordinal
    /// (`truth_coverage.tsv`'s own column, CONV §8 schema).
    pub plateau_last_group_ordinal: u64,
    /// The plateau's clock resolved to a one-minute bar ordinal (CONV §3;
    /// what CONV §8 rule 5's delay arithmetic and A8's as-of-bar regime join
    /// actually consume). Signed: a plateau very near session start can, in
    /// degenerate constructions, resolve non-positive; kept `i64` to match
    /// `labels::f_prox::EpisodeProjection::plateau_bar_ordinal`'s convention.
    pub plateau_bar_ordinal: i64,
    /// The plateau's native timestamp (CONV §8 rule 3's `plateau_last_ns`;
    /// note the registered asymmetry, CONV §8 closing note: this is the
    /// plateau's NATIVE stamp, while a candidate's own clock is its
    /// group-close `causal_visible_ts_ns`).
    pub plateau_last_ns: i64,
    /// Verbatim `truth_coverage.tsv` `coincident_ambiguities` column
    /// (CONV §8 schema) -- summed, never re-derived, for the pooled
    /// ambiguity count (design brief §C "ambiguity counts").
    pub coincident_ambiguities: u32,
}

/// Sums [`TruthRow::coincident_ambiguities`] over a truth population
/// (design brief §C "ambiguity counts"): a property of the truth population
/// itself, not of any one candidate stream, so it is reported once, pooled,
/// rather than per stream. O(n).
#[must_use]
pub fn pooled_ambiguity_count(truths: &[TruthRow]) -> u64 {
    truths
        .iter()
        .map(|truth| u64::from(truth.coincident_ambiguities))
        .sum()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn truth(coincident_ambiguities: u32) -> TruthRow {
        TruthRow {
            episode_id: [0; 32],
            session: SessionId {
                year: 2022,
                ordinal: 0,
            },
            anchor_bps: 40,
            continuity_ordinal: 0,
            side: Side::Low,
            price_u6: 1_000_000,
            plateau_last_group_ordinal: 0,
            plateau_bar_ordinal: 0,
            plateau_last_ns: 0,
            coincident_ambiguities,
        }
    }

    #[test]
    fn pooled_ambiguity_count_sums_the_verbatim_column() {
        let truths = vec![truth(0), truth(2), truth(1)];
        assert_eq!(pooled_ambiguity_count(&truths), 3);
    }

    #[test]
    fn pooled_ambiguity_count_of_empty_population_is_zero() {
        assert_eq!(pooled_ambiguity_count(&[]), 0);
    }
}
