// Fixture FRAME-1..FRAME-5: the frame-A / frame-B / civil-date type wall.
//
// FRAME-1 is the non-convertibility fixture named in the WP1 brief: a bare
// int64 must never become a FrameB implicitly, and the compile-fail companion
// (ci/check_compile_fail.sh) proves the same thing at the compiler level.
#include <cstdint>
#include <string>
#include <type_traits>

#include "gtest/gtest.h"
#include "qr_core/frames.hpp"

namespace {

TEST(FrameTypes, NoImplicitConversionInEitherDirection) {
  EXPECT_FALSE((std::is_convertible_v<std::int64_t, qr::FrameB>));
  EXPECT_FALSE((std::is_convertible_v<std::int64_t, qr::FrameA>));
  EXPECT_FALSE((std::is_convertible_v<std::int64_t, qr::CivilDate>));
  EXPECT_FALSE((std::is_convertible_v<int, qr::FrameB>));
  EXPECT_FALSE((std::is_convertible_v<double, qr::FrameB>));
  EXPECT_FALSE((std::is_convertible_v<bool, qr::FrameB>));
  EXPECT_FALSE((std::is_convertible_v<qr::FrameB, std::int64_t>));
  EXPECT_FALSE((std::is_convertible_v<qr::FrameA, std::int64_t>));
  EXPECT_FALSE((std::is_convertible_v<qr::CivilDate, std::int64_t>));
  EXPECT_FALSE((std::is_convertible_v<qr::FrameA, qr::FrameB>));
  EXPECT_FALSE((std::is_convertible_v<qr::FrameB, qr::FrameA>));
  EXPECT_FALSE((std::is_constructible_v<qr::FrameB, qr::FrameA>));
  EXPECT_FALSE((std::is_constructible_v<qr::FrameB, int>));
  EXPECT_FALSE((std::is_constructible_v<qr::FrameB, double>));
  EXPECT_FALSE((std::is_default_constructible_v<qr::FrameA>));
  EXPECT_FALSE((std::is_default_constructible_v<qr::FrameB>));
  EXPECT_FALSE((std::is_default_constructible_v<qr::CivilDate>));
}

TEST(FrameTypes, FrameAHasExactlyOnePublicMint) {
  // No public constructor at all: the ONLY producer is the greppable factory.
  EXPECT_FALSE((std::is_constructible_v<qr::FrameA, std::int64_t>));
  const qr::FrameA instant = qr::FrameA::from_published_utc_epoch_ns(1'641'220'200'000'000'000);
  EXPECT_EQ(instant.ns(), 1'641'220'200'000'000'000);
  EXPECT_TRUE((std::is_same_v<decltype(qr::FrameA::from_published_utc_epoch_ns(0)), qr::FrameA>));
}

TEST(FrameTypes, FrameBWrapsExactNanosecondsAndOrders) {
  const qr::FrameB early{std::int64_t{1'641'220'200'000'000'000}};
  const qr::FrameB late{std::int64_t{1'641'243'600'000'000'000}};
  EXPECT_EQ(early.ns(), 1'641'220'200'000'000'000);
  EXPECT_LT(early, late);
  EXPECT_EQ(early, qr::FrameB{std::int64_t{1'641'220'200'000'000'000}});
  EXPECT_EQ(sizeof(qr::FrameB), sizeof(std::int64_t));
}

TEST(CivilDateType, ParsesCanonicalDaysAndRoundTrips) {
  const auto epoch = qr::CivilDate::parse_ymd("1970-01-01");
  ASSERT_TRUE(epoch.has_value());
  EXPECT_EQ(epoch.value().days_since_epoch(), 0);
  EXPECT_EQ(epoch.value().to_ymd(), "1970-01-01");

  for (const char* day : {"2022-01-03", "2022-07-05", "2024-02-29", "2024-12-26", "2025-12-31",
                          "2000-02-29", "2026-01-02"}) {
    const auto parsed = qr::CivilDate::parse_ymd(day);
    ASSERT_TRUE(parsed.has_value()) << day;
    EXPECT_EQ(parsed.value().to_ymd(), std::string(day));
  }
}

TEST(CivilDateType, RefusesEveryNonCanonicalCivilDay) {
  for (const char* bad : {"2022-1-03", "2022-01-3", "20220103", "2022-13-01", "2022-00-01",
                          "2022-01-00", "2022-01-32", "2023-02-29", "2100-02-29", "2022-02-30",
                          "2022-04-31", "yyyy-mm-dd", "2022-01-0x", "", "2022-01-030"}) {
    const auto parsed = qr::CivilDate::parse_ymd(bad);
    ASSERT_FALSE(parsed.has_value()) << "accepted malformed civil day: " << bad;
    EXPECT_EQ(parsed.error().code(), qr::RefusalCode::MALFORMED_CIVIL_DATE) << bad;
  }
}

TEST(CivilDateType, DeltaDaysIsExactSignedDayArithmetic) {
  const auto first = qr::CivilDate::parse_ymd("2022-07-05");
  const auto second = qr::CivilDate::parse_ymd("2022-07-06");
  const auto leap_before = qr::CivilDate::parse_ymd("2024-02-28");
  const auto leap_after = qr::CivilDate::parse_ymd("2024-03-01");
  ASSERT_TRUE(first.has_value());
  ASSERT_TRUE(second.has_value());
  ASSERT_TRUE(leap_before.has_value());
  ASSERT_TRUE(leap_after.has_value());

  EXPECT_EQ(second.value().delta_days(first.value()), 1);
  EXPECT_EQ(first.value().delta_days(second.value()), -1);
  EXPECT_EQ(first.value().delta_days(first.value()), 0);
  EXPECT_EQ(leap_after.value().delta_days(leap_before.value()), 2)
      << "2024 is a leap year: 02-28 -> 03-01 is two days";
  EXPECT_LT(first.value(), second.value());
}

}  // namespace
