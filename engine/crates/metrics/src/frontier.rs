//! Frontier non-domination over (recall, burden) (design brief §C:
//! "frontier (recall vs burden, non-dominated set over streams; integer
//! ratio comparisons)").

use crate::session::StreamId;
use std::cmp::Ordering;

/// One candidate stream's pooled gate position, sufficient for frontier and
/// proposal-bank ranking.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StreamPoint {
    pub stream: StreamId,
    pub hits: u64,
    /// Pooled truth denominator (8,914 in production). Carried per point
    /// rather than hardcoded so degenerate/test populations can differ;
    /// production callers must ensure every point being compared shares the
    /// same pooled population.
    pub truths_denominator: u64,
    /// The one frozen burden scalar (design brief §C "FP burden"; A9 "the
    /// one frozen burden scalar"; see
    /// [`crate::capture::CaptureCounts::burden`]).
    pub burden: u64,
    /// Design brief §C: "Ties: earlier stream registration order, never
    /// hash." Caller-assigned (e.g. a frozen catalog's index).
    pub registration_order: u64,
}

/// Exact recall comparison via cross-product (division-free): `a`'s recall
/// (`a.hits / a.truths_denominator`) vs `b`'s recall.
#[must_use]
pub fn compare_recall(a: &StreamPoint, b: &StreamPoint) -> Ordering {
    let left = u128::from(a.hits) * u128::from(b.truths_denominator);
    let right = u128::from(b.hits) * u128::from(a.truths_denominator);
    left.cmp(&right)
}

/// `true` iff `a` dominates `b`: `a`'s recall >= `b`'s AND `a`'s burden <=
/// `b`'s, with at least one strict (standard Pareto dominance over
/// (recall maximized, burden minimized)).
#[must_use]
pub fn dominates(a: &StreamPoint, b: &StreamPoint) -> bool {
    let recall_cmp = compare_recall(a, b);
    let recall_at_least = recall_cmp != Ordering::Less;
    let burden_at_most = a.burden <= b.burden;
    let strictly_better = recall_cmp == Ordering::Greater || a.burden < b.burden;
    recall_at_least && burden_at_most && strictly_better
}

/// The non-dominated subset of `points` (design brief §C "frontier ...
/// non-dominated set over streams"), preserving `points`' own relative
/// order.
///
/// Declared complexity: O(n²) (every point tested against every other) --
/// the registered stream catalog is small (single/low-double-digit
/// candidate count), so a faster skyline algorithm is not warranted.
#[must_use]
pub fn non_dominated(points: &[StreamPoint]) -> Vec<StreamPoint> {
    points
        .iter()
        .enumerate()
        .filter(|(index, candidate)| {
            !points
                .iter()
                .enumerate()
                .any(|(other_index, other)| other_index != *index && dominates(other, candidate))
        })
        .map(|(_, candidate)| candidate.clone())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn point(
        name: &str,
        hits: u64,
        truths_denominator: u64,
        burden: u64,
        order: u64,
    ) -> StreamPoint {
        StreamPoint {
            stream: StreamId::new(name, 40),
            hits,
            truths_denominator,
            burden,
            registration_order: order,
        }
    }

    #[test]
    fn compare_recall_handles_differing_denominators_via_cross_product() {
        // 90/100 (0.90) vs 45/50 (0.90): equal.
        let a = point("a", 90, 100, 0, 0);
        let b = point("b", 45, 50, 0, 1);
        assert_eq!(compare_recall(&a, &b), Ordering::Equal);
    }

    #[test]
    fn a_strictly_better_stream_dominates_a_strictly_worse_one() {
        let a = point("a", 90, 100, 10, 0); // recall .90, burden 10
        let b = point("b", 80, 100, 20, 1); // recall .80, burden 20
        assert!(dominates(&a, &b));
        assert!(!dominates(&b, &a));
    }

    #[test]
    fn a_recall_burden_tradeoff_is_non_dominated_either_way() {
        let a = point("a", 90, 100, 20, 0); // higher recall, higher burden
        let b = point("b", 80, 100, 10, 1); // lower recall, lower burden
        assert!(!dominates(&a, &b));
        assert!(!dominates(&b, &a));
    }

    #[test]
    fn identical_points_do_not_dominate_each_other() {
        let a = point("a", 90, 100, 10, 0);
        let b = point("b", 90, 100, 10, 1);
        assert!(!dominates(&a, &b));
        assert!(!dominates(&b, &a));
    }

    #[test]
    fn non_dominated_excludes_only_the_strictly_worse_point() {
        let a = point("a", 90, 100, 10, 0);
        let b = point("b", 80, 100, 20, 1); // dominated by a
        let c = point("c", 70, 100, 5, 2); // tradeoff vs a: lower recall, lower burden
        let frontier = non_dominated(&[a.clone(), b, c.clone()]);
        assert_eq!(frontier, vec![a, c]);
    }

    #[test]
    fn ties_are_all_kept_on_the_frontier() {
        let a = point("a", 90, 100, 10, 0);
        let b = point("b", 90, 100, 10, 1);
        let frontier = non_dominated(&[a.clone(), b.clone()]);
        assert_eq!(frontier, vec![a, b]);
    }
}
