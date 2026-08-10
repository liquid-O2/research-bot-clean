// qr_replay/policy_gate.hpp — the A6 entry gate as an interface, plus its first
// implementation (the causal running top-q quantile + P(stop) <= rho).
//
// SPEC (verbatim, evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 6,
// "A6 gate redesign"):
//   "Entry gate: at each clock, ENTER the unique highest predicted `net_h*`
//    legal side iff (i) that prediction is in the session's top-q quantile of
//    predicted `net_h*` among legal rows so far that session (causal running
//    quantile over strictly-prior same-session predictions), and (ii) predicted
//    `P(stop before h*)` <= rho.  The pair (q, rho) in {1,2,5,10,20,30}% x
//    {.15,.25,.40} is selected on the gate-select block by a NON-DOLLAR
//    criterion only ...  Degenerate/nonfinite scores in a cell => PASS_ALL
//    (zero ENTERs) for that cell, never a looser gate."
//
// "PASS" IS THE CARD'S WORD FOR "DO NOT TRADE" (section 6: watches "PASS/expire";
// PASS_ALL is glossed "zero ENTERs"). A gate that "passes" a row in the English
// sense is one that ADMITS it; to keep the two senses apart, everything here
// says ADMIT / BLOCK and never "pass".
//
// THE THREE LAWS THIS INTERFACE EXISTS TO MAKE MECHANICAL:
//
//  1. CAUSALITY. `evaluate()` is const and `observe()` is the only mutator, and
//     the kernel calls them in that order per equal-timestamp group: every row
//     of a clock is evaluated BEFORE any row of that clock is observed. A row
//     therefore never sees itself, its same-clock sibling, or any future row.
//     A gate that folded the two calls together could not be proven causal by
//     any fixture; split, the proof is a two-line perturbation test.
//  2. NEVER LOOSER. An empty prior population and a DEGENERATE prior population
//     (every strictly-prior prediction equal, so a "top-q" threshold would
//     admit the whole session) both BLOCK, and a nonfinite score blocks its own
//     row and never enters the population.
//  3. ONE POPULATION. Only `legal_enter` rows are observed ("among legal rows
//     so far that session"), and occupancy plays no part: whether a clock was
//     free is a scheduling fact of the replay, not a fact about the score
//     stream, so the threshold at row i is identical under every occupancy path.
#ifndef QR_REPLAY_POLICY_GATE_HPP
#define QR_REPLAY_POLICY_GATE_HPP

#include <cstdint>
#include <functional>
#include <queue>
#include <vector>

#include "qr_replay/action.hpp"

namespace qr::replay {

/// Why a row was admitted or blocked. Every clock in the ledger carries one of
/// these, so no decision is ever unexplained.
enum class GateReason : std::uint8_t {
  ADMITTED = 0,
  ILLEGAL_ROW,      ///< `legal_enter` is false — never gate-eligible.
  NONFINITE_SCORE,  ///< predicted net or risk is not finite.
  GATE_WARMUP,      ///< fewer than `kGateWarmupMinimum` strictly-prior predictions this session.
  DEGENERATE_PRIOR, ///< every strictly-prior prediction is equal; a top-q test would admit all.
  BELOW_TOP_Q,      ///< prediction under the causal running quantile threshold.
  RISK_ABOVE_RHO,   ///< predicted P(stop before h*) > rho.
};

/// WARM-UP FLOOR (orchestrator ruling, 2026-08-10, in answer to this lane's
/// question 3): "gate inadmissible until n>=50 strictly-prior same-session
/// predictions; before that, no entry, typed GATE_WARMUP (preregistered
/// constant)."  A top-q quantile estimated from a handful of prior rows is not
/// a top-q quantile — at n = 1 a "top 1%" test admits anything at or above the
/// single value seen — so the gate reports GATE_WARMUP and enters nothing until
/// its own population can carry the claim. The constant is preregistered: it is
/// not tuned, not per-fold, and not a function of q.
inline constexpr std::int64_t kGateWarmupMinimum = 50;

const char* gate_reason_name(GateReason reason) noexcept;

struct GateDecision {
  bool admitted = false;
  GateReason reason = GateReason::ILLEGAL_ROW;
};

/// The gate interface the replay kernel talks to. Implementations must be
/// deterministic and must not look at labels, outcomes, or anything but the
/// scores and legality of rows already observed.
class PolicyGate {
 public:
  PolicyGate() = default;
  PolicyGate(const PolicyGate&) = delete;
  PolicyGate& operator=(const PolicyGate&) = delete;
  virtual ~PolicyGate();

