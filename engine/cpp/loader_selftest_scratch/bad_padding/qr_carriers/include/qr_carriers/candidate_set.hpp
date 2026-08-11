// qr_carriers/candidate_set.hpp — THE 24-FIELD CANDIDATE-SET ROWS.
//
// SPEC (evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 5, verbatim):
//
//   "The prefix candidate-set encoder receives, per visible candidate, 24
//    fields: one-hot policy vocabulary exactly `{dc001,dc002,dc003,dc004,dc005,
//    dc006,dc007,dc008,dc010,dc012,dc015,dc020}`, reversal/20, log1p member
//    count, log1p age seconds, own/opposite/mixed/unavailable relation one-hot,
//    and visibility-in-last-{1,5,15,30,60}s flags. Shared element MLP
//    24->32->32 (SiLU); set mean+max gives 64."
//
// SPEC (section 2): "At a decision, the causal context is the full set of
// admitted primitive candidates whose own visibility is strictly earlier than
// the decision and no more than 60s old. Candidate member IDs are foreign keys
// only; own `member_count` is lawful because that primitive candidate's member
// set is fixed at its visibility. No nonprimitive row or later-visible sibling
// contributes."
//
// 12 + 1 + 1 + 1 + 4 + 5 = 24, static_asserted below.
//
// THE FOUR-WAY RELATION IS THE ROSTER'S OWN TYPED VOCABULARY, not a new one.
// qr_candidates resolves a candidate to LONG, SHORT, or SIDE_UNAVAILABLE with a
// distinct cause, and the card's four relation slots map onto exactly that:
//   own         = the candidate's authenticated side equals the action's side;
//   opposite    = it is the other side;
//   mixed       = SIDE_UNAVAILABLE because its members DISAGREED on side
//                 (SideUnavailableCause::MIXED_MEMBER_SIDE) — the one cause that
//                 is about a mixture rather than an absence;
//   unavailable = SIDE_UNAVAILABLE for any other cause.
// Collapsing "mixed" into "unavailable" would merge two census categories the
// roster keeps distinct, which the card's own "never silently zero/unknown-
// coded" rule forbids.
//
// AGE IS IN SECONDS, as section 5 words it ("log1p age seconds"), while every
// section-4 age stays in log1p(microseconds); see the note in transforms.hpp.
// The visibility-in-last-{1,5,15,30,60}s flags are inclusive (`age <= k`),
// because section 2 admits the visible set as "no more than 60s old".
//
// THE SET IS RAGGED AND IS NEVER CAPPED (orchestrator ruling, 2026-08-10).
// Section 2 defines the causal context as "the full set of admitted primitive
// candidates whose own visibility is strictly earlier than the decision and no
// more than 60s old" — a count, not a budget. APPENDIX C4's `candset [N,64,24]`
// sketch is amended on the orchestrator's side: the block below is CSR
// (concatenated 24-field rows plus per-decision offsets), and the measured
// session-125 maximum is 362 visible candidates at one decision, so a 64-row
// cap would silently drop two thirds of the largest sets with no stated rule for
// choosing which. (JSA's separate 64-TOKEN cap is a different object and stands.)
//
// THE CSR INVARIANT IS THE ONE qr_nbbo ALREADY PAID FOR: `offsets` carries
// `rows() + 1` entries and an EMPTY block holds `{0}`, never `{}` — the frozen
// reader's own 2026-08-05 probe caught a derived default building offsets one
// short on every real session while hand-built fixtures satisfied it.
#ifndef QR_CARRIERS_CANDIDATE_SET_HPP
#define QR_CARRIERS_CANDIDATE_SET_HPP

#include <array>
#include <cstdint>
#include <span>
#include <string_view>
#include <vector>

#include "qr_carriers/channels.hpp"
#include "qr_carriers/transforms.hpp"
#include "qr_core/refusal.hpp"

