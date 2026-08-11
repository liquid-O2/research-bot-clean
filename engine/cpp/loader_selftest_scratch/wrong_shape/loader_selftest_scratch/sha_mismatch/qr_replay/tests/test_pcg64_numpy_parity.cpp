// qr_replay/tests/test_pcg64_numpy_parity.cpp — the PCG64 + SeedSequence port
// against literals produced by numpy itself.
//
// The fixture (tests/fixtures/replay/pcg64_numpy_parity.tsv) was written once by
// tests/fixtures/make_pcg64_parity.py under numpy 2.1.2 and is committed as
// data. Nothing here recomputes an expectation from the port: if the port and
// numpy disagree by one bit, these tests go red.
#include <gtest/gtest.h>

#include <cstdint>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

#include "qr_replay/pcg64.hpp"

namespace qr::replay {
namespace {

struct CaseKey {
  std::string sid;
  std::string side_index;

  friend bool operator<(const CaseKey& a, const CaseKey& b) {
    return a.sid != b.sid ? a.sid < b.sid : a.side_index < b.side_index;
  }
};

struct Fixture {
  // kind -> case -> index-ordered values
  std::map<std::string, std::map<CaseKey, std::vector<std::uint64_t>>> rows;
  std::vector<CaseKey> cases;  // in file order
};

/// numpy `_coerce_to_uint32_array` for one non-negative integer written in
/// decimal: little-endian uint32 words, and zero contributes exactly one word.
std::vector<std::uint32_t> decimal_to_words(const std::string& text) {
  std::vector<std::uint64_t> limbs;
  for (const char c : text) {
    std::uint64_t carry = static_cast<std::uint64_t>(c - '0');
    for (std::uint64_t& limb : limbs) {
      const std::uint64_t value = limb * 10ull + carry;
      limb = value & 0xffffffffull;
      carry = value >> 32;
    }
    while (carry != 0) {
      limbs.push_back(carry & 0xffffffffull);
      carry >>= 32;
    }
  }
  if (limbs.empty()) {
    limbs.push_back(0);
  }
  std::vector<std::uint32_t> words;
  words.reserve(limbs.size());
  for (const std::uint64_t limb : limbs) {
    words.push_back(static_cast<std::uint32_t>(limb));
  }
  return words;
}

std::vector<std::uint32_t> entropy_words(const CaseKey& key) {
  std::vector<std::uint32_t> words = decimal_to_words("20260810");
  for (const std::vector<std::uint32_t>& part :
       {decimal_to_words(key.sid), decimal_to_words(key.side_index)}) {
    words.insert(words.end(), part.begin(), part.end());
  }
  return words;
}

const Fixture& fixture() {
  static const Fixture* loaded = [] {
    auto* parsed = new Fixture();
    const std::string path = std::string(QR_REPLAY_FIXTURE_DIR) + "/pcg64_numpy_parity.tsv";
    std::ifstream input(path);
    EXPECT_TRUE(input.is_open()) << "missing committed fixture " << path;
    std::string line;
    while (std::getline(input, line)) {
      if (line.empty() || line[0] == '#' || line.rfind("kind\t", 0) == 0) {
        continue;
      }
      std::istringstream fields(line);
      std::string kind;
      std::string sid;
      std::string side_index;
      std::string index;
      std::string value;
      std::getline(fields, kind, '\t');
      std::getline(fields, sid, '\t');
      std::getline(fields, side_index, '\t');
      std::getline(fields, index, '\t');
      std::getline(fields, value, '\t');
      const CaseKey key{sid, side_index};
      auto& bucket = parsed->rows[kind][key];
      const std::size_t position = static_cast<std::size_t>(std::stoull(index));
      if (bucket.size() <= position) {
        bucket.resize(position + 1);
      }
      bucket[position] = std::stoull(value);
      if (kind == "pool32") {
        bool known = false;
        for (const CaseKey& seen : parsed->cases) {
          known = known || (!(seen < key) && !(key < seen));
        }
        if (!known) {
          parsed->cases.push_back(key);
        }
      }
    }
    return parsed;
  }();
  return *loaded;
}

/// Returned BY VALUE on purpose: a reference into the fixture map, bound in a
/// call whose arguments include a temporary, trips -Wdangling-reference, and a
/// test that has to argue about lifetimes is a test nobody re-reads.
std::vector<std::uint64_t> expect_row(const std::string& kind, const CaseKey& key) {
  const auto kind_it = fixture().rows.find(kind);
  EXPECT_NE(kind_it, fixture().rows.end()) << "fixture has no rows of kind " << kind;
  const auto case_it = kind_it->second.find(key);
  EXPECT_NE(case_it, kind_it->second.end()) << "fixture has no " << kind << " for case";
  return case_it->second;
}

TEST(NumpyParity, TheFixtureItselfIsPresentAndCoversEveryCase) {
  ASSERT_FALSE(fixture().cases.empty()) << "the committed numpy literals are missing";
  EXPECT_EQ(fixture().cases.size(), 10u);
  for (const char* const kind : {"pool32", "state32", "state64", "raw64", "raw32", "coin"}) {
    EXPECT_EQ(fixture().rows.at(std::string(kind)).size(), fixture().cases.size()) << kind;
  }
}

TEST(NumpyParity, SeedSequenceMixEntropyReproducesTheNumpyPool) {
  for (const CaseKey& key : fixture().cases) {
    const std::vector<std::uint32_t> words = entropy_words(key);
    const SeedSequence seq = SeedSequence::from_entropy_words(words);
    const std::vector<std::uint64_t> expected = expect_row("pool32", key);
    ASSERT_EQ(expected.size(), SeedSequence::kPoolSize);
    for (std::size_t i = 0; i < SeedSequence::kPoolSize; ++i) {
      EXPECT_EQ(static_cast<std::uint64_t>(seq.pool()[i]), expected[i])
          << "pool word " << i << " for (" << key.sid << ", " << key.side_index << ")";
    }
  }
}

TEST(NumpyParity, GenerateStateReproducesBothTheThirtyTwoAndSixtyFourBitViews) {
  for (const CaseKey& key : fixture().cases) {
    const SeedSequence seq = SeedSequence::from_entropy_words(entropy_words(key));

    std::array<std::uint32_t, 4> state32{};
    seq.generate_state_u32(state32);
    const std::vector<std::uint64_t> expected32 = expect_row("state32", key);
    ASSERT_EQ(expected32.size(), 4u);
    for (std::size_t i = 0; i < 4; ++i) {
      EXPECT_EQ(static_cast<std::uint64_t>(state32[i]), expected32[i]) << "state32 word " << i;
    }

    std::array<std::uint64_t, 4> state64{};
    seq.generate_state_u64(state64);
    const std::vector<std::uint64_t> expected64 = expect_row("state64", key);
    ASSERT_EQ(expected64.size(), 4u);
    for (std::size_t i = 0; i < 4; ++i) {
      EXPECT_EQ(state64[i], expected64[i]) << "state64 word " << i;
    }
  }
}

TEST(NumpyParity, TheRawSixtyFourBitStreamMatchesNumpyRandomRaw) {
  for (const CaseKey& key : fixture().cases) {
    Pcg64 generator(SeedSequence::from_entropy_words(entropy_words(key)));
    const std::vector<std::uint64_t> expected = expect_row("raw64", key);
    ASSERT_EQ(expected.size(), 8u);
    for (std::size_t i = 0; i < expected.size(); ++i) {
      EXPECT_EQ(generator.next_uint64(), expected[i])
          << "raw64 draw " << i << " for (" << key.sid << ", " << key.side_index << ")";
    }
  }
}

TEST(NumpyParity, TheThirtyTwoBitStreamTakesTheLowHalfFirstAndCachesTheHigh) {
  for (const CaseKey& key : fixture().cases) {
    Pcg64 generator(SeedSequence::from_entropy_words(entropy_words(key)));
    const std::vector<std::uint64_t> expected = expect_row("raw32", key);
    ASSERT_EQ(expected.size(), 16u);
    for (std::size_t i = 0; i < expected.size(); ++i) {
      EXPECT_EQ(static_cast<std::uint64_t>(generator.next_uint32()), expected[i])
          << "raw32 draw " << i;
    }
  }
}

TEST(NumpyParity, TheCoinDrawsMatchNumpyGeneratorIntegersZeroTwo) {
  // This is the test that refuted the obvious guess: integers(0, 2) is NOT the
  // low bit of a draw. numpy takes Lemire's bounded path on the 32-bit
  // generator, so the coin is the TOP bit of next_uint32().
  for (const CaseKey& key : fixture().cases) {
    Pcg64 generator(SeedSequence::from_entropy_words(entropy_words(key)));
    const std::vector<std::uint64_t> expected = expect_row("coin", key);
    ASSERT_EQ(expected.size(), 8u);
    for (std::size_t i = 0; i < expected.size(); ++i) {
      EXPECT_EQ(static_cast<std::uint64_t>(generator.bounded_uint32(1)), expected[i])
          << "coin draw " << i << " for (" << key.sid << ", " << key.side_index << ")";
    }
  }
}

TEST(NumpyParity, CoinSideMapsTheFirstDrawOfItsOwnSeedStream) {
  // coin_side(sid, side_index) == SeedSequence([20260810, sid, side_index]) ->
  // integers(0, 2) -> {0: LONG, 1: SHORT}.
  for (const CaseKey& key : fixture().cases) {
    const std::uint64_t sid = std::stoull(key.sid);
    if (key.side_index.size() > 18) {
      continue;  // the port-coverage entropy shapes exceed an int64 index
    }
    const std::uint64_t side_index = std::stoull(key.side_index);
    const std::vector<std::uint64_t> expected = expect_row("coin", key);
    const Side expected_side = expected[0] == 0 ? Side::LONG : Side::SHORT;
    EXPECT_EQ(coin_side(static_cast<std::int64_t>(sid), static_cast<std::int64_t>(side_index)),
              expected_side)
        << "coin_side(" << key.sid << ", " << key.side_index << ")";
  }
}

TEST(NumpyParity, TheIntegerEntropyPathAgreesWithTheWordEntropyPath) {
  // from_entropy() decomposes integers the way numpy does; for every case whose
  // parts fit in 64 bits it must land on the same pool as the explicit words.
  for (const CaseKey& key : fixture().cases) {
    if (key.side_index.size() > 19) {
      continue;
    }
    const std::array<std::uint64_t, 3> values = {20260810ull, std::stoull(key.sid),
                                                 std::stoull(key.side_index)};
    const SeedSequence by_values = SeedSequence::from_entropy(values);
    const SeedSequence by_words = SeedSequence::from_entropy_words(entropy_words(key));
    for (std::size_t i = 0; i < SeedSequence::kPoolSize; ++i) {
      EXPECT_EQ(by_values.pool()[i], by_words.pool()[i]) << "pool word " << i;
    }
  }
}

TEST(U128Arithmetic, MultiplyAddAndShiftAreExactAcrossTheCarryBoundary) {
  // The 128-bit helpers are hand-written because __int128 is a GNU extension
  // this tree may not use, so their carries are tested directly.
  const U128 all_ones{0xffffffffffffffffull, 0xffffffffffffffffull};
  const U128 one{0, 1};
  EXPECT_EQ(u128_add(all_ones, one), (U128{0, 0}));  // wraps modulo 2^128
  EXPECT_EQ(u128_add(U128{0, 0xffffffffffffffffull}, one), (U128{1, 0}));
  EXPECT_EQ(u128_shl1(U128{0, 0x8000000000000000ull}), (U128{1, 0}));
  EXPECT_EQ(u128_mul(U128{0, 0xffffffffffffffffull}, U128{0, 2}),
            (U128{1, 0xfffffffffffffffeull}));
  EXPECT_EQ(u128_mul(U128{0, 0x100000000ull}, U128{0, 0x100000000ull}), (U128{1, 0}));
}

}  // namespace
}  // namespace qr::replay
