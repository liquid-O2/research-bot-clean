// qr_replay/tests/test_policy_gate.cpp — the A6 gate: causality of the running
// quantile, the exact order statistics, and the "never a looser gate" rules.
#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
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
constexpr std::int64_t kSid = 400;

std::int64_t T(std::int64_t minutes) { return minutes * kMinuteNs; }

/// The reference quantile: numpy's linear interpolation between order
/// statistics, over a SORTED COPY of the whole population. Deliberately the
/// slow, obvious implementation — it is the oracle the incremental structure
/// has to match.
double reference_quantile(std::vector<double> population, std::int64_t q_percent) {
  std::sort(population.begin(), population.end());
  const std::int64_t n = static_cast<std::int64_t>(population.size());
  const std::int64_t scaled = (100 - q_percent) * (n - 1);
  const std::size_t index = static_cast<std::size_t>(scaled / 100);
  const std::int64_t remainder = scaled % 100;
  const double lower = population[index];
  const double upper = index + 1 < population.size() ? population[index + 1] : lower;
  if (remainder == 0) {
    return lower;
  }
  return lower + (static_cast<double>(remainder) / 100.0) * (upper - lower);
}

ScoredAction scored(std::int64_t ordinal, std::int64_t ts, double net, double stop_prob = 0.0,
                    bool legal = true, std::int64_t hold_ns = 15 * kMinuteNs) {
  return test::make_action(
      kSid,
      ActionSpec{ordinal, ts, Side::LONG, net, stop_prob, legal, LabelState::OK, kSecondNs, hold_ns,
                 100, 0, false},
      kH);
}

/// Drive a gate exactly as the kernel does: evaluate every row of a clock
/// before observing any row of that clock.
std::vector<GateDecision> drive(PolicyGate& gate, const std::vector<ScoredAction>& rows) {
  gate.begin_session(kSid);
  std::vector<GateDecision> decisions(rows.size());
  std::size_t i = 0;
  while (i < rows.size()) {
    std::size_t j = i;
    while (j < rows.size() && rows[j].key.decision_ts_ns == rows[i].key.decision_ts_ns) {
      ++j;
    }
    for (std::size_t k = i; k < j; ++k) {
      decisions[k] = gate.evaluate(rows[k]);
    }
    for (std::size_t k = i; k < j; ++k) {
      gate.observe(rows[k]);
    }
    i = j;
  }
  return decisions;
}

TEST(RunningQuantile, MatchesASortedReferenceAfterEveryObservation) {
  QuantileRiskGate gate(20, 1.0);
  gate.begin_session(kSid);
  Pcg64 rng(SeedSequence::from_entropy(std::array<std::uint64_t, 2>{20260810, 11}));

  std::vector<double> population;
  for (std::int64_t i = 0; i < 4000; ++i) {
    // numpy's random(): the top 53 bits of a 64-bit draw.
    const double value = static_cast<double>(rng.next_uint64() >> 11) * (1.0 / 9007199254740992.0);
    ScoredAction row = scored(i + 1, T(i), value);
    gate.observe(row);
    population.push_back(value);
    ASSERT_EQ(gate.population_size(), static_cast<std::int64_t>(population.size()));
    if (gate.has_threshold()) {
      ASSERT_DOUBLE_EQ(gate.threshold(), reference_quantile(population, 20))
          << "after " << population.size() << " observations";
    }
  }
}

TEST(RunningQuantile, TheThresholdIsTheHandComputedInterpolatedOrderStatistic) {
  // Population 0..99, q = 10%: level p = 0.90, h = 0.90 * 99 = 89.1, so the
  // threshold is x[89] + 0.1 * (x[90] - x[89]) = 89 + 0.1 = 89.1 exactly.
  QuantileRiskGate gate(10, 1.0);
  gate.begin_session(kSid);
  for (std::int64_t i = 0; i < 100; ++i) {
    gate.observe(scored(i + 1, T(i), static_cast<double>(i)));
  }
  ASSERT_TRUE(gate.has_threshold());
  EXPECT_DOUBLE_EQ(gate.threshold(), 89.1);
  EXPECT_TRUE(gate.evaluate(scored(1000, T(1000), 89.1)).admitted);
  EXPECT_FALSE(gate.evaluate(scored(1000, T(1000), 89.09)).admitted);
  EXPECT_EQ(gate.evaluate(scored(1000, T(1000), 89.09)).reason, GateReason::BELOW_TOP_Q);
}

