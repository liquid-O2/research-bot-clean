// Fixture SCOPE-1..SCOPE-8: the 125..917 wall fires BEFORE a path is formed.
//
// AMENDMENT 2026-08-12-c (D-038): the scope wall moved from 749 (2024-12-26) to
// W = 917 (2025-08-29) = the last registry session strictly before 2025-09-01.
// SCOPE-7/SCOPE-8 below are the new fixtures: W+1 (2025-09-02) is refused, and
// the SEALED ZONE - the 2025 share-era boundary s962 (2025-11-03) and the
// profile-flip sessions s1001/s1002 - is proven to be on the refusing side of
// the wall, which is the whole point of choosing W where D-038 put it.
//
// SCOPE-3 is the poisoned-root fixture named in the WP1 brief: the corpus root
// handed to the resolver is a REGULAR FILE, so every filesystem touch through
// it fails. An out-of-scope ordinal still comes back with the wall's refusal
// (ORDINAL_OUTSIDE_SCOPE), which is only possible if nothing was touched; an
// in-scope ordinal through the SAME root comes back with INVALID_CORPUS_ROOT,
// proving the root really is poisoned and really is examined afterwards.
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

#include "gtest/gtest.h"
#include "qr_registry/day_scope.hpp"
#include "qr_registry/registry.hpp"

