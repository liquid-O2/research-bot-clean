// qrdisc plane state: the CPython object that holds one session's marshalled
// buffers, plus the round-trip surface engine/entry_v2/
// test_qrdisc_state_marshal.py reads them back through.
//
// See include/qr_entry_v2/qrdisc_plane_state.hpp for the boundary contract and
// for why the numpy API table is shared rather than imported here.
#include "qr_entry_v2/qrdisc_plane_state.hpp"

#include <string>

std::int64_t qrdisc_floor_div(std::int64_t numerator, std::int64_t denominator) {
  const std::int64_t quotient = numerator / denominator;
  const std::int64_t remainder = numerator % denominator;
  if (remainder != 0 && ((remainder < 0) != (denominator < 0))) return quotient - 1;
  return quotient;
}

bool qrdisc_as_int64(PyObject* value, const char* field, std::int64_t* out) {
  PyObject* as_int = PyNumber_Long(value);
  if (as_int == nullptr) return false;
  int overflow = 0;
  const long long converted = PyLong_AsLongLongAndOverflow(as_int, &overflow);
  Py_DECREF(as_int);
  if (converted == -1 && PyErr_Occurred()) return false;
  if (overflow != 0) {
    PyErr_Format(PyExc_OverflowError,
                 "qrdisc: field %s does not fit in int64; source=%R", field,
                 value);
    return false;
  }
  *out = static_cast<std::int64_t>(converted);
  return true;
}

bool qrdisc_mapping_int64(PyObject* mapping, const char* key,
                          std::int64_t* out) {
  PyObject* item = PyMapping_GetItemString(mapping, key);
  if (item == nullptr) return false;  // KeyError, exactly as the oracle raises
  const bool ok = qrdisc_as_int64(item, key, out);
  Py_DECREF(item);
  return ok;
}

void qrdisc_raise_refusal(QrdiscPlaneObject* plane, const char* message) {
  PyErr_SetString(plane->refusal_type, message);
}

// --- plane type ------------------------------------------------------------

namespace {

PyObject* qrdisc_plane_new(PyTypeObject* type, PyObject*, PyObject*) {
  QrdiscPlaneObject* self =
      reinterpret_cast<QrdiscPlaneObject*>(type->tp_alloc(type, 0));
  if (self == nullptr) return nullptr;
  self->buffers = new std::vector<QrdiscBuffer>();
  self->scalars = nullptr;
  self->delegates = nullptr;
  self->refusal_type = nullptr;
  self->open_ns = 0;
  self->duration = 0;
  self->family_calls = 0;
  return reinterpret_cast<PyObject*>(self);
}

void qrdisc_plane_dealloc(PyObject* object) {
  PyTypeObject* type = Py_TYPE(object);
  QrdiscPlaneObject* self = reinterpret_cast<QrdiscPlaneObject*>(object);
  if (self->buffers != nullptr) {
    for (QrdiscBuffer& buffer : *self->buffers) {
      Py_XDECREF(buffer.array);
    }
    delete self->buffers;
    self->buffers = nullptr;
  }
  Py_CLEAR(self->scalars);
  Py_CLEAR(self->delegates);
  Py_CLEAR(self->refusal_type);
  // Heap types own a reference from every instance (PyType_FromSpec contract).
  type->tp_free(object);
  Py_DECREF(type);
}

PyType_Slot kQrdiscPlaneSlots[] = {
    {Py_tp_new, reinterpret_cast<void*>(qrdisc_plane_new)},
    {Py_tp_dealloc, reinterpret_cast<void*>(qrdisc_plane_dealloc)},
    {0, nullptr},
};

PyType_Spec kQrdiscPlaneSpec = {
    /* name */ "qr_disc_native.QrdiscPlane",
    /* basicsize */ static_cast<int>(sizeof(QrdiscPlaneObject)),
    /* itemsize */ 0,
    /* flags */ Py_TPFLAGS_DEFAULT,
    /* slots */ kQrdiscPlaneSlots,
};

const QrdiscBuffer* qrdisc_find_buffer(QrdiscPlaneObject* plane,
                                       const std::string& name) {
  for (const QrdiscBuffer& buffer : *plane->buffers) {
    if (buffer.name == name) return &buffer;
  }
  return nullptr;
}

}  // namespace

