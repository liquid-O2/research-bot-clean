// qr_labels/label_kernel.hpp — THE fresh-entry label kernel: one shared
// stop_scan, the seven-horizon executable menu, the co-primary certificate and
// the barrier auxiliary.
//
// SPEC (verbatim, evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 3):
//   "For every unique action row, the C++ label kernel (ONE shared stop_scan
//    primitive; a 1-cent stop shift must move every ledger identically)
//    produces the native fresh labels: entry = first eligible IWM quote group
//    strictly after the decision; LONG entry ask_max/mark bid_min, SHORT entry
//    bid_min/mark ask_max; adverse wins equal-ms; 576 cents cost once.
//    **A1 PRIMARY — executable fixed-menu outcome vector:** for every horizon
//    h in {2, 5, 15, 30, 60, 120 min, close}: the causal $300 (=30,000
//    net-cent) stop is monitored from entry; if the marked net crosses
//    -30,000c the exit fills at the NEXT lawful mark strictly after crossing
//    (gap-through retained and reported); otherwise exit at the first eligible
//    group with ts >= t_entry + h (close => final eligible group). Emit
//    `menu_net_cent[7]`, `menu_mae_cent[7]`, `menu_exit_ts[7]`, `stop_hit[7]`.
//    **Co-primary (representation discrimination, weight 0.5 in section 5):**
//    `certificate_net_cent` = the uncapped best positive executable mark before
//    the first net -30,000-cent adverse wall, otherwise the wall or final
//    eligible group; `certificate_mae_cent` = exact marked MAE from entry
//    through that exit."
//   "`legal_enter` is determined only by the authenticated watch and clock.
//    Label states `OK`, `ENTRY_UNAVAILABLE`, and `EXIT_UNAVAILABLE` are
//    separate outcome masks. Every row is predicted and retained."
//   "The barrier auxiliary calls `barrier_order(entry_idx,side,5000,5000)`:
//    thresholds are +/-5,000 **net cents** after cost ..., scanned over full
//    RTH; same-group ties map to ADVERSE_FIRST. Raw states are FAVORABLE_FIRST,
//    ADVERSE_FIRST, SAME_GROUP_ADVERSE, NEITHER; the three-class auxiliary maps
//    SAME_GROUP_ADVERSE to ADVERSE_FIRST and NEITHER to CENSORED."
// SPEC (FINAL_PLAN.md APPENDIX C5): "`label_action(QuoteGroups&, ActionKey,
//    Side) -> Expected<LabelRow,Refusal>`; ONE stop_scan primitive for wall +
//    all 7 horizons; 1-cent-shift mutant must move both ledgers identically."
// SPEC (FINAL_PLAN.md APPENDIX A13): "per horizon h: entry per kernel; shared
//    stop_scan (wall -30,000c net); stop => exit next lawful mark strict-after
//    (gap-through retained); else first eligible group >= t_entry+h (close =>
//    final group). Emit menu_net_cent[7], menu_mae_cent[7], menu_exit_ts[7],
//    stop_hit[7] -> truth leaf."
//
// ONE STOP_SCAN, LITERALLY. `stop_scan` is called ONCE per action row and its
// result — the crossing index and the next-lawful-mark exit index — is the only
// wall knowledge the menu ledger and the certificate ledger have. Neither
// re-derives it, so the APPENDIX C5 mutant (move the wall) cannot move one
// ledger without moving the other; that is a structural property of this file,
// and `test_label_kernel.cpp` fires it as a mutation.
//
// THE C5 MUTANT, STATED HONESTLY (a WP7 finding, reported not buried). The
// realised net is `frac*10 - 576`, so every reachable net is congruent to 4
// modulo 10 and the reachable nets straddling the wall are -30,006 and -29,996.
// Shifting the wall by ONE cent (-30,000 -> -29,999 or -30,001) therefore
// cannot move any crossing: the frac threshold `floor((T+576)/10)` is -2,943 for
// all three. The mutant is VACUOUS as literally worded, and no test can catch
// it because there is nothing to catch. WP7 implements it in both honest forms:
//   * the one-cent shift moves NEITHER ledger, proven with the lattice
//     arithmetic in the test rather than asserted; and
//   * the SMALLEST EFFECTIVE shift (to -29,996, the next reachable net) moves
//     the crossing, and both ledgers move with it, together, to the same new
//     crossing — which is what the mutant is FOR.
//
// WHAT "MONITORED FROM ENTRY" MEANS HERE, PRECISELY:
//   * the wall, the horizons and the certificate all scan marks STRICTLY AFTER
//     the entry group ("Search future eligible groups strictly after entry
//     through registry close", the frozen kernel's own statement,
//     transcripts/CONVERSATION.md:24082). You cannot be stopped out at the
//     instant you fill.
//   * the MAE ranges over the CLOSED interval [entry, exit] — "MAE is
//     max(0, -minimum marked net over entry through exit)"
//     (transcripts/CONVERSATION.md:24086) — so it always includes the entry
//     group's own mark, i.e. the immediate spread-plus-cost drawdown. On the
//     conservative envelope that mark is always negative, so an OK label never
//     reports a zero MAE.
//   * `stop_hit[h]` is the card's "stop before h" (APPENDIX D: "P(stop before
//     h*)"), so the crossing must be STRICTLY BEFORE the horizon's own exit
//     group. When both land on the same group the horizon exit executes there
//     and `stop_hit` is 0. This is also why a stop that fires always has a next
//     lawful mark: the horizon group itself is one.
//   * a horizon that runs past the session's last lawful mark exits at that
//     final mark, exactly as `close` does. The truth leaf (APPENDIX C4) has one
//     `label_state` and no per-horizon availability mask, and the position
//     really does end at the close, so this is the only reading that keeps
//     `menu_net_cent[h]` a realisable number. DECLARED, and raised as a STOP
//     question in the WP7 report.
#ifndef QR_LABELS_LABEL_KERNEL_HPP
#define QR_LABELS_LABEL_KERNEL_HPP

