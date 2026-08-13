#include "qr_futsess/calendar.hpp"

#include <cstdio>
#include <cstdlib>
#include <ctime>

#include "qr_futsess/constants.hpp"

namespace qr::futsess {
namespace {

// days_from_civil / civil_from_days: Howard Hinnant's proleptic Gregorian
// algorithms. Exact integer arithmetic, no time-zone involvement, valid across
// the whole range this program touches.
std::int64_t days_from_civil(std::int64_t y, std::int64_t m, std::int64_t d) {
  y -= (m <= 2) ? 1 : 0;
  const std::int64_t era = (y >= 0 ? y : y - 399) / 400;
  const std::int64_t yoe = y - era * 400;
  const std::int64_t doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
  const std::int64_t doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
  return era * 146097 + doe - 719468;
}

}  // namespace

std::string Date::iso() const {
  char buf[16];
  std::snprintf(buf, sizeof(buf), "%04d-%02d-%02d", year, month, day);
  return std::string(buf);
}

std::string Date::compact() const {
  char buf[16];
  std::snprintf(buf, sizeof(buf), "%04d%02d%02d", year, month, day);
  return std::string(buf);
}

std::int64_t date_to_day(const Date& d) { return days_from_civil(d.year, d.month, d.day); }

Date day_to_date(std::int64_t z) {
  z += 719468;
  const std::int64_t era = (z >= 0 ? z : z - 146096) / 146097;
  const std::int64_t doe = z - era * 146097;
  const std::int64_t yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
  const std::int64_t y = yoe + era * 400;
  const std::int64_t doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
  const std::int64_t mp = (5 * doy + 2) / 153;
  const std::int64_t d = doy - (153 * mp + 2) / 5 + 1;
  const std::int64_t m = mp + (mp < 10 ? 3 : -9);
  Date out;
  out.year = static_cast<std::int32_t>(y + ((m <= 2) ? 1 : 0));
  out.month = static_cast<std::int32_t>(m);
  out.day = static_cast<std::int32_t>(d);
  return out;
}

Date date_from_yyyymmdd(std::int32_t v) {
  Date d;
  d.year = v / 10000;
  d.month = (v / 100) % 100;
  d.day = v % 100;
  return d;
}

namespace {

std::int64_t local_to_epoch(const Date& d, int hour) {
  std::tm tmv{};
  tmv.tm_year = d.year - 1900;
  tmv.tm_mon = d.month - 1;
  tmv.tm_mday = d.day;
  tmv.tm_hour = hour;
  tmv.tm_min = 0;
  tmv.tm_sec = 0;
  tmv.tm_isdst = -1;  // let the tz database decide the offset for this instant
  return static_cast<std::int64_t>(std::mktime(&tmv));
}

}  // namespace

Expected<std::monostate, Refusal> init_globex_timezone() {
  ::setenv("TZ", "America/Chicago", 1);
  ::tzset();
  // A tz database that failed to load leaves mktime on UTC and would silently
  // shift every session by five or six hours. These two instants are pinned
  // from the reference clock (Python zoneinfo, America/Chicago): one in CST,
  // one in CDT, so a fixed-offset fallback fails at least one of them.
  struct Probe {
    Date date;
    int hour;
    std::int64_t expect;
  };
  const Probe probes[] = {
      {Date{2024, 1, 1}, 17, 1704150000},  // 17:00 CST = 23:00Z
      {Date{2024, 7, 1}, 17, 1719871200},  // 17:00 CDT = 22:00Z
  };
  for (const Probe& p : probes) {
    const std::int64_t got = local_to_epoch(p.date, p.hour);
    if (got != p.expect) {
      return refuse<std::monostate>(
          Refusal(RefusalCode::CLOCK_VIOLATION, "qr_futsess::init_globex_timezone",
                  "America/Chicago tz rules did not load — session clock would be wrong",
                  got - p.expect));
    }
  }
  return std::monostate{};
}

std::pair<std::int64_t, std::int64_t> session_bounds(const Date& trade_date) {
  const Date prev = day_to_date(date_to_day(trade_date) - 1);
  // NOTE (faithful to s3_sessions.session_bounds): the span is 23h on every
  // date whose [17:00 d-1, 16:00 d) window does not straddle a DST transition.
  // The two Sunday trade dates per year that DO straddle one produce a 22h or
  // 24h window; the reference computes them the same way and those sessions
  // carry no two-sided seconds (the market is shut from Saturday 17:00), so
  // they are dropped by the n_valid == 0 rule before any receipt is written.
  return {local_to_epoch(prev, 17), local_to_epoch(trade_date, 16)};
}

}  // namespace qr::futsess
