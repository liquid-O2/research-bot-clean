// qr_gen/generate.hpp — PRODUCTION EVENT GENERATION (PORT_M1B_SPEC §1 S2).
//
// The C++ home of the union roster. Its acceptance is a candidate-EXACT
// differential against the frozen S1-v2 Python oracle
// (engine/port_m1/b8_generation_v2.py, commit 31426a4): same id set, same value
// in every stored field, over every session.
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
//   G2_RECLAIM    a level break reclaimed within 30 MINUTES of the break
//                 (CC-M1-3.5), decision = reclaim confirmation + tau*
//
// DEDUP: (session, decision_sec, side) -> ONE candidate; family, rung and level
// tags are UNIONED and confirmation_sec is the EARLIEST confirmation mapping to
// that decision second.
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

/// Family bits of the roster's `fam_mask` (b8_generation_v2.FAMILIES order).
inline constexpr std::uint8_t kFamG1 = 1 << 0;
inline constexpr std::uint8_t kFamG1Fine = 1 << 1;
inline constexpr std::uint8_t kFamG1FastOpen = 1 << 2;
inline constexpr std::uint8_t kFamG2Reject = 1 << 3;
inline constexpr std::uint8_t kFamG2Reclaim = 1 << 4;

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
  std::uint8_t fam_bits = 0;
  std::uint16_t level_bits = 0;
  std::uint8_t rung_mask = 0;
  std::int32_t conf_sec = 0;
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

/// G2 emissions from a session's resolved level touches.
[[nodiscard]] std::vector<Emission> g2_emissions(const std::vector<Touch>& touches,
                                                 std::int64_t* n_dropped_reclaim_bound);

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
