// qr_campaign_build — THE CAMPAIGN CORPUS-BUILD DRIVER (FINAL_PLAN.md §9 R2).
//
// One tool, three modes:
//
//   BUILD (default)   spec gate → roster stage → ordinal-ordered dispatch of one
//                     worker per session → campaign receipt with the manifest
//                     root hash. Each worker publishes both shards of its
//                     session through the APPENDIX C4 topology (a tagged
//                     FEATURE_BUILDER child, an untagged emit parent).
//   --rosters-only    stage 1 alone (what the probe gate runs first).
//   --compare-runs    byte-compares two run roots and diffs their manifests:
//                     the two-run identity verdict.
//
// WHY THE DISPATCHER FORKS RATHER THAN EXECS. A worker needs the embedded
// registry, the frozen card gate and the run layout — all of which the parent
// has already established. fork() hands them over without re-establishing them
// 625 times, and the child's own fork of the tagged constructor phase is
// unaffected by it.
//
// DETERMINISM UNDER PARALLELISM. Sessions are dispatched in ASCENDING ORDINAL
// ORDER and every published byte is a function of one session alone, so the
// worker count changes only the wall clock. The campaign receipt is assembled
// by READING the per-session receipts in ordinal order, never by appending in
// completion order — that is the ordinal-only merge law, and the fixture
// `CampaignLedger.IsOrdinalOrderedWhateverTheCompletionOrder` fires it.
//
// HEARTBEAT. One line per finished session on stderr, which is exactly what
// lab/run.sh appends to runs/<name>.hb: `done/total ordinal=... elapsed=...s
// rate=.../s eta=...s`. The launcher's stall detector reads its mtime.
#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>

#include <algorithm>
#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <fstream>
#include <map>
#include <string>
#include <vector>

#include "qr_campaign/driver.hpp"
#include "qr_campaign/session_build.hpp"
#include "qr_candidates/signal_root.hpp"

