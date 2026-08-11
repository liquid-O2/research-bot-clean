// qr_nbbo/census.hpp — the seven-way quote state, the session domain, and the
// full-day NBBO census.
//
// SPEC (design/DESIGN_SUBSTRATE.md section 6): "`qr_nbbo` (equal-ms group
// machine + **census**)".
// SPEC (WP5 brief): "FullDayQuoteCensus ... publish census TSV (all QuoteKind/
// flag counts, printed in full)"; "port the full census/flag vocabulary, not a
// subset" (D-017).
// Port reference (read-only, semantics-exact):
//   /workspace/engine/crates/corpus/src/reader.rs
//     StockQuoteDomain      :74-80
//     StockQuoteState       :82-91
//     FullDayQuoteCensus    :154-174
//     stock_quote_domain    :1170-1191   (the domain windows)
//     quote_state           :1193-1212   (THE seven-way classifier)
//     census accumulation   :1612-1635
//
// TWO DELIBERATE DIVERGENCES FROM THE REFERENCE, BOTH ORDERED BY THE PLAN:
//
//  1. `stock_quote_domain` OPENS WITH `clock.to_frame_a_same_civil_day(time_b)?`
//     (reader.rs:1173) — the exact latent abort the substrate design names:
//     "note the same latent `?`-abort shape exists in production
//     reader.rs:1173 — the port must not copy it" (design/DESIGN_SUBSTRATE.md
//     section 6). `classify_domain` here is therefore TOTAL: it runs
//     qr_clock's own total classifier first and returns a typed
//     `DomainClass` for every input, with no error path. A wrong-civil-day or
//     malformed stamp is a census row, never a 12-hour pass that dies.
//  2. `derivative_null_mask_counts[32]` (reader.rs:173) is a census over
//     source columns 9..13 (`d_bid_size`, `d_ask_size`, `bid_px_chg`,
//     `ask_px_chg`, `dt_prev_ms`). FINAL_PLAN APPENDIX B1 puts those columns
//     behind a wall: "cols 9-15 (d_sizes, px_chg, dt_prev, mid, spread) NEVER
//     READ — recomputed (scalar-means-before-derived law)", and WP4's pinned
//     projection stops at slot 8. A census field is not a licence to read a
//     forbidden column, so that one reference field is UNREACHABLE BY LAW here
//     and is recorded as such rather than silently dropped. Everything else in
//     the reference census is ported.
//
// WHAT THE RTH PROJECTION MAKES STRUCTURALLY ZERO. The reference streams the
// whole 04:00-20:00 tape; WP4's `StockQuoteReader` applies the session clock's
// half-open frame-B RTH window before a row is ever retained (B1's law), so a
// census built over that reader can only see RTH rows. The domain histogram is
// still carried in full — the classifier is ported and unit-tested on all four
// domains — and the machine REFUSES if a non-RTH group ever reaches it. Zero
// is asserted, never assumed.
#ifndef QR_NBBO_CENSUS_HPP
#define QR_NBBO_CENSUS_HPP

#include <array>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

#include "qr_clock/session_clock.hpp"
#include "qr_core/validity.hpp"
#include "qr_nbbo/quote_groups.hpp"

