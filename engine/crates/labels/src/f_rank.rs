//! F-RANK — episode/session-relative descriptive ranks (prefix-causal).
//! Design authority: `docs/specs/events3_design_v1.md` §A "F-RANK",
//! `docs/specs/events3_formula_addendum_v1.md` §3, and
//! `docs/specs/events3_design_amendment_v2.md` §A7 (F7) "F-RANK
//! reconciliation" (published set frozen to exactly `eligible_count,
//! rank_reversal, rank_staleness`; the design brief's "pivot prominence" is
//! struck — no registered prominence definition exists, revisit hook
//! recorded there). Schema: `docs/specs/family_schemas/f_rank_schema_v1.md`.
//!
//! ## Input gap (escalation — recorded in the task report)
//!
//! [`SignalSeed`] (`crate::anchor`) does not carry `reversal_bps` or
//! `pivot_last_ts_ns`, both required by this family's exact formulas, and
//! this family's edit scope excludes `anchor.rs`. [`RankSeed`] is this
//! family's own extension (wraps [`SignalSeed`] plus the two extra
//! `event_signals.tsv` columns, read by [`parse_rank_seeds`] the same way
//! `crate::probe::parse_seeds` reads its five) — [`write_tsv`] therefore
//! takes `&[RankSeed]`, not the bare `&[SignalSeed]` the four EVENTS.2
//! families use. Wiring `parse_rank_seeds` into the probe CLI
//! (`crate::probe`) is out of this family's edit scope and left to the
//! infra wave.
//!
//! ## Exact sweep (`O(A log A)` per session, `A` = `3 * seeds.len()`)
//!
//! 1. Build one [`RankAnchor`] per `(signal, slot)` — signal-major,
//!    slot-minor, matching the output row order.
//! 2. Filter to the population: anchors with `visible_at_slot = true`
//!    (regardless of that anchor's own `slot_available` — the registered
//!    eligibility test names only `visible_at_slot` and `cutoff_ts`, see the
//!    schema doc).
//! 3. Coordinate-compress the population twice: once by
//!    `(reversal_bps desc, causal_visible_ts_ns asc, row_index asc)`, once by
//!    `(staleness asc, causal_visible_ts_ns asc, row_index asc)` — anchors
//!    with an identical composite key (only possible for different slots of
//!    the very same signal, which share every one of those fields) collapse
//!    to the same coordinate.
//! 4. Sort the population by `cutoff_ts_ns` ascending and sweep in batches of
//!    equal `cutoff_ts_ns` (mutually-eligible anchors must all be inserted
//!    into the order-statistic structures before any of them is queried):
//!    insert the whole batch into two Fenwick (binary-indexed) trees, then
//!    query `eligible_count` (the running inserted total) and both ranks
//!    (`1 + count of strictly-better coordinates already inserted`) for
//!    every batch member whose own row needs a value (`slot_available &&
//!    visible_at_slot`).

use crate::anchor::{SignalSeed, Slot, SlotRow};
use crate::frame::SessionFrame;
use std::fmt::Write as _;
use std::fs::File;
use std::io::{self, BufWriter, Write as _};
use std::path::Path;

/// [`SignalSeed`] plus the two `event_signals.tsv` columns this family's
/// formulas need that `SignalSeed` does not carry: `reversal_bps` (registered
/// header column index 6, 0-based, `registered_conventions_extract_v1.md`
/// §4) and `pivot_last_ts_ns` (index 15).
#[derive(Clone, Copy, Debug)]
pub struct RankSeed {
    pub seed: SignalSeed,
    pub reversal_bps: u64,
    pub pivot_last_ts_ns: i64,
}

