// qr_emit/npy_writer.cpp — the .npy v1.0 leaf writer (see npy_writer.hpp for
// the frozen format ruling this implements).
#include "qr_emit/npy_writer.hpp"

#include <fcntl.h>
#include <openssl/evp.h>
#include <sys/stat.h>
#include <unistd.h>

#include <bit>
#include <cerrno>
#include <limits>
#include <cstring>
#include <utility>

#include "qr_core/checked.hpp"

namespace qr::emit {
namespace {

// The payload is written by copying a contiguous array of SCALARS, never a
// struct: a struct's padding bytes are unspecified and would break two-run byte
// identity. Scalar arrays have no padding, and this assert pins the one
// property that makes the copy a correct little-endian C-order encoding.
static_assert(std::endian::native == std::endian::little,
              "the .npy leaves are '<i8'/'<i4'/'<f4'/'|u1' — little-endian by "
              "declaration, so the host must be little-endian for a direct copy "
              "to be the encoding");
static_assert(sizeof(float) == 4, "'<f4' is IEEE-754 binary32");
static_assert(std::numeric_limits<float>::is_iec559, "'<f4' is IEEE-754 binary32");

constexpr std::size_t kWriteChunkBytes = 1U << 20;  // 1 MiB per write(2)

Refusal config_refusal(const char* site, const char* detail, std::int64_t context = 0) {
  return Refusal(RefusalCode::CONFIG, site, detail, context);
}

Refusal io_refusal(const char* site, const char* detail, std::int64_t context = 0) {
  return Refusal(RefusalCode::IO, site, detail, context);
}

/// Decimal of a non-negative int64, field by field (no locale, no iostreams).
std::string decimal(std::int64_t value) {
  if (value == 0) {
    return "0";
  }
  const bool negative = value < 0;
  // Built on the unsigned magnitude so INT64_MIN has no special case.
  std::uint64_t magnitude =
      negative ? (~static_cast<std::uint64_t>(value) + 1U) : static_cast<std::uint64_t>(value);
  char buffer[24];
  std::size_t index = sizeof(buffer);
  while (magnitude != 0) {
    buffer[--index] = static_cast<char>('0' + static_cast<char>(magnitude % 10U));
    magnitude /= 10U;
  }
  std::string out;
  if (negative) {
    out.push_back('-');
  }
  out.append(buffer + index, sizeof(buffer) - index);
  return out;
}

}  // namespace

const char* npy_dtype_descr(NpyDtype dtype) noexcept {
  switch (dtype) {
    case NpyDtype::I8:
      return "<i8";
    case NpyDtype::I4:
      return "<i4";
    case NpyDtype::F4:
      return "<f4";
    case NpyDtype::U1:
      return "|u1";
  }
  detail::fail_fast("qr::emit::npy_dtype_descr: dtype outside the four pinned types");
}

std::size_t npy_dtype_size(NpyDtype dtype) noexcept {
  switch (dtype) {
    case NpyDtype::I8:
      return 8;
    case NpyDtype::I4:
      return 4;
    case NpyDtype::F4:
      return 4;
    case NpyDtype::U1:
      return 1;
  }
  detail::fail_fast("qr::emit::npy_dtype_size: dtype outside the four pinned types");
}

Expected<NpyDtype, Refusal> npy_dtype_from_descr(std::string_view descr) {
  if (descr == "<i8") {
    return NpyDtype::I8;
  }
  if (descr == "<i4") {
    return NpyDtype::I4;
  }
  if (descr == "<f4") {
    return NpyDtype::F4;
  }
  if (descr == "|u1") {
    return NpyDtype::U1;
  }
  return Expected<NpyDtype, Refusal>::refuse(config_refusal(
      "qr_emit::npy_dtype_from_descr", "descr is outside the four APPENDIX C4 dtypes"));
}

Expected<std::int64_t, Refusal> npy_element_count(std::span<const std::int64_t> shape) {
  if (shape.empty() || shape.size() > kNpyMaxDims) {
    return Expected<std::int64_t, Refusal>::refuse(
        config_refusal("qr_emit::npy_element_count", "shape must carry 1..3 dimensions",
                       static_cast<std::int64_t>(shape.size())));
  }
  std::int64_t count = 1;
  for (std::size_t index = 0; index < shape.size(); ++index) {
    const std::int64_t dim = shape[index];
    if (dim < 0) {
      return Expected<std::int64_t, Refusal>::refuse(
          config_refusal("qr_emit::npy_element_count", "negative dimension", dim));
    }
    Expected<std::int64_t, Refusal> product = checked_mul(count, dim);
    if (!product) {
      return product;
    }
    count = product.value();
  }
  return count;
}

Expected<std::string, Refusal> npy_header_bytes(NpyDtype dtype,
                                                std::span<const std::int64_t> shape) {
  Expected<std::int64_t, Refusal> elements = npy_element_count(shape);
  if (!elements) {
    return Expected<std::string, Refusal>::refuse(elements.error());
  }

  // The dict, field by field, in numpy's own key order and spacing.
  std::string dict = "{'descr': '";
  dict += npy_dtype_descr(dtype);
  dict += "', 'fortran_order': False, 'shape': (";
  for (std::size_t index = 0; index < shape.size(); ++index) {
    if (index > 0) {
      dict += ", ";
    }
    dict += decimal(shape[index]);
  }
  if (shape.size() == 1) {
    dict += ",";  // numpy writes a 1-tuple as "(5,)"
  }
  dict += "), }";

  // numpy's padding rule, reproduced exactly: pad with spaces so that
  // 10 + len(dict + pad + '\n') is a multiple of 64, and pad by a full 64 bytes
  // when the unpadded length already lands on the boundary.
  const std::size_t unpadded = kNpyPrologueFixedBytes + dict.size() + 1;
  const std::size_t pad = kNpyHeaderAlignment - (unpadded % kNpyHeaderAlignment);
  const std::size_t header_len = dict.size() + pad + 1;
  if (header_len > 0xFFFFU) {
    return Expected<std::string, Refusal>::refuse(config_refusal(
        "qr_emit::npy_header_bytes", "header does not fit the .npy v1.0 uint16 HEADER_LEN",
        static_cast<std::int64_t>(header_len)));
  }

  std::string out;
  out.reserve(kNpyPrologueFixedBytes + header_len);
  out.push_back('\x93');
  out += "NUMPY";
  out.push_back('\x01');  // major version 1
  out.push_back('\x00');  // minor version 0
  out.push_back(static_cast<char>(header_len & 0xFFU));
  out.push_back(static_cast<char>((header_len >> 8) & 0xFFU));
  out += dict;
  out.append(pad, ' ');
  out.push_back('\n');
  return out;
}

// --- NpyWriter -------------------------------------------------------------

NpyWriter::NpyWriter(NpyWriter&& other) noexcept
    : fd_(other.fd_),
      digest_(other.digest_),
      path_(std::move(other.path_)),
      rel_path_(std::move(other.rel_path_)),
      dtype_(other.dtype_),
      shape_(std::move(other.shape_)),
      elements_declared_(other.elements_declared_),
      elements_written_(other.elements_written_),
      file_bytes_(other.file_bytes_),
      finished_(other.finished_) {
  other.fd_ = -1;
  other.digest_ = nullptr;
  other.finished_ = true;
}

NpyWriter& NpyWriter::operator=(NpyWriter&& other) noexcept {
  if (this != &other) {
    close_descriptor();
    fd_ = other.fd_;
    digest_ = other.digest_;
    path_ = std::move(other.path_);
    rel_path_ = std::move(other.rel_path_);
    dtype_ = other.dtype_;
    shape_ = std::move(other.shape_);
    elements_declared_ = other.elements_declared_;
    elements_written_ = other.elements_written_;
    file_bytes_ = other.file_bytes_;
    finished_ = other.finished_;
    other.fd_ = -1;
    other.digest_ = nullptr;
    other.finished_ = true;
  }
  return *this;
}

NpyWriter::~NpyWriter() { close_descriptor(); }

void NpyWriter::close_descriptor() noexcept {
  if (fd_ >= 0) {
    ::close(fd_);
    fd_ = -1;
  }
  if (digest_ != nullptr) {
    EVP_MD_CTX_free(static_cast<EVP_MD_CTX*>(digest_));
    digest_ = nullptr;
  }
}

Expected<NpyWriter, Refusal> NpyWriter::create(const std::filesystem::path& path,
                                               std::string rel_path, NpyDtype dtype,
                                               std::span<const std::int64_t> shape) {
  Expected<std::int64_t, Refusal> elements = npy_element_count(shape);
  if (!elements) {
    return Expected<NpyWriter, Refusal>::refuse(elements.error());
  }
  Expected<std::string, Refusal> header = npy_header_bytes(dtype, shape);
  if (!header) {
    return Expected<NpyWriter, Refusal>::refuse(header.error());
  }

  // O_EXCL: a leaf is created, never overwritten. Overwriting is how a partial
  // rerun silently mixes two builds into one shard.
  const int fd = ::open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0644);
  if (fd < 0) {
    return Expected<NpyWriter, Refusal>::refuse(
        io_refusal("qr_emit::NpyWriter::create", "cannot create the leaf file", errno));
  }

