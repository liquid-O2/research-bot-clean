#include "qr_sources/normalize.hpp"

#include <cmath>
#include <cstring>

namespace qr::sources {
namespace {

constexpr const char* kShareSite = "qr_sources::nbbo_size_to_shares";
constexpr const char* kDollarSite = "qr_sources::dollars_to_u6";
constexpr const char* kPriceSite = "qr_sources::price_to_u6";
constexpr const char* kTextSite = "qr_sources::inline_text";
constexpr const char* kDateSite = "qr_sources::date_to_day_ordinal";

/// The i64 range bound as a double, exactly as the reference spells it
/// (`mod.rs:388`): 2^63, which is representable, unlike i64::MAX.
constexpr double kI64Limit = 9'223'372'036'854'775'808.0;

}  // namespace

double round_ties_even(double value) noexcept {
  const double floor_value = std::floor(value);
  const double fraction = value - floor_value;
  if (fraction > 0.5) {
    return floor_value + 1.0;
  }
  if (fraction < 0.5) {
    return floor_value;
  }
  // Exactly halfway: pick the even neighbour.
  return (std::fmod(floor_value, 2.0) == 0.0) ? floor_value : floor_value + 1.0;
}

Expected<std::int64_t, Refusal> nbbo_size_to_shares(std::int64_t raw,
                                                    std::string_view day) noexcept {
  // A negative size is not a count; multiplying it would invent one. The
  // reference passes it through untouched (`stock_quotes.rs:262-272`).
  if (raw < 0) {
    return raw;
  }
  // ISO days compare lexicographically, so this IS chronological
  // (`reader.rs:1343-1351`).
  if (day >= kShareEraFirstDay) {
    return raw;
  }
  return checked_mul(raw, kSharesPerLot);
}

Expected<std::int64_t, Refusal> dollars_to_u6(double value) noexcept {
  const double scaled = value * static_cast<double>(kU6PerDollar);
  if (!std::isfinite(value) || !std::isfinite(scaled) || !(scaled >= -kI64Limit) ||
      !(scaled < kI64Limit)) {
    return refuse<std::int64_t>(Refusal(RefusalCode::CONTENT_MISMATCH, kDollarSite,
                                        "dollar price does not normalize to u6"));
  }
  return static_cast<std::int64_t>(round_ties_even(scaled));
}

Expected<std::int64_t, Refusal> price_to_u6(ColumnForm form, std::int64_t integer,
                                            double real) noexcept {
  switch (form) {
    case ColumnForm::CentI32:
    case ColumnForm::CentI64:
      return checked_mul(integer, kU6PerCent);
    case ColumnForm::MillI32:
      return checked_mul(integer, kU6PerMill);
    case ColumnForm::DollarF64:
      return dollars_to_u6(real);
    default:
      break;
  }
  return refuse<std::int64_t>(Refusal(RefusalCode::CONFIG, kPriceSite,
                                      "column form is not a price form",
                                      static_cast<std::int64_t>(form)));
}

const char* right_name(Right right) noexcept {
  switch (right) {
    case Right::Call: return "CALL";
    case Right::Put: return "PUT";
    case Right::Other: return "OTHER";
  }
  return "OTHER";
}

Right parse_right(std::string_view text) noexcept {
  if (text == "CALL" || text == "C" || text == "call") {
    return Right::Call;
  }
  if (text == "PUT" || text == "P" || text == "put") {
    return Right::Put;
  }
  return Right::Other;
}

Expected<InlineText, Refusal> inline_text(std::string_view text) noexcept {
  if (text.size() > kInlineTextCapacity) {
    return refuse<InlineText>(Refusal(RefusalCode::CONTENT_MISMATCH, kTextSite,
                                      "retained text is longer than the inline capacity",
                                      static_cast<std::int64_t>(text.size())));
  }
  InlineText out;
  out.size = static_cast<std::uint8_t>(text.size());
  if (!text.empty()) {
    std::memcpy(out.data.data(), text.data(), text.size());
  }
  return out;
}

Expected<std::int32_t, Refusal> date_to_day_ordinal(ColumnForm form, std::int64_t ordinal,
                                                    std::string_view text) noexcept {
  if (form == ColumnForm::DateI32) {
    return static_cast<std::int32_t>(ordinal);
  }
  if (form != ColumnForm::DateText) {
    return refuse<std::int32_t>(Refusal(RefusalCode::CONFIG, kDateSite,
                                        "column form is not a date form",
                                        static_cast<std::int64_t>(form)));
  }
  Expected<CivilDate, Refusal> parsed = CivilDate::parse_ymd(text);
  if (!parsed.has_value()) {
    return refuse<std::int32_t>(parsed.error());
  }
  const std::int64_t days = parsed.value().days_since_epoch();
  if (days < static_cast<std::int64_t>(INT32_MIN) || days > static_cast<std::int64_t>(INT32_MAX)) {
    return refuse<std::int32_t>(Refusal(RefusalCode::ARITHMETIC_OVERFLOW, kDateSite,
                                        "civil day does not fit a day ordinal", days));
  }
  return static_cast<std::int32_t>(days);
}

}  // namespace qr::sources
