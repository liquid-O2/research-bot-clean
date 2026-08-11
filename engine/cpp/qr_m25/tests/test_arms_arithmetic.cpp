// qr_m25/tests/test_arms_arithmetic.cpp — the decomposition panel against HAND
// ARITHMETIC on a three-session synthetic (FINAL_PLAN section 8 item 2).
//
// Every expected number below is computed by hand in the comment above it from
// the fixture's own nets and the kernel's own rules (one position, a new entry
// needs decision_ts > prior exit_ts, zero days stay in the denominator, the
// causal daily-loss-limit halts at -$900 cumulative). If the code and the
// arithmetic ever disagree, one of them is wrong and this test says which.
#include <gtest/gtest.h>

#include <vector>

#include "m25_test_support.hpp"
#include "qr_m25/arms.hpp"
#include "qr_replay/scorecard.hpp"

namespace {

using qr::m25::Arm;
using qr::m25::kDailyLossLimitCent;
using qr::m25::run_arm;
using qr::m25::SessionTape;
using qr::m25::test::Spec;

/// SESSION A (ordinal 125). Spacing 60s, hold 60s: a trade entered at clock c
/// exits at (c*60 + 61)s, so it occupies exactly the next clock.
///   clock 0: LONG -2000  SHORT +1000
///   clock 1: LONG +9000  SHORT -9000
///   clock 2: LONG +4000  SHORT -5000
///   clock 3: LONG  -100  SHORT  +900
SessionTape session_a() {
  const std::vector<Spec> specs = {
      Spec{0, true, -2000, 60, true, false, 0},  Spec{0, false, 1000, 60, true, false, 0},
      Spec{1, true, 9000, 60, true, false, 0},   Spec{1, false, -9000, 60, true, false, 0},
      Spec{2, true, 4000, 60, true, false, 0},   Spec{2, false, -5000, 60, true, false, 0},
      Spec{3, true, -100, 60, true, false, 0},   Spec{3, false, 900, 60, true, false, 0},
  };
  return qr::m25::test::make_tape(125, 2022, specs);
}

/// SESSION B (ordinal 126). One clock, BOTH labels unavailable: a zero day that
/// stays in the denominator and can never trade.
SessionTape session_b() {
  const std::vector<Spec> specs = {
      Spec{0, true, 5000, 60, false, false, 0},
      Spec{0, false, -5000, 60, false, false, 0},
  };
  return qr::m25::test::make_tape(126, 2022, specs);
}

/// SESSION C (ordinal 127). Seven clocks; every EVEN clock is a stopped LONG at
/// -30,000c with a 25c gap-through, every odd clock is a -10c pair.
SessionTape session_c() {
  std::vector<Spec> specs;
  for (std::int64_t c = 0; c < 7; ++c) {
    if (c % 2 == 0) {
      specs.push_back(Spec{c, true, -30000, 60, true, true, 25});
      specs.push_back(Spec{c, false, 100, 60, true, false, 0});
    } else {
      specs.push_back(Spec{c, true, -10, 60, true, false, 0});
      specs.push_back(Spec{c, false, -10, 60, true, false, 0});
    }
  }
  return qr::m25::test::make_tape(127, 2022, specs);
}

qr::replay::DailyLedger run(Arm arm, SessionTape tape, std::size_t horizon = 2) {
  auto ledger = run_arm(arm, &tape, horizon, 0, kDailyLossLimitCent);
  EXPECT_TRUE(ledger.has_value()) << (ledger.has_value() ? "" : ledger.error().message());
  return ledger.value();
}

std::int64_t census(const qr::replay::DailyLedger& ledger, qr::replay::ClockOutcome outcome) {
  return ledger.clock_census[static_cast<std::size_t>(outcome)];
}

}  // namespace

TEST(ArmsArithmetic, ForcedLongTakesTheLongSideOfEveryFreeClock) {
  // clock 0 LONG -2000 (occupies clock 1); clock 2 LONG +4000 (occupies clock 3).
  // -2000 + 4000 = +2000 over 2 trades.
  const qr::replay::DailyLedger ledger = run(Arm::FORCED_LONG, session_a());
  EXPECT_EQ(ledger.net_cent, 2000);
  EXPECT_EQ(ledger.trade_count(), 2);
  EXPECT_EQ(census(ledger, qr::replay::ClockOutcome::OCCUPIED), 2);
  for (const auto& trade : ledger.trades) {
    EXPECT_EQ(trade.key.side, qr::replay::Side::LONG);
  }
}

TEST(ArmsArithmetic, ForcedShortTakesTheShortSideOfEveryFreeClock) {
  // clock 0 SHORT +1000 (occupies clock 1); clock 2 SHORT -5000 (occupies 3).
  // 1000 - 5000 = -4000 over 2 trades.
  const qr::replay::DailyLedger ledger = run(Arm::FORCED_SHORT, session_a());
  EXPECT_EQ(ledger.net_cent, -4000);
  EXPECT_EQ(ledger.trade_count(), 2);
  for (const auto& trade : ledger.trades) {
    EXPECT_EQ(trade.key.side, qr::replay::Side::SHORT);
  }
}

