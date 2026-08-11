// qr_carriers/channels.hpp — THE THREE CHANNEL LISTS, VERBATIM AND EXHAUSTIVE.
//
// SPEC (evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 4, the three
// lists quoted whole — "Per-side raw message channels are fixed"):
//
//   * stock-print (17): log interarrival, oriented print return, oriented
//     print-minus-mid, oriented aggressor {-1,0,1}, log size, oriented signed
//     size, spread bps, log own/opposite attached size, oriented size
//     imbalance, log quote age, quote-present, attachment-valid, sequence-gap
//     signed-log, sequence-monotone, same-ms, directional-eligible quality bit;
//   * stock-NBBO (16): log interarrival, oriented midpoint change, spread bps,
//     log own/opposite size, oriented imbalance, own/opposite price change,
//     own/opposite signed size change, locked, crossed, positive-two-sided,
//     bid-changed, ask-changed, same-ms;
//   * option-print (22): log interarrival, oriented underlying return, oriented
//     right direction, oriented causal aggressor, log size, oriented signed
//     premium flow, oriented print-minus-mid, spread bps, oriented delta,
//     gamma, oriented vanna/charm, IV, log DTE, oriented moneyness, recomputed
//     delta/gamma/vanna/charm flow, log quote age, log underlying age, and
//     directional-eligible quality bit.
//
// D-017 / directive "the channel lists are exhaustive law — no channel skipped,
// no extra channel". The counts are checked at compile time against the ONLY
// independent arithmetic the card gives for them (section 5): "For stock print,
// equal-time mean+max over 17 values+17 masks plus log multiplicity is 69
// inputs; NBBO's 16-value analog is 65 and option's 22-value analog is 89."
// (17+17)*2+1 = 69, (16+16)*2+1 = 65, (22+22)*2+1 = 89 — the static_asserts at
// the bottom of this header are that identity, so adding or dropping a channel
// breaks the build rather than a distant capacity table.
//
// THE ORIENTATION LAW IS A TABLE, NOT A CONVENTION (section 4, verbatim):
//   "`sigma=+1` for LONG and -1 for SHORT; stock price/return and signed-flow
//    channels are multiplied by sigma, and own/opposite is ask/bid for LONG and
//    bid/ask for SHORT. For options, `rho=+1` CALL and -1 PUT; oriented right
//    is `sigma*rho`, causal aggressor is `sigma*rho*v` ... Already signed
//    delta/vanna/charm and their recomputed flow columns are multiplied by
//    sigma. Gamma and recomputed gamma-flow remain side-invariant. Signed
//    premium flow is `sigma*rho*v*size*price_u6`. Oriented moneyness is
//    `sigma*rho*(underlying_u6-strike_u6)/strike_u6`."
//   "LONG/SHORT reflection changes only the declared directional channels and
//    swaps own/opposite fields; counts, spreads, gamma, ages, masks, and
//    quality remain unchanged."
// `kStockPrintOrientation` / `kNbboOrientation` / `kOptionPrintOrientation`
// below assign every channel exactly one of the four kinds, and the reflection
// fixture reads THESE tables — so "the declared directional channels" is a
// machine-checkable set rather than a reading of prose.
//
// TWO ORIENTATION RULINGS THIS LANE MADE EXPLICIT (both reported as STOP
// questions with the lane, both implemented the way the card's own enumeration
// points):
//   1. A channel is sigma-multiplied exactly when its declared NAME begins
//      "oriented"; a name without that prefix (NBBO "own/opposite price
//      change", "own/opposite signed size change") reflects ONLY through the
//      own/opposite swap, because the card's reflection sentence lists the swap
//      and the declared directional channels as two separate mechanisms.
//   2. Option "oriented print-minus-mid" carries `sigma*rho`, not bare sigma:
//      every option quantity that is directional in UNDERLYING space without
//      already being rho-signed by construction (oriented right, causal
//      aggressor, signed premium flow, oriented moneyness) is enumerated as
//      sigma*rho, while the bare-sigma option channels (delta, vanna, charm and
//      their flows) are the ones the card calls "already signed".
//
// CC-005 AND THE OWN/OPPOSITE SWAP ARE DIFFERENT LAWS ON DIFFERENT CHANNELS,
// and this header keeps them apart on purpose. The depth-imbalance channel is
// defined bid-minus-ask and sigma-oriented ("CC-005 ... sigma-oriented at the
// channel layer (own = bid for LONG)"), while the own/opposite SIZE channels
// take own = ask for LONG from the orientation law. A LONG buys at the ask, so
// its "own" queue is the ask queue; a positive imbalance means bid-side depth
// dominance, which is what a LONG wants. Collapsing the two would silently make
// one of them wrong.
#ifndef QR_CARRIERS_CHANNELS_HPP
#define QR_CARRIERS_CHANNELS_HPP

