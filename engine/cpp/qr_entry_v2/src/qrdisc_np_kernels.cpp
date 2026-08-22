// Exact-arithmetic kernels for the qrdisc port.  See the header for the scope
// law; see tests/test_qrdisc_kernels.cpp for the numpy-derived fixtures that
// pin every line below.
#include "qr_entry_v2/qrdisc_np_kernels.hpp"

#include <algorithm>
#include <cmath>
#include <string>

namespace {

std::int64_t qrdisc_wrap_to_int64(std::uint64_t value) {
  // numpy's int64 accumulator wraps; C++ signed overflow is UB, so the sum is
  // carried unsigned and converted here.  The conversion is implementation
  // defined before C++20 and two's-complement-defined from C++20 on, which is
  // the standard this tree compiles against (engine/cpp/CMakeLists.txt:18).
  return static_cast<std::int64_t>(value);
}

void qrdisc_require_non_empty(std::int64_t count, const char* kernel) {
  if (count >= 1) return;
  throw QrdiscKernelError(
      std::string(kernel) + ": count=" + std::to_string(count) +
      ", expected count>=1; the oracle guards emptiness at the call site "
      "(`if len(x) else 0.0`) and never asks for an empty reduction");
}

// numpy's _lerp (numpy/lib/_function_base_impl.py:4606-4627): one formula below
// t == 0.5 and a different one at or above it.  The two disagree in the last
// ulp, which is why this is a named function and not an inlined expression.
double qrdisc_numpy_lerp(double lower, double upper, double weight) {
  const double difference = upper - lower;
  if (weight >= 0.5) return upper - difference * (1.0 - weight);
  return lower + difference * weight;
}

}  // namespace

std::int64_t qrdisc_searchsorted_left_i64(QrdiscI64Span haystack,
                                          std::int64_t needle) {
  std::int64_t low = 0;
  std::int64_t high = haystack.count;
  while (low < high) {
    const std::int64_t middle = low + (high - low) / 2;
    if (haystack.data[middle] < needle) {
      low = middle + 1;
    } else {
      high = middle;
    }
  }
  return low;
}

std::int64_t qrdisc_searchsorted_right_i64(QrdiscI64Span haystack,
                                           std::int64_t needle) {
  std::int64_t low = 0;
  std::int64_t high = haystack.count;
  while (low < high) {
    const std::int64_t middle = low + (high - low) / 2;
    if (haystack.data[middle] <= needle) {
      low = middle + 1;
    } else {
      high = middle;
    }
  }
  return low;
}

void qrdisc_cumsum_i64(QrdiscI64Span source, std::int64_t* out) {
  std::uint64_t running = 0;
  for (std::int64_t index = 0; index < source.count; ++index) {
    running += static_cast<std::uint64_t>(source.data[index]);
    out[index] = qrdisc_wrap_to_int64(running);
  }
}

void qrdisc_cumsum_prepend_zero_i64(QrdiscI64Span source, std::int64_t* out) {
  out[0] = 0;
  std::uint64_t running = 0;
  for (std::int64_t index = 0; index < source.count; ++index) {
    running += static_cast<std::uint64_t>(source.data[index]);
    out[index + 1] = qrdisc_wrap_to_int64(running);
  }
}

double qrdisc_quantile_linear_f64(double* scratch, std::int64_t count,
                                  double quantile) {
  qrdisc_require_non_empty(count, "qrdisc_quantile_linear_f64");
  // numpy partitions at the two neighbouring indexes; a full sort puts the same
  // order statistics at those positions.  NaN is out of contract: the oracle
  // refuses a non-finite map before any value reaches the store
  // (discretionary_features.py:2692-2693).
  std::sort(scratch, scratch + count);
  const double virtual_index =
      static_cast<double>(count - 1) * quantile;  // method="linear", alpha=beta=1
  if (virtual_index >= static_cast<double>(count - 1)) return scratch[count - 1];
  if (virtual_index < 0.0) return scratch[0];
  const double previous_index = std::floor(virtual_index);
  const std::int64_t lower = static_cast<std::int64_t>(previous_index);
  const double gamma = virtual_index - previous_index;
  return qrdisc_numpy_lerp(scratch[lower], scratch[lower + 1], gamma);
}

double qrdisc_median_f64(double* scratch, std::int64_t count) {
  qrdisc_require_non_empty(count, "qrdisc_median_f64");
  std::sort(scratch, scratch + count);
  const std::int64_t middle = count / 2;
  if (count % 2 == 1) return scratch[middle] / 1.0;
  return (scratch[middle - 1] + scratch[middle]) / 2.0;
}

double qrdisc_median_i64(std::int64_t* scratch, std::int64_t count) {
  qrdisc_require_non_empty(count, "qrdisc_median_i64");
  std::sort(scratch, scratch + count);
  const std::int64_t middle = count / 2;
  if (count % 2 == 1) return static_cast<double>(scratch[middle]) / 1.0;
  // np.mean over an integer array accumulates in float64: both order statistics
  // convert to double BEFORE the addition, which differs from an int64 sum
  // above 2**53.
  return (static_cast<double>(scratch[middle - 1]) +
          static_cast<double>(scratch[middle])) /
         2.0;
}

double qrdisc_aligned_usd(std::int64_t side, std::int64_t current_mid2,
                          std::int64_t base_mid2, double factor) {
  const std::int64_t aligned_ticks = side * (current_mid2 - base_mid2);
  return static_cast<double>(aligned_ticks) * factor;
}

double qrdisc_horizon_ratio(double short_value, double long_value) {
  return (short_value + 1.0) / (long_value + 1.0);
}
