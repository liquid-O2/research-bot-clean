//! F-DWELL — dwell/occupation/runs/underwater family (bar-close integration
//! vs the pivot price `P`, §11.3). Design authority: `docs/specs/events3_design_v1.md`
//! §A "F-DWELL", `docs/specs/events3_formula_addendum_v1.md` §4, and
//! `docs/specs/events3_design_amendment_v2.md` §A5 (F-DWELL — WINS every
//! conflict with the other two). Exact schema:
//! `docs/specs/family_schemas/f_dwell_schema_v1.md`.
//!
//! One integration law (amendment A5): each one-minute bar's representative
//! price is the last scientific-path group strictly before the bar's
//! clipped end (`min(bar_end, observed_end_ns)`) — never a group at/after
//! that bound, so a breaker- or close-clipped bar can never leak a
//! post-frontier price into its own representative. A bar with no such group
//! *inside the slot's own window* is `NO_QUOTE`; a bar whose representative
//! group is `HETEROGENEOUS` (CONV §7: more than one distinct scientific
//! midpoint at that millisecond, intra-group order uncertain) is
//! `AMBIGUOUS_CLOSE` — an implementer-authored gap-fill, since no formula
//! anywhere defines a single scalar "close" for a heterogeneous group; this
//! mirrors `f_pass.tsv`'s own `Scalar → EXACT` / `Heterogeneous →
//! INTERVAL_AMBIGUOUS` precedent (kind-based, never a fabricated price).
//! Both excluded states are removed from the run/break-reclaim sequence
//! entirely, as if the bar did not exist.
//!
//! Complexity: `O(bars_in_window * log(n))` per anchor, `n` =
//! `frame.group_count()` — one [`SessionFrame::end_position`] binary search
//! per bar boundary (`bars_in_window` ≤ `expected_bar_count`, 390 or 210 for
//! an early-close day), never an `O(window-groups)` scan. This is the
//! architect-authorized complexity for this family (a fixed small bar count,
//! not proportional to how many scientific groups fall inside the window).

use crate::anchor::{Side, SignalSeed, Slot, SlotRow, WindowFrontier};
use crate::frame::{GroupKind, SessionFrame};
use std::fmt::Write as _;
use std::fs::File;
use std::io::{self, BufWriter, Write as _};
use std::path::Path;

/// Registered one-minute bar duration in nanoseconds (CONV §3).
const BAR_NS: i64 = 60_000_000_000;
/// Nanoseconds per millisecond — group timestamps and every window boundary
/// used by this family are millisecond-grained, so every clipped bar span
/// converts to milliseconds losslessly (amendment A5).
const NANOS_PER_MS: i64 = 1_000_000;

/// One bar's classification against `P` (schema "Bar walk"): `NoQuote` and
/// `AmbiguousClose` are excluded from every sum/run; `Above`/`Below`/`At` are
/// "valid" bars carrying a signed three-valued sign for run/break-reclaim
/// purposes.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum BarState {
    NoQuote,
    AmbiguousClose,
    Above,
    Below,
    At,
}

/// `dir` from `extreme_side` (`label_probe_schema_v1.md` "Direction
/// shorthand"): `Low → +1` (favorable = up), `High → −1` (favorable = down).
const fn dir(side: Side) -> i64 {
    match side {
        Side::Low => 1,
        Side::High => -1,
    }
}

/// One anchor's complete F-DWELL result (schema "Value columns").
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct DwellResult {
    above_ns: i64,
    below_ns: i64,
    at_ns: i64,
    longest_fav_run_bars: u32,
    longest_adv_run_bars: u32,
    break_reclaim_count: i64,
    /// `None` when the accumulated area does not fit `i64` (typed OVERFLOW
    /// guard, amendment A5).
    retained_area_u6ms: Option<i64>,
    no_quote_bars: i64,
    ambiguous_close_bars: i64,
}

/// The result of locating and classifying one bar's representative group:
/// the [`BarState`] plus, for `Above` bars only, the signed `u6` value
/// needed for the area contribution (avoids a second lookup of the same
/// representative index).
struct BarClassification {
    state: BarState,
    /// `Some` only when `state == BarState::Above` (`dir · (close − P)`,
    /// always strictly positive in that case).
    above_signed_u6: Option<i64>,
}

