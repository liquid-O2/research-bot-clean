// The TAIL of `CausalDiscretionaryPlane.feature_map`, transcribed
// expression-for-expression from discretionary_features.py:2502-2694.
//
// WHY IT IS A FILE OF ITS OWN
//   These ~190 lines belong to no family: they are inline arithmetic over the
//   MERGED map, so no family-by-family port could ever reach them, and while
//   they stayed in Python the whole-map delegate had to assemble every row.
//   Porting them is what lets qrdisc_assembly.cpp own the row.
//
// PYTHON SEMANTICS THAT ARE NOT C++ SEMANTICS
//   `float(a and b and c)` is not `(a && b && c) ? 1.0 : 0.0`.  Python's `and`
//   returns the FIRST falsy operand, else the LAST operand, and float() is
//   applied to THAT object — so `float(x and y)` is y's value when x is
//   truthy, not 1.0.  `qrdisc_and_chain` reproduces it exactly; several tail
//   features (`disc_path_failed_auction_reentry`, :2571) depend on it.
//
// FLOAT LAW
//   Association order is the oracle's, `math.log1p` (:2660) is std::log1p from
//   the same glibc, and -ffp-contract=off keeps a fused multiply-add out of
//   `conflict_fraction * log1p(...)`.
#include "qr_entry_v2/qrdisc_assembly.hpp"

#include <cmath>
#include <initializer_list>
#include <string>
#include <vector>

#include "qr_entry_v2/qrdisc_np_kernels.hpp"

namespace {

// discretionary_features.py's `float(a and b and ...)`: the first falsy operand
// (whose float() is 0.0 for every numeric type the tail sees), else the last.
double qrdisc_and_chain(std::initializer_list<double> operands) {
  double last = 0.0;
  for (const double operand : operands) {
    if (operand == 0.0) return 0.0;
    last = operand;
  }
  return last;
}

// `values[name]` with the read failure latched, so one gathering block reads a
// dozen names and is checked once instead of nesting a branch per lookup.
class QrdiscTailReader {
 public:
  explicit QrdiscTailReader(const QrdiscRowValues* values) : values_(values) {}
  double operator()(const char* name) {
    if (failed_) return 0.0;
    double out = 0.0;
    if (!values_->lookup(name, &out)) failed_ = true;
    return out;
  }
  bool failed() const { return failed_; }

 private:
  const QrdiscRowValues* values_;
  bool failed_ = false;
};

// The row of `_state_series` (discretionary_features.py:1970) the tail reads,
// already indexed at :2527-2529.
struct QrdiscStateRow {
  double displacement = 0.0;
  double adverse_max = 0.0;
  double favorable_max = 0.0;
  double adverse_seen = 0.0;
  double reclaim_seen = 0.0;
  double lift_seen = 0.0;
  double retest_seen = 0.0;
  double invalidated_seen = 0.0;
  std::int64_t first_ts_ns[4] = {0, 0, 0, 0};
};

// Every column reference one row borrows data from, released together after
// the LAST read (R6 F11).  `PyMapping_GetItemString` returns a NEW reference
// and `PyArray_DATA` hands back memory the ARRAY owns; what keeps the series
// alive across the reads below is the `state` mapping this row holds, NOT the
// plane's `_state_cache` — a `_state_series` delegate that built its mapping on
// the fly would leave every borrowed pointer dangling the moment the column
// reference was dropped.  Holding the references removes that dependence.
class QrdiscColumnRefs {
 public:
  QrdiscColumnRefs() = default;
  QrdiscColumnRefs(const QrdiscColumnRefs&) = delete;
  QrdiscColumnRefs& operator=(const QrdiscColumnRefs&) = delete;
  ~QrdiscColumnRefs() {
    for (PyObject* held : refs_) Py_DECREF(held);
  }
  void keep(PyObject* reference) { refs_.push_back(reference); }

