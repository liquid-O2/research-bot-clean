// qr_parquet_probe — the real-file digest and throughput probe.
//
// WP3 brief, REAL-FILE CHECK: "decode all projected-type columns, print row
// count + per-column (count, i64-sum or bitwise-xor for doubles) — these numbers
// become committed fixtures for WP9's differential."
//
// It is a binary rather than a ctest case because one of the two authorized
// files is a 704MB option-quote shard: that belongs in an artifact run, exactly
// as ci/run_all.sh already treats the WP0 whole-corpus census. The small trades
// file's numbers ARE asserted every run, by
// qr_parquet/tests/test_real_file.cpp against the committed TSV this tool
// writes.
//
// usage:
//   qr_parquet_probe <parquet-path> --label <name> [--iterations N] [--tsv PATH]
//
// Output is deterministic: sorted by leaf index, no timestamps, no paths in the
// digest rows beyond the one `path` metric.
#include <cinttypes>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "qr_parquet/reader.hpp"

namespace {

constexpr std::uint64_t kFnvOffsetBasis = 0xCBF29CE484222325ULL;
constexpr std::uint64_t kFnvPrime = 0x100000001B3ULL;

std::uint64_t fnv1a(std::uint64_t digest, const std::uint8_t* data, std::size_t size) {
  for (std::size_t index = 0; index < size; ++index) {
    digest ^= static_cast<std::uint64_t>(data[index]);
    digest *= kFnvPrime;
  }
  return digest;
}

struct ColumnTotals {
  std::int64_t non_null = 0;
  std::int64_t null_count = 0;
  std::uint64_t digest = 0;
  bool digest_started = false;
};

/// Folds one row group's digest into the whole-column digest, by the rule the
/// digest type demands: sum for integers, xor for doubles, and a rolling FNV-1a
/// over the concatenated length-prefixed bytes for byte arrays.
void fold(ColumnTotals& totals, const qr::parquet::ColumnData& column) {
  using qr::parquet::LeafType;
  switch (column.type) {
    case LeafType::INT32:
    case LeafType::INT64:
      totals.digest += qr::parquet::column_digest(column);
      break;
    case LeafType::DOUBLE:
      totals.digest ^= qr::parquet::column_digest(column);
      break;
    case LeafType::BYTE_ARRAY: {
      if (!totals.digest_started) {
        totals.digest = kFnvOffsetBasis;
        totals.digest_started = true;
      }
      for (std::int64_t row = 0; row < column.num_rows; ++row) {
        if (column.is_null(row)) {
          continue;
        }
        const std::string_view value = column.byte_array(row);
        const std::uint32_t length = static_cast<std::uint32_t>(value.size());
        std::uint8_t length_le[4];
        for (unsigned index = 0; index < 4; ++index) {
          length_le[index] = static_cast<std::uint8_t>((length >> (index * 8U)) & 0xFFU);
        }
        totals.digest = fnv1a(totals.digest, length_le, sizeof(length_le));
        totals.digest = fnv1a(totals.digest,
                              reinterpret_cast<const std::uint8_t*>(value.data()), value.size());
      }
      break;
    }
  }
  totals.null_count += column.null_count;
  totals.non_null += column.num_rows - column.null_count;
}

int usage() {
  std::fprintf(stderr,
               "usage: qr_parquet_probe <parquet-path> --label <name> "
               "[--iterations N] [--tsv PATH]\n");
  return 2;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) {
    return usage();
  }
  const std::string path = argv[1];
  std::string label = "unlabelled";
  std::string tsv_path;
  int iterations = 1;
  for (int index = 2; index < argc; ++index) {
    const std::string flag = argv[index];
    if (index + 1 >= argc) {
      return usage();
    }
    const std::string value = argv[++index];
    if (flag == "--label") {
      label = value;
    } else if (flag == "--iterations") {
      iterations = std::atoi(value.c_str());
    } else if (flag == "--tsv") {
      tsv_path = value;
    } else {
      return usage();
    }
  }
  if (iterations < 1) {
    iterations = 1;
  }

  qr::parquet::FileExpected<qr::parquet::File> opened = qr::parquet::File::open(path);
  if (!opened.has_value()) {
    std::fprintf(stderr, "REFUSED: %s\n", opened.error().message().c_str());
    return 1;
  }
  const qr::parquet::File& file = opened.value();

  std::vector<ColumnTotals> totals(file.leaves().size());
  std::uint64_t output_digest = kFnvOffsetBasis;
  std::int64_t decoded_values = 0;
  double best_seconds = 0.0;
  // Independent oracle, free on every real file: the min/max/null_count the
  // WRITER stored in the footer. A decode error shows up here immediately.
  std::int64_t statistics_compared = 0;
  std::int64_t statistics_mismatched = 0;

