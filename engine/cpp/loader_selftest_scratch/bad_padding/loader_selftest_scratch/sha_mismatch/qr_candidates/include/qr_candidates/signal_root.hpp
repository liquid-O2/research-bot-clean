// qr_candidates/signal_root.hpp — the frozen event-signal sequence-root formula.
//
// SPEC: evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 2 —
//   "Every session must match the exact `signal_count` and
//    `signal_sequence_root` in `t14_bounds`."
//
// THIS FILE IS A REPRODUCTION, NOT A DESIGN. The roots live in a sealed
// publication that was written years before this substrate existed; the only
// admissible implementation is the one that reproduces them bit for bit. The
// formula is ported from the bounded non-prefetch feasibility witness, source
// sha256 12cf894248a371cbc98d7b6d0a65ab0fc1fc359cbe1e36a8b7c927eb8c1f6d3b
// (`StableHasher` / `start_root` / `hash_signal`), whose four framing/kernel
// constants are published in
// side_prefix_feasibility_v1/probe_s125_v3/receipt.json ("root_formula", the
// receipt whose own sha256 the task card pins as
// 62e8d98805a97f42f016ce4b725d832f30fd968912180d50b7696dde69e87ccf).
//
// THE FORMULA, exactly:
//
//   prologue = len_be64("<framing_semantic>") || "<framing_semantic>"
//            || len_be64("<framing_code>")     || "<framing_code>"
//            || len_be64("<domain>")           || "<domain>"
//            || len_be64("<kernel_semantic>")  || "<kernel_semantic>"
//            || len_be64("<kernel_code>")      || "<kernel_code>"
//            || be64(session_signal_count)
//   root     = hex(sha256(prologue || image(row_0) || ... || image(row_{n-1})))
//
// where `image(row)` is the 24-term encoding built by `encode_signal_image`
// below. Note the asymmetry that is load-bearing: TEXT terms are
// length-prefixed, DIGEST terms are the 32 RAW bytes of the parsed hex with no
// length prefix at all, and integers are fixed-width BIG-ENDIAN. None of that
// is negotiable — a single reordered or re-framed term changes every root.
#ifndef QR_CANDIDATES_SIGNAL_ROOT_HPP
#define QR_CANDIDATES_SIGNAL_ROOT_HPP

#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>

#include "qr_core/refusal.hpp"

namespace qr::candidates {

/// Streaming SHA-256 over OpenSSL's EVP interface. Move-only; no copy, so a
/// half-absorbed root can never be silently duplicated.
class Sha256 {
 public:
  Sha256();
  ~Sha256();
  Sha256(const Sha256&) = delete;
  Sha256& operator=(const Sha256&) = delete;
  Sha256(Sha256&& other) noexcept;
  Sha256& operator=(Sha256&& other) noexcept;

  void update(const void* data, std::size_t size) noexcept;
  void update(std::string_view text) noexcept { update(text.data(), text.size()); }

  /// Finalizes and returns the lowercase hex digest. The object is left
  /// finalized; call `reset` to start another digest.
  [[nodiscard]] std::string finish_hex();

  /// Restarts the context, so one object can seal a whole ladder of sessions
  /// without reallocating.
  void reset();

