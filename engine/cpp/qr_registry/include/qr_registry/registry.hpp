// qr_registry/registry.hpp - the frozen 1,003-session accepted-session registry.
//
// SPEC: design/DESIGN_SUBSTRATE.md section 6 -
//   "`qr_registry` (TSV + per-file sha gate + 125..917 wall before path
//    formation)"
// Reference port (read-only): /workspace/engine/crates/corpus/src/registry.rs
// (parse + EXPECTED_REGISTRY_SHA256 gate) and .../corpus/src/error.rs
// (refusal taxonomy).
//
// The registry text is EMBEDDED in the binary (generated at configure time
// from engine/crates/corpus/registry/accepted_compact_sessions.tsv) exactly as
// the Rust build embeds it with include_str!, so authentication and session
// lookup never depend on where the binary happens to run.
//
// WHAT IS VERIFIED HERE: the registry file's OWN sha256 against the pinned
// digest. The per-session payload parquet digests (source_sha256) are NOT
// verified in WP1 - that is the lazy per-session check at read time in a later
// work package. Each session's recorded digest and size are carried through so
// that check has its authority.
#ifndef QR_REGISTRY_REGISTRY_HPP
#define QR_REGISTRY_REGISTRY_HPP

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

#include "qr_core/frames.hpp"
#include "qr_core/refusal.hpp"

namespace qr {

/// Pinned sha256 of accepted_compact_sessions.tsv, ported verbatim from
/// corpus::registry::EXPECTED_REGISTRY_SHA256 (registry.rs:26-27). Also the
/// `corpus_registry_1003` row of authorities/REGISTRY.tsv.
inline constexpr std::string_view kExpectedRegistrySha256 =
    "233dc10ab4c0973a8caa92792757a322bbff102296f0e7ffb71c6d78810bcaed";

/// The frozen 16-column header, ported verbatim from registry.rs:31-36.
inline constexpr std::string_view kRegistryHeader =
    "day\tsession_start_ns\tsession_end_ns\texpected_bar_count\tsource_relative_path\t"
    "official_binding_id\tsource_sha256\tsource_size_bytes\tsource_profile\t"
    "raw_rth_row_count\tcomplete_group_count\tsource_parent_id\tcoverage_authority_id\t"
    "dependency_code_root\taccepted_day_summary_id\taccepted_day_summary_blob_sha256";

inline constexpr std::size_t kRegistryColumns = 16;
inline constexpr std::size_t kRegistrySessionCount = 1003;
inline constexpr std::int64_t kBarNs = 60'000'000'000;

/// Raw tick price encoding of one session's source parquet (registry.rs:41-46).
enum class SourceProfile : std::uint8_t {
  /// bid/ask are Int32 integer cents.
  CentInt32 = 0,
  /// bid/ask are Float64 dollars.
  DollarFloat64 = 1,
};

/// The registry string for a profile ("cent_int32" / "dollar_float64").
[[nodiscard]] const char* source_profile_name(SourceProfile profile) noexcept;

/// One registry-pinned session. Exactly the ten fields WP1 exposes, plus the
/// parsed civil date (the day string validated into a strong type).
struct Session {
  std::string day;
  CivilDate civil_date;
  std::int64_t session_start_ns;
  std::int64_t session_end_ns;
  std::int64_t expected_bar_count;
  std::string source_relative_path;
  std::string source_sha256;
  std::int64_t source_size_bytes;
  SourceProfile source_profile;
  std::int64_t raw_rth_row_count;
  std::int64_t complete_group_count;
};

/// Receipt of a successful load (mirrors corpus::RegistryReceipt).
struct RegistryReceipt {
  std::string sha256;
  std::size_t session_count;
};

/// The parsed, digest-gated registry.
class Registry {
 public:
  /// Loads the embedded registry text: sha256 gate FIRST, then parse.
  [[nodiscard]] static Expected<Registry, Refusal> load_embedded();

  /// Loads registry text from disk: sha256 gate FIRST, then parse. A single
  /// flipped byte anywhere in the file refuses with REGISTRY_DIGEST_MISMATCH.
  [[nodiscard]] static Expected<Registry, Refusal> load_from_file(
      const std::filesystem::path& path);

  /// Gate + parse over caller-held bytes.
  [[nodiscard]] static Expected<Registry, Refusal> load_from_text(std::string_view tsv);

  /// TEST-ONLY escape hatch: parse WITHOUT the digest gate, so malformation
  /// itself can be exercised. No production entry point calls this; every
  /// other loader gates first.
  [[nodiscard]] static Expected<Registry, Refusal> parse_without_digest_gate(
      std::string_view tsv);

  [[nodiscard]] std::size_t size() const noexcept { return sessions_.size(); }
  [[nodiscard]] const std::vector<Session>& sessions() const noexcept { return sessions_; }
  [[nodiscard]] const RegistryReceipt& receipt() const noexcept { return receipt_; }

  /// Session by 0-based calendar ordinal. Out-of-range is a refusal, never UB.
  [[nodiscard]] Expected<const Session*, Refusal> session_at(std::int64_t ordinal) const noexcept;

  /// 0-based calendar ordinal of a civil day, or UNKNOWN_SESSION.
  [[nodiscard]] Expected<std::int64_t, Refusal> ordinal_of_day(std::string_view day) const noexcept;

 private:
  explicit Registry(std::vector<Session> sessions, RegistryReceipt receipt) noexcept
      : sessions_(std::move(sessions)), receipt_(std::move(receipt)) {}

  std::vector<Session> sessions_;
  RegistryReceipt receipt_;
};

/// Lowercase hex sha256 of a byte range (OpenSSL libcrypto).
[[nodiscard]] std::string sha256_hex(std::string_view bytes);

/// The embedded registry text (generated from the pinned TSV at configure time).
[[nodiscard]] std::string_view embedded_registry_text() noexcept;

}  // namespace qr

#endif  // QR_REGISTRY_REGISTRY_HPP
