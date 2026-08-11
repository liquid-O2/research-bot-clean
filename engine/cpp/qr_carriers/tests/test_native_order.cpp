// test_native_order.cpp — WP8b: the reduced equal-time group vectors, the
// 128-group micro carrier, the 120-bin full carrier, the section-7 destructions
// that live in the same constructors, and the APPENDIX C4 leaves.
//
// SPEC: task card V4 section 4 (`NATIVE_ORDER`), section 5 (the 69/65/89
// arithmetic) and section 7 (e)/(f) + the production-constructor mutants, all
// quoted in native_order.hpp and group_vector.hpp.
//
// EVERY EXPECTED VALUE IS A HAND LITERAL WITH ITS ARITHMETIC IN A COMMENT, and
// no expected value is produced by calling the function under test.
#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

#include "carriers_test_support.hpp"
#include "destruction_guard.hpp"
#include "qr_carriers/direct_raw.hpp"
#include "qr_carriers/native_emit.hpp"
#include "qr_carriers/native_order.hpp"

namespace qr::carriers {
namespace {

using testing::clock_125;
using testing::frame_a_of;
using testing::open_ms;
using testing::option_row;
using testing::quote_row;
using testing::rows_of;
using testing::trade_row;

StreamOptions with_vectors() {
  StreamOptions options;
  options.retain_group_vectors = true;
  // Every group also keeps its per-side reference rows: the fixtures compare the
  // side-neutral table against them, so the sample is the whole tape.
  options.side_spot_stride = 1;
  return options;
}

/// One group's reduced vector for `side`, derived from the stored side-neutral
/// table by the loader's own law.
template <std::size_t N>
std::array<float, N> oriented_row(Modality modality, const GroupVectorTable& neutral,
                                  std::size_t group, Side side) {
  std::array<float, N> out{};
  orient_group_vector(modality, neutral.row(group), side, out);
  return out;
}

DecisionWindow window_at(std::int64_t cutoff_ns_a, Side side = Side::LONG) {
  DecisionWindow window;
  window.cutoff_ns_a = cutoff_ns_a;
  window.session_open_ns_a = clock_125().session_start_a().ns();
  window.side = side;
  return window;
}

DecisionWindow window_with_visibility(std::int64_t cutoff_ns_a, std::int64_t visibility_ns_a,
                                      Side side = Side::LONG) {
  DecisionWindow window = window_at(cutoff_ns_a, side);
  window.phase_reference_present = true;
  window.phase_reference_ns_a = visibility_ns_a;
  return window;
}

/// A hand group record at a timestamp — for the carrier laws, which are laws
/// about ORDER and MEMBERSHIP and never look inside a group.
GroupRecord group_at(std::int64_t ts_ns_a, std::int32_t tokens = 1) {
  GroupRecord group;
  group.ts_ns_a = ts_ns_a;
  group.token_count = tokens;
  group.log1p_multiplicity = std::log1p(static_cast<double>(tokens));
  return group;
}

/// The three-print tape the group-vector fixtures read. Its first two groups are
/// the ones test_channels.cpp already pinned by hand:
///   @ open+8'000ms : one print, price 100'000'000 u6, size 100, seq 5
///   @ open+10'000ms: P1 price 100'030'000 size 300 (return +3bps, imbalance -1/6)
///                    P2 price 100'050'000 size 200 (return +5bps, imbalance -0.8)
///   @ open+12'000ms: P3 quote at 11'000ms (age 1'000'000us)
///                    P4 quote at 12'000ms (EQUAL_TIME: the age is masked)
std::vector<qr::sources::StockTradeRow> prior_group() {
  return rows_of<qr::sources::StockTradeRow>({trade_row(open_ms() + 8'000, 100'000'000, 100,
                                                        open_ms() + 7'000, 99'990'000,
                                                        100'010'000, 400, 400, 5)});
}
qr::sources::StockTradeRow print_p1() {
  return trade_row(open_ms() + 10'000, 100'030'000, 300, open_ms() + 9'000, 99'990'000,
                   100'010'000, 500, 700, 10);
}
qr::sources::StockTradeRow print_p2() {
  return trade_row(open_ms() + 10'000, 100'050'000, 200, open_ms() + 9'500, 100'010'000,
                   100'030'000, 100, 900, 12);
}
qr::sources::StockTradeRow print_p5() {
  // The THIRD member of the equal-millisecond group the permutation control
  // uses. Its size is 4 because the three log sizes
  //   log1p(300) = 5.70711026474888, log1p(200) = 5.303304908059076,
  //   log1p(4)   = 1.6094379124341003
  // do NOT sum associatively in IEEE-754 double: (a+b)+c = 12.61985308524205
  // while (c+b)+a = 12.619853085242053. A two-member group could never show
  // that — floating-point addition is commutative — so a two-member fixture
  // would pass a build that reduced in arrival order. This one cannot.
  return trade_row(open_ms() + 10'000, 100'040'000, 4, open_ms() + 9'200, 100'000'000,
                   100'020'000, 200, 300, 11);
}
qr::sources::StockTradeRow print_p3() {
  return trade_row(open_ms() + 12'000, 100'060'000, 400, open_ms() + 11'000, 100'040'000,
                   100'080'000, 300, 300, 20);
}
qr::sources::StockTradeRow print_p6() {
  // The third member of the LAST group, for the same reason print_p5 exists:
  // log1p(400) + log1p(5) + log1p(500) is order-dependent in double
  // (14.002326997619488 forwards, 14.00232699761949 reversed), so reversing the
  // group's row order is a real test of the canonical reduction and not a
  // restatement of the commutativity of `+`.
  return trade_row(open_ms() + 12'000, 100'065'000, 5, open_ms() + 11'500, 100'040'000,
                   100'080'000, 300, 300, 21);
}
qr::sources::StockTradeRow print_p4() {
  // Its attached quote carries the print's OWN timestamp: EQUAL_TIME_UNORDERED,
  // so every clock-dependent channel of this member is masked.
  return trade_row(open_ms() + 12'000, 100'070'000, 500, open_ms() + 12'000, 100'040'000,
                   100'080'000, 300, 300, 22);
}

StockPrintStream three_group_tape() {
  StockPrintStream stream(clock_125(), with_vectors());
  EXPECT_TRUE(stream.push_group(open_ms() + 8'000, prior_group()).has_value());
  EXPECT_TRUE(stream
                  .push_group(open_ms() + 10'000,
                              rows_of<qr::sources::StockTradeRow>({print_p1(), print_p2()}))
                  .has_value());
  EXPECT_TRUE(stream
                  .push_group(open_ms() + 12'000,
                              rows_of<qr::sources::StockTradeRow>({print_p3(), print_p4()}))
                  .has_value());
  return stream;
}

/// f4 is what the table stores and what C4 emits, so a hand literal is compared
/// after exactly one rounding — never with a tolerance.
float f4(double value) { return static_cast<float>(value); }

// ---------------------------------------------------------------------------
// 1. The reduced group vector: 69 / 65 / 89.
// ---------------------------------------------------------------------------

TEST(NativeGroupVector, TheThreeWidthsAndBlockOffsetsAreTheCardsOwnArithmetic) {
  // Section 5: "equal-time mean+max over 17 values+17 masks plus log
  // multiplicity is 69 inputs; NBBO's 16-value analog is 65 and option's
  // 22-value analog is 89".
  EXPECT_EQ(kStockPrintGroupDim, 69U);
  EXPECT_EQ(kNbboGroupDim, 65U);
  EXPECT_EQ(kOptionPrintGroupDim, 89U);
  EXPECT_EQ(group_vector_dim_of(Modality::STOCK_PRINT), 69U);
  EXPECT_EQ(group_vector_dim_of(Modality::STOCK_NBBO), 65U);
  EXPECT_EQ(group_vector_dim_of(Modality::OPTION_PRINT), 89U);

  // The four blocks tile the vector exactly once and the tail scalar closes it.
  EXPECT_EQ(group_mean_value_offset(kStockPrintChannelCount), 0U);
  EXPECT_EQ(group_mean_mask_offset(kStockPrintChannelCount), 17U);
  EXPECT_EQ(group_max_value_offset(kStockPrintChannelCount), 34U);
  EXPECT_EQ(group_max_mask_offset(kStockPrintChannelCount), 51U);
  EXPECT_EQ(group_log_multiplicity_offset(kStockPrintChannelCount), 68U);

  // Every component is named, and no name repeats.
  for (const Modality modality :
       {Modality::STOCK_PRINT, Modality::STOCK_NBBO, Modality::OPTION_PRINT}) {
    std::vector<std::string> names;
    for (std::size_t index = 0; index < group_vector_dim_of(modality); ++index) {
      names.push_back(group_vector_component_name(modality, index));
    }
    EXPECT_EQ(names.size(), group_vector_dim_of(modality));
    std::sort(names.begin(), names.end());
    EXPECT_EQ(std::unique(names.begin(), names.end()), names.end())
        << modality_name(modality) << " repeated a group-vector component name";
  }
  EXPECT_EQ(group_vector_component_name(Modality::STOCK_PRINT, 68), "LOG1P_GROUP_MULTIPLICITY");
}

TEST(NativeGroupVector, EqualTimeMembersReduceByFiniteMeanAndMaxWithLogMultiplicity) {
  const StockPrintStream stream = three_group_tape();
  const GroupVectorTable& table = stream.group_vectors();
  ASSERT_EQ(table.groups(), 3U);
  ASSERT_EQ(table.dim(), 74U);  // 69 + the 5 negating channels' min block
  // sigma = +1, so the stored table's first 69 cells ARE the LONG vector.
  const std::span<const float> reduced = table.row(1);  // the two-print group

  constexpr std::size_t kC = kStockPrintChannelCount;
  const std::size_t mean_value = group_mean_value_offset(kC);
  const std::size_t mean_mask = group_mean_mask_offset(kC);
  const std::size_t max_value = group_max_value_offset(kC);
  const std::size_t max_mask = group_max_mask_offset(kC);

  // Oriented print return: P1 = +3bps, P2 = +5bps -> mean 4, max 5.
  EXPECT_EQ(reduced[mean_value + kSpOrientedPrintReturn], f4(4.0));
  EXPECT_EQ(reduced[max_value + kSpOrientedPrintReturn], f4(5.0));
  EXPECT_EQ(reduced[mean_mask + kSpOrientedPrintReturn], f4(1.0));
  EXPECT_EQ(reduced[max_mask + kSpOrientedPrintReturn], f4(1.0));

  // Log size: log1p(300) and log1p(200) -> mean (log1p(300)+log1p(200))/2,
  // max log1p(300).
  EXPECT_EQ(reduced[mean_value + kSpLogSize], f4((std::log1p(300.0) + std::log1p(200.0)) / 2.0));
  EXPECT_EQ(reduced[max_value + kSpLogSize], f4(std::log1p(300.0)));

  // Oriented size imbalance: -1/6 and -0.8 -> mean (-1/6 + -0.8)/2, max -1/6.
  EXPECT_EQ(reduced[mean_value + kSpOrientedSizeImbalance],
            f4((-1.0 / 6.0 + -0.8) / 2.0));
  EXPECT_EQ(reduced[max_value + kSpOrientedSizeImbalance], f4(-1.0 / 6.0));

  // A structural bit reduces like any other channel: same-ms is 1 for both
  // members of a two-member group.
  EXPECT_EQ(reduced[mean_value + kSpSameMs], f4(1.0));
  EXPECT_EQ(reduced[max_value + kSpSameMs], f4(1.0));

  // "concatenate log group multiplicity": log1p(2).
  EXPECT_EQ(reduced[group_log_multiplicity_offset(kC)], f4(std::log1p(2.0)));

  // THE MAX IS A MAX, NOT A NEGATED MAX. SHORT's returns are -3 and -5, so its
  // mean is -4 and its max is -3 — a reflection of the LONG max (-5) would be
  // the wrong number and this is the assertion that catches it.
  const std::array<float, kStockPrintGroupDim> short_reduced =
      oriented_row<kStockPrintGroupDim>(Modality::STOCK_PRINT, table, 1, Side::SHORT);
  EXPECT_EQ(short_reduced[mean_value + kSpOrientedPrintReturn], f4(-4.0));
  EXPECT_EQ(short_reduced[max_value + kSpOrientedPrintReturn], f4(-3.0));
  // ... and the independently built per-side reduction says the same thing.
  EXPECT_EQ(stream.spot_side_vectors(Side::SHORT).row(1)[max_value + kSpOrientedPrintReturn],
            f4(-3.0));
}

TEST(NativeGroupVector, AChannelWithNoFinitePresentMemberEmitsValueZeroAndBothMasksZero) {
  // "zero such members emits value0/presence0. Max follows the same
  // eligibility." The FIRST group of the tape has no strictly-earlier group, so
  // its print return and its sequence gap have no member value at all.
  const StockPrintStream stream = three_group_tape();
  const std::span<const float> reduced = stream.group_vectors().row(0);
  constexpr std::size_t kC = kStockPrintChannelCount;
  for (const std::size_t channel :
       {static_cast<std::size_t>(kSpOrientedPrintReturn),
        static_cast<std::size_t>(kSpSequenceGapSignedLog)}) {
    EXPECT_EQ(reduced[group_mean_value_offset(kC) + channel], 0.0F);
    EXPECT_EQ(reduced[group_mean_mask_offset(kC) + channel], 0.0F);
    EXPECT_EQ(reduced[group_max_value_offset(kC) + channel], 0.0F);
    EXPECT_EQ(reduced[group_max_mask_offset(kC) + channel], 0.0F);
  }
  // A single-member group's multiplicity tail is log1p(1).
  EXPECT_EQ(reduced[group_log_multiplicity_offset(kC)], f4(std::log1p(1.0)));
}

TEST(NativeGroupVector, APartlyPresentChannelKeepsItsPresentFractionAndItsPresentValue) {
  // The third group's two members differ in ONE dependency: P3's attached quote
  // is 1'000ms earlier (age 1'000'000us) and P4's carries the print's own
  // timestamp (EQUAL_TIME_UNORDERED, so its age is masked). The mean and the max
  // therefore divide by ONE present member, and the two mask blocks disagree:
  // the mean of the presence bits is 1/2 and their max is 1.
  const StockPrintStream stream = three_group_tape();
  const std::span<const float> reduced = stream.group_vectors().row(2);
  constexpr std::size_t kC = kStockPrintChannelCount;
  EXPECT_EQ(reduced[group_mean_value_offset(kC) + kSpLogQuoteAge], f4(std::log1p(1'000'000.0)));
  EXPECT_EQ(reduced[group_max_value_offset(kC) + kSpLogQuoteAge], f4(std::log1p(1'000'000.0)));
  EXPECT_EQ(reduced[group_mean_mask_offset(kC) + kSpLogQuoteAge], f4(0.5));
  EXPECT_EQ(reduced[group_max_mask_offset(kC) + kSpLogQuoteAge], f4(1.0));
  // The quote-PRESENT structural bit is 1 for both members: the clock verdict
  // masks the age, not the existence of the attachment.
  EXPECT_EQ(reduced[group_mean_mask_offset(kC) + kSpQuotePresent], f4(1.0));
}

TEST(NativeGroupVector, ANbboGroupReducesToItsOwnGroupLevelVector) {
  // All sixteen NBBO channels are group-level by construction, so the equal-time
  // mean+max reduction of the group is that vector: mean == max for every
  // channel and the two mask blocks agree.
  NbboStream stream(clock_125(), with_vectors());
  ASSERT_TRUE(stream
                  .push_group(open_ms() + 1'000,
                              rows_of<qr::sources::StockQuoteRow>({quote_row(
                                  open_ms() + 1'000, 99'990'000, 100'010'000, 500, 700)}))
                  .has_value());
  ASSERT_TRUE(stream
                  .push_group(open_ms() + 2'000,
                              rows_of<qr::sources::StockQuoteRow>(
                                  {quote_row(open_ms() + 2'000, 100'000'000, 100'020'000, 200, 100),
                                   quote_row(open_ms() + 2'000, 100'010'000, 100'030'000, 200,
                                             500)}))
                  .has_value());

  const GroupVectorTable& table = stream.group_vectors();
  ASSERT_EQ(table.groups(), 2U);
  ASSERT_EQ(table.dim(), 67U);  // 65 + the 2 negating channels' min block
  constexpr std::size_t kC = kNbboChannelCount;
  const std::span<const float> reduced = table.row(1);
  for (std::size_t channel = 0; channel < kC; ++channel) {
    EXPECT_EQ(reduced[group_mean_value_offset(kC) + channel],
              reduced[group_max_value_offset(kC) + channel])
        << nbbo_channel_name(channel) << ": a group-level channel's mean and max must agree";
    EXPECT_EQ(reduced[group_mean_mask_offset(kC) + channel],
              reduced[group_max_mask_offset(kC) + channel]);
    const float mask = reduced[group_mean_mask_offset(kC) + channel];
    EXPECT_TRUE(mask == 0.0F || mask == 1.0F) << "a constant group's mask is 0 or 1, never 1/k";
  }
  // The FIRST group's own hand values: one eligible member, so its scalar means
  // are its own numbers. LONG's own queue is the ask: log1p(700).
  const std::span<const float> first = table.row(0);
  EXPECT_EQ(first[group_mean_value_offset(kC) + kNbLogOwnSize], f4(std::log1p(700.0)));
  EXPECT_EQ(first[group_max_value_offset(kC) + kNbLogOwnSize], f4(std::log1p(700.0)));
  EXPECT_EQ(first[group_mean_value_offset(kC) + kNbLogOppositeSize], f4(std::log1p(500.0)));
  // Two members -> log1p(2); one member -> log1p(1).
  EXPECT_EQ(reduced[group_log_multiplicity_offset(kC)], f4(std::log1p(2.0)));
  EXPECT_EQ(first[group_log_multiplicity_offset(kC)], f4(std::log1p(1.0)));
  // A constant group's MIN is its own value too, so the reflected max is the
  // negated value rather than the negated max of some other member.
  for (std::size_t slot = 0; slot < sigma_flip_channels(Modality::STOCK_NBBO).size(); ++slot) {
    const std::size_t channel = sigma_flip_channels(Modality::STOCK_NBBO)[slot];
    EXPECT_EQ(reduced[neutral_min_offset(kC) + slot],
              reduced[group_max_value_offset(kC) + channel]);
  }
}

TEST(NativeGroupVector, TheTableIsBuiltOnlyWhenTheConstructorControlAsksForIt) {
  // The reduction is a per-(session, side, modality) TABLE; a DIRECT-only run
  // must not pay for it. The control is on the constructor and defaults to off.
  StockPrintStream without(clock_125());
  ASSERT_TRUE(without.push_group(open_ms() + 8'000, prior_group()).has_value());
  EXPECT_EQ(without.groups().size(), 1U);
  EXPECT_EQ(without.group_vectors().groups(), 0U);
  EXPECT_EQ(without.spot_side_vectors(Side::LONG).groups(), 0U);

  StockPrintStream with(clock_125(), with_vectors());
  ASSERT_TRUE(with.push_group(open_ms() + 8'000, prior_group()).has_value());
  EXPECT_EQ(with.group_vectors().groups(), 1U);
  EXPECT_EQ(with.group_vectors().form(), GroupVectorTable::Form::NEUTRAL);
  // The per-side reference is its own control: off unless a stride asks for it.
  StreamOptions neutral_only;
  neutral_only.retain_group_vectors = true;
  StockPrintStream lean(clock_125(), neutral_only);
  ASSERT_TRUE(lean.push_group(open_ms() + 8'000, prior_group()).has_value());
  EXPECT_EQ(lean.group_vectors().groups(), 1U);
  EXPECT_EQ(lean.spot_side_vectors(Side::LONG).groups(), 0U);
  EXPECT_EQ(lean.spot_side_vectors(Side::SHORT).groups(), 0U);
  // Turning it on may not move a DIRECT-visible bit: the reduction READS the
  // token rows, it does not build them.
  ASSERT_EQ(without.groups().size(), with.groups().size());
  EXPECT_EQ(testing::serialize(without.groups()[0]), testing::serialize(with.groups()[0]));
}

// ---------------------------------------------------------------------------
// 1b. Side-neutral storage: the loader's law against the per-side reduction.
// ---------------------------------------------------------------------------

/// Byte-compares `orient(neutral[g], side)` against the INDEPENDENTLY built
/// per-side reduction of the same group, for every sampled group of a stream.
template <std::size_t N, class Stream>
void expect_orientation_reproduces_the_side(Modality modality, const Stream& stream) {
  const GroupVectorTable& neutral = stream.group_vectors();
  ASSERT_GT(stream.spot_groups().size(), 0U);
  for (const Side side : {Side::LONG, Side::SHORT}) {
    const GroupVectorTable& reference = stream.spot_side_vectors(side);
    ASSERT_EQ(reference.groups(), stream.spot_groups().size());
    for (std::size_t sample = 0; sample < stream.spot_groups().size(); ++sample) {
      const std::size_t group = static_cast<std::size_t>(stream.spot_groups()[sample]);
      std::array<float, N> derived{};
      orient_group_vector(modality, neutral.row(group), side, derived);
      const std::span<const float> expected = reference.row(sample);
      for (std::size_t index = 0; index < N; ++index) {
        // Bit-for-bit: two cells that are numerically equal but differ in the
        // sign of zero are two different emitted bytes.
        std::uint32_t derived_bits = 0;
        std::uint32_t expected_bits = 0;
        std::memcpy(&derived_bits, &derived[index], sizeof(derived_bits));
        std::memcpy(&expected_bits, &expected[index], sizeof(expected_bits));
        EXPECT_EQ(derived_bits, expected_bits)
            << modality_name(modality) << " group " << group << " " << side_name(side) << " "
            << group_vector_component_name(modality, index) << ": " << derived[index] << " vs "
            << expected[index];
      }
    }
  }
}

TEST(NativeSideNeutralGroupVector, OrientingTheNeutralTableReproducesEverySideByteForByte) {
  // The ruling's whole claim, as a test: the stored table is side-neutral, and
  // `orient_group_vector` recovers the reduced vector the card's own per-side
  // reduction produces — on a tape that carries multi-member groups, masked
  // channels, partially present channels, own/opposite pairs and both signs.
  const StockPrintStream prints = three_group_tape();
  expect_orientation_reproduces_the_side<kStockPrintGroupDim>(Modality::STOCK_PRINT, prints);

  NbboStream quotes(clock_125(), with_vectors());
  ASSERT_TRUE(quotes
                  .push_group(open_ms() + 1'000,
                              rows_of<qr::sources::StockQuoteRow>({quote_row(
                                  open_ms() + 1'000, 99'990'000, 100'010'000, 500, 700)}))
                  .has_value());
  ASSERT_TRUE(quotes
                  .push_group(open_ms() + 2'000,
                              rows_of<qr::sources::StockQuoteRow>(
                                  {quote_row(open_ms() + 2'000, 100'000'000, 100'020'000, 200, 100),
                                   quote_row(open_ms() + 2'000, 100'010'000, 100'030'000, 200,
                                             500)}))
                  .has_value());
  // A locked group, so a masked-everything NBBO vector is in the comparison too.
  ASSERT_TRUE(quotes
                  .push_group(open_ms() + 3'000,
                              rows_of<qr::sources::StockQuoteRow>({quote_row(
                                  open_ms() + 3'000, 100'020'000, 100'020'000, 300, 300)}))
                  .has_value());
  expect_orientation_reproduces_the_side<kNbboGroupDim>(Modality::STOCK_NBBO, quotes);

  OptionPrintStream options(clock_125(), with_vectors());
  ASSERT_TRUE(options
                  .push_group(open_ms() + 3'000,
                              rows_of<qr::sources::OptionPrintRow>(
                                  {option_row(open_ms() + 3'000, 1'800'000, 5,
                                              qr::sources::Right::Call, 180'000'000, 19'243,
                                              open_ms() + 2'000, 1'700'000, 1'900'000,
                                              "2022-07-05T09:30:02.000", 180.0, 1),
                                   option_row(open_ms() + 3'000, 1'850'000, 7,
                                              qr::sources::Right::Put, 180'000'000, 19'243,
                                              open_ms() + 2'500, 1'750'000, 1'950'000,
                                              "2022-07-05T09:30:02.500", 180.25, 2)}))
                  .has_value());
  ASSERT_TRUE(options
                  .push_group(open_ms() + 5'000,
                              rows_of<qr::sources::OptionPrintRow>({option_row(
                                  open_ms() + 5'000, 1'900'000, 3, qr::sources::Right::Call,
                                  180'000'000, 19'243, open_ms() + 4'000, 1'850'000, 1'950'000,
                                  "2022-07-05T09:30:04.000", 180.5, 3)}))
                  .has_value());
  expect_orientation_reproduces_the_side<kOptionPrintGroupDim>(Modality::OPTION_PRINT, options);
}

TEST(NativeSideNeutralGroupVector, TheOrientationLeafIsTheFrozenChannelTableAndNothingElse) {
  // The exported leaf is channels.hpp's table, not a second copy of it: every
  // row is read back and compared against the declared orientation, the declared
  // swap partner, and the min slot the negating channels occupy in order.
  for (const Modality modality :
       {Modality::STOCK_PRINT, Modality::STOCK_NBBO, Modality::OPTION_PRINT}) {
    const std::size_t channels = declared_value_channel_count(modality);
    const std::vector<std::int32_t> leaf = orientation_leaf(modality);
    ASSERT_EQ(leaf.size(), channels * kOrientationLeafColumns);
    std::size_t expected_slot = 0;
    for (std::size_t channel = 0; channel < channels; ++channel) {
      const OrientKind kind = group_channel_orientation(modality, channel);
      EXPECT_EQ(leaf[channel * kOrientationLeafColumns + 0], static_cast<std::int32_t>(kind));
      EXPECT_EQ(leaf[channel * kOrientationLeafColumns + 1],
                static_cast<std::int32_t>(group_channel_swap_partner(modality, channel)));
      if (kind == OrientKind::SIGMA || kind == OrientKind::SIGMA_RHO) {
        EXPECT_EQ(leaf[channel * kOrientationLeafColumns + 2],
                  static_cast<std::int32_t>(expected_slot));
        EXPECT_EQ(sigma_flip_channels(modality)[expected_slot], channel);
        ++expected_slot;
      } else {
        EXPECT_EQ(leaf[channel * kOrientationLeafColumns + 2], -1);
      }
      // A swap partner is an involution and never points outside the modality.
      const std::size_t partner = group_channel_swap_partner(modality, channel);
      EXPECT_LT(partner, channels);
      EXPECT_EQ(group_channel_swap_partner(modality, partner), channel);
      EXPECT_EQ(kind == OrientKind::OWN_OPPOSITE_SWAP, partner != channel);
    }
    // The min block is exactly the negating channels, and the widths are the
    // ruling's own arithmetic.
    EXPECT_EQ(expected_slot, sigma_flip_channels(modality).size());
    EXPECT_EQ(neutral_group_vector_dim_of(modality),
              group_vector_dim_of(modality) + expected_slot);
  }
  EXPECT_EQ(neutral_group_vector_dim_of(Modality::STOCK_PRINT), 74U);
  EXPECT_EQ(neutral_group_vector_dim_of(Modality::STOCK_NBBO), 67U);
  EXPECT_EQ(neutral_group_vector_dim_of(Modality::OPTION_PRINT), 101U);
}

// ---------------------------------------------------------------------------
// 2. The 128-group micro carrier.
// ---------------------------------------------------------------------------

/// `count` groups at 100ms spacing starting at open+1'000ms.
std::vector<GroupRecord> ladder(std::size_t count) {
  std::vector<GroupRecord> groups;
  groups.reserve(count);
  for (std::size_t index = 0; index < count; ++index) {
    groups.push_back(group_at(frame_a_of(1'000 + static_cast<std::int64_t>(index) * 100)));
  }
  return groups;
}

TEST(NativeMicroCarrier, ExactlyOneHundredAndTwentyEightGroupsAreRetainedAndTheRestAreTruncated) {
  // 200 groups at 100ms from open+1'000ms; the cutoff sits after the 200th, so
  // 200 groups are strictly before it and the carrier keeps the last 128:
  // start = 200-128 = 72, truncated = 72, left pad = 0.
  const std::vector<GroupRecord> groups = ladder(200);
  NativeOrderBuilder builder(Modality::STOCK_PRINT, groups);
  const auto micro = builder.build_micro(window_at(frame_a_of(30'000)));
  ASSERT_TRUE(micro.has_value());
  EXPECT_EQ(micro.value().length, 128);
  EXPECT_EQ(micro.value().start, 72);
  EXPECT_EQ(micro.value().truncated, 72);
  EXPECT_EQ(micro.value().left_pad, 0);
  // Chronological, oldest slot first, newest in the last slot.
  EXPECT_EQ(micro.value().slot_group[0], 72);
  EXPECT_EQ(micro.value().slot_group[127], 199);
  for (std::size_t slot = 1; slot < kMicroCarrierGroups; ++slot) {
    EXPECT_EQ(micro.value().slot_group[slot], micro.value().slot_group[slot - 1] + 1);
  }
  EXPECT_EQ(micro.value().phase_slots[static_cast<std::size_t>(Phase::PAD)], 0);
}

TEST(NativeMicroCarrier, FewerThanOneHundredAndTwentyEightGroupsLeaveATypedLeftPad) {
  // 30 groups before the cutoff: length 30, left pad 98, truncated 0, and the
  // 98 pad slots carry NO group and NO phase.
  const std::vector<GroupRecord> groups = ladder(30);
  NativeOrderBuilder builder(Modality::STOCK_PRINT, groups);
  const auto micro = builder.build_micro(window_at(frame_a_of(30'000)));
  ASSERT_TRUE(micro.has_value());
  EXPECT_EQ(micro.value().length, 30);
  EXPECT_EQ(micro.value().left_pad, 98);
  EXPECT_EQ(micro.value().start, 0);
  EXPECT_EQ(micro.value().truncated, 0);
  for (std::size_t slot = 0; slot < 98U; ++slot) {
    EXPECT_TRUE(micro.value().is_pad(slot));
    EXPECT_EQ(micro.value().slot_group[slot], -1);
    EXPECT_EQ(micro.value().slot_phase[slot], Phase::PAD);
  }
  EXPECT_EQ(micro.value().slot_group[98], 0);
  EXPECT_EQ(micro.value().slot_group[127], 29);
  EXPECT_EQ(micro.value().phase_slots[static_cast<std::size_t>(Phase::PAD)], 98);
}

TEST(NativeMicroCarrier, AnEqualCutoffGroupIsExcludedAndTheOneBeforeItIsNot) {
  // "the most recent 128 groups STRICTLY before cutoff"; "Current/equal-cutoff
  // tokens are excluded". Groups at 1'000/1'100/1'200ms, cutoff at 1'200ms.
  const std::vector<GroupRecord> groups = ladder(3);
  NativeOrderBuilder builder(Modality::STOCK_PRINT, groups);
  const auto micro = builder.build_micro(window_at(frame_a_of(1'200)));
  ASSERT_TRUE(micro.has_value());
  EXPECT_EQ(micro.value().length, 2);
  EXPECT_EQ(micro.value().slot_group[126], 0);
  EXPECT_EQ(micro.value().slot_group[127], 1);  // never group 2, which IS the cutoff
  EXPECT_EQ(builder.groups_before(frame_a_of(1'200)), 2U);
  // One nanosecond later the equal group is strictly before and joins.
  const auto after = builder.build_micro(window_at(frame_a_of(1'200) + 1));
  ASSERT_TRUE(after.has_value());
  EXPECT_EQ(after.value().length, 3);
  EXPECT_EQ(after.value().slot_group[127], 2);
}

TEST(NativeMicroCarrier, AGroupExactlyAtTheVisibilityIsPhaseEqualUnorderedAndNeitherPhase) {
  // "A group with timestamp < visibility is APPROACH, > visibility is RESPONSE,
  // and == visibility is typed PHASE_EQUAL_UNORDERED, receives no phase
  // embedding, and enters neither phase denominator."
  const std::vector<GroupRecord> groups = ladder(10);  // 1'000 .. 1'900ms
  NativeOrderBuilder builder(Modality::STOCK_PRINT, groups);
  const auto micro =
      builder.build_micro(window_with_visibility(frame_a_of(30'000), frame_a_of(1'400)));
  ASSERT_TRUE(micro.has_value());
  // Groups 0..3 are before 1'400ms, group 4 IS 1'400ms, groups 5..9 are after.
  EXPECT_EQ(micro.value().phase_slots[static_cast<std::size_t>(Phase::APPROACH)], 4);
  EXPECT_EQ(micro.value().phase_slots[static_cast<std::size_t>(Phase::PHASE_EQUAL_UNORDERED)], 1);
  EXPECT_EQ(micro.value().phase_slots[static_cast<std::size_t>(Phase::RESPONSE)], 5);
  EXPECT_EQ(micro.value().slot_phase[118 + 3], Phase::APPROACH);  // slot of group 3
  EXPECT_EQ(micro.value().slot_phase[118 + 4], Phase::PHASE_EQUAL_UNORDERED);
  EXPECT_EQ(micro.value().slot_phase[118 + 5], Phase::RESPONSE);

  // DIRECT counts the same split and also excludes the equal group from both
  // denominators — the two constructors may never disagree about it.
  DirectRawBuilder direct(Modality::STOCK_PRINT, groups);
  const auto row =
      direct.build(window_with_visibility(frame_a_of(30'000), frame_a_of(1'400)));
  ASSERT_TRUE(row.has_value());
  const std::size_t base = kDirectFullWindowOffset;
  EXPECT_DOUBLE_EQ(row.value().value[base + kDirectLog1pApproachGroupCount], std::log1p(4.0));
  EXPECT_DOUBLE_EQ(row.value().value[base + kDirectLog1pResponseGroupCount], std::log1p(5.0));
}

TEST(NativeMicroCarrier, AnAbsentVisibilityReferenceLeavesEveryGroupWithoutAPhase) {
  // With no reference there is no phase to claim, and the card's state for "no
  // phase embedding" is PHASE_EQUAL_UNORDERED (lane ruling, reported).
  const std::vector<GroupRecord> groups = ladder(10);
  NativeOrderBuilder builder(Modality::STOCK_PRINT, groups);
  const auto micro = builder.build_micro(window_at(frame_a_of(30'000)));
  ASSERT_TRUE(micro.has_value());
  EXPECT_EQ(micro.value().phase_slots[static_cast<std::size_t>(Phase::PHASE_EQUAL_UNORDERED)], 10);
  EXPECT_EQ(micro.value().phase_slots[static_cast<std::size_t>(Phase::APPROACH)], 0);
  EXPECT_EQ(micro.value().phase_slots[static_cast<std::size_t>(Phase::RESPONSE)], 0);
  EXPECT_FALSE(builder.split_for(window_at(frame_a_of(30'000))).reference_present);
}

TEST(NativeMicroCarrier, TheTruncatedSetIsExactlyTheOneDirectDividesItsOmissionsBy) {
  // DIRECT's omission fraction is "the number of its groups in the complete 120s
  // carrier that are truncated from recent128". The 120s window here holds 200
  // groups, so 72 are truncated — the SAME 72 the micro carrier left behind, and
  // all 72 are APPROACH (they precede the visibility).
  const std::vector<GroupRecord> groups = ladder(200);
  const std::int64_t cutoff = frame_a_of(30'000);
  const std::int64_t visibility = frame_a_of(20'000);  // after group 190
  NativeOrderBuilder builder(Modality::STOCK_PRINT, groups);
  const auto micro = builder.build_micro(window_with_visibility(cutoff, visibility));
  ASSERT_TRUE(micro.has_value());
  EXPECT_EQ(micro.value().truncated, 72);

  DirectRawBuilder direct(Modality::STOCK_PRINT, groups);
  const auto row = direct.build(window_with_visibility(cutoff, visibility));
  ASSERT_TRUE(row.has_value());
  const std::size_t base = kDirectFullWindowOffset;
  // Approach groups: those before 20'000ms = groups 0..189 -> 190 of them, of
  // which the truncated 72 are all approach: 72/190.
  EXPECT_DOUBLE_EQ(row.value().value[base + kDirectApproachOmissionFraction], 72.0 / 190.0);
  // No response group is truncated: 0/10.
  EXPECT_DOUBLE_EQ(row.value().value[base + kDirectResponseOmissionFraction], 0.0);
  EXPECT_TRUE(row.value().presence(base + kDirectResponseOmissionFraction));
}

// ---------------------------------------------------------------------------
// 3. The 120-bin full carrier.
// ---------------------------------------------------------------------------

TEST(NativeBinCarrier, ThereAreExactlyOneHundredAndTwentyOneSecondBinsAndTheyAreNeverTruncated) {
  // An EMPTY group table still produces 120 bins: "Its ordered 120-bin sequence
  // is never truncated."
  const std::vector<GroupRecord> none;
  NativeOrderBuilder empty(Modality::STOCK_PRINT, none);
  const auto bins = empty.build_bins(window_at(frame_a_of(300'000)));
  ASSERT_TRUE(bins.has_value());
  EXPECT_EQ(bins.value().start.size(), 120U);
  EXPECT_EQ(bins.value().nonempty_bins, 0);
  EXPECT_EQ(bins.value().pre_open_pad_bins, 0);  // 300s into the session
  for (std::size_t bin = 0; bin < kBinCarrierBins; ++bin) {
    EXPECT_EQ(bins.value().valid[bin], 1U) << "bin " << bin << " is in session";
    EXPECT_EQ(bins.value().length[bin], 0);
    EXPECT_EQ(bins.value().nonempty[bin], 0U);
    EXPECT_DOUBLE_EQ(bins.value().log1p_group_count[bin], 0.0);  // log1p(0) = 0
  }
}

TEST(NativeBinCarrier, ABinIsLeftClosedAndRightOpenSoABoundaryTokenLandsInTheLaterBin) {
  // The cutoff is at 300'000ms, so bin i covers
  // [180'000 + i*1'000 ms, 180'000 + (i+1)*1'000 ms).
  // A group at exactly 181'000ms is bin 1's LEFT edge: it belongs to bin 1 and
  // never to bin 0, whose right edge it is.
  const std::vector<GroupRecord> groups{
      group_at(frame_a_of(180'000)),  // bin 0's left edge -> bin 0
      group_at(frame_a_of(180'999)),  // still inside bin 0
      group_at(frame_a_of(181'000)),  // bin 1's left edge -> bin 1, not bin 0
  };
  NativeOrderBuilder builder(Modality::STOCK_PRINT, groups);
  const auto bins = builder.build_bins(window_at(frame_a_of(300'000)));
  ASSERT_TRUE(bins.has_value());
  EXPECT_EQ(bins.value().start[0], 0);
  EXPECT_EQ(bins.value().length[0], 2);
  EXPECT_EQ(bins.value().nonempty[0], 1U);
  EXPECT_DOUBLE_EQ(bins.value().log1p_group_count[0], std::log1p(2.0));
  EXPECT_EQ(bins.value().start[1], 2);
  EXPECT_EQ(bins.value().length[1], 1);
  EXPECT_DOUBLE_EQ(bins.value().log1p_group_count[1], std::log1p(1.0));
  EXPECT_EQ(bins.value().length[2], 0);
  EXPECT_EQ(bins.value().member_groups, 3);
  EXPECT_EQ(bins.value().nonempty_bins, 2);
}

TEST(NativeBinCarrier, TheLastBinEndsBeforeTheCutoffSoAnEqualCutoffGroupIsExcluded) {
  // Bin 119 is [cutoff-1s, cutoff): a group AT the cutoff is in no bin at all.
  const std::vector<GroupRecord> groups{
      group_at(frame_a_of(299'999)),  // inside bin 119
      group_at(frame_a_of(300'000)),  // the cutoff itself
  };
  NativeOrderBuilder builder(Modality::STOCK_PRINT, groups);
  const auto bins = builder.build_bins(window_at(frame_a_of(300'000)));
  ASSERT_TRUE(bins.has_value());
  EXPECT_EQ(bins.value().length[119], 1);
  EXPECT_EQ(bins.value().start[119], 0);
  EXPECT_EQ(bins.value().member_groups, 1);
}

TEST(NativeBinCarrier, ARealPrintOnEachBoundaryLandsWhereTheCardPutsIt) {
  // The named production-constructor mutant "place a token on each bin/cutoff
  // boundary", driven through the ACTUAL stock-print constructor rather than a
  // hand group record. The cutoff is open+300'000ms, so bin 118 is
  // [298'000, 299'000) and bin 119 is [299'000, 300'000).
  StockPrintStream stream(clock_125(), with_vectors());
  std::int64_t sequence = 0;
  for (const std::int64_t offset : {298'999, 299'000, 300'000}) {
    ASSERT_TRUE(stream
                    .push_group(open_ms() + offset,
                                rows_of<qr::sources::StockTradeRow>({trade_row(
                                    open_ms() + offset, 100'000'000, 100, open_ms() + offset - 500,
                                    99'990'000, 100'010'000, 400, 400, ++sequence)}))
                    .has_value());
  }
  ASSERT_EQ(stream.groups().size(), 3U);
  NativeOrderBuilder builder(Modality::STOCK_PRINT, stream.groups());
  const auto bins = builder.build_bins(window_at(frame_a_of(300'000)));
  ASSERT_TRUE(bins.has_value());
  // 298'999ms is inside bin 118; 299'000ms OPENS bin 119 (left-closed) rather
  // than closing bin 118; the cutoff group is in no bin at all.
  EXPECT_EQ(bins.value().start[118], 0);
  EXPECT_EQ(bins.value().length[118], 1);
  EXPECT_EQ(bins.value().start[119], 1);
  EXPECT_EQ(bins.value().length[119], 1);
  EXPECT_EQ(bins.value().member_groups, 2);
  EXPECT_EQ(bins.value().nonempty_bins, 2);
  // The micro carrier drops the equal-cutoff group for the same reason.
  const auto micro = builder.build_micro(window_at(frame_a_of(300'000)));
  ASSERT_TRUE(micro.has_value());
  EXPECT_EQ(micro.value().length, 2);
  EXPECT_EQ(micro.value().slot_group[127], 1);
}

TEST(NativeBinCarrier, PreOpenBinsAreTypedZeroLeftPadAndAnEmptyInSessionBinIsNot) {
  // A cutoff 30s into the session: bins whose right edge is at or before the
  // open are pads. cutoff-120s = open-90s, so bins 0..89 end at or before the
  // open and bins 90..119 are in session — 90 typed pads.
  const std::vector<GroupRecord> groups{group_at(frame_a_of(29'500))};
  NativeOrderBuilder builder(Modality::STOCK_PRINT, groups);
  const auto bins = builder.build_bins(window_at(frame_a_of(30'000)));
  ASSERT_TRUE(bins.has_value());
  EXPECT_EQ(bins.value().pre_open_pad_bins, 90);
  for (std::size_t bin = 0; bin < 90U; ++bin) {
    EXPECT_TRUE(bins.value().is_pad(bin));
    EXPECT_EQ(bins.value().start[bin], -1);  // the pad's own value, not "empty"
    EXPECT_EQ(bins.value().length[bin], 0);
    EXPECT_EQ(bins.value().valid[bin], 0U);
  }
  // Bin 90 covers [open, open+1s): in session, valid, and empty — which is NOT
  // the same state as a pad.
  EXPECT_FALSE(bins.value().is_pad(90));
  EXPECT_EQ(bins.value().start[90], 0);
  EXPECT_EQ(bins.value().valid[90], 1U);
  EXPECT_EQ(bins.value().length[90], 0);
  // The one group sits in bin 119 = [29s, 30s).
  EXPECT_EQ(bins.value().length[119], 1);
}

// ---------------------------------------------------------------------------
// 4. The section-7 destructions, and the wall that keeps them out.
// ---------------------------------------------------------------------------

/// Every bit DIRECT_RAW and the micro carrier produce for one window.
std::vector<std::uint8_t> direct_and_micro_bytes(Modality modality,
                                                 std::span<const GroupRecord> groups,
                                                 const DecisionWindow& window,
                                                 const MicroCarrier& micro) {
  std::vector<std::uint8_t> bytes;
  const auto push = [&bytes](std::uint64_t bits) {
    for (unsigned shift = 0; shift < 64; shift += 8) {
      bytes.push_back(static_cast<std::uint8_t>((bits >> shift) & 0xFFU));
    }
  };
  DirectRawBuilder direct(modality, groups);
  const auto row = direct.build(window);
  EXPECT_TRUE(row.has_value());
  for (std::size_t column = 0; column < kDirectColumnCount; ++column) {
    std::uint64_t value_bits = 0;
    std::memcpy(&value_bits, &row.value().value[column], sizeof(value_bits));
    push(value_bits);
    push(static_cast<std::uint64_t>(row.value().validity[column]));
  }
  push(static_cast<std::uint64_t>(micro.start));
  push(static_cast<std::uint64_t>(micro.length));
  push(static_cast<std::uint64_t>(micro.left_pad));
  push(static_cast<std::uint64_t>(micro.truncated));
  for (std::size_t slot = 0; slot < kMicroCarrierGroups; ++slot) {
    push(static_cast<std::uint64_t>(micro.slot_group[slot]));
    push(static_cast<std::uint64_t>(micro.slot_phase[slot]));
  }
  return bytes;
}

TEST(NativeOrderDestructions, BinOrderReverseKeepsTheValidMultisetThePadsAndEveryOtherInput) {
  // Section 7 (f): "reverses the value+mask tuples only within the ordered valid
  // in-session support of the 120 bins, leaves fixed pre-open pads/validity in
  // place, keeps the valid-bin multiset and every DIRECT/micro input
  // bit-identical".
  //
  // A 30s cutoff gives 90 pre-open pads and 30 valid bins, so the reversal has
  // both kinds to respect.
  std::vector<GroupRecord> groups;
  for (std::int64_t index = 0; index < 30; ++index) {
    // One group per in-session second, so every valid bin is distinguishable.
    groups.push_back(group_at(frame_a_of(index * 1'000 + 500)));
  }
  const DecisionWindow window = window_with_visibility(frame_a_of(30'000), frame_a_of(10'000));

  NativeOrderBuilder production(Modality::STOCK_PRINT, groups);
  NativeCarrierControls controls;
  controls.bin_order_reverse = true;
  NativeOrderBuilder destroyed(Modality::STOCK_PRINT, groups, controls);

  const auto clean = production.build_bins(window);
  const auto reversed = destroyed.build_bins(window);
  ASSERT_TRUE(clean.has_value());
  ASSERT_TRUE(reversed.has_value());

  // The pads and the validity plane do not move.
  for (std::size_t bin = 0; bin < kBinCarrierBins; ++bin) {
    EXPECT_EQ(clean.value().valid[bin], reversed.value().valid[bin]);
  }
  EXPECT_EQ(clean.value().pre_open_pad_bins, reversed.value().pre_open_pad_bins);
  EXPECT_EQ(clean.value().nonempty_bins, reversed.value().nonempty_bins);
  EXPECT_EQ(clean.value().member_groups, reversed.value().member_groups);

  // The valid tuples are the same multiset, in reversed order.
  std::vector<std::pair<std::int32_t, std::int32_t>> forward;
  std::vector<std::pair<std::int32_t, std::int32_t>> backward;
  for (std::size_t bin = 0; bin < kBinCarrierBins; ++bin) {
    if (clean.value().valid[bin] == 0U) {
      continue;
    }
    forward.emplace_back(clean.value().start[bin], clean.value().length[bin]);
    backward.emplace_back(reversed.value().start[bin], reversed.value().length[bin]);
  }
  ASSERT_EQ(forward.size(), 30U);
  std::vector<std::pair<std::int32_t, std::int32_t>> flipped = forward;
  std::reverse(flipped.begin(), flipped.end());
  EXPECT_EQ(backward, flipped) << "the reversal is not the reversal of the valid support";
  std::sort(forward.begin(), forward.end());
  std::sort(backward.begin(), backward.end());
  EXPECT_EQ(forward, backward) << "the valid-bin multiset changed";

  // "every DIRECT/micro input bit-identical" — the law, as a test.
  const auto clean_micro = production.build_micro(window);
  const auto destroyed_micro = destroyed.build_micro(window);
  ASSERT_TRUE(clean_micro.has_value());
  ASSERT_TRUE(destroyed_micro.has_value());
  EXPECT_EQ(direct_and_micro_bytes(Modality::STOCK_PRINT, groups, window, clean_micro.value()),
            direct_and_micro_bytes(Modality::STOCK_PRINT, groups, window,
                                   destroyed_micro.value()));
}

TEST(NativeOrderDestructions, TheRecentOneHundredAndTwentyEightReverseKeepsTheMultisetAndThePad) {
  // Section 7 (e): the valid recent-128 sequence reverses; the typed left pad
  // does not move, and the retained group multiset is unchanged.
  const std::vector<GroupRecord> groups = ladder(30);
  const DecisionWindow window = window_with_visibility(frame_a_of(30'000), frame_a_of(2'000));

  NativeOrderBuilder production(Modality::STOCK_PRINT, groups);
  NativeCarrierControls controls;
  controls.recent128_reverse = true;
  NativeOrderBuilder destroyed(Modality::STOCK_PRINT, groups, controls);
  const auto clean = production.build_micro(window);
  const auto reversed = destroyed.build_micro(window);
  ASSERT_TRUE(clean.has_value());
  ASSERT_TRUE(reversed.has_value());

  EXPECT_EQ(reversed.value().left_pad, clean.value().left_pad);
  EXPECT_EQ(reversed.value().length, clean.value().length);
  EXPECT_EQ(reversed.value().truncated, clean.value().truncated);
  for (std::size_t slot = 0; slot < 98U; ++slot) {
    EXPECT_TRUE(reversed.value().is_pad(slot)) << "the left pad moved";
  }
  EXPECT_EQ(reversed.value().slot_group[98], 29);   // newest first, after the pad
  EXPECT_EQ(reversed.value().slot_group[127], 0);   // oldest last
  std::vector<std::int32_t> clean_groups;
  std::vector<std::int32_t> reversed_groups;
  for (std::size_t slot = 98; slot < kMicroCarrierGroups; ++slot) {
    clean_groups.push_back(clean.value().slot_group[slot]);
    reversed_groups.push_back(reversed.value().slot_group[slot]);
  }
  std::vector<std::int32_t> flipped = clean_groups;
  std::reverse(flipped.begin(), flipped.end());
  EXPECT_EQ(reversed_groups, flipped);
  // The phase of a slot follows its OWN group, so the labels travel with it.
  EXPECT_EQ(reversed.value().phase_slots, clean.value().phase_slots);
}

TEST(NativeOrderDestructions, TheProductionPathIsIdenticalToABuildWithoutTheFlagCode) {
  // "destruction-flag off = production path byte-identical to a build without
  // the flag code compiled". The comparison binary links a SECOND build of the
  // library compiled with -DQR_CARRIERS_NO_DESTRUCTIONS, where the controls type
  // and every branch that reads it do not exist.
  const std::string here = std::filesystem::read_symlink("/proc/self/exe").parent_path().string();
  const std::string command = here + "/qr_carriers_nodestruct_probe";
  ASSERT_TRUE(std::filesystem::exists(command)) << "missing " << command;
  std::FILE* pipe = ::popen(command.c_str(), "r");
  ASSERT_NE(pipe, nullptr);
  char buffer[128] = {0};
  const char* line = std::fgets(buffer, sizeof(buffer), pipe);
  const int status = ::pclose(pipe);
  ASSERT_NE(line, nullptr);
  EXPECT_EQ(status, 0);

  std::string printed(buffer);
  const std::string prefix = "production_fingerprint ";
  ASSERT_EQ(printed.rfind(prefix, 0), 0U) << "unexpected probe output: " << printed;
  std::string digest = printed.substr(prefix.size());
  while (!digest.empty() && (digest.back() == '\n' || digest.back() == '\r')) {
    digest.pop_back();
  }
  EXPECT_EQ(digest.size(), 16U);
  // The ordinary build, with the flags off, over exactly the same tape.
  EXPECT_EQ(guard::production_fingerprint(), digest)
      << "the destruction code moved a production bit";
}

TEST(NativeOrderDestructions, ADestroyedCarrierIsRefusedAtTheEmissionDoor) {
  // The second wall: a published C4 tape carries the PRODUCTION carriers, and
  // (start,len) cannot express a reversal, so the emission door refuses one.
  const std::vector<GroupRecord> groups = ladder(30);
  const DecisionWindow window = window_at(frame_a_of(30'000));
  StockPrintStream stream(clock_125(), with_vectors());
  for (std::size_t index = 0; index < 30; ++index) {
    ASSERT_TRUE(stream
                    .push_group(open_ms() + 1'000 + static_cast<std::int64_t>(index) * 100,
                                rows_of<qr::sources::StockTradeRow>({trade_row(
                                    open_ms() + 1'000 + static_cast<std::int64_t>(index) * 100,
                                    100'000'000, 100, open_ms() + 500, 99'990'000, 100'010'000,
                                    400, 400, static_cast<std::int64_t>(index))}))
                    .has_value());
  }
  NativeOrderShard shard(Modality::STOCK_PRINT, stream.groups(), stream.group_vectors());

  NativeOrderBuilder production(Modality::STOCK_PRINT, stream.groups());
  const auto clean_micro = production.build_micro(window);
  const auto clean_bins = production.build_bins(window);
  ASSERT_TRUE(clean_micro.has_value());
  ASSERT_TRUE(clean_bins.has_value());
  const PhaseSplit split = production.split_for(window);
  EXPECT_TRUE(shard.push_decision(clean_micro.value(), clean_bins.value(), split).has_value());

  NativeCarrierControls controls;
  controls.recent128_reverse = true;
  controls.bin_order_reverse = true;
  NativeOrderBuilder destroyed(Modality::STOCK_PRINT, stream.groups(), controls);
  const auto bad_micro = destroyed.build_micro(window);
  const auto bad_bins = destroyed.build_bins(window);
  ASSERT_TRUE(bad_micro.has_value());
  ASSERT_TRUE(bad_bins.has_value());
  const auto refused_micro = shard.push_decision(bad_micro.value(), clean_bins.value(), split);
  ASSERT_FALSE(refused_micro.has_value());
  EXPECT_EQ(refused_micro.error().code(), RefusalCode::CONTENT_MISMATCH);
  const auto refused_bins = shard.push_decision(clean_micro.value(), bad_bins.value(), split);
  ASSERT_FALSE(refused_bins.has_value());
  EXPECT_EQ(refused_bins.error().code(), RefusalCode::CONTENT_MISMATCH);
  // A refusal appends nothing.
  EXPECT_EQ(shard.decisions(), 1);
}

// ---------------------------------------------------------------------------
// 5. The production-constructor controls, through the WHOLE chain.
// ---------------------------------------------------------------------------

/// Everything the WP8b substrate produces for one hand tape: the three streams'
/// group records, both sides' reduced group vectors, and DIRECT + micro + bin
/// for a fixed set of decisions — plus the prior states the tape left behind.
struct ChainImage {
  std::vector<std::uint8_t> bytes;
};

void push_u64(std::vector<std::uint8_t>& bytes, std::uint64_t bits) {
  for (unsigned shift = 0; shift < 64; shift += 8) {
    bytes.push_back(static_cast<std::uint8_t>((bits >> shift) & 0xFFU));
  }
}
void push_f64(std::vector<std::uint8_t>& bytes, double value) {
  std::uint64_t bits = 0;
  std::memcpy(&bits, &value, sizeof(bits));
  push_u64(bytes, bits);
}
void push_f32(std::vector<std::uint8_t>& bytes, float value) {
  std::uint32_t bits = 0;
  std::memcpy(&bits, &value, sizeof(bits));
  push_u64(bytes, bits);
}

void fold_modality(ChainImage& image, Modality modality, std::span<const GroupRecord> groups,
                   const GroupVectorTable& neutral, const GroupVectorTable& longs,
                   const GroupVectorTable& shorts) {
  for (const GroupRecord& group : groups) {
    const auto serialized = testing::serialize(group);
    image.bytes.insert(image.bytes.end(), serialized.begin(), serialized.end());
  }
  for (const GroupVectorTable* table : {&neutral, &longs, &shorts}) {
    push_u64(image.bytes, table->groups());
    push_u64(image.bytes, table->dim());
    for (const float value : table->values()) {
      push_f32(image.bytes, value);
    }
  }
  DirectRawBuilder direct(modality, groups);
  NativeOrderBuilder native(modality, groups);
  for (const Side side : {Side::LONG, Side::SHORT}) {
    for (const std::int64_t cutoff_ms : {11'000, 13'000, 30'000}) {
      const DecisionWindow window =
          window_with_visibility(frame_a_of(cutoff_ms), frame_a_of(10'000), side);
      const auto row = direct.build(window);
      EXPECT_TRUE(row.has_value());
      for (std::size_t column = 0; column < kDirectColumnCount; ++column) {
        push_f64(image.bytes, row.value().value[column]);
        push_u64(image.bytes, static_cast<std::uint64_t>(row.value().validity[column]));
      }
      const auto micro = native.build_micro(window);
      EXPECT_TRUE(micro.has_value());
      push_u64(image.bytes, static_cast<std::uint64_t>(micro.value().start));
      push_u64(image.bytes, static_cast<std::uint64_t>(micro.value().length));
      push_u64(image.bytes, static_cast<std::uint64_t>(micro.value().left_pad));
      push_u64(image.bytes, static_cast<std::uint64_t>(micro.value().truncated));
      for (std::size_t slot = 0; slot < kMicroCarrierGroups; ++slot) {
        push_u64(image.bytes, static_cast<std::uint64_t>(micro.value().slot_group[slot]));
        push_u64(image.bytes, static_cast<std::uint64_t>(micro.value().slot_phase[slot]));
      }
      const auto bins = native.build_bins(window);
      EXPECT_TRUE(bins.has_value());
      for (std::size_t bin = 0; bin < kBinCarrierBins; ++bin) {
        push_u64(image.bytes, static_cast<std::uint64_t>(bins.value().start[bin]));
        push_u64(image.bytes, static_cast<std::uint64_t>(bins.value().length[bin]));
        push_f64(image.bytes, bins.value().log1p_group_count[bin]);
        push_u64(image.bytes, bins.value().nonempty[bin]);
        push_u64(image.bytes, bins.value().valid[bin]);
      }
    }
  }
}

/// Builds the whole chain over a tape whose multi-member groups are presented in
/// the given member order.
ChainImage build_chain(bool reversed, bool reverse_last_group = false) {
  ChainImage image;

  StockPrintStream prints(clock_125(), with_vectors());
  EXPECT_TRUE(prints.push_group(open_ms() + 8'000, prior_group()).has_value());
  std::vector<qr::sources::StockTradeRow> equal_ms =
      reversed ? rows_of<qr::sources::StockTradeRow>({print_p5(), print_p2(), print_p1()})
               : rows_of<qr::sources::StockTradeRow>({print_p1(), print_p2(), print_p5()});
  EXPECT_TRUE(prints.push_group(open_ms() + 10'000, equal_ms).has_value());
  std::vector<qr::sources::StockTradeRow> third =
      reverse_last_group
          ? rows_of<qr::sources::StockTradeRow>({print_p4(), print_p6(), print_p3()})
          : rows_of<qr::sources::StockTradeRow>({print_p3(), print_p6(), print_p4()});
  EXPECT_TRUE(prints.push_group(open_ms() + 12'000, third).has_value());

  NbboStream quotes(clock_125(), with_vectors());
  EXPECT_TRUE(quotes
                  .push_group(open_ms() + 1'000,
                              rows_of<qr::sources::StockQuoteRow>({quote_row(
                                  open_ms() + 1'000, 99'990'000, 100'010'000, 500, 700)}))
                  .has_value());
  const auto quote_a = quote_row(open_ms() + 2'000, 100'000'000, 100'020'000, 200, 100);
  const auto quote_b = quote_row(open_ms() + 2'000, 100'010'000, 100'030'000, 200, 500);
  EXPECT_TRUE(quotes
                  .push_group(open_ms() + 2'000,
                              reversed
                                  ? rows_of<qr::sources::StockQuoteRow>({quote_b, quote_a})
                                  : rows_of<qr::sources::StockQuoteRow>({quote_a, quote_b}))
                  .has_value());

  OptionPrintStream options(clock_125(), with_vectors());
  const auto option_a =
      option_row(open_ms() + 3'000, 1'800'000, 5, qr::sources::Right::Call, 180'000'000, 19'243,
                 open_ms() + 2'000, 1'700'000, 1'900'000, "2022-07-05T09:30:02.000", 180.0, 1);
  const auto option_b =
      option_row(open_ms() + 3'000, 1'850'000, 7, qr::sources::Right::Put, 180'000'000, 19'243,
                 open_ms() + 2'500, 1'750'000, 1'950'000, "2022-07-05T09:30:02.500", 180.25, 2);
  EXPECT_TRUE(options
                  .push_group(open_ms() + 3'000,
                              reversed
                                  ? rows_of<qr::sources::OptionPrintRow>({option_b, option_a})
                                  : rows_of<qr::sources::OptionPrintRow>({option_a, option_b}))
                  .has_value());
  EXPECT_TRUE(options
                  .push_group(open_ms() + 5'000,
                              rows_of<qr::sources::OptionPrintRow>({option_row(
                                  open_ms() + 5'000, 1'900'000, 3, qr::sources::Right::Call,
                                  180'000'000, 19'243, open_ms() + 4'000, 1'850'000, 1'950'000,
                                  "2022-07-05T09:30:04.000", 180.5, 3)}))
                  .has_value());

  fold_modality(image, Modality::STOCK_PRINT, prints.groups(), prints.group_vectors(),
                prints.spot_side_vectors(Side::LONG), prints.spot_side_vectors(Side::SHORT));
  fold_modality(image, Modality::STOCK_NBBO, quotes.groups(), quotes.group_vectors(),
                quotes.spot_side_vectors(Side::LONG), quotes.spot_side_vectors(Side::SHORT));
  fold_modality(image, Modality::OPTION_PRINT, options.groups(), options.group_vectors(),
                options.spot_side_vectors(Side::LONG), options.spot_side_vectors(Side::SHORT));

  // The prior states the permuted groups left behind — the control's "and all
  // later prior states" half.
  push_u64(image.bytes, prints.prior().prior().present ? 1U : 0U);
  push_u64(image.bytes, static_cast<std::uint64_t>(prints.prior().prior().mean));
  push_u64(image.bytes, static_cast<std::uint64_t>(prints.vwap_notional_sum()));
  push_u64(image.bytes, static_cast<std::uint64_t>(prints.vwap_size_sum()));
  push_u64(image.bytes, options.underlying_prior().prior().present ? 1U : 0U);
  push_u64(image.bytes, static_cast<std::uint64_t>(options.underlying_prior().prior().mean));
  return image;
}

TEST(NativeOrderProductionControls, AWithinTimestampPermutationIsBitIdenticalThroughTheChain) {
  // Section 7: "The equal-ms control permutes a real multirow timestamp group
  // through the ACTUAL stock, NBBO, option, prior-state, DIRECT, micro, and bin
  // constructors and requires every output bit and all later prior states to
  // remain identical; a standalone reducer fixture is not evidence."
  const ChainImage forward = build_chain(false);
  const ChainImage reverse = build_chain(true);
  ASSERT_FALSE(forward.bytes.empty());
  EXPECT_EQ(forward.bytes, reverse.bytes)
      << "permuting an equal-timestamp group moved an output bit";
}

TEST(NativeOrderProductionControls, ReversingASameGroupRowOrderIsAlsoBitIdentical) {
  // The named production-constructor mutant "reverse a same-group row order",
  // on a DIFFERENT group: three members whose dependencies disagree (P3's and
  // P6's quotes are usable, P4's is EQUAL_TIME) and whose log sizes do not sum
  // associatively, so a reduction that consumed rows in arrival order would
  // show it here.
  const ChainImage forward = build_chain(false, false);
  const ChainImage reversed = build_chain(false, true);
  EXPECT_EQ(forward.bytes, reversed.bytes);
}

TEST(NativeOrderProductionControls, MovingAGroupAcrossTheVisibilityChangesOnlyThePhaseLabels) {
  // The mutant: one group moves from just before the visibility to just after
  // it. Its membership in both carriers is unchanged (the timestamps stay inside
  // the same bin and the same recent-128 run); only its phase label and the two
  // phase counts move.
  const std::int64_t cutoff = frame_a_of(30'000);
  const std::int64_t visibility = frame_a_of(1'450);
  const std::vector<GroupRecord> groups{
      group_at(frame_a_of(1'400)), group_at(frame_a_of(1'440)), group_at(frame_a_of(1'480))};
  NativeOrderBuilder builder(Modality::STOCK_PRINT, groups);
  const auto before = builder.build_micro(window_with_visibility(cutoff, visibility));
  ASSERT_TRUE(before.has_value());
  EXPECT_EQ(before.value().phase_slots[static_cast<std::size_t>(Phase::APPROACH)], 2);
  EXPECT_EQ(before.value().phase_slots[static_cast<std::size_t>(Phase::RESPONSE)], 1);

  // Now the middle group is one nanosecond LATER than the visibility.
  std::vector<GroupRecord> moved = groups;
  moved[1].ts_ns_a = visibility + 1;
  NativeOrderBuilder after_builder(Modality::STOCK_PRINT, moved);
  const auto after = after_builder.build_micro(window_with_visibility(cutoff, visibility));
  ASSERT_TRUE(after.has_value());
  EXPECT_EQ(after.value().phase_slots[static_cast<std::size_t>(Phase::APPROACH)], 1);
  EXPECT_EQ(after.value().phase_slots[static_cast<std::size_t>(Phase::RESPONSE)], 2);
  // Membership, order, pad and truncation are untouched.
  EXPECT_EQ(after.value().length, before.value().length);
  EXPECT_EQ(after.value().left_pad, before.value().left_pad);
  EXPECT_EQ(after.value().slot_group, before.value().slot_group);

  // And exactly ON the visibility it is in neither phase.
  std::vector<GroupRecord> equal = groups;
  equal[1].ts_ns_a = visibility;
  NativeOrderBuilder equal_builder(Modality::STOCK_PRINT, equal);
  const auto at = equal_builder.build_micro(window_with_visibility(cutoff, visibility));
  ASSERT_TRUE(at.has_value());
  EXPECT_EQ(at.value().phase_slots[static_cast<std::size_t>(Phase::APPROACH)], 1);
  EXPECT_EQ(at.value().phase_slots[static_cast<std::size_t>(Phase::RESPONSE)], 1);
  EXPECT_EQ(at.value().phase_slots[static_cast<std::size_t>(Phase::PHASE_EQUAL_UNORDERED)], 1);
}

TEST(NativeOrderProductionControls, DroppingThePreviousSequenceValidGroupMovesOnlyItsOwnOutputs) {
  // The mutant: the tape loses its FIRST sequence-valid group. The second
  // group's sequence gap loses its reference (the card: "The first
  // sequence-valid group ... have all three missing"), which must show up in
  // that group's reduced vector — and nowhere else in the vector.
  const auto build = [](bool with_first) {
    StockPrintStream stream(clock_125(), with_vectors());
    if (with_first) {
      EXPECT_TRUE(stream.push_group(open_ms() + 8'000, prior_group()).has_value());
    }
    EXPECT_TRUE(stream
                    .push_group(open_ms() + 10'000,
                                rows_of<qr::sources::StockTradeRow>({print_p1(), print_p2()}))
                    .has_value());
    return stream;
  };
  const StockPrintStream complete = build(true);
  const StockPrintStream dropped = build(false);
  constexpr std::size_t kC = kStockPrintChannelCount;
  const std::span<const float> with_prior = complete.group_vectors().row(1);
  const std::span<const float> without_prior = dropped.group_vectors().row(0);

  // With the first group present: gap = seq_min(10) - prev_seq_max(5) = 5.
  EXPECT_EQ(with_prior[group_mean_value_offset(kC) + kSpSequenceGapSignedLog],
            f4(std::log1p(5.0)));
  EXPECT_EQ(with_prior[group_mean_mask_offset(kC) + kSpSequenceGapSignedLog], f4(1.0));
  EXPECT_EQ(with_prior[group_mean_value_offset(kC) + kSpSequenceMonotone], f4(1.0));
  // Without it, all three sequence facts are missing: value0/presence0.
  EXPECT_EQ(without_prior[group_mean_value_offset(kC) + kSpSequenceGapSignedLog], 0.0F);
  EXPECT_EQ(without_prior[group_mean_mask_offset(kC) + kSpSequenceGapSignedLog], 0.0F);
  EXPECT_EQ(without_prior[group_max_mask_offset(kC) + kSpSequenceGapSignedLog], 0.0F);
  EXPECT_EQ(without_prior[group_mean_mask_offset(kC) + kSpSequenceMonotone], 0.0F);
  // The print RETURN also loses its prior group — the declared dependency — but
  // the size and multiplicity components, which depend on neither, do not move.
  EXPECT_EQ(without_prior[group_mean_mask_offset(kC) + kSpOrientedPrintReturn], 0.0F);
  EXPECT_EQ(without_prior[group_mean_value_offset(kC) + kSpLogSize],
            with_prior[group_mean_value_offset(kC) + kSpLogSize]);
  EXPECT_EQ(without_prior[group_log_multiplicity_offset(kC)],
            with_prior[group_log_multiplicity_offset(kC)]);
}

TEST(NativeOrderProductionControls, DuplicatingOneAttachmentFailureReasonMovesNoReducedCell) {
  // "unusable attachment is one union indicator per print ... never multiple
  // counts for one print". A print whose attachment fails on TWO families at
  // once must reduce to the same vector as the same print failing on one, save
  // for the channels the second failure genuinely masks.
  qr::sources::StockTradeRow one_reason = trade_row(open_ms() + 10'000, 100'000'000, 300,
                                                    open_ms() + 9'000, 100'010'000, 99'990'000,
                                                    500, 700, 10);
  qr::sources::StockTradeRow two_reasons = one_reason;
  two_reasons.quote_ts_ms_b = open_ms() + 10'000;  // + an independent clock failure

  const auto run = [](const qr::sources::StockTradeRow& row) {
    StockPrintStream stream(clock_125(), with_vectors());
    EXPECT_TRUE(
        stream.push_group(open_ms() + 10'000, rows_of<qr::sources::StockTradeRow>({row}))
            .has_value());
    return stream;
  };
  const StockPrintStream single = run(one_reason);
  const StockPrintStream doubled = run(two_reasons);
  ASSERT_EQ(single.groups().size(), 1U);
  ASSERT_EQ(doubled.groups().size(), 1U);
  EXPECT_EQ(single.groups()[0].unusable_attachment_tokens, 1);
  EXPECT_EQ(doubled.groups()[0].unusable_attachment_tokens, 1);

  constexpr std::size_t kC = kStockPrintChannelCount;
  const std::span<const float> one = single.group_vectors().row(0);
  const std::span<const float> two = doubled.group_vectors().row(0);
  // The crossed quote already masked every signing-dependent channel in BOTH;
  // the second failure only takes the clock-dependent age with it.
  EXPECT_EQ(one[group_mean_mask_offset(kC) + kSpLogQuoteAge], f4(1.0));
  EXPECT_EQ(two[group_mean_mask_offset(kC) + kSpLogQuoteAge], 0.0F);
  EXPECT_EQ(one[group_mean_value_offset(kC) + kSpLogSize],
            two[group_mean_value_offset(kC) + kSpLogSize]);
  EXPECT_EQ(one[group_mean_value_offset(kC) + kSpQuotePresent],
            two[group_mean_value_offset(kC) + kSpQuotePresent]);
  EXPECT_EQ(one[group_log_multiplicity_offset(kC)], two[group_log_multiplicity_offset(kC)]);
}

// ---------------------------------------------------------------------------
// 6. The APPENDIX C4 leaves.
// ---------------------------------------------------------------------------

TEST(NativeOrderEmission, TheLeavesCarryTheAppendixC4NamesShapesAndDtypes) {
  StockPrintStream stream(clock_125(), with_vectors());
  for (std::size_t index = 0; index < 5; ++index) {
    const std::int64_t offset = 1'000 + static_cast<std::int64_t>(index) * 100;
    ASSERT_TRUE(stream
                    .push_group(open_ms() + offset,
                                rows_of<qr::sources::StockTradeRow>({trade_row(
                                    open_ms() + offset, 100'000'000, 100, open_ms() + 500,
                                    99'990'000, 100'010'000, 400, 400,
                                    static_cast<std::int64_t>(index))}))
                    .has_value());
  }
  NativeOrderShard shard(Modality::STOCK_PRINT, stream.groups(), stream.group_vectors());
  NativeOrderBuilder builder(Modality::STOCK_PRINT, stream.groups());
  for (const std::int64_t cutoff_ms : {2'000, 30'000}) {
    const DecisionWindow window =
        window_with_visibility(frame_a_of(cutoff_ms), frame_a_of(1'250));
    const auto micro = builder.build_micro(window);
    const auto bins = builder.build_bins(window);
    ASSERT_TRUE(micro.has_value());
    ASSERT_TRUE(bins.has_value());
    ASSERT_TRUE(
        shard.push_decision(micro.value(), bins.value(), builder.split_for(window)).has_value());
  }
  EXPECT_EQ(shard.decisions(), 2);
  EXPECT_EQ(shard.groups(), 5);

  // The names are C4's, with the per-modality suffix every group-indexed leaf
  // needs.
  EXPECT_EQ(native_leaf_name(NativeLeaf::GROUPS, Modality::STOCK_PRINT), "groups_stock_print");
  EXPECT_EQ(native_leaf_name(NativeLeaf::GROUP_TS, Modality::STOCK_NBBO), "group_ts_stock_nbbo");
  EXPECT_EQ(native_leaf_name(NativeLeaf::ORIENTATION, Modality::STOCK_NBBO),
            "orientation_stock_nbbo");
  EXPECT_EQ(native_leaf_name(NativeLeaf::BINS_INDEX, Modality::OPTION_PRINT),
            "bins_index_option_print");
  // Three leaves belong to the session and three to the side.
  EXPECT_TRUE(native_leaf_is_session_scoped(NativeLeaf::GROUPS));
  EXPECT_TRUE(native_leaf_is_session_scoped(NativeLeaf::GROUP_TS));
  EXPECT_TRUE(native_leaf_is_session_scoped(NativeLeaf::ORIENTATION));
  EXPECT_FALSE(native_leaf_is_session_scoped(NativeLeaf::RECENT128));
  EXPECT_FALSE(native_leaf_is_session_scoped(NativeLeaf::PHASE_SPLIT));
  EXPECT_FALSE(native_leaf_is_session_scoped(NativeLeaf::BINS_INDEX));

  // The shapes are C4's, with the side-neutral group width: [G,74], [G], [17,3],
  // [N,2], [N,2], [N,120,2].
  EXPECT_EQ(shard.leaf_shape(NativeLeaf::GROUPS), (std::vector<std::int64_t>{5, 74}));
  EXPECT_EQ(shard.leaf_shape(NativeLeaf::GROUP_TS), (std::vector<std::int64_t>{5}));
  EXPECT_EQ(shard.leaf_shape(NativeLeaf::ORIENTATION), (std::vector<std::int64_t>{17, 3}));
  EXPECT_EQ(shard.leaf_shape(NativeLeaf::RECENT128), (std::vector<std::int64_t>{2, 2}));
  EXPECT_EQ(shard.leaf_shape(NativeLeaf::PHASE_SPLIT), (std::vector<std::int64_t>{2, 2}));
  EXPECT_EQ(shard.leaf_shape(NativeLeaf::BINS_INDEX), (std::vector<std::int64_t>{2, 120, 2}));
  EXPECT_EQ(shard.group_values().size(), 5U * 74U);
  EXPECT_EQ(shard.orientation().size(), 17U * 3U);
  EXPECT_EQ(shard.bins_index().size(), 2U * 120U * 2U);

  // ... and they survive a REAL publish. The session-scoped leaves are written
  // ONCE, into the LONG shard; the SHORT shard carries only its own decisions.
  const std::filesystem::path base =
      std::filesystem::path(QR_TEST_SCRATCH_DIR) / "wp8b_native_emit";
  std::error_code error;
  std::filesystem::remove_all(base, error);
  std::array<std::int64_t, 2> published_leaves{};
  for (const qr::emit::Side side : {qr::emit::Side::LONG, qr::emit::Side::SHORT}) {
    const auto dir = qr::emit::c4_shard_dir(base, 125, side);
    ASSERT_TRUE(dir.has_value());
    qr::emit::ShardSpec spec;
    spec.publish_dir = dir.value();
    spec.session_ordinal = 125;
    spec.side = side;
    spec.build_id = "wp8b_native_order";
    auto writer = qr::emit::ShardWriter::begin(spec);
    ASSERT_TRUE(writer.has_value());
    const bool session_leaves = side == qr::emit::Side::LONG;
    ASSERT_TRUE(write_native_order_leaves(*writer.value(), shard, session_leaves).has_value());
    const auto receipt = writer.value()->publish();
    ASSERT_TRUE(receipt.has_value());
    published_leaves[static_cast<std::size_t>(side)] = receipt.value().leaf_count;

    std::ifstream manifest(dir.value() / "manifest.tsv");
    ASSERT_TRUE(manifest.good());
    const std::string text((std::istreambuf_iterator<char>(manifest)),
                           std::istreambuf_iterator<char>());
    EXPECT_NE(text.find("features/recent128_stock_print.npy\t<i4\t2,2"), std::string::npos)
        << text;
    EXPECT_NE(text.find("features/phase_split_stock_print.npy\t<i4\t2,2"), std::string::npos)
        << text;
    EXPECT_NE(text.find("features/bins_index_stock_print.npy\t<i4\t2,120,2"), std::string::npos)
        << text;
    if (session_leaves) {
      EXPECT_NE(text.find("features/groups_stock_print.npy\t<f4\t5,74"), std::string::npos)
          << text;
      EXPECT_NE(text.find("features/group_ts_stock_print.npy\t<i8\t5"), std::string::npos)
          << text;
      EXPECT_NE(text.find("features/orientation_stock_print.npy\t<i4\t17,3"), std::string::npos)
          << text;
    } else {
      // The SHORT shard does NOT restate the session's group table: that is the
      // whole content of the side-neutral ruling.
      EXPECT_EQ(text.find("features/groups_stock_print.npy"), std::string::npos) << text;
      EXPECT_EQ(text.find("features/orientation_stock_print.npy"), std::string::npos) << text;
    }
  }
  EXPECT_EQ(published_leaves[0], 6);
  EXPECT_EQ(published_leaves[1], 3);
  std::filesystem::remove_all(base, error);
}

}  // namespace
}  // namespace qr::carriers
