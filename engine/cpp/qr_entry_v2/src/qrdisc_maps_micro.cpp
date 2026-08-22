// qrdisc native family: `_event_micro_map` (discretionary_features.py:1897),
// emitted once per horizon exactly as feature_map:2487-2494 calls it.
//
// The family seam is the SEVEN calls, not one: feature_map loops the horizons
// and merges each dict in turn, so the block of names this file emits is what
// the row actually contains, and the ratios at :2506 read those names back.
//
// Every float reduction here is either integer-exact, one of the median or
// quantile kernels qrdisc_np_kernels.cpp proves against numpy 2.1.2, or
// delegated to numpy through qrdisc_kernels_events.hpp.  Nothing is
// re-derived.
#include <algorithm>
#include <cmath>
#include <string>
#include <vector>

#include "qr_entry_v2/qrdisc_kernels_events.hpp"
#include "qr_entry_v2/qrdisc_maps.hpp"
#include "qr_entry_v2/qrdisc_np_kernels.hpp"

namespace {

constexpr std::int64_t kNanosPerSecond = 1000000000;

// The horizons of feature_map:2487, in its order.
const std::int64_t kQrdiscEventHorizons[7] = {1, 5, 15, 30, 60, 120, 300};

// `array.sum(dtype=np.int64)`: exact, and overflow WRAPS as numpy's int64
// accumulator does (C++ signed overflow is UB, so it runs unsigned).
std::int64_t qrdisc_sum_i64(const std::vector<std::int64_t>& values) {
  std::uint64_t running = 0;
  for (const std::int64_t value : values) {
    running += static_cast<std::uint64_t>(value);
  }
  return static_cast<std::int64_t>(running);
}

// `np.diff(ts).astype(np.float64) / 1e6`.
std::vector<double> qrdisc_gaps_ms(const std::vector<std::int64_t>& ts) {
  std::vector<double> gaps;
  if (ts.size() < 2) return gaps;
  gaps.reserve(ts.size() - 1);
  for (std::size_t index = 1; index < ts.size(); ++index) {
    gaps.push_back(static_cast<double>(ts[index] - ts[index - 1]) / 1e6);
  }
  return gaps;
}

double qrdisc_ratio_or_zero(double numerator, double denominator) {
  return denominator != 0.0 ? numerator / denominator : 0.0;
}

}  // namespace

