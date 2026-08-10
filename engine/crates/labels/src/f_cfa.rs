//! F-CFA — act-now/wait-one/wait-two/pass counterfactual atoms. Design
//! authority: `docs/specs/events3_design_amendment_v2.md` §A4 (F4) "F-CFA
//! real counterfactuals" (wins all conflicts with
//! `docs/specs/events3_formula_addendum_v1.md` §5 and
//! `docs/specs/events3_design_v1.md` §A "F-CFA") and
//! `docs/specs/family_schemas/f_cfa_schema_v1.md` (exact column list, written
//! first, includes the recorded escalations below).
//!
//! Row shape (a deviation from the standard D1/D2/D3-only convention): **four
//! rows per signal** — `D1` (act-now), `D2` (wait-one), `D3` (wait-two), and
//! `PASS` (never act), contiguous, `PASS` last. `PASS`'s common-prefix fields
//! (everything except the `slot` column itself) are D1's own, verbatim — see
//! the schema doc's recorded escalation on this point.
//!
//! Complexity per signal: O(log n) for each of D1/D2/D3's own terminal-group
//! lookup (a direct re-derivation of F-TERM's CLOSE-horizon algorithm against
//! shared [`SessionFrame`] primitives — no new *scan*, matching the design
//! doc's "pure `ExtremaTree` derivations" framing) plus O(log n) for each of the
//! two wait-atom transitions (one [`crate::extrema::ExtremaTree`] range query
//! per side). Four rows × O(log n) per signal, `n` = `frame.group_count()`.

use crate::anchor::{Side, SignalSeed, Slot, SlotRow, WindowFrontier};
use crate::frame::{GroupKind, SessionFrame};
use std::fs::File;
use std::io::{self, BufWriter, Write};
use std::path::Path;

/// The full `f_cfa.tsv` header: the ten-column common prefix followed by the
/// thirteen F-CFA value columns, in the exact order pinned by
/// `docs/specs/family_schemas/f_cfa_schema_v1.md` "Value columns".
pub const HEADER: &str = "day\tsignal_id\tslot\tseed_bar_ordinal\tcutoff_ts_ns\tslot_available\tvisible_at_slot\twindow_left\twindow_end\twindow_frontier\tslot_price_lo_u6\tslot_price_hi_u6\tslot_price_group_kind\tterm_close_price_lo_u6\tterm_close_price_hi_u6\tterm_close_group_kind\tterm_close_state\tact_lo_u6\tact_hi_u6\tact_state\twait_forgone_fav_u6\twait_avoided_adv_u6\twait_state";

// --------------------------- typed states ---------------------------

/// The CLOSE-horizon terminal group's own availability/censor state
/// (`f_cfa_schema_v1.md` "Reference terminal interval"). Mirrors F-TERM's
/// per-horizon state set exactly; `CloseTruncated` is reserved and never
/// constructed here (this family's own nominal end is always
/// `session_end_ns` identically, so the truncation trigger never fires —
/// matching `crate::f_ord::OrdState::NeitherCloseTruncated`'s precedent).
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum TerminalState {
    Attained,
    WideBreaker,
    #[allow(
        dead_code,
        reason = "reserved: this family's nominal end is always session_end_ns \
                  identically, so the truncation trigger never fires and this \
                  variant is never constructed — kept so the wire vocabulary \
                  matches F-TERM's CLOSE horizon and any match stays schema-complete"
    )]
    CloseTruncated,
    SourceCensored,
    /// The row's own common prefix is `DECISION_UNAVAILABLE`/`NOT_VISIBLE`.
    Na,
}

impl TerminalState {
    const fn wire(self) -> &'static str {
        match self {
            Self::Attained => "ATTAINED",
            Self::WideBreaker => "WIDE_BREAKER",
            Self::CloseTruncated => "CLOSE_TRUNCATED",
            Self::SourceCensored => "SOURCE_CENSORED",
            Self::Na => "NA",
        }
    }
}

/// The act value's own state (`f_cfa_schema_v1.md` "Act value"): mirrors
/// [`TerminalState`] verbatim for `D1`/`D2`/`D3` rows (an act value is
/// computable exactly when the terminal interval is), plus the `PASS`-only
/// constant `Pass`.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum ActState {
    Attained,
    WideBreaker,
    CloseTruncated,
    SourceCensored,
    Na,
    /// The `PASS` row only: `act_lo_u6 = act_hi_u6 = 0` unconditionally.
    Pass,
}

