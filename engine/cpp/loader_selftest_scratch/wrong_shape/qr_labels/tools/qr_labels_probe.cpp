// qr_labels_probe — the authorized session-125 watch + label run (WP7).
//
// WP7 brief, REAL-FILE CHECK (payload read authorized for this work package on
// EXACTLY the already-opened streams of session 125):
//   /workspace/data/tokens/stock_quotes/IWM/2022/2022-07-05.parquet
//   plus the WP6-sealed candidate roster of that session (roster.tsv), which is
//   a PUBLICATION of the qr_candidates authority and not a payload read.
// "build watches for all 25,934 side-resolved candidates (from qr_candidates),
//  label all watch-actions with the full menu+certificate; report: action-row
//  count, per-state censuses, stop_hit rates per horizon, certificate vs
//  menu_net_15 summary stats; wall + RSS; two-run byte identity."
//
// It is a binary rather than a ctest case for the reason WP3/WP4/WP5
// established: 15.4M rows and 2.8M groups do not belong in every ctest
// invocation. ci/wp7_labels_realfile_gate.sh runs it against the release build.
//
// NOTHING IN THE PUBLISHED TSVs IS A TIMING. Wall and RSS go to stdout only, so
// the artifact bytes are identical across runs by construction.
//
// usage:
//   qr_labels_probe --root DIR --roster PATH [--ordinal N] [--label NAME]
//                   [--out DIR] [--skip-wp5-verify]
#include <algorithm>
#include <chrono>
#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include "qr_labels/execution_tape.hpp"
#include "qr_labels/label_kernel.hpp"
#include "qr_labels/watches.hpp"
#include "qr_nbbo/group_machine.hpp"
#include "qr_sources/stock_quotes.hpp"

