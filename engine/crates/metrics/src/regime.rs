//! Regime-population tercile computation (amendment §A8): the order-
//! statistic cut rule shared by the vol-regime axis (the rate `rv_sum_sq_15
//! / rv_count_15`) and the COMPRESSED band axis (raw `band_u6_30`), plus the
//! exact TREND/COMPRESSED/RANGE predicate.
//!
//! "Tercile rule: population = all 1,003 x per-session bars' `rv_sum_sq_15`
//! (count-valid rows only), order-statistic cuts at ranks `floor(n/3)` and
//! `floor(2n/3)` (1-based, ties: lower rank wins -- values equal to a cut go
//! to the lower tercile), integer comparisons on cross-products `rv_sum_sq ·
//! count'` vs `rv_sum_sq' · count`. ... Trend/range/compression predicates
//! (exact, on the plateau bar's trailing 30-bar quantities): `TREND` iff
//! `4·|net_move| ≥ 3·band`, `COMPRESSED` iff the bar's `band` is in the
//! bottom development-distribution tercile (same order-statistic rule on
//! band), else `RANGE` (TREND wins over COMPRESSED when both hold)."

use std::cmp::Ordering;

/// Three-way tercile membership.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Tercile {
    Low,
    Mid,
    High,
}

impl Tercile {
    /// All three terciles (cross-product-building convenience).
    pub const ALL: [Self; 3] = [Self::Low, Self::Mid, Self::High];

    #[must_use]
    pub const fn wire(self) -> &'static str {
        match self {
            Self::Low => "LOW",
            Self::Mid => "MID",
            Self::High => "HIGH",
        }
    }
}

/// Computes A8's two order-statistic cut elements: the 1-based-rank
/// `floor(n/3)`-th and `floor(2n/3)`-th smallest elements of `population`
/// under `compare`. Returned **by value** (not by rank index) so a caller
/// can classify any later value against them via [`classify_tercile`]
/// without re-sorting or retaining the population. `None` iff `population`
/// is empty.
///
/// For `n < 3` (`floor(n/3) == 0`, no 1-based rank-1 element exists), both
/// cuts pin to the population's smallest element -- an implementation
/// default for a degenerate case the amendment does not itself specify
/// (real populations are ~391,170 bars; this only matters in tests).
///
/// Declared complexity: O(n log n) (one sort of a population copy).
#[must_use]
pub fn tercile_cuts<T: Copy>(
    population: &[T],
    mut compare: impl FnMut(&T, &T) -> Ordering,
) -> Option<(T, T)> {
    if population.is_empty() {
        return None;
    }
    let mut sorted: Vec<T> = population.to_vec();
    sorted.sort_by(&mut compare);
    let n = sorted.len();
    let lower_rank = n / 3;
    let upper_rank = (2 * n) / 3;
    let lower_index = lower_rank.saturating_sub(1);
    let upper_index = upper_rank.saturating_sub(1);
    Some((sorted[lower_index], sorted[upper_index]))
}

/// Classifies `value` against the two cuts from [`tercile_cuts`]. A8's tie
/// rule: "ties: lower rank wins -- values equal to a cut go to the lower
/// tercile" -- so `value` equal to `lower_cut` is [`Tercile::Low`], and
/// `value` equal to `upper_cut` is [`Tercile::Mid`] (the lower side of
/// *that* cut).
#[must_use]
pub fn classify_tercile<T>(
    value: &T,
    lower_cut: &T,
    upper_cut: &T,
    mut compare: impl FnMut(&T, &T) -> Ordering,
) -> Tercile {
    if compare(value, lower_cut) != Ordering::Greater {
        Tercile::Low
    } else if compare(value, upper_cut) != Ordering::Greater {
        Tercile::Mid
    } else {
        Tercile::High
    }
}

/// Compares two realized-variance rate pairs `(sum, count)` as `sum_a /
/// count_a` vs `sum_b / count_b`, division-free (A8: "integer comparisons
/// on cross-products"). Both counts must be strictly positive -- a
/// "count-valid" population (A8) never contains a non-positive-count row;
/// callers filter `rv_count_15 > 0` before building the population.
///
/// # Panics
///
/// Panics if either `count` is not strictly positive.
#[must_use]
pub fn compare_rate(sum_a: i64, count_a: i64, sum_b: i64, count_b: i64) -> Ordering {
    assert!(
        count_a > 0 && count_b > 0,
        "compare_rate requires count-valid (count > 0) rows"
    );
    let left = i128::from(sum_a) * i128::from(count_b);
    let right = i128::from(sum_b) * i128::from(count_a);
    left.cmp(&right)
}

/// A8's `TREND` / `COMPRESSED` / `RANGE` state.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum TrendRangeState {
    Trend,
    Compressed,
    Range,
}

impl TrendRangeState {
    /// All three states (cross-product-building convenience).
    pub const ALL: [Self; 3] = [Self::Trend, Self::Compressed, Self::Range];

    #[must_use]
    pub const fn wire(self) -> &'static str {
        match self {
            Self::Trend => "TREND",
            Self::Compressed => "COMPRESSED",
            Self::Range => "RANGE",
        }
    }
}

