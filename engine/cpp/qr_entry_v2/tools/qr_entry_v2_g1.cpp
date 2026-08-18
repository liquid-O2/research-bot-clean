#include <charconv>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <map>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "qr_entry_v2/g1.hpp"
#include "qr_futsess/constants.hpp"

namespace {

enum class CliStage {
  CANDIDATES,
  TEACHER,
  DEPLOYABLE_CEILING,
  MECHANICAL_CEILING,
  ARRIVAL,
  ALL,
};

void usage(const char* program) {
  std::fprintf(
      stderr,
      "usage: %s --stage candidates|teacher|deployable-ceiling|"
      "mechanical-ceiling|arrival|all --asset SI|HG|NKD|ALL\n"
      "  [--output-root PATH] [--start-d8 YYYYMMDD] "
      "[--end-d8-exclusive YYYYMMDD]\n"
      "  [--compliance-file FILE --compliance-sha256 SHA256]\n"
      "  [--threshold ASSET=USD ... --threshold-receipt-sha256 SHA256]\n"
      "\n"
      "candidates reads QRE2V2 locks/phases/QRE2EVT2 packs and writes receive-clock G1 rows.\n"
      "teacher reads those rows and writes the separate privileged certificate plane.\n"
      "deployable-ceiling excludes prohibited/unknown compliance; mechanical-ceiling\n"
      "is a diagnostics-only upper bound. arrival requires an explicit frozen threshold\n"
      "for every selected asset. all runs candidates, teacher, and both ceilings; it does\n"
      "not run arrival. A missing compliance artifact deliberately makes every candidate\n"
      "COMPLIANCE_UNKNOWN. Ordinary CLI is hard-confined to [%d,%d).\n",
      program, qr::entry_v2::kDevelopmentStartD8,
      qr::entry_v2::kDevelopmentEndD8Exclusive);
}

bool parse_d8(const char* text, std::int32_t* out) {
  const char* end = text + std::strlen(text);
  const auto parsed = std::from_chars(text, end, *out);
  return parsed.ec == std::errc{} && parsed.ptr == end;
}

bool parse_double(std::string_view text, double* out) {
  const char* begin = text.data();
  const char* end = begin + text.size();
  const auto parsed = std::from_chars(begin, end, *out);
  return parsed.ec == std::errc{} && parsed.ptr == end && std::isfinite(*out);
}

std::optional<CliStage> parse_stage(std::string_view name) {
  if (name == "candidates") return CliStage::CANDIDATES;
  if (name == "teacher") return CliStage::TEACHER;
  if (name == "deployable-ceiling") return CliStage::DEPLOYABLE_CEILING;
  if (name == "mechanical-ceiling") return CliStage::MECHANICAL_CEILING;
  if (name == "arrival") return CliStage::ARRIVAL;
  if (name == "all") return CliStage::ALL;
  return std::nullopt;
}

bool parse_threshold(std::string_view value,
                     qr::entry_v2::ArrivalThresholds* thresholds) {
  const std::size_t equal = value.find('=');
  if (equal == std::string_view::npos || equal == 0u || equal + 1u >= value.size()) {
    return false;
  }
  qr::futsess::Asset asset{};
  const std::string name(value.substr(0, equal));
  double amount = 0.0;
  if (!qr::futsess::asset_from_name(name, &asset) ||
      !parse_double(value.substr(equal + 1u), &amount) ||
      thresholds->min_value_usd.contains(asset)) {
    return false;
  }
  thresholds->min_value_usd.emplace(asset, amount);
  return true;
}

bool build_configs(const std::string& asset_name,
                   const qr::entry_v2::Config& base,
                   std::vector<qr::entry_v2::Config>* configs) {
  if (asset_name == "ALL") {
    for (qr::futsess::Asset asset : {qr::futsess::Asset::SI,
                                     qr::futsess::Asset::HG,
                                     qr::futsess::Asset::NKD}) {
      qr::entry_v2::Config config = base;
      config.asset = asset;
      configs->push_back(std::move(config));
    }
    return true;
  }
  qr::entry_v2::Config config = base;
  if (!qr::futsess::asset_from_name(asset_name, &config.asset)) return false;
  configs->push_back(std::move(config));
  return true;
}

void print_stats(std::string_view stage, const qr::entry_v2::Config& config,
                 const qr::entry_v2::G1BuildStats& stats) {
  std::printf(
      "stage\t%.*s\nasset\t%s\nstart_d8\t%d\nend_d8_exclusive\t%d\n"
      "sessions\t%llu\nno_candidate_sessions\t%llu\ncandidates\t%llu\n"
      "teacher_ready\t%llu\nteacher_refused\t%llu\nmanifest_sha256\t%s\n"
      "receipt_sha256\t%s\n",
      static_cast<int>(stage.size()), stage.data(),
      qr::futsess::asset_spec(config.asset).name, config.start_d8,
      config.end_d8_exclusive,
      static_cast<unsigned long long>(stats.sessions),
      static_cast<unsigned long long>(stats.no_candidate_sessions),
      static_cast<unsigned long long>(stats.candidates),
      static_cast<unsigned long long>(stats.teacher_ready),
      static_cast<unsigned long long>(stats.teacher_refused),
      stats.manifest_sha256.c_str(), stats.receipt_sha256.c_str());
}

int refusal(const qr::Refusal& error) {
  std::fprintf(stderr, "REFUSED: %s\n", error.message().c_str());
  return 1;
}

}  // namespace

