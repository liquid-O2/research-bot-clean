// qr_m25/twins.hpp — Q_max: THE TWIN-DISCORDANCE OBSERVABILITY CEILING.
//
// THE RULING, VERBATIM: "Q_max = the twin-discordance observability ceiling: the
// skill achievable when ranking only by information that survives label-twin
// discordance (fresh-label twins = same (session,side,clock-bucket) actions with
// identical causal-prefix keys but different outcomes bound the attainable rank
// fidelity)".
//
// WHY THE LITERAL FORM IS EMPTY ON THIS OBJECT, MEASURED. The ruling's twin is
// an EXACT match: two actions of the same (session, side, clock-bucket) whose
// causal-prefix keys are identical. The causal prefix this campaign publishes is
// `features/direct_raw [N,3,60] f4` — per-modality continuous summaries over
// windows {1,5,30,120}s. On session 125 LONG there are 16,027 action rows and
// 16,027 DISTINCT direct_raw rows: ZERO exact twins, in the whole session. An
// exact-identity twin set is therefore empty by construction on continuous
// carriers, and a ceiling estimated from an empty set is not a ceiling. This is
// recorded here, in the code, because it is a property of the object and not a
// choice of this implementation.
//
// THE EXECUTABLE FORM (what this module computes). The twin argument does not
// actually need identical keys — it needs the CONDITIONAL VARIANCE of the
// outcome given the causal prefix, which is what discordance between
// indistinguishable actions measures. Write X = (session, side, clock-bucket,
// causal prefix) and z = the outcome's normal score (the SAME normal score the
// skill law corrupts, so the two numbers live on one axis). Any predictor
// measurable with respect to X has squared rank fidelity at most
//
//     rho_max^2 = Var(E[z|X]) / Var(z) = 1 - E[Var(z|X)] / Var(z),
//
// and for a matched pair (i,j) inside one cell of X,
//
//     E[(z_i - z_j)^2] = 2 * Var(z|X).
//
// So the ceiling is read off matched pairs. The pairs are formed by NEAREST
// NEIGHBOUR in the causal-prefix metric inside the (session, side, clock-bucket)
// cell — the closest thing to an identical key the data contains — and the
// residual mismatch is removed by EXTRAPOLATION: the k-th nearest neighbour
// ladder gives (mean prefix distance d_k, mean squared outcome gap D_k) for
// k = 1..K, D is fitted affinely in d, and the intercept D_0 = D(d -> 0) is the
// discordance an EXACT twin would have shown. Both numbers are published:
//
//   * Q_max (BINDING) = sqrt(max(0, 1 - D_0 / (2*Var z)))  — the exact-twin
//     ceiling the ruling names, estimated without the nearest-neighbour bias;
//   * Q_max_k1 (CONSERVATIVE PANEL) = the same with D_1 in place of D_0. Since
//     D_1 >= D_0, this is a lower ceiling and therefore a STRICTER gate.
//   * Q_max_clock_only (REFERENCE PANEL) = the same with ALL pairs of the cell,
//     i.e. the ceiling of a predictor that sees the clock bucket and the side
//     but nothing about the market at all.
//
// THE OVERLAP DEFECT, MEASURED, AND THE DISJOINT LADDER THAT ANSWERS IT.
// The twin identity E[(z_i - z_j)^2] = 2*Var(z|X) needs the two outcomes to be
// CONDITIONALLY INDEPENDENT draws given X. On this object the prefix-nearest
// neighbour of an action is almost always the action one or two seconds away —
// the 120s window summaries barely move in a second — and two actions two
// seconds apart held for fifteen minutes are very nearly THE SAME TRADE. Their
// outcomes are positively correlated by construction, the squared gap collapses,
// and the ceiling is pushed towards 1 for a purely mechanical reason. That is
// not a hypothesis: on the real corpus the OVERLAP-PERMITTING ladder returns
// q_max_k1 ~ 0.97 and even the clock-bucket-only reference returns ~0.94, which
// is not a statement about market predictability at all.
//
// So every pair is also accumulated under a DISJOINT ladder: a pair counts for
// horizon h only when the two trades' holding windows [entry, exit_h] do not
// overlap, i.e. neither is still open when the other opens. Those two outcomes
// are separate trades over separate price paths, which is what the identity
// requires. The disjoint ladder is horizon-specific by construction (the same
// two actions can be disjoint at 2 minutes and overlapping at an hour), and at
// horizons whose holding window exceeds the clock bucket it has NO support at
// all — that is reported as INSUFFICIENT_SUPPORT and never as a ceiling of 1.
//
// THE CLOCK BUCKET. Held constant inside a cell so the twin's discordance is not
// the predictable part of the time of day. Published as a curve over
// W in {15, 60, 300, 900, 3600} seconds. The BINDING value is the SMALLEST W
// whose disjoint ladder carries enough pairs at the horizon in question: the
// twin argument wants the two actions as clock-comparable as it can get them,
// and a wider bucket buys support by weakening exactly that.
//
// CELL CAP. A cell is capped at kTwinCellCap members by a deterministic stride,
// so the widest buckets cost what the narrow ones cost. The cap is a compute
// law, fixed here, never a function of a result.
//
// DIRECTION OF ERROR, STATED. Nearest neighbours are not identical, so D_1
// OVERSTATES the irreducible variance and Q_max_k1 UNDERSTATES the ceiling; the
// extrapolation removes that bias to first order. Overlapping pairs bias the
// other way and are quarantined in their own ladder. Neither panel can be
// tuned: K, the bucket widths, the cap, the metric, and the fit are fixed here.
#ifndef QR_M25_TWINS_HPP
#define QR_M25_TWINS_HPP

