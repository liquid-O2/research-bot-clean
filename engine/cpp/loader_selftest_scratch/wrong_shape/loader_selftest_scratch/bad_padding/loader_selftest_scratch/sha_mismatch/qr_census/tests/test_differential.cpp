// qr_census/tests/test_differential.cpp — the differential's own laws.
//
// Every test here is proven able to fail: tests/red_ledger.tsv maps each id to
// a committed mutant patch and the log of the run where that mutant made it go
// red (FINAL_PLAN section 6, red-ledger law).
#include <algorithm>
#include <array>
#include <cstdint>
#include <numeric>
#include <string>
#include <vector>

#include <gtest/gtest.h>

#include "qr_census/differential.hpp"

namespace {

using qr::census::DiffCell;
using qr::census::DiffKind;
using qr::census::DiffStream;
using qr::census::SessionDiff;

/// Five compared quote cells, the way the reader would hand them over.
std::array<DiffCell, 5> quote_row(std::int64_t ts, std::int64_t bid_shares, std::int64_t bid_u6,
                                  std::int64_t ask_shares, std::int64_t ask_u6) {
  return {DiffCell{ts, 0.0, false}, DiffCell{bid_shares, 0.0, false}, DiffCell{bid_u6, 0.0, false},
          DiffCell{ask_shares, 0.0, false}, DiffCell{ask_u6, 0.0, false}};
}

std::string sha_of(const std::vector<std::array<DiffCell, 5>>& rows) {
  SessionDiff diff(DiffStream::StockQuotes, "2022-07-05", true);
  const std::array<bool, 5> mask{false, false, false, false, false};
  for (const auto& row : rows) {
    diff.push(row, mask);
  }
  diff.finish();
  return diff.row_sha256();
}

}  // namespace

// ---------------------------------------------------------------------------
// The intersection is a published, exact object.
// ---------------------------------------------------------------------------

TEST(Intersection, EveryStreamPublishesItsComparedAndItsUncomparedColumns) {
  // The counts are the arithmetic of the two projections, and they are pinned
  // so that widening one side without re-deriving the intersection cannot pass
  // silently.
  //   B1: this port projects 9 leaves, the frozen reader 5     -> 5 compared, 4 cpp-only
  //   B2: this port projects 19 leaves, the frozen reader 10   -> 10 compared, 9 cpp-only
  //   B3: this port projects 20 of 62, the frozen reader 25    -> 14 compared,
  //                                                              6 cpp-only + 11 rust-only
  //   B4: both project the same 8 leaves                       -> 8 compared, 0 uncompared
  EXPECT_EQ(qr::census::compared_columns(DiffStream::StockQuotes).size(), 5U);
  EXPECT_EQ(qr::census::uncompared_columns(DiffStream::StockQuotes).size(), 4U);
  EXPECT_EQ(qr::census::compared_columns(DiffStream::StockTrades).size(), 10U);
  EXPECT_EQ(qr::census::uncompared_columns(DiffStream::StockTrades).size(), 9U);
  EXPECT_EQ(qr::census::compared_columns(DiffStream::OptionPrints).size(), 14U);
  EXPECT_EQ(qr::census::uncompared_columns(DiffStream::OptionPrints).size(), 17U);
  EXPECT_EQ(qr::census::compared_columns(DiffStream::OptionQuotes).size(), 8U);
  EXPECT_EQ(qr::census::uncompared_columns(DiffStream::OptionQuotes).size(), 0U);

  // Nine of the seventeen uncompared print columns are the frozen reader's own
  // (walled or unprojected here); the rest are this port's.
  std::size_t rust_only = 0;
  for (const auto& column : qr::census::uncompared_columns(DiffStream::OptionPrints)) {
    if (column.side == qr::census::ColumnSide::RustOnly) {
      ++rust_only;
    }
    EXPECT_FALSE(column.name.empty());
    EXPECT_FALSE(column.reason.empty());
  }
  EXPECT_EQ(rust_only, 11U);
}

TEST(Intersection, NoColumnIsBothComparedAndEnumeratedAsUncomparable) {
  for (std::size_t index = 0; index < qr::census::kDiffStreamCount; ++index) {
    const auto stream = static_cast<DiffStream>(index);
    for (const auto& compared : qr::census::compared_columns(stream)) {
      for (const auto& uncompared : qr::census::uncompared_columns(stream)) {
        EXPECT_NE(compared.name, uncompared.name)
            << "column " << compared.name << " of " << qr::census::diff_stream_name(stream)
            << " is claimed both compared and non-compared";
      }
    }
  }
}

