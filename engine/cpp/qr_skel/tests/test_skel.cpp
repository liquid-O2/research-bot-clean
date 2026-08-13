// qr_skel test suite — the STRUCTURAL laws of PORT_M1B_SPEC §1 S3 plus the
// per-field semantics of design/PORT_M1B_S3_CONV.md.
//
// Every test in this file has a committed mutant in tests/mutants/MS*.patch and
// a red log proving it can fail (tests/red_ledger.tsv). The fixtures are
// synthetic sessions built here, so the suite runs without the corpus; the
// byte-exact agreement with the independent Python oracle over real sessions is
// the separate parity gate (engine/port_m1b/compare_skel.py).
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <filesystem>
#include <limits>
#include <string>
#include <vector>

#include "gtest/gtest.h"
#include "qr_skel/binpack.hpp"
#include "qr_skel/engine.hpp"
#include "qr_skel/geom.hpp"
#include "qr_skel/query.hpp"
#include "qr_skel/session.hpp"
#include "qr_skel/skeleton.hpp"

namespace {

using namespace qr::skel;  // NOLINT(build/namespaces) — test-local
using qr::futsess::Asset;

std::string scratch(const std::string& leaf) {
  const std::string dir = std::string(QR_TEST_SCRATCH_DIR) + "/qr_skel/" + leaf;
  std::filesystem::create_directories(dir);
  return dir;
}

/// Write a synthetic QRSESS1 session receipt: `mid` on a 1-second grid, with
/// `state` 0 (two-sided) or 5 (empty) and a phase tag per second.
void write_session(const std::string& dir, std::int32_t date8, const std::vector<double>& mid,
                   const std::vector<std::int8_t>& state, const std::vector<std::int8_t>& phase,
                   const std::vector<double>* spread = nullptr) {
  const std::vector<double> flat(mid.size(), 1.0);  // a $1 book: always sane
  BinPackWriter w;
  w.add("g0_mid", "float64", mid);
  w.add("g0_state", "int8", state);
  w.add("phase_tag", "int8", phase);
  w.add("g0_spread_usd", "float64", (spread != nullptr) ? *spread : flat);
  char stem[512];
  std::snprintf(stem, sizeof(stem), "%s/%08d", dir.c_str(), date8);
  ASSERT_TRUE(w.write(stem, "QRSESS1", [](qr::futsess::JsonWriter&) {}).has_value());
}

void write_candidates(const std::string& stem, const char* asset,
                      const std::vector<Candidate>& rows) {
  std::vector<std::int64_t> id;
  std::vector<std::int32_t> d8, ds;
  std::vector<std::int8_t> sd;
  std::vector<double> at;
  for (const Candidate& c : rows) {
    id.push_back(c.cand_id);
    d8.push_back(c.date8);
    ds.push_back(c.dec_sec);
    sd.push_back(c.side);
    at.push_back(c.atr14_usd);
  }
  BinPackWriter w;
  w.add("cand_id", "int64", id);
  w.add("date8", "int32", d8);
  w.add("dec_sec", "int32", ds);
  w.add("side", "int8", sd);
  w.add("atr14_usd", "float64", at);
  ASSERT_TRUE(w.write(stem, "QRCAND1", [&](qr::futsess::JsonWriter& jw) {
                 jw.key("asset");
                 jw.value_string(asset);
               }).has_value());
}

/// A flat-then-shaped NKD session. NKD is the convenient asset for fixtures:
/// mult 5, tick 5.0, so one tick == $25 and every quantity is exact in binary.
struct Fixture {
  std::string dir;
  SessionView view;
};

Fixture make_fixture(const std::string& leaf, const std::vector<double>& mid,
                     const std::vector<std::int8_t>& state, std::int32_t phase_switch = -1) {
  Fixture f;
  f.dir = scratch(leaf);
  std::vector<std::int8_t> phase(mid.size(), 0);
  if (phase_switch >= 0) {
    for (std::size_t t = static_cast<std::size_t>(phase_switch); t < phase.size(); ++t) {
      phase[t] = 1;
    }
  }
  write_session(f.dir, 20240102, mid, state, phase);
  auto v = SessionView::load(f.dir, 20240102);
  EXPECT_TRUE(v.has_value());
  f.view = std::move(v).value();
  return f;
}

/// The independent direct scan the kernel must agree with, for the small
/// synthetic paths only (the corpus-scale oracle is the Python one).
std::int32_t brute_first_passage(const SessionView& s, std::int32_t anchor, std::int8_t side,
                                 double mult, double level, bool adverse) {
  const double entry = s.mid()[static_cast<std::size_t>(anchor)];
  for (std::size_t i = 0; i < s.vt().size(); ++i) {
    if (s.vt()[i] < anchor) {
      continue;
    }
    const double f = (s.vm()[i] - entry) * static_cast<double>(side) * mult + 0.0;
    if ((adverse ? -f : f) >= level) {
      return s.vt()[i];
    }
  }
  return -1;
}

// =========================================================== the ladder =====

TEST(Ladder, RungIsTickRoundedHalfUpAndScalesWithK) {
  // NKD: mult 5, tick_px 5.0 -> tick_usd 25. ATR $2500 gives a raw first rung
  // of 0.02*2500 = $50 = 10 price units = exactly 2 ticks.
  const AssetGeom& g = asset_geom(Asset::NKD);
  double ladder[kRungCount];
  ASSERT_TRUE(build_ladder(g, 2500.0, ladder).has_value());
  EXPECT_DOUBLE_EQ(ladder[0], 50.0);
  EXPECT_DOUBLE_EQ(ladder[1], 100.0);
  EXPECT_DOUBLE_EQ(ladder[kRungCount - 1], 50.0 * static_cast<double>(kRungCount));
  // HALF-UP, not truncation: a raw rung of 1.5 ticks must round UP to 2.
  // SI: mult 5000, tick 0.005. ATR chosen so 0.02*ATR/mult = 0.0075 px.
  const AssetGeom& si = asset_geom(Asset::SI);
  double l2[kRungCount];
  ASSERT_TRUE(build_ladder(si, 0.0075 * 5000.0 / 0.02, l2).has_value());
  EXPECT_DOUBLE_EQ(l2[0], 0.010 * 5000.0);
  // The ladder is non-decreasing in k, always.
  for (std::size_t k = 1; k < kRungCount; ++k) {
    EXPECT_LE(l2[k - 1], l2[k]);
  }
}

TEST(Ladder, RefusesAnAtrWhoseFirstRungRoundsToZeroTicksOrIsNotPositive) {
  const AssetGeom& g = asset_geom(Asset::NKD);
  double ladder[kRungCount];
  // 0.02 * 100 / 5 = 0.4 price units, which rounds to 0 on a 5.0 tick grid.
  EXPECT_FALSE(build_ladder(g, 100.0, ladder).has_value());
  EXPECT_FALSE(build_ladder(g, 0.0, ladder).has_value());
  EXPECT_FALSE(build_ladder(g, -1.0, ladder).has_value());
  EXPECT_FALSE(build_ladder(g, std::nan(""), ladder).has_value());
}

TEST(Ladder, TickDollarValueIsTickTimesMultForEveryAsset) {
  // A transcription slip in either column would silently rescale every rung.
  for (Asset a : {Asset::SI, Asset::HG, Asset::NKD}) {
    const AssetGeom& g = asset_geom(a);
    EXPECT_DOUBLE_EQ(g.tick_px * static_cast<double>(g.mult), g.tick_usd)
        << qr::futsess::asset_spec(a).name;
    EXPECT_EQ(g.mult, qr::futsess::asset_spec(a).mult);
    EXPECT_DOUBLE_EQ(g.tick_usd, qr::futsess::asset_spec(a).tick_usd);
  }
}

// ========================================================= the skeleton =====

TEST(Skeleton, FirstPassageIsTheFirstSecondTheRunningMaximumReachesTheRung) {
  // Path (NKD, $5/price-unit): up 10 units, back down, then up 30 units.
  std::vector<double> mid(600, 30000.0);
  for (std::size_t t = 100; t < 200; ++t) mid[t] = 30010.0;   // +$50
  for (std::size_t t = 200; t < 300; ++t) mid[t] = 29990.0;   // -$50
  for (std::size_t t = 300; t < 600; ++t) mid[t] = 30030.0;   // +$150
  std::vector<std::int8_t> state(600, 0);
  Fixture f = make_fixture("fp", mid, state);

  double ladder[kRungCount];
  ASSERT_TRUE(build_ladder(asset_geom(Asset::NKD), 2500.0, ladder).has_value());  // $50/rung
  ChunkScratch sc;
  RecordArrays recs;
  AnchorSkeleton a;
  ASSERT_TRUE(compute_anchor(f.view, asset_geom(Asset::NKD), 1, 0, ladder, sc, recs, &a)
                  .has_value());

  EXPECT_EQ(a.observed_secs, 600);
  EXPECT_EQ(a.tau_up[0], 100);  // $50 first reached at t=100
  EXPECT_EQ(a.tau_up[1], 300);  // $100 only at t=300
  EXPECT_EQ(a.tau_up[2], 300);  // $150 too
  EXPECT_EQ(a.tau_up[3], -1);   // $200 never
  EXPECT_EQ(a.tau_dn[0], 200);  // adverse $50 at t=200
  EXPECT_EQ(a.tau_dn[1], -1);
  // and the kernel agrees with a direct scan on every rung
  for (std::size_t k = 0; k < kRungCount; ++k) {
    EXPECT_EQ(a.tau_up[k], brute_first_passage(f.view, 0, 1, 5.0, ladder[k], false)) << k;
    EXPECT_EQ(a.tau_dn[k], brute_first_passage(f.view, 0, 1, 5.0, ladder[k], true)) << k;
  }
}

TEST(Skeleton, BothSidesAreRetainedEvenWhenOneBarrierWinsFirst) {
  // Adverse touches first and the favorable side touches later. The engine must
  // store BOTH times; resolving the race is the decode layer's job (CONV C10).
  std::vector<double> mid(400, 30000.0);
  for (std::size_t t = 50; t < 100; ++t) mid[t] = 29990.0;   // adverse $50 first
  for (std::size_t t = 100; t < 400; ++t) mid[t] = 30010.0;  // favorable $50 later
  std::vector<std::int8_t> state(400, 0);
  Fixture f = make_fixture("both", mid, state);
  double ladder[kRungCount];
  ASSERT_TRUE(build_ladder(asset_geom(Asset::NKD), 2500.0, ladder).has_value());
  ChunkScratch sc;
  RecordArrays recs;
  AnchorSkeleton a;
  ASSERT_TRUE(compute_anchor(f.view, asset_geom(Asset::NKD), 1, 0, ladder, sc, recs, &a)
                  .has_value());
  EXPECT_EQ(a.tau_dn[0], 50);
  EXPECT_EQ(a.tau_up[0], 100);
  const BarrierOutcome o = decode_barrier_cell(a, 1, 1);
  EXPECT_EQ(o.winner, BarrierWinner::kAdverse);
  EXPECT_TRUE(o.up_hit);   // the loser's time survives the decode
  EXPECT_EQ(o.tau_up_sec, 100);
}

TEST(Skeleton, ObservedSecsZeroMeansUnavailableAndIsNeverANoHit) {
  std::vector<double> mid(300, 30000.0);
  std::vector<std::int8_t> state(300, 0);
  state[150] = 5;  // the d1 anchor lands on a second with no two-sided book
  Fixture f = make_fixture("unavail", mid, state);
  double ladder[kRungCount];
  ASSERT_TRUE(build_ladder(asset_geom(Asset::NKD), 2500.0, ladder).has_value());
  ChunkScratch sc;
  RecordArrays recs;
  AnchorSkeleton a;
  ASSERT_TRUE(compute_anchor(f.view, asset_geom(Asset::NKD), 1, 150, ladder, sc, recs, &a)
                  .has_value());
  EXPECT_EQ(a.observed_secs, 0);
  EXPECT_EQ(a.anchor_sec, 150);
  EXPECT_TRUE(std::isnan(a.entry_mid));
  EXPECT_TRUE(std::isnan(a.mfe_usd));
  EXPECT_EQ(a.f_len, 0);
  EXPECT_EQ(a.tau_up[0], -1);
  EXPECT_FALSE(decode_barrier_cell(a, 1, 1).available);
  // and an available anchor with no touch is a DIFFERENT state: tau null but
  // observed_secs > 0.
  ASSERT_TRUE(compute_anchor(f.view, asset_geom(Asset::NKD), 1, 0, ladder, sc, recs, &a)
                  .has_value());
  EXPECT_GT(a.observed_secs, 0);
  EXPECT_EQ(a.tau_up[0], -1);
  EXPECT_TRUE(decode_barrier_cell(a, 1, 1).available);
}

TEST(Skeleton, PrefixMaximaRecordsAreStrictIncreasesAndNeverTheAnchorItself) {
  std::vector<double> mid(10, 30000.0);
  mid[1] = 30000.0;  // equal to the anchor: not a record
  mid[2] = 30010.0;
  mid[3] = 30010.0;  // equal to the running max: not a record
  mid[4] = 30020.0;
  for (std::size_t t = 5; t < 10; ++t) mid[t] = 30020.0;
  std::vector<std::int8_t> state(10, 0);
  Fixture f = make_fixture("recs", mid, state);
  double ladder[kRungCount];
  ASSERT_TRUE(build_ladder(asset_geom(Asset::NKD), 2500.0, ladder).has_value());
  ChunkScratch sc;
  RecordArrays recs;
  AnchorSkeleton a;
  ASSERT_TRUE(compute_anchor(f.view, asset_geom(Asset::NKD), 1, 0, ladder, sc, recs, &a)
                  .has_value());
  ASSERT_EQ(a.f_len, 2);
  EXPECT_EQ(recs.f_t[0], 2);
  EXPECT_EQ(recs.f_t[1], 4);
  EXPECT_FLOAT_EQ(recs.f_v[0], 50.0f);
  EXPECT_FLOAT_EQ(recs.f_v[1], 100.0f);
  EXPECT_EQ(a.mfe_usd, 100.0);
  EXPECT_EQ(a.mfe_argmax_sec, 4);
  EXPECT_EQ(a.time_to_peak_secs, 4);
}

TEST(Skeleton, RecordValuesAreStoredFloat32ButEveryComparisonIsFloat64) {
  // Two consecutive prefix maxima that COLLIDE in float32 but straddle a rung
  // in float64. Searching the stored float32 copy would resolve the rung to the
  // earlier record; searching the float64 values resolves it to the later one,
  // which is what a direct scan of the path says.
  // NKD (mult 5): f = (mid - entry) * 5. entry 30000.
  //   mid 30000 + 19999999.5 -> f = 99999997.5
  //   mid 30000 + 20000000.0 -> f = 100000000.0
  // Both round to the float32 value 1e8 (its ulp there is 8), and rung 200 of
  // an ATR of $2.5e7 is exactly $100,000,000.
  std::vector<double> mid(10, 30000.0);
  std::vector<std::int8_t> state(10, 0);
  mid[2] = 30000.0 + 19999999.5;
  for (std::size_t t = 4; t < 10; ++t) mid[t] = 30000.0 + 20000000.0;
  Fixture f = make_fixture("f32", mid, state);
  double ladder[kRungCount];
  ASSERT_TRUE(build_ladder(asset_geom(Asset::NKD), 2.5e7, ladder).has_value());
  ASSERT_DOUBLE_EQ(ladder[kRungCount - 1], 1e8);
  ChunkScratch sc;
  RecordArrays recs;
  AnchorSkeleton a;
  ASSERT_TRUE(compute_anchor(f.view, asset_geom(Asset::NKD), 1, 0, ladder, sc, recs, &a)
                  .has_value());
  ASSERT_EQ(a.f_len, 2);
  EXPECT_EQ(recs.f_t[0], 2);
  EXPECT_EQ(recs.f_t[1], 4);
  // the STORED values collide ...
  EXPECT_EQ(recs.f_v[0], recs.f_v[1]);
  // ... and the search that produced tau still separated them, agreeing with a
  // direct scan of the path.
  EXPECT_EQ(a.tau_up[kRungCount - 1], 4);
  EXPECT_EQ(a.tau_up[kRungCount - 1],
            brute_first_passage(f.view, 0, 1, 5.0, ladder[kRungCount - 1], false));
}

TEST(Skeleton, HorizonMarksNeverCrossTheSessionEndAndTakeTheLastObservation) {
  // The path STEPS at the 30-minute mark and that very second is unavailable,
  // so "last observation at or before the mark" and "first observation after
  // it" give different answers. The mark takes the earlier one.
  std::vector<double> mid(4000, 30000.0);
  for (std::size_t t = 100; t < 1800; ++t) mid[t] = 30010.0;   // +$50
  for (std::size_t t = 1800; t < 4000; ++t) mid[t] = 30020.0;  // +$100
  std::vector<std::int8_t> state(4000, 0);
  state[1800] = 5;  // the 30m mark's own second has no two-sided book
  Fixture f = make_fixture("marks", mid, state, /*phase_switch=*/2500);
  double ladder[kRungCount];
  ASSERT_TRUE(build_ladder(asset_geom(Asset::NKD), 2500.0, ladder).has_value());
  ChunkScratch sc;
  RecordArrays recs;
  AnchorSkeleton a;
  ASSERT_TRUE(compute_anchor(f.view, asset_geom(Asset::NKD), 1, 0, ladder, sc, recs, &a)
                  .has_value());
  EXPECT_DOUBLE_EQ(a.f_mark[0], 50.0);   // 30m = t 1800 -> the t 1799 observation
  EXPECT_DOUBLE_EQ(a.f_mark[1], 100.0);  // 60m = t 3600
  EXPECT_TRUE(std::isnan(a.f_mark[2]));  // 120m = t 7200 is past the close
  EXPECT_EQ(a.phase_close_sec, 2500);
  EXPECT_DOUBLE_EQ(a.f_mark[3], 100.0);
  EXPECT_EQ(a.sess_close_sec, 3999);
  EXPECT_DOUBLE_EQ(a.f_mark[4], 100.0);
}

TEST(Skeleton, MaeBeforeArgmaxIgnoresAdversityAfterThePeak) {
  std::vector<double> mid(500, 30000.0);
  for (std::size_t t = 50; t < 100; ++t) mid[t] = 29990.0;   // -$50 before peak
  for (std::size_t t = 100; t < 200; ++t) mid[t] = 30020.0;  // peak +$100
  for (std::size_t t = 200; t < 500; ++t) mid[t] = 29960.0;  // -$200 AFTER peak
  std::vector<std::int8_t> state(500, 0);
  Fixture f = make_fixture("mae", mid, state);
  double ladder[kRungCount];
  ASSERT_TRUE(build_ladder(asset_geom(Asset::NKD), 2500.0, ladder).has_value());
  ChunkScratch sc;
  RecordArrays recs;
  AnchorSkeleton a;
  ASSERT_TRUE(compute_anchor(f.view, asset_geom(Asset::NKD), 1, 0, ladder, sc, recs, &a)
                  .has_value());
  EXPECT_DOUBLE_EQ(a.mfe_usd, 100.0);
  EXPECT_EQ(a.mfe_argmax_sec, 100);
  EXPECT_DOUBLE_EQ(a.mae_before_argmax_usd, 50.0);   // only the pre-peak dip
  EXPECT_DOUBLE_EQ(a.mae_unwalled_usd, 200.0);       // the whole window
}

TEST(Skeleton, GivebackIsThePeakMinusThePostPeakMinimumNotTheTerminalValue) {
  std::vector<double> mid(500, 30000.0);
  for (std::size_t t = 100; t < 200; ++t) mid[t] = 30020.0;  // peak +$100
  for (std::size_t t = 200; t < 300; ++t) mid[t] = 29980.0;  // trough -$100
  for (std::size_t t = 300; t < 500; ++t) mid[t] = 30010.0;  // recovers to +$50
  std::vector<std::int8_t> state(500, 0);
  Fixture f = make_fixture("give", mid, state);
  double ladder[kRungCount];
  ASSERT_TRUE(build_ladder(asset_geom(Asset::NKD), 2500.0, ladder).has_value());
  ChunkScratch sc;
  RecordArrays recs;
  AnchorSkeleton a;
  ASSERT_TRUE(compute_anchor(f.view, asset_geom(Asset::NKD), 1, 0, ladder, sc, recs, &a)
                  .has_value());
  EXPECT_DOUBLE_EQ(a.giveback_post_peak_usd, 200.0);  // 100 - (-100)
  EXPECT_DOUBLE_EQ(a.f_terminal_usd, 50.0);           // the terminal is separate
}

TEST(Skeleton, MonotonicityCountsSTRICTLYFavorableOneMinuteSteps) {
  // 5 minutes of path: up, flat, up, down, flat -> 2 favorable of 5 steps.
  std::vector<double> mid(400, 30000.0);
  for (std::size_t t = 60; t < 400; ++t) mid[t] = 30010.0;
  for (std::size_t t = 180; t < 400; ++t) mid[t] = 30020.0;
  for (std::size_t t = 240; t < 400; ++t) mid[t] = 30005.0;
  std::vector<std::int8_t> state(400, 0);
  Fixture f = make_fixture("mono", mid, state);
  double ladder[kRungCount];
  ASSERT_TRUE(build_ladder(asset_geom(Asset::NKD), 2500.0, ladder).has_value());
  ChunkScratch sc;
  RecordArrays recs;
  AnchorSkeleton a;
  ASSERT_TRUE(compute_anchor(f.view, asset_geom(Asset::NKD), 1, 0, ladder, sc, recs, &a)
                  .has_value());
  EXPECT_EQ(a.mono_steps, 6);  // (399 - 0) / 60
  EXPECT_DOUBLE_EQ(a.monotonicity, 2.0 / 6.0);
}

TEST(Skeleton, TimeUnderwaterCountsStrictlyNegativeSecondsOnly) {
  std::vector<double> mid(300, 30000.0);
  for (std::size_t t = 100; t < 150; ++t) mid[t] = 29995.0;  // 50 seconds < 0
  std::vector<std::int8_t> state(300, 0);
  Fixture f = make_fixture("uw", mid, state);
  double ladder[kRungCount];
  ASSERT_TRUE(build_ladder(asset_geom(Asset::NKD), 2500.0, ladder).has_value());
  ChunkScratch sc;
  RecordArrays recs;
  AnchorSkeleton a;
  ASSERT_TRUE(compute_anchor(f.view, asset_geom(Asset::NKD), 1, 0, ladder, sc, recs, &a)
                  .has_value());
  EXPECT_EQ(a.time_underwater_secs, 50);  // the 250 flat seconds are NOT underwater
  EXPECT_DOUBLE_EQ(a.uw_share, 50.0 / 300.0);
}

TEST(Skeleton, ShortSideExcursionIsMeasuredAgainstTheSideAndCarriesNoNegativeZero) {
  std::vector<double> mid(200, 30000.0);
  for (std::size_t t = 100; t < 200; ++t) mid[t] = 29990.0;  // price DOWN
  std::vector<std::int8_t> state(200, 0);
  Fixture f = make_fixture("short", mid, state);
  double ladder[kRungCount];
  ASSERT_TRUE(build_ladder(asset_geom(Asset::NKD), 2500.0, ladder).has_value());
  ChunkScratch sc;
  RecordArrays recs;
  AnchorSkeleton a;
  ASSERT_TRUE(compute_anchor(f.view, asset_geom(Asset::NKD), -1, 0, ladder, sc, recs, &a)
                  .has_value());
  EXPECT_DOUBLE_EQ(a.mfe_usd, 50.0);  // down IS favorable for a short
  EXPECT_EQ(a.tau_up[0], 100);
  EXPECT_EQ(a.tau_dn[0], -1);

  // CONV C4: no emitted field may carry -0.0, or byte-exact parity against the
  // oracle is undefined. For a SHORT the excursion at any second whose mid
  // equals the entry is (0) * -1 * mult = -0.0, so the fields that read the
  // path DIRECTLY -- the terminal value and the marks -- are where it surfaces.
  // This path returns exactly to the entry at the close.
  std::vector<double> back(200, 30000.0);
  for (std::size_t t = 50; t < 150; ++t) back[t] = 29990.0;
  Fixture f2 = make_fixture("short_back", back, state);
  ASSERT_TRUE(compute_anchor(f2.view, asset_geom(Asset::NKD), -1, 0, ladder, sc, recs, &a)
                  .has_value());
  EXPECT_DOUBLE_EQ(a.f_terminal_usd, 0.0);
  EXPECT_FALSE(std::signbit(a.f_terminal_usd)) << "f_terminal_usd carries -0.0";
  EXPECT_FALSE(std::signbit(a.f_mark[4])) << "the session-close mark carries -0.0";
  EXPECT_FALSE(std::signbit(a.f_mark[3])) << "the phase-close mark carries -0.0";
  EXPECT_FALSE(std::signbit(a.mae_unwalled_usd));
  EXPECT_FALSE(std::signbit(a.giveback_post_peak_usd));
  // the long side of the same path must agree numerically and in sign of zero
  ASSERT_TRUE(compute_anchor(f2.view, asset_geom(Asset::NKD), 1, 0, ladder, sc, recs, &a)
                  .has_value());
  EXPECT_FALSE(std::signbit(a.f_terminal_usd));
}

// ========================================================= CC-M1-4 mask =====

TEST(MidSanity, AWideBookSecondIsExcludedFromEveryMidConsumer) {
  // D-054's finding, in miniature: the book blows out for 30 seconds and the
  // MID prints a $1,000 excursion that never traded. With the mask off the
  // engine reports it as MFE; with the mask on the seconds are typed-excluded
  // and the excursion disappears -- it is not interpolated, it is absent.
  const std::string dir = scratch("sanity");
  std::vector<double> mid(400, 30000.0);
  std::vector<std::int8_t> state(400, 0);
  std::vector<std::int8_t> phase(400, 0);
  std::vector<double> spread(400, 20.0);          // a normal $20 book
  for (std::size_t t = 100; t < 130; ++t) {
    mid[t] = 30200.0;                             // +$1,000 of phantom travel
    spread[t] = 900.0;                            // on a 45x-median book
  }
  write_session(dir, 20240102, mid, state, phase, &spread);

  double ladder[kRungCount];
  ASSERT_TRUE(build_ladder(asset_geom(Asset::NKD), 2500.0, ladder).has_value());
  ChunkScratch sc;
  RecordArrays recs;
  AnchorSkeleton a;

  auto off = SessionView::load(dir, 20240102);
  ASSERT_TRUE(off.has_value());
  EXPECT_EQ(off.value().n_insane(), 0);
  EXPECT_EQ(off.value().vt().size(), 400u);
  ASSERT_TRUE(compute_anchor(off.value(), asset_geom(Asset::NKD), 1, 0, ladder, sc, recs, &a)
                  .has_value());
  EXPECT_DOUBLE_EQ(a.mfe_usd, 1000.0);
  EXPECT_EQ(a.tau_up[0], 100);

  SanityPolicy pol;
  pol.enabled = true;
  pol.phase_median_spread_usd[0] = 20.0;  // ceiling = min(10*20, 500) = $200
  pol.phase_median_spread_usd[1] = 20.0;
  pol.phase_median_spread_usd[2] = 20.0;
  auto on = SessionView::load(dir, 20240102, pol);
  ASSERT_TRUE(on.has_value());
  EXPECT_EQ(on.value().n_insane(), 30);
  EXPECT_EQ(on.value().n_two_sided(), 400);
  EXPECT_EQ(on.value().vt().size(), 370u);
  ASSERT_TRUE(compute_anchor(on.value(), asset_geom(Asset::NKD), 1, 0, ladder, sc, recs, &a)
                  .has_value());
  EXPECT_DOUBLE_EQ(a.mfe_usd, 0.0);      // the phantom leg is gone
  EXPECT_EQ(a.tau_up[0], -1);
  EXPECT_EQ(a.observed_secs, 370);       // masked, never interpolated
}

TEST(MidSanity, AnAnchorOnAnInsaneSecondIsUnavailableNotMerelyTwoSided) {
  const std::string dir = scratch("sanity_anchor");
  std::vector<double> mid(300, 30000.0);
  std::vector<std::int8_t> state(300, 0);
  std::vector<std::int8_t> phase(300, 0);
  std::vector<double> spread(300, 20.0);
  spread[150] = 600.0;  // two-sided, but far outside the ceiling
  write_session(dir, 20240102, mid, state, phase, &spread);
  SanityPolicy pol;
  pol.enabled = true;
  for (std::size_t k = 0; k < kPhaseCount; ++k) pol.phase_median_spread_usd[k] = 20.0;
  auto v = SessionView::load(dir, 20240102, pol);
  ASSERT_TRUE(v.has_value());
  EXPECT_EQ(v.value().state()[150], 0);            // still TWO_SIDED ...
  EXPECT_FALSE(v.value().is_valid_second(150));    // ... and still not usable
  double ladder[kRungCount];
  ASSERT_TRUE(build_ladder(asset_geom(Asset::NKD), 2500.0, ladder).has_value());
  ChunkScratch sc;
  RecordArrays recs;
  AnchorSkeleton a;
  ASSERT_TRUE(compute_anchor(v.value(), asset_geom(Asset::NKD), 1, 150, ladder, sc, recs, &a)
                  .has_value());
  EXPECT_EQ(a.observed_secs, 0);
  EXPECT_TRUE(std::isnan(a.entry_mid));
}

TEST(MidSanity, TheCeilingIsTenTimesTheMedianCappedAtFiveHundredAndIsInclusive) {
  SanityPolicy pol;
  pol.enabled = true;
  pol.phase_median_spread_usd[0] = 20.0;   // 10x = 200 < 500 -> the median binds
  pol.phase_median_spread_usd[1] = 80.0;   // 10x = 800 > 500 -> the CAP binds
  pol.phase_median_spread_usd[2] = 50.0;   // 10x = 500 == the cap
  EXPECT_DOUBLE_EQ(pol.threshold_usd(0), 200.0);
  EXPECT_DOUBLE_EQ(pol.threshold_usd(1), 500.0);
  EXPECT_DOUBLE_EQ(pol.threshold_usd(2), 500.0);
  SanityPolicy off;
  EXPECT_TRUE(std::isinf(off.threshold_usd(0)));

  // inclusive at the boundary, excluded one cent above it
  const std::string dir = scratch("sanity_edge");
  std::vector<double> mid(10, 30000.0);
  std::vector<std::int8_t> state(10, 0);
  std::vector<std::int8_t> phase(10, 0);
  std::vector<double> spread(10, 20.0);
  spread[3] = 200.0;
  spread[4] = 200.01;
  write_session(dir, 20240102, mid, state, phase, &spread);
  auto v = SessionView::load(dir, 20240102, pol);
  ASSERT_TRUE(v.has_value());
  EXPECT_TRUE(v.value().is_valid_second(3));
  EXPECT_FALSE(v.value().is_valid_second(4));
  EXPECT_EQ(v.value().n_insane(), 1);
}

// ============================================================ the decode ====

TEST(Query, SimultaneousTouchResolvesAdverseAndKeepsTheAmbiguityTyping) {
  AnchorSkeleton a{};
  a.observed_secs = 10;
  for (std::size_t k = 0; k < kRungCount; ++k) {
    a.tau_up[k] = -1;
    a.tau_dn[k] = -1;
  }
  a.tau_up[0] = 500;
  a.tau_dn[0] = 500;
  const BarrierOutcome o = decode_barrier_cell(a, 1, 1);
  EXPECT_EQ(o.winner, BarrierWinner::kAdverse);
  EXPECT_TRUE(o.same_second_ambiguous);
  EXPECT_TRUE(o.up_hit);
  EXPECT_TRUE(o.dn_hit);
  a.tau_dn[0] = 501;
  const BarrierOutcome o2 = decode_barrier_cell(a, 1, 1);
  EXPECT_EQ(o2.winner, BarrierWinner::kFavorable);
  EXPECT_FALSE(o2.same_second_ambiguous);
  // asymmetric cells are free: rung 1 up against rung 200 down
  EXPECT_EQ(decode_barrier_cell(a, 1, kRungCount).winner, BarrierWinner::kFavorable);
  EXPECT_EQ(decode_barrier_cell(a, kRungCount, 1).winner, BarrierWinner::kAdverse);
}

// ========================================================= the structure ====

TEST(Structure, MoreQueriedBarrierCellsDoNotIncreaseStoredRowsOrBytes) {
  const std::string sdir = scratch("struct_sessions");
  std::vector<double> mid(2000, 30000.0);
  for (std::size_t t = 500; t < 2000; ++t) mid[t] = 30030.0;
  std::vector<std::int8_t> state(2000, 0);
  std::vector<std::int8_t> phase(2000, 0);
  write_session(sdir, 20240102, mid, state, phase);
  const std::string odir = scratch("struct_out");
  const std::string cstem = odir + "/cands";
  std::vector<Candidate> rows;
  for (int i = 0; i < 40; ++i) {
    rows.push_back(Candidate{i, 20240102, 10 * i, (i % 2 == 0) ? std::int8_t{1} : std::int8_t{-1},
                             2500.0});
  }
  write_candidates(cstem, "NKD", rows);
  auto set = CandidateSet::load(cstem);
  ASSERT_TRUE(set.has_value());
  ShardOptions opt;
  opt.asset = Asset::NKD;
  opt.session_dir = sdir;
  opt.out_stem = odir + "/NKD_202401";
  opt.month = "202401";
  auto st = build_shard(set.value(), 0, set.value().rows.size(), opt);
  ASSERT_TRUE(st.has_value());
  EXPECT_EQ(st.value().stored_rows, 40);
  const auto bytes_before = std::filesystem::file_size(opt.out_stem + ".bin");

  // Load the shard back and query an ever-larger set of barrier cells. The
  // recovered law: "increasing barrier cells does not increase physical row
  // count" (LABEL_ATLAS_V2 §3.2.7).
  auto pack = BinPack::load(opt.out_stem, "QRSKEL1");
  ASSERT_TRUE(pack.has_value());
  auto tau_up = pack.value().get<std::int32_t>("a0_tau_up", "int32");
  auto tau_dn = pack.value().get<std::int32_t>("a0_tau_dn", "int32");
  auto obs = pack.value().get<std::int32_t>("a0_observed_secs", "int32");
  ASSERT_TRUE(tau_up.has_value());
  ASSERT_TRUE(tau_dn.has_value());
  ASSERT_TRUE(obs.has_value());
  // FIXED SHAPE: exactly kRungCount cells per row per side, never data-dependent.
  EXPECT_EQ(tau_up.value().size(), 40u * kRungCount);
  EXPECT_EQ(tau_dn.value().size(), 40u * kRungCount);

  std::int64_t decoded = 0;
  for (std::size_t cells : {std::size_t{1}, std::size_t{100}, kRungCount * kRungCount}) {
    AnchorSkeleton a{};
    a.observed_secs = obs.value()[0];
    for (std::size_t k = 0; k < kRungCount; ++k) {
      a.tau_up[k] = tau_up.value()[k];
      a.tau_dn[k] = tau_dn.value()[k];
    }
    for (std::size_t c = 0; c < cells; ++c) {
      const std::size_t up = (c % kRungCount) + 1;
      const std::size_t dn = (c / kRungCount) % kRungCount + 1;
      decoded += static_cast<std::int64_t>(decode_barrier_cell(a, up, dn).winner);
    }
    EXPECT_EQ(std::filesystem::file_size(opt.out_stem + ".bin"), bytes_before);
  }
  EXPECT_NE(decoded, std::numeric_limits<std::int64_t>::min());  // the sweep ran
}

TEST(Structure, BoundedChunkingNeverHoldsMoreThanOneChunkOfAnchorRows) {
  const std::string sdir = scratch("chunk_sessions");
  std::vector<double> mid(2000, 30000.0);
  std::vector<std::int8_t> state(2000, 0);
  std::vector<std::int8_t> phase(2000, 0);
  write_session(sdir, 20240102, mid, state, phase);
  const std::string odir = scratch("chunk_out");
  const std::string cstem = odir + "/cands";
  std::vector<Candidate> rows;
  for (int i = 0; i < 100; ++i) {
    rows.push_back(Candidate{i, 20240102, 5 * i, 1, 2500.0});
  }
  write_candidates(cstem, "NKD", rows);
  auto set = CandidateSet::load(cstem);
  ASSERT_TRUE(set.has_value());
  ShardOptions opt;
  opt.asset = Asset::NKD;
  opt.session_dir = sdir;
  opt.out_stem = odir + "/NKD_202401";
  opt.month = "202401";
  opt.chunk_candidates = 8;
  auto st = build_shard(set.value(), 0, set.value().rows.size(), opt);
  ASSERT_TRUE(st.has_value());
  EXPECT_EQ(st.value().stored_rows, 100);
  EXPECT_LE(st.value().max_live_anchor_rows,
            static_cast<std::int64_t>(opt.chunk_candidates * kAnchorCount));
  // and the bounded-execution law is enforced, not merely observed
  opt.chunk_candidates = kChunkCandidatesMax + 1;
  EXPECT_FALSE(build_shard(set.value(), 0, set.value().rows.size(), opt).has_value());
}

TEST(Structure, TwoRunsOfTheSameShardAreByteIdentical) {
  const std::string sdir = scratch("ident_sessions");
  std::vector<double> mid(3000, 30000.0);
  for (std::size_t t = 0; t < 3000; ++t) {
    mid[t] = 30000.0 + 5.0 * static_cast<double>((t * 7919) % 13);
  }
  std::vector<std::int8_t> state(3000, 0);
  std::vector<std::int8_t> phase(3000, 0);
  write_session(sdir, 20240102, mid, state, phase);
  const std::string odir = scratch("ident_out");
  const std::string cstem = odir + "/cands";
  std::vector<Candidate> rows;
  for (int i = 0; i < 50; ++i) {
    rows.push_back(Candidate{i, 20240102, 13 * i, (i % 3 == 0) ? std::int8_t{-1} : std::int8_t{1},
                             2500.0});
  }
  write_candidates(cstem, "NKD", rows);
  auto set = CandidateSet::load(cstem);
  ASSERT_TRUE(set.has_value());
  auto run = [&](const std::string& stem) {
    ShardOptions opt;
    opt.asset = Asset::NKD;
    opt.session_dir = sdir;
    opt.out_stem = stem;
    opt.month = "202401";
    EXPECT_TRUE(build_shard(set.value(), 0, set.value().rows.size(), opt).has_value());
    std::FILE* fh = std::fopen((stem + ".bin").c_str(), "rb");
    std::string all;
    char buf[4096];
    std::size_t got = 0;
    while ((got = std::fread(buf, 1, sizeof(buf), fh)) != 0) {
      all.append(buf, got);
    }
    std::fclose(fh);
    std::FILE* jh = std::fopen((stem + ".json").c_str(), "rb");
    while ((got = std::fread(buf, 1, sizeof(buf), jh)) != 0) {
      all.append(buf, got);
    }
    std::fclose(jh);
    return all;
  };
  // The SAME stem is rebuilt twice: a differing stem would differ in the
  // sidecar's "bin" member for a reason that has nothing to do with determinism.
  const std::string first = run(odir + "/run_same");
  const std::string second = run(odir + "/run_same");
  EXPECT_EQ(first, second);
  EXPECT_FALSE(first.empty());
}

// =============================================================== receipts ===

TEST(Candidates, RefusesACandidateFileWhoseDateColumnGoesBackwards) {
  const std::string odir = scratch("cand_order");
  const std::string cstem = odir + "/cands";
  write_candidates(cstem, "NKD",
                   {Candidate{0, 20240103, 10, 1, 2500.0}, Candidate{1, 20240102, 10, 1, 2500.0}});
  EXPECT_FALSE(CandidateSet::load(cstem).has_value());
  write_candidates(cstem, "NKD",
                   {Candidate{0, 20240102, 10, 1, 2500.0}, Candidate{1, 20240102, 20, 1, 2500.0},
                    Candidate{2, 20240103, 5, -1, 2500.0}});
  EXPECT_TRUE(CandidateSet::load(cstem).has_value());
}

TEST(BinPack, RefusesADescriptorThatRunsPastTheEndOfTheBlob) {
  const std::string odir = scratch("binpack");
  const std::string stem = odir + "/trunc";
  write_candidates(stem, "NKD", {Candidate{0, 20240102, 10, 1, 2500.0}});
  // Truncate the blob under a sidecar that still claims the full length.
  std::filesystem::resize_file(stem + ".bin", 4);
  EXPECT_FALSE(BinPack::load(stem, "QRCAND1").has_value());
  EXPECT_FALSE(BinPack::load(stem, "QRSESS1").has_value());  // wrong format tag too
}

TEST(Params, CanonicalJsonHasSortedKeysAndAShortestRoundTripFloat) {
  const std::string j = params_canonical_json(Asset::SI, 512);
  EXPECT_EQ(j,
            "{\"anchor_count\":2,\"anchor_d1_delay_secs\":60,\"asset\":\"SI\","
            "\"chunk_candidates\":512,\"horizon_secs\":[1800,3600,7200],\"rung_count\":200,"
            "\"rung_step\":0.02,\"spec_sha16\":\"2b83f9e70340a413\"}");
  EXPECT_EQ(j.find(' '), std::string::npos);
  EXPECT_EQ(params_hash(Asset::SI, 512).size(), 64u);
  EXPECT_NE(params_hash(Asset::SI, 512), params_hash(Asset::NKD, 512));
}

TEST(Params, TheFrozenSpecShaIsCheckedAgainstTheFileNotMerelyDeclared) {
  auto got = file_sha16(QR_M1B_SPEC_PATH);
  ASSERT_TRUE(got.has_value()) << "cannot read " << QR_M1B_SPEC_PATH;
  EXPECT_EQ(got.value(), std::string(spec_sha16_pin()));
}

}  // namespace
