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

class SessionView {
 public:
  /// Load `<dir>/<YYYYMMDD>.{bin,json}`.
  [[nodiscard]] static Expected<SessionView, Refusal> load(const std::string& dir,
                                                           std::int32_t date8);

  [[nodiscard]] std::int32_t n() const { return n_; }
  [[nodiscard]] std::int32_t date8() const { return date8_; }
  [[nodiscard]] const std::vector<double>& mid() const { return mid_; }
  [[nodiscard]] const std::vector<std::int8_t>& state() const { return state_; }
  [[nodiscard]] const std::vector<std::int8_t>& phase_tag() const { return phase_; }
  /// Ascending valid session seconds (state == ST_TWO_SIDED).
  [[nodiscard]] const std::vector<std::int32_t>& vt() const { return vt_; }
  /// mid at each valid second, same order as vt().
  [[nodiscard]] const std::vector<double>& vm() const { return vm_; }
  /// Index into vt() of the first valid second >= sec (lower_bound).
  [[nodiscard]] std::size_t vt_lower_bound(std::int32_t sec) const;
  /// CONV C1: first second strictly after `sec` whose phase differs, else n-1.
  [[nodiscard]] std::int32_t next_phase_boundary(std::int32_t sec) const;
  [[nodiscard]] bool is_valid_second(std::int32_t sec) const {
    return sec >= 0 && sec < n_ && state_[static_cast<std::size_t>(sec)] == 0;
  }

 private:
  std::int32_t n_ = 0;
  std::int32_t date8_ = 0;
  std::vector<double> mid_;
  std::vector<std::int8_t> state_;
  std::vector<std::int8_t> phase_;
  std::vector<std::int32_t> vt_;
  std::vector<double> vm_;
};

}  // namespace qr::skel

#endif  // QR_SKEL_SESSION_HPP
