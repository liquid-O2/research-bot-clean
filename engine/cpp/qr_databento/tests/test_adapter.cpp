#include <gtest/gtest.h>

#include <cstdint>
#include <string>

#include "qr_databento/adapter.hpp"
#include "qr_dbn/dbn.hpp"

namespace {

TEST(DatabentoAdapter, AuthorityIsFrozenAndExplicitAboutPortability) {
  const auto& authority = qr::databento::build_authority();
  EXPECT_STREQ(authority.databento_version, "0.64.0");
  EXPECT_STREQ(authority.declared_upstream_commit,
               "12eca77e70137ea848e4af3f4173ee0569cbf1aa");
  EXPECT_EQ(std::string(authority.vendor_tree_sha256).size(), 64u);
  EXPECT_EQ(std::string(authority.adapter_source_sha256).size(), 64u);
  EXPECT_EQ(std::string(authority.clock_law_sha256).size(), 64u);
  EXPECT_NE(std::string(authority.portability_gap).find("build-cache"),
            std::string::npos);
}

TEST(DatabentoAdapter, FullSiSnapshotMatchesIndependentOracleInPhysicalOrder) {
  const std::string path = QR_DATABENTO_SI_SNAPSHOT_FILE;
  qr::databento::Mbp1File official;
  auto opened = official.open(path);
  ASSERT_TRUE(opened) << opened.error().message();

  qr::dbn::DbnStream custom;
  auto custom_opened = custom.open(path);
  ASSERT_TRUE(custom_opened) << custom_opened.error().message();
  std::uint64_t count = 0;
  std::uint64_t snapshot_count = 0;
  std::uint64_t previous_recv = 0;
  bool have_previous = false;
  while (true) {
    auto lhs = official.next_mbp1();
    ASSERT_TRUE(lhs) << lhs.error().message();
    auto rhs = custom.next_mbp1();
    ASSERT_TRUE(rhs) << rhs.error().message();
    if (!lhs.value().has_value()) {
      EXPECT_EQ(rhs.value(), nullptr);
      break;
    }
    ASSERT_NE(rhs.value(), nullptr);
    const auto& a = *lhs.value();
    const auto& b = *rhs.value();
    EXPECT_EQ(a.source_ordinal, count);
    EXPECT_EQ(a.publisher_id, b.hd.publisher_id);
    EXPECT_EQ(a.instrument_id, b.hd.instrument_id);
    EXPECT_EQ(a.ts_recv_ns, b.ts_recv);
    EXPECT_EQ(a.ts_event_ns, b.hd.ts_event);
    EXPECT_EQ(a.sequence, b.sequence);
    EXPECT_EQ(a.price, b.price);
    EXPECT_EQ(a.size, b.size);
    EXPECT_EQ(a.action, b.action);
    EXPECT_EQ(a.side, b.side);
    EXPECT_EQ(a.flags, b.flags);
    EXPECT_EQ(a.depth, b.depth);
    EXPECT_EQ(a.ts_in_delta_ns, b.ts_in_delta);
    EXPECT_EQ(a.bid_px, b.levels[0].bid_px);
    EXPECT_EQ(a.ask_px, b.levels[0].ask_px);
    EXPECT_EQ(a.bid_sz, b.levels[0].bid_sz);
    EXPECT_EQ(a.ask_sz, b.levels[0].ask_sz);
    EXPECT_EQ(a.bid_ct, b.levels[0].bid_ct);
    EXPECT_EQ(a.ask_ct, b.levels[0].ask_ct);
    if (have_previous) {
      EXPECT_LE(previous_recv, a.ts_recv_ns);
    }
    previous_recv = a.ts_recv_ns;
    have_previous = true;
    if ((a.flags & (qr::databento::kFlagSnapshot |
                    qr::databento::kFlagBadTsRecv)) ==
        (qr::databento::kFlagSnapshot | qr::databento::kFlagBadTsRecv)) {
      ++snapshot_count;
    }
    if (count == 3u) {
      EXPECT_EQ(a.instrument_id, 32490u);
      EXPECT_EQ(a.ts_event_ns, 1622419198740669027ULL);
      EXPECT_EQ(a.ts_recv_ns, 1622419200000000000ULL);
    } else if (count == 4u) {
      EXPECT_EQ(a.instrument_id, 79190u);
      EXPECT_EQ(a.ts_event_ns, 1622401207681005329ULL);
      EXPECT_EQ(a.ts_recv_ns, 1622419200000000000ULL);
    }
    ++count;
  }
  EXPECT_EQ(count, 331441u);
  EXPECT_EQ(snapshot_count, 45u);
}

}  // namespace