/// Records the gate's verdict on every row the KERNEL asks about, so a test can
/// compare two replays decision by decision rather than only trade by trade.
class DecisionRecordingGate final : public PolicyGate {
 public:
  struct Row {
    std::int64_t ts = 0;
    std::int64_t ordinal = 0;
    std::int64_t side = 0;
    bool admitted = false;
    GateReason reason = GateReason::ILLEGAL_ROW;
  };

  DecisionRecordingGate(std::int64_t q_percent, double rho) : inner_(q_percent, rho) {}

  void begin_session(std::int64_t session_ordinal) override {
    inner_.begin_session(session_ordinal);
    decisions.clear();
  }
  [[nodiscard]] GateDecision evaluate(const ScoredAction& action) const override {
    const GateDecision decision = inner_.evaluate(action);
    decisions.push_back({action.key.decision_ts_ns, action.key.decision_ordinal,
                         static_cast<std::int64_t>(action.key.side), decision.admitted,
                         decision.reason});
    return decision;
  }
  void observe(const ScoredAction& action) override { inner_.observe(action); }
  [[nodiscard]] const char* name() const noexcept override { return "DecisionRecordingGate"; }

  mutable std::vector<Row> decisions;

 private:
  QuantileRiskGate inner_;
};

/// Replay `rows` and return the gate's decision on every row the kernel judged.
std::vector<DecisionRecordingGate::Row> decisions_through_replay(
    const std::vector<ScoredAction>& rows, std::int64_t q_percent = 30) {
  DecisionRecordingGate gate(q_percent, 1.0);
  const Expected<DailyLedger, Refusal> result = replay({kSid, 2023}, rows, gate, ReplayPolicy(kH));
  EXPECT_TRUE(result.has_value()) << (result.has_value() ? "" : result.error().message());
  return gate.decisions;
}

TEST(GateCausality, AFutureRowsScoreCannotChangeAnEarlierRowsDecision) {
  std::vector<ScoredAction> rows;
  for (std::int64_t i = 0; i < 120; ++i) {  // well past the warm-up floor
    const double net = static_cast<double>((i * 37) % 40);  // deterministic spread
    rows.push_back(scored(i + 1, T(i), net));
  }
  QuantileRiskGate gate(30, 1.0);
  const std::vector<GateDecision> baseline = drive(gate, rows);

  for (const std::size_t perturbed : {std::size_t{80}, std::size_t{100}, std::size_t{119}}) {
    std::vector<ScoredAction> mutated = rows;
    mutated[perturbed].predicted_net = 1e9;  // a future row screams
    QuantileRiskGate other(30, 1.0);
    const std::vector<GateDecision> after = drive(other, mutated);
    for (std::size_t i = 0; i < perturbed; ++i) {
      EXPECT_EQ(after[i].admitted, baseline[i].admitted)
          << "row " << i << " changed when future row " << perturbed << " changed";
      EXPECT_EQ(after[i].reason, baseline[i].reason) << "row " << i;
    }

    // The same law THROUGH THE KERNEL: whatever the kernel asked the gate about
    // before the perturbed clock must come back identical, verdict for verdict.
    const std::vector<DecisionRecordingGate::Row> replayed_baseline =
        decisions_through_replay(rows);
    const std::vector<DecisionRecordingGate::Row> replayed_after =
        decisions_through_replay(mutated);
    const std::int64_t perturbed_ts = rows[perturbed].key.decision_ts_ns;
    std::size_t prefix = 0;
    while (prefix < replayed_baseline.size() && replayed_baseline[prefix].ts < perturbed_ts) {
      ++prefix;
    }
    ASSERT_GT(prefix, 0u) << "no decision was made before the perturbed clock";
    ASSERT_GE(replayed_after.size(), prefix);
    for (std::size_t i = 0; i < prefix; ++i) {
      EXPECT_EQ(replayed_after[i].ts, replayed_baseline[i].ts) << "decision " << i;
      EXPECT_EQ(replayed_after[i].ordinal, replayed_baseline[i].ordinal) << "decision " << i;
      EXPECT_EQ(replayed_after[i].admitted, replayed_baseline[i].admitted) << "decision " << i;
      EXPECT_EQ(replayed_after[i].reason, replayed_baseline[i].reason) << "decision " << i;
    }
  }
}

