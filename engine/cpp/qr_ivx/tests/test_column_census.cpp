// RED-FIRST FIXTURES for the CC-013 column census (qr_ivx/column_census.hpp).
//
// Every case below fails on a specific plausible mistake, named in its comment.
// The census is a RECEIPT for a change-control decision, so the verdict table
// and the "undefined vs zero" rules are the part that must not be wrong.
#include <gtest/gtest.h>

#include <cstdlib>
#include <limits>
#include <string>

#include "qr_ivx/column_census.hpp"
#include "qr_ivx/tsv.hpp"

namespace {

qr::ivx::ColumnStat populated(std::int64_t values, std::int64_t nulls, std::int64_t chunks) {
  qr::ivx::ColumnStat stat;
  stat.name = "vomma";
  stat.in_schema = true;
  stat.leaf = 23;
  stat.kind = qr::ivx::StatKind::DOUBLE;
  stat.chunks = chunks;
  stat.chunks_with_statistics = chunks;
  stat.chunks_with_null_count = chunks;
  stat.chunks_with_range = chunks;
  stat.num_values = values;
  stat.null_count = nulls;
  stat.has_range = true;
  stat.min_value = -1.5;
  stat.max_value = 4.25;
  return stat;
}

}  // namespace

// A column the schema does not carry is ABSENT — not "all null", which would
// read as "the vendor sends the column and leaves it empty" and would send the
// amendment the wrong way.
TEST(ColumnCensusVerdict, MissingFromSchemaIsAbsentNotAllNull) {
  qr::ivx::ColumnStat stat;
  stat.name = "ultima";
  stat.in_schema = false;
  EXPECT_EQ(qr::ivx::verdict_of(stat), qr::ivx::ColumnVerdict::ABSENT);
}

TEST(ColumnCensusVerdict, EveryValueNullIsAllNull) {
  qr::ivx::ColumnStat stat = populated(1000, 1000, 2);
  EXPECT_EQ(qr::ivx::verdict_of(stat), qr::ivx::ColumnVerdict::ALL_NULL);
}

// A PARTIAL null-count report cannot prove "all null": the unreported chunks
// might be full. The census must not upgrade a partial report into a verdict.
TEST(ColumnCensusVerdict, PartialNullCountsCannotProveAllNull) {
  qr::ivx::ColumnStat stat = populated(1000, 1000, 4);
  stat.chunks_with_null_count = 3;
  EXPECT_NE(qr::ivx::verdict_of(stat), qr::ivx::ColumnVerdict::ALL_NULL);
}

// A column that is present but pinned at zero everywhere is DEAD in the sense
// the amendment cares about, and it must be distinguishable from a real one.
TEST(ColumnCensusVerdict, ZeroEverywhereIsConstantZeroNotReal) {
  qr::ivx::ColumnStat stat = populated(1000, 0, 2);
  stat.min_value = 0.0;
  stat.max_value = 0.0;
  stat.chunks_zero_range = 2;
  EXPECT_EQ(qr::ivx::verdict_of(stat), qr::ivx::ColumnVerdict::CONSTANT_ZERO);
}

TEST(ColumnCensusVerdict, PopulatedWithRangeIsReal) {
  EXPECT_EQ(qr::ivx::verdict_of(populated(1000, 4, 2)), qr::ivx::ColumnVerdict::REAL);
}

// A NaN/Inf bound is not a range and must not be silently folded into one; it
// gets its own verdict so "real but dirty" never reads as "real".
TEST(ColumnCensusVerdict, NonFiniteBoundIsItsOwnVerdict) {
  qr::ivx::ColumnStat stat = populated(1000, 0, 3);
  stat.chunks_nonfinite_bound = 1;
  EXPECT_EQ(qr::ivx::verdict_of(stat), qr::ivx::ColumnVerdict::REAL_WITH_NONFINITE);
}

TEST(ColumnCensusVerdict, PopulatedWithoutAnyStoredRangeSaysSo) {
  qr::ivx::ColumnStat stat = populated(1000, 0, 2);
  stat.has_range = false;
  stat.chunks_with_range = 0;
  EXPECT_EQ(qr::ivx::verdict_of(stat), qr::ivx::ColumnVerdict::POPULATED_NO_RANGE);
}