#include <array>
#include <cstddef>
#include <cstdint>

#include "qr_carriers/transforms.hpp"
#include "qr_core/validity.hpp"
#include "qr_sources/normalize.hpp"

namespace qr::carriers {

// ---------------------------------------------------------------------------
// Side and the two orientation scalars.
// ---------------------------------------------------------------------------

/// The authenticated action side. LOW->LONG and HIGH->SHORT upstream; this
/// module only ever consumes the resolved answer.
enum class Side : std::uint8_t { LONG = 0, SHORT = 1 };

[[nodiscard]] const char* side_name(Side side) noexcept;

/// `sigma = +1` for LONG and -1 for SHORT (section 4, verbatim).
[[nodiscard]] constexpr double sigma_of(Side side) noexcept {
  return side == Side::LONG ? 1.0 : -1.0;
}

/// `rho = +1` CALL and -1 PUT. A right the vendor wrote as neither is NOT
/// folded into one of them (WP4 keeps it as `Right::Other`): rho is undefined
/// and every sigma*rho channel of that print is masked.
[[nodiscard]] constexpr bool rho_is_defined(qr::sources::Right right) noexcept {
  return right == qr::sources::Right::Call || right == qr::sources::Right::Put;
}
[[nodiscard]] constexpr double rho_of(qr::sources::Right right) noexcept {
  return right == qr::sources::Right::Call ? 1.0 : -1.0;
}

/// How one channel reflects when the action side flips.
enum class OrientKind : std::uint8_t {
  /// "counts, spreads, gamma, ages, masks, and quality remain unchanged".
  INVARIANT = 0,
  /// Multiplied by sigma.
  SIGMA = 1,
  /// Multiplied by sigma*rho (option directional-in-underlying channels).
  SIGMA_RHO = 2,
  /// Not negated; the LONG value of this channel is the SHORT value of its
  /// declared partner ("swaps own/opposite fields").
  OWN_OPPOSITE_SWAP = 3,
};

[[nodiscard]] const char* orient_kind_name(OrientKind kind) noexcept;

// ---------------------------------------------------------------------------
// The stock-print list (17).
// ---------------------------------------------------------------------------

enum StockPrintChannel : std::size_t {
  kSpLogInterarrival = 0,
  kSpOrientedPrintReturn = 1,
  kSpOrientedPrintMinusMid = 2,
  kSpOrientedAggressor = 3,
  kSpLogSize = 4,
  kSpOrientedSignedSize = 5,
  kSpSpreadBps = 6,
  kSpLogOwnAttachedSize = 7,
  kSpLogOppositeAttachedSize = 8,
  kSpOrientedSizeImbalance = 9,
  kSpLogQuoteAge = 10,
  kSpQuotePresent = 11,
  kSpAttachmentValid = 12,
  kSpSequenceGapSignedLog = 13,
  kSpSequenceMonotone = 14,
  kSpSameMs = 15,
  kSpDirectionalEligible = 16,
};
inline constexpr std::size_t kStockPrintChannelCount = 17;

inline constexpr std::array<OrientKind, kStockPrintChannelCount> kStockPrintOrientation{
    OrientKind::INVARIANT,          // log interarrival
    OrientKind::SIGMA,              // oriented print return
    OrientKind::SIGMA,              // oriented print-minus-mid
    OrientKind::SIGMA,              // oriented aggressor
    OrientKind::INVARIANT,          // log size
    OrientKind::SIGMA,              // oriented signed size
    OrientKind::INVARIANT,          // spread bps
    OrientKind::OWN_OPPOSITE_SWAP,  // log own attached size
    OrientKind::OWN_OPPOSITE_SWAP,  // log opposite attached size
    OrientKind::SIGMA,              // oriented size imbalance
    OrientKind::INVARIANT,          // log quote age
    OrientKind::INVARIANT,          // quote-present
    OrientKind::INVARIANT,          // attachment-valid
    OrientKind::INVARIANT,          // sequence-gap signed-log
    OrientKind::INVARIANT,          // sequence-monotone
    OrientKind::INVARIANT,          // same-ms
    OrientKind::INVARIANT,          // directional-eligible
};

// ---------------------------------------------------------------------------
// The stock-NBBO list (16).
// ---------------------------------------------------------------------------

enum NbboChannel : std::size_t {
  kNbLogInterarrival = 0,
  kNbOrientedMidpointChange = 1,
  kNbSpreadBps = 2,
  kNbLogOwnSize = 3,
  kNbLogOppositeSize = 4,
  kNbOrientedImbalance = 5,
  kNbOwnPriceChange = 6,
  kNbOppositePriceChange = 7,
  kNbOwnSignedSizeChange = 8,
  kNbOppositeSignedSizeChange = 9,
  kNbLocked = 10,
  kNbCrossed = 11,
  kNbPositiveTwoSided = 12,
  kNbBidChanged = 13,
  kNbAskChanged = 14,
  kNbSameMs = 15,
};
inline constexpr std::size_t kNbboChannelCount = 16;

inline constexpr std::array<OrientKind, kNbboChannelCount> kNbboOrientation{
    OrientKind::INVARIANT,          // log interarrival
    OrientKind::SIGMA,              // oriented midpoint change
    OrientKind::INVARIANT,          // spread bps
    OrientKind::OWN_OPPOSITE_SWAP,  // log own size
    OrientKind::OWN_OPPOSITE_SWAP,  // log opposite size
    OrientKind::SIGMA,              // oriented imbalance
    OrientKind::OWN_OPPOSITE_SWAP,  // own price change
    OrientKind::OWN_OPPOSITE_SWAP,  // opposite price change
    OrientKind::OWN_OPPOSITE_SWAP,  // own signed size change
    OrientKind::OWN_OPPOSITE_SWAP,  // opposite signed size change
    OrientKind::INVARIANT,          // locked
    OrientKind::INVARIANT,          // crossed
    OrientKind::INVARIANT,          // positive-two-sided
    OrientKind::INVARIANT,          // bid-changed
    OrientKind::INVARIANT,          // ask-changed
    OrientKind::INVARIANT,          // same-ms
};

// ---------------------------------------------------------------------------
// The option-print list (22).
// ---------------------------------------------------------------------------

enum OptionPrintChannel : std::size_t {
  kOpLogInterarrival = 0,
  kOpOrientedUnderlyingReturn = 1,
  kOpOrientedRightDirection = 2,
  kOpOrientedCausalAggressor = 3,
  kOpLogSize = 4,
  kOpOrientedSignedPremiumFlow = 5,
  kOpOrientedPrintMinusMid = 6,
  kOpSpreadBps = 7,
  kOpOrientedDelta = 8,
  kOpGamma = 9,
  kOpOrientedVanna = 10,
  kOpOrientedCharm = 11,
  kOpImpliedVol = 12,
  kOpLogDte = 13,
  kOpOrientedMoneyness = 14,
  kOpOrientedDeltaFlow = 15,
  kOpGammaFlow = 16,
  kOpOrientedVannaFlow = 17,
  kOpOrientedCharmFlow = 18,
  kOpLogQuoteAge = 19,
  kOpLogUnderlyingAge = 20,
  kOpDirectionalEligible = 21,
};
inline constexpr std::size_t kOptionPrintChannelCount = 22;

inline constexpr std::array<OrientKind, kOptionPrintChannelCount> kOptionPrintOrientation{
    OrientKind::INVARIANT,  // log interarrival
    OrientKind::SIGMA,      // oriented underlying return (a STOCK return: sigma)
    OrientKind::SIGMA_RHO,  // oriented right direction = sigma*rho
    OrientKind::SIGMA_RHO,  // oriented causal aggressor = sigma*rho*v
    OrientKind::INVARIANT,  // log size
    OrientKind::SIGMA_RHO,  // oriented signed premium flow
    OrientKind::SIGMA_RHO,  // oriented print-minus-mid (ruling 2 in the header)
    OrientKind::INVARIANT,  // spread bps
    OrientKind::SIGMA,      // oriented delta (already rho-signed)
    OrientKind::INVARIANT,  // gamma (side-invariant, by name)
    OrientKind::SIGMA,      // oriented vanna
    OrientKind::SIGMA,      // oriented charm
    OrientKind::INVARIANT,  // IV
    OrientKind::INVARIANT,  // log DTE
    OrientKind::SIGMA_RHO,  // oriented moneyness
    OrientKind::SIGMA,      // recomputed delta flow
    OrientKind::INVARIANT,  // recomputed gamma flow (side-invariant, by name)
    OrientKind::SIGMA,      // recomputed vanna flow
    OrientKind::SIGMA,      // recomputed charm flow
    OrientKind::INVARIANT,  // log quote age
    OrientKind::INVARIANT,  // log underlying age
    OrientKind::INVARIANT,  // directional-eligible
};

/// The own/opposite partner of a channel, for the reflection fixture. Returns
/// the channel itself for every non-swap channel.
[[nodiscard]] std::size_t stock_print_swap_partner(std::size_t channel) noexcept;
[[nodiscard]] std::size_t nbbo_swap_partner(std::size_t channel) noexcept;

// ---------------------------------------------------------------------------
// Names (screaming-snake, never sentences) — censuses print every one of them.
// ---------------------------------------------------------------------------

[[nodiscard]] const char* stock_print_channel_name(std::size_t channel) noexcept;
[[nodiscard]] const char* nbbo_channel_name(std::size_t channel) noexcept;
[[nodiscard]] const char* option_print_channel_name(std::size_t channel) noexcept;

/// The three modalities, in the frozen order APPENDIX C4 stores them in
/// (`direct_raw [N,3,60]`).
enum class Modality : std::uint8_t { STOCK_PRINT = 0, STOCK_NBBO = 1, OPTION_PRINT = 2 };
inline constexpr std::size_t kModalityCount = 3;
[[nodiscard]] const char* modality_name(Modality modality) noexcept;
/// The declared value-channel count of a modality — the denominator of the
/// card's raw-missing fraction ("absent value cells divided by `token_count *
/// declared_value_channel_count`").
[[nodiscard]] std::size_t declared_value_channel_count(Modality modality) noexcept;

// ---------------------------------------------------------------------------
// One token's channel vector: values AND their parallel presence bits.
// ---------------------------------------------------------------------------

/// "Every value channel has a parallel presence bit; structurally observed
/// binary quality values use presence1." The presence bit is derived from the
/// validity so the two can never disagree, and a masked channel's value is
/// exactly 0.0.
template <std::size_t N>
struct ChannelRow {
  std::array<double, N> value{};
  std::array<Validity, N> validity{};

