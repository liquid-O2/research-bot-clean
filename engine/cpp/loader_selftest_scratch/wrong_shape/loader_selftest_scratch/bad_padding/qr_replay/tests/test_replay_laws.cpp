// qr_replay/tests/test_replay_laws.cpp — the C6 mutant list, one test each,
// plus the tape-validation refusals and the null-control side streams.
//
// C6: "mutants: side reversal, double cost, occupancy shift, initial-zero
// removal, tie reorder, key misjoin." Initial-zero removal lives with the MDD
// in test_scorecard.cpp; the other five are here, each with a fixture whose
// numbers differ under the mutation and only under the mutation.
#include <gtest/gtest.h>

#include <vector>

#include "qr_replay/pcg64.hpp"
#include "qr_replay/policy_gate.hpp"
#include "qr_replay/replay.hpp"
#include "replay_test_support.hpp"

namespace qr::replay {
namespace {

using test::ActionSpec;
using test::kMinuteNs;
using test::kSecondNs;
using test::make_tape;

constexpr std::size_t kH = 2;
constexpr std::int64_t kSid = 300;

std::int64_t T(std::int64_t minutes) { return minutes * kMinuteNs; }

Expected<DailyLedger, Refusal> run(const std::vector<ScoredAction>& tape,
                                   const ReplayPolicy& policy) {
  AdmitAllGate gate;
  return replay({kSid, 2023}, tape, gate, policy);
}

Expected<DailyLedger, Refusal> run(const std::vector<ScoredAction>& tape) {
  return run(tape, ReplayPolicy(kH));
}

std::int64_t census(const DailyLedger& ledger, ClockOutcome outcome) {
  return ledger.clock_census[static_cast<std::size_t>(outcome)];
}

// --- C6 mutant 1: side reversal ---------------------------------------------

TEST(ReplayLaws, ExecutesTheSelectedSideAndNeverItsMirror) {
  // The LONG row wins on prediction and is worth +1,000c; the SHORT row it beats
  // is worth +50,000c. A kernel that executes the mirror side books 50x the
  // money, which is precisely why the fixture makes the mirror the rich one.
  const std::vector<ScoredAction> tape = make_tape(
      kSid,
      {
          {1, T(0), Side::LONG, 9.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, 1000, 0,
           false},
          {1, T(0), Side::SHORT, 1.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, 50000,
           0, false},
      },
      kH);
  const Expected<DailyLedger, Refusal> result = run(tape);
  ASSERT_TRUE(result.has_value()) << (result.has_value() ? "" : result.error().message());
  ASSERT_EQ(result.value().trade_count(), 1);
  EXPECT_EQ(result.value().trades[0].key.side, Side::LONG);
  EXPECT_EQ(result.value().net_cent, 1000);
}

TEST(ReplayLaws, TheExecutedTradeCarriesItsOwnLabelsGapThroughSoTheBreachPanelSeesTheWall) {
  // The breach panel of card section 6 is `stop_hit AND gap_through_cent > 0`.
  // Both halves have to reach the ledger, and the gap-through is the half the
  // kernel cannot derive: it is what the label's ONE shared stop_scan measured
  // at the fill, and MAE cannot stand in for it (every stopped trade's MAE
  // clears 30,000 by the mod-10 lattice).
  const std::vector<ScoredAction> tape = make_tape(
      kSid,
      {
          {1, T(0), Side::LONG, 9.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, -30506,
           30506, true, 506},
          {2, T(60), Side::LONG, 9.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, -29996,
           30006, true, 0},
      },
      kH);
  const Expected<DailyLedger, Refusal> result = run(tape, ReplayPolicy(kH));
  ASSERT_TRUE(result.has_value()) << (result.has_value() ? "" : result.error().message());
  ASSERT_EQ(result.value().trade_count(), 2);
  EXPECT_TRUE(result.value().trades[0].stop_hit);
  EXPECT_EQ(result.value().trades[0].gap_through_cent, 506);
  EXPECT_TRUE(result.value().trades[1].stop_hit);
  EXPECT_EQ(result.value().trades[1].gap_through_cent, 0);
  EXPECT_EQ(result.value().trades[1].mae_cent, 30006);
}

// --- C6 mutant 2: double cost -----------------------------------------------

TEST(ReplayLaws, TheLabelsNetIsBookedUnchangedBecauseTheCostWasAlreadyChargedOnce) {
  // menu_net_cent is NET of the 576c the LABEL kernel charged (card section 3:
  // "576 cents cost once"; the barrier thresholds are "net cents after cost").
  // The replay adds nothing and subtracts nothing: a second charge would show
  // up here as 24,424c, and two trades would show it twice.
  const std::vector<ScoredAction> tape = make_tape(
      kSid,
      {
          {1, T(0), Side::LONG, 5.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, 25000, 0,
           false},
          {2, T(30), Side::LONG, 5.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, 25000,
           0, false},
      },
      kH);
  const Expected<DailyLedger, Refusal> result = run(tape);
  ASSERT_TRUE(result.has_value()) << (result.has_value() ? "" : result.error().message());
  ASSERT_EQ(result.value().trade_count(), 2);
  EXPECT_EQ(result.value().trades[0].net_cent, 25000);
  EXPECT_EQ(result.value().trades[1].net_cent, 25000);
  EXPECT_EQ(result.value().net_cent, 50000);
}

TEST(ReplayLaws, ALabelThatDidNotChargeTheCostExactlyOnceIsRefused) {
  std::vector<ScoredAction> tape = make_tape(
      kSid,
      {{1, T(0), Side::LONG, 5.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, 25000, 0,
        false}},
      kH);
  tape[0].label.cost_charged_cent = 2 * kTradeCostCent;
  const Expected<DailyLedger, Refusal> result = run(tape);
  ASSERT_FALSE(result.has_value());
  EXPECT_EQ(result.error().code(), RefusalCode::CONTENT_MISMATCH);
}

// --- C6 mutant 3: occupancy shift -------------------------------------------

std::vector<ScoredAction> occupancy_tape(std::int64_t second_clock_ts) {
  return make_tape(kSid,
                   {
                       {1, T(0), Side::LONG, 5.0, 0.1, true, LabelState::OK, kSecondNs,
                        15 * kMinuteNs, 10000, 0, false},
                       {2, second_clock_ts, Side::LONG, 5.0, 0.1, true, LabelState::OK, kSecondNs,
                        15 * kMinuteNs, 70000, 0, false},
                   },
                   kH);
}

TEST(ReplayLaws, ANewEntryRequiresAClockStrictlyAfterThePriorExit) {
  // The first trade exits at T(15)+1s.
  const std::int64_t exit_ts = T(15) + kSecondNs;

  const Expected<DailyLedger, Refusal> at_exit = run(occupancy_tape(exit_ts));
  ASSERT_TRUE(at_exit.has_value()) << (at_exit.has_value() ? "" : at_exit.error().message());
  EXPECT_EQ(at_exit.value().trade_count(), 1) << "a clock AT the prior exit instant is occupied";
  EXPECT_EQ(census(at_exit.value(), ClockOutcome::OCCUPIED), 1);
  EXPECT_EQ(at_exit.value().net_cent, 10000);

  const Expected<DailyLedger, Refusal> after_exit = run(occupancy_tape(exit_ts + 1));
  ASSERT_TRUE(after_exit.has_value()) << (after_exit.has_value() ? "" : after_exit.error().message());
  EXPECT_EQ(after_exit.value().trade_count(), 2) << "one nanosecond later the clock is free";
  EXPECT_EQ(after_exit.value().net_cent, 80000);
}

// --- C6 mutant 4: tie reorder ------------------------------------------------

TEST(ReplayLaws, AnExactTopTieAbstainsUnderEitherRowOrder) {
  // Same clock, same prediction, different money. Whichever row a mutant picks,
  // it books money the law says does not exist; and the answer may not depend on
  // which of the two rows the tape happens to list first.
  const std::vector<ScoredAction> forward = make_tape(
      kSid,
      {
          {1, T(0), Side::LONG, 4.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, 11000, 0,
           false},
          {1, T(0), Side::SHORT, 4.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, 22000,
           0, false},
      },
      kH);
  const std::vector<ScoredAction> reversed = make_tape(
      kSid,
      {
          {1, T(0), Side::SHORT, 4.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, 22000,
           0, false},
          {1, T(0), Side::LONG, 4.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, 11000, 0,
           false},
      },
      kH);

  for (const std::vector<ScoredAction>* tape : {&forward, &reversed}) {
    const Expected<DailyLedger, Refusal> result = run(*tape);
    ASSERT_TRUE(result.has_value()) << (result.has_value() ? "" : result.error().message());
    EXPECT_EQ(result.value().trade_count(), 0);
    EXPECT_EQ(result.value().net_cent, 0);
    EXPECT_EQ(census(result.value(), ClockOutcome::ABSTAIN_TIE), 1);
  }
}

TEST(ReplayLaws, ATieBelowAUniqueTopDoesNotAbstain) {
  // Two rows tie at 4.0 but a third row is strictly above them: the top IS
  // unique, so the clock trades. This is the boundary the tie law must not
  // over-reach past.
  const std::vector<ScoredAction> tape = make_tape(
      kSid,
      {
          {1, T(0), Side::LONG, 4.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, 11000, 0,
           false},
          {1, T(0), Side::SHORT, 4.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, 22000,
           0, false},
          {2, T(0), Side::LONG, 6.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, 33000, 0,
           false},
      },
      kH);
  const Expected<DailyLedger, Refusal> result = run(tape);
  ASSERT_TRUE(result.has_value()) << (result.has_value() ? "" : result.error().message());
  ASSERT_EQ(result.value().trade_count(), 1);
  EXPECT_EQ(result.value().trades[0].net_cent, 33000);
}

// --- C6 mutant 5: key misjoin ------------------------------------------------

TEST(ReplayLaws, ALabelCarryingAnotherRowsKeyIsRefusedNotExecuted) {
  std::vector<ScoredAction> tape = make_tape(
      kSid,
      {{1, T(0), Side::LONG, 5.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, 25000, 0,
        false}},
      kH);
  tape[0].label.key.decision_ordinal += 1;  // the label of a different action row
  const Expected<DailyLedger, Refusal> result = run(tape);
  ASSERT_FALSE(result.has_value());
  EXPECT_EQ(result.error().code(), RefusalCode::CONTENT_MISMATCH);
}

TEST(ReplayLaws, ALabelWhoseSideDoesNotMatchItsRowIsRefused) {
  std::vector<ScoredAction> tape = make_tape(
      kSid,
      {{1, T(0), Side::LONG, 5.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, 25000, 0,
        false}},
      kH);
  tape[0].label.key.side = Side::SHORT;
  const Expected<DailyLedger, Refusal> result = run(tape);
  ASSERT_FALSE(result.has_value());
  EXPECT_EQ(result.error().code(), RefusalCode::CONTENT_MISMATCH);
}

// --- uncapped, chronological, one position ----------------------------------

TEST(ReplayLaws, EntriesAreUncapped) {
  // Fifty non-overlapping clocks, fifty trades. No cap exists anywhere: the
  // three-trades-a-day evaluator cap was REJECTED (FINAL_PLAN section 3) and
  // survives only as a diagnostic panel outside this kernel.
  std::vector<ActionSpec> specs;
  for (std::int64_t k = 0; k < 50; ++k) {
    specs.push_back({k + 1, T(20 * k), Side::LONG, 5.0, 0.1, true, LabelState::OK, kSecondNs,
                     15 * kMinuteNs, 100, 0, false});
  }
  const Expected<DailyLedger, Refusal> result = run(make_tape(kSid, specs, kH));
  ASSERT_TRUE(result.has_value()) << (result.has_value() ? "" : result.error().message());
  EXPECT_EQ(result.value().trade_count(), 50);
  EXPECT_EQ(result.value().net_cent, 5000);
}

TEST(ReplayLaws, ANonChronologicalTapeIsRefusedAndNeverSortedIntoSilence) {
  std::vector<ScoredAction> tape = make_tape(
      kSid,
      {
          {1, T(30), Side::LONG, 5.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, 100, 0,
           false},
          {2, T(0), Side::LONG, 5.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, 100, 0,
           false},
      },
      kH);
  const Expected<DailyLedger, Refusal> result = run(tape);
  ASSERT_FALSE(result.has_value());
  EXPECT_EQ(result.error().code(), RefusalCode::OUT_OF_ORDER);
}

TEST(ReplayLaws, TwoRowsSharingOnePredictionKeyAtOneClockAreRefused) {
  const std::vector<ScoredAction> tape = make_tape(
      kSid,
      {
          {1, T(0), Side::LONG, 5.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, 100, 0,
           false},
          {1, T(0), Side::LONG, 6.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, 200, 0,
           false},
      },
      kH);
  const Expected<DailyLedger, Refusal> result = run(tape);
  ASSERT_FALSE(result.has_value());
  EXPECT_EQ(result.error().code(), RefusalCode::CONTENT_MISMATCH);
}

TEST(ReplayLaws, AForeignSessionRowIsRefused) {
  std::vector<ScoredAction> tape = make_tape(
      kSid,
      {{1, T(0), Side::LONG, 5.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, 100, 0,
        false}},
      kH);
  tape[0].key.session_ordinal += 1;
  tape[0].label.key.session_ordinal += 1;
  const Expected<DailyLedger, Refusal> result = run(tape);
  ASSERT_FALSE(result.has_value());
  EXPECT_EQ(result.error().code(), RefusalCode::CONTENT_MISMATCH);
}

TEST(ReplayLaws, AFillAtItsOwnDecisionInstantIsAClockViolation) {
  const std::vector<ScoredAction> tape = make_tape(
      kSid,
      {{1, T(0), Side::LONG, 5.0, 0.1, true, LabelState::OK, /*fill_delay_ns=*/0, 15 * kMinuteNs,
        100, 0, false}},
      kH);
  const Expected<DailyLedger, Refusal> result = run(tape);
  ASSERT_FALSE(result.has_value());
  EXPECT_EQ(result.error().code(), RefusalCode::CLOCK_VIOLATION);
}

TEST(ReplayLaws, AnExitBeforeItsOwnEntryIsAClockViolation) {
  const std::vector<ScoredAction> tape = make_tape(
      kSid,
      {{1, T(0), Side::LONG, 5.0, 0.1, true, LabelState::OK, kSecondNs, /*hold_ns=*/-kSecondNs, 100,
        0, false}},
      kH);
  const Expected<DailyLedger, Refusal> result = run(tape);
  ASSERT_FALSE(result.has_value());
  EXPECT_EQ(result.error().code(), RefusalCode::CLOCK_VIOLATION);
}

TEST(ReplayLaws, AHorizonOutsideTheSevenMenuIsARefusal) {
  const std::vector<ScoredAction> tape = make_tape(
      kSid,
      {{1, T(0), Side::LONG, 5.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, 100, 0,
        false}},
      kH);
  const Expected<DailyLedger, Refusal> result = run(tape, ReplayPolicy(kHorizonCount));
  ASSERT_FALSE(result.has_value());
  EXPECT_EQ(result.error().code(), RefusalCode::CONFIG);
}

TEST(ReplayLaws, TheKernelReadsTheHorizonItWasAskedForAndNoOther) {
  // The builder fills every other horizon with a loud sentinel, so replaying at
  // horizon 0 must produce the sentinel of horizon 0 rather than the 15-minute
  // number the tape was built around.
  const std::vector<ScoredAction> tape = make_tape(
      kSid,
      {{1, T(0), Side::LONG, 5.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, 25000, 0,
        false}},
      kH);
  const Expected<DailyLedger, Refusal> at_two = run(tape, ReplayPolicy(2));
  ASSERT_TRUE(at_two.has_value()) << (at_two.has_value() ? "" : at_two.error().message());
  EXPECT_EQ(at_two.value().net_cent, 25000);

  const Expected<DailyLedger, Refusal> at_zero = run(tape, ReplayPolicy(0));
  ASSERT_TRUE(at_zero.has_value()) << (at_zero.has_value() ? "" : at_zero.error().message());
  EXPECT_EQ(at_zero.value().net_cent, test::kWrongHorizonSentinelNet);
}

// --- null-control side streams (FINAL_PLAN sections 8 and 11) ---------------

std::vector<ScoredAction> two_sided_tape(std::size_t clocks) {
  std::vector<ActionSpec> specs;
  for (std::size_t k = 0; k < clocks; ++k) {
    const std::int64_t ordinal = static_cast<std::int64_t>(k) + 1;
    const std::int64_t ts = T(20 * static_cast<std::int64_t>(k));
    // The LONG row always wins on prediction, so the unforced replay takes LONG
    // at every clock and any change of side is the override's doing.
    specs.push_back({ordinal, ts, Side::LONG, 9.0, 0.1, true, LabelState::OK, kSecondNs,
                     15 * kMinuteNs, 100, 0, false});
    specs.push_back({ordinal, ts, Side::SHORT, 1.0, 0.1, true, LabelState::OK, kSecondNs,
                     15 * kMinuteNs, -100, 0, false});
  }
  return make_tape(kSid, specs, kH);
}

TEST(NullControls, ForcedSidesTradeTheModelsOwnClocksOnTheForcedSide) {
  const std::vector<ScoredAction> tape = two_sided_tape(6);

  ReplayPolicy forced_long(kH);
  forced_long.side_override = SideOverride::FORCE_LONG;
  const Expected<DailyLedger, Refusal> as_long = run(tape, forced_long);
  ASSERT_TRUE(as_long.has_value()) << (as_long.has_value() ? "" : as_long.error().message());
  EXPECT_EQ(as_long.value().trade_count(), 6);
  EXPECT_EQ(as_long.value().net_cent, 600);

  ReplayPolicy forced_short(kH);
  forced_short.side_override = SideOverride::FORCE_SHORT;
  const Expected<DailyLedger, Refusal> as_short = run(tape, forced_short);
  ASSERT_TRUE(as_short.has_value()) << (as_short.has_value() ? "" : as_short.error().message());
  EXPECT_EQ(as_short.value().trade_count(), 6);
  EXPECT_EQ(as_short.value().net_cent, -600);
  for (const TradeRecord& trade : as_short.value().trades) {
    EXPECT_EQ(trade.key.side, Side::SHORT);
  }
  // Identical times, different sides — the N1 shape.
  ASSERT_EQ(as_long.value().trades.size(), as_short.value().trades.size());
  for (std::size_t i = 0; i < as_long.value().trades.size(); ++i) {
    EXPECT_EQ(as_long.value().trades[i].key.decision_ts_ns,
              as_short.value().trades[i].key.decision_ts_ns);
  }
}

TEST(NullControls, AForcedSideWithNoLegalRowOfThatSideIsTypedNotSilent) {
  const std::vector<ScoredAction> tape = make_tape(
      kSid,
      {{1, T(0), Side::LONG, 9.0, 0.1, true, LabelState::OK, kSecondNs, 15 * kMinuteNs, 100, 0,
        false}},
      kH);
  ReplayPolicy forced_short(kH);
  forced_short.side_override = SideOverride::FORCE_SHORT;
  const Expected<DailyLedger, Refusal> result = run(tape, forced_short);
  ASSERT_TRUE(result.has_value()) << (result.has_value() ? "" : result.error().message());
  EXPECT_EQ(result.value().trade_count(), 0);
  EXPECT_EQ(census(result.value(), ClockOutcome::OVERRIDE_SIDE_UNAVAILABLE), 1);
}

TEST(NullControls, TheSeededCoinIsReproducibleAndAgreesWithItsOwnSeedStream) {
  const std::vector<ScoredAction> tape = two_sided_tape(12);
  ReplayPolicy coin(kH);
  coin.side_override = SideOverride::SEEDED_COIN;

  const Expected<DailyLedger, Refusal> first = run(tape, coin);
  const Expected<DailyLedger, Refusal> second = run(tape, coin);
  ASSERT_TRUE(first.has_value()) << (first.has_value() ? "" : first.error().message());
  ASSERT_TRUE(second.has_value());
  ASSERT_EQ(first.value().trade_count(), 12);
  EXPECT_EQ(first.value().coin_draws, 12);

  for (std::size_t i = 0; i < 12; ++i) {
    const Side expected = coin_side(kSid, static_cast<std::int64_t>(i));
    EXPECT_EQ(first.value().trades[i].key.side, expected) << "coin draw " << i;
    EXPECT_EQ(second.value().trades[i].key.side, first.value().trades[i].key.side);
    EXPECT_EQ(second.value().trades[i].net_cent, first.value().trades[i].net_cent);
  }
  // A coin that always said the same thing would not be a coin.
  bool saw_long = false;
  bool saw_short = false;
  for (const TradeRecord& trade : first.value().trades) {
    saw_long = saw_long || trade.key.side == Side::LONG;
    saw_short = saw_short || trade.key.side == Side::SHORT;
  }
  EXPECT_TRUE(saw_long);
  EXPECT_TRUE(saw_short);
}

// --- the causal daily-loss-limit (FINAL_PLAN section 11) --------------------

std::vector<ScoredAction> losing_tape() {
  std::vector<ActionSpec> specs;
  for (std::int64_t k = 0; k < 4; ++k) {
    specs.push_back({k + 1, T(20 * k), Side::LONG, 5.0, 0.1, true, LabelState::OK, kSecondNs,
                     15 * kMinuteNs, -40000, 0, false});
  }
  return make_tape(kSid, specs, kH);
}

TEST(DailyLossLimit, TheSessionHaltsOnceRealizedProfitAndLossReachesTheFrozenLimit) {
  // Four clocks, each -40,000c. Cumulative: -40,000; -80,000; -120,000 <=
  // -90,000 -> halt, so the fourth clock never trades.
  ReplayPolicy limited(kH);
  limited.daily_loss_limit_cent = -90000;
  const Expected<DailyLedger, Refusal> result = run(losing_tape(), limited);
  ASSERT_TRUE(result.has_value()) << (result.has_value() ? "" : result.error().message());
  EXPECT_EQ(result.value().trade_count(), 3);
  EXPECT_EQ(result.value().net_cent, -120000);
  EXPECT_TRUE(result.value().halted_daily_loss);
  EXPECT_EQ(census(result.value(), ClockOutcome::HALTED_DAILY_LOSS), 1);
}

TEST(DailyLossLimit, TheUnlimitedPanelKeepsTrading) {
  // The {inf} panel of section 11: no limit, all four clocks trade.
  const Expected<DailyLedger, Refusal> result = run(losing_tape(), ReplayPolicy(kH));
  ASSERT_TRUE(result.has_value()) << (result.has_value() ? "" : result.error().message());
  EXPECT_EQ(result.value().trade_count(), 4);
  EXPECT_EQ(result.value().net_cent, -160000);
  EXPECT_FALSE(result.value().halted_daily_loss);
}

}  // namespace
}  // namespace qr::replay
