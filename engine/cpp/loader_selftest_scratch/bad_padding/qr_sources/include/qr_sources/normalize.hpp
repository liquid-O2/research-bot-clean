// qr_sources/normalize.hpp — the value normalizations every stream shares.
//
// SPEC (WP4 brief, reference semantics of
// /workspace/engine/crates/select_v2/src/sources/mod.rs:269-399):
//   "u6 normalization: cent -> x10,000, dollar -> round(x1e6); mid NEVER read"
// SPEC (WP4 brief + /workspace/engine/crates/corpus/src/reader.rs:1337-1351):
//   "lot->share era law: NBBO sizes x100 before 2025-11-03".
//
// U6 IS THE ONE PRICE SCALE. Dollars x 1,000,000, as an i64, for every price in
// every stream, so the two on-disk encodings compare directly and nothing
// downstream has to know which profile a session was written in.
//
// THE ERA BREAK IS NORMALIZED AT THE READER BOUNDARY, NOT IN EACH FAMILY
// (reader.rs:1332-1336): "every consumer must see one unit across the whole
// development set, or a 100x scale step in the final 41 sessions becomes a
// year-inversion against a certification floor".
//
// SCOPE NOTE (WP4 brief): the era break at 2025-11-03 is BEYOND the s749 scope
// wall, so it is implemented here and exercised ONLY by synthetic two-era
// fixtures. No 2025-11-03+ payload is opened by anything in this module — that
// is FINAL_PLAN B7's wall, and DayScope refuses those ordinals before a path
// can even be formed.
//
// DELIBERATE DEVIATION FROM THE REFERENCE: the Rust `nbbo_size_to_shares` uses
// `saturating_mul(100)`. Saturation is a range-limiting guard, which FINAL_PLAN
// section 6 bans ("clamp/saturate banned in guards"); the C++ law is a checked
// multiply that REFUSES on overflow. No real size is anywhere near the bound,
// so the two agree on every value the corpus contains.
#ifndef QR_SOURCES_NORMALIZE_HPP
#define QR_SOURCES_NORMALIZE_HPP

#include <array>
#include <cstddef>
#include <cstdint>
#include <string_view>

#include "qr_core/checked.hpp"
#include "qr_core/frames.hpp"
#include "qr_core/refusal.hpp"
#include "qr_sources/stream_spec.hpp"

namespace qr::sources {

/// Fixed-point scale of a u6 price: dollars x 1,000,000.
inline constexpr std::int64_t kU6PerDollar = 1'000'000;
/// u6 units in one cent.
inline constexpr std::int64_t kU6PerCent = 10'000;
/// u6 units in one mill (the strike convention).
inline constexpr std::int64_t kU6PerMill = 1'000;

/// First civil day on which the stock-quote feed reports NBBO sizes in SHARES
/// (finding F-34, `corpus::reader::SHARE_ERA_FIRST_DAY`). ISO days compare
/// lexicographically, so string comparison is chronological.
inline constexpr std::string_view kShareEraFirstDay = "2025-11-03";
/// The round lot the pre-2025-11-03 feed counts in.
inline constexpr std::int64_t kSharesPerLot = 100;

/// Normalizes a raw NBBO size to SHARES for the session's era.
///
/// Ported from `corpus::nbbo_size_to_shares` (reader.rs:1343-1351) with the two
/// behaviours the reference readers add at their own boundary
/// (`stock_quotes.rs:262-272`): a negative size is passed through untouched
/// (it is not a count and multiplying it would invent one), and the lot-era
/// multiply is CHECKED rather than saturating.
[[nodiscard]] Expected<std::int64_t, Refusal> nbbo_size_to_shares(std::int64_t raw,
                                                                  std::string_view day) noexcept;

/// Round-half-to-even, computed FROM THE VALUE rather than from the floating
/// point environment's current rounding mode, so the result cannot depend on
/// what some other translation unit did to the FPU. This is the rounding law
/// of the u6 normalization, exposed so it can be tested on exact inputs.
[[nodiscard]] double round_ties_even(double value) noexcept;

/// Scales dollars to u6, refusing anything that cannot be represented.
///
/// Ported from `select_v2::sources::dollars_to_u6` (mod.rs:387-399):
/// non-finite, or a scaled magnitude outside the i64 range, is a refusal — not
/// a substituted boundary value. Ties round to even.
[[nodiscard]] Expected<std::int64_t, Refusal> dollars_to_u6(double value) noexcept;

/// Normalizes one decoded price/strike cell to u6 by its resolved on-disk form.
/// `CentI32`/`CentI64` x 10,000; `MillI32` x 1,000; `DollarF64` as above. Any
/// other form is a programmer error, not a data error, and refuses.
[[nodiscard]] Expected<std::int64_t, Refusal> price_to_u6(ColumnForm form, std::int64_t integer,
                                                          double real) noexcept;

/// Contract right. Anything the vendor writes that is neither call nor put is
/// kept as `Other` rather than folded into one of them (reference
/// `options_prints.rs:111-126`).
enum class Right : std::uint8_t { Call = 0, Put = 1, Other = 2 };

[[nodiscard]] const char* right_name(Right right) noexcept;

/// Parses a vendor right token exactly as the frozen reference does.
[[nodiscard]] Right parse_right(std::string_view text) noexcept;

/// UTF-8 text retained VERBATIM from the tape, inline so a row stays trivially
/// copyable and can outlive the column buffer it was decoded from.
///
/// WHY IT EXISTS: `underlying_timestamp(36)` is UTF-8 text in the measured IWM
/// compact print profile (`2022-07-05T09:30:00.000`, 23 bytes). B3 projects it;
/// nothing in the cited spec says how to interpret it, so WP4 RETAINS IT RAW
/// and interprets nothing. A value longer than the inline capacity is a typed
/// refusal, never a truncation.
inline constexpr std::size_t kInlineTextCapacity = 31;

struct InlineText {
  std::uint8_t size = 0;
  std::array<char, kInlineTextCapacity> data{};

  [[nodiscard]] std::string_view view() const noexcept {
    return std::string_view(data.data(), size);
  }
  friend bool operator==(const InlineText& lhs, const InlineText& rhs) noexcept {
    return lhs.view() == rhs.view();
  }
};

/// Copies `text` into an `InlineText`, or refuses when it does not fit.
[[nodiscard]] Expected<InlineText, Refusal> inline_text(std::string_view text) noexcept;

/// Days since the Unix epoch for a decoded date cell.
/// `DateI32` is already the ordinal; `DateText` is parsed as an ISO civil day
/// through `qr::CivilDate` (reference `mod.rs:359-378`), and a non-ISO value is
/// MALFORMED_CIVIL_DATE rather than a guessed date.
[[nodiscard]] Expected<std::int32_t, Refusal> date_to_day_ordinal(ColumnForm form,
                                                                  std::int64_t ordinal,
                                                                  std::string_view text) noexcept;

/// The true midpoint of a two-sided u6 quote — COMPUTED, never read from the
/// vendor `mid` column (which is `bid + ask` in the compact profile and the
/// real midpoint in the wide one). Overflow-free by construction.
[[nodiscard]] constexpr std::int64_t midpoint_u6(std::int64_t bid_u6,
                                                 std::int64_t ask_u6) noexcept {
  return bid_u6 + ((ask_u6 - bid_u6) / 2);
}

}  // namespace qr::sources

#endif  // QR_SOURCES_NORMALIZE_HPP
