#include "qr_entry_v2/g1.hpp"

#include <openssl/evp.h>

#include <algorithm>
#include <array>
#include <bit>
#include <charconv>
#include <cmath>
#include <cstdlib>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>
#include <map>
#include <set>
#include <sstream>
#include <string_view>
#include <tuple>
#include <utility>

#include "qr_futsess/json.hpp"

namespace qr::entry_v2 {
namespace {

namespace fs = std::filesystem;
using qr::futsess::JsonWriter;

constexpr std::string_view kCandidateSchema = "QRE2G1CAND2";
constexpr std::string_view kCandidateManifestSchema = "QRE2G1CANDMAN2";
constexpr std::string_view kPivotSchema = "QRE2G1PIVOT1";
constexpr std::string_view kPivotManifestSchema = "QRE2G1PIVOTMAN1";
constexpr std::string_view kPriorSchema = "QRE2G1PRIOR2";
constexpr std::string_view kTeacherSchema = "QRE2G1TEACH2";
constexpr std::string_view kTeacherManifestSchema = "QRE2G1TEACHMAN2";
constexpr std::string_view kScheduleSchema = "QRE2G1SCHEDULE2";
constexpr std::string_view kCandidateReceiptSchema = "QRE2G1CANDRECEIPT2";
constexpr std::string_view kTeacherReceiptSchema = "QRE2G1TEACHRECEIPT2";
constexpr std::string_view kScheduleReceiptSchema = "QRE2G1SCHEDRECEIPT2";

struct CandidateManifestLine {
  std::int32_t d8 = 0;
  CandidateSessionStatus status = CandidateSessionStatus::NO_EVENTS;
  std::uint64_t rows = 0;
  std::uint64_t raw_events = 0;
  std::uint64_t two_sided_events = 0;
  std::uint64_t sane_events = 0;
  std::string candidate_file;
  std::string candidate_sha256;
  std::string event_pack_sha256;
  std::string receipt_file;
  std::string receipt_sha256;
};

struct PivotManifestLine {
  std::int32_t d8 = 0;
  std::uint64_t rows = 0;
  std::uint64_t candidates = 0;
  std::string pivot_file;
  std::string pivot_sha256;
};

struct TeacherManifestLine {
  std::int32_t d8 = 0;
  std::uint64_t rows = 0;
  std::uint64_t ready = 0;
  std::uint64_t refused = 0;
  std::string teacher_file;
  std::string teacher_sha256;
  std::string candidate_sha256;
  std::string event_pack_sha256;
  std::string receipt_file;
  std::string receipt_sha256;
};

struct EventAuthorityLine {
  std::int32_t d8 = 0;
  std::string status;
  std::int64_t locked_iid = -1;
  std::int64_t selection_basis_d8 = -1;
  std::int64_t open_utc = 0;
  std::int64_t close_utc = 0;
  std::string binary_file;
  std::string binary_sha256;
  std::string sidecar_file;
  std::string sidecar_sha256;
};

struct EventAuthority {
  std::map<std::int32_t, EventAuthorityLine> rows;
  std::string manifest_sha256;
};

struct CandidateAuthority {
  std::map<std::int32_t, CandidateManifestLine> rows;
  std::string manifest_sha256;
};

[[nodiscard]] const char* asset_name(qr::futsess::Asset asset) {
  return qr::futsess::asset_spec(asset).name;
}

[[nodiscard]] std::string window_tag(const Config& config) {
  return "start_d8=" + std::to_string(config.start_d8) +
         " end_d8_exclusive=" + std::to_string(config.end_d8_exclusive);
}

[[nodiscard]] Expected<std::monostate, Refusal> validate_config_window(
    const Config& config) {
  if (config.start_d8 < kDevelopmentStartD8 ||
      config.end_d8_exclusive > kDevelopmentEndD8Exclusive ||
      config.start_d8 >= config.end_d8_exclusive) {
    return refuse<std::monostate>(Refusal(
        RefusalCode::DAY_OUTSIDE_CALENDAR,
        "qr_entry_v2::g1_artifacts/window",
        "ordinary G1 artifacts are confined to [20210101,20250701)"));
  }
  return std::monostate{};
}

[[nodiscard]] Refusal io_refusal(const char* site, const char* detail) {
  return Refusal(RefusalCode::IO, site, detail);
}

[[nodiscard]] Refusal content_refusal(const char* site, const char* detail,
                                      std::int64_t context = 0) {
  return Refusal(RefusalCode::CONTENT_MISMATCH, site, detail, context);
}

[[nodiscard]] std::string hex_digest(const unsigned char* digest,
                                     unsigned int length) {
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
  if (EVP_Digest(bytes.data(), bytes.size(), digest.data(), &length,
                 EVP_sha256(), nullptr) != 1 || length != 32u) {
    return {};
  }
  return hex_digest(digest.data(), length);
}

[[nodiscard]] bool valid_sha256(std::string_view value) {
  return value.size() == 64u &&
         std::all_of(value.begin(), value.end(), [](char ch) {
           return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
         });
}

[[nodiscard]] Expected<std::string, Refusal> sha256_file(const fs::path& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    return refuse<std::string>(io_refusal(
        "qr_entry_v2::g1_artifacts/sha256_file", "cannot open artifact for hashing"));
  }
  EVP_MD_CTX* context = EVP_MD_CTX_new();
  if (context == nullptr || EVP_DigestInit_ex(context, EVP_sha256(), nullptr) != 1) {
    EVP_MD_CTX_free(context);
    return refuse<std::string>(io_refusal(
        "qr_entry_v2::g1_artifacts/sha256_file", "cannot initialize SHA-256"));
  }
  std::array<char, 1u << 20> buffer{};
  while (in) {
    in.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
    const std::streamsize got = in.gcount();
    if (got > 0 && EVP_DigestUpdate(context, buffer.data(),
                                    static_cast<std::size_t>(got)) != 1) {
      EVP_MD_CTX_free(context);
      return refuse<std::string>(io_refusal(
          "qr_entry_v2::g1_artifacts/sha256_file", "cannot update SHA-256"));
    }
  }
  if (!in.eof()) {
    EVP_MD_CTX_free(context);
    return refuse<std::string>(io_refusal(
        "qr_entry_v2::g1_artifacts/sha256_file", "cannot read artifact"));
  }
  std::array<unsigned char, EVP_MAX_MD_SIZE> digest{};
  unsigned int length = 0;
  const int finalized = EVP_DigestFinal_ex(context, digest.data(), &length);
  EVP_MD_CTX_free(context);
  if (finalized != 1 || length != 32u) {
    return refuse<std::string>(io_refusal(
        "qr_entry_v2::g1_artifacts/sha256_file", "cannot finalize SHA-256"));
  }
  return hex_digest(digest.data(), length);
}

[[nodiscard]] Expected<std::monostate, Refusal> write_atomic(
    const fs::path& path, std::string_view bytes) {
  std::error_code ec;
  fs::create_directories(path.parent_path(), ec);
  if (ec) {
    return refuse<std::monostate>(io_refusal(
        "qr_entry_v2::g1_artifacts/write_atomic", "cannot create artifact directory"));
  }
  const fs::path temporary = path.string() + ".tmp";
  std::FILE* file = std::fopen(temporary.c_str(), "wb");
  if (file == nullptr) {
    return refuse<std::monostate>(io_refusal(
        "qr_entry_v2::g1_artifacts/write_atomic", "cannot open temporary artifact"));
  }
  const std::size_t wrote = std::fwrite(bytes.data(), 1, bytes.size(), file);
  const int closed = std::fclose(file);
  if (wrote != bytes.size() || closed != 0) {
    fs::remove(temporary, ec);
    return refuse<std::monostate>(io_refusal(
        "qr_entry_v2::g1_artifacts/write_atomic", "short artifact write"));
  }
  fs::rename(temporary, path, ec);
  if (ec) {
    fs::remove(temporary, ec);
    return refuse<std::monostate>(io_refusal(
        "qr_entry_v2::g1_artifacts/write_atomic", "cannot publish artifact"));
  }
  return std::monostate{};
}

[[nodiscard]] Expected<std::string, Refusal> read_text(const fs::path& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    return refuse<std::string>(io_refusal(
        "qr_entry_v2::g1_artifacts/read_text", "cannot open required artifact"));
  }
  std::ostringstream out;
  out << in.rdbuf();
  if (!in.eof() && in.fail()) {
    return refuse<std::string>(io_refusal(
        "qr_entry_v2::g1_artifacts/read_text", "cannot read required artifact"));
  }
  return out.str();
}

[[nodiscard]] fs::path g1_root(const Config& config) {
  return fs::path(config.output_root) / "g1";
}

[[nodiscard]] fs::path event_manifest_path(const Config& config) {
  return fs::path(config.output_root) / "events" / asset_name(config.asset) /
         "manifest.tsv";
}

[[nodiscard]] fs::path candidate_path(const Config& config, std::int32_t d8) {
  return g1_root(config) / "candidates" / asset_name(config.asset) /
         (std::to_string(d8) + ".tsv");
}

[[nodiscard]] fs::path candidate_manifest_path(const Config& config) {
  return g1_root(config) / "candidates" / asset_name(config.asset) / "manifest.tsv";
}

[[nodiscard]] fs::path pivot_path(const Config& config, std::int32_t d8) {
  return g1_root(config) / "pivot" / asset_name(config.asset) /
         (std::to_string(d8) + ".tsv");
}

[[nodiscard]] fs::path pivot_manifest_path(const Config& config) {
  return g1_root(config) / "pivot" / asset_name(config.asset) / "manifest.tsv";
}

[[nodiscard]] fs::path prior_path(const Config& config) {
  return g1_root(config) / "priors" /
         (std::string(asset_name(config.asset)) + ".tsv");
}

[[nodiscard]] fs::path teacher_path(const Config& config, std::int32_t d8) {
  return g1_root(config) / "teacher" / asset_name(config.asset) /
         (std::to_string(d8) + ".tsv");
}

