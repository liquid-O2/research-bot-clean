// qr_core/validity.hpp - the 14-state validity lattice and Typed<T>.
//
// SPEC (verbatim, design/DESIGN_SUBSTRATE.md APPENDIX C1):
//   enum class Validity : uint8_t {VALID, MISSING, EQUAL_TIME_UNORDERED,
//   ATTACHMENT_FUTURE, WRONG_CIVIL_DAY, STALE_DIAG, LOCKED, CROSSED,
//   ONE_SIDED, NONFINITE, NONPOSITIVE, CONDITION_INELIGIBLE,
//   CLOCK_UNAVAILABLE, MODALITY_ABSENT};
//   template<class T> struct Typed {T value; Validity v;};
//   combine = worst-wins frozen table
//
// TWO ORDERS LIVE HERE AND THEY ARE NOT THE SAME ORDER:
//
//   * The DECLARATION order below is frozen by APPENDIX C1 and never changes.
//   * The SEVERITY order that "worst wins" refers to is the orchestrator's
//     ruling of 2026-08-10, best to worst:
//
//       VALID < STALE_DIAG < MISSING < EQUAL_TIME_UNORDERED <
//       ATTACHMENT_FUTURE < WRONG_CIVIL_DAY < LOCKED < CROSSED < ONE_SIDED <
//       NONFINITE < NONPOSITIVE < CONDITION_INELIGIBLE < CLOCK_UNAVAILABLE <
//       MODALITY_ABSENT
//
//     Ruling rationale: STALE_DIAG is DIAGNOSTIC ONLY under card law - quote
//     age gates nothing and the value stays usable - so it may dominate VALID
//     and nothing else. It must never outrank an unavailability state:
//     combine(STALE_DIAG, MISSING) is MISSING, not STALE_DIAG.
//
// THE FROZEN TABLE. `combine` is a lookup in kCombineTable below, written out
// cell by cell (14x14 = 196 entries) so that a mutant patch can flip exactly
// one cell and a test must catch it. Rows and columns are indexed by the
// DECLARATION order; the contents encode the SEVERITY order. Nothing here is
// derived at run time and no state is special-cased.
#ifndef QR_CORE_VALIDITY_HPP
#define QR_CORE_VALIDITY_HPP

#include <cstddef>
#include <cstdint>

