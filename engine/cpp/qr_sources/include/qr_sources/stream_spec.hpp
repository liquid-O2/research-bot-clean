// qr_sources/stream_spec.hpp — THE PINNED STREAM SPECS AND THEIR WALLS.
//
// SPEC (design/DESIGN_SUBSTRATE.md, M1, qr_sources bullet, verbatim):
//   "`qr_sources` (six pinned readers per App. B: projections, dual profile per
//    registry row, price_lead_1 decode-refusal, forbidden-column walls)"
// SPEC (design/DESIGN_SUBSTRATE.md APPENDIX C3, verbatim):
//   "`struct StreamSpec {names; projection; forbidden;}` compile-time asserts;
//    `open(DayScope, Profile)` refuses wrong schema pre-payload; `next_group()`
//    equal-time iterator, rows unordered within group."
// SPEC (FINAL_PLAN.md APPENDIX B, B1-B4): the exact per-column projections,
//    uses and refusals reproduced verbatim above each spec below.
// Reference semantics (read-only): /workspace/engine/crates/select_v2/src/sources/*.rs
//
// WP4 SCOPE: the four IWM streams. B5 (RUTW prints, "same 62-name wide
// profile") is DEFERRED — and deferral here is a WALL, not an omission: a wide
// RUTW file handed to the IWM compact print reader is refused BY NAME at open,
// with a fixture proving it.
//
// THREE WALLS LIVE IN THIS FILE, in increasing order of when they fire:
//
//   1. COMPILE TIME — `spec_is_wellformed` is a constexpr predicate every spec
//      passes through a static_assert. A projection that contains a forbidden
//      index, is unsorted, repeats a leaf, or runs past the name list does not
//      COMPILE. ci/check_compile_fail.sh proves each of those really fails.
//   2. OPEN TIME, BEFORE ANY PAYLOAD BYTE — `gate_schema` walks the file's own
//      schema: the column count, every column NAME in order (including the
//      names of columns this reader never decodes: drift in an unread column
//      is still drift), and the physical form of every projected column
//      against its admitted set. It runs on the footer alone.
//   3. DECODE TIME — `read_pinned_column` is the ONLY door to a leaf's bytes,
//      and it refuses any leaf outside the projection. A forbidden leaf is
//      COLUMN_FORBIDDEN naming the column; `price_lead_1` is the name-pinned
//      case B2 calls out ("DECODE-REFUSED (future-looking; name-pinned only)").
//      The readers themselves go through this door, so the wall cannot be
//      dodged by asking the reader instead of asking the file.
#ifndef QR_SOURCES_STREAM_SPEC_HPP
#define QR_SOURCES_STREAM_SPEC_HPP

#include <array>
#include <cstddef>
#include <cstdint>
#include <span>
#include <string_view>
#include <vector>

#include "qr_parquet/reader.hpp"
#include "qr_registry/registry.hpp"

