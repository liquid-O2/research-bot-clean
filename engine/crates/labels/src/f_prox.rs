//! F-PROX — truth-relative proximity family (**OUTCOME-ONLY**). Design
//! authority: `docs/specs/events3_design_v1.md` §A ("F-PROX"),
//! `docs/specs/events3_formula_addendum_v1.md` §6, REWRITTEN in full by
//! `docs/specs/events3_design_amendment_v2.md` §A2 (action-slot clock), §A3
//! (join plan + relation multiplicity), §A7 (captured-opportunity fraction)
//! — **the amendment wins every conflict** with the other two documents —
//! and the captured-opportunity formula itself CORRECTED again by the
//! amendment's own **ruling E10** ("architect correction, supersedes A7's
//! captured-opportunity formula"): A7's original denominator
//! `dir·(truth_extreme_price − pivot_price)` is degenerate by the exact-key
//! match construction (the related truth's price always equals the
//! signal's `pivot_price_u6`), so E10 replaces both `cap_opp_num_u6` and
//! `cap_opp_den_u6` with `ExtremaTree` range queries that need no truth
//! price at all — see [`cap_opp_fields`]. Schema (write this first, read it
//! before this file): `docs/specs/family_schemas/f_prox_schema_v1.md`
//! (marked `E10-corrected` in its "Captured-opportunity fraction" section).
//!
//! Every published column of this family carries the schema's
//! `outcome_only` flag: F-PROX is barred from candidate construction (the d3
//! amendment) and exists only for post-hoc diagnostic/gate use.
//!
//! Kernel cost per anchor: one `HashMap` lookup (relation resolution, O(1)
//! amortized) plus, for a resolvable `(signal, slot)` row, O(1) bar
//! arithmetic and at most four [`crate::extrema::ExtremaTree`] range queries
//! (E10's `cap_opp` num/den, each a favorable-extreme-over-a-window query)
//! plus two [`crate::frame::SessionFrame::end_position`]/
//! [`crate::frame::SessionFrame::first_breaker_start_after`] descents (the
//! post-plateau window resolution) — every one O(log n). Combined with
//! [`crate::anchor::SlotRow::compute`]'s own O(log n) window resolution,
//! `write_tsv` is O(`seeds.len()` · log n), `n` = `frame.group_count()` — the
//! same order as every other family.

use crate::anchor::{Side, SignalSeed, Slot, SlotRow, WindowFrontier};
use crate::frame::SessionFrame;
use std::collections::HashMap;
use std::fmt::Write as _;
use std::fs::File;
use std::io::{self, BufWriter, Write as _};
use std::path::Path;

/// Registered nanoseconds-per-minute bar duration (CONV §3). Duplicated
/// locally: `crate::anchor`'s own copy is private to that module.
const NANOSECONDS_PER_BAR: i64 = 60_000_000_000;

/// One truth episode's F-PROX-relevant projection, shaped exactly like
/// amendment §A10's promised `truth_relation_projection.parquet` leaf entry
/// ("truth rows (`episode_id`, side, price, continuity, plateau bar/ordinal
/// refs, `anchor_bps`)"). **Not itself derivable from
/// `pubread::AssignmentReader` + `pubread::TruthCoverageReader`'s currently
/// published columns alone** — see [`TruthRelationDay`]'s doc comment for the
/// exact statement of what is and is not derivable today (the infra-wave
/// verification narrowed this considerably from the wave-1 author's
/// original escalation: `plateau_bar_ordinal`/`plateau_end_ts_ns` ARE now
/// derivable from `corpus::SessionData` alone; `truth_extreme_price_u6`
/// still is not).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct EpisodeProjection {
    /// The related truth episode's `truth_coverage.tsv` `episode_id`.
    pub episode_id: [u8; 32],
    /// Raw provenance reference: the matched episode's registered
    /// `truth_coverage.tsv` `plateau_last_group_ordinal` (a **group** index
    /// into the day's COMPLETE ordered group sequence — see the infra-wave
    /// verification below — published verbatim for audit).
    pub plateau_last_group_ordinal: u64,
    /// The plateau's clock resolved to a one-minute bar ordinal (CONV §3),
    /// the value the amendment §A2 arithmetic actually consumes. Derived by
    /// the probe/run layer as `floor((plateau_end_ts_ns - session_start_ns)
    /// / 60e9)` — see [`TruthRelationDay`]'s doc comment.
    pub plateau_bar_ordinal: i64,
    /// The native timestamp of the group at `plateau_last_group_ordinal`
    /// (infra-wave addition, ruling E10): the exact bound the E10-corrected
    /// `cap_opp_den_u6` post-plateau window opens strictly after. Derived by
    /// the probe/run layer from `corpus::SessionData.groups.ts_ns
    /// [plateau_last_group_ordinal]` — see [`TruthRelationDay`]'s doc
    /// comment for the group-ordinal provenance verification.
    pub plateau_end_ts_ns: i64,
    /// The truth episode's registered extreme price (u6), if known. **Not**
    /// published by either pubread reader today (see [`TruthRelationDay`]);
    /// `None` for any signal relation resolved from the two currently
    /// published leaves alone (a real probe/run population always supplies
    /// `None` until the A10 `truth_relation_projection.parquet` leaf
    /// exists). Used only by `truth_price_gap_u6` — the E10-corrected
    /// `cap_opp` columns no longer depend on it at all (that was the whole
    /// point of E10: the old formula's dependence on this exact field was
    /// what made it degenerate by construction).
    pub truth_extreme_price_u6: Option<i64>,
}

/// One signal's resolved relation to the truth-episode population at
/// `anchor_bps = 40` (amendment §A3's join path: `signal_id →
/// assignments.tsv member_signal_ids → related_episode_ids →
/// truth_coverage.tsv episode_id`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SignalRelation {
    /// `relation_count = 0`: no relation edge for this signal.
    NoTruthRelation,
    /// `relation_count = 1`: exactly one related episode; its projection.
    Single(EpisodeProjection),
    /// `relation_count = n > 1` (A3: "never silent first-pick, never row
    /// multiplication" — one row is still emitted, carrying only the count,
    /// no chosen episode's fields).
    MultiRelation { relation_count: u32 },
}

impl SignalRelation {
    /// `relation_count` column value: `0` / `1` / `n`.
    #[must_use]
    const fn relation_count(self) -> u64 {
        match self {
            Self::NoTruthRelation => 0,
            Self::Single(_) => 1,
            Self::MultiRelation { relation_count } => relation_count as u64,
        }
    }

    /// `relation_state` wire string.
    #[must_use]
    const fn wire(self) -> &'static str {
        match self {
            Self::NoTruthRelation => "NO_TRUTH_RELATION",
            Self::Single(_) => "SINGLE_RELATION",
            Self::MultiRelation { .. } => "MULTI_RELATION",
        }
    }
}

