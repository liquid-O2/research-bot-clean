#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstring>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <limits>
#include <optional>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#include "qr_entry_v2/g1.hpp"

namespace {

using qr::entry_v2::ArrivalThresholds;
using qr::entry_v2::CandidateDelay;
using qr::entry_v2::CandidateRow;
using qr::entry_v2::CandidateSessionStatus;
using qr::entry_v2::CompletedSessionInput;
using qr::entry_v2::DayPriors;
using qr::entry_v2::EventPack;
using qr::entry_v2::EventRow;
using qr::entry_v2::ExpectedSession;
using qr::entry_v2::LockRow;
using qr::entry_v2::LockStatus;
using qr::entry_v2::PhaseRow;
using qr::entry_v2::PivotRow;
using qr::entry_v2::TeacherRow;
using qr::entry_v2::TeacherStatus;
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

PhaseRow phase_schedule() {
  PhaseRow phase;
  phase.month = 202401;
  // TOKYO [00:00,01:00), LONDON [01:00,02:00), NY [02:00,00:00).
  phase.boundaries = {3600, 7200, 0};
  return phase;
}

LockRow lock_row() {
  LockRow lock;
  lock.d8 = 20240101;
  lock.status = LockStatus::LOCKED;
  lock.locked_iid = 17;
  lock.selection_basis_d8 = 20231229;
  lock.open_utc = kDay0;
  lock.close_utc = kDay0 + 3500;
  return lock;
}

DayPriors ready_priors() {
  DayPriors priors;
  priors.d8 = 20240101;
  priors.atr14_present = true;
  priors.atr14_prev_usd = 2000.0;
  for (auto& phase : priors.phase) {
    phase.present = true;
    phase.completed_sessions = 60;
    phase.observations = 6000;
    phase.median_spread_usd = 25.0;
    phase.sane_ceiling_usd = 250.0;
  }
  return priors;
}

EventPack confirmation_pack(std::int64_t equal_decision_mid2) {
  EventPack pack;
  std::memcpy(pack.header.magic, "QRE2EVT2", 8);
  pack.header.version = 2;
  pack.header.asset_idx = static_cast<std::uint8_t>(Asset::SI);
  pack.header.d8 = 20240101;
  pack.header.locked_iid = 17;
  pack.header.open_utc = kDay0;
  pack.header.close_utc = kDay0 + 3500;
  pack.header.row_bytes = qr::entry_v2::kEventRowBytes;
  const std::uint64_t base = static_cast<std::uint64_t>(kDay0) * kNs;
  constexpr std::int64_t base_mid2 = 50'000'000'000LL;
  pack.rows.push_back(bbo(base, base_mid2, 1));
  // +$300 for SI: +0.06 price = +120m in mid2.  Every rung reaches.
  pack.rows.push_back(bbo(base + kNs, base_mid2 + 120'000'000LL, 2));
  // Exactly the FAST_OPEN decision timestamp.  This row is future to its
  // candidate prefix but is the first row of the teacher suffix.
  pack.rows.push_back(bbo(base + 16 * kNs, equal_decision_mid2, 900));
  // Same receive-time batch, smaller sequence second: physical order wins and
  // the whole batch remains future to the equal decision.
  pack.rows.push_back(bbo(base + 16 * kNs, equal_decision_mid2, 1));
  pack.rows.push_back(bbo(base + 200 * kNs, equal_decision_mid2, 4));
  // Exchange time deliberately descends while receive time remains monotone.
  pack.rows[0].ts_event_ns = base + 900u;
  pack.rows[1].ts_event_ns = base + 800u;
  pack.rows[2].ts_event_ns = base + 700u;
  pack.rows[3].ts_event_ns = base + 600u;
  pack.header.n_events = pack.rows.size();
  return pack;
}

LockRow pivot_lock() {
  LockRow lock = lock_row();
  lock.close_utc = kDay0 + 100;
  return lock;
}

EventPack pivot_pack(std::int64_t future_mid2) {
  EventPack pack;
  std::memcpy(pack.header.magic, "QRE2EVT2", 8);
  pack.header.version = 2;
  pack.header.asset_idx = static_cast<std::uint8_t>(Asset::SI);
  pack.header.d8 = 20240101;
  pack.header.locked_iid = 17;
  pack.header.open_utc = kDay0;
  pack.header.close_utc = kDay0 + 100;
  pack.header.row_bytes = qr::entry_v2::kEventRowBytes;
  const std::uint64_t base_ts = static_cast<std::uint64_t>(kDay0) * kNs;
  constexpr std::int64_t base_mid2 = 50'000'000'000LL;
  pack.rows = {
      bbo(base_ts, base_mid2, 1),
      bbo(base_ts + kNs, base_mid2 + 120'000'000LL, 2),
      bbo(base_ts + 2 * kNs, base_mid2 + 200'000'000LL, 3),
      bbo(base_ts + 3 * kNs, base_mid2 - 200'000'000LL, 4),
      bbo(base_ts + 18 * kNs, future_mid2, 5),
  };
  pack.header.n_events = pack.rows.size();
  pack.artifact_sha256 = std::string(64, 'a');
  return pack;
}

std::vector<PivotRow> pivots_for(
    const std::vector<PivotRow>& rows, std::string_view candidate_id) {
  std::vector<PivotRow> out;
  std::copy_if(rows.begin(), rows.end(), std::back_inserter(out),
               [candidate_id](const PivotRow& row) {
                 return row.candidate_id == candidate_id;
               });
  return out;
}

std::string pivot_bytes(const std::vector<PivotRow>& rows) {
  std::ostringstream out;
  out << "# QRE2G1PIVOT1\n"
         "candidate_id\tasset\td8\trung_index\tside\tpivot_mid2"
         "\tpivot_ts_recv_ns\tpivot_ordinal\tleg_start_mid2"
         "\tleg_start_ts_recv_ns\tleg_start_ordinal\tconf_mid2"
         "\tthreshold_mid2_raw\n";
  for (const PivotRow& row : rows) {
    out << row.candidate_id << '\t'
        << qr::futsess::asset_spec(row.asset).name << '\t' << row.d8 << '\t'
        << static_cast<unsigned>(row.rung_index) << '\t'
        << static_cast<int>(row.side) << '\t' << row.pivot_mid2 << '\t'
        << row.pivot_ts_recv_ns << '\t' << row.pivot_ordinal << '\t'
        << row.leg_start_mid2 << '\t' << row.leg_start_ts_recv_ns << '\t'
        << row.leg_start_ordinal << '\t' << row.conf_mid2 << '\t'
        << row.threshold_mid2_raw << '\n';
  }
  return out.str();
}

std::vector<std::string> split_tabs(std::string_view line) {
  std::vector<std::string> fields;
  std::size_t start = 0;
  while (start <= line.size()) {
    const std::size_t tab = line.find('\t', start);
    const std::size_t end =
        tab == std::string_view::npos ? line.size() : tab;
    fields.emplace_back(line.substr(start, end - start));
    if (tab == std::string_view::npos) break;
    start = tab + 1;
  }
  return fields;
}

std::optional<DayPriors> load_prior(
    const std::filesystem::path& path, std::string_view asset,
    std::int32_t wanted_d8) {
  std::ifstream in(path);
  std::string line;
  try {
    while (std::getline(in, line)) {
      if (line.empty() || line[0] == '#' ||
          line.starts_with("asset\t")) {
        continue;
      }
      const std::vector<std::string> fields = split_tabs(line);
      if (fields.size() != 19u || fields[0] != asset ||
          std::stoi(fields[1]) != wanted_d8) {
        continue;
      }
      DayPriors prior;
      const auto number = [](const std::string& text) {
        return text == "NA" ? std::numeric_limits<double>::quiet_NaN()
                            : std::stod(text);
      };
      prior.d8 = wanted_d8;
      prior.atr14_present = std::stoi(fields[2]) != 0;
      prior.atr14_prev_usd = number(fields[3]);
      for (std::size_t p = 0; p < prior.phase.size(); ++p) {
        const std::size_t offset = 4u + p * 5u;
        prior.phase[p].present = std::stoi(fields[offset]) != 0;
        prior.phase[p].completed_sessions =
            static_cast<std::uint32_t>(std::stoul(fields[offset + 1u]));
        prior.phase[p].observations = std::stoull(fields[offset + 2u]);
        prior.phase[p].median_spread_usd = number(fields[offset + 3u]);
        prior.phase[p].sane_ceiling_usd = number(fields[offset + 4u]);
      }
      return prior;
    }
  } catch (const std::exception&) {
    return std::nullopt;
  }
  return std::nullopt;
}

std::int64_t raw_tick(Asset asset) {
  switch (asset) {
    case Asset::SI: return 5'000'000;
    case Asset::HG: return 500'000;
    case Asset::NKD: return 5'000'000'000;
  }
  return 0;
}

const CandidateRow& fast_long(const std::vector<CandidateRow>& rows) {
  const auto found = std::find_if(rows.begin(), rows.end(), [](const CandidateRow& row) {
    return row.delay == CandidateDelay::FAST_OPEN_15 && row.side == 1 &&
           row.confirmation_event_ordinal == 1;
  });
  EXPECT_NE(found, rows.end());
  return *found;
}

TeacherRow teacher(std::string id, Asset asset, std::int32_t d8,
                   std::uint64_t decision, std::uint64_t exit, double value) {
  TeacherRow row;
  row.candidate_id = std::move(id);
  row.asset = asset;
  row.d8 = d8;
  row.decision_ts_ns = decision;
  row.exit_ts_ns = exit;
  row.phase_close_utc = static_cast<std::int64_t>(exit / kNs);
  row.status = TeacherStatus::READY;
  row.cert_close_usd = value;
  row.payer = value > 0.0;
  row.take_target = value >= qr::entry_v2::kTakeTargetUsd;
  row.compliance = qr::entry_v2::ComplianceStatus::CLEAR;
  return row;
}

}  // namespace

