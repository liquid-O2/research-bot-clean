#include "qr_labels/watches.hpp"

#include <algorithm>
#include <array>
#include <utility>

namespace qr::labels {
namespace {

constexpr const char* kClockSite = "qr_labels::DecisionClock";
constexpr const char* kRosterSite = "qr_labels::DecisionRoster";
constexpr const char* kWatchSite = "qr_labels::build_watches";
constexpr const char* kWallSite = "qr_labels::visibility_wall";

constexpr std::array<const char*, kWatchStageCount> kStageNames{"D0", "D30", "D60"};
/// The card's own offsets: D0 is the visibility itself, D30 is +30s, D60 +60s.
constexpr std::array<std::int64_t, kWatchStageCount> kStageOffsetNs{
    0, 30 * kNanosecondsPerSecond, 60 * kNanosecondsPerSecond};

void append_i64(std::string& out, std::int64_t value) { out += std::to_string(value); }

void append_metric(std::string& out, std::string_view label, std::string_view metric,
                   std::int64_t value) {
  out.append(label);
  out.push_back('\t');
  out.append(metric);
  out.push_back('\t');
  append_i64(out, value);
  out.push_back('\n');
}

}  // namespace

const char* watch_stage_name(WatchStage stage) noexcept {
  const auto index = static_cast<std::size_t>(stage);
  return index < kStageNames.size() ? kStageNames[index] : "UNKNOWN";
}

std::int64_t watch_stage_offset_ns(WatchStage stage) noexcept {
  const auto index = static_cast<std::size_t>(stage);
  return index < kStageOffsetNs.size() ? kStageOffsetNs[index] : 0;
}

// ---------------------------------------------------------------------------
// DecisionClock
// ---------------------------------------------------------------------------

Expected<DecisionClock, Refusal> DecisionClock::from_clock(const SessionClock& clock) {
  const std::int64_t start = clock.session_start_a().ns();
  const std::int64_t end = clock.session_end_a().ns();
  const Expected<std::int64_t, Refusal> span = checked_sub(end, start);
  if (!span.has_value()) {
    return Expected<DecisionClock, Refusal>::refuse(span.error());
  }
  if (span.value() <= 0 || span.value() % kNanosecondsPerSecond != 0) {
    // The session's own registry row makes the span an exact number of bars,
    // so an inexact number of whole seconds means the clock and the registry
    // disagree — a refusal, never a rounded second count.
    return Expected<DecisionClock, Refusal>::refuse(
        Refusal(RefusalCode::CLOCK_VIOLATION, kClockSite,
                "the session span is not a positive whole number of seconds", span.value()));
  }
  return DecisionClock(start, end, span.value() / kNanosecondsPerSecond);
}

Expected<std::int64_t, Refusal> DecisionClock::second_ts(std::int64_t second) const noexcept {
  if (second < 0 || second >= second_count_) {
    return Expected<std::int64_t, Refusal>::refuse(
        Refusal(RefusalCode::CLOCK_VIOLATION, kClockSite,
                "the session does not register that whole second", second));
  }
  const Expected<std::int64_t, Refusal> offset = checked_mul(second, kNanosecondsPerSecond);
  if (!offset.has_value()) {
    return Expected<std::int64_t, Refusal>::refuse(offset.error());
  }
  return checked_add(session_start_ns_, offset.value());
}

Expected<std::int64_t, Refusal> DecisionClock::second_of(std::int64_t ts) const noexcept {
  const Expected<std::int64_t, Refusal> delta = checked_sub(ts, session_start_ns_);
  if (!delta.has_value()) {
    return Expected<std::int64_t, Refusal>::refuse(delta.error());
  }
  if (delta.value() < 0 || delta.value() % kNanosecondsPerSecond != 0) {
    return Expected<std::int64_t, Refusal>::refuse(
        Refusal(RefusalCode::CLOCK_VIOLATION, kClockSite,
                "the instant is not a registered whole second of this session", ts));
  }
  const std::int64_t second = delta.value() / kNanosecondsPerSecond;
  if (second >= second_count_) {
    return Expected<std::int64_t, Refusal>::refuse(
        Refusal(RefusalCode::CLOCK_VIOLATION, kClockSite,
                "the instant is at or after this session's close", ts));
  }
  return second;
}

std::int64_t DecisionClock::first_second_strictly_after(std::int64_t ts) const noexcept {
  if (second_count_ <= 0) {
    return kNoIndex;
  }
  if (ts < session_start_ns_) {
    return 0;
  }
  const std::int64_t delta = ts - session_start_ns_;
  const std::int64_t second = delta / kNanosecondsPerSecond + 1;
  return second < second_count_ ? second : kNoIndex;
}

std::int64_t DecisionClock::first_second_at_or_after(std::int64_t ts) const noexcept {
  if (second_count_ <= 0) {
    return kNoIndex;
  }
  if (ts <= session_start_ns_) {
    return 0;
  }
  const std::int64_t delta = ts - session_start_ns_;
  const std::int64_t second = ceil_div_positive(delta, kNanosecondsPerSecond);
  return second < second_count_ ? second : kNoIndex;
}

std::int64_t DecisionClock::last_second_at_or_before(std::int64_t ts) const noexcept {
  if (second_count_ <= 0 || ts < session_start_ns_) {
    return kNoIndex;
  }
  const std::int64_t delta = ts - session_start_ns_;
  const std::int64_t second = delta / kNanosecondsPerSecond;
  // Past the close, the last registered whole second at or before `ts` is the
  // session's final registered second. This is not a range-limited guard
  // substituting a value for a refusal: it is the definition of "last
  // registered second <= ts" over a finite registered set.
  return second < second_count_ ? second : second_count_ - 1;
}

// ---------------------------------------------------------------------------
// THE VISIBILITY WALL
// ---------------------------------------------------------------------------

Expected<std::int64_t, Refusal> refuse_unless_visible_in_session(
    const DecisionClock& clock, std::int64_t visible_ts_ns) noexcept {
  // A BOUND CHECK, deliberately not `second_of`. The roster is the union of the
  // registered seconds AND the candidate visibilities, so an instant that is
  // not a registered whole second is exactly what the union law exists to carry;
  // a wall written with `second_of` would refuse every lawful sub-second
  // visibility and collapse the roster back onto the second grid.
  //
  // HALF-OPEN, because the card's own registered set is: seconds run
  // k = 0 .. bar_count*60 - 1 and "the close instant is NOT a registered
  // second". `session_end_ns` is that close instant, so it is OUT.
  if (visible_ts_ns < clock.session_start_ns()) {
    return Expected<std::int64_t, Refusal>::refuse(
        Refusal(RefusalCode::CLOCK_VIOLATION, kWallSite,
                "the candidate's visibility is before the session open", visible_ts_ns));
  }
  if (visible_ts_ns >= clock.session_end_ns()) {
    return Expected<std::int64_t, Refusal>::refuse(
        Refusal(RefusalCode::CLOCK_VIOLATION, kWallSite,
                "the candidate's visibility is at or after the session close", visible_ts_ns));
  }
  return visible_ts_ns;
}

// ---------------------------------------------------------------------------
// DecisionRoster
// ---------------------------------------------------------------------------

Expected<DecisionRoster, Refusal> DecisionRoster::build(const DecisionClock& clock,
                                                        std::span<const std::int64_t> visibilities) {
  // THE VISIBILITY WALL, before anything is unioned (card section 3, review
  // B1): "a candidate `visible_ts_ns` outside [session_start_ns,
  // session_end_ns) is REFUSED (typed CLOCK_VIOLATION), never censused into the
  // ordinal roster — a fail-open here silently renumbers every decision ordinal
  // in the session."
  for (const std::int64_t visibility : visibilities) {
    const Expected<std::int64_t, Refusal> inside =
        refuse_unless_visible_in_session(clock, visibility);
    if (!inside.has_value()) {
      return Expected<DecisionRoster, Refusal>::refuse(inside.error());
    }
  }
  std::vector<std::int64_t> instants;
  instants.reserve(static_cast<std::size_t>(clock.second_count()) + visibilities.size());
  for (std::int64_t second = 0; second < clock.second_count(); ++second) {
    const Expected<std::int64_t, Refusal> ts = clock.second_ts(second);
    if (!ts.has_value()) {
      return Expected<DecisionRoster, Refusal>::refuse(ts.error());
    }
    instants.push_back(ts.value());
  }
  for (const std::int64_t visibility : visibilities) {
    instants.push_back(visibility);
  }
  // THE UNION, sorted and deduplicated: "the sorted union of every registered
  // whole second and every ... visibility timestamp".
  std::sort(instants.begin(), instants.end());
  instants.erase(std::unique(instants.begin(), instants.end()), instants.end());

  DecisionRoster roster(std::move(instants));
  // Condition 6 in this module's shape: strict increase is re-checked on the
  // OUTPUT, so a construction that stopped deduplicating cannot pass.
  for (std::size_t index = 1; index < roster.instants_.size(); ++index) {
    if (roster.instants_[index] <= roster.instants_[index - 1]) {
      return Expected<DecisionRoster, Refusal>::refuse(
          Refusal(RefusalCode::OUT_OF_ORDER, kRosterSite,
                  "the authority roster is not strictly increasing",
                  static_cast<std::int64_t>(index)));
    }
  }
  for (const std::int64_t visibility : visibilities) {
    const Expected<std::int64_t, Refusal> second = clock.second_of(visibility);
    if (second.has_value()) {
      roster.visibility_on_second_ += 1;
    } else {
      roster.visibility_only_ += 1;
    }
  }
  return roster;
}

Expected<DecisionRoster, Refusal> DecisionRoster::from_instants(std::vector<std::int64_t> instants) {
  DecisionRoster roster(std::move(instants));
  for (std::size_t index = 1; index < roster.instants_.size(); ++index) {
    if (roster.instants_[index] <= roster.instants_[index - 1]) {
      return Expected<DecisionRoster, Refusal>::refuse(
          Refusal(RefusalCode::OUT_OF_ORDER, kRosterSite,
                  "the authority roster is not strictly increasing",
                  static_cast<std::int64_t>(index)));
    }
  }
  return roster;
}

std::int64_t DecisionRoster::ts_at(std::int64_t ordinal) const {
  if (ordinal < 0 || ordinal >= size()) {
    detail::fail_fast("qr::labels::DecisionRoster::ts_at outside the roster");
  }
  return instants_[static_cast<std::size_t>(ordinal)];
}

Expected<std::int64_t, Refusal> DecisionRoster::ordinal_of(std::int64_t ts) const noexcept {
  const auto found = std::lower_bound(instants_.begin(), instants_.end(), ts);
  if (found == instants_.end() || *found != ts) {
    // THE EXACT JOIN. A decision instant that is not on the authority roster
    // is a refusal; there is no nearest-neighbour fallback anywhere.
    return Expected<std::int64_t, Refusal>::refuse(
        Refusal(RefusalCode::CONTENT_MISMATCH, kRosterSite,
                "the decision instant is not on the authority clock roster", ts));
  }
  return static_cast<std::int64_t>(found - instants_.begin());
}

// ---------------------------------------------------------------------------
// The watch build.
// ---------------------------------------------------------------------------

std::string WatchCensus::to_tsv(std::string_view label) const {
  std::string out = "label\tmetric\tvalue\n";
  append_metric(out, label, "candidates", candidates);
  append_metric(out, label, "watches_built", watches_built);
  append_metric(out, label, "watches_clock_unavailable", watches_clock_unavailable);
  for (std::size_t stage = 0; stage < kWatchStageCount; ++stage) {
    std::string metric = "watches_built_";
    metric += kStageNames[stage];
    append_metric(out, label, metric, per_stage_built[stage]);
  }
  for (std::size_t stage = 0; stage < kWatchStageCount; ++stage) {
    std::string metric = "watches_clock_unavailable_";
    metric += kStageNames[stage];
    append_metric(out, label, metric, per_stage_clock_unavailable[stage]);
  }
  append_metric(out, label, "actions", actions);
  append_metric(out, label, "actions_long", actions_long);
  append_metric(out, label, "actions_short", actions_short);
  append_metric(out, label, "converged_watches", converged_watches);
  return out;
}

Expected<std::int64_t, Refusal> refuse_unless_one_to_one(
    std::span<const ActionRow> actions) noexcept {
  for (std::size_t index = 0; index < actions.size(); ++index) {
    const ActionRow& current = actions[index];
    if (index > 0) {
      const ActionRow& previous = actions[index - 1];
      const bool ascending =
          previous.key.decision_ordinal < current.key.decision_ordinal ||
          (previous.key.decision_ordinal == current.key.decision_ordinal &&
           static_cast<std::int64_t>(previous.key.side) < static_cast<std::int64_t>(current.key.side));
      if (!ascending) {
        return Expected<std::int64_t, Refusal>::refuse(
            Refusal(RefusalCode::OUT_OF_ORDER, kWatchSite,
                    "the prediction keys are not strictly ascending, so one key repeats",
                    current.key.decision_ordinal));
      }
      if (previous.key.decision_ordinal == current.key.decision_ordinal &&
          previous.key.decision_ts_ns != current.key.decision_ts_ns) {
        return Expected<std::int64_t, Refusal>::refuse(
            Refusal(RefusalCode::CONTENT_MISMATCH, kWatchSite,
                    "one decision ordinal carries two different instants",
                    current.key.decision_ts_ns));
      }
      if (previous.key.decision_ordinal != current.key.decision_ordinal &&
          previous.key.decision_ts_ns == current.key.decision_ts_ns) {
        return Expected<std::int64_t, Refusal>::refuse(
            Refusal(RefusalCode::CONTENT_MISMATCH, kWatchSite,
                    "two decision ordinals carry the same instant",
                    current.key.decision_ts_ns));
      }
      if (previous.key.decision_ordinal < current.key.decision_ordinal &&
          previous.key.decision_ts_ns > current.key.decision_ts_ns) {
        return Expected<std::int64_t, Refusal>::refuse(
            Refusal(RefusalCode::OUT_OF_ORDER, kWatchSite,
                    "a later decision ordinal carries an earlier instant",
                    current.key.decision_ts_ns));
      }
    }
  }
  return static_cast<std::int64_t>(actions.size());
}

Expected<WatchPlan, Refusal> build_watches(std::int64_t session_ordinal, const DecisionClock& clock,
                                           const DecisionRoster& roster,
                                           std::span<const WatchCandidate> candidates) {
  WatchPlan plan;
  plan.ledger.reserve(candidates.size() * kWatchStageCount);
  plan.census.candidates = static_cast<std::int64_t>(candidates.size());

  // THE VISIBILITY WALL again, on the candidates themselves. The roster's wall
  // does not cover this: `build_watches` is handed a roster it did not build,
  // and an out-of-session candidate whose watches all resolve to
  // CLOCK_UNAVAILABLE would otherwise be censused into the ledger as three
  // typed rows instead of refusing the session.
  for (const WatchCandidate& candidate : candidates) {
    const Expected<std::int64_t, Refusal> inside =
        refuse_unless_visible_in_session(clock, candidate.visible_ts_ns);
    if (!inside.has_value()) {
      return Expected<WatchPlan, Refusal>::refuse(inside.error());
    }
  }

  for (const WatchCandidate& candidate : candidates) {
    for (std::size_t stage_index = 0; stage_index < kWatchStageCount; ++stage_index) {
      const auto stage = static_cast<WatchStage>(stage_index);
      WatchRow row;
      row.candidate_id = candidate.candidate_id;
      row.candidate_physical_key = candidate.candidate_physical_key;
      row.policy_name = candidate.policy_name;
      row.reversal_bps = candidate.reversal_bps;
      row.member_count = candidate.member_count;
      row.visible_ts_ns = candidate.visible_ts_ns;
      row.side = candidate.side;
      row.stage = stage;

      const Expected<std::int64_t, Refusal> target =
          checked_add(candidate.visible_ts_ns, watch_stage_offset_ns(stage));
      if (!target.has_value()) {
        return Expected<WatchPlan, Refusal>::refuse(target.error());
      }
      // THE THREE RULES, verbatim from card section 3.
      std::int64_t second = kNoIndex;
      switch (stage) {
        case WatchStage::D0:
          second = clock.first_second_strictly_after(candidate.visible_ts_ns);
          break;
        case WatchStage::D30:
          second = clock.first_second_at_or_after(target.value());
          break;
        case WatchStage::D60:
          second = clock.last_second_at_or_before(target.value());
          break;
      }
      if (second != kNoIndex) {
        const Expected<std::int64_t, Refusal> ts = clock.second_ts(second);
        if (!ts.has_value()) {
          return Expected<WatchPlan, Refusal>::refuse(ts.error());
        }
        // D60 carries a SECOND condition — "still strictly after visibility" —
        // and a whole second at or before visibility is out of session for it.
        if (stage == WatchStage::D60 && ts.value() <= candidate.visible_ts_ns) {
          second = kNoIndex;
        } else {
          row.decision_second = second;
          row.decision_ts_ns = ts.value();
        }
      }
      if (second == kNoIndex) {
        row.clock_state = Validity::CLOCK_UNAVAILABLE;
        plan.census.watches_clock_unavailable += 1;
        plan.census.per_stage_clock_unavailable[stage_index] += 1;
        plan.ledger.push_back(std::move(row));
        continue;
      }

      // THE CARD'S IDENTITY, checked and not assumed.
      const Expected<std::int64_t, Refusal> offset =
          checked_mul(row.decision_second, kNanosecondsPerSecond);
      if (!offset.has_value()) {
        return Expected<WatchPlan, Refusal>::refuse(offset.error());
      }
      const Expected<std::int64_t, Refusal> rebuilt =
          checked_add(clock.session_start_ns(), offset.value());
      if (!rebuilt.has_value()) {
        return Expected<WatchPlan, Refusal>::refuse(rebuilt.error());
      }
      if (rebuilt.value() != row.decision_ts_ns) {
        return Expected<WatchPlan, Refusal>::refuse(Refusal(
            RefusalCode::CLOCK_VIOLATION, kWatchSite,
            "decision_ts_ns != session_start_ns + decision_second*1e9", row.decision_ts_ns));
      }
      // THE EXACT JOIN onto the authority roster.
      const Expected<std::int64_t, Refusal> ordinal = roster.ordinal_of(row.decision_ts_ns);
      if (!ordinal.has_value()) {
        return Expected<WatchPlan, Refusal>::refuse(ordinal.error());
      }
      row.decision_ordinal = ordinal.value();
      plan.census.watches_built += 1;
      plan.census.per_stage_built[stage_index] += 1;
      plan.ledger.push_back(std::move(row));
    }
  }

  // --- the ledger's total order -------------------------------------------
  std::sort(plan.ledger.begin(), plan.ledger.end(), [](const WatchRow& a, const WatchRow& b) {
    if (a.candidate_id != b.candidate_id) {
      return a.candidate_id < b.candidate_id;
    }
    return static_cast<std::uint8_t>(a.stage) < static_cast<std::uint8_t>(b.stage);
  });

  // --- the UNIQUE action rows ----------------------------------------------
  std::vector<std::pair<std::int64_t, std::int64_t>> keys;  // (ordinal, side sign)
  keys.reserve(plan.ledger.size());
  for (const WatchRow& row : plan.ledger) {
    if (row.clock_state != Validity::VALID) {
      continue;
    }
    keys.emplace_back(row.decision_ordinal, static_cast<std::int64_t>(row.side));
  }
  std::sort(keys.begin(), keys.end());
  keys.erase(std::unique(keys.begin(), keys.end()), keys.end());

  plan.actions.reserve(keys.size());
  for (const auto& [ordinal, side_sign] : keys) {
    ActionRow action;
    action.key.session_ordinal = session_ordinal;
    action.key.decision_ordinal = ordinal;
    action.key.decision_ts_ns = roster.ts_at(ordinal);
    action.key.side = static_cast<Side>(side_sign);
    const Expected<std::int64_t, Refusal> second = clock.second_of(action.key.decision_ts_ns);
    if (!second.has_value()) {
      return Expected<WatchPlan, Refusal>::refuse(second.error());
    }
    action.decision_second = second.value();
    plan.actions.push_back(action);
  }

  // --- bind every watch to its action and enforce the ONE-TO-ONE law -------
  for (WatchRow& row : plan.ledger) {
    if (row.clock_state != Validity::VALID) {
      continue;
    }
    const auto found = std::lower_bound(
        keys.begin(), keys.end(),
        std::pair<std::int64_t, std::int64_t>{row.decision_ordinal,
                                              static_cast<std::int64_t>(row.side)});
    if (found == keys.end() || found->first != row.decision_ordinal ||
        found->second != static_cast<std::int64_t>(row.side)) {
      return Expected<WatchPlan, Refusal>::refuse(
          Refusal(RefusalCode::CONTENT_MISMATCH, kWatchSite,
                  "a lawful watch has no action row", row.decision_ordinal));
    }
    const auto action_index = static_cast<std::int64_t>(found - keys.begin());
    ActionRow& action = plan.actions[static_cast<std::size_t>(action_index)];
    // THE ONE-TO-ONE LAW: "(session_ordinal,decision_ordinal,side) plus
    // timestamp must be one-to-one". A watch whose instant disagrees with the
    // instant its key already carries breaks it, and the whole session
    // refuses.
    if (action.key.decision_ts_ns != row.decision_ts_ns ||
        action.decision_second != row.decision_second) {
      return Expected<WatchPlan, Refusal>::refuse(
          Refusal(RefusalCode::CONTENT_MISMATCH, kWatchSite,
                  "one prediction key carries two different decision instants",
                  row.decision_ts_ns));
    }
    row.action_index = action_index;
    action.watch_count += 1;
    action.stage_mask = static_cast<std::uint8_t>(
        action.stage_mask | static_cast<std::uint8_t>(1U << static_cast<unsigned>(row.stage)));
  }
  // THE ONE-TO-ONE LAW, re-checked on the OUTPUT through its named primitive.
  const Expected<std::int64_t, Refusal> one_to_one = refuse_unless_one_to_one(plan.actions);
  if (!one_to_one.has_value()) {
    return Expected<WatchPlan, Refusal>::refuse(one_to_one.error());
  }

  plan.census.actions = static_cast<std::int64_t>(plan.actions.size());
  for (const ActionRow& action : plan.actions) {
    if (action.key.side == Side::LONG) {
      plan.census.actions_long += 1;
    } else {
      plan.census.actions_short += 1;
    }
    plan.census.converged_watches += action.watch_count - 1;
  }
  return plan;
}

std::string render_watch_ledger(const WatchPlan& plan) {
  std::string out =
      "candidate_id\tphysical_key\tpolicy_name\treversal_bps\tmember_count\tvisible_ts_ns\tside\t"
      "stage\tclock_state\tdecision_second\tdecision_ts_ns\tdecision_ordinal\taction_index\n";
  for (const WatchRow& row : plan.ledger) {
    out += row.candidate_id;
    out += '\t';
    out += row.candidate_physical_key;
    out += '\t';
    out += row.policy_name;
    out += '\t';
    out += std::to_string(row.reversal_bps);
    out += '\t';
    out += std::to_string(row.member_count);
    out += '\t';
    append_i64(out, row.visible_ts_ns);
    out += '\t';
    out += qr::replay::side_name(row.side);
    out += '\t';
    out += watch_stage_name(row.stage);
    out += '\t';
    out += validity_name(row.clock_state);
    out += '\t';
    append_i64(out, row.decision_second);
    out += '\t';
    append_i64(out, row.decision_ts_ns);
    out += '\t';
    append_i64(out, row.decision_ordinal);
    out += '\t';
    append_i64(out, row.action_index);
    out += '\n';
  }
  return out;
}

}  // namespace qr::labels
