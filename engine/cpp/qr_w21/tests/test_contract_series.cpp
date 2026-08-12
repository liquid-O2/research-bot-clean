// qr_w21/tests/test_contract_series.cpp — PER-CONTRACT OPTION-QUOTE EMISSION,
// red-first.
//
// SPEC: design/D020_SCALE_PROTOCOL.md §ORCH-6.3 (the named work item) over
// FINAL_PLAN APPENDIX B4's eight projected columns.
//
// NOT RE-TESTED HERE (the repository law forbids a second copy of an existing
// proof): the B4 projection and its walled `mid` column (qr_sources
// `SpecLaws.*`, `OptionQuotes.*`), the equal-time group machine, and the
// 125..749 scope wall. What is tested here is the emission block itself.
#include <gtest/gtest.h>

#include <cstdint>
#include <string>
#include <vector>

#include "gtest/gtest.h"
#include "qr_w21/contract_series.hpp"

namespace {

using qr::sources::Right;
using qr::w21::ActivityCensus;
using qr::w21::ContractId;
using qr::w21::ContractSeries;

constexpr std::int64_t kU6 = 1'000'000;
/// 2023-08-04 as days since the Unix epoch.
constexpr std::int32_t kExpiryA = 19573;
constexpr std::int32_t kExpiryB = 19580;

qr::sources::OptionQuoteRow quote_row(std::int32_t expiry, std::int64_t strike_u6, Right right,
                                      std::int64_t bid_u6, std::int64_t ask_u6,
                                      std::int64_t bid_size, std::int64_t ask_size,
                                      std::uint16_t null_mask = 0) {
  qr::sources::OptionQuoteRow row;
  row.expiration_day = expiry;
  row.strike_u6 = strike_u6;
  row.right = right;
  row.bid_u6 = bid_u6;
  row.ask_u6 = ask_u6;
  row.bid_size = bid_size;
  row.ask_size = ask_size;
  row.null_mask = null_mask;
  return row;
}

}  // namespace

// ---------------------------------------------------------------------------
// The contract identity.
// ---------------------------------------------------------------------------

