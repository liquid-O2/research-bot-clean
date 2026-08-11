// Shared fixture support for the WP2 clock suite.
//
// THE THREE PINNED FIXTURE SESSIONS are the ones the reference port pins
// (session_clock.rs:669-671): one EDT full day, one EST full day, one 210-bar
// early close. Nothing here computes a timezone: every expected value is
// derived from the authenticated registry row, in the test.
#ifndef QR_CLOCK_TESTS_CLOCK_TEST_SUPPORT_HPP
#define QR_CLOCK_TESTS_CLOCK_TEST_SUPPORT_HPP

#include <string>
#include <string_view>
#include <utility>

#include "qr_clock/session_clock.hpp"
#include "qr_core/frames.hpp"
#include "qr_registry/registry.hpp"

namespace qr_clock_test {

/// One EDT full day, one EST full day, one 210-bar early close.
inline constexpr std::string_view kEdtFullDay = "2024-05-24";
inline constexpr std::string_view kEstFullDay = "2024-01-16";
inline constexpr std::string_view kEarlyClose = "2024-07-03";

inline constexpr std::int64_t kHourNs = 3'600'000'000'000;

inline const qr::Registry& registry() {
  static const qr::Registry loaded = [] {
    auto result = qr::Registry::load_embedded();
    if (!result.has_value()) {
      qr::detail::fail_fast("clock fixtures: the embedded registry failed its digest gate");
    }
    return std::move(result).value();
  }();
  return loaded;
}

inline qr::CivilDate date(std::string_view ymd) {
  auto parsed = qr::CivilDate::parse_ymd(ymd);
  if (!parsed.has_value()) {
    qr::detail::fail_fast("clock fixtures: fixture day is not a canonical civil date");
  }
  return std::move(parsed).value();
}

inline const qr::Session& session(std::string_view ymd) {
  auto ordinal = registry().ordinal_of_day(ymd);
  if (!ordinal.has_value()) {
    qr::detail::fail_fast("clock fixtures: fixture day has no registry row");
  }
  auto row = registry().session_at(ordinal.value());
  if (!row.has_value()) {
    qr::detail::fail_fast("clock fixtures: registry ordinal did not resolve");
  }
  return *row.value();
}

inline qr::SessionClock clock(std::string_view ymd) {
  auto built = qr::SessionClock::for_day(registry(), date(ymd));
  if (!built.has_value()) {
    qr::detail::fail_fast("clock fixtures: pinned fixture session failed to build a clock");
  }
  return std::move(built).value();
}

/// The registry-derived frame-B open of a session, recomputed IN THE TEST from
/// the session's own civil date and the 09:30 wall convention written out here
/// in literals — so a mutation of the module's own constant is caught rather
/// than mirrored.
inline std::int64_t expected_open_b_ns(const qr::Session& row) {
  const std::int64_t midnight_ms = row.civil_date.days_since_epoch() * 86'400'000LL;
  const std::int64_t open_ms = midnight_ms + (9LL * 3'600'000LL + 30LL * 60'000LL);
  return open_ms * 1'000'000LL;
}

/// A message that is safe to stream whether or not the result refused.
template <class T>
inline std::string why(const qr::Expected<T, qr::Refusal>& result) {
  return result.has_value() ? std::string("<value>") : result.error().message();
}

}  // namespace qr_clock_test

#endif  // QR_CLOCK_TESTS_CLOCK_TEST_SUPPORT_HPP