namespace {

/// The loaded registry, or nullptr when loading itself refused. Returning a
/// pointer (instead of aborting) keeps a broken implementation observable as a
/// test FAILURE, which is what a red log has to record.
const qr::Registry* registry_or_null() {
  static qr::Expected<qr::Registry, qr::Refusal> loaded = qr::Registry::load_embedded();
  return loaded.has_value() ? &loaded.value() : nullptr;
}

std::filesystem::path poisoned_root() {
  const std::filesystem::path dir = std::filesystem::path(QR_TEST_SCRATCH_DIR) / "day_scope";
  std::filesystem::create_directories(dir);
  const std::filesystem::path root = dir / "poisoned_root_is_a_regular_file";
  std::ofstream out(root, std::ios::binary | std::ios::trunc);
  out << "not a directory";
  return root;
}

TEST(ScopeWall, AdmitsExactlyTheSevenHundredNinetyThreeScopedOrdinals) {
  const qr::Registry* const reg = registry_or_null();
  ASSERT_NE(reg, nullptr) << "embedded registry failed to load";
  // Exhaustive over the whole 1,003-session calendar. Mismatches are collected
  // rather than reported one EXPECT at a time, so a wrong wall produces a short
  // legible failure instead of a thousand lines.
  std::int64_t admitted = 0;
  std::vector<std::int64_t> wrong_verdict;
  std::vector<std::int64_t> wrong_refusal;
  for (std::int64_t ordinal = 0; ordinal < 1003; ++ordinal) {
    const auto scope = qr::DayScope::admit(*reg, ordinal);
    const bool in_scope = ordinal >= 125 && ordinal <= 917;
    if (scope.has_value() != in_scope) {
      wrong_verdict.push_back(ordinal);
    }
    if (scope.has_value()) {
      ++admitted;
      if (scope.value().ordinal() != ordinal) {
        wrong_verdict.push_back(ordinal);
      }
    } else if (scope.error().code() != qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE ||
               scope.error().context() != ordinal) {
      wrong_refusal.push_back(ordinal);
    }
  }
  EXPECT_TRUE(wrong_verdict.empty())
      << wrong_verdict.size() << " ordinals got the wrong admit verdict, first: "
      << (wrong_verdict.empty() ? -1 : wrong_verdict.front());
  EXPECT_TRUE(wrong_refusal.empty())
      << wrong_refusal.size() << " refusals were not ORDINAL_OUTSIDE_SCOPE(ordinal), first: "
      << (wrong_refusal.empty() ? -1 : wrong_refusal.front());
  EXPECT_EQ(admitted, qr::kScopeSessionCount);
  EXPECT_EQ(qr::kScopeFirstOrdinal, 125);
  EXPECT_EQ(qr::kScopeLastOrdinal, 917);
  EXPECT_EQ(qr::kScopeSessionCount, 793);
}

TEST(ScopeWall, RefusesTheNamedOutOfScopeOrdinals) {
  const qr::Registry* const reg = registry_or_null();
  ASSERT_NE(reg, nullptr) << "embedded registry failed to load";
  for (const std::int64_t ordinal : {std::int64_t{918}, std::int64_t{962}, std::int64_t{1001},
                                     std::int64_t{1002}, std::int64_t{1003}, std::int64_t{124},
                                     std::int64_t{0}, std::int64_t{-1},
                                     std::int64_t{9'999'999}}) {
    const auto scope = qr::DayScope::admit(*reg, ordinal);
    ASSERT_FALSE(scope.has_value()) << "ordinal " << ordinal << " must not be admitted";
    EXPECT_EQ(scope.error().code(), qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE) << ordinal;
  }

  const auto boundary_low = qr::DayScope::admit(*reg, 125);
  ASSERT_TRUE(boundary_low.has_value());
  EXPECT_EQ(boundary_low.value().day(), "2022-07-05");
  const auto boundary_high = qr::DayScope::admit(*reg, 917);
  ASSERT_TRUE(boundary_high.has_value());
  EXPECT_EQ(boundary_high.value().day(), "2025-08-29");
  // The old wall's last session and the first session past it are now BOTH
  // inside: this is the extension, stated as an equality on civil days.
  const auto old_wall = qr::DayScope::admit(*reg, 749);
  ASSERT_TRUE(old_wall.has_value());
  EXPECT_EQ(old_wall.value().day(), "2024-12-26");
  const auto first_newly_admitted = qr::DayScope::admit(*reg, 750);
  ASSERT_TRUE(first_newly_admitted.has_value());
  EXPECT_EQ(first_newly_admitted.value().day(), "2024-12-27");
}

// SCOPE-7: THE NEW WALL, stated on both sides in civil-day terms. W is the last
// session strictly before 2025-09-01; W+1 is the first session at or after it.
TEST(ScopeWall, TheAmendedWallIsTheLastSessionStrictlyBeforeSeptemberFirstTwentyTwentyFive) {
  const qr::Registry* const reg = registry_or_null();
  ASSERT_NE(reg, nullptr) << "embedded registry failed to load";

  const auto w = qr::DayScope::admit(*reg, qr::kScopeLastOrdinal);
  ASSERT_TRUE(w.has_value()) << "W itself must be admitted";
  EXPECT_LT(w.value().day(), "2025-09-01") << "W is not strictly before the seal date";

  const auto past = qr::DayScope::admit(*reg, qr::kScopeLastOrdinal + 1);
  ASSERT_FALSE(past.has_value()) << "W+1 must be refused";
  EXPECT_EQ(past.error().code(), qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE);
  EXPECT_EQ(past.error().context(), qr::kScopeLastOrdinal + 1);
  const auto past_row = reg->session_at(qr::kScopeLastOrdinal + 1);
  ASSERT_TRUE(past_row.has_value());
  EXPECT_GE(past_row.value()->day, "2025-09-01")
      << "W+1 is before the seal date, so the wall was placed too early";
  EXPECT_EQ(past_row.value()->day, "2025-09-02");

  // MAXIMALITY: every registry row strictly before the seal date is admitted,
  // and every row at or after it is refused. This is the amendment, exhaustively.
  std::vector<std::int64_t> wrong;
  for (std::int64_t ordinal = qr::kScopeFirstOrdinal;
       ordinal < static_cast<std::int64_t>(reg->size()); ++ordinal) {
    const auto row = reg->session_at(ordinal);
    ASSERT_TRUE(row.has_value());
    const bool before_seal = row.value()->day < "2025-09-01";
    if (qr::DayScope::admit(*reg, ordinal).has_value() != before_seal) {
      wrong.push_back(ordinal);
    }
  }
  EXPECT_TRUE(wrong.empty()) << wrong.size() << " ordinals disagree with the 2025-09-01 seal, "
                             << "first: " << (wrong.empty() ? -1 : wrong.front());
}

// SCOPE-8: THE SEALED ZONE (D-038 clause 5). The 2025 share-era boundary and the
// profile-flip sessions must stay strictly ABOVE the wall - their decode
// complexity is certification-day work. Named by ordinal AND by civil day, so a
// registry substitution cannot quietly move them.
TEST(ScopeWall, TheSealedZoneKeepsTheShareEraBoundaryAndTheProfileFlipSessions) {
  const qr::Registry* const reg = registry_or_null();
  ASSERT_NE(reg, nullptr) << "embedded registry failed to load";

  struct Sealed {
    std::int64_t ordinal;
    const char* day;
    const char* why;
  };
  for (const Sealed& sealed : {Sealed{962, "2025-11-03", "NBBO lot->share era boundary"},
                               Sealed{1001, "2025-12-30", "price profile flip"},
                               Sealed{1002, "2025-12-31", "price profile flip"}}) {
    const auto row = reg->session_at(sealed.ordinal);
    ASSERT_TRUE(row.has_value()) << sealed.why;
    EXPECT_EQ(row.value()->day, sealed.day) << sealed.why;
    EXPECT_GT(sealed.ordinal, qr::kScopeLastOrdinal)
        << "SEALED ZONE BREACH: " << sealed.why << " (" << sealed.day << ") is at or below W";
    const auto scope = qr::DayScope::admit(*reg, sealed.ordinal);
    ASSERT_FALSE(scope.has_value()) << "SEALED ZONE BREACH: " << sealed.why << " was admitted";
    EXPECT_EQ(scope.error().code(), qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE);
    const auto by_day = qr::DayScope::admit_day(*reg, sealed.day);
    ASSERT_FALSE(by_day.has_value()) << "SEALED ZONE BREACH by day: " << sealed.day;
    EXPECT_EQ(by_day.error().code(), qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE);
  }
}

TEST(ScopeWall, RefusalHappensBeforeAnyFilesystemAccess) {
  const qr::Registry* const reg = registry_or_null();
  ASSERT_NE(reg, nullptr) << "embedded registry failed to load";
  const std::filesystem::path root = poisoned_root();
  ASSERT_TRUE(std::filesystem::is_regular_file(root)) << "the poison must be in place";

  // Out of scope: the wall answers, so nothing ever looked at the root.
  for (const std::int64_t ordinal : {std::int64_t{918}, std::int64_t{962}, std::int64_t{1002},
                                     std::int64_t{124}}) {
    const auto resolved = qr::resolve_source_path(*reg, root, ordinal);
    ASSERT_FALSE(resolved.has_value()) << ordinal;
    EXPECT_EQ(resolved.error().code(), qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE)
        << "ordinal " << ordinal << " reached the filesystem before the wall";
  }

  // A 2026 day: refused by the calendar, again without touching the root.
  const auto in_2026 = qr::resolve_source_path_for_day(*reg, root, "2026-01-02");
  ASSERT_FALSE(in_2026.has_value());
  EXPECT_EQ(in_2026.error().code(), qr::RefusalCode::DAY_OUTSIDE_CALENDAR);

  // In scope, SAME root: now the root is examined, and it is poisoned.
  const auto scoped = qr::resolve_source_path(*reg, root, 125);
  ASSERT_FALSE(scoped.has_value());
  EXPECT_EQ(scoped.error().code(), qr::RefusalCode::INVALID_CORPUS_ROOT)
      << "the poisoned root must fail once it IS examined";
}

TEST(ScopeWall, AdmitByDayRefusesTwoThousandTwentySixAndOutOfScopeSessions) {
  const qr::Registry* const reg = registry_or_null();
  ASSERT_NE(reg, nullptr) << "embedded registry failed to load";
  for (const char* day : {"2026-01-02", "2026-08-10", "2021-12-31", "2019-01-02", "not-a-day"}) {
    const auto scope = qr::DayScope::admit_day(*reg, day);
    ASSERT_FALSE(scope.has_value()) << day;
    EXPECT_EQ(scope.error().code(), qr::RefusalCode::DAY_OUTSIDE_CALENDAR) << day;
  }
  // Registered but out of the 125..917 scope: a different, more precise wall.
  for (const char* day : {"2022-01-03", "2025-09-02", "2025-11-03", "2025-12-31"}) {
    const auto scope = qr::DayScope::admit_day(*reg, day);
    ASSERT_FALSE(scope.has_value()) << day;
    EXPECT_EQ(scope.error().code(), qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE) << day;
  }
  const auto scoped = qr::DayScope::admit_day(*reg, "2022-07-05");
  ASSERT_TRUE(scoped.has_value());
  EXPECT_EQ(scoped.value().ordinal(), 125);
}

TEST(ScopeWall, PathsAreComposedOnlyFromAnAdmittedScope) {
  const qr::Registry* const reg = registry_or_null();
  ASSERT_NE(reg, nullptr) << "embedded registry failed to load";
  const auto scope = qr::DayScope::admit(*reg, 125);
  ASSERT_TRUE(scope.has_value());
  EXPECT_EQ(scope.value().source_path("/corpus/root").string(),
            "/corpus/root/2022/2022-07-05.parquet");
  EXPECT_EQ(scope.value().session().source_relative_path, "2022/2022-07-05.parquet");
  EXPECT_EQ(scope.value().bar_count(), 390);
  EXPECT_EQ(scope.value().civil_date().to_ymd(), "2022-07-05");
  EXPECT_EQ(scope.value().profile(), qr::SourceProfile::CentInt32);
}

TEST(ScopeWall, ScopedSessionsResolveAgainstTheRealPinnedCorpus) {
  const qr::Registry* const reg = registry_or_null();
  ASSERT_NE(reg, nullptr) << "embedded registry failed to load";
  // The pinned corpus root (memory: never trust a shallow find claiming it is
  // missing). Resolution is stat-only; no payload byte is read in WP1.
  const std::filesystem::path root = "/workspace/data/tokens/stock_quotes/IWM";
  ASSERT_TRUE(std::filesystem::is_directory(root)) << "pinned IWM corpus root is missing";

  for (const std::int64_t ordinal : {std::int64_t{125}, std::int64_t{437}, std::int64_t{749},
                                     std::int64_t{750}, std::int64_t{833}, std::int64_t{917}}) {
    const auto resolved = qr::resolve_source_path(*reg, root, ordinal);
    ASSERT_TRUE(resolved.has_value())
        << "ordinal " << ordinal << ": " << resolved.error().message();
    EXPECT_TRUE(std::filesystem::is_regular_file(resolved.value()));
  }

  // Out of scope stays unreadable even against the real root.
  const auto refused = qr::resolve_source_path(*reg, root, 918);
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE);
}

}  // namespace
