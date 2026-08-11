// Fixtures NPY-1..NPY-13: the .npy v1.0 encoding, against numpy's own bytes.
//
// SPEC: FINAL_PLAN.md APPENDIX C4 + the frozen WP10 format ruling (".npy v1.0
// (\x93NUMPY magic, dict header padded to 64B, C-order little-endian)").
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <span>
#include <filesystem>
#include <string>
#include <vector>

#include "emit_test_support.hpp"
#include "gtest/gtest.h"
#include "qr_emit/npy_writer.hpp"

namespace {

using qr::emit::NpyDtype;
using qr::emit::NpyWriter;
using qr_emit_test::read_file;
using qr_emit_test::scratch;

std::filesystem::path fixture(const std::string& name) {
  return std::filesystem::path(QR_EMIT_NPY_FIXTURE_DIR) / (name + ".npy");
}

std::string header_of(NpyDtype dtype, std::vector<std::int64_t> shape) {
  auto header = qr::emit::npy_header_bytes(dtype, shape);
  EXPECT_TRUE(header.has_value()) << "shape refused unexpectedly";
  return header.has_value() ? header.value() : std::string();
}

TEST(NpyDtypes, AreTheFourPinnedAppendixC4Types) {
  EXPECT_EQ(qr::emit::kNpyDtypeCount, 4U);
  EXPECT_STREQ(qr::emit::npy_dtype_descr(NpyDtype::I8), "<i8");
  EXPECT_STREQ(qr::emit::npy_dtype_descr(NpyDtype::I4), "<i4");
  EXPECT_STREQ(qr::emit::npy_dtype_descr(NpyDtype::F4), "<f4");
  EXPECT_STREQ(qr::emit::npy_dtype_descr(NpyDtype::U1), "|u1");
  EXPECT_EQ(qr::emit::npy_dtype_size(NpyDtype::I8), 8U);
  EXPECT_EQ(qr::emit::npy_dtype_size(NpyDtype::I4), 4U);
  EXPECT_EQ(qr::emit::npy_dtype_size(NpyDtype::F4), 4U);
  EXPECT_EQ(qr::emit::npy_dtype_size(NpyDtype::U1), 1U);
  for (const NpyDtype dtype : {NpyDtype::I8, NpyDtype::I4, NpyDtype::F4, NpyDtype::U1}) {
    auto back = qr::emit::npy_dtype_from_descr(qr::emit::npy_dtype_descr(dtype));
    ASSERT_TRUE(back.has_value());
    EXPECT_EQ(back.value(), dtype);
  }
  // '>i8' is big-endian and '<f8' is float64: both are outside C4 and neither
  // may be silently coerced into a pinned type.
  EXPECT_FALSE(qr::emit::npy_dtype_from_descr(">i8").has_value());
  EXPECT_FALSE(qr::emit::npy_dtype_from_descr("<f8").has_value());
  EXPECT_FALSE(qr::emit::npy_dtype_from_descr("<i8 ").has_value());
}

TEST(NpyHeader, IsNumpysOwnPrologueByteForByte) {
  struct Case {
    const char* name;
    NpyDtype dtype;
    std::vector<std::int64_t> shape;
  };
  const std::vector<Case> cases = {
      {"i8_1d", NpyDtype::I8, {5}},
      {"i4_2d", NpyDtype::I4, {3, 4}},
      {"f4_3d", NpyDtype::F4, {2, 3, 4}},
      {"u1_2d", NpyDtype::U1, {2, 7}},
      {"i8_empty_2d", NpyDtype::I8, {0, 7}},
  };
  for (const Case& item : cases) {
    const std::string reference = read_file(fixture(item.name));
    ASSERT_GE(reference.size(), 128U) << item.name;
    const std::string ours = header_of(item.dtype, item.shape);
    ASSERT_EQ(ours.size(), 128U) << item.name;
    EXPECT_EQ(ours, reference.substr(0, ours.size()))
        << item.name << ": our prologue is not numpy's prologue";
  }
}

TEST(NpyHeader, CarriesTheMagicVersionAndLittleEndianHeaderLength) {
  const std::string header = header_of(NpyDtype::F4, {2, 3, 4});
  ASSERT_GE(header.size(), 10U);
  EXPECT_EQ(static_cast<unsigned char>(header[0]), 0x93U);
  EXPECT_EQ(header.substr(1, 5), "NUMPY");
  EXPECT_EQ(static_cast<unsigned char>(header[6]), 1U);
  EXPECT_EQ(static_cast<unsigned char>(header[7]), 0U);
  const std::size_t declared = static_cast<std::size_t>(static_cast<unsigned char>(header[8])) |
                               (static_cast<std::size_t>(static_cast<unsigned char>(header[9]))
                                << 8);
  EXPECT_EQ(declared, header.size() - 10U) << "HEADER_LEN does not describe the header";
  EXPECT_EQ(header.back(), '\n');
  EXPECT_NE(header.find("'fortran_order': False"), std::string::npos)
      << "C order is part of the ruling, not a default";
}

TEST(NpyHeader, AlwaysLandsThePayloadOnASixtyFourByteBoundary) {
  // The invariant that makes the leaves mmap-friendly and that the off-by-one
  // padding mutant breaks. Swept over every dtype and 1..3 dimensions,
  // including digit-count changes (9 -> 10 -> 100 -> 1000).
  for (const NpyDtype dtype : {NpyDtype::I8, NpyDtype::I4, NpyDtype::F4, NpyDtype::U1}) {
    for (const std::int64_t a : {0, 1, 7, 9, 10, 99, 100, 1000, 123456}) {
      const std::string one = header_of(dtype, {a});
      EXPECT_EQ(one.size() % 64U, 0U) << "1-D " << a;
      const std::string two = header_of(dtype, {a, 7});
      EXPECT_EQ(two.size() % 64U, 0U) << "2-D " << a;
      const std::string three = header_of(dtype, {a, 3, 60});
      EXPECT_EQ(three.size() % 64U, 0U) << "3-D " << a;
      // The pad is never empty: the '\n' terminator always follows at least one
      // space, because numpy pads by a whole 64 bytes when already aligned.
      EXPECT_GE(one.size(), 64U);
    }
  }
}

TEST(NpyHeader, OneDimensionalShapesAreWrittenAsOneTuples) {
  const std::string one = header_of(NpyDtype::I8, {5});
  EXPECT_NE(one.find("'shape': (5,), }"), std::string::npos);
  const std::string two = header_of(NpyDtype::I8, {5, 7});
  EXPECT_NE(two.find("'shape': (5, 7), }"), std::string::npos);
  const std::string three = header_of(NpyDtype::I8, {5, 7, 9});
  EXPECT_NE(three.find("'shape': (5, 7, 9), }"), std::string::npos);
}

TEST(NpyHeader, RefusesShapesOutsideOneToThreeDimensionsAndNegativeExtents) {
  const std::vector<std::int64_t> none;
  EXPECT_FALSE(qr::emit::npy_header_bytes(NpyDtype::I8, none).has_value());
  const std::vector<std::int64_t> four = {1, 2, 3, 4};
  EXPECT_FALSE(qr::emit::npy_header_bytes(NpyDtype::I8, four).has_value());
  const std::vector<std::int64_t> negative = {3, -1};
  EXPECT_FALSE(qr::emit::npy_header_bytes(NpyDtype::I8, negative).has_value());
  // An element count that overflows int64 is a refusal, never a wrapped size.
  const std::vector<std::int64_t> huge = {1LL << 40, 1LL << 40, 1LL << 40};
  auto refused = qr::emit::npy_element_count(huge);
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::ARITHMETIC_OVERFLOW);
}

