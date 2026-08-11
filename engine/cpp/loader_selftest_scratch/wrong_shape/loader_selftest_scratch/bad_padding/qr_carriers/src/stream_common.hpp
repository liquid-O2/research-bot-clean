// qr_carriers/src/stream_common.hpp — helpers shared by the three modality
// constructors. Internal to the module: it holds no law of its own, only the
// two or three shapes that would otherwise be spelled three times and could
// then drift apart.
#ifndef QR_CARRIERS_SRC_STREAM_COMMON_HPP
#define QR_CARRIERS_SRC_STREAM_COMMON_HPP

#include <cstdint>
#include <optional>

#include "qr_carriers/channels.hpp"
#include "qr_carriers/transforms.hpp"
#include "qr_core/validity.hpp"

namespace qr::carriers::detail_streams {

/// Applies an orientation factor to an already-transformed channel value. A
/// masked value stays masked at exactly 0.0 — orientation never resurrects a
/// missing channel, and -0.0 never appears (multiplying the stored 0.0 by -1
/// would produce it, and -0.0 != 0.0 bitwise, which two-run byte identity
/// would notice).
[[nodiscard]] inline Typed<double> oriented(Typed<double> value, double factor) noexcept {
  if (value.v != Validity::VALID) {
    return masked(value.v);
  }
  if (value.value == 0.0) {
    return present(0.0);
  }
  return present(value.value * factor);
}

/// The three-way sign of `left - right`, on exact integers.
[[nodiscard]] inline int sign_of_difference(std::int64_t left, std::int64_t right) noexcept {
  if (left > right) {
    return 1;
  }
  if (left < right) {
    return -1;
  }
  return 0;
}

/// An optional integer cell: the value when the column was non-null.
[[nodiscard]] inline std::optional<std::int64_t> cell(bool is_null, std::int64_t value) noexcept {
  if (is_null) {
    return std::nullopt;
  }
  return value;
}

/// Worst-wins over two dependency verdicts, spelled once so no constructor
/// invents an ordering of its own.
[[nodiscard]] inline Validity both(Validity left, Validity right) noexcept {
  return combine(left, right);
}

}  // namespace qr::carriers::detail_streams

#endif  // QR_CARRIERS_SRC_STREAM_COMMON_HPP
