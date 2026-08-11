// test_grid_location_candset.cpp — the prefix 1s midpoint grid (including the
// brief's "midpoint-carry fixture (no timeout; age grows; stale flag
// diagnostic-only)"), the 16 location/clock values, and the 24-field
// candidate-set rows.
#include <gtest/gtest.h>

#include <cmath>

#include "carriers_test_support.hpp"
#include "qr_carriers/candidate_set.hpp"
#include "qr_carriers/grid_1s.hpp"
#include "qr_carriers/location.hpp"

namespace qr::carriers {
namespace {

using testing::clock_125;
using testing::frame_a_of;
using testing::open_ms;

std::vector<NbboStream::EligibleMid> mids(
    std::initializer_list<std::pair<std::int64_t, std::int64_t>> entries) {
  std::vector<NbboStream::EligibleMid> out;
  for (const auto& entry : entries) {
    out.push_back(NbboStream::EligibleMid{frame_a_of(entry.first), entry.second, 20'000});
  }
  return out;
}

// ---------------------------------------------------------------------------
// THE MIDPOINT-CARRY CONTROL.
// ---------------------------------------------------------------------------

TEST(MidpointGridCarry, TheCarryHasNoTimeoutTheAgeGrowsAndStaleIsDiagnosticOnly) {
  // ONE eligible quote, at open+2'500ms, midpoint 100'000'000. Every later
  // endpoint carries it forever: "Carry has no hard timeout".
  const auto grid = MidpointGrid::build(clock_125(), mids({{2'500, 100'000'000}}));
  ASSERT_TRUE(grid.has_value());
  const auto& points = grid.value().points();

  // Endpoints 0, 1 and 2 are BEFORE the first valid quote (the quote is at
  // 2.5s and endpoint 2 is at 2.0s): "before the first valid quote it is
  // missing".
  EXPECT_FALSE(points[0].present);
  EXPECT_FALSE(points[1].present);
  EXPECT_FALSE(points[2].present);

  // Endpoint 3 (3.0s) is the first to see it: age = 3.0s - 2.5s = 0.5s =
  // 500'000us, and the source landed inside the bin [2.0s, 3.0s) -> fresh.
  ASSERT_TRUE(points[3].present);
  EXPECT_EQ(points[3].mid_u6, 100'000'000);
  EXPECT_EQ(points[3].age_micros, 500'000);
  EXPECT_TRUE(points[3].fresh_in_bin);
  EXPECT_FALSE(points[3].stale_gt_1s);

  // Endpoint 4: age 1.5s. The source is no longer in this bin, and the value is
  // now flagged stale — but it is STILL CARRIED, because the flag gates nothing.
  ASSERT_TRUE(points[4].present);
  EXPECT_EQ(points[4].mid_u6, 100'000'000);
  EXPECT_EQ(points[4].age_micros, 1'500'000);
  EXPECT_FALSE(points[4].fresh_in_bin);
  EXPECT_TRUE(points[4].stale_gt_1s);

  // Ten minutes later it is still carried, and the age has grown to exactly
  // 600s - 2.5s = 597.5s = 597'500'000us.
  ASSERT_TRUE(points[600].present);
  EXPECT_EQ(points[600].mid_u6, 100'000'000);
  EXPECT_EQ(points[600].age_micros, 597'500'000);
  EXPECT_TRUE(points[600].stale_gt_1s);

  // The very last endpoint of the session is still present: the carry never
  // expires and the grid never crosses the session.
  ASSERT_FALSE(points.empty());
  EXPECT_TRUE(points.back().present);
  // 390 bars * 60 seconds + 1 endpoint.
  EXPECT_EQ(points.size(), static_cast<std::size_t>(390 * 60 + 1));
}

TEST(MidpointGridCarry, AnEndpointCarriesOnlyQuotesSTRICTLYBeforeIt) {
  // A quote stamped exactly ON endpoint 5 belongs to endpoint 6, not 5.
  const auto grid = MidpointGrid::build(clock_125(), mids({{5'000, 100'000'000}}));
  ASSERT_TRUE(grid.has_value());
  EXPECT_FALSE(grid.value().points()[5].present);
  ASSERT_TRUE(grid.value().points()[6].present);
  EXPECT_EQ(grid.value().points()[6].age_micros, 1'000'000);
}

TEST(MidpointGridCarry, TheGridCensusCountsEveryEndpointStateInFull) {
  const auto grid = MidpointGrid::build(clock_125(), mids({{2'500, 100'000'000}}));
  ASSERT_TRUE(grid.has_value());
  const MidpointGrid::Census census = grid.value().census();
  EXPECT_EQ(census.endpoints, 390 * 60 + 1);
  EXPECT_EQ(census.first_present_endpoint, 3);
  // Endpoints 3..23400 inclusive are present: 23'401 - 3 = 23'398.
  EXPECT_EQ(census.present, 23'398);
  // Exactly one endpoint (3) is fresh; all the rest are carried and stale.
  EXPECT_EQ(census.fresh_in_bin, 1);
  EXPECT_EQ(census.stale_gt_1s, 23'397);
}

TEST(PrefixRealizedVolatility, RvNeedsTwoPresentConsecutiveEndpointsAndACarryContributesZero) {
  // Quotes at 1.5s (100.000000) and 2.5s (100.010000): endpoint 2 carries the
  // first, endpoint 3 the second, and endpoints 4+ carry the second unchanged.
  const auto grid = MidpointGrid::build(
      clock_125(), mids({{1'500, 100'000'000}, {2'500, 100'010'000}}));
  ASSERT_TRUE(grid.has_value());

  // At endpoint 1 there is no present point at all -> missing.
  EXPECT_EQ(grid.value().realized_volatility(1, 1).v, Validity::MISSING);
  // At endpoint 2 the previous endpoint is absent -> still missing ("RV requires
  // two present consecutive endpoints").
  EXPECT_EQ(grid.value().realized_volatility(2, 1).v, Validity::MISSING);

  // At endpoint 3 the pair (2,3) exists: r = log(100'010'000/100'000'000).
  const double expected = std::log(100'010'000.0 / 100'000'000.0);
  const Typed<double> rv1 = grid.value().realized_volatility(3, 1);
  ASSERT_EQ(rv1.v, Validity::VALID);
  EXPECT_NEAR(rv1.value, std::sqrt(expected * expected), 1e-18);

  // At endpoint 4 the 1s window is the pair (3,4), a CARRIED UNCHANGED midpoint:
  // "A carried unchanged midpoint contributes a zero return" -> RV is exactly 0
  // and PRESENT (it is a measured zero, not an absence).
  const Typed<double> rv_carry = grid.value().realized_volatility(4, 1);
  ASSERT_EQ(rv_carry.v, Validity::VALID);
  EXPECT_DOUBLE_EQ(rv_carry.value, 0.0);

  // Over 5s ending at endpoint 5 the only nonzero return is still the one move.
  const Typed<double> rv5 = grid.value().realized_volatility(5, 5);
  ASSERT_EQ(rv5.v, Validity::VALID);
  EXPECT_NEAR(rv5.value, std::sqrt(expected * expected), 1e-18);
}

TEST(PrefixEndpoint, TheCompleteSecondEndingAtTheCutoffIsThePrefixEndpoint) {
  const auto grid = MidpointGrid::build(clock_125(), mids({{1'000, 100'000'000}}));
  ASSERT_TRUE(grid.has_value());
  // A decision instant is session_start + decision_second*1e9, so it IS an
  // endpoint, and it reads only strictly-prior quotes.
  const auto endpoint = grid.value().prefix_endpoint(frame_a_of(60'000));
  ASSERT_TRUE(endpoint.has_value());
  EXPECT_EQ(*endpoint, 60U);
  EXPECT_EQ(grid.value().endpoint_ns(60), frame_a_of(60'000));
  // "The partial second containing cutoff ... excluded": a cutoff 300ms into a
  // second still resolves to the completed second below it.
  const auto partial = grid.value().prefix_endpoint(frame_a_of(60'300));
  ASSERT_TRUE(partial.has_value());
  EXPECT_EQ(*partial, 60U);
}

TEST(PrefixEndpoint, ACutoffAtOrPastTheGridEndIsAbsentAndNeverSubstitutesTheClose) {
  // The contract this fixture holds the implementation to is the header's own:
  // "Absent when the cutoff is before the session start or PAST THE GRID."
  // Substituting the last endpoint for an out-of-range cutoff is a
  // range-limiting guard returning a VALUE where the contract says nullopt, and
  // the value it returns is the session close — "a terminal close endpoint,
  // never a decision instant" (card section 3).
  const auto grid = MidpointGrid::build(clock_125(), mids({{1'000, 100'000'000}}));
  ASSERT_TRUE(grid.has_value());
  const std::size_t last = grid.value().size() - 1U;
  const std::int64_t close_ns = grid.value().endpoint_ns(last);
  EXPECT_EQ(close_ns, clock_125().session_end_a().ns());

  const auto at_close = grid.value().prefix_endpoint(close_ns);
  EXPECT_FALSE(at_close.has_value())
      << "a cutoff standing on the session close returned endpoint " << *at_close << " of "
      << grid.value().size() << " — the close itself, substituted for an absent answer";
  const auto past_close = grid.value().prefix_endpoint(close_ns + kNanosPerSecond);
  EXPECT_FALSE(past_close.has_value())
      << "a cutoff one second past the close returned endpoint " << *past_close
      << " — the close substituted for an instant that is not on the grid at all";
  const auto far_past = grid.value().prefix_endpoint(close_ns + 3'600 * kNanosPerSecond);
  EXPECT_FALSE(far_past.has_value())
      << "an hour past the close returned endpoint " << *far_past;

  // The last LAWFUL cutoff — the final registered second — is unaffected, and so
  // is the last nanosecond before the close: the wall moves nothing inside the
  // session.
  const auto final_second = grid.value().prefix_endpoint(close_ns - kNanosPerSecond);
  ASSERT_TRUE(final_second.has_value());
  EXPECT_EQ(*final_second, last - 1U);
  const auto last_nanosecond = grid.value().prefix_endpoint(close_ns - 1);
  ASSERT_TRUE(last_nanosecond.has_value());
  EXPECT_EQ(*last_nanosecond, last - 1U);
}

// ---------------------------------------------------------------------------
// The 16 location/clock values.
// ---------------------------------------------------------------------------

TEST(LocationValues, TheSixteenValuesAreTheCardsSixteenValues) {
  // Prefix midpoints: open 100.000000 at 1s, a high of 100.020000 at 100s, a low
  // of 99.980000 at 200s, and the anchor m = 100.010000 at 250s.
  const std::vector<NbboStream::EligibleMid> eligible =
      mids({{1'000, 100'000'000}, {100'000, 100'020'000}, {200'000, 99'980'000},
            {250'000, 100'010'000}});
  const auto grid = MidpointGrid::build(clock_125(), eligible);
  ASSERT_TRUE(grid.has_value());

  // One stock print group at 240s and one option print group at 200s.
  std::vector<GroupRecord> stock_groups(1);
  stock_groups[0].ts_ns_a = frame_a_of(240'000);
  std::vector<GroupRecord> option_groups(1);
  option_groups[0].ts_ns_a = frame_a_of(200'000);
  // VWAP after that stock group: 100'000'000 * 300 notional over 300 shares.
  const std::vector<std::int64_t> notional{100'000'000LL * 300LL};
  const std::vector<std::int64_t> sizes{300};

  LocationInputs inputs;
  inputs.clock = &clock_125();
  inputs.grid = &grid.value();
  inputs.eligible_mids = eligible;
  inputs.stock_print_groups = stock_groups;
  inputs.option_print_groups = option_groups;
  inputs.vwap_notional_prefix = notional;
  inputs.vwap_size_prefix = sizes;
  const LocationBuilder builder(inputs);

  const auto row = builder.build(frame_a_of(300'000), Side::LONG);
  ASSERT_TRUE(row.has_value());
  const auto& value = row.value().value;

  // The session is 390 bars = 23'400s. 300s elapsed -> fraction 300/23400.
  const double fraction = 300.0 / 23'400.0;
  EXPECT_DOUBLE_EQ(value[kLocSessionTimeFraction], fraction);
  // THE CYCLICAL ENCODING (orchestrator ruling): sin(2*pi*f) / cos(2*pi*f).
  //   f = 300/23400 = 1/78; 2*pi/78 = 0.0805536... rad
  //   sin = 0.08046656871672588, cos = 0.99675730813421
  EXPECT_DOUBLE_EQ(value[kLocSessionTimeSine], std::sin(kTwoPi * fraction));
  EXPECT_DOUBLE_EQ(value[kLocSessionTimeCosine], std::cos(kTwoPi * fraction));
  EXPECT_NEAR(value[kLocSessionTimeSine], 0.08046656871672588, 1e-15);
  EXPECT_NEAR(value[kLocSessionTimeCosine], 0.99675730813421004, 1e-15);
  // ... and it is NOT the bare sin(f)/cos(f) this lane first shipped: at this
  // fraction the two differ in the second decimal place, so the fixture cannot
  // pass under either reading by accident.
  EXPECT_GT(std::abs(value[kLocSessionTimeSine] - std::sin(fraction)), 0.06);
  EXPECT_GT(std::abs(value[kLocSessionTimeCosine] - std::cos(fraction)), 0.003);
  EXPECT_DOUBLE_EQ(value[kLocSecondsToCloseFraction], (23'400.0 - 300.0) / 23'400.0);
  EXPECT_DOUBLE_EQ(value[kLocEarlyCloseBit], 0.0);  // session 125 is a 390-bar day
  // The five pure clock values are ALWAYS present.
  for (const std::size_t index : {kLocSessionTimeFraction, kLocSessionTimeSine,
                                  kLocSessionTimeCosine, kLocSecondsToCloseFraction,
                                  kLocEarlyCloseBit}) {
    EXPECT_TRUE(row.value().presence(index)) << location_value_name(index);
  }

  // m = 100'010'000; open = 100'000'000; high = 100'020'000; low = 99'980'000.
  //   from open:  (100'010'000-100'000'000)*10'000/100'000'000 = 1e8/1e8 = 1 bps
  EXPECT_DOUBLE_EQ(value[kLocOrientedBpsFromOpen], 1.0);
  //   from high:  (100'010'000-100'020'000)*10'000/100'020'000 = -1e8/100'020'000
  //               = -0.9998 -> TRUNCATED toward zero -> 0
  EXPECT_DOUBLE_EQ(value[kLocOrientedBpsFromRunningHigh], 0.0);
  //   from low:   (100'010'000-99'980'000)*10'000/99'980'000 = 3e8/99'980'000
  //               = 3.0006 -> 3
  EXPECT_DOUBLE_EQ(value[kLocOrientedBpsFromRunningLow], 3.0);
  //   range:      (100'020'000-99'980'000)*10'000/100'000'000 = 4e8/1e8 = 4 bps
  EXPECT_DOUBLE_EQ(value[kLocRunningRangeBps], 4.0);
  //   from VWAP:  vwap = 30'000'000'000/300 = 100'000'000; same as open -> 1 bps
  EXPECT_DOUBLE_EQ(value[kLocOrientedBpsFromPrefixVwap], 1.0);
  //   spread:     20'000*10'000/100'010'000 = 2e8/100'010'000 = 1.9998 -> 1
  EXPECT_DOUBLE_EQ(value[kLocCurrentSpreadBps], 1.0);
  //   last stock print 300s - 240s = 60s; last option print 300s - 200s = 100s
  EXPECT_NEAR(value[kLocLog1pSecondsSinceLastStockPrint], std::log1p(60.0), 1e-15);
  EXPECT_NEAR(value[kLocLog1pSecondsSinceLastOptionPrint], std::log1p(100.0), 1e-15);

  // SHORT negates every ORIENTED distance and leaves the range and the spread.
  const auto short_row = builder.build(frame_a_of(300'000), Side::SHORT);
  ASSERT_TRUE(short_row.has_value());
  EXPECT_DOUBLE_EQ(short_row.value().value[kLocOrientedBpsFromOpen], -1.0);
  EXPECT_DOUBLE_EQ(short_row.value().value[kLocOrientedBpsFromRunningLow], -3.0);
  EXPECT_DOUBLE_EQ(short_row.value().value[kLocRunningRangeBps], 4.0);
  EXPECT_DOUBLE_EQ(short_row.value().value[kLocCurrentSpreadBps], 1.0);
  EXPECT_DOUBLE_EQ(short_row.value().value[kLocSessionTimeFraction], fraction);
}

TEST(LocationValues, TheSessionClockIsACYCLICALEncodingOverTheWholeSession) {
  const std::vector<NbboStream::EligibleMid> eligible;
  const auto grid = MidpointGrid::build(clock_125(), eligible);
  ASSERT_TRUE(grid.has_value());
  const std::vector<GroupRecord> empty_groups;
  const std::vector<std::int64_t> empty_sums;
  LocationInputs inputs;
  inputs.clock = &clock_125();
  inputs.grid = &grid.value();
  inputs.eligible_mids = eligible;
  inputs.stock_print_groups = empty_groups;
  inputs.option_print_groups = empty_groups;
  inputs.vwap_notional_prefix = empty_sums;
  inputs.vwap_size_prefix = empty_sums;
  const LocationBuilder builder(inputs);

  // One session = one full turn, so the quarter marks land on the axes.
  // 23'400s of RTH: a quarter is 5'850s, a half is 11'700s.
  const auto at_open = builder.build(frame_a_of(0), Side::LONG);
  ASSERT_TRUE(at_open.has_value());
  EXPECT_DOUBLE_EQ(at_open.value().value[kLocSessionTimeSine], 0.0);
  EXPECT_DOUBLE_EQ(at_open.value().value[kLocSessionTimeCosine], 1.0);

  const auto at_quarter = builder.build(frame_a_of(5'850'000), Side::LONG);
  ASSERT_TRUE(at_quarter.has_value());
  EXPECT_NEAR(at_quarter.value().value[kLocSessionTimeSine], 1.0, 1e-12);
  EXPECT_NEAR(at_quarter.value().value[kLocSessionTimeCosine], 0.0, 1e-12);

  const auto at_half = builder.build(frame_a_of(11'700'000), Side::LONG);
  ASSERT_TRUE(at_half.has_value());
  EXPECT_NEAR(at_half.value().value[kLocSessionTimeSine], 0.0, 1e-12);
  EXPECT_NEAR(at_half.value().value[kLocSessionTimeCosine], -1.0, 1e-12);
  // The bare-fraction reading would give sin(0.5) = 0.479 and cos(0.5) = 0.878
  // here — nowhere near the axis.
  EXPECT_LT(at_half.value().value[kLocSessionTimeCosine], -0.99);
}

TEST(LocationValues, WithNoPrefixMidpointEveryTapeDependentValueIsMaskedButTheClockIsNot) {
  const std::vector<NbboStream::EligibleMid> eligible;
  const auto grid = MidpointGrid::build(clock_125(), eligible);
  ASSERT_TRUE(grid.has_value());
  const std::vector<GroupRecord> empty_groups;
  const std::vector<std::int64_t> empty_sums;

  LocationInputs inputs;
  inputs.clock = &clock_125();
  inputs.grid = &grid.value();
  inputs.eligible_mids = eligible;
  inputs.stock_print_groups = empty_groups;
  inputs.option_print_groups = empty_groups;
  inputs.vwap_notional_prefix = empty_sums;
  inputs.vwap_size_prefix = empty_sums;
  const LocationBuilder builder(inputs);
  const auto row = builder.build(frame_a_of(300'000), Side::LONG);
  ASSERT_TRUE(row.has_value());

  for (std::size_t index = 0; index < kLocationValueCount; ++index) {
    const bool pure_clock = index <= kLocEarlyCloseBit;
    EXPECT_EQ(row.value().presence(index), pure_clock) << location_value_name(index);
    if (!pure_clock) {
      EXPECT_DOUBLE_EQ(row.value().value[index], 0.0) << location_value_name(index);
    }
  }
  EXPECT_EQ(kLocationValueCount, 16U);
  EXPECT_EQ(kLocationProjectionWidth, 32U);
  EXPECT_FALSE(location_value_is_continuous(kLocEarlyCloseBit));
  EXPECT_TRUE(location_value_is_continuous(kLocCurrentSpreadBps));
}

// ---------------------------------------------------------------------------
// The 24-field candidate-set rows.
// ---------------------------------------------------------------------------

TEST(CandidateSetRow, TheTwentyFourFieldsAreTheCardsTwentyFourFields) {
  EXPECT_EQ(kCandidateSetFieldCount, 24U);
  EXPECT_EQ(kPolicyVocabularySize, 12U);
  EXPECT_EQ(kCandidateRelationCount, 4U);
  EXPECT_EQ(kVisibilityFlagCount, 5U);

  VisibleCandidate candidate;
  candidate.policy_index = policy_index_of("dc010");  // the 9th entry, index 8
  candidate.reversal_bps = 30;
  candidate.member_count = 3;
  candidate.visible_ts_ns_a = frame_a_of(280'000);
  candidate.relation = CandidateRelation::OWN;
  ASSERT_EQ(candidate.policy_index, 8U);

  const auto row = build_candidate_set_row(candidate, frame_a_of(300'000));
  ASSERT_TRUE(row.has_value());
  const auto& value = row.value().value;

  // The 12-way policy one-hot: exactly index 8 is hot.
  for (std::size_t index = 0; index < kPolicyVocabularySize; ++index) {
    EXPECT_DOUBLE_EQ(value[kCandPolicyOneHot + index], index == 8U ? 1.0 : 0.0);
  }
  // reversal/20 = 30/20 = 1.5
  EXPECT_DOUBLE_EQ(value[kCandReversalOver20], 1.5);
  // log1p member count = log1p(3)
  EXPECT_NEAR(value[kCandLog1pMemberCount], std::log1p(3.0), 1e-15);
  // age = 300s - 280s = 20s -> log1p(20)
  EXPECT_NEAR(value[kCandLog1pAgeSeconds], std::log1p(20.0), 1e-15);
  // the relation one-hot: OWN
  EXPECT_DOUBLE_EQ(value[kCandRelationOneHot + 0], 1.0);
  for (std::size_t index = 1; index < kCandidateRelationCount; ++index) {
    EXPECT_DOUBLE_EQ(value[kCandRelationOneHot + index], 0.0);
  }
  // visibility-in-last-{1,5,15,30,60}s at an age of 20s: 0,0,0,1,1
  EXPECT_DOUBLE_EQ(value[kCandVisibilityFlags + 0], 0.0);
  EXPECT_DOUBLE_EQ(value[kCandVisibilityFlags + 1], 0.0);
  EXPECT_DOUBLE_EQ(value[kCandVisibilityFlags + 2], 0.0);
  EXPECT_DOUBLE_EQ(value[kCandVisibilityFlags + 3], 1.0);
  EXPECT_DOUBLE_EQ(value[kCandVisibilityFlags + 4], 1.0);
  // Every field is present; the one-hots and flags are structural.
  for (std::size_t field = 0; field < kCandidateSetFieldCount; ++field) {
    EXPECT_TRUE(row.value().presence(field)) << candidate_set_field_name(field);
  }
}

TEST(CandidateSetRow, TheRecencyFlagsAreInclusiveExactlyAtTheirHorizon) {
  VisibleCandidate candidate;
  candidate.policy_index = 0;
  candidate.member_count = 1;
  candidate.relation = CandidateRelation::OPPOSITE;
  // Age exactly 60s: section 2 admits "no more than 60s old", so the 60s flag is
  // set and the 30s one is not.
  candidate.visible_ts_ns_a = frame_a_of(240'000);
  const auto row = build_candidate_set_row(candidate, frame_a_of(300'000));
  ASSERT_TRUE(row.has_value());
  EXPECT_DOUBLE_EQ(row.value().value[kCandVisibilityFlags + 3], 0.0);  // 30s
  EXPECT_DOUBLE_EQ(row.value().value[kCandVisibilityFlags + 4], 1.0);  // 60s
  EXPECT_DOUBLE_EQ(row.value().value[kCandRelationOneHot + 1], 1.0);   // OPPOSITE
}

TEST(CandidateSetRow, ANonprimitivePolicyOrANonPriorVisibilityRefusesRatherThanZeroCodes) {
  VisibleCandidate candidate;
  candidate.policy_index = policy_index_of("UNION");
  EXPECT_EQ(candidate.policy_index, kPolicyVocabularySize);
  candidate.member_count = 1;
  candidate.visible_ts_ns_a = frame_a_of(100'000);
  // "Registry rows with stream_policy_name=UNION ... enter no prefix set" — the
  // encoder refuses instead of silently zero-coding a 13th policy.
  EXPECT_FALSE(build_candidate_set_row(candidate, frame_a_of(300'000)).has_value());

  candidate.policy_index = 0;
  candidate.visible_ts_ns_a = frame_a_of(300'000);  // equal to the decision
  const auto equal = build_candidate_set_row(candidate, frame_a_of(300'000));
  ASSERT_FALSE(equal.has_value());
  EXPECT_EQ(equal.error().code(), RefusalCode::CLOCK_VIOLATION);
}

TEST(CandidateSetRow, TheFrozenPolicyVocabularyOrderIsTheCardsOrder) {
  const std::array<std::string_view, 12> expected{"dc001", "dc002", "dc003", "dc004",
                                                  "dc005", "dc006", "dc007", "dc008",
                                                  "dc010", "dc012", "dc015", "dc020"};
  for (std::size_t index = 0; index < expected.size(); ++index) {
    EXPECT_EQ(kPolicyVocabulary[index], expected[index]);
    EXPECT_EQ(policy_index_of(expected[index]), index);
  }
  // The gaps are NOT primitive: dc009, dc011, dc013, dc014, dc016..dc019.
  for (const char* absent : {"dc009", "dc011", "dc013", "dc014", "dc016", "dc019", "UNION"}) {
    EXPECT_EQ(policy_index_of(absent), kPolicyVocabularySize) << absent;
  }
  EXPECT_FALSE(candidate_set_field_is_continuous(kCandPolicyOneHot));
  EXPECT_TRUE(candidate_set_field_is_continuous(kCandReversalOver20));
  EXPECT_TRUE(candidate_set_field_is_continuous(kCandLog1pAgeSeconds));
  EXPECT_FALSE(candidate_set_field_is_continuous(kCandVisibilityFlags));
}

// ---------------------------------------------------------------------------
// The RAGGED candidate-set block (orchestrator ruling: no cap, CSR offsets).
// ---------------------------------------------------------------------------

CandidateSetRow row_for(std::size_t policy_index, std::int64_t age_seconds) {
  VisibleCandidate candidate;
  candidate.policy_index = policy_index;
  candidate.member_count = 1;
  candidate.relation = CandidateRelation::OWN;
  candidate.visible_ts_ns_a = frame_a_of(300'000 - age_seconds * 1'000);
  auto built = build_candidate_set_row(candidate, frame_a_of(300'000));
  EXPECT_TRUE(built.has_value());
  return built.value();
}

TEST(CandidateSetBlockLaw, AnEmptyBlockHoldsTheSingleZeroOffsetAndNotAnEmptyVector) {
  const CandidateSetBlock block;
  EXPECT_EQ(block.decisions(), 0U);
  EXPECT_EQ(block.total_rows(), 0U);
  EXPECT_EQ(block.max_rows(), 0U);
  // The CSR invariant qr_nbbo already paid for: offsets carry rows()+1 entries,
  // so the empty projection is {0} and never {}.
  ASSERT_EQ(block.offsets().size(), 1U);
  EXPECT_EQ(block.offsets()[0], 0U);
}

TEST(CandidateSetBlockLaw, DecisionsOfDifferentWidthsConcatenateWithExactOffsets) {
  CandidateSetBlock block;
  const std::vector<CandidateSetRow> none;
  const std::vector<CandidateSetRow> one{row_for(0, 5)};
  const std::vector<CandidateSetRow> three{row_for(1, 5), row_for(2, 15), row_for(3, 45)};

  ASSERT_TRUE(block.push_decision(three).has_value());
  ASSERT_TRUE(block.push_decision(none).has_value());
  ASSERT_TRUE(block.push_decision(one).has_value());

  // 3 rows, then 0, then 1: offsets are 0, 3, 3, 4 — four entries for three
  // decisions, and the empty decision is a REAL decision with zero rows.
  ASSERT_EQ(block.offsets().size(), 4U);
  EXPECT_EQ(block.offsets()[0], 0U);
  EXPECT_EQ(block.offsets()[1], 3U);
  EXPECT_EQ(block.offsets()[2], 3U);
  EXPECT_EQ(block.offsets()[3], 4U);
  EXPECT_EQ(block.decisions(), 3U);
  EXPECT_EQ(block.row_count(0), 3U);
  EXPECT_EQ(block.row_count(1), 0U);
  EXPECT_EQ(block.row_count(2), 1U);
  EXPECT_EQ(block.total_rows(), 4U);
  EXPECT_EQ(block.max_rows(), 3U);
  // 4 rows x 24 fields, concatenated.
  EXPECT_EQ(block.values().size(), 4U * kCandidateSetFieldCount);
  EXPECT_EQ(block.validity().size(), 4U * kCandidateSetFieldCount);

  // Row addressing lands on the right policy one-hot in every decision.
  EXPECT_DOUBLE_EQ(block.value_at(0, 0, kCandPolicyOneHot + 1), 1.0);
  EXPECT_DOUBLE_EQ(block.value_at(0, 2, kCandPolicyOneHot + 3), 1.0);
  EXPECT_DOUBLE_EQ(block.value_at(2, 0, kCandPolicyOneHot + 0), 1.0);
  EXPECT_EQ(block.validity_at(2, 0, kCandLog1pAgeSeconds), Validity::VALID);
}

TEST(CandidateSetBlockLaw, TheBlockIsNeverCappedSoAWideDecisionKeepsEveryCandidate) {
  // Session 125's widest measured decision carries 362 visible candidates, far
  // past APPENDIX C4's 64-row sketch; the ruling is that the set is ragged and
  // uncapped, so a 400-row decision must survive whole.
  CandidateSetBlock block;
  std::vector<CandidateSetRow> wide;
  wide.reserve(400);
  for (std::int64_t index = 0; index < 400; ++index) {
    wide.push_back(row_for(static_cast<std::size_t>(index % 12), 1 + index % 59));
  }
  ASSERT_TRUE(block.push_decision(wide).has_value());
  EXPECT_EQ(block.row_count(0), 400U);
  EXPECT_EQ(block.max_rows(), 400U);
  EXPECT_GT(block.row_count(0), 64U);
  EXPECT_EQ(block.values().size(), 400U * kCandidateSetFieldCount);
}

}  // namespace
}  // namespace qr::carriers\n