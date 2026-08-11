// The real-file check and the decode budget gate.
//
// WP3 brief, REAL-FILE CHECK (payload read authorized for this WP on exactly
// this file): /workspace/data/tokens/stock_trades/IWM/2022/2022-07-05.parquet
// (session 125). "decode all projected-type columns, print row count +
// per-column (count, i64-sum or bitwise-xor for doubles) — these numbers become
// committed fixtures for WP9's differential."
//
// The committed numbers live in engine/cpp/tests/fixtures/real_file_digests.tsv,
// written by qr_parquet_probe. This suite re-derives them from the file on every
// run: if the decoder drifts, or the corpus file changes, the row stops matching.
//
// The 704MB option-quote shard's row is in the same TSV but is produced by the
// probe as an artifact run (see ci/wp3_parquet_realfile_gate.sh); putting a
// 57.8M-row decode inside every ctest invocation, twice, under ASan, is not a
// per-commit gate.
#include <gtest/gtest.h>

#include <chrono>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

#include "qr_parquet/reader.hpp"

namespace {

using qr::parquet::ColumnData;
using qr::parquet::DecodeWorkspace;
using qr::parquet::File;
using qr::parquet::LeafType;

constexpr const char* kTradesLabel = "IWM_stock_trades_2022-07-05";
/// The measured single-thread floor from the WP3 brief: ">=25M values/s on the
/// real trades file".
constexpr double kValuesPerSecondFloor = 25e6;

constexpr std::uint64_t kFnvOffsetBasis = 0xCBF29CE484222325ULL;
constexpr std::uint64_t kFnvPrime = 0x100000001B3ULL;

std::uint64_t fnv1a(std::uint64_t digest, const std::uint8_t* data, std::size_t size) {
  for (std::size_t index = 0; index < size; ++index) {
    digest ^= static_cast<std::uint64_t>(data[index]);
    digest *= kFnvPrime;
  }
  return digest;
}

/// key = "<kind>/<name>/<metric>" -> value, for one label of the committed TSV.
using DigestRows = std::map<std::string, std::string>;

DigestRows load_committed(const std::string& label) {
  DigestRows rows;
  std::ifstream input(QR_PARQUET_REAL_DIGESTS);
  EXPECT_TRUE(input.good()) << "cannot read " << QR_PARQUET_REAL_DIGESTS;
  std::string line;
  bool header = true;
  while (std::getline(input, line)) {
    if (header) {
      header = false;
      continue;
    }
    if (line.empty()) {
      continue;
    }
    std::vector<std::string> fields;
    std::string field;
    std::istringstream stream(line);
    while (std::getline(stream, field, '\t')) {
      fields.push_back(field);
    }
    if (fields.size() != 5 || fields[0] != label) {
      continue;
    }
    rows[fields[1] + "/" + fields[2] + "/" + fields[3]] = fields[4];
  }
  return rows;
}

std::int64_t as_int(const DigestRows& rows, const std::string& key) {
  const auto found = rows.find(key);
  EXPECT_NE(found, rows.end()) << "committed digest row missing: " << key;
  if (found == rows.end()) {
    return -1;
  }
  return static_cast<std::int64_t>(std::strtoll(found->second.c_str(), nullptr, 10));
}

struct Totals {
  std::int64_t non_null = 0;
  std::int64_t null_count = 0;
  std::uint64_t digest = 0;
  bool started = false;
};

void fold(Totals& totals, const ColumnData& column) {
  switch (column.type) {
    case LeafType::INT32:
    case LeafType::INT64:
      totals.digest += qr::parquet::column_digest(column);
      break;
    case LeafType::DOUBLE:
      totals.digest ^= qr::parquet::column_digest(column);
      break;
    case LeafType::BYTE_ARRAY: {
      if (!totals.started) {
        totals.digest = kFnvOffsetBasis;
        totals.started = true;
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
        totals.digest =
            fnv1a(totals.digest, reinterpret_cast<const std::uint8_t*>(value.data()), value.size());
      }
      break;
    }
  }
  totals.null_count += column.null_count;
  totals.non_null += column.num_rows - column.null_count;
}

struct DecodeResult {
  std::int64_t decoded_values = 0;
  std::uint64_t output_digest = kFnvOffsetBasis;
  std::vector<Totals> per_column;
  double seconds = 0.0;
};

/// Decodes every column of every row group once.
DecodeResult decode_all(const File& file) {
  DecodeResult result;
  result.per_column.assign(file.leaves().size(), Totals{});
  DecodeWorkspace workspace;
  ColumnData column;
  std::vector<std::uint8_t> serialized;
  const auto started = std::chrono::steady_clock::now();
  for (std::size_t group = 0; group < file.num_row_groups(); ++group) {
    for (std::size_t leaf = 0; leaf < file.leaves().size(); ++leaf) {
      const qr::parquet::FileExpected<std::int64_t> rows =
          file.read_column(group, leaf, workspace, column);
      EXPECT_TRUE(rows.has_value())
          << (rows.has_value() ? std::string() : rows.error().message());
      if (!rows.has_value()) {
        return result;
      }
      result.decoded_values += rows.value();
      fold(result.per_column[leaf], column);
      serialized.clear();
      qr::parquet::append_serialized(column, serialized);
      result.output_digest = fnv1a(result.output_digest, serialized.data(), serialized.size());
    }
  }
  result.seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
  return result;
}

std::string trades_path() {
  const DigestRows rows = load_committed(kTradesLabel);
  const auto found = rows.find("file/-/path");
  if (found == rows.end()) {
    return {};
  }
  return found->second;
}

TEST(RealFileDigests, StockTradesSessionOneTwentyFiveMatchesTheCommittedFixture) {
  const std::string path = trades_path();
  ASSERT_FALSE(path.empty()) << "no path row for " << kTradesLabel;
  const qr::parquet::FileExpected<File> opened = File::open(path);
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const File& file = opened.value();
  const DigestRows committed = load_committed(kTradesLabel);

  EXPECT_EQ(file.num_rows(), as_int(committed, "file/-/num_rows"));
  EXPECT_EQ(static_cast<std::int64_t>(file.num_row_groups()),
            as_int(committed, "file/-/num_row_groups"));
  EXPECT_EQ(static_cast<std::int64_t>(file.leaves().size()),
            as_int(committed, "file/-/num_leaves"));

  const DecodeResult result = decode_all(file);
  EXPECT_EQ(result.decoded_values, as_int(committed, "file/-/decoded_values"));
  EXPECT_EQ(static_cast<std::int64_t>(result.output_digest),
            as_int(committed, "file/-/output_digest_i64"));
  for (std::size_t leaf = 0; leaf < file.leaves().size(); ++leaf) {
    const std::string name = file.leaves()[leaf].name;
    EXPECT_EQ(result.per_column[leaf].non_null, as_int(committed, "column/" + name + "/n_nonnull"))
        << name;
    EXPECT_EQ(result.per_column[leaf].null_count, as_int(committed, "column/" + name + "/n_null"))
        << name;
    EXPECT_EQ(static_cast<std::int64_t>(result.per_column[leaf].digest),
              as_int(committed, "column/" + name + "/digest_i64"))
        << name;
  }
}

TEST(RealFileDigests, DecodedValuesAgreeWithTheWritersOwnColumnStatistics) {
  const std::string path = trades_path();
  ASSERT_FALSE(path.empty());
  const qr::parquet::FileExpected<File> opened = File::open(path);
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const File& file = opened.value();
  DecodeWorkspace workspace;
  ColumnData column;
  int compared = 0;
  for (std::size_t group = 0; group < file.num_row_groups(); ++group) {
    for (std::size_t leaf = 0; leaf < file.leaves().size(); ++leaf) {
      const qr::parquet::ColumnChunkMeta& chunk =
          file.metadata().row_groups[group].columns[leaf];
      if (!chunk.has_statistics) {
        continue;
      }
      ASSERT_TRUE(file.read_column(group, leaf, workspace, column).has_value());
      const qr::parquet::StatisticsCheck check = qr::parquet::verify_against_statistics(
          chunk.statistics, file.leaves()[leaf].type, column);
      EXPECT_TRUE(check.null_count_present)
          << file.leaves()[leaf].name << ": the writer stored no null count";
      EXPECT_TRUE(check.null_count_matches)
          << file.leaves()[leaf].name
          << ": definition levels disagree with the writer's null count";
      EXPECT_TRUE(check.min_matches) << file.leaves()[leaf].name << " min";
      EXPECT_TRUE(check.max_matches) << file.leaves()[leaf].name << " max";
      if (check.comparable) {
        ++compared;
      }
    }
  }
  // 24 columns x 2 row groups; every one of them carries statistics in this
  // corpus (the WP0 census records has_timestamp_stats=yes for all 8,726 files).
  EXPECT_EQ(compared, 48);
}

TEST(RealFileDigests, TwoRunsOverTheRealFileAreByteIdentical) {
  const std::string path = trades_path();
  ASSERT_FALSE(path.empty());
  std::vector<std::uint8_t> runs[2];
  for (int attempt = 0; attempt < 2; ++attempt) {
    const qr::parquet::FileExpected<File> opened = File::open(path);
    ASSERT_TRUE(opened.has_value()) << opened.error().message();
    const File& file = opened.value();
    DecodeWorkspace workspace;
    ColumnData column;
    for (std::size_t group = 0; group < file.num_row_groups(); ++group) {
      for (std::size_t leaf = 0; leaf < file.leaves().size(); ++leaf) {
        ASSERT_TRUE(file.read_column(group, leaf, workspace, column).has_value());
        qr::parquet::append_serialized(column, runs[attempt]);
      }
    }
  }
  ASSERT_EQ(runs[0].size(), runs[1].size());
  EXPECT_EQ(runs[0], runs[1]);
}

TEST(RealFileDigests, RowGroupTimestampPruningOnTheRealFileKeepsOnlyOverlappingGroups) {
  const std::string path = trades_path();
  ASSERT_FALSE(path.empty());
  const qr::parquet::FileExpected<File> opened = File::open(path);
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const File& file = opened.value();
  const qr::parquet::FileExpected<std::size_t> ts = file.leaf_index("trade_timestamp");
  ASSERT_TRUE(ts.has_value()) << ts.error().message();

  // Every row group of this file carries INT64 timestamp statistics (the census
  // records has_timestamp_stats=yes for the whole corpus).
  std::vector<qr::parquet::Int64Stats> stats;
  for (std::size_t group = 0; group < file.num_row_groups(); ++group) {
    const qr::parquet::Int64Stats one = file.int64_stats(group, ts.value());
    ASSERT_TRUE(one.present) << "row group " << group << " has no timestamp statistics";
    EXPECT_LE(one.min, one.max);
    stats.push_back(one);
  }
  ASSERT_GE(stats.size(), 2U);

  // A window entirely before the first row group prunes everything; a window
  // covering the whole file keeps everything.
  EXPECT_TRUE(file.rth_row_groups(ts.value(), 0, stats.front().min).empty());
  EXPECT_EQ(file.rth_row_groups(ts.value(), stats.front().min, stats.back().max + 1).size(),
            file.num_row_groups());
  // A window inside the FIRST row group only must not keep the last one.
  const std::vector<std::size_t> kept =
      file.rth_row_groups(ts.value(), stats.front().min, stats.front().min + 1);
  EXPECT_FALSE(kept.empty());
  EXPECT_EQ(kept.front(), 0U);
}

TEST(RealFileBudget, SingleThreadDecodeMeetsTheValueRateFloor) {
  const std::string path = trades_path();
  ASSERT_FALSE(path.empty());
  const qr::parquet::FileExpected<File> opened = File::open(path);
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const File& file = opened.value();

  // Best of three: the measurement, not the scheduler, is what we want.
  double best = 0.0;
  std::int64_t values = 0;
  for (int attempt = 0; attempt < 3; ++attempt) {
    const DecodeResult result = decode_all(file);
    values = result.decoded_values;
    if (attempt == 0 || result.seconds < best) {
      best = result.seconds;
    }
  }
  ASSERT_GT(best, 0.0);
  const double rate = static_cast<double>(values) / best;
  std::printf("[ BUDGET   ] qr_parquet single-thread decode: %.0f values/s (%" PRId64
              " values in %.4fs)\n",
              rate, values, best);

#if !defined(__SANITIZE_ADDRESS__)
  // The floor is enforced in BOTH the dev (-O0) and release builds: the
  // unoptimized decoder already clears it, so a regression that only shows up
  // under -O2 cannot hide behind a debug build.
  EXPECT_GE(rate, kValuesPerSecondFloor)
      << "decode throughput is below the WP3 budget of 25M values/s";
#else
  // Under ASan/UBSan the number measures the sanitizer, not the decoder, so it
  // is reported and not asserted.
  GTEST_SKIP() << "throughput floor is not asserted under the sanitizers; measured " << rate
               << " values/s here";
#endif
}

}  // namespace
