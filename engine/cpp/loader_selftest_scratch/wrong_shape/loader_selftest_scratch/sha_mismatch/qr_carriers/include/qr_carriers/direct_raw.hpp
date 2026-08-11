// qr_carriers/direct_raw.hpp — DIRECT_RAW: EXACTLY 60 COLUMNS PER MODALITY.
//
// SPEC (evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 4, verbatim):
//
//   "`DIRECT_RAW` has per-modality summaries for windows {1,5,30,120}s: log
//    count, valid fraction, and mean/last of the four preregistered mechanism
//    channels (stock print: return/aggressor/signed-size/imbalance; NBBO:
//    mid-change/spread/imbalance/own-size-change; option: underlying-return/
//    aggressor/premium-flow/delta-flow), plus 20 full-window clock/order/
//    attachment-quality statistics. Exactly 60 columns/modality."
//
//   "For an empty window count/valid/mean/last are 0 and the full-window
//    nonempty bit is 0."
//
//   "The exact 20 full-window columns are: log1p token count; log1p timestamp-
//    group count; nonempty; all-four-mechanisms-finite group fraction;
//    raw-channel missing fraction; multi-token-group fraction; mean log1p group
//    multiplicity; max log1p group multiplicity; mean/p90/max log1p intergroup
//    gap microseconds (nearest-rank p90); log1p covered span microseconds;
//    log1p age of last group; log1p approach-group count; log1p response-group
//    count; omitted/total approach-group fraction; omitted/total response-group
//    fraction; unusable-attachment fraction; vendor-sequence inversion fraction;
//    and `r_modality = finite-all-four group count / max(group count,1)` (0 when
//    empty). For NBBO, attachment-invalid and sequence-inversion are typed
//    structural zeros."
//
//   "The two phase counts exclude groups exactly equal to newest same-side
//    visibility. A group with timestamp `< visibility` is APPROACH, `>
//    visibility` is RESPONSE, and `== visibility` is typed
//    `PHASE_EQUAL_UNORDERED`, receives no phase embedding, and enters neither
//    phase denominator. For each phase, omission is the number of its groups in
//    the complete 120s carrier that are truncated from recent128 divided by all
//    complete-120s groups of that phase; a zero denominator emits
//    value0/presence0. Raw missing fraction is exactly absent value cells
//    divided by `token_count * declared_value_channel_count`; zero tokens emits
//    value0/presence0. For stock/option prints, unusable attachment is one union
//    indicator per print over every quote/underlying clock or validity
//    dependency required by that print, divided by all prints—never multiple
//    counts for one print. NBBO remains structural0."
//
//   "Window `valid_fraction` uses timestamp-group count as denominator and
//    requires all four declared mechanism values; attachment/condition-quality
//    fractions use all prints in the window; reliability uses the exact
//    group-count formula above. No unavailable row is removed from a denominator."
//
// 4*10 + 20 = 60, and `kDirectColumnCount` is static_asserted to it: adding a
// window or a statistic breaks the build.
//
// THE COLUMN ORDER IS FROZEN HERE. Windows in the card's own order
// {1,5,30,120}s; inside a window: log count, valid fraction, then the four
// mechanisms mechanism-major as (mean, last) pairs; then the twenty full-window
// statistics in the card's own listed order. `direct_column_name` prints them.
//
// TWO READINGS THIS LANE FIXED, BOTH REPORTED AS STOP QUESTIONS:
//   1. A window's "log count" is the TOKEN (message) count, not its group
//      count: the transform table's count row names "message count" as its unit,
//      and the full-window block lists token count and group count as two
//      separate statistics precisely because it needs both — a window block that
//      meant the group count would make its own `valid fraction` denominator
//      redundant with it.
//   2. A window's `last` is the mechanism value of "the greatest strictly-prior
//      timestamp group" of that window, and is masked when THAT group's value is
//      absent. Searching backwards for the newest group that happens to carry a
//      value would be a rule the card does not state.
//
// PERFORMANCE (the plan's performance-budget rule — arithmetic before code).
// Every window is a contiguous suffix-anchored range of one session's group
// array, so every ADDITIVE statistic is an O(1) difference of prefix sums built
// once per session; only the three range statistics that are not additive (max
// log1p multiplicity, max log1p gap, nearest-rank p90 gap) touch the range, and
// they are SIDE-INVARIANT, so they are computed once per distinct window and
// reused by the LONG and SHORT rows of that cutoff. Prefix sums are double; the
// mechanism values are O(1)-O(10^2) and a session has <3x10^6 groups, so the
// running sum stays below ~3x10^8 and the differenced window mean carries an
// absolute error below 1e-9 — twelve orders of magnitude under the feature
// scale, and fully deterministic (two-run byte identity is unaffected).
#ifndef QR_CARRIERS_DIRECT_RAW_HPP
#define QR_CARRIERS_DIRECT_RAW_HPP

