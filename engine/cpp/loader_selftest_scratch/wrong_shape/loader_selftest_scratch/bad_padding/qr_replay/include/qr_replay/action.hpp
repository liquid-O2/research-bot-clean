// qr_replay/action.hpp — the minimal ScoredAction / LabelRow the ONE economic
// replay kernel consumes (WP11; WP7's label kernel conforms to these structs).
//
// SPEC (verbatim, FINAL_PLAN.md APPENDIX C6):
//   "**C6 replay:** `replay(span<ScoredAction>, PolicyGate&) → DailyLedger`;
//    chronological, one-position, uncapped, tie-abstain, occupied-skip, zero
//    days, E0=0 MDD; mutants: side reversal, double cost, occupancy shift,
//    initial-zero removal, tie reorder, key misjoin."
//
// SPEC (verbatim, evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 6):
//   "At an equal decision timestamp, select the unique highest predicted-net
//    legal side among rows passing the frozen gate; an exact top tie abstains.
//    A selected row uses only its own fresh label/exit. A new entry requires
//    `decision_ts > prior certificate_exit_ts`; there is no cooldown and all
//    zero days remain. Occupied clocks cannot enter."
//
// THE KEY (card section 3, verbatim): "The scientific/ prediction key
// `(session_ordinal,decision_ordinal,side)` plus timestamp must be one-to-one;
// `decision_second` is never substituted for ordinal."  APPENDIX C4 stores it
// as `keys [N,4] i8` in BOTH the feature and the truth leaf — the four int64
// fields of `ActionKey` below, in that order.  The kernel re-checks the score
// row's key against its own label's key on every row: that check is what the
// C6 "key misjoin" mutant has to defeat.
//
// WHERE THE 576 CENTS LIVE, AND WHY THE KERNEL DOES NOT SUBTRACT THEM.
// The cost is charged ONCE in the whole pipeline, by the LABEL kernel, and the
// menu values the replay consumes are already net of it.  Card section 3, the
// label-kernel paragraph, verbatim: "entry = first eligible IWM quote group
// strictly after the decision; LONG entry ask_max/mark bid_min, SHORT entry
// bid_min/mark ask_max; adverse wins equal-ms; 576 cents cost once."  The same
// section fixes the unit arithmetically: the barrier thresholds are "+/-5,000
// **net cents** after cost (about +$55.76 gross versus -$44.24 gross)" —
// 5,000 net + 576 = 5,576 gross, so net = gross - 576.  The "$300 stop" is
// likewise "=30,000 net-cent".  Therefore:
//
//   * `LabelRow::menu_net_cent[h]` is NET of the 576c;
//   * the replay kernel adds NOTHING and subtracts NOTHING — the C6 "double
//     cost" mutant is a kernel that charges the cost a second time;
//   * `LabelRow::cost_charged_cent` records what the label kernel charged, and
//     `replay()` REFUSES any row whose value is not exactly 576, which is how
//     "charged once per trade" becomes a checkable invariant of the kernel
//     rather than an honour-system comment.
#ifndef QR_REPLAY_ACTION_HPP
#define QR_REPLAY_ACTION_HPP

#include <array>
#include <cstdint>

namespace qr::replay {

/// The frozen menu of exit horizons (card section 3 / APPENDIX D):
/// h in {2, 5, 15, 30, 60, 120 min, close}.  Index 6 is "close".
inline constexpr std::size_t kHorizonCount = 7;

/// Minutes per horizon index; the close horizon carries -1 because it is not a
/// duration ("close => final eligible group").
inline constexpr std::array<std::int32_t, kHorizonCount> kHorizonMinutes = {2, 5, 15, 30, 60, 120, -1};

/// Round-trip cost, charged ONCE per trade by the label kernel (card section 3).
inline constexpr std::int64_t kTradeCostCent = 576;

/// The causal stop, in NET cents (card section 3: "the causal $300 (=30,000
/// net-cent) stop"). It is the WALL, and it is NOT the breach test: card
/// section 6 defines a realized gap-through breach as `stop_hit[h] AND
/// gap_through_cent > 0` and forbids `menu_mae_cent > 30000`, because
/// `net_cent = frac_u6*10 - 576` puts every net on the residue class 4 (mod 10)
/// and every MAE on 6 (mod 10) — so the smallest MAE a stopped trade can print
/// is 30,006 and the MAE threshold is true for every one of them.
inline constexpr std::int64_t kStopNetCent = 30000;

/// Side authentication (APPENDIX A notation: "sigma=+1 LONG/-1 SHORT").
/// The underlying type is int64 so `ActionKey` is exactly four int64 fields,
/// the `keys [N,4] i8` layout of APPENDIX C4.
enum class Side : std::int64_t { LONG = 1, SHORT = -1 };

/// Label availability (card section 3, verbatim): "Label states `OK`,
/// `ENTRY_UNAVAILABLE`, and `EXIT_UNAVAILABLE` are separate outcome masks.
/// Every row is predicted and retained.  An ENTER selected on an unavailable
/// label becomes typed `NO_FRESH_FILL`, makes no trade, closes those watches,
/// and is never silently dropped."  NO_FRESH_FILL is not a label state: it is
/// what the REPLAY does with a selected row whose label is not OK, so it lives
/// in `ClockOutcome` (replay.hpp), not here.
enum class LabelState : std::uint8_t {
  OK = 0,
  ENTRY_UNAVAILABLE = 1,
  EXIT_UNAVAILABLE = 2,
};

const char* label_state_name(LabelState state) noexcept;
const char* side_name(Side side) noexcept;

/// The scientific/prediction key, `keys [N,4] i8` (APPENDIX C4), in the frozen
/// field order.
struct ActionKey {
  std::int64_t session_ordinal = 0;
  std::int64_t decision_ordinal = 0;
  std::int64_t decision_ts_ns = 0;  // FrameA nanoseconds
  Side side = Side::LONG;

