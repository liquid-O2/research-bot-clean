// qr_ivx_volindex — THE VOL-INDEX CONTEXT JOIN (brief item C).
//
// WHAT: the banked FRED daily closes in
// /workspace/artifacts/reference/vol_indices/FRED_{VIXCLS,RVXCLS,VXDCLS}.csv
// folded into a per-session regime-context row: prior-day levels, 5-observation
// changes, and the RVX-VIX spread.
//
// THE ONE LAW THAT MATTERS: STRICTLY PRIOR. A session's row may only cite
// observations whose date is STRICTLY BEFORE that session's own civil day.
// These are daily CLOSES; the close of the session's own day is published after
// the session ends, so joining it would be a straight lookahead leak into every
// model that reads this table. The join therefore takes the LATEST observation
// strictly before the day, and it also emits `*_lag_days` so a consumer can see
// exactly how stale that observation is (1 on a normal weekday, 3 across a
// weekend, more across a holiday) rather than assuming freshness.
//
// FRED writes "." for a non-observation. That is a MISSING VALUE, not a zero
// and not a carry-forward at the parser level: such rows are dropped from the
// observation sequence entirely, so "the latest strictly prior OBSERVATION" is
// exactly what the column name says.
//
// Output is a WIDE tsv — this is a join table for sheets and models, not a
// census report — with `NA` for every absent cell. No wall-clock value is
// written, so two runs are byte-identical.
//
// usage: qr_ivx_volindex --vix CSV --rvx CSV --vxd CSV --out TSV
//                        [--from ORDINAL] [--to ORDINAL]
#include <algorithm>
#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <limits>
#include <fstream>
#include <map>
#include <string>
#include <vector>

#include "qr_ivx/tsv.hpp"
#include "qr_registry/day_scope.hpp"
#include "qr_registry/registry.hpp"

namespace {

int usage() {
  std::fprintf(stderr,
               "usage: qr_ivx_volindex --vix CSV --rvx CSV --vxd CSV --out TSV\n"
               "                       [--from ORDINAL] [--to ORDINAL]\n");
  return 2;
}

/// Days since 1970-01-01 for an ISO `YYYY-MM-DD`, or INT64_MIN when the text is
/// not that shape. Howard Hinnant's days_from_civil, which is exact for every
/// proleptic Gregorian date and needs no library.
std::int64_t days_from_iso(const std::string& iso) {
  if (iso.size() != 10 || iso[4] != '-' || iso[7] != '-') {
    return std::numeric_limits<std::int64_t>::min();
  }
  for (const std::size_t at : {0U, 1U, 2U, 3U, 5U, 6U, 8U, 9U}) {
    if (iso[at] < '0' || iso[at] > '9') return std::numeric_limits<std::int64_t>::min();
  }
  std::int64_t year = std::strtoll(iso.substr(0, 4).c_str(), nullptr, 10);
  const std::int64_t month = std::strtoll(iso.substr(5, 2).c_str(), nullptr, 10);
  const std::int64_t day = std::strtoll(iso.substr(8, 2).c_str(), nullptr, 10);
  if (month < 1 || month > 12 || day < 1 || day > 31) {
    return std::numeric_limits<std::int64_t>::min();
  }
  year -= month <= 2 ? 1 : 0;
  const std::int64_t era = (year >= 0 ? year : year - 399) / 400;
  const auto year_of_era = static_cast<std::uint64_t>(year - era * 400);
  const auto day_of_year =
      static_cast<std::uint64_t>((153 * (month + (month > 2 ? -3 : 9)) + 2) / 5 + day - 1);
  const std::uint64_t day_of_era =
      year_of_era * 365 + year_of_era / 4 - year_of_era / 100 + day_of_year;
  return era * 146097 + static_cast<std::int64_t>(day_of_era) - 719468;
}

struct Observation {
  std::string date;
  std::int64_t epoch_day = 0;
  double value = 0.0;
};

/// One FRED series: `observation_date,<SERIES>` with "." for a missing value.
/// Rows are kept in file order and the file is required to be ascending by
/// date — a series that is not sorted would break the "latest strictly prior"
/// search, so the loader REFUSES rather than sorting behind the caller's back.
bool load_series(const std::string& path, std::vector<Observation>& out) {
  std::ifstream input(path);
  if (!input) {
    std::fprintf(stderr, "cannot read %s\n", path.c_str());
    return false;
  }
  std::string line;
  bool first = true;
  while (std::getline(input, line)) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    if (line.empty()) continue;
    if (first) {
      first = false;
      if (line.rfind("observation_date,", 0) == 0) continue;  // the header
    }
    const std::size_t comma = line.find(',');
    if (comma == std::string::npos) continue;
    const std::string date = line.substr(0, comma);
    const std::string text = line.substr(comma + 1);
    const std::int64_t epoch_day = days_from_iso(date);
    if (epoch_day == std::numeric_limits<std::int64_t>::min()) continue;
    if (text.empty() || text == ".") continue;  // FRED's own missing marker
    char* end = nullptr;
    const double value = std::strtod(text.c_str(), &end);
    if (end == text.c_str() || !std::isfinite(value)) continue;
    if (!out.empty() && epoch_day <= out.back().epoch_day) {
      std::fprintf(stderr, "REFUSED: %s is not strictly ascending at %s\n", path.c_str(),
                   date.c_str());
      return false;
    }
    out.push_back(Observation{date, epoch_day, value});
  }
  return !out.empty();
}

