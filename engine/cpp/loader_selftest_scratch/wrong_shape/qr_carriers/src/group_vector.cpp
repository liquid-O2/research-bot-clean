// qr_carriers/src/group_vector.cpp — the reduced group vector's names, widths
// and table (task card V4 section 4 `NATIVE_ORDER`, section 5's 69/65/89).
#include "qr_carriers/group_vector.hpp"

namespace qr::carriers {

std::size_t group_vector_dim_of(Modality modality) noexcept {
  switch (modality) {
    case Modality::STOCK_PRINT:
      return kStockPrintGroupDim;
    case Modality::STOCK_NBBO:
      return kNbboGroupDim;
    case Modality::OPTION_PRINT:
      return kOptionPrintGroupDim;
  }
  detail::fail_fast("qr::carriers::group_vector_dim_of: unknown modality");
}

std::string group_vector_component_name(Modality modality, std::size_t index) {
  const std::size_t channels = declared_value_channel_count(modality);
  const char* (*channel_name)(std::size_t) = nullptr;
  switch (modality) {
    case Modality::STOCK_PRINT:
      channel_name = &stock_print_channel_name;
      break;
    case Modality::STOCK_NBBO:
      channel_name = &nbbo_channel_name;
      break;
    case Modality::OPTION_PRINT:
      channel_name = &option_print_channel_name;
      break;
  }
  if (channel_name == nullptr) {
    detail::fail_fast("qr::carriers::group_vector_component_name: unknown modality");
  }
  if (index >= group_vector_dim(channels)) {
    detail::fail_fast("qr::carriers::group_vector_component_name: index outside the vector");
  }
  if (index == group_log_multiplicity_offset(channels)) {
    return "LOG1P_GROUP_MULTIPLICITY";
  }
  const std::size_t block = index / channels;
  const std::size_t channel = index % channels;
  const char* prefix = "";
  switch (block) {
    case 0:
      prefix = "MEAN_VALUE.";
      break;
    case 1:
      prefix = "MEAN_MASK.";
      break;
    case 2:
      prefix = "MAX_VALUE.";
      break;
    default:
      prefix = "MAX_MASK.";
      break;
  }
  return std::string(prefix) + channel_name(channel);
}

// ---------------------------------------------------------------------------
// The frozen orientation table, reached by modality (channels.hpp owns it).
// ---------------------------------------------------------------------------

OrientKind group_channel_orientation(Modality modality, std::size_t channel) noexcept {
  switch (modality) {
    case Modality::STOCK_PRINT:
      if (channel < kStockPrintChannelCount) {
        return kStockPrintOrientation[channel];
      }
      break;
    case Modality::STOCK_NBBO:
      if (channel < kNbboChannelCount) {
        return kNbboOrientation[channel];
      }
      break;
    case Modality::OPTION_PRINT:
      if (channel < kOptionPrintChannelCount) {
        return kOptionPrintOrientation[channel];
      }
      break;
  }
  detail::fail_fast("qr::carriers::group_channel_orientation: channel outside the modality");
}

std::size_t group_channel_swap_partner(Modality modality, std::size_t channel) noexcept {
  switch (modality) {
    case Modality::STOCK_PRINT:
      return stock_print_swap_partner(channel);
    case Modality::STOCK_NBBO:
      return nbbo_swap_partner(channel);
    case Modality::OPTION_PRINT:
      // The option list declares no own/opposite pair (channels.hpp): every one
      // of its 22 channels is INVARIANT, SIGMA or SIGMA_RHO.
      return channel;
  }
  detail::fail_fast("qr::carriers::group_channel_swap_partner: unknown modality");
}

namespace {

/// "the channels whose oriented value NEGATES when the side flips": SIGMA and
/// SIGMA_RHO alike, since `sigma = -1` multiplies both.
[[nodiscard]] bool negates(OrientKind kind) noexcept {
  return kind == OrientKind::SIGMA || kind == OrientKind::SIGMA_RHO;
}

[[nodiscard]] std::vector<std::size_t> build_flips(Modality modality) {
  std::vector<std::size_t> flips;
  const std::size_t channels = declared_value_channel_count(modality);
  for (std::size_t channel = 0; channel < channels; ++channel) {
    if (negates(group_channel_orientation(modality, channel))) {
      flips.push_back(channel);
    }
  }
  return flips;
}

const std::vector<std::size_t>& flips_of(Modality modality) {
  static const std::vector<std::size_t> stock_print = build_flips(Modality::STOCK_PRINT);
  static const std::vector<std::size_t> stock_nbbo = build_flips(Modality::STOCK_NBBO);
  static const std::vector<std::size_t> option_print = build_flips(Modality::OPTION_PRINT);
  switch (modality) {
    case Modality::STOCK_PRINT:
      return stock_print;
    case Modality::STOCK_NBBO:
      return stock_nbbo;
    case Modality::OPTION_PRINT:
      return option_print;
  }
  detail::fail_fast("qr::carriers::flips_of: unknown modality");
}

}  // namespace

std::span<const std::size_t> sigma_flip_channels(Modality modality) noexcept {
  const std::vector<std::size_t>& flips = flips_of(modality);
  return {flips.data(), flips.size()};
}

std::size_t sigma_flip_slot(Modality modality, std::size_t channel) noexcept {
  const std::vector<std::size_t>& flips = flips_of(modality);
  for (std::size_t slot = 0; slot < flips.size(); ++slot) {
    if (flips[slot] == channel) {
      return slot;
    }
  }
  return kNoSigmaSlot;
}

std::size_t neutral_group_vector_dim_of(Modality modality) noexcept {
  const std::size_t dim = group_vector_dim_of(modality) + flips_of(modality).size();
  switch (modality) {
    case Modality::STOCK_PRINT:
      if (dim != kStockPrintNeutralDim) {
        break;
      }
      return dim;
    case Modality::STOCK_NBBO:
      if (dim != kNbboNeutralDim) {
        break;
      }
      return dim;
    case Modality::OPTION_PRINT:
      if (dim != kOptionPrintNeutralDim) {
        break;
      }
      return dim;
  }
  // The compile-time width and the table-derived one are the same statement
  // twice; a build where they disagree may not run.
  detail::fail_fast("qr::carriers::neutral_group_vector_dim_of: width disagreement");
}

std::string neutral_vector_component_name(Modality modality, std::size_t index) {
  const std::size_t channels = declared_value_channel_count(modality);
  if (index < group_vector_dim(channels)) {
    return group_vector_component_name(modality, index);
  }
  const std::span<const std::size_t> flips = sigma_flip_channels(modality);
  const std::size_t slot = index - neutral_min_offset(channels);
  if (slot >= flips.size()) {
    detail::fail_fast("qr::carriers::neutral_vector_component_name: index outside the vector");
  }
  return std::string("MIN_VALUE.") + group_vector_component_name(modality, flips[slot]).substr(
                                          std::string("MEAN_VALUE.").size());
}

void orient_group_vector(Modality modality, std::span<const float> neutral, Side side,
                         std::span<float> out) noexcept {
  const std::size_t channels = declared_value_channel_count(modality);
  if (neutral.size() != neutral_group_vector_dim_of(modality) ||
      out.size() != group_vector_dim(channels)) {
    detail::fail_fast("qr::carriers::orient_group_vector: wrong widths");
  }
  const std::size_t mean_value = group_mean_value_offset(channels);
  const std::size_t mean_mask = group_mean_mask_offset(channels);
  const std::size_t max_value = group_max_value_offset(channels);
  const std::size_t max_mask = group_max_mask_offset(channels);
  for (std::size_t channel = 0; channel < channels; ++channel) {
    if (side == Side::LONG) {
      // sigma = +1: the stored vector IS the LONG one, verbatim.
      out[mean_value + channel] = canonical_f4(neutral[mean_value + channel]);
      out[mean_mask + channel] = canonical_f4(neutral[mean_mask + channel]);
      out[max_value + channel] = canonical_f4(neutral[max_value + channel]);
      out[max_mask + channel] = canonical_f4(neutral[max_mask + channel]);
      continue;
    }
    switch (group_channel_orientation(modality, channel)) {
      case OrientKind::INVARIANT: {
        out[mean_value + channel] = canonical_f4(neutral[mean_value + channel]);
        out[mean_mask + channel] = canonical_f4(neutral[mean_mask + channel]);
        out[max_value + channel] = canonical_f4(neutral[max_value + channel]);
        out[max_mask + channel] = canonical_f4(neutral[max_mask + channel]);
        break;
      }
      case OrientKind::SIGMA:
      case OrientKind::SIGMA_RHO: {
        const bool present_bit = neutral[max_mask + channel] != 0.0F;
        const std::size_t slot = sigma_flip_slot(modality, channel);
        // An absent channel stays exactly +0.0 ("value0"), never -0.0.
        out[mean_value + channel] =
            present_bit ? canonical_f4(-neutral[mean_value + channel]) : 0.0F;
        out[max_value + channel] =
            present_bit ? canonical_f4(-neutral[neutral_min_offset(channels) + slot]) : 0.0F;
        out[mean_mask + channel] = canonical_f4(neutral[mean_mask + channel]);
        out[max_mask + channel] = canonical_f4(neutral[max_mask + channel]);
        break;
      }
      case OrientKind::OWN_OPPOSITE_SWAP: {
        // "swaps own/opposite fields": the channel takes its partner's value AND
        // its partner's mask, in both blocks.
        const std::size_t partner = group_channel_swap_partner(modality, channel);
        out[mean_value + channel] = canonical_f4(neutral[mean_value + partner]);
        out[mean_mask + channel] = canonical_f4(neutral[mean_mask + partner]);
        out[max_value + channel] = canonical_f4(neutral[max_value + partner]);
        out[max_mask + channel] = canonical_f4(neutral[max_mask + partner]);
        break;
      }
    }
  }
  // "counts ... remain unchanged": the multiplicity is side-invariant.
  out[group_log_multiplicity_offset(channels)] =
      canonical_f4(neutral[group_log_multiplicity_offset(channels)]);
}

std::vector<std::int32_t> orientation_leaf(Modality modality) {
  const std::size_t channels = declared_value_channel_count(modality);
  std::vector<std::int32_t> rows;
  rows.reserve(channels * kOrientationLeafColumns);
  for (std::size_t channel = 0; channel < channels; ++channel) {
    const OrientKind kind = group_channel_orientation(modality, channel);
    const std::size_t slot = sigma_flip_slot(modality, channel);
    rows.push_back(static_cast<std::int32_t>(kind));
    rows.push_back(static_cast<std::int32_t>(group_channel_swap_partner(modality, channel)));
    rows.push_back(slot == kNoSigmaSlot ? -1 : static_cast<std::int32_t>(slot));
  }
  return rows;
}

GroupVectorTable::GroupVectorTable(Modality modality, Side side)
    : dim_(group_vector_dim_of(modality)),
      modality_(modality),
      side_(side),
      form_(Form::ORIENTED) {}

GroupVectorTable::GroupVectorTable(Modality modality)
    : dim_(neutral_group_vector_dim_of(modality)), modality_(modality), form_(Form::NEUTRAL) {}

std::span<const float> GroupVectorTable::row(std::size_t group) const noexcept {
  if (dim_ == 0 || group >= groups()) {
    detail::fail_fast("qr::carriers::GroupVectorTable::row: index outside the table");
  }
  return std::span<const float>(values_.data() + group * dim_, dim_);
}

void GroupVectorTable::append(std::span<const double> reduced) {
  if (reduced.size() != dim_) {
    detail::fail_fast("qr::carriers::GroupVectorTable::append: wrong reduced width");
  }
  for (const double value : reduced) {
    values_.push_back(canonical_f4(value));
  }
}

void GroupVectorTable::reserve(std::size_t groups) { values_.reserve(groups * dim_); }

}  // namespace qr::carriers
