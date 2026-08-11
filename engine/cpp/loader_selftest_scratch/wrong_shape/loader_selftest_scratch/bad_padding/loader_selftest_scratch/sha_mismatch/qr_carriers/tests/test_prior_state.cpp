// test_prior_state.cpp — THE PRIOR-STATE MACHINES.
//
// The brief's named production-constructor controls that live here:
//   * "drop first/previous sequence-valid group";
//   * "scalar-means vs mean-of-derived swap (NBBO channels)" — the arithmetic
//     half, on hand literals chosen so the two answers DIFFER (a fixture where
//     they coincide proves nothing);
//   * the update-after-the-complete-group law, watched as WHEN the prior moves.
#include <gtest/gtest.h>

#include "qr_carriers/prior_state.hpp"

namespace qr::carriers {
namespace {

TEST(StockPrintPriorMachine, PriorMovesOnlyAfterTheWholeGroupIsReduced) {
  StockPrintPrior prior;
  EXPECT_FALSE(prior.prior().present);
  EXPECT_EQ(prior.prior().validity(), Validity::MISSING);

  prior.begin_group(1'000);
  EXPECT_TRUE(prior.observe_eligible_price(100'000'000));
  // The prior is STILL absent after the first member: a machine that updated
  // inside the member loop would leak member 1 into member 2's comparison.
  EXPECT_FALSE(prior.prior().present);
  EXPECT_TRUE(prior.observe_eligible_price(102'000'000));
  EXPECT_FALSE(prior.prior().present);

  prior.commit_group();
  ASSERT_TRUE(prior.prior().present);
  // (100'000'000 + 102'000'000) / 2 = 101'000'000
  EXPECT_EQ(prior.prior().mean, 101'000'000);
  EXPECT_EQ(prior.prior().ts_ns_a, 1'000);
}

TEST(StockPrintPriorMachine, TheMeanIsAnExactIntegerSumTruncatedOnce) {
  StockPrintPrior prior;
  prior.begin_group(7);
  EXPECT_TRUE(prior.observe_eligible_price(100));
  EXPECT_TRUE(prior.observe_eligible_price(101));
  prior.commit_group();
  // 201 / 2 = 100 (truncating integer division, taken once at the accessor)
  EXPECT_EQ(prior.prior().mean, 100);
}

TEST(StockPrintPriorMachine, AGroupWithNoEligibleMemberNeverBecomesThePrior) {
  StockPrintPrior prior;
  prior.begin_group(10);
  EXPECT_TRUE(prior.observe_eligible_price(500));
  prior.commit_group();
  ASSERT_TRUE(prior.prior().present);
  EXPECT_EQ(prior.prior().mean, 500);
  EXPECT_EQ(prior.prior().ts_ns_a, 10);

  // The next group has nothing eligible: "the nearest strictly-earlier ELIGIBLE
  // timestamp group" is still the first one.
  prior.begin_group(20);
  prior.commit_group();
  EXPECT_EQ(prior.prior().mean, 500);
  EXPECT_EQ(prior.prior().ts_ns_a, 10);
}

TEST(StockPrintPriorMachine, MemberOrderInsideAGroupChangesNothing) {
  StockPrintPrior forward;
  StockPrintPrior reverse;
  forward.begin_group(3);
  reverse.begin_group(3);
  for (const std::int64_t price : {11, 22, 33}) {
    EXPECT_TRUE(forward.observe_eligible_price(price));
  }
  for (const std::int64_t price : {33, 22, 11}) {
    EXPECT_TRUE(reverse.observe_eligible_price(price));
  }
  forward.commit_group();
  reverse.commit_group();
  // 66/3 = 22 either way: an exact integer sum is order-invariant.
  EXPECT_EQ(forward.prior().mean, 22);
  EXPECT_EQ(reverse.prior().mean, forward.prior().mean);
}

// ---------------------------------------------------------------------------
// The NBBO scalar-means-before-derived law.
// ---------------------------------------------------------------------------

TEST(NbboScalarLaw, MidpointComesFromTheSCALARMeansAndNotFromPerRowMidpoints) {
  NbboScalars scalars;
  // Two eligible members: (bid 100, ask 104) and (bid 101, ask 107).
  EXPECT_TRUE(scalars.bid_u6.add(100));
  EXPECT_TRUE(scalars.ask_u6.add(104));
  EXPECT_TRUE(scalars.bid_u6.add(101));
  EXPECT_TRUE(scalars.ask_u6.add(107));

  // THE LAW: mean(bid) = 201/2 = 100, mean(ask) = 211/2 = 105,
  //          mid = 100 + (105-100)/2 = 100 + 2 = 102.
  const Typed<std::int64_t> mid = scalars.mid();
  ASSERT_EQ(mid.v, Validity::VALID);
  EXPECT_EQ(mid.value, 102);

  // THE NAMED MUTANT: mean of the per-row midpoints would be
  //   midpoint(100,104) = 102, midpoint(101,107) = 104, mean = 103.
  // The two answers differ by design, so this fixture cannot pass by accident.
  EXPECT_NE(mid.value, 103);

  // spread = mean(ask) - mean(bid) = 105 - 100 = 5.
  const Typed<std::int64_t> spread = scalars.spread();
  ASSERT_EQ(spread.v, Validity::VALID);
  EXPECT_EQ(spread.value, 5);
}

TEST(NbboScalarLaw, Cc005ImbalanceComesFromTheTwoSizeMeansAndNotFromPerRowRatios) {
  NbboScalars scalars;
  // Two eligible members: sizes (bid 200, ask 100) and (bid 200, ask 500).
  EXPECT_TRUE(scalars.bid_u6.add(100));
  EXPECT_TRUE(scalars.ask_u6.add(104));
  EXPECT_TRUE(scalars.bid_shares.add(200));
  EXPECT_TRUE(scalars.ask_shares.add(100));
  EXPECT_TRUE(scalars.bid_u6.add(100));
  EXPECT_TRUE(scalars.ask_u6.add(104));
  EXPECT_TRUE(scalars.bid_shares.add(200));
  EXPECT_TRUE(scalars.ask_shares.add(500));

  // THE LAW (CC-005): mean_bid_size = 400/2 = 200, mean_ask_size = 600/2 = 300,
  //   imbalance = (200-300)/(200+300) = -100/500 = -0.2 exactly.
  const Typed<double> imbalance = scalars.imbalance();
  ASSERT_EQ(imbalance.v, Validity::VALID);
  EXPECT_DOUBLE_EQ(imbalance.value, -0.2);

  // THE NAMED MUTANT: mean of per-row imbalances would be
  //   (200-100)/300 = 1/3, (200-500)/700 = -3/7, mean = (1/3 - 3/7)/2
  //                                                  = (7/21 - 9/21)/2 = -1/21
  //                                                  = -0.047619047619...
  EXPECT_GT(std::abs(imbalance.value - (-1.0 / 21.0)), 0.1);
}

TEST(NbboScalarLaw, AZeroSizeDenominatorIsTypedMissingAndNotADivisionByZero) {
  NbboScalars scalars;
  EXPECT_TRUE(scalars.bid_u6.add(100));
  EXPECT_TRUE(scalars.ask_u6.add(104));
  EXPECT_TRUE(scalars.bid_shares.add(0));
  EXPECT_TRUE(scalars.ask_shares.add(0));
  const Typed<double> imbalance = scalars.imbalance();
  EXPECT_EQ(imbalance.v, Validity::MISSING);
  EXPECT_DOUBLE_EQ(imbalance.value, 0.0);
}

TEST(NbboPriorMachineLaw, TheFrozenPriorMovesOnlyOnCommitAndOnlyForEligibleGroups) {
  NbboPriorMachine machine;
  machine.begin_group(100);
  EXPECT_TRUE(machine.observe_eligible(100, 104, 10, 20));
  EXPECT_FALSE(machine.prior().present);  // still frozen mid-group
  machine.commit_group();
  ASSERT_TRUE(machine.prior().present);
  EXPECT_EQ(machine.prior().scalars.bid_u6.mean().value, 100);

  machine.begin_group(200);  // no eligible member at all
  machine.commit_group();
  EXPECT_EQ(machine.prior().ts_ns_a, 100);
}

// ---------------------------------------------------------------------------
// The option per-contract prior and the global underlying prior.
// ---------------------------------------------------------------------------

TEST(OptionContractPriorLaw, EachExactContractCarriesItsOwnPriorAndNothingElseDoes) {
  OptionContractPrior prior;
  const ContractKey call{19'000, 180'000'000, qr::sources::Right::Call};
  const ContractKey put{19'000, 180'000'000, qr::sources::Right::Put};
  const ContractKey other_strike{19'000, 181'000'000, qr::sources::Right::Call};

  prior.begin_group(50);
  EXPECT_TRUE(prior.observe_eligible_price(call, 1'000'000));
  EXPECT_TRUE(prior.observe_eligible_price(call, 1'020'000));
  EXPECT_TRUE(prior.observe_eligible_price(put, 3'000'000));
  EXPECT_FALSE(prior.prior(call).present);  // frozen until the group closes
  prior.commit_group();

  // (1'000'000 + 1'020'000)/2 = 1'010'000 for the call; the put is untouched by
  // it, and a different strike has no prior at all.
  ASSERT_TRUE(prior.prior(call).present);
  EXPECT_EQ(prior.prior(call).mean, 1'010'000);
  ASSERT_TRUE(prior.prior(put).present);
  EXPECT_EQ(prior.prior(put).mean, 3'000'000);
  EXPECT_FALSE(prior.prior(other_strike).present);
  EXPECT_EQ(prior.tracked_contracts(), 2U);
}

TEST(UnderlyingPriorLaw, OnlyMembersSharingTheGreatestValidAttachmentUpdateThePrior) {
  UnderlyingPrior prior;
  prior.begin_group();
  // Three members: attachments at 10, 20 and 20 nanoseconds with underlying
  // values 10, 20 and 30. The greatest valid attachment is 20; the prior is the
  // mean of ONLY the two members sharing it: (20+30)/2 = 25.
  EXPECT_TRUE(prior.observe_valid(10, 10));
  EXPECT_TRUE(prior.observe_valid(20, 20));
  EXPECT_TRUE(prior.observe_valid(20, 30));
  EXPECT_FALSE(prior.prior().present);
  prior.commit_group();
  ASSERT_TRUE(prior.prior().present);
  EXPECT_EQ(prior.prior().mean, 25);
  EXPECT_EQ(prior.prior().ts_ns_a, 20);
}

TEST(UnderlyingPriorLaw, TheUpdateIsInvariantUnderSameGroupMemberOrder) {
  UnderlyingPrior forward;
  UnderlyingPrior reverse;
  forward.begin_group();
  reverse.begin_group();
  for (const auto& entry : {std::pair<std::int64_t, std::int64_t>{10, 10},
                            {20, 20},
                            {20, 30}}) {
    EXPECT_TRUE(forward.observe_valid(entry.first, entry.second));
  }
  for (const auto& entry : {std::pair<std::int64_t, std::int64_t>{20, 30},
                            {20, 20},
                            {10, 10}}) {
    EXPECT_TRUE(reverse.observe_valid(entry.first, entry.second));
  }
  forward.commit_group();
  reverse.commit_group();
  // "Same-group member order ... can never enter that update."
  EXPECT_EQ(forward.prior().mean, 25);
  EXPECT_EQ(reverse.prior().mean, forward.prior().mean);
  EXPECT_EQ(reverse.prior().ts_ns_a, forward.prior().ts_ns_a);
}

TEST(UnderlyingPriorLaw, AGroupWithNoValidAttachmentLeavesThePriorUnchanged) {
  UnderlyingPrior prior;
  prior.begin_group();
  EXPECT_TRUE(prior.observe_valid(5, 111));
  prior.commit_group();
  ASSERT_TRUE(prior.prior().present);

  prior.begin_group();  // "An absent valid attachment leaves the prior unchanged."
  prior.commit_group();
  EXPECT_EQ(prior.prior().mean, 111);
  EXPECT_EQ(prior.prior().ts_ns_a, 5);
}

// ---------------------------------------------------------------------------
// The groupwise sequence law, and the brief's "drop first/previous
// sequence-valid group" control.
// ---------------------------------------------------------------------------

/// Runs a sequence tape: each element is one group's finite sequence values.
std::vector<SequenceVerdict> run_sequence_tape(
    const std::vector<std::vector<std::int64_t>>& groups) {
  SequenceQuality machine;
  std::vector<SequenceVerdict> out;
  for (const auto& group : groups) {
    machine.begin_group();
    for (const std::int64_t sequence : group) {
      machine.observe_sequence(sequence);
    }
    const auto verdict = machine.verdict();
    EXPECT_TRUE(verdict.has_value());
    out.push_back(verdict.value());
    machine.commit_group();
  }
  return out;
}

TEST(SequenceLaw, GapIsCurrentMinMinusPreviousMaxAndTheFirstValidGroupHasNone) {
  //   A: {5, 9}   -> first sequence-valid group: all three missing
  //   B: {12, 15} -> gap = min(B) - max(A) = 12 - 9 = 3 >= 0 -> monotone
  //   C: {}       -> no finite sequence: all three missing, and C does NOT
  //                  become the previous group
  //   D: {14}     -> gap = 14 - max(B) = 14 - 15 = -1 -> inversion
  const auto verdicts = run_sequence_tape({{5, 9}, {12, 15}, {}, {14}});
  ASSERT_EQ(verdicts.size(), 4U);

  EXPECT_TRUE(verdicts[0].group_sequence_valid);
  EXPECT_FALSE(verdicts[0].pair_formed);

  EXPECT_TRUE(verdicts[1].pair_formed);
  EXPECT_EQ(verdicts[1].gap, 3);
  EXPECT_TRUE(verdicts[1].monotone);
  EXPECT_FALSE(verdicts[1].inversion);

  EXPECT_FALSE(verdicts[2].group_sequence_valid);
  EXPECT_FALSE(verdicts[2].pair_formed);

  EXPECT_TRUE(verdicts[3].pair_formed);
  EXPECT_EQ(verdicts[3].gap, -1);
  EXPECT_FALSE(verdicts[3].monotone);
  EXPECT_TRUE(verdicts[3].inversion);
}

TEST(SequenceLaw, DroppingTheFirstSequenceValidGroupMovesExactlyTheDeclaredOutputs) {
  // THE BRIEF'S CONTROL. Same tape without group A: B is now the first
  // sequence-valid group, so its gap/monotone/inversion become MISSING, and
  // D's gap is unchanged because it measures against B either way.
  const auto with_a = run_sequence_tape({{5, 9}, {12, 15}, {}, {14}});
  const auto without_a = run_sequence_tape({{12, 15}, {}, {14}});
  ASSERT_EQ(without_a.size(), 3U);

  EXPECT_TRUE(with_a[1].pair_formed);
  EXPECT_FALSE(without_a[0].pair_formed);  // the declared change
  EXPECT_TRUE(without_a[0].group_sequence_valid);

  // D is untouched: -1 either way.
  EXPECT_EQ(with_a[3].gap, -1);
  EXPECT_EQ(without_a[2].gap, -1);
  EXPECT_TRUE(without_a[2].inversion);
}

TEST(SequenceLaw, DroppingThePREVIOUSSequenceValidGroupChangesTheGapItAnchored) {
  // Same tape without group B: D now measures against A, so
  //   gap = 14 - max(A) = 14 - 9 = 5 >= 0 -> monotone, not an inversion.
  const auto without_b = run_sequence_tape({{5, 9}, {}, {14}});
  ASSERT_EQ(without_b.size(), 3U);
  EXPECT_TRUE(without_b[2].pair_formed);
  EXPECT_EQ(without_b[2].gap, 5);
  EXPECT_TRUE(without_b[2].monotone);
  EXPECT_FALSE(without_b[2].inversion);
}

TEST(SequenceLaw, MinAndMaxAreTheOnlyWithinGroupStatisticsAndArePermutationInvariant) {
  // "There is no within-group sequence/order statistic": the same multiset in
  // any order gives the same verdict.
  const auto ascending = run_sequence_tape({{1, 2}, {9, 4, 7}});
  const auto shuffled = run_sequence_tape({{2, 1}, {7, 9, 4}});
  ASSERT_EQ(ascending.size(), shuffled.size());
  // gap = min{4,7,9} - max{1,2} = 4 - 2 = 2 either way.
  EXPECT_EQ(ascending[1].gap, 2);
  EXPECT_EQ(shuffled[1].gap, ascending[1].gap);
  EXPECT_EQ(shuffled[1].monotone, ascending[1].monotone);
}

TEST(GroupInterarrivalLaw, TheFirstGroupHasNoInterarrivalAndTheSecondHasOne) {
  GroupInterarrival machine;
  const auto first = machine.micros_before(1'000'000);
  ASSERT_TRUE(first.has_value());
  EXPECT_FALSE(first.value().has_value());  // "present only from the second group onward"
  machine.commit_group(1'000'000);

  const auto second = machine.micros_before(4'000'000);
  ASSERT_TRUE(second.has_value());
  ASSERT_TRUE(second.value().has_value());
  // (4'000'000 - 1'000'000) ns = 3'000'000 ns = 3'000 us
  EXPECT_EQ(*second.value(), 3'000);
}

}  // namespace
}  // namespace qr::carriers