TEST(GateCausality, APriorRowsScoreDoesChangeALaterDecision) {
  // The control for the test above: a gate that ignored its population would
  // pass causality trivially. Raising an EARLY row's score lifts the running
  // threshold and must flip a later admission.
  std::vector<ScoredAction> rows;
  for (std::int64_t i = 0; i < 120; ++i) {
    rows.push_back(scored(i + 1, T(i), static_cast<double>(i % 10)));
  }
  QuantileRiskGate gate(30, 1.0);
  const std::vector<GateDecision> baseline = drive(gate, rows);

  std::vector<ScoredAction> mutated = rows;
  for (std::size_t i = 0; i < 60; ++i) {
    mutated[i].predicted_net = 1e6;  // early rows scream instead
  }
  QuantileRiskGate other(30, 1.0);
  const std::vector<GateDecision> after = drive(other, mutated);

  bool any_flip = false;
  for (std::size_t i = 60; i < rows.size(); ++i) {
    any_flip = any_flip || (after[i].admitted != baseline[i].admitted);
  }
  EXPECT_TRUE(any_flip) << "the gate is insensitive to its own strictly-prior population";
}

TEST(GateCausality, SameClockSiblingsAreNotInEachOthersPopulation) {
  // Two rows share one clock. Whatever the sibling scores, neither row may see
  // it: the population at that clock is the strictly-prior rows only.
  //
  // The numbers are chosen so that the law BITES, at the smallest population the
  // warm-up floor allows. Prior population {1..50} at q = 50% gives
  // h = 0.5 * 49 = 24.5 and threshold x[24] + 0.5*(x[25]-x[24]) = 25 + 0.5 =
  // 25.5, so the LONG row at exactly 25.5 is admitted. Let the same clock's two
  // rows into the population and n becomes 52: h = 0.5 * 51 = 25.5, both order
  // statistics move up, and the identical row is blocked. A fixture where the
  // sibling could not move the threshold would prove nothing.
  // Holds are 30 seconds, well inside the one-minute clock spacing, so that no
  // clock is occupied and the kernel really does evaluate the row under test.
  constexpr std::int64_t kShortHold = 30 * kSecondNs;
  std::vector<ScoredAction> rows;
  for (std::int64_t i = 1; i <= 50; ++i) {
    rows.push_back(scored(i, T(i - 1), static_cast<double>(i), 0.0, true, kShortHold));
  }
  rows.push_back(scored(51, T(50), 25.5, 0.0, true, kShortHold));
  rows.push_back(scored(51, T(50), 5.0, 0.0, true, kShortHold));
  rows.back().key.side = Side::SHORT;
  rows.back().label.key.side = Side::SHORT;

  const std::size_t under_test = rows.size() - 2;  // the LONG row of the shared clock
  QuantileRiskGate gate(50, 1.0);
  const std::vector<GateDecision> baseline = drive(gate, rows);
  ASSERT_TRUE(baseline[under_test].admitted) << "the row under test must start out admitted";

  std::vector<ScoredAction> mutated = rows;
  mutated.back().predicted_net = 1e9;
  QuantileRiskGate other(50, 1.0);
  const std::vector<GateDecision> after = drive(other, mutated);

  EXPECT_EQ(after[under_test].admitted, baseline[under_test].admitted);
  EXPECT_EQ(after[under_test].reason, baseline[under_test].reason);

  // And through the kernel: the sibling's score may decide WHICH row wins the
  // clock, never whether the other row was admitted.
  const std::vector<DecisionRecordingGate::Row> replayed_baseline =
      decisions_through_replay(rows, 50);
  const std::vector<DecisionRecordingGate::Row> replayed_after =
      decisions_through_replay(mutated, 50);
  ASSERT_EQ(replayed_after.size(), replayed_baseline.size());
  ASSERT_EQ(replayed_baseline.size(), rows.size()) << "every row must reach the gate";
  for (std::size_t i = 0; i < replayed_baseline.size(); ++i) {
    if (replayed_baseline[i].ordinal == 51 &&
        replayed_baseline[i].side == static_cast<std::int64_t>(Side::SHORT)) {
      continue;  // the perturbed row itself, whose own verdict is allowed to move
    }
    EXPECT_EQ(replayed_after[i].admitted, replayed_baseline[i].admitted) << "decision " << i;
    EXPECT_EQ(replayed_after[i].reason, replayed_baseline[i].reason) << "decision " << i;
  }
}

