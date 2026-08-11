// qr_carriers/transforms.hpp — THE EXHAUSTIVE TRANSFORM TABLE.
//
// SPEC (evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 4, verbatim
// — "The transform table is exhaustive:"):
//
//   | Input kind              | Exact pre-TRAIN transform and unit |
//   |-------------------------|------------------------------------|
//   | nonnegative count/size  | `log1p(x)` in raw shares (stock), contracts
//   |                         | (options), or message count |
//   | time/gap/age/span       | checked integer microseconds, then `log1p(us)` |
//   | signed size/flow/gap    | `sign(x)*log1p(abs(x))` in raw shares, contracts,
//   |                         | or `u6*contracts` for premium |
//   | price displacement      | checked truncating integer bps
//   |                         | `(num_u6*10000)/positive_den_u6`; invalid
//   |                         | denominator is missing |
//   | fraction/reliability    | `numerator/max(eligible_denominator,1)`;
//   |                         | denominator zero emits value0, presence0 |
//   | raw Greek/IV            | finite raw dimensionless value, no nonlinear
//   |                         | transform before TRAIN normalization |
//   | DTE                     | nonnegative calendar days, then `log1p(days)` |
//
// EXHAUSTIVE MEANS EXHAUSTIVE (directive D-017). There are exactly seven
// entries below, one per row, and every carrier channel in this module is built
// by calling one of them. A channel that computed `log(x)` or `x/den` inline
// would be a private eighth transform, which the word "exhaustive" forbids.
//
// ABSENCE IS A STATE, NEVER A NUMBER. Every entry returns `Typed<double>`: an
// out-of-domain input (negative count, nonpositive denominator, non-finite
// Greek) comes back as value 0 with a masking `Validity`, exactly as the card's
// "denominator zero emits value0, presence0" and APPENDIX A's "every value
// channel carries a presence bit (missing => 0,p=0)" require. Nothing here
// substitutes a boundary value for a true one — that is FINAL_PLAN section 6's
// arithmetic law, and it is why the displacement entry returns `Expected` on
// i64 overflow instead of clamping.
//
// THE TWO UNIT WORDS THE CARD USES, AND WHY BOTH LIVE HERE (STOP-question note,
// reported to the orchestrator with this lane): section 4's table says every
// "time/gap/age/span" is `log1p(microseconds)`, while section 5's location list
// and candidate-set list name two channels "log1p seconds since last stock
// print" / "log1p age seconds". Both statements are cited law over DIFFERENT
// objects, so both are implemented verbatim and named apart:
// `time_log1p_micros` serves every section-4 channel and
// `time_log1p_seconds` serves exactly the three section-5 channels that say
// "seconds". No third convention exists.
#ifndef QR_CARRIERS_TRANSFORMS_HPP
#define QR_CARRIERS_TRANSFORMS_HPP

#include <cmath>
#include <cstdint>

#include "qr_core/checked.hpp"
#include "qr_core/refusal.hpp"
#include "qr_core/validity.hpp"

