// qr_m25_run — THE M2.5 RUNNER (FINAL_PLAN.md section 8).
//
// It measures three things on TRAIN sessions of one fold and writes receipts;
// it decides nothing. The verdict (Q*, Q_max, the gate, the affine cap B) is
// assembled by `engine/cpp/python/m25_reading.py`, which owns the pinned
// estimator and therefore owns every confidence bound.
//
//   --mode arms    the decomposition panel (FINAL_PLAN section 8 item 2)
//   --mode sweep   the parametric skill sweep over the A6 gate family (item 1)
//   --mode twins   the twin-discordance observability ceiling (item 1, Q_max)
//   --mode all     all three
//
// EVERY DOLLAR COMES OUT OF `qr::replay::replay`. This tool writes scores and
// gates; it never adds, subtracts, caps or interpolates money.
//
// usage:
//   qr_m25_run --run DIR --fold F4|F5 --out DIR [--mode all]
//              [--threads N] [--replicates N] [--first N] [--last N]
//              [--card-sha HEX] [--qgrid a,b,c] [--skip-loss-limit-panel]
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#include "qr_m25/arms.hpp"
#include "qr_m25/skill.hpp"
#include "qr_m25/tape.hpp"
#include "qr_m25/twins.hpp"

namespace {

using qr::m25::Arm;
using qr::m25::Fold;
using qr::m25::kArmCount;
using qr::m25::SessionTape;
using qr::m25::TapeRoot;
using qr::replay::kHorizonCount;

/// The A6 selection grid, verbatim (card section 6): q in {1,2,5,10,20,30}%,
/// rho in {.15,.25,.40}, h over the seven-horizon menu.
constexpr std::int64_t kQPercent[] = {1, 2, 5, 10, 20, 30};
constexpr double kRho[] = {0.15, 0.25, 0.40};
constexpr std::size_t kQPercentCount = 6;
constexpr std::size_t kRhoCount = 3;

struct Options {
  std::filesystem::path run_dir;
  std::filesystem::path out_dir;
  Fold fold = Fold::F5;
  std::string mode = "all";
  int threads = 12;
  std::int64_t replicates = 1;
  std::int64_t first = -1;
  std::int64_t last = -1;
  std::string card_sha;
  std::vector<double> q_grid;
  bool loss_limit_panel = true;
};

int fail(const qr::Refusal& refusal) {
  std::fprintf(stderr, "REFUSED: %s\n", refusal.message().c_str());
  return 1;
}

std::vector<double> default_q_grid() {
  std::vector<double> grid;
  for (int step = 0; step <= 20; ++step) {
    grid.push_back(static_cast<double>(step) * 0.05);
  }
  return grid;
}

/// One sweep cell: a skill level and an A6 (h, q, rho) triple.
struct SweepCell {
  double q_skill = 0.0;
  std::size_t horizon = 0;
  std::int64_t q_percent = 0;
  double rho = 0.0;
};

std::string to_string_exact(double value) {
  char buffer[32];
  std::snprintf(buffer, sizeof(buffer), "%.6f", value);
  return buffer;
}

}  // namespace