impl ActState {
    const fn wire(self) -> &'static str {
        match self {
            Self::Attained => "ATTAINED",
            Self::WideBreaker => "WIDE_BREAKER",
            Self::CloseTruncated => "CLOSE_TRUNCATED",
            Self::SourceCensored => "SOURCE_CENSORED",
            Self::Na => "NA",
            Self::Pass => "PASS",
        }
    }

    const fn from_terminal(state: TerminalState) -> Self {
        match state {
            TerminalState::Attained => Self::Attained,
            TerminalState::WideBreaker => Self::WideBreaker,
            TerminalState::CloseTruncated => Self::CloseTruncated,
            TerminalState::SourceCensored => Self::SourceCensored,
            TerminalState::Na => Self::Na,
        }
    }
}

/// The wait atom's own state (`f_cfa_schema_v1.md` "Wait atoms").
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum WaitState {
    Attained,
    /// A breaker starts strictly between the two cutoffs (A4: "never a
    /// resumed-path value").
    WaitCensored,
    /// The range `[left_k, left_{k+1})` is empty with no intervening
    /// breaker (recorded escalation — see the schema doc).
    SourceCensored,
    /// Either slot of the transition is `DECISION_UNAVAILABLE`/`NOT_VISIBLE`,
    /// or this row has no "next slot" (`D3`, `PASS`).
    Na,
}

impl WaitState {
    const fn wire(self) -> &'static str {
        match self {
            Self::Attained => "ATTAINED",
            Self::WaitCensored => "WAIT_CENSORED",
            Self::SourceCensored => "SOURCE_CENSORED",
            Self::Na => "NA",
        }
    }
}

// --------------------------- value computation ---------------------------

/// The CLOSE-horizon terminal group for one row's own window (`f_cfa_schema_v1.md`
/// "Reference terminal interval"): re-derives F-TERM's own `CLOSE`-horizon
/// algorithm directly against shared [`SessionFrame`] primitives (F-TERM's
/// per-horizon function is private to its module, so this is the same O(log
/// n) end-position descent, not a new scan).
#[derive(Clone, Copy, Debug)]
struct TermClose {
    price_lo: Option<i64>,
    price_hi: Option<i64>,
    group_kind: Option<GroupKind>,
    state: TerminalState,
}

impl TermClose {
    const fn na() -> Self {
        Self {
            price_lo: None,
            price_hi: None,
            group_kind: None,
            state: TerminalState::Na,
        }
    }

    fn format(&self) -> String {
        match (self.price_lo, self.price_hi, self.group_kind) {
            (Some(lo), Some(hi), Some(kind)) => {
                format!("{lo}\t{hi}\t{}\t{}", kind.wire(), self.state.wire())
            }
            _ => format!("NA\tNA\tNA\t{}", self.state.wire()),
        }
    }
}

/// Computes the CLOSE-horizon terminal group for a window starting at
/// `window_left` (a valid group index or `frame.group_count()`) with cutoff
/// `cutoff_ts_ns`: the LAST scientific group with `ts_ns < min(session_end_ns,
/// first_breaker_start_after(cutoff))` and index `>= window_left`
/// (`f_cfa_schema_v1.md` "Reference terminal interval"; identical to
/// F-TERM's own `CLOSE` horizon, `label_probe_schema_v1.md` "`f_term.tsv`").
///
/// O(log n): one [`SessionFrame::first_breaker_start_after`] descent plus one
/// [`SessionFrame::end_position`] descent.
fn terminal_close(frame: &SessionFrame, window_left: usize, cutoff_ts_ns: i64) -> TermClose {
    let session_end_ns = frame.session_end_ns;
    let breaker_start = frame.first_breaker_start_after(cutoff_ts_ns);
    let bound = breaker_start.map_or(session_end_ns, |start| start.min(session_end_ns));
    let terminal_end_position = frame.end_position(bound);

    if terminal_end_position <= window_left {
        return TermClose {
            price_lo: None,
            price_hi: None,
            group_kind: None,
            state: TerminalState::SourceCensored,
        };
    }
    let idx = terminal_end_position - 1;
    // `nominal_end_ns` (session_end_ns) is never > `frame.session_end_ns`
    // for this family, so `CLOSE_TRUNCATED` never triggers here (reserved).
    let state = if breaker_start.is_some_and(|start| start < session_end_ns) {
        TerminalState::WideBreaker
    } else {
        TerminalState::Attained
    };
    TermClose {
        price_lo: Some(frame.m_lo[idx]),
        price_hi: Some(frame.m_hi[idx]),
        group_kind: Some(frame.kind[idx]),
        state,
    }
}

