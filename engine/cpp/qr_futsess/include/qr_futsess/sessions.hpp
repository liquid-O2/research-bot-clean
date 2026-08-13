// qr_futsess/sessions.hpp — Globex session assembly (M0 spec §5, reference
// engine/port_m0/s3_sessions.py).
//
// Pass 1: per-session dominance, session metadata, bars + ATR14, roll flags.
// Pass 2: stitched session grids + phase tags -> one receipt per session.
//
// The phase boundaries are NOT recomputed here: PORT_M1_SPEC §1.2 pins them to
// the FROZEN tables artifacts/cache/port/m0/phases_{ASSET}.json, which this
// module reads.
#ifndef QR_FUTSESS_SESSIONS_HPP
#define QR_FUTSESS_SESSIONS_HPP

#include <array>
#include <cstdint>
#include <map>
#include <string>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_futsess/calendar.hpp"
#include "qr_futsess/constants.hpp"

namespace qr::futsess {

/// The frozen per-year phase boundaries, in UTC seconds-of-day:
/// {TOKYO|LONDON, LONDON|NY, NY|TOKYO}.
struct PhaseTable {
  std::map<int, std::array<std::int64_t, 3>> by_year;
};

[[nodiscard]] Expected<PhaseTable, Refusal> load_phase_table(const std::string& path);

/// The dominance rule pinned by s1 (`repro_si2024.receipt.json`). R1/R2 are
/// update-count rules; R3/R4 are trade-size-sum rules.
enum class DominanceRule : std::uint8_t { R1, R2, R3, R4 };

/// Read the pinned rule from the s1 receipt. Refuses unless the receipt's
/// verdict is MATCH — without a matched fingerprint §5 has no pinned rule.
[[nodiscard]] Expected<DominanceRule, Refusal> load_pinned_rule(const std::string& receipt_path);

struct AssembleOptions {
  Asset asset = Asset::SI;
  std::string day_dir;      // directory of .qrday intermediates
  std::string out_dir;      // where session receipts are written
  std::string phases_path;  // frozen m0 phases_{ASSET}.json
  DominanceRule rule = DominanceRule::R1;
};

struct AssembleResult {
  std::int64_t n_sessions = 0;
  std::int64_t n_bars = 0;
};

/// Run both passes for one asset.
[[nodiscard]] Expected<AssembleResult, Refusal> assemble_asset(const AssembleOptions& opt);

// --- pieces exposed for unit tests ------------------------------------------

/// Cyclic membership: [lo, hi) on the 86400-second circle (s3 `_in_cyclic`).
[[nodiscard]] bool in_cyclic(std::int64_t x, std::int64_t lo, std::int64_t hi);

/// Phase index of a UTC second-of-day given the three boundaries (s3 `phase_of`).
[[nodiscard]] std::int8_t phase_of(std::int64_t sec_of_day,
                                   const std::array<std::int64_t, 3>& bounds);

/// Wilder ATR: seed = SMA of the first `period` true ranges, then recursive.
/// Entries before the seed are NaN (s3 `wilder_atr`).
[[nodiscard]] std::vector<double> wilder_atr(const std::vector<double>& trs, int period);

}  // namespace qr::futsess

#endif  // QR_FUTSESS_SESSIONS_HPP
