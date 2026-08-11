// qr_registry/warmup_scope.hpp — THE PRIOR-ONLY WARMUP SCOPE (CC-012).
//
// SPEC (design/DESIGN_FEATURES.md sha bf70dd35e5407863, §CC-012 WARMUP SCOPE
// RULING, verbatim):
//
//   "Conflict: A3 'burn-in 0..124 warmup lawful' vs qr_registry 125-wall.
//    RULING: a distinct `WarmupScope` type, constructible ONLY for ordinals
//    0..124 (compile-disjoint from DayScope 125..749), accepted ONLY by
//    prior-state accumulator entry points (carrier warmup). Candidate/label/
//    emission APIs refuse WarmupScope (typed). Zero-leak rationale: ordinals
//    0..124 (2022-01-03..2022-07-01) precede ALL folds chronologically and
//    belong to none; prior-only accumulation from strictly-past data leaks
//    nothing; payload is on disk and outside every never-open list. The
//    125-wall stays intact for every decision/label/candidate path."
//
// TWO WALLS, FACING OPPOSITE DIRECTIONS, AND NEITHER WEAKENS THE OTHER.
// `DayScope::admit` refuses everything below 125 exactly as it always did —
// this header adds no path into it, changes none of its bytes, and the
// r2 fixture re-proves it. `WarmupScope::admit` refuses everything at or above
// 125. The two ranges are disjoint, so no ordinal can produce both, and no
// session can be read for warmup and for decisions through one object.
//
// COMPILE-DISJOINT MEANS COMPILE-DISJOINT. There is deliberately no conversion,
// no common base, and no accessor returning a DayScope: `DayScope` is not
// constructible from a `WarmupScope` and every decision-path entry point
// (candidates, labels, emission) therefore cannot be called with one at all.
// That is a stronger guarantee than a runtime check, and the r3 fixture asserts
// exactly that non-invocability rather than trusting a code review of call
// sites. The one runtime refusal that remains is for the reverse mistake — a
// decision row asked for a warmup ordinal — which `refuse_warmup_ordinal`
// types.
//
// WHAT A WARMUP SCOPE MAY DO: form the payload path of its own session, so a
// prior-state accumulator can read strictly-past sessions. Nothing else. It
// carries no decision second, no side, no candidate, and no label.
#ifndef QR_REGISTRY_WARMUP_SCOPE_HPP
#define QR_REGISTRY_WARMUP_SCOPE_HPP

#include <cstdint>
#include <filesystem>
#include <string>
#include <type_traits>
#include <utility>

#include "qr_core/refusal.hpp"
#include "qr_registry/day_scope.hpp"
#include "qr_registry/registry.hpp"

namespace qr {

/// The warmup calendar: 0-based ordinals 0..124 inclusive — the 125 sessions
/// 2022-01-03..2022-07-01 that precede the scoped calendar and belong to no
/// fold. CC-012's "compile-disjoint from DayScope 125..749" is the
/// static_assert below: the two ranges cannot overlap by construction.
inline constexpr std::int64_t kWarmupFirstOrdinal = 0;
inline constexpr std::int64_t kWarmupLastOrdinal = 124;
inline constexpr std::int64_t kWarmupSessionCount = 125;
static_assert(kWarmupLastOrdinal - kWarmupFirstOrdinal + 1 == kWarmupSessionCount);
static_assert(kWarmupLastOrdinal < kScopeFirstOrdinal,
              "CC-012: the warmup and scoped calendars must be disjoint");

/// One admitted warmup session. Path-forming, and nothing else.
class WarmupScope {
 public:
  WarmupScope() = delete;

  /// **THE WARMUP WALL.** Admits a 0-based calendar ordinal iff it is inside
  /// 0..124. An ordinal at or above `kScopeFirstOrdinal` refuses with
  /// ORDINAL_OUTSIDE_SCOPE — before any path exists and without touching the
  /// filesystem, the same shape as `DayScope::admit`.
  [[nodiscard]] static Expected<WarmupScope, Refusal> admit(const Registry& registry,
                                                            std::int64_t ordinal);

  [[nodiscard]] std::int64_t ordinal() const noexcept { return ordinal_; }
  [[nodiscard]] const Session& session() const noexcept { return session_; }
  [[nodiscard]] const std::string& day() const noexcept { return session_.day; }
  [[nodiscard]] CivilDate civil_date() const noexcept { return session_.civil_date; }
  [[nodiscard]] SourceProfile profile() const noexcept { return session_.source_profile; }
  [[nodiscard]] std::int64_t bar_count() const noexcept { return session_.expected_bar_count; }

  /// The registry-declared payload path of this warmup session. Pure string
  /// composition, a MEMBER for the same reason `DayScope::source_path` is one:
  /// a path may only be derived from an admitted scope.
  [[nodiscard]] std::filesystem::path source_path(
      const std::filesystem::path& corpus_root) const;

 private:
  WarmupScope(std::int64_t ordinal, Session session) noexcept
      : ordinal_(ordinal), session_(std::move(session)) {}

  std::int64_t ordinal_;
  Session session_;
};

/// The typed refusal for the reverse mistake: a DECISION-path caller (a feature
/// row, a label, an emitted tape row) naming a warmup ordinal. CC-012's "never
/// as decision rows" written once so every wave-2 entry point refuses it in the
/// same words.
[[nodiscard]] Refusal refuse_warmup_ordinal(const char* site, std::int64_t ordinal) noexcept;

/// True when `ordinal` belongs to the warmup calendar. The one predicate the
/// decision-path guards read; it never mints a scope.
[[nodiscard]] constexpr bool is_warmup_ordinal(std::int64_t ordinal) noexcept {
  return ordinal >= kWarmupFirstOrdinal && ordinal <= kWarmupLastOrdinal;
}

// CC-012 "compile-disjoint", as a build-breaking assertion rather than a
// comment: no implicit or explicit conversion may exist in either direction, so
// a warmup session can never be laundered into a decision-path API.
static_assert(!std::is_constructible_v<DayScope, const WarmupScope&>,
              "CC-012: a WarmupScope may never become a DayScope");
static_assert(!std::is_constructible_v<WarmupScope, const DayScope&>,
              "CC-012: a DayScope may never become a WarmupScope");

}  // namespace qr

#endif  // QR_REGISTRY_WARMUP_SCOPE_HPP