[[nodiscard]] fs::path teacher_manifest_path(const Config& config) {
  return g1_root(config) / "teacher" / asset_name(config.asset) / "manifest.tsv";
}

[[nodiscard]] fs::path session_receipt_path(const Config& config,
                                            std::int32_t d8,
                                            std::string_view stage) {
  return g1_root(config) / "receipts" / asset_name(config.asset) /
         (std::to_string(d8) + "." + std::string(stage) + ".json");
}

[[nodiscard]] fs::path aggregate_receipt_path(const Config& config,
                                              std::string_view stage) {
  return g1_root(config) / "receipts" /
         (std::string(asset_name(config.asset)) + "." + std::string(stage) + ".json");
}

[[nodiscard]] std::vector<std::string> split_tabs(std::string_view line) {
  std::vector<std::string> out;
  std::size_t start = 0;
  for (;;) {
    const std::size_t tab = line.find('\t', start);
    const std::size_t stop = tab == std::string_view::npos ? line.size() : tab;
    out.emplace_back(line.substr(start, stop - start));
    if (tab == std::string_view::npos) break;
    start = tab + 1u;
  }
  if (!out.empty() && !out.back().empty() && out.back().back() == '\r') {
    out.back().pop_back();
  }
  return out;
}

template <class T>
[[nodiscard]] bool parse_int(std::string_view text, T* out) {
  const char* first = text.data();
  const char* last = text.data() + text.size();
  const auto parsed = std::from_chars(first, last, *out);
  return parsed.ec == std::errc{} && parsed.ptr == last;
}

[[nodiscard]] bool parse_double(std::string_view text, double* out) {
  if (text == "NA") {
    *out = std::numeric_limits<double>::quiet_NaN();
    return true;
  }
  std::string copy(text);
  char* end = nullptr;
  *out = std::strtod(copy.c_str(), &end);
  return end == copy.c_str() + static_cast<std::ptrdiff_t>(copy.size()) &&
         std::isfinite(*out);
}

[[nodiscard]] std::string number_or_na(double value) {
  if (!std::isfinite(value)) return "NA";
  std::ostringstream out;
  out << std::setprecision(std::numeric_limits<double>::max_digits10) << value;
  return out.str();
}

[[nodiscard]] bool parse_candidate_status(std::string_view text,
                                          CandidateSessionStatus* out) {
  for (const CandidateSessionStatus value : {
           CandidateSessionStatus::READY, CandidateSessionStatus::NO_ATR14,
           CandidateSessionStatus::NO_LOCK, CandidateSessionStatus::NO_EVENTS,
           CandidateSessionStatus::NO_SANE_BBO}) {
    if (text == candidate_session_status_name(value)) {
      *out = value;
      return true;
    }
  }
  return false;
}

[[nodiscard]] Expected<EventAuthority, Refusal> read_event_authority(
    const Config& config) {
  auto text = read_text(event_manifest_path(config));
  if (!text) return refuse<EventAuthority>(text.error());
  EventAuthority authority;
  authority.manifest_sha256 = sha256_bytes(text.value());
  std::istringstream in(text.value());
  std::string line;
  const std::string schema = "# QRE2EVENTMAN2 " + window_tag(config);
  const std::string columns =
      "asset\td8\tstatus\tlocked_iid\tselection_basis_d8\topen_utc\tclose_utc"
      "\tevent_count\tmin_ts_recv_ns\tmax_ts_recv_ns\tmin_ts_event_ns"
      "\tmax_ts_event_ns\traw_records\ttrusted_economic_records"
      "\tsnapshot_records\tstandalone_bad_ts_recv_records\tmaybe_bad_book_records"
      "\tbinary_file\tbinary_sha256\tsidecar_file\tsidecar_sha256";
  if (!std::getline(in, line) || line != schema || !std::getline(in, line) ||
      line != columns) {
    return refuse<EventAuthority>(content_refusal(
        "qr_entry_v2::g1_artifacts/read_event_authority",
        "event manifest schema/window mismatch"));
  }
  while (std::getline(in, line)) {
    if (line.empty()) continue;
    const auto f = split_tabs(line);
    EventAuthorityLine row;
    if (f.size() != 21u || f[0] != asset_name(config.asset) ||
        !parse_int(f[1], &row.d8) || !parse_int(f[3], &row.locked_iid) ||
        !parse_int(f[4], &row.selection_basis_d8) ||
        !parse_int(f[5], &row.open_utc) || !parse_int(f[6], &row.close_utc) ||
        row.d8 < config.start_d8 || row.d8 >= config.end_d8_exclusive) {
      return refuse<EventAuthority>(content_refusal(
          "qr_entry_v2::g1_artifacts/read_event_authority", "invalid event authority row"));
    }
    row.status = f[2];
    row.binary_file = f[17];
    row.binary_sha256 = f[18];
    row.sidecar_file = f[19];
    row.sidecar_sha256 = f[20];
    const std::string expected_binary = std::string("events/") +
        asset_name(config.asset) + "/" + std::to_string(row.d8) + ".qre2";
    if (((row.status == "READY") !=
         (row.binary_file == expected_binary && valid_sha256(row.binary_sha256))) ||
        (row.status != "READY" &&
         (row.binary_file != "-" || row.binary_sha256 != "-")) ||
        row.sidecar_file != expected_binary + ".json" ||
        !valid_sha256(row.sidecar_sha256) ||
        !authority.rows.emplace(row.d8, row).second) {
      return refuse<EventAuthority>(content_refusal(
          "qr_entry_v2::g1_artifacts/read_event_authority",
          "event authority paths/hashes/status are inconsistent", row.d8));
    }
    auto sidecar = read_text(fs::path(config.output_root) / row.sidecar_file);
    if (!sidecar || sha256_bytes(sidecar.value()) != row.sidecar_sha256) {
      return refuse<EventAuthority>(content_refusal(
          "qr_entry_v2::g1_artifacts/read_event_authority",
          "event sidecar differs from pinned manifest", row.d8));
    }
  }
  return authority;
}

[[nodiscard]] Expected<CandidateAuthority, Refusal> read_candidate_authority(
    const Config& config) {
  auto text = read_text(candidate_manifest_path(config));
  if (!text) return refuse<CandidateAuthority>(text.error());
  CandidateAuthority authority;
  authority.manifest_sha256 = sha256_bytes(text.value());
  std::istringstream in(text.value());
  std::string line;
  const std::string schema = "# " + std::string(kCandidateManifestSchema) + " " +
                             window_tag(config);
  const std::string columns =
      "asset\td8\tstatus\trows\traw_events\ttwo_sided_events\tsane_events"
      "\tcandidate_file\tcandidate_sha256\tevent_pack_sha256"
      "\treceipt_file\treceipt_sha256";
  if (!std::getline(in, line) || line != schema || !std::getline(in, line) ||
      line != columns) {
    return refuse<CandidateAuthority>(content_refusal(
        "qr_entry_v2::g1_artifacts/read_candidate_authority",
        "candidate manifest schema/window mismatch"));
  }
  while (std::getline(in, line)) {
    if (line.empty()) continue;
    const auto f = split_tabs(line);
    CandidateManifestLine row;
    if (f.size() != 12u || f[0] != asset_name(config.asset) ||
        !parse_int(f[1], &row.d8) || !parse_candidate_status(f[2], &row.status) ||
        !parse_int(f[3], &row.rows) || !parse_int(f[4], &row.raw_events) ||
        !parse_int(f[5], &row.two_sided_events) || !parse_int(f[6], &row.sane_events)) {
      return refuse<CandidateAuthority>(content_refusal(
          "qr_entry_v2::g1_artifacts/read_candidate_authority",
          "invalid candidate manifest row"));
    }
    row.candidate_file = f[7];
    row.candidate_sha256 = f[8];
    row.event_pack_sha256 = f[9] == "ABSENT" ? "" : f[9];
    row.receipt_file = f[10];
    row.receipt_sha256 = f[11];
    const std::string expected_file = std::string("g1/candidates/") +
        asset_name(config.asset) + "/" + std::to_string(row.d8) + ".tsv";
    const std::string expected_receipt = std::string("g1/receipts/") +
        asset_name(config.asset) + "/" + std::to_string(row.d8) + ".candidates.json";
    if (row.candidate_file != expected_file || row.receipt_file != expected_receipt ||
        !valid_sha256(row.candidate_sha256) || !valid_sha256(row.receipt_sha256) ||
        (!row.event_pack_sha256.empty() && !valid_sha256(row.event_pack_sha256)) ||
        !authority.rows.emplace(row.d8, row).second) {
      return refuse<CandidateAuthority>(content_refusal(
          "qr_entry_v2::g1_artifacts/read_candidate_authority",
          "candidate manifest paths/hashes are inconsistent", row.d8));
    }
    auto receipt = read_text(fs::path(config.output_root) / row.receipt_file);
    if (!receipt || sha256_bytes(receipt.value()) != row.receipt_sha256) {
      return refuse<CandidateAuthority>(content_refusal(
          "qr_entry_v2::g1_artifacts/read_candidate_authority",
          "candidate receipt differs from pinned manifest", row.d8));
    }
  }
  return authority;
}

