#include "qr_parquet/thrift.hpp"

namespace qr::parquet::thrift {

bool Reader::byte(std::uint8_t& out) noexcept {
  if (!ok()) {
    return false;
  }
  if (pos_ >= size_) {
    fail("thrift buffer exhausted");
    return false;
  }
  out = data_[pos_];
  ++pos_;
  return true;
}

bool Reader::varint(std::uint64_t& out) noexcept {
  if (!ok()) {
    return false;
  }
  std::uint64_t result = 0;
  unsigned shift = 0;
  for (;;) {
    std::uint8_t b = 0;
    if (!byte(b)) {
      return false;
    }
    result |= static_cast<std::uint64_t>(b & 0x7FU) << shift;
    if ((b & 0x80U) == 0) {
      out = result;
      return true;
    }
    shift += 7;
    if (shift > 63) {
      fail("thrift varint longer than 64 bits");
      return false;
    }
  }
}

bool Reader::zigzag(std::int64_t& out) noexcept {
  std::uint64_t raw = 0;
  if (!varint(raw)) {
    return false;
  }
  // (n >> 1) ^ -(n & 1), computed in unsigned space so the negation is defined.
  const std::uint64_t magnitude = raw >> 1U;
  const std::uint64_t sign = ~((raw & 1U) - 1U);  // 0 or all-ones
  out = static_cast<std::int64_t>(magnitude ^ sign);
  return true;
}

bool Reader::take(std::size_t n, const std::uint8_t*& out) noexcept {
  if (!ok()) {
    return false;
  }
  if (n > size_ - pos_) {  // size_ >= pos_ always; no overflow
    fail("thrift buffer exhausted");
    return false;
  }
  out = data_ + pos_;
  pos_ += n;
  return true;
}

bool Reader::binary(std::string& out) {
  std::uint64_t length = 0;
  if (!varint(length)) {
    return false;
  }
  if (length > static_cast<std::uint64_t>(size_)) {
    fail("thrift binary length exceeds buffer");
    return false;
  }
  const std::uint8_t* bytes = nullptr;
  if (!take(static_cast<std::size_t>(length), bytes)) {
    return false;
  }
  out.assign(reinterpret_cast<const char*>(bytes), static_cast<std::size_t>(length));
  return true;
}

bool Reader::skip_binary() noexcept {
  std::uint64_t length = 0;
  if (!varint(length)) {
    return false;
  }
  if (length > static_cast<std::uint64_t>(size_)) {
    fail("thrift binary length exceeds buffer");
    return false;
  }
  const std::uint8_t* ignored = nullptr;
  return take(static_cast<std::size_t>(length), ignored);
}

bool Reader::list_header(std::uint32_t& count, std::uint8_t& element) noexcept {
  std::uint8_t header = 0;
  if (!byte(header)) {
    return false;
  }
  element = static_cast<std::uint8_t>(header & 0x0FU);
  const std::uint8_t short_count = static_cast<std::uint8_t>(header >> 4U);
  if (short_count != 0x0F) {
    count = short_count;
    return true;
  }
  std::uint64_t long_count = 0;
  if (!varint(long_count)) {
    return false;
  }
  // A list header may not promise more elements than the buffer could hold even
  // at one byte each: that is a corrupt footer, not an allocation request.
  if (long_count > static_cast<std::uint64_t>(size_)) {
    fail("thrift list longer than the buffer");
    return false;
  }
  count = static_cast<std::uint32_t>(long_count);
  return true;
}

bool Reader::integer(std::uint8_t field_type, std::int64_t& out) noexcept {
  switch (field_type) {
    case kByte: {
      std::uint8_t value = 0;
      if (!byte(value)) {
        return false;
      }
      out = static_cast<std::int64_t>(static_cast<std::int8_t>(value));
      return true;
    }
    case kI16:
    case kI32:
    case kI64:
      return zigzag(out);
    default:
      fail("thrift field is not an integer");
      return false;
  }
}

bool Reader::skip(std::uint8_t field_type, int depth) {
  if (!ok()) {
    return false;
  }
  if (depth > kMaxSkipDepth) {
    fail("thrift nesting deeper than the skip limit");
    return false;
  }
  switch (field_type) {
    case kBoolTrue:
    case kBoolFalse:
      return true;
    case kByte: {
      std::uint8_t ignored = 0;
      return byte(ignored);
    }
    case kI16:
    case kI32:
    case kI64: {
      std::int64_t ignored = 0;
      return zigzag(ignored);
    }
    case kDouble: {
      const std::uint8_t* ignored = nullptr;
      return take(8, ignored);
    }
    case kBinary:
      return skip_binary();
    case kList:
    case kSet: {
      std::uint32_t count = 0;
      std::uint8_t element = 0;
      if (!list_header(count, element)) {
        return false;
      }
      for (std::uint32_t index = 0; index < count; ++index) {
        if (!skip(element, depth + 1)) {
          return false;
        }
      }
      return true;
    }
    case kMap: {
      std::uint64_t count = 0;
      if (!varint(count)) {
        return false;
      }
      if (count > static_cast<std::uint64_t>(size())) {
        fail("thrift map longer than the buffer");
        return false;
      }
      if (count == 0) {
        return true;
      }
      std::uint8_t kinds = 0;
      if (!byte(kinds)) {
        return false;
      }
      const std::uint8_t key_type = static_cast<std::uint8_t>(kinds >> 4U);
      const std::uint8_t value_type = static_cast<std::uint8_t>(kinds & 0x0FU);
      for (std::uint64_t index = 0; index < count; ++index) {
        if (!skip(key_type, depth + 1) || !skip(value_type, depth + 1)) {
          return false;
        }
      }
      return true;
    }
    case kStruct: {
      StructScope scope(*this);
      std::int16_t field_id = 0;
      std::uint8_t inner_type = 0;
      while (scope.next(field_id, inner_type)) {
        if (!skip(inner_type, depth + 1)) {
          return false;
        }
      }
      return ok();
    }
    default:
      fail("thrift element type is not one of the protocol's types");
      return false;
  }
}

bool StructScope::next(std::int16_t& field_id, std::uint8_t& field_type) noexcept {
  std::uint8_t header = 0;
  if (!reader_.byte(header)) {
    return false;
  }
  if (header == kStop) {
    return false;
  }
  field_type = static_cast<std::uint8_t>(header & 0x0FU);
  const std::uint8_t delta = static_cast<std::uint8_t>(header >> 4U);
  if (delta == 0) {
    std::int64_t explicit_id = 0;
    if (!reader_.zigzag(explicit_id)) {
      return false;
    }
    if (explicit_id < 0 || explicit_id > 32767) {
      reader_.fail("thrift field id outside the i16 range");
      return false;
    }
    field_id = static_cast<std::int16_t>(explicit_id);
  } else {
    const std::int32_t widened = static_cast<std::int32_t>(reader_.last_field_id()) +
                                 static_cast<std::int32_t>(delta);
    if (widened > 32767) {
      reader_.fail("thrift field id outside the i16 range");
      return false;
    }
    field_id = static_cast<std::int16_t>(widened);
  }
  reader_.set_last_field_id(field_id);
  return true;
}

}  // namespace qr::parquet::thrift