namespace qr::carriers {

/// The frozen 12-policy primitive vocabulary, in the card's own order. It is
/// restated here (rather than reached for through qr_candidates) because the
/// ONE-HOT ORDER is a model-facing frozen layout, not a roster detail: a change
/// in the roster's ordering must not silently permute a feature column.
inline constexpr std::array<std::string_view, 12> kPolicyVocabulary{
    "dc001", "dc002", "dc003", "dc004", "dc005", "dc006",
    "dc007", "dc008", "dc010", "dc012", "dc015", "dc020"};
inline constexpr std::size_t kPolicyVocabularySize = 12;

/// The five visibility-recency horizons, in the card's own order.
inline constexpr std::array<std::int64_t, 5> kVisibilityFlagSeconds{1, 5, 15, 30, 60};
inline constexpr std::size_t kVisibilityFlagCount = 5;

/// The candidate's relation to the action being scored.
enum class CandidateRelation : std::uint8_t { OWN = 0, OPPOSITE = 1, MIXED = 2, UNAVAILABLE = 3 };
inline constexpr std::size_t kCandidateRelationCount = 4;
[[nodiscard]] const char* candidate_relation_name(CandidateRelation relation) noexcept;

/// The frozen field layout.
enum CandidateSetField : std::size_t {
  kCandPolicyOneHot = 0,                                        // 12 fields
  kCandReversalOver20 = kCandPolicyOneHot + kPolicyVocabularySize,
  kCandLog1pMemberCount = kCandReversalOver20 + 1,
  kCandLog1pAgeSeconds = kCandLog1pMemberCount + 1,
  kCandRelationOneHot = kCandLog1pAgeSeconds + 1,               // 4 fields
  kCandVisibilityFlags = kCandRelationOneHot + kCandidateRelationCount,  // 5 fields
};
inline constexpr std::size_t kCandidateSetFieldCount =
    kCandVisibilityFlags + kVisibilityFlagCount;
static_assert(kCandidateSetFieldCount == 24, "section 5: 24 candidate-set fields");

/// The reversal divisor, from the card's own "reversal/20".
inline constexpr double kReversalDivisor = 20.0;

[[nodiscard]] std::string_view candidate_set_field_name(std::size_t field);
/// False for the two one-hot blocks and the five flags; true for the three
/// continuous fields. "Binary/categorical/mask fields are never centered or
/// scaled."
[[nodiscard]] bool candidate_set_field_is_continuous(std::size_t field) noexcept;

/// One visible candidate, as the encoder reads it. Every field comes from the
/// roster; nothing is recomputed here.
struct VisibleCandidate {
  /// Index into `kPolicyVocabulary`, or `kPolicyVocabularySize` when the policy
  /// is not primitive. A nonprimitive row never reaches this encoder (it "enters
  /// no prefix set"), so the out-of-vocabulary index exists to REFUSE, not to
  /// zero-code.
  std::size_t policy_index = kPolicyVocabularySize;
  std::int64_t reversal_bps = 0;
  std::int64_t member_count = 0;
  /// The candidate's own visibility, frame-A nanoseconds.
  std::int64_t visible_ts_ns_a = 0;
  CandidateRelation relation = CandidateRelation::UNAVAILABLE;
};

/// Resolves a policy name to its frozen one-hot index, or `kPolicyVocabularySize`.
[[nodiscard]] std::size_t policy_index_of(std::string_view policy_name) noexcept;

/// One candidate-set row: 24 values with their parallel presence bits.
struct CandidateSetRow {
  std::array<double, kCandidateSetFieldCount> value{};
  std::array<Validity, kCandidateSetFieldCount> validity{};

  CandidateSetRow() noexcept { validity.fill(Validity::MISSING); }
  void set(std::size_t field, Typed<double> typed) noexcept {
    value[field] = typed.v == Validity::VALID ? typed.value : 0.0;
    validity[field] = typed.v;
  }
  [[nodiscard]] bool presence(std::size_t field) const noexcept {
    return validity[field] == Validity::VALID;
  }
};

/// Builds one row. Refuses a candidate whose policy is out of vocabulary or
/// whose visibility is not strictly earlier than the cutoff — both are roster
/// contradictions, not maskable data states.
[[nodiscard]] Expected<CandidateSetRow, Refusal> build_candidate_set_row(
    const VisibleCandidate& candidate, std::int64_t cutoff_ns_a);

/// The RAGGED candidate-set block of one session: every decision's rows,
/// concatenated, with CSR offsets. This is the emitter interface — WP10 writes
/// `values`/`validity` as flat arrays and `offsets` beside them.
class CandidateSetBlock {
 public:
  CandidateSetBlock() { offsets_.push_back(0); }

  /// Appends ONE decision's visible-candidate rows, in the order given (the
  /// caller's order is the roster's own visibility order; nothing is sorted or
  /// truncated here).
  [[nodiscard]] Expected<std::size_t, Refusal> push_decision(
      std::span<const CandidateSetRow> rows);

  /// Decisions appended so far.
  [[nodiscard]] std::size_t decisions() const noexcept { return offsets_.size() - 1U; }
  /// Rows of decision `index`.
  [[nodiscard]] std::size_t row_count(std::size_t index) const;
  /// Field `field` of row `row` of decision `index`.
  [[nodiscard]] double value_at(std::size_t index, std::size_t row, std::size_t field) const;
  [[nodiscard]] Validity validity_at(std::size_t index, std::size_t row,
                                     std::size_t field) const;
  /// The largest row count over all decisions — the receipt number that shows
  /// what a fixed-width cap would have cost.
  [[nodiscard]] std::size_t max_rows() const noexcept { return max_rows_; }
  [[nodiscard]] std::size_t total_rows() const noexcept {
    return values_.size() / kCandidateSetFieldCount;
  }

  [[nodiscard]] const std::vector<double>& values() const noexcept { return values_; }
  [[nodiscard]] const std::vector<Validity>& validity() const noexcept { return validity_; }
  /// `decisions() + 1` entries, always — `{0}` when empty.
  [[nodiscard]] const std::vector<std::uint32_t>& offsets() const noexcept { return offsets_; }

 private:
  [[nodiscard]] std::size_t flat_index(std::size_t index, std::size_t row,
                                       std::size_t field) const;
  std::vector<double> values_;
  std::vector<Validity> validity_;
  std::vector<std::uint32_t> offsets_;
  std::size_t max_rows_ = 0;
};

}  // namespace qr::carriers

#endif  // QR_CARRIERS_CANDIDATE_SET_HPP
