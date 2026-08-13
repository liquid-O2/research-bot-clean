// qr_dbn/dbn.hpp — exact binary decode of Databento DBN GLBX mbp-1 payloads.
//
// SPEC: design/PORT_M1_SPEC.md §1.1 — "exact DBN binary decode of GLBX mbp-1
// files: zstd streaming (libzstd) -> metadata header (symbology mappings incl.
// date-ranged instrument->raw-symbol) -> fixed-size Mbp1Msg records
// (RecordHeader + price/size/action/side/flags/depth/ts_recv/ts_event/sequence
// + levels[0] bid/ask px/sz)".
//
// LAYOUT PROVENANCE (the lane's verification, not a recollection):
//   * The struct offsets below were decoded from the `databento_dbn` Python
//     library's record introspection and then CROSS-CHECKED FIELD BY FIELD
//     against 5,000 consecutive real records of
//     `[Copper] .../glbx-mdp3-20240101-20241231.mbp-1.dbn.zst`
//     (qr_dbn/tests/test_real_file.cpp reruns that cross-check).
//   * The metadata parse is verified by exact frame consumption (the parse must
//     land on the last byte of the declared frame) plus a mapping-by-mapping
//     comparison against the library's decoded `Metadata.mappings`.
//   * The Python library is an ORACLE ONLY. Nothing here calls it at runtime.
//
// VERSION (spec defect, reported by the lane): PORT_M1_SPEC §1.1 says "DBN-v3".
// Every payload file in artifacts/reference/futures_mbp1/ carries the magic
// `DBN\x01` — they are DBN **v1** streams (v1 keeps the deprecated
// `record_count` field and pins symbol strings at 22 bytes; v2+ moved to a
// header-declared `symbol_cstr_len`). This decoder implements the version it
// can verify against real bytes and refuses every other version by name rather
// than guessing at an unverified layout.
#ifndef QR_DBN_DBN_HPP
#define QR_DBN_DBN_HPP

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_dbn/zstd_stream.hpp"

namespace qr::dbn {

/// DBN v1 pins symbol C-strings at 22 bytes (`SYMBOL_CSTR_LEN_V1`).
inline constexpr std::size_t kSymbolCstrLenV1 = 22;
/// The only stream version this decoder has verified real bytes for.
inline constexpr std::uint8_t kSupportedVersion = 1;
/// `Schema::Mbp1`.
inline constexpr std::uint16_t kSchemaMbp1 = 1;
/// `RType::Mbp1`.
inline constexpr std::uint8_t kRTypeMbp1 = 1;
/// DBN record lengths are stored in units of 4 bytes (`length` field).
inline constexpr std::size_t kLengthUnit = 4;

#pragma pack(push, 1)
/// DBN `RecordHeader` — 16 bytes, identical in every DBN version.
struct RecordHeader {
  std::uint8_t length;          // record length in 4-byte units
  std::uint8_t rtype;           // RType
  std::uint16_t publisher_id;
  std::uint32_t instrument_id;
  std::uint64_t ts_event;       // UTC nanoseconds — THE clock (M0 spec §0)
};

/// DBN `BidAskPair` — 32 bytes.
struct BidAskPair {
  std::int64_t bid_px;
  std::int64_t ask_px;
  std::uint32_t bid_sz;
  std::uint32_t ask_sz;
  std::uint32_t bid_ct;
  std::uint32_t ask_ct;
};

/// DBN `Mbp1Msg` — 80 bytes.
struct Mbp1Msg {
  RecordHeader hd;
  std::int64_t price;
  std::uint32_t size;
  std::uint8_t action;          // ASCII: 'A' 'C' 'M' 'R' 'T' 'F' ...
  std::uint8_t side;            // ASCII: 'B' 'A' 'N'
  std::uint8_t flags;           // bit 7 (0x80) = F_LAST
  std::uint8_t depth;
  std::uint64_t ts_recv;
  std::int32_t ts_in_delta;
  std::uint32_t sequence;
  BidAskPair levels[1];
};
#pragma pack(pop)

static_assert(sizeof(RecordHeader) == 16, "DBN RecordHeader must be 16 bytes");
static_assert(sizeof(BidAskPair) == 32, "DBN BidAskPair must be 32 bytes");
static_assert(sizeof(Mbp1Msg) == 80, "DBN Mbp1Msg must be 80 bytes");

/// One date-ranged symbology interval. Dates are YYYYMMDD integers, whose
/// integer order is exactly their calendar order.
struct MappingInterval {
  std::int32_t start_date = 0;
  std::int32_t end_date = 0;
  std::string symbol;           // the mapped-TO side (stype_out)
};

/// One `raw_symbol -> intervals` row of the metadata symbology block.
struct SymbolMapping {
  std::string raw_symbol;
  std::vector<MappingInterval> intervals;
};

/// The decoded DBN metadata header.
struct Metadata {
  std::uint8_t version = 0;
  std::string dataset;
  std::uint16_t schema = 0;
  std::uint64_t start = 0;
  std::uint64_t end = 0;
  std::uint64_t limit = 0;
  std::uint8_t stype_in = 0;
  std::uint8_t stype_out = 0;
  std::uint8_t ts_out = 0;
  std::vector<std::string> symbols;
  std::vector<std::string> partial;
  std::vector<std::string> not_found;
  std::vector<SymbolMapping> mappings;
};

/// `instrument_id -> date-ranged raw symbol`, the inversion PORT M0
/// `common.invert_mappings` performs, with its exact ordering and lookup rules.
class SymbolIndex {
 public:
  /// Build from decoded metadata. Intervals whose mapped-to symbol is not a
  /// plain integer instrument id are skipped, exactly as the M0 reference does.
  void build(const Metadata& md);