bool qrdisc_event_micro_map(QrdiscPlaneObject* plane, const QrdiscRowInputs& row,
                            QrdiscValueMap* out) {
  std::int64_t formation_ts_ns = 0;
  if (!qrdisc_mapping_int64(row.formation_candidate, "decision_ts_ns",
                            &formation_ts_ns)) {
    return false;
  }
  for (const std::int64_t horizon : kQrdiscEventHorizons) {
    const std::int64_t left_ns =
        std::max(formation_ts_ns, row.snapshot_ts_ns - horizon * kNanosPerSecond);
    const std::int64_t right_ns = row.snapshot_ts_ns;
    QrdiscEventStreams streams;
    if (!qrdisc_event_streams(plane, row.formation_tick, 2, left_ns, right_ns,
                              row.side, &streams)) {
      return false;
    }
    const std::vector<std::int64_t>& attack_ts = streams.attack.ts;
    const std::vector<std::int64_t>& attack_size = streams.attack.first;
    const std::vector<std::int64_t>& lift_ts = streams.lift.ts;
    const std::vector<std::int64_t>& lift_size = streams.lift.first;
    const std::vector<std::int64_t>& reload_ts = streams.reload.ts;
    const std::vector<std::int64_t>& latency = streams.reload.first;
    const std::vector<std::int64_t>& reload_size = streams.reload.second;
    const std::vector<std::int64_t>& pull_ts = streams.pull.ts;
    const std::vector<std::int64_t>& lifetime = streams.pull.first;
    const std::vector<std::int64_t>& pull_size = streams.pull.second;

    const double width_sec =
        std::max(1e-9, static_cast<double>(right_ns - left_ns) / 1e9);
    std::vector<double> attack_gap = qrdisc_gaps_ms(attack_ts);
    std::vector<double> lift_gap = qrdisc_gaps_ms(lift_ts);
    const std::int64_t midpoint =
        left_ns + qrdisc_floor_div(right_ns - left_ns, 2);
    std::int64_t attack_first = 0;
    for (const std::int64_t timestamp : attack_ts) {
      if (timestamp < midpoint) ++attack_first;
    }
    const std::int64_t attack_second =
        static_cast<std::int64_t>(attack_ts.size()) - attack_first;
    bool ordered = false;
    if (!attack_ts.empty() && !reload_ts.empty() && !lift_ts.empty()) {
      const QrdiscI64Span attack_span{
          attack_ts.data(), static_cast<std::int64_t>(attack_ts.size())};
      const QrdiscI64Span lift_span{
          lift_ts.data(), static_cast<std::int64_t>(lift_ts.size())};
      for (const std::int64_t reload_time : reload_ts) {
        if (qrdisc_searchsorted_left_i64(attack_span, reload_time) > 0 &&
            qrdisc_searchsorted_right_i64(lift_span, reload_time) <
                lift_span.count) {
          ordered = true;
          break;
        }
      }
    }

    const std::int64_t attack_volume = qrdisc_sum_i64(attack_size);
    const std::int64_t reload_volume = qrdisc_sum_i64(reload_size);
    double attack_mean = 0.0;
    if (!attack_size.empty() &&
        !qrdisc_np_mean_i64(attack_size.data(),
                            static_cast<std::int64_t>(attack_size.size()),
                            &attack_mean)) {
      return false;
    }
    double lift_mean = 0.0;
    if (!lift_size.empty() &&
        !qrdisc_np_mean_i64(lift_size.data(),
                            static_cast<std::int64_t>(lift_size.size()),
                            &lift_mean)) {
      return false;
    }
    // The median/quantile kernels REORDER their scratch, so each gets its own
    // copy; `latency` and `lifetime` are int64 and cross to double first,
    // which is what numpy's own quantile does with an integer array.
    std::vector<double> latency_scratch(latency.begin(), latency.end());
    std::vector<std::int64_t> latency_median_scratch(latency);
    std::vector<std::int64_t> lifetime_scratch(lifetime);
    std::vector<double> attack_gap_median_scratch(attack_gap);
    std::vector<double> lift_gap_scratch(lift_gap);

    const std::string prefix = "disc_evt_h" + std::to_string(horizon) + "_";
    out->emplace_back(prefix + "attack_event_count",
                      static_cast<double>(attack_ts.size()));
    out->emplace_back(prefix + "attack_event_rate",
                      static_cast<double>(attack_ts.size()) / width_sec);
    out->emplace_back(prefix + "attack_volume",
                      static_cast<double>(attack_volume));
    out->emplace_back(prefix + "attack_mean_size", attack_mean);
    out->emplace_back(
        prefix + "attack_max_size",
        attack_size.empty()
            ? 0.0
            : static_cast<double>(
                  *std::max_element(attack_size.begin(), attack_size.end())));
    out->emplace_back(
        prefix + "attack_gap_median_ms",
        attack_gap_median_scratch.empty()
            ? 0.0
            : qrdisc_median_f64(
                  attack_gap_median_scratch.data(),
                  static_cast<std::int64_t>(attack_gap_median_scratch.size())));
    out->emplace_back(
        prefix + "attack_gap_p10_ms",
        attack_gap.empty()
            ? 0.0
            : qrdisc_quantile_linear_f64(
                  attack_gap.data(),
                  static_cast<std::int64_t>(attack_gap.size()), .10));
    out->emplace_back(
        prefix + "attack_peak_100ms",
        static_cast<double>(qrdisc_peak_count(
            attack_ts.data(), static_cast<std::int64_t>(attack_ts.size()),
            100000000)));
    out->emplace_back(
        prefix + "attack_peak_250ms",
        static_cast<double>(qrdisc_peak_count(
            attack_ts.data(), static_cast<std::int64_t>(attack_ts.size()),
            250000000)));
    out->emplace_back(prefix + "attack_rate_acceleration",
                      qrdisc_horizon_ratio(static_cast<double>(attack_second),
                                           static_cast<double>(attack_first)));
    out->emplace_back(prefix + "lift_event_count",
                      static_cast<double>(lift_ts.size()));
    out->emplace_back(prefix + "lift_event_rate",
                      static_cast<double>(lift_ts.size()) / width_sec);
    out->emplace_back(prefix + "lift_volume",
                      static_cast<double>(qrdisc_sum_i64(lift_size)));
    out->emplace_back(prefix + "lift_mean_size", lift_mean);
    out->emplace_back(
        prefix + "lift_max_size",
        lift_size.empty()
            ? 0.0
            : static_cast<double>(
                  *std::max_element(lift_size.begin(), lift_size.end())));
    out->emplace_back(
        prefix + "lift_gap_median_ms",
        lift_gap_scratch.empty()
            ? 0.0
            : qrdisc_median_f64(
                  lift_gap_scratch.data(),
                  static_cast<std::int64_t>(lift_gap_scratch.size())));
    out->emplace_back(
        prefix + "lift_peak_100ms",
        static_cast<double>(qrdisc_peak_count(
            lift_ts.data(), static_cast<std::int64_t>(lift_ts.size()),
            100000000)));
    out->emplace_back(prefix + "reload_event_count",
                      static_cast<double>(reload_ts.size()));
    out->emplace_back(prefix + "reload_size",
                      static_cast<double>(reload_volume));
    out->emplace_back(
        prefix + "reload_latency_median_ms",
        latency_median_scratch.empty()
            ? 0.0
            : qrdisc_median_i64(
                  latency_median_scratch.data(),
                  static_cast<std::int64_t>(latency_median_scratch.size())) /
                  1e6);
    out->emplace_back(
        prefix + "reload_latency_p90_ms",
        latency_scratch.empty()
            ? 0.0
            : qrdisc_quantile_linear_f64(
                  latency_scratch.data(),
                  static_cast<std::int64_t>(latency_scratch.size()), .90) /
                  1e6);
    out->emplace_back(
        prefix + "reload_per_attack",
        qrdisc_ratio_or_zero(static_cast<double>(reload_ts.size()),
                             static_cast<double>(attack_ts.size())));
    out->emplace_back(
        prefix + "reload_size_per_attack_volume",
        qrdisc_ratio_or_zero(static_cast<double>(reload_volume),
                             static_cast<double>(attack_volume)));
    out->emplace_back(prefix + "pull_no_fill_count",
                      static_cast<double>(pull_ts.size()));
    out->emplace_back(prefix + "pull_no_fill_size",
                      static_cast<double>(qrdisc_sum_i64(pull_size)));
    out->emplace_back(
        prefix + "pull_size_over_reload_size",
        qrdisc_ratio_or_zero(static_cast<double>(qrdisc_sum_i64(pull_size)),
                             static_cast<double>(reload_volume)));
    out->emplace_back(
        prefix + "pull_lifetime_median_ms",
        lifetime_scratch.empty()
            ? 0.0
            : qrdisc_median_i64(
                  lifetime_scratch.data(),
                  static_cast<std::int64_t>(lifetime_scratch.size())) /
                  1e6);
    out->emplace_back(prefix + "attack_reload_lift_ordered",
                      ordered ? 1.0 : 0.0);
    out->emplace_back(
        prefix + "last_attack_age_ms",
        attack_ts.empty()
            ? 0.0
            : static_cast<double>(right_ns - attack_ts.back()) / 1e6);
    out->emplace_back(
        prefix + "last_lift_age_ms",
        lift_ts.empty() ? 0.0
                        : static_cast<double>(right_ns - lift_ts.back()) / 1e6);
    out->emplace_back(
        prefix + "last_reload_age_ms",
        reload_ts.empty()
            ? 0.0
            : static_cast<double>(right_ns - reload_ts.back()) / 1e6);
  }
  return true;
}
