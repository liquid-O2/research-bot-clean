// Kernel lockdown for the qrdisc port (stage 2).
//
// EVIDENCE PROVENANCE.  Every expected number below was produced by running
// numpy 2.1.2 on this box and hand-transcribed here as an IEEE-754 bit pattern.
// Nothing in this file is computed with the kernels under test, and no fixture
// is derived from the same expression the kernel implements — a mirror
// assertion would pass whether the port is right or wrong.
//
// The double comparisons are BIT comparisons, not tolerances: D-017 makes the
// stored float32 bytes the contract, and a last-ulp float64 difference is
// exactly what survives the cast often enough to matter.
#include <gtest/gtest.h>

#include <cstdint>
#include <cstring>
#include <vector>

#include "qr_entry_v2/qrdisc_np_kernels.hpp"

namespace {

// Test-local bit view.  Deliberately not a kernel helper: the assertion must
// not share code with the thing it judges.
std::uint64_t bits_of(double value) {
  std::uint64_t out = 0;
  std::memcpy(&out, &value, sizeof(out));
  return out;
}

double double_of(std::uint64_t pattern) {
  double out = 0.0;
  std::memcpy(&out, &pattern, sizeof(out));
  return out;
}

#define EXPECT_BITS(expected_pattern, actual)                       \
  EXPECT_EQ(static_cast<std::uint64_t>(expected_pattern),           \
            bits_of(actual))                                        \
      << "expected " << double_of(expected_pattern) << " got " << (actual)

// np.asarray([10, 20, 20, 20, 35, 40], np.int64)
const std::int64_t kHaystack[] = {10, 20, 20, 20, 35, 40};
QrdiscI64Span haystack() { return QrdiscI64Span{kHaystack, 6}; }

}  // namespace

// ---------------------------------------------------------------------------
// searchsorted family
// Transcribed from: np.searchsorted(hay, p, side=...) for p in
// (5, 10, 20, 21, 40, 41) -> left (0,0,1,4,5,6) right (0,1,4,4,6,6).
// ---------------------------------------------------------------------------
TEST(QrdiscSearchsorted, LeftMatchesNumpy) {
  EXPECT_EQ(0, qrdisc_searchsorted_left_i64(haystack(), 5));
  EXPECT_EQ(0, qrdisc_searchsorted_left_i64(haystack(), 10));
  EXPECT_EQ(1, qrdisc_searchsorted_left_i64(haystack(), 20));
  EXPECT_EQ(4, qrdisc_searchsorted_left_i64(haystack(), 21));
  EXPECT_EQ(5, qrdisc_searchsorted_left_i64(haystack(), 40));
  EXPECT_EQ(6, qrdisc_searchsorted_left_i64(haystack(), 41));
}

TEST(QrdiscSearchsorted, RightMatchesNumpy) {
  EXPECT_EQ(0, qrdisc_searchsorted_right_i64(haystack(), 5));
  EXPECT_EQ(1, qrdisc_searchsorted_right_i64(haystack(), 10));
  EXPECT_EQ(4, qrdisc_searchsorted_right_i64(haystack(), 20));
  EXPECT_EQ(4, qrdisc_searchsorted_right_i64(haystack(), 21));
  EXPECT_EQ(6, qrdisc_searchsorted_right_i64(haystack(), 40));
  EXPECT_EQ(6, qrdisc_searchsorted_right_i64(haystack(), 41));
}

TEST(QrdiscSearchsorted, EmptyHaystackIsZeroLikeNumpy) {
  EXPECT_EQ(0, qrdisc_searchsorted_left_i64(QrdiscI64Span{nullptr, 0}, 7));
  EXPECT_EQ(0, qrdisc_searchsorted_right_i64(QrdiscI64Span{nullptr, 0}, 7));
}

// ---------------------------------------------------------------------------
// integer cumulative ops
// Transcribed from: np.cumsum(np.asarray([3,-1,0,7,2], np.int64)) ->
// [3, 2, 2, 9, 11]; np.r_[np.int64(0), ...] -> [0, 3, 2, 2, 9, 11].
// ---------------------------------------------------------------------------
TEST(QrdiscCumsum, MatchesNumpy) {
  const std::int64_t source[] = {3, -1, 0, 7, 2};
  std::int64_t out[5] = {0};
  qrdisc_cumsum_i64(QrdiscI64Span{source, 5}, out);
  const std::int64_t expected[] = {3, 2, 2, 9, 11};
  for (int index = 0; index < 5; ++index) {
    EXPECT_EQ(expected[index], out[index]) << "at index " << index;
  }
}

