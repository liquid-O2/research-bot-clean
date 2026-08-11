// qr_carriers/location.hpp — THE 16 LOCATION/CLOCK VALUES.
//
// SPEC (evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 5, verbatim):
//
//   "The exact 16 location/clock values are: session-time fraction; its
//    sine/cosine; seconds-to-close fraction; early-close bit; oriented bps from
//    session open; oriented bps from running high; oriented bps from running
//    low; running range bps; oriented bps from prefix VWAP; prefix RV over
//    1s,5s,30s; current spread bps; log1p seconds since last stock print; and
//    log1p seconds since last option print. Each has a parallel presence bit
//    (the five pure clock values are always present). The 32 values/bits project
//    32->64 and add to the 64d candidate-set embedding."
//
//   "Location uses the last valid IWM NBBO midpoint strictly before cutoff as
//    `m`; open/high/low are the first/min/max such prefix midpoints, and VWAP is
//    size-weighted IWM stock prints strictly before cutoff that pass the frozen
//    stock condition/size/price contract. Every oriented distance is
//    `sigma*(m-reference)*10000/reference`; range is `(high-low)*10000/open`.
//    Prefix RV at 1/5/30s is `sqrt(sum(log(m_t/m_{t-1})^2))` on the prior
//    complete 1s midpoint grid and is missing with fewer than two valid points.
//    Time fractions use registered RTH open/close; spread and last-print ages
//    use only strict-prior observations."
//
// THE FIVE PURE CLOCK VALUES ARE INDICES 0..4 and their presence bits are
// unconditionally set, exactly as the parenthesis says: session-time fraction,
// its sine, its cosine, seconds-to-close fraction, early-close bit. Everything
// else depends on tape and can be masked.
//
// TWO READINGS, BOTH RULED BY THE ORCHESTRATOR (2026-08-10):
//   1. "its sine/cosine" is the CYCLICAL encoding: sin(2*pi*f) and cos(2*pi*f)
//      of the session-time fraction. (This lane first implemented the literal
//      sin(f)/cos(f) and returned the question; the ruling is the 2*pi form,
//      because a bare sine of a fraction in [0,1] is near-linear in f and adds
//      nothing to the fraction beside it.)
//   2. "log1p SECONDS since last stock/option print" is implemented in SECONDS,
//      as section 5 words it, while every section-4 age/gap stays in
//      log1p(MICROseconds) per the exhaustive transform table. Both lines are
//      cited law over different objects; `transforms.hpp` carries the same note.
//
// EARLY CLOSE IS READ FROM THE SESSION'S OWN REGISTRY ROW, never from a caller:
// nine pinned sessions are 210-bar early closes (qr_clock's own warning), so the
// bit is `expected_bar_count != 390` and the time fractions divide by that same
// session's real span.
#ifndef QR_CARRIERS_LOCATION_HPP
#define QR_CARRIERS_LOCATION_HPP

#include <array>
#include <cstdint>
#include <span>
#include <vector>

#include "qr_carriers/channels.hpp"
#include "qr_carriers/grid_1s.hpp"
#include "qr_carriers/streams.hpp"
#include "qr_clock/session_clock.hpp"
#include "qr_core/refusal.hpp"

namespace qr::carriers {

enum LocationValue : std::size_t {
  kLocSessionTimeFraction = 0,
  kLocSessionTimeSine = 1,
  kLocSessionTimeCosine = 2,
  kLocSecondsToCloseFraction = 3,
  kLocEarlyCloseBit = 4,
  kLocOrientedBpsFromOpen = 5,
  kLocOrientedBpsFromRunningHigh = 6,
  kLocOrientedBpsFromRunningLow = 7,
  kLocRunningRangeBps = 8,
  kLocOrientedBpsFromPrefixVwap = 9,
  kLocPrefixRv1s = 10,
  kLocPrefixRv5s = 11,
  kLocPrefixRv30s = 12,
  kLocCurrentSpreadBps = 13,
  kLocLog1pSecondsSinceLastStockPrint = 14,
  kLocLog1pSecondsSinceLastOptionPrint = 15,
};
inline constexpr std::size_t kLocationValueCount = 16;
/// "The 32 values/bits project 32->64" — the model-facing width.
inline constexpr std::size_t kLocationProjectionWidth = 2 * kLocationValueCount;
static_assert(kLocationProjectionWidth == 32);
/// The bar count of a regular (non-early-close) session.
inline constexpr std::int64_t kRegularBarCount = 390;
/// The cyclical encoding's period: one whole session maps to one full turn.
inline constexpr double kTwoPi = 6.283185307179586476925286766559;

[[nodiscard]] const char* location_value_name(std::size_t index) noexcept;
/// False for the early-close bit; true for the other fifteen. "Binary/
/// categorical/mask fields are never centered or scaled."
[[nodiscard]] bool location_value_is_continuous(std::size_t index) noexcept;

/// One decision's location row: 16 values with their parallel presence bits.
struct LocationRow {
  std::array<double, kLocationValueCount> value{};
  std::array<Validity, kLocationValueCount> validity{};

  LocationRow() noexcept { validity.fill(Validity::MISSING); }
  void set(std::size_t index, Typed<double> typed) noexcept {
    value[index] = typed.v == Validity::VALID ? typed.value : 0.0;
    validity[index] = typed.v;
  }
  [[nodiscard]] bool presence(std::size_t index) const noexcept {
    return validity[index] == Validity::VALID;
  }
};

/// Everything one session's location layer reads. Nothing here is opened or
/// decoded: the three streams and the grid are already built.
struct LocationInputs {
  const SessionClock* clock = nullptr;
  const MidpointGrid* grid = nullptr;
  /// The session's ELIGIBLE NBBO group midpoints, causal order.
  std::span<const NbboStream::EligibleMid> eligible_mids;
  /// The stock-print and option-print group records, causal order (their
  /// timestamps are the "last print" clocks).
  std::span<const GroupRecord> stock_print_groups;
  std::span<const GroupRecord> option_print_groups;
  /// The exact integer VWAP running sums after each stock-print group.
  std::span<const std::int64_t> vwap_notional_prefix;
  std::span<const std::int64_t> vwap_size_prefix;
};

/// Builds location rows for one session. Construction precomputes the running
/// high/low of the prefix midpoints so a decision is O(log n), never a rescan.
class LocationBuilder {
 public:
  explicit LocationBuilder(const LocationInputs& inputs);

  [[nodiscard]] Expected<LocationRow, Refusal> build(std::int64_t cutoff_ns_a, Side side) const;

 private:
  const SessionClock* clock_;
  const MidpointGrid* grid_;
  std::span<const NbboStream::EligibleMid> eligible_mids_;
  std::span<const GroupRecord> stock_print_groups_;
  std::span<const GroupRecord> option_print_groups_;
  std::span<const std::int64_t> vwap_notional_prefix_;
  std::span<const std::int64_t> vwap_size_prefix_;
  /// Running max/min of `eligible_mids_[0..i]`.
  std::vector<std::int64_t> running_high_;
  std::vector<std::int64_t> running_low_;
};

}  // namespace qr::carriers

#endif  // QR_CARRIERS_LOCATION_HPP
