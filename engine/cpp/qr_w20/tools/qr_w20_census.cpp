// qr_w20_census — the W2.0 dossier census runs (D3 option prints, D4 option
// quotes).
//
// SPEC: FINAL_PLAN section 10 W2.0 (dossiers are census-driven and censuses come
// FIRST), APPENDIX B3/B4 (the projected columns), APPENDIX B7 (never opened).
//
// THE WALL IS THE FIRST THING THIS BINARY DOES with any ordinal: every mode
// goes through `DayScope::admit`, which refuses outside 125..749 BEFORE a path
// exists. There is no code path here that forms a corpus path from a raw
// ordinal or a raw day string.
//
// A binary rather than a ctest case, for the reason WP3/WP4/WP5 established:
// one option-quote session is 27M-148M rows.
//
// usage:
//   qr_w20_census coverage --root DIR --out TSV
//   qr_w20_census dialect  --root DIR --out TSV [--ordinals LIST]
//   qr_w20_census quotes   --root DIR --out TSV --ordinals LIST [--tapes DIR]
//   qr_w20_census prints   --root DIR --out TSV --ordinals LIST [--tapes DIR]
//
// --ordinals accepts a comma list or `ladder` (the declared arithmetic set,
// below). Output carries no wall-clock value, so two runs are byte-identical.
#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "qr_registry/registry.hpp"
#include "qr_w20/mechanics.hpp"

namespace {

/// THE DECLARED SESSION SET, fixed before any census ran and derived by ordinal
/// arithmetic only (never by hash, name, size or "interesting" content — the
/// repository law forbids choosing scientific membership that way):
///   * 125 + 50k for k = 0..12  — an even sweep of the whole 625-session scope;
///   * 749                      — the last scoped session;
///   * 646 and 647              — the option-quote flat -> shard era boundary
///                                pair FINAL_PLAN section 6 already names.
constexpr std::array<std::int64_t, 16> kLadder{125, 175, 225, 275, 325, 375, 425, 475,
                                               525, 575, 625, 646, 647, 675, 725, 749};

const qr::Registry* registry_or_null() {
  static qr::Expected<qr::Registry, qr::Refusal> loaded = qr::Registry::load_embedded();
  return loaded.has_value() ? &loaded.value() : nullptr;
}

int usage() {
  std::fprintf(stderr,
               "usage: qr_w20_census <coverage|dialect|quotes|prints> --root DIR --out TSV\n"
               "                     [--ordinals 125,175,... | ladder] [--tapes DIR]\n");
  return 2;
}

std::vector<std::int64_t> parse_ordinals(const std::string& text) {
  std::vector<std::int64_t> out;
  if (text.empty() || text == "ladder") {
    out.assign(kLadder.begin(), kLadder.end());
    return out;
  }
  if (text == "all") {
    for (std::int64_t ordinal = qr::kScopeFirstOrdinal; ordinal <= qr::kScopeLastOrdinal;
         ++ordinal) {
      out.push_back(ordinal);
    }
    return out;
  }
  std::size_t start = 0;
  while (start <= text.size()) {
    const std::size_t comma = text.find(',', start);
    const std::string token =
        text.substr(start, comma == std::string::npos ? std::string::npos : comma - start);
    if (!token.empty()) {
      out.push_back(std::strtoll(token.c_str(), nullptr, 10));
    }
    if (comma == std::string::npos) break;
    start = comma + 1;
  }
  return out;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) {
    return usage();
  }
  const std::string mode = argv[1];
  std::string root;
  std::string out;
  std::string tapes;
  std::string ordinals_text = "ladder";
  for (int index = 2; index < argc; ++index) {
    const std::string flag = argv[index];
    if (flag == "--root" && index + 1 < argc) {
      root = argv[++index];
    } else if (flag == "--out" && index + 1 < argc) {
      out = argv[++index];
    } else if (flag == "--tapes" && index + 1 < argc) {
      tapes = argv[++index];
    } else if (flag == "--ordinals" && index + 1 < argc) {
      ordinals_text = argv[++index];
    } else {
      return usage();
    }
  }
  if (root.empty() || out.empty()) {
    return usage();
  }
  const qr::Registry* const registry = registry_or_null();
  if (registry == nullptr) {
    std::fprintf(stderr, "the embedded registry refused to load\n");
    return 1;
  }
  const std::filesystem::path corpus_root(root);
  qr::w20::CensusReport report;

