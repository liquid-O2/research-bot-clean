// qr_dbn/zstd_stream.hpp — streaming zstd decompression over a payload file.
//
// SPEC: design/PORT_M1_SPEC.md §1.1 ("zstd streaming (libzstd)") and
// design/PORT_M0_CENSUS_SPEC.md §0 (the proven decode pattern: a zstd stream
// reader feeding fixed-size chunks into the DBN record decoder).
//
// LAW: libzstd does the decompression. Nothing here reimplements the format.
// Every failure is a typed Refusal — a truncated or corrupt frame is never
// silently treated as a clean end of stream, because a short read that looks
// like EOF would turn a damaged file into a shorter, plausible-looking day.
#ifndef QR_DBN_ZSTD_STREAM_HPP
#define QR_DBN_ZSTD_STREAM_HPP

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

#include "qr_core/refusal.hpp"

namespace qr::dbn {

/// Sequential reader over a `.zst` file, yielding the decompressed byte stream.
/// Handles multi-frame files (libzstd resets between concatenated frames).
class ZstdStream {
 public:
  ZstdStream() = default;
  ~ZstdStream();

  ZstdStream(const ZstdStream&) = delete;
  ZstdStream& operator=(const ZstdStream&) = delete;
  ZstdStream(ZstdStream&& other) noexcept;
  ZstdStream& operator=(ZstdStream&& other) noexcept;

  /// Open `path` for streaming decompression.
  [[nodiscard]] Expected<std::monostate, Refusal> open(const std::string& path);

  /// Fill up to `n` bytes into `dst`. Returns the number of bytes produced,
  /// which is short ONLY at true end of stream. A frame that ends mid-payload
  /// is DECODE_FAILED, never a short read.
  [[nodiscard]] Expected<std::size_t, Refusal> read(void* dst, std::size_t n);

  /// True once the underlying stream is exhausted at a clean frame boundary.
  [[nodiscard]] bool exhausted() const noexcept { return file_eof_ && in_pos_ >= in_size_; }

 private:
  void reset() noexcept;

  std::FILE* fh_ = nullptr;
  void* dstream_ = nullptr;              // ZSTD_DStream*, opaque here
  std::vector<std::uint8_t> in_buf_;
  std::size_t in_pos_ = 0;
  std::size_t in_size_ = 0;
  bool file_eof_ = false;
  bool frame_open_ = false;              // mid-frame: EOF here is truncation
  std::string path_;
};

}  // namespace qr::dbn

#endif  // QR_DBN_ZSTD_STREAM_HPP
