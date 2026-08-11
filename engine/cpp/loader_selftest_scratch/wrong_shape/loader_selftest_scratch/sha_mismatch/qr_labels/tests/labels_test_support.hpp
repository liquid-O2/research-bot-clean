// Shared support for the qr_labels suite.
//
// The micro-tapes here are HAND-BUILT ROWS with HAND-COMPUTED expectations, not
// files: WP7's object is the watch/label kernel, and the file boundary below it
// belongs to WP4/WP5, already fixtured and already gated. Every tape is clocked
// by the REAL authenticated registry session 125, so the frame-B -> frame-A
// conversion under test is the production one and not a stub.
//
// THE ARITHMETIC IS CHOSEN SO THE READER CAN CHECK IT BY HAND. Every fixture
// fills at exactly 1,000,000 u6 ($1.00), which makes `frac_u6` equal the price
// move in u6 units and therefore
//
//     net_cent = move_u6 * 10 - 576
//
// so the wall (-30,000c) sits at move -2,943 (net -30,006; the previous
// reachable net is -29,996 at move -2,942), the favorable barrier (+5,000c) at
// move +558 (net +5,004) and the adverse barrier (-5,000c) at move -443 (net
// -5,006). Those five numbers appear as literals in the tests.
#ifndef QR_LABELS_TESTS_SUPPORT_HPP
#define QR_LABELS_TESTS_SUPPORT_HPP

#include <gtest/gtest.h>

#include <cstdint>
#include <initializer_list>
#include <span>
#include <string>
#include <vector>

#include "fixture_support.hpp"
#include "qr_clock/session_clock.hpp"
#include "qr_labels/execution_tape.hpp"
#include "qr_labels/label_kernel.hpp"
#include "qr_labels/watches.hpp"
#include "qr_sources/stock_quotes.hpp"

