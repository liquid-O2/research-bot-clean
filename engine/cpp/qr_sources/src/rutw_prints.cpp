#include "qr_sources/rutw_prints.hpp"

#include <span>
#include <string>

#include "qr_clock/session_clock.hpp"

namespace qr::sources {
namespace {

constexpr const char* kOpenSite = "qr_sources::RutwPrintReader::open";

}  // namespace

bool is_rutw_corpus_root(const std::filesystem::path& corpus_root) noexcept {
  for (const std::filesystem::path& component : corpus_root) {
    if (component.native() == kDeferredPrintModality) {
      return true;
    }
  }
  return false;
}

FileExpected<RutwPrintReader> RutwPrintReader::open(const DayScope& scope,
                                                     const std::filesystem::path& corpus_root) {
  // WALL 1 — THE MODALITY, ON THE PATH, BEFORE A PAYLOAD PATH IS FORMED. This
  // is the exact mirror of `OptionPrintReader::open`'s wall: that reader
  // refuses a root carrying `RUTW`, this one refuses a root that does not. The
  // pair is what makes the B5 wall two-way, and it holds whatever encoding the
  // vendor writes either corpus in.
  if (!is_rutw_corpus_root(corpus_root)) {
    return parquet::refuse_file<RutwPrintReader>(
        RefusalCode::CONFIG, kOpenSite,
        "this reader is pinned to the RUTW print corpus; the root names no RUTW modality",
        corpus_root.string(), std::string(kDeferredPrintModality), scope.ordinal());
  }

  // WALL 2 — THE REGISTRY-SESSION WALL (B5: "registry-session wall (W2.12)"),
  // inherited rather than rebuilt: `scope` exists only because
  // `DayScope::admit` minted it, and the session clock refuses a registry row
  // it cannot place.
  const std::filesystem::path path = day_file(corpus_root, scope);
  Expected<SessionClock, Refusal> clock = SessionClock::from_session(scope.session());
  if (!clock.has_value()) {
    return parquet::refuse_file<RutwPrintReader>(clock.error().code(), kOpenSite,
                                                  "the session clock refuses this registry row",
                                                  path.string(), scope.day(), scope.ordinal());
  }
  const std::int64_t open_ms = clock.value().open_b().ns() / kNanosecondsPerMillisecond;
  const std::int64_t close_ms = clock.value().close_b().ns() / kNanosecondsPerMillisecond;

  // WALL 3 — THE PROFILE, ON THE FILE'S OWN SCHEMA, BEFORE A PAYLOAD BYTE.
  // ONE admitted vector, not two: B5 is the wide profile and nothing else, so
  // IWM-compact bytes fail on `expiration` (DATE ordinal against a UTF-8 pin)
  // and are refused by name. `gate_schema` also pins all 62 NAMES in order,
  // including the 42 columns this reader never decodes.
  FileExpected<SessionSource> source =
      SessionSource::open(path, view_of(kRutwPrintSpec),
                          std::span<const ColumnForm>(kRutwPrintFormsWide), open_ms, close_ms);
  if (!source.has_value()) {
    return FileExpected<RutwPrintReader>::refuse(source.error());
  }
  return RutwPrintReader(std::move(source).value(), scope.day());
}

}  // namespace qr::sources
