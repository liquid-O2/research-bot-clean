// qr_registry/day_scope.hpp - THE SCOPE WALL.
//
// SPEC: design/DESIGN_SUBSTRATE.md section 6 -
//   "`qr_registry` (TSV + per-file sha gate + 125..749 wall before path
//    formation)"
// AMENDED by FINAL_PLAN AMENDMENT 2026-08-12-c (user ruling D-038): the wall
// moves to 125..917. W = 917 = 2025-08-29 = the LAST registry session strictly
// before 2025-09-01. Everything from 2025-09-01 onward (918..1002) plus the
// 2026/RTY payload is the SEALED final exam and is refused here.
// Reference port (read-only): /workspace/engine/crates/select_v2/src/calendar.rs
// ("The calendar wall": the only way to build a DayScope is admit(), and a path
// is only ever formed FROM an admitted scope).
//
// THE WALL, mechanically: there is no function anywhere in this module that
// turns a raw ordinal or a raw civil-day string into a path. `source_path` is a
// member of DayScope, and DayScope has no public constructor, so a path can
// only exist downstream of a successful `admit`. Ordinals outside 125..917 -
// which is every warmup day, every session from 2025-09-01 onward (including
// the share-era boundary s962 = 2025-11-03 and the profile-flip sessions
// s1001/s1002), and every 2026 day - never produce a scope, therefore never
// produce a path, therefore never reach the filesystem. The refusal happens
// BEFORE the corpus root is even examined.
#ifndef QR_REGISTRY_DAY_SCOPE_HPP
#define QR_REGISTRY_DAY_SCOPE_HPP

#include <cstdint>
#include <filesystem>
#include <string_view>

#include "qr_core/refusal.hpp"
#include "qr_registry/registry.hpp"

namespace qr {

/// The scoped calendar: 0-based ordinals 125..917 inclusive - the 793 sessions
/// FINAL_PLAN AMENDMENT 2026-08-12-c puts in scope ("research/learning scope =
/// sessions 125..W where W = last session before 2025-09-01"). W was read off
/// the frozen registry: ordinal 917 = 2025-08-29, and 918 = 2025-09-02 is the
/// first sealed session. The pre-amendment wall was 749 (2024-12-26).
inline constexpr std::int64_t kScopeFirstOrdinal = 125;
inline constexpr std::int64_t kScopeLastOrdinal = 917;
inline constexpr std::int64_t kScopeSessionCount = 793;
static_assert(kScopeLastOrdinal - kScopeFirstOrdinal + 1 == kScopeSessionCount);

/// The first SEALED ordinal - the exam wall. Nothing at or above this may be
/// admitted by any research path until the certification day (D-038 clause 2).
inline constexpr std::int64_t kFirstSealedOrdinal = kScopeLastOrdinal + 1;
static_assert(kFirstSealedOrdinal == 918);
/// The sealed-zone landmarks D-038 clause 5 names explicitly. They are asserted
/// to be sealed by fixture SCOPE-8; naming them here makes an accidental wall
/// move a compile-visible fact rather than a silent one.
static_assert(kScopeLastOrdinal < 962, "s962 (2025-11-03 share era) must stay sealed");
static_assert(kScopeLastOrdinal < 1001, "s1001/s1002 (profile flip) must stay sealed");

/// One admitted, in-scope session. The only path-forming object in the module.
class DayScope {
 public:
  DayScope() = delete;

  /// **THE WALL.** Admits a 0-based calendar ordinal iff it is inside
  /// 125..917. Refuses with ORDINAL_OUTSIDE_SCOPE otherwise - before any path
  /// exists and without touching the filesystem (this function takes no root).
  [[nodiscard]] static Expected<DayScope, Refusal> admit(const Registry& registry,
                                                         std::int64_t ordinal);

  /// Admits by civil day. A day with no registry row (every 2026 day) refuses
  /// with DAY_OUTSIDE_CALENDAR; a registered day outside 125..917 refuses with
  /// ORDINAL_OUTSIDE_SCOPE. Neither forms a path.
  [[nodiscard]] static Expected<DayScope, Refusal> admit_day(const Registry& registry,
                                                             std::string_view day);

  [[nodiscard]] std::int64_t ordinal() const noexcept { return ordinal_; }
  [[nodiscard]] const Session& session() const noexcept { return session_; }
  [[nodiscard]] const std::string& day() const noexcept { return session_.day; }
  [[nodiscard]] CivilDate civil_date() const noexcept { return session_.civil_date; }
  [[nodiscard]] SourceProfile profile() const noexcept { return session_.source_profile; }
  [[nodiscard]] std::int64_t bar_count() const noexcept { return session_.expected_bar_count; }

  /// The registry-declared stock-quote payload path for this session. Pure
  /// string composition: it touches nothing. It is a MEMBER because a path may
  /// only be derived from an admitted scope.
  [[nodiscard]] std::filesystem::path source_path(
      const std::filesystem::path& corpus_root) const;

 private:
  DayScope(std::int64_t ordinal, Session session) noexcept
      : ordinal_(ordinal), session_(std::move(session)) {}

  std::int64_t ordinal_;
  Session session_;
};

/// Admit-then-resolve, in that order: the wall fires before the corpus root is
/// examined, and the returned path is known to exist. Used by the fixture that
/// proves an out-of-scope ordinal never reaches the filesystem.
[[nodiscard]] Expected<std::filesystem::path, Refusal> resolve_source_path(
    const Registry& registry, const std::filesystem::path& corpus_root, std::int64_t ordinal);

/// Same ordering, keyed by civil day.
[[nodiscard]] Expected<std::filesystem::path, Refusal> resolve_source_path_for_day(
    const Registry& registry, const std::filesystem::path& corpus_root, std::string_view day);

}  // namespace qr

#endif  // QR_REGISTRY_DAY_SCOPE_HPP
