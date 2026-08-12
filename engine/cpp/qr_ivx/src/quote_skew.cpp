#include "qr_ivx/quote_skew.hpp"

#include <cmath>
#include <limits>

#include "qr_w21/surface.hpp"

namespace qr::ivx {
namespace {

Typed<double> absent(Validity why) noexcept { return Typed<double>{0.0, why}; }
Typed<double> valid(double value) noexcept {
  return std::isfinite(value) ? Typed<double>{value, Validity::VALID}
                              : Typed<double>{0.0, Validity::NONFINITE};
}

/// A quote is usable at a grid second when it is STRICTLY PRIOR to that
/// second's boundary, at most the W2.1 age gate old, and two-sided with a
/// positive bid at or below the ask.
///
/// `boundary_ms` is `open + second * 1000` — the grid endpoint's own instant,
/// the same convention the emitted 1s midpoint grid uses (endpoint `s` carries
/// the last eligible midpoint STRICTLY BEFORE `open + s` seconds). Using the
/// END of the second instead would let a quote posted inside the second value
/// that same second.
bool usable(std::int64_t boundary_ms, std::int64_t bid_u6, std::int64_t ask_u6,
            std::int64_t ts_ms_b, bool present) noexcept {
  if (!present) return false;
  if (bid_u6 <= 0 || ask_u6 <= 0 || bid_u6 > ask_u6) return false;
  if (ts_ms_b >= boundary_ms) return false;  // STRICTLY prior, never equal
  return boundary_ms - ts_ms_b <= qr::w21::kContractAgeGateMs;
}

double mid_of(std::int64_t bid_u6, std::int64_t ask_u6) noexcept {
  return 0.5 * (static_cast<double>(bid_u6) + static_cast<double>(ask_u6));
}

}  // namespace

QuoteSkewBuilder::QuoteSkewBuilder(std::int64_t open_ms_b, std::int64_t session_epoch_day,
                                   std::int64_t plane_dte,
                                   const std::vector<std::int64_t>* grid_mid_u6,
                                   std::int64_t retain_from, std::int64_t retain_to)
    : open_ms_b_(open_ms_b),
      session_epoch_day_(session_epoch_day),
      plane_dte_(plane_dte),
      grid_mid_u6_(grid_mid_u6),
      retain_from_(retain_from),
      retain_to_(retain_to) {
  for (std::size_t window = 0; window < kWindows; ++window) {
    windows_[window].window = static_cast<std::int64_t>(window);
  }
}

void QuoteSkewBuilder::observe(const qr::sources::OptionQuoteRow& row) {
  ++rows_observed_;
  namespace slots = qr::sources;
  if (row.is_null(slots::kOptionQuoteSlotExpiration) ||
      row.is_null(slots::kOptionQuoteSlotStrike) || row.is_null(slots::kOptionQuoteSlotRight) ||
      row.is_null(slots::kOptionQuoteSlotTimestamp)) {
    return;
  }
  if (row.right != qr::sources::Right::Call && row.right != qr::sources::Right::Put) {
    return;
  }
  const std::int64_t dte =
      static_cast<std::int64_t>(row.expiration_day) - session_epoch_day_;
  if (dte != plane_dte_) {
    return;
  }
  ++rows_on_plane_;

  // EVALUATE FIRST, THEN APPLY. The second's value must rest on quotes STRICTLY
  // PRIOR to the second's end, so every second that has fully elapsed is closed
  // out before this row is folded into the state.
  const std::int64_t elapsed_ms = row.ts_ms_b - open_ms_b_;
  if (elapsed_ms < 0) {
    return;
  }
  const std::int64_t second = elapsed_ms / 1000;
  evaluate_through(second);

  StrikeState& state = ladder_[row.strike_u6];
  const Quote quote{row.ts_ms_b,
                    row.is_null(slots::kOptionQuoteSlotBid) ? 0 : row.bid_u6,
                    row.is_null(slots::kOptionQuoteSlotAsk) ? 0 : row.ask_u6};
  if (row.right == qr::sources::Right::Call) {
    state.call = quote;
    state.has_call = true;
  } else {
    state.put = quote;
    state.has_put = true;
  }
}

void QuoteSkewBuilder::evaluate_through(std::int64_t second) {
  // Closes every grid second up to AND INCLUDING `second`: that second's
  // boundary instant has already passed once a row stamped at or after it has
  // arrived, and `usable` is what keeps the read strictly prior.
  const std::int64_t last = kWindowSeconds * static_cast<std::int64_t>(kWindows);
  while (next_second_ <= second && next_second_ < last) {
    const QuoteSkewSecond value = evaluate_one(next_second_);
    const auto window = static_cast<std::size_t>(next_second_ / kWindowSeconds);
    Accumulator& accumulator = accumulator_[window];
    if (value.state != Validity::MODALITY_ABSENT) {
      ++accumulator.present;
    }
    if (value.state == Validity::VALID) {
      ++accumulator.valid;
      for (std::size_t offset = 0; offset < value.tilt.size(); ++offset) {
        if (value.tilt[offset].v != Validity::VALID) continue;
        accumulator.tilt[offset] += value.tilt[offset].value;
        accumulator.log_ratio[offset] += value.log_ratio[offset].value;
        ++accumulator.support[offset];
      }
    }
    if (next_second_ >= retain_from_ && next_second_ <= retain_to_) {
      retained_.push_back(value);
    }
    ++next_second_;
  }
}

QuoteSkewSecond QuoteSkewBuilder::evaluate_one(std::int64_t second) const {
  QuoteSkewSecond out;
  out.second = second;
  const std::int64_t boundary_ms = open_ms_b_ + second * 1000;

  if (grid_mid_u6_ == nullptr ||
      static_cast<std::size_t>(second) >= grid_mid_u6_->size()) {
    out.state = Validity::CLOCK_UNAVAILABLE;
    return out;
  }
  const std::int64_t spot = (*grid_mid_u6_)[static_cast<std::size_t>(second)];
  if (spot <= 0) {
    out.state = Validity::MISSING;
    return out;
  }
  out.spot_u6 = spot;

  // The ladder of this second: every strike whose BOTH rights are usable.
  std::vector<std::int64_t> rungs;
  for (const auto& [strike, state] : ladder_) {
    const bool call_ok = usable(boundary_ms, state.call.bid_u6, state.call.ask_u6,
                                state.call.ts_ms_b, state.has_call);
    const bool put_ok = usable(boundary_ms, state.put.bid_u6, state.put.ask_u6, state.put.ts_ms_b,
                               state.has_put);
    if (call_ok && put_ok) {
      rungs.push_back(strike);
    }
  }
  out.ladder_rungs = static_cast<std::int64_t>(rungs.size());
  if (rungs.empty()) {
    out.state = Validity::ONE_SIDED;
    return out;
  }

  // Q5's ATM rule, and its ratified tie reading: equidistant candidates are
  // UNDECIDABLE, never broken by an identifier.
  std::size_t best = rungs.size();
  std::int64_t best_abs = std::numeric_limits<std::int64_t>::max();
  std::int64_t best_signed = 0;
  bool tied = false;
  for (std::size_t index = 0; index < rungs.size(); ++index) {
    const auto x = qr::w21::moneyness_log_bps(rungs[index], spot);
    if (!x.has_value()) continue;
    const std::int64_t magnitude = x.value() < 0 ? -x.value() : x.value();
    if (magnitude > qr::w21::kStraddleMaxAbsBps) continue;
    if (magnitude < best_abs) {
      best_abs = magnitude;
      best = index;
      best_signed = x.value();
      tied = false;
    } else if (magnitude == best_abs) {
      tied = true;
    }
  }
  if (best == rungs.size()) {
    out.state = Validity::MISSING;
    return out;
  }
  if (tied) {
    out.state = Validity::EQUAL_TIME_UNORDERED;
    return out;
  }
  out.atm_strike_u6 = rungs[best];
  out.atm_moneyness_bps = best_signed;

  const StrikeState& atm = ladder_.at(rungs[best]);
  const double call_atm = mid_of(atm.call.bid_u6, atm.call.ask_u6);
  const double put_atm = mid_of(atm.put.bid_u6, atm.put.ask_u6);
  const double straddle = call_atm + put_atm;
  if (!(straddle > 0.0)) {
    out.state = Validity::NONPOSITIVE;
    return out;
  }
  out.straddle_mid_u6 = valid(straddle);
  out.state = Validity::VALID;

  // Offset 0 is the ATM rung itself; offsets 1..2 walk the ladder outward.
  out.tilt[0] = valid((put_atm - call_atm) / straddle);
  out.log_ratio[0] = valid(std::log(put_atm / call_atm));
  for (std::size_t index = 0; index < kQuoteSkewOffsets.size(); ++index) {
    const std::int64_t step = kQuoteSkewOffsets[index];
    const auto down = static_cast<std::int64_t>(best) - step;
    const auto up = static_cast<std::int64_t>(best) + step;
    if (down < 0 || up >= static_cast<std::int64_t>(rungs.size())) {
      out.tilt[index + 1] = absent(Validity::MISSING);
      out.log_ratio[index + 1] = absent(Validity::MISSING);
      continue;
    }
    const StrikeState& lower = ladder_.at(rungs[static_cast<std::size_t>(down)]);
    const StrikeState& upper = ladder_.at(rungs[static_cast<std::size_t>(up)]);
    const double put_mid = mid_of(lower.put.bid_u6, lower.put.ask_u6);
    const double call_mid = mid_of(upper.call.bid_u6, upper.call.ask_u6);
    if (!(put_mid > 0.0) || !(call_mid > 0.0)) {
      out.tilt[index + 1] = absent(Validity::NONPOSITIVE);
      out.log_ratio[index + 1] = absent(Validity::NONPOSITIVE);
      continue;
    }
    out.tilt[index + 1] = valid((put_mid - call_mid) / straddle);
    out.log_ratio[index + 1] = valid(std::log(put_mid / call_mid));
  }
  return out;
}

void QuoteSkewBuilder::finish() {
  evaluate_through(kWindowSeconds * static_cast<std::int64_t>(kWindows) - 1);
  for (std::size_t window = 0; window < kWindows; ++window) {
    QuoteSkewWindow& out = windows_[window];
    const Accumulator& accumulator = accumulator_[window];
    out.seconds_present = accumulator.present;
    out.seconds_valid = accumulator.valid;
    for (std::size_t offset = 0; offset < 3; ++offset) {
      out.support[offset] = accumulator.support[offset];
      if (accumulator.support[offset] > 0) {
        const auto n = static_cast<double>(accumulator.support[offset]);
        out.mean_tilt[offset] = valid(accumulator.tilt[offset] / n);
        out.mean_log_ratio[offset] = valid(accumulator.log_ratio[offset] / n);
      } else {
        out.mean_tilt[offset] = absent(Validity::MISSING);
        out.mean_log_ratio[offset] = absent(Validity::MISSING);
      }
    }
    if (window > 0 && out.mean_tilt[1].v == Validity::VALID &&
        windows_[window - 1].mean_tilt[1].v == Validity::VALID) {
      out.d_mean_tilt_1 = valid(out.mean_tilt[1].value - windows_[window - 1].mean_tilt[1].value);
    }
  }
}

void emit(Report& report, const std::string& key, const QuoteSkewBuilder& builder,
          bool retain_seconds) {
  report.metric("qskew", key, "rows_observed", builder.rows_observed());
  report.metric("qskew", key, "rows_on_plane", builder.rows_on_plane());
  for (const QuoteSkewWindow& window : builder.windows()) {
    const std::string row = key + "/w" + std::to_string(window.window);
    report.metric("qskew", row, "seconds_present", window.seconds_present);
    report.metric("qskew", row, "seconds_valid", window.seconds_valid);
    for (std::size_t offset = 0; offset < 3; ++offset) {
      const std::string name = "off" + std::to_string(offset);
      report.metric("qskew", row, name + "_support", window.support[offset]);
      report.typed("qskew", row, name + "_mean_tilt", window.mean_tilt[offset]);
      report.typed("qskew", row, name + "_mean_log_ratio", window.mean_log_ratio[offset]);
    }
    report.typed("qskew", row, "d_mean_tilt_off1", window.d_mean_tilt_1);
  }
  if (!retain_seconds) {
    return;
  }
  for (const QuoteSkewSecond& one : builder.seconds()) {
    const std::string row = key + "/t" + std::to_string(one.second);
    report.text("qskew_second", row, "state", qr::validity_name(one.state));
    if (one.state != Validity::VALID) continue;
    report.metric("qskew_second", row, "spot_u6", one.spot_u6);
    report.metric("qskew_second", row, "atm_strike_u6", one.atm_strike_u6);
    report.metric("qskew_second", row, "atm_moneyness_bps", one.atm_moneyness_bps);
    report.metric("qskew_second", row, "ladder_rungs", one.ladder_rungs);
    report.typed("qskew_second", row, "straddle_mid_u6", one.straddle_mid_u6);
    for (std::size_t offset = 0; offset < 3; ++offset) {
      const std::string name = "off" + std::to_string(offset);
      report.typed("qskew_second", row, name + "_tilt", one.tilt[offset]);
      report.typed("qskew_second", row, name + "_log_ratio", one.log_ratio[offset]);
    }
  }
}

}  // namespace qr::ivx