// A heap type built from a spec rather than a static PyTypeObject: the static
// form leaves ~40 members implicitly zeroed, which this tree's -Werror=
// missing-field-initializers rejects outright (engine/cpp/CMakeLists.txt:36).
PyTypeObject* QrdiscPlaneType = nullptr;

PyObject* qrdisc_plane_type_ready() {
  PyObject* type = PyType_FromSpec(&kQrdiscPlaneSpec);
  if (type == nullptr) return nullptr;
  QrdiscPlaneType = reinterpret_cast<PyTypeObject*>(type);
  return type;
}

// --- build_plane -----------------------------------------------------------

namespace {

bool qrdisc_adopt_buffer(QrdiscPlaneObject* plane, PyObject* key,
                         PyObject* value) {
  if (!PyUnicode_Check(key)) {
    PyErr_Format(PyExc_TypeError,
                 "qrdisc build_plane: buffer key must be str, got %R", key);
    return false;
  }
  if (!PyArray_Check(value)) {
    PyErr_Format(PyExc_TypeError,
                 "qrdisc build_plane: buffer %R must be a numpy ndarray, got %s",
                 key, Py_TYPE(value)->tp_name);
    return false;
  }
  PyArrayObject* array = reinterpret_cast<PyArrayObject*>(value);
  const int ndim = PyArray_NDIM(array);
  const int type_num = PyArray_TYPE(array);
  if (ndim < 1 || ndim > 2) {
    PyErr_Format(PyExc_ValueError,
                 "qrdisc build_plane: buffer %R has ndim=%d, expected 1 or 2",
                 key, ndim);
    return false;
  }
  if (type_num != NPY_INT64 && type_num != NPY_FLOAT64 &&
      type_num != NPY_UINT8) {
    PyErr_Format(PyExc_ValueError,
                 "qrdisc build_plane: buffer %R has dtype num=%d, expected "
                 "int64(%d), float64(%d) or uint8(%d)",
                 key, type_num, NPY_INT64, NPY_FLOAT64, NPY_UINT8);
    return false;
  }
  if (!PyArray_IS_C_CONTIGUOUS(array)) {
    PyErr_Format(PyExc_ValueError,
                 "qrdisc build_plane: buffer %R is not C-contiguous; the "
                 "marshaller must hand over contiguous memory so the native "
                 "side can read it without copying",
                 key);
    return false;
  }
  const char* utf8_name = PyUnicode_AsUTF8(key);
  if (utf8_name == nullptr) return false;  // std::string(nullptr) would be UB
  QrdiscBuffer buffer;
  buffer.name = utf8_name;
  Py_INCREF(value);
  buffer.array = array;
  buffer.data = PyArray_DATA(array);
  buffer.shape[0] = PyArray_DIM(array, 0);
  buffer.shape[1] = ndim == 2 ? PyArray_DIM(array, 1) : 0;
  buffer.ndim = ndim;
  buffer.type_num = type_num;
  plane->buffers->push_back(buffer);
  return true;
}

}  // namespace

