// qrdisc native family: `_forward_vol_map` (discretionary_features.py:2029),
// plus the two readers every family shares.
//
// This family is the least entangled one in the map: apart from the session's
// `_last_mid` second-clock it reads nothing but the formation candidate, whose
// values arrive as STRINGS from the capture (`atr14_prev_usd` is
// '2824.8457183145256', not a float).  `float(...)` on a str is a correctly
// rounded decimal parse, so the port calls Python's own conversion rather than
// strtod: two correctly-rounded parsers agree, but only one of them is the
// oracle's, and D-017 compares bits.
#include "qr_entry_v2/qrdisc_maps.hpp"

#include <cmath>

namespace {

constexpr std::int64_t kNanosPerSecond = 1000000000;

void qrdisc_push(QrdiscValueMap* out, const std::string& prefix,
                 const char* name, double value) {
  out->emplace_back(prefix + name, value);
}

// The scope-local values the cross-scope block reads back out of `values`
// (discretionary_features.py:2185-2218).  Held rather than looked up: the
// oracle reads its own dict, and a name lookup per row would be the only place
// in this file where a typo could silently read a neighbouring feature.
struct QrdiscVolScope {
  double sigma_hat_usd;
  double range_hat_usd;
  double move_q50_usd;
  double move_q90_usd;
  double q50_coverage;
  double q90_coverage;
  double q50_remaining_usd;
  double quantile_curvature_usd;
  double vintage_sigma_slope_5_usd;
  double vintage_range_slope_5_usd;
  double regime_present;
  double regime_low;
  double regime_mid;
  double regime_high;
};

const char* const kQrdiscVintageNames[] = {
    "vintage_history_present", "vintage_ready_count_5",
    "vintage_ready_count_22", "vintage_sigma_delta_1_usd",
    "vintage_sigma_slope_5_usd", "vintage_sigma_slope_22_usd",
    "vintage_sigma_acceleration_usd", "vintage_range_delta_1_usd",
    "vintage_range_slope_5_usd", "vintage_range_slope_22_usd",
    "vintage_range_acceleration_usd", "vintage_q50_delta_1_usd",
    "vintage_q50_slope_5_usd", "vintage_q50_slope_22_usd",
    "vintage_q50_acceleration_usd", "vintage_q90_delta_1_usd",
    "vintage_q90_slope_5_usd", "vintage_q90_slope_22_usd",
    "vintage_q90_acceleration_usd", "vintage_rv_ratio_delta_1",
    "vintage_rv_ratio_slope_5", "vintage_rv_ratio_slope_22",
    "vintage_rv_ratio_acceleration", "vintage_regime_changed",
    "vintage_regime_persistence"};

}  // namespace

const QrdiscBuffer* qrdisc_plane_buffer_named(QrdiscPlaneObject* plane,
                                              const char* name,
                                              int expected_type_num,
                                              int expected_ndim) {
  for (const QrdiscBuffer& buffer : *plane->buffers) {
    if (buffer.name != name) continue;
    if (buffer.type_num != expected_type_num || buffer.ndim != expected_ndim) {
      PyErr_Format(PyExc_TypeError,
                   "qrdisc: marshalled buffer '%s' is type %d ndim %d, "
                   "expected type %d ndim %d",
                   name, buffer.type_num, buffer.ndim, expected_type_num,
                   expected_ndim);
      return nullptr;
    }
    return &buffer;
  }
  PyErr_Format(PyExc_KeyError,
               "qrdisc: marshalled buffer '%s' is missing; the plane carries "
               "%zd buffers and every native family reads its state through "
               "them",
               name, static_cast<Py_ssize_t>(plane->buffers->size()));
  return nullptr;
}

Py_ssize_t qrdisc_scalar_field_index(QrdiscPlaneObject* plane,
                                     const char* tuple_name, const char* name) {
  PyObject* names = PyDict_GetItemString(plane->scalars, tuple_name);
  if (names == nullptr || !PyTuple_Check(names)) {
    PyErr_Format(PyExc_KeyError,
                 "qrdisc: scalar '%s' is missing or is not a tuple of field "
                 "names",
                 tuple_name);
    return -1;
  }
  const Py_ssize_t count = PyTuple_GET_SIZE(names);
  for (Py_ssize_t index = 0; index < count; ++index) {
    PyObject* candidate = PyTuple_GET_ITEM(names, index);
    const char* text = PyUnicode_AsUTF8(candidate);
    if (text == nullptr) return -1;
    if (std::string(text) == name) return index;
  }
  PyErr_Format(PyExc_KeyError,
               "qrdisc: field '%s' is not in scalar '%s' (%zd entries); the "
               "marshalled dataclass no longer carries it",
               name, tuple_name, count);
  return -1;
}

