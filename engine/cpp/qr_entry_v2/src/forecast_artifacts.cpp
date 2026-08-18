#include "qr_entry_v2/forecast.hpp"

#include <openssl/evp.h>

#include <algorithm>
#include <array>
#include <charconv>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>
#include <map>
#include <set>
#include <sstream>
#include <string_view>
#include <tuple>
#include <utility>

#include "qr_futsess/json.hpp"

namespace qr::entry_v2 {
namespace {

namespace fs = std::filesystem;
using qr::futsess::JsonWriter;

constexpr std::string_view kForecastSchema = "QRE2FORECAST2";
constexpr std::string_view kForecastReceiptSchema = "QRE2FORECASTRECEIPT2";

struct EventManifestRow {
  std::int32_t d8 = 0;
  std::string status;
  std::int64_t locked_iid = -1;
  std::int64_t selection_basis_d8 = -1;
  std::int64_t open_utc = 0;
  std::int64_t close_utc = 0;
  std::string binary_file;
  std::string binary_sha256;
  std::string sidecar_file;
  std::string sidecar_sha256;
};

[[nodiscard]] const char* asset_name(qr::futsess::Asset asset) {
  return qr::futsess::asset_spec(asset).name;
}

[[nodiscard]] std::string window_tag(const Config& config) {
  return "start_d8=" + std::to_string(config.start_d8) +
         " end_d8_exclusive=" + std::to_string(config.end_d8_exclusive);
}

[[nodiscard]] Expected<std::monostate, Refusal> validate_window(
    const Config& config, const char* site) {
  if (config.start_d8 < kDevelopmentStartD8 ||
      config.end_d8_exclusive > kDevelopmentEndD8Exclusive ||
      config.start_d8 >= config.end_d8_exclusive) {
    return refuse<std::monostate>(Refusal(
        RefusalCode::DAY_OUTSIDE_CALENDAR, site,
        "QRE2FORECAST2 is confined to [20210101,20250701)"));
  }
  return std::monostate{};
}

[[nodiscard]] Refusal io_refusal(const char* site, const char* detail) {
  return Refusal(RefusalCode::IO, site, detail);
}

[[nodiscard]] Refusal content_refusal(const char* site, const char* detail,
                                      std::int64_t context = 0) {
  return Refusal(RefusalCode::CONTENT_MISMATCH, site, detail, context);
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

[[nodiscard]] Expected<std::string, Refusal> sha256_file(const fs::path& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    return refuse<std::string>(io_refusal(
        "qr_entry_v2::forecast/sha256_file", "cannot open artifact for hashing"));
  }
  EVP_MD_CTX* context = EVP_MD_CTX_new();
  if (context == nullptr || EVP_DigestInit_ex(context, EVP_sha256(), nullptr) != 1) {
    EVP_MD_CTX_free(context);
    return refuse<std::string>(io_refusal(
        "qr_entry_v2::forecast/sha256_file", "cannot initialize SHA-256"));
  }
  std::array<char, 1u << 20> buffer{};
  while (in) {
    in.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
    const std::streamsize got = in.gcount();
    if (got > 0 && EVP_DigestUpdate(context, buffer.data(),
                                    static_cast<std::size_t>(got)) != 1) {
      EVP_MD_CTX_free(context);
      return refuse<std::string>(io_refusal(
          "qr_entry_v2::forecast/sha256_file", "cannot update SHA-256"));
    }
  }
  if (!in.eof()) {
    EVP_MD_CTX_free(context);
    return refuse<std::string>(io_refusal(
        "qr_entry_v2::forecast/sha256_file", "cannot read artifact"));
  }
  std::array<unsigned char, EVP_MAX_MD_SIZE> digest{};
  unsigned int length = 0;
  const int finalized = EVP_DigestFinal_ex(context, digest.data(), &length);
  EVP_MD_CTX_free(context);
  if (finalized != 1 || length != 32u) {
    return refuse<std::string>(io_refusal(
        "qr_entry_v2::forecast/sha256_file", "cannot finalize SHA-256"));
  }
  return hex_digest(digest.data(), length);
}

[[nodiscard]] Expected<std::string, Refusal> read_text(const fs::path& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    return refuse<std::string>(io_refusal(
        "qr_entry_v2::forecast/read_text", "cannot open required artifact"));
  }
  std::ostringstream out;
  out << in.rdbuf();
  if (!in.eof() && in.fail()) {
    return refuse<std::string>(io_refusal(
        "qr_entry_v2::forecast/read_text", "cannot read required artifact"));
  }
  return out.str();
}

[[nodiscard]] Expected<std::monostate, Refusal> write_atomic(
    const fs::path& path, std::string_view bytes) {
  std::error_code ec;
  fs::create_directories(path.parent_path(), ec);
  if (ec) {
    return refuse<std::monostate>(io_refusal(
        "qr_entry_v2::forecast/write_atomic", "cannot create artifact directory"));
  }
  const fs::path temporary = path.string() + ".tmp";
  std::FILE* file = std::fopen(temporary.c_str(), "wb");
  if (file == nullptr) {
    return refuse<std::monostate>(io_refusal(
        "qr_entry_v2::forecast/write_atomic", "cannot open temporary artifact"));
  }
  const std::size_t wrote = std::fwrite(bytes.data(), 1, bytes.size(), file);
  const int closed = std::fclose(file);
  if (wrote != bytes.size() || closed != 0) {
    fs::remove(temporary, ec);
    return refuse<std::monostate>(io_refusal(
        "qr_entry_v2::forecast/write_atomic", "short artifact write"));
  }
  fs::rename(temporary, path, ec);
  if (ec) {
    fs::remove(temporary, ec);
    return refuse<std::monostate>(io_refusal(
        "qr_entry_v2::forecast/write_atomic", "cannot publish artifact"));
  }
  return std::monostate{};
}

[[nodiscard]] fs::path forecast_path(const Config& config) {
  return fs::path(config.output_root) / "forecast" /
         (std::string(asset_name(config.asset)) + ".qrf2.tsv");
}

[[nodiscard]] fs::path receipt_path(const Config& config) {
  return fs::path(config.output_root) / "forecast" /
         (std::string(asset_name(config.asset)) + ".qrf2.json");
}

[[nodiscard]] fs::path event_manifest_path(const Config& config) {
  return fs::path(config.output_root) / "events" / asset_name(config.asset) /
         "manifest.tsv";
}

[[nodiscard]] std::vector<std::string> split_tabs(std::string_view line) {
  std::vector<std::string> out;
  std::size_t start = 0;
  for (;;) {
    const std::size_t tab = line.find('\t', start);
    const std::size_t stop = tab == std::string_view::npos ? line.size() : tab;
    out.emplace_back(line.substr(start, stop - start));
    if (tab == std::string_view::npos) break;
    start = tab + 1u;
  }
  if (!out.empty() && !out.back().empty() && out.back().back() == '\r') {
    out.back().pop_back();
  }
  return out;
}

template <class T>
[[nodiscard]] bool parse_int(std::string_view text, T* out) {
  const char* begin = text.data();
  const char* end = begin + text.size();
  const auto parsed = std::from_chars(begin, end, *out);
  return parsed.ec == std::errc{} && parsed.ptr == end;
}

[[nodiscard]] bool parse_double(std::string_view text, double* out) {
  if (text == "NA") {
    *out = std::numeric_limits<double>::quiet_NaN();
    return true;
  }
  std::string copy(text);
  char* end = nullptr;
  *out = std::strtod(copy.c_str(), &end);
  return end == copy.c_str() + static_cast<std::ptrdiff_t>(copy.size()) &&
         std::isfinite(*out);
}

[[nodiscard]] std::string number_or_na(double value) {
  if (!std::isfinite(value)) return "NA";
  std::ostringstream out;
  out << std::setprecision(std::numeric_limits<double>::max_digits10) << value;
  return out.str();
}

[[nodiscard]] const std::vector<std::string>& forecast_columns() {
  static const std::vector<std::string> columns = [] {
    std::vector<std::string> out = {
        "asset", "d8", "segment", "status", "missing_reason",
        "history_end_d8", "availability_ts_ns", "fit_month",
        "fit_end_range_d8", "fit_end_sigma_d8", "n_train_range",
        "rank_range", "n_train_sigma", "rank_sigma", "rv1_usd", "rv5_usd",
        "rv22_usd", "prior_parkinson_usd", "prior_gk_usd", "prior_rs_usd",
        "prior_jump_usd", "sigma_hat_usd", "range_hat_usd",
        "rv5_over_rv66", "regime_cut_lo", "regime_cut_hi", "regime_tag",
        "ladder_source", "n_calibration", "n_regime_calibration"};
    for (const char* q : {"q10", "q25", "q50", "q75", "q90"}) {
      out.emplace_back(std::string("move_") + q + "_ratio");
      out.emplace_back(std::string("move_") + q + "_usd");
    }
    for (const char* q : {"q10", "q25", "q50", "q75", "q90"}) {
      out.emplace_back(std::string("move_rs_") + q + "_ratio");
      out.emplace_back(std::string("move_rs_") + q + "_usd");
    }
    out.insert(out.end(), {"phase_profile_sha256", "model_sha256",
                           "history_source_sha256", "lineage_sha256"});
    return out;
  }();
  return columns;
}

[[nodiscard]] std::string joined_columns() {
  std::ostringstream out;
  for (std::size_t i = 0; i < forecast_columns().size(); ++i) {
    if (i != 0u) out << '\t';
    out << forecast_columns()[i];
  }
  return out.str();
}

[[nodiscard]] std::string render_rows(const Config& config,
                                      const std::vector<ForecastRow>& rows) {
  std::ostringstream out;
  out << "# " << kForecastSchema << ' ' << window_tag(config) << " asset="
      << asset_name(config.asset) << " law_sha256=" << forecast_law_sha256()
      << '\n' << joined_columns() << '\n';
  out << std::setprecision(std::numeric_limits<double>::max_digits10);
  for (const ForecastRow& row : rows) {
    out << asset_name(row.asset) << '\t' << row.d8 << '\t'
        << forecast_segment_name(row.segment) << '\t'
        << forecast_status_name(row.status) << '\t'
        << forecast_missing_reason_name(row.missing_reason) << '\t'
        << row.history_end_d8 << '\t' << row.availability_ts_ns << '\t'
        << row.fit_month << '\t' << row.fit_end_range_d8 << '\t'
        << row.fit_end_sigma_d8 << '\t' << row.n_train_range << '\t'
        << row.rank_range << '\t' << row.n_train_sigma << '\t'
        << row.rank_sigma << '\t' << number_or_na(row.rv1_usd) << '\t'
        << number_or_na(row.rv5_usd) << '\t' << number_or_na(row.rv22_usd)
        << '\t' << number_or_na(row.prior_parkinson_usd) << '\t'
        << number_or_na(row.prior_gk_usd) << '\t'
        << number_or_na(row.prior_rs_usd) << '\t'
        << number_or_na(row.prior_jump_usd) << '\t'
        << number_or_na(row.sigma_hat_usd) << '\t'
        << number_or_na(row.range_hat_usd) << '\t'
        << number_or_na(row.rv5_over_rv66) << '\t'
        << number_or_na(row.regime_cut_lo) << '\t'
        << number_or_na(row.regime_cut_hi) << '\t'
        << forecast_regime_name(row.regime) << '\t'
        << forecast_ladder_source_name(row.ladder_source) << '\t'
        << row.n_calibration << '\t' << row.n_regime_calibration;
    for (std::size_t q = 0; q < kForecastQuantiles.size(); ++q) {
      out << '\t' << number_or_na(row.move_ratio[q]) << '\t'
          << number_or_na(row.move_usd[q]);
    }
    for (std::size_t q = 0; q < kForecastQuantiles.size(); ++q) {
      out << '\t' << number_or_na(row.regime_move_ratio[q]) << '\t'
          << number_or_na(row.regime_move_usd[q]);
    }
    out << '\t' << row.phase_profile_sha256 << '\t' << row.model_sha256
        << '\t' << row.history_source_sha256 << '\t' << row.lineage_sha256
        << '\n';
  }
  return out.str();
}

[[nodiscard]] Expected<std::vector<EventManifestRow>, Refusal>
read_event_manifest(const Config& config) {
  auto text = read_text(event_manifest_path(config));
  if (!text) return refuse<std::vector<EventManifestRow>>(text.error());
  std::istringstream in(text.value());
  std::string line;
  const std::string expected = "# QRE2EVENTMAN2 " + window_tag(config);
  const std::string columns =
      "asset\td8\tstatus\tlocked_iid\tselection_basis_d8\topen_utc\tclose_utc"
      "\tevent_count\tmin_ts_recv_ns\tmax_ts_recv_ns\tmin_ts_event_ns"
      "\tmax_ts_event_ns\traw_records\ttrusted_economic_records"
      "\tsnapshot_records\tstandalone_bad_ts_recv_records\tmaybe_bad_book_records"
      "\tbinary_file\tbinary_sha256\tsidecar_file\tsidecar_sha256";
  if (!std::getline(in, line) || line != expected || !std::getline(in, line) ||
      line != columns) {
    return refuse<std::vector<EventManifestRow>>(content_refusal(
        "qr_entry_v2::forecast/read_event_manifest",
        "source event manifest schema/window mismatch"));
  }
  std::vector<EventManifestRow> rows;
  while (std::getline(in, line)) {
    if (line.empty()) continue;
    const auto fields = split_tabs(line);
    EventManifestRow row;
    if (fields.size() != 21u || fields[0] != asset_name(config.asset) ||
        !parse_int(fields[1], &row.d8) || row.d8 < config.start_d8 ||
        row.d8 >= config.end_d8_exclusive ||
        !parse_int(fields[3], &row.locked_iid) ||
        !parse_int(fields[4], &row.selection_basis_d8) ||
        !parse_int(fields[5], &row.open_utc) ||
        !parse_int(fields[6], &row.close_utc) ||
        (!rows.empty() && row.d8 <= rows.back().d8)) {
      return refuse<std::vector<EventManifestRow>>(content_refusal(
          "qr_entry_v2::forecast/read_event_manifest", "invalid source row"));
    }
    row.status = fields[2];
    row.binary_file = fields[17];
    row.binary_sha256 = fields[18];
    row.sidecar_file = fields[19];
    row.sidecar_sha256 = fields[20];
    const std::string expected_binary =
        std::string("events/") + asset_name(config.asset) + "/" +
        std::to_string(row.d8) + ".qre2";
    const std::string expected_sidecar = expected_binary + ".json";
    if ((row.status == "READY") !=
            (row.binary_file != "-" && valid_sha256(row.binary_sha256)) ||
        (row.status != "READY" &&
         (row.binary_file != "-" || row.binary_sha256 != "-")) ||
        (row.status == "READY" && row.binary_file != expected_binary) ||
        row.sidecar_file != expected_sidecar || !valid_sha256(row.sidecar_sha256)) {
      return refuse<std::vector<EventManifestRow>>(content_refusal(
          "qr_entry_v2::forecast/read_event_manifest",
          "event status/binary hash mismatch", row.d8));
    }
    auto sidecar = read_text(fs::path(config.output_root) / row.sidecar_file);
    if (!sidecar || sha256_bytes(sidecar.value()) != row.sidecar_sha256) {
      return refuse<std::vector<EventManifestRow>>(content_refusal(
          "qr_entry_v2::forecast/read_event_manifest",
          "event sidecar differs from source manifest", row.d8));
    }
    rows.push_back(std::move(row));
  }
  return rows;
}

[[nodiscard]] std::map<std::int32_t, PhaseRow> phase_map(
    const std::vector<PhaseRow>& rows) {
  std::map<std::int32_t, PhaseRow> out;
  for (const PhaseRow& row : rows) out.emplace(row.month, row);
  return out;
}

[[nodiscard]] std::string source_session_hash(
    const Config& config, const LockRow& lock, const PhaseRow& phase,
    const EventManifestRow& event) {
  std::ostringstream out;
  out << "QRE2FORECASTSOURCE2|" << asset_name(config.asset) << '|' << lock.d8
      << '|' << lock_status_name(lock.status) << '|' << lock.locked_iid << '|'
      << lock.selection_basis_d8 << '|' << lock.open_utc << '|' << lock.close_utc
      << '|' << phase.profile_sha256 << '|' << event.status << '|'
      << event.binary_sha256;
  return sha256_bytes(out.str());
}

[[nodiscard]] std::string receipt_text(
    const Config& config, const ForecastBuildStats& stats,
    std::string_view event_manifest_sha, std::string_view locks_sha,
    std::string_view phases_sha, std::string_view lineage_sha) {
  JsonWriter json;
  json.begin_object();
  json.key("schema");
  json.value_string(std::string(kForecastReceiptSchema));
  json.key("asset");
  json.value_string(asset_name(config.asset));
  json.key("start_d8");
  json.value_int(config.start_d8);
  json.key("end_d8_exclusive");
  json.value_int(config.end_d8_exclusive);
  json.key("forecast_law_sha256");
  json.value_string(forecast_law_sha256());
  json.key("realized_law");
  json.value_string(
      "trusted QRE2EVT2 mids on ts_recv; snapshot atomically discards pre-reset "
      "current-session OHLC/extrema/return/spread aggregates; previous-tick "
      "300-second dollar returns; RV/BV/jump/Parkinson/GK/RS");
  json.key("model_law");
  json.value_string("expanding monthly rank-full OLS(log RANGE,log SIGMA); MIN_TRAIN=250; no imputation/context/substitution");
  json.key("availability_law");
  json.value_string(
      "availability_ts_ns=session_open_ts_recv_ns; join requires "
      "availability_ts_ns<decision_ts_ns");
  json.key("calibration_law");
  json.value_string("trailing250 strictly-prior range/sigma ratios; min30; causal trailing regime cuts; explicit unscaled fallback");
  json.key("sessions");
  json.value_int(static_cast<std::int64_t>(stats.sessions));
  json.key("rows");
  json.value_int(static_cast<std::int64_t>(stats.rows));
  json.key("ready");
  json.value_int(static_cast<std::int64_t>(stats.ready));
  json.key("missing");
  json.value_int(static_cast<std::int64_t>(stats.missing));
  json.key("source_hashes");
  json.begin_object();
  json.key("event_manifest_sha256");
  json.value_string(std::string(event_manifest_sha));
  json.key("locks_sha256");
  json.value_string(std::string(locks_sha));
  json.key("phase_schedule_sha256");
  json.value_string(std::string(phases_sha));
  json.end_object();
  json.key("lineage_aggregate_sha256");
  json.value_string(std::string(lineage_sha));
  json.key("output_sha256");
  json.value_string(stats.output_sha256);
  json.key("holdout_start_d8");
  json.value_int(kDevelopmentEndD8Exclusive);
  json.key("final_exam_permit");
  json.value_bool(false);
  json.end_object();
  return json.text() + "\n";
}

[[nodiscard]] Expected<ForecastStatus, Refusal> parse_status(
    const std::string& value) {
  if (value == "READY") return ForecastStatus::READY;
  if (value == "MISSING") return ForecastStatus::MISSING;
  return refuse<ForecastStatus>(content_refusal(
      "qr_entry_v2::read_forecast_artifact", "unknown forecast status"));
}

[[nodiscard]] Expected<ForecastMissingReason, Refusal> parse_reason(
    const std::string& value) {
  if (value == "NONE") return ForecastMissingReason::NONE;
  if (value == "DESIGN_HISTORY") return ForecastMissingReason::DESIGN_HISTORY;
  if (value == "MIN_TRAIN") return ForecastMissingReason::MIN_TRAIN;
  if (value == "RANK_DEFICIENT") return ForecastMissingReason::RANK_DEFICIENT;
  if (value == "NONFINITE_PREDICTION") {
    return ForecastMissingReason::NONFINITE_PREDICTION;
  }
  return refuse<ForecastMissingReason>(content_refusal(
      "qr_entry_v2::read_forecast_artifact", "unknown missing reason"));
}

[[nodiscard]] Expected<ForecastRegime, Refusal> parse_regime(
    const std::string& value) {
  if (value == "NA") return ForecastRegime::NA;
  if (value == "LOW") return ForecastRegime::LOW;
  if (value == "MID") return ForecastRegime::MID;
  if (value == "HIGH") return ForecastRegime::HIGH;
  return refuse<ForecastRegime>(content_refusal(
      "qr_entry_v2::read_forecast_artifact", "unknown forecast regime"));
}

[[nodiscard]] Expected<ForecastLadderSource, Refusal> parse_ladder(
    const std::string& value) {
  if (value == "MISSING") return ForecastLadderSource::MISSING;
  if (value == "REGIME") return ForecastLadderSource::REGIME;
  if (value == "UNSCALED_FALLBACK") {
    return ForecastLadderSource::UNSCALED_FALLBACK;
  }
  return refuse<ForecastLadderSource>(content_refusal(
      "qr_entry_v2::read_forecast_artifact", "unknown ladder source"));
}

[[nodiscard]] bool all_finite(const std::array<double, 5>& values) {
  return std::all_of(values.begin(), values.end(), [](double value) {
    return std::isfinite(value);
  });
}

[[nodiscard]] bool all_missing(const std::array<double, 5>& values) {
  return std::all_of(values.begin(), values.end(), [](double value) {
    return !std::isfinite(value);
  });
}

[[nodiscard]] bool positive_nondecreasing(
    const std::array<double, 5>& values) {
  for (std::size_t i = 0; i < values.size(); ++i) {
    if (!std::isfinite(values[i]) || !(values[i] > 0.0) ||
        (i != 0u && values[i] < values[i - 1u])) {
      return false;
    }
  }
  return true;
}

[[nodiscard]] bool exact_scaled(const std::array<double, 5>& ratios,
                                const std::array<double, 5>& dollars,
                                double sigma) {
  for (std::size_t i = 0; i < ratios.size(); ++i) {
    if (dollars[i] != ratios[i] * sigma) return false;
  }
  return true;
}

}  // namespace

