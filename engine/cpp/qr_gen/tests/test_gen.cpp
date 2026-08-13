// qr_gen test suite — RED-FIRST (FINAL_PLAN §6 red-ledger law).
//
// Every test here has a committed mutant under tests/mutants/MG*.patch and a
// committed red log proving it can fail. A green test with no proof that it
// can go red is worth nothing.
//
// The tests exercise the LAWS, not the corpus: the ZigZag's confirmation rule
// and its floors, the ADDITIVE FAST-OPEN family and its half-open window, the
// dedup contract, the level arm/touch/re-arm machine, the 15-minute outcome
// window, the 30-minute reclaim bound, the family-bit layout, and the frozen
// spec pins. The whole-corpus candidate-exact differential against the S1-v2
// Python oracle lives in engine/port_m1b/compare_gen.py.
#include <gtest/gtest.h>

#include <cmath>
#include <cstdio>
#include <string>
#include <vector>

#include "qr_gen/calendar.hpp"
#include "qr_gen/families.hpp"
#include "qr_gen/generate.hpp"
#include "qr_gen/levels.hpp"
#include "qr_gen/tables.hpp"
#include "qr_skel/engine.hpp"
#include "qr_skel/geom.hpp"

namespace {

using namespace qr::gen;  // NOLINT(build/namespaces) — test-local
using qr::futsess::Asset;

std::vector<std::int32_t> iota_secs(std::size_t n) {
  std::vector<std::int32_t> v(n);
  for (std::size_t i = 0; i < n; ++i) {
    v[i] = static_cast<std::int32_t>(i);
  }
  return v;
}

}  // namespace

// ==================================================================== ZigZag ==
TEST(ZigZag, ConfirmationIsTheFirstSecondTheRetraceREACHESTheThreshold) {
  // Rises to 106 by second 4, holds, then retraces. With a threshold of exactly
  // 2.0 the HIGH confirms at the FIRST second whose retrace REACHES 2.0.
  const std::vector<std::int32_t> secs = iota_secs(8);
  const std::vector<double> mids = {100, 100, 103, 105, 106, 106, 105, 104};
  const std::vector<double> thr(8, 2.0);
  const auto piv = zigzag_scan(secs, mids, thr);
  ASSERT_EQ(piv.size(), 2u);
  EXPECT_EQ(piv[0].side, 1);           // the opening leg confirms the LOW first
  EXPECT_EQ(piv[0].conf_sec, 2);
  EXPECT_EQ(piv[1].side, -1);          // a confirmed HIGH -> SHORT
  EXPECT_EQ(piv[1].pivot_sec, 4);      // the extreme kept its FIRST second
  EXPECT_EQ(piv[1].conf_sec, 7);       // 106 - 104 == 2.0 exactly: reached
}

TEST(ZigZag, TheExtremeKeepsTheFIRSTSecondItWasReached) {
  const std::vector<std::int32_t> secs = iota_secs(6);
  // The high 110 is reached at second 2 and touched again at second 4; the
  // pivot second must stay 2 (a repeat of the extreme is not a new extreme).
  const std::vector<double> mids = {100, 100, 110, 109, 110, 107};
  const std::vector<double> thr(6, 3.0);
  const auto piv = zigzag_scan(secs, mids, thr);
  ASSERT_EQ(piv.size(), 2u);
  EXPECT_EQ(piv[1].side, -1);
  EXPECT_EQ(piv[1].pivot_sec, 2);
  EXPECT_EQ(piv[1].conf_sec, 5);
}

TEST(ZigZag, ThresholdIsReadAtTheCONFIRMATIONSecondsOwnPhase) {
  // The retrace reaches 2 at second 3 but that second's threshold is 5; it only
  // confirms at second 5, where the phase's threshold has dropped to 2.
  const std::vector<std::int32_t> secs = iota_secs(6);
  const std::vector<double> mids = {100, 100, 110, 108, 107, 107};
  const std::vector<double> thr = {5.0, 5.0, 5.0, 5.0, 5.0, 2.0};
  const auto piv = zigzag_scan(secs, mids, thr);
  ASSERT_EQ(piv.size(), 2u);
  EXPECT_EQ(piv[1].side, -1);
  EXPECT_EQ(piv[1].conf_sec, 5);
}

TEST(ZigZag, RungThresholdTakesTheFLOORSAndRoundsHalfUpToTheTick) {
  const qr::skel::AssetGeom& g = qr::skel::asset_geom(Asset::SI);  // mult 5000, tick $25
  // 0.05 x $2,000 = $100 beats both floors (4 ticks = $100 ties, 2 x median
  // spread = $50) -> $100 / 5000 = 0.02 price units, already on the tick grid.
  EXPECT_DOUBLE_EQ(rung_threshold_px(g, 0.05, 2000.0, 25.0), 0.02);
  // A tiny ATR is floored by 4 ticks = $100, never by the ATR term.
  EXPECT_DOUBLE_EQ(rung_threshold_px(g, 0.05, 10.0, 25.0), 0.02);
  // A wide book floors by 2 x median spread = $400 -> 0.08 price units.
  EXPECT_DOUBLE_EQ(rung_threshold_px(g, 0.05, 10.0, 200.0), 0.08);
  // HALF-UP onto the tick: $2,001 x 0.05 = $100.05 -> 0.02001 -> 0.02.
  EXPECT_DOUBLE_EQ(rung_threshold_px(g, 0.05, 2001.0, 25.0), 0.02);
  // A missing phase median drops the spread floor entirely (never NaN).
  EXPECT_DOUBLE_EQ(rung_threshold_px(g, 0.05, 2000.0, std::nan("")), 0.02);
}

// ================================================================= FAST-OPEN ==
TEST(FastOpen, TheWindowIsHalfOpenAndMeasuredFromTheLastOpenAtOrBeforeIt) {
  const std::vector<std::int32_t> opens = {0, 1000, 5000};
  EXPECT_TRUE(in_fast_open(0, opens));
  EXPECT_TRUE(in_fast_open(299, opens));
  EXPECT_FALSE(in_fast_open(300, opens));   // exactly 300s after: OUTSIDE
  EXPECT_FALSE(in_fast_open(999, opens));
  EXPECT_TRUE(in_fast_open(1000, opens));
  EXPECT_TRUE(in_fast_open(1299, opens));
  EXPECT_FALSE(in_fast_open(1300, opens));
}

TEST(FastOpen, IsADDITIVEAndNeverReplacesTheTauStarCandidate) {
  // CC-M1-5 D13: a confirmation inside an open window emits BOTH the tau*
  // candidate and the 15s one, under separate family tags.
  const std::vector<Confirmation> confs = {{100, 1, 0b0010}};
  const std::vector<std::int32_t> opens = {0};
  const auto em = g1_emissions(confs, opens);
  ASSERT_EQ(em.size(), 2u);
  EXPECT_EQ(em[0].dec_sec, 100 + kTauStar);
  EXPECT_EQ(em[0].fam_bits, kFamG1);
  EXPECT_EQ(em[1].dec_sec, 100 + kFastOpenDelay);
  EXPECT_EQ(em[1].fam_bits, kFamG1FastOpen);
  // Outside the window only the tau* candidate exists.
  const auto em2 = g1_emissions({{5000, 1, 0b0010}}, opens);
  ASSERT_EQ(em2.size(), 1u);
  EXPECT_EQ(em2[0].dec_sec, 5000 + kTauStar);
}

