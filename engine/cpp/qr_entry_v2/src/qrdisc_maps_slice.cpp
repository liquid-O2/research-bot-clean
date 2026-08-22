// qrdisc native kernel: `_trade_slice_map` (discretionary_features.py:1576).
//
// NOT A FAMILY.  feature_map never calls it; `_trade_clock_map` (:1671) and
// `_volume_clock_map` (:1683) do, and they own the window arguments (left,
// right, support_fraction).  So this file exports a kernel with the oracle
// method's own signature, gated at that seam against the oracle's bound method,
// and the clock families call it once they go native.
//
// The emitted NAME ORDER is the dict literal's order at :1627-1669: those names
// reach the dense store through the clock families, so order is identity here
// exactly as it is for a family.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <string>
#include <vector>

#include "qr_entry_v2/qrdisc_kernels_events.hpp"
#include "qr_entry_v2/qrdisc_maps.hpp"
#include "qr_entry_v2/qrdisc_np_kernels.hpp"

namespace {

// `np.mean` over a float64 array: numpy's own sum, then the divide.
//
// ONE OF TWO MEANS, AND THIS IS THE OTHER ONE'S SIBLING (R6 F18).  The
// delegation law lives in qrdisc_kernels_events.hpp:14-35.  This form is used
// by `_trade_slice_map`'s two call sites only — the sign autocorrelations and
// the formation fraction — where the port already owns the transcribed sum;
// qrdisc_maps_clock.cpp's `qrdisc_mean_or_zero` delegates to numpy's own
// `.mean()` for `_event_clock_map`'s four economic-event ratios.  Both are
// bit-identical to their own oracle site and each is receipted there.
bool qrdisc_mean_via_sum(const double* data, std::int64_t count, double* out) {
  double total = 0.0;
  if (!qrdisc_np_sum_f64(data, count, &total)) return false;
  *out = total / static_cast<double>(count);
  return true;
}

double qrdisc_guarded_ratio(double numerator, double denominator) {
  return denominator != 0.0 ? numerator / denominator : 0.0;
}

}  // namespace

