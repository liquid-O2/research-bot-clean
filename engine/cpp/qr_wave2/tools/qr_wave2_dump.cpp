// qr_wave2_dump — THE D-020 PACK DUMP for W2.13 + W2.2.
//
// The census (qr_wave2_census) proves the two families construct and publishes
// presence counts and a digest. A CASE PACK needs the other half: the ACTUAL 22
// channel values at ONE decision second. This tool is the same pathway, the
// same constructors and the same warmup law, with the values printed instead of
// folded into a counter.
//
// It is census-style: read-only, no wall-clock value in the output, %.17g for
// every double, so two runs of the same arguments are byte-identical.
//
// TWO MODES, because the prior history is history-INDEPENDENT per session.
// `SessionSummary` is a full-session reduction that never reads the history
// (session_pass.hpp: "The summary is always computed the same way for a warmup
// and a scoped session"), so the expensive per-session pass can be computed in
// parallel and replayed in calendar order afterwards. The replay is exactly the
// census's own loop: observe every strictly-prior ordinal, then take
// `history.view_for(history.size())` for the session under construction.
//
//   summaries --from A --to B --out FILE
//       One row per ordinal in [A,B]. Ordinals 0..124 go through WarmupScope
//       (CC-012), 125+ through DayScope, exactly as the census does.
//
//   values --summaries FILE --ordinal N --seconds LIST --out FILE
//       Replays the summaries for 0..N-1 into PriorSessionHistory, runs ONE
//       retained pass on N, and prints the 8 W2.2 + 14 W2.13 channels for every
//       requested grid endpoint and BOTH sides.
//
// THE SUMMARY CROSS-CHECK. The session under construction computes its own
// summary live; if the cached row for the SAME ordinal disagrees in any field,
// the tool refuses. A stale or mismatched summaries file can therefore never
// silently change a pack's numbers.
#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "qr_clock/session_clock.hpp"
#include "qr_registry/day_scope.hpp"
#include "qr_registry/registry.hpp"
#include "qr_registry/warmup_scope.hpp"
#include "qr_wave2/prior_structure.hpp"
#include "qr_wave2/session_pass.hpp"
#include "qr_wave2/variance_budget.hpp"

