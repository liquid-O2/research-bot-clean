// qr_nbbo/group_machine.hpp — THE equal-millisecond NBBO group state machine.
//
// SPEC (design/DESIGN_SUBSTRATE.md section 6): "`qr_nbbo` (equal-ms group
// machine + census)".
// SPEC (WP5 brief), the laws that must survive the port EXACTLY:
//   * validity = finite, bid>0, ask>0, ask>bid, both conditions eligible
//     (code 0);
//   * locked (bid==ask), crossed (bid>ask), one-sided as typed quality tokens
//     with economic values MASKED (Validity states, not sentinel values);
//   * derived midpoint/imbalance computed from SEPARATE SCALAR GROUP MEANS,
//     never mean-of-row-derived (task card V4 section 4);
//   * prior-group state updates only after the complete group;
//   * permutation-invariant reductions.
// Port reference (read-only, semantics-exact):
//   /workspace/engine/crates/corpus/src/reader.rs
//     PendingGroup             :364-389
//     add_member               :622-657
//     finish_pending_group     :659-685   (the registry-count wall + the SOLE
//                                          frame-B -> frame-A conversion)
//     push_pending_group       :691-755   (kind / quality / dedup)
//     QuoteGroupAccumulator    :757-840   (the streaming shape this machine
//                                          takes: group key in, group out)
//     stream_full_day_session  :1353-1751 (the census accumulation and the
//                                          FULL_DAY_LEGACY_COUNTS seal)
//
// WHERE THE STATE LIVES. The machine holds exactly two pieces of state between
// groups, and they are updated at two different moments on purpose:
//
//   * the OUTPUT (`QuoteGroups` + `FullDayQuoteCensus`) grows as each group is
//     sealed;
//   * the PRIOR (`PriorGroupState`) is FROZEN for the whole of a group and is
//     replaced only after that group has been completely reduced, and only if
//     the group had an eligible member. Task card V4 section 4: "Every member
//     of the current equal-time group compares to that one frozen prior-group
//     mean; only after the whole current group is reduced does its eligible
//     finite mean replace the prior state." An implementation that updates the
//     prior inside the member loop leaks the first member of a group into the
//     comparison the second member makes — the named mutant M702.
//
// PERMUTATION INVARIANCE IS STRUCTURAL, NOT INCIDENTAL. Every reduction here
// is a count, an exact integer sum, a boolean OR, a max, or a sorted-and-
// deduplicated set. WP4's `GroupTape` already canonicalizes in-group row
// order, but this machine does not depend on that: feed it any permutation of
// a group's rows and every output byte is identical.
#ifndef QR_NBBO_GROUP_MACHINE_HPP
#define QR_NBBO_GROUP_MACHINE_HPP

#include <cstdint>
#include <span>
#include <string>
#include <utility>
#include <vector>

#include "qr_clock/session_clock.hpp"
#include "qr_core/refusal.hpp"
#include "qr_nbbo/census.hpp"
#include "qr_nbbo/quote_groups.hpp"
#include "qr_registry/day_scope.hpp"
#include "qr_sources/stock_quotes.hpp"