/// Per-session, pre-joined truth/relation input to [`write_tsv`] (the task's
/// DATA ACCESS extension to the family signature): a `signal_id`-keyed
/// lookup of each signal's [`SignalRelation`] at `anchor_bps = 40`.
///
/// # Population contract (probe/run layer — NOT built inside this module)
///
/// For one session (day `ordinal`) and the join's fixed `anchor_bps = 40`
/// (amendment §A3):
///
/// 1. **Relation edges** (`signal_id → DEDUPLICATED UNION of
///    related_episode_ids`): stream `pubread::AssignmentReader` over
///    `assignments.tsv`, keeping only rows with `row.anchor_bps == 40 &&
///    row.day == <this day>`. `assignments.tsv` rows are per `(stream,
///    candidate)`, so a `signal_id` legitimately appears in
///    `row.member_signal_ids` across MULTIPLE such rows (e.g. as the sole
///    member of its own `UNMATCHED_EVENT_SCORABLE` candidate AND as a
///    co-member of a different candidate's `DUPLICATE_TIMELY` row) — the
///    registered signal↔episode relation is the stream-independent
///    key-match fact, not a per-row fact, so for every `member_signal_id` in
///    every qualifying row, UNION `row.related_episode_ids` into that
///    signal's accumulated `BTreeSet<[u8; 32]>` (ruling E16, wave-4 P0;
///    serialization is ascending hex, a set-serialization order, never a
///    scientific tie-break).
///    - A `signal_id` with no such row → `SignalRelation::NoTruthRelation`
///      (`relation_count = 0`).
///    - Union size `== 1` → `SignalRelation::Single`, with the one episode's
///      projection (step 2).
///    - Union size `> 1` → `SignalRelation::MultiRelation { relation_count:
///      union size as u32 }` (A3: no episode fields are attached — "never
///      silent first-pick").
///
///    The one-row-per-signal assumption this doc comment previously
///    recorded is STRUCK (ruling E16): it was falsified by the real pinned
///    publication (confirmed via `assignments.tsv` inspection — a signal can
///    be both a self-candidate row's sole member and a different
///    candidate's co-member on the same day at `anchor_bps = 40`) and is no
///    longer assumed or asserted anywhere in the probe/run layer.
///
/// 2. **Episode truth-side fields** (`episode_id →
///    plateau_last_group_ordinal`): stream `pubread::TruthCoverageReader`
///    over `truth_coverage.tsv`, keeping only rows with `row.anchor_bps ==
///    40 && row.day == <this day>`, keyed by `row.episode_id`, giving
///    `plateau_last_group_ordinal` directly.
///
/// 3. **`plateau_bar_ordinal` / `plateau_end_ts_ns` — VERIFIED DERIVABLE
///    (infra-wave provenance verification, narrowing the wave-1 author's
///    original escalation)**: the wave-1 F-PROX author recorded these as an
///    unresolved gap, assuming both required the not-yet-built A10
///    `truth_relation_projection.parquet` leaf. The infra wave traced the
///    archived registered pipeline's `group_ordinal` axis with provenance
///    and established that this assumption was **too pessimistic** for
///    `plateau_end_ts_ns`/`plateau_bar_ordinal` specifically:
///
///    - `compact_adapter.rs::validate_full_group_columns` enforces `ordinal
///      == index` for every group in the day's COMPLETE, unfiltered,
///      ascending-timestamp group sequence (`/workspace/archive/rust/
///      iwm_atlas_v2/src/compact_adapter.rs:730`) — i.e. a "group ordinal"
///      is a plain 0-based row position in that sequence, the exact same
///      sequence `corpus::SessionData.groups` decodes and `labels::probe`'s
///      own `day_groups.tsv` dumps "ALL groups incl. wide-only/unresolved,
///      ascending ts" (`docs/specs/label_probe_schema_v1.md` item 3).
///    - The scientific-path projection RETAINS this original full-sequence
///      ordinal rather than renumbering scientific groups 0..k
///      (`compact_adapter.rs:781`, `scientific.group_ordinal.push(ordinal)`
///      — `ordinal` is the just-validated full-sequence index, not a fresh
///      scientific-only counter).
///    - `build_runs` (`compact_adapter.rs:960-1034`, called from the main
///      compact build path at `compact_adapter.rs:1407`) constructs every
///      `StateRun`'s `first_group_ordinal`/`last_group_ordinal`
///      (`event_input.rs:290-381`) directly from that retained value
///      (`compact_adapter.rs:985,1011,1024`).
///    - `EpisodeFragment::from_run` copies `run.last_group_ordinal()`
///      verbatim into a truth episode's plateau fragments
///      (`episode_book.rs:108-127`), and the adequacy layer's
///      `plateau_last_group_ordinal` (the value that ends up published in
///      `truth_coverage.tsv`) is the `max` over exactly those fragments'
///      `last_group_ordinal()` (`intrabar_event_adequacy.rs:1574-1579`).
///
///    **Verdict: YES — `plateau_last_group_ordinal` indexes the COMPLETE
///    ordered group sequence, i.e. it is exactly a `day_groups.tsv` /
///    `corpus::SessionData.groups` row position (0-based).** Therefore,
///    given the same day's `SessionData` (already loaded by the probe/run
///    layer to build the `SessionFrame` in the first place):
///    `plateau_end_ts_ns = session.groups.ts_ns[plateau_last_group_ordinal
///    as usize]` (the native timestamp of that exact row — the truth-side
///    clock, per CONV §4/§8, is stamped at the plateau's NATIVE timestamp,
///    never the causal-visible `+1ms` convention the signal side uses), and
///    `plateau_bar_ordinal = (plateau_end_ts_ns - session_start_ns) /
///    60_000_000_000` (CONV §3's official minute index, floor division on a
///    non-negative numerator for any registered timestamp). No new pubread
///    leaf, and no A10 projection, is needed for these two fields. `cli`'s
///    `resolve_truth_rows` implements exactly this; out-of-bounds ordinals
///    (unreachable for any registered publication, but never silently
///    guessed) are a hard, typed error, not a panic or an `NA` fabrication.
///
///    `truth_extreme_price_u6` remains the one genuinely unresolved gap:
///    neither `AssignmentReader` nor `TruthCoverageReader` publishes any
///    price field for a truth episode at all (`truth_coverage.tsv`'s 21
///    columns, as typed in `pubread::leaves::truth_coverage`, carry no
///    `price_u6`), so [`EpisodeProjection::truth_extreme_price_u6`] is
///    `Option`-typed and populated as `None` by any real probe/run
///    population until the A10 leaf exists — see that field's own doc
///    comment. This narrower, corrected gap statement supersedes the
///    wave-1 author's original combined escalation for both fields.
pub struct TruthRelationDay {
    relations: HashMap<[u8; 32], SignalRelation>,
}

impl TruthRelationDay {
    /// Builds a day's relation lookup from an already-resolved map (the
    /// probe/run layer's job to build per the population contract above;
    /// tests build it directly/synthetically).
    #[must_use]
    pub fn new(relations: HashMap<[u8; 32], SignalRelation>) -> Self {
        Self { relations }
    }

    /// The signal's relation; absent entries are
    /// [`SignalRelation::NoTruthRelation`] (a signal with no relation edge is
    /// never inserted by the population contract above, so a lookup miss and
    /// an explicit `NoTruthRelation` entry are equivalent). `pub(crate)`
    /// (rather than private) so `crate::probe`'s own unit tests can inspect a
    /// built [`TruthRelationDay`] directly.
    #[must_use]
    pub(crate) fn relation_for(&self, signal_id: &[u8; 32]) -> SignalRelation {
        self.relations
            .get(signal_id)
            .copied()
            .unwrap_or(SignalRelation::NoTruthRelation)
    }
}

/// `cap_opp_state` (amendment §A7 "Captured-opportunity fraction",
/// E10-corrected): explains exactly why `cap_opp_num_u6`/`cap_opp_den_u6`
/// are present or `NA` on this row. The pair is treated as one atomic unit
/// (A7: "published as the integer pair, never divided") — both populated
/// together or both `NA` together.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CapOppState {
    /// Inherits [`SignalRelation::NoTruthRelation`] (A3).
    NoTruthRelation,
    /// Inherits [`SignalRelation::MultiRelation`] (A3).
    MultiRelation,
    /// `SINGLE_RELATION`, but the row's own registered slot window (the
    /// half-open `window_left`..`window_end` range every other column in
    /// this file uses) is empty, so no "favorable extreme over the slot's
    /// own window" exists to compute `cap_opp_num_u6` against (E10: "extreme
    /// over the SLOT's own registered window"). A generalization of the
    /// wave-1 author's original condition (`window_left` not indexing an
    /// existing group at all): that case is the special case where
    /// `window_left` is at or past `frame.group_count()`, which always
    /// implies `window_left` is at or past `window_end` too (`window_end`
    /// is itself bounded by `frame.group_count()`) — so the single check
    /// below subsumes it without losing any coverage. Recorded as an
    /// escalation (schema-authorship completion, not itself named by the
    /// amendment, same status as the original).
    SlotPriceUnavailable,
    /// `SINGLE_RELATION`, slot window available, but the truth's
    /// post-plateau window (E10: "scientific groups with `ts > plateau_end_ts`
    /// up to the session close") is empty — no favorable extreme exists to
    /// compute `cap_opp_den_u6` against. A new typed completion this
    /// infra-wave correction introduces (the post-plateau window is itself a
    /// new E10 concept; recorded as an escalation, the same pattern as
    /// `SlotPriceUnavailable`).
    PostPlateauUnavailable,
    /// `SINGLE_RELATION`, both windows available, `cap_opp_den_u6 == 0` (A7:
    /// "zero-den typed `DEGENERATE`").
    Degenerate,
    /// `SINGLE_RELATION`, both windows available, `cap_opp_den_u6 > 0`.
    Complete,
}