namespace qr::nbbo {

// ---------------------------------------------------------------------------
// The seven-way member state (reader.rs:82-91 / :1193-1212).
// ---------------------------------------------------------------------------

/// Exact port of `corpus::reader::StockQuoteState`. This is the CENSUS view of
/// a member, and it is not the typed C1 view: it ignores conditions entirely
/// (the reference's `quote_state` takes only prices and sizes) and it calls a
/// two-sided quote with a nonpositive size INVALID rather than one-sided.
enum class QuoteState : std::uint8_t {
  NORMAL = 0,
  LOCKED = 1,
  CROSSED = 2,
  BID_ONLY = 3,
  ASK_ONLY = 4,
  BOTH_SIDES_ABSENT = 5,
  INVALID = 6,
};

inline constexpr std::size_t kQuoteStateCount = 7;

[[nodiscard]] const char* quote_state_name(QuoteState state) noexcept;

/// One member's raw two-sided fields, as the classifiers read them. A field is
/// `nullopt` when the tape carried a null there — absence is a state, never a
/// sentinel value (the WP4 mask law).
struct MemberFields {
  std::optional<std::int64_t> bid_u6;
  std::optional<std::int64_t> ask_u6;
  std::optional<std::int64_t> bid_shares;
  std::optional<std::int64_t> ask_shares;
  std::optional<std::int64_t> bid_condition;
  std::optional<std::int64_t> ask_condition;
};

/// THE SEVEN-WAY CLASSIFIER (exact port of `quote_state`, reader.rs:1193-1212).
///
/// `malformed` is the reference's `invalid` argument: a field that failed to
/// decode while its column was non-null, or a price outside the sanity
/// ceiling. The reference filters prices and sizes to strictly positive BEFORE
/// this call (reader.rs:1550-1559), so this function does the same filtering
/// itself rather than trusting a caller to have done it.
[[nodiscard]] QuoteState classify_quote_state(const MemberFields& fields,
                                              bool malformed) noexcept;

/// THE TYPED C1 VIEW of the same member (APPENDIX C1 + task card V4 section 4,
/// "a quote is signing/valuation-valid only when bid/ask are finite, bid>0,
/// ask>0, **ask>bid**, and every available bid/ask condition passes its pinned
/// condition contract. Locked, crossed, one-sided/nonpositive, nonfinite, or
/// condition-ineligible quotes remain typed quality but cannot ... supply
/// midpoint/spread/depth/valuation").
///
/// Built by worst-wins `combine` over per-field states, so the lattice — not a
/// hand-written priority chain — decides which token a multiply-defective
/// member carries.
[[nodiscard]] Validity classify_member_validity(const MemberFields& fields) noexcept;

/// THE STRUCTURAL-VALIDITY PREDICATE of the CSR view (exact port of the
/// `structurally_valid` expression in `add_member`, reader.rs:632-639),
/// including the two loose rules the reference freezes: `ask >= bid` (a LOCKED
/// member is structurally valid) and `(bid + ask) % 2 == 0` (a member whose
/// midpoint is not an exact u6 integer is not).
[[nodiscard]] bool is_structurally_valid(const MemberFields& fields) noexcept;

// ---------------------------------------------------------------------------
// The session domain (reader.rs:74-80 / :1170-1191), TOTALIZED.
// ---------------------------------------------------------------------------

/// Exact port of `corpus::reader::StockQuoteDomain`, plus the three states the
/// TOTALIZED classifier needs where the reference had a `?`.
enum class QuoteDomain : std::uint8_t {
  PREMARKET = 0,
  RTH = 1,
  AFTER_HOURS = 2,
  OUTSIDE_DOMAIN = 3,
  /// The stamp is on a different civil day than this clock's.
  WRONG_CIVIL_DAY = 4,
  /// The stamp's own arithmetic refuses (the totalized image of the
  /// reference's ArithmeticOverflow branch).
  MALFORMED = 5,
  /// There was no stamp at all.
  MISSING = 6,
};

inline constexpr std::size_t kQuoteDomainCount = 7;

[[nodiscard]] const char* quote_domain_name(QuoteDomain domain) noexcept;

/// The domain of one frame-B millisecond stamp against the registered stock
/// session windows — 04:00 to the open is PREMARKET, the clock's own half-open
/// RTH window is RTH, the four hours after the post-open boundary are
/// AFTER_HOURS, everything else OUTSIDE_DOMAIN (reader.rs:1174-1189, including
/// its early-close branch: a 210-bar session's after-hours window starts at
/// its own close, a 390-bar session's at open + 6h30m).
///
/// TOTAL: no error path, no abort (design section 6). Non-on-day stamps come
/// back as WRONG_CIVIL_DAY / MALFORMED / MISSING.
[[nodiscard]] QuoteDomain classify_domain(const SessionClock& clock,
                                          std::optional<std::int64_t> ts_ms_b) noexcept;

// ---------------------------------------------------------------------------
// The census.
// ---------------------------------------------------------------------------

/// The full-day NBBO census. Every counter the reference carries that this
/// projection can lawfully see, plus the typed C1 histograms the reference has
/// no vocabulary for.
struct FullDayQuoteCensus {
  // --- what the reader handed over ---------------------------------------
  /// Equal-millisecond groups delivered (the registry's complete_group_count).
  std::int64_t group_count = 0;
  /// Retained RTH member rows (the registry's raw_rth_row_count).
  std::int64_t rth_rows = 0;
  /// All-null sentinel rows the reader skipped and counted.
  std::int64_t sentinel_rows = 0;
  /// Groups holding more than one member (the card's `same-ms` bit).
  std::int64_t multi_member_groups = 0;
  /// The largest member count of any one group.
  std::int64_t max_group_multiplicity = 0;

  // --- domain histogram (ported classifier; RTH-only stream) -------------
  std::array<std::int64_t, kQuoteDomainCount> domain_rows{};

  // --- the seven-way state histogram (exact port) ------------------------
  std::array<std::int64_t, kQuoteStateCount> state_rows{};

  // --- the CSR classification (exact port) -------------------------------
  std::int64_t structurally_valid_rows = 0;
  std::int64_t rejected_rows = 0;
  std::int64_t scientific_rows = 0;
  std::int64_t wide_rows = 0;
  std::int64_t groups_with_locked_member = 0;
  std::array<std::int64_t, kQuoteKindCount> kind_groups{};
  std::array<std::int64_t, kQualityFlagCount> quality_flag_groups{};
  /// Distinct midpoints retained in each CSR arm.
  std::int64_t scientific_midpoints = 0;
  std::int64_t wide_midpoints = 0;

  // --- the typed C1 histograms -------------------------------------------
  std::array<std::int64_t, kValidityCount> member_validity{};
  std::array<std::int64_t, kValidityCount> group_validity{};
  std::int64_t eligible_rows = 0;
  std::int64_t groups_without_eligible_member = 0;
  std::int64_t groups_without_prior_state = 0;

  // --- the price profile of the source row (exact port) ------------------
  /// `cent_int32` rows; the reference calls these "compact".
  std::int64_t compact_rows = 0;
  /// `dollar_float64` rows; the reference calls these "wide".
  std::int64_t wide_profile_rows = 0;

  /// Reference census field `derivative_null_mask_counts[32]`, over source
  /// columns 9..13. UNREACHABLE BY LAW: APPENDIX B1 never reads those columns.
  /// Carried as a named constant so the omission is a recorded fact and not a
  /// silently missing counter.
  static constexpr const char* kUnreachableByProjection = "derivative_null_mask_counts[32]";

  /// The census as a deterministic TSV: one `metric<TAB>value` row per
  /// counter, every kind, flag, state, domain and validity printed IN FULL
  /// including the zeros. Order is fixed by this function, never by a map.
  [[nodiscard]] std::string to_tsv(std::string_view label) const;
};

}  // namespace qr::nbbo

#endif  // QR_NBBO_CENSUS_HPP
