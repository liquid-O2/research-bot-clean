// qrdisc native families: `_regime_map` (discretionary_features.py:2226) and
// `_target_map` (:2272).
//
// `_target_map` is the first family that reads MARSHALLED SESSION STATE rather
// than the candidate: it needs `_profile_at` for both the session and the
// phase-scoped start, which only exists in the buffers because
// qrdisc_state_marshal.qrdisc_warm_plane_caches built the phase-scoped series
// before marshalling.  An unwarmed start is a refusal here, never a silent
// "no profile": that would emit a plausible, wrong row.
#include "qr_entry_v2/qrdisc_maps.hpp"

#include <algorithm>
#include <cmath>

namespace {

constexpr std::int64_t kProfileIntervalSec = 300;  // PROFILE_INTERVAL_SEC

// The seven level ticks `_target_map` reads out of one `_ProfileState`
// (discretionary_features.py:2280-2283 and :2292-2297), in the oracle's order.
// Order is irrelevant to the output — the distances are set-deduped and sorted
// — but it keeps the transcription readable against the source.
const char* const kQrdiscTargetLevelFields[] = {
    "low_tick", "val_tick", "poc_tick", "vah_tick", "high_tick",
    "nearest_hvn_tick", "nearest_lvn_tick"};

struct QrdiscProfileLookup {
  bool present;
  const std::int64_t* integers;  // row of profile__int_values, or nullptr
};

// `_profile_at` (discretionary_features.py:843) against the marshalled cache.
bool qrdisc_profile_at(QrdiscPlaneObject* plane, const char* prefix,
                       std::int64_t start_sec, std::int64_t snapshot_sec,
                       QrdiscProfileLookup* out) {
  out->present = false;
  out->integers = nullptr;
  const std::string base(prefix);
  const QrdiscBuffer* starts = qrdisc_plane_buffer_named(plane, (base + "__starts").c_str(), NPY_INT64, 1);
  const QrdiscBuffer* offsets = qrdisc_plane_buffer_named(plane, (base + "__offsets").c_str(), NPY_INT64, 1);
  const QrdiscBuffer* present = qrdisc_plane_buffer_named(plane, (base + "__present").c_str(), NPY_UINT8, 1);
  const QrdiscBuffer* integers = qrdisc_plane_buffer_named(plane, (base + "__int_values").c_str(), NPY_INT64, 2);
  if (starts == nullptr || offsets == nullptr || present == nullptr || integers == nullptr) {
    return false;
  }
  const std::int64_t start = start_sec > 0 ? start_sec : 0;
  const std::int64_t* start_values = static_cast<const std::int64_t*>(starts->data);
  npy_intp slot = -1;
  for (npy_intp index = 0; index < starts->shape[0]; ++index) {
    if (start_values[index] == start) {
      slot = index;
      break;
    }
  }
  if (slot < 0) {
    PyErr_Format(plane->refusal_type,
                 "qrdisc: profile cache '%s' has no series for start=%lld; the "
                 "plane was marshalled without warming that key, so the native "
                 "family would silently answer 'no profile'",
                 prefix, static_cast<long long>(start));
    return false;
  }
  const std::int64_t* offset_values = static_cast<const std::int64_t*>(offsets->data);
  const std::int64_t ordinal =
      qrdisc_floor_div(snapshot_sec - start, kProfileIntervalSec) - 1;
  const std::int64_t begin = offset_values[slot];
  const std::int64_t length = offset_values[slot + 1] - begin;
  if (ordinal < 0 || ordinal >= length) return true;  // the absent branch
  const std::int64_t row = begin + ordinal;
  out->present = static_cast<const std::uint8_t*>(present->data)[row] != 0;
  out->integers = static_cast<const std::int64_t*>(integers->data) +
                  row * static_cast<std::int64_t>(integers->shape[1]);
  return true;
}

bool qrdisc_scalar_double(QrdiscPlaneObject* plane, const char* name, double* out) {
  PyObject* value = PyDict_GetItemString(plane->scalars, name);
  if (value == nullptr) {
    PyErr_Format(PyExc_KeyError, "qrdisc: scalar '%s' is missing", name);
    return false;
  }
  *out = PyFloat_AsDouble(value);
  return !(*out == -1.0 && PyErr_Occurred());
}

bool qrdisc_scalar_int64(QrdiscPlaneObject* plane, const char* name, std::int64_t* out) {
  PyObject* value = PyDict_GetItemString(plane->scalars, name);
  if (value == nullptr) {
    PyErr_Format(PyExc_KeyError, "qrdisc: scalar '%s' is missing", name);
    return false;
  }
  return qrdisc_as_int64(value, name, out);
}

}  // namespace

