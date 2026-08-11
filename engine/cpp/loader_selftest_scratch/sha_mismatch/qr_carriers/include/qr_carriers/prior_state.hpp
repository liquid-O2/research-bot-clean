// qr_carriers/prior_state.hpp — THE PRIOR-STATE MACHINES.
//
// SPEC (evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 4, verbatim):
//
//   "Every stateful prior is built by taking the finite eligible mean of each
//    primitive scalar separately over the nearest strictly-earlier timestamp
//    group: stock-print price/tick fallback; stock-NBBO bid, ask, bid size, and
//    ask size; and option-print price per exact contract. NBBO prior/current
//    midpoint and imbalance are derived only **after** those scalar means,
//    never by averaging per-row midpoint or imbalance. Option underlying uses
//    the attached-timestamp rule above. Every current-group member compares
//    only to the frozen prior; update occurs after the complete group, and an
//    absent eligible group yields missing/unresolved."
//
//   "Every member of the current equal-time group compares to that one frozen
//    prior-group mean; only after the whole current group is reduced does its
//    eligible finite mean replace the prior state."
//
//   "Underlying return compares that value to a global prior state constructed
//    only from earlier **print-timestamp groups**. After a complete print group
//    is processed, find the greatest valid `underlying_timestamp` observed among
//    its members and update the global prior to the finite positive mean of only
//    members sharing that timestamp. An absent valid attachment leaves the prior
//    unchanged. Same-group member order and rows from any later print group can
//    never enter that update."
//
//   "Sequence quality is also groupwise and permutation-invariant: for each
//    group take finite `seq_min` and `seq_max`; against the nearest
//    strictly-earlier sequence-valid group, `sequence_gap = current_seq_min -
//    previous_seq_max`, stored as signed-log, `sequence_monotone = (gap>=0)`,
//    and `sequence_inversion = (gap<0)`. The first sequence-valid group and
//    groups with no finite sequence have all three missing. The previous group
//    updates only after the current group is complete; the inversion-fraction
//    denominator is adjacent valid-group pairs."
//
//   "Group interarrival is present only from the second timestamp group onward."
//
// EVERY MACHINE HERE HAS THE SAME THREE-BEAT SHAPE, and the beats are separate
// functions ON PURPOSE — `begin_group` / `observe...` / `commit_group`. The
// named mutant this shape exists to kill (M702's carriers analogue) updates the
// prior inside the member loop, which leaks member 1 of a group into the
// comparison member 2 makes. A machine whose update is a distinct call cannot
// do that by accident, and a fixture can watch WHEN the prior moves rather than
// only what it holds.
//
// EXACT INTEGER SUMS, NOT RUNNING DOUBLES. Every scalar reduction is an i64 sum
// plus a count, so it is associative and commutative and therefore
// permutation-invariant by construction rather than by canonical input order —
// the same law qr_nbbo/quote_groups.hpp states for `ScalarMean`. The mean is a
// checked truncating division taken at the accessor.
#ifndef QR_CARRIERS_PRIOR_STATE_HPP
#define QR_CARRIERS_PRIOR_STATE_HPP

#include <cstdint>
#include <map>
#include <optional>

#include "qr_carriers/transforms.hpp"
#include "qr_core/checked.hpp"
#include "qr_core/refusal.hpp"
#include "qr_core/validity.hpp"
#include "qr_sources/normalize.hpp"

namespace qr::carriers {

// ---------------------------------------------------------------------------
// One primitive scalar.
// ---------------------------------------------------------------------------

/// An EXACT integer sum over the eligible members of one group, plus their
/// count. `add` refuses on overflow instead of wrapping or saturating; the
/// caller turns that into an ARITHMETIC_OVERFLOW refusal.
struct ScalarAccumulator {
  std::int64_t sum = 0;
  std::int64_t count = 0;

  void reset() noexcept {
    sum = 0;
    count = 0;
  }

  [[nodiscard]] bool add(std::int64_t value) noexcept {
    const auto next = checked_add(sum, value);
    if (!next.has_value()) {
      return false;
    }
    sum = next.value();
    ++count;
    return true;
  }

