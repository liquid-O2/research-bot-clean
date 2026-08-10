//! Proposal bank (design brief §C "proposal bank"; amendment §A9): the
//! frozen eligibility-first selection rule.
//!
//! This replaces the pre-A9 design ("filters only on pooled recall >= 0.80
//! and sorts by recall then burden"), which Sol's design review (finding 9)
//! showed could publish a bank containing **zero** floor-eligible streams:
//! "Streams A/B/C have recalls .90/.89/.88 but LCBs .76/.78/.79; stream D
//! has recall .87 and LCB .81. Sorting chooses A/B/C and need not add D, so
//! the published proposal bank can contain no floor-eligible stream even
//! though one exists." (`research/review_records/events3_sol_design_review.md`
//! finding 9.) A9's fix, implemented here: filter on the complete
//! point+LCB predicate **first**, then rank/select only among the
//! survivors.
//!
//! # L5 fix (`research/review_records/events23_consolidated_ledger.md`)
//!
//! Two findings from the EVENTS.2+3 consolidated review batch landed
//! together here:
//!
//! - **Sol#11 (P2) / Opus#F3 (P2)** — "LCB eligibility comparison is outside
//!   the pinned estimator and accepts non-finite values" /
//!   "The proposal-bank LCB eligibility is decided in Rust on an `f64`,
//!   duplicating the `>= 0.80` decision the pinned estimator/verifier also
//!   makes." A1: "the verifier recomputes the LCB via the pinned estimator
//!   and requires exact unrounded agreement with the published gate
//!   result." This crate previously accepted an arbitrary `f64` (even
//!   `+inf`) and performed its OWN `lcb >= 0.80` comparison
//!   ([`StreamLcb::lcb`], the old `LCB_FLOOR` constant) — a second,
//!   independently-parsed authority for the exact same threshold decision.
//!   Fixed: [`StreamLcb`] now carries an [`EstimatorVerdict`] (the pinned
//!   estimator's own canonical exact-decimal LCB string PLUS its own
//!   `>= 0.80` boolean); [`is_eligible`] consumes `passes_floor` directly
//!   and performs NO threshold comparison of its own, and [`build_bank`]
//!   rejects a non-finite/malformed `lcb_canonical` as a typed
//!   [`InvalidLcbCanonicalError`] before any eligibility filtering happens.
//! - **Sol#10 (P1) / Opus#F5 (P3)** — "A one- or two-stream frontier is
//!   labeled `SELECTED`" / "Bank publishes a sub-3-member bank as `SELECTED`
//!   when `eligible_count >= 3` but the non-dominated frontier is smaller
//!   than 3." A9: "Fewer than 3 eligible → publish the actual count with
//!   state `BANK_INSUFFICIENT` (honest insufficiency, never padding)." The
//!   previous code only ran this check when `eligible_count < 3`, so a
//!   `>= 3`-eligible-but-mostly-mutually-dominated population (Sol#10's own
//!   A/B/C domination scenario, reproduced as a test below) could still
//!   publish a 1-member bank as `SELECTED`. Fixed: [`build_bank`] now always
//!   computes the non-dominated frontier first and checks ITS length
//!   against 3, unconditionally (no separate `eligible_count < 3`
//!   short-circuit) — `BankState::Insufficient` now carries `eligible_count`,
//!   `frontier_count`, and `members` so a sub-3 frontier is never silently
//!   relabeled `SELECTED` regardless of how many candidates were eligible.

use crate::frontier::{StreamPoint, compare_recall, non_dominated};
use std::fmt;

/// The pinned Python estimator's per-stream verdict (A1/A9). L5 fix
/// (Sol#11/Opus#F3): Rust performs **no** threshold comparison of its own —
/// `passes_floor` is the estimator's own `>= 0.80` decision and is the SOLE
/// authority [`is_eligible`] consults for the LCB conjunct.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EstimatorVerdict {
    /// The unrounded year-stratified-session-block LCB's canonical
    /// exact-decimal string representation, as emitted by the pinned
    /// estimator (A1: "the run receipt pins the estimator file sha256 ...
    /// the verifier recomputes the LCB via the pinned estimator and
    /// requires exact unrounded agreement with the published gate result").
    /// Never parsed into a float for comparison by this crate -- see
    /// [`passes_floor`](Self::passes_floor). Carried (and validated as
    /// well-formed by [`build_bank`]) purely so the published bank is
    /// self-describing/auditable against the pinned estimator's own output,
    /// without this crate ever becoming a second authority for the `>= 0.80`
    /// decision.
    pub lcb_canonical: String,
    /// The pinned estimator's own `unrounded LCB >= 0.80` decision (A1/A9).
    /// This crate consumes this boolean directly; it never re-derives it
    /// from `lcb_canonical` or from any other transported/re-parsed value.
    pub passes_floor: bool,
}

