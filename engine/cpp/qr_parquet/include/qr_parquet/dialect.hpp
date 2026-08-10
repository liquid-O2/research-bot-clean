// qr_parquet/dialect.hpp — the pinned parquet dialect and the typed FILE refusal.
//
// SPEC (design/DESIGN_SUBSTRATE.md, M1, qr_parquet bullet):
//   "dialect-pinned custom decoder, primary: thrift-compact footer, ZSTD pages
//    into reused arena, PLAIN/RLE/RLE_DICTIONARY, def-levels->validity, flat
//    INT32/INT64/DOUBLE/BYTE_ARRAY; ANY tuple outside the census = typed file
//    refusal"
//
// MEASURED AUTHORITY (the census this file is pinned to; hard-refuse outside it):
//   /workspace/artifacts/cache/cpp/dialect_census.tsv — 8,726 corpus files,
//   every row exhibiting exactly
//     codec           ZSTD
//     encoding_set    subsets of {PLAIN, RLE, RLE_DICTIONARY}
//     physical_type   {BYTE_ARRAY, DOUBLE, INT32, INT64}
//     converted_type  {DATE, INT_8, NONE, UINT_32, UTF8}
//     leaves          flat (no nesting)
//     timestamp stats always present
//
// FAIL-CLOSED LAW. Nothing here degrades. A file carrying any other codec,
// encoding, physical type, converted type or repetition is REFUSED by name and
// the payload is never touched. There is no "best effort" path, no fallback
// decoder, and no silent widening: adding a tuple to the pinned set is a source
// change that has to pass the same review as any other.
#ifndef QR_PARQUET_DIALECT_HPP
#define QR_PARQUET_DIALECT_HPP

#include <cstdint>
#include <string>
#include <utility>

#include "qr_core/refusal.hpp"

