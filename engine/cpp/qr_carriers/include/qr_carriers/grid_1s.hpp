// qr_carriers/grid_1s.hpp — THE PREFIX 1s MIDPOINT GRID.
//
// SPEC (evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 4, verbatim):
//
//   "The prefix 1s midpoint grid never crosses a session. At each complete-second
//    endpoint it carries the last finite, positive, two-sided, strictly unlocked/
//    noncrossed (`ask>bid`), condition-eligible IWM NBBO midpoint whose timestamp
//    is strictly before that endpoint; before the first valid quote it is
//    missing. Carry has no hard timeout: source age in microseconds and
//    `fresh_in_bin` are separate channels, and `stale_gt_1s` is diagnostic only.
//    These three fields are grid-audit fields, not additional model columns. A
//    carried unchanged midpoint contributes a zero return; RV requires two
//    present consecutive endpoints. The partial second containing cutoff and all
//    equal-cutoff groups are excluded."
//
// SPEC (section 5): "Prefix RV at 1/5/30s is `sqrt(sum(log(m_t/m_{t-1})^2))` on
// the prior complete 1s midpoint grid and is missing with fewer than two valid
// points."
//
// NO TIMEOUT MEANS NO TIMEOUT. The carry never expires and `stale_gt_1s` gates
// nothing — it is a diagnostic bit beside a continuous age, exactly as the card
// says. An implementation that dropped a carried midpoint after some horizon
// would be inventing an unregistered staleness cutoff, which the same section
// forbids for attachment age in the same words.
//
// WHY THE ENDPOINT AT THE CUTOFF SECOND IS LAWFUL. A decision instant is
// `session_start + decision_second * 1e9` (section 3), so it IS a whole-second
// endpoint, and that endpoint's value is the last valid midpoint STRICTLY BEFORE
// it. The excluded "partial second containing cutoff" is the one that would end
// after the cutoff; the second ending exactly at the cutoff is complete and its
// endpoint reads only strictly-prior quotes.
//
// THE SOURCE SERIES IS THE ELIGIBLE-GROUP MIDPOINT, not a per-row midpoint: the
// card's scalar-means-before-derived law makes a group's midpoint the quantity
// derived from its two price means (qr_nbbo::GroupScalars / NbboScalars::mid),
// and eligibility already carries finite/positive/two-sided/ask>bid/condition-0.
#ifndef QR_CARRIERS_GRID_1S_HPP
#define QR_CARRIERS_GRID_1S_HPP

#include <cstdint>
#include <optional>
#include <span>
#include <vector>

#include "qr_carriers/streams.hpp"
#include "qr_carriers/transforms.hpp"
#include "qr_clock/session_clock.hpp"
#include "qr_core/refusal.hpp"

namespace qr::carriers {

/// One complete-second endpoint of the grid.
struct GridPoint {
  /// The carried midpoint, u6. Meaningful only when `present`.
  std::int64_t mid_u6 = 0;
  /// Age of the carried midpoint's SOURCE group at this endpoint, in checked
  /// integer microseconds. A grid-audit field.
  std::int64_t age_micros = 0;
  bool present = false;
  /// The source group's timestamp lies inside this endpoint's own one-second
  /// bin `[endpoint-1s, endpoint)`. A grid-audit field.
  bool fresh_in_bin = false;
  /// Diagnostic only — it gates nothing.
  bool stale_gt_1s = false;
};

/// The whole session's grid. `endpoint(i) = session_start + i seconds`, for
/// `i = 0 .. bar_count*60`, so the last endpoint is the session close and the
/// grid never crosses a session.
class MidpointGrid {
 public:
  /// Builds the grid from the session's ELIGIBLE NBBO group midpoints, in causal
  /// order (`NbboStream::eligible_midpoints()`).
  [[nodiscard]] static Expected<MidpointGrid, Refusal> build(
      const SessionClock& clock, std::span<const NbboStream::EligibleMid> eligible);

  [[nodiscard]] const std::vector<GridPoint>& points() const noexcept { return points_; }
  [[nodiscard]] std::size_t size() const noexcept { return points_.size(); }
  [[nodiscard]] std::int64_t endpoint_ns(std::size_t index) const noexcept {
    return session_start_ns_ + static_cast<std::int64_t>(index) * kNanosPerSecond;
  }

  /// The greatest complete-second endpoint at or before `cutoff_ns_a`, i.e. the
  /// last endpoint of "the prior complete 1s midpoint grid". Absent when the
  /// cutoff is before the session start or AT OR PAST THE GRID END — the grid's
  /// final endpoint is the session close, and the card makes that a terminal
  /// carry endpoint and "never a decision instant" (section 3), so no lawful
  /// cutoff ever resolves to it. Absent means absent: this never clamps a
  /// cutoff onto the close and hands back the close's carried value.
  [[nodiscard]] std::optional<std::size_t> prefix_endpoint(
      std::int64_t cutoff_ns_a) const noexcept;

  /// `sqrt(sum(log(m_t/m_{t-1})^2))` over the `seconds` returns ending at
  /// `endpoint_index`. "A carried unchanged midpoint contributes a zero return"
  /// (log(m/m) = 0, so this falls out of the formula rather than being a case);
  /// "missing with fewer than two valid points".
  [[nodiscard]] Typed<double> realized_volatility(std::size_t endpoint_index,
                                                  std::int64_t seconds) const noexcept;

  /// Grid audit counters, printed in full by the probe.
  struct Census {
    std::int64_t endpoints = 0;
    std::int64_t present = 0;
    std::int64_t fresh_in_bin = 0;
    std::int64_t stale_gt_1s = 0;
    std::int64_t first_present_endpoint = -1;
  };
  [[nodiscard]] Census census() const noexcept;

 private:
  std::vector<GridPoint> points_;
  std::int64_t session_start_ns_ = 0;
};

}  // namespace qr::carriers

#endif  // QR_CARRIERS_GRID_1S_HPP
