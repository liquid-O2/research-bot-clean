// The equal-time group iterator.
//
// SPEC (design/DESIGN_SUBSTRATE.md APPENDIX C3): "`next_group()` equal-time
// iterator, rows unordered within group."
// SPEC (WP4 brief, fixtures): "multi-row same-ms group delivered unordered with
// group multiplicity, prior-group boundary correct (permutation of in-group row
// order => byte-identical groups fixture)".
#include <gtest/gtest.h>

#include <cstdint>
#include <span>
#include <utility>
#include <vector>

#include "fixture_support.hpp"
#include "qr_sources/session_source.hpp"
#include "qr_sources/stock_quotes.hpp"

namespace {

using qr::sources::GroupTape;
using qr::sources::StockQuoteRow;
using qr::sources::testing::fixture_root;
using qr::sources::testing::literal_int;
using qr::sources::testing::scope_125;

StockQuoteRow row_at(std::int64_t ts_ms, std::int64_t bid_u6, std::int64_t bid_shares) {
  StockQuoteRow row;
  row.ts_ms_b = ts_ms;
  row.bid_u6 = bid_u6;
  row.ask_u6 = bid_u6 + 10'000;
  row.bid_shares = bid_shares;
  row.ask_shares = bid_shares + 100;
  return row;
}

struct Delivered {
  std::int64_t ts_ms_b = 0;
  std::vector<StockQuoteRow> rows;
};

std::vector<Delivered> drain(GroupTape<StockQuoteRow>& tape) {
  std::vector<Delivered> out;
  std::int64_t ts = 0;
  std::span<const StockQuoteRow> rows;
  while (tape.next(ts, rows)) {
    Delivered one;
    one.ts_ms_b = ts;
    one.rows.assign(rows.begin(), rows.end());
    out.push_back(std::move(one));
  }
  return out;
}

std::vector<std::uint8_t> serialize(const std::vector<Delivered>& groups) {
  std::vector<std::uint8_t> bytes;
  for (const Delivered& group : groups) {
    qr::sources::append_i64(group.ts_ms_b, bytes);
    qr::sources::append_i64(static_cast<std::int64_t>(group.rows.size()), bytes);
    for (const StockQuoteRow& row : group.rows) {
      append_serialized(row, bytes);
    }
  }
  return bytes;
}

TEST(GroupTape, EqualMillisecondRunsBecomeOneGroupAndMultiplicityIsPreserved) {
  GroupTape<StockQuoteRow> tape;
  tape.begin_chunk();
  tape.push(row_at(10, 100, 1));
  tape.push(row_at(10, 200, 2));
  tape.push(row_at(11, 300, 3));
  tape.push(row_at(12, 400, 4));
  tape.push(row_at(12, 400, 4));  // an exact duplicate inside one millisecond
  tape.push(row_at(12, 500, 5));
  tape.end_chunk(true);

  const std::vector<Delivered> groups = drain(tape);
  ASSERT_EQ(groups.size(), 3U);
  EXPECT_EQ(groups[0].ts_ms_b, 10);
  EXPECT_EQ(groups[0].rows.size(), 2U);
  EXPECT_EQ(groups[1].ts_ms_b, 11);
  EXPECT_EQ(groups[1].rows.size(), 1U);
  EXPECT_EQ(groups[2].ts_ms_b, 12);
  // A repeated quote is a fact about the tape, not a duplicate to collapse.
  EXPECT_EQ(groups[2].rows.size(), 3U);
  EXPECT_EQ(groups[2].rows[0].bid_u6, 400);
  EXPECT_EQ(groups[2].rows[1].bid_u6, 400);
  EXPECT_EQ(groups[2].rows[2].bid_u6, 500);
  // Every row of a group carries the group's own millisecond, and no group
  // holds two different ones.
  for (const Delivered& group : groups) {
    for (const StockQuoteRow& row : group.rows) {
      EXPECT_EQ(row.ts_ms_b, group.ts_ms_b);
    }
  }
}

TEST(GroupTape, AGroupStraddlingAChunkBoundaryIsDeliveredOnceAndWhole) {
  GroupTape<StockQuoteRow> tape;
  tape.begin_chunk();
  tape.push(row_at(10, 100, 1));
  tape.push(row_at(10, 200, 2));
  tape.push(row_at(11, 300, 3));  // this run touches the end of the chunk
  tape.end_chunk(false);

  std::vector<Delivered> first = drain(tape);
  ASSERT_EQ(first.size(), 1U) << "the trailing run must be carried, not delivered";
  EXPECT_EQ(first[0].ts_ms_b, 10);
  EXPECT_TRUE(tape.has_carry());

  tape.begin_chunk();
  tape.push(row_at(11, 400, 4));
  tape.push(row_at(12, 500, 5));
  tape.end_chunk(true);
  const std::vector<Delivered> second = drain(tape);
  ASSERT_EQ(second.size(), 2U);
  EXPECT_EQ(second[0].ts_ms_b, 11);
  EXPECT_EQ(second[0].rows.size(), 2U) << "the straddling group must arrive whole";
  EXPECT_EQ(second[1].ts_ms_b, 12);
  EXPECT_EQ(second[1].rows.size(), 1U);
  EXPECT_FALSE(tape.has_carry());
}

TEST(GroupTape, InGroupOrderIsCanonicalSoAnInputPermutationIsInvisible) {
  const std::vector<StockQuoteRow> rows{row_at(10, 300, 3), row_at(10, 100, 1),
                                        row_at(10, 200, 2), row_at(11, 400, 4)};
  std::vector<std::vector<std::uint8_t>> renderings;
  // Every permutation of the equal-time run (the first three rows) must render
  // the same bytes; the fourth row is a different millisecond and stays last.
  const std::vector<std::vector<std::size_t>> orders{
      {0, 1, 2, 3}, {2, 1, 0, 3}, {1, 0, 2, 3}, {1, 2, 0, 3}, {2, 0, 1, 3}, {0, 2, 1, 3}};
  for (const std::vector<std::size_t>& order : orders) {
    GroupTape<StockQuoteRow> tape;
    tape.begin_chunk();
    for (const std::size_t index : order) {
      tape.push(rows[index]);
    }
    tape.end_chunk(true);
    renderings.push_back(serialize(drain(tape)));
  }
  for (std::size_t index = 1; index < renderings.size(); ++index) {
    EXPECT_EQ(renderings[0], renderings[index]) << "permutation " << index << " rendered differently";
  }
  EXPECT_FALSE(renderings[0].empty());
}

TEST(GroupTape, AnEmptyChunkDeliversNothingAndKeepsTheCarry) {
  GroupTape<StockQuoteRow> tape;
  tape.begin_chunk();
  tape.push(row_at(10, 100, 1));
  tape.end_chunk(false);
  EXPECT_TRUE(drain(tape).empty());
  EXPECT_TRUE(tape.has_carry());

  tape.begin_chunk();  // a chunk with no admitted rows at all
  tape.end_chunk(false);
  EXPECT_TRUE(drain(tape).empty());
  EXPECT_TRUE(tape.has_carry()) << "an empty chunk must not lose the carried run";

  tape.begin_chunk();
  tape.end_chunk(true);
  const std::vector<Delivered> flushed = drain(tape);
  ASSERT_EQ(flushed.size(), 1U);
  EXPECT_EQ(flushed[0].ts_ms_b, 10);
}

// --- the fixture-level statement -------------------------------------------

std::vector<std::uint8_t> read_all_groups(const std::string& tree, std::int64_t& groups,
                                          std::int64_t& rows) {
  const auto scope = scope_125();
  EXPECT_TRUE(scope.has_value());
  std::vector<std::uint8_t> bytes;
  if (!scope.has_value()) {
    return bytes;
  }
  auto opened = qr::sources::StockQuoteReader::open(*scope, fixture_root(tree),
                                                    scope->profile());
  EXPECT_TRUE(opened.has_value()) << (opened.has_value() ? "" : opened.error().message());
  if (!opened.has_value()) {
    return bytes;
  }
  qr::sources::StockQuoteReader reader = std::move(opened).value();
  qr::sources::StockQuoteReader::Group group;
  while (true) {
    const auto more = reader.next_group(group);
    EXPECT_TRUE(more.has_value()) << (more.has_value() ? "" : more.error().message());
    if (!more.has_value() || !more.value()) {
      break;
    }
    qr::sources::append_i64(group.ts_ms_b, bytes);
    qr::sources::append_i64(static_cast<std::int64_t>(group.rows.size()), bytes);
    for (const StockQuoteRow& row : group.rows) {
      append_serialized(row, bytes);
    }
  }
  groups = reader.group_count();
  rows = reader.rth_rows();
  return bytes;
}

TEST(GroupFixtures, PermutingRowsInsideEveryEqualTimeGroupProducesByteIdenticalGroups) {
  std::int64_t plain_groups = 0;
  std::int64_t plain_rows = 0;
  const std::vector<std::uint8_t> plain = read_all_groups("sq_cent", plain_groups, plain_rows);
  std::int64_t permuted_groups = 0;
  std::int64_t permuted_rows = 0;
  const std::vector<std::uint8_t> permuted =
      read_all_groups("sq_permuted", permuted_groups, permuted_rows);

  ASSERT_FALSE(plain.empty());
  EXPECT_EQ(plain_groups, literal_int("stock_quotes/*/group_count"));
  EXPECT_EQ(plain_rows, literal_int("stock_quotes/*/rth_rows"));
  EXPECT_EQ(permuted_groups, plain_groups);
  EXPECT_EQ(permuted_rows, plain_rows);
  EXPECT_EQ(plain, permuted)
      << "in-group row order is not information: permuting it must change nothing";
}

TEST(GroupFixtures, TwoRunsOverTheSameFixtureAreByteIdentical) {
  std::int64_t groups = 0;
  std::int64_t rows = 0;
  const std::vector<std::uint8_t> first = read_all_groups("sq_cent", groups, rows);
  const std::vector<std::uint8_t> second = read_all_groups("sq_cent", groups, rows);
  ASSERT_FALSE(first.empty());
  EXPECT_EQ(first, second);
}

}  // namespace
