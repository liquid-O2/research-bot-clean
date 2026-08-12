// Rowgroup-addressed session decoding: the four independent identity checks,
// the column wall, and the 917 scope wall (AMENDMENT 2026-08-12-c).
#include <gtest/gtest.h>

#include <string>
#include <vector>

#include "candidates_test_support.hpp"
#include "qr_candidates/roster.hpp"
#include "qr_candidates/rowgroup_table.hpp"

namespace {

using namespace qr::candidates;          // NOLINT(build/namespaces)
using namespace qr::candidates::testing;  // NOLINT(build/namespaces)
using qr::Expected;

constexpr std::size_t kFixtureRowGroups = 6;

std::vector<std::string_view> as_vector(const auto& array) {
  return std::vector<std::string_view>(array.begin(), array.end());
}

SessionIndex load_index(const std::string& name) {
  auto index = SessionIndex::parse_without_digest_gate(read_whole_file(fixture_path(name)));
  EXPECT_TRUE(index.has_value()) << (index.has_value() ? "" : index.error().message());
  return index.has_value() ? std::move(index).value() : SessionIndex{};
}

Expected<RowGroupTable, qr::Refusal> open_projection(
    const std::string& parquet = "projection_good.parquet",
    const std::string& index = "projection_index.tsv") {
  return RowGroupTable::open(fixture_path(parquet), {}, load_index(index),
                             as_vector(kProjectionAllowlist), as_vector(kProjectionForbidden),
                             kFixtureRowGroups);
}

Expected<RowGroupTable, qr::Refusal> open_registry(
    const std::string& parquet = "registry_good.parquet",
    const std::string& index = "registry_index.tsv") {
  return RowGroupTable::open(fixture_path(parquet), {}, load_index(index),
                             as_vector(kRegistryAllowlist), as_vector(kRegistryForbidden),
                             kFixtureRowGroups);
}

// --- the session index -------------------------------------------------------

TEST(SessionIndexWall, ParsesTheDenseLadderAndRefusesPastNineSeventeen) {
  const SessionIndex index = load_index("projection_index.tsv");
  const auto row = index.at(2);
  ASSERT_TRUE(row.has_value());
  EXPECT_EQ(row.value()->ordinal, 2U);
  EXPECT_EQ(row.value()->day, Literals().text("day", "2"));
  EXPECT_EQ(kMaxSessionOrdinal, 917U);
  const auto past = index.at(kMaxSessionOrdinal + 1U);
  ASSERT_FALSE(past.has_value());
  EXPECT_EQ(past.error().code(), qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE);
}

TEST(SessionIndexWall, ARowWhoseOrdinalIsNotItsPositionRefuses) {
  auto index = SessionIndex::parse_without_digest_gate(
      read_whole_file(fixture_path("projection_index_bad_ordinal.tsv")));
  ASSERT_FALSE(index.has_value());
  EXPECT_EQ(index.error().code(), qr::RefusalCode::OUT_OF_ORDER);
}

TEST(SessionIndexWall, AWrongHeaderRefuses) {
  auto index = SessionIndex::parse_without_digest_gate("ordinal\tday\trow\n0\t2022-01-03\t1\n");
  ASSERT_FALSE(index.has_value());
  EXPECT_EQ(index.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
}

TEST(SessionIndexWall, ANonCivilDayRefuses) {
  auto index = SessionIndex::parse_without_digest_gate("ordinal\tday\trows\n0\t2022-1-3\t1\n");
  ASSERT_FALSE(index.has_value());
  EXPECT_EQ(index.error().code(), qr::RefusalCode::MALFORMED_CIVIL_DATE);
}

TEST(SessionIndexWall, ADigestThatDoesNotMatchRefusesBeforeAnythingIsParsed) {
  auto index = SessionIndex::load(fixture_path("projection_index.tsv"), std::string(64, 'a'));
  ASSERT_FALSE(index.has_value());
  EXPECT_EQ(index.error().code(), qr::RefusalCode::SOURCE_AUTHENTICATION_FAILED);
}

// --- the column wall ---------------------------------------------------------

TEST(ColumnWall, TheProjectionAllowlistIsExactlyTheEightNamedColumns) {
  EXPECT_EQ(kProjectionAllowlist.size(), 8U);
  auto table = open_projection();
  ASSERT_TRUE(table.has_value()) << (table.has_value() ? "" : table.error().message());
  auto columns = table.value().read_session(2);
  ASSERT_TRUE(columns.has_value()) << (columns.has_value() ? "" : columns.error().message());
  EXPECT_EQ(columns.value().num_columns(), 8U);
  for (const std::string_view name : kProjectionAllowlist) {
    EXPECT_TRUE(columns.value().column(name).has_value()) << name;
  }
}

TEST(ColumnWall, TheSideColumnIsUnreachableFromADecodedSession) {
  // `side` is the very answer this work package must derive. It exists in the
  // file, it is in the forbidden list, and no decoded session can reach it.
  auto table = open_projection();
  ASSERT_TRUE(table.has_value());
  auto columns = table.value().read_session(2);
  ASSERT_TRUE(columns.has_value());
  const auto side = columns.value().column("side");
  ASSERT_FALSE(side.has_value());
  EXPECT_EQ(side.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
}

TEST(ColumnWall, ThePhysicalClusterIdIsUnreachableFromADecodedRegistrySession) {
  auto table = open_registry();
  ASSERT_TRUE(table.has_value());
  auto columns = table.value().read_session(2);
  ASSERT_TRUE(columns.has_value());
  EXPECT_FALSE(columns.value().column("physical_cluster_id").has_value());
  EXPECT_FALSE(columns.value().column("cluster_disposition").has_value());
  EXPECT_FALSE(columns.value().column("cluster_size").has_value());
}

TEST(ColumnWall, AnAllowlistThatNamesAForbiddenColumnRefusesBeforeTheFileIsOpened) {
  std::vector<std::string_view> allow = as_vector(kProjectionAllowlist);
  allow.emplace_back("side");
  auto table = RowGroupTable::open(fixture_path("projection_good.parquet"), {},
                                   load_index("projection_index.tsv"), allow,
                                   as_vector(kProjectionForbidden), kFixtureRowGroups);
  ASSERT_FALSE(table.has_value());
  EXPECT_EQ(table.error().code(), qr::RefusalCode::CONFIG);
}

TEST(ColumnWall, AForbiddenColumnThatVanishedFromTheSchemaRefuses) {
  // A guard that guards nothing is worse than no guard: if a rename made a
  // forbidden column disappear, this must be loud.
  std::vector<std::string_view> forbidden = as_vector(kProjectionForbidden);
  forbidden.emplace_back("a_column_that_does_not_exist");
  auto table = RowGroupTable::open(fixture_path("projection_good.parquet"), {},
                                   load_index("projection_index.tsv"),
                                   as_vector(kProjectionAllowlist), forbidden, kFixtureRowGroups);
  ASSERT_FALSE(table.has_value());
  EXPECT_EQ(table.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
}

TEST(ColumnWall, ARepeatedAllowlistEntryRefuses) {
  std::vector<std::string_view> allow = as_vector(kProjectionAllowlist);
  allow.emplace_back("day");
  auto table = RowGroupTable::open(fixture_path("projection_good.parquet"), {},
                                   load_index("projection_index.tsv"), allow,
                                   as_vector(kProjectionForbidden), kFixtureRowGroups);
  ASSERT_FALSE(table.has_value());
  EXPECT_EQ(table.error().code(), qr::RefusalCode::CONFIG);
}

TEST(ColumnWall, AnEmptyAllowlistIsNotAProjection) {
  auto table = RowGroupTable::open(fixture_path("projection_good.parquet"), {},
                                   load_index("projection_index.tsv"), {},
                                   as_vector(kProjectionForbidden), kFixtureRowGroups);
  ASSERT_FALSE(table.has_value());
  EXPECT_EQ(table.error().code(), qr::RefusalCode::CONFIG);
}

// --- the four identity checks -------------------------------------------------

TEST(RowGroupIdentity, DecodesPhysicalRowGroupIAsSessionI) {
  auto table = open_projection();
  ASSERT_TRUE(table.has_value());
  for (std::uint32_t ordinal = 0; ordinal < kFixtureRowGroups; ++ordinal) {
    auto columns = table.value().read_session(ordinal);
    ASSERT_TRUE(columns.has_value()) << ordinal;
    EXPECT_EQ(columns.value().ordinal(), ordinal);
    EXPECT_EQ(columns.value().day(), Literals().text("day", std::to_string(ordinal)));
  }
}

TEST(RowGroupIdentity, DayStatisticsThatSpanTwoDaysRefuse) {
  auto table = open_projection("projection_bad_day_stats.parquet");
  ASSERT_TRUE(table.has_value());
  auto columns = table.value().read_session(2);
  ASSERT_FALSE(columns.has_value());
  EXPECT_EQ(columns.error().code(), qr::RefusalCode::WRONG_CIVIL_DAY);
}

TEST(RowGroupIdentity, DayStatisticsThatNameADifferentDayThanTheIndexRefuse) {
  auto table = open_projection("projection_wrong_day_stats.parquet");
  ASSERT_TRUE(table.has_value());
  auto columns = table.value().read_session(2);
  ASSERT_FALSE(columns.has_value());
  EXPECT_EQ(columns.error().code(), qr::RefusalCode::WRONG_CIVIL_DAY);
}

TEST(RowGroupIdentity, AbsentDayStatisticsRefuseRatherThanFallingBackToTheValues) {
  // The statistics are an INDEPENDENT witness to the row group's identity.
  // "Trust the values instead" would delete the independence.
  auto table = open_projection("projection_no_day_stats.parquet");
  ASSERT_TRUE(table.has_value());
  auto columns = table.value().read_session(2);
  ASSERT_FALSE(columns.has_value());
  EXPECT_EQ(columns.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
}

TEST(RowGroupIdentity, ADecodedRowCarryingANeighboursDayRefusesDespiteCleanStatistics) {
  auto table = open_projection("projection_smuggled_day.parquet");
  ASSERT_TRUE(table.has_value());
  auto columns = table.value().read_session(2);
  ASSERT_FALSE(columns.has_value());
  EXPECT_EQ(columns.error().code(), qr::RefusalCode::WRONG_CIVIL_DAY);
}

TEST(RowGroupIdentity, ADecodedRowCountThatDiffersFromTheIndexRefuses) {
  auto table = open_projection("projection_good.parquet", "projection_index_bad_rows.tsv");
  ASSERT_TRUE(table.has_value());
  auto columns = table.value().read_session(2);
  ASSERT_FALSE(columns.has_value());
  EXPECT_EQ(columns.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}

TEST(RowGroupIdentity, AnOrdinalPastTheWallNeverBecomesARowGroupIndex) {
  auto table = open_projection();
  ASSERT_TRUE(table.has_value());
  const auto columns = table.value().read_session(kMaxSessionOrdinal + 1U);
  ASSERT_FALSE(columns.has_value());
  EXPECT_EQ(columns.error().code(), qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE);
}

TEST(RowGroupIdentity, AnOrdinalWithNoIndexRowRefuses) {
  auto table = open_projection();
  ASSERT_TRUE(table.has_value());
  const auto columns = table.value().read_session(kFixtureRowGroups + 1);
  ASSERT_FALSE(columns.has_value());
  EXPECT_EQ(columns.error().code(), qr::RefusalCode::UNKNOWN_SESSION);
}

TEST(RowGroupIdentity, AFileWithTheWrongRowGroupCountRefuses) {
  auto table = RowGroupTable::open(fixture_path("projection_good.parquet"), {},
                                   load_index("projection_index.tsv"),
                                   as_vector(kProjectionAllowlist),
                                   as_vector(kProjectionForbidden), kPublicationRowGroups);
  ASSERT_FALSE(table.has_value());
  EXPECT_EQ(table.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
}

TEST(RowGroupIdentity, TwoDecodesOfOneSessionAgreeCellForCell) {
  auto table = open_projection();
  ASSERT_TRUE(table.has_value());
  auto first = table.value().read_session(2);
  auto second = table.value().read_session(2);
  ASSERT_TRUE(first.has_value());
  ASSERT_TRUE(second.has_value());
  ASSERT_EQ(first.value().num_rows(), second.value().num_rows());
  for (std::size_t column = 0; column < first.value().num_columns(); ++column) {
    for (std::int64_t row = 0; row < first.value().num_rows(); ++row) {
      ASSERT_EQ(first.value().is_null(column, row), second.value().is_null(column, row));
      EXPECT_EQ(first.value().value(column, row), second.value().value(column, row));
    }
  }
}

TEST(RowGroupIdentity, ARequiredLeafCarriesNoNullsSoAnAbsentCellIsAnEmptyValue) {
  // The bound publications are 100% REQUIRED leaves
  // (tests/fixtures/publication_repetition_census.tsv), so there is no null
  // STATE in this family at all: an absent physical key arrives as an empty
  // cell and must be refused on its SHAPE, never mistaken for a present value.
  auto table = open_projection("projection_join_physical_empty.parquet");
  ASSERT_TRUE(table.has_value()) << (table.has_value() ? "" : table.error().message());
  auto columns = table.value().read_session(2);
  ASSERT_TRUE(columns.has_value()) << (columns.has_value() ? "" : columns.error().message());
  const auto physical = columns.value().column("physical_event_id");
  ASSERT_TRUE(physical.has_value());
  bool saw_empty = false;
  for (std::int64_t row = 0; row < columns.value().num_rows(); ++row) {
    EXPECT_FALSE(columns.value().is_null(physical.value(), row)) << row;
    saw_empty = saw_empty || columns.value().value(physical.value(), row).empty();
  }
  EXPECT_TRUE(saw_empty);
}

// --- the per-family dialect profiles (ruling CC-003) -------------------------

TEST(DialectProfiles, ThePublicationProfileRefusesAnOptionalLeaf) {
  // OPTIONAL is lawful in the TOKEN CORPUS and unheard of in the publications.
  // Each family is gated against its own measured census, so this file is
  // refused here and accepted there — that asymmetry IS the ruling.
  auto table = open_projection("projection_optional_leaves.parquet");
  ASSERT_FALSE(table.has_value()) << "an OPTIONAL-leaf publication was admitted";
  EXPECT_EQ(table.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);

  auto as_publication = qr::parquet::File::open(fixture_path("projection_optional_leaves.parquet"),
                                                qr::parquet::DialectProfile::PUBLICATION);
  ASSERT_FALSE(as_publication.has_value());
  EXPECT_NE(as_publication.error().message().find("OPTIONAL"), std::string::npos)
      << as_publication.error().message();
  EXPECT_NE(as_publication.error().message().find("PUBLICATION"), std::string::npos)
      << as_publication.error().message();

  // THE CORPUS PIN IS UNTOUCHED: the very same bytes open under CORPUS.
  auto as_corpus = qr::parquet::File::open(fixture_path("projection_optional_leaves.parquet"),
                                           qr::parquet::DialectProfile::CORPUS);
  ASSERT_TRUE(as_corpus.has_value()) << as_corpus.error().message();
  EXPECT_EQ(as_corpus.value().profile(), qr::parquet::DialectProfile::CORPUS);
}

TEST(DialectProfiles, TheCorpusProfileRefusesTheRequiredPublicationShape) {
  // The mirror image, which is what makes the two profiles a partition rather
  // than a widening: a publication file is refused by a corpus reader.
  auto as_corpus = qr::parquet::File::open(fixture_path("projection_good.parquet"),
                                           qr::parquet::DialectProfile::CORPUS);
  ASSERT_FALSE(as_corpus.has_value()) << "a REQUIRED publication was admitted as corpus";
  EXPECT_NE(as_corpus.error().message().find("REQUIRED"), std::string::npos)
      << as_corpus.error().message();
  auto as_publication = qr::parquet::File::open(fixture_path("projection_good.parquet"),
                                                qr::parquet::DialectProfile::PUBLICATION);
  ASSERT_TRUE(as_publication.has_value()) << as_publication.error().message();
  EXPECT_EQ(as_publication.value().profile(), qr::parquet::DialectProfile::PUBLICATION);
}

TEST(DialectProfiles, ThePublicationProfileRefusesEveryTupleOutsideItsMeasuredCensus) {
  // The measured publication census is ZSTD / {PLAIN,RLE,RLE_DICTIONARY} /
  // BYTE_ARRAY / UTF8 / REQUIRED / flat. Anything else is a producer change and
  // must be a loud refusal, not a silent admission.
  for (const char* name : {"projection_snappy_codec.parquet", "projection_int64_leaf.parquet",
                           "projection_no_converted.parquet"}) {
    auto table = open_projection(name);
    ASSERT_FALSE(table.has_value()) << name << " was admitted";
    EXPECT_EQ(table.error().code(), qr::RefusalCode::SCHEMA_MISMATCH) << name;
    auto direct = qr::parquet::File::open(fixture_path(name),
                                          qr::parquet::DialectProfile::PUBLICATION);
    ASSERT_FALSE(direct.has_value()) << name;
    EXPECT_NE(direct.error().message().find("PUBLICATION"), std::string::npos)
        << name << ": " << direct.error().message();
  }
}

TEST(DialectProfiles, ThePublicationReaderDeclaresItsFamilyRatherThanInheritingADefault) {
  // A default-profile open of a publication must fail, which is the mechanical
  // proof that RowGroupTable passes PUBLICATION on purpose.
  auto defaulted = qr::parquet::File::open(fixture_path("projection_good.parquet"));
  ASSERT_FALSE(defaulted.has_value());
  auto table = open_projection();
  ASSERT_TRUE(table.has_value()) << (table.has_value() ? "" : table.error().message());
}

}  // namespace
