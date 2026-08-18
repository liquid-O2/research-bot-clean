#include "qr_entry_v2/substrate.hpp"

#include <openssl/evp.h>

#include <algorithm>
#include <array>
#include <bit>
#include <cctype>
#include <charconv>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <limits>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <string_view>
#include <system_error>
#include <tuple>
#include <utility>

#include "qr_databento/adapter.hpp"
#include "qr_futsess/calendar.hpp"
#include "qr_futsess/constants.hpp"
#include "qr_futsess/json.hpp"
#include "qr_futsess/seal.hpp"

namespace qr::entry_v2 {
namespace {

namespace fs = std::filesystem;
using qr::futsess::Asset;
using qr::futsess::Date;
using qr::futsess::JsonWriter;

constexpr std::int64_t kNsPerSecond = 1'000'000'000LL;
constexpr std::uint64_t kPreH2ReceiveEndExclusiveNs = 1'751'320'800'000'000'000ULL;
constexpr std::int32_t kPhaseBinSeconds = 30 * 60;
constexpr std::int32_t kPhaseSearchBins = 4;  // +/- two hours
constexpr std::string_view kTallySchema = "QRE2TALLY2";
constexpr std::string_view kLockSchema = "QRE2LOCK2";
constexpr std::string_view kPhaseSchema = "QRE2PHASE2";
constexpr std::string_view kInputSchema = "QRE2INPUT2";
constexpr std::string_view kEventManifestSchema = "QRE2EVENTMAN2";
constexpr std::string_view kReceiptSchema = "QRE2RECEIPT2";
constexpr std::array<std::string_view, 2> kKnownMixed2025ProviderSha256 = {
    "30a9e8f81d46e3213b2d2324cfd8d957cf70aa2ef1aab256e2c618a513ab884a",
    "b5896ac57718416bbb1b663ed817bd2ae0e6ae43ab2c7212d429e10f648d43be"};
static_assert(std::endian::native == std::endian::little,
              "QRE2 binary encoding is pinned to little-endian hosts");

struct InputRow {
  std::string path;
  std::uintmax_t size = 0;
  std::string sha256;
  std::string hash_source;
  std::string access;
  std::int32_t container_start_d8 = 0;
  std::int32_t container_end_d8 = 0;
};

struct EventManifestRow {
  LockRow lock;
  std::string status;
  std::uint64_t n_events = 0;
  std::uint64_t min_ts_recv_ns = 0;
  std::uint64_t max_ts_recv_ns = 0;
  std::uint64_t min_ts_event_ns = 0;
  std::uint64_t max_ts_event_ns = 0;
  std::uint64_t raw_records = 0;
  std::uint64_t trusted_economic_records = 0;
  std::uint64_t snapshot_records = 0;
  std::uint64_t standalone_bad_ts_recv_records = 0;
  std::uint64_t maybe_bad_book_records = 0;
  std::string binary_rel;
  std::string binary_sha256;
  std::string sidecar_rel;
  std::string sidecar_sha256;
};

// Standalone BAD_TS_RECV is a transport-clock defect, not a snapshot marker.
// Its payload cannot choose a symbol, date, ordering key, or economic value.
// We retain only an IID-local count and attribute it after clean F_LAST book
// anchors prove that both sides of the gap belong to one Globex session.
struct BadTsRecvGap {
  bool active = false;
  bool have_last_clean_anchor = false;
  std::int32_t last_clean_anchor_d8 = 0;
  std::uint64_t records = 0;
};

struct CleanClockDecision {
  bool quarantine_economic = false;
  std::uint64_t resolved_bad_records = 0;
};

[[nodiscard]] bool standalone_bad_ts_recv(std::uint8_t flags) noexcept {
  return (flags & kFlagBadTsRecv) != 0u &&
         (flags & kFlagSnapshot) == 0u;
}

[[nodiscard]] bool clean_clock_anchor(std::uint8_t flags,
                                      bool sane_book) noexcept {
  return sane_book && (flags & kFlagLast) != 0u &&
         (flags & (kFlagSnapshot | kFlagBadTsRecv | kFlagMaybeBadBook)) == 0u;
}

[[nodiscard]] Expected<std::monostate, Refusal> note_bad_ts_recv(
    std::map<std::uint32_t, BadTsRecvGap>* gaps, std::uint32_t iid,
    const char* site) {
  BadTsRecvGap& gap = (*gaps)[iid];
  if (!gap.have_last_clean_anchor) {
    return refuse<std::monostate>(Refusal(
        RefusalCode::CLOCK_VIOLATION, site,
        "standalone BAD_TS_RECV has no preceding clean sane F_LAST IID anchor",
        static_cast<std::int64_t>(iid)));
  }
  if (gap.records == std::numeric_limits<std::uint64_t>::max()) {
    return refuse<std::monostate>(Refusal(
        RefusalCode::ARITHMETIC_OVERFLOW, site,
        "standalone BAD_TS_RECV burst counter overflow",
        static_cast<std::int64_t>(iid)));
  }
  gap.active = true;
  ++gap.records;
  return std::monostate{};
}

[[nodiscard]] Expected<CleanClockDecision, Refusal> observe_clean_clock(
    std::map<std::uint32_t, BadTsRecvGap>* gaps, std::uint32_t iid,
    std::int32_t d8, std::uint8_t flags, bool sane_book, const char* site) {
  BadTsRecvGap& gap = (*gaps)[iid];
  CleanClockDecision decision;
  if (gap.active) {
    if (!gap.have_last_clean_anchor || gap.last_clean_anchor_d8 != d8) {
      return refuse<CleanClockDecision>(Refusal(
          RefusalCode::CLOCK_VIOLATION, site,
          "standalone BAD_TS_RECV burst crosses a Globex session boundary",
          static_cast<std::int64_t>(iid)));
    }
    decision.quarantine_economic = true;
    if (clean_clock_anchor(flags, sane_book)) {
      decision.resolved_bad_records = gap.records;
      gap.active = false;
      gap.records = 0;
      gap.last_clean_anchor_d8 = d8;
    }
    return decision;
  }
  if (clean_clock_anchor(flags, sane_book)) {
    gap.have_last_clean_anchor = true;
    gap.last_clean_anchor_d8 = d8;
  }
  return decision;
}

[[nodiscard]] Expected<std::monostate, Refusal> require_no_open_bad_ts_recv_gap(
    const std::map<std::uint32_t, BadTsRecvGap>& gaps, const char* site) {
  const auto open = std::find_if(gaps.begin(), gaps.end(), [](const auto& item) {
    return item.second.active;
  });
  if (open != gaps.end()) {
    return refuse<std::monostate>(Refusal(
        RefusalCode::CLOCK_VIOLATION, site,
        "standalone BAD_TS_RECV burst has no later clean sane F_LAST IID anchor",
        static_cast<std::int64_t>(open->first)));
  }
  return std::monostate{};
}

[[nodiscard]] const char* asset_name(Asset asset) { return qr::futsess::asset_spec(asset).name; }

[[nodiscard]] std::uint8_t asset_index(Asset asset) {
  return static_cast<std::uint8_t>(asset);
}

[[nodiscard]] fs::path tally_path(const Config& c) {
  return fs::path(c.output_root) / "tallies" / (std::string(asset_name(c.asset)) + ".tsv");
}

[[nodiscard]] fs::path lock_path(const Config& c) {
  return fs::path(c.output_root) / "locks" / (std::string(asset_name(c.asset)) + ".tsv");
}

[[nodiscard]] fs::path phase_path(const Config& c) {
  return fs::path(c.output_root) / "phases" / (std::string(asset_name(c.asset)) + ".tsv");
}

[[nodiscard]] fs::path inputs_path(const Config& c) {
  return fs::path(c.output_root) / "manifests" /
         (std::string(asset_name(c.asset)) + ".inputs.tsv");
}

[[nodiscard]] fs::path event_dir(const Config& c) {
  return fs::path(c.output_root) / "events" / asset_name(c.asset);
}

[[nodiscard]] fs::path receipt_path(const Config& c, std::string_view stage) {
  return fs::path(c.output_root) / "receipts" /
         (std::string(asset_name(c.asset)) + "." + std::string(stage) + ".json");
}

[[nodiscard]] Refusal io_refusal(const char* site, const char* detail) {
  return Refusal(RefusalCode::IO, site, detail);
}

[[nodiscard]] Refusal content_refusal(const char* site, const char* detail,
                                      std::int64_t context = 0) {
  return Refusal(RefusalCode::CONTENT_MISMATCH, site, detail, context);
}

[[nodiscard]] bool valid_sha256(std::string_view value) {
  return value.size() == 64u &&
         std::all_of(value.begin(), value.end(), [](char ch) {
           return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
         });
}

[[nodiscard]] bool known_mixed_provider_hash(std::string_view value) {
  return std::find(kKnownMixed2025ProviderSha256.begin(),
                   kKnownMixed2025ProviderSha256.end(), value) !=
         kKnownMixed2025ProviderSha256.end();
}

[[nodiscard]] bool h2_or_mixed_basename(const fs::path& path) {
  std::string name = path.filename().string();
  std::transform(name.begin(), name.end(), name.begin(), [](unsigned char ch) {
    return static_cast<char>(std::tolower(ch));
  });
  return name.find("mixed") != std::string::npos ||
         name.find("holdout") != std::string::npos ||
         name.find("h2") != std::string::npos ||
         name.find("20250101-20251231") != std::string::npos;
}

[[nodiscard]] Expected<std::monostate, Refusal> validate_window(const Config& config) {
  if (config.start_d8 < kDevelopmentStartD8 ||
      config.end_d8_exclusive > kDevelopmentEndD8Exclusive ||
      config.start_d8 >= config.end_d8_exclusive) {
    return refuse<std::monostate>(Refusal(
        RefusalCode::DAY_OUTSIDE_CALENDAR, "qr_entry_v2::validate_window",
        "ordinary entry-v2 builds are confined to [20210101,20250701)"));
  }
  return std::monostate{};
}

[[nodiscard]] std::string window_tag(const Config& config) {
  return "start_d8=" + std::to_string(config.start_d8) +
         " end_d8_exclusive=" + std::to_string(config.end_d8_exclusive);
}

[[nodiscard]] Expected<std::monostate, Refusal> ensure_parent(const fs::path& path) {
  std::error_code ec;
  fs::create_directories(path.parent_path(), ec);
  if (ec) {
    return refuse<std::monostate>(
        io_refusal("qr_entry_v2::ensure_parent", "cannot create artifact directory"));
  }
  return std::monostate{};
}

[[nodiscard]] Expected<std::monostate, Refusal> write_atomic(const fs::path& path,
                                                             std::string_view bytes) {
  auto parent = ensure_parent(path);
  if (!parent) {
    return parent;
  }
  const fs::path tmp = path.string() + ".tmp";
  std::FILE* file = std::fopen(tmp.c_str(), "wb");
  if (file == nullptr) {
    return refuse<std::monostate>(
        io_refusal("qr_entry_v2::write_atomic", "cannot open temporary artifact"));
  }
  const std::size_t wrote = std::fwrite(bytes.data(), 1, bytes.size(), file);
  const int closed = std::fclose(file);
  if (wrote != bytes.size() || closed != 0) {
    std::error_code ignored;
    fs::remove(tmp, ignored);
    return refuse<std::monostate>(
        io_refusal("qr_entry_v2::write_atomic", "short artifact write"));
  }
  std::error_code ec;
  fs::rename(tmp, path, ec);
  if (ec) {
    fs::remove(tmp, ec);
    return refuse<std::monostate>(
        io_refusal("qr_entry_v2::write_atomic", "cannot publish artifact atomically"));
  }
  return std::monostate{};
}

[[nodiscard]] Expected<std::string, Refusal> read_text(const fs::path& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    return refuse<std::string>(
        io_refusal("qr_entry_v2::read_text", "cannot open required artifact"));
  }
  std::ostringstream out;
  out << in.rdbuf();
  if (!in.eof() && in.fail()) {
    return refuse<std::string>(
        io_refusal("qr_entry_v2::read_text", "cannot read required artifact"));
  }
  return out.str();
}

[[nodiscard]] std::string hex_digest(const unsigned char* digest, unsigned int length) {
  static constexpr char kHex[] = "0123456789abcdef";
  std::string out(static_cast<std::size_t>(length) * 2u, '0');
  for (unsigned int i = 0; i < length; ++i) {
    const std::size_t j = static_cast<std::size_t>(i) * 2u;
    out[j] = kHex[digest[i] >> 4u];
    out[j + 1u] = kHex[digest[i] & 0x0Fu];
  }
  return out;
}

[[nodiscard]] std::string sha256_bytes(std::string_view bytes) {
  std::array<unsigned char, EVP_MAX_MD_SIZE> digest{};
  unsigned int length = 0;
  const int ok = EVP_Digest(bytes.data(), bytes.size(), digest.data(), &length, EVP_sha256(),
                            nullptr);
  if (ok != 1 || length != 32u) {
    return {};
  }
  return hex_digest(digest.data(), length);
}

[[nodiscard]] Expected<std::string, Refusal> sha256_file(const fs::path& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    return refuse<std::string>(
        io_refusal("qr_entry_v2::sha256_file", "cannot open input for hashing"));
  }
  EVP_MD_CTX* raw = EVP_MD_CTX_new();
  if (raw == nullptr) {
    return refuse<std::string>(
        io_refusal("qr_entry_v2::sha256_file", "cannot allocate digest context"));
  }
  const auto cleanup = [&raw]() { EVP_MD_CTX_free(raw); };
  if (EVP_DigestInit_ex(raw, EVP_sha256(), nullptr) != 1) {
    cleanup();
    return refuse<std::string>(
        io_refusal("qr_entry_v2::sha256_file", "cannot initialize digest"));
  }
  std::array<char, 1u << 20> buffer{};
  while (in) {
    in.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
    const std::streamsize got = in.gcount();
    if (got > 0 &&
        EVP_DigestUpdate(raw, buffer.data(), static_cast<std::size_t>(got)) != 1) {
      cleanup();
      return refuse<std::string>(
          io_refusal("qr_entry_v2::sha256_file", "cannot update digest"));
    }
  }
  if (!in.eof()) {
    cleanup();
    return refuse<std::string>(
        io_refusal("qr_entry_v2::sha256_file", "cannot finish input read"));
  }
  std::array<unsigned char, EVP_MAX_MD_SIZE> digest{};
  unsigned int length = 0;
  if (EVP_DigestFinal_ex(raw, digest.data(), &length) != 1 || length != 32u) {
    cleanup();
    return refuse<std::string>(
        io_refusal("qr_entry_v2::sha256_file", "cannot finalize digest"));
  }
  cleanup();
  return hex_digest(digest.data(), length);
}