Expected<ForecastBuildStats, Refusal> build_forecast_artifact(
    const Config& config) {
  auto window = validate_window(config, "qr_entry_v2::build_forecast_artifact");
  if (!window) return refuse<ForecastBuildStats>(window.error());
  auto locks = read_locks(config);
  auto phases = read_phases(config);
  auto events = read_event_manifest(config);
  if (!locks) return refuse<ForecastBuildStats>(locks.error());
  if (!phases) return refuse<ForecastBuildStats>(phases.error());
  if (!events) return refuse<ForecastBuildStats>(events.error());
  if (locks.value().size() != events.value().size()) {
    return refuse<ForecastBuildStats>(content_refusal(
        "qr_entry_v2::build_forecast_artifact",
        "locks and event manifest have different denominators"));
  }
  auto event_manifest_sha = sha256_file(event_manifest_path(config));
  auto locks_sha = sha256_file(fs::path(config.output_root) / "locks" /
                               (std::string(asset_name(config.asset)) + ".tsv"));
  auto phases_sha = sha256_file(fs::path(config.output_root) / "phases" /
                                (std::string(asset_name(config.asset)) + ".tsv"));
  if (!event_manifest_sha) return refuse<ForecastBuildStats>(event_manifest_sha.error());
  if (!locks_sha) return refuse<ForecastBuildStats>(locks_sha.error());
  if (!phases_sha) return refuse<ForecastBuildStats>(phases_sha.error());

  const auto by_month = phase_map(phases.value());
  CausalPriorState sane_state(config.asset);
  ForecastModelState model_state(config.asset);
  std::vector<ForecastRow> rows;
  rows.reserve(locks.value().size() * kForecastSegmentCount);
  ForecastBuildStats stats;
  for (std::size_t ordinal = 0; ordinal < locks.value().size(); ++ordinal) {
    const LockRow& lock = locks.value()[ordinal];
    const EventManifestRow& event = events.value()[ordinal];
    if (lock.d8 != event.d8 || lock.d8 < config.start_d8 ||
        lock.d8 >= config.end_d8_exclusive ||
        lock.d8 >= kDevelopmentEndD8Exclusive ||
        lock.locked_iid != event.locked_iid ||
        lock.selection_basis_d8 != event.selection_basis_d8 ||
        lock.open_utc != event.open_utc || lock.close_utc != event.close_utc) {
      return refuse<ForecastBuildStats>(content_refusal(
          "qr_entry_v2::build_forecast_artifact",
          "source rows escaped the exact development denominator", lock.d8));
    }
    const auto phase = by_month.find(lock.d8 / 100);
    if (phase == by_month.end() || !valid_sha256(phase->second.profile_sha256)) {
      return refuse<ForecastBuildStats>(content_refusal(
          "qr_entry_v2::build_forecast_artifact",
          "missing or unpinned causal phase schedule", lock.d8));
    }
    auto sane_priors = sane_state.snapshot(lock.d8);
    if (!sane_priors) return refuse<ForecastBuildStats>(sane_priors.error());

    // The row is frozen before this function opens or hashes the current pack.
    auto forecast = model_state.snapshot(lock.d8, lock.open_utc,
                                         phase->second.profile_sha256);
    if (!forecast) return refuse<ForecastBuildStats>(forecast.error());
    for (const ForecastRow& row : forecast.value()) {
      rows.push_back(row);
      ++stats.rows;
      if (row.status == ForecastStatus::READY) ++stats.ready;
      else ++stats.missing;
    }

    ForecastSessionRealization realized;
    for (std::size_t s = 0; s < realized.segment.size(); ++s) {
      realized.segment[s].segment = static_cast<ForecastSegment>(s);
    }
    realized.sane_commit.d8 = lock.d8;
    realized.sane_commit.locked_iid = lock.locked_iid;
    realized.sane_commit.session_ordinal = ordinal;
    if (event.status == "READY") {
      if (lock.status != LockStatus::LOCKED) {
        return refuse<ForecastBuildStats>(content_refusal(
            "qr_entry_v2::build_forecast_artifact",
            "READY event pack belongs to an unlocked session", lock.d8));
      }
      const fs::path path = fs::path(config.output_root) / event.binary_file;
      auto pack = read_event_pack(path.string(), event.binary_sha256);
      if (!pack) return refuse<ForecastBuildStats>(pack.error());
      auto current = realize_forecast_session(
          config.asset, lock, phase->second, pack.value(), sane_priors.value(),
          ordinal);
      if (!current) return refuse<ForecastBuildStats>(current.error());
      realized = std::move(current).value();
    }
    const std::string source_hash = source_session_hash(
        config, lock, phase->second, event);
    auto sane_committed = sane_state.commit(realized.sane_commit);
    if (!sane_committed) return refuse<ForecastBuildStats>(sane_committed.error());
    auto model_committed = model_state.commit(lock.d8, realized.segment, source_hash);
    if (!model_committed) return refuse<ForecastBuildStats>(model_committed.error());
    ++stats.sessions;
  }

  const std::string output = render_rows(config, rows);
  stats.output_sha256 = sha256_bytes(output);
  auto wrote = write_atomic(forecast_path(config), output);
  if (!wrote) return refuse<ForecastBuildStats>(wrote.error());
  std::ostringstream lineage;
  lineage << "QRE2FORECASTLINEAGES2";
  for (const ForecastRow& row : rows) lineage << '|' << row.lineage_sha256;
  const std::string lineage_sha = sha256_bytes(lineage.str());
  const std::string receipt = receipt_text(
      config, stats, event_manifest_sha.value(), locks_sha.value(),
      phases_sha.value(), lineage_sha);
  wrote = write_atomic(receipt_path(config), receipt);
  if (!wrote) return refuse<ForecastBuildStats>(wrote.error());
  stats.receipt_sha256 = sha256_bytes(receipt);
  return stats;
}

