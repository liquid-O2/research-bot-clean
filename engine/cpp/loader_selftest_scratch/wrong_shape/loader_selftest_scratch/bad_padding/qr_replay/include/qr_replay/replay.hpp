// qr_replay/replay.hpp — THE economic replay kernel (there is exactly one).
//
// SPEC (verbatim, FINAL_PLAN.md APPENDIX C6):
//   "`replay(span<ScoredAction>, PolicyGate&) → DailyLedger`; chronological,
//    one-position, uncapped, tie-abstain, occupied-skip, zero days, E0=0 MDD;
//    mutants: side reversal, double cost, occupancy shift, initial-zero
//    removal, tie reorder, key misjoin."
//
// SPEC (verbatim, card section 6, the chronology/selection law):
//   "At an equal decision timestamp, select the unique highest predicted-net
//    legal side among rows passing the frozen gate; an exact top tie abstains.
//    A selected row uses only its own fresh label/exit. A new entry requires
//    `decision_ts > prior certificate_exit_ts`; there is no cooldown and all
//    zero days remain. Occupied clocks cannot enter."
//   "An ENTER selected on an unavailable label becomes typed `NO_FRESH_FILL`,
//    makes no trade, closes those watches, and is never silently dropped."
//
// SPEC (verbatim, FINAL_PLAN.md section 11, part of the ENTRY policy):
//   "**Causal daily-loss-limit (designer C4; part of the ENTRY policy):** with
//    E0=0 in the running max, ONE session losing >$1,000 fails the contract
//    outright; frozen ex ante: cumulative realized intraday P&L <= -$900 => PASS
//    for the rest of the session ({inf, -$600} as nonbinding panels)."
//
// SPEC (FINAL_PLAN.md section 8 item 2 / section 11 N1): the kernel carries the
// null-control side streams — "forced-LONG, forced-SHORT, seeded coin" and
// "N1 side-coin at identical times".
//
// THE SIGNATURE. C6 writes `replay(span<ScoredAction>, PolicyGate&)`; both of
// those arguments are here unchanged. Two more are unavoidable and neither is a
// design choice:
//   * `SessionRef` — a session that produced no legal row at all still has to
//     appear in the denominator ("zero-trade/unavailable sessions in the
//     denominator", "all zero days remain"), and an empty span cannot say which
//     session it is or which year it belongs to (the min-year panel).
//   * `ReplayPolicy` — which of the seven menu horizons is being replayed
//     (N5 replays all seven), which side-override stream is running, and the
//     daily-loss-limit value, which section 11 freezes as one binding number
//     plus two panels rather than one constant.
//
// WHAT THE KERNEL NEVER DOES: it never charges the 576c cost (the label kernel
// did, once — see action.hpp), never interpolates inside a session, never caps
// the number of entries, never drops a row silently, and never lets an outcome
// influence a selection.
#ifndef QR_REPLAY_REPLAY_HPP
#define QR_REPLAY_REPLAY_HPP

#include <array>
#include <cstdint>
#include <optional>
#include <span>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_replay/action.hpp"
#include "qr_replay/policy_gate.hpp"

namespace qr::replay {

/// What happened at one decision clock. Every clock in the session lands in
/// exactly one of these buckets and the buckets sum to the clock count: that is
/// what "never silently dropped" means, mechanically.
enum class ClockOutcome : std::uint8_t {
  ENTERED = 0,
  NO_LEGAL_ROW,               ///< no legal row at this clock.
  GATE_BLOCKED,               ///< legal rows, none admitted by the gate.
  ABSTAIN_TIE,                ///< exact top tie among admitted rows.
  OCCUPIED,                   ///< a position was open: "occupied clocks cannot enter".
  NO_FRESH_FILL,              ///< selected row's label is not OK.
  OVERRIDE_SIDE_UNAVAILABLE,  ///< a side-override stream found no legal row of the forced side.
  HALTED_DAILY_LOSS,          ///< causal daily-loss-limit already tripped this session.
};

inline constexpr std::size_t kClockOutcomeCount = 8;
const char* clock_outcome_name(ClockOutcome outcome) noexcept;

/// Null-control side streams (FINAL_PLAN sections 8 and 11). The override
/// replaces the SIDE of a selection the model already made, at the model's own
/// clock, so entry TIMES are preserved ("N1 side-coin at identical times");
/// it never invents a clock the model did not select.
enum class SideOverride : std::uint8_t {
  NONE = 0,
  FORCE_LONG,
  FORCE_SHORT,
  SEEDED_COIN,  ///< PCG64 SeedSequence([20260810, sid, side_index]); see pcg64.hpp.
};

const char* side_override_name(SideOverride override_kind) noexcept;

/// Which session is being replayed. `year` exists only for the min-year
/// concentration panel (card section 6: "leave-top-10-out, and min-year").
struct SessionRef {
  std::int64_t session_ordinal = 0;
  std::int32_t year = 0;
};

/// The replay's frozen policy knobs.
struct ReplayPolicy {
  /// The horizon index into the 7-menu. Required at construction: a default
  /// would be a hidden choice of h*, and h* is chosen per fold on TRAIN.
  explicit ReplayPolicy(std::size_t horizon) : horizon_index(horizon) {}

