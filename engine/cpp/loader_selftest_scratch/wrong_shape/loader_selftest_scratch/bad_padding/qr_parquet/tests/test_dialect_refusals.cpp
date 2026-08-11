// The fail-closed wall.
//
// SPEC (design/DESIGN_SUBSTRATE.md M1 qr_parquet bullet, verbatim):
//   "ANY tuple outside the census = typed file refusal"
// and the WP3 brief's expansion: "ANY (codec, encoding, physical/converted
// type, repetition) tuple outside the pinned set = typed FILE refusal naming
// the path — fail-closed, never degrade".
//
// Every fixture read here is written by the committed generator
// engine/cpp/tests/fixtures/make_parquet_fixtures.py; not one byte of any of
// them was edited by hand.
#include <gtest/gtest.h>

#include <string>

#include "qr_parquet/reader.hpp"

namespace {

using qr::RefusalCode;
using qr::parquet::ColumnData;
using qr::parquet::DecodeWorkspace;
using qr::parquet::File;

std::string fixture(const char* name) {
  return std::string(QR_PARQUET_FIXTURE_DIR) + "/" + name;
}

qr::parquet::FileRefusal no_refusal(const char* name) {
  return qr::parquet::FileRefusal(
      qr::Refusal(RefusalCode::CONFIG, "test", "the wall did not refuse"), fixture(name));
}

/// Opens a fixture that must be refused AT OPEN, and returns the refusal.
qr::parquet::FileRefusal refused_open(const char* name) {
  qr::parquet::FileExpected<File> opened = File::open(fixture(name));
  if (opened.has_value()) {
    ADD_FAILURE() << name << " was accepted at open; the wall is open";
    return no_refusal(name);
  }
  return opened.error();
}

TEST(ParquetWall, MissingLeadingMagicIsADecodeRefusalNamingThePath) {
  const qr::parquet::FileRefusal refusal = refused_open("qr_missing_magic.parquet");
  EXPECT_EQ(refusal.code(), RefusalCode::DECODE_FAILED);
  EXPECT_EQ(refusal.path(), fixture("qr_missing_magic.parquet"));
  EXPECT_NE(refusal.message().find("qr_missing_magic.parquet"), std::string::npos);
  EXPECT_NE(refusal.message().find("magic"), std::string::npos);
}

TEST(ParquetWall, BadFooterLengthIsADecodeRefusalAndNeverReadsPastTheMapping) {
  const qr::parquet::FileRefusal refusal = refused_open("qr_bad_footer_length.parquet");
  EXPECT_EQ(refusal.code(), RefusalCode::DECODE_FAILED);
  EXPECT_NE(refusal.message().find("footer length"), std::string::npos);
}

TEST(ParquetWall, UnknownCodecIsRefusedByNameBeforeAnyPageIsTouched) {
  const qr::parquet::FileRefusal refusal = refused_open("qr_unknown_codec.parquet");
  EXPECT_EQ(refusal.code(), RefusalCode::SCHEMA_MISMATCH);
  EXPECT_NE(refusal.message().find("SNAPPY"), std::string::npos)
      << "the refusal must NAME the offending codec: " << refusal.message();
  EXPECT_NE(refusal.message().find("codec"), std::string::npos);
}

TEST(ParquetWall, UnknownChunkEncodingIsRefusedByNameAtOpen) {
  const qr::parquet::FileRefusal refusal = refused_open("qr_unknown_chunk_encoding.parquet");
  EXPECT_EQ(refusal.code(), RefusalCode::SCHEMA_MISMATCH);
  EXPECT_NE(refusal.message().find("DELTA_BINARY_PACKED"), std::string::npos)
      << refusal.message();
}

TEST(ParquetWall, UnpinnedPhysicalTypeIsRefusedByName) {
  const qr::parquet::FileRefusal refusal = refused_open("qr_bad_physical_type.parquet");
  EXPECT_EQ(refusal.code(), RefusalCode::SCHEMA_MISMATCH);
  EXPECT_NE(refusal.message().find("FLOAT"), std::string::npos) << refusal.message();
}

TEST(ParquetWall, UnpinnedConvertedTypeIsRefusedByName) {
  const qr::parquet::FileRefusal refusal = refused_open("qr_bad_converted_type.parquet");
  EXPECT_EQ(refusal.code(), RefusalCode::SCHEMA_MISMATCH);
  EXPECT_NE(refusal.message().find("DECIMAL"), std::string::npos) << refusal.message();
}

TEST(ParquetWall, RepeatedLeafIsRefusedBecauseTheDialectIsFlatOnly) {
  const qr::parquet::FileRefusal refusal = refused_open("qr_repeated_leaf.parquet");
  EXPECT_EQ(refusal.code(), RefusalCode::SCHEMA_MISMATCH);
  EXPECT_NE(refusal.message().find("REPEATED"), std::string::npos) << refusal.message();
}

TEST(ParquetWall, RequiredLeafIsRefusedBecauseTheCensusOnlyEverObservedOptional) {
  // Orchestrator ruling 2026-08-10: census-pinned fail-closed. The measured
  // authority (dialect_census.tsv, 8,726 files) never carried a REQUIRED leaf,
  // so a REQUIRED leaf is a LOUD REFUSAL and a change-control census update --
  // never a silent widening of the reader.
  const qr::parquet::FileRefusal refusal = refused_open("qr_required_leaf.parquet");
  EXPECT_EQ(refusal.code(), RefusalCode::SCHEMA_MISMATCH);
  EXPECT_NE(refusal.message().find("REQUIRED"), std::string::npos) << refusal.message();
  EXPECT_NE(refusal.message().find("repetition"), std::string::npos) << refusal.message();
}

TEST(ParquetWall, NestedSchemaIsRefusedBecauseTheDialectIsFlatOnly) {
  const qr::parquet::FileRefusal refusal = refused_open("qr_nested_schema.parquet");
  EXPECT_EQ(refusal.code(), RefusalCode::SCHEMA_MISMATCH);
  EXPECT_NE(refusal.message().find("flat"), std::string::npos) << refusal.message();
}

/// Decodes every column of every row group and returns the FIRST refusal.
/// Corruptions that live in the pages, not the footer, surface here.
qr::parquet::FileRefusal refused_decode(const char* name) {
  qr::parquet::FileExpected<File> opened = File::open(fixture(name));
  if (!opened.has_value()) {
    ADD_FAILURE() << name << " must open cleanly; its corruption lives in a page. Got: "
                  << opened.error().message();
    return no_refusal(name);
  }
  const File& file = opened.value();
  DecodeWorkspace workspace;
  ColumnData column;
  for (std::size_t group = 0; group < file.num_row_groups(); ++group) {
    for (std::size_t leaf = 0; leaf < file.leaves().size(); ++leaf) {
      qr::parquet::FileExpected<std::int64_t> rows =
          file.read_column(group, leaf, workspace, column);
      if (!rows.has_value()) {
        return rows.error();
      }
    }
  }
  ADD_FAILURE() << name << " decoded without a refusal; the page wall is open";
  return no_refusal(name);
}

TEST(ParquetWall, UnknownPageEncodingIsRefusedByNameAtDecode) {
  // The chunk metadata still declares only pinned encodings; the offending
  // encoding lives in the DATA PAGE header. The page-level gate must catch it,
  // so the footer gate cannot be the only wall.
  const qr::parquet::FileRefusal refusal = refused_decode("qr_unknown_encoding.parquet");
  EXPECT_EQ(refusal.code(), RefusalCode::SCHEMA_MISMATCH);
  EXPECT_NE(refusal.message().find("DELTA_BINARY_PACKED"), std::string::npos)
      << refusal.message();
}

TEST(ParquetWall, TruncatedPageIsADecodeRefusalNamingThePath) {
  const qr::parquet::FileRefusal refusal = refused_decode("qr_truncated_page.parquet");
  EXPECT_EQ(refusal.code(), RefusalCode::DECODE_FAILED);
  EXPECT_EQ(refusal.path(), fixture("qr_truncated_page.parquet"));
  EXPECT_NE(refusal.message().find("qr_truncated_page.parquet"), std::string::npos);
}

TEST(ParquetWall, DictionaryIndexOutOfRangeIsADecodeRefusalCarryingTheIndex) {
  const qr::parquet::FileRefusal refusal = refused_decode("qr_dict_index_oob.parquet");
  EXPECT_EQ(refusal.code(), RefusalCode::DECODE_FAILED);
  EXPECT_NE(refusal.message().find("dictionary index"), std::string::npos)
      << refusal.message();
  // The dictionary of `sym` has four entries; the generator writes index 4.
  EXPECT_EQ(refusal.context(), 4);
}

TEST(ParquetWall, ShortDefinitionLevelStreamIsADecodeRefusal) {
  const qr::parquet::FileRefusal refusal =
      refused_decode("qr_def_level_count_mismatch.parquet");
  EXPECT_EQ(refusal.code(), RefusalCode::DECODE_FAILED);
  EXPECT_NE(refusal.message().find("definition level"), std::string::npos)
      << refusal.message();
}

TEST(ParquetWall, AMissingFileIsAnIoRefusalNotACrash) {
  qr::parquet::FileExpected<File> opened = File::open(fixture("qr_does_not_exist.parquet"));
  ASSERT_FALSE(opened.has_value());
  EXPECT_EQ(opened.error().code(), RefusalCode::IO);
  EXPECT_NE(opened.error().message().find("qr_does_not_exist.parquet"), std::string::npos);
}

TEST(ParquetWall, AnUnknownColumnNameIsASchemaRefusalNotAGuess) {
  qr::parquet::FileExpected<File> opened = File::open(fixture("qr_good_v1.parquet"));
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  qr::parquet::FileExpected<std::size_t> index = opened.value().leaf_index("no_such_column");
  ASSERT_FALSE(index.has_value());
  EXPECT_EQ(index.error().code(), RefusalCode::SCHEMA_MISMATCH);
  EXPECT_NE(index.error().message().find("no_such_column"), std::string::npos);
}

TEST(ParquetWall, OutOfRangeRowGroupAndLeafIndicesAreRefusedNotUndefined) {
  qr::parquet::FileExpected<File> opened = File::open(fixture("qr_good_v1.parquet"));
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const File& file = opened.value();
  DecodeWorkspace workspace;
  ColumnData column;
  qr::parquet::FileExpected<std::int64_t> bad_group =
      file.read_column(file.num_row_groups(), 0, workspace, column);
  ASSERT_FALSE(bad_group.has_value());
  EXPECT_EQ(bad_group.error().code(), RefusalCode::CONFIG);
  qr::parquet::FileExpected<std::int64_t> bad_leaf =
      file.read_column(0, file.leaves().size(), workspace, column);
  ASSERT_FALSE(bad_leaf.has_value());
  EXPECT_EQ(bad_leaf.error().code(), RefusalCode::CONFIG);
}

}  // namespace
