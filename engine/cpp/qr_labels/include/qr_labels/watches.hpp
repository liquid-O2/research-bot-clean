// qr_labels/watches.hpp — the three watches, the decision clock, the authority
// decision-ordinal roster and the unique action rows.
//
// SPEC (verbatim, evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 3):
//   "Each side-authenticated admitted primitive candidate creates three
//    watches:
//    * D0: first registered whole-second clock strictly after own visibility;
//    * D30: first whole-second clock at or after visibility +30s;
//    * D60: last registered whole-second clock at or before visibility +60s,
//      still strictly after visibility. Thus the focal candidate remains inside
//      the inclusive age<=60s set.
//    Out-of-session watches are `CLOCK_UNAVAILABLE`. No D90/D120 row exists in
//    this test. Many watches may converge. First compute `decision_second` from
//    the registered session clock and require
//    `decision_ts_ns=session_start_ns+decision_second*1e9`. Authority
//    `decision_ordinal` is nonlinear: reconstruct the sealed authority clock
//    roster as the sorted union of every registered whole second and every
//    sealed evidence-change timestamp, and verify all persisted label/evidence
//    ordinals. Then exact-join `(session_ordinal,decision_ts_ns,side)` and carry
//    that authority ordinal. The scientific/prediction key
//    `(session_ordinal,decision_ordinal,side)` plus timestamp must be
//    one-to-one; `decision_second` is never substituted for ordinal. A separate
//    many-to-one watch ledger retains candidate ID, opaque physical key, own
//    visibility, stage, policy/reversal/member count, and action key. No
//    candidate multiplicity duplicates a fit or score row."
//
// THE V4 CONSTRUCTION OF THE ROSTER (WP7 brief, verbatim): "the sorted union,
// per session, of every registered whole second and every
// admitted-primitive-candidate visibility timestamp — ordinal = index in that
// roster". The card's "sealed evidence-change timestamp" IS that visibility
// instant: a primitive candidate's evidence set is fixed at its own visibility
// (card section 2, last paragraph), so its visibility is the instant the
// session's evidence changes.
//
// WHY THE ORDINAL IS NOT THE SECOND. The roster is the union of two grids, so
// it is NONLINEAR in time: inserting one visibility between two seconds shifts
// every later ordinal by one and no earlier one at all. That is the mutant
// `test_watches.cpp` fires. `decision_second` is retained beside the ordinal
// for the card's identity check and is never substituted for it.
#ifndef QR_LABELS_WATCHES_HPP
#define QR_LABELS_WATCHES_HPP

#include <array>
#include <cstdint>
#include <span>
#include <string>
#include <string_view>
#include <vector>

#include "qr_clock/session_clock.hpp"
#include "qr_core/refusal.hpp"
#include "qr_core/validity.hpp"
#include "qr_labels/money.hpp"

namespace qr::labels {

/// The three watches of the card. There is no D90 and no D120 in this test,
/// so there is no enumerator for one either.
enum class WatchStage : std::uint8_t { D0 = 0, D30 = 1, D60 = 2 };
inline constexpr std::size_t kWatchStageCount = 3;
[[nodiscard]] const char* watch_stage_name(WatchStage stage) noexcept;
/// The stage's offset from the candidate's own visibility, in nanoseconds
/// (D0 = 0s, D30 = 30s, D60 = 60s).
[[nodiscard]] std::int64_t watch_stage_offset_ns(WatchStage stage) noexcept;

// ---------------------------------------------------------------------------
// The registered whole-second clock.
// ---------------------------------------------------------------------------

/// The session's REGISTERED whole seconds: `session_start_ns + k * 1e9` for
/// every k with that instant inside the half-open frame-A session window. The
/// count comes from the session's OWN registry row (390 bars on most sessions,
/// 210 on the nine early closes), never from a constant.
class DecisionClock {
 public:
  [[nodiscard]] static Expected<DecisionClock, Refusal> from_clock(const SessionClock& clock);

  [[nodiscard]] std::int64_t session_start_ns() const noexcept { return session_start_ns_; }
  [[nodiscard]] std::int64_t session_end_ns() const noexcept { return session_end_ns_; }
  /// How many whole seconds this session registers.
  [[nodiscard]] std::int64_t second_count() const noexcept { return second_count_; }

