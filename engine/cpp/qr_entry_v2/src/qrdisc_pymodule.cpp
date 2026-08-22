// qr_disc_native — the row path and module init of the qrdisc port of
// CausalDiscretionaryPlane.feature_map (discretionary_features.py:2389, frozen).
//
// WHAT THIS FILE IS FOR (stage 3): the BOUNDARY, not the speed.  A session's
// state crosses ONCE (qrdisc_plane_state.cpp); this file answers ONE row by
// running the parts it can prove bit-identical natively and DELEGATING
// everything else back to Python through a named callback table.  Delegated
// arithmetic is bit-identical by construction — it is literally the oracle's
// own code — so any differential mismatch at this stage localises to the
// marshalling or the row plumbing, which is exactly what stage 3 must prove.
//
// pybind11 is not vendored and nothing may be downloaded, so this is the raw
// CPython C API plus the numpy C API.  This is the ONE translation unit that
// imports numpy's function table (see qrdisc_plane_state.hpp).
//
// The module is compiled by engine/entry_v2/qrdisc_native_loader.py, which
// bakes QRDISC_SOURCE_MANIFEST_SHA256 in and refuses a binary whose manifest
// disagrees with the sources on disk.
#define QRDISC_ARRAY_IMPORTER
#include "qr_entry_v2/qrdisc_plane_state.hpp"

#include <cstdint>
#include <exception>
#include <string>

#include "qr_entry_v2/qrdisc_assembly.hpp"
#include "qr_entry_v2/qrdisc_kernels_events.hpp"
#include "qr_entry_v2/qrdisc_maps.hpp"
#include "qr_entry_v2/qrdisc_np_kernels.hpp"

#ifndef QRDISC_SOURCE_MANIFEST_SHA256
#error "QRDISC_SOURCE_MANIFEST_SHA256 must be defined by the building loader"
#endif

