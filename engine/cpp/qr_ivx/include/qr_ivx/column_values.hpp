// qr_ivx/column_values.hpp — the CC-013 VALUE census, through the reader.
//
// The census that AUTHORIZED CC-013 (column_census.hpp) could only read the
// parquet footer, because the columns were still walled: it proved they are
// populated and could say nothing about what is in them. Now that the
// amendment has landed and `qr::sources::OptionPrintReader` projects all
// eleven, this is the other half of the receipt — the distribution of the
// DECODED values, on the same five sessions, so the amendment's claim ("REAL,
// sane ranges") is checked against the values and not only against the
// writer's own min/max.
//
// EXACTNESS. Values are RETAINED and the statistics are computed in two passes
// over the retained vector, so the mean, the population standard deviation and
// every quantile are exact for the session rather than streaming
// approximations. A session is ~47k admitted rows x 11 columns x 8 bytes, which
// is a few megabytes.
//
// NON-FINITE IS COUNTED, NEVER MIXED IN. A NaN or an infinity is excluded from
// every statistic and reported as its own count, because one infinity would
// otherwise swallow the mean, the range and every quantile of the column.
#ifndef QR_IVX_COLUMN_VALUES_HPP
#define QR_IVX_COLUMN_VALUES_HPP

#include <array>
#include <cstdint>
#include <string>
#include <vector>

#include "qr_ivx/tsv.hpp"
#include "qr_sources/option_prints.hpp"

namespace qr::ivx {

/// The eleven columns CC-013 admitted, plus the four reference columns that
/// were already projected — a distribution nobody can read without something
/// to read it AGAINST.
inline constexpr std::array<const char*, 15> kValueCensusColumns{
    "delta",  "gamma",      "vanna",      "charm",      "implied_vol",
    "vega",   "vomma",      "veta",       "vera",       "speed",
    "zomma",  "color",      "ultima",     "dual_delta", "iv_error"};
/// `dual_gamma` is censused too; it is listed apart only because the array
/// above is sized by the pairs the emitter walks. (Kept explicit rather than
/// clever: the emitter iterates `kValueCensusColumns` and then this one.)
inline constexpr const char* kValueCensusExtraColumn = "dual_gamma";

/// One column's exact distribution over one session's ADMITTED rows.
struct ValueDistribution {
  std::string name;
  std::int64_t rows = 0;
  std::int64_t nulls = 0;
  std::int64_t nonfinite = 0;
  std::int64_t finite = 0;
  double minimum = 0.0;
  double maximum = 0.0;
  double mean = 0.0;
  double stdev = 0.0;
  /// p01, p10, p50, p90, p99 of the finite values.
  std::array<double, 5> quantile{};
};

/// Accumulates one session, one column at a time.
class Cc013ValueCensus {
 public:
  Cc013ValueCensus();
  /// Folds one decoded print. Rows are folded whole, so every column's row
  /// count is the same number and the null counts are comparable.
  void observe(const qr::sources::OptionPrintRow& row);
  [[nodiscard]] std::vector<ValueDistribution> finish() const;
  [[nodiscard]] std::int64_t rows() const noexcept { return rows_; }

 private:
  std::vector<std::string> names_;
  std::vector<std::size_t> slots_;
  std::vector<std::vector<double>> values_;  // finite values only
  std::vector<std::int64_t> nulls_;
  std::vector<std::int64_t> nonfinite_;
  std::int64_t rows_ = 0;
};

void emit(Report& report, const std::string& key, const std::vector<ValueDistribution>& columns);

}  // namespace qr::ivx

#endif  // QR_IVX_COLUMN_VALUES_HPP
