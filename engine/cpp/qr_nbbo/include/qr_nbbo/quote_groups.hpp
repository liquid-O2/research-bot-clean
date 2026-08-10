// qr_nbbo/quote_groups.hpp — the equal-millisecond NBBO group projection.
//
// SPEC (design/DESIGN_SUBSTRATE.md section 6): "`qr_nbbo` (equal-ms group
// machine + census)". SPEC (WP5 brief): "QuoteGroups CSR, QuoteKind/
// QualityFlags, FullDayQuoteCensus, share-era normalization + FINAL_PLAN
// APPENDIX C1 typed states".
// SPEC (design/DESIGN_SUBSTRATE.md APPENDIX C5): the labels kernel is
// `label_action(QuoteGroups&, ActionKey, Side)` — this is that `QuoteGroups`.
// Port reference (read-only, semantics-exact):
//   /workspace/engine/crates/corpus/src/reader.rs
//     QuoteKind          :205-217
//     QualityFlags(u32)  :219-236
//     QuoteGroups CSR    :238-322   (offsets carry len()+1 entries, never [])
//     add_member         :622-657   (THE structural-validity predicate)
//     push_pending_group :691-755   (THE kind/quality/dedup authority)
//
// THREE VIEWS OF ONE GROUP LIVE HERE, AND THEY ARE NOT THE SAME VIEW. The
// reference itself carries two of them and APPENDIX C1 adds the third; WP5
// ports all three rather than collapsing them (D-017: the full vocabulary, not
// a subset):
//
//   1. THE CSR VIEW (frozen reference bytes). `structurally_valid_count`,
//      the scientific/wide midpoint split, `kind` and `quality` are the
//      reference's own classification, ported literally — including the two
//      places it is deliberately LOOSE: a LOCKED quote (ask == bid) is
//      structurally valid there, and a member whose bid+ask is odd is not
//      (its midpoint would not be an exact u6 integer). WP9's byte
//      differential compares these columns against the frozen Rust reader, so
//      "improving" either rule would be a defect, not a fix.
//   2. THE CENSUS VIEW (`census.hpp`): the seven-way `QuoteState` histogram
//      the reference computes for its full-day census, ported literally.
//   3. THE TYPED VIEW (APPENDIX C1 + task-card V4 section 4): a member is
//      ELIGIBLE only when it is finite, bid > 0, ask > 0, **ask > bid**, and
//      both conditions are code 0. Locked, crossed, one-sided, nonpositive,
//      nonfinite and condition-ineligible members stay as typed quality
//      tokens with their economic values MASKED — a `Validity`, never a
//      sentinel value (the WP4 mask law: absence is a state, never a number
//      that can be summed into a statistic by accident).
//
// THE SCALAR-MEANS-BEFORE-DERIVED LAW (task card V4 section 4, verbatim):
// "NBBO prior/current midpoint and imbalance are derived only **after** those
// scalar means, never by averaging per-row midpoint or imbalance."  So this
// projection stores the four PRIMITIVE scalar reductions — exact integer sums
// of bid, ask, bid size and ask size over the eligible members, with their
// count — and derives the midpoint from those two means. Sums are exact
// integers, so the reduction is permutation-invariant by construction and not
// merely by canonical input order.
#ifndef QR_NBBO_QUOTE_GROUPS_HPP
#define QR_NBBO_QUOTE_GROUPS_HPP

#include <cstddef>
#include <cstdint>
#include <span>
#include <string_view>
#include <vector>

#include "qr_core/checked.hpp"
#include "qr_core/refusal.hpp"
#include "qr_core/validity.hpp"