namespace {

constexpr std::int64_t kNanosPerSecond = 1000000000;

// --- the row path ----------------------------------------------------------

// Convert the delegate's Mapping[str, float] into the pair the store contract
// is expressed in: a float64 value vector plus the emitted NAME ORDER, which is
// identity for the dense store (disc_native_differential.py:14-18).
// `overrides`, when non-null, replaces the delegate's value for every name it
// carries.  That is how ONE family swaps to native while the rest of the row
// is still the oracle's own bytes: the store differential then judges exactly
// the swapped columns.  `matched` catches the half of the name contract this
// site can see — a native name the oracle never emits, which would otherwise
// be dropped without a trace.  The other half (a name the family FAILED to
// emit, which quietly keeps the delegate's value) is only visible against the
// oracle's own family, and is asserted there by
// engine/entry_v2/test_qrdisc_maps.py.
PyObject* qrdisc_split_mapping(PyObject* mapping, PyObject* overrides) {
  PyObject* items = PyMapping_Items(mapping);
  if (items == nullptr) return nullptr;
  if (!PyList_Check(items)) {
    PyErr_Format(PyExc_TypeError,
                 "qrdisc feature_map_row: delegate's items() gave %s, expected "
                 "a list of (name, value) pairs",
                 Py_TYPE(items)->tp_name);
    Py_DECREF(items);
    return nullptr;
  }
  const Py_ssize_t count = PyList_GET_SIZE(items);
  npy_intp shape[1] = {count};
  PyObject* values = PyArray_SimpleNew(1, shape, NPY_FLOAT64);
  PyObject* names = PyTuple_New(count);
  if (values == nullptr || names == nullptr) {
    Py_XDECREF(values);
    Py_XDECREF(names);
    Py_DECREF(items);
    return nullptr;
  }
  double* out = static_cast<double*>(
      PyArray_DATA(reinterpret_cast<PyArrayObject*>(values)));
  Py_ssize_t matched = 0;
  for (Py_ssize_t index = 0; index < count; ++index) {
    PyObject* pair = PyList_GET_ITEM(items, index);
    if (!PyTuple_Check(pair) || PyTuple_GET_SIZE(pair) != 2) {
      PyErr_Format(PyExc_TypeError,
                   "qrdisc feature_map_row: delegate returned a mapping whose "
                   "item %zd is %R, expected a (name, value) pair",
                   index, pair);
      Py_DECREF(values);
      Py_DECREF(names);
      Py_DECREF(items);
      return nullptr;
    }
    PyObject* key = PyTuple_GET_ITEM(pair, 0);
    PyObject* value = PyTuple_GET_ITEM(pair, 1);
    if (!PyUnicode_Check(key)) {
      PyErr_Format(PyExc_TypeError,
                   "qrdisc feature_map_row: feature name at position %zd is "
                   "%R, expected str",
                   index, key);
      Py_DECREF(values);
      Py_DECREF(names);
      Py_DECREF(items);
      return nullptr;
    }
    if (overrides != nullptr) {
      PyObject* native = PyDict_GetItem(overrides, key);
      if (native != nullptr) {
        value = native;
        ++matched;
      }
    }
    const double as_double = PyFloat_AsDouble(value);
    if (as_double == -1.0 && PyErr_Occurred()) {
      Py_DECREF(values);
      Py_DECREF(names);
      Py_DECREF(items);
      return nullptr;
    }
    out[index] = as_double;
    Py_INCREF(key);
    PyTuple_SET_ITEM(names, index, key);
  }
  Py_DECREF(items);
  if (overrides != nullptr && matched != PyDict_Size(overrides)) {
    PyErr_Format(PyExc_KeyError,
                 "qrdisc feature_map_row: the native families emitted %zd "
                 "names the oracle's map does not contain (native=%zd, "
                 "matched=%zd); a name the oracle never emits would be dropped "
                 "silently and one it emits would keep the delegated value",
                 PyDict_Size(overrides) - matched, PyDict_Size(overrides),
                 matched);
    Py_DECREF(values);
    Py_DECREF(names);
    return nullptr;
  }
  PyObject* result = PyTuple_Pack(2, values, names);
  Py_DECREF(values);
  Py_DECREF(names);
  return result;
}

// The family names the row path can compute natively.  A name appears in a
// plane's delegation table mapped to None to say "this family is native now";
// mapped to a callable, or absent, it stays the oracle's.
const char* const kQrdiscNativeFamilies[] = {
    "_forward_vol_map", "_regime_map",        "_target_map",
    "_event_micro_map", "_prior_reaction_map", "_event_clock_map",
    "_trade_clock_map", "_volume_clock_map"};

bool qrdisc_family_is_native(QrdiscPlaneObject* plane, const char* family) {
  PyObject* entry = PyDict_GetItemString(plane->delegates, family);
  return entry != nullptr && entry == Py_None;
}

bool qrdisc_run_family(QrdiscPlaneObject* plane, const char* family,
                       const QrdiscRowInputs& row, QrdiscValueMap* out) {
  // Counted BEFORE the dispatch, so an unknown family name still registers as
  // an attempt and the caller's arithmetic (rows x families) stays exact.
  ++plane->family_calls;
  const std::string name(family);
  if (name == "_regime_map") return qrdisc_regime_map(plane, row, out);
  if (name == "_forward_vol_map") return qrdisc_forward_vol_map(plane, row, out);
  if (name == "_event_micro_map") return qrdisc_event_micro_map(plane, row, out);
  if (name == "_prior_reaction_map") return qrdisc_prior_reaction_map(plane, row, out);
  if (name == "_event_clock_map") return qrdisc_event_clock_map(plane, row, out);
  if (name == "_trade_clock_map") return qrdisc_trade_clock_map(plane, row, out);
  if (name == "_volume_clock_map") return qrdisc_volume_clock_map(plane, row, out);
  if (name == "_target_map") {
    double atr_usd = 0.0;
    // feature_map:2437 reads it WITHOUT the non-finite clamp the vol family's
    // own `number()` closure applies.
    if (!qrdisc_candidate_number(row.formation_candidate, "atr14_prev_usd",
                                 false, &atr_usd)) {
      return false;
    }
    return qrdisc_target_map(plane, row, atr_usd, out);
  }
  PyErr_Format(PyExc_KeyError,
               "qrdisc: '%s' is not a natively implemented family; known "
               "families are _forward_vol_map, _regime_map, _target_map, "
               "_event_micro_map, _prior_reaction_map, _event_clock_map, "
               "_trade_clock_map, _volume_clock_map",
               family);
  return false;
}

// Transcribed from discretionary_features.py:2393-2403.  The ORDER of these
// steps is contract, not style: a missing formation key must raise KeyError
// from the same place, and the snapshot refusal must win over it.
bool qrdisc_parse_row(QrdiscPlaneObject* plane, PyObject* snapshot_object,
                      PyObject* current_mid2, PyObject* side,
                      PyObject* formation, QrdiscRowInputs* out) {
  std::int64_t snapshot_ts_ns = 0;
  if (!qrdisc_as_int64(snapshot_object, "snapshot_ts_ns", &snapshot_ts_ns)) {
    return false;
  }
  out->snapshot_sec =
      qrdisc_floor_div(snapshot_ts_ns - plane->open_ns, kNanosPerSecond);
  if (!(0 <= out->snapshot_sec && out->snapshot_sec <= plane->duration)) {
    qrdisc_raise_refusal(plane, "snapshot is outside session");
    return false;
  }
  std::int64_t formation_bid = 0;
  std::int64_t formation_ask = 0;
  std::int64_t phase_open_utc = 0;
  if (!qrdisc_mapping_int64(formation, "decision_sec", &out->formation_sec) ||
      !qrdisc_mapping_int64(formation, "entry_mid2", &out->formation_mid2) ||
      !qrdisc_mapping_int64(formation, "entry_bid_px", &formation_bid) ||
      !qrdisc_mapping_int64(formation, "entry_ask_px", &formation_ask) ||
      !qrdisc_mapping_int64(formation, "phase_open_utc", &phase_open_utc)) {
    return false;
  }
  if (!(0 <= out->formation_sec && out->formation_sec <= out->snapshot_sec &&
        formation_bid > 0 && formation_ask > formation_bid)) {
    qrdisc_raise_refusal(plane, "formation state is malformed");
    return false;
  }
  out->phase_open_sec =
      phase_open_utc - qrdisc_floor_div(plane->open_ns, kNanosPerSecond);
  out->formation_candidate = formation;
  out->snapshot_ts_ns = snapshot_ts_ns;
  if (!qrdisc_as_int64(current_mid2, "current_mid2", &out->current_mid2) ||
      !qrdisc_as_int64(side, "side", &out->side)) {
    return false;
  }
  // feature_map:2432-2433.  Derived from values this function has already read
  // and refused on, so no candidate key is touched earlier than the oracle
  // touches it.
  std::int64_t raw_tick = 0;
  PyObject* raw_tick_object = PyDict_GetItemString(plane->scalars, "raw_tick");
  if (raw_tick_object == nullptr) {
    PyErr_SetString(PyExc_KeyError, "qrdisc: scalar 'raw_tick' is missing");
    return false;
  }
  if (!qrdisc_as_int64(raw_tick_object, "raw_tick", &raw_tick)) return false;
  out->formation_tick = qrdisc_floor_div(
      out->side > 0 ? formation_bid : formation_ask, raw_tick);
  return true;
}

PyObject* qrdisc_value_map_pair(const QrdiscValueMap& map) {
  const Py_ssize_t count = static_cast<Py_ssize_t>(map.size());
  npy_intp shape[1] = {count};
  PyObject* values = PyArray_SimpleNew(1, shape, NPY_FLOAT64);
  PyObject* names = PyTuple_New(count);
  if (values == nullptr || names == nullptr) {
    Py_XDECREF(values);
    Py_XDECREF(names);
    return nullptr;
  }
  double* out = static_cast<double*>(
      PyArray_DATA(reinterpret_cast<PyArrayObject*>(values)));
  for (Py_ssize_t index = 0; index < count; ++index) {
    out[index] = map[static_cast<std::size_t>(index)].second;
    PyObject* name =
        PyUnicode_FromString(map[static_cast<std::size_t>(index)].first.c_str());
    if (name == nullptr) {
      Py_DECREF(values);
      Py_DECREF(names);
      return nullptr;
    }
    PyTuple_SET_ITEM(names, index, name);
  }
  PyObject* result = PyTuple_Pack(2, values, names);
  Py_DECREF(values);
  Py_DECREF(names);
  return result;
}

// EVERY CPython entry point below wraps its body in the same try/catch
// `qrdisc_probe_kernels` already used (R6 F4).  A C++ exception escaping into
// the interpreter is `std::terminate` — the whole process, no traceback — and
// the bodies allocate std::vector and std::string on every row.  The body is a
// separate function rather than an indented `try` block so the diff stays
// readable and each boundary is greppable.
PyObject* qrdisc_family_map_body(PyObject* args, PyObject* kwargs) {
  static const char* keywords[] = {"plane",        "family",
                                   "snapshot_ts_ns", "current_bid",
                                   "current_ask",  "current_mid2",
                                   "side",         "formation_candidate",
                                   nullptr};
  PyObject* object = nullptr;
  const char* family = nullptr;
  PyObject* snapshot_object = nullptr;
  PyObject* current_bid = nullptr;
  PyObject* current_ask = nullptr;
  PyObject* current_mid2 = nullptr;
  PyObject* side = nullptr;
  PyObject* formation = nullptr;
  if (!PyArg_ParseTupleAndKeywords(
          args, kwargs, "OsOOOOOO", const_cast<char**>(keywords), &object,
          &family, &snapshot_object, &current_bid, &current_ask, &current_mid2,
          &side, &formation)) {
    return nullptr;
  }
  if (Py_TYPE(object) != QrdiscPlaneType) {
    PyErr_Format(PyExc_TypeError,
                 "qrdisc family_map: expected a QrdiscPlane, got %s",
                 Py_TYPE(object)->tp_name);
    return nullptr;
  }
  QrdiscPlaneObject* plane = reinterpret_cast<QrdiscPlaneObject*>(object);
  QrdiscRowInputs row{};
  if (!qrdisc_parse_row(plane, snapshot_object, current_mid2, side, formation,
                        &row)) {
    return nullptr;
  }
  QrdiscValueMap map;
  if (!qrdisc_run_family(plane, family, row, &map)) return nullptr;
  return qrdisc_value_map_pair(map);
}

PyObject* qrdisc_family_map(PyObject*, PyObject* args, PyObject* kwargs) {
  try {
    return qrdisc_family_map_body(args, kwargs);
  } catch (const std::exception& error) {
    PyErr_SetString(PyExc_RuntimeError, error.what());
    return nullptr;
  }
}

PyObject* qrdisc_feature_map_row_body(PyObject* args, PyObject* kwargs) {
  static const char* keywords[] = {"plane",       "snapshot_ts_ns",
                                   "current_bid", "current_ask",
                                   "current_mid2", "side",
                                   "formation_candidate", nullptr};
  PyObject* object = nullptr;
  PyObject* snapshot_object = nullptr;
  PyObject* current_bid = nullptr;
  PyObject* current_ask = nullptr;
  PyObject* current_mid2 = nullptr;
  PyObject* side = nullptr;
  PyObject* formation = nullptr;
  if (!PyArg_ParseTupleAndKeywords(
          args, kwargs, "OOOOOOO", const_cast<char**>(keywords), &object,
          &snapshot_object, &current_bid, &current_ask, &current_mid2, &side,
          &formation)) {
    return nullptr;
  }
  if (Py_TYPE(object) != QrdiscPlaneType) {
    PyErr_Format(PyExc_TypeError,
                 "qrdisc feature_map_row: expected a QrdiscPlane, got %s",
                 Py_TYPE(object)->tp_name);
    return nullptr;
  }
  QrdiscPlaneObject* plane = reinterpret_cast<QrdiscPlaneObject*>(object);
  QrdiscRowInputs row{};
  if (!qrdisc_parse_row(plane, snapshot_object, current_mid2, side, formation,
                        &row)) {
    return nullptr;
  }

  // Wave 2 of stage 4: when the delegation table can answer EVERY family
  // individually, the row is assembled here — families called one by one, the
  // merge in feature_map's own insertion order, then the tail
  // (discretionary_features.py:2502-2694) natively.  The whole-map delegate is
  // no longer on the path; a native family stops costing extra and starts
  // saving.  Availability is the switch: drop one family from the table and the
  // splice path below takes the row back, which is the debugging fallback.
  if (qrdisc_assembly_available(plane)) {
    const QrdiscRowObjects objects{snapshot_object, current_bid, current_ask,
                                   current_mid2,    side,        formation};
    std::int64_t snapshot_ts_ns = 0;
    std::int64_t formation_ts_ns = 0;
    QrdiscRowValues values;
    if (!qrdisc_as_int64(snapshot_object, "snapshot_ts_ns", &snapshot_ts_ns) ||
        !qrdisc_assemble_families(plane, row, objects, qrdisc_run_family,
                                  &formation_ts_ns, &values) ||
        !qrdisc_assembly_tail(plane, row, objects, snapshot_ts_ns,
                              formation_ts_ns, &values)) {
      return nullptr;
    }
    return qrdisc_value_map_pair(values.entries());
  }

  // Wave 1 of stage 4: the families marked native in the delegation table are
  // computed here and SPLICED over the delegate's own values.  The whole-map
  // delegate still assembles the row, so the emitted name order is still the
  // oracle's; the wave that assembles natively inherits families whose values
  // the store differential has already judged column by column.
  PyObject* overrides = nullptr;
  for (const char* family : kQrdiscNativeFamilies) {
    if (!qrdisc_family_is_native(plane, family)) continue;
    if (overrides == nullptr) {
      overrides = PyDict_New();
      if (overrides == nullptr) return nullptr;
    }
    QrdiscValueMap map;
    if (!qrdisc_run_family(plane, family, row, &map)) {
      Py_DECREF(overrides);
      return nullptr;
    }
    for (const std::pair<std::string, double>& entry : map) {
      PyObject* value = PyFloat_FromDouble(entry.second);
      if (value == nullptr ||
          PyDict_SetItemString(overrides, entry.first.c_str(), value) != 0) {
        Py_XDECREF(value);
        Py_DECREF(overrides);
        return nullptr;
      }
      Py_DECREF(value);
    }
  }

  PyObject* delegate = PyDict_GetItemString(plane->delegates, "feature_map");
  if (delegate == nullptr) {
    PyErr_SetString(PyExc_KeyError,
                    "qrdisc feature_map_row: the delegation table has no "
                    "'feature_map' entry and no native map families are "
                    "registered yet; stage 3 requires the whole-map delegate");
    Py_XDECREF(overrides);
    return nullptr;
  }
  // The oracle's feature_map is keyword-ONLY (discretionary_features.py:2389),
  // so the delegate is invoked by keyword.  Calling the bound method directly —
  // rather than through a Python-side shim — keeps the delegated arithmetic
  // literally the oracle's own bytes.
  PyObject* delegate_kwargs = PyDict_New();
  if (delegate_kwargs == nullptr) {
    Py_XDECREF(overrides);
    return nullptr;
  }
  const bool packed =
      PyDict_SetItemString(delegate_kwargs, "snapshot_ts_ns", snapshot_object) == 0 &&
      PyDict_SetItemString(delegate_kwargs, "current_bid", current_bid) == 0 &&
      PyDict_SetItemString(delegate_kwargs, "current_ask", current_ask) == 0 &&
      PyDict_SetItemString(delegate_kwargs, "current_mid2", current_mid2) == 0 &&
      PyDict_SetItemString(delegate_kwargs, "side", side) == 0 &&
      PyDict_SetItemString(delegate_kwargs, "formation_candidate", formation) == 0;
  if (!packed) {
    Py_DECREF(delegate_kwargs);
    Py_XDECREF(overrides);
    return nullptr;
  }
  PyObject* empty_args = PyTuple_New(0);
  if (empty_args == nullptr) {
    Py_DECREF(delegate_kwargs);
    Py_XDECREF(overrides);
    return nullptr;
  }
  PyObject* mapping = PyObject_Call(delegate, empty_args, delegate_kwargs);
  Py_DECREF(empty_args);
  Py_DECREF(delegate_kwargs);
  if (mapping == nullptr) {
    Py_XDECREF(overrides);
    return nullptr;
  }
  PyObject* result = qrdisc_split_mapping(mapping, overrides);
  Py_DECREF(mapping);
  Py_XDECREF(overrides);
  return result;
}

PyObject* qrdisc_feature_map_row(PyObject*, PyObject* args, PyObject* kwargs) {
  try {
    return qrdisc_feature_map_row_body(args, kwargs);
  } catch (const std::exception& error) {
    PyErr_SetString(PyExc_RuntimeError, error.what());
    return nullptr;
  }
}

// The engagement counter F7 arms: how many times this plane entered
// `qrdisc_run_family`.  Zero after a run whose builder named native families is
// the inert-native-path defect — correct bytes from the delegate, and a timing
// number for the path nobody exercised.
PyObject* qrdisc_family_call_count(PyObject*, PyObject* args) {
  PyObject* object = nullptr;
  if (!PyArg_ParseTuple(args, "O", &object)) return nullptr;
  if (Py_TYPE(object) != QrdiscPlaneType) {
    PyErr_Format(PyExc_TypeError,
                 "qrdisc family_call_count: expected a QrdiscPlane, got %s",
                 Py_TYPE(object)->tp_name);
    return nullptr;
  }
  return PyLong_FromLongLong(
      reinterpret_cast<QrdiscPlaneObject*>(object)->family_calls);
}

// Which path a row will take.  Exposed because "the native assembly ran" must
// be ASSERTABLE: a table missing one family silently falls back to the whole-map
// delegate, which still produces correct bytes and would let a speed claim be
// made for a run that never used the new path.
PyObject* qrdisc_assembly_available_py(PyObject*, PyObject* args) {
  PyObject* object = nullptr;
  if (!PyArg_ParseTuple(args, "O", &object)) return nullptr;
  if (Py_TYPE(object) != QrdiscPlaneType) {
    PyErr_Format(PyExc_TypeError,
                 "qrdisc assembly_available: expected a QrdiscPlane, got %s",
                 Py_TYPE(object)->tp_name);
    return nullptr;
  }
  return PyBool_FromLong(qrdisc_assembly_available(
      reinterpret_cast<QrdiscPlaneObject*>(object)));
}

PyObject* qrdisc_source_manifest_sha256(PyObject*, PyObject*) {
  return PyUnicode_FromString(QRDISC_SOURCE_MANIFEST_SHA256);
}

// A kernel probe, so the loader can prove the .so it just built carries the
// same kernels the gtest suite locked down rather than a stale object file.
PyObject* qrdisc_probe_kernels(PyObject*, PyObject*) {
  try {
    const std::int64_t haystack[] = {10, 20, 20, 20, 35, 40};
    const std::int64_t left =
        qrdisc_searchsorted_left_i64(QrdiscI64Span{haystack, 6}, 20);
    const std::int64_t right =
        qrdisc_searchsorted_right_i64(QrdiscI64Span{haystack, 6}, 20);
    double pair[2] = {1.0, 2.0};
    const double quantile = qrdisc_quantile_linear_f64(pair, 2, 0.10);
    return Py_BuildValue("(LLd)", static_cast<long long>(left),
                         static_cast<long long>(right), quantile);
  } catch (const std::exception& error) {
    PyErr_SetString(PyExc_RuntimeError, error.what());
    return nullptr;
  }
}

// CPython's own cast for METH_KEYWORDS entries (methodobject.h's
// _PyCFunction_CAST): the two-step cast through a generic function pointer is
// what keeps -Werror=cast-function-type quiet without disabling it.
template <typename Function>
PyCFunction qrdisc_keyword_method(Function function) {
  return reinterpret_cast<PyCFunction>(
      reinterpret_cast<void (*)(void)>(function));
}

// The blocked-pairwise transcription of numpy's float64 `.sum()`, exposed so a
// Python test can compare its bytes against numpy's own on the lengths where
// the pairwise-only model is wrong (qrdisc_kernels_events.hpp).  Without a
// probe the kernel is only ever judged through a family, where a one-ulp sum
// error hides behind float32 truncation at the store.
PyObject* qrdisc_probe_pairwise_sum(PyObject*, PyObject* args) {
  PyObject* object = nullptr;
  if (!PyArg_ParseTuple(args, "O", &object)) return nullptr;
  PyArrayObject* array = reinterpret_cast<PyArrayObject*>(
      PyArray_FROMANY(object, NPY_FLOAT64, 1, 1, NPY_ARRAY_C_CONTIGUOUS));
  if (array == nullptr) return nullptr;
  double total = 0.0;
  const bool ok = qrdisc_np_sum_f64(
      static_cast<const double*>(PyArray_DATA(array)),
      static_cast<std::int64_t>(PyArray_DIM(array, 0)), &total);
  Py_DECREF(array);
  if (!ok) return nullptr;
  return PyFloat_FromDouble(total);
}

// `_ledger_sum` is a kernel whose consumers (`_level_values` :1161 and
// `_price_shape_values` :1208) are not ported yet, so no family gate reaches
// it.  This probe is its seam: without one it would be C++ nothing runs and
// nothing checks.
PyObject* qrdisc_probe_ledger_sum_body(PyObject* args) {
  PyObject* object = nullptr;
  long long center_tick = 0;
  long long radius = 0;
  long long left_sec = 0;
  long long right_sec = 0;
  if (!PyArg_ParseTuple(args, "OLLLL", &object, &center_tick, &radius,
                        &left_sec, &right_sec)) {
    return nullptr;
  }
  if (Py_TYPE(object) != QrdiscPlaneType) {
    PyErr_Format(PyExc_TypeError,
                 "qrdisc probe_ledger_sum: expected a QrdiscPlane, got %s",
                 Py_TYPE(object)->tp_name);
    return nullptr;
  }
  QrdiscLedgerSum result;
  if (!qrdisc_ledger_sum(reinterpret_cast<QrdiscPlaneObject*>(object),
                         center_tick, radius, left_sec, right_sec, &result)) {
    return nullptr;
  }
  npy_intp shape[1] = {static_cast<npy_intp>(result.totals.size())};
  PyObject* totals = PyArray_SimpleNew(1, shape, NPY_INT64);
  if (totals == nullptr) return nullptr;
  std::int64_t* out = static_cast<std::int64_t*>(
      PyArray_DATA(reinterpret_cast<PyArrayObject*>(totals)));
  for (std::size_t index = 0; index < result.totals.size(); ++index) {
    out[index] = result.totals[index];
  }
  PyObject* pair = Py_BuildValue(
      "NLLLLLL", totals, static_cast<long long>(result.buy_bursts),
      static_cast<long long>(result.sell_bursts),
      static_cast<long long>(result.last_buy),
      static_cast<long long>(result.last_sell),
      static_cast<long long>(result.max_buy),
      static_cast<long long>(result.max_sell));
  return pair;
}

PyObject* qrdisc_probe_ledger_sum(PyObject*, PyObject* args) {
  try {
    return qrdisc_probe_ledger_sum_body(args);
  } catch (const std::exception& error) {
    PyErr_SetString(PyExc_RuntimeError, error.what());
    return nullptr;
  }
}

// `_trade_slice_map` is a kernel, not a family: its window arguments come from
// the two clock families, so it cannot be reached through family_map's row-only
// signature and gets its own entry point to be gated at its own seam.
PyObject* qrdisc_trade_slice_map_entry_body(PyObject* args, PyObject* kwargs) {
  static const char* keywords[] = {"plane",
                                   "prefix",
                                   "left",
                                   "right",
                                   "support_fraction",
                                   "snapshot_ts_ns",
                                   "formation_ts_ns",
                                   "side",
                                   nullptr};
  PyObject* object = nullptr;
  const char* prefix = nullptr;
  long long left = 0;
  long long right = 0;
  double support_fraction = 0.0;
  long long snapshot_ts_ns = 0;
  long long formation_ts_ns = 0;
  long long side = 0;
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OsLLdLLL",
                                   const_cast<char**>(keywords), &object,
                                   &prefix, &left, &right, &support_fraction,
                                   &snapshot_ts_ns, &formation_ts_ns, &side)) {
    return nullptr;
  }
  if (Py_TYPE(object) != QrdiscPlaneType) {
    PyErr_Format(PyExc_TypeError,
                 "qrdisc trade_slice_map: expected a QrdiscPlane, got %s",
                 Py_TYPE(object)->tp_name);
    return nullptr;
  }
  QrdiscPlaneObject* plane = reinterpret_cast<QrdiscPlaneObject*>(object);
  // R6 F16.  In production the two clock families compute this window; here the
  // CALLER supplies it, so this seam is the only thing between a bad index and
  // a read before or past the marshalled trade vectors.  The four are indexed
  // together (qrdisc_maps_slice.cpp:56-64), so their lengths must agree too.
  static const char* const kQrdiscTradeVectors[4] = {
      "attr___trade_ts", "attr___trade_sign", "attr___trade_exact_sizes",
      "attr___trade_exact_ticks"};
  static const int kQrdiscTradeVectorTypes[4] = {NPY_INT64, NPY_UINT8,
                                                 NPY_INT64, NPY_INT64};
  npy_intp length = 0;
  for (int slot = 0; slot < 4; ++slot) {
    const QrdiscBuffer* buffer = qrdisc_plane_buffer_named(
        plane, kQrdiscTradeVectors[slot], kQrdiscTradeVectorTypes[slot], 1);
    if (buffer == nullptr) return nullptr;
    if (slot == 0) {
      length = buffer->shape[0];
    } else if (buffer->shape[0] != length) {
      PyErr_Format(PyExc_ValueError,
                   "qrdisc trade_slice_map: '%s' holds %lld entries but "
                   "'attr___trade_ts' holds %lld; the four trade vectors are "
                   "indexed together",
                   kQrdiscTradeVectors[slot],
                   static_cast<long long>(buffer->shape[0]),
                   static_cast<long long>(length));
      return nullptr;
    }
  }
  if (!(0 <= left && left <= right &&
        right <= static_cast<long long>(length))) {
    PyErr_Format(PyExc_ValueError,
                 "qrdisc trade_slice_map: window left=%lld right=%lld violates "
                 "0 <= left <= right <= %lld (the marshalled trade length)",
                 left, right, static_cast<long long>(length));
    return nullptr;
  }
  QrdiscValueMap map;
  if (!qrdisc_trade_slice_map(plane, std::string(prefix), left, right,
                              support_fraction, snapshot_ts_ns, formation_ts_ns,
                              side, &map)) {
    return nullptr;
  }
  return qrdisc_value_map_pair(map);
}

