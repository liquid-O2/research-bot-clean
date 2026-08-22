// Shared per-row kernels of the qrdisc port.  See qrdisc_kernels_events.hpp
// for the delegation law these transcriptions obey.
#include "qr_entry_v2/qrdisc_kernels_events.hpp"

#include <algorithm>
#include <numeric>
#include <string>

#include "qr_entry_v2/qrdisc_maps.hpp"
#include "qr_entry_v2/qrdisc_np_kernels.hpp"

namespace {

// numpy's own module object, imported ONCE by PyInit_qr_disc_native (R6 F17)
// and only read from here.  The previous lazy `static ... if (cached ==
// nullptr)` assigned on the ROW path: an import failure there left the null
// cached and retried every row, and the write itself was a per-row race the
// module-init form cannot have.
PyObject* g_qrdisc_numpy_module = nullptr;

PyObject* qrdisc_numpy_module() {
  if (g_qrdisc_numpy_module == nullptr) {
    PyErr_SetString(PyExc_RuntimeError,
                    "qrdisc: numpy was not imported at module init; "
                    "PyInit_qr_disc_native must call "
                    "qrdisc_import_numpy_module before any row runs");
  }
  return g_qrdisc_numpy_module;
}

// A borrowed, read-only numpy view over caller memory.  Nothing is copied and
// nothing outlives the call: the array is destroyed before the kernel returns.
PyObject* qrdisc_borrowed_array(const void* data, std::int64_t count,
                                int type_num) {
  npy_intp dimensions[1] = {static_cast<npy_intp>(count)};
  // const_cast is safe: NPY_ARRAY_WRITEABLE is not set, so numpy will refuse a
  // write, and every delegated reduction below is pure.
  PyObject* array = PyArray_New(&PyArray_Type, 1, dimensions, type_num, nullptr,
                                const_cast<void*>(data), 0,
                                NPY_ARRAY_C_CONTIGUOUS, nullptr);
  return array;
}

bool qrdisc_call_method_double(PyObject* object, const char* method,
                               double* out) {
  PyObject* result = PyObject_CallMethod(object, method, nullptr);
  if (result == nullptr) return false;
  *out = PyFloat_AsDouble(result);
  Py_DECREF(result);
  return !(*out == -1.0 && PyErr_Occurred());
}

bool qrdisc_np_reduce(const void* data, std::int64_t count, int type_num,
                      const char* method, double* out) {
  PyObject* array = qrdisc_borrowed_array(data, count, type_num);
  if (array == nullptr) return false;
  const bool ok = qrdisc_call_method_double(array, method, out);
  Py_DECREF(array);
  return ok;
}

}  // namespace

bool qrdisc_import_numpy_module() {
  g_qrdisc_numpy_module = PyImport_ImportModule("numpy");
  return g_qrdisc_numpy_module != nullptr;
}

bool qrdisc_np_mean_i64(const std::int64_t* data, std::int64_t count,
                        double* out) {
  return qrdisc_np_reduce(data, count, NPY_INT64, "mean", out);
}

bool qrdisc_np_mean_f64(const double* data, std::int64_t count, double* out) {
  return qrdisc_np_reduce(data, count, NPY_FLOAT64, "mean", out);
}

namespace {

// numpy's float64 `.sum()`, transcribed.
//
// TWO LEVELS, BOTH MEASURED (scratchpad spike_pairwise2.py, numpy 2.1.2, this
// box).  Inside one buffer's worth of elements the reduction is numpy's
// pairwise sum (loops_utils.h.src `pairwise_sum_DOUBLE`): naive below 8, eight
// partial accumulators up to 128, then a split at n/2 rounded down to a
// multiple of 8.  ACROSS buffers the ufunc machinery accumulates the block
// results left to right, which is why the pairwise form alone is right up to
// 8192 elements and then diverges by an ulp (measured wrong at 8200, 9000,
// 10007, 16383, 16385, 20000, 50000; the blocked form matched every one, and
// matched at all 2050 lengths below 2050 and at every slice alignment tried).
constexpr std::int64_t kQrdiscNumpyBufferSize = 8192;

double qrdisc_pairwise_sum(const double* data, std::int64_t count) {
  if (count < 8) {
    double result = 0.0;
    for (std::int64_t index = 0; index < count; ++index) result += data[index];
    return result;
  }
  if (count <= 128) {
    double partial[8] = {data[0], data[1], data[2], data[3],
                         data[4], data[5], data[6], data[7]};
    std::int64_t index = 8;
    for (; index < count - (count % 8); index += 8) {
      for (int lane = 0; lane < 8; ++lane) partial[lane] += data[index + lane];
    }
    double result = ((partial[0] + partial[1]) + (partial[2] + partial[3])) +
                    ((partial[4] + partial[5]) + (partial[6] + partial[7]));
    for (; index < count; ++index) result += data[index];
    return result;
  }
  std::int64_t half = count / 2;
  half -= half % 8;
  return qrdisc_pairwise_sum(data, half) +
         qrdisc_pairwise_sum(data + half, count - half);
}

}  // namespace

