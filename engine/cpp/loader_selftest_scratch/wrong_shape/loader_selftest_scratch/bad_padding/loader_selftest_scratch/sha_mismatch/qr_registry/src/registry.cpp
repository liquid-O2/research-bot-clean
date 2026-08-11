#include "qr_registry/registry.hpp"

#include <openssl/evp.h>

#include <array>
#include <charconv>
#include <cstdio>
#include <fstream>
#include <ios>
#include <iterator>
#include <sstream>
#include <system_error>
#include <utility>
#include <vector>

#include "qr_core/checked.hpp"

namespace qr {
namespace registry_blob {
extern const char kRegistryTsv[];
extern const std::size_t kRegistryTsvSize;
}  // namespace registry_blob

namespace {

constexpr const char* kSite = "qr_registry::Registry";

constexpr Refusal malformed(const char* detail, std::int64_t context = 0) noexcept {
  return Refusal(RefusalCode::REGISTRY_MALFORMED, kSite, detail, context);
}

/// Splits one TSV line into exactly kRegistryColumns fields, or refuses.
bool split_columns(std::string_view line, std::array<std::string_view, kRegistryColumns>& out) {
  std::size_t count = 0;
  std::size_t start = 0;
  while (true) {
    const std::size_t tab = line.find('\t', start);
    if (count >= kRegistryColumns) {
      return false;  // too many columns
    }
    if (tab == std::string_view::npos) {
      out[count] = line.substr(start);
      ++count;
      break;
    }
    out[count] = line.substr(start, tab - start);
    ++count;
    start = tab + 1;
  }
  return count == kRegistryColumns;
}

/// Strict base-10 int64 parse: the whole field must be consumed and no sign
/// decoration or whitespace is tolerated.
bool parse_i64(std::string_view field, std::int64_t& out) {
  if (field.empty()) {
    return false;
  }
  const char* begin = field.data();
  const char* end = begin + field.size();
  const std::from_chars_result result = std::from_chars(begin, end, out, 10);
  return result.ec == std::errc() && result.ptr == end;
}

bool is_lowercase_hex64(std::string_view field) {
  if (field.size() != 64) {
    return false;
  }
  for (const char c : field) {
    const bool digit = c >= '0' && c <= '9';
    const bool lower = c >= 'a' && c <= 'f';
    if (!digit && !lower) {
      return false;
    }
  }
  return true;
}

Expected<Session, Refusal> parse_row(std::string_view line, std::int64_t row_index) {
  std::array<std::string_view, kRegistryColumns> fields{};
  if (!split_columns(line, fields)) {
    return Expected<Session, Refusal>::refuse(
        malformed("registry row does not have exactly 16 columns", row_index));
  }

  const auto civil = CivilDate::parse_ymd(fields[0]);
  if (!civil.has_value()) {
    return Expected<Session, Refusal>::refuse(
        malformed("registry row day is not a canonical civil date", row_index));
  }

  std::int64_t session_start_ns = 0;
  std::int64_t session_end_ns = 0;
  std::int64_t expected_bar_count = 0;
  std::int64_t source_size_bytes = 0;
  std::int64_t raw_rth_row_count = 0;
  std::int64_t complete_group_count = 0;
  if (!parse_i64(fields[1], session_start_ns)) {
    return Expected<Session, Refusal>::refuse(malformed("bad session_start_ns", row_index));
  }
  if (!parse_i64(fields[2], session_end_ns)) {
    return Expected<Session, Refusal>::refuse(malformed("bad session_end_ns", row_index));
  }
  if (!parse_i64(fields[3], expected_bar_count) || expected_bar_count <= 0 ||
      expected_bar_count > 0xFFFF) {
    return Expected<Session, Refusal>::refuse(malformed("bad expected_bar_count", row_index));
  }
  if (fields[4].empty()) {
    return Expected<Session, Refusal>::refuse(malformed("empty source_relative_path", row_index));
  }
  if (!is_lowercase_hex64(fields[6])) {
    return Expected<Session, Refusal>::refuse(malformed("bad source_sha256", row_index));
  }
  if (!parse_i64(fields[7], source_size_bytes) || source_size_bytes <= 0) {
    return Expected<Session, Refusal>::refuse(malformed("bad source_size_bytes", row_index));
  }
  SourceProfile profile{};
  if (fields[8] == "cent_int32") {
    profile = SourceProfile::CentInt32;
  } else if (fields[8] == "dollar_float64") {
    profile = SourceProfile::DollarFloat64;
  } else {
    return Expected<Session, Refusal>::refuse(malformed("unknown source_profile", row_index));
  }
  if (!parse_i64(fields[9], raw_rth_row_count) || raw_rth_row_count < 0) {
    return Expected<Session, Refusal>::refuse(malformed("bad raw_rth_row_count", row_index));
  }
  if (!parse_i64(fields[10], complete_group_count) || complete_group_count < 0) {
    return Expected<Session, Refusal>::refuse(malformed("bad complete_group_count", row_index));
  }

  // registry.rs:104-108: session bounds must agree with expected_bar_count.
  const auto span = checked_sub(session_end_ns, session_start_ns);
  if (!span.has_value()) {
    return Expected<Session, Refusal>::refuse(malformed("session span overflowed", row_index));
  }
  const auto declared = checked_mul(expected_bar_count, kBarNs);
  if (!declared.has_value()) {
    return Expected<Session, Refusal>::refuse(malformed("bar span overflowed", row_index));
  }
  if (span.value() != declared.value()) {
    return Expected<Session, Refusal>::refuse(
        malformed("session bounds disagree with expected_bar_count", row_index));
  }

  return Session{
      std::string(fields[0]),
      civil.value(),
      session_start_ns,
      session_end_ns,
      expected_bar_count,
      std::string(fields[4]),
      std::string(fields[6]),
      source_size_bytes,
      profile,
      raw_rth_row_count,
      complete_group_count,
  };
}

}  // namespace

const char* source_profile_name(SourceProfile profile) noexcept {
  switch (profile) {
    case SourceProfile::CentInt32:
      return "cent_int32";
    case SourceProfile::DollarFloat64:
      return "dollar_float64";
  }
  return "unknown_profile";
}

std::string sha256_hex(std::string_view bytes) {
  std::array<unsigned char, EVP_MAX_MD_SIZE> digest{};
  unsigned int digest_len = 0;
  if (EVP_Digest(bytes.data(), bytes.size(), digest.data(), &digest_len, EVP_sha256(), nullptr) !=
      1) {
    detail::fail_fast("OpenSSL EVP_Digest(sha256) failed");
  }
  static constexpr char kHex[] = "0123456789abcdef";
  std::string out;
  out.reserve(static_cast<std::size_t>(digest_len) * 2);
  for (unsigned int i = 0; i < digest_len; ++i) {
    out.push_back(kHex[digest[i] >> 4]);
    out.push_back(kHex[digest[i] & 0x0F]);
  }
  return out;
}

std::string_view embedded_registry_text() noexcept {
  return std::string_view(registry_blob::kRegistryTsv, registry_blob::kRegistryTsvSize);
}

Expected<Registry, Refusal> Registry::parse_without_digest_gate(std::string_view tsv) {
  std::size_t cursor = 0;
  const auto next_line = [&tsv, &cursor](std::string_view& line) -> bool {
    if (cursor >= tsv.size()) {
      return false;
    }
    const std::size_t newline = tsv.find('\n', cursor);
    if (newline == std::string_view::npos) {
      line = tsv.substr(cursor);
      cursor = tsv.size();
    } else {
      line = tsv.substr(cursor, newline - cursor);
      cursor = newline + 1;
    }
    return true;
  };

  std::string_view header;
  if (!next_line(header)) {
    return Expected<Registry, Refusal>::refuse(malformed("registry text is empty"));
  }
  if (header != kRegistryHeader) {
    return Expected<Registry, Refusal>::refuse(
        malformed("registry header drifted from the frozen schema"));
  }

  std::vector<Session> sessions;
  sessions.reserve(kRegistrySessionCount);
  std::string_view line;
  std::int64_t row_index = 0;
  while (next_line(line)) {
    if (line.empty()) {
      return Expected<Registry, Refusal>::refuse(malformed("blank registry row", row_index));
    }
    auto session = parse_row(line, row_index);
    if (!session.has_value()) {
      return Expected<Registry, Refusal>::refuse(session.error());
    }
    if (!sessions.empty() && !(sessions.back().day < session.value().day)) {
      return Expected<Registry, Refusal>::refuse(
          malformed("registry days are not strictly sorted", row_index));
    }
    sessions.push_back(std::move(session).value());
    ++row_index;
  }

  if (sessions.size() != kRegistrySessionCount) {
    return Expected<Registry, Refusal>::refuse(
        malformed("registry does not carry exactly 1,003 sessions",
                  static_cast<std::int64_t>(sessions.size())));
  }

  RegistryReceipt receipt{std::string(), sessions.size()};
  return Registry(std::move(sessions), std::move(receipt));
}

Expected<Registry, Refusal> Registry::load_from_text(std::string_view tsv) {
  // GATE FIRST: the digest decides whether the bytes may be parsed at all.
  const std::string digest = sha256_hex(tsv);
  if (digest != kExpectedRegistrySha256) {
    return Expected<Registry, Refusal>::refuse(
        Refusal(RefusalCode::REGISTRY_DIGEST_MISMATCH, kSite,
                "registry text does not hash to the pinned EXPECTED_REGISTRY_SHA256",
                static_cast<std::int64_t>(tsv.size())));
  }
  auto parsed = parse_without_digest_gate(tsv);
  if (!parsed.has_value()) {
    return parsed;
  }
  Registry registry = std::move(parsed).value();
  registry.receipt_.sha256 = digest;
  return registry;
}

Expected<Registry, Refusal> Registry::load_embedded() {
  return load_from_text(embedded_registry_text());
}

Expected<Registry, Refusal> Registry::load_from_file(const std::filesystem::path& path) {
  std::ifstream stream(path, std::ios::binary);
  if (!stream) {
    return Expected<Registry, Refusal>::refuse(
        Refusal(RefusalCode::IO, kSite, "registry file could not be opened"));
  }
  std::ostringstream buffer;
  buffer << stream.rdbuf();
  if (!stream.good() && !stream.eof()) {
    return Expected<Registry, Refusal>::refuse(
        Refusal(RefusalCode::IO, kSite, "registry file could not be read"));
  }
  const std::string text = buffer.str();
  return load_from_text(text);
}

Expected<const Session*, Refusal> Registry::session_at(std::int64_t ordinal) const noexcept {
  if (ordinal < 0 || static_cast<std::size_t>(ordinal) >= sessions_.size()) {
    return Expected<const Session*, Refusal>::refuse(
        Refusal(RefusalCode::DAY_OUTSIDE_CALENDAR, kSite,
                "ordinal past the 1,003-session calendar", ordinal));
  }
  return &sessions_[static_cast<std::size_t>(ordinal)];
}

Expected<std::int64_t, Refusal> Registry::ordinal_of_day(std::string_view day) const noexcept {
  std::size_t low = 0;
  std::size_t high = sessions_.size();
  while (low < high) {
    const std::size_t mid = low + (high - low) / 2;
    const std::string_view candidate = sessions_[mid].day;
    if (candidate < day) {
      low = mid + 1;
    } else if (candidate > day) {
      high = mid;
    } else {
      return static_cast<std::int64_t>(mid);
    }
  }
  return Expected<std::int64_t, Refusal>::refuse(
      Refusal(RefusalCode::UNKNOWN_SESSION, kSite, "civil day has no row in the frozen registry"));
}

}  // namespace qr
