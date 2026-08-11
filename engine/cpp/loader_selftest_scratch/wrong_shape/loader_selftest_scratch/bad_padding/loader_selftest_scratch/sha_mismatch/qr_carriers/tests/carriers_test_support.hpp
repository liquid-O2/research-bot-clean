// Shared support for the qr_carriers (WP8a) suite.
//
// THE TAPES ARE HAND-BUILT ROWS, NOT FILES. WP8a's object is the channel and
// summary construction; the file boundary below it is WP4's and WP5's, already
// fixtured and already gated. Every tape is clocked by the REAL authenticated
// registry session 125, so the frame-B -> frame-A conversion under test is the
// production one and never a stub.
//
// EVERY EXPECTED VALUE IN THIS SUITE IS A HAND LITERAL WITH ITS ARITHMETIC IN A
// COMMENT. Nothing is compared against the code's own output, and no expected
// value is computed by calling the function under test with different arguments.
#ifndef QR_CARRIERS_TESTS_SUPPORT_HPP
#define QR_CARRIERS_TESTS_SUPPORT_HPP

#include <gtest/gtest.h>

#include <cstdint>
#include <cstring>
#include <initializer_list>
#include <string_view>
#include <utility>
#include <vector>

#include "qr_carriers/channels.hpp"
#include "qr_carriers/streams.hpp"
#include "qr_clock/session_clock.hpp"
#include "qr_registry/registry.hpp"
#include "qr_sources/option_prints.hpp"
#include "qr_sources/stock_quotes.hpp"
#include "qr_sources/stock_trades.hpp"

