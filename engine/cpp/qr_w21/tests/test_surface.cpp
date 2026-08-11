// qr_w21/tests/test_surface.cpp — the W2.1 constructors, red-first.
//
// Every test names the ruling it pins (design/DESIGN_FEATURES.md §W21-PIN-1,
// sha 0bb646c1e0de75e5) or the A2 sentence it implements, and every one of them
// is proven able to fail by a committed mutant in tests/red_ledger.tsv.
//
// NOT RE-TESTED HERE (already proven elsewhere, and the repository law forbids
// a second copy of an existing proof):
//   * the B3/B4 forbidden-column wall — qr_sources
//     `SpecLaws.TheWalledColumnsAreExactlyAppendixB`, mutant M315;
//   * the strictly-prior 1s-grid read and A2's 0.5bp event boundary — qr_w20
//     `SpotGridLaw.*`, mutants MW03/MW04/MW05;
//   * the 125..749 scope wall — qr_registry / qr_w20 `ScopeWallLaw`, mutant MW11.
#include <array>
#include <cmath>
#include <filesystem>
#include <map>
#include <string>
#include <vector>

#include "gtest/gtest.h"
#include "qr_emit/npy_writer.hpp"
#include "qr_registry/registry.hpp"
#include "qr_w21/surface.hpp"

namespace {

using qr::Validity;
using qr::sources::Right;
using namespace qr::w21;

constexpr std::int64_t kU6 = 1'000'000;

const qr::Registry& registry() {
  static qr::Expected<qr::Registry, qr::Refusal> loaded = qr::Registry::load_embedded();
  EXPECT_TRUE(loaded.has_value());
  return loaded.value();
}

std::filesystem::path scratch(const std::string& leaf) {
  const std::filesystem::path root = std::filesystem::path(QR_W21_TEST_SCRATCH) / leaf;
  std::filesystem::remove_all(root);
  std::filesystem::create_directories(root);
  return root;
}

LiveQuote quote(std::int64_t bid_u6, std::int64_t ask_u6, std::int64_t bid_size,
                std::int64_t ask_size, std::int64_t age_micros = 0) {
  LiveQuote out;
  out.bid_u6 = bid_u6;
  out.ask_u6 = ask_u6;
  out.bid_size = bid_size;
  out.ask_size = ask_size;
  out.age_micros = age_micros;
  return out;
}

/// The strike whose ln(K/m) is exactly `x_bps` against `spot_u6`, rounded to the
/// nearest u6 — used to place a contract ON a band edge.
std::int64_t strike_at_log_bps(std::int64_t spot_u6, std::int64_t x_bps) {
  for (std::int64_t candidate = static_cast<std::int64_t>(
           std::llround(static_cast<double>(spot_u6) *
                        std::exp(static_cast<double>(x_bps) / 10000.0))) -
                                4;
       candidate <= static_cast<std::int64_t>(
                        std::llround(static_cast<double>(spot_u6) *
                                     std::exp(static_cast<double>(x_bps) / 10000.0))) +
                        4;
       ++candidate) {
    const auto measured = moneyness_log_bps(candidate, spot_u6);
    if (measured.has_value() && measured.value() == x_bps) return candidate;
  }
  ADD_FAILURE() << "no strike reproduces " << x_bps << "bp against " << spot_u6;
  return 0;
}

}  // namespace

// ---------------------------------------------------------------------------
// Q1 / Q2 — the bucket axis.
// ---------------------------------------------------------------------------

TEST(BucketAxisLaw, AnExactEdgeFallsInTheBandAboveIt) {
  // Q1 edges {-150,-50,+50,+150}, RIGHT-OPEN per the substrate's bin law.
  EXPECT_EQ(moneyness_band(-151), 0U);
  EXPECT_EQ(moneyness_band(-150), 1U);  // exact edge -> band above
  EXPECT_EQ(moneyness_band(-51), 1U);
  EXPECT_EQ(moneyness_band(-50), 2U);   // exact edge
  EXPECT_EQ(moneyness_band(0), 2U);
  EXPECT_EQ(moneyness_band(49), 2U);
  EXPECT_EQ(moneyness_band(50), 3U);    // exact edge
  EXPECT_EQ(moneyness_band(149), 3U);
  EXPECT_EQ(moneyness_band(150), 4U);   // exact edge
  EXPECT_EQ(moneyness_band(1'000'000), 4U);
  EXPECT_EQ(moneyness_band(-1'000'000), 0U);
}

