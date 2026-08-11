// qr_m25/tests/test_twin_ceiling.cpp — Q_max, the twin-discordance observability
// ceiling (FINAL_PLAN section 8 item 1).
//
// The ceiling is checked at both ends of its own definition:
//   * when the causal prefix DETERMINES the outcome, indistinguishable actions
//     have indistinguishable outcomes and the ceiling must be near 1;
//   * when the prefix says nothing at all, twins are maximally discordant and
//     the ceiling must collapse to near 0 — and that is the case that makes the
//     M2.5 gate able to fail.
#include <gtest/gtest.h>

#include <cmath>
#include <vector>

#include "m25_test_support.hpp"
#include "qr_m25/twins.hpp"

namespace {

using qr::m25::accumulate_twins;
using qr::m25::build_skill_draws;
using qr::m25::SessionTape;
using qr::m25::test::Spec;
using qr::m25::twin_ceiling;

constexpr std::size_t kWidth = 8;
constexpr std::int64_t kRows = 600;

/// A deterministic uniform in [0,1) that is a pure function of its argument.
double mixed(std::uint64_t x) {
  x += 0x9E3779B97F4A7C15ULL;
  x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9ULL;
  x = (x ^ (x >> 27)) * 0x94D049BB133111EBULL;
  x ^= x >> 31;
  return static_cast<double>(x >> 11) * (1.0 / 9007199254740992.0);
}

/// Build a one-side session where the outcome is `signal` and the prefix is
/// `carrier` — the two are equal in the reachable construction and independent
/// in the unreachable one.
struct Built {
  SessionTape tape;
  std::vector<float> prefix;
};

Built build(bool prefix_determines_outcome) {
  std::vector<Spec> specs;
  std::vector<float> prefix(static_cast<std::size_t>(kRows) * kWidth, 0.0F);
  for (std::int64_t c = 0; c < kRows; ++c) {
    const double signal = mixed(static_cast<std::uint64_t>(c) * 2 + 1);
    const double independent = mixed(static_cast<std::uint64_t>(c) * 977 + 12345);
    const double outcome = prefix_determines_outcome ? signal : independent;
    const double carrier = signal;
    Spec spec;
    spec.clock = c;
    spec.is_long = true;
    spec.net_cent = static_cast<std::int64_t>(std::llround((outcome - 0.5) * 20000.0));
    spec.hold_seconds = 30;
    specs.push_back(spec);
    for (std::size_t w = 0; w < kWidth; ++w) {
      prefix[static_cast<std::size_t>(c) * kWidth + w] = static_cast<float>(carrier);
    }
  }
  return Built{qr::m25::test::make_tape(125, 2022, specs, 1), std::move(prefix)};
}

}  // namespace

TEST(TwinCeiling, APrefixThatDeterminesTheOutcomeGivesACeilingNearOne) {
  Built built = build(true);
  const auto draws = build_skill_draws(built.tape, 0);
  const auto accumulated = accumulate_twins(built.tape, draws, built.prefix, kWidth, 60);
  ASSERT_GT(accumulated.pair_count[0], 0);
  const qr::m25::TwinCeiling ceiling = twin_ceiling(accumulated, 2);
  EXPECT_GT(ceiling.q_max, 0.95) << "d0=" << ceiling.d0 << " var=" << ceiling.variance;
  EXPECT_GT(ceiling.q_max_k1, 0.90);
  // The clock bucket alone still knows nothing: the outcome is not a function of
  // the time of day in this construction.
  EXPECT_LT(ceiling.q_max_clock_only, 0.35);
}

TEST(TwinCeiling, APrefixThatSaysNothingCollapsesTheCeilingToZero) {
  Built built = build(false);
  const auto draws = build_skill_draws(built.tape, 0);
  const auto accumulated = accumulate_twins(built.tape, draws, built.prefix, kWidth, 60);
  const qr::m25::TwinCeiling ceiling = twin_ceiling(accumulated, 2);
  EXPECT_LT(ceiling.q_max, 0.30) << "d0=" << ceiling.d0 << " var=" << ceiling.variance;
  EXPECT_LT(ceiling.q_max_k1, 0.30);
  EXPECT_LT(ceiling.q_max_clock_only, 0.30);
}

TEST(TwinCeiling, TheExtrapolationNeverExceedsTheNearestNeighbourBound) {
  for (const bool determines : {true, false}) {
    Built built = build(determines);
    const auto draws = build_skill_draws(built.tape, 0);
    for (const std::int64_t bucket : qr::m25::kTwinBucketSeconds) {
      const auto accumulated = accumulate_twins(built.tape, draws, built.prefix, kWidth, bucket);
      if (accumulated.pair_count[0] == 0) {
        continue;
      }
      const qr::m25::TwinCeiling ceiling = twin_ceiling(accumulated, 2);
      // D0 <= D1 (the ladder is increasing in distance), so the extrapolated
      // ceiling is never STRICTER than the conservative one, and neither leaves
      // [0,1].
      EXPECT_LE(ceiling.d0, ceiling.d1 + 1e-12);
      EXPECT_GE(ceiling.q_max, ceiling.q_max_k1 - 1e-12);
      EXPECT_GE(ceiling.q_max, 0.0);
      EXPECT_LE(ceiling.q_max, 1.0);
    }
  }
}

