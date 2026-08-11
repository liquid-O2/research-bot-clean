// The execution envelope (qr_labels/execution_tape.hpp): qr_nbbo's eligibility
// used verbatim, the conservative extrema, permutation invariance, the binding
// check against the WP5 projection, and the range-extremum index.
#include <gtest/gtest.h>

#include <algorithm>
#include <vector>

#include "labels_test_support.hpp"
#include "qr_nbbo/group_machine.hpp"

namespace qr::labels {
namespace {

using testing::group_at;
using testing::group_of;
using testing::Lcg;
using testing::MicroGroup;
using testing::open_ms_125;
using testing::quote_row;
using testing::tape_of;

TEST(ExecutionTape, TheFourExtremaAreTheConservativeEnvelopeOfTheEligibleMembers) {
  // Four members at ONE millisecond. The fills are the ADVERSE corners:
  // ask_max for a LONG and bid_min for a SHORT, never the friendly ones.
  const ExecutionTape tape = tape_of({group_of(1'000, {{999'900, 1'000'000},
                                                       {999'800, 999'950},
                                                       {999'850, 1'000'050},
                                                       {999'870, 999'990}})});
  ASSERT_EQ(tape.size(), 1);
  EXPECT_EQ(tape.bid_min_u6[0], 999'800);
  EXPECT_EQ(tape.bid_max_u6[0], 999'900);
  EXPECT_EQ(tape.ask_min_u6[0], 999'950);
  EXPECT_EQ(tape.ask_max_u6[0], 1'000'050);
  EXPECT_EQ(tape.eligible_count[0], 4);
  EXPECT_EQ(tape.entry_price(0, Side::LONG), 1'000'050);
  EXPECT_EQ(tape.entry_price(0, Side::SHORT), 999'800);
  EXPECT_EQ(tape.adverse_mark(0, Side::LONG), 999'800);
  EXPECT_EQ(tape.adverse_mark(0, Side::SHORT), 1'000'050);
  EXPECT_EQ(tape.favorable_mark(0, Side::LONG), 999'900);
  EXPECT_EQ(tape.favorable_mark(0, Side::SHORT), 999'950);
}

TEST(ExecutionTape, EligibilityIsQrNbbosPredicateAndNothingElse) {
  // Locked (bid == ask), crossed (bid > ask), condition-ineligible, zero-size
  // and null-priced members are NOT eligible, so they never touch an extremum.
  // The one good member decides the whole group.
  MicroGroup group;
  group.ms_offset = 2'000;
  const std::int64_t ms = open_ms_125() + 2'000;
  group.rows.push_back(quote_row(ms, 1'000'000, 1'000'000));            // LOCKED
  group.rows.push_back(quote_row(ms, 1'000'100, 1'000'000));            // CROSSED
  group.rows.push_back(quote_row(ms, 999'000, 1'001'000, 100, 100, 1)); // condition 1
  group.rows.push_back(quote_row(ms, 999'000, 1'001'000, 0, 100));      // zero bid size
  group.rows.push_back(quote_row(ms, 999'900, 1'000'000));              // the only eligible one
  const ExecutionTape tape = tape_of({group});
  ASSERT_EQ(tape.size(), 1);
  EXPECT_EQ(tape.eligible_count[0], 1);
  EXPECT_EQ(tape.bid_min_u6[0], 999'900);
  EXPECT_EQ(tape.ask_max_u6[0], 1'000'000);
  EXPECT_EQ(tape.census.ineligible_members, 4);
}

TEST(ExecutionTape, AGroupWithNoEligibleMemberCarriesNoLawfulMarkButIsCensused) {
  const ExecutionTape tape = tape_of({group_at(1'000, 1'000'000, 1'000'000),  // locked
                                      group_at(2'000, 999'900, 1'000'000)});
  EXPECT_EQ(tape.size(), 1);
  EXPECT_EQ(tape.census.groups_seen, 2);
  EXPECT_EQ(tape.census.groups_eligible, 1);
  EXPECT_EQ(tape.census.groups_without_eligible_member, 1);
}

TEST(ExecutionTape, MemberPermutationDoesNotMoveASingleByte) {
  const std::vector<std::pair<std::int64_t, std::int64_t>> quotes{
      {999'900, 1'000'000}, {999'800, 999'950}, {999'850, 1'000'050}, {999'870, 999'990}};
  std::vector<std::pair<std::int64_t, std::int64_t>> permuted{quotes.rbegin(), quotes.rend()};

  MicroGroup forward;
  MicroGroup backward;
  forward.ms_offset = 1'000;
  backward.ms_offset = 1'000;
  for (const auto& [bid, ask] : quotes) {
    forward.rows.push_back(quote_row(open_ms_125() + 1'000, bid, ask));
  }
  for (const auto& [bid, ask] : permuted) {
    backward.rows.push_back(quote_row(open_ms_125() + 1'000, bid, ask));
  }
  std::vector<std::uint8_t> a;
  std::vector<std::uint8_t> b;
  tape_of({forward}).append_serialized(0, a);
  tape_of({backward}).append_serialized(0, b);
  EXPECT_EQ(a, b);
}

TEST(ExecutionTape, EqualOrDescendingGroupStampsAreRefused) {
  ExecutionTapeBuilder builder = ExecutionTapeBuilder::from_clock(testing::clock_125(), 125);
  const std::vector<qr::sources::StockQuoteRow> first{
      quote_row(open_ms_125() + 1'000, 999'900, 1'000'000)};
  ASSERT_TRUE(builder.push_group(open_ms_125() + 1'000, first).has_value());
  const std::vector<qr::sources::StockQuoteRow> again{
      quote_row(open_ms_125() + 1'000, 999'900, 1'000'000)};
  EXPECT_FALSE(builder.push_group(open_ms_125() + 1'000, again).has_value());
  const std::vector<qr::sources::StockQuoteRow> earlier{
      quote_row(open_ms_125() + 500, 999'900, 1'000'000)};
  EXPECT_FALSE(builder.push_group(open_ms_125() + 500, earlier).has_value());
}

TEST(ExecutionTape, ARowWhoseStampIsNotItsOwnGroupsIsRefused) {
  ExecutionTapeBuilder builder = ExecutionTapeBuilder::from_clock(testing::clock_125(), 125);
  const std::vector<qr::sources::StockQuoteRow> rows{
      quote_row(open_ms_125() + 999, 999'900, 1'000'000)};
  EXPECT_FALSE(builder.push_group(open_ms_125() + 1'000, rows).has_value());
}

TEST(ExecutionTape, AGroupOutsideTheSessionsRegularHoursIsRefusedByTheClock) {
  ExecutionTapeBuilder builder = ExecutionTapeBuilder::from_clock(testing::clock_125(), 125);
  const std::int64_t before_open = open_ms_125() - 1;
  const std::vector<qr::sources::StockQuoteRow> rows{
      quote_row(before_open, 999'900, 1'000'000)};
  EXPECT_FALSE(builder.push_group(before_open, rows).has_value());
}

TEST(ExecutionTape, FirstStrictlyAfterExcludesExactEqualityAndFirstAtOrAfterIncludesIt) {
  const ExecutionTape tape =
      tape_of({group_at(1'000, 999'900, 1'000'000), group_at(2'000, 999'900, 1'000'000)});
  const std::int64_t first_ts = tape.ts_ns[0];
  EXPECT_EQ(tape.first_strictly_after(first_ts), 1);
  EXPECT_EQ(tape.first_at_or_after(first_ts), 0);
  EXPECT_EQ(tape.first_strictly_after(tape.ts_ns[1]), kNoIndex);
  EXPECT_EQ(tape.first_at_or_after(tape.ts_ns[1] + 1), kNoIndex);
}

TEST(ExecutionTape, VerifyAgainstBindsTheTapeToTheWp5ProjectionGroupForGroup) {
  // The SAME rows through BOTH machines: WP5's projection and WP7's envelope.
  const std::vector<MicroGroup> groups{
      group_of(1'000, {{999'900, 1'000'000}, {999'800, 999'950}}),
      group_at(1'500, 1'000'000, 1'000'000),  // locked: no lawful mark
      group_of(2'000, {{999'700, 999'900}})};

  qr::nbbo::SessionPins pins;
  pins.day = "2022-07-05";
  pins.profile = SourceProfile::CentInt32;
  pins.raw_rth_row_count = 4;
  pins.complete_group_count = 3;
  qr::nbbo::GroupMachine machine =
      qr::nbbo::GroupMachine::from_clock(testing::clock_125(), pins);
  for (const MicroGroup& group : groups) {
    ASSERT_TRUE(machine.push_group(open_ms_125() + group.ms_offset, group.rows).has_value());
  }
  ASSERT_TRUE(machine.seal(0).has_value());

  ExecutionTape tape = tape_of(groups);
  const Expected<std::int64_t, Refusal> matched = verify_against(tape, machine.groups());
  ASSERT_TRUE(matched.has_value()) << matched.error().message();
  EXPECT_EQ(matched.value(), 2);

  // A drifted extremum is caught by the projection's own exact sums.
  ExecutionTape corrupted = tape;
  // 999,800 -> 999,900 puts the claimed MINIMUM above the exact mean of the
  // two eligible bids, which the projection's own sums forbid.
  corrupted.bid_min_u6[0] = corrupted.bid_max_u6[0];
  EXPECT_FALSE(verify_against(corrupted, machine.groups()).has_value());
  ExecutionTape dropped = tape;
  dropped.ts_ns.pop_back();
  dropped.bid_min_u6.pop_back();
  dropped.bid_max_u6.pop_back();
  dropped.ask_min_u6.pop_back();
  dropped.ask_max_u6.pop_back();
  dropped.eligible_count.pop_back();
  EXPECT_FALSE(verify_against(dropped, machine.groups()).has_value());
}

// ---------------------------------------------------------------------------
// The range-extremum index.
// ---------------------------------------------------------------------------

TEST(ExtremumIndexQueries, MatchABruteForceScanOverEveryRangeOfAPseudoRandomArray) {
  Lcg lcg(20260810);
  std::vector<std::int64_t> values;
  values.reserve(97);
  for (std::size_t index = 0; index < 97; ++index) {
    values.push_back(lcg.between(-40, 40));
  }
  const ExtremumIndex tree = ExtremumIndex::build(values);
  for (std::int64_t lo = 0; lo < static_cast<std::int64_t>(values.size()); ++lo) {
    for (std::int64_t hi = lo; hi < static_cast<std::int64_t>(values.size()); ++hi) {
      const auto begin = values.begin() + lo;
      const auto end = values.begin() + hi + 1;
      const std::int64_t expected_min = *std::min_element(begin, end);
      const std::int64_t expected_max = *std::max_element(begin, end);
      ASSERT_EQ(tree.range_min(lo, hi), expected_min) << lo << ".." << hi;
      ASSERT_EQ(tree.range_max(lo, hi), expected_max) << lo << ".." << hi;
      ASSERT_EQ(tree.leftmost_argmin(lo, hi), lo + (std::min_element(begin, end) - begin));
      ASSERT_EQ(tree.leftmost_argmax(lo, hi), lo + (std::max_element(begin, end) - begin));
      for (const std::int64_t threshold : {-41, -20, 0, 20, 41}) {
        std::int64_t below = kNoIndex;
        std::int64_t above = kNoIndex;
        for (std::int64_t index = lo; index <= hi; ++index) {
          if (below == kNoIndex && values[static_cast<std::size_t>(index)] <= threshold) {
            below = index;
          }
          if (above == kNoIndex && values[static_cast<std::size_t>(index)] >= threshold) {
            above = index;
          }
        }
        ASSERT_EQ(tree.first_at_or_below(lo, hi, threshold), below);
        ASSERT_EQ(tree.first_at_or_above(lo, hi, threshold), above);
      }
    }
  }
}

TEST(ExtremumIndexQueries, TheLeftmostArgumentOfATiedExtremumIsTheEarliestOne) {
  const std::vector<std::int64_t> values{5, 9, 3, 9, 3, 9};
  const ExtremumIndex tree = ExtremumIndex::build(values);
  EXPECT_EQ(tree.leftmost_argmax(0, 5), 1);
  EXPECT_EQ(tree.leftmost_argmin(0, 5), 2);
  EXPECT_EQ(tree.leftmost_argmax(2, 5), 3);
  EXPECT_EQ(tree.leftmost_argmin(3, 5), 4);
}

TEST(ExtremumIndexQueries, ASingleElementIndexAnswersItsOnlyRange) {
  const std::vector<std::int64_t> values{42};
  const ExtremumIndex tree = ExtremumIndex::build(values);
  EXPECT_EQ(tree.size(), 1);
  EXPECT_EQ(tree.range_min(0, 0), 42);
  EXPECT_EQ(tree.range_max(0, 0), 42);
  EXPECT_EQ(tree.first_at_or_below(0, 0, 41), kNoIndex);
  EXPECT_EQ(tree.first_at_or_below(0, 0, 42), 0);
}

}  // namespace
}  // namespace qr::labels
