// qr_sources_probe — the authorized real-file read and the 3-stream throughput
// measurement for WP4.
//
// WP4 brief, REAL-FILE CHECK (payload read authorized for this work package on
// EXACTLY these files and no others):
//   session 125 day files for stock_quotes / stock_trades / options_prints, and
//   the SAME option_quotes shard WP3 opened (2025-01-02/exp2025-01-02) at the
//   SCHEMA level only.
// "Report per stream: RTH row count (stock_quotes must equal registry
//  raw_rth_row_count for s125), group count (must equal registry
//  complete_group_count for stock_quotes), per-projected-column (n_nonnull,
//  n_null, digest per WP3's rule)."
//
// It is a binary rather than a ctest case for the reason WP3 already
// established: the stock-quote session is 15.4M rows over 126 row groups, and a
// 139M-value decode does not belong in every ctest invocation, twice, under
// ASan. ci/wp4_sources_realfile_gate.sh runs it against the release build.
//
// usage:
//   qr_sources_probe <stream> --root DIR --label NAME [--ordinal N]
//                    [--iterations N] [--tsv PATH]
//   qr_sources_probe option_quotes_schema --file PATH --label NAME [--tsv PATH]
//
// Output is deterministic: no timestamps, no wall-clock numbers in the TSV.
#include <chrono>
#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <string>
#include <utility>
#include <vector>

#include "qr_sources/option_prints.hpp"
#include "qr_sources/option_quotes.hpp"
#include "qr_sources/rutw_prints.hpp"
#include "qr_sources/stock_quotes.hpp"
#include "qr_sources/stock_trades.hpp"

namespace {

constexpr std::uint64_t kFnvOffsetBasis = 0xCBF29CE484222325ULL;
constexpr std::uint64_t kFnvPrime = 0x100000001B3ULL;

std::uint64_t fnv1a(std::uint64_t digest, const std::vector<std::uint8_t>& data) {
  for (const std::uint8_t byte : data) {
    digest ^= static_cast<std::uint64_t>(byte);
    digest *= kFnvPrime;
  }
  return digest;
}

struct Row {
  std::string label;
  std::string kind;
  std::string name;
  std::string metric;
  std::string value;
};

class Report {
 public:
  explicit Report(std::string label) : label_(std::move(label)) {}

  void file_metric(const std::string& metric, std::int64_t value) {
    rows_.push_back(Row{label_, "file", "-", metric, std::to_string(value)});
  }
  void file_text(const std::string& metric, const std::string& value) {
    rows_.push_back(Row{label_, "file", "-", metric, value});
  }
  void column_metric(const std::string& column, const std::string& metric, std::int64_t value) {
    rows_.push_back(Row{label_, "column", column, metric, std::to_string(value)});
  }

  [[nodiscard]] const std::vector<Row>& rows() const { return rows_; }

  void print() const {
    for (const Row& row : rows_) {
      std::printf("%s\t%s\t%s\t%s\t%s\n", row.label.c_str(), row.kind.c_str(), row.name.c_str(),
                  row.metric.c_str(), row.value.c_str());
    }
  }

  [[nodiscard]] bool write(const std::string& path) const {
    std::FILE* out = std::fopen(path.c_str(), "wb");
    if (out == nullptr) {
      return false;
    }
    std::fprintf(out, "label\tkind\tname\tmetric\tvalue\n");
    for (const Row& row : rows_) {
      std::fprintf(out, "%s\t%s\t%s\t%s\t%s\n", row.label.c_str(), row.kind.c_str(),
                   row.name.c_str(), row.metric.c_str(), row.value.c_str());
    }
    return std::fclose(out) == 0;
  }

 private:
  std::string label_;
  std::vector<Row> rows_;
};

const qr::Registry* registry_or_null() {
  static qr::Expected<qr::Registry, qr::Refusal> loaded = qr::Registry::load_embedded();
  return loaded.has_value() ? &loaded.value() : nullptr;
}

/// The per-stream extras a pass may publish beyond the shared counters.
/// The default publishes nothing, so the four original streams report exactly
/// what they reported before.
struct NoExtras {
  template <class Row>
  void row(const Row&) noexcept {}
  template <class Reader>
  void publish(Report&, const Reader&) const {}
};

/// B3/B5's extras: the print CENSUS (rows, attachment health, junk) and the
/// distinct-contract COVERAGE. Both are counts the reader never acts on.
struct PrintExtras {
  qr::sources::OptionPrintCoverage coverage;

  void row(const qr::sources::OptionPrintRow& value) { coverage.observe(value); }

