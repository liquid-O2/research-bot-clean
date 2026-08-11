// qr_w21/surface.hpp — W2.1 OPTION-QUOTE BLOCK CONSTRUCTORS.
//
// SPEC, in force order:
//   1. design/DESIGN_FEATURES.md §W21-PIN-1 (sha 0bb646c1e0de75e5) — the twelve
//      orchestrator rulings on D4 §7, which AMEND A2 where they say so;
//   2. FINAL_PLAN APPENDIX A2 (option-quote surface, straddle PROXY_VOL,
//      requote latency, coverage thinning) and its notation paragraph;
//   3. FINAL_PLAN APPENDIX B4 (the eight projected columns) and APPENDIX C
//      (Typed<T>, checked arithmetic, strictly-prior law).
//
// WHAT IS NOT HERE, AND WHY. A2's Greek-residual repricing block is NOT built:
// §W21-PIN-1 Q6/Q7 pin the interval, the exclusion gates and the reliability
// weight, but the UNIT of "sigma-rho-oriented resid_bps" is still open — bps of
// the contract's own mid and bps of the underlying are both readable from the
// text and give materially different channels once a bucket mean is taken over
// cheap OTM and expensive ATM contracts together. The implementer stop rule
// applies; the question is returned rather than answered.
//
// THE TRANSFORM LAW. qr_carriers' transform table is exhaustive FOR THE CARD's
// section-4 channels. A2 is a separately frozen design that states its own
// formulas (PROXY_VOL, Delta-log, Delta-W_S, the refill ratio), so those
// formulas govern verbatim here; every quantity A2 does NOT give a formula for
// is built by calling the table (`count_log1p` for sizes, `time_log1p_micros`
// for ages, `displacement_bps` for price displacements, `fraction` for
// fractions). No private eighth transform exists in this module.
//
// STRICTLY PRIOR, MECHANICALLY. Every constructor is driven by the 1s grid.
// The state used at grid second `s` is the state left by quote groups whose
// frame-B millisecond is STRICTLY BEFORE the endpoint of second `s`, and the
// spot at second `s` is that endpoint's carried midpoint — itself the last
// eligible NBBO mid strictly before the endpoint. A group landing exactly ON an
// endpoint belongs to the NEXT second, never to the endpoint that closes.
//
// BUCKET-EDGE CONVENTION (substrate law, not a lane choice). The bin carrier
// fixes this substrate's binning as RIGHT-OPEN — qr_carriers/src/native_order.cpp
// ("Right-open: the bin ends BEFORE its right edge"). The five moneyness bands
// therefore are, with edges {-150,-50,+50,+150} in bps of ln(K/m):
//     band 0: x < -150 | band 1: [-150,-50) | band 2: [-50,+50)
//     band 3: [+50,+150) | band 4: x >= +150
// so an exact edge always falls in the band ABOVE it. Fixtured at all four.
#ifndef QR_W21_SURFACE_HPP
#define QR_W21_SURFACE_HPP

#include <array>
#include <cstdint>
#include <filesystem>
#include <map>
#include <optional>
#include <span>
#include <vector>

#include "qr_carriers/transforms.hpp"
#include "qr_core/refusal.hpp"
#include "qr_core/validity.hpp"
#include "qr_registry/day_scope.hpp"
#include "qr_sources/option_quotes.hpp"
#include "qr_w20/mechanics.hpp"

