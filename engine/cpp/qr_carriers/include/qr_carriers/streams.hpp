// qr_carriers/streams.hpp — THE THREE PER-MODALITY CHANNEL CONSTRUCTORS.
//
// SPEC: evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 4 — the
// three channel lists (quoted in full in channels.hpp), the attachment and
// signing law (quoted in attach.hpp), the prior-state law and the sequence law
// (quoted in prior_state.hpp), the causal-aggressor recompute, the directional
// eligibility contracts, and the orientation law.
//
// ONE PASS, ONE TOKEN AT A TIME, AGAINST A FROZEN PRIOR. Each builder consumes
// a session's equal-timestamp groups in causal order. Within a group every
// token is built against the SAME frozen prior; the prior machines commit only
// after the whole group is reduced. That is the card's law and it is also why
// there is no way to express the M702-shaped defect here: `commit_group` is a
// separate call that happens after the member loop has ended.
//
// PERMUTATION INVARIANCE IS STRUCTURAL, IN TWO LAYERS.
//   1. Every prior update is an exact integer sum/count, a running maximum, or
//      a min/max — all order-invariant (prior_state.hpp).
//   2. The group's four MECHANISM means are floating-point sums, and
//      floating-point addition is NOT associative, so the builders canonically
//      order a group's members (qr::sources::canonical_less, the same total
//      order WP4's GroupTape uses) BEFORE reducing. The reduction is then
//      bit-identical for every permutation of the input rows, which is exactly
//      what the equal-ms production-constructor control requires ("requires
//      every output bit and all later prior states to remain identical"). A
//      builder that leaned on the reader having already canonicalized would
//      pass the real-file check and fail the control.
//
// SIDE IS AN INPUT, NOT A POST-PROCESS. Each token is CONSTRUCTED once per
// side, through the same function, so the reflection control compares two
// independently built rows rather than a row and its own negation.
//
// WHY NBBO CHANNELS ARE GROUP-LEVEL AND PRINT CHANNELS ARE TOKEN-LEVEL. Every
// one of the sixteen NBBO channels is defined on quantities the card derives
// from the group's SEPARATE SCALAR MEANS ("NBBO prior/current midpoint and
// imbalance are derived only **after** those scalar means, never by averaging
// per-row midpoint or imbalance"), so an NBBO token's channel vector IS its
// group's channel vector, broadcast to its members; the equal-time mean+max
// reduction of a constant is that constant. Building NBBO channels per row and
// averaging them afterwards is the named mutant, not an implementation choice.
#ifndef QR_CARRIERS_STREAMS_HPP
#define QR_CARRIERS_STREAMS_HPP

#include <array>
#include <cstdint>
#include <optional>
#include <span>
#include <vector>

#include "qr_carriers/attach.hpp"
#include "qr_carriers/channels.hpp"
#include "qr_carriers/prior_state.hpp"
#include "qr_clock/session_clock.hpp"
#include "qr_core/refusal.hpp"
#include "qr_sources/option_prints.hpp"
#include "qr_sources/stock_quotes.hpp"
#include "qr_sources/stock_trades.hpp"

