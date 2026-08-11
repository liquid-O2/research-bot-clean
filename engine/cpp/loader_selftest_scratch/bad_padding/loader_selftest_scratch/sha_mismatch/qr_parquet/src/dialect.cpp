#include "qr_parquet/dialect.hpp"

#include <string>

namespace qr::parquet {

const char* dialect_profile_name(DialectProfile profile) noexcept {
  switch (profile) {
    case DialectProfile::CORPUS:
      return "CORPUS";
    case DialectProfile::PUBLICATION:
      return "PUBLICATION";
  }
  return "UNKNOWN";
}

const char* codec_name(std::int32_t codec) noexcept {
  switch (codec) {
    case 0: return "UNCOMPRESSED";
    case 1: return "SNAPPY";
    case 2: return "GZIP";
    case 3: return "LZO";
    case 4: return "BROTLI";
    case 5: return "LZ4";
    case 6: return "ZSTD";
    case 7: return "LZ4_RAW";
    default: return "UNKNOWN_CODEC";
  }
}

const char* encoding_name(std::int32_t encoding) noexcept {
  switch (encoding) {
    case 0: return "PLAIN";
    case 1: return "GROUP_VAR_INT";
    case 2: return "PLAIN_DICTIONARY";
    case 3: return "RLE";
    case 4: return "BIT_PACKED";
    case 5: return "DELTA_BINARY_PACKED";
    case 6: return "DELTA_LENGTH_BYTE_ARRAY";
    case 7: return "DELTA_BYTE_ARRAY";
    case 8: return "RLE_DICTIONARY";
    case 9: return "BYTE_STREAM_SPLIT";
    default: return "UNKNOWN_ENCODING";
  }
}

const char* physical_name(std::int32_t type) noexcept {
  switch (type) {
    case 0: return "BOOLEAN";
    case 1: return "INT32";
    case 2: return "INT64";
    case 3: return "INT96";
    case 4: return "FLOAT";
    case 5: return "DOUBLE";
    case 6: return "BYTE_ARRAY";
    case 7: return "FIXED_LEN_BYTE_ARRAY";
    default: return "UNKNOWN_PHYSICAL_TYPE";
  }
}

const char* converted_name(std::int32_t converted) noexcept {
  switch (converted) {
    case -1: return "NONE";
    case 0: return "UTF8";
    case 1: return "MAP";
    case 2: return "MAP_KEY_VALUE";
    case 3: return "LIST";
    case 4: return "ENUM";
    case 5: return "DECIMAL";
    case 6: return "DATE";
    case 7: return "TIME_MILLIS";
    case 8: return "TIME_MICROS";
    case 9: return "TIMESTAMP_MILLIS";
    case 10: return "TIMESTAMP_MICROS";
    case 11: return "UINT_8";
    case 12: return "UINT_16";
    case 13: return "UINT_32";
    case 14: return "UINT_64";
    case 15: return "INT_8";
    case 16: return "INT_16";
    case 17: return "INT_32";
    case 18: return "INT_64";
    case 19: return "JSON";
    case 20: return "BSON";
    case 21: return "INTERVAL";
    default: return "UNKNOWN_CONVERTED_TYPE";
  }
}

const char* repetition_name(std::int32_t repetition) noexcept {
  switch (repetition) {
    case 0: return "REQUIRED";
    case 1: return "OPTIONAL";
    case 2: return "REPEATED";
    default: return "UNKNOWN_REPETITION";
  }
}

std::string FileRefusal::message() const {
  std::string text = refusal_code_name(refusal_.code());
  text += " at ";
  text += refusal_.site();
  text += ": ";
  text += refusal_.detail();
  if (!detail_.empty()) {
    text += " (";
    text += detail_;
    text += ")";
  }
  if (refusal_.context() != 0) {
    text += " [context=";
    text += std::to_string(refusal_.context());
    text += "]";
  }
  text += " path=";
  text += path_;
  return text;
}

}  // namespace qr::parquet
