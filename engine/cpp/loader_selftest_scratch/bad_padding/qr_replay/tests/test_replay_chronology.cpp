// qr_replay/tests/test_replay_chronology.cpp — the hand-computed three-session
// chronology fixture.
//
// Everything asserted here was computed by hand FIRST and is written out with
// its arithmetic; the kernel either reproduces these literals or it is wrong.
// The fixture exercises, in one tape: occupancy blocking at and inside a prior
// exit, a typed NO_FRESH_FILL on a selected-but-unavailable label, an exact-tie
// abstention, a clock with no legal row, a zero-trade session that stays in the
// denominator, and an MDD whose peak is E0 = 0 before any gain.
//
// THE TAPE (horizon under test = index 2, the 15-minute menu entry; T(m) is m
// minutes after an arbitrary session base, and fills land 1 second after their
// own decision):
//
//   session 125 (year 2022)
//     T(0)   ord 1  LONG  pred 10.0  net +25,000c  mae   1,200c  exit T(15)+1s
//            ord 1  SHORT pred  2.0  net  -3,000c
//            -> LONG is the unique highest admitted row: ENTER, +25,000c.
//     T(10)  ord 2  LONG  pred  8.0                  -> OCCUPIED (10 < 15:01)
//     T(15)  ord 3  LONG  pred  8.0                  -> OCCUPIED (15:00 <= 15:01;
//            "a new entry requires decision_ts > prior exit_ts", so the equal
//            instant is still occupied)
//     T(16)  ord 4  LONG  pred  5.0  label ENTRY_UNAVAILABLE
//            ord 4  SHORT pred  3.0  net  +9,999c
//            -> the unique highest row is the LONG one; its label is not OK, so
//               the clock is NO_FRESH_FILL and NOTHING trades. The +9,999c of
//               the second-best row must never appear: selection does not fall
//               through to a runner-up, because that would let an OUTCOME
//               (label availability) choose the entry.
//     T(20)  ord 5  LONG  pred  7.0  net -30,500c  mae 30,500c  stop  gap 500c
//                                    exit T(23)+1s
//            -> ENTER, stopped out at the causal $300 wall and the fill landed
//               500c PAST it: the breach panel's definition is `stop_hit AND
//               gap_through_cent > 0`, so this is the one breach (a stopped
//               trade whose fill came back to the wall would not be one, however
//               large its MAE).
//     session net = +25,000 - 30,500 = -5,500c = -$55.00; 2 trades; 5 clocks;
//     census ENTERED 2 / OCCUPIED 2 / NO_FRESH_FILL 1.
//
//   session 126 (year 2022) — the zero-trade day that stays in the denominator
//     T(0)   ord 1  LONG  pred 4.0 and SHORT pred 4.0 -> ABSTAIN_TIE (exact tie)
//     T(5)   ord 2  both rows illegal                 -> NO_LEGAL_ROW
//     session net = 0c; 0 trades; 2 clocks.
//
//   session 127 (year 2023)
//     T(0)   ord 1  LONG  pred 1.0  net +10,000c  mae   800c  exit T(15)+1s
//     T(30)  ord 2  SHORT pred 9.0  net  +5,000c  mae   400c  exit T(45)+1s
//     session net = +15,000c = $150.00; 2 trades; 2 clocks.
//
// THE SCORECARD (three sessions, in this order):
//   session nets (cents)  = [-5,500, 0, +15,000]
//   total                 = +9,500c = $95.00 over THREE sessions (the zero-trade
//                           day is in the denominator) -> mean = $31.666...
//   trades/session        = 4 / 3 = 1.333...
//   equity  E0=0, E1=-5,500, E2=-5,500, E3=+9,500
//   running max INCLUDING E0: 0, 0, 0, 9,500
//   drawdowns:               0, 5,500, 5,500, 0      -> MDD = 5,500c = $55.00
//     (drop E0 from the running maximum and the maxima become -5,500, -5,500,
//      9,500, every drawdown is 0 and the MDD reads $0.00 — this fixture is
//      exactly the "peak precedes any gain" case the C6 initial-zero-removal
//      mutant has to survive, and it cannot.)
//   min-year: 2022 = (-5,500 + 0)/2 = -2,750c = -$27.50; 2023 = +$150.00 -> 2022.
//   breach panel: one stop fired AND gapped through (500c past the wall) -> 1;
//                 max MAE = 30,500c, which is the SEPARATE MAE panel.
//   leave-top-10-out: undefined at three sessions.
#include <gtest/gtest.h>

#include <vector>

#include "qr_replay/policy_gate.hpp"
#include "qr_replay/replay.hpp"
#include "qr_replay/scorecard.hpp"
#include "replay_test_support.hpp"

