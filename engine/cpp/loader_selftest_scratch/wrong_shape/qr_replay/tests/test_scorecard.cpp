// qr_replay/tests/test_scorecard.cpp — the scorecard aggregates, with the
// zero-inclusive MDD (C6 mutant "initial-zero removal") at the centre.
#include <gtest/gtest.h>

#include <cstdint>
#include <vector>

#include "qr_replay/scorecard.hpp"

namespace qr::replay {
namespace {

/// A ledger built straight from its trade nets: the scorecard's input is the
/// per-session net vector, and these fixtures are about the aggregation, not
/// about the chronology that produced it.
DailyLedger make_ledger(std::int64_t session_ordinal, std::int32_t year,
                        const std::vector<std::int64_t>& trade_nets,
                        const std::vector<std::int64_t>& trade_maes = {}) {
  DailyLedger ledger;
  ledger.session = {session_ordinal, year};
  for (std::size_t i = 0; i < trade_nets.size(); ++i) {
    TradeRecord trade;
    trade.key.session_ordinal = session_ordinal;
    trade.key.decision_ordinal = static_cast<std::int64_t>(i) + 1;
    trade.net_cent = trade_nets[i];
    trade.mae_cent = i < trade_maes.size() ? trade_maes[i] : 0;
    ledger.trades.push_back(trade);
    ledger.net_cent += trade_nets[i];
  }
  ledger.clock_count = static_cast<std::int64_t>(trade_nets.size());
  return ledger;
}

/// One trade as the GAP-THROUGH BREACH panel sees it. The four fields are the
/// four the card's breach definition needs: the realised net, the realised MAE,
/// whether the stop executed, and how far past the wall the fill landed.
struct TradeShape {
  std::int64_t net_cent = 0;
  std::int64_t mae_cent = 0;
  bool stop_hit = false;
  std::int64_t gap_through_cent = 0;
};

DailyLedger make_shaped_ledger(std::int64_t session_ordinal, std::int32_t year,
                               const std::vector<TradeShape>& trades) {
  DailyLedger ledger;
  ledger.session = {session_ordinal, year};
  for (std::size_t i = 0; i < trades.size(); ++i) {
    TradeRecord trade;
    trade.key.session_ordinal = session_ordinal;
    trade.key.decision_ordinal = static_cast<std::int64_t>(i) + 1;
    trade.net_cent = trades[i].net_cent;
    trade.mae_cent = trades[i].mae_cent;
    trade.stop_hit = trades[i].stop_hit;
    trade.gap_through_cent = trades[i].gap_through_cent;
    ledger.trades.push_back(trade);
    ledger.net_cent += trades[i].net_cent;
  }
  ledger.clock_count = static_cast<std::int64_t>(trades.size());
  return ledger;
}

Scorecard score_or_die(const std::vector<DailyLedger>& ledgers) {
  const Expected<Scorecard, Refusal> result = score(ledgers);
  EXPECT_TRUE(result.has_value()) << (result.has_value() ? "" : result.error().message());
  return result.has_value() ? result.value() : Scorecard{};
}

TEST(ZeroInclusiveMdd, ThePeakBeforeAnyGainIsCountedBecauseEZeroIsInTheRunningMaximum) {
  // Two sessions: -$200.00 then +$500.00.
  //   E0 = 0, E1 = -20,000c, E2 = +30,000c
  //   running max INCLUDING E0: 0, 0, 30,000
  //   drawdowns:                0, 20,000, 0        -> MDD = 20,000c = $200.00
  // Drop E0 from the running maximum and the maxima become -20,000 then 30,000,
  // every drawdown is zero and the MDD reads $0.00 — the whole loss disappears.
  const std::vector<DailyLedger> ledgers = {make_ledger(125, 2022, {-20000}),
                                            make_ledger(126, 2022, {50000})};
  const Scorecard card = score_or_die(ledgers);
  EXPECT_EQ(card.mdd_cent, 20000);
  EXPECT_EQ(card.total_net_cent, 30000);
}

TEST(ZeroInclusiveMdd, TheDrawdownIsTheMaximumOverEveryDayNotJustTheLastOne) {
  // Nets: +30,000; -50,000; +10,000; -20,000
  //   E: 0, 30,000, -20,000, -10,000, -30,000
  //   running max: 0, 30,000, 30,000, 30,000, 30,000
  //   drawdowns:   0,      0, 50,000, 40,000, 60,000  -> MDD = 60,000c = $600.00
  const std::vector<DailyLedger> ledgers = {
      make_ledger(125, 2022, {30000}), make_ledger(126, 2022, {-50000}),
      make_ledger(127, 2022, {10000}), make_ledger(128, 2022, {-20000})};
  const Scorecard card = score_or_die(ledgers);
  EXPECT_EQ(card.mdd_cent, 60000);
}

TEST(ZeroInclusiveMdd, AnAllWinningSequenceHasNoDrawdownAtAll) {
  const std::vector<DailyLedger> ledgers = {make_ledger(125, 2022, {10000}),
                                            make_ledger(126, 2022, {20000})};
  EXPECT_EQ(score_or_die(ledgers).mdd_cent, 0);
}

TEST(Denominator, ZeroTradeSessionsStayInTheDenominatorAndInTheEquityPath) {
  // One session made $10.00 and three made nothing: the mean is $2.50, not
  // $10.00. "zero days stay" / "all zero days remain".
  const std::vector<DailyLedger> ledgers = {make_ledger(125, 2022, {1000}),
                                            make_ledger(126, 2022, {}), make_ledger(127, 2022, {}),
                                            make_ledger(128, 2022, {})};
  const Scorecard card = score_or_die(ledgers);
  EXPECT_EQ(card.session_count, 4);
  EXPECT_EQ(card.zero_trade_session_count, 3);
  EXPECT_EQ(card.trade_count, 1);
  EXPECT_DOUBLE_EQ(card.mean_net_dollars, 2.5);
  EXPECT_DOUBLE_EQ(card.trades_per_session, 0.25);
  ASSERT_EQ(card.session_net_cent.size(), 4u);
  EXPECT_EQ(card.session_net_cent[3], 0);
}

TEST(ConcentrationPanels, LeaveTopTenOutDropsExactlyTheTenLargestSessions) {
  // Twelve sessions worth 1,000c .. 12,000c. Total 78,000c over 12 sessions is
  // a $65.00 mean; dropping the ten largest (3,000..12,000 = 75,000c) leaves
  // 3,000c over two sessions = $15.00.
  std::vector<DailyLedger> ledgers;
  for (std::int64_t i = 1; i <= 12; ++i) {
    ledgers.push_back(make_ledger(124 + i, 2022, {i * 1000}));
  }
  const Scorecard card = score_or_die(ledgers);
  EXPECT_DOUBLE_EQ(card.mean_net_dollars, 65.0);
  ASSERT_TRUE(card.mean_net_dollars_leave_top_10_out.has_value());
  EXPECT_DOUBLE_EQ(*card.mean_net_dollars_leave_top_10_out, 15.0);
}

TEST(ConcentrationPanels, LeaveTopTenOutIsUndefinedAtTenSessionsOrFewer) {
  std::vector<DailyLedger> ledgers;
  for (std::int64_t i = 1; i <= 10; ++i) {
    ledgers.push_back(make_ledger(124 + i, 2022, {i * 1000}));
  }
  EXPECT_FALSE(score_or_die(ledgers).mean_net_dollars_leave_top_10_out.has_value());
}

TEST(ConcentrationPanels, MinYearIsTheWorstYearsOwnMean) {
  // 2022: +10,000c and +20,000c -> $150.00 mean.
  // 2023: -5,000c and +1,000c   -> -$20.00 mean.
  const std::vector<DailyLedger> ledgers = {
      make_ledger(125, 2022, {10000}), make_ledger(126, 2022, {20000}),
      make_ledger(500, 2023, {-5000}), make_ledger(501, 2023, {1000})};
  const Scorecard card = score_or_die(ledgers);
  EXPECT_EQ(card.min_year, 2023);
  EXPECT_DOUBLE_EQ(card.min_year_mean_net_dollars, -20.0);
}

// ---------------------------------------------------------------------------
// THE GAP-THROUGH BREACH PANEL (card section 6, consolidated review L3-2).
//
//   "Realized gap-through breaches — defined as `stop_hit[h] AND
//    gap_through_cent > 0` (stop fired AND the fill landed beyond the wall;
//    NOTE: the mod-10 lattice makes `menu_mae_cent>30000` true for EVERY
//    stopped trade, so MAE-threshold counting is a degenerate breach statistic
//    and is forbidden; MAE remains a separate panel)"
//
// THE LATTICE, in one line: `net_cent = frac_u6*10 - 576` (CC-007), so every
// net is congruent to 4 (mod 10) and every MAE, which is `-net` at the worst
// mark, is congruent to 6 (mod 10). A stopped trade crossed the wall, so its
// MAE is at least 30,000 — and the smallest lattice point at or above 30,000 is
// 30,006. `mae > 30000` is therefore TRUE FOR EVERY STOPPED TRADE, and the old
// {29,999 / 30,000 / 30,001} fixture could only look discriminating because not
// one of those three numbers is a value the kernel can produce.
// ---------------------------------------------------------------------------

TEST(BreachPanel, ABreachIsAStopThatGappedThroughTheWallNotMerelyAnMaeAboveIt) {
  const std::vector<DailyLedger> ledgers = {make_shaped_ledger(
      125, 2022,
      {// Stopped, and the fill came back to the wall: NOT a breach — even though
       // its MAE is 30,006, the smallest MAE any stopped trade can print.
       TradeShape{-29996, 30006, true, 0},
       // Stopped, and the fill landed 506c past the wall: THE breach.
       TradeShape{-30506, 30506, true, 506},
       // Never stopped at all.
       TradeShape{-9996, 29996, false, 0}})};
  const Scorecard card = score_or_die(ledgers);
  EXPECT_EQ(card.breach_count, 1);
  // MAE stays its own panel and still sees every trade.
  EXPECT_EQ(card.max_mae_cent, 30506);
}

TEST(BreachPanel, EveryStoppedTradeClearsTheMaeThresholdSoTheMaeTestCannotBeTheBreachTest) {
  // Three stopped trades, none of which gapped through. Under the forbidden
  // `mae > 30000` rule all three would count; under the card's rule none does.
  const std::vector<std::int64_t> maes = {30006, 30016, 30106};
  std::vector<TradeShape> trades;
  for (const std::int64_t mae : maes) {
    trades.push_back(TradeShape{-29996, mae, true, 0});
    EXPECT_GT(mae, kStopNetCent) << "a stopped trade always clears the stop in MAE";
    EXPECT_EQ(mae % 10, 6) << "an MAE off the mod-10 lattice is not a value the kernel can print";
  }
  const std::vector<DailyLedger> ledgers = {make_shaped_ledger(125, 2022, trades)};
  const Scorecard card = score_or_die(ledgers);
  EXPECT_EQ(card.breach_count, 0);
  EXPECT_EQ(card.max_mae_cent, 30106);
}

TEST(BreachPanel, AGapThroughOnARowThatDidNotStopIsNotABreachEither) {
  // Both halves of the conjunction are load-bearing: a nonzero gap_through on a
  // row whose stop never fired is a contradiction the panel must not count.
  const std::vector<DailyLedger> ledgers = {
      make_shaped_ledger(125, 2022, {TradeShape{-9996, 19996, false, 400}})};
  EXPECT_EQ(score_or_die(ledgers).breach_count, 0);
}

TEST(MaeQuantiles, NearestRankOverTenTradesMatchesTheHandComputedIndices) {
  // Ten trades with MAEs 100c..1,000c. Nearest rank, 1-based index ceil(p*N):
  //   p50 -> ceil(0.50*10) =  5 ->   500c
  //   p90 -> ceil(0.90*10) =  9 ->   900c
  //   p95 -> ceil(0.95*10) = 10 -> 1,000c
  //   p99 -> ceil(0.99*10) = 10 -> 1,000c
  //   max                       -> 1,000c
  // No interpolation anywhere: every number printed is an MAE a trade really had.
  std::vector<std::int64_t> nets(10, -100);
  std::vector<std::int64_t> maes;
  for (std::int64_t i = 1; i <= 10; ++i) {
    maes.push_back(i * 100);
  }
  const std::vector<DailyLedger> ledgers = {make_ledger(125, 2022, nets, maes)};
  const Scorecard card = score_or_die(ledgers);
  EXPECT_EQ(card.mae_p50_cent, 500);
  EXPECT_EQ(card.mae_p90_cent, 900);
  EXPECT_EQ(card.mae_p95_cent, 1000);
  EXPECT_EQ(card.mae_p99_cent, 1000);
  EXPECT_EQ(card.max_mae_cent, 1000);
}

TEST(MaeQuantiles, NearestRankRoundsUpOnAnUnevenCountAndPoolsEverySession) {
  // Seven trades spread over three sessions, MAEs 10c..70c:
  //   p50 -> ceil(0.50*7) = 4 -> 40c   (a floor rank would say 30c)
  //   p90 -> ceil(0.90*7) = 7 -> 70c
  //   p95 -> ceil(0.95*7) = 7 -> 70c
  //   p99 -> ceil(0.99*7) = 7 -> 70c
  const std::vector<DailyLedger> ledgers = {
      make_ledger(125, 2022, {-100, -100, -100}, {30, 10, 20}),
      make_ledger(126, 2022, {}, {}),
      make_ledger(127, 2022, {-100, -100, -100, -100}, {70, 40, 60, 50})};
  const Scorecard card = score_or_die(ledgers);
  EXPECT_EQ(card.mae_p50_cent, 40);
  EXPECT_EQ(card.mae_p90_cent, 70);
  EXPECT_EQ(card.mae_p95_cent, 70);
  EXPECT_EQ(card.mae_p99_cent, 70);
  EXPECT_EQ(card.max_mae_cent, 70);
}

TEST(MaeQuantiles, ASingleTradeIsItsOwnEveryQuantileAndNoTradeIsZero) {
  const std::vector<DailyLedger> one = {make_ledger(125, 2022, {-100}, {4242})};
  const Scorecard single = score_or_die(one);
  EXPECT_EQ(single.mae_p50_cent, 4242);
  EXPECT_EQ(single.mae_p99_cent, 4242);
  EXPECT_EQ(single.max_mae_cent, 4242);

  const std::vector<DailyLedger> none = {make_ledger(125, 2022, {})};
  const Scorecard empty = score_or_die(none);
  EXPECT_EQ(empty.mae_p50_cent, 0);
  EXPECT_EQ(empty.mae_p99_cent, 0);
  EXPECT_EQ(empty.max_mae_cent, 0);
}

TEST(ScorecardRefusals, SessionsOutOfChronologicalOrderAreRefused) {
  const std::vector<DailyLedger> ledgers = {make_ledger(126, 2022, {1000}),
                                            make_ledger(125, 2022, {1000})};
  const Expected<Scorecard, Refusal> result = score(ledgers);
  ASSERT_FALSE(result.has_value());
  EXPECT_EQ(result.error().code(), RefusalCode::OUT_OF_ORDER);
}

TEST(ScorecardRefusals, AScorecardOverZeroSessionsIsRefused) {
  const std::vector<DailyLedger> ledgers;
  const Expected<Scorecard, Refusal> result = score(ledgers);
  ASSERT_FALSE(result.has_value());
  EXPECT_EQ(result.error().code(), RefusalCode::CONFIG);
}

}  // namespace
}  // namespace qr::replay