  /// The truncating mean, or MISSING when no member was eligible.
  [[nodiscard]] Typed<std::int64_t> mean() const noexcept {
    if (count <= 0) {
      return Typed<std::int64_t>{0, Validity::MISSING};
    }
    return Typed<std::int64_t>{sum / count, Validity::VALID};
  }
};

/// A FROZEN prior: the nearest strictly-earlier eligible group's scalar mean.
/// "an absent eligible group yields missing/unresolved" — absence is `present
/// == false`, never a zero that could be differenced against.
struct PriorScalar {
  bool present = false;
  /// Frame-A nanoseconds of the group that set it.
  std::int64_t ts_ns_a = 0;
  std::int64_t mean = 0;

  [[nodiscard]] Validity validity() const noexcept {
    return present ? Validity::VALID : Validity::MISSING;
  }
};

// ---------------------------------------------------------------------------
// Stock-print price / tick-fallback prior.
// ---------------------------------------------------------------------------

/// The stock-print prior: the eligible finite mean price of the nearest
/// strictly-earlier print group. It is BOTH the return denominator and the
/// tick-fallback reference ("the sign of price minus the prior print-group
/// mean"), which is why the card names it once for two uses.
class StockPrintPrior {
 public:
  void begin_group(std::int64_t group_ts_ns_a) noexcept {
    pending_ts_ns_a_ = group_ts_ns_a;
    pending_.reset();
  }
  /// Observes ONE eligible member (condition-eligible, finite positive price).
  [[nodiscard]] bool observe_eligible_price(std::int64_t price_u6) noexcept {
    return pending_.add(price_u6);
  }
  /// "only after the whole current group is reduced does its eligible finite
  /// mean replace the prior state"; a group with no eligible member never
  /// becomes the prior.
  void commit_group() noexcept {
    const Typed<std::int64_t> mean = pending_.mean();
    if (mean.v == Validity::VALID) {
      prior_ = PriorScalar{true, pending_ts_ns_a_, mean.value};
    }
    pending_.reset();
  }
  [[nodiscard]] const PriorScalar& prior() const noexcept { return prior_; }

 private:
  PriorScalar prior_{};
  ScalarAccumulator pending_{};
  std::int64_t pending_ts_ns_a_ = 0;
};

// ---------------------------------------------------------------------------
// Stock-NBBO four-scalar prior.
// ---------------------------------------------------------------------------

/// The four separate primitive scalars of the NBBO law — bid, ask, bid size and
/// ask size — frozen together because they come from one group.
///
/// THE SCALAR-MEANS-BEFORE-DERIVED LAW LIVES IN THE ACCESSORS: `mid` and
/// `spread` are computed FROM the two price means at the moment they are asked
/// for, and no per-row midpoint is ever averaged. `imbalance` is CC-005,
/// computed from the two SIZE means. This mirrors qr_nbbo::GroupScalars exactly;
/// the difference is only that this struct carries the FROZEN copy while
/// GroupScalars carries the CURRENT group.
struct NbboScalars {
  ScalarAccumulator bid_u6;
  ScalarAccumulator ask_u6;
  ScalarAccumulator bid_shares;
  ScalarAccumulator ask_shares;

  void reset() noexcept {
    bid_u6.reset();
    ask_u6.reset();
    bid_shares.reset();
    ask_shares.reset();
  }
  [[nodiscard]] std::int64_t eligible_count() const noexcept { return bid_u6.count; }

  /// `(mean(bid) + mean(ask)) / 2` — AFTER the two scalar means.
  [[nodiscard]] Typed<std::int64_t> mid() const noexcept;
  /// `mean(ask) - mean(bid)` — same law, same order.
  [[nodiscard]] Typed<std::int64_t> spread() const noexcept;
  /// CC-005: `(mean_bid_size - mean_ask_size)/(mean_bid_size + mean_ask_size)`,
  /// zero denominator => typed missing.
  [[nodiscard]] Typed<double> imbalance() const noexcept;
};

struct NbboPrior {
  bool present = false;
  std::int64_t ts_ns_a = 0;
  NbboScalars scalars{};

