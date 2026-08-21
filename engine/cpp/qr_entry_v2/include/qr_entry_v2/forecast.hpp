// qr_entry_v2/forecast.hpp -- causal realized-volatility and HAR forecasts.
//
// QRE2FORECAST4 is observational context. It is generated at the current
// session open from completed QRE2 sessions only and is never part of a G1
// candidate's identity.  Current-session realized values live only inside the
// state after commit and are not serialized onto that session's forecast row.
#ifndef QR_ENTRY_V2_FORECAST_HPP
#define QR_ENTRY_V2_FORECAST_HPP

#include <array>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "qr_entry_v2/g1.hpp"

namespace qr::entry_v2 {

inline constexpr std::size_t kForecastSegmentCount = 4;
inline constexpr std::size_t kForecastFeatureCount = 12;
inline constexpr std::size_t kForecastMinTrain = 250;
inline constexpr std::int32_t kForecastSubsampleSec = 300;
inline constexpr std::size_t kForecastRegimeLong = 66;
inline constexpr std::size_t kForecastCalibrationWindow = 250;
inline constexpr std::size_t kForecastCalibrationMin = 30;
inline constexpr std::size_t kForecastSigmaCalibrationWindow = 66;
inline constexpr std::size_t kForecastSigmaCalibrationMin = 20;
inline constexpr double kForecastSigmaOlsWeight = 1.0;
inline constexpr std::array<double, 5> kForecastQuantiles = {
    0.10, 0.25, 0.50, 0.75, 0.90};

enum class ForecastSegment : std::uint8_t {
  SESSION = 0,
  TOKYO = 1,
  LONDON = 2,
  NY = 3,
};

[[nodiscard]] const char* forecast_segment_name(ForecastSegment segment) noexcept;
[[nodiscard]] Expected<ForecastSegment, Refusal> forecast_segment_from_name(
    const std::string& name);

enum class ForecastStatus : std::uint8_t { READY = 0, MISSING };
enum class ForecastMissingReason : std::uint8_t {
  NONE = 0,
  DESIGN_HISTORY,
  MIN_TRAIN,
  RANK_DEFICIENT,
  NONFINITE_PREDICTION,
};
enum class ForecastRegime : std::uint8_t { NA = 0, LOW, MID, HIGH };
enum class ForecastLadderSource : std::uint8_t {
  MISSING = 0,
  REGIME,
  UNSCALED_FALLBACK,
};

[[nodiscard]] const char* forecast_status_name(ForecastStatus status) noexcept;
[[nodiscard]] const char* forecast_missing_reason_name(
    ForecastMissingReason reason) noexcept;
[[nodiscard]] const char* forecast_regime_name(ForecastRegime regime) noexcept;
[[nodiscard]] const char* forecast_ladder_source_name(
    ForecastLadderSource source) noexcept;

// Completed-session target/input values.  RV/BV/jump are sums of squared
// 300-second dollar returns (the historical b2_fvol field names carry `_usd`).
struct RealizedVolSegment {
  ForecastSegment segment = ForecastSegment::SESSION;
  bool valid = false;
  std::uint64_t sane_events = 0;
  std::uint64_t grid_samples = 0;
  double open_px = 0.0;
  double high_px = 0.0;
  double low_px = 0.0;
  double close_px = 0.0;
  double range_usd = 0.0;
  double rv_usd = 0.0;
  double bv_usd = 0.0;
  double jump_usd = 0.0;
  double sigma_usd = 0.0;
  double parkinson_usd = 0.0;
  double gk_usd = 0.0;
  double rs_usd = 0.0;
};

struct ForecastSessionRealization {
  std::array<RealizedVolSegment, kForecastSegmentCount> segment{};
  // Same raw two-sided spread histograms as G1; admitted only after the
  // forecast snapshot so day d never influences day d sanity or prediction.
  CompletedSessionInput sane_commit{};
};

[[nodiscard]] Expected<ForecastSessionRealization, Refusal>
realize_forecast_session(qr::futsess::Asset asset, const LockRow& lock,
                         const PhaseRow& schedule, const EventPack& pack,
                         const DayPriors& sane_priors,
                         std::size_t session_ordinal);

struct ForecastRow {
  qr::futsess::Asset asset = qr::futsess::Asset::SI;
  std::int32_t d8 = 0;
  ForecastSegment segment = ForecastSegment::SESSION;
  ForecastStatus status = ForecastStatus::MISSING;
  ForecastMissingReason missing_reason = ForecastMissingReason::DESIGN_HISTORY;
  std::int32_t history_end_d8 = -1;
  std::uint64_t availability_ts_ns = 0;
  std::int32_t fit_month = 0;
  std::int32_t fit_end_range_d8 = -1;
  std::int32_t fit_end_sigma_d8 = -1;
  std::uint32_t n_train_range = 0;
  std::uint32_t rank_range = 0;
  std::uint32_t n_train_sigma = 0;
  std::uint32_t rank_sigma = 0;

