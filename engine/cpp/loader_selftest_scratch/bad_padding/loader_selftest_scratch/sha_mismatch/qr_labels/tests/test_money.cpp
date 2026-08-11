// The exact integer money math (qr_labels/money.hpp): formulas (2) and (3), the
// price-gate inversion, and the ten-cent net lattice that makes the APPENDIX C5
// one-cent stop shift a provable no-op.
#include <gtest/gtest.h>

#include <cstdint>

#include "qr_labels/money.hpp"

namespace qr::labels {
namespace {

TEST(MoneyMath, FracIsTruncationTowardZeroOnBothSigns) {
  // 7 * 1,000,000 / 3 = 2,333,333.33... -> 2,333,333 both ways: truncation
  // toward zero, never floor and never a rounded value.
  EXPECT_EQ(frac_u6(7, 3).value(), 2'333'333);
  EXPECT_EQ(frac_u6(-7, 3).value(), -2'333'333);
  EXPECT_EQ(frac_u6(0, 1'000'000).value(), 0);
}

TEST(MoneyMath, ANonPositiveFillOrMarkIsARefusalNotAGuardedDivision) {
  EXPECT_FALSE(frac_u6(1, 0).has_value());
  EXPECT_FALSE(frac_u6(1, -5).has_value());
  EXPECT_FALSE(mark_net_cent(1'000'000, 0, Side::LONG).has_value());
  EXPECT_FALSE(mark_net_cent(0, 1'000'000, Side::LONG).has_value());
}

TEST(MoneyMath, TheFiveHundredAndSeventySixCentCostIsChargedExactlyOnce) {
  // A flat move is not a flat outcome: it is the cost, once.
  EXPECT_EQ(net_cent_of_frac(0).value(), -kTradeCostCent);
  EXPECT_EQ(mark_net_cent(1'000'000, 1'000'000, Side::LONG).value(), -576);
  // The card's own arithmetic: +5,000 net is "+$55.76 gross" and -5,000 net is
  // "-$44.24 gross".
  EXPECT_EQ(net_cent_of_frac(558).value() + kTradeCostCent, 5'580);
  EXPECT_EQ(net_cent_of_frac(558).value(), 5'004);
  EXPECT_EQ(net_cent_of_frac(-443).value(), -5'006);
}

TEST(MoneyMath, LongAndShortMarksAreExactMirrorsAroundTheFill) {
  // A $1.00 fill makes frac equal the move in u6, so these are hand-checkable.
  EXPECT_EQ(mark_net_cent(1'000'000, 1'001'000, Side::LONG).value(), 1'000 * 10 - 576);
  EXPECT_EQ(mark_net_cent(1'000'000, 999'000, Side::SHORT).value(), 1'000 * 10 - 576);
  EXPECT_EQ(mark_net_cent(1'000'000, 999'000, Side::LONG).value(), -1'000 * 10 - 576);
  EXPECT_EQ(mark_net_cent(1'000'000, 1'001'000, Side::SHORT).value(), -1'000 * 10 - 576);
}

TEST(MoneyMath, TheReachableNetLatticeIsTenCentsWideAroundMinusFiveSevenSix) {
  // net = frac*10 - 576, so every reachable net is congruent to 4 modulo 10.
  for (std::int64_t frac = -5; frac <= 5; ++frac) {
    const std::int64_t net = net_cent_of_frac(frac).value();
    EXPECT_EQ(((net % 10) + 10) % 10, 4) << "frac " << frac;
  }
  // The two reachable nets that straddle the wall.
  EXPECT_EQ(net_cent_of_frac(-2'943).value(), -30'006);
  EXPECT_EQ(net_cent_of_frac(-2'942).value(), -29'996);
}

TEST(MoneyMath, AOneCentStopShiftCannotMoveTheFracThresholdButFourCentsCan) {
  // THE APPENDIX C5 MUTANT, MEASURED. The frac threshold of the wall is
  // floor((T + 576)/10); at T = -30,000 that is floor(-2,942.4) = -2,943, and
  // one cent either way leaves it exactly there.
  const std::int64_t at_wall = frac_threshold_for_net(NetBound::AT_OR_BELOW, -30'000).value();
  EXPECT_EQ(at_wall, -2'943);
  EXPECT_EQ(frac_threshold_for_net(NetBound::AT_OR_BELOW, -29'999).value(), at_wall);
  EXPECT_EQ(frac_threshold_for_net(NetBound::AT_OR_BELOW, -30'001).value(), at_wall);
  // The SMALLEST EFFECTIVE shifts: up to the next reachable net (-29,996) and
  // down past the previous one (-30,007 -> -2,944).
  EXPECT_EQ(frac_threshold_for_net(NetBound::AT_OR_BELOW, -29'996).value(), -2'942);
  EXPECT_EQ(frac_threshold_for_net(NetBound::AT_OR_BELOW, -30'007).value(), -2'944);
}

TEST(MoneyMath, TheWallPriceGateIsTheExactBoundaryOnBothSides) {
  // LONG: the gate is a bid at or below floor(E*(1e6-2943)/1e6) = 997,057, and
  // the next tick up is the last mark that does NOT cross.
  const PriceGate longs =
      price_gate_for_net(1'000'000, Side::LONG, NetBound::AT_OR_BELOW, -30'000).value();
  EXPECT_TRUE(longs.triggers_at_or_below);
  EXPECT_EQ(longs.price_u6, 997'057);
  EXPECT_EQ(mark_net_cent(1'000'000, 997'057, Side::LONG).value(), -30'006);
  EXPECT_EQ(mark_net_cent(1'000'000, 997'058, Side::LONG).value(), -29'996);

  // SHORT: mirrored — an ask at or ABOVE ceil(E*(1e6+2943)/1e6) = 1,002,943.
  const PriceGate shorts =
      price_gate_for_net(1'000'000, Side::SHORT, NetBound::AT_OR_BELOW, -30'000).value();
  EXPECT_FALSE(shorts.triggers_at_or_below);
  EXPECT_EQ(shorts.price_u6, 1'002'943);
  EXPECT_EQ(mark_net_cent(1'000'000, 1'002'943, Side::SHORT).value(), -30'006);
  EXPECT_EQ(mark_net_cent(1'000'000, 1'002'942, Side::SHORT).value(), -29'996);
}

TEST(MoneyMath, TheBarrierPriceGatesAreTheExactBoundariesOnBothSides) {
  const PriceGate favorable_long =
      price_gate_for_net(1'000'000, Side::LONG, NetBound::AT_OR_ABOVE, kBarrierNetCent).value();
  EXPECT_FALSE(favorable_long.triggers_at_or_below);
  EXPECT_EQ(favorable_long.price_u6, 1'000'558);
  EXPECT_EQ(mark_net_cent(1'000'000, 1'000'558, Side::LONG).value(), 5'004);
  EXPECT_EQ(mark_net_cent(1'000'000, 1'000'557, Side::LONG).value(), 4'994);

  const PriceGate adverse_long =
      price_gate_for_net(1'000'000, Side::LONG, NetBound::AT_OR_BELOW, -kBarrierNetCent).value();
  EXPECT_TRUE(adverse_long.triggers_at_or_below);
  EXPECT_EQ(adverse_long.price_u6, 999'557);
  EXPECT_EQ(mark_net_cent(1'000'000, 999'557, Side::LONG).value(), -5'006);
  EXPECT_EQ(mark_net_cent(1'000'000, 999'558, Side::LONG).value(), -4'996);

  const PriceGate favorable_short =
      price_gate_for_net(1'000'000, Side::SHORT, NetBound::AT_OR_ABOVE, kBarrierNetCent).value();
  EXPECT_TRUE(favorable_short.triggers_at_or_below);
  EXPECT_EQ(favorable_short.price_u6, 999'442);
  EXPECT_EQ(mark_net_cent(1'000'000, 999'442, Side::SHORT).value(), 5'004);

  const PriceGate adverse_short =
      price_gate_for_net(1'000'000, Side::SHORT, NetBound::AT_OR_BELOW, -kBarrierNetCent).value();
  EXPECT_FALSE(adverse_short.triggers_at_or_below);
  EXPECT_EQ(adverse_short.price_u6, 1'000'443);
  EXPECT_EQ(mark_net_cent(1'000'000, 1'000'443, Side::SHORT).value(), -5'006);
}

TEST(MoneyMath, ThePriceGateIsExactAtEveryPriceOverAWideSweep) {
  // The closed-form inversion is an ACCELERATOR of `mark_net_cent`, so it must
  // agree with it at every price, not merely at the boundary the fixtures pin.
  // Sweep a realistic IWM fill and every price within +/-4,000 u6 of it.
  const std::int64_t fill = 172'345'000;
  for (const Side side : {Side::LONG, Side::SHORT}) {
    const PriceGate wall = price_gate_for_net(fill, side, NetBound::AT_OR_BELOW, -30'000).value();
    const PriceGate favorable =
        price_gate_for_net(fill, side, NetBound::AT_OR_ABOVE, kBarrierNetCent).value();
    for (std::int64_t offset = -600'000; offset <= 600'000; offset += 997) {
      const std::int64_t price = fill + offset;
      const std::int64_t net = mark_net_cent(fill, price, side).value();
      const bool wall_gate =
          wall.triggers_at_or_below ? price <= wall.price_u6 : price >= wall.price_u6;
      EXPECT_EQ(wall_gate, net <= -30'000) << "price " << price;
      const bool favorable_gate = favorable.triggers_at_or_below ? price <= favorable.price_u6
                                                                 : price >= favorable.price_u6;
      EXPECT_EQ(favorable_gate, net >= kBarrierNetCent) << "price " << price;
    }
  }
}

TEST(MoneyMath, ANetGateWithTheWrongFracSignRefusesRatherThanGuessingABranch) {
  // Only the two branches the card's own thresholds live on exist; anything
  // else is a refusal, not an untested closed form.
  EXPECT_FALSE(
      price_gate_for_net(1'000'000, Side::LONG, NetBound::AT_OR_BELOW, kBarrierNetCent).has_value());
  EXPECT_FALSE(
      price_gate_for_net(1'000'000, Side::LONG, NetBound::AT_OR_ABOVE, -30'000).has_value());
  EXPECT_FALSE(price_gate_for_net(0, Side::LONG, NetBound::AT_OR_BELOW, -30'000).has_value());
}

TEST(MoneyMath, FloorAndCeilDivisionAreExactOnNegativeNumerators) {
  EXPECT_EQ(floor_div_positive(-29'424, 10), -2'943);
  EXPECT_EQ(ceil_div_positive(-29'424, 10), -2'942);
  EXPECT_EQ(floor_div_positive(5'576, 10), 557);
  EXPECT_EQ(ceil_div_positive(5'576, 10), 558);
  EXPECT_EQ(floor_div_positive(-30, 10), -3);
  EXPECT_EQ(ceil_div_positive(-30, 10), -3);
}

}  // namespace
}  // namespace qr::labels