/// A8's exact trend/range/compression predicate on one bar's trailing
/// 30-bar quantities: `TREND` iff `4·|net_move| ≥ 3·band` (wins over
/// COMPRESSED when both hold); else `COMPRESSED` iff `band_tercile` is
/// [`Tercile::Low`] (the bottom development-distribution tercile of
/// `band_u6_30`, from [`tercile_cuts`]/[`classify_tercile`] over the raw
/// `band_u6_30` population); else `RANGE`.
#[must_use]
pub fn classify_trend_range(
    net_move_u6_30: i64,
    band_u6_30: i64,
    band_tercile: Tercile,
) -> TrendRangeState {
    let trend =
        i128::from(4) * i128::from(net_move_u6_30).abs() >= i128::from(3) * i128::from(band_u6_30);
    if trend {
        TrendRangeState::Trend
    } else if matches!(band_tercile, Tercile::Low) {
        TrendRangeState::Compressed
    } else {
        TrendRangeState::Range
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ------------------------- tercile cuts + ties -------------------------

    #[test]
    fn tercile_cuts_pick_the_exact_registered_order_statistic_ranks() {
        // n = 9: floor(9/3) = 3 (3rd smallest, 0-based index 2), floor(18/3)
        // = 6 (6th smallest, 0-based index 5).
        let population = [5_i64, 1, 3, 2, 4, 9, 8, 7, 6];
        let (lower, upper) = tercile_cuts(&population, i64::cmp).expect("non-empty");
        assert_eq!(lower, 3); // sorted: 1,2,3,4,5,6,7,8,9 -> index 2 = 3
        assert_eq!(upper, 6); // index 5 = 6
    }

    #[test]
    fn ties_at_a_cut_value_resolve_to_the_lower_tercile() {
        // sorted population: 1,2,2,2,5,5,5,8,9 (n=9) -> lower cut = index2 =
        // 2, upper cut = index5 = 5 (a real gap between the two cuts, so a
        // genuinely-between value like 3 can be checked too).
        let population = [5_i64, 2, 9, 2, 5, 1, 2, 8, 5];
        let (lower, upper) = tercile_cuts(&population, i64::cmp).expect("non-empty");
        assert_eq!(lower, 2);
        assert_eq!(upper, 5);

        // A value EQUAL to the lower cut goes to Low (not Mid).
        assert_eq!(
            classify_tercile(&2_i64, &lower, &upper, i64::cmp),
            Tercile::Low
        );
        // A value EQUAL to the upper cut goes to Mid (the lower side of
        // *that* cut), not High.
        assert_eq!(
            classify_tercile(&5_i64, &lower, &upper, i64::cmp),
            Tercile::Mid
        );
        // Strictly below the lower cut: Low.
        assert_eq!(
            classify_tercile(&1_i64, &lower, &upper, i64::cmp),
            Tercile::Low
        );
        // Strictly above the upper cut: High.
        assert_eq!(
            classify_tercile(&9_i64, &lower, &upper, i64::cmp),
            Tercile::High
        );
        // Strictly between the two cuts: Mid.
        assert_eq!(
            classify_tercile(&3_i64, &lower, &upper, i64::cmp),
            Tercile::Mid
        );
    }

    #[test]
    fn tercile_cuts_of_empty_population_is_none() {
        let population: [i64; 0] = [];
        assert_eq!(tercile_cuts(&population, i64::cmp), None);
    }

    // ------------------------- rate comparison -------------------------

    #[test]
    fn compare_rate_orders_by_the_ratio_without_dividing() {
        // 3/10 (0.3) vs 4/20 (0.2): a is bigger.
        assert_eq!(compare_rate(3, 10, 4, 20), Ordering::Greater);
        // Equal rates via different (sum, count) pairs: 2/4 == 1/2.
        assert_eq!(compare_rate(2, 4, 1, 2), Ordering::Equal);
        assert_eq!(compare_rate(1, 2, 2, 4), Ordering::Equal);
    }

    #[test]
    #[should_panic(expected = "count-valid")]
    fn compare_rate_panics_on_a_non_positive_count() {
        let _ = compare_rate(1, 0, 1, 1);
    }

    // ------------------------- trend/range/compression -------------------------

    #[test]
    fn trend_wins_when_the_move_is_large_even_if_band_is_compressed() {
        // 4*|net_move| = 4*30 = 120 >= 3*band = 3*30 = 90 -> TREND, even
        // though band_tercile is Low (would otherwise be COMPRESSED).
        let state = classify_trend_range(30, 30, Tercile::Low);
        assert_eq!(state, TrendRangeState::Trend);
    }

    #[test]
    fn compressed_when_not_trend_and_band_is_in_the_bottom_tercile() {
        // 4*|net_move| = 4*1 = 4 < 3*band = 3*100 = 300 -> not TREND.
        let state = classify_trend_range(1, 100, Tercile::Low);
        assert_eq!(state, TrendRangeState::Compressed);
    }

    #[test]
    fn range_when_not_trend_and_band_is_not_in_the_bottom_tercile() {
        let state = classify_trend_range(1, 100, Tercile::Mid);
        assert_eq!(state, TrendRangeState::Range);
        let state_high = classify_trend_range(1, 100, Tercile::High);
        assert_eq!(state_high, TrendRangeState::Range);
    }

    #[test]
    fn trend_boundary_is_inclusive() {
        // 4*|net_move| == 3*band exactly -> TREND (>=, not >).
        let state = classify_trend_range(3, 4, Tercile::Mid);
        assert_eq!(state, TrendRangeState::Trend);
    }
}