/// One candidate stream's full bank input: its gate position plus the
/// pinned estimator's [`EstimatorVerdict`] (A9: "LCB value is an INPUT
/// (computed externally by the pinned Python estimator; metrics ... accepts
/// its result for bank filtering via a function parameter)").
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StreamLcb {
    pub point: StreamPoint,
    pub verdict: EstimatorVerdict,
}

/// A9's full frozen eligibility predicate: `5*hits >= 4*truths_denominator`
/// (the exact-integer form of `recall >= 0.80`) AND the pinned estimator's
/// own `passes_floor` boolean (L5 fix: NOT a local LCB comparison -- see the
/// module doc's Sol#11/Opus#F3 note). "Equality cases resolve toward
/// inclusion for the ≥ comparisons as written" (A9): the recall conjunct
/// uses `>=`, and `passes_floor` is already the estimator's own inclusive
/// `>= 0.80` decision.
#[must_use]
pub fn is_eligible(point: &StreamPoint, verdict: &EstimatorVerdict) -> bool {
    let recall_floor =
        5_u128 * u128::from(point.hits) >= 4_u128 * u128::from(point.truths_denominator);
    recall_floor && verdict.passes_floor
}

/// Whether the published bank is a complete 3-5-member selection, or an
/// honest under-3 shortfall (A9: "Fewer than 3 eligible → publish the
/// actual count with state `BANK_INSUFFICIENT` (honest insufficiency, never
/// padding)").
///
/// L5 fix (Sol#10/Opus#F5): [`Insufficient`](Self::Insufficient) is now
/// reached whenever the eligible non-dominated FRONTIER has fewer than 3
/// members -- not only when `eligible_count < 3` -- so a `>= 3`-eligible
/// population that is mostly mutually dominated (Sol#10's A/B/C scenario)
/// can never be mislabeled `Selected` with fewer than 3 streams. It carries
/// its own `eligible_count`/`frontier_count`/`members` so a consumer never
/// has to guess which count explains the shortfall.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum BankState {
    Selected,
    Insufficient {
        /// The total count of streams that passed [`is_eligible`],
        /// regardless of whether they survived non-domination.
        eligible_count: usize,
        /// The size of the eligible non-dominated frontier (`members.len()`,
        /// carried separately for callers that only want the count).
        frontier_count: usize,
        /// Every eligible non-dominated stream (ranked), published
        /// honestly -- NEVER padded with a dominated or ineligible stream.
        members: Vec<StreamPoint>,
    },
}

impl BankState {
    #[must_use]
    pub const fn wire(&self) -> &'static str {
        match self {
            Self::Selected => "SELECTED",
            Self::Insufficient { .. } => "BANK_INSUFFICIENT",
        }
    }
}

/// The published proposal bank.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ProposalBank {
    pub state: BankState,
    /// The selected (or, if [`BankState::Insufficient`], every eligible
    /// non-dominated) streams, in published (ranked) order -- identical to
    /// `state`'s own `members` in the `Insufficient` case, duplicated here
    /// so callers can read `streams`/`eligible_count` uniformly regardless
    /// of `state`.
    pub streams: Vec<StreamPoint>,
    /// The total count of streams that passed [`is_eligible`], regardless
    /// of whether they made the final selection.
    pub eligible_count: usize,
}

/// A9's extension rule is written directly in terms of raw `hits`/`burden`
/// (`100·hits_c ≥ 99·hits_3`, `10·burden_c ≤ 9·burden_3`), which only
/// encodes the intended *recall* comparison when every candidate shares the
/// same `truths_denominator`. A caller passing streams with differing
/// denominators would silently misapply the frozen formula, so this is a
/// typed error instead of a silent miscomparison.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct MismatchedTruthsDenominatorError;

