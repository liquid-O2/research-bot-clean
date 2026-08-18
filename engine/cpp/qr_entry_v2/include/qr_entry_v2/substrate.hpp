// qr_entry_v2/substrate.hpp — clean causal futures selection and event packs.
//
// The namespace is intentionally disjoint from qr_futsess's legacy session
// format.  The four production stages are:
//   1. all-instrument, per-session R1 update tallies;
//   2. instrument lock from the PREVIOUS COMPLETED session's outright winner;
//   3. monthly phase boundaries from at most 252 strictly-prior clean sessions;
//   4. exact full-session MBP-1 records for the causally locked instrument.
#ifndef QR_ENTRY_V2_SUBSTRATE_HPP
#define QR_ENTRY_V2_SUBSTRATE_HPP

#include <array>
#include <cstddef>
#include <cstdint>
#include <map>
#include <set>
#include <string>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_futsess/constants.hpp"

namespace qr::entry_v2 {

inline constexpr const char* kDefaultOutputRoot =
    "/workspace/artifacts/cache/port/entry_v2";
inline constexpr std::int32_t kDevelopmentStartD8 = 20210101;
inline constexpr std::int32_t kDevelopmentEndD8Exclusive = 20250701;
inline constexpr const char* kClockLawReceiptSha256 =
    "37c5b0e81e199193158632b3e8f61808ef82c23c71233ff9a3c75510e126f9e3";
inline constexpr std::size_t kPhaseBins = 48;
inline constexpr std::size_t kPhaseLookback = 252;
inline constexpr std::size_t kPhaseMinFit = 60;
inline constexpr std::array<std::int32_t, 3> kFixedPhaseBounds = {
    7 * 3600, 11 * 3600, 21 * 3600 + 30 * 60};

enum class Stage : std::uint8_t { TALLY = 0, LOCK = 1, PHASE = 2, EVENTS = 3, ALL = 4 };

struct Config {
  qr::futsess::Asset asset = qr::futsess::Asset::SI;
  std::vector<std::string> inputs;
  // Exact QRE2INPUT2 admission authority. Every path must be explicitly
  // allowlisted with its provider-authenticated SHA-256 before the payload is
  // stat'ed or opened. DEVELOPMENT_PREFIX paths are transport-readable only
  // through the fixed pre-H2 receive-time boundary.
  std::map<std::string, std::string> development_input_sha256;
  std::set<std::string> development_prefix_inputs;
  std::string output_root = kDefaultOutputRoot;
  std::int32_t start_d8 = kDevelopmentStartD8;
  std::int32_t end_d8_exclusive = kDevelopmentEndD8Exclusive;
};

struct StageStats {
  std::uint64_t rows = 0;
  std::uint64_t records = 0;
  std::uint64_t refusals = 0;
  std::uint64_t content_hashed_inputs = 0;
  std::uint64_t trusted_hash_inputs = 0;
  std::uint64_t raw_records = 0;
  std::uint64_t trusted_economic_records = 0;
  std::uint64_t snapshot_records = 0;
  std::uint64_t standalone_bad_ts_recv_records = 0;
  std::uint64_t maybe_bad_book_records = 0;
  std::string output_sha256;
  std::string receipt_sha256;
};

struct TallyRow {
  std::int32_t d8 = 0;
  std::uint32_t iid = 0;
  std::string symbol;
  bool outright = false;
  std::uint64_t updates = 0;
  std::uint64_t raw_records = 0;
  std::uint64_t trusted_economic_records = 0;
  std::uint64_t snapshot_records = 0;
  std::uint64_t standalone_bad_ts_recv_records = 0;
  std::uint64_t maybe_bad_book_records = 0;
  // Counts of updates whose record-level top book is two-sided, by UTC half-hour.
  std::array<std::uint64_t, kPhaseBins> phase_updates{};
};

inline constexpr std::uint8_t kFlagMaybeBadBook = 0x04u;
inline constexpr std::uint8_t kFlagBadTsRecv = 0x08u;
inline constexpr std::uint8_t kFlagSnapshot = 0x20u;
inline constexpr std::uint8_t kFlagLast = 0x80u;

struct BookQualityDecision {
  bool snapshot_row = false;
  bool trusted_economic = false;
  bool reset_derived_state = false;
  bool maybe_bad_book_row = false;
  std::uint64_t generation = 0;
};

// Per-instrument causal book-health state. Snapshot rows initialize/reset raw
// book state but are never economic observations. The first subsequent sane
// ordinary row establishes trust only for later rows.
class BookQualityState {
 public:
  [[nodiscard]] Expected<BookQualityDecision, Refusal> observe(
      std::uint64_t ts_recv_ns, std::uint8_t flags, bool sane_book);
  [[nodiscard]] bool unresolved_taint() const noexcept { return tainted_; }

