// Fixtures CLOCK-1..CLOCK-6 — one counterfixture per fail-closed boundary
// condition, mirroring session_clock.rs:723-851, plus the summer/winter offset
// fixtures and the i64-overflow injection.
//
// THE FIRING LAW: every guard here ships with an instance it must REJECT and
// an innocent instance it must ACCEPT. Passing on correct input proves nothing.
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <span>
#include <string>
#include <vector>

#include "clock_test_support.hpp"
#include "gtest/gtest.h"
#include "qr_clock/session_clock.hpp"
#include "qr_core/frames.hpp"
#include "qr_registry/registry.hpp"

namespace {

using qr_clock_test::clock;
using qr_clock_test::date;
using qr_clock_test::kEarlyClose;
using qr_clock_test::kEdtFullDay;
using qr_clock_test::kEstFullDay;
using qr_clock_test::kHourNs;
using qr_clock_test::registry;
using qr_clock_test::session;
using qr_clock_test::why;

std::vector<qr::FrameB> open_relative_tape(const qr::SessionClock& c, int rows) {
  std::vector<qr::FrameB> tape;
  tape.reserve(static_cast<std::size_t>(rows));
  for (int k = 0; k < rows; ++k) {
    tape.push_back(qr::FrameB{c.open_b().ns() + static_cast<std::int64_t>(k) * qr::kBarNs});
  }
  return tape;
}

// ---------------------------------------------------------------------------
// The three pinned fixture sessions really are the shapes they are pinned for.
// ---------------------------------------------------------------------------

TEST(ClockFixtures, ThePinnedSessionsAreTheShapesTheyArePinnedFor) {
  EXPECT_EQ(clock(kEdtFullDay).expected_bar_count(), 390);
  EXPECT_EQ(clock(kEstFullDay).expected_bar_count(), 390);
  EXPECT_EQ(clock(kEarlyClose).expected_bar_count(), 210)
      << "the early-close fixture must actually be an early close";
}

// ---------------------------------------------------------------------------
// CLOCK-2 — boundary condition 2: the registry row's own span must equal
// expected_bar_count * BAR_NS, checked AT CONSTRUCTION.
// ---------------------------------------------------------------------------

TEST(ClockConstruction, SpanMismatchWithItsOwnBarCountRefusesAtConstruction) {
  qr::Session corrupted = session(kEarlyClose);
  // The old defect's shape: a 210-bar session carrying a 390-bar span.
  corrupted.session_end_ns = corrupted.session_start_ns + 390 * qr::kBarNs;
  const auto refused = qr::SessionClock::from_session(corrupted);
  ASSERT_FALSE(refused.has_value()) << "a 390-bar span on a 210-bar row must not build a clock";
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::CLOCK_VIOLATION);
  EXPECT_STREQ(refused.error().site(), "qr_clock::SessionClock::from_session");
  EXPECT_EQ(refused.error().context(), 390 * qr::kBarNs) << "the refusal carries the bad span";

  // The innocent instance: the untouched row builds.
  const auto innocent = qr::SessionClock::from_session(session(kEarlyClose));
  EXPECT_TRUE(innocent.has_value()) << why(innocent);
}

TEST(ClockConstruction, UnregisteredDayIsAnUnknownSessionRefusalNotACrash) {
  const auto refused = qr::SessionClock::for_day(registry(), date("2026-01-02"));
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::UNKNOWN_SESSION);
}

// ---------------------------------------------------------------------------
// i64-overflow injection — every arithmetic path refuses instead of wrapping
// or substituting a boundary value for the true result.
// ---------------------------------------------------------------------------

