// qr_m25/npy.hpp — the minimal .npy READER the M2.5 machinery needs.
//
// WHY IT EXISTS. qr_emit owns the WRITER (`qr_emit/npy_writer.hpp`) because the
// DecisionTape is written from C++; nothing in the tree ever had to read one
// back, because the trainer is Python (`engine/cpp/python/decision_tape_loader.py`).
// M2.5 runs the FROZEN replay kernel over the truth leaves, so it is the first
// C++ consumer of a published tape and needs the other half.
//
// WHAT IT ENFORCES (the same three laws the Python loader enforces, so the two
// readers cannot disagree about what a tape says):
//   1. the manifest is the authority — dtype, shape and row count are checked
//      against the manifest row, and a leaf whose own header disagrees is a
//      typed refusal, never a reshape and never a cast;
//   2. the four APPENDIX C4 element types and nothing else (`<i8`, `<i4`,
//      `<f4`, `|u1`); a foreign dtype is a refusal;
//   3. C-order only. `fortran_order: True` is a refusal rather than a silent
//      transpose.
//
// It maps the file (read-only, MAP_PRIVATE) instead of copying it: a TRAIN fold
// is 396 sessions x 2 sides and the feature leaves the twin machinery reads are
// 11 MB each, so a copy per leaf would be gigabytes of needless traffic.
#ifndef QR_M25_NPY_HPP
#define QR_M25_NPY_HPP

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <span>
#include <string>
#include <variant>
#include <vector>

#include "qr_core/refusal.hpp"

namespace qr::m25 {

using qr::Expected;
using qr::Refusal;
using qr::RefusalCode;

/// "Succeeded, or a typed refusal" — the same alias qr_emit declares, redeclared
/// here so qr_m25 does not link the emit library just to name a return type.
using Status = Expected<std::monostate, Refusal>;

/// The success value of a `Status`.
[[nodiscard]] inline Status ok() noexcept { return Status(std::monostate{}); }

/// The four APPENDIX C4 element types.
enum class NpyDtype : std::uint8_t { I8, I4, F4, U1 };

[[nodiscard]] const char* npy_dtype_name(NpyDtype dtype) noexcept;

/// A read-only memory map of one .npy leaf, plus its parsed header.
class NpyArray {
 public:
  NpyArray() = default;
  NpyArray(const NpyArray&) = delete;
  NpyArray& operator=(const NpyArray&) = delete;
  NpyArray(NpyArray&& other) noexcept;
  NpyArray& operator=(NpyArray&& other) noexcept;
  ~NpyArray();

  /// Map `path` and parse its header. Refuses IO on any open/stat/mmap failure,
  /// SCHEMA_MISMATCH on a header this reader does not accept, and
  /// CONTENT_MISMATCH when the file is not exactly the size its own header
  /// implies (a truncated or over-long leaf is never read partially).
  [[nodiscard]] static Expected<NpyArray, Refusal> open(const std::filesystem::path& path);

  [[nodiscard]] NpyDtype dtype() const noexcept { return dtype_; }
  [[nodiscard]] const std::vector<std::int64_t>& shape() const noexcept { return shape_; }
  [[nodiscard]] std::int64_t rows() const noexcept { return shape_.empty() ? 0 : shape_[0]; }
  [[nodiscard]] std::int64_t element_count() const noexcept { return element_count_; }

  /// Typed views. Each refuses (fail-fast) when the element type is not the one
  /// asked for: a leaf read at the wrong width is an economic error, not a
  /// recoverable case.
  [[nodiscard]] std::span<const std::int64_t> i8() const;
  [[nodiscard]] std::span<const std::int32_t> i4() const;
  [[nodiscard]] std::span<const float> f4() const;
  [[nodiscard]] std::span<const std::uint8_t> u1() const;

 private:
  void* map_ = nullptr;
  std::size_t map_bytes_ = 0;
  std::size_t data_offset_ = 0;
  NpyDtype dtype_ = NpyDtype::U1;
  std::vector<std::int64_t> shape_;
  std::int64_t element_count_ = 0;
};

/// One manifest row of a published DecisionTape shard.
struct ManifestLeaf {
  std::string rel_path;  ///< e.g. "truth/menu_net_cent.npy"
  std::string section;   ///< "features" | "truth"
  std::string name;      ///< "menu_net_cent.npy"
  std::string dtype;     ///< the manifest's dtype token
  std::vector<std::int64_t> shape;
  std::int64_t rows = 0;
  std::string sha256;
};

/// A parsed `manifest.tsv` (schema `qr_emit_manifest_v1`).
struct TapeManifest {
  std::string build_id;
  std::int64_t session_ordinal = 0;
  std::string side;  ///< "LONG" | "SHORT"
  std::string card_sha256;
  std::vector<ManifestLeaf> leaves;

  [[nodiscard]] const ManifestLeaf* find(const std::string& rel_path) const noexcept;
};

/// Parse the shard's manifest. Refuses SCHEMA_MISMATCH on a foreign schema line.
[[nodiscard]] Expected<TapeManifest, Refusal> read_manifest(const std::filesystem::path& shard_dir);

/// Open `shard_dir/rel_path` and check it against the manifest row of the same
/// path: dtype token, shape and row count must all agree. This is the ONLY
/// sanctioned way to read a tape leaf.
[[nodiscard]] Expected<NpyArray, Refusal> open_leaf(const std::filesystem::path& shard_dir,
                                                    const TapeManifest& manifest,
                                                    const std::string& rel_path);

}  // namespace qr::m25

#endif  // QR_M25_NPY_HPP