namespace qr::carriers {

/// Microseconds in one second, and nanoseconds in one microsecond: the two
/// exact integer conversions the "checked integer microseconds" row needs.
inline constexpr std::int64_t kMicrosPerSecond = 1'000'000;
inline constexpr std::int64_t kNanosPerMicro = 1'000;
inline constexpr std::int64_t kNanosPerSecond = 1'000'000'000;
/// One basis point is 1/10,000: the price-displacement row's scale.
inline constexpr std::int64_t kBpsScale = 10'000;

/// A masked (absent) value: 0 with a typed reason. The card's "value0,
/// presence0" written once so no channel spells it a second way.
[[nodiscard]] constexpr Typed<double> masked(Validity why) noexcept {
  return Typed<double>{0.0, why};
}

/// A present value.
[[nodiscard]] constexpr Typed<double> present(double value) noexcept {
  return Typed<double>{value, Validity::VALID};
}

// ---------------------------------------------------------------------------
// Row 1 — nonnegative count/size: log1p(x).
// ---------------------------------------------------------------------------

/// `log1p(x)` over a NONNEGATIVE count in raw shares, contracts or messages. A
/// negative input is outside the row's declared domain and is masked
/// NONPOSITIVE rather than folded through `log1p` (which would return NaN below
/// -1 and a negative number above it).
[[nodiscard]] inline Typed<double> count_log1p(std::int64_t raw) noexcept {
  if (raw < 0) {
    return masked(Validity::NONPOSITIVE);
  }
  return present(std::log1p(static_cast<double>(raw)));
}

// ---------------------------------------------------------------------------
// Row 2 — time/gap/age/span: checked integer microseconds, then log1p(us).
// ---------------------------------------------------------------------------

/// `to_ns - from_ns` in TRUNCATED integer microseconds, under checked
/// subtraction. The tape is millisecond-stamped, so every real difference is an
/// exact multiple of 1,000us and the truncation never fires on corpus data; it
/// is still written as a truncation because the card says integer microseconds
/// and a rounding rule invented here would be an eighth transform.
[[nodiscard]] inline Expected<std::int64_t, Refusal> duration_micros(
    std::int64_t from_ns, std::int64_t to_ns) noexcept {
  const auto delta = checked_sub(to_ns, from_ns);
  if (!delta.has_value()) {
    return Expected<std::int64_t, Refusal>::refuse(delta.error());
  }
  return delta.value() / kNanosPerMicro;
}

/// `log1p(us)`. A negative span is outside the row's domain (the strict-prior
/// law makes it unreachable from real tape) and is masked, never negated.
[[nodiscard]] inline Typed<double> time_log1p_micros(std::int64_t micros) noexcept {
  if (micros < 0) {
    return masked(Validity::NONPOSITIVE);
  }
  return present(std::log1p(static_cast<double>(micros)));
}

/// `log1p(seconds)` for EXACTLY the three section-5 channels whose own text
/// says "seconds" (the two location last-print ages and the candidate-set age).
/// The seconds are derived from the same checked integer microseconds, so the
/// two units never come from two different clocks.
[[nodiscard]] inline Typed<double> time_log1p_seconds(std::int64_t micros) noexcept {
  if (micros < 0) {
    return masked(Validity::NONPOSITIVE);
  }
  return present(std::log1p(static_cast<double>(micros) / static_cast<double>(kMicrosPerSecond)));
}

// ---------------------------------------------------------------------------
// Row 3 — signed size/flow/gap: sign(x)*log1p(abs(x)).
// ---------------------------------------------------------------------------

/// `sign(x)*log1p(|x|)`. Zero maps to zero (sign 0), so the transform is odd
/// and continuous at the origin, and a side reflection that negates `x`
/// negates the output exactly — which is what the orientation fixture asserts.
[[nodiscard]] inline Typed<double> signed_log1p(double raw) noexcept {
  if (!std::isfinite(raw)) {
    return masked(Validity::NONFINITE);
  }
  if (raw == 0.0) {
    return present(0.0);
  }
  const double magnitude = std::log1p(std::fabs(raw));
  return present(raw < 0.0 ? -magnitude : magnitude);
}

/// The exact-integer door onto the same row (signed shares, contracts, or
/// `u6*contracts` premium), so a caller never has to widen through double
/// itself and lose the sign of a value at the i64 boundary.
[[nodiscard]] inline Typed<double> signed_log1p_int(std::int64_t raw) noexcept {
  return signed_log1p(static_cast<double>(raw));
}

// ---------------------------------------------------------------------------
// Row 4 — price displacement: checked truncating integer bps.
// ---------------------------------------------------------------------------

/// `(num_u6*10000)/positive_den_u6`, TRUNCATING (C++ integer division truncates
/// toward zero, which is the card's word), with the multiply checked. A
/// nonpositive denominator is "invalid denominator is missing" — masked, never
/// a substituted 0 or a floating-point rescue.
///
/// Returned as an exact integer count of basis points: the value the model sees
/// is this integer widened to double, and no intermediate rounding exists.
[[nodiscard]] inline Expected<Typed<std::int64_t>, Refusal> displacement_bps(
    std::int64_t numerator_u6, std::int64_t denominator_u6) noexcept {
  if (denominator_u6 <= 0) {
    return Typed<std::int64_t>{0, Validity::MISSING};
  }
  const auto scaled = checked_mul(numerator_u6, kBpsScale);
  if (!scaled.has_value()) {
    return Expected<Typed<std::int64_t>, Refusal>::refuse(scaled.error());
  }
  return Typed<std::int64_t>{scaled.value() / denominator_u6, Validity::VALID};
}

/// The same row, delivered as the channel-layer `Typed<double>`.
[[nodiscard]] inline Expected<Typed<double>, Refusal> displacement_bps_value(
    std::int64_t numerator_u6, std::int64_t denominator_u6) noexcept {
  const auto bps = displacement_bps(numerator_u6, denominator_u6);
  if (!bps.has_value()) {
    return Expected<Typed<double>, Refusal>::refuse(bps.error());
  }
  return Typed<double>{static_cast<double>(bps.value().value), bps.value().v};
}

// ---------------------------------------------------------------------------
// Row 5 — fraction/reliability: numerator/max(eligible_denominator,1).
// ---------------------------------------------------------------------------

/// `numerator/max(denominator,1)`; "denominator zero emits value0, presence0".
/// A negative denominator is not a denominator and masks identically.
[[nodiscard]] inline Typed<double> fraction(std::int64_t numerator,
                                            std::int64_t denominator) noexcept {
  if (denominator <= 0) {
    return masked(Validity::MISSING);
  }
  return present(static_cast<double>(numerator) / static_cast<double>(denominator));
}

/// The ONE declared exception to the presence half of row 5, quoted from the
/// card's own parenthesis: "`r_modality = finite-all-four group count /
/// max(group count,1)` (0 when empty)". The empty case has a DEFINED value of
/// 0 because section 5 multiplies by it (`r_print`, `r_nbbo`, `r_option` weight
/// the interaction rung), so it is present-with-zero, not missing.
[[nodiscard]] inline Typed<double> reliability_r_modality(std::int64_t finite_all_four_groups,
                                                          std::int64_t group_count) noexcept {
  const std::int64_t denominator = group_count > 1 ? group_count : 1;
  return present(static_cast<double>(finite_all_four_groups) / static_cast<double>(denominator));
}

// ---------------------------------------------------------------------------
// Row 6 — raw Greek/IV: the finite raw dimensionless value, untransformed.
// ---------------------------------------------------------------------------

/// The identity on a finite value; a non-finite one is masked NONFINITE. No
/// nonlinear transform runs before TRAIN normalization, which is the row's
/// whole content.
[[nodiscard]] inline Typed<double> raw_dimensionless(double value) noexcept {
  if (!std::isfinite(value)) {
    return masked(Validity::NONFINITE);
  }
  return present(value);
}

// ---------------------------------------------------------------------------
// Row 7 — DTE: nonnegative calendar days, then log1p(days).
// ---------------------------------------------------------------------------

/// `log1p(days)` over NONNEGATIVE calendar days. A negative day count (an
/// expiry before the session) is outside the declared domain and is masked.
[[nodiscard]] inline Typed<double> dte_log1p_days(std::int64_t calendar_days) noexcept {
  if (calendar_days < 0) {
    return masked(Validity::NONPOSITIVE);
  }
  return present(std::log1p(static_cast<double>(calendar_days)));
}

// ---------------------------------------------------------------------------
// The two structural helpers the card's own wording needs.
// ---------------------------------------------------------------------------

/// A structurally observed binary quality value: "structurally observed binary
/// quality values use presence1" (section 4). The value is 0.0 or 1.0 and the
/// presence bit is always set.
[[nodiscard]] constexpr Typed<double> structural_bit(bool set) noexcept {
  return Typed<double>{set ? 1.0 : 0.0, Validity::VALID};
}

/// "All token/group/bin means divide only by the number of finite present
/// members; zero such members emits value0/presence0." The one mean primitive.
[[nodiscard]] inline Typed<double> finite_member_mean(double sum_of_present,
                                                      std::int64_t present_count) noexcept {
  if (present_count <= 0) {
    return masked(Validity::MISSING);
  }
  return present(sum_of_present / static_cast<double>(present_count));
}

}  // namespace qr::carriers

#endif  // QR_CARRIERS_TRANSFORMS_HPP