PyObject* qrdisc_build_plane(PyObject*, PyObject* args, PyObject* kwargs) {
  static const char* keywords[] = {"scalars", "buffers", "delegates",
                                   "refusal_type", nullptr};
  PyObject* scalars = nullptr;
  PyObject* buffers = nullptr;
  PyObject* delegates = nullptr;
  PyObject* refusal_type = nullptr;
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OOOO",
                                   const_cast<char**>(keywords), &scalars,
                                   &buffers, &delegates, &refusal_type)) {
    return nullptr;
  }
  if (!PyDict_Check(scalars) || !PyDict_Check(buffers) ||
      !PyDict_Check(delegates)) {
    PyErr_SetString(PyExc_TypeError,
                    "qrdisc build_plane: scalars, buffers and delegates must "
                    "all be dicts");
    return nullptr;
  }
  if (!PyType_Check(refusal_type)) {
    PyErr_Format(PyExc_TypeError,
                 "qrdisc build_plane: refusal_type must be the oracle's "
                 "DiscretionaryFeatureRefusal class, got %R",
                 refusal_type);
    return nullptr;
  }
  PyObject* object = qrdisc_plane_new(QrdiscPlaneType, nullptr, nullptr);
  if (object == nullptr) return nullptr;
  QrdiscPlaneObject* plane = reinterpret_cast<QrdiscPlaneObject*>(object);
  Py_INCREF(scalars);
  plane->scalars = scalars;
  Py_INCREF(refusal_type);
  plane->refusal_type = refusal_type;

  PyObject* key = nullptr;
  PyObject* value = nullptr;
  Py_ssize_t position = 0;
  while (PyDict_Next(delegates, &position, &key, &value)) {
    // None is the NATIVE marker: the table maps a segment name either to the
    // oracle callable that still owns it, or to None to say the port owns it
    // now.  Anything else is a mis-wired table, not a swap.
    if (value != Py_None && !PyCallable_Check(value)) {
      PyErr_Format(PyExc_TypeError,
                   "qrdisc build_plane: delegate %R is neither callable nor "
                   "None (got %s); the delegation table maps a segment name to "
                   "the oracle callable that still owns it, or to None once "
                   "the native family has replaced it",
                   key, Py_TYPE(value)->tp_name);
      Py_DECREF(object);
      return nullptr;
    }
  }
  Py_INCREF(delegates);
  plane->delegates = delegates;

  position = 0;
  while (PyDict_Next(buffers, &position, &key, &value)) {
    if (!qrdisc_adopt_buffer(plane, key, value)) {
      Py_DECREF(object);
      return nullptr;
    }
  }
  if (!qrdisc_mapping_int64(scalars, "open_ns", &plane->open_ns) ||
      !qrdisc_mapping_int64(scalars, "duration", &plane->duration)) {
    Py_DECREF(object);
    return nullptr;
  }
  return object;
}

// --- state round-trip surface ---------------------------------------------

PyObject* qrdisc_plane_buffer(PyObject*, PyObject* args) {
  PyObject* object = nullptr;
  const char* name = nullptr;
  if (!PyArg_ParseTuple(args, "Os", &object, &name)) return nullptr;
  if (Py_TYPE(object) != QrdiscPlaneType) {
    PyErr_Format(PyExc_TypeError, "qrdisc plane_buffer: expected a QrdiscPlane, got %s",
                 Py_TYPE(object)->tp_name);
    return nullptr;
  }
  QrdiscPlaneObject* plane = reinterpret_cast<QrdiscPlaneObject*>(object);
  const QrdiscBuffer* buffer = qrdisc_find_buffer(plane, std::string(name));
  if (buffer == nullptr) {
    PyErr_Format(PyExc_KeyError,
                 "qrdisc plane_buffer: no marshalled buffer named '%s' "
                 "(marshalled=%zd buffers)",
                 name, static_cast<Py_ssize_t>(plane->buffers->size()));
    return nullptr;
  }
  // Deliberately NOT the stored ndarray object: the view is rebuilt from the
  // raw pointer the native side will read, so the round-trip check proves the
  // C-visible memory, not the Python object it came from.
  npy_intp shape[2] = {buffer->shape[0], buffer->shape[1]};
  PyObject* view = PyArray_SimpleNewFromData(buffer->ndim, shape,
                                             buffer->type_num, buffer->data);
  if (view == nullptr) return nullptr;
  Py_INCREF(object);
  if (PyArray_SetBaseObject(reinterpret_cast<PyArrayObject*>(view), object) <
      0) {
    Py_DECREF(object);
    Py_DECREF(view);
    return nullptr;
  }
  return view;
}

PyObject* qrdisc_plane_buffer_names(PyObject*, PyObject* args) {
  PyObject* object = nullptr;
  if (!PyArg_ParseTuple(args, "O", &object)) return nullptr;
  if (Py_TYPE(object) != QrdiscPlaneType) {
    PyErr_Format(PyExc_TypeError,
                 "qrdisc plane_buffer_names: expected a QrdiscPlane, got %s",
                 Py_TYPE(object)->tp_name);
    return nullptr;
  }
  QrdiscPlaneObject* plane = reinterpret_cast<QrdiscPlaneObject*>(object);
  PyObject* names =
      PyTuple_New(static_cast<Py_ssize_t>(plane->buffers->size()));
  if (names == nullptr) return nullptr;
  Py_ssize_t index = 0;
  for (const QrdiscBuffer& buffer : *plane->buffers) {
    PyObject* name = PyUnicode_FromString(buffer.name.c_str());
    if (name == nullptr) {
      Py_DECREF(names);
      return nullptr;
    }
    PyTuple_SET_ITEM(names, index, name);
    ++index;
  }
  return names;
}