TEST(BucketAxisLaw, TheEdgeIsTheLogRatioAndNotTheLinearOne) {
  // The discriminating strike: exactly +150bp LINEAR above the spot. Its log
  // ratio is 10000*ln(1.015) = 148.886bp, so Q1's ln rule puts it in band 3
  // while a linear (K-m)/m rule would put it in band 4. One contract, two
  // different buckets — which is why Q1 says ln(K/m).
  const std::int64_t spot = 200 * kU6;
  const std::int64_t strike = spot + (spot * 150) / 10000;
  const std::int64_t linear_bps = ((strike - spot) * 10000) / spot;
  EXPECT_EQ(linear_bps, 150);
  EXPECT_EQ(moneyness_band(linear_bps), 4U);

  const auto x = moneyness_log_bps(strike, spot);
  ASSERT_TRUE(x.has_value());
  EXPECT_EQ(x.value(), 149);
  EXPECT_EQ(moneyness_band(x.value()), 3U);

  // And the exact-edge strike really does exist on the log scale.
  const auto on_edge = moneyness_log_bps(strike_at_log_bps(spot, 150), spot);
  ASSERT_TRUE(on_edge.has_value());
  EXPECT_EQ(on_edge.value(), 150);
  EXPECT_EQ(moneyness_band(on_edge.value()), 4U);

  const auto refused = moneyness_log_bps(strike, 0);
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}

TEST(BucketAxisLaw, TheSurfaceIsFiveByTwoByTwoAndEverythingElseIsOffSurface) {
  EXPECT_EQ(kBuckets, 20U);
  // Q2: the quote surface has exactly the DTE 0 and DTE 1 planes, because the
  // measured tape carries nothing else (D4 section 0.1).
  ASSERT_TRUE(bucket_index(0, 0, Right::Call).has_value());
  ASSERT_TRUE(bucket_index(0, 1, Right::Put).has_value());
  EXPECT_FALSE(bucket_index(0, 2, Right::Call).has_value());
  EXPECT_FALSE(bucket_index(0, 7, Right::Call).has_value());
  EXPECT_FALSE(bucket_index(0, -1, Right::Call).has_value());
  EXPECT_FALSE(bucket_index(0, 0, Right::Other).has_value());

  // The index is a bijection onto 0..19 and round-trips through bucket_key.
  std::array<int, kBuckets> seen{};
  for (std::size_t band = 0; band < kMoneynessBands; ++band) {
    for (std::int64_t dte = 0; dte < 2; ++dte) {
      for (const Right right : {Right::Call, Right::Put}) {
        const std::int64_t x = band == 0 ? -1000 : (band == 4 ? 1000 : kMoneynessEdgesBps[band - 1]);
        const auto index = bucket_index(x, dte, right);
        ASSERT_TRUE(index.has_value());
        ++seen[index.value()];
        const BucketKey key = bucket_key(index.value());
        EXPECT_EQ(key.moneyness_band, band);
        EXPECT_EQ(key.dte_plane, static_cast<std::size_t>(dte));
        EXPECT_EQ(key.right, right == Right::Call ? 0U : 1U);
      }
    }
  }
  for (const int count : seen) EXPECT_EQ(count, 1);
}

TEST(BucketAxisLaw, OrientationIsSigmaTimesRho) {
  const auto call = bucket_index(0, 0, Right::Call).value();
  const auto put = bucket_index(0, 0, Right::Put).value();
  EXPECT_EQ(orientation(call, true), 1);
  EXPECT_EQ(orientation(call, false), -1);
  EXPECT_EQ(orientation(put, true), -1);
  EXPECT_EQ(orientation(put, false), 1);
}

// ---------------------------------------------------------------------------
// Q4 — the bucket reduction.
// ---------------------------------------------------------------------------