  [[nodiscard]] Validity validity() const noexcept {
    return present ? Validity::VALID : Validity::MISSING;
  }
};

/// The NBBO prior machine. Same three beats; the group's four accumulators are
/// filled from ELIGIBLE members only (`qr::nbbo::classify_member` VALID).
class NbboPriorMachine {
 public:
  void begin_group(std::int64_t group_ts_ns_a) noexcept {
    pending_ts_ns_a_ = group_ts_ns_a;
    pending_.reset();
  }
  [[nodiscard]] bool observe_eligible(std::int64_t bid_u6, std::int64_t ask_u6,
                                      std::int64_t bid_shares, std::int64_t ask_shares) noexcept {
    return pending_.bid_u6.add(bid_u6) && pending_.ask_u6.add(ask_u6) &&
           pending_.bid_shares.add(bid_shares) && pending_.ask_shares.add(ask_shares);
  }
  void commit_group() noexcept {
    if (pending_.eligible_count() > 0) {
      prior_ = NbboPrior{true, pending_ts_ns_a_, pending_};
    }
    pending_.reset();
  }
  [[nodiscard]] const NbboPrior& prior() const noexcept { return prior_; }
  /// The CURRENT group's scalars, valid between `begin_group` and
  /// `commit_group` — the current-side half of the "derived only after the
  /// scalar means" law.
  [[nodiscard]] const NbboScalars& pending() const noexcept { return pending_; }

 private:
  NbboPrior prior_{};
  NbboScalars pending_{};
  std::int64_t pending_ts_ns_a_ = 0;
};

// ---------------------------------------------------------------------------
// Option-print per-contract price prior.
// ---------------------------------------------------------------------------

/// EXACT contract identity: expiry, strike and right. Not a hash, not an id —
/// "the same ... exact option contract" is these three fields.
struct ContractKey {
  std::int32_t expiration_day = 0;
  std::int64_t strike_u6 = 0;
  qr::sources::Right right = qr::sources::Right::Other;

  friend bool operator<(const ContractKey& lhs, const ContractKey& rhs) noexcept {
    if (lhs.expiration_day != rhs.expiration_day) {
      return lhs.expiration_day < rhs.expiration_day;
    }
    if (lhs.strike_u6 != rhs.strike_u6) {
      return lhs.strike_u6 < rhs.strike_u6;
    }
    return static_cast<std::uint8_t>(lhs.right) < static_cast<std::uint8_t>(rhs.right);
  }
  friend bool operator==(const ContractKey& lhs, const ContractKey& rhs) noexcept {
    return lhs.expiration_day == rhs.expiration_day && lhs.strike_u6 == rhs.strike_u6 &&
           lhs.right == rhs.right;
  }
};

/// One prior price per exact contract. `std::map` and not an unordered
/// container: iteration order is part of two-run byte identity and the CI grep
/// gate bans unordered containers on output paths.
class OptionContractPrior {
 public:
  void begin_group(std::int64_t group_ts_ns_a) noexcept {
    pending_ts_ns_a_ = group_ts_ns_a;
    pending_.clear();
  }
  /// Observes ONE eligible member of `key` (single-leg, positive size, finite
  /// positive price).
  [[nodiscard]] bool observe_eligible_price(const ContractKey& key, std::int64_t price_u6);
  void commit_group();
  /// The frozen prior of one contract, or an absent `PriorScalar`.
  [[nodiscard]] PriorScalar prior(const ContractKey& key) const;
  [[nodiscard]] std::size_t tracked_contracts() const noexcept { return prior_.size(); }