namespace qr::sources {

using qr::parquet::ColumnData;
using qr::parquet::DecodeWorkspace;
using qr::parquet::FileExpected;
using qr::parquet::LeafConverted;
using qr::parquet::LeafType;

// ---------------------------------------------------------------------------
// What a projected column IS, and what it is allowed to be on disk.
// ---------------------------------------------------------------------------

/// The USE a projected column is retained for (APPENDIX B's "uses" column).
/// The role decides which on-disk forms are admitted and how the value
/// normalizes; it never decides whether the column is read (the projection
/// does that).
enum class ColumnRole : std::uint8_t {
  /// Naive-ET (frame B) milliseconds. NEVER converted here: qr_clock is the
  /// one frame boundary, and this module hands frame-B milliseconds on.
  TimestampMs,
  /// A whole number: size, venue, condition, sequence.
  Int,
  /// A price in the corpus's minor units, normalized to u6 (dollars x 1e6).
  Price,
  /// An option strike: integer mills in the compact profile, dollars in the
  /// wide one. Normalized to u6 like a price, by a different scale.
  Strike,
  /// A calendar date: day ordinal (INT32/DATE) or ISO text.
  Date,
  /// UTF-8 text retained verbatim, interpreted by nobody in WP4.
  Text,
  /// A dimensionless real (greeks, implied vol, underlying price).
  Float,
};

/// The resolved ON-DISK form of one projected column, decided at open from the
/// file's own schema. This is what "detect the profile from the file's own
/// schema and refuse anything outside the admitted set" means mechanically.
enum class ColumnForm : std::uint8_t {
  /// INT64 naive-ET milliseconds.
  TimestampMsI64,
  IntI32,
  IntI64,
  /// INT32 integer cents; u6 = value x 10,000.
  CentI32,
  /// INT64 integer cents; u6 = value x 10,000.
  CentI64,
  /// INT32 integer mills (the strike convention); u6 = value x 1,000.
  MillI32,
  /// DOUBLE dollars; u6 = round_ties_even(value x 1,000,000).
  DollarF64,
  /// INT32 days since the Unix epoch (converted type DATE).
  DateI32,
  /// UTF-8 ISO `YYYY-MM-DD`.
  DateText,
  TextUtf8,
  FloatF64,
};

[[nodiscard]] const char* column_role_name(ColumnRole role) noexcept;
[[nodiscard]] const char* column_form_name(ColumnForm form) noexcept;

/// Whether `form` is one of the forms `role` admits. The admitted sets are the
/// frozen Rust reference's (`select_v2::sources::{price_col, strike_col,
/// int_col, date_col, text_col, float_col, timestamp_col}`), which exists
/// precisely because sampling 1,383 files is not proof over all of them.
[[nodiscard]] constexpr bool role_admits(ColumnRole role, ColumnForm form) noexcept {
  switch (role) {
    case ColumnRole::TimestampMs:
      return form == ColumnForm::TimestampMsI64;
    case ColumnRole::Int:
      return form == ColumnForm::IntI32 || form == ColumnForm::IntI64;
    case ColumnRole::Price:
      return form == ColumnForm::CentI32 || form == ColumnForm::CentI64 ||
             form == ColumnForm::DollarF64;
    case ColumnRole::Strike:
      return form == ColumnForm::MillI32 || form == ColumnForm::DollarF64;
    case ColumnRole::Date:
      return form == ColumnForm::DateI32 || form == ColumnForm::DateText;
    case ColumnRole::Text:
      return form == ColumnForm::TextUtf8;
    case ColumnRole::Float:
      return form == ColumnForm::FloatF64;
  }
  return false;
}

// ---------------------------------------------------------------------------
// The forbidden set.
// ---------------------------------------------------------------------------

/// WHY a column is walled off. The three reasons are APPENDIX B's own three
/// phrasings, and they are kept apart because they mean different things to a
/// reviewer: a NEVER READ column may be recomputed from what IS read, a
/// DECODE-REFUSED column may never be recomputed at all (it is future data),
/// and a HARD-REFUSED column is a vendor answer to a question this program
/// insists on answering itself.
enum class ForbidReason : std::uint8_t {
  /// "NEVER READ — recomputed (scalar-means-before-derived law)" (B1).
  NeverRead,
  /// "DECODE-REFUSED (future-looking; name-pinned only)" (B2, `price_lead_1`).
  DecodeRefused,
  /// "HARD-REFUSED: side(38), sweep_*(47-50), prem/*_flow(53-61), unlisted
  /// Greeks" (B3). Aggressor and flows are recomputed by this program.
  HardRefused,
};

[[nodiscard]] const char* forbid_reason_name(ForbidReason reason) noexcept;

struct ForbiddenColumn {
  std::size_t leaf = 0;
  ForbidReason reason = ForbidReason::NeverRead;
};

// ---------------------------------------------------------------------------
// APPENDIX C3's StreamSpec.
// ---------------------------------------------------------------------------

/// `struct StreamSpec {names; projection; forbidden;}` (APPENDIX C3), plus the
/// two things a projection is useless without: the ROLE of each projected
/// column and which leaf carries the stream's clock.
template <std::size_t NNames, std::size_t NProj, std::size_t NForb>
struct StreamSpec {
  /// The stream's own name, for refusal text ("stock_quotes", ...).
  std::string_view stream;
  /// EVERY column of the corpus, in file order. Columns this reader never
  /// decodes are pinned here too: an unread column that changes name is still
  /// a schema drift, and drift detection is the whole point of a pin.
  std::array<std::string_view, NNames> names;
  /// The projected leaf indices, strictly ascending.
  std::array<std::size_t, NProj> projection;
  /// The role of `projection[i]`.
  std::array<ColumnRole, NProj> roles;
  /// The walled-off leaves, strictly ascending by leaf index.
  std::array<ForbiddenColumn, NForb> forbidden;
  /// The leaf whose timestamp defines RTH membership and the equal-time
  /// groups. Must itself be projected with role TimestampMs.
  std::size_t timestamp_leaf;
};

// --- the compile-time asserts ----------------------------------------------

template <std::size_t NNames, std::size_t NProj, std::size_t NForb>
[[nodiscard]] constexpr bool projection_is_ascending_and_in_range(
    const StreamSpec<NNames, NProj, NForb>& spec) noexcept {
  for (std::size_t index = 0; index < NProj; ++index) {
    if (spec.projection[index] >= NNames) {
      return false;
    }
    if (index > 0 && spec.projection[index] <= spec.projection[index - 1]) {
      return false;
    }
  }
  return true;
}

template <std::size_t NNames, std::size_t NProj, std::size_t NForb>
[[nodiscard]] constexpr bool forbidden_is_ascending_and_in_range(
    const StreamSpec<NNames, NProj, NForb>& spec) noexcept {
  for (std::size_t index = 0; index < NForb; ++index) {
    if (spec.forbidden[index].leaf >= NNames) {
      return false;
    }
    if (index > 0 && spec.forbidden[index].leaf <= spec.forbidden[index - 1].leaf) {
      return false;
    }
  }
  return true;
}

/// THE CENTRAL COMPILE-TIME LAW: a projected column may not also be forbidden.
/// "projection containing a forbidden index -> compile-time or open-time
/// refusal" (WP4 brief, fixtures).
template <std::size_t NNames, std::size_t NProj, std::size_t NForb>
[[nodiscard]] constexpr bool projection_and_forbidden_are_disjoint(
    const StreamSpec<NNames, NProj, NForb>& spec) noexcept {
  for (const ForbiddenColumn& walled : spec.forbidden) {
    for (const std::size_t projected : spec.projection) {
      if (projected == walled.leaf) {
        return false;
      }
    }
  }
  return true;
}

template <std::size_t NNames, std::size_t NProj, std::size_t NForb>
[[nodiscard]] constexpr bool names_are_unique_and_nonempty(
    const StreamSpec<NNames, NProj, NForb>& spec) noexcept {
  for (std::size_t index = 0; index < NNames; ++index) {
    if (spec.names[index].empty()) {
      return false;
    }
    for (std::size_t other = index + 1; other < NNames; ++other) {
      if (spec.names[index] == spec.names[other]) {
        return false;
      }
    }
  }
  return true;
}

template <std::size_t NNames, std::size_t NProj, std::size_t NForb>
[[nodiscard]] constexpr bool clock_leaf_is_projected(
    const StreamSpec<NNames, NProj, NForb>& spec) noexcept {
  for (std::size_t index = 0; index < NProj; ++index) {
    if (spec.projection[index] == spec.timestamp_leaf) {
      return spec.roles[index] == ColumnRole::TimestampMs;
    }
  }
  return false;
}

/// Every law above, in one predicate, so every spec can assert it in one line.
template <std::size_t NNames, std::size_t NProj, std::size_t NForb>
[[nodiscard]] constexpr bool spec_is_wellformed(
    const StreamSpec<NNames, NProj, NForb>& spec) noexcept {
  return !spec.stream.empty() && NProj > 0 && NProj <= NNames && NForb <= NNames &&
         projection_is_ascending_and_in_range(spec) && forbidden_is_ascending_and_in_range(spec) &&
         projection_and_forbidden_are_disjoint(spec) && names_are_unique_and_nonempty(spec) &&
         clock_leaf_is_projected(spec);
}

// ---------------------------------------------------------------------------
// The type-erased view every runtime wall takes.
// ---------------------------------------------------------------------------

/// A spec erased to spans. The gate and the decode door are ONE implementation
/// each rather than one per stream: a wall with four copies is four walls to
/// get wrong.
class SpecView {
 public:
  constexpr SpecView(std::string_view stream, std::span<const std::string_view> names,
                     std::span<const std::size_t> projection, std::span<const ColumnRole> roles,
                     std::span<const ForbiddenColumn> forbidden,
                     std::size_t timestamp_leaf) noexcept
      : stream_(stream),
        names_(names),
        projection_(projection),
        roles_(roles),
        forbidden_(forbidden),
        timestamp_leaf_(timestamp_leaf) {}

