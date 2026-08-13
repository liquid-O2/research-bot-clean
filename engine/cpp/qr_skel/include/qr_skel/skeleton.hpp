// qr_skel/skeleton.hpp — the LABEL TENSOR ENGINE (PORT_M1B_SPEC §1 S3).
//
// ONE forward pass per (candidate, anchor) fills a FIXED-SHAPE structure:
// first-passage tensors over the 200-rung ATR ladder on BOTH sides, the five
// horizon marks, the landmark block, and the ragged prefix-maxima record
// sequences. Every label downstream is a QUERY over this structure (query.hpp)
// and never a second read of the tape.
//
// Conventions: design/PORT_M1B_S3_CONV.md C3-C9.
#ifndef QR_SKEL_SKELETON_HPP
#define QR_SKEL_SKELETON_HPP

#include <cstdint>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_skel/geom.hpp"
#include "qr_skel/session.hpp"

namespace qr::skel {

/// One anchor's fixed-shape skeleton. The tensors are ALWAYS materialised at
/// kRungCount per side, whether or not either side is touched: the shape is a
/// law, not a function of the data (structural suite).
struct AnchorSkeleton {
  std::int32_t anchor_sec = -1;
  /// 0 == UNAVAILABLE (CONV C3). A null tau means NO TOUCH, never unavailable.
  std::int32_t observed_secs = 0;
  double entry_mid = 0.0;

  std::int32_t tau_up[kRungCount];
  std::int32_t tau_dn[kRungCount];

  /// 30m, 60m, 120m, phase-close, session-close (CONV C9).
  double f_mark[kHorizonMarkCount];
  std::int32_t phase_close_sec = -1;
  std::int32_t sess_close_sec = -1;

  double mfe_usd = 0.0;
  std::int32_t mfe_argmax_sec = -1;
  double mae_before_argmax_usd = 0.0;
  double mae_unwalled_usd = 0.0;
  double f_terminal_usd = 0.0;
  double giveback_post_peak_usd = 0.0;
  std::int32_t time_to_peak_secs = -1;
  std::int32_t time_underwater_secs = -1;
  double uw_share = 0.0;
  std::int32_t mono_steps = -1;
  double monotonicity = 0.0;

  /// Offsets into the shard-level ragged record arrays.
  std::int64_t f_off = 0;
  std::int64_t f_len = 0;
  std::int64_t a_off = 0;
  std::int64_t a_len = 0;
};

/// Reusable working set for one anchor. Allocated once per worker and reused,
/// so the engine never accumulates a whole shard of paths (ATLAS §3.2.6).
struct ChunkScratch {
  std::vector<double> f;
  std::vector<std::int32_t> rec_t_f;
  std::vector<double> rec_v_f;   // float64: every comparison and search uses this
  std::vector<float> rec_v_f32;  // float32: the m0 storage quantization (CONV C7)
  std::vector<std::int32_t> rec_t_a;
  std::vector<double> rec_v_a;
  std::vector<float> rec_v_a32;
};

/// The ragged record arrays of one output shard.
struct RecordArrays {
  std::vector<std::int32_t> f_t;
  std::vector<float> f_v;
  std::vector<std::int32_t> a_t;
  std::vector<float> a_v;
};

/// Fill `out` for one anchor. `rung_usd` is the kRungCount ladder from
/// build_ladder(). Appends this anchor's prefix-maxima records to `recs` and
/// stores their offsets in `out`. An unavailable anchor is a normal outcome,
/// not a refusal: it emits observed_secs == 0 and the null fill.
[[nodiscard]] Expected<std::monostate, Refusal> compute_anchor(const SessionView& s,
                                                               const AssetGeom& geom,
                                                               std::int8_t side,
                                                               std::int32_t anchor_sec,
                                                               const double* rung_usd,
                                                               ChunkScratch& scratch,
                                                               RecordArrays& recs,
                                                               AnchorSkeleton* out);

}  // namespace qr::skel

#endif  // QR_SKEL_SKELETON_HPP
