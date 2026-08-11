#include "qr_sources/stock_quotes.hpp"

#include <array>
#include <string>

namespace qr::sources {
namespace {

constexpr const char* kOpenSite = "qr_sources::StockQuoteReader::open";
constexpr const char* kRowSite = "qr_sources::StockQuoteReader::row";

/// The seven fields the corpus's own null-pattern law covers
/// (`corpus/src/reader.rs:488-502`): timestamp, both sizes, both prices, both
/// conditions. The two EXCHANGE columns are outside it — B1 projects them as
/// venue features, and an absent venue is a null field, not a broken row.
constexpr std::array<std::size_t, 7> kNullPatternSlots{
    kQuoteSlotTimestamp, kQuoteSlotBidSize,      kQuoteSlotBid,       kQuoteSlotBidCondition,
    kQuoteSlotAskSize,   kQuoteSlotAsk,          kQuoteSlotAskCondition};

}  // namespace

bool canonical_less(const StockQuoteRow& left, const StockQuoteRow& right) noexcept {
  // Field-by-field, in projection order, with the null mask last: a total,
  // deterministic order over the whole row, so any permutation of an
  // equal-time run canonicalizes to the same sequence.
  if (left.ts_ms_b != right.ts_ms_b) return left.ts_ms_b < right.ts_ms_b;
  if (left.bid_shares != right.bid_shares) return left.bid_shares < right.bid_shares;
  if (left.bid_exchange != right.bid_exchange) return left.bid_exchange < right.bid_exchange;
  if (left.bid_u6 != right.bid_u6) return left.bid_u6 < right.bid_u6;
  if (left.bid_condition != right.bid_condition) return left.bid_condition < right.bid_condition;
  if (left.ask_shares != right.ask_shares) return left.ask_shares < right.ask_shares;
  if (left.ask_exchange != right.ask_exchange) return left.ask_exchange < right.ask_exchange;
  if (left.ask_u6 != right.ask_u6) return left.ask_u6 < right.ask_u6;
  if (left.ask_condition != right.ask_condition) return left.ask_condition < right.ask_condition;
  return left.null_mask < right.null_mask;
}

void append_serialized(const StockQuoteRow& row, std::vector<std::uint8_t>& out) {
  append_i64(row.ts_ms_b, out);
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

void StockQuoteDigests::fold(const StockQuoteRow& row) noexcept {
  const std::array<std::int64_t, 9> values{row.ts_ms_b,       row.bid_shares,  row.bid_exchange,
                                           row.bid_u6,        row.bid_condition, row.ask_shares,
                                           row.ask_exchange,  row.ask_u6,      row.ask_condition};
  for (std::size_t slot = 0; slot < values.size(); ++slot) {
    if (row.is_null(slot)) {
      field[slot].add_null();
    } else {
      field[slot].add_i64(values[slot]);
    }
  }
}

std::string_view StockQuoteDigests::field_name(std::size_t slot) noexcept {
  static constexpr std::array<std::string_view, 9> kNames{
      "ts_ms_b",       "bid_shares", "bid_exchange", "bid_u6",       "bid_condition",
      "ask_shares",    "ask_exchange", "ask_u6",     "ask_condition"};
  return slot < kNames.size() ? kNames[slot] : std::string_view{"?"};
}

FileExpected<StockQuoteReader> StockQuoteReader::open(const DayScope& scope,
                                                      const std::filesystem::path& corpus_root,
                                                      SourceProfile profile) {
  const std::filesystem::path path = scope.source_path(corpus_root);

  // THE DUAL PROFILE LAW, half one: the REGISTRY ROW decides. A caller that
  // asks for a different encoding than the session's own row declares is
  // refused — this is the wall against "detect it" and against "assume the
  // year", both of which the corpus falsifies (2025-12-30 is cent_int32 while
  // 2025-12-31 is dollar_float64).
  if (profile != scope.profile()) {
    std::string detail = "session ";
    detail += scope.day();
    detail += " is registered as ";
    detail += source_profile_name(scope.profile());
    detail += " but was opened as ";
    detail += source_profile_name(profile);
    return parquet::refuse_file<StockQuoteReader>(
        RefusalCode::CONFIG, kOpenSite, "the registry row decides the price profile, not the caller",
        path.string(), std::move(detail), scope.ordinal());
  }

  Expected<SessionClock, Refusal> clock = SessionClock::from_session(scope.session());
  if (!clock.has_value()) {
    return parquet::refuse_file<StockQuoteReader>(clock.error().code(), kOpenSite,
                                                  "the session clock refuses this registry row",
                                                  path.string(), scope.day(), scope.ordinal());
  }
  const std::int64_t open_ms = clock.value().open_b().ns() / kNanosecondsPerMillisecond;
  const std::int64_t close_ms = clock.value().close_b().ns() / kNanosecondsPerMillisecond;

  // THE DUAL PROFILE LAW, half two: the FILE must carry the declared profile's
  // physical forms. `gate_schema` runs on the footer alone.
  FileExpected<SessionSource> source =
      SessionSource::open(path, view_of(kStockQuoteSpec), stock_quote_forms(profile), open_ms,
                          close_ms);
  if (!source.has_value()) {
    return FileExpected<StockQuoteReader>::refuse(source.error());
  }
  return StockQuoteReader(std::move(source).value(), profile, scope.day());
}

FileExpected<bool> StockQuoteReader::fill() {
  FileExpected<std::int64_t> decoded = source_.next_chunk();
  if (!decoded.has_value()) {
    return FileExpected<bool>::refuse(decoded.error());
  }
  const std::int64_t rows = decoded.value();
  const bool end_of_session = rows == 0;
  tape_.begin_chunk();
  for (std::int64_t row = 0; row < rows; ++row) {
    // 1. THE NULL PATTERN (corpus law). An all-null row is the file's sentinel:
    //    skipped and COUNTED. A row that mixes null and non-null NBBO fields is
    //    undecodable and refuses — it is never half-trusted.
    unsigned nulls = 0;
    for (const std::size_t slot : kNullPatternSlots) {
      nulls += source_.cell(slot).is_null(row) ? 1U : 0U;
    }
    if (nulls == kNullPatternSlots.size()) {
      ++sentinel_rows_;
      continue;
    }
    if (nulls != 0) {
      return source_.refuse<bool>(
          Refusal(RefusalCode::CONTENT_MISMATCH, kRowSite,
                  "row mixes null and non-null NBBO fields", row),
          day_);
    }

    // 2. ORDER. The equal-time group machine's precondition is a non-decreasing
    //    tape, and the corpus refuses a descent rather than sorting it into
    //    silence (`reader.rs:895-901`).
    Expected<std::int64_t, Refusal> timestamp =
        cell_i64(source_.cell(kQuoteSlotTimestamp), source_.form(kQuoteSlotTimestamp), row);
    if (!timestamp.has_value()) {
      return source_.refuse<bool>(timestamp.error(), day_);
    }
    const std::int64_t ts_ms = timestamp.value();
    if (has_last_ts_ && ts_ms < last_ts_ms_) {
      return source_.refuse<bool>(
          Refusal(RefusalCode::OUT_OF_ORDER, kRowSite, "quote tape descends in time", ts_ms), day_);
    }
    last_ts_ms_ = ts_ms;
    has_last_ts_ = true;

    // 3. THE RTH WINDOW, applied in FRAME B before any conversion.
    if (ts_ms < source_.open_ms_b() || ts_ms >= source_.close_ms_b()) {
      continue;
    }
    ++rth_rows_;

    StockQuoteRow built;
    built.ts_ms_b = ts_ms;
    const std::array<std::size_t, 2> price_slots{kQuoteSlotBid, kQuoteSlotAsk};
    std::array<std::int64_t, 2> prices{0, 0};
    for (std::size_t index = 0; index < price_slots.size(); ++index) {
      const std::size_t slot = price_slots[index];
      Expected<std::int64_t, Refusal> value =
          cell_u6(source_.cell(slot), source_.form(slot), row);
      if (!value.has_value()) {
        return source_.refuse<bool>(value.error(), day_);
      }
      prices[index] = value.value();
    }
    built.bid_u6 = prices[0];
    built.ask_u6 = prices[1];

    const std::array<std::size_t, 2> size_slots{kQuoteSlotBidSize, kQuoteSlotAskSize};
    std::array<std::int64_t, 2> sizes{0, 0};
    for (std::size_t index = 0; index < size_slots.size(); ++index) {
      const std::size_t slot = size_slots[index];
      Expected<std::int64_t, Refusal> raw = cell_i64(source_.cell(slot), source_.form(slot), row);
      if (!raw.has_value()) {
        return source_.refuse<bool>(raw.error(), day_);
      }
      // THE ERA LAW, folded at the reader boundary so no family ever sees a
      // 100x step (synthetic-fixture-only in this scope: s749 is well before
      // the 2025-11-03 break).
      Expected<std::int64_t, Refusal> shares = nbbo_size_to_shares(raw.value(), day_);
      if (!shares.has_value()) {
        return source_.refuse<bool>(shares.error(), day_);
      }
      sizes[index] = shares.value();
    }
    built.bid_shares = sizes[0];
    built.ask_shares = sizes[1];

    const std::array<std::size_t, 4> int_slots{kQuoteSlotBidExchange, kQuoteSlotBidCondition,
                                               kQuoteSlotAskExchange, kQuoteSlotAskCondition};
    std::array<std::int64_t, 4> ints{0, 0, 0, 0};
    for (std::size_t index = 0; index < int_slots.size(); ++index) {
      Expected<std::int64_t, Refusal> value =
          read_nullable_int(source_, int_slots[index], row, built.null_mask);
      if (!value.has_value()) {
        return source_.refuse<bool>(value.error(), day_);
      }
      ints[index] = value.value();
    }
    built.bid_exchange = ints[0];
    built.bid_condition = ints[1];
    built.ask_exchange = ints[2];
    built.ask_condition = ints[3];

    tape_.push(built);
  }
  tape_.end_chunk(end_of_session);
  if (end_of_session) {
    exhausted_ = true;
  }
  return true;
}

FileExpected<bool> StockQuoteReader::next_group(Group& out) {
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
