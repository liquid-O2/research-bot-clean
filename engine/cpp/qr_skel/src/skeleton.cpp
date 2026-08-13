#include "qr_skel/skeleton.hpp"

#include <algorithm>
#include <cmath>
#include <limits>

namespace qr::skel {
namespace {

constexpr double kNaN = std::numeric_limits<double>::quiet_NaN();

/// CONV C3: the UNAVAILABLE fill. Every double NaN, every derived int -1,
/// every tau null, zero records. `observed_secs == 0` is the discriminator.
void fill_unavailable(std::int32_t anchor_sec, const RecordArrays& recs, AnchorSkeleton* out) {
  out->anchor_sec = anchor_sec;
  out->observed_secs = 0;
  out->entry_mid = kNaN;
  for (std::size_t k = 0; k < kRungCount; ++k) {
    out->tau_up[k] = -1;
    out->tau_dn[k] = -1;
  }
  for (std::size_t h = 0; h < kHorizonMarkCount; ++h) {
    out->f_mark[h] = kNaN;
  }
  out->phase_close_sec = -1;
  out->sess_close_sec = -1;
  out->mfe_usd = kNaN;
  out->mfe_argmax_sec = -1;
  out->mae_before_argmax_usd = kNaN;
  out->mae_unwalled_usd = kNaN;
  out->f_terminal_usd = kNaN;
  out->giveback_post_peak_usd = kNaN;
  out->time_to_peak_secs = -1;
  out->time_underwater_secs = -1;
  out->uw_share = kNaN;
  out->mono_steps = -1;
  out->monotonicity = kNaN;
  out->f_off = static_cast<std::int64_t>(recs.f_t.size());
  out->f_len = 0;
  out->a_off = static_cast<std::int64_t>(recs.a_t.size());
  out->a_len = 0;
}

}  // namespace

Expected<std::monostate, Refusal> compute_anchor(const SessionView& s, const AssetGeom& geom,
                                                 std::int8_t side, std::int32_t anchor_sec,
                                                 const double* rung_usd, ChunkScratch& sc,
                                                 RecordArrays& recs, AnchorSkeleton* out) {
  if (side != 1 && side != -1) {
    return refuse<std::monostate>(Refusal(RefusalCode::CONTENT_MISMATCH, "qr_skel::compute_anchor",
                                          "candidate side is neither +1 nor -1", side));
  }
  if (!s.is_valid_second(anchor_sec)) {
    fill_unavailable(anchor_sec, recs, out);
    return std::monostate{};
  }
  const double entry = s.mid()[static_cast<std::size_t>(anchor_sec)];
  if (!std::isfinite(entry)) {
    return refuse<std::monostate>(Refusal(RefusalCode::CONTENT_MISMATCH, "qr_skel::compute_anchor",
                                          "two-sided second carries a non-finite mid", anchor_sec));
  }

  const std::vector<std::int32_t>& vt = s.vt();
  const std::vector<double>& vm = s.vm();
  const std::size_t j0 = s.vt_lower_bound(anchor_sec);
  const std::size_t m = vt.size() - j0;

  out->anchor_sec = anchor_sec;
  out->observed_secs = static_cast<std::int32_t>(m);
  out->entry_mid = entry;

  // ---- the ONE forward pass (CONV C4) --------------------------------------
  const double sided = static_cast<double>(side);
  const double mult = static_cast<double>(geom.mult);
  sc.f.resize(m);
  for (std::size_t i = 0; i < m; ++i) {
    // The trailing `+ 0.0` is the NEGATIVE-ZERO NORMALIZATION of CONV C4: for a
    // short candidate every second whose mid equals the entry yields -0.0,
    // whose BYTES differ from +0.0 while every comparison says they are equal.
    // Byte-exact parity has to be well defined, so -0.0 is folded to +0.0.
    // `x + 0.0` is exact for every finite x, so no other value moves.
    sc.f[i] = (vm[j0 + i] - entry) * sided * mult + 0.0;
  }

  // ---- prefix-maxima records (CONV C7) + the landmark block (CONV C8) ------
  sc.rec_t_f.clear();
  sc.rec_v_f.clear();
  sc.rec_v_f32.clear();
  sc.rec_t_a.clear();
  sc.rec_v_a.clear();
  sc.rec_v_a32.clear();

  double run_f = 0.0;  // f[0] == +0.0 exactly (CONV C4)
  double run_a = 0.0;
  std::size_t argmax_i = 0;
  std::int32_t underwater = (sc.f[0] < 0.0) ? 1 : 0;
  for (std::size_t i = 1; i < m; ++i) {
    const double v = sc.f[i];
    if (v > run_f) {
      run_f = v;
      argmax_i = i;
      sc.rec_t_f.push_back(vt[j0 + i]);
      sc.rec_v_f.push_back(run_f);
      sc.rec_v_f32.push_back(static_cast<float>(run_f));
    }
    if (-v > run_a) {
      run_a = -v;
      sc.rec_t_a.push_back(vt[j0 + i]);
      sc.rec_v_a.push_back(run_a);
      sc.rec_v_a32.push_back(static_cast<float>(run_a));
    }
    if (v < 0.0) {
      ++underwater;
    }
  }
  out->mfe_usd = run_f;
  out->mfe_argmax_sec = vt[j0 + argmax_i];
  out->mae_unwalled_usd = run_a;
  out->time_to_peak_secs = out->mfe_argmax_sec - anchor_sec;
  out->f_terminal_usd = sc.f[m - 1];
  out->time_underwater_secs = underwater;
  out->uw_share = static_cast<double>(underwater) / static_cast<double>(m);

  // MAE before the argmax: the adverse prefix maximum evaluated at argmax_i.
  double mae_before = 0.0;
  for (std::size_t i = 0; i <= argmax_i; ++i) {
    if (-sc.f[i] > mae_before) {
      mae_before = -sc.f[i];
    }
  }
  out->mae_before_argmax_usd = mae_before;

  // Giveback after the peak: MFE minus the post-peak minimum (ATLAS §3.3's
  // "one extra range query"). No observation after the peak => no giveback.
  double post_min = run_f;
  for (std::size_t i = argmax_i + 1; i < m; ++i) {
    if (sc.f[i] < post_min) {
      post_min = sc.f[i];
    }
  }
  out->giveback_post_peak_usd = (argmax_i + 1 < m) ? (run_f - post_min) : 0.0;

  // ---- first-passage tensors: prefix-max + BINARY SEARCH (CONV C6) --------
  // The stored prefix-max record values are strictly increasing, so the first
  // second at which the running maximum reaches rung_usd[k] is a lower_bound.
  // O(log R) per query; no O(window) rescan per rung, ever.
  for (std::size_t k = 0; k < kRungCount; ++k) {
    const double x = rung_usd[k];
    const auto itf = std::lower_bound(sc.rec_v_f.begin(), sc.rec_v_f.end(), x);
    out->tau_up[k] = (itf == sc.rec_v_f.end())
                         ? -1
                         : sc.rec_t_f[static_cast<std::size_t>(itf - sc.rec_v_f.begin())];
    const auto ita = std::lower_bound(sc.rec_v_a.begin(), sc.rec_v_a.end(), x);
    out->tau_dn[k] = (ita == sc.rec_v_a.end())
                         ? -1
                         : sc.rec_t_a[static_cast<std::size_t>(ita - sc.rec_v_a.begin())];
  }

  // ---- horizon marks (CONV C9) --------------------------------------------
  const std::int32_t n = s.n();
  const std::int32_t pc = s.next_phase_boundary(anchor_sec);
  const std::int32_t sc_sec = n - 1;
  out->phase_close_sec = pc;
  out->sess_close_sec = sc_sec;
  const std::int32_t marks[kHorizonMarkCount] = {anchor_sec + kHorizonSecs[0],
                                                 anchor_sec + kHorizonSecs[1],
                                                 anchor_sec + kHorizonSecs[2], pc, sc_sec};
  for (std::size_t h = 0; h < kHorizonMarkCount; ++h) {
    const std::int32_t mk = marks[h];
    if (mk >= n) {
      out->f_mark[h] = kNaN;
      continue;
    }
    const std::size_t j = static_cast<std::size_t>(
        std::upper_bound(vt.begin() + static_cast<std::ptrdiff_t>(j0), vt.end(), mk) -
        (vt.begin() + static_cast<std::ptrdiff_t>(j0)));
    // mk >= anchor_sec == vt[j0], so j >= 1 always.
    out->f_mark[h] = sc.f[j - 1];
  }

  // ---- monotonicity: favorable 1-minute steps (CONV C8) -------------------
  const std::int32_t span = vt[vt.size() - 1] - anchor_sec;
  const std::int32_t steps = span / 60;
  out->mono_steps = steps;
  if (steps <= 0) {
    out->monotonicity = kNaN;
  } else {
    std::size_t idx = 0;
    double prev = sc.f[0];
    std::int32_t favorable = 0;
    for (std::int32_t i = 1; i <= steps; ++i) {
      const std::int32_t mark = anchor_sec + 60 * i;
      while (idx + 1 < m && vt[j0 + idx + 1] <= mark) {
        ++idx;
      }
      const double cur = sc.f[idx];
      if (cur > prev) {
        ++favorable;
      }
      prev = cur;
    }
    out->monotonicity = static_cast<double>(favorable) / static_cast<double>(steps);
  }

  // ---- publish the ragged records -----------------------------------------
  out->f_off = static_cast<std::int64_t>(recs.f_t.size());
  out->f_len = static_cast<std::int64_t>(sc.rec_t_f.size());
  out->a_off = static_cast<std::int64_t>(recs.a_t.size());
  out->a_len = static_cast<std::int64_t>(sc.rec_t_a.size());
  recs.f_t.insert(recs.f_t.end(), sc.rec_t_f.begin(), sc.rec_t_f.end());
  recs.f_v.insert(recs.f_v.end(), sc.rec_v_f32.begin(), sc.rec_v_f32.end());
  recs.a_t.insert(recs.a_t.end(), sc.rec_t_a.begin(), sc.rec_t_a.end());
  recs.a_v.insert(recs.a_v.end(), sc.rec_v_a32.begin(), sc.rec_v_a32.end());
  return std::monostate{};
}

}  // namespace qr::skel
