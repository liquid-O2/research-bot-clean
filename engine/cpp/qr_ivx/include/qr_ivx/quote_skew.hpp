// qr_ivx/quote_skew.hpp — THE MODEL-FREE QUOTE-SKEW PROXY (brief item B3).
//
// SPEC (orchestrator brief): "for the ATM strike and +-1/+-2 strikes where
// two-sided: OTM-put-mid / OTM-call-mid price ratio normalized by straddle mid
// -> a no-inversion skew proxy per second."
//
// NO INVERSION, ANYWHERE. Every number below is a ratio of quoted MIDPOINTS.
// There is no volatility, no time-to-expiry, no distribution and no root find:
// the object is a PRICE tilt, and the straddle mid is the only scale it is
// divided by. That is what makes it lawful beside the traded-IV work rather
// than a second, weaker estimate of the same thing.
//
// THE BRIEF NAMES TWO READINGS OF "ratio ... normalized by straddle mid" and
// this module emits BOTH rather than choosing one silently:
//   * `tilt` = (put_mid - call_mid) / straddle_mid — a difference expressed in
//     units of the straddle, additive across offsets and bounded in practice;
//   * `log_ratio` = ln(put_mid / call_mid) — the pure ratio, scale-free, which
//     is what "put-mid / call-mid ratio" says literally.
// ORIENTATION LAW (fixtured): both are POSITIVE when the OTM PUT is richer than
// the matching OTM CALL — the classic equity-index sign, and the same sign
// convention as `SkewCell::risk_reversal` on the traded side, so the two
// objects can be compared without a mental flip.
//
// THE LADDER IS THE TAPE'S OWN. "+-1/+-2 strikes" means one and two rungs of
// the strike ladder ACTUALLY QUOTED two-sided in that second on that expiry,
// not a fixed dollar step: strike spacing changes with era and with distance
// from spot, and a fixed step would silently compare different objects across
// sessions.
//
// EVERY LAW IT INHERITS from the W2.1 block, unchanged, because a second set of
// contract-state rules would be a second thing to get wrong:
//   * a contract's state is its LAST STRICTLY-PRIOR quote (Q11);
//   * a contract is usable only if that quote is at most 300s old
//     (`qr::w21::kContractAgeGateMs`) and two-sided with 0 < bid <= ask (Q4);
//   * the ATM strike is the argmin |ln(K/m)| among strikes with BOTH rights
//     usable, and only within 150bp (Q5); equidistant candidates are TYPED
//     UNDECIDABLE, never broken by an id (the §W21-PIN-1 ratified reading);
//   * DTE planes are {0,1} only (Q2).
#ifndef QR_IVX_QUOTE_SKEW_HPP
#define QR_IVX_QUOTE_SKEW_HPP

#include <array>
#include <cstdint>
#include <map>
#include <string>
#include <vector>

#include "qr_core/validity.hpp"
#include "qr_ivx/iv_cross.hpp"
#include "qr_ivx/tsv.hpp"
#include "qr_sources/option_quotes.hpp"