TEST(QrdiscCumsum, PrependZeroMatchesNumpy) {
  const std::int64_t source[] = {3, -1, 0, 7, 2};
  std::int64_t out[6] = {0};
  qrdisc_cumsum_prepend_zero_i64(QrdiscI64Span{source, 5}, out);
  const std::int64_t expected[] = {0, 3, 2, 2, 9, 11};
  for (int index = 0; index < 6; ++index) {
    EXPECT_EQ(expected[index], out[index]) << "at index " << index;
  }
}

// numpy's int64 accumulator wraps on overflow.  Transcribed from
// np.cumsum(np.asarray([2**62, 2**62, -2**62], np.int64)) ->
// [4611686018427387904, -9223372036854775808, 4611686018427387904].
TEST(QrdiscCumsum, OverflowWrapsLikeNumpy) {
  const std::int64_t source[] = {4611686018427387904LL, 4611686018427387904LL,
                                 -4611686018427387904LL};
  std::int64_t out[3] = {0};
  qrdisc_cumsum_i64(QrdiscI64Span{source, 3}, out);
  EXPECT_EQ(4611686018427387904LL, out[0]);
  EXPECT_EQ(INT64_MIN, out[1]);
  EXPECT_EQ(4611686018427387904LL, out[2]);
}

// ---------------------------------------------------------------------------
// quantile / median value selection
// Transcribed from np.quantile(values, q) on numpy 2.1.2.
// ---------------------------------------------------------------------------
TEST(QrdiscQuantile, SingleElementIsThatElement) {
  std::vector<double> values{4.5};
  EXPECT_BITS(0x4012000000000000ULL,
              qrdisc_quantile_linear_f64(values.data(), 1, 0.10));
  values = {4.5};
  EXPECT_BITS(0x4012000000000000ULL,
              qrdisc_quantile_linear_f64(values.data(), 1, 0.90));
}

TEST(QrdiscQuantile, PairMatchesNumpy) {
  const std::vector<double> source{1.0, 2.0};
  std::vector<double> values = source;
  EXPECT_BITS(0x3ff199999999999aULL,  // 1.1
              qrdisc_quantile_linear_f64(values.data(), 2, 0.10));
  values = source;
  EXPECT_BITS(0x3ffe666666666666ULL,  // 1.9
              qrdisc_quantile_linear_f64(values.data(), 2, 0.90));
  values = source;
  EXPECT_BITS(0x3ff8000000000000ULL,  // 1.5
              qrdisc_quantile_linear_f64(values.data(), 2, 0.50));
}

// Unsorted input, five elements: np.quantile([7,1,3,9,2], .10) == 1.4,
// (.90) == 8.2, (.50) == 3.0, (.25) == 2.0.
TEST(QrdiscQuantile, UnsortedFiveMatchesNumpy) {
  const std::vector<double> source{7.0, 1.0, 3.0, 9.0, 2.0};
  std::vector<double> values = source;
  EXPECT_BITS(0x3ff6666666666666ULL,
              qrdisc_quantile_linear_f64(values.data(), 5, 0.10));
  values = source;
  EXPECT_BITS(0x4020666666666666ULL,
              qrdisc_quantile_linear_f64(values.data(), 5, 0.90));
  values = source;
  EXPECT_BITS(0x4008000000000000ULL,
              qrdisc_quantile_linear_f64(values.data(), 5, 0.50));
  values = source;
  EXPECT_BITS(0x4000000000000000ULL,
              qrdisc_quantile_linear_f64(values.data(), 5, 0.25));
}

// The shape the tape maps actually pass: seven inter-event gaps in ms.
// np.quantile(gaps, .10) == 0.35000000000000003,
// np.quantile(gaps, .90) == 59.80000000000002.
TEST(QrdiscQuantile, GapMillisecondsMatchNumpy) {
  const std::vector<double> source{0.125, 12.5, 3.25, 88.0, 5.5, 0.5, 41.0};
  std::vector<double> values = source;
  EXPECT_BITS(0x3fd6666666666667ULL,
              qrdisc_quantile_linear_f64(values.data(), 7, 0.10));
  values = source;
  EXPECT_BITS(0x404de66666666669ULL,
              qrdisc_quantile_linear_f64(values.data(), 7, 0.90));
  values = source;
  EXPECT_BITS(0x3ffe000000000000ULL,  // 1.875, gamma exactly 0.5
              qrdisc_quantile_linear_f64(values.data(), 7, 0.25));
}

