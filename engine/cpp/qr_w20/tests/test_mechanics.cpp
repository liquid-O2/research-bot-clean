// qr_w20/tests/test_mechanics.cpp — the W2.0 census machinery, red-first.
//
// WHAT IS NOT RE-TESTED HERE, deliberately. The B3/B4 forbidden-column wall
// (side(38), sweep_*(47-50), prem/*_flow(53-61), unlisted greeks, and B4's
// derived block) is already proven in qr_sources
// (`SpecLaws.TheWalledColumnsAreExactlyAppendixB`, red-ledger mutation
// M315_sources_option_quote_derived_block_unwalled, plus the
// `read_pinned_column` COLUMN_FORBIDDEN refusals in the same file). This module
// reaches a payload byte ONLY through those readers, so re-asserting the wall
// here would be a second copy of an existing proof, which the repository law
// ("keep active source lean") forbids.
//
// WHAT IS TESTED HERE is exactly what W2.0 adds: exact counting, the
// strictly-prior spot read, A2's half-basis-point move boundary, coverage /
// MODALITY_ABSENT typing, the scope wall on the census entry points, and the
// two-run byte identity of an emitted census.
#include <array>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <string>
#include <type_traits>
#include <vector>

#include "gtest/gtest.h"
#include "qr_emit/npy_writer.hpp"
#include "qr_registry/registry.hpp"
#include "qr_w20/mechanics.hpp"

namespace {

using qr::w20::CensusReport;
using qr::w20::CoverageRow;
using qr::w20::DenseCounter;
using qr::w20::Era;
using qr::w20::SpotGrid;

std::filesystem::path scratch(const std::string& leaf) {
  const std::filesystem::path root = std::filesystem::path(QR_W20_TEST_SCRATCH) / leaf;
  std::filesystem::remove_all(root);
  std::filesystem::create_directories(root);
  return root;
}

/// Writes `<dir>/features/grid_1s.npy` with the given midpoints (u6), through
/// the PRODUCTION writer so the fixture cannot drift from the emitted form.
void write_grid(const std::filesystem::path& dir, const std::vector<std::int64_t>& mids) {
  std::filesystem::create_directories(dir / "features");
  const std::array<std::int64_t, 2> shape{static_cast<std::int64_t>(mids.size()), 4};
  auto created = qr::emit::NpyWriter::create(dir / "features" / "grid_1s.npy",
                                             "features/grid_1s.npy", qr::emit::NpyDtype::F4, shape);
  ASSERT_TRUE(created.has_value()) << created.error().message();
  std::vector<float> values(mids.size() * 4, 0.0F);
  for (std::size_t index = 0; index < mids.size(); ++index) {
    values[index * 4] = static_cast<float>(mids[index]);
  }
  qr::emit::NpyWriter live = std::move(created).value();
  const auto ok = live.append(std::span<const float>(values));
  ASSERT_TRUE(ok.has_value()) << ok.error().message();
  const auto finished = live.finish();
  ASSERT_TRUE(finished.has_value()) << finished.error().message();
}

const qr::Registry& registry() {
  static qr::Expected<qr::Registry, qr::Refusal> loaded = qr::Registry::load_embedded();
  EXPECT_TRUE(loaded.has_value());
  return loaded.value();
}

}  // namespace

// ---------------------------------------------------------------------------
// Exact counting.
// ---------------------------------------------------------------------------

TEST(DenseCounterLaw, QuantileIsTheExactRankRuleAndNeverInterpolates) {
  DenseCounter counter(0, 16);
  for (const std::int64_t value : {1, 1, 1, 4, 9}) {
    counter.add(value);
  }
  bool outside = true;
  // n=5. p50 -> rank ceil(2.5)=3 -> the third smallest is 1.
  EXPECT_EQ(counter.quantile(50, 100, outside), 1);
  EXPECT_FALSE(outside);
  // p75 -> rank ceil(3.75)=4 -> 4. An interpolating quantile would answer 2 or
  // 2.5 here, which is a value the data never contained.
  EXPECT_EQ(counter.quantile(75, 100, outside), 4);
  EXPECT_FALSE(outside);
  EXPECT_EQ(counter.quantile(100, 100, outside), 9);
  EXPECT_EQ(counter.count_le(1), 3);
  EXPECT_EQ(counter.count_le(3), 3);
  EXPECT_EQ(counter.count_le(4), 4);
}