namespace qr::carriers {

/// How many preregistered mechanism channels each modality declares (section 4:
/// "mean/last of the four preregistered mechanism channels").
inline constexpr std::size_t kMechanismCount = 4;

/// The mechanism channel indices, per modality, exactly as section 4 names them:
///   stock print: return/aggressor/signed-size/imbalance;
///   NBBO:        mid-change/spread/imbalance/own-size-change;
///   option:      underlying-return/aggressor/premium-flow/delta-flow.
inline constexpr std::array<std::size_t, kMechanismCount> kStockPrintMechanisms{
    kSpOrientedPrintReturn, kSpOrientedAggressor, kSpOrientedSignedSize, kSpOrientedSizeImbalance};
inline constexpr std::array<std::size_t, kMechanismCount> kNbboMechanisms{
    kNbOrientedMidpointChange, kNbSpreadBps, kNbOrientedImbalance, kNbOwnSignedSizeChange};
inline constexpr std::array<std::size_t, kMechanismCount> kOptionPrintMechanisms{
    kOpOrientedUnderlyingReturn, kOpOrientedCausalAggressor, kOpOrientedSignedPremiumFlow,
    kOpOrientedDeltaFlow};

[[nodiscard]] std::span<const std::size_t> mechanism_channels(Modality modality) noexcept;

// ---------------------------------------------------------------------------
// The reduced group record — everything DIRECT_RAW reads.
// ---------------------------------------------------------------------------

/// One reduced equal-timestamp group of one modality.
///
/// The four mechanism values are held for BOTH sides because a session is
/// streamed once and serves LONG and SHORT decisions; nothing else in the
/// record is side-dependent (masks, counts and quality are invariant under
/// reflection, by the card's own reflection sentence).
struct GroupRecord {
  /// Frame-A nanoseconds — converted ONCE, by qr_clock, at group admission.
  std::int64_t ts_ns_a = 0;
  /// Members of the equal-timestamp group (the modality's TOKEN count).
  std::int32_t token_count = 0;
  /// Absent value cells summed over this group's tokens: the numerator of the
  /// raw-missing fraction.
  std::int32_t absent_value_cells = 0;
  /// Tokens whose union attachment indicator fired — ONE per token, never one
  /// per failed dependency.
  std::int32_t unusable_attachment_tokens = 0;
  /// The group carried at least one finite vendor sequence.
  bool sequence_group_valid = false;
  /// An adjacent valid-group pair was formed (the inversion denominator).
  bool sequence_pair = false;
  bool sequence_inversion = false;
  /// `log1p(token_count)` — the card's "group multiplicity", transformed once
  /// at construction so the DIRECT layer never calls log1p inside a per-decision
  /// loop (the plan's performance-budget rule: arithmetic before clarity claims).
  double log1p_multiplicity = 0.0;
  /// `log1p(microseconds since the previous group)`, absent at the stream's
  /// first group. The DIRECT intergroup-gap statistics read exactly these.
  double log1p_gap_micros = 0.0;
  bool has_gap = false;

  std::array<double, kMechanismCount> mechanism_long{};
  std::array<double, kMechanismCount> mechanism_short{};
  /// Bit `k` set == mechanism `k` is PRESENT for that side.
  std::uint8_t mechanism_present_long = 0;
  std::uint8_t mechanism_present_short = 0;

