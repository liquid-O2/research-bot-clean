// qr_m25/src/tape.cpp — DecisionTape -> ScoredAction rows, plus the TRAIN wall.
#include "qr_m25/tape.hpp"

#include <algorithm>
#include <fstream>
#include <sstream>

namespace qr::m25 {
namespace {

using qr::replay::kHorizonCount;
using qr::replay::LabelRow;
using qr::replay::LabelState;
using qr::replay::ScoredAction;
using qr::replay::Side;

Refusal mismatch(const char* site, const char* detail, std::int64_t context) noexcept {
  return Refusal(RefusalCode::CONTENT_MISMATCH, site, detail, context);
}

std::string shard_name(std::int64_t ordinal) {
  std::string digits = std::to_string(ordinal);
  while (digits.size() < 4) {
    digits.insert(digits.begin(), '0');
  }
  return "s" + digits;
}

/// One shard's truth leaves, mapped and checked against its manifest.
struct TruthLeaves {
  NpyArray keys;
  NpyArray feature_keys;
  NpyArray label_state;
  NpyArray entry_ts;
  NpyArray menu_net;
  NpyArray menu_mae;
  NpyArray menu_exit;
  NpyArray stop_hit;
  NpyArray gap_through;
  NpyArray cost_charged;
  std::int64_t rows = 0;
};

Expected<TruthLeaves, Refusal> load_truth(const std::filesystem::path& shard_dir,
                                          const TapeManifest& manifest) {
  TruthLeaves out;
  struct Binding {
    const char* rel;
    NpyArray* slot;
  };
  const Binding bindings[] = {
      {"truth/keys.npy", &out.keys},
      {"features/keys.npy", &out.feature_keys},
      {"truth/label_state.npy", &out.label_state},
      {"truth/entry_ts_ns.npy", &out.entry_ts},
      {"truth/menu_net_cent.npy", &out.menu_net},
      {"truth/menu_mae_cent.npy", &out.menu_mae},
      {"truth/menu_exit_ts.npy", &out.menu_exit},
      {"truth/stop_hit.npy", &out.stop_hit},
      {"truth/gap_through_cent.npy", &out.gap_through},
      {"truth/cost_charged_cent.npy", &out.cost_charged},
  };
  for (const Binding& binding : bindings) {
    Expected<NpyArray, Refusal> leaf = open_leaf(shard_dir, manifest, binding.rel);
    if (!leaf.has_value()) {
      return refuse<TruthLeaves>(leaf.error());
    }
    *binding.slot = std::move(leaf).value();
  }
  out.rows = out.keys.rows();
  const std::int64_t n = out.rows;
  if (out.keys.shape().size() != 2 || out.keys.shape()[1] != 4) {
    return refuse<TruthLeaves>(mismatch("qr_m25::load_truth", "truth/keys is not [N,4]", n));
  }
  const NpyArray* per_row[] = {&out.label_state, &out.entry_ts, &out.gap_through, &out.cost_charged};
  for (const NpyArray* leaf : per_row) {
    if (leaf->rows() != n) {
      return refuse<TruthLeaves>(mismatch("qr_m25::load_truth", "truth leaf row count disagrees",
                                          leaf->rows()));
    }
  }
  const NpyArray* per_menu[] = {&out.menu_net, &out.menu_mae, &out.menu_exit, &out.stop_hit};
  for (const NpyArray* leaf : per_menu) {
    if (leaf->rows() != n || leaf->shape().size() != 2 ||
        leaf->shape()[1] != static_cast<std::int64_t>(kHorizonCount)) {
      return refuse<TruthLeaves>(mismatch("qr_m25::load_truth", "menu leaf is not [N,7]", leaf->rows()));
    }
  }
  // The C4 join: features/keys and truth/keys are the SAME array in a lawful
  // shard. Checking it here is what makes "the label travels with its row" a
  // fact about the tape rather than an assumption of this loader.
  if (out.feature_keys.rows() != n) {
    return refuse<TruthLeaves>(mismatch("qr_m25::load_truth", "features/keys row count disagrees",
                                        out.feature_keys.rows()));
  }
  const std::span<const std::int64_t> tk = out.keys.i8();
  const std::span<const std::int64_t> fk = out.feature_keys.i8();
  if (tk.size() != fk.size() || !std::equal(tk.begin(), tk.end(), fk.begin())) {
    return refuse<TruthLeaves>(mismatch("qr_m25::load_truth",
                                        "features/keys and truth/keys are not the same array", n));
  }
  return out;
}

Status append_rows(const TruthLeaves& leaves, std::int64_t session_ordinal, SessionTape* tape) {
  const std::int64_t n = leaves.rows;
  const std::span<const std::int64_t> keys = leaves.keys.i8();
  const std::span<const std::uint8_t> state = leaves.label_state.u1();
  const std::span<const std::int64_t> entry = leaves.entry_ts.i8();
  const std::span<const std::int64_t> net = leaves.menu_net.i8();
  const std::span<const std::int64_t> mae = leaves.menu_mae.i8();
  const std::span<const std::int64_t> exit_ts = leaves.menu_exit.i8();
  const std::span<const std::uint8_t> stop = leaves.stop_hit.u1();
  const std::span<const std::int64_t> gap = leaves.gap_through.i8();
  const std::span<const std::int64_t> cost = leaves.cost_charged.i8();

  for (std::int64_t i = 0; i < n; ++i) {
    const std::size_t k = static_cast<std::size_t>(i) * 4;
    if (keys[k] != session_ordinal) {
      return Status::refuse(mismatch("qr_m25::append_rows", "key belongs to another session", keys[k]));
    }
    const std::int64_t side_value = keys[k + 3];
    if (side_value != 1 && side_value != -1) {
      return Status::refuse(mismatch("qr_m25::append_rows", "key side is neither +1 nor -1", side_value));
    }
    if (state[static_cast<std::size_t>(i)] > 2) {
      return Status::refuse(mismatch("qr_m25::append_rows", "label_state outside {OK,ENTRY,EXIT}",
                                     state[static_cast<std::size_t>(i)]));
    }
    ScoredAction action;
    action.key.session_ordinal = keys[k];
    action.key.decision_ordinal = keys[k + 1];
    action.key.decision_ts_ns = keys[k + 2];
    action.key.side = side_value == 1 ? Side::LONG : Side::SHORT;
    action.legal_enter = true;  // card section 6: legality is the authenticated
                                // watch and clock, and a published action row IS
                                // an authenticated watch at a lawful clock.
    LabelRow& label = action.label;
    label.key = action.key;
    label.state = static_cast<LabelState>(state[static_cast<std::size_t>(i)]);
    label.entry_ts_ns = entry[static_cast<std::size_t>(i)];
    label.gap_through_cent = gap[static_cast<std::size_t>(i)];
    label.cost_charged_cent = cost[static_cast<std::size_t>(i)];
    for (std::size_t h = 0; h < kHorizonCount; ++h) {
      const std::size_t at = static_cast<std::size_t>(i) * kHorizonCount + h;
      label.menu_net_cent[h] = net[at];
      label.menu_mae_cent[h] = mae[at];
      label.menu_exit_ts[h] = exit_ts[at];
      label.stop_hit[h] = stop[at];
    }
    switch (label.state) {
      case LabelState::OK: ++tape->label_ok_rows; break;
      case LabelState::ENTRY_UNAVAILABLE: ++tape->label_entry_unavailable_rows; break;
      case LabelState::EXIT_UNAVAILABLE: ++tape->label_exit_unavailable_rows; break;
    }
    if (action.key.side == Side::LONG) {
      ++tape->long_rows;
    } else {
      ++tape->short_rows;
    }
    tape->rows.push_back(action);
  }
  return ok();
}

}  // namespace

const char* fold_name(Fold fold) noexcept {
  switch (fold) {
    case Fold::F4: return "F4";
    case Fold::F5: return "F5";
  }
  return "UNKNOWN_FOLD";
}

bool parse_fold(const std::string& text, Fold* out) noexcept {
  if (text == "F4") { *out = Fold::F4; return true; }
  if (text == "F5") { *out = Fold::F5; return true; }
  return false;
}

TrainRange train_range(Fold fold) noexcept {
  switch (fold) {
    case Fold::F4: return TrainRange{125, 395};
    case Fold::F5: return TrainRange{125, 520};
  }
  return TrainRange{0, -1};
}

Status assert_train_session(Fold fold, std::int64_t session_ordinal) {
  const TrainRange range = train_range(fold);
  if (session_ordinal < range.first || session_ordinal > range.last) {
    return Status::refuse(Refusal(RefusalCode::ORDINAL_OUTSIDE_SCOPE, "qr_m25::assert_train_session",
                                  "session is not inside this fold's TRAIN range", session_ordinal));
  }
  return ok();
}

TapeRoot tape_root(const std::filesystem::path& run_dir) {
  return TapeRoot{run_dir / "tapes", run_dir / "receipts"};
}

Expected<std::string, Refusal> shard_card_sha(const TapeRoot& root, std::int64_t session_ordinal) {
  const std::filesystem::path dir = root.tapes / shard_name(session_ordinal) / "L";
  Expected<TapeManifest, Refusal> manifest = read_manifest(dir);
  if (!manifest.has_value()) {
    return refuse<std::string>(manifest.error());
  }
  if (manifest.value().card_sha256.empty()) {
    return refuse<std::string>(mismatch("qr_m25::shard_card_sha",
                                        "shard manifest carries no task_card_v4 census row",
                                        session_ordinal));
  }
  return manifest.value().card_sha256;
}

Expected<SessionTape, Refusal> load_session(const TapeRoot& root, Fold fold,
                                            std::int64_t session_ordinal) {
  if (Status wall = assert_train_session(fold, session_ordinal); !wall.has_value()) {
    return refuse<SessionTape>(wall.error());
  }

  SessionTape tape;
  tape.session_ordinal = session_ordinal;

  // The campaign session receipt carries the civil day; the year is the block
  // bootstrap's stratum label and nothing else reads it.
  {
    const std::filesystem::path receipt = root.receipts / "sessions" / (shard_name(session_ordinal) + ".tsv");
    std::ifstream in(receipt);
    if (!in) {
      return refuse<SessionTape>(Refusal(RefusalCode::IO, "qr_m25::load_session",
                                         "cannot open the campaign session receipt", session_ordinal));
    }
    std::string line;
    while (std::getline(in, line)) {
      std::stringstream stream(line);
      std::string section;
      std::string metric;
      std::string value;
      if (std::getline(stream, section, '\t') && std::getline(stream, metric, '\t') &&
          std::getline(stream, value, '\t') && section == "session" && metric == "day") {
        tape.day = value;
        break;
      }
    }
    if (tape.day.size() < 4) {
      return refuse<SessionTape>(Refusal(RefusalCode::MALFORMED_CIVIL_DATE, "qr_m25::load_session",
                                         "session receipt has no civil day", session_ordinal));
    }
    tape.year = static_cast<std::int32_t>(std::stoi(tape.day.substr(0, 4)));
  }

  for (const char* side_dir : {"L", "S"}) {
    const std::filesystem::path shard = root.tapes / shard_name(session_ordinal) / side_dir;
    Expected<TapeManifest, Refusal> manifest = read_manifest(shard);
    if (!manifest.has_value()) {
      return refuse<SessionTape>(manifest.error());
    }
    if (manifest.value().session_ordinal != session_ordinal) {
      return refuse<SessionTape>(mismatch("qr_m25::load_session",
                                          "shard manifest names another session",
                                          manifest.value().session_ordinal));
    }
    Expected<TruthLeaves, Refusal> leaves = load_truth(shard, manifest.value());
    if (!leaves.has_value()) {
      return refuse<SessionTape>(leaves.error());
    }
    if (Status appended = append_rows(leaves.value(), session_ordinal, &tape); !appended.has_value()) {
      return refuse<SessionTape>(appended.error());
    }
  }

  // ONE chronological stream. LONG before SHORT inside a clock is a stable
  // presentation order only: the kernel treats an equal-timestamp group as one
  // clock and its selection law is order-free (strict `>` for a new best, exact
  // equality for a tie).
  std::sort(tape.rows.begin(), tape.rows.end(),
            [](const ScoredAction& a, const ScoredAction& b) {
              if (a.key.decision_ts_ns != b.key.decision_ts_ns) {
                return a.key.decision_ts_ns < b.key.decision_ts_ns;
              }
              return static_cast<std::int64_t>(a.key.side) > static_cast<std::int64_t>(b.key.side);
            });

  for (std::size_t i = 0; i < tape.rows.size(); ++i) {
    if (i == 0 || tape.rows[i].key.decision_ts_ns != tape.rows[i - 1].key.decision_ts_ns) {
      tape.clock_starts.push_back(i);
    } else if (tape.rows[i].key.side == tape.rows[i - 1].key.side) {
      return refuse<SessionTape>(mismatch("qr_m25::load_session",
                                          "two rows share (timestamp, side) in one session",
                                          tape.rows[i].key.decision_ts_ns));
    }
  }
  return tape;
}

}  // namespace qr::m25
