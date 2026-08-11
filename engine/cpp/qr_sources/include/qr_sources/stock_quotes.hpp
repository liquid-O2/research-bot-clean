// qr_sources/stock_quotes.hpp — B1: the IWM NBBO stock-quote reader.
//
// SPEC (FINAL_PLAN APPENDIX B1, verbatim): "ts(0)=clock; bid_size/ask_size(1/5)
// =depth/imbalance/queue-decomp; bid_exchange/ask_exchange(2/6)=venue features
// (projection EXTENDED vs old [0,1,3,4,5,7,8]); bid/ask(3/7)=all price channels
// (finite,>0,ask>bid); conditions(4/8)=eligibility code 0; cols 9-15 NEVER READ
// — recomputed (scalar-means-before-derived law)."
// SPEC (design/DESIGN_SUBSTRATE.md APPENDIX C3): open refuses wrong schema
// pre-payload; next_group() is the equal-time iterator.
// Reference semantics (read-only): select_v2/src/sources/stock_quotes.rs and
// corpus/src/reader.rs:842-940 (the row/group counts the registry pins).
//
// THIS IS THE STREAM THE REGISTRY COUNTS. After a full pass over an admitted
// session, `rth_rows()` equals that session's `raw_rth_row_count` and
// `group_count()` equals its `complete_group_count` — two independent numbers
// signed into the frozen registry, reproduced by a decoder that shares no code
// with the one that produced them. That is the WP4 half of the "registry
// oracle" (FINAL_PLAN section 6, correctness oracle 2).
//
// WHAT IS NOT DONE HERE: eligibility (condition == 0), structural validity
// (ask >= bid, sizes > 0), quote KIND classification and midpoint dedup. Those
// are the group machine's, in WP5 (`qr_nbbo`). This reader retains the raw
// two-sided state and refuses only what is undecodable.
#ifndef QR_SOURCES_STOCK_QUOTES_HPP
#define QR_SOURCES_STOCK_QUOTES_HPP

#include <cstdint>
#include <filesystem>
#include <span>
#include <string>
#include <vector>

#include "qr_clock/session_clock.hpp"
#include "qr_registry/day_scope.hpp"
#include "qr_registry/warmup_scope.hpp"
#include "qr_sources/session_source.hpp"
#include "qr_sources/stream_spec.hpp"

namespace qr::sources {

/// Projection slots of `kStockQuoteSpec`, i.e. the bit positions of
/// `StockQuoteRow::null_mask`. They are the leaf indices too, because B1
/// projects a prefix — but the mask is defined on SLOTS, so a future
/// projection change cannot silently re-point a bit.
enum StockQuoteSlot : std::size_t {
  kQuoteSlotTimestamp = 0,
  kQuoteSlotBidSize = 1,
  kQuoteSlotBidExchange = 2,
  kQuoteSlotBid = 3,
  kQuoteSlotBidCondition = 4,
  kQuoteSlotAskSize = 5,
  kQuoteSlotAskExchange = 6,
  kQuoteSlotAsk = 7,
  kQuoteSlotAskCondition = 8,
};

/// One retained NBBO row: raw two-sided state, normalized to u6 and shares.
struct StockQuoteRow {
  /// Naive-ET (frame B) milliseconds, exactly as stamped on the tape.
  std::int64_t ts_ms_b = 0;
  std::int64_t bid_u6 = 0;
  std::int64_t ask_u6 = 0;
  /// Displayed size in SHARES (the F-34 lot/share era folded at this boundary).
  std::int64_t bid_shares = 0;
  std::int64_t ask_shares = 0;
  std::int64_t bid_exchange = 0;
  std::int64_t ask_exchange = 0;
  std::int64_t bid_condition = 0;
  std::int64_t ask_condition = 0;
  /// Bit `slot` set == projected column `slot` was null on the tape. A null
  /// field carries 0, never a sentinel that could collide with a real value.
  std::uint16_t null_mask = 0;