bool qrdisc_np_sum_f64(const double* data, std::int64_t count, double* out) {
  double result = 0.0;
  for (std::int64_t offset = 0; offset < count;
       offset += kQrdiscNumpyBufferSize) {
    result += qrdisc_pairwise_sum(
        data + offset, std::min(kQrdiscNumpyBufferSize, count - offset));
  }
  *out = result;
  return true;
}

bool qrdisc_np_dot_f64(const double* left, const double* right,
                       std::int64_t count, double* out) {
  PyObject* numpy = qrdisc_numpy_module();
  if (numpy == nullptr) return false;
  PyObject* left_array = qrdisc_borrowed_array(left, count, NPY_FLOAT64);
  if (left_array == nullptr) return false;
  PyObject* right_array = qrdisc_borrowed_array(right, count, NPY_FLOAT64);
  if (right_array == nullptr) {
    Py_DECREF(left_array);
    return false;
  }
  PyObject* result =
      PyObject_CallMethod(numpy, "dot", "OO", left_array, right_array);
  Py_DECREF(left_array);
  Py_DECREF(right_array);
  if (result == nullptr) return false;
  *out = PyFloat_AsDouble(result);
  Py_DECREF(result);
  return !(*out == -1.0 && PyErr_Occurred());
}

bool qrdisc_ledger_field(QrdiscPlaneObject* plane, const char* field,
                         QrdiscRaggedField* out) {
  const std::string base = std::string("ledger__") + field;
  // `cumulative` is the ONE 2-D ledger member; every other field is a vector
  // (qrdisc_state_marshal.py:100-102, which names it as the 2-D member that
  // keeps its second axis).  Both are int64: _TickLedger holds nothing else
  // (discretionary_features.py:323-348).
  const int values_ndim = std::string(field) == "cumulative" ? 2 : 1;
  const QrdiscBuffer* values = qrdisc_plane_buffer_named(
      plane, (base + "__values").c_str(), NPY_INT64, values_ndim);
  const QrdiscBuffer* offsets = qrdisc_plane_buffer_named(
      plane, (base + "__offsets").c_str(), NPY_INT64, 1);
  if (values == nullptr || offsets == nullptr) return false;
  out->values = static_cast<const std::int64_t*>(values->data);
  out->offsets = static_cast<const std::int64_t*>(offsets->data);
  out->columns = values->ndim == 2 ? static_cast<std::int64_t>(values->shape[1]) : 1;
  return true;
}

bool qrdisc_ledger_slot(QrdiscPlaneObject* plane, std::int64_t tick,
                        std::int64_t* slot) {
  // A MISSING `ledger__ticks` buffer and a tick with no ledger are two
  // different facts (R6 F5).  The old int64 return collapsed them into -1, so a
  // plane marshalled without the ledger silently took the oracle's
  // `if ledger is None: continue` branch for EVERY tick and emitted a plausible
  // all-zero row.  The KeyError qrdisc_plane_buffer_named set now propagates.
  const QrdiscBuffer* ticks =
      qrdisc_plane_buffer_named(plane, "ledger__ticks", NPY_INT64, 1);
  if (ticks == nullptr) return false;
  const QrdiscI64Span span{static_cast<const std::int64_t*>(ticks->data),
                           static_cast<std::int64_t>(ticks->shape[0])};
  const std::int64_t found = qrdisc_searchsorted_left_i64(span, tick);
  *slot = (found >= span.count || span.data[found] != tick) ? -1 : found;
  return true;
}

