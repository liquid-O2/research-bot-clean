// test_channels.cpp — THE THREE CHANNEL LISTS, ON HAND LITERALS, THROUGH THE
// ACTUAL PRODUCTION CONSTRUCTORS.
//
// The brief's named controls that live here:
//   * "equal-ms permutation through the ACTUAL constructors (bit-identical
//     outputs + later prior states)";
//   * "orientation reflection at channel level (sigma swap changes exactly the
//     declared channels; gamma invariant)";
//   * "duplicate one attachment failure reason (unusable-attachment fraction
//     must not double-count)".
//
// Every expected value is hand arithmetic in the comment beside it. Where the
// law's answer is an INTEGER (a bps displacement, a microsecond span, a raw
// size) the integer is the literal and the declared transform is then applied
// to it — the transform itself is proven separately in test_transforms.cpp.
#include <gtest/gtest.h>

#include <cctype>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <string>

#include "carriers_test_support.hpp"
#include "qr_carriers/streams.hpp"

namespace qr::carriers {
namespace {

using testing::clock_125;
using testing::frame_a_of;
using testing::open_ms;
using testing::option_row;
using testing::quote_row;
using testing::rows_of;
using testing::serialize;
using testing::trade_row;

// --- the stock-print tape ----------------------------------------------------
//
//   group @ open+8'000ms : one eligible print, price 100'000'000 u6, seq 5
//   group @ open+10'000ms: two eligible prints (an equal-millisecond group)
//     P1 price 100'030'000, size 300, quote@9'000ms bid 99'990'000 ask 100'010'000
//                                     sizes 500/700, seq 10
//     P2 price 100'050'000, size 200, quote@9'500ms bid 100'010'000 ask 100'030'000
//                                     sizes 100/900, seq 12
constexpr std::int64_t kPriorPrice = 100'000'000;

std::vector<qr::sources::StockTradeRow> prior_print_group() {
  return rows_of<qr::sources::StockTradeRow>(
      {trade_row(open_ms() + 8'000, kPriorPrice, 100, open_ms() + 7'000, 99'990'000, 100'010'000,
                 400, 400, /*sequence=*/5)});
}

qr::sources::StockTradeRow print_p1() {
  return trade_row(open_ms() + 10'000, 100'030'000, 300, open_ms() + 9'000, 99'990'000,
                   100'010'000, 500, 700, /*sequence=*/10);
}
qr::sources::StockTradeRow print_p2() {
  return trade_row(open_ms() + 10'000, 100'050'000, 200, open_ms() + 9'500, 100'010'000,
                   100'030'000, 100, 900, /*sequence=*/12);
}

TEST(StockPrintChannels, TheSeventeenChannelsAreTheCardsSeventeenValues) {
  StockPrintStream stream(clock_125());
  const auto first = stream.push_group(open_ms() + 8'000, prior_print_group());
  ASSERT_TRUE(first.has_value());

  const auto group = rows_of<qr::sources::StockTradeRow>({print_p1(), print_p2()});
  StockPrintTokenInputs inputs;
  const qr::sources::StockTradeRow row = print_p1();
  inputs.row = &row;
  inputs.group.ts_ns_a = frame_a_of(10'000);
  inputs.group.interarrival_micros = 2'000'000;  // 10'000ms - 8'000ms = 2'000ms = 2'000'000us
  inputs.group.same_ms = true;                   // multiplicity 2
  inputs.group.sequence = SequenceVerdict{/*valid=*/true, /*pair=*/true, /*gap=*/5,
                                          /*monotone=*/true, /*inversion=*/false};
  inputs.eligibility = classify_stock_print(row);
  inputs.quote_attachment = classify_attachment_ms(clock_125(), open_ms() + 9'000,
                                                   inputs.group.ts_ns_a);
  QuoteFields quote;
  quote.bid_u6 = 99'990'000;
  quote.ask_u6 = 100'010'000;
  quote.bid_size = 500;
  quote.ask_size = 700;
  quote.bid_condition = 0;
  quote.ask_condition = 0;
  inputs.quote_signing = quote_signing_validity(quote);
  inputs.price_prior = PriorScalar{true, frame_a_of(8'000), kPriorPrice};

  ASSERT_EQ(inputs.quote_signing, Validity::VALID);
  ASSERT_TRUE(inputs.quote_attachment.usable());
  ASSERT_TRUE(inputs.eligibility.direction_eligible);

  const auto built = build_stock_print_token(inputs, Side::LONG);
  ASSERT_TRUE(built.has_value());
  const auto& channels = built.value().channels;

  //  0  log interarrival: 2'000'000 us
  EXPECT_NEAR(channels.value[kSpLogInterarrival], std::log1p(2'000'000.0), 1e-12);
  //  1  oriented print return: (100'030'000 - 100'000'000)*10'000/100'000'000
  //       = 30'000*10'000/1e8 = 3e8/1e8 = 3 bps
  EXPECT_DOUBLE_EQ(channels.value[kSpOrientedPrintReturn], 3.0);
  //  2  oriented print-minus-mid: mid = 99'990'000 + (100'010'000-99'990'000)/2
  //       = 100'000'000; (100'030'000-100'000'000)*10'000/100'000'000 = 3 bps
  EXPECT_DOUBLE_EQ(channels.value[kSpOrientedPrintMinusMid], 3.0);
  //  3  oriented aggressor: price 100'030'000 >= ask 100'010'000 -> +1
  EXPECT_DOUBLE_EQ(channels.value[kSpOrientedAggressor], 1.0);
  //  4  log size: 300
  EXPECT_NEAR(channels.value[kSpLogSize], std::log1p(300.0), 1e-15);
  //  5  oriented signed size: +1 * 300 = 300 -> sign*log1p(300)
  EXPECT_NEAR(channels.value[kSpOrientedSignedSize], std::log1p(300.0), 1e-15);
  //  6  spread bps: (100'010'000-99'990'000)*10'000/100'000'000 = 2e8/1e8 = 2
  EXPECT_DOUBLE_EQ(channels.value[kSpSpreadBps], 2.0);
  //  7  log own attached size: LONG own = ASK = 700
  EXPECT_NEAR(channels.value[kSpLogOwnAttachedSize], std::log1p(700.0), 1e-15);
  //  8  log opposite attached size: LONG opposite = BID = 500
  EXPECT_NEAR(channels.value[kSpLogOppositeAttachedSize], std::log1p(500.0), 1e-15);
  //  9  oriented size imbalance (CC-005 shape): (500-700)/(500+700) = -200/1200 = -1/6
  EXPECT_DOUBLE_EQ(channels.value[kSpOrientedSizeImbalance], -1.0 / 6.0);
  // 10  log quote age: 10'000ms - 9'000ms = 1'000ms = 1'000'000us
  EXPECT_NEAR(channels.value[kSpLogQuoteAge], std::log1p(1'000'000.0), 1e-12);
  // 11..16 the structural and quality values
  EXPECT_DOUBLE_EQ(channels.value[kSpQuotePresent], 1.0);
  EXPECT_DOUBLE_EQ(channels.value[kSpAttachmentValid], 1.0);
  EXPECT_NEAR(channels.value[kSpSequenceGapSignedLog], std::log1p(5.0), 1e-15);
  EXPECT_DOUBLE_EQ(channels.value[kSpSequenceMonotone], 1.0);
  EXPECT_DOUBLE_EQ(channels.value[kSpSameMs], 1.0);
  EXPECT_DOUBLE_EQ(channels.value[kSpDirectionalEligible], 1.0);

  // Every one of the seventeen is PRESENT on this fully-attached print.
  for (std::size_t channel = 0; channel < kStockPrintChannelCount; ++channel) {
    EXPECT_TRUE(channels.presence(channel)) << stock_print_channel_name(channel);
  }
  EXPECT_FALSE(built.value().unusable_attachment);
  EXPECT_EQ(group.size(), 2U);
}

TEST(StockPrintChannels, TruncatingIntegerBpsIsVisibleInPrintMinusMid) {
  StockPrintTokenInputs inputs;
  const qr::sources::StockTradeRow row = print_p2();
  inputs.row = &row;
  inputs.group.ts_ns_a = frame_a_of(10'000);
  inputs.eligibility = classify_stock_print(row);
  inputs.quote_attachment =
      classify_attachment_ms(clock_125(), open_ms() + 9'500, inputs.group.ts_ns_a);
  QuoteFields quote;
  quote.bid_u6 = 100'010'000;
  quote.ask_u6 = 100'030'000;
  quote.bid_size = 100;
  quote.ask_size = 900;
  quote.bid_condition = 0;
  quote.ask_condition = 0;
  inputs.quote_signing = quote_signing_validity(quote);
  inputs.price_prior = PriorScalar{true, frame_a_of(8'000), kPriorPrice};

  const auto built = build_stock_print_token(inputs, Side::LONG);
  ASSERT_TRUE(built.has_value());
  const auto& channels = built.value().channels;
  // mid = 100'010'000 + (100'030'000-100'010'000)/2 = 100'020'000
  // (100'050'000-100'020'000)*10'000/100'020'000 = 3e8/100'020'000 = 2.9994
  //   -> TRUNCATED to 2, not rounded to 3.
  EXPECT_DOUBLE_EQ(channels.value[kSpOrientedPrintMinusMid], 2.0);
  // spread: (100'030'000-100'010'000)*10'000/100'020'000 = 2e8/100'020'000 = 1.9996 -> 1
  EXPECT_DOUBLE_EQ(channels.value[kSpSpreadBps], 1.0);
  // return vs the prior group mean: 50'000*10'000/1e8 = 5 bps
  EXPECT_DOUBLE_EQ(channels.value[kSpOrientedPrintReturn], 5.0);
  // imbalance: (100-900)/1000 = -0.8
  EXPECT_DOUBLE_EQ(channels.value[kSpOrientedSizeImbalance], -0.8);
}

TEST(StockPrintChannels, AnUnusableQuoteSkipsTheQuoteBranchAndFallsBackToThePriorTick) {
  // The quote is CROSSED (bid > ask), so it "cannot sign an aggressor or supply
  // midpoint/spread/depth/valuation" — the quote branch is SKIPPED, not imputed,
  // and the aggressor comes from the prior print-group mean instead.
  qr::sources::StockTradeRow row =
      trade_row(open_ms() + 10'000, 99'970'000, 300, open_ms() + 9'000, 100'010'000, 99'990'000,
                500, 700, /*sequence=*/10);
  StockPrintTokenInputs inputs;
  inputs.row = &row;
  inputs.group.ts_ns_a = frame_a_of(10'000);
  inputs.eligibility = classify_stock_print(row);
  inputs.quote_attachment =
      classify_attachment_ms(clock_125(), open_ms() + 9'000, inputs.group.ts_ns_a);
  QuoteFields quote;
  quote.bid_u6 = 100'010'000;
  quote.ask_u6 = 99'990'000;
  quote.bid_size = 500;
  quote.ask_size = 700;
  quote.bid_condition = 0;
  quote.ask_condition = 0;
  inputs.quote_signing = quote_signing_validity(quote);
  ASSERT_EQ(inputs.quote_signing, Validity::CROSSED);
  inputs.price_prior = PriorScalar{true, frame_a_of(8'000), kPriorPrice};

  const auto built = build_stock_print_token(inputs, Side::LONG);
  ASSERT_TRUE(built.has_value());
  const auto& channels = built.value().channels;
  // price 99'970'000 < prior mean 100'000'000 -> sign = -1
  EXPECT_DOUBLE_EQ(channels.value[kSpOrientedAggressor], -1.0);
  // The quote-dependent channels are MASKED with the typed quality token.
  EXPECT_EQ(channels.validity[kSpSpreadBps], Validity::CROSSED);
  EXPECT_EQ(channels.validity[kSpOrientedPrintMinusMid], Validity::CROSSED);
  EXPECT_EQ(channels.validity[kSpLogOwnAttachedSize], Validity::CROSSED);
  EXPECT_EQ(channels.validity[kSpOrientedSizeImbalance], Validity::CROSSED);
  EXPECT_DOUBLE_EQ(channels.value[kSpSpreadBps], 0.0);
  // The CLOCK is fine, so the age channel survives; and attachment-valid is 0.
  EXPECT_TRUE(channels.presence(kSpLogQuoteAge));
  EXPECT_DOUBLE_EQ(channels.value[kSpAttachmentValid], 0.0);
  // The return still works: it depends on the prior group, not on the quote.
  //   (99'970'000-100'000'000)*10'000/1e8 = -3e8/1e8 = -3 bps
  EXPECT_DOUBLE_EQ(channels.value[kSpOrientedPrintReturn], -3.0);
  // ONE union indicator, whatever the reason.
  EXPECT_TRUE(built.value().unusable_attachment);
}

TEST(StockPrintChannels, DuplicatingAnAttachmentFailureReasonDoesNotDoubleCountThePrint) {
  // THE BRIEF'S CONTROL. The second print's attached quote fails on BOTH
  // dependency families at once — its clock is EQUAL_TIME_UNORDERED and its
  // prices are crossed — while the first fails on one. "unusable attachment is
  // one union indicator per print over every quote/underlying clock OR validity
  // dependency required by that print ... never multiple counts for one print",
  // so both groups' counters must read exactly 1.
  qr::sources::StockTradeRow one_reason =
      trade_row(open_ms() + 10'000, 100'000'000, 300, open_ms() + 9'000, 100'010'000, 99'990'000,
                500, 700, 10);
  qr::sources::StockTradeRow two_reasons = one_reason;
  two_reasons.quote_ts_ms_b = open_ms() + 10'000;  // + a second, independent failure

  StockPrintStream single(clock_125());
  StockPrintStream doubled(clock_125());
  const auto pushed_single =
      single.push_group(open_ms() + 10'000, rows_of<qr::sources::StockTradeRow>({one_reason}));
  const auto pushed_double =
      doubled.push_group(open_ms() + 10'000, rows_of<qr::sources::StockTradeRow>({two_reasons}));
  ASSERT_TRUE(pushed_single.has_value());
  ASSERT_TRUE(pushed_double.has_value());

  ASSERT_EQ(single.groups().size(), 1U);
  ASSERT_EQ(doubled.groups().size(), 1U);
  // One failed dependency, and then two: the counter does not move.
  EXPECT_EQ(single.groups()[0].unusable_attachment_tokens, 1);
  EXPECT_EQ(doubled.groups()[0].unusable_attachment_tokens, 1);
  EXPECT_EQ(doubled.groups()[0].token_count, 1);
  // Both failure families really did fire on the second print.
  EXPECT_EQ(classify_attachment_ms(clock_125(), open_ms() + 10'000, frame_a_of(10'000)).state,
            AttachState::EQUAL_TIME_UNORDERED);
  EXPECT_EQ(classify_attachment_ms(clock_125(), open_ms() + 9'000, frame_a_of(10'000)).state,
            AttachState::USABLE);
}

// ---------------------------------------------------------------------------
// The equal-millisecond permutation control, through the ACTUAL constructors.
// ---------------------------------------------------------------------------

TEST(EqualMillisecondPermutation, StockPrintOutputsAndLaterPriorStatesAreBitIdentical) {
  const auto run = [](bool reversed) {
    StockPrintStream stream(clock_125());
    const auto prior = stream.push_group(open_ms() + 8'000, prior_print_group());
    EXPECT_TRUE(prior.has_value());
    const auto group = reversed ? rows_of<qr::sources::StockTradeRow>({print_p2(), print_p1()})
                                : rows_of<qr::sources::StockTradeRow>({print_p1(), print_p2()});
    const auto pushed = stream.push_group(open_ms() + 10'000, group);
    EXPECT_TRUE(pushed.has_value());
    // A LATER group, so the fixture compares the prior states the permuted group
    // left behind and not only the permuted group's own bytes.
    const auto later = stream.push_group(
        open_ms() + 12'000,
        rows_of<qr::sources::StockTradeRow>({trade_row(open_ms() + 12'000, 100'060'000, 50,
                                                       open_ms() + 11'000, 100'040'000,
                                                       100'060'000, 10, 20, 20)}));
    EXPECT_TRUE(later.has_value());
    std::vector<std::uint8_t> bytes;
    for (const GroupRecord& record : stream.groups()) {
      const auto serialized = serialize(record);
      bytes.insert(bytes.end(), serialized.begin(), serialized.end());
    }
    return std::make_pair(bytes, stream.prior().prior());
  };

  const auto forward = run(false);
  const auto reverse = run(true);
  EXPECT_EQ(forward.first, reverse.first) << "permuting an equal-ms group moved an output bit";
  EXPECT_EQ(forward.second.present, reverse.second.present);
  EXPECT_EQ(forward.second.mean, reverse.second.mean);
  EXPECT_EQ(forward.second.ts_ns_a, reverse.second.ts_ns_a);
  // The group's mechanism means are a real reduction over two DIFFERENT members
  // (return 3 and 5 -> mean 4), so the comparison is not trivially satisfied.
  ASSERT_FALSE(forward.first.empty());
}

TEST(EqualMillisecondPermutation, TheStockPrintGroupMeanIsTheOneTheCardDefines) {
  StockPrintStream stream(clock_125());
  ASSERT_TRUE(stream.push_group(open_ms() + 8'000, prior_print_group()).has_value());
  ASSERT_TRUE(stream
                  .push_group(open_ms() + 10'000,
                              rows_of<qr::sources::StockTradeRow>({print_p1(), print_p2()}))
                  .has_value());
  ASSERT_EQ(stream.groups().size(), 2U);
  const GroupRecord& group = stream.groups()[1];
  // mechanism 0 is the oriented print return: (3 + 5)/2 = 4 bps.
  const Typed<double> mean_return = group.mechanism(Side::LONG, 0);
  ASSERT_EQ(mean_return.v, Validity::VALID);
  EXPECT_DOUBLE_EQ(mean_return.value, 4.0);
  // mechanism 1 is the oriented aggressor: both prints lifted the offer, (1+1)/2 = 1.
  EXPECT_DOUBLE_EQ(group.mechanism(Side::LONG, 1).value, 1.0);
  // mechanism 3 is the oriented size imbalance: (-1/6 + -0.8)/2 = -0.4833333...
  EXPECT_DOUBLE_EQ(group.mechanism(Side::LONG, 3).value, (-1.0 / 6.0 + -0.8) / 2.0);
  // SHORT is the same reduction with sigma = -1 applied to each member first.
  EXPECT_DOUBLE_EQ(group.mechanism(Side::SHORT, 0).value, -4.0);
  EXPECT_TRUE(group.all_four_present(Side::LONG));
  EXPECT_EQ(group.token_count, 2);
  EXPECT_DOUBLE_EQ(group.log1p_multiplicity, std::log1p(2.0));
}

TEST(EqualMillisecondPermutation, NbboAndOptionGroupsAreAlsoBitIdenticalUnderPermutation) {
  const auto nbbo_run = [](bool reversed) {
    NbboStream stream(clock_125());
    EXPECT_TRUE(stream
                    .push_group(open_ms() + 1'000,
                                testing::rows_of<qr::sources::StockQuoteRow>({quote_row(
                                    open_ms() + 1'000, 99'990'000, 100'010'000, 500, 700)}))
                    .has_value());
    const auto a = quote_row(open_ms() + 2'000, 100'000'000, 100'020'000, 200, 100);
    const auto b = quote_row(open_ms() + 2'000, 100'010'000, 100'030'000, 200, 500);
    const auto group = reversed ? testing::rows_of<qr::sources::StockQuoteRow>({b, a})
                                : testing::rows_of<qr::sources::StockQuoteRow>({a, b});
    EXPECT_TRUE(stream.push_group(open_ms() + 2'000, group).has_value());
    std::vector<std::uint8_t> bytes;
    for (const GroupRecord& record : stream.groups()) {
      const auto serialized = serialize(record);
      bytes.insert(bytes.end(), serialized.begin(), serialized.end());
    }
    return bytes;
  };
  EXPECT_EQ(nbbo_run(false), nbbo_run(true));

  const auto option_run = [](bool reversed) {
    OptionPrintStream stream(clock_125());
    const auto a = option_row(open_ms() + 3'000, 1'800'000, 5, qr::sources::Right::Call,
                              180'000'000, 19'243, open_ms() + 2'000, 1'700'000, 1'900'000,
                              "2022-07-05T09:30:02.000", 180.0, 1);
    const auto b = option_row(open_ms() + 3'000, 1'850'000, 7, qr::sources::Right::Put,
                              180'000'000, 19'243, open_ms() + 2'500, 1'750'000, 1'950'000,
                              "2022-07-05T09:30:02.500", 180.25, 2);
    const auto group = reversed ? testing::rows_of<qr::sources::OptionPrintRow>({b, a})
                                : testing::rows_of<qr::sources::OptionPrintRow>({a, b});
    EXPECT_TRUE(stream.push_group(open_ms() + 3'000, group).has_value());
    std::vector<std::uint8_t> bytes;
    for (const GroupRecord& record : stream.groups()) {
      const auto serialized = serialize(record);
      bytes.insert(bytes.end(), serialized.begin(), serialized.end());
    }
    // The prior states the permuted group left behind must match too.
    const PriorScalar underlying = stream.underlying_prior().prior();
    bytes.push_back(underlying.present ? 1U : 0U);
    for (unsigned shift = 0; shift < 64; shift += 8) {
      bytes.push_back(static_cast<std::uint8_t>(
          (static_cast<std::uint64_t>(underlying.mean) >> shift) & 0xFFU));
    }
    return bytes;
  };
  EXPECT_EQ(option_run(false), option_run(true));
}

// ---------------------------------------------------------------------------
// The NBBO channel list.
// ---------------------------------------------------------------------------

TEST(NbboChannels, TheSixteenChannelsAreTheCardsSixteenValues) {
  NbboStream stream(clock_125());
  ASSERT_TRUE(stream
                  .push_group(open_ms() + 1'000,
                              testing::rows_of<qr::sources::StockQuoteRow>({quote_row(
                                  open_ms() + 1'000, 99'990'000, 100'010'000, 500, 700)}))
                  .has_value());

  NbboPriorMachine machine;
  machine.begin_group(frame_a_of(1'000));
  ASSERT_TRUE(machine.observe_eligible(99'990'000, 100'010'000, 500, 700));
  machine.commit_group();
  const NbboPrior prior = machine.prior();

  NbboScalars current;
  ASSERT_TRUE(current.bid_u6.add(100'000'000));
  ASSERT_TRUE(current.ask_u6.add(100'020'000));
  ASSERT_TRUE(current.bid_shares.add(200));
  ASSERT_TRUE(current.ask_shares.add(100));
  ASSERT_TRUE(current.bid_u6.add(100'010'000));
  ASSERT_TRUE(current.ask_u6.add(100'030'000));
  ASSERT_TRUE(current.bid_shares.add(200));
  ASSERT_TRUE(current.ask_shares.add(500));

  NbboGroupInputs inputs;
  inputs.group.ts_ns_a = frame_a_of(2'000);
  inputs.group.interarrival_micros = 1'000'000;  // 1'000ms
  inputs.group.same_ms = true;
  inputs.current = &current;
  inputs.prior = &prior;
  inputs.any_positive_two_sided = true;

  const auto built = build_nbbo_group_token(inputs, Side::LONG);
  ASSERT_TRUE(built.has_value());
  const auto& channels = built.value().channels;

  //  means: bid = 200'010'000/2 = 100'005'000, ask = 200'050'000/2 = 100'025'000
  //  mid   = 100'005'000 + (100'025'000-100'005'000)/2 = 100'015'000, spread = 20'000
  //  prior: bid 99'990'000, ask 100'010'000, mid 100'000'000, sizes 500/700
  EXPECT_NEAR(channels.value[kNbLogInterarrival], std::log1p(1'000'000.0), 1e-12);
  //  1  oriented midpoint change: 15'000*10'000/1e8 = 1.5e8/1e8 = 1.5 -> TRUNCATED 1
  EXPECT_DOUBLE_EQ(channels.value[kNbOrientedMidpointChange], 1.0);
  //  2  spread bps: 20'000*10'000/100'015'000 = 2e8/100'015'000 = 1.9997 -> 1
  EXPECT_DOUBLE_EQ(channels.value[kNbSpreadBps], 1.0);
  //  3  log own size: LONG own = ASK = (100+500)/2 = 300
  EXPECT_NEAR(channels.value[kNbLogOwnSize], std::log1p(300.0), 1e-15);
  //  4  log opposite size: BID = (200+200)/2 = 200
  EXPECT_NEAR(channels.value[kNbLogOppositeSize], std::log1p(200.0), 1e-15);
  //  5  oriented imbalance (CC-005): (200-300)/(200+300) = -100/500 = -0.2
  EXPECT_DOUBLE_EQ(channels.value[kNbOrientedImbalance], -0.2);
  //  6  own price change (ASK): 15'000*10'000/100'010'000 = 1.4998 -> 1
  EXPECT_DOUBLE_EQ(channels.value[kNbOwnPriceChange], 1.0);
  //  7  opposite price change (BID): 15'000*10'000/99'990'000 = 1.50015 -> 1
  EXPECT_DOUBLE_EQ(channels.value[kNbOppositePriceChange], 1.0);
  //  8  own signed size change (ASK): 300 - 700 = -400 -> -log1p(400)
  EXPECT_NEAR(channels.value[kNbOwnSignedSizeChange], -std::log1p(400.0), 1e-15);
  //  9  opposite signed size change (BID): 200 - 500 = -300 -> -log1p(300)
  EXPECT_NEAR(channels.value[kNbOppositeSignedSizeChange], -std::log1p(300.0), 1e-15);
  // 10..15
  EXPECT_DOUBLE_EQ(channels.value[kNbLocked], 0.0);
  EXPECT_DOUBLE_EQ(channels.value[kNbCrossed], 0.0);
  EXPECT_DOUBLE_EQ(channels.value[kNbPositiveTwoSided], 1.0);
  EXPECT_DOUBLE_EQ(channels.value[kNbBidChanged], 1.0);
  EXPECT_DOUBLE_EQ(channels.value[kNbAskChanged], 1.0);
  EXPECT_DOUBLE_EQ(channels.value[kNbSameMs], 1.0);
  for (std::size_t channel = 0; channel < kNbboChannelCount; ++channel) {
    EXPECT_TRUE(channels.presence(channel)) << nbbo_channel_name(channel);
  }
  // NBBO hangs on no attachment: the union indicator can never fire.
  EXPECT_FALSE(built.value().unusable_attachment);
}

TEST(NbboChannels, WithNoPriorEligibleGroupTheChangeChannelsAreMissingNotZero) {
  NbboScalars current;
  ASSERT_TRUE(current.bid_u6.add(100'000'000));
  ASSERT_TRUE(current.ask_u6.add(100'020'000));
  ASSERT_TRUE(current.bid_shares.add(200));
  ASSERT_TRUE(current.ask_shares.add(100));
  const NbboPrior absent_prior;

  NbboGroupInputs inputs;
  inputs.group.ts_ns_a = frame_a_of(2'000);
  inputs.current = &current;
  inputs.prior = &absent_prior;

  const auto built = build_nbbo_group_token(inputs, Side::LONG);
  ASSERT_TRUE(built.has_value());
  const auto& channels = built.value().channels;
  for (const std::size_t channel : {static_cast<std::size_t>(kNbOrientedMidpointChange),
                                    static_cast<std::size_t>(kNbOwnPriceChange),
                                    static_cast<std::size_t>(kNbOppositePriceChange),
                                    static_cast<std::size_t>(kNbOwnSignedSizeChange),
                                    static_cast<std::size_t>(kNbOppositeSignedSizeChange),
                                    static_cast<std::size_t>(kNbBidChanged),
                                    static_cast<std::size_t>(kNbAskChanged)}) {
    EXPECT_EQ(channels.validity[channel], Validity::MISSING) << nbbo_channel_name(channel);
    EXPECT_DOUBLE_EQ(channels.value[channel], 0.0);
  }
  // The current-group channels still resolve.
  EXPECT_TRUE(channels.presence(kNbSpreadBps));
  EXPECT_TRUE(channels.presence(kNbOrientedImbalance));
}

// ---------------------------------------------------------------------------
// The option-print channel list.
// ---------------------------------------------------------------------------

/// Session 125 is 2022-07-05; days since epoch 19'178. A +30-day expiry is
/// 19'208, so DTE = 30 exactly.
constexpr std::int32_t kExpiryPlus30 = 19'208;

OptionPrintTokenInputs option_inputs(qr::sources::Right right) {
  static qr::sources::OptionPrintRow row;
  row = option_row(open_ms() + 5'000, 2'050'000, 10, right, 180'000'000, kExpiryPlus30,
                   open_ms() + 4'000, 1'900'000, 2'100'000, "2022-07-05T09:30:04.000", 180.5, 3);
  OptionPrintTokenInputs inputs;
  inputs.row = &row;
  inputs.group.ts_ns_a = frame_a_of(5'000);
  inputs.group.interarrival_micros = 2'000'000;  // 5'000ms - 3'000ms
  inputs.directional_eligible = true;
  inputs.directional_validity = Validity::VALID;
  inputs.quote_attachment =
      classify_attachment_ms(clock_125(), open_ms() + 4'000, inputs.group.ts_ns_a);
  QuoteFields quote;
  quote.bid_u6 = 1'900'000;
  quote.ask_u6 = 2'100'000;
  quote.bid_size = 10;
  quote.ask_size = 20;
  inputs.quote_signing = quote_signing_validity(quote);
  inputs.underlying_attachment = classify_attachment_text(
      clock_125(), std::string_view("2022-07-05T09:30:04.000"), inputs.group.ts_ns_a);
  inputs.underlying_u6 = 180'500'000;
  inputs.contract_prior = PriorScalar{true, frame_a_of(3'000), 1'800'000};
  inputs.underlying_prior = PriorScalar{true, frame_a_of(2'000), 180'000'000};
  inputs.dte_present = true;
  inputs.dte_days = 30;
  return inputs;
}

TEST(OptionPrintChannels, TheTwentyTwoChannelsAreTheCardsTwentyTwoValues) {
  const OptionPrintTokenInputs inputs = option_inputs(qr::sources::Right::Call);
  ASSERT_TRUE(inputs.quote_attachment.usable());
  ASSERT_TRUE(inputs.underlying_attachment.usable());
  ASSERT_EQ(inputs.quote_signing, Validity::VALID);

  const auto built = build_option_print_token(inputs, Side::LONG);
  ASSERT_TRUE(built.has_value());
  const auto& channels = built.value().channels;

  //  0 log interarrival: 2'000'000us
  EXPECT_NEAR(channels.value[kOpLogInterarrival], std::log1p(2'000'000.0), 1e-12);
  //  1 oriented underlying return: (180'500'000-180'000'000)*10'000/180'000'000
  //      = 5e9/1.8e8 = 27.77... -> TRUNCATED 27
  EXPECT_DOUBLE_EQ(channels.value[kOpOrientedUnderlyingReturn], 27.0);
  //  2 oriented right direction = sigma*rho = (+1)*(+1) = +1
  EXPECT_DOUBLE_EQ(channels.value[kOpOrientedRightDirection], 1.0);
  //  3 oriented causal aggressor: 1'900'000 < 2'050'000 < 2'100'000, so the quote
  //      branch resolves neither side; the same-contract prior is 1'800'000 and
  //      2'050'000 > 1'800'000 -> v = +1; sigma*rho*v = +1
  EXPECT_DOUBLE_EQ(channels.value[kOpOrientedCausalAggressor], 1.0);
  //  4 log size: 10 contracts
  EXPECT_NEAR(channels.value[kOpLogSize], std::log1p(10.0), 1e-15);
  //  5 oriented signed premium flow: sigma*rho*v*size*price_u6
  //      = 1*1*1*10*2'050'000 = 20'500'000 -> sign*log1p(20'500'000)
  EXPECT_NEAR(channels.value[kOpOrientedSignedPremiumFlow], std::log1p(20'500'000.0), 1e-11);
  //  6 oriented print-minus-mid: mid = 1'900'000 + (2'100'000-1'900'000)/2 = 2'000'000;
  //      (2'050'000-2'000'000)*10'000/2'000'000 = 5e8/2e6 = 250 bps
  EXPECT_DOUBLE_EQ(channels.value[kOpOrientedPrintMinusMid], 250.0);
  //  7 spread bps: 200'000*10'000/2'000'000 = 2e9/2e6 = 1000 bps
  EXPECT_DOUBLE_EQ(channels.value[kOpSpreadBps], 1000.0);
  //  8..12 the raw Greeks and IV, untransformed, with sigma where declared
  EXPECT_DOUBLE_EQ(channels.value[kOpOrientedDelta], 0.5);
  EXPECT_DOUBLE_EQ(channels.value[kOpGamma], 0.25);
  EXPECT_DOUBLE_EQ(channels.value[kOpOrientedVanna], 0.125);
  EXPECT_DOUBLE_EQ(channels.value[kOpOrientedCharm], -0.0625);
  EXPECT_DOUBLE_EQ(channels.value[kOpImpliedVol], 0.2);
  // 13 log DTE: 30 calendar days
  EXPECT_NEAR(channels.value[kOpLogDte], std::log1p(30.0), 1e-15);
  // 14 oriented moneyness: sigma*rho*(180'500'000-180'000'000)*10'000/180'000'000 = 27
  EXPECT_DOUBLE_EQ(channels.value[kOpOrientedMoneyness], 27.0);
  // 15..18 the recomputed flows: v*size*greek, then sign*log1p
  EXPECT_NEAR(channels.value[kOpOrientedDeltaFlow], std::log1p(5.0), 1e-15);      // 1*10*0.5
  EXPECT_NEAR(channels.value[kOpGammaFlow], std::log1p(2.5), 1e-15);              // 1*10*0.25
  EXPECT_NEAR(channels.value[kOpOrientedVannaFlow], std::log1p(1.25), 1e-15);     // 1*10*0.125
  EXPECT_NEAR(channels.value[kOpOrientedCharmFlow], -std::log1p(0.625), 1e-15);   // 1*10*-0.0625
  // 19/20 the two attachment ages
  EXPECT_NEAR(channels.value[kOpLogQuoteAge], std::log1p(1'000'000.0), 1e-12);
  EXPECT_NEAR(channels.value[kOpLogUnderlyingAge], std::log1p(1'000'000.0), 1e-12);
  // 21 the quality bit
  EXPECT_DOUBLE_EQ(channels.value[kOpDirectionalEligible], 1.0);
  for (std::size_t channel = 0; channel < kOptionPrintChannelCount; ++channel) {
    EXPECT_TRUE(channels.presence(channel)) << option_print_channel_name(channel);
  }
  EXPECT_FALSE(built.value().unusable_attachment);
}

TEST(OptionPrintChannels, AFutureUnderlyingAttachmentMasksEveryGreekAndEveryFlow) {
  // "The 42 known future option attachments must therefore be masked, not
  // consumed": the underlying stamp is AFTER the print.
  OptionPrintTokenInputs inputs = option_inputs(qr::sources::Right::Call);
  inputs.underlying_attachment = classify_attachment_text(
      clock_125(), std::string_view("2022-07-05T09:30:06.000"), inputs.group.ts_ns_a);
  ASSERT_EQ(inputs.underlying_attachment.state, AttachState::ATTACHMENT_FUTURE);

  const auto built = build_option_print_token(inputs, Side::LONG);
  ASSERT_TRUE(built.has_value());
  const auto& channels = built.value().channels;
  for (const std::size_t channel :
       {static_cast<std::size_t>(kOpOrientedDelta), static_cast<std::size_t>(kOpGamma),
        static_cast<std::size_t>(kOpOrientedVanna), static_cast<std::size_t>(kOpOrientedCharm),
        static_cast<std::size_t>(kOpImpliedVol), static_cast<std::size_t>(kOpOrientedDeltaFlow),
        static_cast<std::size_t>(kOpGammaFlow), static_cast<std::size_t>(kOpOrientedVannaFlow),
        static_cast<std::size_t>(kOpOrientedCharmFlow),
        static_cast<std::size_t>(kOpOrientedUnderlyingReturn),
        static_cast<std::size_t>(kOpOrientedMoneyness),
        static_cast<std::size_t>(kOpLogUnderlyingAge)}) {
    EXPECT_EQ(channels.validity[channel], Validity::ATTACHMENT_FUTURE)
        << option_print_channel_name(channel);
    EXPECT_DOUBLE_EQ(channels.value[channel], 0.0);
  }
  // The print REMAINS, and its quote-only and print-native channels survive.
  EXPECT_TRUE(channels.presence(kOpSpreadBps));
  EXPECT_TRUE(channels.presence(kOpOrientedPrintMinusMid));
  EXPECT_TRUE(channels.presence(kOpLogDte));
  EXPECT_TRUE(channels.presence(kOpLogSize));
  EXPECT_TRUE(built.value().unusable_attachment);
}

TEST(OptionPrintChannels, AMultilegPrintIsRetainedWithItsTypedReasonAndNoDirectionalValue) {
  OptionPrintTokenInputs inputs = option_inputs(qr::sources::Right::Call);
  inputs.directional_eligible = false;
  inputs.directional_validity = Validity::CONDITION_INELIGIBLE;

  const auto built = build_option_print_token(inputs, Side::LONG);
  ASSERT_TRUE(built.has_value());
  const auto& channels = built.value().channels;
  EXPECT_EQ(channels.validity[kOpOrientedCausalAggressor], Validity::CONDITION_INELIGIBLE);
  EXPECT_EQ(channels.validity[kOpOrientedSignedPremiumFlow], Validity::CONDITION_INELIGIBLE);
  EXPECT_EQ(channels.validity[kOpOrientedDeltaFlow], Validity::CONDITION_INELIGIBLE);
  EXPECT_DOUBLE_EQ(channels.value[kOpDirectionalEligible], 0.0);
  // Raw counts and the nondirectional context survive: "All option prints remain
  // as nondirectional context."
  EXPECT_TRUE(channels.presence(kOpLogSize));
  EXPECT_TRUE(channels.presence(kOpSpreadBps));
  EXPECT_TRUE(channels.presence(kOpOrientedDelta));
}

// ---------------------------------------------------------------------------
// THE ORIENTATION REFLECTION CONTROL.
// ---------------------------------------------------------------------------

/// Asserts the reflection law channel by channel, straight off the declared
/// orientation tables: a SIGMA/SIGMA_RHO channel negates, an OWN_OPPOSITE_SWAP
/// channel takes its partner's value, and an INVARIANT channel does not move.
template <std::size_t N>
void expect_reflection(const ChannelRow<N>& long_row, const ChannelRow<N>& short_row,
                       const std::array<OrientKind, N>& orientation,
                       std::size_t (*partner)(std::size_t), const char* (*name)(std::size_t)) {
  for (std::size_t channel = 0; channel < N; ++channel) {
    // Masks and quality "remain unchanged" under reflection, always.
    EXPECT_EQ(long_row.validity[channel], short_row.validity[channel]) << name(channel);
    switch (orientation[channel]) {
      case OrientKind::INVARIANT:
        EXPECT_DOUBLE_EQ(short_row.value[channel], long_row.value[channel]) << name(channel);
        break;
      case OrientKind::SIGMA:
      case OrientKind::SIGMA_RHO:
        EXPECT_DOUBLE_EQ(short_row.value[channel], -long_row.value[channel]) << name(channel);
        break;
      case OrientKind::OWN_OPPOSITE_SWAP:
        EXPECT_DOUBLE_EQ(short_row.value[channel], long_row.value[partner(channel)])
            << name(channel);
        break;
    }
  }
}

TEST(OrientationReflection, StockPrintReflectionMovesExactlyTheDeclaredChannels) {
  StockPrintTokenInputs inputs;
  const qr::sources::StockTradeRow row = print_p1();
  inputs.row = &row;
  inputs.group.ts_ns_a = frame_a_of(10'000);
  inputs.group.interarrival_micros = 2'000'000;
  inputs.group.same_ms = true;
  inputs.group.sequence = SequenceVerdict{true, true, 5, true, false};
  inputs.eligibility = classify_stock_print(row);
  inputs.quote_attachment =
      classify_attachment_ms(clock_125(), open_ms() + 9'000, inputs.group.ts_ns_a);
  QuoteFields quote;
  quote.bid_u6 = 99'990'000;
  quote.ask_u6 = 100'010'000;
  quote.bid_size = 500;
  quote.ask_size = 700;
  quote.bid_condition = 0;
  quote.ask_condition = 0;
  inputs.quote_signing = quote_signing_validity(quote);
  inputs.price_prior = PriorScalar{true, frame_a_of(8'000), kPriorPrice};

  const auto long_row = build_stock_print_token(inputs, Side::LONG);
  const auto short_row = build_stock_print_token(inputs, Side::SHORT);
  ASSERT_TRUE(long_row.has_value());
  ASSERT_TRUE(short_row.has_value());
  expect_reflection(long_row.value().channels, short_row.value().channels, kStockPrintOrientation,
                    &stock_print_swap_partner, &stock_print_channel_name);
  // Spot literals so the table itself cannot be quietly wrong:
  //   the return is +3 LONG and -3 SHORT; own size is the ASK (700) LONG and the
  //   BID (500) SHORT; the spread is 2 bps on both sides.
  EXPECT_DOUBLE_EQ(short_row.value().channels.value[kSpOrientedPrintReturn], -3.0);
  EXPECT_NEAR(short_row.value().channels.value[kSpLogOwnAttachedSize], std::log1p(500.0), 1e-15);
  EXPECT_DOUBLE_EQ(short_row.value().channels.value[kSpSpreadBps], 2.0);
}

TEST(OrientationReflection, NbboReflectionMovesExactlyTheDeclaredChannels) {
  NbboScalars current;
  ASSERT_TRUE(current.bid_u6.add(100'005'000));
  ASSERT_TRUE(current.ask_u6.add(100'025'000));
  ASSERT_TRUE(current.bid_shares.add(200));
  ASSERT_TRUE(current.ask_shares.add(300));
  NbboPrior prior;
  prior.present = true;
  prior.ts_ns_a = frame_a_of(1'000);
  ASSERT_TRUE(prior.scalars.bid_u6.add(99'990'000));
  ASSERT_TRUE(prior.scalars.ask_u6.add(100'010'000));
  ASSERT_TRUE(prior.scalars.bid_shares.add(500));
  ASSERT_TRUE(prior.scalars.ask_shares.add(700));

  NbboGroupInputs inputs;
  inputs.group.ts_ns_a = frame_a_of(2'000);
  inputs.group.interarrival_micros = 1'000'000;
  inputs.current = &current;
  inputs.prior = &prior;
  inputs.any_positive_two_sided = true;

  const auto long_row = build_nbbo_group_token(inputs, Side::LONG);
  const auto short_row = build_nbbo_group_token(inputs, Side::SHORT);
  ASSERT_TRUE(long_row.has_value());
  ASSERT_TRUE(short_row.has_value());
  expect_reflection(long_row.value().channels, short_row.value().channels, kNbboOrientation,
                    &nbbo_swap_partner, &nbbo_channel_name);
  // The imbalance is CC-005's bid-minus-ask, sigma-oriented:
  //   (200-300)/500 = -0.2 LONG, +0.2 SHORT.
  EXPECT_DOUBLE_EQ(long_row.value().channels.value[kNbOrientedImbalance], -0.2);
  EXPECT_DOUBLE_EQ(short_row.value().channels.value[kNbOrientedImbalance], 0.2);
}

TEST(OrientationReflection, OptionReflectionMovesExactlyTheDeclaredChannelsAndGammaIsInvariant) {
  const OptionPrintTokenInputs inputs = option_inputs(qr::sources::Right::Call);
  const auto long_row = build_option_print_token(inputs, Side::LONG);
  const auto short_row = build_option_print_token(inputs, Side::SHORT);
  ASSERT_TRUE(long_row.has_value());
  ASSERT_TRUE(short_row.has_value());
  expect_reflection(long_row.value().channels, short_row.value().channels,
                    kOptionPrintOrientation, [](std::size_t channel) { return channel; },
                    &option_print_channel_name);
  // GAMMA AND GAMMA-FLOW ARE SIDE-INVARIANT, by name, and they are the only two
  // Greek columns that are.
  EXPECT_DOUBLE_EQ(short_row.value().channels.value[kOpGamma], 0.25);
  EXPECT_NEAR(short_row.value().channels.value[kOpGammaFlow], std::log1p(2.5), 1e-15);
  EXPECT_DOUBLE_EQ(short_row.value().channels.value[kOpOrientedDelta], -0.5);
  EXPECT_DOUBLE_EQ(short_row.value().channels.value[kOpOrientedRightDirection], -1.0);
}

TEST(OrientationReflection, RhoFlipsExactlyTheSigmaRhoChannelsAndLeavesTheSigmaOnesAlone) {
  const auto call = build_option_print_token(option_inputs(qr::sources::Right::Call), Side::LONG);
  const auto put = build_option_print_token(option_inputs(qr::sources::Right::Put), Side::LONG);
  ASSERT_TRUE(call.has_value());
  ASSERT_TRUE(put.has_value());
  for (std::size_t channel = 0; channel < kOptionPrintChannelCount; ++channel) {
    const double call_value = call.value().channels.value[channel];
    const double put_value = put.value().channels.value[channel];
    if (kOptionPrintOrientation[channel] == OrientKind::SIGMA_RHO) {
      EXPECT_DOUBLE_EQ(put_value, -call_value) << option_print_channel_name(channel);
    } else {
      EXPECT_DOUBLE_EQ(put_value, call_value) << option_print_channel_name(channel);
    }
  }
  // A right the vendor wrote as neither call nor put leaves rho undefined, and
  // every sigma*rho channel is MASKED rather than folded into one of them.
  const auto other = build_option_print_token(option_inputs(qr::sources::Right::Other),
                                              Side::LONG);
  ASSERT_TRUE(other.has_value());
  for (std::size_t channel = 0; channel < kOptionPrintChannelCount; ++channel) {
    if (kOptionPrintOrientation[channel] == OrientKind::SIGMA_RHO) {
      EXPECT_FALSE(other.value().channels.presence(channel))
          << option_print_channel_name(channel);
    }
  }
  EXPECT_TRUE(other.value().channels.presence(kOpGamma));
}

// ---------------------------------------------------------------------------
// The attachment and condition contracts.
// ---------------------------------------------------------------------------

TEST(AttachmentLaw, TheFiveNonUsableStatesAreDistinctAndCarryTheirOwnValidity) {
  const std::int64_t print_ts = frame_a_of(10'000);
  EXPECT_EQ(classify_attachment_ms(clock_125(), std::nullopt, print_ts).state,
            AttachState::ATTACHMENT_MISSING);
  EXPECT_EQ(classify_attachment_ms(clock_125(), open_ms() + 10'000, print_ts).state,
            AttachState::EQUAL_TIME_UNORDERED);
  EXPECT_EQ(classify_attachment_ms(clock_125(), open_ms() + 10'001, print_ts).state,
            AttachState::ATTACHMENT_FUTURE);
  EXPECT_EQ(classify_attachment_ms(clock_125(), open_ms() + 9'999, print_ts).state,
            AttachState::USABLE);
  // One civil day earlier: WRONG_CIVIL_DAY with its exact signed delta.
  const Attachment wrong_day =
      classify_attachment_ms(clock_125(), open_ms() - kMillisecondsPerDay, print_ts);
  EXPECT_EQ(wrong_day.state, AttachState::ATTACHMENT_WRONG_DAY);
  EXPECT_EQ(wrong_day.delta_days, -1);

  EXPECT_EQ(attach_validity(AttachState::USABLE), Validity::VALID);
  EXPECT_EQ(attach_validity(AttachState::ATTACHMENT_MISSING), Validity::MISSING);
  EXPECT_EQ(attach_validity(AttachState::EQUAL_TIME_UNORDERED), Validity::EQUAL_TIME_UNORDERED);
  EXPECT_EQ(attach_validity(AttachState::ATTACHMENT_FUTURE), Validity::ATTACHMENT_FUTURE);
  EXPECT_EQ(attach_validity(AttachState::ATTACHMENT_WRONG_DAY), Validity::WRONG_CIVIL_DAY);
  EXPECT_EQ(attach_validity(AttachState::ATTACHMENT_MALFORMED), Validity::MALFORMED);
}

TEST(AttachmentLaw, TheUnderlyingTimestampTextParseIsExactFormAndMalformedOtherwise) {
  // The measured compact-profile shape, and only it.
  EXPECT_TRUE(parse_naive_et_iso_ms("2022-07-05T09:30:00.000").has_value());
  // 2022-07-05 is day 19'178 since the epoch; 09:30:00.000 is 34'200'000 ms.
  EXPECT_EQ(*parse_naive_et_iso_ms("2022-07-05T09:30:00.000"),
            19'178LL * 86'400'000LL + 34'200'000LL);
  // Everything else is MALFORMED — never MISSING, never a substituted instant.
  for (const char* bad : {"2022-07-05T09:30:00", "2022-07-05T09:30:00.000Z",
                          "2022-07-05 09:30:00.000", "2022-13-05T09:30:00.000",
                          "2022-07-05T24:00:00.000", "2022-07-05T09:60:00.000", ""}) {
    EXPECT_FALSE(parse_naive_et_iso_ms(bad).has_value()) << bad;
  }
  const std::int64_t print_ts = frame_a_of(10'000);
  EXPECT_EQ(classify_attachment_text(clock_125(), std::string_view("nonsense"), print_ts).state,
            AttachState::ATTACHMENT_MALFORMED);
  EXPECT_EQ(classify_attachment_text(clock_125(), std::nullopt, print_ts).state,
            AttachState::ATTACHMENT_MISSING);
}

TEST(SigningLaw, EveryDisqualifyingShapeKeepsItsOwnTypedQualityToken) {
  const auto build = [](std::optional<std::int64_t> bid, std::optional<std::int64_t> ask,
                        std::optional<std::int64_t> bid_condition) {
    QuoteFields quote;
    quote.bid_u6 = bid;
    quote.ask_u6 = ask;
    quote.bid_size = 100;
    quote.ask_size = 100;
    quote.bid_condition = bid_condition;
    quote.ask_condition = 0;
    return quote_signing_validity(quote);
  };
  EXPECT_EQ(build(100, 104, 0), Validity::VALID);
  EXPECT_EQ(build(104, 104, 0), Validity::LOCKED);     // bid == ask
  EXPECT_EQ(build(105, 104, 0), Validity::CROSSED);    // bid > ask
  EXPECT_EQ(build(100, std::nullopt, 0), Validity::ONE_SIDED);
  EXPECT_EQ(build(std::nullopt, std::nullopt, 0), Validity::MISSING);
  EXPECT_EQ(build(0, 104, 0), Validity::NONPOSITIVE);
  EXPECT_EQ(build(100, 104, 7), Validity::CONDITION_INELIGIBLE);
}

TEST(StockConditionContract, ThePrimaryExtendedAndSentinelClausesAreAllEnforced) {
  qr::sources::StockTradeRow row =
      trade_row(open_ms() + 1'000, 100'000'000, 100, open_ms() + 500, 99'990'000, 100'010'000,
                100, 100);
  EXPECT_TRUE(classify_stock_print(row).direction_eligible);
  EXPECT_EQ(classify_stock_print(row).primary, TradeConditionClass::REGULAR);
  EXPECT_TRUE(classify_stock_print(row).sentinel_absent);

  // types 40..44 are CANCEL: recognized, counted, and NOT direction-eligible.
  for (const std::int64_t code : {40, 41, 42, 43, 44}) {
    row.condition = code;
    const auto verdict = classify_stock_print(row);
    EXPECT_EQ(verdict.primary, TradeConditionClass::CANCEL) << code;
    EXPECT_FALSE(verdict.direction_eligible) << code;
    EXPECT_TRUE(verdict.primary_nonzero) << code;
  }
  row.condition = 39;
  EXPECT_EQ(classify_stock_print(row).primary, TradeConditionClass::INELIGIBLE);
  row.condition = 45;
  EXPECT_EQ(classify_stock_print(row).primary, TradeConditionClass::INELIGIBLE);

  // "each of four extended-condition slots is absent only at sentinel255,
  // otherwise it too must be code0".
  row.condition = 0;
  row.ext_condition = {0, 255, 255, 255};
  EXPECT_TRUE(classify_stock_print(row).direction_eligible);
  row.ext_condition = {0, 255, 12, 255};
  EXPECT_FALSE(classify_stock_print(row).direction_eligible);
  EXPECT_TRUE(classify_stock_print(row).extended_nonzero);

  row.ext_condition = {255, 255, 255, 255};
  row.size = 0;
  EXPECT_FALSE(classify_stock_print(row).direction_eligible);
  EXPECT_TRUE(classify_stock_print(row).nonpositive_size);
  row.size = 100;
  row.price_u6 = 0;
  EXPECT_FALSE(classify_stock_print(row).direction_eligible);
  EXPECT_TRUE(classify_stock_print(row).nonfinite_price);
}

// ---------------------------------------------------------------------------
// CC-008: the admitted extended-condition vocabulary is {0, 32}, the sentinel
// stays {255}, and the conjunction is RETAINED.
// ---------------------------------------------------------------------------

qr::sources::StockTradeRow print_with(std::int64_t primary,
                                      std::array<std::int64_t, 4> extended) {
  qr::sources::StockTradeRow row =
      trade_row(open_ms() + 1'000, 100'000'000, 100, open_ms() + 500, 99'990'000, 100'010'000,
                100, 100);
  row.condition = primary;
  row.ext_condition = extended;
  return row;
}

TEST(Cc008ExtendedVocabulary, ARegularPrintWhoseListSpellsRegularAs32IsELIGIBLE) {
  // The shape 598,255 real prints carry: primary 0 with slot 1 == 32 and the
  // other three slots at the 255 sentinel.
  const auto verdict = classify_stock_print(print_with(0, {32, 255, 255, 255}));
  EXPECT_TRUE(verdict.direction_eligible);
  EXPECT_FALSE(verdict.extended_nonzero);
  EXPECT_TRUE(verdict.sentinel_absent);
  EXPECT_EQ(verdict.directional_validity, Validity::VALID);
  // The bare 0 spelling is admitted too — the vocabulary is {0, 32}, not {32}.
  EXPECT_TRUE(classify_stock_print(print_with(0, {0, 255, 255, 255})).direction_eligible);
  EXPECT_TRUE(classify_stock_print(print_with(0, {255, 255, 255, 255})).direction_eligible);
}

TEST(Cc008ExtendedVocabulary, ARegularPrintCARRYINGAREALEXTENDEDCODEStaysINELIGIBLE) {
  // THE FAIL-CLOSED CASE, and the reason the conjunction is retained rather than
  // deleted: a primary-0 print with a real sale condition in its list (95 is the
  // corpus's most common one) is refused. The corpus has never produced this
  // row — the clause exists to refuse it if it ever does.
  const auto verdict = classify_stock_print(print_with(0, {32, 95, 255, 255}));
  EXPECT_FALSE(verdict.direction_eligible);
  EXPECT_TRUE(verdict.extended_nonzero);
  EXPECT_EQ(verdict.directional_validity, Validity::CONDITION_INELIGIBLE);
  // Every real code the three sessions carry disqualifies, in every slot.
  for (const std::int64_t code : {1, 2, 4, 8, 9, 11, 62, 66, 95, 96, 108, 115, 124}) {
    EXPECT_FALSE(classify_stock_print(print_with(0, {32, code, 255, 255})).direction_eligible)
        << code;
    EXPECT_FALSE(classify_stock_print(print_with(0, {32, 255, 255, code})).direction_eligible)
        << code;
  }
}

TEST(Cc008ExtendedVocabulary, ANonRegularPrimaryIsINELIGIBLEWhateverItsExtendedSlotsSay) {
  EXPECT_FALSE(classify_stock_print(print_with(4, {255, 255, 255, 255})).direction_eligible);
  EXPECT_FALSE(classify_stock_print(print_with(4, {32, 255, 255, 255})).direction_eligible);
  EXPECT_FALSE(classify_stock_print(print_with(95, {255, 95, 255, 115})).direction_eligible);
  // A CANCEL type is recognized and still refused.
  const auto cancel = classify_stock_print(print_with(41, {255, 255, 255, 255}));
  EXPECT_EQ(cancel.primary, TradeConditionClass::CANCEL);
  EXPECT_FALSE(cancel.direction_eligible);
}

/// Reads one pinned census TSV into `section\tmetric -> value`.
std::map<std::string, std::int64_t> pinned_census(const std::string& session) {
  const std::string path =
      std::string(QR_CARRIERS_FIXTURE_DIR) + "/carriers_conditions_session" + session + ".tsv";
  std::ifstream input(path);
  EXPECT_TRUE(input.good()) << "missing pinned census " << path;
  std::map<std::string, std::int64_t> out;
  std::string line;
  bool header = true;
  while (std::getline(input, line)) {
    if (header) {
      header = false;
      continue;
    }
    const std::size_t first = line.find('\t');
    const std::size_t second = line.find('\t', first + 1);
    if (first == std::string::npos || second == std::string::npos) {
      continue;
    }
    const std::string key = line.substr(0, second);
    const std::string value = line.substr(second + 1);
    if (!value.empty() && (std::isdigit(static_cast<unsigned char>(value[0])) != 0 ||
                           value[0] == '-')) {
      out[key] = std::strtoll(value.c_str(), nullptr, 10);
    }
  }
  return out;
}

TEST(Cc008CensusPin, TheBiconditionalThatGroundsTheRulingHoldsOnAllThreePinnedSessions) {
  // THE MEASUREMENT CC-008 RESTS ON, kept executable rather than quoted: on each
  // pinned session `ext1 == 32` IFF `primary == 0`, with no exceptions.
  for (const char* session : {"125", "500", "625"}) {
    const auto census = pinned_census(session);
    ASSERT_FALSE(census.empty()) << session;
    const auto primary_zero = census.find("codes.stock_print_primary\t0");
    const auto ext1_32 = census.find("codes.stock_print_ext1\t32");
    const auto crosstab = census.find("crosstab.ext1_x_primary\t32_x_0");
    ASSERT_NE(primary_zero, census.end()) << session;
    ASSERT_NE(ext1_32, census.end()) << session;
    ASSERT_NE(crosstab, census.end()) << session;
    // Every primary-0 print has ext1 == 32, and every ext1 == 32 print has
    // primary 0: all three counts are the same number.
    EXPECT_EQ(ext1_32->second, primary_zero->second) << session;
    EXPECT_EQ(crosstab->second, primary_zero->second) << session;
    // ... and that number is the eligible count under CC-008.
    const auto eligible = census.find("quality.stock_print\teligible");
    ASSERT_NE(eligible, census.end()) << session;
    EXPECT_EQ(eligible->second, primary_zero->second) << session;

    // 32 is a SLOT-1 value, never a filler: it appears in no other slot.
    for (const char* slot : {"2", "3", "4"}) {
      EXPECT_EQ(census.count(std::string("codes.stock_print_ext") + slot + "\t32"), 0U)
          << session << " slot " << slot;
    }
    // 255 is the real absence sentinel, in every slot, on every session.
    for (const char* slot : {"1", "2", "3", "4"}) {
      EXPECT_EQ(census.count(std::string("codes.stock_print_ext") + slot + "\t255"), 1U)
          << session << " slot " << slot;
    }

    // THE PIN AND THE PRODUCTION CONTRACT MUST AGREE, or the census is
    // decoration: the classifier admits exactly the slot-1 code the pin says is
    // the regular spelling, and refuses the other slot-1 codes the pin records.
    EXPECT_TRUE(is_extended_condition_admitted(32)) << session;
    EXPECT_TRUE(classify_stock_print(print_with(0, {32, 255, 255, 255})).direction_eligible)
        << session;
    for (const std::int64_t other : {9, 11}) {
      if (census.count(std::string("codes.stock_print_ext1\t") + std::to_string(other)) == 0U) {
        continue;
      }
      EXPECT_FALSE(is_extended_condition_admitted(other)) << session << " code " << other;
      EXPECT_FALSE(classify_stock_print(print_with(0, {other, 255, 255, 255})).direction_eligible)
          << session << " code " << other;
    }
  }
}

TEST(Cc008CensusPin, TheEligibleCountIsTheOneTheGateReportsForSessionOneTwentyFive) {
  const auto census = pinned_census("125");
  EXPECT_EQ(census.at("quality.stock_print\ttotal"), 192'540);
  EXPECT_EQ(census.at("quality.stock_print\teligible"), 45'169);
  EXPECT_EQ(census.at("codes.stock_print_ext1\t32"), 45'169);
  EXPECT_EQ(census.at("codes.stock_print_ext1\t255"), 147'359);
  // The counterfactual the ruling turned on: the old bare-0 vocabulary admitted
  // nothing at all on this session.
  EXPECT_EQ(census.at("sentinel_counterfactual\teligible_if_sentinels_are_255"), 0);

  // The pinned arithmetic and the production classifier are one claim: every
  // print is either eligible or primary-nonzero, and the two dominant real row
  // shapes classify the way the pin's split requires.
  EXPECT_EQ(census.at("quality.stock_print\teligible") +
                census.at("quality.stock_print\tprimary_nonzero"),
            census.at("quality.stock_print\ttotal"));
  EXPECT_TRUE(classify_stock_print(print_with(0, {32, 255, 255, 255})).direction_eligible);
  EXPECT_FALSE(classify_stock_print(print_with(115, {255, 95, 255, 115})).direction_eligible);
}

}  // namespace
}  // namespace qr::carriers