  /// Raw symbol of `iid` on `yyyymmdd`; "" when the id is unmapped.
  /// Rule (M0 `common.symbol_for`): the first interval with
  /// `start <= day < end`; else the first interval; else "".
  [[nodiscard]] const std::string& symbol_for(std::uint32_t iid, std::int32_t yyyymmdd) const;

  /// `is_outright` (M0 `common.is_outright`): non-empty and containing no '-'.
  [[nodiscard]] static bool is_outright(const std::string& raw_symbol);

 private:
  struct Entry {
    std::uint32_t iid;
    std::int32_t start_date;
    std::int32_t end_date;
    std::string raw_symbol;
  };
  std::vector<Entry> entries_;  // sorted by (iid, start, end, raw_symbol)
};

/// Streaming DBN reader: metadata first, then fixed-size records.
class DbnStream {
 public:
  /// Open and decode the metadata header. Refuses a non-DBN magic, an
  /// unverified stream version, a non-mbp-1 schema, and any metadata frame the
  /// parse does not consume exactly.
  [[nodiscard]] Expected<std::monostate, Refusal> open(const std::string& path);

  [[nodiscard]] const Metadata& metadata() const noexcept { return metadata_; }

  /// Next `Mbp1Msg`, or nullptr at a clean end of stream. Records of other
  /// rtypes are skipped and counted. The returned pointer is valid until the
  /// next call.
  [[nodiscard]] Expected<const Mbp1Msg*, Refusal> next_mbp1();

  [[nodiscard]] std::uint64_t n_skipped() const noexcept { return n_skipped_; }
  [[nodiscard]] std::uint64_t n_mbp1() const noexcept { return n_mbp1_; }

 private:
  /// Guarantee `want` bytes are buffered; returns the number actually
  /// available (< want only at end of stream).
  [[nodiscard]] Expected<std::size_t, Refusal> ensure(std::size_t want);

  ZstdStream zs_;
  Metadata metadata_;
  // Records are copied here before being handed out: the decompressed buffer
  // offset of a record is arbitrary, so reading its 8-byte members in place
  // would be an unaligned access (UBSan-visible, and not portable).
  Mbp1Msg scratch_{};
  std::vector<std::uint8_t> buf_;
  std::size_t head_ = 0;
  std::size_t tail_ = 0;
  std::uint64_t n_skipped_ = 0;
  std::uint64_t n_mbp1_ = 0;
  std::string path_;
};

/// Parse a metadata frame body (everything after the 8-byte magic+length
/// prefix). Exposed so fixtures can drive it without a file.
[[nodiscard]] Expected<Metadata, Refusal> parse_metadata_frame(std::uint8_t version,
                                                               const std::uint8_t* body,
                                                               std::size_t len);

}  // namespace qr::dbn

#endif  // QR_DBN_DBN_HPP