  [[nodiscard]] constexpr std::string_view stream() const noexcept { return stream_; }
  [[nodiscard]] constexpr std::span<const std::string_view> names() const noexcept {
    return names_;
  }
  [[nodiscard]] constexpr std::span<const std::size_t> projection() const noexcept {
    return projection_;
  }
  [[nodiscard]] constexpr std::span<const ColumnRole> roles() const noexcept { return roles_; }
  [[nodiscard]] constexpr std::span<const ForbiddenColumn> forbidden() const noexcept {
    return forbidden_;
  }
  [[nodiscard]] constexpr std::size_t timestamp_leaf() const noexcept { return timestamp_leaf_; }

  /// Slot of `leaf` inside the projection, or `projection().size()` when the
  /// leaf is not projected.
  [[nodiscard]] std::size_t slot_of(std::size_t leaf) const noexcept;
  [[nodiscard]] bool projects(std::size_t leaf) const noexcept;
  /// The wall reason for `leaf`, or nullptr when the leaf is not walled.
  [[nodiscard]] const ForbiddenColumn* forbids(std::size_t leaf) const noexcept;
  /// Leaf index of a pinned column name, or `names().size()` when unknown.
  [[nodiscard]] std::size_t leaf_of_name(std::string_view name) const noexcept;

 private:
  std::string_view stream_;
  std::span<const std::string_view> names_;
  std::span<const std::size_t> projection_;
  std::span<const ColumnRole> roles_;
  std::span<const ForbiddenColumn> forbidden_;
  std::size_t timestamp_leaf_;
};

template <std::size_t NNames, std::size_t NProj, std::size_t NForb>
[[nodiscard]] constexpr SpecView view_of(const StreamSpec<NNames, NProj, NForb>& spec) noexcept {
  return SpecView(spec.stream, std::span<const std::string_view>(spec.names),
                  std::span<const std::size_t>(spec.projection),
                  std::span<const ColumnRole>(spec.roles),
                  std::span<const ForbiddenColumn>(spec.forbidden), spec.timestamp_leaf);
}

// ---------------------------------------------------------------------------
// B1 — stock quotes (16 cols).
// ---------------------------------------------------------------------------
//
// FINAL_PLAN APPENDIX B1, verbatim: "ts(0)=clock; bid_size/ask_size(1/5)=depth/
// imbalance/queue-decomp; bid_exchange/ask_exchange(2/6)=venue features
// (projection EXTENDED vs old [0,1,3,4,5,7,8]); bid/ask(3/7)=all price channels
// (finite,>0,ask>bid); conditions(4/8)=eligibility code 0; cols 9-15 (d_sizes,
// px_chg, dt_prev, mid, spread) NEVER READ — recomputed (scalar-means-before-
// derived law)."
inline constexpr StreamSpec<16, 9, 7> kStockQuoteSpec{
    .stream = "stock_quotes",
    .names = {"timestamp", "bid_size", "bid_exchange", "bid", "bid_condition", "ask_size",
              "ask_exchange", "ask", "ask_condition", "d_bid_size", "d_ask_size", "bid_px_chg",
              "ask_px_chg", "dt_prev_ms", "mid", "spread_bps"},
    .projection = {0, 1, 2, 3, 4, 5, 6, 7, 8},
    .roles = {ColumnRole::TimestampMs, ColumnRole::Int, ColumnRole::Int, ColumnRole::Price,
              ColumnRole::Int, ColumnRole::Int, ColumnRole::Int, ColumnRole::Price,
              ColumnRole::Int},
    .forbidden = {ForbiddenColumn{9, ForbidReason::NeverRead},
                  ForbiddenColumn{10, ForbidReason::NeverRead},
                  ForbiddenColumn{11, ForbidReason::NeverRead},
                  ForbiddenColumn{12, ForbidReason::NeverRead},
                  ForbiddenColumn{13, ForbidReason::NeverRead},
                  ForbiddenColumn{14, ForbidReason::NeverRead},
                  ForbiddenColumn{15, ForbidReason::NeverRead}},
    .timestamp_leaf = 0,
};
static_assert(spec_is_wellformed(kStockQuoteSpec));

/// THE DUAL PROFILE LAW (B1 + reference `stock_quotes.rs:274-296`): the
/// session's REGISTRY ROW decides the price encoding — never chronology, never
/// detection. (The profile is not chronologically monotone: 2025-12-30 is
/// `cent_int32` and 2025-12-31 is `dollar_float64`.) These are the two admitted
/// form vectors, in projection order; the file must match the declared one
/// exactly or open refuses.
inline constexpr std::array<ColumnForm, 9> kStockQuoteFormsCentInt32{
    ColumnForm::TimestampMsI64, ColumnForm::IntI32,   ColumnForm::IntI64,
    ColumnForm::CentI32,        ColumnForm::IntI64,   ColumnForm::IntI32,
    ColumnForm::IntI64,         ColumnForm::CentI32,  ColumnForm::IntI64};
inline constexpr std::array<ColumnForm, 9> kStockQuoteFormsDollarFloat64{
    ColumnForm::TimestampMsI64, ColumnForm::IntI64,     ColumnForm::IntI64,
    ColumnForm::DollarF64,      ColumnForm::IntI64,     ColumnForm::IntI64,
    ColumnForm::IntI64,         ColumnForm::DollarF64,  ColumnForm::IntI64};

/// The admitted form vector for a registry-declared profile.
[[nodiscard]] std::span<const ColumnForm> stock_quote_forms(SourceProfile profile) noexcept;

// ---------------------------------------------------------------------------
// B2 — stock trades (24 cols; V4 projects 19).
// ---------------------------------------------------------------------------
//
// FINAL_PLAN APPENDIX B2, verbatim: "trade_ts(0); quote_ts(1)=attachment clock
// (strict-prior; WCD typed); sequence(2)=quality only, never ordering;
// ext_cond1-4(3-6)=sentinel-255 conjunction; condition(7)=0 admit/40-44 CANCEL;
// size(8); exchange(9); price(10); attached bid/ask blocks (11,13,14/15,17,18)
// = quote-certified aggressor + own/opposite; attached exchanges (12,16) =
// internalization proxy; 19-21,23 NEVER READ; **price_lead_1(22)
// DECODE-REFUSED** (future-looking; name-pinned only)."
inline constexpr StreamSpec<24, 19, 5> kStockTradeSpec{
    .stream = "stock_trades",
    .names = {"trade_timestamp", "quote_timestamp", "sequence", "ext_condition1", "ext_condition2",
              "ext_condition3", "ext_condition4", "condition", "size", "exchange", "price",
              "bid_size", "bid_exchange", "bid", "bid_condition", "ask_size", "ask_exchange", "ask",
              "ask_condition", "dt_prev_ms", "mid", "price_lag_1", "price_lead_1", "spread_bps"},
    .projection = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18},
    .roles = {ColumnRole::TimestampMs, ColumnRole::TimestampMs, ColumnRole::Int, ColumnRole::Int,
              ColumnRole::Int, ColumnRole::Int, ColumnRole::Int, ColumnRole::Int, ColumnRole::Int,
              ColumnRole::Int, ColumnRole::Price, ColumnRole::Int, ColumnRole::Int,
              ColumnRole::Price, ColumnRole::Int, ColumnRole::Int, ColumnRole::Int,
              ColumnRole::Price, ColumnRole::Int},
    .forbidden = {ForbiddenColumn{19, ForbidReason::NeverRead},
                  ForbiddenColumn{20, ForbidReason::NeverRead},
                  ForbiddenColumn{21, ForbidReason::NeverRead},
                  // THE NAME-PINNED FUTURE FIELD. It stays in `names` so drift
                  // is still detected, and it is walled so decoding it is a
                  // typed refusal rather than a silent leak of the answer.
                  ForbiddenColumn{22, ForbidReason::DecodeRefused},
                  ForbiddenColumn{23, ForbidReason::NeverRead}},
    .timestamp_leaf = 0,
};
static_assert(spec_is_wellformed(kStockTradeSpec));