  NpyWriter writer;
  writer.fd_ = fd;
  writer.path_ = path;
  writer.rel_path_ = std::move(rel_path);
  writer.dtype_ = dtype;
  writer.shape_.assign(shape.begin(), shape.end());
  writer.elements_declared_ = elements.value();
  writer.digest_ = EVP_MD_CTX_new();
  if (writer.digest_ == nullptr) {
    return Expected<NpyWriter, Refusal>::refuse(
        io_refusal("qr_emit::NpyWriter::create", "OpenSSL EVP_MD_CTX_new failed"));
  }
  if (EVP_DigestInit_ex(static_cast<EVP_MD_CTX*>(writer.digest_), EVP_sha256(), nullptr) != 1) {
    return Expected<NpyWriter, Refusal>::refuse(
        io_refusal("qr_emit::NpyWriter::create", "OpenSSL EVP_DigestInit_ex failed"));
  }

  const std::string& bytes = header.value();
  Status written = writer.write_all(reinterpret_cast<const std::uint8_t*>(bytes.data()),
                                    bytes.size());
  if (!written) {
    return Expected<NpyWriter, Refusal>::refuse(written.error());
  }
  return writer;
}

Status NpyWriter::write_all(const std::uint8_t* data, std::size_t bytes) {
  if (fd_ < 0) {
    return Status::refuse(io_refusal("qr_emit::NpyWriter::write_all", "leaf is not open"));
  }
  if (EVP_DigestUpdate(static_cast<EVP_MD_CTX*>(digest_), data, bytes) != 1) {
    return Status::refuse(io_refusal("qr_emit::NpyWriter::write_all", "EVP_DigestUpdate failed"));
  }
  std::size_t offset = 0;
  while (offset < bytes) {
    const std::size_t remaining = bytes - offset;
    const std::size_t chunk = remaining < kWriteChunkBytes ? remaining : kWriteChunkBytes;
    const ssize_t produced = ::write(fd_, data + offset, chunk);
    if (produced < 0) {
      if (errno == EINTR) {
        continue;
      }
      return Status::refuse(
          io_refusal("qr_emit::NpyWriter::write_all", "write(2) failed", errno));
    }
    offset += static_cast<std::size_t>(produced);
  }
  file_bytes_ += static_cast<std::int64_t>(bytes);
  return ok_status();
}