  template <class Reader>
  void publish(Report& report, const Reader& reader) const {
    const qr::sources::OptionPrintCensus& census = reader.census();
    for (std::size_t index = 0; index < qr::sources::OptionPrintCensus::kFields; ++index) {
      report.column_metric(std::string(qr::sources::OptionPrintCensus::field_name(index)),
                           "census", census.field(index));
    }
    report.column_metric("contracts", "coverage", coverage.contracts());
    report.column_metric("expirations", "coverage", coverage.expirations());
    report.column_metric("strikes", "coverage", coverage.strikes());
  }
};

/// One full pass over a stream: the counters, the per-field digests, and the
/// serialized output digest (which is what two-run byte identity compares).
template <class Reader, class Digests, class Open, class Extras = NoExtras>
int run_stream(Report& report, const Open& open_reader, int iterations, bool registry_counts,
               const qr::Session& session, const std::string& corpus_root_text,
               Extras extras = Extras{}) {
  double best_seconds = 0.0;
  std::int64_t values = 0;
  for (int attempt = 0; attempt < iterations; ++attempt) {
    Extras pass_extras = extras;
    auto opened = open_reader();
    if (!opened.has_value()) {
      std::fprintf(stderr, "REFUSED: %s\n", opened.error().message().c_str());
      return 1;
    }
    Reader reader = std::move(opened).value();
    Digests digests;
    std::uint64_t output_digest = kFnvOffsetBasis;
    std::vector<std::uint8_t> bytes;
    typename Reader::Group group;
    const auto started = std::chrono::steady_clock::now();
    while (true) {
      const auto more = reader.next_group(group);
      if (!more.has_value()) {
        std::fprintf(stderr, "REFUSED: %s\n", more.error().message().c_str());
        return 1;
      }
      if (!more.value()) {
        break;
      }
      bytes.clear();
      qr::sources::append_i64(group.ts_ms_b, bytes);
      qr::sources::append_i64(static_cast<std::int64_t>(group.rows.size()), bytes);
      for (const auto& row : group.rows) {
        append_serialized(row, bytes);
        digests.fold(row);
        pass_extras.row(row);
      }
      output_digest = fnv1a(output_digest, bytes);
    }
    const double seconds =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
    if (attempt == 0 || seconds < best_seconds) {
      best_seconds = seconds;
    }
    values = reader.decoded_values();

    if (attempt == 0) {
      report.file_text("path", reader.path().string());
      report.file_text("corpus_root", corpus_root_text);
      report.file_metric("file_rows", reader.source().file_rows());
      report.file_metric("num_row_groups",
                         static_cast<std::int64_t>(reader.source().row_groups_total()));
      report.file_metric("row_groups_kept",
                         static_cast<std::int64_t>(reader.source().row_groups_kept()));
      report.file_metric("num_leaves",
                         static_cast<std::int64_t>(reader.source().file().leaves().size()));
      report.file_metric("rth_rows", reader.rth_rows());
      report.file_metric("group_count", reader.group_count());
      report.file_metric("decoded_values", values);
      report.file_metric("output_digest_i64", static_cast<std::int64_t>(output_digest));
      if (registry_counts) {
        report.file_metric("registry_raw_rth_row_count", session.raw_rth_row_count);
        report.file_metric("registry_complete_group_count", session.complete_group_count);
        report.file_metric("registry_rth_rows_match",
                           reader.rth_rows() == session.raw_rth_row_count ? 1 : 0);
        report.file_metric("registry_group_count_match",
                           reader.group_count() == session.complete_group_count ? 1 : 0);
      }
      for (std::size_t slot = 0; slot < digests.field.size(); ++slot) {
        const std::string name(Digests::field_name(slot));
        report.column_metric(name, "n_nonnull", digests.field[slot].non_null());
        report.column_metric(name, "n_null", digests.field[slot].nulls());
        report.column_metric(name, "digest_i64", digests.field[slot].digest_i64());
      }
      pass_extras.publish(report, reader);
    }
  }
  if (best_seconds > 0.0) {
    std::printf("best_seconds %.6f\n", best_seconds);
    std::printf("values_per_second %" PRId64 "\n",
                static_cast<std::int64_t>(static_cast<double>(values) / best_seconds));
  }
  return 0;
}

int usage() {
  std::fprintf(stderr,
               "usage: qr_sources_probe <stock_quotes|stock_trades|options_prints|rutw_prints> "
               "--root DIR --label NAME [--ordinal N] [--iterations N] [--tsv PATH]\n"
               "       qr_sources_probe option_quotes_schema --file PATH --label NAME "
               "[--tsv PATH]\n");
  return 2;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) {
    return usage();
  }
  const std::string stream = argv[1];
  std::string root;
  std::string file;
  std::string label;
  std::string tsv;
  std::int64_t ordinal = 125;
  int iterations = 1;
  for (int index = 2; index < argc; ++index) {
    const std::string flag = argv[index];
    const bool has_value = index + 1 < argc;
    if (flag == "--root" && has_value) {
      root = argv[++index];
    } else if (flag == "--file" && has_value) {
      file = argv[++index];
    } else if (flag == "--label" && has_value) {
      label = argv[++index];
    } else if (flag == "--tsv" && has_value) {
      tsv = argv[++index];
    } else if (flag == "--ordinal" && has_value) {
      ordinal = std::strtoll(argv[++index], nullptr, 10);
    } else if (flag == "--iterations" && has_value) {
      iterations = static_cast<int>(std::strtol(argv[++index], nullptr, 10));
    } else {
      return usage();
    }
  }
  if (label.empty()) {
    return usage();
  }
  Report report(label);

