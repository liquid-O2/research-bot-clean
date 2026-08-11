// qr_parquet/arena.hpp — the reused page arena and the per-chunk dictionary cache.
//
// SPEC: design/DESIGN_SUBSTRATE.md M1 qr_parquet bullet — "ZSTD pages into a
// reused arena" and "dictionary-page cache per chunk".
//
// WHY IT IS SHAPED THIS WAY. A decode pass over a real option-quote shard walks
// ~9,000 column chunks and tens of thousands of pages; allocating a fresh buffer
// per page would dominate the budget. `Arena` therefore owns THREE named
// buffers that only ever grow — page bytes, level bytes, dictionary-index bytes
// — and every page reuses them in place. They are named rather than bump
// allocated so that no pointer handed out can be invalidated by a later grow
// inside the same page.
//
// The dictionary is NOT in the arena: it must survive every data page of its
// column chunk, and the arena's page buffer is overwritten by each page. It
// lives in `DictionaryCache`, cleared once per chunk.
#ifndef QR_PARQUET_ARENA_HPP
#define QR_PARQUET_ARENA_HPP

#include <cstddef>
#include <cstdint>
#include <vector>

#include "qr_parquet/column.hpp"

namespace qr::parquet {

class Arena {
 public:
  /// Uncompressed page bytes land here.
  [[nodiscard]] std::uint8_t* page(std::size_t bytes) {
    if (page_.size() < bytes) {
      page_.resize(bytes);
    }
    return page_.data();
  }
  /// One byte per definition level of the current page.
  [[nodiscard]] std::uint8_t* levels(std::size_t count) {
    if (levels_.size() < count) {
      levels_.resize(count);
    }
    return levels_.data();
  }
  /// One entry per non-null value of the current page (dictionary indices).
  [[nodiscard]] std::uint32_t* indices(std::size_t count) {
    if (indices_.size() < count) {
      indices_.resize(count);
    }
    return indices_.data();
  }

  [[nodiscard]] std::size_t bytes_reserved() const noexcept {
    return page_.capacity() + levels_.capacity() + indices_.capacity() * sizeof(std::uint32_t);
  }

  /// Drops the reserved capacity. Only tests need this; the decode path keeps
  /// the buffers for the life of the worker.
  void release() {
    std::vector<std::uint8_t>().swap(page_);
    std::vector<std::uint8_t>().swap(levels_);
    std::vector<std::uint32_t>().swap(indices_);
  }

 private:
  std::vector<std::uint8_t> page_;
  std::vector<std::uint8_t> levels_;
  std::vector<std::uint32_t> indices_;
};

/// The decoded dictionary page of the column chunk currently being read.
struct DictionaryCache {
  bool present = false;
  LeafType type = LeafType::INT64;
  std::size_t count = 0;

  std::vector<std::int32_t> i32;
  std::vector<std::int64_t> i64;
  std::vector<double> f64;
  std::vector<std::uint32_t> offsets;  // count + 1 entries
  std::vector<std::uint8_t> bytes;

  void clear() noexcept {
    present = false;
    count = 0;
    i32.clear();
    i64.clear();
    f64.clear();
    offsets.clear();
    bytes.clear();
  }
};

/// Everything one decoding worker reuses. One per thread; never shared.
struct DecodeWorkspace {
  Arena arena;
  DictionaryCache dictionary;
};

}  // namespace qr::parquet

#endif  // QR_PARQUET_ARENA_HPP
