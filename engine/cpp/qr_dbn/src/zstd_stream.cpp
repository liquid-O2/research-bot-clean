#include "qr_dbn/zstd_stream.hpp"

#include <zstd.h>

#include <cstring>
#include <utility>

namespace qr::dbn {
namespace {

// 1 MiB compressed-side window. The decode pattern in PORT_M0_CENSUS_SPEC §0
// uses 4 MiB on the DECOMPRESSED side; this is the input side and only needs to
// keep libzstd fed.
constexpr std::size_t kInChunk = 1u << 20;

ZSTD_DStream* as_dstream(void* p) { return static_cast<ZSTD_DStream*>(p); }

}  // namespace

ZstdStream::~ZstdStream() { reset(); }

void ZstdStream::reset() noexcept {
  if (dstream_ != nullptr) {
    ZSTD_freeDStream(as_dstream(dstream_));
    dstream_ = nullptr;
  }
  if (fh_ != nullptr) {
    std::fclose(fh_);
    fh_ = nullptr;
  }
  in_pos_ = 0;
  in_size_ = 0;
  file_eof_ = false;
  frame_open_ = false;
}

ZstdStream::ZstdStream(ZstdStream&& other) noexcept { *this = std::move(other); }

ZstdStream& ZstdStream::operator=(ZstdStream&& other) noexcept {
  if (this != &other) {
    reset();
    fh_ = other.fh_;
    dstream_ = other.dstream_;
    in_buf_ = std::move(other.in_buf_);
    in_pos_ = other.in_pos_;
    in_size_ = other.in_size_;
    file_eof_ = other.file_eof_;
    frame_open_ = other.frame_open_;
    path_ = std::move(other.path_);
    other.fh_ = nullptr;
    other.dstream_ = nullptr;
    other.in_pos_ = 0;
    other.in_size_ = 0;
    other.file_eof_ = false;
    other.frame_open_ = false;
  }
  return *this;
}

Expected<std::monostate, Refusal> ZstdStream::open(const std::string& path) {
  reset();
  path_ = path;
  fh_ = std::fopen(path.c_str(), "rb");
  if (fh_ == nullptr) {
    return refuse<std::monostate>(
        Refusal(RefusalCode::IO, "qr_dbn::ZstdStream::open", "cannot open payload file"));
  }
  dstream_ = ZSTD_createDStream();
  if (dstream_ == nullptr) {
    reset();
    return refuse<std::monostate>(
        Refusal(RefusalCode::IO, "qr_dbn::ZstdStream::open", "ZSTD_createDStream failed"));
  }
  const std::size_t rc = ZSTD_initDStream(as_dstream(dstream_));
  if (ZSTD_isError(rc) != 0u) {
    reset();
    return refuse<std::monostate>(
        Refusal(RefusalCode::DECODE_FAILED, "qr_dbn::ZstdStream::open", "ZSTD_initDStream failed"));
  }
  in_buf_.resize(kInChunk);
  return std::monostate{};
}

Expected<std::size_t, Refusal> ZstdStream::read(void* dst, std::size_t n) {
  if (fh_ == nullptr || dstream_ == nullptr) {
    return refuse<std::size_t>(
        Refusal(RefusalCode::IO, "qr_dbn::ZstdStream::read", "read on a stream that is not open"));
  }
  ZSTD_outBuffer out{dst, n, 0};
  while (out.pos < out.size) {
    if (in_pos_ >= in_size_) {
      if (file_eof_) {
        // A frame left half-decoded at end of file is a truncated payload, not
        // an end of stream. Refuse rather than hand back a short day.
        if (frame_open_) {
          return refuse<std::size_t>(Refusal(RefusalCode::DECODE_FAILED, "qr_dbn::ZstdStream::read",
                                             "zstd frame truncated at end of file"));
        }
        break;
      }
      const std::size_t got = std::fread(in_buf_.data(), 1, in_buf_.size(), fh_);
      if (got == 0) {
        if (std::ferror(fh_) != 0) {
          return refuse<std::size_t>(
              Refusal(RefusalCode::IO, "qr_dbn::ZstdStream::read", "read error on payload file"));
        }
        file_eof_ = true;
        continue;
      }
      in_pos_ = 0;
      in_size_ = got;
    }
    ZSTD_inBuffer in{in_buf_.data(), in_size_, in_pos_};
    const std::size_t rc = ZSTD_decompressStream(as_dstream(dstream_), &out, &in);
    in_pos_ = in.pos;
    if (ZSTD_isError(rc) != 0u) {
      return refuse<std::size_t>(Refusal(RefusalCode::DECODE_FAILED, "qr_dbn::ZstdStream::read",
                                         "ZSTD_decompressStream refused the frame"));
    }
    // rc == 0 means a frame boundary was just reached; anything else means the
    // decoder is still inside a frame and expects more input.
    frame_open_ = (rc != 0);
  }
  return out.pos;
}

}  // namespace qr::dbn
