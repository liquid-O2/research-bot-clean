// The family fan-out of `CausalDiscretionaryPlane.feature_map`, transcribed
// call site by call site from discretionary_features.py:2404-2500.
//
// Read the ordering law and the delegation contract in
// include/qr_entry_v2/qrdisc_assembly.hpp.  The merged-map mechanism is in
// qrdisc_assembly_merge.cpp and the tail (:2502-2694) in
// qrdisc_assembly_tail.cpp, so each file stays inside one read.
//
// EVERY ARGUMENT IS THE ORACLE'S OWN
//   feature_map hands some arguments through UNCONVERTED (`side=side`,
//   `current_mid2=current_mid2`, `formation_candidate=formation_candidate`) and
//   converts others with `int()` (`snapshot_ts_ns=int(snapshot_ts_ns)`,
//   `formation_sec`, `formation_mid2`, the ticks).  That split is reproduced
//   exactly: the raw objects travel in QrdiscRowObjects, the converted ones are
//   boxed once per row in QrdiscRowInts.
#include "qr_entry_v2/qrdisc_assembly.hpp"

#include <cstdio>
#include <string>

namespace {

// Every family feature_map calls, plus `_state_series` which the tail calls.
// A name here maps in the delegation table either to the oracle's bound method
// or to None (the port owns it); absent means the row cannot be assembled.
const char* const kQrdiscAssemblyFamilies[] = {
    "_profile_map",             "_initial_balance_map",
    "_forward_vol_map",         "_regime_map",
    "_target_map",              "_level_values",
    "_prior_reaction_map",      "_event_clock_map",
    "_trade_clock_map",         "_volume_clock_map",
    "_tape_slope_map",          "_test_maturity_map",
    "_best_quote_response_map", "_event_micro_map",
    "_price_shape_values",      "_state_series",
};

// The int arguments feature_map converts with `int()` before passing them on,
// boxed once per row.  A raw argument is NOT here: it travels unconverted.
struct QrdiscRowInts {
  PyObject* snapshot_sec = nullptr;
  PyObject* phase_open_sec = nullptr;
  PyObject* formation_sec = nullptr;
  PyObject* formation_tick = nullptr;
  PyObject* current_tick = nullptr;
  PyObject* snapshot_ts_ns = nullptr;
  PyObject* formation_ts_ns = nullptr;
  PyObject* formation_mid2 = nullptr;
  PyObject* atr_usd = nullptr;
  PyObject* zero = nullptr;
  PyObject* radius2 = nullptr;
  PyObject* radius4 = nullptr;

  ~QrdiscRowInts() {
    Py_XDECREF(snapshot_sec);
    Py_XDECREF(phase_open_sec);
    Py_XDECREF(formation_sec);
    Py_XDECREF(formation_tick);
    Py_XDECREF(current_tick);
    Py_XDECREF(snapshot_ts_ns);
    Py_XDECREF(formation_ts_ns);
    Py_XDECREF(formation_mid2);
    Py_XDECREF(atr_usd);
    Py_XDECREF(zero);
    Py_XDECREF(radius2);
    Py_XDECREF(radius4);
  }

  // The boxes built BEFORE the first family call.  `current_tick`, `atr_usd`
  // and `formation_ts_ns` are deliberately absent: the oracle reads their
  // inputs later in the row (:2434, :2436, :2457) and R6 F9 keeps that read
  // order, so those three are boxed at their own positions in the fan-out.
  bool complete() const {
    return snapshot_sec && phase_open_sec && formation_sec && formation_tick &&
           snapshot_ts_ns && formation_mid2 && zero && radius2 && radius4;
  }
};

bool qrdisc_family_is_native_here(QrdiscPlaneObject* plane, const char* family) {
  PyObject* entry = PyDict_GetItemString(plane->delegates, family);
  return entry != nullptr && entry == Py_None;
}

// The whole block of a native family, merged where its delegated calls sit.
bool qrdisc_native_block(QrdiscPlaneObject* plane, const char* family,
                         const QrdiscRowInputs& row,
                         QrdiscNativeFamilyFn run_native,
                         QrdiscRowValues* values) {
  QrdiscValueMap map;
  if (!run_native(plane, family, row, &map)) return false;
  for (const std::pair<std::string, double>& entry : map) {
    values->set(entry.first, entry.second);
  }
  return true;
}

}  // namespace

