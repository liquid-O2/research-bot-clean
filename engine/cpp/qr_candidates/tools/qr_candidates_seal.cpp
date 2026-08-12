// qr_candidates_seal — the WP6 real-data seal.
//
// WHAT IT DOES, in the order the task card requires:
//
//   1. verifies the pinned digest of every authority it will DECODE (the two
//      publication parquets and their session indices);
//   2. reads `t14_bounds.tsv` one byte at a time through the stop ordinal;
//   3. seals the ordinal-0..stop prefix of `event_signals.tsv` with the bounded
//      non-prefetch pread reader, checking every session's row count and
//      sequence root, and retaining exactly the requested session;
//   4. writes that session's safe leaf and hashes it;
//   5. builds that session's candidate roster by exact-joining the candidate
//      registry to the rowgroup-addressed raw projection and authenticating
//      every side from the sealed member signals;
//   6. writes a deterministic receipt plus the leaf, roster and census, so two
//      runs can be compared byte for byte.
//
// THE TWO FILES IT DOES NOT HASH. `event_signals.tsv` (14GB) and
// `t14_bounds.tsv` both continue past ordinal 749 into sessions this program is
// forbidden to read. Recomputing their whole-file digests would read exactly
// the bytes the wall exists to keep out, so this binary verifies their pinned
// BYTE SIZES, reads only the admitted prefix, and publishes a sha256 over
// precisely the bytes it consumed. Their pinned whole-file digests are
// authority-level facts, checked out of band and recorded in the receipt.
//
// usage:
//   qr_candidates_seal --out DIR [--stop 749] [--resolve 125] [--skip-parquet-digest]
#include <sys/stat.h>

#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <optional>
#include <string>
#include <vector>

#include "qr_candidates/prefix_reader.hpp"
#include "qr_candidates/roster.hpp"
#include "qr_candidates/rowgroup_table.hpp"
#include "qr_candidates/signal_root.hpp"