TEST(ContractId, TheSpellingRoundTripsAndEveryRejectionIsTyped) {
  const auto parsed = qr::w21::parse_contract_id("2023-08-04:1900000000:CALL");
  ASSERT_TRUE(parsed.has_value()) << parsed.error().message();
  EXPECT_EQ(parsed.value().expiration_day, kExpiryA);
  EXPECT_EQ(parsed.value().strike_u6, 1'900'000'000);
  EXPECT_EQ(parsed.value().right, Right::Call);
  EXPECT_EQ(qr::w21::format_contract_id(parsed.value()), "2023-08-04:1900000000:CALL");

  // The short right tokens are the frozen set's, so a caller may spell either.
  const auto shorthand = qr::w21::parse_contract_id("2023-08-04:1900000000:P");
  ASSERT_TRUE(shorthand.has_value()) << shorthand.error().message();
  EXPECT_EQ(shorthand.value().right, Right::Put);

  // A malformed day is a DATE refusal, not a generic one.
  const auto bad_day = qr::w21::parse_contract_id("2023-13-04:1900000000:CALL");
  ASSERT_FALSE(bad_day.has_value());
  EXPECT_EQ(bad_day.error().code(), qr::RefusalCode::MALFORMED_CIVIL_DATE);

  // A strike that is not a whole positive u6 integer is refused, never
  // rounded: "1900.0" is a decimal price, and this interface takes u6.
  for (const char* text : {"2023-08-04:1900.0:CALL", "2023-08-04:0:CALL",
                           "2023-08-04:-5:CALL", "2023-08-04:19000000x:CALL"}) {
    const auto refused = qr::w21::parse_contract_id(text);
    ASSERT_FALSE(refused.has_value()) << text << " was accepted";
    EXPECT_EQ(refused.error().code(), qr::RefusalCode::CONFIG) << text;
  }

  // An unnamed right is a CALLER error here — never `Right::Other`, which
  // would silently answer with an empty series.
  const auto bad_right = qr::w21::parse_contract_id("2023-08-04:1900000000:XY");
  ASSERT_FALSE(bad_right.has_value());
  EXPECT_EQ(bad_right.error().code(), qr::RefusalCode::CONFIG);

  // And the shape itself is pinned: two fields, or four, is not a contract.
  for (const char* text : {"2023-08-04:1900000000", "2023-08-04:1900000000:CALL:X", ""}) {
    const auto refused = qr::w21::parse_contract_id(text);
    ASSERT_FALSE(refused.has_value()) << "'" << text << "' was accepted";
    EXPECT_EQ(refused.error().code(), qr::RefusalCode::CONFIG);
  }
}

TEST(ContractId, TheOrderIsTotalAcrossAllThreeFields) {
  // A `std::map` keyed on this must iterate deterministically, so no two
  // distinct contracts may compare equivalent.
  const std::vector<ContractId> ordered{
      ContractId{kExpiryA, 1800 * kU6, Right::Call},
      ContractId{kExpiryA, 1800 * kU6, Right::Put},
      ContractId{kExpiryA, 1900 * kU6, Right::Call},
      ContractId{kExpiryB, 1700 * kU6, Right::Call},
  };
  for (std::size_t i = 0; i < ordered.size(); ++i) {
    for (std::size_t j = 0; j < ordered.size(); ++j) {
      EXPECT_EQ(ordered[i] < ordered[j], i < j) << i << " vs " << j;
      EXPECT_EQ(ordered[i] == ordered[j], i == j) << i << " vs " << j;
    }
  }
}

// ---------------------------------------------------------------------------
// The named-contract series.
// ---------------------------------------------------------------------------

TEST(ContractSeries, OnlyTheNamedContractInsideTheWindowIsRetained) {
  const ContractId named{kExpiryA, 1900 * kU6, Right::Call};
  ContractSeries series(named, 100, 200);

  // Inside the window, the named contract.
  series.observe(100, 100'000, quote_row(kExpiryA, 1900 * kU6, Right::Call, 4 * kU6, 5 * kU6, 11,
                                         21));
  series.observe(200, 200'500, quote_row(kExpiryA, 1900 * kU6, Right::Call, 4 * kU6, 6 * kU6, 12,
                                         22));
  // Same expiry and strike, the OTHER right — a different contract.
  series.observe(150, 150'000, quote_row(kExpiryA, 1900 * kU6, Right::Put, 1 * kU6, 2 * kU6, 1, 2));
  // Same expiry and right, a neighbouring strike.
  series.observe(150, 150'000, quote_row(kExpiryA, 1895 * kU6, Right::Call, 1 * kU6, 2 * kU6, 1,
                                         2));
  // Same strike and right, the next expiry.
  series.observe(150, 150'000, quote_row(kExpiryB, 1900 * kU6, Right::Call, 1 * kU6, 2 * kU6, 1,
                                         2));
  // The named contract, one second OUTSIDE each edge of the closed window.
  series.observe(99, 99'000, quote_row(kExpiryA, 1900 * kU6, Right::Call, 9 * kU6, 9 * kU6, 9, 9));
  series.observe(201, 201'000, quote_row(kExpiryA, 1900 * kU6, Right::Call, 9 * kU6, 9 * kU6, 9,
                                         9));

  ASSERT_EQ(series.quotes().size(), 2U);
  EXPECT_EQ(series.quotes()[0].second, 100);
  EXPECT_EQ(series.quotes()[0].ms, 100'000);
  EXPECT_EQ(series.quotes()[0].bid_u6, 4 * kU6);
  EXPECT_EQ(series.quotes()[0].ask_u6, 5 * kU6);
  EXPECT_EQ(series.quotes()[0].bid_size, 11);
  EXPECT_EQ(series.quotes()[0].ask_size, 21);
  EXPECT_EQ(series.quotes()[1].second, 200);
  EXPECT_EQ(series.quotes()[1].ask_size, 22);
  // The window is CLOSED at both ends, and the out-of-window rows of the named
  // contract are still counted as the contract existing in this session.
  EXPECT_EQ(series.session_rows(), 4);
}

TEST(ContractSeries, AnAbsentSideStaysAbsentAndTheMidpointIsComputedNotRead) {
  const ContractId named{kExpiryA, 1900 * kU6, Right::Put};
  ContractSeries series(named, 0, 1000);
  const std::uint16_t bid_absent =
      static_cast<std::uint16_t>(1U << qr::sources::kOptionQuoteSlotBid);
  series.observe(10, 10'000,
                 quote_row(kExpiryA, 1900 * kU6, Right::Put, 4 * kU6, 6 * kU6, 11, 21));
  series.observe(11, 11'000,
                 quote_row(kExpiryA, 1900 * kU6, Right::Put, 0, 6 * kU6, 0, 21, bid_absent));

  ASSERT_EQ(series.quotes().size(), 2U);
  std::int64_t mid = -1;
  ASSERT_TRUE(series.quotes()[0].mid_u6(mid));
  EXPECT_EQ(mid, 5 * kU6);
  // A one-sided quote has NO midpoint. Returning bid+ask, or the live side, or
  // zero would each be an invented price.
  mid = -1;
  EXPECT_FALSE(series.quotes()[1].mid_u6(mid));
  EXPECT_EQ(mid, -1);
  EXPECT_TRUE(series.quotes()[1].is_null(qr::sources::kOptionQuoteSlotBid));
  EXPECT_EQ(series.quotes()[1].bid_u6, 0) << "an absent field carries 0, never a sentinel";
  EXPECT_FALSE(series.quotes()[1].is_null(qr::sources::kOptionQuoteSlotAsk));
}

// ---------------------------------------------------------------------------
// The discovery census.
// ---------------------------------------------------------------------------

