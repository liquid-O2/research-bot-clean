// qrdisc native family: `_prior_reaction_map` (discretionary_features.py:2321).
//
// WHAT IT MEASURES
//   How the tape reacted the LAST time this price level was attacked, before
//   the formation moment.  The attack timestamps come from the shared
//   `_event_streams` kernel (qrdisc_kernels_events.hpp:67); this family reads
//   only the `attack_ts` column of it, then replays each burst against the
//   economic mid series.
//
// FLOAT LAW
//   The reaction path is integer mid2 arithmetic scaled once by `factor`, so
//   every favorable/adverse extreme is an exact order statistic.  Only the
//   per-horizon `np.mean` and `_slope` are reductions, and both are delegated
//   to numpy (qrdisc_kernels_events.hpp:14-29).
#include "qr_entry_v2/qrdisc_maps.hpp"

#include <algorithm>
#include <string>
#include <vector>

#include "qr_entry_v2/qrdisc_kernels_events.hpp"
#include "qr_entry_v2/qrdisc_np_kernels.hpp"

namespace {

constexpr std::int64_t kNanosPerSecond = 1000000000;
// discretionary_features.py:2330 — two attacks closer than this are one burst.
constexpr std::int64_t kQrdiscBurstGapNs = 5000000000;
// :2338 and :2340.
const std::int64_t kQrdiscPriorHorizons[] = {5, 30, 120};
constexpr std::size_t kQrdiscPriorMaxCompleted = 20;

bool qrdisc_prior_scalar_int64(QrdiscPlaneObject* plane, const char* name,
                               std::int64_t* out) {
  PyObject* value = PyDict_GetItemString(plane->scalars, name);
  if (value == nullptr) {
    PyErr_Format(PyExc_KeyError, "qrdisc: scalar '%s' is missing", name);
    return false;
  }
  return qrdisc_as_int64(value, name, out);
}

}  // namespace