TEST(FastOpen, TheFineRungTagsG1FineAndTheCoarseRungsTagG1) {
  const auto only_fine = g1_emissions({{100, 1, kFineBit}}, {});
  ASSERT_EQ(only_fine.size(), 1u);
  EXPECT_EQ(only_fine[0].fam_bits, kFamG1Fine);
  const auto both = g1_emissions({{100, 1, 0b0011}}, {});
  ASSERT_EQ(both.size(), 1u);
  EXPECT_EQ(both[0].fam_bits, static_cast<std::uint8_t>(kFamG1 | kFamG1Fine));
  EXPECT_EQ(both[0].rung_mask, 0b0011);
}

// ===================================================================== dedup ==
TEST(Dedup, UnionsTheTagsAndKeepsTheEARLIESTConfirmationSecond) {
  std::vector<Emission> in = {
      Emission{500, 1, kFamG1, 0, 0b0110, 380},
      Emission{500, 1, kFamG2Reject, 0b000010, 0, 300},
      Emission{500, -1, kFamG1, 0, 0b1000, 380},
      Emission{400, 1, kFamG1Fine, 0, 0b0001, 280},
  };
  const auto out = dedup(in);
  ASSERT_EQ(out.size(), 3u);
  // Ordered by (dec_sec, side): 400/+1, then 500/-1, then 500/+1.
  EXPECT_EQ(out[0].dec_sec, 400);
  EXPECT_EQ(out[1].dec_sec, 500);
  EXPECT_EQ(out[1].side, -1);
  EXPECT_EQ(out[2].dec_sec, 500);
  EXPECT_EQ(out[2].side, 1);
  EXPECT_EQ(out[2].fam_bits, static_cast<std::uint8_t>(kFamG1 | kFamG2Reject));
  EXPECT_EQ(out[2].level_bits, 0b000010);
  EXPECT_EQ(out[2].rung_mask, 0b0110);
  EXPECT_EQ(out[2].conf_sec, 300);  // the EARLIEST, not the last writer
}

TEST(Dedup, ASideIsPartOfTheIdentitySoOppositeSidesNeverMerge) {
  const auto out = dedup({Emission{500, 1, kFamG1, 0, 0b0010, 380},
                          Emission{500, -1, kFamG1, 0, 0b0100, 380}});
  ASSERT_EQ(out.size(), 2u);
  EXPECT_NE(out[0].side, out[1].side);
  EXPECT_EQ(out[0].rung_mask, 0b0100);  // side -1 sorts first and keeps ITS mask
}

// ================================================================ G2 bounds ===
TEST(Reclaim, TheThirtyMinuteBoundIsMeasuredFromTheBREAKAndIsInclusive) {
  EXPECT_TRUE(reclaim_within_bound(1000, 1000 + 1800));
  EXPECT_FALSE(reclaim_within_bound(1000, 1000 + 1801));
  EXPECT_FALSE(reclaim_within_bound(-1, 500));  // no break -> no reclaim
  EXPECT_FALSE(reclaim_within_bound(1000, -1));
}

TEST(Reclaim, AnOutOfBoundReclaimIsDroppedAndCountedNotSilentlyKept) {
  Touch t;
  t.family = LevelFamily::NDAY;
  t.approach_side = 1;
  t.break_sec = 1000;
  t.reclaim_sec = 1000 + 1801;
  std::int64_t dropped = 0;
  const auto em = g2_emissions({t}, &dropped);
  EXPECT_TRUE(em.empty());
  EXPECT_EQ(dropped, 1);
  t.reclaim_sec = 1000 + 1800;
  dropped = 0;
  const auto em2 = g2_emissions({t}, &dropped);
  ASSERT_EQ(em2.size(), 1u);
  EXPECT_EQ(dropped, 0);
  EXPECT_EQ(em2[0].fam_bits, kFamG2Reclaim);
  EXPECT_EQ(em2[0].dec_sec, 2800 + kTauStar);
  EXPECT_EQ(em2[0].level_bits, 1u << static_cast<unsigned>(LevelFamily::NDAY));
}

TEST(G2, CarriesTheApproachSideAndTauStarNotTheFastOpenDelay) {
  Touch t;
  t.family = LevelFamily::VWAP;
  t.approach_side = -1;
  t.reject_sec = 4000;
  std::int64_t dropped = 0;
  const auto em = g2_emissions({t}, &dropped);
  ASSERT_EQ(em.size(), 1u);
  EXPECT_EQ(em[0].side, -1);
  EXPECT_EQ(em[0].dec_sec, 4000 + kTauStar);  // CC-M1-5 D14: G2 keeps tau*
  EXPECT_EQ(em[0].conf_sec, 4000);
}

// ======================================================= the level machine ====
TEST(Levels, ALevelMustArmForFiveMinutesBeyondTwoTolBeforeItCanBeTouched) {
  const double tol = 1.0;
  const std::size_t n = 1200;
  std::vector<double> dist(n, 10.0);   // far: > 2 x tol
  std::vector<std::int8_t> ph(n, 0);   // one phase: no boundary re-arm
  // A first approach at second 100 — too early, the level has not armed yet.
  dist[100] = 0.5;
  // A second approach at 900, by which time 300+ far seconds have passed.
  dist[900] = 0.5;
  const auto scan = touch_scan(dist, ph, 0, tol);
  ASSERT_EQ(scan.touches.size(), 1u);
  EXPECT_EQ(scan.touches[0], 900);
  // ... but VIRGINITY is arming-independent: the level was near at 100.
  EXPECT_EQ(scan.first_near, 100);
}

TEST(Levels, EveryPhaseBoundaryReArmsALevelImmediately) {
  const double tol = 1.0;
  const std::size_t n = 400;
  std::vector<double> dist(n, 10.0);
  std::vector<std::int8_t> ph(n, 0);
  for (std::size_t i = 200; i < n; ++i) {
    ph[i] = 1;  // a phase boundary at 200
  }
  dist[210] = 0.5;  // only 10 far seconds since the boundary
  const auto scan = touch_scan(dist, ph, 0, tol);
  ASSERT_EQ(scan.touches.size(), 1u);
  EXPECT_EQ(scan.touches[0], 210);
}

TEST(Levels, ATouchDisarmsTheLevelUntilItReArms) {
  const double tol = 1.0;
  const std::size_t n = 2000;
  std::vector<double> dist(n, 10.0);
  std::vector<std::int8_t> ph(n, 0);
  dist[400] = 0.5;   // armed by 300 far seconds -> a touch
  dist[401] = 0.5;   // still near: NOT a second touch
  dist[402] = 0.5;
  dist[800] = 0.5;   // re-armed by 300+ far seconds -> a second touch
  const auto scan = touch_scan(dist, ph, 0, tol);
  ASSERT_EQ(scan.touches.size(), 2u);
  EXPECT_EQ(scan.touches[0], 400);
  EXPECT_EQ(scan.touches[1], 800);
}

