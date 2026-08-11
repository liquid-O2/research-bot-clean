// qr_carriers/src/location.cpp — the 16 location/clock values.
#include "qr_carriers/location.hpp"

#include <algorithm>
#include <cmath>

namespace qr::carriers {
namespace {

constexpr std::array<const char*, kLocationValueCount> kNames{
    "SESSION_TIME_FRACTION",
    "SESSION_TIME_SINE",
    "SESSION_TIME_COSINE",
    "SECONDS_TO_CLOSE_FRACTION",
    "EARLY_CLOSE_BIT",
    "ORIENTED_BPS_FROM_OPEN",
    "ORIENTED_BPS_FROM_RUNNING_HIGH",
    "ORIENTED_BPS_FROM_RUNNING_LOW",
    "RUNNING_RANGE_BPS",
    "ORIENTED_BPS_FROM_PREFIX_VWAP",
    "PREFIX_RV_1S",
    "PREFIX_RV_5S",
    "PREFIX_RV_30S",
    "CURRENT_SPREAD_BPS",
    "LOG1P_SECONDS_SINCE_LAST_STOCK_PRINT",
    "LOG1P_SECONDS_SINCE_LAST_OPTION_PRINT",
};

/// Index of the last element with `ts_ns_a < cutoff`, or absent.
template <class Element, class Project>
[[nodiscard]] std::optional<std::size_t> last_strictly_before(std::span<const Element> elements,
                                                              std::int64_t cutoff_ns_a,
                                                              Project project) {
  const auto found = std::lower_bound(
      elements.begin(), elements.end(), cutoff_ns_a,
      [&project](const Element& element, std::int64_t bound) { return project(element) < bound; });
  const std::size_t index = static_cast<std::size_t>(found - elements.begin());
  if (index == 0) {
    return std::nullopt;
  }
  return index - 1U;
}

}  // namespace

const char* location_value_name(std::size_t index) noexcept {
  if (index >= kLocationValueCount) {
    detail::fail_fast("qr::carriers::location_value_name: index out of range");
  }
  return kNames[index];
}

bool location_value_is_continuous(std::size_t index) noexcept {
  return index != kLocEarlyCloseBit;
}

LocationBuilder::LocationBuilder(const LocationInputs& inputs)
    : clock_(inputs.clock),
      grid_(inputs.grid),
      eligible_mids_(inputs.eligible_mids),
      stock_print_groups_(inputs.stock_print_groups),
      option_print_groups_(inputs.option_print_groups),
      vwap_notional_prefix_(inputs.vwap_notional_prefix),
      vwap_size_prefix_(inputs.vwap_size_prefix) {
  if (clock_ == nullptr || grid_ == nullptr) {
    detail::fail_fast("qr::carriers::LocationBuilder: null clock or grid");
  }
  running_high_.resize(eligible_mids_.size());
  running_low_.resize(eligible_mids_.size());
  for (std::size_t index = 0; index < eligible_mids_.size(); ++index) {
    const std::int64_t mid = eligible_mids_[index].mid_u6;
    running_high_[index] = index == 0 ? mid : std::max(running_high_[index - 1U], mid);
    running_low_[index] = index == 0 ? mid : std::min(running_low_[index - 1U], mid);
  }
}

Expected<LocationRow, Refusal> LocationBuilder::build(std::int64_t cutoff_ns_a, Side side) const {
  LocationRow row;
  const double sigma = sigma_of(side);
  const std::int64_t open_ns = clock_->session_start_a().ns();
  const std::int64_t close_ns = clock_->session_end_a().ns();
  const double span = static_cast<double>(close_ns - open_ns);

  // --- 0..4: the five pure clock values (always present) ------------------------
  const double elapsed = static_cast<double>(cutoff_ns_a - open_ns);
  const double session_fraction = span > 0.0 ? elapsed / span : 0.0;
  row.set(kLocSessionTimeFraction, present(session_fraction));
  // ORCHESTRATOR RULING (2026-08-10): "its sine/cosine" is the CYCLICAL
  // encoding sin(2*pi*f) / cos(2*pi*f). Bare sin(f) on a fraction in [0,1] is
  // near-linear and carries no more information than f itself, which is not
  // what a sine/cosine pair is for.
  const double session_angle = kTwoPi * session_fraction;
  row.set(kLocSessionTimeSine, present(std::sin(session_angle)));
  row.set(kLocSessionTimeCosine, present(std::cos(session_angle)));
  row.set(kLocSecondsToCloseFraction,
          present(span > 0.0 ? static_cast<double>(close_ns - cutoff_ns_a) / span : 0.0));
  row.set(kLocEarlyCloseBit, structural_bit(clock_->expected_bar_count() != kRegularBarCount));

  // --- the prefix midpoint anchor `m` and the open/high/low ----------------------
  const auto mid_index = last_strictly_before<NbboStream::EligibleMid>(
      eligible_mids_, cutoff_ns_a,
      [](const NbboStream::EligibleMid& element) { return element.ts_ns_a; });

  const auto oriented_distance = [&](std::size_t column, std::int64_t reference)
      -> Expected<bool, Refusal> {
    const auto bps = displacement_bps_value(eligible_mids_[*mid_index].mid_u6 - reference,
                                            reference);
    if (!bps.has_value()) {
      return Expected<bool, Refusal>::refuse(bps.error());
    }
    const Typed<double> value = bps.value();
    row.set(column, value.v == Validity::VALID
                        ? (value.value == 0.0 ? present(0.0) : present(value.value * sigma))
                        : masked(value.v));
    return true;
  };

  if (!mid_index.has_value()) {
    row.set(kLocOrientedBpsFromOpen, masked(Validity::MISSING));
    row.set(kLocOrientedBpsFromRunningHigh, masked(Validity::MISSING));
    row.set(kLocOrientedBpsFromRunningLow, masked(Validity::MISSING));
    row.set(kLocRunningRangeBps, masked(Validity::MISSING));
    row.set(kLocOrientedBpsFromPrefixVwap, masked(Validity::MISSING));
    row.set(kLocCurrentSpreadBps, masked(Validity::MISSING));
  } else {
    const std::int64_t open_mid = eligible_mids_[0].mid_u6;
    const std::int64_t high = running_high_[*mid_index];
    const std::int64_t low = running_low_[*mid_index];
    const auto from_open = oriented_distance(kLocOrientedBpsFromOpen, open_mid);
    if (!from_open.has_value()) {
      return Expected<LocationRow, Refusal>::refuse(from_open.error());
    }
    const auto from_high = oriented_distance(kLocOrientedBpsFromRunningHigh, high);
    if (!from_high.has_value()) {
      return Expected<LocationRow, Refusal>::refuse(from_high.error());
    }
    const auto from_low = oriented_distance(kLocOrientedBpsFromRunningLow, low);
    if (!from_low.has_value()) {
      return Expected<LocationRow, Refusal>::refuse(from_low.error());
    }
    // "range is `(high-low)*10000/open`" — not oriented, by its own formula.
    const auto range = displacement_bps_value(high - low, open_mid);
    if (!range.has_value()) {
      return Expected<LocationRow, Refusal>::refuse(range.error());
    }
    row.set(kLocRunningRangeBps, range.value());

    // "spread ... use[s] only strict-prior observations": the spread of the same
    // last eligible group that supplied `m`.
    const auto spread = displacement_bps_value(eligible_mids_[*mid_index].spread_u6,
                                               eligible_mids_[*mid_index].mid_u6);
    if (!spread.has_value()) {
      return Expected<LocationRow, Refusal>::refuse(spread.error());
    }
    row.set(kLocCurrentSpreadBps, spread.value());

    // --- prefix VWAP -------------------------------------------------------------
    const auto vwap_group = last_strictly_before<GroupRecord>(
        stock_print_groups_, cutoff_ns_a,
        [](const GroupRecord& group) { return group.ts_ns_a; });
    if (!vwap_group.has_value() || vwap_size_prefix_.empty() ||
        vwap_size_prefix_[*vwap_group] <= 0) {
      row.set(kLocOrientedBpsFromPrefixVwap, masked(Validity::MISSING));
    } else {
      const std::int64_t vwap_u6 =
          vwap_notional_prefix_[*vwap_group] / vwap_size_prefix_[*vwap_group];
      const auto from_vwap = oriented_distance(kLocOrientedBpsFromPrefixVwap, vwap_u6);
      if (!from_vwap.has_value()) {
        return Expected<LocationRow, Refusal>::refuse(from_vwap.error());
      }
    }
  }

  // --- 10..12: prefix RV on the prior complete 1s grid ----------------------------
  {
    const auto endpoint = grid_->prefix_endpoint(cutoff_ns_a);
    const std::array<std::pair<std::size_t, std::int64_t>, 3> horizons{
        std::make_pair(static_cast<std::size_t>(kLocPrefixRv1s), std::int64_t{1}),
        std::make_pair(static_cast<std::size_t>(kLocPrefixRv5s), std::int64_t{5}),
        std::make_pair(static_cast<std::size_t>(kLocPrefixRv30s), std::int64_t{30})};
    for (const auto& horizon : horizons) {
      row.set(horizon.first, endpoint.has_value()
                                 ? grid_->realized_volatility(*endpoint, horizon.second)
                                 : masked(Validity::MISSING));
    }
  }

  // --- 14/15: the two last-print ages, in SECONDS (section 5's own unit) ----------
  {
    const std::array<std::pair<std::size_t, std::span<const GroupRecord>>, 2> streams{
        std::make_pair(static_cast<std::size_t>(kLocLog1pSecondsSinceLastStockPrint),
                       stock_print_groups_),
        std::make_pair(static_cast<std::size_t>(kLocLog1pSecondsSinceLastOptionPrint),
                       option_print_groups_)};
    for (const auto& entry : streams) {
      const auto last = last_strictly_before<GroupRecord>(
          entry.second, cutoff_ns_a, [](const GroupRecord& group) { return group.ts_ns_a; });
      if (!last.has_value()) {
        row.set(entry.first, masked(Validity::MISSING));
        continue;
      }
      const auto micros = duration_micros(entry.second[*last].ts_ns_a, cutoff_ns_a);
      if (!micros.has_value()) {
        return Expected<LocationRow, Refusal>::refuse(micros.error());
      }
      row.set(entry.first, time_log1p_seconds(micros.value()));
    }
  }
  return row;
}

}  // namespace qr::carriers
