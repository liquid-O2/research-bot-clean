// RED-FIRST FIXTURES for the traded-IV cross-section (qr_ivx/iv_cross.hpp).
//
// The three laws the brief names explicitly — ORIENTATION, WEIGHTING and the
// WINDOW law — get a case each that fails if the law is inverted, dropped or
// shifted by one. The admission laws (B3's both-attachments rule, the
// single-leg rule) get cases because a census that silently admits a row it
// should not is a census with a wrong denominator everywhere.
#include <gtest/gtest.h>

#include <cmath>
#include <cstdint>
#include <array>
#include <limits>
#include <string>
#include <vector>

#include "qr_ivx/iv_cross.hpp"
#include "qr_sources/normalize.hpp"
#include "qr_w21/surface.hpp"

namespace {

constexpr std::int64_t kOpenMs = 1'657'020'600'000;  // an arbitrary frame-B open
constexpr std::int64_t kEpochDay = kOpenMs / 86'400'000;
const std::string kDay = "2022-07-05";

/// A fully admissible print, which each case then breaks in exactly one way.
qr::sources::OptionPrintRow print(std::int64_t second, double strike, double spot, double iv,
                                 std::int64_t size, qr::sources::Right right,
                                 std::int32_t dte_days = 0) {
  qr::sources::OptionPrintRow row;
  row.ts_ms_b = kOpenMs + second * 1000;
  row.quote_ts_ms_b = row.ts_ms_b - 1;  // STRICTLY prior
  row.condition = 18;                   // B3's single-leg set
  row.size = size;
  row.price_u6 = 1'000'000;
  row.strike_u6 = static_cast<std::int64_t>(std::llround(strike * 1e6));
  row.bid_u6 = 900'000;
  row.ask_u6 = 1'100'000;
  row.bid_size = 5;
  row.ask_size = 5;
  row.implied_vol = iv;
  row.underlying_price = spot;
  row.expiration_day = static_cast<std::int32_t>(kEpochDay) + dte_days;
  row.right = right;
  row.null_mask = 0;
  const auto stamp = qr::sources::inline_text(kDay + "T09:30:00.000");
  row.underlying_ts_text = stamp.value();
  return row;
}

/// A five-strike smile around spot 100 whose PUT wing is richer than its CALL
/// wing (the classic equity-index shape) or, mirrored, the reverse.
std::vector<qr::sources::OptionPrintRow> smile(bool put_rich, std::int64_t second = 10,
                                               std::int64_t size = 100) {
  const double spot = 100.0;
  // ln(K/m) at these strikes is roughly -400, -200, 0, +200, +400 bps.
  const std::array<double, 5> strikes{96.0, 98.0, 100.0, 102.0, 104.0};
  std::vector<qr::sources::OptionPrintRow> rows;
  for (std::size_t index = 0; index < strikes.size(); ++index) {
    // The tilt is written in the module's OWN coordinate — the rounded integer
    // ln-moneyness it bins and fits on — so "a pure tilt has no curvature" is a
    // statement about the fit, not about the rounding.
    const auto strike_u6 = static_cast<std::int64_t>(std::llround(strikes[index] * 1e6));
    const auto spot_u6 = static_cast<std::int64_t>(std::llround(spot * 1e6));
    const auto bps = qr::w21::moneyness_log_bps(strike_u6, spot_u6);
    const double x = static_cast<double>(bps.value()) / 10000.0;
    // A pure tilt: IV falls with strike when the puts are rich.
    const double iv = 0.25 + (put_rich ? -1.0 : 1.0) * x;
    if (strikes[index] <= spot) {
      rows.push_back(print(second, strikes[index], spot, iv, size, qr::sources::Right::Put));
    }
    if (strikes[index] >= spot) {
      rows.push_back(print(second, strikes[index], spot, iv, size, qr::sources::Right::Call));
    }
  }
  return rows;
}

qr::ivx::TradedIvTables run(const std::vector<qr::sources::OptionPrintRow>& rows,
                            qr::ivx::TradedIvOptions options = {}) {
  qr::ivx::TradedIvSession session(125, kDay, "IWM", kOpenMs, kEpochDay, options);
  for (const auto& row : rows) session.observe(row);
  return session.finish();
}

const qr::ivx::SkewCell* cell_of(const qr::ivx::TradedIvTables& tables, std::int64_t window,
                                 std::int32_t expiry) {
  for (const qr::ivx::SkewCell& cell : tables.cells) {
    if (cell.window == window && cell.expiration_day == expiry) return &cell;
  }
  return nullptr;
}

}  // namespace