TEST(ClockConstruction, OverflowingArithmeticRefusesInsteadOfWrappingOrClamping) {
  // (a) a civil day so far out that local midnight in nanoseconds cannot fit.
  {
    qr::Session row = session(kEdtFullDay);
    row.day = "9999-12-31";
    row.civil_date = date("9999-12-31");
    const auto refused = qr::SessionClock::from_session(row);
    ASSERT_FALSE(refused.has_value()) << "a year-9999 open cannot fit i64 nanoseconds";
    EXPECT_EQ(refused.error().code(), qr::RefusalCode::ARITHMETIC_OVERFLOW);
  }
  // (b) session_end - session_start overflows.
  {
    qr::Session row = session(kEdtFullDay);
    row.session_start_ns = -9'000'000'000'000'000'000LL;
    row.session_end_ns = 9'000'000'000'000'000'000LL;
    const auto refused = qr::SessionClock::from_session(row);
    ASSERT_FALSE(refused.has_value());
    EXPECT_EQ(refused.error().code(), qr::RefusalCode::ARITHMETIC_OVERFLOW);
  }
  // (c) expected_bar_count * BAR_NS overflows.
  {
    qr::Session row = session(kEdtFullDay);
    row.expected_bar_count = 9'000'000'000LL;
    const auto refused = qr::SessionClock::from_session(row);
    ASSERT_FALSE(refused.has_value());
    EXPECT_EQ(refused.error().code(), qr::RefusalCode::ARITHMETIC_OVERFLOW);
  }
  // The innocent instance: the untouched row still builds.
  EXPECT_TRUE(qr::SessionClock::from_session(session(kEdtFullDay)).has_value());
}

// ---------------------------------------------------------------------------
// The summer/winter offset fixtures — the registry IS the clock authority and
// this module owns no timezone table. Both expected offsets are computed here
// from the registry rows, never hardcoded as 4h/5h.
// ---------------------------------------------------------------------------

TEST(SessionOffsets, SummerAndWinterOffsetsAreDerivedFromTheRegistryRowsThemselves) {
  for (const std::string_view day : {kEdtFullDay, kEstFullDay, kEarlyClose}) {
    const qr::Session& row = session(day);
    const qr::SessionClock c = clock(day);
    const std::int64_t open_b_ns = qr_clock_test::expected_open_b_ns(row);
    EXPECT_EQ(c.open_b().ns(), open_b_ns) << day;
    EXPECT_EQ(c.close_b().ns(), open_b_ns + row.expected_bar_count * qr::kBarNs) << day;
    EXPECT_EQ(c.session_start_a().ns(), row.session_start_ns) << day;
    EXPECT_EQ(c.session_end_a().ns(), row.session_end_ns) << day;
    EXPECT_EQ(c.offset_ns(), row.session_start_ns - open_b_ns) << day;
  }
  // The DST signature, from the registry alone: the frame-A image of the SAME
  // 09:30 ET wall open differs between the winter and the summer session by
  // exactly one hour. This is what makes a frame confusion a 4h error on one
  // day and a 5h error on the other.
  const std::int64_t edt_offset = clock(kEdtFullDay).offset_ns();
  const std::int64_t est_offset = clock(kEstFullDay).offset_ns();
  EXPECT_EQ(est_offset - edt_offset, kHourNs);
  EXPECT_GT(est_offset, 0);
  EXPECT_GT(edt_offset, 0);
}