int main(int argc, char** argv) {
  Options options;
  for (int index = 1; index < argc; ++index) {
    const std::string argument = argv[index];
    const bool has_next = index + 1 < argc;
    if (argument == "--run" && has_next) {
      options.run_dir = argv[++index];
    } else if (argument == "--out" && has_next) {
      options.out_dir = argv[++index];
    } else if (argument == "--fold" && has_next) {
      if (!qr::m25::parse_fold(argv[++index], &options.fold)) {
        std::fprintf(stderr, "unknown fold\n");
        return 2;
      }
    } else if (argument == "--mode" && has_next) {
      options.mode = argv[++index];
    } else if (argument == "--threads" && has_next) {
      options.threads = std::atoi(argv[++index]);
    } else if (argument == "--replicates" && has_next) {
      options.replicates = std::atoll(argv[++index]);
    } else if (argument == "--first" && has_next) {
      options.first = std::atoll(argv[++index]);
    } else if (argument == "--last" && has_next) {
      options.last = std::atoll(argv[++index]);
    } else if (argument == "--card-sha" && has_next) {
      options.card_sha = argv[++index];
    } else if (argument == "--skip-loss-limit-panel") {
      options.loss_limit_panel = false;
    } else if (argument == "--qgrid" && has_next) {
      std::stringstream stream(argv[++index]);
      std::string field;
      while (std::getline(stream, field, ',')) {
        options.q_grid.push_back(std::atof(field.c_str()));
      }
    } else {
      std::fprintf(stderr, "unknown argument: %s\n", argument.c_str());
      return 2;
    }
  }
  if (options.run_dir.empty() || options.out_dir.empty()) {
    std::fprintf(stderr, "usage: qr_m25_run --run DIR --fold F4|F5 --out DIR [--mode all]\n");
    return 2;
  }
  if (options.q_grid.empty()) {
    options.q_grid = default_q_grid();
  }
  if (options.threads < 1) {
    options.threads = 1;
  }

  const TapeRoot root = qr::m25::tape_root(options.run_dir);
  const qr::m25::TrainRange range = qr::m25::train_range(options.fold);
  const std::int64_t first = options.first < 0 ? range.first : options.first;
  const std::int64_t last = options.last < 0 ? range.last : options.last;
  std::vector<std::int64_t> sessions;
  for (std::int64_t ordinal = first; ordinal <= last; ++ordinal) {
    if (qr::m25::Status wall = qr::m25::assert_train_session(options.fold, ordinal);
        !wall.has_value()) {
      return fail(wall.error());
    }
    sessions.push_back(ordinal);
  }
  if (sessions.empty()) {
    std::fprintf(stderr, "no TRAIN sessions selected\n");
    return 2;
  }

  // THE FROZEN-CARD CHECK, once, before anything is measured.
  {
    qr::Expected<std::string, qr::Refusal> sha = qr::m25::shard_card_sha(root, sessions.front());
    if (!sha.has_value()) {
      return fail(sha.error());
    }
    if (!options.card_sha.empty() && sha.value() != options.card_sha) {
      std::fprintf(stderr, "REFUSED: shard card sha %s != expected %s\n", sha.value().c_str(),
                   options.card_sha.c_str());
      return 1;
    }
    options.card_sha = sha.value();
  }

  std::filesystem::create_directories(options.out_dir);
  const bool do_arms = options.mode == "all" || options.mode == "arms";
  const bool do_sweep = options.mode == "all" || options.mode == "sweep";
  const bool do_twins = options.mode == "all" || options.mode == "twins";

  std::vector<SweepCell> cells;
  if (do_sweep) {
    for (const double q_skill : options.q_grid) {
      for (std::size_t h = 0; h < kHorizonCount; ++h) {
        for (std::size_t qi = 0; qi < kQPercentCount; ++qi) {
          for (std::size_t ri = 0; ri < kRhoCount; ++ri) {
            cells.push_back(SweepCell{q_skill, h, kQPercent[qi], kRho[ri]});
          }
        }
      }
    }
  }

  const std::size_t session_count = sessions.size();
  const std::size_t cell_count = cells.size();
  // Per-replicate dense matrices [cell, session]. Sessions are the fast axis so
  // Python reads one cell's session vector contiguously.
  std::vector<std::vector<std::int64_t>> sweep_net(
      static_cast<std::size_t>(options.replicates),
      std::vector<std::int64_t>(cell_count * session_count, 0));
  std::vector<std::vector<std::int32_t>> sweep_trades(
      static_cast<std::size_t>(options.replicates),
      std::vector<std::int32_t>(cell_count * session_count, 0));

  std::mutex output_mutex;
  std::vector<std::string> session_rows(session_count);
  std::vector<std::string> arm_rows(session_count);
  std::vector<std::string> twin_ladder_rows(session_count);
  std::vector<std::string> twin_pool_rows(session_count);
  std::atomic<std::size_t> next_session{0};
  std::atomic<bool> failed{false};
  qr::Refusal first_refusal(qr::RefusalCode::CONFIG, "qr_m25_run", "no refusal", 0);

  const auto wall_start = std::chrono::steady_clock::now();

  auto worker = [&]() {
    for (;;) {
      const std::size_t index = next_session.fetch_add(1);
      if (index >= session_count || failed.load()) {
        return;
      }
      const std::int64_t ordinal = sessions[index];
      qr::Expected<SessionTape, qr::Refusal> loaded =
          qr::m25::load_session(root, options.fold, ordinal);
      if (!loaded.has_value()) {
        std::lock_guard<std::mutex> guard(output_mutex);
        if (!failed.exchange(true)) {
          first_refusal = loaded.error();
        }
        return;
      }
      SessionTape tape = std::move(loaded).value();

      {
        std::ostringstream row;
        row << qr::m25::fold_name(options.fold) << '\t' << ordinal << '\t' << tape.day << '\t'
            << tape.year << '\t' << tape.rows.size() << '\t' << tape.clock_count() << '\t'
            << tape.long_rows << '\t' << tape.short_rows << '\t' << tape.label_ok_rows << '\t'
            << tape.label_entry_unavailable_rows << '\t' << tape.label_exit_unavailable_rows << '\n';
        session_rows[index] = row.str();
      }

      if (do_arms) {
        std::ostringstream rows;
        std::vector<std::int64_t> limits{qr::m25::kDailyLossLimitCent};
        if (options.loss_limit_panel) {
          limits.push_back(qr::m25::kDailyLossLimitPanelCent);
        }
        for (const std::int64_t limit : limits) {
          for (std::size_t a = 0; a < kArmCount; ++a) {
            const Arm arm = static_cast<Arm>(a);
            for (std::size_t h = 0; h < kHorizonCount; ++h) {
              qr::Expected<qr::replay::DailyLedger, qr::Refusal> ledger =
                  qr::m25::run_arm(arm, &tape, h, 0, limit);
              if (!ledger.has_value()) {
                std::lock_guard<std::mutex> guard(output_mutex);
                if (!failed.exchange(true)) {
                  first_refusal = ledger.error();
                }
                return;
              }
              const qr::replay::DailyLedger& daily = ledger.value();
              std::int64_t breaches = 0;
              std::int64_t max_mae = 0;
              for (const qr::replay::TradeRecord& trade : daily.trades) {
                if (trade.stop_hit && trade.gap_through_cent > 0) {
                  ++breaches;
                }
                max_mae = std::max(max_mae, trade.mae_cent);
              }
              rows << qr::m25::fold_name(options.fold) << '\t' << qr::m25::arm_name(arm) << '\t' << h
                   << '\t' << limit << '\t' << ordinal << '\t' << tape.year << '\t'
                   << daily.net_cent << '\t' << daily.trade_count() << '\t' << breaches << '\t'
                   << max_mae << '\t' << (daily.halted_daily_loss ? 1 : 0) << '\t'
                   << daily.clock_count << '\t'
                   << daily.clock_census[static_cast<std::size_t>(qr::replay::ClockOutcome::ENTERED)]
                   << '\t'
                   << daily.clock_census[static_cast<std::size_t>(qr::replay::ClockOutcome::OCCUPIED)]
                   << '\t'
                   << daily.clock_census[static_cast<std::size_t>(
                          qr::replay::ClockOutcome::NO_FRESH_FILL)]
                   << '\t'
                   << daily.clock_census[static_cast<std::size_t>(
                          qr::replay::ClockOutcome::OVERRIDE_SIDE_UNAVAILABLE)]
                   << '\t' << daily.coin_draws << '\n';
            }
          }
        }
        arm_rows[index] = rows.str();
      }

      if (do_sweep || do_twins) {
        for (std::int64_t replicate = 0; replicate < options.replicates; ++replicate) {
          const qr::m25::SkillDraws draws = qr::m25::build_skill_draws(tape, replicate);

          if (do_sweep) {
            for (std::size_t c = 0; c < cell_count; ++c) {
              const SweepCell& cell = cells[c];
              qr::Expected<qr::replay::DailyLedger, qr::Refusal> ledger = qr::m25::run_skill_cell(
                  draws, &tape, cell.q_skill, cell.horizon, cell.q_percent, cell.rho,
                  qr::m25::kDailyLossLimitCent);
              if (!ledger.has_value()) {
                std::lock_guard<std::mutex> guard(output_mutex);
                if (!failed.exchange(true)) {
                  first_refusal = ledger.error();
                }
                return;
              }
              sweep_net[static_cast<std::size_t>(replicate)][c * session_count + index] =
                  ledger.value().net_cent;
              sweep_trades[static_cast<std::size_t>(replicate)][c * session_count + index] =
                  static_cast<std::int32_t>(ledger.value().trade_count());
            }
          }

          if (do_twins && replicate == 0) {
            std::size_t width = 0;
            qr::Expected<std::vector<float>, qr::Refusal> prefix =
                qr::m25::load_prefix_matrix(root, tape, &width);
            if (!prefix.has_value()) {
              std::lock_guard<std::mutex> guard(output_mutex);
              if (!failed.exchange(true)) {
                first_refusal = prefix.error();
              }
              return;
            }
            std::ostringstream ladder;
            std::ostringstream pool;
            for (const std::int64_t bucket : qr::m25::kTwinBucketSeconds) {
              const qr::m25::TwinAccumulator accumulated =
                  qr::m25::accumulate_twins(tape, draws, prefix.value(), width, bucket);
              for (std::size_t k = 0; k < qr::m25::kTwinLadderDepth; ++k) {
                for (std::size_t h = 0; h < kHorizonCount; ++h) {
                  ladder << ordinal << '\t' << bucket << '\t' << k << '\t' << h << '\t'
                         << accumulated.pair_count[k] << '\t'
                         << to_string_exact(accumulated.distance_sum[k]) << '\t'
                         << to_string_exact(accumulated.gap_sq_sum[k][h]) << '\t'
                         << accumulated.disjoint_pair_count[k][h] << '\t'
                         << to_string_exact(accumulated.disjoint_distance_sum[k][h]) << '\t'
                         << to_string_exact(accumulated.disjoint_gap_sq_sum[k][h]) << '\n';
                }
              }
              for (std::size_t h = 0; h < kHorizonCount; ++h) {
                pool << ordinal << '\t' << bucket << '\t' << h << '\t' << accumulated.all_pair_count
                     << '\t' << to_string_exact(accumulated.all_gap_sq_sum[h]) << '\t'
                     << accumulated.z_row_count << '\t'
                     << to_string_exact(accumulated.z_centred_sq_sum[h]) << '\t'
                     << accumulated.cell_count << '\t' << accumulated.rows_in_cells << '\t'
                     << accumulated.exact_key_twin_pairs << '\t'
                     << accumulated.all_disjoint_pair_count[h] << '\t'
                     << to_string_exact(accumulated.all_disjoint_gap_sq_sum[h]) << '\n';
              }
            }
            twin_ladder_rows[index] = ladder.str();
            twin_pool_rows[index] = pool.str();
          }
        }
      }
    }
  };

  std::vector<std::thread> pool;
  pool.reserve(static_cast<std::size_t>(options.threads));
  for (int t = 0; t < options.threads; ++t) {
    pool.emplace_back(worker);
  }
  for (std::thread& thread : pool) {
    thread.join();
  }
  if (failed.load()) {
    return fail(first_refusal);
  }

  const auto wall_end = std::chrono::steady_clock::now();
  const std::int64_t wall_ms =
      std::chrono::duration_cast<std::chrono::milliseconds>(wall_end - wall_start).count();

  auto write_text = [&](const char* name, const std::string& header,
                        const std::vector<std::string>& rows) {
    const std::filesystem::path path = options.out_dir / name;
    std::FILE* file = std::fopen(path.c_str(), "wb");
    if (file == nullptr) {
      return false;
    }
    std::fwrite(header.data(), 1, header.size(), file);
    for (const std::string& row : rows) {
      std::fwrite(row.data(), 1, row.size(), file);
    }
    std::fclose(file);
    return true;
  };

  if (!write_text("sessions.tsv",
                  "fold\tsession\tday\tyear\trows\tclocks\tlong_rows\tshort_rows\tlabel_ok\t"
                  "label_entry_unavailable\tlabel_exit_unavailable\n",
                  session_rows)) {
    std::fprintf(stderr, "cannot write sessions.tsv\n");
    return 1;
  }
  if (do_arms &&
      !write_text("arms.tsv",
                  "fold\tarm\thorizon\tdaily_loss_limit_cent\tsession\tyear\tnet_cent\ttrades\t"
                  "breaches\tmax_mae_cent\thalted\tclocks\tentered\toccupied\tno_fresh_fill\t"
                  "override_side_unavailable\tcoin_draws\n",
                  arm_rows)) {
    std::fprintf(stderr, "cannot write arms.tsv\n");
    return 1;
  }
  if (do_twins) {
    if (!write_text("twins_ladder.tsv",
                    "session\tbucket_seconds\tk\thorizon\tpairs\tdistance_sum\tgap_sq_sum\t"
                    "disjoint_pairs\tdisjoint_distance_sum\tdisjoint_gap_sq_sum\n",
                    twin_ladder_rows) ||
        !write_text("twins_pool.tsv",
                    "session\tbucket_seconds\thorizon\tall_pairs\tall_gap_sq_sum\tz_rows\t"
                    "z_centred_sq_sum\tcells\trows_in_cells\texact_key_twin_pairs\t"
                    "all_disjoint_pairs\tall_disjoint_gap_sq_sum\n",
                    twin_pool_rows)) {
      std::fprintf(stderr, "cannot write the twin receipts\n");
      return 1;
    }
  }

  if (do_sweep) {
    {
      std::vector<std::string> rows;
      rows.reserve(cell_count);
      for (std::size_t c = 0; c < cell_count; ++c) {
        std::ostringstream row;
        row << c << '\t' << to_string_exact(cells[c].q_skill) << '\t' << cells[c].horizon << '\t'
            << cells[c].q_percent << '\t' << to_string_exact(cells[c].rho) << '\n';
        rows.push_back(row.str());
      }
      write_text("sweep_cells.tsv", "cell\tq_skill\thorizon\tq_percent\trho\n", rows);
    }
    {
      std::vector<std::string> rows;
      rows.reserve(session_count);
      for (std::size_t s = 0; s < session_count; ++s) {
        std::ostringstream row;
        row << s << '\t' << sessions[s] << '\n';
        rows.push_back(row.str());
      }
      write_text("sweep_sessions.tsv", "index\tsession\n", rows);
    }
    for (std::int64_t replicate = 0; replicate < options.replicates; ++replicate) {
      const std::string suffix = "_r" + std::to_string(replicate) + ".bin";
      const std::filesystem::path net_path = options.out_dir / ("sweep_net_cent" + suffix);
      std::FILE* file = std::fopen(net_path.c_str(), "wb");
      if (file == nullptr) {
        std::fprintf(stderr, "cannot write %s\n", net_path.c_str());
        return 1;
      }
      const std::vector<std::int64_t>& net = sweep_net[static_cast<std::size_t>(replicate)];
      std::fwrite(net.data(), sizeof(std::int64_t), net.size(), file);
      std::fclose(file);

      const std::filesystem::path trade_path = options.out_dir / ("sweep_trades" + suffix);
      file = std::fopen(trade_path.c_str(), "wb");
      if (file == nullptr) {
        std::fprintf(stderr, "cannot write %s\n", trade_path.c_str());
        return 1;
      }
      const std::vector<std::int32_t>& trades = sweep_trades[static_cast<std::size_t>(replicate)];
      std::fwrite(trades.data(), sizeof(std::int32_t), trades.size(), file);
      std::fclose(file);
    }
  }

  {
    std::vector<std::string> rows;
    auto add = [&rows](const std::string& metric, const std::string& value) {
      rows.push_back("run\t" + metric + "\t" + value + "\n");
    };
    add("schema", "qr_m25_run_v1");
    add("card_sha256", options.card_sha);
    add("run_dir", options.run_dir.string());
    add("fold", qr::m25::fold_name(options.fold));
    add("mode", options.mode);
    add("sessions", std::to_string(session_count));
    add("first_session", std::to_string(sessions.front()));
    add("last_session", std::to_string(sessions.back()));
    add("threads", std::to_string(options.threads));
    add("replicates", std::to_string(options.replicates));
    add("sweep_cells", std::to_string(cell_count));
    add("daily_loss_limit_cent", std::to_string(qr::m25::kDailyLossLimitCent));
    add("horizon_ref_index", std::to_string(qr::m25::kHorizonRefIndex));
    add("m25_seed_tag", std::to_string(qr::m25::kM25Tag));
    add("twin_ladder_depth", std::to_string(qr::m25::kTwinLadderDepth));
    add("twin_cell_cap", std::to_string(qr::m25::kTwinCellCap));
    std::string buckets;
    for (const std::int64_t bucket : qr::m25::kTwinBucketSeconds) {
      buckets += (buckets.empty() ? "" : ",") + std::to_string(bucket);
    }
    add("twin_bucket_seconds", buckets);
    add("wall_ms", std::to_string(wall_ms));
    write_text("run.tsv", "section\tmetric\tvalue\n", rows);
  }

  std::fprintf(stdout, "qr_m25_run: fold=%s sessions=%zu cells=%zu wall_ms=%lld\n",
               qr::m25::fold_name(options.fold), session_count, cell_count,
               static_cast<long long>(wall_ms));
  return 0;
}