/// Parses a day's verbatim `event_signals.tsv` line slice into [`RankSeed`]s:
/// reuses [`crate::probe::parse_seeds`] for the five columns every family
/// needs, then reads the two extra columns this family needs by fixed index
/// off the same lines. O(`seeds_raw_lines.len()`).
///
/// # Panics
///
/// Panics under the same conditions as [`crate::probe::parse_seeds`], plus if
/// `reversal_bps` (column 6) or `pivot_last_ts_ns` (column 15) fail to parse
/// as their registered integer type.
#[must_use]
pub fn parse_rank_seeds(seeds_raw_lines: &[String]) -> Vec<RankSeed> {
    let base = crate::probe::parse_seeds(seeds_raw_lines);
    seeds_raw_lines
        .iter()
        .zip(base)
        .map(|(line, seed)| {
            let columns: Vec<&str> = line.split('\t').collect();
            let reversal_bps_raw = columns[6];
            let pivot_last_ts_ns_raw = columns[15];
            RankSeed {
                seed,
                reversal_bps: reversal_bps_raw
                    .parse()
                    .unwrap_or_else(|_| panic!("reversal_bps is not a u64: {reversal_bps_raw}")),
                pivot_last_ts_ns: pivot_last_ts_ns_raw.parse().unwrap_or_else(|_| {
                    panic!("pivot_last_ts_ns is not an i64: {pivot_last_ts_ns_raw}")
                }),
            }
        })
        .collect()
}

/// The three published value columns (`docs/specs/family_schemas/
/// f_rank_schema_v1.md`), or `None` for a row whose own `window_frontier` is
/// `DECISION_UNAVAILABLE`/`NOT_VISIBLE` (the common-prefix blanket-NA rule).
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct RankValues {
    pub eligible_count: u64,
    pub rank_reversal: u64,
    pub rank_staleness: u64,
}

/// One `(signal, slot)` anchor's ranking-relevant fields, output-row order
/// (signal-major, slot-minor).
#[derive(Clone, Copy, Debug)]
struct RankAnchor {
    /// Output row position (`signal_index * 3 + slot_ordinal`).
    output_position: usize,
    cutoff_ts_ns: i64,
    causal_visible_ts_ns: i64,
    /// The anchor signal's 0-based row position in `day_signals.tsv`.
    row_index: usize,
    reversal_bps: u64,
    /// `cutoff_ts_ns - pivot_last_ts_ns`.
    staleness: i64,
    visible_at_slot: bool,
    /// `slot_available && visible_at_slot` — whether this row's own value
    /// columns are computed (vs. blanket-`NA`).
    needs_value: bool,
}

const fn slot_ordinal(slot: Slot) -> usize {
    match slot {
        Slot::D1 => 0,
        Slot::D2 => 1,
        Slot::D3 => 2,
    }
}

/// Minimal binary-indexed (Fenwick) tree of point-add / prefix-sum counts —
/// this family's own `O(A log A)` order-statistic structure. 0-based
/// coordinates in `[0, n)`; `add`/`count_less_than` are each `O(log n)`.
struct Fenwick {
    tree: Vec<u64>,
}

impl Fenwick {
    fn new(n: usize) -> Self {
        Self {
            tree: vec![0; n + 1],
        }
    }

    fn add(&mut self, at: usize, delta: u64) {
        let mut i = at + 1;
        while i < self.tree.len() {
            self.tree[i] += delta;
            i += i & i.wrapping_neg();
        }
    }

    /// Count of inserted elements at a coordinate strictly less than `at`.
    fn count_less_than(&self, at: usize) -> u64 {
        let Some(target) = at.checked_sub(1) else {
            return 0;
        };
        let mut i = target + 1;
        let mut sum = 0;
        while i > 0 {
            sum += self.tree[i];
            i -= i & i.wrapping_neg();
        }
        sum
    }
}

/// Assigns each element of a pre-sorted key sequence a Fenwick coordinate:
/// elements with an identical key (only possible, for this family, between
/// different slots of the very same signal) collapse to the same coordinate
/// — the one, honest way to make an unresolvable tie share a rank rather
/// than inventing a hidden order. O(n).
fn coordinates_from_sorted<T: PartialEq>(sorted_keys: &[T]) -> Vec<usize> {
    let mut coordinate = Vec::with_capacity(sorted_keys.len());
    let mut last_distinct = 0usize;
    for (index, key) in sorted_keys.iter().enumerate() {
        if index == 0 || *key != sorted_keys[index - 1] {
            last_distinct = index;
        }
        coordinate.push(last_distinct);
    }
    coordinate
}

/// Composite tie-break suffix shared by both rankings: `(causal_visible_ts_ns
/// asc, row_index asc)` — "never by id"
/// (`docs/specs/events3_formula_addendum_v1.md` §3).
type TieSuffix = (i64, usize);

