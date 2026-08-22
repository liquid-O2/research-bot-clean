// Native ROW ASSEMBLY for the qrdisc port: the half of
// `CausalDiscretionaryPlane.feature_map` that is not a family.
//
// WHY THIS EXISTS (stage 4, wave 2)
//   Wave 1 could only SPLICE: the whole-map delegate assembled the row in
//   Python and native family values were written over it, so a native family
//   cost extra time and saved none.  The blocker is the TAIL —
//   discretionary_features.py:2502-2694, ~190 lines of inline arithmetic over
//   the merged dict that belongs to no family and therefore could never be
//   ported family-by-family.  With the tail native, the row can be assembled
//   here: every family is called individually (natively, or through its own
//   entry in the delegation table), merged in the oracle's insertion order, and
//   the tail runs on the merged map.  The whole-map delegate then has no job
//   left except as the fallback when the table is incomplete.
//
// WHAT IS STILL THE ORACLE'S
//   Every family the port has not ported.  Its bound method is called with
//   feature_map's OWN arguments for this row (qrdisc_assembly.cpp transcribes
//   discretionary_features.py:2404-2500 call site by call site), so delegated
//   arithmetic remains literally the oracle's bytes and a differential
//   mismatch localises to assembly, ordering, or the tail.
//
// ORDER IS IDENTITY
//   The emitted name order is the dense store's column identity
//   (disc_native_differential.py:14-18).  `QrdiscRowValues` therefore
//   reproduces `dict.update` exactly: a new name appends, an existing name
//   keeps its position and takes the new value.
//
// FLOAT LAW
//   Every tail expression is transcribed in the oracle's association order and
//   the module is built with -ffp-contract=off, because the comparison is
//   bit-for-bit.
#ifndef QR_ENTRY_V2_QRDISC_ASSEMBLY_HPP
#define QR_ENTRY_V2_QRDISC_ASSEMBLY_HPP

#include <cstddef>
#include <cstdint>
#include <initializer_list>
#include <string>
#include <unordered_map>

#include "qr_entry_v2/qrdisc_maps.hpp"
#include "qr_entry_v2/qrdisc_plane_state.hpp"

// The merged feature map of ONE row: an ordered (name, value) vector with a
// name index over it.  `set` is `dict.__setitem__`; `lookup` is `dict[name]`,
// raising KeyError from the same place the oracle's subscript would.
class QrdiscRowValues {
 public:
  void set(const std::string& name, double value);
  bool lookup(const char* name, double* out) const;
  const QrdiscValueMap& entries() const { return entries_; }
  void clear();

 private:
  QrdiscValueMap entries_;
  std::unordered_map<std::string, std::size_t> index_;
};

// The per-row objects feature_map passes to its families UNCONVERTED
// (discretionary_features.py:2407 `side=side`, :2407 `current_mid2=`), kept
// distinct from the int64 copies in QrdiscRowInputs: a family that multiplies
// by `side` sees whatever object the caller handed in, and re-boxing it as a
// fresh Python int would be a different object graph than the oracle's.
struct QrdiscRowObjects {
  PyObject* snapshot_ts_ns;  // borrowed, raw
  PyObject* current_bid;     // borrowed, raw
  PyObject* current_ask;     // borrowed, raw
  PyObject* current_mid2;    // borrowed, raw
  PyObject* side;            // borrowed, raw
  PyObject* formation;       // borrowed, raw
};

// Can this plane's delegation table answer EVERY family individually?  True
// means the row can be assembled here; false means the caller must fall back to
// the whole-map delegate.  Sets no exception — it is a question, not a check.
bool qrdisc_assembly_available(QrdiscPlaneObject* plane);

// The native-family dispatcher, owned by the row path (qrdisc_pymodule.cpp's
// `qrdisc_run_family`) because that is the table the family lanes extend.  It
// is passed in rather than called directly so a lane adding a family never has
// to touch this file, and this file never has to know which families exist.
//
// A NATIVE FAMILY EMITS ITS WHOLE BLOCK.  feature_map calls `_event_micro_map`
// seven times (:2487-2494) and `_level_values` seven times (:2443-2455); the
// native family answers all of them in ONE call, in feature_map's own order
// (qrdisc_maps_micro.cpp:4-7).  So the fan-out below runs a block's loop only
// while that family is still the oracle's.
using QrdiscNativeFamilyFn = bool (*)(QrdiscPlaneObject*, const char*,
                                      const QrdiscRowInputs&, QrdiscValueMap*);

// discretionary_features.py:2404-2500 — the family fan-out and the merge.
bool qrdisc_assemble_families(QrdiscPlaneObject* plane,
                              const QrdiscRowInputs& row,
                              const QrdiscRowObjects& objects,
                              QrdiscNativeFamilyFn run_native,
                              std::int64_t* formation_ts_ns_out,
                              QrdiscRowValues* values);

// discretionary_features.py:2502-2694 — the tail, including the non-finite
// refusal at :2692.  `formation_ts_ns` is feature_map's own :2457 value.
bool qrdisc_assembly_tail(QrdiscPlaneObject* plane, const QrdiscRowInputs& row,
                          const QrdiscRowObjects& objects,
                          std::int64_t snapshot_ts_ns,
                          std::int64_t formation_ts_ns,
                          QrdiscRowValues* values);

// The keyword-name tuple one delegated call site passes every row.  Built once
// per call site (a function-local static), never per row: the alternative is
// ~280 short-lived str objects per row across the 40 call sites of the fan-out.
PyObject* qrdisc_kwnames(std::initializer_list<const char*> names);

// The one delegated call shape both halves need: `plane.<name>(**kwargs)` with
// keyword-only arguments, vectorcalled so no kwargs dict is built per row.
// `args` is parallel to `kwnames`; the result is merged into `values` with
// dict.update semantics.  A missing table entry is a KeyError naming the family.
bool qrdisc_delegate_into(QrdiscPlaneObject* plane, const char* family,
                          PyObject* const* args, PyObject* kwnames,
                          QrdiscRowValues* values);

// The delegated call for a family that returns something other than a mapping
// (`_state_series`, discretionary_features.py:1970, is positional and returns a
// Mapping[str, ndarray]).  Returns a NEW reference, or nullptr with the error set.
PyObject* qrdisc_delegate_call(QrdiscPlaneObject* plane, const char* family,
                               PyObject* const* args, std::size_t count,
                               PyObject* kwnames);

// Merge one Mapping[str, float] into `values` in ITS iteration order.
bool qrdisc_merge_mapping(PyObject* mapping, QrdiscRowValues* values);

#endif  // QR_ENTRY_V2_QRDISC_ASSEMBLY_HPP