/// Classifies one bar's representative group (schema "Bar walk"): looks up
/// the last scientific-path group with `ts_ns < bound` via
/// [`SessionFrame::end_position`] (O(log n)), then applies the
/// `NO_QUOTE` / `AMBIGUOUS_CLOSE` / `ABOVE`/`BELOW`/`AT` rule.
fn classify_bar(
    frame: &SessionFrame,
    side: Side,
    pivot_price_u6: i64,
    window_left: usize,
    bound: i64,
) -> BarClassification {
    let idx = frame.end_position(bound);
    if idx == 0 {
        return BarClassification {
            state: BarState::NoQuote,
            above_signed_u6: None,
        };
    }
    let g = idx - 1;
    if g < window_left {
        return BarClassification {
            state: BarState::NoQuote,
            above_signed_u6: None,
        };
    }
    if frame.kind[g] == GroupKind::Heterogeneous {
        return BarClassification {
            state: BarState::AmbiguousClose,
            above_signed_u6: None,
        };
    }
    let close_u6 = frame.m_lo[g];
    debug_assert_eq!(
        close_u6, frame.m_hi[g],
        "a Scalar group's m_lo must equal its m_hi"
    );
    let signed_u6 = dir(side)
        .checked_mul(close_u6 - pivot_price_u6)
        .expect("dir * (close - P) overflowed i64 for a registered anchor price");
    match signed_u6.cmp(&0) {
        std::cmp::Ordering::Greater => BarClassification {
            state: BarState::Above,
            above_signed_u6: Some(signed_u6),
        },
        std::cmp::Ordering::Less => BarClassification {
            state: BarState::Below,
            above_signed_u6: None,
        },
        std::cmp::Ordering::Equal => BarClassification {
            state: BarState::At,
            above_signed_u6: None,
        },
    }
}

/// Running totals for one anchor's bar walk (extracted from [`compute_dwell`]
/// purely to keep that function short — same fields as [`DwellResult`] plus
/// the run/break-reclaim tracking state that doesn't survive past the walk).
#[derive(Default)]
struct DwellAccumulator {
    above_ns: i64,
    below_ns: i64,
    at_ns: i64,
    no_quote_bars: i64,
    ambiguous_close_bars: i64,
    break_reclaim_count: i64,
    longest_fav_run_bars: u32,
    longest_adv_run_bars: u32,
    current_sign: Option<i8>,
    current_run_len: u32,
    area_i128: i128,
}

impl DwellAccumulator {
    /// Folds one classified bar into the running totals
    /// (`docs/specs/family_schemas/f_dwell_schema_v1.md` "Bar walk"/"Value
    /// columns"). `bar_span_ns` is that bar's own clipped span.
    ///
    /// # Panics
    ///
    /// Panics on `i64`/`u32` overflow (unreachable for any registered
    /// session) or if `bar_span_ns` is not an exact millisecond multiple for
    /// an `Above` bar (amendment A5's "spans are exact ms multiples"
    /// invariant).
    fn record(&mut self, classification: &BarClassification, bar_span_ns: i64) {
        match classification.state {
            BarState::NoQuote => self.no_quote_bars += 1,
            BarState::AmbiguousClose => self.ambiguous_close_bars += 1,
            BarState::Above => {
                self.above_ns = self
                    .above_ns
                    .checked_add(bar_span_ns)
                    .expect("above_ns overflowed i64");
                let rem = bar_span_ns % NANOS_PER_MS;
                assert_eq!(
                    rem, 0,
                    "bar span must be an exact millisecond multiple (amendment A5)"
                );
                let span_ms = bar_span_ns / NANOS_PER_MS;
                let signed_u6 = classification
                    .above_signed_u6
                    .expect("Above classification always carries its signed value");
                self.area_i128 += i128::from(signed_u6) * i128::from(span_ms);
                self.record_valid_sign(1);
            }
            BarState::Below => {
                self.below_ns = self
                    .below_ns
                    .checked_add(bar_span_ns)
                    .expect("below_ns overflowed i64");
                self.record_valid_sign(-1);
            }
            BarState::At => {
                self.at_ns = self
                    .at_ns
                    .checked_add(bar_span_ns)
                    .expect("at_ns overflowed i64");
                self.record_valid_sign(0);
            }
        }
    }