/// The causal slot price (`f_cfa_schema_v1.md` "Causal slot price" / A4): the
/// `window_left` group's `m_lo`/`m_hi`, or `None` if `window_left ==
/// frame.group_count()` (no scientific group exists at/after cutoff at all).
///
/// O(1).
fn slot_price_at(frame: &SessionFrame, window_left: usize) -> Option<(i64, i64, GroupKind)> {
    if window_left >= frame.group_count() {
        None
    } else {
        Some((
            frame.m_lo[window_left],
            frame.m_hi[window_left],
            frame.kind[window_left],
        ))
    }
}

/// The act value (`f_cfa_schema_v1.md` "Act value" / A4 exact rewrite):
/// `dir · (endpoint − slot_price)` as signed interval subtraction, with **no
/// max-with-zero flooring** — computable exactly when both `slot_price` and
/// `term`'s price exist (a missing `slot_price` always implies `term.state ==
/// SOURCE_CENSORED` too, so `term.state` alone determines `act_state`).
///
/// O(1).
fn act_from(
    side: Side,
    slot_price: Option<(i64, i64, GroupKind)>,
    term: &TermClose,
) -> (Option<i64>, Option<i64>, ActState) {
    match (slot_price, term.price_lo, term.price_hi) {
        (Some((slot_lo, slot_hi, _)), Some(term_lo), Some(term_hi)) => {
            let (lo, hi) = match side {
                Side::Low => (term_lo - slot_hi, term_hi - slot_lo),
                Side::High => (slot_lo - term_hi, slot_hi - term_lo),
            };
            (Some(lo), Some(hi), ActState::from_terminal(term.state))
        }
        _ => (None, None, ActState::from_terminal(term.state)),
    }
}

/// One row's full set of F-CFA value fields (everything except the wait
/// atom, which is transition-level, not row-level).
struct RowValues {
    slot_price: Option<(i64, i64, GroupKind)>,
    term: TermClose,
    act_lo: Option<i64>,
    act_hi: Option<i64>,
    act_state: ActState,
}

impl RowValues {
    const fn na() -> Self {
        Self {
            slot_price: None,
            term: TermClose::na(),
            act_lo: None,
            act_hi: None,
            act_state: ActState::Na,
        }
    }

    /// Formats the ten non-wait value columns: `slot_price_lo_u6
    /// slot_price_hi_u6 slot_price_group_kind term_close_price_lo_u6
    /// term_close_price_hi_u6 term_close_group_kind term_close_state
    /// act_lo_u6 act_hi_u6 act_state`.
    fn format(&self) -> String {
        let (sp_lo, sp_hi, sp_kind) = match self.slot_price {
            Some((lo, hi, kind)) => (lo.to_string(), hi.to_string(), kind.wire().to_owned()),
            None => ("NA".to_owned(), "NA".to_owned(), "NA".to_owned()),
        };
        let act = match (self.act_lo, self.act_hi) {
            (Some(lo), Some(hi)) => format!("{lo}\t{hi}\t{}", self.act_state.wire()),
            _ => format!("NA\tNA\t{}", self.act_state.wire()),
        };
        format!("{sp_lo}\t{sp_hi}\t{sp_kind}\t{}\t{act}", self.term.format())
    }
}

/// Computes one `D1`/`D2`/`D3` row's [`RowValues`] from its already-computed
/// common prefix (`docs/specs/family_schemas/f_cfa_schema_v1.md`).
///
/// O(log n): one [`terminal_close`] call.
fn row_values(frame: &SessionFrame, seed: &SignalSeed, prefix: &SlotRow) -> RowValues {
    if matches!(
        prefix.window_frontier,
        WindowFrontier::DecisionUnavailable | WindowFrontier::NotVisible
    ) {
        return RowValues::na();
    }
    let window_left = prefix
        .window_left
        .expect("window_left present when slot available and visible");
    let slot_price = slot_price_at(frame, window_left);
    let term = terminal_close(frame, window_left, prefix.cutoff_ts_ns);
    let (act_lo, act_hi, act_state) = act_from(seed.extreme_side, slot_price, &term);
    RowValues {
        slot_price,
        term,
        act_lo,
        act_hi,
        act_state,
    }
}

/// Computes the `PASS` row's [`RowValues`] (`f_cfa_schema_v1.md` "Row shape"
/// and "Act value"): `slot_price` is always absent (passing never enters);
/// `term_close_*` follows D1's own availability exactly; both act bounds are
/// pinned to zero and `act_state = PASS` **unconditionally** (A4: "PASS = 0
/// exactly", stated with no attached condition).
fn pass_row_values(frame: &SessionFrame, d1: &SlotRow) -> RowValues {
    let term = if matches!(
        d1.window_frontier,
        WindowFrontier::DecisionUnavailable | WindowFrontier::NotVisible
    ) {
        TermClose::na()
    } else {
        let window_left = d1
            .window_left
            .expect("window_left present when slot available and visible");
        terminal_close(frame, window_left, d1.cutoff_ts_ns)
    };
    RowValues {
        slot_price: None,
        term,
        act_lo: Some(0),
        act_hi: Some(0),
        act_state: ActState::Pass,
    }
}