TEST(EntryV2Priors, DaySnapshotIsTakenBeforeThatDayCanEnterAtrOrSpreadHistory) {
  qr::entry_v2::CausalPriorState state(Asset::SI);
  auto first = state.snapshot(20240101);
  ASSERT_TRUE(first.has_value()) << first.error().message();
  EXPECT_FALSE(first.value().atr14_present);
  EXPECT_FALSE(first.value().phase[0].present);
  EXPECT_DOUBLE_EQ(first.value().phase[0].sane_ceiling_usd, 500.0);

  constexpr std::int64_t center = 50'000'000'000LL;
  for (std::size_t i = 0; i < 14; ++i) {
    CompletedSessionInput completed;
    completed.d8 = 20240101 + static_cast<std::int32_t>(i);
    completed.locked_iid = 7;
    completed.session_ordinal = i;
    completed.bar_present = true;
    completed.bar_high_mid2 = center + 10'000'000;
    completed.bar_low_mid2 = center - 10'000'000;
    completed.bar_close_mid2 = center;
    completed.phase_spread_ticks[0][1] = 10;
    auto committed = state.commit(completed);
    ASSERT_TRUE(committed.has_value()) << committed.error().message();
  }
  auto day15 = state.snapshot(20240115);
  ASSERT_TRUE(day15.has_value()) << day15.error().message();
  ASSERT_TRUE(day15.value().atr14_present);
  EXPECT_DOUBLE_EQ(day15.value().atr14_prev_usd, 50.0);
  ASSERT_TRUE(day15.value().phase[0].present);
  EXPECT_DOUBLE_EQ(day15.value().phase[0].median_spread_usd, 25.0);
  EXPECT_EQ(day15.value().phase[0].completed_sessions, 14u);

  CompletedSessionInput poison;
  poison.d8 = 20240115;
  poison.locked_iid = 7;
  poison.session_ordinal = 14;
  poison.bar_present = true;
  poison.bar_high_mid2 = center + 2'000'000'000;
  poison.bar_low_mid2 = center - 2'000'000'000;
  poison.bar_close_mid2 = center;
  poison.phase_spread_ticks[0][100] = 1'000'000;
  ASSERT_TRUE(state.commit(poison).has_value());
  // The already-exposed day-15 value is immutable; only day 16 sees poison.
  EXPECT_DOUBLE_EQ(day15.value().atr14_prev_usd, 50.0);
  EXPECT_DOUBLE_EQ(day15.value().phase[0].median_spread_usd, 25.0);
  auto day16 = state.snapshot(20240116);
  ASSERT_TRUE(day16.has_value());
  EXPECT_GT(day16.value().atr14_prev_usd, day15.value().atr14_prev_usd);
  EXPECT_GT(day16.value().phase[0].median_spread_usd,
            day15.value().phase[0].median_spread_usd);
}