[[nodiscard]] std::string render_candidate_rows(
    const Config& config, std::int32_t d8,
    const std::vector<CandidateRow>& rows) {
  std::ostringstream out;
  out << "# " << kCandidateSchema << ' ' << window_tag(config) << " d8=" << d8 << '\n';
  out << "candidate_id\tasset\td8\tlocked_iid\tselection_basis_d8"
         "\tconfirmation_ts_recv_ns\tconfirmation_event_ordinal\tdecision_ts_ns"
         "\tdecision_sec\tside\tphase\trung_mask\tdelay\tphase_open_utc"
         "\tphase_close_utc\tevent_cutoff\tprefix_last_event_ordinal"
         "\tprefix_last_availability_ts_ns\tevent_pack_sha256\tprefix_sha256"
         "\tclock_law_receipt_sha256\tlineage_sha256"
         "\tentry_bid_px\tentry_ask_px\tentry_mid2\tentry_spread_usd"
         "\tfrozen_cost_usd\tatr14_prev_usd\tspread_prior_present"
         "\tspread_prior_usd\tsane_ceiling_usd\tcompliance_status"
         "\tcompliance_distance_sec\tcompliance_artifact_sha256\n";
  out << std::setprecision(std::numeric_limits<double>::max_digits10);
  for (const CandidateRow& row : rows) {
    out << row.candidate_id << '\t' << asset_name(row.asset) << '\t' << row.d8 << '\t'
        << row.locked_iid << '\t' << row.selection_basis_d8 << '\t'
        << row.confirmation_ts_recv_ns << '\t' << row.confirmation_event_ordinal << '\t'
        << row.decision_ts_ns << '\t' << row.decision_sec << '\t'
        << static_cast<int>(row.side) << '\t' << static_cast<unsigned>(row.phase) << '\t'
        << static_cast<unsigned>(row.rung_mask) << '\t' << candidate_delay_name(row.delay)
        << '\t' << row.phase_open_utc << '\t' << row.phase_close_utc << '\t'
        << row.event_cutoff << '\t' << row.prefix_last_event_ordinal << '\t'
        << row.prefix_last_availability_ts_ns << '\t' << row.event_pack_sha256 << '\t'
        << row.prefix_sha256 << '\t' << row.clock_law_receipt_sha256 << '\t'
        << row.lineage_sha256 << '\t' << row.entry_bid_px << '\t' << row.entry_ask_px
        << '\t' << row.entry_mid2 << '\t' << row.entry_spread_usd << '\t'
        << row.frozen_cost_usd << '\t' << row.atr14_prev_usd << '\t'
        << (row.spread_prior_present ? 1 : 0) << '\t'
        << number_or_na(row.spread_prior_usd) << '\t' << row.sane_ceiling_usd << '\t'
        << compliance_status_name(row.compliance) << '\t'
        << number_or_na(row.compliance_distance_sec) << '\t'
        << (row.compliance_artifact_sha256.empty() ? "ABSENT" :
            row.compliance_artifact_sha256) << '\n';
  }
  return out.str();
}

[[nodiscard]] Expected<std::string, Refusal> render_pivot_rows(
    const Config& config, std::int32_t d8,
    const std::vector<CandidateRow>& candidates,
    const std::vector<PivotRow>& pivots) {
  std::map<std::string, const CandidateRow*> by_id;
  std::size_t expected_rows = 0;
  for (const CandidateRow& candidate : candidates) {
    if (!by_id.emplace(candidate.candidate_id, &candidate).second) {
      return refuse<std::string>(content_refusal(
          "qr_entry_v2::g1_artifacts/render_pivot_rows",
          "candidate identity is duplicated"));
    }
    expected_rows += static_cast<std::size_t>(
        std::popcount(static_cast<unsigned>(candidate.rung_mask)));
  }
  std::set<std::pair<std::string, std::uint8_t>> keys;
  for (const PivotRow& pivot : pivots) {
    const auto candidate = by_id.find(pivot.candidate_id);
    if (candidate == by_id.end() || pivot.asset != config.asset ||
        pivot.d8 != d8 || pivot.side != candidate->second->side ||
        pivot.rung_index >= kG1RungCount ||
        (candidate->second->rung_mask &
         static_cast<std::uint8_t>(1u << pivot.rung_index)) == 0u ||
        !keys.emplace(pivot.candidate_id, pivot.rung_index).second) {
      return refuse<std::string>(content_refusal(
          "qr_entry_v2::g1_artifacts/render_pivot_rows",
          "pivot row differs from its candidate rung"));
    }
  }
  if (pivots.size() != expected_rows) {
    return refuse<std::string>(content_refusal(
        "qr_entry_v2::g1_artifacts/render_pivot_rows",
        "pivot row count differs from candidate rung masks"));
  }
  std::ostringstream out;
  out << "# " << kPivotSchema << ' ' << window_tag(config) << " d8=" << d8
      << '\n';
  out << "candidate_id\tasset\td8\trung_index\tside\tpivot_mid2"
         "\tpivot_ts_recv_ns\tpivot_ordinal\tleg_start_mid2"
         "\tleg_start_ts_recv_ns\tleg_start_ordinal\tconf_mid2"
         "\tthreshold_mid2_raw\n";
  for (const PivotRow& pivot : pivots) {
    out << pivot.candidate_id << '\t' << asset_name(pivot.asset) << '\t'
        << pivot.d8 << '\t' << static_cast<unsigned>(pivot.rung_index) << '\t'
        << static_cast<int>(pivot.side) << '\t' << pivot.pivot_mid2 << '\t'
        << pivot.pivot_ts_recv_ns << '\t' << pivot.pivot_ordinal << '\t'
        << pivot.leg_start_mid2 << '\t' << pivot.leg_start_ts_recv_ns << '\t'
        << pivot.leg_start_ordinal << '\t' << pivot.conf_mid2 << '\t'
        << pivot.threshold_mid2_raw << '\n';
  }
  return out.str();
}

[[nodiscard]] std::string render_prior_header(const Config& config) {
  std::ostringstream out;
  out << "# " << kPriorSchema << ' ' << window_tag(config) << '\n';
  out << "asset\td8\tatr14_present\tatr14_prev_usd";
  for (std::size_t p = 0; p < kG1PhaseCount; ++p) {
    out << "\tp" << p << "_spread_present\tp" << p << "_completed_sessions"
        << "\tp" << p << "_observations\tp" << p << "_median_spread_usd"
        << "\tp" << p << "_sane_ceiling_usd";
  }
  out << '\n';
  return out.str();
}

void append_prior_row(std::ostringstream* out, const Config& config,
                      const DayPriors& prior) {
  *out << std::setprecision(std::numeric_limits<double>::max_digits10)
       << asset_name(config.asset) << '\t' << prior.d8 << '\t'
       << (prior.atr14_present ? 1 : 0) << '\t'
       << number_or_na(prior.atr14_prev_usd);
  for (const PhaseSpreadPrior& phase : prior.phase) {
    *out << '\t' << (phase.present ? 1 : 0) << '\t' << phase.completed_sessions
         << '\t' << phase.observations << '\t'
         << number_or_na(phase.median_spread_usd) << '\t' << phase.sane_ceiling_usd;
  }
  *out << '\n';
}

[[nodiscard]] std::string render_teacher_rows(
    const Config& config, std::int32_t d8,
    const std::vector<TeacherRow>& rows) {
  std::ostringstream out;
  out << "# " << kTeacherSchema << ' ' << window_tag(config) << " d8=" << d8 << '\n';
  out << "candidate_id\tasset\td8\tdecision_ts_ns\texit_ts_ns\tphase_close_utc"
         "\tstatus\tcert_close_usd\tmfe_usd\tmae_usd\ttime_to_peak_sec"
         "\twall_hit\tpayer\ttake_target\tcompliance_status\n";
  out << std::setprecision(std::numeric_limits<double>::max_digits10);
  for (const TeacherRow& row : rows) {
    out << row.candidate_id << '\t' << asset_name(row.asset) << '\t' << row.d8 << '\t'
        << row.decision_ts_ns << '\t' << row.exit_ts_ns << '\t' << row.phase_close_utc
        << '\t' << teacher_status_name(row.status) << '\t' << row.cert_close_usd << '\t'
        << row.mfe_usd << '\t' << row.mae_usd << '\t' << row.time_to_peak_sec
        << '\t' << (row.wall_hit ? 1 : 0) << '\t' << (row.payer ? 1 : 0)
        << '\t' << (row.take_target ? 1 : 0) << '\t'
        << compliance_status_name(row.compliance) << '\n';
  }
  return out.str();
}

