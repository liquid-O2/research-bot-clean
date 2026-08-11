// qr_m25/tests/m25_test_support.hpp — hand-built tapes for the arithmetic
// fixtures, and a published-shard builder for the round-trip fixtures.
#ifndef QR_M25_TEST_SUPPORT_HPP
#define QR_M25_TEST_SUPPORT_HPP

#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

#include "qr_emit/shard_writer.hpp"
#include "qr_m25/tape.hpp"
#include "qr_replay/action.hpp"

namespace qr::m25::test {

inline constexpr std::int64_t kNs = 1000000000;
inline constexpr std::int64_t kStart = 1657027800000000000;

/// One hand-specified action: which clock, which side, the net at EVERY horizon,
/// and how long it is held.
struct Spec {
  std::int64_t clock = 0;          ///< clock index; decision_ts = kStart + clock * spacing
  bool is_long = true;
  std::int64_t net_cent = 0;       ///< the same net at every horizon (hand arithmetic)
  std::int64_t hold_seconds = 60;  ///< exit = entry + hold, at every horizon
  bool available = true;           ///< false => ENTRY_UNAVAILABLE
  bool stopped = false;
  std::int64_t gap_through_cent = 0;
  /// Per-horizon step added to `net_cent` at horizon h: zero keeps every horizon
  /// identical (what the hand arithmetic wants), non-zero makes the REPLAYED
  /// horizon observable in the result (what the horizon fixtures want).
  std::int64_t net_step_per_horizon = 0;
};

/// Build a SessionTape directly (no files): the arithmetic fixtures need exact
/// control of every number, and the loader is exercised by the round-trip
/// fixtures instead.
inline SessionTape make_tape(std::int64_t ordinal, std::int32_t year,
                             const std::vector<Spec>& specs, std::int64_t spacing_seconds = 60) {
  SessionTape tape;
  tape.session_ordinal = ordinal;
  tape.year = year;
  tape.day = std::to_string(year) + "-01-03";
  for (const Spec& spec : specs) {
    qr::replay::ScoredAction action;
    action.key.session_ordinal = ordinal;
    action.key.decision_ordinal = spec.clock;
    action.key.decision_ts_ns = kStart + spec.clock * spacing_seconds * kNs;
    action.key.side = spec.is_long ? qr::replay::Side::LONG : qr::replay::Side::SHORT;
    action.legal_enter = true;
    action.label.key = action.key;
    action.label.state =
        spec.available ? qr::replay::LabelState::OK : qr::replay::LabelState::ENTRY_UNAVAILABLE;
    action.label.entry_ts_ns = action.key.decision_ts_ns + kNs;
    action.label.gap_through_cent = spec.gap_through_cent;
    action.label.cost_charged_cent = qr::replay::kTradeCostCent;
    for (std::size_t h = 0; h < qr::replay::kHorizonCount; ++h) {
      const std::int64_t net =
          spec.net_cent + static_cast<std::int64_t>(h) * spec.net_step_per_horizon;
      action.label.menu_net_cent[h] = net;
      action.label.menu_mae_cent[h] = net < 0 ? -net + 6 : 6;
      action.label.menu_exit_ts[h] = action.label.entry_ts_ns + spec.hold_seconds * kNs;
      action.label.stop_hit[h] = spec.stopped ? 1 : 0;
    }
    tape.rows.push_back(action);
    if (spec.is_long) {
      ++tape.long_rows;
    } else {
      ++tape.short_rows;
    }
    if (spec.available) {
      ++tape.label_ok_rows;
    } else {
      ++tape.label_entry_unavailable_rows;
    }
  }
  std::sort(tape.rows.begin(), tape.rows.end(),
            [](const qr::replay::ScoredAction& a, const qr::replay::ScoredAction& b) {
              if (a.key.decision_ts_ns != b.key.decision_ts_ns) {
                return a.key.decision_ts_ns < b.key.decision_ts_ns;
              }
              return static_cast<std::int64_t>(a.key.side) > static_cast<std::int64_t>(b.key.side);
            });
  for (std::size_t i = 0; i < tape.rows.size(); ++i) {
    if (i == 0 || tape.rows[i].key.decision_ts_ns != tape.rows[i - 1].key.decision_ts_ns) {
      tape.clock_starts.push_back(i);
    }
  }
  return tape;
}

/// Publish a minimal but LAWFUL shard pair for one session, from hand specs, so
/// the loader/round-trip fixtures read real published bytes.
Status publish_specs(const std::filesystem::path& run_dir, std::int64_t ordinal,
                     const std::string& day, const std::vector<Spec>& specs,
                     std::int64_t spacing_seconds = 60,
                     const std::vector<float>* prefix_long = nullptr,
                     const std::vector<float>* prefix_short = nullptr);

}  // namespace qr::m25::test

#endif  // QR_M25_TEST_SUPPORT_HPP