TEST(GateWarmUp, NothingIsAdmittedBelowTheFiftyRowFloorAndTheFiftiethRowOpensIt) {
  // The preregistered warm-up floor (kGateWarmupMinimum = 50): an empty
  // population and a 49-row population are equally inadmissible, and the very
  // next observation makes the gate live. The row under test scores far above
  // every prior row, so the ONLY thing that can be blocking it is the floor.
  QuantileRiskGate gate(10, 1.0);
  gate.begin_session(kSid);
  EXPECT_EQ(gate.evaluate(scored(1, T(0), 5.0)).reason, GateReason::GATE_WARMUP)
      << "an empty population is the first warm-up case";

  for (std::int64_t i = 0; i < kGateWarmupMinimum - 1; ++i) {
    gate.observe(scored(i + 1, T(i), static_cast<double>(i)));
  }
  EXPECT_EQ(gate.population_size(), kGateWarmupMinimum - 1);
  EXPECT_FALSE(gate.is_warm());
  const GateDecision cold = gate.evaluate(scored(99, T(99), 1e6));
  EXPECT_FALSE(cold.admitted);
  EXPECT_EQ(cold.reason, GateReason::GATE_WARMUP);

  gate.observe(scored(kGateWarmupMinimum, T(kGateWarmupMinimum), 0.5));
  EXPECT_EQ(gate.population_size(), kGateWarmupMinimum);
  EXPECT_TRUE(gate.is_warm());
  const GateDecision warm = gate.evaluate(scored(99, T(99), 1e6));
  EXPECT_TRUE(warm.admitted) << "the fiftieth strictly-prior row opens the gate";
  EXPECT_EQ(warm.reason, GateReason::ADMITTED);
}

TEST(GateWarmUp, TheFloorIsCountedInStrictlyPriorLegalRowsOnly) {
  // Illegal and nonfinite rows do not count toward the floor: they never join
  // the population, so a session full of them never warms the gate up.
  QuantileRiskGate gate(10, 1.0);
  gate.begin_session(kSid);
  for (std::int64_t i = 0; i < 200; ++i) {
    gate.observe(scored(i + 1, T(i), static_cast<double>(i), 0.0, /*legal=*/false));
  }
  EXPECT_FALSE(gate.is_warm());
  EXPECT_EQ(gate.evaluate(scored(999, T(999), 1e6)).reason, GateReason::GATE_WARMUP);
}

TEST(GateNeverLooser, ADegeneratePopulationBlocksInsteadOfAdmittingEverything) {
  // Every strictly-prior prediction identical: a top-q threshold would equal
  // that value and admit the whole session. Card section 6: "Degenerate/
  // nonfinite scores in a cell => PASS_ALL (zero ENTERs) for that cell, never a
  // looser gate."
  QuantileRiskGate gate(1, 1.0);
  gate.begin_session(kSid);
  for (std::int64_t i = 0; i < 50; ++i) {
    gate.observe(scored(i + 1, T(i), 3.5));
  }
  EXPECT_FALSE(gate.has_threshold());
  const GateDecision decision = gate.evaluate(scored(99, T(99), 3.5));
  EXPECT_FALSE(decision.admitted);
  EXPECT_EQ(decision.reason, GateReason::DEGENERATE_PRIOR);
  // One different value is enough to make the population informative again.
  gate.observe(scored(51, T(51), 9.0));
  EXPECT_TRUE(gate.has_threshold());
}

