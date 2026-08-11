// qr_replay/scorecard.hpp — the scorecard aggregates over a chronological
// sequence of DailyLedgers (WP11's second half).
//
// SPEC (verbatim, card section 6):
//   "Secondary hindsight replay reports dollars/all-session, trades/day, MDD,
//    MAE quantiles/max/>$300, zero days, leave-top-10-out, and min-year."
//   "MDD is exact zero-inclusive end-of-day drawdown: form one net-dollar value
//    for every chronological test session (zero on no-trade days), set equity
//    E0=0 and `Ek=sum_{i<=k} daily_i`, include E0 in the running maximum, and
//    report `max_k(running_max(E0..Ek)-Ek)`. No intraday interpolation or
//    omission of zero days."
//
// SPEC (FINAL_PLAN section 11): the pass conditions read `mean_LCB > $2,000`
// and `MDD_UCB < $1,000` off the block-resampled estimator, and the
// concentration panel is "leave-top-10-out clears + min-year + zero-day + gap +
// tail panels", with "realized gap-through breach count reported with UCB".
//
// WHAT A BREACH IS (card section 6, as amended by the consolidated review,
// verbatim): "Realized gap-through breaches — defined as `stop_hit[h] AND
// gap_through_cent > 0` (stop fired AND the fill landed beyond the wall; NOTE:
// the mod-10 lattice makes `menu_mae_cent>30000` true for EVERY stopped trade,
// so MAE-threshold counting is a degenerate breach statistic and is forbidden;
// MAE remains a separate panel)". The V3.3.3 phrasing `menu_mae[h*]>30000` that
// FINAL_PLAN section 11 still carries is superseded by this definition.
//
// WHAT THIS FILE DOES NOT DO. It computes no confidence bound. The mean LCB and
// the MDD UCB are the pinned `estimator_laws.py` and its MDD sibling law (own
// SHA, year strata, block 5, 10,000 replicates); this scorecard produces the
// per-session net vector and the exact statistics those laws resample, and
// nothing here may grow a second, unpinned estimator.
//
// MAE QUANTILES (orchestrator ruling, 2026-08-10, in answer to this lane's
// question 8): "MAE quantiles = {p50,p90,p95,p99,max}, nearest-rank". Levels and
// estimator are therefore preregistered, not chosen here. NEAREST-RANK means the
// value at 1-based ascending index ceil(p*N) — no interpolation, so every
// reported number is an MAE that a real trade actually printed:
//
//     index(p) = ceil(p * N)  computed in integers as (p_percent * N + 99) / 100,
//     clamped into [1, N];  p50/p90/p95/p99, and max = index N.
//
// The per-trade values stay exposed on the ledgers (`TradeRecord::mae_cent`) so
// any further panel can be built without a second estimator.
#ifndef QR_REPLAY_SCORECARD_HPP
#define QR_REPLAY_SCORECARD_HPP

#include <cstdint>
#include <optional>
#include <span>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_replay/replay.hpp"

namespace qr::replay {

struct Scorecard {
  /// The denominator: EVERY session handed in, including zero-trade sessions
  /// and sessions with no tradable row at all.
  std::int64_t session_count = 0;
  std::int64_t zero_trade_session_count = 0;
  std::int64_t trade_count = 0;

  /// One net value per session, in chronological order (zero on a no-trade
  /// session). This is the vector the pinned estimator resamples.
  std::vector<std::int64_t> session_net_cent;

  std::int64_t total_net_cent = 0;
  double mean_net_dollars = 0.0;      ///< dollars per session over ALL sessions.
  double trades_per_session = 0.0;

  /// Exact zero-inclusive end-of-day MDD, in cents, with E0 = 0 included in the
  /// running maximum.
  std::int64_t mdd_cent = 0;

  /// Concentration panels.
  std::optional<double> mean_net_dollars_leave_top_10_out;  ///< nullopt when <= 10 sessions.
  double min_year_mean_net_dollars = 0.0;
  std::int32_t min_year = 0;

  /// Gap-through breach panel (card section 6): trades where the stop FIRED and
  /// the fill landed beyond the wall — `stop_hit[h] AND gap_through_cent > 0`.
  /// It is NOT an MAE threshold: `net_cent = frac_u6*10 - 576` puts every MAE
  /// on the residue class 6 (mod 10), so the smallest MAE a stopped trade can
  /// print is 30,006 and `mae > 30000` would count every stopped trade.
  std::int64_t breach_count = 0;
  /// The worst realised MAE over every trade — a SEPARATE panel, never the
  /// breach test.
  std::int64_t max_mae_cent = 0;

  /// Nearest-rank MAE quantiles over every trade of every session, in cents.
  /// All zero when no trade was taken at all.
  std::int64_t mae_p50_cent = 0;
  std::int64_t mae_p90_cent = 0;
  std::int64_t mae_p95_cent = 0;
  std::int64_t mae_p99_cent = 0;
};

/// The nearest-rank quantile of an ASCENDING-sorted vector: the value at 1-based
/// index ceil(p_percent/100 * N), clamped into [1, N]. Exposed because the
/// scorecard's MAE panel and any cross-check must use the one definition.
[[nodiscard]] std::int64_t nearest_rank(const std::vector<std::int64_t>& ascending,
                                        std::int64_t p_percent);

/// Aggregate a chronological sequence of session ledgers.
///
/// Refusals: CONFIG (no sessions at all — a scorecard over nothing is not a
/// number), OUT_OF_ORDER (session ordinals not strictly increasing: the MDD is
/// defined on the chronological sequence, so a resorted input would silently
/// produce a different drawdown), ARITHMETIC_OVERFLOW from the equity sum.
Expected<Scorecard, Refusal> score(std::span<const DailyLedger> ledgers);

}  // namespace qr::replay

#endif  // QR_REPLAY_SCORECARD_HPP
