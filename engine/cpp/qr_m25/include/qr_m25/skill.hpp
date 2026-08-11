// qr_m25/skill.hpp — THE PARAMETRIC SKILL LAW of the M2.5 gate (FINAL_PLAN.md
// section 8 item 1; the registered G2 shape).
//
// THE BRIEF, VERBATIM: "operationalize Q* per the registered G2 design:
// parametric skill sweep — score = true net_h corrupted by rank-noise at skill
// level Q (Q=1 perfect ranking -> Q=0 random), find minimal Q clearing the bar
// via the gate family's best admissible cell".
//
// THE LAW, WRITTEN OUT. Inside ONE session, over its N action rows (both sides
// together, because the kernel's selection at a clock compares the two sides):
//
//   1. TRUTH IN NORMAL SCORES.  r_i = the 1-based ascending rank of the row's
//      own `menu_net_cent[h]`; z_i = Phi^-1((r_i - 0.5)/N) — the van der Waerden
//      / Hazen normal score. It is a STRICTLY MONOTONE transform of the truth,
//      so ranking by z is ranking by net, exactly; it exists so the corruption
//      below has a scale that is the same in every session and every horizon.
//      Ties and unavailable labels: rows whose `label_state != OK` have no net
//      at all and rank BELOW every OK row (they can never trade — the kernel
//      types them NO_FRESH_FILL — so a skilled agent puts them last); ties in
//      net break by `(decision_ordinal, side)`, which is a total order because
//      the prediction key is one-to-one.
//
//   2. THE CORRUPTION (Gaussian copula, correlation exactly Q).
//         score_i(Q) = Q * z_i + sqrt(1 - Q^2) * e_i,     e_i ~ N(0,1) iid.
//      Q is therefore literally the normal-score (rank) correlation between the
//      agent's ranking signal and the truth: Q=1 gives score = z (PERFECT
//      ranking), Q=0 gives score = e (RANDOM ranking), and every value between
//      is a real, calibrated amount of ranking skill. Nothing here is a proxy
//      for skill; it IS the rank-fidelity parameter, which is what makes it
//      comparable to the twin ceiling Q_max, measured in the same units.
//
//   3. THE RISK CHANNEL, CALIBRATED (the A6 gate's second clause needs a
//      PROBABILITY, not a score: "predicted P(stop before h_ref) <= rho").
//      Let S_i = `stop_hit[h_ref]` and p = the session's OK-row stop rate at
//      h_ref, t = Phi^-1(1 - p).  Draw the latent y_i ~ N(0,1) CONDITIONED on
//      the truth it must reproduce — y_i > t exactly when S_i = 1 — by inverse
//      CDF on the correct tail.  The agent observes r_i = Q*y_i + sqrt(1-Q^2)*f_i
//      with f_i ~ N(0,1) iid, and reports the exact posterior
//         P(S_i = 1 | r_i) = 1 - Phi( (t - Q*r_i) / sqrt(1 - Q^2) ).
//      At Q=1 this is the truth bit itself; at Q=0 it is the base rate p for
//      every row (a gate at rho >= p then admits everything, and at rho < p
//      nothing — which is the honest behaviour of a zero-skill risk head).
//      The same skill Q drives both channels because Q is the skill of ONE
//      agent, and the two noises are independent draws.
//
//   4. COMMON RANDOM NUMBERS.  e_i, f_i and the latent draw are taken ONCE per
//      (session, replicate) in row order and REUSED at every Q, so the Q-sweep
//      is a deterministic monotone-in-Q family on one noise realisation rather
//      than 21 unrelated experiments. That is what makes "the minimal Q clearing
//      the bar" a well-defined number instead of a sampling artefact.
//
//   5. THE SEED.  `SeedSequence([20260810, 3486317, session_ordinal, replicate])`
//      with 3486317 = int.from_bytes(b"m25", "little") — the brief's
//      `SeedSequence(20260810,"m25",...)` written in the only entropy alphabet
//      numpy's SeedSequence has (uint32 words), by the same little-endian byte
//      coercion numpy itself uses. The stream is the numpy-parity PCG64 the
//      replay kernel already carries (qr_replay/pcg64.hpp), so every draw is
//      reproducible from Python with
//      `numpy.random.Generator(PCG64(SeedSequence([...]))).random()`.
//
// RESULT-BLINDNESS. Every constant above (the seed, the tag, the grid, the
// normal-score convention, the tie order) is fixed here, before any number is
// computed, and none of them is a function of any result.
#ifndef QR_M25_SKILL_HPP
#define QR_M25_SKILL_HPP

