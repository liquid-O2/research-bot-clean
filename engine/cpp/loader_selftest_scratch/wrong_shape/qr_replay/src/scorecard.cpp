// qr_replay/src/scorecard.cpp — scorecard aggregates (card section 6).
#include "qr_replay/scorecard.hpp"

#include <algorithm>
#include <cstddef>
#include <functional>
#include <utility>
#include <vector>

#include "qr_core/checked.hpp"

namespace qr::replay {

std::int64_t nearest_rank(const std::vector<std::int64_t>& ascending, std::int64_t p_percent) {
  const std::int64_t n = static_cast<std::int64_t>(ascending.size());
  if (n == 0) {
    return 0;
  }
  // ceil(p * n) in exact integers; index 1..n, 1-based.
  std::int64_t rank = (p_percent * n + 99) / 100;
  if (rank < 1) {
    rank = 1;
  }
  if (rank > n) {
    rank = n;
  }
  return ascending[static_cast<std::size_t>(rank - 1)];
}

Expected<Scorecard, Refusal> score(std::span<const DailyLedger> ledgers) {
  if (ledgers.empty()) {
    return refuse<Scorecard>(Refusal(RefusalCode::CONFIG, "qr_replay::score/empty",
                                     "a scorecard over zero sessions is not a number", 0));
  }

  Scorecard card;
  card.session_count = static_cast<std::int64_t>(ledgers.size());
  card.session_net_cent.reserve(ledgers.size());
  std::vector<std::int64_t> mae_cents;

  // --- per-session pass -----------------------------------------------------
  std::int64_t previous_ordinal = 0;
  bool have_previous = false;
  for (const DailyLedger& ledger : ledgers) {
    if (have_previous && ledger.session.session_ordinal <= previous_ordinal) {
      return refuse<Scorecard>(Refusal(RefusalCode::OUT_OF_ORDER, "qr_replay::score/chronology",
                                       "session ledgers are not in strictly increasing session order",
                                       ledger.session.session_ordinal));
    }
    previous_ordinal = ledger.session.session_ordinal;
    have_previous = true;

    card.session_net_cent.push_back(ledger.net_cent);
    card.trade_count += ledger.trade_count();
    if (ledger.zero_trade_session()) {
      ++card.zero_trade_session_count;
    }
    const Expected<std::int64_t, Refusal> total = checked_add(card.total_net_cent, ledger.net_cent);
    if (!total.has_value()) {
      return refuse<Scorecard>(total.error());
    }
    card.total_net_cent = total.value();

    for (const TradeRecord& trade : ledger.trades) {
      if (trade.mae_cent > card.max_mae_cent) {
        card.max_mae_cent = trade.mae_cent;
      }
      // THE BREACH, card section 6 verbatim: "Realized gap-through breaches —
      // defined as `stop_hit[h] AND gap_through_cent > 0` (stop fired AND the
      // fill landed beyond the wall; NOTE: the mod-10 lattice makes
      // `menu_mae_cent>30000` true for EVERY stopped trade, so MAE-threshold
      // counting is a degenerate breach statistic and is forbidden; MAE remains
      // a separate panel)". Both conjuncts are load-bearing and neither is
      // derivable from the other.
      if (trade.stop_hit && trade.gap_through_cent > 0) {
        ++card.breach_count;
      }
      mae_cents.push_back(trade.mae_cent);
    }
  }

  // --- MAE panel: nearest-rank {p50, p90, p95, p99}, max already tracked -----
  std::sort(mae_cents.begin(), mae_cents.end());
  card.mae_p50_cent = nearest_rank(mae_cents, 50);
  card.mae_p90_cent = nearest_rank(mae_cents, 90);
  card.mae_p95_cent = nearest_rank(mae_cents, 95);
  card.mae_p99_cent = nearest_rank(mae_cents, 99);

  const double sessions = static_cast<double>(card.session_count);
  card.mean_net_dollars = (static_cast<double>(card.total_net_cent) / 100.0) / sessions;
  card.trades_per_session = static_cast<double>(card.trade_count) / sessions;

  // --- MDD: exact, zero-inclusive, E0 = 0 in the running maximum ------------
  // Ek = sum_{i<=k} daily_i, running max over E0..Ek INCLUDING E0, and the
  // drawdown is max_k(running_max - Ek). Every session is in the sequence,
  // zero-trade ones included, and nothing is interpolated inside a day.
  std::int64_t equity = 0;       // E0
  std::int64_t running_max = 0;  // "include E0 in the running maximum"
  card.mdd_cent = 0;             // k = 0 contributes running_max - E0 = 0
  for (const std::int64_t daily : card.session_net_cent) {
    const Expected<std::int64_t, Refusal> next = checked_add(equity, daily);
    if (!next.has_value()) {
      return refuse<Scorecard>(next.error());
    }
    equity = next.value();
    if (equity > running_max) {
      running_max = equity;
    }
    const Expected<std::int64_t, Refusal> drawdown = checked_sub(running_max, equity);
    if (!drawdown.has_value()) {
      return refuse<Scorecard>(drawdown.error());
    }
    if (drawdown.value() > card.mdd_cent) {
      card.mdd_cent = drawdown.value();
    }
  }

  // --- leave-top-10-out ------------------------------------------------------
  if (card.session_count > 10) {
    std::vector<std::int64_t> sorted = card.session_net_cent;
    // Descending by net; the ten largest sessions come off the front. Sorting a
    // copy of the values keeps the panel independent of session order.
    std::sort(sorted.begin(), sorted.end(), std::greater<std::int64_t>());
    std::int64_t remaining_total = 0;
    for (std::size_t i = 10; i < sorted.size(); ++i) {
      const Expected<std::int64_t, Refusal> acc = checked_add(remaining_total, sorted[i]);
      if (!acc.has_value()) {
        return refuse<Scorecard>(acc.error());
      }
      remaining_total = acc.value();
    }
    const double remaining_sessions = static_cast<double>(card.session_count - 10);
    card.mean_net_dollars_leave_top_10_out =
        (static_cast<double>(remaining_total) / 100.0) / remaining_sessions;
  }

  // --- min-year --------------------------------------------------------------
  // Sorted vector, never an unordered container: iteration order is output here.
  std::vector<std::pair<std::int32_t, std::pair<std::int64_t, std::int64_t>>> per_year;  // year -> (sum, count)
  for (const DailyLedger& ledger : ledgers) {
    const std::int32_t year = ledger.session.year;
    const auto it = std::lower_bound(
        per_year.begin(), per_year.end(), year,
        [](const auto& entry, std::int32_t probe) { return entry.first < probe; });
    if (it == per_year.end() || it->first != year) {
      per_year.insert(it, {year, {ledger.net_cent, 1}});
    } else {
      const Expected<std::int64_t, Refusal> acc = checked_add(it->second.first, ledger.net_cent);
      if (!acc.has_value()) {
        return refuse<Scorecard>(acc.error());
      }
      it->second.first = acc.value();
      it->second.second += 1;
    }
  }
  bool first_year = true;
  for (const auto& entry : per_year) {
    const double mean =
        (static_cast<double>(entry.second.first) / 100.0) / static_cast<double>(entry.second.second);
    if (first_year || mean < card.min_year_mean_net_dollars) {
      card.min_year_mean_net_dollars = mean;
      card.min_year = entry.first;
      first_year = false;
    }
  }

  return card;
}

}  // namespace qr::replay
