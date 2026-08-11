// qr_sources/stock_trades.hpp — B2: the IWM stock-print (tape) reader.
//
// SPEC (FINAL_PLAN APPENDIX B2, verbatim): "trade_ts(0); quote_ts(1)=attachment
// clock (strict-prior; WCD typed); sequence(2)=quality only, never ordering;
// ext_cond1-4(3-6)=sentinel-255 conjunction; condition(7)=0 admit/40-44 CANCEL;
// size(8); exchange(9); price(10); attached bid/ask blocks (11,13,14/15,17,18)
// = quote-certified aggressor + own/opposite; attached exchanges (12,16) =
// internalization proxy; 19-21,23 NEVER READ; **price_lead_1(22)
// DECODE-REFUSED** (future-looking; name-pinned only)."
// Reference semantics (read-only): select_v2/src/sources/stock_trades.rs.
//
// THE FUTURE FIELD. `price_lead_1` stays in the schema pin so drift is still
// detected and is walled in `kStockTradeSpec.forbidden` as DecodeRefused, so
// asking for it — by index or by name — is a COLUMN_FORBIDDEN refusal that
// names the column. The reference enforced the same law with a Rust unit test
// asserting the projection does not contain the index; the C++ port makes the
// decode path itself refuse, which is a wall rather than a check.
//
// WHAT IS NOT DONE HERE: the sentinel-255 conjunction, the CANCEL codes, the
// aggressor rule and the internalization proxy are USES of these columns and
// land with their features. This reader retains them.
#ifndef QR_SOURCES_STOCK_TRADES_HPP
#define QR_SOURCES_STOCK_TRADES_HPP

#include <array>
#include <cstdint>
#include <filesystem>
#include <span>
#include <string>
#include <vector>

#include "qr_registry/day_scope.hpp"
#include "qr_registry/warmup_scope.hpp"
#include "qr_sources/session_source.hpp"
#include "qr_sources/stream_spec.hpp"

namespace qr::sources {

/// Projection slots of `kStockTradeSpec` == bit positions of the row's
/// `null_mask` (B2 projects leaves 0..18, so slot == leaf here).
enum StockTradeSlot : std::size_t {
  kTradeSlotTradeTimestamp = 0,
  kTradeSlotQuoteTimestamp = 1,
  kTradeSlotSequence = 2,
  kTradeSlotExtCondition1 = 3,
  kTradeSlotExtCondition2 = 4,
  kTradeSlotExtCondition3 = 5,
  kTradeSlotExtCondition4 = 6,
  kTradeSlotCondition = 7,
  kTradeSlotSize = 8,
  kTradeSlotExchange = 9,
  kTradeSlotPrice = 10,
  kTradeSlotBidSize = 11,
  kTradeSlotBidExchange = 12,
  kTradeSlotBid = 13,
  kTradeSlotBidCondition = 14,
  kTradeSlotAskSize = 15,
  kTradeSlotAskExchange = 16,
  kTradeSlotAsk = 17,
  kTradeSlotAskCondition = 18,
};

/// One retained print, with the NBBO state the vendor attached to it.
struct StockTradeRow {
  /// Print instant, naive-ET (frame B) milliseconds.
  std::int64_t ts_ms_b = 0;
  /// The ATTACHMENT CLOCK, retained raw in frame B. Whether it is strict-prior,
  /// on-day or wrong-civil-day is `qr_clock::classify_attach`'s answer, asked
  /// where the attachment is USED — never silently here.
  std::int64_t quote_ts_ms_b = 0;
  std::int64_t sequence = 0;
  std::array<std::int64_t, 4> ext_condition{};
  std::int64_t condition = 0;
  std::int64_t size = 0;
  std::int64_t exchange = 0;
  std::int64_t price_u6 = 0;
  std::int64_t bid_u6 = 0;
  std::int64_t ask_u6 = 0;
  /// Attached NBBO sizes in SHARES (F-34 era folded, as for the quote stream).
  std::int64_t bid_shares = 0;
  std::int64_t ask_shares = 0;
  std::int64_t bid_exchange = 0;
  std::int64_t ask_exchange = 0;
  std::int64_t bid_condition = 0;
  std::int64_t ask_condition = 0;
  /// Bit `slot` set == that projected column was null on the tape.
  std::uint32_t null_mask = 0;