std::int64_t qrdisc_peak_count(const std::int64_t* timestamps,
                               std::int64_t count, std::int64_t width_ns) {
  std::int64_t left = 0;
  std::int64_t best = 0;
  for (std::int64_t right = 0; right < count; ++right) {
    while (timestamps[right] - timestamps[left] >= width_ns) ++left;
    best = std::max(best, right - left + 1);
  }
  return best;
}

bool qrdisc_slope(const double* values, std::int64_t count, double* out) {
  *out = 0.0;
  if (count < 2) return true;
  std::vector<double> x(static_cast<std::size_t>(count));
  for (std::int64_t index = 0; index < count; ++index) {
    x[static_cast<std::size_t>(index)] = static_cast<double>(index);
  }
  double x_mean = 0.0;
  if (!qrdisc_np_mean_f64(x.data(), count, &x_mean)) return false;
  std::vector<double> centered(static_cast<std::size_t>(count));
  for (std::int64_t index = 0; index < count; ++index) {
    centered[static_cast<std::size_t>(index)] =
        x[static_cast<std::size_t>(index)] - x_mean;
  }
  double denominator = 0.0;
  if (!qrdisc_np_dot_f64(centered.data(), centered.data(), count, &denominator)) {
    return false;
  }
  if (!(denominator > 0.0)) return true;
  double value_mean = 0.0;
  if (!qrdisc_np_mean_f64(values, count, &value_mean)) return false;
  std::vector<double> deviations(static_cast<std::size_t>(count));
  for (std::int64_t index = 0; index < count; ++index) {
    deviations[static_cast<std::size_t>(index)] =
        values[static_cast<std::size_t>(index)] - value_mean;
  }
  double numerator = 0.0;
  if (!qrdisc_np_dot_f64(centered.data(), deviations.data(), count, &numerator)) {
    return false;
  }
  *out = numerator / denominator;
  return true;
}

namespace {

// One (timestamps, columns...) contribution of a single tick, kept until every
// tick in the radius has been visited so the concatenation order below is the
// oracle's own tick order (discretionary_features.py:1882-1886).
struct QrdiscStreamChunk {
  const std::int64_t* ts;
  const std::int64_t* first;
  const std::int64_t* second;  // nullptr for attack/lift
  std::int64_t count;
};

// np.concatenate over the chunks then `np.argsort(kind="stable")`: a stable
// sort of (chunk order, position) by timestamp is the same permutation.
void qrdisc_merge_chunks(const std::vector<QrdiscStreamChunk>& chunks,
                         QrdiscEventStream* out) {
  std::int64_t total = 0;
  for (const QrdiscStreamChunk& chunk : chunks) total += chunk.count;
  std::vector<std::pair<std::int64_t, std::int64_t>> flat;
  flat.reserve(static_cast<std::size_t>(total));
  for (std::size_t index = 0; index < chunks.size(); ++index) {
    for (std::int64_t position = 0; position < chunks[index].count; ++position) {
      flat.emplace_back(chunks[index].ts[position],
                        static_cast<std::int64_t>(index) * (total + 1) + position);
    }
  }
  std::stable_sort(flat.begin(), flat.end(),
                   [](const std::pair<std::int64_t, std::int64_t>& left,
                      const std::pair<std::int64_t, std::int64_t>& right) {
                     return left.first < right.first;
                   });
  out->ts.reserve(flat.size());
  out->first.reserve(flat.size());
  const bool has_second = !chunks.empty() && chunks[0].second != nullptr;
  if (has_second) out->second.reserve(flat.size());
  for (const std::pair<std::int64_t, std::int64_t>& entry : flat) {
    const std::size_t chunk = static_cast<std::size_t>(entry.second / (total + 1));
    const std::int64_t position = entry.second % (total + 1);
    out->ts.push_back(entry.first);
    out->first.push_back(chunks[chunk].first[position]);
    if (has_second) out->second.push_back(chunks[chunk].second[position]);
  }
}

}  // namespace

