// qr_replay/src/policy_gate.cpp — the A6 gate (card section 6).
#include "qr_replay/policy_gate.hpp"

#include <cmath>

#include "qr_core/refusal.hpp"

namespace qr::replay {

PolicyGate::~PolicyGate() = default;

const char* gate_reason_name(GateReason reason) noexcept {
  switch (reason) {
    case GateReason::ADMITTED: return "ADMITTED";
    case GateReason::ILLEGAL_ROW: return "ILLEGAL_ROW";
    case GateReason::NONFINITE_SCORE: return "NONFINITE_SCORE";
    case GateReason::GATE_WARMUP: return "GATE_WARMUP";
    case GateReason::DEGENERATE_PRIOR: return "DEGENERATE_PRIOR";
    case GateReason::BELOW_TOP_Q: return "BELOW_TOP_Q";
    case GateReason::RISK_ABOVE_RHO: return "RISK_ABOVE_RHO";
  }
  return "UNKNOWN_GATE_REASON";
}

// --- QuantileRiskGate -------------------------------------------------------

QuantileRiskGate::QuantileRiskGate(std::int64_t q_percent, double rho)
    : q_percent_(q_percent), rho_(rho) {
  if (q_percent < 1 || q_percent > 99) {
    detail::fail_fast("QuantileRiskGate: q_percent must be an integer percent in 1..99");
  }
  if (!(rho >= 0.0) || !(rho <= 1.0)) {
    detail::fail_fast("QuantileRiskGate: rho must be a probability in [0,1]");
  }
}

void QuantileRiskGate::begin_session(std::int64_t /*session_ordinal*/) {
  low_ = std::priority_queue<double>();
  high_ = std::priority_queue<double, std::vector<double>, std::greater<double>>();
  min_seen_ = 0.0;
  max_seen_ = 0.0;
}

bool QuantileRiskGate::has_threshold() const noexcept {
  if (low_.empty() && high_.empty()) {
    return false;
  }
  // Degenerate prior: every strictly-prior prediction is the same number, so a
  // top-q threshold would equal that number and admit the whole session.
  // "never a looser gate" (card section 6).
  return min_seen_ != max_seen_;
}

double QuantileRiskGate::threshold() const noexcept {
  const std::int64_t n = population_size();
  if (n <= 0) {
    detail::fail_fast("QuantileRiskGate::threshold() on an empty population");
  }
  // h = floor((1 - q) * (n - 1)) and its fractional part, in exact integers.
  const std::int64_t scaled = (100 - q_percent_) * (n - 1);
  const std::int64_t remainder = scaled % 100;
  const double lower = low_.top();
  const double upper = high_.empty() ? lower : high_.top();
  if (remainder == 0) {
    return lower;
  }
  return lower + (static_cast<double>(remainder) / 100.0) * (upper - lower);
}

void QuantileRiskGate::rebalance() noexcept {
  const std::int64_t n = population_size();
  // low_ must hold exactly h + 1 elements, where h = floor((1 - q) * (n - 1)).
  const std::size_t target = static_cast<std::size_t>(((100 - q_percent_) * (n - 1)) / 100) + 1;
  while (low_.size() > target) {
    high_.push(low_.top());
    low_.pop();
  }
  while (low_.size() < target && !high_.empty()) {
    low_.push(high_.top());
    high_.pop();
  }
}

void QuantileRiskGate::observe(const ScoredAction& action) {
  if (!action.legal_enter) {
    return;  // "among legal rows so far that session"
  }
  if (!std::isfinite(action.predicted_net)) {
    return;  // a nonfinite score is not a number the quantile can carry
  }
  const double value = action.predicted_net;
  if (low_.empty() || value <= low_.top()) {
    low_.push(value);
  } else {
    high_.push(value);
  }
  if (population_size() == 1) {
    min_seen_ = value;
    max_seen_ = value;
  } else {
    min_seen_ = value < min_seen_ ? value : min_seen_;
    max_seen_ = value > max_seen_ ? value : max_seen_;
  }
  rebalance();
}

GateDecision QuantileRiskGate::evaluate(const ScoredAction& action) const {
  if (!action.legal_enter) {
    return {false, GateReason::ILLEGAL_ROW};
  }
  if (!std::isfinite(action.predicted_net) || !std::isfinite(action.predicted_stop_prob)) {
    return {false, GateReason::NONFINITE_SCORE};
  }
  if (!is_warm()) {
    // The preregistered warm-up floor: fewer than kGateWarmupMinimum
    // strictly-prior same-session predictions cannot carry a top-q claim.
    return {false, GateReason::GATE_WARMUP};
  }
  if (min_seen_ == max_seen_) {
    return {false, GateReason::DEGENERATE_PRIOR};
  }
  if (action.predicted_net < threshold()) {
    return {false, GateReason::BELOW_TOP_Q};
  }
  if (action.predicted_stop_prob > rho_) {
    return {false, GateReason::RISK_ABOVE_RHO};
  }
  return {true, GateReason::ADMITTED};
}

// --- AdmitAllGate -----------------------------------------------------------

void AdmitAllGate::begin_session(std::int64_t /*session_ordinal*/) {}

GateDecision AdmitAllGate::evaluate(const ScoredAction& action) const {
  if (!action.legal_enter) {
    return {false, GateReason::ILLEGAL_ROW};
  }
  if (!std::isfinite(action.predicted_net) || !std::isfinite(action.predicted_stop_prob)) {
    return {false, GateReason::NONFINITE_SCORE};
  }
  return {true, GateReason::ADMITTED};
}

void AdmitAllGate::observe(const ScoredAction& /*action*/) {}

}  // namespace qr::replay