// ---------------------------------------------------------------------------
// THE MONEYNESS AXIS.
// ---------------------------------------------------------------------------

// The four §W21-PIN-1 edges must still be edges. If the finer ATM steps had
// been added by MOVING an edge instead of inserting between them, the traded
// curve and the quote surface would no longer be talking about the same bands.
TEST(MoneynessAxis, KeepsTheW21Pin1Edges) {
  const std::vector<std::int64_t> pinned{-150, -50, 50, 150};
  for (const std::int64_t edge : pinned) {
    bool found = false;
    for (const std::int64_t candidate : qr::ivx::kMoneynessEdgesBps) {
      found = found || candidate == edge;
    }
    EXPECT_TRUE(found) << "the §W21-PIN-1 edge " << edge << " was dropped";
  }
}

// RIGHT-OPEN, per the substrate bin law: a value exactly ON an edge belongs to
// the band that edge OPENS, never the one it closes.
TEST(MoneynessAxis, EdgesAreRightOpen) {
  EXPECT_EQ(qr::ivx::moneyness_band(-151), 1U);
  EXPECT_EQ(qr::ivx::moneyness_band(-150), 2U);
  EXPECT_EQ(qr::ivx::moneyness_band(-51), 2U);
  EXPECT_EQ(qr::ivx::moneyness_band(-50), 3U);
  EXPECT_EQ(qr::ivx::moneyness_band(-26), 3U);
  EXPECT_EQ(qr::ivx::moneyness_band(-25), 4U);
  EXPECT_EQ(qr::ivx::moneyness_band(0), 4U);
  EXPECT_EQ(qr::ivx::moneyness_band(24), 4U);
  EXPECT_EQ(qr::ivx::moneyness_band(25), 5U);
  EXPECT_EQ(qr::ivx::moneyness_band(300), 8U);
  EXPECT_EQ(qr::ivx::moneyness_band(299), 7U);
}

TEST(MoneynessAxis, EveryIntegerLandsInExactlyOneBand) {
  for (std::int64_t x = -1000; x <= 1000; ++x) {
    EXPECT_LT(qr::ivx::moneyness_band(x), qr::ivx::kBands);
  }
}

// ---------------------------------------------------------------------------
// THE ORIENTATION LAW.
// ---------------------------------------------------------------------------

// POSITIVE = puts richer. Inverting the subtraction would flip the sign of
// every skew channel in the program and no aggregate would notice.
TEST(SkewOrientation, PutRichSmileIsPositive) {
  const qr::ivx::TradedIvTables tables = run(smile(/*put_rich=*/true));
  const qr::ivx::SkewCell* cell = cell_of(tables, 0, static_cast<std::int32_t>(kEpochDay));
  ASSERT_NE(cell, nullptr);
  ASSERT_EQ(cell->risk_reversal.v, qr::Validity::VALID);
  EXPECT_GT(cell->risk_reversal.value, 0.0);
  ASSERT_EQ(cell->skew_slope.v, qr::Validity::VALID);
  EXPECT_GT(cell->skew_slope.value, 0.0);
}

TEST(SkewOrientation, CallRichSmileIsNegativeAndExactlyMirrored) {
  const qr::ivx::TradedIvTables put_rich = run(smile(/*put_rich=*/true));
  const qr::ivx::TradedIvTables call_rich = run(smile(/*put_rich=*/false));
  const qr::ivx::SkewCell* a = cell_of(put_rich, 0, static_cast<std::int32_t>(kEpochDay));
  const qr::ivx::SkewCell* b = cell_of(call_rich, 0, static_cast<std::int32_t>(kEpochDay));
  ASSERT_NE(a, nullptr);
  ASSERT_NE(b, nullptr);
  ASSERT_EQ(b->risk_reversal.v, qr::Validity::VALID);
  EXPECT_LT(b->risk_reversal.value, 0.0);
  EXPECT_NEAR(a->risk_reversal.value, -b->risk_reversal.value, 1e-12);
}

