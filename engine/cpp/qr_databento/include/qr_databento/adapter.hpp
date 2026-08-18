#ifndef QR_DATABENTO_ADAPTER_HPP
#define QR_DATABENTO_ADAPTER_HPP

#include <cstdint>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#include "qr_core/refusal.hpp"

namespace qr::databento {

inline constexpr std::uint8_t kFlagLast = 0x80u;
inline constexpr std::uint8_t kFlagSnapshot = 0x20u;
inline constexpr std::uint8_t kFlagBadTsRecv = 0x08u;
inline constexpr std::uint8_t kFlagMaybeBadBook = 0x04u;

struct MappingInterval {
  std::int32_t start_yyyymmdd = 0;
  std::int32_t end_yyyymmdd = 0;
  std::string instrument_id;
};

struct SymbolMapping {
  std::string raw_symbol;
  std::vector<MappingInterval> intervals;
};

struct Metadata {
  std::uint8_t version = 0;
  std::string dataset;
  std::uint16_t schema = 0;
  std::uint64_t start_ts_recv_ns = 0;
  std::uint64_t end_ts_recv_ns = 0;
  std::uint64_t limit = 0;
  std::uint8_t stype_in = 0;
  std::uint8_t stype_out = 0;
  bool ts_out = false;
  std::vector<std::string> symbols;
  std::vector<std::string> partial;
  std::vector<std::string> not_found;
  std::vector<SymbolMapping> mappings;
};

struct Mbp1Row {
  std::uint64_t source_ordinal = 0;
  std::uint16_t publisher_id = 0;
  std::uint32_t instrument_id = 0;
  std::uint64_t ts_recv_ns = 0;
  std::uint64_t ts_event_ns = 0;
  std::uint32_t sequence = 0;
  std::int64_t price = 0;
  std::uint32_t size = 0;
  std::uint8_t action = 0;
  std::uint8_t side = 0;
  std::uint8_t flags = 0;
  std::uint8_t depth = 0;
  std::int32_t ts_in_delta_ns = 0;
  std::int64_t bid_px = 0;
  std::int64_t ask_px = 0;
  std::uint32_t bid_sz = 0;
  std::uint32_t ask_sz = 0;
  std::uint32_t bid_ct = 0;
  std::uint32_t ask_ct = 0;
  std::string raw_symbol;
};

struct BuildAuthority {
  const char* databento_version;
  const char* declared_upstream_commit;
  const char* vendor_tree_sha256;
  const char* adapter_source_sha256;
  const char* clock_law_sha256;
  const char* portability_gap;
};

[[nodiscard]] const BuildAuthority& build_authority() noexcept;

class Mbp1File {
 public:
  Mbp1File();
  ~Mbp1File();
  Mbp1File(Mbp1File&&) noexcept;
  Mbp1File& operator=(Mbp1File&&) noexcept;
  Mbp1File(const Mbp1File&) = delete;
  Mbp1File& operator=(const Mbp1File&) = delete;

  [[nodiscard]] Expected<std::monostate, Refusal> open(
      const std::string& path, std::uint64_t source_ordinal_base = 0);
  [[nodiscard]] const Metadata& metadata() const noexcept;
  [[nodiscard]] Expected<std::optional<Mbp1Row>, Refusal> next_mbp1();
  [[nodiscard]] std::uint64_t records_read() const noexcept;

 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

}  // namespace qr::databento

#endif  // QR_DATABENTO_ADAPTER_HPP