/// Computes `RankValues` for every `(signal, slot)` anchor of one session in
/// one pass (see the module doc "Exact sweep"). Returns a vector indexed by
/// output position (`signal_index * 3 + slot_ordinal`); `None` at positions
/// whose own row does not need a value.
///
/// O(`A log A`), `A = 3 * seeds.len()`.
fn compute_ranks(seeds: &[RankSeed], frame: &SessionFrame) -> Vec<Option<RankValues>> {
    let total_rows = seeds.len() * 3;
    let mut anchors: Vec<RankAnchor> = Vec::with_capacity(total_rows);
    for (row_index, rank_seed) in seeds.iter().enumerate() {
        for slot in Slot::ALL {
            let row = SlotRow::compute(frame, &rank_seed.seed, slot, frame.session_end_ns);
            let staleness = row
                .cutoff_ts_ns
                .checked_sub(rank_seed.pivot_last_ts_ns)
                .expect("cutoff_ts_ns - pivot_last_ts_ns overflowed i64");
            anchors.push(RankAnchor {
                output_position: row_index * 3 + slot_ordinal(slot),
                cutoff_ts_ns: row.cutoff_ts_ns,
                causal_visible_ts_ns: rank_seed.seed.causal_visible_ts_ns,
                row_index,
                reversal_bps: rank_seed.reversal_bps,
                staleness,
                visible_at_slot: row.visible_at_slot,
                needs_value: row.slot_available && row.visible_at_slot,
            });
        }
    }

    let population: Vec<usize> = (0..anchors.len())
        .filter(|&index| anchors[index].visible_at_slot)
        .collect();

    let mut results = vec![None; total_rows];
    if population.is_empty() {
        return results;
    }

    // Coordinate compression: reversal (descending) then staleness
    // (ascending), both with the shared tie-break suffix.
    let mut order_rev = population.clone();
    order_rev.sort_by_key(|&index| {
        let a = &anchors[index];
        (
            std::cmp::Reverse(a.reversal_bps),
            a.causal_visible_ts_ns,
            a.row_index,
        )
    });
    let rev_keys: Vec<(std::cmp::Reverse<u64>, TieSuffix)> = order_rev
        .iter()
        .map(|&index| {
            let a = &anchors[index];
            (
                std::cmp::Reverse(a.reversal_bps),
                (a.causal_visible_ts_ns, a.row_index),
            )
        })
        .collect();
    let rev_coord_by_sorted_position = coordinates_from_sorted(&rev_keys);
    let mut coord_rev = vec![0usize; anchors.len()];
    for (position, &anchor_index) in order_rev.iter().enumerate() {
        coord_rev[anchor_index] = rev_coord_by_sorted_position[position];
    }

    let mut order_stale = population.clone();
    order_stale.sort_by_key(|&index| {
        let a = &anchors[index];
        (a.staleness, a.causal_visible_ts_ns, a.row_index)
    });
    let stale_keys: Vec<(i64, TieSuffix)> = order_stale
        .iter()
        .map(|&index| {
            let a = &anchors[index];
            (a.staleness, (a.causal_visible_ts_ns, a.row_index))
        })
        .collect();
    let stale_coord_by_sorted_position = coordinates_from_sorted(&stale_keys);
    let mut coord_stale = vec![0usize; anchors.len()];
    for (position, &anchor_index) in order_stale.iter().enumerate() {
        coord_stale[anchor_index] = stale_coord_by_sorted_position[position];
    }

    // Sweep by cutoff_ts_ns ascending, batched by equal cutoff_ts_ns.
    let mut order_cutoff = population.clone();
    order_cutoff.sort_by_key(|&index| anchors[index].cutoff_ts_ns);

    let mut fenwick_rev = Fenwick::new(population.len());
    let mut fenwick_stale = Fenwick::new(population.len());
    let mut total_inserted: u64 = 0;

    let mut i = 0;
    while i < order_cutoff.len() {
        let mut j = i;
        let batch_cutoff = anchors[order_cutoff[i]].cutoff_ts_ns;
        while j < order_cutoff.len() && anchors[order_cutoff[j]].cutoff_ts_ns == batch_cutoff {
            j += 1;
        }
        // Insert the whole batch first.
        for &anchor_index in &order_cutoff[i..j] {
            fenwick_rev.add(coord_rev[anchor_index], 1);
            fenwick_stale.add(coord_stale[anchor_index], 1);
            total_inserted += 1;
        }
        // Then query every batch member whose own row needs a value.
        for &anchor_index in &order_cutoff[i..j] {
            let anchor = &anchors[anchor_index];
            if anchor.needs_value {
                results[anchor.output_position] = Some(RankValues {
                    eligible_count: total_inserted,
                    rank_reversal: 1 + fenwick_rev.count_less_than(coord_rev[anchor_index]),
                    rank_staleness: 1 + fenwick_stale.count_less_than(coord_stale[anchor_index]),
                });
            }
        }
        i = j;
    }

    results
}

