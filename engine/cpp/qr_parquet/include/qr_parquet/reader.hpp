// qr_parquet/reader.hpp — the dialect-pinned parquet reader.
//
// SPEC (design/DESIGN_SUBSTRATE.md, M1, qr_parquet bullet, verbatim):
//   "dialect-pinned custom decoder, primary: thrift-compact footer, ZSTD pages
//    into reused arena, PLAIN/RLE/RLE_DICTIONARY, def-levels->validity, flat
//    INT32/INT64/DOUBLE/BYTE_ARRAY; ANY tuple outside the census = typed file
//    refusal"
// plus, from the WP3 brief's expansion of the same bullet: row-group timestamp
// statistics exposure for RTH pruning, column projection by leaf index,
// DataPage v1 AND v2 header shapes, dictionary-page cache per chunk.
//
// OPEN IS THE WALL. `File::open` parses the footer and gates the WHOLE file —
// every row group, every column chunk, every schema element — against the
// pinned dialect before a single payload byte is decoded. A projection cannot
// dodge the gate by simply not asking for the offending column.
//
// PRUNING IS A SPEED LEVER, NEVER A CORRECTNESS ONE (the rule the frozen Rust
// reader states at select_v2/src/sources/mod.rs:211-214): `rth_row_groups`
// keeps every row group whose INT64 statistics can overlap the window, and
// keeps ALL of them the moment any row group's statistics are missing.
#ifndef QR_PARQUET_READER_HPP
#define QR_PARQUET_READER_HPP

#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

#include "qr_parquet/arena.hpp"
#include "qr_parquet/column.hpp"
#include "qr_parquet/dialect.hpp"
#include "qr_parquet/metadata.hpp"

namespace qr::parquet {

/// One flat leaf column of the file's schema, after the dialect gate.
struct LeafColumn {
  std::string name;
  LeafType type = LeafType::INT64;
  LeafConverted converted = LeafConverted::NONE;
  bool optional = true;             // false == REQUIRED, no definition levels
  bool logical_timestamp = false;   // informational; pruning is by leaf index
};

/// INT64 min/max of one column chunk, as carried by its statistics.
struct Int64Stats {
  bool present = false;
  std::int64_t min = 0;
  std::int64_t max = 0;
  bool has_null_count = false;
  std::int64_t null_count = 0;
};

/// Result of comparing a decoded chunk against the WRITER's own statistics.
///
/// The min/max/null_count in a parquet footer were computed by whatever wrote
/// the file — for this corpus, Polars. Agreeing with them is therefore an
/// INDEPENDENT check on both the values this decoder produces and its
/// definition-level handling, available on every real file at no cost.
struct StatisticsCheck {
  bool comparable = false;   // the chunk carried usable min/max for this type
  bool min_matches = true;
  bool max_matches = true;
  bool null_count_matches = true;
  bool null_count_present = false;

  [[nodiscard]] bool agrees() const noexcept {
    return min_matches && max_matches && null_count_matches;
  }
};

/// Compares one decoded column chunk against the statistics its writer stored.
[[nodiscard]] StatisticsCheck verify_against_statistics(const Statistics& statistics,
                                                        LeafType type, const ColumnData& column);

class File {
 public:
  File(const File&) = delete;
  File& operator=(const File&) = delete;
  File(File&& other) noexcept;
  File& operator=(File&& other) noexcept;
  ~File();

  /// Maps the file, parses its footer, and gates the whole file against the
  /// pinned dialect. Every failure is a typed refusal naming this path.
  [[nodiscard]] static FileExpected<File> open(std::string path);

  [[nodiscard]] const std::string& path() const noexcept { return path_; }
  [[nodiscard]] std::int64_t num_rows() const noexcept { return meta_.num_rows; }
  [[nodiscard]] std::size_t num_row_groups() const noexcept { return meta_.row_groups.size(); }
  [[nodiscard]] std::int64_t row_group_num_rows(std::size_t row_group) const noexcept;
  [[nodiscard]] const std::vector<LeafColumn>& leaves() const noexcept { return leaves_; }
  [[nodiscard]] const FileMeta& metadata() const noexcept { return meta_; }
  [[nodiscard]] std::size_t size_bytes() const noexcept { return size_; }

  /// Column projection by NAME resolves to the leaf index the rest of the API
  /// takes; an unknown name is a SCHEMA_MISMATCH refusal naming the path.
  [[nodiscard]] FileExpected<std::size_t> leaf_index(std::string_view name) const;

  /// The row group's INT64 statistics for one leaf, or `present == false`.
  [[nodiscard]] Int64Stats int64_stats(std::size_t row_group, std::size_t leaf) const;

  /// Row groups whose `leaf` statistics can overlap [open_ms, close_ms), the
  /// port of select_v2::sources::rth_row_groups. Falls back to every row group
  /// when any statistics are missing.
  [[nodiscard]] std::vector<std::size_t> rth_row_groups(std::size_t leaf, std::int64_t open_ms,
                                                        std::int64_t close_ms) const;

  /// Decodes ONE column chunk (leaf `leaf` of row group `row_group`) into
  /// `out`. Returns the row count decoded. `workspace` is reused across calls
  /// and holds the arena and the per-chunk dictionary cache.
  [[nodiscard]] FileExpected<std::int64_t> read_column(std::size_t row_group, std::size_t leaf,
                                                       DecodeWorkspace& workspace,
                                                       ColumnData& out) const;

 private:
  File() = default;

  [[nodiscard]] FileExpected<std::int64_t> decode_data_page(const PageHeader& header,
                                                            const std::uint8_t* body,
                                                            std::size_t body_size,
                                                            const LeafColumn& leaf,
                                                            std::int64_t first_row,
                                                            DecodeWorkspace& workspace,
                                                            ColumnData& out) const;

  [[nodiscard]] FileExpected<std::int64_t> decode_dictionary_page(const PageHeader& header,
                                                                  const std::uint8_t* body,
                                                                  std::size_t body_size,
                                                                  const LeafColumn& leaf,
                                                                  DecodeWorkspace& workspace) const;

  template <class T>
  [[nodiscard]] FileExpected<T> refuse(RefusalCode code, const char* site, const char* what,
                                       std::string detail = {}, std::int64_t context = 0) const {
    return refuse_file<T>(code, site, what, path_, std::move(detail), context);
  }

  std::string path_;
  const std::uint8_t* data_ = nullptr;
  std::size_t size_ = 0;
  FileMeta meta_;
  std::vector<LeafColumn> leaves_;
};

}  // namespace qr::parquet

#endif  // QR_PARQUET_READER_HPP