impl fmt::Display for MismatchedTruthsDenominatorError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "bank candidates do not share one truths_denominator; A9's extension \
             rule is frozen in terms of raw hits/burden and requires it"
        )
    }
}

impl std::error::Error for MismatchedTruthsDenominatorError {}

/// L5 fix (Sol#11/Opus#F3): a candidate's `lcb_canonical` is not the pinned
/// estimator's registered exact-decimal representation. Carries the
/// offending string for diagnosis. This crate never compares the parsed
/// value against `0.80` -- this error exists purely to reject a malformed
/// or non-finite (`"inf"`/`"-inf"`/`"nan"`/exponent-notation/garbage)
/// canonical value before it is ever published, per the finding's "At
/// minimum reject non-finite values and compare only a canonical
/// exact-decimal representation" minimal fix.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct InvalidLcbCanonicalError(pub String);

impl fmt::Display for InvalidLcbCanonicalError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "estimator lcb_canonical {:?} is not a well-formed finite exact-decimal \
             string; Rust performs no threshold comparison of its own and requires a \
             well-formed canonical value from the pinned estimator",
            self.0
        )
    }
}

impl std::error::Error for InvalidLcbCanonicalError {}

/// [`build_bank`]'s error type: either candidates share no common
/// `truths_denominator`, or one candidate's `lcb_canonical` is malformed or
/// non-finite (L5 fix, Sol#11/Opus#F3).
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum BankError {
    MismatchedTruthsDenominator(MismatchedTruthsDenominatorError),
    InvalidLcbCanonical(InvalidLcbCanonicalError),
}

impl fmt::Display for BankError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::MismatchedTruthsDenominator(e) => e.fmt(f),
            Self::InvalidLcbCanonical(e) => e.fmt(f),
        }
    }
}

impl std::error::Error for BankError {}

impl From<MismatchedTruthsDenominatorError> for BankError {
    fn from(e: MismatchedTruthsDenominatorError) -> Self {
        Self::MismatchedTruthsDenominator(e)
    }
}

impl From<InvalidLcbCanonicalError> for BankError {
    fn from(e: InvalidLcbCanonicalError) -> Self {
        Self::InvalidLcbCanonical(e)
    }
}

/// Validates that `s` is a well-formed finite exact-decimal string: an
/// optional leading `-`, one or more ASCII digits, optionally `.` followed
/// by one or more ASCII digits -- NEVER exponent notation, `inf`/`infinity`/
/// `nan` (in any case), leading/trailing whitespace, or empty. This is the
/// ONLY numeric handling of the estimator's LCB this crate performs: a
/// well-formedness/finiteness check, never a `>= 0.80` comparison (L5 fix,
/// Sol#11/Opus#F3 -- that decision belongs solely to
/// [`EstimatorVerdict::passes_floor`]).
///
/// # Errors
///
/// Returns [`InvalidLcbCanonicalError`] if `s` does not match the grammar
/// above (this also rejects every non-finite token Rust's own `f64::parse`
/// would otherwise accept, since those never match the digits-only grammar).
fn validate_lcb_canonical(s: &str) -> Result<(), InvalidLcbCanonicalError> {
    let malformed = || InvalidLcbCanonicalError(s.to_owned());
    let body = s.strip_prefix('-').unwrap_or(s);
    if body.is_empty() {
        return Err(malformed());
    }
    let mut parts = body.splitn(2, '.');
    let int_part = parts.next().unwrap_or("");
    let frac_part = parts.next();
    if int_part.is_empty() || !int_part.bytes().all(|b| b.is_ascii_digit()) {
        return Err(malformed());
    }
    if let Some(frac) = frac_part
        && (frac.is_empty() || !frac.bytes().all(|b| b.is_ascii_digit()))
    {
        return Err(malformed());
    }
    Ok(())
}

/// Ranks eligible streams by A9's frozen tie order: `(recall desc, burden
/// asc, registration_order asc)`.
fn rank(mut points: Vec<StreamPoint>) -> Vec<StreamPoint> {
    points.sort_by(|a, b| {
        compare_recall(b, a)
            .then_with(|| a.burden.cmp(&b.burden))
            .then_with(|| a.registration_order.cmp(&b.registration_order))
    });
    points
}

