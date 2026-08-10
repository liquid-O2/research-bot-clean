// qr_replay/tests/test_replay_budget.cpp — the WP11 efficiency gate.
//
// BUDGET (WP11 brief): a 1,000,000-action synthetic replay in <= 2s
// single-threaded. FINAL_PLAN section 6, "Efficiency law": "every WP has a CI
// benchmark gate — slower than budget cannot merge".
//
// The tape is built ONCE and excluded from the measurement: what is being timed
// is the kernel and its gate, not the harness. The gate is the real one
// (QuantileRiskGate), because the running quantile is the only part of the
// kernel that is not O(1) per row and is therefore the only thing a budget can
// meaningfully protect.
#include <gtest/gtest.h>

#include <chrono>
#include <cinttypes>
#include <cstdio>
#include <vector>

#include "qr_replay/policy_gate.hpp"
#include "qr_replay/replay.hpp"
#include "replay_test_support.hpp"

namespace qr::replay {
namespace {

using test::kMinuteNs;
using test::kSecondNs;

constexpr std::size_t kH = 2;
constexpr std::int64_t kSid = 600;
constexpr double kBudgetSeconds = 2.0;

#if defined(__SANITIZE_ADDRESS__)
constexpr std::size_t kClocks = 50000;  // the sanitizers time themselves, not us
#else
constexpr std::size_t kClocks = 500000;  // x2 sides = 1,000,000 actions
#endif

std::vector<ScoredAction> synthetic_tape() {
  std::vector<ScoredAction> tape;
  tape.reserve(2 * kClocks);
  for (std::size_t k = 0; k < kClocks; ++k) {
    const std::int64_t ordinal = static_cast<std::int64_t>(k) + 1;
    const std::int64_t ts = static_cast<std::int64_t>(k) * 10 * kSecondNs;
    // A deterministic, well-spread score stream: a full-period LCG mixed down
    // to [0,1). No randomness library involvement, so the benchmark tape is
    // identical on every run and machine.
    const std::uint64_t mixed = (static_cast<std::uint64_t>(k) * 6364136223846793005ull) + 1ull;
    const double score = static_cast<double>(mixed >> 11) * (1.0 / 9007199254740992.0);
    for (const Side side : {Side::LONG, Side::SHORT}) {
      test::ActionSpec spec;
      spec.decision_ordinal = ordinal;
      spec.decision_ts_ns = ts;
      spec.side = side;
      spec.predicted_net = side == Side::LONG ? score : 1.0 - score;
      spec.predicted_stop_prob = 0.1;
      spec.fill_delay_ns = kSecondNs;
      spec.hold_ns = kMinuteNs;
      spec.net_cent = side == Side::LONG ? 100 : -100;
      tape.push_back(test::make_action(kSid, spec, kH));
    }
  }
  return tape;
}

TEST(ReplayBudget, OneMillionActionsReplayInsideTheSingleThreadWall) {
  const std::vector<ScoredAction> tape = synthetic_tape();
  ASSERT_EQ(tape.size(), 2 * kClocks);

  double best = 0.0;
  std::int64_t trades = 0;
  for (int attempt = 0; attempt < 3; ++attempt) {
    QuantileRiskGate gate(5, 0.40);
    const auto started = std::chrono::steady_clock::now();
    const Expected<DailyLedger, Refusal> result =
        replay({kSid, 2023}, tape, gate, ReplayPolicy(kH));
    const auto finished = std::chrono::steady_clock::now();
    ASSERT_TRUE(result.has_value()) << (result.has_value() ? "" : result.error().message());
    const double seconds = std::chrono::duration<double>(finished - started).count();
    if (attempt == 0 || seconds < best) {
      best = seconds;
    }
    trades = result.value().trade_count();
  }
  ASSERT_GT(trades, 0) << "a replay that never trades is not a benchmark of anything";

  const double rate = static_cast<double>(tape.size()) / best;
  std::printf("[ BUDGET   ] qr_replay: %zu actions in %.4fs (%.0f actions/s, %" PRId64 " trades)\n",
              tape.size(), best, rate, trades);

#if !defined(__SANITIZE_ADDRESS__)
  EXPECT_LE(best, kBudgetSeconds)
      << "the WP11 budget is 1,000,000 actions in 2 seconds, single-threaded";
#else
  GTEST_SKIP() << "the wall is not asserted under the sanitizers; measured " << best << "s for "
               << tape.size() << " actions";
#endif
}

}  // namespace
}  // namespace qr::replay
