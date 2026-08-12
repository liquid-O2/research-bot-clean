// qr_ivx/iv_cross.hpp — TRADED-IV CROSS-SECTION FROM OWNED DATA.
//
// SPEC (orchestrator brief, IV-COMPLEX lane, 2026-08-12), which this header
// pins into formulas:
//   B1 per-strike traded-IV curve: per session per expiry, size-weighted VENDOR
//      IV of prints bucketed by ln(K/m) (the §W21-PIN-1 edges plus finer ATM
//      steps), per 30-minute window -> skew slope (put-side minus call-side
//      regression) + curvature + their intraday innovations;
//   B2 term traded-IV: the same per-expiry aggregation across ALL expiries the
//      prints carry (D3: 26-35) -> near/far IV ratio + slope innovations (the
//      F10 term-micro object, prints-sourced so NOT degenerate);
//   D1 traded-vs-surface richness: print IV minus the concurrent PROXY_VOL;
//   D2 per-contract IV velocity (age-aware), aggregated by moneyness bucket;
//   D3 cross-strike IV dispersion (same-window and same-second forms);
//   D4 the per-bucket IV INNOVATION VECTOR (which part of the smile moved);
//   D5 signed vol-demand flow by bucket with the 0DTE split;
//   D6 the same constructions on the RUTW tape + the IWM-minus-RUTW spread;
//   D7 vol-of-vol (F6) + the spike/bleed/flat state;
//   D8 the fluctuation-dissipation ratio;
//   D9 the third-order time-irreversibility statistic A3.
//
// THE FIREWALL STANDS. Nothing here inverts an option pricing model. Every IV
// number is the VENDOR's own `implied_vol(34)` column, which APPENDIX B3
// already projects, read under B3's own attachment law; every surface number is
// the W2.1 block's PROXY_VOL, which is labelled a proxy and never called IV.
// No Black-Scholes, no root find, no greek recomputation.
//
// THE ADMITTED PRINT (pinned, and every rejection is COUNTED, never silent):
//   1. the projected cells this module reads are all present: expiration,
//      strike, right in {C,P}, size, price, implied_vol, underlying_price,
//      quote_ts, underlying_ts;
//   2. B3's BOTH-ATTACHMENTS law holds: `quote_ts(45)` is STRICTLY before the
//      print instant, and `underlying_ts(36)` is stamped with this session's
//      own civil day (a ten-byte comparison, never a parse — WP4's rule);
//   3. the print is SINGLE-LEG (condition in {18,95,125,126}). A spread prints
//      its legs at negotiated prices, so the vendor IV of a leg is not a quote
//      on that strike's volatility. Multi-leg prints are counted and excluded;
//   4. size > 0, implied_vol finite and > 0, underlying_price finite and > 0.
//
// THE SPOT THIS MODULE DIVIDES BY is the print's OWN attached
// `underlying_price(37)` — a projected column carrying B3's strictly-prior
// attachment, and the only spot the RUTW tape has at all. When the emitted 1s
// midpoint grid is also supplied, the module carries an INDEPENDENT
// cross-check: how often the grid's spot puts a print in a different moneyness
// band. It never silently substitutes one for the other.
//
// TWO-RUN IDENTITY. All iteration is over vectors and ordered maps in
// insertion/key order; no wall-clock value enters any number; every real is
// emitted through `%.17g`.
#ifndef QR_IVX_IV_CROSS_HPP
#define QR_IVX_IV_CROSS_HPP

#include <array>
#include <cstdint>
#include <map>
#include <set>
#include <string>
#include <tuple>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_core/validity.hpp"
#include "qr_ivx/tsv.hpp"
#include "qr_sources/option_prints.hpp"

