// Exact-arithmetic kernels for the qrdisc port.
//
// SCOPE LAW (stage-1 delegation law).  Only operations whose numpy result this
// code can reproduce bit-for-bit live here.  Anything whose numpy answer
// depends on a reduction topology, a BLAS call or a pairwise summation order
// this file cannot prove is DELEGATED back to numpy's own C ufuncs through the
// binding's callback table instead — bit-identical by construction.
//
// Every expected value in tests/test_qrdisc_kernels.cpp was produced by RUNNING
// numpy 2.1.2 on this box and hand-transcribed as a bit pattern.  No expected
// value is ever computed by the code under test (mirror-assertion ban).
#ifndef QR_ENTRY_V2_QRDISC_NP_KERNELS_HPP
#define QR_ENTRY_V2_QRDISC_NP_KERNELS_HPP

#include <cstdint>

#include "qr_entry_v2/qrdisc_types.hpp"

// np.searchsorted(haystack, needle, side="left"): first index i with
// haystack[i] >= needle.  haystack must be non-decreasing (the oracle only ever
// searches its own sorted ledgers); an unsorted haystack is not diagnosed, in
// numpy or here.
std::int64_t qrdisc_searchsorted_left_i64(QrdiscI64Span haystack,
                                          std::int64_t needle);

// np.searchsorted(haystack, needle, side="right"): first index i with
// haystack[i] > needle.
std::int64_t qrdisc_searchsorted_right_i64(QrdiscI64Span haystack,
                                           std::int64_t needle);

// NO PRODUCTION CALLER YET (R6 F21).  Both cumsum declarations are staged for
// the two families still delegated to the oracle — `_level_values` and
// `_price_shape_values` (discretionary_features.py:1161, :1208) — which rebuild
// these prefixes per window.  Until one of them is ported, the only thing that
// exercises them is tests/test_qrdisc_kernels.cpp.
//
// np.cumsum(source, dtype=np.int64) into out[0 .. count-1].  Overflow WRAPS,
// exactly as numpy's int64 accumulator does; C++ signed overflow is UB, so the
// accumulation runs unsigned and is converted back.
void qrdisc_cumsum_i64(QrdiscI64Span source, std::int64_t* out);

// np.r_[np.int64(0), np.cumsum(source, dtype=np.int64)] into out[0 .. count].
// This exact shape is what _TickLedger.cumulative and _trade_volume_prefix
// carry (discretionary_features.py:626-627, 774-779).
void qrdisc_cumsum_prepend_zero_i64(QrdiscI64Span source, std::int64_t* out);

// np.quantile(values, q) with numpy's default method="linear".
//
// `scratch` is REORDERED in place (numpy's own np.quantile partitions a copy of
// its input).  The caller owns the buffer.  count >= 1 and 0 <= q <= 1 are
// contract, not input: the oracle's call sites all guard emptiness with
// `if len(x) else 0.0` and pass literal quantiles.
double qrdisc_quantile_linear_f64(double* scratch, std::int64_t count, double q);

// np.median(values) for a float64 array: odd count selects the middle order
// statistic, even count returns (lower + upper) / 2.0 in double.
double qrdisc_median_f64(double* scratch, std::int64_t count);

// np.median(values) for an int64 array.  numpy's mean over an integer array
// accumulates in float64, so both order statistics are converted to double
// BEFORE the addition; summing in int64 first would differ above 2^53.
double qrdisc_median_i64(std::int64_t* scratch, std::int64_t count);

// The aligned-price expression transcribed from discretionary_features.py:
// 213-218 — `side * (current_mid2 - base_mid2) * self.factor`.  Python evaluates
// the parenthesised difference and the `side *` product in EXACT integer
// arithmetic and only then converts to double; computing the difference in
// double would round twice for mid2 values above 2^53.
double qrdisc_aligned_usd(std::int64_t side, std::int64_t current_mid2,
                          std::int64_t base_mid2, double factor);

// The horizon-ratio expression transcribed from discretionary_features.py:2505
// — `(short + 1.0) / (long + 1.0)`.  Both addends round before the divide.
double qrdisc_horizon_ratio(double short_value, double long_value);

#endif  // QR_ENTRY_V2_QRDISC_NP_KERNELS_HPP
