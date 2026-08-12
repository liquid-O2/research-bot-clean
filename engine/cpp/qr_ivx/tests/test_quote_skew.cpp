// RED-FIRST FIXTURES for the model-free quote-skew proxy
// (qr_ivx/quote_skew.hpp).
//
// The proxy exists precisely because the firewall forbids inverting a model, so
// the cases that matter are the ones that keep it HONEST: strict priority, the
// age gate, the two-sided requirement, the ATM tie rule, and the orientation.
#include <gtest/gtest.h>

#include <cmath>
#include <cstdint>
#include <array>
#include <limits>
#include <vector>

#include "qr_ivx/quote_skew.hpp"
#include "qr_w21/surface.hpp"

namespace {

constexpr std::int64_t kOpenMs = 1'667'309'400'000;
constexpr std::int64_t kEpochDay = kOpenMs / 86'400'000;
constexpr std::int64_t kSpotU6 = 100'000'000;  // $100.00

std::vector<std::int64_t> flat_grid(std::int64_t spot_u6 = kSpotU6) {
  return std::vector<std::int64_t>(23401, spot_u6);
}

qr::sources::OptionQuoteRow quote(std::int64_t second_ms_offset, double strike,
                                  qr::sources::Right right, std::int64_t bid_u6,
                                  std::int64_t ask_u6, std::int32_t dte = 0) {
  qr::sources::OptionQuoteRow row;
  row.ts_ms_b = kOpenMs + second_ms_offset;
  row.strike_u6 = static_cast<std::int64_t>(std::llround(strike * 1e6));
  row.bid_u6 = bid_u6;
  row.ask_u6 = ask_u6;
  row.bid_size = 10;
  row.ask_size = 10;
  row.expiration_day = static_cast<std::int32_t>(kEpochDay) + dte;
  row.right = right;
  row.null_mask = 0;
  return row;
}

/// A five-rung ladder at 98..102 whose OTM PUT mids sit above the matching OTM
/// CALL mids (put-rich), or below (call-rich).
std::vector<qr::sources::OptionQuoteRow> ladder(bool put_rich, std::int64_t at_ms = 0) {
  std::vector<qr::sources::OptionQuoteRow> rows;
  const std::array<double, 5> strikes{98.0, 99.0, 100.0, 101.0, 102.0};
  for (std::size_t index = 0; index < strikes.size(); ++index) {
    const auto rung = static_cast<double>(index);
    // Distance from the middle rung, in rungs.
    const double distance = std::abs(rung - 2.0);
    const double base = 1'000'000.0 - 200'000.0 * distance;
    const double tilt = put_rich ? 120'000.0 * distance : -120'000.0 * distance;
    const auto put_mid = static_cast<std::int64_t>(base + tilt / 2.0);
    const auto call_mid = static_cast<std::int64_t>(base - tilt / 2.0);
    rows.push_back(quote(at_ms, strikes[index], qr::sources::Right::Put, put_mid - 10'000,
                         put_mid + 10'000));
    rows.push_back(quote(at_ms, strikes[index], qr::sources::Right::Call, call_mid - 10'000,
                         call_mid + 10'000));
  }
  return rows;
}

qr::ivx::QuoteSkewSecond evaluate(const std::vector<qr::sources::OptionQuoteRow>& rows,
                                  const std::vector<std::int64_t>& grid, std::int64_t second) {
  qr::ivx::QuoteSkewBuilder builder(kOpenMs, kEpochDay, 0, &grid, second, second);
  for (const auto& row : rows) builder.observe(row);
  builder.finish();
  for (const qr::ivx::QuoteSkewSecond& one : builder.seconds()) {
    if (one.second == second) return one;
  }
  return qr::ivx::QuoteSkewSecond{};
}

}  // namespace

// ORIENTATION: positive when the OTM put is richer than the matching OTM call —
// the same sign convention as the traded-side `risk_reversal`, so the two can be
// read side by side without a mental flip.
TEST(QuoteSkewOrientation, PutRichLadderIsPositive) {
  const auto grid = flat_grid();
  const qr::ivx::QuoteSkewSecond one = evaluate(ladder(/*put_rich=*/true), grid, 5);
  ASSERT_EQ(one.state, qr::Validity::VALID);
  EXPECT_EQ(one.atm_strike_u6, 100'000'000);
  ASSERT_EQ(one.tilt[1].v, qr::Validity::VALID);
  EXPECT_GT(one.tilt[1].value, 0.0);
  ASSERT_EQ(one.log_ratio[1].v, qr::Validity::VALID);
  EXPECT_GT(one.log_ratio[1].value, 0.0);
  ASSERT_EQ(one.tilt[2].v, qr::Validity::VALID);
  EXPECT_GT(one.tilt[2].value, one.tilt[1].value);  // the tilt widens outward
}

TEST(QuoteSkewOrientation, CallRichLadderIsNegative) {
  const auto grid = flat_grid();
  const qr::ivx::QuoteSkewSecond one = evaluate(ladder(/*put_rich=*/false), grid, 5);
  ASSERT_EQ(one.state, qr::Validity::VALID);
  ASSERT_EQ(one.tilt[1].v, qr::Validity::VALID);
  EXPECT_LT(one.tilt[1].value, 0.0);
}

// The NORMALIZER is the ATM straddle mid, not a strike or a spot. Doubling
// every quoted premium must leave the tilt unchanged and the log-ratio too.
TEST(QuoteSkewNormalization, ScalingEveryPremiumLeavesTheProxyUnchanged) {
  const auto grid = flat_grid();
  std::vector<qr::sources::OptionQuoteRow> doubled = ladder(true);
  for (auto& row : doubled) {
    row.bid_u6 *= 2;
    row.ask_u6 *= 2;
  }
  const qr::ivx::QuoteSkewSecond base = evaluate(ladder(true), grid, 5);
  const qr::ivx::QuoteSkewSecond scaled = evaluate(doubled, grid, 5);
  ASSERT_EQ(base.tilt[1].v, qr::Validity::VALID);
  ASSERT_EQ(scaled.tilt[1].v, qr::Validity::VALID);
  EXPECT_NEAR(base.tilt[1].value, scaled.tilt[1].value, 1e-9);
  EXPECT_NEAR(base.log_ratio[1].value, scaled.log_ratio[1].value, 1e-9);
}

// STRICT PRIORITY. A quote stamped exactly ON a grid second's boundary is NOT
// state for that second. Without this the proxy reads the future by one tick.
TEST(QuoteSkewCausality, QuoteAtTheBoundaryIsNotStateForThatSecond) {
  const auto grid = flat_grid();
  std::vector<qr::sources::OptionQuoteRow> rows = ladder(true, /*at_ms=*/5000);
  // A LATER ROW IS PART OF THE FIXTURE, not decoration. Without it second 5 is
  // closed out by the arrival of the boundary rows themselves — before any of
  // them is folded — so the case would pass on the evaluation ORDER alone and
  // would never exercise the strict-priority comparison it exists to pin. The
  // trailing quote forces second 5 to be valued with the boundary rows already
  // in the ladder, which is exactly the situation `usable` must refuse.
  const std::vector<qr::sources::OptionQuoteRow> later = ladder(true, /*at_ms=*/9000);
  rows.insert(rows.end(), later.begin(), later.end());
  const qr::ivx::QuoteSkewSecond at = evaluate(rows, grid, 5);
  EXPECT_NE(at.state, qr::Validity::VALID);
  const qr::ivx::QuoteSkewSecond after = evaluate(rows, grid, 6);
  EXPECT_EQ(after.state, qr::Validity::VALID);
}

// THE AGE GATE is the W2.1 one, inherited rather than re-invented: a quote more
// than 300s stale is not a live market.
TEST(QuoteSkewCausality, StaleQuotesLeaveTheLadderEmpty) {
  const auto grid = flat_grid();
  const std::vector<qr::sources::OptionQuoteRow> rows = ladder(true, /*at_ms=*/0);
  const std::int64_t gate_seconds = qr::w21::kContractAgeGateMs / 1000;
  EXPECT_EQ(evaluate(rows, grid, gate_seconds).state, qr::Validity::VALID);
  const qr::ivx::QuoteSkewSecond past = evaluate(rows, grid, gate_seconds + 1);
  EXPECT_NE(past.state, qr::Validity::VALID);
  EXPECT_EQ(past.ladder_rungs, 0);
}

// A rung is only a rung when BOTH rights are two-sided there — the straddle and
// the offsets are meaningless otherwise.
TEST(QuoteSkewLadder, OneSidedRungsAreNotRungs) {
  const auto grid = flat_grid();
  std::vector<qr::sources::OptionQuoteRow> rows = ladder(true);
  for (auto& row : rows) {
    if (row.strike_u6 == 99'000'000 && row.right == qr::sources::Right::Put) {
      row.bid_u6 = 0;  // one-sided: no bid
    }
  }
  const qr::ivx::QuoteSkewSecond one = evaluate(rows, grid, 5);
  ASSERT_EQ(one.state, qr::Validity::VALID);
  EXPECT_EQ(one.ladder_rungs, 4);
  // With 99 gone the ladder is {98,100,101,102}; the ATM rung is at index 1, so
  // the +-2 offset walks off the low end and must be ABSENT, not clamped to 98.
  EXPECT_EQ(one.tilt[2].v, qr::Validity::MISSING);
  EXPECT_EQ(one.tilt[1].v, qr::Validity::VALID);
}

// A CROSSED quote is not a market. It must leave the rung out rather than
// produce a negative mid.
TEST(QuoteSkewLadder, CrossedQuotesAreNotRungs) {
  const auto grid = flat_grid();
  std::vector<qr::sources::OptionQuoteRow> rows = ladder(true);
  for (auto& row : rows) {
    if (row.strike_u6 == 100'000'000 && row.right == qr::sources::Right::Call) {
      const std::int64_t bid = row.bid_u6;
      row.bid_u6 = row.ask_u6;
      row.ask_u6 = bid;  // crossed
    }
  }
  const qr::ivx::QuoteSkewSecond one = evaluate(rows, grid, 5);
  EXPECT_NE(one.atm_strike_u6, 100'000'000);
}

// Q5's ratified tie reading: EQUIDISTANT ATM candidates are TYPED UNDECIDABLE.
// Breaking the tie by strike order would make the channel depend on an
// arbitrary identifier.
TEST(QuoteSkewAtm, EquidistantCandidatesAreUndecidable) {
  // Find the upper strike whose rounded ln-moneyness is the exact mirror of the
  // lower one's, so the tie is real rather than approximate.
  const std::int64_t lower = 99'000'000;
  const auto low_bps = qr::w21::moneyness_log_bps(lower, kSpotU6);
  ASSERT_TRUE(low_bps.has_value());
  const std::int64_t target = -low_bps.value();
  std::int64_t found = 0;
  for (std::int64_t upper = 100'000'000; upper <= 102'000'000; upper += 100) {
    const auto bps = qr::w21::moneyness_log_bps(upper, kSpotU6);
    if (bps.has_value() && bps.value() == target) {
      found = upper;
      break;
    }
  }
  ASSERT_GT(found, 0);
  std::vector<qr::sources::OptionQuoteRow> rows;
  for (const std::int64_t strike : {lower, found}) {
    const double dollars = static_cast<double>(strike) / 1e6;
    rows.push_back(quote(0, dollars, qr::sources::Right::Put, 900'000, 1'100'000));
    rows.push_back(quote(0, dollars, qr::sources::Right::Call, 900'000, 1'100'000));
  }
  const auto grid = flat_grid();
  EXPECT_EQ(evaluate(rows, grid, 5).state, qr::Validity::EQUAL_TIME_UNORDERED);
}

// The DTE plane is a filter, not a suggestion: a builder pinned to plane 0 must
// see nothing on a one-day expiry.
TEST(QuoteSkewPlane, OtherExpiriesAreNotOnThePlane) {
  const auto grid = flat_grid();
  std::vector<qr::sources::OptionQuoteRow> rows = ladder(true);
  for (auto& row : rows) row.expiration_day += 1;
  qr::ivx::QuoteSkewBuilder builder(kOpenMs, kEpochDay, 0, &grid, 0, 10);
  for (const auto& row : rows) builder.observe(row);
  builder.finish();
  EXPECT_EQ(builder.rows_observed(), static_cast<std::int64_t>(rows.size()));
  EXPECT_EQ(builder.rows_on_plane(), 0);
}

// An absent grid spot is a TYPED absence, never a substituted spot.
TEST(QuoteSkewPlane, MissingGridSpotTypesTheSecondAbsent) {
  std::vector<std::int64_t> grid = flat_grid();
  grid[5] = 0;
  EXPECT_EQ(evaluate(ladder(true), grid, 5).state, qr::Validity::MISSING);
}

// Two runs of the same input produce the same window aggregates.
TEST(QuoteSkewDeterminism, TwoRunsAgree) {
  const auto grid = flat_grid();
  const std::vector<qr::sources::OptionQuoteRow> rows = ladder(true);
  qr::ivx::Report first;
  qr::ivx::Report second;
  {
    qr::ivx::QuoteSkewBuilder builder(kOpenMs, kEpochDay, 0, &grid, 0, 20);
    for (const auto& row : rows) builder.observe(row);
    builder.finish();
    emit(first, "s209/p0", builder, true);
  }
  {
    qr::ivx::QuoteSkewBuilder builder(kOpenMs, kEpochDay, 0, &grid, 0, 20);
    for (const auto& row : rows) builder.observe(row);
    builder.finish();
    emit(second, "s209/p0", builder, true);
  }
  ASSERT_EQ(first.rows().size(), second.rows().size());
  for (std::size_t index = 0; index < first.rows().size(); ++index) {
    EXPECT_EQ(first.rows()[index].value, second.rows()[index].value);
  }
}