namespace qr::ivx {

// ---------------------------------------------------------------------------
// Pinned constants. Every one of them is a DESIGN PIN with a stated reason;
// none is a tuned number.
// ---------------------------------------------------------------------------

/// The intraday window. 30 minutes is the brief's grain; RTH is 23,400s, so the
/// session holds exactly 13 whole windows and the last one is not a stub.
inline constexpr std::int64_t kWindowSeconds = 1800;
inline constexpr std::size_t kWindows = 13;
static_assert(kWindowSeconds * static_cast<std::int64_t>(kWindows) == 23400,
              "the RTH session must divide into whole 30-minute windows");

/// The moneyness axis in `10000 * ln(K/m)`. The four §W21-PIN-1 edges
/// {-150,-50,+50,+150} are PRESENT AND UNMOVED; the brief's "finer ATM steps"
/// add +/-25 (about half a strike at IWM scale), and +/-300 splits the far wing
/// from the tail instead of letting a 20-delta and a 5-delta print share a bin.
/// Bins are RIGHT-OPEN, per the substrate bin law ratified in §W21-PIN-2.
inline constexpr std::array<std::int64_t, 8> kMoneynessEdgesBps{-300, -150, -50, -25,
                                                                25,   50,   150, 300};
inline constexpr std::size_t kBands = kMoneynessEdgesBps.size() + 1;  // 9
inline constexpr std::size_t kRights = 2;                             // Call, Put

/// The wing anchor at which the put wing and the call wing are differenced:
/// ln-moneyness 0.0150 == the +/-150bp §W21-PIN-1 outer edge. Reading the two
/// wing fits at a COMMON |x| is what makes the difference a skew rather than a
/// pair of unrelated slopes.
inline constexpr double kWingAnchorLn = 0.0150;

/// A wing regression needs three DISTINCT strikes (two points define a line
/// exactly and say nothing about fit); the quadratic needs five.
inline constexpr std::int64_t kMinWingStrikes = 3;
inline constexpr std::int64_t kMinCurvatureStrikes = 5;
/// A window/expiry cell needs this much traded size before its fit is a
/// statement about the market rather than about one lot.
inline constexpr std::int64_t kMinCellWeight = 10;

/// D2: two consecutive prints of ONE contract more than half an hour apart are
/// not a repricing SPEED, they are two unrelated observations. Same gate the
/// W2.1 Greek-residual block uses for greek age (`kGreekMaxAgeSeconds`).
inline constexpr std::int64_t kIvVelocityMaxGapMs = 1'800'000;

/// B2: the "far" leg of the near/far ratio is the nearest expiry at least a
/// week out — past the weekly-expiry cluster that shares the near leg's event
/// set. When no such expiry trades in the window the ratio is typed absent and
/// the fallback (largest available DTE) is emitted under its own name.
inline constexpr std::int64_t kTermFarMinDteDays = 7;
/// A term regression needs three distinct expiries.
inline constexpr std::int64_t kMinTermExpiries = 3;

/// D8/D9 supports. A 30-minute window holds 1,800 grid seconds, so these are
/// small fractions of a full window and reject only genuinely thin ones.
inline constexpr std::int64_t kMinFdPairs = 60;
inline constexpr std::int64_t kMinFdQuietPoints = 30;
inline constexpr std::int64_t kMinA3Pairs = 120;

/// D7: the spike/bleed state cut. The threshold is the SESSION's own 80th
/// percentile of |window-to-window relative PROXY_VOL change|, emitted beside
/// the state so a deployable feature can substitute a TRAIN-frozen era
/// quantile. A census may describe a session with the session's own scale; a
/// FEATURE may not, and this header says so out loud.
inline constexpr std::int64_t kVolStateQuantileNumerator = 80;
inline constexpr std::int64_t kVolStateQuantileDenominator = 100;

/// AN ARRAY OF TYPED ABSENCES, and the reason this helper has to exist.
///
/// `qr::Typed` is a bare aggregate (`{T value; Validity v;}`) and `Validity`
/// declares `VALID` FIRST, so `Validity::VALID == 0` and
/// `std::array<Typed<double>, N>{}` value-initialises every element to
/// `{0.0, VALID}` — a VALID ZERO. That is precisely the "an absence filled with
/// a zero" this program forbids everywhere else: a channel that was never
/// computed would be published as a measurement of zero, and a consumer reading
/// the `_v` column would be told to believe it.
///
/// Every SCALAR `Typed` member in this header already carries an explicit
/// `{0.0, Validity::MISSING}` initialiser for that reason. The ARRAY members
/// could not say the same thing with `{}`, so they say it through this.
template <std::size_t N>
[[nodiscard]] constexpr std::array<Typed<double>, N> absent_array() {
  std::array<Typed<double>, N> out{};
  for (std::size_t index = 0; index < N; ++index) {
    out[index] = Typed<double>{0.0, Validity::MISSING};
  }
  return out;
}

/// The right-open band of `x_bps` on `kMoneynessEdgesBps`. Total: every integer
/// lands in exactly one of the nine bands.
[[nodiscard]] std::size_t moneyness_band(std::int64_t x_bps) noexcept;
/// The band's inclusive-low edge label, for emission (`-INF` for band 0).
[[nodiscard]] std::string band_label(std::size_t band);

// ---------------------------------------------------------------------------
// Weighted least squares over a retained point set.
// ---------------------------------------------------------------------------

/// A size-weighted straight line `y = a + b x`, or typed absent.
struct LineFit {
  Typed<double> intercept{0.0, Validity::MISSING};
  Typed<double> slope{0.0, Validity::MISSING};
  std::int64_t weight = 0;
  std::int64_t points = 0;
  std::int64_t distinct_x = 0;

