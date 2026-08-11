// qr_candidates/roster.hpp — the causal candidate roster and side authentication.
//
// SPEC (evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 2, the
// clauses this file implements, verbatim):
//
//   "Every candidate-registry row with `row_kind=CANDIDATE`, a valid own
//    `visible_ts_ns`, `event_scorable=true`, and primitive policy in the frozen
//    12-policy vocabulary {dc001,dc002,dc003,dc004,dc005,dc006,dc007,dc008,
//    dc010,dc012,dc015,dc020} is admitted at its **own visibility**. Registry
//    rows with `stream_policy_name=UNION` or any unknown/nonprimitive policy
//    remain in a typed census but are `NONPRIMITIVE_CENSUS_ONLY` ..."
//
//   "Exact-join each admitted registry candidate to one raw `row_kind=CANDIDATE`
//    projection row by `(derived_session_ordinal,candidate_id)` and require
//    equal policy, reversal, visibility, and member IDs. Parse projected
//    `member_signal_ids` strictly as a nonempty comma-separated list of unique
//    lowercase 64-hex IDs in ascending lexicographic canonical order, with no
//    whitespace or empty token; `raw_member_count` is only
//    `len(parsed_member_ids)`. Require the exact parsed member list and this
//    derived count to match the registry member list/count. That raw row's
//    nonnull `physical_event_id` is `candidate_physical_key`; missing/duplicate/
//    mismatch is fatal. Every admitted primitive candidate member ID must
//    resolve in its own session. The unique common `physical_event_id` of its
//    resolved members must equal `candidate_physical_key`; cardinality other
//    than one is fatal. Every member's `physical_event_id` must equal that
//    candidate-row key, all members must agree on side, every member visibility
//    must be <= candidate visibility, and each member's policy/reversal must
//    equal that primitive candidate's own declared policy/reversal. ...
//    LOW->LONG and HIGH->SHORT. Missing/mixed/mismatched members make the
//    primitive candidate `SIDE_UNAVAILABLE`, retain it in the primitive
//    denominator, and forbid ENTER."
//
// THE TWO FAILURE GRADES, AND WHY THEY DIFFER.
//
//   * FATAL refuses the candidate and therefore the session. It is reserved for
//     the cases where two sealed authorities CONTRADICT each other — a join
//     that does not resolve one-to-one, a raw cell that disagrees with the
//     registry cell, a member set whose physical identity is not the candidate's
//     physical identity. Nothing scientific can be salvaged from a contradiction
//     between authorities, and the card says so in the word "fatal".
//   * SIDE_UNAVAILABLE is a TYPED SCIENTIFIC STATE, not an error. The data is
//     self-consistent; it simply does not authenticate a side. The candidate
//     STAYS IN THE PRIMITIVE DENOMINATOR (dropping it would silently select the
//     population on an outcome-adjacent property) and ENTER is forbidden for it.
//
// WHAT NEVER ENTERS. `physical_cluster_id`, `cluster_disposition`,
// `cluster_size`, `side`, and every relation/matrix/label/score/outcome column
// are absent from both projections by construction (see rowgroup_table.hpp's
// allowlists), so no code in this file can reach them.
#ifndef QR_CANDIDATES_ROSTER_HPP
#define QR_CANDIDATES_ROSTER_HPP

#include <array>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

#include "qr_candidates/prefix_reader.hpp"
#include "qr_candidates/rowgroup_table.hpp"
#include "qr_core/refusal.hpp"

