// qr_replay/src/pcg64.cpp — numpy-semantics SeedSequence + PCG64.
//
// Every constant and every step below mirrors numpy 2.1.2:
//   numpy/random/bit_generator.pyx  (SeedSequence: _hashmix/_mix/mix_entropy/
//                                    generate_state, INIT_A..XSHIFT)
//   numpy/random/src/pcg64/pcg64.h  (pcg_setseq_128_step_r,
//                                    pcg_output_xsl_rr_128_64, pcg64_next32)
//   numpy/random/_bounded_integers.pyx.in (bounded_lemire_uint32)
// and is pinned literal-by-literal by tests/fixtures/replay/pcg64_numpy_parity.tsv.
#include "qr_replay/pcg64.hpp"

#include <cstdint>

#include "qr_core/refusal.hpp"

namespace qr::replay {
namespace {

// --- SeedSequence constants (numpy bit_generator.pyx) -----------------------
constexpr std::uint32_t kInitA = 0x43b0d7e5u;
constexpr std::uint32_t kMultA = 0x931e8875u;
constexpr std::uint32_t kInitB = 0x8b51f9ddu;
constexpr std::uint32_t kMultB = 0x58f38dedu;
constexpr std::uint32_t kMixMultL = 0xca01f9ddu;
constexpr std::uint32_t kMixMultR = 0x4973f715u;
constexpr int kXShift = 16;  // itemsize * 8 // 2 for uint32

// --- PCG64 constants (numpy pcg64.h: PCG_DEFAULT_MULTIPLIER_128) ------------
constexpr U128 kPcgMultiplier{0x2360ed051fc65da4ull, 0x4385df649fccf645ull};

/// numpy `_hashmix`: mutates the rolling hash constant and returns the mixed value.
std::uint32_t hashmix(std::uint32_t value, std::uint32_t& hash_const) noexcept {
  value ^= hash_const;
  hash_const *= kMultA;
  value *= hash_const;
  value ^= value >> kXShift;
  return value;
}

/// numpy `_mix`.
std::uint32_t mix(std::uint32_t x, std::uint32_t y) noexcept {
  std::uint32_t result = kMixMultL * x - kMixMultR * y;
  result ^= result >> kXShift;
  return result;
}

/// 64x64 -> 128 exact product, built from 32-bit halves because
/// `unsigned __int128` is a GNU extension this tree may not use.
U128 mul64(std::uint64_t a, std::uint64_t b) noexcept {
  const std::uint64_t a_lo = a & 0xffffffffull;
  const std::uint64_t a_hi = a >> 32;
  const std::uint64_t b_lo = b & 0xffffffffull;
  const std::uint64_t b_hi = b >> 32;

  const std::uint64_t ll = a_lo * b_lo;
  const std::uint64_t lh = a_lo * b_hi;
  const std::uint64_t hl = a_hi * b_lo;
  const std::uint64_t hh = a_hi * b_hi;

  const std::uint64_t mid = (ll >> 32) + (lh & 0xffffffffull) + (hl & 0xffffffffull);
  U128 out{};
  out.lo = (ll & 0xffffffffull) | (mid << 32);
  out.hi = hh + (lh >> 32) + (hl >> 32) + (mid >> 32);
  return out;
}

std::uint64_t rotr64(std::uint64_t value, std::uint32_t rot) noexcept {
  return (value >> rot) | (value << ((0u - rot) & 63u));
}

}  // namespace

U128 u128_add(U128 a, U128 b) noexcept {
  U128 out{};
  out.lo = a.lo + b.lo;
  out.hi = a.hi + b.hi + (out.lo < a.lo ? 1ull : 0ull);
  return out;
}

U128 u128_mul(U128 a, U128 b) noexcept {
  U128 out = mul64(a.lo, b.lo);
  out.hi += a.hi * b.lo + a.lo * b.hi;
  return out;
}

U128 u128_shl1(U128 a) noexcept {
  U128 out{};
  out.hi = (a.hi << 1) | (a.lo >> 63);
  out.lo = a.lo << 1;
  return out;
}

// --- SeedSequence -----------------------------------------------------------

SeedSequence SeedSequence::from_entropy_words(std::span<const std::uint32_t> words) noexcept {
  SeedSequence seq;
  std::uint32_t hash_const = kInitA;

  // "Add in the entropy up to the pool size."
  for (std::size_t i = 0; i < kPoolSize; ++i) {
    const std::uint32_t value = i < words.size() ? words[i] : 0u;
    seq.pool_[i] = hashmix(value, hash_const);
  }
  // "Mix all bits together so late bits can affect earlier bits."
  for (std::size_t i_src = 0; i_src < kPoolSize; ++i_src) {
    for (std::size_t i_dst = 0; i_dst < kPoolSize; ++i_dst) {
      if (i_src != i_dst) {
        seq.pool_[i_dst] = mix(seq.pool_[i_dst], hashmix(seq.pool_[i_src], hash_const));
      }
    }
  }
  // "Add any remaining entropy, mixing each new entropy word with each pool word."
  for (std::size_t i_src = kPoolSize; i_src < words.size(); ++i_src) {
    for (std::size_t i_dst = 0; i_dst < kPoolSize; ++i_dst) {
      seq.pool_[i_dst] = mix(seq.pool_[i_dst], hashmix(words[i_src], hash_const));
    }
  }
  return seq;
}

SeedSequence SeedSequence::from_entropy(std::span<const std::uint64_t> values) {
  // numpy `_coerce_to_uint32_array`: each integer becomes its little-endian
  // uint32 words, and a zero becomes exactly one zero word.
  std::vector<std::uint32_t> words;
  words.reserve(values.size() * 2);
  for (const std::uint64_t value : values) {
    if (value == 0) {
      words.push_back(0u);
      continue;
    }
    std::uint64_t remaining = value;
    while (remaining > 0) {
      words.push_back(static_cast<std::uint32_t>(remaining & 0xffffffffull));
      remaining >>= 32;
    }
  }
  return from_entropy_words(words);
}

void SeedSequence::generate_state_u32(std::span<std::uint32_t> out) const noexcept {
  std::uint32_t hash_const = kInitB;
  for (std::size_t i = 0; i < out.size(); ++i) {
    std::uint32_t data_val = pool_[i % kPoolSize];  // itertools.cycle(self.pool)
    data_val ^= hash_const;
    hash_const *= kMultB;
    data_val *= hash_const;
    data_val ^= data_val >> kXShift;
    out[i] = data_val;
  }
}

void SeedSequence::generate_state_u64(std::span<std::uint64_t> out) const noexcept {
  std::vector<std::uint32_t> words(out.size() * 2);
  generate_state_u32(words);
  for (std::size_t i = 0; i < out.size(); ++i) {
    // `.view(np.uint64)` on a little-endian machine: low word first.
    out[i] = static_cast<std::uint64_t>(words[2 * i]) |
             (static_cast<std::uint64_t>(words[2 * i + 1]) << 32);
  }
}

// --- PCG64 ------------------------------------------------------------------

Pcg64::Pcg64(const SeedSequence& seed) noexcept {
  std::array<std::uint64_t, 4> words{};
  seed.generate_state_u64(words);

  // pcg64_set_seed: seed = (w0 << 64) | w1, inc = (w2 << 64) | w3.
  const U128 initstate{words[0], words[1]};
  const U128 initseq{words[2], words[3]};

  // pcg_setseq_128_srandom_r.
  state_ = U128{0, 0};
  inc_ = u128_shl1(initseq);
  inc_.lo |= 1ull;
  step();
  state_ = u128_add(state_, initstate);
  step();
}

void Pcg64::step() noexcept { state_ = u128_add(u128_mul(state_, kPcgMultiplier), inc_); }

std::uint64_t Pcg64::next_uint64() noexcept {
  step();
  // pcg_output_xsl_rr_128_64: rotr64((hi ^ lo), state >> 122).
  const std::uint64_t xored = state_.hi ^ state_.lo;
  const std::uint32_t rot = static_cast<std::uint32_t>(state_.hi >> 58);
  return rotr64(xored, rot);
}

std::uint32_t Pcg64::next_uint32() noexcept {
  if (has_uint32_) {
    has_uint32_ = false;
    return cached_uint32_;
  }
  const std::uint64_t next = next_uint64();
  has_uint32_ = true;
  cached_uint32_ = static_cast<std::uint32_t>(next >> 32);
  return static_cast<std::uint32_t>(next & 0xffffffffull);
}

std::uint32_t Pcg64::bounded_uint32(std::uint32_t rng_inclusive) noexcept {
  if (rng_inclusive == 0) {
    return 0;
  }
  // bounded_lemire_uint32.
  const std::uint64_t rng_excl = static_cast<std::uint64_t>(rng_inclusive) + 1ull;
  std::uint64_t m = static_cast<std::uint64_t>(next_uint32()) * rng_excl;
  std::uint32_t leftover = static_cast<std::uint32_t>(m & 0xffffffffull);
  if (leftover < rng_excl) {
    const std::uint32_t threshold = static_cast<std::uint32_t>((0xffffffffull - rng_inclusive) % rng_excl);
    while (leftover < threshold) {
      m = static_cast<std::uint64_t>(next_uint32()) * rng_excl;
      leftover = static_cast<std::uint32_t>(m & 0xffffffffull);
    }
  }
  return static_cast<std::uint32_t>(m >> 32);
}

Side coin_side(std::int64_t session_ordinal, std::int64_t side_index) {
  if (session_ordinal < 0 || side_index < 0) {
    // numpy refuses negative entropy outright; so do we, as code and not as an
    // assert, rather than reinterpreting a negative as a huge unsigned word.
    ::qr::detail::fail_fast("qr_replay::coin_side: entropy values must be non-negative");
  }
  const std::array<std::uint64_t, 3> entropy = {kProgramSeed,
                                                static_cast<std::uint64_t>(session_ordinal),
                                                static_cast<std::uint64_t>(side_index)};
  const SeedSequence seq = SeedSequence::from_entropy(entropy);
  Pcg64 generator(seq);
  return generator.bounded_uint32(1) == 0 ? Side::LONG : Side::SHORT;
}

}  // namespace qr::replay