  /// The fitted value at `x`, absent whenever the fit is absent.
  [[nodiscard]] Typed<double> at(double x) const noexcept;
};

/// A size-weighted parabola `y = c0 + c1 x + c2 x^2`; `curvature` is `2 c2`.
struct QuadFit {
  Typed<double> curvature{0.0, Validity::MISSING};
  std::int64_t points = 0;
  std::int64_t distinct_x = 0;
};

/// One (x, y, weight) observation of a fit.
struct FitPoint {
  double x = 0.0;
  double y = 0.0;
  std::int64_t weight = 0;
  std::int32_t x_key = 0;  // the exact integer x, for the distinct-strike count
};

[[nodiscard]] LineFit fit_line(const std::vector<FitPoint>& points, std::int64_t min_distinct,
                               std::int64_t min_weight);
[[nodiscard]] QuadFit fit_quadratic(const std::vector<FitPoint>& points, std::int64_t min_distinct,
                                    std::int64_t min_weight);
/// POPULATION two-pass weighted mean and standard deviation (the §W21-PIN-2
/// ratified reading). Two-pass because a one-pass `E[y^2]-E[y]^2` on IVs that
/// agree to four decimals is a subtraction of nearly equal numbers.
[[nodiscard]] Typed<double> weighted_mean(const std::vector<FitPoint>& points);
[[nodiscard]] Typed<double> weighted_stdev(const std::vector<FitPoint>& points);

// ---------------------------------------------------------------------------
// B1: the per-window, per-expiry traded-IV curve.
// ---------------------------------------------------------------------------

/// The skew object of ONE (window, expiry) cell.
///
/// ORIENTATION LAW, stated once and fixtured: `risk_reversal` is
/// `put_wing(-0.0150) - call_wing(+0.0150)`, so it is POSITIVE when the puts
/// are richer than the calls — the classic equity-index sign. `skew_slope` is
/// that difference per unit of ln-moneyness travelled (`/ 2 * kWingAnchorLn`),
/// so it carries the same sign. `curvature` is POSITIVE for a convex smile.
struct SkewCell {
  std::int64_t window = 0;
  std::int32_t expiration_day = 0;
  std::int32_t dte_days = 0;
  std::int64_t prints = 0;
  std::int64_t weight = 0;

  LineFit put_wing;
  LineFit call_wing;
  QuadFit smile;

  Typed<double> atm_iv{0.0, Validity::MISSING};
  /// Which definition produced `atm_iv`: "WINGS" (the average of the two wing
  /// intercepts at x=0, preferred) or "ATM_BAND" (the size-weighted mean IV of
  /// band 4 when a wing did not fit). Emitted so no reader has to guess.
  std::string atm_iv_source = "ABSENT";
  Typed<double> risk_reversal{0.0, Validity::MISSING};
  Typed<double> skew_slope{0.0, Validity::MISSING};
  Typed<double> curvature{0.0, Validity::MISSING};
  /// D3: dispersion of the traded IVs across strikes inside the cell, and the
  /// weighted mean of the per-second cross-strike dispersions (the same
  /// disorder read at two time scales).
  Typed<double> cross_strike_stdev{0.0, Validity::MISSING};
  Typed<double> same_second_stdev{0.0, Validity::MISSING};
  std::int64_t same_second_groups = 0;

