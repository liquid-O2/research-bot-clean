#include "qr_gen/families.hpp"

#include <algorithm>
#include <cmath>
#include <deque>
#include <limits>

#include "qr_futsess/constants.hpp"

namespace qr::gen {
namespace {

constexpr double kInf = std::numeric_limits<double>::infinity();

/// Maximal runs of `true` in `flag`, mapped through `secs`, as inclusive
/// (first, last) pairs. A run is contiguous in INDEX space.
std::vector<Interval> runs_of(const std::vector<std::int32_t>& secs, const std::vector<char>& flag) {
  std::vector<Interval> out;
  const std::size_t n = flag.size();
  std::size_t i = 0;
  while (i < n) {
    if (flag[i] == 0) {
      ++i;
      continue;
    }
    const std::size_t a = i;
    while (i + 1 < n && flag[i + 1] != 0) {
      ++i;
    }
    out.push_back(Interval{secs[a], secs[i]});
    ++i;
  }
  return out;
}

}  // namespace

// ================================================================= windows ====
std::vector<Interval> merge_intervals(std::vector<Interval> iv) {
  std::vector<Interval> in;
  in.reserve(iv.size());
  for (const Interval& x : iv) {
    if (x.b >= x.a) {
      in.push_back(x);
    }
  }
  std::sort(in.begin(), in.end(), [](const Interval& x, const Interval& y) {
    return (x.a != y.a) ? (x.a < y.a) : (x.b < y.b);
  });
  std::vector<Interval> out;
  for (const Interval& x : in) {
    // `a <= last.b + 1` merges ABUTTING intervals too: [0,299] and [300,599]
    // are one window, which is what a merged trigger set means.
    if (!out.empty() && x.a <= out.back().b + 1) {
      out.back().b = std::max(out.back().b, x.b);
    } else {
      out.push_back(x);
    }
  }
  return out;
}

std::vector<Interval> open_windows(const std::vector<std::int32_t>& secs, std::int32_t width) {
  std::vector<Interval> iv;
  iv.reserve(secs.size());
  for (std::int32_t t : secs) {
    iv.push_back(Interval{t, t + width - 1});
  }
  return merge_intervals(std::move(iv));
}

bool in_intervals(std::int32_t sec, const std::vector<Interval>& iv) {
  if (iv.empty()) {
    return false;
  }
  // The intervals are sorted and disjoint: the only candidate is the last one
  // whose start is <= sec.
  std::size_t lo = 0;
  std::size_t hi = iv.size();
  while (lo < hi) {
    const std::size_t mid = lo + (hi - lo) / 2;
    if (iv[mid].a <= sec) {
      lo = mid + 1;
    } else {
      hi = mid;
    }
  }
  if (lo == 0) {
    return false;
  }
  return sec <= iv[lo - 1].b;
}

// =================================================================== shock ====
std::vector<double> sliding_max(const std::vector<double>& a, std::int32_t w) {
  std::vector<double> out(a.size());
  if (a.empty()) {
    return out;
  }
  const std::size_t width = static_cast<std::size_t>(std::max(1, w));
  if (width == 1) {
    return a;
  }
  std::deque<std::size_t> dq;  // indices, values decreasing
  for (std::size_t i = 0; i < a.size(); ++i) {
    while (!dq.empty() && a[dq.back()] <= a[i]) {
      dq.pop_back();
    }
    dq.push_back(i);
    while (dq.front() + width <= i) {
      dq.pop_front();
    }
    out[i] = a[dq.front()];
  }
  return out;
}

std::vector<double> rolling_range_usd(const std::vector<std::int32_t>& vt,
                                      const std::vector<double>& vm, double mult,
                                      std::int32_t span) {
  std::vector<double> out;
  if (vt.empty()) {
    return out;
  }
  const std::int64_t t0 = vt.front();
  const std::size_t n = static_cast<std::size_t>(vt.back() - t0 + 1);
  // A sliding MIN is a sliding MAX of the NEGATION, so the unobserved filler of
  // the negated series is -inf exactly like the maximum series' own filler; a
  // +inf filler here would make every window's minimum the filler itself.
  std::vector<double> hi(n, -kInf);
  std::vector<double> neg_lo(n, -kInf);
  for (std::size_t k = 0; k < vt.size(); ++k) {
    const std::size_t p = static_cast<std::size_t>(vt[k] - t0);
    hi[p] = vm[k];
    neg_lo[p] = -vm[k];
  }
  const std::vector<double> mx = sliding_max(hi, span);
  const std::vector<double> mn = sliding_max(neg_lo, span);
  out.resize(vt.size());
  for (std::size_t k = 0; k < vt.size(); ++k) {
    const std::size_t p = static_cast<std::size_t>(vt[k] - t0);
    out[k] = (mx[p] + mn[p]) * mult;
  }
  return out;
}

std::vector<Interval> shock_episodes(const std::vector<std::int32_t>& vt,
                                     const std::vector<double>& vm, double mult) {
  if (vt.empty()) {
    return {};
  }
  const std::vector<double> rng = rolling_range_usd(vt, vm, mult, kShockSpan);
  std::vector<char> flag(vt.size(), 0);
  for (std::size_t k = 0; k < vt.size(); ++k) {
    flag[k] = (rng[k] >= kShockUsd) ? 1 : 0;
  }
  return runs_of(vt, flag);
}

std::vector<Interval> insane_episodes(const std::vector<std::int8_t>& state,
                                      const std::vector<std::uint8_t>& sane) {
  const std::size_t n = state.size();
  std::vector<std::int32_t> secs(n);
  std::vector<char> flag(n, 0);
  for (std::size_t t = 0; t < n; ++t) {
    secs[t] = static_cast<std::int32_t>(t);
    const bool two_sided = (state[t] == qr::futsess::kStTwoSided);
    flag[t] = (two_sided && sane[t] == 0) ? 1 : 0;
  }
  std::vector<Interval> out;
  for (const Interval& r : runs_of(secs, flag)) {
    if (r.b - r.a + 1 >= kInsaneMinSec) {
      out.push_back(r);
    }
  }
  return out;
}

std::vector<std::size_t> first_confirmations_after(const std::vector<std::int32_t>& conf_secs,
                                                   std::int32_t end_sec) {
  std::int32_t first = 0;
  bool have = false;
  for (std::int32_t c : conf_secs) {
    if (c > end_sec && (!have || c < first)) {
      first = c;
      have = true;
    }
  }
  std::vector<std::size_t> out;
  if (!have) {
    return out;
  }
  for (std::size_t i = 0; i < conf_secs.size(); ++i) {
    if (conf_secs[i] == first) {
      out.push_back(i);
    }
  }
  return out;
}

// ========================================================= opening ranges =====
OpeningRange opening_range(const std::vector<std::int32_t>& vt, const std::vector<double>& vm,
                           const std::vector<std::int8_t>& phase_at_vt, int phase, int minutes) {
  OpeningRange out;
  out.phase = static_cast<std::int8_t>(phase);
  const std::int8_t p = static_cast<std::int8_t>(phase);
  // The SANE seconds of this segment, in session order. `vt` is already the
  // D-054 SANE view, so this is (phase_tag == p) & valid by construction.
  std::size_t first = vt.size();
  std::size_t count = 0;
  for (std::size_t k = 0; k < vt.size(); ++k) {
    if (phase_at_vt[k] == p) {
      if (first == vt.size()) {
        first = k;
      }
      ++count;
    }
  }
  if (count < 2) {
    return out;
  }
  const std::int32_t t1 = vt[first] + static_cast<std::int32_t>(minutes) * 60;
  double hi = 0.0;
  double lo = 0.0;
  std::size_t n_in = 0;
  std::size_t n_rest = 0;
  for (std::size_t k = first; k < vt.size(); ++k) {
    if (phase_at_vt[k] != p) {
      continue;
    }
    if (vt[k] < t1) {
      // The range side: the extremes of the SANE mids inside [open, open+width).
      if (n_in == 0) {
        hi = vm[k];
        lo = vm[k];
      } else {
        hi = std::max(hi, vm[k]);
        lo = std::min(lo, vm[k]);
      }
      ++n_in;
    } else {
      ++n_rest;
    }
  }
  // TYPED EXCLUSION: a segment with nothing inside the range, or nothing left
  // after it, has NO opening range — not a degenerate one.
  if (n_in == 0 || n_rest == 0) {
    return out;
  }
  out.hi = hi;
  out.lo = lo;
  out.t1 = t1;
  out.valid = true;
  return out;
}

std::vector<OrExtLevel> orext_flag_levels(const OpeningRange& r) {
  std::vector<OrExtLevel> out;
  if (!r.valid) {
    return out;
  }
  const double rng = r.hi - r.lo;
  for (std::size_t i = 0; i < kOrExtKCount; ++i) {
    const double k = kOrExtK[i];
    if (k < kOrExtKMin) {
      continue;  // F-D6 is "beyond an OR_EXT k >= 1.5 level", not any level
    }
    out.push_back(OrExtLevel{r.t1, r.hi + k * rng, 1, r.phase});
    out.push_back(OrExtLevel{r.t1, r.lo - k * rng, -1, r.phase});
  }
  return out;
}

bool beyond_extension(double mid, std::int32_t sec, std::int8_t phase,
                      const std::vector<OrExtLevel>& cells) {
  for (const OrExtLevel& c : cells) {
    if (sec < c.t1 || phase != c.phase) {
      continue;
    }
    if (c.side > 0 && mid >= c.price) {
      return true;
    }
    if (c.side < 0 && mid <= c.price) {
      return true;
    }
  }
  return false;
}

}  // namespace qr::gen