namespace qr::parquet {

// --- parquet.thrift enum values (raw, so an unpinned value can be NAMED) ----
// Type
inline constexpr std::int32_t kTypeBoolean = 0;
inline constexpr std::int32_t kTypeInt32 = 1;
inline constexpr std::int32_t kTypeInt64 = 2;
inline constexpr std::int32_t kTypeInt96 = 3;
inline constexpr std::int32_t kTypeFloat = 4;
inline constexpr std::int32_t kTypeDouble = 5;
inline constexpr std::int32_t kTypeByteArray = 6;
inline constexpr std::int32_t kTypeFixedLenByteArray = 7;

// ConvertedType. -1 is this decoder's spelling of "the field is absent", which
// the census reports as NONE.
inline constexpr std::int32_t kConvertedNone = -1;
inline constexpr std::int32_t kConvertedUtf8 = 0;
inline constexpr std::int32_t kConvertedDate = 6;
inline constexpr std::int32_t kConvertedUint32 = 13;
inline constexpr std::int32_t kConvertedInt8 = 15;

// FieldRepetitionType
inline constexpr std::int32_t kRepetitionRequired = 0;
inline constexpr std::int32_t kRepetitionOptional = 1;
inline constexpr std::int32_t kRepetitionRepeated = 2;

// CompressionCodec
inline constexpr std::int32_t kCodecUncompressed = 0;
inline constexpr std::int32_t kCodecSnappy = 1;
inline constexpr std::int32_t kCodecZstd = 6;

// Encoding
inline constexpr std::int32_t kEncodingPlain = 0;
inline constexpr std::int32_t kEncodingPlainDictionary = 2;
inline constexpr std::int32_t kEncodingRle = 3;
inline constexpr std::int32_t kEncodingDeltaBinaryPacked = 5;
inline constexpr std::int32_t kEncodingRleDictionary = 8;

// PageType
inline constexpr std::int32_t kPageDataV1 = 0;
inline constexpr std::int32_t kPageIndex = 1;
inline constexpr std::int32_t kPageDictionary = 2;
inline constexpr std::int32_t kPageDataV2 = 3;

// --- the pinned sets, ONE PER PRODUCER FAMILY -------------------------------
//
// ORCHESTRATOR RULING CC-003 (2026-08-10): census-derived walls are PER
// PRODUCER. The token corpus and the derived publications are written by
// different producers with different measured dialects, so each family carries
// its own pin and a file is gated against the profile its reader declares.
// Widening one pin to cover the other would dilute the corpus wall — the whole
// point of a measured authority is that it describes what was actually seen.
//
//   CORPUS      — /workspace/data/tokens/**, measured by the WP0 whole-corpus
//                 census (dialect_census.tsv, 8,726 files): ZSTD, encodings
//                 within {PLAIN, RLE, RLE_DICTIONARY}, physical within
//                 {INT32, INT64, DOUBLE, BYTE_ARRAY}, converted within
//                 {NONE, UTF8, DATE, UINT_32, INT_8}, OPTIONAL leaves only.
//                 THIS PIN IS BYTE-UNCHANGED by CC-003.
//   PUBLICATION — the derived run publications (the V4 task card's
//                 truth_relation_projection and candidate_action_registry),
//                 measured by tests/fixtures/publication_repetition_census.tsv
//                 and tests/fixtures/publication_dialect_census.tsv: ZSTD,
//                 encodings within {PLAIN, RLE, RLE_DICTIONARY}, BYTE_ARRAY
//                 leaves only, UTF8 only, REQUIRED leaves only, flat.
//                 One row group per registered session; that LAYOUT pin lives
//                 with the reader that depends on it
//                 (qr_candidates::RowGroupTable's `expected_row_groups`),
//                 because it is a layout fact, not an encoding tuple.
//
// Both profiles are fail-closed in the same way: anything outside the profile's
// measured set is a typed refusal naming the file, the column and the offending
// value. Neither profile is a superset of the other — a corpus file is refused
// by the PUBLICATION profile exactly as loudly as the reverse.
enum class DialectProfile : std::uint8_t { CORPUS = 0, PUBLICATION = 1 };

/// Screaming-snake name of a profile, for refusal text.
[[nodiscard]] const char* dialect_profile_name(DialectProfile profile) noexcept;

/// ZSTD and nothing else (census: every one of the 8,726 files).
[[nodiscard]] constexpr bool is_pinned_codec(std::int32_t codec) noexcept {
  return codec == kCodecZstd;
}

/// PLAIN, RLE, RLE_DICTIONARY and nothing else. PLAIN_DICTIONARY (the pre-2.0
/// spelling) is NOT pinned: the census never observed it.
[[nodiscard]] constexpr bool is_pinned_encoding(std::int32_t encoding) noexcept {
  return encoding == kEncodingPlain || encoding == kEncodingRle ||
         encoding == kEncodingRleDictionary;
}

/// INT32, INT64, DOUBLE, BYTE_ARRAY and nothing else.
[[nodiscard]] constexpr bool is_pinned_physical(std::int32_t type) noexcept {
  return type == kTypeInt32 || type == kTypeInt64 || type == kTypeDouble ||
         type == kTypeByteArray;
}

/// NONE, UTF8, DATE, UINT_32, INT_8 and nothing else.
[[nodiscard]] constexpr bool is_pinned_converted(std::int32_t converted) noexcept {
  return converted == kConvertedNone || converted == kConvertedUtf8 ||
         converted == kConvertedDate || converted == kConvertedUint32 ||
         converted == kConvertedInt8;
}

/// OPTIONAL and nothing else.
///
/// ORCHESTRATOR RULING (2026-08-10): census-pinned fail-closed. The measured
/// authority never observed a REQUIRED leaf, so REQUIRED is refused exactly
/// like REPEATED — a future REQUIRED file must produce a LOUD REFUSAL and a
/// change-control census update, never a silent widening here. Nesting is
/// refused separately (a leaf may not have children, and no schema element
/// below the root may have children).
[[nodiscard]] constexpr bool is_pinned_repetition(std::int32_t repetition) noexcept {
  return repetition == kRepetitionOptional;
}

// --- the profile-aware gate ------------------------------------------------
//
// EVERY PUBLICATION PREDICATE IS WRITTEN OUT, and every CORPUS predicate
// DELEGATES to the single-argument function above. The delegation is
// deliberate: the corpus pin has exactly one definition, so a mutation of it
// still reaches `File::open` through this path and the WP3 red-ledger entries
// that prove the corpus wall (M201, M205) keep reproducing unchanged.

/// PUBLICATION: ZSTD, same as the corpus.
[[nodiscard]] constexpr bool is_pinned_codec(std::int32_t codec, DialectProfile profile) noexcept {
  return profile == DialectProfile::PUBLICATION ? codec == kCodecZstd : is_pinned_codec(codec);
}

/// PUBLICATION: PLAIN, RLE, RLE_DICTIONARY — the measured encoding set.
[[nodiscard]] constexpr bool is_pinned_encoding(std::int32_t encoding,
                                                DialectProfile profile) noexcept {
  return profile == DialectProfile::PUBLICATION
             ? (encoding == kEncodingPlain || encoding == kEncodingRle ||
                encoding == kEncodingRleDictionary)
             : is_pinned_encoding(encoding);
}

/// PUBLICATION: BYTE_ARRAY and nothing else. Every leaf of both bound
/// publications is a UTF8 string; an INT32/INT64/DOUBLE leaf has never been
/// observed in this family and is refused rather than silently admitted.
[[nodiscard]] constexpr bool is_pinned_physical(std::int32_t type,
                                                DialectProfile profile) noexcept {
  return profile == DialectProfile::PUBLICATION ? type == kTypeByteArray : is_pinned_physical(type);
}

/// PUBLICATION: UTF8 and nothing else (not even NONE).
[[nodiscard]] constexpr bool is_pinned_converted(std::int32_t converted,
                                                 DialectProfile profile) noexcept {
  return profile == DialectProfile::PUBLICATION ? converted == kConvertedUtf8
                                                : is_pinned_converted(converted);
}

/// PUBLICATION: REQUIRED and nothing else — the mirror image of the corpus pin.
/// The publications carry no definition levels and no nulls at all; an OPTIONAL
/// leaf in this family is a producer change, and it must be as loud here as a
/// REQUIRED leaf is in the corpus family.
[[nodiscard]] constexpr bool is_pinned_repetition(std::int32_t repetition,
                                                  DialectProfile profile) noexcept {
  return profile == DialectProfile::PUBLICATION ? repetition == kRepetitionRequired
                                                : is_pinned_repetition(repetition);
}

// The PUBLICATION set, asserted at compile time. Only the publication branch is
// asserted here, and deliberately so: the corpus branch DELEGATES to the single
// pinned predicate above, and a compile-time assertion about it would turn every
// corpus-wall mutation into a BUILD failure instead of a test failure — which
// would silently destroy the red-ledger evidence for M201 and M205. The
// cross-profile behaviour is proven at RUN time instead, by
// qr_candidates/tests/test_rowgroup_table.cpp's DialectProfiles suite, where a
// mutant makes a test go red exactly as the red-ledger law requires.
static_assert(!is_pinned_repetition(kRepetitionOptional, DialectProfile::PUBLICATION));
static_assert(is_pinned_repetition(kRepetitionRequired, DialectProfile::PUBLICATION));
static_assert(!is_pinned_repetition(kRepetitionRepeated, DialectProfile::PUBLICATION));
static_assert(is_pinned_physical(kTypeByteArray, DialectProfile::PUBLICATION));
static_assert(!is_pinned_physical(kTypeInt64, DialectProfile::PUBLICATION));
static_assert(!is_pinned_physical(kTypeInt32, DialectProfile::PUBLICATION));
static_assert(!is_pinned_physical(kTypeDouble, DialectProfile::PUBLICATION));
static_assert(is_pinned_converted(kConvertedUtf8, DialectProfile::PUBLICATION));
static_assert(!is_pinned_converted(kConvertedNone, DialectProfile::PUBLICATION));
static_assert(is_pinned_codec(kCodecZstd, DialectProfile::PUBLICATION));
static_assert(!is_pinned_codec(kCodecSnappy, DialectProfile::PUBLICATION));
static_assert(is_pinned_encoding(kEncodingPlain, DialectProfile::PUBLICATION));
static_assert(!is_pinned_encoding(kEncodingPlainDictionary, DialectProfile::PUBLICATION));

/// Screaming-snake name of a raw enum value, or "UNKNOWN" when unpinned. Used
/// only to build refusal text, never to make a decision.
[[nodiscard]] const char* codec_name(std::int32_t codec) noexcept;
[[nodiscard]] const char* encoding_name(std::int32_t encoding) noexcept;
[[nodiscard]] const char* physical_name(std::int32_t type) noexcept;
[[nodiscard]] const char* converted_name(std::int32_t converted) noexcept;
[[nodiscard]] const char* repetition_name(std::int32_t repetition) noexcept;

// --- the typed FILE refusal ------------------------------------------------

/// A `qr::Refusal` that also NAMES THE FILE. `qr::Refusal` deliberately carries
/// only static strings so that the arithmetic fast path allocates nothing; a
/// parquet refusal must name the offending path, so it is wrapped here rather
/// than by widening the core type.
class FileRefusal {
 public:
  FileRefusal(Refusal refusal, std::string path, std::string detail = {}) noexcept
      : refusal_(refusal), path_(std::move(path)), detail_(std::move(detail)) {}

