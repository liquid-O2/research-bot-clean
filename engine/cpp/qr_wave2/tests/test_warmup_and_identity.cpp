// Fixtures CC-012 r3 and r4, plus the burn-in lawfulness the brief names:
//
//   r3  the decision path cannot take a warmup session — by TYPE (a label
//       builder is not invocable with a WarmupScope, and a DayScope is not
//       constructible from one) and by RUNTIME REFUSAL (a decision ordinal in
//       0..124 is refused with the warmup refusal).
//   r4  two-run byte identity of the warmed priors: the same observed sessions
//       produce a bit-identical digest of every view, twice.
//
//   burn-in  sessions 0..124 ARE usable as priors for s125+ — a history warmed
//            over the whole warmup calendar hands s125 a complete ATR14, both
//            range windows and a converged EWMA, with no wall violation and no
//            warmup-absent channel.
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <string>
#include <type_traits>
#include <vector>

#include "gtest/gtest.h"
#include "qr_carriers/grid_1s.hpp"
#include "qr_labels/execution_tape.hpp"
#include "qr_registry/day_scope.hpp"
#include "qr_registry/warmup_scope.hpp"
#include "qr_wave2/prior_state.hpp"
#include "qr_wave2/session_pass.hpp"
#include "wave2_guard.hpp"
#include "wave2_test_support.hpp"

namespace {

using qr::wave2::PriorSessionHistory;
using qr::wave2::PriorView;
using qr::wave2::testing::flat_path;
using qr::wave2::testing::grid_from_path;
using qr::wave2::testing::summary_of;

constexpr std::int64_t kHigh = 101'000'000;
constexpr std::int64_t kLow = 99'000'000;
constexpr std::int64_t kClose = 100'000'000;
constexpr std::int64_t kVwap = 100'500'000;

/// FNV-1a over every bit of a view — the digest shape the carrier probes use.
class Digest {
 public:
  void feed_u64(std::uint64_t bits) noexcept {
    for (unsigned shift = 0; shift < 64; shift += 8) {
      value_ ^= (bits >> shift) & 0xFFULL;
      value_ *= 0x100000001B3ULL;
    }
  }
  void feed_i64(std::int64_t value) noexcept { feed_u64(static_cast<std::uint64_t>(value)); }
  void feed_f64(double value) noexcept {
    std::uint64_t bits = 0;
    static_assert(sizeof(bits) == sizeof(double));
    std::memcpy(&bits, &value, sizeof(bits));
    feed_u64(bits);
  }
  void feed_view(const PriorView& view) noexcept {
    feed_i64(view.prior_present ? 1 : 0);
    feed_i64(view.prior_high_u6);
    feed_i64(view.prior_low_u6);
    feed_i64(view.prior_close_u6);
    feed_i64(view.prior_vwap_present ? 1 : 0);
    feed_i64(view.prior_vwap_u6);
    feed_i64(view.range5_present ? 1 : 0);
    feed_i64(view.high5_u6);
    feed_i64(view.low5_u6);
    feed_i64(view.range20_present ? 1 : 0);
    feed_i64(view.high20_u6);
    feed_i64(view.low20_u6);
    feed_i64(view.atr_present ? 1 : 0);
    feed_f64(view.atr14_bps);
    feed_i64(view.rv_prior_present ? 1 : 0);
    feed_f64(view.rv_prior_rate);
    feed_f64(view.rv_prior_total);
    feed_i64(view.priors_available);
  }
  [[nodiscard]] std::uint64_t value() const noexcept { return value_; }

