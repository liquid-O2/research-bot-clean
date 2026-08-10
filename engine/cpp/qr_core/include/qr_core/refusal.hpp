// qr_core/refusal.hpp — the typed refusal taxonomy and the Expected carrier.
//
// SPEC: design/DESIGN_SUBSTRATE.md APPENDIX C1 —
//   "`Expected<int64_t,Refusal> checked_add(...)` via __builtin_*_overflow"
//
// The taxonomy is a port of the frozen Rust refusal set (read-only references
// /workspace/engine/crates/corpus/src/error.rs and
// /workspace/engine/crates/select_v2/src/error.rs). Every variant means the
// same thing here as there: "do not trust this data". Nothing recovers by
// substituting a boundary value — overflow is a refusal, never a substituted
// in-range number (FINAL_PLAN section 6 arithmetic law).
//
// Refusal is deliberately trivially copyable: `site` and `detail` are static
// string literals and `context` is an integer, so the success path of a
// checked-arithmetic call allocates nothing and the error path allocates
// nothing either.
#ifndef QR_CORE_REFUSAL_HPP
#define QR_CORE_REFUSAL_HPP

#include <cstdint>
#include <string>
#include <utility>
#include <variant>

namespace qr {

/// Ported refusal taxonomy. The first fifteen mirror `corpus::CorpusError`
/// one-for-one; the last four mirror the `select_v2` wall/config refusals plus
/// the two this substrate adds by name (the 125..749 scope wall and registry
/// malformation, which the Rust build expressed as a compile-time panic).
enum class RefusalCode : std::uint8_t {
  INVALID_CORPUS_ROOT = 0,
  REGISTRY_DIGEST_MISMATCH,
  UNKNOWN_SESSION,
  SOURCE_AUTHENTICATION_FAILED,
  IO,
  SCHEMA_MISMATCH,
  DECODE_FAILED,
  OUT_OF_ORDER,
  CONTENT_MISMATCH,
  ARITHMETIC_OVERFLOW,
  MALFORMED_CIVIL_DATE,
  WRONG_CIVIL_DAY,
  INVALID_DIRECT_INSTANT_TIMEZONE,
  OUTSIDE_RTH,
  CLOCK_VIOLATION,
  DAY_OUTSIDE_CALENDAR,
  MODALITY_ABSENT,
  ORDINAL_OUTSIDE_SCOPE,
  REGISTRY_MALFORMED,
  CONFIG,
};

inline constexpr std::size_t kRefusalCodeCount = 20;

/// Stable screaming-snake name of a refusal code (never a sentence).
const char* refusal_code_name(RefusalCode code) noexcept;

/// A typed refusal. `site` is a greppable static tag naming the exact code
/// site; `detail` is a static explanation; `context` carries one integer
/// (offending ordinal, row index, value) or 0 when unused.
class Refusal {
 public:
  constexpr Refusal(RefusalCode code, const char* site, const char* detail,
                    std::int64_t context = 0) noexcept
      : code_(code), site_(site), detail_(detail), context_(context) {}

  [[nodiscard]] constexpr RefusalCode code() const noexcept { return code_; }
  [[nodiscard]] constexpr const char* site() const noexcept { return site_; }
  [[nodiscard]] constexpr const char* detail() const noexcept { return detail_; }
  [[nodiscard]] constexpr std::int64_t context() const noexcept { return context_; }

  /// Human-readable one-line message. Formatting happens only when asked.
  [[nodiscard]] std::string message() const;

  friend constexpr bool operator==(const Refusal& lhs, const Refusal& rhs) noexcept {
    return lhs.code_ == rhs.code_ && lhs.context_ == rhs.context_;
  }

 private:
  RefusalCode code_;
  const char* site_;
  const char* detail_;
  std::int64_t context_;
};

namespace detail {
/// Fail-closed programmer-contract violation. This is code, not `assert()`:
/// it never disappears under NDEBUG (FINAL_PLAN section 6, "guards are code
/// never assert()").
[[noreturn]] void fail_fast(const char* what) noexcept;
}  // namespace detail

/// The value-or-refusal carrier named by APPENDIX C1. Deliberately minimal:
/// no implicit unwrapping, no exceptions, no default-constructed empty state.
template <class T, class E = Refusal>
class Expected {
 public:
  using value_type = T;
  using error_type = E;

  constexpr Expected(T value) noexcept  // NOLINT(google-explicit-constructor)
      : storage_(std::in_place_index<0>, std::move(value)) {}

  static constexpr Expected refuse(E error) noexcept {
    return Expected(std::in_place_index<1>, std::move(error));
  }

  [[nodiscard]] constexpr bool has_value() const noexcept { return storage_.index() == 0; }
  constexpr explicit operator bool() const noexcept { return has_value(); }

  [[nodiscard]] constexpr const T& value() const& {
    if (!has_value()) {
      detail::fail_fast("qr::Expected::value() called on a refusal");
    }
    return *std::get_if<0>(&storage_);
  }

  [[nodiscard]] constexpr T&& value() && {
    if (!has_value()) {
      detail::fail_fast("qr::Expected::value() called on a refusal");
    }
    return std::move(*std::get_if<0>(&storage_));
  }

  [[nodiscard]] constexpr const E& error() const& {
    if (has_value()) {
      detail::fail_fast("qr::Expected::error() called on a value");
    }
    return *std::get_if<1>(&storage_);
  }

 private:
  template <std::size_t I, class U>
  constexpr Expected(std::in_place_index_t<I> tag, U&& init) noexcept
      : storage_(tag, std::forward<U>(init)) {}

  std::variant<T, E> storage_;
};

/// Convenience: build a refused Expected without naming the value type twice.
template <class T, class E = Refusal>
constexpr Expected<T, E> refuse(E error) noexcept {
  return Expected<T, E>::refuse(std::move(error));
}

}  // namespace qr

#endif  // QR_CORE_REFUSAL_HPP