TEST(ArmsArithmetic, TheSeededCoinPicksOneOfTheFourLawfulOutcomes) {
  // The coin trades the same two clocks (0 and 2) as the forced arms; only the
  // SIDE is drawn. The four lawful nets are +1000+4000, +1000-5000, -2000+4000,
  // -2000-5000, and the kernel must consume exactly one draw per selection.
  const qr::replay::DailyLedger ledger = run(Arm::SEEDED_COIN, session_a());
  EXPECT_EQ(ledger.trade_count(), 2);
  EXPECT_EQ(ledger.coin_draws, 2);
  const std::int64_t net = ledger.net_cent;
  EXPECT_TRUE(net == 5000 || net == -4000 || net == 2000 || net == -7000) << net;

  // And it is REPRODUCIBLE: the same session replays to the same coin.
  const qr::replay::DailyLedger again = run(Arm::SEEDED_COIN, session_a());
  EXPECT_EQ(again.net_cent, net);
}

TEST(ArmsArithmetic, PerfectSideOnlyTradesEveryFreeClockOnTheBetterSide) {
  // clock 0 best side is SHORT +1000 (occupies clock 1); clock 2 best side is
  // LONG +4000 (occupies clock 3). 1000 + 4000 = +5000 over 2 trades.
  const qr::replay::DailyLedger ledger = run(Arm::PERFECT_SIDE_ONLY, session_a());
  EXPECT_EQ(ledger.net_cent, 5000);
  EXPECT_EQ(ledger.trade_count(), 2);
  EXPECT_EQ(ledger.trades[0].key.side, qr::replay::Side::SHORT);
  EXPECT_EQ(ledger.trades[1].key.side, qr::replay::Side::LONG);
}

TEST(ArmsArithmetic, PerfectTakeSkipOnAControlSideOnlyTakesItsOwnWinners) {
  // LONG side, winners only: clock 1 (+9000) and clock 2 (+4000). Entering
  // clock 1 occupies clock 2, so the arm takes 9000 on one trade.
  const qr::replay::DailyLedger long_side = run(Arm::PERFECT_TAKESKIP_LONG_SIDE, session_a());
  EXPECT_EQ(long_side.net_cent, 9000);
  EXPECT_EQ(long_side.trade_count(), 1);

  // SHORT side, winners only: clock 0 (+1000) and clock 3 (+900); clock 0
  // occupies clock 1, clock 2 has no member. 1000 + 900 = 1900 over 2 trades.
  const qr::replay::DailyLedger short_side = run(Arm::PERFECT_TAKESKIP_SHORT_SIDE, session_a());
  EXPECT_EQ(short_side.net_cent, 1900);
  EXPECT_EQ(short_side.trade_count(), 2);
}

TEST(ArmsArithmetic, GreedyPerfectSideAndTakeSkipIsBeatenByTheOnePositionOptimum) {
  // GREEDY: clock 0 SHORT +1000 -> clock 1 (+9000!) is occupied -> clock 2 LONG
  // +4000 -> clock 3 occupied. 1000 + 4000 = 5000.
  const qr::replay::DailyLedger greedy = run(Arm::PERFECT_SIDE_TAKESKIP_GREEDY, session_a());
  EXPECT_EQ(greedy.net_cent, 5000);
  EXPECT_EQ(greedy.trade_count(), 2);

  // DP: skip clock 0, take LONG +9000 at clock 1 (occupying clock 2), then
  // SHORT +900 at clock 3. 9000 + 900 = 9900 — strictly more than greedy, which
  // is the whole reason the envelope is a DP and not a rule of thumb.
  const qr::replay::DailyLedger optimum = run(Arm::PERFECT_SIDE_TAKESKIP_DP, session_a());
  EXPECT_EQ(optimum.net_cent, 9900);
  EXPECT_EQ(optimum.trade_count(), 2);
  EXPECT_GT(optimum.net_cent, greedy.net_cent);
  EXPECT_EQ(optimum.trades[0].key.side, qr::replay::Side::LONG);
  EXPECT_EQ(optimum.trades[0].net_cent, 9000);
  EXPECT_EQ(optimum.trades[1].net_cent, 900);
}

TEST(ArmsArithmetic, TheOptimumIsNeverBeatenByAnyOtherArm) {
  // The envelope is an envelope: no arm through this kernel can out-earn the
  // one-position optimum at the same horizon.
  const qr::replay::DailyLedger optimum = run(Arm::PERFECT_SIDE_TAKESKIP_DP, session_a());
  for (std::size_t a = 0; a < qr::m25::kArmCount; ++a) {
    const qr::replay::DailyLedger other = run(static_cast<Arm>(a), session_a());
    EXPECT_LE(other.net_cent, optimum.net_cent) << qr::m25::arm_name(static_cast<Arm>(a));
  }
}

