// The marshalled-state half of the qrdisc CPython boundary: the plane object,
// its borrowed numpy buffers, and the round-trip surface the contract test
// reads them back through.
//
// Split out of qrdisc_pymodule.cpp so each file stays inside one read: this
// side is finished (it consumes the marshaller's output and will not grow),
// while the row path on the other side grows one map family per stage.
//
// NUMPY C API ACROSS TWO TRANSLATION UNITS.  numpy's function table is a
// per-TU pointer.  PY_ARRAY_UNIQUE_SYMBOL makes it one shared global instead;
// exactly one TU may define QRDISC_ARRAY_IMPORTER and call import_array(), and
// every other TU picks the table up as extern.
#ifndef QR_ENTRY_V2_QRDISC_PLANE_STATE_HPP
#define QR_ENTRY_V2_QRDISC_PLANE_STATE_HPP

#define PY_SSIZE_T_CLEAN
#include <Python.h>

#define PY_ARRAY_UNIQUE_SYMBOL QRDISC_ARRAY_API
#ifndef QRDISC_ARRAY_IMPORTER
#define NO_IMPORT_ARRAY
#endif
#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <numpy/arrayobject.h>

#include <cstdint>
#include <string>
#include <vector>

// One borrowed numpy buffer.  `array` owns the reference; `data` is the raw
// pointer the kernels will read once families land natively (stage 4+).
struct QrdiscBuffer {
  std::string name;
  PyArrayObject* array;
  void* data;
  npy_intp shape[2];
  int ndim;
  int type_num;
};

struct QrdiscPlaneObject {
  PyObject_HEAD
  std::vector<QrdiscBuffer>* buffers;
  PyObject* scalars;       // dict, owned
  PyObject* delegates;     // dict of name -> callable, owned
  PyObject* refusal_type;  // the oracle's DiscretionaryFeatureRefusal, owned
  std::int64_t open_ns;
  std::int64_t duration;
  // ENGAGEMENT COUNTER (R6 F7).  Incremented once per `qrdisc_run_family` call,
  // read back by the module's `family_call_count`.  A native family that is
  // never entered — a delegation-table typo, a name the dispatcher does not
  // know — still yields the oracle's own correct bytes, so the differential
  // passes for a run that measured the OLD path.  This makes engagement a
  // number the caller can assert instead of an assumption.
  std::int64_t family_calls;
};

// Set by qrdisc_plane_type_ready() during module init.
extern PyTypeObject* QrdiscPlaneType;

// Creates the heap type.  Returns a NEW reference to it, or nullptr on error.
PyObject* qrdisc_plane_type_ready();

// Python's // floors toward -infinity; C++ / truncates toward zero.  The
// snapshot second at discretionary_features.py:2393 is a floor division and a
// pre-open snapshot must land on the same negative second Python produces, or
// the "snapshot is outside session" refusal fires on different rows.
std::int64_t qrdisc_floor_div(std::int64_t numerator, std::int64_t denominator);

// `int(value)` with Python's own semantics (str, int, numpy scalar all behave
// exactly as the oracle's int() does), then a range check that REFUSES rather
// than silently truncating.
bool qrdisc_as_int64(PyObject* value, const char* field, std::int64_t* out);

// PyObject_GetItem + qrdisc_as_int64.  A missing key raises KeyError from the
// same place the oracle's subscript would.
bool qrdisc_mapping_int64(PyObject* mapping, const char* key,
                          std::int64_t* out);

void qrdisc_raise_refusal(QrdiscPlaneObject* plane, const char* message);

PyObject* qrdisc_build_plane(PyObject* self, PyObject* args, PyObject* kwargs);
PyObject* qrdisc_plane_buffer(PyObject* self, PyObject* args);
PyObject* qrdisc_plane_buffer_names(PyObject* self, PyObject* args);

#endif  // QR_ENTRY_V2_QRDISC_PLANE_STATE_HPP