Status NpyWriter::append_bytes(const void* first, std::size_t count, NpyDtype dtype) {
  if (finished_) {
    return Status::refuse(
        config_refusal("qr_emit::NpyWriter::append", "leaf is already finished"));
  }
  if (dtype != dtype_) {
    return Status::refuse(config_refusal("qr_emit::NpyWriter::append",
                                         "element type does not match the declared dtype",
                                         static_cast<std::int64_t>(dtype)));
  }
  Expected<std::int64_t, Refusal> total =
      checked_add(elements_written_, static_cast<std::int64_t>(count));
  if (!total) {
    return Status::refuse(total.error());
  }
  if (total.value() > elements_declared_) {
    return Status::refuse(config_refusal("qr_emit::NpyWriter::append",
                                         "more elements than the declared shape",
                                         total.value()));
  }
  if (count > 0) {
    Status written = write_all(static_cast<const std::uint8_t*>(first),
                               count * npy_dtype_size(dtype));
    if (!written) {
      return written;
    }
  }
  elements_written_ = total.value();
  return ok_status();
}

Status NpyWriter::append(std::span<const std::int64_t> values) {
  return append_bytes(values.data(), values.size(), NpyDtype::I8);
}

Status NpyWriter::append(std::span<const std::int32_t> values) {
  return append_bytes(values.data(), values.size(), NpyDtype::I4);
}

