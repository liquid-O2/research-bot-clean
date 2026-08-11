// The census, end to end over a real reader, across the share era, and against
// the registry.
//
// SPEC (WP5 brief, FIXTURES): "era-boundary synthetic pair; census cross-check
// vs registry complete_group_count on s125".
// SPEC (WP5 brief, REAL-FILE CHECK): "publish census TSV (all QuoteKind/flag
// counts, printed in full) to tests/fixtures/".
//
// The fixture tree here is WP4's own sq_cent tree, driven through the REAL
// StockQuoteReader: this is the only place the group machine is exercised
// against a decoded parquet file inside ctest, and it is payload-free.
#include <gtest/gtest.h>

#include <cstdint>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#include "nbbo_test_support.hpp"
#include "qr_nbbo/group_machine.hpp"
#include "qr_sources/normalize.hpp"
#include "qr_sources/stock_quotes.hpp"

namespace {

using qr::Validity;
using qr::nbbo::FullDayQuoteCensus;
using qr::nbbo::GroupMachine;
using qr::nbbo::QuoteDomain;
using qr::nbbo::QuoteKind;
using qr::nbbo::QuoteState;
using qr::nbbo::testing::clock_125;
using qr::nbbo::testing::open_ms_125;
using qr::nbbo::testing::pins_for;
using qr::nbbo::testing::quote_row;
using qr::nbbo::testing::run_tape;
using qr::nbbo::testing::TapeGroup;
using qr::sources::testing::fixture_root;
using qr::sources::testing::literal_int;
using qr::sources::testing::scope_125;

/// Drives the WP4 reader over a FIXTURE tree into a machine pinned to that
/// tree's own counts (the fixture is 11 rows / 7 groups, not session 125's
/// 14,761,979 / 2,810,589 — the real registry seal is the probe's job).
GroupMachine run_fixture_tree(const std::string& tree, std::int64_t rows, std::int64_t groups) {
  const auto scope = scope_125();
  EXPECT_TRUE(scope.has_value());
  GroupMachine machine = GroupMachine::from_clock(clock_125(), pins_for(rows, groups));
  auto opened =
      qr::sources::StockQuoteReader::open(*scope, fixture_root(tree), scope->profile());
  EXPECT_TRUE(opened.has_value()) << (opened.has_value() ? "" : opened.error().message());
  if (!opened.has_value()) {
    return machine;
  }
  qr::sources::StockQuoteReader reader = std::move(opened).value();
  qr::sources::StockQuoteReader::Group group;
  while (true) {
    const auto more = reader.next_group(group);
    EXPECT_TRUE(more.has_value()) << (more.has_value() ? "" : more.error().message());
    if (!more.has_value() || !more.value()) {
      break;
    }
    const auto pushed = machine.push_group(group.ts_ms_b, group.rows);
    EXPECT_TRUE(pushed.has_value()) << (pushed.has_value() ? "" : pushed.error().message());
    if (!pushed.has_value()) {
      return machine;
    }
  }
  const auto sealed = machine.seal(reader.sentinel_rows());
  EXPECT_TRUE(sealed.has_value()) << (sealed.has_value() ? "" : sealed.error().message());
  return machine;
}

}  // namespace

// ---------------------------------------------------------------------------
// End to end over the WP4 reader.
// ---------------------------------------------------------------------------

