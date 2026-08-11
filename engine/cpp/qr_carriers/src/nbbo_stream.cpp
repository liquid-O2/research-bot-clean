// qr_carriers/src/nbbo_stream.cpp — the 16 stock-NBBO channels and the NBBO
// session pass.
//
// SPEC (task card V4 section 4): the stock-NBBO channel list (16); "Standalone
// stock NBBO rows obey the same finite/positive/ask>bid/condition law for all
// price, size, midpoint, imbalance, and return channels; invalid rows remain as
// locked/crossed/one-sided/condition quality tokens with those economic values
// masked"; the scalar-means-before-derived law; **CC-005**; and the prior-state
// law. "For NBBO, attachment-invalid and sequence-inversion are typed
// structural zeros."
//
// THE ELIGIBILITY VERDICT IS qr_nbbo's, NOT A SECOND COPY. `classify_member`
// (qr_nbbo/group_machine.hpp) is the frozen typed view of one NBBO row, already
// red-ledgered by WP5; re-deriving it here would be a second authority on the
// same question. This file consumes it and adds only the CHANNEL layer.
#include <cmath>

#include "qr_carriers/streams.hpp"
#include "qr_nbbo/census.hpp"
#include "qr_nbbo/group_machine.hpp"
#include "stream_common.hpp"