[[nodiscard]] Expected<std::vector<InputRow>, Refusal> inspect_inputs(const Config& config) {
  auto window = validate_window(config);
  if (!window) {
    return refuse<std::vector<InputRow>>(window.error());
  }
  if (config.inputs.empty()) {
    return refuse<std::vector<InputRow>>(
        Refusal(RefusalCode::CONFIG, "qr_entry_v2::inspect_inputs",
                "tally/events stage requires at least one --input"));
  }
  const std::vector<std::string>& paths = config.inputs;
  if (std::adjacent_find(paths.begin(), paths.end()) != paths.end()) {
    return refuse<std::vector<InputRow>>(
        Refusal(RefusalCode::CONFIG, "qr_entry_v2::inspect_inputs",
                "duplicate input path would double-count records"));
  }
  std::vector<InputRow> out;
  out.reserve(paths.size());
  const std::set<std::string> input_set(paths.begin(), paths.end());
  if (config.development_input_sha256.size() != input_set.size()) {
    return refuse<std::vector<InputRow>>(Refusal(
        RefusalCode::CONFIG, "qr_entry_v2::inspect_inputs",
        "every input requires exactly one provider SHA and development allowlist row"));
  }
  for (const auto& [path, hash] : config.development_input_sha256) {
    if (input_set.find(path) == input_set.end() || !valid_sha256(hash)) {
      return refuse<std::vector<InputRow>>(Refusal(
          RefusalCode::CONFIG, "qr_entry_v2::inspect_inputs",
          "provider input hash is malformed or names a path absent from inputs"));
    }
  }
  if (!std::all_of(config.development_prefix_inputs.begin(),
                   config.development_prefix_inputs.end(),
                   [&input_set](const std::string& path) {
                     return input_set.find(path) != input_set.end();
                   })) {
    return refuse<std::vector<InputRow>>(Refusal(
        RefusalCode::CONFIG, "qr_entry_v2::inspect_inputs",
        "DEVELOPMENT_PREFIX names a path absent from inputs"));
  }
  std::vector<std::string> sealed;
  std::tuple<std::int32_t, std::int32_t, std::string> previous_key{};
  bool have_previous = false;
  for (const std::string& path : paths) {
    if (path.find('\t') != std::string::npos || path.find('\n') != std::string::npos) {
      return refuse<std::vector<InputRow>>(
          Refusal(RefusalCode::CONFIG, "qr_entry_v2::inspect_inputs",
                  "input path contains a TSV control character"));
    }
    const auto authority = config.development_input_sha256.find(path);
    if (authority == config.development_input_sha256.end()) {
      return refuse<std::vector<InputRow>>(Refusal(
          RefusalCode::CONFIG, "qr_entry_v2::inspect_inputs",
          "input is absent from the provider-hash development allowlist"));
    }
    const bool development_prefix =
        config.development_prefix_inputs.find(path) !=
        config.development_prefix_inputs.end();
    if (!development_prefix &&
        (known_mixed_provider_hash(authority->second) || h2_or_mixed_basename(path))) {
      return refuse<std::vector<InputRow>>(Refusal(
          RefusalCode::DAY_OUTSIDE_CALENDAR, "qr_entry_v2::inspect_inputs",
          "known mixed/H2 provider object is blocked before stat or payload open"));
    }
    // Filename, access, and range admission intentionally precede stat, seal
    // probing, and payload open. Pure H2/2026 containers are never touched; a
    // crossing container requires explicit bounded-prefix authority.
    const std::vector<int> dates = qr::futsess::filename_dates(path);
    if (dates.empty() || dates.size() > 2u) {
      return refuse<std::vector<InputRow>>(Refusal(
          RefusalCode::CONFIG, "qr_entry_v2::inspect_inputs",
          "input basename must declare one date or one inclusive date range"));
    }
    const std::int32_t container_start = dates.front();
    const std::int32_t container_end = dates.back();
    if (container_start > container_end) {
      return refuse<std::vector<InputRow>>(Refusal(
          RefusalCode::CONFIG, "qr_entry_v2::inspect_inputs",
          "input basename date range runs backwards"));
    }
    if (container_start >= kDevelopmentEndD8Exclusive) {
      return refuse<std::vector<InputRow>>(Refusal(
          RefusalCode::DAY_OUTSIDE_CALENDAR, "qr_entry_v2::inspect_inputs",
          "input container begins inside the sealed 2025H2/final-exam window",
          container_start));
    }
    if (development_prefix) {
      // A UTC-daily 20250630 container legitimately crosses the 22:00 UTC
      // Globex boundary even though its basename contains only 20250630.
      // QRE2INPUT2 supplies the explicit prefix authority; the authenticated
      // DBN metadata check below must then prove that the payload really
      // extends beyond the fixed receive-time cutoff.
      if (container_end < 20250630) {
        return refuse<std::vector<InputRow>>(Refusal(
            RefusalCode::CONFIG, "qr_entry_v2::inspect_inputs",
            "DEVELOPMENT_PREFIX must cross the fixed pre-H2 boundary"));
      }
    } else if (container_end >= kDevelopmentEndD8Exclusive) {
      return refuse<std::vector<InputRow>>(Refusal(
          RefusalCode::DAY_OUTSIDE_CALENDAR, "qr_entry_v2::inspect_inputs",
          "mixed/H2 range requires explicit DEVELOPMENT_PREFIX admission",
          container_end));
    }
    const auto key = std::tuple{container_start, container_end, path};
    if (have_previous && key <= previous_key) {
      return refuse<std::vector<InputRow>>(Refusal(
          RefusalCode::OUT_OF_ORDER, "qr_entry_v2::inspect_inputs",
          "QRE2INPUT2 rows must already be in chronological manifest order"));
    }
    previous_key = key;
    have_previous = true;
    if (container_end < config.start_d8) {
      continue;  // no byte or file-stat read for a container outside the window
    }
    if (container_start >= config.end_d8_exclusive) {
      return refuse<std::vector<InputRow>>(Refusal(
          RefusalCode::DAY_OUTSIDE_CALENDAR, "qr_entry_v2::inspect_inputs",
          "input container begins inside the sealed 2025H2/final-exam window",
          container_start));
    }
    auto seal = qr::futsess::guard_seal(path, &sealed);
    if (!seal) {
      return refuse<std::vector<InputRow>>(seal.error());
    }
    std::error_code ec;
    const std::uintmax_t size = fs::file_size(path, ec);
    if (ec) {
      return refuse<std::vector<InputRow>>(
          io_refusal("qr_entry_v2::inspect_inputs", "cannot stat input payload"));
    }
    // One content pass at the raw admission boundary. Downstream stages use
    // the resulting immutable input manifest and never call this hash again
    // within the same admission.
    auto actual = sha256_file(path);
    if (!actual) {
      return refuse<std::vector<InputRow>>(actual.error());
    }
    if (actual.value() != authority->second) {
      return refuse<std::vector<InputRow>>(content_refusal(
          "qr_entry_v2::inspect_inputs",
          "payload bytes differ from provider-authenticated SHA-256"));
    }
    if (!development_prefix && known_mixed_provider_hash(actual.value())) {
      return refuse<std::vector<InputRow>>(Refusal(
          RefusalCode::DAY_OUTSIDE_CALENDAR, "qr_entry_v2::inspect_inputs",
          "renamed known mixed/H2 provider object is inadmissible"));
    }
    out.push_back(InputRow{
        path, size, actual.value(), "CONTENT_VERIFIED_PROVIDER_SHA256",
        development_prefix ? "DEVELOPMENT_PREFIX" : "DEVELOPMENT",
        container_start, container_end});
  }
  if (out.empty()) {
    return refuse<std::vector<InputRow>>(Refusal(
        RefusalCode::CONFIG, "qr_entry_v2::inspect_inputs",
        "no input container overlaps the requested development window"));
  }
  return out;
}

[[nodiscard]] std::string render_inputs(const Config& config, const std::vector<InputRow>& rows) {
  std::ostringstream out;
  out << "# " << kInputSchema << ' ' << window_tag(config) << '\n';
  out << "path\tprovider_sha256\taccess\n";
  for (const InputRow& row : rows) {
    out << row.path << '\t' << row.sha256 << '\t' << row.access << '\n';
  }
  return out.str();
}

[[nodiscard]] Expected<std::string, Refusal> publish_inputs(const Config& config,
                                                            const std::vector<InputRow>& rows,
                                                            bool require_existing_match) {
  const std::string text = render_inputs(config, rows);
  const fs::path path = inputs_path(config);
  if (require_existing_match) {
    auto old = read_text(path);
    if (!old) {
      return refuse<std::string>(old.error());
    }
    if (old.value() != text) {
      return refuse<std::string>(content_refusal(
          "qr_entry_v2::publish_inputs",
          "raw input manifest changed after tallies/locks were built"));
    }
  } else {
    auto wrote = write_atomic(path, text);
    if (!wrote) {
      return refuse<std::string>(wrote.error());
    }
  }
  return sha256_bytes(text);
}

[[nodiscard]] Expected<std::monostate, Refusal> validate_input_metadata(
    const qr::databento::Metadata& metadata, std::string_view access) {
  constexpr std::uint64_t kDevelopmentStartUtcNs = 1'609'459'200'000'000'000ULL;
  const bool prefix = access == "DEVELOPMENT_PREFIX";
  if (metadata.start_ts_recv_ns < kDevelopmentStartUtcNs ||
      metadata.start_ts_recv_ns >= kPreH2ReceiveEndExclusiveNs ||
      (!prefix && metadata.end_ts_recv_ns > kPreH2ReceiveEndExclusiveNs) ||
      (prefix && metadata.end_ts_recv_ns <= kPreH2ReceiveEndExclusiveNs)) {
    return refuse<std::monostate>(Refusal(
        RefusalCode::DAY_OUTSIDE_CALENDAR,
        "qr_entry_v2::validate_input_metadata",
        "official DBN receive-time metadata disagrees with development access"));
  }
  return std::monostate{};
}

[[nodiscard]] Expected<std::monostate, Refusal> validate_record_window(
    const qr::databento::Metadata& metadata, const qr::databento::Mbp1Row& row) {
  if (row.ts_recv_ns < metadata.start_ts_recv_ns ||
      row.ts_recv_ns >= metadata.end_ts_recv_ns ||
      row.ts_recv_ns >= kPreH2ReceiveEndExclusiveNs) {
    return refuse<std::monostate>(Refusal(
        RefusalCode::DAY_OUTSIDE_CALENDAR,
        "qr_entry_v2::validate_record_window",
        "MBP-1 IndexTs is outside official metadata or the DEVELOPMENT/H1 seal"));
  }
  return std::monostate{};
}