[[nodiscard]] Expected<std::vector<CandidateRow>, Refusal> read_candidate_rows(
    const Config& config, std::int32_t d8, std::string_view expected_sha256) {
  auto text = read_text(candidate_path(config, d8));
  if (!text) return refuse<std::vector<CandidateRow>>(text.error());
  if (!valid_sha256(expected_sha256) || sha256_bytes(text.value()) != expected_sha256) {
    return refuse<std::vector<CandidateRow>>(content_refusal(
        "qr_entry_v2::g1_artifacts/read_candidate_rows",
        "candidate bytes differ from pinned candidate manifest"));
  }
  std::istringstream in(text.value());
  std::string line;
  const std::string expected = "# " + std::string(kCandidateSchema) + " " +
                               window_tag(config) + " d8=" + std::to_string(d8);
  const std::string columns =
      "candidate_id\tasset\td8\tlocked_iid\tselection_basis_d8"
      "\tconfirmation_ts_recv_ns\tconfirmation_event_ordinal\tdecision_ts_ns"
      "\tdecision_sec\tside\tphase\trung_mask\tdelay\tphase_open_utc"
      "\tphase_close_utc\tevent_cutoff\tprefix_last_event_ordinal"
      "\tprefix_last_availability_ts_ns\tevent_pack_sha256\tprefix_sha256"
      "\tclock_law_receipt_sha256\tlineage_sha256\tentry_bid_px\tentry_ask_px"
      "\tentry_mid2\tentry_spread_usd\tfrozen_cost_usd\tatr14_prev_usd"
      "\tspread_prior_present\tspread_prior_usd\tsane_ceiling_usd"
      "\tcompliance_status\tcompliance_distance_sec\tcompliance_artifact_sha256";
  if (!std::getline(in, line) || line != expected || !std::getline(in, line) ||
      line != columns) {
    return refuse<std::vector<CandidateRow>>(content_refusal(
        "qr_entry_v2::g1_artifacts/read_candidate_rows", "candidate schema/window mismatch"));
  }
  std::vector<CandidateRow> rows;
  while (std::getline(in, line)) {
    if (line.empty()) continue;
    const std::vector<std::string> f = split_tabs(line);
    if (f.size() != 34u) {
      return refuse<std::vector<CandidateRow>>(content_refusal(
          "qr_entry_v2::g1_artifacts/read_candidate_rows", "candidate row width mismatch"));
    }
    CandidateRow row;
    row.candidate_id = f[0];
    std::int32_t row_d8 = 0;
    int side = 0;
    unsigned phase = 0;
    unsigned rung = 0;
    int spread_present = 0;
    if (f[1] != asset_name(config.asset) || !parse_int(f[2], &row_d8) || row_d8 != d8 ||
        !parse_int(f[3], &row.locked_iid) || !parse_int(f[4], &row.selection_basis_d8) ||
        !parse_int(f[5], &row.confirmation_ts_recv_ns) ||
        !parse_int(f[6], &row.confirmation_event_ordinal) ||
        !parse_int(f[7], &row.decision_ts_ns) || !parse_int(f[8], &row.decision_sec) ||
        !parse_int(f[9], &side) || !parse_int(f[10], &phase) ||
        !parse_int(f[11], &rung) || !parse_int(f[13], &row.phase_open_utc) ||
        !parse_int(f[14], &row.phase_close_utc) || !parse_int(f[15], &row.event_cutoff) ||
        !parse_int(f[16], &row.prefix_last_event_ordinal) ||
        !parse_int(f[17], &row.prefix_last_availability_ts_ns) ||
        !parse_int(f[22], &row.entry_bid_px) || !parse_int(f[23], &row.entry_ask_px) ||
        !parse_int(f[24], &row.entry_mid2) || !parse_double(f[25], &row.entry_spread_usd) ||
        !parse_double(f[26], &row.frozen_cost_usd) ||
        !parse_double(f[27], &row.atr14_prev_usd) ||
        !parse_int(f[28], &spread_present) || !parse_double(f[29], &row.spread_prior_usd) ||
        !parse_double(f[30], &row.sane_ceiling_usd) ||
        !parse_double(f[32], &row.compliance_distance_sec) ||
        (side != -1 && side != 1) || phase >= kG1PhaseCount || rung > 15u ||
        (spread_present != 0 && spread_present != 1)) {
      return refuse<std::vector<CandidateRow>>(content_refusal(
          "qr_entry_v2::g1_artifacts/read_candidate_rows", "invalid candidate field"));
    }
    if (f[12] == "STANDARD_120") {
      row.delay = CandidateDelay::STANDARD_120;
    } else if (f[12] == "FAST_OPEN_15") {
      row.delay = CandidateDelay::FAST_OPEN_15;
    } else {
      return refuse<std::vector<CandidateRow>>(content_refusal(
          "qr_entry_v2::g1_artifacts/read_candidate_rows", "unknown candidate delay"));
    }
    row.asset = config.asset;
    row.d8 = d8;
    row.side = static_cast<std::int8_t>(side);
    row.phase = static_cast<std::uint8_t>(phase);
    row.rung_mask = static_cast<std::uint8_t>(rung);
    row.event_pack_sha256 = f[18];
    row.prefix_sha256 = f[19];
    row.clock_law_receipt_sha256 = f[20];
    row.lineage_sha256 = f[21];
    row.spread_prior_present = spread_present != 0;
    if (f[31] == "CLEAR") {
      row.compliance = ComplianceStatus::CLEAR;
    } else if (f[31] == "PROHIBITED") {
      row.compliance = ComplianceStatus::PROHIBITED;
    } else if (f[31] == "COMPLIANCE_UNKNOWN") {
      row.compliance = ComplianceStatus::COMPLIANCE_UNKNOWN;
    } else {
      return refuse<std::vector<CandidateRow>>(content_refusal(
          "qr_entry_v2::g1_artifacts/read_candidate_rows", "unknown compliance status"));
    }
    row.compliance_artifact_sha256 = f[33] == "ABSENT" ? "" : f[33];
    if (row.candidate_id.empty() || !valid_sha256(row.event_pack_sha256) ||
        !valid_sha256(row.prefix_sha256) ||
        row.clock_law_receipt_sha256 != kClockLawReceiptSha256 ||
        !valid_sha256(row.lineage_sha256) ||
        (row.spread_prior_present != std::isfinite(row.spread_prior_usd)) ||
        (!row.compliance_artifact_sha256.empty() &&
         !valid_sha256(row.compliance_artifact_sha256)) ||
        row.candidate_id != g1_candidate_id(row) ||
        row.lineage_sha256 != g1_candidate_lineage(row)) {
      return refuse<std::vector<CandidateRow>>(content_refusal(
          "qr_entry_v2::g1_artifacts/read_candidate_rows", "candidate hash/mask mismatch"));
    }
    rows.push_back(std::move(row));
  }
  if (!std::is_sorted(rows.begin(), rows.end(), [](const CandidateRow& lhs,
                                                    const CandidateRow& rhs) {
        return std::tie(lhs.decision_ts_ns, lhs.confirmation_event_ordinal, lhs.side) <
               std::tie(rhs.decision_ts_ns, rhs.confirmation_event_ordinal, rhs.side);
      })) {
    return refuse<std::vector<CandidateRow>>(Refusal(
        RefusalCode::OUT_OF_ORDER, "qr_entry_v2::g1_artifacts/read_candidate_rows",
        "candidate artifact is not in identity order"));
  }
  return rows;
}

[[nodiscard]] Expected<std::map<std::int32_t, DayPriors>, Refusal> read_priors(
    const Config& config) {
  auto text = read_text(prior_path(config));
  if (!text) return refuse<std::map<std::int32_t, DayPriors>>(text.error());
  std::istringstream in(text.value());
  std::string line;
  const std::string expected = "# " + std::string(kPriorSchema) + " " + window_tag(config);
  if (!std::getline(in, line) || line != expected || !std::getline(in, line)) {
    return refuse<std::map<std::int32_t, DayPriors>>(content_refusal(
        "qr_entry_v2::g1_artifacts/read_priors", "prior schema/window mismatch"));
  }
  std::map<std::int32_t, DayPriors> out;
  while (std::getline(in, line)) {
    if (line.empty()) continue;
    const std::vector<std::string> f = split_tabs(line);
    if (f.size() != 19u) {
      return refuse<std::map<std::int32_t, DayPriors>>(content_refusal(
          "qr_entry_v2::g1_artifacts/read_priors", "prior row width mismatch"));
    }
    DayPriors row;
    int atr = 0;
    if (f[0] != asset_name(config.asset) || !parse_int(f[1], &row.d8) ||
        !parse_int(f[2], &atr) || !parse_double(f[3], &row.atr14_prev_usd) ||
        (atr != 0 && atr != 1)) {
      return refuse<std::map<std::int32_t, DayPriors>>(content_refusal(
          "qr_entry_v2::g1_artifacts/read_priors", "invalid ATR prior field"));
    }
    row.atr14_present = atr != 0;
    if (row.atr14_present != std::isfinite(row.atr14_prev_usd)) {
      return refuse<std::map<std::int32_t, DayPriors>>(content_refusal(
          "qr_entry_v2::g1_artifacts/read_priors", "ATR prior mask mismatch"));
    }
    for (std::size_t p = 0; p < kG1PhaseCount; ++p) {
      const std::size_t b = 4u + p * 5u;
      int present = 0;
      if (!parse_int(f[b], &present) ||
          !parse_int(f[b + 1u], &row.phase[p].completed_sessions) ||
          !parse_int(f[b + 2u], &row.phase[p].observations) ||
          !parse_double(f[b + 3u], &row.phase[p].median_spread_usd) ||
          !parse_double(f[b + 4u], &row.phase[p].sane_ceiling_usd) ||
          (present != 0 && present != 1)) {
        return refuse<std::map<std::int32_t, DayPriors>>(content_refusal(
            "qr_entry_v2::g1_artifacts/read_priors", "invalid phase prior field"));
      }
      row.phase[p].present = present != 0;
      if (row.phase[p].present != std::isfinite(row.phase[p].median_spread_usd)) {
        return refuse<std::map<std::int32_t, DayPriors>>(content_refusal(
            "qr_entry_v2::g1_artifacts/read_priors", "spread prior mask mismatch"));
      }
    }
    if (!out.emplace(row.d8, row).second) {
      return refuse<std::map<std::int32_t, DayPriors>>(content_refusal(
          "qr_entry_v2::g1_artifacts/read_priors", "duplicate prior day"));
    }
  }
  return out;
}

[[nodiscard]] Expected<std::vector<TeacherRow>, Refusal> read_teacher_rows(
    const Config& config, std::int32_t d8) {
  auto text = read_text(teacher_path(config, d8));
  if (!text) return refuse<std::vector<TeacherRow>>(text.error());
  std::istringstream in(text.value());
  std::string line;
  const std::string expected = "# " + std::string(kTeacherSchema) + " " +
                               window_tag(config) + " d8=" + std::to_string(d8);
  if (!std::getline(in, line) || line != expected || !std::getline(in, line)) {
    return refuse<std::vector<TeacherRow>>(content_refusal(
        "qr_entry_v2::g1_artifacts/read_teacher_rows", "teacher schema/window mismatch"));
  }
  std::vector<TeacherRow> rows;
  while (std::getline(in, line)) {
    if (line.empty()) continue;
    const std::vector<std::string> f = split_tabs(line);
    if (f.size() != 15u) {
      return refuse<std::vector<TeacherRow>>(content_refusal(
          "qr_entry_v2::g1_artifacts/read_teacher_rows", "teacher row width mismatch"));
    }
    TeacherRow row;
    int wall = 0;
    int payer = 0;
    int target = 0;
    if (f[1] != asset_name(config.asset) || !parse_int(f[2], &row.d8) || row.d8 != d8 ||
        !parse_int(f[3], &row.decision_ts_ns) || !parse_int(f[4], &row.exit_ts_ns) ||
        !parse_int(f[5], &row.phase_close_utc) ||
        !parse_double(f[7], &row.cert_close_usd) || !parse_double(f[8], &row.mfe_usd) ||
        !parse_double(f[9], &row.mae_usd) || !parse_double(f[10], &row.time_to_peak_sec) ||
        !parse_int(f[11], &wall) || !parse_int(f[12], &payer) ||
        !parse_int(f[13], &target)) {
      return refuse<std::vector<TeacherRow>>(content_refusal(
          "qr_entry_v2::g1_artifacts/read_teacher_rows", "invalid teacher field"));
    }
    if (f[6] == "READY") {
      row.status = TeacherStatus::READY;
    } else if (f[6] == "NO_SANE_SUFFIX") {
      row.status = TeacherStatus::NO_SANE_SUFFIX;
    } else {
      return refuse<std::vector<TeacherRow>>(content_refusal(
          "qr_entry_v2::g1_artifacts/read_teacher_rows", "unknown teacher status"));
    }
    row.candidate_id = f[0];
    row.asset = config.asset;
    row.wall_hit = wall != 0;
    row.payer = payer != 0;
    row.take_target = target != 0;
    if (f[14] == "CLEAR") {
      row.compliance = ComplianceStatus::CLEAR;
    } else if (f[14] == "PROHIBITED") {
      row.compliance = ComplianceStatus::PROHIBITED;
    } else if (f[14] == "COMPLIANCE_UNKNOWN") {
      row.compliance = ComplianceStatus::COMPLIANCE_UNKNOWN;
    } else {
      return refuse<std::vector<TeacherRow>>(content_refusal(
          "qr_entry_v2::g1_artifacts/read_teacher_rows", "unknown compliance status"));
    }
    rows.push_back(std::move(row));
  }
  return rows;
}

