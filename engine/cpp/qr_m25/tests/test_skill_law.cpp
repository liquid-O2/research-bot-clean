// qr_m25/tests/test_skill_law.cpp — the parametric skill law of FINAL_PLAN
// section 8 item 1: its two endpoints, its calibration, its determinism, and the
// numpy parity of every number it draws.
#include <gtest/gtest.h>

#include <algorithm>
#include <cmath>
#include <numeric>
#include <vector>

#include "m25_test_support.hpp"
#include "qr_m25/skill.hpp"

namespace {

using qr::m25::build_skill_draws;
using qr::m25::DrawPurpose;
using qr::m25::kHorizonRefIndex;
using qr::m25::SessionTape;
using qr::m25::SkillDraws;
using qr::m25::test::Spec;
using qr::replay::LabelState;

/// A session with a spread of nets and a realistic stop rate.
SessionTape wide_tape(std::int64_t ordinal = 125, std::int64_t rows = 400) {
  std::vector<Spec> specs;
  for (std::int64_t c = 0; c < rows; ++c) {
    Spec spec;
    spec.clock = c;
    spec.is_long = true;
    // A deterministic zig-zag: distinct nets, both signs, a few at the stop.
    spec.net_cent = ((c * 7919) % 20011) - 10000;
    spec.hold_seconds = 30;
    spec.stopped = spec.net_cent <= -9000;
    // One row in fifty carries no fresh label: it can never trade, so a skilled
    // agent must rank it BELOW every row that can.
    spec.available = (c % 50) != 49;
    specs.push_back(spec);
    Spec other = spec;
    other.is_long = false;
    other.net_cent = -spec.net_cent - 1152;
    other.stopped = other.net_cent <= -9000;
    specs.push_back(other);
  }
  return qr::m25::test::make_tape(ordinal, 2022, specs);
}

double pearson(const std::vector<double>& a, const std::vector<double>& b) {
  const double n = static_cast<double>(a.size());
  const double mean_a = std::accumulate(a.begin(), a.end(), 0.0) / n;
  const double mean_b = std::accumulate(b.begin(), b.end(), 0.0) / n;
  double cov = 0.0;
  double var_a = 0.0;
  double var_b = 0.0;
  for (std::size_t i = 0; i < a.size(); ++i) {
    const double da = a[i] - mean_a;
    const double db = b[i] - mean_b;
    cov += da * db;
    var_a += da * da;
    var_b += db * db;
  }
  return cov / std::sqrt(var_a * var_b);
}

}  // namespace

TEST(SkillLaw, PhiInverseMatchesScipyToSixteenDigits) {
  // Pinned from scipy.special.ndtri (scipy 1.18.0) — the skill axis is defined
  // by these numbers, so an approximation that is "close enough" is not.
  const struct {
    double p;
    double want;
  } cases[] = {
      {1e-300, -37.0470962993612},        {1e-12, -7.034483825301131},
      {0.0001, -3.7190164854556804},      {0.001, -3.090232306167813},
      {0.025, -1.9599639845400545},       {0.1, -1.2815515655446004},
      {0.25, -0.6744897501960817},        {0.4, -0.2533471031357997},
      {0.5, 0.0},                         {0.6, 0.2533471031357997},
      {0.75, 0.6744897501960817},         {0.9, 1.2815515655446004},
      {0.975, 1.959963984540054},         {0.999, 3.090232306167813},
      {0.9999, 3.719016485455709},        {0.999999999999, 7.0344869100478356},
  };
  for (const auto& one : cases) {
    const double got = qr::m25::ndtri(one.p);
    EXPECT_NEAR(got, one.want, 1e-12 * std::max(1.0, std::fabs(one.want))) << "p=" << one.p;
  }
  EXPECT_NEAR(qr::m25::ndtr(0.0), 0.5, 1e-15);
  EXPECT_NEAR(qr::m25::ndtr(1.959963984540054), 0.975, 1e-12);
}

