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
