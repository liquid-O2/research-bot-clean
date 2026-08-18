// qr_entry_v2/g1.hpp -- clean raw-event G1 candidates and privileged labels.
//
// This namespace owns two deliberately separate planes:
//   * CandidateRow is causal at decision_ts_ns on the receive clock. It contains no path outcome,
//     certificate, oracle action, rank, or future-derived field.
//   * TeacherRow begins at the exact lower_bound cutoff and is joined only by
//     candidate_id.  Schedule ceilings and chronological truth-score arrivals
//     are separate derivations over TeacherRow; neither is a candidate target.
#ifndef QR_ENTRY_V2_G1_HPP
#define QR_ENTRY_V2_G1_HPP

#include <array>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <limits>
#include <map>
#include <optional>
#include <string>
#include <tuple>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_entry_v2/substrate.hpp"

namespace qr::entry_v2 {

inline constexpr std::size_t kG1RungCount = 4;
inline constexpr std::size_t kG1PhaseCount = 3;
inline constexpr std::array<double, kG1RungCount> kG1Rungs = {
    0.05, 0.075, 0.11, 0.15};
inline constexpr std::int32_t kG1StandardDelaySec = 120;
inline constexpr std::int32_t kG1FastOpenDelaySec = 15;
inline constexpr std::int32_t kG1FastOpenWindowSec = 300;
inline constexpr std::size_t kSpreadPriorSessions = 60;
inline constexpr std::size_t kAtrPeriod = 14;
inline constexpr std::size_t kMinBarDistinctSeconds = 100;
inline constexpr double kSaneSpreadMultiple = 10.0;
inline constexpr double kSaneSpreadCapUsd = 500.0;
inline constexpr double kFrozenFeeUsd = 5.0;
inline constexpr double kTeacherWallUsd = 900.0;
inline constexpr double kTakeTargetUsd = 600.0;
inline constexpr std::size_t kMaxEntriesPerAssetDay = 3;
inline constexpr std::size_t kMaxEntriesPerPortfolioDay = 9;

enum class CandidateSessionStatus : std::uint8_t {
  READY = 0,
  NO_ATR14,
  NO_LOCK,
  NO_EVENTS,
  NO_SANE_BBO,
};

[[nodiscard]] const char* candidate_session_status_name(
    CandidateSessionStatus status) noexcept;

struct PhaseSpreadPrior {
  bool present = false;
  std::uint32_t completed_sessions = 0;
  std::uint64_t observations = 0;
  // NaN iff present == false.
  double median_spread_usd = 0.0;
  // D-054: min(10 * median, $500); exactly $500 only when absent or capped.
  double sane_ceiling_usd = kSaneSpreadCapUsd;
};

struct DayPriors {
  std::int32_t d8 = 0;
  bool atr14_present = false;
  // NaN iff atr14_present == false.  The value is through d-1.
  double atr14_prev_usd = 0.0;
  std::array<PhaseSpreadPrior, kG1PhaseCount> phase{};
};

// Shared D-054 classification primitive.  Forecast and candidate lanes use
// this same event-grain law so their notion of a sane QRE2 mid cannot drift.
struct SaneBookObservation {
  bool two_sided = false;
  bool sane = false;
  std::int64_t mid2 = 0;
  std::int64_t spread_raw = 0;
  std::int64_t spread_ticks = 0;
  double spread_usd = 0.0;
  std::uint8_t phase = 0;
};

[[nodiscard]] Expected<SaneBookObservation, Refusal> classify_sane_book(
    qr::futsess::Asset asset, const EventRow& row, const PhaseRow& schedule,
    const DayPriors& priors);

// A completed session's information admitted to the prior state only after
// candidates for that session have been generated.
struct CompletedSessionInput {
  std::int32_t d8 = 0;
  std::int64_t locked_iid = -1;
  std::size_t session_ordinal = 0;
  bool bar_present = false;
  std::int64_t bar_high_mid2 = 0;
  std::int64_t bar_low_mid2 = 0;
  std::int64_t bar_close_mid2 = 0;
  // Exact spread-in-ticks histograms over every two-sided raw event, including
  // wide events.  The sane mask for day d uses only strictly-prior histograms.
  std::array<std::map<std::int64_t, std::uint64_t>, 3> phase_spread_ticks{};
};

// Incremental chronological prior owner.  snapshot(d) never mutates state;
// commit(d) is the only operation that admits d into future snapshots.
class CausalPriorState {
 public:
  explicit CausalPriorState(qr::futsess::Asset asset);

  [[nodiscard]] Expected<DayPriors, Refusal> snapshot(std::int32_t d8) const;
  [[nodiscard]] Expected<std::monostate, Refusal> commit(
      const CompletedSessionInput& completed);

