// qr_ivx_columns — THE CC-013 COLUMN CENSUS RUN.
//
// CHARTER: design/DESIGN_FEATURES.md §CC-013 ("requires: column census first
// (presence/range/junk-rate per era) ... the amendment lands only with the
// census receipt"). This binary produces that receipt and NOTHING ELSE: it does
// not amend the projection, it does not decode a value, and `qr_sources` — the
// module that owns the hard-refusal wall — is not linked into it.
//
// usage: qr_ivx_columns --root DIR --out TSV --ordinals LIST
//
// `--root` is the option-print corpus root (APPENDIX B3). Output carries no
// wall-clock value, so two runs of the same arguments are byte-identical.
#include <algorithm>
#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <string>
#include <vector>

#include "qr_ivx/column_census.hpp"
#include "qr_ivx/tsv.hpp"
#include "qr_registry/registry.hpp"

namespace {

int usage() {
  std::fprintf(stderr, "usage: qr_ivx_columns --root DIR --out TSV --ordinals LIST\n");
  return 2;
}

std::vector<std::int64_t> parse_ordinals(const std::string& text) {
  std::vector<std::int64_t> out;
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

/// The per-column ERA-STABILITY fold: one row set per column summarising how
/// the per-session verdicts agree. "Stable" means every censused session
/// returned the SAME verdict; the census reports the disagreement rather than
/// picking a winner.
struct Stability {
  std::int64_t sessions = 0;
  std::map<std::string, std::int64_t> verdicts;  // ordered: emission is output
  std::int64_t real_sessions = 0;
  bool has_range = false;
  double min_value = 0.0;
  double max_value = 0.0;
  std::int64_t min_presence_ppm = -1;
  std::int64_t max_presence_ppm = -1;
};

}  // namespace

int main(int argc, char** argv) {
  std::string root;
  std::string out_path;
  std::string ordinals_text;
  for (int index = 1; index < argc; ++index) {
    const std::string flag = argv[index];
    if (index + 1 >= argc) return usage();
    const std::string value = argv[++index];
    if (flag == "--root") {
      root = value;
    } else if (flag == "--out") {
      out_path = value;
    } else if (flag == "--ordinals") {
      ordinals_text = value;
    } else {
      return usage();
    }
  }
  if (root.empty() || out_path.empty() || ordinals_text.empty()) return usage();

  auto registry = qr::Registry::load_embedded();
  if (!registry.has_value()) {
    std::fprintf(stderr, "the embedded registry refused to load\n");
    return 1;
  }

  qr::ivx::Report report;
  report.text("run", "spec", "charter", "design/DESIGN_FEATURES.md#CC-013");
  report.text("run", "spec", "reads", "PARQUET_SCHEMA_AND_FOOTER_STATISTICS_ONLY");
  report.text("run", "spec", "decodes_values", "NO");

  std::map<std::string, Stability> stability;

  for (const std::int64_t ordinal : parse_ordinals(ordinals_text)) {
    const auto scope = qr::DayScope::admit(registry.value(), ordinal);
    if (!scope.has_value()) {
      std::fprintf(stderr, "REFUSED: %s\n", scope.error().message().c_str());
      return 1;
    }
    const auto census = qr::ivx::census_print_columns(scope.value(), std::filesystem::path(root));
    if (!census.has_value()) {
      std::fprintf(stderr, "REFUSED s%lld: %s\n", static_cast<long long>(ordinal),
                   census.error().message().c_str());
      return 1;
    }
    const qr::ivx::SessionColumnCensus& one = census.value();
    const std::string session_key = "s" + std::to_string(ordinal);
    report.text("session", session_key, "day", one.day);
    report.metric("session", session_key, "files", one.files);
    report.metric("session", session_key, "file_rows", one.file_rows);
    report.metric("session", session_key, "row_groups", one.row_groups);
    report.metric("session", session_key, "schema_leaves", one.schema_leaves);

    for (const qr::ivx::ColumnStat& stat : one.columns) {
      const std::string key = session_key + "/" + stat.name;
      const qr::ivx::ColumnVerdict verdict = qr::ivx::verdict_of(stat);
      report.text("column", key, "standing", qr::ivx::spec_standing_name(stat.standing));
      report.text("column", key, "verdict", qr::ivx::column_verdict_name(verdict));
      report.metric("column", key, "in_schema", stat.in_schema ? 1 : 0);
      report.metric("column", key, "leaf", stat.leaf);
      report.metric("column", key, "physical_type", stat.physical_type);
      report.text("column", key, "stat_kind", qr::ivx::stat_kind_name(stat.kind));
      report.metric("column", key, "chunks", stat.chunks);
      report.metric("column", key, "chunks_with_statistics", stat.chunks_with_statistics);
      report.metric("column", key, "chunks_with_null_count", stat.chunks_with_null_count);
      report.metric("column", key, "chunks_with_range", stat.chunks_with_range);
      report.metric("column", key, "chunks_nonfinite_bound", stat.chunks_nonfinite_bound);
      report.metric("column", key, "chunks_zero_range", stat.chunks_zero_range);
      report.metric("column", key, "num_values", stat.num_values);
      report.metric("column", key, "null_count", stat.null_count);
      report.metric("column", key, "presence_ppm", qr::ivx::presence_ppm(stat));
      if (stat.has_range) {
        report.real("column", key, "min_value", stat.min_value);
        report.real("column", key, "max_value", stat.max_value);
      } else {
        report.text("column", key, "min_value", "NO_RANGE");
        report.text("column", key, "max_value", "NO_RANGE");
      }

      Stability& fold = stability[stat.name];
      ++fold.sessions;
      ++fold.verdicts[qr::ivx::column_verdict_name(verdict)];
      if (verdict == qr::ivx::ColumnVerdict::REAL ||
          verdict == qr::ivx::ColumnVerdict::REAL_WITH_NONFINITE) {
        ++fold.real_sessions;
      }
      if (stat.has_range) {
        if (!fold.has_range) {
          fold.has_range = true;
          fold.min_value = stat.min_value;
          fold.max_value = stat.max_value;
        } else {
          fold.min_value = std::min(fold.min_value, stat.min_value);
          fold.max_value = std::max(fold.max_value, stat.max_value);
        }
      }
      const std::int64_t presence = qr::ivx::presence_ppm(stat);
      if (presence >= 0) {
        fold.min_presence_ppm =
            fold.min_presence_ppm < 0 ? presence : std::min(fold.min_presence_ppm, presence);
        fold.max_presence_ppm =
            fold.max_presence_ppm < 0 ? presence : std::max(fold.max_presence_ppm, presence);
      }
    }
    std::fprintf(stderr, "done s%lld rows=%lld files=%lld\n", static_cast<long long>(ordinal),
                 static_cast<long long>(one.file_rows), static_cast<long long>(one.files));
  }

  for (const auto& [name, fold] : stability) {
    report.metric("era", name, "sessions", fold.sessions);
    report.metric("era", name, "real_sessions", fold.real_sessions);
    report.metric("era", name, "distinct_verdicts",
                  static_cast<std::int64_t>(fold.verdicts.size()));
    report.text("era", name, "stable", fold.verdicts.size() == 1 ? "YES" : "NO");
    for (const auto& [verdict, count] : fold.verdicts) {
      report.metric("era_verdict", name + "/" + verdict, "sessions", count);
    }
    report.metric("era", name, "min_presence_ppm", fold.min_presence_ppm);
    report.metric("era", name, "max_presence_ppm", fold.max_presence_ppm);
    if (fold.has_range) {
      report.real("era", name, "min_value", fold.min_value);
      report.real("era", name, "max_value", fold.max_value);
    } else {
      report.text("era", name, "min_value", "NO_RANGE");
      report.text("era", name, "max_value", "NO_RANGE");
    }
  }

  const auto written = report.write(out_path);
  if (!written.has_value()) {
    std::fprintf(stderr, "REFUSED: %s\n", written.error().message().c_str());
    return 1;
  }
  return 0;
}