[[nodiscard]] Expected<std::string, Refusal> publish_receipt(
    const Config& config, std::string_view stage, std::string_view input_sha,
    std::string_view output_sha, std::uint64_t rows, std::uint64_t records,
    std::uint64_t refusals, std::uint64_t content_hashed_inputs,
    std::uint64_t trusted_hash_inputs, std::uint64_t raw_records,
    std::uint64_t trusted_economic_records, std::uint64_t snapshot_records,
    std::uint64_t standalone_bad_ts_recv_records,
    std::uint64_t maybe_bad_book_records) {
  const qr::databento::BuildAuthority& authority = qr::databento::build_authority();
  std::ostringstream core;
  core << kReceiptSchema << '|' << stage << '|' << asset_name(config.asset) << '|'
       << input_sha << '|' << output_sha << '|' << rows << '|' << records << '|' << refusals
       << "|phase_lookback=" << kPhaseLookback << "|phase_min=" << kPhaseMinFit
       << "|selection=previous_completed_outright_R1_lower_iid_tie"
       << "|window=" << config.start_d8 << ':' << config.end_d8_exclusive
       << "|content_hashed_inputs=" << content_hashed_inputs
       << "|trusted_hash_inputs=" << trusted_hash_inputs
       << "|raw_records=" << raw_records
       << "|trusted_economic_records=" << trusted_economic_records
       << "|snapshot_records=" << snapshot_records
       << "|standalone_bad_ts_recv_records=" << standalone_bad_ts_recv_records
       << "|maybe_bad_book_records=" << maybe_bad_book_records
       << "|adapter=" << authority.adapter_source_sha256
       << "|clock_law=" << authority.clock_law_sha256 << "|seal=20260101";
  const std::string core_sha = sha256_bytes(core.str());
  JsonWriter json;
  json.begin_object();
  json.key("schema");
  json.value_string(std::string(kReceiptSchema));
  json.key("stage");
  json.value_string(std::string(stage));
  json.key("asset");
  json.value_string(asset_name(config.asset));
  json.key("start_d8");
  json.value_int(config.start_d8);
  json.key("end_d8_exclusive");
  json.value_int(config.end_d8_exclusive);
  json.key("input_sha256");
  json.value_string(std::string(input_sha));
  json.key("output_sha256");
  json.value_string(std::string(output_sha));
  json.key("rows");
  json.value_int(static_cast<std::int64_t>(rows));
  json.key("records");
  json.value_int(static_cast<std::int64_t>(records));
  json.key("typed_refusals");
  json.value_int(static_cast<std::int64_t>(refusals));
  json.key("content_hashed_inputs");
  json.value_int(static_cast<std::int64_t>(content_hashed_inputs));
  json.key("trusted_hash_inputs");
  json.value_int(static_cast<std::int64_t>(trusted_hash_inputs));
  json.key("raw_records");
  json.value_int(static_cast<std::int64_t>(raw_records));
  json.key("trusted_economic_records");
  json.value_int(static_cast<std::int64_t>(trusted_economic_records));
  json.key("snapshot_records");
  json.value_int(static_cast<std::int64_t>(snapshot_records));
  json.key("standalone_bad_ts_recv_records");
  json.value_int(static_cast<std::int64_t>(standalone_bad_ts_recv_records));
  json.key("maybe_bad_book_records");
  json.value_int(static_cast<std::int64_t>(maybe_bad_book_records));
  json.key("session_assignment_clock");
  json.value_string("ts_recv");
  json.key("symbology_date_clock");
  json.value_string("floor_utc(ts_recv)");
  json.key("causal_visibility_clock");
  json.value_string("IndexTs/ts_recv");
  json.key("exchange_feature_clock");
  json.value_string("ts_event");
  json.key("equal_receive_time");
  json.value_string("future");
  json.key("tie_order");
  json.value_string("ordered_input_manifest_then_dbn_decode_ordinal");
  json.key("official_adapter_source_sha256");
  json.value_string(authority.adapter_source_sha256);
  json.key("official_vendor_tree_sha256");
  json.value_string(authority.vendor_tree_sha256);
  json.key("declared_databento_upstream_commit");
  json.value_string(authority.declared_upstream_commit);
  json.key("clock_law_sha256");
  json.value_string(authority.clock_law_sha256);
  json.key("selection_rule");
  json.value_string("previous_completed_session_outright_R1_lower_iid_tie");
  json.key("phase_rule");
  json.value_string("month_frozen_up_to_252_strictly_prior_clean_sessions_min60_fixed_fallback");
  json.key("holdout_start_d8");
  json.value_int(kDevelopmentEndD8Exclusive);
  json.key("final_exam_permit");
  json.value_bool(false);
  json.key("seal_cutoff_d8");
  json.value_int(20260101);
  json.key("receipt_core_sha256");
  json.value_string(core_sha);
  json.end_object();
  const std::string text = json.text() + "\n";
  auto wrote = write_atomic(receipt_path(config, stage), text);
  if (!wrote) {
    return refuse<std::string>(wrote.error());
  }
  return sha256_bytes(text);
}

[[nodiscard]] std::vector<std::string> split_tabs(std::string_view line) {
  std::vector<std::string> out;
  std::size_t start = 0;
  for (;;) {
    const std::size_t tab = line.find('\t', start);
    const std::size_t stop = tab == std::string_view::npos ? line.size() : tab;
    out.emplace_back(line.substr(start, stop - start));
    if (tab == std::string_view::npos) {
      break;
    }
    start = tab + 1u;
  }
  if (!out.empty() && !out.back().empty() && out.back().back() == '\r') {
    out.back().pop_back();
  }
  return out;
}

template <class T>
[[nodiscard]] bool parse_number(std::string_view text, T* out) {
  const char* first = text.data();
  const char* last = text.data() + text.size();
  const auto result = std::from_chars(first, last, *out);
  return result.ec == std::errc{} && result.ptr == last;
}

[[nodiscard]] std::string render_tallies(const Config& config,
                                         const std::vector<TallyRow>& rows) {
  std::ostringstream out;
  out << "# " << kTallySchema << ' ' << window_tag(config) << '\n';
  out << "asset\td8\tiid\tsymbol\toutright\tupdates\traw_records"
         "\ttrusted_economic_records\tsnapshot_records"
         "\tstandalone_bad_ts_recv_records\tmaybe_bad_book_records";
  for (std::size_t b = 0; b < kPhaseBins; ++b) {
    char name[16];
    std::snprintf(name, sizeof(name), "\tb%02zu", b);
    out << name;
  }
  out << '\n';
  for (const TallyRow& row : rows) {
    out << asset_name(config.asset) << '\t' << row.d8 << '\t' << row.iid << '\t'
        << (row.symbol.empty() ? "-" : row.symbol) << '\t' << (row.outright ? 1 : 0)
        << '\t' << row.updates << '\t' << row.raw_records << '\t'
        << row.trusted_economic_records << '\t' << row.snapshot_records << '\t'
        << row.standalone_bad_ts_recv_records << '\t' << row.maybe_bad_book_records;
    for (const std::uint64_t count : row.phase_updates) {
      out << '\t' << count;
    }
    out << '\n';
  }
  return out.str();
}

[[nodiscard]] std::string render_locks(const Config& config,
                                       const std::vector<LockRow>& rows) {
  std::ostringstream out;
  out << "# " << kLockSchema << ' ' << window_tag(config) << '\n';
  out << "asset\td8\tstatus\tlocked_iid\tselection_basis_d8"
         "\tselection_basis_updates\tselection_basis_symbol\topen_utc\tclose_utc\n";
  for (const LockRow& row : rows) {
    out << asset_name(config.asset) << '\t' << row.d8 << '\t'
        << lock_status_name(row.status) << '\t'
        << row.locked_iid << '\t' << row.selection_basis_d8 << '\t'
        << row.selection_basis_updates << '\t'
        << (row.selection_basis_symbol.empty() ? "-" : row.selection_basis_symbol) << '\t'
        << row.open_utc << '\t' << row.close_utc << '\n';
  }
  return out.str();
}

[[nodiscard]] std::string render_phases(const Config& config,
                                        const std::vector<PhaseRow>& rows) {
  std::ostringstream out;
  out << "# " << kPhaseSchema << ' ' << window_tag(config) << '\n';
  out << "asset\tmonth\tsource\tn_fit\tfit_start_d8\tfit_end_d8"
         "\ttokyo_london_sec\tlondon_ny_sec\tny_tokyo_sec\tprofile_sha256\n";
  for (const PhaseRow& row : rows) {
    out << asset_name(config.asset) << '\t' << row.month << '\t'
        << phase_source_name(row.source)
        << '\t' << row.n_fit << '\t' << row.fit_start_d8 << '\t' << row.fit_end_d8 << '\t'
        << row.boundaries[0] << '\t' << row.boundaries[1] << '\t' << row.boundaries[2] << '\t'
        << row.profile_sha256 << '\n';
  }
  return out.str();
}

[[nodiscard]] Expected<Date, Refusal> trade_date_for(std::uint64_t ts_ns) {
  if (ts_ns > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) {
    return refuse<Date>(Refusal(RefusalCode::ARITHMETIC_OVERFLOW,
                                "qr_entry_v2::trade_date_for",
                                "event timestamp exceeds signed clock range"));
  }
  const std::int64_t sec = static_cast<std::int64_t>(ts_ns / static_cast<std::uint64_t>(kNsPerSecond));
  const Date utc = qr::futsess::day_to_date(sec / qr::futsess::kSecondsPerDay);
  for (const Date candidate : {utc, qr::futsess::day_to_date(qr::futsess::date_to_day(utc) + 1)}) {
    const auto [open, close] = qr::futsess::session_bounds(candidate);
    if (open <= sec && sec < close) {
      return candidate;
    }
  }
  return refuse<Date>(Refusal(RefusalCode::OUTSIDE_RTH, "qr_entry_v2::trade_date_for",
                              "record is outside the 23-hour Globex session"));
}

[[nodiscard]] bool is_outside_session(const Refusal& refusal) {
  return refusal.code() == RefusalCode::OUTSIDE_RTH;
}

[[nodiscard]] std::int32_t cyclic_distance(std::int32_t lhs, std::int32_t rhs) {
  const std::int32_t n = static_cast<std::int32_t>(kPhaseBins);
  const std::int32_t forward = (lhs - rhs + n) % n;
  const std::int32_t backward = (rhs - lhs + n) % n;
  return std::min(forward, backward);
}

[[nodiscard]] std::int32_t find_boundary(const std::array<double, kPhaseBins>& smooth,
                                         std::int32_t seed_sec) {
  const std::int32_t n = static_cast<std::int32_t>(kPhaseBins);
  const std::int32_t seed = (seed_sec / kPhaseBinSeconds) % n;
  std::vector<std::int32_t> local;
  std::vector<std::int32_t> window;
  for (std::int32_t offset = -kPhaseSearchBins; offset <= kPhaseSearchBins; ++offset) {
    const std::int32_t bin = (seed + offset + n) % n;
    window.push_back(bin);
    const std::int32_t prev = (bin - 1 + n) % n;
    const std::int32_t next = (bin + 1) % n;
    if (smooth[static_cast<std::size_t>(bin)] <= smooth[static_cast<std::size_t>(prev)] &&
        smooth[static_cast<std::size_t>(bin)] <= smooth[static_cast<std::size_t>(next)]) {
      local.push_back(bin);
    }
  }
  const auto by_seed = [seed](std::int32_t lhs, std::int32_t rhs) {
    return std::tuple{cyclic_distance(lhs, seed), lhs} <
           std::tuple{cyclic_distance(rhs, seed), rhs};
  };
  std::int32_t best = seed;
  if (!local.empty()) {
    best = *std::min_element(local.begin(), local.end(), by_seed);
  } else {
    best = *std::min_element(window.begin(), window.end(), [&smooth](std::int32_t lhs,
                                                                    std::int32_t rhs) {
      return std::tie(smooth[static_cast<std::size_t>(lhs)], lhs) <
             std::tie(smooth[static_cast<std::size_t>(rhs)], rhs);
    });
  }
  return best * kPhaseBinSeconds;
}

[[nodiscard]] std::string profile_digest(
    const std::vector<std::pair<std::int32_t, std::array<std::uint64_t, kPhaseBins>>>& fit) {
  std::ostringstream canonical;
  for (const auto& [d8, bins] : fit) {
    canonical << d8;
    for (const std::uint64_t value : bins) {
      canonical << ',' << value;
    }
    canonical << '\n';
  }
  return sha256_bytes(canonical.str());
}

[[nodiscard]] Expected<std::vector<TallyRow>, Refusal> parse_tallies(const Config& config,
                                                                    std::string_view text) {
  const std::string expected = "# " + std::string(kTallySchema) + " " + window_tag(config) + "\n";
  if (!text.starts_with(expected)) {
    return refuse<std::vector<TallyRow>>(content_refusal(
        "qr_entry_v2::parse_tallies", "tally artifact belongs to a different record window"));
  }
  std::istringstream in{std::string(text)};
  std::string line;
  bool header = false;
  std::vector<TallyRow> rows;
  std::pair<std::int32_t, std::uint32_t> previous{-1, 0};
  while (std::getline(in, line)) {
    if (line.empty() || line[0] == '#') {
      continue;
    }
    if (!header) {
      header = true;
      continue;
    }
    const std::vector<std::string> f = split_tabs(line);
    if (f.size() != 11u + kPhaseBins || f[0] != asset_name(config.asset)) {
      return refuse<std::vector<TallyRow>>(content_refusal(
          "qr_entry_v2::parse_tallies", "tally row has the wrong schema or asset"));
    }
    TallyRow row;
    std::uint32_t outright = 0;
    if (!parse_number(f[1], &row.d8) || !parse_number(f[2], &row.iid) ||
        !parse_number(f[4], &outright) || !parse_number(f[5], &row.updates) ||
        !parse_number(f[6], &row.raw_records) ||
        !parse_number(f[7], &row.trusted_economic_records) ||
        !parse_number(f[8], &row.snapshot_records) ||
        !parse_number(f[9], &row.standalone_bad_ts_recv_records) ||
        !parse_number(f[10], &row.maybe_bad_book_records) || outright > 1u) {
      return refuse<std::vector<TallyRow>>(content_refusal(
          "qr_entry_v2::parse_tallies", "tally row contains a malformed number"));
    }
    row.symbol = f[3] == "-" ? std::string() : f[3];
    row.outright = outright == 1u;
    for (std::size_t b = 0; b < kPhaseBins; ++b) {
      if (!parse_number(f[11u + b], &row.phase_updates[b])) {
        return refuse<std::vector<TallyRow>>(content_refusal(
            "qr_entry_v2::parse_tallies", "phase-bin tally is malformed"));
      }
    }
    const std::pair<std::int32_t, std::uint32_t> key{row.d8, row.iid};
    if (!rows.empty() && key <= previous) {
      return refuse<std::vector<TallyRow>>(Refusal(
          RefusalCode::OUT_OF_ORDER, "qr_entry_v2::parse_tallies",
          "tally keys are duplicated or not strictly increasing"));
    }
    previous = key;
    rows.push_back(std::move(row));
  }
  if (!header) {
    return refuse<std::vector<TallyRow>>(content_refusal(
        "qr_entry_v2::parse_tallies", "tally artifact has no column header"));
  }
  return rows;
}