TEST(SessionOffsets, EveryRegisteredSessionAgreesWithItsOwnRegistryRow) {
  ASSERT_EQ(registry().size(), qr::kRegistrySessionCount);
  // Counted, not asserted row by row: 1,003 sessions x 5 invariants would bury
  // a real failure under five thousand identical lines. The first offending
  // day is reported for each invariant, which is what a debugger needs.
  struct Tally {
    const char* what;
    int failures;
    std::string first_day;
    std::string first_detail;
  };
  Tally built_ok{"clock builds", 0, {}, {}};
  Tally start_a{"session_start_a == registry session_start_ns", 0, {}, {}};
  Tally end_a{"session_end_a == registry session_end_ns", 0, {}, {}};
  Tally span_b{"close_b - open_b == expected_bar_count * BAR_NS", 0, {}, {}};
  Tally open_b{"open_b == civil-date-derived 09:30 ET", 0, {}, {}};
  Tally whole_hour{"offset is exactly 4h or 5h", 0, {}, {}};
  const auto note = [](Tally& tally, const std::string& day, const std::string& detail) {
    ++tally.failures;
    if (tally.first_day.empty()) {
      tally.first_day = day;
      tally.first_detail = detail;
    }
  };
  int early_closes = 0;
  for (const qr::Session& row : registry().sessions()) {
    const auto result = qr::SessionClock::from_session(row);
    if (!result.has_value()) {
      note(built_ok, row.day, why(result));
      continue;
    }
    const qr::SessionClock& c = result.value();
    if (c.session_start_a().ns() != row.session_start_ns) {
      note(start_a, row.day, std::to_string(c.session_start_a().ns()));
    }
    if (c.session_end_a().ns() != row.session_end_ns) {
      note(end_a, row.day, std::to_string(c.session_end_a().ns()));
    }
    if (c.close_b().ns() - c.open_b().ns() != row.expected_bar_count * qr::kBarNs) {
      note(span_b, row.day, std::to_string(c.close_b().ns() - c.open_b().ns()));
    }
    if (c.open_b().ns() != qr_clock_test::expected_open_b_ns(row)) {
      note(open_b, row.day, std::to_string(c.open_b().ns()));
    }
    // Ported invariant (session_clock.rs:876-883): the UTC offset is always
    // 4h or 5h — never anything else, and never zero, which is exactly what a
    // frame confusion looks like.
    if (c.offset_ns() != 4 * kHourNs && c.offset_ns() != 5 * kHourNs) {
      note(whole_hour, row.day, std::to_string(c.offset_ns()));
    }
    if (row.expected_bar_count == 210) {
      ++early_closes;
    }
  }
  for (const Tally* tally : {&built_ok, &start_a, &end_a, &span_b, &open_b, &whole_hour}) {
    EXPECT_EQ(tally->failures, 0) << tally->what << ": " << tally->failures << " of "
                                  << registry().size() << " sessions disagree, first "
                                  << tally->first_day << " (" << tally->first_detail << ")";
  }
  EXPECT_EQ(early_closes, 9) << "the registry pins nine 210-bar early closes";
}

// ---------------------------------------------------------------------------
// CLOCK-3 — boundary condition 3: the half-open frame-B RTH window.
// ---------------------------------------------------------------------------

TEST(ToFrameA, PremarketTheCloseItselfAndPostmarketRefuseInsteadOfConverting) {
  const qr::SessionClock c = clock(kEarlyClose);
  const struct {
    const char* label;
    qr::FrameB ts_b;
  } refused_cases[] = {
      {"premarket", qr::FrameB{c.open_b().ns() - 1}},
      {"the close itself (half-open)", qr::FrameB{c.close_b().ns()}},
      {"postmarket", qr::FrameB{c.close_b().ns() + qr::kBarNs}},
  };
  for (const auto& item : refused_cases) {
    const auto refused = c.to_frame_a(item.ts_b);
    ASSERT_FALSE(refused.has_value()) << item.label << " must be refused, not converted";
    EXPECT_EQ(refused.error().code(), qr::RefusalCode::OUTSIDE_RTH) << item.label;
    EXPECT_STREQ(refused.error().site(), "qr_clock::to_frame_a/condition3_frame_b_rth_window")
        << item.label;
    EXPECT_FALSE(c.contains_b(item.ts_b)) << item.label;
  }
  // The innocent instance: one nanosecond inside the close.
  const auto admitted = c.to_frame_a(qr::FrameB{c.close_b().ns() - 1});
  ASSERT_TRUE(admitted.has_value()) << why(admitted);
  EXPECT_TRUE(c.contains_a(admitted.value()));
}

