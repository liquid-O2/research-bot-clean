#include "qr_labels/label_kernel.hpp"

#include <algorithm>
#include <array>

namespace qr::labels {
namespace {

constexpr const char* kScanSite = "qr_labels::stop_scan";
constexpr const char* kLabelSite = "qr_labels::label_action";
constexpr const char* kBarrierSite = "qr_labels::barrier_order";

constexpr std::array<const char*, kBarrierStateCount> kBarrierStateNames{
    "FAVORABLE_FIRST", "ADVERSE_FIRST", "SAME_GROUP_ADVERSE", "NEITHER"};
constexpr std::array<const char*, kBarrierClassCount> kBarrierClassNames{"FAVORABLE", "ADVERSE",
                                                                        "CENSORED"};

/// The first index in [lo,hi] whose column value crosses `gate`, or kNoIndex.
[[nodiscard]] std::int64_t first_crossing(const ExtremumIndex& column, std::int64_t lo,
                                          std::int64_t hi, const PriceGate& gate) {
  if (lo > hi) {
    return kNoIndex;
  }
  return gate.triggers_at_or_below ? column.first_at_or_below(lo, hi, gate.price_u6)
                                   : column.first_at_or_above(lo, hi, gate.price_u6);
}

/// The WORST adverse price over [lo,hi] — the one that minimises the marked
/// net. `mark_net_cent` is monotone increasing in a LONG bid and decreasing in
/// a SHORT ask, so the minimum net is the net of this one price and no scan of
/// the range's nets is needed.
[[nodiscard]] std::int64_t worst_adverse_price(const ExtremumIndex& adverse, std::int64_t lo,
                                               std::int64_t hi, Side side) {
  return side == Side::LONG ? adverse.range_min(lo, hi) : adverse.range_max(lo, hi);
}

/// The BEST adverse price over [lo,hi] and the EARLIEST index attaining it
/// ("tied maxima earliest").
[[nodiscard]] std::int64_t best_adverse_index(const ExtremumIndex& adverse, std::int64_t lo,
                                              std::int64_t hi, Side side) {
  return side == Side::LONG ? adverse.leftmost_argmax(lo, hi) : adverse.leftmost_argmin(lo, hi);
}

void append_i64(std::vector<std::uint8_t>& out, std::int64_t value) {
  const auto bits = static_cast<std::uint64_t>(value);
  for (std::size_t byte = 0; byte < sizeof(std::uint64_t); ++byte) {
    out.push_back(static_cast<std::uint8_t>((bits >> (8U * byte)) & 0xFFU));
  }
}

void append_metric(std::string& out, std::string_view label, std::string_view metric,
                   std::int64_t value) {
  out.append(label);
  out.push_back('\t');
  out.append(metric);
  out.push_back('\t');
  out.append(std::to_string(value));
  out.push_back('\n');
}

}  // namespace

const char* barrier_state_name(BarrierState state) noexcept {
  const auto index = static_cast<std::size_t>(state);
  return index < kBarrierStateNames.size() ? kBarrierStateNames[index] : "UNKNOWN";
}

const char* barrier_class_name(BarrierClass value) noexcept {
  const auto index = static_cast<std::size_t>(value);
  return index < kBarrierClassNames.size() ? kBarrierClassNames[index] : "UNKNOWN";
}

BarrierClass barrier_three_class(BarrierState state) noexcept {
  switch (state) {
    case BarrierState::FAVORABLE_FIRST:
      return BarrierClass::FAVORABLE;
    case BarrierState::ADVERSE_FIRST:
    case BarrierState::SAME_GROUP_ADVERSE:
      return BarrierClass::ADVERSE;
    case BarrierState::NEITHER:
      break;
  }
  return BarrierClass::CENSORED;
}

// ---------------------------------------------------------------------------
// stop_scan — THE shared primitive.
// ---------------------------------------------------------------------------

Expected<StopScan, Refusal> stop_scan(const SessionLabelIndex& index, std::int64_t entry_index,
                                      std::int64_t entry_u6, Side side,
                                      std::int64_t wall_net_cent) {
  const ExecutionTape& tape = index.tape();
  StopScan scan;
  scan.wall_net_cent = wall_net_cent;
  if (entry_index < 0 || entry_index >= tape.size()) {
    return Expected<StopScan, Refusal>::refuse(Refusal(
        RefusalCode::CONTENT_MISMATCH, kScanSite, "the entry index is off the tape", entry_index));
  }
  const std::int64_t first = entry_index + 1;
  const std::int64_t last = tape.size() - 1;
  if (first > last) {
    return scan;  // no lawful mark after the fill: nothing can be scanned
  }

  const Expected<PriceGate, Refusal> gate =
      price_gate_for_net(entry_u6, side, NetBound::AT_OR_BELOW, wall_net_cent);
  if (!gate.has_value()) {
    return Expected<StopScan, Refusal>::refuse(gate.error());
  }
  const std::int64_t crossing = first_crossing(index.adverse(side), first, last, gate.value());
  if (crossing == kNoIndex) {
    return scan;
  }

  // THE PRICE GATE IS AN ACCELERATOR, NEVER AN AUTHORITY. Both directions are
  // re-checked against the exact net: the crossing really crosses, and nothing
  // strictly before it did. A defect in the closed-form inversion therefore
  // refuses the session instead of quietly relabelling it.
  const Expected<std::int64_t, Refusal> crossing_net =
      mark_net_cent(entry_u6, tape.adverse_mark(crossing, side), side);
  if (!crossing_net.has_value()) {
    return Expected<StopScan, Refusal>::refuse(crossing_net.error());
  }
  if (crossing_net.value() > wall_net_cent) {
    return Expected<StopScan, Refusal>::refuse(
        Refusal(RefusalCode::CONTENT_MISMATCH, kScanSite,
                "the price gate reported a crossing whose exact net is above the wall",
                crossing_net.value()));
  }
  if (crossing > first) {
    const std::int64_t before =
        worst_adverse_price(index.adverse(side), first, crossing - 1, side);
    const Expected<std::int64_t, Refusal> before_net = mark_net_cent(entry_u6, before, side);
    if (!before_net.has_value()) {
      return Expected<StopScan, Refusal>::refuse(before_net.error());
    }
    if (before_net.value() <= wall_net_cent) {
      return Expected<StopScan, Refusal>::refuse(
          Refusal(RefusalCode::CONTENT_MISMATCH, kScanSite,
                  "an earlier mark crossed the wall than the price gate reported",
                  before_net.value()));
    }
  }

  scan.crossed = true;
  scan.crossing_index = crossing;
  scan.crossing_net_cent = crossing_net.value();
  // "the exit fills at the NEXT lawful mark strictly after crossing".
  scan.exit_index = crossing + 1 <= last ? crossing + 1 : kNoIndex;
  const std::int64_t fill_index = scan.exit_index != kNoIndex ? scan.exit_index : crossing;
  const Expected<std::int64_t, Refusal> exit_net =
      mark_net_cent(entry_u6, tape.adverse_mark(fill_index, side), side);
  if (!exit_net.has_value()) {
    return Expected<StopScan, Refusal>::refuse(exit_net.error());
  }
  scan.exit_net_cent = exit_net.value();
  scan.crossing_ts_ns = tape.ts_ns[static_cast<std::size_t>(crossing)];
  scan.exit_ts_ns = tape.ts_ns[static_cast<std::size_t>(fill_index)];
  // "gap-through retained and reported": how far past the wall the FILL landed.
  scan.gap_through_cent = exit_net.value() < wall_net_cent ? wall_net_cent - exit_net.value() : 0;
  return scan;
}

// ---------------------------------------------------------------------------
// barrier_order
// ---------------------------------------------------------------------------

Expected<BarrierOutcome, Refusal> barrier_order(const SessionLabelIndex& index,
                                                std::int64_t entry_index, Side side,
                                                std::int64_t favorable_net_cent,
                                                std::int64_t adverse_net_cent) {
  const ExecutionTape& tape = index.tape();
  BarrierOutcome out;
  if (entry_index < 0 || entry_index >= tape.size()) {
    return Expected<BarrierOutcome, Refusal>::refuse(
        Refusal(RefusalCode::CONTENT_MISMATCH, kBarrierSite, "the entry index is off the tape",
                entry_index));
  }
  const std::int64_t entry_u6 = tape.entry_price(entry_index, side);
  const std::int64_t first = entry_index + 1;
  const std::int64_t last = tape.size() - 1;  // "scanned over full RTH"
  if (first > last) {
    return out;  // NEITHER: there is no mark to touch either barrier
  }

  // The FAVORABLE barrier reads the favorable extremum (bid_max LONG /
  // ask_min SHORT) and the ADVERSE barrier the adverse one (bid_min / ask_max).
  // Two different columns of the same millisecond is exactly what makes
  // SAME_GROUP_ADVERSE reachable — one conservative mark per group could never
  // touch both barriers at once, and the card enumerates that state.
  const Expected<PriceGate, Refusal> favorable_gate =
      price_gate_for_net(entry_u6, side, NetBound::AT_OR_ABOVE, favorable_net_cent);
  if (!favorable_gate.has_value()) {
    return Expected<BarrierOutcome, Refusal>::refuse(favorable_gate.error());
  }
  const Expected<PriceGate, Refusal> adverse_gate =
      price_gate_for_net(entry_u6, side, NetBound::AT_OR_BELOW, adverse_net_cent);
  if (!adverse_gate.has_value()) {
    return Expected<BarrierOutcome, Refusal>::refuse(adverse_gate.error());
  }

  out.favorable_index = first_crossing(index.favorable(side), first, last, favorable_gate.value());
  out.adverse_index = first_crossing(index.adverse(side), first, last, adverse_gate.value());

  if (out.favorable_index != kNoIndex) {
    const Expected<std::int64_t, Refusal> net =
        mark_net_cent(entry_u6, tape.favorable_mark(out.favorable_index, side), side);
    if (!net.has_value()) {
      return Expected<BarrierOutcome, Refusal>::refuse(net.error());
    }
    if (net.value() < favorable_net_cent) {
      return Expected<BarrierOutcome, Refusal>::refuse(
          Refusal(RefusalCode::CONTENT_MISMATCH, kBarrierSite,
                  "the favorable price gate reported a touch whose exact net is below it",
                  net.value()));
    }
  }
  if (out.adverse_index != kNoIndex) {
    const Expected<std::int64_t, Refusal> net =
        mark_net_cent(entry_u6, tape.adverse_mark(out.adverse_index, side), side);
    if (!net.has_value()) {
      return Expected<BarrierOutcome, Refusal>::refuse(net.error());
    }
    if (net.value() > adverse_net_cent) {
      return Expected<BarrierOutcome, Refusal>::refuse(
          Refusal(RefusalCode::CONTENT_MISMATCH, kBarrierSite,
                  "the adverse price gate reported a touch whose exact net is above it",
                  net.value()));
    }
  }

  if (out.favorable_index == kNoIndex && out.adverse_index == kNoIndex) {
    out.state = BarrierState::NEITHER;
  } else if (out.adverse_index == kNoIndex) {
    out.state = BarrierState::FAVORABLE_FIRST;
  } else if (out.favorable_index == kNoIndex) {
    out.state = BarrierState::ADVERSE_FIRST;
  } else if (out.favorable_index < out.adverse_index) {
    out.state = BarrierState::FAVORABLE_FIRST;
  } else if (out.adverse_index < out.favorable_index) {
    out.state = BarrierState::ADVERSE_FIRST;
  } else {
    // "same-group ties map to ADVERSE_FIRST" — the raw state records that the
    // tie happened, and the three-class map does the folding.
    out.state = BarrierState::SAME_GROUP_ADVERSE;
  }
  out.three_class = barrier_three_class(out.state);

  std::int64_t first_touch = kNoIndex;
  if (out.favorable_index != kNoIndex && out.adverse_index != kNoIndex) {
    first_touch = std::min(out.favorable_index, out.adverse_index);
  } else if (out.favorable_index != kNoIndex) {
    first_touch = out.favorable_index;
  } else if (out.adverse_index != kNoIndex) {
    first_touch = out.adverse_index;
  }
  out.first_touch_ts_ns =
      first_touch == kNoIndex ? 0 : tape.ts_ns[static_cast<std::size_t>(first_touch)];
  return out;
}

// ---------------------------------------------------------------------------
// label_action
// ---------------------------------------------------------------------------

namespace {

/// The MAE over the CLOSED interval [entry_index, exit_index], in net cents:
/// `max(0, -min net)`.
[[nodiscard]] Expected<std::int64_t, Refusal> mae_cent(const SessionLabelIndex& index,
                                                       std::int64_t entry_index,
                                                       std::int64_t exit_index,
                                                       std::int64_t entry_u6, Side side) {
  const std::int64_t worst =
      worst_adverse_price(index.adverse(side), entry_index, exit_index, side);
  const Expected<std::int64_t, Refusal> worst_net = mark_net_cent(entry_u6, worst, side);
  if (!worst_net.has_value()) {
    return Expected<std::int64_t, Refusal>::refuse(worst_net.error());
  }
  return worst_net.value() < 0 ? -worst_net.value() : 0;
}

}  // namespace

Expected<LabelRow, Refusal> label_action(const SessionLabelIndex& index, ActionKey key, Side side,
                                         std::int64_t wall_net_cent) {
  const ExecutionTape& tape = index.tape();
  LabelRow row;
  row.menu.key = key;
  row.menu.cost_charged_cent = kTradeCostCent;
  if (key.side != side) {
    return Expected<LabelRow, Refusal>::refuse(
        Refusal(RefusalCode::CONTENT_MISMATCH, kLabelSite,
                "the action key's side is not the side being labelled",
                static_cast<std::int64_t>(side)));
  }

  // --- the entry rule ------------------------------------------------------
  const std::int64_t entry_index = tape.first_strictly_after(key.decision_ts_ns);
  if (entry_index == kNoIndex) {
    row.menu.state = LabelState::ENTRY_UNAVAILABLE;
    return row;
  }
  row.entry_index = entry_index;
  row.menu.entry_ts_ns = tape.ts_ns[static_cast<std::size_t>(entry_index)];
  const std::int64_t entry_u6 = tape.entry_price(entry_index, side);
  row.entry_u6 = entry_u6;
  if (entry_u6 <= 0) {
    return Expected<LabelRow, Refusal>::refuse(
        Refusal(RefusalCode::CONTENT_MISMATCH, kLabelSite,
                "an eligible group produced a non-positive fill price", entry_u6));
  }
  const std::int64_t last = tape.size() - 1;
  if (entry_index >= last) {
    // Filled on the session's final lawful mark: there is no mark to exit at.
    row.menu.state = LabelState::EXIT_UNAVAILABLE;
    return row;
  }

  // --- THE ONE SHARED SCAN -------------------------------------------------
  const Expected<StopScan, Refusal> scan =
      stop_scan(index, entry_index, entry_u6, side, wall_net_cent);
  if (!scan.has_value()) {
    return Expected<LabelRow, Refusal>::refuse(scan.error());
  }
  row.scan = scan.value();
  // The truth column the ECONOMIC replay reads. The scan is shared across all
  // seven horizons, so its gap-through is one scalar on the row and not a
  // per-horizon array; card section 6's breach panel is `stop_hit[h] AND
  // gap_through_cent > 0`, and without this line the replay would be left with
  // the forbidden MAE threshold as its only wall evidence.
  row.menu.gap_through_cent = row.scan.gap_through_cent;

  // --- the seven-horizon executable menu -----------------------------------
  for (std::size_t horizon = 0; horizon < kHorizonCount; ++horizon) {
    std::int64_t horizon_index = last;  // "close => final eligible group"
    if (kHorizonMinutes[horizon] >= 0) {
      const Expected<std::int64_t, Refusal> offset =
          checked_mul(kHorizonMinutes[horizon], kNanosecondsPerMinute);
      if (!offset.has_value()) {
        return Expected<LabelRow, Refusal>::refuse(offset.error());
      }
      const Expected<std::int64_t, Refusal> deadline =
          checked_add(row.menu.entry_ts_ns, offset.value());
      if (!deadline.has_value()) {
        return Expected<LabelRow, Refusal>::refuse(deadline.error());
      }
      const std::int64_t found = tape.first_at_or_after(deadline.value());
      // A horizon that runs past the session's last lawful mark exits there,
      // exactly as `close` does (see the header's declared reading).
      horizon_index = found == kNoIndex ? last : found;
    }

    std::int64_t exit_index = horizon_index;
    bool stopped = false;
    if (row.scan.crossed && row.scan.crossing_index < horizon_index) {
      // "stop before h": the crossing is STRICTLY before this horizon's exit,
      // so the fill is the next lawful mark after the crossing — which exists,
      // because the horizon's own group is one.
      if (row.scan.exit_index == kNoIndex) {
        return Expected<LabelRow, Refusal>::refuse(
            Refusal(RefusalCode::CONTENT_MISMATCH, kLabelSite,
                    "a stop fired before a horizon but no lawful mark follows the crossing",
                    row.scan.crossing_index));
      }
      exit_index = row.scan.exit_index;
      stopped = true;
    }

    const Expected<std::int64_t, Refusal> net =
        mark_net_cent(entry_u6, tape.adverse_mark(exit_index, side), side);
    if (!net.has_value()) {
      return Expected<LabelRow, Refusal>::refuse(net.error());
    }
    const Expected<std::int64_t, Refusal> mae =
        mae_cent(index, entry_index, exit_index, entry_u6, side);
    if (!mae.has_value()) {
      return Expected<LabelRow, Refusal>::refuse(mae.error());
    }
    row.menu.menu_net_cent[horizon] = net.value();
    row.menu.menu_mae_cent[horizon] = mae.value();
    row.menu.menu_exit_ts[horizon] = tape.ts_ns[static_cast<std::size_t>(exit_index)];
    row.menu.stop_hit[horizon] = stopped ? 1U : 0U;
  }

  // --- the co-primary certificate ------------------------------------------
  // "the uncapped best positive executable mark BEFORE the first net
  // -30,000-cent adverse wall, otherwise the wall or final eligible group".
  const std::int64_t window_hi = row.scan.crossed ? row.scan.crossing_index - 1 : last;
  std::int64_t certificate_index = kNoIndex;
  if (entry_index + 1 <= window_hi) {
    const std::int64_t best = best_adverse_index(index.adverse(side), entry_index + 1, window_hi,
                                                 side);
    const Expected<std::int64_t, Refusal> best_net =
        mark_net_cent(entry_u6, tape.adverse_mark(best, side), side);
    if (!best_net.has_value()) {
      return Expected<LabelRow, Refusal>::refuse(best_net.error());
    }
    if (best_net.value() > 0) {
      certificate_index = best;
    }
  }
  if (certificate_index == kNoIndex) {
    // No positive pre-wall mark: the wall if there is one, else the final
    // lawful mark. "Never exit at entry merely because entry is maximum" is
    // structural here — the search never includes the entry group.
    certificate_index = row.scan.crossed
                            ? (row.scan.exit_index != kNoIndex ? row.scan.exit_index : last)
                            : last;
  }
  const Expected<std::int64_t, Refusal> certificate_net =
      mark_net_cent(entry_u6, tape.adverse_mark(certificate_index, side), side);
  if (!certificate_net.has_value()) {
    return Expected<LabelRow, Refusal>::refuse(certificate_net.error());
  }
  const Expected<std::int64_t, Refusal> certificate_mae =
      mae_cent(index, entry_index, certificate_index, entry_u6, side);
  if (!certificate_mae.has_value()) {
    return Expected<LabelRow, Refusal>::refuse(certificate_mae.error());
  }
  row.certificate_exit_index = certificate_index;
  row.certificate_exit_ts_ns = tape.ts_ns[static_cast<std::size_t>(certificate_index)];
  row.certificate_net_cent = certificate_net.value();
  row.certificate_mae_cent = certificate_mae.value();

  // --- the barrier auxiliary -----------------------------------------------
  const Expected<BarrierOutcome, Refusal> barrier =
      barrier_order(index, entry_index, side, kBarrierNetCent, -kBarrierNetCent);
  if (!barrier.has_value()) {
    return Expected<LabelRow, Refusal>::refuse(barrier.error());
  }
  row.barrier = barrier.value();
  row.menu.state = LabelState::OK;
  return row;
}

Expected<std::vector<LabelRow>, Refusal> label_session(const SessionLabelIndex& index,
                                                       std::span<const ActionRow> actions,
                                                       std::int64_t wall_net_cent) {
  std::vector<LabelRow> rows;
  rows.reserve(actions.size());
  for (const ActionRow& action : actions) {
    Expected<LabelRow, Refusal> row =
        label_action(index, action.key, action.key.side, wall_net_cent);
    if (!row.has_value()) {
      return Expected<std::vector<LabelRow>, Refusal>::refuse(row.error());
    }
    rows.push_back(std::move(row).value());
  }
  return rows;
}

// ---------------------------------------------------------------------------
// census + rendering
// ---------------------------------------------------------------------------

void LabelCensus::observe(const LabelRow& row) {
  rows += 1;
  per_state[static_cast<std::size_t>(row.menu.state)] += 1;
  for (std::size_t horizon = 0; horizon < kHorizonCount; ++horizon) {
    if (row.menu.stop_hit[horizon] != 0U) {
      stop_hit[horizon] += 1;
    }
  }
  barrier_state[static_cast<std::size_t>(row.barrier.state)] += 1;
  if (row.scan.gap_through_cent > 0) {
    gap_through_rows += 1;
  }
  if (row.menu.state == LabelState::OK && row.certificate_net_cent > 0) {
    certificate_positive_rows += 1;
  }
}

std::string LabelCensus::to_tsv(std::string_view label) const {
  std::string out = "label\tmetric\tvalue\n";
  append_metric(out, label, "rows", rows);
  for (std::size_t state = 0; state < per_state.size(); ++state) {
    std::string metric = "state_";
    metric += qr::replay::label_state_name(static_cast<LabelState>(state));
    append_metric(out, label, metric, per_state[state]);
  }
  for (std::size_t horizon = 0; horizon < kHorizonCount; ++horizon) {
    std::string metric = "stop_hit_h";
    metric += std::to_string(kHorizonMinutes[horizon]);
    append_metric(out, label, metric, stop_hit[horizon]);
  }
  for (std::size_t state = 0; state < kBarrierStateCount; ++state) {
    std::string metric = "barrier_";
    metric += barrier_state_name(static_cast<BarrierState>(state));
    append_metric(out, label, metric, barrier_state[state]);
  }
  append_metric(out, label, "gap_through_rows", gap_through_rows);
  append_metric(out, label, "certificate_positive_rows", certificate_positive_rows);
  return out;
}

void append_serialized(const LabelRow& row, std::vector<std::uint8_t>& out) {
  append_i64(out, row.menu.key.session_ordinal);
  append_i64(out, row.menu.key.decision_ordinal);
  append_i64(out, row.menu.key.decision_ts_ns);
  append_i64(out, static_cast<std::int64_t>(row.menu.key.side));
  append_i64(out, static_cast<std::int64_t>(row.menu.state));
  append_i64(out, row.menu.entry_ts_ns);
  append_i64(out, row.entry_u6);
  for (std::size_t horizon = 0; horizon < kHorizonCount; ++horizon) {
    append_i64(out, row.menu.menu_net_cent[horizon]);
    append_i64(out, row.menu.menu_mae_cent[horizon]);
    append_i64(out, row.menu.menu_exit_ts[horizon]);
    append_i64(out, static_cast<std::int64_t>(row.menu.stop_hit[horizon]));
  }
  append_i64(out, row.menu.cost_charged_cent);
  append_i64(out, row.certificate_net_cent);
  append_i64(out, row.certificate_mae_cent);
  append_i64(out, row.certificate_exit_ts_ns);
  append_i64(out, static_cast<std::int64_t>(row.barrier.state));
  append_i64(out, static_cast<std::int64_t>(row.barrier.three_class));
  append_i64(out, row.barrier.first_touch_ts_ns);
  append_i64(out, row.scan.crossed ? 1 : 0);
  append_i64(out, row.scan.gap_through_cent);
}

std::string render_label_rows(std::span<const LabelRow> rows) {
  std::string out =
      "session_ordinal\tdecision_ordinal\tdecision_ts_ns\tside\tstate\tentry_ts_ns\tentry_u6\t"
      "cost_charged_cent";
  for (std::size_t horizon = 0; horizon < kHorizonCount; ++horizon) {
    const std::string suffix =
        kHorizonMinutes[horizon] >= 0 ? std::to_string(kHorizonMinutes[horizon]) + "m" : "close";
    out += "\tnet_" + suffix + "\tmae_" + suffix + "\texit_ts_" + suffix + "\tstop_" + suffix;
  }
  out +=
      "\tcertificate_net_cent\tcertificate_mae_cent\tcertificate_exit_ts_ns\tbarrier_state\t"
      "barrier_class\tbarrier_first_touch_ts_ns\tstop_crossed\tstop_crossing_ts_ns\t"
      "stop_gap_through_cent\n";
  for (const LabelRow& row : rows) {
    out += std::to_string(row.menu.key.session_ordinal);
    out += '\t';
    out += std::to_string(row.menu.key.decision_ordinal);
    out += '\t';
    out += std::to_string(row.menu.key.decision_ts_ns);
    out += '\t';
    out += qr::replay::side_name(row.menu.key.side);
    out += '\t';
    out += qr::replay::label_state_name(row.menu.state);
    out += '\t';
    out += std::to_string(row.menu.entry_ts_ns);
    out += '\t';
    out += std::to_string(row.entry_u6);
    out += '\t';
    out += std::to_string(row.menu.cost_charged_cent);
    for (std::size_t horizon = 0; horizon < kHorizonCount; ++horizon) {
      out += '\t';
      out += std::to_string(row.menu.menu_net_cent[horizon]);
      out += '\t';
      out += std::to_string(row.menu.menu_mae_cent[horizon]);
      out += '\t';
      out += std::to_string(row.menu.menu_exit_ts[horizon]);
      out += '\t';
      out += std::to_string(static_cast<std::int64_t>(row.menu.stop_hit[horizon]));
    }
    out += '\t';
    out += std::to_string(row.certificate_net_cent);
    out += '\t';
    out += std::to_string(row.certificate_mae_cent);
    out += '\t';
    out += std::to_string(row.certificate_exit_ts_ns);
    out += '\t';
    out += barrier_state_name(row.barrier.state);
    out += '\t';
    out += barrier_class_name(row.barrier.three_class);
    out += '\t';
    out += std::to_string(row.barrier.first_touch_ts_ns);
    out += '\t';
    out += row.scan.crossed ? "1" : "0";
    out += '\t';
    out += std::to_string(row.scan.crossing_ts_ns);
    out += '\t';
    out += std::to_string(row.scan.gap_through_cent);
    out += '\n';
  }
  return out;
}

}  // namespace qr::labels
