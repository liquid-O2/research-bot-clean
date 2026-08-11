// qr_emit/npy_writer.hpp — the .npy v1.0 leaf writer.
//
// SPEC: FINAL_PLAN.md APPENDIX C4 (DecisionTape) + design/DESIGN_SUBSTRATE.md
// M1 `qr_emit` bullet ("qr_emit (.npy + manifest; features/truth process
// separation per App. C4)").
//
// FORMAT RULING (frozen, quoted from the WP10 brief):
//   ".npy v1.0 (\x93NUMPY magic, dict header padded to 64B, C-order
//    little-endian), writer ~80 LOC C++; deterministic field-by-field writes;
//    sorted file order; no struct memcpy."
//
// The prologue this writer emits is byte-for-byte what numpy's own
// `numpy.lib.format.write_array_header_1_0` emits, which is why
// tests/fixtures/npy/*.npy (produced by numpy 2.1.2) can be compared against
// our output byte for byte instead of merely "parsed successfully":
//
//   6 bytes  \x93NUMPY
//   1 byte   major version 1
//   1 byte   minor version 0
//   2 bytes  HEADER_LEN, little-endian uint16
//   HEADER_LEN bytes: the ASCII dict, space-padded, '\n'-terminated, chosen so
//                     that 10 + HEADER_LEN is a multiple of 64 (numpy pads by a
//                     full 64 bytes when the unpadded length already aligns —
//                     reproduced exactly).
//
// The dtypes are exactly the four APPENDIX C4 names — i8 (int64), i4 (int32),
// f4 (float32), u1 (uint8) — and shapes are 1..3 dimensions, which covers every
// leaf C4 declares ([N,3,60], [G,69|65|89], [G], [N,2], [N], [N,120,2], [S,4],
// [N,32], [N,64,24], [N,4], [N,7]).
#ifndef QR_EMIT_NPY_WRITER_HPP
#define QR_EMIT_NPY_WRITER_HPP

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <span>
#include <string>
#include <string_view>
#include <variant>
#include <vector>

#include "qr_core/refusal.hpp"

namespace qr::emit {

/// A refusal-or-nothing result. Nothing here throws and nothing here recovers
/// by substituting a value (FINAL_PLAN section 6 arithmetic law).
using Status = Expected<std::monostate, Refusal>;

[[nodiscard]] inline Status ok_status() noexcept { return Status(std::monostate{}); }

/// The four APPENDIX C4 element types. The enumerator names are the C4 names.
enum class NpyDtype : std::uint8_t { I8, I4, F4, U1 };

inline constexpr std::size_t kNpyDtypeCount = 4;

/// numpy descr string: "<i8", "<i4", "<f4", "|u1" (u1 has no byte order).
[[nodiscard]] const char* npy_dtype_descr(NpyDtype dtype) noexcept;

/// Element size in bytes: 8, 4, 4, 1.
[[nodiscard]] std::size_t npy_dtype_size(NpyDtype dtype) noexcept;

/// Inverse of npy_dtype_descr; refuses anything outside the four pinned names.
[[nodiscard]] Expected<NpyDtype, Refusal> npy_dtype_from_descr(std::string_view descr);

inline constexpr std::size_t kNpyMaxDims = 3;
inline constexpr std::size_t kNpyHeaderAlignment = 64;
inline constexpr std::size_t kNpyPrologueFixedBytes = 10;  // magic + version + HEADER_LEN

/// The complete .npy prologue (magic .. terminating '\n') for `dtype` and
/// `shape`. Refuses: 0 or more than 3 dimensions, a negative dimension, an
/// element count that overflows int64, and a header that would not fit the
/// v1.0 uint16 HEADER_LEN field.
[[nodiscard]] Expected<std::string, Refusal> npy_header_bytes(NpyDtype dtype,
                                                              std::span<const std::int64_t> shape);

/// Product of `shape`, refusing on overflow. A zero dimension gives 0.
[[nodiscard]] Expected<std::int64_t, Refusal> npy_element_count(std::span<const std::int64_t> shape);

/// What a finished leaf is: everything the manifest needs about it.
struct NpyLeafReceipt {
  std::string rel_path;               ///< e.g. "features/direct_raw.npy"
  NpyDtype dtype = NpyDtype::F4;      ///< manifest `dtype` column, as a descr
  std::vector<std::int64_t> shape;    ///< manifest `shape` column, comma-joined
  std::int64_t rows = 0;              ///< manifest `rows` column = shape[0]
  std::int64_t file_bytes = 0;        ///< prologue + payload
  std::string sha256;                 ///< of the WHOLE file, prologue included
};

/// Streams one .npy leaf to disk: prologue on create, payload by append, digest
/// and fsync on finish. The file is opened O_CREAT|O_EXCL — a leaf is never
/// silently overwritten.
///
/// Move-only. Destroying an unfinished writer closes the descriptor and leaves
/// the partial file where it is: the stage directory is the only place partial
/// files ever exist, and the no-replace publish never promotes one.
class NpyWriter {
 public:
  NpyWriter(const NpyWriter&) = delete;
  NpyWriter& operator=(const NpyWriter&) = delete;
  NpyWriter(NpyWriter&& other) noexcept;
  NpyWriter& operator=(NpyWriter&& other) noexcept;
  ~NpyWriter();

  [[nodiscard]] static Expected<NpyWriter, Refusal> create(const std::filesystem::path& path,
                                                           std::string rel_path, NpyDtype dtype,
                                                           std::span<const std::int64_t> shape);

  /// Appends elements in C order. The span's element type must match the
  /// declared dtype exactly — a mismatch is a refusal, never a reinterpretation.
  [[nodiscard]] Status append(std::span<const std::int64_t> values);
  [[nodiscard]] Status append(std::span<const std::int32_t> values);
  [[nodiscard]] Status append(std::span<const float> values);
  [[nodiscard]] Status append(std::span<const std::uint8_t> values);

  /// Flushes, fsyncs, closes, and returns the receipt. Refuses when the number
  /// of appended elements is not exactly the declared element count — a short
  /// or long leaf is a refusal, not a padded array.
  [[nodiscard]] Expected<NpyLeafReceipt, Refusal> finish();

  [[nodiscard]] std::int64_t elements_written() const noexcept { return elements_written_; }
  [[nodiscard]] std::int64_t elements_declared() const noexcept { return elements_declared_; }

 private:
  NpyWriter() = default;
  [[nodiscard]] Status write_all(const std::uint8_t* data, std::size_t bytes);
  [[nodiscard]] Status append_bytes(const void* first, std::size_t count, NpyDtype dtype);
  void close_descriptor() noexcept;

  int fd_ = -1;
  void* digest_ = nullptr;  // EVP_MD_CTX*, opaque here so no header leaks OpenSSL
  std::filesystem::path path_;
  std::string rel_path_;
  NpyDtype dtype_ = NpyDtype::F4;
  std::vector<std::int64_t> shape_;
  std::int64_t elements_declared_ = 0;
  std::int64_t elements_written_ = 0;
  std::int64_t file_bytes_ = 0;
  bool finished_ = false;
};

}  // namespace qr::emit

#endif  // QR_EMIT_NPY_WRITER_HPP
