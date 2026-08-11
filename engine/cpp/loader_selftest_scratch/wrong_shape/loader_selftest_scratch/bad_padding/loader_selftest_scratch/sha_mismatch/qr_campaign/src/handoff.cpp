#include "qr_campaign/handoff.hpp"

#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#include <cstring>
#include <utility>

namespace qr::campaign {
namespace {

constexpr const char* kSite = "qr_campaign::handoff";

[[nodiscard]] Refusal io(const char* detail, std::int64_t context = 0) {
  return Refusal(RefusalCode::IO, kSite, detail, context);
}
[[nodiscard]] Refusal content(const char* detail, std::int64_t context = 0) {
  return Refusal(RefusalCode::CONTENT_MISMATCH, kSite, detail, context);
}

constexpr std::uint64_t kAlignment = 64;

[[nodiscard]] std::uint64_t align_up(std::uint64_t value) {
  return (value + kAlignment - 1) / kAlignment * kAlignment;
}

/// pwrite in bounded chunks: one 750MB group table is a single logical leaf but
/// never a single syscall.
[[nodiscard]] bool write_all(int fd, const void* data, std::uint64_t bytes,
                             std::uint64_t offset) {
  const auto* cursor = static_cast<const std::uint8_t*>(data);
  std::uint64_t written = 0;
  while (written < bytes) {
    const std::uint64_t remaining = bytes - written;
    const std::size_t chunk =
        static_cast<std::size_t>(remaining > (64U << 20U) ? (64U << 20U) : remaining);
    const ssize_t result =
        ::pwrite(fd, cursor + written, chunk, static_cast<off_t>(offset + written));
    if (result <= 0) {
      return false;
    }
    written += static_cast<std::uint64_t>(result);
  }
  return true;
}

void store_u64(std::uint8_t* out, std::uint64_t value) { std::memcpy(out, &value, sizeof(value)); }
void store_i64(std::uint8_t* out, std::int64_t value) { std::memcpy(out, &value, sizeof(value)); }
[[nodiscard]] std::uint64_t load_u64(const std::uint8_t* in) {
  std::uint64_t value = 0;
  std::memcpy(&value, in, sizeof(value));
  return value;
}
[[nodiscard]] std::int64_t load_i64(const std::uint8_t* in) {
  std::int64_t value = 0;
  std::memcpy(&value, in, sizeof(value));
  return value;
}

}  // namespace

Expected<int, Refusal> create_handoff_fd() {
  const int fd = ::memfd_create("qr_campaign_handoff", MFD_CLOEXEC);
  if (fd < 0) {
    return Expected<int, Refusal>::refuse(io("memfd_create refused the handoff file"));
  }
  return Expected<int, Refusal>(fd);
}

Status HandoffWriter::append(std::string_view name, LeafScope scope, NpyDtype dtype,
                             std::span<const std::int64_t> shape, const void* data,
                             std::uint64_t bytes) {
  if (leaves_.size() >= kHandoffMaxLeaves) {
    return Status::refuse(content("the handoff header cannot describe another leaf",
                                  static_cast<std::int64_t>(leaves_.size())));
  }
  if (name.empty() || name.size() >= kHandoffNameBytes) {
    return Status::refuse(content("a handoff leaf name does not fit the descriptor"));
  }
  if (shape.empty() || shape.size() > 3) {
    return Status::refuse(content("a handoff leaf carries 1..3 dimensions",
                                  static_cast<std::int64_t>(shape.size())));
  }
  std::uint64_t elements = 1;
  for (const std::int64_t extent : shape) {
    if (extent < 0) {
      return Status::refuse(content("a handoff leaf carries a negative extent", extent));
    }
    elements *= static_cast<std::uint64_t>(extent);
  }
  if (elements * qr::emit::npy_dtype_size(dtype) != bytes) {
    return Status::refuse(content("a handoff leaf's byte count is not its shape times its dtype",
                                  static_cast<std::int64_t>(bytes)));
  }
  const std::uint64_t offset = align_up(cursor_);
  if (bytes > 0 && !write_all(fd_, data, bytes, offset)) {
    return Status::refuse(io("short write into the handoff blob"));
  }
  HandoffLeaf leaf;
  leaf.name = std::string(name);
  leaf.scope = scope;
  leaf.dtype = dtype;
  leaf.shape.assign(shape.begin(), shape.end());
  leaf.offset = offset;
  leaf.bytes = bytes;
  leaves_.push_back(std::move(leaf));
  cursor_ = offset + bytes;
  return ok_status();
}

Status HandoffWriter::finish() {
  std::vector<std::uint8_t> header(kHandoffHeaderBytes, 0);
  std::memcpy(header.data(), kHandoffMagic.data(), kHandoffMagic.size());
  store_u64(header.data() + 32, static_cast<std::uint64_t>(leaves_.size()));
  store_u64(header.data() + 40, cursor_);
  std::uint8_t* descriptor = header.data() + 64;
  for (const HandoffLeaf& leaf : leaves_) {
    std::memcpy(descriptor, leaf.name.data(), leaf.name.size());
    descriptor[kHandoffNameBytes] = static_cast<std::uint8_t>(leaf.scope);
    descriptor[kHandoffNameBytes + 1] = static_cast<std::uint8_t>(leaf.dtype);
    descriptor[kHandoffNameBytes + 2] = static_cast<std::uint8_t>(leaf.shape.size());
    for (std::size_t index = 0; index < 3; ++index) {
      store_i64(descriptor + 56 + index * 8,
                index < leaf.shape.size() ? leaf.shape[index] : 0);
    }
    store_u64(descriptor + 80, leaf.offset);
    store_u64(descriptor + 88, leaf.bytes);
    descriptor += kHandoffDescriptorBytes;
  }
  if (!write_all(fd_, header.data(), header.size(), 0)) {
    return Status::refuse(io("short write of the handoff header"));
  }
  if (::fsync(fd_) != 0 && errno != EINVAL) {
    // memfd has no backing device; EINVAL from fsync is expected and harmless.
    return Status::refuse(io("cannot flush the handoff blob"));
  }
  return ok_status();
}

HandoffReader::HandoffReader(HandoffReader&& other) noexcept
    : base_(other.base_), size_(other.size_), leaves_(std::move(other.leaves_)) {
  other.base_ = nullptr;
  other.size_ = 0;
}

HandoffReader& HandoffReader::operator=(HandoffReader&& other) noexcept {
  if (this != &other) {
    if (base_ != nullptr) {
      ::munmap(const_cast<std::uint8_t*>(base_), size_);
    }
    base_ = other.base_;
    size_ = other.size_;
    leaves_ = std::move(other.leaves_);
    other.base_ = nullptr;
    other.size_ = 0;
  }
  return *this;
}

HandoffReader::~HandoffReader() {
  if (base_ != nullptr) {
    ::munmap(const_cast<std::uint8_t*>(base_), size_);
  }
}

Expected<HandoffReader, Refusal> HandoffReader::map(int fd) {
  using Result = Expected<HandoffReader, Refusal>;
  struct ::stat info = {};
  if (::fstat(fd, &info) != 0) {
    return Result::refuse(io("cannot stat the handoff blob"));
  }
  const auto size = static_cast<std::size_t>(info.st_size);
  if (size < kHandoffHeaderBytes) {
    return Result::refuse(content("the handoff blob is shorter than its own header",
                                  static_cast<std::int64_t>(size)));
  }
  void* mapping = ::mmap(nullptr, size, PROT_READ, MAP_SHARED, fd, 0);
  if (mapping == MAP_FAILED) {
    return Result::refuse(io("cannot map the handoff blob"));
  }
  HandoffReader reader;
  reader.base_ = static_cast<const std::uint8_t*>(mapping);
  reader.size_ = size;
  if (std::memcmp(reader.base_, kHandoffMagic.data(), kHandoffMagic.size()) != 0) {
    return Result::refuse(content("the handoff blob does not carry the driver's magic"));
  }
  const std::uint64_t count = load_u64(reader.base_ + 32);
  const std::uint64_t end = load_u64(reader.base_ + 40);
  if (count == 0) {
    return Result::refuse(content("the handoff blob describes no leaf: the feature builder did "
                                  "not finish"));
  }
  if (count > kHandoffMaxLeaves || end > size) {
    return Result::refuse(content("the handoff header is inconsistent with the blob",
                                  static_cast<std::int64_t>(count)));
  }
  const std::uint8_t* descriptor = reader.base_ + 64;
  for (std::uint64_t index = 0; index < count; ++index) {
    HandoffLeaf leaf;
    const char* name = reinterpret_cast<const char*>(descriptor);
    const std::size_t length = ::strnlen(name, kHandoffNameBytes);
    leaf.name.assign(name, length);
    leaf.scope = static_cast<LeafScope>(descriptor[kHandoffNameBytes]);
    leaf.dtype = static_cast<NpyDtype>(descriptor[kHandoffNameBytes + 1]);
    const std::size_t dims = descriptor[kHandoffNameBytes + 2];
    if (leaf.name.empty() || dims == 0 || dims > 3) {
      return Result::refuse(content("a handoff descriptor is malformed",
                                    static_cast<std::int64_t>(index)));
    }
    for (std::size_t dim = 0; dim < dims; ++dim) {
      leaf.shape.push_back(load_i64(descriptor + 56 + dim * 8));
    }
    leaf.offset = load_u64(descriptor + 80);
    leaf.bytes = load_u64(descriptor + 88);
    if (leaf.offset < kHandoffHeaderBytes || leaf.offset + leaf.bytes > size) {
      return Result::refuse(content("a handoff leaf runs outside the blob",
                                    static_cast<std::int64_t>(index)));
    }
    reader.leaves_.push_back(std::move(leaf));
    descriptor += kHandoffDescriptorBytes;
  }
  return Result(std::move(reader));
}

const void* HandoffReader::payload(const HandoffLeaf& leaf) const noexcept {
  return base_ + leaf.offset;
}

Expected<std::uint64_t, Refusal> HandoffReader::elements(const HandoffLeaf& leaf) const {
  std::uint64_t count = 1;
  for (const std::int64_t extent : leaf.shape) {
    count *= static_cast<std::uint64_t>(extent);
  }
  if (count * qr::emit::npy_dtype_size(leaf.dtype) != leaf.bytes) {
    return Expected<std::uint64_t, Refusal>::refuse(
        content("a handoff leaf's bytes disagree with its shape"));
  }
  return Expected<std::uint64_t, Refusal>(count);
}

}  // namespace qr::campaign
