// qr_wave2/tests/wave2_test_support.hpp — hand-built sessions for the wave-2
// fixtures. Payload-free: every series here is written by hand, so a fixture
// asserts a formula rather than a corpus.
#ifndef QR_WAVE2_TESTS_SUPPORT_HPP
#define QR_WAVE2_TESTS_SUPPORT_HPP

#include <cstdint>
#include <string_view>
#include <utility>
#include <vector>

#include "qr_carriers/grid_1s.hpp"
#include "qr_carriers/streams.hpp"
#include "qr_clock/session_clock.hpp"
#include "qr_registry/registry.hpp"
#include "qr_wave2/prior_state.hpp"

namespace qr::wave2::testing {

/// Session 125 — the one authorized development session, used here only for its
/// CLOCK (the grid needs a real session span; no payload is opened).
inline constexpr std::string_view kSession125Day = "2022-07-05";

inline const Registry& registry() {
  static const Registry loaded = [] {
    auto result = Registry::load_embedded();
    if (!result.has_value()) {
      detail::fail_fast("wave2 fixtures: the embedded registry failed its digest gate");
    }
    return std::move(result).value();
  }();
  return loaded;
}

inline const SessionClock& clock_125() {
  static const SessionClock built = [] {
    auto date = CivilDate::parse_ymd(kSession125Day);
    if (!date.has_value()) {
      detail::fail_fast("wave2 fixtures: session-125 day is not a canonical civil date");
    }
    auto clock = SessionClock::for_day(registry(), date.value());
    if (!clock.has_value()) {
      detail::fail_fast("wave2 fixtures: the registry refused session 125");
    }
    return std::move(clock).value();
  }();
  return built;
}

/// One eligible NBBO group at `offset_seconds` after the open, carrying `mid_u6`.
inline carriers::NbboStream::EligibleMid eligible_mid(std::int64_t offset_seconds,
                                                      std::int64_t mid_u6) {
  carriers::NbboStream::EligibleMid mid;
  mid.ts_ns_a = clock_125().session_start_a().ns() + offset_seconds * carriers::kNanosPerSecond;
  mid.mid_u6 = mid_u6;
  mid.spread_u6 = 10'000;
  return mid;
}

/// A grid built from a hand-written midpoint path: `mids[i]` is the eligible
/// midpoint posted `i` seconds after the session start (so endpoint `i+1`
/// carries it — the grid reads STRICTLY BEFORE its endpoint).
inline carriers::MidpointGrid grid_from_path(const std::vector<std::int64_t>& mids) {
  std::vector<carriers::NbboStream::EligibleMid> eligible;
  eligible.reserve(mids.size());
  for (std::size_t index = 0; index < mids.size(); ++index) {
    eligible.push_back(eligible_mid(static_cast<std::int64_t>(index), mids[index]));
  }
  auto grid = carriers::MidpointGrid::build(clock_125(), eligible);
  if (!grid.has_value()) {
    detail::fail_fast("wave2 fixtures: the grid refused a hand-built path");
  }
  return std::move(grid).value();
}

/// A flat path of `seconds` identical midpoints — zero returns everywhere, so
/// B is driven entirely by RV_prior and every arithmetic is hand-checkable.
inline std::vector<std::int64_t> flat_path(std::size_t seconds, std::int64_t mid_u6) {
  return std::vector<std::int64_t>(seconds, mid_u6);
}

/// A summary with the four levels and a variance total set by hand.
inline SessionSummary summary_of(std::int64_t ordinal, std::int64_t high_u6, std::int64_t low_u6,
                                 std::int64_t close_u6, std::int64_t vwap_u6,
                                 double rth_sum_r2 = 0.0, std::int64_t rth_seconds = 23400) {
  SessionSummary summary;
  summary.ordinal = ordinal;
  summary.high_u6 = high_u6;
  summary.low_u6 = low_u6;
  summary.close_u6 = close_u6;
  summary.grid_present = true;
  summary.vwap_u6 = vwap_u6;
  summary.vwap_present = true;
  summary.rth_sum_r2 = rth_sum_r2;
  summary.rth_seconds = rth_seconds;
  summary.valid_steps = rth_seconds;
  return summary;
}

/// `count` identical prior sessions, so a window's arithmetic is exact.
inline PriorSessionHistory history_of(std::int64_t count, std::int64_t high_u6,
                                      std::int64_t low_u6, std::int64_t close_u6,
                                      std::int64_t vwap_u6, double rth_sum_r2 = 0.0) {
  PriorSessionHistory history;
  for (std::int64_t ordinal = 0; ordinal < count; ++ordinal) {
    const auto observed =
        history.observe(summary_of(ordinal, high_u6, low_u6, close_u6, vwap_u6, rth_sum_r2));
    if (!observed.has_value()) {
      detail::fail_fast("wave2 fixtures: the history refused a hand-built summary");
    }
  }
  return history;
}

}  // namespace qr::wave2::testing

#endif  // QR_WAVE2_TESTS_SUPPORT_HPP