namespace {

using qr::campaign::BuildOptions;
using qr::campaign::Receipt;
using qr::campaign::RunLayout;
using qr::campaign::SessionTask;

int fail(const qr::Refusal& refusal) {
  std::fprintf(stderr, "REFUSED: %s\n", refusal.message().c_str());
  return 1;
}

double now_seconds() {
  struct ::timespec ts {};
  ::clock_gettime(CLOCK_MONOTONIC, &ts);
  return static_cast<double>(ts.tv_sec) + static_cast<double>(ts.tv_nsec) * 1e-9;
}

std::int64_t vm_hwm_kib() {
  std::ifstream status("/proc/self/status");
  std::string line;
  while (std::getline(status, line)) {
    if (line.rfind("VmHWM:", 0) == 0) {
      return std::strtoll(line.c_str() + 6, nullptr, 10);
    }
  }
  return -1;
}

/// The container's own memory counter — a kernel number, read by path, with no
/// process-name matching anywhere (the repo's fleet-control law). Negative when
/// the counter is not exposed, in which case the receipt says so rather than
/// guessing.
std::int64_t cgroup_memory_bytes() {
  for (const char* path : {"/sys/fs/cgroup/memory.current",
                           "/sys/fs/cgroup/memory/memory.usage_in_bytes"}) {
    std::ifstream input(path);
    std::int64_t value = 0;
    if (input && (input >> value)) {
      return value;
    }
  }
  return -1;
}

int usage() {
  std::fprintf(stderr,
               "usage: qr_campaign_build [--root DIR] [--run2] [--sessions all|LIST]\n"
               "                         [--workers N] [--resume] [--rosters-only]\n"
               "                         [--skip-publication-digests]\n"
               "       qr_campaign_build --compare-runs ROOT_A ROOT_B\n"
               "\n"
               "  --sessions  `all` (125..749), a comma list (`125,500,625`) or ranges\n"
               "              (`125-200`). The R1 probe object is `125,500,625`.\n"
               "  --run2      publish into <root>/run2 instead of <root>/run1.\n");
  return 2;
}

// ---------------------------------------------------------------------------
// --compare-runs: the two-run identity verdict
// ---------------------------------------------------------------------------

/// Files whose bytes are a function of the WALL CLOCK, not of the science.
bool is_timing_artifact(const std::string& relative) {
  return relative.rfind("receipts/timings/", 0) == 0 ||
         relative == "receipts/campaign_timing.tsv";
}

/// The fd-census receipts name the paths the constructor phase opened, which
/// include the run root itself. They are compared after that ONE substitution,
/// which is the only difference two lawful runs may have.
bool is_run_scoped_text(const std::string& relative) {
  return relative.rfind("receipts/builder_fd_census/", 0) == 0;
}

std::vector<std::string> list_files(const std::filesystem::path& root) {
  std::vector<std::string> out;
  std::error_code code;
  for (const std::filesystem::directory_entry& entry :
       std::filesystem::recursive_directory_iterator(root, code)) {
    if (entry.is_regular_file()) {
      out.push_back(entry.path().lexically_relative(root).generic_string());
    }
  }
  std::sort(out.begin(), out.end());
  return out;
}

std::string read_file(const std::filesystem::path& path) {
  std::ifstream input(path, std::ios::binary);
  return std::string((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
}

std::string normalize(std::string text, const std::string& root) {
  std::size_t at = 0;
  while ((at = text.find(root, at)) != std::string::npos) {
    text.replace(at, root.size(), "<RUN_ROOT>");
    at += 10;
  }
  return text;
}

int compare_runs(const std::filesystem::path& left_root, const std::filesystem::path& right_root) {
  const std::vector<std::string> left = list_files(left_root);
  const std::vector<std::string> right = list_files(right_root);
  std::vector<std::string> only_left;
  std::vector<std::string> only_right;
  std::set_difference(left.begin(), left.end(), right.begin(), right.end(),
                      std::back_inserter(only_left));
  std::set_difference(right.begin(), right.end(), left.begin(), left.end(),
                      std::back_inserter(only_right));

  std::int64_t compared = 0;
  std::int64_t identical = 0;
  std::int64_t skipped = 0;
  std::vector<std::string> differing;
  for (const std::string& relative : left) {
    if (!std::binary_search(right.begin(), right.end(), relative)) {
      continue;
    }
    if (is_timing_artifact(relative)) {
      ++skipped;
      continue;
    }
    ++compared;
    bool same = false;
    if (is_run_scoped_text(relative)) {
      same = normalize(read_file(left_root / relative), left_root.string()) ==
             normalize(read_file(right_root / relative), right_root.string());
    } else {
      auto a = qr::candidates::sha256_file_hex((left_root / relative).string());
      auto b = qr::candidates::sha256_file_hex((right_root / relative).string());
      same = a.has_value() && b.has_value() && a.value() == b.value();
    }
    if (same) {
      ++identical;
    } else {
      differing.push_back(relative);
    }
  }

  std::printf("compare\tleft\t%s\n", left_root.c_str());
  std::printf("compare\tright\t%s\n", right_root.c_str());
  std::printf("compare\tfiles_left\t%zu\n", left.size());
  std::printf("compare\tfiles_right\t%zu\n", right.size());
  std::printf("compare\tcompared\t%" PRId64 "\n", compared);
  std::printf("compare\tidentical\t%" PRId64 "\n", identical);
  std::printf("compare\tskipped_timing\t%" PRId64 "\n", skipped);
  std::printf("compare\tonly_left\t%zu\n", only_left.size());
  std::printf("compare\tonly_right\t%zu\n", only_right.size());
  std::printf("compare\tdiffering\t%zu\n", differing.size());
  for (std::size_t index = 0; index < differing.size() && index < 20; ++index) {
    std::printf("differ\t%s\n", differing[index].c_str());
    // A manifest that differs is worth showing line by line: it names the leaf.
    if (differing[index].size() >= 12 &&
        differing[index].compare(differing[index].size() - 12, 12, "manifest.tsv") == 0) {
      std::istringstream a(read_file(left_root / differing[index]));
      std::istringstream b(read_file(right_root / differing[index]));
      std::string line_a;
      std::string line_b;
      std::int64_t line = 0;
      std::int64_t shown = 0;
      while ((std::getline(a, line_a) || std::getline(b, line_b)) && shown < 5) {
        ++line;
        if (line_a != line_b) {
          std::printf("manifest_diff\t%s\t%" PRId64 "\tA=%s\tB=%s\n", differing[index].c_str(),
                      line, line_a.c_str(), line_b.c_str());
          ++shown;
        }
        line_a.clear();
        line_b.clear();
      }
    }
  }
  for (std::size_t index = 0; index < only_left.size() && index < 20; ++index) {
    std::printf("only_left\t%s\n", only_left[index].c_str());
  }
  for (std::size_t index = 0; index < only_right.size() && index < 20; ++index) {
    std::printf("only_right\t%s\n", only_right[index].c_str());
  }
  const bool identical_runs =
      differing.empty() && only_left.empty() && only_right.empty() && compared > 0;
  std::printf("compare\tverdict\t%s\n", identical_runs ? "BYTE_IDENTICAL" : "DIFFERENT");
  return identical_runs ? 0 : 1;
}

}  // namespace

int main(int argc, char** argv) {
  std::filesystem::path base(qr::campaign::kDefaultBaseRoot);
  std::string sessions_spec = "all";
  int run_index = 1;
  int workers = 12;
  bool resume = false;
  bool rosters_only = false;
  BuildOptions options;

  for (int index = 1; index < argc; ++index) {
    const std::string flag = argv[index];
    const bool has_value = index + 1 < argc;
    if (flag == "--root" && has_value) {
      base = argv[++index];
    } else if (flag == "--sessions" && has_value) {
      sessions_spec = argv[++index];
    } else if (flag == "--workers" && has_value) {
      workers = std::atoi(argv[++index]);
    } else if (flag == "--run2") {
      run_index = 2;
    } else if (flag == "--resume") {
      resume = true;
    } else if (flag == "--rosters-only") {
      rosters_only = true;
    } else if (flag == "--skip-publication-digests") {
      options.verify_publication_digests = false;
    } else if (flag == "--build-id" && has_value) {
      options.build_id = argv[++index];
    } else if (flag == "--compare-runs" && index + 2 < argc) {
      const std::filesystem::path left = argv[index + 1];
      const std::filesystem::path right = argv[index + 2];
      return compare_runs(left, right);
    } else {
      return usage();
    }
  }
  if (workers < 1 || workers > 64) {
    std::fprintf(stderr, "--workers must be 1..64\n");
    return 2;
  }

  // --- THE SPEC GATE, before a single path is formed ------------------------
  const qr::campaign::Status spec =
      qr::campaign::verify_frozen_spec(qr::campaign::kCardPath, qr::campaign::kCardSha256);
  if (!spec.has_value()) {
    return fail(spec.error());
  }

  auto sessions = qr::campaign::parse_session_list(sessions_spec);
  if (!sessions.has_value()) {
    return fail(sessions.error());
  }
  auto layout = qr::campaign::run_layout(base, run_index);
  if (!layout.has_value()) {
    return fail(layout.error());
  }
  const RunLayout run = layout.value();

  const double started = now_seconds();
  std::fprintf(stderr, "campaign start run=%d sessions=%zu workers=%d root=%s\n", run_index,
               sessions.value().size(), workers, run.root().c_str());

  // --- STAGE 1: the rosters -------------------------------------------------
  const double roster_started = now_seconds();
  const qr::campaign::Status rostered =
      qr::campaign::build_rosters(run, sessions.value(), options);
  if (!rostered.has_value()) {
    return fail(rostered.error());
  }
  const double roster_seconds = now_seconds() - roster_started;
  std::fprintf(stderr, "rosters done sessions=%zu seconds=%.1f\n", sessions.value().size(),
               roster_seconds);
  if (rosters_only) {
    std::printf("rosters\tsessions\t%zu\nrosters\tseconds\t%.3f\n", sessions.value().size(),
                roster_seconds);
    return 0;
  }

  // --- STAGE 2: ordinal-ordered dispatch ------------------------------------
  auto plan = qr::campaign::plan_tasks(run, sessions.value(), resume);
  if (!plan.has_value()) {
    return fail(plan.error());
  }
  const std::vector<SessionTask>& tasks = plan.value();

  std::map<::pid_t, std::size_t> inflight;
  std::map<std::size_t, double> started_at;
  std::size_t next = 0;
  std::size_t done = 0;
  std::int64_t failures = 0;
  std::int64_t peak_cgroup_bytes = 0;
  const double dispatch_started = now_seconds();

  while (next < tasks.size() || !inflight.empty()) {
    while (failures == 0 && inflight.size() < static_cast<std::size_t>(workers) &&
           next < tasks.size()) {
      const SessionTask& task = tasks[next];
      if (!task.any_work()) {
        std::fprintf(stderr, "skip ordinal=%lld (already published)\n",
                     static_cast<long long>(task.ordinal));
        ++next;
        ++done;
        continue;
      }
      const ::pid_t child = ::fork();
      if (child < 0) {
        std::fprintf(stderr, "REFUSED: cannot fork a session worker\n");
        failures += 1;
        break;
      }
      if (child == 0) {
        const qr::campaign::Status built = qr::campaign::build_session(run, task, options);
        if (!built.has_value()) {
          std::fprintf(stderr, "REFUSED (session %lld): %s\n",
                       static_cast<long long>(task.ordinal), built.error().message().c_str());
          ::_exit(12);
        }
        ::_exit(0);
      }
      inflight.emplace(child, next);
      started_at.emplace(next, now_seconds());
      ++next;
    }
    if (inflight.empty()) {
      break;
    }
    int status = 0;
    const ::pid_t finished = ::waitpid(-1, &status, WNOHANG);
    if (finished == 0) {
      const std::int64_t memory = cgroup_memory_bytes();
      peak_cgroup_bytes = std::max(peak_cgroup_bytes, memory);
      struct ::timespec pause {
        0, 200 * 1000 * 1000
      };
      ::nanosleep(&pause, nullptr);
      continue;
    }
    if (finished < 0) {
      if (errno == EINTR) {
        continue;
      }
      std::fprintf(stderr, "REFUSED: waitpid failed\n");
      failures += 1;
      break;
    }
    const auto entry = inflight.find(finished);
    if (entry == inflight.end()) {
      continue;
    }
    const std::size_t slot = entry->second;
    const SessionTask& task = tasks[slot];
    const double seconds = now_seconds() - started_at[slot];
    inflight.erase(entry);
    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) {
      std::fprintf(stderr, "FAILED ordinal=%lld exit=%d\n", static_cast<long long>(task.ordinal),
                   WIFEXITED(status) ? WEXITSTATUS(status) : -1);
      failures += 1;
      continue;
    }
    ++done;
    Receipt timing;
    timing.add("timing", "ordinal", task.ordinal);
    timing.add("timing", "seconds_milli", static_cast<std::int64_t>(seconds * 1000.0));
    const qr::campaign::Status written = timing.write(run.session_timing(task.ordinal));
    if (!written.has_value()) {
      return fail(written.error());
    }
    const double elapsed = now_seconds() - dispatch_started;
    const double rate = elapsed > 0.0 ? static_cast<double>(done) / elapsed : 0.0;
    const double eta = rate > 0.0 ? static_cast<double>(tasks.size() - done) / rate : 0.0;
    std::fprintf(stderr, "%zu/%zu ordinal=%lld session=%.1fs elapsed=%.1fs rate=%.2f/s eta=%.0fs\n",
                 done, tasks.size(), static_cast<long long>(task.ordinal), seconds, elapsed, rate,
                 eta);
  }

  const double dispatch_seconds = now_seconds() - dispatch_started;
  if (failures > 0) {
    std::fprintf(stderr, "campaign FAILED: %lld session(s) refused\n",
                 static_cast<long long>(failures));
    return 1;
  }

  // --- the campaign receipt (ordinal-ordered by construction) ---------------
  auto campaign = qr::campaign::render_campaign_receipt(run, sessions.value());
  if (!campaign.has_value()) {
    return fail(campaign.error());
  }
  {
    std::error_code code;
    std::filesystem::create_directories(run.receipts(), code);
    const std::filesystem::path path = run.receipts() / "campaign.tsv";
    const std::filesystem::path staged =
        run.receipts() / (".campaign.tsv.tmp-" + std::to_string(::getpid()));
    std::ofstream out(staged, std::ios::binary | std::ios::trunc);
    out << campaign.value();
    out.close();
    std::filesystem::rename(staged, path, code);
    if (code) {
      std::fprintf(stderr, "REFUSED: cannot publish the campaign receipt\n");
      return 1;
    }
  }

  struct ::rusage children {};
  ::getrusage(RUSAGE_CHILDREN, &children);
  Receipt timing;
  timing.add_text("timing", "schema", "qr_campaign_timing_v1");
  timing.add("timing", "run_index", run_index);
  timing.add("timing", "workers", workers);
  timing.add("timing", "sessions", static_cast<std::int64_t>(sessions.value().size()));
  timing.add("timing", "roster_seconds_milli", static_cast<std::int64_t>(roster_seconds * 1000.0));
  timing.add("timing", "dispatch_seconds_milli",
             static_cast<std::int64_t>(dispatch_seconds * 1000.0));
  timing.add("timing", "wall_seconds_milli",
             static_cast<std::int64_t>((now_seconds() - started) * 1000.0));
  timing.add("timing", "dispatcher_vm_hwm_kib", vm_hwm_kib());
  timing.add("timing", "max_single_worker_rss_kib", children.ru_maxrss);
  timing.add("timing", "peak_cgroup_memory_bytes", peak_cgroup_bytes);
  const qr::campaign::Status timing_written =
      timing.write(run.receipts() / "campaign_timing.tsv");
  if (!timing_written.has_value()) {
    return fail(timing_written.error());
  }

  std::fputs(campaign.value().c_str(), stdout);
  std::printf("timing\troster_seconds\t%.3f\n", roster_seconds);
  std::printf("timing\tdispatch_seconds\t%.3f\n", dispatch_seconds);
  std::printf("timing\twall_seconds\t%.3f\n", now_seconds() - started);
  std::printf("timing\tmax_single_worker_rss_kib\t%ld\n", children.ru_maxrss);
  std::printf("timing\tpeak_cgroup_memory_bytes\t%" PRId64 "\n", peak_cgroup_bytes);
  return 0;
}