/// Index of the LATEST observation STRICTLY BEFORE `epoch_day`, or -1.
std::int64_t latest_strictly_prior(const std::vector<Observation>& series,
                                   std::int64_t epoch_day) {
  // The series is ascending, so the first element NOT before `epoch_day` bounds
  // the answer; stepping back one gives the latest that is.
  std::int64_t low = 0;
  auto high = static_cast<std::int64_t>(series.size());
  while (low < high) {
    const std::int64_t middle = low + (high - low) / 2;
    if (series[static_cast<std::size_t>(middle)].epoch_day < epoch_day) {
      low = middle + 1;
    } else {
      high = middle;
    }
  }
  return low - 1;
}

struct Cell {
  bool present = false;
  std::string date;
  double level = 0.0;
  bool has_change = false;
  double change_5 = 0.0;
  std::int64_t lag_days = 0;
};

/// The 5-OBSERVATION change: level(prior) - level(prior minus five OBSERVATIONS).
/// Observations, not calendar days, because the index only prints on trading
/// days and a calendar offset would silently compare a Monday with a holiday.
Cell fold(const std::vector<Observation>& series, std::int64_t epoch_day) {
  Cell out;
  const std::int64_t at = latest_strictly_prior(series, epoch_day);
  if (at < 0) return out;
  const Observation& prior = series[static_cast<std::size_t>(at)];
  out.present = true;
  out.date = prior.date;
  out.level = prior.value;
  out.lag_days = epoch_day - prior.epoch_day;
  if (at >= 5) {
    out.has_change = true;
    out.change_5 = prior.value - series[static_cast<std::size_t>(at - 5)].value;
  }
  return out;
}

void put(std::FILE* out, const Cell& cell) {
  if (!cell.present) {
    std::fputs("\tNA\tNA\tNA\tNA", out);
    return;
  }
  std::fprintf(out, "\t%s\t%s", cell.date.c_str(), qr::ivx::g17(cell.level).c_str());
  if (cell.has_change) {
    std::fprintf(out, "\t%s", qr::ivx::g17(cell.change_5).c_str());
  } else {
    std::fputs("\tNA", out);
  }
  std::fprintf(out, "\t%" PRId64, cell.lag_days);
}

}  // namespace

