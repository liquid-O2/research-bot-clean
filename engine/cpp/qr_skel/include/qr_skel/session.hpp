// qr_skel/session.hpp — the read-only session view the label engine walks.
//
// SPEC: design/PORT_M1B_S3_CONV.md C1. Source of truth is the QRSESS1 receipt
// pair written by qr_futsess_assemble, which M1.A gate A proved field-exact
// against the m0 Python session receipts.
#ifndef QR_SKEL_SESSION_HPP
#define QR_SKEL_SESSION_HPP

#include <cstdint>
#include <string>
#include <vector>

#include "qr_core/refusal.hpp"

namespace qr::skel {

using qr::Expected;
using qr::Refusal;
using qr::RefusalCode;

/// CC-M1-4 / D-054 MID-SANITY. A second is MID-SANE iff it is TWO_SIDED **and**
/// `spread_$ <= min(kSaneMedianMultiple x trailing-phase-median spread_$,
/// kSaneAbsoluteCapUsd)`. Wide-but-two-sided books produce phantom mid travel,
/// so every mid consumer -- this engine included -- must walk sane seconds only.
///
/// The two constants are transcribed from D-054. The per-(session, phase)
/// MEDIAN is an INPUT, not a constant: the law says "trailing-phase-median"
/// without pinning the trailing window, so the window belongs to whoever owns
/// that definition and this engine is handed the resulting numbers. With
/// `enabled == false` the mask is the identity and a second is sane iff it is
/// two-sided (the pre-D-054 behaviour, kept so earlier receipts reproduce).
inline constexpr double kSaneMedianMultiple = 10.0;
inline constexpr double kSaneAbsoluteCapUsd = 500.0;
inline constexpr std::size_t kPhaseCount = 3;

struct SanityPolicy {
  bool enabled = false;
  /// Median spread in DOLLARS per phase index (TOKYO, LONDON, NY).
  double phase_median_spread_usd[kPhaseCount] = {0.0, 0.0, 0.0};

  /// The sanity ceiling for a phase, in dollars.
  [[nodiscard]] double threshold_usd(std::int8_t phase) const;
};

class SessionView {
 public:
  /// Load `<dir>/<YYYYMMDD>.{bin,json}` and apply `policy` to the valid grid.
  [[nodiscard]] static Expected<SessionView, Refusal> load(const std::string& dir,
                                                           std::int32_t date8,
                                                           const SanityPolicy& policy = {});

  [[nodiscard]] std::int32_t n() const { return n_; }
  [[nodiscard]] std::int32_t date8() const { return date8_; }
  [[nodiscard]] const std::vector<double>& mid() const { return mid_; }
  [[nodiscard]] const std::vector<std::int8_t>& state() const { return state_; }
  [[nodiscard]] const std::vector<std::int8_t>& phase_tag() const { return phase_; }
  [[nodiscard]] const std::vector<double>& spread_usd() const { return spread_; }
  /// Ascending MID-SANE session seconds (two-sided, and inside the spread
  /// ceiling when the policy is enabled).
  [[nodiscard]] const std::vector<std::int32_t>& vt() const { return vt_; }
  /// Seconds that are TWO_SIDED but were excluded by the sanity mask, and the
  /// two-sided total they are measured against (CC-M1-4 `insane_frac`).
  [[nodiscard]] std::int32_t n_insane() const { return n_insane_; }
  [[nodiscard]] std::int32_t n_two_sided() const { return n_two_sided_; }
  /// mid at each valid second, same order as vt().
  [[nodiscard]] const std::vector<double>& vm() const { return vm_; }
  /// Index into vt() of the first valid second >= sec (lower_bound).
  [[nodiscard]] std::size_t vt_lower_bound(std::int32_t sec) const;
  /// CONV C1: first second strictly after `sec` whose phase differs, else n-1.
  [[nodiscard]] std::int32_t next_phase_boundary(std::int32_t sec) const;
  /// TRUE only for a MID-SANE second: an anchor on a wide-book second is
  /// UNAVAILABLE, not merely two-sided (CC-M1-4 rule 2).
  [[nodiscard]] bool is_valid_second(std::int32_t sec) const {
    return sec >= 0 && sec < n_ && sane_[static_cast<std::size_t>(sec)] != 0;
  }

 private:
  std::int32_t n_ = 0;
  std::int32_t date8_ = 0;
  std::vector<double> mid_;
  std::vector<std::int8_t> state_;
  std::vector<std::int8_t> phase_;
  std::vector<double> spread_;
  std::vector<std::uint8_t> sane_;
  std::vector<std::int32_t> vt_;
  std::vector<double> vm_;
  std::int32_t n_insane_ = 0;
  std::int32_t n_two_sided_ = 0;
};

}  // namespace qr::skel

#endif  // QR_SKEL_SESSION_HPP