namespace {

[[noreturn]] void die(const std::string& message) {
  std::fprintf(stderr, "qr_wave2_dump: %s\n", message.c_str());
  std::exit(1);
}

/// The first scoped ordinal; below it a session is a CC-012 warmup ordinal.
constexpr std::int64_t kFirstScopedOrdinal = 125;

struct SummaryRow {
  qr::wave2::SessionSummary summary;
  std::string day;
};

void print_summary(std::FILE* out, const qr::wave2::SessionSummary& s, const std::string& day) {
  std::fprintf(out,
               "summary\t%" PRId64 "\t%s\t%" PRId64 "\t%" PRId64 "\t%" PRId64 "\t%d\t%" PRId64
               "\t%d\t%.17g\t%" PRId64 "\t%" PRId64 "\n",
               s.ordinal, day.c_str(), s.high_u6, s.low_u6, s.close_u6, s.grid_present ? 1 : 0,
               s.vwap_u6, s.vwap_present ? 1 : 0, s.rth_sum_r2, s.rth_seconds, s.valid_steps);
}

std::vector<SummaryRow> read_summaries(const std::string& path) {
  std::FILE* in = std::fopen(path.c_str(), "rb");
  if (in == nullptr) {
    die("cannot open summaries file " + path);
  }
  std::vector<SummaryRow> rows;
  char line[1024];
  while (std::fgets(line, sizeof(line), in) != nullptr) {
    if (std::strncmp(line, "summary\t", 8) != 0) {
      continue;
    }
    SummaryRow row;
    char day[64];
    int grid_present = 0;
    int vwap_present = 0;
    const int fields = std::sscanf(
        line,
        "summary\t%" SCNd64 "\t%63s\t%" SCNd64 "\t%" SCNd64 "\t%" SCNd64 "\t%d\t%" SCNd64
        "\t%d\t%lf\t%" SCNd64 "\t%" SCNd64,
        &row.summary.ordinal, day, &row.summary.high_u6, &row.summary.low_u6,
        &row.summary.close_u6, &grid_present, &row.summary.vwap_u6, &vwap_present,
        &row.summary.rth_sum_r2, &row.summary.rth_seconds, &row.summary.valid_steps);
    if (fields != 11) {
      die("malformed summary row in " + path);
    }
    row.summary.grid_present = grid_present != 0;
    row.summary.vwap_present = vwap_present != 0;
    row.day = day;
    rows.push_back(row);
  }
  std::fclose(in);
  return rows;
}

bool same_summary(const qr::wave2::SessionSummary& a, const qr::wave2::SessionSummary& b) {
  return a.ordinal == b.ordinal && a.high_u6 == b.high_u6 && a.low_u6 == b.low_u6 &&
         a.close_u6 == b.close_u6 && a.grid_present == b.grid_present && a.vwap_u6 == b.vwap_u6 &&
         a.vwap_present == b.vwap_present && a.rth_sum_r2 == b.rth_sum_r2 &&
         a.rth_seconds == b.rth_seconds && a.valid_steps == b.valid_steps;
}

std::vector<std::int64_t> parse_list(const std::string& text) {
  std::vector<std::int64_t> out;
  std::size_t start = 0;
  while (start <= text.size()) {
    const std::size_t comma = text.find(',', start);
    const std::string token =
        text.substr(start, comma == std::string::npos ? std::string::npos : comma - start);
    if (!token.empty()) {
      out.push_back(std::strtoll(token.c_str(), nullptr, 10));
    }
    if (comma == std::string::npos) {
      break;
    }
    start = comma + 1;
  }
  return out;
}

int usage() {
  std::fprintf(stderr,
               "usage: qr_wave2_dump summaries --from A --to B --out FILE\n"
               "       qr_wave2_dump values --summaries FILE --ordinal N --seconds LIST"
               " --out FILE\n"
               "       [--quotes-root DIR] [--trades-root DIR]\n");
  return 2;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) {
    return usage();
  }
  const std::string mode = argv[1];
  std::string quotes_root = "/workspace/data/tokens/stock_quotes/IWM";
  std::string trades_root = "/workspace/data/tokens/stock_trades/IWM";
  std::string summaries_path;
  std::string out_path;
  std::string seconds_text;
  std::int64_t from = -1;
  std::int64_t to = -1;
  std::int64_t ordinal = -1;
  for (int index = 2; index < argc; ++index) {
    const std::string flag = argv[index];
    const auto next = [&]() -> std::string {
      if (index + 1 >= argc) {
        die("missing value for " + flag);
      }
      return argv[++index];
    };
    if (flag == "--quotes-root") {
      quotes_root = next();
    } else if (flag == "--trades-root") {
      trades_root = next();
    } else if (flag == "--summaries") {
      summaries_path = next();
    } else if (flag == "--out") {
      out_path = next();
    } else if (flag == "--seconds") {
      seconds_text = next();
    } else if (flag == "--from") {
      from = std::stoll(next());
    } else if (flag == "--to") {
      to = std::stoll(next());
    } else if (flag == "--ordinal") {
      ordinal = std::stoll(next());
    } else {
      return usage();
    }
  }
  if (out_path.empty()) {
    return usage();
  }

  auto registry = qr::Registry::load_embedded();
  if (!registry.has_value()) {
    die(std::string("registry: ") + registry.error().message());
  }
  qr::wave2::CorpusRoots roots;
  roots.stock_quotes = quotes_root;
  roots.stock_trades = trades_root;

  std::FILE* out = std::fopen(out_path.c_str(), "wb");
  if (out == nullptr) {
    die("cannot write " + out_path);
  }

  if (mode == "summaries") {
    if (from < 0 || to < from) {
      return usage();
    }
    std::fprintf(out, "# qr_wave2_dump summaries (SessionSummary, prior_state.hpp)\n");
    std::fprintf(out,
                 "# kind\tordinal\tday\thigh_u6\tlow_u6\tclose_u6\tgrid_present\tvwap_u6\t"
                 "vwap_present\trth_sum_r2\trth_seconds\tvalid_steps\n");
    for (std::int64_t o = from; o <= to; ++o) {
      if (o < kFirstScopedOrdinal) {
        auto scope = qr::WarmupScope::admit(registry.value(), o);
        if (!scope.has_value()) {
          die("warmup scope " + std::to_string(o) + ": " + scope.error().message());
        }
        auto pass = qr::wave2::run_pass(scope.value(), roots);
        if (!pass.has_value()) {
          die("warmup pass " + std::to_string(o) + ": " + pass.error().message());
        }
        print_summary(out, pass.value().summary, scope.value().day());
      } else {
        auto scope = qr::DayScope::admit(registry.value(), o);
        if (!scope.has_value()) {
          die("scope " + std::to_string(o) + ": " + scope.error().message());
        }
        auto pass = qr::wave2::run_pass(scope.value(), roots, /*retain_series=*/false);
        if (!pass.has_value()) {
          die("pass " + std::to_string(o) + ": " + pass.error().message());
        }
        print_summary(out, pass.value().summary, scope.value().day());
      }
    }
    std::fclose(out);
    return 0;
  }