bool qrdisc_prior_reaction_map(QrdiscPlaneObject* plane,
                               const QrdiscRowInputs& row, QrdiscValueMap* out) {
  const QrdiscBuffer* economic_ts_buffer =
      qrdisc_plane_buffer_named(plane, "attr___economic_ts", NPY_INT64, 1);
  const QrdiscBuffer* economic_mid2_buffer =
      qrdisc_plane_buffer_named(plane, "attr___economic_mid2", NPY_INT64, 1);
  if (economic_ts_buffer == nullptr || economic_mid2_buffer == nullptr) return false;
  const QrdiscI64Span economic_ts{
      static_cast<const std::int64_t*>(economic_ts_buffer->data),
      static_cast<std::int64_t>(economic_ts_buffer->shape[0])};
  const std::int64_t* economic_mid2 =
      static_cast<const std::int64_t*>(economic_mid2_buffer->data);
  PyObject* factor_object = PyDict_GetItemString(plane->scalars, "factor");
  if (factor_object == nullptr) {
    PyErr_SetString(PyExc_KeyError, "qrdisc: scalar 'factor' is missing");
    return false;
  }
  const double factor = PyFloat_AsDouble(factor_object);
  if (factor == -1.0 && PyErr_Occurred()) return false;
  std::int64_t raw_tick = 0;
  std::int64_t multiplier = 0;
  if (!qrdisc_prior_scalar_int64(plane, "raw_tick", &raw_tick) ||
      !qrdisc_prior_scalar_int64(plane, "multiplier", &multiplier)) {
    return false;
  }
  std::int64_t formation_ts_ns = 0;
  if (!qrdisc_mapping_int64(row.formation_candidate, "decision_ts_ns",
                            &formation_ts_ns)) {
    return false;
  }

  QrdiscEventStreams streams;
  if (!qrdisc_event_streams(plane, row.formation_tick, 2, plane->open_ns,
                            formation_ts_ns, row.side, &streams)) {
    return false;
  }
  // `attack[np.r_[True, np.diff(attack) > 5e9]]` (:2330): the first attack plus
  // every one that opens a new burst.
  const std::vector<std::int64_t>& attack = streams.attack.ts;
  std::vector<std::int64_t> burst;
  for (std::size_t index = 0; index < attack.size(); ++index) {
    if (index == 0 || attack[index] - attack[index - 1] > kQrdiscBurstGapNs) {
      burst.push_back(attack[index]);
    }
  }
  out->emplace_back("disc_origin_prior_attack_bursts",
                    static_cast<double>(burst.size()));
  out->emplace_back(
      "disc_origin_last_attack_age_sec",
      burst.empty() ? 0.0
                    : static_cast<double>(formation_ts_ns - burst.back()) / 1e9);

  for (const std::int64_t horizon : kQrdiscPriorHorizons) {
    const std::int64_t width_ns = horizon * kNanosPerSecond;
    // `burst[burst + horizon * 1e9 <= formation_ts_ns][-20:]` (:2339-2340).
    // `burst` is non-decreasing, so the mask selects a prefix and the tail slice
    // is its last twenty entries.
    std::size_t completed_end = 0;
    while (completed_end < burst.size() &&
           burst[completed_end] + width_ns <= formation_ts_ns) {
      ++completed_end;
    }
    const std::size_t completed_begin =
        completed_end > kQrdiscPriorMaxCompleted
            ? completed_end - kQrdiscPriorMaxCompleted
            : 0;
    std::vector<double> favorable;
    std::vector<double> adverse;
    for (std::size_t index = completed_begin; index < completed_end; ++index) {
      const std::int64_t timestamp = burst[index];
      const std::int64_t left =
          qrdisc_searchsorted_left_i64(economic_ts, timestamp);
      const std::int64_t right =
          qrdisc_searchsorted_left_i64(economic_ts, timestamp + width_ns);
      if (left >= right) continue;
      const std::int64_t base = economic_mid2[left > 0 ? left - 1 : 0];
      double highest = 0.0;
      double lowest = 0.0;
      for (std::int64_t slot = left; slot < right; ++slot) {
        const double step =
            qrdisc_aligned_usd(row.side, economic_mid2[slot], base, factor);
        if (slot == left || step > highest) highest = step;
        if (slot == left || step < lowest) lowest = step;
      }
      favorable.push_back(highest > 0.0 ? highest : 0.0);
      adverse.push_back(-lowest > 0.0 ? -lowest : 0.0);
    }

    const std::int64_t reactions = static_cast<std::int64_t>(favorable.size());
    double favorable_mean = 0.0;
    double adverse_mean = 0.0;
    double favorable_slope = 0.0;
    double adverse_slope = 0.0;
    if (reactions > 0 &&
        (!qrdisc_np_mean_f64(favorable.data(), reactions, &favorable_mean) ||
         !qrdisc_np_mean_f64(adverse.data(), reactions, &adverse_mean))) {
      return false;
    }
    // `_slope` is called unconditionally by the oracle (:2368, :2376); it
    // answers 0.0 for a list of fewer than two reactions.
    if (!qrdisc_slope(favorable.data(), reactions, &favorable_slope) ||
        !qrdisc_slope(adverse.data(), reactions, &adverse_slope)) {
      return false;
    }
    double favorable_max = 0.0;
    std::int64_t defended = 0;
    std::int64_t large = 0;
    // `4.0 * self.raw_tick * 1e-9 * self.multiplier` (:2384-2385), in the
    // oracle's own left-to-right association.
    const double large_origin_usd =
        4.0 * static_cast<double>(raw_tick) * 1e-9 * static_cast<double>(multiplier);
    for (std::size_t index = 0; index < favorable.size(); ++index) {
      if (index == 0 || favorable[index] > favorable_max) {
        favorable_max = favorable[index];
      }
      if (favorable[index] > adverse[index]) ++defended;
      if (favorable[index] >= large_origin_usd) ++large;
    }

    const std::string prefix = "disc_origin_h" + std::to_string(horizon) + "_";
    out->emplace_back(prefix + "completed_reactions",
                      static_cast<double>(reactions));
    out->emplace_back(prefix + "favorable_mean_usd", favorable_mean);
    out->emplace_back(prefix + "favorable_max_usd", favorable_max);
    out->emplace_back(prefix + "favorable_first_usd",
                      reactions ? favorable.front() : 0.0);
    out->emplace_back(prefix + "favorable_last_usd",
                      reactions ? favorable.back() : 0.0);
    out->emplace_back(prefix + "favorable_slope_usd", favorable_slope);
    out->emplace_back(prefix + "adverse_mean_usd", adverse_mean);
    out->emplace_back(prefix + "adverse_first_usd",
                      reactions ? adverse.front() : 0.0);
    out->emplace_back(prefix + "adverse_last_usd",
                      reactions ? adverse.back() : 0.0);
    out->emplace_back(prefix + "adverse_slope_usd", adverse_slope);
    out->emplace_back(prefix + "response_decay_usd",
                      reactions ? favorable.back() - favorable.front() : 0.0);
    // Both remaining reductions are over BOOLEAN arrays, whose numpy sum is an
    // exact integer count: no delegated reduction is needed for either.
    out->emplace_back(prefix + "defense_rate",
                      reactions ? static_cast<double>(defended) /
                                      static_cast<double>(reactions)
                                : 0.0);
    out->emplace_back(prefix + "large_origin_count",
                      reactions ? static_cast<double>(large) : 0.0);
  }
  return true;
}
