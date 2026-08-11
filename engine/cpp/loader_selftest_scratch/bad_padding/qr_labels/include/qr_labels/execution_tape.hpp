// qr_labels/execution_tape.hpp — the equal-millisecond EXECUTION ENVELOPE and
// its range-extremum index.
//
// SPEC (verbatim, evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 3):
//   "entry = first eligible IWM quote group strictly after the decision; LONG
//    entry ask_max/mark bid_min, SHORT entry bid_min/mark ask_max; adverse wins
//    equal-ms"
// SPEC (card section 3, the barrier auxiliary): "Raw states are
//    FAVORABLE_FIRST, ADVERSE_FIRST, SAME_GROUP_ADVERSE, NEITHER"
//
// WHY THIS TYPE EXISTS, AND THE ONE DECLARED DEVIATION FROM APPENDIX C5.
// APPENDIX C5 spells the kernel as `label_action(QuoteGroups&, ActionKey,
// Side)`. `qr::nbbo::QuoteGroups` physically cannot answer it: by the
// scalar-means-before-derived law it stores EXACT SUMS and COUNTS of the
// eligible members' bids and asks (quote_groups.hpp, `GroupScalars`), and a
// sum plus a count does not determine an extremum. The card's fills are
// extrema — `ask_max`, `bid_min` — and the barrier's SAME_GROUP_ADVERSE state
// additionally needs the FAVORABLE extrema (`bid_max` for LONG, `ask_min` for
// SHORT), because a single conservative mark per group can never touch both
// barriers at one millisecond. So WP7 projects the four per-group extrema it
// needs, from the same rows, through the same eligibility authority
// (`qr::nbbo::classify_member`), and `verify_against` binds the result to the
// WP5 projection group for group. Nothing here re-decides eligibility and
// nothing here touches WP5's serialized bytes.
//
// ELIGIBILITY IS QR_NBBO'S, VERBATIM. A member is eligible exactly when
// `qr::nbbo::classify_member(row).validity == Validity::VALID` — finite,
// bid > 0, ask > 0, ask > bid, both conditions code 0, sizes present and
// positive. That predicate is the ONE authority; `verify_against` proves this
// tape's per-group eligible count equals WP5's `eligible_count` column, group
// for group, so the two modules cannot drift apart silently.
//
// THE TAPE IS THE SEQUENCE OF LAWFUL MARKS. Only eligible groups get a row: an
// ineligible millisecond is not a place a fill or a mark can happen, so "the
// NEXT lawful mark strictly after crossing" and "the first eligible group with
// ts >= entry + h" are both plain index arithmetic on this tape. The census
// retains how many groups were dropped and why, so nothing is silently thrown
// away.
#ifndef QR_LABELS_EXECUTION_TAPE_HPP
#define QR_LABELS_EXECUTION_TAPE_HPP

#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include "qr_clock/session_clock.hpp"
#include "qr_core/refusal.hpp"
#include "qr_labels/money.hpp"
#include "qr_nbbo/quote_groups.hpp"
#include "qr_registry/day_scope.hpp"
#include "qr_sources/stock_quotes.hpp"

namespace qr::labels {

/// Per-session counters of what the builder saw. Retained in full: a group
/// that carries no lawful mark is a census row, never a silent drop.
struct ExecutionTapeCensus {
  std::int64_t groups_seen = 0;
  std::int64_t groups_eligible = 0;
  std::int64_t groups_without_eligible_member = 0;
  std::int64_t eligible_members = 0;
  std::int64_t ineligible_members = 0;
  [[nodiscard]] std::string to_tsv(std::string_view label) const;
};

/// The four per-group execution extrema over the ELIGIBLE members of one
/// equal-millisecond group, in causal order, one row per eligible group.
struct ExecutionTape {
  /// Frame-A nanoseconds, strictly increasing.
  std::vector<std::int64_t> ts_ns;
  /// The ADVERSE LONG mark and the LONG-side barrier's adverse column.
  std::vector<std::int64_t> bid_min_u6;
  /// The FAVORABLE LONG mark (barrier only; never the primary).
  std::vector<std::int64_t> bid_max_u6;
  /// The FAVORABLE SHORT mark (barrier only; never the primary).
  std::vector<std::int64_t> ask_min_u6;
  /// The SHORT entry-side maximum: the LONG fill and the adverse SHORT mark.
  std::vector<std::int64_t> ask_max_u6;
  /// Eligible member count of the group (>= 1 for every retained row).
  std::vector<std::int64_t> eligible_count;