TEST(Levels, NothingBeforeTheLevelsCreationSecondArmsTouchesOrCountsAsNear) {
  const double tol = 1.0;
  const std::size_t n = 2000;
  std::vector<double> dist(n, 10.0);
  std::vector<std::int8_t> ph(n, 0);
  dist[100] = 0.5;   // before creation: invisible
  dist[1500] = 0.5;
  const auto scan = touch_scan(dist, ph, 1000, tol);
  ASSERT_EQ(scan.touches.size(), 1u);
  EXPECT_EQ(scan.touches[0], 1500);
  EXPECT_EQ(scan.first_near, 1500);
}

TEST(Levels, AnUnobservableDistanceIsNeitherNearNorFarAndCannotArm) {
  const double tol = 1.0;
  const std::size_t n = 1000;
  std::vector<double> dist(n, std::nan(""));  // no observation is ever far
  std::vector<std::int8_t> ph(n, 0);
  dist[900] = 0.5;
  const auto scan = touch_scan(dist, ph, 0, tol);
  EXPECT_TRUE(scan.touches.empty());
  EXPECT_EQ(scan.first_near, 900);
}

TEST(Outcome, RejectIsTheFirstMoveOfTheFullSizeBackToTheApproachSide) {
  // Approached from ABOVE (app = +1): a REJECT is the mid moving back UP by
  // >= reject_move within 15 minutes.
  std::vector<std::int32_t> secs = iota_secs(1000);
  std::vector<double> diff(1000, 0.0);
  for (std::size_t i = 500; i < 1000; ++i) {
    diff[i] = 5.0;
  }
  const auto oc = classify_touch(diff, secs, 100, 1, 1.0, 5.0);
  EXPECT_EQ(oc.outcome, Outcome::REJECT);
  EXPECT_EQ(oc.reject_sec, 500);
  EXPECT_EQ(oc.outcome_sec, 500);
  EXPECT_EQ(oc.break_sec, -1);
}

TEST(Outcome, TheWindowIsFifteenMinutesAndNothingOutsideItResolvesTheTouch) {
  std::vector<std::int32_t> secs = iota_secs(3000);
  std::vector<double> diff(3000, 0.0);
  for (std::size_t i = 1001; i < 3000; ++i) {
    diff[i] = 5.0;  // 901s after the touch at 100: OUTSIDE the 900s window
  }
  const auto oc = classify_touch(diff, secs, 100, 1, 1.0, 5.0);
  EXPECT_EQ(oc.outcome, Outcome::NONE);
  EXPECT_EQ(oc.reject_sec, -1);
  // one second earlier is INSIDE (the window bound is inclusive)
  std::vector<double> diff2(3000, 0.0);
  for (std::size_t i = 1000; i < 3000; ++i) {
    diff2[i] = 5.0;
  }
  const auto oc2 = classify_touch(diff2, secs, 100, 1, 1.0, 5.0);
  EXPECT_EQ(oc2.reject_sec, 1000);
}

TEST(Outcome, BreakNeedsSixtySECONDSBeyondTheLevelAndReclaimNeedsOneTwentyBack) {
  std::vector<std::int32_t> secs = iota_secs(4000);
  std::vector<double> diff(4000, 0.0);
  // Beyond the level (app = +1 -> "beyond" is diff * app < -tol) from 200.
  for (std::size_t i = 200; i < 1000; ++i) {
    diff[i] = -5.0;
  }
  for (std::size_t i = 1000; i < 4000; ++i) {
    diff[i] = 0.0;  // back on the approach side
  }
  const auto oc = classify_touch(diff, secs, 100, 1, 1.0, 5.0);
  EXPECT_EQ(oc.break_sec, 259);       // the 60th second of the run
  EXPECT_EQ(oc.reclaim_sec, 1119);    // the 120th second back
  EXPECT_EQ(oc.outcome, Outcome::RECLAIM);
  EXPECT_EQ(oc.outcome_sec, 1119);
}

TEST(Outcome, ARunOfBeyondSecondsThatBreaksBeforeSixtyNeverBreaksTheLevel) {
  std::vector<std::int32_t> secs = iota_secs(2000);
  std::vector<double> diff(2000, 0.0);
  for (std::size_t i = 200; i < 259; ++i) {
    diff[i] = -5.0;  // 59 seconds only
  }
  const auto oc = classify_touch(diff, secs, 100, 1, 1.0, 5.0);
  EXPECT_EQ(oc.break_sec, -1);
  EXPECT_EQ(oc.reclaim_sec, -1);
}

TEST(Outcome, ReclaimIsSearchedFromTheBREAKAndBeyondTheFifteenMinuteWindow) {
  std::vector<std::int32_t> secs = iota_secs(6000);
  std::vector<double> diff(6000, 0.0);
  for (std::size_t i = 200; i < 4000; ++i) {
    diff[i] = -5.0;
  }
  const auto oc = classify_touch(diff, secs, 100, 1, 1.0, 5.0);
  EXPECT_EQ(oc.break_sec, 259);
  EXPECT_EQ(oc.reclaim_sec, 4119);  // far outside the 900s outcome window
  EXPECT_EQ(oc.outcome, Outcome::RECLAIM);
}

TEST(Outcome, WhenBothResolveTheEARLIEROneIsTheOutcome) {
  // A genuine simultaneity is impossible (a second cannot be >= +5 and < -1 at
  // once), so the law that matters is: whichever landed EARLIER is the outcome.
  std::vector<std::int32_t> secs = iota_secs(2000);
  std::vector<double> diff(2000, 0.0);
  for (std::size_t i = 200; i < 400; ++i) {
    diff[i] = -5.0;  // breaks at 259
  }
  for (std::size_t i = 400; i < 500; ++i) {
    diff[i] = 5.0;   // rejects at 400, LATER; only 100s back, so no RECLAIM
  }
  for (std::size_t i = 500; i < 2000; ++i) {
    diff[i] = -5.0;
  }
  const auto oc = classify_touch(diff, secs, 100, 1, 1.0, 5.0);
  EXPECT_EQ(oc.break_sec, 259);
  EXPECT_EQ(oc.reject_sec, 400);
  EXPECT_EQ(oc.reclaim_sec, -1);
  EXPECT_EQ(oc.outcome, Outcome::BREAK);
  EXPECT_EQ(oc.outcome_sec, 259);
  // ... and with the reject FIRST the same rule names REJECT.
  std::vector<double> diff2(2000, 0.0);
  for (std::size_t i = 150; i < 200; ++i) {
    diff2[i] = 5.0;  // rejects at 150
  }
  for (std::size_t i = 300; i < 2000; ++i) {
    diff2[i] = -5.0;  // breaks at 359 and never comes back: no RECLAIM
  }
  const auto oc2 = classify_touch(diff2, secs, 100, 1, 1.0, 5.0);
  EXPECT_EQ(oc2.reject_sec, 150);
  EXPECT_EQ(oc2.break_sec, 359);
  EXPECT_EQ(oc2.reclaim_sec, -1);
  EXPECT_EQ(oc2.outcome, Outcome::REJECT);
}