namespace qr::candidates {

// --- the two projections ----------------------------------------------------

/// The eight columns of `truth_relation_projection.parquet` this program may
/// open. EXACTLY these; the card enumerates them and nothing else exists.
inline constexpr std::array<std::string_view, 8> kProjectionAllowlist = {
    "day",       "row_kind",           "candidate_id", "physical_event_id",
    "stream_policy_name", "stream_reversal_bps", "visible_ts_ns", "member_signal_ids"};

/// Every other leaf of that publication, named so the refusal is explicit
/// rather than implied by absence. `side` heads the list on purpose: it is the
/// answer this work package must DERIVE, and reading it would be the whole
/// experiment's most direct leak.
inline constexpr std::array<std::string_view, 16> kProjectionForbidden = {
    "side",
    "episode_id",
    "related_episode_ids",
    "relation_count",
    "signal_id",
    "plateau_last_group_ordinal",
    "plateau_bar_ordinal",
    "plateau_end_ts_ns",
    "registration_ordinal",
    "confirmation_group_ordinal",
    "visible_bar_ordinal",
    "session_end_ns",
    "event_scorable",
    "price_u6",
    "continuity_ordinal",
    "coincident_ambiguities"};

/// The ten columns of `candidate_action_registry.parquet` this program opens.
inline constexpr std::array<std::string_view, 10> kRegistryAllowlist = {
    "day",           "session_ordinal",     "row_kind",          "candidate_id",
    "stream_policy_name", "stream_reversal_bps", "member_signal_ids", "member_count",
    "visible_ts_ns", "event_scorable"};

/// The registry's final-relation and reachability columns, all refused.
/// `physical_cluster_id` is here BY NAME: the card calls it "an unrelated
/// opaque audit foreign key" that "never substitutes for this member-derived
/// physical key", so this module must not be able to see it at all.
inline constexpr std::array<std::string_view, 16> kRegistryForbidden = {
    "physical_cluster_id",
    "cluster_disposition",
    "cluster_size",
    "d1_reachable",
    "d1_legal_actions",
    "d2_reachable",
    "d2_legal_actions",
    "d3_reachable",
    "d3_legal_actions",
    "cost_cell_id",
    "d2_predecessor",
    "d3_predecessor",
    "registration_ordinal",
    "confirmation_group_ordinal",
    "visible_bar_ordinal",
    "session_end_ns"};

/// The frozen 12-policy primitive vocabulary. Note the gaps: dc009, dc011,
/// dc013, dc014 and dc016..dc019 are NOT primitive, and a row carrying one is
/// census-only exactly like UNION.
inline constexpr std::array<std::string_view, 12> kPrimitivePolicies = {
    "dc001", "dc002", "dc003", "dc004", "dc005", "dc006",
    "dc007", "dc008", "dc010", "dc012", "dc015", "dc020"};

[[nodiscard]] bool is_primitive_policy(std::string_view name) noexcept;

// --- typed states -----------------------------------------------------------

/// What a registry row is, scientifically.
enum class AdmissionClass : std::uint8_t {
  /// row_kind != CANDIDATE. Not part of this roster's population at all.
  NOT_A_CANDIDATE_ROW,
  /// Primitive policy, own visibility, event_scorable=true. The population.
  ADMITTED_PRIMITIVE,
  /// Primitive policy but not scorable, or with no own visibility. Counted,
  /// never admitted, never silently merged with the admitted set.
  PRIMITIVE_NOT_ADMITTED,
  /// UNION or any unknown/nonprimitive policy: typed census only. Creates no
  /// watch, action, prefix membership, feature, sampler, denominator, fit or
  /// score, and is never zero/unknown-coded into one.
  NONPRIMITIVE_CENSUS_ONLY,
};
[[nodiscard]] const char* admission_class_name(AdmissionClass value) noexcept;

/// THE ONE PLACE a registry row's class is decided (card section 2). It exists
/// as a named function, and not as four scattered `if`s inside the build loop,
/// so the four classes can be fixtured directly and so PRIMITIVE_NOT_ADMITTED
/// is a value the code actually produces rather than a comment about one.
///
/// `event_scorable` arrives as a BOOL because the cell is parsed strictly
/// (`parse_bool`: exactly "true" or "false", everything else a DECODE refusal)
/// before it gets here — the review's L2-F1 finding was that `cell == "true"`
/// silently mapped `TRUE`, `1` and every other spelling onto "not scorable",
/// which removes a candidate from the population without a word.
[[nodiscard]] AdmissionClass classify_admission(std::string_view row_kind,
                                                std::string_view policy_name, bool event_scorable,
                                                bool has_own_visibility) noexcept;

/// The authenticated side, or the typed unavailability.
enum class SideState : std::uint8_t { LONG, SHORT, SIDE_UNAVAILABLE };
[[nodiscard]] const char* side_state_name(SideState value) noexcept;

/// Why a side could not be authenticated. Distinct causes stay distinct: the
/// census must never merge "a member is missing" with "the members disagree".
enum class SideUnavailableCause : std::uint8_t {
  NONE,
  MEMBER_UNRESOLVED,
  MIXED_MEMBER_SIDE,
  MEMBER_POLICY_OR_REVERSAL_MISMATCH,
  MEMBER_VISIBILITY_IN_FUTURE,
};
[[nodiscard]] const char* side_unavailable_cause_name(SideUnavailableCause value) noexcept;

/// One admitted primitive candidate, after authentication.
struct CandidateRecord {
  std::uint32_t session_ordinal = 0;
  std::string candidate_id;
  std::string policy_name;
  std::uint64_t reversal_bps = 0;
  std::int64_t visible_ts_ns = 0;
  /// len(parsed member ids) — DERIVED, never a stored aggregate.
  std::uint64_t member_count = 0;
  /// The raw projection row's nonnull physical_event_id, proven equal to the
  /// unique physical identity of the member set.
  std::string candidate_physical_key;
  SideState side = SideState::SIDE_UNAVAILABLE;
  SideUnavailableCause cause = SideUnavailableCause::NONE;
  /// True whenever the side is unavailable. ENTER is a WP7 decision; this flag
  /// is the roster's binding veto on it.
  bool enter_forbidden = true;
};

/// The typed census of one session. The first fourteen counters are the frozen
/// feasibility witness's receipt fields, name for name, so the two runs compare
/// number by number; the rest are the V4 additions.
struct RosterCensus {
  std::uint64_t registry_row_group_rows = 0;
  std::uint64_t registry_candidate_rows = 0;
  std::uint64_t primitive_candidate_rows = 0;
  std::uint64_t nonprimitive_union_census_only_rows = 0;
  std::uint64_t nonprimitive_unknown_census_only_rows = 0;
  std::uint64_t admitted_rows = 0;
  std::uint64_t resolved_rows = 0;
  std::uint64_t missing_member_references = 0;
  std::uint64_t mixed_side_candidates = 0;
  std::uint64_t primitive_member_policy_or_reversal_mismatch_candidates = 0;
  std::uint64_t future_member_candidates = 0;
  std::uint64_t member_count_mismatch_candidates = 0;
  std::uint64_t duplicate_candidate_ids = 0;
  std::uint64_t resolved_long = 0;
  std::uint64_t resolved_short = 0;
  // --- V4 additions ---------------------------------------------------------
  std::uint64_t projection_rows = 0;
  std::uint64_t projection_candidate_rows = 0;
  std::uint64_t side_unavailable_candidates = 0;
  std::uint64_t physical_key_authenticated_candidates = 0;
  /// The two REASONS a primitive candidate was not admitted, kept apart: a row
  /// whose `event_scorable` is false, and a row with no own visibility. Their
  /// sum plus `admitted_rows` is `primitive_candidate_rows`, so the primitive
  /// denominator accounts for every row it counted.
  std::uint64_t primitive_not_admitted_unscorable = 0;
  std::uint64_t primitive_not_admitted_no_visibility = 0;
};

/// The roster of one session: every admitted primitive candidate, in ascending
/// candidate_id order (a total order that exists in the data, never row order).
struct SessionRoster {
  std::uint32_t session_ordinal = 0;
  std::string day;
  std::vector<CandidateRecord> candidates;
  RosterCensus census;
};

// --- the strict member-id parse ---------------------------------------------

/// Parses `member_signal_ids` under the card's five simultaneous laws: nonempty,
/// comma separated, unique, lowercase 64-hex, ascending lexicographic. Any
/// whitespace or empty token refuses. Ascending order is REQUIRED rather than
/// imposed by sorting: the cell is a canonical form, and a cell that is not in
/// canonical form is not the cell the sealing authority wrote.
[[nodiscard]] Expected<std::vector<std::string_view>, Refusal> parse_member_signal_ids(
    std::string_view cell);

// --- the roster -------------------------------------------------------------

/// Builds one session's roster from the three authorities.
///
/// `registry` must be the candidate registry's row group for `ordinal`,
/// `projection` the truth-relation projection's row group for `ordinal`, and
/// `signals` the sealed event-signal set of that same session. Any
/// contradiction between them refuses; a self-consistent failure to
/// authenticate a side is recorded as SIDE_UNAVAILABLE and retained.
[[nodiscard]] Expected<SessionRoster, Refusal> build_session_roster(
    std::uint32_t ordinal, const SessionColumns& registry, const SessionColumns& projection,
    const SessionSignals& signals);

/// Deterministic, field-by-field rendering of a roster: the artifact two-run
/// identity and late-sibling invariance are asserted on.
[[nodiscard]] std::string render_roster(const SessionRoster& roster);

/// Deterministic rendering of a census, one `key\tvalue` line per counter.
[[nodiscard]] std::string render_census(const RosterCensus& census);

}  // namespace qr::candidates

#endif  // QR_CANDIDATES_ROSTER_HPP
