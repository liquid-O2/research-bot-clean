// qr_sources/option_prints.hpp — B3: the IWM option-print reader.
//
// SPEC (FINAL_PLAN APPENDIX B3, verbatim): "expiration(1), strike(2), right(3),
// ts(4), sequence(5), condition(10) [single-leg in {18,95,125,126}], size(11),
// price(13), delta(14), gamma(20), vanna(21), charm(22), IV(34),
// underlying_ts(36), underlying_px(37), bid(39), bid_size(40), ask(42),
// ask_size(43), quote_ts(45). +vega(16) via W2.4 registered extension.
// HARD-REFUSED: side(38), sweep_*(47-50), prem/*_flow(53-61), unlisted Greeks.
// Aggressor recomputed; IV/Greeks need BOTH strict-prior attachments; flows =
// v*size*greek."
// Reference semantics (read-only): select_v2/src/sources/options_prints.rs.
//
// THE HARD REFUSALS ARE THE POINT OF THIS READER. `side` is the vendor's
// aggressor answer and this program recomputes aggression from the quote it
// certifies itself; `sweep_*` and the `*_flow`/`prem` block are vendor
// derivations of exactly the quantities the feature families exist to build.
// They are walled in `kOptionPrintSpec.forbidden`, so reaching them is a
// COLUMN_FORBIDDEN refusal naming the column — not a code review convention.
//
// TWO ATTACHMENT CLOCKS, BOTH RETAINED RAW. B3 requires greeks and IV to rest
// on BOTH strict-prior attachments (`underlying_ts(36)` and `quote_ts(45)`).
// This reader retains both without interpreting either: `quote_ts` as frame-B
// milliseconds, `underlying_ts` as the UTF-8 text the compact profile stores
// (measured: `2022-07-05T09:30:00.000`). WP4 does not parse that text — no
// cited spec section says how, and inventing a parse is exactly what the stop
// rule forbids.
//
// B5 (RUTW prints) HAS ITS OWN READER — `qr_sources/rutw_prints.hpp`. The 62
// names, the 20-leaf projection and the 29 hard-refused columns are SHARED (a
// compile-time assert in stream_spec.hpp), and so is every row law below: this
// file owns the decode, the RTH window, the monotonicity refusal, the
// equal-time group machine and the census, and BOTH readers drive it. What is
// not shared is which corpus and which profile each is pinned to, and that is
// a two-way wall: this reader refuses a RUTW corpus root by name, and the RUTW
// reader refuses both a non-RUTW root and IWM-compact bytes.
#ifndef QR_SOURCES_OPTION_PRINTS_HPP
#define QR_SOURCES_OPTION_PRINTS_HPP

#include <array>
#include <cstdint>
#include <filesystem>
#include <set>
#include <span>
#include <string>
#include <string_view>
#include <tuple>
#include <vector>

#include "qr_registry/day_scope.hpp"
#include "qr_sources/normalize.hpp"
#include "qr_sources/session_source.hpp"
#include "qr_sources/stream_spec.hpp"

namespace qr::sources {

/// Projection slots of `kOptionPrintSpec` == bit positions of `null_mask`.
/// Slots are NOT leaf indices here (B3 projects 20 of 62 columns), which is
/// exactly why the mask is defined on slots.
enum OptionPrintSlot : std::size_t {
  kPrintSlotExpiration = 0,        // leaf 1
  kPrintSlotStrike = 1,            // leaf 2
  kPrintSlotRight = 2,             // leaf 3
  kPrintSlotTimestamp = 3,         // leaf 4
  kPrintSlotSequence = 4,          // leaf 5
  kPrintSlotCondition = 5,         // leaf 10
  kPrintSlotSize = 6,              // leaf 11
  kPrintSlotPrice = 7,             // leaf 13
  kPrintSlotDelta = 8,             // leaf 14
  kPrintSlotGamma = 9,             // leaf 20
  kPrintSlotVanna = 10,            // leaf 21
  kPrintSlotCharm = 11,            // leaf 22
  kPrintSlotImpliedVol = 12,       // leaf 34
  kPrintSlotUnderlyingTimestamp = 13,  // leaf 36
  kPrintSlotUnderlyingPrice = 14,  // leaf 37
  kPrintSlotBid = 15,              // leaf 39
  kPrintSlotBidSize = 16,          // leaf 40
  kPrintSlotAsk = 17,              // leaf 42
  kPrintSlotAskSize = 18,          // leaf 43
  kPrintSlotQuoteTimestamp = 19,   // leaf 45
};

/// One retained option print.
struct OptionPrintRow {
  /// Print instant, naive-ET (frame B) milliseconds.
  std::int64_t ts_ms_b = 0;
  /// The quote attachment clock, raw frame-B milliseconds.
  std::int64_t quote_ts_ms_b = 0;
  std::int64_t sequence = 0;
  /// The print condition. B3's single-leg set is EXPOSED, not applied:
  /// `is_single_leg_print_condition` is available and nothing here filters.
  std::int64_t condition = 0;
  std::int64_t size = 0;
  std::int64_t price_u6 = 0;
  std::int64_t strike_u6 = 0;
  std::int64_t bid_u6 = 0;
  std::int64_t ask_u6 = 0;
  std::int64_t bid_size = 0;
  std::int64_t ask_size = 0;
  double delta = 0.0;
  double gamma = 0.0;
  double vanna = 0.0;
  double charm = 0.0;
  double implied_vol = 0.0;
  double underlying_price = 0.0;
  /// The underlying attachment clock as the tape stores it: UTF-8 text,
  /// retained verbatim and interpreted by nobody in WP4.
  ///
  /// ORCHESTRATOR RULING (2026-08-10): verbatim retention here is final, and
  /// the PARSE OWNER IS WP8's attachment layer. The value is naive-ET frame-B
  /// ISO-8601 with milliseconds (the token-corpus clock law; measured
  /// `2022-07-05T09:30:00.000`), so WP8 converts it exactly as it converts any
  /// other frame-B stamp — through qr_clock and never by a second 09:30 anchor.
  /// A value that does not parse there is `Validity::MALFORMED` (the fifteenth
  /// state), never MISSING and never a substituted instant.
  InlineText underlying_ts_text{};
  /// Expiration as days since the Unix epoch.
  std::int32_t expiration_day = 0;
  Right right = Right::Other;
  std::uint32_t null_mask = 0;