namespace qr::labels::testing {

using qr::sources::StockQuoteRow;

/// The fill every fixture uses: $1.00 in u6.
inline constexpr std::int64_t kFill = 1'000'000;
/// The move whose net is the first at or below the -30,000c wall (-30,006).
inline constexpr std::int64_t kWallMove = -2'943;
/// The move whose net is the last one ABOVE the wall (-29,996).
inline constexpr std::int64_t kJustAboveWallMove = -2'942;
/// The move whose net first reaches the +5,000c favorable barrier (+5,004).
inline constexpr std::int64_t kFavorableBarrierMove = 558;
/// The move whose net first reaches the -5,000c adverse barrier (-5,006).
inline constexpr std::int64_t kAdverseBarrierMove = -443;

/// The hand arithmetic itself, so a test can state the expectation without
/// repeating the formula: net of a price move against the $1.00 fill.
[[nodiscard]] inline constexpr std::int64_t net_of_move(std::int64_t move_u6) {
  return move_u6 * 10 - 576;
}

/// The session-125 clock, from the frozen registry row.
inline SessionClock clock_125() {
  const auto scope = qr::sources::testing::scope_125();
  EXPECT_TRUE(scope.has_value()) << "the registry refused session 125";
  Expected<SessionClock, Refusal> clock = SessionClock::from_session(scope->session());
  EXPECT_TRUE(clock.has_value());
  return clock.value();
}

/// Frame-B millisecond of session 125's open: the anchor every micro-tape
/// offset is measured from.
inline std::int64_t open_ms_125() { return clock_125().open_b().ns() / kNanosecondsPerMillisecond; }

/// One NBBO row. Sizes are SHARES and prices u6 (WP4 has already folded the
/// profile and the lot/share era).
inline StockQuoteRow quote_row(std::int64_t ts_ms_b, std::int64_t bid_u6, std::int64_t ask_u6,
                               std::int64_t bid_shares = 100, std::int64_t ask_shares = 100,
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

/// One equal-millisecond group of a micro-tape.
struct MicroGroup {
  std::int64_t ms_offset = 0;
  std::vector<StockQuoteRow> rows;
};

/// A single-member group at `ms_offset` quoting `bid`/`ask`.
inline MicroGroup group_at(std::int64_t ms_offset, std::int64_t bid_u6, std::int64_t ask_u6) {
  return MicroGroup{ms_offset, {quote_row(open_ms_125() + ms_offset, bid_u6, ask_u6)}};
}

/// A group whose members are given explicitly (the equal-ms envelope fixtures).
inline MicroGroup group_of(std::int64_t ms_offset,
                           std::initializer_list<std::pair<std::int64_t, std::int64_t>> quotes) {
  MicroGroup group;
  group.ms_offset = ms_offset;
  for (const auto& [bid, ask] : quotes) {
    group.rows.push_back(quote_row(open_ms_125() + ms_offset, bid, ask));
  }
  return group;
}

/// Builds a sealed execution tape from micro-groups, through the production
/// builder and the production clock.
///
/// A REFUSAL IS A TEST FAILURE, NEVER AN ABORT: `Expected::value()` on a
/// refusal fails fast by design, which would kill the whole binary and leave
/// the red-ledger run unable to enumerate what went red. Every helper here
/// records the failure and returns an empty-but-valid object instead.
inline ExecutionTape tape_of(const std::vector<MicroGroup>& groups) {
  ExecutionTapeBuilder builder = ExecutionTapeBuilder::from_clock(clock_125(), 125);
  for (const MicroGroup& group : groups) {
    const Expected<bool, Refusal> pushed =
        builder.push_group(open_ms_125() + group.ms_offset, group.rows);
    if (!pushed.has_value()) {
      ADD_FAILURE() << "push_group refused: " << pushed.error().message();
      return ExecutionTape{};
    }
  }
  Expected<ExecutionTape, Refusal> sealed = builder.seal();
  if (!sealed.has_value()) {
    ADD_FAILURE() << "seal refused: " << sealed.error().message();
    return ExecutionTape{};
  }
  return std::move(sealed).value();
}

inline SessionLabelIndex index_of(const std::vector<MicroGroup>& groups) {
  return SessionLabelIndex::build(tape_of(groups));
}

/// An action key at the session-125 frame-A instant `session_start + ns`.
inline ActionKey key_at(std::int64_t offset_ns, Side side, std::int64_t ordinal = 7) {
  ActionKey key;
  key.session_ordinal = 125;
  key.decision_ordinal = ordinal;
  key.decision_ts_ns = clock_125().session_start_a().ns() + offset_ns;
  key.side = side;
  return key;
}

/// `label_action`, with the test's own failure message on a refusal.
inline LabelRow label_or_fail(const SessionLabelIndex& index, ActionKey key, Side side,
                              std::int64_t wall = kStopWallNetCent) {
  Expected<LabelRow, Refusal> row = label_action(index, key, side, wall);
  if (!row.has_value()) {
    ADD_FAILURE() << "label_action refused: " << row.error().message();
    return LabelRow{};
  }
  return std::move(row).value();
}

/// The value of an `Expected`, or a recorded failure and `fallback`.
template <class T>
inline T value_or_fail(const Expected<T, Refusal>& expected, T fallback) {
  if (!expected.has_value()) {
    ADD_FAILURE() << "refused: " << expected.error().message();
    return fallback;
  }
  return expected.value();
}

// ---------------------------------------------------------------------------
// THE LINEAR REFERENCE.
// ---------------------------------------------------------------------------

/// A deliberately naive re-implementation of the whole kernel: it walks every
/// lawful mark one at a time, computes every net with `mark_net_cent`, and
/// knows nothing about price gates or segment trees. The production kernel must
/// agree with it byte for byte on every fixture and on a pseudo-random tape —
/// this is the "validate the optimized algorithm against a simple linear
/// reference ... require byte-identical labels" rule the frozen kernel states
/// (transcripts/CONVERSATION.md:24089-24091).
inline LabelRow linear_reference_label(const ExecutionTape& tape, ActionKey key, Side side,
                                       std::int64_t wall = kStopWallNetCent) {
  LabelRow row;
  row.menu.key = key;
  row.menu.cost_charged_cent = kTradeCostCent;

  std::int64_t entry = kNoIndex;
  for (std::int64_t index = 0; index < tape.size(); ++index) {
    if (tape.ts_ns[static_cast<std::size_t>(index)] > key.decision_ts_ns) {
      entry = index;
      break;
    }
  }
  if (entry == kNoIndex) {
    row.menu.state = LabelState::ENTRY_UNAVAILABLE;
    return row;
  }
  row.entry_index = entry;
  row.menu.entry_ts_ns = tape.ts_ns[static_cast<std::size_t>(entry)];
  const std::int64_t fill = tape.entry_price(entry, side);
  row.entry_u6 = fill;
  const std::int64_t last = tape.size() - 1;
  if (entry >= last) {
    row.menu.state = LabelState::EXIT_UNAVAILABLE;
    return row;
  }

  const auto net_at = [&](std::int64_t index) {
    return mark_net_cent(fill, tape.adverse_mark(index, side), side).value();
  };
  const auto mae_over = [&](std::int64_t lo, std::int64_t hi) {
    std::int64_t worst = net_at(lo);
    for (std::int64_t index = lo + 1; index <= hi; ++index) {
      worst = std::min(worst, net_at(index));
    }
    return worst < 0 ? -worst : 0;
  };

  std::int64_t crossing = kNoIndex;
  for (std::int64_t index = entry + 1; index <= last; ++index) {
    if (net_at(index) <= wall) {
      crossing = index;
      break;
    }
  }
  row.scan.wall_net_cent = wall;
  row.scan.crossed = crossing != kNoIndex;
  row.scan.crossing_index = crossing;
  if (crossing != kNoIndex) {
    row.scan.crossing_net_cent = net_at(crossing);
    row.scan.crossing_ts_ns = tape.ts_ns[static_cast<std::size_t>(crossing)];
    row.scan.exit_index = crossing < last ? crossing + 1 : kNoIndex;
    const std::int64_t fill_index = row.scan.exit_index != kNoIndex ? row.scan.exit_index : crossing;
    row.scan.exit_net_cent = net_at(fill_index);
    row.scan.exit_ts_ns = tape.ts_ns[static_cast<std::size_t>(fill_index)];
    row.scan.gap_through_cent =
        row.scan.exit_net_cent < wall ? wall - row.scan.exit_net_cent : 0;
  }

  for (std::size_t horizon = 0; horizon < kHorizonCount; ++horizon) {
    std::int64_t target = last;
    if (kHorizonMinutes[horizon] >= 0) {
      const std::int64_t deadline =
          row.menu.entry_ts_ns + kHorizonMinutes[horizon] * kNanosecondsPerMinute;
      target = last;
      for (std::int64_t index = entry; index <= last; ++index) {
        if (tape.ts_ns[static_cast<std::size_t>(index)] >= deadline) {
          target = index;
          break;
        }
      }
    }
    std::int64_t exit = target;
    bool stopped = false;
    if (crossing != kNoIndex && crossing < target) {
      exit = crossing + 1;
      stopped = true;
    }
    row.menu.menu_net_cent[horizon] = net_at(exit);
    row.menu.menu_mae_cent[horizon] = mae_over(entry, exit);
    row.menu.menu_exit_ts[horizon] = tape.ts_ns[static_cast<std::size_t>(exit)];
    row.menu.stop_hit[horizon] = stopped ? 1U : 0U;
  }

  const std::int64_t window_hi = crossing != kNoIndex ? crossing - 1 : last;
  std::int64_t certificate = kNoIndex;
  std::int64_t best = 0;
  for (std::int64_t index = entry + 1; index <= window_hi; ++index) {
    const std::int64_t net = net_at(index);
    if (certificate == kNoIndex || net > best) {
      certificate = index;
      best = net;
    }
  }
  if (certificate == kNoIndex || best <= 0) {
    certificate = crossing != kNoIndex ? (crossing < last ? crossing + 1 : last) : last;
  }
  row.certificate_exit_index = certificate;
  row.certificate_exit_ts_ns = tape.ts_ns[static_cast<std::size_t>(certificate)];
  row.certificate_net_cent = net_at(certificate);
  row.certificate_mae_cent = mae_over(entry, certificate);

  std::int64_t favorable = kNoIndex;
  std::int64_t adverse = kNoIndex;
  for (std::int64_t index = entry + 1; index <= last; ++index) {
    if (favorable == kNoIndex &&
        mark_net_cent(fill, tape.favorable_mark(index, side), side).value() >= kBarrierNetCent) {
      favorable = index;
    }
    if (adverse == kNoIndex && net_at(index) <= -kBarrierNetCent) {
      adverse = index;
    }
  }
  row.barrier.favorable_index = favorable;
  row.barrier.adverse_index = adverse;
  if (favorable == kNoIndex && adverse == kNoIndex) {
    row.barrier.state = BarrierState::NEITHER;
  } else if (adverse == kNoIndex || (favorable != kNoIndex && favorable < adverse)) {
    row.barrier.state = BarrierState::FAVORABLE_FIRST;
  } else if (favorable == kNoIndex || adverse < favorable) {
    row.barrier.state = BarrierState::ADVERSE_FIRST;
  } else {
    row.barrier.state = BarrierState::SAME_GROUP_ADVERSE;
  }
  row.barrier.three_class = barrier_three_class(row.barrier.state);
  std::int64_t first_touch = kNoIndex;
  if (favorable != kNoIndex && adverse != kNoIndex) {
    first_touch = std::min(favorable, adverse);
  } else if (favorable != kNoIndex) {
    first_touch = favorable;
  } else if (adverse != kNoIndex) {
    first_touch = adverse;
  }
  row.barrier.first_touch_ts_ns =
      first_touch == kNoIndex ? 0 : tape.ts_ns[static_cast<std::size_t>(first_touch)];
  row.menu.state = LabelState::OK;
  return row;
}

/// The serialized bytes of one label row (the differential's comparison unit).
inline std::vector<std::uint8_t> bytes_of(const LabelRow& row) {
  std::vector<std::uint8_t> out;
  append_serialized(row, out);
  return out;
}

/// A deterministic 64-bit LCG, so the pseudo-random tapes are the same bytes on
/// every run and on every machine (no <random>, whose engines are free to
/// differ across implementations).
class Lcg {
 public:
  explicit Lcg(std::uint64_t seed) noexcept : state_(seed) {}
  std::uint64_t next() noexcept {
    state_ = state_ * 6364136223846793005ULL + 1442695040888963407ULL;
    return state_;
  }
  /// A value in [lo, hi].
  std::int64_t between(std::int64_t lo, std::int64_t hi) noexcept {
    const auto span = static_cast<std::uint64_t>(hi - lo + 1);
    return lo + static_cast<std::int64_t>(next() % span);
  }

 private:
  std::uint64_t state_;
};

}  // namespace qr::labels::testing

#endif  // QR_LABELS_TESTS_SUPPORT_HPP