/// The `f_rank.tsv` header: the ten-column common prefix followed by
/// `eligible_count`, `rank_reversal`, `rank_staleness`
/// (`docs/specs/family_schemas/f_rank_schema_v1.md`).
#[must_use]
pub fn header() -> String {
    "day\tsignal_id\tslot\tseed_bar_ordinal\tcutoff_ts_ns\tslot_available\t\
     visible_at_slot\twindow_left\twindow_end\twindow_frontier\t\
     eligible_count\trank_reversal\trank_staleness"
        .to_owned()
}

/// Computes every `(signal, slot)` row as one tab-joined line, no header, no
/// trailing newline: one row per `(signal, slot)`, slots in order `D1, D2,
/// D3` (slot-minor), signals in the order given by `seeds` (`day_signals.tsv`
/// publication order). Reusable in-memory (e.g. for parquet publication)
/// without going through [`write_tsv`]'s file.
///
/// O(`seeds.len() log seeds.len()`) — see the module doc "Exact sweep".
#[must_use]
pub fn rows(frame: &SessionFrame, seeds: &[RankSeed]) -> Vec<String> {
    let ranks = compute_ranks(seeds, frame);
    let mut out = Vec::with_capacity(seeds.len() * Slot::ALL.len());
    for (row_index, rank_seed) in seeds.iter().enumerate() {
        for slot in Slot::ALL {
            let row = SlotRow::compute(frame, &rank_seed.seed, slot, frame.session_end_ns);
            let mut line = row.format_prefix(frame.day);
            match ranks[row_index * 3 + slot_ordinal(slot)] {
                Some(values) => write!(
                    line,
                    "\t{}\t{}\t{}",
                    values.eligible_count, values.rank_reversal, values.rank_staleness
                )
                .expect("writing to a String cannot fail"),
                None => line.push_str("\tNA\tNA\tNA"),
            }
            out.push(line);
        }
    }
    out
}

