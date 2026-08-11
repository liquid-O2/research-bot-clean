#include "qr_core/refusal.hpp"

#include <array>
#include <cstddef>
#include <cstdio>
#include <cstdlib>
#include <string>

namespace qr {
namespace {

constexpr std::array<const char*, kRefusalCodeCount> kNames = {
    "INVALID_CORPUS_ROOT",
    "REGISTRY_DIGEST_MISMATCH",
    "UNKNOWN_SESSION",
    "SOURCE_AUTHENTICATION_FAILED",
    "IO",
    "SCHEMA_MISMATCH",
    "DECODE_FAILED",
    "OUT_OF_ORDER",
    "CONTENT_MISMATCH",
    "ARITHMETIC_OVERFLOW",
    "MALFORMED_CIVIL_DATE",
    "WRONG_CIVIL_DAY",
    "INVALID_DIRECT_INSTANT_TIMEZONE",
    "OUTSIDE_RTH",
    "CLOCK_VIOLATION",
    "DAY_OUTSIDE_CALENDAR",
    "MODALITY_ABSENT",
    "ORDINAL_OUTSIDE_SCOPE",
    "REGISTRY_MALFORMED",
    "CONFIG",
    "COLUMN_FORBIDDEN",
};

}  // namespace

const char* refusal_code_name(RefusalCode code) noexcept {
  const auto index = static_cast<std::size_t>(code);
  if (index >= kRefusalCodeCount) {
    return "UNKNOWN_REFUSAL";
  }
  return kNames[index];
}

std::string Refusal::message() const {
  std::string out = refusal_code_name(code_);
  out += " at ";
  out += (site_ != nullptr) ? site_ : "<unnamed site>";
  if (detail_ != nullptr && detail_[0] != '\0') {
    out += ": ";
    out += detail_;
  }
  if (context_ != 0) {
    out += " [context=";
    out += std::to_string(context_);
    out += "]";
  }
  return out;
}

namespace detail {

void fail_fast(const char* what) noexcept {
  std::fputs("qr fail-closed: ", stderr);
  std::fputs((what != nullptr) ? what : "<unnamed>", stderr);
  std::fputc('\n', stderr);
  std::fflush(stderr);
  std::abort();
}

}  // namespace detail
}  // namespace qr
