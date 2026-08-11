// qr_carriers/attach.hpp — THE ATTACHMENT LAW, THE SIGNING LAW, AND THE STOCK
// CONDITION CONTRACT.
//
// SPEC (evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 4, verbatim):
//
//   "An attached stock/option quote or underlying value is temporally usable
//    only when its observed timestamp is nonnull and strictly `< print_timestamp
//    < decision_cutoff`; an underlying value must additionally be finite and
//    positive. A quote is signing/valuation-valid only when bid/ask are finite,
//    bid>0, ask>0, **ask>bid**, and every available bid/ask condition passes its
//    pinned condition contract. Locked, crossed, one-sided/nonpositive,
//    nonfinite, or condition-ineligible quotes remain typed quality but cannot
//    sign an aggressor or supply midpoint/spread/depth/valuation. Equality is
//    `EQUAL_TIME_UNORDERED` and unavailable; a later timestamp is
//    `ATTACHMENT_FUTURE`; null is `ATTACHMENT_MISSING`. The print remains.
//    Attachment age is a continuous channel; no unregistered staleness cutoff
//    gates it (age>5s is reported diagnostically). The 42 known future option
//    attachments must therefore be masked, not consumed."
//
//   "The stock print eligibility contract is the production allowlist in
//    `engine/crates/select/src/execution_contract.rs` ...:
//    `is_trade_condition_eligible(code)` admits exactly code0 (REGULAR),
//    types40..44 as CANCEL, and excludes every other code;
//    `is_quote_condition_eligible(code)` likewise admits only code0. The
//    adapter/sentinel contract is `adapters/stock_trades.rs` ...: each of four
//    extended-condition slots is absent only at sentinel255, otherwise it too
//    must be code0. ... Thus a direction-eligible stock print requires primary
//    code0, every present extended code0, finite positive price, and positive
//    size. All other prints remain in raw counts/quality with their typed
//    reason ... Per session/window the immutable quality ledger reports total,
//    eligible, primary-nonzero, extended-nonzero, CANCEL40..44, sentinel-absent,
//    nonpositive-size, and nonfinite-price counts."
//
// THE UNDERLYING-TIMESTAMP PARSE IS THIS MODULE'S, BY RULING. WP4 retained
// `underlying_timestamp(36)` as verbatim UTF-8 and interpreted nothing
// (qr_sources/option_prints.hpp: "the PARSE OWNER IS WP8's attachment layer.
// The value is naive-ET frame-B ISO-8601 with milliseconds ... A value that
// does not parse there is `Validity::MALFORMED` (the fifteenth state), never
// MISSING and never a substituted instant."). `parse_naive_et_iso_ms` below is
// that parse and nothing else in the module reads that text.
//
// WHY THE PARSE IS EXACT-FORM AND NOT TOLERANT: the corpus clock law is
// naive-Eastern frame B. A timestamp carrying `Z`, an offset, or a different
// precision would be a DIFFERENT FRAME wearing the same shape, and accepting it
// would put the whole option attachment layer 4-5 hours into its own future
// (memory: "clock frame hazard"). Exactly `YYYY-MM-DDTHH:MM:SS.mmm` parses;
// everything else is MALFORMED.
//
// NOTHING HERE MASKS A CHANNEL. This header CLASSIFIES; the modality
// constructors apply the mask. That split is deliberate: the WP8 masking map in
// qr_clock/session_clock.hpp is a mapping from an attachment class to a
// `Validity`, and a classifier that also masked would make the map unobservable.
#ifndef QR_CARRIERS_ATTACH_HPP
#define QR_CARRIERS_ATTACH_HPP

#include <cstdint>
#include <optional>
#include <string_view>

#include "qr_clock/session_clock.hpp"
#include "qr_core/validity.hpp"
#include "qr_sources/stock_trades.hpp"

namespace qr::carriers {

// ---------------------------------------------------------------------------
// The attachment classification.
// ---------------------------------------------------------------------------

/// The SIX typed outcomes of asking "is this attachment usable for this print?".
/// Five come from the card's own words plus qr_clock's total classifier; the
/// sixth (MALFORMED) is the fifteenth validity state, reached only through the
/// underlying-timestamp text parse and the millisecond widening.
enum class AttachState : std::uint8_t {
  /// Nonnull, on this session's civil day, and STRICTLY earlier than the print.
  USABLE = 0,
  /// "null is `ATTACHMENT_MISSING`".
  ATTACHMENT_MISSING = 1,
  /// "Equality is `EQUAL_TIME_UNORDERED` and unavailable".
  EQUAL_TIME_UNORDERED = 2,
  /// "a later timestamp is `ATTACHMENT_FUTURE`" — the 42 known future option
  /// attachments land here and are masked, not consumed.
  ATTACHMENT_FUTURE = 3,
  /// A well-formed instant on a different civil day (delta_days carried).
  ATTACHMENT_WRONG_DAY = 4,
  /// The attachment's own arithmetic or encoding refuses.
  ATTACHMENT_MALFORMED = 5,
};
inline constexpr std::size_t kAttachStateCount = 6;

[[nodiscard]] const char* attach_state_name(AttachState state) noexcept;

/// The WP8 masking map (qr_clock/session_clock.hpp, orchestrator ruling
/// 2026-08-10), extended by the two states that are about ORDER rather than
/// day: usable -> VALID, missing -> MISSING, equal -> EQUAL_TIME_UNORDERED,
/// future -> ATTACHMENT_FUTURE, wrong day -> WRONG_CIVIL_DAY, malformed ->
/// MALFORMED.
[[nodiscard]] Validity attach_validity(AttachState state) noexcept;

/// One classified attachment: its state, its converted instant when USABLE, and
/// its signed day delta when ATTACHMENT_WRONG_DAY.
struct Attachment {
  AttachState state = AttachState::ATTACHMENT_MISSING;
  /// Frame-A nanoseconds. Meaningful only when `state == USABLE`.
  std::int64_t ts_ns_a = 0;
  /// Signed civil-day difference. Meaningful only when ATTACHMENT_WRONG_DAY.
  std::int64_t delta_days = 0;