/// Writes `f_rank.tsv` for every `(signal, slot)` row ([`rows`]).
///
/// # Errors
///
/// Returns an [`io::Error`] if `out_path` cannot be created or written.
pub fn write_tsv(frame: &SessionFrame, seeds: &[RankSeed], out_path: &Path) -> io::Result<()> {
    let mut out = BufWriter::new(File::create(out_path)?);
    writeln!(out, "{}", header())?;
    for line in rows(frame, seeds) {
        writeln!(out, "{line}")?;
    }
    out.flush()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::anchor::Side;

    const BAR_NS: i64 = 60_000_000_000;

    fn base_seed(
        pivot_last_bar_ordinal: u64,
        causal_visible_ts_ns: i64,
        id_byte: u8,
    ) -> SignalSeed {
        SignalSeed {
            signal_id: [id_byte; 32],
            extreme_side: Side::Low,
            pivot_price_u6: 1_000_000,
            pivot_last_bar_ordinal,
            causal_visible_ts_ns,
        }
    }

    fn rank_seed(
        pivot_last_bar_ordinal: u64,
        causal_visible_ts_ns: i64,
        id_byte: u8,
        reversal_bps: u64,
        pivot_last_ts_ns: i64,
    ) -> RankSeed {
        RankSeed {
            seed: base_seed(pivot_last_bar_ordinal, causal_visible_ts_ns, id_byte),
            reversal_bps,
            pivot_last_ts_ns,
        }
    }

    fn simple_frame(session_end_bars: i64) -> SessionFrame {
        SessionFrame::from_parts_for_test(
            0,
            session_end_bars * BAR_NS,
            vec![0],
            vec![100],
            vec![100],
            vec![crate::frame::GroupKind::Scalar],
            Vec::new(),
        )
    }

    // ------------------------- coordinates_from_sorted -------------------------

    #[test]
    fn coordinates_group_equal_keys_and_advance_on_distinct_ones() {
        let keys = [1, 1, 2, 2, 2, 3];
        assert_eq!(coordinates_from_sorted(&keys), vec![0, 0, 2, 2, 2, 5]);
    }

    // ------------------------------ Fenwick tree ------------------------------

    #[test]
    fn fenwick_counts_strictly_less_than_coordinate() {
        let mut tree = Fenwick::new(5);
        for c in [0, 0, 2, 4] {
            tree.add(c, 1);
        }
        assert_eq!(tree.count_less_than(0), 0);
        assert_eq!(tree.count_less_than(1), 2);
        assert_eq!(tree.count_less_than(2), 2);
        assert_eq!(tree.count_less_than(3), 3);
        assert_eq!(tree.count_less_than(5), 4);
    }

    // ------------------------------ compute_ranks ------------------------------

    #[test]
    fn single_visible_signal_ranks_first_of_one_at_every_slot() {
        // One signal, visible immediately: at D1, D2, D3 it is always the
        // sole eligible member of its own population (earlier slots of the
        // SAME signal are also eligible). `reversal_bps` is a per-signal
        // constant, so it's a full tie across all three slots (all rank 1).
        // `staleness = cutoff_ts - pivot_last_ts_ns` grows with the slot's
        // own (larger) cutoff, so it is NOT tied: D1 is freshest within any
        // population that includes it, so D2's own row ranks *behind* D1
        // (rank 2 of 2), and D3 ranks behind both D1 and D2 (rank 3 of 3).
        let frame = simple_frame(10);
        let seeds = vec![rank_seed(0, 0, 0xaa, 40, 0)];
        let ranks = compute_ranks(&seeds, &frame);
        assert_eq!(
            ranks[0],
            Some(RankValues {
                eligible_count: 1,
                rank_reversal: 1,
                rank_staleness: 1
            })
        );
        assert_eq!(
            ranks[1],
            Some(RankValues {
                eligible_count: 2,
                rank_reversal: 1,
                rank_staleness: 2
            })
        );
        assert_eq!(
            ranks[2],
            Some(RankValues {
                eligible_count: 3,
                rank_reversal: 1,
                rank_staleness: 3
            })
        );
    }

    #[test]
    fn eligible_set_includes_same_signal_earlier_slots() {
        // D2's eligible_count must include D1 of the SAME signal (D1's
        // cutoff <= D2's cutoff) in addition to D2 itself: eligible_count=2
        // at D2, not 1.
        let frame = simple_frame(10);
        let seeds = vec![rank_seed(0, 0, 0xaa, 40, 0)];
        let ranks = compute_ranks(&seeds, &frame);
        let d2 = ranks[1].expect("D2 computed");
        assert_eq!(d2.eligible_count, 2);
    }

    #[test]
    fn rank_reversal_orders_by_reversal_bps_descending() {
        // Two signals visible at the same D1 cutoff-eligible time, distinct
        // reversal_bps: larger reversal_bps ranks 1st.
        let frame = simple_frame(10);
        let seeds = vec![rank_seed(5, 0, 0xaa, 20, 0), rank_seed(5, 0, 0xbb, 80, 0)];
        let ranks = compute_ranks(&seeds, &frame);
        // Both signals' D1 cutoff = BAR_NS (seed_bar_ordinal=5, slot D1 =>
        // cutoff = 6*BAR_NS for both) => same batch, eligible_count=2 each.
        let sig0_d1 = ranks[0].expect("signal 0 D1");
        let sig1_d1 = ranks[3].expect("signal 1 D1");
        assert_eq!(sig0_d1.eligible_count, 2);
        assert_eq!(sig1_d1.eligible_count, 2);
        // reversal_bps 80 (signal 1) ranks 1st; reversal_bps 20 (signal 0)
        // ranks 2nd.
        assert_eq!(sig1_d1.rank_reversal, 1);
        assert_eq!(sig0_d1.rank_reversal, 2);
    }

    #[test]
    fn rank_reversal_ties_broken_by_earlier_visible_ts_then_row_index() {
        // Three signals, all reversal_bps=40 (a full tie on the primary
        // value), all visible/eligible at the same D1 cutoff instant.
        // Signal A: visible_ts=100 (earliest) => rank 1.
        // Signal B and C: visible_ts=200 (tied with each other) => broken by
        // row index (B is row 1, C is row 2) => B rank 2, C rank 3.
        let frame = simple_frame(10);
        let seeds = vec![
            rank_seed(5, 100, 0xaa, 40, 0), // A, row 0
            rank_seed(5, 200, 0xbb, 40, 0), // B, row 1
            rank_seed(5, 200, 0xcc, 40, 0), // C, row 2
        ];
        let ranks = compute_ranks(&seeds, &frame);
        let a_d1 = ranks[0].expect("A D1");
        let b_d1 = ranks[3].expect("B D1");
        let c_d1 = ranks[6].expect("C D1");
        assert_eq!(a_d1.rank_reversal, 1);
        assert_eq!(b_d1.rank_reversal, 2);
        assert_eq!(c_d1.rank_reversal, 3);
    }

    #[test]
    fn same_signal_different_slots_share_a_rank_when_fully_tied() {
        // A single signal's D1 and D2 anchors share identical
        // `reversal_bps`, `causal_visible_ts_ns`, and row index — the tie
        // rule cannot separate them on THAT ranking, so within D2's own
        // population (which includes D1) they must receive the SAME
        // rank_reversal (both rank 1), never an invented distinct order.
        // `staleness` is NOT tied across slots of the same signal (it grows
        // with the slot's own larger cutoff), so rank_staleness correctly
        // differs (D2 ranks behind D1: 2 of 2).
        let frame = simple_frame(10);
        let seeds = vec![rank_seed(0, 0, 0xaa, 40, 0)];
        let ranks = compute_ranks(&seeds, &frame);
        let d2 = ranks[1].expect("D2 computed");
        assert_eq!(d2.rank_reversal, 1);
        assert_eq!(d2.rank_staleness, 2);
    }

    #[test]
    fn rank_staleness_orders_ascending_freshest_first() {
        // Two signals sharing a D1 cutoff-eligible batch; smaller staleness
        // (cutoff - pivot_last_ts_ns) ranks 1st (freshest).
        let frame = simple_frame(10);
        let seeds = vec![
            rank_seed(5, 0, 0xaa, 40, 0),          // staleness = cutoff - 0 (larger)
            rank_seed(5, 0, 0xbb, 40, 5 * BAR_NS), // staleness = cutoff - 5*BAR_NS (smaller)
        ];
        let ranks = compute_ranks(&seeds, &frame);
        let sig0_d1 = ranks[0].expect("signal 0 D1");
        let sig1_d1 = ranks[3].expect("signal 1 D1");
        assert_eq!(sig1_d1.rank_staleness, 1);
        assert_eq!(sig0_d1.rank_staleness, 2);
    }

    #[test]
    fn not_visible_anchor_is_excluded_from_everyone_else_population() {
        // Signal B is not visible until after D1's cutoff for signal A —
        // signal B's own D1 row is NA, and it must NOT count toward signal
        // A's eligible_count either.
        let frame = simple_frame(10);
        let seeds = vec![
            rank_seed(0, 0, 0xaa, 40, 0), // A: D1 cutoff = BAR_NS, visible at 0.
            rank_seed(0, BAR_NS + 1, 0xbb, 40, 0), // B: not visible at its own D1 cutoff.
        ];
        let ranks = compute_ranks(&seeds, &frame);
        let a_d1 = ranks[0].expect("A D1 computed");
        // Only A itself is eligible for A's own D1 (B is not visible yet).
        assert_eq!(a_d1.eligible_count, 1);
        // B's own D1 row is NA (not visible).
        assert_eq!(ranks[3], None);
    }

    #[test]
    fn decision_unavailable_rows_are_na_and_never_inflate_anyone_elses_eligible_count() {
        // seed_bar_ordinal near the session end: A's D2/D3 cutoffs land at
        // or past session_end_ns (DECISION_UNAVAILABLE, needs_value=false).
        // Note (provable, not just tested): a DECISION_UNAVAILABLE anchor's
        // own cutoff_ts is necessarily >= session_end_ns, so it can only be
        // "eligible" (cutoff_ts(a') <= cutoff_ts(a)) for some other anchor a
        // whose own cutoff_ts is ALSO >= session_end_ns — i.e. an anchor
        // that is itself DECISION_UNAVAILABLE and therefore never needs a
        // value either. A DECISION_UNAVAILABLE anchor can thus never affect
        // any row this family actually emits a value for; the registered
        // eligibility rule (`visible_at_slot` + `cutoff_ts`, no
        // `slot_available` test) is faithfully implemented, and this test
        // pins the one externally-observable consequence: such rows are
        // NA, and B's own (fully available) ranking is unaffected by A's
        // unavailable slots.
        let session_end_bars = 3;
        let frame = simple_frame(session_end_bars);
        let seeds = vec![
            rank_seed(1, 0, 0xaa, 40, 0), // A: D1 cutoff=2*BAR_NS (avail), D2 cutoff=3*BAR_NS==end (UNAVAILABLE), D3 cutoff=4*BAR_NS (UNAVAILABLE).
            rank_seed(0, 0, 0xbb, 20, 0), // B: D1 cutoff=BAR_NS (avail, earlier than A's D1/D2/D3).
        ];
        let ranks = compute_ranks(&seeds, &frame);
        assert_eq!(ranks[1], None); // A's D2: DECISION_UNAVAILABLE.
        assert_eq!(ranks[2], None); // A's D3: DECISION_UNAVAILABLE.
        // B's D1 population is just {B's D1} (A's D1 cutoff is later, and
        // A's D2/D3 are both unavailable and later still): eligible_count=1.
        let b_d1 = ranks[3].expect("B D1 computed");
        assert_eq!(b_d1.eligible_count, 1);
    }

    // --------------------------------- write_tsv --------------------------------

    fn temp_out_path(name: &str) -> std::path::PathBuf {
        std::env::temp_dir().join(format!("f_rank_test_{}_{name}.tsv", std::process::id()))
    }

    #[test]
    fn write_tsv_header_has_the_exact_expected_column_count() {
        let header = header();
        let columns: Vec<&str> = header.split('\t').collect();
        assert_eq!(columns.len(), 13);
        assert_eq!(columns[9], "window_frontier");
        assert_eq!(columns[10], "eligible_count");
        assert_eq!(columns[11], "rank_reversal");
        assert_eq!(columns[12], "rank_staleness");
    }

    #[test]
    fn write_tsv_produces_three_rows_per_signal_with_values_or_na() {
        let frame = simple_frame(3);
        let seeds = vec![rank_seed(1, 0, 0xaa, 40, 0)];
        let path = temp_out_path("basic");
        write_tsv(&frame, &seeds, &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        assert_eq!(lines.next(), Some(header().as_str()));
        let d1 = lines.next().expect("D1 row");
        let d2 = lines.next().expect("D2 row");
        let d3 = lines.next().expect("D3 row");
        assert_eq!(lines.next(), None);

        let d1_cols: Vec<&str> = d1.split('\t').collect();
        assert_eq!(d1_cols[10], "1"); // eligible_count
        assert_eq!(d1_cols[11], "1"); // rank_reversal
        assert_eq!(d1_cols[12], "1"); // rank_staleness

        let d2_cols: Vec<&str> = d2.split('\t').collect();
        assert_eq!(d2_cols[9], "DECISION_UNAVAILABLE");
        assert_eq!(d2_cols[10], "NA");
        assert_eq!(d2_cols[11], "NA");
        assert_eq!(d2_cols[12], "NA");

        let d3_cols: Vec<&str> = d3.split('\t').collect();
        assert_eq!(d3_cols[9], "DECISION_UNAVAILABLE");
        assert_eq!(d3_cols[10], "NA");

        std::fs::remove_file(&path).ok();
    }

    // ---------------------------- parse_rank_seeds ----------------------------

    #[test]
    fn parse_rank_seeds_extracts_reversal_bps_and_pivot_last_ts_ns() {
        let mut columns = vec!["0".to_owned(); 40];
        columns[1] = "2022-01-03".to_owned();
        columns[2] = "11".repeat(32);
        columns[6] = "40".to_owned();
        columns[9] = "LOW".to_owned();
        columns[10] = "1000000".to_owned();
        columns[15] = "12345".to_owned();
        columns[16] = "7".to_owned();
        columns[20] = "999".to_owned();
        let line = columns.join("\t");

        let parsed = parse_rank_seeds(&[line]);
        assert_eq!(parsed.len(), 1);
        assert_eq!(parsed[0].reversal_bps, 40);
        assert_eq!(parsed[0].pivot_last_ts_ns, 12345);
        assert_eq!(parsed[0].seed.pivot_last_bar_ordinal, 7);
        assert_eq!(parsed[0].seed.causal_visible_ts_ns, 999);
    }
}
