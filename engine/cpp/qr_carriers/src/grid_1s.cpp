// qr_carriers/src/grid_1s.cpp — the prefix 1s midpoint grid.
#include "qr_carriers/grid_1s.hpp"

#include <cmath>

namespace qr::carriers {

Expected<MidpointGrid, Refusal> MidpointGrid::build(
    const SessionClock& clock, std::span<const NbboStream::EligibleMid> eligible) {
  MidpointGrid grid;
  grid.session_start_ns_ = clock.session_start_a().ns();
  const std::size_t endpoints =
      static_cast<std::size_t>(clock.expected_bar_count() * 60) + 1U;
  grid.points_.assign(endpoints, GridPoint{});

  // One forward walk: for endpoint i, advance the source cursor over every
  // eligible group STRICTLY BEFORE it, then carry the last one. The carry has no
  // timeout, so the cursor never rewinds and never expires.
  std::size_t cursor = 0;
  bool have_source = false;
  std::int64_t carried_mid = 0;
  std::int64_t carried_ts = 0;
  for (std::size_t index = 0; index < endpoints; ++index) {
    const std::int64_t endpoint = grid.endpoint_ns(index);
    while (cursor < eligible.size() && eligible[cursor].ts_ns_a < endpoint) {
      have_source = true;
      carried_mid = eligible[cursor].mid_u6;
      carried_ts = eligible[cursor].ts_ns_a;
      ++cursor;
    }
    if (!have_source) {
      continue;  // "before the first valid quote it is missing"
    }
    const auto age = duration_micros(carried_ts, endpoint);
    if (!age.has_value()) {
      return Expected<MidpointGrid, Refusal>::refuse(age.error());
    }
    GridPoint& point = grid.points_[index];
    point.present = true;
    point.mid_u6 = carried_mid;
    point.age_micros = age.value();
    point.fresh_in_bin = carried_ts >= endpoint - kNanosPerSecond;
    point.stale_gt_1s = age.value() > kMicrosPerSecond;
  }
  return grid;
}

std::optional<std::size_t> MidpointGrid::prefix_endpoint(std::int64_t cutoff_ns_a) const noexcept {
  if (points_.empty() || cutoff_ns_a < session_start_ns_) {
    return std::nullopt;
  }
  const std::int64_t index = (cutoff_ns_a - session_start_ns_) / kNanosPerSecond;
  if (index < 0) {
    return std::nullopt;
  }
  // "Absent when the cutoff is ... past the grid" — and the grid's LAST endpoint
  // is the session close, which the card makes a terminal endpoint and "never a
  // decision instant". So a cutoff standing on the close is already past every
  // endpoint a decision may read, and the answer is ABSENT.
  //
  // WHY NOT CLAMP. Returning `points_.size() - 1` for an out-of-range cutoff is
  // a range-limiting guard handing back a VALUE where the contract says nullopt,
  // and the value it hands back is the close's own carried midpoint: a caller
  // asking about an instant off the grid would silently receive the session's
  // last RV instead of a mask.
  if (static_cast<std::size_t>(index) + 1U >= points_.size()) {
    return std::nullopt;
  }
  return static_cast<std::size_t>(index);
}

Typed<double> MidpointGrid::realized_volatility(std::size_t endpoint_index,
                                                std::int64_t seconds) const noexcept {
  if (endpoint_index >= points_.size() || seconds <= 0) {
    return masked(Validity::MISSING);
  }
  const std::size_t span = static_cast<std::size_t>(seconds);
  const std::size_t first = endpoint_index >= span ? endpoint_index - span : 0U;
  double sum_squares = 0.0;
  std::int64_t pairs = 0;
  for (std::size_t index = first + 1U; index <= endpoint_index; ++index) {
    const GridPoint& previous = points_[index - 1U];
    const GridPoint& current = points_[index];
    if (!previous.present || !current.present || previous.mid_u6 <= 0 || current.mid_u6 <= 0) {
      continue;
    }
    // A carried unchanged midpoint gives log(1) = 0 and contributes nothing.
    const double ratio =
        static_cast<double>(current.mid_u6) / static_cast<double>(previous.mid_u6);
    const double logret = std::log(ratio);
    sum_squares += logret * logret;
    ++pairs;
  }
  if (pairs <= 0) {
    return masked(Validity::MISSING);  // "fewer than two valid points"
  }
  return present(std::sqrt(sum_squares));
}

MidpointGrid::Census MidpointGrid::census() const noexcept {
  Census out;
  out.endpoints = static_cast<std::int64_t>(points_.size());
  for (std::size_t index = 0; index < points_.size(); ++index) {
    const GridPoint& point = points_[index];
    if (!point.present) {
      continue;
    }
    if (out.first_present_endpoint < 0) {
      out.first_present_endpoint = static_cast<std::int64_t>(index);
    }
    ++out.present;
    if (point.fresh_in_bin) {
      ++out.fresh_in_bin;
    }
    if (point.stale_gt_1s) {
      ++out.stale_gt_1s;
    }
  }
  return out;
}

}  // namespace qr::carriers