TEST(QrdiscQuantile, NegativeValuesMatchNumpy) {
  const std::vector<double> source{-3.5, -0.25, -100.0, 2.0};
  std::vector<double> values = source;
  EXPECT_BITS(0xc051c33333333333ULL,  // -71.05
              qrdisc_quantile_linear_f64(values.data(), 4, 0.10));
  values = source;
  EXPECT_BITS(0x3ff5333333333335ULL,  // 1.3250000000000004
              qrdisc_quantile_linear_f64(values.data(), 4, 0.90));
  values = source;
  EXPECT_BITS(0xc03ba00000000000ULL,  // -27.625
              qrdisc_quantile_linear_f64(values.data(), 4, 0.25));
}

// THE branch fixture.  numpy's _lerp switches formula at t >= 0.5:
//   t <  0.5 -> a + (b - a) * t
//   t >= 0.5 -> b - (b - a) * (1 - t)
// Each case below is a two-element quantile whose gamma is >= 0.5 and where the
// two formulas disagree in the last ulp.  A single-formula implementation
// returns the `naive` pattern in the comment and FAILS here; that is the whole
// point of the fixture.
TEST(QrdiscQuantile, TwoBranchLerpMatchesNumpy) {
  {  // naive a+(b-a)*t would give 0x40623467cf367f7a
    std::vector<double> values{double_of(0xc069d4731a734918ULL),
                               double_of(0x40634696b5cc54d0ULL)};
    EXPECT_BITS(0x40623467cf367f7bULL,
                qrdisc_quantile_linear_f64(values.data(), 2,
                                           double_of(0x3fef3d7b58e26346ULL)));
  }
  {  // naive a+(b-a)*t would give 0x40592336dd2d2fc0
    std::vector<double> values{double_of(0xc083f460bf71e37bULL),
                               double_of(0x4083c20591240162ULL)};
    EXPECT_BITS(0x40592336dd2d2fc8ULL,
                qrdisc_quantile_linear_f64(values.data(), 2,
                                           double_of(0x3fe29c77f248e9cdULL)));
  }
  {  // naive a+(b-a)*t would give 0x40426152948f00f0
    std::vector<double> values{double_of(0xc06fe68ea8f48e30ULL),
                               double_of(0x40715d3b232f7becULL)};
    EXPECT_BITS(0x40426152948f00ecULL,
                qrdisc_quantile_linear_f64(values.data(), 2,
                                           double_of(0x3fe1871f66d93390ULL)));
  }
}

TEST(QrdiscQuantile, EmptyIsRefusedWithTheCount) {
  double* nothing = nullptr;
  EXPECT_THROW(qrdisc_quantile_linear_f64(nothing, 0, 0.5), QrdiscKernelError);
}

// np.median: [4.5] -> 4.5, [1,2] -> 1.5, [7,1,3,9,2] -> 3.0,
// [0.125,12.5,3.25,88,5.5,0.5,41] -> 5.5, [-3.5,-0.25,-100,2] -> -1.875.
TEST(QrdiscMedian, Float64MatchesNumpy) {
  std::vector<double> one{4.5};
  EXPECT_BITS(0x4012000000000000ULL, qrdisc_median_f64(one.data(), 1));
  std::vector<double> two{1.0, 2.0};
  EXPECT_BITS(0x3ff8000000000000ULL, qrdisc_median_f64(two.data(), 2));
  std::vector<double> five{7.0, 1.0, 3.0, 9.0, 2.0};
  EXPECT_BITS(0x4008000000000000ULL, qrdisc_median_f64(five.data(), 5));
  std::vector<double> seven{0.125, 12.5, 3.25, 88.0, 5.5, 0.5, 41.0};
  EXPECT_BITS(0x4016000000000000ULL, qrdisc_median_f64(seven.data(), 7));
  std::vector<double> four{-3.5, -0.25, -100.0, 2.0};
  EXPECT_BITS(0xbffe000000000000ULL, qrdisc_median_f64(four.data(), 4));
}