/// Ruling E21(c) / E22(b): the single BEST floor-eligible stream by A9's
/// frozen tie order `(recall desc, burden asc, registration_order asc)` --
/// the IDENTICAL ranking [`rank`] (this module's own proposal-bank ranking)
/// applies, extracted here so `stage1 metrics` (the writer, choosing the
/// `session_recall.tsv`/`stream_summary.tsv` `is_gate` stream) and
/// `stage1 verify-stage1` (the verifier, `publish::gate`'s
/// `StageGate::recompute`) share ONE implementation of the registered rule
/// rather than two independently maintained copies (E22(b): "the writer and
/// verifier share one rule; first-registered-order selection is struck").
///
/// Note this never restricts to the non-dominated frontier first (unlike
/// [`build_bank`]'s own multi-member selection): the single top-ranked
/// eligible point by this exact tie order can never be dominated by another
/// eligible point (domination would require an equal-or-better rank on both
/// axes with one strict, which is exactly what this ranking already orders
/// first) -- so ranking the full eligible set and taking the first is
/// equivalent, and simpler.
///
/// Returns `None` iff no candidate is floor-eligible ([`is_eligible`]) --
/// E21(a)'s own failure condition; the caller decides what that means for
/// its own acceptance/publication logic, this function only answers "which
/// stream, if any, is the registered gate stream".
#[must_use]
pub fn best_eligible_stream(candidates: &[StreamLcb]) -> Option<StreamPoint> {
    let eligible: Vec<StreamPoint> = candidates
        .iter()
        .filter(|candidate| is_eligible(&candidate.point, &candidate.verdict))
        .map(|candidate| candidate.point.clone())
        .collect();
    rank(eligible).into_iter().next()
}

