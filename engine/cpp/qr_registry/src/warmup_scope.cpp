#include "qr_registry/warmup_scope.hpp"

#include <utility>

namespace qr {
namespace {

constexpr const char* kSite = "qr_registry::WarmupScope";

}  // namespace

Expected<WarmupScope, Refusal> WarmupScope::admit(const Registry& registry, std::int64_t ordinal) {
  // THE WARMUP WALL, first statement of the function — the mirror image of
  // DayScope::admit, and like it, this function takes no filesystem argument.
  if (ordinal < kWarmupFirstOrdinal || ordinal > kWarmupLastOrdinal) {
    return Expected<WarmupScope, Refusal>::refuse(
        Refusal(RefusalCode::ORDINAL_OUTSIDE_SCOPE, kSite,
                "ordinal outside the warmup calendar 0..124", ordinal));
  }
  auto session = registry.session_at(ordinal);
  if (!session.has_value()) {
    return Expected<WarmupScope, Refusal>::refuse(session.error());
  }
  return WarmupScope(ordinal, *session.value());
}

std::filesystem::path WarmupScope::source_path(const std::filesystem::path& corpus_root) const {
  return corpus_root / session_.source_relative_path;
}

Refusal refuse_warmup_ordinal(const char* site, std::int64_t ordinal) noexcept {
  return Refusal(RefusalCode::ORDINAL_OUTSIDE_SCOPE, site,
                 "warmup ordinals 0..124 are prior-state only and never a decision row", ordinal);
}

}  // namespace qr
