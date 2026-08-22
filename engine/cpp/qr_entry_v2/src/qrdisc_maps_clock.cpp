// qrdisc native families: `_event_clock_map` (discretionary_features.py:1471),
// `_trade_clock_map` (:1671) and `_volume_clock_map` (:1683).
//
// WHAT AN "EVENT CLOCK" FAMILY IS
//   feature_map calls each of these methods once per target (:2461, :2466,
//   :2471), so the native family is every one of those calls merged in the
//   loop's order.  The delegation table is keyed by METHOD name: a family that
//   emitted only its first target would silently leave the other three on the
//   delegate's values, which the store differential would then pass.
//
// WHY THE TWO TRADE CLOCKS ARE THIN
//   Both are a window selection followed by the SAME body, `_trade_slice_map`
//   (:1576), which is ported once as a shared kernel (qrdisc_maps.hpp:91-100)
//   rather than transcribed twice.  Only the selection differs: the trade clock
//   counts trades back from the snapshot, the volume clock walks the volume
//   prefix.
//
// FLOAT LAW
//   Sums, means and dots of float64 arrays are DELEGATED to numpy
//   (qrdisc_kernels_events.hpp:14-29): the values here are ratios, not integer
//   counts, so their pairwise-summation order is load-bearing.  Everything
//   integer-exact — searchsorted, the size sums, the mid2 displacement — stays
//   native.
#include "qr_entry_v2/qrdisc_maps.hpp"

#include <algorithm>
#include <cmath>
#include <string>
#include <vector>

#include "qr_entry_v2/qrdisc_kernels_events.hpp"
#include "qr_entry_v2/qrdisc_np_kernels.hpp"