    /// Updates run-length and break/reclaim tracking for one valid bar's
    /// three-valued sign (`+1` above / `0` at / `-1` below); `NoQuote` and
    /// `AmbiguousClose` bars never call this — they are excluded from the
    /// sequence entirely.
    fn record_valid_sign(&mut self, sign: i8) {
        match self.current_sign {
            Some(prev) if prev == sign => {
                self.current_run_len = self
                    .current_run_len
                    .checked_add(1)
                    .expect("run length overflowed u32");
            }
            Some(_) => {
                self.break_reclaim_count = self
                    .break_reclaim_count
                    .checked_add(1)
                    .expect("break_reclaim_count overflowed i64");
                self.current_run_len = 1;
            }
            None => self.current_run_len = 1,
        }
        self.current_sign = Some(sign);
        match sign {
            1 => self.longest_fav_run_bars = self.longest_fav_run_bars.max(self.current_run_len),
            -1 => self.longest_adv_run_bars = self.longest_adv_run_bars.max(self.current_run_len),
            _ => {}
        }
    }

    /// Converts the running totals into the published [`DwellResult`],
    /// applying the typed OVERFLOW guard to the accumulated area.
    fn finish(self) -> DwellResult {
        DwellResult {
            above_ns: self.above_ns,
            below_ns: self.below_ns,
            at_ns: self.at_ns,
            longest_fav_run_bars: self.longest_fav_run_bars,
            longest_adv_run_bars: self.longest_adv_run_bars,
            break_reclaim_count: self.break_reclaim_count,
            retained_area_u6ms: i64::try_from(self.area_i128).ok(),
            no_quote_bars: self.no_quote_bars,
            ambiguous_close_bars: self.ambiguous_close_bars,
        }
    }
}

/// Computes the complete F-DWELL result for one anchor over its own
/// close-bounded window (`docs/specs/family_schemas/f_dwell_schema_v1.md`
/// "Bar walk"). `row` must have `window_left` present (i.e. its frontier is
/// neither `DECISION_UNAVAILABLE` nor `NOT_VISIBLE`) — callers only invoke
/// this after checking that.
///
/// `O(bars_in_window * log(n))`: one [`SessionFrame::end_position`] descent
/// per bar boundary.
///
/// # Panics
///
/// Panics if `row.window_left` is absent (caller invariant), if the bar-walk
/// arithmetic overflows `i64` (unreachable for any registered session, at
/// most a few hundred one-minute bars), or if a clipped bar span is not an
/// exact millisecond multiple (amendment A5's invariant: every window
/// boundary used here is millisecond-grained).
fn compute_dwell(frame: &SessionFrame, seed: &SignalSeed, row: &SlotRow) -> DwellResult {
    let window_left = row
        .window_left
        .expect("compute_dwell called only when the window is present");

    // observed_end_ns mirrors SlotRow::compute's own derivation (not exposed
    // by anchor.rs, which this crate may not edit): F-DWELL's own
    // nominal_end_ns is frame.session_end_ns, so requested_end_ns collapses
    // to session_end_ns exactly.
    let requested_end_ns = frame.session_end_ns;
    let observed_end_ns = frame
        .first_breaker_start_after(row.cutoff_ts_ns)
        .map_or(requested_end_ns, |start| start.min(requested_end_ns));

    let mut acc = DwellAccumulator::default();
    let mut bar_start_ns = row.cutoff_ts_ns;
    while bar_start_ns < observed_end_ns {
        let bar_end_ns = bar_start_ns
            .checked_add(BAR_NS)
            .expect("bar_start_ns + BAR_NS overflowed i64 for a registered session");
        let bound = bar_end_ns.min(observed_end_ns);
        let bar_span_ns = bound - bar_start_ns;

        let classification = classify_bar(
            frame,
            seed.extreme_side,
            seed.pivot_price_u6,
            window_left,
            bound,
        );
        acc.record(&classification, bar_span_ns);

        bar_start_ns = bar_end_ns;
    }

    acc.finish()
}

