#include "qr_skel/session.hpp"

#include <algorithm>
#include <cstdio>
#include <limits>

#include "qr_futsess/constants.hpp"
#include "qr_skel/binpack.hpp"

namespace qr::skel {

double SanityPolicy::threshold_usd(std::int8_t phase) const {
  if (!enabled) {
    return std::numeric_limits<double>::infinity();
  }
  const std::size_t p = static_cast<std::size_t>(phase);
  if (phase < 0 || p >= kPhaseCount) {
    return 0.0;  // an unknown phase has no sane seconds; never a silent pass
  }
  return std::min(kSaneMedianMultiple * phase_median_spread_usd[p], kSaneAbsoluteCapUsd);
}

Expected<SessionView, Refusal> SessionView::load(const std::string& dir, std::int32_t date8,
                                                 const SanityPolicy& policy) {
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
  auto spread = p.get<double>("g0_spread_usd", "float64");
  if (!spread) {
    return refuse<SessionView>(spread.error());
  }

  SessionView s;
  s.date8_ = date8;
  s.mid_ = std::move(mid).value();
  s.state_ = std::move(state).value();
  s.phase_ = std::move(phase).value();
  s.spread_ = std::move(spread).value();
  // CONV C1 (the m0 DST clip): every array is truncated to the shortest of the
  // mid/phase grids. state must cover that span or the receipt is malformed.
  const std::size_t n = std::min(s.mid_.size(), s.phase_.size());
  if (s.state_.size() < n || s.spread_.size() < n) {
    return refuse<SessionView>(Refusal(RefusalCode::CONTENT_MISMATCH, "qr_skel::SessionView::load",
                                       "a grid is shorter than the clipped mid/phase grids"));
  }
  s.mid_.resize(n);
  s.phase_.resize(n);
  s.state_.resize(n);
  s.spread_.resize(n);
  s.n_ = static_cast<std::int32_t>(n);

  double thr[kPhaseCount];
  for (std::size_t i = 0; i < kPhaseCount; ++i) {
    thr[i] = policy.threshold_usd(static_cast<std::int8_t>(i));
  }
  s.sane_.assign(n, 0);
  s.vt_.reserve(n);
  s.vm_.reserve(n);
  for (std::size_t t = 0; t < n; ++t) {
    if (s.state_[t] != qr::futsess::kStTwoSided) {
      continue;
    }
    ++s.n_two_sided_;
    // CC-M1-4: the ceiling is inclusive. A non-finite spread on a two-sided
    // second can never satisfy it, which is the intended exclusion.
    const std::int8_t ph = s.phase_[t];
    const double ceiling = (ph >= 0 && static_cast<std::size_t>(ph) < kPhaseCount)
                               ? thr[static_cast<std::size_t>(ph)]
                               : 0.0;
    if (!(s.spread_[t] <= ceiling)) {
      ++s.n_insane_;
      continue;
    }
    s.sane_[t] = 1;
    s.vt_.push_back(static_cast<std::int32_t>(t));
    s.vm_.push_back(s.mid_[t]);
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
