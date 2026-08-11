// qr_registry/day_scope.hpp - THE SCOPE WALL.
//
// SPEC: design/DESIGN_SUBSTRATE.md section 6 -
//   "`qr_registry` (TSV + per-file sha gate + 125..749 wall before path
//    formation)"
// Reference port (read-only): /workspace/engine/crates/select_v2/src/calendar.rs
// ("The calendar wall": the only way to build a DayScope is admit(), and a path
// is only ever formed FROM an admitted scope).
//
// THE WALL, mechanically: there is no function anywhere in this module that
// turns a raw ordinal or a raw civil-day string into a path. `source_path` is a
// member of DayScope, and DayScope has no public constructor, so a path can
// only exist downstream of a successful `admit`. Ordinals outside 125..749 -
// which is every 2020/2021 warmup day, every 2025 day, and every 2026 day -
// never produce a scope, therefore never produce a path, therefore never reach
// the filesystem. The refusal happens BEFORE the corpus root is even examined.
#ifndef QR_REGISTRY_DAY_SCOPE_HPP
#define QR_REGISTRY_DAY_SCOPE_HPP

#include <cstdint>
#include <filesystem>
#include <string_view>

#include "qr_core/refusal.hpp"
#include "qr_registry/registry.hpp"

namespace qr {

/// The scoped calendar: 0-based ordinals 125..749 inclusive - the 625 sessions
/// FINAL_PLAN section 1 puts in scope ("1,003 sessions 2022-25 (125..749 = the
/// 625 in current scope)").
inline constexpr std::int64_t kScopeFirstOrdinal = 125;
inline constexpr std::int64_t kScopeLastOrdinal = 749;
inline constexpr std::int64_t kScopeSessionCount = 625;
static_assert(kScopeLastOrdinal - kScopeFirstOrdinal + 1 == kScopeSessionCount);

/// One admitted, in-scope session. The only path-forming object in the module.
class DayScope {
 public:
  DayScope() = delete;

  /// **THE WALL.** Admits a 0-based calendar ordinal iff it is inside
  /// 125..749. Refuses with ORDINAL_OUTSIDE_SCOPE otherwise - before any path
  /// exists and without touching the filesystem (this function takes no root).
  [[nodiscard]] static Expected<DayScope, Refusal> admit(const Registry& registry,
                                                         std::int64_t ordinal);

  /// Admits by civil day. A day with no registry row (every 2026 day) refuses
  /// with DAY_OUTSIDE_CALENDAR; a registered day outside 125..749 refuses with
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