// The slope is the difference PER UNIT of ln-moneyness travelled between the
// two anchors, i.e. divided by 2 x 0.0150. A missing (or doubled) factor would
// silently rescale every downstream comparison.
TEST(SkewOrientation, SlopeIsTheRiskReversalPerLnMoneyness) {
  const qr::ivx::TradedIvTables tables = run(smile(/*put_rich=*/true));
  const qr::ivx::SkewCell* cell = cell_of(tables, 0, static_cast<std::int32_t>(kEpochDay));
  ASSERT_NE(cell, nullptr);
  EXPECT_NEAR(cell->skew_slope.value,
              cell->risk_reversal.value / (2.0 * qr::ivx::kWingAnchorLn), 1e-12);
}

// A pure tilt has NO curvature. A quadratic fit that leaked the linear term
// into `curvature` would report a smile where there is only a skew.
TEST(SkewOrientation, PureTiltHasZeroCurvature) {
  const qr::ivx::TradedIvTables tables = run(smile(/*put_rich=*/true));
  const qr::ivx::SkewCell* cell = cell_of(tables, 0, static_cast<std::int32_t>(kEpochDay));
  ASSERT_NE(cell, nullptr);
  ASSERT_EQ(cell->curvature.v, qr::Validity::VALID);
  EXPECT_NEAR(cell->curvature.value, 0.0, 1e-9);
}

// ---------------------------------------------------------------------------
// THE WEIGHTING LAW.
// ---------------------------------------------------------------------------

// SIZE-WEIGHTED means one print of 3 lots equals three prints of 1 lot. An
// unweighted mean would pass every other test in this file and be wrong.
TEST(Weighting, OnePrintOfThreeEqualsThreePrintsOfOne) {
  std::vector<qr::sources::OptionPrintRow> heavy = smile(true);
  std::vector<qr::sources::OptionPrintRow> split;
  for (const auto& row : heavy) {
    qr::sources::OptionPrintRow one = row;
    one.size = 1;
    split.push_back(one);
    split.push_back(one);
    split.push_back(one);
  }
  for (auto& row : heavy) row.size = 3;
  const qr::ivx::TradedIvTables heavy_tables = run(heavy);
  const qr::ivx::TradedIvTables split_tables = run(split);
  const qr::ivx::SkewCell* a = cell_of(heavy_tables, 0, static_cast<std::int32_t>(kEpochDay));
  const qr::ivx::SkewCell* b = cell_of(split_tables, 0, static_cast<std::int32_t>(kEpochDay));
  ASSERT_NE(a, nullptr);
  ASSERT_NE(b, nullptr);
  EXPECT_NEAR(a->risk_reversal.value, b->risk_reversal.value, 1e-12);
  EXPECT_EQ(a->weight, b->weight);
}

// The band mean must move toward the HEAVIER print, not to the midpoint.
TEST(Weighting, BandMeanIsPulledByTheHeavierPrint) {
  std::vector<qr::sources::OptionPrintRow> rows;
  rows.push_back(print(10, 100.0, 100.0, 0.20, 1, qr::sources::Right::Call));
  rows.push_back(print(10, 100.0, 100.0, 0.30, 3, qr::sources::Right::Call));
  const qr::ivx::TradedIvTables tables = run(rows);
  const qr::ivx::SkewCell* cell = cell_of(tables, 0, static_cast<std::int32_t>(kEpochDay));
  ASSERT_NE(cell, nullptr);
  const std::size_t slot = 4 * qr::ivx::kRights + 0;  // ATM band, CALL
  ASSERT_EQ(cell->band_iv[slot].v, qr::Validity::VALID);
  EXPECT_NEAR(cell->band_iv[slot].value, 0.275, 1e-12);
  EXPECT_EQ(cell->band_weight[slot], 4);
}

// ---------------------------------------------------------------------------
// THE WINDOW LAW.
// ---------------------------------------------------------------------------