/// One wait-atom transition's result (`f_cfa_schema_v1.md` "Wait atoms").
struct WaitResult {
    forgone: Option<i64>,
    avoided: Option<i64>,
    state: WaitState,
}

impl WaitResult {
    const fn na() -> Self {
        Self {
            forgone: None,
            avoided: None,
            state: WaitState::Na,
        }
    }

    const fn wait_censored() -> Self {
        Self {
            forgone: None,
            avoided: None,
            state: WaitState::WaitCensored,
        }
    }

    const fn source_censored() -> Self {
        Self {
            forgone: None,
            avoided: None,
            state: WaitState::SourceCensored,
        }
    }

    /// Formats the three wait-atom columns: `wait_forgone_fav_u6
    /// wait_avoided_adv_u6 wait_state`.
    fn format(&self) -> String {
        match (self.forgone, self.avoided) {
            (Some(f), Some(a)) => format!("{f}\t{a}\t{}", self.state.wire()),
            _ => format!("NA\tNA\t{}", self.state.wire()),
        }
    }
}

/// Computes the wait atom for the transition from slot `k` (`row_k`) to slot
/// `k+1` (`row_k1`) (`f_cfa_schema_v1.md` "Wait atoms" / A4 range clamp +
/// addendum v1 §5 formula, using `P` directly, not `slot_price`).
///
/// O(log n): one [`SessionFrame::first_breaker_start_after`] descent plus, in
/// the non-censored case, two [`crate::extrema::ExtremaTree`] range queries.
fn wait_atom(
    frame: &SessionFrame,
    seed: &SignalSeed,
    row_k: &SlotRow,
    row_k1: &SlotRow,
) -> WaitResult {
    if matches!(
        row_k.window_frontier,
        WindowFrontier::DecisionUnavailable | WindowFrontier::NotVisible
    ) {
        return WaitResult::na();
    }
    if matches!(
        row_k1.window_frontier,
        WindowFrontier::DecisionUnavailable | WindowFrontier::NotVisible
    ) {
        return WaitResult::na();
    }
    let left_k = row_k
        .window_left
        .expect("window_left present when slot available and visible");
    let left_k1 = row_k1
        .window_left
        .expect("window_left present when slot available and visible");

    let breaker_start = frame.first_breaker_start_after(row_k.cutoff_ts_ns);
    if breaker_start.is_some_and(|start| start < row_k1.cutoff_ts_ns) {
        return WaitResult::wait_censored();
    }
    if left_k >= left_k1 {
        return WaitResult::source_censored();
    }

    let last = left_k1 - 1;
    let tree = frame.extrema();
    let (fav_value, adv_value) = match seed.extreme_side {
        Side::Low => (
            tree.range_max(left_k, last).value,
            tree.range_min(left_k, last).value,
        ),
        Side::High => (
            tree.range_min(left_k, last).value,
            tree.range_max(left_k, last).value,
        ),
    };
    let p = seed.pivot_price_u6;
    let (forgone, avoided) = match seed.extreme_side {
        Side::Low => ((fav_value - p).max(0), (p - adv_value).max(0)),
        Side::High => ((p - fav_value).max(0), (adv_value - p).max(0)),
    };
    WaitResult {
        forgone: Some(forgone),
        avoided: Some(avoided),
        state: WaitState::Attained,
    }
}

// --------------------------- PASS row prefix ---------------------------

/// Hex-encodes a 32-byte digest as 64 lowercase hex characters — a local
/// reimplementation of `crate::anchor`'s private helper of the same shape
/// (that module's own is not `pub`, so it cannot be called from here); kept
/// in lock-step with the schema's "Digests: 64 lowercase hex chars" rule.
fn hex32(digest: &[u8; 32]) -> String {
    use std::fmt::Write as _;
    digest
        .iter()
        .fold(String::with_capacity(64), |mut out, byte| {
            write!(out, "{byte:02x}").expect("writing to a String cannot fail");
            out
        })
}

const fn bool_wire(value: bool) -> &'static str {
    if value { "true" } else { "false" }
}

fn opt_usize_wire(value: Option<usize>) -> String {
    value.map_or_else(|| "NA".to_owned(), |v| v.to_string())
}