/// The single measured stock-trade profile (18 sampled days spanning 2020-2025,
/// reference `stock_trades.rs:9-12`): prices are `Float64` dollars, everything
/// else is `Int64`. Detection still runs: the file must MATCH this vector.
inline constexpr std::array<ColumnForm, 19> kStockTradeForms{
    ColumnForm::TimestampMsI64, ColumnForm::TimestampMsI64, ColumnForm::IntI64,
    ColumnForm::IntI64,         ColumnForm::IntI64,         ColumnForm::IntI64,
    ColumnForm::IntI64,         ColumnForm::IntI64,         ColumnForm::IntI64,
    ColumnForm::IntI64,         ColumnForm::DollarF64,      ColumnForm::IntI64,
    ColumnForm::IntI64,         ColumnForm::DollarF64,      ColumnForm::IntI64,
    ColumnForm::IntI64,         ColumnForm::IntI64,         ColumnForm::DollarF64,
    ColumnForm::IntI64};

/// The leaf `price_lead_1` sits at, as a NAME-PINNED constant: B2 pins the
/// refusal to the name, so the wall survives a reordered corpus.
inline constexpr std::string_view kPriceLead1Name = "price_lead_1";

// ---------------------------------------------------------------------------
// B3 — option prints (62 cols; the ADDENDUM 20 projected).
// ---------------------------------------------------------------------------
//
// FINAL_PLAN APPENDIX B3, verbatim: "expiration(1), strike(2), right(3), ts(4),
// sequence(5), condition(10) [single-leg in {18,95,125,126}], size(11),
// price(13), delta(14), gamma(20), vanna(21), charm(22), IV(34),
// underlying_ts(36), underlying_px(37), bid(39), bid_size(40), ask(42),
// ask_size(43), quote_ts(45). +vega(16) via W2.4 registered extension.
// HARD-REFUSED: side(38), sweep_*(47-50), prem/*_flow(53-61), unlisted Greeks.
// Aggressor recomputed; IV/Greeks need BOTH strict-prior attachments; flows =
// v*size*greek."
//
// `vega(16)` is NOT walled: B3 names it as a REGISTERED extension that W2.4
// turns on. Every other unprojected greek is "unlisted" and therefore walled.
inline constexpr StreamSpec<62, 20, 29> kOptionPrintSpec{
    .stream = "options_prints",
    .names = {"symbol",       "expiration",   "strike",     "right",
              "timestamp",    "sequence",     "ext_condition1", "ext_condition2",
              "ext_condition3", "ext_condition4", "condition",  "size",
              "exchange",     "price",        "delta",      "theta",
              "vega",         "rho",          "epsilon",    "lambda",
              "gamma",        "vanna",        "charm",      "vomma",
              "veta",         "vera",         "speed",      "zomma",
              "color",        "ultima",       "d1",         "d2",
              "dual_delta",   "dual_gamma",   "implied_vol", "iv_error",
              "underlying_timestamp", "underlying_price", "side", "bid",
              "bid_size",     "bid_exchange", "ask",        "ask_size",
              "ask_exchange", "quote_timestamp", "dt_prev_contract_ms", "sweep_id",
              "sweep_n",      "sweep_size",   "sweep_exchanges", "dt_prev_any_ms",
              "dte",          "moneyness",    "prem",       "delta_flow",
              "gamma_flow",   "vanna_flow",   "speed_flow", "zomma_flow",
              "charm_flow",   "vomma_flow"},
    .projection = {1, 2, 3, 4, 5, 10, 11, 13, 14, 20, 21, 22, 34, 36, 37, 39, 40, 42, 43, 45},
    .roles = {ColumnRole::Date,        // expiration(1)
              ColumnRole::Strike,      // strike(2)
              ColumnRole::Text,        // right(3)
              ColumnRole::TimestampMs, // timestamp(4)
              ColumnRole::Int,         // sequence(5)
              ColumnRole::Int,         // condition(10)
              ColumnRole::Int,         // size(11)
              ColumnRole::Price,       // price(13)
              ColumnRole::Float,       // delta(14)
              ColumnRole::Float,       // gamma(20)
              ColumnRole::Float,       // vanna(21)
              ColumnRole::Float,       // charm(22)
              ColumnRole::Float,       // implied_vol(34)
              ColumnRole::Text,        // underlying_timestamp(36)
              ColumnRole::Float,       // underlying_price(37)
              ColumnRole::Price,       // bid(39)
              ColumnRole::Int,         // bid_size(40)
              ColumnRole::Price,       // ask(42)
              ColumnRole::Int,         // ask_size(43)
              ColumnRole::TimestampMs},// quote_timestamp(45)
    .forbidden = {ForbiddenColumn{15, ForbidReason::HardRefused},   // theta
                  ForbiddenColumn{17, ForbidReason::HardRefused},   // rho
                  ForbiddenColumn{18, ForbidReason::HardRefused},   // epsilon
                  ForbiddenColumn{19, ForbidReason::HardRefused},   // lambda
                  ForbiddenColumn{23, ForbidReason::HardRefused},   // vomma
                  ForbiddenColumn{24, ForbidReason::HardRefused},   // veta
                  ForbiddenColumn{25, ForbidReason::HardRefused},   // vera
                  ForbiddenColumn{26, ForbidReason::HardRefused},   // speed
                  ForbiddenColumn{27, ForbidReason::HardRefused},   // zomma
                  ForbiddenColumn{28, ForbidReason::HardRefused},   // color
                  ForbiddenColumn{29, ForbidReason::HardRefused},   // ultima
                  ForbiddenColumn{30, ForbidReason::HardRefused},   // d1
                  ForbiddenColumn{31, ForbidReason::HardRefused},   // d2
                  ForbiddenColumn{32, ForbidReason::HardRefused},   // dual_delta
                  ForbiddenColumn{33, ForbidReason::HardRefused},   // dual_gamma
                  ForbiddenColumn{38, ForbidReason::HardRefused},   // side
                  ForbiddenColumn{47, ForbidReason::HardRefused},   // sweep_id
                  ForbiddenColumn{48, ForbidReason::HardRefused},   // sweep_n
                  ForbiddenColumn{49, ForbidReason::HardRefused},   // sweep_size
                  ForbiddenColumn{50, ForbidReason::HardRefused},   // sweep_exchanges
                  ForbiddenColumn{53, ForbidReason::HardRefused},   // moneyness
                  ForbiddenColumn{54, ForbidReason::HardRefused},   // prem
                  ForbiddenColumn{55, ForbidReason::HardRefused},   // delta_flow
                  ForbiddenColumn{56, ForbidReason::HardRefused},   // gamma_flow
                  ForbiddenColumn{57, ForbidReason::HardRefused},   // vanna_flow
                  ForbiddenColumn{58, ForbidReason::HardRefused},   // speed_flow
                  ForbiddenColumn{59, ForbidReason::HardRefused},   // zomma_flow
                  ForbiddenColumn{60, ForbidReason::HardRefused},   // charm_flow
                  ForbiddenColumn{61, ForbidReason::HardRefused}},  // vomma_flow
    .timestamp_leaf = 4,
};
static_assert(spec_is_wellformed(kOptionPrintSpec));

