// qr_w21_census — the W2.1 constructor's CENSUS AUDIT run (D-006: "a
// constructor is built only with spec + red-first fixture proof + census
// audit").
//
// SPEC: FINAL_PLAN APPENDIX A2 as amended by design/DESIGN_FEATURES.md
// §W21-PIN-1. The scope wall fires first: every ordinal goes through
// `DayScope::admit`, and ordinals 125..208 return the typed MODALITY_ABSENT
// block without a path ever being formed (Q12).
//
// usage: qr_w21_census --root DIR --prints DIR --tapes DIR --out TSV [--ordinals LIST]
// Output carries no wall-clock value, so two runs are byte-identical.
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#include "qr_registry/registry.hpp"
#include "qr_w21/surface.hpp"

namespace {

/// The declared ladder, unchanged from the W2.0 dossier runs so the two
/// censuses describe the same sessions: 125 + 50k (k=0..12), the flat->shard
/// era pair {646,647} FINAL_PLAN section 6 names, and the last scoped session.
constexpr std::array<std::int64_t, 16> kLadder{125, 175, 225, 275, 325, 375, 425, 475,
                                               525, 575, 625, 646, 647, 675, 725, 749};

const qr::Registry* registry_or_null() {
  static qr::Expected<qr::Registry, qr::Refusal> loaded = qr::Registry::load_embedded();
  return loaded.has_value() ? &loaded.value() : nullptr;
}

int usage() {
  std::fprintf(stderr,
               "usage: qr_w21_census --root DIR --prints DIR --tapes DIR --out TSV\n"
               "                     [--ordinals LIST|ladder]\n");
  return 2;
}

std::vector<std::int64_t> parse_ordinals(const std::string& text) {
  std::vector<std::int64_t> out;
  if (text.empty() || text == "ladder") {
    out.assign(kLadder.begin(), kLadder.end());
    return out;
  }
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

}  // namespace

int main(int argc, char** argv) {
  std::string root;
  std::string prints;
  std::string tapes;
  std::string out;
  std::string ordinals_text = "ladder";
  for (int index = 1; index < argc; ++index) {
    const std::string flag = argv[index];
    if (flag == "--root" && index + 1 < argc) {
      root = argv[++index];
    } else if (flag == "--prints" && index + 1 < argc) {
      prints = argv[++index];
    } else if (flag == "--tapes" && index + 1 < argc) {
      tapes = argv[++index];
    } else if (flag == "--out" && index + 1 < argc) {
      out = argv[++index];
    } else if (flag == "--ordinals" && index + 1 < argc) {
      ordinals_text = argv[++index];
    } else {
      return usage();
    }
  }
  if (root.empty() || prints.empty() || tapes.empty() || out.empty()) return usage();

  const qr::Registry* const registry = registry_or_null();
  if (registry == nullptr) {
    std::fprintf(stderr, "the embedded registry refused to load\n");
    return 1;
  }
  qr::w20::CensusReport report;
  for (const std::int64_t ordinal : parse_ordinals(ordinals_text)) {
    const auto scope = qr::DayScope::admit(*registry, ordinal);
    if (!scope.has_value()) {
      std::fprintf(stderr, "REFUSED: %s\n", scope.error().message().c_str());
      return 1;
    }
    char padded[16];
    std::snprintf(padded, sizeof(padded), "s%04lld", static_cast<long long>(ordinal));
    const std::filesystem::path tape_side_dir = std::filesystem::path(tapes) / padded / "L";
    qr::w21::SurfaceOptions options;
    options.prints_root = std::filesystem::path(prints);
    const auto built = qr::w21::SurfaceBuilder::build(scope.value(), std::filesystem::path(root),
                                                      tape_side_dir, options);
    if (!built.has_value()) {
      std::fprintf(stderr, "REFUSED s%lld: %s\n", static_cast<long long>(ordinal),
                   built.error().message().c_str());
      return 1;
    }
    emit(report, ordinal, scope.value().day(), built.value());
    std::fprintf(stderr, "done s%lld rows=%lld valid_bucket_seconds=%lld\n",
                 static_cast<long long>(ordinal), static_cast<long long>(built.value().rth_rows()),
                 static_cast<long long>(built.value().valid_bucket_seconds()));
  }
  const auto written = report.write(out);
  if (!written.has_value()) {
    std::fprintf(stderr, "REFUSED: %s\n", written.error().message().c_str());
    return 1;
  }
  return 0;
}