TEST(TwinCeiling, ExactPrefixTwinsAreCountedAsSuch) {
  // Two rows of one bucket carrying byte-identical prefixes: the literal twin of
  // the ruling. The census has to see them, because the whole reason the
  // ceiling is estimated by extrapolation is that on the REAL corpus this count
  // is zero.
  std::vector<Spec> specs;
  std::vector<float> prefix(static_cast<std::size_t>(10) * kWidth, 0.0F);
  for (std::int64_t c = 0; c < 10; ++c) {
    Spec spec;
    spec.clock = c;
    spec.is_long = true;
    spec.net_cent = c * 137;
    specs.push_back(spec);
    for (std::size_t w = 0; w < kWidth; ++w) {
      // Rows 3 and 4 share a prefix exactly; everyone else is distinct.
      const double value = (c == 4) ? 3.0 : static_cast<double>(c);
      prefix[static_cast<std::size_t>(c) * kWidth + w] = static_cast<float>(value);
    }
  }
  SessionTape tape = qr::m25::test::make_tape(125, 2022, specs, 1);
  const auto draws = build_skill_draws(tape, 0);
  const auto accumulated = accumulate_twins(tape, draws, prefix, kWidth, 60);
  // Both members of the pair report the other as their zero-distance nearest
  // neighbour, so the census counts two directed pairs.
  EXPECT_EQ(accumulated.exact_key_twin_pairs, 2);
  EXPECT_EQ(accumulated.cell_count, 1);
  EXPECT_EQ(accumulated.rows_in_cells, 10);
}

TEST(TwinCeiling, RowsWithoutAnOutcomeTakeNoPartInAnyPair) {
  std::vector<Spec> specs;
  std::vector<float> prefix(static_cast<std::size_t>(6) * kWidth, 0.0F);
  for (std::int64_t c = 0; c < 6; ++c) {
    Spec spec;
    spec.clock = c;
    spec.is_long = true;
    spec.net_cent = c * 1000;
    spec.available = c < 3;  // the last three carry no fresh label
    specs.push_back(spec);
    for (std::size_t w = 0; w < kWidth; ++w) {
      prefix[static_cast<std::size_t>(c) * kWidth + w] = static_cast<float>(c);
    }
  }
  SessionTape tape = qr::m25::test::make_tape(125, 2022, specs, 1);
  const auto draws = build_skill_draws(tape, 0);
  const auto accumulated = accumulate_twins(tape, draws, prefix, kWidth, 60);
  EXPECT_EQ(accumulated.rows_in_cells, 3);
  EXPECT_EQ(accumulated.z_row_count, 3);
  EXPECT_EQ(accumulated.all_pair_count, 3);  // 3 choose 2
}

// --- the OVERLAP DEFECT, reproduced in miniature ---------------------------
//
// The construction: the outcome is a per-block constant (plus a whisper of
// noise) and the holding window is as long as a block, so actions inside one
// block are nearly the same trade AND nearly the same outcome; the causal prefix
// is independent noise and says nothing about anything. An overlap-permitting
// twin ladder therefore reports a ceiling near 1 — the exact artefact measured
// on the real corpus — while the truth is that the prefix carries no
// information at all. The DISJOINT ladder has to say so.

namespace {

Built build_block_outcomes(std::int64_t rows, std::int64_t block, std::int64_t hold_seconds) {
  std::vector<Spec> specs;
  std::vector<float> prefix(static_cast<std::size_t>(rows) * kWidth, 0.0F);
  for (std::int64_t c = 0; c < rows; ++c) {
    const double level = mixed(static_cast<std::uint64_t>(c / block) * 31 + 5);
    const double whisper = mixed(static_cast<std::uint64_t>(c) * 13 + 991) * 0.002;
    Spec spec;
    spec.clock = c;
    spec.is_long = true;
    spec.net_cent = static_cast<std::int64_t>(std::llround((level + whisper - 0.5) * 20000.0));
    spec.hold_seconds = hold_seconds;
    specs.push_back(spec);
    for (std::size_t w = 0; w < kWidth; ++w) {
      prefix[static_cast<std::size_t>(c) * kWidth + w] =
          static_cast<float>(mixed(static_cast<std::uint64_t>(c) * 7919 + w * 104729));
    }
  }
  return Built{qr::m25::test::make_tape(125, 2022, specs, 1), std::move(prefix)};
}

}  // namespace

