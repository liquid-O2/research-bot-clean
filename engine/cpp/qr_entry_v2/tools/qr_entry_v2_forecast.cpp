#include <charconv>
#include <cstdio>
#include <cstring>
#include <string>
#include <utility>
#include <vector>

#include "qr_entry_v2/forecast.hpp"
#include "qr_futsess/constants.hpp"

namespace {

void usage(const char* program) {
  std::fprintf(
      stderr,
      "usage: %s --asset SI|HG|NKD|ALL [--output-root PATH] "
      "[--start-d8 YYYYMMDD] [--end-d8-exclusive YYYYMMDD]\n"
      "\n"
      "Builds the isolated QRE2FORECAST4 observation plane from existing "
      "QRE2 locks, phase schedules, event manifest, and exact event packs.\n"
      "Outputs: <root>/forecast/<ASSET>.qrf4.tsv, .qrf4.eval.tsv, and "
      ".qrf4.json.  The eval sidecar is diagnostics-only hindsight data.\n"
      "Ordinary CLI is hard-confined to [%d,%d); it cannot open 2025H2.\n",
      program, qr::entry_v2::kDevelopmentStartD8,
      qr::entry_v2::kDevelopmentEndD8Exclusive);
}

bool parse_d8(const char* text, std::int32_t* out) {
  const char* end = text + std::strlen(text);
  const auto parsed = std::from_chars(text, end, *out);
  return parsed.ec == std::errc{} && parsed.ptr == end;
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

}  // namespace

int main(int argc, char** argv) {
  qr::entry_v2::Config base;
  std::string asset_name;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    const auto need = [&](const char* option) -> const char* {
      if (i + 1 >= argc) {
        std::fprintf(stderr, "missing value after %s\n", option);
        return nullptr;
      }
      return argv[++i];
    };
    if (arg == "--asset") {
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
    } else if (arg == "--help" || arg == "-h") {
      usage(argv[0]);
      return 0;
    } else {
      std::fprintf(stderr, "unknown argument: %s\n", arg.c_str());
      usage(argv[0]);
      return 2;
    }
  }

  std::vector<qr::entry_v2::Config> configs;
  if (!build_configs(asset_name, base, &configs)) {
    usage(argv[0]);
    return 2;
  }
  for (const qr::entry_v2::Config& config : configs) {
    auto result = qr::entry_v2::build_forecast_artifact(config);
    if (!result) {
      std::fprintf(stderr, "REFUSED: %s\n", result.error().message().c_str());
      return 1;
    }
    const qr::entry_v2::ForecastBuildStats& stats = result.value();
    std::printf(
        "asset\t%s\nstart_d8\t%d\nend_d8_exclusive\t%d\nsessions\t%llu\n"
        "rows\t%llu\nready\t%llu\nmissing\t%llu\nevaluation_rows\t%llu\n"
        "evaluation_valid\t%llu\noutput_sha256\t%s\n"
        "evaluation_output_sha256\t%s\nreceipt_sha256\t%s\n",
        qr::futsess::asset_spec(config.asset).name, config.start_d8,
        config.end_d8_exclusive,
        static_cast<unsigned long long>(stats.sessions),
        static_cast<unsigned long long>(stats.rows),
        static_cast<unsigned long long>(stats.ready),
        static_cast<unsigned long long>(stats.missing),
        static_cast<unsigned long long>(stats.evaluation_rows),
        static_cast<unsigned long long>(stats.evaluation_valid),
        stats.output_sha256.c_str(), stats.evaluation_output_sha256.c_str(),
        stats.receipt_sha256.c_str());
  }
  return 0;
}
