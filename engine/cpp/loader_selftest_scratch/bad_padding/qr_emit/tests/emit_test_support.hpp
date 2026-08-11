// Shared helpers for the qr_emit fixtures. Test-only.
#ifndef QR_EMIT_TESTS_EMIT_TEST_SUPPORT_HPP
#define QR_EMIT_TESTS_EMIT_TEST_SUPPORT_HPP

#include <openssl/evp.h>

#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

namespace qr_emit_test {

/// A fresh scratch directory under the build tree (never /tmp: the container
/// overlay is banned by the machine law).
inline std::filesystem::path scratch(const std::string& name) {
  const std::filesystem::path dir = std::filesystem::path(QR_TEST_SCRATCH_DIR) / "emit" / name;
  std::filesystem::remove_all(dir);
  std::filesystem::create_directories(dir);
  return dir;
}

inline std::string read_file(const std::filesystem::path& path) {
  std::ifstream stream(path, std::ios::binary);
  return std::string(std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>());
}

inline std::string sha256_hex(std::string_view bytes) {
  unsigned char digest[EVP_MAX_MD_SIZE];
  unsigned int length = 0;
  EVP_Digest(bytes.data(), bytes.size(), digest, &length, EVP_sha256(), nullptr);
  static constexpr char kHex[] = "0123456789abcdef";
  std::string hex;
  for (unsigned int index = 0; index < length; ++index) {
    hex.push_back(kHex[digest[index] >> 4]);
    hex.push_back(kHex[digest[index] & 0x0FU]);
  }
  return hex;
}

/// Every regular file under `root`, as repo-relative sorted paths.
inline std::vector<std::string> sorted_files(const std::filesystem::path& root) {
  std::vector<std::string> out;
  for (const std::filesystem::directory_entry& entry :
       std::filesystem::recursive_directory_iterator(root)) {
    if (entry.is_regular_file()) {
      out.push_back(std::filesystem::relative(entry.path(), root).string());
    }
  }
  std::sort(out.begin(), out.end());
  return out;
}

// --- the fixture array literals -------------------------------------------
// Identical, by hand, to tests/fixtures/make_npy_fixtures.py. Duplicated on
// purpose: the round-trip test is only a round trip if the two sides computed
// the values independently.

inline std::vector<std::int64_t> literal_i8_1d() {
  std::vector<std::int64_t> out;
  for (std::int64_t index = 0; index < 5; ++index) {
    out.push_back((index - 2) * 1000000007);
  }
  return out;
}

inline std::vector<std::int32_t> literal_i4_2d() {
  std::vector<std::int32_t> out;
  for (std::int32_t row = 0; row < 3; ++row) {
    for (std::int32_t column = 0; column < 4; ++column) {
      out.push_back(row * 4 + column - 5);
    }
  }
  return out;
}

inline std::vector<float> literal_f4_3d() {
  std::vector<float> out;
  for (int a = 0; a < 2; ++a) {
    for (int b = 0; b < 3; ++b) {
      for (int c = 0; c < 4; ++c) {
        out.push_back(static_cast<float>(a * 12 + b * 4 + c) / 8.0F);
      }
    }
  }
  return out;
}

inline std::vector<std::uint8_t> literal_u1_2d() {
  std::vector<std::uint8_t> out;
  for (int row = 0; row < 2; ++row) {
    for (int column = 0; column < 7; ++column) {
      out.push_back(static_cast<std::uint8_t>(((row * 7 + column) * 37) % 256));
    }
  }
  return out;
}

}  // namespace qr_emit_test

#endif  // QR_EMIT_TESTS_EMIT_TEST_SUPPORT_HPP