  ChannelRow() noexcept { validity.fill(Validity::MISSING); }

  void set(std::size_t channel, Typed<double> typed) noexcept {
    value[channel] = typed.v == Validity::VALID ? typed.value : 0.0;
    validity[channel] = typed.v;
  }

  [[nodiscard]] bool presence(std::size_t channel) const noexcept {
    return validity[channel] == Validity::VALID;
  }

  /// The number of ABSENT value cells in this token — the numerator the card's
  /// raw-missing fraction sums over tokens.
  [[nodiscard]] std::size_t absent_cells() const noexcept {
    std::size_t absent = 0;
    for (std::size_t index = 0; index < N; ++index) {
      if (validity[index] != Validity::VALID) {
        ++absent;
      }
    }
    return absent;
  }
};

using StockPrintRowChannels = ChannelRow<kStockPrintChannelCount>;
using NbboRowChannels = ChannelRow<kNbboChannelCount>;
using OptionPrintRowChannels = ChannelRow<kOptionPrintChannelCount>;

/// Per-channel presence census of one modality over a whole session: how many
/// tokens carried the channel and how many of those had it present. Printed in
/// full (every channel, including the zeros) by the probe.
template <std::size_t N>
struct ChannelCensus {
  std::array<std::int64_t, N> present{};
  std::int64_t tokens = 0;