TEST(GateNeverLooser, TheRiskLegBlocksAboveRho) {
  QuantileRiskGate gate(30, 0.25);
  gate.begin_session(kSid);
  for (std::int64_t i = 0; i < 60; ++i) {  // past the warm-up floor
    gate.observe(scored(i + 1, T(i), static_cast<double>(i)));
  }
  EXPECT_TRUE(gate.evaluate(scored(99, T(99), 100.0, 0.25)).admitted) << "rho is inclusive";
  const GateDecision blocked = gate.evaluate(scored(99, T(99), 100.0, 0.2500001));
  EXPECT_FALSE(blocked.admitted);
  EXPECT_EQ(blocked.reason, GateReason::RISK_ABOVE_RHO);
}

TEST(GateNeverLooser, IllegalRowsAreNeitherAdmittedNorObserved) {
  QuantileRiskGate gate(30, 1.0);
  gate.begin_session(kSid);
  for (std::int64_t i = 0; i < 10; ++i) {
    gate.observe(scored(i + 1, T(i), 1e6, 0.0, /*legal=*/false));
  }
  EXPECT_EQ(gate.population_size(), 0);
  const GateDecision decision = gate.evaluate(scored(99, T(99), 5.0, 0.0, /*legal=*/false));
  EXPECT_FALSE(decision.admitted);
  EXPECT_EQ(decision.reason, GateReason::ILLEGAL_ROW);
}

TEST(GateNeverLooser, NonfiniteScoresBlockTheirOwnRowAndNeverJoinThePopulation) {
  QuantileRiskGate gate(30, 1.0);
  gate.begin_session(kSid);
  for (std::int64_t i = 0; i < 10; ++i) {
    gate.observe(scored(i + 1, T(i), static_cast<double>(i)));
  }
  const std::int64_t before = gate.population_size();
  gate.observe(scored(50, T(50), std::numeric_limits<double>::quiet_NaN()));
  gate.observe(scored(51, T(51), std::numeric_limits<double>::infinity()));
  EXPECT_EQ(gate.population_size(), before);

  EXPECT_EQ(gate.evaluate(scored(52, T(52), std::numeric_limits<double>::quiet_NaN())).reason,
            GateReason::NONFINITE_SCORE);
  ScoredAction bad_risk = scored(53, T(53), 100.0);
  bad_risk.predicted_stop_prob = std::numeric_limits<double>::quiet_NaN();
  EXPECT_EQ(gate.evaluate(bad_risk).reason, GateReason::NONFINITE_SCORE);
}

TEST(GateInReplay, TheKernelCountsNonfiniteScoresAndNeverTradesThem) {
  std::vector<ActionSpec> specs;
  for (std::int64_t i = 0; i < 80; ++i) {  // past the warm-up floor, so trades happen
    specs.push_back({i + 1, T(20 * i), Side::LONG, static_cast<double>((i * 13) % 80), 0.1, true,
                     LabelState::OK, kSecondNs, 15 * kMinuteNs, 100, 0, false});
  }
  std::vector<ScoredAction> tape = make_tape(kSid, specs, kH);
  tape[60].predicted_net = std::numeric_limits<double>::quiet_NaN();

  QuantileRiskGate gate(30, 1.0);
  const Expected<DailyLedger, Refusal> result = replay({kSid, 2023}, tape, gate, ReplayPolicy(kH));
  ASSERT_TRUE(result.has_value()) << (result.has_value() ? "" : result.error().message());
  EXPECT_EQ(result.value().nonfinite_score_count, 1);
  EXPECT_GT(result.value().trade_count(), 0) << "the tape must trade, or nothing is proven";
  for (const TradeRecord& trade : result.value().trades) {
    EXPECT_NE(trade.key.decision_ordinal, 61);
  }
}