bool qrdisc_event_streams(QrdiscPlaneObject* plane, std::int64_t center_tick,
                          std::int64_t radius, std::int64_t left_ns,
                          std::int64_t right_ns, std::int64_t side,
                          QrdiscEventStreams* out) {
  // The four (timestamp field, column fields) triples the oracle picks by side
  // (discretionary_features.py:1839-1856), in its own bucket order.
  const bool aligned = side > 0;
  const char* const timestamp_fields[4] = {
      aligned ? "sell_ts_ns" : "buy_ts_ns",
      aligned ? "buy_ts_ns" : "sell_ts_ns",
      aligned ? "bid_reload_ts_ns" : "ask_reload_ts_ns",
      aligned ? "bid_pull_ts_ns" : "ask_pull_ts_ns"};
  const char* const first_fields[4] = {
      aligned ? "sell_event_size" : "buy_event_size",
      aligned ? "buy_event_size" : "sell_event_size",
      aligned ? "bid_reload_latency_ns" : "ask_reload_latency_ns",
      aligned ? "bid_pull_lifetime_ns" : "ask_pull_lifetime_ns"};
  const char* const second_fields[4] = {
      nullptr, nullptr, aligned ? "bid_reload_size" : "ask_reload_size",
      aligned ? "bid_pull_size" : "ask_pull_size"};

  QrdiscEventStream* streams[4] = {&out->attack, &out->lift, &out->reload,
                                   &out->pull};
  for (int bucket = 0; bucket < 4; ++bucket) {
    QrdiscRaggedField timestamps{};
    QrdiscRaggedField first{};
    QrdiscRaggedField second{};
    if (!qrdisc_ledger_field(plane, timestamp_fields[bucket], &timestamps) ||
        !qrdisc_ledger_field(plane, first_fields[bucket], &first)) {
      return false;
    }
    if (second_fields[bucket] != nullptr &&
        !qrdisc_ledger_field(plane, second_fields[bucket], &second)) {
      return false;
    }
    std::vector<QrdiscStreamChunk> chunks;
    for (std::int64_t tick = center_tick - radius; tick <= center_tick + radius;
         ++tick) {
      std::int64_t slot = 0;
      if (!qrdisc_ledger_slot(plane, tick, &slot)) return false;
      if (slot < 0) continue;  // the oracle's `if ledger is None: continue`
      const std::int64_t begin = timestamps.offsets[slot];
      const QrdiscI64Span group{timestamps.values + begin,
                                timestamps.offsets[slot + 1] - begin};
      const std::int64_t left = qrdisc_searchsorted_left_i64(group, left_ns);
      const std::int64_t right = qrdisc_searchsorted_left_i64(group, right_ns);
      if (right <= left) continue;
      chunks.push_back(QrdiscStreamChunk{
          group.data + left, first.values + first.offsets[slot] + left,
          second_fields[bucket] == nullptr
              ? nullptr
              : second.values + second.offsets[slot] + left,
          right - left});
    }
    qrdisc_merge_chunks(chunks, streams[bucket]);
  }
  return true;
}

