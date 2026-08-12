#include "qr_ivx/column_values.hpp"

#include <algorithm>
#include <cmath>

namespace qr::ivx {
namespace {

/// The row field behind each censused slot. One switch, so a column can never
/// be censused under a neighbour's name.
double value_of(const qr::sources::OptionPrintRow& row, std::size_t slot) noexcept {
  namespace s = qr::sources;
  switch (slot) {
    case s::kPrintSlotDelta:
      return row.delta;
    case s::kPrintSlotVega:
      return row.vega;
    case s::kPrintSlotGamma:
      return row.gamma;
    case s::kPrintSlotVanna:
      return row.vanna;
    case s::kPrintSlotCharm:
      return row.charm;
    case s::kPrintSlotVomma:
      return row.vomma;
    case s::kPrintSlotVeta:
      return row.veta;
    case s::kPrintSlotVera:
      return row.vera;
    case s::kPrintSlotSpeed:
      return row.speed;
    case s::kPrintSlotZomma:
      return row.zomma;
    case s::kPrintSlotColor:
      return row.color;
    case s::kPrintSlotUltima:
      return row.ultima;
    case s::kPrintSlotDualDelta:
      return row.dual_delta;
    case s::kPrintSlotDualGamma:
      return row.dual_gamma;
    case s::kPrintSlotImpliedVol:
      return row.implied_vol;
    case s::kPrintSlotIvError:
      return row.iv_error;
    default:
      return 0.0;
  }
}

std::size_t slot_of(const std::string& name) noexcept {
  namespace s = qr::sources;
  if (name == "delta") return s::kPrintSlotDelta;
  if (name == "vega") return s::kPrintSlotVega;
  if (name == "gamma") return s::kPrintSlotGamma;
  if (name == "vanna") return s::kPrintSlotVanna;
  if (name == "charm") return s::kPrintSlotCharm;
  if (name == "vomma") return s::kPrintSlotVomma;
  if (name == "veta") return s::kPrintSlotVeta;
  if (name == "vera") return s::kPrintSlotVera;
  if (name == "speed") return s::kPrintSlotSpeed;
  if (name == "zomma") return s::kPrintSlotZomma;
  if (name == "color") return s::kPrintSlotColor;
  if (name == "ultima") return s::kPrintSlotUltima;
  if (name == "dual_delta") return s::kPrintSlotDualDelta;
  if (name == "dual_gamma") return s::kPrintSlotDualGamma;
  if (name == "implied_vol") return s::kPrintSlotImpliedVol;
  return s::kPrintSlotIvError;
}

/// The q-th quantile of a SORTED vector by the census quantile law: the
/// smallest value v with count(<= v) >= ceil(q*n).
double quantile_of(const std::vector<double>& sorted, std::int64_t numerator,
                   std::int64_t denominator) {
  if (sorted.empty()) return 0.0;
  const auto n = static_cast<std::int64_t>(sorted.size());
  const std::int64_t rank = (n * numerator + denominator - 1) / denominator;
  const std::int64_t index = std::min(std::max(rank, std::int64_t{1}), n) - 1;
  return sorted[static_cast<std::size_t>(index)];
}

}  // namespace

Cc013ValueCensus::Cc013ValueCensus() {
  for (const char* name : kValueCensusColumns) {
    names_.emplace_back(name);
  }
  names_.emplace_back(kValueCensusExtraColumn);
  for (const std::string& name : names_) {
    slots_.push_back(slot_of(name));
  }
  values_.resize(names_.size());
  nulls_.assign(names_.size(), 0);
  nonfinite_.assign(names_.size(), 0);
}

void Cc013ValueCensus::observe(const qr::sources::OptionPrintRow& row) {
  ++rows_;
  for (std::size_t index = 0; index < slots_.size(); ++index) {
    const std::size_t slot = slots_[index];
    if (row.is_null(slot)) {
      ++nulls_[index];
      continue;
    }
    const double value = value_of(row, slot);
    if (!std::isfinite(value)) {
      ++nonfinite_[index];
      continue;
    }
    values_[index].push_back(value);
  }
}

std::vector<ValueDistribution> Cc013ValueCensus::finish() const {
  std::vector<ValueDistribution> out;
  out.reserve(names_.size());
  for (std::size_t index = 0; index < names_.size(); ++index) {
    ValueDistribution one;
    one.name = names_[index];
    one.rows = rows_;
    one.nulls = nulls_[index];
    one.nonfinite = nonfinite_[index];
    one.finite = static_cast<std::int64_t>(values_[index].size());
    if (one.finite == 0) {
      out.push_back(std::move(one));
      continue;
    }
    // PASS ONE: the mean. PASS TWO: the population variance around it.
    double total = 0.0;
    for (const double value : values_[index]) total += value;
    one.mean = total / static_cast<double>(one.finite);
    double variance = 0.0;
    for (const double value : values_[index]) {
      const double residual = value - one.mean;
      variance += residual * residual;
    }
    one.stdev = std::sqrt(variance / static_cast<double>(one.finite));
    std::vector<double> sorted = values_[index];
    std::sort(sorted.begin(), sorted.end());
    one.minimum = sorted.front();
    one.maximum = sorted.back();
    one.quantile[0] = quantile_of(sorted, 1, 100);
    one.quantile[1] = quantile_of(sorted, 10, 100);
    one.quantile[2] = quantile_of(sorted, 50, 100);
    one.quantile[3] = quantile_of(sorted, 90, 100);
    one.quantile[4] = quantile_of(sorted, 99, 100);
    out.push_back(std::move(one));
  }
  return out;
}

void emit(Report& report, const std::string& key, const std::vector<ValueDistribution>& columns) {
  static constexpr std::array<const char*, 5> kQuantileNames{"p01", "p10", "p50", "p90", "p99"};
  for (const ValueDistribution& one : columns) {
    const std::string row = key + "/" + one.name;
    report.metric("value", row, "rows", one.rows);
    report.metric("value", row, "nulls", one.nulls);
    report.metric("value", row, "nonfinite", one.nonfinite);
    report.metric("value", row, "finite", one.finite);
    if (one.finite == 0) {
      report.text("value", row, "state", "NO_FINITE_VALUE");
      continue;
    }
    report.real("value", row, "min", one.minimum);
    report.real("value", row, "max", one.maximum);
    report.real("value", row, "mean", one.mean);
    report.real("value", row, "stdev", one.stdev);
    for (std::size_t index = 0; index < kQuantileNames.size(); ++index) {
      report.real("value", row, kQuantileNames[index], one.quantile[index]);
    }
  }
}

}  // namespace qr::ivx