  [[nodiscard]] Typed<double> mechanism(Side side, std::size_t index) const noexcept {
    const unsigned mask =
        static_cast<unsigned>(side == Side::LONG ? mechanism_present_long : mechanism_present_short);
    const bool present_bit = ((mask >> static_cast<unsigned>(index)) & 1U) != 0U;
    const double value = side == Side::LONG ? mechanism_long[index] : mechanism_short[index];
    return Typed<double>{present_bit ? value : 0.0,
                         present_bit ? Validity::VALID : Validity::MISSING};
  }
  /// "all-four-mechanisms-finite group fraction" / the window valid fraction's
  /// numerator / `r_modality`'s numerator — one predicate, used by all three.
  [[nodiscard]] bool all_four_present(Side side) const noexcept {
    const std::uint8_t mask = side == Side::LONG ? mechanism_present_long : mechanism_present_short;
    return mask == 0x0FU;
  }
  void set_mechanism(Side side, std::size_t index, Typed<double> value) noexcept;
};

// ---------------------------------------------------------------------------
// Per-token constructor inputs (pure functions, so a fixture can hand-build
// every dependency and assert a hand-computed literal).
// ---------------------------------------------------------------------------

/// Group-level facts shared by every token of a group.
struct GroupContext {
  std::int64_t ts_ns_a = 0;
  /// Checked integer microseconds since the previous group, absent at the first
  /// group of the stream.
  std::optional<std::int64_t> interarrival_micros;
  /// "`same-ms=1` exactly when the complete Frame-A timestamp group has
  /// multiplicity>1".
  bool same_ms = false;
  SequenceVerdict sequence{};
};

struct StockPrintTokenInputs {
  const qr::sources::StockTradeRow* row = nullptr;
  GroupContext group{};
  StockPrintEligibility eligibility{};
  /// The classified attached-quote clock and the attached quote's signing
  /// verdict — two separate laws, kept separate.
  Attachment quote_attachment{};
  Validity quote_signing = Validity::MISSING;
  /// The FROZEN nearest strictly-earlier eligible print-group mean price.
  PriorScalar price_prior{};
};

struct NbboGroupInputs {
  GroupContext group{};
  /// The CURRENT group's four separate scalar means.
  const NbboScalars* current = nullptr;
  /// The FROZEN nearest strictly-earlier eligible group.
  const NbboPrior* prior = nullptr;
  bool any_locked = false;
  bool any_crossed = false;
  bool any_positive_two_sided = false;
};

struct OptionPrintTokenInputs {
  const qr::sources::OptionPrintRow* row = nullptr;
  GroupContext group{};
  /// Base directional eligibility: "positive size, pinned single-leg condition
  /// in {18,95,125,126}".
  bool directional_eligible = false;
  Validity directional_validity = Validity::CONDITION_INELIGIBLE;
  Attachment quote_attachment{};
  Validity quote_signing = Validity::MISSING;
  /// The underlying attachment CLOCK verdict and the underlying VALUE in u6.
  Attachment underlying_attachment{};
  std::optional<std::int64_t> underlying_u6;
  /// Nonzero-length only when the underlying cell was a non-finite or
  /// unrepresentable double.
  bool underlying_value_finite = true;
  /// The FROZEN same-contract prior print mean, and the global underlying prior.
  PriorScalar contract_prior{};
  PriorScalar underlying_prior{};
  /// Calendar days to expiry, from the session's own civil day.
  std::int64_t dte_days = 0;
  bool dte_present = false;
};

/// One token's channels plus the two audit facts DIRECT needs from it.
template <std::size_t N>
struct TokenResult {
  ChannelRow<N> channels;
  /// The ONE union attachment indicator of this token.
  bool unusable_attachment = false;
};

using StockPrintTokenResult = TokenResult<kStockPrintChannelCount>;
using NbboTokenResult = TokenResult<kNbboChannelCount>;
using OptionPrintTokenResult = TokenResult<kOptionPrintChannelCount>;

/// THE THREE CONSTRUCTORS. Pure: same inputs, same bytes, no hidden state.
[[nodiscard]] Expected<StockPrintTokenResult, Refusal> build_stock_print_token(
    const StockPrintTokenInputs& inputs, Side side);
[[nodiscard]] Expected<NbboTokenResult, Refusal> build_nbbo_group_token(
    const NbboGroupInputs& inputs, Side side);
[[nodiscard]] Expected<OptionPrintTokenResult, Refusal> build_option_print_token(
    const OptionPrintTokenInputs& inputs, Side side);

// ---------------------------------------------------------------------------
// The three session builders.
// ---------------------------------------------------------------------------

/// The stock-print session builder.
class StockPrintStream {
 public:
  explicit StockPrintStream(SessionClock clock) : clock_(std::move(clock)) {}

  /// Reduces ONE complete equal-timestamp group, in causal order.
  [[nodiscard]] Expected<std::size_t, Refusal> push_group(
      std::int64_t ts_ms_b, std::span<const qr::sources::StockTradeRow> rows);

  [[nodiscard]] const std::vector<GroupRecord>& groups() const noexcept { return groups_; }
  [[nodiscard]] const StockPrintCensus& census() const noexcept { return census_; }
  [[nodiscard]] const StockQualityLedger& quality() const noexcept { return quality_; }
  /// Per-attachment-state histogram over prints (printed in full by the probe).
  [[nodiscard]] const std::array<std::int64_t, kAttachStateCount>& attach_states() const noexcept {
    return attach_states_;
  }
  [[nodiscard]] const StockPrintPrior& prior() const noexcept { return prior_; }
  /// The size-weighted prefix VWAP accumulators (section 5 location law): only
  /// prints that pass the frozen condition/size/price contract enter. Kept as
  /// EXACT integer running sums so the location layer's VWAP is a checked
  /// truncating division and not a floating-point running average.
  [[nodiscard]] std::int64_t vwap_size_sum() const noexcept { return vwap_size_sum_; }
  [[nodiscard]] std::int64_t vwap_notional_sum() const noexcept { return vwap_notional_sum_; }
  /// The same two sums AFTER each group, aligned one-for-one with `groups()`,
  /// so a decision's PREFIX vwap (strictly before its cutoff) is a lookup rather
  /// than a rescan. Section 5: "VWAP is size-weighted IWM stock prints strictly
  /// before cutoff that pass the frozen stock condition/size/price contract."
  [[nodiscard]] const std::vector<std::int64_t>& vwap_notional_prefix() const noexcept {
    return vwap_notional_prefix_;
  }
  [[nodiscard]] const std::vector<std::int64_t>& vwap_size_prefix() const noexcept {
    return vwap_size_prefix_;
  }