bool qrdisc_regime_map(QrdiscPlaneObject* plane, const QrdiscRowInputs& row,
                       QrdiscValueMap* out) {
  const QrdiscBuffer* last_mid = qrdisc_plane_buffer_named(plane, "attr___last_mid", NPY_INT64, 1);
  if (last_mid == nullptr) return false;
  const std::int64_t* mids = static_cast<const std::int64_t*>(last_mid->data);
  double factor = 0.0;
  if (!qrdisc_scalar_double(plane, "factor", &factor)) return false;

  const std::int64_t horizons[3] = {60, 300, 1800};
  double range_usd[3] = {};
  double path_efficiency[3] = {};
  for (int index = 0; index < 3; ++index) {
    const std::int64_t horizon = horizons[index];
    const std::int64_t begin =
        row.snapshot_sec - horizon > 0 ? row.snapshot_sec - horizon : 0;
    const QrdiscMidWindow window = qrdisc_mid_window(mids, begin, row.snapshot_sec);
    const std::string prefix = "disc_regime_h" + std::to_string(horizon) + "_";
    if (window.count < 2) {
      out->emplace_back(prefix + "range_usd", 0.0);
      out->emplace_back(prefix + "displacement_usd", 0.0);
      out->emplace_back(prefix + "aligned_displacement_usd", 0.0);
      out->emplace_back(prefix + "path_variation_usd", 0.0);
      out->emplace_back(prefix + "path_efficiency", 0.0);
      out->emplace_back(prefix + "range_position", 0.0);
      continue;
    }
    const double displacement = static_cast<double>(window.last - window.first) * factor;
    const double variation = static_cast<double>(window.absolute_variation) * factor;
    const double span = static_cast<double>(window.highest - window.lowest) * factor;
    const std::int64_t width = window.highest - window.lowest;
    range_usd[index] = span;
    path_efficiency[index] = variation != 0.0 ? std::fabs(displacement) / variation : 0.0;
    out->emplace_back(prefix + "range_usd", span);
    out->emplace_back(prefix + "displacement_usd", displacement);
    out->emplace_back(prefix + "aligned_displacement_usd",
                      static_cast<double>(row.side) * displacement);
    out->emplace_back(prefix + "path_variation_usd", variation);
    out->emplace_back(prefix + "path_efficiency", path_efficiency[index]);
    out->emplace_back(prefix + "range_position",
                      static_cast<double>(row.current_mid2 - window.lowest) /
                          static_cast<double>(width > 1 ? width : 1));
  }
  out->emplace_back("disc_regime_efficiency_60_over_1800",
                    (path_efficiency[0] + .01) / (path_efficiency[2] + .01));
  out->emplace_back("disc_regime_range_60_over_1800",
                    (range_usd[0] + 1.0) / (range_usd[2] + 1.0));
  out->emplace_back("disc_regime_range_300_over_1800",
                    (range_usd[1] + 1.0) / (range_usd[2] + 1.0));
  return true;
}

