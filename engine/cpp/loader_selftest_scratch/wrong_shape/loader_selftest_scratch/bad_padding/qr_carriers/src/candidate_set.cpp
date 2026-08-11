// qr_carriers/src/candidate_set.cpp — the 24-field candidate-set rows.
#include "qr_carriers/candidate_set.hpp"

#include <limits>
#include <string>
#include <vector>

namespace qr::carriers {
namespace {

constexpr std::array<const char*, kCandidateRelationCount> kRelationNames{"OWN", "OPPOSITE",
                                                                          "MIXED", "UNAVAILABLE"};

}  // namespace

const char* candidate_relation_name(CandidateRelation relation) noexcept {
  const std::size_t index = static_cast<std::size_t>(relation);
  if (index >= kCandidateRelationCount) {
    return "UNKNOWN_RELATION";
  }
  return kRelationNames[index];
}

std::string_view candidate_set_field_name(std::size_t field) {
  static const std::vector<std::string> names = [] {
    std::vector<std::string> built;
    built.reserve(kCandidateSetFieldCount);
    for (const std::string_view policy : kPolicyVocabulary) {
      built.emplace_back("POLICY_" + std::string(policy));
    }
    built.emplace_back("REVERSAL_OVER_20");
    built.emplace_back("LOG1P_MEMBER_COUNT");
    built.emplace_back("LOG1P_AGE_SECONDS");
    for (const char* relation : kRelationNames) {
      built.emplace_back("RELATION_" + std::string(relation));
    }
    for (const std::int64_t seconds : kVisibilityFlagSeconds) {
      built.emplace_back("VISIBLE_IN_LAST_" + std::to_string(seconds) + "S");
    }
    return built;
  }();
  if (field >= names.size()) {
    detail::fail_fast("qr::carriers::candidate_set_field_name: field out of range");
  }
  return names[field];
}

bool candidate_set_field_is_continuous(std::size_t field) noexcept {
  return field == kCandReversalOver20 || field == kCandLog1pMemberCount ||
         field == kCandLog1pAgeSeconds;
}

std::size_t policy_index_of(std::string_view policy_name) noexcept {
  for (std::size_t index = 0; index < kPolicyVocabularySize; ++index) {
    if (kPolicyVocabulary[index] == policy_name) {
      return index;
    }
  }
  return kPolicyVocabularySize;
}

Expected<CandidateSetRow, Refusal> build_candidate_set_row(const VisibleCandidate& candidate,
                                                           std::int64_t cutoff_ns_a) {
  if (candidate.policy_index >= kPolicyVocabularySize) {
    return Expected<CandidateSetRow, Refusal>::refuse(
        Refusal(RefusalCode::CONTENT_MISMATCH, "qr_carriers::build_candidate_set_row",
                "a nonprimitive policy reached the candidate-set encoder",
                static_cast<std::int64_t>(candidate.policy_index)));
  }
  if (candidate.visible_ts_ns_a >= cutoff_ns_a) {
    return Expected<CandidateSetRow, Refusal>::refuse(
        Refusal(RefusalCode::CLOCK_VIOLATION, "qr_carriers::build_candidate_set_row",
                "a candidate visible at or after the decision reached the encoder",
                candidate.visible_ts_ns_a));
  }

  CandidateSetRow row;
  // --- the 12-way policy one-hot ------------------------------------------------
  for (std::size_t index = 0; index < kPolicyVocabularySize; ++index) {
    row.set(kCandPolicyOneHot + index, structural_bit(index == candidate.policy_index));
  }
  // --- reversal/20, log1p member count, log1p age seconds ------------------------
  row.set(kCandReversalOver20,
          present(static_cast<double>(candidate.reversal_bps) / kReversalDivisor));
  row.set(kCandLog1pMemberCount, count_log1p(candidate.member_count));
  const auto age_micros = duration_micros(candidate.visible_ts_ns_a, cutoff_ns_a);
  if (!age_micros.has_value()) {
    return Expected<CandidateSetRow, Refusal>::refuse(age_micros.error());
  }
  row.set(kCandLog1pAgeSeconds, time_log1p_seconds(age_micros.value()));

  // --- the 4-way relation one-hot -------------------------------------------------
  for (std::size_t index = 0; index < kCandidateRelationCount; ++index) {
    row.set(kCandRelationOneHot + index,
            structural_bit(index == static_cast<std::size_t>(candidate.relation)));
  }

  // --- the five visibility-recency flags ------------------------------------------
  // Inclusive, matching section 2's "no more than 60s old" admission.
  const std::int64_t age_ns = cutoff_ns_a - candidate.visible_ts_ns_a;
  for (std::size_t index = 0; index < kVisibilityFlagCount; ++index) {
    const std::int64_t horizon_ns = kVisibilityFlagSeconds[index] * kNanosPerSecond;
    row.set(kCandVisibilityFlags + index, structural_bit(age_ns <= horizon_ns));
  }
  return row;
}

// ---------------------------------------------------------------------------
// The ragged block.
// ---------------------------------------------------------------------------

Expected<std::size_t, Refusal> CandidateSetBlock::push_decision(
    std::span<const CandidateSetRow> rows) {
  const std::size_t appended = values_.size() / kCandidateSetFieldCount + rows.size();
  if (appended > static_cast<std::size_t>(std::numeric_limits<std::uint32_t>::max())) {
    return Expected<std::size_t, Refusal>::refuse(
        Refusal(RefusalCode::ARITHMETIC_OVERFLOW, "qr_carriers::CandidateSetBlock::push_decision",
                "the candidate-set CSR offset does not fit u32",
                static_cast<std::int64_t>(appended)));
  }
  for (const CandidateSetRow& row : rows) {
    for (std::size_t field = 0; field < kCandidateSetFieldCount; ++field) {
      values_.push_back(row.value[field]);
      validity_.push_back(row.validity[field]);
    }
  }
  offsets_.push_back(static_cast<std::uint32_t>(appended));
  if (rows.size() > max_rows_) {
    max_rows_ = rows.size();
  }
  return decisions() - 1U;
}

std::size_t CandidateSetBlock::row_count(std::size_t index) const {
  if (index + 1U >= offsets_.size()) {
    detail::fail_fast("qr_carriers::CandidateSetBlock::row_count: decision out of range");
  }
  return offsets_[index + 1U] - offsets_[index];
}

std::size_t CandidateSetBlock::flat_index(std::size_t index, std::size_t row,
                                          std::size_t field) const {
  if (row >= row_count(index) || field >= kCandidateSetFieldCount) {
    detail::fail_fast("qr_carriers::CandidateSetBlock: row or field out of range");
  }
  return (static_cast<std::size_t>(offsets_[index]) + row) * kCandidateSetFieldCount + field;
}

double CandidateSetBlock::value_at(std::size_t index, std::size_t row, std::size_t field) const {
  return values_[flat_index(index, row, field)];
}

Validity CandidateSetBlock::validity_at(std::size_t index, std::size_t row,
                                        std::size_t field) const {
  return validity_[flat_index(index, row, field)];
}

}  // namespace qr::carriers