  if (mode != "values") {
    return usage();
  }
  if (summaries_path.empty() || ordinal < 0 || seconds_text.empty()) {
    return usage();
  }
  // THE DECISION-PATH GUARD, before any path is formed.
  if (!qr::wave2::admit_decision_ordinal(ordinal).has_value()) {
    die("ordinal " + std::to_string(ordinal) + " may not carry decisions");
  }

  const std::vector<SummaryRow> cached = read_summaries(summaries_path);
  qr::wave2::PriorSessionHistory history;
  std::int64_t expected = 0;
  const qr::wave2::SessionSummary* cached_self = nullptr;
  for (const SummaryRow& row : cached) {
    if (row.summary.ordinal == ordinal) {
      cached_self = &row.summary;
    }
    if (row.summary.ordinal >= ordinal) {
      continue;
    }
    if (row.summary.ordinal != expected) {
      die("summaries are not the contiguous calendar prefix: expected ordinal " +
          std::to_string(expected) + ", found " + std::to_string(row.summary.ordinal));
    }
    if (!history.observe(row.summary).has_value()) {
      die("history refused ordinal " + std::to_string(row.summary.ordinal));
    }
    ++expected;
  }
  if (expected != ordinal) {
    die("summaries stop at ordinal " + std::to_string(expected) + ", need " +
        std::to_string(ordinal));
  }

  auto scope = qr::DayScope::admit(registry.value(), ordinal);
  if (!scope.has_value()) {
    die("scope " + std::to_string(ordinal) + ": " + scope.error().message());
  }
  auto clock = qr::SessionClock::from_session(scope.value().session());
  if (!clock.has_value()) {
    die("clock " + std::to_string(ordinal) + ": " + clock.error().message());
  }
  auto pass = qr::wave2::run_pass(scope.value(), roots, /*retain_series=*/true);
  if (!pass.has_value()) {
    die("pass " + std::to_string(ordinal) + ": " + pass.error().message());
  }
  if (cached_self != nullptr && !same_summary(*cached_self, pass.value().summary)) {
    die("the cached summary for ordinal " + std::to_string(ordinal) +
        " disagrees with the live pass");
  }

  const qr::wave2::PriorView priors = history.view_for(history.size());
  qr::wave2::VarianceBudgetInputs inputs;
  inputs.grid = &pass.value().grid;
  inputs.stock_print_groups = pass.value().stock_print_groups;
  inputs.vwap_notional_prefix = pass.value().vwap_notional_prefix;
  inputs.vwap_size_prefix = pass.value().vwap_size_prefix;
  inputs.priors = priors;
  auto budget = qr::wave2::VarianceBudgetSession::build(inputs);
  if (!budget.has_value()) {
    die("budget " + std::to_string(ordinal) + ": " + budget.error().message());
  }

  const std::int64_t session_seconds = scope.value().bar_count() * 60;
  const auto open = budget.value().open_u6();

  std::fprintf(out, "# qr_wave2_dump values (W2.13-PIN-1 + W2.2-PIN-1, CC-012 warmup)\n");
  std::fprintf(out, "session\tordinal\t%" PRId64 "\n", ordinal);
  std::fprintf(out, "session\tday\t%s\n", scope.value().day().c_str());
  std::fprintf(out, "session\tsession_start_ns\t%" PRId64 "\n", clock.value().session_start_a().ns());
  std::fprintf(out, "session\tsession_seconds\t%" PRId64 "\n", session_seconds);
  std::fprintf(out, "session\tendpoints\t%" PRId64 "\n",
               static_cast<std::int64_t>(budget.value().endpoints()));
  std::fprintf(out, "session\tpriors_available\t%" PRId64 "\n", priors.priors_available);
  std::fprintf(out, "session\tatr_present\t%d\n", priors.atr_present ? 1 : 0);
  std::fprintf(out, "session\tatr14_bps\t%.17g\n", priors.atr14_bps);
  std::fprintf(out, "session\trv_prior_present\t%d\n", priors.rv_prior_present ? 1 : 0);
  std::fprintf(out, "session\trv_prior_rate\t%.17g\n", priors.rv_prior_rate);
  std::fprintf(out, "session\trv_prior_total\t%.17g\n", priors.rv_prior_total);
  std::fprintf(out, "session\tprior_present\t%d\n", priors.prior_present ? 1 : 0);
  std::fprintf(out, "session\tprior_high_u6\t%" PRId64 "\n", priors.prior_high_u6);
  std::fprintf(out, "session\tprior_low_u6\t%" PRId64 "\n", priors.prior_low_u6);
  std::fprintf(out, "session\tprior_close_u6\t%" PRId64 "\n", priors.prior_close_u6);
  std::fprintf(out, "session\tprior_vwap_present\t%d\n", priors.prior_vwap_present ? 1 : 0);
  std::fprintf(out, "session\tprior_vwap_u6\t%" PRId64 "\n", priors.prior_vwap_u6);
  std::fprintf(out, "session\trange5_present\t%d\n", priors.range5_present ? 1 : 0);
  std::fprintf(out, "session\thigh5_u6\t%" PRId64 "\n", priors.high5_u6);
  std::fprintf(out, "session\tlow5_u6\t%" PRId64 "\n", priors.low5_u6);
  std::fprintf(out, "session\trange20_present\t%d\n", priors.range20_present ? 1 : 0);
  std::fprintf(out, "session\thigh20_u6\t%" PRId64 "\n", priors.high20_u6);
  std::fprintf(out, "session\tlow20_u6\t%" PRId64 "\n", priors.low20_u6);
  std::fprintf(out, "session\topen_present\t%d\n", open.v == qr::Validity::VALID ? 1 : 0);
  std::fprintf(out, "session\topen_u6\t%" PRId64 "\n", open.value);