Status NpyWriter::append(std::span<const float> values) {
  return append_bytes(values.data(), values.size(), NpyDtype::F4);
}

Status NpyWriter::append(std::span<const std::uint8_t> values) {
  return append_bytes(values.data(), values.size(), NpyDtype::U1);
}

Expected<NpyLeafReceipt, Refusal> NpyWriter::finish() {
  if (finished_) {
    return Expected<NpyLeafReceipt, Refusal>::refuse(
        config_refusal("qr_emit::NpyWriter::finish", "leaf is already finished"));
  }
  if (elements_written_ != elements_declared_) {
    return Expected<NpyLeafReceipt, Refusal>::refuse(
        config_refusal("qr_emit::NpyWriter::finish",
                       "appended element count is not the declared element count",
                       elements_written_));
  }
  unsigned char digest[EVP_MAX_MD_SIZE];
  unsigned int digest_len = 0;
  if (EVP_DigestFinal_ex(static_cast<EVP_MD_CTX*>(digest_), digest, &digest_len) != 1) {
    return Expected<NpyLeafReceipt, Refusal>::refuse(
        io_refusal("qr_emit::NpyWriter::finish", "EVP_DigestFinal_ex failed"));
  }
  // fsync before the receipt exists: a manifest row is a claim about durable
  // bytes, so the bytes are durable before the row is written.
  if (::fsync(fd_) != 0) {
    return Expected<NpyLeafReceipt, Refusal>::refuse(
        io_refusal("qr_emit::NpyWriter::finish", "fsync(2) on the leaf failed", errno));
  }
  if (::close(fd_) != 0) {
    fd_ = -1;
    return Expected<NpyLeafReceipt, Refusal>::refuse(
        io_refusal("qr_emit::NpyWriter::finish", "close(2) on the leaf failed", errno));
  }
  fd_ = -1;
  finished_ = true;

  static constexpr char kHex[] = "0123456789abcdef";
  std::string hex;
  hex.reserve(static_cast<std::size_t>(digest_len) * 2);
  for (unsigned int index = 0; index < digest_len; ++index) {
    hex.push_back(kHex[digest[index] >> 4]);
    hex.push_back(kHex[digest[index] & 0x0FU]);
  }

  NpyLeafReceipt receipt;
  receipt.rel_path = rel_path_;
  receipt.dtype = dtype_;
  receipt.shape = shape_;
  receipt.rows = shape_.empty() ? 0 : shape_.front();
  receipt.file_bytes = file_bytes_;
  receipt.sha256 = std::move(hex);
  return receipt;
}

}  // namespace qr::emit
