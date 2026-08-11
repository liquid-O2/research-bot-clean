// qr_carriers/normalization.hpp — TRAIN-ONLY EQUAL-SESSION NORMALIZATION.
//
// SPEC (evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 4, verbatim):
//
//   "For each continuous feature and TRAIN session s, use only finite present
//    values to compute `m_s=mean(x)` and `q_s=mean(x^2)`. Across the `S` TRAIN
//    sessions having at least one present value, `mu=mean_s(m_s)` and
//    `scale=sqrt(max(mean_s(q_s)-mu^2,0))`; S=0 gives `(mu,scale)=(0,1)` and
//    scale<1e-6 becomes 1. Apply `(x-mu)/scale`, clip [-8,8], and write 0 when
//    missing while retaining its presence bit. Binary/categorical/mask fields
//    are never centered or scaled. This is equal-session, TRAIN-only
//    normalization; every per-feature `(S,mu,scale)` is hashed."
//
// SPEC (section 4, the channel paragraph): "Continuous normalization is fit with
// equal session weight on TRAIN sessions only, scale floor 1e-6->1, clipped
// [-8,8], then frozen."
//
// WHAT THIS LANE DELIVERS AND WHAT IT DOES NOT. WP8a builds the COMPUTATION and
// its hash as a library — the accumulators, the two-level equal-session
// reduction, the floors, the clip and the digest. The FIT ITSELF runs later,
// when the TRAIN fold's sessions exist as built feature tapes; nothing here
// opens a session or decides which sessions are TRAIN. That separation is the
// point: the fold walls (section 1) belong to the runner, and a library that
// could choose its own sessions would be a second authority on them.
//
// EQUAL SESSION WEIGHT IS TWO LEVELS, NOT ONE. `mu` is the mean OVER SESSIONS of
// each session's own mean — never the pooled mean of all values, which would
// weight a busy session more than a quiet one. `scale` is built from the
// same-shaped mean of per-session second moments. A single-level pooled
// implementation is the defect this two-level shape exists to make impossible.
//
// THE SCALE FLOOR IS A FLOOR, NOT A CLAMP OF THE DATA. `scale < 1e-6 -> 1`
// replaces a degenerate SCALE; it never limits a value's range. The clip
// `[-8,8]` is applied to the STANDARDIZED value and is the card's own law.
#ifndef QR_CARRIERS_NORMALIZATION_HPP
#define QR_CARRIERS_NORMALIZATION_HPP

#include <cstdint>
#include <span>
#include <string>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_core/validity.hpp"

namespace qr::carriers {

/// The scale floor and the clip bound, from the card.
inline constexpr double kScaleFloor = 1e-6;
inline constexpr double kNormalizationClip = 8.0;

/// One feature's moments within ONE session, over FINITE PRESENT values only.
struct SessionMoments {
  double sum = 0.0;
  double sum_squares = 0.0;
  std::int64_t count = 0;

  /// Observes one value. A missing or non-finite value is not observed at all —
  /// "use only finite present values".
  void observe(double value) noexcept;
  /// Observes a typed channel value, which is the same rule stated once.
  void observe_typed(double value, Validity validity) noexcept;

  [[nodiscard]] bool present() const noexcept { return count > 0; }
  /// `m_s = mean(x)`.
  [[nodiscard]] double first_moment() const noexcept;
  /// `q_s = mean(x^2)`.
  [[nodiscard]] double second_moment() const noexcept;
};

/// One feature's FROZEN normalization.
struct FeatureNormalization {
  /// `S`: TRAIN sessions having at least one present value.
  std::int64_t sessions = 0;
  double mu = 0.0;
  double scale = 1.0;
  /// False for binary/categorical/mask features: they are "never centered or
  /// scaled", and `apply` returns them untouched and unclipped.
  bool centered = true;

  /// `(x-mu)/scale`, clipped to [-8,8]. Identity for a non-centered feature.
  [[nodiscard]] double apply(double value) const noexcept;
};

/// Accumulates per-session moments across TRAIN sessions with EQUAL session
/// weight, then freezes `(S, mu, scale)` per feature.
class NormalizationFitter {
 public:
  /// `continuous[i] == 0` marks feature `i` binary/categorical/mask.
  NormalizationFitter(std::size_t feature_count, std::span<const std::uint8_t> continuous);

  /// Folds ONE TRAIN session's per-feature moments. A feature with no present
  /// value in this session contributes nothing and does not increment its `S`.
  [[nodiscard]] Expected<bool, Refusal> observe_session(std::span<const SessionMoments> moments);

  /// The frozen table. `S=0` gives `(mu,scale)=(0,1)`; `scale<1e-6` becomes 1.
  [[nodiscard]] std::vector<FeatureNormalization> freeze() const;

  [[nodiscard]] std::size_t feature_count() const noexcept { return feature_count_; }
  [[nodiscard]] std::int64_t sessions_observed() const noexcept { return sessions_observed_; }

 private:
  std::size_t feature_count_;
  std::vector<std::uint8_t> continuous_;
  std::vector<double> sum_first_;
  std::vector<double> sum_second_;
  std::vector<std::int64_t> sessions_;
  std::int64_t sessions_observed_ = 0;
};

/// The canonical field-by-field rendering of the frozen table — one
/// `index<TAB>S<TAB>mu<TAB>scale<TAB>centered` line per feature, `%.17g` so the
/// text round-trips the double exactly.
[[nodiscard]] std::string render_normalization(std::span<const FeatureNormalization> table);

/// "every per-feature `(S,mu,scale)` is hashed" — the sha256 of exactly that
/// canonical rendering.
[[nodiscard]] std::string normalization_sha256(std::span<const FeatureNormalization> table);

}  // namespace qr::carriers

#endif  // QR_CARRIERS_NORMALIZATION_HPP
