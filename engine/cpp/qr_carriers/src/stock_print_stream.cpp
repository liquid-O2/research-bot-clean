// qr_carriers/src/stock_print_stream.cpp — the 17 stock-print channels and the
// stock-print session pass.
//
// SPEC (task card V4 section 4): the stock-print channel list (17), the stock
// eligibility contract, the attachment/signing law, the causal aggressor
// ("Print aggressor is +1 when price>=valid prior ask, -1 when price<=valid
// prior bid, otherwise the sign of price minus the prior print-group mean (zero
// on tie/missing), then reflected to action side"), the prior-state law, the
// groupwise sequence law, and the orientation law.
#include <algorithm>

#include <cmath>

#include "qr_carriers/streams.hpp"
#include "stream_common.hpp"

namespace qr::carriers {

using detail_streams::both;
using detail_streams::cell;
using detail_streams::oriented;
using detail_streams::sign_of_difference;

std::span<const std::size_t> mechanism_channels(Modality modality) noexcept {
  switch (modality) {
    case Modality::STOCK_PRINT:
      return {kStockPrintMechanisms.data(), kStockPrintMechanisms.size()};
    case Modality::STOCK_NBBO:
      return {kNbboMechanisms.data(), kNbboMechanisms.size()};
    case Modality::OPTION_PRINT:
      return {kOptionPrintMechanisms.data(), kOptionPrintMechanisms.size()};
  }
  detail::fail_fast("qr::carriers::mechanism_channels: unknown modality");
}

void GroupRecord::set_mechanism(Side side, std::size_t index, Typed<double> value) noexcept {
  const bool present_bit = value.v == Validity::VALID;
  if (side == Side::LONG) {
    mechanism_long[index] = present_bit ? value.value : 0.0;
    if (present_bit) {
      mechanism_present_long |= static_cast<std::uint8_t>(1U << index);
    }
  } else {
    mechanism_short[index] = present_bit ? value.value : 0.0;
    if (present_bit) {
      mechanism_present_short |= static_cast<std::uint8_t>(1U << index);
    }
  }
}

namespace {

/// The attached quote of a stock print, as the signing law reads it.
[[nodiscard]] QuoteFields attached_quote(const qr::sources::StockTradeRow& row) noexcept {
  using namespace qr::sources;
  QuoteFields quote;
  quote.bid_u6 = cell(row.is_null(kTradeSlotBid), row.bid_u6);
  quote.ask_u6 = cell(row.is_null(kTradeSlotAsk), row.ask_u6);
  quote.bid_size = cell(row.is_null(kTradeSlotBidSize), row.bid_shares);
  quote.ask_size = cell(row.is_null(kTradeSlotAskSize), row.ask_shares);
  quote.bid_condition = cell(row.is_null(kTradeSlotBidCondition), row.bid_condition);
  quote.ask_condition = cell(row.is_null(kTradeSlotAskCondition), row.ask_condition);
  return quote;
}

}  // namespace

Expected<StockPrintTokenResult, Refusal> build_stock_print_token(
    const StockPrintTokenInputs& inputs, Side side) {
  using namespace qr::sources;
  if (inputs.row == nullptr) {
    detail::fail_fast("qr::carriers::build_stock_print_token: null row");
  }
  const StockTradeRow& row = *inputs.row;
  const double sigma = sigma_of(side);
  const QuoteFields quote = attached_quote(row);

  StockPrintTokenResult out;
  ChannelRow<kStockPrintChannelCount>& channels = out.channels;

  // --- the two attachment verdicts, kept apart --------------------------------
  // "Attachment age is a continuous channel" and needs only the CLOCK verdict;
  // sign/midpoint/spread/depth additionally need the SIGNING verdict.
  const bool clock_usable = inputs.quote_attachment.usable();
  const bool signing_valid = inputs.quote_signing == Validity::VALID;
  const bool quote_usable = clock_usable && signing_valid;
  const Validity quote_dependency =
      both(inputs.quote_attachment.validity(), inputs.quote_signing);
  // ONE union indicator per print over every dependency it requires.
  out.unusable_attachment = !quote_usable;

  const Validity directional = inputs.eligibility.directional_validity;
  const bool directional_ok = inputs.eligibility.direction_eligible;

  // --- 0. log interarrival ----------------------------------------------------
  channels.set(kSpLogInterarrival,
               inputs.group.interarrival_micros.has_value()
                   ? time_log1p_micros(*inputs.group.interarrival_micros)
                   : masked(Validity::MISSING));

  // --- 1. oriented print return ----------------------------------------------
  {
    const Validity dependency = both(directional, inputs.price_prior.validity());
    if (dependency != Validity::VALID) {
      channels.set(kSpOrientedPrintReturn, masked(dependency));
    } else {
      const auto bps = displacement_bps_value(row.price_u6 - inputs.price_prior.mean,
                                              inputs.price_prior.mean);
      if (!bps.has_value()) {
        return Expected<StockPrintTokenResult, Refusal>::refuse(bps.error());
      }
      channels.set(kSpOrientedPrintReturn, oriented(bps.value(), sigma));
    }
  }

  // --- 2. oriented print-minus-mid --------------------------------------------
  std::optional<std::int64_t> attached_mid;
  if (quote_usable) {
    attached_mid = midpoint_u6(*quote.bid_u6, *quote.ask_u6);
  }
  {
    const Validity dependency = both(directional, quote_usable ? Validity::VALID : quote_dependency);
    if (dependency != Validity::VALID || !attached_mid.has_value()) {
      channels.set(kSpOrientedPrintMinusMid,
                   masked(dependency == Validity::VALID ? Validity::MISSING : dependency));
    } else {
      const auto bps = displacement_bps_value(row.price_u6 - *attached_mid, *attached_mid);
      if (!bps.has_value()) {
        return Expected<StockPrintTokenResult, Refusal>::refuse(bps.error());
      }
      channels.set(kSpOrientedPrintMinusMid, oriented(bps.value(), sigma));
    }
  }

  // --- 3. oriented aggressor ---------------------------------------------------
  // The quote branch first, the strictly-prior print-group tick fallback second,
  // and "the quote branch is skipped, not imputed, when its attachment is
  // unavailable". With NEITHER reference the aggressor is unresolved (masked),
  // which is not the same fact as a resolved tie (present 0).
  int aggressor = 0;
  bool aggressor_resolved = false;
  if (directional_ok) {
    if (quote_usable && row.price_u6 >= *quote.ask_u6) {
      aggressor = 1;
      aggressor_resolved = true;
    } else if (quote_usable && row.price_u6 <= *quote.bid_u6) {
      aggressor = -1;
      aggressor_resolved = true;
    } else if (inputs.price_prior.present) {
      aggressor = sign_of_difference(row.price_u6, inputs.price_prior.mean);
      aggressor_resolved = true;
    } else if (quote_usable) {
      // Inside a valid spread with no prior print group: the reference exists
      // but says neither buy nor sell — a resolved tie, value 0.
      aggressor = 0;
      aggressor_resolved = true;
    }
  }
  channels.set(kSpOrientedAggressor,
               aggressor_resolved
                   ? oriented(present(static_cast<double>(aggressor)), sigma)
                   : masked(directional_ok ? Validity::MISSING : directional));

  // --- 4. log size (a RAW COUNT: it survives an ineligible condition) ----------
  channels.set(kSpLogSize, row.is_null(kTradeSlotSize) ? masked(Validity::MISSING)
                                                       : count_log1p(row.size));

  // --- 5. oriented signed size -------------------------------------------------
  if (!aggressor_resolved || row.is_null(kTradeSlotSize)) {
    channels.set(kSpOrientedSignedSize,
                 masked(directional_ok ? Validity::MISSING : directional));
  } else {
    const auto signed_size = checked_mul(static_cast<std::int64_t>(aggressor), row.size);
    if (!signed_size.has_value()) {
      return Expected<StockPrintTokenResult, Refusal>::refuse(signed_size.error());
    }
    channels.set(kSpOrientedSignedSize,
                 oriented(signed_log1p_int(signed_size.value()), sigma));
  }

  // --- 6. spread bps (invariant) ------------------------------------------------
  if (!quote_usable) {
    channels.set(kSpSpreadBps, masked(quote_dependency));
  } else {
    const auto bps = displacement_bps_value(*quote.ask_u6 - *quote.bid_u6, *attached_mid);
    if (!bps.has_value()) {
      return Expected<StockPrintTokenResult, Refusal>::refuse(bps.error());
    }
    channels.set(kSpSpreadBps, bps.value());
  }

  // --- 7/8. log own / opposite attached size -----------------------------------
  // "own/opposite is ask/bid for LONG and bid/ask for SHORT".
  {
    const std::optional<std::int64_t> own = side == Side::LONG ? quote.ask_size : quote.bid_size;
    const std::optional<std::int64_t> opposite =
        side == Side::LONG ? quote.bid_size : quote.ask_size;
    channels.set(kSpLogOwnAttachedSize, (quote_usable && own.has_value())
                                            ? count_log1p(*own)
                                            : masked(quote_usable ? Validity::MISSING
                                                                  : quote_dependency));
    channels.set(kSpLogOppositeAttachedSize,
                 (quote_usable && opposite.has_value())
                     ? count_log1p(*opposite)
                     : masked(quote_usable ? Validity::MISSING : quote_dependency));
  }

  // --- 9. oriented size imbalance (CC-005 shape, on the attached sizes) ---------
  if (!quote_usable || !quote.bid_size.has_value() || !quote.ask_size.has_value()) {
    channels.set(kSpOrientedSizeImbalance,
                 masked(quote_usable ? Validity::MISSING : quote_dependency));
  } else {
    const std::int64_t total = *quote.bid_size + *quote.ask_size;
    if (total == 0) {
      channels.set(kSpOrientedSizeImbalance, masked(Validity::MISSING));
    } else {
      const double imbalance =
          static_cast<double>(*quote.bid_size - *quote.ask_size) / static_cast<double>(total);
      channels.set(kSpOrientedSizeImbalance, oriented(present(imbalance), sigma));
    }
  }

  // --- 10. log quote age (the CLOCK verdict alone) ------------------------------
  if (!clock_usable) {
    channels.set(kSpLogQuoteAge, masked(inputs.quote_attachment.validity()));
  } else {
    const auto micros =
        duration_micros(inputs.quote_attachment.ts_ns_a, inputs.group.ts_ns_a);
    if (!micros.has_value()) {
      return Expected<StockPrintTokenResult, Refusal>::refuse(micros.error());
    }
    channels.set(kSpLogQuoteAge, time_log1p_micros(micros.value()));
  }

  // --- 11/12/15/16. the structurally observed binary quality values -------------
  channels.set(kSpQuotePresent, structural_bit(row.quote_present()));
  channels.set(kSpAttachmentValid, structural_bit(quote_usable));
  channels.set(kSpSameMs, structural_bit(inputs.group.same_ms));
  channels.set(kSpDirectionalEligible, structural_bit(directional_ok));

  // --- 13/14. the groupwise sequence quality ------------------------------------
  channels.set(kSpSequenceGapSignedLog, inputs.group.sequence.pair_formed
                                            ? signed_log1p_int(inputs.group.sequence.gap)
                                            : masked(Validity::MISSING));
  channels.set(kSpSequenceMonotone, inputs.group.sequence.pair_formed
                                        ? structural_bit(inputs.group.sequence.monotone)
                                        : masked(Validity::MISSING));
  return out;
}

// ---------------------------------------------------------------------------
// The session pass.
// ---------------------------------------------------------------------------

Expected<std::size_t, Refusal> StockPrintStream::push_group(
    std::int64_t ts_ms_b, std::span<const qr::sources::StockTradeRow> rows) {
  const auto ts_a = clock_.to_frame_a(FrameB{ts_ms_b * kNanosecondsPerMillisecond});
  if (!ts_a.has_value()) {
    return Expected<std::size_t, Refusal>::refuse(ts_a.error());
  }
  const std::int64_t group_ts_ns_a = ts_a.value().ns();

  // Canonical member order BEFORE any floating-point reduction (see the header:
  // permutation invariance is structural, in two layers).
  canonical_.assign(rows.begin(), rows.end());
  if (canonical_.size() > 1) {
    std::sort(canonical_.begin(), canonical_.end(),
              [](const qr::sources::StockTradeRow& left, const qr::sources::StockTradeRow& right) {
                return qr::sources::canonical_less(left, right);
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
  for (const qr::sources::StockTradeRow& row : canonical_) {
    if (!row.is_null(qr::sources::kTradeSlotSequence)) {
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
  // NATIVE_ORDER (section 4): "identity token values plus presence bits are
  // reduced by finite mean and max over ALL equal-time members". The reduction
  // is fed from THIS member loop — the same canonical order, the same frozen
  // prior — so the equal-ms control exercises it through the real constructor.
  std::array<GroupReducer<kStockPrintChannelCount>, 2> reducers{};

  prior_.begin_group(group_ts_ns_a);
  for (const qr::sources::StockTradeRow& row : canonical_) {
    StockPrintTokenInputs inputs;
    inputs.row = &row;
    inputs.group = context;
    inputs.eligibility = classify_stock_print(row);
    inputs.quote_attachment = classify_attachment_ms(
        clock_, cell(row.is_null(qr::sources::kTradeSlotQuoteTimestamp), row.quote_ts_ms_b),
        group_ts_ns_a);
    inputs.quote_signing = quote_signing_validity(attached_quote(row));
    inputs.price_prior = prior_.prior();

    for (const Side side : {Side::LONG, Side::SHORT}) {
      const auto token = build_stock_print_token(inputs, side);
      if (!token.has_value()) {
        return Expected<std::size_t, Refusal>::refuse(token.error());
      }
      const auto& channels = token.value().channels;
      if (options_.retain_group_vectors) {
        reducers[static_cast<std::size_t>(side)].observe(channels);
      }
      for (std::size_t index = 0; index < kMechanismCount; ++index) {
        const std::size_t channel = kStockPrintMechanisms[index];
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
        quality_.fold(inputs.eligibility);
        ++attach_states_[static_cast<std::size_t>(inputs.quote_attachment.state)];
        record.absent_value_cells += static_cast<std::int32_t>(channels.absent_cells());
        if (token.value().unusable_attachment) {
          ++record.unusable_attachment_tokens;
        }
        if (inputs.eligibility.direction_eligible) {
          const auto weighted = checked_mul(row.price_u6, row.size);
          if (!weighted.has_value()) {
            return Expected<std::size_t, Refusal>::refuse(weighted.error());
          }
          const auto notional = checked_add(vwap_notional_sum_, weighted.value());
          if (!notional.has_value()) {
            return Expected<std::size_t, Refusal>::refuse(notional.error());
          }
          vwap_notional_sum_ = notional.value();
          vwap_size_sum_ += row.size;
        }
      }
    }

    // The prior sees ONLY eligible members, and only after the whole group.
    if (inputs.eligibility.direction_eligible && !prior_.observe_eligible_price(row.price_u6)) {
      return Expected<std::size_t, Refusal>::refuse(
          Refusal(RefusalCode::ARITHMETIC_OVERFLOW, "qr_carriers::StockPrintStream::push_group",
                  "stock print prior price sum overflowed", row.price_u6));
    }
  }

  for (std::size_t index = 0; index < kMechanismCount; ++index) {
    record.set_mechanism(Side::LONG, index, finite_member_mean(sum_long[index], count_long[index]));
    record.set_mechanism(Side::SHORT, index,
                         finite_member_mean(sum_short[index], count_short[index]));
  }

  if (options_.retain_group_vectors) {
    // The STORED form is side-neutral: the unoriented (LONG) vector plus the min
    // block the reflected side's max needs (group_vector.hpp).
    std::array<double, kStockPrintNeutralDim> neutral{};
    reducers[static_cast<std::size_t>(Side::LONG)].write_neutral(
        Modality::STOCK_PRINT, record.token_count, record.log1p_multiplicity, neutral);
    vectors_.append(neutral);
    if (options_.side_spot_stride > 0 &&
        static_cast<std::int64_t>(groups_.size()) % options_.side_spot_stride == 0) {
      // The independent per-side reference for the sampled group.
      std::array<double, kStockPrintGroupDim> reduced{};
      for (const Side side : {Side::LONG, Side::SHORT}) {
        const std::size_t index = static_cast<std::size_t>(side);
        reducers[index].write(record.token_count, record.log1p_multiplicity, reduced);
        spot_[index].append(reduced);
      }
      spot_groups_.push_back(static_cast<std::int32_t>(groups_.size()));
    }
  }

  prior_.commit_group();
  sequence_.commit_group();
  interarrival_.commit_group(group_ts_ns_a);
  vwap_notional_prefix_.push_back(vwap_notional_sum_);
  vwap_size_prefix_.push_back(vwap_size_sum_);
  groups_.push_back(record);
  return groups_.size() - 1;
}

}  // namespace qr::carriers