namespace qr::carriers::testing {

/// Session 125 — the one authorized development session.
inline constexpr std::string_view kSession125Day = "2022-07-05";

inline const Registry& registry() {
  static const Registry loaded = [] {
    auto result = Registry::load_embedded();
    if (!result.has_value()) {
      detail::fail_fast("carrier fixtures: the embedded registry failed its digest gate");
    }
    return std::move(result).value();
  }();
  return loaded;
}

inline const SessionClock& clock_125() {
  static const SessionClock built = [] {
    auto date = CivilDate::parse_ymd(kSession125Day);
    if (!date.has_value()) {
      detail::fail_fast("carrier fixtures: session-125 day is not a canonical civil date");
    }
    auto clock = SessionClock::for_day(registry(), date.value());
    if (!clock.has_value()) {
      detail::fail_fast("carrier fixtures: the registry refused session 125");
    }
    return std::move(clock).value();
  }();
  return built;
}

/// Frame-B millisecond of session 125's 09:30 open — the anchor every hand tape
/// expresses its timestamps as an offset from.
inline std::int64_t open_ms() {
  return clock_125().open_b().ns() / kNanosecondsPerMillisecond;
}

/// Frame-A nanosecond of a frame-B offset, through the production clock.
inline std::int64_t frame_a_of(std::int64_t offset_ms) {
  auto converted = clock_125().to_frame_a(FrameB{(open_ms() + offset_ms) * kNanosecondsPerMillisecond});
  if (!converted.has_value()) {
    detail::fail_fast("carrier fixtures: a fixture offset left the RTH window");
  }
  return converted.value().ns();
}

// ---------------------------------------------------------------------------
// Row builders.
// ---------------------------------------------------------------------------

/// One stock print with a complete attached quote block. Prices are u6, sizes
/// are shares, conditions are the production allowlist's codes.
inline qr::sources::StockTradeRow trade_row(std::int64_t ts_ms_b, std::int64_t price_u6,
                                            std::int64_t size, std::int64_t quote_ts_ms_b,
                                            std::int64_t bid_u6, std::int64_t ask_u6,
                                            std::int64_t bid_shares, std::int64_t ask_shares,
                                            std::int64_t sequence = 0) {
  qr::sources::StockTradeRow row;
  row.ts_ms_b = ts_ms_b;
  row.quote_ts_ms_b = quote_ts_ms_b;
  row.sequence = sequence;
  row.ext_condition = {255, 255, 255, 255};  // all four slots absent at the sentinel
  row.condition = 0;                          // REGULAR
  row.size = size;
  row.exchange = 0;
  row.price_u6 = price_u6;
  row.bid_u6 = bid_u6;
  row.ask_u6 = ask_u6;
  row.bid_shares = bid_shares;
  row.ask_shares = ask_shares;
  row.bid_condition = 0;
  row.ask_condition = 0;
  return row;
}

inline qr::sources::StockQuoteRow quote_row(std::int64_t ts_ms_b, std::int64_t bid_u6,
                                            std::int64_t ask_u6, std::int64_t bid_shares,
                                            std::int64_t ask_shares) {
  qr::sources::StockQuoteRow row;
  row.ts_ms_b = ts_ms_b;
  row.bid_u6 = bid_u6;
  row.ask_u6 = ask_u6;
  row.bid_shares = bid_shares;
  row.ask_shares = ask_shares;
  row.bid_condition = 0;
  row.ask_condition = 0;
  return row;
}

/// One option print with both attachments present and every Greek finite.
/// `underlying_ts_text` is the naive-ET frame-B ISO-8601 ms text the compact
/// profile stores; the parse of it is WP8a's own, by the WP4 ruling.
inline qr::sources::OptionPrintRow option_row(std::int64_t ts_ms_b, std::int64_t price_u6,
                                              std::int64_t size, qr::sources::Right right,
                                              std::int64_t strike_u6, std::int32_t expiration_day,
                                              std::int64_t quote_ts_ms_b, std::int64_t bid_u6,
                                              std::int64_t ask_u6,
                                              std::string_view underlying_ts_text,
                                              double underlying_price, std::int64_t sequence = 0) {
  qr::sources::OptionPrintRow row;
  row.ts_ms_b = ts_ms_b;
  row.quote_ts_ms_b = quote_ts_ms_b;
  row.sequence = sequence;
  row.condition = 18;  // single-leg
  row.size = size;
  row.price_u6 = price_u6;
  row.strike_u6 = strike_u6;
  row.bid_u6 = bid_u6;
  row.ask_u6 = ask_u6;
  row.bid_size = 10;
  row.ask_size = 20;
  row.delta = 0.5;
  row.gamma = 0.25;
  row.vanna = 0.125;
  row.charm = -0.0625;
  row.implied_vol = 0.2;
  row.underlying_price = underlying_price;
  auto text = qr::sources::inline_text(underlying_ts_text);
  if (!text.has_value()) {
    detail::fail_fast("carrier fixtures: underlying timestamp text does not fit inline");
  }
  row.underlying_ts_text = text.value();
  row.expiration_day = expiration_day;
  row.right = right;
  return row;
}

template <class Row>
inline std::vector<Row> rows_of(std::initializer_list<Row> rows) {
  return std::vector<Row>(rows);
}

/// Byte-level serialization of a channel row, for the permutation control's
/// "every output bit" comparison. Values are compared as their exact IEEE-754
/// bit patterns, never with a tolerance.
template <std::size_t N>
inline std::vector<std::uint8_t> serialize(const ChannelRow<N>& row) {
  std::vector<std::uint8_t> out;
  out.reserve(N * 9);
  for (std::size_t index = 0; index < N; ++index) {
    std::uint64_t bits = 0;
    static_assert(sizeof(bits) == sizeof(double));
    std::memcpy(&bits, &row.value[index], sizeof(bits));
    for (unsigned shift = 0; shift < 64; shift += 8) {
      out.push_back(static_cast<std::uint8_t>((bits >> shift) & 0xFFU));
    }
    out.push_back(static_cast<std::uint8_t>(row.validity[index]));
  }
  return out;
}

/// The same for a reduced group record.
inline std::vector<std::uint8_t> serialize(const GroupRecord& group) {
  std::vector<std::uint8_t> out;
  const auto push_i64 = [&out](std::int64_t value) {
    const std::uint64_t bits = static_cast<std::uint64_t>(value);
    for (unsigned shift = 0; shift < 64; shift += 8) {
      out.push_back(static_cast<std::uint8_t>((bits >> shift) & 0xFFU));
    }
  };
  const auto push_double = [&out](double value) {
    std::uint64_t bits = 0;
    std::memcpy(&bits, &value, sizeof(bits));
    for (unsigned shift = 0; shift < 64; shift += 8) {
      out.push_back(static_cast<std::uint8_t>((bits >> shift) & 0xFFU));
    }
  };
  push_i64(group.ts_ns_a);
  push_i64(group.token_count);
  push_i64(group.absent_value_cells);
  push_i64(group.unusable_attachment_tokens);
  out.push_back(group.sequence_group_valid ? 1U : 0U);
  out.push_back(group.sequence_pair ? 1U : 0U);
  out.push_back(group.sequence_inversion ? 1U : 0U);
  out.push_back(group.has_gap ? 1U : 0U);
  push_double(group.log1p_multiplicity);
  push_double(group.log1p_gap_micros);
  for (std::size_t index = 0; index < kMechanismCount; ++index) {
    push_double(group.mechanism_long[index]);
    push_double(group.mechanism_short[index]);
  }
  out.push_back(group.mechanism_present_long);
  out.push_back(group.mechanism_present_short);
  return out;
}

}  // namespace qr::carriers::testing

#endif  // QR_CARRIERS_TESTS_SUPPORT_HPP
