// qr_ivx_colvalues — THE CC-013 VALUE CENSUS RUN (the amendment's second half).
//
// `qr_ivx_columns` read the parquet FOOTER while the columns were still walled
// and authorized the amendment. This binary reads the same five sessions
// through `qr::sources::OptionPrintReader`, which now projects all eleven, and
// publishes the exact distribution of the DECODED values beside the four
// already-projected greeks as a reference.
//
// usage: qr_ivx_colvalues --prints DIR --out TSV --ordinals LIST [--rutw]
//
// `--rutw` drives the B5 reader instead, so "same laws" is checked on the
// values and not only on the spec asserts.
#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <utility>
#include <vector>

#include "qr_ivx/column_values.hpp"
#include "qr_ivx/tsv.hpp"
#include "qr_registry/registry.hpp"
#include "qr_sources/option_prints.hpp"
#include "qr_sources/rutw_prints.hpp"

namespace {

int usage() {
  std::fprintf(stderr,
               "usage: qr_ivx_colvalues --prints DIR --out TSV --ordinals LIST [--rutw]\n");
  return 2;
}

std::vector<std::int64_t> parse_ordinals(const std::string& text) {
  std::vector<std::int64_t> out;
  std::size_t start = 0;
  while (start <= text.size()) {
    const std::size_t comma = text.find(',', start);
    const std::string token =
        text.substr(start, comma == std::string::npos ? std::string::npos : comma - start);
    if (!token.empty()) out.push_back(std::strtoll(token.c_str(), nullptr, 10));
    if (comma == std::string::npos) break;
    start = comma + 1;
  }
  return out;
}

template <class Reader>
bool run_tape(Reader reader, qr::ivx::Cc013ValueCensus& census) {
  typename Reader::Group group;
  for (;;) {
    const auto more = reader.next_group(group);
    if (!more.has_value()) {
      std::fprintf(stderr, "REFUSED: %s\n", more.error().refusal().message().c_str());
      return false;
    }
    if (!more.value()) break;
    for (const qr::sources::OptionPrintRow& row : group.rows) {
      census.observe(row);
    }
  }
  return true;
}

}  // namespace

int main(int argc, char** argv) {
  std::string prints;
  std::string out_path;
  std::string ordinals_text;
  bool rutw = false;
  for (int index = 1; index < argc; ++index) {
    const std::string flag = argv[index];
    if (flag == "--rutw") {
      rutw = true;
      continue;
    }
    if (index + 1 >= argc) return usage();
    const std::string value = argv[++index];
    if (flag == "--prints") {
      prints = value;
    } else if (flag == "--out") {
      out_path = value;
    } else if (flag == "--ordinals") {
      ordinals_text = value;
    } else {
      return usage();
    }
  }
  if (prints.empty() || out_path.empty() || ordinals_text.empty()) return usage();

  auto registry = qr::Registry::load_embedded();
  if (!registry.has_value()) {
    std::fprintf(stderr, "the embedded registry refused to load\n");
    return 1;
  }

  qr::ivx::Report report;
  report.text("run", "spec", "charter", "design/DESIGN_FEATURES.md#CC-013 (LANDED)");
  report.text("run", "spec", "path", "READER_PATH_DECODED_VALUES");
  report.text("run", "spec", "tape", rutw ? "RUTW" : "IWM");

  for (const std::int64_t ordinal : parse_ordinals(ordinals_text)) {
    const auto scope = qr::DayScope::admit(registry.value(), ordinal);
    if (!scope.has_value()) {
      std::fprintf(stderr, "REFUSED: %s\n", scope.error().message().c_str());
      return 1;
    }
    qr::ivx::Cc013ValueCensus census;
    if (rutw) {
      auto opened =
          qr::sources::RutwPrintReader::open(scope.value(), std::filesystem::path(prints));
      if (!opened.has_value()) {
        std::fprintf(stderr, "REFUSED s%lld: %s\n", static_cast<long long>(ordinal),
                     opened.error().refusal().message().c_str());
        return 1;
      }
      if (!run_tape(std::move(opened).value(), census)) return 1;
    } else {
      auto opened =
          qr::sources::OptionPrintReader::open(scope.value(), std::filesystem::path(prints));
      if (!opened.has_value()) {
        std::fprintf(stderr, "REFUSED s%lld: %s\n", static_cast<long long>(ordinal),
                     opened.error().refusal().message().c_str());
        return 1;
      }
      if (!run_tape(std::move(opened).value(), census)) return 1;
    }
    const std::string key = "s" + std::to_string(ordinal) + "/" + (rutw ? "RUTW" : "IWM");
    report.text("session", key, "day", scope.value().day());
    report.metric("session", key, "rth_rows", census.rows());
    emit(report, key, census.finish());
    std::fprintf(stderr, "done s%lld rows=%lld\n", static_cast<long long>(ordinal),
                 static_cast<long long>(census.rows()));
  }

  const auto written = report.write(out_path);
  if (!written.has_value()) {
    std::fprintf(stderr, "REFUSED: %s\n", written.error().message().c_str());
    return 1;
  }
  return 0;
}
