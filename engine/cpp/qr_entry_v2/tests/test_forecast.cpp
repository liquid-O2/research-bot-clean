#include <gtest/gtest.h>

#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <string>

#include "qr_entry_v2/forecast.hpp"
#include "qr_futsess/calendar.hpp"

namespace {

using qr::entry_v2::DayPriors;
using qr::entry_v2::EventPack;
using qr::entry_v2::EventRow;
using qr::entry_v2::ForecastArtifact;
using qr::entry_v2::ForecastLadderSource;
using qr::entry_v2::ForecastMissingReason;
using qr::entry_v2::ForecastModelState;
using qr::entry_v2::ForecastRow;
using qr::entry_v2::ForecastSegment;
using qr::entry_v2::ForecastStatus;
using qr::entry_v2::LockRow;
using qr::entry_v2::LockStatus;
using qr::entry_v2::PhaseRow;
using qr::entry_v2::RealizedVolSegment;
using qr::futsess::Asset;

constexpr std::uint64_t kNs = 1'000'000'000ULL;
constexpr std::int64_t kDay0 = 1'704'067'200;  // 2024-01-01 00:00:00Z
constexpr std::int64_t kSiTickRaw = 5'000'000;

EventRow bbo(std::uint64_t ts_recv_ns, std::int64_t mid2,
             std::uint32_t sequence, std::uint64_t ts_event_ns = 0,
             std::uint8_t flags = 0) {
  EventRow row{};
  row.ts_recv_ns = ts_recv_ns;
  row.ts_event_ns = ts_event_ns == 0u ? ts_recv_ns : ts_event_ns;
  row.bid_px = (mid2 - kSiTickRaw) / 2;
  row.ask_px = (mid2 + kSiTickRaw) / 2;
  row.price = row.ask_px;
  row.bid_sz = row.ask_sz = 10;
  row.bid_ct = row.ask_ct = 1;
  row.sequence = sequence;
  row.receive_session_sec = static_cast<std::int32_t>(ts_recv_ns / kNs - kDay0);
  row.flags = flags;
  return row;
}

PhaseRow phases() {
  PhaseRow row;
  row.month = 202401;
  row.boundaries = {3600, 7200, 0};
  row.profile_sha256 = std::string(64, 'a');
  return row;
}

LockRow lock() {
  LockRow row;
  row.d8 = 20240101;
  row.status = LockStatus::LOCKED;
  row.locked_iid = 17;
  row.selection_basis_d8 = 20231229;
  row.open_utc = kDay0;
  row.close_utc = kDay0 + 900;
  return row;
}

DayPriors sane_priors() {
  DayPriors priors;
  priors.d8 = 20240101;
  for (auto& phase : priors.phase) {
    phase.sane_ceiling_usd = 500.0;
  }
  return priors;
}

EventPack simple_pack() {
  EventPack pack;
  std::memcpy(pack.header.magic, "QRE2EVT2", 8);
  pack.header.version = 2;
  pack.header.asset_idx = static_cast<std::uint8_t>(Asset::SI);
  pack.header.d8 = 20240101;
  pack.header.locked_iid = 17;
  pack.header.open_utc = kDay0;
  pack.header.close_utc = kDay0 + 900;
  pack.header.row_bytes = qr::entry_v2::kEventRowBytes;
  const std::uint64_t base_ts = static_cast<std::uint64_t>(kDay0) * kNs;
  constexpr std::int64_t base_mid2 = 50'000'000'000LL;
  pack.rows = {bbo(base_ts, base_mid2, 1),
               bbo(base_ts + 300u * kNs, base_mid2 + 20'000'000LL, 2),
               bbo(base_ts + 600u * kNs, base_mid2 - 20'000'000LL, 3)};
  // Exchange timestamps descend; receive order and forecast grid do not.
  pack.rows[0].ts_event_ns = base_ts + 900u;
  pack.rows[1].ts_event_ns = base_ts + 800u;
  pack.rows[2].ts_event_ns = base_ts + 700u;
  pack.header.n_events = pack.rows.size();
  return pack;
}

std::int32_t date_at(std::int64_t start_day, int offset) {
  return qr::futsess::day_to_date(start_day + offset).yyyymmdd();
}

std::array<RealizedVolSegment, qr::entry_v2::kForecastSegmentCount>
synthetic_realized(int index, double mutation = 0.0) {
  std::array<RealizedVolSegment, qr::entry_v2::kForecastSegmentCount> out{};
  for (std::size_t s = 0; s < out.size(); ++s) {
    const double si = static_cast<double>(s);
    const double ii = static_cast<double>(index);
    const double rv = std::exp(
        7.8 + 0.27 * std::sin(0.73 * ii + 0.31 * si) +
        0.19 * std::cos(0.017 * ii * ii + 0.47 * si) +
        0.04 * std::sin(0.113 * ii * ii + 0.2 * si));
    RealizedVolSegment& row = out[s];
    row.segment = static_cast<ForecastSegment>(s);
    row.valid = true;
    row.range_usd = std::exp(
        5.4 + 0.23 * std::sin(0.29 * ii + 0.41 * si) +
        0.13 * std::cos(0.023 * ii * ii + 0.37 * si)) + mutation;
    row.rv_usd = rv + mutation * mutation;
    row.bv_usd = 0.71 * row.rv_usd;
    row.jump_usd = std::exp(3.1 + 0.21 * std::sin(0.43 * ii + 0.61 * si));
    row.sigma_usd = std::sqrt(row.rv_usd);
    row.parkinson_usd = std::exp(
        3.7 + 0.16 * std::sin(0.19 * ii + 0.17 * si));
    row.gk_usd = std::exp(
        3.6 + 0.14 * std::cos(0.31 * ii + 0.29 * si));
    row.rs_usd = std::exp(
        3.5 + 0.12 * std::sin(0.037 * ii * ii + 0.23 * si));
  }
  return out;
}

void expect_same_frozen_row(const ForecastRow& lhs, const ForecastRow& rhs) {
  EXPECT_EQ(lhs.d8, rhs.d8);
  EXPECT_EQ(lhs.segment, rhs.segment);
  EXPECT_EQ(lhs.status, rhs.status);
  EXPECT_EQ(lhs.missing_reason, rhs.missing_reason);
  EXPECT_EQ(lhs.history_end_d8, rhs.history_end_d8);
  EXPECT_EQ(lhs.availability_ts_ns, rhs.availability_ts_ns);
  EXPECT_EQ(lhs.model_sha256, rhs.model_sha256);
  EXPECT_EQ(lhs.history_source_sha256, rhs.history_source_sha256);
  EXPECT_EQ(lhs.lineage_sha256, rhs.lineage_sha256);
}

}  // namespace

