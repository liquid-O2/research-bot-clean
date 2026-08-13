#include "qr_gen/calendar.hpp"

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <fstream>

namespace qr::gen {
namespace {

using std::chrono::days;
using std::chrono::hours;
using std::chrono::local_days;
using std::chrono::local_info;
using std::chrono::local_seconds;
using std::chrono::minutes;
using std::chrono::seconds;
using std::chrono::sys_seconds;
using std::chrono::time_zone;
using std::chrono::year_month_day;

const time_zone* zone_or_null(const char* tz) {
  // locate_zone throws when the tz database has no such zone; a generation run
  // must never continue on a silently substituted UTC.
  try {
    return std::chrono::locate_zone(tz);
  } catch (...) {
    return nullptr;
  }
}

/// The twelve month names as calendar_fomc.csv spells them, plus the three-
/// letter abbreviations the span rows use ("Jan/Feb", "Oct/Nov").
const char* const kMonthNames[12] = {"January", "February", "March",     "April",
                                     "May",     "June",     "July",      "August",
                                     "September", "October", "November", "December"};

int month_index(const std::string& s) {
  for (int i = 0; i < 12; ++i) {
    if (s == kMonthNames[i]) {
      return i + 1;
    }
  }
  for (int i = 0; i < 12; ++i) {
    if (s.size() == 3 && s.compare(0, 3, kMonthNames[i], 0, 3) == 0) {
      return i + 1;
    }
  }
  return -1;
}

std::string trim(const std::string& s) {
  std::size_t a = 0;
  std::size_t b = s.size();
  while (a < b && (s[a] == ' ' || s[a] == '\t' || s[a] == '\r' || s[a] == '\n')) {
    ++a;
  }
  while (b > a && (s[b - 1] == ' ' || s[b - 1] == '\t' || s[b - 1] == '\r' || s[b - 1] == '\n')) {
    --b;
  }
  return s.substr(a, b - a);
}

std::vector<std::string> split(const std::string& s, char sep) {
  std::vector<std::string> out;
  std::size_t a = 0;
  for (;;) {
    const std::size_t p = s.find(sep, a);
    if (p == std::string::npos) {
      out.push_back(s.substr(a));
      return out;
    }
    out.push_back(s.substr(a, p - a));
    a = p + 1;
  }
}

bool all_digits(const std::string& s) {
  if (s.empty()) {
    return false;
  }
  for (char c : s) {
    if (c < '0' || c > '9') {
      return false;
    }
  }
  return true;
}

}  // namespace

std::vector<std::int32_t> local_epoch_offsets(std::int64_t open_utc, std::int32_t n, const char* tz,
                                              int hh, int mm) {
  std::vector<std::int32_t> out;
  const time_zone* z = zone_or_null(tz);
  if (z == nullptr || n <= 0) {
    return out;
  }
  const local_seconds base = z->to_local(sys_seconds{seconds{open_utc}});
  const local_days base_day = std::chrono::floor<days>(base);
  for (int dd = -1; dd <= 1; ++dd) {
    const local_seconds lt =
        local_seconds{(base_day + days{dd}).time_since_epoch()} + hours{hh} + minutes{mm};
    const local_info info = z->get_info(lt);
    // PEP-495 fold=0, which is what `datetime(..., tzinfo=ZoneInfo(tz))` uses:
    // the offset BEFORE the transition, in both the ambiguous and the
    // nonexistent case. The round trip below is what turns "nonexistent" into a
    // drop instead of a silent shift.
    const seconds off = info.first.offset;
    const sys_seconds e{lt.time_since_epoch() - off};
    const local_seconds back = z->to_local(e);
    const seconds tod = back - std::chrono::floor<days>(back);
    const int back_hh = static_cast<int>(tod.count() / 3600);
    const int back_mm = static_cast<int>((tod.count() % 3600) / 60);
    if (back_hh != hh || back_mm != mm) {
      continue;  // a wall time that does not exist on a spring-forward date
    }
    const std::int64_t ep = e.time_since_epoch().count();
    if (ep >= open_utc && ep < open_utc + static_cast<std::int64_t>(n)) {
      out.push_back(static_cast<std::int32_t>(ep - open_utc));
    }
  }
  std::sort(out.begin(), out.end());
  out.erase(std::unique(out.begin(), out.end()), out.end());
  return out;
}

std::int32_t local_date8(std::int64_t epoch, const char* tz) {
  const time_zone* z = zone_or_null(tz);
  if (z == nullptr) {
    return -1;
  }
  const local_seconds lt = z->to_local(sys_seconds{seconds{epoch}});
  const year_month_day ymd{std::chrono::floor<days>(lt)};
  return static_cast<std::int32_t>(int(ymd.year())) * 10000 +
         static_cast<std::int32_t>(unsigned(ymd.month())) * 100 +
         static_cast<std::int32_t>(unsigned(ymd.day()));
}

Expected<std::vector<std::int32_t>, Refusal> fomc_release_dates(const std::string& csv_path) {
  std::ifstream fh(csv_path);
  if (!fh) {
    return refuse<std::vector<std::int32_t>>(
        Refusal(RefusalCode::IO, "qr_gen::fomc_release_dates", "cannot open the FOMC calendar"));
  }
  std::string line;
  if (!std::getline(fh, line)) {
    return refuse<std::vector<std::int32_t>>(Refusal(
        RefusalCode::SCHEMA_MISMATCH, "qr_gen::fomc_release_dates", "FOMC calendar is empty"));
  }
  const std::vector<std::string> header = split(trim(line), ',');
  if (header.empty() || trim(header[0]) != "year") {
    return refuse<std::vector<std::int32_t>>(
        Refusal(RefusalCode::SCHEMA_MISMATCH, "qr_gen::fomc_release_dates",
                "unexpected FOMC calendar header (first column is not 'year')"));
  }
  std::vector<std::int32_t> out;
  while (std::getline(fh, line)) {
    const std::vector<std::string> f = split(trim(line), ',');
    if (f.size() < 3 || !all_digits(trim(f[0]))) {
      continue;
    }
    const int year = std::atoi(trim(f[0]).c_str());
    std::vector<std::string> months;
    for (const std::string& m : split(f[1], '/')) {
      if (!trim(m).empty()) {
        months.push_back(trim(m));
      }
    }
    std::vector<std::string> dd;
    for (const std::string& d : split(f[2], '-')) {
      if (!trim(d).empty()) {
        dd.push_back(trim(d));
      }
    }
    if (months.empty() || dd.empty()) {
      continue;
    }
    const int mon = month_index(months.back());
    if (mon < 0) {
      continue;
    }
    const int day = std::atoi(dd.back().c_str());
    // A "Dec/Jan" style span whose LAST month is January belongs to the next
    // calendar year; every other span stays on the row's own year.
    const int y = (months.size() > 1 && mon == 1) ? year + 1 : year;
    out.push_back(y * 10000 + mon * 100 + day);
  }
  std::sort(out.begin(), out.end());
  out.erase(std::unique(out.begin(), out.end()), out.end());
  return out;
}

}  // namespace qr::gen