namespace qr {

enum class Validity : std::uint8_t {
  VALID,
  MISSING,
  EQUAL_TIME_UNORDERED,
  ATTACHMENT_FUTURE,
  WRONG_CIVIL_DAY,
  STALE_DIAG,
  LOCKED,
  CROSSED,
  ONE_SIDED,
  NONFINITE,
  NONPOSITIVE,
  CONDITION_INELIGIBLE,
  CLOCK_UNAVAILABLE,
  MODALITY_ABSENT,
};

/// Exactly fourteen states (APPENDIX C1). Anything else is a spec drift.
inline constexpr std::size_t kValidityCount = 14;

/// A value that carries its own validity. Aggregate, exactly as specified.
template <class T>
struct Typed {
  T value;
  Validity v;
};

namespace lattice {
using enum Validity;

/// The frozen worst-wins table. Row = left operand, column = right operand.
inline constexpr Validity kCombineTable[kValidityCount][kValidityCount] = {
    // row VALID
    {VALID, MISSING, EQUAL_TIME_UNORDERED, ATTACHMENT_FUTURE,
     WRONG_CIVIL_DAY, STALE_DIAG, LOCKED, CROSSED,
     ONE_SIDED, NONFINITE, NONPOSITIVE, CONDITION_INELIGIBLE,
     CLOCK_UNAVAILABLE, MODALITY_ABSENT},
    // row MISSING
    {MISSING, MISSING, EQUAL_TIME_UNORDERED, ATTACHMENT_FUTURE,
     WRONG_CIVIL_DAY, MISSING, LOCKED, CROSSED,
     ONE_SIDED, NONFINITE, NONPOSITIVE, CONDITION_INELIGIBLE,
     CLOCK_UNAVAILABLE, MODALITY_ABSENT},
    // row EQUAL_TIME_UNORDERED
    {EQUAL_TIME_UNORDERED, EQUAL_TIME_UNORDERED, EQUAL_TIME_UNORDERED, ATTACHMENT_FUTURE,
     WRONG_CIVIL_DAY, EQUAL_TIME_UNORDERED, LOCKED, CROSSED,
     ONE_SIDED, NONFINITE, NONPOSITIVE, CONDITION_INELIGIBLE,
     CLOCK_UNAVAILABLE, MODALITY_ABSENT},
    // row ATTACHMENT_FUTURE
    {ATTACHMENT_FUTURE, ATTACHMENT_FUTURE, ATTACHMENT_FUTURE, ATTACHMENT_FUTURE,
     WRONG_CIVIL_DAY, ATTACHMENT_FUTURE, LOCKED, CROSSED,
     ONE_SIDED, NONFINITE, NONPOSITIVE, CONDITION_INELIGIBLE,
     CLOCK_UNAVAILABLE, MODALITY_ABSENT},
    // row WRONG_CIVIL_DAY
    {WRONG_CIVIL_DAY, WRONG_CIVIL_DAY, WRONG_CIVIL_DAY, WRONG_CIVIL_DAY,
     WRONG_CIVIL_DAY, WRONG_CIVIL_DAY, LOCKED, CROSSED,
     ONE_SIDED, NONFINITE, NONPOSITIVE, CONDITION_INELIGIBLE,
     CLOCK_UNAVAILABLE, MODALITY_ABSENT},
    // row STALE_DIAG
    {STALE_DIAG, MISSING, EQUAL_TIME_UNORDERED, ATTACHMENT_FUTURE,
     WRONG_CIVIL_DAY, STALE_DIAG, LOCKED, CROSSED,
     ONE_SIDED, NONFINITE, NONPOSITIVE, CONDITION_INELIGIBLE,
     CLOCK_UNAVAILABLE, MODALITY_ABSENT},
    // row LOCKED
    {LOCKED, LOCKED, LOCKED, LOCKED,
     LOCKED, LOCKED, LOCKED, CROSSED,
     ONE_SIDED, NONFINITE, NONPOSITIVE, CONDITION_INELIGIBLE,
     CLOCK_UNAVAILABLE, MODALITY_ABSENT},
    // row CROSSED
    {CROSSED, CROSSED, CROSSED, CROSSED,
     CROSSED, CROSSED, CROSSED, CROSSED,
     ONE_SIDED, NONFINITE, NONPOSITIVE, CONDITION_INELIGIBLE,
     CLOCK_UNAVAILABLE, MODALITY_ABSENT},
    // row ONE_SIDED
    {ONE_SIDED, ONE_SIDED, ONE_SIDED, ONE_SIDED,
     ONE_SIDED, ONE_SIDED, ONE_SIDED, ONE_SIDED,
     ONE_SIDED, NONFINITE, NONPOSITIVE, CONDITION_INELIGIBLE,
     CLOCK_UNAVAILABLE, MODALITY_ABSENT},
    // row NONFINITE
    {NONFINITE, NONFINITE, NONFINITE, NONFINITE,
     NONFINITE, NONFINITE, NONFINITE, NONFINITE,
     NONFINITE, NONFINITE, NONPOSITIVE, CONDITION_INELIGIBLE,
     CLOCK_UNAVAILABLE, MODALITY_ABSENT},
    // row NONPOSITIVE
    {NONPOSITIVE, NONPOSITIVE, NONPOSITIVE, NONPOSITIVE,
     NONPOSITIVE, NONPOSITIVE, NONPOSITIVE, NONPOSITIVE,
     NONPOSITIVE, NONPOSITIVE, NONPOSITIVE, CONDITION_INELIGIBLE,
     CLOCK_UNAVAILABLE, MODALITY_ABSENT},
    // row CONDITION_INELIGIBLE
    {CONDITION_INELIGIBLE, CONDITION_INELIGIBLE, CONDITION_INELIGIBLE, CONDITION_INELIGIBLE,
     CONDITION_INELIGIBLE, CONDITION_INELIGIBLE, CONDITION_INELIGIBLE, CONDITION_INELIGIBLE,
     CONDITION_INELIGIBLE, CONDITION_INELIGIBLE, CONDITION_INELIGIBLE, CONDITION_INELIGIBLE,
     CLOCK_UNAVAILABLE, MODALITY_ABSENT},
    // row CLOCK_UNAVAILABLE
    {CLOCK_UNAVAILABLE, CLOCK_UNAVAILABLE, CLOCK_UNAVAILABLE, CLOCK_UNAVAILABLE,
     CLOCK_UNAVAILABLE, CLOCK_UNAVAILABLE, CLOCK_UNAVAILABLE, CLOCK_UNAVAILABLE,
     CLOCK_UNAVAILABLE, CLOCK_UNAVAILABLE, CLOCK_UNAVAILABLE, CLOCK_UNAVAILABLE,
     CLOCK_UNAVAILABLE, MODALITY_ABSENT},
    // row MODALITY_ABSENT
    {MODALITY_ABSENT, MODALITY_ABSENT, MODALITY_ABSENT, MODALITY_ABSENT,
     MODALITY_ABSENT, MODALITY_ABSENT, MODALITY_ABSENT, MODALITY_ABSENT,
     MODALITY_ABSENT, MODALITY_ABSENT, MODALITY_ABSENT, MODALITY_ABSENT,
     MODALITY_ABSENT, MODALITY_ABSENT},
};

}  // namespace lattice

/// Worst-wins combination of two validity states (frozen table lookup).
[[nodiscard]] constexpr Validity combine(Validity a, Validity b) noexcept {
  return lattice::kCombineTable[static_cast<std::size_t>(a)][static_cast<std::size_t>(b)];
}

/// Stable screaming-snake name of a validity state (never a sentence).
[[nodiscard]] const char* validity_name(Validity v) noexcept;

/// True only for the VALID state; every other state masks the value.
template <class T>
[[nodiscard]] constexpr bool is_valid(const Typed<T>& typed) noexcept {
  return typed.v == Validity::VALID;
}

/// Worst-wins combination of a typed value's validity with another state.
template <class T>
[[nodiscard]] constexpr Typed<T> with_combined(const Typed<T>& typed, Validity other) noexcept {
  return Typed<T>{typed.value, combine(typed.v, other)};
}

}  // namespace qr

#endif  // QR_CORE_VALIDITY_HPP