TEST(DenseCounterLaw, ValuesOutsideTheDomainAreCountedApartAndNeverFoldedIn) {
  DenseCounter counter(0, 4);
  counter.add(-7);
  counter.add(2);
  counter.add(99);
  EXPECT_EQ(counter.total(), 3);
  EXPECT_EQ(counter.under(), 1);
  EXPECT_EQ(counter.over(), 1);
  // The true extremes survive the domain, so a census can never claim the
  // clipped edge was the observed maximum.
  EXPECT_EQ(counter.min(), -7);
  EXPECT_EQ(counter.max(), 99);
  EXPECT_EQ(counter.count_at(0), 0);
  EXPECT_EQ(counter.count_at(3), 0);
  EXPECT_EQ(counter.count_at(2), 1);
  bool outside = false;
  const std::int64_t high = counter.quantile(99, 100, outside);
  EXPECT_TRUE(outside);
  EXPECT_EQ(high, 4);
}

TEST(DenseCounterLaw, WeightedAdditionEqualsRepeatedAddition) {
  DenseCounter repeated(0, 8);
  DenseCounter weighted(0, 8);
  for (int index = 0; index < 5; ++index) {
    repeated.add(3);
  }
  repeated.add(11);
  weighted.add_weighted(3, 5);
  weighted.add_weighted(11, 1);
  weighted.add_weighted(4, 0);  // a zero-weight observation adds nothing.
  EXPECT_EQ(repeated.total(), weighted.total());
  EXPECT_EQ(repeated.count_at(3), weighted.count_at(3));
  EXPECT_EQ(repeated.over(), weighted.over());
  ASSERT_TRUE(repeated.sum().has_value());
  ASSERT_TRUE(weighted.sum().has_value());
  EXPECT_EQ(repeated.sum().value(), weighted.sum().value());
  EXPECT_EQ(weighted.sum().value(), 26);
}

TEST(DenseCounterLaw, ASumThatCannotBeRepresentedRefusesInsteadOfWrapping) {
  // (a) the COUNT cannot be represented: the observation is refused, the
  // counter is flagged, and nothing wraps or clamps.
  DenseCounter counts(0, 4);
  counts.add_weighted(1, 9223372036854775807LL);
  counts.add_weighted(1, 2);
  EXPECT_TRUE(counts.counts_overflowed());
  EXPECT_EQ(counts.total(), 9223372036854775807LL);
  EXPECT_EQ(counts.count_at(1), 9223372036854775807LL);

  // (b) the SUM cannot be represented while the counts still can: the counts
  // stay exact and only the sum refuses.
  DenseCounter sums(0, 4);
  sums.add(9223372036854775807LL);
  sums.add(2);
  EXPECT_FALSE(sums.counts_overflowed());
  EXPECT_EQ(sums.total(), 2);
  const auto sum = sums.sum();
  ASSERT_FALSE(sum.has_value());
  EXPECT_EQ(sum.error().code(), qr::RefusalCode::ARITHMETIC_OVERFLOW);
}

// ---------------------------------------------------------------------------
// The strictly-prior spot series.
// ---------------------------------------------------------------------------

TEST(SpotGridLaw, TheReadEndpointIsTheLastCompleteSecondAtOrBeforeTheInstant) {
  const std::filesystem::path dir = scratch("grid_prior");
  // bar_count 1 => 61 endpoints. The step is 64 u6 because the emitted leaf is
  // f4: near $100 the float32 grid is exact only on multiples of 8 u6, so a
  // fixture stepping by 1 would be asserting a value the leaf cannot hold.
  std::vector<std::int64_t> mids(61, 0);
  for (std::size_t index = 0; index < mids.size(); ++index) {
    mids[index] = 100000000 + 64 * static_cast<std::int64_t>(index);
  }
  write_grid(dir, mids);
  const auto grid = SpotGrid::open(dir, 1000, 1);
  ASSERT_TRUE(grid.has_value()) << grid.error().message();
  EXPECT_EQ(grid.value().endpoints(), 61);
  EXPECT_EQ(grid.value().present_endpoints(), 61);
  // open = 1000ms. An instant 1ms into second 3 still reads endpoint 3, and an
  // instant 1ms BEFORE it reads endpoint 2 — never the endpoint ahead.
  EXPECT_EQ(grid.value().mid_u6_at(1000 + 3000), 100000192);
  EXPECT_EQ(grid.value().mid_u6_at(1000 + 3001), 100000192);
  EXPECT_EQ(grid.value().mid_u6_at(1000 + 2999), 100000128);
  EXPECT_EQ(grid.value().mid_u6_at(999), 0);
}

