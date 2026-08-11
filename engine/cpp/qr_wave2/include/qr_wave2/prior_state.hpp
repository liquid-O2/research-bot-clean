// qr_wave2/prior_state.hpp — THE CROSS-SESSION PRIOR-STATE MACHINES (W2.13, W2.2).
//
// SPEC (design/DESIGN_FEATURES.md sha bf70dd35e5407863):
//
//   §W2.13-PIN-1: "Sources: pH/pL/pC = max/min/last of the prior session's
//    valid 1s-grid eligible-NBBO mids (the frozen spot-law series); pVWAP =
//    prior session Sum(price*size)/Sum(size) over ELIGIBLE stock prints (B2
//    law); O = first valid grid mid today; H_k/L_k = max(pH)/min(pL) over prior
//    k sessions EXCLUDING today, k in {5,20}; ATR14 = simple mean over prior 14
//    sessions of TR_s = [max(pH_s,pC_{s-1}) - min(pL_s,pC_{s-1})] in bps of
//    pC_{s-1}."
//
//   §W2.2-PIN-1: "RV_prior = EWMA_{alpha=0.06} over prior sessions of
//    (Sum_RTH r^2)/T_RTH, seed = first observed session's value (ordinal 0
//    under WarmupScope; converged by s125)." and "RV_prior_TOTAL = EWMA_{0.06}
//    of prior sessions' Sum_RTH r^2 (same accumulator family, total form)".
//
//   §CC-012: warmup ordinals 0..124 feed these accumulators and NOTHING else.
//
// THE THREE-BEAT SHAPE OF qr_carriers/prior_state.hpp, LIFTED TO SESSIONS.
// There, the unit of prior state is an equal-time GROUP and the law is "the
// prior updates only after the whole current group is reduced". Here the unit
// is a whole SESSION and the law is the same one session-sized: a session's own
// values may never enter the priors that session reads. `view_for` therefore
// takes a position and reads only entries STRICTLY BEFORE it, and `observe`
// appends — the two are separate calls for exactly the reason the group
// machines separate `observe` from `commit_group`, and the strictly-prior
// fixture watches WHEN a summary becomes visible rather than only what it
// holds.
//
// EWMA IS STORED PER ENTRY, NOT AS ONE RUNNING SCALAR. Each observed session
// carries the EWMA value AFTER it, so the value a session reads is its
// predecessor's stored one. A running scalar would be indistinguishable from a
// leaked own-session update, and the cross-session shuffle destruction (A11)
// would have nothing well-defined to permute.
#ifndef QR_WAVE2_PRIOR_STATE_HPP
#define QR_WAVE2_PRIOR_STATE_HPP

#include <cstdint>
#include <optional>
#include <span>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_core/validity.hpp"

namespace qr::wave2 {

/// EWMA weight of the newest prior session (A3 / W2.2-PIN-1, frozen).
inline constexpr double kEwmaAlpha = 0.06;
/// Prior sessions in the ATR window (W2.13-PIN-1, frozen).
inline constexpr std::int64_t kAtrWindowSessions = 14;
/// The two range-position windows (W2.13-PIN-1, frozen).
inline constexpr std::int64_t kRangeWindowShort = 5;
inline constexpr std::int64_t kRangeWindowLong = 20;
/// One basis point is 1/10,000 (same constant, same meaning, as the carriers').
inline constexpr std::int64_t kBpsScale = 10'000;

// ---------------------------------------------------------------------------
// One session, reduced to the scalars the two families read.
// ---------------------------------------------------------------------------

/// Everything W2.13 and W2.2 need from a COMPLETED session. Every field is a
/// full-session reduction; nothing here is prefix state, and nothing here is
/// ever read by the session that produced it.
struct SessionSummary {
  /// 0-based calendar ordinal (warmup 0..124 or scoped 125..749).
  std::int64_t ordinal = -1;

  // --- W2.13 sources: the frozen spot-law series -----------------------------
  /// max / min / last of the session's PRESENT 1s-grid midpoints, u6.
  std::int64_t high_u6 = 0;
  std::int64_t low_u6 = 0;
  std::int64_t close_u6 = 0;
  /// At least one present grid endpoint existed. A session without one
  /// contributes no level at all rather than a zero that could be differenced.
  bool grid_present = false;
  /// Sum(price*size)/Sum(size) over eligible stock prints, u6.
  std::int64_t vwap_u6 = 0;
  bool vwap_present = false;

  // --- W2.2 sources: the variance budget's prior term -------------------------
  /// Sum of r^2 over the session's valid 1s grid steps, in bps^2.
  double rth_sum_r2 = 0.0;
  /// T_RTH: the session's RTH span in seconds (the rate denominator).
  std::int64_t rth_seconds = 0;
  /// Valid 1s steps that contributed (audit; never a denominator — the pin
  /// divides by T_RTH).
  std::int64_t valid_steps = 0;

