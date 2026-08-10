//! Segment tree over per-group `(hi, lo)` price pairs, giving O(log n) range
//! extrema and O(log n) leftmost-threshold-crossing descent queries.
//!
//! Design authority: `docs/specs/label_kernel_design_v1.md` §"Query
//! structures". Build is O(n) time and O(n) memory; every query below is
//! O(log n) by construction (recursive descent over a binary tree of depth
//! `ceil(log2(n))` — never an O(window) scan).

/// Result of a [`ExtremaTree::range_max`] query: the maximum `hi` value over
/// the queried range and the leftmost (smallest) group index attaining it.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RangeMax {
    pub value: i64,
    pub first_index: usize,
}

/// Result of a [`ExtremaTree::range_min`] query: the minimum `lo` value over
/// the queried range and the leftmost (smallest) group index attaining it.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RangeMin {
    pub value: i64,
    pub first_index: usize,
}

/// One node's cached extreme: the value plus the leftmost index (within the
/// node's subtree) attaining it. `None` is the identity element (empty
/// range), used only transiently during queries — every stored tree node
/// covers a nonempty range and is always `Some`.
type Extreme = Option<(i64, usize)>;

/// Segment tree over per-group `(max_hi, min_lo)` price pairs.
///
/// Build O(n); all queries O(log n). Indices are group indices `[0, n)`.
/// Two independent binary trees (max over `hi`, min over `lo`) are stored as
/// flat, 1-indexed arrays of size `4 * n` (the standard recursive
/// segment-tree bound) — no unsafe, no explicit recursion-depth risk beyond
/// `ceil(log2(n))`, which is at most ~25 for the largest sessions this
/// crate targets (n up to 30,000,000).
pub struct ExtremaTree {
    n: usize,
    max_val: Vec<i64>,
    max_idx: Vec<usize>,
    min_val: Vec<i64>,
    min_idx: Vec<usize>,
}

/// Picks the larger value, ties resolved to the leftmost (smaller) index.
/// `a` is always the result of the left-subtree recursive call and `b` the
/// right-subtree call, so an `a`-vs-`b` value tie correctly prefers `a`
/// (the smaller original index range) without needing to compare indices.
fn merge_max(a: Extreme, b: Extreme) -> Extreme {
    match (a, b) {
        (None, None) => None,
        (Some(x), None) => Some(x),
        (None, Some(y)) => Some(y),
        (Some(x), Some(y)) => Some(if x.0 >= y.0 { x } else { y }),
    }
}

/// Picks the smaller value, ties resolved to the leftmost index (see
/// [`merge_max`] for why comparing only values suffices).
fn merge_min(a: Extreme, b: Extreme) -> Extreme {
    match (a, b) {
        (None, None) => None,
        (Some(x), None) => Some(x),
        (None, Some(y)) => Some(y),
        (Some(x), Some(y)) => Some(if x.0 <= y.0 { x } else { y }),
    }
}

fn build_max(node: usize, lo: usize, hi: usize, data: &[i64], val: &mut [i64], idx: &mut [usize]) {
    if lo == hi {
        val[node] = data[lo];
        idx[node] = lo;
        return;
    }
    let mid = lo + (hi - lo) / 2;
    build_max(2 * node, lo, mid, data, val, idx);
    build_max(2 * node + 1, mid + 1, hi, data, val, idx);
    if val[2 * node] >= val[2 * node + 1] {
        val[node] = val[2 * node];
        idx[node] = idx[2 * node];
    } else {
        val[node] = val[2 * node + 1];
        idx[node] = idx[2 * node + 1];
    }
}

fn build_min(node: usize, lo: usize, hi: usize, data: &[i64], val: &mut [i64], idx: &mut [usize]) {
    if lo == hi {
        val[node] = data[lo];
        idx[node] = lo;
        return;
    }
    let mid = lo + (hi - lo) / 2;
    build_min(2 * node, lo, mid, data, val, idx);
    build_min(2 * node + 1, mid + 1, hi, data, val, idx);
    if val[2 * node] <= val[2 * node + 1] {
        val[node] = val[2 * node];
        idx[node] = idx[2 * node];
    } else {
        val[node] = val[2 * node + 1];
        idx[node] = idx[2 * node + 1];
    }
}

fn query_max(
    node: usize,
    lo: usize,
    hi: usize,
    a: usize,
    b: usize,
    val: &[i64],
    idx: &[usize],
) -> Extreme {
    if b < lo || hi < a {
        return None;
    }
    if a <= lo && hi <= b {
        return Some((val[node], idx[node]));
    }
    let mid = lo + (hi - lo) / 2;
    let left = query_max(2 * node, lo, mid, a, b, val, idx);
    let right = query_max(2 * node + 1, mid + 1, hi, a, b, val, idx);
    merge_max(left, right)
}

