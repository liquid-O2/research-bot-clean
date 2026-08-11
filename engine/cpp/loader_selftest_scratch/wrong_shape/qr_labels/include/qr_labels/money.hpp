// qr_labels/money.hpp — THE exact integer money math of the fresh-entry label.
//
// SPEC (verbatim, evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 3):
//   "entry = first eligible IWM quote group strictly after the decision; LONG
//    entry ask_max/mark bid_min, SHORT entry bid_min/mark ask_max; adverse wins
//    equal-ms; 576 cents cost once."
//   "the causal $300 (=30,000 net-cent) stop"
//   "thresholds are +/-5,000 **net cents** after cost (about +$55.76 gross
//    versus -$44.24 gross)"
//
// THE UNIT LAW, DERIVED FROM THE CARD'S OWN PARENTHETICAL. +5,000 net cents is
// "+$55.76 gross" = 5,576 gross cents and -5,000 net is "-$44.24 gross" =
// -4,424 gross cents, so
//
//     net_cent = gross_cent - 576                                        (1)
//
// exactly once per round trip, which is what "576 cents cost once" means and
// what qr_replay/action.hpp already encodes ("`LabelRow::menu_net_cent[h]` is
// NET of the 576c; the replay kernel adds NOTHING and subtracts NOTHING").
//
// THE GROSS SCALE. The card fixes the unit (cents of realised P&L) but not the
// notional that turns a price FRACTION into gross cents. The project's frozen
// fresh-entry arithmetic — carried identically in three independent places of
// the design record (transcripts/CONVERSATION.md:12871-12873, :17703-17704 and
// :24080, the last being the frozen kernel's own statement) — is
//
//     frac_u6  = trunc_toward_zero(move_u6 * 1,000,000 / entry_fill_u6)   (2)
//     net_cent = frac_u6 * 10 - 576                                       (3)
//
// i.e. gross_cent = frac_u6 * 10, a $100,000 notional per action row. THIS IS
// A DECLARED CARRY-IN, NOT A LOCAL INVENTION: the card section this module is
// built from does not restate (2)/(3), so the WP7 report raises it as a STOP
// question. It is centralised HERE, in two named constants, so that an
// adjudication that changes the notional changes exactly one line.
//
// EVERY NUMBER BELOW IS AN INTEGER. There is no floating point anywhere in the
// label kernel: a double cannot represent 1e12/3 exactly, two-run byte
// identity is a law, and `trunc_toward_zero` is exactly what C++ integer
// division already does (C++20 [expr.mul]/4: the quotient is truncated toward
// zero), so the frozen formula ports without a rounding helper.
#ifndef QR_LABELS_MONEY_HPP
#define QR_LABELS_MONEY_HPP

#include <cstdint>

#include "qr_core/checked.hpp"
#include "qr_core/refusal.hpp"
#include "qr_replay/action.hpp"