/// Formats the `PASS` row's common prefix (`f_cfa_schema_v1.md` "Row shape" /
/// "Common prefix"): identical to `d1`'s own ten fields, with the `slot`
/// column overwritten to the literal `PASS` (a fourth wire value legal only
/// in this family's file, per the schema doc).
fn format_pass_prefix(day: &str, d1: &SlotRow) -> String {
    format!(
        "{day}\t{}\tPASS\t{}\t{}\t{}\t{}\t{}\t{}\t{}",
        hex32(&d1.signal_id),
        d1.seed_bar_ordinal,
        d1.cutoff_ts_ns,
        bool_wire(d1.slot_available),
        bool_wire(d1.visible_at_slot),
        opt_usize_wire(d1.window_left),
        opt_usize_wire(d1.window_end),
        d1.window_frontier.wire(),
    )
}

// --------------------------- write_tsv ---------------------------

/// Writes `f_cfa.tsv` for one session: **four** rows per signal, in order
/// `D1, D2, D3, PASS` (signal-major, slot-minor, `PASS` last — a deviation
/// from the standard three-row convention, `f_cfa_schema_v1.md` "Row shape"),
/// signals in the order given by `seeds` (`day_signals.tsv` publication
/// order).
///
/// O(`seeds.len()` × 4 rows), each O(log n); `n` = `frame.group_count()`.
///
/// # Errors
///
/// Returns an [`io::Error`] if `out_path` cannot be created or written.
/// Computes every signal's four rows (`D1, D2, D3, PASS` — this family's own
/// deviation from the standard three-row convention,
/// `f_cfa_schema_v1.md` "Row shape") as tab-joined lines, no header, no
/// trailing newline, signals in the order given by `seeds`
/// (`day_signals.tsv` publication order). Reusable in-memory (e.g. for
/// parquet publication) without going through [`write_tsv`]'s file.
///
/// O(`seeds.len()` × 4 rows), each O(log n); `n` = `frame.group_count()`.
#[must_use]
pub fn rows(frame: &SessionFrame, seeds: &[SignalSeed]) -> Vec<String> {
    let mut out = Vec::with_capacity(seeds.len() * 4);
    for seed in seeds {
        let d1 = SlotRow::compute(frame, seed, Slot::D1, frame.session_end_ns);
        let d2 = SlotRow::compute(frame, seed, Slot::D2, frame.session_end_ns);
        let d3 = SlotRow::compute(frame, seed, Slot::D3, frame.session_end_ns);

        let d1_values = row_values(frame, seed, &d1);
        let d2_values = row_values(frame, seed, &d2);
        let d3_values = row_values(frame, seed, &d3);

        let wait_d1_d2 = wait_atom(frame, seed, &d1, &d2);
        let wait_d2_d3 = wait_atom(frame, seed, &d2, &d3);

        out.push(format!(
            "{}\t{}\t{}",
            d1.format_prefix(frame.day),
            d1_values.format(),
            wait_d1_d2.format()
        ));
        out.push(format!(
            "{}\t{}\t{}",
            d2.format_prefix(frame.day),
            d2_values.format(),
            wait_d2_d3.format()
        ));
        out.push(format!(
            "{}\t{}\t{}",
            d3.format_prefix(frame.day),
            d3_values.format(),
            WaitResult::na().format()
        ));

        let pass_values = pass_row_values(frame, &d1);
        out.push(format!(
            "{}\t{}\t{}",
            format_pass_prefix(frame.day, &d1),
            pass_values.format(),
            WaitResult::na().format()
        ));
    }
    out
}

