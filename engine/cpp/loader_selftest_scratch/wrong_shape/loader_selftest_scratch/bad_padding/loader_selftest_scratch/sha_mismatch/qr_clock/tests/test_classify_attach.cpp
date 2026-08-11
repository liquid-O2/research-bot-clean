// Fixtures WCD-1..WCD-8 — the totalized attachment classifier.
//
// SPEC: design/DESIGN_SUBSTRATE.md section 6 — "WCD fix = totalize, don't
// catch: total classifier classify_attach(ts_b, clock) -> {MISSING, MALFORMED,
// WRONG_CIVIL_DAY(delta_days), ON_DAY(FrameA)} with no error path; conversion
// only in ON_DAY; ... census carries delta_days histogram; ... fixtures WCD-1..8
// incl. 'mask is observable' and 'no prior-state perturbation'".
//
// The defect this replaces: a wrong-civil-day attachment reaching a `?` and
// aborting a whole pass (the latent shape at reader.rs:1173). Here a WCD row is
// a TYPED STATE the run carries forward and the census counts.
#include <cstdint>
#include <limits>
#include <map>
#include <optional>
#include <string>
#include <vector>

#include "clock_test_support.hpp"
#include "gtest/gtest.h"
#include "qr_clock/session_clock.hpp"
#include "qr_core/frames.hpp"

