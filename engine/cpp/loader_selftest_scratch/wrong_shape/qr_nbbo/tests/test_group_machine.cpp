// THE GOLDEN MICRO-TAPE and the four laws the WP5 brief names.
//
// Every expected number below is HAND-COMPUTED, with its arithmetic in the
// comment beside it. Nothing here is a recorded output of the code under test.
//
// The tape is ten equal-millisecond groups covering, in order: a normal tight
// quote; a locked quote; a crossed quote; a zero-priced side; a
// condition-ineligible quote; a three-row group carrying the scalar-means
// discriminator plus a rejected member; a wide-only group; a mixed
// scientific+wide group; a duplicated-member group; and a price above the
// sanity ceiling.
#include <gtest/gtest.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <string>
#include <vector>

#include "nbbo_test_support.hpp"
#include "qr_nbbo/group_machine.hpp"

namespace {

using qr::Validity;
using qr::nbbo::GroupMachine;
using qr::nbbo::kMaxNormalizedNbboPriceU6;
using qr::nbbo::QualityFlags;
using qr::nbbo::QuoteGroups;
using qr::nbbo::QuoteKind;
using qr::nbbo::QuoteState;
using qr::nbbo::SessionPins;
using qr::nbbo::testing::clock_125;
using qr::nbbo::testing::open_ms_125;
using qr::nbbo::testing::pins_for;
using qr::nbbo::testing::quote_row;
using qr::nbbo::testing::rows_of;
using qr::nbbo::testing::run_tape;
using qr::nbbo::testing::TapeGroup;

constexpr std::int64_t kTapeRows = 14;
constexpr std::int64_t kTapeGroups = 10;

/// The golden tape. Group ordinals are the vector's own indices.
std::vector<TapeGroup> golden_tape() {
  const std::int64_t open = open_ms_125();
  return {
      // 0 A: one normal tight quote. bid+ask = 342,010,000 (even) -> mid
      //      171,005,000; spread 10,000 -> 10,000*20,000 = 200,000,000 <=
      //      50*342,010,000 = 17,100,500,000 -> scientific.
      {open + 0, {quote_row(open + 0, 171'000'000, 171'010'000, 500, 700)}},
      // 1 B: LOCKED. ask == bid, so the frozen CSR predicate admits it and the
      //      card's ask>bid law does not.
      {open + 1, {quote_row(open + 1, 171'020'000, 171'020'000, 300, 400)}},
      // 2 C: CROSSED. ask < bid -> rejected by the CSR, typed CROSSED.
      {open + 2, {quote_row(open + 2, 171'050'000, 171'040'000, 100, 200)}},
      // 3 D: a zero-priced ask -> BID_ONLY to the census, NONPOSITIVE typed.
      {open + 3, {quote_row(open + 3, 171'030'000, 0, 500, 600)}},
      // 4 E: bid condition 1 -> NORMAL to the census, CONDITION_INELIGIBLE
      //      typed, rejected by the CSR.
      {open + 4, {quote_row(open + 4, 171'060'000, 171'070'000, 400, 400, 1, 0)}},
      // 5 F: THE SCALAR-MEANS DISCRIMINATOR.
      //      F1 (171,000,000 / 171,000,002): sum 342,000,002 even, spread 2 ->
      //         scientific, member midpoint 171,000,001.
      //      F2 (171,000,001 / 171,000,005): sum 342,000,006 even, spread 4 ->
      //         scientific, member midpoint 171,000,003.
      //      F3 (171,000,010 / 171,000,008): crossed -> rejected, not eligible.
      //      Separate scalar means over the two eligible members:
      //         sum bid = 342,000,001 -> mean 171,000,000 (trunc of ....5)
      //         sum ask = 342,000,007 -> mean 171,000,003 (trunc of ....5)
      //         mid = (171,000,000 + 171,000,003) / 2 = 171,000,001
      //      Mean of the ROW midpoints would be
      //         (171,000,001 + 171,000,003) / 2 = 171,000,002 — one u6 unit
      //      away, which is exactly what the named mutant produces.
      {open + 5,
       {quote_row(open + 5, 171'000'000, 171'000'002, 500, 500),
        quote_row(open + 5, 171'000'001, 171'000'005, 700, 900),
        quote_row(open + 5, 171'000'010, 171'000'008, 300, 300)}},
      // 6 G: WIDE ONLY. spread 2,000,000 -> 2,000,000*20,000 = 40,000,000,000 >
      //      50*342,000,000 = 17,100,000,000.
      {open + 6, {quote_row(open + 6, 170'000'000, 172'000'000, 100, 200)}},
      // 7 H: one scientific + one wide member.
      //      H1 mid 171,105,000 (sum 342,210,000, spread 10,000).
      //      H2 mid 171,000,000 (wide).
      //      means: bid sum 341,100,000 -> 170,550,000; ask sum 343,110,000 ->
      //      171,555,000; mid = 342,105,000 / 2 = 171,052,500.
      {open + 7,
       {quote_row(open + 7, 171'100'000, 171'110'000, 500, 500),
        quote_row(open + 7, 170'000'000, 172'000'000, 100, 100)}},
      // 8 I: the same quote twice. Multiplicity is a fact about the tape (two
      //      scientific members) but the CSR keeps one DISTINCT midpoint.
      {open + 8,
       {quote_row(open + 8, 171'200'000, 171'210'000, 500, 500),
        quote_row(open + 8, 171'200'000, 171'210'000, 500, 500)}},
      // 9 J: an ask one unit above the sanity ceiling -> INVALID / NONFINITE.
      {open + 9, {quote_row(open + 9, 171'300'000, kMaxNormalizedNbboPriceU6 + 1, 500, 500)}},
  };
}

GroupMachine golden_machine() {
  return GroupMachine::from_clock(clock_125(), pins_for(kTapeRows, kTapeGroups));
}

// ---------------------------------------------------------------------------
// The tape, group by group.
// ---------------------------------------------------------------------------

TEST(GoldenTape, EveryGroupResolvesToItsHandComputedRow) {
  GroupMachine machine = golden_machine();
  const auto sealed = run_tape(machine, golden_tape());
  ASSERT_TRUE(sealed.has_value()) << (sealed.has_value() ? "" : sealed.error().message());
  EXPECT_EQ(sealed.value(), kTapeGroups);
  const QuoteGroups& groups = machine.groups();
  ASSERT_EQ(groups.size(), static_cast<std::size_t>(kTapeGroups));

  // --- 0 A -----------------------------------------------------------------
  EXPECT_EQ(groups.raw_member_count[0], 1U);
  EXPECT_EQ(groups.structurally_valid_count[0], 1U);
  EXPECT_EQ(groups.scientific_member_count[0], 1U);
  EXPECT_EQ(groups.wide_member_count[0], 0U);
  EXPECT_EQ(groups.rejected_member_count[0], 0U);
  EXPECT_EQ(groups.has_locked_member[0], 0U);
  EXPECT_EQ(groups.kind[0], QuoteKind::SINGLE_SCIENTIFIC);
  EXPECT_EQ(groups.quality[0].bits, 0U);
  ASSERT_EQ(groups.scientific_midpoints(0).size(), 1U);
  EXPECT_EQ(groups.scientific_midpoints(0)[0], 171'005'000);
  EXPECT_EQ(groups.group_validity[0], Validity::VALID);
  EXPECT_EQ(groups.mean_validity[0], Validity::VALID);
  EXPECT_EQ(groups.eligible_count[0], 1);
  EXPECT_EQ(groups.bid_u6_sum[0], 171'000'000);
  EXPECT_EQ(groups.ask_u6_sum[0], 171'010'000);
  EXPECT_EQ(groups.bid_shares_sum[0], 500);
  EXPECT_EQ(groups.ask_shares_sum[0], 700);
  EXPECT_EQ(groups.mid_u6[0], 171'005'000);
  // No earlier eligible group exists, so the change is MISSING and NOT zero.
  EXPECT_EQ(groups.mid_change_validity[0], Validity::MISSING);
  EXPECT_EQ(groups.prior_validity[0], Validity::MISSING);

  // --- 1 B (locked) --------------------------------------------------------
  EXPECT_EQ(groups.structurally_valid_count[1], 1U);
  EXPECT_EQ(groups.has_locked_member[1], 1U);
  EXPECT_EQ(groups.kind[1], QuoteKind::SINGLE_SCIENTIFIC);
  EXPECT_EQ(groups.quality[1].bits, QualityFlags::LOCKED);
  ASSERT_EQ(groups.scientific_midpoints(1).size(), 1U);
  EXPECT_EQ(groups.scientific_midpoints(1)[0], 171'020'000);
  EXPECT_EQ(groups.group_validity[1], Validity::LOCKED);
  // MASKED: the locked quote supplies no midpoint to the card's channels.
  EXPECT_EQ(groups.mean_validity[1], Validity::MISSING);
  EXPECT_EQ(groups.eligible_count[1], 0);
  EXPECT_EQ(groups.mid_u6[1], 0);
  EXPECT_EQ(groups.bid_u6_sum[1], 0);

  // --- 2 C (crossed) -------------------------------------------------------
  EXPECT_EQ(groups.structurally_valid_count[2], 0U);
  EXPECT_EQ(groups.rejected_member_count[2], 1U);
  EXPECT_EQ(groups.kind[2], QuoteKind::UNRESOLVED);
  EXPECT_EQ(groups.quality[2].bits, QualityFlags::REJECTED_ONLY);
  EXPECT_EQ(groups.group_validity[2], Validity::CROSSED);
  EXPECT_EQ(groups.mean_validity[2], Validity::MISSING);

  // --- 3 D (zero-priced ask) ----------------------------------------------
  EXPECT_EQ(groups.kind[3], QuoteKind::UNRESOLVED);
  EXPECT_EQ(groups.quality[3].bits, QualityFlags::REJECTED_ONLY);
  EXPECT_EQ(groups.group_validity[3], Validity::NONPOSITIVE);

  // --- 4 E (condition ineligible) -----------------------------------------
  EXPECT_EQ(groups.kind[4], QuoteKind::UNRESOLVED);
  EXPECT_EQ(groups.group_validity[4], Validity::CONDITION_INELIGIBLE);
  EXPECT_EQ(groups.eligible_count[4], 0);

  // --- 5 F (the multi-row group) ------------------------------------------
  EXPECT_EQ(groups.raw_member_count[5], 3U);
  EXPECT_EQ(groups.structurally_valid_count[5], 2U);
  EXPECT_EQ(groups.scientific_member_count[5], 2U);
  EXPECT_EQ(groups.rejected_member_count[5], 1U);
  EXPECT_EQ(groups.kind[5], QuoteKind::MULTI_SCIENTIFIC);
  EXPECT_EQ(groups.quality[5].bits, QualityFlags::MIXED_REJECTED);
  ASSERT_EQ(groups.scientific_midpoints(5).size(), 2U);
  EXPECT_EQ(groups.scientific_midpoints(5)[0], 171'000'001);
  EXPECT_EQ(groups.scientific_midpoints(5)[1], 171'000'003);
  EXPECT_EQ(groups.group_validity[5], Validity::CROSSED) << "worst wins over the members";
  EXPECT_EQ(groups.eligible_count[5], 2);
  EXPECT_EQ(groups.bid_u6_sum[5], 342'000'001);
  EXPECT_EQ(groups.ask_u6_sum[5], 342'000'007);
  EXPECT_EQ(groups.bid_shares_sum[5], 1'200);
  EXPECT_EQ(groups.ask_shares_sum[5], 1'400);
  EXPECT_EQ(groups.mid_u6[5], 171'000'001);
  // Its prior is group A — B, C, D and E had no eligible member and therefore
  // never became the prior. 171,000,001 - 171,005,000 = -4,999.
  EXPECT_EQ(groups.mid_change_validity[5], Validity::VALID);
  EXPECT_EQ(groups.mid_change_u6[5], -4'999);

  // --- 6 G (wide only) -----------------------------------------------------
  EXPECT_EQ(groups.wide_member_count[6], 1U);
  EXPECT_EQ(groups.scientific_member_count[6], 0U);
  EXPECT_EQ(groups.kind[6], QuoteKind::WIDE_ONLY);
  EXPECT_EQ(groups.quality[6].bits, QualityFlags::WIDE_SPREAD | QualityFlags::WIDE_ONLY);
  ASSERT_EQ(groups.wide_midpoints(6).size(), 1U);
  EXPECT_EQ(groups.wide_midpoints(6)[0], 171'000'000);
  // A wide spread is still an ELIGIBLE quote: the card's law is ask>bid, not
  // "tight". mid = (170,000,000 + 172,000,000) / 2 = 171,000,000.
  EXPECT_EQ(groups.eligible_count[6], 1);
  EXPECT_EQ(groups.mid_u6[6], 171'000'000);
  EXPECT_EQ(groups.mid_change_u6[6], -1);  // 171,000,000 - 171,000,001

  // --- 7 H (mixed scientific + wide) --------------------------------------
  EXPECT_EQ(groups.scientific_member_count[7], 1U);
  EXPECT_EQ(groups.wide_member_count[7], 1U);
  EXPECT_EQ(groups.kind[7], QuoteKind::SINGLE_SCIENTIFIC);
  EXPECT_EQ(groups.quality[7].bits,
            QualityFlags::WIDE_SPREAD | QualityFlags::MIXED_SCIENTIFIC_WIDE);
  EXPECT_EQ(groups.eligible_count[7], 2);
  EXPECT_EQ(groups.bid_u6_sum[7], 341'100'000);
  EXPECT_EQ(groups.ask_u6_sum[7], 343'110'000);
  EXPECT_EQ(groups.mid_u6[7], 171'052'500);
  EXPECT_EQ(groups.mid_change_u6[7], 52'500);  // 171,052,500 - 171,000,000

  // --- 8 I (duplicate members) --------------------------------------------
  EXPECT_EQ(groups.raw_member_count[8], 2U);
  EXPECT_EQ(groups.scientific_member_count[8], 2U);
  EXPECT_EQ(groups.kind[8], QuoteKind::SINGLE_SCIENTIFIC);
  ASSERT_EQ(groups.scientific_midpoints(8).size(), 1U)
      << "two members, one DISTINCT midpoint: multiplicity is counted, the CSR dedups";
  EXPECT_EQ(groups.scientific_midpoints(8)[0], 171'205'000);
  EXPECT_EQ(groups.eligible_count[8], 2);
  EXPECT_EQ(groups.mid_u6[8], 171'205'000);
  EXPECT_EQ(groups.mid_change_u6[8], 152'500);  // 171,205,000 - 171,052,500

  // --- 9 J (above the sanity ceiling) -------------------------------------
  EXPECT_EQ(groups.kind[9], QuoteKind::UNRESOLVED);
  EXPECT_EQ(groups.quality[9].bits, QualityFlags::REJECTED_ONLY);
  EXPECT_EQ(groups.group_validity[9], Validity::NONFINITE);
  EXPECT_EQ(groups.eligible_count[9], 0);

  // --- the frame-A clock ---------------------------------------------------
  for (std::size_t index = 0; index + 1 < groups.size(); ++index) {
    EXPECT_LT(groups.ts_ns[index], groups.ts_ns[index + 1]);
  }
  const auto expected_first = clock_125().to_frame_a(qr::FrameB{open_ms_125() * 1'000'000});
  ASSERT_TRUE(expected_first.has_value());
  EXPECT_EQ(groups.ts_ns[0], expected_first.value().ns());
}

TEST(GoldenTape, TheCensusIsTheHandComputedOne) {
  GroupMachine machine = golden_machine();
  ASSERT_TRUE(run_tape(machine, golden_tape()).has_value());
  const auto& census = machine.census();

  EXPECT_EQ(census.group_count, kTapeGroups);
  EXPECT_EQ(census.rth_rows, kTapeRows);
  EXPECT_EQ(census.sentinel_rows, 1);
  EXPECT_EQ(census.multi_member_groups, 3);      // F, H, I
  EXPECT_EQ(census.max_group_multiplicity, 3);   // F

  // Seven-way census states: NORMAL = A + E + F1 + F2 + G + H1 + H2 + I x2 = 9.
  EXPECT_EQ(census.state_rows[static_cast<std::size_t>(QuoteState::NORMAL)], 9);
  EXPECT_EQ(census.state_rows[static_cast<std::size_t>(QuoteState::LOCKED)], 1);
  EXPECT_EQ(census.state_rows[static_cast<std::size_t>(QuoteState::CROSSED)], 2);  // C, F3
  EXPECT_EQ(census.state_rows[static_cast<std::size_t>(QuoteState::BID_ONLY)], 1);
  EXPECT_EQ(census.state_rows[static_cast<std::size_t>(QuoteState::ASK_ONLY)], 0);
  EXPECT_EQ(census.state_rows[static_cast<std::size_t>(QuoteState::BOTH_SIDES_ABSENT)], 0);
  EXPECT_EQ(census.state_rows[static_cast<std::size_t>(QuoteState::INVALID)], 1);  // J

  // Typed member histogram: VALID = A + F1 + F2 + G + H1 + H2 + I x2 = 8.
  EXPECT_EQ(census.member_validity[static_cast<std::size_t>(Validity::VALID)], 8);
  EXPECT_EQ(census.member_validity[static_cast<std::size_t>(Validity::LOCKED)], 1);
  EXPECT_EQ(census.member_validity[static_cast<std::size_t>(Validity::CROSSED)], 2);
  EXPECT_EQ(census.member_validity[static_cast<std::size_t>(Validity::NONPOSITIVE)], 1);
  EXPECT_EQ(census.member_validity[static_cast<std::size_t>(Validity::CONDITION_INELIGIBLE)], 1);
  EXPECT_EQ(census.member_validity[static_cast<std::size_t>(Validity::NONFINITE)], 1);
  EXPECT_EQ(census.eligible_rows, 8);

  EXPECT_EQ(census.structurally_valid_rows, 9);  // A B F1 F2 G H1 H2 I x2
  EXPECT_EQ(census.rejected_rows, 5);            // C D E F3 J
  EXPECT_EQ(census.scientific_rows, 7);          // A B F1 F2 H1 I x2
  EXPECT_EQ(census.wide_rows, 2);                // G H2
  EXPECT_EQ(census.groups_with_locked_member, 1);
  EXPECT_EQ(census.scientific_midpoints, 6);     // A1 B1 F2 H1 I1
  EXPECT_EQ(census.wide_midpoints, 2);           // G H

  EXPECT_EQ(census.kind_groups[static_cast<std::size_t>(QuoteKind::SINGLE_SCIENTIFIC)], 4);
  EXPECT_EQ(census.kind_groups[static_cast<std::size_t>(QuoteKind::MULTI_SCIENTIFIC)], 1);
  EXPECT_EQ(census.kind_groups[static_cast<std::size_t>(QuoteKind::WIDE_ONLY)], 1);
  EXPECT_EQ(census.kind_groups[static_cast<std::size_t>(QuoteKind::UNRESOLVED)], 4);

  EXPECT_EQ(census.quality_flag_groups[0], 1);  // LOCKED                B
  EXPECT_EQ(census.quality_flag_groups[1], 2);  // WIDE_SPREAD           G H
  EXPECT_EQ(census.quality_flag_groups[2], 1);  // MIXED_REJECTED        F
  EXPECT_EQ(census.quality_flag_groups[3], 4);  // REJECTED_ONLY         C D E J
  EXPECT_EQ(census.quality_flag_groups[4], 1);  // MIXED_SCIENTIFIC_WIDE H
  EXPECT_EQ(census.quality_flag_groups[5], 1);  // WIDE_ONLY             G

  EXPECT_EQ(census.group_validity[static_cast<std::size_t>(Validity::VALID)], 4);  // A G H I
  EXPECT_EQ(census.group_validity[static_cast<std::size_t>(Validity::CROSSED)], 2);  // C F
  EXPECT_EQ(census.groups_without_eligible_member, 5);  // B C D E J
  EXPECT_EQ(census.groups_without_prior_state, 1);      // only A

  // The RTH-only projection: every retained row is RTH, and that is asserted
  // rather than assumed.
  EXPECT_EQ(census.domain_rows[static_cast<std::size_t>(qr::nbbo::QuoteDomain::RTH)], kTapeRows);
  for (std::size_t index = 0; index < qr::nbbo::kQuoteDomainCount; ++index) {
    if (index == static_cast<std::size_t>(qr::nbbo::QuoteDomain::RTH)) {
      continue;
    }
    EXPECT_EQ(census.domain_rows[index], 0);
  }
  EXPECT_EQ(census.compact_rows, kTapeRows);
  EXPECT_EQ(census.wide_profile_rows, 0);

  // Cross-checks that must hold on ANY tape, printed here on this one.
  EXPECT_EQ(census.structurally_valid_rows + census.rejected_rows, census.rth_rows);
  EXPECT_EQ(census.scientific_rows + census.wide_rows, census.structurally_valid_rows);
  std::int64_t states = 0;
  for (const std::int64_t count : census.state_rows) {
    states += count;
  }
  EXPECT_EQ(states, census.rth_rows);
  std::int64_t typed = 0;
  for (const std::int64_t count : census.member_validity) {
    typed += count;
  }
  EXPECT_EQ(typed, census.rth_rows);
}

// ---------------------------------------------------------------------------
// LAW 1 — separate scalar means, then derive (task card V4 section 4).
// ---------------------------------------------------------------------------

TEST(ScalarMeansLaw, TheMidpointIsDerivedFromTheSeparateMeansAndNeverFromRowMidpoints) {
  GroupMachine machine = golden_machine();
  ASSERT_TRUE(run_tape(machine, golden_tape()).has_value());
  const QuoteGroups& groups = machine.groups();

  // The law, on group F's two eligible members:
  //   mean(bid) = floor(342,000,001 / 2) = 171,000,000
  //   mean(ask) = floor(342,000,007 / 2) = 171,000,003
  //   mid       = floor((171,000,000 + 171,000,003) / 2) = 171,000,001
  const auto scalars = groups.scalars(5);
  ASSERT_EQ(scalars.bid_u6.mean().value, 171'000'000);
  ASSERT_EQ(scalars.ask_u6.mean().value, 171'000'003);
  const auto mid = scalars.mid_u6();
  ASSERT_TRUE(mid.has_value());
  EXPECT_EQ(mid.value().value, 171'000'001);
  EXPECT_EQ(groups.mid_u6[5], 171'000'001);

  // THE NAMED MUTANT'S ANSWER, computed here from the same two rows so the
  // contrast is visible rather than asserted:
  //   row midpoints 171,000,001 and 171,000,003
  //   mean of them  = floor(342,000,004 / 2) = 171,000,002
  const std::int64_t mean_of_row_midpoints = ((171'000'000 + 171'000'002) / 2 +
                                              (171'000'001 + 171'000'005) / 2) /
                                             2;
  EXPECT_EQ(mean_of_row_midpoints, 171'000'002);
  EXPECT_NE(groups.mid_u6[5], mean_of_row_midpoints)
      << "the projection is averaging row-derived midpoints, which card V4 section 4 forbids";

  // The size means are separate primitives too: 1,200/2 and 1,400/2.
  EXPECT_EQ(scalars.bid_shares.mean().value, 600);
  EXPECT_EQ(scalars.ask_shares.mean().value, 700);
  // And the spread is derived after the means, not averaged across rows:
  // 171,000,003 - 171,000,000 = 3, while the row spreads are 2 and 4.
  const auto spread = scalars.spread_u6();
  ASSERT_TRUE(spread.has_value());
  EXPECT_EQ(spread.value().value, 3);
}

TEST(ScalarMeansLaw, AGroupWithNoEligibleMemberHasMissingMeansAndAMaskedZero) {
  GroupMachine machine = golden_machine();
  ASSERT_TRUE(run_tape(machine, golden_tape()).has_value());
  const QuoteGroups& groups = machine.groups();
  for (const std::size_t index : {1U, 2U, 3U, 4U, 9U}) {
    EXPECT_EQ(groups.eligible_count[index], 0) << "group " << index;
    EXPECT_EQ(groups.mean_validity[index], Validity::MISSING) << "group " << index;
    EXPECT_EQ(groups.mid_u6[index], 0) << "group " << index;
    EXPECT_EQ(groups.scalars(index).bid_u6.mean().v, Validity::MISSING) << "group " << index;
    EXPECT_EQ(groups.mid_change_validity[index], Validity::MISSING) << "group " << index;
  }
}

// ---------------------------------------------------------------------------
// LAW 1b — the depth imbalance, composed from the same separate size means
// (orchestrator ruling CC-005).
// ---------------------------------------------------------------------------

TEST(ImbalanceLaw, ItIsTheSignedSizeRatioOfTheTwoSeparateSizeMeans) {
  GroupMachine machine = golden_machine();
  ASSERT_TRUE(run_tape(machine, golden_tape()).has_value());
  const QuoteGroups& groups = machine.groups();

  // Group A: one member, 500 bid / 700 ask shares.
  //   (500 - 700) / (500 + 700) = -200 / 1,200
  const auto group_a = groups.scalars(0).imbalance();
  ASSERT_TRUE(group_a.has_value());
  EXPECT_EQ(group_a.value().v, Validity::VALID);
  EXPECT_DOUBLE_EQ(group_a.value().value, -200.0 / 1200.0);

  // Group F: two eligible members, size sums 1,200 and 1,400 -> means 600 and
  //   700, so (600 - 700) / (600 + 700) = -100 / 1,300. The means come first:
  //   the per-row imbalances are (500-500)/1000 = 0 and (700-900)/1600 =
  //   -0.125, whose mean is -0.0625, a different number.
  const auto group_f = groups.scalars(5).imbalance();
  ASSERT_TRUE(group_f.has_value());
  EXPECT_DOUBLE_EQ(group_f.value().value, -100.0 / 1300.0);
  EXPECT_NE(group_f.value().value, (0.0 + -0.125) / 2.0);

  // Group G: 100 / 200 -> -100 / 300.
  const auto group_g = groups.scalars(6).imbalance();
  ASSERT_TRUE(group_g.has_value());
  EXPECT_DOUBLE_EQ(group_g.value().value, -100.0 / 300.0);

  // Groups H and I are balanced books: exactly zero, not "nearly".
  for (const std::size_t index : {7U, 8U}) {
    const auto balanced = groups.scalars(index).imbalance();
    ASSERT_TRUE(balanced.has_value()) << "group " << index;
    EXPECT_EQ(balanced.value().v, Validity::VALID) << "group " << index;
    EXPECT_DOUBLE_EQ(balanced.value().value, 0.0) << "group " << index;
  }

  // Every group with no eligible member has no imbalance either — MISSING,
  // with a masked zero rather than a zero that reads as "balanced".
  for (const std::size_t index : {1U, 2U, 3U, 4U, 9U}) {
    const auto missing = groups.scalars(index).imbalance();
    ASSERT_TRUE(missing.has_value()) << "group " << index;
    EXPECT_EQ(missing.value().v, Validity::MISSING) << "group " << index;
    EXPECT_DOUBLE_EQ(missing.value().value, 0.0) << "group " << index;
  }
}

TEST(ImbalanceLaw, ItIsBoundedByPlusMinusOneAndAZeroDenominatorIsTypedMissing) {
  const auto imbalance_of = [](std::int64_t bid_sum, std::int64_t ask_sum, std::int64_t count) {
    qr::nbbo::GroupScalars scalars;
    scalars.bid_u6 = qr::nbbo::ScalarMean{0, count};
    scalars.ask_u6 = qr::nbbo::ScalarMean{0, count};
    scalars.bid_shares = qr::nbbo::ScalarMean{bid_sum, count};
    scalars.ask_shares = qr::nbbo::ScalarMean{ask_sum, count};
    return scalars.imbalance();
  };
  // All depth on one side is the envelope, and it is reached exactly.
  const auto all_bid = imbalance_of(500, 0, 1);
  ASSERT_TRUE(all_bid.has_value());
  EXPECT_DOUBLE_EQ(all_bid.value().value, 1.0);
  const auto all_ask = imbalance_of(0, 500, 1);
  ASSERT_TRUE(all_ask.has_value());
  EXPECT_DOUBLE_EQ(all_ask.value().value, -1.0);
  // Nothing between the sides can leave [-1, 1].
  for (std::int64_t bid = 0; bid <= 1'000; bid += 137) {
    for (std::int64_t ask = 0; ask <= 1'000; ask += 149) {
      const auto value = imbalance_of(bid, ask, 1);
      ASSERT_TRUE(value.has_value());
      if (value.value().v == Validity::VALID) {
        EXPECT_GE(value.value().value, -1.0) << bid << "/" << ask;
        EXPECT_LE(value.value().value, 1.0) << bid << "/" << ask;
      }
    }
  }
  // A ZERO DENOMINATOR IS TYPED MISSING, never a division (the ruling).
  const auto degenerate = imbalance_of(0, 0, 1);
  ASSERT_TRUE(degenerate.has_value());
  EXPECT_EQ(degenerate.value().v, Validity::MISSING);
  EXPECT_DOUBLE_EQ(degenerate.value().value, 0.0);
  EXPECT_FALSE(std::isnan(degenerate.value().value));
  // And so is an absent group (count 0), for the same reason.
  const auto absent = imbalance_of(0, 0, 0);
  ASSERT_TRUE(absent.has_value());
  EXPECT_EQ(absent.value().v, Validity::MISSING);
}

// ---------------------------------------------------------------------------
// LAW 2 — the prior updates only after the complete group.
// ---------------------------------------------------------------------------

TEST(PriorStateLaw, ThePriorIsFrozenForTheWholeGroupAndMovesOnlyAfterIt) {
  GroupMachine machine = golden_machine();
  const std::vector<TapeGroup> tape = golden_tape();

  ASSERT_TRUE(machine.push_group(tape[0].ts_ms_b, tape[0].rows).has_value());
  EXPECT_TRUE(machine.prior().present);
  EXPECT_EQ(machine.prior().ts_ms_b, tape[0].ts_ms_b);
  EXPECT_EQ(machine.prior().scalars.bid_u6.sum, 171'000'000);
  EXPECT_EQ(machine.prior().scalars.bid_u6.count, 1);

  // B..E have no eligible member, so none of them may become the prior — the
  // law names the nearest strictly-earlier ELIGIBLE group.
  for (std::size_t index = 1; index <= 4; ++index) {
    ASSERT_TRUE(machine.push_group(tape[index].ts_ms_b, tape[index].rows).has_value());
    EXPECT_EQ(machine.prior().ts_ms_b, tape[0].ts_ms_b) << "group " << index << " moved the prior";
    EXPECT_EQ(machine.prior().scalars.bid_u6.sum, 171'000'000);
  }

  // F is a three-row group. After it, the prior is F's COMPLETE reduction —
  // count 2 (its two eligible members), never a partial count of 1.
  ASSERT_TRUE(machine.push_group(tape[5].ts_ms_b, tape[5].rows).has_value());
  EXPECT_EQ(machine.prior().ts_ms_b, tape[5].ts_ms_b);
  EXPECT_EQ(machine.prior().scalars.bid_u6.count, 2);
  EXPECT_EQ(machine.prior().scalars.bid_u6.sum, 342'000'001);
  EXPECT_EQ(machine.prior().scalars.ask_u6.sum, 342'000'007);
  // And the change F published was measured against A, the frozen prior it
  // was reduced under: 171,000,001 - 171,005,000 = -4,999.
  EXPECT_EQ(machine.groups().mid_change_u6[5], -4'999);
  EXPECT_EQ(machine.groups().prior_ts_ns[5], machine.groups().ts_ns[0]);
}

TEST(PriorStateLaw, EveryChangeIsMeasuredAgainstTheNearestEarlierEligibleGroup) {
  GroupMachine machine = golden_machine();
  ASSERT_TRUE(run_tape(machine, golden_tape()).has_value());
  const QuoteGroups& groups = machine.groups();
  // The eligible groups are 0, 5, 6, 7, 8 — the chain the changes must follow.
  EXPECT_EQ(groups.prior_validity[0], Validity::MISSING);
  EXPECT_EQ(groups.prior_ts_ns[5], groups.ts_ns[0]);
  EXPECT_EQ(groups.prior_ts_ns[6], groups.ts_ns[5]);
  EXPECT_EQ(groups.prior_ts_ns[7], groups.ts_ns[6]);
  EXPECT_EQ(groups.prior_ts_ns[8], groups.ts_ns[7]);
  EXPECT_EQ(groups.prior_ts_ns[9], groups.ts_ns[8]);
  // Ineligible groups still SEE a prior (B..E all see A) — they simply never
  // become one.
  for (const std::size_t index : {1U, 2U, 3U, 4U}) {
    EXPECT_EQ(groups.prior_ts_ns[index], groups.ts_ns[0]) << "group " << index;
    EXPECT_EQ(groups.prior_validity[index], Validity::VALID) << "group " << index;
  }
}

// ---------------------------------------------------------------------------
// LAW 3 — permutation invariance, and LAW 4 — two-run identity.
// ---------------------------------------------------------------------------

std::vector<std::uint8_t> run_and_serialize(const std::vector<TapeGroup>& tape,
                                            std::string& census_tsv,
                                            std::vector<double>& imbalances) {
  GroupMachine machine = golden_machine();
  EXPECT_TRUE(run_tape(machine, tape).has_value());
  census_tsv = machine.census().to_tsv("tape");
  // The imbalance is a COMPOSED ACCESSOR and so is not in the serialized byte
  // string; it is compared here explicitly, or a permutation could move it
  // without any fixture noticing.
  imbalances.clear();
  for (std::size_t index = 0; index < machine.groups().size(); ++index) {
    const auto value = machine.groups().scalars(index).imbalance();
    EXPECT_TRUE(value.has_value());
    imbalances.push_back(value.has_value() ? value.value().value : 0.0);
    imbalances.push_back(static_cast<double>(
        value.has_value() ? static_cast<int>(value.value().v) : -1));
  }
  return machine.serialize();
}

TEST(PermutationInvariance, PermutingRowsInsideEveryEqualTimeGroupChangesNothing) {
  std::string base_census;
  std::vector<double> base_imbalance;
  const std::vector<std::uint8_t> base =
      run_and_serialize(golden_tape(), base_census, base_imbalance);
  ASSERT_FALSE(base.empty());
  ASSERT_FALSE(base_imbalance.empty());

  // Every permutation of the three-row group, and both of the two-row groups.
  std::vector<std::size_t> order{0, 1, 2};
  int permutations = 0;
  do {
    std::vector<TapeGroup> tape = golden_tape();
    const std::vector<qr::sources::StockQuoteRow> rows = tape[5].rows;
    for (std::size_t index = 0; index < order.size(); ++index) {
      tape[5].rows[index] = rows[order[index]];
    }
    std::swap(tape[7].rows[0], tape[7].rows[1]);
    std::swap(tape[8].rows[0], tape[8].rows[1]);
    std::string census;
    std::vector<double> imbalance;
    const std::vector<std::uint8_t> permuted = run_and_serialize(tape, census, imbalance);
    EXPECT_EQ(base, permuted) << "permutation " << permutations << " changed the projection";
    EXPECT_EQ(base_census, census) << "permutation " << permutations << " changed the census";
    EXPECT_EQ(base_imbalance, imbalance)
        << "permutation " << permutations << " changed a group imbalance";
    ++permutations;
  } while (std::next_permutation(order.begin(), order.end()));
  EXPECT_EQ(permutations, 6);
}

TEST(Determinism, TwoRunsOverTheSameTapeAreByteIdentical) {
  std::string first_census;
  std::string second_census;
  std::vector<double> first_imbalance;
  std::vector<double> second_imbalance;
  const std::vector<std::uint8_t> first =
      run_and_serialize(golden_tape(), first_census, first_imbalance);
  const std::vector<std::uint8_t> second =
      run_and_serialize(golden_tape(), second_census, second_imbalance);
  ASSERT_FALSE(first.empty());
  EXPECT_EQ(first, second);
  EXPECT_EQ(first_census, second_census);
  EXPECT_EQ(first_imbalance, second_imbalance);
}

// ---------------------------------------------------------------------------
// The registry oracle and the structural walls.
// ---------------------------------------------------------------------------

TEST(RegistryOracle, TheSealRefusesWhenEitherPinnedCountDisagrees) {
  {
    GroupMachine machine =
        GroupMachine::from_clock(clock_125(), pins_for(kTapeRows + 1, kTapeGroups));
    const auto sealed = run_tape(machine, golden_tape());
    ASSERT_FALSE(sealed.has_value());
    EXPECT_EQ(sealed.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
  }
  {
    GroupMachine machine =
        GroupMachine::from_clock(clock_125(), pins_for(kTapeRows, kTapeGroups + 1));
    const auto sealed = run_tape(machine, golden_tape());
    ASSERT_FALSE(sealed.has_value());
    EXPECT_EQ(sealed.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
  }
}

TEST(RegistryOracle, TheGroupCountIsALiveWallAndNotOnlyAFinalCheck) {
  // Pinned one group short: the machine must refuse the group that would
  // exceed the registry's count, not discover it at the seal.
  GroupMachine machine = GroupMachine::from_clock(clock_125(), pins_for(kTapeRows, kTapeGroups - 1));
  const std::vector<TapeGroup> tape = golden_tape();
  for (std::size_t index = 0; index + 1 < tape.size(); ++index) {
    ASSERT_TRUE(machine.push_group(tape[index].ts_ms_b, tape[index].rows).has_value())
        << "group " << index;
  }
  const auto refused = machine.push_group(tape.back().ts_ms_b, tape.back().rows);
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}

TEST(OrderLaw, ASplitEqualTimeRunAndADescendingTapeAreBothRefused) {
  const std::int64_t open = open_ms_125();
  {
    GroupMachine machine = GroupMachine::from_clock(clock_125(), pins_for(2, 2));
    ASSERT_TRUE(machine.push_group(open, rows_of({quote_row(open, 171'000'000, 171'010'000, 500, 500)}))
                    .has_value());
    // The same millisecond arriving as a SECOND group means an equal-time run
    // was split — one millisecond is one group, by definition.
    const auto refused =
        machine.push_group(open, rows_of({quote_row(open, 171'000'002, 171'010'002, 500, 500)}));
    ASSERT_FALSE(refused.has_value());
    EXPECT_EQ(refused.error().code(), qr::RefusalCode::OUT_OF_ORDER);
  }
  {
    GroupMachine machine = GroupMachine::from_clock(clock_125(), pins_for(2, 2));
    ASSERT_TRUE(machine.push_group(open + 5, rows_of({quote_row(open + 5, 171'000'000, 171'010'000, 5, 5)}))
                    .has_value());
    const auto refused =
        machine.push_group(open + 4, rows_of({quote_row(open + 4, 171'000'000, 171'010'000, 5, 5)}));
    ASSERT_FALSE(refused.has_value());
    EXPECT_EQ(refused.error().code(), qr::RefusalCode::OUT_OF_ORDER);
  }
}

TEST(StructuralWalls, NonRthEmptyAndMisstampedGroupsAreAllRefused) {
  const std::int64_t open = open_ms_125();
  GroupMachine machine = GroupMachine::from_clock(clock_125(), pins_for(1, 1));
  {  // one minute before the open: the reader's RTH filter and the clock must
     // agree, and a disagreement is a refusal rather than a dropped row.
    const std::int64_t before = open - 60'000;
    const auto refused =
        machine.push_group(before, rows_of({quote_row(before, 171'000'000, 171'010'000, 500, 500)}));
    ASSERT_FALSE(refused.has_value());
    EXPECT_EQ(refused.error().code(), qr::RefusalCode::OUTSIDE_RTH);
  }
  {  // a group with no members at all
    const auto refused = machine.push_group(open, rows_of({}));
    ASSERT_FALSE(refused.has_value());
    EXPECT_EQ(refused.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
  }
  {  // a member carrying another millisecond
    const auto refused =
        machine.push_group(open, rows_of({quote_row(open + 1, 171'000'000, 171'010'000, 500, 500)}));
    ASSERT_FALSE(refused.has_value());
    EXPECT_EQ(refused.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
  }
}

TEST(CsrInvariant, EveryOffsetsArrayCarriesExactlyOnePlusSizeEntries) {
  QuoteGroups empty;
  EXPECT_EQ(empty.size(), 0U);
  ASSERT_EQ(empty.scientific_midpoint_offsets.size(), 1U)
      << "the empty projection's offsets are {0}, never {}";
  EXPECT_EQ(empty.scientific_midpoint_offsets[0], 0U);
  ASSERT_EQ(empty.wide_midpoint_offsets.size(), 1U);

  GroupMachine machine = golden_machine();
  ASSERT_TRUE(run_tape(machine, golden_tape()).has_value());
  const QuoteGroups& groups = machine.groups();
  EXPECT_EQ(groups.scientific_midpoint_offsets.size(), groups.size() + 1);
  EXPECT_EQ(groups.wide_midpoint_offsets.size(), groups.size() + 1);
  // And the slices they describe tile their arrays exactly.
  std::size_t scientific = 0;
  std::size_t wide = 0;
  for (std::size_t index = 0; index < groups.size(); ++index) {
    scientific += groups.scientific_midpoints(index).size();
    wide += groups.wide_midpoints(index).size();
  }
  EXPECT_EQ(scientific, groups.scientific_midpoints_u6.size());
  EXPECT_EQ(wide, groups.wide_midpoints_u6.size());
}

}  // namespace