TEST(SpotGridLaw, ExactlyHalfABasisPointIsAMoveAndOneUnitLessIsNot) {
  const std::filesystem::path dir = scratch("grid_move");
  // A2: "spot-move event = |Delta mid| >= 0.5bps". At m = 200,000,000 u6, half
  // a basis point is exactly 10,000 u6. Every level below is a multiple of 16,
  // which is the f4 leaf's exact grid at $200 — a fixture that straddled the
  // boundary by less than one ULP would be testing float rounding, not the law.
  std::vector<std::int64_t> mids(61, 200000000);
  for (std::size_t index = 10; index <= 11; ++index) {
    mids[index] = 200000000 + 9984;  // 0.4992bp: UNDER the boundary
  }
  for (std::size_t index = 30; index <= 39; ++index) {
    mids[index] = 200000000 + 10000;  // exactly 0.5bp up: a move at 30
  }
  for (std::size_t index = 40; index < mids.size(); ++index) {
    mids[index] = 200000000 - 10000;  // 1bp down off the raised level: a move at 40
  }
  write_grid(dir, mids);
  const auto grid = SpotGrid::open(dir, 0, 1);
  ASSERT_TRUE(grid.has_value()) << grid.error().message();
  const std::vector<std::int64_t>& moves = grid.value().move_endpoints();
  EXPECT_EQ(moves, (std::vector<std::int64_t>{30, 40}));
}

TEST(SpotGridLaw, AnAbsentEndpointIsAbsentAndIsNeverAMoveAgainstZero) {
  const std::filesystem::path dir = scratch("grid_absent");
  std::vector<std::int64_t> mids(61, 0);
  for (std::size_t index = 30; index < mids.size(); ++index) {
    mids[index] = 150000000;
  }
  write_grid(dir, mids);
  const auto grid = SpotGrid::open(dir, 0, 1);
  ASSERT_TRUE(grid.has_value()) << grid.error().message();
  EXPECT_EQ(grid.value().present_endpoints(), 31);
  EXPECT_EQ(grid.value().mid_u6_at(29000), 0);
  EXPECT_EQ(grid.value().mid_u6_at(30000), 150000000);
  // The 0 -> 150,000,000 step at endpoint 30 is an APPEARANCE, not a move: a
  // missing endpoint carries 0 and zero is not a price.
  EXPECT_TRUE(grid.value().move_endpoints().empty());
}

