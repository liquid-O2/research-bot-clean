#include "qr_wave2/prior_state.hpp"

#include <algorithm>

#include "qr_carriers/transforms.hpp"
#include "qr_registry/warmup_scope.hpp"

namespace qr::wave2 {
namespace {

constexpr const char* kSite = "qr_wave2::PriorSessionHistory";

}  // namespace

Typed<double> true_range_bps(const SessionSummary& session,
                             std::int64_t prior_close_u6) noexcept {
  // "TR_s = [max(pH_s,pC_{s-1}) - min(pL_s,pC_{s-1})] in bps of pC_{s-1}".
  // A session without a present grid has no pH/pL and therefore no true range;
  // a nonpositive prior close is an invalid denominator, which the frozen
  // displacement row types MISSING rather than substituting for.
  if (!session.grid_present || prior_close_u6 <= 0) {
    return carriers::masked(Validity::MISSING);
  }
  const std::int64_t top = std::max(session.high_u6, prior_close_u6);
  const std::int64_t bottom = std::min(session.low_u6, prior_close_u6);
  const auto bps = carriers::displacement_bps_value(top - bottom, prior_close_u6);
  if (!bps.has_value()) {
    return carriers::masked(Validity::NONFINITE);
  }
  return bps.value();
}

Expected<std::size_t, Refusal> PriorSessionHistory::observe(const SessionSummary& summary) {
  if (summary.ordinal <= last_ordinal_) {
    return Expected<std::size_t, Refusal>::refuse(
        Refusal(RefusalCode::OUT_OF_ORDER, kSite,
                "sessions must be observed in strictly increasing calendar order",
                summary.ordinal));
  }
  Entry entry;
  entry.summary = summary;

  // The EWMA of the pin: seed = the FIRST OBSERVED session's value, then
  // alpha*new + (1-alpha)*old. A session with no rate (T_RTH <= 0) cannot enter
  // the average, so it carries the previous value forward unchanged rather than
  // seeding or dragging it with a zero.
  const bool have_previous = !entries_.empty();
  const double previous_rate = have_previous ? entries_.back().ewma_rate_after : 0.0;
  const double previous_total = have_previous ? entries_.back().ewma_total_after : 0.0;
  const bool previous_seeded = have_previous && seeded_;
  if (summary.has_rate()) {
    if (!previous_seeded) {
      entry.ewma_rate_after = summary.rth_rate();
      entry.ewma_total_after = summary.rth_sum_r2;
      seeded_ = true;
    } else {
      entry.ewma_rate_after = kEwmaAlpha * summary.rth_rate() + (1.0 - kEwmaAlpha) * previous_rate;
      entry.ewma_total_after =
          kEwmaAlpha * summary.rth_sum_r2 + (1.0 - kEwmaAlpha) * previous_total;
    }
  } else {
    entry.ewma_rate_after = previous_rate;
    entry.ewma_total_after = previous_total;
  }

  if (is_warmup_ordinal(summary.ordinal)) {
    ++warmup_sessions_;
  }
  last_ordinal_ = summary.ordinal;
  entries_.push_back(entry);
  return entries_.size() - 1U;
}

std::size_t PriorSessionHistory::source_position(std::size_t position,
                                                 const DestructionControls& controls) const noexcept {
#ifndef QR_WAVE2_NO_DESTRUCTIONS
  // A11's cross-session shuffle: the CALLER's fold-scoped map decides which
  // session's priors this position reads. Out-of-range entries are ignored
  // rather than wrapped, so a malformed map cannot silently read the future.
  if (controls.cross_session_shuffle && position < controls.shuffle_map.size()) {
    const std::int64_t mapped = controls.shuffle_map[position];
    if (mapped >= 0 && static_cast<std::size_t>(mapped) < entries_.size()) {
      return static_cast<std::size_t>(mapped);
    }
  }
#else
  (void)controls;
#endif
  return position;
}

PriorView PriorSessionHistory::view_for(std::size_t position,
                                        const DestructionControls& controls) const {
  PriorView view;
  const std::size_t source = source_position(position, controls);
  // STRICTLY PRIOR: entries [0, source) only. The session at `source` is the
  // one being constructed and its own reduction is not visible to it.
  if (source == 0 || source > entries_.size()) {
    return view;
  }
  const std::size_t priors = source;
  view.priors_available = static_cast<std::int64_t>(priors);

  const Entry& previous = entries_[source - 1U];
  if (previous.summary.grid_present) {
    view.prior_present = true;
    view.prior_high_u6 = previous.summary.high_u6;
    view.prior_low_u6 = previous.summary.low_u6;
    view.prior_close_u6 = previous.summary.close_u6;
  }
  if (previous.summary.vwap_present) {
    view.prior_vwap_present = true;
    view.prior_vwap_u6 = previous.summary.vwap_u6;
  }

  // H_k / L_k over the prior k sessions EXCLUDING today. A window is present
  // only when k full sessions exist AND every one of them carried a level:
  // "max(pH) over prior k" is not a max over whichever of them happened to have
  // one.
  const auto window_extremes = [&](std::int64_t k, bool& present, std::int64_t& high,
                                   std::int64_t& low) {
    present = false;
    if (static_cast<std::int64_t>(priors) < k) {
      return;
    }
    std::int64_t window_high = 0;
    std::int64_t window_low = 0;
    bool first = true;
    for (std::size_t index = priors - static_cast<std::size_t>(k); index < priors; ++index) {
      const SessionSummary& session = entries_[index].summary;
      if (!session.grid_present) {
        return;
      }
      window_high = first ? session.high_u6 : std::max(window_high, session.high_u6);
      window_low = first ? session.low_u6 : std::min(window_low, session.low_u6);
      first = false;
    }
    present = true;
    high = window_high;
    low = window_low;
  };
  window_extremes(kRangeWindowShort, view.range5_present, view.high5_u6, view.low5_u6);
  window_extremes(kRangeWindowLong, view.range20_present, view.high20_u6, view.low20_u6);

  // ATR14: the simple mean of the 14 prior sessions' true ranges. TR_s needs
  // pC_{s-1}, so the window needs FIFTEEN entries; with fewer the channel is
  // typed absent rather than averaged over a short window.
  if (static_cast<std::int64_t>(priors) >= kAtrWindowSessions + 1) {
    double sum = 0.0;
    std::int64_t counted = 0;
    const std::size_t first = priors - static_cast<std::size_t>(kAtrWindowSessions);
    for (std::size_t index = first; index < priors; ++index) {
      const Typed<double> range = true_range_bps(entries_[index].summary,
                                                 entries_[index - 1U].summary.close_u6);
      if (range.v != Validity::VALID) {
        counted = -1;
        break;
      }
      sum += range.value;
      ++counted;
    }
    if (counted == kAtrWindowSessions) {
      view.atr_present = true;
      view.atr14_bps = sum / static_cast<double>(kAtrWindowSessions);
    }
  }

  // The EWMA the previous session left behind — never one this session updated.
  if (previous.ewma_rate_after > 0.0 || previous.ewma_total_after > 0.0) {
    view.rv_prior_present = true;
    view.rv_prior_rate = previous.ewma_rate_after;
    view.rv_prior_total = previous.ewma_total_after;
  }
  return view;
}

Expected<PriorView, Refusal> PriorSessionHistory::view_for_ordinal(
    std::int64_t ordinal, const DestructionControls& controls) const {
  for (std::size_t index = 0; index < entries_.size(); ++index) {
    if (entries_[index].summary.ordinal == ordinal) {
      return view_for(index, controls);
    }
  }
  return Expected<PriorView, Refusal>::refuse(
      Refusal(RefusalCode::UNKNOWN_SESSION, kSite, "no observed session carries this ordinal",
              ordinal));
}

}  // namespace qr::wave2
