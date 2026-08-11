// qr_wave2/variance_budget.hpp — W2.2, THE VARIANCE BUDGET (exactly 8 channels).
//
// SPEC (design/DESIGN_FEATURES.md sha bf70dd35e5407863, §W2.2-PIN-1, verbatim):
//
//   "r(s) = 1e4 * dln(m) per valid 1s grid step (bps). B components are
//    VARIANCE RATES in bps^2/s: RV_1m = Sum_{60s} r^2/60; RV_5m =
//    Sum_{300s} r^2/300; RV_prior = EWMA_{alpha=0.06} over prior sessions of
//    (Sum_RTH r^2)/T_RTH, seed = first observed session's value (ordinal 0
//    under WarmupScope; converged by s125). B(t) = 0.5*RV_1m + 0.3*RV_5m +
//    0.2*RV_prior.
//    X set (reversal_bps DROPPED — candidate-row field, not a carrier;
//    normalizing it is the arm's input transform, not this family): X_open,
//    X_high, X_low, X_vwap (sigma-oriented bps displacements from open /
//    running session high / running session low / running VWAP) and X_range
//    (H_t-L_t running range, bps). Anchors/tau: open & VWAP & range => tau =
//    t_since_open; high/low => tau = t - t_of_current_running_extreme (the
//    family's OWN accumulator tracks extreme timestamps — location module is
//    NOT edited). tau_min = 10s: tau < 10 => typed, never divided.
//    Channels: 1-5 Xtilde = X/sqrt(B*tau); 6 budget_consumed =
//    (Sum_{open..t} r^2)/RV_prior_TOTAL where RV_prior_TOTAL = EWMA_{0.06} of
//    prior sessions' Sum_RTH r^2 (same accumulator family, total form; guard
//    >0); 7 logB = ln B(t); 8 dlogB_60 = ln B(t) - ln B(t-60s). Destruction
//    twin: B_const = equal-weight time-mean of B(t) over the session's valid
//    seconds, substituted session-constant (dlogB == 0)."
//
// ONE SERIES, ONE CLOCK. r, B, the running extremes and every X are all read
// off the SAME frozen 1s midpoint grid (qr_carriers/grid_1s.hpp), because the
// pin defines r "per valid 1s grid step" and defines tau for high/low as the
// age of the current running extreme — an age only a timestamped series can
// give. The five X displacements themselves are the location law's own
// quantities, so they use the location law's own arithmetic:
// "Every oriented distance is `sigma*(m-reference)*10000/reference`; range is
// `(high-low)*10000/open`" (task card V4 section 5, quoted in
// qr_carriers/location.hpp) — this family scales them by the budget, it does
// not redefine them, and the location module itself is untouched per the pin.
//
// WINDOWS ARE WHOLE OR THEY ARE MISSING. RV_1m at second 30 would have to
// pretend the thirty seconds before the open had zero variance; that is the
// zero-imputation the arithmetic law forbids, so a window that does not fit
// inside the elapsed session is typed MISSING and B with it. Inside a fitting
// window, invalid steps (a grid gap) contribute nothing and the denominator
// stays the pin's fixed 60/300 — but a window with NO valid step is MISSING
// too, which is the frozen grid law's own "missing with fewer than two valid
// points" carried onto a window.
#ifndef QR_WAVE2_VARIANCE_BUDGET_HPP
#define QR_WAVE2_VARIANCE_BUDGET_HPP

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <vector>

#include "qr_carriers/channels.hpp"
#include "qr_carriers/grid_1s.hpp"
#include "qr_carriers/streams.hpp"
#include "qr_core/refusal.hpp"
#include "qr_wave2/prior_state.hpp"