TEST(SpotGridLaw, AGridWhoseLengthDisagreesWithTheSessionRefuses) {
  const std::filesystem::path dir = scratch("grid_short");
  write_grid(dir, std::vector<std::int64_t>(60, 100000000));
  const auto grid = SpotGrid::open(dir, 0, 1);  // bar_count 1 demands 61 rows
  ASSERT_FALSE(grid.has_value());
  EXPECT_EQ(grid.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}

// ---------------------------------------------------------------------------
// Coverage typing and the scope wall.
// ---------------------------------------------------------------------------

TEST(CoverageLaw, AnUncoveredSessionIsModalityAbsentAndNotAnError) {
  const std::filesystem::path root = scratch("coverage_absent");
  const auto scope = qr::DayScope::admit(registry(), 125);
  ASSERT_TRUE(scope.has_value());
  const auto row = qr::w20::coverage_of(scope.value(), root);
  ASSERT_TRUE(row.has_value()) << row.error().message();
  EXPECT_EQ(row.value().era, Era::ABSENT);
  EXPECT_EQ(row.value().shard_count, 0);
  EXPECT_EQ(row.value().bytes, 0);
  EXPECT_EQ(row.value().day, scope.value().day());

  // ... and the DIALECT census, which must open a file, says MODALITY_ABSENT
  // rather than inventing an empty dialect.
  const auto dialect = qr::w20::option_quote_dialect(scope.value(), root);
  ASSERT_FALSE(dialect.has_value());
  EXPECT_EQ(dialect.error().code(), qr::RefusalCode::MODALITY_ABSENT);
  EXPECT_EQ(dialect.error().context(), 125);
}

TEST(CoverageLaw, TheFlatAndShardLayoutsAreDistinguishedAndShardsAreCountedInSortedOrder) {
  const std::filesystem::path root = scratch("coverage_eras");
  const auto flat_scope = qr::DayScope::admit(registry(), 125);
  const auto shard_scope = qr::DayScope::admit(registry(), 126);
  ASSERT_TRUE(flat_scope.has_value());
  ASSERT_TRUE(shard_scope.has_value());

  const std::string flat_day = flat_scope.value().day();
  const std::string shard_day = shard_scope.value().day();
  std::filesystem::create_directories(root / flat_day.substr(0, 4));
  {
    std::ofstream out(root / flat_day.substr(0, 4) / (flat_day + ".parquet"), std::ios::binary);
    out << "0123456789";
  }
  const std::filesystem::path shard_dir = root / shard_day.substr(0, 4) / shard_day;
  std::filesystem::create_directories(shard_dir);
  // Written in REVERSE name order on purpose: the census must not depend on the
  // directory's natural order (two-run byte identity is a law).
  for (const char* name : {"expB.parquet", "expA.parquet", "notes.txt"}) {
    std::ofstream out(shard_dir / name, std::ios::binary);
    out << "abc";
  }

  const auto flat = qr::w20::coverage_of(flat_scope.value(), root);
  ASSERT_TRUE(flat.has_value());
  EXPECT_EQ(flat.value().era, Era::FLAT);
  EXPECT_EQ(flat.value().shard_count, 1);
  EXPECT_EQ(flat.value().bytes, 10);

  const auto sharded = qr::w20::coverage_of(shard_scope.value(), root);
  ASSERT_TRUE(sharded.has_value());
  EXPECT_EQ(sharded.value().era, Era::SHARD);
  // `notes.txt` is not a shard: only `.parquet` counts.
  EXPECT_EQ(sharded.value().shard_count, 2);
  EXPECT_EQ(sharded.value().bytes, 6);
}

TEST(ScopeWallLaw, ACensusOrdinalOutsideTheScopeNeverProducesAScopeOrAPath) {
  for (const std::int64_t ordinal : {124, 750, 962, 1002}) {
    const auto scope = qr::DayScope::admit(registry(), ordinal);
    ASSERT_FALSE(scope.has_value()) << "ordinal " << ordinal << " must not admit";
    EXPECT_EQ(scope.error().code(), qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE);
  }
  // The census entry points take a DayScope, so there is no overload that could
  // accept a raw ordinal and form a path from it.
  static_assert(!std::is_invocable_v<decltype(&qr::w20::coverage_of), std::int64_t,
                                     const std::filesystem::path&>);
}

// ---------------------------------------------------------------------------
// Determinism of the emitted census.
// ---------------------------------------------------------------------------

TEST(CensusReportLaw, TwoWritesOfTheSameCensusAreByteIdentical) {
  const std::filesystem::path dir = scratch("census_identity");
  CensusReport report;
  DenseCounter counter(0, 8);
  for (const std::int64_t value : {0, 1, 1, 2, 5, 5, 5, 99}) {
    counter.add(value);
  }
  report.text("session", "s125", "day", "2022-07-05");
  report.metric("stream", "s125", "rth_rows", 42);
  report.distribution("s125", "example", counter);
  report.histogram("s125", "example_hist", counter);

  const auto first = report.write(dir / "run1.tsv");
  ASSERT_TRUE(first.has_value());
  const auto second = report.write(dir / "run2.tsv");
  ASSERT_TRUE(second.has_value());

  const auto slurp = [](const std::filesystem::path& path) {
    std::ifstream in(path, std::ios::binary);
    return std::string((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
  };
  const std::string run1 = slurp(dir / "run1.tsv");
  const std::string run2 = slurp(dir / "run2.tsv");
  EXPECT_EQ(run1, run2);
  EXPECT_NE(run1.find("s125\texample\tp50\t2\n"), std::string::npos) << run1;
  EXPECT_NE(run1.find("s125\texample\tcounts_overflowed\t0\n"), std::string::npos) << run1;
  EXPECT_NE(run1.find("s125\texample_hist\tcell_over\t1\n"), std::string::npos) << run1;
}
