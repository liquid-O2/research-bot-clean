// Shared value types for the qrdisc port of the discretionary per-row query
// path (engine/entry_v2/discretionary_features.py, frozen oracle).
//
// WHY these are plain spans and not owning containers: every array the kernels
// read is borrowed from a numpy buffer that the CPython binding keeps alive for
// the lifetime of the marshalled plane (qrdisc_pymodule.cpp).  Copying would
// both cost the port its Amdahl headroom and open a second source of truth for
// bytes D-017 requires to stay identical to the store's.
#ifndef QR_ENTRY_V2_QRDISC_TYPES_HPP
#define QR_ENTRY_V2_QRDISC_TYPES_HPP

#include <cstdint>
#include <stdexcept>
#include <string>

// Every kernel refusal carries the offending value AND the expected shape:
// a bare "invalid input" costs a debugging round to learn what the check knew.
class QrdiscKernelError : public std::runtime_error {
 public:
  explicit QrdiscKernelError(const std::string& message)
      : std::runtime_error(message) {}
};

struct QrdiscI64Span {
  const std::int64_t* data;
  std::int64_t count;
};

struct QrdiscF64Span {
  const double* data;
  std::int64_t count;
};

#endif  // QR_ENTRY_V2_QRDISC_TYPES_HPP