namespace qr::wave2 {

using carriers::Side;

/// The frozen component weights (A3 / W2.2-PIN-1).
inline constexpr double kWeightRv1m = 0.5;
inline constexpr double kWeightRv5m = 0.3;
inline constexpr double kWeightRvPrior = 0.2;
/// The two intraday windows, in seconds.
inline constexpr std::int64_t kRv1mSeconds = 60;
inline constexpr std::int64_t kRv5mSeconds = 300;
/// "tau_min = 10s: tau < 10 => typed, never divided."
inline constexpr std::int64_t kTauMinSeconds = 10;
/// The innovation lag of channel 8.
inline constexpr std::int64_t kDeltaLogBSeconds = 60;

// ---------------------------------------------------------------------------
// The eight channels, in the pin's own order.
// ---------------------------------------------------------------------------

enum VarianceBudgetChannel : std::size_t {
  kVbXtildeOpen = 0,
  kVbXtildeHigh = 1,
  kVbXtildeLow = 2,
  kVbXtildeVwap = 3,
  kVbXtildeRange = 4,
  kVbBudgetConsumed = 5,
  kVbLogB = 6,
  kVbDeltaLogB60 = 7,
};
inline constexpr std::size_t kVarianceBudgetChannelCount = 8;
static_assert(kVarianceBudgetChannelCount == 8,
              "W2.2-PIN-1: exactly 8 channels; the enumeration binds");

/// How each channel reflects when the action side flips (the orientation law of
/// qr_carriers/channels.hpp, applied to this family). Range is NOT oriented —
/// it is a width, and the location law writes it without sigma.
inline constexpr std::array<carriers::OrientKind, kVarianceBudgetChannelCount>
    kVarianceBudgetOrientation{
        carriers::OrientKind::SIGMA,      // Xtilde from open
        carriers::OrientKind::SIGMA,      // Xtilde from running high
        carriers::OrientKind::SIGMA,      // Xtilde from running low
        carriers::OrientKind::SIGMA,      // Xtilde from running VWAP
        carriers::OrientKind::INVARIANT,  // Xtilde of the running range
        carriers::OrientKind::INVARIANT,  // budget consumed
        carriers::OrientKind::INVARIANT,  // log B
        carriers::OrientKind::INVARIANT,  // dlog B over 60s
    };

[[nodiscard]] const char* variance_budget_channel_name(std::size_t channel) noexcept;
/// False for none of them: all eight are continuous and TRAIN-normalized.
[[nodiscard]] bool variance_budget_channel_is_continuous(std::size_t channel) noexcept;

using VarianceBudgetRow = carriers::ChannelRow<kVarianceBudgetChannelCount>;
using VarianceBudgetCensus = carriers::ChannelCensus<kVarianceBudgetChannelCount>;

// ---------------------------------------------------------------------------
// The per-session accumulator.
// ---------------------------------------------------------------------------

/// Everything one session's budget reads. The grid and the print groups are
/// already built by qr_carriers; this family opens nothing itself.
struct VarianceBudgetInputs {
  const carriers::MidpointGrid* grid = nullptr;
  /// The stock-print groups, causal order, and their running VWAP sums — the
  /// same two prefix arrays the location layer takes.
  std::span<const carriers::GroupRecord> stock_print_groups;
  std::span<const std::int64_t> vwap_notional_prefix;
  std::span<const std::int64_t> vwap_size_prefix;
  /// The strictly-prior cross-session state (RV_prior rate and total).
  PriorView priors;
};

/// One session's budget series: B at every grid endpoint, the running extremes
/// with their timestamps, and the eight channels at any endpoint.
class VarianceBudgetSession {
 public:
  [[nodiscard]] static Expected<VarianceBudgetSession, Refusal> build(
      const VarianceBudgetInputs& inputs, const DestructionControls& controls = {});

  /// B(t) at an endpoint, in bps^2/s. MISSING before the windows fit, when no
  /// valid step is in a window, or when RV_prior is absent.
  [[nodiscard]] Typed<double> budget(std::size_t endpoint_index) const noexcept;

  /// sigma_scale(t) = sqrt(B(t)*1800) in bps — W2.13-PIN-1's z_vwap
  /// denominator, defined here because B is defined here.
  [[nodiscard]] Typed<double> sigma_scale_bps(std::size_t endpoint_index) const noexcept;

  /// The eight channels at one endpoint, for one side.
  [[nodiscard]] VarianceBudgetRow channels(std::size_t endpoint_index, Side side) const noexcept;

  /// The running VWAP (u6) at an endpoint, strictly-prior — W2.13 channels 13
  /// and 14 read the same series, so it is computed once, here.
  [[nodiscard]] Typed<std::int64_t> running_vwap_u6(std::size_t endpoint_index) const noexcept;
  /// The session's first present grid midpoint — W2.13-PIN-1's `O`.
  [[nodiscard]] Typed<std::int64_t> open_u6() const noexcept;

  [[nodiscard]] std::size_t endpoints() const noexcept { return present_.size(); }

  /// Audit counters, printed in full by the census tool.
  struct Census {
    std::int64_t endpoints = 0;
    std::int64_t valid_steps = 0;
    std::int64_t budget_present = 0;
    std::int64_t budget_absent_window = 0;
    std::int64_t budget_absent_no_valid_step = 0;
    std::int64_t budget_absent_no_prior = 0;
    std::int64_t destruction_constant_budget = 0;
  };
  [[nodiscard]] const Census& census() const noexcept { return census_; }

 private:
  VarianceBudgetSession() = default;

  /// Sum of r^2 over the valid steps ending in `(index-seconds, index]`, or an
  /// absent optional when the window does not fit or holds no valid step.
  [[nodiscard]] std::optional<double> window_sum_r2(std::size_t index,
                                                    std::int64_t seconds) const noexcept;

  std::vector<std::uint8_t> present_;
  std::vector<std::int64_t> mid_u6_;
  /// Cumulative sum of r^2 (bps^2) over valid steps up to and including i.
  std::vector<double> cum_r2_;
  /// Valid steps up to and including i — the window's "any valid step" test.
  std::vector<std::int64_t> cum_valid_steps_;
  /// B(t) per endpoint and its validity.
  std::vector<double> budget_;
  std::vector<std::uint8_t> budget_present_;
  /// Running extremes and the endpoint at which each was SET (first attainment).
  std::vector<std::int64_t> run_high_u6_;
  std::vector<std::int64_t> run_low_u6_;
  std::vector<std::int64_t> run_high_index_;
  std::vector<std::int64_t> run_low_index_;
  std::vector<std::uint8_t> run_present_;
  /// The running VWAP at each endpoint (u6), strictly-prior.
  std::vector<std::int64_t> vwap_u6_;
  std::vector<std::uint8_t> vwap_present_;

  std::int64_t open_u6_value_ = 0;
  bool open_present_ = false;
  /// RV_prior_TOTAL: channel 6's denominator, frozen at build from the
  /// strictly-prior EWMA (never recomputed per decision).
  double rv_prior_total_ = 0.0;
  Census census_{};
};

}  // namespace qr::wave2

#endif  // QR_WAVE2_VARIANCE_BUDGET_HPP