namespace qr::nbbo {

// ---------------------------------------------------------------------------
// Frozen constants (reader.rs:48-53).
// ---------------------------------------------------------------------------

/// "A quote is scientific (tight) when its spread is at most 50 bps of the
/// bid+ask total, i.e. `spread / mid <= 50bps` restated to avoid division"
/// (reader.rs:48-50). The restatement is `spread * 20_000 <= 50 * total`,
/// because `mid = total / 2` and one bp is 1/10,000.
inline constexpr std::int64_t kMaxScientificSpreadBps = 50;
/// The multiplier the division-free restatement uses: 2 (mid = total/2) x
/// 10,000 (bps).
inline constexpr std::int64_t kScientificSpreadScale = 20'000;
/// "Sanity ceiling on a normalized u6 price ($1,000,000/share); guards against
/// a corrupt or misinterpreted price column rather than any real quote"
/// (reader.rs:51-53).
inline constexpr std::int64_t kMaxNormalizedNbboPriceU6 = 1'000'000'000'000;

// ---------------------------------------------------------------------------
// QuoteKind — what kind of clean NBBO quote (if any) a group resolved to.
// ---------------------------------------------------------------------------

/// Exact port of `corpus::reader::QuoteKind` (reader.rs:205-217).
enum class QuoteKind : std::uint8_t {
  /// Exactly one scientific (tight-spread) midpoint: the unambiguous quote.
  SINGLE_SCIENTIFIC = 0,
  /// More than one distinct scientific midpoint at the same millisecond
  /// (multiple exchanges disagreed): ambiguous.
  MULTI_SCIENTIFIC = 1,
  /// No scientific midpoint, but at least one wide-spread midpoint.
  WIDE_ONLY = 2,
  /// No valid member at all: every raw tick in the group was rejected.
  UNRESOLVED = 3,
};

inline constexpr std::size_t kQuoteKindCount = 4;

/// Stable screaming-snake name (never a sentence).
[[nodiscard]] const char* quote_kind_name(QuoteKind kind) noexcept;

// ---------------------------------------------------------------------------
// QualityFlags — the six per-group quality bits.
// ---------------------------------------------------------------------------

/// Exact port of `corpus::reader::QualityFlags` (reader.rs:219-236), which the
/// reference in turn mirrors from `archive/.../scientific_path.rs`. The bit
/// VALUES are frozen: a downstream census keyed by bit position must not move
/// when a flag is added.
struct QualityFlags {
  static constexpr std::uint32_t LOCKED = 1U << 0;
  static constexpr std::uint32_t WIDE_SPREAD = 1U << 1;
  static constexpr std::uint32_t MIXED_REJECTED = 1U << 2;
  static constexpr std::uint32_t REJECTED_ONLY = 1U << 3;
  static constexpr std::uint32_t MIXED_SCIENTIFIC_WIDE = 1U << 4;
  static constexpr std::uint32_t WIDE_ONLY = 1U << 5;

  std::uint32_t bits = 0;

  [[nodiscard]] constexpr bool contains(std::uint32_t flag) const noexcept {
    return (bits & flag) == flag;
  }
  friend constexpr bool operator==(QualityFlags lhs, QualityFlags rhs) noexcept {
    return lhs.bits == rhs.bits;
  }
};

inline constexpr std::size_t kQualityFlagCount = 6;

/// The six flags in bit order, for censuses that print every one of them.
[[nodiscard]] std::uint32_t quality_flag_at(std::size_t index) noexcept;
/// Stable screaming-snake name of the flag at `index` (never a sentence).
[[nodiscard]] const char* quality_flag_name(std::size_t index) noexcept;

// ---------------------------------------------------------------------------
// The typed scalar reduction (task card V4 section 4).
// ---------------------------------------------------------------------------

/// One primitive scalar's group reduction: an EXACT integer sum over the
/// eligible members and their count.
///
/// The sum is kept exact and the mean is a checked truncating division AT THE
/// ACCESSOR, for three reasons: integer addition is associative and
/// commutative, so the reduction is permutation-invariant without relying on
/// any input order; nothing is rounded away before a consumer that may need
/// the exact numerator; and no floating-point accumulation enters a path whose
/// two-run byte identity is a law.
struct ScalarMean {
  std::int64_t sum = 0;
  std::int64_t count = 0;

  /// The truncating mean, or MISSING when no member was eligible. Absence is a
  /// typed state with a masked (zero) value — never a sentinel number.
  [[nodiscard]] Typed<std::int64_t> mean() const noexcept {
    if (count <= 0) {
      return Typed<std::int64_t>{0, Validity::MISSING};
    }
    return Typed<std::int64_t>{sum / count, Validity::VALID};
  }
  friend constexpr bool operator==(const ScalarMean& lhs, const ScalarMean& rhs) noexcept {
    return lhs.sum == rhs.sum && lhs.count == rhs.count;
  }
};

/// The four separate primitive scalar means of one equal-time group, plus the
/// quantities DERIVED FROM THEM (never from per-row derived values).
struct GroupScalars {
  ScalarMean bid_u6;
  ScalarMean ask_u6;
  ScalarMean bid_shares;
  ScalarMean ask_shares;