[[nodiscard]] std::map<std::int32_t, PhaseRow> phase_by_month(
    const std::vector<PhaseRow>& rows) {
  std::map<std::int32_t, PhaseRow> out;
  for (const PhaseRow& row : rows) out.emplace(row.month, row);
  return out;
}

[[nodiscard]] std::string relative_to_root(const Config& config,
                                           const fs::path& path) {
  std::error_code ec;
  const fs::path rel = fs::relative(path, config.output_root, ec);
  return ec ? path.string() : rel.string();
}

}  // namespace

Expected<ComplianceCalendar, Refusal> load_compliance_calendar(
    const std::string& path, const std::string& expected_sha256) {
  if (path.empty() || !valid_sha256(expected_sha256)) {
    return refuse<ComplianceCalendar>(Refusal(
        RefusalCode::CONFIG, "qr_entry_v2::load_compliance_calendar",
        "compliance path and expected lowercase SHA-256 are both required"));
  }
  auto actual = sha256_file(path);
  if (!actual) return refuse<ComplianceCalendar>(actual.error());
  if (actual.value() != expected_sha256) {
    return refuse<ComplianceCalendar>(content_refusal(
        "qr_entry_v2::load_compliance_calendar", "compliance artifact hash mismatch"));
  }
  auto text = read_text(path);
  if (!text) return refuse<ComplianceCalendar>(text.error());
  std::istringstream in(text.value());
  std::string line;
  if (!std::getline(in, line) || line != "# QRE2COMPLIANCE1" ||
      !std::getline(in, line) ||
      line != "kind\tinterval_id\tstart_ts_ns\tend_ts_ns\tavailability_ts_ns"
              "\tprovenance_sha256") {
    return refuse<ComplianceCalendar>(content_refusal(
        "qr_entry_v2::load_compliance_calendar", "compliance schema mismatch"));
  }
  ComplianceCalendar calendar;
  calendar.available = true;
  calendar.artifact_sha256 = actual.value();
  std::set<std::string> ids;
  while (std::getline(in, line)) {
    if (line.empty()) continue;
    const std::vector<std::string> f = split_tabs(line);
    if (f.size() != 6u) {
      return refuse<ComplianceCalendar>(content_refusal(
          "qr_entry_v2::load_compliance_calendar", "compliance row width mismatch"));
    }
    ComplianceInterval row;
    if (f[0] == "COVERAGE") {
      row.kind = ComplianceRowKind::COVERAGE;
    } else if (f[0] == "PROHIBITED") {
      row.kind = ComplianceRowKind::PROHIBITED;
    } else {
      return refuse<ComplianceCalendar>(content_refusal(
          "qr_entry_v2::load_compliance_calendar", "unknown compliance row kind"));
    }
    row.interval_id = f[1];
    row.provenance_sha256 = f[5];
    if (row.interval_id.empty() || !ids.insert(row.interval_id).second ||
        !parse_int(f[2], &row.start_ts_ns) || !parse_int(f[3], &row.end_ts_ns) ||
        !parse_int(f[4], &row.availability_ts_ns) ||
        row.start_ts_ns > row.end_ts_ns || row.availability_ts_ns == 0u ||
        !valid_sha256(row.provenance_sha256)) {
      return refuse<ComplianceCalendar>(content_refusal(
          "qr_entry_v2::load_compliance_calendar", "invalid compliance interval"));
    }
    if (row.kind == ComplianceRowKind::PROHIBITED &&
        row.end_ts_ns - row.start_ts_ns != 20u * 60u * 1'000'000'000ULL) {
      return refuse<ComplianceCalendar>(content_refusal(
          "qr_entry_v2::load_compliance_calendar",
          "D-077 prohibited interval must be exactly [-10,+10] minutes"));
    }
    calendar.rows.push_back(std::move(row));
  }
  if (calendar.rows.empty()) {
    return refuse<ComplianceCalendar>(content_refusal(
        "qr_entry_v2::load_compliance_calendar", "compliance artifact is empty"));
  }
  std::sort(calendar.rows.begin(), calendar.rows.end(),
            [](const ComplianceInterval& lhs, const ComplianceInterval& rhs) {
              return std::tie(lhs.start_ts_ns, lhs.end_ts_ns, lhs.kind, lhs.interval_id) <
                     std::tie(rhs.start_ts_ns, rhs.end_ts_ns, rhs.kind, rhs.interval_id);
            });
  return calendar;
}