 private:
  void* context_ = nullptr;  // EVP_MD_CTX*, opaque so OpenSSL stays out of the header
};

/// Streaming sha256 of a whole file, in fixed-size blocks. Used to verify the
/// pinned digests of the bound authorities before anything is decoded.
[[nodiscard]] Expected<std::string, Refusal> sha256_file_hex(const std::string& path);

// --- the frozen constants ---------------------------------------------------

inline constexpr std::string_view kFramingSemantic =
    "a65d17669c77c27559f091d69b03b52d4cb303fbb6c961e59c7c99d1216f243a";
inline constexpr std::string_view kFramingCode =
    "991fadb2d273890d5c0f472ba36869e0af62d3872ef2c1aee6a570fd17ddd167";
inline constexpr std::string_view kKernelSemantic =
    "3332cc2e53ae1e2f53d63b8bf8c56b2840169682f27ca7bff055000b90b55cc8";
inline constexpr std::string_view kKernelCode =
    "4aba65b4297d62d45873595ab44db403c9c6cc2cce1e5c497d99f975f78abd79";
inline constexpr std::string_view kSignalDomain =
    "iwm-atlas-v2-causal-intrabar-signal-sequence-v1";

/// The number of tab-separated cells in one `event_signals.tsv` row. A row of
/// any other width is refused; the sealing authority refused it too.
inline constexpr std::size_t kSignalFieldCount = 40;

/// EXACT size of one row's image, by construction:
///   7 digest terms x 32 bytes                                        = 224
/// + continuity u32 4, side u8 1, pivot_price i64 8, state u64 8,
///   group u64 8, conf_ts i64 8, visible i64 8, retouch bool 1,
///   two optional u32 (1 presence byte + 4 when present) 5 + 5,
///   latency i64 8 + i64 8 + u64 8 + u64 8, price i64 8 + i64 8,
///   crossing u32 4                                                   = 108
///                                                                    = 332
/// Sized as a compile-time constant so the hot loop never allocates. Every
/// writer bounds-checks against it, so adding a term without resizing refuses
/// instead of overrunning.
inline constexpr std::size_t kSignalImageCapacity = 332;

/// Zero-based cell indices this formula reads, named so a reordered port is a
/// compile error rather than a silently different root.
enum SignalField : std::size_t {
  kFieldOrdinal = 0,
  kFieldDay = 1,
  kFieldSignalId = 2,
  kFieldPhysicalEventId = 3,
  kFieldPolicyId = 4,
  kFieldPolicyName = 5,
  kFieldReversalBps = 6,
  kFieldCausalRunPrefixRoot = 7,
  kFieldContinuityOrdinal = 8,
  kFieldExtremeSide = 9,
  kFieldPivotPriceU6 = 10,
  kFieldPivotEvidenceRoot = 11,
  kFieldConfirmationStatePosition = 17,
  kFieldConfirmationGroupOrdinal = 18,
  kFieldConfirmationTsNs = 19,
  kFieldCausalVisibleTsNs = 20,
  kFieldPivotRetouchOrderUncertain = 23,
  kFieldOriginToVisibleDelayBarsMin = 24,
  kFieldOriginToVisibleDelayBarsMax = 25,
  kFieldLatencyFromPivotNsMin = 26,
  kFieldLatencyFromPivotNsMax = 27,
  kFieldLatencyFromPivotGroupsMin = 28,
  kFieldLatencyFromPivotGroupsMax = 29,
  kFieldConfirmationPriceLowU6 = 31,
  kFieldConfirmationPriceHighU6 = 32,
  kFieldConfirmationCrossingCount = 33,
  kFieldConfirmationCrossingSetRoot = 34,
  kFieldConfirmationGroupRoot = 35,
};

/// The pinned `event_signals.tsv` header line (40 names, tab separated).
[[nodiscard]] std::string_view signal_header() noexcept;

/// The pinned `t14_bounds.tsv` header line (50 names, tab separated).
[[nodiscard]] std::string_view t14_header() noexcept;

/// Writes one row's hash image into `out` and returns how many bytes it used.
/// Every cell is parsed with the strict parsers of parse.hpp, so a malformed
/// cell refuses here rather than hashing a substituted value.
[[nodiscard]] Expected<std::size_t, Refusal> encode_signal_image(
    const std::string_view fields[kSignalFieldCount], std::uint8_t out[kSignalImageCapacity]);

/// Absorbs the per-session prologue (framing, domain, kernel, declared count).
void absorb_root_prologue(Sha256& hasher, std::uint64_t session_signal_count);

}  // namespace qr::candidates

#endif  // QR_CANDIDATES_SIGNAL_ROOT_HPP