namespace {

// feature_map:2461, :2466, :2471, in the oracle's own loop order.
const std::int64_t kQrdiscEventClockCounts[] = {16, 64, 256, 1024};
const std::int64_t kQrdiscTradeClockCounts[] = {8, 32, 128, 512};
const std::int64_t kQrdiscVolumeClockVolumes[] = {64, 256, 1024};

// The message ledger `_event_clock_map` slices (discretionary_features.py:
// 571-579), borrowed from the marshalled buffers.
struct QrdiscMessageLedger {
  const std::int64_t* ts;
  const std::uint8_t* action;
  const std::uint8_t* event_side;
  const std::int64_t* size;
  const std::uint8_t* economic;
  const std::int64_t* mid2;
  const std::int64_t* bid_size;
  const std::int64_t* ask_size;
  const std::int64_t* bid_count;
  const std::int64_t* ask_count;
  std::int64_t count;
  double factor;
};

// Every buffer these clocks read is 1-D; `type_num` is the dtype the
// MARSHALLER emits (R6 F6) — uint8 for the action/side/economic columns the
// oracle builds as uint8/bool, int64 for the rest.
const void* qrdisc_clock_buffer(QrdiscPlaneObject* plane, const char* name,
                                int expected_type_num, std::int64_t* count) {
  const QrdiscBuffer* buffer =
      qrdisc_plane_buffer_named(plane, name, expected_type_num, 1);
  if (buffer == nullptr) return nullptr;
  if (count != nullptr) *count = static_cast<std::int64_t>(buffer->shape[0]);
  return buffer->data;
}

bool qrdisc_message_ledger(QrdiscPlaneObject* plane, QrdiscMessageLedger* out) {
  const void* ts =
      qrdisc_clock_buffer(plane, "attr___message_ts", NPY_INT64, &out->count);
  const void* action =
      qrdisc_clock_buffer(plane, "attr___message_action", NPY_UINT8, nullptr);
  const void* event_side =
      qrdisc_clock_buffer(plane, "attr___message_side", NPY_UINT8, nullptr);
  const void* size =
      qrdisc_clock_buffer(plane, "attr___message_size", NPY_INT64, nullptr);
  // `_message_economic` is bool (discretionary_features.py:576) and the
  // marshaller carries bool as a uint8 view.
  const void* economic =
      qrdisc_clock_buffer(plane, "attr___message_economic", NPY_UINT8, nullptr);
  const void* mid2 =
      qrdisc_clock_buffer(plane, "attr___message_mid2", NPY_INT64, nullptr);
  const void* bid_size =
      qrdisc_clock_buffer(plane, "attr___message_bid_sz", NPY_INT64, nullptr);
  const void* ask_size =
      qrdisc_clock_buffer(plane, "attr___message_ask_sz", NPY_INT64, nullptr);
  const void* bid_count =
      qrdisc_clock_buffer(plane, "attr___message_bid_ct", NPY_INT64, nullptr);
  const void* ask_count =
      qrdisc_clock_buffer(plane, "attr___message_ask_ct", NPY_INT64, nullptr);
  if (ts == nullptr || action == nullptr || event_side == nullptr ||
      size == nullptr || economic == nullptr || mid2 == nullptr ||
      bid_size == nullptr || ask_size == nullptr || bid_count == nullptr ||
      ask_count == nullptr) {
    return false;
  }
  PyObject* factor = PyDict_GetItemString(plane->scalars, "factor");
  if (factor == nullptr) {
    PyErr_SetString(PyExc_KeyError, "qrdisc: scalar 'factor' is missing");
    return false;
  }
  out->factor = PyFloat_AsDouble(factor);
  if (out->factor == -1.0 && PyErr_Occurred()) return false;
  out->ts = static_cast<const std::int64_t*>(ts);
  out->action = static_cast<const std::uint8_t*>(action);
  out->event_side = static_cast<const std::uint8_t*>(event_side);
  out->size = static_cast<const std::int64_t*>(size);
  out->economic = static_cast<const std::uint8_t*>(economic);
  out->mid2 = static_cast<const std::int64_t*>(mid2);
  out->bid_size = static_cast<const std::int64_t*>(bid_size);
  out->ask_size = static_cast<const std::int64_t*>(ask_size);
  out->bid_count = static_cast<const std::int64_t*>(bid_count);
  out->ask_count = static_cast<const std::int64_t*>(ask_count);
  return true;
}

// `values.sum()` with numpy's own answer for the one case numpy settles by
// definition rather than by summation order: the empty sum is exactly 0.0.
bool qrdisc_sum_or_zero(const std::vector<double>& values, double* out) {
  *out = 0.0;
  if (values.empty()) return true;
  return qrdisc_np_sum_f64(values.data(),
                           static_cast<std::int64_t>(values.size()), out);
}

// The `mean()` closure of discretionary_features.py:1536-1537.
//
// ONE OF TWO MEANS (R6 F18).  The delegation law lives in
// qrdisc_kernels_events.hpp:14-35.  This form delegates to numpy's own
// `.mean()` and serves `_event_clock_map`'s four economic-event ratios only;
// qrdisc_maps_slice.cpp's `qrdisc_mean_via_sum` uses the port's transcribed
// sum for `_trade_slice_map`'s autocorrelations and formation fraction.  Both
// are bit-identical to their own oracle site and each is receipted there.
bool qrdisc_mean_or_zero(const std::vector<double>& values, double* out) {
  *out = 0.0;
  if (values.empty()) return true;
  return qrdisc_np_mean_f64(values.data(),
                            static_cast<std::int64_t>(values.size()), out);
}

// One target count of `_event_clock_map`.
bool qrdisc_event_clock_window(const QrdiscMessageLedger& ledger,
                               std::int64_t target_count,
                               const QrdiscRowInputs& row,
                               std::int64_t formation_ts_ns,
                               QrdiscValueMap* out) {
  const std::string prefix =
      "disc_eclock_n" + std::to_string(target_count) + "_";
  const std::int64_t right = qrdisc_searchsorted_left_i64(
      QrdiscI64Span{ledger.ts, ledger.count}, row.snapshot_ts_ns);
  const std::int64_t left = std::max<std::int64_t>(0, right - target_count);
  const std::int64_t count = right - left;

  // The compacted arrays the oracle's boolean indexing produces: numpy sums the
  // SELECTED values in their own order, so the mask is materialised as a
  // compacted vector rather than summed in place.
  std::vector<double> signed_flow(static_cast<std::size_t>(count));
  std::vector<double> trade_sizes;
  std::vector<double> quote_sizes;
  std::vector<double> defense_commit_sizes;
  std::vector<double> defense_cancel_sizes;
  std::vector<double> opposing_cancel_sizes;
  std::vector<double> opposing_commit_sizes;
  std::vector<std::int64_t> economic_mid2;
  std::vector<double> bid_size;
  std::vector<double> ask_size;
  std::vector<double> bid_count;
  std::vector<double> ask_count;
  std::int64_t trade_count = 0;
  std::int64_t add_count = 0;
  std::int64_t cancel_count = 0;
  std::int64_t modify_count = 0;
  std::int64_t formation_count = 0;
  std::int64_t economic_count = 0;
  const std::uint8_t defense_side = row.side > 0 ? 'B' : 'A';
  const std::uint8_t opposing_side = row.side > 0 ? 'A' : 'B';
  for (std::int64_t index = 0; index < count; ++index) {
    const std::int64_t slot = left + index;
    const double size = static_cast<double>(ledger.size[slot]);
    const std::uint8_t action = ledger.action[slot];
    const std::uint8_t event_side = ledger.event_side[slot];
    const bool trade = action == 'T';
    const bool add = action == 'A';
    const bool cancel = action == 'C';
    const bool modify = action == 'M';
    const bool defense = event_side == defense_side;
    const bool opposing = event_side == opposing_side;
    if (trade) {
      ++trade_count;
      trade_sizes.push_back(size);
    }
    if (add) ++add_count;
    if (cancel) ++cancel_count;
    if (modify) ++modify_count;
    if (add || cancel || modify) quote_sizes.push_back(size);
    if ((add || modify) && defense) defense_commit_sizes.push_back(size);
    if (cancel && defense) defense_cancel_sizes.push_back(size);
    if (cancel && opposing) opposing_cancel_sizes.push_back(size);
    if ((add || modify) && opposing) opposing_commit_sizes.push_back(size);
    signed_flow[static_cast<std::size_t>(index)] =
        (trade && event_side == 'B') ? size
                                     : ((trade && event_side == 'A') ? -size : 0.0);
    if (ledger.ts[slot] >= formation_ts_ns) ++formation_count;
    if (ledger.economic[slot] != 0) {
      ++economic_count;
      economic_mid2.push_back(ledger.mid2[slot]);
      bid_size.push_back(static_cast<double>(ledger.bid_size[slot]));
      ask_size.push_back(static_cast<double>(ledger.ask_size[slot]));
      bid_count.push_back(static_cast<double>(ledger.bid_count[slot]));
      ask_count.push_back(static_cast<double>(ledger.ask_count[slot]));
    }
  }

  const double span =
      count >= 2 ? static_cast<double>(ledger.ts[right - 1] - ledger.ts[left]) / 1e9
                 : 0.0;
  std::vector<double> gaps(static_cast<std::size_t>(count > 0 ? count - 1 : 0));
  for (std::size_t index = 0; index + 1 < static_cast<std::size_t>(count); ++index) {
    gaps[index] = static_cast<double>(ledger.ts[left + static_cast<std::int64_t>(index) + 1] -
                                      ledger.ts[left + static_cast<std::int64_t>(index)]) /
                  1e6;
  }

  double trade_volume = 0.0;
  double quote_size = 0.0;
  double defense_commit = 0.0;
  double defense_cancel = 0.0;
  double opposing_cancel = 0.0;
  double opposing_commit = 0.0;
  double signed_total = 0.0;
  if (!qrdisc_sum_or_zero(trade_sizes, &trade_volume) ||
      !qrdisc_sum_or_zero(quote_sizes, &quote_size) ||
      !qrdisc_sum_or_zero(defense_commit_sizes, &defense_commit) ||
      !qrdisc_sum_or_zero(defense_cancel_sizes, &defense_cancel) ||
      !qrdisc_sum_or_zero(opposing_cancel_sizes, &opposing_cancel) ||
      !qrdisc_sum_or_zero(opposing_commit_sizes, &opposing_commit) ||
      !qrdisc_sum_or_zero(signed_flow, &signed_total)) {
    return false;
  }
  const double defense_commitment =
      quote_size != 0.0 ? (defense_commit - defense_cancel) / quote_size : 0.0;
  const double opposing_withdrawal =
      quote_size != 0.0 ? (opposing_cancel - opposing_commit) / quote_size : 0.0;

  double displacement = 0.0;
  double variation = 0.0;
  if (economic_mid2.size() >= 2) {
    displacement = qrdisc_aligned_usd(row.side, economic_mid2.back(),
                                      economic_mid2.front(), ledger.factor);
    std::vector<double> absolute(economic_mid2.size() - 1);
    for (std::size_t index = 0; index + 1 < economic_mid2.size(); ++index) {
      absolute[index] = std::fabs(
          static_cast<double>(economic_mid2[index + 1] - economic_mid2[index]));
    }
    double total = 0.0;
    if (!qrdisc_sum_or_zero(absolute, &total)) return false;
    variation = total * ledger.factor;
  }

  // discretionary_features.py:1521-1534 — the four per-economic-event ratios,
  // or four empty arrays when the window holds no economic event at all.
  std::vector<double> size_imbalance;
  std::vector<double> count_imbalance;
  std::vector<double> defense_average;
  std::vector<double> opposing_average;
  if (!bid_size.empty()) {
    const double side_value = static_cast<double>(row.side);
    size_imbalance.resize(bid_size.size());
    count_imbalance.resize(bid_size.size());
    defense_average.resize(bid_size.size());
    opposing_average.resize(bid_size.size());
    for (std::size_t index = 0; index < bid_size.size(); ++index) {
      size_imbalance[index] = side_value * (bid_size[index] - ask_size[index]) /
                              std::max(1.0, bid_size[index] + ask_size[index]);
      count_imbalance[index] = side_value * (bid_count[index] - ask_count[index]) /
                               std::max(1.0, bid_count[index] + ask_count[index]);
      const double defense_size = row.side > 0 ? bid_size[index] : ask_size[index];
      const double defense_count = row.side > 0 ? bid_count[index] : ask_count[index];
      const double opposing_size = row.side > 0 ? ask_size[index] : bid_size[index];
      const double opposing_count = row.side > 0 ? ask_count[index] : bid_count[index];
      defense_average[index] = defense_size / std::max(1.0, defense_count);
      opposing_average[index] = opposing_size / std::max(1.0, opposing_count);
    }
  }
  double size_imbalance_mean = 0.0;
  double count_imbalance_mean = 0.0;
  double defense_average_mean = 0.0;
  double opposing_average_mean = 0.0;
  double size_imbalance_slope = 0.0;
  double count_imbalance_slope = 0.0;
  double defense_average_slope = 0.0;
  double opposing_average_slope = 0.0;
  const std::int64_t economic_width = static_cast<std::int64_t>(bid_size.size());
  if (!qrdisc_mean_or_zero(size_imbalance, &size_imbalance_mean) ||
      !qrdisc_mean_or_zero(count_imbalance, &count_imbalance_mean) ||
      !qrdisc_mean_or_zero(defense_average, &defense_average_mean) ||
      !qrdisc_mean_or_zero(opposing_average, &opposing_average_mean) ||
      !qrdisc_slope(size_imbalance.data(), economic_width, &size_imbalance_slope) ||
      !qrdisc_slope(count_imbalance.data(), economic_width, &count_imbalance_slope) ||
      !qrdisc_slope(defense_average.data(), economic_width, &defense_average_slope) ||
      !qrdisc_slope(opposing_average.data(), economic_width, &opposing_average_slope)) {
    return false;
  }

  const double counted = static_cast<double>(count);
  // The emitted NAME ORDER is the dict literal's order at :1539-1574: those
  // names reach the dense store, so order is identity here as it is for the
  // slice kernel (qrdisc_maps_slice.cpp:9).
  out->emplace_back(prefix + "support_count", counted);
  out->emplace_back(prefix + "support_fraction",
                    counted / static_cast<double>(target_count));
  out->emplace_back(prefix + "span_ms", span * 1e3);
  out->emplace_back(prefix + "event_rate_hz", span > 0 ? counted / span : 0.0);
  out->emplace_back(prefix + "gap_median_ms",
                    gaps.empty() ? 0.0
                                 : qrdisc_median_f64(
                                       gaps.data(),
                                       static_cast<std::int64_t>(gaps.size())));
  out->emplace_back(prefix + "gap_p10_ms",
                    gaps.empty() ? 0.0
                                 : qrdisc_quantile_linear_f64(
                                       gaps.data(),
                                       static_cast<std::int64_t>(gaps.size()), .10));
  // `np.mean` over a boolean array is an exact integer count divided by the
  // length, so these five fractions need no delegated reduction.
  out->emplace_back(prefix + "formation_fraction",
                    count ? static_cast<double>(formation_count) / counted : 0.0);
  out->emplace_back(prefix + "trade_fraction",
                    count ? static_cast<double>(trade_count) / counted : 0.0);
  out->emplace_back(prefix + "add_fraction",
                    count ? static_cast<double>(add_count) / counted : 0.0);
  out->emplace_back(prefix + "cancel_fraction",
                    count ? static_cast<double>(cancel_count) / counted : 0.0);
  out->emplace_back(prefix + "modify_fraction",
                    count ? static_cast<double>(modify_count) / counted : 0.0);
  out->emplace_back(prefix + "trade_volume", trade_volume);
  out->emplace_back(prefix + "aligned_flow_fraction",
                    trade_volume != 0.0
                        ? static_cast<double>(row.side) * signed_total / trade_volume
                        : 0.0);
  out->emplace_back(prefix + "defense_commitment", defense_commitment);
  out->emplace_back(prefix + "opposing_withdrawal", opposing_withdrawal);
  out->emplace_back(prefix + "quote_churn_per_trade_volume",
                    trade_volume != 0.0 ? quote_size / trade_volume : 0.0);
  out->emplace_back(prefix + "aligned_displacement_usd", displacement);
  out->emplace_back(prefix + "path_variation_usd", variation);
  out->emplace_back(prefix + "path_efficiency",
                    variation != 0.0 ? std::fabs(displacement) / variation : 0.0);
  out->emplace_back(prefix + "aligned_size_imbalance_mean", size_imbalance_mean);
  out->emplace_back(prefix + "aligned_size_imbalance_slope", size_imbalance_slope);
  out->emplace_back(prefix + "aligned_count_imbalance_mean", count_imbalance_mean);
  out->emplace_back(prefix + "aligned_count_imbalance_slope", count_imbalance_slope);
  out->emplace_back(prefix + "defense_average_order_size", defense_average_mean);
  out->emplace_back(prefix + "defense_average_order_size_slope", defense_average_slope);
  out->emplace_back(prefix + "opposing_average_order_size", opposing_average_mean);
  out->emplace_back(prefix + "opposing_average_order_size_slope", opposing_average_slope);
  out->emplace_back(prefix + "size_count_divergence",
                    size_imbalance_mean - count_imbalance_mean);
  out->emplace_back(prefix + "economic_fraction",
                    count ? static_cast<double>(economic_count) / counted : 0.0);
  return true;
}

// `_trade_ts` and `_trade_volume_prefix`, the two vectors both trade clocks
// select their window with (discretionary_features.py:620, 626-627).
bool qrdisc_trade_clock_vectors(QrdiscPlaneObject* plane, const std::int64_t** ts,
                                std::int64_t* count,
                                const std::int64_t** volume_prefix,
                                std::int64_t* prefix_count) {
  const void* trade_ts =
      qrdisc_clock_buffer(plane, "attr___trade_ts", NPY_INT64, count);
  // The prefix is one longer than the trade vector (a prepended zero), but its
  // OWN length is read rather than derived: `np.searchsorted` searches the whole
  // array, and a derived length would silently mis-search a marshaller change.
  const void* prefix = qrdisc_clock_buffer(
      plane, "attr___trade_volume_prefix", NPY_INT64, prefix_count);
  if (trade_ts == nullptr || prefix == nullptr) return false;
  *ts = static_cast<const std::int64_t*>(trade_ts);
  *volume_prefix = static_cast<const std::int64_t*>(prefix);
  return true;
}

}  // namespace