/// The `f_dwell.tsv` header: the ten-column common prefix
/// (`crate::anchor::SlotRow::format_prefix`) followed by the ten F-DWELL
/// value columns (`docs/specs/family_schemas/f_dwell_schema_v1.md`).
#[must_use]
pub fn header() -> &'static str {
    "day\tsignal_id\tslot\tseed_bar_ordinal\tcutoff_ts_ns\tslot_available\t\
     visible_at_slot\twindow_left\twindow_end\twindow_frontier\t\
     above_ns\tbelow_ns\tat_ns\tlongest_fav_run_bars\tlongest_adv_run_bars\t\
     break_reclaim_count\tretained_area_u6ms\tretained_area_state\t\
     no_quote_bars\tambiguous_close_bars"
}

/// Appends the ten F-DWELL value columns for one computed result.
fn push_value_columns(line: &mut String, result: &DwellResult) {
    let (area_wire, state_wire) = match result.retained_area_u6ms {
        Some(value) => (value.to_string(), "OK"),
        None => ("NA".to_owned(), "OVERFLOW"),
    };
    write!(
        line,
        "\t{}\t{}\t{}\t{}\t{}\t{}\t{area_wire}\t{state_wire}\t{}\t{}",
        result.above_ns,
        result.below_ns,
        result.at_ns,
        result.longest_fav_run_bars,
        result.longest_adv_run_bars,
        result.break_reclaim_count,
        result.no_quote_bars,
        result.ambiguous_close_bars,
    )
    .expect("writing to a String cannot fail");
}

/// Computes every `(signal, slot)` row as one tab-joined line, no header, no
/// trailing newline: one row per `(signal, slot)`, slots in order `D1, D2,
/// D3` (slot-minor), signals in the order given by `seeds` — the caller's
/// `day_signals.tsv` publication order (`docs/specs/label_probe_schema_v1.md`
/// "Family-file common prefix"). Reusable in-memory (e.g. for parquet
/// publication) without going through [`write_tsv`]'s file.
///
/// Rows whose window frontier is `DECISION_UNAVAILABLE`/`NOT_VISIBLE` carry
/// literal `NA` in all ten value columns; every other row computes the full
/// bar walk (`docs/specs/family_schemas/f_dwell_schema_v1.md` "Bar walk").
///
/// `O(seeds.len() * 3 slots * bars_in_window)`, each bar boundary `O(log n)`.
#[must_use]
pub fn rows(frame: &SessionFrame, seeds: &[SignalSeed]) -> Vec<String> {
    let mut out = Vec::with_capacity(seeds.len() * Slot::ALL.len());
    for seed in seeds {
        for slot in Slot::ALL {
            let row = SlotRow::compute(frame, seed, slot, frame.session_end_ns);
            let mut line = row.format_prefix(frame.day);
            if matches!(
                row.window_frontier,
                WindowFrontier::DecisionUnavailable | WindowFrontier::NotVisible
            ) {
                line.push_str("\tNA\tNA\tNA\tNA\tNA\tNA\tNA\tNA\tNA\tNA");
            } else {
                let result = compute_dwell(frame, seed, &row);
                push_value_columns(&mut line, &result);
            }
            out.push(line);
        }
    }
    out
}