#include <cstdint>
#include <vector>

#include "qr_m25/tape.hpp"
#include "qr_replay/pcg64.hpp"

namespace qr::m25 {

/// int.from_bytes(b"m25", "little") — the brief's "m25" seed word.
inline constexpr std::uint64_t kM25Tag = 3486317;

/// The FIXED comparability horizon of the card's h-LAW: "all horizon-bound heads
/// bind to the FIXED comparability horizon h_ref = 15 min". Index 2 of
/// {2,5,15,30,60,120,close}.
inline constexpr std::size_t kHorizonRefIndex = 2;

/// Phi^-1, Wichura's AS241 (PPND16): |relative error| < 1e-16 over the whole
/// open unit interval. Chosen over a rational-approximation "good enough to
/// 1e-9" because these numbers are the scale of the skill axis itself.
[[nodiscard]] double ndtri(double p) noexcept;

/// Phi, via std::erfc — the exact complement so the far tail keeps its digits.
[[nodiscard]] double ndtr(double x) noexcept;

/// numpy-parity uniform doubles from the numpy-parity PCG64: `(next_uint64() >>
/// 11) * 2^-53`, which is `random_standard_uniform` verbatim.
/// What a uniform stream is FOR. The purpose is part of the seed so two
/// different M2.5 randomisations of the same session can never share draws.
enum class DrawPurpose : std::uint64_t {
  SKILL = 0,           ///< the corruption noises and the risk latent
  DECOMPOSITION_COIN = 1,  ///< the per-clock control coin of the decomposition panel
};

class UniformStream {
 public:
  /// `SeedSequence([20260810, kM25Tag, purpose, session_ordinal, replicate])`.
  UniformStream(DrawPurpose purpose, std::int64_t session_ordinal, std::int64_t replicate);

  [[nodiscard]] double next() noexcept;

 private:
  qr::replay::Pcg64 generator_;
};

/// Everything about one session that does not depend on Q: the truth normal
/// scores at each horizon, the conditioned latents, and the two noise vectors.
/// Built ONCE per (session, replicate) and swept over Q.
struct SkillDraws {
  std::size_t row_count = 0;

  /// Truth normal scores, per horizon: `net_z[h][i]`.
  std::vector<std::vector<double>> net_z;

  /// The risk latent, the two noise vectors, and the session's h_ref stop rate.
  std::vector<double> risk_latent;
  std::vector<double> net_noise;
  std::vector<double> risk_noise;
  double stop_rate_h_ref = 0.0;
  double stop_threshold = 0.0;  ///< t = Phi^-1(1 - p); +/-inf at a degenerate rate.

  /// Census: rows whose label is not OK (ranked below every OK row).
  std::int64_t unavailable_rows = 0;
};

/// Build the Q-independent draws for one session at one replicate.
[[nodiscard]] SkillDraws build_skill_draws(const SessionTape& tape, std::int64_t replicate);

/// Write the skill-Q agent's two predictions into `tape.rows` for horizon `h`.
/// `q_skill` must be in [0,1]; the endpoints are exact (Q=1 writes the truth
/// bit as the stop probability, not a probability near it).
void apply_skill(const SkillDraws& draws, double q_skill, std::size_t horizon_index,
                 SessionTape* tape);

}  // namespace qr::m25

#endif  // QR_M25_SKILL_HPP