[[nodiscard]] Expected<std::vector<LockRow>, Refusal> parse_locks(const Config& config,
                                                                  std::string_view text) {
  const std::string expected = "# " + std::string(kLockSchema) + " " + window_tag(config) + "\n";
  if (!text.starts_with(expected)) {
    return refuse<std::vector<LockRow>>(content_refusal(
        "qr_entry_v2::parse_locks", "lock artifact belongs to a different record window"));
  }
  std::istringstream in{std::string(text)};
  std::string line;
  bool header = false;
  std::vector<LockRow> rows;
  while (std::getline(in, line)) {
    if (line.empty() || line[0] == '#') {
      continue;
    }
    if (!header) {
      header = true;
      continue;
    }
    const std::vector<std::string> f = split_tabs(line);
    if (f.size() != 9u || f[0] != asset_name(config.asset)) {
      return refuse<std::vector<LockRow>>(content_refusal(
          "qr_entry_v2::parse_locks", "lock row has the wrong schema or asset"));
    }
    LockRow row;
    if (f[2] == "LOCKED") {
      row.status = LockStatus::LOCKED;
    } else if (f[2] == "WARMUP_NO_PREVIOUS") {
      row.status = LockStatus::WARMUP_NO_PREVIOUS;
    } else if (f[2] == "REFUSED_PREVIOUS_NO_OUTRIGHT") {
      row.status = LockStatus::REFUSED_PREVIOUS_NO_OUTRIGHT;
    } else {
      return refuse<std::vector<LockRow>>(content_refusal(
          "qr_entry_v2::parse_locks", "lock row has an unknown status"));
    }
    if (!parse_number(f[1], &row.d8) || !parse_number(f[3], &row.locked_iid) ||
        !parse_number(f[4], &row.selection_basis_d8) ||
        !parse_number(f[5], &row.selection_basis_updates) ||
        !parse_number(f[7], &row.open_utc) || !parse_number(f[8], &row.close_utc)) {
      return refuse<std::vector<LockRow>>(content_refusal(
          "qr_entry_v2::parse_locks", "lock row contains a malformed number"));
    }
    row.selection_basis_symbol = f[6] == "-" ? std::string() : f[6];
    if ((!rows.empty() && row.d8 <= rows.back().d8) || row.close_utc <= row.open_utc ||
        (row.status == LockStatus::LOCKED && row.locked_iid < 0)) {
      return refuse<std::vector<LockRow>>(content_refusal(
          "qr_entry_v2::parse_locks", "lock row violates key or clock invariants"));
    }
    rows.push_back(std::move(row));
  }
  if (!header) {
    return refuse<std::vector<LockRow>>(content_refusal(
        "qr_entry_v2::parse_locks", "lock artifact has no column header"));
  }
  return rows;
}

[[nodiscard]] Expected<std::vector<PhaseRow>, Refusal> parse_phases(const Config& config,
                                                                    std::string_view text) {
  const std::string expected = "# " + std::string(kPhaseSchema) + " " + window_tag(config) + "\n";
  if (!text.starts_with(expected)) {
    return refuse<std::vector<PhaseRow>>(content_refusal(
        "qr_entry_v2::parse_phases", "phase artifact belongs to a different record window"));
  }
  std::istringstream in{std::string(text)};
  std::string line;
  bool header = false;
  std::vector<PhaseRow> rows;
  while (std::getline(in, line)) {
    if (line.empty() || line[0] == '#') {
      continue;
    }
    if (!header) {
      header = true;
      continue;
    }
    const std::vector<std::string> f = split_tabs(line);
    if (f.size() != 10u || f[0] != asset_name(config.asset)) {
      return refuse<std::vector<PhaseRow>>(content_refusal(
          "qr_entry_v2::parse_phases", "phase row has the wrong schema or asset"));
    }
    PhaseRow row;
    if (f[2] == "TRAILING_252_PRIOR") {
      row.source = PhaseSource::TRAILING_252_PRIOR;
    } else if (f[2] == "FIXED_MIN60") {
      row.source = PhaseSource::FIXED_MIN60;
    } else {
      return refuse<std::vector<PhaseRow>>(content_refusal(
          "qr_entry_v2::parse_phases", "phase row has an unknown source"));
    }
    if (!parse_number(f[1], &row.month) || !parse_number(f[3], &row.n_fit) ||
        !parse_number(f[4], &row.fit_start_d8) || !parse_number(f[5], &row.fit_end_d8) ||
        !parse_number(f[6], &row.boundaries[0]) || !parse_number(f[7], &row.boundaries[1]) ||
        !parse_number(f[8], &row.boundaries[2])) {
      return refuse<std::vector<PhaseRow>>(content_refusal(
          "qr_entry_v2::parse_phases", "phase row contains a malformed number"));
    }
    row.profile_sha256 = f[9];
    if ((!rows.empty() && row.month <= rows.back().month) || row.n_fit > kPhaseLookback) {
      return refuse<std::vector<PhaseRow>>(content_refusal(
          "qr_entry_v2::parse_phases", "phase schedule violates order/lookback invariants"));
    }
    rows.push_back(std::move(row));
  }
  if (!header) {
    return refuse<std::vector<PhaseRow>>(content_refusal(
        "qr_entry_v2::parse_phases", "phase artifact has no column header"));
  }
  return rows;
}

[[nodiscard]] std::array<std::uint8_t, kEventPackHeaderBytes> encode_event_header(
    const EventPackHeader& header) {
  std::array<std::uint8_t, kEventPackHeaderBytes> disk_header{};
  const auto store = [&disk_header](std::size_t offset, const auto& value) {
    std::memcpy(disk_header.data() + offset, &value, sizeof(value));
  };
  std::memcpy(disk_header.data(), header.magic, 8);
  store(8, header.version);
  disk_header[12] = header.asset_idx;
  std::memcpy(disk_header.data() + 13, header.reserved_asset, 3);
  store(16, header.d8);
  store(20, header.locked_iid);
  store(28, header.open_utc);
  store(36, header.close_utc);
  store(44, header.n_events);
  store(52, header.row_bytes);
  store(56, header.reserved);
  return disk_header;
}

[[nodiscard]] Expected<std::monostate, Refusal> write_event_binary(
    const fs::path& path, const EventPackHeader& header, const std::vector<EventRow>& rows) {
  auto parent = ensure_parent(path);
  if (!parent) {
    return parent;
  }
  const fs::path tmp = path.string() + ".tmp";
  std::FILE* file = std::fopen(tmp.c_str(), "wb");
  if (file == nullptr) {
    return refuse<std::monostate>(
        io_refusal("qr_entry_v2::write_event_binary", "cannot open event-pack temporary"));
  }
  const auto disk_header = encode_event_header(header);
  const bool header_ok =
      std::fwrite(disk_header.data(), 1, disk_header.size(), file) == disk_header.size();
  bool rows_ok = true;
  constexpr std::size_t kChunkRows = 4096;
  std::vector<std::uint8_t> buffer(kChunkRows * kEventRowBytes);
  for (std::size_t begin = 0; rows_ok && begin < rows.size(); begin += kChunkRows) {
    const std::size_t count = std::min(kChunkRows, rows.size() - begin);
    for (std::size_t i = 0; i < count; ++i) {
      std::memcpy(buffer.data() + i * kEventRowBytes, &rows[begin + i], kEventRowBytes);
    }
    const std::size_t bytes = count * kEventRowBytes;
    rows_ok = std::fwrite(buffer.data(), 1, bytes, file) == bytes;
  }
  const int closed = std::fclose(file);
  if (!header_ok || !rows_ok || closed != 0) {
    std::error_code ignored;
    fs::remove(tmp, ignored);
    return refuse<std::monostate>(
        io_refusal("qr_entry_v2::write_event_binary", "short event-pack write"));
  }
  std::error_code ec;
  fs::rename(tmp, path, ec);
  if (ec) {
    fs::remove(tmp, ec);
    return refuse<std::monostate>(io_refusal(
        "qr_entry_v2::write_event_binary", "cannot publish event pack atomically"));
  }
  return std::monostate{};
}

void json_array_descriptor(JsonWriter& json, const char* name, const char* dtype,
                           std::int64_t offset) {
  json.begin_object();
  json.key("name");
  json.value_string(name);
  json.key("dtype");
  json.value_string(dtype);
  json.key("offset_bytes");
  json.value_int(offset);
  json.end_object();
}

[[nodiscard]] std::string event_sidecar_json(const Config& config,
                                             const EventManifestRow& row,
                                             std::string_view input_sha,
                                             std::string_view locks_sha,
                                             std::string_view phase_sha) {
  JsonWriter json;
  json.begin_object();
  json.key("schema");
  json.value_string("QRE2EVENTMETA2");
  json.key("status");
  json.value_string(row.status);
  json.key("asset");
  json.value_string(asset_name(config.asset));
  json.key("asset_idx");
  json.value_int(asset_index(config.asset));
  json.key("d8");
  json.value_int(row.lock.d8);
  json.key("record_window");
  json.begin_object();
  json.key("start_d8");
  json.value_int(config.start_d8);
  json.key("end_d8_exclusive");
  json.value_int(config.end_d8_exclusive);
  json.end_object();
  json.key("locked_iid");
  if (row.lock.locked_iid >= 0) {
    json.value_int(row.lock.locked_iid);
  } else {
    json.value_null();
  }
  json.key("selection_basis_d8");
  if (row.lock.selection_basis_d8 >= 0) {
    json.value_int(row.lock.selection_basis_d8);
  } else {
    json.value_null();
  }
  json.key("selection_basis_updates");
  json.value_int(static_cast<std::int64_t>(row.lock.selection_basis_updates));
  json.key("selection_basis_symbol");
  json.value_string(row.lock.selection_basis_symbol);
  json.key("open_utc");
  json.value_int(row.lock.open_utc);
  json.key("close_utc");
  json.value_int(row.lock.close_utc);
  json.key("event_count");
  json.value_int(static_cast<std::int64_t>(row.n_events));
  json.key("min_ts_recv_ns");
  json.value_int(static_cast<std::int64_t>(row.min_ts_recv_ns));
  json.key("max_ts_recv_ns");
  json.value_int(static_cast<std::int64_t>(row.max_ts_recv_ns));
  json.key("min_ts_event_ns");
  json.value_int(static_cast<std::int64_t>(row.min_ts_event_ns));
  json.key("max_ts_event_ns");
  json.value_int(static_cast<std::int64_t>(row.max_ts_event_ns));
  json.key("raw_records");
  json.value_int(static_cast<std::int64_t>(row.raw_records));
  json.key("trusted_economic_records");
  json.value_int(static_cast<std::int64_t>(row.trusted_economic_records));
  json.key("snapshot_records");
  json.value_int(static_cast<std::int64_t>(row.snapshot_records));
  json.key("standalone_bad_ts_recv_records");
  json.value_int(static_cast<std::int64_t>(row.standalone_bad_ts_recv_records));
  json.key("maybe_bad_book_records");
  json.value_int(static_cast<std::int64_t>(row.maybe_bad_book_records));
  json.key("event_pack_sha256");
  if (row.binary_sha256.empty()) {
    json.value_null();
  } else {
    json.value_string(row.binary_sha256);
  }
  json.key("binary_file");
  if (row.binary_rel.empty()) {
    json.value_null();
  } else {
    json.value_string(row.binary_rel);
  }
  json.key("source_hashes");
  json.begin_object();
  json.key("input_manifest_sha256");
  json.value_string(std::string(input_sha));
  json.key("locks_sha256");
  json.value_string(std::string(locks_sha));
  json.key("phase_schedule_sha256");
  json.value_string(std::string(phase_sha));
  json.key("event_pack_sha256");
  if (row.binary_sha256.empty()) {
    json.value_null();
  } else {
    json.value_string(row.binary_sha256);
  }
  json.end_object();
  json.key("cutoff_rule");
  json.value_string("lower_bound(ts_recv_ns,decision_ts_ns); equal receive-time batch is future");
  json.key("session_assignment_clock");
  json.value_string("ts_recv");
  json.key("symbology_date_clock");
  json.value_string("floor_utc(ts_recv)");
  json.key("causal_visibility_clock");
  json.value_string("IndexTs/ts_recv");
  json.key("exchange_feature_clock");
  json.value_string("ts_event");
  json.key("equal_receive_time");
  json.value_string("future");
  json.key("tie_order");
  json.value_string("ordered_input_manifest_then_dbn_decode_ordinal");
  json.key("binary_schema");
  json.begin_object();
  json.key("magic");
  json.value_string("QRE2EVT2");
  json.key("byte_order");
  json.value_string("little");
  json.key("header_bytes");
  json.value_int(static_cast<std::int64_t>(kEventPackHeaderBytes));
  json.key("row_bytes");
  json.value_int(static_cast<std::int64_t>(kEventRowBytes));
  json.key("layout");
  json.value_string("packed_array_of_structs");
  json.key("arrays");
  json.begin_array();
  json_array_descriptor(json, "ts_recv_ns", "<u8", offsetof(EventRow, ts_recv_ns));
  json_array_descriptor(json, "ts_event_ns", "<u8", offsetof(EventRow, ts_event_ns));
  json_array_descriptor(json, "action", "u1", offsetof(EventRow, action));
  json_array_descriptor(json, "side", "u1", offsetof(EventRow, side));
  json_array_descriptor(json, "price", "<i8", offsetof(EventRow, price));
  json_array_descriptor(json, "size", "<u4", offsetof(EventRow, size));
  json_array_descriptor(json, "flags", "u1", offsetof(EventRow, flags));
  json_array_descriptor(json, "sequence", "<u4", offsetof(EventRow, sequence));
  json_array_descriptor(json, "bid_px", "<i8", offsetof(EventRow, bid_px));
  json_array_descriptor(json, "ask_px", "<i8", offsetof(EventRow, ask_px));
  json_array_descriptor(json, "bid_sz", "<u4", offsetof(EventRow, bid_sz));
  json_array_descriptor(json, "ask_sz", "<u4", offsetof(EventRow, ask_sz));
  json_array_descriptor(json, "bid_ct", "<u4", offsetof(EventRow, bid_ct));
  json_array_descriptor(json, "ask_ct", "<u4", offsetof(EventRow, ask_ct));
  json_array_descriptor(json, "ts_in_delta", "<i4", offsetof(EventRow, ts_in_delta));
  json_array_descriptor(json, "receive_session_sec", "<i4",
                        offsetof(EventRow, receive_session_sec));
  json_array_descriptor(json, "depth", "u1", offsetof(EventRow, depth));
  json.end_array();
  json.end_object();
  json.end_object();
  return json.text() + "\n";
}

