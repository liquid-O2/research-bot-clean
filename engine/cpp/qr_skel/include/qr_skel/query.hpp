// qr_skel/query.hpp — the DECODE layer (LABEL_ATLAS_V2 §3.2.4, CONV C10).
//
// "Every barrier label is a decode, not a scan." A barrier cell is derived from
// the stored first-passage tensors alone: no tape, no session, no new row. This
// is what makes an asymmetric risk/reward sweep free, and it is the reason the
// structural suite can assert that querying MORE cells never stores more rows.
#ifndef QR_SKEL_QUERY_HPP
#define QR_SKEL_QUERY_HPP

#include <cstdint>

#include "qr_skel/skeleton.hpp"

namespace qr::skel {

/// Winner codes. The favorable/adverse race is resolved here and ONLY here;
/// storage keeps both times unconditionally.
enum class BarrierWinner : std::int8_t {
  kNeither = -2,    ///< neither barrier touched inside the observed window
  kAdverse = -1,    ///< adverse first, OR the two touched in the same second
  kFavorable = 1,
};

struct BarrierOutcome {
  bool available = false;   ///< observed_secs > 0
  bool up_hit = false;
  bool dn_hit = false;
  std::int32_t tau_up_sec = -1;  ///< retained even when the adverse side wins
  std::int32_t tau_dn_sec = -1;  ///< retained even when the favorable side wins
  /// SAME_GROUP typing (ATLAS §4.3 A2): preserved alongside the resolved
  /// winner, never collapsed into it.
  bool same_second_ambiguous = false;
  BarrierWinner winner = BarrierWinner::kNeither;
};

/// `up_k` / `dn_k` are ONE-BASED rung indices in 1..kRungCount. An index out of
/// range is a programmer error, so it is reported as an unavailable outcome
/// rather than reading past the tensor.
[[nodiscard]] BarrierOutcome decode_barrier_cell(const AnchorSkeleton& a, std::size_t up_k,
                                                 std::size_t dn_k) noexcept;

}  // namespace qr::skel

#endif  // QR_SKEL_QUERY_HPP
