// The three watches, the registered whole-second clock, the authority
// decision-ordinal roster and the one-to-one prediction key
// (qr_labels/watches.hpp; task card V4 section 3).
#include <gtest/gtest.h>

#include <string>
#include <vector>

#include "labels_test_support.hpp"

namespace qr::labels {
namespace {

using testing::clock_125;

DecisionClock decision_clock() {
  Expected<DecisionClock, Refusal> clock = DecisionClock::from_clock(clock_125());
  EXPECT_TRUE(clock.has_value());
  return clock.value();
}

WatchCandidate candidate(std::string id, std::int64_t visible_ts_ns, Side side = Side::LONG) {
  WatchCandidate out;
  out.candidate_id = std::move(id);
  out.candidate_physical_key = "0000000000000000000000000000000000000000000000000000000000000001";
  out.policy_name = "dc002";
  out.reversal_bps = 2;
  out.member_count = 1;
  out.visible_ts_ns = visible_ts_ns;
  out.side = side;
  return out;
}

WatchPlan plan_of(const DecisionClock& clock, const std::vector<WatchCandidate>& candidates) {
  std::vector<std::int64_t> visibilities;
  visibilities.reserve(candidates.size());
  for (const WatchCandidate& row : candidates) {
    visibilities.push_back(row.visible_ts_ns);
  }
  Expected<DecisionRoster, Refusal> roster = DecisionRoster::build(clock, visibilities);
  if (!roster.has_value()) {
    ADD_FAILURE() << "the roster refused: " << roster.error().message();
    return WatchPlan{};
  }
  Expected<WatchPlan, Refusal> plan = build_watches(125, clock, roster.value(), candidates);
  if (!plan.has_value()) {
    ADD_FAILURE() << "build_watches refused: " << plan.error().message();
    return WatchPlan{};
  }
  return std::move(plan).value();
}

/// The watch row of one stage, or a recorded failure and a blank row (never
/// `front()` on an empty ledger, which would abort the whole binary).
const WatchRow& stage_row(const WatchPlan& plan, WatchStage stage) {
  for (const WatchRow& row : plan.ledger) {
    if (row.stage == stage) {
      return row;
    }
  }
  ADD_FAILURE() << "no watch row for stage " << watch_stage_name(stage);
  static const WatchRow kBlank{};
  return kBlank;
}

/// The authority ordinal of an instant, or a recorded failure and kNoIndex.
std::int64_t ordinal_of(const DecisionRoster& roster, std::int64_t ts) {
  return testing::value_or_fail(roster.ordinal_of(ts), kNoIndex);
}

// ---------------------------------------------------------------------------
// The registered whole-second clock.
// ---------------------------------------------------------------------------

TEST(DecisionSecondClock, RegistersOneSecondPerBarMinuteOfItsOwnRegistryRow) {
  const DecisionClock clock = decision_clock();
  // Session 125 is a 390-bar day: 23,400 registered whole seconds, the first at
  // the open and the last one second before the close.
  EXPECT_EQ(clock.second_count(), 390 * 60);
  EXPECT_EQ(clock.second_ts(0).value(), clock.session_start_ns());
  EXPECT_EQ(clock.second_ts(clock.second_count() - 1).value(),
            clock.session_end_ns() - kNanosecondsPerSecond);
  EXPECT_FALSE(clock.second_ts(clock.second_count()).has_value());
  EXPECT_FALSE(clock.second_ts(-1).has_value());
}

TEST(DecisionSecondClock, TheCardsIdentityHoldsForEveryRegisteredSecond) {
  const DecisionClock clock = decision_clock();
  for (const std::int64_t second : {std::int64_t{0}, std::int64_t{1}, std::int64_t{12'345},
                                    clock.second_count() - 1}) {
    const std::int64_t ts = clock.second_ts(second).value();
    EXPECT_EQ(ts, clock.session_start_ns() + second * kNanosecondsPerSecond);
    EXPECT_EQ(testing::value_or_fail(clock.second_of(ts), kNoIndex), second);
  }
  // An instant that is not a registered whole second has no second at all.
  EXPECT_FALSE(clock.second_of(clock.session_start_ns() + 1).has_value());
  EXPECT_FALSE(clock.second_of(clock.session_end_ns()).has_value());
}

TEST(DecisionSecondClock, TheThreeSelectionRulesAreTheCardsThreeRules) {
  const DecisionClock clock = decision_clock();
  const std::int64_t start = clock.session_start_ns();
  // D0: STRICTLY after. On a second exactly, the answer is the NEXT one.
  EXPECT_EQ(clock.first_second_strictly_after(start), 1);
  EXPECT_EQ(clock.first_second_strictly_after(start + 1), 1);
  EXPECT_EQ(clock.first_second_strictly_after(start + kNanosecondsPerSecond - 1), 1);
  // D30: at OR after.
  EXPECT_EQ(clock.first_second_at_or_after(start), 0);
  EXPECT_EQ(clock.first_second_at_or_after(start + 1), 1);
  EXPECT_EQ(clock.first_second_at_or_after(start + kNanosecondsPerSecond), 1);
  // D60: the LAST at or before.
  EXPECT_EQ(clock.last_second_at_or_before(start), 0);
  EXPECT_EQ(clock.last_second_at_or_before(start + kNanosecondsPerSecond - 1), 0);
  EXPECT_EQ(clock.last_second_at_or_before(start + kNanosecondsPerSecond), 1);
  EXPECT_EQ(clock.last_second_at_or_before(start - 1), kNoIndex);
  // Past the close, the last registered second at or before is the final one.
  EXPECT_EQ(clock.last_second_at_or_before(clock.session_end_ns() + kNanosecondsPerSecond),
            clock.second_count() - 1);
}

// ---------------------------------------------------------------------------
// The three watches.
// ---------------------------------------------------------------------------

TEST(Watches, EachCandidateCreatesExactlyThreeWatchesAndNoD90OrD120) {
  const DecisionClock clock = decision_clock();
  const WatchPlan plan = plan_of(clock, {candidate("a", clock.second_ts(100).value() + 500)});
  ASSERT_EQ(plan.ledger.size(), 3U);
  EXPECT_EQ(kWatchStageCount, 3U);
  EXPECT_EQ(plan.census.watches_built, 3);
}

TEST(Watches, D0IsTheFirstRegisteredSecondStrictlyAfterOwnVisibility) {
  const DecisionClock clock = decision_clock();
  // Visibility exactly ON second 100: D0 is second 101, never 100.
  const WatchPlan on_second = plan_of(clock, {candidate("a", clock.second_ts(100).value())});
  EXPECT_EQ(stage_row(on_second, WatchStage::D0).decision_second, 101);
  // Visibility half a second into second 100: D0 is second 101.
  const WatchPlan mid =
      plan_of(clock, {candidate("a", clock.second_ts(100).value() + 500'000'000)});
  EXPECT_EQ(stage_row(mid, WatchStage::D0).decision_second, 101);
}

TEST(Watches, D30IsTheFirstRegisteredSecondAtOrAfterVisibilityPlusThirty) {
  const DecisionClock clock = decision_clock();
  const WatchPlan on_second = plan_of(clock, {candidate("a", clock.second_ts(100).value())});
  EXPECT_EQ(stage_row(on_second, WatchStage::D30).decision_second, 130);
  const WatchPlan mid =
      plan_of(clock, {candidate("a", clock.second_ts(100).value() + 500'000'000)});
  EXPECT_EQ(stage_row(mid, WatchStage::D30).decision_second, 131);
}

TEST(Watches, D60IsTheLastRegisteredSecondAtOrBeforeVisibilityPlusSixty) {
  const DecisionClock clock = decision_clock();
  const WatchPlan on_second = plan_of(clock, {candidate("a", clock.second_ts(100).value())});
  EXPECT_EQ(stage_row(on_second, WatchStage::D60).decision_second, 160);
  const WatchPlan mid =
      plan_of(clock, {candidate("a", clock.second_ts(100).value() + 500'000'000)});
  EXPECT_EQ(stage_row(mid, WatchStage::D60).decision_second, 160);
  // The whole point of the rule: the focal candidate's own age at D60 is at
  // most 60 seconds.
  const WatchRow& row = stage_row(mid, WatchStage::D60);
  EXPECT_LE(row.decision_ts_ns - row.visible_ts_ns, 60 * kNanosecondsPerSecond);
  EXPECT_GT(row.decision_ts_ns - row.visible_ts_ns, 0);
}

TEST(Watches, D60IsClockUnavailableWhenTheLastSecondIsNotStrictlyAfterVisibility) {
  const DecisionClock clock = decision_clock();
  // THE NAMED EDGE. A candidate visible exactly ON the session's final
  // registered second: "at or before visibility+60s" is that same second, and
  // "still strictly after visibility" fails, so the watch is out of session.
  const std::int64_t final_second = clock.second_ts(clock.second_count() - 1).value();
  const WatchPlan at_final = plan_of(clock, {candidate("a", final_second)});
  const WatchRow& unavailable = stage_row(at_final, WatchStage::D60);
  EXPECT_EQ(unavailable.clock_state, Validity::CLOCK_UNAVAILABLE);
  EXPECT_EQ(unavailable.decision_second, kNoIndex);
  EXPECT_EQ(unavailable.action_index, kNoIndex);
  // One microsecond earlier, the SAME final second IS strictly after it, so the
  // watch exists.
  const WatchPlan just_before = plan_of(clock, {candidate("a", final_second - 1'000)});
  const WatchRow& available = stage_row(just_before, WatchStage::D60);
  EXPECT_EQ(available.clock_state, Validity::VALID);
  EXPECT_EQ(available.decision_second, clock.second_count() - 1);
}

TEST(Watches, OutOfSessionWatchesAreRetainedAsClockUnavailableAndNeverDropped) {
  const DecisionClock clock = decision_clock();
  // Visible on the final registered second: D0 has no second strictly after,
  // D30's +30s is past the close, D60 is the edge above. All three are typed.
  const std::int64_t final_second = clock.second_ts(clock.second_count() - 1).value();
  const WatchPlan plan = plan_of(clock, {candidate("a", final_second)});
  ASSERT_EQ(plan.ledger.size(), 3U);
  for (const WatchRow& row : plan.ledger) {
    EXPECT_EQ(row.clock_state, Validity::CLOCK_UNAVAILABLE) << watch_stage_name(row.stage);
  }
  EXPECT_EQ(plan.census.watches_clock_unavailable, 3);
  EXPECT_EQ(plan.census.watches_built, 0);
  EXPECT_TRUE(plan.actions.empty());
}

TEST(Watches, TheLedgerRetainsEveryFieldTheCardEnumerates) {
  const DecisionClock clock = decision_clock();
  const WatchPlan plan = plan_of(clock, {candidate("a", clock.second_ts(10).value() + 7)});
  const WatchRow& row = stage_row(plan, WatchStage::D0);
  EXPECT_EQ(row.candidate_id, "a");
  EXPECT_EQ(row.candidate_physical_key.size(), 64U);
  EXPECT_EQ(row.policy_name, "dc002");
  EXPECT_EQ(row.reversal_bps, 2U);
  EXPECT_EQ(row.member_count, 1U);
  EXPECT_EQ(row.visible_ts_ns, clock.second_ts(10).value() + 7);
  EXPECT_EQ(row.side, Side::LONG);
  EXPECT_NE(row.action_index, kNoIndex);
  EXPECT_NE(render_watch_ledger(plan).find("dc002"), std::string::npos);
}

TEST(Watches, ManyWatchesConvergeOntoOneActionRowAndNeverDuplicateAFitRow) {
  const DecisionClock clock = decision_clock();
  // Three candidates whose D0/D30/D60 all land on second 101: one action row.
  const std::vector<WatchCandidate> candidates{
      candidate("a", clock.second_ts(100).value() + 1),
      candidate("b", clock.second_ts(100).value() + 2),
      candidate("c", clock.second_ts(100).value() + 3),
  };
  const WatchPlan plan = plan_of(clock, candidates);
  EXPECT_EQ(plan.ledger.size(), 9U);
  // D0 -> 101, D30 -> 131, D60 -> 160 for all three candidates.
  ASSERT_EQ(plan.actions.size(), 3U);
  EXPECT_EQ(plan.actions[0].decision_second, 101);
  EXPECT_EQ(plan.actions[0].watch_count, 3);
  EXPECT_EQ(plan.actions[0].stage_mask, 1U);
  EXPECT_EQ(plan.actions[1].decision_second, 131);
  EXPECT_EQ(plan.actions[2].decision_second, 160);
  EXPECT_EQ(plan.census.converged_watches, 6);
}

TEST(Watches, LongAndShortAtOneClockAreTwoActionRowsNotOne) {
  const DecisionClock clock = decision_clock();
  const std::int64_t visible = clock.second_ts(100).value() + 1;
  const WatchPlan plan = plan_of(
      clock, {candidate("a", visible, Side::LONG), candidate("b", visible, Side::SHORT)});
  ASSERT_EQ(plan.actions.size(), 6U);
  EXPECT_EQ(plan.census.actions_long, 3);
  EXPECT_EQ(plan.census.actions_short, 3);
  EXPECT_EQ(plan.actions[0].key.decision_ordinal, plan.actions[1].key.decision_ordinal);
  EXPECT_NE(plan.actions[0].key.side, plan.actions[1].key.side);
}

// ---------------------------------------------------------------------------
// The authority decision-ordinal roster.
// ---------------------------------------------------------------------------

TEST(DecisionOrdinalRoster, IsTheSortedUnionOfEverySecondAndEveryVisibility) {
  const DecisionClock clock = decision_clock();
  const std::int64_t on_second = clock.second_ts(50).value();
  const std::int64_t between = clock.second_ts(50).value() + 250'000'000;
  const std::vector<std::int64_t> visibilities{between, on_second, between};
  const Expected<DecisionRoster, Refusal> built = DecisionRoster::build(clock, visibilities);
  ASSERT_TRUE(built.has_value()) << built.error().message();
  const DecisionRoster& roster = built.value();
  // One new instant only: the visibility that is not itself a whole second, and
  // the duplicate collapses.
  EXPECT_EQ(roster.size(), clock.second_count() + 1);
  EXPECT_EQ(roster.visibilities_off_second(), 2);
  EXPECT_EQ(roster.visibilities_on_second(), 1);
  EXPECT_EQ(ordinal_of(roster, on_second), 50);
  EXPECT_EQ(ordinal_of(roster, between), 51);
  // The ordinal is NOT the second from here on: second 51 has ordinal 52.
  EXPECT_EQ(ordinal_of(roster, clock.second_ts(51).value()), 52);
}

TEST(DecisionOrdinalRoster, MovingOneVisibilityShiftsOrdinalsOnlyAtOrAfterIt) {
  // THE PERMUTATION MUTANT of the WP7 brief.
  const DecisionClock clock = decision_clock();
  const std::int64_t before = clock.second_ts(50).value() + 250'000'000;
  const std::int64_t after = clock.second_ts(80).value() + 250'000'000;
  const Expected<DecisionRoster, Refusal> built_original =
      DecisionRoster::build(clock, std::vector<std::int64_t>{before});
  const Expected<DecisionRoster, Refusal> built_moved =
      DecisionRoster::build(clock, std::vector<std::int64_t>{after});
  ASSERT_TRUE(built_original.has_value());
  ASSERT_TRUE(built_moved.has_value());
  const DecisionRoster& original = built_original.value();
  const DecisionRoster& moved = built_moved.value();
  ASSERT_EQ(original.size(), moved.size());
  for (std::int64_t second = 0; second < clock.second_count(); ++second) {
    const std::int64_t ts = clock.second_ts(second).value();
    const std::int64_t left = ordinal_of(original, ts);
    const std::int64_t right = ordinal_of(moved, ts);
    if (second <= 50) {
      EXPECT_EQ(left, right) << "second " << second << " moved but is before the change";
    } else if (second <= 80) {
      EXPECT_EQ(left, right + 1) << "second " << second;
    } else {
      EXPECT_EQ(left, right) << "second " << second;
    }
  }
}

TEST(DecisionOrdinalRoster, AnInstantOffTheRosterIsARefusalAndNeverANearestNeighbour) {
  const DecisionClock clock = decision_clock();
  const Expected<DecisionRoster, Refusal> built =
      DecisionRoster::build(clock, std::vector<std::int64_t>{});
  ASSERT_TRUE(built.has_value());
  const DecisionRoster& roster = built.value();
  EXPECT_FALSE(roster.ordinal_of(clock.second_ts(10).value() + 1).has_value());
  EXPECT_FALSE(roster.ordinal_of(clock.session_end_ns()).has_value());
  EXPECT_EQ(ordinal_of(roster, clock.second_ts(10).value()), 10);
}

TEST(DecisionOrdinalRoster, ARosterThatIsNotStrictlyIncreasingIsRefused) {
  // A duplicated instant would give TWO ordinals ONE timestamp, which is
  // exactly the one-to-one law's other direction; the roster refuses to exist.
  EXPECT_FALSE(DecisionRoster::from_instants({10, 10, 20}).has_value());
  EXPECT_FALSE(DecisionRoster::from_instants({30, 20}).has_value());
  EXPECT_TRUE(DecisionRoster::from_instants({10, 20, 30}).has_value());
}

// ---------------------------------------------------------------------------
// The one-to-one prediction key.
// ---------------------------------------------------------------------------

ActionRow action(std::int64_t ordinal, std::int64_t ts, Side side) {
  ActionRow row;
  row.key.session_ordinal = 125;
  row.key.decision_ordinal = ordinal;
  row.key.decision_ts_ns = ts;
  row.key.side = side;
  return row;
}

TEST(OneToOneKey, RefusesOneOrdinalCarryingTwoDifferentInstants) {
  const std::vector<ActionRow> rows{action(7, 1'000, Side::SHORT), action(7, 2'000, Side::LONG)};
  EXPECT_FALSE(refuse_unless_one_to_one(rows).has_value());
}

TEST(OneToOneKey, RefusesTwoOrdinalsCarryingTheSameInstant) {
  const std::vector<ActionRow> rows{action(7, 1'000, Side::LONG), action(8, 1'000, Side::LONG)};
  EXPECT_FALSE(refuse_unless_one_to_one(rows).has_value());
}

TEST(OneToOneKey, RefusesARepeatedKeyAndAnInvertedInstant) {
  const std::vector<ActionRow> repeated{action(7, 1'000, Side::LONG), action(7, 1'000, Side::LONG)};
  EXPECT_FALSE(refuse_unless_one_to_one(repeated).has_value());
  const std::vector<ActionRow> inverted{action(7, 2'000, Side::LONG), action(8, 1'000, Side::LONG)};
  EXPECT_FALSE(refuse_unless_one_to_one(inverted).has_value());
}

TEST(OneToOneKey, AcceptsTheLawfulShapeBothSidesAtOneClockAndOneSideAcrossClocks) {
  const std::vector<ActionRow> rows{action(7, 1'000, Side::SHORT), action(7, 1'000, Side::LONG),
                                    action(8, 2'000, Side::SHORT), action(8, 2'000, Side::LONG)};
  const Expected<std::int64_t, Refusal> checked = refuse_unless_one_to_one(rows);
  ASSERT_TRUE(checked.has_value()) << checked.error().message();
  EXPECT_EQ(checked.value(), 4);
}

TEST(OneToOneKey, TheProductionPlanSatisfiesItAndTheSecondIsNeverTheOrdinal) {
  const DecisionClock clock = decision_clock();
  const WatchPlan plan = plan_of(clock, {candidate("a", clock.second_ts(10).value() + 5),
                                         candidate("b", clock.second_ts(20).value() + 5)});
  EXPECT_TRUE(refuse_unless_one_to_one(plan.actions).has_value());
  bool saw_a_gap = false;
  for (const ActionRow& row : plan.actions) {
    EXPECT_EQ(row.key.decision_ts_ns,
              clock.session_start_ns() + row.decision_second * kNanosecondsPerSecond);
    if (row.key.decision_ordinal != row.decision_second) {
      saw_a_gap = true;
    }
  }
  EXPECT_TRUE(saw_a_gap) << "with two off-second visibilities the ordinal must leave the second";
}

TEST(Watches, TheLedgerIsByteIdenticalUnderAnyInputOrderNotMerelyAcrossTwoRuns) {
  // Two-run identity of a deterministic function of the same input is free; the
  // law that has to hold is that the ledger's own total order — (candidate_id,
  // stage) — does not depend on the order the roster happened to arrive in.
  const DecisionClock clock = decision_clock();
  const std::vector<WatchCandidate> forward{
      candidate("a", clock.second_ts(10).value() + 5),
      candidate("b", clock.second_ts(30).value() + 11, Side::SHORT),
      candidate("c", clock.second_ts(10).value() + 5, Side::SHORT)};
  const std::vector<WatchCandidate> shuffled{forward[2], forward[0], forward[1]};
  EXPECT_EQ(render_watch_ledger(plan_of(clock, forward)),
            render_watch_ledger(plan_of(clock, forward)));
  EXPECT_EQ(render_watch_ledger(plan_of(clock, forward)),
            render_watch_ledger(plan_of(clock, shuffled)));
}

}  // namespace
}  // namespace qr::labels
