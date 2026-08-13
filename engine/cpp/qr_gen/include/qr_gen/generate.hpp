// qr_gen/generate.hpp — PRODUCTION EVENT GENERATION (PORT_M1B_SPEC §1 S2).
//
// The C++ home of the union roster. Its acceptance is a candidate-EXACT
// differential against the frozen S1-v3 Python oracle
// (engine/port_m1/b10_generation_v3.py at the S1.1+S1.2 freeze commit bec58a9,
// receipted by artifacts/cache/port/m1/generation_v3/ORACLE_FREEZE.tsv): same
// id set, same row order, same value in every stored field, over every session.
//
// WHAT IS GENERATED (all of it on MID-SANE seconds only, D-054):
//   G1            ZigZag confirmations over the FOUR-rung ladder
//                 {0.05, 0.075, 0.11, 0.15} x ATR14($) under the §1 floors
//                 max(4 x tick_$, 2 x phase-median spread_$); decision second =
//                 confirmation + tau* (CC-M1-3.1, tau* = 120s, all assets).
//                 The 0.05 rung is tagged G1_FINE, the coarse three G1.
//   G1_FAST_OPEN  ADDITIVE (CC-M1-5 D13): a confirmation landing in the first
//                 300s after a phase open ALSO emits a candidate at delay 15s
//                 under its own family tag — beside the tau* one, never instead
//                 of it. G1 rungs only (D14); G2 keeps tau* everywhere.
//   G2_REJECT     a level touch that rejects (§6), decision = confirmation+tau*
//                 — now including births at the CC-M1-6.1 OR_EXT levels
//   G2_RECLAIM    a level break reclaimed within 30 MINUTES of the break
//                 (CC-M1-3.5), decision = reclaim confirmation + tau*
//
// THE FOUR CC-M1-7.1 DISCOVERY FAMILIES (S1.2, adopted on conditional value):
//   NEWS_WINDOW   a G1 confirmation in the first 600s after a scheduled release
//                 (the fixed 08:30/10:00 ET slots + FOMC 14:00 ET on the
//                 meeting's last day), SINGLE 15s delay. BOJ deferred (FD-2).
//   MICRO_OPEN    a G1 confirmation in the first 300s after the Tokyo lunch
//                 reopen (12:30 JST) or the US cash open (09:30 ET), 15s delay
//                 — the FAST-OPEN construction on opens beyond the 3 phases.
//   POST_SHOCK    the FIRST confirmation (G1 or G2) strictly after a causal
//                 shock episode ends, delay tau*. Low supply, largest
//                 per-candidate edge, and one of the two families that survive
//                 BOTH the phase-close and the peak-exit readings (CC-M1-8.2).
//   FIRST_TEST    NKD ONLY (CC-M1-7.1: a feature, not a family, on SI/HG): the
//                 session's earliest confirming touch per kept level family,
//                 delay tau*; the level's first-ever touch is carried as a FLAG.
//
// AND ONE FLAG, NEVER A FAMILY (CC-M1-7.2 / V3-4 — it fires on 36-43% of
// candidates and must not be read as supply): F-D6 EXHAUSTION-AT-EXTENSION.
// FAST-CLOSE (F-D1) is RETIRED and is never generated.
//
// DEDUP: (session, decision_sec, side) -> ONE candidate; family, rung, level
// and flag tags are UNIONED and confirmation_sec is the EARLIEST confirmation
// mapping to that decision second.
//
// The label fields of each candidate (prefix-maxima skeleton, horizon marks,
// MFE/MAE landmarks) are produced by qr_skel::compute_anchor at the d0 anchor —
// the same code, already byte-parity-proven against this roster in S3. This
// engine does not own a second copy of that arithmetic.
#ifndef QR_GEN_GENERATE_HPP
#define QR_GEN_GENERATE_HPP

#include <cstdint>
#include <map>
#include <string>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_gen/calendar.hpp"
#include "qr_gen/families.hpp"
#include "qr_gen/levels.hpp"
#include "qr_gen/tables.hpp"
#include "qr_skel/engine.hpp"
#include "qr_skel/skeleton.hpp"

