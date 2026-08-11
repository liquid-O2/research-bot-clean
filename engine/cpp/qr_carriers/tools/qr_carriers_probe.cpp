// qr_carriers_probe — the authorized WP8a session-125 construction run.
//
// WP8a brief, REAL-FILE CHECK (payload read authorized for this work package on
// EXACTLY these three already-opened s125 streams and no others):
//   /workspace/data/tokens/stock_quotes/IWM/2022/2022-07-05.parquet
//   /workspace/data/tokens/stock_trades/IWM/2022/2022-07-05.parquet
//   /workspace/data/tokens/options_prints/IWM/2022/2022-07-05.parquet
// "build all three modality channel streams + DIRECT_RAW 60-col rows + location
//  values + candidate-set rows for the s125 watch roster ...; report
//  per-modality channel presence censuses (printed in full), DIRECT column count
//  assertion (exactly 60), grid stats; two-run byte identity; wall/RSS."
//
// WHERE THE DECISIONS COME FROM. The brief authorizes "decisions = D0 watches
// from the roster directly". D0's law is section 3's, applied verbatim: the
// first registered whole-second clock STRICTLY after a candidate's own
// visibility, with `decision_ts_ns = session_start_ns + decision_second*1e9`.
// The AUTHORITY ORDINAL is deliberately NOT derived here — it is the sealed
// authority clock roster's answer and belongs to WP7's watch builder; this probe
// keys on (decision_second, side), which is one-to-one with the instant inside
// one session and is all a feature-construction receipt needs.
//
// THE ROSTER IS READ, NEVER DERIVED. `--roster` takes the `roster.tsv` that
// qr_candidates_seal publishes: WP6 is the roster authority and a second
// derivation here would be a second authority on the same question.
//
// NOTHING IS EMITTED. WP8a builds and censuses; the .npy/manifest emission is
// WP10's. The probe writes only its own receipt TSV, whose two-run byte identity
// is the determinism proof.
#include <algorithm>
#include <chrono>
#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#include "qr_carriers/candidate_set.hpp"
#include "qr_carriers/direct_raw.hpp"
#include "qr_carriers/grid_1s.hpp"
#include "qr_carriers/location.hpp"
#include "qr_carriers/streams.hpp"
#include "qr_nbbo/group_machine.hpp"
#include "qr_sources/option_prints.hpp"
#include "qr_sources/stock_quotes.hpp"
#include "qr_sources/stock_trades.hpp"

