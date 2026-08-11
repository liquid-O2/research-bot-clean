#include "qr_labels/money.hpp"

namespace qr::labels {
namespace {

constexpr const char* kFracSite = "qr_labels::frac_u6";
constexpr const char* kNetSite = "qr_labels::net_cent_of_frac";
constexpr const char* kMoveSite = "qr_labels::move_u6";
constexpr const char* kGateSite = "qr_labels::price_gate_for_net";

}  // namespace

Expected<std::int64_t, Refusal> frac_u6(std::int64_t move, std::int64_t entry_u6) noexcept {
  if (entry_u6 <= 0) {
    return Expected<std::int64_t, Refusal>::refuse(
        Refusal(RefusalCode::CONTENT_MISMATCH, kFracSite,
                "an executable fill price must be strictly positive", entry_u6));
  }
  const Expected<std::int64_t, Refusal> scaled = checked_mul(move, kFracScaleU6);
  if (!scaled.has_value()) {
    return Expected<std::int64_t, Refusal>::refuse(scaled.error());
  }
  // C++20 [expr.mul]/4: integer division truncates toward zero, which IS
  // `trunc_toward_zero` in the frozen formula. No rounding helper is involved.
  return scaled.value() / entry_u6;
}

Expected<std::int64_t, Refusal> net_cent_of_frac(std::int64_t frac) noexcept {
  const Expected<std::int64_t, Refusal> gross = checked_mul(frac, kGrossCentPerFracU6);
  if (!gross.has_value()) {
    return Expected<std::int64_t, Refusal>::refuse(gross.error());
  }
  return checked_sub(gross.value(), kTradeCostCent);
}

Expected<std::int64_t, Refusal> move_u6(std::int64_t entry_u6, std::int64_t mark_u6,
                                        Side side) noexcept {
  if (mark_u6 <= 0) {
    return Expected<std::int64_t, Refusal>::refuse(Refusal(
        RefusalCode::CONTENT_MISMATCH, kMoveSite, "a mark price must be strictly positive",
        mark_u6));
  }
  return side == Side::LONG ? checked_sub(mark_u6, entry_u6) : checked_sub(entry_u6, mark_u6);
}

Expected<std::int64_t, Refusal> mark_net_cent(std::int64_t entry_u6, std::int64_t mark_u6,
                                              Side side) noexcept {
  const Expected<std::int64_t, Refusal> move = move_u6(entry_u6, mark_u6, side);
  if (!move.has_value()) {
    return Expected<std::int64_t, Refusal>::refuse(move.error());
  }
  const Expected<std::int64_t, Refusal> frac = frac_u6(move.value(), entry_u6);
  if (!frac.has_value()) {
    return Expected<std::int64_t, Refusal>::refuse(frac.error());
  }
  return net_cent_of_frac(frac.value());
}

Expected<std::int64_t, Refusal> frac_threshold_for_net(NetBound bound,
                                                       std::int64_t net_cent) noexcept {
  // net = frac*10 - 576, so:
  //   net <= T  <=>  frac <= floor((T + 576) / 10)
  //   net >= T  <=>  frac >= ceil ((T + 576) / 10)
  const Expected<std::int64_t, Refusal> gross = checked_add(net_cent, kTradeCostCent);
  if (!gross.has_value()) {
    return Expected<std::int64_t, Refusal>::refuse(gross.error());
  }
  return bound == NetBound::AT_OR_BELOW
             ? floor_div_positive(gross.value(), kGrossCentPerFracU6)
             : ceil_div_positive(gross.value(), kGrossCentPerFracU6);
}

Expected<PriceGate, Refusal> price_gate_for_net(std::int64_t entry_u6, Side side, NetBound bound,
                                                std::int64_t net_cent) noexcept {
  if (entry_u6 <= 0) {
    return Expected<PriceGate, Refusal>::refuse(
        Refusal(RefusalCode::CONTENT_MISMATCH, kGateSite,
                "an executable fill price must be strictly positive", entry_u6));
  }
  const Expected<std::int64_t, Refusal> threshold = frac_threshold_for_net(bound, net_cent);
  if (!threshold.has_value()) {
    return Expected<PriceGate, Refusal>::refuse(threshold.error());
  }
  const std::int64_t frac = threshold.value();
  if (bound == NetBound::AT_OR_BELOW && frac >= 0) {
    return Expected<PriceGate, Refusal>::refuse(
        Refusal(RefusalCode::CONFIG, kGateSite,
                "an at-or-below net gate needs a strictly negative frac threshold", frac));
  }
  if (bound == NetBound::AT_OR_ABOVE && frac <= 0) {
    return Expected<PriceGate, Refusal>::refuse(
        Refusal(RefusalCode::CONFIG, kGateSite,
                "an at-or-above net gate needs a strictly positive frac threshold", frac));
  }

  // The inversion, side by side. sigma = +1 LONG / -1 SHORT (APPENDIX A
  // notation), and with `S = 1,000,000 + sigma*frac` the whole family is
  // `price vs entry * S / 1,000,000`:
  //
  //   LONG  (move = p - E, frac < 0):  frac(p) <= F  <=>  p <= floor(E*S/1e6)
  //   LONG  (move = p - E, frac > 0):  frac(p) >= F  <=>  p >= ceil (E*S/1e6)
  //   SHORT (move = E - p, frac < 0):  frac(p) <= F  <=>  p >= ceil (E*S/1e6)
  //   SHORT (move = E - p, frac > 0):  frac(p) >= F  <=>  p <= floor(E*S/1e6)
  //
  // Each equivalence is exact because `frac` is a truncation of a monotone
  // rational function of p and the frac threshold has a known sign: for a
  // negative threshold the truncation is a ceiling and `ceil(x) <= F <=> x <=
  // F`; for a positive one it is a floor and `floor(x) >= F <=> x >= F`.
  const std::int64_t sigma = side == Side::LONG ? 1 : -1;
  const Expected<std::int64_t, Refusal> signed_frac = checked_mul(sigma, frac);
  if (!signed_frac.has_value()) {
    return Expected<PriceGate, Refusal>::refuse(signed_frac.error());
  }
  const Expected<std::int64_t, Refusal> scale = checked_add(kFracScaleU6, signed_frac.value());
  if (!scale.has_value()) {
    return Expected<PriceGate, Refusal>::refuse(scale.error());
  }
  const Expected<std::int64_t, Refusal> numerator = checked_mul(entry_u6, scale.value());
  if (!numerator.has_value()) {
    return Expected<PriceGate, Refusal>::refuse(numerator.error());
  }

  const bool at_or_below = (side == Side::LONG) == (bound == NetBound::AT_OR_BELOW);
  PriceGate gate;
  gate.triggers_at_or_below = at_or_below;
  gate.price_u6 = at_or_below ? floor_div_positive(numerator.value(), kFracScaleU6)
                              : ceil_div_positive(numerator.value(), kFracScaleU6);
  return gate;
}

}  // namespace qr::labels
