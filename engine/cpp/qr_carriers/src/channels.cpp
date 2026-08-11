// qr_carriers/src/channels.cpp — the channel-vocabulary name tables.
//
// Names are SCREAMING_SNAKE and never sentences (the substrate's census law):
// a census prints them verbatim and a downstream reader keys on them.
#include "qr_carriers/channels.hpp"

#include "qr_core/refusal.hpp"

namespace qr::carriers {
namespace {

constexpr std::array<const char*, kStockPrintChannelCount> kStockPrintNames{
    "LOG_INTERARRIVAL",
    "ORIENTED_PRINT_RETURN",
    "ORIENTED_PRINT_MINUS_MID",
    "ORIENTED_AGGRESSOR",
    "LOG_SIZE",
    "ORIENTED_SIGNED_SIZE",
    "SPREAD_BPS",
    "LOG_OWN_ATTACHED_SIZE",
    "LOG_OPPOSITE_ATTACHED_SIZE",
    "ORIENTED_SIZE_IMBALANCE",
    "LOG_QUOTE_AGE",
    "QUOTE_PRESENT",
    "ATTACHMENT_VALID",
    "SEQUENCE_GAP_SIGNED_LOG",
    "SEQUENCE_MONOTONE",
    "SAME_MS",
    "DIRECTIONAL_ELIGIBLE",
};

constexpr std::array<const char*, kNbboChannelCount> kNbboNames{
    "LOG_INTERARRIVAL",
    "ORIENTED_MIDPOINT_CHANGE",
    "SPREAD_BPS",
    "LOG_OWN_SIZE",
    "LOG_OPPOSITE_SIZE",
    "ORIENTED_IMBALANCE",
    "OWN_PRICE_CHANGE",
    "OPPOSITE_PRICE_CHANGE",
    "OWN_SIGNED_SIZE_CHANGE",
    "OPPOSITE_SIGNED_SIZE_CHANGE",
    "LOCKED",
    "CROSSED",
    "POSITIVE_TWO_SIDED",
    "BID_CHANGED",
    "ASK_CHANGED",
    "SAME_MS",
};

constexpr std::array<const char*, kOptionPrintChannelCount> kOptionPrintNames{
    "LOG_INTERARRIVAL",
    "ORIENTED_UNDERLYING_RETURN",
    "ORIENTED_RIGHT_DIRECTION",
    "ORIENTED_CAUSAL_AGGRESSOR",
    "LOG_SIZE",
    "ORIENTED_SIGNED_PREMIUM_FLOW",
    "ORIENTED_PRINT_MINUS_MID",
    "SPREAD_BPS",
    "ORIENTED_DELTA",
    "GAMMA",
    "ORIENTED_VANNA",
    "ORIENTED_CHARM",
    "IMPLIED_VOL",
    "LOG_DTE",
    "ORIENTED_MONEYNESS",
    "ORIENTED_DELTA_FLOW",
    "GAMMA_FLOW",
    "ORIENTED_VANNA_FLOW",
    "ORIENTED_CHARM_FLOW",
    "LOG_QUOTE_AGE",
    "LOG_UNDERLYING_AGE",
    "DIRECTIONAL_ELIGIBLE",
};

}  // namespace

const char* side_name(Side side) noexcept {
  switch (side) {
    case Side::LONG:
      return "LONG";
    case Side::SHORT:
      return "SHORT";
  }
  return "UNKNOWN_SIDE";
}

const char* orient_kind_name(OrientKind kind) noexcept {
  switch (kind) {
    case OrientKind::INVARIANT:
      return "INVARIANT";
    case OrientKind::SIGMA:
      return "SIGMA";
    case OrientKind::SIGMA_RHO:
      return "SIGMA_RHO";
    case OrientKind::OWN_OPPOSITE_SWAP:
      return "OWN_OPPOSITE_SWAP";
  }
  return "UNKNOWN_ORIENT_KIND";
}

const char* stock_print_channel_name(std::size_t channel) noexcept {
  if (channel >= kStockPrintChannelCount) {
    detail::fail_fast("qr::carriers::stock_print_channel_name: channel out of range");
  }
  return kStockPrintNames[channel];
}

const char* nbbo_channel_name(std::size_t channel) noexcept {
  if (channel >= kNbboChannelCount) {
    detail::fail_fast("qr::carriers::nbbo_channel_name: channel out of range");
  }
  return kNbboNames[channel];
}

const char* option_print_channel_name(std::size_t channel) noexcept {
  if (channel >= kOptionPrintChannelCount) {
    detail::fail_fast("qr::carriers::option_print_channel_name: channel out of range");
  }
  return kOptionPrintNames[channel];
}

std::size_t stock_print_swap_partner(std::size_t channel) noexcept {
  switch (channel) {
    case kSpLogOwnAttachedSize:
      return kSpLogOppositeAttachedSize;
    case kSpLogOppositeAttachedSize:
      return kSpLogOwnAttachedSize;
    default:
      return channel;
  }
}

std::size_t nbbo_swap_partner(std::size_t channel) noexcept {
  switch (channel) {
    case kNbLogOwnSize:
      return kNbLogOppositeSize;
    case kNbLogOppositeSize:
      return kNbLogOwnSize;
    case kNbOwnPriceChange:
      return kNbOppositePriceChange;
    case kNbOppositePriceChange:
      return kNbOwnPriceChange;
    case kNbOwnSignedSizeChange:
      return kNbOppositeSignedSizeChange;
    case kNbOppositeSignedSizeChange:
      return kNbOwnSignedSizeChange;
    default:
      return channel;
  }
}

const char* modality_name(Modality modality) noexcept {
  switch (modality) {
    case Modality::STOCK_PRINT:
      return "STOCK_PRINT";
    case Modality::STOCK_NBBO:
      return "STOCK_NBBO";
    case Modality::OPTION_PRINT:
      return "OPTION_PRINT";
  }
  return "UNKNOWN_MODALITY";
}

std::size_t declared_value_channel_count(Modality modality) noexcept {
  switch (modality) {
    case Modality::STOCK_PRINT:
      return kStockPrintChannelCount;
    case Modality::STOCK_NBBO:
      return kNbboChannelCount;
    case Modality::OPTION_PRINT:
      return kOptionPrintChannelCount;
  }
  detail::fail_fast("qr::carriers::declared_value_channel_count: unknown modality");
}

}  // namespace qr::carriers