bool qrdisc_event_clock_map(QrdiscPlaneObject* plane, const QrdiscRowInputs& row,
                            QrdiscValueMap* out) {
  QrdiscMessageLedger ledger{};
  if (!qrdisc_message_ledger(plane, &ledger)) return false;
  std::int64_t formation_ts_ns = 0;
  if (!qrdisc_mapping_int64(row.formation_candidate, "decision_ts_ns",
                            &formation_ts_ns)) {
    return false;
  }
  for (const std::int64_t target_count : kQrdiscEventClockCounts) {
    if (!qrdisc_event_clock_window(ledger, target_count, row, formation_ts_ns,
                                   out)) {
      return false;
    }
  }
  return true;
}

bool qrdisc_trade_clock_map(QrdiscPlaneObject* plane, const QrdiscRowInputs& row,
                            QrdiscValueMap* out) {
  const std::int64_t* ts = nullptr;
  const std::int64_t* volume_prefix = nullptr;
  std::int64_t count = 0;
  std::int64_t prefix_count = 0;
  if (!qrdisc_trade_clock_vectors(plane, &ts, &count, &volume_prefix,
                                  &prefix_count)) {
    return false;
  }
  std::int64_t formation_ts_ns = 0;
  if (!qrdisc_mapping_int64(row.formation_candidate, "decision_ts_ns",
                            &formation_ts_ns)) {
    return false;
  }
  const std::int64_t right =
      qrdisc_searchsorted_left_i64(QrdiscI64Span{ts, count}, row.snapshot_ts_ns);
  for (const std::int64_t target_count : kQrdiscTradeClockCounts) {
    const std::int64_t left = std::max<std::int64_t>(0, right - target_count);
    if (!qrdisc_trade_slice_map(
            plane, "disc_tclock_n" + std::to_string(target_count) + "_", left,
            right, static_cast<double>(right - left) / static_cast<double>(target_count),
            row.snapshot_ts_ns, formation_ts_ns, row.side, out)) {
      return false;
    }
  }
  return true;
}