 private:
  std::vector<PyObject*> refs_;
};

// One marshalled column of the state series, checked for the dtype the oracle
// built it with: a silent reinterpretation here would be invisible arithmetic.
const void* qrdisc_state_column(PyObject* state, const char* name, int type_num,
                                npy_intp* length, QrdiscColumnRefs* refs) {
  PyObject* column = PyMapping_GetItemString(state, name);
  if (column == nullptr) return nullptr;
  if (!PyArray_Check(column)) {
    PyErr_Format(PyExc_TypeError,
                 "qrdisc tail: _state_series['%s'] is %s, expected ndarray",
                 name, Py_TYPE(column)->tp_name);
    Py_DECREF(column);
    return nullptr;
  }
  PyArrayObject* array = reinterpret_cast<PyArrayObject*>(column);
  if (PyArray_TYPE(array) != type_num || PyArray_NDIM(array) != 1 ||
      !PyArray_IS_C_CONTIGUOUS(array)) {
    PyErr_Format(PyExc_TypeError,
                 "qrdisc tail: _state_series['%s'] is type %d ndim %d, "
                 "expected a contiguous 1-D type %d",
                 name, PyArray_TYPE(array), PyArray_NDIM(array), type_num);
    Py_DECREF(column);
    return nullptr;
  }
  *length = PyArray_DIM(array, 0);
  const void* data = PyArray_DATA(array);
  // The reference moves to the caller's QrdiscColumnRefs and is dropped only
  // after the last read of `data` (R6 F11), so the pointer never outlives the
  // object that owns its memory.
  refs->keep(column);
  return data;
}

bool qrdisc_read_state_row(QrdiscPlaneObject* plane,
                           const QrdiscRowObjects& objects,
                           std::int64_t snapshot_ts_ns,
                           std::int64_t formation_ts_ns,
                           std::int64_t formation_mid2, QrdiscStateRow* out) {
  PyObject* formation_object = PyLong_FromLongLong(formation_ts_ns);
  PyObject* mid2_object = PyLong_FromLongLong(formation_mid2);
  if (formation_object == nullptr || mid2_object == nullptr) {
    Py_XDECREF(formation_object);
    Py_XDECREF(mid2_object);
    return false;
  }
  // :2526 — `self._state_series(formation_ts_ns, formation_mid2, side)`, all
  // three POSITIONAL, `side` unconverted.
  PyObject* args[3] = {formation_object, mid2_object, objects.side};
  PyObject* state =
      qrdisc_delegate_call(plane, "_state_series", args, 3, nullptr);
  Py_DECREF(formation_object);
  Py_DECREF(mid2_object);
  if (state == nullptr) return false;

  QrdiscColumnRefs columns;
  npy_intp timestamps_length = 0;
  npy_intp displacement_length = 0;
  npy_intp first_length = 0;
  const std::int64_t* timestamps = static_cast<const std::int64_t*>(
      qrdisc_state_column(state, "ts_ns", NPY_INT64, &timestamps_length,
                          &columns));
  const double* displacement = static_cast<const double*>(qrdisc_state_column(
      state, "displacement", NPY_FLOAT64, &displacement_length, &columns));
  const std::int64_t* first_ts_ns = static_cast<const std::int64_t*>(
      qrdisc_state_column(state, "first_ts_ns", NPY_INT64, &first_length,
                          &columns));
  if (timestamps == nullptr || displacement == nullptr ||
      first_ts_ns == nullptr) {
    Py_DECREF(state);
    return false;
  }
  // An EMPTY series would clamp the index below to -1 and every column read
  // after it would run one element before the buffer (R6 F13).  The oracle
  // never builds one, so this is a refusal, not a branch.
  if (displacement_length == 0) {
    PyErr_Format(PyExc_ValueError,
                 "qrdisc tail: _state_series['displacement'] has %lld entries, "
                 "expected at least 1 (the snapshot index would clamp to -1)",
                 static_cast<long long>(displacement_length));
    Py_DECREF(state);
    return false;
  }
  // :2527-2529 — searchsorted-left minus one, then clamped into the series.
  const std::int64_t found = qrdisc_searchsorted_left_i64(
      QrdiscI64Span{timestamps, static_cast<std::int64_t>(timestamps_length)},
      snapshot_ts_ns);
  std::int64_t index = found - 1;
  if (index < 0) index = 0;
  if (index > displacement_length - 1) index = displacement_length - 1;

  const char* const flags[5] = {"adverse_seen", "reclaim_seen", "lift_seen",
                                "retest_seen", "invalidated_seen"};
  double* const targets[5] = {&out->adverse_seen, &out->reclaim_seen,
                              &out->lift_seen, &out->retest_seen,
                              &out->invalidated_seen};
  for (int slot = 0; slot < 5; ++slot) {
    npy_intp length = 0;
    const std::uint8_t* column = static_cast<const std::uint8_t*>(
        qrdisc_state_column(state, flags[slot], NPY_BOOL, &length, &columns));
    if (column == nullptr) {
      Py_DECREF(state);
      return false;
    }
    *targets[slot] = column[index] != 0 ? 1.0 : 0.0;
  }
  const char* const maxima[2] = {"adverse_max", "favorable_max"};
  double* const maxima_targets[2] = {&out->adverse_max, &out->favorable_max};
  for (int slot = 0; slot < 2; ++slot) {
    npy_intp length = 0;
    const double* column = static_cast<const double*>(
        qrdisc_state_column(state, maxima[slot], NPY_FLOAT64, &length,
                            &columns));
    if (column == nullptr) {
      Py_DECREF(state);
      return false;
    }
    *maxima_targets[slot] = column[index];
  }
  out->displacement = displacement[index];
  if (first_length != 4) {
    PyErr_Format(PyExc_ValueError,
                 "qrdisc tail: _state_series['first_ts_ns'] has %lld entries, "
                 "expected 4 (adverse, reclaim, lift, retest)",
                 static_cast<long long>(first_length));
    Py_DECREF(state);
    return false;
  }
  for (int slot = 0; slot < 4; ++slot) out->first_ts_ns[slot] = first_ts_ns[slot];
  Py_DECREF(state);
  return true;
}

// :2531-2533 — `state_age`.
double qrdisc_state_age(std::int64_t snapshot_ts_ns, std::int64_t first) {
  if (0 <= first && first < snapshot_ts_ns) {
    return static_cast<double>(snapshot_ts_ns - first) / 1e9;
  }
  return 0.0;
}

}  // namespace