fn query_min(
    node: usize,
    lo: usize,
    hi: usize,
    a: usize,
    b: usize,
    val: &[i64],
    idx: &[usize],
) -> Extreme {
    if b < lo || hi < a {
        return None;
    }
    if a <= lo && hi <= b {
        return Some((val[node], idx[node]));
    }
    let mid = lo + (hi - lo) / 2;
    let left = query_min(2 * node, lo, mid, a, b, val, idx);
    let right = query_min(2 * node + 1, mid + 1, hi, a, b, val, idx);
    merge_min(left, right)
}

/// Descends for the leftmost leaf index `g` in `[a, hi]` (subtree range
/// `[lo, hi]`) with `val[g] >= threshold`, using the node's cached max to
/// prune whole subtrees. Left child is always tried before right, so the
/// first `Some` found while unwinding is the leftmost match.
fn first_ge(
    node: usize,
    lo: usize,
    hi: usize,
    a: usize,
    threshold: i64,
    val: &[i64],
    idx: &[usize],
) -> Option<usize> {
    if hi < a || val[node] < threshold {
        return None;
    }
    if lo == hi {
        return Some(idx[node]);
    }
    let mid = lo + (hi - lo) / 2;
    first_ge(2 * node, lo, mid, a, threshold, val, idx)
        .or_else(|| first_ge(2 * node + 1, mid + 1, hi, a, threshold, val, idx))
}

/// Symmetric to [`first_ge`]: leftmost leaf with `val[g] <= threshold`.
fn first_le(
    node: usize,
    lo: usize,
    hi: usize,
    a: usize,
    threshold: i64,
    val: &[i64],
    idx: &[usize],
) -> Option<usize> {
    if hi < a || val[node] > threshold {
        return None;
    }
    if lo == hi {
        return Some(idx[node]);
    }
    let mid = lo + (hi - lo) / 2;
    first_le(2 * node, lo, mid, a, threshold, val, idx)
        .or_else(|| first_le(2 * node + 1, mid + 1, hi, a, threshold, val, idx))
}

impl ExtremaTree {
    /// Builds from parallel slices `hi[g]`, `lo[g]` (`hi[g] >= lo[g]` is not
    /// assumed; both are stored and queried independently).
    ///
    /// # Panics
    ///
    /// Panics if `hi.len() != lo.len()` or if both are empty.
    #[must_use]
    pub fn build(hi: &[i64], lo: &[i64]) -> Self {
        assert_eq!(
            hi.len(),
            lo.len(),
            "hi and lo slices must have equal length"
        );
        let n = hi.len();
        assert!(n > 0, "ExtremaTree requires at least one group");

        let size = 4 * n;
        let mut max_val = vec![i64::MIN; size];
        let mut max_idx = vec![0usize; size];
        let mut min_val = vec![i64::MAX; size];
        let mut min_idx = vec![0usize; size];
        build_max(1, 0, n - 1, hi, &mut max_val, &mut max_idx);
        build_min(1, 0, n - 1, lo, &mut min_val, &mut min_idx);

        Self {
            n,
            max_val,
            max_idx,
            min_val,
            min_idx,
        }
    }

    /// Number of groups this tree was built over.
    #[must_use]
    pub fn len(&self) -> usize {
        self.n
    }

    /// Always `false`: [`Self::build`] panics on an empty input, so a live
    /// `ExtremaTree` always has at least one group. Included for clippy's
    /// `len_without_is_empty`.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        false
    }

    /// Max of `hi` over inclusive range `[a, b]`; leftmost attaining index.
    ///
    /// # Panics
    ///
    /// Panics if `a > b` or `b >= len()`.
    #[must_use]
    pub fn range_max(&self, a: usize, b: usize) -> RangeMax {
        assert!(
            a <= b && b < self.n,
            "range_max: invalid range [{a}, {b}] for n = {}",
            self.n
        );
        let (value, first_index) = query_max(1, 0, self.n - 1, a, b, &self.max_val, &self.max_idx)
            .expect("nonempty range always yields a result");
        RangeMax { value, first_index }
    }

    /// Min of `lo` over inclusive range `[a, b]`; leftmost attaining index.
    ///
    /// # Panics
    ///
    /// Panics if `a > b` or `b >= len()`.
    #[must_use]
    pub fn range_min(&self, a: usize, b: usize) -> RangeMin {
        assert!(
            a <= b && b < self.n,
            "range_min: invalid range [{a}, {b}] for n = {}",
            self.n
        );
        let (value, first_index) = query_min(1, 0, self.n - 1, a, b, &self.min_val, &self.min_idx)
            .expect("nonempty range always yields a result");
        RangeMin { value, first_index }
    }

    /// Leftmost index `g` in `[a, n)` with `hi[g] >= threshold`; `None` if
    /// none. O(log n) by tree descent — never a scan.
    #[must_use]
    pub fn first_at_or_above(&self, a: usize, threshold: i64) -> Option<usize> {
        first_ge(1, 0, self.n - 1, a, threshold, &self.max_val, &self.max_idx)
    }

    /// Leftmost index `g` in `[a, n)` with `lo[g] <= threshold`; `None` if
    /// none. O(log n) by tree descent — never a scan.
    #[must_use]
    pub fn first_at_or_below(&self, a: usize, threshold: i64) -> Option<usize> {
        first_le(1, 0, self.n - 1, a, threshold, &self.min_val, &self.min_idx)
    }
}