TEST(Intersection, EveryStreamProjectsItsClockAndTheRowWidthFollowsTheKinds) {
  // The clock column has to be inside the intersection: it is what makes a row
  // addressable, and the canonical image groups on it.
  EXPECT_EQ(qr::census::clock_column_index(DiffStream::StockQuotes), 0U);
  EXPECT_EQ(qr::census::clock_column_index(DiffStream::StockTrades), 0U);
  EXPECT_EQ(qr::census::clock_column_index(DiffStream::OptionPrints), 3U);
  EXPECT_EQ(qr::census::clock_column_index(DiffStream::OptionQuotes), 3U);
  // width = sum over compared columns of (kind width + 1 null-flag byte).
  EXPECT_EQ(qr::census::canonical_row_width(DiffStream::StockQuotes), 5U * 9U);
  EXPECT_EQ(qr::census::canonical_row_width(DiffStream::StockTrades), 10U * 9U);
  EXPECT_EQ(qr::census::canonical_row_width(DiffStream::OptionPrints), 5U + 2U + (12U * 9U));
  EXPECT_EQ(qr::census::canonical_row_width(DiffStream::OptionQuotes), 5U + 2U + (6U * 9U));
}

// ---------------------------------------------------------------------------
// The canonical byte image.
// ---------------------------------------------------------------------------

TEST(CanonicalImage, PermutingAnEqualTimestampRunDoesNotChangeTheDigest) {
  const std::vector<std::array<DiffCell, 5>> forward{
      quote_row(1000, 100, 17'000'000, 200, 17'010'000),
      quote_row(1000, 300, 17'000'000, 400, 17'020'000),
      quote_row(1000, 500, 16'990'000, 600, 17'010'000),
  };
  std::vector<std::array<DiffCell, 5>> backward(forward.rbegin(), forward.rend());
  std::vector<std::array<DiffCell, 5>> rotated{forward[1], forward[2], forward[0]};
  const std::string reference = sha_of(forward);
  EXPECT_EQ(sha_of(backward), reference);
  EXPECT_EQ(sha_of(rotated), reference);
}

TEST(CanonicalImage, RowsInDifferentMillisecondsKeepTheirTapeOrder) {
  // Canonicalization is WITHIN a run only. Two rows a millisecond apart are two
  // events, and swapping them is a different tape.
  const std::vector<std::array<DiffCell, 5>> forward{
      quote_row(1000, 100, 17'000'000, 200, 17'010'000),
      quote_row(1001, 300, 17'000'000, 400, 17'020'000),
  };
  const std::vector<std::array<DiffCell, 5>> swapped{forward[1], forward[0]};
  EXPECT_NE(sha_of(swapped), sha_of(forward));
}

TEST(CanonicalImage, MultiplicityIsPreservedInsideARun) {
  const std::vector<std::array<DiffCell, 5>> once{
      quote_row(1000, 100, 17'000'000, 200, 17'010'000),
  };
  const std::vector<std::array<DiffCell, 5>> twice{once[0], once[0]};
  EXPECT_NE(sha_of(twice), sha_of(once));
}

TEST(CanonicalImage, TheStreamAndTheDayAreBoundIntoTheDigest) {
  const std::vector<std::array<DiffCell, 5>> rows{
      quote_row(1000, 100, 17'000'000, 200, 17'010'000),
  };
  SessionDiff other_day(DiffStream::StockQuotes, "2022-07-06", true);
  const std::array<bool, 5> mask{false, false, false, false, false};
  other_day.push(rows[0], mask);
  other_day.finish();
  EXPECT_NE(other_day.row_sha256(), sha_of(rows));
}

TEST(CanonicalImage, ANullFlagIsPartOfTheImageSoAZeroIsNotAnAbsence) {
  const std::array<bool, 5> mask{false, false, false, false, false};
  SessionDiff present(DiffStream::StockQuotes, "2022-07-05", true);
  present.push(quote_row(1000, 0, 17'000'000, 200, 17'010'000), mask);
  present.finish();
  SessionDiff absent(DiffStream::StockQuotes, "2022-07-05", true);
  std::array<DiffCell, 5> row = quote_row(1000, 0, 17'000'000, 200, 17'010'000);
  row[1].is_null = true;
  absent.push(row, mask);
  absent.finish();
  EXPECT_NE(absent.row_sha256(), present.row_sha256());
}

TEST(CanonicalImage, ByteModeOffLeavesNoDigestRatherThanAnEmptyOne) {
  SessionDiff diff(DiffStream::StockQuotes, "2022-07-05", false);
  const std::array<bool, 5> mask{false, false, false, false, false};
  diff.push(quote_row(1000, 100, 17'000'000, 200, 17'010'000), mask);
  diff.finish();
  EXPECT_TRUE(diff.row_sha256().empty());
  EXPECT_EQ(diff.rows(), 1);
}

// ---------------------------------------------------------------------------
// WP3's digest rule, applied to emitted values.
// ---------------------------------------------------------------------------

