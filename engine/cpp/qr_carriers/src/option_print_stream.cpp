// qr_carriers/src/option_print_stream.cpp — the 22 option-print channels and
// the option-print session pass.
//
// SPEC (task card V4 section 4, the clauses this file is):
//
//   "Quote-dependent option fields (attached bid/ask/sizes, print-minus-mid,
//    spread, quote age) require a strict-prior quote. Underlying-dependent
//    fields (underlying return/age and moneyness) require a strict-prior
//    underlying observation. IV, delta/gamma/vanna/charm, and every derived
//    Greek-flow value require **both** strict-prior attachments; any equal,
//    future, or missing dependency masks the value and its flow. DTE/right/
//    print price/size remain print-native. A causal option aggressor is
//    recomputed per contract: with a valid strict-prior quote, print>=ask is +1
//    and print<=bid is -1; otherwise use the sign of this print price minus the
//    prior strictly-earlier same-contract print (0 on tie/missing). The quote
//    branch is skipped, not imputed, when its attachment is unavailable.
//    Derived flow is `causal_aggressor * size * greek`; no persisted side or
//    FlowBlock value participates. Each option print uses only its own
//    strict-prior attached underlying value for its current underlying/
//    moneyness/Greek inputs."
//
//   "Causal aggressor and signed-premium flow require positive size, pinned
//    single-leg condition in `{18,95,125,126}`, and either a strict-prior quote
//    or a strict-prior same-contract print. Greek-flow additionally requires
//    both strict-prior quote and underlying dependencies as above. Multileg,
//    unknown, and nonpositive-size prints are retained with exact typed reason
//    and `directional_eligible=0` ... Each directional value's presence is the
//    conjunction of base directional eligibility and its declared dependency
//    mask. No sign is guessed."
//
// THE TWO ATTACHMENT VERDICTS ARE THREE FACTS, NOT ONE. A print's quote
// attachment has a CLOCK verdict (strict-prior / equal / future / missing /
// wrong day / malformed) and a SIGNING verdict (finite, bid>0, ask>0, ask>bid);
// its underlying attachment has a clock verdict and a VALUE verdict (finite and
// positive). The card assigns different subsets to different channels — quote
// age needs only the quote clock, spread needs the quote clock AND signing, the
// Greeks need both clocks — so this file keeps the three apart and never
// collapses them into one "attachment ok" boolean.
#include <algorithm>
#include <utility>

#include <cmath>

#include "qr_carriers/streams.hpp"
#include "stream_common.hpp"