bool qrdisc_assembly_available(QrdiscPlaneObject* plane) {
  for (const char* family : kQrdiscAssemblyFamilies) {
    if (PyDict_GetItemString(plane->delegates, family) == nullptr) return false;
  }
  PyObject* prior = PyDict_GetItemString(plane->scalars, "prior_present");
  if (prior == nullptr) return false;
  // `level_association_mode` is required by BOTH halves — the prior-session
  // call site below (:2417-2423) and the tail's two mode flags (:2688-2691) —
  // so a plane lacking it must take the splice path here, not KeyError from
  // inside the assembly (R6 F12).
  if (PyDict_GetItemString(plane->scalars, "level_association_mode") ==
      nullptr) {
    return false;
  }
  const char* needed = prior == Py_True ? "_prior_session_feature_map"
                                        : "_prior_session_empty_feature_map";
  return PyDict_GetItemString(plane->delegates, needed) != nullptr;
}

bool qrdisc_assemble_families(QrdiscPlaneObject* plane,
                              const QrdiscRowInputs& row,
                              const QrdiscRowObjects& objects,
                              QrdiscNativeFamilyFn run_native,
                              std::int64_t* formation_ts_ns_out,
                              QrdiscRowValues* values) {
  // READ ORDER IS REFUSAL ORDER (R6 F9, D-017).  A malformed candidate must
  // raise from the SAME point in the row as the oracle, so each candidate and
  // quote read sits where feature_map does it.  Only what :2432 needs is read
  // here; `current_bid|current_ask` (:2434), `atr14_prev_usd` (:2436) and
  // `decision_ts_ns` (:2457) are read further down.
  std::int64_t raw_tick = 0;
  std::int64_t formation_bid = 0;
  std::int64_t formation_ask = 0;
  // feature_map:2464 passes `int(snapshot_ts_ns)`.  It is the query ARGUMENT,
  // which the oracle also reads first (:2393), so the row parse's own value is
  // reused rather than re-read.
  const std::int64_t snapshot_ts_ns = row.snapshot_ts_ns;
  PyObject* raw_tick_object = PyDict_GetItemString(plane->scalars, "raw_tick");
  if (raw_tick_object == nullptr) {
    PyErr_SetString(PyExc_KeyError, "qrdisc: scalar 'raw_tick' is missing");
    return false;
  }
  if (!qrdisc_as_int64(raw_tick_object, "raw_tick", &raw_tick) ||
      !qrdisc_mapping_int64(objects.formation, "entry_bid_px", &formation_bid) ||
      !qrdisc_mapping_int64(objects.formation, "entry_ask_px", &formation_ask)) {
    return false;
  }
  const std::int64_t formation_tick = qrdisc_floor_div(
      row.side > 0 ? formation_bid : formation_ask, raw_tick);

  QrdiscRowInts boxed;
  boxed.snapshot_sec = PyLong_FromLongLong(row.snapshot_sec);
  boxed.phase_open_sec = PyLong_FromLongLong(row.phase_open_sec);
  boxed.formation_sec = PyLong_FromLongLong(row.formation_sec);
  boxed.formation_tick = PyLong_FromLongLong(formation_tick);
  boxed.snapshot_ts_ns = PyLong_FromLongLong(snapshot_ts_ns);
  boxed.formation_mid2 = PyLong_FromLongLong(row.formation_mid2);
  boxed.zero = PyLong_FromLongLong(0);
  boxed.radius2 = PyLong_FromLongLong(2);
  boxed.radius4 = PyLong_FromLongLong(4);
  if (!boxed.complete()) return false;

  // :2405-2416 — the two profile scopes, then the two initial-balance scopes.
  static PyObject* const profile_kw = qrdisc_kwnames(
      {"prefix", "start_sec", "snapshot_sec", "current_mid2", "side"});
  const char* const scoped_prefixes[4] = {
      "disc_auction_session_", "disc_auction_phase_", "disc_ib_session_",
      "disc_ib_phase_"};
  for (int scope = 0; scope < 4; ++scope) {
    const char* family = scope < 2 ? "_profile_map" : "_initial_balance_map";
    if (qrdisc_family_is_native_here(plane, family)) {
      if (scope % 2 != 0) continue;  // the native family emitted both scopes
      if (!qrdisc_native_block(plane, family, row, run_native, values)) {
        return false;
      }
      continue;
    }
    PyObject* prefix = PyUnicode_FromString(scoped_prefixes[scope]);
    if (prefix == nullptr) return false;
    PyObject* args[5] = {prefix,
                         (scope % 2 == 0) ? boxed.zero : boxed.phase_open_sec,
                         boxed.snapshot_sec, objects.current_mid2,
                         objects.side};
    const bool merged =
        qrdisc_delegate_into(plane, family, args, profile_kw, values);
    Py_DECREF(prefix);
    if (!merged) return false;
  }

  // :2417-2423 — the prior session, or its empty schema when there is none.
  PyObject* prior_present = PyDict_GetItemString(plane->scalars, "prior_present");
  PyObject* mode = PyDict_GetItemString(plane->scalars, "level_association_mode");
  if (prior_present == nullptr || mode == nullptr) {
    PyErr_SetString(PyExc_KeyError,
                    "qrdisc: scalars 'prior_present' and "
                    "'level_association_mode' are both required");
    return false;
  }
  if (prior_present == Py_True) {
    static PyObject* const prior_kw =
        qrdisc_kwnames({"current_mid2", "formation_bid", "formation_ask",
                        "side", "level_association_mode"});
    PyObject* bid = PyLong_FromLongLong(formation_bid);
    PyObject* ask = PyLong_FromLongLong(formation_ask);
    if (bid == nullptr || ask == nullptr) {
      Py_XDECREF(bid);
      Py_XDECREF(ask);
      return false;
    }
    PyObject* args[5] = {objects.current_mid2, bid, ask, objects.side, mode};
    const bool merged = qrdisc_delegate_into(
        plane, "_prior_session_feature_map", args, prior_kw, values);
    Py_DECREF(bid);
    Py_DECREF(ask);
    if (!merged) return false;
  } else if (!qrdisc_delegate_into(plane, "_prior_session_empty_feature_map",
                                   nullptr, nullptr, values)) {
    return false;
  }

  // :2424-2430 and :2440-2442 — the three families of wave 1.
  static PyObject* const vol_kw = qrdisc_kwnames(
      {"formation_candidate", "formation_sec", "phase_open_sec",
       "snapshot_sec", "current_mid2", "formation_mid2", "side"});
  if (qrdisc_family_is_native_here(plane, "_forward_vol_map")) {
    if (!qrdisc_native_block(plane, "_forward_vol_map", row, run_native,
                             values)) {
      return false;
    }
  } else {
    PyObject* args[7] = {objects.formation,  boxed.formation_sec,
                         boxed.phase_open_sec, boxed.snapshot_sec,
                         objects.current_mid2, boxed.formation_mid2,
                         objects.side};
    if (!qrdisc_delegate_into(plane, "_forward_vol_map", args, vol_kw, values)) {
      return false;
    }
  }
  static PyObject* const regime_kw =
      qrdisc_kwnames({"snapshot_sec", "current_mid2", "side"});
  if (qrdisc_family_is_native_here(plane, "_regime_map")) {
    if (!qrdisc_native_block(plane, "_regime_map", row, run_native, values)) {
      return false;
    }
  } else {
    PyObject* args[3] = {boxed.snapshot_sec, objects.current_mid2,
                         objects.side};
    if (!qrdisc_delegate_into(plane, "_regime_map", args, regime_kw, values)) {
      return false;
    }
  }
  // :2434-2435 — the current quote, read AFTER `_regime_map` because that is
  // where the oracle reads it (R6 F9).
  std::int64_t current_quote = 0;
  if (!qrdisc_as_int64(row.side > 0 ? objects.current_bid : objects.current_ask,
                       row.side > 0 ? "current_bid" : "current_ask",
                       &current_quote)) {
    return false;
  }
  const std::int64_t current_tick = qrdisc_floor_div(current_quote, raw_tick);
  // :2436-2439 — `float(formation_candidate.get("atr14_prev_usd", 0.0))`,
  // WITHOUT the vol family's non-finite clamp.
  double atr_usd = 0.0;
  if (!qrdisc_candidate_number(objects.formation, "atr14_prev_usd", false,
                               &atr_usd)) {
    return false;
  }
  boxed.current_tick = PyLong_FromLongLong(current_tick);
  boxed.atr_usd = PyFloat_FromDouble(atr_usd);
  if (boxed.current_tick == nullptr || boxed.atr_usd == nullptr) return false;

  static PyObject* const target_kw = qrdisc_kwnames(
      {"snapshot_sec", "current_mid2", "side", "phase_open_sec", "atr_usd"});
  if (qrdisc_family_is_native_here(plane, "_target_map")) {
    if (!qrdisc_native_block(plane, "_target_map", row, run_native, values)) {
      return false;
    }
  } else {
    PyObject* args[5] = {boxed.snapshot_sec, objects.current_mid2, objects.side,
                         boxed.phase_open_sec, boxed.atr_usd};
    if (!qrdisc_delegate_into(plane, "_target_map", args, target_kw, values)) {
      return false;
    }
  }

  // :2443-2455 — six level windows around the formation tick, then the one
  // around the CURRENT tick over the last 30 seconds: seven contiguous calls.
  static PyObject* const level_kw =
      qrdisc_kwnames({"prefix", "center_tick", "radius", "left_sec",
                      "right_sec", "side", "age_reference_sec"});
  if (qrdisc_family_is_native_here(plane, "_level_values")) {
    if (!qrdisc_native_block(plane, "_level_values", row, run_native, values)) {
      return false;
    }
  } else {
    const std::int64_t radii[3] = {0, 2, 4};
    for (int slot = 0; slot < 3; ++slot) {
      PyObject* radius = PyLong_FromLongLong(radii[slot]);
      char memory_prefix[32];
      char level_prefix[32];
      std::snprintf(memory_prefix, sizeof(memory_prefix), "disc_memory_z%lld_",
                    static_cast<long long>(radii[slot]));
      std::snprintf(level_prefix, sizeof(level_prefix), "disc_level_z%lld_",
                    static_cast<long long>(radii[slot]));
      PyObject* memory_name = PyUnicode_FromString(memory_prefix);
      PyObject* level_name = PyUnicode_FromString(level_prefix);
      if (radius == nullptr || memory_name == nullptr || level_name == nullptr) {
        Py_XDECREF(radius);
        Py_XDECREF(memory_name);
        Py_XDECREF(level_name);
        return false;
      }
      PyObject* memory_args[7] = {memory_name,         boxed.formation_tick,
                                  radius,              boxed.zero,
                                  boxed.formation_sec, objects.side,
                                  boxed.formation_sec};
      PyObject* level_args[7] = {level_name,          boxed.formation_tick,
                                 radius,              boxed.formation_sec,
                                 boxed.snapshot_sec,  objects.side,
                                 boxed.snapshot_sec};
      const bool merged =
          qrdisc_delegate_into(plane, "_level_values", memory_args, level_kw,
                               values) &&
          qrdisc_delegate_into(plane, "_level_values", level_args, level_kw,
                               values);
      Py_DECREF(radius);
      Py_DECREF(memory_name);
      Py_DECREF(level_name);
      if (!merged) return false;
    }
    const std::int64_t current_left =
        row.snapshot_sec - 30 > 0 ? row.snapshot_sec - 30 : 0;
    PyObject* current_name = PyUnicode_FromString("disc_current_z2_");
    PyObject* current_left_object = PyLong_FromLongLong(current_left);
    if (current_name == nullptr || current_left_object == nullptr) {
      Py_XDECREF(current_name);
      Py_XDECREF(current_left_object);
      return false;
    }
    PyObject* current_args[7] = {current_name,       boxed.current_tick,
                                 boxed.radius2,      current_left_object,
                                 boxed.snapshot_sec, objects.side,
                                 boxed.snapshot_sec};
    const bool merged = qrdisc_delegate_into(plane, "_level_values",
                                             current_args, level_kw, values);
    Py_DECREF(current_name);
    Py_DECREF(current_left_object);
    if (!merged) return false;
  }

  // :2457 — `int(formation_candidate["decision_ts_ns"])`, read HERE and not at
  // the top of the row: a candidate missing that key must raise KeyError after
  // the level windows have already emitted, exactly as the oracle does (R6 F9).
  std::int64_t formation_ts_ns = 0;
  if (!qrdisc_mapping_int64(objects.formation, "decision_ts_ns",
                            &formation_ts_ns)) {
    return false;
  }
  *formation_ts_ns_out = formation_ts_ns;
  boxed.formation_ts_ns = PyLong_FromLongLong(formation_ts_ns);
  if (boxed.formation_ts_ns == nullptr) return false;

  // :2458-2475 — the prior reaction, then the three clock blocks.
  static PyObject* const reaction_kw =
      qrdisc_kwnames({"formation_tick", "formation_ts_ns", "side"});
  if (qrdisc_family_is_native_here(plane, "_prior_reaction_map")) {
    if (!qrdisc_native_block(plane, "_prior_reaction_map", row, run_native,
                             values)) {
      return false;
    }
  } else {
    PyObject* args[3] = {boxed.formation_tick, boxed.formation_ts_ns,
                         objects.side};
    if (!qrdisc_delegate_into(plane, "_prior_reaction_map", args, reaction_kw,
                              values)) {
      return false;
    }
  }
  static PyObject* const count_clock_kw = qrdisc_kwnames(
      {"target_count", "snapshot_ts_ns", "formation_ts_ns", "side"});
  static PyObject* const volume_clock_kw = qrdisc_kwnames(
      {"target_volume", "snapshot_ts_ns", "formation_ts_ns", "side"});
  const char* const clock_families[3] = {"_event_clock_map", "_trade_clock_map",
                                         "_volume_clock_map"};
  const std::int64_t clock_targets[3][4] = {
      {16, 64, 256, 1024}, {8, 32, 128, 512}, {64, 256, 1024, 0}};
  const int clock_counts[3] = {4, 4, 3};
  for (int block = 0; block < 3; ++block) {
    if (qrdisc_family_is_native_here(plane, clock_families[block])) {
      if (!qrdisc_native_block(plane, clock_families[block], row, run_native,
                               values)) {
        return false;
      }
      continue;
    }
    for (int slot = 0; slot < clock_counts[block]; ++slot) {
      PyObject* target = PyLong_FromLongLong(clock_targets[block][slot]);
      if (target == nullptr) return false;
      PyObject* args[4] = {target, boxed.snapshot_ts_ns, boxed.formation_ts_ns,
                           objects.side};
      const bool merged = qrdisc_delegate_into(
          plane, clock_families[block], args,
          block < 2 ? count_clock_kw : volume_clock_kw, values);
      Py_DECREF(target);
      if (!merged) return false;
    }
  }

  // :2476-2485 — the tape slope and the two formation-response families.
  static PyObject* const tape_kw = qrdisc_kwnames({"snapshot_sec", "side"});
  if (qrdisc_family_is_native_here(plane, "_tape_slope_map")) {
    if (!qrdisc_native_block(plane, "_tape_slope_map", row, run_native,
                             values)) {
      return false;
    }
  } else {
    PyObject* args[2] = {boxed.snapshot_sec, objects.side};
    if (!qrdisc_delegate_into(plane, "_tape_slope_map", args, tape_kw, values)) {
      return false;
    }
  }
  static PyObject* const maturity_kw = qrdisc_kwnames(
      {"formation_tick", "formation_ts_ns", "snapshot_ts_ns", "side"});
  PyObject* maturity_args[4] = {boxed.formation_tick, boxed.formation_ts_ns,
                                boxed.snapshot_ts_ns, objects.side};
  const char* const response_families[2] = {"_test_maturity_map",
                                            "_best_quote_response_map"};
  for (const char* family : response_families) {
    const bool merged =
        qrdisc_family_is_native_here(plane, family)
            ? qrdisc_native_block(plane, family, row, run_native, values)
            : qrdisc_delegate_into(plane, family, maturity_args, maturity_kw,
                                   values);
    if (!merged) return false;
  }

  // :2486-2494 — the seven event-micro horizons.
  static PyObject* const micro_kw = qrdisc_kwnames(
      {"prefix", "center_tick", "radius", "left_ns", "right_ns", "side"});
  if (qrdisc_family_is_native_here(plane, "_event_micro_map")) {
    if (!qrdisc_native_block(plane, "_event_micro_map", row, run_native,
                             values)) {
      return false;
    }
  } else {
    const std::int64_t horizons[7] = {1, 5, 15, 30, 60, 120, 300};
    for (int slot = 0; slot < 7; ++slot) {
      const std::int64_t bounded =
          snapshot_ts_ns - horizons[slot] * 1000000000;
      const std::int64_t left_ns =
          formation_ts_ns > bounded ? formation_ts_ns : bounded;
      char prefix_text[32];
      std::snprintf(prefix_text, sizeof(prefix_text), "disc_evt_h%lld_",
                    static_cast<long long>(horizons[slot]));
      PyObject* prefix = PyUnicode_FromString(prefix_text);
      PyObject* left_object = PyLong_FromLongLong(left_ns);
      if (prefix == nullptr || left_object == nullptr) {
        Py_XDECREF(prefix);
        Py_XDECREF(left_object);
        return false;
      }
      PyObject* args[6] = {prefix,      boxed.formation_tick, boxed.radius2,
                           left_object, boxed.snapshot_ts_ns, objects.side};
      const bool merged = qrdisc_delegate_into(plane, "_event_micro_map", args,
                                               micro_kw, values);
      Py_DECREF(prefix);
      Py_DECREF(left_object);
      if (!merged) return false;
    }
  }

  // :2495-2500 — the two footprint horizons.
  static PyObject* const shape_kw = qrdisc_kwnames(
      {"prefix", "center_tick", "radius", "left_sec", "right_sec", "side"});
  if (qrdisc_family_is_native_here(plane, "_price_shape_values")) {
    return qrdisc_native_block(plane, "_price_shape_values", row, run_native,
                               values);
  }
  const std::int64_t footprints[2] = {30, 300};
  for (int slot = 0; slot < 2; ++slot) {
    const std::int64_t bounded = row.snapshot_sec - footprints[slot];
    const std::int64_t left_sec =
        row.formation_sec > bounded ? row.formation_sec : bounded;
    char prefix_text[32];
    std::snprintf(prefix_text, sizeof(prefix_text), "disc_footprint_h%lld_",
                  static_cast<long long>(footprints[slot]));
    PyObject* prefix = PyUnicode_FromString(prefix_text);
    PyObject* left_object = PyLong_FromLongLong(left_sec);
    if (prefix == nullptr || left_object == nullptr) {
      Py_XDECREF(prefix);
      Py_XDECREF(left_object);
      return false;
    }
    PyObject* args[6] = {prefix,      boxed.formation_tick, boxed.radius4,
                         left_object, boxed.snapshot_sec,   objects.side};
    const bool merged = qrdisc_delegate_into(plane, "_price_shape_values", args,
                                             shape_kw, values);
    Py_DECREF(prefix);
    Py_DECREF(left_object);
    if (!merged) return false;
  }
  return true;
}
