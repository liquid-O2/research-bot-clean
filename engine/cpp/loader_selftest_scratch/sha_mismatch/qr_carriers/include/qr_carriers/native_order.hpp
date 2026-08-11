// qr_carriers/native_order.hpp — THE TWO NATIVE_ORDER CARRIERS.
//
// SPEC (evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 4,
// `NATIVE_ORDER`, verbatim):
//
//   "The micro carrier is the most recent 128 groups strictly before cutoff,
//    chronological, with a learned bias-free two-state 2x64 approach/response
//    embedding added according to whether each group is strictly before or
//    after the newest same-side authorizing visibility. Visibility-equal groups
//    are retained as `PHASE_EQUAL_UNORDERED` with zero phase embedding, and
//    typed left pad and truncation counts are retained. Second, the full carrier
//    is exactly 120 complete left-closed/right-open one-second bins
//    `[cutoff-120s+i,cutoff-120s+(i+1)s)`, `i=0..119`, spanning
//    `[cutoff-120s,cutoff)`; equal-cutoff groups are excluded. Within a bin, the
//    64d equal-time group embeddings are reduced by mean+max plus log group
//    count/nonempty, then projected `130->64`; pre-open bins are typed zero left
//    pad. ... Its ordered 120-bin sequence is never truncated."
//
//   "A group with timestamp `< visibility` is APPROACH, `> visibility` is
//    RESPONSE, and `== visibility` is typed `PHASE_EQUAL_UNORDERED`, receives no
//    phase embedding, and enters neither phase denominator."
//
// WHAT THIS MODULE EMITS, AND WHAT IT DOES NOT. The 64d embeddings, the phase
// table and the `130->64` reducer are learned Python parameters. C++ emits the
// REDUCED VECTORS (group_vector.hpp), their timestamps, the per-decision group
// MEMBERSHIP of both carriers and the phase split — exactly APPENDIX C4's
// `groups_{mod} [G,69|65|89] f4; group_ts [G] i8; recent128 [N,2] i4;
// phase_split [N] i4; bins_index [N,120,2] i4`. Every quantity the card lists
// inside a bin is therefore either emitted or an exact function of what is
// emitted: `log group count` is `log1p(len)` and `nonempty` is `len>0`, both
// carried here as typed values so a fixture can assert the card's own words.
//
// THE MICRO CARRIER IS NOT WINDOW-LIMITED. "the most recent 128 groups strictly
// before cutoff" has no 120s clause, and the DIRECT omission fractions are
// defined as the complete-120s groups that are "truncated from recent128" —
// which is only a coherent quantity if recent128 may reach FURTHER BACK than
// 120s. So the retained set is the last min(128, P) of the session's P groups
// strictly before the cutoff, and DIRECT's `truncated = max(0, W-128)` (W = the
// 120s window's group count) is the same set restricted to that window. The two
// constructors are cross-checked against each other by fixture.
//
// TWO CONSEQUENCES OF THAT DEFINITION, BOTH EMITTED RATHER THAN RECOMPUTED:
//   * `left_pad = 128 - length` — the typed zero left pad early in a session;
//   * `truncated = start` — the count of pre-cutoff groups the 128 cap dropped,
//     because the retained run is a SUFFIX of the pre-cutoff prefix, so its
//     start index IS the number of groups it left behind.
//
// A PRE-OPEN BIN IS ONE THAT ENDS AT OR BEFORE THE SESSION OPEN (lane ruling,
// reported as a STOP question). A bin that straddles the open carries real
// in-session support and can hold groups, so calling it a pad would zero a bin
// that has data; a bin whose right edge is at or before the open cannot contain
// any group at all. Pads are emitted as `start=-1, len=0`, which is a value no
// in-session bin can take (an empty in-session bin is `start>=0, len=0`) — so
// the C4 leaf distinguishes "typed zero left pad, validity 0" from "a real bin
// that happened to be empty, validity 1" with no extra leaf.
//
// AN ABSENT VISIBILITY REFERENCE LABELS EVERY GROUP `PHASE_EQUAL_UNORDERED`
// (lane ruling, reported as a STOP question). The card gives the phase embedding
// exactly one reference — the newest same-side authorizing visibility — and
// gives `PHASE_EQUAL_UNORDERED` the meaning "no phase embedding". With no
// reference there is no phase to claim, and zero phase embedding is the state
// the card already defines for that. This matches DIRECT_RAW, which masks its
// four phase columns rather than inventing a split.
//
// THE DESTRUCTIONS LIVE IN THIS CONSTRUCTOR, BEHIND FLAGS (section 7 (e) and
// (f), and FINAL_PLAN section 6's "destructions in the SAME constructors"):
//
//   (e) "reversing the valid recent-128 timestamp-group sequence is reported,
//        while any within-timestamp permutation must be bit-identical";
//   (f) "`BIN_ORDER_REVERSE` reverses the value+mask tuples only within the
//        ordered valid in-session support of the 120 bins, leaves fixed pre-open
//        pads/validity in place, keeps the valid-bin multiset and every
//        DIRECT/micro input bit-identical".
//
// AND THEY MAY NOT LEAK. Two independent walls, both fixtured:
//   1. `QR_CARRIERS_NO_DESTRUCTIONS` compiles the flag code — and the flags
//      themselves — out entirely, and `qr_carriers_nodestruct_probe` proves the
//      production bytes of a fixed tape are identical to the ordinary build's;
//   2. the emission door (`NativeOrderShard::push_decision`) REFUSES a carrier
//      whose slots are not the production chronological run, so a destroyed
//      carrier cannot be written into a C4 tape even by mistake.
#ifndef QR_CARRIERS_NATIVE_ORDER_HPP
#define QR_CARRIERS_NATIVE_ORDER_HPP

