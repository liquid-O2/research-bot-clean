// qr_gen/levels.hpp — the LEVEL LEDGER (PORT_M1_SPEC §4 / D-050) restricted to
// the SEVEN KEPT families: the six of CC-M1-3.3 plus CC-M1-6.1's OR_EXT.
//
//   FVOL_LADDER  anchor +- Q_q(range/sigma_hat) x sigma_hat, q in {10,25,50,75,90}
//   FVOL_BAND    anchor +- k x sigma_hat, k in {0.5, 1.0, 1.5, 2.0}
//                anchors = prev settle (from second 0) and each phase open
//   NDAY         N-session lookback H/L, N in {2,3,5,10,20}
//   PRIOR_DAY    prior session H / L / settle
//   PHASE_HL     per-segment H/L, segment in {OVERNIGHT,TOKYO,LONDON,NY},
//                lookback in {1,2,3,5} sessions
//   VWAP         causal session/phase VWAP line and +- {2.0, 2.5} x sigma_vwap
//                (D-053; the +-1/+-2 set is superseded)
//   OR_EXT       CC-M1-6.1 opening-range extensions, OR_H + k x OR_range and
//                OR_L - k x OR_range over k in {0.5, 1.0, 1.5, 2.0}, in the SIX
//                ADOPTED CELLS ONLY (SI OR30 TOKYO/LONDON/NY + OR60
//                TOKYO/LONDON; NKD OR30 LONDON; HG NONE — its 2.2-2.8pp
//                marginals missed the 3pp bar, and the empty set is the
//                adoption, not an omission). G2-REJECT / G2-RECLAIM fire at an
//                OR_EXT level exactly like at any other kept level: no new
//                confirmation type, no special case.
//
// OR_EXT IS DOUBLY SCOPED, and both scopes are laws with mutants:
//   SEGMENT  outside its own phase the level DOES NOT EXIST — it can neither be
//            touched nor arm nor resolve there. The census's target is
//            REST_OF_WINDOW|segment, so a TOKYO opening range says nothing
//            about a NEW YORK price. The exclusion is NaN (never 0, never
//            +inf): every consumer downstream treats a NaN second as
//            unobserved.
//   SESSION  its identity, virginity and touch count never cross sessions, even
//            when tomorrow's construction lands on the same tick.
//
// The RETIRED sources (FVOL_LADDER_RS, PRIOR_WEEK, PROFILE, DEV_POC, ROUND) are
// not built: a level's arm/touch state machine runs per level and its ledger
// identity is keyed by the level's own name, so dropping a family cannot move
// any kept family's touches. That independence is a test, not a hope.
//
// STATE MACHINE (§4, verbatim):
//   tol      = max(2 x tick_$, 0.05 x ATR14_$) / mult
//   ARM      >= 300 observed seconds with |mid - L| > 2 x tol; re-arms at every
//            phase boundary
//   TOUCH    the first observed second with |mid - L| <= tol while ARMED
//   VIRGIN   never within tol since creation (arming-independent)
//   OUTCOME  REJECT  |  BREAK  |  RECLAIM, resolved in the 15-minute window
#ifndef QR_GEN_LEVELS_HPP
#define QR_GEN_LEVELS_HPP

#include <cstdint>
#include <map>
#include <string>
#include <utility>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_gen/families.hpp"
#include "qr_gen/gensession.hpp"
#include "qr_gen/tables.hpp"
#include "qr_skel/geom.hpp"