  /// Eligible member count (identical for all four scalars: an eligible member
  /// carries all four fields, by definition of eligibility).
  [[nodiscard]] std::int64_t eligible_count() const noexcept { return bid_u6.count; }

  /// THE DERIVED MIDPOINT. `(mean(bid) + mean(ask)) / 2`, computed AFTER the
  /// two scalar means — this is the law, and `mean((bid_i + ask_i) / 2)` is
  /// the named mutant it must never become.
  [[nodiscard]] Expected<Typed<std::int64_t>, Refusal> mid_u6() const noexcept;

  /// THE DERIVED SPREAD. `mean(ask) - mean(bid)`, same law, same order.
  [[nodiscard]] Expected<Typed<std::int64_t>, Refusal> spread_u6() const noexcept;

  /// THE DERIVED DEPTH IMBALANCE (orchestrator ruling CC-005, verbatim):
  ///
  ///   imbalance = (mean_bid_size - mean_ask_size)
  ///             / (mean_bid_size + mean_ask_size)
  ///
  /// "computed from the separate scalar group means (permutation-invariant),
  /// zero denominator => typed missing; bounded [-1,1]; sigma-orientation
  /// applied at the WP8 channel layer (own=bid for LONG). The legacy
  /// ln(bid/ask) is a price ratio, not the depth imbalance the card's channel
  /// list means — not adopted."
  ///
  /// A COMPOSED ACCESSOR, not a stored column: it is a pure function of the
  /// two size means already retained exactly (sum + count), so it adds no
  /// floating-point value to the serialized byte string whose two-run identity
  /// is a law, and any later rounding or orientation law composes on top of
  /// the same exact integers.
  [[nodiscard]] Expected<Typed<double>, Refusal> imbalance() const noexcept;
};

// ---------------------------------------------------------------------------
// The frozen prior-group state.
// ---------------------------------------------------------------------------

/// The nearest strictly-earlier ELIGIBLE group's scalar means, frozen.
///
/// Task card V4 section 4, verbatim: "Every member of the current equal-time
/// group compares to that one frozen prior-group mean; only after the whole
/// current group is reduced does its eligible finite mean replace the prior
/// state." A group with no eligible member never becomes the prior — the law
/// says "the nearest strictly-earlier ELIGIBLE timestamp group" — and an
/// absent prior is MISSING, not zero.
struct PriorGroupState {
  bool present = false;
  /// Frame-B millisecond and frame-A nanosecond of the group that set it.
  std::int64_t ts_ms_b = 0;
  std::int64_t ts_ns_a = 0;
  GroupScalars scalars{};

  [[nodiscard]] Validity validity() const noexcept {
    return present ? Validity::VALID : Validity::MISSING;
  }
};

// ---------------------------------------------------------------------------
// QuoteGroups — the CSR projection.
// ---------------------------------------------------------------------------

/// Complete equal-millisecond NBBO group projection for one session, in causal
/// (timestamp) order. Every millisecond that had at least one raw tick during
/// regular trading hours gets a row, including rejected-only and wide-only
/// ones — downstream consumers decide what to do with those; this projection
/// discards nothing (reader.rs:238-247).
///
/// The two `*_offsets` arrays are CSR offsets into their matching `*_u6`
/// array: group `i`'s midpoints are `midpoints_u6[offsets[i]..offsets[i+1]]`,
/// deduplicated and sorted ascending. Each has exactly `size() + 1` entries —
/// the empty projection therefore holds `{0}`, never `{}`. That invariant is
/// not decoration: the reference's own 2026-08-05 production probe caught a
/// derived `Default` building offsets one short on every real session while
/// hand-built fixtures satisfied it (reader.rs:265-274).
class QuoteGroups {
 public:
  QuoteGroups() { clear(); }

  /// Reserves for `groups` groups. The CSR invariant holds at every size.
  void reserve(std::size_t groups);
  void clear();