/// Writes `f_cfa.tsv` for every signal's four rows ([`rows`]).
///
/// # Errors
///
/// Returns an [`io::Error`] if `out_path` cannot be created or written.
pub fn write_tsv(frame: &SessionFrame, seeds: &[SignalSeed], out_path: &Path) -> io::Result<()> {
    let mut out = BufWriter::new(File::create(out_path)?);
    writeln!(out, "{HEADER}")?;
    for line in rows(frame, seeds) {
        writeln!(out, "{line}")?;
    }
    out.flush()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::frame::Breaker;

    const BAR_NS: i64 = 60_000_000_000;

    fn seed(
        side: Side,
        pivot_last_bar_ordinal: u64,
        causal_visible_ts_ns: i64,
        pivot_price_u6: i64,
    ) -> SignalSeed {
        SignalSeed {
            signal_id: [0x77; 32],
            extreme_side: side,
            pivot_price_u6,
            pivot_last_bar_ordinal,
            causal_visible_ts_ns,
        }
    }

    fn temp_out_path(name: &str) -> std::path::PathBuf {
        std::env::temp_dir().join(format!("f_cfa_test_{}_{name}.tsv", std::process::id()))
    }

    // ------------------------- header shape -------------------------

    #[test]
    fn header_has_the_exact_expected_column_count() {
        let columns: Vec<&str> = HEADER.split('\t').collect();
        // 10 common-prefix columns + 13 value columns.
        assert_eq!(columns.len(), 23);
        assert_eq!(columns[9], "window_frontier");
        assert_eq!(columns[10], "slot_price_lo_u6");
        assert_eq!(columns[13], "term_close_price_lo_u6");
        assert_eq!(columns[17], "act_lo_u6");
        assert_eq!(columns[20], "wait_forgone_fav_u6");
        assert_eq!(columns[22], "wait_state");
    }

    #[test]
    fn write_tsv_emits_four_rows_per_signal_in_order() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            10 * BAR_NS,
            vec![0, BAR_NS, 9 * BAR_NS],
            vec![100, 100, 100],
            vec![100, 100, 100],
            vec![GroupKind::Scalar; 3],
            Vec::new(),
        );
        let seeds = vec![seed(Side::Low, 0, 0, 1_000_000)];
        let path = temp_out_path("four_rows");
        write_tsv(&frame, &seeds, &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        std::fs::remove_file(&path).ok();

        let mut lines = content.lines();
        assert_eq!(lines.next(), Some(HEADER));
        let d1 = lines.next().expect("D1 row");
        let d2 = lines.next().expect("D2 row");
        let d3 = lines.next().expect("D3 row");
        let pass = lines.next().expect("PASS row");
        assert_eq!(lines.next(), None);

        assert!(d1.contains("\tD1\t"));
        assert!(d2.contains("\tD2\t"));
        assert!(d3.contains("\tD3\t"));
        assert!(pass.contains("\tPASS\t"));
        assert_eq!(d1.split('\t').count(), 23);
        assert_eq!(pass.split('\t').count(), 23);
    }

    // --------------------- edge test: short-side sign correctness ---------------------

    #[test]
    fn high_origin_favorable_down_gain_is_positive_act_value() {
        // Side::High: dir=-1, favorable=DOWN. P = 1_000_000. Slot price
        // (D1's own window_left group) = 999_000; the CLOSE terminal group
        // sits at 990_000 (price fell further: favorable for a short).
        let session_end_ns = 10 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![0, BAR_NS, 9 * BAR_NS],
            vec![999_999, 999_000, 990_000],
            vec![999_999, 999_000, 990_000],
            vec![GroupKind::Scalar; 3],
            Vec::new(),
        );
        let s = seed(Side::High, 0, 0, 1_000_000); // D1 cutoff = BAR_NS.
        let d1 = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        assert_eq!(d1.window_left, Some(1)); // g1 (999_000) is window_left.
        let values = row_values(&frame, &s, &d1);

        // slot_price = (999_000, 999_000); terminal = (990_000, 990_000).
        // act_lo = slot_lo - term_hi = 999_000 - 990_000 = 9_000.
        // act_hi = slot_hi - term_lo = 999_000 - 990_000 = 9_000.
        assert_eq!(values.act_lo, Some(9_000));
        assert_eq!(values.act_hi, Some(9_000));
        assert!(
            values.act_lo.unwrap() > 0,
            "a HIGH-origin favorable move must be a POSITIVE act value (shorts keep gains)"
        );
        assert_eq!(values.act_state, ActState::Attained);
    }

    // --------------------- edge test: breaker between D1 and D2 ---------------------

    #[test]
    fn breaker_between_d1_and_d2_yields_wait_censored() {
        let session_end_ns = 20 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![0],
            vec![100],
            vec![100],
            vec![GroupKind::Scalar],
            vec![Breaker {
                start_ns: BAR_NS + 1, // strictly after D1 cutoff (BAR_NS)
                end_ns: BAR_NS + 2,   // strictly before D2 cutoff (2*BAR_NS)
            }],
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let d1 = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        let d2 = SlotRow::compute(&frame, &s, Slot::D2, frame.session_end_ns);
        assert!(!matches!(
            d1.window_frontier,
            WindowFrontier::DecisionUnavailable | WindowFrontier::NotVisible
        ));
        assert!(!matches!(
            d2.window_frontier,
            WindowFrontier::DecisionUnavailable | WindowFrontier::NotVisible
        ));

        let wait = wait_atom(&frame, &s, &d1, &d2);
        assert_eq!(wait.state, WaitState::WaitCensored);
        assert_eq!(wait.forgone, None);
        assert_eq!(wait.avoided, None);
    }

    // --------------------- edge test: slot unavailable rows ---------------------

    #[test]
    fn slot_unavailable_rows_are_all_na_but_pass_act_stays_unconditional() {
        // session_end at 3 bars; seed_bar_ordinal = 1 => D1 cutoff = 2*BAR_NS
        // (available), D2 cutoff = 3*BAR_NS == session_end (DECISION_UNAVAILABLE),
        // D3 cutoff = 4*BAR_NS (DECISION_UNAVAILABLE too).
        let session_end_ns = 3 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![0, BAR_NS],
            vec![100, 100],
            vec![100, 100],
            vec![GroupKind::Scalar; 2],
            Vec::new(),
        );
        let s = seed(Side::Low, 1, 0, 1_000_000);
        let path = temp_out_path("slot_unavailable");
        write_tsv(&frame, std::slice::from_ref(&s), &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        std::fs::remove_file(&path).ok();
        let mut lines = content.lines();
        lines.next(); // header
        let d1 = lines.next().expect("D1 row");
        let d2 = lines.next().expect("D2 row");
        let d3 = lines.next().expect("D3 row");
        let pass = lines.next().expect("PASS row");

        let d2_cols: Vec<&str> = d2.split('\t').collect();
        assert_eq!(d2_cols[9], "DECISION_UNAVAILABLE");
        // Every one of the 13 value columns is NA on D2.
        assert!(d2_cols[10..].iter().all(|&c| c == "NA"));

        let d3_cols: Vec<&str> = d3.split('\t').collect();
        assert_eq!(d3_cols[9], "DECISION_UNAVAILABLE");
        assert!(d3_cols[10..].iter().all(|&c| c == "NA"));

        // D1 is available, but its wait-to-D2 atom is NA because D2 (the
        // transition's far slot) is itself DECISION_UNAVAILABLE.
        let d1_cols: Vec<&str> = d1.split('\t').collect();
        assert_ne!(d1_cols[9], "DECISION_UNAVAILABLE");
        assert_eq!(d1_cols[22], "NA"); // wait_state

        // PASS reuses D1's (available) common prefix, so term_close_state is
        // populated, but act stays 0/0/PASS regardless.
        let pass_cols: Vec<&str> = pass.split('\t').collect();
        assert_eq!(pass_cols[2], "PASS");
        assert_ne!(pass_cols[9], "DECISION_UNAVAILABLE");
        assert_eq!(pass_cols[17], "0"); // act_lo_u6
        assert_eq!(pass_cols[18], "0"); // act_hi_u6
        assert_eq!(pass_cols[19], "PASS"); // act_state
    }

    #[test]
    fn pass_act_is_zero_even_when_d1_itself_is_decision_unavailable() {
        // A session so short that even D1 is unavailable.
        let session_end_ns = BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![0],
            vec![100],
            vec![100],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000); // D1 cutoff == session_end_ns.
        let d1 = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        assert_eq!(d1.window_frontier, WindowFrontier::DecisionUnavailable);

        let pass_values = pass_row_values(&frame, &d1);
        assert_eq!(pass_values.act_lo, Some(0));
        assert_eq!(pass_values.act_hi, Some(0));
        assert_eq!(pass_values.act_state, ActState::Pass);
        // term_close is NA here since D1 itself is unavailable.
        assert_eq!(pass_values.term.state, TerminalState::Na);
    }

    // --------------------- edge test: interval typing from heterogeneous groups ---------------------

    #[test]
    fn heterogeneous_slot_and_terminal_groups_yield_a_non_degenerate_act_interval() {
        // Side::Low (dir=+1). slot_price group (window_left) is
        // Heterogeneous [990, 1010]; the CLOSE terminal group is also
        // Heterogeneous [1100, 1150].
        let session_end_ns = 10 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![0, BAR_NS, 9 * BAR_NS],
            vec![500, 990, 1100],
            vec![500, 1010, 1150],
            vec![
                GroupKind::Scalar,
                GroupKind::Heterogeneous,
                GroupKind::Heterogeneous,
            ],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 700); // D1 cutoff = BAR_NS => window_left = 1.
        let d1 = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        assert_eq!(d1.window_left, Some(1));
        let values = row_values(&frame, &s, &d1);

        assert_eq!(
            values.slot_price,
            Some((990, 1010, GroupKind::Heterogeneous))
        );
        assert_eq!(values.term.price_lo, Some(1100));
        assert_eq!(values.term.price_hi, Some(1150));
        assert_eq!(values.term.group_kind, Some(GroupKind::Heterogeneous));

        // act_lo = term_lo - slot_hi = 1100 - 1010 = 90.
        // act_hi = term_hi - slot_lo = 1150 - 990 = 160.
        assert_eq!(values.act_lo, Some(90));
        assert_eq!(values.act_hi, Some(160));
        assert!(
            values.act_lo.unwrap() < values.act_hi.unwrap(),
            "a heterogeneous-group act value must be a genuine (non-degenerate) interval"
        );

        let formatted = values.format();
        let cols: Vec<&str> = formatted.split('\t').collect();
        assert_eq!(cols[2], "HETEROGENEOUS"); // slot_price_group_kind
        assert_eq!(cols[5], "HETEROGENEOUS"); // term_close_group_kind
    }

    // --------------------- wait atom: normal ATTAINED case ---------------------

    #[test]
    fn wait_atom_hand_computed_forgone_and_avoided() {
        // Side::Low, P = 1_000_000. Range [1,3) covers two groups:
        // g1 (m_lo=999_900, m_hi=1_000_300), g2 (m_lo=999_700, m_hi=1_000_100).
        let session_end_ns = 20 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![0, BAR_NS, BAR_NS + 30_000_000_000, 2 * BAR_NS, 5 * BAR_NS],
            vec![999_999, 999_900, 999_700, 1_000_000, 999_999],
            vec![999_999, 1_000_300, 1_000_100, 1_000_000, 999_999],
            vec![GroupKind::Scalar; 5],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let d1 = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        let d2 = SlotRow::compute(&frame, &s, Slot::D2, frame.session_end_ns);
        assert_eq!(d1.window_left, Some(1));
        assert_eq!(d2.window_left, Some(3));

        let wait = wait_atom(&frame, &s, &d1, &d2);
        assert_eq!(wait.state, WaitState::Attained);
        // fav_extreme = max(hi[1..=2]) = 1_000_300. forgone = 300.
        assert_eq!(wait.forgone, Some(300));
        // adv_extreme = min(lo[1..=2]) = 999_700. avoided = 300.
        assert_eq!(wait.avoided, Some(300));
    }

    #[test]
    fn wait_atom_empty_range_without_breaker_is_source_censored() {
        // No group falls in [cutoff_D1, cutoff_D2) = [BAR_NS, 2*BAR_NS); the
        // only groups are at ts=0 (before) and ts=5*BAR_NS (well after), and
        // there is no breaker at all.
        let session_end_ns = 20 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![0, 5 * BAR_NS],
            vec![100, 100],
            vec![100, 100],
            vec![GroupKind::Scalar; 2],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let d1 = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        let d2 = SlotRow::compute(&frame, &s, Slot::D2, frame.session_end_ns);
        assert_eq!(d1.window_left, d2.window_left); // both point at g1.

        let wait = wait_atom(&frame, &s, &d1, &d2);
        assert_eq!(wait.state, WaitState::SourceCensored);
        assert_eq!(wait.forgone, None);
        assert_eq!(wait.avoided, None);
    }

    #[test]
    fn wait_atom_na_when_the_far_slot_is_decision_unavailable() {
        // D1 available, D2 unavailable (session ends before D2's cutoff).
        let session_end_ns = 3 * BAR_NS / 2; // 1.5 bars: D1 cutoff (1 bar) < it, D2 cutoff (2 bars) does not.
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![0],
            vec![100],
            vec![100],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let d1 = SlotRow::compute(&frame, &s, Slot::D1, frame.session_end_ns);
        let d2 = SlotRow::compute(&frame, &s, Slot::D2, frame.session_end_ns);
        assert!(!matches!(
            d1.window_frontier,
            WindowFrontier::DecisionUnavailable
        ));
        assert_eq!(d2.window_frontier, WindowFrontier::DecisionUnavailable);

        let wait = wait_atom(&frame, &s, &d1, &d2);
        assert_eq!(wait.state, WaitState::Na);
    }

    #[test]
    fn d3_and_pass_rows_always_carry_na_wait_atoms_via_write_tsv() {
        let frame = SessionFrame::from_parts_for_test(
            0,
            20 * BAR_NS,
            vec![0, BAR_NS],
            vec![100, 100],
            vec![100, 100],
            vec![GroupKind::Scalar; 2],
            Vec::new(),
        );
        let seeds = vec![seed(Side::Low, 0, 0, 1_000_000)];
        let path = temp_out_path("d3_pass_wait_na");
        write_tsv(&frame, &seeds, &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        std::fs::remove_file(&path).ok();
        let mut lines = content.lines();
        lines.next();
        lines.next(); // D1
        lines.next(); // D2
        let d3 = lines.next().expect("D3 row");
        let pass = lines.next().expect("PASS row");
        let d3_cols: Vec<&str> = d3.split('\t').collect();
        let pass_cols: Vec<&str> = pass.split('\t').collect();
        assert_eq!(d3_cols[20], "NA");
        assert_eq!(d3_cols[22], "NA");
        assert_eq!(pass_cols[20], "NA");
        assert_eq!(pass_cols[22], "NA");
    }
}