  /// THE CARD'S IDENTITY: `decision_ts_ns = session_start_ns + second * 1e9`.
  [[nodiscard]] Expected<std::int64_t, Refusal> second_ts(std::int64_t second) const noexcept;
  /// The second index of a registered instant, or a refusal when `ts` is not
  /// one of this session's registered whole seconds.
  [[nodiscard]] Expected<std::int64_t, Refusal> second_of(std::int64_t ts) const noexcept;

  /// D0's rule: the first registered whole second STRICTLY after `ts`, or
  /// `kNoIndex` when the session has none (an out-of-session watch).
  [[nodiscard]] std::int64_t first_second_strictly_after(std::int64_t ts) const noexcept;
  /// D30's rule: the first registered whole second at or after `ts`.
  [[nodiscard]] std::int64_t first_second_at_or_after(std::int64_t ts) const noexcept;
  /// D60's rule: the last registered whole second at or before `ts`.
  [[nodiscard]] std::int64_t last_second_at_or_before(std::int64_t ts) const noexcept;

 private:
  DecisionClock(std::int64_t start, std::int64_t end, std::int64_t seconds) noexcept
      : session_start_ns_(start), session_end_ns_(end), second_count_(seconds) {}

  std::int64_t session_start_ns_ = 0;
  std::int64_t session_end_ns_ = 0;
  std::int64_t second_count_ = 0;
};

// ---------------------------------------------------------------------------
// The authority decision-ordinal roster.
// ---------------------------------------------------------------------------

/// The sorted union of every registered whole second and every admitted
/// primitive candidate's own visibility instant. `decision_ordinal` is the
/// index into THIS vector and nothing else.
class DecisionRoster {
 public:
  /// Builds the roster. `visibilities` may repeat and may arrive in any order;
  /// the union is sorted and deduplicated, so the roster is strictly
  /// increasing by construction — and `build` re-checks that on the OUTPUT
  /// rather than trusting the construction.
  [[nodiscard]] static Expected<DecisionRoster, Refusal> build(
      const DecisionClock& clock, std::span<const std::int64_t> visibilities);

  /// TEST-ONLY: builds a roster from explicit instants WITHOUT the union
  /// construction, so the one-to-one law can be fired by a counterfixture (a
  /// duplicated instant) instead of only by a source mutant.
  [[nodiscard]] static Expected<DecisionRoster, Refusal> from_instants(
      std::vector<std::int64_t> instants);

  [[nodiscard]] std::int64_t size() const noexcept {
    return static_cast<std::int64_t>(instants_.size());
  }
  [[nodiscard]] std::int64_t ts_at(std::int64_t ordinal) const;
  /// The exact join of card section 3. A timestamp that is not on the roster
  /// is a refusal, never a nearest neighbour.
  [[nodiscard]] Expected<std::int64_t, Refusal> ordinal_of(std::int64_t ts) const noexcept;
  [[nodiscard]] std::span<const std::int64_t> instants() const noexcept { return instants_; }

  /// How many of the SUPPLIED visibilities were not themselves registered
  /// whole seconds, and how many were. These count visibilities, not roster
  /// entries: several candidates may share one evidence instant, and the union
  /// keeps one entry for it. `size()` is the authority on entries.
  [[nodiscard]] std::int64_t visibilities_off_second() const noexcept { return visibility_only_; }
  [[nodiscard]] std::int64_t visibilities_on_second() const noexcept {
    return visibility_on_second_;
  }

 private:
  explicit DecisionRoster(std::vector<std::int64_t> instants) : instants_(std::move(instants)) {}

  std::vector<std::int64_t> instants_;
  std::int64_t visibility_only_ = 0;
  std::int64_t visibility_on_second_ = 0;
};

// ---------------------------------------------------------------------------
// The watch ledger and the unique action rows.
// ---------------------------------------------------------------------------

/// One side-authenticated admitted primitive candidate, as the watch builder
/// needs it. Deliberately a plain value type owned by WP7: the roster itself is
/// WP6's authority (`qr::candidates::CandidateRecord`), and copying the six
/// fields the card names keeps the label kernel free of a parquet dependency.
struct WatchCandidate {
  std::string candidate_id;
  /// The opaque physical key. A foreign key in the ledger and NOTHING else:
  /// never a feature, a gate, a sampler or a tie-breaker (card section 2).
  std::string candidate_physical_key;
  std::string policy_name;
  std::uint64_t reversal_bps = 0;
  std::uint64_t member_count = 0;
  std::int64_t visible_ts_ns = 0;
  Side side = Side::LONG;
};

/// One row of the MANY-TO-ONE watch ledger (card section 3). Every field the
/// card enumerates is here, and the action key is the join to the unique
/// scored row.
struct WatchRow {
  std::string candidate_id;
  std::string candidate_physical_key;
  std::string policy_name;
  std::uint64_t reversal_bps = 0;
  std::uint64_t member_count = 0;
  std::int64_t visible_ts_ns = 0;
  Side side = Side::LONG;
  WatchStage stage = WatchStage::D0;