// ================================================== families / masks / pins ===
TEST(Families, TheKeptSevenAreTheCCM133SetPlusOrExtAppendedAtTheTopBit) {
  ASSERT_EQ(kLevelFamilyCount, 7u);
  EXPECT_STREQ(level_family_name(LevelFamily::FVOL_LADDER), "FVOL_LADDER");
  EXPECT_STREQ(level_family_name(LevelFamily::FVOL_BAND), "FVOL_BAND");
  EXPECT_STREQ(level_family_name(LevelFamily::NDAY), "NDAY");
  EXPECT_STREQ(level_family_name(LevelFamily::PRIOR_DAY), "PRIOR_DAY");
  EXPECT_STREQ(level_family_name(LevelFamily::PHASE_HL), "PHASE_HL");
  EXPECT_STREQ(level_family_name(LevelFamily::VWAP), "VWAP");
  EXPECT_STREQ(level_family_name(LevelFamily::OR_EXT), "OR_EXT");
  EXPECT_EQ(static_cast<int>(LevelFamily::FVOL_LADDER), 0);
  EXPECT_EQ(static_cast<int>(LevelFamily::VWAP), 5);
  // APPENDED, never inserted: every bit the v2 roster wrote keeps its meaning.
  EXPECT_EQ(static_cast<int>(LevelFamily::OR_EXT), 6);
}

TEST(Families, TheDO53VwapBandSetIsTheLineAndPlusMinusTwoAndTwoAndAHalfSigma) {
  ASSERT_EQ(kVwapBandCount, 5u);
  std::vector<double> b(kVwapBands, kVwapBands + kVwapBandCount);
  std::sort(b.begin(), b.end());
  EXPECT_DOUBLE_EQ(b[0], -2.5);
  EXPECT_DOUBLE_EQ(b[1], -2.0);
  EXPECT_DOUBLE_EQ(b[2], 0.0);
  EXPECT_DOUBLE_EQ(b[3], 2.0);
  EXPECT_DOUBLE_EQ(b[4], 2.5);
  // the superseded +-1 sigma bands must be gone
  for (double v : b) {
    EXPECT_NE(std::fabs(v), 1.0);
  }
}

TEST(Families, TheFourRungLadderLeadsWithTheFineRungAtBitZero) {
  ASSERT_EQ(kRungCount4, 4u);
  EXPECT_DOUBLE_EQ(kRungs[0], 0.05);
  EXPECT_DOUBLE_EQ(kRungs[1], 0.075);
  EXPECT_DOUBLE_EQ(kRungs[2], 0.11);
  EXPECT_DOUBLE_EQ(kRungs[3], 0.15);
  EXPECT_EQ(kFineBit, 0b0001);
  EXPECT_EQ(kCoarseMask, 0b1110);
  EXPECT_EQ(kTauStar, 120);
}

TEST(Params, TheGeneratorsCanonicalJsonHasSortedKeysAndShortestRoundTripFloats) {
  const std::string j = params_canonical_json(Asset::NKD);
  // "no whitespace" is about the SEPARATORS: strip the string literals and no
  // whitespace at all may remain.
  std::string skeleton;
  bool in_str = false;
  for (std::size_t i = 0; i < j.size(); ++i) {
    if (j[i] == '"') {
      in_str = !in_str;
      continue;
    }
    if (!in_str) {
      skeleton.push_back(j[i]);
    }
  }
  EXPECT_EQ(skeleton.find(' '), std::string::npos) << skeleton;
  EXPECT_EQ(skeleton.find('\t'), std::string::npos);
  EXPECT_EQ(skeleton.find('\n'), std::string::npos);
  EXPECT_NE(j.find("\"tau_star_sec\":120"), std::string::npos);
  EXPECT_NE(j.find("\"rungs\":[0.05,0.075,0.11,0.15]"), std::string::npos);
  EXPECT_NE(j.find("\"vwap_bands\":[0,2,-2,2.5,-2.5]"), std::string::npos);
  // keys are sorted: every '"key":' occurrence must be lexicographically
  // greater than the previous one at the top level.
  std::string prev;
  std::size_t p = 1;
  int depth = 0;
  bool sorted = true;
  while (p < j.size()) {
    if (j[p] == '[') {
      ++depth;
    } else if (j[p] == ']') {
      --depth;
    } else if (j[p] == '"' && depth == 0 && (j[p - 1] == '{' || j[p - 1] == ',')) {
      const std::size_t e = j.find('"', p + 1);
      const std::string key = j.substr(p + 1, e - p - 1);
      if (!prev.empty() && !(prev < key)) {
        sorted = false;
      }
      prev = key;
      p = e;
    }
    ++p;
  }
  EXPECT_TRUE(sorted) << j;
  EXPECT_EQ(params_hash(Asset::NKD).size(), 64u);
  EXPECT_NE(params_hash(Asset::SI), params_hash(Asset::NKD));
}

TEST(Params, TheFrozenSpecShasAreCheckedAgainstTheFilesNotMerelyDeclared) {
  auto m1b = qr::skel::file_sha16(QR_M1B_SPEC_PATH);
  ASSERT_TRUE(m1b.has_value());
  EXPECT_EQ(m1b.value(), std::string(spec_sha16_pin()));
  auto m1 = qr::skel::file_sha16(QR_M1_SPEC_PATH);
  ASSERT_TRUE(m1.has_value());
  const std::string j = params_canonical_json(Asset::SI);
  EXPECT_NE(j.find("\"spec_m1_sha16\":\"" + m1.value() + "\""), std::string::npos);
  EXPECT_NE(j.find("\"spec_m1b_sha16\":\"" + m1b.value() + "\""), std::string::npos);
}

// ======================================== S2.2: the CC-M1-6.1 OR_EXT ledger ===
TEST(OrExt, TheAdoptedCellsAreTheSixOfCCM161AndHGHasNONE) {
  const auto si = orext_adopted_cells(Asset::SI);
  ASSERT_EQ(si.size(), 5u);
  // SI: OR30 {TOKYO, LONDON, NY} + OR60 {TOKYO, LONDON}. Phase indices are
  // TOKYO=0, LONDON=1, NY=2.
  EXPECT_EQ(si[0], std::make_pair(0, 30));
  EXPECT_EQ(si[1], std::make_pair(1, 30));
  EXPECT_EQ(si[2], std::make_pair(2, 30));
  EXPECT_EQ(si[3], std::make_pair(0, 60));
  EXPECT_EQ(si[4], std::make_pair(1, 60));
  const auto nkd = orext_adopted_cells(Asset::NKD);
  ASSERT_EQ(nkd.size(), 1u);
  EXPECT_EQ(nkd[0], std::make_pair(1, 30));
  // HG's 2.2-2.8pp marginals missed the 3pp bar: the EMPTY set is the adoption,
  // not an omission. A single HG cell here would silently create a family.
  EXPECT_TRUE(orext_adopted_cells(Asset::HG).empty());
}

