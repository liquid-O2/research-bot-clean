#include "qr_ivx/iv_cross.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <utility>

#include "qr_w21/surface.hpp"

namespace qr::ivx {
namespace {

constexpr double kNan = std::numeric_limits<double>::quiet_NaN();

/// A typed absent real, with the state that says WHY.
Typed<double> absent(Validity why) noexcept { return Typed<double>{0.0, why}; }
Typed<double> valid(double value) noexcept {
  return std::isfinite(value) ? Typed<double>{value, Validity::VALID}
                              : Typed<double>{0.0, Validity::NONFINITE};
}

/// Difference of two typed reals; absent whenever either side is.
Typed<double> difference(Typed<double> now, Typed<double> before) noexcept {
  if (now.v != Validity::VALID || before.v != Validity::VALID) {
    return absent(combine(now.v, before.v) == Validity::VALID ? Validity::MISSING
                                                             : combine(now.v, before.v));
  }
  return valid(now.value - before.value);
}

std::size_t band_right_slot(std::size_t band, std::uint8_t right) noexcept {
  return band * kRights + static_cast<std::size_t>(right);
}

/// Population weighted mean/stdev over a POINT SET, two-pass.
struct MeanStdev {
  Typed<double> mean{0.0, Validity::MISSING};
  Typed<double> stdev{0.0, Validity::MISSING};
};

MeanStdev mean_stdev(const std::vector<FitPoint>& points) {
  MeanStdev out;
  double weight = 0.0;
  double weighted = 0.0;
  for (const FitPoint& point : points) {
    if (point.weight <= 0) continue;
    weight += static_cast<double>(point.weight);
    weighted += static_cast<double>(point.weight) * point.y;
  }
  if (weight <= 0.0) {
    return out;
  }
  const double mean = weighted / weight;
  out.mean = valid(mean);
  double variance = 0.0;
  for (const FitPoint& point : points) {
    if (point.weight <= 0) continue;
    const double residual = point.y - mean;
    variance += static_cast<double>(point.weight) * residual * residual;
  }
  out.stdev = valid(std::sqrt(variance / weight));
  return out;
}

std::int64_t distinct_x_of(const std::vector<FitPoint>& points) {
  std::set<std::int32_t> seen;
  for (const FitPoint& point : points) {
    if (point.weight > 0) seen.insert(point.x_key);
  }
  return static_cast<std::int64_t>(seen.size());
}

std::int64_t total_weight_of(const std::vector<FitPoint>& points) {
  std::int64_t total = 0;
  for (const FitPoint& point : points) {
    if (point.weight > 0) total += point.weight;
  }
  return total;
}

/// Exact-order population median of a copy. Sorting a copy keeps the caller's
/// vector in tape order, which two-run identity depends on.
double median_of(std::vector<double> values) {
  if (values.empty()) return kNan;
  std::sort(values.begin(), values.end());
  const std::size_t half = values.size() / 2;
  if (values.size() % 2 == 1) {
    return values[half];
  }
  return 0.5 * (values[half - 1] + values[half]);
}

/// The q-th percentile by the census quantile law (smallest value v with
/// count(<= v) >= ceil(q*n)), on a sorted copy.
double percentile_of(std::vector<double> values, std::int64_t numerator,
                     std::int64_t denominator) {
  if (values.empty()) return kNan;
  std::sort(values.begin(), values.end());
  const auto n = static_cast<std::int64_t>(values.size());
  const std::int64_t rank = (n * numerator + denominator - 1) / denominator;  // ceil
  const std::int64_t index = std::min(std::max(rank, std::int64_t{1}), n) - 1;
  return values[static_cast<std::size_t>(index)];
}

int sign_of(double value) noexcept { return value > 0.0 ? 1 : (value < 0.0 ? -1 : 0); }

}  // namespace

// ---------------------------------------------------------------------------
// The moneyness axis.
// ---------------------------------------------------------------------------

std::size_t moneyness_band(std::int64_t x_bps) noexcept {
  // RIGHT-OPEN bins: band i is [edge[i-1], edge[i]). Linear scan over eight
  // edges; a binary search would buy nothing and could hide an off-by-one.
  for (std::size_t index = 0; index < kMoneynessEdgesBps.size(); ++index) {
    if (x_bps < kMoneynessEdgesBps[index]) {
      return index;
    }
  }
  return kMoneynessEdgesBps.size();
}

std::string band_label(std::size_t band) {
  if (band == 0) {
    return "b0[-INF," + std::to_string(kMoneynessEdgesBps[0]) + ")";
  }
  const std::string low = std::to_string(kMoneynessEdgesBps[band - 1]);
  if (band >= kMoneynessEdgesBps.size()) {
    return "b" + std::to_string(band) + "[" + low + ",+INF)";
  }
  return "b" + std::to_string(band) + "[" + low + "," +
         std::to_string(kMoneynessEdgesBps[band]) + ")";
}

// ---------------------------------------------------------------------------
// Weighted least squares.
// ---------------------------------------------------------------------------

Typed<double> LineFit::at(double x) const noexcept {
  if (intercept.v != Validity::VALID || slope.v != Validity::VALID) {
    return absent(Validity::MISSING);
  }
  return valid(intercept.value + slope.value * x);
}

LineFit fit_line(const std::vector<FitPoint>& points, std::int64_t min_distinct,
                 std::int64_t min_weight) {
  LineFit out;
  out.distinct_x = distinct_x_of(points);
  out.weight = total_weight_of(points);
  for (const FitPoint& point : points) {
    if (point.weight > 0) ++out.points;
  }
  if (out.distinct_x < min_distinct || out.weight < min_weight) {
    return out;
  }
  double w = 0.0;
  double wx = 0.0;
  double wy = 0.0;
  double wxx = 0.0;
  double wxy = 0.0;
  for (const FitPoint& point : points) {
    if (point.weight <= 0) continue;
    const double weight = static_cast<double>(point.weight);
    w += weight;
    wx += weight * point.x;
    wy += weight * point.y;
    wxx += weight * point.x * point.x;
    wxy += weight * point.x * point.y;
  }
  const double denominator = w * wxx - wx * wx;
  if (!(std::abs(denominator) > 0.0) || !std::isfinite(denominator)) {
    // Every point sat on one x. `distinct_x` should already have caught it;
    // this is the arithmetic's own refusal, not a second opinion.
    out.slope = absent(Validity::NONFINITE);
    out.intercept = absent(Validity::NONFINITE);
    return out;
  }
  const double slope = (w * wxy - wx * wy) / denominator;
  const double intercept = (wy - slope * wx) / w;
  out.slope = valid(slope);
  out.intercept = valid(intercept);
  return out;
}

QuadFit fit_quadratic(const std::vector<FitPoint>& points, std::int64_t min_distinct,
                      std::int64_t min_weight) {
  QuadFit out;
  out.distinct_x = distinct_x_of(points);
  for (const FitPoint& point : points) {
    if (point.weight > 0) ++out.points;
  }
  if (out.distinct_x < min_distinct || total_weight_of(points) < min_weight) {
    return out;
  }
  // Normal equations for y = c0 + c1 x + c2 x^2, solved by Cramer's rule on the
  // 3x3 weighted moment matrix. Three coefficients is small enough that an
  // explicit determinant is clearer — and more auditable — than a factorization.
  double m[3][3] = {{0, 0, 0}, {0, 0, 0}, {0, 0, 0}};
  double rhs[3] = {0, 0, 0};
  for (const FitPoint& point : points) {
    if (point.weight <= 0) continue;
    const double weight = static_cast<double>(point.weight);
    const double x1 = point.x;
    const double x2 = x1 * x1;
    const double x3 = x2 * x1;
    const double x4 = x2 * x2;
    m[0][0] += weight;
    m[0][1] += weight * x1;
    m[0][2] += weight * x2;
    m[1][1] += weight * x2;
    m[1][2] += weight * x3;
    m[2][2] += weight * x4;
    rhs[0] += weight * point.y;
    rhs[1] += weight * x1 * point.y;
    rhs[2] += weight * x2 * point.y;
  }
  m[1][0] = m[0][1];
  m[2][0] = m[0][2];
  m[2][1] = m[1][2];
  const auto det3 = [](const double a[3][3]) {
    return a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) -
           a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0]) +
           a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]);
  };
  const double determinant = det3(m);
  if (!std::isfinite(determinant) || determinant == 0.0) {
    out.curvature = absent(Validity::NONFINITE);
    return out;
  }
  double replaced[3][3];
  for (std::size_t row = 0; row < 3; ++row) {
    for (std::size_t column = 0; column < 3; ++column) {
      replaced[row][column] = m[row][column];
    }
  }
  for (std::size_t row = 0; row < 3; ++row) {
    replaced[row][2] = rhs[row];
  }
  const double c2 = det3(replaced) / determinant;
  out.curvature = valid(2.0 * c2);
  return out;
}