namespace {

[[nodiscard]] std::string candidate_session_receipt(
    const Config& config, const CandidateSession& session,
    std::string_view output_sha, std::string_view event_sha,
    std::string_view locks_sha, std::string_view phases_sha,
    const ComplianceCalendar* compliance) {
  std::uint64_t clear = 0;
  std::uint64_t prohibited = 0;
  std::uint64_t unknown = 0;
  for (const CandidateRow& row : session.candidates) {
    if (row.compliance == ComplianceStatus::CLEAR) ++clear;
    if (row.compliance == ComplianceStatus::PROHIBITED) ++prohibited;
    if (row.compliance == ComplianceStatus::COMPLIANCE_UNKNOWN) ++unknown;
  }
  JsonWriter json;
  json.begin_object();
  json.key("schema");
  json.value_string(std::string(kCandidateReceiptSchema));
  json.key("asset");
  json.value_string(asset_name(config.asset));
  json.key("d8");
  json.value_int(session.priors.d8);
  json.key("start_d8");
  json.value_int(config.start_d8);
  json.key("end_d8_exclusive");
  json.value_int(config.end_d8_exclusive);
  json.key("status");
  json.value_string(candidate_session_status_name(session.status));
  json.key("rows");
  json.value_int(static_cast<std::int64_t>(session.candidates.size()));
  json.key("raw_events");
  json.value_int(static_cast<std::int64_t>(session.raw_events));
  json.key("two_sided_events");
  json.value_int(static_cast<std::int64_t>(session.two_sided_events));
  json.key("sane_events");
  json.value_int(static_cast<std::int64_t>(session.sane_events));
  json.key("confirmations");
  json.value_int(static_cast<std::int64_t>(session.confirmations));
  json.key("atr14_present");
  json.value_bool(session.priors.atr14_present);
  json.key("prior_commit_order");
  json.value_string("snapshot(d)_then_generate(d)_then_commit(d)");
  json.key("candidate_identity");
  json.value_string(
      "SHA256(asset,d8,decision,confirmation ordinal,side,event pack,prefix,clock receipt); rung bits unioned");
  json.key("cutoff_rule");
  json.value_string(
      "lower_bound(ts_recv_ns,decision_ts_ns); whole equal receive-time batch is future");
  json.key("cost_rule");
  json.value_string("strict-prefix decision spread + frozen $5 fee");
  json.key("compliance_rule");
  json.value_string("D-077 point-in-time coverage; [-10,+10]m prohibited; unknown not deployable");
  json.key("compliance_clear");
  json.value_int(static_cast<std::int64_t>(clear));
  json.key("compliance_prohibited");
  json.value_int(static_cast<std::int64_t>(prohibited));
  json.key("compliance_unknown");
  json.value_int(static_cast<std::int64_t>(unknown));
  json.key("source_hashes");
  json.begin_object();
  json.key("event_pack_sha256");
  event_sha.empty() ? json.value_null() : json.value_string(std::string(event_sha));
  json.key("locks_sha256");
  json.value_string(std::string(locks_sha));
  json.key("phase_schedule_sha256");
  json.value_string(std::string(phases_sha));
  json.key("compliance_artifact_sha256");
  if (compliance == nullptr || !compliance->available) {
    json.value_null();
  } else {
    json.value_string(compliance->artifact_sha256);
  }
  json.end_object();
  json.key("output_sha256");
  json.value_string(std::string(output_sha));
  json.key("holdout_start_d8");
  json.value_int(kDevelopmentEndD8Exclusive);
  json.key("final_exam_permit");
  json.value_bool(false);
  json.end_object();
  return json.text() + "\n";
}

[[nodiscard]] std::string teacher_session_receipt(
    const Config& config, std::int32_t d8, const std::vector<TeacherRow>& rows,
    std::string_view output_sha, std::string_view candidate_sha,
    std::string_view event_sha, std::string_view prior_sha,
    std::string_view phases_sha) {
  const std::uint64_t ready = static_cast<std::uint64_t>(std::count_if(
      rows.begin(), rows.end(), [](const TeacherRow& row) {
        return row.status == TeacherStatus::READY;
      }));
  JsonWriter json;
  json.begin_object();
  json.key("schema");
  json.value_string(std::string(kTeacherReceiptSchema));
  json.key("asset");
  json.value_string(asset_name(config.asset));
  json.key("d8");
  json.value_int(d8);
  json.key("start_d8");
  json.value_int(config.start_d8);
  json.key("end_d8_exclusive");
  json.value_int(config.end_d8_exclusive);
  json.key("rows");
  json.value_int(static_cast<std::int64_t>(rows.size()));
  json.key("ready");
  json.value_int(static_cast<std::int64_t>(ready));
  json.key("typed_no_sane_suffix");
  json.value_int(static_cast<std::int64_t>(rows.size() - ready));
  json.key("wall_rule");
  json.value_string("first exact net <= -$900; actual gap-through value retained");
  json.key("suffix_rule");
  json.value_string("begins at candidate lower_bound cutoff; last sane event <= scheduled phase close");
  json.key("target_rule");
  json.value_string("payer=(cert_close>0); take_target=(cert_close>=600); no occupancy/rank");
  json.key("source_hashes");
  json.begin_object();
  json.key("candidate_sha256");
  json.value_string(std::string(candidate_sha));
  json.key("event_pack_sha256");
  event_sha.empty() ? json.value_null() : json.value_string(std::string(event_sha));
  json.key("prior_schedule_sha256");
  json.value_string(std::string(prior_sha));
  json.key("phase_schedule_sha256");
  json.value_string(std::string(phases_sha));
  json.end_object();
  json.key("output_sha256");
  json.value_string(std::string(output_sha));
  json.key("holdout_start_d8");
  json.value_int(kDevelopmentEndD8Exclusive);
  json.key("final_exam_permit");
  json.value_bool(false);
  json.end_object();
  return json.text() + "\n";
}

[[nodiscard]] std::string render_candidate_manifest(
    const Config& config, const std::vector<CandidateManifestLine>& rows) {
  std::ostringstream out;
  out << "# " << kCandidateManifestSchema << ' ' << window_tag(config) << '\n';
  out << "asset\td8\tstatus\trows\traw_events\ttwo_sided_events\tsane_events"
         "\tcandidate_file\tcandidate_sha256\tevent_pack_sha256"
         "\treceipt_file\treceipt_sha256\n";
  for (const CandidateManifestLine& row : rows) {
    out << asset_name(config.asset) << '\t' << row.d8 << '\t'
        << candidate_session_status_name(row.status) << '\t' << row.rows << '\t'
        << row.raw_events << '\t' << row.two_sided_events << '\t' << row.sane_events
        << '\t' << row.candidate_file << '\t' << row.candidate_sha256 << '\t'
        << (row.event_pack_sha256.empty() ? "ABSENT" : row.event_pack_sha256)
        << '\t' << row.receipt_file << '\t' << row.receipt_sha256 << '\n';
  }
  return out.str();
}

[[nodiscard]] std::string render_pivot_manifest(
    const Config& config, const std::vector<PivotManifestLine>& rows) {
  std::ostringstream out;
  out << "# " << kPivotManifestSchema << ' ' << window_tag(config) << '\n';
  out << "asset\td8\trows\tcandidates\tpivot_file\tpivot_sha256\n";
  for (const PivotManifestLine& row : rows) {
    out << asset_name(config.asset) << '\t' << row.d8 << '\t' << row.rows
        << '\t' << row.candidates << '\t' << row.pivot_file << '\t'
        << row.pivot_sha256 << '\n';
  }
  return out.str();
}

[[nodiscard]] std::string render_teacher_manifest(
    const Config& config, const std::vector<TeacherManifestLine>& rows) {
  std::ostringstream out;
  out << "# " << kTeacherManifestSchema << ' ' << window_tag(config) << '\n';
  out << "asset\td8\trows\tready\trefused\tteacher_file\tteacher_sha256"
         "\tcandidate_sha256\tevent_pack_sha256\treceipt_file\treceipt_sha256\n";
  for (const TeacherManifestLine& row : rows) {
    out << asset_name(config.asset) << '\t' << row.d8 << '\t' << row.rows << '\t'
        << row.ready << '\t' << row.refused << '\t' << row.teacher_file << '\t'
        << row.teacher_sha256 << '\t' << row.candidate_sha256 << '\t'
        << (row.event_pack_sha256.empty() ? "ABSENT" : row.event_pack_sha256)
        << '\t' << row.receipt_file << '\t' << row.receipt_sha256 << '\n';
  }
  return out.str();
}

[[nodiscard]] std::string aggregate_receipt(
    const Config& config, std::string_view stage, std::string_view schema,
    const G1BuildStats& stats, std::string_view manifest_sha,
    std::string_view auxiliary_sha, std::string_view compliance_sha = {}) {
  JsonWriter json;
  json.begin_object();
  json.key("schema");
  json.value_string(std::string(schema));
  json.key("stage");
  json.value_string(std::string(stage));
  json.key("asset");
  json.value_string(asset_name(config.asset));
  json.key("start_d8");
  json.value_int(config.start_d8);
  json.key("end_d8_exclusive");
  json.value_int(config.end_d8_exclusive);
  json.key("sessions");
  json.value_int(static_cast<std::int64_t>(stats.sessions));
  json.key("no_candidate_sessions");
  json.value_int(static_cast<std::int64_t>(stats.no_candidate_sessions));
  json.key("candidates");
  json.value_int(static_cast<std::int64_t>(stats.candidates));
  json.key("pivot_rows");
  json.value_int(static_cast<std::int64_t>(stats.pivot_rows));
  json.key("teacher_ready");
  json.value_int(static_cast<std::int64_t>(stats.teacher_ready));
  json.key("teacher_refused");
  json.value_int(static_cast<std::int64_t>(stats.teacher_refused));
  json.key("manifest_sha256");
  json.value_string(std::string(manifest_sha));
  json.key("pivot_manifest_sha256");
  stats.pivot_manifest_sha256.empty()
      ? json.value_null()
      : json.value_string(stats.pivot_manifest_sha256);
  json.key("auxiliary_sha256");
  auxiliary_sha.empty() ? json.value_null() : json.value_string(std::string(auxiliary_sha));
  json.key("compliance_artifact_sha256");
  compliance_sha.empty() ? json.value_null() : json.value_string(std::string(compliance_sha));
  json.key("holdout_start_d8");
  json.value_int(kDevelopmentEndD8Exclusive);
  json.key("final_exam_permit");
  json.value_bool(false);
  json.end_object();
  return json.text() + "\n";
}

}  // namespace

