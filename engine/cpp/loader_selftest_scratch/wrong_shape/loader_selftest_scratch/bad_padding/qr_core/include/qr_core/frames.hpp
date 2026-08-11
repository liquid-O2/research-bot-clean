// qr_core/frames.hpp - the frame-A / frame-B / civil-date strong types.
//
// SPEC (design/DESIGN_SUBSTRATE.md section 6 + APPENDIX C1):
//   "FrameA/FrameB/CivilDate strong types, deleted implicit conversions +
//    static_assert non-convertibility"
//   "FrameA/FrameB wrapped i64, explicit ctors, deleted conversions"
//
// WHY THIS TYPE WALL EXISTS: every token corpus timestamp is naive-Eastern
// wall clock (frame B). Only a session clock may turn one into a true UTC
// instant (frame A). Mixing the two silently reads hours into the future, so
// the two frames are DIFFERENT TYPES that cannot be built from, converted to,
// or compared with a bare integer, or with each other.
//
//   * FrameB  - naive-Eastern instant, explicit ctor from int64 nanoseconds.
//   * FrameA  - true UTC instant. Constructible ONLY through the greppable
//               factory `FrameA::from_published_utc_epoch_ns`. There is no
//               public constructor at all, so no code can mint a frame-A
//               instant by accident; the WP2 clock port is the only lawful
//               producer, and every other producer is a grep away.
//   * CivilDate - a civil day, wrapped as days since 1970-01-01. Days (not a
//               packed YYYYMMDD) is the encoding the design requires, because
//               section 6 specifies WRONG_CIVIL_DAY(delta_days): a day
//               DIFFERENCE has to be exact integer arithmetic.
#ifndef QR_CORE_FRAMES_HPP
#define QR_CORE_FRAMES_HPP

#include <concepts>
#include <cstdint>
#include <string>
#include <string_view>
#include <type_traits>

#include "qr_core/refusal.hpp"

namespace qr {

/// True UTC nanoseconds since the epoch. No public constructor.
class FrameA {
 public:
  FrameA() = delete;

  /// The ONLY way to mint a frame-A instant. Greppable by name.
  [[nodiscard]] static constexpr FrameA from_published_utc_epoch_ns(std::int64_t ns) noexcept {
    return FrameA(ns);
  }

  [[nodiscard]] constexpr std::int64_t ns() const noexcept { return ns_; }

  friend constexpr bool operator==(FrameA lhs, FrameA rhs) noexcept { return lhs.ns_ == rhs.ns_; }
  friend constexpr auto operator<=>(FrameA lhs, FrameA rhs) noexcept { return lhs.ns_ <=> rhs.ns_; }

 private:
  explicit constexpr FrameA(std::int64_t ns) noexcept : ns_(ns) {}
  std::int64_t ns_;
};

/// Naive-Eastern (wall clock) nanoseconds as published by the token corpora.
class FrameB {
 public:
  FrameB() = delete;
  explicit constexpr FrameB(std::int64_t ns) noexcept : ns_(ns) {}

  /// Every other source type is deleted: no int, no unsigned, no double, no
  /// bool, no FrameA. Only an exact int64_t may become a frame-B instant.
  template <class T>
    requires(!std::same_as<std::remove_cvref_t<T>, std::int64_t> &&
             !std::same_as<std::remove_cvref_t<T>, FrameB>)
  FrameB(T) = delete;

  [[nodiscard]] constexpr std::int64_t ns() const noexcept { return ns_; }

  friend constexpr bool operator==(FrameB lhs, FrameB rhs) noexcept { return lhs.ns_ == rhs.ns_; }
  friend constexpr auto operator<=>(FrameB lhs, FrameB rhs) noexcept { return lhs.ns_ <=> rhs.ns_; }

 private:
  std::int64_t ns_;
};

/// A civil day, as days since 1970-01-01 (proleptic Gregorian).
class CivilDate {
 public:
  CivilDate() = delete;
  explicit constexpr CivilDate(std::int64_t days_since_epoch) noexcept
      : days_(days_since_epoch) {}

  template <class T>
    requires(!std::same_as<std::remove_cvref_t<T>, std::int64_t> &&
             !std::same_as<std::remove_cvref_t<T>, CivilDate>)
  CivilDate(T) = delete;

  /// Parses a canonical `YYYY-MM-DD` civil day. Anything else - wrong length,
  /// non-digits, a month/day out of range, a day past the month's real length
  /// - is RefusalCode::MALFORMED_CIVIL_DATE (ported from
  /// corpus::CorpusError::MalformedCivilDate).
  [[nodiscard]] static Expected<CivilDate, Refusal> parse_ymd(std::string_view text) noexcept;

  [[nodiscard]] constexpr std::int64_t days_since_epoch() const noexcept { return days_; }

  /// Canonical `YYYY-MM-DD` rendering (round-trips parse_ymd).
  [[nodiscard]] std::string to_ymd() const;

  /// Exact signed day difference (this - other). Never approximate.
  [[nodiscard]] constexpr std::int64_t delta_days(CivilDate other) const noexcept {
    return days_ - other.days_;
  }

  friend constexpr bool operator==(CivilDate lhs, CivilDate rhs) noexcept {
    return lhs.days_ == rhs.days_;
  }
  friend constexpr auto operator<=>(CivilDate lhs, CivilDate rhs) noexcept {
    return lhs.days_ <=> rhs.days_;
  }

 private:
  std::int64_t days_;
};

// --- the non-convertibility wall, checked at compile time -------------------
// A bare integer may never become a frame instant implicitly, a frame instant
// may never decay to an integer, and the two frames may never convert into
// each other.
static_assert(!std::is_convertible_v<std::int64_t, FrameA>);
static_assert(!std::is_convertible_v<std::int64_t, FrameB>);
static_assert(!std::is_convertible_v<std::int64_t, CivilDate>);
static_assert(!std::is_convertible_v<int, FrameB>);
static_assert(!std::is_convertible_v<double, FrameB>);
static_assert(!std::is_convertible_v<bool, FrameB>);
static_assert(!std::is_convertible_v<FrameA, std::int64_t>);
static_assert(!std::is_convertible_v<FrameB, std::int64_t>);
static_assert(!std::is_convertible_v<CivilDate, std::int64_t>);
static_assert(!std::is_convertible_v<FrameA, FrameB>);
static_assert(!std::is_convertible_v<FrameB, FrameA>);
static_assert(!std::is_constructible_v<FrameA, std::int64_t>);
static_assert(!std::is_constructible_v<FrameB, FrameA>);
static_assert(!std::is_constructible_v<FrameB, int>);
static_assert(!std::is_constructible_v<FrameB, double>);
static_assert(!std::is_constructible_v<CivilDate, int>);
static_assert(std::is_constructible_v<FrameB, std::int64_t>);
static_assert(std::is_constructible_v<CivilDate, std::int64_t>);
static_assert(!std::is_default_constructible_v<FrameA>);
static_assert(!std::is_default_constructible_v<FrameB>);
static_assert(!std::is_default_constructible_v<CivilDate>);
static_assert(sizeof(FrameA) == sizeof(std::int64_t));
static_assert(sizeof(FrameB) == sizeof(std::int64_t));
static_assert(sizeof(CivilDate) == sizeof(std::int64_t));

}  // namespace qr

#endif  // QR_CORE_FRAMES_HPP