namespace {

using qr::carriers::CandidateRelation;
using qr::carriers::DecisionWindow;
using qr::carriers::DirectRawBuilder;
using qr::carriers::GroupRecord;
using qr::carriers::LocationBuilder;
using qr::carriers::LocationInputs;
using qr::carriers::MidpointGrid;
using qr::carriers::Modality;
using qr::carriers::NbboStream;
using qr::carriers::OptionPrintStream;
using qr::carriers::Side;
using qr::carriers::StockPrintStream;
using qr::carriers::VisibleCandidate;

/// One roster row, as `qr_candidates::render_roster` writes it.
struct RosterRow {
  std::string candidate_id;
  std::string policy_name;
  std::int64_t reversal_bps = 0;
  std::int64_t visible_ts_ns = 0;
  std::int64_t member_count = 0;
  Side side = Side::LONG;
  bool side_available = false;
  /// SIDE_UNAVAILABLE because the members DISAGREED, as opposed to any other
  /// cause — the card keeps the two apart and so does the relation one-hot.
  bool mixed_members = false;
};

/// One D0 action row: the unique (decision_second, side) key.
struct ActionRow {
  std::int64_t decision_second = 0;
  Side side = Side::LONG;
  std::int64_t decision_ts_ns = 0;
  std::int64_t watch_count = 0;
  /// The newest SAME-SIDE authorizing visibility at this decision.
  std::int64_t phase_reference_ns = 0;
  bool phase_reference_present = false;
};

[[noreturn]] void die(const std::string& message) {
  std::fprintf(stderr, "REFUSED: %s\n", message.c_str());
  std::exit(1);
}

const qr::Registry& registry() {
  static const qr::Registry loaded = [] {
    auto result = qr::Registry::load_embedded();
    if (!result.has_value()) {
      die("the embedded registry failed its digest gate");
    }
    return std::move(result).value();
  }();
  return loaded;
}

std::vector<RosterRow> read_roster(const std::string& path, std::int64_t ordinal) {
  std::ifstream input(path);
  if (!input) {
    die("cannot open the roster TSV at " + path);
  }
  std::vector<RosterRow> rows;
  std::string line;
  bool header = true;
  while (std::getline(input, line)) {
    if (header) {
      header = false;
      continue;
    }
    if (line.empty()) {
      continue;
    }
    std::vector<std::string> field;
    std::string cell;
    std::istringstream stream(line);
    while (std::getline(stream, cell, '\t')) {
      field.push_back(cell);
    }
    if (field.size() < 11) {
      die("a roster row has fewer than the eleven published columns");
    }
    if (std::strtoll(field[0].c_str(), nullptr, 10) != ordinal) {
      continue;
    }
    RosterRow row;
    row.candidate_id = field[2];
    row.policy_name = field[3];
    row.reversal_bps = std::strtoll(field[4].c_str(), nullptr, 10);
    row.visible_ts_ns = std::strtoll(field[5].c_str(), nullptr, 10);
    row.member_count = std::strtoll(field[6].c_str(), nullptr, 10);
    if (field[8] == "LONG") {
      row.side = Side::LONG;
      row.side_available = true;
    } else if (field[8] == "SHORT") {
      row.side = Side::SHORT;
      row.side_available = true;
    }
    row.mixed_members = field[9] == "MIXED_MEMBER_SIDE";
    rows.push_back(std::move(row));
  }
  return rows;
}

/// Peak resident set, in KiB, from the kernel rather than from a guess.
std::int64_t peak_rss_kib() {
  std::ifstream status("/proc/self/status");
  std::string line;
  while (std::getline(status, line)) {
    if (line.rfind("VmHWM:", 0) == 0) {
      return std::strtoll(line.c_str() + 6, nullptr, 10);
    }
  }
  return -1;
}

double seconds_since(std::chrono::steady_clock::time_point start) {
  return std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
}

/// The receipt: a deterministic `section<TAB>metric<TAB>value` TSV. NO TIMINGS
/// go in it — the two-run byte-identity comparison is on this file.
class Receipt {
 public:
  void add(const std::string& section, const std::string& metric, std::int64_t value) {
    char buffer[64];
    std::snprintf(buffer, sizeof(buffer), "%" PRId64, value);
    rows_.push_back(section + "\t" + metric + "\t" + buffer);
  }
  void add_text(const std::string& section, const std::string& metric, const std::string& value) {
    rows_.push_back(section + "\t" + metric + "\t" + value);
  }
  void write(const std::string& path) const {
    std::FILE* out = std::fopen(path.c_str(), "wb");
    if (out == nullptr) {
      die("cannot write the receipt at " + path);
    }
    const std::string header = "section\tmetric\tvalue\n";
    std::fwrite(header.data(), 1, header.size(), out);
    for (const std::string& row : rows_) {
      std::fwrite(row.data(), 1, row.size(), out);
      std::fputc('\n', out);
    }
    std::fclose(out);
  }
  void print() const {
    for (const std::string& row : rows_) {
      std::printf("%s\n", row.c_str());
    }
  }

 private:
  std::vector<std::string> rows_;
};

/// FNV-1a over the constructed feature bytes: the ONE number whose equality
/// across two runs proves the whole construction is deterministic.
class Fingerprint {
 public:
  void feed(double value) {
    std::uint64_t bits = 0;
    std::memcpy(&bits, &value, sizeof(bits));
    feed(static_cast<std::int64_t>(bits));
  }
  void feed(std::int64_t value) {
    auto bits = static_cast<std::uint64_t>(value);
    for (unsigned shift = 0; shift < 64; shift += 8) {
      digest_ ^= (bits >> shift) & 0xFFULL;
      digest_ *= 0x100000001B3ULL;
    }
  }
  void feed(qr::Validity validity) { feed(static_cast<std::int64_t>(validity)); }
  [[nodiscard]] std::uint64_t value() const { return digest_; }