  /// D4: the per-(band, right) size-weighted mean IV of the cell.
  std::array<Typed<double>, kBands * kRights> band_iv = absent_array<kBands * kRights>();
  std::array<std::int64_t, kBands * kRights> band_weight{};

  /// The window-to-window innovations (this cell minus the SAME expiry's cell
  /// in window-1). Absent in window 0 and whenever either side is absent.
  Typed<double> d_atm_iv{0.0, Validity::MISSING};
  Typed<double> d_risk_reversal{0.0, Validity::MISSING};
  Typed<double> d_skew_slope{0.0, Validity::MISSING};
  Typed<double> d_curvature{0.0, Validity::MISSING};
  /// D4's innovation VECTOR: which part of the smile moved.
  std::array<Typed<double>, kBands * kRights> d_band_iv = absent_array<kBands * kRights>();

  /// D1: size-weighted mean of (print IV - concurrent PROXY_VOL), in vol
  /// points. `plain` compares against the ATM PROXY_VOL as-is and is therefore
  /// only meaningful inside the ATM band; `skew_adjusted` translates the ATM
  /// level to each print's own moneyness using the PRIOR window's traded-IV
  /// wing fit (strictly prior, model-free) and is meaningful across the smile.
  Typed<double> richness_plain{0.0, Validity::MISSING};
  Typed<double> richness_skew_adjusted{0.0, Validity::MISSING};
  std::int64_t richness_points = 0;
  Typed<double> d_richness_plain{0.0, Validity::MISSING};
};

// ---------------------------------------------------------------------------
// B2: the term structure, per window, across every expiry.
// ---------------------------------------------------------------------------

struct TermWindow {
  std::int64_t window = 0;
  std::int64_t expiries = 0;
  std::int32_t near_dte = -1;
  std::int32_t far_dte = -1;
  /// True when `far_dte` is the largest available DTE because no expiry
  /// reached `kTermFarMinDteDays` — the ratio is still emitted, under a flag,
  /// never silently redefined.
  bool far_is_fallback = false;
  Typed<double> near_iv{0.0, Validity::MISSING};
  Typed<double> far_iv{0.0, Validity::MISSING};
  Typed<double> near_far_ratio{0.0, Validity::MISSING};
  /// Weighted LS slope of ATM IV on ln(1 + DTE days) across every expiry with a
  /// valid ATM IV. ln(1+DTE) rather than DTE because the term structure's own
  /// shape is logarithmic in time and 0DTE must be representable.
  Typed<double> term_slope{0.0, Validity::MISSING};
  Typed<double> d_near_far_ratio{0.0, Validity::MISSING};
  Typed<double> d_term_slope{0.0, Validity::MISSING};
};

// ---------------------------------------------------------------------------
// D2 / D5: per-window, per-band aggregates that are not curve objects.
// ---------------------------------------------------------------------------

struct BandWindow {
  std::int64_t window = 0;
  std::size_t band = 0;
  /// D2: size-weighted mean signed and absolute IV velocity, in vol points per
  /// second, plus the weighted mean age of the pair (the "age-aware" part: a
  /// velocity from a 3-second gap and one from a 20-minute gap are not the
  /// same measurement, and the census says which it saw).
  Typed<double> iv_velocity_signed{0.0, Validity::MISSING};
  Typed<double> iv_velocity_absolute{0.0, Validity::MISSING};
  Typed<double> iv_velocity_mean_gap_seconds{0.0, Validity::MISSING};
  std::int64_t iv_velocity_pairs = 0;
  /// D5: quote-certified signed size, all expiries and the 0DTE split.
  /// `v = +1` when the print is at or above the attached ask, `-1` at or below
  /// the bid, and UNDECIDABLE inside — never a guess, never zero-as-a-sign.
  std::int64_t signed_size = 0;
  std::int64_t signed_size_0dte = 0;
  std::int64_t decided_size = 0;
  std::int64_t undecidable_size = 0;
};

// ---------------------------------------------------------------------------
// The session-level admission census.
// ---------------------------------------------------------------------------

struct AdmissionCensus {
  std::int64_t rows_seen = 0;
  std::int64_t admitted = 0;
  std::int64_t rejected_null_cell = 0;
  std::int64_t rejected_right = 0;
  std::int64_t rejected_multi_leg = 0;
  std::int64_t rejected_attachment = 0;
  std::int64_t rejected_iv = 0;
  std::int64_t rejected_size = 0;
  std::int64_t rejected_spot = 0;
  std::int64_t rejected_moneyness = 0;
  std::int64_t rejected_window = 0;
  /// The independent cross-check: admitted prints whose band under the emitted
  /// 1s midpoint grid differs from their band under the attached
  /// `underlying_price`. Zero when no grid was supplied.
  std::int64_t grid_band_disagreements = 0;
  std::int64_t grid_compared = 0;
};

// ---------------------------------------------------------------------------
// The optional surface series (D1, D7, D8, D9).
// ---------------------------------------------------------------------------

/// Exactly what this module needs from the W2.1 block, in a shape a fixture can
/// build by hand. Absence is NaN for the reals and 0 for the u6 spot, matching
/// the emitted grid's own convention.
struct SurfaceSeries {
  static constexpr std::size_t kPlanes = 2;  // W21-PIN-1 Q2: DTE in {0,1} only
  std::int64_t seconds = 0;
  std::vector<std::int64_t> spot_u6;  // size == seconds
  std::vector<double> pv_mid;         // size == seconds * kPlanes
  std::vector<double> pv_bid;
  std::vector<double> pv_ask;