  [[nodiscard]] std::size_t size() const noexcept { return ts_ns.size(); }
  [[nodiscard]] bool empty() const noexcept { return ts_ns.empty(); }

  /// The scientific (tight-spread) midpoints of group `index`, deduplicated
  /// and sorted ascending.
  [[nodiscard]] std::span<const std::int64_t> scientific_midpoints(std::size_t index) const;
  /// The wide-spread midpoints of group `index`, deduplicated and ascending.
  [[nodiscard]] std::span<const std::int64_t> wide_midpoints(std::size_t index) const;

  /// The four separate primitive scalar means of group `index`.
  [[nodiscard]] GroupScalars scalars(std::size_t index) const;

  /// Every column of one group, appended field by field in little-endian
  /// order: the serialization the two-run-identity and permutation fixtures
  /// compare. No padding, no pointers, no addresses (FINAL_PLAN section 6).
  void append_serialized(std::size_t index, std::vector<std::uint8_t>& out) const;

  // --- the frozen reference columns (reader.rs:248-263) --------------------
  std::vector<std::int64_t> ts_ns;
  std::vector<std::uint32_t> raw_member_count;
  std::vector<std::uint32_t> structurally_valid_count;
  std::vector<std::uint32_t> scientific_member_count;
  std::vector<std::uint32_t> wide_member_count;
  std::vector<std::uint32_t> rejected_member_count;
  /// `std::uint8_t` and not `bool`: `std::vector<bool>` is a bitset whose
  /// elements have no address, and every column here must serialize as bytes.
  std::vector<std::uint8_t> has_locked_member;
  std::vector<QuoteKind> kind;
  std::vector<QualityFlags> quality;
  std::vector<std::uint32_t> scientific_midpoint_offsets;
  std::vector<std::int64_t> scientific_midpoints_u6;
  std::vector<std::uint32_t> wide_midpoint_offsets;
  std::vector<std::int64_t> wide_midpoints_u6;

  // --- the typed columns (APPENDIX C1 + card V4 section 4) ----------------
  /// Frame-B millisecond of the group, retained beside its frame-A image so a
  /// consumer never has to invert the clock to recover the tape's own stamp.
  std::vector<std::int64_t> ts_ms_b;
  /// Worst-wins combination of every member's `Validity` — the group's quality
  /// token. It does NOT gate the scalar means (a crossed member among four
  /// good ones masks itself, not the group); `mean_validity` does.
  std::vector<Validity> group_validity;
  /// VALID exactly when at least one member was eligible; MISSING otherwise.
  /// This is what masks the means and everything derived from them.
  std::vector<Validity> mean_validity;
  /// Bit `k` set == at least one member of this group was in `QuoteState(k)`.
  /// The card's per-group `locked` / `crossed` / `positive-two-sided` channels
  /// read these bits; the day-level per-state member COUNTS live in the census.
  std::vector<std::uint16_t> state_mask;
  /// The four EXACT primitive sums over the eligible members, and their count.
  std::vector<std::int64_t> eligible_count;
  std::vector<std::int64_t> bid_u6_sum;
  std::vector<std::int64_t> ask_u6_sum;
  std::vector<std::int64_t> bid_shares_sum;
  std::vector<std::int64_t> ask_shares_sum;
  /// Derived AFTER the scalar means (never from per-row midpoints), masked by
  /// `mean_validity`.
  std::vector<std::int64_t> mid_u6;
  /// `mid_u6` minus the FROZEN prior eligible group's midpoint, itself derived
  /// after that group's scalar means. MISSING until a prior eligible group
  /// exists ("an absent eligible group yields missing/unresolved").
  std::vector<std::int64_t> mid_change_u6;
  std::vector<Validity> mid_change_validity;
  /// Frame-A nanoseconds of the frozen prior eligible group, and its validity.
  std::vector<std::int64_t> prior_ts_ns;
  std::vector<Validity> prior_validity;

 private:
  [[nodiscard]] std::span<const std::int64_t> csr_slice(
      const std::vector<std::uint32_t>& offsets, const std::vector<std::int64_t>& values,
      std::size_t index) const;
};

}  // namespace qr::nbbo

#endif  // QR_NBBO_QUOTE_GROUPS_HPP