#include <array>
#include <cstdint>
#include <span>
#include <string>
#include <string_view>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_labels/execution_tape.hpp"
#include "qr_labels/money.hpp"
#include "qr_labels/watches.hpp"
#include "qr_replay/action.hpp"

namespace qr::labels {

// ---------------------------------------------------------------------------
// The barrier auxiliary's four raw states and three-class map.
// ---------------------------------------------------------------------------

enum class BarrierState : std::uint8_t {
  FAVORABLE_FIRST = 0,
  ADVERSE_FIRST = 1,
  SAME_GROUP_ADVERSE = 2,
  NEITHER = 3,
};
inline constexpr std::size_t kBarrierStateCount = 4;
[[nodiscard]] const char* barrier_state_name(BarrierState state) noexcept;

/// "the three-class auxiliary maps SAME_GROUP_ADVERSE to ADVERSE_FIRST and
/// NEITHER to CENSORED".
enum class BarrierClass : std::uint8_t { FAVORABLE = 0, ADVERSE = 1, CENSORED = 2 };
inline constexpr std::size_t kBarrierClassCount = 3;
[[nodiscard]] const char* barrier_class_name(BarrierClass value) noexcept;
[[nodiscard]] BarrierClass barrier_three_class(BarrierState state) noexcept;

/// The barrier auxiliary's own row.
struct BarrierOutcome {
  BarrierState state = BarrierState::NEITHER;
  BarrierClass three_class = BarrierClass::CENSORED;
  /// The first favorable / adverse touch index, or `kNoIndex`.
  std::int64_t favorable_index = kNoIndex;
  std::int64_t adverse_index = kNoIndex;
  /// The instant of the first touch of either barrier, or 0.
  std::int64_t first_touch_ts_ns = 0;
};

/// `barrier_order(entry_idx, side, favorable_net_cent, adverse_net_cent)` of
/// card section 3, scanned over full RTH (every lawful mark strictly after
/// entry, through the session's last one).
[[nodiscard]] Expected<BarrierOutcome, Refusal> barrier_order(const SessionLabelIndex& index,
                                                              std::int64_t entry_index, Side side,
                                                              std::int64_t favorable_net_cent,
                                                              std::int64_t adverse_net_cent);

// ---------------------------------------------------------------------------
// THE shared stop_scan primitive.
// ---------------------------------------------------------------------------

/// The wall, scanned ONCE per action row.
struct StopScan {
  /// The wall this scan used, in signed net cents (-30,000 in production).
  std::int64_t wall_net_cent = kStopWallNetCent;
  bool crossed = false;
  /// The first lawful mark strictly after entry whose marked net is at or
  /// below the wall.
  std::int64_t crossing_index = kNoIndex;
  /// "the exit fills at the NEXT lawful mark strictly after crossing": the
  /// crossing index plus one, or `kNoIndex` when the crossing is the session's
  /// final lawful mark.
  std::int64_t exit_index = kNoIndex;
  /// The realised net at the crossing and at the fill. `gap_through_cent` is
  /// how far below the wall the FILL landed (0 when it landed at or above it) —
  /// the card's "gap-through retained and reported".
  std::int64_t crossing_net_cent = 0;
  std::int64_t exit_net_cent = 0;
  std::int64_t gap_through_cent = 0;
  /// The instants of the crossing and of the fill (0 when nothing crossed).
  std::int64_t crossing_ts_ns = 0;
  std::int64_t exit_ts_ns = 0;
};

/// THE ONE PRIMITIVE. Every ledger in this file consumes this result and no
/// other wall knowledge.
[[nodiscard]] Expected<StopScan, Refusal> stop_scan(const SessionLabelIndex& index,
                                                    std::int64_t entry_index,
                                                    std::int64_t entry_u6, Side side,
                                                    std::int64_t wall_net_cent);

// ---------------------------------------------------------------------------
// The label row.
// ---------------------------------------------------------------------------

/// One action row's complete truth record. `menu` is WP11's own struct, filled
/// here (brief: "conform to qr_replay's ScoredAction/LabelRow structs where
/// they overlap"); the certificate and barrier columns sit beside it because
/// the economic replay never reads them ("Certificate quantities are
/// NONPROMOTABLE for economics and never gate anything in section 6").
struct LabelRow {
  qr::replay::LabelRow menu{};