#[cfg(test)]
#[allow(
    clippy::cast_possible_truncation,
    clippy::cast_possible_wrap,
    reason = "test-only LCG driving small, hand-bounded array lengths/values"
)]
mod tests {
    use super::*;

    /// Minimal 3-line linear congruential generator (numerical recipes
    /// constants), used only to make the property test's random arrays and
    /// queries deterministic and reproducible without a `rand` dependency.
    struct Lcg(u64);
    impl Lcg {
        fn next_u64(&mut self) -> u64 {
            self.0 = self
                .0
                .wrapping_mul(6_364_136_223_846_793_005)
                .wrapping_add(1_442_695_040_888_963_407);
            self.0
        }
        /// Uniform value in `[0, bound)`.
        fn next_below(&mut self, bound: u64) -> u64 {
            self.next_u64() % bound
        }
    }

    // ---- hand-written case with known answers, including duplicate extremes ----

    #[test]
    fn hand_written_known_answers() {
        // groups:      0   1   2   3   4   5   6
        let hi = vec![10, 20, 20, 5, 20, 15, 8];
        let lo = vec![9, 18, 3, 3, 12, 1, 1];
        let tree = ExtremaTree::build(&hi, &lo);

        assert_eq!(tree.len(), 7);
        assert!(!tree.is_empty());

        // Full range: max hi = 20, first at index 1 (leftmost of the tie 1,2,4).
        let m = tree.range_max(0, 6);
        assert_eq!(m.value, 20);
        assert_eq!(m.first_index, 1);

        // Restrict away from index 1: leftmost tie becomes index 2.
        let m2 = tree.range_max(2, 6);
        assert_eq!(m2.value, 20);
        assert_eq!(m2.first_index, 2);

        // Single-element range.
        let m3 = tree.range_max(3, 3);
        assert_eq!(m3.value, 5);
        assert_eq!(m3.first_index, 3);

        // Full range min: lo has a tie of 1 at indices 5 and 6; leftmost is 5.
        let mn = tree.range_min(0, 6);
        assert_eq!(mn.value, 1);
        assert_eq!(mn.first_index, 5);

        // Restrict to [6,6]: only index 6 available.
        let mn2 = tree.range_min(6, 6);
        assert_eq!(mn2.value, 1);
        assert_eq!(mn2.first_index, 6);

        // Threshold descent, exact match at a tie: leftmost hi >= 20 from 0 is index 1.
        assert_eq!(tree.first_at_or_above(0, 20), Some(1));
        // From index 2 onward, leftmost hi >= 20 is index 2.
        assert_eq!(tree.first_at_or_above(2, 20), Some(2));
        // Above all values: none.
        assert_eq!(tree.first_at_or_above(0, 21), None);
        // Below (or at) all values: first index in range.
        assert_eq!(tree.first_at_or_above(0, i64::MIN), Some(0));

        // Leftmost lo <= 1 from 0 is index 5.
        assert_eq!(tree.first_at_or_below(0, 1), Some(5));
        // From 6, only index 6 remains.
        assert_eq!(tree.first_at_or_below(6, 1), Some(6));
        // Below all values: none.
        assert_eq!(tree.first_at_or_below(0, 0), None);
        // Above all values: first index in range.
        assert_eq!(tree.first_at_or_below(0, i64::MAX), Some(0));
        // a = n - 1 (last index only).
        assert_eq!(tree.first_at_or_below(6, i64::MAX), Some(6));
    }

    #[test]
    #[should_panic(expected = "equal length")]
    fn build_panics_on_mismatched_lengths() {
        let _ = ExtremaTree::build(&[1, 2], &[1]);
    }

    #[test]
    #[should_panic(expected = "at least one group")]
    fn build_panics_on_empty() {
        let _ = ExtremaTree::build(&[], &[]);
    }