  std::size_t horizon_index;
  SideOverride side_override = SideOverride::NONE;

  /// Cumulative realized intraday P&L at or below this many cents halts entries
  /// for the rest of the session. FINAL_PLAN section 11 freezes -90000 (-$900)
  /// as the binding value and {none, -60000} as the nonbinding panels; there is
  /// deliberately no default, so every call states which of the three it is.
  std::optional<std::int64_t> daily_loss_limit_cent{};
};

/// One executed trade.
struct TradeRecord {
  ActionKey key{};             ///< the row actually executed (after any side override).
  std::int64_t entry_ts_ns = 0;
  std::int64_t exit_ts_ns = 0;
  std::int64_t net_cent = 0;   ///< menu_net_cent[h] — already net of the 576c, charged once.
  std::int64_t mae_cent = 0;   ///< menu_mae_cent[h] — the separate MAE panel's input.
  bool stop_hit = false;
  /// The label's own `gap_through_cent`: how far past the wall the stop's fill
  /// landed. With `stop_hit` this is the whole of the card's breach definition
  /// (`stop_hit AND gap_through_cent > 0`); the MAE column is a different panel
  /// and never the breach test.
  std::int64_t gap_through_cent = 0;
};

/// The C6 return type: one session's economic result plus the typed census that
/// accounts for every clock in it.
struct DailyLedger {
  SessionRef session{};
  std::vector<TradeRecord> trades;

  /// Sum of `trades[i].net_cent`; exactly zero on a zero-trade day, which stays
  /// in the denominator.
  std::int64_t net_cent = 0;

  /// Clock census, indexed by `ClockOutcome`. Sums to `clock_count`.
  std::array<std::int64_t, kClockOutcomeCount> clock_census{};
  std::int64_t clock_count = 0;

  /// Row-level counts (rows, not clocks).
  std::int64_t row_count = 0;
  std::int64_t legal_row_count = 0;
  std::int64_t nonfinite_score_count = 0;  ///< the degenerate-score census of card section 6.

  /// True once the causal daily-loss-limit halted the session.
  bool halted_daily_loss = false;

  /// Coin draws consumed (SEEDED_COIN only) — the reproducibility receipt.
  std::int64_t coin_draws = 0;

  [[nodiscard]] std::int64_t trade_count() const noexcept {
    return static_cast<std::int64_t>(trades.size());
  }
  [[nodiscard]] bool zero_trade_session() const noexcept { return trades.empty(); }
};

/// Replay ONE session. `actions` must be chronological (nondecreasing
/// `decision_ts_ns`) and belong to `session`; anything else is a typed refusal,
/// never a silent sort and never a skipped row.
///
/// Refusals: OUT_OF_ORDER (chronology), CONTENT_MISMATCH (foreign session,
/// duplicated prediction key, label/score key misjoin, a label that did not
/// charge the cost exactly once), CLOCK_VIOLATION (a fill at or before its own
/// decision instant, or an exit before its own entry), CONFIG (horizon index
/// outside the 7-menu).
Expected<DailyLedger, Refusal> replay(const SessionRef& session,
                                      std::span<const ScoredAction> actions,
                                      PolicyGate& gate,
                                      const ReplayPolicy& policy);

}  // namespace qr::replay

#endif  // QR_REPLAY_REPLAY_HPP
