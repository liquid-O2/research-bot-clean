// Fixtures CC-012 r1 and r2: the two walls face opposite directions and NEITHER
// weakens the other.
//
//   r1  WarmupScope refuses every ordinal >= 125 (and, exhaustively, admits
//       exactly 0..124 over the whole 1,003-session calendar).
//   r2  DayScope STILL refuses every ordinal <= 124 — the 125-wall is intact
//       after CC-012, which is the half of the ruling a new type could silently
//       break.
//
// r3 (candidate/label/emission APIs cannot be called with a WarmupScope) and r4
// (two-run byte identity of warmed priors) live with the accumulators they
// constrain, in qr_wave2/tests/test_warmup_and_prior_state.cpp.
#include <cstdint>
#include <vector>

#include "gtest/gtest.h"
#include "qr_registry/day_scope.hpp"
#include "qr_registry/registry.hpp"
#include "qr_registry/warmup_scope.hpp"

namespace {

const qr::Registry* registry_or_null() {
  static qr::Expected<qr::Registry, qr::Refusal> loaded = qr::Registry::load_embedded();
  return loaded.has_value() ? &loaded.value() : nullptr;
}

TEST(WarmupWall, AdmitsExactlyTheOneHundredTwentyFiveWarmupOrdinals) {
  const qr::Registry* const reg = registry_or_null();
  ASSERT_NE(reg, nullptr) << "embedded registry failed to load";
  std::int64_t admitted = 0;
  std::vector<std::int64_t> wrong_verdict;
  for (std::int64_t ordinal = 0; ordinal < static_cast<std::int64_t>(reg->size()); ++ordinal) {
    const auto scope = qr::WarmupScope::admit(*reg, ordinal);
    const bool expected = ordinal <= 124;
    if (scope.has_value() != expected) {
      wrong_verdict.push_back(ordinal);
      continue;
    }
    if (scope.has_value()) {
      ++admitted;
      EXPECT_EQ(scope.value().ordinal(), ordinal);
    }
  }
  EXPECT_TRUE(wrong_verdict.empty()) << "first wrong ordinal: " << wrong_verdict.front();
  EXPECT_EQ(admitted, qr::kWarmupSessionCount);
}

TEST(WarmupWall, RefusesTheFirstScopedOrdinalAndEverythingAboveIt) {
  const qr::Registry* const reg = registry_or_null();
  ASSERT_NE(reg, nullptr) << "embedded registry failed to load";
  // The exact boundary CC-012 draws: 124 is the last warmup session and 125 is
  // the first decision session, so these two calls must disagree.
  const auto last_warmup = qr::WarmupScope::admit(*reg, 124);
  ASSERT_TRUE(last_warmup.has_value());
  EXPECT_EQ(last_warmup.value().day(), "2022-07-01");

  for (const std::int64_t ordinal : {std::int64_t{125}, std::int64_t{126}, std::int64_t{500},
                                     std::int64_t{749}, std::int64_t{750}, std::int64_t{917},
                                     std::int64_t{918}, std::int64_t{1002}}) {
    const auto refused = qr::WarmupScope::admit(*reg, ordinal);
    ASSERT_FALSE(refused.has_value()) << "warmup wall admitted ordinal " << ordinal;
    EXPECT_EQ(refused.error().code(), qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE);
  }
  // A negative ordinal is outside both calendars and reaches no registry row.
  EXPECT_FALSE(qr::WarmupScope::admit(*reg, -1).has_value());
}

TEST(WarmupWall, TheScopedWallStillRefusesEveryWarmupOrdinal) {
  const qr::Registry* const reg = registry_or_null();
  ASSERT_NE(reg, nullptr) << "embedded registry failed to load";
  // r2: CC-012 says "the 125-wall stays intact for every decision/label/
  // candidate path". Adding a warmup door must not open the scoped one.
  std::vector<std::int64_t> leaked;
  for (std::int64_t ordinal = 0; ordinal <= 124; ++ordinal) {
    const auto scope = qr::DayScope::admit(*reg, ordinal);
    if (scope.has_value()) {
      leaked.push_back(ordinal);
      continue;
    }
    EXPECT_EQ(scope.error().code(), qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE);
  }
  EXPECT_TRUE(leaked.empty()) << "DayScope admitted warmup ordinal " << leaked.front();
  // and the first scoped ordinal is still admitted, so the wall did not simply
  // start refusing everything.
  EXPECT_TRUE(qr::DayScope::admit(*reg, 125).has_value());
}

TEST(WarmupWall, TheTwoCalendarsAreDisjointAndCoverTheWholeRegistry) {
  const qr::Registry* const reg = registry_or_null();
  ASSERT_NE(reg, nullptr) << "embedded registry failed to load";
  std::int64_t both = 0;
  std::int64_t neither = 0;
  for (std::int64_t ordinal = 0; ordinal < static_cast<std::int64_t>(reg->size()); ++ordinal) {
    const bool warmup = qr::WarmupScope::admit(*reg, ordinal).has_value();
    const bool scoped = qr::DayScope::admit(*reg, ordinal).has_value();
    both += (warmup && scoped) ? 1 : 0;
    // Ordinals past W belong to neither calendar BY DESIGN (the s918+ wall),
    // so "neither" is counted, not asserted away.
    neither += (!warmup && !scoped) ? 1 : 0;
  }
  EXPECT_EQ(both, 0) << "an ordinal was admitted by both walls";
  EXPECT_EQ(neither, static_cast<std::int64_t>(reg->size()) - qr::kWarmupSessionCount -
                         qr::kScopeSessionCount);
  EXPECT_TRUE(qr::is_warmup_ordinal(0));
  EXPECT_TRUE(qr::is_warmup_ordinal(124));
  EXPECT_FALSE(qr::is_warmup_ordinal(125));
}

}  // namespace