namespace {

using qr::labels::ActionRow;
using qr::labels::ExecutionTape;
using qr::labels::LabelCensus;
using qr::labels::LabelRow;
using qr::labels::SessionLabelIndex;
using qr::labels::Side;
using qr::labels::WatchCandidate;
using qr::labels::WatchPlan;

constexpr std::uint64_t kFnvOffsetBasis = 0xCBF29CE484222325ULL;
constexpr std::uint64_t kFnvPrime = 0x100000001B3ULL;

std::uint64_t fnv1a(std::string_view data) {
  std::uint64_t digest = kFnvOffsetBasis;
  for (const char byte : data) {
    digest ^= static_cast<std::uint64_t>(static_cast<std::uint8_t>(byte));
    digest *= kFnvPrime;
  }
  return digest;
}

const qr::Registry* registry_or_null() {
  static qr::Expected<qr::Registry, qr::Refusal> loaded = qr::Registry::load_embedded();
  return loaded.has_value() ? &loaded.value() : nullptr;
}

[[noreturn]] void die(const std::string& what) {
  std::fprintf(stderr, "REFUSED: %s\n", what.c_str());
  std::exit(1);
}

std::int64_t peak_rss_kib() {
  std::ifstream status("/proc/self/status");
  std::string line;
  while (std::getline(status, line)) {
    if (line.rfind("VmHWM:", 0) == 0) {
      return std::strtoll(line.c_str() + 6, nullptr, 10);
    }
  }
  return 0;
}

void write_file(const std::string& path, const std::string& text) {
  std::ofstream out(path, std::ios::binary | std::ios::trunc);
  if (!out) {
    die("cannot write " + path);
  }
  out << text;
  out.close();
  if (!out) {
    die("cannot close " + path);
  }
}

/// The WP6-sealed roster, parsed strictly: the header must be the exact one
/// `qr::candidates::render_roster` writes, and every field is read by name.
struct RosterParse {
  /// The side-authenticated candidates: only these create watches (card
  /// section 3, "Each side-authenticated admitted primitive candidate creates
  /// three watches").
  std::vector<WatchCandidate> candidates;
  /// EVERY admitted primitive candidate's own visibility, side-resolved or
  /// not: the authority clock roster is the sorted union of the registered
  /// whole seconds and every ADMITTED PRIMITIVE candidate's visibility, and a
  /// SIDE_UNAVAILABLE row stays in the primitive denominator (card section 2).
  std::vector<std::int64_t> admitted_visibilities;
  std::int64_t rows = 0;
  std::int64_t side_unavailable = 0;
  std::int64_t long_rows = 0;
  std::int64_t short_rows = 0;
};

RosterParse parse_roster(const std::string& path, std::int64_t ordinal) {
  static constexpr const char* kHeader =
      "session_ordinal\tday\tcandidate_id\tpolicy_name\treversal_bps\tvisible_ts_ns\t"
      "member_count\tcandidate_physical_key\tside\tcause\tenter_forbidden";
  std::ifstream in(path);
  if (!in) {
    die("cannot open the sealed roster " + path);
  }
  std::string line;
  if (!std::getline(in, line) || line != kHeader) {
    die("the roster header is not the WP6 authority's own header: " + path);
  }
  RosterParse out;
  while (std::getline(in, line)) {
    if (line.empty()) {
      continue;
    }
    std::vector<std::string> field;
    field.reserve(11);
    std::string cell;
    std::istringstream row(line);
    while (std::getline(row, cell, '\t')) {
      field.push_back(cell);
    }
    if (field.size() != 11) {
      die("a roster row does not carry the authority's eleven fields");
    }
    if (std::strtoll(field[0].c_str(), nullptr, 10) != ordinal) {
      die("the roster carries a session other than the requested one");
    }
    out.rows += 1;
    out.admitted_visibilities.push_back(std::strtoll(field[5].c_str(), nullptr, 10));
    WatchCandidate candidate;
    candidate.candidate_id = field[2];
    candidate.policy_name = field[3];
    candidate.reversal_bps = std::strtoull(field[4].c_str(), nullptr, 10);
    candidate.visible_ts_ns = std::strtoll(field[5].c_str(), nullptr, 10);
    candidate.member_count = std::strtoull(field[6].c_str(), nullptr, 10);
    candidate.candidate_physical_key = field[7];
    if (field[8] == "LONG") {
      candidate.side = Side::LONG;
      out.long_rows += 1;
    } else if (field[8] == "SHORT") {
      candidate.side = Side::SHORT;
      out.short_rows += 1;
    } else {
      // SIDE_UNAVAILABLE: retained in the primitive denominator, forbidden to
      // ENTER, and it creates no watch (card section 2/3).
      out.side_unavailable += 1;
      continue;
    }
    out.candidates.push_back(std::move(candidate));
  }
  return out;
}

struct Metric {
  std::string name;
  std::string value;
};

void metric(std::vector<Metric>& rows, std::string name, std::int64_t value) {
  rows.push_back(Metric{std::move(name), std::to_string(value)});
}

/// Exact integer summary of one column: count, sum, truncating mean, min,
/// median (lower of the two middles on an even count) and max. No floating
/// point enters a published artifact.
void summarize(std::vector<Metric>& rows, const std::string& prefix,
               std::vector<std::int64_t> values) {
  metric(rows, prefix + "_count", static_cast<std::int64_t>(values.size()));
  if (values.empty()) {
    return;
  }
  std::sort(values.begin(), values.end());
  std::int64_t sum = 0;
  for (const std::int64_t value : values) {
    sum += value;
  }
  metric(rows, prefix + "_sum_cent", sum);
  metric(rows, prefix + "_mean_cent_trunc", sum / static_cast<std::int64_t>(values.size()));
  metric(rows, prefix + "_min_cent", values.front());
  metric(rows, prefix + "_p50_cent", values[(values.size() - 1) / 2]);
  metric(rows, prefix + "_max_cent", values.back());
}

int usage() {
  std::fprintf(stderr,
               "usage: qr_labels_probe --root DIR --roster PATH [--ordinal N] [--label NAME] "
               "[--out DIR] [--skip-wp5-verify]\n");
  return 2;
}

}  // namespace