namespace {

using qr_clock_test::clock;
using qr_clock_test::kEarlyClose;
using qr_clock_test::kEdtFullDay;
using qr_clock_test::kEstFullDay;

// WCD-1 -- an attachment on the PREVIOUS civil day is typed, not thrown.
TEST(ClassifyAttach, PreviousCivilDayIsTypedWithItsDeltaNotThrown) {
  const qr::SessionClock c = clock(kEdtFullDay);
  for (const std::int64_t back_days : {std::int64_t{1}, std::int64_t{3}, std::int64_t{365}}) {
    const qr::FrameB ts_b{c.open_b().ns() - back_days * qr::kNanosecondsPerDay};
    const qr::AttachClass classified = qr::classify_attach(ts_b, c);
    ASSERT_EQ(classified.kind(), qr::AttachKind::WRONG_CIVIL_DAY) << "back " << back_days;
    EXPECT_EQ(classified.delta_days(), -back_days);
  }
  // The boundary: one nanosecond before this civil day's local midnight is
  // still the previous day; local midnight itself is not.
  const std::int64_t local_midnight_ns =
      c.open_b().ns() - qr::kWallOpenOffsetMs * qr::kNanosecondsPerMillisecond;
  EXPECT_EQ(qr::classify_attach(qr::FrameB{local_midnight_ns - 1}, c).delta_days(), -1);
  EXPECT_EQ(qr::classify_attach(qr::FrameB{local_midnight_ns}, c).kind(), qr::AttachKind::ON_DAY);
}

// WCD-2 -- an attachment on the NEXT civil day is typed, not thrown.
TEST(ClassifyAttach, NextCivilDayIsTypedWithItsDeltaNotThrown) {
  const qr::SessionClock c = clock(kEdtFullDay);
  for (const std::int64_t forward_days : {std::int64_t{1}, std::int64_t{2}, std::int64_t{400}}) {
    const qr::FrameB ts_b{c.open_b().ns() + forward_days * qr::kNanosecondsPerDay};
    const qr::AttachClass classified = qr::classify_attach(ts_b, c);
    ASSERT_EQ(classified.kind(), qr::AttachKind::WRONG_CIVIL_DAY) << "forward " << forward_days;
    EXPECT_EQ(classified.delta_days(), forward_days);
  }
  // The boundary: the last nanosecond of this civil day is ON_DAY, the next is
  // the next day.
  const std::int64_t next_midnight_ns =
      c.open_b().ns() - qr::kWallOpenOffsetMs * qr::kNanosecondsPerMillisecond +
      qr::kNanosecondsPerDay;
  EXPECT_EQ(qr::classify_attach(qr::FrameB{next_midnight_ns - 1}, c).kind(),
            qr::AttachKind::ON_DAY);
  EXPECT_EQ(qr::classify_attach(qr::FrameB{next_midnight_ns}, c).delta_days(), 1);
}

// WCD-3 -- equal-time attachments classify identically, to the nanosecond.
TEST(ClassifyAttach, EqualTimeAttachmentsClassifyIdenticallyAndPreserveSubMillisecondOrder) {
  const qr::SessionClock c = clock(kEstFullDay);
  const qr::FrameB first{c.open_b().ns() + 7};
  const qr::FrameB second{c.open_b().ns() + 7};
  const qr::FrameB later{c.open_b().ns() + 8};
  const qr::AttachClass a = qr::classify_attach(first, c);
  const qr::AttachClass b = qr::classify_attach(second, c);
  const qr::AttachClass d = qr::classify_attach(later, c);
  ASSERT_EQ(a.kind(), qr::AttachKind::ON_DAY);
  EXPECT_EQ(a, b) << "two equal-time attachments must classify to the same typed value";
  EXPECT_EQ(a.frame_a().ns(), c.session_start_a().ns() + 7);
  EXPECT_EQ(a.frame_a(), b.frame_a());
  EXPECT_LT(b.frame_a(), d.frame_a());
}

// WCD-4 -- a same-day attachment LATER than the session (a "future" one) is
// still ON_DAY: the classifier types the civil day and nothing else. Futureness
// is a separate typed state, decided by the consumer that knows the event time.
TEST(ClassifyAttach, FutureSameDayAttachmentStaysOnDayAndStillConverts) {
  const qr::SessionClock c = clock(kEarlyClose);
  for (const std::int64_t ts_ns : {c.close_b().ns(), c.close_b().ns() + 3 * qr::kBarNs,
                                   c.open_b().ns() - 1}) {
    const qr::AttachClass classified = qr::classify_attach(qr::FrameB{ts_ns}, c);
    ASSERT_EQ(classified.kind(), qr::AttachKind::ON_DAY) << ts_ns;
    EXPECT_EQ(classified.frame_a().ns(), ts_ns + c.offset_ns());
    // ... and the RTH conversion still refuses it: the classifier is not an
    // eligibility screen and never silently widens the session window.
    EXPECT_FALSE(c.to_frame_a(qr::FrameB{ts_ns}).has_value());
  }
}

// WCD-5 -- an absent attachment is MISSING, not a zero and not an abort.
TEST(ClassifyAttach, AbsentAttachmentIsMissing) {
  const qr::SessionClock c = clock(kEdtFullDay);
  const qr::AttachClass classified = qr::classify_attach(std::nullopt, c);
  EXPECT_EQ(classified.kind(), qr::AttachKind::MISSING);
  EXPECT_EQ(classified, qr::AttachClass::missing());
  EXPECT_FALSE(classified.is_on_day());
  EXPECT_EQ(c.classify_attach_ms(std::nullopt).kind(), qr::AttachKind::MISSING);
}

// WCD-6 -- a stamp whose own arithmetic refuses is MALFORMED, never an abort
// and never a wrapped value.
TEST(ClassifyAttach, MalformedMillisecondStampIsMalformedNotAnAbortAndNotAWrap) {
  const qr::SessionClock c = clock(kEdtFullDay);
  for (const std::int64_t ms : {std::numeric_limits<std::int64_t>::max(),
                                std::numeric_limits<std::int64_t>::min(),
                                std::int64_t{9'300'000'000'000LL},
                                std::int64_t{-9'300'000'000'000LL}}) {
    const qr::AttachClass classified = c.classify_attach_ms(ms);
    EXPECT_EQ(classified.kind(), qr::AttachKind::MALFORMED) << "ms " << ms;
    EXPECT_FALSE(qr::frame_b_from_naive_et_ms(ms).has_value()) << "ms " << ms;
  }
  // The innocent instance: this session's own open, in the tape's own unit.
  const std::int64_t open_ms = c.open_b().ns() / qr::kNanosecondsPerMillisecond;
  const qr::AttachClass admitted = c.classify_attach_ms(open_ms);
  ASSERT_EQ(admitted.kind(), qr::AttachKind::ON_DAY);
  EXPECT_EQ(admitted.frame_a(), c.session_start_a());
}

// WCD-7 -- the valid control classifies DIFFERENTLY from every WCD input: the
// mask is discriminating, not a constant.
TEST(ClassifyAttach, ValidControlClassifiesDifferentlyFromEveryWrongDayInput) {
  const qr::SessionClock c = clock(kEdtFullDay);
  const qr::FrameB control{c.open_b().ns() + 11 * qr::kBarNs};
  const qr::AttachClass valid = qr::classify_attach(control, c);
  ASSERT_EQ(valid.kind(), qr::AttachKind::ON_DAY);
  EXPECT_EQ(valid.frame_a().ns(), c.session_start_a().ns() + 11 * qr::kBarNs);

  const std::vector<qr::AttachClass> wcd_inputs = {
      qr::classify_attach(qr::FrameB{control.ns() - qr::kNanosecondsPerDay}, c),
      qr::classify_attach(qr::FrameB{control.ns() + qr::kNanosecondsPerDay}, c),
      qr::classify_attach(std::nullopt, c),
      c.classify_attach_ms(std::numeric_limits<std::int64_t>::max()),
  };
  for (const qr::AttachClass& other : wcd_inputs) {
    EXPECT_NE(valid.kind(), other.kind());
    EXPECT_FALSE(valid == other);
    EXPECT_FALSE(other.is_on_day());
  }
}

// WCD-8 -- classifying wrong-day, missing and malformed attachments perturbs no
// prior state, and the mask is observable: a delta_days census can be built and
// the same valid input classifies identically before and after.
TEST(ClassifyAttach, NoPriorStatePerturbationAndTheDeltaDaysCensusIsObservable) {
  const qr::SessionClock c = clock(kEdtFullDay);
  const qr::FrameB control{c.open_b().ns() + 5 * qr::kBarNs};
  const qr::AttachClass before = qr::classify_attach(control, c);

  // A snapshot of every observable the clock exposes.
  const std::string day_before(c.day());
  const std::int64_t open_before = c.open_b().ns();
  const std::int64_t close_before = c.close_b().ns();
  const std::int64_t start_before = c.session_start_a().ns();
  const std::int64_t end_before = c.session_end_a().ns();
  const std::int64_t offset_before = c.offset_ns();
  const std::int64_t bars_before = c.expected_bar_count();

  // A tape that mixes every non-ON_DAY class in among the good rows. Nothing
  // aborts, nothing is dropped, every row gets a typed class.
  std::map<std::int64_t, int> delta_days_histogram;
  int missing = 0;
  int malformed = 0;
  int on_day = 0;
  const std::vector<std::optional<std::int64_t>> tape_ms = {
      c.open_b().ns() / qr::kNanosecondsPerMillisecond,
      (c.open_b().ns() - qr::kNanosecondsPerDay) / qr::kNanosecondsPerMillisecond,
      std::nullopt,
      std::numeric_limits<std::int64_t>::max(),
      (c.open_b().ns() + 2 * qr::kNanosecondsPerDay) / qr::kNanosecondsPerMillisecond,
      (c.open_b().ns() - qr::kNanosecondsPerDay) / qr::kNanosecondsPerMillisecond,
      c.open_b().ns() / qr::kNanosecondsPerMillisecond + 1,
  };
  for (const std::optional<std::int64_t>& stamp : tape_ms) {
    const qr::AttachClass classified = c.classify_attach_ms(stamp);
    switch (classified.kind()) {
      case qr::AttachKind::MISSING:
        ++missing;
        break;
      case qr::AttachKind::MALFORMED:
        ++malformed;
        break;
      case qr::AttachKind::WRONG_CIVIL_DAY:
        ++delta_days_histogram[classified.delta_days()];
        break;
      case qr::AttachKind::ON_DAY:
        ++on_day;
        break;
    }
  }
  // PRINT RETAINED: every row of the tape got a typed class and not one was
  // dropped, skipped or aborted on.
  int wrong_day = 0;
  for (const auto& bucket : delta_days_histogram) {
    wrong_day += bucket.second;
  }
  EXPECT_EQ(missing + malformed + wrong_day + on_day, static_cast<int>(tape_ms.size()));
  EXPECT_EQ(missing, 1);
  EXPECT_EQ(malformed, 1);
  EXPECT_EQ(on_day, 2);
  ASSERT_EQ(delta_days_histogram.size(), 2U);
  EXPECT_EQ(delta_days_histogram[-1], 2);
  EXPECT_EQ(delta_days_histogram[2], 1);

  // No prior-state perturbation: the clock is exactly what it was, and the
  // control input classifies to exactly the same typed value as before.
  EXPECT_EQ(std::string(c.day()), day_before);
  EXPECT_EQ(c.open_b().ns(), open_before);
  EXPECT_EQ(c.close_b().ns(), close_before);
  EXPECT_EQ(c.session_start_a().ns(), start_before);
  EXPECT_EQ(c.session_end_a().ns(), end_before);
  EXPECT_EQ(c.offset_ns(), offset_before);
  EXPECT_EQ(c.expected_bar_count(), bars_before);
  const qr::AttachClass after = qr::classify_attach(control, c);
  EXPECT_EQ(before, after);
  EXPECT_EQ(before.frame_a(), after.frame_a());
}

// The totality claim itself, plus the i64-overflow injection: every input in
// the domain lands in exactly one of the four kinds, and none of them refuses.
TEST(ClassifyAttach, IsTotalOverTheWholeDomainAndConvertsOnlyOnDay) {
  const qr::SessionClock c = clock(kEstFullDay);
  const std::vector<std::optional<std::int64_t>> ns_inputs = {
      std::nullopt,
      std::numeric_limits<std::int64_t>::max(),
      std::numeric_limits<std::int64_t>::min(),
      0,
      -1,
      c.open_b().ns(),
      c.close_b().ns() - 1,
      c.open_b().ns() - qr::kNanosecondsPerDay,
  };
  int converted = 0;
  for (const std::optional<std::int64_t>& raw : ns_inputs) {
    const std::optional<qr::FrameB> ts_b =
        raw.has_value() ? std::optional<qr::FrameB>(qr::FrameB{*raw}) : std::nullopt;
    const qr::AttachClass classified = qr::classify_attach(ts_b, c);
    switch (classified.kind()) {
      case qr::AttachKind::ON_DAY:
        ++converted;
        EXPECT_EQ(classified.frame_a().ns(), *raw + c.offset_ns());
        break;
      case qr::AttachKind::WRONG_CIVIL_DAY:
        EXPECT_NE(classified.delta_days(), 0);
        break;
      case qr::AttachKind::MISSING:
        EXPECT_FALSE(raw.has_value());
        break;
      case qr::AttachKind::MALFORMED:
        break;
    }
  }
  EXPECT_EQ(converted, 2) << "conversion happens only in ON_DAY";
  // Every kind has its own stable name (the census writes these).
  EXPECT_STREQ(qr::attach_kind_name(qr::AttachKind::MISSING), "MISSING");
  EXPECT_STREQ(qr::attach_kind_name(qr::AttachKind::MALFORMED), "MALFORMED");
  EXPECT_STREQ(qr::attach_kind_name(qr::AttachKind::WRONG_CIVIL_DAY), "WRONG_CIVIL_DAY");
  EXPECT_STREQ(qr::attach_kind_name(qr::AttachKind::ON_DAY), "ON_DAY");
}

TEST(ClassifyAttach, CivilDayOfANaiveInstantIsExactFloorDivisionNotTruncation) {
  EXPECT_EQ(qr::civil_day_of_naive_et_ns(0), 0);
  EXPECT_EQ(qr::civil_day_of_naive_et_ns(qr::kNanosecondsPerDay - 1), 0);
  EXPECT_EQ(qr::civil_day_of_naive_et_ns(qr::kNanosecondsPerDay), 1);
  // Truncation toward zero would call this day 0; it is the day before.
  EXPECT_EQ(qr::civil_day_of_naive_et_ns(-1), -1);
  EXPECT_EQ(qr::civil_day_of_naive_et_ns(-qr::kNanosecondsPerDay), -1);
  EXPECT_EQ(qr::civil_day_of_naive_et_ns(-qr::kNanosecondsPerDay - 1), -2);
}

}  // namespace