  std::int64_t session_ordinal = 0;
  std::string day;
  std::int64_t session_start_ns = 0;
  std::int64_t session_end_ns = 0;
  ExecutionTapeCensus census;

  [[nodiscard]] std::int64_t size() const noexcept {
    return static_cast<std::int64_t>(ts_ns.size());
  }
  [[nodiscard]] bool empty() const noexcept { return ts_ns.empty(); }

  /// THE ENTRY RULE's index half: the first lawful mark strictly after `ts`,
  /// or `kNoIndex`. Exact equality is excluded, by the card's own word
  /// "strictly".
  [[nodiscard]] std::int64_t first_strictly_after(std::int64_t ts) const noexcept;
  /// THE HORIZON RULE's index half: the first lawful mark at or after `ts`.
  [[nodiscard]] std::int64_t first_at_or_after(std::int64_t ts) const noexcept;

  /// The LONG fill / the SHORT fill of the group at `index` (card section 3:
  /// "LONG entry ask_max ... SHORT entry bid_min").
  [[nodiscard]] std::int64_t entry_price(std::int64_t index, Side side) const;
  /// The ADVERSE mark of the group at `index` ("adverse wins equal-ms"):
  /// bid_min for LONG, ask_max for SHORT. This is THE primary mark — menu,
  /// certificate, MAE and the wall all read it.
  [[nodiscard]] std::int64_t adverse_mark(std::int64_t index, Side side) const;
  /// The FAVORABLE mark of the group at `index`: bid_max for LONG, ask_min for
  /// SHORT. Read by the barrier auxiliary ONLY.
  [[nodiscard]] std::int64_t favorable_mark(std::int64_t index, Side side) const;

  /// Field-by-field little-endian serialization of one row: the byte string
  /// the two-run identity and permutation fixtures compare.
  void append_serialized(std::int64_t index, std::vector<std::uint8_t>& out) const;
};

// ---------------------------------------------------------------------------
// The builder.
// ---------------------------------------------------------------------------

/// Streams equal-millisecond groups into an `ExecutionTape`, in the same shape
/// as `qr::nbbo::GroupMachine` so that one pass over the WP4 reader can feed
/// both.
class ExecutionTapeBuilder {
 public:
  /// Production entry point: clock and identity come from the session's own
  /// authenticated registry row.
  [[nodiscard]] static Expected<ExecutionTapeBuilder, Refusal> for_scope(const DayScope& scope);
  /// Fixture entry point: an explicit clock, no payload path anywhere.
  [[nodiscard]] static ExecutionTapeBuilder from_clock(SessionClock clock,
                                                       std::int64_t session_ordinal);

  /// Reduces ONE complete equal-millisecond group. Returns whether the group
  /// carried at least one eligible member (i.e. whether a row was appended).
  /// Enforces, rather than assumes, that stamps strictly increase and that the
  /// group is inside this clock's frame-B RTH window.
  [[nodiscard]] Expected<bool, Refusal> push_group(
      std::int64_t ts_ms_b, std::span<const qr::sources::StockQuoteRow> rows);

  /// Freezes the tape.
  [[nodiscard]] Expected<ExecutionTape, Refusal> seal();

  [[nodiscard]] const ExecutionTapeCensus& census() const noexcept { return census_; }

 private:
  ExecutionTapeBuilder(SessionClock clock, std::int64_t session_ordinal);