/// A gate that records the running threshold after every observation, so a test
/// can compare two replays' POPULATIONS rather than only their trades.
class RecordingGate final : public PolicyGate {
 public:
  RecordingGate(std::int64_t q_percent, double rho) : inner_(q_percent, rho) {}

  void begin_session(std::int64_t session_ordinal) override {
    inner_.begin_session(session_ordinal);
    thresholds.clear();
  }
  [[nodiscard]] GateDecision evaluate(const ScoredAction& action) const override {
    return inner_.evaluate(action);
  }
  void observe(const ScoredAction& action) override {
    inner_.observe(action);
    thresholds.push_back(inner_.has_threshold() ? inner_.threshold()
                                                : std::numeric_limits<double>::quiet_NaN());
  }
  [[nodiscard]] const char* name() const noexcept override { return "RecordingGate"; }

  std::vector<double> thresholds;

 private:
  QuantileRiskGate inner_;
};

/// A gate that records, at every evaluation, the latest timestamp it has been
/// allowed to observe. It is the witness for the kernel's half of the causality
/// law: evaluate-then-observe, per clock.
class OrderWitnessGate final : public PolicyGate {
 public:
  void begin_session(std::int64_t /*session_ordinal*/) override {
    last_observed_ts = std::numeric_limits<std::int64_t>::min();
    evaluated_ts.clear();
    observed_at_evaluate.clear();
  }
  [[nodiscard]] GateDecision evaluate(const ScoredAction& action) const override {
    evaluated_ts.push_back(action.key.decision_ts_ns);
    observed_at_evaluate.push_back(last_observed_ts);
    return {action.legal_enter, action.legal_enter ? GateReason::ADMITTED : GateReason::ILLEGAL_ROW};
  }
  void observe(const ScoredAction& action) override {
    last_observed_ts = action.key.decision_ts_ns;
  }
  [[nodiscard]] const char* name() const noexcept override { return "OrderWitnessGate"; }

  mutable std::vector<std::int64_t> evaluated_ts;
  mutable std::vector<std::int64_t> observed_at_evaluate;
  std::int64_t last_observed_ts = std::numeric_limits<std::int64_t>::min();
};

TEST(GateInReplay, TheKernelEvaluatesAClockBeforeItObservesAnyOfThatClocksRows) {
  // The kernel's half of the causality law. Nothing the gate has been shown at
  // the moment it judges a row may come from that row's own clock or later.
  std::vector<ActionSpec> specs;
  for (std::int64_t i = 0; i < 20; ++i) {
    const std::int64_t ordinal = i + 1;
    specs.push_back({ordinal, T(20 * i), Side::LONG, static_cast<double>(i), 0.1, true,
                     LabelState::OK, kSecondNs, kMinuteNs, 100, 0, false});
    specs.push_back({ordinal, T(20 * i), Side::SHORT, static_cast<double>(i) + 0.5, 0.1, true,
                     LabelState::OK, kSecondNs, kMinuteNs, 100, 0, false});
  }
  OrderWitnessGate witness;
  const Expected<DailyLedger, Refusal> result =
      replay({kSid, 2023}, make_tape(kSid, specs, kH), witness, ReplayPolicy(kH));
  ASSERT_TRUE(result.has_value()) << (result.has_value() ? "" : result.error().message());

  ASSERT_FALSE(witness.evaluated_ts.empty());
  for (std::size_t i = 0; i < witness.evaluated_ts.size(); ++i) {
    EXPECT_LT(witness.observed_at_evaluate[i], witness.evaluated_ts[i])
        << "evaluation " << i << " saw a row from its own clock or later";
  }
}