  [[nodiscard]] const Refusal& refusal() const noexcept { return refusal_; }
  [[nodiscard]] RefusalCode code() const noexcept { return refusal_.code(); }
  [[nodiscard]] const char* site() const noexcept { return refusal_.site(); }
  [[nodiscard]] std::int64_t context() const noexcept { return refusal_.context(); }
  [[nodiscard]] const std::string& path() const noexcept { return path_; }
  /// Extra dynamic text (the offending enum name, the column, ...) or empty.
  [[nodiscard]] const std::string& detail() const noexcept { return detail_; }

  /// One line: "<CODE> at <site>: <detail> [context=<n>] path=<path>".
  [[nodiscard]] std::string message() const;

 private:
  Refusal refusal_;
  std::string path_;
  std::string detail_;
};

/// Every qr_parquet entry point returns one of these.
template <class T>
using FileExpected = Expected<T, FileRefusal>;

/// Build a refused FileExpected without naming the value type twice.
template <class T>
[[nodiscard]] FileExpected<T> refuse_file(RefusalCode code, const char* site, const char* what,
                                          std::string path, std::string detail = {},
                                          std::int64_t context = 0) {
  return FileExpected<T>::refuse(
      FileRefusal(Refusal(code, site, what, context), std::move(path), std::move(detail)));
}

}  // namespace qr::parquet

#endif  // QR_PARQUET_DIALECT_HPP