impl CapOppState {
    #[must_use]
    const fn wire(self) -> &'static str {
        match self {
            Self::NoTruthRelation => "NO_TRUTH_RELATION",
            Self::MultiRelation => "MULTI_RELATION",
            Self::SlotPriceUnavailable => "SLOT_PRICE_UNAVAILABLE",
            Self::PostPlateauUnavailable => "POST_PLATEAU_UNAVAILABLE",
            Self::Degenerate => "DEGENERATE",
            Self::Complete => "COMPLETE",
        }
    }
}

/// `cap_opp_den_frontier` — the post-plateau (denominator) window's OWN
/// typed censor state (L6 fix, `research/review_records/
/// events23_consolidated_ledger.md`; Sol#5 P1 "E10's post-plateau breaker
/// censor is computed but not published as a typed state"). Before this
/// fix, [`PostPlateauWindow`] computed exactly this distinction internally
/// and discarded it: [`cap_opp_fields`] reported bare
/// `CapOppState::Degenerate`/`CapOppState::Complete` for a nonempty
/// breaker-truncated denominator, indistinguishable from a genuine
/// full-close read. This column publishes that distinction directly, using
/// the SAME common frontier precedence as the base schema's
/// `WindowFrontier` (`DECISION_UNAVAILABLE > NOT_VISIBLE > SOURCE_CENSORED >
/// WIDE_BREAKER > COMPLETE`), restricted to the three states reachable once
/// the post-plateau window is actually resolved
/// (`DECISION_UNAVAILABLE`/`NOT_VISIBLE` never reach this column at all —
/// the row-level blanket rule already nulls it, along with every other
/// value column, before `cap_opp_*` is ever computed on those rows).
/// `cap_opp_state` itself is unchanged by this fix (it still reads
/// `Degenerate`/`Complete` purely off the `cap_opp_den_u6` value) — this is
/// the registered denominator-frontier sibling that must be read alongside
/// it before treating a `COMPLETE`/`DEGENERATE` denominator as a full-close
/// read.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CapOppDenFrontier {
    /// The post-plateau window is empty (exactly
    /// `CapOppState::PostPlateauUnavailable`).
    SourceCensored,
    /// The post-plateau window is non-empty, but a breaker starts strictly
    /// after `plateau_end_ts_ns` and before the session close: the window
    /// closed at the breaker, not at the close. **A non-empty
    /// breaker-truncated denominator is typed here and is never typed
    /// `Complete`**, regardless of what `cap_opp_state` reads
    /// (`Degenerate`/`Complete` are both reachable with a `WideBreaker`
    /// denominator).
    WideBreaker,
    /// The post-plateau window ran uncensored all the way to the session
    /// close (no intervening breaker).
    Complete,
}

impl CapOppDenFrontier {
    #[must_use]
    const fn wire(self) -> &'static str {
        match self {
            Self::SourceCensored => "SOURCE_CENSORED",
            Self::WideBreaker => "WIDE_BREAKER",
            Self::Complete => "COMPLETE",
        }
    }
}

/// Favorable-direction sign from `extreme_side` (amendment §A4's convention,
/// shared by this family): `+1` for `Low` (favorable = up), `-1` for `High`
/// (favorable = down).
#[must_use]
const fn dir(side: Side) -> i64 {
    match side {
        Side::Low => 1,
        Side::High => -1,
    }
}

/// The full set of resolved F-PROX value columns for one `(signal, slot)`
/// row whose window frontier is neither `DECISION_UNAVAILABLE` nor
/// `NOT_VISIBLE` (those two blanket-`NA` the whole row before this is ever
/// built — see [`write_tsv`]).
struct ProxValues {
    relation: SignalRelation,
    truth_episode_id: Option<[u8; 32]>,
    plateau_last_group_ordinal: Option<u64>,
    plateau_bar_ordinal: Option<i64>,
    signal_visible_delay_bars: Option<i64>,
    slot_delay_bars: Option<i64>,
    near_extreme_credit: Option<bool>,
    truth_price_gap_u6: Option<i64>,
    cap_opp_state: CapOppState,
    cap_opp_num_u6: Option<i64>,
    cap_opp_den_u6: Option<i64>,
    cap_opp_den_frontier: Option<CapOppDenFrontier>,
}

/// The five per-signal (relation-only, slot-independent) value columns:
/// `truth_episode_id`, `plateau_last_group_ordinal`, `plateau_bar_ordinal`,
/// `signal_visible_delay_bars`, `truth_price_gap_u6`.
struct PerSignalFields {
    truth_episode_id: Option<[u8; 32]>,
    plateau_last_group_ordinal: Option<u64>,
    plateau_bar_ordinal: Option<i64>,
    signal_visible_delay_bars: Option<i64>,
    truth_price_gap_u6: Option<i64>,
}

impl PerSignalFields {
    const NA: Self = Self {
        truth_episode_id: None,
        plateau_last_group_ordinal: None,
        plateau_bar_ordinal: None,
        signal_visible_delay_bars: None,
        truth_price_gap_u6: None,
    };
}

/// Computes [`PerSignalFields`]. `NA` (`None`) throughout unless `relation`
/// is [`SignalRelation::Single`]. `truth_price_gap_u6` is additionally `NA`
/// whenever the matched episode's `truth_extreme_price_u6` itself is
/// unknown (the still-open A10 data-access gap — see
/// [`EpisodeProjection::truth_extreme_price_u6`]). O(1).
fn per_signal_fields(
    frame: &SessionFrame,
    seed: &SignalSeed,
    relation: SignalRelation,
) -> PerSignalFields {
    let SignalRelation::Single(episode) = relation else {
        return PerSignalFields::NA;
    };

    // visible_bar = floor((causal_visible_ts_ns - session_start_ns) / 60e9)
    // (CONV §3 official minute index; causal_visible_ts_ns is a group-close
    // timestamp, not generally a bar boundary, so this is a floor division,
    // not the exact-boundary division used for slot_delay_bars below).
    let visible_bar = (seed.causal_visible_ts_ns - frame.session_start_ns) / NANOSECONDS_PER_BAR;
    let signal_visible_delay_bars = visible_bar - episode.plateau_bar_ordinal;

    let truth_price_gap_u6 = episode
        .truth_extreme_price_u6
        .map(|truth_extreme_price_u6| {
            let gap_128 =
                (i128::from(seed.pivot_price_u6) - i128::from(truth_extreme_price_u6)).abs();
            i64::try_from(gap_128)
                .expect("truth_price_gap_u6 fits in i64 for any registered u6 price pair")
        });

    PerSignalFields {
        truth_episode_id: Some(episode.episode_id),
        plateau_last_group_ordinal: Some(episode.plateau_last_group_ordinal),
        plateau_bar_ordinal: Some(episode.plateau_bar_ordinal),
        signal_visible_delay_bars: Some(signal_visible_delay_bars),
        truth_price_gap_u6,
    }
}

/// Computes `slot_delay_bars`/`near_extreme_credit` (amendment §A2 — the
/// rewritten, per-**slot** quantities). `NA` unless `relation` is
/// [`SignalRelation::Single`]. O(1).
///
/// # Panics
///
/// Panics if `row.cutoff_ts_ns - frame.session_start_ns` is not an exact
/// multiple of one bar — unreachable for any row produced by
/// [`SlotRow::compute`], whose `cutoff_ts_ns` is always
/// `session_start_ns + whole_bars * 60e9` by construction.
fn slot_delay_fields(
    frame: &SessionFrame,
    row: &SlotRow,
    relation: SignalRelation,
) -> (Option<i64>, Option<bool>) {
    let SignalRelation::Single(episode) = relation else {
        return (None, None);
    };

    let offset_ns = row.cutoff_ts_ns - frame.session_start_ns;
    assert_eq!(
        offset_ns % NANOSECONDS_PER_BAR,
        0,
        "cutoff_ts_ns is not an exact bar boundary (unreachable per SlotRow::compute)"
    );
    let slot_cutoff_bar = offset_ns / NANOSECONDS_PER_BAR;
    let slot_delay_bars = slot_cutoff_bar - episode.plateau_bar_ordinal;
    let near_extreme_credit = (1..=3).contains(&slot_delay_bars);
    (Some(slot_delay_bars), Some(near_extreme_credit))
}

