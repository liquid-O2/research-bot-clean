// qr_core/checked.hpp - checked integer arithmetic that refuses on overflow.
//
// SPEC (design/DESIGN_SUBSTRATE.md APPENDIX C1 + section 6):
//   "checked arithmetic via __builtin_*_overflow returning Refusal"
//   "`Expected<int64_t,Refusal> checked_add(...)` via __builtin_*_overflow"
//
// LAW: an overflowing operation returns RefusalCode::ARITHMETIC_OVERFLOW. It
// never wraps, never traps, and never substitutes a boundary value for the
// true result. The ci/check_banned_constructs.sh gate enforces the absence of
// range-limiting helpers in this module.
#ifndef QR_CORE_CHECKED_HPP
#define QR_CORE_CHECKED_HPP

#include <cstdint>

#include "qr_core/refusal.hpp"

namespace qr {

/// a + b, or ARITHMETIC_OVERFLOW.
[[nodiscard]] inline Expected<std::int64_t, Refusal> checked_add(std::int64_t a,
                                                                 std::int64_t b) noexcept {
  std::int64_t out = 0;
  if (__builtin_add_overflow(a, b, &out)) {
    return Expected<std::int64_t, Refusal>::refuse(
        Refusal(RefusalCode::ARITHMETIC_OVERFLOW, "qr_core::checked_add", "int64 addition overflowed", b));
  }
  return out;
}

/// a - b, or ARITHMETIC_OVERFLOW.
[[nodiscard]] inline Expected<std::int64_t, Refusal> checked_sub(std::int64_t a,
                                                                 std::int64_t b) noexcept {
  std::int64_t out = 0;
  if (__builtin_sub_overflow(a, b, &out)) {
    return Expected<std::int64_t, Refusal>::refuse(
        Refusal(RefusalCode::ARITHMETIC_OVERFLOW, "qr_core::checked_sub", "int64 subtraction overflowed", b));
  }
  return out;
}

/// a * b, or ARITHMETIC_OVERFLOW.
[[nodiscard]] inline Expected<std::int64_t, Refusal> checked_mul(std::int64_t a,
                                                                 std::int64_t b) noexcept {
  std::int64_t out = 0;
  if (__builtin_mul_overflow(a, b, &out)) {
    return Expected<std::int64_t, Refusal>::refuse(
        Refusal(RefusalCode::ARITHMETIC_OVERFLOW, "qr_core::checked_mul", "int64 multiplication overflowed", b));
  }
  return out;
}

}  // namespace qr

#endif  // QR_CORE_CHECKED_HPP