/// Builds the proposal bank per A9's frozen rule, as corrected by the L5
/// review-batch fix (module doc; Sol#10/Sol#11/Opus#F3/Opus#F5):
///
/// 1. Every candidate's `lcb_canonical` must be a well-formed finite
///    exact-decimal string ([`validate_lcb_canonical`]) -- a typed error
///    otherwise, checked before any filtering.
/// 2. Filter every candidate through [`is_eligible`] (recall floor AND the
///    pinned estimator's own `passes_floor` -- never a local `>= 0.80`
///    comparison).
/// 3. Take the non-dominated subset of the eligible streams (recall vs
///    burden), ranked by `(recall desc, burden asc, registration_order
///    asc)`.
/// 4. **Unconditionally** (L5 fix -- no more `eligible_count < 3`
///    short-circuit): fewer than 3 members in that frontier →
///    [`BankState::Insufficient`], publishing every frontier member
///    (never padded with a dominated or ineligible stream).
/// 5. Otherwise: take the top 3 of the frontier, then add up to 2 more from
///    the remaining ranked frontier streams, each iff `100·hits_c ≥
///    99·hits_3` (within 1% recall of the 3rd selected, both against the
///    fixed 3rd-place reference) AND `10·burden_c ≤ 9·burden_3` (at least
///    10% lower burden).
///
/// # Errors
///
/// Returns [`BankError::MismatchedTruthsDenominator`] if `candidates` do not
/// all share one `truths_denominator`, or
/// [`BankError::InvalidLcbCanonical`] if any candidate's `lcb_canonical` is
/// malformed or non-finite (see each error's own doc comment).
pub fn build_bank(candidates: &[StreamLcb]) -> Result<ProposalBank, BankError> {
    if let Some(first) = candidates.first()
        && candidates
            .iter()
            .any(|c| c.point.truths_denominator != first.point.truths_denominator)
    {
        return Err(MismatchedTruthsDenominatorError.into());
    }

    for candidate in candidates {
        validate_lcb_canonical(&candidate.verdict.lcb_canonical)?;
    }

    let eligible: Vec<StreamPoint> = candidates
        .iter()
        .filter(|candidate| is_eligible(&candidate.point, &candidate.verdict))
        .map(|candidate| candidate.point.clone())
        .collect();
    let eligible_count = eligible.len();

    // L5 fix (Sol#10/Opus#F5): the frontier is now ALWAYS computed and its
    // length checked against 3, regardless of `eligible_count` -- the old
    // code only ran this check inside an `eligible_count < 3` branch, so a
    // `>= 3`-eligible-but-mostly-dominated population could still reach the
    // `Selected` path below with fewer than 3 frontier members.
    let frontier = rank(non_dominated(&eligible));
    let frontier_count = frontier.len();
    if frontier_count < 3 {
        return Ok(ProposalBank {
            state: BankState::Insufficient {
                eligible_count,
                frontier_count,
                members: frontier.clone(),
            },
            streams: frontier,
            eligible_count,
        });
    }

    let mut selected: Vec<StreamPoint> = frontier[..3].to_vec();
    let third = &frontier[2];
    for candidate in &frontier[3..] {
        if selected.len() >= 5 {
            break;
        }
        let recall_within_one_pct =
            100_u128 * u128::from(candidate.hits) >= 99_u128 * u128::from(third.hits);
        let burden_ten_pct_lower =
            10_u128 * u128::from(candidate.burden) <= 9_u128 * u128::from(third.burden);
        if recall_within_one_pct && burden_ten_pct_lower {
            selected.push(candidate.clone());
        }
    }

    Ok(ProposalBank {
        state: BankState::Selected,
        streams: selected,
        eligible_count,
    })
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
            stream: crate::session::StreamId::new(name, 40),
            hits,
            truths_denominator,
            burden,
            registration_order: order,
        }
    }

    /// Builds an [`EstimatorVerdict`] for tests: `passes_floor` is supplied
    /// directly (as the pinned estimator would), never derived from
    /// `lcb_canonical` by this crate.
    fn verdict(lcb_canonical: &str, passes_floor: bool) -> EstimatorVerdict {
        EstimatorVerdict {
            lcb_canonical: lcb_canonical.to_owned(),
            passes_floor,
        }
    }

    fn candidate(
        name: &str,
        hits: u64,
        denom: u64,
        burden: u64,
        order: u64,
        lcb_canonical: &str,
        passes_floor: bool,
    ) -> StreamLcb {
        StreamLcb {
            point: point(name, hits, denom, burden, order),
            verdict: verdict(lcb_canonical, passes_floor),
        }
    }

    // ------------------------- F9 scenario (verbatim numbers) -------------------------
    //
    // research/review_records/events3_sol_design_review.md finding 9:
    // "Streams A/B/C have recalls .90/.89/.88 but LCBs .76/.78/.79; stream D
    // has recall .87 and LCB .81." All four pass the recall floor (>= .80);
    // only D passes the LCB floor. The fixed rule must publish D (the only
    // floor-eligible stream), never A/B/C.

    #[test]
    fn f9_scenario_only_the_lcb_eligible_stream_enters_the_bank() {
        let candidates = vec![
            candidate("A", 90, 100, 10, 0, "0.7600000000", false),
            candidate("B", 89, 100, 11, 1, "0.7800000000", false),
            candidate("C", 88, 100, 12, 2, "0.7900000000", false),
            candidate("D", 87, 100, 13, 3, "0.8100000000", true),
        ];
        let bank = build_bank(&candidates).expect("build_bank");

        assert_eq!(bank.eligible_count, 1);
        assert_eq!(
            bank.state,
            BankState::Insufficient {
                eligible_count: 1,
                frontier_count: 1,
                members: vec![point("D", 87, 100, 13, 3)],
            }
        );
        assert_eq!(bank.streams.len(), 1);
        assert_eq!(bank.streams[0].stream.policy_name(), "D");
    }

    // ------------------------- eligibility: pinned-estimator boolean, no local comparison -------------------------

    #[test]
    fn eligibility_consumes_the_pinned_estimators_boolean_verdict_directly() {
        // L5 fix (Sol#11/Opus#F3): `is_eligible` performs NO local LCB
        // comparison -- only `passes_floor` (the estimator's own decision)
        // and the exact-integer recall floor matter. A canonical string
        // whose *numeric value* would suggest the opposite outcome must not
        // change the result: the estimator's boolean is the sole authority.
        let p = point("a", 90, 100, 0, 0);
        assert!(is_eligible(&p, &verdict("0.0001000000", true)));
        assert!(!is_eligible(&p, &verdict("0.9999000000", false)));
    }

    #[test]
    fn recall_floor_boundary_is_inclusive_at_exact_equality() {
        // 5*80 == 4*100 exactly ("equality cases resolve toward inclusion").
        let p = point("a", 80, 100, 0, 0);
        assert!(is_eligible(&p, &verdict("0.8000000000", true)));
    }

    #[test]
    fn one_below_the_recall_floor_is_ineligible() {
        let p = point("a", 79, 100, 0, 0);
        assert!(!is_eligible(&p, &verdict("0.9000000000", true)));
    }

    #[test]
    fn recall_floor_true_but_estimator_says_no_is_ineligible() {
        let p = point("a", 90, 100, 0, 0);
        assert!(!is_eligible(&p, &verdict("0.9000000000", false)));
    }

    // ------------------------- L5 fix: malformed/non-finite lcb_canonical -------------------------

    #[test]
    fn non_finite_canonical_is_a_typed_error() {
        for bad in ["inf", "-inf", "infinity", "nan", "NaN", "Infinity"] {
            let candidates = vec![candidate("A", 90, 100, 10, 0, bad, true)];
            assert_eq!(
                build_bank(&candidates).unwrap_err(),
                BankError::InvalidLcbCanonical(InvalidLcbCanonicalError(bad.to_owned())),
                "expected {bad:?} to be rejected as non-finite"
            );
        }
    }

    #[test]
    fn malformed_canonical_is_a_typed_error() {
        for bad in ["", "-", ".", "0.", "not-a-number", "0..8", "1.2.3", " 0.80"] {
            let candidates = vec![candidate("A", 90, 100, 10, 0, bad, true)];
            assert!(
                matches!(
                    build_bank(&candidates),
                    Err(BankError::InvalidLcbCanonical(_))
                ),
                "expected {bad:?} to be rejected as malformed"
            );
        }
    }

    #[test]
    fn scientific_notation_canonical_is_rejected_not_exact_decimal() {
        // "Exact-decimal" is a textual contract, not "whatever f64::parse
        // accepts" -- exponent notation is well-formed IEEE-754 input but is
        // not the registered canonical form.
        let candidates = vec![candidate("A", 90, 100, 10, 0, "8e-1", true)];
        assert!(matches!(
            build_bank(&candidates),
            Err(BankError::InvalidLcbCanonical(_))
        ));
    }

    #[test]
    fn well_formed_canonical_values_are_accepted() {
        for good in ["0.8000000000", "0", "1", "-0.5", "123.456"] {
            let candidates = vec![candidate("A", 90, 100, 10, 0, good, true)];
            assert!(
                build_bank(&candidates).is_ok(),
                "expected {good:?} to be accepted"
            );
        }
    }

    #[test]
    fn invalid_canonical_is_rejected_before_mismatched_denominator_would_even_matter() {
        // A single-candidate list can never trigger the denominator-mismatch
        // check, so this also confirms the canonical validation runs
        // independently of it.
        let candidates = vec![candidate("A", 90, 100, 10, 0, "garbage", true)];
        assert!(matches!(
            build_bank(&candidates),
            Err(BankError::InvalidLcbCanonical(_))
        ));
    }

    // ------------------------- frontier + top-3 selection -------------------------

    #[test]
    fn frontier_excludes_a_dominated_stream_then_selects_the_top_three_by_recall() {
        let candidates = vec![
            candidate("A", 900, 1000, 100, 0, "0.8500000000", true), // recall .900, burden 100
            candidate("B", 895, 1000, 90, 1, "0.8500000000", true),  // recall .895, burden 90
            candidate("C", 890, 1000, 80, 2, "0.8500000000", true),  // recall .890, burden 80
            candidate("D", 850, 1000, 95, 3, "0.8500000000", true), // dominated by B (lower recall, higher burden)
            candidate("E", 888, 1000, 79, 4, "0.8500000000", true), // recall .888, burden 79 -- fails the extension burden test vs C
        ];
        let bank = build_bank(&candidates).expect("build_bank");
        assert_eq!(bank.eligible_count, 5);
        assert_eq!(bank.state, BankState::Selected);
        let names: Vec<&str> = bank
            .streams
            .iter()
            .map(|p| p.stream.policy_name())
            .collect();
        // D is dominated (excluded from the frontier entirely); E fails the
        // extension's burden test against C (10*79=790 > 9*80=720), so the
        // bank is exactly the top three by recall.
        assert_eq!(names, vec!["A", "B", "C"]);
    }

    #[test]
    fn extension_adds_a_fourth_stream_when_both_conditions_hold() {
        let candidates = vec![
            candidate("A", 900, 1000, 100, 0, "0.8500000000", true),
            candidate("B", 895, 1000, 90, 1, "0.8500000000", true),
            candidate("C", 890, 1000, 80, 2, "0.8500000000", true),
            // recall within 1% of C: 100*888 = 88800 >= 99*890 = 88110 (true).
            // burden >= 10% lower than C: 10*70 = 700 <= 9*80 = 720 (true).
            candidate("E", 888, 1000, 70, 3, "0.8500000000", true),
        ];
        let bank = build_bank(&candidates).expect("build_bank");
        let names: Vec<&str> = bank
            .streams
            .iter()
            .map(|p| p.stream.policy_name())
            .collect();
        assert_eq!(names, vec!["A", "B", "C", "E"]);
    }

    #[test]
    fn extension_caps_at_five_total_streams() {
        let candidates = vec![
            candidate("A", 900, 1000, 100, 0, "0.8500000000", true),
            candidate("B", 895, 1000, 90, 1, "0.8500000000", true),
            candidate("C", 890, 1000, 80, 2, "0.8500000000", true),
            candidate("D", 889, 1000, 70, 3, "0.8500000000", true),
            candidate("E", 888, 1000, 60, 4, "0.8500000000", true),
            candidate("F", 887, 1000, 50, 5, "0.8500000000", true),
        ];
        let bank = build_bank(&candidates).expect("build_bank");
        assert!(bank.streams.len() <= 5);
    }

    // ------------------------- honest insufficiency -------------------------

    #[test]
    fn zero_eligible_streams_is_insufficient_with_an_empty_bank() {
        let candidates = vec![candidate("A", 90, 100, 10, 0, "0.5000000000", false)];
        let bank = build_bank(&candidates).expect("build_bank");
        assert_eq!(
            bank.state,
            BankState::Insufficient {
                eligible_count: 0,
                frontier_count: 0,
                members: vec![],
            }
        );
        assert_eq!(bank.eligible_count, 0);
        assert!(bank.streams.is_empty());
    }

    #[test]
    fn empty_candidate_list_is_insufficient() {
        let bank = build_bank(&[]).expect("build_bank");
        assert_eq!(
            bank.state,
            BankState::Insufficient {
                eligible_count: 0,
                frontier_count: 0,
                members: vec![],
            }
        );
        assert_eq!(bank.eligible_count, 0);
    }

    // ------------------------- L5 fix: Sol#10's A/B/C domination scenario -------------------------
    //
    // research/review_records/events23_sol_adversarial.md finding 10:
    // "denominator 8,914 and LCB 0.80 for all, let A=(8000 hits, burden 1),
    // B=(7500,2), and C=(7200,3). All three clear the point floor, but A
    // dominates B and C, so the frontier contains only A. The code
    // publishes one stream with SELECTED, even though its own state
    // documentation defines selected as a complete 3-5-member result."

    #[test]
    fn sol10_a_dominates_b_and_c_is_insufficient_not_selected() {
        let candidates = vec![
            candidate("A", 8000, 8914, 1, 0, "0.8000000000", true),
            candidate("B", 7500, 8914, 2, 1, "0.8000000000", true),
            candidate("C", 7200, 8914, 3, 2, "0.8000000000", true),
        ];
        let bank = build_bank(&candidates).expect("build_bank");

        assert_eq!(bank.eligible_count, 3);
        // A dominates BOTH B (higher hits, lower burden) and C, so the
        // non-dominated frontier is exactly {A}: size 1, never padded, and
        // never mislabeled SELECTED.
        assert_eq!(
            bank.state,
            BankState::Insufficient {
                eligible_count: 3,
                frontier_count: 1,
                members: vec![point("A", 8000, 8914, 1, 0)],
            }
        );
        assert_eq!(bank.streams, vec![point("A", 8000, 8914, 1, 0)]);
    }

    // ------------------------- error contract -------------------------

    #[test]
    fn mismatched_truths_denominator_is_a_typed_error() {
        let candidates = vec![
            candidate("A", 90, 100, 10, 0, "0.8500000000", true),
            candidate("B", 900, 1000, 10, 1, "0.8500000000", true),
        ];
        assert_eq!(
            build_bank(&candidates).unwrap_err(),
            BankError::MismatchedTruthsDenominator(MismatchedTruthsDenominatorError)
        );
    }
}
