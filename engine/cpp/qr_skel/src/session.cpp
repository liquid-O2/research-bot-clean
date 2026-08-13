#include "qr_skel/session.hpp"

#include <algorithm>
#include <cstdio>

#include "qr_futsess/constants.hpp"
#include "qr_skel/binpack.hpp"

namespace qr::skel {

Expected<SessionView, Refusal> SessionView::load(const std::string& dir, std::int32_t date8) {
  char stem[512];
  std::snprintf(stem, sizeof(stem), "%s/%08d", dir.c_str(), date8);
  auto pack = BinPack::load(stem, "QRSESS1");
  if (!pack) {
    return refuse<SessionView>(pack.error());
  }
  const BinPack& p = pack.value();
  auto mid = p.get<double>("g0_mid", "float64");
  if (!mid) {
    return refuse<SessionView>(mid.error());
  }
  auto state = p.get<std::int8_t>("g0_state", "int8");
  if (!state) {
    return refuse<SessionView>(state.error());
  }
  auto phase = p.get<std::int8_t>("phase_tag", "int8");
  if (!phase) {
    return refuse<SessionView>(phase.error());
  }

  SessionView s;
  s.date8_ = date8;
  s.mid_ = std::move(mid).value();
  s.state_ = std::move(state).value();
  s.phase_ = std::move(phase).value();
  // CONV C1 (the m0 DST clip): every array is truncated to the shortest of the
  // mid/phase grids. state must cover that span or the receipt is malformed.
  const std::size_t n = std::min(s.mid_.size(), s.phase_.size());
  if (s.state_.size() < n) {
    return refuse<SessionView>(Refusal(RefusalCode::CONTENT_MISMATCH, "qr_skel::SessionView::load",
                                       "state grid is shorter than the clipped mid/phase grids"));
  }
  s.mid_.resize(n);
  s.phase_.resize(n);
  s.state_.resize(n);
  s.n_ = static_cast<std::int32_t>(n);

  s.vt_.reserve(n);
  s.vm_.reserve(n);
  for (std::size_t t = 0; t < n; ++t) {
    if (s.state_[t] == qr::futsess::kStTwoSided) {
      s.vt_.push_back(static_cast<std::int32_t>(t));
      s.vm_.push_back(s.mid_[t]);
    }
  }
  return s;
}

std::size_t SessionView::vt_lower_bound(std::int32_t sec) const {
  return static_cast<std::size_t>(std::lower_bound(vt_.begin(), vt_.end(), sec) - vt_.begin());
}

std::int32_t SessionView::next_phase_boundary(std::int32_t sec) const {
  const std::int8_t p = phase_[static_cast<std::size_t>(sec)];
  for (std::int32_t t = sec + 1; t < n_; ++t) {
    if (phase_[static_cast<std::size_t>(t)] != p) {
      return t;
    }
  }
  return n_ - 1;
}

}  // namespace qr::skel