PyObject* qrdisc_trade_slice_map_entry(PyObject*, PyObject* args,
                                       PyObject* kwargs) {
  try {
    return qrdisc_trade_slice_map_entry_body(args, kwargs);
  } catch (const std::exception& error) {
    PyErr_SetString(PyExc_RuntimeError, error.what());
    return nullptr;
  }
}

PyMethodDef kQrdiscMethods[] = {
    {"build_plane", qrdisc_keyword_method(qrdisc_build_plane),
     METH_VARARGS | METH_KEYWORDS,
     "build_plane(scalars, buffers, delegates, refusal_type) -> QrdiscPlane"},
    {"family_map", qrdisc_keyword_method(qrdisc_family_map),
     METH_VARARGS | METH_KEYWORDS,
     "family_map(plane, family, snapshot_ts_ns, current_bid, current_ask, "
     "current_mid2, side, formation_candidate) -> (values, names)"},
    {"feature_map_row", qrdisc_keyword_method(qrdisc_feature_map_row),
     METH_VARARGS | METH_KEYWORDS,
     "feature_map_row(plane, snapshot_ts_ns, current_bid, current_ask, "
     "current_mid2, side, formation_candidate) -> (values, names)"},
    {"trade_slice_map", qrdisc_keyword_method(qrdisc_trade_slice_map_entry),
     METH_VARARGS | METH_KEYWORDS,
     "trade_slice_map(plane, prefix, left, right, support_fraction, "
     "snapshot_ts_ns, formation_ts_ns, side) -> (values, names)"},
    {"probe_ledger_sum", qrdisc_probe_ledger_sum, METH_VARARGS,
     "probe_ledger_sum(plane, center_tick, radius, left_sec, right_sec) -> "
     "(totals, buy_bursts, sell_bursts, last_buy, last_sell, max_buy, "
     "max_sell)"},
    {"probe_pairwise_sum", qrdisc_probe_pairwise_sum, METH_VARARGS,
     "probe_pairwise_sum(values) -> the port's transcription of np.sum"},
    {"assembly_available", qrdisc_assembly_available_py, METH_VARARGS,
     "assembly_available(plane) -> True when feature_map_row will assemble the "
     "row natively instead of falling back to the whole-map delegate"},
    {"family_call_count", qrdisc_family_call_count, METH_VARARGS,
     "family_call_count(plane) -> how many native family calls this plane has "
     "run, so a caller can ASSERT the native path was entered"},
    {"plane_buffer", qrdisc_plane_buffer, METH_VARARGS,
     "plane_buffer(plane, name) -> ndarray view over the marshalled memory"},
    {"plane_buffer_names", qrdisc_plane_buffer_names, METH_VARARGS,
     "plane_buffer_names(plane) -> tuple of marshalled buffer names"},
    {"source_manifest_sha256", qrdisc_source_manifest_sha256, METH_NOARGS,
     "source_manifest_sha256() -> the C++ manifest this binary was built from"},
    {"probe_kernels", qrdisc_probe_kernels, METH_NOARGS,
     "probe_kernels() -> (searchsorted_left, searchsorted_right, quantile)"},
    {nullptr, nullptr, 0, nullptr},
};

PyModuleDef kQrdiscModule = {
    PyModuleDef_HEAD_INIT,
    "qr_disc_native",
    "Native boundary for the discretionary per-row query path (qrdisc port).",
    -1,
    kQrdiscMethods,
    nullptr,
    nullptr,
    nullptr,
    nullptr,
};

}  // namespace

PyMODINIT_FUNC PyInit_qr_disc_native(void) {
  if (_import_array() < 0) return nullptr;
  // numpy's MODULE object (distinct from its C function table above) is
  // imported once here and read from the row path, never assigned there
  // (R6 F17).
  if (!qrdisc_import_numpy_module()) return nullptr;
  PyObject* type = qrdisc_plane_type_ready();
  if (type == nullptr) return nullptr;
  PyObject* module = PyModule_Create(&kQrdiscModule);
  if (module == nullptr) {
    Py_DECREF(type);
    return nullptr;
  }
  Py_INCREF(type);
  if (PyModule_AddObject(module, "QrdiscPlane", type) < 0) {
    Py_DECREF(type);
    Py_DECREF(type);
    Py_DECREF(module);
    return nullptr;
  }
  return module;
}
