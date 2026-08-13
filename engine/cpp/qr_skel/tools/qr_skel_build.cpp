// qr_skel_build — the S3 production driver (PORT_M1B_SPEC §1 S3).
//
//   qr_skel_build --asset SI --candidates <stem> --sessions <dir> --out <dir>
//                 [--workers N] [--chunk 512] [--months YYYYMM,...]
//
// One shard per (asset, month). Shards are independent: each worker thread
// owns its sessions and its output pair, so nothing is shared and two runs are
// byte-identical. Progress goes to stderr, one line per finished shard, which
// is the run.sh heartbeat contract.
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <map>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "qr_futsess/json.hpp"
#include "qr_skel/engine.hpp"

namespace {

using namespace qr::skel;  // NOLINT(build/namespaces) — tool-local

struct Args {
  std::string asset;
  std::string candidates;
  std::string sessions;
  std::string out;
  std::size_t workers = 4;
  std::size_t chunk = kChunkCandidates;
  std::vector<std::string> months;
};

bool parse(int argc, char** argv, Args* a) {
  for (int i = 1; i < argc; ++i) {
    const std::string k = argv[i];
    const bool has_next = (i + 1 < argc);
    if (k == "--asset" && has_next) {
      a->asset = argv[++i];
    } else if (k == "--candidates" && has_next) {
      a->candidates = argv[++i];
    } else if (k == "--sessions" && has_next) {
      a->sessions = argv[++i];
    } else if (k == "--out" && has_next) {
      a->out = argv[++i];
    } else if (k == "--workers" && has_next) {
      a->workers = static_cast<std::size_t>(std::atoi(argv[++i]));
    } else if (k == "--chunk" && has_next) {
      a->chunk = static_cast<std::size_t>(std::atoi(argv[++i]));
    } else if (k == "--months" && has_next) {
      std::string s = argv[++i];
      std::size_t p = 0;
      while (p <= s.size()) {
        const std::size_t c = s.find(',', p);
        const std::string tok = s.substr(p, (c == std::string::npos) ? std::string::npos : c - p);
        if (!tok.empty()) {
          a->months.push_back(tok);
        }
        if (c == std::string::npos) {
          break;
        }
        p = c + 1;
      }
    } else {
      std::fprintf(stderr, "unknown or incomplete argument: %s\n", k.c_str());
      return false;
    }
  }
  return !a->asset.empty() && !a->candidates.empty() && !a->sessions.empty() && !a->out.empty() &&
         a->workers >= 1 && a->workers <= 6;
}

}  // namespace