namespace qr::w21 {

using qr::Expected;
using qr::Refusal;
using qr::RefusalCode;
using qr::Typed;
using qr::Validity;
using qr::carriers::kBpsScale;

// ---------------------------------------------------------------------------
// The pinned constants. Every one of them cites its ruling.
// ---------------------------------------------------------------------------

/// Q1: "x = ln(K/m) in bps, edges {-150,-50,+50,+150} -> 5 buckets".
inline constexpr std::array<std::int64_t, 4> kMoneynessEdgesBps{-150, -50, 50, 150};
inline constexpr std::size_t kMoneynessBands = 5;
/// Q2 (AMENDED BY MEASUREMENT): "quotes carry DTE in {0,1} only => surface =
/// 5 moneyness x 2 DTE x 2 right = 20 buckets".
inline constexpr std::size_t kDtePlanes = 2;
inline constexpr std::size_t kRights = 2;
inline constexpr std::size_t kBuckets = kMoneynessBands * kDtePlanes * kRights;
static_assert(kBuckets == 20, "W21-PIN-1 Q2: the surface is 5 x 2 x 2");

/// Q4: "Contract state: last strictly-prior quote, age-gate 300s".
/// Q5 uses the same gate for the straddle legs.
inline constexpr std::int64_t kContractAgeGateMs = 300'000;
/// Q4: "bucket VALID iff >=50% two-sided" — as an exact integer test,
/// 2 * two_sided >= contracts.
inline constexpr std::int64_t kValidTwoSidedNumerator = 2;
/// Q5: "none within |ln(K/m)|<=150bp => straddle absent".
inline constexpr std::int64_t kStraddleMaxAbsBps = 150;
/// Q3: "remaining time < 300s => PROXY_VOL typed absent".
inline constexpr std::int64_t kProxyVolGuardSeconds = 300;
/// Q3: "T = (expiry-day 16:00 ET close ts - t)/365.0y". 16:00 ET is a NAIVE-ET
/// (frame-B) wall-clock instant, so it is exact integer arithmetic on the
/// expiry day's epoch-day and needs no timezone rule.
inline constexpr std::int64_t kExpiryCloseSecondsIntoDay = 16 * 3600;
inline constexpr double kYearSeconds = 365.0 * 86400.0;
/// A2 / Q8: the shared horizon triplet for Delta-log PROXY_VOL and Delta-W_S.
inline constexpr std::array<std::int64_t, 3> kHorizonsSeconds{5, 30, 120};
/// Q11: "spot event = |Delta u| >= 0.5bp between consecutive grid seconds" —
/// half a basis point of m is m/20000, tested in exact integers.
inline constexpr std::int64_t kHalfBpDenominator = 20'000;
/// A2: "no-requote-5s fraction (diagnostic)".
inline constexpr std::int64_t kRequoteHorizonMs = 5'000;
/// Q9: "evaporation event = side total size drop >=50% between consecutive
/// seconds; refill ratio = size(t+5s)/size(t-1) clip [0,2]".
inline constexpr std::int64_t kRefillLookaheadSeconds = 5;
inline constexpr double kRefillRatioCap = 2.0;
inline constexpr std::int64_t kRefillWindowSeconds = 120;
/// Q10: "900s trailing median of the 60s-sampled bucket spread; expanding
/// window from open below 900s (min 120s else typed)".
inline constexpr std::int64_t kThinningSampleSeconds = 60;
inline constexpr std::int64_t kThinningMedianWindowSeconds = 900;
inline constexpr std::int64_t kThinningMinimumWindowSeconds = 120;
/// A2: "coverage thinning: valid-bucket fraction now vs 60s ago".
inline constexpr std::int64_t kThinningLookbackSeconds = 60;
/// Q12: "MODALITY_ABSENT = exactly ordinals 125..208 (84 sessions)".
inline constexpr std::int64_t kFirstCoveredOrdinal = 209;

// ---------------------------------------------------------------------------
// The bucket axis.
// ---------------------------------------------------------------------------

/// `10000 * ln(K/m)`, rounded half away from zero. Q1 names the log ratio, and
/// the small-angle substitute (K-m)/m is NOT it: at the +150bp edge the two
/// differ by 1.1bp, which would move contracts across a band boundary.
[[nodiscard]] Expected<std::int64_t, Refusal> moneyness_log_bps(std::int64_t strike_u6,
                                                                std::int64_t spot_u6) noexcept;

/// The RIGHT-OPEN band of `x_bps` (see the header note). Total: every integer
/// lands in exactly one of the five bands.
[[nodiscard]] std::size_t moneyness_band(std::int64_t x_bps) noexcept;

/// The surface slot of one contract, or absent when the contract is off the
/// surface: DTE outside {0,1} (Q2) or a right the tape did not name.
[[nodiscard]] std::optional<std::size_t> bucket_index(std::int64_t x_bps, std::int64_t dte_days,
                                                      qr::sources::Right right) noexcept;

/// Decomposition of a slot, for emission and fixtures.
struct BucketKey {
  std::size_t moneyness_band = 0;
  std::size_t dte_plane = 0;
  std::size_t right = 0;
};
[[nodiscard]] BucketKey bucket_key(std::size_t index) noexcept;
/// sigma-rho orientation of a slot: rho = +1 CALL / -1 PUT (APPENDIX A
/// notation), sigma = +1 LONG / -1 SHORT.
[[nodiscard]] int orientation(std::size_t bucket, bool long_side) noexcept;

// ---------------------------------------------------------------------------
// One grid second of one bucket (Q4).
// ---------------------------------------------------------------------------

/// Q4, verbatim: "Bucket channels: sum bid_size, sum ask_size, size-weighted
/// mean spread_bps, size-weighted mean log1p(age_us), two-sided fraction
/// (validity; bucket VALID iff >=50% two-sided), size-weighted stdev of
/// spread_bps ... Price-LEVEL channels live in the ATM-straddle block (Q5), not
/// in buckets."
///
/// THERE IS NO PRICE FIELD IN THIS STRUCT. That is the Q4 amendment expressed
/// as a type: a bucket cannot average raw option prices across strikes because
/// it never holds one.
struct BucketSecond {
  /// Contracts whose last strictly-prior quote is inside the 300s age gate.
  std::int64_t contracts = 0;
  /// Of those, the ones quoting two-sided-positive (`bid>0 && ask>bid`).
  std::int64_t two_sided = 0;
  std::int64_t bid_size_sum = 0;
  std::int64_t ask_size_sum = 0;
  /// The size-weighted moments over the TWO-SIDED members (a one-sided quote
  /// has no spread at all), weight = that member's `bid_size + ask_size`.
  Typed<double> mean_spread_bps{};
  Typed<double> stdev_spread_bps{};
  /// Over EVERY member (an age exists whether or not the quote is two-sided).
  Typed<double> mean_log1p_age_micros{};
  Typed<double> two_sided_fraction{};
  /// Q4's validity: `2 * two_sided >= contracts`, and never on an empty bucket.
  bool valid = false;