/// Writes `f_dwell.tsv` for every `(signal, slot)` row ([`rows`]).
///
/// # Errors
///
/// Returns an [`io::Error`] if `out_path` cannot be created or written.
pub fn write_tsv(frame: &SessionFrame, seeds: &[SignalSeed], out_path: &Path) -> io::Result<()> {
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
    use crate::frame::{Breaker, GroupKind};

    fn seed(
        side: Side,
        pivot_last_bar_ordinal: u64,
        causal_visible_ts_ns: i64,
        pivot_price_u6: i64,
    ) -> SignalSeed {
        SignalSeed {
            signal_id: [0xab; 32],
            extreme_side: side,
            pivot_price_u6,
            pivot_last_bar_ordinal,
            causal_visible_ts_ns,
        }
    }

    fn temp_out_path(name: &str) -> std::path::PathBuf {
        std::env::temp_dir().join(format!("f_dwell_test_{}_{name}.tsv", std::process::id()))
    }

    // ------------------------- header shape -------------------------

    #[test]
    fn header_has_twenty_columns() {
        let columns: Vec<&str> = header().split('\t').collect();
        assert_eq!(columns.len(), 20);
        assert_eq!(columns[0], "day");
        assert_eq!(columns[9], "window_frontier");
        assert_eq!(columns[10], "above_ns");
        assert_eq!(columns[19], "ambiguous_close_bars");
    }

    // ------------------------- decision unavailable / not visible -------------------------

    #[test]
    fn write_tsv_decision_unavailable_row_is_all_na() {
        let session_end_ns = 3 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![0],
            vec![100],
            vec![100],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(Side::Low, 1, 0, 1_000_000);
        let path = temp_out_path("decision_unavailable");
        write_tsv(&frame, std::slice::from_ref(&s), &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        lines.next(); // header
        lines.next(); // D1 (available)
        let d2 = lines.next().expect("D2 row");
        let cols: Vec<&str> = d2.split('\t').collect();
        assert_eq!(cols[9], "DECISION_UNAVAILABLE");
        assert!(cols[10..].iter().all(|&c| c == "NA"));
        std::fs::remove_file(&path).ok();
    }

    // ------------------------- equality-at-P bars -------------------------

    #[test]
    fn equality_at_p_counts_to_at_ns_not_above_or_below() {
        // D1 cutoff = BAR_NS (seed bar 0). session_end_ns = 2*BAR_NS bounds
        // the window to exactly one bar, so the hand computation is crisp.
        // window_left = end_position(BAR_NS) = 1 (group 0 at ts=0 predates
        // the cutoff); the one walked bar's representative is group 1
        // (ts=BAR_NS, index 1 >= window_left), price == P exactly.
        let frame = SessionFrame::from_parts_for_test(
            0,
            2 * BAR_NS,
            vec![0, BAR_NS],
            vec![100, 1_000_000],
            vec![100, 1_000_000],
            vec![GroupKind::Scalar; 2],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        assert_eq!(row.window_left, Some(1));
        let result = compute_dwell(&frame, &s, &row);
        assert_eq!(result.at_ns, BAR_NS);
        assert_eq!(result.above_ns, 0);
        assert_eq!(result.below_ns, 0);
        assert_eq!(result.no_quote_bars, 0);
        assert_eq!(result.retained_area_u6ms, Some(0));
    }

    // ------------------------- NO_QUOTE leading bars -------------------------

    #[test]
    fn no_quote_leading_bars_before_the_first_in_window_group() {
        // Window opens at cutoff = BAR_NS (D1, seed bar 0); the pre-cutoff
        // group at ts=0 is index 0 but window_left = end_position(BAR_NS) =
        // 1, so bars whose "last group before bound" is still index 0 must
        // be NO_QUOTE. The first in-window group doesn't arrive until
        // ts = 3*BAR_NS + 1 (inside the fourth bar).
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, 3 * BAR_NS + 1, 4 * BAR_NS],
            vec![50, 999_000, 1_000_500],
            vec![50, 999_000, 1_000_500],
            vec![GroupKind::Scalar; 3],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        assert_eq!(row.window_left, Some(1));
        let result = compute_dwell(&frame, &s, &row);
        // Bars [BAR_NS,2*BAR_NS), [2*BAR_NS,3*BAR_NS), [3*BAR_NS,4*BAR_NS):
        // the last group before each of those bounds (2*BAR_NS, 3*BAR_NS,
        // 4*BAR_NS respectively) is still group 0 (ts=0) for the first two,
        // and group 1 (ts=3*BAR_NS+1) for the third. Group 0 < window_left
        // (1): NO_QUOTE for the first two bars only.
        assert_eq!(result.no_quote_bars, 2);
        // Bar [3*BAR_NS,4*BAR_NS): representative is group 1 (index 1 >=
        // window_left 1), price 999_000 < P(1_000_000): BELOW.
        assert!(result.below_ns >= BAR_NS);
    }

    // ------------------------- breaker-inside-bar -------------------------

    #[test]
    fn breaker_inside_bar_clips_the_bar_and_never_leaks_the_post_breaker_close() {
        // D1 cutoff = BAR_NS (seed bar 0). Group 0 sits exactly at cutoff
        // (price == P). A breaker starts mid-way through the FIRST windowed
        // bar (cutoff + BAR_NS/2, strictly after cutoff so it is reachable
        // by `first_breaker_start_after`), with a scientific group AFTER the
        // breaker (at 2*BAR_NS) that must NOT be used as that bar's
        // representative.
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![BAR_NS, 2 * BAR_NS],
            vec![1_000_000, 2_000_000],
            vec![1_000_000, 2_000_000],
            vec![GroupKind::Scalar; 2],
            vec![Breaker {
                start_ns: BAR_NS + BAR_NS / 2,
                end_ns: 3 * BAR_NS,
            }],
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        assert_eq!(row.window_frontier, WindowFrontier::WideBreaker);
        let result = compute_dwell(&frame, &s, &row);
        // observed_end_ns = BAR_NS + BAR_NS/2 (the breaker start): only one
        // clipped bar is walked, span BAR_NS/2, representative = group 0
        // (price == P): AT. The group at 2*BAR_NS (price 2_000_000, would be
        // far ABOVE) must never be selected.
        assert_eq!(result.at_ns, BAR_NS / 2);
        assert_eq!(result.above_ns, 0);
        assert_eq!(result.no_quote_bars, 0);
    }

    // ------------------------- window shorter than one bar -------------------------

    #[test]
    fn window_shorter_than_one_bar_is_a_single_clipped_bar() {
        // D1 cutoff = BAR_NS. A breaker starting exactly 1ms after cutoff
        // (millisecond-aligned, respecting the amendment's exact-ms-span
        // invariant) censors the window to far less than one full bar.
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![BAR_NS],
            vec![1_000_000],
            vec![1_000_000],
            vec![GroupKind::Scalar],
            vec![Breaker {
                start_ns: BAR_NS + 1_000_000, // exactly 1ms after cutoff
                end_ns: 2 * BAR_NS,
            }],
        );
        let s = seed(Side::Low, 0, 0, 999_000);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        assert_eq!(row.window_left, Some(0));
        let result = compute_dwell(&frame, &s, &row);
        // Only one bar walked, clipped to span 1_000_000ns (1ms);
        // representative = group 0 (price 1_000_000 > P 999_000): ABOVE.
        assert_eq!(result.above_ns, 1_000_000);
        assert_eq!(result.below_ns, 0);
        assert_eq!(result.at_ns, 0);
        assert_eq!(result.no_quote_bars, 0);
        // signed_u6 = 1_000, bar_span_ms = 1 => area = 1_000.
        assert_eq!(result.retained_area_u6ms, Some(1_000));
    }

    // ------------------------- longest-run and break/reclaim hand case -------------------------

    #[test]
    fn longest_run_and_break_reclaim_hand_computed() {
        // D1 cutoff = BAR_NS (seed bar 0); session ends at 5*BAR_NS so
        // exactly 4 bars fall in the window. Each bar has its own scalar
        // group exactly at its own start: prices chosen to give the
        // sequence ABOVE, ABOVE, BELOW, ABOVE (P = 1_000_000, Low: dir=+1).
        let frame = SessionFrame::from_parts_for_test(
            0,
            5 * BAR_NS,
            vec![BAR_NS, 2 * BAR_NS, 3 * BAR_NS, 4 * BAR_NS],
            vec![1_100_000, 1_200_000, 900_000, 1_050_000],
            vec![1_100_000, 1_200_000, 900_000, 1_050_000],
            vec![GroupKind::Scalar; 4],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        let result = compute_dwell(&frame, &s, &row);
        // Sequence: ABOVE, ABOVE, BELOW, ABOVE.
        // Transitions: (above,above)=same, (above,below)=change,
        // (below,above)=change => break_reclaim_count = 2.
        assert_eq!(result.break_reclaim_count, 2);
        // longest_fav_run_bars: the first two ABOVE bars => 2 (the trailing
        // single ABOVE bar doesn't beat that).
        assert_eq!(result.longest_fav_run_bars, 2);
        // longest_adv_run_bars: the single BELOW bar => 1.
        assert_eq!(result.longest_adv_run_bars, 1);
        assert_eq!(result.above_ns, 3 * BAR_NS);
        assert_eq!(result.below_ns, BAR_NS);
        assert_eq!(result.no_quote_bars, 0);
    }

    // ------------------------- real-scale area bound -------------------------

    #[test]
    fn real_scale_area_bound_fits_comfortably_in_i64() {
        // Worst-case bound sanity: max plausible IWM price displacement
        // (~$50 => 5e7 u6) held ABOVE for a full 390-bar session
        // (session length in ms = 390 * 60_000 = 23_400_000 ms).
        let max_signed_u6: i128 = 50_000_000; // ~$50
        let max_span_ms: i128 = 390 * 60_000;
        let worst_case_area = max_signed_u6 * max_span_ms;
        assert!(i64::try_from(worst_case_area).is_ok());
        assert!(worst_case_area < i128::from(i64::MAX));
    }

    #[test]
    fn retained_area_overflow_is_typed_not_panicking() {
        // D1 cutoff = BAR_NS; session ends at 2*BAR_NS so exactly one full
        // bar is walked. Construct a single huge representative price whose
        // displacement/span product deliberately exceeds i64::MAX: signed_u6
        // ~= i64::MAX/2 held ABOVE for a full bar (60_000 ms) -> area ~=
        // (i64::MAX/2) * 60_000, far past i64::MAX.
        let huge_price = i64::MAX / 2 + 1;
        let frame = SessionFrame::from_parts_for_test(
            0,
            2 * BAR_NS,
            vec![BAR_NS],
            vec![huge_price],
            vec![huge_price],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        let result = compute_dwell(&frame, &s, &row);
        assert_eq!(result.retained_area_u6ms, None);
    }

    // ------------------------- AMBIGUOUS_CLOSE (heterogeneous representative) -------------------------

    #[test]
    fn heterogeneous_representative_bar_is_ambiguous_close_not_a_guess() {
        // D1 cutoff = BAR_NS; the sole group sits exactly at cutoff and is
        // Heterogeneous (multiple distinct scientific midpoints at that
        // millisecond) — no fabricated single close, typed AMBIGUOUS_CLOSE.
        let frame = SessionFrame::from_parts_for_test(
            0,
            2 * BAR_NS,
            vec![BAR_NS],
            vec![990_000],
            vec![1_010_000],
            vec![GroupKind::Heterogeneous],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        let result = compute_dwell(&frame, &s, &row);
        assert_eq!(result.ambiguous_close_bars, 1);
        assert_eq!(result.above_ns, 0);
        assert_eq!(result.below_ns, 0);
        assert_eq!(result.at_ns, 0);
    }

    // ------------------------- SOURCE_CENSORED whole-window NO_QUOTE -------------------------

    #[test]
    fn source_censored_window_resolves_every_bar_to_no_quote() {
        // Two groups both strictly before the window opens; the window
        // itself (cutoff onward) contains zero scientific groups at all.
        let frame = SessionFrame::from_parts_for_test(
            0,
            5 * BAR_NS,
            vec![0, 1],
            vec![100, 100],
            vec![100, 100],
            vec![GroupKind::Scalar; 2],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let row = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        assert_eq!(row.window_frontier, WindowFrontier::SourceCensored);
        let result = compute_dwell(&frame, &s, &row);
        // 4 bars from BAR_NS to 5*BAR_NS, all NO_QUOTE.
        assert_eq!(result.no_quote_bars, 4);
        assert_eq!(result.above_ns, 0);
        assert_eq!(result.below_ns, 0);
        assert_eq!(result.at_ns, 0);
        assert_eq!(result.retained_area_u6ms, Some(0));
    }
}