bool qrdisc_ledger_sum(QrdiscPlaneObject* plane, std::int64_t center_tick,
                       std::int64_t radius, std::int64_t left_sec,
                       std::int64_t right_sec, QrdiscLedgerSum* out) {
  QrdiscRaggedField seconds{};
  QrdiscRaggedField cumulative{};
  QrdiscRaggedField buy_burst{};
  QrdiscRaggedField sell_burst{};
  QrdiscRaggedField buy_seconds{};
  QrdiscRaggedField sell_seconds{};
  QrdiscRaggedField buy_volume{};
  QrdiscRaggedField sell_volume{};
  if (!qrdisc_ledger_field(plane, "seconds", &seconds) ||
      !qrdisc_ledger_field(plane, "cumulative", &cumulative) ||
      !qrdisc_ledger_field(plane, "buy_burst_cumulative", &buy_burst) ||
      !qrdisc_ledger_field(plane, "sell_burst_cumulative", &sell_burst) ||
      !qrdisc_ledger_field(plane, "buy_seconds", &buy_seconds) ||
      !qrdisc_ledger_field(plane, "sell_seconds", &sell_seconds) ||
      !qrdisc_ledger_field(plane, "buy_second_volume", &buy_volume) ||
      !qrdisc_ledger_field(plane, "sell_second_volume", &sell_volume)) {
    return false;
  }
  // The metric width is the marshalled name tuple's length, NOT `cumulative`'s
  // second axis (R6 F14): a cumulative that lost its second axis used to read
  // as one metric and silently emit a one-entry totals vector.  The two must
  // agree, and a disagreement is a refusal naming both.
  PyObject* metric_names =
      PyDict_GetItemString(plane->scalars, "ledger_metrics");
  if (metric_names == nullptr || !PyTuple_Check(metric_names)) {
    PyErr_SetString(PyExc_KeyError,
                    "qrdisc: scalar 'ledger_metrics' is missing or is not a "
                    "tuple of metric names");
    return false;
  }
  const std::int64_t metrics =
      static_cast<std::int64_t>(PyTuple_GET_SIZE(metric_names));
  if (cumulative.columns != metrics) {
    PyErr_Format(PyExc_ValueError,
                 "qrdisc: ledger 'cumulative' carries %lld columns but the "
                 "marshalled 'ledger_metrics' names %lld metrics",
                 static_cast<long long>(cumulative.columns),
                 static_cast<long long>(metrics));
    return false;
  }
  out->totals.assign(static_cast<std::size_t>(metrics), 0);
  out->buy_bursts = 0;
  out->sell_bursts = 0;
  out->last_buy = -1;
  out->last_sell = -1;
  out->max_buy = 0;
  out->max_sell = 0;
  for (std::int64_t tick = center_tick - radius; tick <= center_tick + radius;
       ++tick) {
    std::int64_t slot = 0;
    if (!qrdisc_ledger_slot(plane, tick, &slot)) return false;
    if (slot < 0) continue;  // the oracle's `if ledger is None: continue`
    const std::int64_t begin = seconds.offsets[slot];
    const QrdiscI64Span group{seconds.values + begin,
                              seconds.offsets[slot + 1] - begin};
    const std::int64_t left = qrdisc_searchsorted_left_i64(group, left_sec);
    const std::int64_t right = qrdisc_searchsorted_left_i64(group, right_sec);
    const std::int64_t* rows =
        cumulative.values + cumulative.offsets[slot] * metrics;
    for (std::int64_t metric = 0; metric < metrics; ++metric) {
      out->totals[static_cast<std::size_t>(metric)] +=
          rows[right * metrics + metric] - rows[left * metrics + metric];
    }
    const std::int64_t* buy_burst_rows = buy_burst.values + buy_burst.offsets[slot];
    const std::int64_t* sell_burst_rows = sell_burst.values + sell_burst.offsets[slot];
    out->buy_bursts += buy_burst_rows[right] - buy_burst_rows[left];
    out->sell_bursts += sell_burst_rows[right] - sell_burst_rows[left];

    const std::int64_t buy_begin = buy_seconds.offsets[slot];
    const QrdiscI64Span buy_group{buy_seconds.values + buy_begin,
                                  buy_seconds.offsets[slot + 1] - buy_begin};
    const std::int64_t buy_left = qrdisc_searchsorted_left_i64(buy_group, left_sec);
    const std::int64_t buy_right = qrdisc_searchsorted_left_i64(buy_group, right_sec);
    const std::int64_t sell_begin = sell_seconds.offsets[slot];
    const QrdiscI64Span sell_group{sell_seconds.values + sell_begin,
                                   sell_seconds.offsets[slot + 1] - sell_begin};
    const std::int64_t sell_left = qrdisc_searchsorted_left_i64(sell_group, left_sec);
    const std::int64_t sell_right = qrdisc_searchsorted_left_i64(sell_group, right_sec);
    if (buy_right > buy_left) {
      out->last_buy = std::max(out->last_buy, buy_group.data[buy_right - 1]);
      const std::int64_t* volumes = buy_volume.values + buy_volume.offsets[slot];
      out->max_buy = std::max(
          out->max_buy, *std::max_element(volumes + buy_left, volumes + buy_right));
    }
    if (sell_right > sell_left) {
      out->last_sell = std::max(out->last_sell, sell_group.data[sell_right - 1]);
      const std::int64_t* volumes = sell_volume.values + sell_volume.offsets[slot];
      out->max_sell = std::max(
          out->max_sell,
          *std::max_element(volumes + sell_left, volumes + sell_right));
    }
  }
  return true;
}