 private:
  std::uint64_t value_ = 0xCBF29CE484222325ULL;
};

/// A history warmed over the WHOLE warmup calendar (ordinals 0..124), with a
/// per-session variation so nothing is accidentally constant, then five scoped
/// sessions. This is the production warmup shape of CC-012.
PriorSessionHistory warmed_history() {
  PriorSessionHistory history;
  for (std::int64_t ordinal = 0; ordinal <= 129; ++ordinal) {
    const std::int64_t drift = (ordinal % 7) * 100'000;
    const double sum_r2 = 23'400.0 + static_cast<double>(ordinal % 5) * 1'000.0;
    if (!history
             .observe(summary_of(ordinal, kHigh + drift, kLow - drift, kClose + drift,
                                 kVwap + drift, sum_r2))
             .has_value()) {
      qr::detail::fail_fast("warmup fixture: the history refused a summary");
    }
  }
  return history;
}

// --- r3: the decision path cannot take a warmup session ----------------------

TEST(WarmupLawfulness, TheDecisionPathCannotTakeAWarmupSession) {
  // HALF ONE, BY TYPE. The label builder's entry point takes a DayScope, and
  // the two scopes are compile-disjoint, so CC-012's "candidate/label/emission
  // APIs refuse WarmupScope" is a property of the type system. (The disjointness
  // itself is also a static_assert in warmup_scope.hpp: a mutant that adds a
  // conversion fails the BUILD, which the mutant driver records as red too.)
  using ForScope = decltype(&qr::labels::ExecutionTapeBuilder::for_scope);
  EXPECT_TRUE((std::is_invocable_v<ForScope, const qr::DayScope&>));
  EXPECT_FALSE((std::is_invocable_v<ForScope, const qr::WarmupScope&>));
  EXPECT_FALSE((std::is_constructible_v<qr::DayScope, const qr::WarmupScope&>));
  EXPECT_FALSE((std::is_constructible_v<qr::WarmupScope, const qr::DayScope&>));
  EXPECT_FALSE((std::is_convertible_v<qr::WarmupScope, qr::DayScope>));

  // HALF TWO, AT RUNTIME: a raw ordinal cannot smuggle a warmup session into a
  // decision row either.
  for (const std::int64_t ordinal : {std::int64_t{0}, std::int64_t{60}, std::int64_t{124}}) {
    const auto refused = qr::wave2::admit_decision_ordinal(ordinal);
    ASSERT_FALSE(refused.has_value()) << "ordinal " << ordinal << " must not carry a decision";
    EXPECT_EQ(refused.error().code(), qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE);
    EXPECT_NE(std::string(refused.error().detail()).find("never a decision row"),
              std::string::npos);
  }
  EXPECT_TRUE(qr::wave2::admit_decision_ordinal(125).has_value());
  EXPECT_TRUE(qr::wave2::admit_decision_ordinal(749).has_value());
  // AMENDMENT 2026-08-12-c: the decision calendar now runs to W = 917.
  EXPECT_TRUE(qr::wave2::admit_decision_ordinal(750).has_value());
  EXPECT_TRUE(qr::wave2::admit_decision_ordinal(917).has_value());
  EXPECT_FALSE(qr::wave2::admit_decision_ordinal(918).has_value());
  EXPECT_FALSE(qr::wave2::admit_decision_ordinal(962).has_value());
}

// --- the burn-in itself ------------------------------------------------------

TEST(WarmupLawfulness, TheWarmupCalendarLeavesSession125WithFullyConvergedPriors) {
  const PriorSessionHistory history = warmed_history();
  ASSERT_EQ(history.warmup_sessions(), 125);
  // Position 125 is ordinal 125 — the first scoped session.
  ASSERT_EQ(history.summary(125U).ordinal, 125);
  const PriorView view = history.view_for(125U);
  EXPECT_EQ(view.priors_available, 125);
  EXPECT_TRUE(view.prior_present);
  EXPECT_TRUE(view.prior_vwap_present);
  EXPECT_TRUE(view.range5_present);
  EXPECT_TRUE(view.range20_present);
  EXPECT_TRUE(view.atr_present);
  EXPECT_GT(view.atr14_bps, 0.0);
  EXPECT_TRUE(view.rv_prior_present);
  EXPECT_GT(view.rv_prior_rate, 0.0);
  EXPECT_GT(view.rv_prior_total, 0.0);
}

TEST(WarmupLawfulness, WithoutTheWarmupTheFirstScopedSessionsAreTypedAbsent) {
  // The counterfactual CC-012 rules out: starting at s125 leaves the first
  // sessions without an ATR window or a 20-day range. They are TYPED absent —
  // never silently averaged over a short window — which is why the ruling
  // exists at all.
  PriorSessionHistory history;
  for (std::int64_t ordinal = 125; ordinal <= 129; ++ordinal) {
    ASSERT_TRUE(history.observe(summary_of(ordinal, kHigh, kLow, kClose, kVwap, 23'400.0))
                    .has_value());
  }
  const PriorView view = history.view_for(4U);
  EXPECT_EQ(view.priors_available, 4);
  EXPECT_FALSE(view.atr_present);
  EXPECT_FALSE(view.range5_present);
  EXPECT_FALSE(view.range20_present);
  EXPECT_EQ(history.warmup_sessions(), 0);
}

// --- r4: two-run byte identity of the warmed priors --------------------------

TEST(WarmupLawfulness, TwoRunsOfTheWarmupProduceAByteIdenticalPriorState) {
  Digest first;
  Digest second;
  const PriorSessionHistory run1 = warmed_history();
  const PriorSessionHistory run2 = warmed_history();
  ASSERT_EQ(run1.size(), run2.size());
  for (std::size_t position = 0; position < run1.size(); ++position) {
    first.feed_view(run1.view_for(position));
    second.feed_view(run2.view_for(position));
  }
  EXPECT_EQ(first.value(), second.value());
  // and the digest is not a degenerate constant
  EXPECT_NE(first.value(), 0xCBF29CE484222325ULL);
}

// --- the destruction guard ---------------------------------------------------

TEST(Wave2Destructions, TheProductionPathIsIdenticalToABuildWithoutTheFlagCode) {
  // "destruction-flag off = production path byte-identical to a build without
  // the flag code compiled". The comparison binary links a SECOND build of the
  // library compiled with -DQR_WAVE2_NO_DESTRUCTIONS, where the control flags
  // and every branch that reads them do not exist.
  const std::string here = std::filesystem::read_symlink("/proc/self/exe").parent_path().string();
  const std::string command = here + "/qr_wave2_nodestruct_probe";
  ASSERT_TRUE(std::filesystem::exists(command)) << "missing " << command;
  std::FILE* pipe = ::popen(command.c_str(), "r");
  ASSERT_NE(pipe, nullptr);
  char buffer[128] = {0};
  const char* line = std::fgets(buffer, sizeof(buffer), pipe);
  const int status = ::pclose(pipe);
  ASSERT_NE(line, nullptr);
  EXPECT_EQ(status, 0);

  std::string printed(buffer);
  const std::string prefix = "production_fingerprint ";
  ASSERT_EQ(printed.rfind(prefix, 0), 0U) << "unexpected probe output: " << printed;
  std::string digest = printed.substr(prefix.size());
  while (!digest.empty() && (digest.back() == '\n' || digest.back() == '\r')) {
    digest.pop_back();
  }
  EXPECT_EQ(digest.size(), 16U);
  EXPECT_EQ(qr::wave2::guard::production_fingerprint(), digest)
      << "the destruction code moved a production bit";
}

// --- the pure session reduction ---------------------------------------------

TEST(WarmupLawfulness, TheSessionReductionReadsTheGridAndThePrintSumsOnly) {
  // A path that rises then falls, so high/low/close are all different.
  std::vector<std::int64_t> mids = flat_path(100, kClose);
  mids[40] = 101'000'000;  // the session high
  mids[60] = 99'000'000;   // the session low
  mids[99] = 100'250'000;  // the close (the LAST present midpoint)
  const auto grid = grid_from_path(mids);
  const qr::wave2::SessionSummary summary =
      qr::wave2::summarize_session(7, grid, 100 * kClose, 100, 23'400);
  EXPECT_EQ(summary.ordinal, 7);
  EXPECT_TRUE(summary.grid_present);
  EXPECT_EQ(summary.high_u6, 101'000'000);
  EXPECT_EQ(summary.low_u6, 99'000'000);
  EXPECT_EQ(summary.close_u6, 100'250'000);
  EXPECT_TRUE(summary.vwap_present);
  EXPECT_EQ(summary.vwap_u6, kClose);
  EXPECT_EQ(summary.rth_seconds, 23'400);
  EXPECT_GT(summary.rth_sum_r2, 0.0);
  EXPECT_GT(summary.valid_steps, 0);

  // No eligible prints at all: the VWAP is ABSENT, not zero.
  const qr::wave2::SessionSummary no_prints = qr::wave2::summarize_session(8, grid, 0, 0, 23'400);
  EXPECT_FALSE(no_prints.vwap_present);
  EXPECT_EQ(no_prints.vwap_u6, 0);
}

}  // namespace