TEST(GateInReplay, NoTradeHappensUntilTheWarmUpFloorIsCleared) {
  // The kernel's view of the ruling: the first kGateWarmupMinimum legal rows of
  // a session are typed GATE_WARMUP and nothing trades on them, however high
  // they score. Row 0 is given the largest score in the tape precisely so that a
  // missing floor would trade immediately.
  std::vector<ActionSpec> specs;
  for (std::int64_t i = 0; i < 120; ++i) {
    const double net = i == 0 ? 1e6 : static_cast<double>((i * 17) % 120);
    specs.push_back({i + 1, T(20 * i), Side::LONG, net, 0.1, true, LabelState::OK, kSecondNs,
                     kMinuteNs, 100, 0, false});
  }
  const std::vector<ScoredAction> tape = make_tape(kSid, specs, kH);
  DecisionRecordingGate gate(30, 1.0);
  const Expected<DailyLedger, Refusal> result =
      replay({kSid, 2023}, tape, gate, ReplayPolicy(kH));
  ASSERT_TRUE(result.has_value()) << (result.has_value() ? "" : result.error().message());

  ASSERT_EQ(gate.decisions.size(), tape.size()) << "no clock is occupied in this tape";
  for (std::size_t i = 0; i < static_cast<std::size_t>(kGateWarmupMinimum); ++i) {
    EXPECT_EQ(gate.decisions[i].reason, GateReason::GATE_WARMUP) << "decision " << i;
    EXPECT_FALSE(gate.decisions[i].admitted) << "decision " << i;
  }
  const std::int64_t first_admissible_ts = T(20 * kGateWarmupMinimum);
  for (const TradeRecord& trade : result.value().trades) {
    EXPECT_GE(trade.key.decision_ts_ns, first_admissible_ts);
  }
  EXPECT_GT(result.value().trade_count(), 0) << "the gate must open eventually";
}

TEST(GateInReplay, OccupancyDoesNotChangeTheRunningPopulation) {
  // The threshold at a clock is a fact about the SCORE STREAM, not about
  // whether the replay happened to be in a position. Replaying the same scores
  // with a 15-minute first hold and with a two-hour first hold changes WHICH
  // clocks can trade (asserted below, so the test is not vacuous) and must not
  // change the running population by a single element.
  std::vector<ActionSpec> specs;
  for (std::int64_t i = 0; i < 120; ++i) {
    specs.push_back({i + 1, T(20 * i), Side::LONG, static_cast<double>((i * 7) % 120), 0.1, true,
                     LabelState::OK, kSecondNs, 15 * kMinuteNs, 100, 0, false});
  }
  RecordingGate short_hold_gate(30, 1.0);
  const Expected<DailyLedger, Refusal> short_hold =
      replay({kSid, 2023}, make_tape(kSid, specs, kH), short_hold_gate, ReplayPolicy(kH));
  ASSERT_TRUE(short_hold.has_value()) << (short_hold.has_value() ? "" : short_hold.error().message());

  // Every label holds for four hours instead of fifteen minutes. It has to be
  // every label, not just the first: under a real gate the first clock of a
  // session cannot trade at all (it has no strictly-prior population), so
  // lengthening only that hold would change nothing and the test would pass
  // vacuously.
  std::vector<ActionSpec> long_specs = specs;
  for (ActionSpec& spec : long_specs) {
    spec.hold_ns = 240 * kMinuteNs;
  }
  RecordingGate long_hold_gate(30, 1.0);
  const Expected<DailyLedger, Refusal> long_hold =
      replay({kSid, 2023}, make_tape(kSid, long_specs, kH), long_hold_gate, ReplayPolicy(kH));
  ASSERT_TRUE(long_hold.has_value()) << (long_hold.has_value() ? "" : long_hold.error().message());

  EXPECT_GT(short_hold.value().trade_count(), long_hold.value().trade_count())
      << "the two occupancy paths must actually differ, or this test proves nothing";

  ASSERT_EQ(short_hold_gate.thresholds.size(), long_hold_gate.thresholds.size());
  for (std::size_t i = 0; i < short_hold_gate.thresholds.size(); ++i) {
    const double a = short_hold_gate.thresholds[i];
    const double b = long_hold_gate.thresholds[i];
    ASSERT_EQ(std::isnan(a), std::isnan(b)) << "threshold " << i;
    if (!std::isnan(a)) {
      EXPECT_DOUBLE_EQ(a, b) << "threshold " << i;
    }
  }
}

}  // namespace
}  // namespace qr::replay