// PRESENCE IS UNDEFINED, NEVER 100%, when the writer did not report null counts
// on every chunk. Returning 1e6 there would claim a fully populated column on
// the strength of missing evidence.
TEST(ColumnCensusPresence, UnreportedNullCountsAreUndefinedNotFull) {
  qr::ivx::ColumnStat stat = populated(1000, 0, 4);
  EXPECT_EQ(qr::ivx::presence_ppm(stat), 1'000'000);
  stat.chunks_with_null_count = 2;
  EXPECT_EQ(qr::ivx::presence_ppm(stat), -1);
}

TEST(ColumnCensusPresence, ExactIntegerFraction) {
  const qr::ivx::ColumnStat stat = populated(1000, 250, 1);
  EXPECT_EQ(qr::ivx::presence_ppm(stat), 750'000);
}

TEST(ColumnCensusPresence, NoRowsIsUndefined) {
  qr::ivx::ColumnStat stat = populated(0, 0, 0);
  EXPECT_EQ(qr::ivx::presence_ppm(stat), -1);
  EXPECT_EQ(qr::ivx::verdict_of(stat), qr::ivx::ColumnVerdict::NO_ROWS);
}

// The receipt has to say, per row, what the amendment would actually change.
// Mislabelling `implied_vol` as refused (or `vomma` as projected) would make
// the census unreadable as a change-control document.
TEST(ColumnCensusStanding, LabelsMatchAppendixB3) {
  EXPECT_EQ(qr::ivx::standing_of("implied_vol"), qr::ivx::SpecStanding::PROJECTED);
  EXPECT_EQ(qr::ivx::standing_of("vomma"), qr::ivx::SpecStanding::HARD_REFUSED);
  EXPECT_EQ(qr::ivx::standing_of("speed"), qr::ivx::SpecStanding::HARD_REFUSED);
  EXPECT_EQ(qr::ivx::standing_of("vega"), qr::ivx::SpecStanding::UNPROJECTED);
  EXPECT_EQ(qr::ivx::standing_of("iv_error"), qr::ivx::SpecStanding::UNPROJECTED);
}

// The candidate list must carry the CONTROL pair. A census where theta and
// vomma look identical is a census that measured nothing, and it can only be
// read as such if theta is in it.
TEST(ColumnCensusStanding, CandidateSetCarriesTheControls) {
  bool has_theta = false;
  bool has_implied_vol = false;
  for (const char* name : qr::ivx::kCandidateColumns) {
    has_theta = has_theta || std::string(name) == "theta";
    has_implied_vol = has_implied_vol || std::string(name) == "implied_vol";
  }
  EXPECT_TRUE(has_theta);
  EXPECT_TRUE(has_implied_vol);
}

// %.17g must ROUND-TRIP: a census whose numbers change under re-parse cannot be
// a receipt. And the three non-finite forms must be platform-stable tokens,
// because "nan" vs "-nan" would break two-run byte identity across compilers.
TEST(TsvFormatting, RoundTripsAndNamesNonFinite) {
  const double value = 0.1 + 0.2;
  EXPECT_EQ(std::strtod(qr::ivx::g17(value).c_str(), nullptr), value);
  EXPECT_EQ(qr::ivx::g17(std::numeric_limits<double>::quiet_NaN()), "NAN");
  EXPECT_EQ(qr::ivx::g17(std::numeric_limits<double>::infinity()), "INF");
  EXPECT_EQ(qr::ivx::g17(-std::numeric_limits<double>::infinity()), "-INF");
}

// An absent typed real must never present a NUMBER in the value column.
TEST(TsvFormatting, AbsentTypedRealNeverEmitsANumber) {
  qr::ivx::Report report;
  report.typed("scope", "key", "channel", qr::Typed<double>{42.0, qr::Validity::MISSING});
  ASSERT_EQ(report.rows().size(), 2U);
  EXPECT_EQ(report.rows()[0].value, "MISSING");
  EXPECT_EQ(report.rows()[1].metric, "channel_v");
  EXPECT_EQ(report.rows()[1].value, "MISSING");
}