  for (int attempt = 0; attempt < iterations; ++attempt) {
    for (ColumnTotals& column : totals) {
      column = ColumnTotals{};
    }
    output_digest = kFnvOffsetBasis;
    decoded_values = 0;
    statistics_compared = 0;
    statistics_mismatched = 0;
    qr::parquet::DecodeWorkspace workspace;
    qr::parquet::ColumnData column;
    std::vector<std::uint8_t> serialized;

    const auto started = std::chrono::steady_clock::now();
    for (std::size_t group = 0; group < file.num_row_groups(); ++group) {
      for (std::size_t leaf = 0; leaf < file.leaves().size(); ++leaf) {
        const qr::parquet::FileExpected<std::int64_t> rows =
            file.read_column(group, leaf, workspace, column);
        if (!rows.has_value()) {
          std::fprintf(stderr, "REFUSED: %s\n", rows.error().message().c_str());
          return 1;
        }
        decoded_values += rows.value();
        const qr::parquet::ColumnChunkMeta& chunk =
            file.metadata().row_groups[group].columns[leaf];
        if (chunk.has_statistics) {
          const qr::parquet::StatisticsCheck check = qr::parquet::verify_against_statistics(
              chunk.statistics, file.leaves()[leaf].type, column);
          if (check.comparable) {
            ++statistics_compared;
          }
          if (!check.agrees()) {
            ++statistics_mismatched;
            std::fprintf(stderr,
                         "STATISTICS MISMATCH: row group %zu column %s (min_ok=%d max_ok=%d "
                         "null_ok=%d)\n",
                         group, file.leaves()[leaf].name.c_str(),
                         static_cast<int>(check.min_matches), static_cast<int>(check.max_matches),
                         static_cast<int>(check.null_count_matches));
          }
        }
        fold(totals[leaf], column);
        serialized.clear();
        qr::parquet::append_serialized(column, serialized);
        output_digest = fnv1a(output_digest, serialized.data(), serialized.size());
      }
    }
    const auto finished = std::chrono::steady_clock::now();
    const double seconds = std::chrono::duration<double>(finished - started).count();
    if (attempt == 0 || seconds < best_seconds) {
      best_seconds = seconds;
    }
  }

  const double values_per_second = best_seconds > 0.0
                                       ? static_cast<double>(decoded_values) / best_seconds
                                       : 0.0;

  std::printf("path              %s\n", path.c_str());
  std::printf("label             %s\n", label.c_str());
  std::printf("rows              %" PRId64 "\n", file.num_rows());
  std::printf("row_groups        %zu\n", file.num_row_groups());
  std::printf("leaves            %zu\n", file.leaves().size());
  std::printf("file_bytes        %zu\n", file.size_bytes());
  std::printf("decoded_values    %" PRId64 "\n", decoded_values);
  std::printf("iterations        %d\n", iterations);
  std::printf("best_seconds      %.6f\n", best_seconds);
  std::printf("values_per_second %.0f\n", values_per_second);
  std::printf("output_digest     %" PRId64 "\n", static_cast<std::int64_t>(output_digest));
  std::printf("stats_compared    %" PRId64 "\n", statistics_compared);
  std::printf("stats_mismatched  %" PRId64 "\n", statistics_mismatched);
  std::printf("\n%-24s %-12s %-9s %12s %10s %22s\n", "column", "type", "converted", "n_nonnull",
              "n_null", "digest_i64");
  for (std::size_t leaf = 0; leaf < file.leaves().size(); ++leaf) {
    std::printf("%-24s %-12s %-9s %12" PRId64 " %10" PRId64 " %22" PRId64 "\n",
                file.leaves()[leaf].name.c_str(),
                qr::parquet::leaf_type_name(file.leaves()[leaf].type),
                qr::parquet::leaf_converted_name(file.leaves()[leaf].converted),
                totals[leaf].non_null, totals[leaf].null_count,
                static_cast<std::int64_t>(totals[leaf].digest));
  }

  if (!tsv_path.empty()) {
    std::FILE* out = std::fopen(tsv_path.c_str(), "w");
    if (out == nullptr) {
      std::fprintf(stderr, "cannot write %s\n", tsv_path.c_str());
      return 1;
    }
    std::fprintf(out, "label\tkind\tname\tmetric\tvalue\n");
    std::fprintf(out, "%s\tfile\t-\tpath\t%s\n", label.c_str(), path.c_str());
    std::fprintf(out, "%s\tfile\t-\tnum_rows\t%" PRId64 "\n", label.c_str(), file.num_rows());
    std::fprintf(out, "%s\tfile\t-\tnum_row_groups\t%zu\n", label.c_str(), file.num_row_groups());
    std::fprintf(out, "%s\tfile\t-\tnum_leaves\t%zu\n", label.c_str(), file.leaves().size());
    std::fprintf(out, "%s\tfile\t-\tdecoded_values\t%" PRId64 "\n", label.c_str(), decoded_values);
    std::fprintf(out, "%s\tfile\t-\toutput_digest_i64\t%" PRId64 "\n", label.c_str(),
                 static_cast<std::int64_t>(output_digest));
    std::fprintf(out, "%s\tfile\t-\tstats_compared\t%" PRId64 "\n", label.c_str(),
                 statistics_compared);
    std::fprintf(out, "%s\tfile\t-\tstats_mismatched\t%" PRId64 "\n", label.c_str(),
                 statistics_mismatched);
    for (std::size_t leaf = 0; leaf < file.leaves().size(); ++leaf) {
      const char* name = file.leaves()[leaf].name.c_str();
      std::fprintf(out, "%s\tcolumn\t%s\tn_nonnull\t%" PRId64 "\n", label.c_str(), name,
                   totals[leaf].non_null);
      std::fprintf(out, "%s\tcolumn\t%s\tn_null\t%" PRId64 "\n", label.c_str(), name,
                   totals[leaf].null_count);
      std::fprintf(out, "%s\tcolumn\t%s\tdigest_i64\t%" PRId64 "\n", label.c_str(), name,
                   static_cast<std::int64_t>(totals[leaf].digest));
    }
    std::fclose(out);
    std::printf("\nwrote %s\n", tsv_path.c_str());
  }
  if (statistics_mismatched != 0) {
    std::fprintf(stderr, "FAIL: %" PRId64 " column chunks disagree with the writer's statistics\n",
                 statistics_mismatched);
    return 1;
  }
  return 0;
}