TEST(BucketReductionLaw, NoRawPriceLevelSurvivesTheReduction) {
  // Q4's amendment as a structural fact: two buckets whose members have wildly
  // different PRICE levels but identical widths, sizes and ages reduce to the
  // same channels. A bucket that averaged raw prices could not do this.
  const std::vector<LiveQuote> cheap{quote(10 * kU6, 12 * kU6, 5, 5),
                                     quote(10 * kU6, 12 * kU6, 5, 5)};
  const std::vector<LiveQuote> rich{quote(1000 * kU6, 1002 * kU6, 5, 5),
                                    quote(1000 * kU6, 1002 * kU6, 5, 5)};
  const BucketSecond a = reduce_bucket(cheap);
  const BucketSecond b = reduce_bucket(rich);
  EXPECT_EQ(a.bid_size_sum, b.bid_size_sum);
  EXPECT_EQ(a.ask_size_sum, b.ask_size_sum);
  EXPECT_EQ(a.contracts, b.contracts);
  // The widths are identical in u6 but NOT in bps of the mid, which is exactly
  // what a spread channel should say.
  EXPECT_NE(a.mean_spread_bps.value, b.mean_spread_bps.value);
  EXPECT_EQ(a.mean_spread_bps.v, Validity::VALID);
  EXPECT_EQ(b.mean_spread_bps.v, Validity::VALID);
}

TEST(BucketReductionLaw, ValidityIsAtLeastHalfTwoSidedAndNeverOnAnEmptyBucket) {
  const BucketSecond empty = reduce_bucket(std::span<const LiveQuote>{});
  EXPECT_FALSE(empty.valid);
  EXPECT_EQ(empty.contracts, 0);
  EXPECT_EQ(empty.two_sided_fraction.v, Validity::MISSING);

  // 2 of 4 two-sided is EXACTLY half and must be VALID.
  const std::vector<LiveQuote> half{quote(1 * kU6, 2 * kU6, 3, 4), quote(1 * kU6, 2 * kU6, 3, 4),
                                    quote(0, 2 * kU6, 0, 4), quote(0, 2 * kU6, 0, 4)};
  const BucketSecond at_half = reduce_bucket(half);
  EXPECT_EQ(at_half.contracts, 4);
  EXPECT_EQ(at_half.two_sided, 2);
  EXPECT_TRUE(at_half.valid);

  // 1 of 3 is below half and must not be.
  const std::vector<LiveQuote> below{quote(1 * kU6, 2 * kU6, 3, 4), quote(0, 2 * kU6, 0, 4),
                                     quote(0, 2 * kU6, 0, 4)};
  const BucketSecond under = reduce_bucket(below);
  EXPECT_EQ(under.two_sided, 1);
  EXPECT_FALSE(under.valid);
}

TEST(BucketReductionLaw, TheMomentsAreSizeWeightedAndOrderInvariant) {
  // Hand-computed: widths 2.00 on a 11.00 mid = 1818bp (truncating), and 1.00
  // on a 10.50 mid = 952bp. Weights are bid_size+ask_size = 100 and 10.
  const LiveQuote wide = quote(10 * kU6, 12 * kU6, 60, 40);
  const LiveQuote tight = quote(10 * kU6, 11 * kU6, 5, 5);
  const std::vector<LiveQuote> forward{wide, tight};
  const std::vector<LiveQuote> reversed{tight, wide};
  const BucketSecond a = reduce_bucket(forward);
  const BucketSecond b = reduce_bucket(reversed);
  EXPECT_EQ(a.mean_spread_bps.value, b.mean_spread_bps.value);
  EXPECT_EQ(a.stdev_spread_bps.value, b.stdev_spread_bps.value);
  const double expected = (100.0 * 1818.0 + 10.0 * 952.0) / 110.0;
  EXPECT_NEAR(a.mean_spread_bps.value, expected, 1e-9);
  // A plain unweighted mean would be 1385, which the weighted one is not.
  EXPECT_GT(a.mean_spread_bps.value, 1700.0);
  EXPECT_GT(a.stdev_spread_bps.value, 0.0);
  EXPECT_EQ(a.bid_size_sum, 65);
  EXPECT_EQ(a.ask_size_sum, 45);
}

