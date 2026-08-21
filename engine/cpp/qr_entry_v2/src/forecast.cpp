#include "qr_entry_v2/forecast.hpp"

#include <openssl/evp.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <iomanip>
#include <limits>
#include <map>
#include <numbers>
#include <set>
#include <sstream>
#include <string_view>
#include <tuple>
#include <utility>

#include "qr_futsess/calendar.hpp"

namespace qr::entry_v2 {
namespace {

constexpr std::uint64_t kNsPerSecond = 1'000'000'000ULL;
constexpr long double kRawPriceScale = 1.0e-9L;
constexpr std::array<std::int64_t, 3> kEntryAssetMultipliers = {
    5'000, 25'000, 5};

[[nodiscard]] std::int64_t entry_asset_multiplier(
    qr::futsess::Asset asset) noexcept {
  return kEntryAssetMultipliers[static_cast<std::size_t>(asset)];
}

constexpr std::string_view kForecastLaw =
    "QRE2FORECAST4|clock=IndexTs/ts_recv; ts_event feature only; equal receive "
    "times retain provider order|book=QRE2EVT2 trusted-economic rows only; "
    "snapshot atomically discards all pre-reset current-session extrema/returns/"
    "OHLC/spread aggregates; unresolved MAYBE_BAD_BOOK invalidates the session until "
    "snapshot|sane=event-grain D-054 trailing60 same-phase pooled spread "
    "median cap min(10x,$500), snapshot-before-commit|realized=SESSION,TOKYO,"
    "LONDON,NY sane mids; previous-tick 300-second dollar returns; RV=sum(r^2); "
    "BV=pi/2 sum(|r_i||r_i-1|); jump=max(RV-BV,0); Parkinson/GK/RS dollarized "
    "OHLC|design=[const,log RV1,log RV5,log RV22,log prior SESSION Parkinson,"
    "log prior SESSION GK,log prior SESSION RS,log1p prior segment jump,Tue..Fri "
    "dummies]; exact complete positive lag windows, no imputation, "
    "no context|fit=expanding monthly OLS(log RANGE), OLS(log SIGMA), rank-full, "
    "MIN_TRAIN=250, no substitution|sigma_point=raw log-OLS multiplied by "
    "strictly-prior trailing66 median(realized_sigma/raw_sigma), min20 else "
    "ratio1; exact-sidecar convex weight selection chose 1.0 calibrated OLS + "
    "0.0 prior-session sigma through 2023 and passed every asset/segment in "
    "2024 and 2025H1 under receipt ef424de36c20ef2eca61f6b70513c18df8aa1c2ca1"
    "0647a6f114581b914edf5c|"
    "ladder=realized_range/sigma_hat trailing250 "
    "strictly prior linear quantiles q10,25,50,75,90 min30|regime=RV5/RV66 "
    "complete positive prior windows; trailing250 prior ratio terciles min30; "
    "same-regime calibration min30 else explicit unscaled fallback|availability="
    "session_open_ts_recv_ns and join requires availability<decision|window=[20210101,"
    "20250701)";

[[nodiscard]] Refusal forecast_content(const char* site, const char* detail,
                                       std::int64_t context = 0) {
  return Refusal(RefusalCode::CONTENT_MISMATCH, site, detail, context);
}

[[nodiscard]] Refusal forecast_clock(const char* site, const char* detail,
                                     std::int64_t context = 0) {
  return Refusal(RefusalCode::CLOCK_VIOLATION, site, detail, context);
}

[[nodiscard]] bool valid_sha256(std::string_view value) {
  return value.size() == 64u &&
         std::all_of(value.begin(), value.end(), [](char ch) {
           return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
         });
}

[[nodiscard]] std::string hex_digest(const unsigned char* digest,
                                     unsigned int length) {
  static constexpr char kHex[] = "0123456789abcdef";
  std::string out(static_cast<std::size_t>(length) * 2u, '0');
  for (unsigned int i = 0; i < length; ++i) {
    const std::size_t j = static_cast<std::size_t>(i) * 2u;
    out[j] = kHex[digest[i] >> 4u];
    out[j + 1u] = kHex[digest[i] & 0x0Fu];
  }
  return out;
}

[[nodiscard]] std::string sha256_bytes(std::string_view bytes) {
  std::array<unsigned char, EVP_MAX_MD_SIZE> digest{};
  unsigned int length = 0;
  if (EVP_Digest(bytes.data(), bytes.size(), digest.data(), &length,
                 EVP_sha256(), nullptr) != 1 || length != 32u) {
    return {};
  }
  return hex_digest(digest.data(), length);
}

[[nodiscard]] double missing_double() {
  return std::numeric_limits<double>::quiet_NaN();
}

void initialize_missing(ForecastRow* row) {
  row->rv1_usd = missing_double();
  row->rv5_usd = missing_double();
  row->rv22_usd = missing_double();
  row->prior_parkinson_usd = missing_double();
  row->prior_gk_usd = missing_double();
  row->prior_rs_usd = missing_double();
  row->prior_jump_usd = missing_double();
  row->sigma_raw_hat_usd = missing_double();
  row->sigma_persistence_usd = missing_double();
  row->sigma_calibration_ratio = missing_double();
  row->sigma_hat_usd = missing_double();
  row->range_hat_usd = missing_double();
  row->rv5_over_rv66 = missing_double();
  row->regime_cut_lo = missing_double();
  row->regime_cut_hi = missing_double();
  row->move_ratio.fill(missing_double());
  row->move_usd.fill(missing_double());
  row->regime_move_ratio.fill(missing_double());
  row->regime_move_usd.fill(missing_double());
}

void initialize_missing(RealizedVolSegment* row) {
  row->open_px = missing_double();
  row->high_px = missing_double();
  row->low_px = missing_double();
  row->close_px = missing_double();
  row->range_usd = missing_double();
  row->rv_usd = missing_double();
  row->bv_usd = missing_double();
  row->jump_usd = missing_double();
  row->sigma_usd = missing_double();
  row->parkinson_usd = missing_double();
  row->gk_usd = missing_double();
  row->rs_usd = missing_double();
}

[[nodiscard]] std::size_t segment_index(ForecastSegment segment) {
  return static_cast<std::size_t>(segment);
}

[[nodiscard]] ForecastSegment phase_segment(std::uint8_t phase) {
  return static_cast<ForecastSegment>(static_cast<std::uint8_t>(phase + 1u));
}

struct MidObservation {
  std::uint64_t ts_recv_ns = 0;
  std::int32_t receive_session_sec = 0;
  std::uint64_t book_generation = 0;
  std::int64_t mid2 = 0;
};

[[nodiscard]] RealizedVolSegment realize_segment(
    qr::futsess::Asset asset, ForecastSegment segment,
    const std::vector<MidObservation>& observations) {
  RealizedVolSegment out;
  out.segment = segment;
  initialize_missing(&out);
  out.sane_events = observations.size();
  if (observations.size() < 2u) return out;

  std::int64_t high_mid2 = observations.front().mid2;
  std::int64_t low_mid2 = observations.front().mid2;
  for (const MidObservation& observation : observations) {
    high_mid2 = std::max(high_mid2, observation.mid2);
    low_mid2 = std::min(low_mid2, observation.mid2);
  }
  const long double open_px = static_cast<long double>(observations.front().mid2) *
                              0.5L * kRawPriceScale;
  const long double high_px = static_cast<long double>(high_mid2) *
                              0.5L * kRawPriceScale;
  const long double low_px = static_cast<long double>(low_mid2) *
                             0.5L * kRawPriceScale;
  const long double close_px = static_cast<long double>(observations.back().mid2) *
                               0.5L * kRawPriceScale;
  const long double mult =
      static_cast<long double>(entry_asset_multiplier(asset));
  out.open_px = static_cast<double>(open_px);
  out.high_px = static_cast<double>(high_px);
  out.low_px = static_cast<double>(low_px);
  out.close_px = static_cast<double>(close_px);
  out.range_usd = static_cast<double>((high_px - low_px) * mult);

  long double rv = 0.0L;
  long double bv_unscaled = 0.0L;
  std::uint64_t return_count = 0;
  std::size_t begin = 0;
  while (begin < observations.size()) {
    std::size_t end = begin + 1u;
    while (end < observations.size() &&
           observations[end].book_generation ==
               observations[begin].book_generation) {
      ++end;
    }
    std::vector<std::int64_t> sampled_mid2;
    std::size_t cursor = begin;
    const std::int64_t first = observations[begin].receive_session_sec;
    const std::int64_t last = observations[end - 1u].receive_session_sec;
    for (std::int64_t grid = first; grid <= last;) {
      while (cursor + 1u < end &&
             observations[cursor + 1u].receive_session_sec <= grid) {
        ++cursor;
      }
      sampled_mid2.push_back(observations[cursor].mid2);
      if (grid > std::numeric_limits<std::int64_t>::max() -
                     kForecastSubsampleSec) {
        break;
      }
      grid += kForecastSubsampleSec;
    }
    out.grid_samples += sampled_mid2.size();
    std::vector<long double> returns;
    returns.reserve(sampled_mid2.size() > 0u ? sampled_mid2.size() - 1u : 0u);
    for (std::size_t i = 1; i < sampled_mid2.size(); ++i) {
      const long double change =
          (static_cast<long double>(sampled_mid2[i]) -
           static_cast<long double>(sampled_mid2[i - 1u])) *
          0.5L * kRawPriceScale * mult;
      returns.push_back(change);
      rv += change * change;
      ++return_count;
    }
    for (std::size_t i = 1; i < returns.size(); ++i) {
      bv_unscaled += std::fabs(returns[i]) * std::fabs(returns[i - 1u]);
    }
    begin = end;
  }
  if (return_count > 0u) {
    const long double bv =
        bv_unscaled * std::numbers::pi_v<long double> / 2.0L;
    out.rv_usd = static_cast<double>(rv);
    out.bv_usd = static_cast<double>(bv);
    out.jump_usd = static_cast<double>(std::max(rv - bv, 0.0L));
    out.sigma_usd = static_cast<double>(std::sqrt(rv));
  }

  const long double scale = close_px * mult;
  if (open_px > 0.0L && high_px > 0.0L && low_px > 0.0L && close_px > 0.0L) {
    const long double hl = std::log(high_px / low_px);
    const long double co = std::log(close_px / open_px);
    const long double hc = std::log(high_px / close_px);
    const long double ho = std::log(high_px / open_px);
    const long double lc = std::log(low_px / close_px);
    const long double lo = std::log(low_px / open_px);
    out.parkinson_usd = static_cast<double>(
        std::sqrt(hl * hl / (4.0L * std::log(2.0L))) * scale);
    const long double gk = 0.5L * hl * hl -
                           (2.0L * std::log(2.0L) - 1.0L) * co * co;
    out.gk_usd = static_cast<double>(std::sqrt(std::max(gk, 0.0L)) * scale);
    const long double rs = hc * ho + lc * lo;
    out.rs_usd = static_cast<double>(std::sqrt(std::max(rs, 0.0L)) * scale);
  }
  out.valid = std::isfinite(out.range_usd) && out.range_usd > 0.0 &&
              std::isfinite(out.parkinson_usd) &&
              std::isfinite(out.gk_usd) && std::isfinite(out.rs_usd);
  return out;
}

[[nodiscard]] double percentile(std::vector<double> values, double q) {
  values.erase(std::remove_if(values.begin(), values.end(), [](double value) {
                 return !std::isfinite(value);
               }), values.end());
  if (values.empty() || !(q >= 0.0 && q <= 1.0)) return missing_double();
  std::sort(values.begin(), values.end());
  const long double position = static_cast<long double>(q) *
                               static_cast<long double>(values.size() - 1u);
  const std::size_t lo = static_cast<std::size_t>(std::floor(position));
  const std::size_t hi = static_cast<std::size_t>(std::ceil(position));
  const long double fraction = position - static_cast<long double>(lo);
  return static_cast<double>(static_cast<long double>(values[lo]) +
                             fraction * (static_cast<long double>(values[hi]) -
                                         static_cast<long double>(values[lo])));
}

[[nodiscard]] std::int32_t weekday_monday_zero(std::int32_t d8) {
  const std::int64_t day = qr::futsess::date_to_day(
      qr::futsess::date_from_yyyymmdd(d8));
  const std::int64_t value = (day + 3) % 7;  // 1970-01-01 was Thursday (3).
  return static_cast<std::int32_t>(value < 0 ? value + 7 : value);
}

struct Design {
  bool valid = false;
  std::array<double, kForecastFeatureCount> x{};
  double rv1 = missing_double();
  double rv5 = missing_double();
  double rv22 = missing_double();
  double parkinson = missing_double();
  double gk = missing_double();
  double rs = missing_double();
  double jump = missing_double();
};

struct Observation {
  std::int32_t d8 = 0;
  RealizedVolSegment realized{};
  double session_parkinson = missing_double();
  double session_gk = missing_double();
  double session_rs = missing_double();
  double forecast_ratio = missing_double();
  double sigma_forecast_ratio = missing_double();
  double regime_ratio = missing_double();
  ForecastRegime regime = ForecastRegime::NA;
};

struct Example {
  std::int32_t d8 = 0;
  std::array<double, kForecastFeatureCount> x{};
  double log_range = missing_double();
  double log_sigma = missing_double();
};

struct SegmentState {
  std::vector<Observation> history;
  std::vector<Example> examples;
};

[[nodiscard]] Design make_design(const SegmentState& state, std::int32_t d8) {
  Design out;
  const auto& history = state.history;
  if (history.size() < 22u) return out;
  const std::size_t n = history.size();
  long double sum5 = 0.0L;
  long double sum22 = 0.0L;
  for (std::size_t i = n - 22u; i < n; ++i) {
    const double rv = history[i].realized.rv_usd;
    if (!std::isfinite(rv) || !(rv > 0.0)) return out;
    sum22 += static_cast<long double>(rv);
    if (i >= n - 5u) sum5 += static_cast<long double>(rv);
  }
  const Observation& prior = history.back();
  if (!std::isfinite(prior.session_parkinson) || !(prior.session_parkinson > 0.0) ||
      !std::isfinite(prior.session_gk) || !(prior.session_gk > 0.0) ||
      !std::isfinite(prior.session_rs) || !(prior.session_rs > 0.0) ||
      !std::isfinite(prior.realized.jump_usd) || prior.realized.jump_usd < 0.0) {
    return out;
  }
  out.rv1 = prior.realized.rv_usd;
  out.rv5 = static_cast<double>(sum5 / 5.0L);
  out.rv22 = static_cast<double>(sum22 / 22.0L);
  out.parkinson = prior.session_parkinson;
  out.gk = prior.session_gk;
  out.rs = prior.session_rs;
  out.jump = prior.realized.jump_usd;
  out.x = {1.0, std::log(out.rv1), std::log(out.rv5), std::log(out.rv22),
           std::log(out.parkinson), std::log(out.gk), std::log(out.rs),
           std::log1p(out.jump), 0.0, 0.0, 0.0, 0.0};
  const std::int32_t weekday = weekday_monday_zero(d8);
  for (std::int32_t k = 1; k <= 4; ++k) {
    out.x[static_cast<std::size_t>(7 + k)] = weekday == k ? 1.0 : 0.0;
  }
  out.valid = std::all_of(out.x.begin(), out.x.end(), [](double value) {
    return std::isfinite(value);
  });
  return out;
}

struct Fit {
  std::uint32_t n_train = 0;
  std::uint32_t rank = 0;
  std::int32_t fit_end_d8 = -1;
  bool ready = false;
  std::array<double, kForecastFeatureCount> beta{};
};

// Deterministic long-double modified Gram-Schmidt with column pivoting.  The
// rank threshold is the standard dimension-scaled double epsilon, not a tuned
// hyperparameter. p is fixed at 12 and n is at most the development history.
[[nodiscard]] Fit fit_ols(const std::vector<Example>& examples,
                          std::int32_t month, bool range_target) {
  std::vector<const Example*> selected;
  for (const Example& example : examples) {
    const double target = range_target ? example.log_range : example.log_sigma;
    if (example.d8 / 100 < month && std::isfinite(target)) {
      selected.push_back(&example);
    }
  }
  Fit out;
  out.n_train = static_cast<std::uint32_t>(selected.size());
  if (!selected.empty()) out.fit_end_d8 = selected.back()->d8;
  const std::size_t n = selected.size();
  constexpr std::size_t p = kForecastFeatureCount;
  if (n < p) return out;

  std::array<std::vector<long double>, p> columns;
  std::vector<long double> y(n);
  for (std::size_t j = 0; j < p; ++j) columns[j].resize(n);
  for (std::size_t i = 0; i < n; ++i) {
    for (std::size_t j = 0; j < p; ++j) {
      columns[j][i] = static_cast<long double>(selected[i]->x[j]);
    }
    y[i] = static_cast<long double>(range_target ? selected[i]->log_range
                                                  : selected[i]->log_sigma);
  }
  std::array<std::size_t, p> permutation{};
  std::array<std::array<long double, p>, p> upper{};
  std::array<long double, p> qty{};
  std::array<long double, p> norm2{};
  long double initial_max_norm = 0.0L;
  for (std::size_t j = 0; j < p; ++j) {
    permutation[j] = j;
    for (long double value : columns[j]) norm2[j] += value * value;
    initial_max_norm = std::max(initial_max_norm, std::sqrt(norm2[j]));
  }
  const long double tolerance =
      static_cast<long double>(std::max(n, p)) *
      static_cast<long double>(std::numeric_limits<double>::epsilon()) *
      initial_max_norm;
  for (std::size_t k = 0; k < p; ++k) {
    std::size_t pivot = k;
    for (std::size_t j = k + 1u; j < p; ++j) {
      if (norm2[j] > norm2[pivot]) pivot = j;
    }
    if (pivot != k) {
      std::swap(columns[k], columns[pivot]);
      std::swap(norm2[k], norm2[pivot]);
      std::swap(permutation[k], permutation[pivot]);
      for (std::size_t i = 0; i < k; ++i) {
        std::swap(upper[i][k], upper[i][pivot]);
      }
    }
    long double norm = 0.0L;
    for (long double value : columns[k]) norm += value * value;
    norm = std::sqrt(norm);
    if (!(norm > tolerance)) break;
    ++out.rank;
    upper[k][k] = norm;
    for (long double& value : columns[k]) value /= norm;
    for (std::size_t i = 0; i < n; ++i) qty[k] += columns[k][i] * y[i];
    for (std::size_t j = k + 1u; j < p; ++j) {
      long double projection = 0.0L;
      for (std::size_t i = 0; i < n; ++i) {
        projection += columns[k][i] * columns[j][i];
      }
      upper[k][j] = projection;
      for (std::size_t i = 0; i < n; ++i) {
        columns[j][i] -= projection * columns[k][i];
      }
      // One deterministic re-orthogonalization pass controls MGS drift.
      long double correction = 0.0L;
      for (std::size_t i = 0; i < n; ++i) {
        correction += columns[k][i] * columns[j][i];
      }
      upper[k][j] += correction;
      for (std::size_t i = 0; i < n; ++i) {
        columns[j][i] -= correction * columns[k][i];
      }
      norm2[j] = 0.0L;
      for (long double value : columns[j]) norm2[j] += value * value;
    }
  }
  if (out.rank != p || out.n_train < kForecastMinTrain) return out;
  std::array<long double, p> permuted_beta{};
  for (std::size_t reverse = 0; reverse < p; ++reverse) {
    const std::size_t i = p - 1u - reverse;
    long double rhs = qty[i];
    for (std::size_t j = i + 1u; j < p; ++j) {
      rhs -= upper[i][j] * permuted_beta[j];
    }
    permuted_beta[i] = rhs / upper[i][i];
  }
  for (std::size_t j = 0; j < p; ++j) {
    out.beta[permutation[j]] = static_cast<double>(permuted_beta[j]);
  }
  out.ready = std::all_of(out.beta.begin(), out.beta.end(), [](double value) {
    return std::isfinite(value);
  });
  return out;
}

[[nodiscard]] double predict(const Fit& fit, const Design& design) {
  if (!fit.ready || !design.valid) return missing_double();
  long double value = 0.0L;
  for (std::size_t i = 0; i < kForecastFeatureCount; ++i) {
    value += static_cast<long double>(fit.beta[i]) *
             static_cast<long double>(design.x[i]);
  }
  const long double prediction = std::exp(value);
  if (!(prediction > 0.0L) ||
      prediction > static_cast<long double>(std::numeric_limits<double>::max())) {
    return missing_double();
  }
  return static_cast<double>(prediction);
}

[[nodiscard]] std::string model_hash(std::int32_t month,
                                     ForecastSegment segment,
                                     const Fit& range, const Fit& sigma) {
  std::ostringstream out;
  out << std::setprecision(std::numeric_limits<double>::max_digits10)
      << "QRE2FORECASTMODEL2|" << forecast_law_sha256() << '|' << month << '|'
      << forecast_segment_name(segment) << '|' << range.n_train << '|'
      << range.rank << '|' << range.fit_end_d8 << '|' << range.ready << '|'
      << sigma.n_train << '|' << sigma.rank << '|' << sigma.fit_end_d8 << '|'
      << sigma.ready;
  for (double value : range.beta) out << '|' << value;
  for (double value : sigma.beta) out << '|' << value;
  return sha256_bytes(out.str());
}

[[nodiscard]] double exact_regime_ratio(const SegmentState& state) {
  const auto& history = state.history;
  if (history.size() < kForecastRegimeLong) return missing_double();
  const std::size_t n = history.size();
  long double sum5 = 0.0L;
  long double sum66 = 0.0L;
  for (std::size_t i = n - kForecastRegimeLong; i < n; ++i) {
    const double rv = history[i].realized.rv_usd;
    if (!std::isfinite(rv) || !(rv > 0.0)) return missing_double();
    sum66 += static_cast<long double>(rv);
    if (i >= n - 5u) sum5 += static_cast<long double>(rv);
  }
  const long double mean5 = sum5 / 5.0L;
  const long double mean66 = sum66 / static_cast<long double>(kForecastRegimeLong);
  return mean66 > 0.0L ? static_cast<double>(mean5 / mean66) : missing_double();
}

[[nodiscard]] std::vector<double> trailing_values(
    const SegmentState& state, bool regime_ratios) {
  std::vector<double> out;
  const std::size_t begin = state.history.size() > kForecastCalibrationWindow
                                ? state.history.size() - kForecastCalibrationWindow
                                : 0u;
  for (std::size_t i = begin; i < state.history.size(); ++i) {
    const double value = regime_ratios ? state.history[i].regime_ratio
                                       : state.history[i].forecast_ratio;
    if (std::isfinite(value)) out.push_back(value);
  }
  return out;
}

[[nodiscard]] std::vector<double> trailing_sigma_calibration(
    const SegmentState& state) {
  std::vector<double> out;
  const std::size_t begin =
      state.history.size() > kForecastSigmaCalibrationWindow
          ? state.history.size() - kForecastSigmaCalibrationWindow
          : 0u;
  for (std::size_t i = begin; i < state.history.size(); ++i) {
    const double value = state.history[i].sigma_forecast_ratio;
    if (std::isfinite(value) && value > 0.0) out.push_back(value);
  }
  return out;
}

[[nodiscard]] ForecastRegime regime_of(double ratio, double low, double high) {
  if (!std::isfinite(ratio) || !std::isfinite(low) || !std::isfinite(high)) {
    return ForecastRegime::NA;
  }
  if (ratio < low) return ForecastRegime::LOW;
  if (ratio < high) return ForecastRegime::MID;
  return ForecastRegime::HIGH;
}

}  // namespace

const char* forecast_segment_name(ForecastSegment segment) noexcept {
  switch (segment) {
    case ForecastSegment::SESSION: return "SESSION";
    case ForecastSegment::TOKYO: return "TOKYO";
    case ForecastSegment::LONDON: return "LONDON";
    case ForecastSegment::NY: return "NY";
  }
  return "UNKNOWN";
}

Expected<ForecastSegment, Refusal> forecast_segment_from_name(
    const std::string& name) {
  if (name == "SESSION") return ForecastSegment::SESSION;
  if (name == "TOKYO") return ForecastSegment::TOKYO;
  if (name == "LONDON") return ForecastSegment::LONDON;
  if (name == "NY") return ForecastSegment::NY;
  return refuse<ForecastSegment>(Refusal(
      RefusalCode::CONFIG, "qr_entry_v2::forecast_segment_from_name",
      "unknown QRE2FORECAST4 segment"));
}

const char* forecast_status_name(ForecastStatus status) noexcept {
  switch (status) {
    case ForecastStatus::READY: return "READY";
    case ForecastStatus::MISSING: return "MISSING";
  }
  return "UNKNOWN";
}

const char* forecast_missing_reason_name(ForecastMissingReason reason) noexcept {
  switch (reason) {
    case ForecastMissingReason::NONE: return "NONE";
    case ForecastMissingReason::DESIGN_HISTORY: return "DESIGN_HISTORY";
    case ForecastMissingReason::MIN_TRAIN: return "MIN_TRAIN";
    case ForecastMissingReason::RANK_DEFICIENT: return "RANK_DEFICIENT";
    case ForecastMissingReason::NONFINITE_PREDICTION: return "NONFINITE_PREDICTION";
  }
  return "UNKNOWN";
}

const char* forecast_regime_name(ForecastRegime regime) noexcept {
  switch (regime) {
    case ForecastRegime::NA: return "NA";
    case ForecastRegime::LOW: return "LOW";
    case ForecastRegime::MID: return "MID";
    case ForecastRegime::HIGH: return "HIGH";
  }
  return "UNKNOWN";
}

const char* forecast_ladder_source_name(ForecastLadderSource source) noexcept {
  switch (source) {
    case ForecastLadderSource::MISSING: return "MISSING";
    case ForecastLadderSource::REGIME: return "REGIME";
    case ForecastLadderSource::UNSCALED_FALLBACK: return "UNSCALED_FALLBACK";
  }
  return "UNKNOWN";
}

std::string forecast_law_sha256() { return sha256_bytes(kForecastLaw); }

std::string forecast_row_lineage(const ForecastRow& row) {
  std::ostringstream out;
  out << std::setprecision(std::numeric_limits<double>::max_digits10)
      << "QRE2FORECASTROW4|" << forecast_law_sha256() << '|'
      << static_cast<unsigned>(row.asset) << '|' << row.d8 << '|'
      << static_cast<unsigned>(row.segment) << '|'
      << static_cast<unsigned>(row.status) << '|'
      << static_cast<unsigned>(row.missing_reason) << '|' << row.history_end_d8
      << '|' << row.availability_ts_ns << '|' << row.fit_month << '|'
      << row.fit_end_range_d8 << '|' << row.fit_end_sigma_d8 << '|'
      << row.n_train_range << '|' << row.rank_range << '|'
      << row.n_train_sigma << '|' << row.rank_sigma << '|' << row.rv1_usd << '|'
      << row.rv5_usd << '|' << row.rv22_usd << '|' << row.prior_parkinson_usd
      << '|' << row.prior_gk_usd << '|' << row.prior_rs_usd << '|'
      << row.prior_jump_usd << '|' << row.sigma_raw_hat_usd << '|'
      << row.sigma_persistence_usd << '|' << row.sigma_calibration_ratio << '|'
      << row.n_sigma_calibration << '|' << row.sigma_hat_usd << '|'
      << row.range_hat_usd << '|' << row.rv5_over_rv66 << '|'
      << row.regime_cut_lo << '|' << row.regime_cut_hi << '|'
      << static_cast<unsigned>(row.regime) << '|'
      << static_cast<unsigned>(row.ladder_source) << '|' << row.n_calibration
      << '|' << row.n_regime_calibration;
  for (double value : row.move_ratio) out << '|' << value;
  for (double value : row.move_usd) out << '|' << value;
  for (double value : row.regime_move_ratio) out << '|' << value;
  for (double value : row.regime_move_usd) out << '|' << value;
  out << '|' << row.phase_profile_sha256 << '|' << row.model_sha256 << '|'
      << row.history_source_sha256;
  return sha256_bytes(out.str());
}

Expected<ForecastSessionRealization, Refusal> realize_forecast_session(
    qr::futsess::Asset asset, const LockRow& lock, const PhaseRow& schedule,
    const EventPack& pack, const DayPriors& sane_priors,
    std::size_t session_ordinal) {
  if (std::memcmp(pack.header.magic, "QRE2EVT2", 8) != 0 ||
      pack.header.version != 2u || pack.header.row_bytes != kEventRowBytes) {
    return refuse<ForecastSessionRealization>(forecast_content(
        "qr_entry_v2::realize_forecast_session", "QRE2EVT2 pack is required"));
  }
  if (lock.status != LockStatus::LOCKED || lock.locked_iid < 0 ||
      lock.d8 != pack.header.d8 || lock.d8 != sane_priors.d8 ||
      pack.header.asset_idx != static_cast<std::uint8_t>(asset) ||
      pack.header.locked_iid != lock.locked_iid ||
      pack.header.open_utc != lock.open_utc ||
      pack.header.close_utc != lock.close_utc || schedule.month != lock.d8 / 100 ||
      lock.d8 < kDevelopmentStartD8 || lock.d8 >= kDevelopmentEndD8Exclusive) {
    return refuse<ForecastSessionRealization>(forecast_content(
        "qr_entry_v2::realize_forecast_session",
        "lock/schedule/event-pack key mismatch or development-wall escape"));
  }
  ForecastSessionRealization out;
  for (std::size_t i = 0; i < out.segment.size(); ++i) {
    out.segment[i].segment = static_cast<ForecastSegment>(i);
    initialize_missing(&out.segment[i]);
  }
  out.sane_commit.d8 = lock.d8;
  out.sane_commit.locked_iid = lock.locked_iid;
  out.sane_commit.session_ordinal = session_ordinal;
  std::array<std::vector<MidObservation>, kForecastSegmentCount> observations;
  std::uint64_t previous_ts_recv = 0;
  bool have_previous = false;
  BookQualityState book_quality;
  for (const EventRow& event : pack.rows) {
    if (have_previous && event.ts_recv_ns < previous_ts_recv) {
      return refuse<ForecastSessionRealization>(Refusal(
          RefusalCode::OUT_OF_ORDER, "qr_entry_v2::realize_forecast_session",
          "event pack receive timestamps are decreasing"));
    }
    previous_ts_recv = event.ts_recv_ns;
    have_previous = true;
    const std::int64_t event_sec =
        static_cast<std::int64_t>(event.ts_recv_ns / kNsPerSecond);
    if (event_sec < lock.open_utc || event_sec >= lock.close_utc) {
      return refuse<ForecastSessionRealization>(forecast_clock(
          "qr_entry_v2::realize_forecast_session",
          "event lies outside its locked session", event_sec));
    }
    if (event.receive_session_sec != event_sec - lock.open_utc) {
      return refuse<ForecastSessionRealization>(forecast_clock(
          "qr_entry_v2::realize_forecast_session",
          "receive_session_sec differs from ts_recv", event.receive_session_sec));
    }
    auto classified = classify_sane_book(asset, event, schedule, sane_priors);
    if (!classified) return refuse<ForecastSessionRealization>(classified.error());
    auto quality = book_quality.observe(event.ts_recv_ns, event.flags,
                                       classified.value().two_sided);
    if (!quality) return refuse<ForecastSessionRealization>(quality.error());
    if (quality.value().reset_derived_state) {
      for (auto& segment : observations) segment.clear();
      out.sane_commit.phase_spread_ticks = {};
    }
    if (!quality.value().trusted_economic) continue;
    if (classified.value().two_sided) {
      ++out.sane_commit.phase_spread_ticks[classified.value().phase]
                                                  [classified.value().spread_ticks];
    }
    if (!classified.value().sane) continue;
    const MidObservation observation{
        event.ts_recv_ns, event.receive_session_sec,
        quality.value().generation,
        classified.value().mid2};
    observations[segment_index(ForecastSegment::SESSION)].push_back(observation);
    observations[segment_index(phase_segment(classified.value().phase))].push_back(
        observation);
  }
  if (book_quality.unresolved_taint()) {
    out.sane_commit.phase_spread_ticks = {};
    return out;
  }
  for (std::size_t i = 0; i < observations.size(); ++i) {
    out.segment[i] = realize_segment(asset, static_cast<ForecastSegment>(i),
                                     observations[i]);
  }
  return out;
}

struct ForecastModelState::Impl {
  explicit Impl(qr::futsess::Asset selected) : asset(selected) {
    history_source_sha256 = sha256_bytes(
        std::string("QRE2FORECASTHISTORY4|") +
        qr::futsess::asset_spec(asset).name);
  }