bool qrdisc_candidate_number(PyObject* mapping, const std::string& key,
                             bool clamp_nonfinite, double* out) {
  *out = 0.0;
  PyObject* item = PyMapping_GetItemString(mapping, key.c_str());
  if (item == nullptr) {
    // `.get(key, 0.0)` — a MISSING key is the default, any other failure is
    // not something the oracle would have swallowed.
    if (!PyErr_ExceptionMatches(PyExc_KeyError)) return false;
    PyErr_Clear();
    return true;
  }
  PyObject* number = PyNumber_Float(item);
  Py_DECREF(item);
  if (number == nullptr) {
    if (!PyErr_ExceptionMatches(PyExc_TypeError) &&
        !PyErr_ExceptionMatches(PyExc_ValueError)) {
      return false;
    }
    PyErr_Clear();
    return true;
  }
  const double value = PyFloat_AS_DOUBLE(number);
  Py_DECREF(number);
  *out = (clamp_nonfinite && !std::isfinite(value)) ? 0.0 : value;
  return true;
}

QrdiscMidWindow qrdisc_mid_window(const std::int64_t* mids, std::int64_t begin,
                                  std::int64_t end) {
  QrdiscMidWindow window{0, 0, 0, 0, 0, 0};
  bool started = false;
  std::int64_t previous = 0;
  for (std::int64_t index = begin; index < end; ++index) {
    const std::int64_t value = mids[index];
    if (value <= 0) continue;  // `mids = mids[mids > 0]`
    if (!started) {
      window.first = value;
      window.lowest = value;
      window.highest = value;
      started = true;
    } else {
      if (value < window.lowest) window.lowest = value;
      if (value > window.highest) window.highest = value;
      const std::int64_t step = value - previous;
      window.absolute_variation += step < 0 ? -step : step;
    }
    previous = value;
    window.last = value;
    ++window.count;
  }
  return window;
}