  [[nodiscard]] std::int64_t group_ts_ms() const noexcept { return ts_ms_b; }
  [[nodiscard]] bool is_null(std::size_t slot) const noexcept {
    return (null_mask & (std::uint32_t{1} << slot)) != 0;
  }
  /// Whether this print's condition is in B3's single-leg set. A FIELD-LEVEL
  /// exposure: the eligibility logic that uses it lands in WP8.
  [[nodiscard]] bool is_single_leg() const noexcept {
    return !is_null(kPrintSlotCondition) && is_single_leg_print_condition(condition);
  }
};

[[nodiscard]] bool canonical_less(const OptionPrintRow& left, const OptionPrintRow& right) noexcept;
void append_serialized(const OptionPrintRow& row, std::vector<std::uint8_t>& out);

struct OptionPrintDigests {
  std::array<ValueDigest, 20> field{};
  void fold(const OptionPrintRow& row) noexcept;
  [[nodiscard]] static std::string_view field_name(std::size_t slot) noexcept;
};

// ---------------------------------------------------------------------------
// The print CENSUS — counted, never applied.
// ---------------------------------------------------------------------------

/// Per-session counters over the ADMITTED (RTH) rows of a print tape.
///
/// EVERY FIELD IS A COUNT OF A CONDITION THE READER DOES NOT ACT ON. WP4's rule
/// for B3 is that eligibility logic lives downstream (`is_single_leg` is
/// exposed and nothing filters on it); the same rule governs here. These
/// counters exist so a census can say what a corpus actually contains — how
/// many prints carry a usable price, how many carry an attachment that is
/// strictly prior — WITHOUT any reader dropping a row on that basis.
///
/// THE ATTACHMENT COLUMNS ARE THE FRAME-B CENSUS FORM, NOT THE AUTHORITY.
/// `quote_ts(45)` and the print instant `ts(4)` are both frame-B milliseconds
/// of the same session, so `quote_ts_ms_b < ts_ms_b` is exact and needs no
/// clock. The AUTHORITATIVE classification — B3's "IV/Greeks need BOTH
/// strict-prior attachments" — stays where it already lives, in qr_carriers'
/// `classify_attachment_ms` / `classify_attachment_text`, which also decide
/// WCD and off-day cases. `underlying_ts(36)` is text WP4 does not parse, so it
/// is censused by presence and by whether its first ten bytes are this
/// session's own civil day — a comparison, never a parse.
struct OptionPrintCensus {
  std::int64_t rth_rows = 0;
  std::int64_t group_count = 0;
  std::int64_t skipped_null_rows = 0;
  /// quote_ts(45): strictly before the print / not before it / absent.
  std::int64_t quote_attachment_prior = 0;
  std::int64_t quote_attachment_not_prior = 0;
  std::int64_t quote_attachment_absent = 0;
  /// underlying_ts(36): present and stamped with this session's day / present
  /// and stamped with some other day / absent.
  std::int64_t underlying_on_day = 0;
  std::int64_t underlying_off_day = 0;
  std::int64_t underlying_absent = 0;
  /// Rows with no null in any of the 20 projected slots.
  std::int64_t fully_populated_rows = 0;
  /// Rows whose five projected greeks and IV are all present.
  std::int64_t greek_complete_rows = 0;
  /// JUNK, by its four mechanical causes. A row may hit more than one, so the
  /// four columns do not sum to `junk_rows`.
  std::int64_t junk_price_rows = 0;
  std::int64_t junk_size_rows = 0;
  std::int64_t junk_right_rows = 0;
  std::int64_t junk_crossed_quote_rows = 0;
  /// Admitted rows hitting at least one junk cause.
  std::int64_t junk_rows = 0;