#include <array>
#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <vector>

#include "qr_carriers/direct_raw.hpp"
#include "qr_carriers/group_vector.hpp"
#include "qr_carriers/streams.hpp"
#include "qr_core/refusal.hpp"

namespace qr::carriers {

/// "exactly 120 complete left-closed/right-open one-second bins".
inline constexpr std::size_t kBinCarrierBins = 120;
/// One bin is exactly one second.
inline constexpr std::int64_t kBinWidthNs = kNanosPerSecond;
/// The carrier spans `[cutoff-120s, cutoff)`.
inline constexpr std::int64_t kBinCarrierSpanNs =
    static_cast<std::int64_t>(kBinCarrierBins) * kBinWidthNs;

static_assert(kMicroCarrierGroups == 128, "section 4: the micro carrier is 128 groups");
static_assert(kBinCarrierBins == 120, "section 4: the full carrier is 120 one-second bins");

// ---------------------------------------------------------------------------
// The phase label.
// ---------------------------------------------------------------------------

/// The card's three phase states, plus the carrier's own typed pad.
enum class Phase : std::uint8_t {
  APPROACH = 0,               ///< group timestamp < newest same-side visibility
  RESPONSE = 1,               ///< group timestamp > newest same-side visibility
  PHASE_EQUAL_UNORDERED = 2,  ///< == visibility (or no reference): zero phase embedding
  PAD = 3,                    ///< a typed left-pad slot; there is no group here
};
inline constexpr std::size_t kPhaseCount = 4;
[[nodiscard]] const char* phase_name(Phase phase) noexcept;

/// Where the visibility reference falls in a modality's group table: the groups
/// `[0, equal_lo)` are APPROACH, `[equal_lo, equal_hi)` are the (at most one)
/// visibility-equal group, and `[equal_hi, G)` are RESPONSE.
///
/// APPENDIX C4 writes `phase_split [N] i4`; this carries TWO indices because one
/// cannot express `PHASE_EQUAL_UNORDERED` — the card requires the equal group to
/// be distinguishable from both phases and to enter neither denominator, and the
/// consumer has no other way to recover it (the decision's visibility timestamp
/// is not a C4 leaf). Reported as a STOP question; emitted as `[N,2] i4`.
struct PhaseSplit {
  std::int32_t equal_lo = 0;
  std::int32_t equal_hi = 0;
  bool reference_present = false;

  [[nodiscard]] Phase phase_of(std::int32_t group_index) const noexcept {
    if (!reference_present) {
      return Phase::PHASE_EQUAL_UNORDERED;
    }
    if (group_index < equal_lo) {
      return Phase::APPROACH;
    }
    if (group_index >= equal_hi) {
      return Phase::RESPONSE;
    }
    return Phase::PHASE_EQUAL_UNORDERED;
  }
};

// ---------------------------------------------------------------------------
// The two carriers.
// ---------------------------------------------------------------------------

/// "the most recent 128 groups strictly before cutoff, chronological ... typed
/// left pad and truncation counts are retained".
struct MicroCarrier {
  /// Group index of the oldest retained group (and, by the header's argument,
  /// the count of pre-cutoff groups the 128 cap dropped).
  std::int32_t start = 0;
  std::int32_t length = 0;    ///< retained groups, <= 128
  std::int32_t left_pad = 0;  ///< 128 - length, typed zero slots at the LEFT
  std::int32_t truncated = 0; ///< == start
  /// Slot `i` holds this group index, or -1 on a typed left-pad slot.
  std::array<std::int32_t, kMicroCarrierGroups> slot_group{};
  std::array<Phase, kMicroCarrierGroups> slot_phase{};
  /// Slot counts per phase — the census the probe prints.
  std::array<std::int32_t, kPhaseCount> phase_slots{};