TEST(BucketReductionLaw, AOneSidedMemberHasNoSpreadButStillHasAnAge) {
  // The one-sided member carries 93 of the bucket's 100 units of displayed
  // size, so a reduction that dropped it from the AGE mean would land on a
  // completely different number rather than on a floating-point neighbour.
  const std::vector<LiveQuote> members{quote(0, 2 * kU6, 0, 93, 5'000),
                                       quote(1 * kU6, 2 * kU6, 3, 4, 1'000)};
  const BucketSecond out = reduce_bucket(members);
  EXPECT_EQ(out.contracts, 2);
  EXPECT_EQ(out.two_sided, 1);
  EXPECT_EQ(out.bid_size_sum, 3);
  EXPECT_EQ(out.ask_size_sum, 97);
  // The spread exists and comes from the two-sided member ALONE.
  EXPECT_EQ(out.mean_spread_bps.v, Validity::VALID);
  EXPECT_NEAR(out.mean_spread_bps.value, 6666.0, 1e-9);
  // The age mean covers BOTH members, size-weighted: 93 units at 5,000us and
  // 7 units at 1,000us.
  ASSERT_EQ(out.mean_log1p_age_micros.v, Validity::VALID);
  const double expected =
      (93.0 * std::log1p(5000.0) + 7.0 * std::log1p(1000.0)) / 100.0;
  EXPECT_NEAR(out.mean_log1p_age_micros.value, expected, 1e-12);
  // Dropping the one-sided member would give exactly log1p(1,000).
  EXPECT_GT(out.mean_log1p_age_micros.value, std::log1p(1000.0) + 1.0);
}

// ---------------------------------------------------------------------------
// Q3 / Q5 / Q8 — the straddle and PROXY_VOL.
// ---------------------------------------------------------------------------

TEST(ProxyVolLaw, TheThreeHundredSecondGuardFiresAndIsTypedNotZero) {
  const std::int64_t expiry_day = 20000;
  const std::int64_t close_ms = (expiry_day * 86400 + 16 * 3600) * 1000;
  // 301s before the expiry-day close: present.
  const Typed<double> alive = years_to_expiry(close_ms - 301'000, expiry_day);
  EXPECT_EQ(alive.v, Validity::VALID);
  EXPECT_GT(alive.value, 0.0);
  // Exactly 300s: still present (the guard is "< 300s").
  EXPECT_EQ(years_to_expiry(close_ms - 300'000, expiry_day).v, Validity::VALID);
  // 299s: the guard fires, and it is a TYPED absence, not a zero.
  const Typed<double> guarded = years_to_expiry(close_ms - 299'000, expiry_day);
  EXPECT_EQ(guarded.v, Validity::MODALITY_ABSENT);
  EXPECT_EQ(guarded.value, 0.0);
  // A guarded T can never produce a PROXY_VOL number.
  EXPECT_NE(proxy_vol(5 * kU6, 200 * kU6, guarded).v, Validity::VALID);
}

TEST(ProxyVolLaw, BidAndAskProxiesAreSeparateSeriesAndOrderedByTheirOwnStraddles) {
  const std::int64_t expiry_day = 20000;
  const std::int64_t close_ms = (expiry_day * 86400 + 16 * 3600) * 1000;
  const std::int64_t now = close_ms - 86'400'000;  // a full day out
  const Typed<double> years = years_to_expiry(now, expiry_day);
  ASSERT_EQ(years.v, Validity::VALID);
  const std::int64_t spot = 200 * kU6;
  const Typed<double> bid = proxy_vol(4 * kU6, spot, years);
  const Typed<double> mid = proxy_vol(5 * kU6, spot, years);
  const Typed<double> ask = proxy_vol(6 * kU6, spot, years);
  ASSERT_EQ(bid.v, Validity::VALID);
  ASSERT_EQ(ask.v, Validity::VALID);
  // A2 requires the two sides SEPARATELY: they are different numbers and the
  // bid-side proxy is strictly below the ask-side one for a positive width.
  EXPECT_LT(bid.value, mid.value);
  EXPECT_LT(mid.value, ask.value);
  // ... and the value is S/(m*sqrt(T)), computed exactly.
  EXPECT_NEAR(mid.value, (5.0 / 200.0) / std::sqrt(years.value), 1e-12);
  // A nonpositive straddle or spot is typed, never a number.
  EXPECT_EQ(proxy_vol(0, spot, years).v, Validity::NONPOSITIVE);
  EXPECT_EQ(proxy_vol(5 * kU6, 0, years).v, Validity::NONPOSITIVE);

  // ... AND THE SEPARATION MUST SURVIVE THE STRADDLE CONSTRUCTOR, not merely
  // the scalar helper: a builder that fed the mid straddle into all three
  // series would pass every assertion above.
  const std::int64_t expiry_day2 = 20000;
  const std::int64_t now2 = (expiry_day2 * 86400 + 16 * 3600) * 1000 - 86'400'000;
  StraddleLegs legs;
  const std::int64_t strike = strike_at_log_bps(spot, 5);
  legs.calls[strike] = quote(3 * kU6, 4 * kU6, 10, 10);
  legs.puts[strike] = quote(1 * kU6, 2 * kU6, 10, 10);
  const StraddleSecond built = select_straddle(legs, spot, now2, expiry_day2);
  ASSERT_TRUE(built.present);
  ASSERT_EQ(built.proxy_vol_bid.v, Validity::VALID);
  ASSERT_EQ(built.proxy_vol_mid.v, Validity::VALID);
  ASSERT_EQ(built.proxy_vol_ask.v, Validity::VALID);
  EXPECT_LT(built.proxy_vol_bid.value, built.proxy_vol_mid.value);
  EXPECT_LT(built.proxy_vol_mid.value, built.proxy_vol_ask.value);
  // Each series is the proxy of ITS OWN straddle, exactly.
  const Typed<double> years2 = years_to_expiry(now2, expiry_day2);
  EXPECT_NEAR(built.proxy_vol_bid.value,
              proxy_vol(built.straddle_bid_u6, spot, years2).value, 1e-15);
  EXPECT_NEAR(built.proxy_vol_ask.value,
              proxy_vol(built.straddle_ask_u6, spot, years2).value, 1e-15);
}

TEST(StraddleSelectionLaw, TheNearestBothSidedStrikeWinsAndNothingIsInterpolated) {
  const std::int64_t spot = 200 * kU6;
  const std::int64_t expiry_day = 20000;
  const std::int64_t now = (expiry_day * 86400 + 16 * 3600) * 1000 - 86'400'000;
  StraddleLegs legs;
  const std::int64_t near_strike = strike_at_log_bps(spot, 10);
  const std::int64_t far_strike = strike_at_log_bps(spot, -40);
  legs.calls[near_strike] = quote(3 * kU6, 4 * kU6, 10, 10);
  legs.puts[near_strike] = quote(1 * kU6, 2 * kU6, 10, 10);
  legs.calls[far_strike] = quote(5 * kU6, 6 * kU6, 10, 10);
  legs.puts[far_strike] = quote(7 * kU6, 8 * kU6, 10, 10);

  const StraddleSecond picked = select_straddle(legs, spot, now, expiry_day);
  ASSERT_TRUE(picked.present);
  EXPECT_EQ(picked.strike_u6, near_strike);
  EXPECT_EQ(picked.moneyness_bps, 10);
  // S_bid = C_bid + P_bid and S_ask = C_ask + P_ask, verbatim.
  EXPECT_EQ(picked.straddle_bid_u6, 4 * kU6);
  EXPECT_EQ(picked.straddle_ask_u6, 6 * kU6);
  EXPECT_EQ(picked.width_u6, 2 * kU6);
  // Nothing is interpolated: the selected strike is one the ladder contained.
  EXPECT_TRUE(legs.calls.count(picked.strike_u6) == 1);

  // Take the CALL leg one-sided at the nearest strike: the next-nearest strike
  // with BOTH legs two-sided wins instead.
  legs.calls[near_strike] = quote(0, 4 * kU6, 0, 10);
  const StraddleSecond fallback = select_straddle(legs, spot, now, expiry_day);
  ASSERT_TRUE(fallback.present);
  EXPECT_EQ(fallback.strike_u6, far_strike);
}

TEST(StraddleSelectionLaw, NothingInsideTheHundredFiftyBpWindowMeansAbsent) {
  const std::int64_t spot = 200 * kU6;
  const std::int64_t expiry_day = 20000;
  const std::int64_t now = (expiry_day * 86400 + 16 * 3600) * 1000 - 86'400'000;
  StraddleLegs legs;
  const std::int64_t outside = strike_at_log_bps(spot, 151);
  legs.calls[outside] = quote(3 * kU6, 4 * kU6, 10, 10);
  legs.puts[outside] = quote(1 * kU6, 2 * kU6, 10, 10);
  const StraddleSecond absent = select_straddle(legs, spot, now, expiry_day);
  EXPECT_FALSE(absent.present);
  EXPECT_EQ(absent.absence, Validity::MODALITY_ABSENT);

  // Exactly 150bp is INSIDE the window ("none within |ln(K/m)|<=150bp").
  const std::int64_t edge = strike_at_log_bps(spot, 150);
  StraddleLegs on_edge;
  on_edge.calls[edge] = quote(3 * kU6, 4 * kU6, 10, 10);
  on_edge.puts[edge] = quote(1 * kU6, 2 * kU6, 10, 10);
  EXPECT_TRUE(select_straddle(on_edge, spot, now, expiry_day).present);
}

TEST(StraddleSelectionLaw, TwoEquidistantStrikesAreUndecidableAndNeverBrokenByOrder) {
  const std::int64_t spot = 200 * kU6;
  const std::int64_t expiry_day = 20000;
  const std::int64_t now = (expiry_day * 86400 + 16 * 3600) * 1000 - 86'400'000;
  StraddleLegs legs;
  const std::int64_t below = strike_at_log_bps(spot, -20);
  const std::int64_t above = strike_at_log_bps(spot, 20);
  legs.calls[below] = quote(3 * kU6, 4 * kU6, 10, 10);
  legs.puts[below] = quote(1 * kU6, 2 * kU6, 10, 10);
  legs.calls[above] = quote(5 * kU6, 6 * kU6, 10, 10);
  legs.puts[above] = quote(7 * kU6, 8 * kU6, 10, 10);
  const StraddleSecond tied = select_straddle(legs, spot, now, expiry_day);
  // The repository law forbids breaking a scientific tie by id, hash or source
  // order, and no ruling picks one, so the selection is typed undecidable.
  EXPECT_FALSE(tied.present);
  EXPECT_EQ(tied.absence, Validity::EQUAL_TIME_UNORDERED);
}

// ---------------------------------------------------------------------------
// Q12 — MODALITY_ABSENT.
// ---------------------------------------------------------------------------

TEST(ModalityLaw, EveryOrdinalBelowTwoHundredAndNineIsModalityAbsentWithoutTouchingTheCorpus) {
  EXPECT_TRUE(SurfaceBuilder::session_is_modality_absent(125));
  EXPECT_TRUE(SurfaceBuilder::session_is_modality_absent(208));
  EXPECT_FALSE(SurfaceBuilder::session_is_modality_absent(209));
  EXPECT_FALSE(SurfaceBuilder::session_is_modality_absent(749));

  // The builder returns the typed block for an absent session even when the
  // corpus root and the tape root are both EMPTY directories — proof that no
  // path was formed and no payload was needed.
  const std::filesystem::path nowhere = scratch("absent");
  const auto scope = qr::DayScope::admit(registry(), 125);
  ASSERT_TRUE(scope.has_value());
  const auto built = SurfaceBuilder::build(scope.value(), nowhere, nowhere);
  ASSERT_TRUE(built.has_value()) << built.error().message();
  EXPECT_TRUE(built.value().modality_absent());
  EXPECT_EQ(built.value().modality(), Validity::MODALITY_ABSENT);
  EXPECT_EQ(built.value().rth_rows(), 0);
  EXPECT_EQ(built.value().valid_bucket_seconds(), 0);

  // ... and the census says MODALITY_ABSENT rather than emitting zeros that
  // would read as "measured and empty".
  qr::w20::CensusReport report;
  emit(report, 125, scope.value().day(), built.value());
  bool said_absent = false;
  bool emitted_a_surface_row = false;
  for (const qr::w20::CensusRow& row : report.rows()) {
    if (row.metric == "modality" && row.text == "MODALITY_ABSENT") said_absent = true;
    if (row.key == "surface") emitted_a_surface_row = true;
  }
  EXPECT_TRUE(said_absent);
  EXPECT_FALSE(emitted_a_surface_row);

  // A covered ordinal with no payload under an empty root is a REFUSAL, not a
  // silent absence: the two states may never be confused.
  const auto covered = qr::DayScope::admit(registry(), 209);
  ASSERT_TRUE(covered.has_value());
  const auto refused = SurfaceBuilder::build(covered.value(), nowhere, nowhere);
  EXPECT_FALSE(refused.has_value());
}