namespace qr::labels {

/// WP7 conforms to WP11's frozen economic vocabulary rather than restating it
/// (brief: "conform to qr_replay's ScoredAction/LabelRow structs where they
/// overlap").
using qr::replay::ActionKey;
using qr::replay::kHorizonCount;
using qr::replay::kHorizonMinutes;
using qr::replay::kStopNetCent;
using qr::replay::kTradeCostCent;
using qr::replay::LabelState;
using qr::replay::Side;

/// The u6 price scale: a price is dollars x 1,000,000, so a return FRACTION
/// expressed on the same scale is `move * 1,000,000 / entry` (formula (2)).
inline constexpr std::int64_t kFracScaleU6 = 1'000'000;

/// Gross cents per unit of `frac_u6` (formula (3)); the $100,000 notional.
inline constexpr std::int64_t kGrossCentPerFracU6 = 10;

/// The barrier auxiliary's symmetric net-cent thresholds (card section 3:
/// "`barrier_order(entry_idx,side,5000,5000)`").
inline constexpr std::int64_t kBarrierNetCent = 5'000;

/// The wall, as a SIGNED net-cent level: the card's "-30,000 net-cent" stop.
/// Signed because `stop_scan` takes the wall as a parameter — the APPENDIX C5
/// stop-shift mutant has to be able to move it, and a mutant that can only
/// move a magnitude cannot express the shift.
inline constexpr std::int64_t kStopWallNetCent = -kStopNetCent;

/// An absent index. Every "no such group / no such second / no such ordinal"
/// answer is this value and never 0, which is a real index.
inline constexpr std::int64_t kNoIndex = -1;

/// Nanoseconds per minute, for the fixed-menu horizons.
inline constexpr std::int64_t kNanosecondsPerMinute = 60'000'000'000;
/// Nanoseconds per second, for `decision_ts_ns = session_start_ns +
/// decision_second * 1e9` (card section 3).
inline constexpr std::int64_t kNanosecondsPerSecond = 1'000'000'000;

// ---------------------------------------------------------------------------
// Exact integer division helpers.
// ---------------------------------------------------------------------------

/// Floor division by a STRICTLY POSITIVE divisor. C++ truncates toward zero,
/// which is not the floor for a negative numerator, and every price bound
/// below needs the true floor.
[[nodiscard]] constexpr std::int64_t floor_div_positive(std::int64_t numerator,
                                                        std::int64_t divisor) noexcept {
  const std::int64_t quotient = numerator / divisor;
  return (numerator % divisor != 0 && numerator < 0) ? quotient - 1 : quotient;
}

/// Ceiling division by a STRICTLY POSITIVE divisor.
[[nodiscard]] constexpr std::int64_t ceil_div_positive(std::int64_t numerator,
                                                       std::int64_t divisor) noexcept {
  const std::int64_t quotient = numerator / divisor;
  return (numerator % divisor != 0 && numerator > 0) ? quotient + 1 : quotient;
}

// ---------------------------------------------------------------------------
// The two frozen formulas.
// ---------------------------------------------------------------------------

/// Formula (2). `entry_u6` must be strictly positive (it is an executable fill
/// price); a non-positive fill is a refusal, never a division guarded by a
/// substituted value.
[[nodiscard]] Expected<std::int64_t, Refusal> frac_u6(std::int64_t move_u6,
                                                      std::int64_t entry_u6) noexcept;

/// Formula (3): the ONE place the 576-cent round trip is charged.
[[nodiscard]] Expected<std::int64_t, Refusal> net_cent_of_frac(std::int64_t frac) noexcept;

/// The signed price move of a mark, in the side's own direction (card section
/// 3): LONG marks a bid against an ask fill, SHORT marks an ask against a bid
/// fill.
[[nodiscard]] Expected<std::int64_t, Refusal> move_u6(std::int64_t entry_u6,
                                                      std::int64_t mark_u6, Side side) noexcept;

/// THE MARK: the realised net cents of exiting at `mark_u6`, cost charged once.
/// This is the single authority for every value the label kernel publishes —
/// menu, certificate, MAE and barrier all reduce to it.
[[nodiscard]] Expected<std::int64_t, Refusal> mark_net_cent(std::int64_t entry_u6,
                                                            std::int64_t mark_u6,
                                                            Side side) noexcept;

// ---------------------------------------------------------------------------
// The inverse: a net threshold as an exact PRICE gate.
// ---------------------------------------------------------------------------

/// Which way a net threshold is crossed.
enum class NetBound : std::uint8_t {
  /// "the marked net crosses -30,000c" — the adverse wall and the adverse
  /// barrier. The derived `frac` threshold must be strictly negative.
  AT_OR_BELOW = 0,
  /// The favorable barrier. The derived `frac` threshold must be strictly
  /// positive.
  AT_OR_ABOVE = 1,
};

/// A net threshold, restated as an exact integer test on a MARK PRICE.
///
/// WHY THIS EXISTS. `mark_net_cent` is monotone in the mark price (increasing
/// for LONG, decreasing for SHORT) because integer truncation is monotone, so
/// "the first group whose net crosses T" is "the first group whose price
/// crosses P" — a range-extremum query instead of a linear scan over 2.8M
/// groups. The kernel still re-checks the exact net at whatever index the
/// price gate finds, so a defect in this inversion cannot silently become a
/// label (the check is code, never an assert).
struct PriceGate {
  /// The threshold price, in u6.
  std::int64_t price_u6 = 0;
  /// True: the net threshold is crossed when the mark price is <= price_u6.
  /// False: it is crossed when the mark price is >= price_u6.
  bool triggers_at_or_below = true;
};

/// Builds the exact price gate of a net threshold.
///
/// Refuses (CONFIG) when the derived `frac` threshold has the wrong sign for
/// `bound`: the closed forms below are the two branches the card's own
/// thresholds live on (-30,000 and -5,000 give frac -2,943 and -443; +5,000
/// gives +558), and a branch with no fixture is a branch that does not exist.
[[nodiscard]] Expected<PriceGate, Refusal> price_gate_for_net(std::int64_t entry_u6, Side side,
                                                              NetBound bound,
                                                              std::int64_t net_cent) noexcept;

/// The `frac` threshold of a net threshold, exposed by name so the boundary
/// arithmetic itself is fixturable: `net = frac*10 - 576` means the reachable
/// nets are exactly the integers congruent to 4 modulo 10, which is why a
/// one-cent shift of the wall is provably a no-op (see the APPENDIX C5 mutant
/// discussion in label_kernel.hpp).
[[nodiscard]] Expected<std::int64_t, Refusal> frac_threshold_for_net(NetBound bound,
                                                                     std::int64_t net_cent) noexcept;

}  // namespace qr::labels

#endif  // QR_LABELS_MONEY_HPP
