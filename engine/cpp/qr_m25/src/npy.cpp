// qr_m25/src/npy.cpp — the minimal .npy reader + manifest parser.
#include "qr_m25/npy.hpp"

#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#include <cerrno>
#include <cstring>
#include <fstream>
#include <sstream>
#include <utility>

namespace qr::m25 {
namespace {

constexpr char kNpyMagic[6] = {'\x93', 'N', 'U', 'M', 'P', 'Y'};
constexpr std::size_t kAlignment = 64;

Refusal io(const char* site, const char* detail, std::int64_t context) noexcept {
  return Refusal(RefusalCode::IO, site, detail, context);
}

Refusal schema(const char* site, const char* detail, std::int64_t context) noexcept {
  return Refusal(RefusalCode::SCHEMA_MISMATCH, site, detail, context);
}

std::size_t dtype_width(NpyDtype dtype) noexcept {
  switch (dtype) {
    case NpyDtype::I8: return 8;
    case NpyDtype::I4: return 4;
    case NpyDtype::F4: return 4;
    case NpyDtype::U1: return 1;
  }
  return 0;
}

bool parse_dtype(const std::string& token, NpyDtype* out) noexcept {
  if (token == "<i8") { *out = NpyDtype::I8; return true; }
  if (token == "<i4") { *out = NpyDtype::I4; return true; }
  if (token == "<f4") { *out = NpyDtype::F4; return true; }
  if (token == "|u1") { *out = NpyDtype::U1; return true; }
  return false;
}

/// Extract the value of `key` from an .npy header dict literal. The writer emits
/// a fixed, canonical form; anything else is refused by the caller rather than
/// parsed heuristically.
bool header_value(const std::string& header, const std::string& key, std::string* out) {
  const std::string needle = "'" + key + "': ";
  const std::size_t at = header.find(needle);
  if (at == std::string::npos) {
    return false;
  }
  std::size_t i = at + needle.size();
  std::size_t depth = 0;
  std::string value;
  while (i < header.size()) {
    const char c = header[i];
    if (c == '(') { ++depth; }
    if (c == ')') { if (depth > 0) { --depth; } }
    if (c == ',' && depth == 0) { break; }
    value.push_back(c);
    ++i;
  }
  // trim
  const std::size_t b = value.find_first_not_of(" \t");
  const std::size_t e = value.find_last_not_of(" \t");
  if (b == std::string::npos) {
    return false;
  }
  *out = value.substr(b, e - b + 1);
  return true;
}

bool parse_shape(const std::string& text, std::vector<std::int64_t>* out) {
  if (text.size() < 2 || text.front() != '(' || text.back() != ')') {
    return false;
  }
  const std::string inner = text.substr(1, text.size() - 2);
  std::stringstream stream(inner);
  std::string field;
  while (std::getline(stream, field, ',')) {
    const std::size_t b = field.find_first_not_of(" \t");
    if (b == std::string::npos) {
      continue;
    }
    const std::size_t e = field.find_last_not_of(" \t");
    const std::string number = field.substr(b, e - b + 1);
    if (number.empty()) {
      continue;
    }
    for (const char c : number) {
      if (c < '0' || c > '9') {
        return false;
      }
    }
    out->push_back(static_cast<std::int64_t>(std::stoll(number)));
  }
  return !out->empty();
}

}  // namespace

const char* npy_dtype_name(NpyDtype dtype) noexcept {
  switch (dtype) {
    case NpyDtype::I8: return "<i8";
    case NpyDtype::I4: return "<i4";
    case NpyDtype::F4: return "<f4";
    case NpyDtype::U1: return "|u1";
  }
  return "UNKNOWN";
}

NpyArray::NpyArray(NpyArray&& other) noexcept
    : map_(other.map_),
      map_bytes_(other.map_bytes_),
      data_offset_(other.data_offset_),
      dtype_(other.dtype_),
      shape_(std::move(other.shape_)),
      element_count_(other.element_count_) {
  other.map_ = nullptr;
  other.map_bytes_ = 0;
}

NpyArray& NpyArray::operator=(NpyArray&& other) noexcept {
  if (this != &other) {
    if (map_ != nullptr) {
      ::munmap(map_, map_bytes_);
    }
    map_ = other.map_;
    map_bytes_ = other.map_bytes_;
    data_offset_ = other.data_offset_;
    dtype_ = other.dtype_;
    shape_ = std::move(other.shape_);
    element_count_ = other.element_count_;
    other.map_ = nullptr;
    other.map_bytes_ = 0;
  }
  return *this;
}

NpyArray::~NpyArray() {
  if (map_ != nullptr) {
    ::munmap(map_, map_bytes_);
    map_ = nullptr;
  }
}

Expected<NpyArray, Refusal> NpyArray::open(const std::filesystem::path& path) {
  const int fd = ::open(path.c_str(), O_RDONLY | O_CLOEXEC);
  if (fd < 0) {
    return refuse<NpyArray>(io("qr_m25::NpyArray::open", "cannot open leaf", errno));
  }
  struct stat st {};
  if (::fstat(fd, &st) != 0) {
    ::close(fd);
    return refuse<NpyArray>(io("qr_m25::NpyArray::open", "cannot stat leaf", errno));
  }
  const auto file_bytes = static_cast<std::size_t>(st.st_size);
  if (file_bytes < 10) {
    ::close(fd);
    return refuse<NpyArray>(schema("qr_m25::NpyArray::open", "file is shorter than an .npy header",
                                   static_cast<std::int64_t>(file_bytes)));
  }
  void* map = ::mmap(nullptr, file_bytes, PROT_READ, MAP_PRIVATE, fd, 0);
  ::close(fd);
  if (map == MAP_FAILED) {
    return refuse<NpyArray>(io("qr_m25::NpyArray::open", "cannot mmap leaf", errno));
  }

  const char* bytes = static_cast<const char*>(map);
  if (std::memcmp(bytes, kNpyMagic, sizeof(kNpyMagic)) != 0) {
    ::munmap(map, file_bytes);
    return refuse<NpyArray>(schema("qr_m25::NpyArray::open", "missing \\x93NUMPY magic", 0));
  }
  const auto major = static_cast<std::uint8_t>(bytes[6]);
  std::size_t header_len = 0;
  std::size_t header_at = 0;
  if (major == 1) {
    std::uint16_t len16 = 0;
    std::memcpy(&len16, bytes + 8, sizeof(len16));
    header_len = len16;
    header_at = 10;
  } else if (major == 2) {
    std::uint32_t len32 = 0;
    std::memcpy(&len32, bytes + 8, sizeof(len32));
    header_len = len32;
    header_at = 12;
  } else {
    ::munmap(map, file_bytes);
    return refuse<NpyArray>(schema("qr_m25::NpyArray::open", "unsupported .npy major version", major));
  }
  if (header_at + header_len > file_bytes) {
    ::munmap(map, file_bytes);
    return refuse<NpyArray>(schema("qr_m25::NpyArray::open", "header runs past end of file",
                                   static_cast<std::int64_t>(header_len)));
  }
  const std::string header(bytes + header_at, header_len);

  std::string descr;
  std::string fortran;
  std::string shape_text;
  if (!header_value(header, "descr", &descr) || !header_value(header, "fortran_order", &fortran) ||
      !header_value(header, "shape", &shape_text)) {
    ::munmap(map, file_bytes);
    return refuse<NpyArray>(schema("qr_m25::NpyArray::open", "header dict is missing a required key", 0));
  }
  if (descr.size() >= 2 && (descr.front() == '\'' || descr.front() == '"')) {
    descr = descr.substr(1, descr.size() - 2);
  }
  NpyDtype dtype = NpyDtype::U1;
  if (!parse_dtype(descr, &dtype)) {
    ::munmap(map, file_bytes);
    return refuse<NpyArray>(schema("qr_m25::NpyArray::open",
                                   "dtype outside the four APPENDIX C4 element types", 0));
  }
  if (fortran != "False") {
    ::munmap(map, file_bytes);
    return refuse<NpyArray>(schema("qr_m25::NpyArray::open", "fortran_order is not False", 0));
  }
  std::vector<std::int64_t> shape;
  if (!parse_shape(shape_text, &shape)) {
    ::munmap(map, file_bytes);
    return refuse<NpyArray>(schema("qr_m25::NpyArray::open", "cannot parse the shape tuple", 0));
  }

  std::int64_t elements = 1;
  for (const std::int64_t dim : shape) {
    elements *= dim;
  }
  const std::size_t data_offset = header_at + header_len;
  if (data_offset % kAlignment != 0) {
    ::munmap(map, file_bytes);
    return refuse<NpyArray>(schema("qr_m25::NpyArray::open", "data does not start on a 64-byte boundary",
                                   static_cast<std::int64_t>(data_offset)));
  }
  const std::size_t want = static_cast<std::size_t>(elements) * dtype_width(dtype);
  if (data_offset + want != file_bytes) {
    ::munmap(map, file_bytes);
    return refuse<NpyArray>(Refusal(RefusalCode::CONTENT_MISMATCH, "qr_m25::NpyArray::open",
                                    "file size is not exactly header + payload",
                                    static_cast<std::int64_t>(file_bytes)));
  }

  NpyArray out;
  out.map_ = map;
  out.map_bytes_ = file_bytes;
  out.data_offset_ = data_offset;
  out.dtype_ = dtype;
  out.shape_ = std::move(shape);
  out.element_count_ = elements;
  return out;
}

std::span<const std::int64_t> NpyArray::i8() const {
  if (dtype_ != NpyDtype::I8) {
    qr::detail::fail_fast("qr_m25::NpyArray::i8 on a non-i8 leaf");
  }
  return {reinterpret_cast<const std::int64_t*>(static_cast<const char*>(map_) + data_offset_),
          static_cast<std::size_t>(element_count_)};
}

std::span<const std::int32_t> NpyArray::i4() const {
  if (dtype_ != NpyDtype::I4) {
    qr::detail::fail_fast("qr_m25::NpyArray::i4 on a non-i4 leaf");
  }
  return {reinterpret_cast<const std::int32_t*>(static_cast<const char*>(map_) + data_offset_),
          static_cast<std::size_t>(element_count_)};
}

std::span<const float> NpyArray::f4() const {
  if (dtype_ != NpyDtype::F4) {
    qr::detail::fail_fast("qr_m25::NpyArray::f4 on a non-f4 leaf");
  }
  return {reinterpret_cast<const float*>(static_cast<const char*>(map_) + data_offset_),
          static_cast<std::size_t>(element_count_)};
}

std::span<const std::uint8_t> NpyArray::u1() const {
  if (dtype_ != NpyDtype::U1) {
    qr::detail::fail_fast("qr_m25::NpyArray::u1 on a non-u1 leaf");
  }
  return {reinterpret_cast<const std::uint8_t*>(static_cast<const char*>(map_) + data_offset_),
          static_cast<std::size_t>(element_count_)};
}

const ManifestLeaf* TapeManifest::find(const std::string& rel) const noexcept {
  for (const ManifestLeaf& leaf : leaves) {
    if (leaf.rel_path == rel) {
      return &leaf;
    }
  }
  return nullptr;
}

Expected<TapeManifest, Refusal> read_manifest(const std::filesystem::path& shard_dir) {
  const std::filesystem::path path = shard_dir / "manifest.tsv";
  std::ifstream in(path);
  if (!in) {
    return refuse<TapeManifest>(io("qr_m25::read_manifest", "cannot open manifest.tsv", 0));
  }
  TapeManifest manifest;
  std::string line;
  bool saw_schema = false;
  while (std::getline(in, line)) {
    if (line.empty() || line[0] == '#') {
      continue;
    }
    std::vector<std::string> field;
    std::stringstream stream(line);
    std::string token;
    while (std::getline(stream, token, '\t')) {
      field.push_back(token);
    }
    if (field.size() < 3) {
      continue;
    }
    if (field[0] == "meta") {
      if (field[1] == "manifest_schema") {
        if (field[2] != "qr_emit_manifest_v1") {
          return refuse<TapeManifest>(schema("qr_m25::read_manifest", "foreign manifest schema", 0));
        }
        saw_schema = true;
      } else if (field[1] == "build_id") {
        manifest.build_id = field[2];
      } else if (field[1] == "session_ordinal") {
        manifest.session_ordinal = std::stoll(field[2]);
      } else if (field[1] == "side") {
        manifest.side = field[2];
      }
    } else if (field[0] == "census" && field.size() >= 4 && field[1] == "task_card_v4") {
      manifest.card_sha256 = field[2];
    } else if (field[0] == "leaf" && field.size() >= 6) {
      ManifestLeaf leaf;
      leaf.rel_path = field[1];
      leaf.dtype = field[2];
      std::stringstream dims(field[3]);
      std::string dim;
      while (std::getline(dims, dim, ',')) {
        leaf.shape.push_back(std::stoll(dim));
      }
      leaf.rows = std::stoll(field[4]);
      leaf.sha256 = field[5];
      const std::size_t slash = leaf.rel_path.find('/');
      leaf.section = slash == std::string::npos ? std::string() : leaf.rel_path.substr(0, slash);
      leaf.name = slash == std::string::npos ? leaf.rel_path : leaf.rel_path.substr(slash + 1);
      manifest.leaves.push_back(std::move(leaf));
    }
  }
  if (!saw_schema) {
    return refuse<TapeManifest>(schema("qr_m25::read_manifest", "manifest carries no schema line", 0));
  }
  if (manifest.leaves.empty()) {
    return refuse<TapeManifest>(schema("qr_m25::read_manifest", "manifest declares no leaves", 0));
  }
  return manifest;
}

Expected<NpyArray, Refusal> open_leaf(const std::filesystem::path& shard_dir,
                                      const TapeManifest& manifest, const std::string& rel_path) {
  const ManifestLeaf* declared = manifest.find(rel_path);
  if (declared == nullptr) {
    return refuse<NpyArray>(Refusal(RefusalCode::CONTENT_MISMATCH, "qr_m25::open_leaf",
                                    "manifest does not declare this leaf", 0));
  }
  Expected<NpyArray, Refusal> opened = NpyArray::open(shard_dir / rel_path);
  if (!opened.has_value()) {
    return opened;
  }
  const NpyArray& array = opened.value();
  if (std::string(npy_dtype_name(array.dtype())) != declared->dtype) {
    return refuse<NpyArray>(Refusal(RefusalCode::CONTENT_MISMATCH, "qr_m25::open_leaf",
                                    "leaf dtype disagrees with its manifest row", 0));
  }
  if (array.shape().size() != declared->shape.size()) {
    return refuse<NpyArray>(Refusal(RefusalCode::CONTENT_MISMATCH, "qr_m25::open_leaf",
                                    "leaf rank disagrees with its manifest row",
                                    static_cast<std::int64_t>(array.shape().size())));
  }
  for (std::size_t i = 0; i < declared->shape.size(); ++i) {
    if (array.shape()[i] != declared->shape[i]) {
      return refuse<NpyArray>(Refusal(RefusalCode::CONTENT_MISMATCH, "qr_m25::open_leaf",
                                      "leaf shape disagrees with its manifest row",
                                      array.shape()[i]));
    }
  }
  if (array.rows() != declared->rows) {
    return refuse<NpyArray>(Refusal(RefusalCode::CONTENT_MISMATCH, "qr_m25::open_leaf",
                                    "leaf row count disagrees with its manifest row", array.rows()));
  }
  return opened;
}

}  // namespace qr::m25