TEST(ToFrameA, TheEarlyCloseWindowRefusesWhatTheFullDayWindowAdmitted) {
  const qr::SessionClock c = clock(kEarlyClose);
  const std::int64_t old_close_b_ns = c.open_b().ns() + 390 * qr::kBarNs;
  EXPECT_EQ(old_close_b_ns - c.close_b().ns(), 180 * qr::kBarNs);
  const qr::FrameB post_close{c.close_b().ns() + qr::kBarNs};
  ASSERT_LT(post_close.ns(), old_close_b_ns) << "the old 390-bar window admitted this instant";
  EXPECT_FALSE(c.to_frame_a(post_close).has_value())
      << "the expected_bar_count window must refuse it";
}

TEST(ToFrameA, InWindowInstantsConvertExactlyAndLandInTheFrameASession) {
  for (const std::string_view day : {kEdtFullDay, kEstFullDay, kEarlyClose}) {
    const qr::SessionClock c = clock(day);
    for (const std::int64_t offset_ns : {std::int64_t{0}, qr::kBarNs, 37 * qr::kBarNs + 12'345}) {
      const auto converted = c.to_frame_a(qr::FrameB{c.open_b().ns() + offset_ns});
      ASSERT_TRUE(converted.has_value()) << day << ": " << why(converted);
      EXPECT_EQ(converted.value().ns(), c.session_start_a().ns() + offset_ns) << day;
      EXPECT_TRUE(c.contains_a(converted.value())) << day;
    }
  }
}

TEST(ToFrameA, SameCivilDayAdmitsExtendedContextThatRthRefuses) {
  const qr::SessionClock c = clock(kEdtFullDay);
  for (const std::int64_t ns : {c.open_b().ns() - 1, c.close_b().ns()}) {
    const qr::FrameB ts_b{ns};
    EXPECT_TRUE(c.to_frame_a_same_civil_day(ts_b).has_value());
    const auto rth = c.to_frame_a(ts_b);
    ASSERT_FALSE(rth.has_value());
    EXPECT_EQ(rth.error().code(), qr::RefusalCode::OUTSIDE_RTH);
  }
  const auto next_day = c.to_frame_a_same_civil_day(qr::FrameB{c.open_b().ns() + qr::kNanosecondsPerDay});
  ASSERT_FALSE(next_day.has_value());
  EXPECT_EQ(next_day.error().code(), qr::RefusalCode::WRONG_CIVIL_DAY);
}

/// **THE COUNTERFIXTURE FOR THE R-HALT-42 DEFECT ITSELF** (session_clock.rs:
/// 718-770). The old construction compared a frame-B tape instant against a
/// frame-A cutoff as if they were the same number; that quote is struck 4-5
/// hours AFTER its own decision instant, and a range-limited tripwire reports
/// the violation as a perfect zero.
TEST(FrameWall, TheOldConstructionFillsAfterItsOwnDecisionInstant) {
  for (const std::string_view day : {kEdtFullDay, kEstFullDay}) {
    const qr::SessionClock c = clock(day);
    const std::int64_t offset_ns = c.offset_ns();
    ASSERT_GT(offset_ns, 0) << day;

    const std::int64_t cutoff_a_ns = c.session_start_a().ns() + qr::kBarNs;
    // THE OLD RULE, verbatim: the last frame-B instant strictly below the
    // cutoff's NUMERIC value. On this tape that instant is well in session.
    const qr::FrameB selected_b{cutoff_a_ns - 1};
    ASSERT_TRUE(c.contains_b(selected_b))
        << day << ": the old rule really did select an in-session quote — the WRONG one";

    const auto real_time = c.to_frame_a(selected_b);
    ASSERT_TRUE(real_time.has_value()) << why(real_time);
    const std::int64_t true_lag_ns = cutoff_a_ns - real_time.value().ns();
    EXPECT_EQ(true_lag_ns, 1 - offset_ns) << day;
    EXPECT_LT(true_lag_ns, 0) << day << ": the old construction fills AFTER its own decision";
    // An unsigned lag cannot represent this defect at all: read unsigned, a
    // 4-5 hour lookahead becomes an absurd forward lag.
    EXPECT_GT(static_cast<std::uint64_t>(true_lag_ns), std::uint64_t{1} << 60U)
        << day << ": an unsigned lag cannot represent this defect";
  }
}

// ---------------------------------------------------------------------------
// CLOCK-4 — boundary condition 4: the converted frame-A instant is inside
// [session_start, session_end).
//
// Exact arithmetic makes this condition UNREACHABLE from any registry row that
// passes construction (span_A == span_B forces the image into the window), so
// its counterfixture uses the named test-only door, exactly as WP1's
// malformation fixture uses Registry::parse_without_digest_gate.
// ---------------------------------------------------------------------------

TEST(ToFrameA, ConvertedInstantOutsideTheFrameASessionRefuses) {
  const qr::SessionClock honest = clock(kEdtFullDay);
  qr::SessionClock::Fields fields = honest.fields();
  // The frame-A session is shrunk to a single bar while the frame-B window
  // still spans the whole day: a mid-session quote now images past the end.
  fields.session_end_ns = fields.session_start_ns + qr::kBarNs;
  const qr::SessionClock corrupted = qr::SessionClock::without_construction_gate(fields);

  const qr::FrameB mid_session{honest.open_b().ns() + 200 * qr::kBarNs};
  ASSERT_TRUE(corrupted.contains_b(mid_session)) << "condition 3 must not be what fires here";
  const auto refused = corrupted.to_frame_a(mid_session);
  ASSERT_FALSE(refused.has_value()) << "a frame-A image outside its session must refuse";
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::CLOCK_VIOLATION);
  EXPECT_STREQ(refused.error().site(), "qr_clock::to_frame_a/condition4_frame_a_session_window")
      << "condition 4 must be the guard that fires";

  // The innocent instance: the same instant on the uncorrupted clock.
  EXPECT_TRUE(honest.to_frame_a(mid_session).has_value());
}