[[nodiscard]] std::string render_event_manifest(const Config& config,
                                                const std::vector<EventManifestRow>& rows) {
  std::ostringstream out;
  out << "# " << kEventManifestSchema << ' ' << window_tag(config) << '\n';
  out << "asset\td8\tstatus\tlocked_iid\tselection_basis_d8\topen_utc\tclose_utc"
         "\tevent_count\tmin_ts_recv_ns\tmax_ts_recv_ns\tmin_ts_event_ns"
         "\tmax_ts_event_ns\traw_records\ttrusted_economic_records"
         "\tsnapshot_records\tstandalone_bad_ts_recv_records\tmaybe_bad_book_records"
         "\tbinary_file\tbinary_sha256"
         "\tsidecar_file\tsidecar_sha256\n";
  for (const EventManifestRow& row : rows) {
    out << asset_name(config.asset) << '\t' << row.lock.d8 << '\t' << row.status << '\t'
        << row.lock.locked_iid << '\t' << row.lock.selection_basis_d8 << '\t'
        << row.lock.open_utc << '\t' << row.lock.close_utc << '\t' << row.n_events << '\t'
        << row.min_ts_recv_ns << '\t' << row.max_ts_recv_ns << '\t'
        << row.min_ts_event_ns << '\t' << row.max_ts_event_ns << '\t'
        << row.raw_records << '\t' << row.trusted_economic_records << '\t'
        << row.snapshot_records << '\t' << row.standalone_bad_ts_recv_records << '\t'
        << row.maybe_bad_book_records << '\t'
        << (row.binary_rel.empty() ? "-" : row.binary_rel) << '\t'
        << (row.binary_sha256.empty() ? "-" : row.binary_sha256) << '\t'
        << row.sidecar_rel << '\t' << row.sidecar_sha256 << '\n';
  }
  return out.str();
}

}  // namespace

Expected<BookQualityDecision, Refusal> BookQualityState::observe(
    std::uint64_t ts_recv_ns, std::uint8_t flags, bool sane_book) {
  const bool snapshot = (flags & kFlagSnapshot) != 0u;
  const bool bad_ts_recv = (flags & kFlagBadTsRecv) != 0u;
  const bool maybe_bad_book = (flags & kFlagMaybeBadBook) != 0u;
  if (snapshot && !bad_ts_recv) {
    return refuse<BookQualityDecision>(Refusal(
        RefusalCode::CONTENT_MISMATCH, "qr_entry_v2::BookQualityState::observe",
        "SNAPSHOT without BAD_TS_RECV is not a valid initialization block"));
  }
  if (bad_ts_recv && !snapshot) {
    return refuse<BookQualityDecision>(Refusal(
        RefusalCode::CONTENT_MISMATCH, "qr_entry_v2::BookQualityState::observe",
        "standalone BAD_TS_RECV reached economic book state instead of transport quarantine"));
  }

  BookQualityDecision decision;
  decision.snapshot_row = snapshot;
  decision.maybe_bad_book_row = maybe_bad_book;
  if (snapshot) {
    if (!in_snapshot_block_ || snapshot_ts_recv_ns_ != ts_recv_ns) {
      if (generation_ == std::numeric_limits<std::uint64_t>::max()) {
        return refuse<BookQualityDecision>(Refusal(
            RefusalCode::ARITHMETIC_OVERFLOW,
            "qr_entry_v2::BookQualityState::observe",
            "book-quality generation overflow"));
      }
      ++generation_;
      decision.reset_derived_state = true;
      in_snapshot_block_ = true;
      snapshot_ts_recv_ns_ = ts_recv_ns;
      snapshot_block_clean_ = !maybe_bad_book;
      tainted_ = maybe_bad_book;
      awaiting_sane_ordinary_ = false;
      trusted_ = false;
    } else if (maybe_bad_book) {
      snapshot_block_clean_ = false;
      tainted_ = true;
    }
    decision.generation = generation_;
    return decision;
  }

  if (in_snapshot_block_) {
    in_snapshot_block_ = false;
    trusted_ = false;
    awaiting_sane_ordinary_ = snapshot_block_clean_ && !tainted_;
    tainted_ = !awaiting_sane_ordinary_;
  }
  if (maybe_bad_book) {
    if (!tainted_) {
      if (generation_ == std::numeric_limits<std::uint64_t>::max()) {
        return refuse<BookQualityDecision>(Refusal(
            RefusalCode::ARITHMETIC_OVERFLOW,
            "qr_entry_v2::BookQualityState::observe",
            "book-quality generation overflow"));
      }
      ++generation_;
      decision.reset_derived_state = true;
    }
    tainted_ = true;
    trusted_ = false;
    awaiting_sane_ordinary_ = false;
    decision.generation = generation_;
    return decision;
  }
  if (tainted_) {
    decision.generation = generation_;
    return decision;
  }
  if (awaiting_sane_ordinary_) {
    if (sane_book) {
      awaiting_sane_ordinary_ = false;
      trusted_ = true;
    }
    decision.generation = generation_;
    return decision;
  }
  decision.trusted_economic = trusted_ && sane_book;
  decision.generation = generation_;
  return decision;
}

const char* lock_status_name(LockStatus status) noexcept {
  switch (status) {
    case LockStatus::LOCKED:
      return "LOCKED";
    case LockStatus::WARMUP_NO_PREVIOUS:
      return "WARMUP_NO_PREVIOUS";
    case LockStatus::REFUSED_PREVIOUS_NO_OUTRIGHT:
      return "REFUSED_PREVIOUS_NO_OUTRIGHT";
  }
  return "UNKNOWN";
}

const char* phase_source_name(PhaseSource source) noexcept {
  switch (source) {
    case PhaseSource::TRAILING_252_PRIOR:
      return "TRAILING_252_PRIOR";
    case PhaseSource::FIXED_MIN60:
      return "FIXED_MIN60";
  }
  return "UNKNOWN";
}

std::vector<LockRow> derive_locks(const std::vector<TallyRow>& tallies) {
  std::map<std::int32_t, std::vector<const TallyRow*>> by_date;
  for (const TallyRow& row : tallies) {
    by_date[row.d8].push_back(&row);
  }
  std::vector<LockRow> out;
  out.reserve(by_date.size());
  const std::vector<const TallyRow*>* previous = nullptr;
  std::int32_t previous_d8 = -1;
  for (const auto& [d8, current] : by_date) {
    (void)current;
    const Date date = qr::futsess::date_from_yyyymmdd(d8);
    const auto [open, close] = qr::futsess::session_bounds(date);
    LockRow row;
    row.d8 = d8;
    row.open_utc = open;
    row.close_utc = close;
    if (previous == nullptr) {
      row.status = LockStatus::WARMUP_NO_PREVIOUS;
    } else {
      const TallyRow* winner = nullptr;
      for (const TallyRow* candidate : *previous) {
        if (!candidate->outright || candidate->updates == 0u) {
          continue;
        }
        if (winner == nullptr || candidate->updates > winner->updates ||
            (candidate->updates == winner->updates && candidate->iid < winner->iid)) {
          winner = candidate;
        }
      }
      row.selection_basis_d8 = previous_d8;
      if (winner == nullptr) {
        row.status = LockStatus::REFUSED_PREVIOUS_NO_OUTRIGHT;
      } else {
        row.status = LockStatus::LOCKED;
        row.locked_iid = static_cast<std::int64_t>(winner->iid);
        row.selection_basis_updates = winner->updates;
        row.selection_basis_symbol = winner->symbol;
      }
    }
    out.push_back(std::move(row));
    previous = &current;
    previous_d8 = d8;
  }
  return out;
}

std::vector<PhaseRow> derive_phase_schedule(const std::vector<TallyRow>& tallies,
                                            const std::vector<LockRow>& locks) {
  std::map<std::pair<std::int32_t, std::uint32_t>, const TallyRow*> tally_of;
  for (const TallyRow& row : tallies) {
    tally_of[{row.d8, row.iid}] = &row;
  }
  std::vector<std::pair<std::int32_t, std::array<std::uint64_t, kPhaseBins>>> clean;
  for (const LockRow& lock : locks) {
    if (lock.status != LockStatus::LOCKED || lock.locked_iid < 0 ||
        lock.locked_iid > static_cast<std::int64_t>(std::numeric_limits<std::uint32_t>::max())) {
      continue;
    }
    const auto found = tally_of.find(
        {lock.d8, static_cast<std::uint32_t>(lock.locked_iid)});
    if (found == tally_of.end()) {
      continue;
    }
    const auto& bins = found->second->phase_updates;
    const bool observed = std::any_of(bins.begin(), bins.end(), [](std::uint64_t v) {
      return v != 0u;
    });
    if (observed) {
      clean.emplace_back(lock.d8, bins);
    }
  }

  std::set<std::int32_t> months;
  for (const LockRow& lock : locks) {
    months.insert(lock.d8 / 100);
  }
  std::vector<PhaseRow> out;
  out.reserve(months.size());
  for (const std::int32_t month : months) {
    const std::int32_t cutoff = month * 100 + 1;
    const auto stop = std::lower_bound(clean.begin(), clean.end(), cutoff,
                                       [](const auto& row, std::int32_t value) {
                                         return row.first < value;
                                       });
    const std::size_t eligible = static_cast<std::size_t>(stop - clean.begin());
    const std::size_t begin_index = eligible > kPhaseLookback ? eligible - kPhaseLookback : 0u;
    std::vector<std::pair<std::int32_t, std::array<std::uint64_t, kPhaseBins>>> fit(
        clean.begin() + static_cast<std::ptrdiff_t>(begin_index), stop);
    PhaseRow row;
    row.month = month;
    row.n_fit = static_cast<std::uint32_t>(fit.size());
    if (!fit.empty()) {
      row.fit_start_d8 = fit.front().first;
      row.fit_end_d8 = fit.back().first;
    }
    row.profile_sha256 = profile_digest(fit);
    if (fit.size() >= kPhaseMinFit) {
      row.source = PhaseSource::TRAILING_252_PRIOR;
      std::array<double, kPhaseBins> raw{};
      for (const auto& item : fit) {
        for (std::size_t b = 0; b < kPhaseBins; ++b) {
          raw[b] += static_cast<double>(item.second[b]);
        }
      }
      std::array<double, kPhaseBins> smooth{};
      for (std::size_t b = 0; b < kPhaseBins; ++b) {
        const std::size_t prev = (b + kPhaseBins - 1u) % kPhaseBins;
        const std::size_t next = (b + 1u) % kPhaseBins;
        smooth[b] = (raw[prev] + raw[b] + raw[next]) / 3.0;
      }
      for (std::size_t i = 0; i < row.boundaries.size(); ++i) {
        row.boundaries[i] = find_boundary(smooth, kFixedPhaseBounds[i]);
      }
    } else {
      row.source = PhaseSource::FIXED_MIN60;
      row.boundaries = kFixedPhaseBounds;
    }
    out.push_back(std::move(row));
  }
  return out;
}

Expected<std::vector<TallyRow>, Refusal> read_tallies(const Config& config) {
  auto window = validate_window(config);
  if (!window) {
    return refuse<std::vector<TallyRow>>(window.error());
  }
  auto text = read_text(tally_path(config));
  if (!text) {
    return refuse<std::vector<TallyRow>>(text.error());
  }
  return parse_tallies(config, text.value());
}

Expected<std::vector<LockRow>, Refusal> read_locks(const Config& config) {
  auto window = validate_window(config);
  if (!window) {
    return refuse<std::vector<LockRow>>(window.error());
  }
  auto text = read_text(lock_path(config));
  if (!text) {
    return refuse<std::vector<LockRow>>(text.error());
  }
  return parse_locks(config, text.value());
}