  if (mode == "coverage") {
    std::array<std::int64_t, 3> era_counts{};
    std::array<std::int64_t, 3> era_bytes{};
    std::int64_t first_covered = -1;
    std::int64_t last_absent = -1;
    for (std::int64_t ordinal = qr::kScopeFirstOrdinal; ordinal <= qr::kScopeLastOrdinal;
         ++ordinal) {
      const auto scope = qr::DayScope::admit(*registry, ordinal);
      if (!scope.has_value()) {
        std::fprintf(stderr, "REFUSED: %s\n", scope.error().message().c_str());
        return 1;
      }
      const auto row = qr::w20::coverage_of(scope.value(), corpus_root);
      if (!row.has_value()) {
        std::fprintf(stderr, "REFUSED: %s\n", row.error().message().c_str());
        return 1;
      }
      const std::string key = "s" + std::to_string(ordinal);
      report.text("session", key, "day", row.value().day);
      report.text("session", key, "era", qr::w20::era_name(row.value().era));
      report.metric("session", key, "shards", row.value().shard_count);
      report.metric("session", key, "bytes", row.value().bytes);
      const auto slot = static_cast<std::size_t>(row.value().era);
      ++era_counts[slot];
      era_bytes[slot] += row.value().bytes;
      if (row.value().era == qr::w20::Era::ABSENT) {
        last_absent = ordinal;
      } else if (first_covered < 0) {
        first_covered = ordinal;
      }
    }
    for (std::size_t slot = 0; slot < era_counts.size(); ++slot) {
      const auto era = static_cast<qr::w20::Era>(slot);
      report.metric("total", qr::w20::era_name(era), "sessions", era_counts[slot]);
      report.metric("total", qr::w20::era_name(era), "bytes", era_bytes[slot]);
    }
    report.metric("total", "coverage", "first_covered_ordinal", first_covered);
    report.metric("total", "coverage", "last_absent_ordinal", last_absent);
    report.metric("total", "coverage", "scoped_sessions",
                  qr::kScopeLastOrdinal - qr::kScopeFirstOrdinal + 1);
  } else if (mode == "dialect") {
    for (const std::int64_t ordinal : parse_ordinals(ordinals_text)) {
      const auto scope = qr::DayScope::admit(*registry, ordinal);
      if (!scope.has_value()) {
        std::fprintf(stderr, "REFUSED: %s\n", scope.error().message().c_str());
        return 1;
      }
      const std::string key = "s" + std::to_string(ordinal);
      const auto rows = qr::w20::option_quote_dialect(scope.value(), corpus_root);
      if (!rows.has_value()) {
        // MODALITY_ABSENT is a RESULT of the dialect census, not a failure of it.
        if (rows.error().code() == qr::RefusalCode::MODALITY_ABSENT) {
          report.text("dialect", key, "day", scope.value().day());
          report.text("dialect", key, "state", "MODALITY_ABSENT");
          continue;
        }
        std::fprintf(stderr, "REFUSED: %s\n", rows.error().message().c_str());
        return 1;
      }
      report.text("dialect", key, "day", scope.value().day());
      report.metric("dialect", key, "shards", static_cast<std::int64_t>(rows.value().size()));
      for (const qr::w20::DialectRow& row : rows.value()) {
        const std::string shard_key = key + "/" + row.shard;
        report.metric("dialect_shard", shard_key, "file_rows", row.file_rows);
        report.metric("dialect_shard", shard_key, "row_groups", row.row_groups);
        static constexpr std::array<const char*, 8> kNames{
            "expiration", "strike", "right", "timestamp", "bid_size", "bid", "ask_size", "ask"};
        for (std::size_t slot = 0; slot < kNames.size(); ++slot) {
          report.metric("dialect_shard", shard_key, std::string("form_") + kNames[slot],
                        static_cast<std::int64_t>(row.forms[slot]));
        }
      }
    }
  } else if (mode == "quotes" || mode == "prints") {
    for (const std::int64_t ordinal : parse_ordinals(ordinals_text)) {
      const auto scope = qr::DayScope::admit(*registry, ordinal);
      if (!scope.has_value()) {
        std::fprintf(stderr, "REFUSED: %s\n", scope.error().message().c_str());
        return 1;
      }
      std::filesystem::path tape_side_dir;
      if (!tapes.empty()) {
        char padded[16];
        std::snprintf(padded, sizeof(padded), "s%04lld", static_cast<long long>(ordinal));
        tape_side_dir = std::filesystem::path(tapes) / padded / "L";
      }
      if (mode == "quotes") {
        const auto census =
            qr::w20::census_option_quotes(scope.value(), corpus_root, tape_side_dir);
        if (!census.has_value()) {
          std::fprintf(stderr, "REFUSED: %s\n", census.error().message().c_str());
          return 1;
        }
        emit(report, census.value());
        std::fprintf(stderr, "done s%lld rows=%lld\n", static_cast<long long>(ordinal),
                     static_cast<long long>(census.value().rth_rows));
      } else {
        const auto census =
            qr::w20::census_option_prints(scope.value(), corpus_root, tape_side_dir);
        if (!census.has_value()) {
          std::fprintf(stderr, "REFUSED: %s\n", census.error().message().c_str());
          return 1;
        }
        emit(report, census.value());
        std::fprintf(stderr, "done s%lld rows=%lld\n", static_cast<long long>(ordinal),
                     static_cast<long long>(census.value().rth_rows));
      }
    }
  } else {
    return usage();
  }

  const auto written = report.write(out);
  if (!written.has_value()) {
    std::fprintf(stderr, "REFUSED: %s\n", written.error().message().c_str());
    return 1;
  }
  return 0;
}