  [[nodiscard]] bool is_pad(std::size_t slot) const noexcept { return slot_group[slot] < 0; }
};

/// "exactly 120 complete left-closed/right-open one-second bins ... pre-open
/// bins are typed zero left pad ... never truncated".
struct BinCarrier {
  /// First group index of bin `i`, or -1 when the bin is a pre-open pad.
  std::array<std::int32_t, kBinCarrierBins> start{};
  std::array<std::int32_t, kBinCarrierBins> length{};
  /// "log group count" and "nonempty", carried as typed values so a fixture can
  /// assert the card's words rather than a derived integer.
  std::array<double, kBinCarrierBins> log1p_group_count{};
  std::array<std::uint8_t, kBinCarrierBins> nonempty{};
  /// 0 exactly on a pre-open pad bin (the card's "typed zero left pad").
  std::array<std::uint8_t, kBinCarrierBins> valid{};
  std::int32_t pre_open_pad_bins = 0;
  std::int32_t nonempty_bins = 0;
  std::int32_t member_groups = 0;

  [[nodiscard]] bool is_pad(std::size_t bin) const noexcept { return valid[bin] == 0U; }
};

#ifndef QR_CARRIERS_NO_DESTRUCTIONS
/// The section-7 destructions, OFF by default. Under
/// `QR_CARRIERS_NO_DESTRUCTIONS` this type and every use of it is compiled out,
/// which is what `qr_carriers_nodestruct_probe` exists to prove is invisible.
struct NativeCarrierControls {
  /// (e) reverse the valid recent-128 group sequence (the left pad stays put).
  bool recent128_reverse = false;
  /// (f) BIN_ORDER_REVERSE over the ordered valid in-session bin support.
  bool bin_order_reverse = false;

  [[nodiscard]] bool any() const noexcept { return recent128_reverse || bin_order_reverse; }
};
#endif

// ---------------------------------------------------------------------------
// The builder.
// ---------------------------------------------------------------------------

/// Builds both native carriers for ONE modality of ONE session.
///
/// PERFORMANCE (the plan's performance-budget rule). The group table is sorted
/// by timestamp, so the micro carrier is one binary search and the bin carrier
/// is 121 binary searches over a SHRINKING subrange — `O(120 log G)` per
/// decision, never a walk over the window's groups (session 125's NBBO carries
/// ~14.4k groups per 120s window against 17,081 decisions, so the walk would be
/// 246M steps and the searches are ~29M comparisons).
class NativeOrderBuilder {
 public:
#ifdef QR_CARRIERS_NO_DESTRUCTIONS
  NativeOrderBuilder(Modality modality, std::span<const GroupRecord> groups);
#else
  NativeOrderBuilder(Modality modality, std::span<const GroupRecord> groups,
                     NativeCarrierControls controls = {});
#endif

  [[nodiscard]] Expected<MicroCarrier, Refusal> build_micro(const DecisionWindow& window) const;
  [[nodiscard]] Expected<BinCarrier, Refusal> build_bins(const DecisionWindow& window) const;
  /// The decision's phase split over the WHOLE group table.
  [[nodiscard]] PhaseSplit split_for(const DecisionWindow& window) const noexcept;

  [[nodiscard]] Modality modality() const noexcept { return modality_; }
  [[nodiscard]] std::size_t group_count() const noexcept { return groups_.size(); }
  /// Groups strictly before `cutoff_ns` — the micro carrier's source prefix.
  [[nodiscard]] std::size_t groups_before(std::int64_t cutoff_ns) const noexcept;

 private:
  [[nodiscard]] std::size_t lower_bound_ts(std::int64_t ts_ns, std::size_t from) const noexcept;
  [[nodiscard]] std::size_t upper_bound_ts(std::int64_t ts_ns, std::size_t from) const noexcept;

