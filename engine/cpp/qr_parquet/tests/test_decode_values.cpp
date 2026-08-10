// Value-level decode against INDEPENDENTLY DERIVED literals.
//
// SPEC: design/DESIGN_SUBSTRATE.md M1 qr_parquet bullet — "ZSTD pages into a
// reused arena, PLAIN/RLE/RLE_DICTIONARY, def-levels->validity bitmap, flat
// INT32/INT64/DOUBLE/BYTE_ARRAY leaves, row-group timestamp statistics exposure
// for RTH pruning, column projection by leaf index, DataPage v1 AND v2 header
// shapes, dictionary-page cache per chunk".
//
// WHERE THE EXPECTED NUMBERS COME FROM. Every literal below is a value the
// generator ENCODED, printed by it, and committed at
// engine/cpp/tests/fixtures/parquet_expected_literals.tsv. The generator has no
// knowledge of this decoder and this decoder has no knowledge of the generator;
// the only thing they share is the parquet file itself. Doubles are compared as
// IEEE-754 bit patterns so nothing hides behind a tolerance.
#include <gtest/gtest.h>

#include <cstring>
#include <string>
#include <vector>

#include "qr_parquet/reader.hpp"

namespace {

using qr::parquet::ColumnData;
using qr::parquet::DecodeWorkspace;
using qr::parquet::File;
using qr::parquet::LeafConverted;
using qr::parquet::LeafType;

constexpr std::int64_t kNull = INT64_MIN;  // sentinel in the expectation tables
constexpr std::int64_t kRows = 20;
constexpr std::int64_t kRowsPerGroup = 10;

std::string fixture(const char* name) {
  return std::string(QR_PARQUET_FIXTURE_DIR) + "/" + name;
}

// --- the committed literals (parquet_expected_literals.tsv) -----------------
const std::int64_t kTs[kRows] = {
    1657027800000, 1657027800250, 1657027800500, 1657027800750, 1657027801000,
    1657027801250, 1657027801500, 1657027801750, 1657027802000, 1657027802250,
    1657054800000, 1657054800250, 1657054800500, 1657054800750, 1657054801000,
    1657054801250, 1657054801500, 1657054801750, 1657054802000, 1657054802250};

const std::int64_t kSeq[kRows] = {1000, 1007, 1014, 1021, 1028, 1035, 1042, 1049, 1056, 1063,
                                  1070, 1077, 1084, 1091, 1098, 1105, 1112, 1119, 1126, 1133};

/// px as IEEE-754 bit patterns; kNull marks the three null rows.
const std::int64_t kPxBits[kRows] = {
    static_cast<std::int64_t>(0x4065480000000000ULL),
    static_cast<std::int64_t>(0x40654851eb851eb8ULL),
    kNull,
    static_cast<std::int64_t>(0x406547d70a3d70a4ULL),
    static_cast<std::int64_t>(0x406549999999999aULL),
    static_cast<std::int64_t>(0x406549eb851eb852ULL),
    static_cast<std::int64_t>(0x406548f5c28f5c29ULL),
    kNull,
    static_cast<std::int64_t>(0x40654947ae147ae1ULL),
    static_cast<std::int64_t>(0x40654ab851eb851fULL),
    static_cast<std::int64_t>(0x4065600000000000ULL),
    static_cast<std::int64_t>(0x4065640000000000ULL),
    static_cast<std::int64_t>(0x4065680000000000ULL),
    kNull,
    static_cast<std::int64_t>(0x4065700000000000ULL),
    static_cast<std::int64_t>(0x4065740000000000ULL),
    static_cast<std::int64_t>(0x4065780000000000ULL),
    static_cast<std::int64_t>(0x40657c0000000000ULL),
    static_cast<std::int64_t>(0x4065800000000000ULL),
    static_cast<std::int64_t>(0x4065840000000000ULL)};

const std::int64_t kSz[kRows] = {100, 100, 200, kNull, 100, 300, 200, 100, -1294967296, 300,
                                 5,   5,   5,   5,     7,   7,   9,   9,   9,           5};

const std::int64_t kFlag[kRows] = {0, 1, 1, 2, 2, 2, -1, -1, 0, 0,
                                   3, 3, 3, 3, 3, -128, 127, 0, 1, 2};

const std::int64_t kDay[kRows] = {19178, 19178, 19178, 19178, 19178, 19178, 19178,
                                  19178, 19178, 19178, 19179, 19179, 19179, 19179,
                                  19179, 19179, 19179, 19179, 19179, 19179};

/// iv as IEEE-754 bit patterns; a dictionary-encoded DOUBLE with one null.
const std::int64_t kIvBits[kRows] = {
    static_cast<std::int64_t>(0x3fd0000000000000ULL),
    static_cast<std::int64_t>(0x3fd0000000000000ULL),
    static_cast<std::int64_t>(0x3fe0000000000000ULL),
    kNull,
    static_cast<std::int64_t>(0x3fd0000000000000ULL),
    static_cast<std::int64_t>(0x3fe8000000000000ULL),
    static_cast<std::int64_t>(0x3fe0000000000000ULL),
    static_cast<std::int64_t>(0x3fd0000000000000ULL),
    static_cast<std::int64_t>(0x3fe8000000000000ULL),
    static_cast<std::int64_t>(0x3fe0000000000000ULL),
    static_cast<std::int64_t>(0x3ff8000000000000ULL),
    static_cast<std::int64_t>(0x3ff8000000000000ULL),
    static_cast<std::int64_t>(0x4002000000000000ULL),
    static_cast<std::int64_t>(0x4002000000000000ULL),
    static_cast<std::int64_t>(0x3ff8000000000000ULL),
    static_cast<std::int64_t>(0x4009000000000000ULL),
    static_cast<std::int64_t>(0x4009000000000000ULL),
    static_cast<std::int64_t>(0x3ff8000000000000ULL),
    static_cast<std::int64_t>(0x4002000000000000ULL),
    static_cast<std::int64_t>(0x4009000000000000ULL)};

const char* const kSym[kRows] = {
    nullptr, "IWM", "IWM", "IWM250102C00200000", "", "IWM", "IWM250102P00195000",
    "IWM", "IWM250102C00200000", "IWM", "IWM", "IWM", "", "IWM250102P00195000",
    "IWM", "IWM", "IWM", "IWM250102C00200000", "IWM", nullptr};

const char* const kVenue[kRows] = {"XNYS", "XNYS", "XNYS", "XNYS", "XNYS", "XNYS", "XNYS",
                                   "XNYS", "XNYS", nullptr, "XNYS", "XNYS", "XNYS", "XNYS",
                                   "XNYS", "XNYS", "XNYS", "XNYS", "XNYS", "XNYS"};

/// digest_i64 column of parquet_expected_literals.tsv, in leaf order.
const std::int64_t kDigests[9] = {33140826022500,       21330,
                                  4640226036386098179,  -1294965830,
                                  23,                   383570,
                                  4605775043916464128,  -4245619203269744983,
                                  -5335709676555448089};
const std::int64_t kNullCounts[9] = {0, 0, 3, 1, 0, 0, 1, 2, 1};

std::int64_t double_bits(double value) {
  std::int64_t bits = 0;
  std::memcpy(&bits, &value, sizeof(bits));
  return bits;
}

/// Reads one leaf across BOTH row groups into a single row-indexed view.
struct WholeColumn {
  std::vector<std::int64_t> integers;  // kNull marks a null row
  std::vector<std::string> strings;    // empty when the leaf is not BYTE_ARRAY
  std::vector<bool> present;
  std::int64_t null_count = 0;
  std::uint64_t digest_first_group = 0;
};

WholeColumn read_whole(const File& file, std::size_t leaf) {
  WholeColumn whole;
  DecodeWorkspace workspace;
  ColumnData column;
  for (std::size_t group = 0; group < file.num_row_groups(); ++group) {
    const qr::parquet::FileExpected<std::int64_t> rows =
        file.read_column(group, leaf, workspace, column);
    EXPECT_TRUE(rows.has_value())
        << (rows.has_value() ? std::string() : rows.error().message());
    if (!rows.has_value()) {
      return whole;
    }
    EXPECT_EQ(rows.value(), kRowsPerGroup);
    if (group == 0) {
      whole.digest_first_group = qr::parquet::column_digest(column);
    }
    whole.null_count += column.null_count;
    for (std::int64_t row = 0; row < column.num_rows; ++row) {
      const bool valid = !column.is_null(row);
      whole.present.push_back(valid);
      switch (column.type) {
        case LeafType::INT32:
          whole.integers.push_back(valid ? static_cast<std::int64_t>(column.i32[static_cast<
                                               std::size_t>(row)])
                                         : kNull);
          whole.strings.emplace_back();
          break;
        case LeafType::INT64:
          whole.integers.push_back(
              valid ? column.i64[static_cast<std::size_t>(row)] : kNull);
          whole.strings.emplace_back();
          break;
        case LeafType::DOUBLE:
          whole.integers.push_back(
              valid ? double_bits(column.f64[static_cast<std::size_t>(row)]) : kNull);
          whole.strings.emplace_back();
          break;
        case LeafType::BYTE_ARRAY:
          whole.integers.push_back(valid ? 0 : kNull);
          whole.strings.emplace_back(valid ? std::string(column.byte_array(row)) : std::string());
          break;
      }
    }
  }
  return whole;
}

void check_integer_leaf(const File& file, const char* name, const std::int64_t* expected) {
  const qr::parquet::FileExpected<std::size_t> leaf = file.leaf_index(name);
  ASSERT_TRUE(leaf.has_value()) << name;
  const WholeColumn whole = read_whole(file, leaf.value());
  ASSERT_EQ(whole.integers.size(), static_cast<std::size_t>(kRows)) << name;
  for (std::size_t row = 0; row < static_cast<std::size_t>(kRows); ++row) {
    EXPECT_EQ(whole.integers[row], expected[row]) << name << " row " << row;
    EXPECT_EQ(whole.present[row], expected[row] != kNull) << name << " validity row " << row;
  }
}

void check_string_leaf(const File& file, const char* name, const char* const* expected) {
  const qr::parquet::FileExpected<std::size_t> leaf = file.leaf_index(name);
  ASSERT_TRUE(leaf.has_value()) << name;
  const WholeColumn whole = read_whole(file, leaf.value());
  ASSERT_EQ(whole.strings.size(), static_cast<std::size_t>(kRows)) << name;
  for (std::size_t row = 0; row < static_cast<std::size_t>(kRows); ++row) {
    const bool should_be_present = expected[row] != nullptr;
    EXPECT_EQ(whole.present[row], should_be_present) << name << " validity row " << row;
    if (should_be_present) {
      EXPECT_EQ(whole.strings[row], std::string(expected[row])) << name << " row " << row;
    } else {
      EXPECT_TRUE(whole.strings[row].empty())
          << name << " row " << row << ": a null row must be a zero-length slice";
    }
  }
}

class ParquetValues : public ::testing::TestWithParam<const char*> {};

TEST_P(ParquetValues, SchemaIsTheNinePinnedFlatLeaves) {
  const qr::parquet::FileExpected<File> opened = File::open(fixture(GetParam()));
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const File& file = opened.value();
  EXPECT_EQ(file.num_rows(), kRows);
  EXPECT_EQ(file.num_row_groups(), 2U);
  EXPECT_EQ(file.row_group_num_rows(0), kRowsPerGroup);
  EXPECT_EQ(file.row_group_num_rows(1), kRowsPerGroup);

  struct Expectation {
    const char* name;
    LeafType type;
    LeafConverted converted;
    bool optional;
  };
  const Expectation expected[] = {
      {"ts", LeafType::INT64, LeafConverted::NONE, true},
      {"seq", LeafType::INT64, LeafConverted::NONE, false},
      {"px", LeafType::DOUBLE, LeafConverted::NONE, true},
      {"sz", LeafType::INT32, LeafConverted::UINT_32, true},
      {"flag", LeafType::INT32, LeafConverted::INT_8, true},
      {"day", LeafType::INT32, LeafConverted::DATE, true},
      {"iv", LeafType::DOUBLE, LeafConverted::NONE, true},
      {"sym", LeafType::BYTE_ARRAY, LeafConverted::UTF8, true},
      {"venue", LeafType::BYTE_ARRAY, LeafConverted::UTF8, true},
  };
  ASSERT_EQ(file.leaves().size(), sizeof(expected) / sizeof(expected[0]));
  for (std::size_t index = 0; index < file.leaves().size(); ++index) {
    EXPECT_EQ(file.leaves()[index].name, expected[index].name);
    EXPECT_EQ(file.leaves()[index].type, expected[index].type) << expected[index].name;
    EXPECT_EQ(file.leaves()[index].converted, expected[index].converted)
        << expected[index].name;
    EXPECT_EQ(file.leaves()[index].optional, expected[index].optional) << expected[index].name;
    // Column projection is by leaf index; the name resolves to that index.
    const qr::parquet::FileExpected<std::size_t> resolved =
        file.leaf_index(expected[index].name);
    ASSERT_TRUE(resolved.has_value());
    EXPECT_EQ(resolved.value(), index);
  }
}

TEST_P(ParquetValues, PlainAndDictionaryLeavesDecodeToTheDerivedLiterals) {
  const qr::parquet::FileExpected<File> opened = File::open(fixture(GetParam()));
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const File& file = opened.value();
  check_integer_leaf(file, "ts", kTs);
  check_integer_leaf(file, "seq", kSeq);
  check_integer_leaf(file, "px", kPxBits);
  check_integer_leaf(file, "sz", kSz);
  check_integer_leaf(file, "flag", kFlag);
  check_integer_leaf(file, "day", kDay);
  check_integer_leaf(file, "iv", kIvBits);
  check_string_leaf(file, "sym", kSym);
  check_string_leaf(file, "venue", kVenue);
}

TEST_P(ParquetValues, NullCountsMatchTheDerivedLiterals) {
  const qr::parquet::FileExpected<File> opened = File::open(fixture(GetParam()));
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const File& file = opened.value();
  for (std::size_t leaf = 0; leaf < file.leaves().size(); ++leaf) {
    const WholeColumn whole = read_whole(file, leaf);
    EXPECT_EQ(whole.null_count, kNullCounts[leaf]) << file.leaves()[leaf].name;
  }
}

TEST_P(ParquetValues, WholeFileDigestsMatchTheDerivedLiterals) {
  const qr::parquet::FileExpected<File> opened = File::open(fixture(GetParam()));
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const File& file = opened.value();
  DecodeWorkspace workspace;
  ColumnData column;
  for (std::size_t leaf = 0; leaf < file.leaves().size(); ++leaf) {
    // The committed digest is over the WHOLE column, so the two row groups are
    // combined the way each rule combines: sum, xor, or a rolling FNV-1a.
    std::uint64_t combined = 0;
    bool first = true;
    std::vector<std::uint8_t> byte_stream;
    for (std::size_t group = 0; group < file.num_row_groups(); ++group) {
      const qr::parquet::FileExpected<std::int64_t> rows =
          file.read_column(group, leaf, workspace, column);
      ASSERT_TRUE(rows.has_value()) << rows.error().message();
      if (column.type == LeafType::BYTE_ARRAY) {
        for (std::int64_t row = 0; row < column.num_rows; ++row) {
          if (column.is_null(row)) {
            continue;
          }
          const std::string_view value = column.byte_array(row);
          const std::uint32_t length = static_cast<std::uint32_t>(value.size());
          for (unsigned shift = 0; shift < 32; shift += 8) {
            byte_stream.push_back(static_cast<std::uint8_t>((length >> shift) & 0xFFU));
          }
          byte_stream.insert(byte_stream.end(), value.begin(), value.end());
        }
      } else if (column.type == LeafType::DOUBLE) {
        combined ^= qr::parquet::column_digest(column);
      } else {
        combined += qr::parquet::column_digest(column);
      }
      first = false;
    }
    (void)first;
    if (file.leaves()[leaf].type == LeafType::BYTE_ARRAY) {
      // Rebuild the FNV-1a over the concatenated stream, the exact rule the
      // generator applies over the whole column.
      std::uint64_t digest = 0xCBF29CE484222325ULL;
      for (std::uint8_t byte : byte_stream) {
        digest ^= static_cast<std::uint64_t>(byte);
        digest *= 0x100000001B3ULL;
      }
      combined = digest;
    }
    EXPECT_EQ(static_cast<std::int64_t>(combined), kDigests[leaf])
        << file.leaves()[leaf].name;
  }
}

INSTANTIATE_TEST_SUITE_P(PageVersions, ParquetValues,
                         ::testing::Values("qr_good_v1.parquet", "qr_good_v2.parquet"),
                         [](const ::testing::TestParamInfo<const char*>& info) {
                           return std::string(info.param).find("v2") != std::string::npos
                                      ? "DataPageV2"
                                      : "DataPageV1";
                         });

TEST(ParquetPageVersions, V1AndV2DecodeToByteIdenticalOutput) {
  const qr::parquet::FileExpected<File> v1 = File::open(fixture("qr_good_v1.parquet"));
  const qr::parquet::FileExpected<File> v2 = File::open(fixture("qr_good_v2.parquet"));
  ASSERT_TRUE(v1.has_value()) << v1.error().message();
  ASSERT_TRUE(v2.has_value()) << v2.error().message();
  DecodeWorkspace workspace;
  ColumnData column;
  std::vector<std::uint8_t> v1_bytes;
  std::vector<std::uint8_t> v2_bytes;
  for (std::size_t group = 0; group < 2; ++group) {
    for (std::size_t leaf = 0; leaf < v1.value().leaves().size(); ++leaf) {
      ASSERT_TRUE(v1.value().read_column(group, leaf, workspace, column).has_value());
      qr::parquet::append_serialized(column, v1_bytes);
      ASSERT_TRUE(v2.value().read_column(group, leaf, workspace, column).has_value());
      qr::parquet::append_serialized(column, v2_bytes);
    }
  }
  EXPECT_EQ(v1_bytes, v2_bytes)
      << "the v1 and v2 page shapes carry the same values and must decode identically";
}

TEST(ParquetStatistics, RowGroupTimestampStatisticsAreExposedForPruning) {
  const qr::parquet::FileExpected<File> opened = File::open(fixture("qr_good_v1.parquet"));
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const File& file = opened.value();
  const qr::parquet::FileExpected<std::size_t> ts = file.leaf_index("ts");
  ASSERT_TRUE(ts.has_value());

  const qr::parquet::Int64Stats first = file.int64_stats(0, ts.value());
  ASSERT_TRUE(first.present);
  EXPECT_EQ(first.min, kTs[0]);
  EXPECT_EQ(first.max, kTs[kRowsPerGroup - 1]);

  const qr::parquet::Int64Stats second = file.int64_stats(1, ts.value());
  ASSERT_TRUE(second.present);
  EXPECT_EQ(second.min, kTs[kRowsPerGroup]);
  EXPECT_EQ(second.max, kTs[kRows - 1]);
}

TEST(ParquetStatistics, RthPruningKeepsExactlyTheOverlappingRowGroups) {
  const qr::parquet::FileExpected<File> opened = File::open(fixture("qr_good_v1.parquet"));
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const File& file = opened.value();
  const std::size_t ts = file.leaf_index("ts").value();

  EXPECT_EQ(file.rth_row_groups(ts, kTs[0], kTs[kRowsPerGroup - 1] + 1),
            (std::vector<std::size_t>{0}));
  EXPECT_EQ(file.rth_row_groups(ts, kTs[kRowsPerGroup], kTs[kRows - 1] + 1),
            (std::vector<std::size_t>{1}));
  EXPECT_EQ(file.rth_row_groups(ts, kTs[0], kTs[kRows - 1] + 1),
            (std::vector<std::size_t>{0, 1}));
  EXPECT_TRUE(file.rth_row_groups(ts, kTs[kRows - 1] + 1, kTs[kRows - 1] + 2).empty());
}

TEST(ParquetStatistics, MissingStatisticsKeepEveryRowGroupBecausePruningIsOnlySpeed) {
  const qr::parquet::FileExpected<File> opened = File::open(fixture("qr_good_v1.parquet"));
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const File& file = opened.value();
  // `seq` carries no statistics at all: pruning must degrade to "keep all",
  // never to "keep none" (select_v2/src/sources/mod.rs:211-214).
  const std::size_t seq = file.leaf_index("seq").value();
  EXPECT_FALSE(file.int64_stats(0, seq).present);
  EXPECT_EQ(file.rth_row_groups(seq, 0, 1), (std::vector<std::size_t>{0, 1}));
}

TEST(ParquetArena, TheArenaIsReusedAcrossPagesAndChunksInsteadOfReallocated) {
  const qr::parquet::FileExpected<File> opened = File::open(fixture("qr_good_v1.parquet"));
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const File& file = opened.value();
  DecodeWorkspace workspace;
  ColumnData column;
  ASSERT_TRUE(file.read_column(0, 0, workspace, column).has_value());
  const std::size_t after_first = workspace.arena.bytes_reserved();
  ASSERT_GT(after_first, 0U);
  std::size_t high_water = after_first;
  for (std::size_t group = 0; group < file.num_row_groups(); ++group) {
    for (std::size_t leaf = 0; leaf < file.leaves().size(); ++leaf) {
      ASSERT_TRUE(file.read_column(group, leaf, workspace, column).has_value());
      high_water = std::max(high_water, workspace.arena.bytes_reserved());
    }
  }
  // Growth is bounded by the largest single page, not by the number of pages:
  // the buffers are reused, never re-allocated per page.
  EXPECT_LE(high_water, 64U * 1024U);
  workspace.arena.release();
  EXPECT_EQ(workspace.arena.bytes_reserved(), 0U);
}

TEST(ParquetDictionary, TheDictionaryCacheIsRebuiltPerChunkNotCarriedAcross) {
  const qr::parquet::FileExpected<File> opened = File::open(fixture("qr_good_v1.parquet"));
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const File& file = opened.value();
  DecodeWorkspace workspace;
  ColumnData column;
  // Read a dictionary-encoded BYTE_ARRAY chunk, then a PLAIN INT64 chunk. If
  // the cache leaked across chunks, the second read would find a stale
  // dictionary of the wrong type.
  const std::size_t sym = file.leaf_index("sym").value();
  const std::size_t ts = file.leaf_index("ts").value();
  ASSERT_TRUE(file.read_column(0, sym, workspace, column).has_value());
  EXPECT_TRUE(workspace.dictionary.present);
  EXPECT_EQ(workspace.dictionary.count, 4U);
  ASSERT_TRUE(file.read_column(0, ts, workspace, column).has_value());
  EXPECT_FALSE(workspace.dictionary.present)
      << "a PLAIN chunk must clear the previous chunk's dictionary";
  ASSERT_TRUE(file.read_column(1, sym, workspace, column).has_value());
  EXPECT_TRUE(workspace.dictionary.present);
}

TEST(ParquetDecode, TwoRunsOverAFixtureAreByteIdentical) {
  std::vector<std::uint8_t> runs[2];
  for (int attempt = 0; attempt < 2; ++attempt) {
    const qr::parquet::FileExpected<File> opened = File::open(fixture("qr_good_v1.parquet"));
    ASSERT_TRUE(opened.has_value()) << opened.error().message();
    DecodeWorkspace workspace;
    ColumnData column;
    for (std::size_t group = 0; group < opened.value().num_row_groups(); ++group) {
      for (std::size_t leaf = 0; leaf < opened.value().leaves().size(); ++leaf) {
        ASSERT_TRUE(opened.value().read_column(group, leaf, workspace, column).has_value());
        qr::parquet::append_serialized(column, runs[attempt]);
      }
    }
  }
  EXPECT_EQ(runs[0], runs[1]);
}

}  // namespace
