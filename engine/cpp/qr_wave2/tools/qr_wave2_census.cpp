// qr_wave2_census — THE REAL-PAYLOAD CENSUS FOR W2.13 AND W2.2.
//
// What it does, in one pass over the calendar:
//   1. CC-012 warmup: `WarmupScope` ordinals [warmup-from, warmup-to] are read
//      through the prior-state entry point ONLY, and folded into the history.
//      No decision, label or emission touches them, and the census records how
//      many warmup ordinals fed the families ("warmup ordinals fed per family
//      recorded").
//   2. Scoped sessions [scoped-from, scoped-to] are read with their series
//      retained, and both families' channels are constructed at a fixed stride
//      of grid endpoints for BOTH sides.
//   3. Per-channel presence censuses, the budget's own absence reasons, and a
//      FNV-1a digest of every produced value are printed as a TSV receipt.
//
// Two runs of the same arguments must produce byte-identical output — that is
// the two-run identity check the brief asks for, and it is why the iteration
// order is the calendar's own and every float is printed with %.17g.
//
// Roots (the corpus layout the WP8a probe documents):
//   --quotes-root /workspace/data/tokens/stock_quotes/IWM
//   --trades-root /workspace/data/tokens/stock_trades/IWM
#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "qr_registry/day_scope.hpp"
#include "qr_registry/registry.hpp"
#include "qr_registry/warmup_scope.hpp"
#include "qr_wave2/prior_structure.hpp"
#include "qr_wave2/session_pass.hpp"
#include "qr_wave2/variance_budget.hpp"
#include "wave2_guard.hpp"

namespace {

using qr::wave2::guard::Digest;

[[noreturn]] void die(const std::string& message) {
  std::fprintf(stderr, "qr_wave2_census: %s\n", message.c_str());
  std::exit(1);
}

struct Args {
  std::string quotes_root = "/workspace/data/tokens/stock_quotes/IWM";
  std::string trades_root = "/workspace/data/tokens/stock_trades/IWM";
  std::int64_t warmup_from = 0;
  std::int64_t warmup_to = 124;
  std::int64_t scoped_from = 125;
  std::int64_t scoped_to = 129;
  /// Endpoints between constructed decision rows (a whole session is 23,400).
  std::int64_t endpoint_stride = 600;
};

}  // namespace

