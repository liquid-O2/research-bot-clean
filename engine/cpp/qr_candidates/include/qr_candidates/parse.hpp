// qr_candidates/parse.hpp — the strict scalar cell parsers of the sealed
// event-signal prefix.
//
// SPEC: evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 2 — every
// session must reproduce the `signal_sequence_root` recorded in `t14_bounds`.
// A root is a hash over PARSED values, so the parsers are part of the frozen
// formula: a cell this file would refuse is a cell the sealing authority
// refused, and a cell it accepts must yield the identical integer.
//
// PORTED VERBATIM from the bounded non-prefetch feasibility witness, source
// sha256 12cf894248a371cbc98d7b6d0a65ab0fc1fc359cbe1e36a8b7c927eb8c1f6d3b
// (`parse_u64` / `parse_u32` / `parse_i64` / `parse_bool` / `parse_opt_u32`).
// The witness's quirks are laws here, not bugs to fix:
//
//   * `parse_u64` refuses an empty cell, any cell with a redundant leading
//     zero, and any non-digit byte — so "+7", " 7", "07" and "" all refuse.
//   * `parse_i64` refuses an empty cell, the string "-0", and a redundant
//     leading zero on a POSITIVE number. It deliberately does NOT reject a
//     redundant leading zero after the sign ("-07"), because the sealing run
//     did not: changing that would change which rows the authority admitted.
//   * `parse_opt_u32` maps exactly the cell "NA" to absent.
//
// Everything refuses by value (`Expected`), never by exception, so a malformed
// byte anywhere in a 10.68M-row prefix names its own cell.
#ifndef QR_CANDIDATES_PARSE_HPP
#define QR_CANDIDATES_PARSE_HPP

#include <cstdint>
#include <optional>
#include <string_view>

#include "qr_core/refusal.hpp"

