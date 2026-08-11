#include "qr_wave2/session_pass.hpp"

#include <cmath>
#include <utility>

#include "qr_carriers/transforms.hpp"
#include "qr_sources/stock_quotes.hpp"
#include "qr_sources/stock_trades.hpp"

namespace qr::wave2 {
namespace {

/// The one body both scope overloads run. It takes the ALREADY-ADMITTED
/// registry row and the two paths, so it can neither form a path nor decide
/// which calendar a session belongs to — the same shape the readers use.
template <class Scope>
[[nodiscard]] Expected<SessionPassResult, Refusal> run_pass_admitted(const Scope& scope,
                                                                     const CorpusRoots& roots,
                                                                     bool retain_series) {
  auto clock = SessionClock::from_session(scope.session());
  if (!clock.has_value()) {
    return Expected<SessionPassResult, Refusal>::refuse(clock.error());
  }
  const SessionClock session_clock = clock.value();

  // --- the NBBO stream and its eligible-midpoint prefix series ---------------
  carriers::NbboStream nbbo(session_clock, carriers::StreamOptions{});
  {
    auto opened = qr::sources::StockQuoteReader::open(scope, roots.stock_quotes, scope.profile());
    if (!opened.has_value()) {
      return Expected<SessionPassResult, Refusal>::refuse(opened.error().refusal());
    }
    qr::sources::StockQuoteReader reader = std::move(opened).value();
    qr::sources::StockQuoteReader::Group group;
    for (;;) {
      auto more = reader.next_group(group);
      if (!more.has_value()) {
        return Expected<SessionPassResult, Refusal>::refuse(more.error().refusal());
      }
      if (!more.value()) {
        break;
      }
      const auto pushed = nbbo.push_group(group.ts_ms_b, group.rows);
      if (!pushed.has_value()) {
        return Expected<SessionPassResult, Refusal>::refuse(pushed.error());
      }
    }
  }

  // --- the stock prints and the eligible-print VWAP sums ---------------------
  carriers::StockPrintStream prints(session_clock, carriers::StreamOptions{});
  {
    auto opened = qr::sources::StockTradeReader::open(scope, roots.stock_trades);
    if (!opened.has_value()) {
      return Expected<SessionPassResult, Refusal>::refuse(opened.error().refusal());
    }
    qr::sources::StockTradeReader reader = std::move(opened).value();
    qr::sources::StockTradeReader::Group group;
    for (;;) {
      auto more = reader.next_group(group);
      if (!more.has_value()) {
        return Expected<SessionPassResult, Refusal>::refuse(more.error().refusal());
      }
      if (!more.value()) {
        break;
      }
      const auto pushed = prints.push_group(group.ts_ms_b, group.rows);
      if (!pushed.has_value()) {
        return Expected<SessionPassResult, Refusal>::refuse(pushed.error());
      }
    }
  }

  auto grid = carriers::MidpointGrid::build(session_clock, nbbo.eligible_midpoints());
  if (!grid.has_value()) {
    return Expected<SessionPassResult, Refusal>::refuse(grid.error());
  }

  SessionPassResult result;
  // T_RTH: the session's own registered span in seconds (390 bars, or 210 on
  // the nine early closes — read from the session's own row, never assumed).
  const std::int64_t rth_seconds = session_clock.expected_bar_count() * 60;
  result.summary = summarize_session(scope.ordinal(), grid.value(), prints.vwap_notional_sum(),
                                     prints.vwap_size_sum(), rth_seconds);
  result.nbbo_groups = static_cast<std::int64_t>(nbbo.groups().size());
  result.print_groups = static_cast<std::int64_t>(prints.groups().size());
  if (retain_series) {
    result.grid = std::move(grid.value());
    result.stock_print_groups = prints.groups();
    result.vwap_notional_prefix = prints.vwap_notional_prefix();
    result.vwap_size_prefix = prints.vwap_size_prefix();
    result.series_retained = true;
  }
  return result;
}

}  // namespace

SessionSummary summarize_session(std::int64_t ordinal, const carriers::MidpointGrid& grid,
                                 std::int64_t vwap_notional_sum, std::int64_t vwap_size_sum,
                                 std::int64_t rth_seconds) noexcept {
  SessionSummary summary;
  summary.ordinal = ordinal;
  summary.rth_seconds = rth_seconds;

  // pH/pL/pC = max/min/LAST of the session's PRESENT grid midpoints, and the
  // session's total sum of r^2 over its valid 1s steps — one walk, because both
  // read the same series.
  const std::vector<carriers::GridPoint>& points = grid.points();
  bool have_previous = false;
  std::int64_t previous_mid = 0;
  for (const carriers::GridPoint& point : points) {
    if (!point.present || point.mid_u6 <= 0) {
      have_previous = false;
      continue;
    }
    if (!summary.grid_present) {
      summary.grid_present = true;
      summary.high_u6 = point.mid_u6;
      summary.low_u6 = point.mid_u6;
    } else {
      if (point.mid_u6 > summary.high_u6) {
        summary.high_u6 = point.mid_u6;
      }
      if (point.mid_u6 < summary.low_u6) {
        summary.low_u6 = point.mid_u6;
      }
    }
    summary.close_u6 = point.mid_u6;
    if (have_previous) {
      const double ratio = static_cast<double>(point.mid_u6) / static_cast<double>(previous_mid);
      const double r_bps = static_cast<double>(carriers::kBpsScale) * std::log(ratio);
      summary.rth_sum_r2 += r_bps * r_bps;
      ++summary.valid_steps;
    }
    have_previous = true;
    previous_mid = point.mid_u6;
  }

  // pVWAP = Sum(price*size)/Sum(size) over ELIGIBLE stock prints — the exact
  // integer sums the print stream kept, divided once, here.
  if (vwap_size_sum > 0) {
    summary.vwap_present = true;
    summary.vwap_u6 = vwap_notional_sum / vwap_size_sum;
  }
  return summary;
}

Expected<SessionPassResult, Refusal> run_pass(const DayScope& scope, const CorpusRoots& roots,
                                              bool retain_series) {
  return run_pass_admitted(scope, roots, retain_series);
}

Expected<SessionPassResult, Refusal> run_pass(const WarmupScope& scope, const CorpusRoots& roots) {
  // CC-012: prior state only. The series are never retained for a warmup
  // session, so there is nothing for a decision constructor to be handed.
  return run_pass_admitted(scope, roots, false);
}

Expected<bool, Refusal> admit_decision_ordinal(std::int64_t ordinal) noexcept {
  if (is_warmup_ordinal(ordinal)) {
    return Expected<bool, Refusal>::refuse(
        refuse_warmup_ordinal("qr_wave2::admit_decision_ordinal", ordinal));
  }
  if (ordinal < kScopeFirstOrdinal || ordinal > kScopeLastOrdinal) {
    return Expected<bool, Refusal>::refuse(
        Refusal(RefusalCode::ORDINAL_OUTSIDE_SCOPE, "qr_wave2::admit_decision_ordinal",
                "a decision row lives only in the scoped calendar 125..749", ordinal));
  }
  return true;
}

}  // namespace qr::wave2
