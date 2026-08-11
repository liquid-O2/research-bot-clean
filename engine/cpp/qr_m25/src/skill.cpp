// qr_m25/src/skill.cpp — AS241 Phi^-1, the numpy-parity uniform stream, and the
// parametric skill corruption law of FINAL_PLAN section 8 item 1.
#include "qr_m25/skill.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <numeric>

namespace qr::m25 {
namespace {

using qr::replay::LabelState;
using qr::replay::ScoredAction;

constexpr double kSqrt1_2 = 0.70710678118654752440;

/// Rank the session's rows for one horizon and return the normal scores.
///
/// Order: every `label_state != OK` row first (they can never trade), then OK
/// rows ascending by `menu_net_cent[h]`, ties by (decision_ordinal, side). The
/// order is total because the prediction key is one-to-one.
std::vector<double> normal_scores(const SessionTape& tape, std::size_t horizon_index) {
  const std::size_t n = tape.rows.size();
  std::vector<std::size_t> order(n);
  std::iota(order.begin(), order.end(), std::size_t{0});
  const std::vector<ScoredAction>& rows = tape.rows;
  std::sort(order.begin(), order.end(), [&rows, horizon_index](std::size_t a, std::size_t b) {
    const bool ok_a = rows[a].label.state == LabelState::OK;
    const bool ok_b = rows[b].label.state == LabelState::OK;
    if (ok_a != ok_b) {
      return !ok_a;  // unavailable rows rank lowest
    }
    if (ok_a) {
      const std::int64_t na = rows[a].label.menu_net_cent[horizon_index];
      const std::int64_t nb = rows[b].label.menu_net_cent[horizon_index];
      if (na != nb) {
        return na < nb;
      }
    }
    if (rows[a].key.decision_ordinal != rows[b].key.decision_ordinal) {
      return rows[a].key.decision_ordinal < rows[b].key.decision_ordinal;
    }
    return static_cast<std::int64_t>(rows[a].key.side) < static_cast<std::int64_t>(rows[b].key.side);
  });

  std::vector<double> z(n, 0.0);
  const double denominator = static_cast<double>(n);
  for (std::size_t rank = 0; rank < n; ++rank) {
    const double p = (static_cast<double>(rank) + 0.5) / denominator;
    z[order[rank]] = ndtri(p);
  }
  return z;
}

}  // namespace

double ndtr(double x) noexcept { return 0.5 * std::erfc(-x * kSqrt1_2); }

// Wichura, AS241 (PPND16). Constants transcribed from the published algorithm.
double ndtri(double p) noexcept {
  if (!(p > 0.0)) {
    return -std::numeric_limits<double>::infinity();
  }
  if (!(p < 1.0)) {
    return std::numeric_limits<double>::infinity();
  }
  const double q = p - 0.5;
  double r = 0.0;
  if (std::fabs(q) <= 0.425) {
    r = 0.180625 - q * q;
    return q *
           (((((((2.5090809287301226727e+3 * r + 3.3430575583588128105e+4) * r +
                 6.7265770927008700853e+4) *
                    r +
                4.5921953931549871457e+4) *
                   r +
               1.3731693765509461125e+4) *
                  r +
              1.9715909503065514427e+3) *
                 r +
             1.3314166789178437745e+2) *
                r +
            3.3871328727963666080e0) /
           (((((((5.2264952788528545610e+3 * r + 2.8729085735721942674e+4) * r +
                 3.9307895800092710610e+4) *
                    r +
                2.1213794301586595867e+4) *
                   r +
               5.3941960214247511077e+3) *
                  r +
              6.8718700749205790830e+2) *
                 r +
             4.2313330701600911252e+1) *
                r +
            1.0);
  }
  r = q < 0.0 ? p : 1.0 - p;
  r = std::sqrt(-std::log(r));
  double value = 0.0;
  if (r <= 5.0) {
    r -= 1.6;
    value = (((((((7.74545014278341407640e-4 * r + 2.27238449892691845833e-2) * r +
                  2.41780725177450611770e-1) *
                     r +
                 1.27045825245236838258e0) *
                    r +
                3.64784832476320460504e0) *
                   r +
               5.76949722146069140550e0) *
                  r +
              4.63033784615654529590e0) *
                 r +
             1.42343711074968357734e0) /
            (((((((1.05075007164441684324e-9 * r + 5.47593808499534494600e-4) * r +
                  1.51986665636164571966e-2) *
                     r +
                 1.48103976427480074590e-1) *
                    r +
                6.89767334985100004550e-1) *
                   r +
               1.67638483018380384940e0) *
                  r +
              2.05319162663775882187e0) *
                 r +
             1.0);
  } else {
    r -= 5.0;
    value = (((((((2.01033439929228813265e-7 * r + 2.71155556874348757815e-5) * r +
                  1.24266094738807843860e-3) *
                     r +
                 2.65321895265761230930e-2) *
                    r +
                2.96560571828504891230e-1) *
                   r +
               1.78482653991729133580e0) *
                  r +
              5.46378491116411436990e0) *
                 r +
             6.65790464350110377720e0) /
            (((((((2.04426310338993978564e-15 * r + 1.42151175831644588870e-7) * r +
                  1.84631831751005468180e-5) *
                     r +
                 7.86869131145613259100e-4) *
                    r +
                1.48753612908506148525e-2) *
                   r +
               1.36929880922735805310e-1) *
                  r +
              5.99832206555887937690e-1) *
                 r +
             1.0);
  }
  return q < 0.0 ? -value : value;
}

UniformStream::UniformStream(DrawPurpose purpose, std::int64_t session_ordinal,
                             std::int64_t replicate)
    : generator_(qr::replay::SeedSequence::from_entropy(std::vector<std::uint64_t>{
          qr::replay::kProgramSeed, kM25Tag, static_cast<std::uint64_t>(purpose),
          static_cast<std::uint64_t>(session_ordinal), static_cast<std::uint64_t>(replicate)})) {}

double UniformStream::next() noexcept {
  // numpy `random_standard_uniform`: (next_uint64() >> 11) * (1 / 2^53).
  return static_cast<double>(generator_.next_uint64() >> 11) * (1.0 / 9007199254740992.0);
}

SkillDraws build_skill_draws(const SessionTape& tape, std::int64_t replicate) {
  SkillDraws draws;
  const std::size_t n = tape.rows.size();
  draws.row_count = n;
  draws.net_z.resize(qr::replay::kHorizonCount);
  for (std::size_t h = 0; h < qr::replay::kHorizonCount; ++h) {
    draws.net_z[h] = normal_scores(tape, h);
  }

  std::int64_t ok_rows = 0;
  std::int64_t stopped = 0;
  for (const ScoredAction& row : tape.rows) {
    if (row.label.state != LabelState::OK) {
      ++draws.unavailable_rows;
      continue;
    }
    ++ok_rows;
    if (row.label.stop_hit[kHorizonRefIndex] != 0) {
      ++stopped;
    }
  }
  draws.stop_rate_h_ref = ok_rows > 0 ? static_cast<double>(stopped) / static_cast<double>(ok_rows) : 0.0;
  const double p = draws.stop_rate_h_ref;
  draws.stop_threshold = ndtri(1.0 - p);

  draws.risk_latent.resize(n);
  draws.net_noise.resize(n);
  draws.risk_noise.resize(n);

  // ONE stream per (session, replicate), consumed in row order, three draws per
  // row, in this fixed order. Independent of Q by construction.
  UniformStream stream(DrawPurpose::SKILL, tape.session_ordinal, replicate);
  for (std::size_t i = 0; i < n; ++i) {
    const double u_net = stream.next();
    const double u_risk = stream.next();
    const double u_latent = stream.next();
    draws.net_noise[i] = ndtri(u_net);
    draws.risk_noise[i] = ndtri(u_risk);

    // The latent that REPRODUCES the truth bit: y > t exactly when stop_hit.
    const bool stop = tape.rows[i].label.state == LabelState::OK &&
                      tape.rows[i].label.stop_hit[kHorizonRefIndex] != 0;
    double u_conditioned = 0.0;
    if (stop) {
      u_conditioned = (1.0 - p) + u_latent * p;
    } else {
      u_conditioned = u_latent * (1.0 - p);
    }
    // Guard the closed endpoints the inverse CDF cannot represent.
    u_conditioned = std::min(std::max(u_conditioned, 1e-300), std::nextafter(1.0, 0.0));
    draws.risk_latent[i] = ndtri(u_conditioned);
  }
  return draws;
}

void apply_skill(const SkillDraws& draws, double q_skill, std::size_t horizon_index,
                 SessionTape* tape) {
  if (tape == nullptr || tape->rows.size() != draws.row_count) {
    qr::detail::fail_fast("qr_m25::apply_skill: draws do not belong to this tape");
  }
  if (horizon_index >= qr::replay::kHorizonCount) {
    qr::detail::fail_fast("qr_m25::apply_skill: horizon index outside the frozen 7-menu");
  }
  if (!(q_skill >= 0.0) || !(q_skill <= 1.0)) {
    qr::detail::fail_fast("qr_m25::apply_skill: skill outside [0,1]");
  }
  const std::vector<double>& z = draws.net_z[horizon_index];
  const double residual = std::sqrt(std::max(0.0, 1.0 - q_skill * q_skill));
  const double t = draws.stop_threshold;
  const bool perfect = q_skill >= 1.0;

  for (std::size_t i = 0; i < tape->rows.size(); ++i) {
    ScoredAction& row = tape->rows[i];
    row.predicted_net_h_star = q_skill * z[i] + residual * draws.net_noise[i];
    if (perfect) {
      row.predicted_stop_prob_h_ref =
          (row.label.state == qr::replay::LabelState::OK && row.label.stop_hit[kHorizonRefIndex] != 0)
              ? 1.0
              : 0.0;
    } else {
      const double observed = q_skill * draws.risk_latent[i] + residual * draws.risk_noise[i];
      row.predicted_stop_prob_h_ref = 1.0 - ndtr((t - q_skill * observed) / residual);
    }
  }
}

}  // namespace qr::m25
