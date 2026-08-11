// qr_carriers/src/native_order.cpp — the 128-group micro carrier, the 120-bin
// full carrier, the section-7 destructions that live in the same constructor,
// and the APPENDIX C4 leaf packing.
//
// SPEC: task card V4 section 4 `NATIVE_ORDER` and section 7 (e)/(f), both quoted
// in native_order.hpp.
#include "qr_carriers/native_order.hpp"

#include <algorithm>
#include <cmath>

#include "qr_core/checked.hpp"

namespace qr::carriers {

namespace {

constexpr const char* kSite = "qr_carriers::native_order";

[[nodiscard]] Refusal content(const char* detail, std::int64_t value) {
  return Refusal(RefusalCode::CONTENT_MISMATCH, kSite, detail, value);
}

}  // namespace

const char* phase_name(Phase phase) noexcept {
  switch (phase) {
    case Phase::APPROACH:
      return "APPROACH";
    case Phase::RESPONSE:
      return "RESPONSE";
    case Phase::PHASE_EQUAL_UNORDERED:
      return "PHASE_EQUAL_UNORDERED";
    case Phase::PAD:
      return "PAD";
  }
  return "UNKNOWN_PHASE";
}

// ---------------------------------------------------------------------------
// NativeOrderBuilder
// ---------------------------------------------------------------------------

#ifdef QR_CARRIERS_NO_DESTRUCTIONS
NativeOrderBuilder::NativeOrderBuilder(Modality modality, std::span<const GroupRecord> groups)
    : modality_(modality), groups_(groups) {}
#else
NativeOrderBuilder::NativeOrderBuilder(Modality modality, std::span<const GroupRecord> groups,
                                       NativeCarrierControls controls)
    : modality_(modality), groups_(groups), controls_(controls) {}
#endif

std::size_t NativeOrderBuilder::lower_bound_ts(std::int64_t ts_ns,
                                               std::size_t from) const noexcept {
  const auto begin = groups_.begin() + static_cast<std::ptrdiff_t>(from);
  const auto found = std::lower_bound(begin, groups_.end(), ts_ns,
                                      [](const GroupRecord& group, std::int64_t bound) {
                                        return group.ts_ns_a < bound;
                                      });
  return static_cast<std::size_t>(found - groups_.begin());
}

std::size_t NativeOrderBuilder::upper_bound_ts(std::int64_t ts_ns,
                                               std::size_t from) const noexcept {
  const auto begin = groups_.begin() + static_cast<std::ptrdiff_t>(from);
  const auto found = std::upper_bound(begin, groups_.end(), ts_ns,
                                      [](std::int64_t bound, const GroupRecord& group) {
                                        return bound < group.ts_ns_a;
                                      });
  return static_cast<std::size_t>(found - groups_.begin());
}

std::size_t NativeOrderBuilder::groups_before(std::int64_t cutoff_ns) const noexcept {
  // "Current/equal-cutoff tokens are excluded" — lower_bound, not upper_bound.
  return lower_bound_ts(cutoff_ns, 0);
}

PhaseSplit NativeOrderBuilder::split_for(const DecisionWindow& window) const noexcept {
  PhaseSplit split;
  if (!window.phase_reference_present) {
    return split;
  }
  split.reference_present = true;
  const std::size_t equal_lo = lower_bound_ts(window.phase_reference_ns_a, 0);
  const std::size_t equal_hi = upper_bound_ts(window.phase_reference_ns_a, equal_lo);
  split.equal_lo = static_cast<std::int32_t>(equal_lo);
  split.equal_hi = static_cast<std::int32_t>(equal_hi);
  return split;
}

Expected<MicroCarrier, Refusal> NativeOrderBuilder::build_micro(
    const DecisionWindow& window) const {
  // "the most recent 128 groups strictly before cutoff, chronological".
  const std::size_t before = groups_before(window.cutoff_ns_a);
  const std::size_t length = std::min(before, kMicroCarrierGroups);
  const std::size_t start = before - length;
  const PhaseSplit split = split_for(window);

  MicroCarrier micro;
  micro.start = static_cast<std::int32_t>(start);
  micro.length = static_cast<std::int32_t>(length);
  micro.left_pad = static_cast<std::int32_t>(kMicroCarrierGroups - length);
  // The retained run is a SUFFIX of the pre-cutoff prefix, so its start index IS
  // the number of pre-cutoff groups the 128 cap dropped.
  micro.truncated = static_cast<std::int32_t>(start);

  for (std::size_t slot = 0; slot < kMicroCarrierGroups; ++slot) {
    if (slot < static_cast<std::size_t>(micro.left_pad)) {
      // "typed left pad": no group, no phase, exact zero downstream.
      micro.slot_group[slot] = -1;
      micro.slot_phase[slot] = Phase::PAD;
      ++micro.phase_slots[static_cast<std::size_t>(Phase::PAD)];
      continue;
    }
    const std::size_t offset = slot - static_cast<std::size_t>(micro.left_pad);
    std::size_t group = start + offset;
#ifndef QR_CARRIERS_NO_DESTRUCTIONS
    if (controls_.recent128_reverse) {
      // Section 7 (e): "reversing the valid recent-128 timestamp-group sequence
      // is reported". The VALID slots reverse; the typed left pad stays put.
      group = before - 1 - offset;
    }
#endif
    micro.slot_group[slot] = static_cast<std::int32_t>(group);
    const Phase phase = split.phase_of(static_cast<std::int32_t>(group));
    micro.slot_phase[slot] = phase;
    ++micro.phase_slots[static_cast<std::size_t>(phase)];
  }
  return micro;
}

Expected<BinCarrier, Refusal> NativeOrderBuilder::build_bins(const DecisionWindow& window) const {
  // "exactly 120 complete left-closed/right-open one-second bins
  //  [cutoff-120s+i, cutoff-120s+(i+1)s), i=0..119, spanning [cutoff-120s,cutoff)".
  const auto base = checked_sub(window.cutoff_ns_a, kBinCarrierSpanNs);
  if (!base.has_value()) {
    return Expected<BinCarrier, Refusal>::refuse(base.error());
  }

  BinCarrier bins;
  std::size_t cursor = lower_bound_ts(base.value(), 0);
  std::int64_t edge_ns = base.value();
  for (std::size_t bin = 0; bin < kBinCarrierBins; ++bin) {
    const auto next_edge = checked_add(edge_ns, kBinWidthNs);
    if (!next_edge.has_value()) {
      return Expected<BinCarrier, Refusal>::refuse(next_edge.error());
    }
    // Right-open: the bin ends BEFORE its right edge, so the last bin
    // [cutoff-1s, cutoff) excludes every equal-cutoff group by construction.
    const std::size_t end = lower_bound_ts(next_edge.value(), cursor);
    const bool pre_open = next_edge.value() <= window.session_open_ns_a;
    if (pre_open) {
      // "pre-open bins are typed zero left pad" — and a group inside one would
      // mean the stream carried a pre-open group, which is a typed refusal
      // rather than a silently padded bin.
      if (end > cursor) {
        return Expected<BinCarrier, Refusal>::refuse(
            content("a group precedes the session open inside a pre-open bin",
                    groups_[cursor].ts_ns_a));
      }
      bins.start[bin] = -1;
      bins.length[bin] = 0;
      bins.log1p_group_count[bin] = 0.0;
      bins.nonempty[bin] = 0U;
      bins.valid[bin] = 0U;
      ++bins.pre_open_pad_bins;
    } else {
      const std::size_t count = end - cursor;
      bins.start[bin] = static_cast<std::int32_t>(cursor);
      bins.length[bin] = static_cast<std::int32_t>(count);
      const Typed<double> log_count = count_log1p(static_cast<std::int64_t>(count));
      bins.log1p_group_count[bin] = log_count.v == Validity::VALID ? log_count.value : 0.0;
      bins.nonempty[bin] = count > 0 ? 1U : 0U;
      bins.valid[bin] = 1U;
      if (count > 0) {
        ++bins.nonempty_bins;
        bins.member_groups += static_cast<std::int32_t>(count);
      }
    }
    cursor = end;
    edge_ns = next_edge.value();
  }

#ifndef QR_CARRIERS_NO_DESTRUCTIONS
  if (controls_.bin_order_reverse) {
    // Section 7 (f): "reverses the value+mask tuples only within the ordered
    // valid in-session support of the 120 bins, leaves fixed pre-open
    // pads/validity in place, keeps the valid-bin multiset". The validity plane
    // is NOT permuted; the tuples carried by the valid positions are.
    std::vector<std::size_t> support;
    support.reserve(kBinCarrierBins);
    for (std::size_t bin = 0; bin < kBinCarrierBins; ++bin) {
      if (bins.valid[bin] != 0U) {
        support.push_back(bin);
      }
    }
    for (std::size_t index = 0; index + 1 < support.size(); ++index) {
      const std::size_t mirror = support.size() - 1 - index;
      if (mirror <= index) {
        break;
      }
      const std::size_t left = support[index];
      const std::size_t right = support[mirror];
      std::swap(bins.start[left], bins.start[right]);
      std::swap(bins.length[left], bins.length[right]);
      std::swap(bins.log1p_group_count[left], bins.log1p_group_count[right]);
      std::swap(bins.nonempty[left], bins.nonempty[right]);
    }
  }
#endif

  return bins;
}

// ---------------------------------------------------------------------------
// The APPENDIX C4 leaves.
// ---------------------------------------------------------------------------

const char* modality_leaf_suffix(Modality modality) noexcept {
  switch (modality) {
    case Modality::STOCK_PRINT:
      return "stock_print";
    case Modality::STOCK_NBBO:
      return "stock_nbbo";
    case Modality::OPTION_PRINT:
      return "option_print";
  }
  return "unknown_modality";
}

bool native_leaf_is_session_scoped(NativeLeaf leaf) noexcept {
  switch (leaf) {
    case NativeLeaf::GROUPS:
    case NativeLeaf::GROUP_TS:
    case NativeLeaf::ORIENTATION:
      return true;
    case NativeLeaf::RECENT128:
    case NativeLeaf::PHASE_SPLIT:
    case NativeLeaf::BINS_INDEX:
      return false;
  }
  detail::fail_fast("qr::carriers::native_leaf_is_session_scoped: unknown leaf");
}

std::string native_leaf_name(NativeLeaf leaf, Modality modality) {
  const char* stem = nullptr;
  switch (leaf) {
    case NativeLeaf::GROUPS:
      stem = "groups_";
      break;
    case NativeLeaf::GROUP_TS:
      stem = "group_ts_";
      break;
    case NativeLeaf::ORIENTATION:
      stem = "orientation_";
      break;
    case NativeLeaf::RECENT128:
      stem = "recent128_";
      break;
    case NativeLeaf::PHASE_SPLIT:
      stem = "phase_split_";
      break;
    case NativeLeaf::BINS_INDEX:
      stem = "bins_index_";
      break;
  }
  if (stem == nullptr) {
    detail::fail_fast("qr::carriers::native_leaf_name: unknown leaf");
  }
  return std::string(stem) + modality_leaf_suffix(modality);
}

NativeOrderShard::NativeOrderShard(Modality modality, std::span<const GroupRecord> groups,
                                   const GroupVectorTable& vectors)
    : modality_(modality),
      dim_(neutral_group_vector_dim_of(modality)),
      groups_(static_cast<std::int64_t>(groups.size())),
      group_values_(vectors.values()),
      orientation_(orientation_leaf(modality)) {
  if (vectors.modality() != modality) {
    detail::fail_fast("qr::carriers::NativeOrderShard: the vector table is another modality");
  }
  if (vectors.form() != GroupVectorTable::Form::NEUTRAL) {
    detail::fail_fast("qr::carriers::NativeOrderShard: a published tape stores the neutral table");
  }
  if (vectors.groups() != groups.size()) {
    detail::fail_fast("qr::carriers::NativeOrderShard: the vector table and group table disagree");
  }
  group_ts_.reserve(groups.size());
  for (const GroupRecord& group : groups) {
    group_ts_.push_back(group.ts_ns_a);
  }
}

Expected<std::size_t, Refusal> NativeOrderShard::push_decision(const MicroCarrier& micro,
                                                               const BinCarrier& bins,
                                                               const PhaseSplit& split) {
  // THE DESTRUCTION WALL. A published tape carries the PRODUCTION carriers; a
  // section-7 destruction changes slot order, which (start,len) cannot express,
  // so it is refused here rather than silently flattened back into a lawful
  // looking pair.
  if (micro.length < 0 || micro.start < 0 ||
      micro.left_pad != static_cast<std::int32_t>(kMicroCarrierGroups) - micro.length) {
    return Expected<std::size_t, Refusal>::refuse(
        content("the micro carrier's left pad is not 128 - length", micro.left_pad));
  }
  if (micro.truncated != micro.start) {
    return Expected<std::size_t, Refusal>::refuse(
        content("the micro carrier's truncation count is not its start index", micro.truncated));
  }
  if (static_cast<std::int64_t>(micro.start) + micro.length > groups_) {
    return Expected<std::size_t, Refusal>::refuse(
        content("the micro carrier runs past the group table", micro.start + micro.length));
  }
  for (std::size_t slot = 0; slot < kMicroCarrierGroups; ++slot) {
    const bool pad = slot < static_cast<std::size_t>(micro.left_pad);
    if (pad) {
      if (micro.slot_group[slot] != -1 || micro.slot_phase[slot] != Phase::PAD) {
        return Expected<std::size_t, Refusal>::refuse(
            content("a typed left-pad slot carries a group", micro.slot_group[slot]));
      }
      continue;
    }
    const std::int32_t expected =
        micro.start + static_cast<std::int32_t>(slot - static_cast<std::size_t>(micro.left_pad));
    if (micro.slot_group[slot] != expected) {
      return Expected<std::size_t, Refusal>::refuse(
          content("the micro carrier is not the chronological production run",
                  micro.slot_group[slot]));
    }
  }

  std::int32_t previous_end = 0;
  bool seen_valid = false;
  for (std::size_t bin = 0; bin < kBinCarrierBins; ++bin) {
    if (bins.valid[bin] == 0U) {
      if (bins.start[bin] != -1 || bins.length[bin] != 0) {
        return Expected<std::size_t, Refusal>::refuse(
            content("a pre-open pad bin carries a group range", bins.start[bin]));
      }
      continue;
    }
    if (bins.start[bin] < 0 ||
        static_cast<std::int64_t>(bins.start[bin]) + bins.length[bin] > groups_) {
      return Expected<std::size_t, Refusal>::refuse(
          content("a bin runs past the group table", bins.start[bin]));
    }
    if (seen_valid && bins.start[bin] < previous_end) {
      return Expected<std::size_t, Refusal>::refuse(
          content("the 120 bins are not in ascending group order", bins.start[bin]));
    }
    seen_valid = true;
    previous_end = bins.start[bin] + bins.length[bin];
  }

  recent128_.push_back(micro.start);
  recent128_.push_back(micro.length);
  // No reference => (-1,-1): every group "receives no phase embedding", which is
  // all an absent visibility leaves the carrier able to claim.
  if (split.reference_present) {
    phase_split_.push_back(split.equal_lo);
    phase_split_.push_back(split.equal_hi);
  } else {
    phase_split_.push_back(-1);
    phase_split_.push_back(-1);
  }
  for (std::size_t bin = 0; bin < kBinCarrierBins; ++bin) {
    bins_index_.push_back(bins.start[bin]);
    bins_index_.push_back(bins.length[bin]);
  }
  ++decisions_;
  return static_cast<std::size_t>(decisions_ - 1);
}

std::vector<std::int64_t> NativeOrderShard::leaf_shape(NativeLeaf leaf) const {
  switch (leaf) {
    case NativeLeaf::GROUPS:
      return {groups_, static_cast<std::int64_t>(dim_)};
    case NativeLeaf::GROUP_TS:
      return {groups_};
    case NativeLeaf::ORIENTATION:
      return {static_cast<std::int64_t>(declared_value_channel_count(modality_)),
              static_cast<std::int64_t>(kOrientationLeafColumns)};
    case NativeLeaf::RECENT128:
      return {decisions_, 2};
    case NativeLeaf::PHASE_SPLIT:
      return {decisions_, 2};
    case NativeLeaf::BINS_INDEX:
      return {decisions_, static_cast<std::int64_t>(kBinCarrierBins), 2};
  }
  detail::fail_fast("qr::carriers::NativeOrderShard::leaf_shape: unknown leaf");
}

}  // namespace qr::carriers