  // Exact no-imputation HAR inputs known at availability_ts_ns.
  double rv1_usd = 0.0;
  double rv5_usd = 0.0;
  double rv22_usd = 0.0;
  double prior_parkinson_usd = 0.0;
  double prior_gk_usd = 0.0;
  double prior_rs_usd = 0.0;
  double prior_jump_usd = 0.0;

  // The final sigma is an evidence-selected shrinkage forecast.  Every
  // component is serialized so calibration cannot become an opaque model
  // mutation.  V4's exact-sidecar selection chose the causally calibrated
  // raw OLS (weight 1.0); persistence remains serialized as a comparator.
  double sigma_raw_hat_usd = 0.0;
  double sigma_persistence_usd = 0.0;
  double sigma_calibration_ratio = 0.0;
  std::uint32_t n_sigma_calibration = 0;
  double sigma_hat_usd = 0.0;
  double range_hat_usd = 0.0;
  double rv5_over_rv66 = 0.0;
  double regime_cut_lo = 0.0;
  double regime_cut_hi = 0.0;
  ForecastRegime regime = ForecastRegime::NA;
  ForecastLadderSource ladder_source = ForecastLadderSource::MISSING;
  std::uint32_t n_calibration = 0;
  std::uint32_t n_regime_calibration = 0;
  std::array<double, 5> move_ratio{};
  std::array<double, 5> move_usd{};
  std::array<double, 5> regime_move_ratio{};
  std::array<double, 5> regime_move_usd{};

  std::string phase_profile_sha256;
  std::string model_sha256;
  std::string history_source_sha256;
  std::string lineage_sha256;
};

[[nodiscard]] std::string forecast_law_sha256();
[[nodiscard]] std::string forecast_row_lineage(const ForecastRow& row);

// Stateful chronological owner. snapshot(d) freezes four rows and their
// designs before commit(d) is allowed to admit realized targets or source
// hashes. Monthly coefficients are fitted only on examples before YYYYMM01.
class ForecastModelState {
 public:
  explicit ForecastModelState(qr::futsess::Asset asset);
  ~ForecastModelState();
  ForecastModelState(ForecastModelState&&) noexcept;
  ForecastModelState& operator=(ForecastModelState&&) noexcept;
  ForecastModelState(const ForecastModelState&) = delete;
  ForecastModelState& operator=(const ForecastModelState&) = delete;

  [[nodiscard]] Expected<std::array<ForecastRow, kForecastSegmentCount>, Refusal>
  snapshot(std::int32_t d8, std::int64_t session_open_utc,
           const std::string& phase_profile_sha256);
  [[nodiscard]] Expected<std::monostate, Refusal> commit(
      std::int32_t d8,
      const std::array<RealizedVolSegment, kForecastSegmentCount>& realized,
      const std::string& source_session_sha256);

 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

struct ForecastArtifact {
  qr::futsess::Asset asset = qr::futsess::Asset::SI;
  std::int32_t start_d8 = 0;
  std::int32_t end_d8_exclusive = 0;
  std::string law_sha256;
  std::string artifact_sha256;
  std::vector<ForecastRow> rows;
};

struct ForecastBuildStats {
  std::uint64_t sessions = 0;
  std::uint64_t rows = 0;
  std::uint64_t ready = 0;
  std::uint64_t missing = 0;
  std::uint64_t evaluation_rows = 0;
  std::uint64_t evaluation_valid = 0;
  std::string output_sha256;
  std::string evaluation_output_sha256;
  std::string receipt_sha256;
};

[[nodiscard]] Expected<ForecastBuildStats, Refusal> build_forecast_artifact(
    const Config& config);

// Reader requires the caller's pinned artifact hash. It validates schema,
// window, row lineage, strict availability, and the 2025H2 wall.
[[nodiscard]] Expected<ForecastArtifact, Refusal> read_forecast_artifact(
    const Config& config, const std::string& expected_sha256);

// Exact later join contract. Availability and decision are receive-clock values.
// Equal availability is not causal: only
// availability_ts_ns < decision_ts_ns is admitted.
[[nodiscard]] Expected<ForecastRow, Refusal> join_forecast(
    const ForecastArtifact& artifact, std::int32_t d8,
    ForecastSegment segment, std::uint64_t decision_ts_ns,
    const std::string& expected_artifact_sha256);

}  // namespace qr::entry_v2

#endif  // QR_ENTRY_V2_FORECAST_HPP