TEST(TwinCeiling, OverlappingNeighboursManufactureACeilingTheDisjointLadderRefuses) {
  // 600 rows at one per second, outcome constant over 60-row blocks, each trade
  // held 60 seconds: inside a block every pair overlaps and shares its outcome.
  Built built = build_block_outcomes(600, 60, 60);
  const auto draws = build_skill_draws(built.tape, 0);

  // At the 60s bucket a cell IS a block: the overlap-permitting ladder sees
  // near-identical outcomes and manufactures a ceiling near 1, and there is not
  // one disjoint pair to check it with.
  const auto inside = accumulate_twins(built.tape, draws, built.prefix, kWidth, 60);
  const qr::m25::TwinCeiling manufactured = twin_ceiling(inside, 2);
  EXPECT_GT(manufactured.q_max_k1, 0.9) << "the artefact did not reproduce";
  EXPECT_EQ(manufactured.disjoint_pairs, 0);
  EXPECT_EQ(manufactured.q_max_disjoint, 0.0);

  // At the 300s bucket a cell spans five blocks, so disjoint pairs exist — and
  // they say what is true: the prefix carries nothing.
  const auto across = accumulate_twins(built.tape, draws, built.prefix, kWidth, 300);
  const qr::m25::TwinCeiling honest = twin_ceiling(across, 2);
  EXPECT_GT(honest.disjoint_pairs, 0);
  EXPECT_LT(honest.q_max_disjoint, 0.45)
      << "disjoint pairs must not inherit the overlap artefact: d0="
      << honest.d0_disjoint << " d1=" << honest.d1_disjoint;
  EXPECT_GT(honest.q_max_k1, honest.q_max_disjoint_k1)
      << "the overlap-permitting ladder must be the more optimistic of the two";
}

TEST(TwinCeiling, ADisjointPairIsOneWhoseHoldingWindowsDoNotTouch) {
  // Four rows one second apart, each held 1 second: rows 0 and 2 are disjoint
  // (0 exits at t+2 <= 2's entry at t+3), adjacent rows are not.
  std::vector<Spec> specs;
  std::vector<float> prefix(static_cast<std::size_t>(4) * kWidth, 0.0F);
  for (std::int64_t c = 0; c < 4; ++c) {
    Spec spec;
    spec.clock = c;
    spec.is_long = true;
    spec.net_cent = c * 1000;
    spec.hold_seconds = 1;
    specs.push_back(spec);
    for (std::size_t w = 0; w < kWidth; ++w) {
      prefix[static_cast<std::size_t>(c) * kWidth + w] = static_cast<float>(c);
    }
  }
  SessionTape tape = qr::m25::test::make_tape(125, 2022, specs, 1);
  const auto draws = build_skill_draws(tape, 0);
  const auto accumulated = accumulate_twins(tape, draws, prefix, kWidth, 60);
  // 6 unordered pairs; entry_i = t_i + 1s and exit_i = t_i + 2s, so a pair is
  // disjoint iff the clocks differ by at least 2: (0,2), (0,3), (1,3) = 3.
  EXPECT_EQ(accumulated.all_pair_count, 6);
  EXPECT_EQ(accumulated.all_disjoint_pair_count[2], 3);
  // Every row has at least one disjoint partner except none: rows 0,1,2,3 each
  // have 2,1,1,2 -> 6 directed nearest-disjoint pairs at k = 0.
  EXPECT_EQ(accumulated.disjoint_pair_count[0][2], 4);
}

TEST(TwinCeiling, AHoldingWindowLongerThanTheBucketLeavesNoDisjointPairAtAll) {
  Built built = build(true);
  const auto draws = build_skill_draws(built.tape, 0);
  // Trades held 30s inside a 15s bucket can never be disjoint.
  const auto accumulated = accumulate_twins(built.tape, draws, built.prefix, kWidth, 15);
  EXPECT_EQ(accumulated.disjoint_pair_count[0][2], 0);
  const qr::m25::TwinCeiling ceiling = twin_ceiling(accumulated, 2);
  EXPECT_EQ(ceiling.disjoint_pairs, 0);
  // No support means NO ceiling — never a ceiling of 1 by default.
  EXPECT_EQ(ceiling.q_max_disjoint, 0.0);
  EXPECT_EQ(ceiling.q_max_disjoint_k1, 0.0);
}

TEST(TwinCeiling, ACellLargerThanTheCapIsThinnedByADeterministicStride) {
  // 1,200 rows in one 3,600s bucket: the cap is 512, so the stride is
  // ceil(1200/512) = 3 and exactly ceil(1200/3) = 400 members survive — a pure
  // function of the cell, with no randomness anywhere near it.
  Built built = build_block_outcomes(1200, 60, 30);
  const auto draws = build_skill_draws(built.tape, 0);
  const auto capped = accumulate_twins(built.tape, draws, built.prefix, kWidth, 3600);
  EXPECT_EQ(capped.cell_count, 1);
  EXPECT_EQ(capped.rows_in_cells, 400);
  EXPECT_LE(static_cast<std::size_t>(capped.rows_in_cells), qr::m25::kTwinCellCap);
  // And it is the SAME 400 every time.
  const auto again = accumulate_twins(built.tape, draws, built.prefix, kWidth, 3600);
  EXPECT_EQ(again.rows_in_cells, capped.rows_in_cells);
  EXPECT_EQ(again.pair_count[0], capped.pair_count[0]);
  EXPECT_DOUBLE_EQ(again.distance_sum[0], capped.distance_sum[0]);
}