int main(int argc, char** argv) {
  std::string vix_path;
  std::string rvx_path;
  std::string vxd_path;
  std::string out_path;
  std::int64_t from = qr::kScopeFirstOrdinal;
  std::int64_t to = qr::kScopeLastOrdinal;
  for (int index = 1; index < argc; ++index) {
    const std::string flag = argv[index];
    if (index + 1 >= argc) return usage();
    const std::string value = argv[++index];
    if (flag == "--vix") {
      vix_path = value;
    } else if (flag == "--rvx") {
      rvx_path = value;
    } else if (flag == "--vxd") {
      vxd_path = value;
    } else if (flag == "--out") {
      out_path = value;
    } else if (flag == "--from") {
      from = std::strtoll(value.c_str(), nullptr, 10);
    } else if (flag == "--to") {
      to = std::strtoll(value.c_str(), nullptr, 10);
    } else {
      return usage();
    }
  }
  if (vix_path.empty() || rvx_path.empty() || vxd_path.empty() || out_path.empty()) {
    return usage();
  }
  if (from < qr::kScopeFirstOrdinal || to > qr::kScopeLastOrdinal || from > to) {
    std::fprintf(stderr, "the ordinal range must lie inside the scope wall [%lld,%lld]\n",
                 static_cast<long long>(qr::kScopeFirstOrdinal),
                 static_cast<long long>(qr::kScopeLastOrdinal));
    return 1;
  }

  std::vector<Observation> vix;
  std::vector<Observation> rvx;
  std::vector<Observation> vxd;
  if (!load_series(vix_path, vix) || !load_series(rvx_path, rvx) || !load_series(vxd_path, vxd)) {
    return 1;
  }

  auto registry = qr::Registry::load_embedded();
  if (!registry.has_value()) {
    std::fprintf(stderr, "the embedded registry refused to load\n");
    return 1;
  }

  std::FILE* out = std::fopen(out_path.c_str(), "wb");
  if (out == nullptr) {
    std::fprintf(stderr, "cannot write %s\n", out_path.c_str());
    return 1;
  }
  std::fputs(
      "ordinal\tday"
      "\tvix_prior_date\tvix_prior\tvix_change_5obs\tvix_lag_days"
      "\trvx_prior_date\trvx_prior\trvx_change_5obs\trvx_lag_days"
      "\tvxd_prior_date\tvxd_prior\tvxd_change_5obs\tvxd_lag_days"
      "\trvx_minus_vix\trvx_over_vix\n",
      out);

  std::int64_t rows = 0;
  for (std::int64_t ordinal = from; ordinal <= to; ++ordinal) {
    const auto scope = qr::DayScope::admit(registry.value(), ordinal);
    if (!scope.has_value()) {
      std::fprintf(stderr, "REFUSED: %s\n", scope.error().message().c_str());
      std::fclose(out);
      return 1;
    }
    const std::int64_t epoch_day = days_from_iso(scope.value().day());
    if (epoch_day == std::numeric_limits<std::int64_t>::min()) {
      std::fprintf(stderr, "REFUSED: session %lld carries a non-ISO day\n",
                   static_cast<long long>(ordinal));
      std::fclose(out);
      return 1;
    }
    const Cell vix_cell = fold(vix, epoch_day);
    const Cell rvx_cell = fold(rvx, epoch_day);
    const Cell vxd_cell = fold(vxd, epoch_day);

    std::fprintf(out, "%" PRId64 "\t%s", ordinal, scope.value().day().c_str());
    put(out, vix_cell);
    put(out, rvx_cell);
    put(out, vxd_cell);
    if (vix_cell.present && rvx_cell.present) {
      std::fprintf(out, "\t%s", qr::ivx::g17(rvx_cell.level - vix_cell.level).c_str());
      if (vix_cell.level > 0.0) {
        std::fprintf(out, "\t%s", qr::ivx::g17(rvx_cell.level / vix_cell.level).c_str());
      } else {
        std::fputs("\tNA", out);
      }
    } else {
      std::fputs("\tNA\tNA", out);
    }
    std::fputc('\n', out);
    ++rows;
  }
  if (std::fclose(out) != 0) {
    std::fprintf(stderr, "the join table did not close cleanly\n");
    return 1;
  }
  std::fprintf(stderr, "wrote %lld rows to %s\n", static_cast<long long>(rows), out_path.c_str());
  return 0;
}