/// The IWM COMPACT print profile, measured on the authorized session-125 file
/// (`options_prints/IWM/2022/2022-07-05.parquet`): `expiration` INT32/DATE,
/// `strike` INT32 mills, `right` UTF8, `size` INT32, `price`/`bid`/`ask` INT32
/// cents, `bid_size`/`ask_size` INT32, `underlying_timestamp` UTF8 text.
///
/// B5 (RUTW, "same 62-name wide profile") IS DEFERRED, AND THE DEFERRAL IS A
/// WALL: a wide file has the same 62 names but `Float64` strike/price and
/// `Int64` sizes, so it fails this vector at open and is refused by name.
inline constexpr std::array<ColumnForm, 20> kOptionPrintFormsIwmCompact{
    ColumnForm::DateI32,   ColumnForm::MillI32,   ColumnForm::TextUtf8,  ColumnForm::TimestampMsI64,
    ColumnForm::IntI64,    ColumnForm::IntI64,    ColumnForm::IntI32,    ColumnForm::CentI32,
    ColumnForm::FloatF64,  ColumnForm::FloatF64,  ColumnForm::FloatF64,  ColumnForm::FloatF64,
    ColumnForm::FloatF64,  ColumnForm::TextUtf8,  ColumnForm::FloatF64,  ColumnForm::CentI32,
    ColumnForm::IntI32,    ColumnForm::CentI32,   ColumnForm::IntI32,    ColumnForm::TimestampMsI64};

