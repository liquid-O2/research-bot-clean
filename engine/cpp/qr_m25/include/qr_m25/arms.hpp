// qr_m25/arms.hpp — the M2.5 DECOMPOSITION PANEL (FINAL_PLAN.md section 8 item 2)
// and the two M2.5-local gates it needs.
//
// SPEC, VERBATIM (FINAL_PLAN section 8 item 2):
//   "Descriptive decomposition panel: forced-LONG, forced-SHORT, seeded coin;
//    perfect-side-only; perfect take/skip at control sides; perfect side+take/skip
//    under one-position scheduling — locating value in side vs abstention vs
//    occupancy. NO hindsight exits anywhere."
//
// EVERY ARM GOES THROUGH THE SAME FROZEN KERNEL. An arm is nothing but (a) a
// score written into `ScoredAction::predicted_net_h_star`, (b) a gate, and
// (c) a `ReplayPolicy`. No arm computes a dollar itself; `qr::replay::replay`
// does, once, for all of them. That is what makes the panel comparable.
//
// WHAT "HINDSIGHT" MEANS HERE, EXACTLY. The panel is DESCRIPTIVE: its whole
// purpose is to say how much of the money lives in knowing the SIDE versus
// knowing when to ABSTAIN versus the OCCUPANCY schedule, so the perfect arms
// necessarily use the realised menu net to choose. What they must NOT do is
// change the EXIT: every arm exits at the same frozen menu horizon with the same
// causal $300 stop, which is precisely the "NO hindsight exits anywhere" clause.
// The kernel enforces it structurally — a trade's net is `menu_net_cent[h]` of
// the row's own label, and no arm can reach past that.
//
// THE ONE-POSITION OPTIMUM. "perfect side+take/skip under one-position
// scheduling" is the BEST schedule the frozen replay can execute, not the greedy
// take-every-positive-trade rule: taking a small winner can block a large one,
// so the greedy rule is strictly weaker and is NOT the envelope. Both are
// reported; the DP (weighted interval scheduling over the rows' own
// (decision_ts, exit_ts, net) triples, with the kernel's own compatibility rule
// `next decision_ts > prior exit_ts`) is the envelope, and it is the arm the
// affine cap B is derived from (FINAL_PLAN section 8: "the affine cap B is
// re-derived here from the perfect-skill envelope").
#ifndef QR_M25_ARMS_HPP
#define QR_M25_ARMS_HPP

#include <cstdint>
#include <string>
#include <unordered_set>
#include <vector>

#include "qr_m25/skill.hpp"
#include "qr_m25/tape.hpp"
#include "qr_replay/policy_gate.hpp"
#include "qr_replay/replay.hpp"

namespace qr::m25 {

/// FINAL_PLAN section 11's binding daily-loss-limit, in cents, and its two
/// declared NONBINDING panels.
inline constexpr std::int64_t kDailyLossLimitCent = -90000;
inline constexpr std::int64_t kDailyLossLimitPanelCent = -60000;

/// The score an unavailable-label row carries in the perfect arms: strictly
/// below every reachable net (a session's net is bounded by the $300 stop and
/// the day's range, so 1e15 cents is unreachable by many orders of magnitude),
/// and FINITE, because a nonfinite score is a censused defect in the kernel.
inline constexpr double kUnavailableRowScore = -1e15;

/// A gate that admits EXACTLY a precomputed set of rows, identified by their own
/// prediction keys. It is the mechanism behind every "perfect take/skip" arm:
/// the abstention decision is made once, outside the kernel, and the kernel then
/// executes it under its own chronology and occupancy rules.
class MemberGate final : public qr::replay::PolicyGate {
 public:
  explicit MemberGate(std::unordered_set<std::int64_t> members) : members_(std::move(members)) {}

  /// The member key: `decision_ordinal * 2 + (side == LONG ? 0 : 1)`, which is
  /// one-to-one inside a session because the prediction key is.
  [[nodiscard]] static std::int64_t member_key(const qr::replay::ActionKey& key) noexcept;

  void begin_session(std::int64_t session_ordinal) override;
  [[nodiscard]] qr::replay::GateDecision evaluate(const qr::replay::ScoredAction& action) const override;
  void observe(const qr::replay::ScoredAction& action) override;
  [[nodiscard]] const char* name() const noexcept override { return "M25MemberGate"; }

 private:
  std::unordered_set<std::int64_t> members_;
};

/// The nine panel arms.
enum class Arm : std::uint8_t {
  FORCED_LONG = 0,
  FORCED_SHORT,
  SEEDED_COIN,
  PERFECT_SIDE_ONLY,
  PERFECT_TAKESKIP_LONG_SIDE,
  PERFECT_TAKESKIP_SHORT_SIDE,
  PERFECT_TAKESKIP_COIN_SIDE,
  PERFECT_SIDE_TAKESKIP_GREEDY,
  PERFECT_SIDE_TAKESKIP_DP,
};

inline constexpr std::size_t kArmCount = 9;
[[nodiscard]] const char* arm_name(Arm arm) noexcept;

/// Replay one arm over one session at one horizon. `tape` is scratch: the arm
/// writes its own scores into it. `replicate` seeds the decomposition coin.
[[nodiscard]] Expected<qr::replay::DailyLedger, Refusal> run_arm(
    Arm arm, SessionTape* tape, std::size_t horizon_index, std::int64_t replicate,
    std::int64_t daily_loss_limit_cent);

/// Replay the skill-Q agent of `draws` through one gate cell of the A6 family.
/// This is the object the Q* sweep measures.
[[nodiscard]] Expected<qr::replay::DailyLedger, Refusal> run_skill_cell(
    const SkillDraws& draws, SessionTape* tape, double q_skill, std::size_t horizon_index,
    std::int64_t q_percent, double rho, std::int64_t daily_loss_limit_cent);

/// The one-position optimum's member set at one horizon (exposed for the
/// hand-arithmetic fixtures, which check the DP against an enumerated optimum).
[[nodiscard]] std::unordered_set<std::int64_t> one_position_optimum(const SessionTape& tape,
                                                                   std::size_t horizon_index);

}  // namespace qr::m25

#endif  // QR_M25_ARMS_HPP
