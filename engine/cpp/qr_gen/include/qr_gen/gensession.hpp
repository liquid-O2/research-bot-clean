// qr_gen/gensession.hpp — the session view generation needs.
//
// It is qr_skel::SessionView (the MID-SANE grid, CC-M1-4 / D-054, whose mask
// definition is handed over from engine/port_m1/b7_sane.py as a QRSANE1 receipt
// — ONE definition of the mask program-wide) PLUS the three things generation
// reads that the label engine never did: the trade tape (causal VWAP levels),
// the dominant instrument id and its update share (roster fields).
//
// SessionView is reused unchanged rather than re-derived: a second reading of
// "which seconds exist" is exactly the defect D-054 was raised against.
#ifndef QR_GEN_GENSESSION_HPP
#define QR_GEN_GENSESSION_HPP

#include <cstdint>
#include <string>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_skel/session.hpp"

namespace qr::gen {

using qr::Expected;
using qr::Refusal;
using qr::RefusalCode;

class GenSession {
 public:
  [[nodiscard]] static Expected<GenSession, Refusal> load(const std::string& dir,
                                                          std::int32_t date8,
                                                          const qr::skel::SanityPolicy& policy);

  [[nodiscard]] const qr::skel::SessionView& view() const { return view_; }
  [[nodiscard]] std::int32_t n() const { return view_.n(); }
  [[nodiscard]] const std::vector<std::int32_t>& vt() const { return view_.vt(); }
  [[nodiscard]] const std::vector<double>& vm() const { return view_.vm(); }
  [[nodiscard]] const std::vector<std::int8_t>& phase_tag() const { return view_.phase_tag(); }

  /// Raw trade tape (ts_event seconds, integer price, size), unfiltered.
  [[nodiscard]] const std::vector<std::int64_t>& trades_sec() const { return trades_sec_; }
  [[nodiscard]] const std::vector<std::int64_t>& trades_px() const { return trades_px_; }
  [[nodiscard]] const std::vector<std::int64_t>& trades_size() const { return trades_size_; }

  [[nodiscard]] std::int64_t iid() const { return iid_; }
  [[nodiscard]] double dominant_share() const { return dominant_share_; }
  /// UTC epoch second of the session open. The S1.2 calendar joins are LOCAL
  /// wall-clock joins, so they need the session's absolute anchor, not its
  /// trade date — a Globex session opens the previous evening ET.
  [[nodiscard]] std::int64_t open_utc() const { return open_utc_; }

 private:
  qr::skel::SessionView view_;
  std::vector<std::int64_t> trades_sec_, trades_px_, trades_size_;
  std::int64_t iid_ = 0;
  double dominant_share_ = 0.0;
  std::int64_t open_utc_ = 0;
};

}  // namespace qr::gen

#endif  // QR_GEN_GENSESSION_HPP