  // --- the schema-level option-quote check (no payload page is read) --------
  if (stream == "option_quotes_schema") {
    if (file.empty()) {
      return usage();
    }
    const auto opened = qr::parquet::File::open(file);
    if (!opened.has_value()) {
      std::fprintf(stderr, "REFUSED: %s\n", opened.error().message().c_str());
      return 1;
    }
    const auto checked = qr::sources::check_option_quote_schema(opened.value());
    if (!checked.has_value()) {
      std::fprintf(stderr, "REFUSED: %s\n", checked.error().message().c_str());
      return 1;
    }
    report.file_text("path", file);
    report.file_metric("file_rows", checked.value().num_rows);
    report.file_metric("num_row_groups", static_cast<std::int64_t>(checked.value().num_row_groups));
    report.file_metric("num_leaves", static_cast<std::int64_t>(checked.value().num_leaves));
    const qr::sources::SpecView spec = view_of(qr::sources::kOptionQuoteSpec);
    for (std::size_t slot = 0; slot < checked.value().forms.size(); ++slot) {
      report.column_metric(std::string(spec.names()[spec.projection()[slot]]), "form_id",
                           static_cast<std::int64_t>(checked.value().forms[slot]));
    }
    report.print();
    if (!tsv.empty() && !report.write(tsv)) {
      std::fprintf(stderr, "cannot write %s\n", tsv.c_str());
      return 1;
    }
    return 0;
  }

  if (root.empty()) {
    return usage();
  }
  const qr::Registry* const registry = registry_or_null();
  if (registry == nullptr) {
    std::fprintf(stderr, "the embedded registry refused to load\n");
    return 1;
  }
  const auto scope = qr::DayScope::admit(*registry, ordinal);
  if (!scope.has_value()) {
    std::fprintf(stderr, "REFUSED: %s\n", scope.error().message().c_str());
    return 1;
  }
  const std::filesystem::path corpus_root(root);
  const auto open_prints = [&] {
    return qr::sources::OptionPrintReader::open(scope.value(), corpus_root);
  };
  const auto open_rutw = [&] {
    return qr::sources::RutwPrintReader::open(scope.value(), corpus_root);
  };
  int status = 0;
  if (stream == "stock_quotes") {
    status = run_stream<qr::sources::StockQuoteReader, qr::sources::StockQuoteDigests>(
        report,
        [&] {
          return qr::sources::StockQuoteReader::open(scope.value(), corpus_root,
                                                     scope.value().profile());
        },
        iterations, true, scope.value().session(), root);
  } else if (stream == "stock_trades") {
    status = run_stream<qr::sources::StockTradeReader, qr::sources::StockTradeDigests>(
        report, [&] { return qr::sources::StockTradeReader::open(scope.value(), corpus_root); },
        iterations, false, scope.value().session(), root);
  } else if (stream == "options_prints") {
    status = run_stream<qr::sources::OptionPrintReader, qr::sources::OptionPrintDigests,
                        decltype(open_prints), PrintExtras>(
        report, open_prints, iterations, false, scope.value().session(), root, PrintExtras{});
  } else if (stream == "rutw_prints") {
    // B5. The SAME digests and the SAME extras as B3 — the appendix says the
    // profile and the laws are the same, so the report is the same report.
    status = run_stream<qr::sources::RutwPrintReader, qr::sources::OptionPrintDigests,
                        decltype(open_rutw), PrintExtras>(
        report, open_rutw, iterations, false, scope.value().session(), root, PrintExtras{});
  } else {
    return usage();
  }
  if (status != 0) {
    return status;
  }
  report.print();
  if (!tsv.empty() && !report.write(tsv)) {
    std::fprintf(stderr, "cannot write %s\n", tsv.c_str());
    return 1;
  }
  return 0;
}