#include <array>
#include <cstdint>
#include <span>
#include <string>
#include <vector>

#include "qr_carriers/channels.hpp"
#include "qr_carriers/streams.hpp"
#include "qr_carriers/transforms.hpp"
#include "qr_core/refusal.hpp"

namespace qr::carriers {

/// The four window lengths, in the card's own order.
inline constexpr std::array<std::int64_t, 4> kDirectWindowSeconds{1, 5, 30, 120};
inline constexpr std::size_t kDirectWindowCount = 4;
/// log count, valid fraction, and (mean,last) per mechanism.
inline constexpr std::size_t kDirectPerWindowColumns = 2 + 2 * kMechanismCount;
inline constexpr std::size_t kDirectFullWindowColumns = 20;
inline constexpr std::size_t kDirectColumnCount =
    kDirectWindowCount * kDirectPerWindowColumns + kDirectFullWindowColumns;
static_assert(kDirectColumnCount == 60, "section 4: exactly 60 columns/modality");

/// The full-window block's column offsets, in the card's listed order.
enum DirectFullWindowColumn : std::size_t {
  kDirectLog1pTokenCount = 0,
  kDirectLog1pGroupCount = 1,
  kDirectNonempty = 2,
  kDirectAllFourFiniteGroupFraction = 3,
  kDirectRawMissingFraction = 4,
  kDirectMultiTokenGroupFraction = 5,
  kDirectMeanLog1pMultiplicity = 6,
  kDirectMaxLog1pMultiplicity = 7,
  kDirectMeanLog1pIntergroupGap = 8,
  kDirectP90Log1pIntergroupGap = 9,
  kDirectMaxLog1pIntergroupGap = 10,
  kDirectLog1pCoveredSpan = 11,
  kDirectLog1pAgeOfLastGroup = 12,
  kDirectLog1pApproachGroupCount = 13,
  kDirectLog1pResponseGroupCount = 14,
  kDirectApproachOmissionFraction = 15,
  kDirectResponseOmissionFraction = 16,
  kDirectUnusableAttachmentFraction = 17,
  kDirectSequenceInversionFraction = 18,
  kDirectRModality = 19,
};

/// The recent-128 micro carrier's length. It appears here — and ONLY here in
/// WP8a — because the two omission fractions are defined against it: "the number
/// of its groups in the complete 120s carrier that are truncated from recent128".
/// The carrier itself is WP8b.
inline constexpr std::size_t kMicroCarrierGroups = 128;

/// One modality's DIRECT_RAW row: the 60 values and their parallel presence.
///
/// APPENDIX C4 stores `direct_raw [N,3,60] f4` — sixty VALUES, with no separate
/// mask plane, because the card encodes absence as the value 0 plus the
/// structural bits already in the block (`nonempty`, the counts). The presence
/// array is retained here as the TYPED record so a fixture can assert the card's
/// literal "value0/presence0" instead of only "value 0".
struct DirectRawRow {
  std::array<double, kDirectColumnCount> value{};
  std::array<Validity, kDirectColumnCount> validity{};

  DirectRawRow() noexcept { validity.fill(Validity::MISSING); }