Expected<ForecastArtifact, Refusal> read_forecast_artifact(
    const Config& config, const std::string& expected_sha256) {
  auto window = validate_window(config, "qr_entry_v2::read_forecast_artifact");
  if (!window) return refuse<ForecastArtifact>(window.error());
  if (!valid_sha256(expected_sha256)) {
    return refuse<ForecastArtifact>(Refusal(
        RefusalCode::CONFIG, "qr_entry_v2::read_forecast_artifact",
        "pinned lowercase artifact SHA-256 is required"));
  }
  auto actual = sha256_file(forecast_path(config));
  if (!actual) return refuse<ForecastArtifact>(actual.error());
  if (actual.value() != expected_sha256) {
    return refuse<ForecastArtifact>(content_refusal(
        "qr_entry_v2::read_forecast_artifact", "forecast artifact hash mismatch"));
  }
  auto text = read_text(forecast_path(config));
  if (!text) return refuse<ForecastArtifact>(text.error());
  std::istringstream in(text.value());
  std::string line;
  const std::string expected_header =
      "# " + std::string(kForecastSchema) + " " + window_tag(config) +
      " asset=" + asset_name(config.asset) + " law_sha256=" +
      forecast_law_sha256();
  if (!std::getline(in, line) || line != expected_header ||
      !std::getline(in, line) || line != joined_columns()) {
    return refuse<ForecastArtifact>(content_refusal(
        "qr_entry_v2::read_forecast_artifact", "forecast schema/window mismatch"));
  }
  ForecastArtifact artifact;
  artifact.asset = config.asset;
  artifact.start_d8 = config.start_d8;
  artifact.end_d8_exclusive = config.end_d8_exclusive;
  artifact.law_sha256 = forecast_law_sha256();
  artifact.artifact_sha256 = actual.value();
  while (std::getline(in, line)) {
    if (line.empty()) continue;
    const auto f = split_tabs(line);
    if (f.size() != forecast_columns().size()) {
      return refuse<ForecastArtifact>(content_refusal(
          "qr_entry_v2::read_forecast_artifact", "forecast row width mismatch"));
    }
    ForecastRow row;
    row.asset = config.asset;
    auto segment = forecast_segment_from_name(f[2]);
    auto status = parse_status(f[3]);
    auto reason = parse_reason(f[4]);
    auto regime = parse_regime(f[26]);
    auto ladder = parse_ladder(f[27]);
    if (!segment) return refuse<ForecastArtifact>(segment.error());
    if (!status) return refuse<ForecastArtifact>(status.error());
    if (!reason) return refuse<ForecastArtifact>(reason.error());
    if (!regime) return refuse<ForecastArtifact>(regime.error());
    if (!ladder) return refuse<ForecastArtifact>(ladder.error());
    row.segment = segment.value();
    row.status = status.value();
    row.missing_reason = reason.value();
    row.regime = regime.value();
    row.ladder_source = ladder.value();
    if (f[0] != asset_name(config.asset) || !parse_int(f[1], &row.d8) ||
        !parse_int(f[5], &row.history_end_d8) ||
        !parse_int(f[6], &row.availability_ts_ns) ||
        !parse_int(f[7], &row.fit_month) ||
        !parse_int(f[8], &row.fit_end_range_d8) ||
        !parse_int(f[9], &row.fit_end_sigma_d8) ||
        !parse_int(f[10], &row.n_train_range) ||
        !parse_int(f[11], &row.rank_range) ||
        !parse_int(f[12], &row.n_train_sigma) ||
        !parse_int(f[13], &row.rank_sigma) ||
        !parse_double(f[14], &row.rv1_usd) ||
        !parse_double(f[15], &row.rv5_usd) ||
        !parse_double(f[16], &row.rv22_usd) ||
        !parse_double(f[17], &row.prior_parkinson_usd) ||
        !parse_double(f[18], &row.prior_gk_usd) ||
        !parse_double(f[19], &row.prior_rs_usd) ||
        !parse_double(f[20], &row.prior_jump_usd) ||
        !parse_double(f[21], &row.sigma_hat_usd) ||
        !parse_double(f[22], &row.range_hat_usd) ||
        !parse_double(f[23], &row.rv5_over_rv66) ||
        !parse_double(f[24], &row.regime_cut_lo) ||
        !parse_double(f[25], &row.regime_cut_hi) ||
        !parse_int(f[28], &row.n_calibration) ||
        !parse_int(f[29], &row.n_regime_calibration)) {
      return refuse<ForecastArtifact>(content_refusal(
          "qr_entry_v2::read_forecast_artifact", "invalid forecast scalar"));
    }
    std::size_t column = 30u;
    for (std::size_t q = 0; q < kForecastQuantiles.size(); ++q) {
      if (!parse_double(f[column++], &row.move_ratio[q]) ||
          !parse_double(f[column++], &row.move_usd[q])) {
        return refuse<ForecastArtifact>(content_refusal(
            "qr_entry_v2::read_forecast_artifact", "invalid move quantile"));
      }
    }
    for (std::size_t q = 0; q < kForecastQuantiles.size(); ++q) {
      if (!parse_double(f[column++], &row.regime_move_ratio[q]) ||
          !parse_double(f[column++], &row.regime_move_usd[q])) {
        return refuse<ForecastArtifact>(content_refusal(
            "qr_entry_v2::read_forecast_artifact", "invalid regime quantile"));
      }
    }
    row.phase_profile_sha256 = f[column++];
    row.model_sha256 = f[column++];
    row.history_source_sha256 = f[column++];
    row.lineage_sha256 = f[column++];
    if (column != f.size() || row.d8 < config.start_d8 ||
        row.d8 >= config.end_d8_exclusive || row.d8 >= kDevelopmentEndD8Exclusive ||
        row.history_end_d8 >= row.d8 || row.fit_month != row.d8 / 100 ||
        !valid_sha256(row.phase_profile_sha256) ||
        !valid_sha256(row.model_sha256) ||
        !valid_sha256(row.history_source_sha256) ||
        !valid_sha256(row.lineage_sha256) ||
        row.lineage_sha256 != forecast_row_lineage(row)) {
      return refuse<ForecastArtifact>(content_refusal(
          "qr_entry_v2::read_forecast_artifact",
          "forecast key/hash/lineage invariant failed", row.d8));
    }
    const bool design_finite = std::isfinite(row.rv1_usd) &&
        std::isfinite(row.rv5_usd) && std::isfinite(row.rv22_usd) &&
        std::isfinite(row.prior_parkinson_usd) &&
        std::isfinite(row.prior_gk_usd) && std::isfinite(row.prior_rs_usd) &&
        std::isfinite(row.prior_jump_usd);
    const std::int32_t fit_cutoff_d8 = row.fit_month * 100 + 1;
    if ((row.fit_end_range_d8 >= 0 &&
         row.fit_end_range_d8 >= fit_cutoff_d8) ||
        (row.fit_end_sigma_d8 >= 0 &&
         row.fit_end_sigma_d8 >= fit_cutoff_d8) ||
        row.n_calibration > kForecastCalibrationWindow ||
        row.n_regime_calibration > row.n_calibration) {
      return refuse<ForecastArtifact>(content_refusal(
          "qr_entry_v2::read_forecast_artifact",
          "monthly-fit/calibration causality invariant failed", row.d8));
    }
    if (row.status == ForecastStatus::READY) {
      if (row.missing_reason != ForecastMissingReason::NONE || !design_finite ||
          !std::isfinite(row.sigma_hat_usd) || !(row.sigma_hat_usd > 0.0) ||
          !std::isfinite(row.range_hat_usd) || !(row.range_hat_usd > 0.0) ||
          row.n_train_range < kForecastMinTrain ||
          row.n_train_sigma < kForecastMinTrain ||
          row.rank_range != kForecastFeatureCount ||
          row.rank_sigma != kForecastFeatureCount) {
        return refuse<ForecastArtifact>(content_refusal(
            "qr_entry_v2::read_forecast_artifact", "READY invariant failed", row.d8));
      }
    } else if (row.missing_reason == ForecastMissingReason::NONE ||
               std::isfinite(row.sigma_hat_usd) ||
               std::isfinite(row.range_hat_usd)) {
      return refuse<ForecastArtifact>(content_refusal(
          "qr_entry_v2::read_forecast_artifact", "MISSING invariant failed", row.d8));
    }
    if (row.ladder_source == ForecastLadderSource::MISSING) {
      if (!all_missing(row.move_ratio) || !all_missing(row.move_usd) ||
          !all_missing(row.regime_move_ratio) ||
          !all_missing(row.regime_move_usd) ||
          (row.status == ForecastStatus::READY &&
           row.n_calibration >= kForecastCalibrationMin)) {
        return refuse<ForecastArtifact>(content_refusal(
            "qr_entry_v2::read_forecast_artifact", "missing ladder has values", row.d8));
      }
    } else if (row.status != ForecastStatus::READY ||
               row.n_calibration < kForecastCalibrationMin ||
               !all_finite(row.move_ratio) || !all_finite(row.move_usd) ||
               !all_finite(row.regime_move_ratio) ||
               !all_finite(row.regime_move_usd) ||
               !positive_nondecreasing(row.move_ratio) ||
               !positive_nondecreasing(row.move_usd) ||
               !positive_nondecreasing(row.regime_move_ratio) ||
               !positive_nondecreasing(row.regime_move_usd) ||
               !exact_scaled(row.move_ratio, row.move_usd,
                             row.sigma_hat_usd) ||
               !exact_scaled(row.regime_move_ratio, row.regime_move_usd,
                             row.sigma_hat_usd) ||
               (row.ladder_source == ForecastLadderSource::REGIME &&
                (row.regime == ForecastRegime::NA ||
                 row.n_regime_calibration < kForecastCalibrationMin)) ||
               (row.ladder_source == ForecastLadderSource::UNSCALED_FALLBACK &&
                (row.regime_move_ratio != row.move_ratio ||
                 row.regime_move_usd != row.move_usd))) {
      return refuse<ForecastArtifact>(content_refusal(
          "qr_entry_v2::read_forecast_artifact", "ladder invariant failed", row.d8));
    }
    const bool have_regime_cuts = std::isfinite(row.regime_cut_lo) &&
                                  std::isfinite(row.regime_cut_hi);
    if ((row.regime == ForecastRegime::NA && have_regime_cuts &&
         std::isfinite(row.rv5_over_rv66)) ||
        (row.regime != ForecastRegime::NA &&
         (!have_regime_cuts || !std::isfinite(row.rv5_over_rv66) ||
          row.regime_cut_lo > row.regime_cut_hi))) {
      return refuse<ForecastArtifact>(content_refusal(
          "qr_entry_v2::read_forecast_artifact", "regime invariant failed",
          row.d8));
    }
    artifact.rows.push_back(std::move(row));
  }
  if (!std::is_sorted(artifact.rows.begin(), artifact.rows.end(),
                      [](const ForecastRow& lhs, const ForecastRow& rhs) {
                        return std::tie(lhs.d8, lhs.segment) <
                               std::tie(rhs.d8, rhs.segment);
                      })) {
    return refuse<ForecastArtifact>(Refusal(
        RefusalCode::OUT_OF_ORDER, "qr_entry_v2::read_forecast_artifact",
        "forecast rows are not in (d8,segment) order"));
  }
  auto locks = read_locks(config);
  if (!locks) return refuse<ForecastArtifact>(locks.error());
  if (artifact.rows.size() != locks.value().size() * kForecastSegmentCount) {
    return refuse<ForecastArtifact>(content_refusal(
        "qr_entry_v2::read_forecast_artifact", "forecast denominator mismatch"));
  }
  for (std::size_t i = 0; i < locks.value().size(); ++i) {
    for (std::size_t s = 0; s < kForecastSegmentCount; ++s) {
      const ForecastRow& row = artifact.rows[i * kForecastSegmentCount + s];
      const std::uint64_t expected_availability =
          static_cast<std::uint64_t>(locks.value()[i].open_utc) * 1'000'000'000ULL;
      if (row.d8 != locks.value()[i].d8 ||
          row.segment != static_cast<ForecastSegment>(s) ||
          row.availability_ts_ns != expected_availability) {
        return refuse<ForecastArtifact>(content_refusal(
            "qr_entry_v2::read_forecast_artifact",
            "row does not match actual locked session open", row.d8));
      }
    }
  }
  return artifact;
}