namespace qr::carriers {

using detail_streams::both;
using detail_streams::cell;
using detail_streams::oriented;
using detail_streams::sign_of_difference;

namespace {

/// The attached option quote, as the signing law reads it. B3 projects NO
/// option quote conditions, so "every AVAILABLE bid/ask condition passes its
/// pinned condition contract" is satisfied by an absent condition rather than
/// by an invented code-0 default.
[[nodiscard]] QuoteFields attached_quote(const qr::sources::OptionPrintRow& row) noexcept {
  using namespace qr::sources;
  QuoteFields quote;
  quote.bid_u6 = cell(row.is_null(kPrintSlotBid), row.bid_u6);
  quote.ask_u6 = cell(row.is_null(kPrintSlotAsk), row.ask_u6);
  quote.bid_size = cell(row.is_null(kPrintSlotBidSize), row.bid_size);
  quote.ask_size = cell(row.is_null(kPrintSlotAskSize), row.ask_size);
  return quote;
}

/// One raw Greek cell: absent column -> MISSING, non-finite value -> NONFINITE,
/// otherwise the raw dimensionless value (transform-table row 6).
[[nodiscard]] Typed<double> greek_cell(const qr::sources::OptionPrintRow& row, std::size_t slot,
                                       double value) noexcept {
  if (row.is_null(slot)) {
    return masked(Validity::MISSING);
  }
  return raw_dimensionless(value);
}

}  // namespace

Expected<OptionPrintTokenResult, Refusal> build_option_print_token(
    const OptionPrintTokenInputs& inputs, Side side) {
  using namespace qr::sources;
  if (inputs.row == nullptr) {
    detail::fail_fast("qr::carriers::build_option_print_token: null row");
  }
  const OptionPrintRow& row = *inputs.row;
  const double sigma = sigma_of(side);
  const bool rho_defined = rho_is_defined(row.right);
  const double sigma_rho = rho_defined ? sigma * rho_of(row.right) : 0.0;
  const QuoteFields quote = attached_quote(row);

  OptionPrintTokenResult out;
  ChannelRow<kOptionPrintChannelCount>& channels = out.channels;

  // --- the three attachment facts -----------------------------------------------
  const bool quote_clock_ok = inputs.quote_attachment.usable();
  const bool quote_signing_ok = inputs.quote_signing == Validity::VALID;
  const bool quote_usable = quote_clock_ok && quote_signing_ok;
  const Validity quote_dependency = both(inputs.quote_attachment.validity(), inputs.quote_signing);

  const bool underlying_clock_ok = inputs.underlying_attachment.usable();
  const bool underlying_value_ok =
      inputs.underlying_u6.has_value() && inputs.underlying_value_finite && *inputs.underlying_u6 > 0;
  const bool underlying_usable = underlying_clock_ok && underlying_value_ok;
  Validity underlying_dependency = inputs.underlying_attachment.validity();
  if (underlying_clock_ok && !underlying_value_ok) {
    underlying_dependency = inputs.underlying_u6.has_value()
                                ? (inputs.underlying_value_finite ? Validity::NONPOSITIVE
                                                                  : Validity::NONFINITE)
                                : Validity::MISSING;
  }
  // "IV, delta/gamma/vanna/charm, and every derived Greek-flow value require
  // **both** strict-prior attachments".
  const Validity greek_dependency =
      both(inputs.quote_attachment.validity(), underlying_dependency);
  const bool greeks_ok = quote_clock_ok && underlying_usable;

  // ONE union indicator per print over every dependency it requires — never one
  // per failed reason. Two simultaneous failures are still one unusable print.
  out.unusable_attachment = !(quote_usable && underlying_usable);

  const Validity directional = inputs.directional_validity;
  const bool directional_ok = inputs.directional_eligible;
  const bool price_present = !row.is_null(kPrintSlotPrice) && row.price_u6 > 0;
  const bool size_present = !row.is_null(kPrintSlotSize);

  // --- 0. log interarrival --------------------------------------------------------
  channels.set(kOpLogInterarrival, inputs.group.interarrival_micros.has_value()
                                       ? time_log1p_micros(*inputs.group.interarrival_micros)
                                       : masked(Validity::MISSING));

  // --- 1. oriented underlying return (a STOCK return: sigma only) -----------------
  if (!underlying_usable || !inputs.underlying_prior.present) {
    channels.set(kOpOrientedUnderlyingReturn,
                 masked(both(underlying_dependency, inputs.underlying_prior.validity())));
  } else {
    const auto bps = displacement_bps_value(*inputs.underlying_u6 - inputs.underlying_prior.mean,
                                            inputs.underlying_prior.mean);
    if (!bps.has_value()) {
      return Expected<OptionPrintTokenResult, Refusal>::refuse(bps.error());
    }
    channels.set(kOpOrientedUnderlyingReturn, oriented(bps.value(), sigma));
  }

  // --- 2. oriented right direction = sigma*rho ------------------------------------
  channels.set(kOpOrientedRightDirection,
               rho_defined ? present(sigma_rho) : masked(Validity::MISSING));

  // --- 3. oriented causal aggressor = sigma*rho*v ---------------------------------
  int aggressor = 0;
  bool aggressor_resolved = false;
  if (directional_ok && price_present) {
    if (quote_usable && row.price_u6 >= *quote.ask_u6) {
      aggressor = 1;
      aggressor_resolved = true;
    } else if (quote_usable && row.price_u6 <= *quote.bid_u6) {
      aggressor = -1;
      aggressor_resolved = true;
    } else if (inputs.contract_prior.present) {
      aggressor = sign_of_difference(row.price_u6, inputs.contract_prior.mean);
      aggressor_resolved = true;
    } else if (quote_usable) {
      // Strictly inside a valid spread with no prior same-contract print: the
      // reference exists and says neither buy nor sell — a resolved tie.
      aggressor = 0;
      aggressor_resolved = true;
    }
  }
  {
    const bool ok = aggressor_resolved && rho_defined;
    channels.set(kOpOrientedCausalAggressor,
                 ok ? oriented(present(static_cast<double>(aggressor)), sigma_rho)
                    : masked(directional_ok ? Validity::MISSING : directional));
  }

  // --- 4. log size (a RAW COUNT: it survives a multileg condition) -----------------
  channels.set(kOpLogSize, size_present ? count_log1p(row.size) : masked(Validity::MISSING));

  // --- 5. oriented signed premium flow = sigma*rho*v*size*price_u6 -----------------
  if (!aggressor_resolved || !rho_defined || !size_present || !price_present) {
    channels.set(kOpOrientedSignedPremiumFlow,
                 masked(directional_ok ? Validity::MISSING : directional));
  } else {
    const auto contracts = checked_mul(static_cast<std::int64_t>(aggressor), row.size);
    if (!contracts.has_value()) {
      return Expected<OptionPrintTokenResult, Refusal>::refuse(contracts.error());
    }
    const auto premium = checked_mul(contracts.value(), row.price_u6);
    if (!premium.has_value()) {
      return Expected<OptionPrintTokenResult, Refusal>::refuse(premium.error());
    }
    channels.set(kOpOrientedSignedPremiumFlow,
                 oriented(signed_log1p_int(premium.value()), sigma_rho));
  }

  // --- 6/7. oriented print-minus-mid and spread bps --------------------------------
  std::optional<std::int64_t> attached_mid;
  if (quote_usable) {
    attached_mid = midpoint_u6(*quote.bid_u6, *quote.ask_u6);
  }
  if (!quote_usable || !price_present || !rho_defined) {
    channels.set(kOpOrientedPrintMinusMid,
                 masked(quote_usable ? Validity::MISSING : quote_dependency));
  } else {
    const auto bps = displacement_bps_value(row.price_u6 - *attached_mid, *attached_mid);
    if (!bps.has_value()) {
      return Expected<OptionPrintTokenResult, Refusal>::refuse(bps.error());
    }
    channels.set(kOpOrientedPrintMinusMid, oriented(bps.value(), sigma_rho));
  }
  if (!quote_usable) {
    channels.set(kOpSpreadBps, masked(quote_dependency));
  } else {
    const auto bps = displacement_bps_value(*quote.ask_u6 - *quote.bid_u6, *attached_mid);
    if (!bps.has_value()) {
      return Expected<OptionPrintTokenResult, Refusal>::refuse(bps.error());
    }
    channels.set(kOpSpreadBps, bps.value());
  }

  // --- 8..12. the Greeks and IV: BOTH strict-prior attachments ---------------------
  const Typed<double> delta =
      greeks_ok ? greek_cell(row, kPrintSlotDelta, row.delta) : masked(greek_dependency);
  const Typed<double> gamma =
      greeks_ok ? greek_cell(row, kPrintSlotGamma, row.gamma) : masked(greek_dependency);
  const Typed<double> vanna =
      greeks_ok ? greek_cell(row, kPrintSlotVanna, row.vanna) : masked(greek_dependency);
  const Typed<double> charm =
      greeks_ok ? greek_cell(row, kPrintSlotCharm, row.charm) : masked(greek_dependency);
  const Typed<double> implied_vol =
      greeks_ok ? greek_cell(row, kPrintSlotImpliedVol, row.implied_vol)
                : masked(greek_dependency);
  channels.set(kOpOrientedDelta, oriented(delta, sigma));
  channels.set(kOpGamma, gamma);  // side-invariant, by name
  channels.set(kOpOrientedVanna, oriented(vanna, sigma));
  channels.set(kOpOrientedCharm, oriented(charm, sigma));
  channels.set(kOpImpliedVol, implied_vol);

  // --- 13. log DTE (print-native) ---------------------------------------------------
  channels.set(kOpLogDte,
               inputs.dte_present ? dte_log1p_days(inputs.dte_days) : masked(Validity::MISSING));

  // --- 14. oriented moneyness = sigma*rho*(underlying_u6-strike_u6)/strike_u6 -------
  if (!underlying_usable || !rho_defined || row.is_null(kPrintSlotStrike) || row.strike_u6 <= 0) {
    channels.set(kOpOrientedMoneyness,
                 masked(underlying_usable ? Validity::MISSING : underlying_dependency));
  } else {
    const auto bps =
        displacement_bps_value(*inputs.underlying_u6 - row.strike_u6, row.strike_u6);
    if (!bps.has_value()) {
      return Expected<OptionPrintTokenResult, Refusal>::refuse(bps.error());
    }
    channels.set(kOpOrientedMoneyness, oriented(bps.value(), sigma_rho));
  }

  // --- 15..18. the recomputed Greek flows: v * size * greek --------------------------
  {
    const std::array<std::pair<std::size_t, Typed<double>>, 4> flows{
        std::make_pair(static_cast<std::size_t>(kOpOrientedDeltaFlow), delta),
        std::make_pair(static_cast<std::size_t>(kOpGammaFlow), gamma),
        std::make_pair(static_cast<std::size_t>(kOpOrientedVannaFlow), vanna),
        std::make_pair(static_cast<std::size_t>(kOpOrientedCharmFlow), charm)};
    for (const auto& entry : flows) {
      // Gamma flow is side-invariant exactly as gamma is; the other three carry
      // sigma because their Greek is "already signed".
      const double factor = entry.first == static_cast<std::size_t>(kOpGammaFlow) ? 1.0 : sigma;
      if (!aggressor_resolved || !size_present || entry.second.v != Validity::VALID) {
        channels.set(entry.first,
                     masked(entry.second.v != Validity::VALID
                                ? entry.second.v
                                : (directional_ok ? Validity::MISSING : directional)));
        continue;
      }
      const double flow =
          static_cast<double>(aggressor) * static_cast<double>(row.size) * entry.second.value;
      channels.set(entry.first, oriented(signed_log1p(flow), factor));
    }
  }

  // --- 19/20. the two attachment ages (CLOCK verdicts alone) --------------------------
  if (!quote_clock_ok) {
    channels.set(kOpLogQuoteAge, masked(inputs.quote_attachment.validity()));
  } else {
    const auto micros = duration_micros(inputs.quote_attachment.ts_ns_a, inputs.group.ts_ns_a);
    if (!micros.has_value()) {
      return Expected<OptionPrintTokenResult, Refusal>::refuse(micros.error());
    }
    channels.set(kOpLogQuoteAge, time_log1p_micros(micros.value()));
  }
  if (!underlying_clock_ok) {
    channels.set(kOpLogUnderlyingAge, masked(inputs.underlying_attachment.validity()));
  } else {
    const auto micros =
        duration_micros(inputs.underlying_attachment.ts_ns_a, inputs.group.ts_ns_a);
    if (!micros.has_value()) {
      return Expected<OptionPrintTokenResult, Refusal>::refuse(micros.error());
    }
    channels.set(kOpLogUnderlyingAge, time_log1p_micros(micros.value()));
  }

  // --- 21. the directional-eligible quality bit ----------------------------------------
  channels.set(kOpDirectionalEligible, structural_bit(directional_ok));
  return out;
}

// ---------------------------------------------------------------------------
// The session pass.
// ---------------------------------------------------------------------------

namespace {

/// Base directional eligibility for an option print: "positive size, pinned
/// single-leg condition in {18,95,125,126}". The typed reason is worst-wins over
/// the two clauses so a masked directional channel says WHICH one failed.
struct OptionEligibility {
  bool eligible = false;
  Validity validity = Validity::CONDITION_INELIGIBLE;
};

[[nodiscard]] OptionEligibility classify_option_print(
    const qr::sources::OptionPrintRow& row) noexcept {
  using namespace qr::sources;
  OptionEligibility out;
  Validity verdict = Validity::VALID;
  if (row.is_null(kPrintSlotSize)) {
    verdict = combine(verdict, Validity::MISSING);
  } else if (row.size <= 0) {
    verdict = combine(verdict, Validity::NONPOSITIVE);
  }
  if (row.is_null(kPrintSlotCondition)) {
    verdict = combine(verdict, Validity::MISSING);
  } else if (!is_single_leg_print_condition(row.condition)) {
    verdict = combine(verdict, Validity::CONDITION_INELIGIBLE);
  }
  out.validity = verdict;
  out.eligible = verdict == Validity::VALID;
  return out;
}

}  // namespace

Expected<std::size_t, Refusal> OptionPrintStream::push_group(
    std::int64_t ts_ms_b, std::span<const qr::sources::OptionPrintRow> rows) {
  using namespace qr::sources;
  const auto ts_a = clock_.to_frame_a(FrameB{ts_ms_b * kNanosecondsPerMillisecond});
  if (!ts_a.has_value()) {
    return Expected<std::size_t, Refusal>::refuse(ts_a.error());
  }
  const std::int64_t group_ts_ns_a = ts_a.value().ns();

  // Canonical member order BEFORE any floating-point reduction.
  canonical_.assign(rows.begin(), rows.end());
  if (canonical_.size() > 1) {
    std::sort(canonical_.begin(), canonical_.end(),
              [](const OptionPrintRow& left, const OptionPrintRow& right) {
                return canonical_less(left, right);
              });
  }

  GroupContext context;
  context.ts_ns_a = group_ts_ns_a;
  const auto gap = interarrival_.micros_before(group_ts_ns_a);
  if (!gap.has_value()) {
    return Expected<std::size_t, Refusal>::refuse(gap.error());
  }
  context.interarrival_micros = gap.value();
  context.same_ms = canonical_.size() > 1;

  sequence_.begin_group();
  for (const OptionPrintRow& row : canonical_) {
    if (!row.is_null(kPrintSlotSequence)) {
      sequence_.observe_sequence(row.sequence);
    }
  }
  const auto verdict = sequence_.verdict();
  if (!verdict.has_value()) {
    return Expected<std::size_t, Refusal>::refuse(verdict.error());
  }
  context.sequence = verdict.value();

  GroupRecord record;
  record.ts_ns_a = group_ts_ns_a;
  record.token_count = static_cast<std::int32_t>(canonical_.size());
  record.sequence_group_valid = context.sequence.group_sequence_valid;
  record.sequence_pair = context.sequence.pair_formed;
  record.sequence_inversion = context.sequence.inversion;
  // The two per-group scalars the DIRECT layer reads without recomputing a
  // transcendental inside a per-decision loop.
  record.log1p_multiplicity =
      std::log1p(static_cast<double>(record.token_count));
  if (context.interarrival_micros.has_value()) {
    record.has_gap = true;
    const Typed<double> gap_value = time_log1p_micros(*context.interarrival_micros);
    record.log1p_gap_micros = gap_value.v == Validity::VALID ? gap_value.value : 0.0;
    record.has_gap = gap_value.v == Validity::VALID;
  }

  std::array<double, kMechanismCount> sum_long{};
  std::array<double, kMechanismCount> sum_short{};
  std::array<std::int64_t, kMechanismCount> count_long{};
  std::array<std::int64_t, kMechanismCount> count_short{};

  contract_prior_.begin_group(group_ts_ns_a);
  underlying_prior_.begin_group();
  const std::int64_t session_day = clock_.civil_date().days_since_epoch();

  for (const OptionPrintRow& row : canonical_) {
    const OptionEligibility eligibility = classify_option_print(row);
    const bool contract_keyed = !row.is_null(kPrintSlotExpiration) &&
                                !row.is_null(kPrintSlotStrike) && !row.is_null(kPrintSlotRight);
    const ContractKey key{row.expiration_day, row.strike_u6, row.right};

    OptionPrintTokenInputs inputs;
    inputs.row = &row;
    inputs.group = context;
    inputs.directional_eligible = eligibility.eligible;
    inputs.directional_validity = eligibility.validity;
    inputs.quote_attachment = classify_attachment_ms(
        clock_, cell(row.is_null(kPrintSlotQuoteTimestamp), row.quote_ts_ms_b), group_ts_ns_a);
    inputs.quote_signing = quote_signing_validity(attached_quote(row));

    // The underlying attachment: the text parse is THIS module's (WP4 ruling),
    // and it goes through qr_clock like every other frame-B stamp.
    const std::optional<std::string_view> underlying_text =
        row.is_null(kPrintSlotUnderlyingTimestamp)
            ? std::optional<std::string_view>{}
            : std::optional<std::string_view>{row.underlying_ts_text.view()};
    inputs.underlying_attachment =
        classify_attachment_text(clock_, underlying_text, group_ts_ns_a);
    if (!row.is_null(kPrintSlotUnderlyingPrice)) {
      const auto underlying_u6 = dollars_to_u6(row.underlying_price);
      if (underlying_u6.has_value()) {
        inputs.underlying_u6 = underlying_u6.value();
      } else {
        inputs.underlying_value_finite = false;
      }
    }
    inputs.contract_prior =
        contract_keyed ? contract_prior_.prior(key) : PriorScalar{};
    inputs.underlying_prior = underlying_prior_.prior();
    if (!row.is_null(kPrintSlotExpiration)) {
      inputs.dte_present = true;
      inputs.dte_days = static_cast<std::int64_t>(row.expiration_day) - session_day;
    }

    for (const Side side : {Side::LONG, Side::SHORT}) {
      const auto token = build_option_print_token(inputs, side);
      if (!token.has_value()) {
        return Expected<std::size_t, Refusal>::refuse(token.error());
      }
      const auto& channels = token.value().channels;
      for (std::size_t index = 0; index < kMechanismCount; ++index) {
        const std::size_t channel = kOptionPrintMechanisms[index];
        if (channels.validity[channel] != Validity::VALID) {
          continue;
        }
        if (side == Side::LONG) {
          sum_long[index] += channels.value[channel];
          ++count_long[index];
        } else {
          sum_short[index] += channels.value[channel];
          ++count_short[index];
        }
      }
      if (side == Side::LONG) {
        census_.fold(channels);
        ++quote_attach_states_[static_cast<std::size_t>(inputs.quote_attachment.state)];
        ++underlying_attach_states_[static_cast<std::size_t>(
            inputs.underlying_attachment.state)];
        record.absent_value_cells += static_cast<std::int32_t>(channels.absent_cells());
        if (token.value().unusable_attachment) {
          ++record.unusable_attachment_tokens;
        }
        if (eligibility.eligible) {
          ++directional_eligible_prints_;
        }
      }
    }

    // The two prior machines see the group's members only; both commit after it.
    const bool price_eligible =
        eligibility.eligible && !row.is_null(kPrintSlotPrice) && row.price_u6 > 0;
    if (price_eligible && contract_keyed &&
        !contract_prior_.observe_eligible_price(key, row.price_u6)) {
      return Expected<std::size_t, Refusal>::refuse(
          Refusal(RefusalCode::ARITHMETIC_OVERFLOW, "qr_carriers::OptionPrintStream::push_group",
                  "option contract prior price sum overflowed", row.price_u6));
    }
    if (inputs.underlying_attachment.usable() && inputs.underlying_u6.has_value() &&
        inputs.underlying_value_finite && *inputs.underlying_u6 > 0 &&
        !underlying_prior_.observe_valid(inputs.underlying_attachment.ts_ns_a,
                                         *inputs.underlying_u6)) {
      return Expected<std::size_t, Refusal>::refuse(
          Refusal(RefusalCode::ARITHMETIC_OVERFLOW, "qr_carriers::OptionPrintStream::push_group",
                  "underlying prior sum overflowed", *inputs.underlying_u6));
    }
  }

  for (std::size_t index = 0; index < kMechanismCount; ++index) {
    record.set_mechanism(Side::LONG, index, finite_member_mean(sum_long[index], count_long[index]));
    record.set_mechanism(Side::SHORT, index,
                         finite_member_mean(sum_short[index], count_short[index]));
  }

  contract_prior_.commit_group();
  underlying_prior_.commit_group();
  sequence_.commit_group();
  interarrival_.commit_group(group_ts_ns_a);
  groups_.push_back(record);
  return groups_.size() - 1;
}

}  // namespace qr::carriers