bool qrdisc_assembly_tail(QrdiscPlaneObject* plane, const QrdiscRowInputs& row,
                          const QrdiscRowObjects& objects,
                          std::int64_t snapshot_ts_ns,
                          std::int64_t formation_ts_ns,
                          QrdiscRowValues* values) {
  QrdiscTailReader read(values);

  // :2502-2524 — the event-horizon ratios.  `event_prefixes` (:2486-2489) is
  // rebuilt here rather than carried: it is a pure function of the horizon.
  const double attack_h1 = read("disc_evt_h1_attack_event_rate");
  const double attack_h5 = read("disc_evt_h5_attack_event_rate");
  const double attack_h30 = read("disc_evt_h30_attack_event_rate");
  const double attack_h60 = read("disc_evt_h60_attack_event_rate");
  const double lift_h1 = read("disc_evt_h1_lift_event_rate");
  const double lift_h5 = read("disc_evt_h5_lift_event_rate");
  const double lift_h30 = read("disc_evt_h30_lift_event_rate");
  const double lift_h60 = read("disc_evt_h60_lift_event_rate");
  const double reload_h5 = read("disc_evt_h5_reload_per_attack");
  const double reload_h60 = read("disc_evt_h60_reload_per_attack");
  if (read.failed()) return false;
  const double attack_exhaustion = attack_h5 < attack_h30 ? 1.0 : 0.0;
  const double lift_acceleration = lift_h5 > lift_h30 ? 1.0 : 0.0;
  values->set("disc_mhi_attack_rate_1_over_30",
              (attack_h1 + 1.0) / (attack_h30 + 1.0));
  values->set("disc_mhi_attack_rate_5_over_60",
              (attack_h5 + 1.0) / (attack_h60 + 1.0));
  values->set("disc_mhi_lift_rate_1_over_30",
              (lift_h1 + 1.0) / (lift_h30 + 1.0));
  values->set("disc_mhi_lift_rate_5_over_60",
              (lift_h5 + 1.0) / (lift_h60 + 1.0));
  values->set("disc_mhi_reload_per_attack_5_minus_60", reload_h5 - reload_h60);
  values->set("disc_mhi_attack_exhaustion_5_vs_30", attack_exhaustion);
  values->set("disc_mhi_lift_acceleration_5_vs_30", lift_acceleration);

  // :2526-2548 — the per-candidate state series, indexed at this snapshot.
  QrdiscStateRow state;
  if (!qrdisc_read_state_row(plane, objects, snapshot_ts_ns, formation_ts_ns,
                             row.formation_mid2, &state)) {
    return false;
  }
  values->set("disc_state_current_displacement_ticks", state.displacement);
  values->set("disc_state_adverse_max_ticks", state.adverse_max);
  values->set("disc_state_favorable_max_ticks", state.favorable_max);
  values->set("disc_state_adverse_seen", state.adverse_seen);
  values->set("disc_state_reclaim_seen", state.reclaim_seen);
  values->set("disc_state_lift_seen", state.lift_seen);
  values->set("disc_state_retest_seen", state.retest_seen);
  values->set("disc_state_invalidated_seen", state.invalidated_seen);
  values->set("disc_state_adverse_age_sec",
              qrdisc_state_age(snapshot_ts_ns, state.first_ts_ns[0]));
  values->set("disc_state_reclaim_age_sec",
              qrdisc_state_age(snapshot_ts_ns, state.first_ts_ns[1]));
  values->set("disc_state_lift_age_sec",
              qrdisc_state_age(snapshot_ts_ns, state.first_ts_ns[2]));
  values->set("disc_state_retest_age_sec",
              qrdisc_state_age(snapshot_ts_ns, state.first_ts_ns[3]));
  values->set("disc_state_near_formation_z2",
              std::fabs(state.displacement) <= 2.0 ? 1.0 : 0.0);

  // :2549-2591 — absorption and path, all off the z2 level window.
  double factor = 0.0;
  PyObject* factor_object = PyDict_GetItemString(plane->scalars, "factor");
  if (factor_object == nullptr) {
    PyErr_SetString(PyExc_KeyError, "qrdisc: scalar 'factor' is missing");
    return false;
  }
  factor = PyFloat_AsDouble(factor_object);
  if (factor == -1.0 && PyErr_Occurred()) return false;
  const double attack = read("disc_level_z2_attack_volume");
  const double lift = read("disc_level_z2_lift_volume");
  const double reloads = read("disc_level_z2_defense_reload_count");
  const double pulls = read("disc_level_z2_defense_pull_no_fill");
  const double memory_bursts = read("disc_memory_z2_attack_bursts");
  if (read.failed()) return false;
  const double displacement_usd =
      static_cast<double>(row.side * (row.current_mid2 - row.formation_mid2)) *
      factor;
  values->set("disc_state_price_yield_per_attack",
              attack != 0.0 ? displacement_usd / attack : 0.0);
  values->set("disc_state_price_yield_per_net_aggression",
              lift != attack ? displacement_usd / std::fabs(lift - attack)
                             : 0.0);
  const double adverse_ticks = state.adverse_max;
  const double favorable_ticks = state.favorable_max;
  values->set("disc_absorption_attack_per_adverse_tick",
              attack / (1.0 + adverse_ticks));
  values->set("disc_absorption_lift_per_favorable_tick",
              lift / (1.0 + favorable_ticks));
  values->set("disc_absorption_reload_per_attack",
              attack != 0.0 ? reloads / attack : 0.0);
  values->set("disc_absorption_pull_vs_refill",
              (pulls + 1.0) / (reloads + 1.0));
  values->set("disc_absorption_two_sided",
              qrdisc_and_chain({attack > 0.0 ? 1.0 : 0.0,
                                lift > 0.0 ? 1.0 : 0.0}));
  values->set("disc_path_failed_auction_reentry",
              qrdisc_and_chain({state.adverse_seen, state.reclaim_seen}));
  values->set("disc_path_absorption_control_transfer",
              qrdisc_and_chain({attack > 0.0 ? 1.0 : 0.0,
                                reloads > 0.0 ? 1.0 : 0.0, state.lift_seen}));
  values->set("disc_path_refill_exhaustion_liftoff",
              qrdisc_and_chain({reloads > 0.0 ? 1.0 : 0.0,
                                attack_exhaustion > 0.0 ? 1.0 : 0.0,
                                lift_acceleration > 0.0 ? 1.0 : 0.0}));
  values->set("disc_path_ofm_retest_complete",
              qrdisc_and_chain({state.adverse_seen, state.reclaim_seen,
                                state.lift_seen, state.retest_seen}));
  values->set("disc_path_defended_retest_current",
              qrdisc_and_chain({state.retest_seen,
                                state.invalidated_seen == 0.0 ? 1.0 : 0.0,
                                state.displacement >= -1.0 ? 1.0 : 0.0}));
  values->set("disc_path_second_test_memory",
              memory_bursts >= 2.0 ? 1.0 : 0.0);
  values->set("disc_path_failed_reclaim_continuation",
              qrdisc_and_chain({state.reclaim_seen,
                                state.displacement <= -1.0 ? 1.0 : 0.0}));

  // :2592-2643 — value acceptance, headroom and the forecast/obstacle ratios.
  const double above = read("disc_auction_session_above_value_time_fraction");
  const double below = read("disc_auction_session_below_value_time_fraction");
  const double phase_headroom = read("disc_fvol_phase_q50_remaining_usd");
  const double inside_value = read("disc_auction_session_inside_value");
  const double path_efficiency = read("disc_regime_h300_path_efficiency");
  const double next_room = read("disc_target_next_room_usd");
  const double phase_q90 = read("disc_fvol_phase_q90_remaining_usd");
  const double ib_break = read("disc_ib_phase_directional_break_seen");
  const double ib_reentry = read("disc_ib_phase_directional_break_reentry_seen");
  const double escape_accepted =
      read("disc_auction_phase_directional_acceptance_score");
  const double escape_failed =
      read("disc_auction_phase_failed_directional_auction");
  const double delta_at_value =
      read("disc_auction_phase_directional_delta_fraction");
  const double poc_5m = read("disc_auction_phase_poc_migration_5m_aligned_usd");
  const double poc_15m = read("disc_auction_phase_poc_migration_15m_aligned_usd");
  if (read.failed()) return false;
  const double directional_acceptance = row.side > 0 ? above : below;
  const double opposite_acceptance = row.side > 0 ? below : above;
  values->set("disc_path_directional_value_acceptance", directional_acceptance);
  values->set("disc_path_opposite_value_acceptance", opposite_acceptance);
  values->set("disc_path_balance_fade_context",
              qrdisc_and_chain({inside_value > 0.0 ? 1.0 : 0.0,
                                path_efficiency < .35 ? 1.0 : 0.0}));
  values->set("disc_path_balance_fade_confirmed",
              qrdisc_and_chain({inside_value > 0.0 ? 1.0 : 0.0,
                                state.adverse_seen, state.reclaim_seen}));
  values->set("disc_path_expansion_context",
              qrdisc_and_chain({directional_acceptance >= .5 ? 1.0 : 0.0,
                                path_efficiency >= .35 ? 1.0 : 0.0}));
  values->set("disc_path_expansion_with_headroom",
              qrdisc_and_chain({directional_acceptance >= .5 ? 1.0 : 0.0,
                                phase_headroom > 0.0 ? 1.0 : 0.0}));
  values->set("disc_path_profile_forecast_headroom_ratio",
              phase_headroom > 0 ? next_room / phase_headroom : 0.0);
  values->set("disc_path_profile_forecast_q90_headroom_ratio",
              phase_q90 > 0 ? next_room / phase_q90 : 0.0);
  values->set("disc_path_forecast_clears_next_obstacle_q50",
              phase_headroom >= next_room && next_room > 0 ? 1.0 : 0.0);
  values->set("disc_path_forecast_clears_next_obstacle_q90",
              phase_q90 >= next_room && next_room > 0 ? 1.0 : 0.0);
  values->set("disc_path_obstacle_minus_q50_headroom_usd",
              next_room - phase_headroom);
  values->set("disc_path_ib_directional_break", ib_break);
  values->set("disc_path_ib_failed_break", ib_reentry);
  values->set("disc_path_value_escape_accepted", escape_accepted);
  values->set("disc_path_value_escape_failed", escape_failed);
  values->set("disc_path_directional_delta_at_value", delta_at_value);
  values->set("disc_path_poc_migration_acceleration_usd",
              poc_5m - (poc_15m / 3.0));

  // :2644-2687 — behaviour and the cross-horizon differences.
  const double persistence_n32 =
      read("disc_tclock_n32_sign_autocorrelation_lag1");
  const double persistence_n128 =
      read("disc_tclock_n128_sign_autocorrelation_lag1");
  const double size_hhi = read("disc_tclock_n32_size_hhi");
  const double aligned_flow = read("disc_tclock_n32_aligned_flow_fraction");
  const double commitment_n64 = read("disc_eclock_n64_defense_commitment");
  const double withdrawal_n64 = read("disc_eclock_n64_opposing_withdrawal");
  const double commitment_n256 = read("disc_eclock_n256_defense_commitment");
  const double response_last = read("disc_test_response_h5_favorable_last_ticks");
  const double response_first =
      read("disc_test_response_h5_favorable_first_ticks");
  const double pull_over_reload = read("disc_test_pull_over_reload_size");
  const double tape_event_h30 = read("disc_tape_h30_event_slope_per_sec2");
  const double tape_event_h120 = read("disc_tape_h120_event_slope_per_sec2");
  const double tape_volume_h30 = read("disc_tape_h30_volume_slope_per_sec2");
  const double tape_volume_h120 = read("disc_tape_h120_volume_slope_per_sec2");
  const double phase_coverage = read("disc_fvol_phase_q50_coverage");
  if (read.failed()) return false;
  const double attack_plus_lift = attack + lift;
  const double smaller = lift < attack ? lift : attack;  // Python's min(a, b)
  const double conflict_fraction =
      attack_plus_lift != 0.0 ? 2.0 * smaller / attack_plus_lift : 0.0;
  values->set("disc_behavior_aggressor_persistence", persistence_n32);
  values->set("disc_behavior_aggressor_concentration", size_hhi);
  values->set("disc_behavior_defense_commitment", commitment_n64);
  values->set("disc_behavior_opposing_withdrawal", withdrawal_n64);
  values->set("disc_behavior_price_elasticity_per_attack",
              attack != 0.0 ? adverse_ticks / attack : 0.0);
  values->set("disc_behavior_conflict_fraction", conflict_fraction);
  values->set("disc_behavior_conflict_intensity",
              conflict_fraction * std::log1p(attack_plus_lift));
  values->set("disc_behavior_response_decay_h5_ticks",
              response_last - response_first);
  values->set("disc_behavior_control_evidence_balance",
              aligned_flow + commitment_n64 + withdrawal_n64 - pull_over_reload);
  values->set("disc_mhi_tape_event_slope_30_minus_120",
              tape_event_h30 - tape_event_h120);
  values->set("disc_mhi_tape_volume_slope_30_minus_120",
              tape_volume_h30 - tape_volume_h120);
  values->set("disc_mhi_trade_persistence_32_minus_128",
              persistence_n32 - persistence_n128);
  values->set("disc_mhi_defense_commitment_64_minus_256",
              commitment_n64 - commitment_n256);
  values->set("disc_mhi_tape_slope_x_phase_headroom",
              tape_volume_h30 * phase_headroom);
  values->set("disc_mhi_flow_x_phase_headroom_fraction",
              aligned_flow *
                  (1.0 - (phase_coverage < 1.0 ? phase_coverage : 1.0)));

  // :2688-2691 — the two association-mode flags.
  PyObject* mode = PyDict_GetItemString(plane->scalars, "level_association_mode");
  if (mode == nullptr) {
    PyErr_SetString(PyExc_KeyError,
                    "qrdisc: scalar 'level_association_mode' is missing");
    return false;
  }
  const int destroyed =
      PyUnicode_CompareWithASCIIString(mode, "LEVEL_ASSOCIATION_DESTROYED");
  const int uncoupled =
      PyUnicode_CompareWithASCIIString(mode, "FILL_COUPLING_DESTROYED");
  if (PyErr_Occurred()) return false;
  values->set("disc_level_association_destroyed", destroyed == 0 ? 1.0 : 0.0);
  values->set("disc_fill_coupling_destroyed", uncoupled == 0 ? 1.0 : 0.0);

  // :2692-2693 — the refusal, with the oracle's own message.
  for (const std::pair<std::string, double>& entry : values->entries()) {
    if (!std::isfinite(entry.second)) {
      qrdisc_raise_refusal(plane, "discretionary feature map is non-finite");
      return false;
    }
  }
  return true;
}
