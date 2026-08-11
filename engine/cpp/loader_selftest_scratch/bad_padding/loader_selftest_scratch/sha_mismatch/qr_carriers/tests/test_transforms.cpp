// test_transforms.cpp — THE EXHAUSTIVE TRANSFORM TABLE, ROW BY ROW, ON HAND
// LITERALS.
//
// The card's table has seven rows and this file has a case per row plus the
// three the brief names explicitly: "checked integer bps truncation, log1p us,
// sign*log1p". Every expected number below is arithmetic done by hand in the
// comment beside it — none of it is produced by calling the function under test.
#include <gtest/gtest.h>

#include <cmath>
#include <limits>

#include "qr_carriers/transforms.hpp"

namespace qr::carriers {
namespace {

// log(100) = 4.605170185988091368...  (log1p(99) = log(100))
constexpr double kLog100 = 4.6051701859880913680;
// log(1000000) = 13.815510557964274104...  (log1p(999999))
constexpr double kLog1e6 = 13.815510557964274104;
// log(30) = 3.40119738166215537... (log1p(29))
constexpr double kLog30 = 3.4011973816621554;
// log1p(1.5) = 0.91629073187415506518...
constexpr double kLog1p1p5 = 0.91629073187415506518;

TEST(TransformTable, NonnegativeCountRowIsLog1pAndRefusesItsOwnDomain) {
  // Row 1: "nonnegative count/size -> log1p(x)".
  EXPECT_EQ(count_log1p(0).v, Validity::VALID);
  EXPECT_DOUBLE_EQ(count_log1p(0).value, 0.0);  // log1p(0) = 0 exactly
  EXPECT_NEAR(count_log1p(99).value, kLog100, 1e-15);
  // A negative count is outside the declared domain: masked, never folded
  // through log1p (which is NaN below -1).
  EXPECT_EQ(count_log1p(-1).v, Validity::NONPOSITIVE);
  EXPECT_DOUBLE_EQ(count_log1p(-1).value, 0.0);
}

TEST(TransformTable, TimeRowIsCheckedIntegerMicrosecondsThenLog1p) {
  // Row 2: "time/gap/age/span -> checked integer microseconds, then log1p(us)".
  // (2'000'000 - 1'000) ns = 1'999'000 ns = 1999 us exactly.
  const auto micros = duration_micros(1'000, 2'000'000);
  ASSERT_TRUE(micros.has_value());
  EXPECT_EQ(micros.value(), 1'999);
  // The tape is millisecond stamped, so a real difference is a whole 1000us.
  const auto whole_ms = duration_micros(0, 5 * 1'000'000);
  ASSERT_TRUE(whole_ms.has_value());
  EXPECT_EQ(whole_ms.value(), 5'000);
  // log1p(999'999) = log(1'000'000).
  EXPECT_NEAR(time_log1p_micros(999'999).value, kLog1e6, 1e-13);
  EXPECT_DOUBLE_EQ(time_log1p_micros(0).value, 0.0);
  EXPECT_EQ(time_log1p_micros(-1).v, Validity::NONPOSITIVE);
  // Overflow is a refusal, never a wrapped or saturated span.
  const auto overflow = duration_micros(std::numeric_limits<std::int64_t>::min(), 1);
  EXPECT_FALSE(overflow.has_value());
  EXPECT_EQ(overflow.error().code(), RefusalCode::ARITHMETIC_OVERFLOW);
}

TEST(TransformTable, SecondsDoorIsTheSameClockDividedByAMillion) {
  // Section 5's three "log1p ... seconds" channels: 1'500'000us = 1.5s, and
  // log1p(1.5) = 0.916290731874155...
  EXPECT_NEAR(time_log1p_seconds(1'500'000).value, kLog1p1p5, 1e-15);
  EXPECT_DOUBLE_EQ(time_log1p_seconds(0).value, 0.0);
  EXPECT_EQ(time_log1p_seconds(-1).v, Validity::NONPOSITIVE);
}

TEST(TransformTable, SignedRowIsOddAndCarriesTheSignThroughLog1p) {
  // Row 3: "signed size/flow/gap -> sign(x)*log1p(abs(x))".
  EXPECT_NEAR(signed_log1p(99.0).value, kLog100, 1e-15);
  EXPECT_NEAR(signed_log1p(-99.0).value, -kLog100, 1e-15);
  // Odd at the origin, and exactly +0.0 (not -0.0, which is a different bit
  // pattern and would break two-run byte identity after an orientation flip).
  EXPECT_DOUBLE_EQ(signed_log1p(0.0).value, 0.0);
  EXPECT_FALSE(std::signbit(signed_log1p(0.0).value));
  EXPECT_NEAR(signed_log1p_int(-99).value, -kLog100, 1e-15);
  EXPECT_EQ(signed_log1p(std::numeric_limits<double>::quiet_NaN()).v, Validity::NONFINITE);
  EXPECT_EQ(signed_log1p(std::numeric_limits<double>::infinity()).v, Validity::NONFINITE);
}

TEST(TransformTable, PriceDisplacementRowTruncatesTowardZeroOnCheckedIntegers) {
  // Row 4: "checked truncating integer bps `(num_u6*10000)/positive_den_u6`".
  // 12'345 * 10'000 = 123'450'000; / 1'000'000 = 123.45 -> TRUNCATED to 123.
  const auto positive = displacement_bps(12'345, 1'000'000);
  ASSERT_TRUE(positive.has_value());
  EXPECT_EQ(positive.value().v, Validity::VALID);
  EXPECT_EQ(positive.value().value, 123);
  // Truncation is toward ZERO, so the negative case is -123, not -124.
  const auto negative = displacement_bps(-12'345, 1'000'000);
  ASSERT_TRUE(negative.has_value());
  EXPECT_EQ(negative.value().value, -123);
  // A sub-basis-point move truncates to exactly 0 and stays PRESENT: 0 bps is a
  // measured displacement, not a missing one.
  //   1 * 10'000 / 99'999'999 = 0.0001 -> 0
  const auto tiny = displacement_bps(1, 99'999'999);
  ASSERT_TRUE(tiny.has_value());
  EXPECT_EQ(tiny.value().v, Validity::VALID);
  EXPECT_EQ(tiny.value().value, 0);
  // "invalid denominator is missing" — zero and negative both.
  const auto zero_den = displacement_bps(5, 0);
  ASSERT_TRUE(zero_den.has_value());
  EXPECT_EQ(zero_den.value().v, Validity::MISSING);
  EXPECT_EQ(zero_den.value().value, 0);
  const auto negative_den = displacement_bps(5, -1'000'000);
  ASSERT_TRUE(negative_den.has_value());
  EXPECT_EQ(negative_den.value().v, Validity::MISSING);
  // The multiply is CHECKED: 2^62 * 10'000 does not fit i64.
  const auto overflow = displacement_bps(std::int64_t{1} << 62, 1);
  EXPECT_FALSE(overflow.has_value());
  EXPECT_EQ(overflow.error().code(), RefusalCode::ARITHMETIC_OVERFLOW);
}

TEST(TransformTable, FractionRowEmitsValueZeroPresenceZeroOnAZeroDenominator) {
  // Row 5: "numerator/max(eligible_denominator,1); denominator zero emits
  // value0, presence0".
  EXPECT_EQ(fraction(3, 4).v, Validity::VALID);
  EXPECT_DOUBLE_EQ(fraction(3, 4).value, 0.75);
  EXPECT_EQ(fraction(1, 0).v, Validity::MISSING);
  EXPECT_DOUBLE_EQ(fraction(1, 0).value, 0.0);
  EXPECT_EQ(fraction(1, -3).v, Validity::MISSING);
}

TEST(TransformTable, ReliabilityRModalityIsTheOneDeclaredPresentWithZeroCase) {
  // "`r_modality = finite-all-four group count / max(group count,1)` (0 when
  // empty)" — the empty case has a DEFINED value, because section 5 multiplies
  // by it. 3/4 = 0.75; 0/max(0,1) = 0 and PRESENT.
  EXPECT_DOUBLE_EQ(reliability_r_modality(3, 4).value, 0.75);
  EXPECT_EQ(reliability_r_modality(0, 0).v, Validity::VALID);
  EXPECT_DOUBLE_EQ(reliability_r_modality(0, 0).value, 0.0);
}

TEST(TransformTable, RawGreekRowAppliesNoTransformAndTypesTheNonFinite) {
  // Row 6: "finite raw dimensionless value, no nonlinear transform".
  EXPECT_DOUBLE_EQ(raw_dimensionless(0.5).value, 0.5);
  EXPECT_DOUBLE_EQ(raw_dimensionless(-0.0625).value, -0.0625);
  EXPECT_EQ(raw_dimensionless(std::numeric_limits<double>::infinity()).v, Validity::NONFINITE);
  EXPECT_DOUBLE_EQ(raw_dimensionless(std::numeric_limits<double>::infinity()).value, 0.0);
}

TEST(TransformTable, DteRowIsLog1pOfNonnegativeCalendarDays) {
  // Row 7: "nonnegative calendar days, then log1p(days)". log1p(29) = log(30).
  EXPECT_DOUBLE_EQ(dte_log1p_days(0).value, 0.0);  // 0DTE is lawful and present
  EXPECT_NEAR(dte_log1p_days(29).value, kLog30, 1e-15);
  EXPECT_EQ(dte_log1p_days(-1).v, Validity::NONPOSITIVE);
}

TEST(TransformTable, StructuralBitsAndFiniteMeansFollowTheirOwnStatedLaws) {
  // "structurally observed binary quality values use presence1".
  EXPECT_EQ(structural_bit(false).v, Validity::VALID);
  EXPECT_DOUBLE_EQ(structural_bit(false).value, 0.0);
  EXPECT_DOUBLE_EQ(structural_bit(true).value, 1.0);
  // "All token/group/bin means divide only by the number of finite present
  // members; zero such members emits value0/presence0." 7.5/3 = 2.5.
  EXPECT_DOUBLE_EQ(finite_member_mean(7.5, 3).value, 2.5);
  EXPECT_EQ(finite_member_mean(0.0, 0).v, Validity::MISSING);
}

}  // namespace
}  // namespace qr::carriers