  /// VALID, or CLOCK_UNAVAILABLE for an out-of-session watch. The row is
  /// retained either way — an unavailable watch is a typed state, never a
  /// dropped candidate.
  Validity clock_state = Validity::VALID;
  /// The whole-second index, its instant, and the authority ordinal. All three
  /// are `kNoIndex`/0 when `clock_state` is not VALID.
  std::int64_t decision_second = kNoIndex;
  std::int64_t decision_ts_ns = 0;
  std::int64_t decision_ordinal = kNoIndex;
  /// Index into `WatchPlan::actions`, or `kNoIndex`.
  std::int64_t action_index = kNoIndex;
};

/// One UNIQUE scored/fit row: the (session_ordinal, decision_ordinal, side) key
/// plus the timestamp, and how many watches converged onto it.
struct ActionRow {
  ActionKey key{};
  std::int64_t decision_second = 0;
  std::int64_t watch_count = 0;
  /// Bit `k` set == at least one watch of `WatchStage(k)` converged here.
  std::uint8_t stage_mask = 0;
};

/// Typed counters of the watch build; printed in full, zeros included.
struct WatchCensus {
  std::int64_t candidates = 0;
  std::int64_t watches_built = 0;
  std::int64_t watches_clock_unavailable = 0;
  std::array<std::int64_t, kWatchStageCount> per_stage_built{};
  std::array<std::int64_t, kWatchStageCount> per_stage_clock_unavailable{};
  std::int64_t actions = 0;
  std::int64_t actions_long = 0;
  std::int64_t actions_short = 0;
  std::int64_t converged_watches = 0;  ///< watches beyond the first on their action
  [[nodiscard]] std::string to_tsv(std::string_view label) const;
};

struct WatchPlan {
  /// The many-to-one ledger, in a total deterministic order:
  /// (candidate_id, stage).
  std::vector<WatchRow> ledger;
  /// The unique action rows, ascending by (decision_ordinal, side). This order
  /// is the chronological order WP11's replay consumes, because the roster is
  /// strictly increasing in time.
  std::vector<ActionRow> actions;
  WatchCensus census;
};

/// THE ONE-TO-ONE LAW as a NAMED PRIMITIVE, so the guard is directly testable
/// on a hand-built action list instead of only through a source mutant (the
/// shape `qr_clock::refuse_unless_non_decreasing` established).
///
/// Card section 3: "The scientific/prediction key
/// `(session_ordinal,decision_ordinal,side)` plus timestamp must be
/// one-to-one". That is three checks, and all three are here: the rows are
/// strictly ascending in (decision_ordinal, side) so no key repeats; one
/// ordinal never carries two different instants; and two different ordinals
/// never carry the same instant. Returns the row count.
[[nodiscard]] Expected<std::int64_t, Refusal> refuse_unless_one_to_one(
    std::span<const ActionRow> actions) noexcept;

/// Builds the three watches of every side-authenticated candidate, the
/// many-to-one ledger and the unique action rows.
///
/// Refuses when: a candidate is not side-authenticated; the card's
/// `decision_ts_ns = session_start_ns + decision_second*1e9` identity fails; a
/// watch's instant is not on the authority roster; or the one-to-one law is
/// violated — two different instants sharing one (ordinal, side) key, or one
/// key carrying two different instants.
[[nodiscard]] Expected<WatchPlan, Refusal> build_watches(std::int64_t session_ordinal,
                                                         const DecisionClock& clock,
                                                         const DecisionRoster& roster,
                                                         std::span<const WatchCandidate> candidates);

/// Deterministic field-by-field rendering of the ledger and of the action rows
/// (the artifact two-run identity is asserted on these bytes).
[[nodiscard]] std::string render_watch_ledger(const WatchPlan& plan);

}  // namespace qr::labels

#endif  // QR_LABELS_WATCHES_HPP