  static constexpr std::size_t kFields = 16;
  [[nodiscard]] std::int64_t field(std::size_t index) const noexcept;
  [[nodiscard]] static std::string_view field_name(std::size_t index) noexcept;
};

/// Folds one ADMITTED row into the census. `day` is the session's own civil
/// day (`YYYY-MM-DD`), used for the underlying-stamp comparison only.
void fold_census(OptionPrintCensus& census, const OptionPrintRow& row,
                 std::string_view day) noexcept;

/// Distinct-contract coverage, kept out of the row counters because it needs
/// memory proportional to the contract set. Ordered containers only: iteration
/// order is output, and two-run byte identity is a law.
class OptionPrintCoverage {
 public:
  void observe(const OptionPrintRow& row);
  [[nodiscard]] std::int64_t contracts() const noexcept {
    return static_cast<std::int64_t>(contracts_.size());
  }
  [[nodiscard]] std::int64_t expirations() const noexcept {
    return static_cast<std::int64_t>(expirations_.size());
  }
  [[nodiscard]] std::int64_t strikes() const noexcept {
    return static_cast<std::int64_t>(strikes_.size());
  }

 private:
  /// (expiration_day, strike_u6, right) — the contract identity B4/W2.1 use.
  std::set<std::tuple<std::int32_t, std::int64_t, std::uint8_t>> contracts_;
  std::set<std::int32_t> expirations_;
  std::set<std::int64_t> strikes_;
};

// ---------------------------------------------------------------------------
// The shared B3/B5 streaming core.
// ---------------------------------------------------------------------------

/// The row laws of an option-print payload, in ONE place.
///
/// B5 says "same laws", and this module's own stated rule is that a wall with
/// four copies is four walls to get wrong. So the admission rule, the
/// monotonicity refusal, the RTH window, the per-slot decode, the equal-time
/// group machine and the census live here, and the two readers
/// (`OptionPrintReader`, `RutwPrintReader`) differ ONLY in which corpus root
/// they admit and which admitted form vector they pin.
class OptionPrintTape {
 public:
  struct Group {
    std::int64_t ts_ms_b = 0;
    std::span<const OptionPrintRow> rows;
  };

  explicit OptionPrintTape(std::string day) : day_(std::move(day)) {}

  /// Pulls the next equal-millisecond group out of `source`.
  [[nodiscard]] FileExpected<bool> next_group(SessionSource& source, Group& out);

  [[nodiscard]] const OptionPrintCensus& census() const noexcept { return census_; }
  [[nodiscard]] std::int64_t rth_rows() const noexcept { return census_.rth_rows; }
  [[nodiscard]] std::int64_t group_count() const noexcept { return census_.group_count; }
  [[nodiscard]] std::int64_t skipped_null_rows() const noexcept {
    return census_.skipped_null_rows;
  }

 private:
  [[nodiscard]] FileExpected<bool> fill(SessionSource& source);

  std::string day_;
  GroupTape<OptionPrintRow> tape_;
  OptionPrintCensus census_{};
  std::int64_t last_ts_ms_ = 0;
  bool has_last_ts_ = false;
  bool exhausted_ = false;
};

/// Streaming option-print reader for one admitted session.
class OptionPrintReader {
 public:
  using Group = OptionPrintTape::Group;

  OptionPrintReader(const OptionPrintReader&) = delete;
  OptionPrintReader& operator=(const OptionPrintReader&) = delete;
  OptionPrintReader(OptionPrintReader&&) = default;
  OptionPrintReader& operator=(OptionPrintReader&&) = default;
  ~OptionPrintReader() = default;

  /// Opens `<corpus_root>/<YYYY>/<day>.parquet` for an ADMITTED session, pinned
  /// to the IWM compact profile.
  [[nodiscard]] static FileExpected<OptionPrintReader> open(
      const DayScope& scope, const std::filesystem::path& corpus_root);

  [[nodiscard]] FileExpected<bool> next_group(Group& out) {
    return tape_.next_group(source_, out);
  }

  [[nodiscard]] std::int64_t rth_rows() const noexcept { return tape_.rth_rows(); }
  [[nodiscard]] std::int64_t group_count() const noexcept { return tape_.group_count(); }
  /// Rows dropped because the print instant was absent (the reference's
  /// admission rule, `options_prints.rs:298-300`).
  [[nodiscard]] std::int64_t skipped_null_rows() const noexcept {
    return tape_.skipped_null_rows();
  }
  [[nodiscard]] const OptionPrintCensus& census() const noexcept { return tape_.census(); }
  [[nodiscard]] std::int64_t decoded_values() const noexcept { return source_.decoded_values(); }
  [[nodiscard]] const std::filesystem::path& path() const noexcept { return source_.path(); }
  [[nodiscard]] const SessionSource& source() const noexcept { return source_; }

 private:
  OptionPrintReader(SessionSource source, std::string day)
      : source_(std::move(source)), tape_(std::move(day)) {}

  SessionSource source_;
  OptionPrintTape tape_;
};

}  // namespace qr::sources

#endif  // QR_SOURCES_OPTION_PRINTS_HPP
