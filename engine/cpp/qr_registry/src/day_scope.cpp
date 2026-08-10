#include "qr_registry/day_scope.hpp"

#include <filesystem>
#include <system_error>
#include <utility>

namespace qr {
namespace {

constexpr const char* kSite = "qr_registry::DayScope";

}  // namespace

Expected<DayScope, Refusal> DayScope::admit(const Registry& registry, std::int64_t ordinal) {
  // THE WALL, first statement of the function: nothing below runs for an
  // out-of-scope ordinal, and this function has no filesystem argument at all.
  if (ordinal < kScopeFirstOrdinal || ordinal > kScopeLastOrdinal) {
    return Expected<DayScope, Refusal>::refuse(
        Refusal(RefusalCode::ORDINAL_OUTSIDE_SCOPE, kSite,
                "ordinal outside the scoped calendar 125..749", ordinal));
  }
  auto session = registry.session_at(ordinal);
  if (!session.has_value()) {
    return Expected<DayScope, Refusal>::refuse(session.error());
  }
  return DayScope(ordinal, *session.value());
}

Expected<DayScope, Refusal> DayScope::admit_day(const Registry& registry, std::string_view day) {
  const auto civil = CivilDate::parse_ymd(day);
  if (!civil.has_value()) {
    return Expected<DayScope, Refusal>::refuse(
        Refusal(RefusalCode::DAY_OUTSIDE_CALENDAR, kSite, "not a YYYY-MM-DD civil day"));
  }
  const auto ordinal = registry.ordinal_of_day(day);
  if (!ordinal.has_value()) {
    return Expected<DayScope, Refusal>::refuse(
        Refusal(RefusalCode::DAY_OUTSIDE_CALENDAR, kSite,
                "no row in the frozen 1,003-session registry"));
  }
  return admit(registry, ordinal.value());
}

std::filesystem::path DayScope::source_path(const std::filesystem::path& corpus_root) const {
  return corpus_root / session_.source_relative_path;
}

Expected<std::filesystem::path, Refusal> resolve_source_path(
    const Registry& registry, const std::filesystem::path& corpus_root, std::int64_t ordinal) {
  auto scope = DayScope::admit(registry, ordinal);
  if (!scope.has_value()) {
    return Expected<std::filesystem::path, Refusal>::refuse(scope.error());
  }
  std::error_code root_error;
  if (!std::filesystem::is_directory(corpus_root, root_error)) {
    return Expected<std::filesystem::path, Refusal>::refuse(
        Refusal(RefusalCode::INVALID_CORPUS_ROOT, kSite,
                "corpus root is missing or is not a directory", ordinal));
  }
  std::filesystem::path path = scope.value().source_path(corpus_root);
  std::error_code file_error;
  if (!std::filesystem::is_regular_file(path, file_error)) {
    return Expected<std::filesystem::path, Refusal>::refuse(Refusal(
        RefusalCode::IO, kSite, "registry-declared source file is not present", ordinal));
  }
  return path;
}

Expected<std::filesystem::path, Refusal> resolve_source_path_for_day(
    const Registry& registry, const std::filesystem::path& corpus_root, std::string_view day) {
  auto scope = DayScope::admit_day(registry, day);
  if (!scope.has_value()) {
    return Expected<std::filesystem::path, Refusal>::refuse(scope.error());
  }
  return resolve_source_path(registry, corpus_root, scope.value().ordinal());
}

}  // namespace qr