TEST(NpyLeaf, WhatWeWriteIsNumpysOwnFileByteForByte) {
  const std::filesystem::path dir = scratch("npy_roundtrip");

  {
    const std::vector<std::int64_t> shape = {5};
    auto writer = NpyWriter::create(dir / "i8_1d.npy", "features/i8_1d.npy", NpyDtype::I8, shape);
    ASSERT_TRUE(writer.has_value()) << writer.error().message();
    NpyWriter leaf = std::move(writer).value();
    const std::vector<std::int64_t> values = qr_emit_test::literal_i8_1d();
    ASSERT_TRUE(leaf.append(values).has_value());
    auto receipt = leaf.finish();
    ASSERT_TRUE(receipt.has_value()) << receipt.error().message();
    EXPECT_EQ(receipt.value().rows, 5);
    EXPECT_EQ(receipt.value().rel_path, "features/i8_1d.npy");
  }
  EXPECT_EQ(read_file(dir / "i8_1d.npy"), read_file(fixture("i8_1d")));

  {
    const std::vector<std::int64_t> shape = {3, 4};
    auto writer = NpyWriter::create(dir / "i4_2d.npy", "features/i4_2d.npy", NpyDtype::I4, shape);
    ASSERT_TRUE(writer.has_value());
    NpyWriter leaf = std::move(writer).value();
    const std::vector<std::int32_t> values = qr_emit_test::literal_i4_2d();
    ASSERT_TRUE(leaf.append(values).has_value());
    ASSERT_TRUE(leaf.finish().has_value());
  }
  EXPECT_EQ(read_file(dir / "i4_2d.npy"), read_file(fixture("i4_2d")));

  {
    const std::vector<std::int64_t> shape = {2, 3, 4};
    auto writer = NpyWriter::create(dir / "f4_3d.npy", "features/f4_3d.npy", NpyDtype::F4, shape);
    ASSERT_TRUE(writer.has_value());
    NpyWriter leaf = std::move(writer).value();
    const std::vector<float> values = qr_emit_test::literal_f4_3d();
    // Appended in two pieces: the encoding may not depend on how the caller
    // chunked the payload.
    ASSERT_TRUE(leaf.append(std::span<const float>(values).subspan(0, 7)).has_value());
    ASSERT_TRUE(leaf.append(std::span<const float>(values).subspan(7)).has_value());
    ASSERT_TRUE(leaf.finish().has_value());
  }
  EXPECT_EQ(read_file(dir / "f4_3d.npy"), read_file(fixture("f4_3d")));

  {
    const std::vector<std::int64_t> shape = {2, 7};
    auto writer = NpyWriter::create(dir / "u1_2d.npy", "truth/u1_2d.npy", NpyDtype::U1, shape);
    ASSERT_TRUE(writer.has_value());
    NpyWriter leaf = std::move(writer).value();
    const std::vector<std::uint8_t> values = qr_emit_test::literal_u1_2d();
    ASSERT_TRUE(leaf.append(values).has_value());
    ASSERT_TRUE(leaf.finish().has_value());
  }
  EXPECT_EQ(read_file(dir / "u1_2d.npy"), read_file(fixture("u1_2d")));

  {
    const std::vector<std::int64_t> shape = {0, 7};
    auto writer = NpyWriter::create(dir / "empty.npy", "truth/empty.npy", NpyDtype::I8, shape);
    ASSERT_TRUE(writer.has_value());
    NpyWriter leaf = std::move(writer).value();
    auto receipt = leaf.finish();
    ASSERT_TRUE(receipt.has_value()) << "a zero-row leaf is a real leaf, not an error";
    EXPECT_EQ(receipt.value().rows, 0);
    EXPECT_EQ(receipt.value().file_bytes, 128);
  }
  EXPECT_EQ(read_file(dir / "empty.npy"), read_file(fixture("i8_empty_2d")));
}

