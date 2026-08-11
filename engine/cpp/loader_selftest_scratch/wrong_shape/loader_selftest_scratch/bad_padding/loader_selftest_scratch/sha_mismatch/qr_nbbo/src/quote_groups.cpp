#include "qr_nbbo/quote_groups.hpp"

#include <array>

#include "qr_sources/session_source.hpp"

namespace qr::nbbo {
namespace {

constexpr const char* kMidSite = "qr_nbbo::GroupScalars::mid_u6";
constexpr const char* kSpreadSite = "qr_nbbo::GroupScalars::spread_u6";
constexpr const char* kImbalanceSite = "qr_nbbo::GroupScalars::imbalance";

constexpr std::array<std::uint32_t, kQualityFlagCount> kQualityFlagBits{
    QualityFlags::LOCKED,       QualityFlags::WIDE_SPREAD,
    QualityFlags::MIXED_REJECTED, QualityFlags::REJECTED_ONLY,
    QualityFlags::MIXED_SCIENTIFIC_WIDE, QualityFlags::WIDE_ONLY};

constexpr std::array<const char*, kQualityFlagCount> kQualityFlagNames{
    "LOCKED", "WIDE_SPREAD", "MIXED_REJECTED", "REJECTED_ONLY", "MIXED_SCIENTIFIC_WIDE",
    "WIDE_ONLY"};

}  // namespace

const char* quote_kind_name(QuoteKind kind) noexcept {
  switch (kind) {
    case QuoteKind::SINGLE_SCIENTIFIC:
      return "SINGLE_SCIENTIFIC";
    case QuoteKind::MULTI_SCIENTIFIC:
      return "MULTI_SCIENTIFIC";
    case QuoteKind::WIDE_ONLY:
      return "WIDE_ONLY";
    case QuoteKind::UNRESOLVED:
      return "UNRESOLVED";
  }
  return "UNKNOWN";
}

std::uint32_t quality_flag_at(std::size_t index) noexcept {
  return index < kQualityFlagBits.size() ? kQualityFlagBits[index] : 0U;
}

const char* quality_flag_name(std::size_t index) noexcept {
  return index < kQualityFlagNames.size() ? kQualityFlagNames[index] : "UNKNOWN";
}

// ---------------------------------------------------------------------------
// GroupScalars — derived only AFTER the separate scalar means.
// ---------------------------------------------------------------------------

Expected<Typed<std::int64_t>, Refusal> GroupScalars::mid_u6() const noexcept {
  // THE LAW (task card V4 section 4): the two scalar means come first, each
  // over its own primitive, and only then is the midpoint derived from them.
  // `mean of (bid_i + ask_i) / 2` is the named mutant, not this.
  const Typed<std::int64_t> mean_bid = bid_u6.mean();
  const Typed<std::int64_t> mean_ask = ask_u6.mean();
  const Validity combined = combine(mean_bid.v, mean_ask.v);
  if (combined != Validity::VALID) {
    return Typed<std::int64_t>{0, combined};
  }
  const Expected<std::int64_t, Refusal> total = checked_add(mean_bid.value, mean_ask.value);
  if (!total.has_value()) {
    return Expected<Typed<std::int64_t>, Refusal>::refuse(
        Refusal(RefusalCode::ARITHMETIC_OVERFLOW, kMidSite, "mean bid + mean ask overflowed"));
  }
  return Typed<std::int64_t>{total.value() / 2, Validity::VALID};
}

Expected<Typed<std::int64_t>, Refusal> GroupScalars::spread_u6() const noexcept {
  const Typed<std::int64_t> mean_bid = bid_u6.mean();
  const Typed<std::int64_t> mean_ask = ask_u6.mean();
  const Validity combined = combine(mean_bid.v, mean_ask.v);
  if (combined != Validity::VALID) {
    return Typed<std::int64_t>{0, combined};
  }
  const Expected<std::int64_t, Refusal> spread = checked_sub(mean_ask.value, mean_bid.value);
  if (!spread.has_value()) {
    return Expected<Typed<std::int64_t>, Refusal>::refuse(
        Refusal(RefusalCode::ARITHMETIC_OVERFLOW, kSpreadSite, "mean ask - mean bid overflowed"));
  }
  return Typed<std::int64_t>{spread.value(), Validity::VALID};
}

Expected<Typed<double>, Refusal> GroupScalars::imbalance() const noexcept {
  // CC-005. The two SIZE means come first, each over its own primitive; the
  // ratio is derived from them and never from per-row imbalances.
  const Typed<std::int64_t> mean_bid = bid_shares.mean();
  const Typed<std::int64_t> mean_ask = ask_shares.mean();
  const Validity combined = combine(mean_bid.v, mean_ask.v);
  if (combined != Validity::VALID) {
    return Typed<double>{0.0, combined};
  }
  const Expected<std::int64_t, Refusal> numerator = checked_sub(mean_bid.value, mean_ask.value);
  const Expected<std::int64_t, Refusal> denominator = checked_add(mean_bid.value, mean_ask.value);
  if (!numerator.has_value() || !denominator.has_value()) {
    return Expected<Typed<double>, Refusal>::refuse(Refusal(
        RefusalCode::ARITHMETIC_OVERFLOW, kImbalanceSite, "size mean sum or difference overflowed"));
  }
  // ZERO DENOMINATOR => TYPED MISSING (the ruling). An eligible member carries
  // a strictly positive size on both sides, so a valid group's denominator is
  // at least 2 — but the guard is code, not an assumption, and it is what
  // stands between a degenerate book and a NaN travelling downstream.
  if (denominator.value() == 0) {
    return Typed<double>{0.0, Validity::MISSING};
  }
  // One IEEE division of two exactly-representable integers, with
  // -ffp-contract=off: deterministic, and bounded by |numerator| <=
  // denominator for nonnegative means.
  return Typed<double>{static_cast<double>(numerator.value()) /
                           static_cast<double>(denominator.value()),
                       Validity::VALID};
}

// ---------------------------------------------------------------------------
// QuoteGroups.
// ---------------------------------------------------------------------------

void QuoteGroups::clear() {
  ts_ns.clear();
  raw_member_count.clear();
  structurally_valid_count.clear();
  scientific_member_count.clear();
  wide_member_count.clear();
  rejected_member_count.clear();
  has_locked_member.clear();
  kind.clear();
  quality.clear();
  scientific_midpoints_u6.clear();
  wide_midpoints_u6.clear();
  ts_ms_b.clear();
  group_validity.clear();
  mean_validity.clear();
  state_mask.clear();
  eligible_count.clear();
  bid_u6_sum.clear();
  ask_u6_sum.clear();
  bid_shares_sum.clear();
  ask_shares_sum.clear();
  mid_u6.clear();
  mid_change_u6.clear();
  mid_change_validity.clear();
  prior_ts_ns.clear();
  prior_validity.clear();
  // THE CSR INVARIANT: `size() + 1` offsets at every size, so the empty
  // projection is `{0}` and never `{}` (reader.rs:265-274 — a derived Default
  // built these one short on every real session).
  scientific_midpoint_offsets.assign(1, 0U);
  wide_midpoint_offsets.assign(1, 0U);
}

void QuoteGroups::reserve(std::size_t groups) {
  ts_ns.reserve(groups);
  raw_member_count.reserve(groups);
  structurally_valid_count.reserve(groups);
  scientific_member_count.reserve(groups);
  wide_member_count.reserve(groups);
  rejected_member_count.reserve(groups);
  has_locked_member.reserve(groups);
  kind.reserve(groups);
  quality.reserve(groups);
  scientific_midpoint_offsets.reserve(groups + 1);
  wide_midpoint_offsets.reserve(groups + 1);
  ts_ms_b.reserve(groups);
  group_validity.reserve(groups);
  mean_validity.reserve(groups);
  state_mask.reserve(groups);
  eligible_count.reserve(groups);
  bid_u6_sum.reserve(groups);
  ask_u6_sum.reserve(groups);
  bid_shares_sum.reserve(groups);
  ask_shares_sum.reserve(groups);
  mid_u6.reserve(groups);
  mid_change_u6.reserve(groups);
  mid_change_validity.reserve(groups);
  prior_ts_ns.reserve(groups);
  prior_validity.reserve(groups);
}

std::span<const std::int64_t> QuoteGroups::csr_slice(const std::vector<std::uint32_t>& offsets,
                                                     const std::vector<std::int64_t>& values,
                                                     std::size_t index) const {
  if (index + 1 >= offsets.size()) {
    detail::fail_fast("qr_nbbo::QuoteGroups CSR access out of range");
  }
  const std::size_t start = offsets[index];
  const std::size_t stop = offsets[index + 1];
  return std::span<const std::int64_t>(values.data() + start, stop - start);
}

std::span<const std::int64_t> QuoteGroups::scientific_midpoints(std::size_t index) const {
  return csr_slice(scientific_midpoint_offsets, scientific_midpoints_u6, index);
}

std::span<const std::int64_t> QuoteGroups::wide_midpoints(std::size_t index) const {
  return csr_slice(wide_midpoint_offsets, wide_midpoints_u6, index);
}

GroupScalars QuoteGroups::scalars(std::size_t index) const {
  if (index >= size()) {
    detail::fail_fast("qr_nbbo::QuoteGroups::scalars out of range");
  }
  GroupScalars out;
  const std::int64_t count = eligible_count[index];
  out.bid_u6 = ScalarMean{bid_u6_sum[index], count};
  out.ask_u6 = ScalarMean{ask_u6_sum[index], count};
  out.bid_shares = ScalarMean{bid_shares_sum[index], count};
  out.ask_shares = ScalarMean{ask_shares_sum[index], count};
  return out;
}

void QuoteGroups::append_serialized(std::size_t index, std::vector<std::uint8_t>& out) const {
  if (index >= size()) {
    detail::fail_fast("qr_nbbo::QuoteGroups::append_serialized out of range");
  }
  using qr::sources::append_i64;
  using qr::sources::append_u8;
  append_i64(ts_ns[index], out);
  append_i64(ts_ms_b[index], out);
  append_i64(static_cast<std::int64_t>(raw_member_count[index]), out);
  append_i64(static_cast<std::int64_t>(structurally_valid_count[index]), out);
  append_i64(static_cast<std::int64_t>(scientific_member_count[index]), out);
  append_i64(static_cast<std::int64_t>(wide_member_count[index]), out);
  append_i64(static_cast<std::int64_t>(rejected_member_count[index]), out);
  append_u8(has_locked_member[index], out);
  append_u8(static_cast<std::uint8_t>(kind[index]), out);
  append_i64(static_cast<std::int64_t>(quality[index].bits), out);
  append_u8(static_cast<std::uint8_t>(group_validity[index]), out);
  append_u8(static_cast<std::uint8_t>(mean_validity[index]), out);
  append_i64(static_cast<std::int64_t>(state_mask[index]), out);
  append_i64(eligible_count[index], out);
  append_i64(bid_u6_sum[index], out);
  append_i64(ask_u6_sum[index], out);
  append_i64(bid_shares_sum[index], out);
  append_i64(ask_shares_sum[index], out);
  append_i64(mid_u6[index], out);
  append_i64(mid_change_u6[index], out);
  append_u8(static_cast<std::uint8_t>(mid_change_validity[index]), out);
  append_i64(prior_ts_ns[index], out);
  append_u8(static_cast<std::uint8_t>(prior_validity[index]), out);
  const std::span<const std::int64_t> scientific = scientific_midpoints(index);
  append_i64(static_cast<std::int64_t>(scientific.size()), out);
  for (const std::int64_t value : scientific) {
    append_i64(value, out);
  }
  const std::span<const std::int64_t> wide = wide_midpoints(index);
  append_i64(static_cast<std::int64_t>(wide.size()), out);
  for (const std::int64_t value : wide) {
    append_i64(value, out);
  }
}

}  // namespace qr::nbbo
