#include "qr_wave2/prior_structure.hpp"

#include <cmath>

#include "qr_carriers/transforms.hpp"

namespace qr::wave2 {
namespace {

/// The integer bps displacement of the frozen transform row, oriented and then
/// divided by ATR14 — the shape every ATR-scaled channel of this family has.
/// `numerator_u6` and `denominator_u6` are exactly the two the pin's formula
/// names, so the denominator is m for 1-4/8/9/13, pC for 5 and O for 11.
[[nodiscard]] Typed<double> atr_scaled_bps(double sigma, std::int64_t numerator_u6,
                                           std::int64_t denominator_u6, bool atr_present,
                                           double atr14_bps) noexcept {
  if (!atr_present || !(atr14_bps > 0.0)) {
    // "zero ATR ... => typed with p=0, never clipped".
    return carriers::masked(Validity::MISSING);
  }
  const auto bps = carriers::displacement_bps_value(numerator_u6, denominator_u6);
  if (!bps.has_value() || bps.value().v != Validity::VALID) {
    return carriers::masked(Validity::MISSING);
  }
  return carriers::present(sigma * bps.value().value / atr14_bps);
}

}  // namespace

const char* prior_structure_channel_name(std::size_t channel) noexcept {
  switch (channel) {
    case kPsDistancePriorHigh: return "PS_D_PRIOR_HIGH";
    case kPsDistancePriorLow: return "PS_D_PRIOR_LOW";
    case kPsDistancePriorClose: return "PS_D_PRIOR_CLOSE";
    case kPsDistancePriorVwap: return "PS_D_PRIOR_VWAP";
    case kPsOvernightGap: return "PS_OVERNIGHT_GAP";
    case kPsRangePosition5: return "PS_RANGE_POSITION_5D";
    case kPsRangePosition20: return "PS_RANGE_POSITION_20D";
    case kPsEdgeDistanceHigh20: return "PS_EDGE_DISTANCE_HIGH_20D";
    case kPsEdgeDistanceLow20: return "PS_EDGE_DISTANCE_LOW_20D";
    case kPsLogAtr14: return "PS_LOG_ATR14";
    case kPsDistanceOpenAtr: return "PS_D_OPEN_ATR";
    case kPsPhaseTimesOpen: return "PS_PHASE_X_OPEN";
    case kPsDistanceIntradayVwapAtr: return "PS_D_INTRADAY_VWAP_ATR";
    case kPsZVwap: return "PS_Z_VWAP";
    default: return "PS_UNKNOWN";
  }
}

Typed<double> phase_fraction(std::int64_t seconds_since_open,
                             std::int64_t session_seconds) noexcept {
  if (session_seconds <= 0 || seconds_since_open < 0) {
    return carriers::masked(Validity::MISSING);
  }
  return carriers::present(static_cast<double>(seconds_since_open) /
                           static_cast<double>(session_seconds));
}

PriorStructureRow build_prior_structure(const PriorStructureInputs& inputs) noexcept {
  PriorStructureRow row;
  const double sigma = carriers::sigma_of(inputs.side);
  const PriorView& priors = inputs.priors;
  const bool atr = priors.atr_present;
  const double atr_bps = priors.atr14_bps;
  const std::int64_t m = inputs.m_u6;
  const bool have_m = inputs.m_present && m > 0;

  // 1-4: sigma*(m - level)/m/ATR14, in bps of m.
  if (have_m && priors.prior_present) {
    row.set(kPsDistancePriorHigh,
            atr_scaled_bps(sigma, m - priors.prior_high_u6, m, atr, atr_bps));
    row.set(kPsDistancePriorLow, atr_scaled_bps(sigma, m - priors.prior_low_u6, m, atr, atr_bps));
    row.set(kPsDistancePriorClose,
            atr_scaled_bps(sigma, m - priors.prior_close_u6, m, atr, atr_bps));
  }
  if (have_m && priors.prior_vwap_present) {
    row.set(kPsDistancePriorVwap, atr_scaled_bps(sigma, m - priors.prior_vwap_u6, m, atr, atr_bps));
  }

  // 5: gap = sig*(O-pC)/pC/ATR14 — session-constant, and in bps of pC.
  if (inputs.open_present && priors.prior_present) {
    row.set(kPsOvernightGap, atr_scaled_bps(sigma, inputs.open_u6 - priors.prior_close_u6,
                                            priors.prior_close_u6, atr, atr_bps));
  }

  // 6-7: rp_k = (m-L_k)/(H_k-L_k), raw, side-neutral. "Zero-range H_k==L_k =>
  // MISSING" is exactly the frozen fraction row's nonpositive-denominator rule.
  if (have_m && priors.range5_present) {
    row.set(kPsRangePosition5,
            carriers::fraction(m - priors.low5_u6, priors.high5_u6 - priors.low5_u6));
  }
  if (have_m && priors.range20_present) {
    row.set(kPsRangePosition20,
            carriers::fraction(m - priors.low20_u6, priors.high20_u6 - priors.low20_u6));
  }

  // 8-9: the 20-day edge distances, in bps of m. Note the pin's own asymmetry:
  // ed_H20 is (H_20 - m) and ed_L20 is (m - L_20), so BOTH are positive when m
  // sits inside the range and both grow as the market approaches that edge.
  if (have_m && priors.range20_present) {
    row.set(kPsEdgeDistanceHigh20, atr_scaled_bps(sigma, priors.high20_u6 - m, m, atr, atr_bps));
    row.set(kPsEdgeDistanceLow20, atr_scaled_bps(sigma, m - priors.low20_u6, m, atr, atr_bps));
  }

  // 10: log_atr = ln(ATR14_bps).
  if (atr && atr_bps > 0.0 && std::isfinite(atr_bps)) {
    row.set(kPsLogAtr14, carriers::present(std::log(atr_bps)));
  }

  // 11: d_open_atr = sig*(m-O)/O/ATR14, in bps of O (the location law's own
  // denominator, which the pin's formula writes out).
  Typed<double> open_distance = carriers::masked(Validity::MISSING);
  if (have_m && inputs.open_present) {
    open_distance = atr_scaled_bps(sigma, m - inputs.open_u6, inputs.open_u6, atr, atr_bps);
    row.set(kPsDistanceOpenAtr, open_distance);
  }

  // 12: phase_x_open = d_open_atr * phi(t) — the mandatory phase interaction.
  if (open_distance.v == Validity::VALID && inputs.phase_present) {
    row.set(kPsPhaseTimesOpen, carriers::present(open_distance.value * inputs.phase));
  }

  // 13-14: the intraday VWAP distance, ATR-scaled and budget-normalized.
  if (have_m && inputs.intraday_vwap_present) {
    row.set(kPsDistanceIntradayVwapAtr,
            atr_scaled_bps(sigma, m - inputs.intraday_vwap_u6, m, atr, atr_bps));
    if (inputs.sigma_scale_present && inputs.sigma_scale_bps > 0.0) {
      // z_vwap = (sig*(m-VWAP_t)/m*1e4)/sigma_scale(t): the numerator is the
      // same integer bps displacement, WITHOUT the ATR scale, over the budget's
      // own half-hour sigma. The three ADD-1 bands are fixture points on this z.
      const auto bps = carriers::displacement_bps_value(m - inputs.intraday_vwap_u6, m);
      if (bps.has_value() && bps.value().v == Validity::VALID) {
        row.set(kPsZVwap,
                carriers::present(sigma * bps.value().value / inputs.sigma_scale_bps));
      }
    }
  }
  return row;
}

}  // namespace qr::wave2