// np.median over int64: [5,1,9] -> 5.0, [5,1,9,2] -> 3.5, [-7] -> -7.0.
// The 2**53 pair is the discriminator for the accumulation dtype: numpy's mean
// converts to float64 BEFORE adding, so [2**53+1, 2**53+3] -> 9007199254740994.0
// (0x4340000000000001).  Summing in int64 and dividing would give the same
// value here only by luck of the halving; the bit pattern is asserted anyway.
TEST(QrdiscMedian, Int64MatchesNumpy) {
  std::vector<std::int64_t> odd{5, 1, 9};
  EXPECT_BITS(0x4014000000000000ULL, qrdisc_median_i64(odd.data(), 3));
  std::vector<std::int64_t> even{5, 1, 9, 2};
  EXPECT_BITS(0x400c000000000000ULL, qrdisc_median_i64(even.data(), 4));
  std::vector<std::int64_t> one{-7};
  EXPECT_BITS(0xc01c000000000000ULL, qrdisc_median_i64(one.data(), 1));
  std::vector<std::int64_t> big{9007199254740993LL, 9007199254740995LL};
  EXPECT_BITS(0x4340000000000001ULL, qrdisc_median_i64(big.data(), 2));
}

TEST(QrdiscMedian, EmptyIsRefusedWithTheCount) {
  double* nothing = nullptr;
  EXPECT_THROW(qrdisc_median_f64(nothing, 0), QrdiscKernelError);
  std::int64_t* no_ints = nullptr;
  EXPECT_THROW(qrdisc_median_i64(no_ints, 0), QrdiscKernelError);
}

// ---------------------------------------------------------------------------
// elementwise float64 with transcribed expression order
// Transcribed from Python: float(side * (current_mid2 - base_mid2) * factor)
// with factor = 0.5e-9 * multiplier (discretionary_features.py:76, 504).
// ---------------------------------------------------------------------------
TEST(QrdiscAlignedUsd, MatchesPythonExpressionOrder) {
  const double factor_1000 = double_of(0x3ea0c6f7a0b5ed8eULL);  // 0.5e-9*1000
  EXPECT_BITS(0x3f02599ed7c6fbd3ULL,  // 3.5000000000000004e-05
              qrdisc_aligned_usd(1, 20050, 19980, factor_1000));
  EXPECT_BITS(0xbf02599ed7c6fbd3ULL,
              qrdisc_aligned_usd(-1, 20050, 19980, factor_1000));
  const double factor_5 = 2.5e-09;
  EXPECT_BITS(0x3e94cdc26b1f07d8ULL,  // 3.1e-07
              qrdisc_aligned_usd(1, 4123457, 4123333, factor_5));
  const double factor_50 = double_of(0x3e5ad7f29abcaf49ULL);  // 0.5e-9*50
  EXPECT_BITS(0x3e90c6f7a0b5ed8eULL,  // 2.5000000000000004e-07
              qrdisc_aligned_usd(-1, -3, 7, factor_50));
}

// A mid2 difference above 2^53 is only exact if the subtraction happens in
// int64.  Transcribed from Python:
//   float(1 * ((2**53 + 3) - 2) * 2.5e-09) == 22517998.13685248
// In double the minuend rounds to 2**53 + 4 first, so a double-subtraction port
// lands one ulp of the difference away.
TEST(QrdiscAlignedUsd, LargeMid2StaysExactInInt64) {
  EXPECT_BITS(0x4175798ee2308c3aULL,
              qrdisc_aligned_usd(1, 9007199254740995LL, 2LL, 2.5e-09));
}

// Transcribed from Python: (short + 1.0) / (long + 1.0)
TEST(QrdiscHorizonRatio, MatchesPythonExpressionOrder) {
  EXPECT_BITS(0x3ff0000000000000ULL, qrdisc_horizon_ratio(0.0, 0.0));
  EXPECT_BITS(0x3fe0000000000000ULL, qrdisc_horizon_ratio(3.0, 7.0));
  EXPECT_BITS(0x3feb13b13b13b13bULL,
              qrdisc_horizon_ratio(0.1, double_of(0x3fd3333333333334ULL)));
  EXPECT_BITS(0x3e112e0be826d695ULL, qrdisc_horizon_ratio(1e-09, 1e9));
}