  [[nodiscard]] std::int64_t group_ts_ms() const noexcept { return ts_ms_b; }
  [[nodiscard]] bool is_null(std::size_t slot) const noexcept {
    return (null_mask & (std::uint32_t{1} << slot)) != 0;
  }
  /// True when the whole attached quote block was present — absence is not
  /// zero, so consumers must ask before using it.
  [[nodiscard]] bool quote_present() const noexcept {
    return !is_null(kTradeSlotBid) && !is_null(kTradeSlotAsk) && !is_null(kTradeSlotBidSize) &&
           !is_null(kTradeSlotAskSize);
  }
};

[[nodiscard]] bool canonical_less(const StockTradeRow& left, const StockTradeRow& right) noexcept;
void append_serialized(const StockTradeRow& row, std::vector<std::uint8_t>& out);

struct StockTradeDigests {
  std::array<ValueDigest, 19> field{};
  void fold(const StockTradeRow& row) noexcept;
  [[nodiscard]] static std::string_view field_name(std::size_t slot) noexcept;
};

/// Streaming print reader for one admitted session.
class StockTradeReader {
 public:
  struct Group {
    std::int64_t ts_ms_b = 0;
    std::span<const StockTradeRow> rows;
  };

  StockTradeReader(const StockTradeReader&) = delete;
  StockTradeReader& operator=(const StockTradeReader&) = delete;
  StockTradeReader(StockTradeReader&&) = default;
  StockTradeReader& operator=(StockTradeReader&&) = default;
  ~StockTradeReader() = default;

  /// Opens `<corpus_root>/<YYYY>/<day>.parquet` for an ADMITTED session. The
  /// single measured profile (`kStockTradeForms`) is pinned: a file outside it
  /// is refused pre-payload, naming the offending column.
  [[nodiscard]] static FileExpected<StockTradeReader> open(
      const DayScope& scope, const std::filesystem::path& corpus_root);

  /// CC-012: the same open for a WARMUP session (ordinals 0..124), reachable
  /// only through a `WarmupScope`. Both overloads run one body.
  [[nodiscard]] static FileExpected<StockTradeReader> open(
      const WarmupScope& scope, const std::filesystem::path& corpus_root);

  [[nodiscard]] FileExpected<bool> next_group(Group& out);

  [[nodiscard]] std::int64_t rth_rows() const noexcept { return rth_rows_; }
  [[nodiscard]] std::int64_t group_count() const noexcept { return group_count_; }
  /// Rows dropped because the print instant or the print price was absent —
  /// the reference's admission rule (`stock_trades.rs:198-200`), counted rather
  /// than silent.
  [[nodiscard]] std::int64_t skipped_null_rows() const noexcept { return skipped_null_rows_; }
  [[nodiscard]] std::int64_t decoded_values() const noexcept { return source_.decoded_values(); }
  [[nodiscard]] const std::filesystem::path& path() const noexcept { return source_.path(); }
  [[nodiscard]] const SessionSource& source() const noexcept { return source_; }

 private:
  StockTradeReader(SessionSource source, std::string day)
      : source_(std::move(source)), day_(std::move(day)) {}

  /// The ONE body both public `open`s run (CC-012), over a path and a registry
  /// row that one of the two walls has already admitted.
  [[nodiscard]] static FileExpected<StockTradeReader> open_admitted(
      std::filesystem::path path, const Session& session, std::int64_t ordinal);

  [[nodiscard]] FileExpected<bool> fill();

  SessionSource source_;
  GroupTape<StockTradeRow> tape_;
  std::string day_;
  std::int64_t rth_rows_ = 0;
  std::int64_t group_count_ = 0;
  std::int64_t skipped_null_rows_ = 0;
  std::int64_t last_ts_ms_ = 0;
  bool has_last_ts_ = false;
  bool exhausted_ = false;
};

}  // namespace qr::sources

#endif  // QR_SOURCES_STOCK_TRADES_HPP