Expected<G1BuildStats, Refusal> build_g1_candidate_artifacts(
    const Config& config, const ComplianceCalendar* compliance) {
  auto window = validate_config_window(config);
  if (!window) return refuse<G1BuildStats>(window.error());
  if (compliance != nullptr && compliance->available &&
      !valid_sha256(compliance->artifact_sha256)) {
    return refuse<G1BuildStats>(Refusal(
        RefusalCode::CONFIG, "qr_entry_v2::build_g1_candidate_artifacts",
        "compliance artifact is available but not hash-pinned"));
  }
  auto locks = read_locks(config);
  auto phases = read_phases(config);
  auto event_authority = read_event_authority(config);
  if (!locks) return refuse<G1BuildStats>(locks.error());
  if (!phases) return refuse<G1BuildStats>(phases.error());
  if (!event_authority) return refuse<G1BuildStats>(event_authority.error());
  if (event_authority.value().rows.size() != locks.value().size()) {
    return refuse<G1BuildStats>(content_refusal(
        "qr_entry_v2::build_g1_candidate_artifacts",
        "event manifest and lock denominator differ"));
  }
  const auto by_month = phase_by_month(phases.value());
  auto locks_sha = sha256_file(fs::path(config.output_root) / "locks" /
                               (std::string(asset_name(config.asset)) + ".tsv"));
  auto phases_sha = sha256_file(fs::path(config.output_root) / "phases" /
                                (std::string(asset_name(config.asset)) + ".tsv"));
  if (!locks_sha) return refuse<G1BuildStats>(locks_sha.error());
  if (!phases_sha) return refuse<G1BuildStats>(phases_sha.error());

  CausalPriorState prior_state(config.asset);
  std::ostringstream prior_text;
  prior_text << render_prior_header(config);
  std::vector<CandidateManifestLine> manifest;
  std::vector<PivotManifestLine> pivot_manifest;
  manifest.reserve(locks.value().size());
  pivot_manifest.reserve(locks.value().size());
  G1BuildStats stats;
  for (std::size_t ordinal = 0; ordinal < locks.value().size(); ++ordinal) {
    const LockRow& lock = locks.value()[ordinal];
    const auto event_it = event_authority.value().rows.find(lock.d8);
    if (event_it == event_authority.value().rows.end() ||
        event_it->second.locked_iid != lock.locked_iid ||
        event_it->second.selection_basis_d8 != lock.selection_basis_d8 ||
        event_it->second.open_utc != lock.open_utc ||
        event_it->second.close_utc != lock.close_utc ||
        (event_it->second.status == "READY" && lock.status != LockStatus::LOCKED)) {
      return refuse<G1BuildStats>(content_refusal(
          "qr_entry_v2::build_g1_candidate_artifacts",
          "event manifest differs from exact causal lock", lock.d8));
    }
    if (lock.d8 < config.start_d8 || lock.d8 >= config.end_d8_exclusive ||
        lock.d8 >= kDevelopmentEndD8Exclusive) {
      return refuse<G1BuildStats>(Refusal(
          RefusalCode::DAY_OUTSIDE_CALENDAR,
          "qr_entry_v2::build_g1_candidate_artifacts",
          "lock row escaped the development record window", lock.d8));
    }
    auto prior = prior_state.snapshot(lock.d8);
    if (!prior) return refuse<G1BuildStats>(prior.error());
    append_prior_row(&prior_text, config, prior.value());
    const auto phase = by_month.find(lock.d8 / 100);
    if (phase == by_month.end()) {
      return refuse<G1BuildStats>(content_refusal(
          "qr_entry_v2::build_g1_candidate_artifacts",
          "no causal monthly phase schedule", lock.d8));
    }

    CandidateSession session;
    session.priors = prior.value();
    session.completed.d8 = lock.d8;
    session.completed.locked_iid = lock.locked_iid;
    session.completed.session_ordinal = ordinal;
    std::string event_sha;
    if (lock.status != LockStatus::LOCKED) {
      session.status = CandidateSessionStatus::NO_LOCK;
    } else if (event_it->second.status != "READY") {
      session.status = CandidateSessionStatus::NO_EVENTS;
    } else {
      const fs::path event_path = fs::path(config.output_root) /
                                  event_it->second.binary_file;
      auto pack = read_event_pack(event_path.string(), event_it->second.binary_sha256);
      if (!pack) return refuse<G1BuildStats>(pack.error());
      auto generated = generate_g1_candidates(config.asset, lock, phase->second,
                                               pack.value(), prior.value(), ordinal);
      if (!generated) return refuse<G1BuildStats>(generated.error());
      session = std::move(generated).value();
      event_sha = pack.value().artifact_sha256;
    }
    auto applied = apply_candidate_compliance(compliance, &session.candidates);
    if (!applied) return refuse<G1BuildStats>(applied.error());

    const std::string candidate_text = render_candidate_rows(
        config, lock.d8, session.candidates);
    const fs::path output = candidate_path(config, lock.d8);
    auto wrote = write_atomic(output, candidate_text);
    if (!wrote) return refuse<G1BuildStats>(wrote.error());
    const std::string output_sha = sha256_bytes(candidate_text);
    auto pivot_text = render_pivot_rows(
        config, lock.d8, session.candidates, session.pivots);
    if (!pivot_text) return refuse<G1BuildStats>(pivot_text.error());
    const fs::path pivot_output = pivot_path(config, lock.d8);
    wrote = write_atomic(pivot_output, pivot_text.value());
    if (!wrote) return refuse<G1BuildStats>(wrote.error());
    const std::string pivot_sha = sha256_bytes(pivot_text.value());
    const std::string receipt_text = candidate_session_receipt(
        config, session, output_sha, event_sha, locks_sha.value(),
        phases_sha.value(), compliance);
    const fs::path receipt = session_receipt_path(config, lock.d8, "candidates");
    wrote = write_atomic(receipt, receipt_text);
    if (!wrote) return refuse<G1BuildStats>(wrote.error());

    CandidateManifestLine line;
    line.d8 = lock.d8;
    line.status = session.status;
    line.rows = session.candidates.size();
    line.raw_events = session.raw_events;
    line.two_sided_events = session.two_sided_events;
    line.sane_events = session.sane_events;
    line.candidate_file = relative_to_root(config, output);
    line.candidate_sha256 = output_sha;
    line.event_pack_sha256 = event_sha;
    line.receipt_file = relative_to_root(config, receipt);
    line.receipt_sha256 = sha256_bytes(receipt_text);
    manifest.push_back(std::move(line));
    pivot_manifest.push_back(PivotManifestLine{
        lock.d8, session.pivots.size(), session.candidates.size(),
        relative_to_root(config, pivot_output), pivot_sha});
    ++stats.sessions;
    stats.candidates += session.candidates.size();
    stats.pivot_rows += session.pivots.size();
    if (session.candidates.empty()) ++stats.no_candidate_sessions;
    auto committed = prior_state.commit(session.completed);
    if (!committed) return refuse<G1BuildStats>(committed.error());
  }

  auto wrote = write_atomic(prior_path(config), prior_text.str());
  if (!wrote) return refuse<G1BuildStats>(wrote.error());
  const std::string prior_sha = sha256_bytes(prior_text.str());
  const std::string manifest_text = render_candidate_manifest(config, manifest);
  wrote = write_atomic(candidate_manifest_path(config), manifest_text);
  if (!wrote) return refuse<G1BuildStats>(wrote.error());
  stats.manifest_sha256 = sha256_bytes(manifest_text);
  const std::string pivot_manifest_text =
      render_pivot_manifest(config, pivot_manifest);
  wrote = write_atomic(pivot_manifest_path(config), pivot_manifest_text);
  if (!wrote) return refuse<G1BuildStats>(wrote.error());
  stats.pivot_manifest_sha256 = sha256_bytes(pivot_manifest_text);
  const std::string receipt_text = aggregate_receipt(
      config, "candidates", kCandidateReceiptSchema, stats,
      stats.manifest_sha256,
      sha256_bytes(prior_sha + "\n" + event_authority.value().manifest_sha256 +
                   "\n" + stats.pivot_manifest_sha256),
      compliance != nullptr && compliance->available
          ? std::string_view(compliance->artifact_sha256)
          : std::string_view{});
  wrote = write_atomic(aggregate_receipt_path(config, "candidates"), receipt_text);
  if (!wrote) return refuse<G1BuildStats>(wrote.error());
  stats.receipt_sha256 = sha256_bytes(receipt_text);
  return stats;
}

Expected<G1BuildStats, Refusal> build_g1_teacher_artifacts(const Config& config) {
  auto window = validate_config_window(config);
  if (!window) return refuse<G1BuildStats>(window.error());
  auto locks = read_locks(config);
  auto phases = read_phases(config);
  auto priors = read_priors(config);
  auto candidate_authority = read_candidate_authority(config);
  auto event_authority = read_event_authority(config);
  if (!locks) return refuse<G1BuildStats>(locks.error());
  if (!phases) return refuse<G1BuildStats>(phases.error());
  if (!priors) return refuse<G1BuildStats>(priors.error());
  if (!candidate_authority) return refuse<G1BuildStats>(candidate_authority.error());
  if (!event_authority) return refuse<G1BuildStats>(event_authority.error());
  if (candidate_authority.value().rows.size() != locks.value().size() ||
      event_authority.value().rows.size() != locks.value().size()) {
    return refuse<G1BuildStats>(content_refusal(
        "qr_entry_v2::build_g1_teacher_artifacts",
        "candidate/event manifests and lock denominator differ"));
  }
  auto prior_sha = sha256_file(prior_path(config));
  auto phases_sha = sha256_file(fs::path(config.output_root) / "phases" /
                                (std::string(asset_name(config.asset)) + ".tsv"));
  if (!prior_sha) return refuse<G1BuildStats>(prior_sha.error());
  if (!phases_sha) return refuse<G1BuildStats>(phases_sha.error());
  const auto by_month = phase_by_month(phases.value());
  std::vector<TeacherManifestLine> manifest;
  G1BuildStats stats;
  for (const LockRow& lock : locks.value()) {
    const auto candidate_auth = candidate_authority.value().rows.find(lock.d8);
    const auto event_auth = event_authority.value().rows.find(lock.d8);
    if (candidate_auth == candidate_authority.value().rows.end() ||
        event_auth == event_authority.value().rows.end() ||
        candidate_auth->second.event_pack_sha256 !=
            (event_auth->second.status == "READY" ? event_auth->second.binary_sha256
                                                  : std::string{})) {
      return refuse<G1BuildStats>(content_refusal(
          "qr_entry_v2::build_g1_teacher_artifacts",
          "candidate manifest is not pinned to event manifest", lock.d8));
    }
    auto candidates = read_candidate_rows(config, lock.d8,
                                          candidate_auth->second.candidate_sha256);
    if (!candidates) return refuse<G1BuildStats>(candidates.error());
    if (candidates.value().size() != candidate_auth->second.rows) {
      return refuse<G1BuildStats>(content_refusal(
          "qr_entry_v2::build_g1_teacher_artifacts",
          "candidate row count differs from pinned manifest", lock.d8));
    }
    const auto prior = priors.value().find(lock.d8);
    const auto phase = by_month.find(lock.d8 / 100);
    if (prior == priors.value().end() || phase == by_month.end()) {
      return refuse<G1BuildStats>(content_refusal(
          "qr_entry_v2::build_g1_teacher_artifacts",
          "teacher cannot find exact candidate prior/phase", lock.d8));
    }
    const std::string& candidate_sha = candidate_auth->second.candidate_sha256;
    std::vector<TeacherRow> rows;
    std::string event_sha;
    if (!candidates.value().empty()) {
      if (event_auth->second.status != "READY") {
        return refuse<G1BuildStats>(io_refusal(
            "qr_entry_v2::build_g1_teacher_artifacts",
            "candidate session has no event pack"));
      }
      const fs::path event_path = fs::path(config.output_root) /
                                  event_auth->second.binary_file;
      auto pack = read_event_pack(event_path.string(), event_auth->second.binary_sha256);
      if (!pack) return refuse<G1BuildStats>(pack.error());
      auto certified = certify_teacher(config.asset, phase->second, pack.value(),
                                       prior->second, candidates.value());
      if (!certified) return refuse<G1BuildStats>(certified.error());
      rows = std::move(certified).value();
      event_sha = pack.value().artifact_sha256;
    }
    const std::string teacher_text = render_teacher_rows(config, lock.d8, rows);
    const fs::path output = teacher_path(config, lock.d8);
    auto wrote = write_atomic(output, teacher_text);
    if (!wrote) return refuse<G1BuildStats>(wrote.error());
    const std::string output_sha = sha256_bytes(teacher_text);
    const std::string receipt_text = teacher_session_receipt(
        config, lock.d8, rows, output_sha, candidate_sha, event_sha,
        prior_sha.value(), phases_sha.value());
    const fs::path receipt = session_receipt_path(config, lock.d8, "teacher");
    wrote = write_atomic(receipt, receipt_text);
    if (!wrote) return refuse<G1BuildStats>(wrote.error());

    TeacherManifestLine line;
    line.d8 = lock.d8;
    line.rows = rows.size();
    line.ready = static_cast<std::uint64_t>(std::count_if(
        rows.begin(), rows.end(), [](const TeacherRow& row) {
          return row.status == TeacherStatus::READY;
        }));
    line.refused = rows.size() - line.ready;
    line.teacher_file = relative_to_root(config, output);
    line.teacher_sha256 = output_sha;
    line.candidate_sha256 = candidate_sha;
    line.event_pack_sha256 = event_sha;
    line.receipt_file = relative_to_root(config, receipt);
    line.receipt_sha256 = sha256_bytes(receipt_text);
    manifest.push_back(std::move(line));
    ++stats.sessions;
    stats.candidates += rows.size();
    stats.teacher_ready += manifest.back().ready;
    stats.teacher_refused += manifest.back().refused;
  }
  const std::string manifest_text = render_teacher_manifest(config, manifest);
  auto wrote = write_atomic(teacher_manifest_path(config), manifest_text);
  if (!wrote) return refuse<G1BuildStats>(wrote.error());
  stats.manifest_sha256 = sha256_bytes(manifest_text);
  const std::string receipt_text = aggregate_receipt(
      config, "teacher", kTeacherReceiptSchema, stats, stats.manifest_sha256,
      sha256_bytes(candidate_authority.value().manifest_sha256 + "\n" +
                   event_authority.value().manifest_sha256));
  wrote = write_atomic(aggregate_receipt_path(config, "teacher"), receipt_text);
  if (!wrote) return refuse<G1BuildStats>(wrote.error());
  stats.receipt_sha256 = sha256_bytes(receipt_text);
  return stats;
}