/// The truth's post-plateau window (ruling E10): the half-open range of
/// frame indices `[left, end)` covering every scientific-path group with
/// `ts_ns > plateau_end_ts_ns`, breaker/close-censored exactly like every
/// other outcome window in this crate ("censor typed": an interrupting
/// breaker simply ends the window early, same as everywhere else — see
/// [`CapOppState::PostPlateauUnavailable`] for what happens when that leaves
/// nothing to query). `frontier` is the L6-fix typed censor state (always
/// resolved — never discarded — see [`CapOppDenFrontier`]).
struct PostPlateauWindow {
    left: usize,
    end: usize,
    frontier: CapOppDenFrontier,
}

/// Resolves [`PostPlateauWindow`] for one matched episode, INCLUDING the L6
/// fix's [`CapOppDenFrontier`] (previously computed as `breaker_start` and
/// then discarded once `bound`/`end` were derived from it — see the ledger
/// finding this fixes: `research/review_records/
/// events23_consolidated_ledger.md` L6, Sol#5 P1).
///
/// Precedence mirrors [`SlotRow::compute`]'s own `window_frontier`
/// resolution exactly (`SourceCensored` checked before `WideBreaker`): an
/// empty window is `SourceCensored` even when a breaker is also present,
/// since there is nothing left to distinguish once the window is empty.
///
/// O(log n): one [`SessionFrame::end_position`] descent for `left` plus one
/// [`SessionFrame::first_breaker_start_after`] descent and a second
/// [`SessionFrame::end_position`] descent for `end`.
///
/// # Panics
///
/// Panics if `plateau_end_ts_ns + 1` overflows `i64` — unreachable for any
/// registered session timestamp.
fn post_plateau_window(frame: &SessionFrame, plateau_end_ts_ns: i64) -> PostPlateauWindow {
    let left = frame.end_position(
        plateau_end_ts_ns
            .checked_add(1)
            .expect("plateau_end_ts_ns + 1 overflowed i64 for a registered timestamp"),
    );
    let breaker_start = frame.first_breaker_start_after(plateau_end_ts_ns);
    let bound = breaker_start.map_or(frame.session_end_ns, |start| {
        start.min(frame.session_end_ns)
    });
    let end = frame.end_position(bound);
    let frontier = if left >= end {
        CapOppDenFrontier::SourceCensored
    } else if breaker_start.is_some_and(|start| start < frame.session_end_ns) {
        CapOppDenFrontier::WideBreaker
    } else {
        CapOppDenFrontier::Complete
    };
    PostPlateauWindow {
        left,
        end,
        frontier,
    }
}

/// Computes the captured-opportunity pair (amendment §A7, **E10-corrected**):
/// `cap_opp_num_u6` = `clamp≥0(dir · (favorable extreme over the SLOT's own
/// registered window − slot_price_u6))` (window = the half-open
/// `window_left`..`window_end` range this row already resolved),
/// `cap_opp_den_u6` = `clamp≥0(dir · (favorable extreme over the TRUTH's own
/// post-plateau window − pivot_price_u6))` — neither depends on
/// `truth_extreme_price_u6` at all (E10's whole point: the old A7 formula's
/// dependence on that exact field was what made it degenerate by the
/// exact-key match construction).
///
/// O(log n): up to two [`crate::extrema::ExtremaTree`] range queries (num
/// side) plus [`post_plateau_window`]'s own O(log n) resolution and up to
/// two more range queries (den side).
///
/// # Panics
///
/// Panics if a `cap_opp_num_u6`/`cap_opp_den_u6` intermediate (computed in
/// `i128`) does not fit back into `i64` — unreachable for any registered u6
/// price pair (many orders of magnitude under `i64::MAX`).
fn cap_opp_fields(
    frame: &SessionFrame,
    seed: &SignalSeed,
    row: &SlotRow,
    relation: SignalRelation,
) -> (
    CapOppState,
    Option<i64>,
    Option<i64>,
    Option<CapOppDenFrontier>,
) {
    let episode = match relation {
        SignalRelation::NoTruthRelation => {
            return (CapOppState::NoTruthRelation, None, None, None);
        }
        SignalRelation::MultiRelation { .. } => {
            return (CapOppState::MultiRelation, None, None, None);
        }
        SignalRelation::Single(episode) => episode,
    };

    let window_left = row
        .window_left
        .expect("window_left present when slot available and visible");
    let window_end = row
        .window_end
        .expect("window_end present when slot available and visible");
    if window_left >= window_end {
        return (CapOppState::SlotPriceUnavailable, None, None, None);
    }

    let tree = frame.extrema();
    let d = i128::from(dir(seed.extreme_side));

    // Numerator: the slot's own window (identical range every other column
    // in this file uses for this row).
    let slot_price_u6 = match seed.extreme_side {
        Side::Low => frame.m_hi[window_left],
        Side::High => frame.m_lo[window_left],
    };
    let slot_favorable_extreme = match seed.extreme_side {
        Side::Low => tree.range_max(window_left, window_end - 1).value,
        Side::High => tree.range_min(window_left, window_end - 1).value,
    };
    let num_128 = (d * (i128::from(slot_favorable_extreme) - i128::from(slot_price_u6))).max(0);
    let cap_opp_num_u6 =
        i64::try_from(num_128).expect("cap_opp_num_u6 fits in i64 for any registered price pair");

    // Denominator: the truth's own post-plateau window (a different range,
    // anchored to the matched episode, not this row's own cutoff). L6 fix:
    // `post.frontier` is ALWAYS resolved here (never discarded) and is
    // published below via every return path, including the
    // `PostPlateauUnavailable` (empty-window) one -- `SourceCensored` there,
    // never `NA`.
    let post = post_plateau_window(frame, episode.plateau_end_ts_ns);
    if post.left >= post.end {
        return (
            CapOppState::PostPlateauUnavailable,
            None,
            None,
            Some(post.frontier),
        );
    }
    let post_favorable_extreme = match seed.extreme_side {
        Side::Low => tree.range_max(post.left, post.end - 1).value,
        Side::High => tree.range_min(post.left, post.end - 1).value,
    };
    let den_128 =
        (d * (i128::from(post_favorable_extreme) - i128::from(seed.pivot_price_u6))).max(0);
    let cap_opp_den_u6 =
        i64::try_from(den_128).expect("cap_opp_den_u6 fits in i64 for any registered price pair");

    let state = if cap_opp_den_u6 == 0 {
        CapOppState::Degenerate
    } else {
        CapOppState::Complete
    };
    (
        state,
        Some(cap_opp_num_u6),
        Some(cap_opp_den_u6),
        Some(post.frontier),
    )
}

impl ProxValues {
    /// Computes the full 13-column value set for one resolvable
    /// `(signal, slot)` row (`relation` already resolved once per signal by
    /// the caller — see [`write_tsv`]).
    fn build(
        frame: &SessionFrame,
        seed: &SignalSeed,
        row: &SlotRow,
        relation: SignalRelation,
    ) -> Self {
        let PerSignalFields {
            truth_episode_id,
            plateau_last_group_ordinal,
            plateau_bar_ordinal,
            signal_visible_delay_bars,
            truth_price_gap_u6,
        } = per_signal_fields(frame, seed, relation);
        let (slot_delay_bars, near_extreme_credit) = slot_delay_fields(frame, row, relation);
        let (cap_opp_state, cap_opp_num_u6, cap_opp_den_u6, cap_opp_den_frontier) =
            cap_opp_fields(frame, seed, row, relation);

        Self {
            relation,
            truth_episode_id,
            plateau_last_group_ordinal,
            plateau_bar_ordinal,
            signal_visible_delay_bars,
            slot_delay_bars,
            near_extreme_credit,
            truth_price_gap_u6,
            cap_opp_state,
            cap_opp_num_u6,
            cap_opp_den_u6,
            cap_opp_den_frontier,
        }
    }
}