TEST(ActivityCensus, TopKRanksByRowsAndBreaksTiesOnTheContractNeverOnArrival) {
  ActivityCensus census(0, 1000);
  const ContractId busy{kExpiryA, 1900 * kU6, Right::Call};
  const ContractId tie_low{kExpiryA, 1850 * kU6, Right::Put};
  const ContractId tie_high{kExpiryB, 1700 * kU6, Right::Call};

  // `tie_high` arrives FIRST and `tie_low` second, and they end with the same
  // row count: the report must still order them by identity.
  census.observe(5, 5'000, quote_row(tie_high.expiration_day, tie_high.strike_u6, tie_high.right,
                                     kU6, 2 * kU6, 1, 1));
  census.observe(6, 6'000, quote_row(tie_low.expiration_day, tie_low.strike_u6, tie_low.right, kU6,
                                     2 * kU6, 1, 1));
  census.observe(7, 7'000, quote_row(tie_high.expiration_day, tie_high.strike_u6, tie_high.right,
                                     kU6, 2 * kU6, 1, 1));
  census.observe(8, 8'000, quote_row(tie_low.expiration_day, tie_low.strike_u6, tie_low.right, kU6,
                                     2 * kU6, 1, 1));
  for (int index = 0; index < 5; ++index) {
    census.observe(10 + index, 10'000 + index,
                   quote_row(busy.expiration_day, busy.strike_u6, busy.right, kU6, 2 * kU6, 1, 1));
  }

  const std::vector<qr::w21::ContractActivity> top = census.top(3);
  ASSERT_EQ(top.size(), 3U);
  EXPECT_EQ(top[0].id, busy);
  EXPECT_EQ(top[0].rows, 5);
  EXPECT_EQ(top[1].id, tie_low) << "a tie must break on the contract, not on arrival order";
  EXPECT_EQ(top[2].id, tie_high);
  EXPECT_EQ(top[1].rows, top[2].rows);
  EXPECT_EQ(census.contracts(), 3);
  EXPECT_EQ(census.rows(), 9);

  // K truncates the report and nothing else.
  EXPECT_EQ(census.top(1).size(), 1U);
  EXPECT_EQ(census.top(1)[0].id, busy);
  EXPECT_EQ(census.top(99).size(), 3U);
}

TEST(ActivityCensus, SecondsPresentCountsSecondsAndTheWindowBoundsEverything) {
  ActivityCensus census(100, 200);
  const ContractId one{kExpiryA, 1900 * kU6, Right::Call};
  // Three rows inside ONE second, then two rows in a second one.
  census.observe(100, 100'000, quote_row(kExpiryA, 1900 * kU6, Right::Call, kU6, 2 * kU6, 1, 1));
  census.observe(100, 100'300, quote_row(kExpiryA, 1900 * kU6, Right::Call, kU6, 2 * kU6, 1, 1));
  census.observe(100, 100'700, quote_row(kExpiryA, 1900 * kU6, Right::Call, kU6, 2 * kU6, 1, 1));
  census.observe(140, 140'000, quote_row(kExpiryA, 1900 * kU6, Right::Call, kU6, 2 * kU6, 1, 1));
  census.observe(140, 140'900, quote_row(kExpiryA, 1900 * kU6, Right::Call, kU6, 2 * kU6, 1, 1));
  // Outside the closed window at both edges: neither row nor second is counted.
  census.observe(99, 99'000, quote_row(kExpiryA, 1900 * kU6, Right::Call, kU6, 2 * kU6, 1, 1));
  census.observe(201, 201'000, quote_row(kExpiryA, 1900 * kU6, Right::Call, kU6, 2 * kU6, 1, 1));

  const std::vector<qr::w21::ContractActivity> top = census.top(5);
  ASSERT_EQ(top.size(), 1U);
  EXPECT_EQ(top[0].id, one);
  EXPECT_EQ(top[0].rows, 5);
  EXPECT_EQ(top[0].seconds_present, 2) << "five rows in two seconds are two seconds";
  EXPECT_EQ(top[0].first_ms, 100'000);
  EXPECT_EQ(top[0].last_ms, 140'900);
  EXPECT_EQ(census.rows(), 5);
}

TEST(ActivityCensus, AnEmptyWindowReportsNothingRatherThanInventingAContract) {
  ActivityCensus census(500, 600);
  census.observe(10, 10'000, quote_row(kExpiryA, 1900 * kU6, Right::Call, kU6, 2 * kU6, 1, 1));
  EXPECT_TRUE(census.top(10).empty());
  EXPECT_EQ(census.contracts(), 0);
  EXPECT_EQ(census.rows(), 0);

  ContractSeries series(ContractId{kExpiryA, 1900 * kU6, Right::Call}, 500, 600);
  series.observe(10, 10'000, quote_row(kExpiryA, 1900 * kU6, Right::Call, kU6, 2 * kU6, 1, 1));
  EXPECT_TRUE(series.quotes().empty());
  // The contract EXISTS in the session — it simply did not quote in the
  // window. Those are different facts and the block keeps them apart.
  EXPECT_EQ(series.session_rows(), 1);
}