// ---------------------------------------------------------------------------
// CLOCK-5 — boundary condition 5: exact offset equality, RE-DERIVED FROM THE
// RESULT. A transposition, a double conversion or a corrupted cached offset is
// caught here.
// ---------------------------------------------------------------------------

TEST(ToFrameA, OffsetEqualityIsReDerivedFromTheResultAndCatchesACorruptedOffset) {
  const qr::SessionClock honest = clock(kEstFullDay);
  qr::SessionClock::Fields fields = honest.fields();
  fields.offset_ns += 1;  // one nanosecond of drift in the cached offset
  const qr::SessionClock corrupted = qr::SessionClock::without_construction_gate(fields);

  const qr::FrameB at_open{honest.open_b().ns()};
  const auto refused = corrupted.to_frame_a(at_open);
  ASSERT_FALSE(refused.has_value()) << "ts_A - session_start must equal ts_B - open_B exactly";
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::CLOCK_VIOLATION);
  EXPECT_STREQ(refused.error().site(), "qr_clock::to_frame_a/condition5_offset_equality")
      << "condition 5 must be the guard that fires";
  EXPECT_EQ(refused.error().context(), 1) << "the refusal carries the offset drift";

  // The innocent instance: the uncorrupted clock converts the same instant.
  const auto admitted = honest.to_frame_a(at_open);
  ASSERT_TRUE(admitted.has_value()) << why(admitted);
  EXPECT_EQ(admitted.value().ns() - honest.session_start_a().ns(),
            at_open.ns() - honest.open_b().ns());
}

// ---------------------------------------------------------------------------
// CLOCK-1 and CLOCK-6 — condition 1 (the requested day) and condition 6 (row
// count, input order, and OUTPUT order re-checked on the output).
// ---------------------------------------------------------------------------