TEST(DigestRule, IntegersWrapAndNullsAreCountedNeverFoldedIntoTheSum) {
  SessionDiff diff(DiffStream::StockQuotes, "2022-07-05", false);
  const std::array<bool, 5> mask{false, false, false, false, false};
  std::array<DiffCell, 5> a = quote_row(1, 7, 2, 3, 4);
  std::array<DiffCell, 5> b = quote_row(2, 11, 2, 3, 4);
  b[1].is_null = true;  // a null contributes NOTHING to the digest
  diff.push(a, mask);
  diff.push(b, mask);
  diff.finish();
  EXPECT_EQ(diff.column(1).non_null(), 1);
  EXPECT_EQ(diff.column(1).nulls(), 1);
  EXPECT_EQ(diff.column(1).digest(), 7U);
  // The clock column saw both values: 1 + 2.
  EXPECT_EQ(diff.column(0).digest(), 3U);
  EXPECT_EQ(diff.column(0).nulls(), 0);
}

TEST(DigestRule, TheIntegerSumIsWrappingRatherThanSaturatingOrRefusing) {
  SessionDiff diff(DiffStream::StockQuotes, "2022-07-05", false);
  const std::array<bool, 5> mask{false, false, false, false, false};
  diff.push(quote_row(std::int64_t{1} << 62, 0, 0, 0, 0), mask);
  diff.push(quote_row(std::int64_t{1} << 62, 0, 0, 0, 0), mask);
  diff.push(quote_row(std::int64_t{1} << 62, 0, 0, 0, 0), mask);
  diff.finish();
  const std::uint64_t expected =
      static_cast<std::uint64_t>(std::int64_t{1} << 62) * 3U;  // wraps by construction
  EXPECT_EQ(diff.column(0).digest(), expected);
}

TEST(DigestRule, DoublesFoldByBitXorSoAnEvenRepetitionCancels) {
  SessionDiff diff(DiffStream::OptionPrints, "2022-07-05", false);
  const std::array<bool, 14> mask{};
  std::array<DiffCell, 14> row{};
  row[3] = DiffCell{5, 0.0, false};       // ts
  row[6] = DiffCell{0, 0.25, false};      // delta
  diff.push(row, mask);
  diff.push(row, mask);
  diff.finish();
  EXPECT_EQ(diff.column(6).non_null(), 2);
  EXPECT_EQ(diff.column(6).digest(), 0U);
}

TEST(DigestRule, TheMaskCensusIsCarriedSeparatelyFromTheSharedNullModel) {
  // The shared model can call a cell present while this port's own mask says
  // null (the folded `right`, the attached block). That divergence is a census
  // number, never a silence.
  SessionDiff diff(DiffStream::OptionPrints, "2022-07-05", false);
  std::array<bool, 14> mask{};
  mask[2] = true;  // right was null on the tape
  std::array<DiffCell, 14> row{};
  row[2] = DiffCell{2, 0.0, false};  // folded to Right::Other
  row[3] = DiffCell{5, 0.0, false};
  diff.push(row, mask);
  diff.finish();
  EXPECT_EQ(diff.column(2).nulls(), 0);
  EXPECT_EQ(diff.column(2).non_null(), 1);
  EXPECT_EQ(diff.mask_null(2), 1);
}

// ---------------------------------------------------------------------------
// The dump TSV is parsed, not trusted.
// ---------------------------------------------------------------------------

TEST(DumpParse, TheHeaderIsPinnedAndDriftIsARefusal) {
  const auto refused = qr::census::parse_dump("kind\tordinal\tday\tstream\tname\tmetric\n");
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
}

TEST(DumpParse, AShortRowIsARefusalNamingItsLine) {
  std::string text(qr::census::kDumpHeader);
  text += "\nsession\t125\t2022-07-05\tstock_quotes\t-\trth_rows\n";
  const auto refused = qr::census::parse_dump(text);
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
  EXPECT_EQ(refused.error().context(), 2);
}

TEST(DumpParse, AWellFormedDumpRoundTripsThroughItsJoinKey) {
  std::string text(qr::census::kDumpHeader);
  text += "\nsession\t125\t2022-07-05\tstock_quotes\t-\trth_rows\t14761979\n";
  text += "column\t125\t2022-07-05\tstock_quotes\tbid_u6\tdigest\t18446744073709551615\n";
  const auto parsed = qr::census::parse_dump(text);
  ASSERT_TRUE(parsed.has_value()) << parsed.error().message();
  ASSERT_EQ(parsed.value().size(), 2U);
  EXPECT_EQ(qr::census::dump_key(parsed.value()[0]),
            "session|00125|stock_quotes|-|rth_rows");
  EXPECT_EQ(qr::census::dump_key(parsed.value()[1]),
            "column|00125|stock_quotes|bid_u6|digest");
  EXPECT_EQ(parsed.value()[1].value, "18446744073709551615");
}

TEST(DumpParse, AnEmptyDumpIsARefusalRatherThanAnEmptyAgreement) {
  const auto refused = qr::census::parse_dump("");
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
}