bool qrdisc_volume_clock_map(QrdiscPlaneObject* plane, const QrdiscRowInputs& row,
                             QrdiscValueMap* out) {
  const std::int64_t* ts = nullptr;
  const std::int64_t* volume_prefix = nullptr;
  std::int64_t count = 0;
  std::int64_t prefix_count = 0;
  if (!qrdisc_trade_clock_vectors(plane, &ts, &count, &volume_prefix,
                                  &prefix_count)) {
    return false;
  }
  std::int64_t formation_ts_ns = 0;
  if (!qrdisc_mapping_int64(row.formation_candidate, "decision_ts_ns",
                            &formation_ts_ns)) {
    return false;
  }
  const std::int64_t right =
      qrdisc_searchsorted_left_i64(QrdiscI64Span{ts, count}, row.snapshot_ts_ns);
  const std::int64_t available = volume_prefix[right];
  for (const std::int64_t target_volume : kQrdiscVolumeClockVolumes) {
    const std::int64_t threshold = std::max<std::int64_t>(0, available - target_volume);
    const std::int64_t left = std::max<std::int64_t>(
        0, qrdisc_searchsorted_right_i64(QrdiscI64Span{volume_prefix, prefix_count},
                                         threshold) -
               1);
    const std::int64_t selected = volume_prefix[right] - volume_prefix[left];
    if (!qrdisc_trade_slice_map(
            plane, "disc_vclock_v" + std::to_string(target_volume) + "_", left,
            right,
            std::min(1.0, static_cast<double>(selected) /
                              static_cast<double>(target_volume)),
            row.snapshot_ts_ns, formation_ts_ns, row.side, out)) {
      return false;
    }
  }
  return true;
}
