// qr_parquet/column.hpp — decoded column output: values + validity bitmap.
//
// SPEC: design/DESIGN_SUBSTRATE.md M1 qr_parquet bullet — "def-levels->validity
// bitmap, flat INT32/INT64/DOUBLE/BYTE_ARRAY leaves".
//
// LAYOUT LAW: every value array is ROW-LENGTH, not dense. Row i of the column
// chunk is element i of the array whether or not it is null; a null row holds a
// zero (an empty slice for BYTE_ARRAY) and its validity bit is 0. Consumers
// index by row and never carry a prefix sum. This is the same shape the frozen
// Rust reader presents (`is_null(row)` / `value(row)`, select_v2/src/sources/mod.rs)
// so the WP9 differential compares like with like.
#ifndef QR_PARQUET_COLUMN_HPP
#define QR_PARQUET_COLUMN_HPP

#include <cstddef>
#include <cstdint>
#include <string_view>
#include <vector>

namespace qr::parquet {

/// A presence bitmap: bit i is 1 when row i carries a value.
class Bitmap {
 public:
  void reset(std::size_t bits) {
    bits_ = bits;
    words_.assign((bits + 63) / 64, 0);
  }
  void set(std::size_t index) noexcept {
    words_[index >> 6U] |= (std::uint64_t{1} << (index & 63U));
  }
  /// Marks [begin, end) present. The all-present fast path for pages with no
  /// nulls, which is the common case in this corpus.
  void set_range(std::size_t begin, std::size_t end) noexcept;
  [[nodiscard]] bool get(std::size_t index) const noexcept {
    return ((words_[index >> 6U] >> (index & 63U)) & 1U) != 0;
  }
  [[nodiscard]] std::size_t size() const noexcept { return bits_; }
  [[nodiscard]] const std::vector<std::uint64_t>& words() const noexcept { return words_; }

 private:
  std::vector<std::uint64_t> words_;
  std::size_t bits_ = 0;
};

/// The pinned leaf physical types, after the dialect gate has accepted them.
enum class LeafType : std::uint8_t { INT32, INT64, DOUBLE, BYTE_ARRAY };

/// The pinned converted types.
enum class LeafConverted : std::uint8_t { NONE, UTF8, DATE, UINT_32, INT_8 };

[[nodiscard]] const char* leaf_type_name(LeafType type) noexcept;
[[nodiscard]] const char* leaf_converted_name(LeafConverted converted) noexcept;

/// One decoded column chunk (one column of one row group).
struct ColumnData {
  LeafType type = LeafType::INT64;
  std::int64_t num_rows = 0;
  std::int64_t null_count = 0;

  std::vector<std::int32_t> i32;
  std::vector<std::int64_t> i64;
  std::vector<double> f64;
  /// BYTE_ARRAY: `offsets` has num_rows + 1 entries into `bytes`.
  std::vector<std::uint32_t> offsets;
  std::vector<std::uint8_t> bytes;

  Bitmap validity;

  /// Sizes every buffer for `rows` of `leaf_type` and clears the validity bits.
  /// Capacity is retained across calls so a per-row-group loop stops allocating
  /// after the first group.
  void reset(LeafType leaf_type, std::int64_t rows);

  [[nodiscard]] bool is_null(std::int64_t row) const noexcept {
    return !validity.get(static_cast<std::size_t>(row));
  }
  /// BYTE_ARRAY accessor; the view points into `bytes` and dies with it.
  [[nodiscard]] std::string_view byte_array(std::int64_t row) const noexcept;
};

/// THE COMMITTED DIGEST RULE (mirrored bit-for-bit by the derivation script
/// engine/cpp/tests/fixtures/make_parquet_fixtures.py::column_digest, and the
/// rule WP9's differential must reproduce on the Rust side):
///
///   INT32 / INT64 : wrapping uint64 sum of the non-null values (each widened
///                   to int64 first, then added modulo 2^64);
///   DOUBLE        : bitwise XOR of the IEEE-754 bit patterns of the non-nulls;
///   BYTE_ARRAY    : FNV-1a 64 over, per non-null value in row order, the
///                   4-byte little-endian length followed by the value bytes.
///
/// Nulls contribute nothing. The result is returned as raw 64 bits; report it
/// as the two's-complement int64 with the same bits.
[[nodiscard]] std::uint64_t column_digest(const ColumnData& column) noexcept;

/// Serializes a decoded column into a byte stream, for two-run byte-identity
/// checks. Field-by-field, little-endian, no padding, no pointers.
void append_serialized(const ColumnData& column, std::vector<std::uint8_t>& out);

}  // namespace qr::parquet

#endif  // QR_PARQUET_COLUMN_HPP