  [[nodiscard]] std::array<std::int64_t, 4> to_array() const noexcept {
    return {session_ordinal, decision_ordinal, decision_ts_ns, static_cast<std::int64_t>(side)};
  }

  friend bool operator==(const ActionKey& a, const ActionKey& b) noexcept {
    return a.session_ordinal == b.session_ordinal && a.decision_ordinal == b.decision_ordinal &&
           a.decision_ts_ns == b.decision_ts_ns && a.side == b.side;
  }
};

/// The truth leaf of APPENDIX C4 for ONE action row, restricted to what the
/// economic replay reads: `menu_net_cent [7] i8`, `menu_mae_cent [7] i8`,
/// `menu_exit_ts [7] i8`, `stop_hit [7] u1`, `label_state u1`, `keys [4] i8`.
/// WP7 (`label_action(QuoteGroups&, ActionKey, Side) -> Expected<LabelRow,
/// Refusal>`, APPENDIX C5) conforms to THIS struct; certificate_net/mae and the
/// barrier class are truth columns the ECONOMIC replay never reads (card
/// section 3: "Certificate quantities are NONPROMOTABLE for economics and
/// never gate anything in section 6"), so they are absent by construction.
struct LabelRow {
  ActionKey key{};
  LabelState state = LabelState::OK;

  /// Fill instant: "entry = first eligible IWM quote group strictly after the
  /// decision" (card section 3). FrameA nanoseconds.
  std::int64_t entry_ts_ns = 0;

  /// Per horizon: realised NET cents (cost already charged once), the exact
  /// marked MAE from entry through that exit, the exit instant, and whether the
  /// causal $300 stop executed before the horizon.
  std::array<std::int64_t, kHorizonCount> menu_net_cent{};
  std::array<std::int64_t, kHorizonCount> menu_mae_cent{};
  std::array<std::int64_t, kHorizonCount> menu_exit_ts{};
  std::array<std::uint8_t, kHorizonCount> stop_hit{};

  /// How far past the wall the STOP's fill landed, in cents, and zero when it
  /// landed at or above the wall — the card's "gap-through retained and
  /// reported". It is a per-ROW scalar and not a per-horizon array because
  /// there is exactly ONE shared `stop_scan` per action row (card section 3:
  /// "ONE shared stop_scan primitive"); `stop_hit[h]` is that one scan read
  /// against each horizon's exit, and the fill it reports is the same fill for
  /// every horizon that stopped.
  ///
  /// WHY THE ECONOMIC REPLAY READS IT. The breach panel of card section 6 is
  /// `stop_hit[h] AND gap_through_cent > 0`; without this column the replay can
  /// only see `menu_mae_cent`, and MAE-threshold counting is the degenerate
  /// statistic the same paragraph forbids.
  std::int64_t gap_through_cent = 0;

  /// What the LABEL kernel charged, in cents. Must be exactly `kTradeCostCent`
  /// on an OK label; `replay()` refuses otherwise (the cost-once invariant).
  std::int64_t cost_charged_cent = kTradeCostCent;
};

/// One scored decision row: the model's two predictions for this (clock, side),
/// its legality, and its OWN fresh label.  The label travels WITH the row
/// because the chronology law says "A selected row uses only its own fresh
/// label/exit" — there is no join inside the kernel to get wrong, and a
/// mis-joined label is caught by the key check instead of being executed.
struct ScoredAction {
  ActionKey key{};

  /// THE SCORE: predicted `net_h*` — "the unique highest predicted `net_h*`
  /// legal side (predicted menu-net at the SELECTED h*)" (card section 6). Any
  /// monotone score unit: only its ORDER and its place in the causal running
  /// quantile are used.
  double predicted_net_h_star = 0.0;

  /// THE RISK: predicted `P(stop before h_ref)` — the A6 risk gate's input, and
  /// h_ref is NOT h*. Card section 3's h-LAW: "all horizon-bound heads bind to
  /// the FIXED comparability horizon h_ref = 15 min", while h* is selected per
  /// fold on the CAL gate-select block jointly with (q, rho). Card section 6
  /// spells the same split out inside the gate itself: the score is the menu net
  /// at the selected h*, and clause (ii) reads "predicted `P(stop before
  /// h_ref)` <= rho". The two field names carry that difference so a caller
  /// cannot fill one from the other by accident.
  double predicted_stop_prob_h_ref = 0.0;

  /// Card section 6: "`legal_enter` is determined only by the authenticated
  /// watch and clock." Illegal rows are still predicted and retained; they can
  /// never be selected and never enter the gate's running population.
  bool legal_enter = true;

  LabelRow label{};
};

}  // namespace qr::replay

#endif  // QR_REPLAY_ACTION_HPP
