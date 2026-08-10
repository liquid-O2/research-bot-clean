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

// --- the pinned set --------------------------------------------------------

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
