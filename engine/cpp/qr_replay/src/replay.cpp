// qr_replay/src/replay.cpp — the one economic replay kernel (FINAL_PLAN
// APPENDIX C6 + card section 6 chronology/selection law + section 11 policy).
#include "qr_replay/replay.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <limits>
#include <utility>
#include <vector>

#include "qr_core/checked.hpp"
#include "qr_replay/pcg64.hpp"

namespace qr::replay {
namespace {

using CensusIndex = std::size_t;

CensusIndex census_index(ClockOutcome outcome) noexcept {
  return static_cast<CensusIndex>(static_cast<std::uint8_t>(outcome));
}

Refusal content_mismatch(const char* site, const char* detail, std::int64_t context) noexcept {
  return Refusal(RefusalCode::CONTENT_MISMATCH, site, detail, context);
}

/// Row-level tape validation. Runs on EVERY row, selected or not: a defective
/// tape is a defect whether or not the defect happened to be executed.
std::optional<Refusal> validate_row(const SessionRef& session, const ScoredAction& action,
                                    std::size_t horizon_index) noexcept {
  if (action.key.session_ordinal != session.session_ordinal) {
    return content_mismatch("qr_replay::replay/session", "action key belongs to another session",
                            action.key.session_ordinal);
  }
  if (!(action.label.key == action.key)) {
    // The C6 "key misjoin" mutant: a label carried by the wrong row.
    return content_mismatch("qr_replay::replay/key_misjoin",
                            "label key does not equal the scored action's own key",
                            action.label.key.decision_ordinal);
  }
  if (action.label.state != LabelState::OK) {
    return std::nullopt;  // an unavailable label carries no marks to check
  }
  if (action.label.cost_charged_cent != kTradeCostCent) {
    // "576c charged once per trade": the label kernel charges it, exactly once,
    // and the replay refuses to execute a label that says otherwise.
    return content_mismatch("qr_replay::replay/cost_once",
                            "label did not charge exactly 576 cents once",
                            action.label.cost_charged_cent);
  }
  if (action.label.entry_ts_ns <= action.key.decision_ts_ns) {
    return Refusal(RefusalCode::CLOCK_VIOLATION, "qr_replay::replay/entry_after_decision",
                   "fill instant is not strictly after its own decision instant",
                   action.label.entry_ts_ns);
  }
  if (action.label.menu_exit_ts[horizon_index] < action.label.entry_ts_ns) {
    return Refusal(RefusalCode::CLOCK_VIOLATION, "qr_replay::replay/exit_after_entry",
                   "exit instant precedes its own entry instant",
                   action.label.menu_exit_ts[horizon_index]);
  }
  return std::nullopt;
}

/// The selection law over a candidate set: "the unique highest predicted-net
/// ... side; an exact top tie abstains". Returns the selected index, or
/// npos with `tie` set when the top is not unique.
struct Selection {
  std::size_t index = std::numeric_limits<std::size_t>::max();
  bool tie = false;
  bool any = false;
};

}  // namespace

const char* clock_outcome_name(ClockOutcome outcome) noexcept {
  switch (outcome) {
    case ClockOutcome::ENTERED: return "ENTERED";
    case ClockOutcome::NO_LEGAL_ROW: return "NO_LEGAL_ROW";
    case ClockOutcome::GATE_BLOCKED: return "GATE_BLOCKED";
    case ClockOutcome::ABSTAIN_TIE: return "ABSTAIN_TIE";
    case ClockOutcome::OCCUPIED: return "OCCUPIED";
    case ClockOutcome::NO_FRESH_FILL: return "NO_FRESH_FILL";
    case ClockOutcome::OVERRIDE_SIDE_UNAVAILABLE: return "OVERRIDE_SIDE_UNAVAILABLE";
    case ClockOutcome::HALTED_DAILY_LOSS: return "HALTED_DAILY_LOSS";
  }
  return "UNKNOWN_CLOCK_OUTCOME";
}

const char* side_override_name(SideOverride override_kind) noexcept {
  switch (override_kind) {
    case SideOverride::NONE: return "NONE";
    case SideOverride::FORCE_LONG: return "FORCE_LONG";
    case SideOverride::FORCE_SHORT: return "FORCE_SHORT";
    case SideOverride::SEEDED_COIN: return "SEEDED_COIN";
  }
  return "UNKNOWN_SIDE_OVERRIDE";
}

Expected<DailyLedger, Refusal> replay(const SessionRef& session,
                                      std::span<const ScoredAction> actions,
                                      PolicyGate& gate,
                                      const ReplayPolicy& policy) {
  if (policy.horizon_index >= kHorizonCount) {
    return refuse<DailyLedger>(Refusal(RefusalCode::CONFIG, "qr_replay::replay/horizon",
                                       "horizon index outside the frozen 7-menu",
                                       static_cast<std::int64_t>(policy.horizon_index)));
  }

  DailyLedger ledger;
  ledger.session = session;
  ledger.row_count = static_cast<std::int64_t>(actions.size());
  gate.begin_session(session.session_ordinal);

  const std::size_t h = policy.horizon_index;
  const std::size_t row_count = actions.size();

  bool has_traded = false;
  std::int64_t last_exit_ts = 0;
  std::int64_t realized_cent = 0;
  bool halted = false;

  // Reusable scratch for the per-clock one-to-one key check; declared once so a
  // million-row tape does not allocate per clock.
  std::vector<std::pair<std::int64_t, std::int64_t>> group_keys;

  std::int64_t previous_ts = 0;
  bool have_previous_ts = false;

  std::size_t i = 0;
  while (i < row_count) {
    const std::int64_t clock_ts = actions[i].key.decision_ts_ns;
    if (have_previous_ts && clock_ts <= previous_ts) {
      // Equal-timestamp rows are ONE clock, so a repeated or smaller timestamp
      // here means the tape is not chronological. It is never sorted silently.
      return refuse<DailyLedger>(Refusal(RefusalCode::OUT_OF_ORDER, "qr_replay::replay/chronology",
                                         "decision timestamps are not strictly increasing across clocks",
                                         clock_ts));
    }
    std::size_t j = i;
    while (j < row_count && actions[j].key.decision_ts_ns == clock_ts) {
      ++j;
    }

    // --- per-row validation and census ------------------------------------
    group_keys.clear();
    for (std::size_t k = i; k < j; ++k) {
      const ScoredAction& row = actions[k];
      if (const std::optional<Refusal> bad = validate_row(session, row, h); bad.has_value()) {
        return refuse<DailyLedger>(*bad);
      }
      group_keys.emplace_back(row.key.decision_ordinal, static_cast<std::int64_t>(row.key.side));
      if (row.legal_enter) {
        ++ledger.legal_row_count;
        if (!std::isfinite(row.predicted_net_h_star) || !std::isfinite(row.predicted_stop_prob_h_ref)) {
          ++ledger.nonfinite_score_count;
        }
      }
    }
    std::sort(group_keys.begin(), group_keys.end());
    if (std::adjacent_find(group_keys.begin(), group_keys.end()) != group_keys.end()) {
      // "The scientific/prediction key (session_ordinal,decision_ordinal,side)
      // plus timestamp must be one-to-one" (card section 3).
      return refuse<DailyLedger>(content_mismatch("qr_replay::replay/duplicate_key",
                                                  "two rows share one prediction key at one clock",
                                                  clock_ts));
    }

    ++ledger.clock_count;

    // --- the decision at this clock ---------------------------------------
    ClockOutcome outcome = ClockOutcome::NO_LEGAL_ROW;
    std::size_t executed = std::numeric_limits<std::size_t>::max();

    if (halted) {
      outcome = ClockOutcome::HALTED_DAILY_LOSS;
    } else if (has_traded && clock_ts <= last_exit_ts) {
      // "Occupied clocks cannot enter"; "A new entry requires decision_ts >
      // prior certificate_exit_ts".
      outcome = ClockOutcome::OCCUPIED;
    } else {
      Selection admitted;
      double best = 0.0;
      bool any_legal = false;
      for (std::size_t k = i; k < j; ++k) {
        const ScoredAction& row = actions[k];
        if (row.legal_enter) {
          any_legal = true;
        }
        const GateDecision decision = gate.evaluate(row);
        if (!decision.admitted) {
          continue;
        }
        if (!admitted.any || row.predicted_net_h_star > best) {
          admitted.any = true;
          admitted.index = k;
          admitted.tie = false;
          best = row.predicted_net_h_star;
        } else if (row.predicted_net_h_star == best) {
          admitted.tie = true;  // "an exact top tie abstains"
        }
      }

      if (!any_legal) {
        outcome = ClockOutcome::NO_LEGAL_ROW;
      } else if (!admitted.any) {
        outcome = ClockOutcome::GATE_BLOCKED;
      } else if (admitted.tie) {
        outcome = ClockOutcome::ABSTAIN_TIE;
      } else {
        executed = admitted.index;

        // --- null-control side streams (sections 8 and 11) -----------------
        if (policy.side_override != SideOverride::NONE) {
          Side target = Side::LONG;
          switch (policy.side_override) {
            case SideOverride::FORCE_LONG: target = Side::LONG; break;
            case SideOverride::FORCE_SHORT: target = Side::SHORT; break;
            case SideOverride::SEEDED_COIN:
              target = coin_side(session.session_ordinal, ledger.coin_draws);
              ++ledger.coin_draws;
              break;
            case SideOverride::NONE: break;
          }
          Selection forced;
          double forced_best = 0.0;
          for (std::size_t k = i; k < j; ++k) {
            const ScoredAction& row = actions[k];
            if (!row.legal_enter || row.key.side != target || !std::isfinite(row.predicted_net_h_star)) {
              continue;
            }
            if (!forced.any || row.predicted_net_h_star > forced_best) {
              forced.any = true;
              forced.index = k;
              forced.tie = false;
              forced_best = row.predicted_net_h_star;
            } else if (row.predicted_net_h_star == forced_best) {
              forced.tie = true;
            }
          }
          if (!forced.any) {
            outcome = ClockOutcome::OVERRIDE_SIDE_UNAVAILABLE;
            executed = std::numeric_limits<std::size_t>::max();
          } else if (forced.tie) {
            outcome = ClockOutcome::ABSTAIN_TIE;
            executed = std::numeric_limits<std::size_t>::max();
          } else {
            executed = forced.index;
          }
        }

        if (executed != std::numeric_limits<std::size_t>::max()) {
          const ScoredAction& row = actions[executed];
          if (row.label.state != LabelState::OK) {
            // "An ENTER selected on an unavailable label becomes typed
            // NO_FRESH_FILL, makes no trade, ... and is never silently dropped."
            outcome = ClockOutcome::NO_FRESH_FILL;
          } else {
            TradeRecord trade;
            trade.key = row.key;
            trade.entry_ts_ns = row.label.entry_ts_ns;
            trade.exit_ts_ns = row.label.menu_exit_ts[h];
            trade.net_cent = row.label.menu_net_cent[h];
            trade.mae_cent = row.label.menu_mae_cent[h];
            trade.stop_hit = row.label.stop_hit[h] != 0;
            // The label's shared stop_scan reported this; the replay carries it
            // and never recomputes it, so the breach panel and the label kernel
            // cannot disagree about what happened at the wall.
            trade.gap_through_cent = row.label.gap_through_cent;

            const Expected<std::int64_t, Refusal> running = checked_add(realized_cent, trade.net_cent);
            if (!running.has_value()) {
              return refuse<DailyLedger>(running.error());
            }
            realized_cent = running.value();
            ledger.net_cent = realized_cent;
            ledger.trades.push_back(trade);
            has_traded = true;
            last_exit_ts = trade.exit_ts_ns;
            outcome = ClockOutcome::ENTERED;

            if (policy.daily_loss_limit_cent.has_value() &&
                realized_cent <= *policy.daily_loss_limit_cent) {
              halted = true;
              ledger.halted_daily_loss = true;
            }
          }
        }
      }
    }

    ledger.clock_census[census_index(outcome)] += 1;

    // --- causality: the clock's own rows join the population only AFTER every
    // decision at this clock has been made.
    for (std::size_t k = i; k < j; ++k) {
      gate.observe(actions[k]);
    }

    previous_ts = clock_ts;
    have_previous_ts = true;
    i = j;
  }

  return ledger;
}

}  // namespace qr::replay
