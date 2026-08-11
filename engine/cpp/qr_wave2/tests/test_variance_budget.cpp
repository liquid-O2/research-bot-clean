// Fixtures for W2.2 — §W2.2-PIN-1's eight channels on hand-built 1s paths:
//
//   * the per-second RATE law: RV_1m = Sum_{60s} r^2/60 and RV_5m over 300s,
//     combined 0.5/0.3/0.2 with the strictly-prior EWMA;
//   * windows are whole or MISSING (no zero-imputation before 5 minutes);
//   * tau: t_since_open for open/VWAP/range, extreme AGE for high/low, and the
//     tau_min = 10s guard that types rather than divides;
//   * VWAP is the prints-based cumulative, strictly prior at the cutoff, with
//     the equal-time group law honored (a group AT the endpoint is excluded);
//   * zero/absent B is typed, never floored;
//   * the destruction twin: session-constant B, bit-identical to production on
//     a constant-B synthetic and different when B really moves.
#include <cmath>
#include <cstdint>
#include <vector>

#include "gtest/gtest.h"
#include "qr_wave2/variance_budget.hpp"
#include "wave2_test_support.hpp"

namespace {

using qr::Validity;
using qr::carriers::Side;
using qr::wave2::DestructionControls;
using qr::wave2::PriorView;
using qr::wave2::VarianceBudgetInputs;
using qr::wave2::VarianceBudgetRow;
using qr::wave2::VarianceBudgetSession;
using qr::wave2::testing::clock_125;
using qr::wave2::testing::flat_path;
using qr::wave2::testing::grid_from_path;

constexpr std::int64_t kBaseMid = 100'000'000;   // 100.00
constexpr std::int64_t kSteppedMid = 100'100'000;  // 100.10, +10 bps exactly
constexpr std::size_t kStepIndex = 349;            // carried by endpoint 350
constexpr double kPriorRate = 5.0;                 // bps^2/s
constexpr double kPriorTotal = 117'000.0;          // bps^2 over the session

PriorView priors_with_rate() {
  PriorView priors;
  priors.rv_prior_present = true;
  priors.rv_prior_rate = kPriorRate;
  priors.rv_prior_total = kPriorTotal;
  priors.priors_available = 20;
  return priors;
}

/// A path that is flat until `kStepIndex`, then flat again one step higher.
std::vector<std::int64_t> stepped_path() {
  std::vector<std::int64_t> mids = flat_path(400, kBaseMid);
  for (std::size_t index = kStepIndex; index < mids.size(); ++index) {
    mids[index] = kSteppedMid;
  }
  return mids;
}

/// The one nonzero return of the stepped path, in bps.
double step_return_bps() {
  return 1e4 * std::log(static_cast<double>(kSteppedMid) / static_cast<double>(kBaseMid));
}

struct Prints {
  std::vector<qr::carriers::GroupRecord> groups;
  std::vector<std::int64_t> notional_prefix;
  std::vector<std::int64_t> size_prefix;
};

/// Two eligible print groups, at +100s and +200s from the session start, with
/// exact integer running sums (the prefix form the print stream keeps).
Prints two_print_groups() {
  Prints prints;
  for (const std::int64_t offset : {std::int64_t{100}, std::int64_t{200}}) {
    qr::carriers::GroupRecord group;
    group.ts_ns_a = clock_125().session_start_a().ns() + offset * qr::carriers::kNanosPerSecond;
    group.token_count = 1;
    prints.groups.push_back(group);
  }
  // After group 0: 100 shares at 100.00 -> VWAP 100.000000.
  // After group 1: +100 shares at 100.20 -> VWAP 100.100000 exactly.
  prints.notional_prefix = {100 * kBaseMid, 100 * kBaseMid + 100 * std::int64_t{100'200'000}};
  prints.size_prefix = {100, 200};
  return prints;
}

VarianceBudgetInputs inputs_for(const qr::carriers::MidpointGrid& grid, const Prints& prints,
                                const PriorView& priors) {
  VarianceBudgetInputs inputs;
  inputs.grid = &grid;
  inputs.stock_print_groups = prints.groups;
  inputs.vwap_notional_prefix = prints.notional_prefix;
  inputs.vwap_size_prefix = prints.size_prefix;
  inputs.priors = priors;
  return inputs;
}

TEST(VarianceBudget, BIsTheWeightedSumOfTwoPerSecondRatesAndThePrior) {
  const auto grid = grid_from_path(stepped_path());
  const Prints prints = two_print_groups();
  auto session = VarianceBudgetSession::build(inputs_for(grid, prints, priors_with_rate()));
  ASSERT_TRUE(session.has_value());
  const double r2 = step_return_bps() * step_return_bps();

  // Endpoint 360: the step (endpoint 350) is inside BOTH windows.
  const auto b360 = session.value().budget(360);
  ASSERT_EQ(b360.v, Validity::VALID);
  EXPECT_DOUBLE_EQ(b360.value, 0.5 * (r2 / 60.0) + 0.3 * (r2 / 300.0) + 0.2 * kPriorRate);

  // Endpoint 340: the step is in NEITHER window, so both intraday terms are a
  // true zero (the returns really were zero) and only the prior term remains.
  const auto b340 = session.value().budget(340);
  ASSERT_EQ(b340.v, Validity::VALID);
  EXPECT_DOUBLE_EQ(b340.value, 0.2 * kPriorRate);

  // Endpoint 355: inside the 60s window but the 300s window too — same value as
  // 360 because no other return exists between them.
  EXPECT_DOUBLE_EQ(session.value().budget(355).value, b360.value);
}

TEST(VarianceBudget, AWindowThatDoesNotFitIsMissingAndNeverZeroFilled) {
  const auto grid = grid_from_path(stepped_path());
  const Prints prints = two_print_groups();
  auto session = VarianceBudgetSession::build(inputs_for(grid, prints, priors_with_rate()));
  ASSERT_TRUE(session.has_value());
  // Before 300 seconds have elapsed the 5-minute window would have to invent
  // variance for time that is not in the session.
  EXPECT_EQ(session.value().budget(0).v, Validity::MISSING);
  EXPECT_EQ(session.value().budget(299).v, Validity::MISSING);
  EXPECT_EQ(session.value().budget(300).v, Validity::VALID);
  EXPECT_GT(session.value().census().budget_absent_window, 0);
}

TEST(VarianceBudget, AbsentPriorSessionsTypeBAndEveryChannelThatNeedsIt) {
  const auto grid = grid_from_path(stepped_path());
  const Prints prints = two_print_groups();
  auto session = VarianceBudgetSession::build(inputs_for(grid, prints, PriorView{}));
  ASSERT_TRUE(session.has_value());
  EXPECT_EQ(session.value().budget(360).v, Validity::MISSING);
  const VarianceBudgetRow row = session.value().channels(360, Side::LONG);
  for (std::size_t channel = 0; channel < qr::wave2::kVarianceBudgetChannelCount; ++channel) {
    EXPECT_FALSE(row.presence(channel)) << "channel " << channel << " needs B or RV_prior_TOTAL";
    EXPECT_DOUBLE_EQ(row.value[channel], 0.0);
  }
  EXPECT_GT(session.value().census().budget_absent_no_prior, 0);
}

TEST(VarianceBudget, TheFiveXsUseTheirOwnAnchorsAndTauMinTypesRatherThanDivides) {
  const auto grid = grid_from_path(stepped_path());
  const Prints prints = two_print_groups();
  auto session = VarianceBudgetSession::build(inputs_for(grid, prints, priors_with_rate()));
  ASSERT_TRUE(session.has_value());
  const double b = session.value().budget(360).value;

  const VarianceBudgetRow row = session.value().channels(360, Side::LONG);
  // X_open = (100.10-100.00)/100.00 = 10 bps exactly; tau = 360s since the open.
  EXPECT_DOUBLE_EQ(row.value[qr::wave2::kVbXtildeOpen], 10.0 / std::sqrt(b * 360.0));
  // The running high IS the spot here, so the displacement is exactly zero; its
  // tau is the extreme's age (set at endpoint 350, so 10s — the boundary).
  EXPECT_DOUBLE_EQ(row.value[qr::wave2::kVbXtildeHigh], 0.0);
  EXPECT_TRUE(row.presence(qr::wave2::kVbXtildeHigh));
  // The running low was set at endpoint 1 and is 10 bps below: tau = 359s.
  EXPECT_DOUBLE_EQ(row.value[qr::wave2::kVbXtildeLow], 10.0 / std::sqrt(b * 359.0));
  // Range = (H-L)/O = 10 bps, over the since-open tau.
  EXPECT_DOUBLE_EQ(row.value[qr::wave2::kVbXtildeRange], 10.0 / std::sqrt(b * 360.0));

  // tau_min: at endpoint 355 the high is only 5 seconds old, so its channel is
  // TYPED rather than divided by a tiny tau — while the low, 354s old, is not.
  const VarianceBudgetRow early = session.value().channels(355, Side::LONG);
  EXPECT_FALSE(early.presence(qr::wave2::kVbXtildeHigh));
  EXPECT_DOUBLE_EQ(early.value[qr::wave2::kVbXtildeHigh], 0.0);
  EXPECT_TRUE(early.presence(qr::wave2::kVbXtildeLow));
}

TEST(VarianceBudget, TheOrientedChannelsNegateAndTheWidthsDoNot) {
  const auto grid = grid_from_path(stepped_path());
  const Prints prints = two_print_groups();
  auto session = VarianceBudgetSession::build(inputs_for(grid, prints, priors_with_rate()));
  ASSERT_TRUE(session.has_value());
  const VarianceBudgetRow longs = session.value().channels(360, Side::LONG);
  const VarianceBudgetRow shorts = session.value().channels(360, Side::SHORT);
  for (std::size_t channel = 0; channel < qr::wave2::kVarianceBudgetChannelCount; ++channel) {
    ASSERT_EQ(longs.validity[channel], shorts.validity[channel]) << "channel " << channel;
    if (qr::wave2::kVarianceBudgetOrientation[channel] == qr::carriers::OrientKind::SIGMA) {
      EXPECT_DOUBLE_EQ(shorts.value[channel], -longs.value[channel]) << "channel " << channel;
    } else {
      EXPECT_DOUBLE_EQ(shorts.value[channel], longs.value[channel]) << "channel " << channel;
    }
  }
}

TEST(VarianceBudget, TheRunningVwapIsPrintsBasedAndStrictlyPriorAtTheCutoff) {
  const auto grid = grid_from_path(flat_path(400, kBaseMid));
  const Prints prints = two_print_groups();
  auto session = VarianceBudgetSession::build(inputs_for(grid, prints, priors_with_rate()));
  ASSERT_TRUE(session.has_value());

  // Before the first print group: no VWAP at all, never a zero.
  EXPECT_EQ(session.value().running_vwap_u6(50).v, Validity::MISSING);
  // After the first group only: 100 shares at 100.00.
  EXPECT_EQ(session.value().running_vwap_u6(150).value, kBaseMid);
  // AT the second group's own instant: the group is NOT strictly before the
  // endpoint, so it is excluded whole — the equal-time group law.
  EXPECT_EQ(session.value().running_vwap_u6(200).value, kBaseMid);
  // One second later it is included, whole: (100*100.00 + 100*100.20)/200.
  EXPECT_EQ(session.value().running_vwap_u6(201).value, 100'100'000);
}

TEST(VarianceBudget, BudgetConsumedIsTheSessionSumOverThePriorTotal) {
  const auto grid = grid_from_path(stepped_path());
  const Prints prints = two_print_groups();
  auto session = VarianceBudgetSession::build(inputs_for(grid, prints, priors_with_rate()));
  ASSERT_TRUE(session.has_value());
  const double r2 = step_return_bps() * step_return_bps();
  // Before the step nothing has been consumed; after it, exactly one r^2.
  EXPECT_DOUBLE_EQ(session.value().channels(340, Side::LONG).value[qr::wave2::kVbBudgetConsumed],
                   0.0);
  EXPECT_DOUBLE_EQ(session.value().channels(360, Side::LONG).value[qr::wave2::kVbBudgetConsumed],
                   r2 / kPriorTotal);
}

TEST(VarianceBudget, LogBAndItsSixtySecondInnovation) {
  const auto grid = grid_from_path(stepped_path());
  const Prints prints = two_print_groups();
  auto session = VarianceBudgetSession::build(inputs_for(grid, prints, priors_with_rate()));
  ASSERT_TRUE(session.has_value());
  const double b360 = session.value().budget(360).value;
  const double b300 = session.value().budget(300).value;
  const VarianceBudgetRow row = session.value().channels(360, Side::LONG);
  EXPECT_DOUBLE_EQ(row.value[qr::wave2::kVbLogB], std::log(b360));
  EXPECT_DOUBLE_EQ(row.value[qr::wave2::kVbDeltaLogB60], std::log(b360) - std::log(b300));
  // The innovation needs a B sixty seconds back; at endpoint 300 there is none.
  EXPECT_FALSE(session.value().channels(300, Side::LONG).presence(qr::wave2::kVbDeltaLogB60));

  // THE LAG IS SIXTY SECONDS, not any other span: at endpoint 440 the budget of
  // sixty seconds ago still carried the step inside its own minute, while the
  // budget of thirty seconds ago no longer did.
  const double b440 = session.value().budget(440).value;
  const double b380 = session.value().budget(380).value;
  ASSERT_NE(b380, session.value().budget(410).value);
  EXPECT_DOUBLE_EQ(session.value().channels(440, Side::LONG).value[qr::wave2::kVbDeltaLogB60],
                   std::log(b440) - std::log(b380));
}

TEST(VarianceBudget, TheDestructionTwinIsBitIdenticalOnAConstantBSynthetic) {
  // A flat path has no intraday variance at all, so B(t) = 0.2*RV_prior at
  // every endpoint where the windows fit — B is ALREADY constant, and the
  // session-constant twin must therefore reproduce production bit for bit.
  const auto grid = grid_from_path(flat_path(400, kBaseMid));
  const Prints prints = two_print_groups();
  auto production = VarianceBudgetSession::build(inputs_for(grid, prints, priors_with_rate()));
  ASSERT_TRUE(production.has_value());

  DestructionControls controls;
  controls.session_constant_budget = true;
  auto destroyed =
      VarianceBudgetSession::build(inputs_for(grid, prints, priors_with_rate()), controls);
  ASSERT_TRUE(destroyed.has_value());

  for (const std::size_t endpoint : {std::size_t{300}, std::size_t{360}, std::size_t{399}}) {
    const VarianceBudgetRow main = production.value().channels(endpoint, Side::LONG);
    const VarianceBudgetRow twin = destroyed.value().channels(endpoint, Side::LONG);
    for (std::size_t channel = 0; channel < qr::wave2::kVarianceBudgetChannelCount; ++channel) {
      ASSERT_EQ(main.validity[channel], twin.validity[channel]);
      EXPECT_DOUBLE_EQ(main.value[channel], twin.value[channel])
          << "endpoint " << endpoint << " channel " << channel;
    }
  }
}

TEST(VarianceBudget, TheDestructionTwinFlattensARealBudgetAndZeroesItsInnovation) {
  const auto grid = grid_from_path(stepped_path());
  const Prints prints = two_print_groups();
  auto production = VarianceBudgetSession::build(inputs_for(grid, prints, priors_with_rate()));
  ASSERT_TRUE(production.has_value());
  DestructionControls controls;
  controls.session_constant_budget = true;
  auto destroyed =
      VarianceBudgetSession::build(inputs_for(grid, prints, priors_with_rate()), controls);
  ASSERT_TRUE(destroyed.has_value());

  // B really moved in production; under the twin every valid second carries the
  // same equal-weight mean, so the 60s innovation is exactly zero.
  EXPECT_NE(production.value().budget(360).value, production.value().budget(340).value);
  EXPECT_DOUBLE_EQ(destroyed.value().budget(360).value, destroyed.value().budget(340).value);
  EXPECT_DOUBLE_EQ(
      destroyed.value().channels(360, Side::LONG).value[qr::wave2::kVbDeltaLogB60], 0.0);
  EXPECT_NE(production.value().channels(360, Side::LONG).value[qr::wave2::kVbDeltaLogB60], 0.0);
  EXPECT_GT(destroyed.value().census().destruction_constant_budget, 0);
}

TEST(VarianceBudget, SigmaScaleIsTheHalfHourRootOfTheBudget) {
  const auto grid = grid_from_path(flat_path(400, kBaseMid));
  const Prints prints = two_print_groups();
  auto session = VarianceBudgetSession::build(inputs_for(grid, prints, priors_with_rate()));
  ASSERT_TRUE(session.has_value());
  const double b = session.value().budget(360).value;
  EXPECT_DOUBLE_EQ(session.value().sigma_scale_bps(360).value, std::sqrt(b * 1800.0));
  EXPECT_EQ(session.value().sigma_scale_bps(10).v, Validity::MISSING);
}

TEST(VarianceBudget, MisalignedVwapPrefixArraysRefuse) {
  const auto grid = grid_from_path(flat_path(400, kBaseMid));
  Prints prints = two_print_groups();
  prints.size_prefix.pop_back();  // one shorter than the groups
  const auto refused = VarianceBudgetSession::build(inputs_for(grid, prints, priors_with_rate()));
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}

}  // namespace