namespace {

using namespace qr;             // NOLINT(build/namespaces)
using namespace qr::candidates;  // NOLINT(build/namespaces)

// --- the bound authorities (task card V4 section 1) -------------------------
constexpr const char* kEventSignalsPath =
    "/workspace/artifacts/runs/e1_rel037_verified_event/event_publication/event_signals.tsv";
constexpr const char* kT14Path =
    "/workspace/artifacts/runs/e1_rel037_verified_event/event_publication/t14_bounds.tsv";
constexpr const char* kProjectionPath =
    "/workspace/artifacts/runs/events.4_stage_run/pub/truth_relation_projection.parquet";
constexpr const char* kProjectionIndexPath =
    "/workspace/artifacts/runs/events.4_stage_run/pub/truth_relation_projection_session_index.tsv";
constexpr const char* kRegistryPath =
    "/workspace/artifacts/runs/e6_registry_fresh/candidate_action_registry.parquet";
constexpr const char* kRegistryIndexPath =
    "/workspace/artifacts/runs/e6_registry_fresh/candidate_action_registry_session_index.tsv";

constexpr const char* kEventSignalsSha =
    "1941d5cbd068fb12a7d17a83a71671dcc6757f83ffd98dacb39f6c2cf8519419";
constexpr const char* kT14Sha =
    "8fe7049c465de312c8e283b7d4c319d82c04e19e2fbe9fd316e3b13d6e46fae8";
constexpr const char* kProjectionSha =
    "c41b889b24305a87149eb48089afc0b06470faa09e72f979f3a090b1c35cc322";
constexpr const char* kProjectionIndexSha =
    "f54cc08bcf7af04f7175afe7b224b57609439e7048c45c87d490c035a0af3556";
constexpr const char* kRegistrySha =
    "f7a9a4d4b9b83fac467044251ec1947ef0019fae69113c2911291f74af2a9d71";
constexpr const char* kRegistryIndexSha =
    "827b72e0f91e10824050653f82e140bd98d1ea1fefd6bd657acf3280ef2587d8";

/// The kernel may not report more read bytes than the ledger requested; this is
/// the slack allowed for reading /proc/self/io itself.
constexpr std::uint64_t kIoSlackBytes = 1U << 20U;

[[noreturn]] void die(const std::string& what) {
  std::fprintf(stderr, "qr_candidates_seal: %s\n", what.c_str());
  std::exit(1);
}

void die_on_refusal(const Refusal& refusal, const char* what) {
  die(std::string(what) + ": " + refusal.message());
}

std::uint64_t vm_hwm_kib() {
  std::FILE* file = std::fopen("/proc/self/status", "rb");
  if (file == nullptr) {
    return 0;
  }
  char line[256];
  std::uint64_t out = 0;
  while (std::fgets(line, sizeof(line), file) != nullptr) {
    unsigned long long value = 0;
    if (std::sscanf(line, "VmHWM: %llu", &value) == 1) {
      out = value;
      break;
    }
  }
  std::fclose(file);
  return out;
}

double now_seconds() {
  struct ::timespec ts {};
  ::clock_gettime(CLOCK_MONOTONIC, &ts);
  return static_cast<double>(ts.tv_sec) + static_cast<double>(ts.tv_nsec) * 1e-9;
}

void write_file(const std::string& path, const std::string& body) {
  std::FILE* file = std::fopen(path.c_str(), "wbx");
  if (file == nullptr) {
    die("cannot create " + path + " (it must not already exist)");
  }
  if (std::fwrite(body.data(), 1, body.size(), file) != body.size()) {
    std::fclose(file);
    die("short write to " + path);
  }
  std::fclose(file);
}

std::string sha256_of(const std::string& body) {
  Sha256 hasher;
  hasher.update(body);
  return hasher.finish_hex();
}

void verify_digest(const char* path, const char* expected, bool enabled) {
  if (!enabled) {
    return;
  }
  const auto digest = sha256_file_hex(path);
  if (!digest) {
    die_on_refusal(digest.error(), path);
  }
  if (digest.value() != expected) {
    die(std::string(path) + " hashes to " + digest.value() + ", not the pinned " + expected);
  }
}

std::int64_t file_size(const char* path) {
  struct ::stat info {};
  if (::stat(path, &info) != 0) {
    die(std::string("cannot stat ") + path);
  }
  return static_cast<std::int64_t>(info.st_size);
}

// --- a deterministic JSON writer -------------------------------------------
class Json {
 public:
  void field(const char* name, const std::string& value) {
    comma();
    body_ += "  \"";
    body_ += name;
    body_ += "\": \"";
    body_ += value;
    body_ += "\"";
  }
  void field(const char* name, std::uint64_t value) {
    comma();
    char scratch[32];
    std::snprintf(scratch, sizeof(scratch), "%" PRIu64, value);
    body_ += "  \"";
    body_ += name;
    body_ += "\": ";
    body_ += scratch;
  }
  void field(const char* name, std::int64_t value) {
    comma();
    char scratch[32];
    std::snprintf(scratch, sizeof(scratch), "%" PRId64, value);
    body_ += "  \"";
    body_ += name;
    body_ += "\": ";
    body_ += scratch;
  }
  void field_seconds(const char* name, double value) {
    comma();
    char scratch[64];
    std::snprintf(scratch, sizeof(scratch), "%.6f", value);
    body_ += "  \"";
    body_ += name;
    body_ += "\": ";
    body_ += scratch;
  }
  [[nodiscard]] std::string done() const { return "{\n" + body_ + "\n}\n"; }

 private:
  void comma() {
    if (!body_.empty()) {
      body_ += ",\n";
    }
  }
  std::string body_;
};

}  // namespace

