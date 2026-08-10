#include "qr_core/validity.hpp"

#include <array>
#include <cstddef>

namespace qr {
namespace {

constexpr std::array<const char*, kValidityCount> kNames = {
    "VALID",     "MISSING",   "EQUAL_TIME_UNORDERED", "ATTACHMENT_FUTURE",
    "WRONG_CIVIL_DAY",        "STALE_DIAG",           "LOCKED",
    "CROSSED",   "ONE_SIDED", "NONFINITE",            "NONPOSITIVE",
    "CONDITION_INELIGIBLE",   "CLOCK_UNAVAILABLE",    "MODALITY_ABSENT",
};

}  // namespace

const char* validity_name(Validity v) noexcept {
  const auto index = static_cast<std::size_t>(v);
  if (index >= kValidityCount) {
    // Guard, not assert: an out-of-domain state is named, never dereferenced.
    return "UNKNOWN_VALIDITY";
  }
  return kNames[index];
}

}  // namespace qr
