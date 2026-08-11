// THE label kernel (qr_labels/label_kernel.hpp): the entry rule, the shared
// stop_scan, the seven-horizon menu, the co-primary certificate, the barrier
// auxiliary, the three label states, and the APPENDIX C5 stop-shift mutant.
//
// Every expectation below is HAND-COMPUTED from the $1.00 fill: with
// entry_u6 = 1,000,000 the frac equals the price move in u6, so
// `net_cent = move*10 - 576` and the fixture literals are readable arithmetic
// rather than recorded output.
#include <gtest/gtest.h>

#include <initializer_list>
#include <vector>

#include "labels_test_support.hpp"

namespace qr::labels {
namespace {

using testing::bytes_of;
using testing::group_at;
using testing::group_of;
using testing::kFill;
using testing::key_at;
using testing::label_or_fail;
using testing::Lcg;
using testing::linear_reference_label;
using testing::MicroGroup;
using testing::net_of_move;

constexpr std::int64_t kMs = 1'000'000;  // one millisecond in nanoseconds

/// The entry group ($1.00 ask, 1c-wide book) followed by one lawful mark per
/// move, one second apart.
std::vector<MicroGroup> ladder(std::initializer_list<std::int64_t> moves) {
  std::vector<MicroGroup> groups{group_at(1'000, 999'900, kFill)};
  std::int64_t ms = 1'000;
  for (const std::int64_t move : moves) {
    ms += 1'000;
    groups.push_back(group_at(ms, kFill + move, kFill + move + 100));
  }
  return groups;
}

/// A decision half a second before the ladder's entry group.
ActionKey before_entry(Side side = Side::LONG) { return key_at(500 * kMs, side); }

/// The mirror of a LONG tape about 2,000,000: a SHORT on the mirror sees the
/// same moves, so both sides must produce identical ledgers.
std::vector<MicroGroup> mirrored(const std::vector<MicroGroup>& groups) {
  std::vector<MicroGroup> out;
  for (const MicroGroup& group : groups) {
    MicroGroup flipped;
    flipped.ms_offset = group.ms_offset;
    for (const qr::sources::StockQuoteRow& row : group.rows) {
      qr::sources::StockQuoteRow mirror = row;
      mirror.bid_u6 = 2'000'000 - row.ask_u6;
      mirror.ask_u6 = 2'000'000 - row.bid_u6;
      flipped.rows.push_back(mirror);
    }
    out.push_back(flipped);
  }
  return out;
}

// ---------------------------------------------------------------------------
// The entry rule and the fills.
// ---------------------------------------------------------------------------

TEST(LabelEntry, IsTheFirstLawfulMarkStrictlyAfterTheDecisionAndNeverAtEquality) {
  const SessionLabelIndex index = testing::index_of(ladder({100, 200}));
  const LabelRow early = label_or_fail(index, before_entry(), Side::LONG);
  EXPECT_EQ(early.entry_index, 0);
  EXPECT_EQ(early.entry_u6, kFill);
  // A decision AT the first group's own instant fills at the NEXT one.
  const LabelRow on_group = label_or_fail(index, key_at(1'000 * kMs, Side::LONG), Side::LONG);
  EXPECT_EQ(on_group.entry_index, 1);
  EXPECT_EQ(on_group.entry_u6, kFill + 100 + 100);
}

TEST(LabelEntry, EqualMillisecondFillsAndMarksAreTheAdverseEnvelope) {
  // Two members at the fill millisecond: the LONG pays the HIGHEST ask and is
  // marked at the LOWEST bid. "adverse wins equal-ms", both ways.
  const SessionLabelIndex index = testing::index_of(
      {group_of(1'000, {{999'900, kFill}, {999'800, 999'950}}), group_at(2'000, 999'950, 999'990)});
  const LabelRow row = label_or_fail(index, before_entry(), Side::LONG);
  EXPECT_EQ(row.entry_u6, kFill);
  // The MAE includes the entry group's own mark: bid_min there is 999,800.
  EXPECT_EQ(row.menu.menu_mae_cent[0], -net_of_move(-200));
  EXPECT_EQ(row.menu.menu_net_cent[0], net_of_move(-50));
}

TEST(LabelEntry, TheFiveHundredAndSeventySixCentCostIsChargedOncePerHorizon) {
  const SessionLabelIndex index = testing::index_of(ladder({0}));
  const LabelRow row = label_or_fail(index, before_entry(), Side::LONG);
  EXPECT_EQ(row.menu.cost_charged_cent, kTradeCostCent);
  for (std::size_t horizon = 0; horizon < kHorizonCount; ++horizon) {
    // A flat exit is not a flat outcome: it is exactly one round trip of cost,
    // and the GROSS of every horizon is zero.
    EXPECT_EQ(row.menu.menu_net_cent[horizon], -kTradeCostCent);
    EXPECT_EQ(row.menu.menu_net_cent[horizon] + kTradeCostCent, 0);
  }
  EXPECT_EQ(row.certificate_net_cent, -kTradeCostCent);
}

// ---------------------------------------------------------------------------
// The wall.
// ---------------------------------------------------------------------------

TEST(StopWall, CrossesAtTheExactMinusThirtyThousandBoundaryAndNotOneTickEarlier) {
  // -2,942 is a net of -29,996 (above the wall); -2,943 is -30,006 (at or
  // below it). The wall is the boundary, not the neighbourhood.
  const SessionLabelIndex above = testing::index_of(ladder({-2'942, -1'000}));
  EXPECT_FALSE(label_or_fail(above, before_entry(), Side::LONG).scan.crossed);

  const SessionLabelIndex at = testing::index_of(ladder({-2'942, -2'943, -1'000}));
  const LabelRow row = label_or_fail(at, before_entry(), Side::LONG);
  ASSERT_TRUE(row.scan.crossed);
  EXPECT_EQ(row.scan.crossing_index, 2);
  EXPECT_EQ(row.scan.crossing_net_cent, -30'006);
}

TEST(StopWall, FillsAtTheNextLawfulMarkStrictlyAfterTheCrossing) {
  const SessionLabelIndex index = testing::index_of(ladder({-2'943, -1'000}));
  const LabelRow row = label_or_fail(index, before_entry(), Side::LONG);
  ASSERT_TRUE(row.scan.crossed);
  EXPECT_EQ(row.scan.crossing_index, 1);
  EXPECT_EQ(row.scan.exit_index, 2);
  EXPECT_EQ(row.scan.exit_net_cent, net_of_move(-1'000));
  // The realised menu net is the FILL's net, not the crossing's.
  EXPECT_EQ(row.menu.menu_net_cent[0], net_of_move(-1'000));
  EXPECT_EQ(row.menu.stop_hit[0], 1U);
}

TEST(StopWall, GapThroughBeyondTheWallIsRetainedAndReportedNeverCappedAtTheWall) {
  const SessionLabelIndex index = testing::index_of(ladder({-2'943, -20'000}));
  const LabelRow row = label_or_fail(index, before_entry(), Side::LONG);
  ASSERT_TRUE(row.scan.crossed);
  EXPECT_EQ(row.scan.exit_net_cent, net_of_move(-20'000));  // -200,576
  EXPECT_LT(row.scan.exit_net_cent, kStopWallNetCent);
  EXPECT_EQ(row.scan.gap_through_cent, kStopWallNetCent - net_of_move(-20'000));
  // The loss is retained in full in the menu ledger, not clipped to -30,000.
  EXPECT_EQ(row.menu.menu_net_cent[0], net_of_move(-20'000));
  EXPECT_EQ(row.menu.menu_mae_cent[0], -net_of_move(-20'000));
}

TEST(StopWall, IsScannedStrictlyAfterTheFillSoAWideEntryCannotStopItself) {
  // The entry group's own mark is -1,576 here; even a mark far below the wall
  // AT the fill instant could not trigger, because the scan starts after it.
  const SessionLabelIndex index = testing::index_of(
      {group_of(1'000, {{960'000, kFill}}), group_at(2'000, 999'900, kFill)});
  const LabelRow row = label_or_fail(index, before_entry(), Side::LONG);
  EXPECT_FALSE(row.scan.crossed);
  EXPECT_EQ(row.menu.menu_mae_cent[0], -net_of_move(-40'000));
}

// ---------------------------------------------------------------------------
// The seven-horizon menu.
// ---------------------------------------------------------------------------

TEST(MenuHorizons, TakeTheFirstLawfulMarkAtOrAfterTheDeadlineIncludingAnExactBoundary) {
  // Marks at +1s, +2min exactly (from the fill), and +2min+1s.
  const std::vector<MicroGroup> groups{group_at(1'000, 999'900, kFill),
                                       group_at(2'000, kFill + 100, kFill + 200),
                                       group_at(121'000, kFill + 300, kFill + 400),
                                       group_at(122'000, kFill + 500, kFill + 600)};
  const SessionLabelIndex index = testing::index_of(groups);
  const LabelRow row = label_or_fail(index, before_entry(), Side::LONG);
  // h = 2min lands EXACTLY on the third group's instant, which is at or after
  // the deadline, so that group is the exit.
  EXPECT_EQ(row.menu.menu_exit_ts[0], index.tape().ts_ns[2]);
  EXPECT_EQ(row.menu.menu_net_cent[0], net_of_move(300));
  // Every longer horizon runs past the tape's end and exits at the final mark,
  // exactly as `close` does.
  for (std::size_t horizon = 1; horizon < kHorizonCount; ++horizon) {
    EXPECT_EQ(row.menu.menu_exit_ts[horizon], index.tape().ts_ns[3]) << horizon;
    EXPECT_EQ(row.menu.menu_net_cent[horizon], net_of_move(500));
  }
}

TEST(MenuHorizons, TheCloseHorizonIsTheFinalLawfulMarkOfTheSession) {
  const SessionLabelIndex index = testing::index_of(ladder({100, 200, 300}));
  const LabelRow row = label_or_fail(index, before_entry(), Side::LONG);
  EXPECT_EQ(row.menu.menu_exit_ts[kHorizonCount - 1], index.tape().ts_ns[3]);
  EXPECT_EQ(row.menu.menu_net_cent[kHorizonCount - 1], net_of_move(300));
  EXPECT_EQ(kHorizonMinutes[kHorizonCount - 1], -1);
}

TEST(MenuHorizons, StopHitMeansStrictlyBeforeTheHorizonSoASameGroupCrossingExitsAtTheHorizon) {
  // The crossing IS the 2-minute horizon's own group: the position ends there
  // at the horizon, and `stop_hit` — "stop BEFORE h" — is 0.
  const std::vector<MicroGroup> groups{group_at(1'000, 999'900, kFill),
                                       group_at(121'000, kFill - 2'943, kFill - 2'843),
                                       group_at(122'000, kFill - 10'000, kFill - 9'900)};
  const SessionLabelIndex index = testing::index_of(groups);
  const LabelRow row = label_or_fail(index, before_entry(), Side::LONG);
  ASSERT_TRUE(row.scan.crossed);
  EXPECT_EQ(row.scan.crossing_index, 1);
  EXPECT_EQ(row.menu.stop_hit[0], 0U);
  EXPECT_EQ(row.menu.menu_net_cent[0], net_of_move(-2'943));
  // Every later horizon is strictly after the crossing, so those DO stop out.
  EXPECT_EQ(row.menu.stop_hit[1], 1U);
  EXPECT_EQ(row.menu.menu_net_cent[1], net_of_move(-10'000));
}

TEST(MenuHorizons, TheMaeIsExactAndRangesFromTheFillThroughEachHorizonsOwnExit) {
  const SessionLabelIndex index = testing::index_of(ladder({-400, 500}));
  const LabelRow row = label_or_fail(index, before_entry(), Side::LONG);
  // Marks: entry -100, then -400, then +500. Worst is -400 -> MAE 4,576.
  EXPECT_EQ(row.menu.menu_mae_cent[0], -net_of_move(-400));
  EXPECT_EQ(row.menu.menu_net_cent[0], net_of_move(500));
  EXPECT_GT(row.menu.menu_mae_cent[0], 0);
}

// ---------------------------------------------------------------------------
// The co-primary certificate.
// ---------------------------------------------------------------------------

TEST(Certificate, IsTheEarliestBestPositiveMarkBeforeTheWall) {
  const SessionLabelIndex index = testing::index_of(ladder({100, 500, 500, -2'943, 10'000}));
  const LabelRow row = label_or_fail(index, before_entry(), Side::LONG);
  // The tied maximum is at indices 2 and 3; the earliest wins. The +10,000
  // mark is AFTER the wall and is not a candidate at all.
  EXPECT_EQ(row.certificate_exit_index, 2);
  EXPECT_EQ(row.certificate_net_cent, net_of_move(500));
  EXPECT_EQ(row.certificate_mae_cent, -net_of_move(-100));
}

TEST(Certificate, FallsBackToTheWallFillWhenNoPreWallMarkIsPositive) {
  const SessionLabelIndex index = testing::index_of(ladder({-100, -2'943, -1'000}));
  const LabelRow row = label_or_fail(index, before_entry(), Side::LONG);
  ASSERT_TRUE(row.scan.crossed);
  EXPECT_EQ(row.certificate_exit_index, row.scan.exit_index);
  EXPECT_EQ(row.certificate_net_cent, net_of_move(-1'000));
}

TEST(Certificate, FallsBackToTheFinalLawfulMarkWhenNothingCrossesAndNothingIsPositive) {
  const SessionLabelIndex index = testing::index_of(ladder({-100, -200}));
  const LabelRow row = label_or_fail(index, before_entry(), Side::LONG);
  EXPECT_FALSE(row.scan.crossed);
  EXPECT_EQ(row.certificate_exit_index, 2);
  EXPECT_EQ(row.certificate_net_cent, net_of_move(-200));
}

TEST(Certificate, NeverExitsAtTheEntryGroupEvenWhenTheEntryMarkIsTheMaximum) {
  // The fill instant's own mark (-1,576) is the best mark on the whole tape,
  // and the certificate still exits later: the search starts after the fill.
  const SessionLabelIndex index = testing::index_of(ladder({-5'000, -6'000}));
  const LabelRow row = label_or_fail(index, before_entry(), Side::LONG);
  EXPECT_NE(row.certificate_exit_index, row.entry_index);
  EXPECT_EQ(row.certificate_net_cent, net_of_move(-6'000));
}

// ---------------------------------------------------------------------------
// The label states.
// ---------------------------------------------------------------------------

TEST(LabelStates, EntryUnavailableIsRetainedWithMaskedValues) {
  const SessionLabelIndex index = testing::index_of(ladder({100}));
  const LabelRow row = label_or_fail(index, key_at(2'000 * kMs, Side::LONG), Side::LONG);
  EXPECT_EQ(row.menu.state, LabelState::ENTRY_UNAVAILABLE);
  EXPECT_EQ(row.entry_index, kNoIndex);
  EXPECT_EQ(row.menu.entry_ts_ns, 0);
  for (std::size_t horizon = 0; horizon < kHorizonCount; ++horizon) {
    EXPECT_EQ(row.menu.menu_net_cent[horizon], 0);
    EXPECT_EQ(row.menu.menu_exit_ts[horizon], 0);
    EXPECT_EQ(row.menu.stop_hit[horizon], 0U);
  }
  EXPECT_EQ(row.certificate_net_cent, 0);
  // The row still carries its own key: it is retained, never dropped.
  EXPECT_EQ(row.menu.key.decision_ts_ns, key_at(2'000 * kMs, Side::LONG).decision_ts_ns);
}

TEST(LabelStates, ExitUnavailableIsTheFillOnTheFinalLawfulMark) {
  const SessionLabelIndex index = testing::index_of(ladder({100}));
  const LabelRow row = label_or_fail(index, key_at(1'000 * kMs, Side::LONG), Side::LONG);
  EXPECT_EQ(row.menu.state, LabelState::EXIT_UNAVAILABLE);
  EXPECT_EQ(row.entry_index, 1);
  EXPECT_GT(row.menu.entry_ts_ns, 0);  // the fill happened; the exit cannot
  EXPECT_EQ(row.menu.menu_exit_ts[0], 0);
  EXPECT_EQ(row.certificate_exit_ts_ns, 0);
}

TEST(LabelStates, TheThreeStatesAreSeparateMasksOverTheSameSession) {
  const SessionLabelIndex index = testing::index_of(ladder({100, 200}));
  LabelCensus census;
  census.observe(label_or_fail(index, key_at(500 * kMs, Side::LONG), Side::LONG));
  census.observe(label_or_fail(index, key_at(2'000 * kMs, Side::LONG), Side::LONG));
  census.observe(label_or_fail(index, key_at(3'000 * kMs, Side::LONG), Side::LONG));
  EXPECT_EQ(census.rows, 3);
  EXPECT_EQ(census.per_state[static_cast<std::size_t>(LabelState::OK)], 1);
  EXPECT_EQ(census.per_state[static_cast<std::size_t>(LabelState::EXIT_UNAVAILABLE)], 1);
  EXPECT_EQ(census.per_state[static_cast<std::size_t>(LabelState::ENTRY_UNAVAILABLE)], 1);
}

// ---------------------------------------------------------------------------
// The barrier auxiliary.
// ---------------------------------------------------------------------------

TEST(BarrierAuxiliary, ReachesAllFourRawStatesAndMapsThemToThreeClasses) {
  const LabelRow favorable =
      label_or_fail(testing::index_of(ladder({100, 558})), before_entry(), Side::LONG);
  EXPECT_EQ(favorable.barrier.state, BarrierState::FAVORABLE_FIRST);
  EXPECT_EQ(favorable.barrier.three_class, BarrierClass::FAVORABLE);

  const LabelRow adverse =
      label_or_fail(testing::index_of(ladder({-100, -443})), before_entry(), Side::LONG);
  EXPECT_EQ(adverse.barrier.state, BarrierState::ADVERSE_FIRST);
  EXPECT_EQ(adverse.barrier.three_class, BarrierClass::ADVERSE);

  const LabelRow neither =
      label_or_fail(testing::index_of(ladder({100, -100})), before_entry(), Side::LONG);
  EXPECT_EQ(neither.barrier.state, BarrierState::NEITHER);
  EXPECT_EQ(neither.barrier.three_class, BarrierClass::CENSORED);
  EXPECT_EQ(neither.barrier.first_touch_ts_ns, 0);

  // SAME MILLISECOND, BOTH BARRIERS: one member posts the favorable bid and
  // another the adverse one. Only a two-column envelope can express this.
  const SessionLabelIndex tie = testing::index_of(
      {group_at(1'000, 999'900, kFill),
       group_of(2'000, {{kFill + 558, kFill + 658}, {kFill - 443, kFill - 343}})});
  const LabelRow same_group = label_or_fail(tie, before_entry(), Side::LONG);
  EXPECT_EQ(same_group.barrier.state, BarrierState::SAME_GROUP_ADVERSE);
  EXPECT_EQ(same_group.barrier.three_class, BarrierClass::ADVERSE);
}

TEST(BarrierAuxiliary, IsScannedOverFullRthAndIgnoresTheStopAndTheHorizons) {
  // The wall fires at index 1, but the barrier keeps scanning to the close and
  // still records the favorable touch at index 3.
  const SessionLabelIndex index = testing::index_of(ladder({-2'943, -10'000, 558}));
  const LabelRow row = label_or_fail(index, before_entry(), Side::LONG);
  ASSERT_TRUE(row.scan.crossed);
  EXPECT_EQ(row.barrier.adverse_index, 1);
  EXPECT_EQ(row.barrier.favorable_index, 3);
  EXPECT_EQ(row.barrier.state, BarrierState::ADVERSE_FIRST);
}

// ---------------------------------------------------------------------------
// THE APPENDIX C5 STOP-SHIFT MUTANT.
// ---------------------------------------------------------------------------

TEST(StopShiftMutant, AOneCentShiftMovesNEITHERLedgerBecauseTheNetLatticeIsTenCentsWide) {
  // Measured, not asserted: the reachable nets straddling the wall are -30,006
  // and -29,996, so no wall in (-30,006, -29,996] can separate them and a
  // one-cent shift is provably a no-op. The C5 mutant as literally worded is
  // vacuous; this test PROVES it is, and the next one fires the real thing.
  const SessionLabelIndex index = testing::index_of(ladder({-2'942, -2'943, 5'000}));
  const LabelRow frozen = label_or_fail(index, before_entry(), Side::LONG);
  // The lattice itself, measured on the realised values: `net = frac*10 - 576`
  // puts every reachable net at 4 modulo 10, which is WHY no one-cent wall can
  // separate two neighbouring nets.
  for (std::size_t horizon = 0; horizon < kHorizonCount; ++horizon) {
    EXPECT_EQ(((frozen.menu.menu_net_cent[horizon] % 10) + 10) % 10, 4) << horizon;
  }
  EXPECT_EQ(((frozen.certificate_net_cent % 10) + 10) % 10, 4);
  for (const std::int64_t wall : {std::int64_t{-29'999}, std::int64_t{-30'001}}) {
    const LabelRow shifted = label_or_fail(index, before_entry(), Side::LONG, wall);
    EXPECT_EQ(bytes_of(shifted), bytes_of(frozen)) << "wall " << wall;
    EXPECT_EQ(shifted.scan.crossing_index, frozen.scan.crossing_index);
    EXPECT_EQ(shifted.certificate_net_cent, frozen.certificate_net_cent);
  }
}

TEST(StopShiftMutant, TheSmallestEffectiveShiftMovesTheMenuAndTheCertificateTogether) {
  // THE C5 MUTANT, in its non-vacuous form: -29,996 is the next reachable net,
  // so the wall now catches the -2,942 mark. ONE stop_scan feeds both ledgers,
  // so both move, and both move to the SAME new crossing.
  const SessionLabelIndex index = testing::index_of(ladder({-2'942, -2'943, 5'000}));
  const LabelRow frozen = label_or_fail(index, before_entry(), Side::LONG);
  ASSERT_TRUE(frozen.scan.crossed);
  EXPECT_EQ(frozen.scan.crossing_index, 2);
  EXPECT_EQ(frozen.menu.menu_net_cent[0], net_of_move(5'000));
  EXPECT_EQ(frozen.certificate_net_cent, net_of_move(5'000));

  const LabelRow shifted = label_or_fail(index, before_entry(), Side::LONG, -29'996);
  ASSERT_TRUE(shifted.scan.crossed);
  EXPECT_EQ(shifted.scan.crossing_index, 1);
  // BOTH ledgers moved, to the same new fill (the mark after the new crossing).
  EXPECT_EQ(shifted.menu.menu_net_cent[0], net_of_move(-2'943));
  EXPECT_EQ(shifted.certificate_net_cent, net_of_move(-2'943));
  EXPECT_EQ(shifted.menu.menu_exit_ts[0], shifted.certificate_exit_ts_ns);
  EXPECT_NE(bytes_of(shifted), bytes_of(frozen));
}

TEST(StopShiftMutant, TheCertificateNeverKnowsAWallTheMenuDoesNot) {
  // Structural: across a sweep of walls, the certificate's fallback exit is
  // ALWAYS the scan's own exit index whenever no pre-wall mark is positive.
  const SessionLabelIndex index = testing::index_of(ladder({-100, -2'000, -2'943, -4'000}));
  for (const std::int64_t wall : {std::int64_t{-30'000}, std::int64_t{-29'996},
                                  std::int64_t{-20'006}, std::int64_t{-10'006}}) {
    const LabelRow row = label_or_fail(index, before_entry(), Side::LONG, wall);
    ASSERT_TRUE(row.scan.crossed) << "wall " << wall;
    EXPECT_EQ(row.certificate_exit_index, row.scan.exit_index) << "wall " << wall;
    EXPECT_EQ(row.menu.menu_net_cent[0], row.scan.exit_net_cent) << "wall " << wall;
  }
}

// ---------------------------------------------------------------------------
// Sides, determinism and the linear-reference differential.
// ---------------------------------------------------------------------------

TEST(LabelSides, AShortOnTheMirroredTapeIsTheExactMirrorOfTheLong) {
  const std::vector<MicroGroup> groups = ladder({-100, 500, -2'943, 2'000});
  const SessionLabelIndex longs = testing::index_of(groups);
  const SessionLabelIndex shorts = testing::index_of(mirrored(groups));
  const LabelRow left = label_or_fail(longs, before_entry(Side::LONG), Side::LONG);
  const LabelRow right = label_or_fail(shorts, before_entry(Side::SHORT), Side::SHORT);
  EXPECT_EQ(left.entry_u6, right.entry_u6);
  EXPECT_EQ(left.certificate_net_cent, right.certificate_net_cent);
  EXPECT_EQ(left.certificate_mae_cent, right.certificate_mae_cent);
  EXPECT_EQ(left.barrier.state, right.barrier.state);
  for (std::size_t horizon = 0; horizon < kHorizonCount; ++horizon) {
    EXPECT_EQ(left.menu.menu_net_cent[horizon], right.menu.menu_net_cent[horizon]) << horizon;
    EXPECT_EQ(left.menu.menu_mae_cent[horizon], right.menu.menu_mae_cent[horizon]) << horizon;
    EXPECT_EQ(left.menu.stop_hit[horizon], right.menu.stop_hit[horizon]) << horizon;
  }
}

TEST(LabelSides, TheKeysSideMustBeTheSideBeingLabelled) {
  const SessionLabelIndex index = testing::index_of(ladder({100}));
  EXPECT_FALSE(label_action(index, key_at(500 * kMs, Side::LONG), Side::SHORT).has_value());
}

TEST(LabelDeterminism, TwoRunsOverTheSameTapeProduceIdenticalBytes) {
  const std::vector<MicroGroup> groups = ladder({-100, 500, -2'943, 2'000});
  const SessionLabelIndex index = testing::index_of(groups);
  std::vector<ActionRow> actions;
  // The last two decisions are deliberately unlabellable — one fills on the
  // final lawful mark (EXIT_UNAVAILABLE) and one has no mark after it at all
  // (ENTRY_UNAVAILABLE). "Every row is predicted and retained", so the session
  // must still return one row per action.
  for (const std::int64_t ms : {500, 1'500, 2'500, 3'500, 4'500, 6'000}) {
    ActionRow row;
    row.key = key_at(ms * kMs, Side::LONG, ms);
    actions.push_back(row);
    row.key = key_at(ms * kMs, Side::SHORT, ms);
    actions.push_back(row);
  }
  const Expected<std::vector<LabelRow>, Refusal> first = label_session(index, actions);
  const Expected<std::vector<LabelRow>, Refusal> second = label_session(index, actions);
  ASSERT_TRUE(first.has_value());
  ASSERT_TRUE(second.has_value());
  EXPECT_EQ(render_label_rows(first.value()), render_label_rows(second.value()));
  EXPECT_EQ(first.value().size(), actions.size());
}

TEST(LinearReferenceDifferential, TheAcceleratedKernelAgreesByteForByteOnAPseudoRandomTape) {
  // The production kernel answers with segment trees and closed-form price
  // gates; the reference walks every mark. They must be the same bytes.
  Lcg lcg(2026081007);
  std::vector<MicroGroup> groups;
  std::int64_t ms = 1'000;
  std::int64_t bid = kFill;
  for (int step = 0; step < 240; ++step) {
    ms += lcg.between(1, 900);
    bid += lcg.between(-400, 400);
    if (bid < 900'000) {
      bid = 900'000;
    }
    if (lcg.between(0, 9) == 0) {
      // an equal-ms group with two members, so the envelope is exercised too
      groups.push_back(group_of(ms, {{bid, bid + 100}, {bid - 60, bid + 40}}));
    } else {
      groups.push_back(group_at(ms, bid, bid + 100));
    }
  }
  const ExecutionTape tape = testing::tape_of(groups);
  const SessionLabelIndex index = SessionLabelIndex::build(tape);
  ASSERT_GT(index.tape().size(), 200);

  int compared = 0;
  int crossings = 0;
  for (std::int64_t step = 0; step < 60; ++step) {
    const std::int64_t offset_ns = 500 * kMs + step * 3'000 * kMs;
    for (const Side side : {Side::LONG, Side::SHORT}) {
      const ActionKey key = key_at(offset_ns, side, step);
      const LabelRow produced = label_or_fail(index, key, side);
      const LabelRow reference = linear_reference_label(tape, key, side);
      ASSERT_EQ(bytes_of(produced), bytes_of(reference))
          << "offset " << offset_ns << " side " << qr::replay::side_name(side);
      compared += 1;
      crossings += produced.scan.crossed ? 1 : 0;
    }
  }
  EXPECT_EQ(compared, 120);
  EXPECT_GT(crossings, 0) << "the differential must exercise the wall, not only quiet tapes";
}

TEST(LinearReferenceDifferential, AgreesUnderShiftedWallsToo) {
  Lcg lcg(2026081011);
  std::vector<MicroGroup> groups;
  std::int64_t ms = 1'000;
  std::int64_t bid = kFill;
  for (int step = 0; step < 160; ++step) {
    ms += lcg.between(1, 700);
    bid += lcg.between(-500, 480);
    if (bid < 900'000) {
      bid = 900'000;
    }
    groups.push_back(group_at(ms, bid, bid + 100));
  }
  const ExecutionTape tape = testing::tape_of(groups);
  const SessionLabelIndex index = SessionLabelIndex::build(tape);
  for (const std::int64_t wall : {std::int64_t{-30'000}, std::int64_t{-29'996},
                                  std::int64_t{-10'006}, std::int64_t{-5'006}}) {
    for (const Side side : {Side::LONG, Side::SHORT}) {
      const ActionKey key = key_at(500 * kMs, side, 3);
      ASSERT_EQ(bytes_of(label_or_fail(index, key, side, wall)),
                bytes_of(linear_reference_label(tape, key, side, wall)))
          << "wall " << wall;
    }
  }
}

TEST(LabelCensusRows, CountsEveryStateHorizonAndBarrierIncludingZeros) {
  const SessionLabelIndex index = testing::index_of(ladder({-2'943, -20'000}));
  LabelCensus census;
  census.observe(label_or_fail(index, before_entry(), Side::LONG));
  const std::string tsv = census.to_tsv("micro");
  EXPECT_NE(tsv.find("state_OK\t1"), std::string::npos);
  EXPECT_NE(tsv.find("stop_hit_h2\t1"), std::string::npos);
  EXPECT_NE(tsv.find("stop_hit_h-1\t1"), std::string::npos);
  EXPECT_NE(tsv.find("barrier_FAVORABLE_FIRST\t0"), std::string::npos);
  EXPECT_NE(tsv.find("gap_through_rows\t1"), std::string::npos);
  EXPECT_EQ(census.certificate_positive_rows, 0);
}

}  // namespace
}  // namespace qr::labels
