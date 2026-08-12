#include "qr_w21/contract_series.hpp"

#include <algorithm>
#include <charconv>
#include <utility>

namespace qr::w21 {
namespace {

constexpr const char* kParseSite = "qr::w21::parse_contract_id";

/// The three colon-separated fields of a contract spelling, or false when the
/// text does not carry exactly three.
bool split_three(std::string_view text, std::string_view& day, std::string_view& strike,
                 std::string_view& right) {
  const std::size_t first = text.find(':');
  if (first == std::string_view::npos) {
    return false;
  }
  const std::size_t second = text.find(':', first + 1);
  if (second == std::string_view::npos) {
    return false;
  }
  if (text.find(':', second + 1) != std::string_view::npos) {
    return false;
  }
  day = text.substr(0, first);
  strike = text.substr(first + 1, second - first - 1);
  right = text.substr(second + 1);
  return !day.empty() && !strike.empty() && !right.empty();
}

}  // namespace

ContractId contract_of(const qr::sources::OptionQuoteRow& row) noexcept {
  return ContractId{row.expiration_day, row.strike_u6, row.right};
}

Expected<ContractId, Refusal> parse_contract_id(std::string_view text) {
  std::string_view day;
  std::string_view strike_text;
  std::string_view right_text;
  if (!split_three(text, day, strike_text, right_text)) {
    return Expected<ContractId, Refusal>::refuse(
        Refusal(qr::RefusalCode::CONFIG, kParseSite,
                "a contract is spelled <YYYY-MM-DD>:<strike_u6>:<C|P>", 0));
  }

  const Expected<qr::CivilDate, Refusal> expiry = qr::CivilDate::parse_ymd(day);
  if (!expiry.has_value()) {
    return Expected<ContractId, Refusal>::refuse(expiry.error());
  }

  std::int64_t strike_u6 = 0;
  const char* const begin = strike_text.data();
  const char* const end = begin + strike_text.size();
  const std::from_chars_result parsed = std::from_chars(begin, end, strike_u6);
  if (parsed.ec != std::errc{} || parsed.ptr != end || strike_u6 <= 0) {
    return Expected<ContractId, Refusal>::refuse(
        Refusal(qr::RefusalCode::CONFIG, kParseSite,
                "the strike must be a positive integer in u6 (dollars x 1e6)", 0));
  }

  const qr::sources::Right right = qr::sources::parse_right(right_text);
  if (right == qr::sources::Right::Other) {
    // ON THE TAPE an unnamed right is a datum and stays `Other`. IN A CALLER'S
    // ARGUMENT it is a typo, and answering it with an empty series would look
    // like "this contract never quoted".
    return Expected<ContractId, Refusal>::refuse(
        Refusal(qr::RefusalCode::CONFIG, kParseSite,
                "the right must be one of C, CALL, P, PUT", 0));
  }

  return ContractId{static_cast<std::int32_t>(expiry.value().days_since_epoch()), strike_u6,
                    right};
}

std::string format_contract_id(const ContractId& id) {
  std::string out = qr::CivilDate(static_cast<std::int64_t>(id.expiration_day)).to_ymd();
  out += ':';
  out += std::to_string(id.strike_u6);
  out += ':';
  out += qr::sources::right_name(id.right);
  return out;
}

bool ContractQuote::mid_u6(std::int64_t& out) const noexcept {
  if (is_null(qr::sources::kOptionQuoteSlotBid) || is_null(qr::sources::kOptionQuoteSlotAsk)) {
    return false;
  }
  out = qr::sources::midpoint_u6(bid_u6, ask_u6);
  return true;
}

void ContractSeries::observe(std::int64_t second, std::int64_t ms,
                             const qr::sources::OptionQuoteRow& row) {
  if (!(contract_of(row) == id_)) {
    return;
  }
  ++session_rows_;
  if (second < from_second_ || second > to_second_) {
    return;
  }
  ContractQuote quote;
  quote.second = second;
  quote.ms = ms;
  quote.bid_u6 = row.bid_u6;
  quote.ask_u6 = row.ask_u6;
  quote.bid_size = row.bid_size;
  quote.ask_size = row.ask_size;
  quote.null_mask = row.null_mask;
  quotes_.push_back(quote);
}

void ActivityCensus::observe(std::int64_t second, std::int64_t ms,
                             const qr::sources::OptionQuoteRow& row) {
  if (second < from_second_ || second > to_second_) {
    return;
  }
  ++rows_;
  Tally& tally = seen_[contract_of(row)];
  if (!tally.started) {
    tally.started = true;
    tally.activity.id = contract_of(row);
    tally.activity.first_ms = ms;
    tally.activity.seconds_present = 1;
    tally.last_second = second;
  } else if (second != tally.last_second) {
    ++tally.activity.seconds_present;
    tally.last_second = second;
  }
  ++tally.activity.rows;
  tally.activity.last_ms = ms;
}

std::vector<ContractActivity> ActivityCensus::top(std::size_t k) const {
  std::vector<ContractActivity> all;
  all.reserve(seen_.size());
  for (const auto& [id, tally] : seen_) {
    all.push_back(tally.activity);
  }
  // The map already iterates in contract order, so a STABLE sort by row count
  // descending leaves ties in contract order — the total order the header
  // promises, with no second comparison to get wrong.
  std::stable_sort(all.begin(), all.end(),
                   [](const ContractActivity& left, const ContractActivity& right) {
                     return left.rows > right.rows;
                   });
  if (all.size() > k) {
    all.resize(k);
  }
  return all;
}

}  // namespace qr::w21