int main(int argc, char** argv) {
  Args args;
  for (int index = 1; index < argc; ++index) {
    const std::string flag = argv[index];
    const auto next = [&]() -> std::string {
      if (index + 1 >= argc) {
        die("missing value for " + flag);
      }
      return argv[++index];
    };
    if (flag == "--quotes-root") {
      args.quotes_root = next();
    } else if (flag == "--trades-root") {
      args.trades_root = next();
    } else if (flag == "--warmup-from") {
      args.warmup_from = std::stoll(next());
    } else if (flag == "--warmup-to") {
      args.warmup_to = std::stoll(next());
    } else if (flag == "--scoped-from") {
      args.scoped_from = std::stoll(next());
    } else if (flag == "--scoped-to") {
      args.scoped_to = std::stoll(next());
    } else if (flag == "--endpoint-stride") {
      args.endpoint_stride = std::stoll(next());
    } else {
      die("unknown flag " + flag);
    }
  }

  auto registry = qr::Registry::load_embedded();
  if (!registry.has_value()) {
    die(std::string("registry: ") + registry.error().message());
  }
  qr::wave2::CorpusRoots roots;
  roots.stock_quotes = args.quotes_root;
  roots.stock_trades = args.trades_root;

  qr::wave2::PriorSessionHistory history;
  Digest digest;
  std::int64_t warmup_sessions_read = 0;
  std::int64_t warmup_grid_absent = 0;
  std::int64_t warmup_vwap_absent = 0;

  // --- 1. the CC-012 warmup -------------------------------------------------
  for (std::int64_t ordinal = args.warmup_from; ordinal <= args.warmup_to; ++ordinal) {
    auto scope = qr::WarmupScope::admit(registry.value(), ordinal);
    if (!scope.has_value()) {
      die("warmup scope " + std::to_string(ordinal) + ": " + scope.error().message());
    }
    auto pass = qr::wave2::run_pass(scope.value(), roots);
    if (!pass.has_value()) {
      die("warmup pass " + std::to_string(ordinal) + ": " + pass.error().message());
    }
    const qr::wave2::SessionSummary& summary = pass.value().summary;
    warmup_grid_absent += summary.grid_present ? 0 : 1;
    warmup_vwap_absent += summary.vwap_present ? 0 : 1;
    if (!history.observe(summary).has_value()) {
      die("warmup history refused ordinal " + std::to_string(ordinal));
    }
    ++warmup_sessions_read;
  }

  // --- 2. the scoped sessions -----------------------------------------------
  qr::wave2::PriorStructureCensus structure_census;
  qr::wave2::VarianceBudgetCensus budget_census;
  qr::wave2::VarianceBudgetSession::Census budget_audit{};
  std::int64_t decision_rows = 0;
  std::int64_t scoped_sessions_read = 0;
  std::vector<std::string> session_rows;

  for (std::int64_t ordinal = args.scoped_from; ordinal <= args.scoped_to; ++ordinal) {
    // THE DECISION-PATH GUARD, on the real loop: a scoped ordinal only.
    if (!qr::wave2::admit_decision_ordinal(ordinal).has_value()) {
      die("ordinal " + std::to_string(ordinal) + " may not carry decisions");
    }
    auto scope = qr::DayScope::admit(registry.value(), ordinal);
    if (!scope.has_value()) {
      die("scope " + std::to_string(ordinal) + ": " + scope.error().message());
    }
    auto pass = qr::wave2::run_pass(scope.value(), roots, /*retain_series=*/true);
    if (!pass.has_value()) {
      die("pass " + std::to_string(ordinal) + ": " + pass.error().message());
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
    std::int64_t session_rows_built = 0;
    for (std::size_t endpoint = 0; endpoint < budget.value().endpoints();
         endpoint += static_cast<std::size_t>(args.endpoint_stride)) {
      for (const qr::wave2::Side side : {qr::wave2::Side::LONG, qr::wave2::Side::SHORT}) {
        const qr::wave2::VarianceBudgetRow vb = budget.value().channels(endpoint, side);
        budget_census.fold(vb);

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
        const auto phase =
            qr::wave2::phase_fraction(static_cast<std::int64_t>(endpoint), session_seconds);
        structure.phase = phase.value;
        structure.phase_present = phase.v == qr::Validity::VALID;
        const auto sigma_scale = budget.value().sigma_scale_bps(endpoint);
        structure.sigma_scale_bps = sigma_scale.value;
        structure.sigma_scale_present = sigma_scale.v == qr::Validity::VALID;
        structure.priors = priors;
        const qr::wave2::PriorStructureRow ps = qr::wave2::build_prior_structure(structure);
        structure_census.fold(ps);

        for (std::size_t channel = 0; channel < qr::wave2::kVarianceBudgetChannelCount;
             ++channel) {
          digest.feed_f64(vb.value[channel]);
          digest.feed_i64(static_cast<std::int64_t>(vb.validity[channel]));
        }
        for (std::size_t channel = 0; channel < qr::wave2::kPriorStructureChannelCount;
             ++channel) {
          digest.feed_f64(ps.value[channel]);
          digest.feed_i64(static_cast<std::int64_t>(ps.validity[channel]));
        }
        ++decision_rows;
        ++session_rows_built;
      }
    }

    const qr::wave2::VarianceBudgetSession::Census& audit = budget.value().census();
    budget_audit.endpoints += audit.endpoints;
    budget_audit.valid_steps += audit.valid_steps;
    budget_audit.budget_present += audit.budget_present;
    budget_audit.budget_absent_window += audit.budget_absent_window;
    budget_audit.budget_absent_no_valid_step += audit.budget_absent_no_valid_step;
    budget_audit.budget_absent_no_prior += audit.budget_absent_no_prior;

    char line[512];
    std::snprintf(line, sizeof(line),
                  "session\t%" PRId64 "\t%s\t%" PRId64 "\t%" PRId64 "\t%" PRId64 "\t%" PRId64
                  "\t%.17g\t%.17g\t%" PRId64 "\n",
                  ordinal, scope.value().day().c_str(), priors.priors_available,
                  static_cast<std::int64_t>(priors.atr_present ? 1 : 0), audit.budget_present,
                  audit.valid_steps, priors.atr14_bps, priors.rv_prior_rate, session_rows_built);
    session_rows.emplace_back(line);

    if (!history.observe(pass.value().summary).has_value()) {
      die("history refused scoped ordinal " + std::to_string(ordinal));
    }
    ++scoped_sessions_read;
  }

  // --- 3. the receipt -------------------------------------------------------
  std::printf("# qr_wave2_census (W2.13-PIN-1 + W2.2-PIN-1, CC-012 warmup)\n");
  std::printf("kind\tkey\tvalue\n");
  std::printf("scope\twarmup_sessions_read\t%" PRId64 "\n", warmup_sessions_read);
  std::printf("scope\twarmup_ordinals_fed\t%" PRId64 "\n", history.warmup_sessions());
  std::printf("scope\twarmup_grid_absent\t%" PRId64 "\n", warmup_grid_absent);
  std::printf("scope\twarmup_vwap_absent\t%" PRId64 "\n", warmup_vwap_absent);
  std::printf("scope\tscoped_sessions_read\t%" PRId64 "\n", scoped_sessions_read);
  std::printf("scope\tdecision_rows_built\t%" PRId64 "\n", decision_rows);
  std::printf("budget\tendpoints\t%" PRId64 "\n", budget_audit.endpoints);
  std::printf("budget\tvalid_1s_steps\t%" PRId64 "\n", budget_audit.valid_steps);
  std::printf("budget\tB_present_endpoints\t%" PRId64 "\n", budget_audit.budget_present);
  std::printf("budget\tB_absent_window_short\t%" PRId64 "\n", budget_audit.budget_absent_window);
  std::printf("budget\tB_absent_no_valid_step\t%" PRId64 "\n",
              budget_audit.budget_absent_no_valid_step);
  std::printf("budget\tB_absent_no_prior\t%" PRId64 "\n", budget_audit.budget_absent_no_prior);

  for (std::size_t channel = 0; channel < qr::wave2::kVarianceBudgetChannelCount; ++channel) {
    std::printf("w2_2_channel\t%s\t%" PRId64 "/%" PRId64 "\n",
                qr::wave2::variance_budget_channel_name(channel), budget_census.present[channel],
                budget_census.tokens);
  }
  for (std::size_t channel = 0; channel < qr::wave2::kPriorStructureChannelCount; ++channel) {
    std::printf("w2_13_channel\t%s\t%" PRId64 "/%" PRId64 "\n",
                qr::wave2::prior_structure_channel_name(channel),
                structure_census.present[channel], structure_census.tokens);
  }
  for (const std::string& row : session_rows) {
    std::fputs(row.c_str(), stdout);
  }
  std::printf("digest\tall_channel_values\t%s\n", digest.hex().c_str());
  return 0;
}
