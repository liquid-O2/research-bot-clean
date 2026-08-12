// qr_sources/rutw_prints.hpp — B5: the RUTW option-print reader.
//
// SPEC (FINAL_PLAN APPENDIX B5, verbatim): "RUTW prints: same 62-name wide
// profile; same laws; registry-session wall (W2.12)."
// SPEC (FINAL_PLAN APPENDIX B3, in force here verbatim because B5 says "same
// laws"): "expiration(1), strike(2), right(3), ts(4), sequence(5),
// condition(10) [single-leg in {18,95,125,126}], size(11), price(13),
// delta(14), gamma(20), vanna(21), charm(22), IV(34), underlying_ts(36),
// underlying_px(37), bid(39), bid_size(40), ask(42), ask_size(43),
// quote_ts(45). +vega(16) via W2.4 registered extension. HARD-REFUSED:
// side(38), sweep_*(47-50), prem/*_flow(53-61), unlisted Greeks. Aggressor
// recomputed; IV/Greeks need BOTH strict-prior attachments; flows =
// v*size*greek."
// SPEC (FINAL_PLAN A10 / W2.12): "RUTW prints through the same causal
// machinery (wide profile)".
//
// WHY THERE ARE TWO READERS AND NOT ONE WITH A FLAG. B3's reader admits TWO
// encodings, because the IWM corpus was measured in both; B5's corpus is
// written in the WIDE encoding and only that one. A single reader carrying a
// modality flag would have to admit the union of both profiles for both
// corpora, which is exactly the fallback this module refuses to build: "there
// are exactly TWO admitted vectors ... a file matching neither is refused by
// name". Two readers, each with its own pin, keeps every wall a wall.
//
// THE WALL IS TWO-WAY, AND IT IS TWO WALLS DEEP ON EACH SIDE.
//
//   MODALITY, at open, before a path to a payload is formed:
//     * `OptionPrintReader` refuses a corpus root carrying the `RUTW`
//       component (`kDeferredPrintModality`);
//     * `RutwPrintReader` refuses a corpus root that does NOT carry it. A RUTW
//       reader pointed at the IWM corpus is a configuration error, and this
//       program says so instead of reading a different instrument's tape into
//       an instrument-labelled stream.
//   PROFILE, at open, before a payload byte is read:
//     * `OptionPrintReader` pins the two IWM vectors (compact and wide),
//       chosen from the file's own `expiration` leaf;
//     * `RutwPrintReader` pins the ONE wide vector. IWM-compact bytes handed
//       to it fail on `expiration` (a DATE ordinal against a UTF-8 pin) and
//       are refused BY NAME.
//
// THE REGISTRY-SESSION WALL IS INHERITED, NOT REBUILT. `open` takes a
// `qr::DayScope`, which only `DayScope::admit` mints, so the 125..749 wall
// fires before any path exists — the same wall B1-B4 stand behind. RUTW adds no
// second calendar: W2.12's "registry-session wall" IS this one.
//
// SAME LAWS, ONE IMPLEMENTATION. Every row law — the null-instant admission
// rule, the monotonicity refusal, the half-open RTH window, the per-slot
// decode, u6 normalization, the equal-time group machine, the census — lives in
// `OptionPrintTape` (qr_sources/option_prints.hpp) and is DRIVEN here. B5's
// rows are `OptionPrintRow`s: the appendix says the profile and the laws are
// the same, so the emitted shape is the same too.
#ifndef QR_SOURCES_RUTW_PRINTS_HPP
#define QR_SOURCES_RUTW_PRINTS_HPP

#include <filesystem>
#include <utility>

#include "qr_registry/day_scope.hpp"
#include "qr_sources/option_prints.hpp"
#include "qr_sources/session_source.hpp"
#include "qr_sources/stream_spec.hpp"

namespace qr::sources {

/// Whether `corpus_root` names the RUTW modality — i.e. carries the `RUTW`
/// path component. The predicate BOTH print readers stand on, from opposite
/// sides, exposed so a fixture can assert the two walls are the same test.
[[nodiscard]] bool is_rutw_corpus_root(const std::filesystem::path& corpus_root) noexcept;

/// Streaming RUTW option-print reader for one admitted session.
class RutwPrintReader {
 public:
  using Group = OptionPrintTape::Group;

  RutwPrintReader(const RutwPrintReader&) = delete;
  RutwPrintReader& operator=(const RutwPrintReader&) = delete;
  RutwPrintReader(RutwPrintReader&&) = default;
  RutwPrintReader& operator=(RutwPrintReader&&) = default;
  ~RutwPrintReader() = default;

  /// Opens `<corpus_root>/<YYYY>/<day>.parquet` for an ADMITTED session, pinned
  /// to the RUTW modality and to the wide profile.
  [[nodiscard]] static FileExpected<RutwPrintReader> open(
      const DayScope& scope, const std::filesystem::path& corpus_root);

  [[nodiscard]] FileExpected<bool> next_group(Group& out) {
    return tape_.next_group(source_, out);
  }

  [[nodiscard]] std::int64_t rth_rows() const noexcept { return tape_.rth_rows(); }
  [[nodiscard]] std::int64_t group_count() const noexcept { return tape_.group_count(); }
  [[nodiscard]] std::int64_t skipped_null_rows() const noexcept {
    return tape_.skipped_null_rows();
  }
  [[nodiscard]] const OptionPrintCensus& census() const noexcept { return tape_.census(); }
  [[nodiscard]] std::int64_t decoded_values() const noexcept { return source_.decoded_values(); }
  [[nodiscard]] const std::filesystem::path& path() const noexcept { return source_.path(); }
  [[nodiscard]] const SessionSource& source() const noexcept { return source_; }

 private:
  RutwPrintReader(SessionSource source, std::string day)
      : source_(std::move(source)), tape_(std::move(day)) {}

  SessionSource source_;
  OptionPrintTape tape_;
};

}  // namespace qr::sources

#endif  // QR_SOURCES_RUTW_PRINTS_HPP
