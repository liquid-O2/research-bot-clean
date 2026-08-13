#include "qr_skel/geom.hpp"

#include <cmath>

namespace qr::skel {
namespace {

// SI / HG / NKD, in the qr_futsess::Asset enum order. mult and tick_usd are
// transcribed from PORT_M0_CENSUS_SPEC §1 (engine/port_m0/common.py:54-97).
constexpr AssetGeom kGeom[3] = {
    {5000, 0.005, 25.00},      // SI
    {25000, 0.0005, 12.50},    // HG
    {5, 5.0, 25.00},           // NKD
};

}  // namespace

const AssetGeom& asset_geom(Asset a) {
  return kGeom[static_cast<std::size_t>(a)];
}

double round_half_up(double x, double step) noexcept {
  return std::floor(x / step + 0.5) * step;
}

Expected<std::monostate, Refusal> build_ladder(const AssetGeom& g, double atr14_usd, double* out) {
  if (!std::isfinite(atr14_usd) || atr14_usd <= 0.0) {
    return refuse<std::monostate>(Refusal(RefusalCode::CONTENT_MISMATCH, "qr_skel::build_ladder",
                                          "candidate ATR14 is not a positive finite dollar value"));
  }
  const double mult = static_cast<double>(g.mult);
  for (std::size_t i = 0; i < kRungCount; ++i) {
    const double k = static_cast<double>(i + 1);
    const double px = round_half_up(k * kRungStep * atr14_usd / mult, g.tick_px);
    if (i == 0 && !(px > 0.0)) {
      // CONV C5: the first rung rounding to zero ticks would make a barrier
      // that is touched before the path moves. Refuse; never substitute.
      return refuse<std::monostate>(Refusal(RefusalCode::CONTENT_MISMATCH, "qr_skel::build_ladder",
                                            "rung 1 rounds to zero ticks for this ATR"));
    }
    out[i] = px * mult;
  }
  return std::monostate{};
}

}  // namespace qr::skel