  /// Called once per session before any row of it is evaluated. Implementations
  /// reset per-session state here: the running population is SESSION-scoped
  /// ("the session's top-q quantile ... so far that session").
  virtual void begin_session(std::int64_t session_ordinal) = 0;

  /// Decide one row against the strictly-prior population. Must not mutate.
  [[nodiscard]] virtual GateDecision evaluate(const ScoredAction& action) const = 0;

  /// Fold one row into the running population. The kernel calls this for every
  /// row of a clock after every row of that clock has been evaluated.
  virtual void observe(const ScoredAction& action) = 0;

  [[nodiscard]] virtual const char* name() const noexcept = 0;
};

/// The A6 gate: causal running top-q quantile over strictly-prior same-session
/// legal predictions, AND predicted P(stop before h*) <= rho.
///
/// THE QUANTILE. Level p = 1 - q over the n strictly-prior predictions, by
/// linear interpolation between order statistics — the definition
/// `numpy.quantile(prior, 1 - q)` uses, so the C++ replay and any Python panel
/// over the same stream agree. It is computed in EXACT rational arithmetic
/// (q is an integer percent from the A6 grid), never as `(1.0 - q) * (n - 1)`
/// in floating point:
///
///     h     = (100 - q_percent) * (n - 1) / 100      (integer division)
///     rem   = (100 - q_percent) * (n - 1) % 100
///     thr   = x[h] + (rem / 100) * (x[h+1] - x[h]),   x[h+1] = x[h] when h = n-1
///
/// and a row is admitted iff `predicted_net >= thr`. The two order statistics
/// x[h], x[h+1] come from a two-heap order-statistic structure (a max-heap of
/// the smallest h+1 values, a min-heap of the rest), so each observation costs
/// O(log n) and the exact same numbers come out as from sorting the population:
/// h grows by at most one per insertion, so one element moves per rebalance.
/// A sorted-vector reference implementation is cross-checked in the tests.
class QuantileRiskGate final : public PolicyGate {
 public:
  /// `q_percent` from the A6 grid {1,2,5,10,20,30}; `rho` from {.15,.25,.40}.
  /// Other values are accepted (the grid is the SELECTION grid, not a wall on
  /// the kernel) but q_percent must be in 1..99 and rho in [0,1].
  QuantileRiskGate(std::int64_t q_percent, double rho);

  void begin_session(std::int64_t session_ordinal) override;
  [[nodiscard]] GateDecision evaluate(const ScoredAction& action) const override;
  void observe(const ScoredAction& action) override;
  [[nodiscard]] const char* name() const noexcept override { return "QuantileRiskGate"; }

  [[nodiscard]] std::int64_t q_percent() const noexcept { return q_percent_; }
  [[nodiscard]] double rho() const noexcept { return rho_; }
  [[nodiscard]] std::int64_t population_size() const noexcept {
    return static_cast<std::int64_t>(low_.size() + high_.size());
  }

  /// True once the population has cleared the preregistered warm-up floor.
  [[nodiscard]] bool is_warm() const noexcept { return population_size() >= kGateWarmupMinimum; }

  /// The current running threshold; only defined once the population is
  /// non-empty and non-degenerate. (Being defined is not being ADMISSIBLE: the
  /// warm-up floor is checked separately, so the threshold can be inspected
  /// while the gate still enters nothing.)
  [[nodiscard]] bool has_threshold() const noexcept;
  [[nodiscard]] double threshold() const noexcept;

 private:
  void rebalance() noexcept;

  std::int64_t q_percent_;
  double rho_;
  std::priority_queue<double> low_;                                                  // max-heap
  std::priority_queue<double, std::vector<double>, std::greater<double>> high_;      // min-heap
  double min_seen_ = 0.0;
  double max_seen_ = 0.0;
};

/// A gate that admits every legal row with finite scores. It is not a null and
/// not a fallback: the M2.5 decomposition panels (FINAL_PLAN section 8: forced
/// sides, seeded coin, perfect take/skip) are defined WITHOUT a learned gate,
/// and the hand-computed chronology fixtures need a gate whose behaviour adds
/// nothing to the arithmetic under test.
class AdmitAllGate final : public PolicyGate {
 public:
  void begin_session(std::int64_t session_ordinal) override;
  [[nodiscard]] GateDecision evaluate(const ScoredAction& action) const override;
  void observe(const ScoredAction& action) override;
  [[nodiscard]] const char* name() const noexcept override { return "AdmitAllGate"; }
};

}  // namespace qr::replay

#endif  // QR_REPLAY_POLICY_GATE_HPP