// 30-minute windows, right-open on the second: 1799 is window 0 and 1800 is
// window 1. An off-by-one here misdates every innovation in the program.
TEST(WindowLaw, BoundaryIsRightOpenOnTheSecond) {
  std::vector<qr::sources::OptionPrintRow> rows;
  for (const auto& row : smile(true, 1799)) rows.push_back(row);
  for (const auto& row : smile(true, 1800)) rows.push_back(row);
  const qr::ivx::TradedIvTables tables = run(rows);
  EXPECT_NE(cell_of(tables, 0, static_cast<std::int32_t>(kEpochDay)), nullptr);
  EXPECT_NE(cell_of(tables, 1, static_cast<std::int32_t>(kEpochDay)), nullptr);
}

// An innovation is only defined against the IMMEDIATELY preceding window. A
// cell whose expiry skipped a window must not difference across the gap.
TEST(WindowLaw, InnovationsOnlySpanAdjacentWindows) {
  std::vector<qr::sources::OptionPrintRow> rows;
  for (const auto& row : smile(true, 10)) rows.push_back(row);
  for (const auto& row : smile(true, 1810)) rows.push_back(row);
  for (const auto& row : smile(true, 5410)) rows.push_back(row);  // window 3, skipping 2
  const qr::ivx::TradedIvTables tables = run(rows);
  const auto expiry = static_cast<std::int32_t>(kEpochDay);
  ASSERT_NE(cell_of(tables, 1, expiry), nullptr);
  EXPECT_EQ(cell_of(tables, 1, expiry)->d_risk_reversal.v, qr::Validity::VALID);
  ASSERT_NE(cell_of(tables, 3, expiry), nullptr);
  EXPECT_NE(cell_of(tables, 3, expiry)->d_risk_reversal.v, qr::Validity::VALID);
  EXPECT_NE(cell_of(tables, 0, expiry)->d_risk_reversal.v, qr::Validity::VALID);
}

// A print at or after the close second is out of the session, not folded into
// the last window.
TEST(WindowLaw, PrintsPastTheCloseAreRejectedNotClamped) {
  std::vector<qr::sources::OptionPrintRow> rows = smile(true, 23400);
  const qr::ivx::TradedIvTables tables = run(rows);
  EXPECT_EQ(tables.census.admitted, 0);
  EXPECT_EQ(tables.census.rejected_window, static_cast<std::int64_t>(rows.size()));
}

// ---------------------------------------------------------------------------
// THE ADMISSION LAWS (APPENDIX B3).
// ---------------------------------------------------------------------------

// "IV/Greeks need BOTH strict-prior attachments." EQUAL is not prior.
TEST(Admission, QuoteAttachmentMustBeStrictlyPrior) {
  std::vector<qr::sources::OptionPrintRow> rows = smile(true);
  for (auto& row : rows) row.quote_ts_ms_b = row.ts_ms_b;
  const qr::ivx::TradedIvTables tables = run(rows);
  EXPECT_EQ(tables.census.admitted, 0);
  EXPECT_EQ(tables.census.rejected_attachment, static_cast<std::int64_t>(rows.size()));
}

TEST(Admission, UnderlyingStampMustCarryThisSessionsDay) {
  std::vector<qr::sources::OptionPrintRow> rows = smile(true);
  const auto other = qr::sources::inline_text("2022-07-06T09:30:00.000");
  for (auto& row : rows) row.underlying_ts_text = other.value();
  const qr::ivx::TradedIvTables tables = run(rows);
  EXPECT_EQ(tables.census.admitted, 0);
  EXPECT_EQ(tables.census.rejected_attachment, static_cast<std::int64_t>(rows.size()));
}

// A spread's legs print at negotiated prices; their vendor IV is not a quote on
// that strike's volatility, and admitting them would bias the curve.
TEST(Admission, MultiLegPrintsAreExcludedAndCounted) {
  std::vector<qr::sources::OptionPrintRow> rows = smile(true);
  for (auto& row : rows) row.condition = 1;  // outside B3's single-leg set
  const qr::ivx::TradedIvTables tables = run(rows);
  EXPECT_EQ(tables.census.admitted, 0);
  EXPECT_EQ(tables.census.rejected_multi_leg, static_cast<std::int64_t>(rows.size()));
}