/// B3's single-leg condition set, EXPOSED AS A FIELD ONLY. The eligibility
/// logic that uses it lands in WP8; nothing in WP4 filters on it.
inline constexpr std::array<std::int64_t, 4> kSingleLegPrintConditions{18, 95, 125, 126};

[[nodiscard]] constexpr bool is_single_leg_print_condition(std::int64_t condition) noexcept {
  for (const std::int64_t admitted : kSingleLegPrintConditions) {
    if (condition == admitted) {
      return true;
    }
  }
  return false;
}

// ---------------------------------------------------------------------------
// B4 — option quotes (19 cols; 8 projected).
// ---------------------------------------------------------------------------
//
// FINAL_PLAN APPENDIX B4, verbatim: "expiration(1), strike(2), right(3), ts(4),
// bid_size(5), bid(7), ask_size(9), ask(11). Flat <=2024-07-31 / sharded after;
// coverage s209+; W2.1 only."
//
// THE WHOLE DERIVED FAMILY (13-18) IS WALLED — orchestrator ruling 2026-08-10,
// extending B1's law to B4: `d_bid_size`, `d_ask_size`, `bid_px_chg`,
// `ask_px_chg`, `dt_prev_contract_ms` and `mid` are the option-quote analogues
// of B1's "cols 9-15 ... NEVER READ — recomputed (scalar-means-before-derived
// law)". `mid` is the sharpest case and the reference states it outright
// (`option_quotes.rs:18-19`): the vendor `mid` is `bid + ask` in the compact
// profile and the true midpoint in the wide one, so it is never read and the
// midpoint is always computed.
inline constexpr StreamSpec<19, 8, 6> kOptionQuoteSpec{
    .stream = "option_quotes",
    .names = {"symbol", "expiration", "strike", "right", "timestamp", "bid_size", "bid_exchange",
              "bid", "bid_condition", "ask_size", "ask_exchange", "ask", "ask_condition",
              "d_bid_size", "d_ask_size", "bid_px_chg", "ask_px_chg", "dt_prev_contract_ms",
              "mid"},
    .projection = {1, 2, 3, 4, 5, 7, 9, 11},
    .roles = {ColumnRole::Date, ColumnRole::Strike, ColumnRole::Text, ColumnRole::TimestampMs,
              ColumnRole::Int, ColumnRole::Price, ColumnRole::Int, ColumnRole::Price},
    .forbidden = {ForbiddenColumn{13, ForbidReason::NeverRead},   // d_bid_size
                  ForbiddenColumn{14, ForbidReason::NeverRead},   // d_ask_size
                  ForbiddenColumn{15, ForbidReason::NeverRead},   // bid_px_chg
                  ForbiddenColumn{16, ForbidReason::NeverRead},   // ask_px_chg
                  ForbiddenColumn{17, ForbidReason::NeverRead},   // dt_prev_contract_ms
                  ForbiddenColumn{18, ForbidReason::NeverRead}},  // mid
    .timestamp_leaf = 4,
};
static_assert(spec_is_wellformed(kOptionQuoteSpec));

