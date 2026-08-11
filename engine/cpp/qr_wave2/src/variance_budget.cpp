#include "qr_wave2/variance_budget.hpp"

#include <algorithm>
#include <cmath>

#include "qr_carriers/transforms.hpp"

namespace qr::wave2 {
namespace {

constexpr const char* kSite = "qr_wave2::VarianceBudgetSession";

/// ln(x) for the two log channels the pin names. It is NOT one of the card's
/// seven transform rows — W2.2-PIN-1 writes `ln B` and `ln B(t) - ln B(t-60s)`
/// itself — so it lives here, once, with the nonpositive guard the arithmetic
/// law requires ("Zero/missing B typed", never clipped).
[[nodiscard]] Typed<double> natural_log(double value) noexcept {
  if (!(value > 0.0) || !std::isfinite(value)) {
    return carriers::masked(Validity::MISSING);
  }
  return carriers::present(std::log(value));
}

/// The location law's oriented displacement, in bps of the REFERENCE:
/// "sigma*(m-reference)*10000/reference".
[[nodiscard]] Typed<double> oriented_bps(double sigma, std::int64_t m_u6,
                                         std::int64_t reference_u6) noexcept {
  const auto bps = carriers::displacement_bps_value(m_u6 - reference_u6, reference_u6);
  if (!bps.has_value() || bps.value().v != Validity::VALID) {
    return carriers::masked(Validity::MISSING);
  }
  return carriers::present(sigma * bps.value().value);
}

}  // namespace

const char* variance_budget_channel_name(std::size_t channel) noexcept {
  switch (channel) {
    case kVbXtildeOpen: return "VB_XTILDE_OPEN";
    case kVbXtildeHigh: return "VB_XTILDE_HIGH";
    case kVbXtildeLow: return "VB_XTILDE_LOW";
    case kVbXtildeVwap: return "VB_XTILDE_VWAP";
    case kVbXtildeRange: return "VB_XTILDE_RANGE";
    case kVbBudgetConsumed: return "VB_BUDGET_CONSUMED";
    case kVbLogB: return "VB_LOG_B";
    case kVbDeltaLogB60: return "VB_DLOG_B_60S";
    default: return "VB_UNKNOWN";
  }
}

bool variance_budget_channel_is_continuous(std::size_t channel) noexcept {
  return channel < kVarianceBudgetChannelCount;
}

std::optional<double> VarianceBudgetSession::window_sum_r2(std::size_t index,
                                                           std::int64_t seconds) const noexcept {
  // THE WINDOW MUST FIT INSIDE THE ELAPSED SESSION (see the header note).
  if (static_cast<std::int64_t>(index) < seconds) {
    return std::nullopt;
  }
  const std::size_t first = index - static_cast<std::size_t>(seconds);
  const std::int64_t steps = cum_valid_steps_[index] - cum_valid_steps_[first];
  if (steps <= 0) {
    return std::nullopt;
  }
  return cum_r2_[index] - cum_r2_[first];
}

Expected<VarianceBudgetSession, Refusal> VarianceBudgetSession::build(
    const VarianceBudgetInputs& inputs, const DestructionControls& controls) {
  if (inputs.grid == nullptr) {
    return Expected<VarianceBudgetSession, Refusal>::refuse(
        Refusal(RefusalCode::CONFIG, kSite, "a variance budget needs the session's 1s grid"));
  }
  if (inputs.vwap_notional_prefix.size() != inputs.stock_print_groups.size() ||
      inputs.vwap_size_prefix.size() != inputs.stock_print_groups.size()) {
    return Expected<VarianceBudgetSession, Refusal>::refuse(
        Refusal(RefusalCode::CONTENT_MISMATCH, kSite,
                "the VWAP prefix arrays must be aligned one-for-one with the print groups",
                static_cast<std::int64_t>(inputs.vwap_notional_prefix.size())));
  }

  VarianceBudgetSession session;
  const std::vector<carriers::GridPoint>& points = inputs.grid->points();
  const std::size_t count = points.size();
  session.present_.resize(count, 0U);
  session.mid_u6_.resize(count, 0);
  session.cum_r2_.resize(count, 0.0);
  session.cum_valid_steps_.resize(count, 0);
  session.budget_.resize(count, 0.0);
  session.budget_present_.resize(count, 0U);
  session.run_high_u6_.resize(count, 0);
  session.run_low_u6_.resize(count, 0);
  session.run_high_index_.resize(count, 0);
  session.run_low_index_.resize(count, 0);
  session.run_present_.resize(count, 0U);
  session.vwap_u6_.resize(count, 0);
  session.vwap_present_.resize(count, 0U);
  session.census_.endpoints = static_cast<std::int64_t>(count);
  session.rv_prior_total_ = inputs.priors.rv_prior_present ? inputs.priors.rv_prior_total : 0.0;

  // --- pass 1: the return series, the cumulative sums, the running extremes ---
  for (std::size_t index = 0; index < count; ++index) {
    const carriers::GridPoint& point = points[index];
    session.present_[index] = point.present ? 1U : 0U;
    session.mid_u6_[index] = point.mid_u6;

    double cumulative = index == 0 ? 0.0 : session.cum_r2_[index - 1U];
    std::int64_t steps = index == 0 ? 0 : session.cum_valid_steps_[index - 1U];
    if (index > 0 && point.present && points[index - 1U].present && point.mid_u6 > 0 &&
        points[index - 1U].mid_u6 > 0) {
      // "r(s) = 1e4 * dln(m) per valid 1s grid step (bps)". A carried unchanged
      // midpoint gives ln(1) = 0 and contributes a zero return, exactly as the
      // frozen grid law says — it is a valid step, not a missing one.
      const double ratio = static_cast<double>(point.mid_u6) /
                           static_cast<double>(points[index - 1U].mid_u6);
      const double r_bps = static_cast<double>(carriers::kBpsScale) * std::log(ratio);
      cumulative += r_bps * r_bps;
      ++steps;
    }
    session.cum_r2_[index] = cumulative;
    session.cum_valid_steps_[index] = steps;

    // Running extremes over PRESENT endpoints, with the endpoint at which each
    // was first attained: a later equal touch does not re-set an extreme, so
    // "t_of_current_running_extreme" is the moment it came into being.
    const bool had_previous = index > 0 && session.run_present_[index - 1U] != 0U;
    if (had_previous) {
      session.run_high_u6_[index] = session.run_high_u6_[index - 1U];
      session.run_low_u6_[index] = session.run_low_u6_[index - 1U];
      session.run_high_index_[index] = session.run_high_index_[index - 1U];
      session.run_low_index_[index] = session.run_low_index_[index - 1U];
      session.run_present_[index] = 1U;
    }
    if (point.present && point.mid_u6 > 0) {
      if (!session.open_present_) {
        session.open_present_ = true;
        session.open_u6_value_ = point.mid_u6;
      }
      if (session.run_present_[index] == 0U) {
        session.run_present_[index] = 1U;
        session.run_high_u6_[index] = point.mid_u6;
        session.run_low_u6_[index] = point.mid_u6;
        session.run_high_index_[index] = static_cast<std::int64_t>(index);
        session.run_low_index_[index] = static_cast<std::int64_t>(index);
      } else {
        if (point.mid_u6 > session.run_high_u6_[index]) {
          session.run_high_u6_[index] = point.mid_u6;
          session.run_high_index_[index] = static_cast<std::int64_t>(index);
        }
        if (point.mid_u6 < session.run_low_u6_[index]) {
          session.run_low_u6_[index] = point.mid_u6;
          session.run_low_index_[index] = static_cast<std::int64_t>(index);
        }
      }
    }
  }
  session.census_.valid_steps = count == 0 ? 0 : session.cum_valid_steps_[count - 1U];

  // --- pass 2: the running VWAP at each endpoint, STRICTLY PRIOR --------------
  // One forward merge over two sorted sequences: the print groups' timestamps
  // and the endpoints. `strictly before` is the same rule the location layer
  // applies, and the equal-time group law is honored because the prefix arrays
  // are indexed by whole GROUPS — a group is never half-included.
  {
    std::size_t group = 0;
    for (std::size_t index = 0; index < count; ++index) {
      const std::int64_t endpoint_ns = inputs.grid->endpoint_ns(index);
      while (group < inputs.stock_print_groups.size() &&
             inputs.stock_print_groups[group].ts_ns_a < endpoint_ns) {
        ++group;
      }
      if (group == 0) {
        continue;  // no print group is strictly before this endpoint
      }
      const std::int64_t size_sum = inputs.vwap_size_prefix[group - 1U];
      const std::int64_t notional_sum = inputs.vwap_notional_prefix[group - 1U];
      if (size_sum > 0) {
        session.vwap_u6_[index] = notional_sum / size_sum;
        session.vwap_present_[index] = 1U;
      }
    }
  }

  // --- pass 3: B(t) ----------------------------------------------------------
  for (std::size_t index = 0; index < count; ++index) {
    if (!inputs.priors.rv_prior_present) {
      ++session.census_.budget_absent_no_prior;
      continue;
    }
    const std::optional<double> sum_1m = session.window_sum_r2(index, kRv1mSeconds);
    const std::optional<double> sum_5m = session.window_sum_r2(index, kRv5mSeconds);
    if (!sum_1m.has_value() || !sum_5m.has_value()) {
      if (static_cast<std::int64_t>(index) < kRv5mSeconds) {
        ++session.census_.budget_absent_window;
      } else {
        ++session.census_.budget_absent_no_valid_step;
      }
      continue;
    }
    const double rv_1m = sum_1m.value() / static_cast<double>(kRv1mSeconds);
    const double rv_5m = sum_5m.value() / static_cast<double>(kRv5mSeconds);
    const double budget = kWeightRv1m * rv_1m + kWeightRv5m * rv_5m +
                          kWeightRvPrior * inputs.priors.rv_prior_rate;
    if (!(budget > 0.0) || !std::isfinite(budget)) {
      continue;  // "Zero/missing B typed" — left absent, never floored
    }
    session.budget_[index] = budget;
    session.budget_present_[index] = 1U;
    ++session.census_.budget_present;
  }

#ifndef QR_WAVE2_NO_DESTRUCTIONS
  // THE DESTRUCTION TWIN, IN THE SAME CONSTRUCTOR (FINAL_PLAN section 6):
  // "B_const = equal-weight time-mean of B(t) over the session's valid seconds,
  // substituted session-constant (dlogB == 0)."
  if (controls.session_constant_budget) {
    double sum = 0.0;
    std::int64_t counted = 0;
    for (std::size_t index = 0; index < count; ++index) {
      if (session.budget_present_[index] != 0U) {
        sum += session.budget_[index];
        ++counted;
      }
    }
    if (counted > 0) {
      const double constant = sum / static_cast<double>(counted);
      for (std::size_t index = 0; index < count; ++index) {
        if (session.budget_present_[index] != 0U) {
          session.budget_[index] = constant;
        }
      }
      session.census_.destruction_constant_budget = counted;
    }
  }
#else
  (void)controls;
#endif
  return session;
}

Typed<double> VarianceBudgetSession::budget(std::size_t endpoint_index) const noexcept {
  if (endpoint_index >= budget_present_.size() || budget_present_[endpoint_index] == 0U) {
    return carriers::masked(Validity::MISSING);
  }
  return carriers::present(budget_[endpoint_index]);
}

Typed<double> VarianceBudgetSession::sigma_scale_bps(std::size_t endpoint_index) const noexcept {
  const Typed<double> b = budget(endpoint_index);
  if (b.v != Validity::VALID) {
    return carriers::masked(b.v);
  }
  // "sigma_scale(t) = sqrt(B(t)*1800) bps" (W2.13-PIN-1). B is bps^2/s, so the
  // product is bps^2 over a half-hour and the root is bps.
  return carriers::present(std::sqrt(b.value * 1800.0));
}

Typed<std::int64_t> VarianceBudgetSession::running_vwap_u6(
    std::size_t endpoint_index) const noexcept {
  if (endpoint_index >= vwap_present_.size() || vwap_present_[endpoint_index] == 0U) {
    return Typed<std::int64_t>{0, Validity::MISSING};
  }
  return Typed<std::int64_t>{vwap_u6_[endpoint_index], Validity::VALID};
}

Typed<std::int64_t> VarianceBudgetSession::open_u6() const noexcept {
  if (!open_present_) {
    return Typed<std::int64_t>{0, Validity::MISSING};
  }
  return Typed<std::int64_t>{open_u6_value_, Validity::VALID};
}

VarianceBudgetRow VarianceBudgetSession::channels(std::size_t endpoint_index,
                                                  Side side) const noexcept {
  VarianceBudgetRow row;
  if (endpoint_index >= present_.size()) {
    return row;
  }
  const double sigma = carriers::sigma_of(side);
  const Typed<double> b = budget(endpoint_index);
  const bool have_m = present_[endpoint_index] != 0U && mid_u6_[endpoint_index] > 0;
  const std::int64_t m_u6 = mid_u6_[endpoint_index];

  // X/sqrt(B*tau) for the five X's. tau < 10s is TYPED, never divided.
  const auto scaled = [&](Typed<double> x, std::int64_t tau_seconds) -> Typed<double> {
    if (x.v != Validity::VALID || b.v != Validity::VALID) {
      return carriers::masked(Validity::MISSING);
    }
    if (tau_seconds < kTauMinSeconds) {
      return carriers::masked(Validity::MISSING);
    }
    const double denominator = std::sqrt(b.value * static_cast<double>(tau_seconds));
    if (!(denominator > 0.0) || !std::isfinite(denominator)) {
      return carriers::masked(Validity::MISSING);
    }
    return carriers::present(x.value / denominator);
  };

  // "open & VWAP & range => tau = t_since_open" — the endpoint index IS the
  // seconds since the session start, by the grid's own definition.
  const std::int64_t tau_open = static_cast<std::int64_t>(endpoint_index);

  if (have_m && open_present_) {
    row.set(kVbXtildeOpen, scaled(oriented_bps(sigma, m_u6, open_u6_value_), tau_open));
  }
  if (have_m && run_present_[endpoint_index] != 0U) {
    // "high/low => tau = t - t_of_current_running_extreme".
    const std::int64_t tau_high =
        static_cast<std::int64_t>(endpoint_index) - run_high_index_[endpoint_index];
    const std::int64_t tau_low =
        static_cast<std::int64_t>(endpoint_index) - run_low_index_[endpoint_index];
    row.set(kVbXtildeHigh, scaled(oriented_bps(sigma, m_u6, run_high_u6_[endpoint_index]),
                                  tau_high));
    row.set(kVbXtildeLow, scaled(oriented_bps(sigma, m_u6, run_low_u6_[endpoint_index]), tau_low));
    if (open_present_) {
      // "range is (high-low)*10000/open" — a width, not an oriented distance.
      const auto range = carriers::displacement_bps_value(
          run_high_u6_[endpoint_index] - run_low_u6_[endpoint_index], open_u6_value_);
      if (range.has_value()) {
        row.set(kVbXtildeRange, scaled(range.value(), tau_open));
      }
    }
  }
  if (have_m && vwap_present_[endpoint_index] != 0U) {
    row.set(kVbXtildeVwap, scaled(oriented_bps(sigma, m_u6, vwap_u6_[endpoint_index]), tau_open));
  }

  // budget_consumed = (Sum_{open..t} r^2)/RV_prior_TOTAL, guard > 0.
  if (rv_prior_total_ > 0.0) {
    row.set(kVbBudgetConsumed, carriers::present(cum_r2_[endpoint_index] / rv_prior_total_));
  }

  row.set(kVbLogB, b.v == Validity::VALID ? natural_log(b.value)
                                          : carriers::masked(Validity::MISSING));
  if (static_cast<std::int64_t>(endpoint_index) >= kDeltaLogBSeconds) {
    const Typed<double> before =
        budget(endpoint_index - static_cast<std::size_t>(kDeltaLogBSeconds));
    const Typed<double> now_log = b.v == Validity::VALID ? natural_log(b.value)
                                                        : carriers::masked(Validity::MISSING);
    const Typed<double> before_log = before.v == Validity::VALID
                                         ? natural_log(before.value)
                                         : carriers::masked(Validity::MISSING);
    if (now_log.v == Validity::VALID && before_log.v == Validity::VALID) {
      row.set(kVbDeltaLogB60, carriers::present(now_log.value - before_log.value));
    }
  }
  return row;
}

}  // namespace qr::wave2