 private:
  bool in_snapshot_block_ = false;
  bool snapshot_block_clean_ = false;
  bool awaiting_sane_ordinary_ = false;
  bool trusted_ = true;
  bool tainted_ = false;
  std::uint64_t snapshot_ts_recv_ns_ = 0;
  std::uint64_t generation_ = 0;
};

enum class LockStatus : std::uint8_t {
  LOCKED = 0,
  WARMUP_NO_PREVIOUS = 1,
  REFUSED_PREVIOUS_NO_OUTRIGHT = 2,
};

[[nodiscard]] const char* lock_status_name(LockStatus status) noexcept;

struct LockRow {
  std::int32_t d8 = 0;
  LockStatus status = LockStatus::WARMUP_NO_PREVIOUS;
  std::int64_t locked_iid = -1;
  std::int32_t selection_basis_d8 = -1;
  std::uint64_t selection_basis_updates = 0;
  std::string selection_basis_symbol;
  std::int64_t open_utc = 0;
  std::int64_t close_utc = 0;
};

enum class PhaseSource : std::uint8_t { TRAILING_252_PRIOR = 0, FIXED_MIN60 = 1 };

[[nodiscard]] const char* phase_source_name(PhaseSource source) noexcept;

struct PhaseRow {
  std::int32_t month = 0;  // YYYYMM
  PhaseSource source = PhaseSource::FIXED_MIN60;
  std::uint32_t n_fit = 0;
  std::int32_t fit_start_d8 = -1;
  std::int32_t fit_end_d8 = -1;
  std::array<std::int32_t, 3> boundaries = kFixedPhaseBounds;
  std::string profile_sha256;
};

// Stable disk contract. The explicit little-endian header encoding is:
// magic@0, version@8, asset_idx@12, d8@16, locked_iid@20, open_utc@28,
// close_utc@36, n_events@44, row_bytes@52, reserved@56 (60 bytes total).
// Every event is the exact selected MBP-1 record; the header supplies the
// immutable session key. Candidate cutoff is
// lower_bound(rows.ts_recv_ns, decision_ts_ns), so equal-time records are not
// silently placed before a decision.
struct EventPackHeader {
  char magic[8];                 // "QRE2EVT2"
  std::uint32_t version;
  std::uint8_t asset_idx;
  std::uint8_t reserved_asset[3];
  std::int32_t d8;
  std::int64_t locked_iid;
  std::int64_t open_utc;
  std::int64_t close_utc;
  std::uint64_t n_events;
  std::uint32_t row_bytes;
  std::uint32_t reserved;
};

struct EventRow {
  std::uint64_t ts_recv_ns;
  std::uint64_t ts_event_ns;
  std::int64_t price;
  std::int64_t bid_px;
  std::int64_t ask_px;
  std::uint32_t size;
  std::uint32_t bid_sz;
  std::uint32_t ask_sz;
  std::uint32_t bid_ct;
  std::uint32_t ask_ct;
  std::uint32_t sequence;
  std::int32_t ts_in_delta;
  std::int32_t receive_session_sec;
  std::uint8_t action;
  std::uint8_t side;
  std::uint8_t flags;
  std::uint8_t depth;
};

// Disk bytes are explicitly encoded/decoded; the in-memory structs remain
// naturally aligned so no packed-member reference can trigger undefined
// behaviour. EventRow has no internal padding through byte 75; its four-byte
// tail padding is deliberately not serialized.
inline constexpr std::size_t kEventPackHeaderBytes = 60;
inline constexpr std::size_t kEventRowBytes = 76;
static_assert(sizeof(EventPackHeader) == 64, "QRE2 in-memory header layout drift");
static_assert(sizeof(EventRow) == 80, "QRE2 in-memory row layout drift");
static_assert(offsetof(EventRow, ts_recv_ns) == 0 && offsetof(EventRow, ts_event_ns) == 8 &&
                  offsetof(EventRow, receive_session_sec) == 68 &&
                  offsetof(EventRow, action) == 72 &&
                  offsetof(EventRow, depth) == 75,
              "QRE2 event field offsets drift");

struct EventPack {
  EventPackHeader header{};
  std::vector<EventRow> rows;
  // Exact serialized QRE2EVT2 bytes. Populated and verified by
  // read_event_pack; pure in-memory fixtures may leave it empty.
  std::string artifact_sha256;
};

// Pure derivations are public so adversarial tests and downstream audits can
// prove that future records do not change an already-frozen decision.
[[nodiscard]] std::vector<LockRow> derive_locks(const std::vector<TallyRow>& tallies);
[[nodiscard]] std::vector<PhaseRow> derive_phase_schedule(
    const std::vector<TallyRow>& tallies, const std::vector<LockRow>& locks);

[[nodiscard]] Expected<std::vector<TallyRow>, Refusal> read_tallies(const Config& config);
[[nodiscard]] Expected<std::vector<LockRow>, Refusal> read_locks(const Config& config);
[[nodiscard]] Expected<std::vector<PhaseRow>, Refusal> read_phases(const Config& config);
[[nodiscard]] Expected<EventPack, Refusal> read_event_pack(
    const std::string& path, const std::string& expected_sha256 = {});
[[nodiscard]] std::string event_pack_sha256(const EventPack& pack);

[[nodiscard]] std::size_t event_cutoff(const std::vector<EventRow>& rows,
                                       std::uint64_t decision_ts_ns) noexcept;

[[nodiscard]] Expected<StageStats, Refusal> run_tally(const Config& config);
[[nodiscard]] Expected<StageStats, Refusal> run_lock(const Config& config);
[[nodiscard]] Expected<StageStats, Refusal> run_phase(const Config& config);
[[nodiscard]] Expected<StageStats, Refusal> run_events(const Config& config);
[[nodiscard]] Expected<StageStats, Refusal> run(const Config& config, Stage stage);

[[nodiscard]] Expected<Stage, Refusal> stage_from_name(const std::string& name);

}  // namespace qr::entry_v2

#endif  // QR_ENTRY_V2_SUBSTRATE_HPP