  /// The fill: the entry group's index on the lawful-mark tape, its
  /// conservative fill price, and the number of lawful marks that followed it.
  std::int64_t entry_index = kNoIndex;
  std::int64_t entry_u6 = 0;

  /// The co-primary certificate.
  std::int64_t certificate_net_cent = 0;
  std::int64_t certificate_mae_cent = 0;
  std::int64_t certificate_exit_ts_ns = 0;
  std::int64_t certificate_exit_index = kNoIndex;

  /// The shared scan's own report (the gap-through panel reads it).
  StopScan scan{};
  BarrierOutcome barrier{};

  [[nodiscard]] LabelState state() const noexcept { return menu.state; }
};

/// THE KERNEL. APPENDIX C5 names it `label_action(QuoteGroups&, ActionKey,
/// Side)`; the first argument is `SessionLabelIndex` for the reason stated at
/// the top of execution_tape.hpp (a `QuoteGroups` cannot answer `ask_max` or
/// `bid_min`, and the barrier needs the favorable extrema too). Every other
/// element of the signature is the design's, including the return type.
///
/// `wall_net_cent` exists only so the APPENDIX C5 stop-shift mutant can move
/// the wall; production callers use the default, which is the card's -30,000.
[[nodiscard]] Expected<LabelRow, Refusal> label_action(const SessionLabelIndex& index,
                                                       ActionKey key, Side side,
                                                       std::int64_t wall_net_cent =
                                                           kStopWallNetCent);

/// Labels every action row of a session, in the plan's own chronological
/// order. Refuses on the first row that refuses: a session with one unlabelled
/// action row is not a session with a hole in it, it is a refused session.
[[nodiscard]] Expected<std::vector<LabelRow>, Refusal> label_session(
    const SessionLabelIndex& index, std::span<const ActionRow> actions,
    std::int64_t wall_net_cent = kStopWallNetCent);

/// Typed per-session counters of the label pass; printed in full, zeros
/// included.
struct LabelCensus {
  std::int64_t rows = 0;
  std::array<std::int64_t, 3> per_state{};  ///< OK / ENTRY_UNAVAILABLE / EXIT_UNAVAILABLE
  std::array<std::int64_t, kHorizonCount> stop_hit{};
  std::array<std::int64_t, kBarrierStateCount> barrier_state{};
  std::int64_t gap_through_rows = 0;
  std::int64_t certificate_positive_rows = 0;
  void observe(const LabelRow& row);
  [[nodiscard]] std::string to_tsv(std::string_view label) const;
};

/// Deterministic field-by-field rendering of the label rows (the artifact
/// two-run identity is asserted on these bytes).
[[nodiscard]] std::string render_label_rows(std::span<const LabelRow> rows);

/// Field-by-field little-endian serialization of one label row: the byte
/// string the two-run identity fixtures compare.
void append_serialized(const LabelRow& row, std::vector<std::uint8_t>& out);

}  // namespace qr::labels

#endif  // QR_LABELS_LABEL_KERNEL_HPP