Expected<std::vector<PhaseRow>, Refusal> read_phases(const Config& config) {
  auto window = validate_window(config);
  if (!window) {
    return refuse<std::vector<PhaseRow>>(window.error());
  }
  auto text = read_text(phase_path(config));
  if (!text) {
    return refuse<std::vector<PhaseRow>>(text.error());
  }
  return parse_phases(config, text.value());
}

Expected<EventPack, Refusal> read_event_pack(const std::string& path,
                                             const std::string& expected_sha256) {
  const std::vector<int> dates = qr::futsess::filename_dates(path);
  if (dates.size() != 1u || dates.front() < kDevelopmentStartD8 ||
      dates.front() >= kDevelopmentEndD8Exclusive ||
      fs::path(path).filename() != std::to_string(dates.front()) + ".qre2") {
    return refuse<EventPack>(Refusal(
        RefusalCode::DAY_OUTSIDE_CALENDAR, "qr_entry_v2::read_event_pack",
        "event filename must be an exact development YYYYMMDD.qre2 key"));
  }
  if (!expected_sha256.empty() && !valid_sha256(expected_sha256)) {
    return refuse<EventPack>(content_refusal(
        "qr_entry_v2::read_event_pack", "expected event-pack SHA-256 is malformed"));
  }
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    return refuse<EventPack>(
        io_refusal("qr_entry_v2::read_event_pack", "cannot open event pack"));
  }
  EventPack pack;
  EVP_MD_CTX* digest = EVP_MD_CTX_new();
  if (digest == nullptr || EVP_DigestInit_ex(digest, EVP_sha256(), nullptr) != 1) {
    EVP_MD_CTX_free(digest);
    return refuse<EventPack>(io_refusal(
        "qr_entry_v2::read_event_pack", "cannot initialize event-pack digest"));
  }
  const auto fail = [&digest](Refusal refusal) -> Expected<EventPack, Refusal> {
    EVP_MD_CTX_free(digest);
    digest = nullptr;
    return refuse<EventPack>(std::move(refusal));
  };
  std::array<std::uint8_t, kEventPackHeaderBytes> disk_header{};
  in.read(reinterpret_cast<char*>(disk_header.data()),
          static_cast<std::streamsize>(disk_header.size()));
  if (in.gcount() != static_cast<std::streamsize>(disk_header.size())) {
    return fail(content_refusal("qr_entry_v2::read_event_pack",
                                "event-pack header is truncated"));
  }
  if (EVP_DigestUpdate(digest, disk_header.data(), disk_header.size()) != 1) {
    return fail(io_refusal("qr_entry_v2::read_event_pack",
                           "cannot hash event-pack header"));
  }
  const auto load = [&disk_header](std::size_t offset, auto* value) {
    std::memcpy(value, disk_header.data() + offset, sizeof(*value));
  };
  std::memcpy(pack.header.magic, disk_header.data(), 8);
  load(8, &pack.header.version);
  pack.header.asset_idx = disk_header[12];
  std::memcpy(pack.header.reserved_asset, disk_header.data() + 13, 3);
  load(16, &pack.header.d8);
  load(20, &pack.header.locked_iid);
  load(28, &pack.header.open_utc);
  load(36, &pack.header.close_utc);
  load(44, &pack.header.n_events);
  load(52, &pack.header.row_bytes);
  load(56, &pack.header.reserved);
  if (std::memcmp(pack.header.magic, "QRE2EVT2", 8) != 0 || pack.header.version != 2u ||
      pack.header.row_bytes != kEventRowBytes) {
    return fail(content_refusal(
        "qr_entry_v2::read_event_pack",
        "event-pack header does not match QRE2EVT2; V1 reinterpretation is forbidden"));
  }
  if (pack.header.asset_idx > 2u || pack.header.locked_iid < 0 ||
      pack.header.d8 != dates.front() || pack.header.reserved != 0u ||
      std::any_of(std::begin(pack.header.reserved_asset),
                  std::end(pack.header.reserved_asset),
                  [](std::uint8_t byte) { return byte != 0u; })) {
    return fail(content_refusal(
        "qr_entry_v2::read_event_pack", "event-pack key/reserved fields are invalid"));
  }
  auto tz = qr::futsess::init_globex_timezone();
  if (!tz) return fail(tz.error());
  const auto bounds = qr::futsess::session_bounds(
      qr::futsess::date_from_yyyymmdd(pack.header.d8));
  if (pack.header.open_utc != bounds.first || pack.header.close_utc != bounds.second ||
      pack.header.close_utc <= pack.header.open_utc) {
    return fail(content_refusal(
        "qr_entry_v2::read_event_pack", "event-pack session bounds are not canonical"));
  }
  if (pack.header.n_events >
      static_cast<std::uint64_t>(std::numeric_limits<std::size_t>::max())) {
    return fail(Refusal(RefusalCode::ARITHMETIC_OVERFLOW,
                        "qr_entry_v2::read_event_pack",
                        "event count does not fit address space"));
  }
  pack.rows.resize(static_cast<std::size_t>(pack.header.n_events));
  constexpr std::size_t kChunkRows = 4096;
  std::vector<std::uint8_t> buffer(kChunkRows * kEventRowBytes);
  for (std::size_t begin = 0; begin < pack.rows.size(); begin += kChunkRows) {
    const std::size_t count = std::min(kChunkRows, pack.rows.size() - begin);
    const std::size_t bytes = count * kEventRowBytes;
    in.read(reinterpret_cast<char*>(buffer.data()), static_cast<std::streamsize>(bytes));
    if (in.gcount() != static_cast<std::streamsize>(bytes)) {
      return fail(content_refusal("qr_entry_v2::read_event_pack",
                                  "event-pack payload is truncated"));
    }
    if (EVP_DigestUpdate(digest, buffer.data(), bytes) != 1) {
      return fail(io_refusal("qr_entry_v2::read_event_pack",
                             "cannot hash event-pack payload"));
    }
    for (std::size_t i = 0; i < count; ++i) {
      std::memcpy(&pack.rows[begin + i], buffer.data() + i * kEventRowBytes,
                  kEventRowBytes);
    }
  }
  char trailing = 0;
  if (in.read(&trailing, 1)) {
    return fail(content_refusal("qr_entry_v2::read_event_pack",
                                "event pack has trailing bytes"));
  }
  if (!std::is_sorted(pack.rows.begin(), pack.rows.end(), [](const EventRow& lhs,
                                                             const EventRow& rhs) {
        return lhs.ts_recv_ns < rhs.ts_recv_ns;
      })) {
    return fail(Refusal(RefusalCode::OUT_OF_ORDER,
                        "qr_entry_v2::read_event_pack",
                        "event rows descend in physical receive-time order"));
  }
  for (const EventRow& row : pack.rows) {
    if (row.ts_recv_ns > static_cast<std::uint64_t>(
                             std::numeric_limits<std::int64_t>::max())) {
      return fail(content_refusal(
          "qr_entry_v2::read_event_pack", "event row has invalid reserved/clock field"));
    }
    const std::int64_t sec = static_cast<std::int64_t>(row.ts_recv_ns / kNsPerSecond);
    if (sec < pack.header.open_utc || sec >= pack.header.close_utc ||
        row.receive_session_sec != sec - pack.header.open_utc) {
      return fail(content_refusal(
          "qr_entry_v2::read_event_pack", "event row is outside/corrupts session clock"));
    }
  }
  std::array<unsigned char, EVP_MAX_MD_SIZE> digest_bytes{};
  unsigned int digest_length = 0;
  if (EVP_DigestFinal_ex(digest, digest_bytes.data(), &digest_length) != 1 ||
      digest_length != 32u) {
    return fail(io_refusal("qr_entry_v2::read_event_pack",
                           "cannot finalize event-pack digest"));
  }
  EVP_MD_CTX_free(digest);
  digest = nullptr;
  pack.artifact_sha256 = hex_digest(digest_bytes.data(), digest_length);
  if (!expected_sha256.empty() && pack.artifact_sha256 != expected_sha256) {
    return refuse<EventPack>(content_refusal(
        "qr_entry_v2::read_event_pack", "event-pack bytes differ from pinned SHA-256"));
  }
  return pack;
}

std::string event_pack_sha256(const EventPack& pack) {
  if (!pack.artifact_sha256.empty()) return pack.artifact_sha256;
  EVP_MD_CTX* digest = EVP_MD_CTX_new();
  if (digest == nullptr || EVP_DigestInit_ex(digest, EVP_sha256(), nullptr) != 1) {
    EVP_MD_CTX_free(digest);
    return {};
  }
  const auto header = encode_event_header(pack.header);
  bool ok = EVP_DigestUpdate(digest, header.data(), header.size()) == 1;
  for (const EventRow& row : pack.rows) {
    ok = ok && EVP_DigestUpdate(digest, &row, kEventRowBytes) == 1;
  }
  std::array<unsigned char, EVP_MAX_MD_SIZE> bytes{};
  unsigned int length = 0;
  ok = ok && EVP_DigestFinal_ex(digest, bytes.data(), &length) == 1 && length == 32u;
  EVP_MD_CTX_free(digest);
  return ok ? hex_digest(bytes.data(), length) : std::string{};
}

std::size_t event_cutoff(const std::vector<EventRow>& rows,
                         std::uint64_t decision_ts_ns) noexcept {
  return static_cast<std::size_t>(
      std::lower_bound(rows.begin(), rows.end(), decision_ts_ns,
                       [](const EventRow& row, std::uint64_t ts) {
                         return row.ts_recv_ns < ts;
                       }) -
      rows.begin());
}