TEST(Admission, NonPositiveOrNonFiniteIvIsRejected) {
  std::vector<qr::sources::OptionPrintRow> rows = smile(true);
  rows[0].implied_vol = 0.0;
  rows[1].implied_vol = std::numeric_limits<double>::quiet_NaN();
  const qr::ivx::TradedIvTables tables = run(rows);
  EXPECT_EQ(tables.census.rejected_iv, 2);
}

// ---------------------------------------------------------------------------
// D2 — per-contract IV velocity.
// ---------------------------------------------------------------------------

TEST(IvVelocity, IsThePerSecondChangeOfOneContractsOwnIv) {
  std::vector<qr::sources::OptionPrintRow> rows;
  rows.push_back(print(10, 100.0, 100.0, 0.20, 1, qr::sources::Right::Call));
  rows.push_back(print(20, 100.0, 100.0, 0.21, 1, qr::sources::Right::Call));
  const qr::ivx::TradedIvTables tables = run(rows);
  const qr::ivx::BandWindow& band = tables.bands[0 * qr::ivx::kBands + 4];
  EXPECT_EQ(band.iv_velocity_pairs, 1);
  ASSERT_EQ(band.iv_velocity_signed.v, qr::Validity::VALID);
  EXPECT_NEAR(band.iv_velocity_signed.value, 0.001, 1e-12);
  EXPECT_NEAR(band.iv_velocity_mean_gap_seconds.value, 10.0, 1e-12);
}

// Two prints half an hour apart are two observations, not a speed.
TEST(IvVelocity, PairsBeyondTheAgeGateAreNotAVelocity) {
  std::vector<qr::sources::OptionPrintRow> rows;
  rows.push_back(print(10, 100.0, 100.0, 0.20, 1, qr::sources::Right::Call));
  rows.push_back(print(10 + 1801, 100.0, 100.0, 0.21, 1, qr::sources::Right::Call));
  const qr::ivx::TradedIvTables tables = run(rows);
  std::int64_t pairs = 0;
  for (const qr::ivx::BandWindow& band : tables.bands) pairs += band.iv_velocity_pairs;
  EXPECT_EQ(pairs, 0);
}

// Different CONTRACTS never pair with each other.
TEST(IvVelocity, DoesNotPairAcrossContracts) {
  std::vector<qr::sources::OptionPrintRow> rows;
  rows.push_back(print(10, 100.0, 100.0, 0.20, 1, qr::sources::Right::Call));
  rows.push_back(print(20, 100.0, 100.0, 0.30, 1, qr::sources::Right::Put));
  const qr::ivx::TradedIvTables tables = run(rows);
  std::int64_t pairs = 0;
  for (const qr::ivx::BandWindow& band : tables.bands) pairs += band.iv_velocity_pairs;
  EXPECT_EQ(pairs, 0);
}

// ---------------------------------------------------------------------------
// D5 — the quote-certified sign.
// ---------------------------------------------------------------------------

// A print INSIDE the spread carries no direction this program will assert; it
// must land in `undecidable_size`, never as a zero inside `decided_size`.
TEST(SignedVolDemand, InsideTheSpreadIsUndecidableNotZero) {
  std::vector<qr::sources::OptionPrintRow> rows;
  qr::sources::OptionPrintRow lift = print(10, 100.0, 100.0, 0.2, 7, qr::sources::Right::Call);
  lift.price_u6 = lift.ask_u6;
  qr::sources::OptionPrintRow hit = print(11, 100.0, 100.0, 0.2, 5, qr::sources::Right::Call);
  hit.price_u6 = hit.bid_u6;
  qr::sources::OptionPrintRow inside = print(12, 100.0, 100.0, 0.2, 9, qr::sources::Right::Call);
  inside.price_u6 = 1'000'000;
  rows = {lift, hit, inside};
  const qr::ivx::TradedIvTables tables = run(rows);
  const qr::ivx::BandWindow& band = tables.bands[0 * qr::ivx::kBands + 4];
  EXPECT_EQ(band.signed_size, 2);        // +7 - 5
  EXPECT_EQ(band.decided_size, 12);      // 7 + 5
  EXPECT_EQ(band.undecidable_size, 9);
}

// ---------------------------------------------------------------------------
// B2 — the term structure.
// ---------------------------------------------------------------------------

