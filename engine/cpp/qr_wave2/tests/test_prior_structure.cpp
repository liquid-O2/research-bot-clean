// Fixtures for W2.13 (+ADD-1) — the 14 channels of §W2.13-PIN-1, on hand
// literals whose arithmetic is written out in the comments:
//
//   * every formula, value by value, with the pin's own denominators;
//   * the sigma-band fixture: {1.5, 2, 2.5} are POINTS on the continuous
//     z_vwap, with the sign flipping with the side (the ADD-1 supersession);
//   * the side-reflection law over the family's orientation table;
//   * the guards: zero ATR, zero range, absent VWAP, absent B — typed with
//     presence 0, never clipped;
//   * the mandatory phase interaction (channel 12 = channel 11 x phi).
#include <cmath>
#include <cstdint>

#include "gtest/gtest.h"
#include "qr_wave2/prior_structure.hpp"
#include "wave2_test_support.hpp"

namespace {

using qr::Validity;
using qr::carriers::OrientKind;
using qr::carriers::Side;
using qr::wave2::build_prior_structure;
using qr::wave2::kPriorStructureChannelCount;
using qr::wave2::kPriorStructureOrientation;
using qr::wave2::PriorStructureInputs;
using qr::wave2::PriorStructureRow;
using qr::wave2::testing::history_of;

constexpr std::int64_t kHigh = 101'000'000;   // 101.00
constexpr std::int64_t kLow = 99'000'000;     //  99.00
constexpr std::int64_t kClose = 100'000'000;  // 100.00
constexpr std::int64_t kVwap = 100'500'000;   // 100.50
constexpr std::int64_t kM = 100'500'000;      // spot 100.50
constexpr std::int64_t kOpen = 100'200'000;   // O = 100.20
constexpr std::int64_t kIntradayVwap = 100'400'000;
/// ATR14 over sixteen identical sessions: (101.00-99.00)/100.00 = 200 bps.
constexpr double kAtr = 200.0;

PriorStructureInputs base_inputs(Side side) {
  // Twenty-one observed sessions, so position 20 has TWENTY priors: enough for
  // the 20-day window (20) and the ATR window (15).
  static const qr::wave2::PriorSessionHistory history =
      history_of(21, kHigh, kLow, kClose, kVwap);
  PriorStructureInputs inputs;
  inputs.side = side;
  inputs.m_u6 = kM;
  inputs.m_present = true;
  inputs.open_u6 = kOpen;
  inputs.open_present = true;
  inputs.intraday_vwap_u6 = kIntradayVwap;
  inputs.intraday_vwap_present = true;
  inputs.phase = 0.5;
  inputs.phase_present = true;
  inputs.sigma_scale_bps = 6.0;
  inputs.sigma_scale_present = true;
  inputs.priors = history.view_for(20U);
  return inputs;
}

TEST(PriorStructure, EveryChannelIsThePinsOwnArithmetic) {
  const PriorStructureRow row = build_prior_structure(base_inputs(Side::LONG));
  ASSERT_DOUBLE_EQ(base_inputs(Side::LONG).priors.atr14_bps, kAtr);

  // 1 d_pH: (100.50-101.00)/100.50 = -49.75 bps -> truncating -49; /200.
  EXPECT_DOUBLE_EQ(row.value[qr::wave2::kPsDistancePriorHigh], -49.0 / kAtr);
  // 2 d_pL: (100.50-99.00)/100.50 = 149.25 -> 149; /200.
  EXPECT_DOUBLE_EQ(row.value[qr::wave2::kPsDistancePriorLow], 149.0 / kAtr);
  // 3 d_pC: (100.50-100.00)/100.50 = 49.75 -> 49; /200.
  EXPECT_DOUBLE_EQ(row.value[qr::wave2::kPsDistancePriorClose], 49.0 / kAtr);
  // 4 d_pVWAP: the spot IS the prior VWAP here, so the distance is exactly 0.
  EXPECT_DOUBLE_EQ(row.value[qr::wave2::kPsDistancePriorVwap], 0.0);
  EXPECT_TRUE(row.presence(qr::wave2::kPsDistancePriorVwap));
  // 5 gap: (100.20-100.00)/100.00 = 20 bps (in bps of pC, per the formula); /200.
  EXPECT_DOUBLE_EQ(row.value[qr::wave2::kPsOvernightGap], 20.0 / kAtr);
  // 6/7 rp: (100.50-99.00)/(101.00-99.00) = 0.75, raw and side-neutral.
  EXPECT_DOUBLE_EQ(row.value[qr::wave2::kPsRangePosition5], 0.75);
  EXPECT_DOUBLE_EQ(row.value[qr::wave2::kPsRangePosition20], 0.75);
  // 8 ed_H20: (101.00-100.50)/100.50 = 49.75 -> 49; /200.
  EXPECT_DOUBLE_EQ(row.value[qr::wave2::kPsEdgeDistanceHigh20], 49.0 / kAtr);
  // 9 ed_L20: (100.50-99.00)/100.50 = 149.25 -> 149; /200.
  EXPECT_DOUBLE_EQ(row.value[qr::wave2::kPsEdgeDistanceLow20], 149.0 / kAtr);
  // 10 log_atr = ln(200).
  EXPECT_DOUBLE_EQ(row.value[qr::wave2::kPsLogAtr14], std::log(kAtr));
  // 11 d_open_atr: (100.50-100.20)/100.20 = 29.94 -> 29; /200.
  EXPECT_DOUBLE_EQ(row.value[qr::wave2::kPsDistanceOpenAtr], 29.0 / kAtr);
  // 12 phase_x_open = channel 11 * phi(0.5) — the mandatory interaction.
  EXPECT_DOUBLE_EQ(row.value[qr::wave2::kPsPhaseTimesOpen], (29.0 / kAtr) * 0.5);
  // 13 d_ivwap_atr: (100.50-100.40)/100.50 = 9.95 -> 9; /200.
  EXPECT_DOUBLE_EQ(row.value[qr::wave2::kPsDistanceIntradayVwapAtr], 9.0 / kAtr);
  // 14 z_vwap = 9 bps / sigma_scale 6 bps = 1.5 — NOT ATR-scaled.
  EXPECT_DOUBLE_EQ(row.value[qr::wave2::kPsZVwap], 1.5);

  for (std::size_t channel = 0; channel < kPriorStructureChannelCount; ++channel) {
    EXPECT_TRUE(row.presence(channel)) << "channel " << channel << " should be present";
  }
}

TEST(PriorStructure, TheSigmaBandsAreFixturePointsOnTheContinuousZ) {
  // ADD-1's {1.5, 2, 2.5} bands are no longer channels: they are values of the
  // one continuous z_vwap. The numerator is a fixed 9 bps, so a band is chosen
  // by the sigma scale — and the SIGN is the side's.
  struct Case {
    double sigma_scale;
    double expected;
  };
  for (const Case& c : {Case{6.0, 1.5}, Case{4.5, 2.0}, Case{3.6, 2.5}}) {
    PriorStructureInputs longs = base_inputs(Side::LONG);
    longs.sigma_scale_bps = c.sigma_scale;
    PriorStructureInputs shorts = base_inputs(Side::SHORT);
    shorts.sigma_scale_bps = c.sigma_scale;

    const double long_z = build_prior_structure(longs).value[qr::wave2::kPsZVwap];
    const double short_z = build_prior_structure(shorts).value[qr::wave2::kPsZVwap];
    EXPECT_DOUBLE_EQ(long_z, c.expected);
    // A LONG above the running VWAP is a SHORT below it: the same band, mirrored.
    EXPECT_DOUBLE_EQ(short_z, -c.expected);
  }
}

TEST(PriorStructure, TheSideReflectionFollowsTheFamilysOrientationTable) {
  const PriorStructureRow longs = build_prior_structure(base_inputs(Side::LONG));
  const PriorStructureRow shorts = build_prior_structure(base_inputs(Side::SHORT));
  for (std::size_t channel = 0; channel < kPriorStructureChannelCount; ++channel) {
    ASSERT_EQ(longs.validity[channel], shorts.validity[channel]) << "channel " << channel;
    switch (kPriorStructureOrientation[channel]) {
      case OrientKind::SIGMA:
        EXPECT_DOUBLE_EQ(shorts.value[channel], -longs.value[channel])
            << "channel " << channel << " must negate under reflection";
        break;
      case OrientKind::INVARIANT:
        EXPECT_DOUBLE_EQ(shorts.value[channel], longs.value[channel])
            << "channel " << channel << " must be side-invariant";
        break;
      default:
        FAIL() << "this family declares no swap/rho channels";
    }
  }
}

TEST(PriorStructure, ZeroAtrTypesEveryAtrScaledChannelAndClipsNothing) {
  PriorStructureInputs inputs = base_inputs(Side::LONG);
  inputs.priors.atr14_bps = 0.0;  // a flat fortnight: the scale collapses
  const PriorStructureRow row = build_prior_structure(inputs);
  for (const std::size_t channel :
       {qr::wave2::kPsDistancePriorHigh, qr::wave2::kPsDistancePriorLow,
        qr::wave2::kPsDistancePriorClose, qr::wave2::kPsDistancePriorVwap,
        qr::wave2::kPsOvernightGap, qr::wave2::kPsEdgeDistanceHigh20,
        qr::wave2::kPsEdgeDistanceLow20, qr::wave2::kPsLogAtr14,
        qr::wave2::kPsDistanceOpenAtr, qr::wave2::kPsPhaseTimesOpen,
        qr::wave2::kPsDistanceIntradayVwapAtr}) {
    EXPECT_FALSE(row.presence(channel)) << "channel " << channel << " must be typed absent";
    EXPECT_DOUBLE_EQ(row.value[channel], 0.0) << "an absent channel carries exactly 0";
  }
  // The two range positions and z_vwap do NOT depend on the ATR scale.
  EXPECT_TRUE(row.presence(qr::wave2::kPsRangePosition5));
  EXPECT_TRUE(row.presence(qr::wave2::kPsRangePosition20));
  EXPECT_TRUE(row.presence(qr::wave2::kPsZVwap));
}

TEST(PriorStructure, AZeroWidthRangeIsMissingRatherThanInfinite) {
  PriorStructureInputs inputs = base_inputs(Side::LONG);
  inputs.priors.high5_u6 = inputs.priors.low5_u6;    // H_k == L_k
  inputs.priors.high20_u6 = inputs.priors.low20_u6;  // the pin's own guard case
  const PriorStructureRow row = build_prior_structure(inputs);
  EXPECT_FALSE(row.presence(qr::wave2::kPsRangePosition5));
  EXPECT_FALSE(row.presence(qr::wave2::kPsRangePosition20));
  EXPECT_DOUBLE_EQ(row.value[qr::wave2::kPsRangePosition5], 0.0);
}

TEST(PriorStructure, AbsentVwapOrBudgetTypesOnlyTheChannelsThatNeedThem) {
  PriorStructureInputs no_vwap = base_inputs(Side::LONG);
  no_vwap.intraday_vwap_present = false;
  const PriorStructureRow without_vwap = build_prior_structure(no_vwap);
  EXPECT_FALSE(without_vwap.presence(qr::wave2::kPsDistanceIntradayVwapAtr));
  EXPECT_FALSE(without_vwap.presence(qr::wave2::kPsZVwap));
  EXPECT_TRUE(without_vwap.presence(qr::wave2::kPsDistancePriorClose));

  PriorStructureInputs no_budget = base_inputs(Side::LONG);
  no_budget.sigma_scale_present = false;
  const PriorStructureRow without_budget = build_prior_structure(no_budget);
  EXPECT_FALSE(without_budget.presence(qr::wave2::kPsZVwap));
  // The ATR-scaled VWAP distance does not need B, so it survives.
  EXPECT_TRUE(without_budget.presence(qr::wave2::kPsDistanceIntradayVwapAtr));
}

TEST(PriorStructure, AnEmptyHistoryProducesNoLevelsAtAll) {
  PriorStructureInputs inputs = base_inputs(Side::LONG);
  inputs.priors = qr::wave2::PriorView{};
  // With no prior sessions there is no RV_prior, hence no B and no sigma_scale:
  // clearing it is what makes this input state a real one.
  inputs.sigma_scale_present = false;
  const PriorStructureRow row = build_prior_structure(inputs);
  for (std::size_t channel = 0; channel < kPriorStructureChannelCount; ++channel) {
    EXPECT_FALSE(row.presence(channel)) << "channel " << channel;
    EXPECT_DOUBLE_EQ(row.value[channel], 0.0);
  }
}

TEST(PriorStructure, ThePhaseOperandIsAFractionOfTheSessionSpan) {
  EXPECT_DOUBLE_EQ(qr::wave2::phase_fraction(0, 23400).value, 0.0);
  EXPECT_DOUBLE_EQ(qr::wave2::phase_fraction(11700, 23400).value, 0.5);
  EXPECT_DOUBLE_EQ(qr::wave2::phase_fraction(23400, 23400).value, 1.0);
  // An early close has a shorter span, so the same clock time is a LATER phase.
  EXPECT_DOUBLE_EQ(qr::wave2::phase_fraction(11700, 12600).value, 11700.0 / 12600.0);
  EXPECT_EQ(qr::wave2::phase_fraction(100, 0).v, Validity::MISSING);
}

}  // namespace
