// qr_emit/src/io_util.hpp — internal, header-only helpers shared by the two
// qr_emit translation units. Not installed and not part of the public API:
// everything here is an implementation detail of the publish discipline.
#ifndef QR_EMIT_SRC_IO_UTIL_HPP
#define QR_EMIT_SRC_IO_UTIL_HPP

#include <fcntl.h>
#include <openssl/evp.h>
#include <unistd.h>

#include <cerrno>
#include <cstdint>
#include <filesystem>
#include <string>
#include <string_view>

#include "qr_emit/npy_writer.hpp"

namespace qr::emit::internal {

inline Refusal config_refusal(const char* site, const char* detail, std::int64_t context = 0) {
  return Refusal(RefusalCode::CONFIG, site, detail, context);
}

inline Refusal io_refusal(const char* site, const char* detail, std::int64_t context = 0) {
  return Refusal(RefusalCode::IO, site, detail, context);
}

/// Decimal of an int64, field by field: no locale, no iostreams, no snprintf
/// format-string surface. INT64_MIN needs no special case because the digits
/// are produced from the unsigned magnitude.
inline std::string decimal(std::int64_t value) {
  const bool negative = value < 0;
  std::uint64_t magnitude =
      negative ? (~static_cast<std::uint64_t>(value) + 1U) : static_cast<std::uint64_t>(value);
  char buffer[24];
  std::size_t index = sizeof(buffer);
  if (magnitude == 0) {
    buffer[--index] = '0';
  }
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

inline std::string sha256_hex_bytes(std::string_view bytes) {
  unsigned char digest[EVP_MAX_MD_SIZE];
  unsigned int digest_len = 0;
  if (EVP_Digest(bytes.data(), bytes.size(), digest, &digest_len, EVP_sha256(), nullptr) != 1) {
    detail::fail_fast("qr::emit: OpenSSL EVP_Digest(sha256) failed");
  }
  static constexpr char kHex[] = "0123456789abcdef";
  std::string hex;
  hex.reserve(static_cast<std::size_t>(digest_len) * 2);
  for (unsigned int index = 0; index < digest_len; ++index) {
    hex.push_back(kHex[digest[index] >> 4]);
    hex.push_back(kHex[digest[index] & 0x0FU]);
  }
  return hex;
}

inline Status fsync_directory(const std::filesystem::path& path) {
  const int fd = ::open(path.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
  if (fd < 0) {
    return Status::refuse(
        io_refusal("qr_emit::fsync_directory", "cannot open the directory", errno));
  }
  const int synced = ::fsync(fd);
  const int sync_errno = errno;
  ::close(fd);
  if (synced != 0) {
    return Status::refuse(
        io_refusal("qr_emit::fsync_directory", "fsync(2) on the directory failed", sync_errno));
  }
  return ok_status();
}

/// Creates a new file (O_EXCL — never an overwrite), writes it whole, fsyncs it.
inline Status write_whole_file(const std::filesystem::path& path, std::string_view bytes) {
  const int fd = ::open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0644);
  if (fd < 0) {
    return Status::refuse(io_refusal("qr_emit::write_whole_file", "cannot create the file", errno));
  }
  std::size_t offset = 0;
  while (offset < bytes.size()) {
    const ssize_t produced = ::write(fd, bytes.data() + offset, bytes.size() - offset);
    if (produced < 0) {
      if (errno == EINTR) {
        continue;
      }
      const int write_errno = errno;
      ::close(fd);
      return Status::refuse(io_refusal("qr_emit::write_whole_file", "write(2) failed", write_errno));
    }
    offset += static_cast<std::size_t>(produced);
  }
  if (::fsync(fd) != 0) {
    const int sync_errno = errno;
    ::close(fd);
    return Status::refuse(io_refusal("qr_emit::write_whole_file", "fsync(2) failed", sync_errno));
  }
  if (::close(fd) != 0) {
    return Status::refuse(io_refusal("qr_emit::write_whole_file", "close(2) failed", errno));
  }
  return ok_status();
}

}  // namespace qr::emit::internal

#endif  // QR_EMIT_SRC_IO_UTIL_HPP
