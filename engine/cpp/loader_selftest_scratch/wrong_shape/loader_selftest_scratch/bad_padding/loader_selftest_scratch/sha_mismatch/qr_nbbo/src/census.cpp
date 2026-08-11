#include "qr_nbbo/census.hpp"

#include <array>
#include <string>

namespace qr::nbbo {
namespace {

constexpr std::array<const char*, kQuoteStateCount> kStateNames{
    "NORMAL", "LOCKED", "CROSSED", "BID_ONLY", "ASK_ONLY", "BOTH_SIDES_ABSENT", "INVALID"};

constexpr std::array<const char*, kQuoteDomainCount> kDomainNames{
    "PREMARKET", "RTH", "AFTER_HOURS", "OUTSIDE_DOMAIN", "WRONG_CIVIL_DAY", "MALFORMED", "MISSING"};

/// Present AND strictly positive — the reference filters both prices and both
/// sizes this way before the seven-way match (reader.rs:1550-1559).
[[nodiscard]] bool positive(const std::optional<std::int64_t>& value) noexcept {
  return value.has_value() && *value > 0;
}

/// The typed state of one price field (APPENDIX C1).
[[nodiscard]] Validity price_validity(const std::optional<std::int64_t>& value) noexcept {
  if (!value.has_value()) {
    return Validity::MISSING;
  }
  if (*value <= 0) {
    return Validity::NONPOSITIVE;
  }
  if (*value > kMaxNormalizedNbboPriceU6) {
    // Above the pinned sanity ceiling the number is not a price on this scale
    // at all — the reference calls the same condition "a corrupt or
    // misinterpreted price column" (reader.rs:51-53).
    return Validity::NONFINITE;
  }
  return Validity::VALID;
}

/// The typed state of one size field.
[[nodiscard]] Validity size_validity(const std::optional<std::int64_t>& value) noexcept {
  if (!value.has_value()) {
    return Validity::MISSING;
  }
  return *value > 0 ? Validity::VALID : Validity::NONPOSITIVE;
}

/// The typed state of one condition field. FINAL_PLAN APPENDIX B1:
/// "conditions(4/8)=eligibility code 0".
[[nodiscard]] Validity condition_validity(const std::optional<std::int64_t>& value) noexcept {
  if (!value.has_value()) {
    return Validity::MISSING;
  }
  return *value == 0 ? Validity::VALID : Validity::CONDITION_INELIGIBLE;
}

std::string tsv_row(std::string_view label, std::string_view metric, std::int64_t value) {
  std::string out(label);
  out += '\t';
  out += metric;
  out += '\t';
  out += std::to_string(value);
  out += '\n';
  return out;
}

}  // namespace

const char* quote_state_name(QuoteState state) noexcept {
  const std::size_t index = static_cast<std::size_t>(state);
  return index < kStateNames.size() ? kStateNames[index] : "UNKNOWN";
}

const char* quote_domain_name(QuoteDomain domain) noexcept {
  const std::size_t index = static_cast<std::size_t>(domain);
  return index < kDomainNames.size() ? kDomainNames[index] : "UNKNOWN";
}

// ---------------------------------------------------------------------------
// The seven-way census classifier (exact port of reader.rs:1193-1212).
// ---------------------------------------------------------------------------

QuoteState classify_quote_state(const MemberFields& fields, bool malformed) noexcept {
  if (malformed) {
    return QuoteState::INVALID;
  }
  const bool bid = positive(fields.bid_u6);
  const bool ask = positive(fields.ask_u6);
  const bool bid_size = positive(fields.bid_shares);
  const bool ask_size = positive(fields.ask_shares);

  // The reference's match arms, in the reference's order. Order is semantics
  // here: the fourth arm is reached only because the first three demand all
  // four fields, so a two-sided quote with a zero size lands on the final
  // catch-all (INVALID) rather than on BID_ONLY.
  if (bid && ask && bid_size && ask_size) {
    if (*fields.bid_u6 < *fields.ask_u6) {
      return QuoteState::NORMAL;
    }
    if (*fields.bid_u6 == *fields.ask_u6) {
      return QuoteState::LOCKED;
    }
    return QuoteState::CROSSED;
  }
  if (bid && !ask && bid_size) {
    return QuoteState::BID_ONLY;
  }
  if (!bid && ask && ask_size) {
    return QuoteState::ASK_ONLY;
  }
  if (!bid && !ask) {
    return QuoteState::BOTH_SIDES_ABSENT;
  }
  return QuoteState::INVALID;
}

// ---------------------------------------------------------------------------
// The typed C1 view.
// ---------------------------------------------------------------------------

Validity classify_member_validity(const MemberFields& fields) noexcept {
  const Validity bid = price_validity(fields.bid_u6);
  const Validity ask = price_validity(fields.ask_u6);
  Validity out = combine(bid, ask);
  out = combine(out, size_validity(fields.bid_shares));
  out = combine(out, size_validity(fields.ask_shares));
  out = combine(out, condition_validity(fields.bid_condition));
  out = combine(out, condition_validity(fields.ask_condition));

  const bool bid_ok = bid == Validity::VALID;
  const bool ask_ok = ask == Validity::VALID;
  if (bid_ok && ask_ok) {
    // ask > bid is the card's law; equality and inversion are typed quality
    // tokens, and the value they carry is masked by being non-VALID.
    if (*fields.bid_u6 == *fields.ask_u6) {
      out = combine(out, Validity::LOCKED);
    } else if (*fields.bid_u6 > *fields.ask_u6) {
      out = combine(out, Validity::CROSSED);
    }
  } else if (bid_ok || ask_ok) {
    out = combine(out, Validity::ONE_SIDED);
  }
  return out;
}

// ---------------------------------------------------------------------------
// The CSR structural predicate (exact port of reader.rs:632-639).
// ---------------------------------------------------------------------------

bool is_structurally_valid(const MemberFields& fields) noexcept {
  if (!fields.bid_u6.has_value() || !fields.ask_u6.has_value() ||
      !fields.bid_shares.has_value() || !fields.ask_shares.has_value() ||
      !fields.bid_condition.has_value() || !fields.ask_condition.has_value()) {
    return false;
  }
  const std::int64_t bid = *fields.bid_u6;
  const std::int64_t ask = *fields.ask_u6;
  // Every clause of the frozen expression, in the frozen order. Note the two
  // LOOSE ones: `ask >= bid` admits a LOCKED member, and the even-sum clause
  // rejects a member whose midpoint would not be an exact u6 integer.
  return *fields.bid_condition == 0 && *fields.ask_condition == 0 && *fields.bid_shares > 0 &&
         *fields.ask_shares > 0 && bid >= 1 && bid <= kMaxNormalizedNbboPriceU6 && ask >= 1 &&
         ask <= kMaxNormalizedNbboPriceU6 && ask >= bid && (bid + ask) % 2 == 0;
}

// ---------------------------------------------------------------------------
// The TOTALIZED domain classifier.
// ---------------------------------------------------------------------------

QuoteDomain classify_domain(const SessionClock& clock,
                            std::optional<std::int64_t> ts_ms_b) noexcept {
  // Step one is the clock's own TOTAL classifier — never
  // `to_frame_a_same_civil_day(..)?`, which is the abort shape the design
  // forbids copying (reader.rs:1173).
  const AttachClass attached = clock.classify_attach_ms(ts_ms_b);
  switch (attached.kind()) {
    case AttachKind::MISSING:
      return QuoteDomain::MISSING;
    case AttachKind::MALFORMED:
      return QuoteDomain::MALFORMED;
    case AttachKind::WRONG_CIVIL_DAY:
      return QuoteDomain::WRONG_CIVIL_DAY;
    case AttachKind::ON_DAY:
      break;
  }
  const Expected<FrameB, Refusal> ts_b = frame_b_from_naive_et_ms(*ts_ms_b);
  if (!ts_b.has_value()) {
    // Unreachable from an ON_DAY classification, and still totalized rather
    // than aborted.
    return QuoteDomain::MALFORMED;
  }

  // The reference's own window arithmetic (reader.rs:1174-1189), in frame B.
  const std::int64_t open_ns = clock.open_b().ns();
  const std::int64_t four_am = open_ns - ((5 * 60 * 60 + 30 * 60) * 1'000'000'000LL);
  // Ported literally, including the branch: on a 210-bar early close the
  // post-open boundary is the session's own close, otherwise open + 6h30m.
  // Both equal `close_b` for a well-formed row (close_b = open_b +
  // bar_count * 60s), and the branch is kept because the reference's is.
  const std::int64_t after_open = clock.expected_bar_count() == 210
                                      ? clock.close_b().ns()
                                      : open_ns + (6 * 60 * 60 + 30 * 60) * 1'000'000'000LL;
  const std::int64_t after_close = after_open + (4 * 60 * 60 * 1'000'000'000LL);
  const std::int64_t ns = ts_b.value().ns();
  if (ns >= four_am && ns < open_ns) {
    return QuoteDomain::PREMARKET;
  }
  if (clock.contains_b(ts_b.value())) {
    return QuoteDomain::RTH;
  }
  if (ns >= after_open && ns < after_close) {
    return QuoteDomain::AFTER_HOURS;
  }
  return QuoteDomain::OUTSIDE_DOMAIN;
}

// ---------------------------------------------------------------------------
// The census TSV.
// ---------------------------------------------------------------------------

std::string FullDayQuoteCensus::to_tsv(std::string_view label) const {
  std::string out;
  out += "label\tmetric\tvalue\n";
  out += tsv_row(label, "group_count", group_count);
  out += tsv_row(label, "rth_rows", rth_rows);
  out += tsv_row(label, "sentinel_rows", sentinel_rows);
  out += tsv_row(label, "multi_member_groups", multi_member_groups);
  out += tsv_row(label, "max_group_multiplicity", max_group_multiplicity);
  for (std::size_t index = 0; index < kQuoteDomainCount; ++index) {
    out += tsv_row(label, std::string("domain_rows.") +
                              quote_domain_name(static_cast<QuoteDomain>(index)),
                   domain_rows[index]);
  }
  for (std::size_t index = 0; index < kQuoteStateCount; ++index) {
    out += tsv_row(label,
                   std::string("state_rows.") + quote_state_name(static_cast<QuoteState>(index)),
                   state_rows[index]);
  }
  out += tsv_row(label, "structurally_valid_rows", structurally_valid_rows);
  out += tsv_row(label, "rejected_rows", rejected_rows);
  out += tsv_row(label, "scientific_rows", scientific_rows);
  out += tsv_row(label, "wide_rows", wide_rows);
  out += tsv_row(label, "groups_with_locked_member", groups_with_locked_member);
  for (std::size_t index = 0; index < kQuoteKindCount; ++index) {
    out += tsv_row(label,
                   std::string("kind_groups.") + quote_kind_name(static_cast<QuoteKind>(index)),
                   kind_groups[index]);
  }
  for (std::size_t index = 0; index < kQualityFlagCount; ++index) {
    out += tsv_row(label, std::string("quality_flag_groups.") + quality_flag_name(index),
                   quality_flag_groups[index]);
  }
  out += tsv_row(label, "scientific_midpoints", scientific_midpoints);
  out += tsv_row(label, "wide_midpoints", wide_midpoints);
  for (std::size_t index = 0; index < kValidityCount; ++index) {
    out += tsv_row(label, std::string("member_validity.") +
                              validity_name(static_cast<Validity>(index)),
                   member_validity[index]);
  }
  for (std::size_t index = 0; index < kValidityCount; ++index) {
    out += tsv_row(label, std::string("group_validity.") +
                              validity_name(static_cast<Validity>(index)),
                   group_validity[index]);
  }
  out += tsv_row(label, "eligible_rows", eligible_rows);
  out += tsv_row(label, "groups_without_eligible_member", groups_without_eligible_member);
  out += tsv_row(label, "groups_without_prior_state", groups_without_prior_state);
  out += tsv_row(label, "compact_rows", compact_rows);
  out += tsv_row(label, "wide_profile_rows", wide_profile_rows);
  return out;
}

}  // namespace qr::nbbo
