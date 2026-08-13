// qr_futsess/constants.hpp — the frozen M0 program-mode constants.
//
// SPEC: design/PORT_M0_CENSUS_SPEC.md §0 (sentinel law, state codes), §1
// (per-asset constants), §4 (sampling, tracking), §5 (session geometry).
// Every value here is transcribed from that spec and cross-checked against the
// reference implementation engine/port_m0/common.py, which is the differential
// oracle for this module.
#ifndef QR_FUTSESS_CONSTANTS_HPP
#define QR_FUTSESS_CONSTANTS_HPP

#include <cstddef>
#include <cstdint>
#include <string>

namespace qr::futsess {

// --- sentinel law (M0 spec §0; common.py:34-35) ------------------------------
// "Test EACH of bid/ask against <= 0 and >= 2**62 BEFORE any arithmetic."
inline constexpr std::int64_t kUndefPrice = 9223372036854775807LL;  // INT64_MAX
inline constexpr std::int64_t kSentHi = 1LL << 62;

// --- DBN flag bit 7, "LAST" (common.py:37) -----------------------------------
inline constexpr std::uint8_t kFLast = 128u;

// --- book state codes (M0 spec §4; common.py:43-49) --------------------------
// 4 (LOCKED) is reserved and deliberately never emitted: locked folds into
// CROSSED by the committed drop rule ask <= bid.
inline constexpr std::int8_t kStTwoSided = 0;
inline constexpr std::int8_t kStNoBid = 1;
inline constexpr std::int8_t kStNoAsk = 2;
inline constexpr std::int8_t kStCrossed = 3;
inline constexpr std::int8_t kStEmpty = 5;
inline constexpr std::int8_t kStPreFirst = 6;

inline constexpr std::int32_t kSecondsPerDay = 86400;
/// A Globex session is [17:00 CT d-1, 16:00 CT d) = 23 hours (spec §5).
inline constexpr std::int32_t kSessionSeconds = 23 * 3600;

// --- s2/s3 parameters (s2_decode.py:41, s3_sessions.py:34-53) ----------------
inline constexpr std::size_t kSiTrackTop = 3;
inline constexpr std::int32_t kMinBarSeconds = 100;
inline constexpr int kRollWindowSessions = 5;
inline constexpr int kWhipsawWindowSessions = 10;
inline constexpr int kShortDayHours = 20;
inline constexpr int kAtrPeriod = 14;

/// The seal cut-off (M0 spec §0): a payload file whose BASENAME carries any
/// 8-digit date component >= this is refused, never opened.
inline constexpr int kSealCutoff = 20260101;

enum class Asset : std::uint8_t { SI = 0, HG = 1, NKD = 2 };

struct AssetSpec {
  const char* name;
  std::int64_t mult;      // $ per 1.0 price unit
  double px_scale;        // raw integer price -> price units
  double tick_usd;
  double band_lo;         // sane daily-median-mid band, M0 §1
  double band_hi;
  const char* dir_name;   // the payload directory under DATA_ROOT
  bool daily;             // SI = one file per day; HG/NKD = one file per year
};

/// Per-asset constants, M0 spec §1 / common.py:54-97.
[[nodiscard]] const AssetSpec& asset_spec(Asset a);
[[nodiscard]] bool asset_from_name(const std::string& name, Asset* out);

/// M0 spec §0 sentinel guard, applied BEFORE any price arithmetic.
/// Mirrors common.classify_book exactly, including "locked folds into CROSSED".
struct BookState {
  std::int8_t state;
  std::int64_t bid;
  std::int64_t ask;
};
[[nodiscard]] inline BookState classify_book(std::int64_t bid, std::int64_t ask) noexcept {
  const bool bid_ok = (bid > 0) && (bid < kSentHi);
  const bool ask_ok = (ask > 0) && (ask < kSentHi);
  if (!bid_ok && !ask_ok) {
    return BookState{kStEmpty, kUndefPrice, kUndefPrice};
  }
  if (!bid_ok) {
    return BookState{kStNoBid, kUndefPrice, ask};
  }
  if (!ask_ok) {
    return BookState{kStNoAsk, bid, kUndefPrice};
  }
  if (bid >= ask) {
    return BookState{kStCrossed, bid, ask};
  }
  return BookState{kStTwoSided, bid, ask};
}

}  // namespace qr::futsess

#endif  // QR_FUTSESS_CONSTANTS_HPP