  /// The transform-table channel forms of the two size sums.
  [[nodiscard]] Typed<double> bid_size_channel() const noexcept;
  [[nodiscard]] Typed<double> ask_size_channel() const noexcept;
  /// The exact size-weighted mean spread in bps, as an integer, for censuses
  /// and for Q10's median series (a median of a rounded series and a rounded
  /// median are different numbers; the census publishes the exact one).
  [[nodiscard]] Typed<std::int64_t> mean_spread_bps_exact() const noexcept;
};

/// One grid second of the whole surface.
struct SurfaceSecond {
  std::array<BucketSecond, kBuckets> bucket{};
  /// The endpoint's carried midpoint (u6); 0 means the grid had none.
  std::int64_t spot_u6 = 0;
  /// Live contracts across all buckets, and how many of those are one-sided —
  /// A2's coverage-thinning "one-sided fraction".
  std::int64_t live_contracts = 0;
  std::int64_t one_sided_contracts = 0;
  [[nodiscard]] std::int64_t valid_buckets() const noexcept;
};

// ---------------------------------------------------------------------------
// The ATM straddle and PROXY_VOL (Q3, Q5, Q8).
// ---------------------------------------------------------------------------

/// Q5: per expiry per second. `absent` carries WHY, so a census can separate
/// "no strike inside 150bp" from "the guard fired".
struct StraddleSecond {
  std::int64_t strike_u6 = 0;
  std::int64_t moneyness_bps = 0;
  std::int64_t straddle_bid_u6 = 0;
  std::int64_t straddle_ask_u6 = 0;
  std::int64_t straddle_mid_u6 = 0;
  /// A2: "width W_S = S_ask - S_bid".
  std::int64_t width_u6 = 0;
  /// A2: PROXY_VOL = S/(m*sqrt(T)) — "label PROXY_VOL, never IV". Bid-side and
  /// ask-side are carried SEPARATELY, as A2 requires.
  Typed<double> proxy_vol_mid{};
  Typed<double> proxy_vol_bid{};
  Typed<double> proxy_vol_ask{};
  bool present = false;
  Validity absence = Validity::MODALITY_ABSENT;
};

/// The channel block A2 names: "channels Delta-log PROXY_VOL {5,30,120}s,
/// bid-side/ask-side straddle vol-proxies SEPARATELY + width W_S = S_ask-S_bid
/// + Delta-W_S" (horizons pinned to the same triplet by Q8).
struct StraddleChannels {
  std::array<Typed<double>, 3> dlog_proxy_vol_mid{};
  std::array<Typed<double>, 3> dlog_proxy_vol_bid{};
  std::array<Typed<double>, 3> dlog_proxy_vol_ask{};
  /// A2 defines W_S = S_ask - S_bid, which is a u6 PRICE quantity, and gives no
  /// denominator for it. It is therefore emitted verbatim in u6 (exact integers
  /// carried as doubles) and NOT normalised: choosing between "bps of the
  /// straddle mid" and "bps of the underlying" is the same open unit question
  /// the Greek-residual block is stopped on, and inventing one here would put
  /// an unpinned constant into a frozen family.
  std::array<Typed<double>, 3> dwidth_u6{};
  Typed<double> proxy_vol_mid{};
  Typed<double> proxy_vol_bid{};
  Typed<double> proxy_vol_ask{};
  Typed<double> width_u6{};
};

/// Q3's T in years, or absent when the 300s guard fires. `ts_ms_b` and the
/// expiry day are both frame-B, so this is exact integer arithmetic.
[[nodiscard]] Typed<double> years_to_expiry(std::int64_t ts_ms_b,
                                            std::int64_t expiry_epoch_day) noexcept;

/// PROXY_VOL = S/(m*sqrt(T)). Absent when S<=0, m<=0 or T is absent.
[[nodiscard]] Typed<double> proxy_vol(std::int64_t straddle_u6, std::int64_t spot_u6,
                                      Typed<double> years) noexcept;

// ---------------------------------------------------------------------------
// Requote latency (Q11) and coverage thinning (Q10 + A2).
// ---------------------------------------------------------------------------

/// One spot-move event and its outcome. The denominator is FROZEN at the event
/// second (Q11: "denominator frozen at event time; no lookahead").
struct RequoteEventRecord {
  std::int64_t event_second = 0;
  std::int64_t denominator_buckets = 0;
  std::int64_t latency_micros = 0;
  bool half_reached = false;
  bool any_reached = false;
};

struct ThinningSecond {
  Typed<double> valid_bucket_fraction{};
  /// A2: "valid-bucket fraction now vs 60s ago" — the difference, absent until
  /// 60s of session have elapsed.
  Typed<double> valid_bucket_fraction_delta_60s{};
  Typed<double> one_sided_fraction{};
  /// A2 + Q10: fraction of the VALID buckets whose current size-weighted mean
  /// spread exceeds twice its own 900s trailing median of the 60s samples.
  Typed<double> wide_vs_trailing_median_fraction{};
};

/// Q9's channels for one bucket at one second, sigma-rho oriented on the
/// difference (a per-side MEAN refill ratio is unsigned, so orienting it would
/// only flip the sign of a positive number).
struct RefillSecond {
  Typed<double> mean_refill_bid{};
  Typed<double> mean_refill_ask{};
  Typed<double> oriented_refill_difference{};
};

// ---------------------------------------------------------------------------
// The session constructor.
// ---------------------------------------------------------------------------

struct SurfaceOptions {
  /// Retain the per-second surface, straddle and channel tables. Off by default
  /// for the same reason qr_carriers' group vectors are: a session is 23,401
  /// seconds x 20 buckets and a census run must not pay for a table it does not
  /// read.
  bool retain_seconds = false;
};

/// The whole-session W2.1 block for ONE admitted session.
class SurfaceBuilder {
 public:
  /// Q12: ordinals 125..208 carry no option-quote payload, so the block is
  /// `MODALITY_ABSENT` for the entire session — a typed state, never an error
  /// and never a zero-filled surface.
  [[nodiscard]] static bool session_is_modality_absent(std::int64_t ordinal) noexcept {
    return ordinal < kFirstCoveredOrdinal;
  }