Typed<double> weighted_mean(const std::vector<FitPoint>& points) { return mean_stdev(points).mean; }
Typed<double> weighted_stdev(const std::vector<FitPoint>& points) {
  return mean_stdev(points).stdev;
}

// ---------------------------------------------------------------------------
// The surface series.
// ---------------------------------------------------------------------------

double SurfaceSeries::proxy_vol_mid(std::int64_t second, std::size_t plane) const noexcept {
  if (second < 0 || second >= seconds || plane >= kPlanes) {
    return kNan;
  }
  const std::size_t at = static_cast<std::size_t>(second) * kPlanes + plane;
  return at < pv_mid.size() ? pv_mid[at] : kNan;
}

const char* vol_state_name(VolState state) noexcept {
  switch (state) {
    case VolState::FLAT:
      return "FLAT";
    case VolState::SPIKING:
      return "SPIKING";
    case VolState::BLEEDING:
      return "BLEEDING";
    case VolState::ABSENT:
    default:
      return "ABSENT";
  }
}

// ---------------------------------------------------------------------------
// The session builder.
// ---------------------------------------------------------------------------

TradedIvSession::TradedIvSession(std::int64_t ordinal, std::string day, std::string tape,
                                 std::int64_t open_ms_b, std::int64_t session_epoch_day,
                                 TradedIvOptions options)
    : ordinal_(ordinal),
      day_(std::move(day)),
      tape_(std::move(tape)),
      open_ms_b_(open_ms_b),
      session_epoch_day_(session_epoch_day),
      options_(options) {
  for (std::size_t window = 0; window < kWindows; ++window) {
    for (std::size_t band = 0; band < kBands; ++band) {
      BandWindow& cell = band_[window * kBands + band];
      cell.window = static_cast<std::int64_t>(window);
      cell.band = band;
    }
  }
}