TEST(OrExt, TheRangeIsTheSANEExtremesInsideTheWindowAndClosesAtOpenPlusWidth) {
  // Segment 1 opens at second 100 (the first SANE second of that phase); a
  // 1-minute range therefore spans [100, 160).
  std::vector<std::int32_t> vt;
  std::vector<double> vm;
  std::vector<std::int8_t> ph;
  for (int t = 100; t < 400; ++t) {
    vt.push_back(t);
    vm.push_back(t == 130 ? 12.0 : (t == 150 ? 8.0 : 10.0));
    ph.push_back(1);
  }
  const auto r = opening_range(vt, vm, ph, 1, 1);
  ASSERT_TRUE(r.valid);
  EXPECT_EQ(r.t1, 160);
  EXPECT_DOUBLE_EQ(r.hi, 12.0);
  EXPECT_DOUBLE_EQ(r.lo, 8.0);
  // A move AFTER the range closes never widens it.
  vm[static_cast<std::size_t>(200 - 100)] = 99.0;
  const auto r2 = opening_range(vt, vm, ph, 1, 1);
  EXPECT_DOUBLE_EQ(r2.hi, 12.0);
}

TEST(OrExt, ASegmentWithNothingLeftAfterTheRangeHasNORangeAtAll) {
  // 30 seconds of segment 2 and a 1-minute range: the range never closes inside
  // the segment, so the cell is a TYPED EXCLUSION, not a degenerate level.
  std::vector<std::int32_t> vt;
  std::vector<double> vm;
  std::vector<std::int8_t> ph;
  for (int t = 0; t < 30; ++t) {
    vt.push_back(t);
    vm.push_back(10.0);
    ph.push_back(2);
  }
  EXPECT_FALSE(opening_range(vt, vm, ph, 2, 1).valid);
  // ... and a segment that never appears at all has none either.
  EXPECT_FALSE(opening_range(vt, vm, ph, 0, 1).valid);
}

TEST(OrExt, OnlyTheKAtLeastOneAndAHalfRungsCarryTheFD6Flag) {
  OpeningRange r;
  r.hi = 110.0;
  r.lo = 100.0;
  r.t1 = 500;
  r.phase = 1;
  r.valid = true;
  const auto lv = orext_flag_levels(r);
  // k in {1.5, 2.0} x both sides == 4 prices. k in {0.5, 1.0} are LEDGER rungs
  // but never flag rungs (F-D6 is "beyond an OR_EXT k >= 1.5 level").
  ASSERT_EQ(lv.size(), 4u);
  EXPECT_DOUBLE_EQ(lv[0].price, 110.0 + 1.5 * 10.0);
  EXPECT_DOUBLE_EQ(lv[1].price, 100.0 - 1.5 * 10.0);
  EXPECT_DOUBLE_EQ(lv[2].price, 110.0 + 2.0 * 10.0);
  EXPECT_DOUBLE_EQ(lv[3].price, 100.0 - 2.0 * 10.0);
  for (const auto& l : lv) {
    EXPECT_EQ(l.t1, 500);
    EXPECT_EQ(l.phase, 1);
  }
}

TEST(OrExt, AnExtensionIsBeyondOnlyInsideItsOwnSegmentAndOnlyOnceItsRangeClosed) {
  OpeningRange r;
  r.hi = 110.0;
  r.lo = 100.0;
  r.t1 = 500;
  r.phase = 1;
  r.valid = true;
  const auto cells = orext_flag_levels(r);
  // Beyond the k=1.5 up extension (125), in segment 1, after the range closed.
  EXPECT_TRUE(beyond_extension(125.0, 600, 1, cells));
  EXPECT_TRUE(beyond_extension(85.0, 600, 1, cells));   // below the down side
  EXPECT_FALSE(beyond_extension(120.0, 600, 1, cells));  // inside the ladder
  // A TOKYO opening range says nothing about a NEW YORK price.
  EXPECT_FALSE(beyond_extension(125.0, 600, 2, cells));
  // Causality: the level does not exist before its own range has closed.
  EXPECT_FALSE(beyond_extension(125.0, 499, 1, cells));
  EXPECT_TRUE(beyond_extension(125.0, 500, 1, cells));
}

TEST(Levels, ASegmentScopedLevelDoesNotExistOutsideItsOwnPhase) {
  // Two phases; the level is scoped to phase 1 and the mid sits ON it for the
  // whole session. Outside phase 1 the distance must be UNOBSERVABLE, so the
  // level can neither arm nor be touched there.
  const std::size_t n = 1000;
  std::vector<double> diff(n, 0.0);
  std::vector<std::int8_t> ph(n, 0);
  for (std::size_t i = 600; i < n; ++i) {
    ph[i] = 1;
  }
  scope_diff(&diff, ph, 1);
  for (std::size_t i = 0; i < 600; ++i) {
    EXPECT_TRUE(std::isnan(diff[i])) << i;
  }
  for (std::size_t i = 600; i < n; ++i) {
    EXPECT_DOUBLE_EQ(diff[i], 0.0);
  }
  // -1 means "no scope": an unscoped level is left completely alone.
  std::vector<double> plain(n, 0.0);
  scope_diff(&plain, ph, -1);
  for (double v : plain) {
    EXPECT_DOUBLE_EQ(v, 0.0);
  }
}

TEST(Levels, AScopedLevelCannotBeTouchedInAForeignSegment) {
  const double tol = 1.0;
  const std::size_t n = 2000;
  std::vector<double> diff(n, 10.0);
  std::vector<std::int8_t> ph(n, 0);
  for (std::size_t i = 1500; i < n; ++i) {
    ph[i] = 1;
  }
  diff[900] = 0.0;   // a near second, but in the FOREIGN segment 0
  diff[1900] = 0.0;  // a near second inside the level's own segment 1
  scope_diff(&diff, ph, 1);
  std::vector<double> dist(n);
  for (std::size_t i = 0; i < n; ++i) {
    dist[i] = std::fabs(diff[i]);
  }
  const auto scan = touch_scan(dist, ph, 0, tol);
  ASSERT_EQ(scan.touches.size(), 1u);
  EXPECT_EQ(scan.touches[0], 1900);
  // VIRGINITY is read from the same scoped series, so the foreign near second
  // does not spend it either.
  EXPECT_EQ(scan.first_near, 1900);
}