  for (const std::int64_t second : parse_list(seconds_text)) {
    if (second < 0 || second >= static_cast<std::int64_t>(budget.value().endpoints())) {
      die("second " + std::to_string(second) + " is outside this session's grid");
    }
    const auto endpoint = static_cast<std::size_t>(second);
    for (const qr::wave2::Side side : {qr::wave2::Side::LONG, qr::wave2::Side::SHORT}) {
      const char* side_name = side == qr::wave2::Side::LONG ? "L" : "S";
      const qr::wave2::VarianceBudgetRow vb = budget.value().channels(endpoint, side);

      qr::wave2::PriorStructureInputs structure;
      structure.side = side;
      const auto& point = pass.value().grid.points()[endpoint];
      structure.m_u6 = point.mid_u6;
      structure.m_present = point.present;
      structure.open_u6 = open.value;
      structure.open_present = open.v == qr::Validity::VALID;
      const auto vwap = budget.value().running_vwap_u6(endpoint);
      structure.intraday_vwap_u6 = vwap.value;
      structure.intraday_vwap_present = vwap.v == qr::Validity::VALID;
      const auto phase = qr::wave2::phase_fraction(second, session_seconds);
      structure.phase = phase.value;
      structure.phase_present = phase.v == qr::Validity::VALID;
      const auto sigma_scale = budget.value().sigma_scale_bps(endpoint);
      structure.sigma_scale_bps = sigma_scale.value;
      structure.sigma_scale_present = sigma_scale.v == qr::Validity::VALID;
      structure.priors = priors;
      const qr::wave2::PriorStructureRow ps = qr::wave2::build_prior_structure(structure);

      std::fprintf(out, "point\t%" PRId64 "\t%s\tmid_u6\t%" PRId64 "\t%d\n", second, side_name,
                   point.mid_u6, point.present ? 1 : 0);
      std::fprintf(out, "point\t%" PRId64 "\t%s\tintraday_vwap_u6\t%" PRId64 "\t%d\n", second,
                   side_name, vwap.value, vwap.v == qr::Validity::VALID ? 1 : 0);
      std::fprintf(out, "point\t%" PRId64 "\t%s\tsigma_scale_bps\t%.17g\t%d\n", second, side_name,
                   sigma_scale.value, sigma_scale.v == qr::Validity::VALID ? 1 : 0);
      std::fprintf(out, "point\t%" PRId64 "\t%s\tphase\t%.17g\t%d\n", second, side_name,
                   phase.value, phase.v == qr::Validity::VALID ? 1 : 0);
      for (std::size_t channel = 0; channel < qr::wave2::kVarianceBudgetChannelCount; ++channel) {
        std::fprintf(out, "w2_2\t%" PRId64 "\t%s\t%s\t%.17g\t%s\n", second, side_name,
                     qr::wave2::variance_budget_channel_name(channel), vb.value[channel],
                     qr::validity_name(vb.validity[channel]));
      }
      for (std::size_t channel = 0; channel < qr::wave2::kPriorStructureChannelCount; ++channel) {
        std::fprintf(out, "w2_13\t%" PRId64 "\t%s\t%s\t%.17g\t%s\n", second, side_name,
                     qr::wave2::prior_structure_channel_name(channel), ps.value[channel],
                     qr::validity_name(ps.validity[channel]));
      }
    }
  }
  std::fclose(out);
  return 0;
}