void TradedIvSession::observe(const qr::sources::OptionPrintRow& row) {
  using qr::sources::Right;
  namespace slots = qr::sources;
  ++census_.rows_seen;

  static constexpr std::array<std::size_t, 8> kRequired{
      slots::kPrintSlotExpiration,      slots::kPrintSlotStrike,
      slots::kPrintSlotRight,           slots::kPrintSlotSize,
      slots::kPrintSlotPrice,           slots::kPrintSlotImpliedVol,
      slots::kPrintSlotUnderlyingPrice, slots::kPrintSlotCondition};
  for (const std::size_t slot : kRequired) {
    if (row.is_null(slot)) {
      ++census_.rejected_null_cell;
      return;
    }
  }
  if (row.right != Right::Call && row.right != Right::Put) {
    ++census_.rejected_right;
    return;
  }
  if (!row.is_single_leg()) {
    ++census_.rejected_multi_leg;
    return;
  }
  // B3's BOTH-ATTACHMENTS law. `quote_ts` and the print instant are both
  // frame-B milliseconds of this session, so the comparison is exact and needs
  // no clock; `underlying_ts` is compared, never parsed (WP4's rule).
  const bool quote_prior = !row.is_null(slots::kPrintSlotQuoteTimestamp) &&
                           row.quote_ts_ms_b < row.ts_ms_b;
  const std::string_view stamp = row.underlying_ts_text.view();
  const bool underlying_on_day = !row.is_null(slots::kPrintSlotUnderlyingTimestamp) &&
                                 stamp.size() >= day_.size() &&
                                 stamp.substr(0, day_.size()) == day_;
  if (!quote_prior || !underlying_on_day) {
    ++census_.rejected_attachment;
    return;
  }
  if (!std::isfinite(row.implied_vol) || row.implied_vol <= 0.0) {
    ++census_.rejected_iv;
    return;
  }
  if (row.size <= 0) {
    ++census_.rejected_size;
    return;
  }
  if (!std::isfinite(row.underlying_price) || row.underlying_price <= 0.0) {
    ++census_.rejected_spot;
    return;
  }
  const auto spot_u6 = static_cast<std::int64_t>(std::llround(row.underlying_price * 1e6));
  if (spot_u6 <= 0) {
    ++census_.rejected_spot;
    return;
  }
  const auto x = qr::w21::moneyness_log_bps(row.strike_u6, spot_u6);
  if (!x.has_value()) {
    ++census_.rejected_moneyness;
    return;
  }
  const std::int64_t elapsed_ms = row.ts_ms_b - open_ms_b_;
  if (elapsed_ms < 0) {
    ++census_.rejected_window;
    return;
  }
  const std::int64_t second = elapsed_ms / 1000;
  if (second >= kWindowSeconds * static_cast<std::int64_t>(kWindows)) {
    ++census_.rejected_window;
    return;
  }
  const auto window = static_cast<std::size_t>(second / kWindowSeconds);
  const std::size_t band = moneyness_band(x.value());
  const auto right = static_cast<std::uint8_t>(row.right);
  const std::int64_t dte_days =
      static_cast<std::int64_t>(row.expiration_day) - session_epoch_day_;

  ++census_.admitted;
  expirations_.insert(row.expiration_day);
  contracts_.insert(std::make_tuple(row.expiration_day, row.strike_u6, right));

  // The INDEPENDENT moneyness cross-check: the emitted 1s grid's own spot. It
  // never replaces the attached one — it only reports how often the two would
  // have binned the print differently.
  if (options_.grid_mid_u6 != nullptr &&
      static_cast<std::size_t>(second) < options_.grid_mid_u6->size()) {
    const std::int64_t grid_spot = (*options_.grid_mid_u6)[static_cast<std::size_t>(second)];
    if (grid_spot > 0) {
      const auto grid_x = qr::w21::moneyness_log_bps(row.strike_u6, grid_spot);
      if (grid_x.has_value()) {
        ++census_.grid_compared;
        if (moneyness_band(grid_x.value()) != band) {
          ++census_.grid_band_disagreements;
        }
      }
    }
  }

  // D2: the contract's own previous print, age-gated.
  const ContractKey contract{row.expiration_day, row.strike_u6, right};
  const auto found = last_print_.find(contract);
  if (found != last_print_.end()) {
    const std::int64_t gap_ms = row.ts_ms_b - found->second.ts_ms_b;
    if (gap_ms > 0 && gap_ms <= kIvVelocityMaxGapMs) {
      const double gap_seconds = static_cast<double>(gap_ms) / 1000.0;
      const double velocity = (row.implied_vol - found->second.iv) / gap_seconds;
      VelocityAccumulator& accumulator = velocity_[window * kBands + band];
      const double weight = static_cast<double>(row.size);
      accumulator.weighted_signed += weight * velocity;
      accumulator.weighted_absolute += weight * std::abs(velocity);
      accumulator.weighted_gap_seconds += weight * gap_seconds;
      accumulator.weight += row.size;
      ++accumulator.pairs;
    }
  }
  last_print_[contract] = LastPrint{row.ts_ms_b, row.implied_vol};

  // D5: the quote-certified sign. UNDECIDABLE is a state, not a zero: a print
  // inside the spread carries no direction this program is willing to assert.
  BandWindow& cell = band_[window * kBands + band];
  const bool quote_usable = !row.is_null(slots::kPrintSlotBid) &&
                            !row.is_null(slots::kPrintSlotAsk) && row.bid_u6 > 0 &&
                            row.ask_u6 > 0 && row.bid_u6 <= row.ask_u6;
  int direction = 0;
  if (quote_usable) {
    if (row.price_u6 >= row.ask_u6) {
      direction = 1;
    } else if (row.price_u6 <= row.bid_u6) {
      direction = -1;
    }
  }
  if (direction != 0) {
    cell.signed_size += direction * row.size;
    cell.decided_size += row.size;
    if (dte_days == 0) {
      cell.signed_size_0dte += direction * row.size;
    }
  } else {
    cell.undecidable_size += row.size;
  }

  double surface_pv = kNan;
  if (options_.surface != nullptr && dte_days >= 0 &&
      dte_days < static_cast<std::int64_t>(SurfaceSeries::kPlanes)) {
    surface_pv = options_.surface->proxy_vol_mid(second, static_cast<std::size_t>(dte_days));
  }

  Point point;
  point.second = second;
  point.weight = row.size;
  point.iv = row.implied_vol;
  point.surface_pv = surface_pv;
  point.x_bps = static_cast<std::int32_t>(x.value());
  point.dte_days = static_cast<std::int32_t>(dte_days);
  point.right = right;
  cells_[CellKey{static_cast<std::int64_t>(window), row.expiration_day}].push_back(point);
}

