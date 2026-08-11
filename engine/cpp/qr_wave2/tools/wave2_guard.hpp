// qr_wave2/tools/wave2_guard.hpp — THE PRODUCTION-PATH FINGERPRINT THE WAVE-2
// DESTRUCTION FLAGS MAY NOT MOVE.
//
// SPEC: FINAL_PLAN section 6's "destructions in the SAME constructors" and the
// WP8b destruction guard it is modelled on — "destruction-flag off = production
// path byte-identical to a build WITHOUT the flag code compiled". A flag that
// defaults to false is not evidence: the branch is still compiled and still
// able to perturb a production bit through a mistake in its own arithmetic. So
// `qr_wave2_nodestruct_probe` links a SECOND build of this library with
// `-DQR_WAVE2_NO_DESTRUCTIONS`, in which `DestructionControls`' flags and every
// branch reading them do not exist at all, and prints the fingerprint below.
// The ordinary test binary computes the same fingerprint through the ordinary
// library with the flags off; equality of the two digests is the guard.
//
// THE TAPE BELOW IS DELIBERATELY DULL. The guard's object is the PATH, not the
// arithmetic — every value law already has its own hand-literal fixture — so
// this header builds one small deterministic session and one small history and
// digests every channel of both families over it.
#ifndef QR_WAVE2_TOOLS_GUARD_HPP
#define QR_WAVE2_TOOLS_GUARD_HPP

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "qr_carriers/grid_1s.hpp"
#include "qr_carriers/streams.hpp"
#include "qr_clock/session_clock.hpp"
#include "qr_registry/registry.hpp"
#include "qr_wave2/prior_state.hpp"
#include "qr_wave2/prior_structure.hpp"
#include "qr_wave2/variance_budget.hpp"

namespace qr::wave2::guard {

/// FNV-1a over every produced bit — the same digest shape the carrier probes use.
class Digest {
 public:
  void feed_u64(std::uint64_t bits) noexcept {
    for (unsigned shift = 0; shift < 64; shift += 8) {
      value_ ^= (bits >> shift) & 0xFFULL;
      value_ *= 0x100000001B3ULL;
    }
  }
  void feed_i64(std::int64_t value) noexcept { feed_u64(static_cast<std::uint64_t>(value)); }
  void feed_f64(double value) noexcept {
    std::uint64_t bits = 0;
    static_assert(sizeof(bits) == sizeof(double));
    std::memcpy(&bits, &value, sizeof(bits));
    feed_u64(bits);
  }
  [[nodiscard]] std::string hex() const {
    static constexpr char kHex[] = "0123456789abcdef";
    std::string out(16, '0');
    for (int index = 15; index >= 0; --index) {
      out[static_cast<std::size_t>(index)] =
          kHex[(value_ >> ((15 - index) * 4)) & 0xFULL];
    }
    return out;
  }