  [[nodiscard]] static Expected<SurfaceBuilder, Refusal> build(
      const DayScope& scope, const std::filesystem::path& corpus_root,
      const std::filesystem::path& tape_side_dir, SurfaceOptions options = {});

  [[nodiscard]] bool modality_absent() const noexcept { return modality_absent_; }
  [[nodiscard]] Validity modality() const noexcept {
    return modality_absent_ ? Validity::MODALITY_ABSENT : Validity::VALID;
  }
  [[nodiscard]] std::int64_t seconds() const noexcept { return seconds_; }
  [[nodiscard]] const std::vector<SurfaceSecond>& surface() const noexcept { return surface_; }
  /// Per-second, PER-EXPIRY-PLANE channels (A2: "per-expiry ATM straddle"),
  /// indexed `second * kDtePlanes + plane`.
  [[nodiscard]] const std::vector<StraddleChannels>& straddle_channels() const noexcept {
    return straddle_channels_;
  }
  [[nodiscard]] const std::vector<ThinningSecond>& thinning() const noexcept { return thinning_; }
  [[nodiscard]] const std::vector<RequoteEventRecord>& requote_events() const noexcept {
    return requote_events_;
  }
  /// Per-second refill channels, bucket-major (`second * kBuckets + bucket`).
  [[nodiscard]] const std::vector<RefillSecond>& refill() const noexcept { return refill_; }