 private:
  std::map<ContractKey, PriorScalar> prior_;
  std::map<ContractKey, ScalarAccumulator> pending_;
  std::int64_t pending_ts_ns_a_ = 0;
};

// ---------------------------------------------------------------------------
// The GLOBAL underlying prior.
// ---------------------------------------------------------------------------

/// The one global underlying state, updated by the card's exact three-clause
/// rule: greatest valid attached underlying timestamp in the completed print
/// group; mean of ONLY the members sharing that timestamp; absent valid
/// attachment leaves the prior unchanged.
///
/// Order-invariant by construction: a running maximum that RESETS the
/// accumulator on a strictly greater timestamp and ADDS on an equal one gives
/// the same (max, sum, count) for every permutation of the members.
class UnderlyingPrior {
 public:
  void begin_group() noexcept {
    have_best_ = false;
    best_ts_ns_a_ = 0;
    pending_.reset();
  }
  /// Observes one member with a USABLE underlying attachment and a finite
  /// positive underlying price.
  [[nodiscard]] bool observe_valid(std::int64_t underlying_ts_ns_a,
                                   std::int64_t underlying_u6) noexcept;
  void commit_group() noexcept;
  [[nodiscard]] const PriorScalar& prior() const noexcept { return prior_; }

 private:
  PriorScalar prior_{};
  ScalarAccumulator pending_{};
  std::int64_t best_ts_ns_a_ = 0;
  bool have_best_ = false;
};

// ---------------------------------------------------------------------------
// Sequence quality.
// ---------------------------------------------------------------------------

/// One group's sequence verdict.
struct SequenceVerdict {
  /// The group carried at least one finite sequence value.
  bool group_sequence_valid = false;
  /// A strictly-earlier sequence-valid group existed, so gap/monotone/inversion
  /// are defined. This is also the "adjacent valid-group pair" the
  /// inversion-fraction denominator counts.
  bool pair_formed = false;
  std::int64_t gap = 0;
  bool monotone = false;
  bool inversion = false;
};

/// The groupwise, permutation-invariant sequence machine. There is NO
/// within-group order statistic here, by law: only min and max, both of which
/// are permutation-invariant.
class SequenceQuality {
 public:
  void begin_group() noexcept {
    have_current_ = false;
    current_min_ = 0;
    current_max_ = 0;
  }
  void observe_sequence(std::int64_t sequence) noexcept {
    if (!have_current_) {
      have_current_ = true;
      current_min_ = sequence;
      current_max_ = sequence;
      return;
    }
    if (sequence < current_min_) {
      current_min_ = sequence;
    }
    if (sequence > current_max_) {
      current_max_ = sequence;
    }
  }
  /// The verdict for the CURRENT group against the FROZEN previous one.
  [[nodiscard]] Expected<SequenceVerdict, Refusal> verdict() const noexcept;
  /// "The previous group updates only after the current group is complete."
  void commit_group() noexcept {
    if (have_current_) {
      previous_present_ = true;
      previous_max_ = current_max_;
    }
    have_current_ = false;
  }
  [[nodiscard]] bool previous_present() const noexcept { return previous_present_; }

 private:
  bool previous_present_ = false;
  std::int64_t previous_max_ = 0;
  bool have_current_ = false;
  std::int64_t current_min_ = 0;
  std::int64_t current_max_ = 0;
};

// ---------------------------------------------------------------------------
// Group interarrival.
// ---------------------------------------------------------------------------

/// "Group interarrival is present only from the second timestamp group onward."
class GroupInterarrival {
 public:
  /// The gap in checked integer microseconds from the previous group, or an
  /// absent optional at the first group of the stream.
  [[nodiscard]] Expected<std::optional<std::int64_t>, Refusal> micros_before(
      std::int64_t group_ts_ns_a) const noexcept;
  void commit_group(std::int64_t group_ts_ns_a) noexcept {
    previous_present_ = true;
    previous_ts_ns_a_ = group_ts_ns_a;
  }
  [[nodiscard]] bool previous_present() const noexcept { return previous_present_; }
  [[nodiscard]] std::int64_t previous_ts_ns_a() const noexcept { return previous_ts_ns_a_; }

 private:
  bool previous_present_ = false;
  std::int64_t previous_ts_ns_a_ = 0;
};

}  // namespace qr::carriers

#endif  // QR_CARRIERS_PRIOR_STATE_HPP