TEST(ArmsArithmetic, AZeroDayStaysInTheDenominatorAndTradesNothing) {
  for (std::size_t a = 0; a < qr::m25::kArmCount; ++a) {
    const qr::replay::DailyLedger ledger = run(static_cast<Arm>(a), session_b());
    EXPECT_EQ(ledger.net_cent, 0) << qr::m25::arm_name(static_cast<Arm>(a));
    EXPECT_EQ(ledger.trade_count(), 0);
    EXPECT_TRUE(ledger.zero_trade_session());
    EXPECT_EQ(ledger.clock_count, 1);
  }
  // The forced arms SELECT the unavailable row and are typed for it; they never
  // silently drop it.
  const qr::replay::DailyLedger forced = run(Arm::FORCED_LONG, session_b());
  EXPECT_EQ(census(forced, qr::replay::ClockOutcome::NO_FRESH_FILL), 1);
}

TEST(ArmsArithmetic, TheCausalDailyLossLimitHaltsTheSessionAtNineHundredDollars) {
  // Even clocks are -30,000c LONGs and each occupies the next clock, so
  // forced-LONG enters clocks 0, 2 and 4: cumulative -30000, -60000, -90000.
  // -90000 <= -90000 trips the limit, so clocks 5 and 6 are HALTED and the day
  // ends at -90000 over exactly 3 trades, each of them a gap-through breach.
  const qr::replay::DailyLedger ledger = run(Arm::FORCED_LONG, session_c());
  EXPECT_EQ(ledger.net_cent, -90000);
  EXPECT_EQ(ledger.trade_count(), 3);
  EXPECT_TRUE(ledger.halted_daily_loss);
  EXPECT_EQ(census(ledger, qr::replay::ClockOutcome::HALTED_DAILY_LOSS), 2);
  std::int64_t breaches = 0;
  for (const auto& trade : ledger.trades) {
    if (trade.stop_hit && trade.gap_through_cent > 0) {
      ++breaches;
    }
  }
  EXPECT_EQ(breaches, 3);

  // The nonbinding -$600 panel halts EARLIER: -30000, -60000 <= -60000 stops it
  // after two trades.
  SessionTape tape = session_c();
  const auto panel = run_arm(Arm::FORCED_LONG, &tape, 2, 0, qr::m25::kDailyLossLimitPanelCent);
  ASSERT_TRUE(panel.has_value());
  EXPECT_EQ(panel.value().trade_count(), 2);
  EXPECT_EQ(panel.value().net_cent, -60000);
}

TEST(ArmsArithmetic, TheThreeSessionScorecardMatchesHandArithmetic) {
  // forced-LONG over the three sessions: +2000, 0, -90000.
  // Equity path E0=0 -> 2000 -> 2000 -> -88000; running max includes E0, so the
  // maximum drawdown is 2000 - (-88000) = 90000c = $900.
  std::vector<qr::replay::DailyLedger> ledgers;
  ledgers.push_back(run(Arm::FORCED_LONG, session_a()));
  ledgers.push_back(run(Arm::FORCED_LONG, session_b()));
  ledgers.push_back(run(Arm::FORCED_LONG, session_c()));
  const auto card = qr::replay::score(ledgers);
  ASSERT_TRUE(card.has_value()) << (card.has_value() ? "" : card.error().message());
  EXPECT_EQ(card.value().session_count, 3);
  EXPECT_EQ(card.value().total_net_cent, -88000);
  EXPECT_EQ(card.value().mdd_cent, 90000);
  EXPECT_EQ(card.value().zero_trade_session_count, 1);
  EXPECT_EQ(card.value().trade_count, 5);
  EXPECT_EQ(card.value().breach_count, 3);
}

TEST(ArmsArithmetic, EveryArmReplaysTheHorizonItWasAskedForAndNothingElse) {
  // The nets now differ by horizon (+1,000c per step), so a trade's net NAMES
  // the horizon that produced it. The kernel refuses a label that did not charge
  // 576c once, and the arms add nothing: a trade's net is its own menu net at
  // the replayed horizon, to the cent.
  const std::vector<Spec> specs = {
      Spec{0, true, -2000, 60, true, false, 0, 1000},
      Spec{0, false, 1000, 60, true, false, 0, 1000},
      Spec{2, true, 4000, 60, true, false, 0, 1000},
      Spec{2, false, -5000, 60, true, false, 0, 1000},
  };
  for (std::size_t horizon = 0; horizon < qr::replay::kHorizonCount; ++horizon) {
    for (std::size_t a = 0; a < qr::m25::kArmCount; ++a) {
      SessionTape tape = qr::m25::test::make_tape(125, 2022, specs);
      const auto ledger =
          run_arm(static_cast<Arm>(a), &tape, horizon, 0, kDailyLossLimitCent);
      ASSERT_TRUE(ledger.has_value());
      for (const auto& trade : ledger.value().trades) {
        bool matched = false;
        for (const auto& row : tape.rows) {
          if (row.key == trade.key) {
            EXPECT_EQ(trade.net_cent, row.label.menu_net_cent[horizon])
                << qr::m25::arm_name(static_cast<Arm>(a)) << " at horizon " << horizon;
            matched = true;
          }
        }
        EXPECT_TRUE(matched);
      }
    }
  }
}