bool qrdisc_trade_slice_map(QrdiscPlaneObject* plane, const std::string& prefix,
                            std::int64_t left, std::int64_t right,
                            double support_fraction,
                            std::int64_t snapshot_ts_ns,
                            std::int64_t formation_ts_ns, std::int64_t side,
                            QrdiscValueMap* out) {
  const QrdiscBuffer* ts_buffer = qrdisc_plane_buffer_named(plane, "attr___trade_ts", NPY_INT64, 1);
  const QrdiscBuffer* sign_buffer =
      qrdisc_plane_buffer_named(plane, "attr___trade_sign", NPY_UINT8, 1);
  const QrdiscBuffer* size_buffer =
      qrdisc_plane_buffer_named(plane, "attr___trade_exact_sizes", NPY_INT64, 1);
  const QrdiscBuffer* tick_buffer =
      qrdisc_plane_buffer_named(plane, "attr___trade_exact_ticks", NPY_INT64, 1);
  if (ts_buffer == nullptr || sign_buffer == nullptr || size_buffer == nullptr ||
      tick_buffer == nullptr) {
    return false;
  }
  const std::int64_t count = right - left;
  const std::int64_t* ts = static_cast<const std::int64_t*>(ts_buffer->data) + left;
  // `_trade_sign` is int8 (discretionary_features.py:622) and the marshaller
  // carries int8 as a uint8 VIEW, same bytes; it is read back as int8 here.
  const std::int8_t* raw_signs =
      static_cast<const std::int8_t*>(sign_buffer->data) + left;
  const std::int64_t* raw_sizes =
      static_cast<const std::int64_t*>(size_buffer->data) + left;
  const std::int64_t* raw_ticks =
      static_cast<const std::int64_t*>(tick_buffer->data) + left;

  const std::size_t width = static_cast<std::size_t>(count > 0 ? count : 0);
  std::vector<double> signs(width);
  std::vector<double> sizes(width);
  std::vector<double> ticks(width);
  std::vector<double> aligned(width);
  for (std::size_t index = 0; index < width; ++index) {
    signs[index] = static_cast<double>(raw_signs[index]);
    sizes[index] = static_cast<double>(raw_sizes[index]);
    ticks[index] = static_cast<double>(raw_ticks[index]);
    aligned[index] = static_cast<double>(side) * signs[index];
  }

  double volume = 0.0;
  if (!qrdisc_np_sum_f64(sizes.data(), count, &volume)) return false;
  const double span =
      count >= 2 ? static_cast<double>(ts[count - 1] - ts[0]) / 1e9 : 0.0;
  std::vector<double> gaps;
  if (count >= 2) {
    gaps.reserve(width - 1);
    for (std::size_t index = 1; index < width; ++index) {
      gaps.push_back(static_cast<double>(ts[index] - ts[index - 1]) / 1e6);
    }
  }

  // `autocorrelation(lag)` (:1590-1593).
  double autocorrelation[2] = {0.0, 0.0};
  const std::int64_t lags[2] = {1, 4};
  for (int slot = 0; slot < 2; ++slot) {
    const std::int64_t lag = lags[slot];
    if (count <= lag) continue;
    std::vector<double> products(static_cast<std::size_t>(count - lag));
    for (std::int64_t index = 0; index < count - lag; ++index) {
      products[static_cast<std::size_t>(index)] =
          signs[static_cast<std::size_t>(index + lag)] *
          signs[static_cast<std::size_t>(index)];
    }
    if (!qrdisc_mean_via_sum(products.data(), count - lag,
                             &autocorrelation[slot])) {
      return false;
    }
  }

  std::int64_t current_run_count = 0;
  double current_run_volume = 0.0;
  double current_run_duration = 0.0;
  double current_control = 0.0;
  std::int64_t max_run_count = 0;
  double max_run_volume = 0.0;
  if (count > 0) {
    const double current_sign = signs[width - 1];
    std::int64_t start = count - 1;
    while (start > 0 && signs[static_cast<std::size_t>(start - 1)] == current_sign) {
      --start;
    }
    current_run_count = count - start;
    if (!qrdisc_np_sum_f64(sizes.data() + start, count - start,
                           &current_run_volume)) {
      return false;
    }
    current_run_duration = static_cast<double>(ts[count - 1] - ts[start]) / 1e6;
    current_control = static_cast<double>(side) * current_sign;
    std::int64_t run_start = 0;
    for (std::int64_t index = 1; index <= count; ++index) {
      if (index == count ||
          signs[static_cast<std::size_t>(index)] !=
              signs[static_cast<std::size_t>(run_start)]) {
        max_run_count = std::max(max_run_count, index - run_start);
        double run_volume = 0.0;
        if (!qrdisc_np_sum_f64(sizes.data() + run_start, index - run_start,
                               &run_volume)) {
          return false;
        }
        max_run_volume = std::max(max_run_volume, run_volume);
        run_start = index;
      }
    }
  }

  double displacement = 0.0;
  double variation = 0.0;
  double tick_range = 0.0;
  if (count >= 2) {
    displacement =
        static_cast<double>(side) * (ticks[width - 1] - ticks[0]);
    std::vector<double> absolute(width - 1);
    for (std::size_t index = 1; index < width; ++index) {
      absolute[index - 1] = std::fabs(ticks[index] - ticks[index - 1]);
    }
    if (!qrdisc_np_sum_f64(absolute.data(), count - 1, &variation)) return false;
    const std::pair<std::vector<double>::iterator, std::vector<double>::iterator>
        extremes = std::minmax_element(ticks.begin(), ticks.end());
    tick_range = *extremes.second - *extremes.first;
  }
  std::vector<double> weights;
  if (volume != 0.0) {
    weights.resize(width);
    for (std::size_t index = 0; index < width; ++index) {
      weights[index] = sizes[index] / volume;
    }
  }
  double first_volume = 0.0;
  double second_volume = volume;
  if (count >= 2) {
    const std::int64_t half = count / 2;
    if (!qrdisc_np_sum_f64(sizes.data(), half, &first_volume) ||
        !qrdisc_np_sum_f64(sizes.data() + half, count - half, &second_volume)) {
      return false;
    }
  }

  double formation_fraction = 0.0;
  if (count > 0) {
    std::vector<double> reached(width);
    for (std::size_t index = 0; index < width; ++index) {
      reached[index] = ts[index] >= formation_ts_ns ? 1.0 : 0.0;
    }
    if (!qrdisc_mean_via_sum(reached.data(), count, &formation_fraction)) {
      return false;
    }
  }
  double aligned_flow = 0.0;
  if (count > 0 &&
      !qrdisc_np_dot_f64(aligned.data(), sizes.data(), count, &aligned_flow)) {
    return false;
  }
  double size_hhi = 0.0;
  if (!weights.empty() &&
      !qrdisc_np_dot_f64(weights.data(), weights.data(),
                         static_cast<std::int64_t>(weights.size()), &size_hhi)) {
    return false;
  }
  double top3 = 0.0;
  if (!weights.empty()) {
    std::vector<double> sorted(weights);
    std::sort(sorted.begin(), sorted.end());
    const std::size_t take = std::min<std::size_t>(3, sorted.size());
    if (!qrdisc_np_sum_f64(sorted.data() + (sorted.size() - take),
                           static_cast<std::int64_t>(take), &top3)) {
      return false;
    }
  }
  std::vector<double> distinct(ticks);
  std::sort(distinct.begin(), distinct.end());
  distinct.erase(std::unique(distinct.begin(), distinct.end()), distinct.end());
  std::vector<double> gap_median_scratch(gaps);

  out->emplace_back(prefix + "support_count", static_cast<double>(count));
  out->emplace_back(prefix + "support_fraction", support_fraction);
  out->emplace_back(prefix + "span_ms", span * 1e3);
  out->emplace_back(prefix + "trade_rate_hz",
                    span > 0.0 ? static_cast<double>(count) / span : 0.0);
  out->emplace_back(prefix + "volume", volume);
  out->emplace_back(prefix + "volume_rate", span > 0.0 ? volume / span : 0.0);
  out->emplace_back(prefix + "formation_fraction", formation_fraction);
  out->emplace_back(prefix + "aligned_flow_fraction",
                    qrdisc_guarded_ratio(aligned_flow, volume));
  out->emplace_back(prefix + "sign_autocorrelation_lag1", autocorrelation[0]);
  out->emplace_back(prefix + "sign_autocorrelation_lag4", autocorrelation[1]);
  out->emplace_back(prefix + "gap_median_ms",
                    gap_median_scratch.empty()
                        ? 0.0
                        : qrdisc_median_f64(gap_median_scratch.data(),
                                            static_cast<std::int64_t>(
                                                gap_median_scratch.size())));
  out->emplace_back(
      prefix + "gap_p10_ms",
      gaps.empty() ? 0.0
                   : qrdisc_quantile_linear_f64(
                         gaps.data(), static_cast<std::int64_t>(gaps.size()),
                         .10));
  out->emplace_back(prefix + "current_run_control", current_control);
  out->emplace_back(prefix + "current_run_count",
                    static_cast<double>(current_run_count));
  out->emplace_back(prefix + "current_run_volume", current_run_volume);
  out->emplace_back(prefix + "current_run_duration_ms", current_run_duration);
  out->emplace_back(prefix + "current_run_over_max_volume",
                    qrdisc_guarded_ratio(current_run_volume, max_run_volume));
  out->emplace_back(prefix + "max_run_count", static_cast<double>(max_run_count));
  out->emplace_back(prefix + "max_run_volume", max_run_volume);
  out->emplace_back(prefix + "volume_acceleration",
                    qrdisc_horizon_ratio(second_volume, first_volume));
  out->emplace_back(prefix + "size_hhi", size_hhi);
  out->emplace_back(prefix + "max_size_fraction",
                    weights.empty()
                        ? 0.0
                        : *std::max_element(weights.begin(), weights.end()));
  out->emplace_back(prefix + "top3_size_fraction", top3);
  out->emplace_back(prefix + "distinct_price_levels",
                    static_cast<double>(distinct.size()));
  out->emplace_back(prefix + "price_range_ticks", tick_range);
  out->emplace_back(prefix + "aligned_displacement_ticks", displacement);
  out->emplace_back(prefix + "path_variation_ticks", variation);
  out->emplace_back(prefix + "path_efficiency",
                    qrdisc_guarded_ratio(std::fabs(displacement), variation));
  out->emplace_back(prefix + "sweep_speed_ticks_per_sec",
                    span > 0.0 ? tick_range / span : 0.0);
  out->emplace_back(
      prefix + "price_yield_per_aligned_volume",
      qrdisc_guarded_ratio(displacement, std::fabs(aligned_flow)));
  out->emplace_back(
      prefix + "last_trade_age_ms",
      count > 0 ? static_cast<double>(snapshot_ts_ns - ts[count - 1]) / 1e6
                : 0.0);
  return true;
}