/// The `f_prox.tsv` header: the ten-column common prefix followed by the 13
/// F-PROX value columns, in schema order
/// (`docs/specs/family_schemas/f_prox_schema_v1.md`).
#[must_use]
pub fn header() -> String {
    "day\tsignal_id\tslot\tseed_bar_ordinal\tcutoff_ts_ns\tslot_available\t\
     visible_at_slot\twindow_left\twindow_end\twindow_frontier\t\
     relation_state\trelation_count\ttruth_episode_id\t\
     plateau_last_group_ordinal\tplateau_bar_ordinal\t\
     signal_visible_delay_bars\tslot_delay_bars\tnear_extreme_credit\t\
     truth_price_gap_u6\tcap_opp_state\tcap_opp_num_u6\tcap_opp_den_u6\t\
     cap_opp_den_frontier"
        .to_owned()
}

/// Hex-encodes a 32-byte digest as 64 lowercase hex characters (schema
/// "Formatting rules"). Duplicated locally: `crate::anchor`'s own copy is
/// private to that module. O(1) (a fixed 32 bytes).
fn hex32(digest: &[u8; 32]) -> String {
    digest
        .iter()
        .fold(String::with_capacity(64), |mut out, byte| {
            write!(out, "{byte:02x}").expect("writing to a String cannot fail");
            out
        })
}

fn opt_hex32_wire(value: Option<[u8; 32]>) -> String {
    value.map_or_else(|| "NA".to_owned(), |digest| hex32(&digest))
}

fn opt_u64_wire(value: Option<u64>) -> String {
    value.map_or_else(|| "NA".to_owned(), |v| v.to_string())
}

fn opt_i64_wire(value: Option<i64>) -> String {
    value.map_or_else(|| "NA".to_owned(), |v| v.to_string())
}

fn opt_bool_wire(value: Option<bool>) -> String {
    value.map_or_else(
        || "NA".to_owned(),
        |v| if v { "true" } else { "false" }.to_owned(),
    )
}

/// L6 fix: `cap_opp_den_frontier` wire formatter (`NA` iff the post-plateau
/// window was never attempted at all — see [`CapOppDenFrontier`]).
fn opt_cap_opp_den_frontier_wire(value: Option<CapOppDenFrontier>) -> String {
    value.map_or_else(|| "NA".to_owned(), |v| v.wire().to_owned())
}

/// Appends the 13 F-PROX value columns, tab-prefixed.
fn push_prox_columns(line: &mut String, values: &ProxValues) {
    write!(
        line,
        "\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}",
        values.relation.wire(),
        values.relation.relation_count(),
        opt_hex32_wire(values.truth_episode_id),
        opt_u64_wire(values.plateau_last_group_ordinal),
        opt_i64_wire(values.plateau_bar_ordinal),
        opt_i64_wire(values.signal_visible_delay_bars),
        opt_i64_wire(values.slot_delay_bars),
        opt_bool_wire(values.near_extreme_credit),
        opt_i64_wire(values.truth_price_gap_u6),
        values.cap_opp_state.wire(),
        opt_i64_wire(values.cap_opp_num_u6),
        opt_i64_wire(values.cap_opp_den_u6),
        opt_cap_opp_den_frontier_wire(values.cap_opp_den_frontier),
    )
    .expect("writing to a String cannot fail");
}

/// Computes every `(signal, slot)` row as one tab-joined line, no header, no
/// trailing newline: one row per `(signal, slot)`, slots in order `D1, D2,
/// D3` (slot-minor), signals in the order given by `seeds` (`day_signals.tsv`
/// publication order), exactly the row-order convention of every other
/// family (`docs/specs/label_probe_schema_v1.md` "Family-file common
/// prefix"). Reusable in-memory (e.g. for parquet publication) without going
/// through [`write_tsv`]'s file.
///
/// `truth` is the per-day pre-joined relation lookup — see
/// [`TruthRelationDay`]'s doc comment for the exact population contract.
///
/// Rows whose window frontier is `DECISION_UNAVAILABLE`/`NOT_VISIBLE` carry
/// literal `NA` in all 13 value columns (the schema's blanket row-level
/// rule, applied uniformly with every other family); every other row
/// (`SOURCE_CENSORED`, `WIDE_BREAKER`, `COMPLETE`) computes the relation
/// state always, and the remaining columns per their own typed-`NA` rules
/// (`docs/specs/family_schemas/f_prox_schema_v1.md`).
///
/// O(`seeds.len()` · log n): one `HashMap` lookup per signal (O(1)
/// amortized) plus [`SlotRow::compute`]'s own O(log n) window resolution per
/// slot, `n` = `frame.group_count()`. No new [`crate::extrema::ExtremaTree`]
/// descents beyond [`cap_opp_fields`]'s own bounded range queries.
#[must_use]
pub fn rows(frame: &SessionFrame, seeds: &[SignalSeed], truth: &TruthRelationDay) -> Vec<String> {
    let mut out = Vec::with_capacity(seeds.len() * Slot::ALL.len());
    for seed in seeds {
        let relation = truth.relation_for(&seed.signal_id);
        for slot in Slot::ALL {
            let row = SlotRow::compute(frame, seed, slot, frame.session_end_ns);
            let mut line = row.format_prefix(frame.day);
            if matches!(
                row.window_frontier,
                WindowFrontier::DecisionUnavailable | WindowFrontier::NotVisible
            ) {
                line.push_str("\tNA\tNA\tNA\tNA\tNA\tNA\tNA\tNA\tNA\tNA\tNA\tNA\tNA");
            } else {
                let values = ProxValues::build(frame, seed, &row, relation);
                push_prox_columns(&mut line, &values);
            }
            out.push(line);
        }
    }
    out
}