#include <array>
#include <cstdint>
#include <vector>

#include "qr_m25/skill.hpp"
#include "qr_m25/tape.hpp"

namespace qr::m25 {

/// The neighbour ladder depth. Fixed.
inline constexpr std::size_t kTwinLadderDepth = 8;

/// Clock-bucket widths, in seconds.
inline constexpr std::array<std::int64_t, 5> kTwinBucketSeconds = {15, 60, 300, 900, 3600};

/// Deterministic per-cell member cap (a compute law, not a statistical choice).
inline constexpr std::size_t kTwinCellCap = 512;

/// One session's contribution to the pooled ceiling, for one bucket width.
/// Everything is a SUM so folds pool by addition and nothing is averaged twice.
struct TwinAccumulator {
  /// Per neighbour rank k (0-based): pair count, summed prefix distance, and
  /// summed squared outcome gap per horizon.
  std::array<std::int64_t, kTwinLadderDepth> pair_count{};
  std::array<double, kTwinLadderDepth> distance_sum{};
  std::array<std::array<double, qr::replay::kHorizonCount>, kTwinLadderDepth> gap_sq_sum{};

  /// The DISJOINT ladder: same shape, but a pair counts at horizon h only when
  /// the two trades' holding windows do not overlap at that horizon.
  std::array<std::array<std::int64_t, qr::replay::kHorizonCount>, kTwinLadderDepth>
      disjoint_pair_count{};
  std::array<std::array<double, qr::replay::kHorizonCount>, kTwinLadderDepth>
      disjoint_distance_sum{};
  std::array<std::array<double, qr::replay::kHorizonCount>, kTwinLadderDepth>
      disjoint_gap_sq_sum{};

  /// All-pairs (clock-only) reference, per horizon, overlapping and disjoint.
  std::int64_t all_pair_count = 0;
  std::array<double, qr::replay::kHorizonCount> all_gap_sq_sum{};
  std::array<std::int64_t, qr::replay::kHorizonCount> all_disjoint_pair_count{};
  std::array<double, qr::replay::kHorizonCount> all_disjoint_gap_sq_sum{};

  /// Outcome variance denominator: sum over rows of (z - mean z)^2, and the row
  /// count, per horizon.
  std::array<double, qr::replay::kHorizonCount> z_centred_sq_sum{};
  std::int64_t z_row_count = 0;

  /// Census.
  std::int64_t cell_count = 0;
  std::int64_t rows_in_cells = 0;
  std::int64_t exact_key_twin_pairs = 0;  ///< pairs at distance EXACTLY zero.

  void add(const TwinAccumulator& other) noexcept;
};

/// The published ceiling numbers for one bucket width and one horizon.
struct TwinCeiling {
  double q_max = 0.0;            ///< extrapolated exact-twin ceiling, OVERLAP-PERMITTING
  double q_max_k1 = 0.0;         ///< nearest-neighbour ceiling, overlap-permitting
  double q_max_clock_only = 0.0; ///< clock-bucket-only ceiling (reference panel)
  double d0 = 0.0;               ///< extrapolated squared gap at distance zero
  double d1 = 0.0;               ///< nearest-neighbour squared gap
  double variance = 0.0;         ///< Var(z)

  /// The DISJOINT ladder's answers — the ones the identity actually licenses.
  double q_max_disjoint = 0.0;
  double q_max_disjoint_k1 = 0.0;
  double q_max_disjoint_clock_only = 0.0;
  double d0_disjoint = 0.0;
  double d1_disjoint = 0.0;
  std::int64_t disjoint_pairs = 0;  ///< nearest-neighbour disjoint pair support
};

[[nodiscard]] TwinCeiling twin_ceiling(const TwinAccumulator& accumulator, std::size_t horizon_index);

/// Accumulate one session at one bucket width. `prefix` is the row-aligned
/// standardised causal-prefix matrix (see `load_prefix_matrix`), `draws` supplies
/// the normal scores. Rows whose label is not OK carry no outcome and take no
/// part in any pair.
[[nodiscard]] TwinAccumulator accumulate_twins(const SessionTape& tape, const SkillDraws& draws,
                                               const std::vector<float>& prefix,
                                               std::size_t prefix_width,
                                               std::int64_t bucket_seconds);

/// Read `features/direct_raw.npy` from both side shards and return it ROW
/// ALIGNED WITH `tape.rows`, standardised column-wise inside the session
/// (zero-variance columns become zero). Refuses CONTENT_MISMATCH when a tape row
/// has no matching shard row.
[[nodiscard]] Expected<std::vector<float>, Refusal> load_prefix_matrix(const TapeRoot& root,
                                                                       const SessionTape& tape,
                                                                       std::size_t* width_out);

}  // namespace qr::m25

#endif  // QR_M25_TWINS_HPP