int main(int argc, char** argv) {
  qr::entry_v2::Config base;
  qr::entry_v2::ArrivalThresholds thresholds;
  std::string stage_name;
  std::string asset_name;
  std::string compliance_file;
  std::string compliance_sha256;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    const auto need = [&](const char* option) -> const char* {
      if (i + 1 >= argc) {
        std::fprintf(stderr, "missing value after %s\n", option);
        return nullptr;
      }
      return argv[++i];
    };
    if (arg == "--stage") {
      const char* value = need("--stage");
      if (value == nullptr) return 2;
      stage_name = value;
    } else if (arg == "--asset") {
      const char* value = need("--asset");
      if (value == nullptr) return 2;
      asset_name = value;
    } else if (arg == "--output-root") {
      const char* value = need("--output-root");
      if (value == nullptr) return 2;
      base.output_root = value;
    } else if (arg == "--start-d8") {
      const char* value = need("--start-d8");
      if (value == nullptr || !parse_d8(value, &base.start_d8)) {
        std::fprintf(stderr, "invalid --start-d8\n");
        return 2;
      }
    } else if (arg == "--end-d8-exclusive") {
      const char* value = need("--end-d8-exclusive");
      if (value == nullptr || !parse_d8(value, &base.end_d8_exclusive)) {
        std::fprintf(stderr, "invalid --end-d8-exclusive\n");
        return 2;
      }
    } else if (arg == "--compliance-file") {
      const char* value = need("--compliance-file");
      if (value == nullptr) return 2;
      compliance_file = value;
    } else if (arg == "--compliance-sha256") {
      const char* value = need("--compliance-sha256");
      if (value == nullptr) return 2;
      compliance_sha256 = value;
    } else if (arg == "--threshold") {
      const char* value = need("--threshold");
      if (value == nullptr || !parse_threshold(value, &thresholds)) {
        std::fprintf(stderr, "invalid or duplicate --threshold; use ASSET=USD\n");
        return 2;
      }
    } else if (arg == "--threshold-receipt-sha256") {
      const char* value = need("--threshold-receipt-sha256");
      if (value == nullptr) return 2;
      thresholds.threshold_receipt_sha256 = value;
    } else if (arg == "--help" || arg == "-h") {
      usage(argv[0]);
      return 0;
    } else {
      std::fprintf(stderr, "unknown argument: %s\n", arg.c_str());
      usage(argv[0]);
      return 2;
    }
  }

  const auto stage = parse_stage(stage_name);
  std::vector<qr::entry_v2::Config> configs;
  if (!stage || !build_configs(asset_name, base, &configs)) {
    usage(argv[0]);
    return 2;
  }
  if (compliance_file.empty() != compliance_sha256.empty()) {
    std::fprintf(stderr, "--compliance-file and --compliance-sha256 are a pair\n");
    return 2;
  }
  const bool candidate_stage = *stage == CliStage::CANDIDATES || *stage == CliStage::ALL;
  if (!candidate_stage && !compliance_file.empty()) {
    std::fprintf(stderr, "compliance input is consumed only by candidates/all\n");
    return 2;
  }
  if (*stage != CliStage::ARRIVAL &&
      (!thresholds.min_value_usd.empty() ||
       !thresholds.threshold_receipt_sha256.empty())) {
    std::fprintf(stderr, "threshold inputs are consumed only by arrival\n");
    return 2;
  }

  std::optional<qr::entry_v2::ComplianceCalendar> compliance;
  if (!compliance_file.empty()) {
    auto loaded = qr::entry_v2::load_compliance_calendar(
        compliance_file, compliance_sha256);
    if (!loaded) return refusal(loaded.error());
    compliance = std::move(loaded).value();
  }

  if (*stage == CliStage::CANDIDATES || *stage == CliStage::ALL) {
    for (const auto& config : configs) {
      auto result = qr::entry_v2::build_g1_candidate_artifacts(
          config, compliance ? &*compliance : nullptr);
      if (!result) return refusal(result.error());
      print_stats("candidates", config, result.value());
    }
  }
  if (*stage == CliStage::TEACHER || *stage == CliStage::ALL) {
    for (const auto& config : configs) {
      auto result = qr::entry_v2::build_g1_teacher_artifacts(config);
      if (!result) return refusal(result.error());
      print_stats("teacher", config, result.value());
    }
  }

  const auto schedule = [&](bool arrival,
                            qr::entry_v2::ScheduleUniverse universe,
                            std::string_view label,
                            const qr::entry_v2::ArrivalThresholds* frozen) {
    auto result = qr::entry_v2::build_g1_schedule_artifact(
        configs, arrival, universe, frozen);
    if (!result) return refusal(result.error());
    print_stats(label, configs.front(), result.value());
    return 0;
  };
  if (*stage == CliStage::DEPLOYABLE_CEILING || *stage == CliStage::ALL) {
    const int status = schedule(
        false, qr::entry_v2::ScheduleUniverse::DEPLOYABLE_CLEAR_ONLY,
        "deployable-ceiling", nullptr);
    if (status != 0) return status;
  }
  if (*stage == CliStage::MECHANICAL_CEILING || *stage == CliStage::ALL) {
    const int status = schedule(
        false, qr::entry_v2::ScheduleUniverse::MECHANICAL_ALL,
        "mechanical-ceiling", nullptr);
    if (status != 0) return status;
  }
  if (*stage == CliStage::ARRIVAL) {
    return schedule(true,
                    qr::entry_v2::ScheduleUniverse::DEPLOYABLE_CLEAR_ONLY,
                    "arrival", &thresholds);
  }
  return 0;
}
