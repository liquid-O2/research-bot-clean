// qr_carriers/src/direct_raw.cpp — the 60-column DIRECT_RAW construction.
#include "qr_carriers/direct_raw.hpp"

#include <algorithm>
#include <cmath>
#include <string>

namespace qr::carriers {
namespace {

/// The twenty full-window statistics, in the card's own listed order.
constexpr std::array<const char*, kDirectFullWindowColumns> kFullWindowNames{
    "FULL_LOG1P_TOKEN_COUNT",
    "FULL_LOG1P_GROUP_COUNT",
    "FULL_NONEMPTY",
    "FULL_ALL_FOUR_FINITE_GROUP_FRACTION",
    "FULL_RAW_MISSING_FRACTION",
    "FULL_MULTI_TOKEN_GROUP_FRACTION",
    "FULL_MEAN_LOG1P_MULTIPLICITY",
    "FULL_MAX_LOG1P_MULTIPLICITY",
    "FULL_MEAN_LOG1P_INTERGROUP_GAP_US",
    "FULL_P90_LOG1P_INTERGROUP_GAP_US",
    "FULL_MAX_LOG1P_INTERGROUP_GAP_US",
    "FULL_LOG1P_COVERED_SPAN_US",
    "FULL_LOG1P_AGE_OF_LAST_GROUP",
    "FULL_LOG1P_APPROACH_GROUP_COUNT",
    "FULL_LOG1P_RESPONSE_GROUP_COUNT",
    "FULL_APPROACH_OMISSION_FRACTION",
    "FULL_RESPONSE_OMISSION_FRACTION",
    "FULL_UNUSABLE_ATTACHMENT_FRACTION",
    "FULL_SEQUENCE_INVERSION_FRACTION",
    "FULL_R_MODALITY",
};

[[nodiscard]] std::size_t side_index(Side side) noexcept {
  return side == Side::LONG ? 0U : 1U;
}

}  // namespace

std::string direct_column_name(Modality modality, std::size_t column) {
  if (column >= kDirectColumnCount) {
    detail::fail_fast("qr::carriers::direct_column_name: column out of range");
  }
  if (column >= kDirectFullWindowOffset) {
    return kFullWindowNames[column - kDirectFullWindowOffset];
  }
  const std::size_t window = column / kDirectPerWindowColumns;
  const std::size_t inside = column % kDirectPerWindowColumns;
  const std::string prefix = "W" + std::to_string(kDirectWindowSeconds[window]) + "S_";
  if (inside == 0) {
    return prefix + "LOG_COUNT";
  }
  if (inside == 1) {
    return prefix + "VALID_FRACTION";
  }
  const std::size_t mech = (inside - 2) / 2;
  const bool is_last = ((inside - 2) % 2) == 1;
  const std::size_t channel = mechanism_channels(modality)[mech];
  const char* channel_name = nullptr;
  switch (modality) {
    case Modality::STOCK_PRINT:
      channel_name = stock_print_channel_name(channel);
      break;
    case Modality::STOCK_NBBO:
      channel_name = nbbo_channel_name(channel);
      break;
    case Modality::OPTION_PRINT:
      channel_name = option_print_channel_name(channel);
      break;
  }
  return prefix + channel_name + (is_last ? "_LAST" : "_MEAN");
}

// ---------------------------------------------------------------------------
// Construction: one pass, all prefix sums.
// ---------------------------------------------------------------------------

DirectRawBuilder::DirectRawBuilder(Modality modality, std::span<const GroupRecord> groups)
    : modality_(modality), groups_(groups) {
  const std::size_t count = groups_.size();
  const std::size_t entries = count + 1;
  pre_tokens_.assign(entries, 0);
  pre_absent_cells_.assign(entries, 0);
  pre_unusable_tokens_.assign(entries, 0);
  pre_multi_token_groups_.assign(entries, 0);
  pre_log1p_multiplicity_.assign(entries, 0.0);
  pre_log1p_gap_.assign(entries, 0.0);
  pre_sequence_pairs_.assign(entries, 0);
  pre_sequence_inversions_.assign(entries, 0);
  for (std::size_t side = 0; side < 2; ++side) {
    pre_all_four_[side].assign(entries, 0);
    for (std::size_t mech = 0; mech < kMechanismCount; ++mech) {
      pre_mech_sum_[side][mech].assign(entries, 0.0);
      pre_mech_count_[side][mech].assign(entries, 0);
    }
  }

  for (std::size_t index = 0; index < count; ++index) {
    const GroupRecord& group = groups_[index];
    const std::size_t next = index + 1;
    pre_tokens_[next] = pre_tokens_[index] + group.token_count;
    pre_absent_cells_[next] = pre_absent_cells_[index] + group.absent_value_cells;
    pre_unusable_tokens_[next] = pre_unusable_tokens_[index] + group.unusable_attachment_tokens;
    pre_multi_token_groups_[next] =
        pre_multi_token_groups_[index] + (group.token_count > 1 ? 1 : 0);
    pre_log1p_multiplicity_[next] = pre_log1p_multiplicity_[index] + group.log1p_multiplicity;
    pre_log1p_gap_[next] = pre_log1p_gap_[index] + (group.has_gap ? group.log1p_gap_micros : 0.0);
    pre_sequence_pairs_[next] = pre_sequence_pairs_[index] + (group.sequence_pair ? 1 : 0);
    pre_sequence_inversions_[next] =
        pre_sequence_inversions_[index] + (group.sequence_inversion ? 1 : 0);
    for (const Side side : {Side::LONG, Side::SHORT}) {
      const std::size_t slot = side_index(side);
      pre_all_four_[slot][next] =
          pre_all_four_[slot][index] + (group.all_four_present(side) ? 1 : 0);
      for (std::size_t mech = 0; mech < kMechanismCount; ++mech) {
        const Typed<double> value = group.mechanism(side, mech);
        const bool ok = value.v == Validity::VALID;
        pre_mech_sum_[slot][mech][next] =
            pre_mech_sum_[slot][mech][index] + (ok ? value.value : 0.0);
        pre_mech_count_[slot][mech][next] = pre_mech_count_[slot][mech][index] + (ok ? 1 : 0);
      }
    }
  }
}

std::size_t DirectRawBuilder::lower_bound_ts(std::int64_t ts_ns) const noexcept {
  const auto found = std::lower_bound(
      groups_.begin(), groups_.end(), ts_ns,
      [](const GroupRecord& group, std::int64_t bound) { return group.ts_ns_a < bound; });
  return static_cast<std::size_t>(found - groups_.begin());
}

std::size_t DirectRawBuilder::upper_bound_ts(std::int64_t ts_ns) const noexcept {
  const auto found = std::upper_bound(
      groups_.begin(), groups_.end(), ts_ns,
      [](std::int64_t bound, const GroupRecord& group) { return bound < group.ts_ns_a; });
  return static_cast<std::size_t>(found - groups_.begin());
}

DirectRawBuilder::Range DirectRawBuilder::range_for(std::int64_t from_ns,
                                                    std::int64_t to_ns) const noexcept {
  Range range;
  range.lo = lower_bound_ts(from_ns);
  range.hi = lower_bound_ts(to_ns);  // right-OPEN: equal-cutoff groups excluded
  if (range.hi < range.lo) {
    range.hi = range.lo;
  }
  return range;
}

void DirectRawBuilder::scan_range(const Range& range) {
  if (scanned_valid_ && scanned_.lo == range.lo && scanned_.hi == range.hi) {
    return;
  }
  scanned_ = range;
  scanned_valid_ = true;
  scan_has_multiplicity_ = false;
  scan_max_log1p_multiplicity_ = 0.0;
  scan_has_gap_ = false;
  scan_max_log1p_gap_ = 0.0;
  scan_p90_log1p_gap_ = 0.0;
  gap_scratch_.clear();

  for (std::size_t index = range.lo; index < range.hi; ++index) {
    const GroupRecord& group = groups_[index];
    if (!scan_has_multiplicity_ || group.log1p_multiplicity > scan_max_log1p_multiplicity_) {
      scan_has_multiplicity_ = true;
      scan_max_log1p_multiplicity_ = group.log1p_multiplicity;
    }
    // Only gaps BETWEEN groups of this window count: the gap stored on group i
    // is the one from group i-1, so the window's internal gaps are exactly the
    // ones on indices (lo, hi).
    if (index > range.lo && group.has_gap) {
      gap_scratch_.push_back(group.log1p_gap_micros);
      if (!scan_has_gap_ || group.log1p_gap_micros > scan_max_log1p_gap_) {
        scan_has_gap_ = true;
        scan_max_log1p_gap_ = group.log1p_gap_micros;
      }
    }
  }
  if (!gap_scratch_.empty()) {
    // Nearest-rank p90: the ceil(0.9*n)-th smallest, 1-based.
    const std::size_t count = gap_scratch_.size();
    const std::size_t rank = static_cast<std::size_t>(
        std::ceil(0.9 * static_cast<double>(count)));
    const std::size_t index = (rank == 0 ? 1U : rank) - 1U;
    std::nth_element(gap_scratch_.begin(),
                     gap_scratch_.begin() + static_cast<std::ptrdiff_t>(index),
                     gap_scratch_.end());
    scan_p90_log1p_gap_ = gap_scratch_[index];
  }
}

// ---------------------------------------------------------------------------
// The row.
// ---------------------------------------------------------------------------

Expected<DirectRawRow, Refusal> DirectRawBuilder::build(const DecisionWindow& window) {
  const std::size_t slot = side_index(window.side);
  const std::int64_t full_start = window.window_start_ns_a();
  const Range full = range_for(full_start, window.cutoff_ns_a);

  DirectRawRow row;

  // --- the four window blocks ------------------------------------------------
  for (std::size_t index = 0; index < kDirectWindowCount; ++index) {
    const std::size_t offset = direct_window_offset(index);
    const std::int64_t span = kDirectWindowSeconds[index] * kNanosPerSecond;
    std::int64_t start = window.cutoff_ns_a - span;
    if (start < window.session_open_ns_a) {
      start = window.session_open_ns_a;
    }
    const Range range{lower_bound_ts(start), full.hi};
    const std::int64_t groups_in_window = static_cast<std::int64_t>(range.size());
    const std::int64_t tokens_in_window =
        pre_tokens_[range.hi] - pre_tokens_[range.lo];

    // "log count" is the message (token) count — see the header's reading 1.
    row.set(offset + 0, count_log1p(tokens_in_window));

    const std::int64_t all_four =
        pre_all_four_[slot][range.hi] - pre_all_four_[slot][range.lo];
    row.set(offset + 1, fraction(all_four, groups_in_window));

    for (std::size_t mech = 0; mech < kMechanismCount; ++mech) {
      const double sum = pre_mech_sum_[slot][mech][range.hi] - pre_mech_sum_[slot][mech][range.lo];
      const std::int64_t present_count = static_cast<std::int64_t>(
          pre_mech_count_[slot][mech][range.hi] - pre_mech_count_[slot][mech][range.lo]);
      row.set(offset + 2 + 2 * mech, finite_member_mean(sum, present_count));
      // "its `last` is the greatest strictly-prior timestamp group" of the
      // window; absent when that group's own value is absent.
      if (range.hi > range.lo) {
        row.set(offset + 3 + 2 * mech, groups_[range.hi - 1].mechanism(window.side, mech));
      } else {
        row.set(offset + 3 + 2 * mech, masked(Validity::MISSING));
      }
    }
  }

  // --- the twenty full-window statistics --------------------------------------
  const std::size_t base = kDirectFullWindowOffset;
  const std::int64_t group_count = static_cast<std::int64_t>(full.size());
  const std::int64_t token_count = pre_tokens_[full.hi] - pre_tokens_[full.lo];

  row.set(base + kDirectLog1pTokenCount, count_log1p(token_count));
  row.set(base + kDirectLog1pGroupCount, count_log1p(group_count));
  row.set(base + kDirectNonempty, structural_bit(group_count > 0));

  const std::int64_t all_four_full =
      pre_all_four_[slot][full.hi] - pre_all_four_[slot][full.lo];
  row.set(base + kDirectAllFourFiniteGroupFraction, fraction(all_four_full, group_count));

  const std::int64_t absent_cells = pre_absent_cells_[full.hi] - pre_absent_cells_[full.lo];
  const std::int64_t declared =
      static_cast<std::int64_t>(declared_value_channel_count(modality_));
  row.set(base + kDirectRawMissingFraction, fraction(absent_cells, token_count * declared));

  const std::int64_t multi_token = static_cast<std::int64_t>(
      pre_multi_token_groups_[full.hi] - pre_multi_token_groups_[full.lo]);
  row.set(base + kDirectMultiTokenGroupFraction, fraction(multi_token, group_count));

  const double multiplicity_sum =
      pre_log1p_multiplicity_[full.hi] - pre_log1p_multiplicity_[full.lo];
  row.set(base + kDirectMeanLog1pMultiplicity, finite_member_mean(multiplicity_sum, group_count));

  scan_range(full);
  row.set(base + kDirectMaxLog1pMultiplicity,
          scan_has_multiplicity_ ? present(scan_max_log1p_multiplicity_)
                                 : masked(Validity::MISSING));

  const double gap_sum = pre_log1p_gap_[full.hi] - pre_log1p_gap_[full.lo];
  const std::int64_t gap_count = static_cast<std::int64_t>(gap_scratch_.size());
  // The prefix sum counts the gap that enters the window from OUTSIDE it (the
  // one stored on group `lo`); the window's internal gaps exclude it.
  const double internal_gap_sum =
      gap_sum - ((full.hi > full.lo && groups_[full.lo].has_gap) ? groups_[full.lo].log1p_gap_micros
                                                                 : 0.0);
  row.set(base + kDirectMeanLog1pIntergroupGap, finite_member_mean(internal_gap_sum, gap_count));
  row.set(base + kDirectP90Log1pIntergroupGap,
          gap_count > 0 ? present(scan_p90_log1p_gap_) : masked(Validity::MISSING));
  row.set(base + kDirectMaxLog1pIntergroupGap,
          scan_has_gap_ ? present(scan_max_log1p_gap_) : masked(Validity::MISSING));

  if (group_count > 0) {
    const auto span = duration_micros(groups_[full.lo].ts_ns_a, groups_[full.hi - 1].ts_ns_a);
    if (!span.has_value()) {
      return Expected<DirectRawRow, Refusal>::refuse(span.error());
    }
    row.set(base + kDirectLog1pCoveredSpan, time_log1p_micros(span.value()));
    const auto age = duration_micros(groups_[full.hi - 1].ts_ns_a, window.cutoff_ns_a);
    if (!age.has_value()) {
      return Expected<DirectRawRow, Refusal>::refuse(age.error());
    }
    row.set(base + kDirectLog1pAgeOfLastGroup, time_log1p_micros(age.value()));
  } else {
    row.set(base + kDirectLog1pCoveredSpan, masked(Validity::MISSING));
    row.set(base + kDirectLog1pAgeOfLastGroup, masked(Validity::MISSING));
  }

  // --- the phase block ---------------------------------------------------------
  if (!window.phase_reference_present) {
    row.set(base + kDirectLog1pApproachGroupCount, masked(Validity::MISSING));
    row.set(base + kDirectLog1pResponseGroupCount, masked(Validity::MISSING));
    row.set(base + kDirectApproachOmissionFraction, masked(Validity::MISSING));
    row.set(base + kDirectResponseOmissionFraction, masked(Validity::MISSING));
  } else {
    // "< visibility is APPROACH, > visibility is RESPONSE, and == visibility is
    // PHASE_EQUAL_UNORDERED ... enters neither phase denominator." The groups are
    // ordered by timestamp, so the split is two binary searches, not a scan.
    const std::size_t equal_lo =
        std::max(full.lo, std::min(full.hi, lower_bound_ts(window.phase_reference_ns_a)));
    const std::size_t equal_hi =
        std::max(full.lo, std::min(full.hi, upper_bound_ts(window.phase_reference_ns_a)));
    const std::int64_t approach = static_cast<std::int64_t>(equal_lo - full.lo);
    const std::int64_t response = static_cast<std::int64_t>(full.hi - equal_hi);
    row.set(base + kDirectLog1pApproachGroupCount, count_log1p(approach));
    row.set(base + kDirectLog1pResponseGroupCount, count_log1p(response));

    // The truncated prefix: the window's groups that fall outside the most
    // recent 128 groups strictly before the cutoff. The window is a contiguous
    // suffix of the session's pre-cutoff groups, so the truncated set is exactly
    // its first max(0, W-128) groups.
    const std::size_t truncated =
        full.size() > kMicroCarrierGroups ? full.size() - kMicroCarrierGroups : 0U;
    const std::size_t truncated_hi = full.lo + truncated;
    const std::int64_t truncated_approach =
        static_cast<std::int64_t>(std::min(truncated_hi, equal_lo) - full.lo);
    const std::int64_t truncated_response = static_cast<std::int64_t>(
        truncated_hi > equal_hi ? truncated_hi - equal_hi : 0U);
    row.set(base + kDirectApproachOmissionFraction, fraction(truncated_approach, approach));
    row.set(base + kDirectResponseOmissionFraction, fraction(truncated_response, response));
  }

  // --- the two structurally-zero-for-NBBO quality fractions ---------------------
  if (modality_ == Modality::STOCK_NBBO) {
    // "For NBBO, attachment-invalid and sequence-inversion are typed structural
    // zeros" — present, with the value 0, not masked.
    row.set(base + kDirectUnusableAttachmentFraction, structural_bit(false));
    row.set(base + kDirectSequenceInversionFraction, structural_bit(false));
  } else {
    const std::int64_t unusable =
        pre_unusable_tokens_[full.hi] - pre_unusable_tokens_[full.lo];
    row.set(base + kDirectUnusableAttachmentFraction, fraction(unusable, token_count));
    const std::int64_t pairs = static_cast<std::int64_t>(pre_sequence_pairs_[full.hi] -
                                                         pre_sequence_pairs_[full.lo]);
    const std::int64_t inversions = static_cast<std::int64_t>(
        pre_sequence_inversions_[full.hi] - pre_sequence_inversions_[full.lo]);
    row.set(base + kDirectSequenceInversionFraction, fraction(inversions, pairs));
  }

  row.set(base + kDirectRModality, reliability_r_modality(all_four_full, group_count));
  return row;
}

}  // namespace qr::carriers