  SessionClock clock_;
  ExecutionTape tape_;
  ExecutionTapeCensus census_;
  std::int64_t last_ts_ms_b_ = 0;
  bool has_last_ts_ = false;
  bool sealed_ = false;
};

/// Runs one authorized session end to end: opens nothing itself, drains the
/// WP4 reader group by group.
[[nodiscard]] qr::parquet::FileExpected<ExecutionTape> build_execution_tape(
    qr::sources::StockQuoteReader& reader, const DayScope& scope);

/// THE BINDING CHECK against the WP5 projection APPENDIX C5 names: same
/// session, same eligible groups in the same order, same eligible counts, and
/// every extremum inside the group's own exact scalar sum bounds. Refuses on
/// the first disagreement.
[[nodiscard]] Expected<std::int64_t, Refusal> verify_against(const ExecutionTape& tape,
                                                             const qr::nbbo::QuoteGroups& groups);

// ---------------------------------------------------------------------------
// The range-extremum index.
// ---------------------------------------------------------------------------

/// A min/max segment tree over one price column, with the three queries the
/// label kernel needs: the range extremum (MAE), the leftmost argument of the
/// range extremum (the certificate's "earliest group attaining the maximum"),
/// and the first index whose value crosses a threshold (the wall and the two
/// barriers).
///
/// WHY A TREE AND NOT A SCAN. Session 125 carries ~2.8M groups and the pass
/// labels tens of thousands of action rows; a per-row linear scan is 10^11
/// comparisons. Every query below is O(log n) and the kernel re-checks the
/// exact net at whatever index it returns, so the structure is an accelerator
/// and never an authority. `test_label_kernel.cpp` differentials the whole
/// kernel against a deliberately naive linear reference.
class ExtremumIndex {
 public:
  ExtremumIndex() = default;
  [[nodiscard]] static ExtremumIndex build(std::span<const std::int64_t> values);

  [[nodiscard]] std::int64_t size() const noexcept { return count_; }

  /// Inclusive-range minimum / maximum. Empty or out-of-domain ranges are a
  /// programmer-contract violation (fail fast), never a silent sentinel.
  [[nodiscard]] std::int64_t range_min(std::int64_t lo, std::int64_t hi) const;
  [[nodiscard]] std::int64_t range_max(std::int64_t lo, std::int64_t hi) const;
  /// The EARLIEST index attaining the range extremum ("tied maxima earliest").
  [[nodiscard]] std::int64_t leftmost_argmin(std::int64_t lo, std::int64_t hi) const;
  [[nodiscard]] std::int64_t leftmost_argmax(std::int64_t lo, std::int64_t hi) const;
  /// The first index in [lo,hi] whose value is <= / >= `threshold`, or
  /// `kNoIndex`.
  [[nodiscard]] std::int64_t first_at_or_below(std::int64_t lo, std::int64_t hi,
                                               std::int64_t threshold) const;
  [[nodiscard]] std::int64_t first_at_or_above(std::int64_t lo, std::int64_t hi,
                                               std::int64_t threshold) const;

 private:
  [[nodiscard]] std::int64_t descend_below(std::size_t node, std::int64_t node_lo,
                                           std::int64_t node_hi, std::int64_t lo, std::int64_t hi,
                                           std::int64_t threshold) const;
  [[nodiscard]] std::int64_t descend_above(std::size_t node, std::int64_t node_lo,
                                           std::int64_t node_hi, std::int64_t lo, std::int64_t hi,
                                           std::int64_t threshold) const;
  void check_range(std::int64_t lo, std::int64_t hi) const;

  std::int64_t count_ = 0;
  std::int64_t padded_ = 0;
  std::vector<std::int64_t> min_;
  std::vector<std::int64_t> max_;
};

/// One session's tape plus the four column indexes the kernel queries. This is
/// the object `label_action` takes in place of APPENDIX C5's `QuoteGroups&`
/// (see the deviation note at the top of this file).
class SessionLabelIndex {
 public:
  [[nodiscard]] static SessionLabelIndex build(ExecutionTape tape);

  [[nodiscard]] const ExecutionTape& tape() const noexcept { return tape_; }
  /// The index of the ADVERSE column of `side` (bid_min LONG / ask_max SHORT).
  [[nodiscard]] const ExtremumIndex& adverse(Side side) const noexcept {
    return side == Side::LONG ? bid_min_ : ask_max_;
  }
  /// The index of the FAVORABLE column of `side` (bid_max LONG / ask_min SHORT).
  [[nodiscard]] const ExtremumIndex& favorable(Side side) const noexcept {
    return side == Side::LONG ? bid_max_ : ask_min_;
  }

 private:
  explicit SessionLabelIndex(ExecutionTape tape);

  ExecutionTape tape_;
  ExtremumIndex bid_min_;
  ExtremumIndex bid_max_;
  ExtremumIndex ask_min_;
  ExtremumIndex ask_max_;
};

}  // namespace qr::labels

#endif  // QR_LABELS_EXECUTION_TAPE_HPP
