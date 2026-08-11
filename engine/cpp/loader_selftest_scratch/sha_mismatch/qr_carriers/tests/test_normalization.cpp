// test_normalization.cpp — the TRAIN-only equal-session normalization
// scaffolding: the two-level reduction, the two floors, the clip, the
// binary/categorical exemption, and the hash of every per-feature (S,mu,scale).
#include <gtest/gtest.h>

#include <cmath>

#include "qr_carriers/normalization.hpp"

namespace qr::carriers {
namespace {

TEST(SessionMomentsLaw, OnlyFinitePresentValuesAreObserved) {
  SessionMoments moments;
  EXPECT_FALSE(moments.present());
  moments.observe(2.0);
  moments.observe(4.0);
  moments.observe(std::numeric_limits<double>::quiet_NaN());        // not finite
  moments.observe(std::numeric_limits<double>::infinity());         // not finite
  moments.observe_typed(99.0, Validity::MISSING);                    // not present
  moments.observe_typed(99.0, Validity::ATTACHMENT_FUTURE);          // not present
  moments.observe_typed(6.0, Validity::VALID);
  EXPECT_EQ(moments.count, 3);
  // m_s = (2+4+6)/3 = 4; q_s = (4+16+36)/3 = 56/3
  EXPECT_DOUBLE_EQ(moments.first_moment(), 4.0);
  EXPECT_DOUBLE_EQ(moments.second_moment(), 56.0 / 3.0);
}

TEST(EqualSessionWeighting, MuIsTheMeanOfSessionMeansAndNotThePooledMean) {
  // Session A: one value, 10.  Session B: ninety-nine values, all 0.
  // EQUAL SESSION WEIGHT gives mu = (10 + 0)/2 = 5.
  // The POOLED mean — the defect this shape exists to prevent — would be
  // 10/100 = 0.1, twenty-fold different.
  const std::array<std::uint8_t, 1> continuous{1};
  NormalizationFitter fitter(1, continuous);

  std::array<SessionMoments, 1> session_a{};
  session_a[0].observe(10.0);
  ASSERT_TRUE(fitter.observe_session(session_a).has_value());

  std::array<SessionMoments, 1> session_b{};
  for (int index = 0; index < 99; ++index) {
    session_b[0].observe(0.0);
  }
  ASSERT_TRUE(fitter.observe_session(session_b).has_value());

  const auto table = fitter.freeze();
  ASSERT_EQ(table.size(), 1U);
  EXPECT_EQ(table[0].sessions, 2);
  EXPECT_DOUBLE_EQ(table[0].mu, 5.0);
  EXPECT_NE(table[0].mu, 0.1);
  // mean_s(q_s) = (100 + 0)/2 = 50; scale = sqrt(50 - 25) = 5.
  EXPECT_DOUBLE_EQ(table[0].scale, 5.0);
}

TEST(EqualSessionWeighting, ASessionWithNoPresentValueDoesNotIncrementS) {
  const std::array<std::uint8_t, 2> continuous{1, 1};
  NormalizationFitter fitter(2, continuous);
  std::array<SessionMoments, 2> first{};
  first[0].observe(4.0);  // feature 1 is absent this session
  ASSERT_TRUE(fitter.observe_session(first).has_value());
  std::array<SessionMoments, 2> second{};
  second[0].observe(6.0);
  second[1].observe(1.0);
  ASSERT_TRUE(fitter.observe_session(second).has_value());

  const auto table = fitter.freeze();
  EXPECT_EQ(fitter.sessions_observed(), 2);
  EXPECT_EQ(table[0].sessions, 2);  // "TRAIN sessions having at least one present value"
  EXPECT_EQ(table[1].sessions, 1);
  EXPECT_DOUBLE_EQ(table[0].mu, 5.0);  // (4+6)/2
  EXPECT_DOUBLE_EQ(table[1].mu, 1.0);
}

TEST(FrozenTableLaw, SZeroGivesZeroAndOneAndADegenerateScaleBecomesOne) {
  const std::array<std::uint8_t, 2> continuous{1, 1};
  NormalizationFitter fitter(2, continuous);
  std::array<SessionMoments, 2> only{};
  // Feature 0 is constant at 7 -> variance 0 -> scale below 1e-6 -> 1.
  only[0].observe(7.0);
  only[0].observe(7.0);
  ASSERT_TRUE(fitter.observe_session(only).has_value());

  const auto table = fitter.freeze();
  EXPECT_EQ(table[0].sessions, 1);
  EXPECT_DOUBLE_EQ(table[0].mu, 7.0);
  EXPECT_DOUBLE_EQ(table[0].scale, 1.0);  // "scale<1e-6 becomes 1"
  // Feature 1 was never present: "S=0 gives (mu,scale)=(0,1)".
  EXPECT_EQ(table[1].sessions, 0);
  EXPECT_DOUBLE_EQ(table[1].mu, 0.0);
  EXPECT_DOUBLE_EQ(table[1].scale, 1.0);
}

TEST(FrozenTableLaw, ApplyStandardizesThenClipsToTheDeclaredEightBound) {
  FeatureNormalization entry;
  entry.sessions = 4;
  entry.mu = 10.0;
  entry.scale = 2.0;
  entry.centered = true;
  // (14-10)/2 = 2
  EXPECT_DOUBLE_EQ(entry.apply(14.0), 2.0);
  // (10-10)/2 = 0
  EXPECT_DOUBLE_EQ(entry.apply(10.0), 0.0);
  // (100-10)/2 = 45 -> clipped to +8
  EXPECT_DOUBLE_EQ(entry.apply(100.0), 8.0);
  // (-100-10)/2 = -55 -> clipped to -8
  EXPECT_DOUBLE_EQ(entry.apply(-100.0), -8.0);
  // Exactly at the bound is not clipped away: (26-10)/2 = 8
  EXPECT_DOUBLE_EQ(entry.apply(26.0), 8.0);
}

TEST(FrozenTableLaw, BinaryAndCategoricalFieldsAreNeverCenteredOrScaled) {
  const std::array<std::uint8_t, 2> continuous{1, 0};
  NormalizationFitter fitter(2, continuous);
  std::array<SessionMoments, 2> session{};
  session[0].observe(100.0);
  session[1].observe(1.0);  // a mask field: observed, but never fitted
  session[1].observe(1.0);
  ASSERT_TRUE(fitter.observe_session(session).has_value());

  const auto table = fitter.freeze();
  EXPECT_TRUE(table[0].centered);
  EXPECT_FALSE(table[1].centered);
  EXPECT_EQ(table[1].sessions, 0);
  EXPECT_DOUBLE_EQ(table[1].mu, 0.0);
  EXPECT_DOUBLE_EQ(table[1].scale, 1.0);
  // A mask value passes through untouched AND unclipped.
  EXPECT_DOUBLE_EQ(table[1].apply(1.0), 1.0);
  EXPECT_DOUBLE_EQ(table[1].apply(0.0), 0.0);
  EXPECT_DOUBLE_EQ(table[1].apply(1'000.0), 1'000.0);
}

TEST(FitterContract, AMomentVectorOfTheWrongWidthRefusesRatherThanTruncating) {
  const std::array<std::uint8_t, 3> continuous{1, 1, 1};
  NormalizationFitter fitter(3, continuous);
  std::array<SessionMoments, 2> too_narrow{};
  const auto refused = fitter.observe_session(too_narrow);
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), RefusalCode::CONTENT_MISMATCH);
}

TEST(NormalizationHash, TheHashCoversEveryPerFeatureTripleAndMovesWhenAnyOfThemMoves) {
  std::vector<FeatureNormalization> table(2);
  table[0] = FeatureNormalization{4, 1.5, 2.5, true};
  table[1] = FeatureNormalization{0, 0.0, 1.0, false};

  const std::string rendered = render_normalization(table);
  EXPECT_NE(rendered.find("0\t4\t1.5\t2.5\t1\n"), std::string::npos) << rendered;
  EXPECT_NE(rendered.find("1\t0\t0\t1\t0\n"), std::string::npos) << rendered;

  const std::string digest = normalization_sha256(table);
  EXPECT_EQ(digest.size(), 64U);
  EXPECT_EQ(normalization_sha256(table), digest);  // deterministic

  // Every one of the three hashed quantities moves the digest.
  auto moved_s = table;
  moved_s[0].sessions = 5;
  EXPECT_NE(normalization_sha256(moved_s), digest);
  auto moved_mu = table;
  moved_mu[0].mu = 1.5000000000000002;  // one ulp
  EXPECT_NE(normalization_sha256(moved_mu), digest);
  auto moved_scale = table;
  moved_scale[0].scale = 2.5000000000000004;
  EXPECT_NE(normalization_sha256(moved_scale), digest);
}

}  // namespace
}  // namespace qr::carriers
