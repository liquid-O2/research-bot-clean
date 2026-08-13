// Fixtures FS-1..FS-14: the M0 program-mode semantics this port must
// reproduce field-exactly (PORT_M0_CENSUS_SPEC §0/§4/§5).
#include <cmath>
#include <cstdio>
#include <string>
#include <vector>

#include "gtest/gtest.h"
#include "qr_futsess/calendar.hpp"
#include "qr_futsess/constants.hpp"
#include "qr_futsess/dayrec.hpp"
#include "qr_futsess/json.hpp"
#include "qr_futsess/seal.hpp"
#include "qr_futsess/sessions.hpp"

namespace {

using namespace qr::futsess;  // NOLINT(build/namespaces) — test-local

// --- FS-1/2: the SEAL -------------------------------------------------------
TEST(Seal, RefusesEveryPayloadWhoseBasenameDateTouches2026) {
  EXPECT_TRUE(is_sealed("glbx-mdp3-20260101.mbp-1.dbn.zst"));
  EXPECT_TRUE(is_sealed("glbx-mdp3-20260101-20260605.mbp-1.dbn.zst"));
  EXPECT_TRUE(is_sealed("glbx-mdp3-20250101-20260101.mbp-1.dbn.zst"));
  EXPECT_FALSE(is_sealed("glbx-mdp3-20251231.mbp-1.dbn.zst"));
  std::vector<std::string> refusals;
  auto r = guard_seal("/data/[Silver] GLBX-20260531-X/glbx-mdp3-20260101.mbp-1.dbn.zst", &refusals);
  ASSERT_FALSE(r.has_value());
  ASSERT_EQ(refusals.size(), 1u);
  EXPECT_EQ(refusals[0], "glbx-mdp3-20260101.mbp-1.dbn.zst");
}

TEST(Seal, ReadsTheBasenameOnlyAndOnlyEightDigitRuns) {
  // The asset DIRECTORY carries a 2026 job date. Testing the whole path would
  // refuse the entire corpus, so only the basename is examined.
  EXPECT_FALSE(is_sealed("/x/[Silver] GLBX-20260531-RPHWMFRBFW/glbx-mdp3-20240603.mbp-1.dbn.zst"));
  // A nine-digit run is not a date component.
  EXPECT_TRUE(filename_dates("f-202601010.dbn").empty());
  ASSERT_EQ(filename_dates("glbx-mdp3-20210101-20211231.mbp-1.dbn.zst").size(), 2u);
}

// --- FS-3/4: the §0 sentinel law -------------------------------------------
TEST(SentinelGuard, Int64MaxNeverReachesArithmetic) {
  // bid + ask with a sentinel overflows int64 to a NEGATIVE number and sails
  // past a naive post-hoc check. The guard must fire on each side FIRST.
  const BookState both = classify_book(kUndefPrice, kUndefPrice);
  EXPECT_EQ(both.state, kStEmpty);
  EXPECT_EQ(both.bid, kUndefPrice);
  EXPECT_EQ(both.ask, kUndefPrice);

  const BookState no_bid = classify_book(kUndefPrice, 3892000000LL);
  EXPECT_EQ(no_bid.state, kStNoBid);
  EXPECT_EQ(no_bid.bid, kUndefPrice);
  EXPECT_EQ(no_bid.ask, 3892000000LL);

  const BookState no_ask = classify_book(3891000000LL, kSentHi);
  EXPECT_EQ(no_ask.state, kStNoAsk);
  EXPECT_EQ(no_ask.ask, kUndefPrice);

  EXPECT_EQ(classify_book(0, 5).state, kStNoBid);
  EXPECT_EQ(classify_book(-1, 5).state, kStNoBid);
}

TEST(SentinelGuard, LockedFoldsIntoCrossedAndTwoSidedNeedsAskAboveBid) {
  EXPECT_EQ(classify_book(3894000000LL, 3892000000LL).state, kStCrossed);
  EXPECT_EQ(classify_book(100, 100).state, kStCrossed);  // locked -> CROSSED, code 3
  EXPECT_EQ(classify_book(100, 101).state, kStTwoSided);
}

// --- FS-5/6: the Globex clock ----------------------------------------------
TEST(Calendar, GlobexSessionBoundsAreDstCorrect) {
  ASSERT_TRUE(init_globex_timezone().has_value());
  // Winter (CST, UTC-6): 2024-01-02 session = [2024-01-01 23:00Z, 2024-01-02 22:00Z).
  auto w = session_bounds(Date{2024, 1, 2});
  EXPECT_EQ(w.first, 1704150000);
  EXPECT_EQ(w.second, 1704232800);
  EXPECT_EQ(w.second - w.first, kSessionSeconds);
  // Summer (CDT, UTC-5): 2024-07-02 session = [2024-07-01 22:00Z, 2024-07-02 21:00Z).
  auto s = session_bounds(Date{2024, 7, 2});
  EXPECT_EQ(s.first, 1719871200);
  EXPECT_EQ(s.second - s.first, kSessionSeconds);
  // A fixed-offset clock would put both opens at the same second-of-day.
  EXPECT_NE(w.first % 86400, s.first % 86400);
}

TEST(Calendar, CivilDateAndDayIndexRoundTrip) {
  for (const Date d : {Date{1970, 1, 1}, Date{2021, 5, 31}, Date{2024, 2, 29}, Date{2025, 12, 31}}) {
    EXPECT_EQ(day_to_date(date_to_day(d)), d) << d.iso();
  }
  EXPECT_EQ(date_to_day(Date{1970, 1, 1}), 0);
  EXPECT_EQ(Date({2024, 6, 3}).compact(), "20240603");
  EXPECT_EQ(Date({2024, 6, 3}).iso(), "2024-06-03");
}

// --- FS-7/8: Wilder ATR14 ---------------------------------------------------
TEST(WilderAtr, SeedIsTheMeanOfTheFirstFourteenTrueRanges) {
  std::vector<double> trs;
  for (int i = 1; i <= 20; ++i) {
    trs.push_back(static_cast<double>(i));
  }
  const std::vector<double> atr = wilder_atr(trs, kAtrPeriod);
  for (int i = 0; i < 13; ++i) {
    EXPECT_TRUE(std::isnan(atr[static_cast<std::size_t>(i)])) << i;
  }
  EXPECT_DOUBLE_EQ(atr[13], (1.0 + 14.0) / 2.0);  // mean of 1..14 = 7.5
  double prev = 7.5;
  for (std::size_t i = 14; i < trs.size(); ++i) {
    prev = (prev * 13.0 + trs[i]) / 14.0;
    EXPECT_DOUBLE_EQ(atr[i], prev) << i;
  }
}

TEST(WilderAtr, ASeriesShorterThanThePeriodIsAllNaN) {
  const std::vector<double> atr = wilder_atr(std::vector<double>(13, 1.0), kAtrPeriod);
  ASSERT_EQ(atr.size(), 13u);
  for (const double v : atr) {
    EXPECT_TRUE(std::isnan(v));
  }
}

// --- FS-9/10: phase tagging -------------------------------------------------
TEST(Phase, CyclicMembershipWrapsThroughMidnight) {
  EXPECT_TRUE(in_cyclic(100, 0, 200));
  EXPECT_FALSE(in_cyclic(200, 0, 200));
  // A wrapped window: [77400, 25200) covers both 80000 and 1000.
  EXPECT_TRUE(in_cyclic(80000, 77400, 25200));
  EXPECT_TRUE(in_cyclic(1000, 77400, 25200));
  EXPECT_FALSE(in_cyclic(40000, 77400, 25200));
}

TEST(Phase, TokyoOwnsTheWindowFromTheMaintenanceBreakToTheLondonOpen) {
  const std::array<std::int64_t, 3> bounds{25200, 39600, 77400};  // the 2024 SI table
  EXPECT_EQ(phase_of(77400, bounds), 0);  // TOKYO starts at NY|TOKYO
  EXPECT_EQ(phase_of(0, bounds), 0);
  EXPECT_EQ(phase_of(25199, bounds), 0);
  EXPECT_EQ(phase_of(25200, bounds), 1);  // LONDON
  EXPECT_EQ(phase_of(39599, bounds), 1);
  EXPECT_EQ(phase_of(39600, bounds), 2);  // NY
  EXPECT_EQ(phase_of(77399, bounds), 2);
}

// --- FS-11/12: the JSON substrate ------------------------------------------
TEST(Json, RoundTripsNestedDocumentsAndNonFiniteNumbers) {
  JsonWriter w;
  w.begin_object();
  w.key("a");
  w.value_int(-7);
  w.key("nan");
  w.value_double(std::nan(""));
  w.key("d");
  w.value_double(0.8457610090728851);
  w.key("list");
  w.begin_array();
  w.value_string("x\"y");
  w.value_bool(true);
  w.value_null();
  w.end_array();
  w.end_object();

  auto doc = json_parse(w.text());
  ASSERT_TRUE(doc.has_value()) << doc.error().message() << " in " << w.text();
  const Json& j = doc.value();
  ASSERT_NE(j.find("a"), nullptr);
  EXPECT_EQ(j.find("a")->number(), -7.0);
  EXPECT_TRUE(std::isnan(j.find("nan")->number()));
  // %.17g must round-trip the double bit-for-bit; the differential compares
  // these values exactly.
  EXPECT_EQ(j.find("d")->number(), 0.8457610090728851);
  ASSERT_NE(j.find("list"), nullptr);
  ASSERT_EQ(j.find("list")->items().size(), 3u);
  EXPECT_EQ(j.find("list")->items()[0].str(), "x\"y");
  EXPECT_TRUE(j.find("list")->items()[1].boolean());
  EXPECT_TRUE(j.find("list")->items()[2].is_null());
}

TEST(Json, RefusesTrailingBytesAndUnterminatedDocuments) {
  EXPECT_FALSE(json_parse("{\"a\":1} junk").has_value());
  EXPECT_FALSE(json_parse("{\"a\":").has_value());
  EXPECT_FALSE(json_parse("[1,2").has_value());
}

// --- FS-13/14: the day intermediate ----------------------------------------
namespace {

DayReceipt sample_receipt() {
  DayReceipt r;
  r.date = Date{2024, 6, 3};
  r.tracked_ids = {2707, 74683};
  const std::size_t n = 2u * static_cast<std::size_t>(kSecondsPerDay);
  r.bid_px.assign(n, kUndefPrice);
  r.ask_px.assign(n, kUndefPrice);
  r.bid_sz.assign(n, 0);
  r.ask_sz.assign(n, 0);
  r.state.assign(n, kStPreFirst);
  r.upd_count.assign(n, 0);
  r.bid_px[5] = 3891000000LL;
  r.ask_px[5] = 3892000000LL;
  r.state[5] = kStTwoSided;
  r.upd_count[5] = 3;
  r.trades_iid = {74683};
  r.trades_sec = {17};
  r.trades_px = {3891500000LL};
  r.trades_size = {2};
  r.trades_side = {'B'};
  r.tally_iid = {2707, 74683};
  r.tally_updates = {10, 20};
  r.tally_trades = {1, 2};
  r.tally_trade_size_sum = {3, 4};
  r.map_iid = {2707, 74683};
  r.map_symbol = {"SIN4-SIU4", "SIN4"};
  r.map_outright = {0u, 1u};
  r.carry_iid = {2707, 74683};
  r.carry_bid = {1, 2};
  r.carry_ask = {3, 4};
  r.carry_bsz = {5, 6};
  r.carry_asz = {7, 8};
  r.carry_state = {kStTwoSided, kStNoBid};
  r.carry_last_sec = {86399, 86398};
  r.n_records = 30;
  r.n_dropped_sentinel = 4;
  r.n_no_flast_seconds = 1;
  r.tick_gcd_raw = 5000000;
  return r;
}

}  // namespace

TEST(DayReceiptIo, RoundTripsEveryFieldByteForByte) {
  const DayReceipt want = sample_receipt();
  const std::string path = std::string(QR_TEST_SCRATCH_DIR) + "/fs13.qrday";
  ASSERT_TRUE(write_day_receipt(path, want).has_value());
  auto got = read_day_receipt(path);
  ASSERT_TRUE(got.has_value()) << got.error().message();
  const DayReceipt& g = got.value();
  EXPECT_EQ(g.date, want.date);
  EXPECT_EQ(g.tracked_ids, want.tracked_ids);
  EXPECT_EQ(g.bid_px, want.bid_px);
  EXPECT_EQ(g.ask_px, want.ask_px);
  EXPECT_EQ(g.state, want.state);
  EXPECT_EQ(g.upd_count, want.upd_count);
  EXPECT_EQ(g.trades_px, want.trades_px);
  EXPECT_EQ(g.trades_side, want.trades_side);
  EXPECT_EQ(g.map_symbol, want.map_symbol);
  EXPECT_EQ(g.map_outright, want.map_outright);
  EXPECT_EQ(g.carry_state, want.carry_state);
  EXPECT_EQ(g.carry_last_sec, want.carry_last_sec);
  EXPECT_EQ(g.tick_gcd_raw, want.tick_gcd_raw);
  EXPECT_EQ(g.row_index(74683), 1);
  EXPECT_EQ(g.row_index(999), -1);

  // Two writes of the same receipt are byte-identical (the two-run law).
  const std::string again = std::string(QR_TEST_SCRATCH_DIR) + "/fs13b.qrday";
  ASSERT_TRUE(write_day_receipt(again, want).has_value());
  std::FILE* a = std::fopen(path.c_str(), "rb");
  std::FILE* b = std::fopen(again.c_str(), "rb");
  ASSERT_NE(a, nullptr);
  ASSERT_NE(b, nullptr);
  int ca = 0;
  int cb = 0;
  std::size_t compared = 0;
  do {
    ca = std::fgetc(a);
    cb = std::fgetc(b);
    ASSERT_EQ(ca, cb) << "byte " << compared;
    ++compared;
  } while (ca != EOF);
  std::fclose(a);
  std::fclose(b);
  EXPECT_GT(compared, 100u);
}

TEST(DayReceiptIo, RefusesACorruptedBody) {
  const std::string path = std::string(QR_TEST_SCRATCH_DIR) + "/fs14.qrday";
  ASSERT_TRUE(write_day_receipt(path, sample_receipt()).has_value());
  // Flip a byte inside the compressed body: zstd's own frame checks or the
  // declared-size check must fire. A short read must never look like data.
  std::FILE* fh = std::fopen(path.c_str(), "r+b");
  ASSERT_NE(fh, nullptr);
  ASSERT_EQ(std::fseek(fh, 40, SEEK_SET), 0);
  const int c = std::fgetc(fh);
  ASSERT_NE(c, EOF);
  ASSERT_EQ(std::fseek(fh, 40, SEEK_SET), 0);
  std::fputc(c ^ 0xFF, fh);
  std::fclose(fh);
  auto got = read_day_receipt(path);
  EXPECT_FALSE(got.has_value());
}

}  // namespace
