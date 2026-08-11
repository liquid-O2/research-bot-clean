// qr_parquet/thrift.hpp — the thrift compact-protocol reader for parquet footers
// and page headers.
//
// SPEC: design/DESIGN_SUBSTRATE.md M1 qr_parquet bullet ("thrift-compact
// footer"). This is a direct port of the WP0 footer parser
// engine/cpp/tools/qr_dialect_census.py (class Reader / fields / skip), which
// already read all 8,726 corpus footers; the struct layout it walks is the same
// one this reader walks.
//
// NO EXCEPTIONS. The python original raised ThriftError; here every call
// returns bool and the first failure latches a static reason on the reader.
// Once `ok()` is false it stays false, so a caller may chain reads and check
// once at the end without ever acting on garbage.
//
// EVERY read is bounds checked against the buffer end. A truncated footer, a
// varint running off the end, a length prefix larger than the buffer: all are
// "not ok", never a read past the mapping.
#ifndef QR_PARQUET_THRIFT_HPP
#define QR_PARQUET_THRIFT_HPP

#include <cstddef>
#include <cstdint>
#include <string>

namespace qr::parquet::thrift {

// Thrift compact element types.
inline constexpr std::uint8_t kStop = 0;
inline constexpr std::uint8_t kBoolTrue = 1;
inline constexpr std::uint8_t kBoolFalse = 2;
inline constexpr std::uint8_t kByte = 3;
inline constexpr std::uint8_t kI16 = 4;
inline constexpr std::uint8_t kI32 = 5;
inline constexpr std::uint8_t kI64 = 6;
inline constexpr std::uint8_t kDouble = 7;
inline constexpr std::uint8_t kBinary = 8;
inline constexpr std::uint8_t kList = 9;
inline constexpr std::uint8_t kSet = 10;
inline constexpr std::uint8_t kMap = 11;
inline constexpr std::uint8_t kStruct = 12;

/// Hard ceiling on nested skipping. Depth is a property of the *input*, so a
/// hostile footer may not be allowed to drive the C++ stack.
inline constexpr int kMaxSkipDepth = 32;

class Reader {
 public:
  Reader(const std::uint8_t* data, std::size_t size) noexcept : data_(data), size_(size) {}

  [[nodiscard]] bool ok() const noexcept { return error_ == nullptr; }
  [[nodiscard]] const char* error() const noexcept {
    return error_ == nullptr ? "" : error_;
  }
  [[nodiscard]] std::size_t position() const noexcept { return pos_; }
  [[nodiscard]] std::size_t size() const noexcept { return size_; }

  /// Latch a failure. The FIRST reason wins: it is the one that explains the
  /// rest.
  void fail(const char* reason) noexcept {
    if (error_ == nullptr) {
      error_ = reason;
    }
  }

  [[nodiscard]] bool byte(std::uint8_t& out) noexcept;
  [[nodiscard]] bool varint(std::uint64_t& out) noexcept;
  [[nodiscard]] bool zigzag(std::int64_t& out) noexcept;
  /// Borrows `n` bytes from the buffer without copying.
  [[nodiscard]] bool take(std::size_t n, const std::uint8_t*& out) noexcept;
  [[nodiscard]] bool binary(std::string& out);
  [[nodiscard]] bool skip_binary() noexcept;
  [[nodiscard]] bool list_header(std::uint32_t& count, std::uint8_t& element) noexcept;
  /// Reads a BYTE/I16/I32/I64 field body as an i64.
  [[nodiscard]] bool integer(std::uint8_t field_type, std::int64_t& out) noexcept;
  /// Skips one value of the given element type (recursively for containers).
  [[nodiscard]] bool skip(std::uint8_t field_type, int depth = 0);

  // The field-id delta chain is per struct; StructScope saves and restores it.
  [[nodiscard]] std::int16_t last_field_id() const noexcept { return last_field_id_; }
  void set_last_field_id(std::int16_t value) noexcept { last_field_id_ = value; }

 private:
  const std::uint8_t* data_;
  std::size_t size_;
  std::size_t pos_ = 0;
  std::int16_t last_field_id_ = 0;
  const char* error_ = nullptr;
};

/// Walks the fields of ONE struct. Construct it, loop on `next()`, and the
/// struct's STOP byte is consumed for you; the enclosing struct's field-id
/// chain is restored on destruction.
///
///   thrift::StructScope scope(reader);
///   std::int16_t fid; std::uint8_t ftype;
///   while (scope.next(fid, ftype)) { ... }
///   if (!reader.ok()) { ...refuse... }
class StructScope {
 public:
  explicit StructScope(Reader& reader) noexcept
      : reader_(reader), saved_(reader.last_field_id()) {
    reader_.set_last_field_id(0);
  }
  StructScope(const StructScope&) = delete;
  StructScope& operator=(const StructScope&) = delete;
  ~StructScope() { reader_.set_last_field_id(saved_); }

  /// True while another field was read; false at STOP or on failure.
  [[nodiscard]] bool next(std::int16_t& field_id, std::uint8_t& field_type) noexcept;

 private:
  Reader& reader_;
  std::int16_t saved_;
};

}  // namespace qr::parquet::thrift

#endif  // QR_PARQUET_THRIFT_HPP
