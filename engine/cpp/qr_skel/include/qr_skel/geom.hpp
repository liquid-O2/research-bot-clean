// qr_skel/geom.hpp — the ATR rung ladder and the per-asset price geometry.
//
// SPEC: design/PORT_M1B_SPEC.md §1 S3 ("rung_k = k x 0.02 x ATR14($), tick-rounded;
// fixed-size vectors"); conventions design/PORT_M1B_S3_CONV.md C5.
//
// tick_px lives here rather than in qr_futsess::AssetSpec so the M1.A module
// that already passed its differential gate is not touched. The identity
// tick_usd == tick_px * mult is asserted by the test suite, not assumed.
#ifndef QR_SKEL_GEOM_HPP
#define QR_SKEL_GEOM_HPP

#include <cstddef>
#include <cstdint>

#include "qr_core/refusal.hpp"
#include "qr_futsess/constants.hpp"

namespace qr::skel {

using qr::Expected;
using qr::Refusal;
using qr::RefusalCode;
using qr::futsess::Asset;

/// The ladder is 200 rungs per side, fixed for every candidate and every
/// anchor. This is a SHAPE, not a tuning parameter: the structural suite
/// asserts it never varies.
inline constexpr std::size_t kRungCount = 200;
/// rung_k = k * kRungStep * ATR14($), k = 1..200.
inline constexpr double kRungStep = 0.02;

/// Bounded columnar execution (LABEL_ATLAS_V2 §3.2.6, ported).
inline constexpr std::size_t kChunkCandidates = 512;
inline constexpr std::size_t kChunkCandidatesMax = 1024;
inline constexpr std::size_t kAnchorCount = 2;  // d0 = decision_sec, d1 = +60s
inline constexpr std::int32_t kAnchorD1Delay = 60;
/// Whole-shard collection refuses above this many candidates (§3.2.6 analogue).
inline constexpr std::size_t kShardCandidateCap = 250000;

/// Horizon offsets from the anchor, in seconds (m0 HORIZON_MARKS).
inline constexpr std::int32_t kHorizonSecs[3] = {1800, 3600, 7200};
inline constexpr std::size_t kHorizonMarkCount = 5;  // 30m, 60m, 120m, phase, session

/// Per-asset price geometry needed by the ladder.
struct AssetGeom {
  std::int64_t mult;  // $ per 1.0 price unit
  double tick_px;     // minimum price increment, price units
  double tick_usd;    // mult * tick_px
};

[[nodiscard]] const AssetGeom& asset_geom(Asset a);

/// m0 HALF-UP rounding onto a grid (census_common.round_half_up).
[[nodiscard]] double round_half_up(double x, double step) noexcept;

/// Fill `out[0..kRungCount)` with rung_usd[k] for k = 1..200 (CONV C5).
/// Refuses a non-finite / non-positive ATR and a first rung that rounds to
/// zero ticks — a degenerate barrier is never silently substituted.
[[nodiscard]] Expected<std::monostate, Refusal> build_ladder(const AssetGeom& g, double atr14_usd,
                                                             double* out);

}  // namespace qr::skel

#endif  // QR_SKEL_GEOM_HPP