int main(int argc, char** argv) {
  std::string root;
  std::string roster_path;
  std::string label = "IWM_labels_2022-07-05";
  std::string out_dir;
  std::int64_t ordinal = 125;
  bool verify_wp5 = true;
  for (int index = 1; index < argc; ++index) {
    const std::string flag = argv[index];
    const bool has_value = index + 1 < argc;
    if (flag == "--root" && has_value) {
      root = argv[++index];
    } else if (flag == "--roster" && has_value) {
      roster_path = argv[++index];
    } else if (flag == "--label" && has_value) {
      label = argv[++index];
    } else if (flag == "--out" && has_value) {
      out_dir = argv[++index];
    } else if (flag == "--ordinal" && has_value) {
      ordinal = std::strtoll(argv[++index], nullptr, 10);
    } else if (flag == "--skip-wp5-verify") {
      verify_wp5 = false;
    } else {
      return usage();
    }
  }
  if (root.empty() || roster_path.empty()) {
    return usage();
  }

  const qr::Registry* const registry = registry_or_null();
  if (registry == nullptr) {
    die("the embedded registry refused to load");
  }
  const auto scope = qr::DayScope::admit(*registry, ordinal);
  if (!scope.has_value()) {
    die(scope.error().message());
  }
  const std::filesystem::path corpus_root(root);

  // --- 1. the execution envelope (the WP4 decode + the WP7 extrema) --------
  const auto tape_started = std::chrono::steady_clock::now();
  auto opened = qr::sources::StockQuoteReader::open(scope.value(), corpus_root,
                                                    scope.value().profile());
  if (!opened.has_value()) {
    die(opened.error().message());
  }
  qr::sources::StockQuoteReader reader = std::move(opened).value();
  auto built = qr::labels::build_execution_tape(reader, scope.value());
  if (!built.has_value()) {
    die(built.error().message());
  }
  ExecutionTape tape = std::move(built).value();
  const double tape_seconds =
      std::chrono::duration<double>(std::chrono::steady_clock::now() - tape_started).count();

  // --- 2. the binding check against the WP5 projection ---------------------
  std::int64_t verified_groups = -1;
  double verify_seconds = 0.0;
  if (verify_wp5) {
    const auto verify_started = std::chrono::steady_clock::now();
    auto reopened = qr::sources::StockQuoteReader::open(scope.value(), corpus_root,
                                                        scope.value().profile());
    if (!reopened.has_value()) {
      die(reopened.error().message());
    }
    qr::sources::StockQuoteReader wp5_reader = std::move(reopened).value();
    auto ran = qr::nbbo::run_session(wp5_reader, scope.value());
    if (!ran.has_value()) {
      die(ran.error().message());
    }
    const qr::nbbo::GroupMachine machine = std::move(ran).value();
    const auto matched = qr::labels::verify_against(tape, machine.groups());
    if (!matched.has_value()) {
      die(matched.error().message());
    }
    verified_groups = matched.value();
    verify_seconds =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - verify_started).count();
  }

  // --- 3. the sealed roster -> watch candidates ----------------------------
  const RosterParse roster = parse_roster(roster_path, ordinal);

  // --- 4. the watches, the authority roster and the unique action rows -----
  const auto watch_started = std::chrono::steady_clock::now();
  auto session_clock = qr::SessionClock::from_session(scope.value().session());
  if (!session_clock.has_value()) {
    die(session_clock.error().message());
  }
  auto decision_clock = qr::labels::DecisionClock::from_clock(session_clock.value());
  if (!decision_clock.has_value()) {
    die(decision_clock.error().message());
  }
  auto decision_roster =
      qr::labels::DecisionRoster::build(decision_clock.value(), roster.admitted_visibilities);
  if (!decision_roster.has_value()) {
    die(decision_roster.error().message());
  }
  auto plan = qr::labels::build_watches(ordinal, decision_clock.value(), decision_roster.value(),
                                        roster.candidates);
  if (!plan.has_value()) {
    die(plan.error().message());
  }
  const WatchPlan watches = std::move(plan).value();
  const double watch_seconds =
      std::chrono::duration<double>(std::chrono::steady_clock::now() - watch_started).count();

  // --- 5. THE LABEL PASS ---------------------------------------------------
  const auto label_started = std::chrono::steady_clock::now();
  SessionLabelIndex index = SessionLabelIndex::build(std::move(tape));
  const double index_seconds =
      std::chrono::duration<double>(std::chrono::steady_clock::now() - label_started).count();
  auto labelled = qr::labels::label_session(index, watches.actions);
  if (!labelled.has_value()) {
    die(labelled.error().message());
  }
  const std::vector<LabelRow> rows = std::move(labelled).value();
  const double label_seconds =
      std::chrono::duration<double>(std::chrono::steady_clock::now() - label_started).count();

  // --- 6. the censuses and the summary -------------------------------------
  LabelCensus census;
  std::vector<std::int64_t> certificate_net;
  std::vector<std::int64_t> menu_net_15;
  std::vector<std::int64_t> certificate_mae;
  std::vector<std::int64_t> menu_mae_15;
  std::int64_t certificate_at_least_menu15 = 0;
  std::int64_t menu15_positive = 0;
  for (const LabelRow& row : rows) {
    census.observe(row);
    if (row.menu.state != qr::labels::LabelState::OK) {
      continue;
    }
    certificate_net.push_back(row.certificate_net_cent);
    certificate_mae.push_back(row.certificate_mae_cent);
    menu_net_15.push_back(row.menu.menu_net_cent[2]);  // h = 15 minutes
    menu_mae_15.push_back(row.menu.menu_mae_cent[2]);
    if (row.certificate_net_cent >= row.menu.menu_net_cent[2]) {
      certificate_at_least_menu15 += 1;
    }
    if (row.menu.menu_net_cent[2] > 0) {
      menu15_positive += 1;
    }
  }

  std::vector<Metric> summary;
  summary.push_back(Metric{"path", reader.path().string()});
  summary.push_back(Metric{"day", scope.value().day()});
  metric(summary, "ordinal", scope.value().ordinal());
  metric(summary, "registry_raw_rth_row_count", scope.value().session().raw_rth_row_count);
  metric(summary, "registry_complete_group_count", scope.value().session().complete_group_count);
  metric(summary, "tape_groups_seen", index.tape().census.groups_seen);
  metric(summary, "tape_lawful_marks", index.tape().size());
  metric(summary, "tape_groups_without_eligible_member",
         index.tape().census.groups_without_eligible_member);
  metric(summary, "tape_eligible_members", index.tape().census.eligible_members);
  metric(summary, "tape_ineligible_members", index.tape().census.ineligible_members);
  metric(summary, "wp5_verified_eligible_groups", verified_groups);
  metric(summary, "roster_rows", roster.rows);
  metric(summary, "roster_side_resolved", static_cast<std::int64_t>(roster.candidates.size()));
  metric(summary, "roster_long", roster.long_rows);
  metric(summary, "roster_short", roster.short_rows);
  metric(summary, "roster_side_unavailable", roster.side_unavailable);
  metric(summary, "roster_admitted_visibilities",
         static_cast<std::int64_t>(roster.admitted_visibilities.size()));
  metric(summary, "decision_roster_size", decision_roster.value().size());
  metric(summary, "decision_roster_registered_seconds", decision_clock.value().second_count());
  metric(summary, "decision_roster_visibilities_off_second",
         decision_roster.value().visibilities_off_second());
  metric(summary, "decision_roster_visibilities_on_second",
         decision_roster.value().visibilities_on_second());
  metric(summary, "watch_rows", static_cast<std::int64_t>(watches.ledger.size()));
  metric(summary, "watches_built", watches.census.watches_built);
  metric(summary, "watches_clock_unavailable", watches.census.watches_clock_unavailable);
  for (std::size_t stage = 0; stage < qr::labels::kWatchStageCount; ++stage) {
    const auto name = qr::labels::watch_stage_name(static_cast<qr::labels::WatchStage>(stage));
    metric(summary, std::string("watches_built_") + name, watches.census.per_stage_built[stage]);
    metric(summary, std::string("watches_clock_unavailable_") + name,
           watches.census.per_stage_clock_unavailable[stage]);
  }
  metric(summary, "action_rows", watches.census.actions);
  metric(summary, "action_rows_long", watches.census.actions_long);
  metric(summary, "action_rows_short", watches.census.actions_short);
  metric(summary, "converged_watches", watches.census.converged_watches);
  metric(summary, "label_rows", census.rows);
  for (std::size_t state = 0; state < census.per_state.size(); ++state) {
    metric(summary,
           std::string("label_state_") +
               qr::replay::label_state_name(static_cast<qr::labels::LabelState>(state)),
           census.per_state[state]);
  }
  for (std::size_t horizon = 0; horizon < qr::labels::kHorizonCount; ++horizon) {
    const std::string suffix = qr::labels::kHorizonMinutes[horizon] >= 0
                                   ? std::to_string(qr::labels::kHorizonMinutes[horizon]) + "m"
                                   : std::string("close");
    metric(summary, "stop_hit_" + suffix, census.stop_hit[horizon]);
  }
  for (std::size_t state = 0; state < qr::labels::kBarrierStateCount; ++state) {
    metric(summary,
           std::string("barrier_") +
               qr::labels::barrier_state_name(static_cast<qr::labels::BarrierState>(state)),
           census.barrier_state[state]);
  }
  metric(summary, "gap_through_rows", census.gap_through_rows);
  metric(summary, "certificate_positive_rows", census.certificate_positive_rows);
  metric(summary, "certificate_at_least_menu15_rows", certificate_at_least_menu15);
  metric(summary, "menu_net_15m_positive_rows", menu15_positive);
  summarize(summary, "certificate_net", certificate_net);
  summarize(summary, "menu_net_15m", menu_net_15);
  summarize(summary, "certificate_mae", certificate_mae);
  summarize(summary, "menu_mae_15m", menu_mae_15);

  std::string summary_tsv = "label\tmetric\tvalue\n";
  for (const Metric& row : summary) {
    summary_tsv += label;
    summary_tsv += '\t';
    summary_tsv += row.name;
    summary_tsv += '\t';
    summary_tsv += row.value;
    summary_tsv += '\n';
  }
  const std::string labels_tsv = qr::labels::render_label_rows(rows);
  const std::string ledger_tsv = qr::labels::render_watch_ledger(watches);

  std::fputs(summary_tsv.c_str(), stdout);
  std::printf("labels_digest_i64 %" PRId64 "\n", static_cast<std::int64_t>(fnv1a(labels_tsv)));
  std::printf("ledger_digest_i64 %" PRId64 "\n", static_cast<std::int64_t>(fnv1a(ledger_tsv)));
  std::printf("tape_seconds %.6f\n", tape_seconds);
  std::printf("verify_seconds %.6f\n", verify_seconds);
  std::printf("watch_seconds %.6f\n", watch_seconds);
  std::printf("index_seconds %.6f\n", index_seconds);
  std::printf("label_seconds %.6f\n", label_seconds);
  std::printf("full_seconds %.6f\n", tape_seconds + watch_seconds + label_seconds);
  std::printf("peak_rss_kib %" PRId64 "\n", peak_rss_kib());

  if (!out_dir.empty()) {
    std::filesystem::create_directories(out_dir);
    write_file(out_dir + "/summary.tsv", summary_tsv);
    write_file(out_dir + "/labels.tsv", labels_tsv);
    write_file(out_dir + "/watch_ledger.tsv", ledger_tsv);
    write_file(out_dir + "/tape_census.tsv", index.tape().census.to_tsv(label));
    write_file(out_dir + "/watch_census.tsv", watches.census.to_tsv(label));
    write_file(out_dir + "/label_census.tsv", census.to_tsv(label));
  }
  return 0;
}