  [[nodiscard]] bool empty() const noexcept { return seconds == 0; }
  [[nodiscard]] double proxy_vol_mid(std::int64_t second, std::size_t plane) const noexcept;
};

/// D7's three-state code.
enum class VolState : std::uint8_t { FLAT = 0, SPIKING = 1, BLEEDING = 2, ABSENT = 3 };
[[nodiscard]] const char* vol_state_name(VolState state) noexcept;

/// D7/D8/D9 for ONE 30-minute window of the surface.
struct SurfaceWindow {
  std::int64_t window = 0;
  std::int64_t seconds_valid = 0;
  /// D7: realized variance of the 1s log-innovations of PROXY_VOL, per side.
  Typed<double> vol_of_vol_mid{0.0, Validity::MISSING};
  Typed<double> vol_of_vol_bid{0.0, Validity::MISSING};
  Typed<double> vol_of_vol_ask{0.0, Validity::MISSING};
  Typed<double> pv_level{0.0, Validity::MISSING};
  Typed<double> pv_relative_change{0.0, Validity::MISSING};
  VolState state = VolState::ABSENT;
  /// D8: response, fluctuation, and their ratio.
  Typed<double> fd_chi{0.0, Validity::MISSING};
  Typed<double> fd_sigma_vv{0.0, Validity::MISSING};
  Typed<double> fd_ratio{0.0, Validity::MISSING};
  Typed<double> d_fd_ratio{0.0, Validity::MISSING};
  std::int64_t fd_pairs = 0;
  std::int64_t fd_quiet_points = 0;
  /// D9: the third-order asymmetry of the 1s spot returns and of the PROXY_VOL
  /// innovations, and the joint sign state.
  Typed<double> a3_return{0.0, Validity::MISSING};
  Typed<double> a3_proxy_vol{0.0, Validity::MISSING};
  std::int64_t a3_joint_state = -1;
  std::int64_t a3_pairs = 0;
};

struct SurfaceDynamics {
  std::array<SurfaceWindow, kWindows> window{};
  Typed<double> state_threshold{0.0, Validity::MISSING};
};

/// D7/D8/D9 over a whole session's surface series. Pure function of the series
/// — no I/O, no clock, fixtureable by hand.
[[nodiscard]] SurfaceDynamics surface_dynamics(const SurfaceSeries& series, std::size_t plane);

// ---------------------------------------------------------------------------
// The session builder.
// ---------------------------------------------------------------------------

struct TradedIvOptions {
  /// The emitted 1s midpoint grid, for the moneyness cross-check only. Empty
  /// means the cross-check is not run (and its counters stay zero).
  const std::vector<std::int64_t>* grid_mid_u6 = nullptr;
  /// The W2.1 surface, for D1. Null means richness is typed absent.
  const SurfaceSeries* surface = nullptr;
};

struct TradedIvTables {
  std::int64_t ordinal = 0;
  std::string day;
  std::string tape;
  AdmissionCensus census;
  /// Every (window, expiry) cell that produced at least one admitted print, in
  /// (window, expiration_day) order.
  std::vector<SkewCell> cells;
  std::array<TermWindow, kWindows> term{};
  std::vector<BandWindow> bands;  // (window, band) order
  std::int64_t expiries = 0;
  std::int64_t contracts = 0;
};

/// Accumulates one session of option prints. The caller drives the reader (the
/// IWM one or the RUTW one — B5 says "same laws", and this class takes the
/// shared `OptionPrintRow`), so one implementation serves both tapes (D6).
class TradedIvSession {
 public:
  TradedIvSession(std::int64_t ordinal, std::string day, std::string tape, std::int64_t open_ms_b,
                  std::int64_t session_epoch_day, TradedIvOptions options = {});

