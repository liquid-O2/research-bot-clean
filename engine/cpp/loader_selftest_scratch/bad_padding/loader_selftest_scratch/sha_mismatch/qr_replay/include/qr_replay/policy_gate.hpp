// qr_replay/policy_gate.hpp — the A6 entry gate as an interface, plus its first
// implementation (the causal running top-q quantile + P(stop) <= rho).
//
// SPEC (verbatim, evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 6,
// "A6 gate redesign", as rewritten by the consolidated review):
//   "Entry gate: at each clock, ENTER the unique highest predicted `net_h\*` legal side
//    (predicted menu-net at the selected h\*) iff (i) that prediction is in the session's
//    top-q quantile among legal rows so far that session (causal running quantile over
//    strictly-prior same-session predictions, warm-up n>=50), and (ii) predicted
//    `P(stop before h_ref)` <= rho. **The triple (h\*, q, rho) in {2,5,15,30,60,120,close} x
//    {1,2,5,10,20,30}% x {.15,.25,.40} is selected on the gate-select block by the NON-DOLLAR
//    criterion only: noncensored favorable-vs-adverse AUC (favorable = net_h > 0) at that
//    coverage, tested one-sided against AUC=0.5 by session-block bootstrap, Holm-corrected at
//    FWER alpha=0.05 across the 126 cells; the argmax is taken over SURVIVING cells only; zero
//    survivors => typed NO_ADMISSIBLE_GATE => PASS_ALL for that arm/fold, never a looser rule;
//    ties -> smallest q, then smallest rho, then h closest to h_ref.** The selected triple
//    freezes before gate-cert and TEST. Degenerate/nonfinite scores in a cell
//    => PASS_ALL (zero ENTERs) for that cell, never a looser gate."
//
// TWO HORIZONS, NOT ONE, AND THAT IS THE POINT OF THE REWRITE. The SCORE the
// gate ranks and thresholds is the predicted menu net at the SELECTED h\*; the
// RISK it tests is `P(stop before h_ref)`, and h_ref is the FIXED comparability
// horizon of 15 minutes (card section 3's h-LAW), not h\*. The two
// `ScoredAction` fields are named `predicted_net_h_star` and
// `predicted_stop_prob_h_ref` so the difference is visible at every call site.
//
// WHAT IS AND IS NOT IMPLEMENTED HERE. The SELECTION of (h\*, q, rho) over the
// 126 cells — the AUC, the session-block bootstrap, the Holm correction — is
// Python-side (family (ii) of the A7 multiplicity structure). What lives here is
// the typed OUTCOME of that selection and the gate it produces:
// `GateSelection` carries either a SELECTED triple or NO_ADMISSIBLE_GATE, and
// `make_selected_gate` turns the second into a `PassAllGate` that enters
// nothing. The refusal to invent a looser fallback is therefore mechanical
// rather than a promise in prose.
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
#include <memory>
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
  RISK_ABOVE_RHO,   ///< predicted P(stop before h_ref) > rho.
  /// Family (ii) produced ZERO surviving cells for this arm/fold, so there is no
  /// admissible (h*, q, rho) at all and the arm PASSes every clock. It is a
  /// typed outcome and not an error: "zero survivors => typed
  /// NO_ADMISSIBLE_GATE => PASS_ALL for that arm/fold, never a looser rule".
  NO_ADMISSIBLE_GATE,
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
/// and a row is admitted iff `predicted_net_h_star >= thr`. The two order statistics
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

// ---------------------------------------------------------------------------
// The family-(ii) selection outcome, and the gate it produces.
// ---------------------------------------------------------------------------

/// What the CAL gate-select block concluded for one arm/fold.
enum class GateSelectionOutcome : std::uint8_t {
  /// At least one of the 126 cells survived Holm at alpha = 0.05, and the argmax
  /// over the survivors is the frozen triple.
  SELECTED = 0,
  /// Zero survivors. There is no admissible gate, and the arm/fold PASSes every
  /// clock — "never a looser rule".
  NO_ADMISSIBLE_GATE = 1,
};

[[nodiscard]] const char* gate_selection_outcome_name(GateSelectionOutcome outcome) noexcept;

/// The frozen result of family (ii) for one arm/fold. THE SELECTION ITSELF IS
/// PYTHON-SIDE; this struct is the boundary the C++ replay consumes, so the two
/// halves cannot disagree about what "no admissible gate" means.
///
/// On NO_ADMISSIBLE_GATE the three parameters are meaningless and must not be
/// read: `make_selected_gate` returns a `PassAllGate`, which never looks at
/// them. That is deliberate — a struct that carried a "default" triple beside
/// the refusal would be one careless read away from the looser rule the card
/// forbids.
struct GateSelection {
  GateSelectionOutcome outcome = GateSelectionOutcome::SELECTED;
  /// h* as an index into the seven-horizon menu (`kHorizonMinutes`).
  std::size_t horizon_index = 0;
  std::int64_t q_percent = 0;
  double rho = 0.0;
};

/// The gate of an arm/fold with NO admissible cell: it BLOCKS every row, with
/// the typed reason, and observes nothing.
///
/// "PASS_ALL" is the card's phrase and it means zero ENTERs (section 6 glosses
/// it exactly so). This class is named for what it does to rows — it admits
/// none — and its reason names why.
class PassAllGate final : public PolicyGate {
 public:
  void begin_session(std::int64_t session_ordinal) override;
  [[nodiscard]] GateDecision evaluate(const ScoredAction& action) const override;
  void observe(const ScoredAction& action) override;
  [[nodiscard]] const char* name() const noexcept override { return "PassAllGate"; }
};

/// THE PLUMBING STUB: the one place a `GateSelection` becomes a gate. A
/// SELECTED triple builds the A6 `QuantileRiskGate`; NO_ADMISSIBLE_GATE builds
/// the `PassAllGate`. There is no third branch, so there is nowhere for a
/// fallback to grow.
[[nodiscard]] std::unique_ptr<PolicyGate> make_selected_gate(const GateSelection& selection);

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