/// Writes `f_prox.tsv` for every `(signal, slot)` row ([`rows`]).
///
/// # Errors
///
/// Returns an [`io::Error`] if `out_path` cannot be created or written.
pub fn write_tsv(
    frame: &SessionFrame,
    seeds: &[SignalSeed],
    truth: &TruthRelationDay,
    out_path: &Path,
) -> io::Result<()> {
    let mut out = BufWriter::new(File::create(out_path)?);
    writeln!(out, "{}", header())?;
    for line in rows(frame, seeds, truth) {
        writeln!(out, "{line}")?;
    }
    out.flush()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::frame::GroupKind;

    const BAR_NS: i64 = NANOSECONDS_PER_BAR;

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

    /// Test helper for [`EpisodeProjection`]: `plateau_last_group_ordinal`
    /// is a fixed placeholder (raw-provenance-only, never itself computed
    /// against by this module) unless a test overrides it explicitly.
    fn episode(
        plateau_bar_ordinal: i64,
        plateau_end_ts_ns: i64,
        truth_extreme_price_u6: Option<i64>,
    ) -> EpisodeProjection {
        EpisodeProjection {
            episode_id: [0xcd; 32],
            plateau_last_group_ordinal: 999,
            plateau_bar_ordinal,
            plateau_end_ts_ns,
            truth_extreme_price_u6,
        }
    }

    fn day(relations: Vec<([u8; 32], SignalRelation)>) -> TruthRelationDay {
        TruthRelationDay::new(relations.into_iter().collect())
    }

    fn temp_out_path(name: &str) -> std::path::PathBuf {
        std::env::temp_dir().join(format!("f_prox_test_{}_{name}.tsv", std::process::id()))
    }

    // -------------------- SignalRelation / CapOppState wire --------------------

    #[test]
    fn relation_wire_and_count_match_the_registered_states() {
        assert_eq!(SignalRelation::NoTruthRelation.wire(), "NO_TRUTH_RELATION");
        assert_eq!(SignalRelation::NoTruthRelation.relation_count(), 0);
        let single = SignalRelation::Single(episode(5, 0, Some(1_000_000)));
        assert_eq!(single.wire(), "SINGLE_RELATION");
        assert_eq!(single.relation_count(), 1);
        let multi = SignalRelation::MultiRelation { relation_count: 3 };
        assert_eq!(multi.wire(), "MULTI_RELATION");
        assert_eq!(multi.relation_count(), 3);
    }

    // ------------------- P0 scenario: delays 0..4, credit divergence -------------------

    // Sol's P0 scenario (amendment A2): visible at plateau+1, but the three
    // slots land at plateau+2/+3/+4 -- near_extreme_credit must differ per
    // slot even though signal_visible_delay_bars (the old, single
    // per-signal quantity) is the same 1 throughout.
    //
    // Hand-computed: plateau_bar_ordinal = 5. causal_visible_ts_ns = 6 *
    // BAR_NS => visible_bar = 6 => signal_visible_delay_bars = 6 - 5 = 1.
    // seed_bar_ordinal (pivot_last_bar_ordinal) = 6 => D1 cutoff_bar = 7,
    // D2 = 8, D3 = 9. slot_delay_bars: D1 = 7-5=2 (credit), D2 = 8-5=3
    // (credit), D3 = 9-5=4 (NOT credit, boundary just past {1,2,3}).
    #[test]
    fn p0_scenario_slot_delay_and_credit_divergence_across_d1_d2_d3() {
        let session_end_ns = 20 * BAR_NS;
        // One scientific group covering the whole session so cap_opp
        // resolves (not the focus of this test, but keeps every slot's
        // window_left valid).
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![0],
            vec![1_000_000],
            vec![1_000_000],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(Side::Low, 6, 6 * BAR_NS, 1_000_000);
        let truth = day(vec![(
            s.signal_id,
            SignalRelation::Single(episode(5, 0, Some(1_000_000))),
        )]);

        let path = temp_out_path("p0_scenario");
        write_tsv(&frame, std::slice::from_ref(&s), &truth, &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        lines.next(); // header
        let d1: Vec<&str> = lines.next().expect("D1 row").split('\t').collect();
        let d2: Vec<&str> = lines.next().expect("D2 row").split('\t').collect();
        let d3: Vec<&str> = lines.next().expect("D3 row").split('\t').collect();
        assert_eq!(lines.next(), None);

        // Column indices: 10 (relation_state) .. 21 (cap_opp_den_u6).
        // signal_visible_delay_bars is column 15 (0-based).
        assert_eq!(d1[15], "1");
        assert_eq!(d2[15], "1");
        assert_eq!(d3[15], "1");

        // slot_delay_bars is column 16.
        assert_eq!(d1[16], "2");
        assert_eq!(d2[16], "3");
        assert_eq!(d3[16], "4");

        // near_extreme_credit is column 17.
        assert_eq!(d1[17], "true");
        assert_eq!(d2[17], "true");
        assert_eq!(d3[17], "false");

        std::fs::remove_file(&path).ok();
    }

    #[test]
    fn slot_delay_boundary_zero_and_four_are_not_credited() {
        // plateau_bar_ordinal = seed_bar_ordinal + 1 (D1 slot cutoff bar) =>
        // slot_delay_bars at D1 = 0 (not in {1,2,3}).
        let session_end_ns = 20 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![0],
            vec![1_000_000],
            vec![1_000_000],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        // D1 cutoff_bar = 1 => plateau = 1 gives slot_delay_bars(D1) = 0.
        let truth = day(vec![(
            s.signal_id,
            SignalRelation::Single(episode(1, 0, Some(1_000_000))),
        )]);
        let path = temp_out_path("boundary_zero");
        write_tsv(&frame, std::slice::from_ref(&s), &truth, &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        lines.next();
        let d1: Vec<&str> = lines.next().expect("D1 row").split('\t').collect();
        assert_eq!(d1[16], "0");
        assert_eq!(d1[17], "false");
        std::fs::remove_file(&path).ok();

        // D3 cutoff_bar = 3; plateau = -1 gives slot_delay_bars(D3) = 4.
        let s2 = seed(Side::Low, 0, 0, 1_000_000);
        let truth2 = day(vec![(
            s2.signal_id,
            SignalRelation::Single(episode(-1, 0, Some(1_000_000))),
        )]);
        let path2 = temp_out_path("boundary_four");
        write_tsv(&frame, std::slice::from_ref(&s2), &truth2, &path2).expect("write_tsv succeeds");
        let content2 = std::fs::read_to_string(&path2).expect("file exists");
        let mut lines2 = content2.lines();
        lines2.next();
        lines2.next(); // D1
        lines2.next(); // D2
        let d3: Vec<&str> = lines2.next().expect("D3 row").split('\t').collect();
        assert_eq!(d3[16], "4");
        assert_eq!(d3[17], "false");
        std::fs::remove_file(&path2).ok();
    }

    // ------------------------- unmatched signal -------------------------

    #[test]
    fn unmatched_signal_is_no_truth_relation_with_all_downstream_na() {
        let session_end_ns = 10 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![0],
            vec![1_000_000],
            vec![1_000_000],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let truth = day(vec![]); // no relation registered at all
        let path = temp_out_path("unmatched");
        write_tsv(&frame, std::slice::from_ref(&s), &truth, &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        lines.next();
        let d1: Vec<&str> = lines.next().expect("D1 row").split('\t').collect();

        assert_eq!(d1[10], "NO_TRUTH_RELATION"); // relation_state
        assert_eq!(d1[11], "0"); // relation_count
        assert_eq!(d1[12], "NA"); // truth_episode_id
        assert_eq!(d1[13], "NA"); // plateau_last_group_ordinal
        assert_eq!(d1[14], "NA"); // plateau_bar_ordinal
        assert_eq!(d1[15], "NA"); // signal_visible_delay_bars
        assert_eq!(d1[16], "NA"); // slot_delay_bars
        assert_eq!(d1[17], "NA"); // near_extreme_credit
        assert_eq!(d1[18], "NA"); // truth_price_gap_u6
        assert_eq!(d1[19], "NO_TRUTH_RELATION"); // cap_opp_state
        assert_eq!(d1[20], "NA"); // cap_opp_num_u6
        assert_eq!(d1[21], "NA"); // cap_opp_den_u6
        assert_eq!(d1[22], "NA"); // cap_opp_den_frontier

        std::fs::remove_file(&path).ok();
    }

    // ------------------------- multi-relation single-row -------------------------

    #[test]
    fn multi_relation_emits_exactly_one_row_per_slot_with_the_count_and_no_episode_fields() {
        let session_end_ns = 10 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![0],
            vec![1_000_000],
            vec![1_000_000],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let truth = day(vec![(
            s.signal_id,
            SignalRelation::MultiRelation { relation_count: 2 },
        )]);
        let path = temp_out_path("multi_relation");
        write_tsv(&frame, std::slice::from_ref(&s), &truth, &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        lines.next();
        let rows: Vec<&str> = lines.collect();
        // Exactly one row per slot (never row multiplication): 3 total.
        assert_eq!(rows.len(), 3);

        let d1: Vec<&str> = rows[0].split('\t').collect();
        assert_eq!(d1[10], "MULTI_RELATION");
        assert_eq!(d1[11], "2");
        assert_eq!(d1[12], "NA"); // truth_episode_id: no episode chosen
        assert_eq!(d1[13], "NA");
        assert_eq!(d1[14], "NA");
        assert_eq!(d1[15], "NA");
        assert_eq!(d1[16], "NA");
        assert_eq!(d1[17], "NA");
        assert_eq!(d1[18], "NA");
        assert_eq!(d1[19], "MULTI_RELATION");
        assert_eq!(d1[20], "NA");
        assert_eq!(d1[21], "NA");
        assert_eq!(d1[22], "NA"); // cap_opp_den_frontier

        std::fs::remove_file(&path).ok();
    }

    // ------------------------- cap_opp: DEGENERATE (den floors to 0) -------------------------

    #[test]
    fn cap_opp_degenerate_when_the_post_plateau_favorable_extreme_equals_pivot() {
        // LOW (dir=+1), P = 1_000_000. D1 cutoff = BAR_NS (seed_bar_ordinal
        // = 0). plateau_end_ts_ns = 0, strictly before BOTH groups, so the
        // post-plateau window ALSO covers both.
        //
        // g0 @ BAR_NS (window_left): m_hi = 999_500 (slot_price).
        // g1 @ 2*BAR_NS: m_hi = 1_000_000 (== P exactly).
        //
        // num: favorable extreme over [0,1] = max(999_500, 1_000_000) =
        // 1_000_000 (index 1). num = clamp(1*(1_000_000-999_500)) = 500.
        // den: SAME window (plateau_end_ts_ns=0 predates both groups) =>
        // favorable extreme = 1_000_000. den = clamp(1*(1_000_000-1_000_000))
        // = 0 => DEGENERATE.
        let session_end_ns = 10 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![BAR_NS, 2 * BAR_NS],
            vec![999_000, 999_000],
            vec![999_500, 1_000_000],
            vec![GroupKind::Scalar; 2],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let truth = day(vec![(
            s.signal_id,
            SignalRelation::Single(episode(0, 0, None)),
        )]);
        let path = temp_out_path("degenerate");
        write_tsv(&frame, std::slice::from_ref(&s), &truth, &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        lines.next();
        let d1: Vec<&str> = lines.next().expect("D1 row").split('\t').collect();

        assert_eq!(d1[19], "DEGENERATE"); // cap_opp_state
        assert_eq!(d1[20], "500"); // cap_opp_num_u6
        assert_eq!(d1[21], "0"); // cap_opp_den_u6
        // L6 fix: no breaker anywhere in this frame -> the denominator ran
        // uncensored to the session close -> COMPLETE (never WIDE_BREAKER),
        // independent of cap_opp_state's own DEGENERATE/COMPLETE split.
        assert_eq!(d1[22], "COMPLETE"); // cap_opp_den_frontier

        std::fs::remove_file(&path).ok();
    }

    #[test]
    fn cap_opp_negative_raw_denominator_clamps_to_zero_and_is_degenerate() {
        // LOW (dir=+1), P = 1_000_000. Both groups' m_hi stay BELOW P, so the
        // post-plateau favorable extreme is adverse relative to the pivot:
        // the raw difference is negative and must clamp to 0, not go
        // negative.
        //
        // g0 @ BAR_NS (window_left): m_hi = 999_500 (slot_price).
        // g1 @ 2*BAR_NS: m_hi = 999_800.
        //
        // num: favorable extreme = max(999_500, 999_800) = 999_800 (index 1).
        // num = clamp(1*(999_800-999_500)) = 300.
        // den: same window (plateau_end_ts_ns=0) => favorable extreme =
        // 999_800. raw = 1*(999_800-1_000_000) = -200 => clamp to 0 =>
        // DEGENERATE.
        let session_end_ns = 10 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![BAR_NS, 2 * BAR_NS],
            vec![999_000, 999_000],
            vec![999_500, 999_800],
            vec![GroupKind::Scalar; 2],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let truth = day(vec![(
            s.signal_id,
            SignalRelation::Single(episode(0, 0, None)),
        )]);
        let path = temp_out_path("degenerate_negative");
        write_tsv(&frame, std::slice::from_ref(&s), &truth, &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        lines.next();
        let d1: Vec<&str> = lines.next().expect("D1 row").split('\t').collect();
        assert_eq!(d1[19], "DEGENERATE");
        assert_eq!(d1[20], "300");
        assert_eq!(d1[21], "0");
        assert_eq!(d1[22], "COMPLETE"); // cap_opp_den_frontier: no breaker present
        std::fs::remove_file(&path).ok();
    }

    // ------------------------- near-close unavailable slot -------------------------

    #[test]
    fn near_close_unavailable_slot_blanket_nulls_every_prox_column() {
        // Mirrors anchor.rs's early-close pattern: session_end at 3 bars,
        // seed_bar_ordinal = 1 => D1 cutoff = 2*BAR_NS (available), D2
        // cutoff = 3*BAR_NS == session_end (DECISION_UNAVAILABLE), D3 cutoff
        // = 4*BAR_NS (DECISION_UNAVAILABLE too).
        let session_end_ns = 3 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![0],
            vec![1_000_000],
            vec![1_000_000],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(Side::Low, 1, 0, 1_000_000);
        let truth = day(vec![(
            s.signal_id,
            SignalRelation::Single(episode(0, 0, Some(1_000_000))),
        )]);
        let path = temp_out_path("near_close_unavailable");
        write_tsv(&frame, std::slice::from_ref(&s), &truth, &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        lines.next();
        let d1: Vec<&str> = lines.next().expect("D1 row").split('\t').collect();
        let d2: Vec<&str> = lines.next().expect("D2 row").split('\t').collect();
        let d3: Vec<&str> = lines.next().expect("D3 row").split('\t').collect();
        assert_eq!(lines.next(), None);

        assert_ne!(d1[9], "DECISION_UNAVAILABLE");
        assert_ne!(d1[10], "NA"); // relation_state resolved on the available slot

        assert_eq!(d2[9], "DECISION_UNAVAILABLE");
        assert!(d2[10..].iter().all(|&c| c == "NA"));
        assert_eq!(d3[9], "DECISION_UNAVAILABLE");
        assert!(d3[10..].iter().all(|&c| c == "NA"));

        std::fs::remove_file(&path).ok();
    }

    // ------------------------- slot price unavailable (no group at cutoff at all) -------------------------

    #[test]
    fn slot_price_unavailable_when_no_group_exists_at_or_after_cutoff() {
        // Single group at ts=0; D1 cutoff = BAR_NS is strictly after it, and
        // no further group exists => window_left == window_end == frame.
        // group_count() (the narrowest, original wave-1 condition, still
        // covered by the broadened E10 check below).
        let session_end_ns = 20 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![0],
            vec![1_000_000],
            vec![1_000_000],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let truth = day(vec![(
            s.signal_id,
            SignalRelation::Single(episode(0, 0, Some(1_000_000))),
        )]);
        let path = temp_out_path("slot_price_unavailable");
        write_tsv(&frame, std::slice::from_ref(&s), &truth, &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        lines.next();
        let d1: Vec<&str> = lines.next().expect("D1 row").split('\t').collect();

        // relation still resolves (SINGLE_RELATION); only cap_opp is
        // unavailable.
        assert_eq!(d1[10], "SINGLE_RELATION");
        assert_eq!(d1[19], "SLOT_PRICE_UNAVAILABLE");
        assert_eq!(d1[20], "NA");
        assert_eq!(d1[21], "NA");
        // L6 fix: the post-plateau (denominator) window is never attempted
        // when the numerator side is unavailable -- NA, not a fabricated
        // frontier.
        assert_eq!(d1[22], "NA"); // cap_opp_den_frontier
        // slot_delay_bars/near_extreme_credit do not depend on slot price:
        // still computed.
        assert_ne!(d1[16], "NA");

        std::fs::remove_file(&path).ok();
    }

    #[test]
    fn cap_opp_slot_price_unavailable_when_the_row_window_is_empty_but_a_later_group_exists() {
        // The E10-broadened condition: window_left (0) DOES index a real
        // group in the frame (group_count() = 1), but a breaker starting
        // just after the D1 cutoff censors the row's own window down to
        // empty BEFORE that group is ever reached — this is a genuinely
        // different reachable case from "no group exists at all" above, and
        // the old wave-1 check (`window_left >= frame.group_count()`) would
        // have missed it.
        let session_end_ns = 20 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![2 * BAR_NS], // strictly after the D1 cutoff (BAR_NS)
            vec![1_000_000],
            vec![1_000_000],
            vec![GroupKind::Scalar],
            vec![crate::frame::Breaker {
                start_ns: BAR_NS + 1, // strictly after cutoff
                end_ns: 3 * BAR_NS,
            }],
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let truth = day(vec![(
            s.signal_id,
            SignalRelation::Single(episode(0, 0, None)),
        )]);
        let path = temp_out_path("slot_window_empty_group_exists");
        write_tsv(&frame, std::slice::from_ref(&s), &truth, &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        lines.next();
        let d1: Vec<&str> = lines.next().expect("D1 row").split('\t').collect();

        assert_eq!(d1[7], "0"); // window_left indexes the real group
        assert_eq!(d1[8], "0"); // window_end == window_left: empty
        assert_eq!(d1[19], "SLOT_PRICE_UNAVAILABLE");
        assert_eq!(d1[20], "NA");
        assert_eq!(d1[21], "NA");
        assert_eq!(d1[22], "NA"); // cap_opp_den_frontier: not attempted

        std::fs::remove_file(&path).ok();
    }

    // ------------------------- post-plateau window unavailable (new, E10) -------------------------

    #[test]
    fn cap_opp_post_plateau_unavailable_when_no_group_follows_the_plateau() {
        // LOW, P = 1_000_000. One group at the D1 cutoff (BAR_NS) makes the
        // slot's own num side computable, but plateau_end_ts_ns is set so
        // late (9*BAR_NS, near the session close) that no group's ts is
        // strictly greater than it: the post-plateau window is empty.
        let session_end_ns = 10 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![BAR_NS],
            vec![999_000],
            vec![1_000_500],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let truth = day(vec![(
            s.signal_id,
            SignalRelation::Single(episode(0, 9 * BAR_NS, None)),
        )]);
        let path = temp_out_path("post_plateau_unavailable");
        write_tsv(&frame, std::slice::from_ref(&s), &truth, &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        lines.next();
        let d1: Vec<&str> = lines.next().expect("D1 row").split('\t').collect();

        assert_eq!(d1[10], "SINGLE_RELATION");
        assert_eq!(d1[19], "POST_PLATEAU_UNAVAILABLE");
        assert_eq!(d1[20], "NA");
        assert_eq!(d1[21], "NA");
        // L6 fix (Sol#5 P1): the post-plateau window IS resolved here (it's
        // simply empty) -- published as SOURCE_CENSORED, never NA, so this
        // empty-denominator case is distinguishable from "never attempted".
        assert_eq!(d1[22], "SOURCE_CENSORED"); // cap_opp_den_frontier

        std::fs::remove_file(&path).ok();
    }

    // ------------------------- L6 fix: WIDE_BREAKER denominator (Sol#5 P1) -------------------------

    #[test]
    fn cap_opp_den_frontier_wide_breaker_when_denominator_is_breaker_truncated() {
        // Sol#5's own scenario (`events23_consolidated_ledger.md` L6):
        // "A truth plateaus at t0; one favorable scientific group occurs at
        // t1; a wide breaker begins at t2, well before close." Both
        // `cap_opp_state` values (DEGENERATE/COMPLETE) can arise with a
        // breaker-truncated denominator -- this scenario lands on COMPLETE
        // (den > 0), which is exactly the case the P1 finding says was
        // previously indistinguishable from a genuine full-close read.
        let session_end_ns = 50 * BAR_NS; // far past t2 -- close does NOT end the window
        let t0 = 3 * BAR_NS; // plateau_end_ts_ns
        let t1 = 4 * BAR_NS; // one favorable scientific group after the plateau
        let t2 = 10 * BAR_NS; // wide breaker begins here, well before close
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![t1, 6 * BAR_NS], // t1, and D1's own window_left group
            vec![1_010_000, 1_020_000],
            vec![1_010_000, 1_020_000],
            vec![GroupKind::Scalar; 2],
            vec![crate::frame::Breaker {
                start_ns: t2,
                end_ns: session_end_ns,
            }],
        );
        // seed_bar_ordinal = 5 -> D1 cutoff = 6*BAR_NS.
        let s = seed(Side::Low, 5, 0, 1_000_000);
        let truth = day(vec![(
            s.signal_id,
            SignalRelation::Single(episode(5, t0, None)),
        )]);
        let path = temp_out_path("den_frontier_wide_breaker");
        write_tsv(&frame, std::slice::from_ref(&s), &truth, &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        lines.next();
        let d1: Vec<&str> = lines.next().expect("D1 row").split('\t').collect();

        // den window = {t1, 6*BAR_NS} (both > t0, both < t2's breaker);
        // favorable (max) = 1_020_000; den = 1_020_000 - 1_000_000 =
        // 20_000 (nonzero -> cap_opp_state stays COMPLETE -- exactly the
        // bug: COMPLETE alone does not reveal the breaker truncation --
        // cap_opp_den_frontier must).
        assert_eq!(d1[19], "COMPLETE"); // cap_opp_state
        assert_eq!(d1[21], "20000"); // cap_opp_den_u6
        assert_eq!(d1[22], "WIDE_BREAKER"); // cap_opp_den_frontier: never COMPLETE here

        std::fs::remove_file(&path).ok();
    }

    // ------------------------- HIGH side mirrors direction (COMPLETE) -------------------------

    #[test]
    fn high_side_cap_opp_uses_m_lo_and_mirrored_dir_complete() {
        // HIGH (short): dir = -1, favorable = down, slot price = m_lo.
        // P = 1_000_000. plateau_end_ts_ns = 0 (predates both groups), so
        // num and den share the same underlying window/extreme.
        //
        // g0 @ BAR_NS (window_left): m_lo = 999_000 (slot_price).
        // g1 @ 2*BAR_NS: m_lo = 998_000 (more favorable for a short).
        //
        // favorable extreme (HIGH: min of m_lo) over [0,1] = 998_000.
        // num = clamp(-1*(998_000-999_000)) = clamp(1_000) = 1_000.
        // den = clamp(-1*(998_000-1_000_000)) = clamp(2_000) = 2_000.
        let session_end_ns = 10 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![BAR_NS, 2 * BAR_NS],
            vec![999_000, 998_000],
            vec![999_500, 998_500],
            vec![GroupKind::Scalar; 2],
            Vec::new(),
        );
        let s = seed(Side::High, 0, 0, 1_000_000);
        let truth = day(vec![(
            s.signal_id,
            SignalRelation::Single(episode(0, 0, None)),
        )]);
        let path = temp_out_path("high_side_complete");
        write_tsv(&frame, std::slice::from_ref(&s), &truth, &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        lines.next();
        let d1: Vec<&str> = lines.next().expect("D1 row").split('\t').collect();

        assert_eq!(d1[19], "COMPLETE");
        assert_eq!(d1[20], "1000");
        assert_eq!(d1[21], "2000");
        assert_eq!(d1[22], "COMPLETE"); // cap_opp_den_frontier: no breaker present

        std::fs::remove_file(&path).ok();
    }

    // ------------------------- header shape -------------------------

    #[test]
    fn header_has_the_exact_expected_column_count_and_names() {
        let h = header();
        let columns: Vec<&str> = h.split('\t').collect();
        assert_eq!(columns.len(), 10 + 13);
        assert_eq!(columns[0], "day");
        assert_eq!(columns[9], "window_frontier");
        assert_eq!(columns[10], "relation_state");
        assert_eq!(columns[11], "relation_count");
        assert_eq!(columns[12], "truth_episode_id");
        assert_eq!(columns[13], "plateau_last_group_ordinal");
        assert_eq!(columns[14], "plateau_bar_ordinal");
        assert_eq!(columns[15], "signal_visible_delay_bars");
        assert_eq!(columns[16], "slot_delay_bars");
        assert_eq!(columns[17], "near_extreme_credit");
        assert_eq!(columns[18], "truth_price_gap_u6");
        assert_eq!(columns[19], "cap_opp_state");
        assert_eq!(columns[20], "cap_opp_num_u6");
        assert_eq!(columns[21], "cap_opp_den_u6");
        assert_eq!(columns[22], "cap_opp_den_frontier");
    }

    // ------------------------- truth_price_gap_u6 -------------------------

    #[test]
    fn truth_price_gap_is_the_absolute_difference() {
        let session_end_ns = 10 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![0],
            vec![1_000_000],
            vec![1_000_000],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let truth = day(vec![(
            s.signal_id,
            SignalRelation::Single(episode(0, 0, Some(1_000_777))),
        )]);
        let path = temp_out_path("price_gap");
        write_tsv(&frame, std::slice::from_ref(&s), &truth, &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        lines.next();
        let d1: Vec<&str> = lines.next().expect("D1 row").split('\t').collect();
        assert_eq!(d1[18], "777");
        std::fs::remove_file(&path).ok();
    }

    #[test]
    fn truth_price_gap_is_na_when_the_truth_extreme_price_is_unknown() {
        // The real, current data-access gap: any probe/run population built
        // from AssignmentReader + TruthCoverageReader alone (no A10 leaf)
        // supplies `None` here, and the column must be NA, not a fabricated
        // value.
        let session_end_ns = 10 * BAR_NS;
        let frame = SessionFrame::from_parts_for_test(
            0,
            session_end_ns,
            vec![0],
            vec![1_000_000],
            vec![1_000_000],
            vec![GroupKind::Scalar],
            Vec::new(),
        );
        let s = seed(Side::Low, 0, 0, 1_000_000);
        let truth = day(vec![(
            s.signal_id,
            SignalRelation::Single(episode(0, 0, None)),
        )]);
        let path = temp_out_path("price_gap_na");
        write_tsv(&frame, std::slice::from_ref(&s), &truth, &path).expect("write_tsv succeeds");
        let content = std::fs::read_to_string(&path).expect("file exists");
        let mut lines = content.lines();
        lines.next();
        let d1: Vec<&str> = lines.next().expect("D1 row").split('\t').collect();
        assert_eq!(d1[18], "NA");
        std::fs::remove_file(&path).ok();
    }
}