TradedIvTables TradedIvSession::finish() {
  TradedIvTables out;
  out.ordinal = ordinal_;
  out.day = day_;
  out.tape = tape_;
  out.census = census_;
  out.expiries = static_cast<std::int64_t>(expirations_.size());
  out.contracts = static_cast<std::int64_t>(contracts_.size());

  // PASS 1 — every cell's own fits. Ordered by (window, expiry), which is the
  // map's key order, so the emission order is the science order.
  out.cells.reserve(cells_.size());
  for (const auto& [key, points] : cells_) {
    SkewCell cell;
    cell.window = key.window;
    cell.expiration_day = key.expiration_day;
    cell.prints = static_cast<std::int64_t>(points.size());
    cell.dte_days = points.empty() ? 0 : points.front().dte_days;

    std::vector<FitPoint> put_wing;
    std::vector<FitPoint> call_wing;
    std::vector<FitPoint> otm;
    std::array<std::vector<FitPoint>, kBands * kRights> by_band;
    for (const Point& point : points) {
      cell.weight += point.weight;
      const FitPoint fit{static_cast<double>(point.x_bps) / 10000.0, point.iv, point.weight,
                         point.x_bps};
      by_band[band_right_slot(moneyness_band(point.x_bps), point.right)].push_back(fit);
      const bool is_put = point.right == static_cast<std::uint8_t>(qr::sources::Right::Put);
      if (is_put && point.x_bps <= 0) {
        put_wing.push_back(fit);
        otm.push_back(fit);
      } else if (!is_put && point.x_bps >= 0) {
        call_wing.push_back(fit);
        otm.push_back(fit);
      }
    }

    cell.put_wing = fit_line(put_wing, kMinWingStrikes, kMinCellWeight);
    cell.call_wing = fit_line(call_wing, kMinWingStrikes, kMinCellWeight);
    cell.smile = fit_quadratic(otm, kMinCurvatureStrikes, kMinCellWeight);
    cell.curvature = cell.smile.curvature;
    cell.cross_strike_stdev = weighted_stdev(otm);

    const Typed<double> put_at_zero = cell.put_wing.at(0.0);
    const Typed<double> call_at_zero = cell.call_wing.at(0.0);
    if (put_at_zero.v == Validity::VALID && call_at_zero.v == Validity::VALID) {
      cell.atm_iv = valid(0.5 * (put_at_zero.value + call_at_zero.value));
      cell.atm_iv_source = "WINGS";
    } else {
      // The ATM band read directly: both rights of band 4 (|x| < 25bp).
      std::vector<FitPoint> atm_band;
      const std::size_t atm = kBands / 2;
      for (std::size_t right = 0; right < kRights; ++right) {
        const std::vector<FitPoint>& source = by_band[band_right_slot(atm, static_cast<std::uint8_t>(right))];
        atm_band.insert(atm_band.end(), source.begin(), source.end());
      }
      if (total_weight_of(atm_band) >= kMinCellWeight) {
        cell.atm_iv = weighted_mean(atm_band);
        cell.atm_iv_source = "ATM_BAND";
      }
    }

    const Typed<double> put_anchor = cell.put_wing.at(-kWingAnchorLn);
    const Typed<double> call_anchor = cell.call_wing.at(kWingAnchorLn);
    if (put_anchor.v == Validity::VALID && call_anchor.v == Validity::VALID) {
      cell.risk_reversal = valid(put_anchor.value - call_anchor.value);
      cell.skew_slope = valid(cell.risk_reversal.value / (2.0 * kWingAnchorLn));
    }

    for (std::size_t slot = 0; slot < by_band.size(); ++slot) {
      cell.band_iv[slot] = weighted_mean(by_band[slot]);
      cell.band_weight[slot] = total_weight_of(by_band[slot]);
    }

    // D3, second time scale: the cross-strike dispersion INSIDE one second,
    // averaged over the cell's seconds by group weight. A second holding one
    // strike carries no dispersion and is not counted.
    {
      std::map<std::int64_t, std::vector<FitPoint>> by_second;
      for (const Point& point : points) {
        by_second[point.second].push_back(
            FitPoint{static_cast<double>(point.x_bps) / 10000.0, point.iv, point.weight,
                     point.x_bps});
      }
      double weighted = 0.0;
      double weight = 0.0;
      for (const auto& [second, group] : by_second) {
        (void)second;
        if (distinct_x_of(group) < 2) continue;
        const Typed<double> dispersion = weighted_stdev(group);
        if (dispersion.v != Validity::VALID) continue;
        const auto group_weight = static_cast<double>(total_weight_of(group));
        weighted += group_weight * dispersion.value;
        weight += group_weight;
        ++cell.same_second_groups;
      }
      cell.same_second_stdev = weight > 0.0 ? valid(weighted / weight) : absent(Validity::MISSING);
    }
    out.cells.push_back(std::move(cell));
  }

  // PASS 2 — innovations and D1 richness, both of which need the PRIOR window's
  // cell of the SAME expiry. Cells are already in (window, expiry) order, so
  // one forward walk with a per-expiry cursor sees the prior cell before it
  // needs it, and nothing looks ahead.
  std::map<std::int32_t, std::size_t> previous;  // expiry -> index into out.cells
  {
    std::size_t index = 0;
    for (const auto& [key, points] : cells_) {
      SkewCell& cell = out.cells[index];
      const auto found = previous.find(key.expiration_day);
      const SkewCell* prior =
          found == previous.end() ? nullptr : &out.cells[found->second];
      // Only the IMMEDIATELY preceding window is an innovation; a gap of
      // windows is a different quantity and is left absent.
      const bool adjacent = prior != nullptr && prior->window == cell.window - 1;
      if (adjacent) {
        cell.d_atm_iv = difference(cell.atm_iv, prior->atm_iv);
        cell.d_risk_reversal = difference(cell.risk_reversal, prior->risk_reversal);
        cell.d_skew_slope = difference(cell.skew_slope, prior->skew_slope);
        cell.d_curvature = difference(cell.curvature, prior->curvature);
        for (std::size_t slot = 0; slot < cell.band_iv.size(); ++slot) {
          cell.d_band_iv[slot] = difference(cell.band_iv[slot], prior->band_iv[slot]);
        }
      }

      // D1: richness against the concurrent PROXY_VOL. The skew-adjusted form
      // translates the ATM proxy level to the print's own moneyness with the
      // PRIOR window's wing fit — strictly prior, and model-free.
      double plain_weighted = 0.0;
      double plain_weight = 0.0;
      double adjusted_weighted = 0.0;
      double adjusted_weight = 0.0;
      for (const Point& point : points) {
        if (!std::isfinite(point.surface_pv) || point.surface_pv <= 0.0) continue;
        ++cell.richness_points;
        if (std::abs(point.x_bps) <= 50) {
          const double weight = static_cast<double>(point.weight);
          plain_weighted += weight * (point.iv - point.surface_pv);
          plain_weight += weight;
        }
        if (prior == nullptr) continue;
        const bool is_put = point.right == static_cast<std::uint8_t>(qr::sources::Right::Put);
        const LineFit& wing = is_put ? prior->put_wing : prior->call_wing;
        const double x = static_cast<double>(point.x_bps) / 10000.0;
        const Typed<double> at_x = wing.at(x);
        const Typed<double> at_zero = wing.at(0.0);
        if (at_x.v != Validity::VALID || at_zero.v != Validity::VALID) continue;
        const double weight = static_cast<double>(point.weight);
        const double reference = point.surface_pv + (at_x.value - at_zero.value);
        adjusted_weighted += weight * (point.iv - reference);
        adjusted_weight += weight;
      }
      cell.richness_plain =
          plain_weight > 0.0 ? valid(plain_weighted / plain_weight) : absent(Validity::MISSING);
      cell.richness_skew_adjusted = adjusted_weight > 0.0
                                        ? valid(adjusted_weighted / adjusted_weight)
                                        : absent(Validity::MISSING);
      if (adjacent) {
        cell.d_richness_plain = difference(cell.richness_plain, prior->richness_plain);
      }
      previous[key.expiration_day] = index;
      ++index;
    }
  }

  // B2 — the term structure, per window.
  for (std::size_t window = 0; window < kWindows; ++window) {
    TermWindow& term = out.term[window];
    term.window = static_cast<std::int64_t>(window);
    std::vector<FitPoint> curve;
    const SkewCell* near = nullptr;
    const SkewCell* far = nullptr;
    const SkewCell* longest = nullptr;
    for (const SkewCell& cell : out.cells) {
      if (cell.window != static_cast<std::int64_t>(window)) continue;
      if (cell.atm_iv.v != Validity::VALID) continue;
      ++term.expiries;
      curve.push_back(FitPoint{std::log1p(static_cast<double>(std::max(cell.dte_days, 0))),
                               cell.atm_iv.value, cell.weight, cell.dte_days});
      if (near == nullptr || cell.dte_days < near->dte_days) near = &cell;
      if (longest == nullptr || cell.dte_days > longest->dte_days) longest = &cell;
      if (cell.dte_days >= kTermFarMinDteDays && (far == nullptr || cell.dte_days < far->dte_days)) {
        far = &cell;
      }
    }
    if (far == nullptr) {
      far = longest;
      term.far_is_fallback = far != nullptr;
    }
    if (near != nullptr) {
      term.near_dte = near->dte_days;
      term.near_iv = near->atm_iv;
    }
    if (far != nullptr) {
      term.far_dte = far->dte_days;
      term.far_iv = far->atm_iv;
    }
    if (near != nullptr && far != nullptr && near != far && far->atm_iv.value > 0.0) {
      term.near_far_ratio = valid(near->atm_iv.value / far->atm_iv.value);
    }
    const LineFit slope = fit_line(curve, kMinTermExpiries, kMinCellWeight);
    term.term_slope = slope.slope;
    if (window > 0) {
      term.d_near_far_ratio = difference(term.near_far_ratio, out.term[window - 1].near_far_ratio);
      term.d_term_slope = difference(term.term_slope, out.term[window - 1].term_slope);
    }
  }

  // D2/D5 — the band aggregates.
  out.bands.reserve(kWindows * kBands);
  for (std::size_t window = 0; window < kWindows; ++window) {
    for (std::size_t band = 0; band < kBands; ++band) {
      BandWindow cell = band_[window * kBands + band];
      const VelocityAccumulator& accumulator = velocity_[window * kBands + band];
      if (accumulator.weight > 0) {
        const double weight = static_cast<double>(accumulator.weight);
        cell.iv_velocity_signed = valid(accumulator.weighted_signed / weight);
        cell.iv_velocity_absolute = valid(accumulator.weighted_absolute / weight);
        cell.iv_velocity_mean_gap_seconds = valid(accumulator.weighted_gap_seconds / weight);
      }
      cell.iv_velocity_pairs = accumulator.pairs;
      out.bands.push_back(cell);
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// D7 / D8 / D9 — the surface's own dynamics.
// ---------------------------------------------------------------------------

SurfaceDynamics surface_dynamics(const SurfaceSeries& series, std::size_t plane) {
  SurfaceDynamics out;
  for (std::size_t window = 0; window < kWindows; ++window) {
    out.window[window].window = static_cast<std::int64_t>(window);
  }
  if (series.empty() || plane >= SurfaceSeries::kPlanes) {
    return out;
  }
  const auto pv_at = [&](const std::vector<double>& side, std::int64_t second) -> double {
    if (second < 0 || second >= series.seconds) return kNan;
    const std::size_t at = static_cast<std::size_t>(second) * SurfaceSeries::kPlanes + plane;
    return at < side.size() ? side[at] : kNan;
  };
  const auto log_innovation = [&](const std::vector<double>& side, std::int64_t second) -> double {
    const double now = pv_at(side, second);
    const double before = pv_at(side, second - 1);
    if (!std::isfinite(now) || !std::isfinite(before) || now <= 0.0 || before <= 0.0) {
      return kNan;
    }
    return std::log(now / before);
  };
  const auto spot_return = [&](std::int64_t second) -> double {
    if (second <= 0 || second >= series.seconds) return kNan;
    const std::int64_t now = series.spot_u6[static_cast<std::size_t>(second)];
    const std::int64_t before = series.spot_u6[static_cast<std::size_t>(second - 1)];
    if (now <= 0 || before <= 0) return kNan;
    return std::log(static_cast<double>(now) / static_cast<double>(before));
  };

  std::array<double, kWindows> level{};
  std::array<bool, kWindows> level_present{};
  for (std::size_t window = 0; window < kWindows; ++window) {
    SurfaceWindow& out_window = out.window[window];
    const std::int64_t from = static_cast<std::int64_t>(window) * kWindowSeconds;
    const std::int64_t to = from + kWindowSeconds;

    std::vector<double> dv_mid;
    std::vector<double> dv_bid;
    std::vector<double> dv_ask;
    std::vector<double> returns;
    std::vector<double> paired_dv;
    std::vector<double> paired_abs_return;
    std::vector<double> levels;
    // The 1s series of this window, in second order. `returns` and `dv_mid`
    // are DENSE (NaN where absent) so that A3's t/t+1 pairing stays on real
    // adjacent seconds instead of silently pairing across a gap.
    for (std::int64_t second = from; second < to && second < series.seconds; ++second) {
      const double level_value = pv_at(series.pv_mid, second);
      if (std::isfinite(level_value) && level_value > 0.0) {
        levels.push_back(level_value);
        ++out_window.seconds_valid;
      }
      const double dv = log_innovation(series.pv_mid, second);
      const double ret = spot_return(second);
      dv_mid.push_back(dv);
      dv_bid.push_back(log_innovation(series.pv_bid, second));
      dv_ask.push_back(log_innovation(series.pv_ask, second));
      returns.push_back(ret);
      if (std::isfinite(dv) && std::isfinite(ret)) {
        paired_dv.push_back(dv);
        paired_abs_return.push_back(std::abs(ret));
      }
    }

    const auto realized_variance = [](const std::vector<double>& innovations) -> Typed<double> {
      double sum = 0.0;
      std::int64_t count = 0;
      for (const double value : innovations) {
        if (!std::isfinite(value)) continue;
        sum += value * value;
        ++count;
      }
      if (count < kMinFdPairs) return absent(Validity::MISSING);
      return valid(sum / static_cast<double>(count));
    };
    out_window.vol_of_vol_mid = realized_variance(dv_mid);
    out_window.vol_of_vol_bid = realized_variance(dv_bid);
    out_window.vol_of_vol_ask = realized_variance(dv_ask);
    if (!levels.empty()) {
      double total = 0.0;
      for (const double value : levels) total += value;
      out_window.pv_level = valid(total / static_cast<double>(levels.size()));
      level[window] = out_window.pv_level.value;
      level_present[window] = true;
    }

    // D8(a): the RESPONSE. OLS of the PROXY_VOL innovation on |spot return|,
    // with an intercept — chi is the slope, i.e. how much the surface moves per
    // unit of being pushed.
    out_window.fd_pairs = static_cast<std::int64_t>(paired_dv.size());
    if (out_window.fd_pairs >= kMinFdPairs) {
      const auto n = static_cast<double>(paired_dv.size());
      double sx = 0.0;
      double sy = 0.0;
      double sxx = 0.0;
      double sxy = 0.0;
      for (std::size_t index = 0; index < paired_dv.size(); ++index) {
        sx += paired_abs_return[index];
        sy += paired_dv[index];
        sxx += paired_abs_return[index] * paired_abs_return[index];
        sxy += paired_abs_return[index] * paired_dv[index];
      }
      const double denominator = n * sxx - sx * sx;
      if (std::isfinite(denominator) && denominator != 0.0) {
        out_window.fd_chi = valid((n * sxy - sx * sy) / denominator);
      } else {
        out_window.fd_chi = absent(Validity::NONFINITE);
      }
      // D8(b): the FLUCTUATION. Dispersion of the innovations in the QUIET half
      // of the window — the seconds whose |return| is at or below the window's
      // own median, i.e. the surface moving while nothing pushed it.
      const double cut = median_of(paired_abs_return);
      std::vector<double> quiet;
      for (std::size_t index = 0; index < paired_dv.size(); ++index) {
        if (paired_abs_return[index] <= cut) quiet.push_back(paired_dv[index]);
      }
      out_window.fd_quiet_points = static_cast<std::int64_t>(quiet.size());
      if (out_window.fd_quiet_points >= kMinFdQuietPoints) {
        double mean = 0.0;
        for (const double value : quiet) mean += value;
        mean /= static_cast<double>(quiet.size());
        double variance = 0.0;
        for (const double value : quiet) variance += (value - mean) * (value - mean);
        const double sigma = std::sqrt(variance / static_cast<double>(quiet.size()));
        out_window.fd_sigma_vv = valid(sigma);
        if (out_window.fd_chi.v == Validity::VALID && sigma > 0.0) {
          out_window.fd_ratio = valid(out_window.fd_chi.value / sigma);
        } else if (sigma <= 0.0) {
          out_window.fd_ratio = absent(Validity::NONPOSITIVE);
        }
      }
    }

    // D8(c): the window-to-window INNOVATION of the ratio, on the same law
    // every other `d_` channel in this module obeys — absent in window 0,
    // absent whenever either side is absent, and never a zero standing in for
    // "no change". (The field was declared and emitted from the start but was
    // never assigned; every census row therefore read MISSING. Fixed here with
    // a red-first fixture, `SurfaceDynamics.FdRatioInnovationIsTheWindowToWindowChange`.)
    if (window > 0 && out_window.fd_ratio.v == Validity::VALID &&
        out.window[window - 1].fd_ratio.v == Validity::VALID) {
      out_window.d_fd_ratio =
          valid(out_window.fd_ratio.value - out.window[window - 1].fd_ratio.value);
    }

    // D9: A3 = (E[r_t r_{t+1}^2] - E[r_t^2 r_{t+1}]) / sigma^3, over ADJACENT
    // seconds only. It is exactly zero for any time-reversible series and
    // changes sign under time reversal, which is the whole point.
    const auto third_order = [](const std::vector<double>& series_values,
                                std::int64_t& pairs_out) -> Typed<double> {
      double forward = 0.0;
      double backward = 0.0;
      std::int64_t pairs = 0;
      double mean = 0.0;
      std::int64_t count = 0;
      for (const double value : series_values) {
        if (!std::isfinite(value)) continue;
        mean += value;
        ++count;
      }
      if (count == 0) {
        pairs_out = 0;
        return absent(Validity::MISSING);
      }
      mean /= static_cast<double>(count);
      double variance = 0.0;
      for (const double value : series_values) {
        if (!std::isfinite(value)) continue;
        variance += (value - mean) * (value - mean);
      }
      const double sigma = std::sqrt(variance / static_cast<double>(count));
      for (std::size_t index = 0; index + 1 < series_values.size(); ++index) {
        const double now = series_values[index];
        const double next = series_values[index + 1];
        if (!std::isfinite(now) || !std::isfinite(next)) continue;
        const double a = now - mean;
        const double b = next - mean;
        forward += a * b * b;
        backward += a * a * b;
        ++pairs;
      }
      pairs_out = pairs;
      if (pairs < kMinA3Pairs) return absent(Validity::MISSING);
      if (!(sigma > 0.0)) return absent(Validity::NONPOSITIVE);
      const double numerator = (forward - backward) / static_cast<double>(pairs);
      return valid(numerator / (sigma * sigma * sigma));
    };
    std::int64_t return_pairs = 0;
    std::int64_t proxy_pairs = 0;
    out_window.a3_return = third_order(returns, return_pairs);
    out_window.a3_proxy_vol = third_order(dv_mid, proxy_pairs);
    out_window.a3_pairs = std::min(return_pairs, proxy_pairs);
    if (out_window.a3_return.v == Validity::VALID &&
        out_window.a3_proxy_vol.v == Validity::VALID) {
      out_window.a3_joint_state = 3 * (sign_of(out_window.a3_return.value) + 1) +
                                  (sign_of(out_window.a3_proxy_vol.value) + 1);
    }
  }

  // D7's state, last: it needs the whole session's change distribution. The
  // threshold is the SESSION's own 80th percentile of |relative change|, and it
  // is emitted beside the state precisely so a deployable feature can replace
  // it with a TRAIN-frozen era quantile.
  std::vector<double> changes;
  for (std::size_t window = 1; window < kWindows; ++window) {
    if (!level_present[window] || !level_present[window - 1] || level[window - 1] <= 0.0) continue;
    const double change = (level[window] - level[window - 1]) / level[window - 1];
    out.window[window].pv_relative_change = valid(change);
    changes.push_back(std::abs(change));
  }
  if (changes.empty()) {
    return out;
  }
  const double threshold =
      percentile_of(changes, kVolStateQuantileNumerator, kVolStateQuantileDenominator);
  out.state_threshold = valid(threshold);
  for (std::size_t window = 0; window < kWindows; ++window) {
    SurfaceWindow& one = out.window[window];
    if (one.pv_relative_change.v != Validity::VALID) {
      one.state = VolState::ABSENT;
      continue;
    }
    if (one.pv_relative_change.value >= threshold) {
      one.state = VolState::SPIKING;
    } else if (one.pv_relative_change.value <= -threshold) {
      one.state = VolState::BLEEDING;
    } else {
      one.state = VolState::FLAT;
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// D6 — the cross-tape spread.
// ---------------------------------------------------------------------------

CrossTapeSpread cross_tape_spread(const TradedIvTables& left, const TradedIvTables& right) {
  CrossTapeSpread out;
  for (std::size_t window = 0; window < kWindows; ++window) {
    out.spread[window] = difference(left.term[window].near_iv, right.term[window].near_iv);
    if (left.term[window].near_iv.v == Validity::VALID &&
        right.term[window].near_iv.v == Validity::VALID &&
        right.term[window].near_iv.value > 0.0) {
      out.ratio[window] =
          valid(left.term[window].near_iv.value / right.term[window].near_iv.value);
    }
    if (window > 0) {
      out.d_spread[window] = difference(out.spread[window], out.spread[window - 1]);
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Emission.
// ---------------------------------------------------------------------------

void emit(Report& report, const TradedIvTables& tables) {
  const std::string session = "s" + std::to_string(tables.ordinal) + "/" + tables.tape;
  report.text("session", session, "day", tables.day);
  report.text("session", session, "tape", tables.tape);
  report.metric("session", session, "expiries", tables.expiries);
  report.metric("session", session, "contracts", tables.contracts);
  const AdmissionCensus& census = tables.census;
  report.metric("admission", session, "rows_seen", census.rows_seen);
  report.metric("admission", session, "admitted", census.admitted);
  report.metric("admission", session, "rejected_null_cell", census.rejected_null_cell);
  report.metric("admission", session, "rejected_right", census.rejected_right);
  report.metric("admission", session, "rejected_multi_leg", census.rejected_multi_leg);
  report.metric("admission", session, "rejected_attachment", census.rejected_attachment);
  report.metric("admission", session, "rejected_iv", census.rejected_iv);
  report.metric("admission", session, "rejected_size", census.rejected_size);
  report.metric("admission", session, "rejected_spot", census.rejected_spot);
  report.metric("admission", session, "rejected_moneyness", census.rejected_moneyness);
  report.metric("admission", session, "rejected_window", census.rejected_window);
  report.metric("admission", session, "grid_compared", census.grid_compared);
  report.metric("admission", session, "grid_band_disagreements", census.grid_band_disagreements);

  for (const SkewCell& cell : tables.cells) {
    const std::string key = session + "/w" + std::to_string(cell.window) + "/e" +
                            std::to_string(cell.expiration_day);
    report.metric("skew", key, "dte_days", cell.dte_days);
    report.metric("skew", key, "prints", cell.prints);
    report.metric("skew", key, "weight", cell.weight);
    report.metric("skew", key, "put_wing_strikes", cell.put_wing.distinct_x);
    report.metric("skew", key, "call_wing_strikes", cell.call_wing.distinct_x);
    report.typed("skew", key, "put_wing_slope", cell.put_wing.slope);
    report.typed("skew", key, "call_wing_slope", cell.call_wing.slope);
    report.text("skew", key, "atm_iv_source", cell.atm_iv_source);
    report.typed("skew", key, "atm_iv", cell.atm_iv);
    report.typed("skew", key, "risk_reversal", cell.risk_reversal);
    report.typed("skew", key, "skew_slope", cell.skew_slope);
    report.typed("skew", key, "curvature", cell.curvature);
    report.typed("skew", key, "cross_strike_stdev", cell.cross_strike_stdev);
    report.typed("skew", key, "same_second_stdev", cell.same_second_stdev);
    report.metric("skew", key, "same_second_groups", cell.same_second_groups);
    report.typed("skew", key, "d_atm_iv", cell.d_atm_iv);
    report.typed("skew", key, "d_risk_reversal", cell.d_risk_reversal);
    report.typed("skew", key, "d_skew_slope", cell.d_skew_slope);
    report.typed("skew", key, "d_curvature", cell.d_curvature);
    report.metric("skew", key, "richness_points", cell.richness_points);
    report.typed("skew", key, "richness_plain", cell.richness_plain);
    report.typed("skew", key, "richness_skew_adjusted", cell.richness_skew_adjusted);
    report.typed("skew", key, "d_richness_plain", cell.d_richness_plain);
    for (std::size_t band = 0; band < kBands; ++band) {
      for (std::size_t right = 0; right < kRights; ++right) {
        const std::size_t slot = band_right_slot(band, static_cast<std::uint8_t>(right));
        if (cell.band_weight[slot] <= 0) continue;  // an empty cell says nothing
        const std::string name =
            band_label(band) + "/" + (right == 0 ? "C" : "P");
        report.metric("smile", key + "/" + name, "weight", cell.band_weight[slot]);
        report.typed("smile", key + "/" + name, "iv", cell.band_iv[slot]);
        report.typed("smile", key + "/" + name, "d_iv", cell.d_band_iv[slot]);
      }
    }
  }

  for (const TermWindow& term : tables.term) {
    const std::string key = session + "/w" + std::to_string(term.window);
    report.metric("term", key, "expiries", term.expiries);
    report.metric("term", key, "near_dte", term.near_dte);
    report.metric("term", key, "far_dte", term.far_dte);
    report.metric("term", key, "far_is_fallback", term.far_is_fallback ? 1 : 0);
    report.typed("term", key, "near_iv", term.near_iv);
    report.typed("term", key, "far_iv", term.far_iv);
    report.typed("term", key, "near_far_ratio", term.near_far_ratio);
    report.typed("term", key, "term_slope", term.term_slope);
    report.typed("term", key, "d_near_far_ratio", term.d_near_far_ratio);
    report.typed("term", key, "d_term_slope", term.d_term_slope);
  }

  for (const BandWindow& band : tables.bands) {
    if (band.iv_velocity_pairs == 0 && band.decided_size == 0 && band.undecidable_size == 0) {
      continue;  // an untouched (window, band) cell carries no information
    }
    const std::string key =
        session + "/w" + std::to_string(band.window) + "/" + band_label(band.band);
    report.metric("band", key, "iv_velocity_pairs", band.iv_velocity_pairs);
    report.typed("band", key, "iv_velocity_signed", band.iv_velocity_signed);
    report.typed("band", key, "iv_velocity_absolute", band.iv_velocity_absolute);
    report.typed("band", key, "iv_velocity_mean_gap_seconds", band.iv_velocity_mean_gap_seconds);
    report.metric("band", key, "signed_size", band.signed_size);
    report.metric("band", key, "signed_size_0dte", band.signed_size_0dte);
    report.metric("band", key, "decided_size", band.decided_size);
    report.metric("band", key, "undecidable_size", band.undecidable_size);
  }
}

void emit(Report& report, const std::string& session_key, const SurfaceDynamics& dynamics) {
  report.typed("surface", session_key, "state_threshold", dynamics.state_threshold);
  for (const SurfaceWindow& window : dynamics.window) {
    const std::string key = session_key + "/w" + std::to_string(window.window);
    report.metric("surface", key, "seconds_valid", window.seconds_valid);
    report.typed("surface", key, "vol_of_vol_mid", window.vol_of_vol_mid);
    report.typed("surface", key, "vol_of_vol_bid", window.vol_of_vol_bid);
    report.typed("surface", key, "vol_of_vol_ask", window.vol_of_vol_ask);
    report.typed("surface", key, "pv_level", window.pv_level);
    report.typed("surface", key, "pv_relative_change", window.pv_relative_change);
    report.text("surface", key, "vol_state", vol_state_name(window.state));
    report.metric("surface", key, "fd_pairs", window.fd_pairs);
    report.metric("surface", key, "fd_quiet_points", window.fd_quiet_points);
    report.typed("surface", key, "fd_chi", window.fd_chi);
    report.typed("surface", key, "fd_sigma_vv", window.fd_sigma_vv);
    report.typed("surface", key, "fd_ratio", window.fd_ratio);
    report.typed("surface", key, "d_fd_ratio", window.d_fd_ratio);
    report.metric("surface", key, "a3_pairs", window.a3_pairs);
    report.typed("surface", key, "a3_return", window.a3_return);
    report.typed("surface", key, "a3_proxy_vol", window.a3_proxy_vol);
    report.metric("surface", key, "a3_joint_state", window.a3_joint_state);
  }
}

void emit(Report& report, const std::string& key, const CrossTapeSpread& spread) {
  for (std::size_t window = 0; window < kWindows; ++window) {
    const std::string row = key + "/w" + std::to_string(window);
    report.typed("cross_tape", row, "iv_spread", spread.spread[window]);
    report.typed("cross_tape", row, "iv_ratio", spread.ratio[window]);
    report.typed("cross_tape", row, "d_iv_spread", spread.d_spread[window]);
  }
}

}  // namespace qr::ivx