  /// Folds ONE decoded print. Every rejection lands in the admission census.
  void observe(const qr::sources::OptionPrintRow& row);

  /// Closes the session and computes every cell, innovation and aggregate.
  [[nodiscard]] TradedIvTables finish();

 private:
  struct Point {
    std::int64_t second = 0;
    std::int64_t weight = 0;
    double iv = 0.0;
    double surface_pv = 0.0;  // NaN when absent
    std::int32_t x_bps = 0;
    std::int32_t dte_days = 0;
    std::uint8_t right = 0;
  };
  struct CellKey {
    std::int64_t window = 0;
    std::int32_t expiration_day = 0;
    friend bool operator<(const CellKey& l, const CellKey& r) noexcept {
      if (l.window != r.window) return l.window < r.window;
      return l.expiration_day < r.expiration_day;
    }
  };
  struct ContractKey {
    std::int32_t expiration_day = 0;
    std::int64_t strike_u6 = 0;
    std::uint8_t right = 0;
    friend bool operator<(const ContractKey& l, const ContractKey& r) noexcept {
      if (l.expiration_day != r.expiration_day) return l.expiration_day < r.expiration_day;
      if (l.strike_u6 != r.strike_u6) return l.strike_u6 < r.strike_u6;
      return l.right < r.right;
    }
  };
  struct LastPrint {
    std::int64_t ts_ms_b = 0;
    double iv = 0.0;
  };
  struct VelocityAccumulator {
    double weighted_signed = 0.0;
    double weighted_absolute = 0.0;
    double weighted_gap_seconds = 0.0;
    std::int64_t weight = 0;
    std::int64_t pairs = 0;
  };

  std::int64_t ordinal_;
  std::string day_;
  std::string tape_;
  std::int64_t open_ms_b_;
  std::int64_t session_epoch_day_;
  TradedIvOptions options_;

  AdmissionCensus census_{};
  std::map<CellKey, std::vector<Point>> cells_;
  std::map<ContractKey, LastPrint> last_print_;
  std::set<std::int32_t> expirations_;
  std::set<std::tuple<std::int32_t, std::int64_t, std::uint8_t>> contracts_;
  std::array<VelocityAccumulator, kWindows * kBands> velocity_{};
  std::array<BandWindow, kWindows * kBands> band_{};
};

/// Emits a whole session's tables into the census report.
void emit(Report& report, const TradedIvTables& tables);
void emit(Report& report, const std::string& session_key, const SurfaceDynamics& dynamics);

/// D6: the IWM-minus-RUTW traded-IV spread of the two tapes' NEAR-expiry ATM
/// IV, per window, with its window-to-window innovation. Both sides must be
/// VALID in a window or the spread is typed absent there.
struct CrossTapeSpread {
  std::array<Typed<double>, kWindows> spread = absent_array<kWindows>();
  std::array<Typed<double>, kWindows> d_spread = absent_array<kWindows>();
  std::array<Typed<double>, kWindows> ratio = absent_array<kWindows>();
};
[[nodiscard]] CrossTapeSpread cross_tape_spread(const TradedIvTables& left,
                                                const TradedIvTables& right);
void emit(Report& report, const std::string& key, const CrossTapeSpread& spread);

}  // namespace qr::ivx

#endif  // QR_IVX_IV_CROSS_HPP