// ---------------------------------------------------------------------------
// The open-time gate and the decode door.
// ---------------------------------------------------------------------------

/// The file's own form for one projected column, or a refusal naming it.
/// PURE FOOTER WORK: it reads the parsed schema, never a page.
[[nodiscard]] FileExpected<ColumnForm> resolve_form(const parquet::File& file, std::size_t leaf,
                                                    ColumnRole role, std::string_view stream);

/// **OPEN IS THE WALL** (APPENDIX C3: "open(DayScope, Profile) refuses wrong
/// schema pre-payload"). Checks, in order and before any payload byte:
///   1. the file's leaf count equals the pinned name count;
///   2. every leaf's NAME equals its pin, in order — including columns this
///      reader never decodes;
///   3. every projected column's on-disk form.
/// `pinned` is the admitted form vector when the stream's profile is DECLARED
/// (the registry row for stock quotes; the single measured profile for trades
/// and IWM prints), or empty when the profile is DETECTED from the file's own
/// schema against the role's admitted set (option quotes: two layouts and two
/// profiles are both lawful).
[[nodiscard]] FileExpected<std::vector<ColumnForm>> gate_schema(
    const SpecView& spec, const parquet::File& file, std::span<const ColumnForm> pinned);

/// **THE ONLY DOOR TO A LEAF'S BYTES.** A leaf outside the projection is a
/// refusal: COLUMN_FORBIDDEN naming the column and its wall reason when the
/// spec walls it, SCHEMA_MISMATCH when the leaf is simply not part of this
/// stream. The readers call exactly this, so the wall cannot be dodged.
[[nodiscard]] FileExpected<std::int64_t> read_pinned_column(const SpecView& spec,
                                                            const parquet::File& file,
                                                            std::size_t row_group, std::size_t leaf,
                                                            DecodeWorkspace& workspace,
                                                            ColumnData& out);

/// Same door, keyed by the pinned NAME — the shape B2's `price_lead_1` rule
/// takes ("name-pinned only"). An unknown name is SCHEMA_MISMATCH.
[[nodiscard]] FileExpected<std::int64_t> read_pinned_column_named(const SpecView& spec,
                                                                  const parquet::File& file,
                                                                  std::size_t row_group,
                                                                  std::string_view name,
                                                                  DecodeWorkspace& workspace,
                                                                  ColumnData& out);

}  // namespace qr::sources

#endif  // QR_SOURCES_STREAM_SPEC_HPP
