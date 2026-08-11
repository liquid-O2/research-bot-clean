#include "qr_parquet/column.hpp"

#include <cstring>

#include "qr_core/refusal.hpp"

namespace qr::parquet {
namespace {

constexpr std::uint64_t kFnvOffsetBasis = 0xCBF29CE484222325ULL;
constexpr std::uint64_t kFnvPrime = 0x100000001B3ULL;

std::uint64_t fnv1a(std::uint64_t digest, const std::uint8_t* data, std::size_t size) noexcept {
  for (std::size_t index = 0; index < size; ++index) {
    digest ^= static_cast<std::uint64_t>(data[index]);
    digest *= kFnvPrime;
  }
  return digest;
}

}  // namespace

void Bitmap::set_range(std::size_t begin, std::size_t end) noexcept {
  if (begin >= end) {
    return;
  }
  const std::size_t first_word = begin >> 6U;
  const std::size_t last_word = (end - 1) >> 6U;
  const std::uint64_t all_ones = ~std::uint64_t{0};
  const std::uint64_t head_mask = all_ones << (begin & 63U);
  const std::size_t tail_bits = ((end - 1) & 63U) + 1;
  const std::uint64_t tail_mask =
      tail_bits == 64 ? all_ones : ((std::uint64_t{1} << tail_bits) - 1);
  if (first_word == last_word) {
    words_[first_word] |= (head_mask & tail_mask);
    return;
  }
  words_[first_word] |= head_mask;
  for (std::size_t word = first_word + 1; word < last_word; ++word) {
    words_[word] = all_ones;
  }
  words_[last_word] |= tail_mask;
}

const char* leaf_type_name(LeafType type) noexcept {
  switch (type) {
    case LeafType::INT32: return "INT32";
    case LeafType::INT64: return "INT64";
    case LeafType::DOUBLE: return "DOUBLE";
    case LeafType::BYTE_ARRAY: return "BYTE_ARRAY";
  }
  qr::detail::fail_fast("qr_parquet::leaf_type_name: unreachable leaf type");
}

const char* leaf_converted_name(LeafConverted converted) noexcept {
  switch (converted) {
    case LeafConverted::NONE: return "NONE";
    case LeafConverted::UTF8: return "UTF8";
    case LeafConverted::DATE: return "DATE";
    case LeafConverted::UINT_32: return "UINT_32";
    case LeafConverted::INT_8: return "INT_8";
  }
  qr::detail::fail_fast("qr_parquet::leaf_converted_name: unreachable converted type");
}

void ColumnData::reset(LeafType leaf_type, std::int64_t rows) {
  type = leaf_type;
  num_rows = rows;
  null_count = 0;
  const std::size_t count = static_cast<std::size_t>(rows);
  i32.clear();
  i64.clear();
  f64.clear();
  offsets.clear();
  bytes.clear();
  switch (leaf_type) {
    case LeafType::INT32:
      i32.assign(count, 0);
      break;
    case LeafType::INT64:
      i64.assign(count, 0);
      break;
    case LeafType::DOUBLE:
      f64.assign(count, 0.0);
      break;
    case LeafType::BYTE_ARRAY:
      offsets.assign(count + 1, 0);
      break;
  }
  validity.reset(count);
}

std::string_view ColumnData::byte_array(std::int64_t row) const noexcept {
  const std::size_t index = static_cast<std::size_t>(row);
  const std::uint32_t begin = offsets[index];
  const std::uint32_t end = offsets[index + 1];
  return std::string_view(reinterpret_cast<const char*>(bytes.data()) + begin,
                          static_cast<std::size_t>(end - begin));
}

std::uint64_t column_digest(const ColumnData& column) noexcept {
  const std::size_t rows = static_cast<std::size_t>(column.num_rows);
  switch (column.type) {
    case LeafType::INT32: {
      std::uint64_t sum = 0;
      for (std::size_t row = 0; row < rows; ++row) {
        if (column.validity.get(row)) {
          sum += static_cast<std::uint64_t>(static_cast<std::int64_t>(column.i32[row]));
        }
      }
      return sum;
    }
    case LeafType::INT64: {
      std::uint64_t sum = 0;
      for (std::size_t row = 0; row < rows; ++row) {
        if (column.validity.get(row)) {
          sum += static_cast<std::uint64_t>(column.i64[row]);
        }
      }
      return sum;
    }
    case LeafType::DOUBLE: {
      std::uint64_t acc = 0;
      for (std::size_t row = 0; row < rows; ++row) {
        if (column.validity.get(row)) {
          std::uint64_t bits = 0;
          std::memcpy(&bits, &column.f64[row], sizeof(bits));
          acc ^= bits;
        }
      }
      return acc;
    }
    case LeafType::BYTE_ARRAY: {
      std::uint64_t digest = kFnvOffsetBasis;
      for (std::size_t row = 0; row < rows; ++row) {
        if (!column.validity.get(row)) {
          continue;
        }
        const std::uint32_t begin = column.offsets[row];
        const std::uint32_t end = column.offsets[row + 1];
        const std::uint32_t length = end - begin;
        std::uint8_t length_le[4];
        length_le[0] = static_cast<std::uint8_t>(length & 0xFFU);
        length_le[1] = static_cast<std::uint8_t>((length >> 8U) & 0xFFU);
        length_le[2] = static_cast<std::uint8_t>((length >> 16U) & 0xFFU);
        length_le[3] = static_cast<std::uint8_t>((length >> 24U) & 0xFFU);
        digest = fnv1a(digest, length_le, sizeof(length_le));
        digest = fnv1a(digest, column.bytes.data() + begin, static_cast<std::size_t>(length));
      }
      return digest;
    }
  }
  qr::detail::fail_fast("qr_parquet::column_digest: unreachable leaf type");
}

void append_serialized(const ColumnData& column, std::vector<std::uint8_t>& out) {
  const auto push = [&out](const void* source, std::size_t size) {
    const auto* bytes = static_cast<const std::uint8_t*>(source);
    out.insert(out.end(), bytes, bytes + size);
  };
  const std::uint8_t type_byte = static_cast<std::uint8_t>(column.type);
  push(&type_byte, 1);
  push(&column.num_rows, sizeof(column.num_rows));
  push(&column.null_count, sizeof(column.null_count));
  for (std::uint64_t word : column.validity.words()) {
    push(&word, sizeof(word));
  }
  switch (column.type) {
    case LeafType::INT32:
      push(column.i32.data(), column.i32.size() * sizeof(std::int32_t));
      break;
    case LeafType::INT64:
      push(column.i64.data(), column.i64.size() * sizeof(std::int64_t));
      break;
    case LeafType::DOUBLE:
      push(column.f64.data(), column.f64.size() * sizeof(double));
      break;
    case LeafType::BYTE_ARRAY:
      push(column.offsets.data(), column.offsets.size() * sizeof(std::uint32_t));
      push(column.bytes.data(), column.bytes.size());
      break;
  }
}

}  // namespace qr::parquet