TEST(SkillLaw, TheUniformStreamIsNumpyPcg64ForTheDeclaredSeed) {
  // numpy 2.1.2: Generator(PCG64(SeedSequence([20260810, 3486317, purpose, sid,
  // replicate]))).random(...). If this ever drifts, the M2.5 draws are a
  // different experiment from the one the receipts name.
  qr::m25::UniformStream skill(DrawPurpose::SKILL, 125, 0);
  const double skill_want[] = {0.18824485033903826, 0.8208774126720866, 0.8878072537303494,
                               0.43691370516936945, 0.444113420847312,  0.10723520400945097,
                               0.46073310796200084, 0.17593389339487975};
  for (const double want : skill_want) {
    EXPECT_DOUBLE_EQ(skill.next(), want);
  }
  qr::m25::UniformStream coin(DrawPurpose::DECOMPOSITION_COIN, 200, 3);
  const double coin_want[] = {0.318399539889089, 0.23880236017941092, 0.16591807831667826,
                              0.4835746169448176};
  for (const double want : coin_want) {
    EXPECT_DOUBLE_EQ(coin.next(), want);
  }
}

TEST(SkillLaw, PerfectSkillRanksExactlyByTheTruth) {
  SessionTape tape = wide_tape();
  const SkillDraws draws = build_skill_draws(tape, 0);
  qr::m25::apply_skill(draws, 1.0, 2, &tape);
  std::vector<std::size_t> order(tape.rows.size());
  std::iota(order.begin(), order.end(), std::size_t{0});
  std::sort(order.begin(), order.end(), [&tape](std::size_t a, std::size_t b) {
    return tape.rows[a].predicted_net_h_star < tape.rows[b].predicted_net_h_star;
  });
  for (std::size_t rank = 1; rank < order.size(); ++rank) {
    const auto& previous = tape.rows[order[rank - 1]].label;
    const auto& current = tape.rows[order[rank]].label;
    // Every step of the perfect ranking is non-decreasing in the truth, and an
    // unavailable label never outranks an available one.
    if (previous.state == LabelState::OK && current.state == LabelState::OK) {
      EXPECT_LE(previous.menu_net_cent[2], current.menu_net_cent[2]);
    }
    EXPECT_FALSE(previous.state == LabelState::OK && current.state != LabelState::OK);
  }
}

TEST(SkillLaw, ZeroSkillIgnoresTheTruthEntirely) {
  SessionTape one = wide_tape();
  SessionTape two = wide_tape();
  // Same keys, different truth: at Q = 0 the scores must be bit-identical,
  // because a zero-skill agent has no access to the outcome at all.
  for (auto& row : two.rows) {
    for (std::size_t h = 0; h < qr::replay::kHorizonCount; ++h) {
      row.label.menu_net_cent[h] = -row.label.menu_net_cent[h];
    }
  }
  const SkillDraws draws_one = build_skill_draws(one, 0);
  const SkillDraws draws_two = build_skill_draws(two, 0);
  qr::m25::apply_skill(draws_one, 0.0, 2, &one);
  qr::m25::apply_skill(draws_two, 0.0, 2, &two);
  for (std::size_t i = 0; i < one.rows.size(); ++i) {
    EXPECT_DOUBLE_EQ(one.rows[i].predicted_net_h_star, two.rows[i].predicted_net_h_star);
  }
}

TEST(SkillLaw, TheSkillParameterIsTheRankCorrelationItClaimsToBe) {
  SessionTape tape = wide_tape(125, 2000);
  const SkillDraws draws = build_skill_draws(tape, 0);
  for (const double q : {0.0, 0.25, 0.5, 0.75, 1.0}) {
    qr::m25::apply_skill(draws, q, 2, &tape);
    std::vector<double> score;
    std::vector<double> truth;
    score.reserve(tape.rows.size());
    truth.reserve(tape.rows.size());
    for (std::size_t i = 0; i < tape.rows.size(); ++i) {
      score.push_back(tape.rows[i].predicted_net_h_star);
      truth.push_back(draws.net_z[2][i]);
    }
    // Q IS the normal-score correlation, by construction of the copula.
    EXPECT_NEAR(pearson(score, truth), q, 0.05) << "q=" << q;
  }
}

