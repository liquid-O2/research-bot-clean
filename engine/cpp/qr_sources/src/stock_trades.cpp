#include "qr_sources/stock_trades.hpp"

#include <array>
#include <string>

#include "qr_clock/session_clock.hpp"

namespace qr::sources {
namespace {

constexpr const char* kOpenSite = "qr_sources::StockTradeReader::open";
constexpr const char* kRowSite = "qr_sources::StockTradeReader::row";

/// The attached-NBBO size slots: B2's `size` (8) is a PRINT size and is already
/// in shares, while (11) and (15) are NBBO displayed sizes and carry the F-34
/// era, exactly as the reference splits them (`stock_trades.rs:207-221`).
constexpr std::array<std::size_t, 2> kNbboSizeSlots{kTradeSlotBidSize, kTradeSlotAskSize};

}  // namespace

bool canonical_less(const StockTradeRow& left, const StockTradeRow& right) noexcept {
  if (left.ts_ms_b != right.ts_ms_b) return left.ts_ms_b < right.ts_ms_b;
  if (left.sequence != right.sequence) return left.sequence < right.sequence;
  if (left.price_u6 != right.price_u6) return left.price_u6 < right.price_u6;
  if (left.size != right.size) return left.size < right.size;
  if (left.exchange != right.exchange) return left.exchange < right.exchange;
  if (left.condition != right.condition) return left.condition < right.condition;
  for (std::size_t index = 0; index < left.ext_condition.size(); ++index) {
    if (left.ext_condition[index] != right.ext_condition[index]) {
      return left.ext_condition[index] < right.ext_condition[index];
    }
  }
  if (left.quote_ts_ms_b != right.quote_ts_ms_b) return left.quote_ts_ms_b < right.quote_ts_ms_b;
  if (left.bid_u6 != right.bid_u6) return left.bid_u6 < right.bid_u6;
  if (left.ask_u6 != right.ask_u6) return left.ask_u6 < right.ask_u6;
  if (left.bid_shares != right.bid_shares) return left.bid_shares < right.bid_shares;
  if (left.ask_shares != right.ask_shares) return left.ask_shares < right.ask_shares;
  if (left.bid_exchange != right.bid_exchange) return left.bid_exchange < right.bid_exchange;
  if (left.ask_exchange != right.ask_exchange) return left.ask_exchange < right.ask_exchange;
  if (left.bid_condition != right.bid_condition) return left.bid_condition < right.bid_condition;
  if (left.ask_condition != right.ask_condition) return left.ask_condition < right.ask_condition;
  return left.null_mask < right.null_mask;
}

void append_serialized(const StockTradeRow& row, std::vector<std::uint8_t>& out) {
  append_i64(row.ts_ms_b, out);
  append_i64(row.quote_ts_ms_b, out);
  append_i64(row.sequence, out);
  for (const std::int64_t value : row.ext_condition) {
    append_i64(value, out);
  }
  append_i64(row.condition, out);
  append_i64(row.size, out);
  append_i64(row.exchange, out);
  append_i64(row.price_u6, out);
  append_i64(row.bid_shares, out);
  append_i64(row.bid_exchange, out);
  append_i64(row.bid_u6, out);
  append_i64(row.bid_condition, out);
  append_i64(row.ask_shares, out);
  append_i64(row.ask_exchange, out);
  append_i64(row.ask_u6, out);
  append_i64(row.ask_condition, out);
  append_i64(static_cast<std::int64_t>(row.null_mask), out);
}

void StockTradeDigests::fold(const StockTradeRow& row) noexcept {
  const std::array<std::int64_t, 19> values{
      row.ts_ms_b,       row.quote_ts_ms_b,   row.sequence,      row.ext_condition[0],
      row.ext_condition[1], row.ext_condition[2], row.ext_condition[3], row.condition,
      row.size,          row.exchange,        row.price_u6,      row.bid_shares,
      row.bid_exchange,  row.bid_u6,          row.bid_condition, row.ask_shares,
      row.ask_exchange,  row.ask_u6,          row.ask_condition};
  for (std::size_t slot = 0; slot < values.size(); ++slot) {
    if (row.is_null(slot)) {
      field[slot].add_null();
    } else {
      field[slot].add_i64(values[slot]);
    }
  }
}

std::string_view StockTradeDigests::field_name(std::size_t slot) noexcept {
  static constexpr std::array<std::string_view, 19> kNames{
      "ts_ms_b",      "quote_ts_ms_b", "sequence",      "ext_condition1", "ext_condition2",
      "ext_condition3", "ext_condition4", "condition",  "size",           "exchange",
      "price_u6",     "bid_shares",    "bid_exchange",  "bid_u6",         "bid_condition",
      "ask_shares",   "ask_exchange",  "ask_u6",        "ask_condition"};
  return slot < kNames.size() ? kNames[slot] : std::string_view{"?"};
}

FileExpected<StockTradeReader> StockTradeReader::open(const DayScope& scope,
                                                      const std::filesystem::path& corpus_root) {
  const std::filesystem::path path = day_file(corpus_root, scope);
  Expected<SessionClock, Refusal> clock = SessionClock::from_session(scope.session());
  if (!clock.has_value()) {
    return parquet::refuse_file<StockTradeReader>(clock.error().code(), kOpenSite,
                                                  "the session clock refuses this registry row",
                                                  path.string(), scope.day(), scope.ordinal());
  }
  const std::int64_t open_ms = clock.value().open_b().ns() / kNanosecondsPerMillisecond;
  const std::int64_t close_ms = clock.value().close_b().ns() / kNanosecondsPerMillisecond;

  FileExpected<SessionSource> source = SessionSource::open(
      path, view_of(kStockTradeSpec), std::span<const ColumnForm>(kStockTradeForms), open_ms,
      close_ms);
  if (!source.has_value()) {
    return FileExpected<StockTradeReader>::refuse(source.error());
  }
  return StockTradeReader(std::move(source).value(), scope.day());
}

FileExpected<bool> StockTradeReader::fill() {
  FileExpected<std::int64_t> decoded = source_.next_chunk();
  if (!decoded.has_value()) {
    return FileExpected<bool>::refuse(decoded.error());
  }
  const std::int64_t rows = decoded.value();
  const bool end_of_session = rows == 0;
  tape_.begin_chunk();
  for (std::int64_t row = 0; row < rows; ++row) {
    // ADMISSION (reference `stock_trades.rs:198-200`): a print with no instant
    // or no price is not a print. Counted, never silently dropped.
    if (source_.cell(kTradeSlotTradeTimestamp).is_null(row) ||
        source_.cell(kTradeSlotPrice).is_null(row)) {
      ++skipped_null_rows_;
      continue;
    }
    Expected<std::int64_t, Refusal> timestamp = cell_i64(
        source_.cell(kTradeSlotTradeTimestamp), source_.form(kTradeSlotTradeTimestamp), row);
    if (!timestamp.has_value()) {
      return source_.refuse<bool>(timestamp.error(), day_);
    }
    const std::int64_t ts_ms = timestamp.value();
    if (has_last_ts_ && ts_ms < last_ts_ms_) {
      return source_.refuse<bool>(
          Refusal(RefusalCode::OUT_OF_ORDER, kRowSite, "print tape descends in time", ts_ms), day_);
    }
    last_ts_ms_ = ts_ms;
    has_last_ts_ = true;
    if (ts_ms < source_.open_ms_b() || ts_ms >= source_.close_ms_b()) {
      continue;
    }
    ++rth_rows_;

    StockTradeRow built;
    built.ts_ms_b = ts_ms;

    Expected<std::int64_t, Refusal> price =
        cell_u6(source_.cell(kTradeSlotPrice), source_.form(kTradeSlotPrice), row);
    if (!price.has_value()) {
      return source_.refuse<bool>(price.error(), day_);
    }
    built.price_u6 = price.value();

    // The attached quote block's prices.
    const std::array<std::size_t, 2> price_slots{kTradeSlotBid, kTradeSlotAsk};
    std::array<std::int64_t, 2> quote_prices{0, 0};
    for (std::size_t index = 0; index < price_slots.size(); ++index) {
      Expected<std::int64_t, Refusal> value =
          read_nullable_u6(source_, price_slots[index], row, built.null_mask);
      if (!value.has_value()) {
        return source_.refuse<bool>(value.error(), day_);
      }
      quote_prices[index] = value.value();
    }
    built.bid_u6 = quote_prices[0];
    built.ask_u6 = quote_prices[1];

    // The attached quote block's displayed sizes, in shares.
    std::array<std::int64_t, 2> shares{0, 0};
    for (std::size_t index = 0; index < kNbboSizeSlots.size(); ++index) {
      Expected<std::int64_t, Refusal> raw =
          read_nullable_int(source_, kNbboSizeSlots[index], row, built.null_mask);
      if (!raw.has_value()) {
        return source_.refuse<bool>(raw.error(), day_);
      }
      if (built.is_null(kNbboSizeSlots[index])) {
        continue;
      }
      Expected<std::int64_t, Refusal> normalized = nbbo_size_to_shares(raw.value(), day_);
      if (!normalized.has_value()) {
        return source_.refuse<bool>(normalized.error(), day_);
      }
      shares[index] = normalized.value();
    }
    built.bid_shares = shares[0];
    built.ask_shares = shares[1];

    // Every remaining projected column is a plain nullable integer, in slot
    // order so the mask bits cannot drift from the projection.
    constexpr std::array<std::size_t, 13> kIntSlots{
        kTradeSlotQuoteTimestamp, kTradeSlotSequence,      kTradeSlotExtCondition1,
        kTradeSlotExtCondition2,  kTradeSlotExtCondition3, kTradeSlotExtCondition4,
        kTradeSlotCondition,      kTradeSlotSize,          kTradeSlotExchange,
        kTradeSlotBidExchange,    kTradeSlotBidCondition,  kTradeSlotAskExchange,
        kTradeSlotAskCondition};
    std::array<std::int64_t, 13> ints{};
    for (std::size_t index = 0; index < kIntSlots.size(); ++index) {
      Expected<std::int64_t, Refusal> value =
          read_nullable_int(source_, kIntSlots[index], row, built.null_mask);
      if (!value.has_value()) {
        return source_.refuse<bool>(value.error(), day_);
      }
      ints[index] = value.value();
    }
    built.quote_ts_ms_b = ints[0];
    built.sequence = ints[1];
    built.ext_condition[0] = ints[2];
    built.ext_condition[1] = ints[3];
    built.ext_condition[2] = ints[4];
    built.ext_condition[3] = ints[5];
    built.condition = ints[6];
    built.size = ints[7];
    built.exchange = ints[8];
    built.bid_exchange = ints[9];
    built.bid_condition = ints[10];
    built.ask_exchange = ints[11];
    built.ask_condition = ints[12];

    tape_.push(built);
  }
  tape_.end_chunk(end_of_session);
  if (end_of_session) {
    exhausted_ = true;
  }
  return true;
}

FileExpected<bool> StockTradeReader::next_group(Group& out) {
  while (true) {
    if (tape_.next(out.ts_ms_b, out.rows)) {
      ++group_count_;
      return true;
    }
    if (exhausted_) {
      return false;
    }
    FileExpected<bool> filled = fill();
    if (!filled.has_value()) {
      return filled;
    }
  }
}

}  // namespace qr::sources
