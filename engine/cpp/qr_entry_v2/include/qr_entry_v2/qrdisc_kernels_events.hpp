// Shared per-row kernels of the qrdisc port: the helpers that more than one
// feature-map family calls, plus the numpy reductions this port refuses to
// re-derive.
//
// WHY A SEPARATE FILE
//   `_event_streams` (discretionary_features.py:1829), `_ledger_sum` (:1128),
//   `_peak_count` (:1258) and `_slope` (:1267) are not families: they emit no
//   names.  They are called BY families — `_event_micro_map` and
//   `_test_maturity_map` share `_event_streams`, `_level_values` and
//   `_price_shape_values` share `_ledger_sum` — so porting them once and
//   letting each family call the same kernel is the only way the ported
//   families cannot drift apart from each other.
//
// REDUCTION DELEGATION LAW (qrdisc_np_kernels.hpp:4-7, applied here)
//   A float64 reduction whose numpy answer this port cannot PROVE bit-for-bit
//   is not reimplemented: the values are wrapped in a borrowed numpy array and
//   numpy's own reduction runs on them.  That is bit-identical by
//   construction, and it is the only honest option for two of them:
//     * `np.dot` on float64 goes to BLAS ddot, whose accumulation order this
//       port cannot reproduce — measured 151 mismatches over 204 lengths
//       against every scalar order tried (scratchpad spike, 2026-08-21).
//     * `.mean()` is delegated for the same reason its accumulator is numpy's
//       own; it is called a handful of times per row, so the call costs
//       nothing worth defending.
//   `.sum()` is the exception that was worth chasing: the second spike
//   (scratchpad/spike_pairwise2.py) established that numpy's float64 sum is
//   pairwise WITHIN one 8192-element buffer and sequential ACROSS buffers, and
//   that model matched numpy at every length and alignment tried, including
//   the seven lengths where the pairwise-only model is wrong.  It is native
//   here because `_trade_slice_map` sums once PER SIGN RUN
//   (discretionary_features.py:1614-1615), which a delegated reduction would
//   make slower than the oracle it replaces.
//   Everything integer-exact (searchsorted, int64 sums, max, run lengths, the
//   peak-count window) stays native, and so do median/quantile, which
//   qrdisc_np_kernels.cpp already proves against numpy 2.1.2.
#ifndef QR_ENTRY_V2_QRDISC_KERNELS_EVENTS_HPP
#define QR_ENTRY_V2_QRDISC_KERNELS_EVENTS_HPP

#include <cstdint>
#include <vector>

#include "qr_entry_v2/qrdisc_plane_state.hpp"

// --- delegated numpy reductions -------------------------------------------
// Each returns false with a Python error set; `count` may be 0 only where the
// oracle also calls numpy on an empty array (it never does for mean/dot).

// Imports numpy's module object into this translation unit's global, ONCE, from
// PyInit_qr_disc_native.  The reductions below borrow it and never import on
// the row path (R6 F17).  False leaves the Python error set.
bool qrdisc_import_numpy_module();

bool qrdisc_np_mean_i64(const std::int64_t* data, std::int64_t count,
                        double* out);
bool qrdisc_np_mean_f64(const double* data, std::int64_t count, double* out);
bool qrdisc_np_sum_f64(const double* data, std::int64_t count, double* out);
bool qrdisc_np_dot_f64(const double* left, const double* right,
                       std::int64_t count, double* out);

// --- _event_streams (discretionary_features.py:1829) -----------------------

// One of the four streams.  `first`/`second` carry the stream's own columns in
// the oracle's own order: attack/lift have only `size`; reload has
// (latency, size); pull has (lifetime, size).
struct QrdiscEventStream {
  std::vector<std::int64_t> ts;
  std::vector<std::int64_t> first;
  std::vector<std::int64_t> second;
};

struct QrdiscEventStreams {
  QrdiscEventStream attack;
  QrdiscEventStream lift;
  QrdiscEventStream reload;
  QrdiscEventStream pull;
};

bool qrdisc_event_streams(QrdiscPlaneObject* plane, std::int64_t center_tick,
                          std::int64_t radius, std::int64_t left_ns,
                          std::int64_t right_ns, std::int64_t side,
                          QrdiscEventStreams* out);

// --- _peak_count (discretionary_features.py:1258) --------------------------
std::int64_t qrdisc_peak_count(const std::int64_t* timestamps,
                               std::int64_t count, std::int64_t width_ns);

// --- _slope (discretionary_features.py:1267) -------------------------------
bool qrdisc_slope(const double* values, std::int64_t count, double* out);

// --- _ledger_sum (discretionary_features.py:1128) --------------------------
struct QrdiscLedgerSum {
  std::vector<std::int64_t> totals;  // one entry per _LEDGER_METRICS name
  std::int64_t buy_bursts;
  std::int64_t sell_bursts;
  std::int64_t last_buy;
  std::int64_t last_sell;
  std::int64_t max_buy;
  std::int64_t max_sell;
};

bool qrdisc_ledger_sum(QrdiscPlaneObject* plane, std::int64_t center_tick,
                       std::int64_t radius, std::int64_t left_sec,
                       std::int64_t right_sec, QrdiscLedgerSum* out);

// One ragged ledger field as the marshaller laid it out
// (qrdisc_state_marshal.py:92-112): `values[offsets[i] .. offsets[i+1])` is the
// group for the i-th entry of `ledger__ticks`.  `columns` is 1 for a vector
// field and the second axis for the 2-D `cumulative` matrix.
struct QrdiscRaggedField {
  const std::int64_t* values;
  const std::int64_t* offsets;
  std::int64_t columns;
};

bool qrdisc_ledger_field(QrdiscPlaneObject* plane, const char* field,
                         QrdiscRaggedField* out);

// Index of `tick` inside `ledger__ticks` into `*slot`, or -1 there when the
// tick has no ledger — the `if ledger is None: continue` branch of both kernels
// above.  Returns FALSE only when the lookup itself failed (a missing or
// mistyped `ledger__ticks` buffer), with that error left set: absence of a tick
// and absence of the ledger are different facts and must not both read as -1.
bool qrdisc_ledger_slot(QrdiscPlaneObject* plane, std::int64_t tick,
                        std::int64_t* slot);

#endif  // QR_ENTRY_V2_QRDISC_KERNELS_EVENTS_HPP
