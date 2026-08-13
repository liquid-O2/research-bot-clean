#include "qr_gen/levels.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <limits>

namespace qr::gen {
namespace {

constexpr double kNaN = std::numeric_limits<double>::quiet_NaN();
constexpr std::int64_t kSentHi = 1LL << 62;

const char* const kFamilyNames[kLevelFamilyCount] = {"FVOL_LADDER", "FVOL_BAND", "NDAY",
                                                     "PRIOR_DAY",   "PHASE_HL",  "VWAP"};

/// The five VWAP band suffixes, spelled exactly as the Python ledger spells
/// them ("%+g"), so a level keeps ONE identity across the two implementations.
const char* const kVwapBandName[kVwapBandCount] = {"+0", "+2", "-2", "+2.5", "-2.5"};
const char* const kFvolKName[kFvolKCount] = {"0.5", "1.0", "1.5", "2.0"};
const char* const kSignName[2] = {"+1", "-1"};

/// The registry identity of a level: its name plus the price it currently sits
/// on (tick-grid rounded). A source that MOVES its price creates a NEW level
/// object — new creation date, virgin again — which is §4's identity law.
std::string static_registry_key(const std::string& key, double price, double tick_px) {
  const long long t = static_cast<long long>(std::nearbyint(price / tick_px));
  char buf[32];
  std::snprintf(buf, sizeof(buf), "%lld", t);
  return key + "\x1f" + buf;
}

std::string dynamic_registry_key(const std::string& key, std::int32_t date8) {
  char buf[32];
  std::snprintf(buf, sizeof(buf), "%d", date8);
  return key + "\x1f" "DYN" "\x1f" + buf;
}

/// First session second of a phase, or -1 when the phase never opens.
std::int32_t phase_open_sec(const GenSession& s, std::size_t phase) {
  const std::vector<std::int8_t>& ph = s.phase_tag();
  for (std::size_t t = 0; t < ph.size(); ++t) {
    if (static_cast<std::size_t>(ph[t]) == phase) {
      return static_cast<std::int32_t>(t);
    }
  }
  return -1;
}

/// max over the finite values only; NaN when none is finite (the Python
/// `[v for v in hs if isfinite(v)]` filter).
struct Extremes {
  double hi = kNaN;
  double lo = kNaN;
  bool have_hi = false;
  bool have_lo = false;
};

void accumulate(Extremes* e, double high, double low) {
  if (std::isfinite(high)) {
    e->hi = e->have_hi ? std::max(e->hi, high) : high;
    e->have_hi = true;
  }
  if (std::isfinite(low)) {
    e->lo = e->have_lo ? std::min(e->lo, low) : low;
    e->have_lo = true;
  }
}

}  // namespace

const char* level_family_name(LevelFamily f) {
  return kFamilyNames[static_cast<std::size_t>(f)];
}

// ============================================================ level builder ==
std::vector<LevelDef> build_levels(const qr::skel::AssetGeom& geom, double px_scale,
                                   const GenSession& s, std::int32_t date8, const V1History& hist,
                                   std::int64_t hist_index, const FvolForecasts& fvol) {
  std::vector<LevelDef> out;
  const double mult = static_cast<double>(geom.mult);
  const std::vector<std::int32_t>& vt = s.vt();
  const std::vector<double>& vm = s.vm();
  const std::int64_t i = hist_index;
  const bool have_prev = (i >= 1);
  const DayBars* prev = have_prev ? &hist.at(i - 1) : nullptr;

  // ------------------------------------------------- (a) fvol levels --------
  struct Anchor {
    const char* name;
    double px;
    std::int32_t sec;
    Segment seg;
  };
  std::vector<Anchor> anchors;
  if (prev != nullptr) {
    const double settle = prev->seg[static_cast<std::size_t>(Segment::SESSION)].close_px;
    if (std::isfinite(settle)) {
      anchors.push_back(Anchor{"SETTLE", settle, 0, Segment::SESSION});
    }
  }
  static const char* const kOpenName[3] = {"OPEN_TOKYO", "OPEN_LONDON", "OPEN_NY"};
  static const Segment kOpenSeg[3] = {Segment::TOKYO, Segment::LONDON, Segment::NY};
  for (std::size_t p = 0; p < 3; ++p) {
    const std::int32_t o = phase_open_sec(s, p);
    if (o < 0) {
      continue;
    }
    const std::size_t j = s.view().vt_lower_bound(o);
    if (j >= vt.size()) {
      continue;
    }
    anchors.push_back(Anchor{kOpenName[p], vm[j], vt[j], kOpenSeg[p]});
  }
  for (const Anchor& a : anchors) {
    const FvolRow* row = fvol.find(date8, a.seg);
    if (row == nullptr) {
      continue;
    }
    const double sig_usd = row->sigma_hat_usd;
    if (!std::isfinite(sig_usd) || sig_usd <= 0.0) {
      continue;
    }
    const double sig_px = sig_usd / mult;
    for (std::size_t k = 0; k < kFvolKCount; ++k) {
      for (std::size_t sg = 0; sg < 2; ++sg) {
        const double sgn = (sg == 0) ? 1.0 : -1.0;
        LevelDef L;
        L.key = std::string("FVOL_BAND|") + a.name + "|k" + kFvolKName[k] + "|" + kSignName[sg];
        L.family = LevelFamily::FVOL_BAND;
        L.price = a.px + sgn * kFvolK[k] * sig_px;
        L.active_from = a.sec;
        out.push_back(std::move(L));
      }
    }
    for (std::size_t q = 0; q < kLadderQCount; ++q) {
      const double m = row->move_q[q];
      if (!std::isfinite(m)) {
        continue;
      }
      char qn[8];
      std::snprintf(qn, sizeof(qn), "q%02d", kLadderQ[q]);
      for (std::size_t sg = 0; sg < 2; ++sg) {
        const double sgn = (sg == 0) ? 1.0 : -1.0;
        LevelDef L;
        L.key = std::string("FVOL_LADDER|") + a.name + "|" + qn + "|" + kSignName[sg];
        L.family = LevelFamily::FVOL_LADDER;
        L.price = a.px + sgn * m * sig_px;
        L.active_from = a.sec;
        out.push_back(std::move(L));
      }
    }
  }

  // ------------------------------------- (b) prior day / N-day lookback -----
  if (prev != nullptr) {
    const SegmentBar& ps = prev->seg[static_cast<std::size_t>(Segment::SESSION)];
    const char* const nm[3] = {"H", "L", "SETTLE"};
    const double v[3] = {ps.high_px, ps.low_px, ps.close_px};
    for (std::size_t k = 0; k < 3; ++k) {
      if (!std::isfinite(v[k])) {
        continue;
      }
      LevelDef L;
      L.key = std::string("PRIOR_DAY|") + nm[k];
      L.family = LevelFamily::PRIOR_DAY;
      L.price = v[k];
      L.active_from = 0;
      out.push_back(std::move(L));
    }
  }
  for (std::size_t k = 0; k < kNdayCount; ++k) {
    const int n = kNdayLookbacks[k];
    if (i < n) {
      continue;  // len(sel) < n
    }
    Extremes e;
    for (std::int64_t d = i - n; d < i; ++d) {
      const SegmentBar& b = hist.at(d).seg[static_cast<std::size_t>(Segment::SESSION)];
      accumulate(&e, b.high_px, b.low_px);
    }
    char key[32];
    if (e.have_hi) {
      std::snprintf(key, sizeof(key), "NDAY|N%d|H", n);
      out.push_back(LevelDef{key, LevelFamily::NDAY, e.hi, 0, false, {}});
    }
    if (e.have_lo) {
      std::snprintf(key, sizeof(key), "NDAY|N%d|L", n);
      out.push_back(LevelDef{key, LevelFamily::NDAY, e.lo, 0, false, {}});
    }
  }

  // ------------------------------------------------- (c) per-phase H/L ------
  static const Segment kSegOrder[4] = {Segment::OVERNIGHT, Segment::TOKYO, Segment::LONDON,
                                       Segment::NY};
  for (std::size_t sgi = 0; sgi < 4; ++sgi) {
    const Segment seg = kSegOrder[sgi];
    for (std::size_t li = 0; li < kPhaseLbCount; ++li) {
      const int lb = kPhaseLookbacks[li];
      if (i < lb) {
        continue;
      }
      Extremes e;
      for (std::int64_t d = i - lb; d < i; ++d) {
        const SegmentBar& b = hist.at(d).seg[static_cast<std::size_t>(seg)];
        // An absent segment row contributes NaN, exactly as the Python
        // `.get(seg, {}).get("high_px", nan)` does.
        accumulate(&e, b.present ? b.high_px : kNaN, b.present ? b.low_px : kNaN);
      }
      char key[48];
      if (e.have_hi) {
        std::snprintf(key, sizeof(key), "PHASE_HL|%s|lb%d|H", segment_name(seg), lb);
        out.push_back(LevelDef{key, LevelFamily::PHASE_HL, e.hi, 0, false, {}});
      }
      if (e.have_lo) {
        std::snprintf(key, sizeof(key), "PHASE_HL|%s|lb%d|L", segment_name(seg), lb);
        out.push_back(LevelDef{key, LevelFamily::PHASE_HL, e.lo, 0, false, {}});
      }
    }
  }

  // ------------------------------------------------------ (d) causal VWAP ---
  const std::int32_t n = s.n();
  const std::size_t nu = static_cast<std::size_t>(n);
  const std::vector<std::int64_t>& tsec = s.trades_sec();
  const std::vector<std::int64_t>& tpx = s.trades_px();
  const std::vector<std::int64_t>& tsz = s.trades_size();
  struct Scope {
    const char* name;
    std::int32_t lo;
    std::int32_t hi;
  };
  std::vector<Scope> scopes;
  if (n > 0) {
    scopes.push_back(Scope{"SESSION", 0, n - 1});
  }
  static const char* const kPhaseName[3] = {"TOKYO", "LONDON", "NY"};
  for (std::size_t p = 0; p < 3; ++p) {
    std::int32_t lo = -1;
    std::int32_t hi = -1;
    for (std::size_t t = 0; t < s.phase_tag().size(); ++t) {
      if (static_cast<std::size_t>(s.phase_tag()[t]) == p) {
        if (lo < 0) {
          lo = static_cast<std::int32_t>(t);
        }
        hi = static_cast<std::int32_t>(t);
      }
    }
    if (lo >= 0) {
      scopes.push_back(Scope{kPhaseName[p], lo, hi});
    }
  }
  std::vector<double> acc_v, acc_vp, acc_vp2;
  for (const Scope& sc : scopes) {
    std::size_t n_sel = 0;
    for (std::size_t k = 0; k < tsec.size(); ++k) {
      if (tpx[k] > 0 && tpx[k] < kSentHi && tsz[k] > 0 && tsec[k] >= 0 && tsec[k] < n &&
          tsec[k] >= sc.lo && tsec[k] <= sc.hi) {
        ++n_sel;
      }
    }
    if (n_sel < 2) {
      continue;
    }
    acc_v.assign(nu, 0.0);
    acc_vp.assign(nu, 0.0);
    acc_vp2.assign(nu, 0.0);
    for (std::size_t k = 0; k < tsec.size(); ++k) {
      if (!(tpx[k] > 0 && tpx[k] < kSentHi && tsz[k] > 0 && tsec[k] >= 0 && tsec[k] < n &&
            tsec[k] >= sc.lo && tsec[k] <= sc.hi)) {
        continue;
      }
      const std::size_t t = static_cast<std::size_t>(tsec[k]);
      const double px = static_cast<double>(tpx[k]) * px_scale;
      const double sz = static_cast<double>(tsz[k]);
      acc_v[t] += sz;
      acc_vp[t] += sz * px;
      acc_vp2[t] += (sz * px) * px;
    }
    // The causal running VWAP and its running deviation, sampled at the
    // MID-SANE seconds (a cumulative sum in second order, never a re-scan).
    std::vector<double> vwap_at(vt.size(), kNaN);
    std::vector<double> sd_at(vt.size(), kNaN);
    double cv = 0.0;
    double cvp = 0.0;
    double cvp2 = 0.0;
    std::size_t j = 0;
    for (std::size_t t = 0; t < nu; ++t) {
      cv += acc_v[t];
      cvp += acc_vp[t];
      cvp2 += acc_vp2[t];
      while (j < vt.size() && static_cast<std::size_t>(vt[j]) == t) {
        if (cv > 0.0) {
          const double w = cvp / cv;
          const double var = cvp2 / cv - w * w;
          const double m = std::isnan(var) ? var : (var > 0.0 ? var : 0.0);
          vwap_at[j] = w;
          sd_at[j] = std::sqrt(m);
        }
        ++j;
      }
    }
    for (std::size_t b = 0; b < kVwapBandCount; ++b) {
      LevelDef L;
      L.key = std::string("VWAP|") + sc.name + "|" + kVwapBandName[b];
      L.family = LevelFamily::VWAP;
      L.price = kNaN;
      L.active_from = sc.lo;
      L.dynamic = true;
      L.series.resize(vt.size());
      for (std::size_t k = 0; k < vt.size(); ++k) {
        L.series[k] = vwap_at[k] + kVwapBands[b] * sd_at[k];
      }
      out.push_back(std::move(L));
    }
  }
  return out;
}

// ======================================================== the state machine ==
TouchScan touch_scan(const std::vector<double>& dist, const std::vector<std::int8_t>& phase_v,
                     std::int64_t active_from, double tol) {
  TouchScan out;
  const std::int64_t n = static_cast<std::int64_t>(dist.size());
  if (n == 0 || active_from >= n) {
    return out;
  }
  std::vector<std::int64_t> arm_pos;
  std::vector<std::int64_t> near_pos;
  std::int64_t run_far = 0;
  const double far_tol = kArmDistanceMult * tol;
  for (std::int64_t k = 0; k < n; ++k) {
    const double d = dist[static_cast<std::size_t>(k)];
    const bool finite = std::isfinite(d);
    const bool is_near = (k >= active_from) && finite && (d <= tol);
    const bool is_far = (k >= active_from) && finite && (d > far_tol);
    run_far = is_far ? run_far + 1 : 0;
    bool armable = (run_far >= kArmSeconds);
    // A phase boundary re-arms every level (§4). Positions before the level's
    // creation second are never armable.
    if (n > 1 && k >= 1 && k >= active_from &&
        phase_v[static_cast<std::size_t>(k)] != phase_v[static_cast<std::size_t>(k - 1)]) {
      armable = true;
    }
    if (armable) {
      arm_pos.push_back(k);
    }
    if (is_near) {
      near_pos.push_back(k);
    }
  }
  out.first_near = near_pos.empty() ? -1 : near_pos.front();
  std::size_t ai = 0;
  std::size_t ni = 0;
  std::int64_t cur = active_from;
  for (;;) {
    while (ai < arm_pos.size() && arm_pos[ai] < cur) {
      ++ai;
    }
    if (ai >= arm_pos.size()) {
      break;
    }
    const std::int64_t a = arm_pos[ai];
    while (ni < near_pos.size() && near_pos[ni] < a) {
      ++ni;
    }
    if (ni >= near_pos.size()) {
      break;
    }
    const std::int64_t t = near_pos[ni];
    out.touches.push_back(t);
    cur = t + 1;
  }
  return out;
}

TouchOutcome classify_touch(const std::vector<double>& diff, const std::vector<std::int32_t>& secs,
                            std::int64_t ti, std::int8_t app, double tol, double reject_move) {
  TouchOutcome out;
  const std::int64_t n = static_cast<std::int64_t>(secs.size());
  const std::int32_t t_sec = secs[static_cast<std::size_t>(ti)];
  // The §6 window is the observations with sec <= t_sec + 900 (searchsorted
  // 'right'), starting at the observation AFTER the touch.
  std::int64_t hi = static_cast<std::int64_t>(
      std::upper_bound(secs.begin(), secs.end(), t_sec + kRejectWindow) - secs.begin());
  const double a = static_cast<double>(app);
  std::int64_t run_beyond = 0;
  for (std::int64_t k = ti + 1; k < hi; ++k) {
    const double w = diff[static_cast<std::size_t>(k)] * a;
    if (out.reject_sec < 0 && w >= reject_move) {
      out.reject_sec = secs[static_cast<std::size_t>(k)];
    }
    run_beyond = (w < -tol) ? run_beyond + 1 : 0;
    if (out.break_sec < 0 && run_beyond >= kBreakHold) {
      out.break_sec = secs[static_cast<std::size_t>(k)];
    }
    if (out.reject_sec >= 0 && out.break_sec >= 0) {
      break;
    }
  }
  if (out.break_sec >= 0) {
    const std::int64_t j = static_cast<std::int64_t>(
        std::lower_bound(secs.begin(), secs.end(), out.break_sec) - secs.begin());
    std::int64_t run_back = 0;
    for (std::int64_t k = j + 1; k < n; ++k) {
      const double w = diff[static_cast<std::size_t>(k)] * a;
      run_back = (w >= -tol) ? run_back + 1 : 0;
      if (run_back >= kReclaimHold) {
        out.reclaim_sec = secs[static_cast<std::size_t>(k)];
        break;
      }
    }
  }
  if (out.reclaim_sec >= 0) {
    // A broken level that is reclaimed resolves as RECLAIM: that is the test's
    // final outcome (§4 ledger field, §6 names).
    out.outcome = Outcome::RECLAIM;
    out.outcome_sec = out.reclaim_sec;
    return out;
  }
  if (out.reject_sec >= 0 && (out.break_sec < 0 || out.reject_sec <= out.break_sec)) {
    // Ties go to REJECT: the Python `cands.sort()` orders (sec, outcome) and
    // REJECT (1) precedes BREAK (2) at an equal second.
    out.outcome = Outcome::REJECT;
    out.outcome_sec = out.reject_sec;
  } else if (out.break_sec >= 0) {
    out.outcome = Outcome::BREAK;
    out.outcome_sec = out.break_sec;
  }
  return out;
}

SessionLedger run_ledger(const qr::skel::AssetGeom& geom, const GenSession& s, std::int32_t date8,
                         double atr14_usd, const std::vector<LevelDef>& levels,
                         LevelRegistry* reg) {
  SessionLedger out;
  const double mult = static_cast<double>(geom.mult);
  out.tol_px = std::max(kTolTicks * geom.tick_usd, kTolAtrFrac * atr14_usd) / mult;
  out.reject_move_px = std::max(kRejectAtrFrac * atr14_usd, kRejectTicks * geom.tick_usd) / mult;
  const double tol = out.tol_px;
  const double reject_move = out.reject_move_px;

  const std::vector<std::int32_t>& vt = s.vt();
  const std::vector<double>& vm = s.vm();
  std::vector<std::int8_t> phase_v(vt.size());
  for (std::size_t k = 0; k < vt.size(); ++k) {
    phase_v[k] = s.phase_tag()[static_cast<std::size_t>(vt[k])];
  }

  std::vector<double> diff(vt.size());
  std::vector<double> dist(vt.size());
  std::vector<std::int64_t> last_outside_upto(vt.size(), -1);
  for (const LevelDef& L : levels) {
    if (!L.dynamic && !std::isfinite(L.price)) {
      continue;
    }
    for (std::size_t k = 0; k < vt.size(); ++k) {
      diff[k] = vm[k] - (L.dynamic ? L.series[k] : L.price);
      dist[k] = std::fabs(diff[k]);
    }
    const std::int64_t af = static_cast<std::int64_t>(s.view().vt_lower_bound(L.active_from));
    if (af >= static_cast<std::int64_t>(vt.size())) {
      continue;
    }
    const std::string rk = L.dynamic ? dynamic_registry_key(L.key, date8)
                                     : static_registry_key(L.key, L.price, geom.tick_px);
    auto it = reg->find(rk);
    if (it == reg->end()) {
      LevelState st;
      st.created_d8 = date8;
      it = reg->emplace(rk, st).first;
    }
    LevelState& st = it->second;

    const TouchScan ts = touch_scan(dist, phase_v, af, tol);
    if (ts.first_near >= 0 && st.virgin) {
      st.virgin = false;
    }
    const std::int32_t row = static_cast<std::int32_t>(out.rows.size());

    // last position strictly outside tol at or before k (the approach side is
    // read there, never at the touch itself).
    std::int64_t last_outside = -1;
    for (std::size_t k = 0; k < vt.size(); ++k) {
      if (std::isfinite(dist[k]) && dist[k] > tol) {
        last_outside = static_cast<std::int64_t>(k);
      }
      last_outside_upto[k] = last_outside;
    }

    for (std::int64_t ti : ts.touches) {
      const std::int64_t jj =
          (ti > 0) ? last_outside_upto[static_cast<std::size_t>(ti - 1)] : -1;
      if (jj < af) {
        continue;
      }
      const std::int8_t app = (diff[static_cast<std::size_t>(jj)] > 0.0)
                                  ? static_cast<std::int8_t>(1)
                                  : static_cast<std::int8_t>(-1);
      const TouchOutcome oc = classify_touch(diff, vt, ti, app, tol, reject_move);
      ++st.touch_count;
      st.last_test_sec = vt[static_cast<std::size_t>(ti)];
      st.last_test_outcome = oc.outcome;
      Touch t;
      t.touch_sec = vt[static_cast<std::size_t>(ti)];
      t.level_row = row;
      t.family = L.family;
      t.level_price =
          L.dynamic ? L.series[static_cast<std::size_t>(ti)] : L.price;
      t.mid = vm[static_cast<std::size_t>(ti)];
      t.approach_side = app;
      t.outcome = oc.outcome;
      t.outcome_sec = oc.outcome_sec;
      t.reject_sec = oc.reject_sec;
      t.break_sec = oc.break_sec;
      t.reclaim_sec = oc.reclaim_sec;
      t.virgin_at_touch = (st.touch_count == 1) ? 1 : 0;
      t.touch_index = st.touch_count;
      out.touches.push_back(t);
    }

    LedgerRow lr;
    lr.family = L.family;
    lr.price = L.dynamic ? L.series[static_cast<std::size_t>(af)] : L.price;
    lr.created_d8 = st.created_d8;
    lr.dynamic = L.dynamic ? 1 : 0;
    lr.virgin = st.virgin ? 1 : 0;
    lr.touch_count = st.touch_count;
    lr.last_test_sec = st.last_test_sec;
    lr.last_test_outcome = static_cast<std::int8_t>(st.last_test_outcome);
    lr.first_near_sec =
        (ts.first_near >= 0) ? vt[static_cast<std::size_t>(ts.first_near)] : -1;
    out.rows.push_back(lr);
  }
  return out;
}

}  // namespace qr::gen