TEST(ConvertSequence, AnInnocentTapeConvertsRowForRowInOrder) {
  const qr::SessionClock c = clock(kEdtFullDay);
  const std::vector<qr::FrameB> tape = open_relative_tape(c, 8);
  const auto converted = c.convert_sequence(date(kEdtFullDay), tape);
  ASSERT_TRUE(converted.has_value()) << why(converted);
  ASSERT_EQ(converted.value().size(), tape.size());
  for (std::size_t index = 0; index < tape.size(); ++index) {
    EXPECT_EQ(converted.value()[index].ns(),
              c.session_start_a().ns() + static_cast<std::int64_t>(index) * qr::kBarNs);
    if (index > 0) {
      EXPECT_LT(converted.value()[index - 1], converted.value()[index]);
    }
  }
}

TEST(ConvertSequence, AnotherDaysClockRefusesTheWholeTape) {
  const qr::SessionClock c = clock(kEdtFullDay);
  const std::vector<qr::FrameB> tape = open_relative_tape(c, 8);
  const auto refused = c.convert_sequence(date(kEstFullDay), tape);
  ASSERT_FALSE(refused.has_value()) << "condition 1: the clock must be the requested day's clock";
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::CLOCK_VIOLATION);
  EXPECT_STREQ(refused.error().site(), "qr_clock::convert_sequence/condition1_requested_day");
  // The innocent instance: the same tape on its own day.
  EXPECT_TRUE(c.convert_sequence(date(kEdtFullDay), tape).has_value());
}

TEST(ConvertSequence, NonMonotoneInputTapeRefusesInsteadOfBeingSortedIntoSilence) {
  const qr::SessionClock c = clock(kEdtFullDay);
  std::vector<qr::FrameB> scrambled = open_relative_tape(c, 8);
  std::swap(scrambled[2], scrambled[5]);
  const auto refused = c.convert_sequence(date(kEdtFullDay), scrambled);
  ASSERT_FALSE(refused.has_value()) << "condition 6a: a non-decreasing input tape is required";
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::CLOCK_VIOLATION);
  EXPECT_EQ(refused.error().context(), 3) << "the refusal names the offending row";
  // The INPUT guard must be what fires: a defective tape is refused before it
  // is converted, not after the output happens to look wrong.
  EXPECT_STREQ(refused.error().site(), "qr_clock::convert_sequence/condition6a_input_order");
}

TEST(ConvertSequence, OnePostCloseRowPoisonsTheWholeTapeInsteadOfBeingDropped) {
  const qr::SessionClock c = clock(kEdtFullDay);
  std::vector<qr::FrameB> tape = open_relative_tape(c, 8);
  tape.push_back(qr::FrameB{c.close_b().ns() + 1});
  const auto refused = c.convert_sequence(date(kEdtFullDay), tape);
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::OUTSIDE_RTH);
  EXPECT_STREQ(refused.error().site(), "qr_clock::to_frame_a/condition3_frame_b_rth_window");
}

TEST(ConvertSequence, OutputOrderIsRecheckedOnTheOutputItself) {
  // Condition 6c on its own primitive: a hand-built descending frame-A tape
  // must refuse and name the descent, and an ascending one must pass. The
  // check is on the OUTPUT, never inferred from the input's monotonicity.
  const std::vector<qr::FrameA> ascending = {
      qr::FrameA::from_published_utc_epoch_ns(10),
      qr::FrameA::from_published_utc_epoch_ns(10),
      qr::FrameA::from_published_utc_epoch_ns(11),
  };
  const auto ok = qr::refuse_unless_non_decreasing(ascending);
  ASSERT_TRUE(ok.has_value()) << why(ok);
  EXPECT_EQ(ok.value(), 3U);

  const std::vector<qr::FrameA> descending = {
      qr::FrameA::from_published_utc_epoch_ns(10),
      qr::FrameA::from_published_utc_epoch_ns(11),
      qr::FrameA::from_published_utc_epoch_ns(9),
  };
  const auto refused = qr::refuse_unless_non_decreasing(descending);
  ASSERT_FALSE(refused.has_value()) << "a descending frame-A tape must refuse";
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::CLOCK_VIOLATION);
  EXPECT_STREQ(refused.error().site(), "qr_clock::refuse_unless_non_decreasing");
  EXPECT_EQ(refused.error().context(), 2) << "the refusal names the first descending row";

  // And convert_sequence really does run it on its own output.
  const qr::SessionClock c = clock(kEstFullDay);
  const auto converted = c.convert_sequence(date(kEstFullDay), open_relative_tape(c, 4));
  ASSERT_TRUE(converted.has_value()) << why(converted);
  EXPECT_TRUE(qr::refuse_unless_non_decreasing(converted.value()).has_value());
}