int main(int argc, char** argv) {
  Args args;
  if (!parse(argc, argv, &args)) {
    std::fprintf(stderr,
                 "usage: qr_skel_build --asset SI --candidates <stem> --sessions <dir> "
                 "--out <dir> [--workers 1..6] [--chunk N] [--months YYYYMM,...]\n");
    return 2;
  }
  qr::futsess::Asset asset;
  if (!qr::futsess::asset_from_name(args.asset, &asset)) {
    std::fprintf(stderr, "unknown asset %s\n", args.asset.c_str());
    return 2;
  }
  auto loaded = CandidateSet::load(args.candidates);
  if (!loaded) {
    std::fprintf(stderr, "REFUSED loading candidates: %s\n", loaded.error().message().c_str());
    return 1;
  }
  const CandidateSet set = std::move(loaded).value();
  if (set.asset != asset) {
    std::fprintf(stderr, "candidate receipt asset does not match --asset\n");
    return 1;
  }

  // Contiguous [lo, hi) per month; date8 is non-decreasing by CandidateSet law.
  struct Shard {
    std::string month;
    std::size_t lo, hi;
  };
  std::vector<Shard> shards;
  for (std::size_t i = 0; i < set.rows.size(); ++i) {
    char mk[8];
    std::snprintf(mk, sizeof(mk), "%06d", set.rows[i].date8 / 100);
    if (shards.empty() || shards.back().month != mk) {
      shards.push_back(Shard{mk, i, i + 1});
    } else {
      shards.back().hi = i + 1;
    }
  }
  if (!args.months.empty()) {
    std::vector<Shard> keep;
    for (const Shard& s : shards) {
      for (const std::string& m : args.months) {
        if (s.month == m) {
          keep.push_back(s);
          break;
        }
      }
    }
    shards.swap(keep);
  }

  const std::time_t t0 = std::time(nullptr);
  std::mutex mu;
  std::size_t next = 0;
  ShardStats total;
  bool failed = false;
  std::string first_error;

  auto worker = [&]() {
    for (;;) {
      std::size_t idx = 0;
      {
        std::lock_guard<std::mutex> g(mu);
        if (failed || next >= shards.size()) {
          return;
        }
        idx = next++;
      }
      const Shard& s = shards[idx];
      ShardOptions opt;
      opt.asset = asset;
      opt.session_dir = args.sessions;
      opt.out_stem = args.out + "/" + args.asset + "_" + s.month;
      opt.month = s.month;
      opt.chunk_candidates = args.chunk;
      auto r = build_shard(set, s.lo, s.hi, opt);
      std::lock_guard<std::mutex> g(mu);
      if (!r) {
        failed = true;
        if (first_error.empty()) {
          first_error = s.month + ": " + r.error().message();
        }
        return;
      }
      const ShardStats& st = r.value();
      total.n_candidates += st.n_candidates;
      total.n_sessions += st.n_sessions;
      total.n_refused_atr += st.n_refused_atr;
      total.n_refused_ladder += st.n_refused_ladder;
      total.n_unavailable_d0 += st.n_unavailable_d0;
      total.n_unavailable_d1 += st.n_unavailable_d1;
      total.n_records_f += st.n_records_f;
      total.n_records_a += st.n_records_a;
      total.stored_rows += st.stored_rows;
      total.stored_bytes += st.stored_bytes;
      if (st.max_live_anchor_rows > total.max_live_anchor_rows) {
        total.max_live_anchor_rows = st.max_live_anchor_rows;
      }
      std::fprintf(stderr, "%s %s rows=%lld sessions=%lld elapsed=%llds\n", args.asset.c_str(),
                   s.month.c_str(), static_cast<long long>(st.stored_rows),
                   static_cast<long long>(st.n_sessions),
                   static_cast<long long>(std::time(nullptr) - t0));
      std::fflush(stderr);
    }
  };

  const std::size_t nthreads =
      std::min(args.workers, shards.empty() ? std::size_t{1} : shards.size());
  std::vector<std::thread> pool;
  pool.reserve(nthreads);
  for (std::size_t i = 0; i < nthreads; ++i) {
    pool.emplace_back(worker);
  }
  for (std::thread& th : pool) {
    th.join();
  }
  if (failed) {
    std::fprintf(stderr, "REFUSED: %s\n", first_error.c_str());
    return 1;
  }

  qr::futsess::JsonWriter jw;
  jw.begin_object();
  jw.key("asset");
  jw.value_string(args.asset);
  jw.key("n_shards");
  jw.value_int(static_cast<std::int64_t>(shards.size()));
  jw.key("n_candidates_in");
  jw.value_int(static_cast<std::int64_t>(set.rows.size()));
  jw.key("n_candidates_stored");
  jw.value_int(total.n_candidates);
  jw.key("n_sessions");
  jw.value_int(total.n_sessions);
  jw.key("n_refused_atr");
  jw.value_int(total.n_refused_atr);
  jw.key("n_refused_ladder");
  jw.value_int(total.n_refused_ladder);
  jw.key("n_unavailable_d0");
  jw.value_int(total.n_unavailable_d0);
  jw.key("n_unavailable_d1");
  jw.value_int(total.n_unavailable_d1);
  jw.key("n_records_favorable");
  jw.value_int(total.n_records_f);
  jw.key("n_records_adverse");
  jw.value_int(total.n_records_a);
  jw.key("max_live_anchor_rows");
  jw.value_int(total.max_live_anchor_rows);
  jw.key("stored_bytes");
  jw.value_int(total.stored_bytes);
  jw.key("chunk_candidates");
  jw.value_int(static_cast<std::int64_t>(args.chunk));
  jw.key("workers");
  jw.value_int(static_cast<std::int64_t>(nthreads));
  jw.key("params_hash");
  jw.value_string(params_hash(asset, args.chunk));
  jw.key("elapsed_secs");
  jw.value_int(static_cast<std::int64_t>(std::time(nullptr) - t0));
  jw.end_object();
  const std::string rp = args.out + "/" + args.asset + "_run.receipt.json";
  std::FILE* fh = std::fopen(rp.c_str(), "wb");
  if (fh == nullptr) {
    std::fprintf(stderr, "cannot write run receipt %s\n", rp.c_str());
    return 1;
  }
  std::fwrite(jw.text().data(), 1, jw.text().size(), fh);
  std::fclose(fh);
  std::fprintf(stderr, "DONE %s shards=%zu rows=%lld elapsed=%llds\n", args.asset.c_str(),
               shards.size(), static_cast<long long>(total.stored_rows),
               static_cast<long long>(std::time(nullptr) - t0));
  return 0;
}