namespace qr::nbbo {

/// The registry facts a session's machine is pinned to. They are not
/// decoration: `complete_group_count` is a live wall during the pass (the
/// reference refuses the group that would exceed it, reader.rs:669-676) and
/// both counts are re-checked at the seal (reader.rs:1729-1738). This is the
/// stateful-machine half of FINAL_PLAN section 6's correctness oracle 2.
struct SessionPins {
  std::string day;
  SourceProfile profile = SourceProfile::CentInt32;
  std::int64_t raw_rth_row_count = 0;
  std::int64_t complete_group_count = 0;
};

/// One member's typed classification, in all three views at once.
struct MemberClass {
  QuoteState state = QuoteState::INVALID;
  Validity validity = Validity::MISSING;
  bool structurally_valid = false;
  bool locked = false;
  /// Set only when `structurally_valid`: the exact u6 midpoint and whether its
  /// spread cleared the 50 bp scientific bar.
  std::int64_t midpoint_u6 = 0;
  bool scientific = false;
};

/// Classifies one already-normalized NBBO row in all three views. Prices are
/// u6, sizes are SHARES (WP4 folded the 2025-11-03 lot->share era at its own
/// boundary, so nothing here knows about eras), and a null field is a mask bit
/// on the row, never a sentinel value.
[[nodiscard]] Expected<MemberClass, Refusal> classify_member(
    const qr::sources::StockQuoteRow& row) noexcept;

/// The reference's division-free scientific-spread test (reader.rs:649):
/// `spread * 20_000 <= 50 * (bid + ask)`, under checked arithmetic. Exposed by
/// name so the bar itself can be fixtured at the boundary.
[[nodiscard]] Expected<bool, Refusal> is_scientific_spread(std::int64_t bid_u6,
                                                           std::int64_t ask_u6) noexcept;

/// THE MACHINE.
class GroupMachine {
 public:
  /// The production entry point: clock and pins both come from the session's
  /// own authenticated registry row.
  [[nodiscard]] static Expected<GroupMachine, Refusal> for_scope(const DayScope& scope);

  /// The fixture entry point: an explicit clock and explicit pins, for the
  /// hand-built micro-tapes and the synthetic era pair. No payload path exists
  /// here — this constructor cannot open anything.
  [[nodiscard]] static GroupMachine from_clock(SessionClock clock, SessionPins pins);

  /// Reduces ONE complete equal-millisecond group and appends its row.
  /// Returns the group's ordinal.
  ///
  /// Preconditions the machine ENFORCES rather than assumes: the group's
  /// timestamp is strictly greater than the previous group's (equal-time runs
  /// are one group, by definition), the stamp is inside this clock's frame-B
  /// RTH window, and the registry's group count is not exceeded.
  [[nodiscard]] Expected<std::int64_t, Refusal> push_group(
      std::int64_t ts_ms_b, std::span<const qr::sources::StockQuoteRow> rows);

  /// Seals the pass: re-checks BOTH registry counts, records the reader's
  /// sentinel-row count, and freezes the census.
  [[nodiscard]] Expected<std::int64_t, Refusal> seal(std::int64_t sentinel_rows);

  [[nodiscard]] const QuoteGroups& groups() const noexcept { return groups_; }
  [[nodiscard]] const FullDayQuoteCensus& census() const noexcept { return census_; }
  /// The FROZEN prior-group state, observable so a fixture can watch WHEN it
  /// moves rather than only what it holds.
  [[nodiscard]] const PriorGroupState& prior() const noexcept { return prior_; }
  [[nodiscard]] const SessionPins& pins() const noexcept { return pins_; }
  [[nodiscard]] const SessionClock& clock() const noexcept { return clock_; }
  [[nodiscard]] bool sealed() const noexcept { return sealed_; }

  /// Every group's columns, serialized field by field: the byte string the
  /// two-run-identity and permutation fixtures compare.
  [[nodiscard]] std::vector<std::uint8_t> serialize() const;

 private:
  GroupMachine(SessionClock clock, SessionPins pins)
      : clock_(std::move(clock)), pins_(std::move(pins)) {}

  SessionClock clock_;
  SessionPins pins_;
  QuoteGroups groups_;
  FullDayQuoteCensus census_;
  PriorGroupState prior_;
  std::vector<std::int64_t> scientific_scratch_;
  std::vector<std::int64_t> wide_scratch_;
  std::int64_t last_ts_ms_b_ = 0;
  bool has_last_ts_ = false;
  bool sealed_ = false;
};

/// Runs a whole authorized session: opens nothing itself, drains the WP4
/// reader group by group, and seals against the registry. This is the
/// "full-day group machine run" of the WP5 real-file check.
[[nodiscard]] qr::parquet::FileExpected<GroupMachine> run_session(
    qr::sources::StockQuoteReader& reader, const DayScope& scope);

}  // namespace qr::nbbo

#endif  // QR_NBBO_GROUP_MACHINE_HPP