 private:
  qr::futsess::Asset asset_;
  std::int32_t last_committed_d8_ = -1;
  std::deque<std::array<std::map<std::int64_t, std::uint64_t>, 3>> spread_sessions_;
  std::array<std::map<std::int64_t, std::uint64_t>, 3> spread_pool_{};
  std::uint64_t tr_count_ = 0;
  long double atr_seed_sum_ = 0.0L;
  std::optional<long double> atr_after_;
  bool have_last_bar_ = false;
  std::size_t last_bar_session_ordinal_ = 0;
  std::int64_t last_bar_iid_ = -1;
  std::int64_t last_bar_close_mid2_ = 0;
};

enum class CandidateDelay : std::uint8_t { STANDARD_120 = 1, FAST_OPEN_15 = 2 };

[[nodiscard]] const char* candidate_delay_name(CandidateDelay delay) noexcept;

enum class ComplianceStatus : std::uint8_t {
  CLEAR = 0,
  PROHIBITED,
  COMPLIANCE_UNKNOWN,
};

[[nodiscard]] const char* compliance_status_name(ComplianceStatus status) noexcept;

enum class ComplianceRowKind : std::uint8_t { COVERAGE = 0, PROHIBITED };

struct ComplianceInterval {
  ComplianceRowKind kind = ComplianceRowKind::COVERAGE;
  std::string interval_id;
  std::uint64_t start_ts_ns = 0;
  std::uint64_t end_ts_ns = 0;  // inclusive
  std::uint64_t availability_ts_ns = 0;
  std::string provenance_sha256;
};

struct ComplianceCalendar {
  bool available = false;
  std::string artifact_sha256;
  std::vector<ComplianceInterval> rows;
};

// Input schema QRE2COMPLIANCE1 has explicit COVERAGE and PROHIBITED rows.
// Absence of a strictly-prior COVERAGE row spanning a decision is UNKNOWN;
// absence of a matching PROHIBITED row alone is never interpreted as CLEAR.
[[nodiscard]] Expected<ComplianceCalendar, Refusal> load_compliance_calendar(
    const std::string& path, const std::string& expected_sha256);

struct CandidateRow {
  std::string candidate_id;
  qr::futsess::Asset asset = qr::futsess::Asset::SI;
  std::int32_t d8 = 0;
  std::int64_t locked_iid = -1;
  std::int64_t selection_basis_d8 = -1;
  std::uint64_t confirmation_ts_recv_ns = 0;
  std::uint64_t confirmation_event_ordinal = 0;
  std::uint64_t decision_ts_ns = 0;
  std::int32_t decision_sec = 0;
  std::int8_t side = 0;  // +1 LONG, -1 SHORT
  std::uint8_t phase = 0;
  std::uint8_t rung_mask = 0;
  CandidateDelay delay = CandidateDelay::STANDARD_120;
  std::int64_t phase_open_utc = 0;
  std::int64_t phase_close_utc = 0;
  // Strict raw prefix [0, event_cutoff); equal-ts records are excluded.
  std::uint64_t event_cutoff = 0;
  std::uint64_t prefix_last_event_ordinal = 0;
  std::uint64_t prefix_last_availability_ts_ns = 0;
  std::string event_pack_sha256;
  std::string prefix_sha256;
  std::string clock_law_receipt_sha256;
  std::string lineage_sha256;
  // Latest sane BBO in that strict prefix.
  std::int64_t entry_bid_px = 0;
  std::int64_t entry_ask_px = 0;
  std::int64_t entry_mid2 = 0;
  double entry_spread_usd = 0.0;
  double frozen_cost_usd = 0.0;  // strict-prefix decision spread + $5
  double atr14_prev_usd = 0.0;
  bool spread_prior_present = false;
  double spread_prior_usd = 0.0;
  double sane_ceiling_usd = kSaneSpreadCapUsd;
  ComplianceStatus compliance = ComplianceStatus::COMPLIANCE_UNKNOWN;
  // Distance to the nearest known prohibited interval; 0 when prohibited,
  // NaN when compliance is unknown or no known interval exists in coverage.
  double compliance_distance_sec = std::numeric_limits<double>::quiet_NaN();
  std::string compliance_artifact_sha256;
};

// Versioned identity primitives are public so every artifact reader can
// recompute them instead of trusting stored identity text.
[[nodiscard]] std::string g1_candidate_id(const CandidateRow& row);
[[nodiscard]] std::string g1_candidate_lineage(const CandidateRow& row);
[[nodiscard]] Expected<std::monostate, Refusal> validate_candidate_prefixes(
    const EventPack& pack, const std::vector<CandidateRow>& candidates);

struct CandidateSession {
  CandidateSessionStatus status = CandidateSessionStatus::NO_EVENTS;
  DayPriors priors{};
  CompletedSessionInput completed{};
  std::vector<CandidateRow> candidates;
  std::uint64_t raw_events = 0;
  std::uint64_t two_sided_events = 0;
  std::uint64_t sane_events = 0;
  std::uint64_t confirmations = 0;
  std::uint64_t skipped_past_close = 0;
  std::uint64_t skipped_no_strict_prefix_bbo = 0;
};

// One session is generated from the day-d snapshot.  The caller must commit
// result.completed only after this call returns.
[[nodiscard]] Expected<CandidateSession, Refusal> generate_g1_candidates(
    qr::futsess::Asset asset, const LockRow& lock, const PhaseRow& schedule,
    const EventPack& pack, const DayPriors& priors, std::size_t session_ordinal);

// Applies the separate point-in-time D-077 plane without changing generator
// mechanics or candidate identity.  It does update causal lineage.
[[nodiscard]] Expected<std::monostate, Refusal> apply_candidate_compliance(
    const ComplianceCalendar* calendar, std::vector<CandidateRow>* candidates);

enum class TeacherStatus : std::uint8_t { READY = 0, NO_SANE_SUFFIX };

[[nodiscard]] const char* teacher_status_name(TeacherStatus status) noexcept;

struct TeacherRow {
  std::string candidate_id;
  qr::futsess::Asset asset = qr::futsess::Asset::SI;
  std::int32_t d8 = 0;
  std::uint64_t decision_ts_ns = 0;
  std::uint64_t exit_ts_ns = 0;
  std::int64_t phase_close_utc = 0;
  TeacherStatus status = TeacherStatus::NO_SANE_SUFFIX;
  double cert_close_usd = 0.0;
  double mfe_usd = 0.0;
  double mae_usd = 0.0;
  double time_to_peak_sec = 0.0;
  bool wall_hit = false;
  bool payer = false;       // cert_close_usd > 0, candidate-local
  bool take_target = false; // cert_close_usd >= $600, candidate-local
  ComplianceStatus compliance = ComplianceStatus::COMPLIANCE_UNKNOWN;
};

// The suffix begins at lower_bound(ts_recv_ns, decision_ts_ns). Equal receive-time batches
// are future and therefore may affect the teacher, never the candidate prefix.
[[nodiscard]] Expected<std::vector<TeacherRow>, Refusal> certify_teacher(
    qr::futsess::Asset asset, const PhaseRow& schedule, const EventPack& pack,
    const DayPriors& priors, const std::vector<CandidateRow>& candidates);

struct ExpectedSession {
  qr::futsess::Asset asset = qr::futsess::Asset::SI;
  std::int32_t d8 = 0;

