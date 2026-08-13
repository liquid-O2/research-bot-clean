// qr_gen_build — the S2 production driver (PORT_M1B_SPEC §1 S2).
//
//   qr_gen_build --asset SI --sessions <dir> --out <dir> --sanity <stem>
//                --bars <path> --cost <path> --v1 <path> --fvol <path>
//
// ONE asset per invocation, sessions walked in DATE ORDER: the level ledger
// carries cross-session memory (creation dates, virginity, touch counts), so
// the session loop is inherently sequential and the parallelism lives ACROSS
// assets (three processes, inside the <= 4 worker cap). Output is one shard
// pair per calendar month, so peak memory is one month.
//
// Progress goes to stderr, one line per finished asset-month, which is the
// run.sh heartbeat contract.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <string>

#include "qr_gen/generate.hpp"

namespace {

using namespace qr::gen;  // NOLINT(build/namespaces) — tool-local

struct Args {
  std::string asset;
  std::string sessions;
  std::string out;
  std::string sanity;
  std::string bars;
  std::string cost;
  std::string v1;
  std::string fvol;
};

bool parse(int argc, char** argv, Args* a) {
  for (int i = 1; i < argc; ++i) {
    const std::string k = argv[i];
    const bool has_next = (i + 1 < argc);
    if (k == "--asset" && has_next) {
      a->asset = argv[++i];
    } else if (k == "--sessions" && has_next) {
      a->sessions = argv[++i];
    } else if (k == "--out" && has_next) {
      a->out = argv[++i];
    } else if (k == "--sanity" && has_next) {
      a->sanity = argv[++i];
    } else if (k == "--bars" && has_next) {
      a->bars = argv[++i];
    } else if (k == "--cost" && has_next) {
      a->cost = argv[++i];
    } else if (k == "--v1" && has_next) {
      a->v1 = argv[++i];
    } else if (k == "--fvol" && has_next) {
      a->fvol = argv[++i];
    } else {
      std::fprintf(stderr, "unknown or incomplete argument: %s\n", k.c_str());
      return false;
    }
  }
  return !a->asset.empty() && !a->sessions.empty() && !a->out.empty() && !a->bars.empty() &&
         !a->cost.empty() && !a->v1.empty() && !a->fvol.empty();
}

}  // namespace

int main(int argc, char** argv) {
  Args a;
  if (!parse(argc, argv, &a)) {
    std::fprintf(stderr,
                 "usage: qr_gen_build --asset SI --sessions <dir> --out <dir> "
                 "--bars <p> --cost <p> --v1 <p> --fvol <p> [--sanity <stem>]\n");
    return 2;
  }
  GenConfig cfg;
  if (!qr::futsess::asset_from_name(a.asset, &cfg.asset)) {
    std::fprintf(stderr, "unknown asset: %s\n", a.asset.c_str());
    return 2;
  }
  cfg.session_dir = a.sessions;
  cfg.out_dir = a.out;
  cfg.sanity_stem = a.sanity;
  cfg.bars_path = a.bars;
  cfg.cost_rollup_path = a.cost;
  cfg.v1_path = a.v1;
  cfg.fvol_path = a.fvol;

  const std::clock_t t0 = std::clock();
  auto res = generate_asset(cfg);
  if (!res) {
    std::fprintf(stderr, "REFUSED %s: %s\n", a.asset.c_str(), res.error().message().c_str());
    return 1;
  }
  const GenStats& st = res.value();
  const double secs = static_cast<double>(std::clock() - t0) / CLOCKS_PER_SEC;
  std::fprintf(stderr,
               "%s done: %lld candidates in %lld shards over %lld sessions "
               "(%lld with a ledger); g1_conf=%lld g2=%lld fast_open=%lld "
               "reclaim_bound_drops=%lld levels=%lld touches=%lld "
               "skip_close=%lld skip_insane=%lld insane=%lld/%lld bytes=%lld %.1fs\n",
               a.asset.c_str(), static_cast<long long>(st.n_candidates),
               static_cast<long long>(st.n_shards), static_cast<long long>(st.n_sessions),
               static_cast<long long>(st.n_sessions_with_ledger),
               static_cast<long long>(st.n_g1_confirmations),
               static_cast<long long>(st.n_g2_events),
               static_cast<long long>(st.n_fast_open_candidates),
               static_cast<long long>(st.n_g2_dropped_reclaim_bound),
               static_cast<long long>(st.n_levels), static_cast<long long>(st.n_touches),
               static_cast<long long>(st.n_skip_past_close),
               static_cast<long long>(st.n_skip_not_sane),
               static_cast<long long>(st.n_seconds_insane),
               static_cast<long long>(st.n_seconds_two_sided),
               static_cast<long long>(st.stored_bytes), secs);
  std::printf("%s\t%lld\t%lld\t%lld\n", a.asset.c_str(), static_cast<long long>(st.n_candidates),
              static_cast<long long>(st.n_records_f), static_cast<long long>(st.n_records_a));
  return 0;
}