TEST(ConvertSequence, EqualTimestampRowsAreKeptEqualAndInOrder) {
  const qr::SessionClock c = clock(kEstFullDay);
  const std::vector<qr::FrameB> tape = {
      qr::FrameB{c.open_b().ns() + 7},
      qr::FrameB{c.open_b().ns() + 7},
      qr::FrameB{c.open_b().ns() + 8},
  };
  const auto converted = c.convert_sequence(date(kEstFullDay), tape);
  ASSERT_TRUE(converted.has_value()) << why(converted);
  ASSERT_EQ(converted.value().size(), 3U);
  EXPECT_EQ(converted.value()[0].ns(), c.session_start_a().ns() + 7);
  EXPECT_EQ(converted.value()[0], converted.value()[1]);
  EXPECT_LT(converted.value()[1], converted.value()[2]);
}

// ---------------------------------------------------------------------------
// The WP2 benchmark gate (FINAL_PLAN section 6, "Efficiency law": slower than
// budget cannot merge). The stated WP2 wall is the full 1,003-session
// cross-check in under 10 seconds; this is that same work — every registered
// session's clock plus a full trading day of conversions on each — enforced
// inside the suite so a regression cannot merge.
// ---------------------------------------------------------------------------

TEST(ClockBudget, EveryRegisteredSessionBuildsAndConvertsUnderTheCrossCheckWall) {
  const auto started = std::chrono::steady_clock::now();
  std::int64_t rows = 0;
  std::int64_t checksum = 0;
  for (const qr::Session& row : registry().sessions()) {
    const auto built = qr::SessionClock::from_session(row);
    ASSERT_TRUE(built.has_value()) << row.day << ": " << why(built);
    const qr::SessionClock& c = built.value();
    std::vector<qr::FrameB> tape;
    tape.reserve(static_cast<std::size_t>(row.expected_bar_count));
    for (std::int64_t bar = 0; bar < row.expected_bar_count; ++bar) {
      tape.push_back(qr::FrameB{c.open_b().ns() + bar * qr::kBarNs});
    }
    const auto converted = c.convert_sequence(row.civil_date, tape);
    ASSERT_TRUE(converted.has_value()) << row.day << ": " << why(converted);
    ASSERT_FALSE(converted.value().empty()) << row.day << ": a session converted to nothing";
    rows += static_cast<std::int64_t>(converted.value().size());
    checksum += converted.value().back().ns() - converted.value().front().ns();
  }
  const auto elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - started);
  EXPECT_EQ(rows, 390 * 994 + 210 * 9);
  EXPECT_GT(checksum, 0);
  EXPECT_LT(elapsed.count(), 10.0) << "WP2 budget blown: " << elapsed.count() << "s";
  std::printf("[budget] 1,003 clocks + %lld conversions: %.4f s\n",
              static_cast<long long>(rows), elapsed.count());
}

TEST(ConvertSequence, AnEmptyTapeConvertsToAnEmptyTape) {
  const qr::SessionClock c = clock(kEdtFullDay);
  const std::vector<qr::FrameB> empty;
  const auto converted = c.convert_sequence(date(kEdtFullDay), empty);
  ASSERT_TRUE(converted.has_value()) << why(converted);
  EXPECT_TRUE(converted.value().empty());
}

}  // namespace