TEST(Qre2ForecastRealized, UsesSanePreviousTickFiveMinuteDollarReturns) {
  auto realized = qr::entry_v2::realize_forecast_session(
      Asset::SI, lock(), phases(), simple_pack(), sane_priors(), 0);
  ASSERT_TRUE(realized.has_value()) << realized.error().message();
  const RealizedVolSegment& session = realized.value().segment[0];
  const RealizedVolSegment& tokyo = realized.value().segment[1];
  EXPECT_TRUE(session.valid);
  EXPECT_EQ(session.sane_events, 3u);
  EXPECT_EQ(session.grid_samples, 3u);
  EXPECT_DOUBLE_EQ(session.open_px, 25.0);
  EXPECT_DOUBLE_EQ(session.high_px, 25.01);
  EXPECT_DOUBLE_EQ(session.low_px, 24.99);
  EXPECT_DOUBLE_EQ(session.close_px, 24.99);
  EXPECT_NEAR(session.range_usd, 100.0, 1e-10);
  EXPECT_NEAR(session.rv_usd, 12'500.0, 1e-9);
  EXPECT_NEAR(session.bv_usd, std::acos(-1.0) * 2'500.0, 1e-9);
  EXPECT_NEAR(session.jump_usd, 12'500.0 - std::acos(-1.0) * 2'500.0,
              1e-9);
  EXPECT_NEAR(session.sigma_usd, std::sqrt(12'500.0), 1e-12);
  EXPECT_TRUE(tokyo.valid);
  EXPECT_DOUBLE_EQ(tokyo.rv_usd, session.rv_usd);
  EXPECT_FALSE(realized.value().segment[2].valid);
  EXPECT_FALSE(realized.value().segment[3].valid);
}

TEST(Qre2ForecastRealized, SnapshotAtomicallyDiscardsPreSnapshotDerivedHistory) {
  EventPack pack = simple_pack();
  const std::uint64_t base = static_cast<std::uint64_t>(kDay0) * kNs;
  constexpr std::int64_t mid = 50'000'000'000LL;
  pack.rows = {
      bbo(base, mid, 1),
      bbo(base + 300u * kNs, mid + 20'000'000LL, 2),
      bbo(base + 400u * kNs, mid + 2'000'000'000LL, 3, 0, 0x28u),
      bbo(base + 401u * kNs, mid - 2'000'000'000LL, 4),
      bbo(base + 500u * kNs, mid, 5),
      bbo(base + 800u * kNs, mid + 20'000'000LL, 6),
  };
  pack.header.n_events = pack.rows.size();
  auto realized = qr::entry_v2::realize_forecast_session(
      Asset::SI, lock(), phases(), pack, sane_priors(), 0);
  ASSERT_TRUE(realized.has_value()) << realized.error().message();
  const RealizedVolSegment& session = realized.value().segment[0];
  EXPECT_EQ(session.sane_events, 2u);
  EXPECT_EQ(session.grid_samples, 2u);
  EXPECT_DOUBLE_EQ(session.open_px, 25.0);
  EXPECT_DOUBLE_EQ(session.high_px, 25.01);
  EXPECT_DOUBLE_EQ(session.low_px, 25.0);
  EXPECT_DOUBLE_EQ(session.close_px, 25.01);
  EXPECT_NEAR(session.rv_usd, 2'500.0, 1e-9);
  EXPECT_DOUBLE_EQ(session.bv_usd, 0.0);

  EventPack tainted = simple_pack();
  tainted.rows[1].flags = 0x04u;
  auto no_suffix = qr::entry_v2::realize_forecast_session(
      Asset::SI, lock(), phases(), tainted, sane_priors(), 0);
  ASSERT_TRUE(no_suffix.has_value()) << no_suffix.error().message();
  EXPECT_EQ(no_suffix.value().segment[0].sane_events, 0u);
  EXPECT_FALSE(no_suffix.value().segment[0].valid);
}

TEST(Qre2ForecastRealized, V1EventPackCannotEnterTheV2ForecastLaw) {
  EventPack stale = simple_pack();
  std::memcpy(stale.header.magic, "QRE2EVT1", 8);
  stale.header.version = 1u;
  auto refused = qr::entry_v2::realize_forecast_session(
      Asset::SI, lock(), phases(), stale, sane_priors(), 0);
  EXPECT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}

TEST(Qre2ForecastCausality, SnapshotMustPrecedeCommitAndStartsTypedMissing) {
  ForecastModelState state(Asset::SI);
  const std::string phase_hash(64, 'a');
  auto first = state.snapshot(20210101, 1'609'459'200, phase_hash);
  ASSERT_TRUE(first.has_value()) << first.error().message();
  for (const ForecastRow& row : first.value()) {
    EXPECT_EQ(row.status, ForecastStatus::MISSING);
    EXPECT_EQ(row.missing_reason, ForecastMissingReason::DESIGN_HISTORY);
    EXPECT_EQ(row.history_end_d8, -1);
    EXPECT_EQ(row.availability_ts_ns, 1'609'459'200ULL * kNs);
    EXPECT_EQ(row.lineage_sha256.size(), 64u);
  }
  auto illegal_second = state.snapshot(20210102, 1'609'545'600, phase_hash);
  EXPECT_FALSE(illegal_second.has_value());
  ASSERT_TRUE(state.commit(20210101, synthetic_realized(0),
                           std::string(64, 'b')).has_value());
  auto second = state.snapshot(20210102, 1'609'545'600, phase_hash);
  ASSERT_TRUE(second.has_value()) << second.error().message();
  EXPECT_EQ(second.value()[0].history_end_d8, 20210101);
}

TEST(Qre2ForecastCausality, SameDayAndSuffixMutationCannotChangeFrozenRows) {
  ASSERT_TRUE(qr::futsess::init_globex_timezone().has_value());
  ForecastModelState left(Asset::SI);
  ForecastModelState right(Asset::SI);
  const std::string phase_hash(64, 'c');
  const std::int64_t start = qr::futsess::date_to_day({2021, 1, 1});
  for (int i = 0; i < 89; ++i) {
    const std::int32_t d8 = date_at(start, i);
    const std::int64_t open = 1'609'459'200 + static_cast<std::int64_t>(i) * 86'400;
    auto a = left.snapshot(d8, open, phase_hash);
    auto b = right.snapshot(d8, open, phase_hash);
    ASSERT_TRUE(a.has_value()) << a.error().message();
    ASSERT_TRUE(b.has_value()) << b.error().message();
    for (std::size_t s = 0; s < a.value().size(); ++s) {
      expect_same_frozen_row(a.value()[s], b.value()[s]);
    }
    const auto original = synthetic_realized(i);
    ASSERT_TRUE(left.commit(d8, original, std::string(64, 'd')).has_value());
    ASSERT_TRUE(right.commit(d8, original, std::string(64, 'd')).has_value());
  }

  const int i = 89;
  const std::int32_t d8 = date_at(start, i);
  const std::int64_t open = 1'609'459'200 + static_cast<std::int64_t>(i) * 86'400;
  auto a = left.snapshot(d8, open, phase_hash);
  auto b = right.snapshot(d8, open, phase_hash);
  ASSERT_TRUE(a.has_value()) << a.error().message();
  ASSERT_TRUE(b.has_value()) << b.error().message();
  for (std::size_t s = 0; s < a.value().size(); ++s) {
    expect_same_frozen_row(a.value()[s], b.value()[s]);
  }
  const auto frozen = a.value();
  ASSERT_TRUE(left.commit(d8, synthetic_realized(i),
                          std::string(64, 'd')).has_value());
  ASSERT_TRUE(right.commit(d8, synthetic_realized(i, 50'000.0),
                           std::string(64, 'e')).has_value());
  // Current-session outcome bytes and their source hash enter after this
  // session's rows were returned; mutating the suffix cannot rewrite them.
  for (std::size_t s = 0; s < frozen.size(); ++s) {
    EXPECT_EQ(frozen[s].lineage_sha256, a.value()[s].lineage_sha256);
    EXPECT_EQ(frozen[s].lineage_sha256, b.value()[s].lineage_sha256);
  }
}

TEST(Qre2ForecastModel, MonthlyFullRankWarmupAndCausalLadderBecomeReady) {
  ASSERT_TRUE(qr::futsess::init_globex_timezone().has_value());
  ForecastModelState state(Asset::SI);
  const std::string phase_hash(64, 'f');
  const std::string source_hash(64, '1');
  const std::int64_t start = qr::futsess::date_to_day({2021, 1, 1});
  std::array<ForecastRow, qr::entry_v2::kForecastSegmentCount> final{};
  bool saw_ready = false;
  for (int i = 0; i < 460; ++i) {
    const std::int32_t d8 = date_at(start, i);
    const std::int64_t open = 1'609'459'200 + static_cast<std::int64_t>(i) * 86'400;
    auto rows = state.snapshot(d8, open, phase_hash);
    ASSERT_TRUE(rows.has_value()) << rows.error().message();
    final = rows.value();
    saw_ready = saw_ready || final[0].status == ForecastStatus::READY;
    ASSERT_TRUE(state.commit(d8, synthetic_realized(i), source_hash).has_value());
  }
  EXPECT_TRUE(saw_ready);
  for (const ForecastRow& row : final) {
    EXPECT_EQ(row.status, ForecastStatus::READY);
    EXPECT_EQ(row.missing_reason, ForecastMissingReason::NONE);
    EXPECT_GE(row.n_train_range, qr::entry_v2::kForecastMinTrain);
    EXPECT_GE(row.n_train_sigma, qr::entry_v2::kForecastMinTrain);
    EXPECT_EQ(row.rank_range, qr::entry_v2::kForecastFeatureCount);
    EXPECT_EQ(row.rank_sigma, qr::entry_v2::kForecastFeatureCount);
    EXPECT_LT(row.fit_end_range_d8, row.fit_month * 100 + 1);
    EXPECT_LT(row.fit_end_sigma_d8, row.fit_month * 100 + 1);
    EXPECT_GT(row.sigma_hat_usd, 0.0);
    EXPECT_GT(row.range_hat_usd, 0.0);
    EXPECT_GE(row.n_calibration, qr::entry_v2::kForecastCalibrationMin);
    EXPECT_NE(row.ladder_source, ForecastLadderSource::MISSING);
    for (std::size_t q = 0; q < row.move_usd.size(); ++q) {
      EXPECT_TRUE(std::isfinite(row.move_usd[q]));
      EXPECT_TRUE(std::isfinite(row.regime_move_usd[q]));
      if (q != 0u) {
        EXPECT_LE(row.move_usd[q - 1u], row.move_usd[q]);
        EXPECT_LE(row.regime_move_usd[q - 1u], row.regime_move_usd[q]);
      }
    }
    if (row.ladder_source == ForecastLadderSource::UNSCALED_FALLBACK) {
      EXPECT_EQ(row.regime_move_ratio, row.move_ratio);
      EXPECT_EQ(row.regime_move_usd, row.move_usd);
    } else {
      EXPECT_GE(row.n_regime_calibration,
                qr::entry_v2::kForecastCalibrationMin);
    }
  }
}

TEST(Qre2ForecastModel, NonfinitePriorMetricIsNotImputed) {
  ASSERT_TRUE(qr::futsess::init_globex_timezone().has_value());
  ForecastModelState state(Asset::SI);
  const std::string phase_hash(64, '2');
  const std::string source_hash(64, '3');
  const std::int64_t start = qr::futsess::date_to_day({2022, 1, 1});
  for (int i = 0; i < 22; ++i) {
    const std::int32_t d8 = date_at(start, i);
    auto rows = state.snapshot(d8, 1'640'995'200 +
        static_cast<std::int64_t>(i) * 86'400, phase_hash);
    ASSERT_TRUE(rows.has_value()) << rows.error().message();
    auto realized = synthetic_realized(i);
    if (i == 17) {
      for (RealizedVolSegment& row : realized) {
        row.rv_usd = std::numeric_limits<double>::quiet_NaN();
      }
    }
    ASSERT_TRUE(state.commit(d8, realized, source_hash).has_value());
  }
  const std::int32_t current_d8 = date_at(start, 22);
  auto current = state.snapshot(current_d8, 1'640'995'200 + 22 * 86'400,
                                phase_hash);
  ASSERT_TRUE(current.has_value()) << current.error().message();
  for (const ForecastRow& row : current.value()) {
    EXPECT_EQ(row.status, ForecastStatus::MISSING);
    EXPECT_EQ(row.missing_reason, ForecastMissingReason::DESIGN_HISTORY);
    EXPECT_FALSE(std::isfinite(row.rv22_usd));
  }
}

TEST(Qre2ForecastJoin, ExactArtifactHashAndStrictAvailabilityAreMandatory) {
  ForecastArtifact artifact;
  artifact.asset = Asset::SI;
  artifact.start_d8 = 20210101;
  artifact.end_d8_exclusive = 20250701;
  artifact.law_sha256 = qr::entry_v2::forecast_law_sha256();
  artifact.artifact_sha256 = std::string(64, '4');
  ForecastRow row;
  row.asset = Asset::SI;
  row.d8 = 20240101;
  row.segment = ForecastSegment::TOKYO;
  row.availability_ts_ns = 100;
  artifact.rows.push_back(row);

  auto equal = qr::entry_v2::join_forecast(
      artifact, 20240101, ForecastSegment::TOKYO, 100,
      artifact.artifact_sha256);
  EXPECT_FALSE(equal.has_value());
  EXPECT_EQ(equal.error().code(), qr::RefusalCode::CLOCK_VIOLATION);
  auto after = qr::entry_v2::join_forecast(
      artifact, 20240101, ForecastSegment::TOKYO, 101,
      artifact.artifact_sha256);
  ASSERT_TRUE(after.has_value()) << after.error().message();
  auto wrong_hash = qr::entry_v2::join_forecast(
      artifact, 20240101, ForecastSegment::TOKYO, 101,
      std::string(64, '5'));
  EXPECT_FALSE(wrong_hash.has_value());
}

TEST(Qre2ForecastSeal, H2IsRefusedBeforeAnyInputCanBeRead) {
  ForecastModelState state(Asset::SI);
  auto snapshot = state.snapshot(20250701, 1'751'324'400,
                                 std::string(64, '6'));
  EXPECT_FALSE(snapshot.has_value());
  EXPECT_EQ(snapshot.error().code(), qr::RefusalCode::CLOCK_VIOLATION);

  qr::entry_v2::Config config;
  config.asset = Asset::SI;
  config.output_root = "/path/that/must/not/be/opened";
  config.end_d8_exclusive = 20250702;
  auto build = qr::entry_v2::build_forecast_artifact(config);
  EXPECT_FALSE(build.has_value());
  EXPECT_EQ(build.error().code(), qr::RefusalCode::DAY_OUTSIDE_CALENDAR);
}
