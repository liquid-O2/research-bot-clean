// qr_carriers/tools/destruction_guard.hpp — THE PRODUCTION-PATH FINGERPRINT
// THAT THE DESTRUCTION FLAGS MAY NOT MOVE.
//
// SPEC: the WP8b brief's destruction guard — "destruction-flag off = production
// path byte-identical to a build WITHOUT the flag code compiled (guard:
// destructions cannot leak into production)" — which is the executable form of
// task card V4 section 7's "(e)/(f)" and FINAL_PLAN section 6's "destructions in
// the SAME constructors".
//
// HOW THE GUARD IS PROVED, AND WHY IT NEEDS TWO BINARIES. A flag that defaults
// to false is not evidence: the branch is still compiled, still reachable, and
// still able to perturb the production bytes through a mistake anywhere in its
// arithmetic. So `qr_carriers_nodestruct_probe` links a SECOND build of the
// carrier library compiled with `-DQR_CARRIERS_NO_DESTRUCTIONS`, in which the
// controls type and every use of it do not exist at all, and prints the
// fingerprint of the tape below. The ordinary test binary computes the same
// fingerprint through the ordinary library with the flags off. Equality of the
// two hexadecimal digests is the guard.
//
// WHY THIS HEADER CARRIES ITS OWN ROW BUILDERS. `tests/carriers_test_support.hpp`
// includes GoogleTest, and the no-destructions probe is a plain tool that must
// not link a test framework. The rows below are therefore built here, and they
// are deliberately dull: the guard's object is the PATH, not the arithmetic —
// every value law already has its own hand-literal fixture.
#ifndef QR_CARRIERS_TOOLS_DESTRUCTION_GUARD_HPP
#define QR_CARRIERS_TOOLS_DESTRUCTION_GUARD_HPP

#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

#include "qr_carriers/direct_raw.hpp"
#include "qr_carriers/native_order.hpp"
#include "qr_carriers/streams.hpp"
#include "qr_clock/session_clock.hpp"
#include "qr_registry/registry.hpp"

namespace qr::carriers::guard {

/// FNV-1a over every produced bit — the same digest shape the WP8a probe uses.
class Digest {
 public:
  void feed_u64(std::uint64_t bits) noexcept {
    for (unsigned shift = 0; shift < 64; shift += 8) {
      value_ ^= (bits >> shift) & 0xFFULL;
      value_ *= 0x100000001B3ULL;
    }
  }
  void feed_i64(std::int64_t value) noexcept { feed_u64(static_cast<std::uint64_t>(value)); }
  void feed_f32(float value) noexcept {
    std::uint32_t bits = 0;
    static_assert(sizeof(bits) == sizeof(float));
    std::memcpy(&bits, &value, sizeof(bits));
    feed_u64(bits);
  }
  void feed_f64(double value) noexcept {
    std::uint64_t bits = 0;
    static_assert(sizeof(bits) == sizeof(double));
    std::memcpy(&bits, &value, sizeof(bits));
    feed_u64(bits);
  }
  [[nodiscard]] std::uint64_t value() const noexcept { return value_; }
  [[nodiscard]] std::string hex() const {
    static const char* kDigits = "0123456789abcdef";
    std::string out(16, '0');
    for (std::size_t index = 0; index < 16; ++index) {
      out[15 - index] = kDigits[(value_ >> (4 * index)) & 0xFULL];
    }
    return out;
  }