TEST(EntryV2Candidates, MissingAtrIsTypedNoCandidateButStillBuildsCurrentPriors) {
  DayPriors missing = ready_priors();
  missing.atr14_present = false;
  missing.atr14_prev_usd = std::numeric_limits<double>::quiet_NaN();
  EventPack pack = confirmation_pack(50'000'000'000LL);
  auto built = qr::entry_v2::generate_g1_candidates(
      Asset::SI, lock_row(), phase_schedule(), pack, missing, 0);
  ASSERT_TRUE(built.has_value()) << built.error().message();
  EXPECT_EQ(built.value().status, CandidateSessionStatus::NO_ATR14);
  EXPECT_TRUE(built.value().candidates.empty());
  EXPECT_GT(built.value().completed.phase_spread_ticks[0].at(1), 0u);
}

TEST(EntryV2Candidates, EqualTimestampIsFutureAndFutureMutationCannotChangeTheCandidate) {
  constexpr std::int64_t base_mid2 = 50'000'000'000LL;
  EventPack loss = confirmation_pack(base_mid2 - 280'000'000LL);
  EventPack gain = confirmation_pack(base_mid2 + 400'000'000LL);
  gain.rows[2].ts_event_ns += 999u * kNs;
  auto loss_built = qr::entry_v2::generate_g1_candidates(
      Asset::SI, lock_row(), phase_schedule(), loss, ready_priors(), 0);
  auto gain_built = qr::entry_v2::generate_g1_candidates(
      Asset::SI, lock_row(), phase_schedule(), gain, ready_priors(), 0);
  ASSERT_TRUE(loss_built.has_value()) << loss_built.error().message();
  ASSERT_TRUE(gain_built.has_value()) << gain_built.error().message();
  const CandidateRow& a = fast_long(loss_built.value().candidates);
  const CandidateRow& b = fast_long(gain_built.value().candidates);
  EXPECT_EQ(a.decision_ts_ns,
            static_cast<std::uint64_t>(kDay0) * kNs + 16 * kNs);
  EXPECT_EQ(a.event_cutoff, 2u);
  EXPECT_EQ(a.prefix_last_event_ordinal, 1u);
  EXPECT_LT(a.prefix_last_availability_ts_ns, a.decision_ts_ns);
  EXPECT_EQ(a.entry_mid2, base_mid2 + 120'000'000LL);
  EXPECT_NE(a.event_pack_sha256, b.event_pack_sha256);
  EXPECT_NE(a.candidate_id, b.candidate_id);
  EXPECT_EQ(a.rung_mask, 0b1111);
  // Pins the QRE2PREFIX2 domain separator and canonical receive-clock prefix;
  // a version-seed truncation must be an intentional break.
  EXPECT_EQ(a.prefix_sha256,
            "22e82d48f3b5064323e00312990ccd3b86211c1f7e1cae772857aa108909f5c1");
  EXPECT_EQ(a.prefix_sha256, b.prefix_sha256);
  EXPECT_NE(a.lineage_sha256, b.lineage_sha256);
  EXPECT_EQ(a.entry_mid2, b.entry_mid2);
  EXPECT_DOUBLE_EQ(a.frozen_cost_usd, 30.0);  // one SI tick + frozen $5

  auto loss_teacher = qr::entry_v2::certify_teacher(
      Asset::SI, phase_schedule(), loss, ready_priors(), {a});
  auto gain_teacher = qr::entry_v2::certify_teacher(
      Asset::SI, phase_schedule(), gain, ready_priors(), {b});
  ASSERT_TRUE(loss_teacher.has_value()) << loss_teacher.error().message();
  ASSERT_TRUE(gain_teacher.has_value()) << gain_teacher.error().message();
  ASSERT_EQ(loss_teacher.value().size(), 1u);
  EXPECT_TRUE(loss_teacher.value()[0].wall_hit);
  EXPECT_EQ(loss_teacher.value()[0].exit_ts_ns, a.decision_ts_ns);
  // Entry is +$300; equal-time future row is -$700: gross -$1,000, cost $30.
  EXPECT_DOUBLE_EQ(loss_teacher.value()[0].cert_close_usd, -1030.0);
  EXPECT_DOUBLE_EQ(loss_teacher.value()[0].mae_usd, 1030.0);
  EXPECT_DOUBLE_EQ(loss_teacher.value()[0].mfe_usd, 0.0);
  EXPECT_DOUBLE_EQ(loss_teacher.value()[0].time_to_peak_sec, 0.0);
  EXPECT_FALSE(loss_teacher.value()[0].payer);
  EXPECT_FALSE(loss_teacher.value()[0].take_target);
  EXPECT_GT(gain_teacher.value()[0].cert_close_usd, 600.0);
  EXPECT_TRUE(gain_teacher.value()[0].payer);
  EXPECT_TRUE(gain_teacher.value()[0].take_target);

  EventPack no_suffix = loss;
  for (std::size_t i = a.event_cutoff; i < no_suffix.rows.size(); ++i) {
    no_suffix.rows[i].ask_px = no_suffix.rows[i].bid_px;  // crossed/locked
  }
  CandidateRow refused_candidate = a;
  refused_candidate.event_pack_sha256 = qr::entry_v2::event_pack_sha256(no_suffix);
  refused_candidate.candidate_id = qr::entry_v2::g1_candidate_id(refused_candidate);
  refused_candidate.compliance = qr::entry_v2::ComplianceStatus::PROHIBITED;
  refused_candidate.lineage_sha256 =
      qr::entry_v2::g1_candidate_lineage(refused_candidate);
  auto refused_teacher = qr::entry_v2::certify_teacher(
      Asset::SI, phase_schedule(), no_suffix, ready_priors(), {refused_candidate});
  ASSERT_TRUE(refused_teacher.has_value()) << refused_teacher.error().message();
  ASSERT_EQ(refused_teacher.value().size(), 1u);
  EXPECT_EQ(refused_teacher.value()[0].status, TeacherStatus::NO_SANE_SUFFIX);
  EXPECT_EQ(refused_teacher.value()[0].compliance,
            qr::entry_v2::ComplianceStatus::PROHIBITED);
}

TEST(EntryV2Candidates, PivotBirthRowsUsePreFlipStateAndExcludeFutureRows) {
  constexpr std::int64_t base_mid2 = 50'000'000'000LL;
  EventPack first = pivot_pack(base_mid2 - 190'000'000LL);
  EventPack mutated = pivot_pack(base_mid2 - 180'000'000LL);
  auto baseline = qr::entry_v2::generate_g1_candidates(
      Asset::SI, pivot_lock(), phase_schedule(), first, ready_priors(), 0);
  auto future_changed = qr::entry_v2::generate_g1_candidates(
      Asset::SI, pivot_lock(), phase_schedule(), mutated, ready_priors(), 0);
  ASSERT_TRUE(baseline.has_value()) << baseline.error().message();
  ASSERT_TRUE(future_changed.has_value()) << future_changed.error().message();
  ASSERT_EQ(baseline.value().candidates.size(),
            future_changed.value().candidates.size());
  for (std::size_t i = 0; i < baseline.value().candidates.size(); ++i) {
    EXPECT_EQ(baseline.value().candidates[i].candidate_id,
              future_changed.value().candidates[i].candidate_id);
    EXPECT_EQ(baseline.value().candidates[i].prefix_sha256,
              future_changed.value().candidates[i].prefix_sha256);
    EXPECT_EQ(baseline.value().candidates[i].rung_mask,
              future_changed.value().candidates[i].rung_mask);
  }
  ASSERT_EQ(baseline.value().pivots, future_changed.value().pivots);

  const auto candidate = std::find_if(
      baseline.value().candidates.begin(), baseline.value().candidates.end(),
      [](const CandidateRow& row) {
        return row.delay == CandidateDelay::FAST_OPEN_15 && row.side == -1 &&
               row.confirmation_event_ordinal == 3u;
      });
  ASSERT_NE(candidate, baseline.value().candidates.end());
  const std::vector<PivotRow> pivots =
      pivots_for(baseline.value().pivots, candidate->candidate_id);
  ASSERT_EQ(pivots.size(), qr::entry_v2::kG1RungCount);
  for (std::size_t rung = 0; rung < pivots.size(); ++rung) {
    const PivotRow& row = pivots[rung];
    EXPECT_EQ(row.rung_index, rung);
    EXPECT_EQ(row.side, -1);
    EXPECT_EQ(row.pivot_mid2, base_mid2 + 200'000'000LL);
    EXPECT_EQ(row.pivot_ordinal, 2u);
    EXPECT_EQ(row.leg_start_mid2, base_mid2);
    EXPECT_EQ(row.leg_start_ordinal, 0u);
    EXPECT_EQ(row.conf_mid2, base_mid2 - 200'000'000LL);
    EXPECT_GT(row.threshold_mid2_raw, 0);
  }
}

TEST(EntryV2Candidates, RealSessionFutureMutationLeavesPivotTagBytesUnchanged) {
  const char* root_env = std::getenv("QRE2_G1_REAL_ROOT");
  const char* asset_env = std::getenv("QRE2_G1_REAL_ASSET");
  const char* d8_env = std::getenv("QRE2_G1_REAL_D8");
  if (root_env == nullptr || asset_env == nullptr || d8_env == nullptr) {
    GTEST_SKIP();
  }
  Asset asset{};
  ASSERT_TRUE(qr::futsess::asset_from_name(asset_env, &asset));
  const std::int32_t d8 = std::stoi(d8_env);
  qr::entry_v2::Config config;
  config.asset = asset;
  config.output_root = root_env;
  auto locks = qr::entry_v2::read_locks(config);
  auto phases = qr::entry_v2::read_phases(config);
  ASSERT_TRUE(locks.has_value()) << locks.error().message();
  ASSERT_TRUE(phases.has_value()) << phases.error().message();
  const auto lock = std::find_if(
      locks.value().begin(), locks.value().end(),
      [d8](const LockRow& row) { return row.d8 == d8; });
  ASSERT_NE(lock, locks.value().end());
  const auto phase = std::find_if(
      phases.value().begin(), phases.value().end(),
      [d8](const PhaseRow& row) { return row.month == d8 / 100; });
  ASSERT_NE(phase, phases.value().end());
  const std::filesystem::path root(root_env);
  const auto prior = load_prior(
      root / "g1" / "priors" / (std::string(asset_env) + ".tsv"),
      asset_env, d8);
  ASSERT_TRUE(prior.has_value());
  const auto started = std::chrono::steady_clock::now();
  auto pack = qr::entry_v2::read_event_pack(
      (root / "events" / asset_env /
       (std::to_string(d8) + ".qre2")).string(),
      "");
  ASSERT_TRUE(pack.has_value()) << pack.error().message();
  const std::size_t ordinal = static_cast<std::size_t>(
      std::distance(locks.value().begin(), lock));
  auto baseline = qr::entry_v2::generate_g1_candidates(
      asset, *lock, *phase, pack.value(), *prior, ordinal);
  const auto elapsed = std::chrono::steady_clock::now() - started;
  ASSERT_TRUE(baseline.has_value()) << baseline.error().message();
  const auto candidate = std::find_if(
      baseline.value().candidates.begin(), baseline.value().candidates.end(),
      [&pack](const CandidateRow& row) {
        if (row.event_cutoff >= pack.value().rows.size()) return false;
        const EventRow& future =
            pack.value().rows[static_cast<std::size_t>(row.event_cutoff)];
        return future.bid_px > 0 && future.ask_px > future.bid_px;
      });
  ASSERT_NE(candidate, baseline.value().candidates.end());
  ASSERT_FALSE(pivots_for(
      baseline.value().pivots, candidate->candidate_id).empty());
  std::cout << "QRE2_PIVOT_REAL_SESSION"
            << "\tasset=" << asset_env
            << "\td8=" << d8
            << "\traw_events=" << pack.value().rows.size()
            << "\twall_ns="
            << std::chrono::duration_cast<std::chrono::nanoseconds>(
                   elapsed).count()
            << '\n';

  EventPack changed = pack.value();
  EventRow& future =
      changed.rows[static_cast<std::size_t>(candidate->event_cutoff)];
  const std::int64_t tick = raw_tick(asset);
  ASSERT_GT(tick, 0);
  ASSERT_LE(future.ask_px, std::numeric_limits<std::int64_t>::max() - tick);
  future.bid_px += tick;
  future.ask_px += tick;
  future.price = future.ask_px;
  auto mutated = qr::entry_v2::generate_g1_candidates(
      asset, *lock, *phase, changed, *prior, ordinal);
  ASSERT_TRUE(mutated.has_value()) << mutated.error().message();
  const auto same_candidate = std::find_if(
      mutated.value().candidates.begin(), mutated.value().candidates.end(),
      [&candidate](const CandidateRow& row) {
        return row.candidate_id == candidate->candidate_id;
      });
  ASSERT_NE(same_candidate, mutated.value().candidates.end());
  EXPECT_EQ(
      pivot_bytes(pivots_for(
          baseline.value().pivots, candidate->candidate_id)),
      pivot_bytes(pivots_for(
          mutated.value().pivots, same_candidate->candidate_id)));
}

TEST(EntryV2Candidates, SnapshotAndBookHealthFlagsCannotManufactureEconomicMotion) {
  const std::uint64_t base = static_cast<std::uint64_t>(kDay0) * kNs;
  constexpr std::int64_t mid = 50'000'000'000LL;
  EventPack pack = confirmation_pack(mid);
  pack.rows = {
      bbo(base, mid - 2'000'000'000LL, 90, base + 900u, 0x28u),
      bbo(base, mid + 2'000'000'000LL, 1, base + 800u, 0x28u),
      bbo(base + kNs, mid, 2),                 // trust seed, not economic
      bbo(base + 2u * kNs, mid, 3),           // machine initialization
      bbo(base + 3u * kNs, mid + 120'000'000LL, 4),
      bbo(base + 18u * kNs, mid + 120'000'000LL, 5),
  };
  pack.header.n_events = pack.rows.size();
  auto built = qr::entry_v2::generate_g1_candidates(
      Asset::SI, lock_row(), phase_schedule(), pack, ready_priors(), 0);
  ASSERT_TRUE(built.has_value()) << built.error().message();
  ASSERT_FALSE(built.value().candidates.empty());
  const auto found = std::find_if(
      built.value().candidates.begin(), built.value().candidates.end(),
      [](const CandidateRow& row) {
        return row.delay == CandidateDelay::FAST_OPEN_15 && row.side == 1 &&
               row.confirmation_event_ordinal == 4u;
      });
  ASSERT_NE(found, built.value().candidates.end());
  const CandidateRow& candidate = *found;
  EXPECT_EQ(candidate.confirmation_event_ordinal, 4u);
  EXPECT_EQ(candidate.event_cutoff, 5u);
  EXPECT_EQ(built.value().two_sided_events, 3u);

  EventPack tainted = confirmation_pack(mid);
  tainted.rows[1].flags = 0x04u;  // MAYBE_BAD_BOOK: no reset follows.
  auto no_motion = qr::entry_v2::generate_g1_candidates(
      Asset::SI, lock_row(), phase_schedule(), tainted, ready_priors(), 0);
  ASSERT_TRUE(no_motion.has_value()) << no_motion.error().message();
  EXPECT_TRUE(no_motion.value().candidates.empty());

  EventPack standalone_bad = confirmation_pack(mid);
  standalone_bad.rows[1].flags = 0x08u;
  auto refused = qr::entry_v2::generate_g1_candidates(
      Asset::SI, lock_row(), phase_schedule(), standalone_bad, ready_priors(), 0);
  EXPECT_FALSE(refused.has_value());
}

TEST(EntryV2Candidates, V1EventPackCannotEnterTheV2CandidateLaw) {
  EventPack stale = confirmation_pack(50'000'000'000LL);
  std::memcpy(stale.header.magic, "QRE2EVT1", 8);
  stale.header.version = 1u;
  auto refused = qr::entry_v2::generate_g1_candidates(
      Asset::SI, lock_row(), phase_schedule(), stale, ready_priors(), 0);
  EXPECT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}

TEST(EntryV2Compliance, PointInTimeCoverageIsRequiredAndProhibitedIntervalsStaySeparate) {
  qr::entry_v2::ComplianceCalendar calendar;
  calendar.available = true;
  calendar.artifact_sha256 = std::string(64, 'b');
  calendar.rows = {
      {qr::entry_v2::ComplianceRowKind::COVERAGE, "COV", 100 * kNs, 900 * kNs,
       1 * kNs, std::string(64, 'c')},
      {qr::entry_v2::ComplianceRowKind::PROHIBITED, "BLS", 400 * kNs, 600 * kNs,
       2 * kNs, std::string(64, 'd')},
      // A later-known row is never backfilled into the 700s candidate.
      {qr::entry_v2::ComplianceRowKind::PROHIBITED, "LATE", 700 * kNs, 700 * kNs,
       800 * kNs, std::string(64, 'e')},
  };
  std::vector<CandidateRow> candidates(3);
  for (std::size_t i = 0; i < candidates.size(); ++i) {
    candidates[i].candidate_id = "C" + std::to_string(i);
  }
  candidates[0].decision_ts_ns = 500 * kNs;
  candidates[1].decision_ts_ns = 700 * kNs;
  candidates[2].decision_ts_ns = 1000 * kNs;
  auto applied = qr::entry_v2::apply_candidate_compliance(&calendar, &candidates);
  ASSERT_TRUE(applied.has_value()) << applied.error().message();
  EXPECT_EQ(candidates[0].compliance,
            qr::entry_v2::ComplianceStatus::PROHIBITED);
  EXPECT_DOUBLE_EQ(candidates[0].compliance_distance_sec, 0.0);
  EXPECT_EQ(candidates[1].compliance, qr::entry_v2::ComplianceStatus::CLEAR);
  EXPECT_DOUBLE_EQ(candidates[1].compliance_distance_sec, 100.0);
  EXPECT_EQ(candidates[2].compliance,
            qr::entry_v2::ComplianceStatus::COMPLIANCE_UNKNOWN);

  std::vector<CandidateRow> absent(1);
  absent[0].candidate_id = "ABSENT";
  absent[0].decision_ts_ns = 500 * kNs;
  ASSERT_TRUE(qr::entry_v2::apply_candidate_compliance(nullptr, &absent).has_value());
  EXPECT_EQ(absent[0].compliance,
            qr::entry_v2::ComplianceStatus::COMPLIANCE_UNKNOWN);
}

TEST(EntryV2Compliance, ArtifactIsHashPinnedAndEnforcesTheExactTwentyMinuteVeto) {
  namespace fs = std::filesystem;
  const std::string prefix =
      "# QRE2COMPLIANCE1\n"
      "kind\tinterval_id\tstart_ts_ns\tend_ts_ns\tavailability_ts_ns"
      "\tprovenance_sha256\n"
      "COVERAGE\tCOV\t1000000000\t3000000000000\t500000000\t" +
      std::string(64, 'c') + "\nPROHIBITED\tBLS\t600000000000\t";
  const std::string suffix = "\t500000000\t" + std::string(64, 'd') + "\n";
  const fs::path dir = fs::path(QR_TEST_SCRATCH_DIR) / "qr_entry_v2_g1";
  std::error_code ec;
  fs::create_directories(dir, ec);
  ASSERT_FALSE(ec);
  const fs::path good_path = dir / "compliance.tsv";
  {
    std::ofstream out(good_path, std::ios::binary | std::ios::trunc);
    out << prefix << "1800000000000" << suffix;
    ASSERT_TRUE(out.good());
  }
  auto good = qr::entry_v2::load_compliance_calendar(
      good_path.string(),
      "7e90a1387364c0689f90742cbb0d4a5684bff17f305d60104ae2a132609df997");
  ASSERT_TRUE(good.has_value()) << good.error().message();
  EXPECT_TRUE(good.value().available);
  EXPECT_EQ(good.value().rows.size(), 2u);
  auto wrong_hash = qr::entry_v2::load_compliance_calendar(
      good_path.string(), std::string(64, '0'));
  EXPECT_FALSE(wrong_hash.has_value());
  EXPECT_EQ(wrong_hash.error().code(), qr::RefusalCode::CONTENT_MISMATCH);

  const fs::path bad_path = dir / "bad_duration.tsv";
  {
    std::ofstream out(bad_path, std::ios::binary | std::ios::trunc);
    out << prefix << "1799999999999" << suffix;
    ASSERT_TRUE(out.good());
  }
  auto bad = qr::entry_v2::load_compliance_calendar(
      bad_path.string(),
      "2b4a6a059e04d825ae68d23976e391318d8c400bf7645640d16d78a38482c00d");
  EXPECT_FALSE(bad.has_value());
  EXPECT_EQ(bad.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}

TEST(EntryV2Schedules, ExactCeilingAndChronologicalTruthArrivalAreDifferentObjects) {
  const std::vector<TeacherRow> rows = {
      teacher("EARLY", Asset::SI, 20240101, 10 * kNs, 100 * kNs, 700.0),
      teacher("LATER_BETTER", Asset::SI, 20240101, 20 * kNs, 30 * kNs, 2000.0),
      teacher("AFTER", Asset::SI, 20240101, 101 * kNs, 110 * kNs, 700.0),
  };
  const std::vector<ExpectedSession> sessions = {
      {Asset::SI, 20240101}, {Asset::SI, 20240102}};
  auto ceiling = qr::entry_v2::exact_schedule_ceiling(rows, sessions);
  ASSERT_TRUE(ceiling.has_value()) << ceiling.error().message();
  EXPECT_FALSE(ceiling.value().selected.at("EARLY"));
  EXPECT_TRUE(ceiling.value().selected.at("LATER_BETTER"));
  EXPECT_TRUE(ceiling.value().selected.at("AFTER"));
  EXPECT_DOUBLE_EQ(ceiling.value().total_usd, 2700.0);
  EXPECT_EQ(ceiling.value().zero_sessions, 1u);
  EXPECT_DOUBLE_EQ(ceiling.value().usd_per_session, 1350.0);

  ArrivalThresholds threshold;
  threshold.min_value_usd[Asset::SI] = 600.0;
  threshold.threshold_receipt_sha256 = std::string(64, 'a');
  auto arrival = qr::entry_v2::chronological_truth_arrival(rows, sessions, threshold);
  ASSERT_TRUE(arrival.has_value()) << arrival.error().message();
  EXPECT_TRUE(arrival.value().selected.at("EARLY"));
  EXPECT_FALSE(arrival.value().selected.at("LATER_BETTER"));
  EXPECT_TRUE(arrival.value().selected.at("AFTER"));
  EXPECT_DOUBLE_EQ(arrival.value().total_usd, 1400.0);
  EXPECT_NE(arrival.value().selected, ceiling.value().selected);
}

TEST(EntryV2Schedules, StrictOccupancyCapsAndEmptySessionDenominatorAreExact) {
  std::vector<TeacherRow> rows = {
      teacher("A", Asset::HG, 20240103, 10 * kNs, 20 * kNs, 100.0),
      // decision == A.exit is occupied under the strict law.
      teacher("B", Asset::HG, 20240103, 20 * kNs, 21 * kNs, 1000.0),
      teacher("C", Asset::HG, 20240103, 22 * kNs, 23 * kNs, 900.0),
      teacher("D", Asset::HG, 20240103, 24 * kNs, 25 * kNs, 800.0),
      teacher("E", Asset::HG, 20240103, 26 * kNs, 27 * kNs, 700.0),
  };
  const std::vector<ExpectedSession> sessions = {
      {Asset::HG, 20240103}, {Asset::HG, 20240104}, {Asset::NKD, 20240103}};
  auto ceiling = qr::entry_v2::exact_schedule_ceiling(rows, sessions);
  ASSERT_TRUE(ceiling.has_value()) << ceiling.error().message();
  EXPECT_EQ(ceiling.value().selected_count, 3u);
  EXPECT_TRUE(ceiling.value().selected.at("B"));
  EXPECT_TRUE(ceiling.value().selected.at("C"));
  EXPECT_TRUE(ceiling.value().selected.at("D"));
  EXPECT_FALSE(ceiling.value().selected.at("A"));
  EXPECT_FALSE(ceiling.value().selected.at("E"));
  EXPECT_LE(ceiling.value().selected_count,
            qr::entry_v2::kMaxEntriesPerPortfolioDay);
  EXPECT_EQ(ceiling.value().expected_sessions, 3u);
  EXPECT_EQ(ceiling.value().zero_sessions, 2u);

  auto empty = qr::entry_v2::exact_schedule_ceiling({}, sessions);
  ASSERT_TRUE(empty.has_value()) << empty.error().message();
  EXPECT_EQ(empty.value().selected_count, 0u);
  EXPECT_EQ(empty.value().zero_sessions, sessions.size());
  EXPECT_DOUBLE_EQ(empty.value().usd_per_session, 0.0);
}

TEST(EntryV2Schedules, DeployableCeilingExcludesUnknownAndProhibitedMechanics) {
  std::vector<TeacherRow> rows = {
      teacher("CLEAR", Asset::SI, 20240105, 10 * kNs, 11 * kNs, 100.0),
      teacher("BLOCKED", Asset::SI, 20240105, 12 * kNs, 13 * kNs, 2000.0),
      teacher("UNKNOWN", Asset::SI, 20240105, 14 * kNs, 15 * kNs, 3000.0),
  };
  rows[1].compliance = qr::entry_v2::ComplianceStatus::PROHIBITED;
  rows[2].compliance = qr::entry_v2::ComplianceStatus::COMPLIANCE_UNKNOWN;
  const std::vector<ExpectedSession> sessions = {{Asset::SI, 20240105}};
  auto deployable = qr::entry_v2::exact_schedule_ceiling(rows, sessions);
  auto mechanical = qr::entry_v2::exact_schedule_ceiling(
      rows, sessions, qr::entry_v2::ScheduleUniverse::MECHANICAL_ALL);
  ASSERT_TRUE(deployable.has_value()) << deployable.error().message();
  ASSERT_TRUE(mechanical.has_value()) << mechanical.error().message();
  EXPECT_TRUE(deployable.value().selected.at("CLEAR"));
  EXPECT_FALSE(deployable.value().selected.at("BLOCKED"));
  EXPECT_FALSE(deployable.value().selected.at("UNKNOWN"));
  EXPECT_DOUBLE_EQ(deployable.value().total_usd, 100.0);
  EXPECT_DOUBLE_EQ(mechanical.value().total_usd, 5100.0);
}

TEST(EntryV2Schedules, PortfolioAndPerAssetDayCapsBindAtExactlyNine) {
  std::vector<TeacherRow> rows;
  const std::array<Asset, 3> assets = {Asset::SI, Asset::HG, Asset::NKD};
  for (std::size_t a = 0; a < assets.size(); ++a) {
    for (std::size_t i = 0; i < 4; ++i) {
      const std::uint64_t decision = (10u + i * 10u) * kNs;
      rows.push_back(teacher("A" + std::to_string(a) + "-" + std::to_string(i),
                             assets[a], 20240106, decision, decision + kNs,
                             100.0 + static_cast<double>(i)));
    }
  }
  const std::vector<ExpectedSession> sessions = {
      {Asset::SI, 20240106}, {Asset::HG, 20240106}, {Asset::NKD, 20240106}};
  auto ceiling = qr::entry_v2::exact_schedule_ceiling(rows, sessions);
  ASSERT_TRUE(ceiling.has_value()) << ceiling.error().message();
  EXPECT_EQ(ceiling.value().selected_count, 9u);
  EXPECT_EQ(ceiling.value().selected_count,
            qr::entry_v2::kMaxEntriesPerPortfolioDay);
  for (std::size_t a = 0; a < assets.size(); ++a) {
    std::size_t selected = 0;
    for (std::size_t i = 0; i < 4; ++i) {
      selected += ceiling.value().selected.at(
          "A" + std::to_string(a) + "-" + std::to_string(i));
    }
    EXPECT_EQ(selected, qr::entry_v2::kMaxEntriesPerAssetDay);
  }
}
