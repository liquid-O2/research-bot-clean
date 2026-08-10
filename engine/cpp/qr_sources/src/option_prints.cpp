#include "qr_sources/option_prints.hpp"

#include <array>
#include <string>

#include "qr_clock/session_clock.hpp"

namespace qr::sources {
namespace {

constexpr const char* kOpenSite = "qr_sources::OptionPrintReader::open";
constexpr const char* kRowSite = "qr_sources::OptionPrintReader::row";

}  // namespace

bool canonical_less(const OptionPrintRow& left, const OptionPrintRow& right) noexcept {
  if (left.ts_ms_b != right.ts_ms_b) return left.ts_ms_b < right.ts_ms_b;
  if (left.expiration_day != right.expiration_day) return left.expiration_day < right.expiration_day;
  if (left.strike_u6 != right.strike_u6) return left.strike_u6 < right.strike_u6;
  if (left.right != right.right) return left.right < right.right;
  if (left.sequence != right.sequence) return left.sequence < right.sequence;
  if (left.condition != right.condition) return left.condition < right.condition;
  if (left.size != right.size) return left.size < right.size;
  if (left.price_u6 != right.price_u6) return left.price_u6 < right.price_u6;
  // Doubles compare by BIT PATTERN: `<` is not a total order on doubles (NaN
  // compares false against everything), and std::sort needs a strict weak
  // ordering or it is undefined behaviour.
  const std::array<double, 6> left_reals{left.delta,       left.gamma,       left.vanna,
                                         left.charm,       left.implied_vol, left.underlying_price};
  const std::array<double, 6> right_reals{right.delta,       right.gamma,       right.vanna,
                                          right.charm,       right.implied_vol,
                                          right.underlying_price};
  for (std::size_t index = 0; index < left_reals.size(); ++index) {
    const std::uint64_t left_bits = double_bits(left_reals[index]);
    const std::uint64_t right_bits = double_bits(right_reals[index]);
    if (left_bits != right_bits) {
      return left_bits < right_bits;
    }
  }
  if (left.bid_u6 != right.bid_u6) return left.bid_u6 < right.bid_u6;
  if (left.ask_u6 != right.ask_u6) return left.ask_u6 < right.ask_u6;
  if (left.bid_size != right.bid_size) return left.bid_size < right.bid_size;
  if (left.ask_size != right.ask_size) return left.ask_size < right.ask_size;
  if (left.quote_ts_ms_b != right.quote_ts_ms_b) return left.quote_ts_ms_b < right.quote_ts_ms_b;
  if (!(left.underlying_ts_text == right.underlying_ts_text)) {
    return left.underlying_ts_text.view() < right.underlying_ts_text.view();
  }
  return left.null_mask < right.null_mask;
}

void append_serialized(const OptionPrintRow& row, std::vector<std::uint8_t>& out) {
  append_i32(row.expiration_day, out);
  append_i64(row.strike_u6, out);
  append_u8(static_cast<std::uint8_t>(row.right), out);
  append_i64(row.ts_ms_b, out);
  append_i64(row.sequence, out);
  append_i64(row.condition, out);
  append_i64(row.size, out);
  append_i64(row.price_u6, out);
  append_f64(row.delta, out);
  append_f64(row.gamma, out);
  append_f64(row.vanna, out);
  append_f64(row.charm, out);
  append_f64(row.implied_vol, out);
  append_text(row.underlying_ts_text.view(), out);
  append_f64(row.underlying_price, out);
  append_i64(row.bid_u6, out);
  append_i64(row.bid_size, out);
  append_i64(row.ask_u6, out);
  append_i64(row.ask_size, out);
  append_i64(row.quote_ts_ms_b, out);
  append_i64(static_cast<std::int64_t>(row.null_mask), out);
}

void OptionPrintDigests::fold(const OptionPrintRow& row) noexcept {
  // Slot order is projection order (B3's ADDENDUM 20), so a digest row can be
  // read straight against the appendix.
  const std::array<std::int64_t, 20> integers{
      static_cast<std::int64_t>(row.expiration_day),
      row.strike_u6,
      static_cast<std::int64_t>(row.right),
      row.ts_ms_b,
      row.sequence,
      row.condition,
      row.size,
      row.price_u6,
      0, 0, 0, 0, 0, 0, 0,  // the six reals and the text slot fold below
      row.bid_u6,
      row.bid_size,
      row.ask_u6,
      row.ask_size,
      row.quote_ts_ms_b};
  const std::array<double, 6> reals{row.delta, row.gamma,       row.vanna,
                                    row.charm, row.implied_vol, row.underlying_price};
  constexpr std::array<std::size_t, 6> kRealSlots{kPrintSlotDelta,      kPrintSlotGamma,
                                                  kPrintSlotVanna,      kPrintSlotCharm,
                                                  kPrintSlotImpliedVol, kPrintSlotUnderlyingPrice};
  for (std::size_t slot = 0; slot < field.size(); ++slot) {
    if (row.is_null(slot)) {
      field[slot].add_null();
      continue;
    }
    if (slot == kPrintSlotUnderlyingTimestamp) {
      field[slot].add_text(row.underlying_ts_text.view());
      continue;
    }
    bool is_real = false;
    for (std::size_t index = 0; index < kRealSlots.size(); ++index) {
      if (kRealSlots[index] == slot) {
        field[slot].add_f64(reals[index]);
        is_real = true;
        break;
      }
    }
    if (!is_real) {
      field[slot].add_i64(integers[slot]);
    }
  }
}

std::string_view OptionPrintDigests::field_name(std::size_t slot) noexcept {
  static constexpr std::array<std::string_view, 20> kNames{
      "expiration_day", "strike_u6",   "right",       "ts_ms_b",       "sequence",
      "condition",      "size",        "price_u6",    "delta",         "gamma",
      "vanna",          "charm",       "implied_vol", "underlying_ts_text",
      "underlying_price", "bid_u6",    "bid_size",    "ask_u6",        "ask_size",
      "quote_ts_ms_b"};
  return slot < kNames.size() ? kNames[slot] : std::string_view{"?"};
}

FileExpected<OptionPrintReader> OptionPrintReader::open(const DayScope& scope,
                                                        const std::filesystem::path& corpus_root) {
  const std::filesystem::path path = day_file(corpus_root, scope);
  Expected<SessionClock, Refusal> clock = SessionClock::from_session(scope.session());
  if (!clock.has_value()) {
    return parquet::refuse_file<OptionPrintReader>(clock.error().code(), kOpenSite,
                                                   "the session clock refuses this registry row",
                                                   path.string(), scope.day(), scope.ordinal());
  }
  const std::int64_t open_ms = clock.value().open_b().ns() / kNanosecondsPerMillisecond;
  const std::int64_t close_ms = clock.value().close_b().ns() / kNanosecondsPerMillisecond;

  FileExpected<SessionSource> source = SessionSource::open(
      path, view_of(kOptionPrintSpec), std::span<const ColumnForm>(kOptionPrintFormsIwmCompact),
      open_ms, close_ms);
  if (!source.has_value()) {
    return FileExpected<OptionPrintReader>::refuse(source.error());
  }
  return OptionPrintReader(std::move(source).value());
}

FileExpected<bool> OptionPrintReader::fill() {
  FileExpected<std::int64_t> decoded = source_.next_chunk();
  if (!decoded.has_value()) {
    return FileExpected<bool>::refuse(decoded.error());
  }
  const std::int64_t rows = decoded.value();
  const bool end_of_session = rows == 0;
  tape_.begin_chunk();
  for (std::int64_t row = 0; row < rows; ++row) {
    // ADMISSION (reference `options_prints.rs:298-300`): a print with no
    // instant cannot be placed on the clock. This is also where the compact
    // corpus's all-null sentinel row leaves the stream.
    if (source_.cell(kPrintSlotTimestamp).is_null(row)) {
      ++skipped_null_rows_;
      continue;
    }
    Expected<std::int64_t, Refusal> timestamp =
        cell_i64(source_.cell(kPrintSlotTimestamp), source_.form(kPrintSlotTimestamp), row);
    if (!timestamp.has_value()) {
      return source_.refuse<bool>(timestamp.error());
    }
    const std::int64_t ts_ms = timestamp.value();
    if (has_last_ts_ && ts_ms < last_ts_ms_) {
      return source_.refuse<bool>(
          Refusal(RefusalCode::OUT_OF_ORDER, kRowSite, "option print tape descends in time", ts_ms));
    }
    last_ts_ms_ = ts_ms;
    has_last_ts_ = true;
    if (ts_ms < source_.open_ms_b() || ts_ms >= source_.close_ms_b()) {
      continue;
    }
    ++rth_rows_;

    OptionPrintRow built;
    built.ts_ms_b = ts_ms;

    // expiration(1): a day ordinal in the compact profile, ISO text in the
    // wide one; either way the row carries the ordinal.
    if (source_.cell(kPrintSlotExpiration).is_null(row)) {
      built.null_mask |= std::uint32_t{1} << kPrintSlotExpiration;
    } else {
      Expected<std::int32_t, Refusal> expiration = cell_day_ordinal(
          source_.cell(kPrintSlotExpiration), source_.form(kPrintSlotExpiration), row);
      if (!expiration.has_value()) {
        return source_.refuse<bool>(expiration.error());
      }
      built.expiration_day = expiration.value();
    }

    // right(3): parsed to the frozen three-valued enum; an unknown token stays
    // Other rather than being folded into call or put.
    if (source_.cell(kPrintSlotRight).is_null(row)) {
      built.null_mask |= std::uint32_t{1} << kPrintSlotRight;
    } else {
      Expected<std::string_view, Refusal> text =
          cell_text(source_.cell(kPrintSlotRight), source_.form(kPrintSlotRight), row);
      if (!text.has_value()) {
        return source_.refuse<bool>(text.error());
      }
      built.right = parse_right(text.value());
    }

    // underlying_ts(36): retained VERBATIM, interpreted by nobody in WP4.
    if (source_.cell(kPrintSlotUnderlyingTimestamp).is_null(row)) {
      built.null_mask |= std::uint32_t{1} << kPrintSlotUnderlyingTimestamp;
    } else {
      Expected<std::string_view, Refusal> text =
          cell_text(source_.cell(kPrintSlotUnderlyingTimestamp),
                    source_.form(kPrintSlotUnderlyingTimestamp), row);
      if (!text.has_value()) {
        return source_.refuse<bool>(text.error());
      }
      Expected<InlineText, Refusal> retained = inline_text(text.value());
      if (!retained.has_value()) {
        return source_.refuse<bool>(retained.error());
      }
      built.underlying_ts_text = retained.value();
    }

    // strike(2) and the three prices (13, 39, 42), all normalized to u6.
    constexpr std::array<std::size_t, 4> kPriceSlots{kPrintSlotStrike, kPrintSlotPrice,
                                                     kPrintSlotBid, kPrintSlotAsk};
    std::array<std::int64_t, 4> prices{};
    for (std::size_t index = 0; index < kPriceSlots.size(); ++index) {
      Expected<std::int64_t, Refusal> value =
          read_nullable_u6(source_, kPriceSlots[index], row, built.null_mask);
      if (!value.has_value()) {
        return source_.refuse<bool>(value.error());
      }
      prices[index] = value.value();
    }
    built.strike_u6 = prices[0];
    built.price_u6 = prices[1];
    built.bid_u6 = prices[2];
    built.ask_u6 = prices[3];

    constexpr std::array<std::size_t, 6> kRealSlots{
        kPrintSlotDelta, kPrintSlotGamma, kPrintSlotVanna,
        kPrintSlotCharm, kPrintSlotImpliedVol, kPrintSlotUnderlyingPrice};
    std::array<double, 6> reals{};
    for (std::size_t index = 0; index < kRealSlots.size(); ++index) {
      Expected<double, Refusal> value =
          read_nullable_f64(source_, kRealSlots[index], row, built.null_mask);
      if (!value.has_value()) {
        return source_.refuse<bool>(value.error());
      }
      reals[index] = value.value();
    }
    built.delta = reals[0];
    built.gamma = reals[1];
    built.vanna = reals[2];
    built.charm = reals[3];
    built.implied_vol = reals[4];
    built.underlying_price = reals[5];

    constexpr std::array<std::size_t, 6> kIntSlots{kPrintSlotSequence, kPrintSlotCondition,
                                                   kPrintSlotSize,     kPrintSlotBidSize,
                                                   kPrintSlotAskSize,  kPrintSlotQuoteTimestamp};
    std::array<std::int64_t, 6> ints{};
    for (std::size_t index = 0; index < kIntSlots.size(); ++index) {
      Expected<std::int64_t, Refusal> value =
          read_nullable_int(source_, kIntSlots[index], row, built.null_mask);
      if (!value.has_value()) {
        return source_.refuse<bool>(value.error());
      }
      ints[index] = value.value();
    }
    built.sequence = ints[0];
    built.condition = ints[1];
    built.size = ints[2];
    built.bid_size = ints[3];
    built.ask_size = ints[4];
    built.quote_ts_ms_b = ints[5];

    tape_.push(built);
  }
  tape_.end_chunk(end_of_session);
  if (end_of_session) {
    exhausted_ = true;
  }
  return true;
}

FileExpected<bool> OptionPrintReader::next_group(Group& out) {
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
