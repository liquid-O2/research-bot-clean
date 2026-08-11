// Unit tests for the thrift compact-protocol reader.
//
// SPEC: design/DESIGN_SUBSTRATE.md M1 qr_parquet bullet ("thrift-compact
// footer"). The reader is the port of engine/cpp/tools/qr_dialect_census.py's
// Reader; these tests pin the two properties the port must not lose — exact
// varint/zigzag arithmetic, and a bounds check on EVERY read.
#include <gtest/gtest.h>

#include <cstdint>
#include <string>
#include <vector>

#include "qr_parquet/thrift.hpp"

namespace {

using qr::parquet::thrift::Reader;
using qr::parquet::thrift::StructScope;

std::vector<std::uint8_t> bytes(std::initializer_list<int> values) {
  std::vector<std::uint8_t> out;
  out.reserve(values.size());
  for (int value : values) {
    out.push_back(static_cast<std::uint8_t>(value));
  }
  return out;
}

TEST(ThriftCompact, VarintDecodesMultiByteValuesExactly) {
  // 0x0e 0xff 0xfe read little-endian base-128: the shape the real corpus uses
  // for a 122,879-long rle run header.
  const std::vector<std::uint8_t> buffer = bytes({0xFE, 0xFF, 0x0E});
  Reader reader(buffer.data(), buffer.size());
  std::uint64_t value = 0;
  ASSERT_TRUE(reader.varint(value));
  EXPECT_EQ(value, 245758U);
  EXPECT_EQ(reader.position(), 3U);
}

TEST(ThriftCompact, ZigzagRoundTripsBothSigns) {
  struct Case {
    std::vector<std::uint8_t> encoded;
    std::int64_t expected;
  };
  const std::vector<Case> cases = {
      {bytes({0x00}), 0},   {bytes({0x01}), -1},  {bytes({0x02}), 1},
      {bytes({0x03}), -2},  {bytes({0xFE, 0x01}), 127}, {bytes({0xFF, 0x01}), -128},
  };
  for (const Case& item : cases) {
    Reader reader(item.encoded.data(), item.encoded.size());
    std::int64_t value = 0;
    ASSERT_TRUE(reader.zigzag(value)) << "case failed to decode";
    EXPECT_EQ(value, item.expected);
  }
}

TEST(ThriftCompact, EveryReadIsBoundsCheckedAndLatchesTheFirstReason) {
  const std::vector<std::uint8_t> buffer = bytes({0x80, 0x80});  // varint never ends
  Reader reader(buffer.data(), buffer.size());
  std::uint64_t value = 0;
  EXPECT_FALSE(reader.varint(value));
  EXPECT_FALSE(reader.ok());
  const std::string first_reason = reader.error();
  EXPECT_FALSE(first_reason.empty());
  // A second read must not overwrite the explanation of the first failure.
  std::uint8_t ignored = 0;
  EXPECT_FALSE(reader.byte(ignored));
  EXPECT_EQ(std::string(reader.error()), first_reason);
}

TEST(ThriftCompact, BinaryLengthLargerThanTheBufferIsRefusedNotAllocated) {
  // A length prefix of 2^35 with two bytes behind it.
  const std::vector<std::uint8_t> buffer = bytes({0x80, 0x80, 0x80, 0x80, 0x02, 0x41, 0x42});
  Reader reader(buffer.data(), buffer.size());
  std::string value;
  EXPECT_FALSE(reader.binary(value));
  EXPECT_FALSE(reader.ok());
  EXPECT_TRUE(value.empty());
}

TEST(ThriftCompact, StructScopeWalksFieldDeltasAndRestoresTheOuterChain) {
  // Outer struct: field 1 (i32 = 2), then a nested struct at field 2 whose own
  // chain restarts at 0, then field 3 of the OUTER struct. If the chain were
  // shared, the trailing field id would come out wrong.
  const std::vector<std::uint8_t> buffer = bytes({
      0x15, 0x04,        // outer field 1, I32, zigzag(4) == 2
      0x1C,              // outer field 2, STRUCT
      0x15, 0x02,        //   inner field 1, I32, zigzag(2) == 1
      0x00,              //   inner STOP
      0x15, 0x06,        // outer field 3, I32, zigzag(6) == 3
      0x00,              // outer STOP
  });
  Reader reader(buffer.data(), buffer.size());
  std::vector<std::int16_t> outer_ids;
  {
    StructScope outer(reader);
    std::int16_t field_id = 0;
    std::uint8_t field_type = 0;
    while (outer.next(field_id, field_type)) {
      outer_ids.push_back(field_id);
      if (field_type == qr::parquet::thrift::kStruct) {
        StructScope inner(reader);
        std::int16_t inner_id = 0;
        std::uint8_t inner_type = 0;
        while (inner.next(inner_id, inner_type)) {
          EXPECT_EQ(inner_id, 1);
          std::int64_t inner_value = 0;
          ASSERT_TRUE(reader.integer(inner_type, inner_value));
          EXPECT_EQ(inner_value, 1);
        }
      } else {
        std::int64_t value = 0;
        ASSERT_TRUE(reader.integer(field_type, value));
      }
    }
  }
  ASSERT_TRUE(reader.ok());
  ASSERT_EQ(outer_ids.size(), 3U);
  EXPECT_EQ(outer_ids[0], 1);
  EXPECT_EQ(outer_ids[1], 2);
  EXPECT_EQ(outer_ids[2], 3);
}

TEST(ThriftCompact, SkipRefusesNestingDeeperThanTheLimit) {
  // A chain of STRUCT-typed field 1s, deeper than kMaxSkipDepth, must fail
  // instead of driving the C++ stack from the input.
  std::vector<std::uint8_t> buffer;
  for (int depth = 0; depth < qr::parquet::thrift::kMaxSkipDepth + 8; ++depth) {
    buffer.push_back(0x1C);  // field 1, STRUCT
  }
  Reader reader(buffer.data(), buffer.size());
  EXPECT_FALSE(reader.skip(qr::parquet::thrift::kStruct));
  EXPECT_FALSE(reader.ok());
}

TEST(ThriftCompact, ListHeaderRefusesAPromiseLargerThanTheBuffer) {
  // 0xF9 == long-form list of BINARY; the varint then claims 2^28 elements.
  const std::vector<std::uint8_t> buffer = bytes({0xF9, 0x80, 0x80, 0x80, 0x01});
  Reader reader(buffer.data(), buffer.size());
  std::uint32_t count = 0;
  std::uint8_t element = 0;
  EXPECT_FALSE(reader.list_header(count, element));
  EXPECT_FALSE(reader.ok());
}

}  // namespace