namespace qr::candidates {

/// The literal that spells "this optional cell is absent".
inline constexpr std::string_view kAbsentCell = "NA";

/// Unsigned decimal, no sign, no redundant leading zero, no whitespace.
[[nodiscard]] inline Expected<std::uint64_t, Refusal> parse_u64(std::string_view cell,
                                                                const char* site) noexcept {
  if (cell.empty() || (cell.size() > 1 && cell.front() == '0')) {
    return refuse<std::uint64_t>(
        Refusal(RefusalCode::DECODE_FAILED, site, "empty or redundant-leading-zero unsigned cell",
                static_cast<std::int64_t>(cell.size())));
  }
  std::uint64_t value = 0;
  for (const char raw : cell) {
    const auto byte = static_cast<unsigned char>(raw);
    if (byte < '0' || byte > '9') {
      return refuse<std::uint64_t>(
          Refusal(RefusalCode::DECODE_FAILED, site, "non-digit byte in an unsigned cell", byte));
    }
    // 10*value + digit, refusing rather than wrapping (FINAL_PLAN section 6).
    if (value > (UINT64_MAX - static_cast<std::uint64_t>(byte - '0')) / 10U) {
      return refuse<std::uint64_t>(
          Refusal(RefusalCode::ARITHMETIC_OVERFLOW, site, "unsigned cell exceeds 64 bits"));
    }
    value = value * 10U + static_cast<std::uint64_t>(byte - '0');
  }
  return value;
}

/// `parse_u64` narrowed to 32 bits; an out-of-range value refuses.
[[nodiscard]] inline Expected<std::uint32_t, Refusal> parse_u32(std::string_view cell,
                                                                const char* site) noexcept {
  const auto wide = parse_u64(cell, site);
  if (!wide) {
    return refuse<std::uint32_t>(wide.error());
  }
  if (wide.value() > UINT32_MAX) {
    return refuse<std::uint32_t>(
        Refusal(RefusalCode::ARITHMETIC_OVERFLOW, site, "unsigned cell exceeds 32 bits",
                static_cast<std::int64_t>(wide.value())));
  }
  return static_cast<std::uint32_t>(wide.value());
}

/// Signed decimal. See the header comment for the two inherited quirks.
[[nodiscard]] inline Expected<std::int64_t, Refusal> parse_i64(std::string_view cell,
                                                               const char* site) noexcept {
  if (cell.empty() || cell == "-0" || (cell.front() == '0' && cell.size() > 1)) {
    return refuse<std::int64_t>(Refusal(RefusalCode::DECODE_FAILED, site,
                                        "empty, negative-zero, or redundant-leading-zero cell",
                                        static_cast<std::int64_t>(cell.size())));
  }
  const bool negative = cell.front() == '-';
  const std::string_view digits = negative ? cell.substr(1) : cell;
  if (digits.empty()) {
    return refuse<std::int64_t>(
        Refusal(RefusalCode::DECODE_FAILED, site, "sign with no digits"));
  }
  std::uint64_t magnitude = 0;
  for (const char raw : digits) {
    const auto byte = static_cast<unsigned char>(raw);
    if (byte < '0' || byte > '9') {
      return refuse<std::int64_t>(
          Refusal(RefusalCode::DECODE_FAILED, site, "non-digit byte in a signed cell", byte));
    }
    if (magnitude > (UINT64_MAX - static_cast<std::uint64_t>(byte - '0')) / 10U) {
      return refuse<std::int64_t>(
          Refusal(RefusalCode::ARITHMETIC_OVERFLOW, site, "signed cell exceeds 64 bits"));
    }
    magnitude = magnitude * 10U + static_cast<std::uint64_t>(byte - '0');
  }
  const std::uint64_t limit =
      negative ? static_cast<std::uint64_t>(INT64_MAX) + 1U : static_cast<std::uint64_t>(INT64_MAX);
  if (magnitude > limit) {
    return refuse<std::int64_t>(
        Refusal(RefusalCode::ARITHMETIC_OVERFLOW, site, "signed cell outside the int64 domain"));
  }
  if (negative) {
    // -magnitude without ever forming +2^63.
    return static_cast<std::int64_t>(~magnitude + 1U);
  }
  return static_cast<std::int64_t>(magnitude);
}

/// Exactly "true" or "false"; anything else refuses.
[[nodiscard]] inline Expected<bool, Refusal> parse_bool(std::string_view cell,
                                                        const char* site) noexcept {
  if (cell == "true") {
    return true;
  }
  if (cell == "false") {
    return false;
  }
  return refuse<bool>(Refusal(RefusalCode::DECODE_FAILED, site, "cell is neither true nor false",
                              static_cast<std::int64_t>(cell.size())));
}

/// "NA" is absent; anything else must be a strict u32.
[[nodiscard]] inline Expected<std::optional<std::uint32_t>, Refusal> parse_opt_u32(
    std::string_view cell, const char* site) noexcept {
  if (cell == kAbsentCell) {
    return std::optional<std::uint32_t>{};
  }
  const auto value = parse_u32(cell, site);
  if (!value) {
    return refuse<std::optional<std::uint32_t>>(value.error());
  }
  return std::optional<std::uint32_t>{value.value()};
}

/// True only for a canonical lowercase 64-hex digest (the shape every
/// `signal_id` / `physical_event_id` / evidence root in the sealed publication
/// carries). Uppercase is REFUSED, not folded: the sealing run's own
/// `digest_hex` refused it, so folding here would admit rows it never saw.
[[nodiscard]] inline bool is_canonical_digest_hex(std::string_view cell) noexcept {
  if (cell.size() != 64) {
    return false;
  }
  for (const char raw : cell) {
    const auto byte = static_cast<unsigned char>(raw);
    const bool digit = byte >= '0' && byte <= '9';
    const bool lower = byte >= 'a' && byte <= 'f';
    if (!digit && !lower) {
      return false;
    }
  }
  return true;
}

}  // namespace qr::candidates

#endif  // QR_CANDIDATES_PARSE_HPP