 private:
  std::uint64_t value_ = 0xCBF29CE484222325ULL;
};

/// Session 125's clock — the one authorized development session. No payload is
/// opened: only the registry row's own span is used.
inline const SessionClock& guard_clock() {
  static const SessionClock built = [] {
    auto registry = Registry::load_embedded();
    if (!registry.has_value()) {
      detail::fail_fast("wave2 guard: the embedded registry failed its digest gate");
    }
    auto date = CivilDate::parse_ymd("2022-07-05");
    if (!date.has_value()) {
      detail::fail_fast("wave2 guard: the development day is not a canonical civil date");
    }
    auto clock = SessionClock::for_day(registry.value(), date.value());
    if (!clock.has_value()) {
      detail::fail_fast("wave2 guard: the registry refused the development session");
    }
    return std::move(clock).value();
  }();
  return built;
}

/// One deterministic session: a sawtooth midpoint path and two print groups.
inline carriers::MidpointGrid guard_grid() {
  std::vector<carriers::NbboStream::EligibleMid> eligible;
  eligible.reserve(600);
  for (std::int64_t second = 0; second < 600; ++second) {
    carriers::NbboStream::EligibleMid mid;
    mid.ts_ns_a = guard_clock().session_start_a().ns() + second * carriers::kNanosPerSecond;
    mid.mid_u6 = 100'000'000 + (second % 11) * 10'000;
    mid.spread_u6 = 10'000;
    eligible.push_back(mid);
  }
  auto grid = carriers::MidpointGrid::build(guard_clock(), eligible);
  if (!grid.has_value()) {
    detail::fail_fast("wave2 guard: the grid refused the guard path");
  }
  return std::move(grid).value();
}

/// The fingerprint: both families' channels at a fixed set of endpoints, for
/// both sides, over the guard tape — with every destruction flag OFF.
inline std::string production_fingerprint() {
  Digest digest;

  PriorSessionHistory history;
  for (std::int64_t ordinal = 0; ordinal <= 20; ++ordinal) {
    SessionSummary summary;
    summary.ordinal = ordinal;
    summary.grid_present = true;
    summary.high_u6 = 101'000'000 + ordinal * 100'000;
    summary.low_u6 = 99'000'000 - ordinal * 100'000;
    summary.close_u6 = 100'000'000 + ordinal * 50'000;
    summary.vwap_present = true;
    summary.vwap_u6 = 100'250'000;
    summary.rth_sum_r2 = 20'000.0 + static_cast<double>(ordinal) * 250.0;
    summary.rth_seconds = 23'400;
    summary.valid_steps = 23'400;
    if (!history.observe(summary).has_value()) {
      detail::fail_fast("wave2 guard: the history refused a guard summary");
    }
  }
  const PriorView priors = history.view_for(20U);

  const carriers::MidpointGrid grid = guard_grid();
  std::vector<carriers::GroupRecord> print_groups;
  std::vector<std::int64_t> notional_prefix;
  std::vector<std::int64_t> size_prefix;
  for (std::int64_t offset = 30; offset <= 570; offset += 60) {
    carriers::GroupRecord group;
    group.ts_ns_a = guard_clock().session_start_a().ns() + offset * carriers::kNanosPerSecond;
    group.token_count = 1;
    print_groups.push_back(group);
    const std::int64_t previous_notional = notional_prefix.empty() ? 0 : notional_prefix.back();
    const std::int64_t previous_size = size_prefix.empty() ? 0 : size_prefix.back();
    notional_prefix.push_back(previous_notional + 100 * (100'000'000 + offset * 1'000));
    size_prefix.push_back(previous_size + 100);
  }

  VarianceBudgetInputs inputs;
  inputs.grid = &grid;
  inputs.stock_print_groups = print_groups;
  inputs.vwap_notional_prefix = notional_prefix;
  inputs.vwap_size_prefix = size_prefix;
  inputs.priors = priors;
  auto budget = VarianceBudgetSession::build(inputs);
  if (!budget.has_value()) {
    detail::fail_fast("wave2 guard: the budget refused the guard session");
  }

  for (const std::size_t endpoint : {std::size_t{310}, std::size_t{400}, std::size_t{599}}) {
    for (const Side side : {Side::LONG, Side::SHORT}) {
      const VarianceBudgetRow vb = budget.value().channels(endpoint, side);
      for (std::size_t channel = 0; channel < kVarianceBudgetChannelCount; ++channel) {
        digest.feed_f64(vb.value[channel]);
        digest.feed_i64(static_cast<std::int64_t>(vb.validity[channel]));
      }
      PriorStructureInputs structure;
      structure.side = side;
      const auto mid = grid.points()[endpoint];
      structure.m_u6 = mid.mid_u6;
      structure.m_present = mid.present;
      const auto open = budget.value().open_u6();
      structure.open_u6 = open.value;
      structure.open_present = open.v == Validity::VALID;
      const auto vwap = budget.value().running_vwap_u6(endpoint);
      structure.intraday_vwap_u6 = vwap.value;
      structure.intraday_vwap_present = vwap.v == Validity::VALID;
      const auto phase = phase_fraction(static_cast<std::int64_t>(endpoint), 23'400);
      structure.phase = phase.value;
      structure.phase_present = phase.v == Validity::VALID;
      const auto sigma_scale = budget.value().sigma_scale_bps(endpoint);
      structure.sigma_scale_bps = sigma_scale.value;
      structure.sigma_scale_present = sigma_scale.v == Validity::VALID;
      structure.priors = priors;
      const PriorStructureRow ps = build_prior_structure(structure);
      for (std::size_t channel = 0; channel < kPriorStructureChannelCount; ++channel) {
        digest.feed_f64(ps.value[channel]);
        digest.feed_i64(static_cast<std::int64_t>(ps.validity[channel]));
      }
    }
  }
  return digest.hex();
}

}  // namespace qr::wave2::guard

#endif  // QR_WAVE2_TOOLS_GUARD_HPP