bool qrdisc_target_map(QrdiscPlaneObject* plane, const QrdiscRowInputs& row,
                       double atr_usd, QrdiscValueMap* out) {
  std::int64_t raw_tick = 0;
  std::int64_t multiplier = 0;
  if (!qrdisc_scalar_int64(plane, "raw_tick", &raw_tick) ||
      !qrdisc_scalar_int64(plane, "multiplier", &multiplier)) {
    return false;
  }
  Py_ssize_t columns[7];
  for (int index = 0; index < 7; ++index) {
    columns[index] = qrdisc_scalar_field_index(plane, "profile_int_fields",
                                               kQrdiscTargetLevelFields[index]);
    if (columns[index] < 0) return false;
  }
  std::vector<double> levels;
  const std::int64_t starts[2] = {0, row.phase_open_sec};
  for (const std::int64_t start : starts) {
    QrdiscProfileLookup state{false, nullptr};
    if (!qrdisc_profile_at(plane, "profile", start, row.snapshot_sec, &state)) return false;
    if (!state.present) continue;
    for (const Py_ssize_t column : columns) {
      levels.push_back(static_cast<double>(state.integers[column]));
    }
  }
  PyObject* prior_present = PyDict_GetItemString(plane->scalars, "prior_present");
  if (prior_present == nullptr) {
    PyErr_SetString(PyExc_KeyError, "qrdisc: scalar 'prior_present' is missing");
    return false;
  }
  if (PyObject_IsTrue(prior_present) == 1) {
    std::int64_t low_mid2 = 0;
    std::int64_t close_mid2 = 0;
    std::int64_t high_mid2 = 0;
    if (!qrdisc_scalar_int64(plane, "prior_low_mid2", &low_mid2) ||
        !qrdisc_scalar_int64(plane, "prior_close_mid2", &close_mid2) ||
        !qrdisc_scalar_int64(plane, "prior_high_mid2", &high_mid2)) {
      return false;
    }
    const double half_tick = 2.0 * static_cast<double>(raw_tick);
    levels.push_back(static_cast<double>(low_mid2) / half_tick);
    levels.push_back(static_cast<double>(close_mid2) / half_tick);
    levels.push_back(static_cast<double>(high_mid2) / half_tick);
    QrdiscProfileLookup prior{false, nullptr};
    // The prior session's profile is marshalled as a one-entry cache at
    // start 0; `_profile_at`'s ordinal arithmetic is bypassed because the
    // oracle reads `prior.profile` directly (discretionary_features.py:2291).
    const QrdiscBuffer* present =
        qrdisc_plane_buffer_named(plane, "prior_profile__present", NPY_UINT8, 1);
    const QrdiscBuffer* integers =
        qrdisc_plane_buffer_named(plane, "prior_profile__int_values", NPY_INT64, 2);
    if (present == nullptr || integers == nullptr) return false;
    prior.present = static_cast<const std::uint8_t*>(present->data)[0] != 0;
    prior.integers = static_cast<const std::int64_t*>(integers->data);
    if (prior.present) {
      for (const Py_ssize_t column : columns) {
        levels.push_back(static_cast<double>(prior.integers[column]));
      }
    }
  }

  const double current_tick =
      static_cast<double>(row.current_mid2) / (2.0 * static_cast<double>(raw_tick));
  const double unit = static_cast<double>(raw_tick) * 1e-9 * static_cast<double>(multiplier);
  std::vector<double> distances;
  distances.reserve(levels.size());
  for (const double level : levels) {
    distances.push_back(static_cast<double>(row.side) * (level - current_tick) * unit);
  }
  std::sort(distances.begin(), distances.end());
  distances.erase(std::unique(distances.begin(), distances.end()), distances.end());
  std::vector<double> forward;
  std::vector<double> behind;
  for (const double distance : distances) {
    if (distance > 0.0) forward.push_back(distance);
    if (distance < 0.0) behind.push_back(-distance);
  }
  std::sort(behind.begin(), behind.end());
  const double room = forward.empty() ? 0.0 : forward.front();
  const double invalidation = behind.empty() ? 0.0 : behind.front();
  double counted[3] = {};
  const double thresholds[3] = {300.0, 600.0, 900.0};
  for (const double distance : forward) {
    for (int index = 0; index < 3; ++index) {
      if (distance <= thresholds[index]) counted[index] += 1.0;
    }
  }
  out->emplace_back("disc_target_forward_present", forward.empty() ? 0.0 : 1.0);
  out->emplace_back("disc_target_next_room_usd", room);
  out->emplace_back("disc_target_second_room_usd",
                    forward.size() > 1 ? forward[1] : 0.0);
  out->emplace_back("disc_target_backward_present", behind.empty() ? 0.0 : 1.0);
  out->emplace_back("disc_target_nearest_invalidation_usd", invalidation);
  out->emplace_back("disc_target_forward_levels_300", counted[0]);
  out->emplace_back("disc_target_forward_levels_600", counted[1]);
  out->emplace_back("disc_target_forward_levels_900", counted[2]);
  out->emplace_back("disc_target_room_over_atr", atr_usd > 0 ? room / atr_usd : 0.0);
  out->emplace_back("disc_target_room_over_invalidation",
                    invalidation > 0 ? room / invalidation : 0.0);
  return true;
}
