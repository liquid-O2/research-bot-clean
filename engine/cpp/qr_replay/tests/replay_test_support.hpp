// qr_replay/tests/replay_test_support.hpp — builders for hand-written tapes.
//
// The fixtures in this suite are ARITHMETIC, so the builder's job is to make the
// arithmetic visible: a spec names a clock, a side, two predictions, and the
// label marks AT THE HORIZON UNDER TEST. Every other horizon of the menu is
// filled with a loud sentinel (a net of -777,700 - h cents), so a kernel that
// reads the wrong horizon does not quietly produce a plausible number.
#ifndef QR_REPLAY_TESTS_SUPPORT_HPP
#define QR_REPLAY_TESTS_SUPPORT_HPP

#include <cstdint>
#include <vector>

#include "qr_replay/action.hpp"

namespace qr::replay::test {

inline constexpr std::int64_t kSecondNs = 1000000000LL;
inline constexpr std::int64_t kMinuteNs = 60LL * kSecondNs;

/// Sentinel net for every horizon that is NOT under test.
inline constexpr std::int64_t kWrongHorizonSentinelNet = -777700;

/// One row of a hand-written tape.
struct ActionSpec {
  std::int64_t decision_ordinal = 0;
  std::int64_t decision_ts_ns = 0;
  Side side = Side::LONG;
  double predicted_net_h_star = 0.0;
  double predicted_stop_prob_h_ref = 0.0;
  bool legal = true;

  LabelState state = LabelState::OK;
  std::int64_t fill_delay_ns = kSecondNs;       ///< entry_ts = decision_ts + this.
  std::int64_t hold_ns = 15 * kMinuteNs;        ///< exit_ts = entry_ts + this (horizon under test).
  std::int64_t net_cent = 0;                    ///< NET of the 576c, which the label kernel charged.
  std::int64_t mae_cent = 0;
  bool stop_hit = false;
  /// How far past the wall the stop's fill landed (0 = it came back to it).
  /// Per ROW, not per horizon: one shared stop_scan, one gap-through.
  std::int64_t gap_through_cent = 0;
};

/// Build one ScoredAction for `session_ordinal` at horizon `h`.
inline ScoredAction make_action(std::int64_t session_ordinal, const ActionSpec& spec, std::size_t h) {
  ScoredAction action;
  action.key.session_ordinal = session_ordinal;
  action.key.decision_ordinal = spec.decision_ordinal;
  action.key.decision_ts_ns = spec.decision_ts_ns;
  action.key.side = spec.side;
  action.predicted_net_h_star = spec.predicted_net_h_star;
  action.predicted_stop_prob_h_ref = spec.predicted_stop_prob_h_ref;
  action.legal_enter = spec.legal;

  LabelRow& label = action.label;
  label.key = action.key;
  label.state = spec.state;
  label.cost_charged_cent = kTradeCostCent;

  if (spec.state == LabelState::OK) {
    label.entry_ts_ns = spec.decision_ts_ns + spec.fill_delay_ns;
    for (std::size_t i = 0; i < kHorizonCount; ++i) {
      label.menu_net_cent[i] = kWrongHorizonSentinelNet - static_cast<std::int64_t>(i);
      label.menu_mae_cent[i] = 0;
      label.menu_exit_ts[i] = label.entry_ts_ns + static_cast<std::int64_t>(i + 1) * kMinuteNs;
      label.stop_hit[i] = 0;
    }
    label.menu_net_cent[h] = spec.net_cent;
    label.menu_mae_cent[h] = spec.mae_cent;
    label.menu_exit_ts[h] = label.entry_ts_ns + spec.hold_ns;
    label.stop_hit[h] = spec.stop_hit ? 1 : 0;
    label.gap_through_cent = spec.gap_through_cent;
  } else {
    // An unavailable label carries no marks at all: if the kernel ever reads
    // them it gets zeros, and a zero-net trade is loudly wrong in the ledger.
    label.entry_ts_ns = 0;
  }
  return action;
}

/// Build a whole session tape.
inline std::vector<ScoredAction> make_tape(std::int64_t session_ordinal,
                                           const std::vector<ActionSpec>& specs, std::size_t h) {
  std::vector<ScoredAction> tape;
  tape.reserve(specs.size());
  for (const ActionSpec& spec : specs) {
    tape.push_back(make_action(session_ordinal, spec, h));
  }
  return tape;
}

}  // namespace qr::replay::test

#endif  // QR_REPLAY_TESTS_SUPPORT_HPP