  friend bool operator<(const ExpectedSession& lhs, const ExpectedSession& rhs) {
    return std::tie(lhs.d8, lhs.asset) < std::tie(rhs.d8, rhs.asset);
  }
  friend bool operator==(const ExpectedSession& lhs, const ExpectedSession& rhs) = default;
};

struct ScheduleResult {
  std::string law;
  std::map<std::string, bool> selected;
  double total_usd = 0.0;
  std::uint64_t selected_count = 0;
  std::uint64_t expected_sessions = 0;
  std::uint64_t zero_sessions = 0;
  double usd_per_session = 0.0;
};

enum class ScheduleUniverse : std::uint8_t {
  DEPLOYABLE_CLEAR_ONLY = 0,
  MECHANICAL_ALL,
};

// Hindsight weighted-interval ceiling: positive weights only, exact occupancy,
// <=3 per asset/day and <=9 per portfolio day.  It is not an arrival policy.
[[nodiscard]] Expected<ScheduleResult, Refusal> exact_schedule_ceiling(
    const std::vector<TeacherRow>& teacher,
    const std::vector<ExpectedSession>& expected_sessions,
    ScheduleUniverse universe = ScheduleUniverse::DEPLOYABLE_CLEAR_ONLY);

struct ArrivalThresholds {
  // Every participating asset must be explicitly present.  Values are frozen
  // outside this replay on an inner training fold; this module never fits one.
  std::map<qr::futsess::Asset, double> min_value_usd;
  std::string threshold_receipt_sha256;
};

// Chronological truth-score control.  At each exact arrival timestamp it sees
// current candidates' true values only; a later candidate cannot displace a
// prior entry.  It shares the ceiling's exact occupancy and count caps.
[[nodiscard]] Expected<ScheduleResult, Refusal> chronological_truth_arrival(
    const std::vector<TeacherRow>& teacher,
    const std::vector<ExpectedSession>& expected_sessions,
    const ArrivalThresholds& thresholds);

struct G1BuildStats {
  std::uint64_t sessions = 0;
  std::uint64_t no_candidate_sessions = 0;
  std::uint64_t candidates = 0;
  std::uint64_t teacher_ready = 0;
  std::uint64_t teacher_refused = 0;
  std::string manifest_sha256;
  std::string receipt_sha256;
};

// Artifact stages over the already-built QRE2 event namespace.  These never
// open raw DBN inputs and inherit Config's hard [20210101,20250701) wall.
[[nodiscard]] Expected<G1BuildStats, Refusal> build_g1_candidate_artifacts(
    const Config& config, const ComplianceCalendar* compliance = nullptr);
[[nodiscard]] Expected<G1BuildStats, Refusal> build_g1_teacher_artifacts(
    const Config& config);
[[nodiscard]] Expected<G1BuildStats, Refusal> build_g1_schedule_artifact(
    const std::vector<Config>& configs, bool arrival, ScheduleUniverse universe,
    const ArrivalThresholds* thresholds = nullptr);

}  // namespace qr::entry_v2

#endif  // QR_ENTRY_V2_G1_HPP