namespace qr::gen {

/// CC-M1-3.3 KEPT level families + CC-M1-6.1's OR_EXT. The enum ORDER is the
/// bit order of the roster's `level_fam_mask`
/// (b10_generation_v3.KEPT_LEVEL_FAMILIES = b8's six, then OR_EXT APPENDED —
/// appended, so every bit the v2 roster ever wrote keeps its meaning).
enum class LevelFamily : std::uint8_t {
  FVOL_LADDER = 0,
  FVOL_BAND = 1,
  NDAY = 2,
  PRIOR_DAY = 3,
  PHASE_HL = 4,
  VWAP = 5,
  OR_EXT = 6,
};
inline constexpr std::size_t kLevelFamilyCount = 7;
[[nodiscard]] const char* level_family_name(LevelFamily f);

/// CC-M1-6.1(1) verbatim: the adopted (phase index, or-minutes) cells of one
/// asset, in the order b10_levels_v4.OREXT_ADOPTED spells them. HG's empty list
/// IS the adoption.
[[nodiscard]] std::vector<std::pair<int, int>> orext_adopted_cells(qr::futsess::Asset asset);

// --- §4 / §6 state-machine constants ---------------------------------------
inline constexpr std::int32_t kArmSeconds = 300;
inline constexpr double kArmDistanceMult = 2.0;
inline constexpr double kTolTicks = 2.0;
inline constexpr double kTolAtrFrac = 0.05;
inline constexpr double kRejectAtrFrac = 0.11;
inline constexpr double kRejectTicks = 6.0;
inline constexpr std::int32_t kRejectWindow = 900;
inline constexpr std::int32_t kBreakHold = 60;
inline constexpr std::int32_t kReclaimHold = 120;

// --- §4 source parameters ---------------------------------------------------
inline constexpr std::size_t kFvolKCount = 4;
inline constexpr double kFvolK[kFvolKCount] = {0.5, 1.0, 1.5, 2.0};
inline constexpr std::size_t kNdayCount = 5;
inline constexpr int kNdayLookbacks[kNdayCount] = {2, 3, 5, 10, 20};
inline constexpr std::size_t kPhaseLbCount = 4;
inline constexpr int kPhaseLookbacks[kPhaseLbCount] = {1, 2, 3, 5};
/// D-053: the VWAP family is the line itself plus +-2.0 and +-2.5 sigma_vwap.
inline constexpr std::size_t kVwapBandCount = 5;
inline constexpr double kVwapBands[kVwapBandCount] = {0.0, 2.0, -2.0, 2.5, -2.5};

enum class Outcome : std::int8_t { NONE = 0, REJECT = 1, BREAK = 2, RECLAIM = 3 };

/// One level active in one session.
struct LevelDef {
  std::string key;              ///< the ledger identity name (source + params)
  LevelFamily family = LevelFamily::VWAP;
  double price = 0.0;           ///< NaN for a dynamic level
  std::int32_t active_from = 0; ///< session second the level exists from
  bool dynamic = false;
  std::vector<double> series;   ///< price at each MID-SANE second, dynamic only
  /// SEGMENT SCOPE: the phase index this level only exists inside; -1 = none.
  std::int8_t scope_phase = -1;
  /// SESSION SCOPE: an intraday object whose identity must NOT persist across
  /// sessions even when tomorrow's construction lands on the same tick.
  bool session_scoped = false;
};

/// One resolved touch. Seconds are absolute session seconds; -1 = never.
struct Touch {
  std::int32_t touch_sec = -1;
  std::int32_t level_row = -1;
  LevelFamily family = LevelFamily::VWAP;
  double level_price = 0.0;
  double mid = 0.0;
  std::int8_t approach_side = 0;  ///< +1 approached from above, -1 from below
  Outcome outcome = Outcome::NONE;
  std::int32_t outcome_sec = -1;
  std::int32_t reject_sec = -1;
  std::int32_t break_sec = -1;
  std::int32_t reclaim_sec = -1;
  std::int8_t virgin_at_touch = 0;
  std::int32_t touch_index = 0;
};

/// One ledger row as of the session end (the D-050 provenance record).
struct LedgerRow {
  LevelFamily family = LevelFamily::VWAP;
  double price = 0.0;
  std::int32_t created_d8 = 0;
  std::int8_t dynamic = 0;
  std::int8_t virgin = 0;
  std::int32_t touch_count = 0;
  std::int32_t last_test_sec = -1;
  std::int8_t last_test_outcome = 0;
  std::int32_t first_near_sec = -1;
};

/// Cross-session ledger memory: creation date, touch count, virginity and last
/// test survive as long as the source keeps producing that price.
struct LevelState {
  std::int32_t created_d8 = 0;
  std::int32_t touch_count = 0;
  bool virgin = true;
  std::int32_t last_test_sec = -1;
  Outcome last_test_outcome = Outcome::NONE;
};
using LevelRegistry = std::map<std::string, LevelState>;

struct SessionLedger {
  std::vector<LedgerRow> rows;
  std::vector<Touch> touches;
  double tol_px = 0.0;
  double reject_move_px = 0.0;
};

/// Every KEPT-family level active in this session, with its creation second.
/// `asset` selects the CC-M1-6.1 OR_EXT cells, which are appended LAST — the
/// same position b3_levels.build_levels gives them, so the ledger's row order
/// is the oracle's row order.
[[nodiscard]] std::vector<LevelDef> build_levels(qr::futsess::Asset asset,
                                                 const qr::skel::AssetGeom& geom, double px_scale,
                                                 const GenSession& s, std::int32_t date8,
                                                 const V1History& hist, std::int64_t hist_index,
                                                 const FvolForecasts& fvol);

/// Run the §4 arm/touch/outcome machine over `levels`, advancing `reg`.
[[nodiscard]] SessionLedger run_ledger(const qr::skel::AssetGeom& geom, const GenSession& s,
                                       std::int32_t date8, double atr14_usd,
                                       const std::vector<LevelDef>& levels, LevelRegistry* reg);

// --- the pieces, exposed so the test suite can drive them directly ----------

/// SEGMENT SCOPE (CC-M1-6.1): overwrite (mid - level) with NaN at every second
/// outside the level's own phase. NaN is the typed exclusion — never 0, never
/// +inf — because every consumer (the near/far masks, the approach-side scan,
/// the outcome comparisons) reads a NaN second as UNOBSERVED. A scope_phase of
/// -1 leaves the series untouched.
void scope_diff(std::vector<double>* diff, const std::vector<std::int8_t>& phase_v,
                std::int8_t scope_phase);

/// §4 arm/touch scan over one level's |mid - L| series at the MID-SANE seconds.
/// `first_near` is the first position within tol at or after `active_from`.
struct TouchScan {
  std::vector<std::int64_t> touches;
  std::int64_t first_near = -1;
};
[[nodiscard]] TouchScan touch_scan(const std::vector<double>& dist,
                                   const std::vector<std::int8_t>& phase_v, std::int64_t active_from,
                                   double tol);

/// §6 outcome resolution for one touch. `diff` = mid - L at the MID-SANE
/// seconds `secs`; `app` = the approach side.
struct TouchOutcome {
  Outcome outcome = Outcome::NONE;
  std::int32_t outcome_sec = -1;
  std::int32_t reject_sec = -1;
  std::int32_t break_sec = -1;
  std::int32_t reclaim_sec = -1;
};
[[nodiscard]] TouchOutcome classify_touch(const std::vector<double>& diff,
                                          const std::vector<std::int32_t>& secs, std::int64_t ti,
                                          std::int8_t app, double tol, double reject_move);

}  // namespace qr::gen

#endif  // QR_GEN_LEVELS_HPP
