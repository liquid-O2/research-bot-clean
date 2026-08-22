// Natively-computed feature-map families of the qrdisc port.
//
// WHAT A "FAMILY" IS
//   `CausalDiscretionaryPlane.feature_map` (discretionary_features.py:2389) is
//   a sequence of per-family helper calls whose dicts are merged in order.  A
//   family ports independently: the differential arbitrates each swap on its
//   own (D-017), and a family still delegated to the oracle is always lawful.
//
// ORDER IS PART OF THE CONTRACT
//   A family returns an ORDERED (name, value) vector, not a dict, because the
//   emitted name order is identity for the dense store
//   (disc_native_differential.py:14-18).  Wave 1 splices these values into the
//   oracle's own mapping, so order is not yet load-bearing at the store
//   boundary; it is asserted directly against the oracle's bound method by
//   engine/entry_v2/test_qrdisc_maps.py so the wave that assembles the row
//   natively inherits a proven order.
//
// FLOAT LAW
//   Every expression is transcribed in the ORACLE's association order, and the
//   module is built with -ffp-contract=off (house FP law), because the
//   comparison is bit-for-bit and a fused multiply-add is a different number.
#ifndef QR_ENTRY_V2_QRDISC_MAPS_HPP
#define QR_ENTRY_V2_QRDISC_MAPS_HPP

#include <cstdint>
#include <string>
#include <utility>
#include <vector>

#include "qr_entry_v2/qrdisc_plane_state.hpp"

using QrdiscValueMap = std::vector<std::pair<std::string, double>>;

// The per-row arguments every family draws from; assembled once by the row
// path so a family never re-parses the candidate mapping.
struct QrdiscRowInputs {
  PyObject* formation_candidate;  // borrowed
  std::int64_t snapshot_ts_ns;
  std::int64_t snapshot_sec;
  std::int64_t formation_sec;
  // `(formation_bid if side > 0 else formation_ask) // raw_tick`, transcribed
  // from feature_map:2432-2433; the event/level families all centre on it.
  std::int64_t formation_tick;
  std::int64_t phase_open_sec;  // UNCLAMPED, as feature_map:2400 computes it
  std::int64_t current_mid2;
  std::int64_t formation_mid2;
  std::int64_t side;
};

// `float(mapping.get(key, 0.0))` with the oracle's own swallow-and-zero
// behaviour (discretionary_features.py:2039-2044): TypeError and ValueError
// become 0.0.  `clamp_nonfinite` is the `number()` closure's extra
// `value if math.isfinite(value) else 0.0` step, which feature_map:2437 does
// NOT apply when it reads `atr14_prev_usd` — one call site, one behaviour.
// Returns false only on an error the oracle would NOT have swallowed.
bool qrdisc_candidate_number(PyObject* mapping, const std::string& key,
                             bool clamp_nonfinite, double* out);

// One `self._last_mid[a:b]` window with the zero entries dropped, reduced to
// the four facts the vol/regime families ask of it.
struct QrdiscMidWindow {
  std::int64_t count;
  std::int64_t first;
  std::int64_t last;
  std::int64_t lowest;
  std::int64_t highest;
  std::int64_t absolute_variation;  // sum |diff|, int64-exact as numpy's is
};

QrdiscMidWindow qrdisc_mid_window(const std::int64_t* mids, std::int64_t begin,
                                  std::int64_t end);

// discretionary_features.py:2029 — `_forward_vol_map`.
bool qrdisc_forward_vol_map(QrdiscPlaneObject* plane,
                            const QrdiscRowInputs& row, QrdiscValueMap* out);

// discretionary_features.py:2226 — `_regime_map`.
bool qrdisc_regime_map(QrdiscPlaneObject* plane, const QrdiscRowInputs& row,
                       QrdiscValueMap* out);

// discretionary_features.py:2272 — `_target_map`.  `atr_usd` is read by
// feature_map:2437, not by the family itself, so it is passed in.
bool qrdisc_target_map(QrdiscPlaneObject* plane, const QrdiscRowInputs& row,
                       double atr_usd, QrdiscValueMap* out);

// discretionary_features.py:1897 — `_event_micro_map`, emitted for all seven
// horizons of feature_map:2487 in that loop's order.
bool qrdisc_event_micro_map(QrdiscPlaneObject* plane, const QrdiscRowInputs& row,
                            QrdiscValueMap* out);

// discretionary_features.py:1576 — `_trade_slice_map`.  NOT a feature_map
// family: it is the shared body of `_trade_clock_map` (:1671) and
// `_volume_clock_map` (:1683), which own the window arguments, so it is
// exported as a kernel and gated at its own seam.
bool qrdisc_trade_slice_map(QrdiscPlaneObject* plane, const std::string& prefix,
                            std::int64_t left, std::int64_t right,
                            double support_fraction,
                            std::int64_t snapshot_ts_ns,
                            std::int64_t formation_ts_ns, std::int64_t side,
                            QrdiscValueMap* out);

// discretionary_features.py:2321 — `_prior_reaction_map`.
bool qrdisc_prior_reaction_map(QrdiscPlaneObject* plane,
                               const QrdiscRowInputs& row, QrdiscValueMap* out);

// discretionary_features.py:1471 — `_event_clock_map`, emitted for all four
// target counts of feature_map:2461 in that loop's order.
bool qrdisc_event_clock_map(QrdiscPlaneObject* plane, const QrdiscRowInputs& row,
                            QrdiscValueMap* out);

// discretionary_features.py:1671 — `_trade_clock_map`, all four target counts
// of feature_map:2466.
bool qrdisc_trade_clock_map(QrdiscPlaneObject* plane, const QrdiscRowInputs& row,
                            QrdiscValueMap* out);

// discretionary_features.py:1683 — `_volume_clock_map`, all three target
// volumes of feature_map:2471.
bool qrdisc_volume_clock_map(QrdiscPlaneObject* plane, const QrdiscRowInputs& row,
                             QrdiscValueMap* out);

// The buffer lookup the families read marshalled state through.  Returns
// nullptr and sets KeyError naming the missing buffer, or TypeError when the
// buffer is not the (type_num, ndim) the MARSHALLER emits for that name
// (R6 F6).  Every call site states what it expects, because the pointer is
// reinterpreted immediately afterwards: a buffer whose dtype changed would
// otherwise be read as the wrong integer width with no diagnostic at all.
// The expected dtype is the marshaller's, not the oracle's — bool and int8
// cross as uint8 VIEWS (qrdisc_state_marshal.py:72-89), so `_trade_sign` is
// NPY_UINT8 here even though the oracle builds it as int8.
const QrdiscBuffer* qrdisc_plane_buffer_named(QrdiscPlaneObject* plane,
                                              const char* name,
                                              int expected_type_num,
                                              int expected_ndim);

// Column index of `name` inside one of the marshalled field-name tuples
// (`profile_int_fields`, ...).  Returns -1 and sets KeyError if absent, so a
// renamed dataclass field fails loudly instead of reading its neighbour.
Py_ssize_t qrdisc_scalar_field_index(QrdiscPlaneObject* plane,
                                     const char* tuple_name, const char* name);

#endif  // QR_ENTRY_V2_QRDISC_MAPS_HPP
