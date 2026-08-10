// qr_parquet/reader.cpp — the dialect-pinned decoder.
//
// SPEC: design/DESIGN_SUBSTRATE.md M1 qr_parquet bullet (see reader.hpp for the
// verbatim text). Encodings implemented, and NOTHING else:
//   * PLAIN                for INT32 / INT64 / DOUBLE / BYTE_ARRAY
//   * RLE                  for definition levels (the RLE/bit-packing hybrid)
//   * RLE_DICTIONARY       for data pages over a PLAIN dictionary page
//   * ZSTD                 for page compression
//   * DataPage v1 and DataPage v2 header shapes
// Anything else — a codec, an encoding, a physical or converted type, a
// repetition, a page type — is a typed FILE refusal naming the path. There is
// no degraded path.
#include "qr_parquet/reader.hpp"

#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <zstd.h>

#include <bit>
#include <cerrno>
#include <cstring>
#include <limits>
#include <utility>

namespace qr::parquet {
namespace {

static_assert(std::endian::native == std::endian::little,
              "qr_parquet decodes PLAIN pages by direct copy; parquet PLAIN is "
              "little-endian and so must the host be");

constexpr std::size_t kMagicBytes = 4;
constexpr std::size_t kFooterTrailerBytes = 8;  // 4-byte footer length + "PAR1"
constexpr std::size_t kMinimumFileBytes = kMagicBytes + kFooterTrailerBytes;
/// A footer larger than this is a corrupt length field, not a real footer. The
/// largest footer in the pinned corpus is ~820KB (the 471-row-group option
/// shard); 256MB is four orders of magnitude of headroom.
constexpr std::uint32_t kMaxFooterBytes = 256U * 1024U * 1024U;

std::int64_t load_i64_le(const std::uint8_t* source) noexcept {
  std::int64_t value = 0;
  std::memcpy(&value, source, sizeof(value));
  return value;
}

/// Decodes exactly `count` values of `bit_width` bits from the RLE/bit-packing
/// hybrid stream in [source, source + size).
///
/// Both run shapes appear in the real corpus. Verified on
/// option_quotes/IWM/2025/2025-01-02/exp2025-01-02.parquet, column `symbol`,
/// row group 0: the definition-level stream is one bit-packed run of 8 followed
/// by one rle-run of 122,872, and the index stream is a bit width of ZERO
/// followed by one rle-run carrying no value bytes at all.
///
/// Returns false when the stream ends before `count` values are produced, which
/// is exactly the "definition level count mismatch" failure.
template <class Out>
bool rle_hybrid_decode(const std::uint8_t* source, std::size_t size, std::uint32_t bit_width,
                       std::size_t count, Out* out) noexcept {
  if (bit_width > 32) {
    return false;
  }
  std::size_t pos = 0;
  std::size_t done = 0;
  const std::uint32_t value_bytes = (bit_width + 7U) / 8U;
  while (done < count) {
    // -- run header (an unsigned varint) --
    std::uint64_t header = 0;
    unsigned shift = 0;
    for (;;) {
      if (pos >= size) {
        return false;
      }
      const std::uint8_t byte = source[pos++];
      header |= static_cast<std::uint64_t>(byte & 0x7FU) << shift;
      if ((byte & 0x80U) == 0) {
        break;
      }
      shift += 7;
      if (shift > 63) {
        return false;
      }
    }

    if ((header & 1U) != 0) {
      // -- bit-packed run: (groups << 1) | 1, eight values per group --
      const std::uint64_t groups = header >> 1U;
      const std::uint64_t values = groups * 8U;
      const std::uint64_t run_bytes = groups * bit_width;
      if (values == 0) {
        return false;  // a run that makes no progress is malformed
      }
      if (run_bytes > size - pos) {
        return false;
      }
      const std::size_t wanted = static_cast<std::size_t>(
          values < static_cast<std::uint64_t>(count - done) ? values : count - done);
      if (bit_width == 0) {
        for (std::size_t index = 0; index < wanted; ++index) {
          out[done + index] = static_cast<Out>(0);
        }
      } else {
        // LSB-first packing: value k occupies bits [k*bit_width, (k+1)*bit_width)
        // of the run's byte stream, counting from the least significant bit of
        // the first byte. bit_width is at most 32, so any single value spans at
        // most five bytes and a five-byte window always lies inside the run.
        const std::uint8_t* run = source + pos;
        const std::uint64_t mask = (std::uint64_t{1} << bit_width) - 1;
        std::uint64_t bit_position = 0;
        for (std::size_t index = 0; index < wanted; ++index) {
          const std::size_t byte_index = static_cast<std::size_t>(bit_position >> 3U);
          const unsigned bit_offset = static_cast<unsigned>(bit_position & 7U);
          const std::size_t window_bytes = (bit_offset + bit_width + 7U) / 8U;
          std::uint64_t window = 0;
          std::memcpy(&window, run + byte_index, window_bytes);
          out[done + index] = static_cast<Out>((window >> bit_offset) & mask);
          bit_position += bit_width;
        }
      }
      pos += static_cast<std::size_t>(run_bytes);
      done += wanted;
    } else {
      // -- rle-run: (run length << 1), one value in ceil(bit_width/8) bytes --
      const std::uint64_t run_length = header >> 1U;
      if (run_length == 0) {
        return false;  // a run that makes no progress is malformed
      }
      if (value_bytes > size - pos) {
        return false;
      }
      std::uint64_t value = 0;
      std::memcpy(&value, source + pos, value_bytes);
      pos += value_bytes;
      const std::size_t wanted = static_cast<std::size_t>(
          run_length < static_cast<std::uint64_t>(count - done) ? run_length : count - done);
      for (std::size_t index = 0; index < wanted; ++index) {
        out[done + index] = static_cast<Out>(value);
      }
      done += wanted;
    }
  }
  return true;
}

/// The number of bits needed to hold `max_value` (0 for max_value == 0). This
/// is how the writer chose the dictionary index width, so it is how the reader
/// must derive the definition-level width.
std::uint32_t bit_width_for(std::uint32_t max_value) noexcept {
  std::uint32_t width = 0;
  while (max_value != 0) {
    ++width;
    max_value >>= 1U;
  }
  return width;
}

}  // namespace

StatisticsCheck verify_against_statistics(const Statistics& statistics, LeafType type,
                                          const ColumnData& column) {
  StatisticsCheck check;
  if (statistics.has_null_count) {
    check.null_count_present = true;
    check.null_count_matches = column.null_count == statistics.null_count;
  }

  const std::string* min_bytes = nullptr;
  const std::string* max_bytes = nullptr;
  if (statistics.has_min_value && statistics.has_max_value) {
    min_bytes = &statistics.min_value;
    max_bytes = &statistics.max_value;
  } else if (statistics.has_min && statistics.has_max) {
    min_bytes = &statistics.min;
    max_bytes = &statistics.max;
  }
  if (min_bytes == nullptr) {
    return check;
  }

  const std::size_t rows = static_cast<std::size_t>(column.num_rows);
  bool any = false;
  switch (type) {
    case LeafType::INT32: {
      if (min_bytes->size() != 4 || max_bytes->size() != 4) {
        return check;
      }
      std::int32_t expected_min = 0;
      std::int32_t expected_max = 0;
      std::memcpy(&expected_min, min_bytes->data(), sizeof(expected_min));
      std::memcpy(&expected_max, max_bytes->data(), sizeof(expected_max));
      std::int32_t low = 0;
      std::int32_t high = 0;
      for (std::size_t row = 0; row < rows; ++row) {
        if (!column.validity.get(row)) continue;
        const std::int32_t value = column.i32[row];
        if (!any || value < low) low = value;
        if (!any || value > high) high = value;
        any = true;
      }
      if (!any) return check;
      check.comparable = true;
      check.min_matches = low == expected_min;
      check.max_matches = high == expected_max;
      return check;
    }
    case LeafType::INT64: {
      if (min_bytes->size() != 8 || max_bytes->size() != 8) {
        return check;
      }
      const std::int64_t expected_min =
          load_i64_le(reinterpret_cast<const std::uint8_t*>(min_bytes->data()));
      const std::int64_t expected_max =
          load_i64_le(reinterpret_cast<const std::uint8_t*>(max_bytes->data()));
      std::int64_t low = 0;
      std::int64_t high = 0;
      for (std::size_t row = 0; row < rows; ++row) {
        if (!column.validity.get(row)) continue;
        const std::int64_t value = column.i64[row];
        if (!any || value < low) low = value;
        if (!any || value > high) high = value;
        any = true;
      }
      if (!any) return check;
      check.comparable = true;
      check.min_matches = low == expected_min;
      check.max_matches = high == expected_max;
      return check;
    }
    case LeafType::DOUBLE: {
      if (min_bytes->size() != 8 || max_bytes->size() != 8) {
        return check;
      }
      double expected_min = 0.0;
      double expected_max = 0.0;
      std::memcpy(&expected_min, min_bytes->data(), sizeof(expected_min));
      std::memcpy(&expected_max, max_bytes->data(), sizeof(expected_max));
      double low = 0.0;
      double high = 0.0;
      for (std::size_t row = 0; row < rows; ++row) {
        if (!column.validity.get(row)) continue;
        const double value = column.f64[row];
        if (value != value) {
          return check;  // a NaN makes min/max writer-dependent; not comparable
        }
        if (!any || value < low) low = value;
        if (!any || value > high) high = value;
        any = true;
      }
      if (!any) return check;
      check.comparable = true;
      check.min_matches = low == expected_min;
      check.max_matches = high == expected_max;
      return check;
    }
    case LeafType::BYTE_ARRAY: {
      // parquet orders BYTE_ARRAY statistics by UNSIGNED byte lexicographic
      // comparison, which is exactly std::string_view's ordering here.
      std::string_view low;
      std::string_view high;
      for (std::size_t row = 0; row < rows; ++row) {
        if (!column.validity.get(row)) continue;
        const std::string_view value = column.byte_array(static_cast<std::int64_t>(row));
        if (!any || value < low) low = value;
        if (!any || value > high) high = value;
        any = true;
      }
      if (!any) return check;
      check.comparable = true;
      check.min_matches = low == *min_bytes;
      check.max_matches = high == *max_bytes;
      return check;
    }
  }
  return check;
}

// ---------------------------------------------------------------------------
// lifetime
// ---------------------------------------------------------------------------

File::File(File&& other) noexcept
    : path_(std::move(other.path_)),
      data_(other.data_),
      size_(other.size_),
      meta_(std::move(other.meta_)),
      leaves_(std::move(other.leaves_)) {
  other.data_ = nullptr;
  other.size_ = 0;
}

File& File::operator=(File&& other) noexcept {
  if (this != &other) {
    if (data_ != nullptr) {
      ::munmap(const_cast<std::uint8_t*>(data_), size_);
    }
    path_ = std::move(other.path_);
    data_ = other.data_;
    size_ = other.size_;
    meta_ = std::move(other.meta_);
    leaves_ = std::move(other.leaves_);
    other.data_ = nullptr;
    other.size_ = 0;
  }
  return *this;
}

File::~File() {
  if (data_ != nullptr) {
    ::munmap(const_cast<std::uint8_t*>(data_), size_);
    data_ = nullptr;
  }
}

// ---------------------------------------------------------------------------
// open: map, parse the footer, gate the whole file
// ---------------------------------------------------------------------------

FileExpected<File> File::open(std::string path) {
  const int fd = ::open(path.c_str(), O_RDONLY | O_CLOEXEC);
  if (fd < 0) {
    return refuse_file<File>(RefusalCode::IO, "qr_parquet::File::open", "cannot open the file",
                             std::move(path), std::string(std::strerror(errno)));
  }
  struct ::stat status = {};
  if (::fstat(fd, &status) != 0) {
    ::close(fd);
    return refuse_file<File>(RefusalCode::IO, "qr_parquet::File::open", "cannot stat the file",
                             std::move(path), std::string(std::strerror(errno)));
  }
  if (status.st_size < 0 || static_cast<std::size_t>(status.st_size) < kMinimumFileBytes) {
    ::close(fd);
    return refuse_file<File>(RefusalCode::DECODE_FAILED, "qr_parquet::File::open",
                             "file is shorter than a parquet header plus footer", std::move(path),
                             {}, static_cast<std::int64_t>(status.st_size));
  }
  const std::size_t size = static_cast<std::size_t>(status.st_size);
  void* mapping = ::mmap(nullptr, size, PROT_READ, MAP_PRIVATE, fd, 0);
  ::close(fd);
  if (mapping == MAP_FAILED) {
    return refuse_file<File>(RefusalCode::IO, "qr_parquet::File::open", "cannot map the file",
                             std::move(path), std::string(std::strerror(errno)));
  }

  File file;
  file.path_ = std::move(path);
  file.data_ = static_cast<const std::uint8_t*>(mapping);
  file.size_ = size;

  // --- magic at BOTH ends ---------------------------------------------------
  if (std::memcmp(file.data_, "PAR1", kMagicBytes) != 0) {
    return file.refuse<File>(RefusalCode::DECODE_FAILED, "qr_parquet::File::open",
                             "leading PAR1 magic is missing");
  }
  if (std::memcmp(file.data_ + size - kMagicBytes, "PAR1", kMagicBytes) != 0) {
    return file.refuse<File>(RefusalCode::DECODE_FAILED, "qr_parquet::File::open",
                             "trailing PAR1 magic is missing");
  }

  // --- footer length --------------------------------------------------------
  std::uint32_t footer_length = 0;
  std::memcpy(&footer_length, file.data_ + size - kFooterTrailerBytes, sizeof(footer_length));
  if (footer_length == 0) {
    return file.refuse<File>(RefusalCode::DECODE_FAILED, "qr_parquet::File::open",
                             "footer length is zero");
  }
  if (footer_length > kMaxFooterBytes) {
    return file.refuse<File>(RefusalCode::DECODE_FAILED, "qr_parquet::File::open",
                             "footer length exceeds the ceiling", {},
                             static_cast<std::int64_t>(footer_length));
  }
  if (static_cast<std::size_t>(footer_length) + kFooterTrailerBytes + kMagicBytes > size) {
    return file.refuse<File>(RefusalCode::DECODE_FAILED, "qr_parquet::File::open",
                             "footer length exceeds the file size", {},
                             static_cast<std::int64_t>(footer_length));
  }

  const char* reason = nullptr;
  if (!parse_file_metadata(file.data_ + size - kFooterTrailerBytes - footer_length, footer_length,
                           file.meta_, reason)) {
    return file.refuse<File>(RefusalCode::DECODE_FAILED, "qr_parquet::File::open",
                             "thrift-compact footer is malformed", std::string(reason));
  }

  // --- the dialect gate: schema --------------------------------------------
  const std::vector<SchemaElement>& schema = file.meta_.schema;
  const SchemaElement& root = schema[0];
  if (root.num_children < 0 ||
      static_cast<std::size_t>(root.num_children) + 1 != schema.size()) {
    return file.refuse<File>(RefusalCode::SCHEMA_MISMATCH, "qr_parquet::File::open",
                             "schema is not flat: the root's child count does not match the "
                             "number of schema elements",
                             {}, static_cast<std::int64_t>(root.num_children));
  }
  file.leaves_.reserve(schema.size() - 1);
  for (std::size_t index = 1; index < schema.size(); ++index) {
    const SchemaElement& element = schema[index];
    if (element.num_children != 0) {
      return file.refuse<File>(RefusalCode::SCHEMA_MISMATCH, "qr_parquet::File::open",
                               "schema is not flat: a leaf carries children", element.name,
                               static_cast<std::int64_t>(element.num_children));
    }
    if (!is_pinned_repetition(element.repetition)) {
      return file.refuse<File>(RefusalCode::SCHEMA_MISMATCH, "qr_parquet::File::open",
                               "repetition is outside the pinned dialect",
                               element.name + " repetition=" +
                                   repetition_name(element.repetition));
    }
    if (!is_pinned_physical(element.type)) {
      return file.refuse<File>(RefusalCode::SCHEMA_MISMATCH, "qr_parquet::File::open",
                               "physical type is outside the pinned dialect",
                               element.name + " physical=" + physical_name(element.type));
    }
    if (!is_pinned_converted(element.converted)) {
      return file.refuse<File>(RefusalCode::SCHEMA_MISMATCH, "qr_parquet::File::open",
                               "converted type is outside the pinned dialect",
                               element.name + " converted=" + converted_name(element.converted));
    }
    LeafColumn leaf;
    leaf.name = element.name;
    switch (element.type) {
      case kTypeInt32: leaf.type = LeafType::INT32; break;
      case kTypeInt64: leaf.type = LeafType::INT64; break;
      case kTypeDouble: leaf.type = LeafType::DOUBLE; break;
      default: leaf.type = LeafType::BYTE_ARRAY; break;
    }
    switch (element.converted) {
      case kConvertedUtf8: leaf.converted = LeafConverted::UTF8; break;
      case kConvertedDate: leaf.converted = LeafConverted::DATE; break;
      case kConvertedUint32: leaf.converted = LeafConverted::UINT_32; break;
      case kConvertedInt8: leaf.converted = LeafConverted::INT_8; break;
      default: leaf.converted = LeafConverted::NONE; break;
    }
    leaf.optional = element.repetition == kRepetitionOptional;
    leaf.logical_timestamp = element.logical_timestamp;
    file.leaves_.push_back(std::move(leaf));
  }

  // --- the dialect gate: every column chunk of every row group --------------
  // Gating the WHOLE file at open time is deliberate: a projection must not be
  // able to dodge the wall by declining to read the offending column.
  for (std::size_t group = 0; group < file.meta_.row_groups.size(); ++group) {
    const RowGroupMeta& row_group = file.meta_.row_groups[group];
    if (row_group.columns.size() != file.leaves_.size()) {
      return file.refuse<File>(RefusalCode::SCHEMA_MISMATCH, "qr_parquet::File::open",
                               "row group column count does not match the leaf count", {},
                               static_cast<std::int64_t>(row_group.columns.size()));
    }
    for (std::size_t leaf = 0; leaf < row_group.columns.size(); ++leaf) {
      const ColumnChunkMeta& chunk = row_group.columns[leaf];
      const LeafColumn& column = file.leaves_[leaf];
      if (!is_pinned_codec(chunk.codec)) {
        return file.refuse<File>(RefusalCode::SCHEMA_MISMATCH, "qr_parquet::File::open",
                                 "compression codec is outside the pinned dialect",
                                 column.name + " codec=" + codec_name(chunk.codec),
                                 static_cast<std::int64_t>(group));
      }
      for (std::int32_t encoding : chunk.encodings) {
        if (!is_pinned_encoding(encoding)) {
          return file.refuse<File>(RefusalCode::SCHEMA_MISMATCH, "qr_parquet::File::open",
                                   "column chunk encoding is outside the pinned dialect",
                                   column.name + " encoding=" + encoding_name(encoding),
                                   static_cast<std::int64_t>(group));
        }
      }
      if (chunk.path.size() != 1) {
        return file.refuse<File>(RefusalCode::SCHEMA_MISMATCH, "qr_parquet::File::open",
                                 "column chunk path is not a flat single element", column.name,
                                 static_cast<std::int64_t>(chunk.path.size()));
      }
      if (chunk.path[0] != column.name) {
        return file.refuse<File>(RefusalCode::SCHEMA_MISMATCH, "qr_parquet::File::open",
                                 "column chunk does not sit at its schema leaf",
                                 chunk.path[0] + " != " + column.name,
                                 static_cast<std::int64_t>(group));
      }
      if (!is_pinned_physical(chunk.type)) {
        return file.refuse<File>(RefusalCode::SCHEMA_MISMATCH, "qr_parquet::File::open",
                                 "column chunk physical type is outside the pinned dialect",
                                 column.name + " physical=" + physical_name(chunk.type),
                                 static_cast<std::int64_t>(group));
      }
      if (chunk.num_values != row_group.num_rows) {
        return file.refuse<File>(RefusalCode::SCHEMA_MISMATCH, "qr_parquet::File::open",
                                 "column chunk value count does not match the row group",
                                 column.name, chunk.num_values);
      }
      // Byte range of the chunk, checked once here so decoding never has to
      // wonder whether the mapping covers it.
      const std::int64_t start =
          chunk.has_dictionary_page_offset ? chunk.dictionary_page_offset : chunk.data_page_offset;
      if (start < static_cast<std::int64_t>(kMagicBytes) || chunk.total_compressed_size < 0) {
        return file.refuse<File>(RefusalCode::DECODE_FAILED, "qr_parquet::File::open",
                                 "column chunk starts outside the file body", column.name, start);
      }
      const std::int64_t end = start + chunk.total_compressed_size;
      if (end > static_cast<std::int64_t>(size - kFooterTrailerBytes)) {
        return file.refuse<File>(RefusalCode::DECODE_FAILED, "qr_parquet::File::open",
                                 "column chunk runs past the file body", column.name, end);
      }
      if (chunk.has_dictionary_page_offset && chunk.dictionary_page_offset > chunk.data_page_offset) {
        return file.refuse<File>(RefusalCode::DECODE_FAILED, "qr_parquet::File::open",
                                 "dictionary page is declared after the first data page",
                                 column.name, chunk.dictionary_page_offset);
      }
    }
  }
  return file;
}

// ---------------------------------------------------------------------------
// metadata accessors
// ---------------------------------------------------------------------------

std::int64_t File::row_group_num_rows(std::size_t row_group) const noexcept {
  if (row_group >= meta_.row_groups.size()) {
    return 0;
  }
  return meta_.row_groups[row_group].num_rows;
}

FileExpected<std::size_t> File::leaf_index(std::string_view name) const {
  for (std::size_t index = 0; index < leaves_.size(); ++index) {
    if (leaves_[index].name == name) {
      return index;
    }
  }
  return refuse<std::size_t>(RefusalCode::SCHEMA_MISMATCH, "qr_parquet::File::leaf_index",
                             "the file carries no such column", std::string(name));
}

Int64Stats File::int64_stats(std::size_t row_group, std::size_t leaf) const {
  Int64Stats stats;
  if (row_group >= meta_.row_groups.size() || leaf >= leaves_.size()) {
    return stats;
  }
  if (leaves_[leaf].type != LeafType::INT64) {
    return stats;
  }
  const ColumnChunkMeta& chunk = meta_.row_groups[row_group].columns[leaf];
  if (!chunk.has_statistics) {
    return stats;
  }
  const Statistics& source = chunk.statistics;
  stats.has_null_count = source.has_null_count;
  stats.null_count = source.null_count;
  // min_value/max_value (fields 5/6) are the current spelling; min/max (fields
  // 1/2) are the deprecated one. Prefer the current, fall back to the old.
  const std::string* min_bytes = nullptr;
  const std::string* max_bytes = nullptr;
  if (source.has_min_value && source.has_max_value) {
    min_bytes = &source.min_value;
    max_bytes = &source.max_value;
  } else if (source.has_min && source.has_max) {
    min_bytes = &source.min;
    max_bytes = &source.max;
  }
  if (min_bytes == nullptr || min_bytes->size() != sizeof(std::int64_t) ||
      max_bytes->size() != sizeof(std::int64_t)) {
    return stats;
  }
  stats.min = load_i64_le(reinterpret_cast<const std::uint8_t*>(min_bytes->data()));
  stats.max = load_i64_le(reinterpret_cast<const std::uint8_t*>(max_bytes->data()));
  stats.present = true;
  return stats;
}

std::vector<std::size_t> File::rth_row_groups(std::size_t leaf, std::int64_t open_ms,
                                              std::int64_t close_ms) const {
  const std::size_t total = meta_.row_groups.size();
  std::vector<std::size_t> keep;
  keep.reserve(total);
  for (std::size_t group = 0; group < total; ++group) {
    const Int64Stats stats = int64_stats(group, leaf);
    if (!stats.present) {
      // Pruning is a speed lever, never a correctness one: one missing statistic
      // and every row group is kept.
      keep.clear();
      for (std::size_t all = 0; all < total; ++all) {
        keep.push_back(all);
      }
      return keep;
    }
    if (stats.max >= open_ms && stats.min < close_ms) {
      keep.push_back(group);
    }
  }
  return keep;
}

// ---------------------------------------------------------------------------
// decode
// ---------------------------------------------------------------------------

FileExpected<std::int64_t> File::read_column(std::size_t row_group, std::size_t leaf,
                                             DecodeWorkspace& workspace, ColumnData& out) const {
  if (row_group >= meta_.row_groups.size()) {
    return refuse<std::int64_t>(RefusalCode::CONFIG, "qr_parquet::File::read_column",
                                "row group index is out of range", {},
                                static_cast<std::int64_t>(row_group));
  }
  if (leaf >= leaves_.size()) {
    return refuse<std::int64_t>(RefusalCode::CONFIG, "qr_parquet::File::read_column",
                                "leaf index is out of range", {},
                                static_cast<std::int64_t>(leaf));
  }
  const RowGroupMeta& group = meta_.row_groups[row_group];
  const ColumnChunkMeta& chunk = group.columns[leaf];
  const LeafColumn& column = leaves_[leaf];

  out.reset(column.type, chunk.num_values);
  workspace.dictionary.clear();

  const std::size_t chunk_start = static_cast<std::size_t>(
      chunk.has_dictionary_page_offset ? chunk.dictionary_page_offset : chunk.data_page_offset);
  const std::size_t chunk_end =
      chunk_start + static_cast<std::size_t>(chunk.total_compressed_size);

  std::int64_t rows_done = 0;
  std::size_t position = chunk_start;
  while (position < chunk_end) {
    PageHeader header;
    const char* reason = nullptr;
    if (!parse_page_header(data_ + position, chunk_end - position, header, reason)) {
      return refuse<std::int64_t>(RefusalCode::DECODE_FAILED, "qr_parquet::File::read_column",
                                  "page header is malformed",
                                  column.name + ": " + std::string(reason),
                                  static_cast<std::int64_t>(position));
    }
    const std::size_t body_start = position + header.header_bytes;
    const std::size_t body_size = static_cast<std::size_t>(header.compressed_page_size);
    if (body_size > chunk_end - body_start) {
      return refuse<std::int64_t>(RefusalCode::DECODE_FAILED, "qr_parquet::File::read_column",
                                  "page runs past the end of its column chunk", column.name,
                                  static_cast<std::int64_t>(body_start + body_size));
    }
    const std::uint8_t* body = data_ + body_start;

    if (header.type == kPageDictionary) {
      FileExpected<std::int64_t> decoded =
          decode_dictionary_page(header, body, body_size, column, workspace);
      if (!decoded) {
        return decoded;
      }
    } else if (header.type == kPageDataV1 || header.type == kPageDataV2) {
      FileExpected<std::int64_t> decoded =
          decode_data_page(header, body, body_size, column, rows_done, workspace, out);
      if (!decoded) {
        return decoded;
      }
      rows_done += decoded.value();
      if (rows_done > chunk.num_values) {
        return refuse<std::int64_t>(RefusalCode::DECODE_FAILED, "qr_parquet::File::read_column",
                                    "column chunk delivered more rows than it declares",
                                    column.name, rows_done);
      }
    } else {
      return refuse<std::int64_t>(RefusalCode::SCHEMA_MISMATCH, "qr_parquet::File::read_column",
                                  "page type is outside the pinned dialect", column.name,
                                  static_cast<std::int64_t>(header.type));
    }
    position = body_start + body_size;
  }

  if (rows_done != chunk.num_values) {
    return refuse<std::int64_t>(RefusalCode::DECODE_FAILED, "qr_parquet::File::read_column",
                                "column chunk delivered fewer rows than it declares", column.name,
                                rows_done);
  }
  return rows_done;
}

FileExpected<std::int64_t> File::decode_dictionary_page(const PageHeader& header,
                                                        const std::uint8_t* body,
                                                        std::size_t body_size,
                                                        const LeafColumn& leaf,
                                                        DecodeWorkspace& workspace) const {
  if (header.dict_encoding != kEncodingPlain) {
    return refuse<std::int64_t>(RefusalCode::SCHEMA_MISMATCH,
                                "qr_parquet::File::decode_dictionary_page",
                                "dictionary page encoding is outside the pinned dialect",
                                leaf.name + " encoding=" + encoding_name(header.dict_encoding));
  }
  if (workspace.dictionary.present) {
    return refuse<std::int64_t>(RefusalCode::DECODE_FAILED,
                                "qr_parquet::File::decode_dictionary_page",
                                "column chunk carries more than one dictionary page", leaf.name);
  }
  if (header.dict_num_values < 0) {
    return refuse<std::int64_t>(RefusalCode::DECODE_FAILED,
                                "qr_parquet::File::decode_dictionary_page",
                                "dictionary page declares a negative value count", leaf.name,
                                header.dict_num_values);
  }

  const std::size_t raw_size = static_cast<std::size_t>(header.uncompressed_page_size);
  std::uint8_t* raw = workspace.arena.page(raw_size == 0 ? 1 : raw_size);
  const std::size_t produced = ZSTD_decompress(raw, raw_size, body, body_size);
  if (ZSTD_isError(produced) != 0 || produced != raw_size) {
    return refuse<std::int64_t>(RefusalCode::DECODE_FAILED,
                                "qr_parquet::File::decode_dictionary_page",
                                "ZSTD dictionary page did not decompress to its declared size",
                                leaf.name, static_cast<std::int64_t>(raw_size));
  }

  DictionaryCache& dictionary = workspace.dictionary;
  const std::size_t count = static_cast<std::size_t>(header.dict_num_values);
  dictionary.type = leaf.type;
  dictionary.count = count;

  switch (leaf.type) {
    case LeafType::INT32:
    case LeafType::INT64:
    case LeafType::DOUBLE: {
      const std::size_t width = leaf.type == LeafType::INT32 ? 4U : 8U;
      if (count * width != raw_size) {
        return refuse<std::int64_t>(RefusalCode::DECODE_FAILED,
                                    "qr_parquet::File::decode_dictionary_page",
                                    "PLAIN dictionary size does not match its value count",
                                    leaf.name, static_cast<std::int64_t>(raw_size));
      }
      if (leaf.type == LeafType::INT32) {
        dictionary.i32.resize(count);
        std::memcpy(dictionary.i32.data(), raw, count * width);
      } else if (leaf.type == LeafType::INT64) {
        dictionary.i64.resize(count);
        std::memcpy(dictionary.i64.data(), raw, count * width);
      } else {
        dictionary.f64.resize(count);
        std::memcpy(dictionary.f64.data(), raw, count * width);
      }
      break;
    }
    case LeafType::BYTE_ARRAY: {
      dictionary.offsets.resize(count + 1);
      dictionary.bytes.clear();
      dictionary.bytes.reserve(raw_size);
      std::size_t cursor = 0;
      for (std::size_t index = 0; index < count; ++index) {
        dictionary.offsets[index] = static_cast<std::uint32_t>(dictionary.bytes.size());
        if (raw_size - cursor < 4) {
          return refuse<std::int64_t>(RefusalCode::DECODE_FAILED,
                                      "qr_parquet::File::decode_dictionary_page",
                                      "PLAIN dictionary ends inside a length prefix", leaf.name,
                                      static_cast<std::int64_t>(index));
        }
        std::uint32_t length = 0;
        std::memcpy(&length, raw + cursor, sizeof(length));
        cursor += 4;
        if (static_cast<std::size_t>(length) > raw_size - cursor) {
          return refuse<std::int64_t>(RefusalCode::DECODE_FAILED,
                                      "qr_parquet::File::decode_dictionary_page",
                                      "PLAIN dictionary value runs past the page", leaf.name,
                                      static_cast<std::int64_t>(index));
        }
        dictionary.bytes.insert(dictionary.bytes.end(), raw + cursor, raw + cursor + length);
        cursor += length;
      }
      dictionary.offsets[count] = static_cast<std::uint32_t>(dictionary.bytes.size());
      if (cursor != raw_size) {
        return refuse<std::int64_t>(RefusalCode::DECODE_FAILED,
                                    "qr_parquet::File::decode_dictionary_page",
                                    "PLAIN dictionary has trailing bytes", leaf.name,
                                    static_cast<std::int64_t>(raw_size - cursor));
      }
      break;
    }
  }
  dictionary.present = true;
  return static_cast<std::int64_t>(count);
}

FileExpected<std::int64_t> File::decode_data_page(const PageHeader& header,
                                                  const std::uint8_t* body, std::size_t body_size,
                                                  const LeafColumn& leaf, std::int64_t first_row,
                                                  DecodeWorkspace& workspace,
                                                  ColumnData& out) const {
  const bool is_v2 = header.type == kPageDataV2;
  const std::int32_t declared_values = is_v2 ? header.v2_num_values : header.v1_num_values;
  const std::int32_t encoding = is_v2 ? header.v2_encoding : header.v1_encoding;

  if (declared_values < 0) {
    return refuse<std::int64_t>(RefusalCode::DECODE_FAILED, "qr_parquet::File::decode_data_page",
                                "data page declares a negative value count", leaf.name,
                                declared_values);
  }
  if (encoding != kEncodingPlain && encoding != kEncodingRleDictionary) {
    return refuse<std::int64_t>(RefusalCode::SCHEMA_MISMATCH,
                                "qr_parquet::File::decode_data_page",
                                "data page encoding is outside the pinned dialect",
                                leaf.name + " encoding=" + encoding_name(encoding));
  }
  if (!is_v2 && leaf.optional && header.v1_definition_level_encoding != kEncodingRle) {
    return refuse<std::int64_t>(
        RefusalCode::SCHEMA_MISMATCH, "qr_parquet::File::decode_data_page",
        "definition level encoding is outside the pinned dialect",
        leaf.name + " encoding=" + encoding_name(header.v1_definition_level_encoding));
  }
  if (is_v2 && header.v2_repetition_levels_byte_length != 0) {
    return refuse<std::int64_t>(RefusalCode::SCHEMA_MISMATCH,
                                "qr_parquet::File::decode_data_page",
                                "data page carries repetition levels; the dialect is flat only",
                                leaf.name,
                                static_cast<std::int64_t>(header.v2_repetition_levels_byte_length));
  }
  if (is_v2 && !header.v2_is_compressed) {
    return refuse<std::int64_t>(RefusalCode::SCHEMA_MISMATCH,
                                "qr_parquet::File::decode_data_page",
                                "uncompressed v2 data page; the dialect pins ZSTD", leaf.name);
  }

  const std::size_t rows = static_cast<std::size_t>(declared_values);
  if (static_cast<std::size_t>(first_row) + rows > static_cast<std::size_t>(out.num_rows)) {
    return refuse<std::int64_t>(RefusalCode::DECODE_FAILED, "qr_parquet::File::decode_data_page",
                                "data page would write past the end of its column chunk",
                                leaf.name, static_cast<std::int64_t>(rows));
  }

  // --- levels and values, decompressed --------------------------------------
  const std::uint8_t* level_bytes = nullptr;
  std::size_t level_size = 0;
  const std::uint8_t* value_bytes = nullptr;
  std::size_t value_size = 0;

  if (is_v2) {
    // v2: the level bytes sit in front of the page, UNCOMPRESSED; only the
    // values are compressed.
    const std::size_t def_size = static_cast<std::size_t>(header.v2_definition_levels_byte_length);
    if (def_size > body_size) {
      return refuse<std::int64_t>(RefusalCode::DECODE_FAILED,
                                  "qr_parquet::File::decode_data_page",
                                  "v2 definition level block runs past the page", leaf.name,
                                  static_cast<std::int64_t>(def_size));
    }
    level_bytes = body;
    level_size = def_size;
    const std::size_t compressed_values = body_size - def_size;
    const std::size_t raw_values =
        static_cast<std::size_t>(header.uncompressed_page_size) >= def_size
            ? static_cast<std::size_t>(header.uncompressed_page_size) - def_size
            : 0;
    std::uint8_t* raw = workspace.arena.page(raw_values == 0 ? 1 : raw_values);
    const std::size_t produced =
        ZSTD_decompress(raw, raw_values, body + def_size, compressed_values);
    if (ZSTD_isError(produced) != 0 || produced != raw_values) {
      return refuse<std::int64_t>(RefusalCode::DECODE_FAILED,
                                  "qr_parquet::File::decode_data_page",
                                  "ZSTD v2 data page did not decompress to its declared size",
                                  leaf.name, static_cast<std::int64_t>(raw_values));
    }
    value_bytes = raw;
    value_size = raw_values;
  } else {
    const std::size_t raw_size = static_cast<std::size_t>(header.uncompressed_page_size);
    std::uint8_t* raw = workspace.arena.page(raw_size == 0 ? 1 : raw_size);
    const std::size_t produced = ZSTD_decompress(raw, raw_size, body, body_size);
    if (ZSTD_isError(produced) != 0 || produced != raw_size) {
      return refuse<std::int64_t>(RefusalCode::DECODE_FAILED,
                                  "qr_parquet::File::decode_data_page",
                                  "ZSTD v1 data page did not decompress to its declared size",
                                  leaf.name, static_cast<std::int64_t>(raw_size));
    }
    if (leaf.optional) {
      // v1: a 4-byte little-endian length prefix, then the RLE level block,
      // then the values -- all inside the same compressed page.
      if (raw_size < 4) {
        return refuse<std::int64_t>(RefusalCode::DECODE_FAILED,
                                    "qr_parquet::File::decode_data_page",
                                    "v1 data page is too small to carry a level length prefix",
                                    leaf.name, static_cast<std::int64_t>(raw_size));
      }
      std::uint32_t declared_level_size = 0;
      std::memcpy(&declared_level_size, raw, sizeof(declared_level_size));
      if (static_cast<std::size_t>(declared_level_size) > raw_size - 4) {
        return refuse<std::int64_t>(RefusalCode::DECODE_FAILED,
                                    "qr_parquet::File::decode_data_page",
                                    "v1 definition level block runs past the page", leaf.name,
                                    static_cast<std::int64_t>(declared_level_size));
      }
      level_bytes = raw + 4;
      level_size = declared_level_size;
      value_bytes = raw + 4 + declared_level_size;
      value_size = raw_size - 4 - declared_level_size;
    } else {
      value_bytes = raw;
      value_size = raw_size;
    }
  }

  // --- definition levels -> validity ---------------------------------------
  std::size_t present_count = rows;
  std::uint8_t* levels = nullptr;
  if (leaf.optional) {
    levels = workspace.arena.levels(rows);
    if (!rle_hybrid_decode<std::uint8_t>(level_bytes, level_size, bit_width_for(1), rows, levels)) {
      return refuse<std::int64_t>(RefusalCode::DECODE_FAILED,
                                  "qr_parquet::File::decode_data_page",
                                  "definition level stream ends before the page's value count",
                                  leaf.name, static_cast<std::int64_t>(rows));
    }
    present_count = 0;
    for (std::size_t index = 0; index < rows; ++index) {
      if (levels[index] > 1) {
        return refuse<std::int64_t>(RefusalCode::DECODE_FAILED,
                                    "qr_parquet::File::decode_data_page",
                                    "definition level exceeds the flat maximum of 1", leaf.name,
                                    static_cast<std::int64_t>(levels[index]));
      }
      present_count += levels[index];
    }
    if (is_v2 && static_cast<std::int64_t>(rows - present_count) != header.v2_num_nulls) {
      return refuse<std::int64_t>(
          RefusalCode::DECODE_FAILED, "qr_parquet::File::decode_data_page",
          "v2 definition levels disagree with the page header's null count", leaf.name,
          static_cast<std::int64_t>(rows - present_count));
    }
    out.null_count += static_cast<std::int64_t>(rows - present_count);
  }

  const bool all_present = present_count == rows;
  if (all_present) {
    out.validity.set_range(static_cast<std::size_t>(first_row),
                           static_cast<std::size_t>(first_row) + rows);
  } else {
    for (std::size_t index = 0; index < rows; ++index) {
      if (levels[index] != 0) {
        out.validity.set(static_cast<std::size_t>(first_row) + index);
      }
    }
  }

  // --- values ---------------------------------------------------------------
  if (encoding == kEncodingRleDictionary) {
    if (!workspace.dictionary.present) {
      return refuse<std::int64_t>(RefusalCode::DECODE_FAILED,
                                  "qr_parquet::File::decode_data_page",
                                  "RLE_DICTIONARY page without a dictionary page", leaf.name);
    }
    if (value_size < 1) {
      return refuse<std::int64_t>(RefusalCode::DECODE_FAILED,
                                  "qr_parquet::File::decode_data_page",
                                  "RLE_DICTIONARY page carries no bit-width byte", leaf.name);
    }
    const std::uint32_t index_width = value_bytes[0];
    std::uint32_t* indices = workspace.arena.indices(present_count == 0 ? 1 : present_count);
    if (!rle_hybrid_decode<std::uint32_t>(value_bytes + 1, value_size - 1, index_width,
                                          present_count, indices)) {
      return refuse<std::int64_t>(RefusalCode::DECODE_FAILED,
                                  "qr_parquet::File::decode_data_page",
                                  "dictionary index stream ends before the page's value count",
                                  leaf.name, static_cast<std::int64_t>(present_count));
    }
    const DictionaryCache& dictionary = workspace.dictionary;
    const std::size_t dictionary_count = dictionary.count;
    std::size_t taken = 0;
    for (std::size_t index = 0; index < rows; ++index) {
      if (!all_present && levels[index] == 0) {
        continue;
      }
      const std::uint32_t entry = indices[taken];
      if (static_cast<std::size_t>(entry) >= dictionary_count) {
        return refuse<std::int64_t>(RefusalCode::DECODE_FAILED,
                                    "qr_parquet::File::decode_data_page",
                                    "dictionary index is outside the dictionary", leaf.name,
                                    static_cast<std::int64_t>(entry));
      }
      const std::size_t row = static_cast<std::size_t>(first_row) + index;
      switch (leaf.type) {
        case LeafType::INT32: out.i32[row] = dictionary.i32[entry]; break;
        case LeafType::INT64: out.i64[row] = dictionary.i64[entry]; break;
        case LeafType::DOUBLE: out.f64[row] = dictionary.f64[entry]; break;
        case LeafType::BYTE_ARRAY: {
          const std::uint32_t begin = dictionary.offsets[entry];
          const std::uint32_t end = dictionary.offsets[entry + 1];
          out.bytes.insert(out.bytes.end(), dictionary.bytes.data() + begin,
                           dictionary.bytes.data() + end);
          break;
        }
      }
      ++taken;
    }
    if (leaf.type == LeafType::BYTE_ARRAY) {
      // Per-row ends. A null row gets a zero-length slice in place, so row i is
      // always [offsets[i], offsets[i+1]) whether or not it carries a value.
      std::size_t cursor = out.offsets[static_cast<std::size_t>(first_row)];
      std::size_t consumed = 0;
      for (std::size_t index = 0; index < rows; ++index) {
        const std::size_t row = static_cast<std::size_t>(first_row) + index;
        if (all_present || levels[index] != 0) {
          const std::uint32_t entry = indices[consumed++];
          cursor += static_cast<std::size_t>(dictionary.offsets[entry + 1] -
                                             dictionary.offsets[entry]);
        }
        out.offsets[row + 1] = static_cast<std::uint32_t>(cursor);
      }
      if (out.bytes.size() > std::numeric_limits<std::uint32_t>::max()) {
        return refuse<std::int64_t>(RefusalCode::ARITHMETIC_OVERFLOW,
                                    "qr_parquet::File::decode_data_page",
                                    "byte-array column chunk exceeds the 32-bit offset space",
                                    leaf.name, static_cast<std::int64_t>(out.bytes.size()));
      }
    }
    return static_cast<std::int64_t>(rows);
  }

  // PLAIN
  switch (leaf.type) {
    case LeafType::INT32:
    case LeafType::INT64:
    case LeafType::DOUBLE: {
      const std::size_t width = leaf.type == LeafType::INT32 ? 4U : 8U;
      if (present_count * width > value_size) {
        return refuse<std::int64_t>(RefusalCode::DECODE_FAILED,
                                    "qr_parquet::File::decode_data_page",
                                    "PLAIN value block is shorter than the page's value count",
                                    leaf.name, static_cast<std::int64_t>(value_size));
      }
      void* destination = nullptr;
      switch (leaf.type) {
        case LeafType::INT32: destination = out.i32.data() + first_row; break;
        case LeafType::INT64: destination = out.i64.data() + first_row; break;
        default: destination = out.f64.data() + first_row; break;
      }
      if (all_present) {
        std::memcpy(destination, value_bytes, rows * width);
      } else {
        auto* target = static_cast<std::uint8_t*>(destination);
        std::size_t taken = 0;
        for (std::size_t index = 0; index < rows; ++index) {
          if (levels[index] == 0) {
            continue;
          }
          std::memcpy(target + index * width, value_bytes + taken * width, width);
          ++taken;
        }
      }
      break;
    }
    case LeafType::BYTE_ARRAY: {
      std::size_t cursor = 0;
      for (std::size_t index = 0; index < rows; ++index) {
        const std::size_t row = static_cast<std::size_t>(first_row) + index;
        if (!all_present && levels[index] == 0) {
          out.offsets[row + 1] = static_cast<std::uint32_t>(out.bytes.size());
          continue;
        }
        if (value_size - cursor < 4) {
          return refuse<std::int64_t>(RefusalCode::DECODE_FAILED,
                                      "qr_parquet::File::decode_data_page",
                                      "PLAIN page ends inside a byte-array length prefix",
                                      leaf.name, static_cast<std::int64_t>(index));
        }
        std::uint32_t length = 0;
        std::memcpy(&length, value_bytes + cursor, sizeof(length));
        cursor += 4;
        if (static_cast<std::size_t>(length) > value_size - cursor) {
          return refuse<std::int64_t>(RefusalCode::DECODE_FAILED,
                                      "qr_parquet::File::decode_data_page",
                                      "PLAIN byte-array value runs past the page", leaf.name,
                                      static_cast<std::int64_t>(index));
        }
        out.bytes.insert(out.bytes.end(), value_bytes + cursor, value_bytes + cursor + length);
        cursor += length;
        out.offsets[row + 1] = static_cast<std::uint32_t>(out.bytes.size());
      }
      if (out.bytes.size() > std::numeric_limits<std::uint32_t>::max()) {
        return refuse<std::int64_t>(RefusalCode::ARITHMETIC_OVERFLOW,
                                    "qr_parquet::File::decode_data_page",
                                    "byte-array column chunk exceeds the 32-bit offset space",
                                    leaf.name, static_cast<std::int64_t>(out.bytes.size()));
      }
      break;
    }
  }
  return static_cast<std::int64_t>(rows);
}

}  // namespace qr::parquet