namespace qr::replay {
namespace {

using test::ActionSpec;
using test::kMinuteNs;
using test::kSecondNs;
using test::make_tape;

constexpr std::size_t kH = 2;  // the 15-minute menu entry

std::int64_t T(std::int64_t minutes) { return minutes * kMinuteNs; }

std::vector<ScoredAction> session_125() {
  return make_tape(125,
                   {
                       {1, T(0), Side::LONG, 10.0, 0.10, true, LabelState::OK, kSecondNs,
                        15 * kMinuteNs, 25000, 1200, false},
                       {1, T(0), Side::SHORT, 2.0, 0.10, true, LabelState::OK, kSecondNs,
                        15 * kMinuteNs, -3000, 900, false},
                       {2, T(10), Side::LONG, 8.0, 0.10, true, LabelState::OK, kSecondNs,
                        15 * kMinuteNs, 40000, 100, false},
                       {3, T(15), Side::LONG, 8.0, 0.10, true, LabelState::OK, kSecondNs,
                        15 * kMinuteNs, 40000, 100, false},
                       {4, T(16), Side::LONG, 5.0, 0.10, true, LabelState::ENTRY_UNAVAILABLE},
                       {4, T(16), Side::SHORT, 3.0, 0.10, true, LabelState::OK, kSecondNs,
                        15 * kMinuteNs, 9999, 100, false},
                       {5, T(20), Side::LONG, 7.0, 0.10, true, LabelState::OK, kSecondNs,
                        3 * kMinuteNs, -30500, 30500, true, 500},
                   },
                   kH);
}

std::vector<ScoredAction> session_126() {
  return make_tape(126,
                   {
                       {1, T(0), Side::LONG, 4.0, 0.10, true, LabelState::OK, kSecondNs,
                        15 * kMinuteNs, 11111, 100, false},
                       {1, T(0), Side::SHORT, 4.0, 0.10, true, LabelState::OK, kSecondNs,
                        15 * kMinuteNs, 22222, 100, false},
                       {2, T(5), Side::LONG, 6.0, 0.10, false, LabelState::OK, kSecondNs,
                        15 * kMinuteNs, 33333, 100, false},
                       {2, T(5), Side::SHORT, 5.0, 0.10, false, LabelState::OK, kSecondNs,
                        15 * kMinuteNs, 44444, 100, false},
                   },
                   kH);
}

std::vector<ScoredAction> session_127() {
  return make_tape(127,
                   {
                       {1, T(0), Side::LONG, 1.0, 0.10, true, LabelState::OK, kSecondNs,
                        15 * kMinuteNs, 10000, 800, false},
                       {2, T(30), Side::SHORT, 9.0, 0.10, true, LabelState::OK, kSecondNs,
                        15 * kMinuteNs, 5000, 400, false},
                   },
                   kH);
}

std::int64_t census(const DailyLedger& ledger, ClockOutcome outcome) {
  return ledger.clock_census[static_cast<std::size_t>(outcome)];
}

DailyLedger replay_or_die(const SessionRef& session, const std::vector<ScoredAction>& tape) {
  AdmitAllGate gate;
  ReplayPolicy policy(kH);
  const Expected<DailyLedger, Refusal> result = replay(session, tape, gate, policy);
  EXPECT_TRUE(result.has_value()) << (result.has_value() ? "" : result.error().message());
  return result.has_value() ? result.value() : DailyLedger{};
}

TEST(HandChronology, SessionOneTwentyFiveMatchesTheHandComputedLedger) {
  const DailyLedger ledger = replay_or_die({125, 2022}, session_125());

  // Two trades: +25,000c then -30,500c (a stop that gapped 500c through).
  ASSERT_EQ(ledger.trade_count(), 2);
  EXPECT_EQ(ledger.trades[0].net_cent, 25000);
  EXPECT_EQ(ledger.trades[0].key.side, Side::LONG);
  EXPECT_EQ(ledger.trades[0].entry_ts_ns, T(0) + kSecondNs);
  EXPECT_EQ(ledger.trades[0].exit_ts_ns, T(15) + kSecondNs);
  EXPECT_EQ(ledger.trades[1].net_cent, -30500);
  EXPECT_EQ(ledger.trades[1].mae_cent, 30500);
  EXPECT_TRUE(ledger.trades[1].stop_hit);
  EXPECT_EQ(ledger.trades[1].gap_through_cent, 500);
  EXPECT_EQ(ledger.trades[1].exit_ts_ns, T(23) + kSecondNs);

  // -5,500 cents = -$55.00 for the session.
  EXPECT_EQ(ledger.net_cent, -5500);

  // Five clocks, and every one of them typed.
  EXPECT_EQ(ledger.clock_count, 5);
  EXPECT_EQ(census(ledger, ClockOutcome::ENTERED), 2);
  EXPECT_EQ(census(ledger, ClockOutcome::OCCUPIED), 2);
  EXPECT_EQ(census(ledger, ClockOutcome::NO_FRESH_FILL), 1);
}

TEST(HandChronology, AnOccupiedClockAtTheExactPriorExitInstantStillCannotEnter) {
  const DailyLedger ledger = replay_or_die({125, 2022}, session_125());
  // T(15) is EARLIER than the prior exit T(15)+1s and T(10) is inside the
  // position; both are OCCUPIED, and neither produced a trade.
  EXPECT_EQ(census(ledger, ClockOutcome::OCCUPIED), 2);
  ASSERT_EQ(ledger.trade_count(), 2);
  EXPECT_NE(ledger.trades[1].key.decision_ordinal, 2);
  EXPECT_NE(ledger.trades[1].key.decision_ordinal, 3);
}

TEST(HandChronology, SelectionDoesNotFallThroughToARunnerUpWhenTheTopLabelIsUnavailable) {
  const DailyLedger ledger = replay_or_die({125, 2022}, session_125());
  EXPECT_EQ(census(ledger, ClockOutcome::NO_FRESH_FILL), 1);
  for (const TradeRecord& trade : ledger.trades) {
    // The runner-up at T(16) carried +9,999c; it must appear nowhere.
    EXPECT_NE(trade.net_cent, 9999);
    EXPECT_NE(trade.key.decision_ordinal, 4);
  }
}

TEST(HandChronology, TheZeroTradeSessionIsATypedZeroNotAnAbsence) {
  const DailyLedger ledger = replay_or_die({126, 2022}, session_126());
  EXPECT_EQ(ledger.trade_count(), 0);
  EXPECT_EQ(ledger.net_cent, 0);
  EXPECT_TRUE(ledger.zero_trade_session());
  EXPECT_EQ(ledger.clock_count, 2);
  EXPECT_EQ(census(ledger, ClockOutcome::ABSTAIN_TIE), 1);
  EXPECT_EQ(census(ledger, ClockOutcome::NO_LEGAL_ROW), 1);
  // Four rows in the tape; the two at T(5) are not legal_enter, so only the two
  // tied rows at T(0) count as legal.
  EXPECT_EQ(ledger.row_count, 4);
  EXPECT_EQ(ledger.legal_row_count, 2);
}

TEST(HandChronology, EveryClockIsAccountedForInTheCensus) {
  const std::vector<std::pair<SessionRef, std::vector<ScoredAction>>> sessions = {
      {{125, 2022}, session_125()}, {{126, 2022}, session_126()}, {{127, 2023}, session_127()}};
  for (const auto& entry : sessions) {
    const DailyLedger ledger = replay_or_die(entry.first, entry.second);
    std::int64_t total = 0;
    for (const std::int64_t count : ledger.clock_census) {
      total += count;
    }
    EXPECT_EQ(total, ledger.clock_count) << "session " << entry.first.session_ordinal;
  }
}

TEST(HandChronology, TheThreeSessionScorecardMatchesTheHandComputedLiterals) {
  const std::vector<DailyLedger> ledgers = {replay_or_die({125, 2022}, session_125()),
                                            replay_or_die({126, 2022}, session_126()),
                                            replay_or_die({127, 2023}, session_127())};
  const Expected<Scorecard, Refusal> scored = score(ledgers);
  ASSERT_TRUE(scored.has_value()) << (scored.has_value() ? "" : scored.error().message());
  const Scorecard& card = scored.value();

  EXPECT_EQ(card.session_count, 3);
  EXPECT_EQ(card.zero_trade_session_count, 1);
  EXPECT_EQ(card.trade_count, 4);
  ASSERT_EQ(card.session_net_cent.size(), 3u);
  EXPECT_EQ(card.session_net_cent[0], -5500);
  EXPECT_EQ(card.session_net_cent[1], 0);
  EXPECT_EQ(card.session_net_cent[2], 15000);

  EXPECT_EQ(card.total_net_cent, 9500);
  EXPECT_DOUBLE_EQ(card.mean_net_dollars, 95.0 / 3.0);
  EXPECT_DOUBLE_EQ(card.trades_per_session, 4.0 / 3.0);

  // MDD = 5,500 cents = $55.00, and it exists ONLY because E0 = 0 is in the
  // running maximum.
  EXPECT_EQ(card.mdd_cent, 5500);

  EXPECT_EQ(card.min_year, 2022);
  EXPECT_DOUBLE_EQ(card.min_year_mean_net_dollars, -27.5);
  EXPECT_FALSE(card.mean_net_dollars_leave_top_10_out.has_value());

  EXPECT_EQ(card.breach_count, 1);
  EXPECT_EQ(card.max_mae_cent, 30500);

  // MAE panel, nearest rank over the four trades' MAEs sorted 400, 800, 1,200,
  // 30,500: p50 -> ceil(0.50*4) = 2 -> 800c; p90 -> ceil(0.90*4) = 4 -> 30,500c;
  // p95 and p99 likewise land on index 4.
  EXPECT_EQ(card.mae_p50_cent, 800);
  EXPECT_EQ(card.mae_p90_cent, 30500);
  EXPECT_EQ(card.mae_p95_cent, 30500);
  EXPECT_EQ(card.mae_p99_cent, 30500);
}

}  // namespace
}  // namespace qr::replay