TEST(FixtureCensus, TheMachineReproducesTheFixtureTreesCommittedCountsThroughTheRealReader) {
  const std::int64_t rows = literal_int("stock_quotes/*/rth_rows");
  const std::int64_t groups = literal_int("stock_quotes/*/group_count");
  const std::int64_t sentinels = literal_int("stock_quotes/*/sentinel_rows");
  ASSERT_EQ(rows, 11);
  ASSERT_EQ(groups, 7);

  const GroupMachine machine = run_fixture_tree("sq_cent", rows, groups);
  // ASSERT, not EXPECT: every column read below is indexed, and a projection
  // that came back short must stop the test rather than walk off its own
  // vectors (a mutant that empties it is a red result, not a segfault).
  ASSERT_EQ(machine.groups().size(), static_cast<std::size_t>(groups));
  const FullDayQuoteCensus& census = machine.census();
  EXPECT_EQ(census.group_count, groups);
  EXPECT_EQ(census.rth_rows, rows);
  EXPECT_EQ(census.sentinel_rows, sentinels);

  // Every row of that tree is a two-sided, condition-0, ten-cent market on a
  // ~$171.45 mid: 100,000 * 20,000 = 2e9 <= 50 * ~342,880,000 = ~1.71e10, so
  // all eleven are NORMAL, VALID and scientific.
  EXPECT_EQ(census.state_rows[static_cast<std::size_t>(QuoteState::NORMAL)], 11);
  EXPECT_EQ(census.member_validity[static_cast<std::size_t>(Validity::VALID)], 11);
  EXPECT_EQ(census.eligible_rows, 11);
  EXPECT_EQ(census.structurally_valid_rows, 11);
  EXPECT_EQ(census.rejected_rows, 0);
  EXPECT_EQ(census.scientific_rows, 11);
  EXPECT_EQ(census.wide_rows, 0);
  EXPECT_EQ(census.groups_with_locked_member, 0);
  // Group 0 is {171.39/171.49, 171.40/171.50} -> two distinct midpoints;
  // group 3 is three distinct ones; group 2 is the same quote twice, so it
  // deduplicates to one.
  EXPECT_EQ(census.kind_groups[static_cast<std::size_t>(QuoteKind::MULTI_SCIENTIFIC)], 2);
  EXPECT_EQ(census.kind_groups[static_cast<std::size_t>(QuoteKind::SINGLE_SCIENTIFIC)], 5);
  EXPECT_EQ(census.kind_groups[static_cast<std::size_t>(QuoteKind::WIDE_ONLY)], 0);
  EXPECT_EQ(census.kind_groups[static_cast<std::size_t>(QuoteKind::UNRESOLVED)], 0);
  EXPECT_EQ(census.scientific_midpoints, 10);  // 2 + 1 + 1 + 3 + 1 + 1 + 1
  EXPECT_EQ(census.wide_midpoints, 0);
  for (std::size_t flag = 0; flag < qr::nbbo::kQualityFlagCount; ++flag) {
    EXPECT_EQ(census.quality_flag_groups[flag], 0) << "flag " << flag;
  }
  EXPECT_EQ(census.multi_member_groups, 3);
  EXPECT_EQ(census.max_group_multiplicity, 3);
  EXPECT_EQ(census.groups_without_eligible_member, 0);
  EXPECT_EQ(census.groups_without_prior_state, 1);
  EXPECT_EQ(census.domain_rows[static_cast<std::size_t>(QuoteDomain::RTH)], 11);
  EXPECT_EQ(census.compact_rows, 11);
  EXPECT_EQ(census.wide_profile_rows, 0);

  // Group 0's separate scalar means:
  //   bid 171,390,000 + 171,400,000 = 342,790,000 -> 171,395,000
  //   ask 171,490,000 + 171,500,000 = 342,990,000 -> 171,495,000
  //   mid = 342,890,000 / 2 = 171,445,000
  EXPECT_EQ(machine.groups().bid_u6_sum[0], 342'790'000);
  EXPECT_EQ(machine.groups().ask_u6_sum[0], 342'990'000);
  EXPECT_EQ(machine.groups().mid_u6[0], 171'445'000);
  // Sizes arrive in SHARES: 5 and 6 lots -> 500 + 600 = 1,100.
  EXPECT_EQ(machine.groups().bid_shares_sum[0], 1'100);
}

TEST(FixtureCensus, PermutingTheFixturesInGroupRowOrderLeavesTheCensusIdentical) {
  const std::int64_t rows = literal_int("stock_quotes/*/rth_rows");
  const std::int64_t groups = literal_int("stock_quotes/*/group_count");
  const GroupMachine plain = run_fixture_tree("sq_cent", rows, groups);
  const GroupMachine permuted = run_fixture_tree("sq_permuted", rows, groups);
  EXPECT_EQ(plain.census().to_tsv("t"), permuted.census().to_tsv("t"));
  EXPECT_EQ(plain.serialize(), permuted.serialize());
  EXPECT_FALSE(plain.serialize().empty());
}

// ---------------------------------------------------------------------------
// The share-era synthetic pair.
// ---------------------------------------------------------------------------

namespace {

/// The same economic tape stamped in the two size eras. `raw` is what the
/// vendor writes; WP4's boundary law turns it into shares before the group
/// machine sees anything, so both tapes must reduce identically.
std::vector<TapeGroup> era_tape(std::int64_t raw_bid, std::int64_t raw_ask,
                                std::string_view day) {
  const auto bid = qr::sources::nbbo_size_to_shares(raw_bid, day);
  const auto ask = qr::sources::nbbo_size_to_shares(raw_ask, day);
  EXPECT_TRUE(bid.has_value());
  EXPECT_TRUE(ask.has_value());
  const std::int64_t open = open_ms_125();
  return {
      {open + 0,
       {quote_row(open + 0, 171'000'000, 171'010'000, bid.value(), ask.value()),
        quote_row(open + 0, 171'000'002, 171'010'004, bid.value(), ask.value())}},
      {open + 1, {quote_row(open + 1, 171'020'000, 171'030'000, bid.value(), ask.value())}},
  };
}

}  // namespace

TEST(ShareEra, TheSameTapeInLotsAndInSharesReducesToTheSameBytes) {
  // 2025-10-31 is the last lot-era day and 2025-11-03 the first share-era day
  // (finding F-34). Five lots and 500 shares are the same book.
  const std::vector<TapeGroup> lots = era_tape(5, 7, "2025-10-31");
  const std::vector<TapeGroup> shares = era_tape(500, 700, "2025-11-03");
  ASSERT_EQ(lots[0].rows[0].bid_shares, 500);
  ASSERT_EQ(shares[0].rows[0].bid_shares, 500);

  GroupMachine lot_machine = GroupMachine::from_clock(clock_125(), pins_for(3, 2));
  GroupMachine share_machine = GroupMachine::from_clock(clock_125(), pins_for(3, 2));
  ASSERT_TRUE(run_tape(lot_machine, lots).has_value());
  ASSERT_TRUE(run_tape(share_machine, shares).has_value());

  EXPECT_EQ(lot_machine.serialize(), share_machine.serialize());
  EXPECT_EQ(lot_machine.census().to_tsv("era"), share_machine.census().to_tsv("era"));
  // The size means are the ones the era could have moved: 500 + 500 = 1,000.
  EXPECT_EQ(lot_machine.groups().bid_shares_sum[0], 1'000);
  EXPECT_EQ(share_machine.groups().bid_shares_sum[0], 1'000);
}

TEST(ShareEra, MisdatingTheEraByOneDayMovesEverySizeMeanByAHundredfold) {
  // The contrast that gives the pair test its bite: the SAME raw lots read as
  // if they were already shares. 2025-11-02 is still the lot era.
  const std::vector<TapeGroup> lots = era_tape(5, 7, "2025-11-02");
  const std::vector<TapeGroup> misdated = era_tape(5, 7, "2025-11-03");
  ASSERT_EQ(lots[0].rows[0].bid_shares, 500);
  ASSERT_EQ(misdated[0].rows[0].bid_shares, 5);

  GroupMachine correct = GroupMachine::from_clock(clock_125(), pins_for(3, 2));
  GroupMachine wrong = GroupMachine::from_clock(clock_125(), pins_for(3, 2));
  ASSERT_TRUE(run_tape(correct, lots).has_value());
  ASSERT_TRUE(run_tape(wrong, misdated).has_value());
  EXPECT_EQ(correct.groups().bid_shares_sum[0], 1'000);
  EXPECT_EQ(wrong.groups().bid_shares_sum[0], 10);
  EXPECT_NE(correct.serialize(), wrong.serialize());
}

// ---------------------------------------------------------------------------
// The census TSV, and the committed session-125 census against the registry.
// ---------------------------------------------------------------------------

TEST(CensusTsv, EveryKindFlagStateDomainAndValidityIsPrintedInFullIncludingZeros) {
  GroupMachine machine = GroupMachine::from_clock(clock_125(), pins_for(1, 1));
  const std::int64_t open = open_ms_125();
  ASSERT_TRUE(
      run_tape(machine, {{open, {quote_row(open, 171'000'000, 171'010'000, 500, 500)}}}).has_value());
  const std::string tsv = machine.census().to_tsv("unit");
  EXPECT_EQ(tsv, machine.census().to_tsv("unit")) << "the census rendering must be deterministic";

  for (std::size_t index = 0; index < qr::nbbo::kQuoteKindCount; ++index) {
    EXPECT_NE(tsv.find(std::string("kind_groups.") +
                       qr::nbbo::quote_kind_name(static_cast<QuoteKind>(index))),
              std::string::npos);
  }
  for (std::size_t index = 0; index < qr::nbbo::kQualityFlagCount; ++index) {
    EXPECT_NE(tsv.find(std::string("quality_flag_groups.") + qr::nbbo::quality_flag_name(index)),
              std::string::npos);
  }
  for (std::size_t index = 0; index < qr::nbbo::kQuoteStateCount; ++index) {
    EXPECT_NE(tsv.find(std::string("state_rows.") +
                       qr::nbbo::quote_state_name(static_cast<QuoteState>(index))),
              std::string::npos);
  }
  for (std::size_t index = 0; index < qr::nbbo::kQuoteDomainCount; ++index) {
    EXPECT_NE(tsv.find(std::string("domain_rows.") +
                       qr::nbbo::quote_domain_name(static_cast<QuoteDomain>(index))),
              std::string::npos);
  }
  for (std::size_t index = 0; index < qr::kValidityCount; ++index) {
    EXPECT_NE(tsv.find(std::string("member_validity.") +
                       qr::validity_name(static_cast<Validity>(index))),
              std::string::npos);
  }
  EXPECT_NE(tsv.find("groups_without_prior_state"), std::string::npos);
}

TEST(CommittedCensus, TheSessionOneTwentyFiveCensusMatchesTheFrozenRegistryRow) {
  // The published census of the authorized real-file run, checked against the
  // two numbers the frozen registry signs — the stateful-machine half of
  // FINAL_PLAN section 6's correctness oracle 2. No payload is opened here:
  // this reads the committed TSV and the embedded registry.
  std::ifstream input(QR_NBBO_SESSION125_CENSUS);
  ASSERT_TRUE(input.is_open()) << "missing " << QR_NBBO_SESSION125_CENSUS;
  std::map<std::string, std::int64_t> census;
  std::string line;
  while (std::getline(input, line)) {
    if (line.empty() || line[0] == '#') {
      continue;
    }
    std::istringstream stream(line);
    std::string label;
    std::string metric;
    std::string value;
    if (!std::getline(stream, label, '\t') || !std::getline(stream, metric, '\t') ||
        !std::getline(stream, value, '\t')) {
      continue;
    }
    if (label == "label") {
      continue;
    }
    census[metric] = std::strtoll(value.c_str(), nullptr, 10);
  }
  ASSERT_FALSE(census.empty());

  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  EXPECT_EQ(census["group_count"], scope->session().complete_group_count);
  EXPECT_EQ(census["rth_rows"], scope->session().raw_rth_row_count);
  EXPECT_EQ(census["group_count"], 2'810'589);
  EXPECT_EQ(census["rth_rows"], 14'761'979);
  // Structural laws the published census must satisfy on any session.
  EXPECT_EQ(census["structurally_valid_rows"] + census["rejected_rows"], census["rth_rows"]);
  EXPECT_EQ(census["scientific_rows"] + census["wide_rows"], census["structurally_valid_rows"]);
  EXPECT_EQ(census["domain_rows.RTH"], census["rth_rows"]);
  EXPECT_EQ(census["compact_rows"], census["rth_rows"]) << "session 125 is a cent_int32 row";
  EXPECT_EQ(census["wide_profile_rows"], 0);
  std::int64_t kinds = 0;
  for (std::size_t index = 0; index < qr::nbbo::kQuoteKindCount; ++index) {
    kinds += census[std::string("kind_groups.") +
                    qr::nbbo::quote_kind_name(static_cast<QuoteKind>(index))];
  }
  EXPECT_EQ(kinds, census["group_count"]);
  std::int64_t states = 0;
  for (std::size_t index = 0; index < qr::nbbo::kQuoteStateCount; ++index) {
    states += census[std::string("state_rows.") +
                     qr::nbbo::quote_state_name(static_cast<QuoteState>(index))];
  }
  EXPECT_EQ(states, census["rth_rows"]);
  std::int64_t typed = 0;
  for (std::size_t index = 0; index < qr::kValidityCount; ++index) {
    typed += census[std::string("member_validity.") +
                    qr::validity_name(static_cast<Validity>(index))];
  }
  EXPECT_EQ(typed, census["rth_rows"]);
}