TEST(TermStructure, RisingTermCarriesAPositiveSlopeAndANearFarRatioBelowOne) {
  std::vector<qr::sources::OptionPrintRow> rows;
  const std::array<std::int32_t, 3> dtes{0, 7, 30};
  const std::array<double, 3> levels{0.20, 0.25, 0.30};
  for (std::size_t index = 0; index < dtes.size(); ++index) {
    for (const double strike : {98.0, 99.0, 100.0, 101.0, 102.0}) {
      const auto right =
          strike <= 100.0 ? qr::sources::Right::Put : qr::sources::Right::Call;
      rows.push_back(print(10, strike, 100.0, levels[index], 50, right, dtes[index]));
      if (strike == 100.0) {
        rows.push_back(print(10, strike, 100.0, levels[index], 50, qr::sources::Right::Call,
                             dtes[index]));
      }
    }
  }
  const qr::ivx::TradedIvTables tables = run(rows);
  const qr::ivx::TermWindow& term = tables.term[0];
  EXPECT_EQ(term.expiries, 3);
  EXPECT_EQ(term.near_dte, 0);
  EXPECT_EQ(term.far_dte, 7);
  EXPECT_FALSE(term.far_is_fallback);
  ASSERT_EQ(term.near_far_ratio.v, qr::Validity::VALID);
  EXPECT_LT(term.near_far_ratio.value, 1.0);
  ASSERT_EQ(term.term_slope.v, qr::Validity::VALID);
  EXPECT_GT(term.term_slope.value, 0.0);
}

// When no expiry reaches a week the far leg is a FALLBACK and says so, rather
// than quietly redefining "far" to mean "the second nearest".
TEST(TermStructure, FarLegFallbackIsFlagged) {
  std::vector<qr::sources::OptionPrintRow> rows;
  for (const std::int32_t dte : {0, 1}) {
    for (const double strike : {98.0, 99.0, 100.0, 101.0, 102.0}) {
      const auto right = strike <= 100.0 ? qr::sources::Right::Put : qr::sources::Right::Call;
      rows.push_back(print(10, strike, 100.0, 0.2 + 0.01 * dte, 50, right, dte));
      if (strike == 100.0) {
        rows.push_back(
            print(10, strike, 100.0, 0.2 + 0.01 * dte, 50, qr::sources::Right::Call, dte));
      }
    }
  }
  const qr::ivx::TradedIvTables tables = run(rows);
  EXPECT_TRUE(tables.term[0].far_is_fallback);
  EXPECT_EQ(tables.term[0].far_dte, 1);
}

// ---------------------------------------------------------------------------
// D7 / D8 / D9 — the surface's own dynamics.
// ---------------------------------------------------------------------------

namespace {

/// A one-window surface series driven by an explicit return path and an
/// explicit PROXY_VOL path.
qr::ivx::SurfaceSeries series_from(const std::vector<double>& returns,
                                   const std::vector<double>& proxy_vol) {
  qr::ivx::SurfaceSeries series;
  series.seconds = static_cast<std::int64_t>(returns.size());
  series.spot_u6.reserve(returns.size());
  const std::size_t cells = returns.size() * qr::ivx::SurfaceSeries::kPlanes;
  series.pv_mid.assign(cells, std::numeric_limits<double>::quiet_NaN());
  series.pv_bid.assign(cells, std::numeric_limits<double>::quiet_NaN());
  series.pv_ask.assign(cells, std::numeric_limits<double>::quiet_NaN());
  double price = 100.0;
  for (std::size_t index = 0; index < returns.size(); ++index) {
    price *= std::exp(returns[index]);
    series.spot_u6.push_back(static_cast<std::int64_t>(std::llround(price * 1e6)));
    const std::size_t slot = index * qr::ivx::SurfaceSeries::kPlanes;
    series.pv_mid[slot] = proxy_vol[index];
    series.pv_bid[slot] = proxy_vol[index] * 0.98;
    series.pv_ask[slot] = proxy_vol[index] * 1.02;
  }
  return series;
}

}  // namespace