  struct Models {
    Fit range;
    Fit sigma;
    std::string hash;
  };

  qr::futsess::Asset asset;
  std::array<SegmentState, kForecastSegmentCount> segment{};
  std::int32_t last_committed_d8 = -1;
  std::string history_source_sha256;
  std::int32_t cached_month = -1;
  std::array<Models, kForecastSegmentCount> models{};
  bool pending = false;
  std::int32_t pending_d8 = -1;
  std::array<Design, kForecastSegmentCount> pending_design{};
  std::array<ForecastRow, kForecastSegmentCount> pending_rows{};

  void fit_month(std::int32_t month) {
    if (cached_month == month) return;
    for (std::size_t i = 0; i < segment.size(); ++i) {
      models[i].range = fit_ols(segment[i].examples, month, true);
      models[i].sigma = fit_ols(segment[i].examples, month, false);
      models[i].hash = model_hash(month, static_cast<ForecastSegment>(i),
                                  models[i].range, models[i].sigma);
    }
    cached_month = month;
  }
};

ForecastModelState::ForecastModelState(qr::futsess::Asset asset)
    : impl_(std::make_unique<Impl>(asset)) {}
ForecastModelState::~ForecastModelState() = default;
ForecastModelState::ForecastModelState(ForecastModelState&&) noexcept = default;
ForecastModelState& ForecastModelState::operator=(ForecastModelState&&) noexcept = default;

Expected<std::array<ForecastRow, kForecastSegmentCount>, Refusal>
ForecastModelState::snapshot(std::int32_t d8, std::int64_t session_open_utc,
                             const std::string& phase_profile_sha256) {
  if (impl_->pending) {
    return refuse<std::array<ForecastRow, kForecastSegmentCount>>(forecast_clock(
        "qr_entry_v2::ForecastModelState::snapshot",
        "previous forecast snapshot has not been committed"));
  }
  if (d8 < kDevelopmentStartD8 || d8 >= kDevelopmentEndD8Exclusive ||
      (impl_->last_committed_d8 >= 0 && d8 <= impl_->last_committed_d8) ||
      session_open_utc <= 0 || !valid_sha256(phase_profile_sha256) ||
      static_cast<std::uint64_t>(session_open_utc) >
          std::numeric_limits<std::uint64_t>::max() / kNsPerSecond) {
    return refuse<std::array<ForecastRow, kForecastSegmentCount>>(forecast_clock(
        "qr_entry_v2::ForecastModelState::snapshot",
        "snapshot must be a chronological development session with pinned phase"));
  }
  const std::int32_t month = d8 / 100;
  impl_->fit_month(month);
  const std::uint64_t availability =
      static_cast<std::uint64_t>(session_open_utc) * kNsPerSecond;
  for (std::size_t s = 0; s < kForecastSegmentCount; ++s) {
    ForecastRow row;
    initialize_missing(&row);
    row.asset = impl_->asset;
    row.d8 = d8;
    row.segment = static_cast<ForecastSegment>(s);
    row.history_end_d8 = impl_->last_committed_d8;
    row.availability_ts_ns = availability;
    row.fit_month = month;
    row.phase_profile_sha256 = phase_profile_sha256;
    row.history_source_sha256 = impl_->history_source_sha256;
    const Impl::Models& model = impl_->models[s];
    row.fit_end_range_d8 = model.range.fit_end_d8;
    row.fit_end_sigma_d8 = model.sigma.fit_end_d8;
    row.n_train_range = model.range.n_train;
    row.rank_range = model.range.rank;
    row.n_train_sigma = model.sigma.n_train;
    row.rank_sigma = model.sigma.rank;
    row.model_sha256 = model.hash;

    const Design design = make_design(impl_->segment[s], d8);
    impl_->pending_design[s] = design;
    if (design.valid) {
      row.rv1_usd = design.rv1;
      row.rv5_usd = design.rv5;
      row.rv22_usd = design.rv22;
      row.prior_parkinson_usd = design.parkinson;
      row.prior_gk_usd = design.gk;
      row.prior_rs_usd = design.rs;
      row.prior_jump_usd = design.jump;
    }

    row.rv5_over_rv66 = exact_regime_ratio(impl_->segment[s]);
    const std::vector<double> regime_history =
        trailing_values(impl_->segment[s], true);
    if (regime_history.size() >= kForecastCalibrationMin) {
      row.regime_cut_lo = percentile(regime_history, 1.0 / 3.0);
      row.regime_cut_hi = percentile(regime_history, 2.0 / 3.0);
    }
    row.regime = regime_of(row.rv5_over_rv66, row.regime_cut_lo,
                           row.regime_cut_hi);

    if (!design.valid) {
      row.missing_reason = ForecastMissingReason::DESIGN_HISTORY;
    } else if (model.range.n_train < kForecastMinTrain ||
               model.sigma.n_train < kForecastMinTrain) {
      row.missing_reason = ForecastMissingReason::MIN_TRAIN;
    } else if (!model.range.ready || !model.sigma.ready) {
      row.missing_reason = ForecastMissingReason::RANK_DEFICIENT;
    } else {
      row.range_hat_usd = predict(model.range, design);
      row.sigma_raw_hat_usd = predict(model.sigma, design);
      row.sigma_persistence_usd = std::sqrt(design.rv1);
      const std::vector<double> sigma_calibration =
          trailing_sigma_calibration(impl_->segment[s]);
      row.n_sigma_calibration =
          static_cast<std::uint32_t>(sigma_calibration.size());
      row.sigma_calibration_ratio =
          sigma_calibration.size() >= kForecastSigmaCalibrationMin
              ? percentile(sigma_calibration, 0.5)
              : 1.0;
      row.sigma_hat_usd =
          kForecastSigmaOlsWeight *
              row.sigma_raw_hat_usd * row.sigma_calibration_ratio +
          (1.0 - kForecastSigmaOlsWeight) * row.sigma_persistence_usd;
      if (!std::isfinite(row.range_hat_usd) ||
          !std::isfinite(row.sigma_raw_hat_usd) ||
          !std::isfinite(row.sigma_persistence_usd) ||
          !std::isfinite(row.sigma_calibration_ratio) ||
          !std::isfinite(row.sigma_hat_usd) ||
          !(row.sigma_raw_hat_usd > 0.0) ||
          !(row.sigma_persistence_usd > 0.0) ||
          !(row.sigma_calibration_ratio > 0.0) ||
          !(row.sigma_hat_usd > 0.0)) {
        row.missing_reason = ForecastMissingReason::NONFINITE_PREDICTION;
      } else {
        row.status = ForecastStatus::READY;
        row.missing_reason = ForecastMissingReason::NONE;
      }
    }

    const std::vector<double> calibration =
        trailing_values(impl_->segment[s], false);
    row.n_calibration = static_cast<std::uint32_t>(calibration.size());
    if (row.status == ForecastStatus::READY &&
        calibration.size() >= kForecastCalibrationMin) {
      for (std::size_t q = 0; q < kForecastQuantiles.size(); ++q) {
        row.move_ratio[q] = percentile(calibration, kForecastQuantiles[q]);
        row.move_usd[q] = row.move_ratio[q] * row.sigma_hat_usd;
      }
      std::vector<double> regime_calibration;
      if (row.regime != ForecastRegime::NA) {
        const auto& history = impl_->segment[s].history;
        const std::size_t begin = history.size() > kForecastCalibrationWindow
                                      ? history.size() - kForecastCalibrationWindow
                                      : 0u;
        for (std::size_t i = begin; i < history.size(); ++i) {
          if (history[i].regime == row.regime &&
              std::isfinite(history[i].forecast_ratio)) {
            regime_calibration.push_back(history[i].forecast_ratio);
          }
        }
      }
      row.n_regime_calibration =
          static_cast<std::uint32_t>(regime_calibration.size());
      if (regime_calibration.size() >= kForecastCalibrationMin) {
        row.ladder_source = ForecastLadderSource::REGIME;
        for (std::size_t q = 0; q < kForecastQuantiles.size(); ++q) {
          row.regime_move_ratio[q] =
              percentile(regime_calibration, kForecastQuantiles[q]);
          row.regime_move_usd[q] =
              row.regime_move_ratio[q] * row.sigma_hat_usd;
        }
      } else {
        row.ladder_source = ForecastLadderSource::UNSCALED_FALLBACK;
        row.regime_move_ratio = row.move_ratio;
        row.regime_move_usd = row.move_usd;
      }
    }
    row.lineage_sha256 = forecast_row_lineage(row);
    impl_->pending_rows[s] = row;
  }
  impl_->pending = true;
  impl_->pending_d8 = d8;
  return impl_->pending_rows;
}

Expected<std::monostate, Refusal> ForecastModelState::commit(
    std::int32_t d8,
    const std::array<RealizedVolSegment, kForecastSegmentCount>& realized,
    const std::string& source_session_sha256) {
  if (!impl_->pending || d8 != impl_->pending_d8 ||
      !valid_sha256(source_session_sha256)) {
    return refuse<std::monostate>(forecast_clock(
        "qr_entry_v2::ForecastModelState::commit",
        "commit must match the pending snapshot and a pinned source session"));
  }
  const RealizedVolSegment& session_realized =
      realized[segment_index(ForecastSegment::SESSION)];
  for (std::size_t s = 0; s < kForecastSegmentCount; ++s) {
    if (realized[s].segment != static_cast<ForecastSegment>(s)) {
      return refuse<std::monostate>(forecast_content(
          "qr_entry_v2::ForecastModelState::commit",
          "realized segment array is not in canonical order"));
    }
    if (!realized[s].valid || !std::isfinite(realized[s].range_usd) ||
        !(realized[s].range_usd > 0.0)) {
      continue;  // documented b2_fvol degenerate-segment drop, never imputed
    }
    if (impl_->pending_design[s].valid) {
      Example example;
      example.d8 = d8;
      example.x = impl_->pending_design[s].x;
      example.log_range = std::log(realized[s].range_usd);
      if (std::isfinite(realized[s].sigma_usd) && realized[s].sigma_usd > 0.0) {
        example.log_sigma = std::log(realized[s].sigma_usd);
      }
      impl_->segment[s].examples.push_back(std::move(example));
    }
    Observation observation;
    observation.d8 = d8;
    observation.realized = realized[s];
    if (session_realized.valid) {
      observation.session_parkinson = session_realized.parkinson_usd;
      observation.session_gk = session_realized.gk_usd;
      observation.session_rs = session_realized.rs_usd;
    }
    const ForecastRow& pending = impl_->pending_rows[s];
    if (pending.status == ForecastStatus::READY &&
        std::isfinite(pending.sigma_hat_usd) && pending.sigma_hat_usd > 0.0) {
      observation.forecast_ratio = realized[s].range_usd /
                                   pending.sigma_hat_usd;
    }
    if (pending.status == ForecastStatus::READY &&
        std::isfinite(pending.sigma_raw_hat_usd) &&
        pending.sigma_raw_hat_usd > 0.0 &&
        std::isfinite(realized[s].sigma_usd) && realized[s].sigma_usd > 0.0) {
      observation.sigma_forecast_ratio =
          realized[s].sigma_usd / pending.sigma_raw_hat_usd;
    }
    observation.regime_ratio = pending.rv5_over_rv66;
    observation.regime = pending.regime;
    impl_->segment[s].history.push_back(std::move(observation));
  }
  std::ostringstream token;
  token << "QRE2FORECASTCOMMIT4|" << impl_->history_source_sha256 << '|'
        << d8 << '|' << source_session_sha256;
  impl_->history_source_sha256 = sha256_bytes(token.str());
  impl_->last_committed_d8 = d8;
  impl_->pending = false;
  impl_->pending_d8 = -1;
  return std::monostate{};
}

}  // namespace qr::entry_v2