    #[test]
    #[should_panic(expected = "invalid range")]
    fn range_max_panics_on_inverted_range() {
        let tree = ExtremaTree::build(&[1, 2, 3], &[0, 1, 2]);
        let _ = tree.range_max(2, 1);
    }

    #[test]
    #[should_panic(expected = "invalid range")]
    fn range_max_panics_on_out_of_bounds() {
        let tree = ExtremaTree::build(&[1, 2, 3], &[0, 1, 2]);
        let _ = tree.range_max(0, 3);
    }

    // ---------------------- brute-force property test ----------------------

    fn brute_range_max(hi: &[i64], a: usize, b: usize) -> RangeMax {
        let mut best = hi[a];
        let mut best_idx = a;
        for (g, &v) in hi.iter().enumerate().take(b + 1).skip(a + 1) {
            if v > best {
                best = v;
                best_idx = g;
            }
        }
        RangeMax {
            value: best,
            first_index: best_idx,
        }
    }

    fn brute_range_min(lo: &[i64], a: usize, b: usize) -> RangeMin {
        let mut best = lo[a];
        let mut best_idx = a;
        for (g, &v) in lo.iter().enumerate().take(b + 1).skip(a + 1) {
            if v < best {
                best = v;
                best_idx = g;
            }
        }
        RangeMin {
            value: best,
            first_index: best_idx,
        }
    }

    fn brute_first_ge(hi: &[i64], a: usize, threshold: i64) -> Option<usize> {
        (a..hi.len()).find(|&g| hi[g] >= threshold)
    }

    fn brute_first_le(lo: &[i64], a: usize, threshold: i64) -> Option<usize> {
        (a..lo.len()).find(|&g| lo[g] <= threshold)
    }

    #[test]
    fn brute_force_property_test() {
        let mut rng = Lcg(0x9E37_79B9_7F4A_7C15);
        let lengths = [1usize, 2, 3, 7, 64, 1000];

        for &n in &lengths {
            for _trial in 0..200 {
                // Small value range to force ties.
                let hi: Vec<i64> = (0..n).map(|_| rng.next_below(5) as i64).collect();
                let lo: Vec<i64> = (0..n).map(|_| rng.next_below(5) as i64).collect();
                let tree = ExtremaTree::build(&hi, &lo);
                assert_eq!(tree.len(), n);

                for _q in 0..50 {
                    // Range queries: also force edge cases (a = n-1, full range).
                    let (a, b) = match rng.next_below(4) {
                        0 => (0, n - 1),     // full range
                        1 => (n - 1, n - 1), // a = n - 1
                        _ => {
                            let x = rng.next_below(n as u64) as usize;
                            let y = rng.next_below(n as u64) as usize;
                            if x <= y { (x, y) } else { (y, x) }
                        }
                    };

                    let got_max = tree.range_max(a, b);
                    let want_max = brute_range_max(&hi, a, b);
                    assert_eq!(
                        (got_max.value, got_max.first_index),
                        (want_max.value, want_max.first_index),
                        "range_max mismatch n={n} a={a} b={b} hi={hi:?}"
                    );

                    let got_min = tree.range_min(a, b);
                    let want_min = brute_range_min(&lo, a, b);
                    assert_eq!(
                        (got_min.value, got_min.first_index),
                        (want_min.value, want_min.first_index),
                        "range_min mismatch n={n} a={a} b={b} lo={lo:?}"
                    );

                    // Threshold descent queries, including exact-match,
                    // above-all, below-all, and a = n - 1.
                    let a2 = if rng.next_below(4) == 0 {
                        n - 1
                    } else {
                        rng.next_below(n as u64) as usize
                    };
                    let threshold = match rng.next_below(4) {
                        0 => -1,               // below all (values are in [0,5))
                        1 => 5,                // above all
                        2 if n > a2 => hi[a2], // exact match at some real value
                        _ => rng.next_below(6) as i64,
                    };

                    let above_actual = tree.first_at_or_above(a2, threshold);
                    let above_expected = brute_first_ge(&hi, a2, threshold);
                    assert_eq!(
                        above_actual, above_expected,
                        "first_at_or_above mismatch n={n} a={a2} threshold={threshold} hi={hi:?}"
                    );

                    let cutoff = match rng.next_below(4) {
                        0 => -1,
                        1 => 5,
                        2 if n > a2 => lo[a2],
                        _ => rng.next_below(6) as i64,
                    };
                    let below_actual = tree.first_at_or_below(a2, cutoff);
                    let below_expected = brute_first_le(&lo, a2, cutoff);
                    assert_eq!(
                        below_actual, below_expected,
                        "first_at_or_below mismatch n={n} a={a2} threshold={cutoff} lo={lo:?}"
                    );
                }
            }
        }
    }
}
