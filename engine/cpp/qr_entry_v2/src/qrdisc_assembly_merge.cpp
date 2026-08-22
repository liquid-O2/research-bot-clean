// The merged-map and delegation primitives of the qrdisc native row assembly.
//
// Split from qrdisc_assembly.cpp so each file stays inside one read: this side
// is the mechanism (dict.update ordering, the keyword-name cache, the
// vectorcall into the delegation table) and does not grow as families land;
// the other side is the transcription of feature_map's fan-out, which shrinks
// as they do.  The contract for both is in
// include/qr_entry_v2/qrdisc_assembly.hpp.
#include "qr_entry_v2/qrdisc_assembly.hpp"

#include <string>

// --- the merged map --------------------------------------------------------

void QrdiscRowValues::set(const std::string& name, double value) {
  const std::unordered_map<std::string, std::size_t>::iterator found =
      index_.find(name);
  if (found != index_.end()) {
    // `dict.__setitem__` on an existing key keeps its POSITION and replaces the
    // value; appending instead would move a store column.
    entries_[found->second].second = value;
    return;
  }
  index_.emplace(name, entries_.size());
  entries_.emplace_back(name, value);
}

bool QrdiscRowValues::lookup(const char* name, double* out) const {
  const std::unordered_map<std::string, std::size_t>::const_iterator found =
      index_.find(std::string(name));
  if (found == index_.end()) {
    PyErr_Format(PyExc_KeyError,
                 "qrdisc assembly: the merged feature map has no '%s'; a "
                 "family the tail reads from did not emit it", name);
    return false;
  }
  *out = entries_[found->second].second;
  return true;
}

void QrdiscRowValues::clear() {
  entries_.clear();
  index_.clear();
}

bool qrdisc_merge_mapping(PyObject* mapping, QrdiscRowValues* values) {
  if (PyDict_CheckExact(mapping)) {
    PyObject* key = nullptr;
    PyObject* value = nullptr;
    Py_ssize_t position = 0;
    while (PyDict_Next(mapping, &position, &key, &value)) {
      Py_ssize_t size = 0;
      const char* utf8 = PyUnicode_Check(key)
                             ? PyUnicode_AsUTF8AndSize(key, &size)
                             : nullptr;
      if (utf8 == nullptr) {
        PyErr_Format(PyExc_TypeError,
                     "qrdisc assembly: feature name %R is not str", key);
        return false;
      }
      const double as_double = PyFloat_AsDouble(value);
      if (as_double == -1.0 && PyErr_Occurred()) return false;
      values->set(std::string(utf8, static_cast<std::size_t>(size)), as_double);
    }
    return true;
  }
  // PriorSessionContext returns a MappingProxyType (discretionary_features.py:
  // 177, :201), which is not a dict; its items() preserves insertion order.
  PyObject* items = PyMapping_Items(mapping);
  if (items == nullptr) return false;
  if (!PyList_Check(items)) {
    PyErr_Format(PyExc_TypeError,
                 "qrdisc assembly: items() gave %s, expected a list of "
                 "(name, value) pairs", Py_TYPE(items)->tp_name);
    Py_DECREF(items);
    return false;
  }
  const Py_ssize_t count = PyList_GET_SIZE(items);
  for (Py_ssize_t index = 0; index < count; ++index) {
    PyObject* pair = PyList_GET_ITEM(items, index);
    if (!PyTuple_Check(pair) || PyTuple_GET_SIZE(pair) != 2) {
      PyErr_Format(PyExc_TypeError,
                   "qrdisc assembly: mapping item %zd is %R, expected a "
                   "(name, value) pair", index, pair);
      Py_DECREF(items);
      return false;
    }
    Py_ssize_t size = 0;
    PyObject* key = PyTuple_GET_ITEM(pair, 0);
    const char* utf8 =
        PyUnicode_Check(key) ? PyUnicode_AsUTF8AndSize(key, &size) : nullptr;
    if (utf8 == nullptr) {
      PyErr_Format(PyExc_TypeError,
                   "qrdisc assembly: feature name %R is not str", key);
      Py_DECREF(items);
      return false;
    }
    const double as_double = PyFloat_AsDouble(PyTuple_GET_ITEM(pair, 1));
    if (as_double == -1.0 && PyErr_Occurred()) {
      Py_DECREF(items);
      return false;
    }
    values->set(std::string(utf8, static_cast<std::size_t>(size)), as_double);
  }
  Py_DECREF(items);
  return true;
}

// --- the delegation table --------------------------------------------------

PyObject* qrdisc_kwnames(std::initializer_list<const char*> names) {
  PyObject* tuple = PyTuple_New(static_cast<Py_ssize_t>(names.size()));
  if (tuple == nullptr) return nullptr;
  Py_ssize_t index = 0;
  for (const char* name : names) {
    PyObject* item = PyUnicode_InternFromString(name);
    if (item == nullptr) {
      Py_DECREF(tuple);
      return nullptr;
    }
    PyTuple_SET_ITEM(tuple, index, item);
    ++index;
  }
  return tuple;  // immortal by construction: one per call site, never freed
}

PyObject* qrdisc_delegate_call(QrdiscPlaneObject* plane, const char* family,
                               PyObject* const* args, std::size_t count,
                               PyObject* kwnames) {
  PyObject* delegate = PyDict_GetItemString(plane->delegates, family);
  if (delegate == nullptr || delegate == Py_None) {
    PyErr_Format(PyExc_KeyError,
                 "qrdisc assembly: the delegation table has no callable for "
                 "'%s'; native row assembly needs every family the port does "
                 "not own to be delegated individually", family);
    return nullptr;
  }
  return PyObject_Vectorcall(delegate, args, count, kwnames);
}

bool qrdisc_delegate_into(QrdiscPlaneObject* plane, const char* family,
                          PyObject* const* args, PyObject* kwnames,
                          QrdiscRowValues* values) {
  PyObject* mapping = qrdisc_delegate_call(plane, family, args, 0, kwnames);
  if (mapping == nullptr) return false;
  const bool merged = qrdisc_merge_mapping(mapping, values);
  Py_DECREF(mapping);
  return merged;
}