bool qrdisc_forward_vol_map(QrdiscPlaneObject* plane,
                            const QrdiscRowInputs& row, QrdiscValueMap* out) {
  const QrdiscBuffer* last_mid = qrdisc_plane_buffer_named(plane, "attr___last_mid", NPY_INT64, 1);
  if (last_mid == nullptr) return false;
  const std::int64_t* mids = static_cast<const std::int64_t*>(last_mid->data);
  PyObject* factor_object = PyDict_GetItemString(plane->scalars, "factor");
  if (factor_object == nullptr) {
    PyErr_SetString(PyExc_KeyError, "qrdisc: scalar 'factor' is missing");
    return false;
  }
  const double factor = PyFloat_AsDouble(factor_object);
  if (factor == -1.0 && PyErr_Occurred()) return false;

  const std::int64_t elapsed =
      row.snapshot_sec - row.formation_sec > 0 ? row.snapshot_sec - row.formation_sec : 0;
  QrdiscVolScope scopes[2] = {};
  for (int index = 0; index < 2; ++index) {
    const bool phase = index == 1;
    const std::string scope = phase ? "phase" : "session";
    const std::string prefix = "disc_fvol_" + scope + "_";
    const std::int64_t start = phase ? row.phase_open_sec : 0;
    double present = 0.0, sigma = 0.0, range_hat = 0.0;
    double q10 = 0.0, q25 = 0.0, q50 = 0.0, q75 = 0.0, q90 = 0.0;
    double forecast_age = 0.0;
    const bool read =
        qrdisc_candidate_number(row.formation_candidate, scope + "_forecast_present", true, &present) &&
        qrdisc_candidate_number(row.formation_candidate, scope + "_sigma_hat_usd", true, &sigma) &&
        qrdisc_candidate_number(row.formation_candidate, scope + "_range_hat_usd", true, &range_hat) &&
        qrdisc_candidate_number(row.formation_candidate, scope + "_move_q10_usd", true, &q10) &&
        qrdisc_candidate_number(row.formation_candidate, scope + "_move_q25_usd", true, &q25) &&
        qrdisc_candidate_number(row.formation_candidate, scope + "_move_q50_usd", true, &q50) &&
        qrdisc_candidate_number(row.formation_candidate, scope + "_move_q75_usd", true, &q75) &&
        qrdisc_candidate_number(row.formation_candidate, scope + "_move_q90_usd", true, &q90) &&
        qrdisc_candidate_number(row.formation_candidate, scope + "_forecast_age_sec", true, &forecast_age);
    if (!read) return false;
    const std::int64_t clamped_start = start > 0 ? start : 0;
    const std::int64_t scope_elapsed =
        row.snapshot_sec - clamped_start > 0 ? row.snapshot_sec - clamped_start : 0;
    std::int64_t close_sec = 0;
    if (phase) {
      // `int(candidate.get("phase_close_utc", 0))` with the oracle's fallback
      // to the snapshot second on a value int() will not accept.
      close_sec = row.snapshot_sec;
      PyObject* item = PyMapping_GetItemString(row.formation_candidate, "phase_close_utc");
      if (item == nullptr) {
        if (!PyErr_ExceptionMatches(PyExc_KeyError)) return false;
        PyErr_Clear();
        close_sec = 0 - qrdisc_floor_div(plane->open_ns, kNanosPerSecond);
      } else {
        std::int64_t utc = 0;
        const bool ok = qrdisc_as_int64(item, "phase_close_utc", &utc);
        Py_DECREF(item);
        if (ok) {
          close_sec = utc - qrdisc_floor_div(plane->open_ns, kNanosPerSecond);
        } else if (PyErr_ExceptionMatches(PyExc_TypeError) ||
                   PyErr_ExceptionMatches(PyExc_ValueError)) {
          PyErr_Clear();
        } else {
          return false;
        }
      }
    } else {
      close_sec = plane->duration;
    }
    const std::int64_t remaining_sec =
        close_sec - row.snapshot_sec > 0 ? close_sec - row.snapshot_sec : 0;
    const QrdiscMidWindow window =
        qrdisc_mid_window(mids, clamped_start, row.snapshot_sec);
    const double actual_range =
        window.count == 0 ? 0.0
                          : static_cast<double>(window.highest - window.lowest) * factor;
    const double aligned_displacement =
        static_cast<double>(row.side * (row.current_mid2 - row.formation_mid2)) * factor;
    const bool ladder = q90 >= q75 && q75 >= q50 && q50 >= q25 && q25 >= q10 && q10 > 0;

    // The emitted NAME ORDER is the dict literal's order at :2070-2167,
    // followed by the vintage loop's `values[prefix + name]` at :2168-2182:
    // those names reach the dense store, so order is identity here.
    qrdisc_push(out, prefix, "present", present);
    qrdisc_push(out, prefix, "age_now_sec", forecast_age + static_cast<double>(elapsed));
    qrdisc_push(out, prefix, "sigma_hat_usd", sigma);
    qrdisc_push(out, prefix, "range_hat_usd", range_hat);
    static const char* const kCarried[] = {
        "sigma_components_present", "sigma_raw_hat_usd", "sigma_persistence_usd",
        "sigma_calibration_ratio", "sigma_calibration_count",
        "sigma_calibrated_hat_usd", "sigma_shrinkage_delta_usd",
        "sigma_ols_minus_persistence_usd", "sigma_ols_over_persistence"};
    for (const char* name : kCarried) {
      double value = 0.0;
      if (!qrdisc_candidate_number(row.formation_candidate, scope + "_" + name, true, &value)) {
        return false;
      }
      qrdisc_push(out, prefix, name, value);
    }
    qrdisc_push(out, prefix, "move_q10_usd", q10);
    qrdisc_push(out, prefix, "move_q25_usd", q25);
    qrdisc_push(out, prefix, "move_q50_usd", q50);
    qrdisc_push(out, prefix, "move_q75_usd", q75);
    qrdisc_push(out, prefix, "move_q90_usd", q90);
    // Emitted name and candidate field diverge for the regime flags: the map
    // key is `regime_low`, the candidate field `<scope>_regime_low_present`
    // (discretionary_features.py:2103-2108).
    static const char* const kNamed[][2] = {
        {"rv5_over_rv66", "rv5_over_rv66"},
        {"rv5_over_rv66_present", "rv5_over_rv66_present"},
        {"regime_low", "regime_low_present"},
        {"regime_mid", "regime_mid_present"},
        {"regime_high", "regime_high_present"},
        {"regime_present", "regime_present"},
        {"move_ladder_present", "move_ladder_present"},
        {"unscaled_fallback_present", "unscaled_fallback_present"}};
    double named[8] = {};
    for (int slot = 0; slot < 8; ++slot) {
      if (!qrdisc_candidate_number(row.formation_candidate,
                                   scope + "_" + kNamed[slot][1], true, &named[slot])) {
        return false;
      }
      qrdisc_push(out, prefix, kNamed[slot][0], named[slot]);
    }
    const double q50_coverage = q50 > 0 ? actual_range / q50 : 0.0;
    const double q90_coverage = q90 > 0 ? actual_range / q90 : 0.0;
    const double q50_remaining = q50 - actual_range > 0.0 ? q50 - actual_range : 0.0;
    const double q90_remaining = q90 - actual_range > 0.0 ? q90 - actual_range : 0.0;
    const double curvature =
        (q90 >= q75 && q75 >= q25 && q25 >= q10 && q10 > 0) ? (q90 - q75) - (q25 - q10) : 0.0;
    qrdisc_push(out, prefix, "actual_range_usd", actual_range);
    qrdisc_push(out, prefix, "range_coverage", range_hat > 0 ? actual_range / range_hat : 0.0);
    qrdisc_push(out, prefix, "q50_coverage", q50_coverage);
    qrdisc_push(out, prefix, "q90_coverage", q90_coverage);
    qrdisc_push(out, prefix, "q50_remaining_usd", q50_remaining);
    qrdisc_push(out, prefix, "q90_remaining_usd", q90_remaining);
    qrdisc_push(out, prefix, "aligned_displacement_over_q50",
                q50 > 0 ? aligned_displacement / q50 : 0.0);
    qrdisc_push(out, prefix, "range_surprise_over_q90",
                q90 > 0 ? (actual_range - q90 > 0.0 ? actual_range - q90 : 0.0) / q90 : 0.0);
    qrdisc_push(out, prefix, "range_hat_over_sigma", sigma > 0 ? range_hat / sigma : 0.0);
    qrdisc_push(out, prefix, "iqr_90_10_usd", q90 - q10 > 0.0 ? q90 - q10 : 0.0);
    qrdisc_push(out, prefix, "iqr_75_25_usd", q75 - q25 > 0.0 ? q75 - q25 : 0.0);
    qrdisc_push(out, prefix, "lower_tail_width_usd", q25 - q10 > 0.0 ? q25 - q10 : 0.0);
    qrdisc_push(out, prefix, "lower_center_width_usd", q50 - q25 > 0.0 ? q50 - q25 : 0.0);
    qrdisc_push(out, prefix, "upper_center_width_usd", q75 - q50 > 0.0 ? q75 - q50 : 0.0);
    qrdisc_push(out, prefix, "upper_tail_width_usd", q90 - q75 > 0.0 ? q90 - q75 : 0.0);
    qrdisc_push(out, prefix, "tail_width_asymmetry",
                ladder ? ((q90 - q75) - (q25 - q10)) /
                             (1.0 > q90 - q10 ? 1.0 : q90 - q10)
                       : 0.0);
    qrdisc_push(out, prefix, "center_width_asymmetry",
                (q75 >= q50 && q50 >= q25 && q25 > 0)
                    ? ((q75 - q50) - (q50 - q25)) / (1.0 > q75 - q25 ? 1.0 : q75 - q25)
                    : 0.0);
    qrdisc_push(out, prefix, "quantile_slope_usd",
                (q90 >= q10 && q10 > 0) ? (q90 - q10) / .8 : 0.0);
    qrdisc_push(out, prefix, "quantile_curvature_usd", curvature);
    qrdisc_push(out, prefix, "q90_over_q50", q50 > 0 ? q90 / q50 : 0.0);
    qrdisc_push(out, prefix, "q50_over_sigma", sigma > 0 ? q50 / sigma : 0.0);
    qrdisc_push(out, prefix, "q90_over_sigma", sigma > 0 ? q90 / sigma : 0.0);
    qrdisc_push(out, prefix, "ladder_monotone", ladder ? 1.0 : 0.0);
    qrdisc_push(out, prefix, "scope_elapsed_sec", static_cast<double>(scope_elapsed));
    qrdisc_push(out, prefix, "scope_remaining_sec", static_cast<double>(remaining_sec));
    qrdisc_push(out, prefix, "range_consumption_usd_per_min",
                scope_elapsed > 0 ? actual_range * 60.0 / static_cast<double>(scope_elapsed) : 0.0);
    qrdisc_push(out, prefix, "q50_consumption_fraction_per_min",
                (scope_elapsed > 0 && q50 > 0)
                    ? actual_range / q50 * 60.0 / static_cast<double>(scope_elapsed)
                    : 0.0);
    qrdisc_push(out, prefix, "q90_consumption_fraction_per_min",
                (scope_elapsed > 0 && q90 > 0)
                    ? actual_range / q90 * 60.0 / static_cast<double>(scope_elapsed)
                    : 0.0);
    qrdisc_push(out, prefix, "q50_headroom_usd_per_remaining_min",
                remaining_sec > 0 ? q50_remaining * 60.0 / static_cast<double>(remaining_sec) : 0.0);
    qrdisc_push(out, prefix, "q90_headroom_usd_per_remaining_min",
                remaining_sec > 0 ? q90_remaining * 60.0 / static_cast<double>(remaining_sec) : 0.0);
    qrdisc_push(out, prefix, "q50_overshoot_usd",
                actual_range - q50 > 0.0 ? actual_range - q50 : 0.0);
    qrdisc_push(out, prefix, "q90_overshoot_usd",
                actual_range - q90 > 0.0 ? actual_range - q90 : 0.0);
    QrdiscVolScope& held = scopes[index];
    for (const char* name : kQrdiscVintageNames) {
      double value = 0.0;
      if (!qrdisc_candidate_number(row.formation_candidate, scope + "_" + name, true, &value)) {
        return false;
      }
      qrdisc_push(out, prefix, name, value);
      if (std::string(name) == "vintage_sigma_slope_5_usd") held.vintage_sigma_slope_5_usd = value;
      if (std::string(name) == "vintage_range_slope_5_usd") held.vintage_range_slope_5_usd = value;
    }
    held.sigma_hat_usd = sigma;
    held.range_hat_usd = range_hat;
    held.move_q50_usd = q50;
    held.move_q90_usd = q90;
    held.q50_coverage = q50_coverage;
    held.q90_coverage = q90_coverage;
    held.q50_remaining_usd = q50_remaining;
    held.quantile_curvature_usd = curvature;
    held.regime_present = named[5];
    held.regime_low = named[2];
    held.regime_mid = named[3];
    held.regime_high = named[4];
  }

  const QrdiscVolScope& session = scopes[0];
  const QrdiscVolScope& phase = scopes[1];
  const std::string cross = "disc_fvol_cross_";
  // The emitted NAME ORDER is the cross-scope dict literal's order at
  // :2191-2223, whose last entry is the intraday-revision flag at :2219-2222.
  qrdisc_push(out, cross, "sigma_phase_minus_session_usd",
              phase.sigma_hat_usd - session.sigma_hat_usd);
  qrdisc_push(out, cross, "sigma_phase_over_session",
              session.sigma_hat_usd != 0.0 ? phase.sigma_hat_usd / session.sigma_hat_usd : 0.0);
  qrdisc_push(out, cross, "range_phase_minus_session_usd",
              phase.range_hat_usd - session.range_hat_usd);
  qrdisc_push(out, cross, "range_phase_over_session",
              session.range_hat_usd != 0.0 ? phase.range_hat_usd / session.range_hat_usd : 0.0);
  qrdisc_push(out, cross, "q50_phase_minus_session_usd",
              phase.move_q50_usd - session.move_q50_usd);
  qrdisc_push(out, cross, "q50_phase_over_session",
              session.move_q50_usd != 0.0 ? phase.move_q50_usd / session.move_q50_usd : 0.0);
  qrdisc_push(out, cross, "q90_phase_minus_session_usd",
              phase.move_q90_usd - session.move_q90_usd);
  qrdisc_push(out, cross, "q90_phase_over_session",
              session.move_q90_usd != 0.0 ? phase.move_q90_usd / session.move_q90_usd : 0.0);
  qrdisc_push(out, cross, "q50_coverage_disagreement",
              phase.q50_coverage - session.q50_coverage);
  qrdisc_push(out, cross, "q90_coverage_disagreement",
              phase.q90_coverage - session.q90_coverage);
  qrdisc_push(out, cross, "q50_remaining_disagreement_usd",
              phase.q50_remaining_usd - session.q50_remaining_usd);
  qrdisc_push(out, cross, "quantile_curvature_disagreement_usd",
              phase.quantile_curvature_usd - session.quantile_curvature_usd);
  qrdisc_push(out, cross, "vintage_sigma_slope_5_disagreement_usd",
              phase.vintage_sigma_slope_5_usd - session.vintage_sigma_slope_5_usd);
  qrdisc_push(out, cross, "vintage_range_slope_5_disagreement_usd",
              phase.vintage_range_slope_5_usd - session.vintage_range_slope_5_usd);
  qrdisc_push(out, cross, "regime_disagreement",
              (session.regime_present > 0 && phase.regime_present > 0 &&
               (session.regime_low != phase.regime_low ||
                session.regime_mid != phase.regime_mid ||
                session.regime_high != phase.regime_high))
                  ? 1.0
                  : 0.0);
  // One open-time vintage per day in the present QRE2 artifact
  // (discretionary_features.py:2219-2222): typed unavailable, not absent.
  out->emplace_back("disc_fvol_intraday_revision_available", 0.0);
  return true;
}