namespace qr::carriers {

using detail_streams::both;
using detail_streams::cell;
using detail_streams::oriented;

Expected<NbboTokenResult, Refusal> build_nbbo_group_token(const NbboGroupInputs& inputs,
                                                          Side side) {
  if (inputs.current == nullptr || inputs.prior == nullptr) {
    detail::fail_fast("qr::carriers::build_nbbo_group_token: null scalars");
  }
  const NbboScalars& current = *inputs.current;
  const NbboPrior& prior = *inputs.prior;
  const double sigma = sigma_of(side);

  NbboTokenResult out;
  // "For NBBO, attachment-invalid ... [is a] typed structural zero": an NBBO
  // row hangs on no attachment, so the union indicator can never fire.
  out.unusable_attachment = false;
  ChannelRow<kNbboChannelCount>& channels = out.channels;

  const Typed<std::int64_t> mid = current.mid();
  const Typed<std::int64_t> spread = current.spread();
  const Typed<std::int64_t> bid_mean = current.bid_u6.mean();
  const Typed<std::int64_t> ask_mean = current.ask_u6.mean();
  const Typed<std::int64_t> bid_size_mean = current.bid_shares.mean();
  const Typed<std::int64_t> ask_size_mean = current.ask_shares.mean();

  const Typed<std::int64_t> prior_mid = prior.present ? prior.scalars.mid()
                                                      : Typed<std::int64_t>{0, Validity::MISSING};
  const Typed<std::int64_t> prior_bid =
      prior.present ? prior.scalars.bid_u6.mean() : Typed<std::int64_t>{0, Validity::MISSING};
  const Typed<std::int64_t> prior_ask =
      prior.present ? prior.scalars.ask_u6.mean() : Typed<std::int64_t>{0, Validity::MISSING};
  const Typed<std::int64_t> prior_bid_size =
      prior.present ? prior.scalars.bid_shares.mean() : Typed<std::int64_t>{0, Validity::MISSING};
  const Typed<std::int64_t> prior_ask_size =
      prior.present ? prior.scalars.ask_shares.mean() : Typed<std::int64_t>{0, Validity::MISSING};

  // --- 0. log interarrival ------------------------------------------------------
  channels.set(kNbLogInterarrival, inputs.group.interarrival_micros.has_value()
                                       ? time_log1p_micros(*inputs.group.interarrival_micros)
                                       : masked(Validity::MISSING));

  // --- 1. oriented midpoint change ----------------------------------------------
  if (mid.v != Validity::VALID || prior_mid.v != Validity::VALID) {
    channels.set(kNbOrientedMidpointChange, masked(both(mid.v, prior_mid.v)));
  } else {
    const auto bps = displacement_bps_value(mid.value - prior_mid.value, prior_mid.value);
    if (!bps.has_value()) {
      return Expected<NbboTokenResult, Refusal>::refuse(bps.error());
    }
    channels.set(kNbOrientedMidpointChange, oriented(bps.value(), sigma));
  }

  // --- 2. spread bps (invariant) -------------------------------------------------
  if (spread.v != Validity::VALID || mid.v != Validity::VALID) {
    channels.set(kNbSpreadBps, masked(both(spread.v, mid.v)));
  } else {
    const auto bps = displacement_bps_value(spread.value, mid.value);
    if (!bps.has_value()) {
      return Expected<NbboTokenResult, Refusal>::refuse(bps.error());
    }
    channels.set(kNbSpreadBps, bps.value());
  }

  // --- 3/4. log own / opposite size ---------------------------------------------
  {
    const Typed<std::int64_t> own = side == Side::LONG ? ask_size_mean : bid_size_mean;
    const Typed<std::int64_t> opposite = side == Side::LONG ? bid_size_mean : ask_size_mean;
    channels.set(kNbLogOwnSize,
                 own.v == Validity::VALID ? count_log1p(own.value) : masked(own.v));
    channels.set(kNbLogOppositeSize,
                 opposite.v == Validity::VALID ? count_log1p(opposite.value) : masked(opposite.v));
  }

  // --- 5. oriented imbalance (CC-005, from the two SIZE means) --------------------
  channels.set(kNbOrientedImbalance, oriented(current.imbalance(), sigma));

  // --- 6/7. own / opposite price change ------------------------------------------
  // Not sigma-multiplied: the declared name carries no "oriented" prefix, so the
  // reflection acts on these channels ONLY through the own/opposite swap.
  {
    const Typed<std::int64_t> own = side == Side::LONG ? ask_mean : bid_mean;
    const Typed<std::int64_t> own_prior = side == Side::LONG ? prior_ask : prior_bid;
    const Typed<std::int64_t> opposite = side == Side::LONG ? bid_mean : ask_mean;
    const Typed<std::int64_t> opposite_prior = side == Side::LONG ? prior_bid : prior_ask;

    const std::array<std::pair<std::size_t, std::pair<Typed<std::int64_t>, Typed<std::int64_t>>>, 2>
        pairs{std::make_pair(static_cast<std::size_t>(kNbOwnPriceChange),
                             std::make_pair(own, own_prior)),
              std::make_pair(static_cast<std::size_t>(kNbOppositePriceChange),
                             std::make_pair(opposite, opposite_prior))};
    for (const auto& entry : pairs) {
      const Typed<std::int64_t>& now = entry.second.first;
      const Typed<std::int64_t>& before = entry.second.second;
      if (now.v != Validity::VALID || before.v != Validity::VALID) {
        channels.set(entry.first, masked(both(now.v, before.v)));
        continue;
      }
      const auto bps = displacement_bps_value(now.value - before.value, before.value);
      if (!bps.has_value()) {
        return Expected<NbboTokenResult, Refusal>::refuse(bps.error());
      }
      channels.set(entry.first, bps.value());
    }
  }

  // --- 8/9. own / opposite signed size change ------------------------------------
  {
    const Typed<std::int64_t> own = side == Side::LONG ? ask_size_mean : bid_size_mean;
    const Typed<std::int64_t> own_prior = side == Side::LONG ? prior_ask_size : prior_bid_size;
    const Typed<std::int64_t> opposite = side == Side::LONG ? bid_size_mean : ask_size_mean;
    const Typed<std::int64_t> opposite_prior =
        side == Side::LONG ? prior_bid_size : prior_ask_size;
    channels.set(kNbOwnSignedSizeChange,
                 (own.v == Validity::VALID && own_prior.v == Validity::VALID)
                     ? signed_log1p_int(own.value - own_prior.value)
                     : masked(both(own.v, own_prior.v)));
    channels.set(kNbOppositeSignedSizeChange,
                 (opposite.v == Validity::VALID && opposite_prior.v == Validity::VALID)
                     ? signed_log1p_int(opposite.value - opposite_prior.value)
                     : masked(both(opposite.v, opposite_prior.v)));
  }

  // --- 10/11/12/15. the structurally observed group quality bits -------------------
  channels.set(kNbLocked, structural_bit(inputs.any_locked));
  channels.set(kNbCrossed, structural_bit(inputs.any_crossed));
  channels.set(kNbPositiveTwoSided, structural_bit(inputs.any_positive_two_sided));
  channels.set(kNbSameMs, structural_bit(inputs.group.same_ms));

  // --- 13/14. bid-changed / ask-changed -------------------------------------------
  channels.set(kNbBidChanged, (bid_mean.v == Validity::VALID && prior_bid.v == Validity::VALID)
                                  ? structural_bit(bid_mean.value != prior_bid.value)
                                  : masked(both(bid_mean.v, prior_bid.v)));
  channels.set(kNbAskChanged, (ask_mean.v == Validity::VALID && prior_ask.v == Validity::VALID)
                                  ? structural_bit(ask_mean.value != prior_ask.value)
                                  : masked(both(ask_mean.v, prior_ask.v)));
  return out;
}

// ---------------------------------------------------------------------------
// The session pass.
// ---------------------------------------------------------------------------

Expected<std::size_t, Refusal> NbboStream::push_group(
    std::int64_t ts_ms_b, std::span<const qr::sources::StockQuoteRow> rows) {
  const auto ts_a = clock_.to_frame_a(FrameB{ts_ms_b * kNanosecondsPerMillisecond});
  if (!ts_a.has_value()) {
    return Expected<std::size_t, Refusal>::refuse(ts_a.error());
  }
  const std::int64_t group_ts_ns_a = ts_a.value().ns();

  GroupContext context;
  context.ts_ns_a = group_ts_ns_a;
  const auto gap = interarrival_.micros_before(group_ts_ns_a);
  if (!gap.has_value()) {
    return Expected<std::size_t, Refusal>::refuse(gap.error());
  }
  context.interarrival_micros = gap.value();
  context.same_ms = rows.size() > 1;
  // NBBO projects no vendor sequence, so all three sequence facts are the
  // card's typed structural zeros; `SequenceVerdict{}` is exactly that.

  NbboGroupInputs inputs;
  inputs.group = context;
  prior_.begin_group(group_ts_ns_a);
  for (const qr::sources::StockQuoteRow& row : rows) {
    const auto classified = qr::nbbo::classify_member(row);
    if (!classified.has_value()) {
      return Expected<std::size_t, Refusal>::refuse(classified.error());
    }
    const qr::nbbo::MemberClass& member = classified.value();
    if (member.state == qr::nbbo::QuoteState::LOCKED) {
      inputs.any_locked = true;
    }
    if (member.state == qr::nbbo::QuoteState::CROSSED) {
      inputs.any_crossed = true;
    }
    const bool two_sided = !row.is_null(qr::sources::kQuoteSlotBid) &&
                           !row.is_null(qr::sources::kQuoteSlotAsk) && row.bid_u6 > 0 &&
                           row.ask_u6 > 0;
    if (two_sided) {
      inputs.any_positive_two_sided = true;
    }
    if (member.validity == Validity::VALID &&
        !prior_.observe_eligible(row.bid_u6, row.ask_u6, row.bid_shares, row.ask_shares)) {
      return Expected<std::size_t, Refusal>::refuse(
          Refusal(RefusalCode::ARITHMETIC_OVERFLOW, "qr_carriers::NbboStream::push_group",
                  "NBBO scalar sum overflowed", row.bid_u6));
    }
  }

  const NbboPrior frozen_prior = prior_.prior();
  inputs.current = &prior_.pending();
  inputs.prior = &frozen_prior;

  GroupRecord record;
  record.ts_ns_a = group_ts_ns_a;
  record.token_count = static_cast<std::int32_t>(rows.size());
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

  for (const Side side : {Side::LONG, Side::SHORT}) {
    const auto token = build_nbbo_group_token(inputs, side);
    if (!token.has_value()) {
      return Expected<std::size_t, Refusal>::refuse(token.error());
    }
    const auto& channels = token.value().channels;
    for (std::size_t index = 0; index < kMechanismCount; ++index) {
      const std::size_t channel = kNbboMechanisms[index];
      record.set_mechanism(side, index,
                           Typed<double>{channels.value[channel], channels.validity[channel]});
    }
    if (side == Side::LONG) {
      // Every member of the group carries this group vector, so the token-level
      // census and the missing-cell numerator scale by the member count.
      const std::int64_t absent_per_token = static_cast<std::int64_t>(channels.absent_cells());
      record.absent_value_cells =
          static_cast<std::int32_t>(absent_per_token * static_cast<std::int64_t>(rows.size()));
      census_.fold_repeated(channels, static_cast<std::int64_t>(rows.size()));
    }
  }

  // The eligible-midpoint prefix series the 1s grid and the location values read.
  const Typed<std::int64_t> mid = prior_.pending().mid();
  const Typed<std::int64_t> spread = prior_.pending().spread();
  if (mid.v == Validity::VALID && spread.v == Validity::VALID) {
    eligible_midpoints_.push_back(EligibleMid{group_ts_ns_a, mid.value, spread.value});
  }

  prior_.commit_group();
  interarrival_.commit_group(group_ts_ns_a);
  groups_.push_back(record);
  return groups_.size() - 1;
}

}  // namespace qr::carriers