Expected<StageStats, Refusal> run_tally(const Config& config) {
  auto tz = qr::futsess::init_globex_timezone();
  if (!tz) {
    return refuse<StageStats>(tz.error());
  }
  auto inspected = inspect_inputs(config);
  if (!inspected) {
    return refuse<StageStats>(inspected.error());
  }
  auto input_sha = publish_inputs(config, inspected.value(), false);
  if (!input_sha) {
    return refuse<StageStats>(input_sha.error());
  }

  std::map<std::pair<std::int32_t, std::uint32_t>, TallyRow> table;
  std::map<std::uint32_t, BookQualityState> quality_by_iid;
  std::map<std::uint32_t, BadTsRecvGap> bad_ts_recv_gaps;
  StageStats stats;
  std::int32_t last_d8 = -1;
  std::uint64_t source_ordinal_base = 0;
  std::uint64_t previous_ts_recv_ns = 0;
  bool have_previous_ts_recv = false;
  bool reached_pre_h2_boundary = false;
  const auto finalize_session = [&](std::int32_t d8) {
    if (d8 < config.start_d8 || d8 >= config.end_d8_exclusive) return;
    for (auto& [key, row] : table) {
      if (key.first != d8) continue;
      const auto quality = quality_by_iid.find(key.second);
      if (quality != quality_by_iid.end() && quality->second.unresolved_taint()) {
        // A MAYBE_BAD_BOOK without a later clean snapshot makes every economic
        // observation for this instrument-session unusable, including rows
        // that happened before the taint was first reported.
        row.updates = 0;
        row.trusted_economic_records = 0;
        row.phase_updates.fill(0);
      }
    }
  };
  for (const InputRow& input : inspected.value()) {
    qr::databento::Mbp1File stream;
    auto opened = stream.open(input.path, source_ordinal_base);
    if (!opened) {
      return refuse<StageStats>(opened.error());
    }
    auto metadata_ok = validate_input_metadata(stream.metadata(), input.access);
    if (!metadata_ok) {
      return refuse<StageStats>(metadata_ok.error());
    }
    for (;;) {
      auto next = stream.next_mbp1();
      if (!next) {
        return refuse<StageStats>(next.error());
      }
      if (!next.value().has_value()) {
        break;
      }
      const qr::databento::Mbp1Row& message = *next.value();
      if (standalone_bad_ts_recv(message.flags)) {
        auto noted = note_bad_ts_recv(&bad_ts_recv_gaps, message.instrument_id,
                                      "qr_entry_v2::run_tally");
        if (!noted) return refuse<StageStats>(noted.error());
        continue;
      }
      if (message.ts_recv_ns >= kPreH2ReceiveEndExclusiveNs) {
        if (input.access != "DEVELOPMENT_PREFIX") {
          return refuse<StageStats>(Refusal(
              RefusalCode::DAY_OUTSIDE_CALENDAR, "qr_entry_v2::run_tally",
              "non-prefix input produced a record at/after the pre-H2 wall"));
        }
        // The official decoder and zstd layer may transport/decode this one
        // fixed-size boundary sentinel (and buffered bytes). IndexTs is the
        // only field inspected here. It never reaches record validation,
        // ordering, session assignment, book state, tallies, or artifacts.
        auto closed = require_no_open_bad_ts_recv_gap(
            bad_ts_recv_gaps, "qr_entry_v2::run_tally");
        if (!closed) return refuse<StageStats>(closed.error());
        reached_pre_h2_boundary = true;
        break;
      }
      auto record_ok = validate_record_window(stream.metadata(), message);
      if (!record_ok) {
        return refuse<StageStats>(record_ok.error());
      }
      if (have_previous_ts_recv && message.ts_recv_ns < previous_ts_recv_ns) {
        return refuse<StageStats>(Refusal(
            RefusalCode::OUT_OF_ORDER, "qr_entry_v2::run_tally",
            "IndexTs/ts_recv descends in ordered manifest decoder order",
            static_cast<std::int64_t>(message.source_ordinal)));
      }
      previous_ts_recv_ns = message.ts_recv_ns;
      have_previous_ts_recv = true;
      auto td = trade_date_for(message.ts_recv_ns);
      if (!td) {
        if (is_outside_session(td.error())) {
          continue;
        }
        return refuse<StageStats>(td.error());
      }
      const std::int32_t d8 = td.value().yyyymmdd();
      if (last_d8 >= 0 && d8 < last_d8) {
        return refuse<StageStats>(Refusal(
            RefusalCode::OUT_OF_ORDER, "qr_entry_v2::run_tally",
            "input payloads are not chronological by trade date", d8));
      }
      if (last_d8 >= 0 && d8 != last_d8) {
        auto closed = require_no_open_bad_ts_recv_gap(
            bad_ts_recv_gaps, "qr_entry_v2::run_tally");
        if (!closed) return refuse<StageStats>(closed.error());
        finalize_session(last_d8);
      }
      last_d8 = d8;
      const auto book = qr::futsess::classify_book(message.bid_px, message.ask_px);
      const bool sane_book = book.state == qr::futsess::kStTwoSided;
      auto clock = observe_clean_clock(&bad_ts_recv_gaps, message.instrument_id,
                                       d8, message.flags, sane_book,
                                       "qr_entry_v2::run_tally");
      if (!clock) return refuse<StageStats>(clock.error());
      auto quality = quality_by_iid[message.instrument_id].observe(
          message.ts_recv_ns, message.flags, sane_book);
      if (!quality) {
        return refuse<StageStats>(quality.error());
      }
      if (d8 < config.start_d8 || d8 >= config.end_d8_exclusive) {
        continue;
      }
      const std::uint32_t iid = message.instrument_id;
      TallyRow& row = table[{d8, iid}];
      if (row.symbol.empty()) {
        row.d8 = d8;
        row.iid = iid;
        row.symbol = message.raw_symbol;
        if (row.symbol.empty()) {
          return refuse<StageStats>(content_refusal(
              "qr_entry_v2::run_tally",
              "official adapter returned an empty exact UTC IndexTs symbol", d8));
        }
        row.outright = !row.symbol.empty() && row.symbol.find('-') == std::string::npos;
      } else if (message.raw_symbol != row.symbol) {
        return refuse<StageStats>(content_refusal(
            "qr_entry_v2::run_tally",
            "instrument maps to conflicting exact UTC IndexTs symbols", d8));
      }
      ++row.raw_records;
      if (clock.value().resolved_bad_records != 0u) {
        if (row.raw_records > std::numeric_limits<std::uint64_t>::max() -
                                  clock.value().resolved_bad_records ||
            row.standalone_bad_ts_recv_records >
                std::numeric_limits<std::uint64_t>::max() -
                    clock.value().resolved_bad_records) {
          return refuse<StageStats>(Refusal(
              RefusalCode::ARITHMETIC_OVERFLOW, "qr_entry_v2::run_tally",
              "bracketed standalone BAD_TS_RECV tally count overflow",
              static_cast<std::int64_t>(iid)));
        }
        row.raw_records += clock.value().resolved_bad_records;
        row.standalone_bad_ts_recv_records +=
            clock.value().resolved_bad_records;
      }
      if (quality.value().snapshot_row) ++row.snapshot_records;
      if (quality.value().maybe_bad_book_row) ++row.maybe_bad_book_records;
      if (quality.value().trusted_economic &&
          !clock.value().quarantine_economic) {
        ++row.updates;
        ++row.trusted_economic_records;
        const std::uint64_t sec = message.ts_recv_ns /
                                  static_cast<std::uint64_t>(kNsPerSecond);
        const std::size_t bin = static_cast<std::size_t>(
            (sec % static_cast<std::uint64_t>(qr::futsess::kSecondsPerDay)) /
            static_cast<std::uint64_t>(kPhaseBinSeconds));
        ++row.phase_updates[bin];
      }
    }
    if (stream.records_read() >
        std::numeric_limits<std::uint64_t>::max() - source_ordinal_base) {
      return refuse<StageStats>(Refusal(
          RefusalCode::ARITHMETIC_OVERFLOW, "qr_entry_v2::run_tally",
          "ordered input manifest source ordinal overflow"));
    }
    source_ordinal_base += stream.records_read();
    if (reached_pre_h2_boundary) break;
  }
  auto closed = require_no_open_bad_ts_recv_gap(
      bad_ts_recv_gaps, "qr_entry_v2::run_tally");
  if (!closed) return refuse<StageStats>(closed.error());
  if (last_d8 >= 0) finalize_session(last_d8);
  std::vector<TallyRow> rows;
  rows.reserve(table.size());
  for (auto& [key, row] : table) {
    (void)key;
    stats.raw_records += row.raw_records;
    stats.trusted_economic_records += row.trusted_economic_records;
    stats.snapshot_records += row.snapshot_records;
    stats.standalone_bad_ts_recv_records += row.standalone_bad_ts_recv_records;
    stats.maybe_bad_book_records += row.maybe_bad_book_records;
    rows.push_back(std::move(row));
  }
  stats.records = stats.raw_records;
  const std::string text = render_tallies(config, rows);
  auto wrote = write_atomic(tally_path(config), text);
  if (!wrote) {
    return refuse<StageStats>(wrote.error());
  }
  stats.rows = rows.size();
  stats.content_hashed_inputs = inspected.value().size();
  stats.trusted_hash_inputs = 0;
  stats.output_sha256 = sha256_bytes(text);
  auto receipt = publish_receipt(config, "tally", input_sha.value(), stats.output_sha256,
                                 stats.rows, stats.records, 0, stats.content_hashed_inputs,
                                 stats.trusted_hash_inputs, stats.raw_records,
                                 stats.trusted_economic_records, stats.snapshot_records,
                                 stats.standalone_bad_ts_recv_records,
                                 stats.maybe_bad_book_records);
  if (!receipt) {
    return refuse<StageStats>(receipt.error());
  }
  stats.receipt_sha256 = receipt.value();
  return stats;
}

Expected<StageStats, Refusal> run_lock(const Config& config) {
  auto tz = qr::futsess::init_globex_timezone();
  if (!tz) {
    return refuse<StageStats>(tz.error());
  }
  auto tallies = read_tallies(config);
  if (!tallies) {
    return refuse<StageStats>(tallies.error());
  }
  auto tally_text = read_text(tally_path(config));
  if (!tally_text) {
    return refuse<StageStats>(tally_text.error());
  }
  const std::vector<LockRow> rows = derive_locks(tallies.value());
  const std::string text = render_locks(config, rows);
  auto wrote = write_atomic(lock_path(config), text);
  if (!wrote) {
    return refuse<StageStats>(wrote.error());
  }
  StageStats stats;
  stats.rows = rows.size();
  for (const TallyRow& row : tallies.value()) {
    stats.raw_records += row.raw_records;
    stats.trusted_economic_records += row.trusted_economic_records;
    stats.snapshot_records += row.snapshot_records;
    stats.standalone_bad_ts_recv_records += row.standalone_bad_ts_recv_records;
    stats.maybe_bad_book_records += row.maybe_bad_book_records;
  }
  stats.records = stats.raw_records;
  stats.refusals = static_cast<std::uint64_t>(std::count_if(
      rows.begin(), rows.end(), [](const LockRow& row) { return row.status != LockStatus::LOCKED; }));
  stats.output_sha256 = sha256_bytes(text);
  auto receipt = publish_receipt(config, "lock", sha256_bytes(tally_text.value()),
                                 stats.output_sha256, stats.rows, stats.records,
                                 stats.refusals, 0, 0, stats.raw_records,
                                 stats.trusted_economic_records, stats.snapshot_records,
                                 stats.standalone_bad_ts_recv_records,
                                 stats.maybe_bad_book_records);
  if (!receipt) {
    return refuse<StageStats>(receipt.error());
  }
  stats.receipt_sha256 = receipt.value();
  return stats;
}

Expected<StageStats, Refusal> run_phase(const Config& config) {
  auto tallies = read_tallies(config);
  if (!tallies) {
    return refuse<StageStats>(tallies.error());
  }
  auto locks = read_locks(config);
  if (!locks) {
    return refuse<StageStats>(locks.error());
  }
  auto tally_text = read_text(tally_path(config));
  auto lock_text = read_text(lock_path(config));
  if (!tally_text) {
    return refuse<StageStats>(tally_text.error());
  }
  if (!lock_text) {
    return refuse<StageStats>(lock_text.error());
  }
  const std::vector<PhaseRow> rows = derive_phase_schedule(tallies.value(), locks.value());
  const std::string text = render_phases(config, rows);
  auto wrote = write_atomic(phase_path(config), text);
  if (!wrote) {
    return refuse<StageStats>(wrote.error());
  }
  StageStats stats;
  stats.rows = rows.size();
  for (const TallyRow& row : tallies.value()) {
    stats.raw_records += row.raw_records;
    stats.trusted_economic_records += row.trusted_economic_records;
    stats.snapshot_records += row.snapshot_records;
    stats.standalone_bad_ts_recv_records += row.standalone_bad_ts_recv_records;
    stats.maybe_bad_book_records += row.maybe_bad_book_records;
  }
  stats.records = stats.raw_records;
  stats.refusals = static_cast<std::uint64_t>(std::count_if(
      rows.begin(), rows.end(), [](const PhaseRow& row) {
        return row.source == PhaseSource::FIXED_MIN60;
      }));
  stats.output_sha256 = sha256_bytes(text);
  const std::string input_sha =
      sha256_bytes(sha256_bytes(tally_text.value()) + "\n" + sha256_bytes(lock_text.value()));
  auto receipt = publish_receipt(config, "phase", input_sha, stats.output_sha256, stats.rows,
                                 stats.records, stats.refusals, 0, 0, stats.raw_records,
                                 stats.trusted_economic_records, stats.snapshot_records,
                                 stats.standalone_bad_ts_recv_records,
                                 stats.maybe_bad_book_records);
  if (!receipt) {
    return refuse<StageStats>(receipt.error());
  }
  stats.receipt_sha256 = receipt.value();
  return stats;
}

