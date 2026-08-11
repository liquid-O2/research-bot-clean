// qr_carriers/src/attach.cpp — the attachment, signing and condition contracts.
#include "qr_carriers/attach.hpp"

#include <array>

#include "qr_core/refusal.hpp"

namespace qr::carriers {
namespace {

/// Exactly the canonical measured shape `2022-07-05T09:30:00.000`.
constexpr std::size_t kIsoMsLength = 23;

[[nodiscard]] bool digits(std::string_view text, std::size_t offset, std::size_t count,
                          std::int64_t& out) noexcept {
  std::int64_t value = 0;
  for (std::size_t index = 0; index < count; ++index) {
    const char character = text[offset + index];
    if (character < '0' || character > '9') {
      return false;
    }
    value = value * 10 + (character - '0');
  }
  out = value;
  return true;
}

}  // namespace

const char* attach_state_name(AttachState state) noexcept {
  switch (state) {
    case AttachState::USABLE:
      return "USABLE";
    case AttachState::ATTACHMENT_MISSING:
      return "ATTACHMENT_MISSING";
    case AttachState::EQUAL_TIME_UNORDERED:
      return "EQUAL_TIME_UNORDERED";
    case AttachState::ATTACHMENT_FUTURE:
      return "ATTACHMENT_FUTURE";
    case AttachState::ATTACHMENT_WRONG_DAY:
      return "ATTACHMENT_WRONG_DAY";
    case AttachState::ATTACHMENT_MALFORMED:
      return "ATTACHMENT_MALFORMED";
  }
  return "UNKNOWN_ATTACH_STATE";
}

Validity attach_validity(AttachState state) noexcept {
  switch (state) {
    case AttachState::USABLE:
      return Validity::VALID;
    case AttachState::ATTACHMENT_MISSING:
      return Validity::MISSING;
    case AttachState::EQUAL_TIME_UNORDERED:
      return Validity::EQUAL_TIME_UNORDERED;
    case AttachState::ATTACHMENT_FUTURE:
      return Validity::ATTACHMENT_FUTURE;
    case AttachState::ATTACHMENT_WRONG_DAY:
      return Validity::WRONG_CIVIL_DAY;
    case AttachState::ATTACHMENT_MALFORMED:
      return Validity::MALFORMED;
  }
  return Validity::MISSING;
}

namespace {

/// The order half of the law, applied only after the clock has said ON_DAY.
[[nodiscard]] Attachment order_against_print(FrameA attach_a, std::int64_t print_ts_ns_a) noexcept {
  Attachment out;
  if (attach_a.ns() < print_ts_ns_a) {
    out.state = AttachState::USABLE;
    out.ts_ns_a = attach_a.ns();
  } else if (attach_a.ns() == print_ts_ns_a) {
    out.state = AttachState::EQUAL_TIME_UNORDERED;
  } else {
    out.state = AttachState::ATTACHMENT_FUTURE;
  }
  return out;
}

[[nodiscard]] Attachment from_attach_class(const AttachClass& classified,
                                           std::int64_t print_ts_ns_a) noexcept {
  Attachment out;
  switch (classified.kind()) {
    case AttachKind::MISSING:
      out.state = AttachState::ATTACHMENT_MISSING;
      return out;
    case AttachKind::MALFORMED:
      out.state = AttachState::ATTACHMENT_MALFORMED;
      return out;
    case AttachKind::WRONG_CIVIL_DAY:
      out.state = AttachState::ATTACHMENT_WRONG_DAY;
      out.delta_days = classified.delta_days();
      return out;
    case AttachKind::ON_DAY:
      return order_against_print(classified.frame_a(), print_ts_ns_a);
  }
  out.state = AttachState::ATTACHMENT_MALFORMED;
  return out;
}

}  // namespace

Attachment classify_attachment_ms(const SessionClock& clock,
                                  std::optional<std::int64_t> attach_ms_b,
                                  std::int64_t print_ts_ns_a) noexcept {
  return from_attach_class(clock.classify_attach_ms(attach_ms_b), print_ts_ns_a);
}

Attachment classify_attachment_text(const SessionClock& clock,
                                    std::optional<std::string_view> attach_text,
                                    std::int64_t print_ts_ns_a) noexcept {
  if (!attach_text.has_value()) {
    Attachment out;
    out.state = AttachState::ATTACHMENT_MISSING;
    return out;
  }
  const std::optional<std::int64_t> milliseconds = parse_naive_et_iso_ms(*attach_text);
  if (!milliseconds.has_value()) {
    Attachment out;
    out.state = AttachState::ATTACHMENT_MALFORMED;
    return out;
  }
  return from_attach_class(clock.classify_attach_ms(milliseconds), print_ts_ns_a);
}

std::optional<std::int64_t> parse_naive_et_iso_ms(std::string_view text) noexcept {
  if (text.size() != kIsoMsLength) {
    return std::nullopt;
  }
  if (text[4] != '-' || text[7] != '-' || text[10] != 'T' || text[13] != ':' || text[16] != ':' ||
      text[19] != '.') {
    return std::nullopt;
  }
  // The civil day goes through qr_core's own parser, so a day that does not
  // exist (2022-02-30) refuses here exactly as it refuses everywhere else.
  const auto civil = CivilDate::parse_ymd(text.substr(0, 10));
  if (!civil.has_value()) {
    return std::nullopt;
  }
  std::int64_t hour = 0;
  std::int64_t minute = 0;
  std::int64_t second = 0;
  std::int64_t milli = 0;
  if (!digits(text, 11, 2, hour) || !digits(text, 14, 2, minute) || !digits(text, 17, 2, second) ||
      !digits(text, 20, 3, milli)) {
    return std::nullopt;
  }
  if (hour > 23 || minute > 59 || second > 59) {
    return std::nullopt;
  }
  const std::int64_t day_ms = civil.value().days_since_epoch() * kMillisecondsPerDay;
  const std::int64_t time_ms = ((hour * 60 + minute) * 60 + second) * 1000 + milli;
  return day_ms + time_ms;
}

Validity quote_signing_validity(const QuoteFields& quote) noexcept {
  const bool bid_present = quote.bid_u6.has_value();
  const bool ask_present = quote.ask_u6.has_value();
  if (!bid_present && !ask_present) {
    return Validity::MISSING;
  }
  if (!bid_present || !ask_present) {
    return Validity::ONE_SIDED;
  }
  Validity verdict = Validity::VALID;
  if (!quote.prices_finite) {
    verdict = combine(verdict, Validity::NONFINITE);
  }
  if (*quote.bid_u6 <= 0 || *quote.ask_u6 <= 0) {
    verdict = combine(verdict, Validity::NONPOSITIVE);
  }
  if (*quote.bid_u6 == *quote.ask_u6) {
    verdict = combine(verdict, Validity::LOCKED);
  } else if (*quote.bid_u6 > *quote.ask_u6) {
    verdict = combine(verdict, Validity::CROSSED);
  }
  if ((quote.bid_condition.has_value() && !is_quote_condition_eligible(*quote.bid_condition)) ||
      (quote.ask_condition.has_value() && !is_quote_condition_eligible(*quote.ask_condition))) {
    verdict = combine(verdict, Validity::CONDITION_INELIGIBLE);
  }
  return verdict;
}

const char* trade_condition_class_name(TradeConditionClass value) noexcept {
  switch (value) {
    case TradeConditionClass::REGULAR:
      return "REGULAR";
    case TradeConditionClass::CANCEL:
      return "CANCEL";
    case TradeConditionClass::INELIGIBLE:
      return "INELIGIBLE";
  }
  return "UNKNOWN_TRADE_CONDITION_CLASS";
}

StockPrintEligibility classify_stock_print(const qr::sources::StockTradeRow& row) noexcept {
  using qr::sources::kTradeSlotCondition;
  using qr::sources::kTradeSlotExtCondition1;
  using qr::sources::kTradeSlotPrice;
  using qr::sources::kTradeSlotSize;

  StockPrintEligibility out;
  const bool condition_present = !row.is_null(kTradeSlotCondition);
  out.primary = condition_present ? classify_trade_condition(row.condition)
                                  : TradeConditionClass::INELIGIBLE;
  out.primary_nonzero = !condition_present || row.condition != 0;

  // CC-008: a present slot must carry an ADMITTED code ({0, 32}); 255 is the
  // absence sentinel; anything else disqualifies the print.
  bool extended_all_admitted = true;
  for (std::size_t slot = 0; slot < row.ext_condition.size(); ++slot) {
    const bool null_cell = row.is_null(kTradeSlotExtCondition1 + slot);
    if (null_cell || row.ext_condition[slot] == kExtendedConditionSentinel) {
      out.sentinel_absent = true;
      continue;
    }
    if (!is_extended_condition_admitted(row.ext_condition[slot])) {
      out.extended_nonzero = true;
      extended_all_admitted = false;
    }
  }

  out.nonpositive_size = row.is_null(kTradeSlotSize) || row.size <= 0;
  out.nonfinite_price = row.is_null(kTradeSlotPrice) || row.price_u6 <= 0;
  out.direction_eligible = out.primary == TradeConditionClass::REGULAR &&
                           extended_all_admitted && !out.nonpositive_size &&
                           !out.nonfinite_price;

  Validity verdict = Validity::VALID;
  if (out.primary != TradeConditionClass::REGULAR || !extended_all_admitted) {
    verdict = combine(verdict, Validity::CONDITION_INELIGIBLE);
  }
  if (row.is_null(kTradeSlotSize) || row.is_null(kTradeSlotPrice)) {
    verdict = combine(verdict, Validity::MISSING);
  }
  if ((!row.is_null(kTradeSlotSize) && row.size <= 0) ||
      (!row.is_null(kTradeSlotPrice) && row.price_u6 <= 0)) {
    verdict = combine(verdict, Validity::NONPOSITIVE);
  }
  out.directional_validity = verdict;
  return out;
}

void StockQualityLedger::fold(const StockPrintEligibility& verdict) noexcept {
  ++total;
  if (verdict.direction_eligible) {
    ++eligible;
  }
  if (verdict.primary_nonzero) {
    ++primary_nonzero;
  }
  if (verdict.extended_nonzero) {
    ++extended_nonzero;
  }
  if (verdict.primary == TradeConditionClass::CANCEL) {
    ++cancel_40_44;
  }
  if (verdict.sentinel_absent) {
    ++sentinel_absent;
  }
  if (verdict.nonpositive_size) {
    ++nonpositive_size;
  }
  if (verdict.nonfinite_price) {
    ++nonfinite_price;
  }
}

}  // namespace qr::carriers
