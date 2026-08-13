// Fixtures DBN-1..DBN-14: the decoder's guards, exercised through the
// PRODUCTION constructor (qr::dbn::DbnStream::open + next_mbp1) on synthetic
// streams built here. PORT_M1_SPEC §1.3 requires that "one deliberately
// corrupted record in a synthetic file must fail the decoder's checksum/size
// guards" — DBN-8 is that fixture, and mutation M701 is its red proof.
#include <zstd.h>

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "gtest/gtest.h"
#include "qr_dbn/dbn.hpp"

namespace {

using qr::dbn::BidAskPair;
using qr::dbn::DbnStream;
using qr::dbn::Mbp1Msg;
using qr::dbn::Metadata;
using qr::dbn::RecordHeader;
using qr::dbn::SymbolIndex;

constexpr std::size_t kScl = qr::dbn::kSymbolCstrLenV1;

void put_u8(std::vector<std::uint8_t>& v, std::uint8_t x) { v.push_back(x); }

template <class T>
void put_le(std::vector<std::uint8_t>& v, T x) {
  const auto* p = reinterpret_cast<const std::uint8_t*>(&x);
  v.insert(v.end(), p, p + sizeof(T));
}

void put_cstr(std::vector<std::uint8_t>& v, const std::string& s, std::size_t width) {
  for (std::size_t i = 0; i < width; ++i) {
    v.push_back(i < s.size() ? static_cast<std::uint8_t>(s[i]) : 0u);
  }
}

struct Interval {
  std::uint32_t start;
  std::uint32_t end;
  std::string symbol;
};
struct Mapping {
  std::string raw;
  std::vector<Interval> intervals;
};

/// Build a DBN v1 metadata frame BODY (everything after magic+length).
std::vector<std::uint8_t> metadata_body(std::uint16_t schema, const std::vector<std::string>& symbols,
                                        const std::vector<Mapping>& mappings) {
  std::vector<std::uint8_t> b;
  put_cstr(b, "GLBX.MDP3", 16);
  put_le<std::uint16_t>(b, schema);
  put_le<std::uint64_t>(b, 1704067200000000000ull);  // start
  put_le<std::uint64_t>(b, 1735689600000000000ull);  // end
  put_le<std::uint64_t>(b, 0);                       // limit
  put_le<std::uint64_t>(b, ~std::uint64_t{0});       // v1 record_count = none
  put_u8(b, 3);                                      // stype_in  = continuous
  put_u8(b, 0);                                      // stype_out = instrument_id
  put_u8(b, 0);                                      // ts_out
  b.insert(b.end(), 47, 0u);                         // reserved[47]
  put_le<std::uint32_t>(b, 0);                       // schema_definition_length
  put_le<std::uint32_t>(b, static_cast<std::uint32_t>(symbols.size()));
  for (const std::string& s : symbols) {
    put_cstr(b, s, kScl);
  }
  put_le<std::uint32_t>(b, 0);  // partial
  put_le<std::uint32_t>(b, 0);  // not_found
  put_le<std::uint32_t>(b, static_cast<std::uint32_t>(mappings.size()));
  for (const Mapping& m : mappings) {
    put_cstr(b, m.raw, kScl);
    put_le<std::uint32_t>(b, static_cast<std::uint32_t>(m.intervals.size()));
    for (const Interval& iv : m.intervals) {
      put_le<std::uint32_t>(b, iv.start);
      put_le<std::uint32_t>(b, iv.end);
      put_cstr(b, iv.symbol, kScl);
    }
  }
  return b;
}

Mbp1Msg make_record(std::uint32_t iid, std::uint64_t ts_event, std::int64_t bid, std::int64_t ask) {
  Mbp1Msg m{};
  m.hd.length = static_cast<std::uint8_t>(sizeof(Mbp1Msg) / qr::dbn::kLengthUnit);
  m.hd.rtype = qr::dbn::kRTypeMbp1;
  m.hd.publisher_id = 1;
  m.hd.instrument_id = iid;
  m.hd.ts_event = ts_event;
  m.price = 4461500000LL;
  m.size = 2;
  m.action = 'A';
  m.side = 'B';
  m.flags = 130;
  m.depth = 0;
  m.ts_recv = ts_event + 1;
  m.ts_in_delta = 7;
  m.sequence = 13740;
  m.levels[0] = BidAskPair{bid, ask, 4, 1, 2, 3};
  return m;
}

/// Assemble a whole stream: magic + frame length + body + record bytes.
std::vector<std::uint8_t> make_stream(std::uint8_t version, const std::vector<std::uint8_t>& body,
                                      const std::vector<std::uint8_t>& records,
                                      std::int32_t frame_len_delta = 0) {
  std::vector<std::uint8_t> out;
  out.push_back('D');
  out.push_back('B');
  out.push_back('N');
  out.push_back(version);
  put_le<std::uint32_t>(
      out, static_cast<std::uint32_t>(static_cast<std::int64_t>(body.size()) + frame_len_delta));
  out.insert(out.end(), body.begin(), body.end());
  out.insert(out.end(), records.begin(), records.end());
  return out;
}

std::vector<std::uint8_t> record_bytes(const Mbp1Msg& m) {
  std::vector<std::uint8_t> v(sizeof(Mbp1Msg));
  std::memcpy(v.data(), &m, sizeof(Mbp1Msg));
  return v;
}

/// zstd-compress `raw` into a scratch file and return its path.
std::string write_zst(const std::string& stem, const std::vector<std::uint8_t>& raw) {
  const std::string path = std::string(QR_TEST_SCRATCH_DIR) + "/" + stem + ".dbn.zst";
  std::vector<std::uint8_t> comp(ZSTD_compressBound(raw.size()));
  const std::size_t n = ZSTD_compress(comp.data(), comp.size(), raw.data(), raw.size(), 3);
  EXPECT_EQ(ZSTD_isError(n), 0u);
  std::FILE* fh = std::fopen(path.c_str(), "wb");
  EXPECT_NE(fh, nullptr);
  if (fh != nullptr) {
    EXPECT_EQ(std::fwrite(comp.data(), 1, n, fh), n);
    std::fclose(fh);
  }
  return path;
}

std::vector<Mapping> simple_mappings() {
  return {Mapping{"HG.v.0",
                  {Interval{20240101, 20240226, "31863"}, Interval{20240226, 20240426, "1101"}}},
          Mapping{"HGH4-HGK4", {Interval{20240101, 20240426, "99001"}}}};
}

// --- DBN-1: the struct geometry is the decode contract ----------------------
TEST(DbnLayout, RecordGeometryMatchesTheVerifiedOnDiskLayout) {
  EXPECT_EQ(sizeof(RecordHeader), 16u);
  EXPECT_EQ(sizeof(BidAskPair), 32u);
  EXPECT_EQ(sizeof(Mbp1Msg), 80u);
  EXPECT_EQ(offsetof(Mbp1Msg, hd), 0u);
  EXPECT_EQ(offsetof(Mbp1Msg, price), 16u);
  EXPECT_EQ(offsetof(Mbp1Msg, size), 24u);
  EXPECT_EQ(offsetof(Mbp1Msg, action), 28u);
  EXPECT_EQ(offsetof(Mbp1Msg, side), 29u);
  EXPECT_EQ(offsetof(Mbp1Msg, flags), 30u);
  EXPECT_EQ(offsetof(Mbp1Msg, depth), 31u);
  EXPECT_EQ(offsetof(Mbp1Msg, ts_recv), 32u);
  EXPECT_EQ(offsetof(Mbp1Msg, ts_in_delta), 40u);
  EXPECT_EQ(offsetof(Mbp1Msg, sequence), 44u);
  EXPECT_EQ(offsetof(Mbp1Msg, levels), 48u);
}

// --- DBN-2: the symbology block ---------------------------------------------
TEST(DbnMetadata, ParsesTheSymbologyBlockExactly) {
  const auto body = metadata_body(qr::dbn::kSchemaMbp1, {"HG.v.0"}, simple_mappings());
  auto md = qr::dbn::parse_metadata_frame(1, body.data(), body.size());
  ASSERT_TRUE(md.has_value()) << md.error().message();
  const Metadata& m = md.value();
  EXPECT_EQ(m.dataset, "GLBX.MDP3");
  EXPECT_EQ(m.schema, qr::dbn::kSchemaMbp1);
  EXPECT_EQ(m.stype_in, 3u);
  EXPECT_EQ(m.stype_out, 0u);
  ASSERT_EQ(m.symbols.size(), 1u);
  EXPECT_EQ(m.symbols[0], "HG.v.0");
  ASSERT_EQ(m.mappings.size(), 2u);
  EXPECT_EQ(m.mappings[0].raw_symbol, "HG.v.0");
  ASSERT_EQ(m.mappings[0].intervals.size(), 2u);
  EXPECT_EQ(m.mappings[0].intervals[1].start_date, 20240226);
  EXPECT_EQ(m.mappings[0].intervals[1].symbol, "1101");
  EXPECT_EQ(m.mappings[1].raw_symbol, "HGH4-HGK4");
}

// --- DBN-3: exact frame consumption is the layout's own proof ---------------
TEST(DbnMetadata, RefusesAFrameItDoesNotConsumeExactly) {
  auto body = metadata_body(qr::dbn::kSchemaMbp1, {"HG.v.0"}, simple_mappings());
  body.insert(body.end(), 4, 0u);  // four bytes the parse cannot account for
  auto md = qr::dbn::parse_metadata_frame(1, body.data(), body.size());
  ASSERT_FALSE(md.has_value());
  EXPECT_EQ(md.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}

// --- DBN-4: an unverified stream version is refused, never guessed ----------
TEST(DbnMetadata, RefusesAnUnverifiedStreamVersion) {
  const auto body = metadata_body(qr::dbn::kSchemaMbp1, {"HG.v.0"}, simple_mappings());
  auto md = qr::dbn::parse_metadata_frame(3, body.data(), body.size());
  ASSERT_FALSE(md.has_value());
  EXPECT_EQ(md.error().code(), qr::RefusalCode::DECODE_FAILED);
  EXPECT_EQ(md.error().context(), 3);
}

// --- DBN-5: schema wall -----------------------------------------------------
TEST(DbnMetadata, RefusesAPayloadThatIsNotMbp1) {
  const auto body = metadata_body(10, {"HG.v.0"}, simple_mappings());  // mbp-10
  auto md = qr::dbn::parse_metadata_frame(1, body.data(), body.size());
  ASSERT_FALSE(md.has_value());
  EXPECT_EQ(md.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
}

// --- DBN-6: the magic -------------------------------------------------------
TEST(DbnStreamGuards, RefusesAPayloadWithoutTheDbnMagic) {
  auto raw = make_stream(1, metadata_body(qr::dbn::kSchemaMbp1, {"X"}, {}), {});
  raw[1] = 'X';
  DbnStream s;
  auto opened = s.open(write_zst("dbn6_bad_magic", raw));
  ASSERT_FALSE(opened.has_value());
  EXPECT_EQ(opened.error().code(), qr::RefusalCode::DECODE_FAILED);
}

// --- DBN-7: a length byte that cannot hold a header -------------------------
TEST(DbnStreamGuards, RefusesARecordShorterThanARecordHeader) {
  auto rec = record_bytes(make_record(1, 1704067200000000000ull, 100, 101));
  rec[0] = 2;  // 2 * 4 = 8 bytes, half a header
  const auto raw = make_stream(1, metadata_body(qr::dbn::kSchemaMbp1, {"X"}, {}), rec);
  DbnStream s;
  ASSERT_TRUE(s.open(write_zst("dbn7_short_len", raw)).has_value());
  auto next = s.next_mbp1();
  ASSERT_FALSE(next.has_value());
  EXPECT_EQ(next.error().code(), qr::RefusalCode::DECODE_FAILED);
  EXPECT_EQ(next.error().context(), 8);
}

// --- DBN-8: THE red-first fixture named by PORT_M1_SPEC §1.3 ----------------
// A single deliberately corrupted record in an otherwise clean synthetic file.
// Only its length field is damaged; every other byte is a valid mbp-1 record.
TEST(DbnStreamGuards, RefusesACorruptedMbp1RecordWhoseLengthIsNotEighty) {
  std::vector<std::uint8_t> recs;
  const auto good = record_bytes(make_record(31863, 1704067200000000000ull, 3891000000LL,
                                             3892000000LL));
  recs.insert(recs.end(), good.begin(), good.end());
  auto corrupt = record_bytes(make_record(31863, 1704067201000000000ull, 3891000000LL,
                                          3892000000LL));
  corrupt[0] = 21;  // 84 bytes: not the fixed mbp-1 size
  recs.insert(recs.end(), corrupt.begin(), corrupt.end());

  const auto raw = make_stream(1, metadata_body(qr::dbn::kSchemaMbp1, {"X"}, {}), recs);
  DbnStream s;
  ASSERT_TRUE(s.open(write_zst("dbn8_corrupt_record", raw)).has_value());

  auto first = s.next_mbp1();
  ASSERT_TRUE(first.has_value()) << first.error().message();
  ASSERT_NE(first.value(), nullptr);
  EXPECT_EQ(first.value()->hd.instrument_id, 31863u);

  auto second = s.next_mbp1();
  ASSERT_FALSE(second.has_value()) << "the corrupted record was accepted";
  EXPECT_EQ(second.error().code(), qr::RefusalCode::DECODE_FAILED);
  EXPECT_EQ(second.error().context(), 84);
}

// --- DBN-9: truncation is never a clean end of stream -----------------------
TEST(DbnStreamGuards, RefusesAStreamThatEndsInsideARecord) {
  auto rec = record_bytes(make_record(1, 1704067200000000000ull, 100, 101));
  rec.resize(60);  // the length byte still claims 80
  const auto raw = make_stream(1, metadata_body(qr::dbn::kSchemaMbp1, {"X"}, {}), rec);
  DbnStream s;
  ASSERT_TRUE(s.open(write_zst("dbn9_truncated", raw)).has_value());
  auto next = s.next_mbp1();
  ASSERT_FALSE(next.has_value());
  EXPECT_EQ(next.error().code(), qr::RefusalCode::DECODE_FAILED);
}

// --- DBN-10: an unknown rtype means the framing is not what we think --------
TEST(DbnStreamGuards, RefusesAnUnknownRecordType) {
  auto rec = record_bytes(make_record(1, 1704067200000000000ull, 100, 101));
  rec[1] = 'B';  // what a second concatenated DBN header would look like
  const auto raw = make_stream(1, metadata_body(qr::dbn::kSchemaMbp1, {"X"}, {}), rec);
  DbnStream s;
  ASSERT_TRUE(s.open(write_zst("dbn10_bad_rtype", raw)).has_value());
  auto next = s.next_mbp1();
  ASSERT_FALSE(next.has_value());
  EXPECT_EQ(next.error().code(), qr::RefusalCode::DECODE_FAILED);
  EXPECT_EQ(next.error().context(), static_cast<std::int64_t>('B'));
}

// --- DBN-11: every field survives the round trip ---------------------------
TEST(DbnStreamGuards, DecodesEveryFieldOfARecord) {
  const Mbp1Msg want = make_record(74683, 1717365600000000000ull, 3891000000LL, 3892000000LL);
  const auto raw =
      make_stream(1, metadata_body(qr::dbn::kSchemaMbp1, {"X"}, {}), record_bytes(want));
  DbnStream s;
  ASSERT_TRUE(s.open(write_zst("dbn11_roundtrip", raw)).has_value());
  auto got = s.next_mbp1();
  ASSERT_TRUE(got.has_value()) << got.error().message();
  ASSERT_NE(got.value(), nullptr);
  const Mbp1Msg& m = *got.value();
  EXPECT_EQ(m.hd.instrument_id, want.hd.instrument_id);
  EXPECT_EQ(m.hd.ts_event, want.hd.ts_event);
  EXPECT_EQ(m.price, want.price);
  EXPECT_EQ(m.size, want.size);
  EXPECT_EQ(m.action, 'A');
  EXPECT_EQ(m.side, 'B');
  EXPECT_EQ(m.flags, 130u);
  EXPECT_EQ(m.ts_recv, want.ts_recv);
  EXPECT_EQ(m.sequence, want.sequence);
  EXPECT_EQ(m.levels[0].bid_px, 3891000000LL);
  EXPECT_EQ(m.levels[0].ask_px, 3892000000LL);
  EXPECT_EQ(m.levels[0].bid_sz, 4u);
  EXPECT_EQ(m.levels[0].ask_sz, 1u);
  auto end = s.next_mbp1();
  ASSERT_TRUE(end.has_value());
  EXPECT_EQ(end.value(), nullptr);
}

// --- DBN-12/13: the symbology inversion M0 depends on ----------------------
TEST(DbnSymbolIndex, ResolvesDateRangedSymbolsAndFallsBackToTheFirstInterval) {
  const auto body = metadata_body(qr::dbn::kSchemaMbp1, {"HG.v.0"}, simple_mappings());
  auto md = qr::dbn::parse_metadata_frame(1, body.data(), body.size());
  ASSERT_TRUE(md.has_value());
  SymbolIndex idx;
  idx.build(md.value());
  EXPECT_EQ(idx.symbol_for(31863, 20240115), "HG.v.0");
  EXPECT_EQ(idx.symbol_for(1101, 20240301), "HG.v.0");
  EXPECT_EQ(idx.symbol_for(99001, 20240115), "HGH4-HGK4");
  // Outside every interval: the first interval's raw symbol, never "".
  EXPECT_EQ(idx.symbol_for(31863, 20250101), "HG.v.0");
  // Unmapped id.
  EXPECT_EQ(idx.symbol_for(4242, 20240115), "");
}

TEST(DbnSymbolIndex, OutrightIsANonEmptySymbolWithoutADash) {
  EXPECT_TRUE(SymbolIndex::is_outright("SIN4"));
  EXPECT_FALSE(SymbolIndex::is_outright("SIN4-SIU4"));
  EXPECT_FALSE(SymbolIndex::is_outright(""));
}

}  // namespace
