// Fixtures for the cross-session prior-state machines (W2.13-PIN-1 sources,
// W2.2-PIN-1's EWMA, A11's destruction):
//
//   * STRICTLY PRIOR — a session's own reduction is invisible to it;
//   * ATR14 — exactly the prior 14 sessions, and absent with fewer than 15;
//   * H_k / L_k — exactly the prior k, EXCLUDING today;
//   * EWMA — seed = the first observed session, then alpha=0.06, and the value
//     a session reads is its PREDECESSOR's;
//   * the cross-session shuffle destruction, and its identity/off behaviour.
#include <cmath>
#include <cstdint>
#include <vector>

#include "gtest/gtest.h"
#include "qr_wave2/prior_state.hpp"
#include "wave2_test_support.hpp"

namespace {

using qr::wave2::DestructionControls;
using qr::wave2::PriorSessionHistory;
using qr::wave2::PriorView;
using qr::wave2::SessionSummary;
using qr::wave2::testing::history_of;
using qr::wave2::testing::summary_of;

// A hand tape of identical sessions: H=101.0, L=99.0, C=100.0, VWAP=100.5.
constexpr std::int64_t kHigh = 101'000'000;
constexpr std::int64_t kLow = 99'000'000;
constexpr std::int64_t kClose = 100'000'000;
constexpr std::int64_t kVwap = 100'500'000;

TEST(PriorHistory, ASessionNeverSeesItsOwnReduction) {
  PriorSessionHistory history = history_of(20, kHigh, kLow, kClose, kVwap);
  // The 21st session is nothing like the others. If any of its own values reach
  // its own view, this fixture fails — that is the strictly-prior law.
  const auto position = history.observe(summary_of(20, 500'000'000, 400'000'000, 450'000'000,
                                                   460'000'000));
  ASSERT_TRUE(position.has_value());
  const PriorView view = history.view_for(position.value());
  EXPECT_EQ(view.prior_high_u6, kHigh);
  EXPECT_EQ(view.prior_low_u6, kLow);
  EXPECT_EQ(view.prior_close_u6, kClose);
  EXPECT_EQ(view.prior_vwap_u6, kVwap);
  EXPECT_EQ(view.high20_u6, kHigh);
  EXPECT_EQ(view.low20_u6, kLow);
  EXPECT_EQ(view.priors_available, 20);
}

TEST(PriorHistory, TheWindowsAreExactlyTheirOwnLength) {
  PriorSessionHistory history;
  // Highs rise session by session, EXCEPT two planted spikes placed so that a
  // window one session too long swallows one of them:
  //   session 18 is inside a 6-session window but outside the 5-session one;
  //   session 4  is inside the 20-session window but outside a 19-session one.
  // A monotone series could not tell these windows apart at all.
  for (std::int64_t ordinal = 0; ordinal < 25; ++ordinal) {
    std::int64_t high = kClose + ordinal * 1'000'000;
    if (ordinal == 18) {
      high = kClose + 50'000'000;
    }
    if (ordinal == 4) {
      high = kClose + 60'000'000;
    }
    ASSERT_TRUE(
        history.observe(summary_of(ordinal, high, kLow - ordinal * 1'000'000, kClose, kVwap))
            .has_value());
  }
  const PriorView view = history.view_for(24U);  // the last observed position
  // Prior 5 = sessions 19..23: the spike at 18 is NOT in it.
  EXPECT_TRUE(view.range5_present);
  EXPECT_EQ(view.high5_u6, kClose + 23 * 1'000'000);
  EXPECT_EQ(view.low5_u6, kLow - 23 * 1'000'000);
  // Prior 20 = sessions 4..23: the spike at 4 IS in it.
  EXPECT_TRUE(view.range20_present);
  EXPECT_EQ(view.high20_u6, kClose + 60'000'000);
  EXPECT_EQ(view.low20_u6, kLow - 23 * 1'000'000);
}

TEST(PriorHistory, AShortWindowIsAbsentAndNeverAveragedOverFewerSessions) {
  PriorSessionHistory history = history_of(4, kHigh, kLow, kClose, kVwap);
  const PriorView view = history.view_for(3U);  // only 3 priors exist
  EXPECT_FALSE(view.range5_present);
  EXPECT_FALSE(view.range20_present);
  EXPECT_FALSE(view.atr_present);
  EXPECT_TRUE(view.prior_present);
}

TEST(PriorHistory, Atr14IsTheMeanTrueRangeOfExactlyFourteenPriorSessions) {
  // TR_s = [max(pH_s,pC_{s-1}) - min(pL_s,pC_{s-1})] in bps of pC_{s-1}
  //      = [101.0 - 99.0] / 100.0 = 2/100 = 200 bps, for every session here.
  PriorSessionHistory history = history_of(16, kHigh, kLow, kClose, kVwap);
  const PriorView view = history.view_for(15U);
  ASSERT_TRUE(view.atr_present);
  EXPECT_DOUBLE_EQ(view.atr14_bps, 200.0);

  // FIFTEEN PRIORS is the minimum: TR_s needs pC_{s-1}, so fourteen true ranges
  // need fifteen summaries behind them. Fourteen priors cannot form the window.
  PriorSessionHistory shorter = history_of(15, kHigh, kLow, kClose, kVwap);
  EXPECT_FALSE(shorter.view_for(14U).atr_present) << "14 priors must not form an ATR14";
  PriorSessionHistory exact = history_of(16, kHigh, kLow, kClose, kVwap);
  EXPECT_TRUE(exact.view_for(15U).atr_present) << "15 priors is the minimum window";
}

TEST(PriorHistory, TrueRangeUsesThePriorCloseWhenItGapsOutsideTheSessionRange) {
  // A gap day: the whole session trades BELOW the prior close, so the true
  // range must be measured from that close, not from the session's own high.
  const SessionSummary gapped = summary_of(1, 98'000'000, 97'000'000, 97'500'000, kVwap);
  const qr::Typed<double> range = qr::wave2::true_range_bps(gapped, kClose);
  ASSERT_EQ(range.v, qr::Validity::VALID);
  // [max(98,100) - min(97,100)] / 100 = 3/100 = 300 bps.
  EXPECT_DOUBLE_EQ(range.value, 300.0);
}

TEST(PriorHistory, TheEwmaSeedsOnTheFirstObservedSessionAndLagsByOne) {
  PriorSessionHistory history;
  // Rates are sum_r2 / 23400. Session 0: 23400 -> rate 1.0. Session 1: 46800 ->
  // rate 2.0. Session 2: 23400 -> rate 1.0.
  ASSERT_TRUE(history.observe(summary_of(0, kHigh, kLow, kClose, kVwap, 23'400.0)).has_value());
  ASSERT_TRUE(history.observe(summary_of(1, kHigh, kLow, kClose, kVwap, 46'800.0)).has_value());
  ASSERT_TRUE(history.observe(summary_of(2, kHigh, kLow, kClose, kVwap, 23'400.0)).has_value());

  // Position 1 reads the EWMA AFTER session 0 — the seed itself.
  const PriorView after_seed = history.view_for(1U);
  ASSERT_TRUE(after_seed.rv_prior_present);
  EXPECT_DOUBLE_EQ(after_seed.rv_prior_rate, 1.0);
  EXPECT_DOUBLE_EQ(after_seed.rv_prior_total, 23'400.0);

  // Position 2 reads the EWMA after session 1: 0.06*2.0 + 0.94*1.0 = 1.06.
  const PriorView after_one = history.view_for(2U);
  ASSERT_TRUE(after_one.rv_prior_present);
  EXPECT_DOUBLE_EQ(after_one.rv_prior_rate, 0.06 * 2.0 + 0.94 * 1.0);
  EXPECT_DOUBLE_EQ(after_one.rv_prior_total, 0.06 * 46'800.0 + 0.94 * 23'400.0);

  // The very first session has no prior at all — absent, not zero.
  EXPECT_FALSE(history.view_for(0U).rv_prior_present);
}

TEST(PriorHistory, ASessionWithNoRateCarriesTheEwmaForwardUnchanged) {
  PriorSessionHistory history;
  ASSERT_TRUE(history.observe(summary_of(0, kHigh, kLow, kClose, kVwap, 23'400.0)).has_value());
  SessionSummary blank = summary_of(1, kHigh, kLow, kClose, kVwap, 0.0);
  blank.rth_seconds = 0;  // no RTH span: no rate to average
  ASSERT_TRUE(history.observe(blank).has_value());
  ASSERT_TRUE(history.observe(summary_of(2, kHigh, kLow, kClose, kVwap, 23'400.0)).has_value());
  // Position 2 reads the EWMA after the rate-less session: still the seed,
  // neither re-seeded nor dragged toward zero by a session that had no rate.
  EXPECT_DOUBLE_EQ(history.view_for(2U).rv_prior_rate, 1.0);
  EXPECT_DOUBLE_EQ(history.view_for(1U).rv_prior_rate, 1.0);
}

TEST(PriorHistory, ObservingOutOfOrderRefuses) {
  PriorSessionHistory history = history_of(3, kHigh, kLow, kClose, kVwap);
  const auto refused = history.observe(summary_of(1, kHigh, kLow, kClose, kVwap));
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::OUT_OF_ORDER);
}

TEST(PriorHistory, TheCrossSessionShuffleMovesThePriorsAndTheIdentityMapDoesNot) {
  PriorSessionHistory history;
  for (std::int64_t ordinal = 0; ordinal < 25; ++ordinal) {
    ASSERT_TRUE(history
                    .observe(summary_of(ordinal, kClose + ordinal * 1'000'000, kLow, kClose,
                                        kVwap))
                    .has_value());
  }
  const PriorView production = history.view_for(24U);

  // Identity map: the destruction is a no-op, which is what makes it a control.
  std::vector<std::int64_t> identity(25);
  for (std::size_t index = 0; index < identity.size(); ++index) {
    identity[index] = static_cast<std::int64_t>(index);
  }
  DestructionControls identity_controls;
  identity_controls.cross_session_shuffle = true;
  identity_controls.shuffle_map = identity;
  const PriorView identical = history.view_for(24U, identity_controls);
  EXPECT_EQ(identical.prior_high_u6, production.prior_high_u6);
  EXPECT_EQ(identical.high20_u6, production.high20_u6);

  // A real permutation: position 24 now reads position 10's priors.
  std::vector<std::int64_t> shuffled = identity;
  shuffled[24] = 10;
  DestructionControls controls;
  controls.cross_session_shuffle = true;
  controls.shuffle_map = shuffled;
  const PriorView destroyed = history.view_for(24U, controls);
  EXPECT_NE(destroyed.prior_high_u6, production.prior_high_u6);
  EXPECT_EQ(destroyed.prior_high_u6, kClose + 9 * 1'000'000);
  EXPECT_EQ(destroyed.priors_available, 10);

  // The FLAG OFF path is the production path, byte for byte.
  DestructionControls off;
  off.shuffle_map = shuffled;  // a map is present but the flag is not set
  const PriorView unaffected = history.view_for(24U, off);
  EXPECT_EQ(unaffected.prior_high_u6, production.prior_high_u6);
}

TEST(PriorHistory, TheWarmupCensusCountsTheWarmupOrdinalsItWasFed) {
  PriorSessionHistory history = history_of(130, kHigh, kLow, kClose, kVwap);
  // Ordinals 0..124 are the warmup calendar; 125..129 are scoped sessions.
  EXPECT_EQ(history.warmup_sessions(), 125);
  EXPECT_EQ(history.scoped_sessions(), 5);
}

}  // namespace