  Modality modality_;
  std::span<const GroupRecord> groups_;
#ifndef QR_CARRIERS_NO_DESTRUCTIONS
  NativeCarrierControls controls_{};
#endif
};

// ---------------------------------------------------------------------------
// The APPENDIX C4 leaves.
// ---------------------------------------------------------------------------

/// The six per-modality NATIVE_ORDER leaves of a C4 features/ section.
///
/// GROUPS, GROUP_TS and ORIENTATION are per `(session, modality)` — the group
/// table is SIDE-NEUTRAL (group_vector.hpp) and is written once, into the LONG
/// shard, with ORIENTATION carrying the frozen per-channel table the loader
/// applies to reach a side. RECENT128, PHASE_SPLIT and BINS_INDEX are per
/// `(session, side)` and are written into both shards.
enum class NativeLeaf : std::uint8_t {
  GROUPS,
  GROUP_TS,
  ORIENTATION,
  RECENT128,
  PHASE_SPLIT,
  BINS_INDEX,
};
inline constexpr std::size_t kNativeLeafCount = 6;
/// True for the three leaves that belong to the session rather than to a side.
[[nodiscard]] bool native_leaf_is_session_scoped(NativeLeaf leaf) noexcept;

/// `groups_stock_print`, `group_ts_stock_nbbo`, `bins_index_option_print`, ...
/// C4 names the group table `groups_{mod}`; every leaf indexed BY that table is
/// per-modality for the same reason (`G` differs per modality), so all five
/// carry the suffix.
[[nodiscard]] std::string native_leaf_name(NativeLeaf leaf, Modality modality);
[[nodiscard]] const char* modality_leaf_suffix(Modality modality) noexcept;

/// One modality's packed C4 leaves for one (session, side) shard.
///
/// THE EMISSION DOOR IS ALSO A DESTRUCTION WALL: `push_decision` refuses a micro
/// carrier whose slots are not the chronological production run and a bin
/// carrier whose bins are not in ascending order, so a section-7 destruction can
/// never be published as a production tape.
///
/// LIFETIME: the group VALUES are not copied — `group_values()` is a span over
/// the `GroupVectorTable` handed to the constructor (session 125's NBBO table is
/// 731MB per side, and the emitter streams it straight to the leaf), so that
/// table must outlive the shard. The timestamps ARE copied, because the group
/// records they come from are the stream's and the leaf needs them contiguous.
class NativeOrderShard {
 public:
  /// `vectors` must be the SIDE-NEUTRAL table of this modality's session.
  NativeOrderShard(Modality modality, std::span<const GroupRecord> groups,
                   const GroupVectorTable& vectors);

  /// Appends ONE decision's carrier membership; returns its row index.
  [[nodiscard]] Expected<std::size_t, Refusal> push_decision(const MicroCarrier& micro,
                                                             const BinCarrier& bins,
                                                             const PhaseSplit& split);

  [[nodiscard]] Modality modality() const noexcept { return modality_; }
  [[nodiscard]] std::int64_t decisions() const noexcept { return decisions_; }
  [[nodiscard]] std::int64_t groups() const noexcept { return groups_; }
  [[nodiscard]] std::size_t dim() const noexcept { return dim_; }

  [[nodiscard]] std::span<const float> group_values() const noexcept { return group_values_; }
  [[nodiscard]] std::span<const std::int64_t> group_ts() const noexcept { return group_ts_; }
  [[nodiscard]] std::span<const std::int32_t> recent128() const noexcept { return recent128_; }
  [[nodiscard]] std::span<const std::int32_t> phase_split() const noexcept { return phase_split_; }
  [[nodiscard]] std::span<const std::int32_t> bins_index() const noexcept { return bins_index_; }
  /// The frozen `[C,3]` orientation table (kind, swap partner, min slot).
  [[nodiscard]] std::span<const std::int32_t> orientation() const noexcept { return orientation_; }

  /// The C4 shape of one leaf, given the decisions pushed so far.
  [[nodiscard]] std::vector<std::int64_t> leaf_shape(NativeLeaf leaf) const;

 private:
  Modality modality_;
  std::size_t dim_ = 0;
  std::int64_t groups_ = 0;
  std::int64_t decisions_ = 0;
  std::span<const float> group_values_;
  std::vector<std::int64_t> group_ts_;
  std::vector<std::int32_t> recent128_;
  std::vector<std::int32_t> phase_split_;
  std::vector<std::int32_t> bins_index_;
  std::vector<std::int32_t> orientation_;
};

}  // namespace qr::carriers

#endif  // QR_CARRIERS_NATIVE_ORDER_HPP