  [[nodiscard]] std::int64_t group_ts_ms() const noexcept { return ts_ms_b; }
  [[nodiscard]] bool is_null(std::size_t slot) const noexcept {
    return (null_mask & static_cast<std::uint16_t>(1U << slot)) != 0;
  }
  /// The true midpoint — computed, never the vendor `mid` column.
  [[nodiscard]] std::int64_t mid_u6() const noexcept { return midpoint_u6(bid_u6, ask_u6); }
};

/// The canonical in-group order (see session_source.hpp): total, deterministic,
/// and independent of the order the vendor happened to write the rows in.
[[nodiscard]] bool canonical_less(const StockQuoteRow& left, const StockQuoteRow& right) noexcept;
void append_serialized(const StockQuoteRow& row, std::vector<std::uint8_t>& out);

/// Per-projected-column digests over the rows a reader EMITS (the WP4 digest
/// rule). One entry per projection slot, in projection order.
struct StockQuoteDigests {
  std::array<ValueDigest, 9> field{};
  void fold(const StockQuoteRow& row) noexcept;
  [[nodiscard]] static std::string_view field_name(std::size_t slot) noexcept;
};

/// Streaming raw-NBBO reader for one admitted session.
class StockQuoteReader {
 public:
  struct Group {
    std::int64_t ts_ms_b = 0;
    /// Valid until the next `next_group` call on this reader.
    std::span<const StockQuoteRow> rows;
  };

  StockQuoteReader(const StockQuoteReader&) = delete;
  StockQuoteReader& operator=(const StockQuoteReader&) = delete;
  StockQuoteReader(StockQuoteReader&&) = default;
  StockQuoteReader& operator=(StockQuoteReader&&) = default;
  ~StockQuoteReader() = default;

  /// APPENDIX C3's `open(DayScope, Profile)`.
  ///
  /// THE DUAL PROFILE LAW IS ENFORCED HERE, TWICE: `profile` must equal the
  /// session's own registry-row profile (a caller may not decide the encoding),
  /// and the file's bid/ask/size columns must have that profile's physical
  /// forms (the file may not disagree with the registry). Neither check is a
  /// fallback: both refuse.
  ///
  /// The path is the registry's OWN relative path composed onto `corpus_root`
  /// (`DayScope::source_path`), never a reconstructed one.
  [[nodiscard]] static FileExpected<StockQuoteReader> open(
      const DayScope& scope, const std::filesystem::path& corpus_root, SourceProfile profile);

  /// CC-012: the SAME open, for a warmup session (ordinals 0..124), reachable
  /// only through a `WarmupScope` and therefore only from a prior-state
  /// accumulator. Both overloads run one body — the profile law, the clock and
  /// the schema gate are the identical code, so a warmup read is not a second,
  /// laxer reader.
  [[nodiscard]] static FileExpected<StockQuoteReader> open(
      const WarmupScope& scope, const std::filesystem::path& corpus_root, SourceProfile profile);

  /// Delivers the next equal-millisecond group. False at end of session.
  [[nodiscard]] FileExpected<bool> next_group(Group& out);

  /// RTH rows retained so far. After a full pass this equals the session's
  /// registry `raw_rth_row_count`.
  [[nodiscard]] std::int64_t rth_rows() const noexcept { return rth_rows_; }
  /// Equal-millisecond groups delivered so far. After a full pass this equals
  /// the session's registry `complete_group_count`.
  [[nodiscard]] std::int64_t group_count() const noexcept { return group_count_; }
  /// All-null rows skipped (the corpus's per-file sentinel row). Counted, never
  /// silently folded into zero.
  [[nodiscard]] std::int64_t sentinel_rows() const noexcept { return sentinel_rows_; }
  [[nodiscard]] std::int64_t decoded_values() const noexcept { return source_.decoded_values(); }
  [[nodiscard]] const std::filesystem::path& path() const noexcept { return source_.path(); }
  [[nodiscard]] SourceProfile profile() const noexcept { return profile_; }
  [[nodiscard]] const SessionSource& source() const noexcept { return source_; }

 private:
  StockQuoteReader(SessionSource source, SourceProfile profile, std::string day)
      : source_(std::move(source)), profile_(profile), day_(std::move(day)) {}

  /// The ONE body both public `open`s run (CC-012). It takes a path and a
  /// registry row that one of the two walls has ALREADY admitted, so it can
  /// neither form a path itself nor decide which calendar a session belongs to.
  [[nodiscard]] static FileExpected<StockQuoteReader> open_admitted(
      std::filesystem::path path, const Session& session, SourceProfile profile,
      std::int64_t ordinal);

  [[nodiscard]] FileExpected<bool> fill();

  SessionSource source_;
  GroupTape<StockQuoteRow> tape_;
  SourceProfile profile_ = SourceProfile::CentInt32;
  std::string day_;
  std::int64_t rth_rows_ = 0;
  std::int64_t group_count_ = 0;
  std::int64_t sentinel_rows_ = 0;
  std::int64_t last_ts_ms_ = 0;
  bool has_last_ts_ = false;
  bool exhausted_ = false;
};

}  // namespace qr::sources

#endif  // QR_SOURCES_STOCK_QUOTES_HPP