namespace qr::gen {

using qr::futsess::Asset;

// --- CC-M1-3 / CC-M1-5 generation constants ---------------------------------
inline constexpr std::int32_t kTauStar = 120;
inline constexpr std::size_t kRungCount4 = 4;
/// bit 0 = G1-FINE, then the m0 three-rung ladder.
inline constexpr double kRungs[kRungCount4] = {0.05, 0.075, 0.11, 0.15};
inline constexpr std::uint8_t kFineBit = 0b0001;
inline constexpr std::uint8_t kCoarseMask = 0b1110;
inline constexpr std::int32_t kFastOpenWindow = 300;
inline constexpr std::int32_t kFastOpenDelay = 15;
inline constexpr std::int32_t kReclaimBoundSec = 1800;
inline constexpr double kRungFloorTicks = 4.0;
inline constexpr double kRungFloorSpreadMult = 2.0;

/// Family bits of the roster's `fam_mask` (b10_generation_v3.FAMILIES order —
/// b8's five, then the four adopted families APPENDED, so every bit the v2
/// roster ever wrote keeps its meaning). Nine families no longer fit a uint8.
inline constexpr std::uint16_t kFamG1 = 1 << 0;
inline constexpr std::uint16_t kFamG1Fine = 1 << 1;
inline constexpr std::uint16_t kFamG1FastOpen = 1 << 2;
inline constexpr std::uint16_t kFamG2Reject = 1 << 3;
inline constexpr std::uint16_t kFamG2Reclaim = 1 << 4;
inline constexpr std::uint16_t kFamNewsWindow = 1 << 5;
inline constexpr std::uint16_t kFamMicroOpen = 1 << 6;
inline constexpr std::uint16_t kFamPostShock = 1 << 7;
inline constexpr std::uint16_t kFamFirstTest = 1 << 8;
inline constexpr std::size_t kFamilyCount = 9;
[[nodiscard]] const char* family_name(std::size_t bit_index);

/// CC-M1-7.2 candidate FLAGS. F-D6 is a flag and never a family; the virgin bit
/// is FIRST_TEST's own qualifier.
inline constexpr std::uint8_t kFlagOrExtBeyond = 1 << 0;      ///< adopted cells
inline constexpr std::uint8_t kFlagOrExtBeyondAny = 1 << 1;   ///< all cells
inline constexpr std::uint8_t kFlagFirstTestVirgin = 1 << 2;

/// CC-M1-7.1: F-D5 is a FAMILY on NKD and a feature elsewhere.
[[nodiscard]] bool first_test_is_a_family(Asset asset);

/// One confirmed ZigZag pivot, deduped across rungs by (second, side).
struct Confirmation {
  std::int32_t conf_sec = 0;
  std::int8_t side = 0;
  std::uint8_t rung_mask = 0;
};

/// One emission BEFORE dedup: a decision second and what produced it.
struct Emission {
  std::int32_t dec_sec = 0;
  std::int8_t side = 0;
  std::uint16_t fam_bits = 0;
  std::uint16_t level_bits = 0;
  std::uint8_t rung_mask = 0;
  std::int32_t conf_sec = 0;
  std::uint8_t flags = 0;
};

// --- the pieces, exposed so the test suite can drive them directly ----------

/// §1 per-phase confirmation threshold in PRICE units for one rung:
/// round_half_up(max(rung x ATR14($), 4 x tick_$, 2 x phase-median spread_$)
///               / mult, tick_px).
[[nodiscard]] double rung_threshold_px(const qr::skel::AssetGeom& geom, double rung, double atr_usd,
                                       double phase_median_spread_usd);

/// The causal ZigZag confirmation scan (m0 §8 sub-pass 1, c_c_roster.zigzag_scan).
/// `thr` is the per-observation threshold, so a confirmation second is always
/// judged under ITS OWN phase's threshold.
struct Pivot {
  double pivot_px = 0.0;
  std::int32_t pivot_sec = 0;
  std::int32_t conf_sec = 0;
  std::int8_t side = 0;
};
[[nodiscard]] std::vector<Pivot> zigzag_scan(const std::vector<std::int32_t>& secs,
                                             const std::vector<double>& mids,
                                             const std::vector<double>& thr);

/// Session second of every phase open: second 0, then every phase-tag change.
[[nodiscard]] std::vector<std::int32_t> phase_open_secs(const std::vector<std::int8_t>& phase_tag);

/// TRUE iff `conf_sec` lies in [open, open + 300) of the phase open at or
/// before it. HALF-OPEN: a confirmation exactly 300s after an open is OUTSIDE.
[[nodiscard]] bool in_fast_open(std::int32_t conf_sec, const std::vector<std::int32_t>& opens);

/// CC-M1-3.5: the reclaim confirmation must land within 30 minutes OF THE BREAK.
[[nodiscard]] bool reclaim_within_bound(std::int32_t break_sec, std::int32_t reclaim_sec);

/// CC-M1-3.4b emission for one session's confirmations (the ADDITIVE FAST-OPEN
/// family of CC-M1-5 D13/D14).
[[nodiscard]] std::vector<Emission> g1_emissions(const std::vector<Confirmation>& confs,
                                                 const std::vector<std::int32_t>& opens);

/// One G2 confirmation: the (second, side) a level test resolved on, its family
/// bit and the LEVEL family it fired at. POST_SHOCK and FIRST_TEST both read
/// the confirmation stream rather than the emissions, so it is named.
struct G2Conf {
  std::int32_t conf_sec = 0;
  std::int8_t side = 0;
  std::uint16_t fam_bit = 0;
  LevelFamily family = LevelFamily::VWAP;
};

/// The G2 confirmations of a session's resolved level touches, in LEDGER ORDER
/// (per touch: the reject, then the reclaim). The order is part of the
/// contract: FIRST_TEST breaks ties on the confirmation second by it.
[[nodiscard]] std::vector<G2Conf> g2_confirmations(const std::vector<Touch>& touches,
                                                   std::int64_t* n_dropped_reclaim_bound);

/// Decision emissions of those confirmations (decision = confirmation + tau*).
[[nodiscard]] std::vector<Emission> g2_emissions_of(const std::vector<G2Conf>& g2);

/// G2 emissions from a session's resolved level touches.
[[nodiscard]] std::vector<Emission> g2_emissions(const std::vector<Touch>& touches,
                                                 std::int64_t* n_dropped_reclaim_bound);

/// Session-second offsets of every scheduled release inside the session.
///
/// THE CALENDAR JOIN (V3-3): the fixed 08:30/10:00 ET slots fire on every
/// session; the FOMC 14:00 ET slot counts only when the ET CALENDAR DAY OF THE
/// RELEASE SECOND is a banked release date — never the session's own trade
/// date, because a Globex session opens the previous evening ET.
[[nodiscard]] std::vector<std::int32_t> news_release_offsets(
    std::int64_t open_utc, std::int32_t n, const std::vector<std::int32_t>& fomc_dates);

/// Session-second offsets of the CC-M1-7.1 micro-opens (DST-correct).
[[nodiscard]] std::vector<std::int32_t> micro_open_offsets(std::int64_t open_utc, std::int32_t n);

/// The FIRST_TEST family: the EARLIEST confirming touch per kept level family
/// of one session. Ties on the confirmation second keep the FIRST one in ledger
/// order (the comparison is strictly-less, so a later equal second never
/// displaces the earlier arrival and its side).
struct FirstTest {
  LevelFamily family = LevelFamily::VWAP;
  std::int32_t conf_sec = 0;
  std::int8_t side = 0;
};
[[nodiscard]] std::vector<FirstTest> first_test_confirmations(const std::vector<G2Conf>& g2);

/// Confirmation seconds of every touch that was its level's FIRST-EVER touch —
/// the FIRST_TEST virgin FLAG.
///
/// OR_EXT IS EXCLUDED HERE AND ONLY HERE. The frozen oracle computes this set
/// through family_discovery._virgin_confirmation_secs, whose LEVELS_DIR still
/// points at m1/levels_v3 (the pre-OR_EXT ledger) and whose family filter is
/// b8's six-family kept set. Because the S1.1 differential proved that adding
/// OR_EXT perturbs no other level's rows or touches, reading the v4 ledger with
/// OR_EXT filtered out is the SAME SET — which is what this reproduces, without
/// building a second ledger. Returned to the orchestrator as defect S22-D1: the
/// oracle's virgin flag is blind to OR_EXT first tests by accident, not by
/// ruling.
[[nodiscard]] std::vector<std::int32_t> virgin_confirmation_secs(
    const std::vector<Touch>& touches);

/// Dedup by (decision second, side): family/rung/level tags unioned,
/// confirmation second = the earliest one mapping to that decision second.
/// The result is ordered by (dec_sec, side), which is the roster's row order.
[[nodiscard]] std::vector<Emission> dedup(const std::vector<Emission>& in);

// --- the driver -------------------------------------------------------------

struct GenConfig {
  Asset asset = Asset::SI;
  std::string session_dir;   ///< artifacts/cache/port/m1/cpp_sessions/{ASSET}
  std::string out_dir;       ///< artifacts/cache/port/m1/gen_cpp/roster
  std::string sanity_stem;   ///< QRSANE1 receipt stem; empty => mask OFF
  std::string bars_path;
  std::string cost_rollup_path;
  std::string v1_path;
  std::string fvol_path;
  std::string fomc_csv_path;  ///< reference/port_context/calendar_fomc.csv
  std::vector<std::int32_t> dates;  ///< empty => every session in session_dir
};

struct GenStats {
  std::int64_t n_sessions = 0;
  std::int64_t n_sessions_with_ledger = 0;
  std::int64_t n_candidates = 0;
  std::int64_t n_skip_past_close = 0;
  std::int64_t n_skip_not_sane = 0;
  std::int64_t n_g1_confirmations = 0;
  std::int64_t n_g2_events = 0;
  std::int64_t n_fast_open_candidates = 0;
  std::int64_t n_g2_dropped_reclaim_bound = 0;
  std::int64_t n_news_conf = 0;
  std::int64_t n_micro_conf = 0;
  std::int64_t n_post_shock = 0;
  std::int64_t n_first_test = 0;
  std::int64_t n_shock_episodes = 0;
  std::int64_t n_insane_episodes = 0;
  std::int64_t n_orext_levels = 0;
  std::int64_t n_orext_touches = 0;
  std::int64_t n_orext_beyond_flags = 0;
  /// Per-family candidate counts, indexed by the fam_mask bit position.
  std::int64_t n_by_family[kFamilyCount] = {0, 0, 0, 0, 0, 0, 0, 0, 0};
  std::int64_t n_levels = 0;
  std::int64_t n_touches = 0;
  std::int64_t n_records_f = 0;
  std::int64_t n_records_a = 0;
  std::int64_t n_shards = 0;
  std::int64_t n_seconds_insane = 0;
  std::int64_t n_seconds_two_sided = 0;
  std::int64_t stored_bytes = 0;
};

/// Build the whole roster of one asset. Sessions are walked in DATE ORDER (the
/// level ledger's cross-session memory makes that a law, not a preference) and
/// flushed one shard per calendar month, so peak memory is one month, never one
/// corpus.
[[nodiscard]] Expected<GenStats, Refusal> generate_asset(const GenConfig& cfg);

/// Every YYYYMMDD with a `.json` receipt in `dir`, ascending.
[[nodiscard]] Expected<std::vector<std::int32_t>, Refusal> session_dates(const std::string& dir);

/// CC-M1-2 addendum: canonical JSON (keys sorted, no whitespace, floats
/// shortest round-trip) of this engine's parameters, and its sha256.
[[nodiscard]] std::string params_canonical_json(Asset asset);
[[nodiscard]] std::string params_hash(Asset asset);
[[nodiscard]] const char* spec_sha16_pin() noexcept;

}  // namespace qr::gen

#endif  // QR_GEN_GENERATE_HPP
