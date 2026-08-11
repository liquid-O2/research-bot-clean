#include "qr_core/frames.hpp"

#include <array>
#include <cstdint>
#include <string>
#include <string_view>

namespace qr {
namespace {

constexpr std::int64_t kEpochShiftDays = 719468;  // 1970-01-01 in the era calendar
constexpr std::int64_t kDaysPerEra = 146097;

/// days_from_civil / civil_from_days: Howard Hinnant's public-domain civil
/// calendar algorithms (chrono-Compatible Low-Level Date Algorithms), exact
/// integer arithmetic over the proleptic Gregorian calendar. Used because
/// section 6 needs an exact WRONG_CIVIL_DAY(delta_days) day difference.
constexpr std::int64_t days_from_civil(std::int64_t year, unsigned month, unsigned day) noexcept {
  year -= (month <= 2) ? 1 : 0;
  const std::int64_t era = (year >= 0 ? year : year - 399) / 400;
  const auto year_of_era = static_cast<unsigned>(year - era * 400);
  const unsigned day_of_year = (153U * (month + (month > 2 ? -3U : 9U)) + 2U) / 5U + day - 1U;
  const unsigned day_of_era =
      year_of_era * 365U + year_of_era / 4U - year_of_era / 100U + day_of_year;
  return era * kDaysPerEra + static_cast<std::int64_t>(day_of_era) - kEpochShiftDays;
}

struct CivilYmd {
  std::int64_t year;
  unsigned month;
  unsigned day;
};

constexpr CivilYmd civil_from_days(std::int64_t days) noexcept {
  days += kEpochShiftDays;
  const std::int64_t era = (days >= 0 ? days : days - (kDaysPerEra - 1)) / kDaysPerEra;
  const auto day_of_era = static_cast<unsigned>(days - era * kDaysPerEra);
  const unsigned year_of_era =
      (day_of_era - day_of_era / 1460U + day_of_era / 36524U - day_of_era / 146096U) / 365U;
  const std::int64_t year = static_cast<std::int64_t>(year_of_era) + era * 400;
  const unsigned day_of_year =
      day_of_era - (365U * year_of_era + year_of_era / 4U - year_of_era / 100U);
  const unsigned mp = (5U * day_of_year + 2U) / 153U;
  const unsigned day = day_of_year - (153U * mp + 2U) / 5U + 1U;
  const unsigned month = mp + (mp < 10U ? 3U : -9U);
  return CivilYmd{year + (month <= 2U ? 1 : 0), month, day};
}

constexpr bool is_leap_year(std::int64_t year) noexcept {
  return (year % 4 == 0 && year % 100 != 0) || year % 400 == 0;
}

constexpr unsigned days_in_month(std::int64_t year, unsigned month) noexcept {
  constexpr std::array<unsigned, 13> kLengths = {0U,  31U, 28U, 31U, 30U, 31U, 30U,
                                                 31U, 31U, 30U, 31U, 30U, 31U};
  if (month == 2U && is_leap_year(year)) {
    return 29U;
  }
  return kLengths[month];
}

constexpr bool all_digits(std::string_view text) noexcept {
  for (const char c : text) {
    if (c < '0' || c > '9') {
      return false;
    }
  }
  return true;
}

constexpr std::int64_t digits_to_int(std::string_view text) noexcept {
  std::int64_t value = 0;
  for (const char c : text) {
    value = value * 10 + static_cast<std::int64_t>(c - '0');
  }
  return value;
}

constexpr Refusal malformed(const char* detail) noexcept {
  return Refusal(RefusalCode::MALFORMED_CIVIL_DATE, "qr_core::CivilDate::parse_ymd", detail);
}

}  // namespace

Expected<CivilDate, Refusal> CivilDate::parse_ymd(std::string_view text) noexcept {
  if (text.size() != 10) {
    return Expected<CivilDate, Refusal>::refuse(
        malformed("civil day is not exactly 10 characters"));
  }
  if (text[4] != '-' || text[7] != '-') {
    return Expected<CivilDate, Refusal>::refuse(malformed("civil day is not YYYY-MM-DD"));
  }
  const std::string_view year_text = text.substr(0, 4);
  const std::string_view month_text = text.substr(5, 2);
  const std::string_view day_text = text.substr(8, 2);
  if (!all_digits(year_text) || !all_digits(month_text) || !all_digits(day_text)) {
    return Expected<CivilDate, Refusal>::refuse(malformed("civil day carries a non-digit"));
  }
  const std::int64_t year = digits_to_int(year_text);
  const auto month = static_cast<unsigned>(digits_to_int(month_text));
  const auto day = static_cast<unsigned>(digits_to_int(day_text));
  if (month < 1U || month > 12U) {
    return Expected<CivilDate, Refusal>::refuse(malformed("civil month outside 01..12"));
  }
  if (day < 1U || day > days_in_month(year, month)) {
    return Expected<CivilDate, Refusal>::refuse(
        malformed("civil day outside the month's real length"));
  }
  return CivilDate(days_from_civil(year, month, day));
}

std::string CivilDate::to_ymd() const {
  const CivilYmd ymd = civil_from_days(days_);
  std::string out(10, '-');
  std::int64_t year = ymd.year;
  for (int i = 3; i >= 0; --i) {
    out[static_cast<std::size_t>(i)] = static_cast<char>('0' + (year % 10));
    year /= 10;
  }
  out[5] = static_cast<char>('0' + (ymd.month / 10U));
  out[6] = static_cast<char>('0' + (ymd.month % 10U));
  out[8] = static_cast<char>('0' + (ymd.day / 10U));
  out[9] = static_cast<char>('0' + (ymd.day % 10U));
  return out;
}

}  // namespace qr
