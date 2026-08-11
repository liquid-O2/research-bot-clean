// Footer and page-header parsing. Ported field-for-field from the WP0 census
// parser engine/cpp/tools/qr_dialect_census.py (parse_schema_element,
// parse_column_metadata, parse_column_chunk, parse_row_group,
// parse_file_metadata), extended with the fields a decoder needs and the WP0
// tool deliberately never read: page offsets, sizes, and statistics bytes.
#include "qr_parquet/metadata.hpp"

#include <limits>

#include "qr_parquet/thrift.hpp"

namespace qr::parquet {
namespace {

using thrift::Reader;
using thrift::StructScope;

/// parquet.thrift LogicalType union: field 8 is TimestampType.
constexpr std::int16_t kLogicalTimestampField = 8;

bool read_i32(Reader& reader, std::uint8_t field_type, std::int32_t& out) {
  std::int64_t wide = 0;
  if (!reader.integer(field_type, wide)) {
    return false;
  }
  if (wide < std::numeric_limits<std::int32_t>::min() ||
      wide > std::numeric_limits<std::int32_t>::max()) {
    reader.fail("parquet i32 field outside the i32 range");
    return false;
  }
  out = static_cast<std::int32_t>(wide);
  return true;
}

bool parse_schema_element(Reader& reader, SchemaElement& out) {
  StructScope scope(reader);
  std::int16_t field_id = 0;
  std::uint8_t field_type = 0;
  while (scope.next(field_id, field_type)) {
    switch (field_id) {
      case 1:
        if (!read_i32(reader, field_type, out.type)) return false;
        break;
      case 3:
        if (!read_i32(reader, field_type, out.repetition)) return false;
        break;
      case 4:
        if (!reader.binary(out.name)) return false;
        break;
      case 5:
        if (!read_i32(reader, field_type, out.num_children)) return false;
        break;
      case 6:
        if (!read_i32(reader, field_type, out.converted)) return false;
        break;
      case 10: {
        if (field_type != thrift::kStruct) {
          if (!reader.skip(field_type)) return false;
          break;
        }
        StructScope logical(reader);
        std::int16_t logical_id = 0;
        std::uint8_t logical_type = 0;
        while (logical.next(logical_id, logical_type)) {
          if (logical_id == kLogicalTimestampField) {
            out.logical_timestamp = true;
          }
          if (!reader.skip(logical_type)) return false;
        }
        if (!reader.ok()) return false;
        break;
      }
      default:
        if (!reader.skip(field_type)) return false;
        break;
    }
  }
  return reader.ok();
}

bool parse_statistics(Reader& reader, Statistics& out) {
  StructScope scope(reader);
  std::int16_t field_id = 0;
  std::uint8_t field_type = 0;
  while (scope.next(field_id, field_type)) {
    switch (field_id) {
      case 1:
        if (!reader.binary(out.max)) return false;
        out.has_max = true;
        break;
      case 2:
        if (!reader.binary(out.min)) return false;
        out.has_min = true;
        break;
      case 3:
        if (!reader.integer(field_type, out.null_count)) return false;
        out.has_null_count = true;
        break;
      case 5:
        if (!reader.binary(out.max_value)) return false;
        out.has_max_value = true;
        break;
      case 6:
        if (!reader.binary(out.min_value)) return false;
        out.has_min_value = true;
        break;
      default:
        if (!reader.skip(field_type)) return false;
        break;
    }
  }
  return reader.ok();
}

bool parse_column_metadata(Reader& reader, ColumnChunkMeta& out) {
  StructScope scope(reader);
  std::int16_t field_id = 0;
  std::uint8_t field_type = 0;
  while (scope.next(field_id, field_type)) {
    switch (field_id) {
      case 1:
        if (!read_i32(reader, field_type, out.type)) return false;
        break;
      case 2: {
        if (field_type != thrift::kList) {
          if (!reader.skip(field_type)) return false;
          break;
        }
        std::uint32_t count = 0;
        std::uint8_t element = 0;
        if (!reader.list_header(count, element)) return false;
        out.encodings.reserve(count);
        for (std::uint32_t index = 0; index < count; ++index) {
          std::int32_t encoding = 0;
          if (element == thrift::kI16 || element == thrift::kI32 || element == thrift::kI64 ||
              element == thrift::kByte) {
            if (!read_i32(reader, element, encoding)) return false;
            out.encodings.push_back(encoding);
          } else {
            if (!reader.skip(element)) return false;
          }
        }
        break;
      }
      case 3: {
        if (field_type != thrift::kList) {
          if (!reader.skip(field_type)) return false;
          break;
        }
        std::uint32_t count = 0;
        std::uint8_t element = 0;
        if (!reader.list_header(count, element)) return false;
        out.path.reserve(count);
        for (std::uint32_t index = 0; index < count; ++index) {
          if (element == thrift::kBinary) {
            std::string part;
            if (!reader.binary(part)) return false;
            out.path.push_back(std::move(part));
          } else {
            if (!reader.skip(element)) return false;
          }
        }
        break;
      }
      case 4:
        if (!read_i32(reader, field_type, out.codec)) return false;
        break;
      case 5:
        if (!reader.integer(field_type, out.num_values)) return false;
        break;
      case 6:
        if (!reader.integer(field_type, out.total_uncompressed_size)) return false;
        break;
      case 7:
        if (!reader.integer(field_type, out.total_compressed_size)) return false;
        break;
      case 9:
        if (!reader.integer(field_type, out.data_page_offset)) return false;
        break;
      case 11:
        if (!reader.integer(field_type, out.dictionary_page_offset)) return false;
        out.has_dictionary_page_offset = true;
        break;
      case 12:
        if (field_type != thrift::kStruct) {
          if (!reader.skip(field_type)) return false;
          break;
        }
        if (!parse_statistics(reader, out.statistics)) return false;
        out.has_statistics = true;
        break;
      default:
        if (!reader.skip(field_type)) return false;
        break;
    }
  }
  return reader.ok();
}

bool parse_column_chunk(Reader& reader, ColumnChunkMeta& out, bool& saw_metadata) {
  StructScope scope(reader);
  std::int16_t field_id = 0;
  std::uint8_t field_type = 0;
  while (scope.next(field_id, field_type)) {
    if (field_id == 3 && field_type == thrift::kStruct) {
      if (!parse_column_metadata(reader, out)) return false;
      saw_metadata = true;
    } else {
      if (!reader.skip(field_type)) return false;
    }
  }
  return reader.ok();
}

bool parse_row_group(Reader& reader, RowGroupMeta& out) {
  StructScope scope(reader);
  std::int16_t field_id = 0;
  std::uint8_t field_type = 0;
  while (scope.next(field_id, field_type)) {
    switch (field_id) {
      case 1: {
        if (field_type != thrift::kList) {
          if (!reader.skip(field_type)) return false;
          break;
        }
        std::uint32_t count = 0;
        std::uint8_t element = 0;
        if (!reader.list_header(count, element)) return false;
        out.columns.reserve(count);
        for (std::uint32_t index = 0; index < count; ++index) {
          if (element != thrift::kStruct) {
            if (!reader.skip(element)) return false;
            continue;
          }
          ColumnChunkMeta chunk;
          bool saw_metadata = false;
          if (!parse_column_chunk(reader, chunk, saw_metadata)) return false;
          if (!saw_metadata) {
            reader.fail("column chunk carries no ColumnMetaData");
            return false;
          }
          out.columns.push_back(std::move(chunk));
        }
        break;
      }
      case 2:
        if (!reader.integer(field_type, out.total_byte_size)) return false;
        break;
      case 3:
        if (!reader.integer(field_type, out.num_rows)) return false;
        break;
      default:
        if (!reader.skip(field_type)) return false;
        break;
    }
  }
  return reader.ok();
}

}  // namespace

bool parse_file_metadata(const std::uint8_t* footer, std::size_t size, FileMeta& out,
                         const char*& reason) {
  Reader reader(footer, size);
  {
    StructScope scope(reader);
    std::int16_t field_id = 0;
    std::uint8_t field_type = 0;
    while (scope.next(field_id, field_type)) {
      switch (field_id) {
        case 1:
          if (!read_i32(reader, field_type, out.version)) break;
          break;
        case 2: {
          if (field_type != thrift::kList) {
            (void)reader.skip(field_type);
            break;
          }
          std::uint32_t count = 0;
          std::uint8_t element = 0;
          if (!reader.list_header(count, element)) break;
          out.schema.reserve(count);
          for (std::uint32_t index = 0; index < count && reader.ok(); ++index) {
            if (element != thrift::kStruct) {
              (void)reader.skip(element);
              continue;
            }
            SchemaElement schema_element;
            if (!parse_schema_element(reader, schema_element)) break;
            out.schema.push_back(std::move(schema_element));
          }
          break;
        }
        case 3:
          (void)reader.integer(field_type, out.num_rows);
          break;
        case 4: {
          if (field_type != thrift::kList) {
            (void)reader.skip(field_type);
            break;
          }
          std::uint32_t count = 0;
          std::uint8_t element = 0;
          if (!reader.list_header(count, element)) break;
          out.row_groups.reserve(count);
          for (std::uint32_t index = 0; index < count && reader.ok(); ++index) {
            if (element != thrift::kStruct) {
              (void)reader.skip(element);
              continue;
            }
            RowGroupMeta group;
            if (!parse_row_group(reader, group)) break;
            out.row_groups.push_back(std::move(group));
          }
          break;
        }
        case 6:
          (void)reader.binary(out.created_by);
          break;
        default:
          (void)reader.skip(field_type);
          break;
      }
      if (!reader.ok()) {
        break;
      }
    }
  }
  if (!reader.ok()) {
    reason = reader.error();
    return false;
  }
  if (out.schema.empty()) {
    reason = "footer carries no schema";
    return false;
  }
  return true;
}

bool parse_page_header(const std::uint8_t* data, std::size_t size, PageHeader& out,
                       const char*& reason) {
  Reader reader(data, size);
  {
    StructScope scope(reader);
    std::int16_t field_id = 0;
    std::uint8_t field_type = 0;
    while (scope.next(field_id, field_type)) {
      switch (field_id) {
        case 1:
          (void)read_i32(reader, field_type, out.type);
          break;
        case 2:
          (void)read_i32(reader, field_type, out.uncompressed_page_size);
          break;
        case 3:
          (void)read_i32(reader, field_type, out.compressed_page_size);
          break;
        case 5: {  // DataPageHeader (v1)
          if (field_type != thrift::kStruct) {
            (void)reader.skip(field_type);
            break;
          }
          StructScope inner(reader);
          std::int16_t inner_id = 0;
          std::uint8_t inner_type = 0;
          while (inner.next(inner_id, inner_type)) {
            switch (inner_id) {
              case 1: (void)read_i32(reader, inner_type, out.v1_num_values); break;
              case 2: (void)read_i32(reader, inner_type, out.v1_encoding); break;
              case 3: (void)read_i32(reader, inner_type, out.v1_definition_level_encoding); break;
              case 4: (void)read_i32(reader, inner_type, out.v1_repetition_level_encoding); break;
              default: (void)reader.skip(inner_type); break;
            }
            if (!reader.ok()) break;
          }
          break;
        }
        case 7: {  // DictionaryPageHeader
          if (field_type != thrift::kStruct) {
            (void)reader.skip(field_type);
            break;
          }
          StructScope inner(reader);
          std::int16_t inner_id = 0;
          std::uint8_t inner_type = 0;
          while (inner.next(inner_id, inner_type)) {
            switch (inner_id) {
              case 1: (void)read_i32(reader, inner_type, out.dict_num_values); break;
              case 2: (void)read_i32(reader, inner_type, out.dict_encoding); break;
              default: (void)reader.skip(inner_type); break;
            }
            if (!reader.ok()) break;
          }
          break;
        }
        case 8: {  // DataPageHeaderV2
          if (field_type != thrift::kStruct) {
            (void)reader.skip(field_type);
            break;
          }
          StructScope inner(reader);
          std::int16_t inner_id = 0;
          std::uint8_t inner_type = 0;
          while (inner.next(inner_id, inner_type)) {
            switch (inner_id) {
              case 1: (void)read_i32(reader, inner_type, out.v2_num_values); break;
              case 2: (void)read_i32(reader, inner_type, out.v2_num_nulls); break;
              case 3: (void)read_i32(reader, inner_type, out.v2_num_rows); break;
              case 4: (void)read_i32(reader, inner_type, out.v2_encoding); break;
              case 5:
                (void)read_i32(reader, inner_type, out.v2_definition_levels_byte_length);
                break;
              case 6:
                (void)read_i32(reader, inner_type, out.v2_repetition_levels_byte_length);
                break;
              case 7:
                out.v2_is_compressed = (inner_type == thrift::kBoolTrue);
                break;
              default: (void)reader.skip(inner_type); break;
            }
            if (!reader.ok()) break;
          }
          break;
        }
        default:
          (void)reader.skip(field_type);
          break;
      }
      if (!reader.ok()) {
        break;
      }
    }
  }
  if (!reader.ok()) {
    reason = reader.error();
    return false;
  }
  if (out.uncompressed_page_size < 0 || out.compressed_page_size < 0) {
    reason = "page header declares a negative size";
    return false;
  }
  out.header_bytes = reader.position();
  return true;
}

}  // namespace qr::parquet