 private:
  SessionClock clock_;
  std::vector<GroupRecord> groups_;
  StockPrintCensus census_;
  StockQualityLedger quality_;
  std::array<std::int64_t, kAttachStateCount> attach_states_{};
  StockPrintPrior prior_;
  SequenceQuality sequence_;
  GroupInterarrival interarrival_;
  std::vector<qr::sources::StockTradeRow> canonical_;
  std::int64_t vwap_size_sum_ = 0;
  std::int64_t vwap_notional_sum_ = 0;
  std::vector<std::int64_t> vwap_notional_prefix_;
  std::vector<std::int64_t> vwap_size_prefix_;
};

/// The NBBO session builder.
class NbboStream {
 public:
  explicit NbboStream(SessionClock clock) : clock_(std::move(clock)) {}

  [[nodiscard]] Expected<std::size_t, Refusal> push_group(
      std::int64_t ts_ms_b, std::span<const qr::sources::StockQuoteRow> rows);

  [[nodiscard]] const std::vector<GroupRecord>& groups() const noexcept { return groups_; }
  [[nodiscard]] const NbboCensus& census() const noexcept { return census_; }
  [[nodiscard]] const NbboPriorMachine& prior_machine() const noexcept { return prior_; }
  /// Every group that had an ELIGIBLE member, as (frame-A ns, midpoint u6,
  /// spread u6): the one prefix series the 1s grid and the location values read.
  struct EligibleMid {
    std::int64_t ts_ns_a = 0;
    std::int64_t mid_u6 = 0;
    std::int64_t spread_u6 = 0;
  };
  [[nodiscard]] const std::vector<EligibleMid>& eligible_midpoints() const noexcept {
    return eligible_midpoints_;
  }

 private:
  SessionClock clock_;
  std::vector<GroupRecord> groups_;
  NbboCensus census_;
  NbboPriorMachine prior_;
  GroupInterarrival interarrival_;
  std::vector<EligibleMid> eligible_midpoints_;
};

/// The option-print session builder.
class OptionPrintStream {
 public:
  explicit OptionPrintStream(SessionClock clock) : clock_(std::move(clock)) {}

  [[nodiscard]] Expected<std::size_t, Refusal> push_group(
      std::int64_t ts_ms_b, std::span<const qr::sources::OptionPrintRow> rows);

  [[nodiscard]] const std::vector<GroupRecord>& groups() const noexcept { return groups_; }
  [[nodiscard]] const OptionPrintCensus& census() const noexcept { return census_; }
  [[nodiscard]] const std::array<std::int64_t, kAttachStateCount>& quote_attach_states()
      const noexcept {
    return quote_attach_states_;
  }
  [[nodiscard]] const std::array<std::int64_t, kAttachStateCount>& underlying_attach_states()
      const noexcept {
    return underlying_attach_states_;
  }
  [[nodiscard]] const UnderlyingPrior& underlying_prior() const noexcept {
    return underlying_prior_;
  }
  [[nodiscard]] const OptionContractPrior& contract_prior() const noexcept {
    return contract_prior_;
  }
  [[nodiscard]] const std::vector<std::int64_t>& last_print_ts_ns() const noexcept {
    return last_print_ts_ns_;
  }
  [[nodiscard]] std::int64_t directional_eligible_prints() const noexcept {
    return directional_eligible_prints_;
  }

 private:
  SessionClock clock_;
  std::vector<GroupRecord> groups_;
  OptionPrintCensus census_;
  std::array<std::int64_t, kAttachStateCount> quote_attach_states_{};
  std::array<std::int64_t, kAttachStateCount> underlying_attach_states_{};
  OptionContractPrior contract_prior_;
  UnderlyingPrior underlying_prior_;
  SequenceQuality sequence_;
  GroupInterarrival interarrival_;
  std::vector<qr::sources::OptionPrintRow> canonical_;
  std::vector<std::int64_t> last_print_ts_ns_;
  std::int64_t directional_eligible_prints_ = 0;
};

}  // namespace qr::carriers

#endif  // QR_CARRIERS_STREAMS_HPP
