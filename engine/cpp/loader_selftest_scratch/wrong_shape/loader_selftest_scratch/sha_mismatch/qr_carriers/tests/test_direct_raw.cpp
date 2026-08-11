// test_direct_raw.cpp — DIRECT_RAW's 60 columns, its window law, and the two
// production-constructor controls that live in it:
//   * "group moved across newest-visibility equality (phase counts change only
//     as specified)";
//   * "token on cutoff boundary (excluded)".
//
// Every expected value is hand arithmetic in the comment beside it.
#include <gtest/gtest.h>

#include <cmath>

#include "carriers_test_support.hpp"
#include "qr_carriers/direct_raw.hpp"

namespace qr::carriers {
namespace {

using testing::clock_125;
using testing::frame_a_of;
using testing::open_ms;
using testing::quote_row;
using testing::rows_of;
using testing::trade_row;

/// A hand-built group record with all four mechanisms present, so the window
/// laws can be exercised without dragging a whole tape behind them.
GroupRecord group_at(std::int64_t ts_ns_a, std::int32_t tokens, double mechanism_value,
                     bool all_four = true) {
  GroupRecord group;
  group.ts_ns_a = ts_ns_a;
  group.token_count = tokens;
  group.log1p_multiplicity = std::log1p(static_cast<double>(tokens));
  for (std::size_t index = 0; index < kMechanismCount; ++index) {
    const bool present_bit = all_four || index == 0;
    group.set_mechanism(Side::LONG, index,
                        present_bit ? present(mechanism_value) : masked(Validity::MISSING));
    group.set_mechanism(Side::SHORT, index,
                        present_bit ? present(-mechanism_value) : masked(Validity::MISSING));
  }
  return group;
}

DecisionWindow window_at(std::int64_t cutoff_ns_a, Side side = Side::LONG) {
  DecisionWindow window;
  window.cutoff_ns_a = cutoff_ns_a;
  window.session_open_ns_a = clock_125().session_start_a().ns();
  window.side = side;
  return window;
}

TEST(DirectRawShape, ThereAreExactlySixtyColumnsAndEveryOneIsNamed) {
  // "Exactly 60 columns/modality" — 4 windows x 10 + 20.
  EXPECT_EQ(kDirectColumnCount, 60U);
  EXPECT_EQ(kDirectWindowCount * kDirectPerWindowColumns, 40U);
  EXPECT_EQ(kDirectFullWindowColumns, 20U);
  EXPECT_EQ(kDirectFullWindowOffset, 40U);

  DirectRawRow row;
  EXPECT_EQ(row.value.size(), 60U);
  EXPECT_EQ(row.validity.size(), 60U);

  // Every column has a distinct frozen name, per modality.
  for (const Modality modality :
       {Modality::STOCK_PRINT, Modality::STOCK_NBBO, Modality::OPTION_PRINT}) {
    std::vector<std::string> names;
    for (std::size_t column = 0; column < kDirectColumnCount; ++column) {
      names.push_back(direct_column_name(modality, column));
    }
    EXPECT_EQ(names.size(), 60U);
    std::sort(names.begin(), names.end());
    EXPECT_EQ(std::unique(names.begin(), names.end()), names.end())
        << modality_name(modality) << " repeated a DIRECT column name";
  }
  // The four windows are the card's own {1,5,30,120}s, in that order.
  EXPECT_EQ(kDirectWindowSeconds[0], 1);
  EXPECT_EQ(kDirectWindowSeconds[1], 5);
  EXPECT_EQ(kDirectWindowSeconds[2], 30);
  EXPECT_EQ(kDirectWindowSeconds[3], 120);
}

TEST(DirectRawWindow, AnEmptyWindowHasZeroCountAndMaskedValidMeanAndLast) {
  // "For an empty window count/valid/mean/last are 0 and the full-window
  // nonempty bit is 0."
  std::vector<GroupRecord> groups;
  DirectRawBuilder builder(Modality::STOCK_PRINT, groups);
  const auto row = builder.build(window_at(frame_a_of(60'000)));
  ASSERT_TRUE(row.has_value());

  for (std::size_t index = 0; index < kDirectWindowCount; ++index) {
    const std::size_t offset = direct_window_offset(index);
    // A count of zero is a MEASURED zero: log1p(0) = 0, present.
    EXPECT_TRUE(row.value().presence(offset + 0));
    EXPECT_DOUBLE_EQ(row.value().value[offset + 0], 0.0);
    // Everything with a group denominator is value0/presence0.
    EXPECT_FALSE(row.value().presence(offset + 1));
    for (std::size_t mech = 0; mech < kMechanismCount; ++mech) {
      EXPECT_FALSE(row.value().presence(offset + 2 + 2 * mech));
      EXPECT_FALSE(row.value().presence(offset + 3 + 2 * mech));
      EXPECT_DOUBLE_EQ(row.value().value[offset + 2 + 2 * mech], 0.0);
      EXPECT_DOUBLE_EQ(row.value().value[offset + 3 + 2 * mech], 0.0);
    }
  }
  const std::size_t base = kDirectFullWindowOffset;
  EXPECT_DOUBLE_EQ(row.value().value[base + kDirectNonempty], 0.0);
  EXPECT_TRUE(row.value().presence(base + kDirectNonempty));  // a structural bit
  // r_modality is the ONE declared present-with-zero fraction.
  EXPECT_TRUE(row.value().presence(base + kDirectRModality));
  EXPECT_DOUBLE_EQ(row.value().value[base + kDirectRModality], 0.0);
  EXPECT_FALSE(row.value().presence(base + kDirectAllFourFiniteGroupFraction));
}

TEST(DirectRawWindow, TheFourNestedWindowsSelectExactlyTheirOwnGroups) {
  // Groups at cutoff-0.5s, -3s, -20s, -100s and -200s. The cutoff is at 300s.
  const std::int64_t cutoff = frame_a_of(300'000);
  std::vector<GroupRecord> groups{
      group_at(frame_a_of(100'000), 1, 5.0),   // 200s before: outside every window
      group_at(frame_a_of(200'000), 1, 4.0),   // 100s before: 120s window only
      group_at(frame_a_of(280'000), 1, 3.0),   // 20s:  30s and 120s
      group_at(frame_a_of(297'000), 1, 2.0),   // 3s:   5s, 30s, 120s
      group_at(frame_a_of(299'500), 1, 1.0),   // 0.5s: every window
  };
  DirectRawBuilder builder(Modality::STOCK_PRINT, groups);
  const auto row = builder.build(window_at(cutoff));
  ASSERT_TRUE(row.has_value());

  // Window token counts: 1s -> 1, 5s -> 2, 30s -> 3, 120s -> 4.
  EXPECT_DOUBLE_EQ(row.value().value[direct_window_offset(0)], std::log1p(1.0));
  EXPECT_DOUBLE_EQ(row.value().value[direct_window_offset(1)], std::log1p(2.0));
  EXPECT_DOUBLE_EQ(row.value().value[direct_window_offset(2)], std::log1p(3.0));
  EXPECT_DOUBLE_EQ(row.value().value[direct_window_offset(3)], std::log1p(4.0));

  // Mechanism 0's window MEAN: 1s -> 1; 5s -> (2+1)/2 = 1.5;
  // 30s -> (3+2+1)/3 = 2; 120s -> (4+3+2+1)/4 = 2.5.
  EXPECT_DOUBLE_EQ(row.value().value[direct_window_offset(0) + 2], 1.0);
  EXPECT_DOUBLE_EQ(row.value().value[direct_window_offset(1) + 2], 1.5);
  EXPECT_DOUBLE_EQ(row.value().value[direct_window_offset(2) + 2], 2.0);
  EXPECT_DOUBLE_EQ(row.value().value[direct_window_offset(3) + 2], 2.5);

  // Mechanism 0's `last` is "the greatest strictly-prior timestamp group" of the
  // window — the 0.5s-old group, so 1.0 in all four.
  for (std::size_t index = 0; index < kDirectWindowCount; ++index) {
    EXPECT_DOUBLE_EQ(row.value().value[direct_window_offset(index) + 3], 1.0);
  }
  // The 200s-old group is outside the 120s carrier entirely.
  const std::size_t base = kDirectFullWindowOffset;
  EXPECT_DOUBLE_EQ(row.value().value[base + kDirectLog1pGroupCount], std::log1p(4.0));
}

TEST(DirectRawWindow, LastIsTheGreatestStrictlyPriorGroupEvenWhenThatGroupsValueIsAbsent) {
  // "its `last` is the greatest strictly-prior timestamp group" — WHICH group
  // supplies the value, not "the newest group that happens to carry one". The
  // most recent group here has no mechanism value at all, so `last` is masked
  // even though an earlier group in the same window does carry one.
  const std::int64_t cutoff = frame_a_of(300'000);
  std::vector<GroupRecord> groups{
      group_at(frame_a_of(290'000), 1, 5.0),
      group_at(frame_a_of(298'000), 1, 0.0, /*all_four=*/false),
  };
  // Strip mechanism 0 from the newest group as well, so nothing at all is there.
  groups[1].set_mechanism(Side::LONG, 0, masked(Validity::MISSING));
  groups[1].set_mechanism(Side::SHORT, 0, masked(Validity::MISSING));
  groups[1].mechanism_present_long = 0;
  groups[1].mechanism_present_short = 0;

  DirectRawBuilder builder(Modality::STOCK_PRINT, groups);
  const auto row = builder.build(window_at(cutoff));
  ASSERT_TRUE(row.has_value());
  const std::size_t last_column = direct_window_offset(3) + 3;
  EXPECT_FALSE(row.value().presence(last_column));
  EXPECT_DOUBLE_EQ(row.value().value[last_column], 0.0);
  // The window MEAN still uses the earlier group's value: 5.0 over one present
  // member — `last` and `mean` are different statistics with different laws.
  EXPECT_DOUBLE_EQ(row.value().value[direct_window_offset(3) + 2], 5.0);
}

TEST(DirectRawWindow, ATokenExactlyOnTheCutoffIsExcludedAndOneMillisecondEarlierIsNot) {
  // THE BRIEF'S CONTROL. "Feature windows are [max(session_open, decision-120s),
  // decision)" and "Current/equal-cutoff tokens are excluded".
  const std::int64_t cutoff = frame_a_of(300'000);
  const std::vector<GroupRecord> on_boundary{group_at(cutoff, 1, 9.0)};
  const std::vector<GroupRecord> just_before{group_at(frame_a_of(299'999), 1, 9.0)};

  DirectRawBuilder excluded(Modality::STOCK_PRINT, on_boundary);
  DirectRawBuilder included(Modality::STOCK_PRINT, just_before);
  const auto excluded_row = excluded.build(window_at(cutoff));
  const auto included_row = included.build(window_at(cutoff));
  ASSERT_TRUE(excluded_row.has_value());
  ASSERT_TRUE(included_row.has_value());

  const std::size_t base = kDirectFullWindowOffset;
  EXPECT_DOUBLE_EQ(excluded_row.value().value[base + kDirectNonempty], 0.0);
  EXPECT_DOUBLE_EQ(excluded_row.value().value[base + kDirectLog1pTokenCount], 0.0);
  EXPECT_DOUBLE_EQ(included_row.value().value[base + kDirectNonempty], 1.0);
  EXPECT_DOUBLE_EQ(included_row.value().value[base + kDirectLog1pTokenCount], std::log1p(1.0));
  // The excluded token contributes nothing to any window's mean either.
  EXPECT_FALSE(excluded_row.value().presence(direct_window_offset(0) + 2));
  EXPECT_DOUBLE_EQ(included_row.value().value[direct_window_offset(0) + 2], 9.0);
}

TEST(DirectRawFullWindow, TheTwentyStatisticsAreTheCardsTwentyStatistics) {
  const std::int64_t cutoff = frame_a_of(300'000);
  // Three groups: multiplicities 1, 3, 2 at 100s, 40s and 10s before the cutoff.
  std::vector<GroupRecord> groups{
      group_at(frame_a_of(200'000), 1, 2.0),
      group_at(frame_a_of(260'000), 3, 4.0),
      group_at(frame_a_of(290'000), 2, 6.0),
  };
  // Gaps: 60s and 30s -> 60'000'000us and 30'000'000us.
  groups[1].has_gap = true;
  groups[1].log1p_gap_micros = std::log1p(60'000'000.0);
  groups[2].has_gap = true;
  groups[2].log1p_gap_micros = std::log1p(30'000'000.0);
  // One absent value cell in the middle group, over 17 declared channels.
  groups[1].absent_value_cells = 1;
  // One unusable-attachment token in the last group, and one sequence pair with
  // an inversion in the middle one.
  groups[2].unusable_attachment_tokens = 1;
  groups[1].sequence_pair = true;
  groups[1].sequence_inversion = true;
  groups[2].sequence_pair = true;

  DirectRawBuilder builder(Modality::STOCK_PRINT, groups);
  const auto row = builder.build(window_at(cutoff));
  ASSERT_TRUE(row.has_value());
  const auto& value = row.value().value;
  const std::size_t base = kDirectFullWindowOffset;

  //  0 log1p token count: 1 + 3 + 2 = 6
  EXPECT_DOUBLE_EQ(value[base + kDirectLog1pTokenCount], std::log1p(6.0));
  //  1 log1p timestamp-group count: 3
  EXPECT_DOUBLE_EQ(value[base + kDirectLog1pGroupCount], std::log1p(3.0));
  //  2 nonempty
  EXPECT_DOUBLE_EQ(value[base + kDirectNonempty], 1.0);
  //  3 all-four-finite group fraction: 3/3 = 1
  EXPECT_DOUBLE_EQ(value[base + kDirectAllFourFiniteGroupFraction], 1.0);
  //  4 raw missing fraction: 1 absent cell / (6 tokens * 17 channels) = 1/102
  EXPECT_DOUBLE_EQ(value[base + kDirectRawMissingFraction], 1.0 / 102.0);
  //  5 multi-token-group fraction: 2 of 3 groups have multiplicity > 1
  EXPECT_DOUBLE_EQ(value[base + kDirectMultiTokenGroupFraction], 2.0 / 3.0);
  //  6 mean log1p multiplicity: (log1p(1)+log1p(3)+log1p(2))/3
  EXPECT_NEAR(value[base + kDirectMeanLog1pMultiplicity],
              (std::log1p(1.0) + std::log1p(3.0) + std::log1p(2.0)) / 3.0, 1e-15);
  //  7 max log1p multiplicity: log1p(3)
  EXPECT_DOUBLE_EQ(value[base + kDirectMaxLog1pMultiplicity], std::log1p(3.0));
  //  8 mean log1p intergroup gap: (log1p(6e7) + log1p(3e7))/2
  EXPECT_NEAR(value[base + kDirectMeanLog1pIntergroupGap],
              (std::log1p(60'000'000.0) + std::log1p(30'000'000.0)) / 2.0, 1e-12);
  //  9 nearest-rank p90 over 2 gaps: ceil(0.9*2) = 2 -> the 2nd smallest = the max
  EXPECT_DOUBLE_EQ(value[base + kDirectP90Log1pIntergroupGap], std::log1p(60'000'000.0));
  // 10 max log1p intergroup gap
  EXPECT_DOUBLE_EQ(value[base + kDirectMaxLog1pIntergroupGap], std::log1p(60'000'000.0));
  // 11 log1p covered span: 290'000ms - 200'000ms = 90s = 90'000'000us
  EXPECT_NEAR(value[base + kDirectLog1pCoveredSpan], std::log1p(90'000'000.0), 1e-12);
  // 12 log1p age of last group: 300'000ms - 290'000ms = 10s = 10'000'000us
  EXPECT_NEAR(value[base + kDirectLog1pAgeOfLastGroup], std::log1p(10'000'000.0), 1e-12);
  // 17 unusable-attachment fraction: 1 print of 6
  EXPECT_DOUBLE_EQ(value[base + kDirectUnusableAttachmentFraction], 1.0 / 6.0);
  // 18 vendor-sequence inversion fraction: 1 inversion over 2 adjacent valid pairs
  EXPECT_DOUBLE_EQ(value[base + kDirectSequenceInversionFraction], 0.5);
  // 19 r_modality: 3 finite-all-four groups / max(3,1) = 1
  EXPECT_DOUBLE_EQ(value[base + kDirectRModality], 1.0);
}

TEST(DirectRawFullWindow, NbboAttachmentAndSequenceFractionsAreStructuralZerosNotMissing) {
  // "For NBBO, attachment-invalid and sequence-inversion are typed structural
  // zeros" — present, value 0, even with no sequence pair anywhere.
  const std::int64_t cutoff = frame_a_of(300'000);
  const std::vector<GroupRecord> groups{group_at(frame_a_of(290'000), 2, 1.0)};
  DirectRawBuilder builder(Modality::STOCK_NBBO, groups);
  const auto row = builder.build(window_at(cutoff));
  ASSERT_TRUE(row.has_value());
  const std::size_t base = kDirectFullWindowOffset;
  EXPECT_TRUE(row.value().presence(base + kDirectUnusableAttachmentFraction));
  EXPECT_DOUBLE_EQ(row.value().value[base + kDirectUnusableAttachmentFraction], 0.0);
  EXPECT_TRUE(row.value().presence(base + kDirectSequenceInversionFraction));
  EXPECT_DOUBLE_EQ(row.value().value[base + kDirectSequenceInversionFraction], 0.0);
  // The missing-cell denominator uses the NBBO modality's own 16 channels.
  EXPECT_EQ(declared_value_channel_count(Modality::STOCK_NBBO), 16U);
  EXPECT_EQ(declared_value_channel_count(Modality::STOCK_PRINT), 17U);
  EXPECT_EQ(declared_value_channel_count(Modality::OPTION_PRINT), 22U);
}

TEST(DirectRawFullWindow, AWindowWithNoMechanismValueMasksTheFractionButNotRModality) {
  const std::int64_t cutoff = frame_a_of(300'000);
  std::vector<GroupRecord> groups{group_at(frame_a_of(290'000), 1, 0.0, /*all_four=*/false)};
  DirectRawBuilder builder(Modality::STOCK_PRINT, groups);
  const auto row = builder.build(window_at(cutoff));
  ASSERT_TRUE(row.has_value());
  const std::size_t base = kDirectFullWindowOffset;
  // 0 of 1 groups have all four mechanisms: the fraction is a PRESENT 0 (its
  // denominator is nonzero), and r_modality agrees.
  EXPECT_TRUE(row.value().presence(base + kDirectAllFourFiniteGroupFraction));
  EXPECT_DOUBLE_EQ(row.value().value[base + kDirectAllFourFiniteGroupFraction], 0.0);
  EXPECT_DOUBLE_EQ(row.value().value[base + kDirectRModality], 0.0);
  // Mechanism 1 has no present member anywhere in the window: value0/presence0.
  EXPECT_FALSE(row.value().presence(direct_window_offset(3) + 2 + 2 * 1));
  // Mechanism 0 does.
  EXPECT_TRUE(row.value().presence(direct_window_offset(3) + 2));
}

// ---------------------------------------------------------------------------
// THE PHASE CONTROL: a group moved across newest-visibility equality.
// ---------------------------------------------------------------------------

TEST(PhaseSplit, MovingAGroupAcrossVisibilityEqualityChangesOnlyTheDeclaredCounts) {
  // THE BRIEF'S CONTROL. Five groups in the window and the newest same-side
  // visibility at 250'000ms. A group AT the visibility is PHASE_EQUAL_UNORDERED
  // and enters NEITHER denominator.
  const std::int64_t cutoff = frame_a_of(300'000);
  const std::int64_t visibility = frame_a_of(250'000);

  const auto build_with = [&](std::int64_t moved_offset_ms) {
    std::vector<GroupRecord> groups{
        group_at(frame_a_of(230'000), 1, 1.0),
        group_at(frame_a_of(240'000), 1, 1.0),
        group_at(frame_a_of(moved_offset_ms), 1, 1.0),
        group_at(frame_a_of(270'000), 1, 1.0),
        group_at(frame_a_of(280'000), 1, 1.0),
    };
    std::sort(groups.begin(), groups.end(),
              [](const GroupRecord& left, const GroupRecord& right) {
                return left.ts_ns_a < right.ts_ns_a;
              });
    DirectRawBuilder builder(Modality::STOCK_PRINT, groups);
    DecisionWindow window = window_at(cutoff);
    window.phase_reference_present = true;
    window.phase_reference_ns_a = visibility;
    auto row = builder.build(window);
    EXPECT_TRUE(row.has_value());
    return row.value();
  };

  const std::size_t base = kDirectFullWindowOffset;
  // BEFORE the visibility: approach = 3 (230, 240, 249), response = 2.
  const DirectRawRow before = build_with(249'000);
  EXPECT_DOUBLE_EQ(before.value[base + kDirectLog1pApproachGroupCount], std::log1p(3.0));
  EXPECT_DOUBLE_EQ(before.value[base + kDirectLog1pResponseGroupCount], std::log1p(2.0));

  // EXACTLY AT the visibility: PHASE_EQUAL_UNORDERED — approach = 2, response = 2,
  // and the group is in NEITHER denominator (2 + 2 = 4 < 5 groups in the window).
  const DirectRawRow equal = build_with(250'000);
  EXPECT_DOUBLE_EQ(equal.value[base + kDirectLog1pApproachGroupCount], std::log1p(2.0));
  EXPECT_DOUBLE_EQ(equal.value[base + kDirectLog1pResponseGroupCount], std::log1p(2.0));
  EXPECT_DOUBLE_EQ(equal.value[base + kDirectLog1pGroupCount], std::log1p(5.0));

  // AFTER the visibility: approach = 2, response = 3.
  const DirectRawRow after = build_with(251'000);
  EXPECT_DOUBLE_EQ(after.value[base + kDirectLog1pApproachGroupCount], std::log1p(2.0));
  EXPECT_DOUBLE_EQ(after.value[base + kDirectLog1pResponseGroupCount], std::log1p(3.0));

  // NOTHING ELSE MOVED. Every non-phase column is bit-identical across the three.
  for (std::size_t column = 0; column < kDirectColumnCount; ++column) {
    const bool is_phase = column == base + kDirectLog1pApproachGroupCount ||
                          column == base + kDirectLog1pResponseGroupCount ||
                          column == base + kDirectApproachOmissionFraction ||
                          column == base + kDirectResponseOmissionFraction;
    // The moved group's own timestamp shifts the gap/span statistics, so those
    // three are excluded from the invariance claim by construction.
    const bool is_timing = column == base + kDirectMeanLog1pIntergroupGap ||
                           column == base + kDirectP90Log1pIntergroupGap ||
                           column == base + kDirectMaxLog1pIntergroupGap ||
                           column == base + kDirectLog1pCoveredSpan;
    if (is_phase || is_timing) {
      continue;
    }
    EXPECT_DOUBLE_EQ(equal.value[column], before.value[column])
        << direct_column_name(Modality::STOCK_PRINT, column);
    EXPECT_DOUBLE_EQ(after.value[column], before.value[column])
        << direct_column_name(Modality::STOCK_PRINT, column);
  }
}

TEST(PhaseSplit, OmissionIsTheTruncatedFromRecent128CountOverThatPhasesGroups) {
  // 130 groups in the window, visibility placed so that the first 60 are
  // APPROACH and the rest RESPONSE. recent128 keeps the last 128, so exactly the
  // first 130 - 128 = 2 groups are truncated, and both are APPROACH.
  const std::int64_t cutoff = frame_a_of(300'000);
  std::vector<GroupRecord> groups;
  groups.reserve(130);
  for (std::int64_t index = 0; index < 130; ++index) {
    groups.push_back(group_at(frame_a_of(190'000 + index * 500), 1, 1.0));
  }
  DecisionWindow window = window_at(cutoff);
  window.phase_reference_present = true;
  window.phase_reference_ns_a = frame_a_of(190'000 + 60 * 500);  // group index 60

  DirectRawBuilder builder(Modality::STOCK_PRINT, groups);
  const auto row = builder.build(window);
  ASSERT_TRUE(row.has_value());
  const std::size_t base = kDirectFullWindowOffset;
  // approach = indices 0..59 = 60; the equal group (index 60) is in neither;
  // response = indices 61..129 = 69.
  EXPECT_DOUBLE_EQ(row.value().value[base + kDirectLog1pApproachGroupCount], std::log1p(60.0));
  EXPECT_DOUBLE_EQ(row.value().value[base + kDirectLog1pResponseGroupCount], std::log1p(69.0));
  // omission: 2 truncated approach groups of 60 approach groups; no response
  // group is truncated.
  EXPECT_DOUBLE_EQ(row.value().value[base + kDirectApproachOmissionFraction], 2.0 / 60.0);
  EXPECT_DOUBLE_EQ(row.value().value[base + kDirectResponseOmissionFraction], 0.0);
  EXPECT_TRUE(row.value().presence(base + kDirectResponseOmissionFraction));
}

TEST(PhaseSplit, WithNoSameSideVisibilityTheFourPhaseColumnsAreMaskedNotZeroCoded) {
  const std::int64_t cutoff = frame_a_of(300'000);
  const std::vector<GroupRecord> groups{group_at(frame_a_of(290'000), 1, 1.0)};
  DirectRawBuilder builder(Modality::STOCK_PRINT, groups);
  const auto row = builder.build(window_at(cutoff));  // phase_reference_present = false
  ASSERT_TRUE(row.has_value());
  const std::size_t base = kDirectFullWindowOffset;
  for (const std::size_t column :
       {base + kDirectLog1pApproachGroupCount, base + kDirectLog1pResponseGroupCount,
        base + kDirectApproachOmissionFraction, base + kDirectResponseOmissionFraction}) {
    EXPECT_FALSE(row.value().presence(column));
    EXPECT_DOUBLE_EQ(row.value().value[column], 0.0);
  }
}

TEST(DirectRawSide, TheShortRowIsTheLongRowWithTheOrientedMechanismsNegated) {
  const std::int64_t cutoff = frame_a_of(300'000);
  const std::vector<GroupRecord> groups{group_at(frame_a_of(299'000), 2, 7.0)};
  DirectRawBuilder builder(Modality::STOCK_PRINT, groups);
  const auto long_row = builder.build(window_at(cutoff, Side::LONG));
  const auto short_row = builder.build(window_at(cutoff, Side::SHORT));
  ASSERT_TRUE(long_row.has_value());
  ASSERT_TRUE(short_row.has_value());
  for (std::size_t index = 0; index < kDirectWindowCount; ++index) {
    const std::size_t offset = direct_window_offset(index);
    EXPECT_DOUBLE_EQ(long_row.value().value[offset + 2], 7.0);
    EXPECT_DOUBLE_EQ(short_row.value().value[offset + 2], -7.0);
    EXPECT_DOUBLE_EQ(long_row.value().value[offset + 3], 7.0);
    EXPECT_DOUBLE_EQ(short_row.value().value[offset + 3], -7.0);
    // Counts do not move under reflection.
    EXPECT_DOUBLE_EQ(short_row.value().value[offset + 0], long_row.value().value[offset + 0]);
  }
}

// ---------------------------------------------------------------------------
// DIRECT over a real constructor-built tape, so the two layers are wired.
// ---------------------------------------------------------------------------

TEST(DirectRawOverRealConstructors, AStockPrintTapeFlowsIntoTheSixtyColumns) {
  StockPrintStream stream(clock_125());
  ASSERT_TRUE(stream
                  .push_group(open_ms() + 8'000,
                              rows_of<qr::sources::StockTradeRow>({trade_row(
                                  open_ms() + 8'000, 100'000'000, 100, open_ms() + 7'000,
                                  99'990'000, 100'010'000, 400, 400, 5)}))
                  .has_value());
  ASSERT_TRUE(stream
                  .push_group(open_ms() + 10'000,
                              rows_of<qr::sources::StockTradeRow>({trade_row(
                                  open_ms() + 10'000, 100'030'000, 300, open_ms() + 9'000,
                                  99'990'000, 100'010'000, 500, 700, 10)}))
                  .has_value());

  DirectRawBuilder builder(Modality::STOCK_PRINT, stream.groups());
  DecisionWindow window = window_at(frame_a_of(11'000));
  window.phase_reference_present = true;
  window.phase_reference_ns_a = frame_a_of(9'000);
  const auto row = builder.build(window);
  ASSERT_TRUE(row.has_value());
  const std::size_t base = kDirectFullWindowOffset;
  // Two groups, two tokens, one approach (8'000ms) and one response (10'000ms).
  EXPECT_DOUBLE_EQ(row.value().value[base + kDirectLog1pGroupCount], std::log1p(2.0));
  EXPECT_DOUBLE_EQ(row.value().value[base + kDirectLog1pTokenCount], std::log1p(2.0));
  EXPECT_DOUBLE_EQ(row.value().value[base + kDirectLog1pApproachGroupCount], std::log1p(1.0));
  EXPECT_DOUBLE_EQ(row.value().value[base + kDirectLog1pResponseGroupCount], std::log1p(1.0));
  // The 10'000ms print's own return is +3 bps and it is the window's `last`.
  EXPECT_DOUBLE_EQ(row.value().value[direct_window_offset(3) + 3], 3.0);
}

}  // namespace
}  // namespace qr::carriers