  void set(std::size_t column, Typed<double> typed) noexcept {
    value[column] = typed.v == Validity::VALID ? typed.value : 0.0;
    validity[column] = typed.v;
  }
  [[nodiscard]] bool presence(std::size_t column) const noexcept {
    return validity[column] == Validity::VALID;
  }
};

/// Frozen column names, all sixty (a census prints every one). The four
/// mechanism slots are named with the modality's OWN declared channel names, so
/// a census cannot silently print a stock-print header over option columns.
[[nodiscard]] std::string direct_column_name(Modality modality, std::size_t column);
/// The first column of window `index` (0..3).
[[nodiscard]] constexpr std::size_t direct_window_offset(std::size_t index) noexcept {
  return index * kDirectPerWindowColumns;
}
/// The first column of the full-window block.
inline constexpr std::size_t kDirectFullWindowOffset =
    kDirectWindowCount * kDirectPerWindowColumns;

// ---------------------------------------------------------------------------
// The decision's window definition.
// ---------------------------------------------------------------------------

/// One decision's feature window, in frame-A nanoseconds.
///
/// "Feature windows are `[max(session_open, decision-120s), decision)`" and
/// "Current/equal-cutoff tokens are excluded" — the range is left-closed and
/// right-OPEN, and `window_start` is computed here rather than by a caller.
struct DecisionWindow {
  std::int64_t cutoff_ns_a = 0;
  std::int64_t session_open_ns_a = 0;
  Side side = Side::LONG;
  /// The newest SAME-SIDE authorizing visibility, the phase split's reference.
  /// A lawful action always has one (its own focal candidate is same-side and
  /// strictly earlier); an absent reference masks the four phase columns rather
  /// than inventing a split.
  bool phase_reference_present = false;
  std::int64_t phase_reference_ns_a = 0;

  [[nodiscard]] std::int64_t window_start_ns_a() const noexcept {
    const std::int64_t full = cutoff_ns_a - 120 * kNanosPerSecond;
    return full > session_open_ns_a ? full : session_open_ns_a;
  }
};

// ---------------------------------------------------------------------------
// The builder.
// ---------------------------------------------------------------------------

/// Builds DIRECT_RAW rows for ONE modality of ONE session.
///
/// Construction walks the session's groups once and builds the prefix sums;
/// `build` is then O(log G) plus one range pass per DISTINCT window.
class DirectRawBuilder {
 public:
  DirectRawBuilder(Modality modality, std::span<const GroupRecord> groups);

  [[nodiscard]] Expected<DirectRawRow, Refusal> build(const DecisionWindow& window);

  [[nodiscard]] Modality modality() const noexcept { return modality_; }
  [[nodiscard]] std::size_t group_count() const noexcept { return groups_.size(); }

 private:
  /// Half-open group index range of a timestamp interval.
  struct Range {
    std::size_t lo = 0;
    std::size_t hi = 0;
    [[nodiscard]] std::size_t size() const noexcept { return hi - lo; }
  };
  [[nodiscard]] Range range_for(std::int64_t from_ns, std::int64_t to_ns) const noexcept;
  [[nodiscard]] std::size_t lower_bound_ts(std::int64_t ts_ns) const noexcept;
  [[nodiscard]] std::size_t upper_bound_ts(std::int64_t ts_ns) const noexcept;
  void scan_range(const Range& range);

  Modality modality_;
  std::span<const GroupRecord> groups_;

  // --- prefix sums (index i holds the sum over groups [0, i)) ---------------
  std::vector<std::int64_t> pre_tokens_;
  std::vector<std::int64_t> pre_absent_cells_;
  std::vector<std::int64_t> pre_unusable_tokens_;
  std::vector<std::int32_t> pre_multi_token_groups_;
  std::vector<double> pre_log1p_multiplicity_;
  std::vector<double> pre_log1p_gap_;
  std::vector<std::int32_t> pre_sequence_pairs_;
  std::vector<std::int32_t> pre_sequence_inversions_;
  /// Side-indexed: [0] LONG, [1] SHORT.
  std::array<std::vector<std::int32_t>, 2> pre_all_four_;
  std::array<std::array<std::vector<double>, kMechanismCount>, 2> pre_mech_sum_;
  std::array<std::array<std::vector<std::int32_t>, kMechanismCount>, 2> pre_mech_count_;

  // --- the memoized side-invariant range statistics --------------------------
  Range scanned_{};
  bool scanned_valid_ = false;
  bool scan_has_multiplicity_ = false;
  double scan_max_log1p_multiplicity_ = 0.0;
  bool scan_has_gap_ = false;
  double scan_max_log1p_gap_ = 0.0;
  double scan_p90_log1p_gap_ = 0.0;
  std::vector<double> gap_scratch_;
};

}  // namespace qr::carriers

#endif  // QR_CARRIERS_DIRECT_RAW_HPP