  [[nodiscard]] bool has_rate() const noexcept { return rth_seconds > 0; }
  /// (Sum_RTH r^2)/T_RTH — the per-second variance rate in bps^2/s.
  [[nodiscard]] double rth_rate() const noexcept {
    return has_rate() ? rth_sum_r2 / static_cast<double>(rth_seconds) : 0.0;
  }
};

// ---------------------------------------------------------------------------
// The view one session gets of everything before it.
// ---------------------------------------------------------------------------

/// The prior-session structure a single session reads. Every member is typed:
/// insufficient history is MISSING, never a partial window silently averaged
/// over fewer sessions than the pin names.
struct PriorView {
  /// The immediately preceding session's levels (pH/pL/pC/pVWAP).
  bool prior_present = false;
  std::int64_t prior_high_u6 = 0;
  std::int64_t prior_low_u6 = 0;
  std::int64_t prior_close_u6 = 0;
  bool prior_vwap_present = false;
  std::int64_t prior_vwap_u6 = 0;

  /// H_k / L_k over prior k sessions EXCLUDING today, k in {5,20}.
  bool range5_present = false;
  std::int64_t high5_u6 = 0;
  std::int64_t low5_u6 = 0;
  bool range20_present = false;
  std::int64_t high20_u6 = 0;
  std::int64_t low20_u6 = 0;

  /// ATR14 in bps, simple mean of 14 true ranges. Absent until 15 prior
  /// sessions exist (TR_s needs pC_{s-1}).
  bool atr_present = false;
  double atr14_bps = 0.0;

  /// EWMA(alpha=0.06) over prior sessions of the per-second variance rate
  /// (bps^2/s) and of the session totals (bps^2). Absent before the first
  /// observed session.
  bool rv_prior_present = false;
  double rv_prior_rate = 0.0;
  double rv_prior_total = 0.0;

  /// How many prior sessions the view was formed from — the census's warmup
  /// depth, and the number the insufficient-history guards key on.
  std::int64_t priors_available = 0;
};

// ---------------------------------------------------------------------------
// The history: append-only, chronological, strictly-prior by construction.
// ---------------------------------------------------------------------------

/// A11's destruction, and only it: "cross-session shuffle in train folds".
/// The map is supplied by the CALLER (fold-scoped, so a shuffle can never cross
/// a fold boundary): `shuffle_map[i]` is the position whose priors position `i`
/// reads. An empty map is the identity, which is the production path.
struct DestructionControls {
#ifndef QR_WAVE2_NO_DESTRUCTIONS
  /// W2.13 / A11: cross-session shuffle of the prior attachment.
  bool cross_session_shuffle = false;
  /// Position -> source position. Read only when the flag is set.
  std::span<const std::int64_t> shuffle_map;
  /// W2.2 / A3: B(t) replaced by its session-constant equal-weight time-mean.
  bool session_constant_budget = false;
#endif
};

/// The whole program's cross-session prior state: warmup sessions 0..124 and
/// then the scoped sessions, in chronological order.
class PriorSessionHistory {
 public:
  /// Appends one COMPLETED session. Refuses a non-increasing ordinal — the
  /// chronology of this vector is load-bearing (it is what "prior" means), so
  /// it is checked rather than assumed.
  [[nodiscard]] Expected<std::size_t, Refusal> observe(const SessionSummary& summary);

  /// The view for the session at `position` — formed from entries STRICTLY
  /// BEFORE it. This is the strictly-prior law of this module, in one place.
  [[nodiscard]] PriorView view_for(std::size_t position,
                                   const DestructionControls& controls = {}) const;

  /// The view a session with this ordinal would get. Refuses an ordinal that
  /// was never observed.
  [[nodiscard]] Expected<PriorView, Refusal> view_for_ordinal(
      std::int64_t ordinal, const DestructionControls& controls = {}) const;

  [[nodiscard]] std::size_t size() const noexcept { return entries_.size(); }
  [[nodiscard]] const SessionSummary& summary(std::size_t position) const {
    return entries_[position].summary;
  }
  /// Observed sessions whose ordinal is in the warmup calendar — the CC-012
  /// census line ("warmup ordinals fed per family recorded").
  [[nodiscard]] std::int64_t warmup_sessions() const noexcept { return warmup_sessions_; }
  [[nodiscard]] std::int64_t scoped_sessions() const noexcept {
    return static_cast<std::int64_t>(entries_.size()) - warmup_sessions_;
  }

 private:
  struct Entry {
    SessionSummary summary;
    /// EWMA values AFTER this session (see the header note).
    double ewma_rate_after = 0.0;
    double ewma_total_after = 0.0;
  };

  /// The position whose priors `position` reads, under the controls.
  [[nodiscard]] std::size_t source_position(std::size_t position,
                                            const DestructionControls& controls) const noexcept;

  std::vector<Entry> entries_;
  std::int64_t warmup_sessions_ = 0;
  std::int64_t last_ordinal_ = -1;
  /// The EWMA seed has been taken ("seed = first observed session's value").
  /// A leading session with no rate leaves it unseeded rather than seeding zero.
  bool seeded_ = false;
};

/// TR_s in bps of pC_{s-1}: `[max(pH_s,pC_{s-1}) - min(pL_s,pC_{s-1})] / pC_{s-1}`.
/// Exposed because the ATR fixture asserts the true-range law on hand literals
/// rather than through a fourteen-session mean.
[[nodiscard]] Typed<double> true_range_bps(const SessionSummary& session,
                                           std::int64_t prior_close_u6) noexcept;

}  // namespace qr::wave2

#endif  // QR_WAVE2_PRIOR_STATE_HPP
