#include <cstdio>
#include <charconv>
#include <cstring>
#include <fstream>
#include <string>
#include <vector>

#include "qr_entry_v2/substrate.hpp"
#include "qr_futsess/constants.hpp"

namespace {

void usage(const char* program) {
  std::fprintf(
      stderr,
      "usage: %s --stage tally|lock|phase|events|all --asset SI|HG|NKD "
      "[--output-root PATH] [--start-d8 YYYYMMDD] "
      "[--end-d8-exclusive YYYYMMDD] [--input FILE ...] [--input-list FILE]\n"
      "\n"
      "default output root: %s\n"
      "default record window: [%d,%d); ordinary CLI cannot exceed 20250701.\n"
      "input-list rows are exactly PATH<TAB>PROVIDER_SHA256<TAB>ACCESS, "
      "where ACCESS is DEVELOPMENT or DEVELOPMENT_PREFIX.\n",
      program, qr::entry_v2::kDefaultOutputRoot, qr::entry_v2::kDevelopmentStartD8,
      qr::entry_v2::kDevelopmentEndD8Exclusive);
}

bool load_input_list(const std::string& path, qr::entry_v2::Config* config) {
  std::ifstream in(path);
  if (!in) {
    return false;
  }
  std::string line;
  while (std::getline(in, line)) {
    if (!line.empty() && line.back() == '\r') {
      line.pop_back();
    }
    if (!line.empty() && line[0] != '#') {
      const std::size_t tab1 = line.find('\t');
      const std::size_t tab2 =
          tab1 == std::string::npos ? std::string::npos : line.find('\t', tab1 + 1u);
      const std::string payload = line.substr(0, tab1);
      const std::string access =
          tab2 == std::string::npos ? std::string{} : line.substr(tab2 + 1u);
      if (payload.empty() || tab1 == std::string::npos || tab2 == std::string::npos ||
          line.find('\t', tab2 + 1u) != std::string::npos ||
          (access != "DEVELOPMENT" && access != "DEVELOPMENT_PREFIX")) {
        return false;
      }
      config->inputs.push_back(payload);
      config->development_input_sha256[payload] =
          line.substr(tab1 + 1u, tab2 - tab1 - 1u);
      if (access == "DEVELOPMENT_PREFIX") {
        config->development_prefix_inputs.insert(payload);
      }
    }
  }
  return in.eof();
}

bool parse_d8(const char* text, std::int32_t* out) {
  const char* end = text + std::strlen(text);
  const auto parsed = std::from_chars(text, end, *out);
  return parsed.ec == std::errc{} && parsed.ptr == end;
}

}  // namespace

int main(int argc, char** argv) {
  qr::entry_v2::Config config;
  std::string stage_name;
  std::string asset_name;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    const auto need = [&](const char* option) -> const char* {
      if (i + 1 >= argc) {
        std::fprintf(stderr, "missing value after %s\n", option);
        return nullptr;
      }
      ++i;
      return argv[i];
    };
    if (arg == "--stage") {
      const char* value = need("--stage");
      if (value == nullptr) {
        return 2;
      }
      stage_name = value;
    } else if (arg == "--asset") {
      const char* value = need("--asset");
      if (value == nullptr) {
        return 2;
      }
      asset_name = value;
    } else if (arg == "--output-root") {
      const char* value = need("--output-root");
      if (value == nullptr) {
        return 2;
      }
      config.output_root = value;
    } else if (arg == "--start-d8") {
      const char* value = need("--start-d8");
      if (value == nullptr || !parse_d8(value, &config.start_d8)) {
        std::fprintf(stderr, "invalid --start-d8\n");
        return 2;
      }
    } else if (arg == "--end-d8-exclusive") {
      const char* value = need("--end-d8-exclusive");
      if (value == nullptr || !parse_d8(value, &config.end_d8_exclusive)) {
        std::fprintf(stderr, "invalid --end-d8-exclusive\n");
        return 2;
      }
    } else if (arg == "--input") {
      const char* value = need("--input");
      if (value == nullptr) {
        return 2;
      }
      config.inputs.emplace_back(value);
    } else if (arg == "--input-list") {
      const char* value = need("--input-list");
      if (value == nullptr || !load_input_list(value, &config)) {
        std::fprintf(stderr, "cannot read --input-list\n");
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
  if (stage_name.empty() || asset_name.empty() ||
      !qr::futsess::asset_from_name(asset_name, &config.asset)) {
    usage(argv[0]);
    return 2;
  }
  auto stage = qr::entry_v2::stage_from_name(stage_name);
  if (!stage) {
    std::fprintf(stderr, "REFUSED: %s\n", stage.error().message().c_str());
    return 2;
  }
  auto result = qr::entry_v2::run(config, stage.value());
  if (!result) {
    std::fprintf(stderr, "REFUSED: %s\n", result.error().message().c_str());
    return 1;
  }
  const qr::entry_v2::StageStats& stats = result.value();
  std::printf("stage\t%s\nasset\t%s\nstart_d8\t%d\nend_d8_exclusive\t%d\n"
              "rows\t%llu\nrecords\t%llu\ntyped_refusals\t%llu\n"
              "content_hashed_inputs\t%llu\ntrusted_hash_inputs\t%llu\n"
              "raw_records\t%llu\ntrusted_economic_records\t%llu\n"
              "snapshot_records\t%llu\nstandalone_bad_ts_recv_records\t%llu\n"
              "maybe_bad_book_records\t%llu\noutput_sha256\t%s\nreceipt_sha256\t%s\n",
              stage_name.c_str(), asset_name.c_str(), config.start_d8,
              config.end_d8_exclusive,
              static_cast<unsigned long long>(stats.rows),
              static_cast<unsigned long long>(stats.records),
              static_cast<unsigned long long>(stats.refusals),
              static_cast<unsigned long long>(stats.content_hashed_inputs),
              static_cast<unsigned long long>(stats.trusted_hash_inputs),
              static_cast<unsigned long long>(stats.raw_records),
              static_cast<unsigned long long>(stats.trusted_economic_records),
              static_cast<unsigned long long>(stats.snapshot_records),
              static_cast<unsigned long long>(stats.standalone_bad_ts_recv_records),
              static_cast<unsigned long long>(stats.maybe_bad_book_records),
              stats.output_sha256.c_str(),
              stats.receipt_sha256.c_str());
  return 0;
}
