// Fixture DBN-R: the REAL-FILE cross-check that pins the struct layout.
//
// PORT_M1_SPEC §1.1 requires the DBN layout be decoded from the databento_dbn
// library's record introspection AND cross-checked against a real file. The
// expected values below were read out of `databento_dbn` (the ORACLE) over the
// first records of this payload; this test proves the C++ decoder, which never
// links that library, reproduces them from the bytes.
//
// The file is one of the corpus's unsealed yearly payloads. Only its head is
// read, so the test costs milliseconds despite the file being 13 GB.
#include <string>

#include "gtest/gtest.h"
#include "qr_dbn/dbn.hpp"

namespace {

TEST(DbnRealFile, MetadataAndLeadingRecordsMatchTheOracle) {
  qr::dbn::DbnStream s;
  auto opened = s.open(QR_DBN_REAL_FILE);
  ASSERT_TRUE(opened.has_value()) << opened.error().message();

  const qr::dbn::Metadata& md = s.metadata();
  EXPECT_EQ(md.version, 1u) << "the corpus payloads are DBN v1 streams";
  EXPECT_EQ(md.dataset, "GLBX.MDP3");
  EXPECT_EQ(md.schema, qr::dbn::kSchemaMbp1);
  EXPECT_EQ(md.stype_in, 3u);   // continuous
  EXPECT_EQ(md.stype_out, 0u);  // instrument_id
  EXPECT_EQ(md.start, 1704067200000000000ull);
  EXPECT_EQ(md.end, 1735689600000000000ull);
  ASSERT_EQ(md.symbols.size(), 1u);
  EXPECT_EQ(md.symbols[0], "HG.v.0");
  ASSERT_EQ(md.mappings.size(), 1u);
  EXPECT_EQ(md.mappings[0].raw_symbol, "HG.v.0");
  ASSERT_EQ(md.mappings[0].intervals.size(), 6u);
  EXPECT_EQ(md.mappings[0].intervals[0].start_date, 20240101);
  EXPECT_EQ(md.mappings[0].intervals[0].end_date, 20240226);
  EXPECT_EQ(md.mappings[0].intervals[0].symbol, "31863");
  EXPECT_EQ(md.mappings[0].intervals[5].start_date, 20241127);
  EXPECT_EQ(md.mappings[0].intervals[5].end_date, 20250101);
  EXPECT_EQ(md.mappings[0].intervals[5].symbol, "19222");

  auto first = s.next_mbp1();
  ASSERT_TRUE(first.has_value()) << first.error().message();
  ASSERT_NE(first.value(), nullptr);
  const qr::dbn::Mbp1Msg r0 = *first.value();
  EXPECT_EQ(r0.hd.length, 20u);  // 20 * 4 = 80 bytes
  EXPECT_EQ(r0.hd.rtype, qr::dbn::kRTypeMbp1);
  EXPECT_EQ(r0.hd.publisher_id, 1u);
  EXPECT_EQ(r0.hd.instrument_id, 31863u);
  EXPECT_EQ(r0.hd.ts_event, 1704027604498741347ull);
  EXPECT_EQ(r0.price, 4461500000LL);
  EXPECT_EQ(r0.size, 2u);
  EXPECT_EQ(r0.action, 'A');
  EXPECT_EQ(r0.side, 'N');
  EXPECT_EQ(r0.flags, 168u);
  EXPECT_EQ(r0.ts_recv, 1704067200000000000ull);
  EXPECT_EQ(r0.sequence, 13740u);
  EXPECT_EQ(r0.levels[0].bid_px, 3891000000LL);
  EXPECT_EQ(r0.levels[0].ask_px, 3892000000LL);
  EXPECT_EQ(r0.levels[0].bid_sz, 4u);
  EXPECT_EQ(r0.levels[0].ask_sz, 1u);

  auto second = s.next_mbp1();
  ASSERT_TRUE(second.has_value()) << second.error().message();
  ASSERT_NE(second.value(), nullptr);
  const qr::dbn::Mbp1Msg r1 = *second.value();
  EXPECT_EQ(r1.hd.ts_event, 1704149171523421785ull);
  EXPECT_EQ(r1.side, 'B');
  EXPECT_EQ(r1.flags, 130u);
  EXPECT_EQ(r1.sequence, 25814u);
  // This record's top of book is CROSSED (bid >= ask); the M0 state machine
  // must see it as such, so the decoder must not normalise it away.
  EXPECT_EQ(r1.levels[0].bid_px, 3894000000LL);
  EXPECT_EQ(r1.levels[0].ask_px, 3892000000LL);

  // Ten thousand more records decode without a single guard firing.
  for (int i = 0; i < 10000; ++i) {
    auto n = s.next_mbp1();
    ASSERT_TRUE(n.has_value()) << "record " << i << ": " << n.error().message();
    ASSERT_NE(n.value(), nullptr);
    EXPECT_EQ(n.value()->hd.rtype, qr::dbn::kRTypeMbp1);
  }
  EXPECT_EQ(s.n_skipped(), 0u);
}

}  // namespace
