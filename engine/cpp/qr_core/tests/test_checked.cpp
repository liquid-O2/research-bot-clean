// Fixture ARITH-1..ARITH-4: checked integer arithmetic refuses on overflow and
// never substitutes a boundary value for the true result.
#include <cstdint>
#include <limits>

#include "gtest/gtest.h"
#include "qr_core/checked.hpp"

namespace {

constexpr std::int64_t kMax = std::numeric_limits<std::int64_t>::max();
constexpr std::int64_t kMin = std::numeric_limits<std::int64_t>::min();

TEST(CheckedArithmetic, AddOverflowIsARefusalNotAValue) {
  const auto result = qr::checked_add(kMax, 1);
  ASSERT_FALSE(result.has_value()) << "INT64_MAX + 1 must never produce a number";
  EXPECT_EQ(result.error().code(), qr::RefusalCode::ARITHMETIC_OVERFLOW);
  EXPECT_STREQ(result.error().site(), "qr_core::checked_add");

  const auto negative = qr::checked_add(kMin, -1);
  ASSERT_FALSE(negative.has_value());
  EXPECT_EQ(negative.error().code(), qr::RefusalCode::ARITHMETIC_OVERFLOW);
}

// Every accessor below is guarded: a broken implementation must make these
// tests FAIL (and so appear in a red log), never abort the whole binary.
void expect_sum(std::int64_t a, std::int64_t b, std::int64_t expected) {
  const auto result = qr::checked_add(a, b);
  ASSERT_TRUE(result.has_value()) << a << " + " << b << " refused unexpectedly";
  EXPECT_EQ(result.value(), expected);
}

TEST(CheckedArithmetic, AddReturnsTheExactSumInsideTheDomain) {
  const auto result = qr::checked_add(kMax - 1, 1);
  ASSERT_TRUE(result.has_value());
  EXPECT_EQ(result.value(), kMax);
  expect_sum(0, 0, 0);
  expect_sum(-5, 12, 7);
  expect_sum(kMin, kMax, -1);
}

TEST(CheckedArithmetic, SubOverflowIsARefusal) {
  const auto result = qr::checked_sub(kMin, 1);
  ASSERT_FALSE(result.has_value());
  EXPECT_EQ(result.error().code(), qr::RefusalCode::ARITHMETIC_OVERFLOW);
  EXPECT_STREQ(result.error().site(), "qr_core::checked_sub");

  ASSERT_FALSE(qr::checked_sub(kMax, -1).has_value());
  const auto small = qr::checked_sub(10, 4);
  ASSERT_TRUE(small.has_value());
  EXPECT_EQ(small.value(), 6);
  const auto zero = qr::checked_sub(kMin, kMin);
  ASSERT_TRUE(zero.has_value());
  EXPECT_EQ(zero.value(), 0);
}

TEST(CheckedArithmetic, MulOverflowIsARefusal) {
  const auto result = qr::checked_mul(kMax, 2);
  ASSERT_FALSE(result.has_value());
  EXPECT_EQ(result.error().code(), qr::RefusalCode::ARITHMETIC_OVERFLOW);
  EXPECT_STREQ(result.error().site(), "qr_core::checked_mul");

  ASSERT_FALSE(qr::checked_mul(kMin, -1).has_value());
  const auto zero = qr::checked_mul(0, kMax);
  ASSERT_TRUE(zero.has_value());
  EXPECT_EQ(zero.value(), 0);
  const auto negative = qr::checked_mul(-3, 7);
  ASSERT_TRUE(negative.has_value());
  EXPECT_EQ(negative.value(), -21);
  // The bar-cutoff arithmetic the calendar needs: 390 bars * 60e9 ns.
  const auto span = qr::checked_mul(390, 60'000'000'000);
  ASSERT_TRUE(span.has_value());
  EXPECT_EQ(span.value(), 23'400'000'000'000);
}

TEST(CheckedArithmetic, RefusalCarriesNoSubstituteValue) {
  const auto refused = qr::checked_mul(kMax, kMax);
  ASSERT_FALSE(refused.has_value());
  // There is no accessor that yields a number here, and the refusal message
  // names the site rather than reporting a range boundary as if it were a sum.
  EXPECT_NE(refused.error().message().find("ARITHMETIC_OVERFLOW"), std::string::npos);
  EXPECT_NE(refused.error().message().find("qr_core::checked_mul"), std::string::npos);
}

TEST(ExpectedCarrier, DistinguishesValueFromRefusalWithoutExceptions) {
  const qr::Expected<std::int64_t, qr::Refusal> ok = std::int64_t{7};
  ASSERT_TRUE(ok.has_value());
  EXPECT_TRUE(static_cast<bool>(ok));
  EXPECT_EQ(ok.value(), 7);

  const auto bad = qr::Expected<std::int64_t, qr::Refusal>::refuse(
      qr::Refusal(qr::RefusalCode::CONFIG, "test", "deliberate", 3));
  EXPECT_FALSE(bad.has_value());
  EXPECT_FALSE(static_cast<bool>(bad));
  EXPECT_EQ(bad.error().code(), qr::RefusalCode::CONFIG);
  EXPECT_EQ(bad.error().context(), 3);
  EXPECT_NE(bad.error().message().find("context=3"), std::string::npos);
}

TEST(RefusalTaxonomy, EveryPortedCodeHasItsOwnName) {
  EXPECT_STREQ(qr::refusal_code_name(qr::RefusalCode::REGISTRY_DIGEST_MISMATCH),
               "REGISTRY_DIGEST_MISMATCH");
  EXPECT_STREQ(qr::refusal_code_name(qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE),
               "ORDINAL_OUTSIDE_SCOPE");
  EXPECT_STREQ(qr::refusal_code_name(qr::RefusalCode::DAY_OUTSIDE_CALENDAR),
               "DAY_OUTSIDE_CALENDAR");
  EXPECT_STREQ(qr::refusal_code_name(qr::RefusalCode::ARITHMETIC_OVERFLOW), "ARITHMETIC_OVERFLOW");
  EXPECT_STREQ(qr::refusal_code_name(static_cast<qr::RefusalCode>(200)), "UNKNOWN_REFUSAL");
}

}  // namespace
