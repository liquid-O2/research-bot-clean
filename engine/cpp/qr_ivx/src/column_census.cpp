#include "qr_ivx/column_census.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <system_error>

#include "qr_parquet/reader.hpp"

namespace qr::ivx {
namespace {

constexpr const char* kSite = "qr_ivx::column_census";

template <class T>
Expected<T, Refusal> refuse_here(RefusalCode code, const char* detail, std::int64_t context = 0) {
  return Expected<T, Refusal>::refuse(Refusal(code, kSite, detail, context));
}

/// parquet.thrift `Type`.
constexpr std::int32_t kTypeInt32 = 1;
constexpr std::int32_t kTypeInt64 = 2;
constexpr std::int32_t kTypeFloat = 4;
constexpr std::int32_t kTypeDouble = 5;

StatKind kind_of_type(std::int32_t type) noexcept {
  switch (type) {
    case kTypeInt32:
      return StatKind::INT32;
    case kTypeInt64:
      return StatKind::INT64;
    case kTypeFloat:
      return StatKind::FLOAT;
    case kTypeDouble:
      return StatKind::DOUBLE;
    default:
      return StatKind::OTHER;
  }
}

/// Decodes ONE PLAIN-encoded statistics bound into a double.
///
/// The parquet statistics min/max are the PLAIN encoding of one value of the
/// column's physical type — little-endian two's complement for the integers,
/// IEEE-754 little-endian for the floats. `std::memcpy` is the only lawful
/// reinterpretation in C++; a reinterpret_cast here would be strict-aliasing
/// UB, and a hand-rolled bit shuffle would be a second endianness convention.
bool decode_bound(StatKind kind, const std::string& bytes, double& out) noexcept {
  switch (kind) {
    case StatKind::INT32: {
      if (bytes.size() != 4) return false;
      std::int32_t value = 0;
      std::memcpy(&value, bytes.data(), sizeof(value));
      out = static_cast<double>(value);
      return true;
    }
    case StatKind::INT64: {
      if (bytes.size() != 8) return false;
      std::int64_t value = 0;
      std::memcpy(&value, bytes.data(), sizeof(value));
      out = static_cast<double>(value);
      return true;
    }
    case StatKind::FLOAT: {
      if (bytes.size() != 4) return false;
      float value = 0.0F;
      std::memcpy(&value, bytes.data(), sizeof(value));
      out = static_cast<double>(value);
      return true;
    }
    case StatKind::DOUBLE: {
      if (bytes.size() != 8) return false;
      double value = 0.0;
      std::memcpy(&value, bytes.data(), sizeof(value));
      out = value;
      return true;
    }
    case StatKind::NONE:
    case StatKind::OTHER:
    default:
      return false;
  }
}

/// The session's print files, in a deterministic order. The flat era stores one
/// file per day; the shard era stores a directory of per-expiry files, and
/// `directory_iterator` order is NOT deterministic, so the names are sorted.
Expected<std::vector<std::filesystem::path>, Refusal> print_files(
    const DayScope& scope, const std::filesystem::path& corpus_root) {
  const std::string& day = scope.day();
  if (day.size() < 4) {
    return refuse_here<std::vector<std::filesystem::path>>(RefusalCode::REGISTRY_MALFORMED,
                                                           "the session day is not YYYY-MM-DD");
  }
  const std::filesystem::path year_dir = corpus_root / day.substr(0, 4);
  std::error_code ec;
  const std::filesystem::path flat = year_dir / (day + ".parquet");
  if (std::filesystem::is_regular_file(flat, ec)) {
    return std::vector<std::filesystem::path>{flat};
  }
  const std::filesystem::path shard_dir = year_dir / day;
  if (!std::filesystem::is_directory(shard_dir, ec)) {
    return refuse_here<std::vector<std::filesystem::path>>(
        RefusalCode::MODALITY_ABSENT, "the print corpus carries no payload for this session",
        scope.ordinal());
  }
  std::vector<std::filesystem::path> out;
  for (const std::filesystem::directory_entry& entry :
       std::filesystem::directory_iterator(shard_dir, ec)) {
    if (entry.is_regular_file(ec) && entry.path().extension() == ".parquet") {
      out.push_back(entry.path());
    }
  }
  if (out.empty()) {
    return refuse_here<std::vector<std::filesystem::path>>(
        RefusalCode::MODALITY_ABSENT, "the print shard directory holds no parquet file",
        scope.ordinal());
  }
  std::sort(out.begin(), out.end());
  return out;
}

}  // namespace

const char* spec_standing_name(SpecStanding standing) noexcept {
  switch (standing) {
    case SpecStanding::PROJECTED:
      return "PROJECTED";
    case SpecStanding::HARD_REFUSED:
      return "HARD_REFUSED";
    case SpecStanding::UNPROJECTED:
    default:
      return "UNPROJECTED";
  }
}

SpecStanding standing_of(std::string_view column) noexcept {
  // Mirrors APPENDIX B3 / `qr::sources::kOptionPrintSpec` for the candidate set
  // ONLY. It is a LABEL for the receipt, not a second wall: nothing in this
  // module reads a value, so nothing here can be dodged.
  if (column == "implied_vol") {
    return SpecStanding::PROJECTED;
  }
  if (column == "vega" || column == "iv_error") {
    return SpecStanding::UNPROJECTED;
  }
  return SpecStanding::HARD_REFUSED;
}

const char* stat_kind_name(StatKind kind) noexcept {
  switch (kind) {
    case StatKind::INT32:
      return "INT32";
    case StatKind::INT64:
      return "INT64";
    case StatKind::FLOAT:
      return "FLOAT";
    case StatKind::DOUBLE:
      return "DOUBLE";
    case StatKind::OTHER:
      return "OTHER";
    case StatKind::NONE:
    default:
      return "NONE";
  }
}

const char* column_verdict_name(ColumnVerdict verdict) noexcept {
  switch (verdict) {
    case ColumnVerdict::NO_ROWS:
      return "NO_ROWS";
    case ColumnVerdict::ABSENT:
      return "ABSENT";
    case ColumnVerdict::ALL_NULL:
      return "ALL_NULL";
    case ColumnVerdict::CONSTANT_ZERO:
      return "CONSTANT_ZERO";
    case ColumnVerdict::REAL:
      return "REAL";
    case ColumnVerdict::REAL_WITH_NONFINITE:
      return "REAL_WITH_NONFINITE";
    case ColumnVerdict::POPULATED_NO_RANGE:
    default:
      return "POPULATED_NO_RANGE";
  }
}

ColumnVerdict verdict_of(const ColumnStat& stat) noexcept {
  if (!stat.in_schema) {
    return ColumnVerdict::ABSENT;
  }
  if (stat.num_values <= 0) {
    return ColumnVerdict::NO_ROWS;
  }
  // A null count is only trustworthy when EVERY chunk reported one; a partial
  // report cannot prove "all null".
  if (stat.chunks_with_null_count == stat.chunks && stat.null_count >= stat.num_values) {
    return ColumnVerdict::ALL_NULL;
  }
  if (!stat.has_range) {
    return ColumnVerdict::POPULATED_NO_RANGE;
  }
  if (stat.chunks_nonfinite_bound > 0) {
    return ColumnVerdict::REAL_WITH_NONFINITE;
  }
  if (stat.chunks_zero_range == stat.chunks_with_range && stat.min_value == 0.0 &&
      stat.max_value == 0.0) {
    return ColumnVerdict::CONSTANT_ZERO;
  }
  return ColumnVerdict::REAL;
}

std::int64_t presence_ppm(const ColumnStat& stat) noexcept {
  if (stat.num_values <= 0) {
    return -1;
  }
  if (stat.chunks_with_null_count != stat.chunks) {
    return -1;  // an unreported null count is UNDEFINED, never "zero nulls".
  }
  const std::int64_t present = stat.num_values - stat.null_count;
  if (present <= 0) {
    return 0;
  }
  // 1e6 * present / num_values, exact, no floating point.
  return (present * 1'000'000) / stat.num_values;
}

Expected<SessionColumnCensus, Refusal> census_print_columns(
    const DayScope& scope, const std::filesystem::path& corpus_root) {
  const auto files = print_files(scope, corpus_root);
  if (!files.has_value()) {
    return refuse<SessionColumnCensus>(files.error());
  }

  SessionColumnCensus out;
  out.ordinal = scope.ordinal();
  out.day = scope.day();
  out.files = static_cast<std::int64_t>(files.value().size());
  out.columns.resize(kCandidateColumns.size());
  for (std::size_t index = 0; index < kCandidateColumns.size(); ++index) {
    out.columns[index].name = kCandidateColumns[index];
    out.columns[index].standing = standing_of(kCandidateColumns[index]);
  }

  for (const std::filesystem::path& path : files.value()) {
    auto opened = qr::parquet::File::open(path.string());
    if (!opened.has_value()) {
      return refuse<SessionColumnCensus>(opened.error().refusal());
    }
    const qr::parquet::File& file = opened.value();
    out.file_rows += file.num_rows();
    out.row_groups += static_cast<std::int64_t>(file.num_row_groups());
    const std::int64_t leaves = static_cast<std::int64_t>(file.leaves().size());
    if (out.schema_leaves == 0) {
      out.schema_leaves = leaves;
    } else if (out.schema_leaves != leaves) {
      return refuse_here<SessionColumnCensus>(RefusalCode::SCHEMA_MISMATCH,
                                              "two shards of one session disagree on leaf count",
                                              leaves);
    }

    for (ColumnStat& stat : out.columns) {
      // Resolution is BY NAME against the file's own schema. The census exists
      // to discover what the vendor layout actually calls these columns, so a
      // hard-coded leaf index would answer its own question.
      std::int64_t leaf = -1;
      for (std::int64_t index = 0; index < leaves; ++index) {
        if (file.leaves()[static_cast<std::size_t>(index)].name == stat.name) {
          leaf = index;
          break;
        }
      }
      if (leaf < 0) {
        continue;  // absent from this file's schema; `in_schema` stays false.
      }
      const qr::parquet::LeafColumn& column = file.leaves()[static_cast<std::size_t>(leaf)];
      if (stat.in_schema && (stat.leaf != leaf || stat.leaf_type != column.type)) {
        return refuse_here<SessionColumnCensus>(
            RefusalCode::SCHEMA_MISMATCH, "two shards of one session disagree on a column's form",
            leaf);
      }
      stat.in_schema = true;
      stat.leaf = leaf;
      stat.leaf_type = column.type;

      for (const qr::parquet::RowGroupMeta& group : file.metadata().row_groups) {
        if (static_cast<std::int64_t>(group.columns.size()) <= leaf) {
          return refuse_here<SessionColumnCensus>(RefusalCode::SCHEMA_MISMATCH,
                                                  "a row group carries fewer chunks than leaves",
                                                  leaf);
        }
        const qr::parquet::ColumnChunkMeta& chunk =
            group.columns[static_cast<std::size_t>(leaf)];
        // The chunk vector is leaf-ordered; PROVE it rather than assume it.
        if (chunk.path.empty() || chunk.path.back() != stat.name) {
          return refuse_here<SessionColumnCensus>(
              RefusalCode::SCHEMA_MISMATCH, "the row group's chunk order is not the leaf order",
              leaf);
        }
        ++stat.chunks;
        stat.num_values += chunk.num_values;
        // The PHYSICAL type comes from the chunk metadata (the raw
        // parquet.thrift `Type` enum), not from the dialect-narrowed
        // `LeafType`: the statistics bounds below are PLAIN bytes of exactly
        // that physical type.
        if (stat.chunks == 1) {
          stat.physical_type = chunk.type;
          stat.kind = kind_of_type(chunk.type);
        } else if (stat.physical_type != chunk.type) {
          return refuse_here<SessionColumnCensus>(
              RefusalCode::SCHEMA_MISMATCH, "one column changed physical type between chunks",
              leaf);
        }
        if (!chunk.has_statistics) {
          continue;
        }
        ++stat.chunks_with_statistics;
        const qr::parquet::Statistics& statistics = chunk.statistics;
        if (statistics.has_null_count) {
          ++stat.chunks_with_null_count;
          stat.null_count += statistics.null_count;
        }
        const std::string* low = statistics.has_min_value  ? &statistics.min_value
                                 : statistics.has_min      ? &statistics.min
                                                           : nullptr;
        const std::string* high = statistics.has_max_value  ? &statistics.max_value
                                  : statistics.has_max      ? &statistics.max
                                                            : nullptr;
        if (low == nullptr || high == nullptr) {
          continue;
        }
        double min_value = 0.0;
        double max_value = 0.0;
        if (!decode_bound(stat.kind, *low, min_value) ||
            !decode_bound(stat.kind, *high, max_value)) {
          continue;  // an uninterpretable bound is NOT a range; say nothing.
        }
        ++stat.chunks_with_range;
        if (!std::isfinite(min_value) || !std::isfinite(max_value)) {
          ++stat.chunks_nonfinite_bound;
          continue;  // a non-finite bound never widens the reported range.
        }
        if (min_value == 0.0 && max_value == 0.0) {
          ++stat.chunks_zero_range;
        }
        if (!stat.has_range) {
          stat.has_range = true;
          stat.min_value = min_value;
          stat.max_value = max_value;
        } else {
          stat.min_value = std::min(stat.min_value, min_value);
          stat.max_value = std::max(stat.max_value, max_value);
        }
      }
    }
  }
  return out;
}

}  // namespace qr::ivx
