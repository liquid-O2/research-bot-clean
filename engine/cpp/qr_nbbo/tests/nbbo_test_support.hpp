// Shared support for the qr_nbbo suite.
//
// The micro-tapes here are HAND-BUILT ROWS, not files: WP5's object is the
// group state machine, and the file boundary below it is WP4's, already
// fixtured and already gated. Every tape is clocked by a REAL authenticated
// registry session (125), so the frame-B -> frame-A conversion under test is
// the production one and not a stub.
#ifndef QR_NBBO_TESTS_SUPPORT_HPP
#define QR_NBBO_TESTS_SUPPORT_HPP

#include <gtest/gtest.h>

#include <cstdint>
#include <string>
#include <vector>

#include "fixture_support.hpp"
#include "qr_clock/session_clock.hpp"
#include "qr_nbbo/group_machine.hpp"
#include "qr_sources/stock_quotes.hpp"

namespace qr::nbbo::testing {

using qr::sources::StockQuoteRow;

/// The session-125 clock, built from the frozen registry row.
inline SessionClock clock_125() {
  const auto scope = qr::sources::testing::scope_125();
  EXPECT_TRUE(scope.has_value()) << "the registry refused session 125";
  Expected<SessionClock, Refusal> clock = SessionClock::from_session(scope->session());
  EXPECT_TRUE(clock.has_value());
  return clock.value();
}

/// Frame-B millisecond of session 125's open — the anchor every micro-tape
/// timestamp is expressed as an offset from.
inline std::int64_t open_ms_125() { return clock_125().open_b().ns() / kNanosecondsPerMillisecond; }

/// Pins for a hand-built tape: the counts the tape itself must reproduce, so
/// `seal()` exercises the registry oracle on every micro-tape too.
inline SessionPins pins_for(std::int64_t rows, std::int64_t groups,
                            SourceProfile profile = SourceProfile::CentInt32) {
  SessionPins pins;
  pins.day = qr::sources::testing::kSession125Day;
  pins.profile = profile;
  pins.raw_rth_row_count = rows;
  pins.complete_group_count = groups;
  return pins;
}

/// One NBBO row. Sizes are SHARES and prices are u6 — WP4's reader boundary
/// has already folded the profile and the lot/share era, so nothing below it
/// knows either exists.
inline StockQuoteRow quote_row(std::int64_t ts_ms_b, std::int64_t bid_u6, std::int64_t ask_u6,
                               std::int64_t bid_shares, std::int64_t ask_shares,
                               std::int64_t bid_condition = 0, std::int64_t ask_condition = 0) {
  StockQuoteRow row;
  row.ts_ms_b = ts_ms_b;
  row.bid_u6 = bid_u6;
  row.ask_u6 = ask_u6;
  row.bid_shares = bid_shares;
  row.ask_shares = ask_shares;
  row.bid_condition = bid_condition;
  row.ask_condition = ask_condition;
  return row;
}

/// Marks projection slot `slot` null on `row` (the WP4 mask law: an absent
/// field is a MASK BIT and the value stays 0, never a sentinel).
inline StockQuoteRow with_null(StockQuoteRow row, std::size_t slot) {
  row.null_mask = static_cast<std::uint16_t>(row.null_mask | (1U << slot));
  return row;
}

/// A one-off row list, for the single-group refusal fixtures. `push_group`
/// takes a span, and a braced list is not one.
inline std::vector<StockQuoteRow> rows_of(std::initializer_list<StockQuoteRow> rows) {
  return std::vector<StockQuoteRow>(rows);
}

/// One equal-millisecond group of a micro-tape.
struct TapeGroup {
  std::int64_t ts_ms_b = 0;
  std::vector<StockQuoteRow> rows;
};

/// Feeds a whole tape through a machine and seals it. Returns the seal's
/// result so a test can assert on the registry oracle directly.
inline Expected<std::int64_t, Refusal> run_tape(GroupMachine& machine,
                                                const std::vector<TapeGroup>& tape,
                                                std::int64_t sentinel_rows = 1) {
  for (const TapeGroup& group : tape) {
    const Expected<std::int64_t, Refusal> pushed = machine.push_group(group.ts_ms_b, group.rows);
    if (!pushed.has_value()) {
      return Expected<std::int64_t, Refusal>::refuse(pushed.error());
    }
  }
  return machine.seal(sentinel_rows);
}

}  // namespace qr::nbbo::testing

#endif  // QR_NBBO_TESTS_SUPPORT_HPP
