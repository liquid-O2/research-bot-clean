// qr_skel/engine.hpp — candidate input, shard execution, QRSKEL1 output.
//
// SPEC: PORT_M1B_SPEC §1 S3; conventions design/PORT_M1B_S3_CONV.md C2/C11.
// The engine is ROSTER-AGNOSTIC: it reads the QRCAND1 candidate schema and
// nothing else, so S1 changing the candidate SET changes no code here.
#ifndef QR_SKEL_ENGINE_HPP
#define QR_SKEL_ENGINE_HPP

#include <cstdint>
#include <string>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_futsess/constants.hpp"
#include "qr_skel/session.hpp"
#include "qr_skel/skeleton.hpp"

namespace qr::skel {

/// Per-trade-date phase median spreads for the CC-M1-4 mask. The engine does
/// NOT compute these: D-054 leaves the trailing window unpinned, so the numbers
/// are supplied and this table is simply looked up.
class SanityTable {
 public:
  /// Load a QRSANE1 receipt: date8 (int32, ascending, unique) and
  /// phase_threshold_usd (float64, row-major [n][kPhaseCount]).
  [[nodiscard]] static Expected<SanityTable, Refusal> load(const std::string& stem);

  [[nodiscard]] bool empty() const { return date8_.empty(); }
  /// The policy for a date. A date absent from an otherwise non-empty table is
  /// a refusal at the call site, never a silently disabled mask.
  [[nodiscard]] Expected<SanityPolicy, Refusal> policy_for(std::int32_t date8) const;

 private:
  std::vector<std::int32_t> date8_;
  std::vector<double> med_;  // thresholds, [n][kPhaseCount]
};

struct Candidate {
  std::int64_t cand_id = 0;
  std::int32_t date8 = 0;
  std::int32_t dec_sec = 0;
  std::int8_t side = 0;
  double atr14_usd = 0.0;
};

struct CandidateSet {
  Asset asset = Asset::SI;
  std::vector<Candidate> rows;  // input order, date8 non-decreasing

  /// Load `<stem>.{bin,json}` in the QRCAND1 schema. Refuses a candidate file
  /// whose date8 column is not non-decreasing (CONV C11: the engine loads each
  /// session once, in order, and never re-opens one).
  [[nodiscard]] static Expected<CandidateSet, Refusal> load(const std::string& stem);
};

struct ShardStats {
  std::int64_t n_candidates = 0;
  std::int64_t n_sessions = 0;
  std::int64_t n_refused_atr = 0;       // CONV C5 REFUSE_BAD_ATR
  std::int64_t n_refused_ladder = 0;    // CONV C5 REFUSE_RUNG_DEGENERATE
  std::int64_t n_unavailable_d0 = 0;
  std::int64_t n_unavailable_d1 = 0;
  std::int64_t n_records_f = 0;
  std::int64_t n_records_a = 0;
  /// The high-water mark of the bounded chunk buffer, in ANCHOR rows. The
  /// structural suite asserts it never exceeds chunk_candidates * kAnchorCount.
  std::int64_t max_live_anchor_rows = 0;
  std::int64_t stored_rows = 0;   // == n_candidates (one row per candidate)
  std::int64_t stored_bytes = 0;  // size of the .bin
  /// CC-M1-4: two-sided seconds excluded by the mid-sanity mask, and the
  /// two-sided total, summed over the shard's sessions (`insane_frac`).
  std::int64_t n_seconds_insane = 0;
  std::int64_t n_seconds_two_sided = 0;
};

struct ShardOptions {
  Asset asset = Asset::SI;
  std::string session_dir;   // artifacts/cache/port/m1/cpp_sessions/{ASSET}
  std::string out_stem;      // <out_dir>/{ASSET}_{YYYYMM}
  std::string month;         // "YYYYMM", for the sidecar
  std::size_t chunk_candidates = kChunkCandidates;
  /// CC-M1-4 mid-sanity, per trade date. Empty => the mask is off and the
  /// engine reproduces its pre-D-054 receipts byte for byte.
  SanityTable sanity;
};

/// Build one shard from `set.rows[lo, hi)`. Refused candidates emit NO row and
/// are counted; every other candidate emits exactly one fixed-shape row.
[[nodiscard]] Expected<ShardStats, Refusal> build_shard(const CandidateSet& set, std::size_t lo,
                                                        std::size_t hi, const ShardOptions& opt);

/// CC-M1-2 addendum: sha256 of the canonical JSON of the engine's parameters
/// (keys sorted, UTF-8, no whitespace, floats shortest round-trip), computed
/// natively. `params_canonical_json` is exposed so the Python comparator can
/// recompute the same string from the same values.
[[nodiscard]] std::string params_canonical_json(Asset asset, std::size_t chunk_candidates);
[[nodiscard]] std::string params_hash(Asset asset, std::size_t chunk_candidates);

/// The PORT_M1B_SPEC.md sha16 this engine is written against, and the sha16 of
/// a file on disk, so the pin can be CHECKED rather than merely declared.
[[nodiscard]] const char* spec_sha16_pin() noexcept;
[[nodiscard]] Expected<std::string, Refusal> file_sha16(const std::string& path);

}  // namespace qr::skel

#endif  // QR_SKEL_ENGINE_HPP