 private:
  std::uint64_t digest_ = 0xCBF29CE484222325ULL;
};

template <std::size_t N>
void census_rows(Receipt& receipt, const std::string& section,
                 const qr::carriers::ChannelCensus<N>& census,
                 const char* (*name)(std::size_t)) {
  receipt.add(section, "tokens", census.tokens);
  for (std::size_t channel = 0; channel < N; ++channel) {
    receipt.add(section, std::string("present.") + name(channel), census.present[channel]);
  }
}

int usage() {
  std::fprintf(stderr,
               "usage: qr_carriers_probe --quotes DIR --trades DIR --options DIR --roster TSV "
               "[--ordinal N] [--tsv PATH]\n"
               "       qr_carriers_probe --conditions-only --trades DIR [--ordinal N] "
               "[--tsv PATH]\n");
  return 2;
}

}  // namespace

int main(int argc, char** argv) {
  std::string quotes_root;
  std::string trades_root;
  std::string options_root;
  std::string roster_path;
  std::string tsv_path;
  std::int64_t ordinal = 125;
  // Stock-trades-only mode: the condition census the sentinel ruling needs, on a
  // session whose other two streams this work package has no business opening.
  bool conditions_only = false;
  for (int index = 1; index < argc; ++index) {
    const std::string flag = argv[index];
    const bool has_value = index + 1 < argc;
    if (flag == "--quotes" && has_value) {
      quotes_root = argv[++index];
    } else if (flag == "--trades" && has_value) {
      trades_root = argv[++index];
    } else if (flag == "--options" && has_value) {
      options_root = argv[++index];
    } else if (flag == "--roster" && has_value) {
      roster_path = argv[++index];
    } else if (flag == "--tsv" && has_value) {
      tsv_path = argv[++index];
    } else if (flag == "--ordinal" && has_value) {
      ordinal = std::strtoll(argv[++index], nullptr, 10);
    } else if (flag == "--conditions-only") {
      conditions_only = true;
    } else {
      return usage();
    }
  }
  if (trades_root.empty()) {
    return usage();
  }
  if (!conditions_only &&
      (quotes_root.empty() || options_root.empty() || roster_path.empty())) {
    return usage();
  }

  const auto scope = qr::DayScope::admit(registry(), ordinal);
  if (!scope.has_value()) {
    die(scope.error().message());
  }
  auto clock = qr::SessionClock::from_session(scope.value().session());
  if (!clock.has_value()) {
    die(clock.error().message());
  }
  const qr::SessionClock session_clock = clock.value();
  const std::int64_t session_start_ns = session_clock.session_start_a().ns();
  const std::int64_t session_end_ns = session_clock.session_end_a().ns();

  Receipt receipt;
  receipt.add_text("session", "day", scope.value().day());
  receipt.add("session", "ordinal", ordinal);
  receipt.add("session", "expected_bar_count", session_clock.expected_bar_count());

  const auto wall_start = std::chrono::steady_clock::now();

  // --- 1. the three modality channel streams ---------------------------------
  double nbbo_seconds = 0.0;
  NbboStream nbbo(session_clock);
  if (!conditions_only) {
    const auto start = std::chrono::steady_clock::now();
    auto opened = qr::sources::StockQuoteReader::open(scope.value(), quotes_root,
                                                      scope.value().profile());
    if (!opened.has_value()) {
      die(opened.error().refusal().message());
    }
    qr::sources::StockQuoteReader reader = std::move(opened).value();
    qr::sources::StockQuoteReader::Group group;
    for (;;) {
      auto more = reader.next_group(group);
      if (!more.has_value()) {
        die(more.error().refusal().message());
      }
      if (!more.value()) {
        break;
      }
      const auto pushed = nbbo.push_group(group.ts_ms_b, group.rows);
      if (!pushed.has_value()) {
        die(pushed.error().message());
      }
    }
    nbbo_seconds = seconds_since(start);
    receipt.add("stock_nbbo", "reader_rth_rows", reader.rth_rows());
    receipt.add("stock_nbbo", "reader_group_count", reader.group_count());
    receipt.add("stock_nbbo", "carrier_group_count",
                static_cast<std::int64_t>(nbbo.groups().size()));
    receipt.add("stock_nbbo", "eligible_midpoint_groups",
                static_cast<std::int64_t>(nbbo.eligible_midpoints().size()));
  }

  double trades_seconds = 0.0;
  // The card's "stricter reader censuses ... full typed-state histograms per
  // probe session, printed in full": every primary and extended condition code
  // the session actually carries, so the eligibility contract is auditable
  // against the tape rather than assumed.
  std::map<std::int64_t, std::int64_t> primary_codes;
  std::map<std::int64_t, std::int64_t> extended_codes;
  // Per-SLOT distributions and the ext1 x primary crosstab: the measurement the
  // orchestrator asked for before any sentinel-set ruling. Nothing here changes
  // a contract; it only reports what the tape actually carries.
  std::array<std::map<std::int64_t, std::int64_t>, 4> extended_slot_codes;
  std::map<std::pair<std::int64_t, std::int64_t>, std::int64_t> ext1_by_primary;
  std::map<std::int64_t, std::int64_t> primary_by_all_slots_blank;
  std::int64_t eligible_under_255 = 0;
  std::int64_t eligible_under_255_and_32 = 0;
  std::int64_t prints_with_a_255_slot = 0;
  std::int64_t prints_with_a_32_slot = 0;
  std::int64_t prints_with_a_real_nonzero_ext = 0;
  StockPrintStream prints(session_clock);
  {
    const auto start = std::chrono::steady_clock::now();
    auto opened = qr::sources::StockTradeReader::open(scope.value(), trades_root);
    if (!opened.has_value()) {
      die(opened.error().refusal().message());
    }
    qr::sources::StockTradeReader reader = std::move(opened).value();
    qr::sources::StockTradeReader::Group group;
    for (;;) {
      auto more = reader.next_group(group);
      if (!more.has_value()) {
        die(more.error().refusal().message());
      }
      if (!more.value()) {
        break;
      }
      for (const qr::sources::StockTradeRow& row : group.rows) {
        const bool primary_present = !row.is_null(qr::sources::kTradeSlotCondition);
        const std::int64_t primary = primary_present ? row.condition : -1;
        if (primary_present) {
          ++primary_codes[primary];
        }
        bool any_255 = false;
        bool any_32 = false;
        bool any_real_nonzero = false;      // present, not 255, not 32, not 0
        bool any_nonzero_outside_255 = false;  // present, not 255, not 0
        bool all_slots_blank = true;        // every slot is 255 or 32
        for (std::size_t slot = 0; slot < row.ext_condition.size(); ++slot) {
          if (row.is_null(qr::sources::kTradeSlotExtCondition1 + slot)) {
            continue;
          }
          const std::int64_t code = row.ext_condition[slot];
          ++extended_codes[code];
          ++extended_slot_codes[slot][code];
          if (slot == 0) {
            ++ext1_by_primary[std::make_pair(code, primary)];
          }
          if (code == 255) {
            any_255 = true;
            continue;
          }
          if (code == 32) {
            any_32 = true;
            continue;
          }
          all_slots_blank = false;
          if (code != 0) {
            any_real_nonzero = true;
            any_nonzero_outside_255 = true;
          }
        }
        if (any_255) { ++prints_with_a_255_slot; }
        if (any_32) { ++prints_with_a_32_slot; }
        if (any_real_nonzero) { ++prints_with_a_real_nonzero_ext; }
        if (all_slots_blank && primary_present) {
          ++primary_by_all_slots_blank[primary];
        }
        const bool size_price_ok = !row.is_null(qr::sources::kTradeSlotSize) && row.size > 0 &&
                                   !row.is_null(qr::sources::kTradeSlotPrice) && row.price_u6 > 0;
        if (primary == 0 && size_price_ok && !any_nonzero_outside_255 && !any_32) {
          ++eligible_under_255;
        }
        if (primary == 0 && size_price_ok && !any_real_nonzero) {
          ++eligible_under_255_and_32;
        }
      }
      const auto pushed = prints.push_group(group.ts_ms_b, group.rows);
      if (!pushed.has_value()) {
        die(pushed.error().message());
      }
    }
    trades_seconds = seconds_since(start);
    receipt.add("stock_print", "reader_rth_rows", reader.rth_rows());
    receipt.add("stock_print", "reader_group_count", reader.group_count());
    receipt.add("stock_print", "carrier_group_count",
                static_cast<std::int64_t>(prints.groups().size()));
  }

  double options_seconds = 0.0;
  OptionPrintStream options(session_clock);
  if (!conditions_only) {
    const auto start = std::chrono::steady_clock::now();
    auto opened = qr::sources::OptionPrintReader::open(scope.value(), options_root);
    if (!opened.has_value()) {
      die(opened.error().refusal().message());
    }
    qr::sources::OptionPrintReader reader = std::move(opened).value();
    qr::sources::OptionPrintReader::Group group;
    for (;;) {
      auto more = reader.next_group(group);
      if (!more.has_value()) {
        die(more.error().refusal().message());
      }
      if (!more.value()) {
        break;
      }
      const auto pushed = options.push_group(group.ts_ms_b, group.rows);
      if (!pushed.has_value()) {
        die(pushed.error().message());
      }
    }
    options_seconds = seconds_since(start);
    receipt.add("option_print", "reader_rth_rows", reader.rth_rows());
    receipt.add("option_print", "reader_group_count", reader.group_count());
    receipt.add("option_print", "carrier_group_count",
                static_cast<std::int64_t>(options.groups().size()));
    receipt.add("option_print", "directional_eligible_prints", options.directional_eligible_prints());
    receipt.add("option_print", "tracked_contracts",
                static_cast<std::int64_t>(options.contract_prior().tracked_contracts()));
  }

  // --- the per-modality channel presence censuses, printed IN FULL ------------
  census_rows(receipt, "census.stock_print", prints.census(),
              &qr::carriers::stock_print_channel_name);
  census_rows(receipt, "census.stock_nbbo", nbbo.census(), &qr::carriers::nbbo_channel_name);
  census_rows(receipt, "census.option_print", options.census(),
              &qr::carriers::option_print_channel_name);

  // --- the typed quality ledgers and attachment histograms, in full -----------
  {
    const auto& ledger = prints.quality();
    receipt.add("quality.stock_print", "total", ledger.total);
    receipt.add("quality.stock_print", "eligible", ledger.eligible);
    receipt.add("quality.stock_print", "primary_nonzero", ledger.primary_nonzero);
    receipt.add("quality.stock_print", "extended_nonzero", ledger.extended_nonzero);
    receipt.add("quality.stock_print", "cancel_40_44", ledger.cancel_40_44);
    receipt.add("quality.stock_print", "sentinel_absent", ledger.sentinel_absent);
    receipt.add("quality.stock_print", "nonpositive_size", ledger.nonpositive_size);
    receipt.add("quality.stock_print", "nonfinite_price", ledger.nonfinite_price);
  }
  for (const auto& entry : primary_codes) {
    receipt.add("codes.stock_print_primary", std::to_string(entry.first), entry.second);
  }
  for (const auto& entry : extended_codes) {
    receipt.add("codes.stock_print_extended", std::to_string(entry.first), entry.second);
  }
  for (std::size_t slot = 0; slot < extended_slot_codes.size(); ++slot) {
    for (const auto& entry : extended_slot_codes[slot]) {
      receipt.add("codes.stock_print_ext" + std::to_string(slot + 1),
                  std::to_string(entry.first), entry.second);
    }
  }
  for (const auto& entry : ext1_by_primary) {
    receipt.add("crosstab.ext1_x_primary",
                std::to_string(entry.first.first) + "_x_" + std::to_string(entry.first.second),
                entry.second);
  }
  for (const auto& entry : primary_by_all_slots_blank) {
    receipt.add("blankslots.primary", std::to_string(entry.first), entry.second);
  }
  receipt.add("sentinel_counterfactual", "prints_with_a_255_slot", prints_with_a_255_slot);
  receipt.add("sentinel_counterfactual", "prints_with_a_32_slot", prints_with_a_32_slot);
  receipt.add("sentinel_counterfactual", "prints_with_a_real_nonzero_ext",
              prints_with_a_real_nonzero_ext);
  receipt.add("sentinel_counterfactual", "eligible_if_sentinels_are_255", eligible_under_255);
  receipt.add("sentinel_counterfactual", "eligible_if_sentinels_are_255_and_32",
              eligible_under_255_and_32);
  for (std::size_t state = 0; state < qr::carriers::kAttachStateCount; ++state) {
    const char* name = qr::carriers::attach_state_name(static_cast<qr::carriers::AttachState>(state));
    receipt.add("attach.stock_print_quote", name, prints.attach_states()[state]);
    receipt.add("attach.option_quote", name, options.quote_attach_states()[state]);
    receipt.add("attach.option_underlying", name, options.underlying_attach_states()[state]);
  }

  if (conditions_only) {
    receipt.print();
    std::printf("trades_seconds %.3f\n", trades_seconds);
    std::printf("peak_rss_kib %" PRId64 "\n", peak_rss_kib());
    if (!tsv_path.empty()) {
      receipt.write(tsv_path);
    }
    return 0;
  }

  // --- 2. the prefix 1s midpoint grid -----------------------------------------
  auto grid = MidpointGrid::build(session_clock, nbbo.eligible_midpoints());
  if (!grid.has_value()) {
    die(grid.error().message());
  }
  const MidpointGrid::Census grid_census = grid.value().census();
  receipt.add("grid_1s", "endpoints", grid_census.endpoints);
  receipt.add("grid_1s", "present", grid_census.present);
  receipt.add("grid_1s", "fresh_in_bin", grid_census.fresh_in_bin);
  receipt.add("grid_1s", "stale_gt_1s", grid_census.stale_gt_1s);
  receipt.add("grid_1s", "first_present_endpoint", grid_census.first_present_endpoint);

  // --- 3. the D0 watch roster ---------------------------------------------------
  const std::vector<RosterRow> roster = read_roster(roster_path, ordinal);
  std::int64_t side_unavailable = 0;
  std::int64_t out_of_session = 0;
  std::map<std::pair<std::int64_t, std::uint8_t>, ActionRow> actions;
  for (const RosterRow& row : roster) {
    if (!row.side_available) {
      ++side_unavailable;
      continue;
    }
    // D0: "first registered whole-second clock strictly after own visibility".
    const std::int64_t elapsed = row.visible_ts_ns - session_start_ns;
    if (elapsed < 0) {
      ++out_of_session;
      continue;
    }
    const std::int64_t decision_second = elapsed / qr::carriers::kNanosPerSecond + 1;
    const std::int64_t decision_ts = session_start_ns + decision_second * qr::carriers::kNanosPerSecond;
    if (decision_ts >= session_end_ns) {
      ++out_of_session;  // CLOCK_UNAVAILABLE
      continue;
    }
    const auto key = std::make_pair(decision_second, static_cast<std::uint8_t>(row.side));
    ActionRow& action = actions[key];
    action.decision_second = decision_second;
    action.side = row.side;
    action.decision_ts_ns = decision_ts;
    ++action.watch_count;
  }
  receipt.add("roster", "rows", static_cast<std::int64_t>(roster.size()));
  receipt.add("roster", "side_unavailable", side_unavailable);
  receipt.add("roster", "clock_unavailable", out_of_session);
  receipt.add("roster", "d0_actions", static_cast<std::int64_t>(actions.size()));

  // The phase reference: the newest SAME-SIDE authorizing visibility strictly
  // before the decision and no more than 60s old.
  std::vector<RosterRow> by_visibility = roster;
  std::sort(by_visibility.begin(), by_visibility.end(),
            [](const RosterRow& left, const RosterRow& right) {
              return left.visible_ts_ns < right.visible_ts_ns;
            });
  for (auto& entry : actions) {
    ActionRow& action = entry.second;
    for (const RosterRow& row : by_visibility) {
      if (row.visible_ts_ns >= action.decision_ts_ns) {
        break;
      }
      if (!row.side_available || row.side != action.side) {
        continue;
      }
      if (action.decision_ts_ns - row.visible_ts_ns > 60 * qr::carriers::kNanosPerSecond) {
        continue;
      }
      action.phase_reference_present = true;
      action.phase_reference_ns = row.visible_ts_ns;
    }
  }

  // --- 4. DIRECT_RAW, location and candidate-set rows for every action ---------
  DirectRawBuilder direct_print(Modality::STOCK_PRINT, prints.groups());
  DirectRawBuilder direct_nbbo(Modality::STOCK_NBBO, nbbo.groups());
  DirectRawBuilder direct_option(Modality::OPTION_PRINT, options.groups());

  LocationInputs location_inputs;
  location_inputs.clock = &session_clock;
  location_inputs.grid = &grid.value();
  location_inputs.eligible_mids = nbbo.eligible_midpoints();
  location_inputs.stock_print_groups = prints.groups();
  location_inputs.option_print_groups = options.groups();
  location_inputs.vwap_notional_prefix = prints.vwap_notional_prefix();
  location_inputs.vwap_size_prefix = prints.vwap_size_prefix();
  const LocationBuilder location(location_inputs);

  Fingerprint fingerprint;
  const auto feature_start = std::chrono::steady_clock::now();
  std::int64_t direct_rows = 0;
  std::int64_t direct_columns_seen = 0;
  std::int64_t location_rows = 0;
  std::int64_t candidate_rows = 0;
  // The RAGGED candidate-set block (orchestrator ruling: no cap, CSR offsets).
  qr::carriers::CandidateSetBlock candidate_block;
  std::vector<qr::carriers::CandidateSetRow> decision_rows;
  std::array<std::int64_t, qr::carriers::kCandidateRelationCount> relation_counts{};
  std::int64_t direct_present_cells = 0;
  std::int64_t location_present_cells = 0;

  for (const auto& entry : actions) {
    const ActionRow& action = entry.second;
    DecisionWindow window;
    window.cutoff_ns_a = action.decision_ts_ns;
    window.session_open_ns_a = session_start_ns;
    window.side = action.side;
    window.phase_reference_present = action.phase_reference_present;
    window.phase_reference_ns_a = action.phase_reference_ns;

    for (DirectRawBuilder* builder : {&direct_print, &direct_nbbo, &direct_option}) {
      const auto row = builder->build(window);
      if (!row.has_value()) {
        die(row.error().message());
      }
      direct_columns_seen = static_cast<std::int64_t>(row.value().value.size());
      ++direct_rows;
      for (std::size_t column = 0; column < qr::carriers::kDirectColumnCount; ++column) {
        fingerprint.feed(row.value().value[column]);
        fingerprint.feed(row.value().validity[column]);
        if (row.value().presence(column)) {
          ++direct_present_cells;
        }
      }
    }

    const auto location_row = location.build(action.decision_ts_ns, action.side);
    if (!location_row.has_value()) {
      die(location_row.error().message());
    }
    ++location_rows;
    for (std::size_t index = 0; index < qr::carriers::kLocationValueCount; ++index) {
      fingerprint.feed(location_row.value().value[index]);
      fingerprint.feed(location_row.value().validity[index]);
      if (location_row.value().presence(index)) {
        ++location_present_cells;
      }
    }

    decision_rows.clear();
    for (const RosterRow& row : by_visibility) {
      if (row.visible_ts_ns >= action.decision_ts_ns) {
        break;
      }
      if (action.decision_ts_ns - row.visible_ts_ns > 60 * qr::carriers::kNanosPerSecond) {
        continue;
      }
      VisibleCandidate candidate;
      candidate.policy_index = qr::carriers::policy_index_of(row.policy_name);
      candidate.reversal_bps = row.reversal_bps;
      candidate.member_count = row.member_count;
      candidate.visible_ts_ns_a = row.visible_ts_ns;
      if (!row.side_available) {
        candidate.relation = row.mixed_members ? CandidateRelation::MIXED
                                               : CandidateRelation::UNAVAILABLE;
      } else {
        candidate.relation = row.side == action.side ? CandidateRelation::OWN
                                                     : CandidateRelation::OPPOSITE;
      }
      const auto candidate_row = qr::carriers::build_candidate_set_row(candidate,
                                                                       action.decision_ts_ns);
      if (!candidate_row.has_value()) {
        die(candidate_row.error().message());
      }
      ++relation_counts[static_cast<std::size_t>(candidate.relation)];
      ++candidate_rows;
      decision_rows.push_back(candidate_row.value());
      for (std::size_t field = 0; field < qr::carriers::kCandidateSetFieldCount; ++field) {
        fingerprint.feed(candidate_row.value().value[field]);
        fingerprint.feed(candidate_row.value().validity[field]);
      }
    }
    const auto appended = candidate_block.push_decision(decision_rows);
    if (!appended.has_value()) {
      die(appended.error().message());
    }
  }
  const double feature_seconds = seconds_since(feature_start);
  const double total_seconds = seconds_since(wall_start);

  receipt.add("direct_raw", "rows", direct_rows);
  receipt.add("direct_raw", "columns_per_row", direct_columns_seen);
  receipt.add("direct_raw", "present_cells", direct_present_cells);
  receipt.add("location", "rows", location_rows);
  receipt.add("location", "present_cells", location_present_cells);
  receipt.add("candidate_set", "rows", candidate_rows);
  receipt.add("candidate_set", "fields_per_row",
              static_cast<std::int64_t>(qr::carriers::kCandidateSetFieldCount));
  receipt.add("candidate_set", "max_visible_per_action",
              static_cast<std::int64_t>(candidate_block.max_rows()));
  // The CSR shape itself, so the receipt shows the ragged block is well formed:
  // offsets carry decisions()+1 entries and the last one is the row total.
  receipt.add("candidate_set", "csr_decisions",
              static_cast<std::int64_t>(candidate_block.decisions()));
  receipt.add("candidate_set", "csr_offset_entries",
              static_cast<std::int64_t>(candidate_block.offsets().size()));
  receipt.add("candidate_set", "csr_total_rows",
              static_cast<std::int64_t>(candidate_block.total_rows()));
  receipt.add("candidate_set", "csr_value_cells",
              static_cast<std::int64_t>(candidate_block.values().size()));
  for (std::size_t relation = 0; relation < qr::carriers::kCandidateRelationCount; ++relation) {
    receipt.add("candidate_set",
                std::string("relation.") +
                    qr::carriers::candidate_relation_name(static_cast<CandidateRelation>(relation)),
                relation_counts[relation]);
  }
  char digest[32];
  std::snprintf(digest, sizeof(digest), "%016" PRIx64, fingerprint.value());
  receipt.add_text("identity", "feature_fnv1a64", digest);

  receipt.print();
  std::printf("nbbo_seconds %.3f\n", nbbo_seconds);
  std::printf("trades_seconds %.3f\n", trades_seconds);
  std::printf("options_seconds %.3f\n", options_seconds);
  std::printf("feature_seconds %.3f\n", feature_seconds);
  std::printf("total_seconds %.3f\n", total_seconds);
  std::printf("peak_rss_kib %" PRId64 "\n", peak_rss_kib());

  if (!tsv_path.empty()) {
    receipt.write(tsv_path);
  }
  return 0;
}
