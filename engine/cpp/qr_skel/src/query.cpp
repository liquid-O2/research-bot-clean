#include "qr_skel/query.hpp"

namespace qr::skel {

BarrierOutcome decode_barrier_cell(const AnchorSkeleton& a, std::size_t up_k,
                                   std::size_t dn_k) noexcept {
  BarrierOutcome o;
  if (up_k < 1 || up_k > kRungCount || dn_k < 1 || dn_k > kRungCount) {
    return o;  // unavailable; nothing is read out of range
  }
  o.available = a.observed_secs > 0;
  if (!o.available) {
    return o;
  }
  o.tau_up_sec = a.tau_up[up_k - 1];
  o.tau_dn_sec = a.tau_dn[dn_k - 1];
  o.up_hit = o.tau_up_sec >= 0;
  o.dn_hit = o.tau_dn_sec >= 0;
  o.same_second_ambiguous = o.up_hit && o.dn_hit && (o.tau_up_sec == o.tau_dn_sec);
  if (o.up_hit && o.dn_hit) {
    // CONV C10 / ATLAS §4.3 A2: a simultaneous touch resolves ADVERSE.
    o.winner = (o.tau_up_sec < o.tau_dn_sec) ? BarrierWinner::kFavorable : BarrierWinner::kAdverse;
  } else if (o.up_hit) {
    o.winner = BarrierWinner::kFavorable;
  } else if (o.dn_hit) {
    o.winner = BarrierWinner::kAdverse;
  } else {
    o.winner = BarrierWinner::kNeither;
  }
  return o;
}

}  // namespace qr::skel