Expected<StageStats, Refusal> run_events(const Config& config) {
  auto tz = qr::futsess::init_globex_timezone();
  if (!tz) {
    return refuse<StageStats>(tz.error());
  }
  auto locks = read_locks(config);
  if (!locks) {
    return refuse<StageStats>(locks.error());
  }
  auto phases = read_phases(config);
  if (!phases) {
    return refuse<StageStats>(phases.error());
  }
  (void)phases;
  auto lock_text = read_text(lock_path(config));
  auto phase_text = read_text(phase_path(config));
  if (!lock_text) {
    return refuse<StageStats>(lock_text.error());
  }
  if (!phase_text) {
    return refuse<StageStats>(phase_text.error());
  }
  const std::string locks_sha = sha256_bytes(lock_text.value());
  const std::string phase_sha = sha256_bytes(phase_text.value());
  auto inspected = inspect_inputs(config);
  if (!inspected) {
    return refuse<StageStats>(inspected.error());
  }
  auto input_sha = publish_inputs(config, inspected.value(), true);
  if (!input_sha) {
    return refuse<StageStats>(input_sha.error());
  }

  std::map<std::int32_t, std::size_t> manifest_index;
  std::vector<EventManifestRow> manifest;
  manifest.reserve(locks.value().size());
  for (const LockRow& lock : locks.value()) {
    EventManifestRow row;
    row.lock = lock;
    row.status = lock.status == LockStatus::LOCKED ? "NO_EVENTS" : lock_status_name(lock.status);
    manifest_index.emplace(lock.d8, manifest.size());
    manifest.push_back(std::move(row));
  }

  std::int32_t current_d8 = -1;
  std::int32_t last_d8 = -1;
  std::vector<EventRow> current_events;
  std::map<std::uint32_t, BookQualityState> quality_by_iid;
  std::map<std::uint32_t, BadTsRecvGap> bad_ts_recv_gaps;
  StageStats stats;
  std::uint64_t source_ordinal_base = 0;
  std::uint64_t previous_ts_recv_ns = 0;
  bool have_previous_ts_recv = false;
  bool reached_pre_h2_boundary = false;
  const auto flush = [&](std::int32_t d8, std::vector<EventRow>* events)
      -> Expected<std::monostate, Refusal> {
    if (d8 < 0) {
      events->clear();
      return std::monostate{};
    }
    const auto found = manifest_index.find(d8);
    if (found == manifest_index.end()) {
      events->clear();
      return std::monostate{};
    }
    EventManifestRow& item = manifest[found->second];
    if (item.lock.status != LockStatus::LOCKED) {
      events->clear();
      return std::monostate{};
    }
    if (item.status == "BAD_TS_RECV_CLOCK_TAINT") {
      // A prior run may have emitted this deterministic path.  A tainted
      // session is an explicit no-pack authority, so remove that stale pack.
      const fs::path stale = event_dir(config) / (std::to_string(d8) + ".qre2");
      std::error_code ec;
      fs::remove(stale, ec);
      if (ec) {
        return refuse<std::monostate>(io_refusal(
            "qr_entry_v2::run_events", "cannot remove stale tainted event pack"));
      }
      item.n_events = 0;
      item.min_ts_recv_ns = 0;
      item.max_ts_recv_ns = 0;
      item.min_ts_event_ns = 0;
      item.max_ts_event_ns = 0;
      item.trusted_economic_records = 0;
      item.binary_rel.clear();
      item.binary_sha256.clear();
      events->clear();
      return std::monostate{};
    }
    const auto quality = quality_by_iid.find(
        static_cast<std::uint32_t>(item.lock.locked_iid));
    if (quality != quality_by_iid.end() && quality->second.unresolved_taint()) {
      item.status = "UNRESOLVED_MAYBE_BAD_BOOK";
      item.trusted_economic_records = 0;
      events->clear();
      return std::monostate{};
    }
    if (events->empty()) {
      events->clear();
      return std::monostate{};
    }
    if (!std::is_sorted(events->begin(), events->end(), [](const EventRow& lhs,
                                                           const EventRow& rhs) {
          return lhs.ts_recv_ns < rhs.ts_recv_ns;
        })) {
      return refuse<std::monostate>(Refusal(
          RefusalCode::OUT_OF_ORDER, "qr_entry_v2::run_events",
          "selected rows descend in physical IndexTs order"));
    }
    EventPackHeader header{};
    std::memcpy(header.magic, "QRE2EVT2", 8);
    header.version = 2;
    header.asset_idx = asset_index(config.asset);
    header.d8 = d8;
    header.locked_iid = item.lock.locked_iid;
    header.open_utc = item.lock.open_utc;
    header.close_utc = item.lock.close_utc;
    header.n_events = events->size();
    header.row_bytes = kEventRowBytes;
    const std::string filename = std::to_string(d8) + ".qre2";
    const fs::path path = event_dir(config) / filename;
    auto wrote = write_event_binary(path, header, *events);
    if (!wrote) {
      return wrote;
    }
    auto hash = sha256_file(path);
    if (!hash) {
      return refuse<std::monostate>(hash.error());
    }
    item.status = "READY";
    item.n_events = events->size();
    item.min_ts_recv_ns = events->front().ts_recv_ns;
    item.max_ts_recv_ns = events->back().ts_recv_ns;
    const auto event_bounds = std::minmax_element(
        events->begin(), events->end(), [](const EventRow& lhs, const EventRow& rhs) {
          return lhs.ts_event_ns < rhs.ts_event_ns;
        });
    item.min_ts_event_ns = event_bounds.first->ts_event_ns;
    item.max_ts_event_ns = event_bounds.second->ts_event_ns;
    item.binary_rel = std::string("events/") + asset_name(config.asset) + "/" + filename;
    item.binary_sha256 = hash.value();
    events->clear();
    return std::monostate{};
  };

  for (const InputRow& input : inspected.value()) {
    qr::databento::Mbp1File stream;
    auto opened = stream.open(input.path, source_ordinal_base);
    if (!opened) {
      return refuse<StageStats>(opened.error());
    }
    auto metadata_ok = validate_input_metadata(stream.metadata(), input.access);
    if (!metadata_ok) {
      return refuse<StageStats>(metadata_ok.error());
    }
    for (;;) {
      auto next = stream.next_mbp1();
      if (!next) {
        return refuse<StageStats>(next.error());
      }
      if (!next.value().has_value()) {
        break;
      }
      const qr::databento::Mbp1Row& message = *next.value();
      if (standalone_bad_ts_recv(message.flags)) {
        auto noted = note_bad_ts_recv(&bad_ts_recv_gaps, message.instrument_id,
                                      "qr_entry_v2::run_events");
        if (!noted) return refuse<StageStats>(noted.error());
        continue;
      }
      if (message.ts_recv_ns >= kPreH2ReceiveEndExclusiveNs) {
        if (input.access != "DEVELOPMENT_PREFIX") {
          return refuse<StageStats>(Refusal(
              RefusalCode::DAY_OUTSIDE_CALENDAR, "qr_entry_v2::run_events",
              "non-prefix input produced a record at/after the pre-H2 wall"));
        }
        // Transport-only sentinel: do not validate, order, partition, mutate
        // state, increment counters, or emit any Entry V2 artifact from it.
        auto closed = require_no_open_bad_ts_recv_gap(
            bad_ts_recv_gaps, "qr_entry_v2::run_events");
        if (!closed) return refuse<StageStats>(closed.error());
        reached_pre_h2_boundary = true;
        break;
      }
      auto record_ok = validate_record_window(stream.metadata(), message);
      if (!record_ok) {
        return refuse<StageStats>(record_ok.error());
      }
      if (have_previous_ts_recv && message.ts_recv_ns < previous_ts_recv_ns) {
        return refuse<StageStats>(Refusal(
            RefusalCode::OUT_OF_ORDER, "qr_entry_v2::run_events",
            "IndexTs/ts_recv descends in ordered manifest decoder order",
            static_cast<std::int64_t>(message.source_ordinal)));
      }
      previous_ts_recv_ns = message.ts_recv_ns;
      have_previous_ts_recv = true;
      auto td = trade_date_for(message.ts_recv_ns);
      if (!td) {
        if (is_outside_session(td.error())) {
          continue;
        }
        return refuse<StageStats>(td.error());
      }
      const std::int32_t d8 = td.value().yyyymmdd();
      if (last_d8 >= 0 && d8 < last_d8) {
        return refuse<StageStats>(Refusal(
            RefusalCode::OUT_OF_ORDER, "qr_entry_v2::run_events",
            "input payloads are not chronological by trade date", d8));
      }
      if (current_d8 >= 0 && d8 != current_d8) {
        auto closed = require_no_open_bad_ts_recv_gap(
            bad_ts_recv_gaps, "qr_entry_v2::run_events");
        if (!closed) return refuse<StageStats>(closed.error());
        auto flushed = flush(current_d8, &current_events);
        if (!flushed) return refuse<StageStats>(flushed.error());
      }
      last_d8 = d8;
      current_d8 = d8;
      const auto book = qr::futsess::classify_book(message.bid_px, message.ask_px);
      const bool sane_book = book.state == qr::futsess::kStTwoSided;
      auto clock = observe_clean_clock(&bad_ts_recv_gaps, message.instrument_id,
                                       d8, message.flags, sane_book,
                                       "qr_entry_v2::run_events");
      if (!clock) return refuse<StageStats>(clock.error());
      auto quality = quality_by_iid[message.instrument_id].observe(
          message.ts_recv_ns, message.flags, sane_book);
      if (!quality) {
        return refuse<StageStats>(quality.error());
      }
      if (d8 < config.start_d8 || d8 >= config.end_d8_exclusive) {
        continue;
      }
      ++stats.records;
      ++stats.raw_records;
      if (clock.value().resolved_bad_records != 0u) {
        stats.records += clock.value().resolved_bad_records;
        stats.raw_records += clock.value().resolved_bad_records;
      }
      const auto mi = manifest_index.find(d8);
      if (mi == manifest_index.end()) {
        continue;
      }
      const LockRow& lock = manifest[mi->second].lock;
      if (lock.status != LockStatus::LOCKED || lock.locked_iid < 0 ||
          static_cast<std::uint64_t>(lock.locked_iid) != message.instrument_id) {
        continue;
      }
      EventManifestRow& item = manifest[mi->second];
      if (clock.value().resolved_bad_records != 0u) {
        item.status = "BAD_TS_RECV_CLOCK_TAINT";
        item.raw_records += clock.value().resolved_bad_records;
        item.standalone_bad_ts_recv_records +=
            clock.value().resolved_bad_records;
        item.trusted_economic_records = 0;
        current_events.clear();
      }
      ++item.raw_records;
      if (quality.value().snapshot_row) ++item.snapshot_records;
      if (quality.value().maybe_bad_book_row) ++item.maybe_bad_book_records;
      if (item.status == "BAD_TS_RECV_CLOCK_TAINT") {
        continue;
      }
      if (quality.value().trusted_economic &&
          !clock.value().quarantine_economic) {
        ++item.trusted_economic_records;
      }
      const std::uint64_t sec = message.ts_recv_ns /
                                static_cast<std::uint64_t>(kNsPerSecond);
      EventRow row{};
      row.ts_recv_ns = message.ts_recv_ns;
      row.ts_event_ns = message.ts_event_ns;
      row.price = message.price;
      row.bid_px = message.bid_px;
      row.ask_px = message.ask_px;
      row.size = message.size;
      row.bid_sz = message.bid_sz;
      row.ask_sz = message.ask_sz;
      row.bid_ct = message.bid_ct;
      row.ask_ct = message.ask_ct;
      row.sequence = message.sequence;
      row.ts_in_delta = message.ts_in_delta_ns;
      row.receive_session_sec = static_cast<std::int32_t>(
          static_cast<std::int64_t>(sec) - lock.open_utc);
      row.action = message.action;
      row.side = message.side;
      row.flags = message.flags;
      row.depth = message.depth;
      current_events.push_back(row);
    }
    if (stream.records_read() >
        std::numeric_limits<std::uint64_t>::max() - source_ordinal_base) {
      return refuse<StageStats>(Refusal(
          RefusalCode::ARITHMETIC_OVERFLOW, "qr_entry_v2::run_events",
          "ordered input manifest source ordinal overflow"));
    }
    source_ordinal_base += stream.records_read();
    if (reached_pre_h2_boundary) break;
  }
  auto closed = require_no_open_bad_ts_recv_gap(
      bad_ts_recv_gaps, "qr_entry_v2::run_events");
  if (!closed) return refuse<StageStats>(closed.error());
  auto flushed = flush(current_d8, &current_events);
  if (!flushed) {
    return refuse<StageStats>(flushed.error());
  }

  for (EventManifestRow& row : manifest) {
    const std::string filename = std::to_string(row.lock.d8) + ".qre2.json";
    row.sidecar_rel = std::string("events/") + asset_name(config.asset) + "/" + filename;
    const std::string sidecar =
        event_sidecar_json(config, row, input_sha.value(), locks_sha, phase_sha);
    auto wrote = write_atomic(event_dir(config) / filename, sidecar);
    if (!wrote) {
      return refuse<StageStats>(wrote.error());
    }
    row.sidecar_sha256 = sha256_bytes(sidecar);
  }
  const std::string manifest_text = render_event_manifest(config, manifest);
  const fs::path manifest_path = event_dir(config) / "manifest.tsv";
  auto wrote = write_atomic(manifest_path, manifest_text);
  if (!wrote) {
    return refuse<StageStats>(wrote.error());
  }
  stats.rows = manifest.size();
  stats.trusted_economic_records = 0;
  stats.snapshot_records = 0;
  stats.standalone_bad_ts_recv_records = 0;
  stats.maybe_bad_book_records = 0;
  for (const EventManifestRow& row : manifest) {
    stats.trusted_economic_records += row.trusted_economic_records;
    stats.snapshot_records += row.snapshot_records;
    stats.standalone_bad_ts_recv_records += row.standalone_bad_ts_recv_records;
    stats.maybe_bad_book_records += row.maybe_bad_book_records;
  }
  stats.content_hashed_inputs = inspected.value().size();
  stats.trusted_hash_inputs = 0;
  stats.refusals = static_cast<std::uint64_t>(std::count_if(
      manifest.begin(), manifest.end(), [](const EventManifestRow& row) {
        return row.status != "READY";
      }));
  stats.output_sha256 = sha256_bytes(manifest_text);
  const std::string source_sha =
      sha256_bytes(input_sha.value() + "\n" + locks_sha + "\n" + phase_sha);
  auto receipt = publish_receipt(config, "events", source_sha, stats.output_sha256, stats.rows,
                                 stats.records, stats.refusals, stats.content_hashed_inputs,
                                 stats.trusted_hash_inputs, stats.raw_records,
                                 stats.trusted_economic_records, stats.snapshot_records,
                                 stats.standalone_bad_ts_recv_records,
                                 stats.maybe_bad_book_records);
  if (!receipt) {
    return refuse<StageStats>(receipt.error());
  }
  stats.receipt_sha256 = receipt.value();
  return stats;
}

Expected<StageStats, Refusal> run(const Config& config, Stage stage) {
  switch (stage) {
    case Stage::TALLY:
      return run_tally(config);
    case Stage::LOCK:
      return run_lock(config);
    case Stage::PHASE:
      return run_phase(config);
    case Stage::EVENTS:
      return run_events(config);
    case Stage::ALL: {
      auto tally = run_tally(config);
      if (!tally) {
        return refuse<StageStats>(tally.error());
      }
      auto lock = run_lock(config);
      if (!lock) {
        return refuse<StageStats>(lock.error());
      }
      auto phase = run_phase(config);
      if (!phase) {
        return refuse<StageStats>(phase.error());
      }
      return run_events(config);
    }
  }
  return refuse<StageStats>(
      Refusal(RefusalCode::CONFIG, "qr_entry_v2::run", "unknown stage"));
}

Expected<Stage, Refusal> stage_from_name(const std::string& name) {
  if (name == "tally") {
    return Stage::TALLY;
  }
  if (name == "lock") {
    return Stage::LOCK;
  }
  if (name == "phase") {
    return Stage::PHASE;
  }
  if (name == "events") {
    return Stage::EVENTS;
  }
  if (name == "all") {
    return Stage::ALL;
  }
  return refuse<Stage>(Refusal(RefusalCode::CONFIG, "qr_entry_v2::stage_from_name",
                               "stage must be tally, lock, phase, events, or all"));
}

}  // namespace qr::entry_v2