// ============================================ S2.2: the CC-M1-7.1 calendars ===
TEST(Calendar, TheEtSlotsFollowDaylightSavingInsteadOfAFrozenUtcOffset) {
  // 2024-01-15 08:30 EST = 13:30 UTC; 2024-07-15 08:30 EDT = 12:30 UTC. A
  // frozen offset gets one of the two wrong for eight months of the year.
  const std::int64_t jan_open = 1705276800;  // 2024-01-15 00:00 UTC
  const auto w = local_epoch_offsets(jan_open, 86400, kTzNewYork, 8, 30);
  ASSERT_EQ(w.size(), 1u);
  EXPECT_EQ(jan_open + w[0], 1705325400);  // 13:30 UTC
  const std::int64_t jul_open = 1720915200;  // 2024-07-14 00:00 UTC
  const auto s = local_epoch_offsets(jul_open, 86400, kTzNewYork, 8, 30);
  ASSERT_EQ(s.size(), 1u);
  EXPECT_EQ(jul_open + s[0], 1720960200);  // 12:30 UTC, one hour earlier
  // Tokyo has no DST at all: 12:30 JST is 03:30 UTC in both halves of the year.
  const auto t = local_epoch_offsets(jan_open, 86400, kTzTokyo, 12, 30);
  ASSERT_EQ(t.size(), 1u);
  EXPECT_EQ((jan_open + t[0]) % 86400, 3 * 3600 + 1800);
}

TEST(Calendar, TheScanReachesTheNextLocalDayBecauseAGlobexSessionOpensTheEveningBefore) {
  // A session opening 2024-01-14 18:00 ET (23:00 UTC) contains 2024-01-15's
  // 08:30 ET slot — a join on the OPEN's own local day would find nothing.
  const std::int64_t open_utc = 1705273200;  // 2024-01-14 23:00 UTC
  const auto w = local_epoch_offsets(open_utc, 86400, kTzNewYork, 8, 30);
  ASSERT_EQ(w.size(), 1u);
  EXPECT_EQ(open_utc + w[0], 1705325400);  // 2024-01-15 08:30 ET
  EXPECT_EQ(local_date8(open_utc, kTzNewYork), 20240114);
  EXPECT_EQ(local_date8(open_utc + w[0], kTzNewYork), 20240115);
  // A window that ends before the slot contains NOTHING (half-open on n).
  EXPECT_TRUE(local_epoch_offsets(open_utc, static_cast<std::int32_t>(w[0]), kTzNewYork, 8, 30)
                  .empty());
}

TEST(Calendar, TheMeetingsLastDayIsTheReleaseAndASpanIntoJanuaryRollsTheYear) {
  auto r = fomc_release_dates(QR_FOMC_CSV_PATH);
  ASSERT_TRUE(r.has_value());
  const std::vector<std::int32_t>& d = r.value();
  const auto has = [&d](std::int32_t x) {
    return std::find(d.begin(), d.end(), x) != d.end();
  };
  // "2021,January,26-27" -> the 27th, never the 26th.
  EXPECT_TRUE(has(20210127));
  EXPECT_FALSE(has(20210126));
  // "2023,Jan/Feb,31-1" -> 2023-02-01: the LAST month and the LAST day.
  EXPECT_TRUE(has(20230201));
  EXPECT_FALSE(has(20230131));
  // "2023,Oct/Nov,31-1" -> 2023-11-01, and the year does NOT roll (only a span
  // whose last month is January belongs to the next year).
  EXPECT_TRUE(has(20231101));
  EXPECT_FALSE(has(20241101));
  // "2025,August,22" -> a single-day row keeps that day.
  EXPECT_TRUE(has(20250822));
  // ascending and deduplicated
  EXPECT_TRUE(std::is_sorted(d.begin(), d.end()));
  EXPECT_EQ(std::adjacent_find(d.begin(), d.end()), d.end());
  // A missing calendar is a REFUSAL, never a silently empty news family.
  EXPECT_FALSE(fomc_release_dates("/nonexistent/calendar_fomc.csv").has_value());
}

TEST(Calendar, TheFomcSlotIsJoinedOnTheReleaseSecondsEtDayNotTheSessionsOwnDay) {
  // Session opens 2024-01-14 23:00 UTC = 18:00 ET on the 14th. The FOMC slot it
  // contains is 2024-01-15 14:00 ET.
  const std::int64_t open_utc = 1705273200;
  const std::vector<std::int32_t> fomc_15 = {20240115};
  const std::vector<std::int32_t> fomc_14 = {20240114};
  const auto with15 = news_release_offsets(open_utc, 86400, fomc_15);
  const auto with14 = news_release_offsets(open_utc, 86400, fomc_14);
  // 08:30 and 10:00 ET fire on EVERY session, so both runs carry two slots;
  // only the 20240115 join adds the 14:00 ET statement.
  EXPECT_EQ(with14.size(), 2u);
  ASSERT_EQ(with15.size(), 3u);
  EXPECT_EQ(open_utc + with15[2], 1705345200);  // 2024-01-15 14:00 ET
}

TEST(Calendar, TheMicroOpensAreTheTokyoLunchReopenAndTheUsCashOpen) {
  const std::int64_t open_utc = 1705273200;  // 2024-01-14 23:00 UTC
  const auto o = micro_open_offsets(open_utc, 86400);
  ASSERT_EQ(o.size(), 2u);
  EXPECT_EQ(open_utc + o[0], 1705289400);  // 2024-01-15 12:30 Asia/Tokyo
  EXPECT_EQ(open_utc + o[1], 1705329000);  // 2024-01-15 09:30 America/New_York
}

// ================================================ S2.2: windows and shocks ====
TEST(Windows, TheWindowIsHalfOpenAndOverlappingTriggersMergeIntoOne) {
  const auto w = open_windows({100}, 300);
  ASSERT_EQ(w.size(), 1u);
  EXPECT_EQ(w[0].a, 100);
  EXPECT_EQ(w[0].b, 399);       // [100, 100+300) -> inclusive 399
  EXPECT_TRUE(in_intervals(100, w));
  EXPECT_TRUE(in_intervals(399, w));
  EXPECT_FALSE(in_intervals(400, w));  // exactly 300s after: OUTSIDE
  EXPECT_FALSE(in_intervals(99, w));
  // Two triggers 60s apart are ONE window, not two that double-count.
  const auto m = open_windows({100, 160}, 300);
  ASSERT_EQ(m.size(), 1u);
  EXPECT_EQ(m[0].a, 100);
  EXPECT_EQ(m[0].b, 459);
  // ... and two that do not touch stay separate.
  const auto sep = open_windows({100, 1000}, 300);
  EXPECT_EQ(sep.size(), 2u);
  EXPECT_FALSE(in_intervals(500, sep));
  EXPECT_TRUE(in_intervals(1000, sep));
}

TEST(Shock, AnEpisodeStartsWhenTheTRAILINGRangeREACHESTheThresholdNotWhenTheMoveBegins) {
  // mult 1: the mid IS the dollar. A $1,000 move completed at second 10.
  std::vector<std::int32_t> vt;
  std::vector<double> vm;
  for (int t = 0; t <= 400; ++t) {
    vt.push_back(t);
    vm.push_back(t < 10 ? 0.0 : 1000.0);
  }
  const auto eps = shock_episodes(vt, vm, 1.0);
  ASSERT_EQ(eps.size(), 1u);
  // The range only REACHES $1,000 at second 10 — never at second 0, which would
  // be the detector reading forward.
  EXPECT_EQ(eps[0].a, 10);
  // ... and it ends at the LAST second whose trailing window still reaches back
  // to the pre-move price: second 9 + 149 = 158, never a second later.
  EXPECT_EQ(eps[0].b, 158);
}