namespace {

[[nodiscard]] std::string schedule_scope(const std::vector<Config>& configs) {
  if (configs.size() == 1u) return asset_name(configs.front().asset);
  return "PORTFOLIO";
}

[[nodiscard]] std::string render_schedule(
    const std::vector<TeacherRow>& teacher, const ScheduleResult& schedule,
    ScheduleUniverse universe, const std::vector<Config>& configs) {
  std::vector<const TeacherRow*> rows;
  rows.reserve(teacher.size());
  for (const TeacherRow& row : teacher) rows.push_back(&row);
  std::sort(rows.begin(), rows.end(), [](const TeacherRow* lhs, const TeacherRow* rhs) {
    return std::tie(lhs->d8, lhs->decision_ts_ns, lhs->asset, lhs->candidate_id) <
           std::tie(rhs->d8, rhs->decision_ts_ns, rhs->asset, rhs->candidate_id);
  });
  std::ostringstream out;
  out << "# " << kScheduleSchema << " scope=" << schedule_scope(configs)
      << " law=" << schedule.law << " universe="
      << (universe == ScheduleUniverse::DEPLOYABLE_CLEAR_ONLY ? "DEPLOYABLE_CLEAR_ONLY"
                                                               : "MECHANICAL_ALL")
      << '\n';
  out << "candidate_id\tasset\td8\tdecision_ts_ns\texit_ts_ns\tcert_close_usd"
         "\tcompliance_status\tselected\n";
  out << std::setprecision(std::numeric_limits<double>::max_digits10);
  for (const TeacherRow* row : rows) {
    out << row->candidate_id << '\t' << asset_name(row->asset) << '\t' << row->d8
        << '\t' << row->decision_ts_ns << '\t' << row->exit_ts_ns << '\t'
        << row->cert_close_usd << '\t' << compliance_status_name(row->compliance)
        << '\t' << (schedule.selected.at(row->candidate_id) ? 1 : 0) << '\n';
  }
  return out.str();
}

[[nodiscard]] std::string schedule_receipt(
    const std::vector<Config>& configs, const ScheduleResult& schedule,
    ScheduleUniverse universe, const ArrivalThresholds* thresholds,
    const std::map<qr::futsess::Asset, std::string>& teacher_manifest_hashes,
    std::string_view output_sha) {
  JsonWriter json;
  json.begin_object();
  json.key("schema");
  json.value_string(std::string(kScheduleReceiptSchema));
  json.key("scope");
  json.value_string(schedule_scope(configs));
  json.key("law");
  json.value_string(schedule.law);
  json.key("universe");
  json.value_string(universe == ScheduleUniverse::DEPLOYABLE_CLEAR_ONLY
                        ? "DEPLOYABLE_CLEAR_ONLY"
                        : "MECHANICAL_ALL");
  json.key("occupancy_rule");
  json.value_string("next decision_ts_ns > prior exit_ts_ns");
  json.key("max_entries_per_asset_day");
  json.value_int(kMaxEntriesPerAssetDay);
  json.key("max_entries_per_portfolio_day");
  json.value_int(kMaxEntriesPerPortfolioDay);
  json.key("selected_count");
  json.value_int(static_cast<std::int64_t>(schedule.selected_count));
  json.key("total_usd");
  json.value_double(schedule.total_usd);
  json.key("expected_sessions");
  json.value_int(static_cast<std::int64_t>(schedule.expected_sessions));
  json.key("zero_sessions");
  json.value_int(static_cast<std::int64_t>(schedule.zero_sessions));
  json.key("usd_per_session");
  json.value_double(schedule.usd_per_session);
  json.key("teacher_manifest_sha256");
  json.begin_object();
  for (const auto& [asset, hash] : teacher_manifest_hashes) {
    json.key(asset_name(asset));
    json.value_string(hash);
  }
  json.end_object();
  json.key("inner_thresholds_usd");
  if (thresholds == nullptr) {
    json.value_null();
  } else {
    json.begin_object();
    for (const auto& [asset, value] : thresholds->min_value_usd) {
      json.key(asset_name(asset));
      json.value_double(value);
    }
    json.end_object();
  }
  json.key("inner_threshold_receipt_sha256");
  if (thresholds == nullptr) {
    json.value_null();
  } else {
    json.value_string(thresholds->threshold_receipt_sha256);
  }
  json.key("output_sha256");
  json.value_string(std::string(output_sha));
  json.key("holdout_start_d8");
  json.value_int(kDevelopmentEndD8Exclusive);
  json.key("final_exam_permit");
  json.value_bool(false);
  json.end_object();
  return json.text() + "\n";
}

}  // namespace

Expected<G1BuildStats, Refusal> build_g1_schedule_artifact(
    const std::vector<Config>& configs, bool arrival, ScheduleUniverse universe,
    const ArrivalThresholds* thresholds) {
  if (configs.empty()) {
    return refuse<G1BuildStats>(Refusal(
        RefusalCode::CONFIG, "qr_entry_v2::build_g1_schedule_artifact",
        "at least one asset config is required"));
  }
  std::set<qr::futsess::Asset> assets;
  for (const Config& config : configs) {
    auto window = validate_config_window(config);
    if (!window) return refuse<G1BuildStats>(window.error());
    if (config.output_root != configs.front().output_root ||
        config.start_d8 != configs.front().start_d8 ||
        config.end_d8_exclusive != configs.front().end_d8_exclusive ||
        !assets.insert(config.asset).second) {
      return refuse<G1BuildStats>(Refusal(
          RefusalCode::CONFIG, "qr_entry_v2::build_g1_schedule_artifact",
          "schedule configs must have one root/window and unique assets"));
    }
  }
  if (arrival && universe != ScheduleUniverse::DEPLOYABLE_CLEAR_ONLY) {
    return refuse<G1BuildStats>(Refusal(
        RefusalCode::CONFIG, "qr_entry_v2::build_g1_schedule_artifact",
        "chronological arrival is deployable-clear only"));
  }
  std::vector<TeacherRow> teacher;
  std::vector<ExpectedSession> expected;
  std::map<qr::futsess::Asset, std::string> teacher_manifest_hashes;
  for (const Config& config : configs) {
    auto manifest_hash = sha256_file(teacher_manifest_path(config));
    if (!manifest_hash) return refuse<G1BuildStats>(manifest_hash.error());
    teacher_manifest_hashes.emplace(config.asset, manifest_hash.value());
    auto locks = read_locks(config);
    if (!locks) return refuse<G1BuildStats>(locks.error());
    for (const LockRow& lock : locks.value()) {
      // Exact opportunity denominator: a session without a causally selected
      // outright could never admit an entry.  Keep reading its typed-empty
      // teacher file for manifest integrity, but do not call it an opportunity.
      if (lock.status == LockStatus::LOCKED) {
        expected.push_back(ExpectedSession{config.asset, lock.d8});
      }
      auto rows = read_teacher_rows(config, lock.d8);
      if (!rows) return refuse<G1BuildStats>(rows.error());
      teacher.insert(teacher.end(), rows.value().begin(), rows.value().end());
    }
  }
  Expected<ScheduleResult, Refusal> scheduled = arrival
      ? (thresholds == nullptr
             ? refuse<ScheduleResult>(Refusal(
                   RefusalCode::CONFIG, "qr_entry_v2::build_g1_schedule_artifact",
                   "arrival schedule requires inner-frozen thresholds"))
             : chronological_truth_arrival(teacher, expected, *thresholds))
      : exact_schedule_ceiling(teacher, expected, universe);
  if (!scheduled) return refuse<G1BuildStats>(scheduled.error());
  const std::string text = render_schedule(teacher, scheduled.value(), universe, configs);
  const std::string kind = arrival
                               ? "arrival"
                               : (universe == ScheduleUniverse::DEPLOYABLE_CLEAR_ONLY
                                      ? "deployable_ceiling"
                                      : "mechanical_ceiling");
  const fs::path output = g1_root(configs.front()) / "schedules" /
                          (schedule_scope(configs) + "." + kind + ".tsv");
  auto wrote = write_atomic(output, text);
  if (!wrote) return refuse<G1BuildStats>(wrote.error());
  const std::string output_sha = sha256_bytes(text);
  const std::string receipt_text = schedule_receipt(
      configs, scheduled.value(), universe, thresholds,
      teacher_manifest_hashes, output_sha);
  const fs::path receipt = g1_root(configs.front()) / "receipts" /
                           (schedule_scope(configs) + "." + kind + ".json");
  wrote = write_atomic(receipt, receipt_text);
  if (!wrote) return refuse<G1BuildStats>(wrote.error());
  G1BuildStats stats;
  stats.sessions = expected.size();
  stats.candidates = teacher.size();
  stats.teacher_ready = scheduled.value().selected_count;
  stats.manifest_sha256 = output_sha;
  stats.receipt_sha256 = sha256_bytes(receipt_text);
  return stats;
}

}  // namespace qr::entry_v2