TEST(NpyWriter, RefusesMoreElementsThanTheDeclaredShape) {
  const std::filesystem::path dir = scratch("npy_overlong");
  const std::vector<std::int64_t> shape = {2, 3};
  auto writer = NpyWriter::create(dir / "leaf.npy", "features/leaf.npy", NpyDtype::I4, shape);
  ASSERT_TRUE(writer.has_value());
  NpyWriter leaf = std::move(writer).value();
  const std::vector<std::int32_t> too_many(7, 1);
  auto refused = leaf.append(too_many);
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::CONFIG);
  EXPECT_EQ(leaf.elements_written(), 0) << "a refused append may not write a partial row";
}

TEST(NpyWriter, RefusesAShortLeafAtFinish) {
  const std::filesystem::path dir = scratch("npy_short");
  const std::vector<std::int64_t> shape = {2, 3};
  auto writer = NpyWriter::create(dir / "leaf.npy", "features/leaf.npy", NpyDtype::I4, shape);
  ASSERT_TRUE(writer.has_value());
  NpyWriter leaf = std::move(writer).value();
  const std::vector<std::int32_t> partial(5, 1);
  ASSERT_TRUE(leaf.append(partial).has_value());
  auto refused = leaf.finish();
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::CONFIG);
  EXPECT_EQ(refused.error().context(), 5) << "the refusal names how many elements arrived";
}

TEST(NpyWriter, RefusesAnElementTypeOtherThanTheDeclaredDtype) {
  const std::filesystem::path dir = scratch("npy_dtype_mismatch");
  const std::vector<std::int64_t> shape = {4};
  auto writer = NpyWriter::create(dir / "leaf.npy", "features/leaf.npy", NpyDtype::F4, shape);
  ASSERT_TRUE(writer.has_value());
  NpyWriter leaf = std::move(writer).value();
  const std::vector<std::int32_t> wrong(4, 1);
  EXPECT_FALSE(leaf.append(wrong).has_value())
      << "int32 into an '<f4' leaf must refuse, not reinterpret";
  const std::vector<std::int64_t> also_wrong(4, 1);
  EXPECT_FALSE(leaf.append(also_wrong).has_value());
  const std::vector<std::uint8_t> still_wrong(4, 1);
  EXPECT_FALSE(leaf.append(still_wrong).has_value());
}

