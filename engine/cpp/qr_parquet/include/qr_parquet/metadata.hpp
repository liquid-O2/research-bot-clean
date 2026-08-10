// qr_parquet/metadata.hpp — the parquet FileMetaData footer, parsed.
//
// SPEC: design/DESIGN_SUBSTRATE.md M1 qr_parquet bullet ("thrift-compact
// footer", "row-group timestamp statistics exposure for RTH pruning").
// Field ids and struct shapes are parquet.thrift (format 2.9), the same layout
// the WP0 census parser walks (engine/cpp/tools/qr_dialect_census.py).
//
// RAW ENUM VALUES ARE KEPT AS INTEGERS on purpose. An out-of-dialect codec must
// be REFUSED BY NAME; converting it into a C++ enum first would either be
// undefined or would erase the very value the refusal has to report.
#ifndef QR_PARQUET_METADATA_HPP
#define QR_PARQUET_METADATA_HPP

#include <cstdint>
#include <string>
#include <vector>

#include "qr_parquet/dialect.hpp"

namespace qr::parquet {

/// parquet.thrift SchemaElement, DFS order, element 0 is the root.
struct SchemaElement {
  std::int32_t type = kConvertedNone;        // -1 when absent (inner nodes)
  std::int32_t repetition = kConvertedNone;  // -1 when absent (the root)
  std::string name;
  std::int32_t num_children = 0;
  std::int32_t converted = kConvertedNone;
  bool logical_timestamp = false;  // LogicalType union carries TimestampType
};

/// parquet.thrift Statistics, kept as the raw encoded byte strings. Nothing
/// interprets them except the INT64 min/max accessor used for RTH pruning.
struct Statistics {
  bool has_null_count = false;
  std::int64_t null_count = 0;
  bool has_min = false;   // deprecated field 2 (min)
  bool has_max = false;   // deprecated field 1 (max)
  bool has_min_value = false;
  bool has_max_value = false;
  std::string min;
  std::string max;
  std::string min_value;
  std::string max_value;
};

/// parquet.thrift ColumnMetaData for one column chunk of one row group.
struct ColumnChunkMeta {
  std::int32_t type = kConvertedNone;
  std::vector<std::int32_t> encodings;
  std::vector<std::string> path;
  std::int32_t codec = kConvertedNone;
  std::int64_t num_values = 0;
  std::int64_t total_uncompressed_size = 0;
  std::int64_t total_compressed_size = 0;
  std::int64_t data_page_offset = 0;
  bool has_dictionary_page_offset = false;
  std::int64_t dictionary_page_offset = 0;
  bool has_statistics = false;
  Statistics statistics;
};

struct RowGroupMeta {
  std::vector<ColumnChunkMeta> columns;
  std::int64_t total_byte_size = 0;
  std::int64_t num_rows = 0;
};

struct FileMeta {
  std::int32_t version = 0;
  std::vector<SchemaElement> schema;
  std::int64_t num_rows = 0;
  std::vector<RowGroupMeta> row_groups;
  std::string created_by;
};

/// parquet.thrift PageHeader plus the v1/v2 data-page and dictionary-page
/// headers. `header_bytes` is how many bytes the header itself occupied, so the
/// page body starts at (header offset + header_bytes).
struct PageHeader {
  std::int32_t type = kConvertedNone;
  std::int32_t uncompressed_page_size = 0;
  std::int32_t compressed_page_size = 0;
  std::size_t header_bytes = 0;

  // DATA_PAGE (v1)
  std::int32_t v1_num_values = 0;
  std::int32_t v1_encoding = kConvertedNone;
  std::int32_t v1_definition_level_encoding = kConvertedNone;
  std::int32_t v1_repetition_level_encoding = kConvertedNone;

  // DATA_PAGE_V2
  std::int32_t v2_num_values = 0;
  std::int32_t v2_num_nulls = 0;
  std::int32_t v2_num_rows = 0;
  std::int32_t v2_encoding = kConvertedNone;
  std::int32_t v2_definition_levels_byte_length = 0;
  std::int32_t v2_repetition_levels_byte_length = 0;
  bool v2_is_compressed = true;  // parquet.thrift default

  // DICTIONARY_PAGE
  std::int32_t dict_num_values = 0;
  std::int32_t dict_encoding = kConvertedNone;
};

/// Parses a thrift-compact FileMetaData out of `footer`. Returns false and
/// leaves `reason` pointing at a static explanation on malformed bytes.
[[nodiscard]] bool parse_file_metadata(const std::uint8_t* footer, std::size_t size, FileMeta& out,
                                       const char*& reason);

/// Parses one thrift-compact PageHeader starting at `data`. `size` is how many
/// bytes remain in the enclosing column chunk, so a header that runs past the
/// chunk fails instead of reading a neighbour's bytes.
[[nodiscard]] bool parse_page_header(const std::uint8_t* data, std::size_t size, PageHeader& out,
                                     const char*& reason);

}  // namespace qr::parquet

#endif  // QR_PARQUET_METADATA_HPP