  [[nodiscard]] bool usable() const noexcept { return state == AttachState::USABLE; }
  [[nodiscard]] Validity validity() const noexcept { return attach_validity(state); }
};

/// Classifies a millisecond-stamped attachment against the print it hangs on.
/// `attach_ms_b` is the raw frame-B millisecond cell (nullopt when the column
/// was null); `print_ts_ns_a` is the print's own already-converted frame-A
/// instant. The conversion goes through `SessionClock::classify_attach_ms` and
/// nowhere else — there is no second 09:30 anchor in this module.
[[nodiscard]] Attachment classify_attachment_ms(const SessionClock& clock,
                                                std::optional<std::int64_t> attach_ms_b,
                                                std::int64_t print_ts_ns_a) noexcept;

/// The same classification for an attachment whose stamp is TEXT (option
/// `underlying_timestamp`). An unparseable value is ATTACHMENT_MALFORMED.
[[nodiscard]] Attachment classify_attachment_text(const SessionClock& clock,
                                                  std::optional<std::string_view> attach_text,
                                                  std::int64_t print_ts_ns_a) noexcept;

/// Naive-ET frame-B epoch MILLISECONDS of a canonical `YYYY-MM-DDTHH:MM:SS.mmm`
/// value, or nullopt. Exactly 23 characters, exactly those separators, exactly
/// three fractional digits; hour < 24, minute < 60, second < 60. No zone
/// designator, no offset, no other precision (see the header note).
[[nodiscard]] std::optional<std::int64_t> parse_naive_et_iso_ms(std::string_view text) noexcept;

// ---------------------------------------------------------------------------
// The quote signing/valuation contract.
// ---------------------------------------------------------------------------

/// A two-sided quote as this module sees it: u6 prices, share/contract sizes,
/// and per-side presence. `bid_condition`/`ask_condition` are optional because
/// B3 projects no option quote conditions — "every AVAILABLE bid/ask condition"
/// is vacuously satisfied when the stream carries none, and is code 0 when it
/// does (`is_quote_condition_eligible` admits only code 0).
struct QuoteFields {
  std::optional<std::int64_t> bid_u6;
  std::optional<std::int64_t> ask_u6;
  std::optional<std::int64_t> bid_size;
  std::optional<std::int64_t> ask_size;
  std::optional<std::int64_t> bid_condition;
  std::optional<std::int64_t> ask_condition;
  /// False only when the source value was a non-finite double before u6
  /// normalization. Integer-cent profiles cannot express one, so this is true
  /// there by construction and the state remains reachable for the float
  /// profiles.
  bool prices_finite = true;
};

/// `is_quote_condition_eligible(code)`: admits only code 0.
[[nodiscard]] constexpr bool is_quote_condition_eligible(std::int64_t code) noexcept {
  return code == 0;
}

/// THE SIGNING LAW, as a single typed verdict built with the frozen worst-wins
/// `combine` lattice rather than a hand-ordered if-chain: finite, bid>0, ask>0,
/// ask>bid, every available condition eligible. VALID only when nothing fired;
/// otherwise the typed quality token (LOCKED / CROSSED / ONE_SIDED /
/// NONPOSITIVE / NONFINITE / CONDITION_INELIGIBLE / MISSING) that the census
/// keeps distinct.
[[nodiscard]] Validity quote_signing_validity(const QuoteFields& quote) noexcept;

// ---------------------------------------------------------------------------
// The stock print condition contract.
// ---------------------------------------------------------------------------

/// The primary trade-condition classes the production allowlist admits.
enum class TradeConditionClass : std::uint8_t {
  /// Code 0.
  REGULAR = 0,
  /// Types 40..44.
  CANCEL = 1,
  /// Every other code — excluded.
  INELIGIBLE = 2,
};

[[nodiscard]] const char* trade_condition_class_name(TradeConditionClass value) noexcept;

/// First and last CANCEL type, inclusive.
inline constexpr std::int64_t kCancelConditionFirst = 40;
inline constexpr std::int64_t kCancelConditionLast = 44;
/// The extended-condition slot sentinel: "absent only at sentinel255".
inline constexpr std::int64_t kExtendedConditionSentinel = 255;

/// **CC-008 (orchestrator ruling, 2026-08-10): the ADMITTED extended-condition
/// vocabulary is {0, 32}; the sentinel stays {255}; the conjunction is
/// RETAINED.**
///
/// The card's V4 text says a present extended slot "must be code0", and on real
/// tape that admits nothing: this lane measured all 598,255 prints of sessions
/// {125, 500, 625} and found `ext1 == 32` IFF `primary == 0`, with ZERO
/// exceptions on every session (45,169 / 88,205 / 47,460 — exactly each
/// session's primary-0 count), while 32 never appears in slots 2..4 and 255 is
/// the dominant filler in all four slots. 32 is therefore the raw
/// sale-condition-list spelling of REGULAR (the ASCII blank slot) and primary 0
/// is the vendor's normalized spelling of the SAME fact; the conjunction's
/// vocabulary was wrong, not the conjunction.
///
/// FAIL-CLOSED PROPERTIES ARE PRESERVED, and that is the point of admitting a
/// VOCABULARY rather than deleting the clause: a primary-0 print carrying any
/// real extended code (95, 115, 96, 108, 124, ...) stays INELIGIBLE, which is a
/// case the corpus has never produced and which the clause exists to refuse if
/// it ever does. The census that grounds this ruling is pinned in
/// `tests/fixtures/carriers_conditions_session{125,500,625}.tsv` and is read by
/// the `Cc008CensusPin` fixtures.
inline constexpr std::array<std::int64_t, 2> kExtendedConditionAdmitted{0, 32};

/// True when a PRESENT (non-sentinel) extended slot carries an admitted code.
[[nodiscard]] constexpr bool is_extended_condition_admitted(std::int64_t code) noexcept {
  for (const std::int64_t admitted : kExtendedConditionAdmitted) {
    if (code == admitted) {
      return true;
    }
  }
  return false;
}

[[nodiscard]] constexpr TradeConditionClass classify_trade_condition(std::int64_t code) noexcept {
  if (code == 0) {
    return TradeConditionClass::REGULAR;
  }
  if (code >= kCancelConditionFirst && code <= kCancelConditionLast) {
    return TradeConditionClass::CANCEL;
  }
  return TradeConditionClass::INELIGIBLE;
}

/// One print's condition verdict, with every fact the immutable quality ledger
/// counts, so nothing is recomputed from a different reading downstream.
struct StockPrintEligibility {
  TradeConditionClass primary = TradeConditionClass::INELIGIBLE;
  /// The primary code was not 0 (CANCEL included).
  bool primary_nonzero = false;
  /// At least one PRESENT extended slot carried a code OUTSIDE the admitted
  /// vocabulary. The card names this ledger field "extended-nonzero"; under
  /// CC-008 the disqualifying set is "not in {0, 32}" rather than "not 0", and
  /// the field keeps the card's name because its ROLE — the extended-condition
  /// disqualification census — is unchanged. The raw per-slot code histograms
  /// the probe prints in full retain every code count, so nothing is lost.
  bool extended_nonzero = false;
  /// At least one extended slot was absent (sentinel 255 or a null cell).
  bool sentinel_absent = false;
  /// Size cell absent or <= 0.
  bool nonpositive_size = false;
  /// Price cell absent or <= 0. The compact integer profiles cannot encode a
  /// NaN, so "nonfinite price" is exactly this set there; the name is the
  /// card's ledger name and is kept.
  bool nonfinite_price = false;
  /// "a direction-eligible stock print requires primary code0, every present
  /// extended code0, finite positive price, and positive size" — with CC-008's
  /// admitted extended vocabulary {0, 32} in place of the bare 0.
  bool direction_eligible = false;
  /// The SAME verdict as a typed state, worst-wins over the four clauses, so a
  /// masked directional channel carries the exact reason instead of a generic
  /// MISSING. VALID exactly when `direction_eligible`.
  Validity directional_validity = Validity::CONDITION_INELIGIBLE;
};

/// Applies the contract to one decoded print.
[[nodiscard]] StockPrintEligibility classify_stock_print(
    const qr::sources::StockTradeRow& row) noexcept;

/// The card's immutable quality ledger, name for name.
struct StockQualityLedger {
  std::int64_t total = 0;
  std::int64_t eligible = 0;
  std::int64_t primary_nonzero = 0;
  std::int64_t extended_nonzero = 0;
  std::int64_t cancel_40_44 = 0;
  std::int64_t sentinel_absent = 0;
  std::int64_t nonpositive_size = 0;
  std::int64_t nonfinite_price = 0;

  void fold(const StockPrintEligibility& verdict) noexcept;
};

}  // namespace qr::carriers

#endif  // QR_CARRIERS_ATTACH_HPP