  void fold(const ChannelRow<N>& row) noexcept { fold_repeated(row, 1); }

  /// Folds ONE channel vector that `count` tokens share. The NBBO modality
  /// needs it: its sixteen channels are group-level by law, so every member of
  /// an equal-millisecond group carries the same vector and the census would
  /// otherwise be a member loop over a constant.
  void fold_repeated(const ChannelRow<N>& row, std::int64_t count) noexcept {
    if (count <= 0) {
      return;
    }
    tokens += count;
    for (std::size_t index = 0; index < N; ++index) {
      if (row.validity[index] == Validity::VALID) {
        present[index] += count;
      }
    }
  }
};

using StockPrintCensus = ChannelCensus<kStockPrintChannelCount>;
using NbboCensus = ChannelCensus<kNbboChannelCount>;
using OptionPrintCensus = ChannelCensus<kOptionPrintChannelCount>;

// ---------------------------------------------------------------------------
// The compile-time identity against section 5's capacity arithmetic.
// ---------------------------------------------------------------------------

static_assert((kStockPrintChannelCount + kStockPrintChannelCount) * 2 + 1 == 69,
              "section 5: stock-print group embedding input is 69");
static_assert((kNbboChannelCount + kNbboChannelCount) * 2 + 1 == 65,
              "section 5: NBBO group embedding input is 65");
static_assert((kOptionPrintChannelCount + kOptionPrintChannelCount) * 2 + 1 == 89,
              "section 5: option-print group embedding input is 89");
static_assert(kStockPrintOrientation.size() == kStockPrintChannelCount);
static_assert(kNbboOrientation.size() == kNbboChannelCount);
static_assert(kOptionPrintOrientation.size() == kOptionPrintChannelCount);

}  // namespace qr::carriers

#endif  // QR_CARRIERS_CHANNELS_HPP
