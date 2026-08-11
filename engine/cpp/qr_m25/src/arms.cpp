// qr_m25/src/arms.cpp — the decomposition panel and the skill-cell replay.
#include "qr_m25/arms.hpp"

#include <algorithm>
#include <limits>

namespace qr::m25 {
namespace {

using qr::replay::AdmitAllGate;
using qr::replay::DailyLedger;
using qr::replay::LabelState;
using qr::replay::QuantileRiskGate;
using qr::replay::ReplayPolicy;
using qr::replay::ScoredAction;
using qr::replay::SessionRef;
using qr::replay::Side;
using qr::replay::SideOverride;

/// The score that makes the kernel's base selection pick a definite side before
/// a side override runs: LONG 1, SHORT 0. It is a presentation rule, not a
/// prediction — the override, not the score, decides the arm's side.
void write_side_indicator_scores(SessionTape* tape) {
  for (ScoredAction& row : tape->rows) {
    row.predicted_net_h_star = row.key.side == Side::LONG ? 1.0 : 0.0;
    row.predicted_stop_prob_h_ref = 0.0;
  }
}

/// The perfect-side score: the row's own realised menu net, in cents, with
/// unavailable rows pushed below everything.
void write_net_scores(SessionTape* tape, std::size_t horizon_index) {
  for (ScoredAction& row : tape->rows) {
    row.predicted_net_h_star = row.label.state == LabelState::OK
                                   ? static_cast<double>(row.label.menu_net_cent[horizon_index])
                                   : kUnavailableRowScore;
    row.predicted_stop_prob_h_ref = 0.0;
  }
}

SessionRef session_ref(const SessionTape& tape) {
  SessionRef ref;
  ref.session_ordinal = tape.session_ordinal;
  ref.year = tape.year;
  return ref;
}

/// Rows of one clock that could actually trade at this horizon.
bool tradable(const ScoredAction& row) noexcept { return row.label.state == LabelState::OK; }

/// The per-clock control coin of the decomposition panel (purpose
/// DECOMPOSITION_COIN): ONE draw per clock, in clock order, independent of which
/// clocks the schedule ends up using — so the coin's side stream is the same
/// whatever the occupancy path does, which the kernel's own coin (whose draw
/// index advances only on selected clocks) is not.
std::vector<Side> decomposition_coin_sides(const SessionTape& tape, std::int64_t replicate) {
  UniformStream stream(DrawPurpose::DECOMPOSITION_COIN, tape.session_ordinal, replicate);
  std::vector<Side> sides(tape.clock_count(), Side::LONG);
  for (std::size_t c = 0; c < tape.clock_count(); ++c) {
    sides[c] = stream.next() < 0.5 ? Side::LONG : Side::SHORT;
  }
  return sides;
}

/// Members = the row of the named side at each clock, kept only when its own
/// realised net is strictly positive. `sides` is either a constant side or the
/// per-clock control coin.
std::unordered_set<std::int64_t> positive_members_on_sides(const SessionTape& tape,
                                                           std::size_t horizon_index,
                                                           const std::vector<Side>& sides) {
  std::unordered_set<std::int64_t> members;
  for (std::size_t c = 0; c < tape.clock_count(); ++c) {
    const std::size_t end = tape.clock_end(c);
    for (std::size_t i = tape.clock_starts[c]; i < end; ++i) {
      const ScoredAction& row = tape.rows[i];
      if (row.key.side != sides[c] || !tradable(row)) {
        continue;
      }
      if (row.label.menu_net_cent[horizon_index] > 0) {
        members.insert(MemberGate::member_key(row.key));
      }
    }
  }
  return members;
}

/// Members = the best-net row at each clock, kept only when that net is
/// strictly positive (the GREEDY perfect arm).
std::unordered_set<std::int64_t> greedy_best_side_members(const SessionTape& tape,
                                                          std::size_t horizon_index) {
  std::unordered_set<std::int64_t> members;
  for (std::size_t c = 0; c < tape.clock_count(); ++c) {
    const std::size_t end = tape.clock_end(c);
    const ScoredAction* best = nullptr;
    for (std::size_t i = tape.clock_starts[c]; i < end; ++i) {
      const ScoredAction& row = tape.rows[i];
      if (!tradable(row)) {
        continue;
      }
      if (best == nullptr ||
          row.label.menu_net_cent[horizon_index] > best->label.menu_net_cent[horizon_index]) {
        best = &row;
      }
    }
    if (best != nullptr && best->label.menu_net_cent[horizon_index] > 0) {
      members.insert(MemberGate::member_key(best->key));
    }
  }
  return members;
}

}  // namespace

std::int64_t MemberGate::member_key(const qr::replay::ActionKey& key) noexcept {
  return key.decision_ordinal * 2 + (key.side == Side::LONG ? 0 : 1);
}

void MemberGate::begin_session(std::int64_t /*session_ordinal*/) {}

qr::replay::GateDecision MemberGate::evaluate(const ScoredAction& action) const {
  qr::replay::GateDecision decision;
  if (!action.legal_enter) {
    decision.reason = qr::replay::GateReason::ILLEGAL_ROW;
    return decision;
  }
  if (members_.find(member_key(action.key)) == members_.end()) {
    // Not in the plan. BELOW_TOP_Q is the kernel's "this row lost its cell"
    // reason; the member gate has exactly one way to block and this is it.
    decision.reason = qr::replay::GateReason::BELOW_TOP_Q;
    return decision;
  }
  decision.admitted = true;
  decision.reason = qr::replay::GateReason::ADMITTED;
  return decision;
}

void MemberGate::observe(const ScoredAction& /*action*/) {}

const char* arm_name(Arm arm) noexcept {
  switch (arm) {
    case Arm::FORCED_LONG: return "forced_long";
    case Arm::FORCED_SHORT: return "forced_short";
    case Arm::SEEDED_COIN: return "seeded_coin";
    case Arm::PERFECT_SIDE_ONLY: return "perfect_side_only";
    case Arm::PERFECT_TAKESKIP_LONG_SIDE: return "perfect_takeskip_long_side";
    case Arm::PERFECT_TAKESKIP_SHORT_SIDE: return "perfect_takeskip_short_side";
    case Arm::PERFECT_TAKESKIP_COIN_SIDE: return "perfect_takeskip_coin_side";
    case Arm::PERFECT_SIDE_TAKESKIP_GREEDY: return "perfect_side_takeskip_greedy";
    case Arm::PERFECT_SIDE_TAKESKIP_DP: return "perfect_side_takeskip_dp";
  }
  return "unknown_arm";
}

std::unordered_set<std::int64_t> one_position_optimum(const SessionTape& tape,
                                                      std::size_t horizon_index) {
  // Weighted interval scheduling, backwards over the clock list. `best[c]` is
  // the greatest total net obtainable from clock c onwards; `take[c]` records
  // which row (if any) achieves it.
  const std::size_t clocks = tape.clock_count();
  std::vector<std::int64_t> best(clocks + 1, 0);
  std::vector<const ScoredAction*> take(clocks, nullptr);

  // Clock timestamps, so the "first clock strictly after this exit" lookup is a
  // binary search rather than a scan.
  std::vector<std::int64_t> clock_ts(clocks, 0);
  for (std::size_t c = 0; c < clocks; ++c) {
    clock_ts[c] = tape.rows[tape.clock_starts[c]].key.decision_ts_ns;
  }

  for (std::size_t step = clocks; step > 0; --step) {
    const std::size_t c = step - 1;
    std::int64_t value = best[c + 1];  // skip this clock
    const ScoredAction* chosen = nullptr;
    const std::size_t end = tape.clock_end(c);
    for (std::size_t i = tape.clock_starts[c]; i < end; ++i) {
      const ScoredAction& row = tape.rows[i];
      if (!tradable(row)) {
        continue;
      }
      const std::int64_t net = row.label.menu_net_cent[horizon_index];
      const std::int64_t exit_ts = row.label.menu_exit_ts[horizon_index];
      // The kernel's own compatibility rule: "A new entry requires decision_ts >
      // prior certificate_exit_ts".
      const std::size_t next =
          static_cast<std::size_t>(std::upper_bound(clock_ts.begin(), clock_ts.end(), exit_ts) -
                                   clock_ts.begin());
      const std::int64_t candidate = net + best[next];
      if (candidate > value) {
        value = candidate;
        chosen = &row;
      }
    }
    best[c] = value;
    take[c] = chosen;
  }

  std::unordered_set<std::int64_t> members;
  std::size_t c = 0;
  while (c < clocks) {
    if (take[c] == nullptr) {
      ++c;
      continue;
    }
    const ScoredAction& row = *take[c];
    members.insert(MemberGate::member_key(row.key));
    const std::int64_t exit_ts = row.label.menu_exit_ts[horizon_index];
    c = static_cast<std::size_t>(std::upper_bound(clock_ts.begin(), clock_ts.end(), exit_ts) -
                                 clock_ts.begin());
  }
  return members;
}

Expected<DailyLedger, Refusal> run_arm(Arm arm, SessionTape* tape, std::size_t horizon_index,
                                       std::int64_t replicate, std::int64_t daily_loss_limit_cent) {
  if (tape == nullptr) {
    qr::detail::fail_fast("qr_m25::run_arm: null tape");
  }
  ReplayPolicy policy(horizon_index);
  policy.daily_loss_limit_cent = daily_loss_limit_cent;

  switch (arm) {
    case Arm::FORCED_LONG:
    case Arm::FORCED_SHORT:
    case Arm::SEEDED_COIN: {
      write_side_indicator_scores(tape);
      policy.side_override = arm == Arm::FORCED_LONG    ? SideOverride::FORCE_LONG
                             : arm == Arm::FORCED_SHORT ? SideOverride::FORCE_SHORT
                                                        : SideOverride::SEEDED_COIN;
      AdmitAllGate gate;
      return qr::replay::replay(session_ref(*tape), tape->rows, gate, policy);
    }
    case Arm::PERFECT_SIDE_ONLY: {
      write_net_scores(tape, horizon_index);
      AdmitAllGate gate;
      return qr::replay::replay(session_ref(*tape), tape->rows, gate, policy);
    }
    case Arm::PERFECT_TAKESKIP_LONG_SIDE:
    case Arm::PERFECT_TAKESKIP_SHORT_SIDE:
    case Arm::PERFECT_TAKESKIP_COIN_SIDE: {
      write_net_scores(tape, horizon_index);
      std::vector<Side> sides;
      if (arm == Arm::PERFECT_TAKESKIP_COIN_SIDE) {
        sides = decomposition_coin_sides(*tape, replicate);
      } else {
        sides.assign(tape->clock_count(),
                     arm == Arm::PERFECT_TAKESKIP_LONG_SIDE ? Side::LONG : Side::SHORT);
      }
      MemberGate gate(positive_members_on_sides(*tape, horizon_index, sides));
      return qr::replay::replay(session_ref(*tape), tape->rows, gate, policy);
    }
    case Arm::PERFECT_SIDE_TAKESKIP_GREEDY: {
      write_net_scores(tape, horizon_index);
      MemberGate gate(greedy_best_side_members(*tape, horizon_index));
      return qr::replay::replay(session_ref(*tape), tape->rows, gate, policy);
    }
    case Arm::PERFECT_SIDE_TAKESKIP_DP: {
      write_net_scores(tape, horizon_index);
      MemberGate gate(one_position_optimum(*tape, horizon_index));
      return qr::replay::replay(session_ref(*tape), tape->rows, gate, policy);
    }
  }
  return refuse<DailyLedger>(Refusal(RefusalCode::CONFIG, "qr_m25::run_arm", "unknown arm", 0));
}

Expected<DailyLedger, Refusal> run_skill_cell(const SkillDraws& draws, SessionTape* tape,
                                              double q_skill, std::size_t horizon_index,
                                              std::int64_t q_percent, double rho,
                                              std::int64_t daily_loss_limit_cent) {
  apply_skill(draws, q_skill, horizon_index, tape);
  ReplayPolicy policy(horizon_index);
  policy.daily_loss_limit_cent = daily_loss_limit_cent;
  QuantileRiskGate gate(q_percent, rho);
  return qr::replay::replay(session_ref(*tape), tape->rows, gate, policy);
}

}  // namespace qr::m25