Expected<ForecastRow, Refusal> join_forecast(
    const ForecastArtifact& artifact, std::int32_t d8,
    ForecastSegment segment, std::uint64_t decision_ts_ns,
    const std::string& expected_artifact_sha256) {
  if (!valid_sha256(expected_artifact_sha256) ||
      expected_artifact_sha256 != artifact.artifact_sha256 ||
      artifact.law_sha256 != forecast_law_sha256()) {
    return refuse<ForecastRow>(Refusal(
        RefusalCode::CONFIG, "qr_entry_v2::join_forecast",
        "forecast join requires the exact artifact and model-law hashes"));
  }
  if (d8 < artifact.start_d8 || d8 >= artifact.end_d8_exclusive ||
      d8 >= kDevelopmentEndD8Exclusive) {
    return refuse<ForecastRow>(Refusal(
        RefusalCode::DAY_OUTSIDE_CALENDAR, "qr_entry_v2::join_forecast",
        "forecast key is outside the development artifact"));
  }
  const auto found = std::lower_bound(
      artifact.rows.begin(), artifact.rows.end(), std::make_tuple(d8, segment),
      [](const ForecastRow& row,
         const std::tuple<std::int32_t, ForecastSegment>& key) {
        return std::tie(row.d8, row.segment) < key;
      });
  if (found == artifact.rows.end() || found->d8 != d8 ||
      found->segment != segment) {
    return refuse<ForecastRow>(content_refusal(
        "qr_entry_v2::join_forecast", "exact forecast segment key is absent", d8));
  }
  if (found->availability_ts_ns >= decision_ts_ns) {
    return refuse<ForecastRow>(Refusal(
        RefusalCode::CLOCK_VIOLATION, "qr_entry_v2::join_forecast",
        "forecast availability must be strictly before decision"));
  }
  return *found;
}

}  // namespace qr::entry_v2