  // --- census counters (published by the audit tool) ---
  [[nodiscard]] std::int64_t rth_rows() const noexcept { return rth_rows_; }
  [[nodiscard]] std::int64_t groups() const noexcept { return groups_; }
  [[nodiscard]] std::int64_t contracts() const noexcept { return contracts_; }
  [[nodiscard]] std::int64_t off_surface_contracts() const noexcept {
    return off_surface_contracts_;
  }
  [[nodiscard]] std::int64_t valid_bucket_seconds() const noexcept { return valid_bucket_seconds_; }
  [[nodiscard]] std::int64_t bucket_seconds() const noexcept { return bucket_seconds_; }
  [[nodiscard]] std::int64_t straddle_present_seconds() const noexcept {
    return straddle_present_seconds_;
  }
  [[nodiscard]] std::int64_t straddle_guard_seconds() const noexcept {
    return straddle_guard_seconds_;
  }
  [[nodiscard]] std::int64_t straddle_no_strike_seconds() const noexcept {
    return straddle_no_strike_seconds_;
  }
  [[nodiscard]] std::int64_t spot_absent_seconds() const noexcept { return spot_absent_seconds_; }
  [[nodiscard]] std::int64_t evaporation_events() const noexcept { return evaporation_events_; }
  [[nodiscard]] std::int64_t no_requote_5s_events() const noexcept { return no_requote_5s_; }
  [[nodiscard]] const w20::DenseCounter& latency_micros_census() const noexcept {
    return latency_micros_;
  }
  [[nodiscard]] const w20::DenseCounter& spread_bps_census() const noexcept { return spread_bps_; }
  [[nodiscard]] const w20::DenseCounter& proxy_vol_census() const noexcept { return proxy_vol_; }

 private:
  SurfaceBuilder() = default;

  bool modality_absent_ = false;
  std::int64_t seconds_ = 0;
  std::vector<SurfaceSecond> surface_;
  std::vector<StraddleChannels> straddle_channels_;
  std::vector<ThinningSecond> thinning_;
  std::vector<RequoteEventRecord> requote_events_;
  std::vector<RefillSecond> refill_;
  std::int64_t rth_rows_ = 0;
  std::int64_t groups_ = 0;
  std::int64_t contracts_ = 0;
  std::int64_t off_surface_contracts_ = 0;
  std::int64_t valid_bucket_seconds_ = 0;
  std::int64_t bucket_seconds_ = 0;
  std::int64_t straddle_present_seconds_ = 0;
  std::int64_t straddle_guard_seconds_ = 0;
  std::int64_t straddle_no_strike_seconds_ = 0;
  std::int64_t spot_absent_seconds_ = 0;
  std::int64_t evaporation_events_ = 0;
  std::int64_t no_requote_5s_ = 0;
  w20::DenseCounter latency_micros_;
  w20::DenseCounter spread_bps_;
  w20::DenseCounter proxy_vol_;
};

/// The census audit of one built session (D-006: "a constructor is built only
/// with spec + red-first fixture proof + census audit").
void emit(w20::CensusReport& report, std::int64_t ordinal, const std::string& day,
          const SurfaceBuilder& built);

// ---------------------------------------------------------------------------
// The pure per-second reducers, exposed so a fixture can hand-build every input
// and assert a hand-computed literal (APPENDIX C's code shape).
// ---------------------------------------------------------------------------

/// One contract's live state as the reducers see it.
struct LiveQuote {
  std::int64_t bid_u6 = 0;
  std::int64_t ask_u6 = 0;
  std::int64_t bid_size = 0;
  std::int64_t ask_size = 0;
  /// Age of the last strictly-prior quote at the grid second's endpoint, in
  /// checked microseconds (Q11: "age = grid-second end - contract's last
  /// strictly-prior quote_ts").
  std::int64_t age_micros = 0;
  [[nodiscard]] bool two_sided() const noexcept { return bid_u6 > 0 && ask_u6 > bid_u6; }
};

/// Q4's reduction of one bucket's members. Members are supplied in the caller's
/// canonical order and the reduction is order-invariant by construction: the
/// moments are computed from exact integer sums of size-weighted terms before
/// any division.
[[nodiscard]] BucketSecond reduce_bucket(std::span<const LiveQuote> members);

/// Q5's straddle selection over one expiry's live legs. `calls` and `puts` are
/// keyed by strike; the nearest strike to `spot_u6` with BOTH legs two-sided
/// and inside the age gate wins, ties are undecidable and refuse.
struct StraddleLegs {
  std::map<std::int64_t, LiveQuote> calls;
  std::map<std::int64_t, LiveQuote> puts;
};
[[nodiscard]] StraddleSecond select_straddle(const StraddleLegs& legs, std::int64_t spot_u6,
                                             std::int64_t ts_ms_b, std::int64_t expiry_epoch_day);

}  // namespace qr::w21

#endif  // QR_W21_SURFACE_HPP