int main(int argc, char** argv) {
  std::string out_dir;
  std::uint32_t stop = kMaxPrefixOrdinal;
  std::uint32_t resolve = kFirstRetainedOrdinal;
  bool parquet_digest = true;
  bool build_roster = true;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    const auto next = [&]() -> std::string {
      if (i + 1 >= argc) {
        die("missing value for " + arg);
      }
      return argv[++i];
    };
    if (arg == "--out") {
      out_dir = next();
    } else if (arg == "--stop") {
      stop = static_cast<std::uint32_t>(std::strtoul(next().c_str(), nullptr, 10));
    } else if (arg == "--resolve") {
      resolve = static_cast<std::uint32_t>(std::strtoul(next().c_str(), nullptr, 10));
    } else if (arg == "--skip-parquet-digest") {
      parquet_digest = false;
    } else if (arg == "--no-roster") {
      // Prefix-seal only. The seal and the roster are independent authorities:
      // the seal needs no parquet at all, so it stays runnable when the
      // publication decode is blocked on something the seal does not use.
      build_roster = false;
    } else {
      die("unknown argument " + arg);
    }
  }
  if (out_dir.empty()) {
    die("usage: qr_candidates_seal --out DIR [--stop 917] [--resolve 125] [--skip-parquet-digest]");
  }
  if (resolve < kFirstRetainedOrdinal || resolve > stop || stop > kMaxPrefixOrdinal) {
    die("--resolve must be in 125..stop and --stop must be <= 917");
  }
  if (::mkdir(out_dir.c_str(), 0755) != 0) {
    die("output directory must not already exist: " + out_dir);
  }

  const double started = now_seconds();

  // --- 1. authority digests --------------------------------------------------
  verify_digest(kProjectionIndexPath, kProjectionIndexSha, true);
  verify_digest(kRegistryIndexPath, kRegistryIndexSha, true);
  verify_digest(kProjectionPath, kProjectionSha, parquet_digest);
  verify_digest(kRegistryPath, kRegistrySha, parquet_digest);
  if (file_size(kEventSignalsPath) != kEventSignalsBytes) {
    die("event_signals.tsv is not the pinned byte size");
  }
  if (file_size(kT14Path) != kT14BoundsBytes) {
    die("t14_bounds.tsv is not the pinned byte size");
  }
  const double after_digests = now_seconds();

  // --- 2. t14 bounds, one byte at a time -------------------------------------
  ReadStats t14_stats;
  std::vector<T14Bound> bounds;
  {
    auto source = FileSource::open(kT14Path);
    if (!source) {
      die_on_refusal(source.error(), kT14Path);
    }
    auto loaded = load_t14_bounds(*source.value(), stop, t14_stats);
    if (!loaded) {
      die_on_refusal(loaded.error(), "t14_bounds");
    }
    bounds = std::move(loaded).value();
  }

  // --- 3. the bounded prefix seal --------------------------------------------
  SessionSignals resolved_session;
  bool captured = false;
  PrefixSealOptions options;
  options.stop_ordinal = stop;
  options.retain_from = resolve;
  options.retain_to = resolve;
  PrefixSeal seal;
  const double prefix_started = now_seconds();
  {
    auto source = FileSource::open(kEventSignalsPath);
    if (!source) {
      die_on_refusal(source.error(), kEventSignalsPath);
    }
    auto sealed = seal_prefix(
        *source.value(), bounds, options, [&](SessionSignals& session) -> Expected<bool, Refusal> {
          if (captured) {
            return refuse<bool>(Refusal(RefusalCode::CONTENT_MISMATCH, "qr_candidates_seal",
                                        "more than one session was retained"));
          }
          resolved_session.begin(session.ordinal());
          for (const SignalAuth& row : session.rows()) {
            resolved_session.append(row);
          }
          const auto ok = resolved_session.seal();
          if (!ok) {
            return refuse<bool>(ok.error());
          }
          captured = true;
          return true;
        });
    if (!sealed) {
      die_on_refusal(sealed.error(), "prefix seal");
    }
    seal = std::move(sealed).value();
  }
  const double prefix_seconds = now_seconds() - prefix_started;
  if (!captured) {
    die("the requested session was never retained");
  }

  // --- the kernel-level non-prefetch check -----------------------------------
  std::uint64_t rchar_delta = 0;
  std::uint64_t syscr_delta = 0;
  if (seal.io_before.available && seal.io_after.available) {
    rchar_delta = seal.io_after.rchar - seal.io_before.rchar;
    syscr_delta = seal.io_after.syscr - seal.io_before.syscr;
    if (rchar_delta > seal.event_stats.requested_bytes + kIoSlackBytes) {
      die("the kernel read more bytes than the ledger requested: a prefetch is present");
    }
  }

  // --- 4. the safe leaf -------------------------------------------------------
  const std::string leaf = render_safe_leaf(resolved_session);
  const std::string leaf_sha = sha256_of(leaf);
  char leaf_name[64];
  std::snprintf(leaf_name, sizeof(leaf_name), "s%04u_event_signal_auth.tsv", resolve);
  write_file(out_dir + "/" + leaf_name, leaf);

  // --- 5. the roster ----------------------------------------------------------
  RosterCensus census;
  std::string roster_sha = "NOT_BUILT";
  std::string census_sha = "NOT_BUILT";
  if (build_roster) {
  auto projection_index = SessionIndex::load(kProjectionIndexPath, kProjectionIndexSha);
  if (!projection_index) {
    die_on_refusal(projection_index.error(), kProjectionIndexPath);
  }
  auto registry_index = SessionIndex::load(kRegistryIndexPath, kRegistryIndexSha);
  if (!registry_index) {
    die_on_refusal(registry_index.error(), kRegistryIndexPath);
  }
  const std::vector<std::string_view> projection_allow(kProjectionAllowlist.begin(),
                                                       kProjectionAllowlist.end());
  const std::vector<std::string_view> projection_deny(kProjectionForbidden.begin(),
                                                      kProjectionForbidden.end());
  const std::vector<std::string_view> registry_allow(kRegistryAllowlist.begin(),
                                                     kRegistryAllowlist.end());
  const std::vector<std::string_view> registry_deny(kRegistryForbidden.begin(),
                                                    kRegistryForbidden.end());
  // The digests were verified above; passing an empty expectation here avoids
  // hashing 6.2GB twice.
  // ONE PUBLICATION AT A TIME. Each table owns a mapped 3GB file and a footer
  // carrying ~25,000 column-chunk descriptors; holding both alive at once
  // roughly doubles the peak. The decoded session outlives its table, so the
  // projection's mapping and footer are released before the registry's exist.
  std::string detail;
  std::optional<SessionColumns> projection_columns;
  {
    auto projection = RowGroupTable::open(kProjectionPath, {}, std::move(projection_index).value(),
                                          projection_allow, projection_deny, kPublicationRowGroups,
                                          &detail);
    if (!projection) {
      die(std::string(kProjectionPath) + ": " + projection.error().message() +
          (detail.empty() ? "" : " | decoder said: " + detail));
    }
    auto columns = projection.value().read_session(resolve);
    if (!columns) {
      die_on_refusal(columns.error(), "projection row group");
    }
    projection_columns.emplace(std::move(columns).value());
  }
  std::optional<SessionColumns> registry_columns;
  {
    auto registry = RowGroupTable::open(kRegistryPath, {}, std::move(registry_index).value(),
                                        registry_allow, registry_deny, kPublicationRowGroups,
                                        &detail);
    if (!registry) {
      die(std::string(kRegistryPath) + ": " + registry.error().message() +
          (detail.empty() ? "" : " | decoder said: " + detail));
    }
    auto columns = registry.value().read_session(resolve);
    if (!columns) {
      die_on_refusal(columns.error(), "registry row group");
    }
    registry_columns.emplace(std::move(columns).value());
  }
  auto roster = build_session_roster(resolve, *registry_columns, *projection_columns,
                                     resolved_session);
  if (!roster) {
    die_on_refusal(roster.error(), "session roster");
  }
  const std::string roster_text = render_roster(roster.value());
  const std::string census_text = render_census(roster.value().census);
  write_file(out_dir + "/roster.tsv", roster_text);
  write_file(out_dir + "/census.tsv", census_text);
  census = roster.value().census;
  roster_sha = sha256_of(roster_text);
  census_sha = sha256_of(census_text);
  }

  // --- 6. the receipt ---------------------------------------------------------
  const double elapsed = now_seconds() - started;
  Json receipt;
  receipt.field("schema_version", "qr_candidates_seal_v1");
  receipt.field("stop_ordinal", static_cast<std::uint64_t>(seal.stop_ordinal));
  receipt.field("resolved_ordinal", static_cast<std::uint64_t>(resolve));
  receipt.field("expected_data_rows", seal.expected_data_rows);
  receipt.field("decoded_data_rows", seal.decoded_data_rows);
  receipt.field("roots_verified", static_cast<std::uint64_t>(seal.roots_verified));
  receipt.field("event_pread_calls", seal.event_stats.pread_calls);
  receipt.field("event_requested_bytes", seal.event_stats.requested_bytes);
  receipt.field("event_header_calls", seal.event_stats.header_calls);
  receipt.field("event_body_block_calls", seal.event_stats.body_block_calls);
  receipt.field("event_final_byte_calls", seal.event_stats.final_byte_calls);
  receipt.field("event_max_request", static_cast<std::uint64_t>(seal.event_stats.max_request));
  receipt.field("event_end_offset_exclusive", seal.event_stats.end_offset_exclusive);
  receipt.field("t14_pread_calls", t14_stats.pread_calls);
  receipt.field("t14_requested_bytes", t14_stats.requested_bytes);
  receipt.field("proc_self_io_rchar_delta", rchar_delta);
  receipt.field("proc_self_io_syscr_delta", syscr_delta);
  receipt.field("consumed_prefix_sha256", seal.consumed_prefix_sha256);
  receipt.field("safe_leaf_name", leaf_name);
  receipt.field("safe_leaf_sha256", leaf_sha);
  receipt.field("safe_leaf_rows", static_cast<std::uint64_t>(resolved_session.size()));
  receipt.field("roster_sha256", roster_sha);
  receipt.field("census_sha256", census_sha);
  receipt.field("session_roots_sha256", [&] {
    Sha256 hasher;
    for (const std::string& root : seal.session_roots) {
      hasher.update(root);
      hasher.update("\n");
    }
    return hasher.finish_hex();
  }());
  receipt.field("event_signals_pinned_sha256_not_rehashed_prefix_wall", kEventSignalsSha);
  receipt.field("t14_bounds_pinned_sha256_not_rehashed_prefix_wall", kT14Sha);
  receipt.field("truth_relation_projection_sha256",
                parquet_digest ? kProjectionSha : "SKIPPED_BY_FLAG");
  receipt.field("candidate_action_registry_sha256",
                parquet_digest ? kRegistrySha : "SKIPPED_BY_FLAG");
  receipt.field("truth_relation_projection_session_index_sha256", kProjectionIndexSha);
  receipt.field("candidate_action_registry_session_index_sha256", kRegistryIndexSha);
  receipt.field("admitted_rows", census.admitted_rows);
  receipt.field("resolved_rows", census.resolved_rows);
  receipt.field("resolved_long", census.resolved_long);
  receipt.field("resolved_short", census.resolved_short);
  receipt.field("nonprimitive_union_census_only_rows",
                census.nonprimitive_union_census_only_rows);
  receipt.field("side_unavailable_candidates", census.side_unavailable_candidates);
  receipt.field("physical_key_authenticated_candidates",
                census.physical_key_authenticated_candidates);
  receipt.field_seconds("digest_seconds", after_digests - started);
  receipt.field_seconds("prefix_seconds", prefix_seconds);
  receipt.field_seconds("elapsed_seconds", elapsed);
  receipt.field("vm_hwm_kib", vm_hwm_kib());
  const std::string receipt_text = receipt.done();
  write_file(out_dir + "/receipt.json", receipt_text);
  std::fputs(receipt_text.c_str(), stdout);
  return 0;
}