TEST(Shock, TheTrailingWindowIsWALLSecondsSoAGapShortensItInsteadOfReachingBack) {
  // Two observations, 150 wall-seconds apart, with a $1,000 gap between them.
  // The window at t=150 is (150-150, 150] = [1, 150]: second 0 is OUTSIDE, so
  // this is NOT a shock. Counting OBSERVATIONS instead of seconds would fire.
  const std::vector<std::int32_t> vt = {0, 150};
  const std::vector<double> vm = {0.0, 1000.0};
  EXPECT_TRUE(shock_episodes(vt, vm, 1.0).empty());
  // One second closer and the same move IS a shock.
  const std::vector<std::int32_t> vt2 = {0, 149};
  EXPECT_EQ(shock_episodes(vt2, vm, 1.0).size(), 1u);
}

TEST(Shock, AWideBookEpisodeNeedsTenSustainedSecondsAndABookOUTAGEIsNeverOne) {
  const std::size_t n = 200;
  std::vector<std::int8_t> state(n, 0);   // 0 == TWO_SIDED
  std::vector<std::uint8_t> sane(n, 1);
  for (std::size_t t = 20; t < 29; ++t) {
    sane[t] = 0;  // 9 wide seconds: too short
  }
  EXPECT_TRUE(insane_episodes(state, sane).empty());
  for (std::size_t t = 20; t < 30; ++t) {
    sane[t] = 0;  // 10 wide seconds: an episode
  }
  const auto e = insane_episodes(state, sane);
  ASSERT_EQ(e.size(), 1u);
  EXPECT_EQ(e[0].a, 20);
  EXPECT_EQ(e[0].b, 29);
  // A ONE-SIDED / EMPTY book for 50 seconds is an OUTAGE, not a wide book: it
  // is not sane either, and it must NOT become a shock episode.
  std::vector<std::int8_t> out_state(n, 0);
  std::vector<std::uint8_t> out_sane(n, 1);
  for (std::size_t t = 100; t < 150; ++t) {
    out_state[t] = 1;  // not TWO_SIDED
    out_sane[t] = 0;
  }
  EXPECT_TRUE(insane_episodes(out_state, out_sane).empty());
}

TEST(PostShock, OnlyTheEARLIESTConfirmationAfterAnEpisodeFiresAndEverySideAtThatSecondDoes) {
  //                       idx: 0    1    2    3
  const std::vector<std::int32_t> conf = {100, 300, 300, 500};
  const auto w = first_confirmations_after(conf, 200);
  ASSERT_EQ(w.size(), 2u);      // both sides confirming on second 300
  EXPECT_EQ(w[0], 1u);
  EXPECT_EQ(w[1], 2u);
  // STRICTLY after: a confirmation ON the episode's last second is part of the
  // shock, not its resolution.
  const auto onboundary = first_confirmations_after(conf, 300);
  ASSERT_EQ(onboundary.size(), 1u);
  EXPECT_EQ(onboundary[0], 3u);
  EXPECT_TRUE(first_confirmations_after(conf, 500).empty());
}

// ================================== S2.2: the adopted families and the flags ===
TEST(NewFamilies, TheNineBitsAppendTheAdoptedFourAfterTheOriginalFive) {
  ASSERT_EQ(kFamilyCount, 9u);
  EXPECT_EQ(kFamG1, 1u << 0);
  EXPECT_EQ(kFamG2Reclaim, 1u << 4);
  EXPECT_EQ(kFamNewsWindow, 1u << 5);
  EXPECT_EQ(kFamMicroOpen, 1u << 6);
  EXPECT_EQ(kFamPostShock, 1u << 7);
  EXPECT_EQ(kFamFirstTest, 1u << 8);
  EXPECT_STREQ(family_name(0), "G1");
  EXPECT_STREQ(family_name(5), "NEWS_WINDOW");
  EXPECT_STREQ(family_name(6), "MICRO_OPEN");
  EXPECT_STREQ(family_name(7), "POST_SHOCK");
  EXPECT_STREQ(family_name(8), "FIRST_TEST");
  // The delays are NOT interchangeable: NEWS and MICRO are 15s, everything
  // else is tau*, and FAST-CLOSE does not exist at all.
  EXPECT_EQ(kNewsDelay, 15);
  EXPECT_EQ(kMicroDelay, 15);
  EXPECT_EQ(kNewsWindow, 600);
  EXPECT_EQ(kMicroWindow, 300);
}

TEST(NewFamilies, FirstTestIsAFamilyOnNKDOnlyAndAFeatureEverywhereElse) {
  EXPECT_TRUE(first_test_is_a_family(Asset::NKD));
  EXPECT_FALSE(first_test_is_a_family(Asset::SI));
  EXPECT_FALSE(first_test_is_a_family(Asset::HG));
}

TEST(FirstTest, IsTheEarliestConfirmingTouchPerLEVELFamilyAndTiesKeepTheEarlierArrival) {
  const std::vector<G2Conf> g2 = {
      {500, 1, kFamG2Reject, LevelFamily::NDAY},
      {300, -1, kFamG2Reject, LevelFamily::VWAP},
      {300, 1, kFamG2Reclaim, LevelFamily::VWAP},   // SAME second, later arrival
      {200, -1, kFamG2Reject, LevelFamily::NDAY},   // earlier than the NDAY 500
  };
  const auto ft = first_test_confirmations(g2);
  ASSERT_EQ(ft.size(), 2u);
  EXPECT_EQ(ft[0].family, LevelFamily::NDAY);
  EXPECT_EQ(ft[0].conf_sec, 200);
  EXPECT_EQ(ft[0].side, -1);
  EXPECT_EQ(ft[1].family, LevelFamily::VWAP);
  EXPECT_EQ(ft[1].conf_sec, 300);
  // A LATER equal second never displaces the earlier arrival, so the side is
  // the FIRST one the ledger produced.
  EXPECT_EQ(ft[1].side, -1);
}

TEST(FirstTest, TheVirginFlagReadsFirstEverTouchesAndIsBLINDToOrExtByTheOraclesConstruction) {
  Touch v;
  v.family = LevelFamily::NDAY;
  v.virgin_at_touch = 1;
  v.reject_sec = 400;
  Touch repeat;
  repeat.family = LevelFamily::VWAP;
  repeat.virgin_at_touch = 0;
  repeat.reject_sec = 500;
  Touch orext;  // a FIRST-ever touch, but on the OR_EXT family
  orext.family = LevelFamily::OR_EXT;
  orext.virgin_at_touch = 1;
  orext.reject_sec = 600;
  Touch late_reclaim;  // virgin, but the reclaim is outside the 30-minute bound
  late_reclaim.family = LevelFamily::PRIOR_DAY;
  late_reclaim.virgin_at_touch = 1;
  late_reclaim.break_sec = 1000;
  late_reclaim.reclaim_sec = 1000 + 1801;
  const auto s = virgin_confirmation_secs({v, repeat, orext, late_reclaim});
  ASSERT_EQ(s.size(), 1u);
  EXPECT_EQ(s[0], 400);
  // The OR_EXT exclusion is the frozen oracle's own construction
  // (family_discovery reads the pre-OR_EXT ledger) — reproduced deliberately
  // and returned as defect S22-D1, not invented here.
  late_reclaim.reclaim_sec = 1000 + 1800;
  const auto s2 = virgin_confirmation_secs({v, orext, late_reclaim});
  ASSERT_EQ(s2.size(), 2u);
  EXPECT_EQ(s2[1], 2800);
}

