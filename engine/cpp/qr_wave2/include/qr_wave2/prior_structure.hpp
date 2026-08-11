// qr_wave2/prior_structure.hpp — W2.13 (+ADD-1), PRIOR-SESSION STRUCTURE
// (exactly 14 channels, the cap met).
//
// SPEC (design/DESIGN_FEATURES.md sha bf70dd35e5407863, §W2.13-PIN-1, verbatim):
//
//   "Channels: 1 d_pH = sig*(m-pH)/m/ATR14; 2 d_pL likewise; 3 d_pC;
//    4 d_pVWAP; 5 gap = sig*(O-pC)/pC/ATR14 (session-constant); 6 rp5 =
//    (m-L_5)/(H_5-L_5) raw [0,1] side-neutral; 7 rp20 likewise; 8 ed_H20 =
//    sig*(H_20-m)/m/ATR14; 9 ed_L20 = sig*(m-L_20)/m/ATR14; 10 log_atr =
//    ln(ATR14_bps); 11 d_open_atr = sig*(m-O)/O/ATR14; 12 phase_x_open =
//    d_open_atr * phi(t) (the mandatory phase interaction, product form; richer
//    forms belong to the interaction arms); 13 d_ivwap_atr =
//    sig*(m-VWAP_t)/m/ATR14; 14 z_vwap = (sig*(m-VWAP_t)/m*1e4)/sigma_scale(t)
//    — ONE continuous z supersedes ADD-1's three discrete band-position
//    channels ({1.5,2,2.5} become fixture points z=+/-k, not channels)."
//
//   "All distances sigma-oriented, in bps of m, ATR-scaled (dimensionless)
//    unless noted." — so every numerator is an integer bps displacement through
//    the frozen transform row, and the denominator each formula names is the
//    denominator used: m for 1-4/8/9/13, pC for 5, O for 11.
//
//   "No duplication with location idx 5/9 (those are RAW bps; W2.13 contributes
//    ATR-scaled/z-normalized variants + the interaction). Guards: zero ATR/
//    range/absent VWAP/B => typed with p=0, never clipped. Zero-range
//    H_k==L_k => MISSING (synthetic fixture)."
//
// WHY THE ADD-1 CORRECTION IS VISIBLE IN THE CHANNEL LIST. Channel 11 is the
// signed side-conditional travel from the open — reversal-depth context, not a
// level-proximity prior — and channel 12 is the session-phase interaction the
// CORRECTION makes mandatory for this family ("top-VALUE entries cluster at the
// open leg-origin while the deployable class occurs ALL DAY"). Channel 12 is a
// PRODUCT, by the pin's own word, so a model that never multiplies still sees
// the interaction, and richer forms are left to the interaction arms.
#ifndef QR_WAVE2_PRIOR_STRUCTURE_HPP
#define QR_WAVE2_PRIOR_STRUCTURE_HPP

#include <array>
#include <cstddef>
#include <cstdint>

#include "qr_carriers/channels.hpp"
#include "qr_core/validity.hpp"
#include "qr_wave2/prior_state.hpp"

namespace qr::wave2 {

enum PriorStructureChannel : std::size_t {
  kPsDistancePriorHigh = 0,
  kPsDistancePriorLow = 1,
  kPsDistancePriorClose = 2,
  kPsDistancePriorVwap = 3,
  kPsOvernightGap = 4,
  kPsRangePosition5 = 5,
  kPsRangePosition20 = 6,
  kPsEdgeDistanceHigh20 = 7,
  kPsEdgeDistanceLow20 = 8,
  kPsLogAtr14 = 9,
  kPsDistanceOpenAtr = 10,
  kPsPhaseTimesOpen = 11,
  kPsDistanceIntradayVwapAtr = 12,
  kPsZVwap = 13,
};
inline constexpr std::size_t kPriorStructureChannelCount = 14;
static_assert(kPriorStructureChannelCount == 14,
              "W2.13-PIN-1: exactly 14 channels, and A11's cap is 14");

/// The reflection law for this family. The two range positions are side-neutral
/// by the pin's own word, and log_atr is a scale.
inline constexpr std::array<carriers::OrientKind, kPriorStructureChannelCount>
    kPriorStructureOrientation{
        carriers::OrientKind::SIGMA,      // d_pH
        carriers::OrientKind::SIGMA,      // d_pL
        carriers::OrientKind::SIGMA,      // d_pC
        carriers::OrientKind::SIGMA,      // d_pVWAP
        carriers::OrientKind::SIGMA,      // gap
        carriers::OrientKind::INVARIANT,  // rp5 (side-neutral)
        carriers::OrientKind::INVARIANT,  // rp20 (side-neutral)
        carriers::OrientKind::SIGMA,      // ed_H20
        carriers::OrientKind::SIGMA,      // ed_L20
        carriers::OrientKind::INVARIANT,  // log_atr
        carriers::OrientKind::SIGMA,      // d_open_atr
        carriers::OrientKind::SIGMA,      // phase_x_open (phi is side-neutral)
        carriers::OrientKind::SIGMA,      // d_ivwap_atr
        carriers::OrientKind::SIGMA,      // z_vwap
    };

[[nodiscard]] const char* prior_structure_channel_name(std::size_t channel) noexcept;

using PriorStructureRow = carriers::ChannelRow<kPriorStructureChannelCount>;
using PriorStructureCensus = carriers::ChannelCensus<kPriorStructureChannelCount>;

/// One decision's inputs. Everything here is already strictly-prior: `m`, `O`
/// and `VWAP_t` come from the session's prefix state at the cutoff endpoint,
/// and `priors` from sessions strictly before this one.
struct PriorStructureInputs {
  carriers::Side side = carriers::Side::LONG;
  /// The spot midpoint at the cutoff endpoint, u6.
  std::int64_t m_u6 = 0;
  bool m_present = false;
  /// O — the session's first valid grid midpoint.
  std::int64_t open_u6 = 0;
  bool open_present = false;
  /// VWAP_t — the intraday running eligible-prints VWAP, strictly-prior.
  std::int64_t intraday_vwap_u6 = 0;
  bool intraday_vwap_present = false;
  /// phi(t) = t_since_open / T_session, in [0,1].
  double phase = 0.0;
  bool phase_present = false;
  /// sigma_scale(t) = sqrt(B(t)*1800) bps, from the W2.2 budget.
  double sigma_scale_bps = 0.0;
  bool sigma_scale_present = false;
  /// The strictly-prior cross-session structure.
  PriorView priors;
};

/// phi(t) = t_since_open / T_session — the session-phase operand channel 12
/// multiplies by. A nonpositive session span is typed, never divided by.
[[nodiscard]] Typed<double> phase_fraction(std::int64_t seconds_since_open,
                                           std::int64_t session_seconds) noexcept;

/// The 14 channels for one decision. Every guard the pin names types its
/// channel absent (value 0, presence 0) and clips nothing.
[[nodiscard]] PriorStructureRow build_prior_structure(const PriorStructureInputs& inputs) noexcept;

}  // namespace qr::wave2

#endif  // QR_WAVE2_PRIOR_STRUCTURE_HPP