TEST(NpyWriter, NeverOverwritesAnExistingLeaf) {
  const std::filesystem::path dir = scratch("npy_exclusive");
  const std::vector<std::int64_t> shape = {1};
  auto first = NpyWriter::create(dir / "leaf.npy", "features/leaf.npy", NpyDtype::U1, shape);
  ASSERT_TRUE(first.has_value());
  auto second = NpyWriter::create(dir / "leaf.npy", "features/leaf.npy", NpyDtype::U1, shape);
  ASSERT_FALSE(second.has_value()) << "O_EXCL: a leaf is created, never replaced";
  EXPECT_EQ(second.error().code(), qr::RefusalCode::IO);
}

TEST(NpyWriter, ReceiptDigestIsTheDigestOfTheWholeFileIncludingTheHeader) {
  const std::filesystem::path dir = scratch("npy_digest");
  const std::vector<std::int64_t> shape = {3, 4};
  auto writer = NpyWriter::create(dir / "leaf.npy", "features/leaf.npy", NpyDtype::I4, shape);
  ASSERT_TRUE(writer.has_value());
  NpyWriter leaf = std::move(writer).value();
  const std::vector<std::int32_t> values = qr_emit_test::literal_i4_2d();
  ASSERT_TRUE(leaf.append(values).has_value());
  auto receipt = leaf.finish();
  ASSERT_TRUE(receipt.has_value());
  const std::string bytes = read_file(dir / "leaf.npy");
  EXPECT_EQ(receipt.value().sha256, qr_emit_test::sha256_hex(bytes));
  EXPECT_EQ(receipt.value().file_bytes, static_cast<std::int64_t>(bytes.size()));
  EXPECT_EQ(receipt.value().shape, shape);
  EXPECT_EQ(receipt.value().dtype, NpyDtype::I4);
}

TEST(NpyWriter, PayloadsLargerThanTheWriteChunkAreEncodedExactly) {
  // 1.5 MiB of float32 crosses the writer's 1 MiB write(2) chunk boundary; the
  // digest and the byte count must be exactly what a single logical array is.
  const std::filesystem::path dir = scratch("npy_chunked");
  const std::int64_t rows = 98304;  // 98304 * 4 elements * 4 bytes = 1.5 MiB
  const std::vector<std::int64_t> shape = {rows, 4};
  auto writer = NpyWriter::create(dir / "big.npy", "features/big.npy", NpyDtype::F4, shape);
  ASSERT_TRUE(writer.has_value());
  NpyWriter leaf = std::move(writer).value();
  std::vector<float> values(static_cast<std::size_t>(rows) * 4);
  for (std::size_t index = 0; index < values.size(); ++index) {
    values[index] = static_cast<float>(index % 4096) / 8.0F;
  }
  ASSERT_TRUE(leaf.append(values).has_value());
  auto receipt = leaf.finish();
  ASSERT_TRUE(receipt.has_value());
  const std::string bytes = read_file(dir / "big.npy");
  EXPECT_EQ(receipt.value().file_bytes, 128 + static_cast<std::int64_t>(values.size()) * 4);
  EXPECT_EQ(receipt.value().sha256, qr_emit_test::sha256_hex(bytes));
  // Spot-check the payload: element k sits at 128 + 4k, little-endian.
  float decoded = 0.0F;
  std::memcpy(&decoded, bytes.data() + 128 + 4 * 5000, 4);
  EXPECT_FLOAT_EQ(decoded, values[5000]);
}

TEST(NpyWriter, TwoRunsOverTheSameLeafAreByteIdentical) {
  const std::filesystem::path dir = scratch("npy_identity");
  std::vector<std::string> written;
  for (const char* run : {"run_a", "run_b"}) {
    const std::filesystem::path path = dir / (std::string(run) + ".npy");
    const std::vector<std::int64_t> shape = {2, 3, 4};
    auto writer = NpyWriter::create(path, "features/x.npy", NpyDtype::F4, shape);
    ASSERT_TRUE(writer.has_value());
    NpyWriter leaf = std::move(writer).value();
    const std::vector<float> values = qr_emit_test::literal_f4_3d();
    ASSERT_TRUE(leaf.append(values).has_value());
    ASSERT_TRUE(leaf.finish().has_value());
    written.push_back(read_file(path));
  }
  EXPECT_EQ(written.at(0), written.at(1));
}

}  // namespace