TEST(Dedup, TheFlagBitsAreUnionedLikeEveryOtherTag) {
  const auto out = dedup({Emission{500, 1, kFamG1, 0, 0b0010, 380, kFlagOrExtBeyond},
                          Emission{500, 1, kFamFirstTest, 0, 0, 300, kFlagFirstTestVirgin}});
  ASSERT_EQ(out.size(), 1u);
  EXPECT_EQ(out[0].flags,
            static_cast<std::uint8_t>(kFlagOrExtBeyond | kFlagFirstTestVirgin));
  EXPECT_EQ(out[0].fam_bits, static_cast<std::uint16_t>(kFamG1 | kFamFirstTest));
  EXPECT_EQ(out[0].conf_sec, 300);
  // The three flag bits are distinct and F-D6 owns the low two.
  EXPECT_EQ(kFlagOrExtBeyond, 1u);
  EXPECT_EQ(kFlagOrExtBeyondAny, 2u);
  EXPECT_EQ(kFlagFirstTestVirgin, 4u);
}

// ==================================================================== tables ==
namespace {

std::string scratch(const char* name) {
  return std::string(QR_TEST_SCRATCH_DIR) + "/" + name;
}

void write_file(const std::string& path, const std::string& text) {
  std::FILE* fh = std::fopen(path.c_str(), "wb");
  ASSERT_NE(fh, nullptr);
  std::fwrite(text.data(), 1, text.size(), fh);
  std::fclose(fh);
}

}  // namespace

TEST(Tables, AFrozenQuoteSessionIsDroppedFromTheLevelHistory) {
  const std::string p = scratch("v1_stale.tsv");
  write_file(p,
             "# comment\n"
             "asset\ttrade_date\tsegment\topen_px\thigh_px\tlow_px\tclose_px\trange_usd\n"
             "SI\t2021-06-01\tSESSION\t10\t11\t9\t10.5\t1000\n"
             "SI\t2021-06-02\tSESSION\t10\t10\t10\t10\t0\n"
             "SI\t2021-06-03\tSESSION\t10\t12\t9\t11\t2000\n"
             "HG\t2021-06-02\tSESSION\t1\t2\t1\t2\t500\n");
  auto h = qr::gen::V1History::load(p, "SI");
  ASSERT_TRUE(h.has_value());
  // 2021-06-02 has a $0 range: a frozen quote, not a session.
  ASSERT_EQ(h.value().dates().size(), 2u);
  EXPECT_EQ(h.value().dates()[0], 20210601);
  EXPECT_EQ(h.value().dates()[1], 20210603);
  // ... so 06-03's "previous session" is 06-01, which is what a PRIOR_DAY level
  // is built from.
  EXPECT_EQ(h.value().index_of(20210603), 1);
  EXPECT_DOUBLE_EQ(
      h.value().at(0).seg[static_cast<std::size_t>(qr::gen::Segment::SESSION)].high_px, 11.0);
  EXPECT_EQ(h.value().index_of(20210602), -1);
}

TEST(Tables, AMissingCellIsNaNAndNeverZero) {
  const std::string p = scratch("bars_nan.tsv");
  write_file(p,
             "trade_date\tATR14_prev_usd\n"
             "2021-05-31\t\n"
             "2021-06-01\t2558.9286\n");
  auto b = qr::gen::BarsTable::load(p);
  ASSERT_TRUE(b.has_value());
  EXPECT_TRUE(std::isnan(b.value().atr14_prev_usd(20210531)));
  EXPECT_TRUE(std::isnan(b.value().atr14_prev_usd(20211231)));
  EXPECT_DOUBLE_EQ(b.value().atr14_prev_usd(20210601), 2558.9286);
}

TEST(Tables, OnlyTheAllSplitAndANumericEraFeedTheRungFloor) {
  const std::string p = scratch("cost_rollup.tsv");
  write_file(p,
             "asset\tphase\tera\tsplit\tspread_med_usd_pooled\n"
             "SI\tTOKYO\t2021\tall\t25\n"
             "SI\tTOKYO\t2021\tex_roll_week\t99\n"
             "SI\tLONDON\tFIT_2021_2024\tall\t77\n"
             "SI\tNY\t2021\tall\t12.5\n"
             "HG\tTOKYO\t2021\tall\t50\n");
  auto m = qr::gen::PhaseMedianSpreads::load(p, "SI");
  ASSERT_TRUE(m.has_value());
  EXPECT_DOUBLE_EQ(m.value().median_usd(2021, 0), 25.0);   // TOKYO, "all" split
  EXPECT_DOUBLE_EQ(m.value().median_usd(2021, 2), 12.5);   // NY
  EXPECT_TRUE(std::isnan(m.value().median_usd(2021, 1)));  // era not numeric
  EXPECT_TRUE(std::isnan(m.value().median_usd(2099, 0)));
}

TEST(Tables, TheLadderColumnsAreMultipliersOnSigmaHatAndAreReadByQuantile) {
  const std::string p = scratch("fvol.tsv");
  write_file(p,
             "asset\ttrade_date\tsegment\tsigma_hat_usd\tmove_q10_usd_per_sigma\t"
             "move_q25_usd_per_sigma\tmove_q50_usd_per_sigma\tmove_q75_usd_per_sigma\t"
             "move_q90_usd_per_sigma\n"
             "SI\t2021-06-01\tSESSION\t1000\t0.5\t0.8\t1.1\t1.5\t2.2\n"
             "SI\t2021-06-01\tTOKYO\t\t\t\t\t\t\n");
  auto f = qr::gen::FvolForecasts::load(p, "SI");
  ASSERT_TRUE(f.has_value());
  const qr::gen::FvolRow* r = f.value().find(20210601, qr::gen::Segment::SESSION);
  ASSERT_NE(r, nullptr);
  EXPECT_DOUBLE_EQ(r->sigma_hat_usd, 1000.0);
  EXPECT_DOUBLE_EQ(r->move_q[0], 0.5);
  EXPECT_DOUBLE_EQ(r->move_q[4], 2.2);
  const qr::gen::FvolRow* t = f.value().find(20210601, qr::gen::Segment::TOKYO);
  ASSERT_NE(t, nullptr);
  EXPECT_TRUE(std::isnan(t->sigma_hat_usd));  // a blank forecast builds NO level
  EXPECT_EQ(f.value().find(20210601, qr::gen::Segment::NY), nullptr);
}
