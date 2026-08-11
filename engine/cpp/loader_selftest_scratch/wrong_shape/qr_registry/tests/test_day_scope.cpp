// Fixture SCOPE-1..SCOPE-6: the 125..749 wall fires BEFORE a path is formed.
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

TEST(ScopeWall, AdmitsExactlyTheSixHundredTwentyFiveScopedOrdinals) {
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
    const bool in_scope = ordinal >= 125 && ordinal <= 749;
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
  EXPECT_EQ(qr::kScopeLastOrdinal, 749);
}

TEST(ScopeWall, RefusesTheNamedOutOfScopeOrdinals) {
  const qr::Registry* const reg = registry_or_null();
  ASSERT_NE(reg, nullptr) << "embedded registry failed to load";
  for (const std::int64_t ordinal : {std::int64_t{750}, std::int64_t{1002}, std::int64_t{1003},
                                     std::int64_t{124}, std::int64_t{0}, std::int64_t{-1},
                                     std::int64_t{9'999'999}}) {
    const auto scope = qr::DayScope::admit(*reg, ordinal);
    ASSERT_FALSE(scope.has_value()) << "ordinal " << ordinal << " must not be admitted";
    EXPECT_EQ(scope.error().code(), qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE) << ordinal;
  }

  const auto boundary_low = qr::DayScope::admit(*reg, 125);
  ASSERT_TRUE(boundary_low.has_value());
  EXPECT_EQ(boundary_low.value().day(), "2022-07-05");
  const auto boundary_high = qr::DayScope::admit(*reg, 749);
  ASSERT_TRUE(boundary_high.has_value());
  EXPECT_EQ(boundary_high.value().day(), "2024-12-26");
}

TEST(ScopeWall, RefusalHappensBeforeAnyFilesystemAccess) {
  const qr::Registry* const reg = registry_or_null();
  ASSERT_NE(reg, nullptr) << "embedded registry failed to load";
  const std::filesystem::path root = poisoned_root();
  ASSERT_TRUE(std::filesystem::is_regular_file(root)) << "the poison must be in place";

  // Out of scope: the wall answers, so nothing ever looked at the root.
  for (const std::int64_t ordinal : {std::int64_t{750}, std::int64_t{1002}, std::int64_t{124}}) {
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
  // Registered but out of the 125..749 scope: a different, more precise wall.
  for (const char* day : {"2022-01-03", "2024-12-27", "2025-12-31"}) {
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

  for (const std::int64_t ordinal : {std::int64_t{125}, std::int64_t{437}, std::int64_t{749}}) {
    const auto resolved = qr::resolve_source_path(*reg, root, ordinal);
    ASSERT_TRUE(resolved.has_value())
        << "ordinal " << ordinal << ": " << resolved.error().message();
    EXPECT_TRUE(std::filesystem::is_regular_file(resolved.value()));
  }

  // Out of scope stays unreadable even against the real root.
  const auto refused = qr::resolve_source_path(*reg, root, 750);
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE);
}

}  // namespace