TEST(SkillLaw, TheRiskHeadIsCalibratedAtBothEndpoints) {
  SessionTape tape = wide_tape();
  const SkillDraws draws = build_skill_draws(tape, 0);
  ASSERT_GT(draws.stop_rate_h_ref, 0.0);
  ASSERT_LT(draws.stop_rate_h_ref, 1.0);

  qr::m25::apply_skill(draws, 0.0, 2, &tape);
  for (const auto& row : tape.rows) {
    // Zero skill: the base rate for every row, never a per-row guess.
    EXPECT_NEAR(row.predicted_stop_prob_h_ref, draws.stop_rate_h_ref, 1e-12);
  }

  qr::m25::apply_skill(draws, 1.0, 2, &tape);
  for (const auto& row : tape.rows) {
    const bool stopped =
        row.label.state == LabelState::OK && row.label.stop_hit[kHorizonRefIndex] != 0;
    EXPECT_DOUBLE_EQ(row.predicted_stop_prob_h_ref, stopped ? 1.0 : 0.0);
  }

  // In between: the reported probability must actually predict the event. The
  // mean predicted probability tracks the realised rate.
  qr::m25::apply_skill(draws, 0.6, 2, &tape);
  double predicted_sum = 0.0;
  double realised = 0.0;
  double counted = 0.0;
  for (const auto& row : tape.rows) {
    if (row.label.state != LabelState::OK) {
      continue;
    }
    predicted_sum += row.predicted_stop_prob_h_ref;
    realised += row.label.stop_hit[kHorizonRefIndex] != 0 ? 1.0 : 0.0;
    counted += 1.0;
  }
  EXPECT_NEAR(predicted_sum / counted, realised / counted, 0.03);
}

TEST(SkillLaw, DrawsAreReproducibleAndReplicateSpecific) {
  SessionTape tape = wide_tape();
  const SkillDraws a = build_skill_draws(tape, 0);
  const SkillDraws b = build_skill_draws(tape, 0);
  const SkillDraws c = build_skill_draws(tape, 1);
  ASSERT_EQ(a.net_noise.size(), b.net_noise.size());
  for (std::size_t i = 0; i < a.net_noise.size(); ++i) {
    EXPECT_DOUBLE_EQ(a.net_noise[i], b.net_noise[i]);
    EXPECT_DOUBLE_EQ(a.risk_noise[i], b.risk_noise[i]);
    EXPECT_DOUBLE_EQ(a.risk_latent[i], b.risk_latent[i]);
  }
  std::size_t differing = 0;
  for (std::size_t i = 0; i < a.net_noise.size(); ++i) {
    if (a.net_noise[i] != c.net_noise[i]) {
      ++differing;
    }
  }
  EXPECT_EQ(differing, a.net_noise.size());
}

TEST(SkillLaw, TheNoiseIsCommonAcrossTheWholeQGrid) {
  SessionTape tape = wide_tape();
  const SkillDraws draws = build_skill_draws(tape, 0);
  qr::m25::apply_skill(draws, 0.0, 2, &tape);
  std::vector<double> at_zero;
  for (const auto& row : tape.rows) {
    at_zero.push_back(row.predicted_net_h_star);
  }
  // score(Q) = Q*z + sqrt(1-Q^2)*e, and score(0) = e. Recovering e from the
  // Q = 0.5 scores must give back exactly the same vector: one noise draw, one
  // family, which is what makes "the minimal Q" a number and not an accident.
  qr::m25::apply_skill(draws, 0.5, 2, &tape);
  const double residual = std::sqrt(1.0 - 0.25);
  for (std::size_t i = 0; i < tape.rows.size(); ++i) {
    const double recovered = (tape.rows[i].predicted_net_h_star - 0.5 * draws.net_z[2][i]) / residual;
    EXPECT_NEAR(recovered, at_zero[i], 1e-9);
  }
}