// D8: chi is the REGRESSION COEFFICIENT of the PROXY_VOL innovation on the
// absolute spot return. Construct a surface that responds with a known gain and
// the fit must recover it.
TEST(SurfaceDynamics, ResponseRecoversTheConstructedGain) {
  const double gain = 3.0;
  std::vector<double> returns(1800, 0.0);
  std::vector<double> proxy_vol(1800, 0.0);
  double level = 0.20;
  proxy_vol[0] = level;
  for (std::size_t index = 1; index < returns.size(); ++index) {
    returns[index] = (index % 2 == 0 ? 1.0 : -1.0) * 1e-4 * static_cast<double>(index % 7 + 1);
    level *= std::exp(gain * std::abs(returns[index]));
    proxy_vol[index] = level;
  }
  const qr::ivx::SurfaceDynamics dynamics = qr::ivx::surface_dynamics(series_from(returns, proxy_vol), 0);
  ASSERT_EQ(dynamics.window[0].fd_chi.v, qr::Validity::VALID);
  EXPECT_NEAR(dynamics.window[0].fd_chi.value, gain, 1e-4);
}

// A surface that never moves has zero fluctuation, so the FD ratio is a
// DIVISION BY ZERO and must be typed absent — never an infinity in a TSV.
TEST(SurfaceDynamics, ZeroFluctuationTypesTheRatioAbsent) {
  std::vector<double> returns(1800, 0.0);
  std::vector<double> proxy_vol(1800, 0.20);
  for (std::size_t index = 1; index < returns.size(); ++index) {
    returns[index] = (index % 2 == 0 ? 1.0 : -1.0) * 1e-4;
  }
  const qr::ivx::SurfaceDynamics dynamics =
      qr::ivx::surface_dynamics(series_from(returns, proxy_vol), 0);
  EXPECT_NE(dynamics.window[0].fd_ratio.v, qr::Validity::VALID);
  ASSERT_EQ(dynamics.window[0].fd_sigma_vv.v, qr::Validity::VALID);
  EXPECT_NEAR(dynamics.window[0].fd_sigma_vv.value, 0.0, 1e-15);
}

// D8, the INNOVATION. `d_fd_ratio` is the window-to-window change of the ratio,
// under the same law every other `d_` channel in this module obeys: absent in
// window 0, absent when either side is absent, and never a zero standing in for
// "no change". Two windows with DIFFERENT constructed gains must therefore
// carry their exact difference in window 1 and nothing at all in window 0.
TEST(SurfaceDynamics, FdRatioInnovationIsTheWindowToWindowChange) {
  const std::size_t window_seconds = static_cast<std::size_t>(qr::ivx::kWindowSeconds);
  std::vector<double> returns(2 * window_seconds, 0.0);
  std::vector<double> proxy_vol(2 * window_seconds, 0.0);
  double level = 0.20;
  proxy_vol[0] = level;
  for (std::size_t index = 1; index < returns.size(); ++index) {
    const double gain = index < window_seconds ? 3.0 : 7.0;
    returns[index] = (index % 2 == 0 ? 1.0 : -1.0) * 1e-4 * static_cast<double>(index % 7 + 1);
    level *= std::exp(gain * std::abs(returns[index]) + 1e-6 * static_cast<double>(index % 5));
    proxy_vol[index] = level;
  }
  const qr::ivx::SurfaceDynamics dynamics =
      qr::ivx::surface_dynamics(series_from(returns, proxy_vol), 0);
  ASSERT_EQ(dynamics.window[0].fd_ratio.v, qr::Validity::VALID);
  ASSERT_EQ(dynamics.window[1].fd_ratio.v, qr::Validity::VALID);
  EXPECT_NE(dynamics.window[0].d_fd_ratio.v, qr::Validity::VALID);
  ASSERT_EQ(dynamics.window[1].d_fd_ratio.v, qr::Validity::VALID);
  EXPECT_NEAR(dynamics.window[1].d_fd_ratio.value,
              dynamics.window[1].fd_ratio.value - dynamics.window[0].fd_ratio.value, 1e-12);
  // Window 2 saw no surface at all, so its innovation is absent rather than a
  // change measured against nothing.
  EXPECT_NE(dynamics.window[2].d_fd_ratio.v, qr::Validity::VALID);
}