 private:
  std::uint64_t value_ = 0xCBF29CE484222325ULL;
};

/// Session 125, the one authorized development session, through the production
/// registry and clock (never a stub).
[[nodiscard]] inline const SessionClock& guard_clock() {
  static const SessionClock built = [] {
    auto loaded = Registry::load_embedded();
    if (!loaded.has_value()) {
      detail::fail_fast("destruction guard: the embedded registry failed its digest gate");
    }
    auto date = CivilDate::parse_ymd("2022-07-05");
    if (!date.has_value()) {
      detail::fail_fast("destruction guard: the session day is not a canonical civil date");
    }
    auto clock = SessionClock::for_day(loaded.value(), date.value());
    if (!clock.has_value()) {
      detail::fail_fast("destruction guard: the registry refused session 125");
    }
    return std::move(clock).value();
  }();
  return built;
}

[[nodiscard]] inline std::int64_t guard_open_ms() {
  return guard_clock().open_b().ns() / kNanosecondsPerMillisecond;
}

/// One stock print with a complete attached quote block.
[[nodiscard]] inline qr::sources::StockTradeRow guard_trade(std::int64_t offset_ms,
                                                            std::int64_t price_u6,
                                                            std::int64_t size,
                                                            std::int64_t sequence) {
  qr::sources::StockTradeRow row;
  row.ts_ms_b = guard_open_ms() + offset_ms;
  row.quote_ts_ms_b = row.ts_ms_b - 5;
  row.sequence = sequence;
  row.ext_condition = {255, 255, 255, 255};
  row.condition = 0;
  row.size = size;
  row.exchange = 0;
  row.price_u6 = price_u6;
  row.bid_u6 = price_u6 - 1000;
  row.ask_u6 = price_u6 + 1000;
  row.bid_shares = 300;
  row.ask_shares = 400;
  row.bid_condition = 0;
  row.ask_condition = 0;
  return row;
}

[[nodiscard]] inline qr::sources::StockQuoteRow guard_quote(std::int64_t offset_ms,
                                                            std::int64_t bid_u6,
                                                            std::int64_t ask_u6) {
  qr::sources::StockQuoteRow row;
  row.ts_ms_b = guard_open_ms() + offset_ms;
  row.bid_u6 = bid_u6;
  row.ask_u6 = ask_u6;
  row.bid_shares = 500;
  row.ask_shares = 700;
  row.bid_condition = 0;
  row.ask_condition = 0;
  return row;
}

/// The fixed tape: 300 print groups and 300 NBBO groups at 100ms spacing, so the
/// carriers see truncation (>128 groups), a left pad (an early cutoff), pre-open
/// bins, empty bins and a phase split. Every bit of every output the WP8b
/// substrate produces goes into the digest.
[[nodiscard]] inline std::string production_fingerprint() {
  StreamOptions options;
  options.retain_group_vectors = true;
  StockPrintStream prints(guard_clock(), options);
  NbboStream quotes(guard_clock(), options);

  for (std::int64_t index = 0; index < 300; ++index) {
    const std::int64_t offset_ms = 1000 + index * 100;
    const std::int64_t price_u6 = 380'000'000 + index * 1000;
    // Two members in every fifth group, so the equal-time reduction is exercised.
    std::vector<qr::sources::StockTradeRow> trades{
        guard_trade(offset_ms, price_u6, 100 + index, index * 2)};
    if (index % 5 == 0) {
      trades.push_back(guard_trade(offset_ms, price_u6 + 500, 50, index * 2 + 1));
    }
    const auto pushed = prints.push_group(trades.front().ts_ms_b, trades);
    if (!pushed.has_value()) {
      detail::fail_fast("destruction guard: the stock-print stream refused a group");
    }
    std::vector<qr::sources::StockQuoteRow> rows{
        guard_quote(offset_ms, price_u6 - 1000, price_u6 + 1000)};
    if (index % 7 == 0) {
      rows.push_back(guard_quote(offset_ms, price_u6 - 2000, price_u6 + 2000));
    }
    const auto quoted = quotes.push_group(rows.front().ts_ms_b, rows);
    if (!quoted.has_value()) {
      detail::fail_fast("destruction guard: the NBBO stream refused a group");
    }
  }

  Digest digest;
  const std::int64_t open_ns = guard_clock().session_start_a().ns();
  // The SIDE-NEUTRAL tables are folded once (they are not per side), then the
  // whole per-side chain is folded for each side.
  for (const GroupVectorTable* table : {&prints.group_vectors(), &quotes.group_vectors()}) {
    digest.feed_i64(static_cast<std::int64_t>(table->groups()));
    digest.feed_i64(static_cast<std::int64_t>(table->dim()));
    for (const float value : table->values()) {
      digest.feed_f32(value);
    }
  }
  for (const Side side : {Side::LONG, Side::SHORT}) {

    struct Stream {
      Modality modality;
      std::span<const GroupRecord> groups;
    };
    const Stream streams[2] = {{Modality::STOCK_PRINT, prints.groups()},
                               {Modality::STOCK_NBBO, quotes.groups()}};
    for (const Stream& stream : streams) {
      DirectRawBuilder direct(stream.modality, stream.groups);
      NativeOrderBuilder native(stream.modality, stream.groups);
      // Three cutoffs: inside the first 120s (pre-open bins + left pad), after
      // 128 groups (truncation), and at the very end of the tape.
      for (const std::int64_t cutoff_ms : {6'000, 20'000, 31'000}) {
        DecisionWindow window;
        window.cutoff_ns_a = open_ns + cutoff_ms * kNanosPerSecond / 1000;
        window.session_open_ns_a = open_ns;
        window.side = side;
        window.phase_reference_present = true;
        window.phase_reference_ns_a = open_ns + (cutoff_ms - 1'500) * kNanosPerSecond / 1000;

        const auto row = direct.build(window);
        if (!row.has_value()) {
          detail::fail_fast("destruction guard: DIRECT_RAW refused a window");
        }
        for (std::size_t column = 0; column < kDirectColumnCount; ++column) {
          digest.feed_f64(row.value().value[column]);
          digest.feed_i64(static_cast<std::int64_t>(row.value().validity[column]));
        }

        const auto micro = native.build_micro(window);
        if (!micro.has_value()) {
          detail::fail_fast("destruction guard: the micro carrier refused a window");
        }
        digest.feed_i64(micro.value().start);
        digest.feed_i64(micro.value().length);
        digest.feed_i64(micro.value().left_pad);
        digest.feed_i64(micro.value().truncated);
        for (std::size_t slot = 0; slot < kMicroCarrierGroups; ++slot) {
          digest.feed_i64(micro.value().slot_group[slot]);
          digest.feed_i64(static_cast<std::int64_t>(micro.value().slot_phase[slot]));
        }

        const auto bins = native.build_bins(window);
        if (!bins.has_value()) {
          detail::fail_fast("destruction guard: the bin carrier refused a window");
        }
        digest.feed_i64(bins.value().pre_open_pad_bins);
        digest.feed_i64(bins.value().nonempty_bins);
        digest.feed_i64(bins.value().member_groups);
        for (std::size_t bin = 0; bin < kBinCarrierBins; ++bin) {
          digest.feed_i64(bins.value().start[bin]);
          digest.feed_i64(bins.value().length[bin]);
          digest.feed_f64(bins.value().log1p_group_count[bin]);
          digest.feed_i64(bins.value().nonempty[bin]);
          digest.feed_i64(bins.value().valid[bin]);
        }
      }
    }
  }
  return digest.hex();
}

}  // namespace qr::carriers::guard

#endif  // QR_CARRIERS_TOOLS_DESTRUCTION_GUARD_HPP