namespace qr::ivx {

/// The two offsets the brief names, beside the ATM rung itself.
inline constexpr std::array<std::int64_t, 2> kQuoteSkewOffsets{1, 2};

/// One grid second of the proxy, for ONE expiry plane.
struct QuoteSkewSecond {
  std::int64_t second = 0;
  std::int64_t spot_u6 = 0;
  std::int64_t atm_strike_u6 = 0;
  std::int64_t atm_moneyness_bps = 0;
  std::int64_t ladder_rungs = 0;
  Typed<double> straddle_mid_u6{0.0, Validity::MISSING};
  /// Offset 0 is the ATM rung's own put/call tilt (the put-call parity tilt of
  /// the forward); offsets 1 and 2 are `kQuoteSkewOffsets`.
  std::array<Typed<double>, 3> tilt{};
  std::array<Typed<double>, 3> log_ratio{};
  Validity state = Validity::MISSING;
};

/// The 30-minute aggregate of the per-second series: size of support and the
/// mean of each channel over the seconds where it was VALID. Means are
/// UNWEIGHTED across seconds on purpose — every grid second is one observation
/// of the quoted surface, and weighting by quoted size would turn a price tilt
/// into a depth statistic.
struct QuoteSkewWindow {
  std::int64_t window = 0;
  std::int64_t seconds_present = 0;
  std::int64_t seconds_valid = 0;
  std::array<Typed<double>, 3> mean_tilt{};
  std::array<Typed<double>, 3> mean_log_ratio{};
  std::array<std::int64_t, 3> support{};
  /// Window-to-window innovation of the +-1 tilt (the brief's headline rung).
  Typed<double> d_mean_tilt_1{0.0, Validity::MISSING};
};

/// Streams one session's option-quote groups and evaluates the proxy on the
/// program's own 1s grid.
class QuoteSkewBuilder {
 public:
  /// `grid_mid_u6` is the emitted 1s midpoint grid (column 0 of
  /// `features/grid_1s.npy`), indexed by session second; a zero entry means the
  /// grid had no eligible midpoint and the second is typed absent.
  /// `retain_from`/`retain_to` bound the per-second series that is KEPT; the
  /// window aggregates always cover the whole session.
  QuoteSkewBuilder(std::int64_t open_ms_b, std::int64_t session_epoch_day, std::int64_t plane_dte,
                   const std::vector<std::int64_t>* grid_mid_u6, std::int64_t retain_from,
                   std::int64_t retain_to);

  /// Folds one decoded quote row. Rows must arrive in non-decreasing `ts_ms_b`,
  /// which the B4 reader already guarantees (it refuses otherwise).
  void observe(const qr::sources::OptionQuoteRow& row);
  /// Closes the session: evaluates every remaining second and the aggregates.
  void finish();

  [[nodiscard]] const std::vector<QuoteSkewSecond>& seconds() const noexcept { return retained_; }
  [[nodiscard]] const std::array<QuoteSkewWindow, kWindows>& windows() const noexcept {
    return windows_;
  }
  [[nodiscard]] std::int64_t rows_observed() const noexcept { return rows_observed_; }
  [[nodiscard]] std::int64_t rows_on_plane() const noexcept { return rows_on_plane_; }

 private:
  struct Quote {
    std::int64_t ts_ms_b = 0;
    std::int64_t bid_u6 = 0;
    std::int64_t ask_u6 = 0;
  };
  struct StrikeState {
    Quote call;
    Quote put;
    bool has_call = false;
    bool has_put = false;
  };

  void evaluate_through(std::int64_t second);
  [[nodiscard]] QuoteSkewSecond evaluate_one(std::int64_t second) const;

  std::int64_t open_ms_b_;
  std::int64_t session_epoch_day_;
  std::int64_t plane_dte_;
  const std::vector<std::int64_t>* grid_mid_u6_;
  std::int64_t retain_from_;
  std::int64_t retain_to_;

  /// Strike-ordered contract state for the ONE expiry plane under study. An
  /// ordered map because the ladder IS its key order.
  std::map<std::int64_t, StrikeState> ladder_;
  std::int64_t next_second_ = 0;
  std::int64_t rows_observed_ = 0;
  std::int64_t rows_on_plane_ = 0;
  std::vector<QuoteSkewSecond> retained_;
  std::array<QuoteSkewWindow, kWindows> windows_{};
  struct Accumulator {
    std::array<double, 3> tilt{};
    std::array<double, 3> log_ratio{};
    std::array<std::int64_t, 3> support{};
    std::int64_t present = 0;
    std::int64_t valid = 0;
  };
  std::array<Accumulator, kWindows> accumulator_{};
};

void emit(Report& report, const std::string& key, const QuoteSkewBuilder& builder,
          bool retain_seconds);

}  // namespace qr::ivx

#endif  // QR_IVX_QUOTE_SKEW_HPP