// D9: A3 is a TIME-ASYMMETRY statistic. Reversing the return sequence must flip
// its sign; a statistic that survives reversal unchanged is not measuring
// irreversibility at all.
TEST(SurfaceDynamics, A3FlipsSignUnderTimeReversal) {
  // A saw-tooth: many small rises, occasional large drops — irreversible by
  // construction. Index 0 is the seed price and carries no grid return, so the
  // reversal is applied to indices 1..N-1 only, which makes the two dense
  // return series EXACT reverses of one another.
  // A period-3 cycle (+1,+2,-3): zero mean, but the forward triple product and
  // the backward one differ, which is exactly what A3 is built to see. (The
  // obvious "many small rises, one big drop" saw-tooth is A3-NEUTRAL — its two
  // triple products are equal — which is itself worth knowing.)
  std::vector<double> returns(1800, 0.0);
  const std::array<double, 3> cycle{1e-3, 2e-3, -3e-3};
  for (std::size_t index = 1; index < returns.size(); ++index) {
    returns[index] = cycle[index % 3];
  }
  const std::vector<double> proxy_vol(1800, 0.20);
  std::vector<double> reversed(1800, 0.0);
  for (std::size_t index = 1; index < returns.size(); ++index) {
    reversed[index] = returns[returns.size() - index];
  }
  const qr::ivx::SurfaceDynamics forward =
      qr::ivx::surface_dynamics(series_from(returns, proxy_vol), 0);
  const qr::ivx::SurfaceDynamics backward =
      qr::ivx::surface_dynamics(series_from(reversed, proxy_vol), 0);
  ASSERT_EQ(forward.window[0].a3_return.v, qr::Validity::VALID);
  ASSERT_EQ(backward.window[0].a3_return.v, qr::Validity::VALID);
  EXPECT_GT(std::abs(forward.window[0].a3_return.value), 1e-3);
  EXPECT_NEAR(forward.window[0].a3_return.value, -backward.window[0].a3_return.value, 1e-3);
}

// D7: vol-of-vol is the realized variance of the PROXY_VOL log-innovations. A
// constant surface has exactly zero.
TEST(SurfaceDynamics, VolOfVolIsZeroForAConstantSurface) {
  const std::vector<double> returns(1800, 1e-5);
  const std::vector<double> proxy_vol(1800, 0.20);
  const qr::ivx::SurfaceDynamics dynamics =
      qr::ivx::surface_dynamics(series_from(returns, proxy_vol), 0);
  ASSERT_EQ(dynamics.window[0].vol_of_vol_mid.v, qr::Validity::VALID);
  EXPECT_NEAR(dynamics.window[0].vol_of_vol_mid.value, 0.0, 1e-24);
}

// A window with no support carries NO number: every D8/D9 channel is typed
// absent rather than computed from three points.
TEST(SurfaceDynamics, ThinWindowsAreTypedAbsent) {
  const std::vector<double> returns(20, 1e-4);
  const std::vector<double> proxy_vol(20, 0.20);
  const qr::ivx::SurfaceDynamics dynamics =
      qr::ivx::surface_dynamics(series_from(returns, proxy_vol), 0);
  EXPECT_NE(dynamics.window[0].fd_chi.v, qr::Validity::VALID);
  EXPECT_NE(dynamics.window[0].a3_return.v, qr::Validity::VALID);
  EXPECT_NE(dynamics.window[0].vol_of_vol_mid.v, qr::Validity::VALID);
}

// ---------------------------------------------------------------------------
// TWO-RUN IDENTITY.
// ---------------------------------------------------------------------------

// The whole point of a census: the same bytes in, the same bytes out. Any
// unordered container or wall-clock value in the path breaks this.
TEST(Determinism, TwoRunsOfTheSameInputEmitTheSameRows) {
  const std::vector<qr::sources::OptionPrintRow> rows = smile(true);
  qr::ivx::Report first;
  qr::ivx::Report second;
  emit(first, run(rows));
  emit(second, run(rows));
  ASSERT_EQ(first.rows().size(), second.rows().size());
  for (std::size_t index = 0; index < first.rows().size(); ++index) {
    EXPECT_EQ(first.rows()[index].scope, second.rows()[index].scope);
    EXPECT_EQ(first.rows()[index].key, second.rows()[index].key);
    EXPECT_EQ(first.rows()[index].metric, second.rows()[index].metric);
    EXPECT_EQ(first.rows()[index].value, second.rows()[index].value);
  }
}
