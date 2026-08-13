// qr_futsess/calendar.hpp — civil dates, UTC day indices, and the DST-correct
// Globex session clock.
//
// SPEC: design/PORT_M0_CENSUS_SPEC.md §5 — "Globex trade date d =
// [17:00 America/Chicago on d-1, 16:00 on d), converted to UTC per-date via
// zoneinfo (DST-correct)". The reference does this with Python's zoneinfo; the
// port does it with the system tz database through mktime(), which reads the
// same IANA rules. Both endpoints (17:00 and 16:00 local) sit far from the
// 02:00 transition instant, so neither is ever ambiguous or nonexistent.
#ifndef QR_FUTSESS_CALENDAR_HPP
#define QR_FUTSESS_CALENDAR_HPP

#include <cstdint>
#include <string>
#include <utility>

#include "qr_core/refusal.hpp"

namespace qr::futsess {

/// A civil date. Comparison order is calendar order.
struct Date {
  std::int32_t year = 0;
  std::int32_t month = 0;
  std::int32_t day = 0;

  [[nodiscard]] std::int32_t yyyymmdd() const { return year * 10000 + month * 100 + day; }
  [[nodiscard]] std::string iso() const;      // YYYY-MM-DD
  [[nodiscard]] std::string compact() const;  // YYYYMMDD

  friend bool operator==(const Date& a, const Date& b) {
    return a.year == b.year && a.month == b.month && a.day == b.day;
  }
  friend bool operator!=(const Date& a, const Date& b) { return !(a == b); }
  friend bool operator<(const Date& a, const Date& b) { return a.yyyymmdd() < b.yyyymmdd(); }
};

/// Days since 1970-01-01 (the index M0 calls `utc_day`).
[[nodiscard]] std::int64_t date_to_day(const Date& d);
[[nodiscard]] Date day_to_date(std::int64_t day_index);
[[nodiscard]] Date date_from_yyyymmdd(std::int32_t v);

/// Install America/Chicago as the process timezone and PROVE it loaded against
/// two pinned instants (one CST, one CDT). Must be called once, before any
/// session_bounds() call, and never concurrently with one.
[[nodiscard]] Expected<std::monostate, Refusal> init_globex_timezone();

/// [open_utc, close_utc) of the Globex trade date, in epoch seconds.
[[nodiscard]] std::pair<std::int64_t, std::int64_t> session_bounds(const Date& trade_date);

}  // namespace qr::futsess

#endif  // QR_FUTSESS_CALENDAR_HPP
