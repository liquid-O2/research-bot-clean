#include "qr_nbbo/group_machine.hpp"

#include <algorithm>
#include <optional>
#include <utility>

namespace qr::nbbo {
namespace {

constexpr const char* kClassifySite = "qr_nbbo::classify_member";
constexpr const char* kSpreadSite = "qr_nbbo::is_scientific_spread";
constexpr const char* kPushSite = "qr_nbbo::GroupMachine::push_group";
constexpr const char* kSealSite = "qr_nbbo::GroupMachine::seal";
constexpr const char* kRunSite = "qr_nbbo::run_session";

/// The reference's `increment` (reader.rs:391-396): a per-group counter that
/// refuses on overflow rather than wrapping.
[[nodiscard]] Expected<std::uint32_t, Refusal> increment(std::uint32_t counter,
                                                         const char* site) noexcept {
  std::uint32_t out = 0;
  if (__builtin_add_overflow(counter, 1U, &out)) {
    return Expected<std::uint32_t, Refusal>::refuse(
        Refusal(RefusalCode::ARITHMETIC_OVERFLOW, site, "group member counter overflowed"));
  }
  return out;
}

/// One row's fields as the classifiers read them: a slot that the tape left
/// null becomes `nullopt`, never a zero that could be mistaken for a price.
[[nodiscard]] MemberFields fields_of(const qr::sources::StockQuoteRow& row) noexcept {
  using namespace qr::sources;
  MemberFields fields;
  if (!row.is_null(kQuoteSlotBid)) {
    fields.bid_u6 = row.bid_u6;
  }
  if (!row.is_null(kQuoteSlotAsk)) {
    fields.ask_u6 = row.ask_u6;
  }
  if (!row.is_null(kQuoteSlotBidSize)) {
    fields.bid_shares = row.bid_shares;
  }
  if (!row.is_null(kQuoteSlotAskSize)) {
    fields.ask_shares = row.ask_shares;
  }
  if (!row.is_null(kQuoteSlotBidCondition)) {
    fields.bid_condition = row.bid_condition;
  }
  if (!row.is_null(kQuoteSlotAskCondition)) {
    fields.ask_condition = row.ask_condition;
  }
  return fields;
}

/// The reference's `invalid` flag (reader.rs:1560-1565): a field whose own
/// value is outside what the scale can mean. A negative size is one (the
/// reference's `size()` closure returns None for it), and a price below zero
/// or above the sanity ceiling is one.
[[nodiscard]] bool is_malformed(const MemberFields& fields) noexcept {
  const auto bad_price = [](const std::optional<std::int64_t>& value) {
    return value.has_value() && (*value < 0 || *value > kMaxNormalizedNbboPriceU6);
  };
  const auto bad_size = [](const std::optional<std::int64_t>& value) {
    return value.has_value() && *value < 0;
  };
  return bad_price(fields.bid_u6) || bad_price(fields.ask_u6) || bad_size(fields.bid_shares) ||
         bad_size(fields.ask_shares);
}

void sort_and_dedup(std::vector<std::int64_t>& values) {
  std::sort(values.begin(), values.end());
  values.erase(std::unique(values.begin(), values.end()), values.end());
}

}  // namespace

// ---------------------------------------------------------------------------
// Member classification.
// ---------------------------------------------------------------------------

Expected<bool, Refusal> is_scientific_spread(std::int64_t bid_u6, std::int64_t ask_u6) noexcept {
  // reader.rs:646-655, restated without division exactly as the reference
  // restates it: `spread / mid <= 50bps` becomes `spread * 20_000 <= 50 *
  // (bid + ask)`. The reference computes it in i128; this tree may not use the
  // `__int128` GNU extension, so every step is a CHECKED i64 operation
  // instead. Both prices are inside the u6 sanity ceiling (1e12) before this
  // is called, so `spread * 20_000 <= 4e16` and `50 * total <= 1e14`: the
  // checks cannot fire on admissible input, and they refuse rather than wrap
  // if they ever do.
  const Expected<std::int64_t, Refusal> total = checked_add(bid_u6, ask_u6);
  if (!total.has_value()) {
    return Expected<bool, Refusal>::refuse(
        Refusal(RefusalCode::ARITHMETIC_OVERFLOW, kSpreadSite, "bid + ask overflowed"));
  }
  const Expected<std::int64_t, Refusal> spread = checked_sub(ask_u6, bid_u6);
  if (!spread.has_value()) {
    return Expected<bool, Refusal>::refuse(
        Refusal(RefusalCode::ARITHMETIC_OVERFLOW, kSpreadSite, "ask - bid overflowed"));
  }
  const Expected<std::int64_t, Refusal> scaled_spread =
      checked_mul(spread.value(), kScientificSpreadScale);
  const Expected<std::int64_t, Refusal> scaled_total =
      checked_mul(kMaxScientificSpreadBps, total.value());
  if (!scaled_spread.has_value() || !scaled_total.has_value()) {
    return Expected<bool, Refusal>::refuse(
        Refusal(RefusalCode::ARITHMETIC_OVERFLOW, kSpreadSite, "spread bar scaling overflowed"));
  }
  return scaled_spread.value() <= scaled_total.value();
}

Expected<MemberClass, Refusal> classify_member(const qr::sources::StockQuoteRow& row) noexcept {
  const MemberFields fields = fields_of(row);
  MemberClass out;
  out.state = classify_quote_state(fields, is_malformed(fields));
  out.validity = classify_member_validity(fields);
  out.structurally_valid = is_structurally_valid(fields);
  if (!out.structurally_valid) {
    return out;
  }
  const std::int64_t bid = *fields.bid_u6;
  const std::int64_t ask = *fields.ask_u6;
  out.locked = bid == ask;
  const Expected<std::int64_t, Refusal> total = checked_add(bid, ask);
  if (!total.has_value()) {
    return Expected<MemberClass, Refusal>::refuse(
        Refusal(RefusalCode::ARITHMETIC_OVERFLOW, kClassifySite, "bid + ask overflowed"));
  }
  // The structural predicate already required an even sum, so this division is
  // exact — the midpoint of a structurally valid member is never rounded.
  out.midpoint_u6 = total.value() / 2;
  const Expected<bool, Refusal> scientific = is_scientific_spread(bid, ask);
  if (!scientific.has_value()) {
    return Expected<MemberClass, Refusal>::refuse(scientific.error());
  }
  out.scientific = scientific.value();
  return out;
}

// ---------------------------------------------------------------------------
// The machine.
// ---------------------------------------------------------------------------

Expected<GroupMachine, Refusal> GroupMachine::for_scope(const DayScope& scope) {
  Expected<SessionClock, Refusal> clock = SessionClock::from_session(scope.session());
  if (!clock.has_value()) {
    return Expected<GroupMachine, Refusal>::refuse(clock.error());
  }
  SessionPins pins;
  pins.day = scope.day();
  pins.profile = scope.profile();
  pins.raw_rth_row_count = scope.session().raw_rth_row_count;
  pins.complete_group_count = scope.session().complete_group_count;
  GroupMachine machine(std::move(clock).value(), std::move(pins));
  if (machine.pins_.complete_group_count > 0) {
    machine.groups_.reserve(static_cast<std::size_t>(machine.pins_.complete_group_count));
  }
  return machine;
}

GroupMachine GroupMachine::from_clock(SessionClock clock, SessionPins pins) {
  return GroupMachine(std::move(clock), std::move(pins));
}

Expected<std::int64_t, Refusal> GroupMachine::push_group(
    std::int64_t ts_ms_b, std::span<const qr::sources::StockQuoteRow> rows) {
  if (sealed_) {
    return Expected<std::int64_t, Refusal>::refuse(
        Refusal(RefusalCode::CONFIG, kPushSite, "the machine is sealed", ts_ms_b));
  }
  if (rows.empty()) {
    return Expected<std::int64_t, Refusal>::refuse(Refusal(
        RefusalCode::CONTENT_MISMATCH, kPushSite, "an equal-time group with no members", ts_ms_b));
  }
  // ONE GROUP PER MILLISECOND: a repeat of, or a descent below, the previous
  // group's stamp means the caller split an equal-time run — the exact hazard
  // the Validity lattice reserves EQUAL_TIME_UNORDERED for.
  if (has_last_ts_ && ts_ms_b <= last_ts_ms_b_) {
    return Expected<std::int64_t, Refusal>::refuse(
        Refusal(RefusalCode::OUT_OF_ORDER, kPushSite,
                "group timestamps must strictly increase (equal-time runs are ONE group)",
                ts_ms_b));
  }
  // THE REGISTRY IS A LIVE WALL, not just a final check (reader.rs:669-676).
  if (pins_.complete_group_count > 0 &&
      static_cast<std::int64_t>(groups_.size()) >= pins_.complete_group_count) {
    return Expected<std::int64_t, Refusal>::refuse(
        Refusal(RefusalCode::CONTENT_MISMATCH, kPushSite,
                "decoded more groups than the registry's complete_group_count", ts_ms_b));
  }
  for (const qr::sources::StockQuoteRow& row : rows) {
    if (row.ts_ms_b != ts_ms_b) {
      return Expected<std::int64_t, Refusal>::refuse(
          Refusal(RefusalCode::CONTENT_MISMATCH, kPushSite,
                  "a member does not carry its own group's millisecond", row.ts_ms_b));
    }
  }

  // The TOTALIZED domain classification (never the reference's `?`-abort).
  const QuoteDomain domain = classify_domain(clock_, ts_ms_b);
  if (domain != QuoteDomain::RTH) {
    // The stream this machine consumes is RTH-filtered in frame B by its
    // reader (APPENDIX B1). A non-RTH group arriving here means the reader and
    // the clock disagree, which is a refusal and never a silently dropped row.
    //
    // DEFENCE IN DEPTH, STATED HONESTLY: `to_frame_a` below would also refuse
    // this group, with the same OUTSIDE_RTH code, under the clock's boundary
    // condition 3. This check is not what makes the window safe — the clock
    // is — but it types the disagreement at the group grain and keeps the
    // census's domain histogram provably RTH-only.
    return Expected<std::int64_t, Refusal>::refuse(
        Refusal(RefusalCode::OUTSIDE_RTH, kPushSite,
                "a non-RTH group reached the group machine", ts_ms_b));
  }
  // THE SOLE FRAME-B -> FRAME-A CONVERSION, through the one clock authority,
  // which re-checks boundary conditions 3, 4 and 5 (reader.rs:677-683).
  const Expected<FrameB, Refusal> ts_b = frame_b_from_naive_et_ms(ts_ms_b);
  if (!ts_b.has_value()) {
    return Expected<std::int64_t, Refusal>::refuse(ts_b.error());
  }
  const Expected<FrameA, Refusal> ts_a = clock_.to_frame_a(ts_b.value());
  if (!ts_a.has_value()) {
    return Expected<std::int64_t, Refusal>::refuse(ts_a.error());
  }

  // --- THE PRIOR IS FROZEN HERE -------------------------------------------
  // Everything below compares against this snapshot, and `prior_` itself is
  // not touched until the whole group has been reduced.
  const PriorGroupState frozen_prior = prior_;

  scientific_scratch_.clear();
  wide_scratch_.clear();
  std::uint32_t raw_members = 0;
  std::uint32_t structurally_valid = 0;
  std::uint32_t scientific_members = 0;
  std::uint32_t wide_members = 0;
  std::uint32_t rejected_members = 0;
  bool has_locked = false;
  std::uint16_t state_bits = 0;
  Validity group_validity = Validity::VALID;
  GroupScalars scalars;

  for (const qr::sources::StockQuoteRow& row : rows) {
    const Expected<MemberClass, Refusal> classified = classify_member(row);
    if (!classified.has_value()) {
      return Expected<std::int64_t, Refusal>::refuse(classified.error());
    }
    const MemberClass& member = classified.value();

    // --- the census views ---------------------------------------------------
    // i64 counters, incremented exactly as the reference increments its census
    // (reader.rs:1616-1635): a count that would need 9.2e18 rows to overflow.
    census_.state_rows[static_cast<std::size_t>(member.state)] += 1;
    census_.member_validity[static_cast<std::size_t>(member.validity)] += 1;
    census_.domain_rows[static_cast<std::size_t>(domain)] += 1;
    if (pins_.profile == SourceProfile::CentInt32) {
      census_.compact_rows += 1;
    } else {
      census_.wide_profile_rows += 1;
    }
    state_bits = static_cast<std::uint16_t>(
        state_bits | static_cast<std::uint16_t>(1U << static_cast<unsigned>(member.state)));
    group_validity = combine(group_validity, member.validity);

    // --- the CSR view (exact port of add_member) ---------------------------
    const Expected<std::uint32_t, Refusal> raw_next = increment(raw_members, kPushSite);
    if (!raw_next.has_value()) {
      return Expected<std::int64_t, Refusal>::refuse(raw_next.error());
    }
    raw_members = raw_next.value();
    if (!member.structurally_valid) {
      const Expected<std::uint32_t, Refusal> next = increment(rejected_members, kPushSite);
      if (!next.has_value()) {
        return Expected<std::int64_t, Refusal>::refuse(next.error());
      }
      rejected_members = next.value();
    } else {
      const Expected<std::uint32_t, Refusal> next = increment(structurally_valid, kPushSite);
      if (!next.has_value()) {
        return Expected<std::int64_t, Refusal>::refuse(next.error());
      }
      structurally_valid = next.value();
      has_locked = has_locked || member.locked;
      if (member.scientific) {
        const Expected<std::uint32_t, Refusal> bump = increment(scientific_members, kPushSite);
        if (!bump.has_value()) {
          return Expected<std::int64_t, Refusal>::refuse(bump.error());
        }
        scientific_members = bump.value();
        scientific_scratch_.push_back(member.midpoint_u6);
      } else {
        const Expected<std::uint32_t, Refusal> bump = increment(wide_members, kPushSite);
        if (!bump.has_value()) {
          return Expected<std::int64_t, Refusal>::refuse(bump.error());
        }
        wide_members = bump.value();
        wide_scratch_.push_back(member.midpoint_u6);
      }
    }

    // --- THE SEPARATE SCALAR MEANS (task card V4 section 4) ----------------
    // Only ELIGIBLE members (finite, positive, ask > bid, conditions code 0)
    // enter the primitive sums. Each primitive is summed on its OWN, exactly,
    // and nothing derived is summed here: the midpoint is computed from the
    // means afterwards, never averaged across rows.
    if (member.validity == Validity::VALID) {
      const std::array<std::pair<ScalarMean*, std::int64_t>, 4> additions{
          std::pair<ScalarMean*, std::int64_t>{&scalars.bid_u6, row.bid_u6},
          std::pair<ScalarMean*, std::int64_t>{&scalars.ask_u6, row.ask_u6},
          std::pair<ScalarMean*, std::int64_t>{&scalars.bid_shares, row.bid_shares},
          std::pair<ScalarMean*, std::int64_t>{&scalars.ask_shares, row.ask_shares}};
      for (const auto& [accumulator, value] : additions) {
        const Expected<std::int64_t, Refusal> sum = checked_add(accumulator->sum, value);
        if (!sum.has_value()) {
          return Expected<std::int64_t, Refusal>::refuse(sum.error());
        }
        accumulator->sum = sum.value();
        accumulator->count += 1;
      }
    }
  }

  // --- seal the group (exact port of push_pending_group) --------------------
  sort_and_dedup(scientific_scratch_);
  sort_and_dedup(wide_scratch_);

  QuoteKind kind = QuoteKind::UNRESOLVED;
  if (scientific_scratch_.size() == 1) {
    kind = QuoteKind::SINGLE_SCIENTIFIC;
  } else if (scientific_scratch_.size() > 1) {
    kind = QuoteKind::MULTI_SCIENTIFIC;
  } else if (wide_members > 0) {
    kind = QuoteKind::WIDE_ONLY;
  }

  QualityFlags quality;
  quality.bits |= has_locked ? QualityFlags::LOCKED : 0U;
  quality.bits |= wide_members > 0 ? QualityFlags::WIDE_SPREAD : 0U;
  quality.bits |=
      (structurally_valid > 0 && rejected_members > 0) ? QualityFlags::MIXED_REJECTED : 0U;
  quality.bits |=
      (structurally_valid == 0 && rejected_members > 0) ? QualityFlags::REJECTED_ONLY : 0U;
  quality.bits |= (scientific_members > 0 && wide_members > 0) ? QualityFlags::MIXED_SCIENTIFIC_WIDE
                                                              : 0U;
  quality.bits |= (scientific_members == 0 && wide_members > 0) ? QualityFlags::WIDE_ONLY : 0U;

  const Expected<Typed<std::int64_t>, Refusal> mid = scalars.mid_u6();
  if (!mid.has_value()) {
    return Expected<std::int64_t, Refusal>::refuse(mid.error());
  }
  // The change is derived from the two midpoints, each of which was itself
  // derived after its own group's scalar means. An absent eligible prior
  // group yields MISSING — never a zero that would read as "no move".
  Typed<std::int64_t> mid_change{0, Validity::MISSING};
  if (mid.value().v == Validity::VALID && frozen_prior.present) {
    const Expected<Typed<std::int64_t>, Refusal> prior_mid = frozen_prior.scalars.mid_u6();
    if (!prior_mid.has_value()) {
      return Expected<std::int64_t, Refusal>::refuse(prior_mid.error());
    }
    if (prior_mid.value().v == Validity::VALID) {
      const Expected<std::int64_t, Refusal> change =
          checked_sub(mid.value().value, prior_mid.value().value);
      if (!change.has_value()) {
        return Expected<std::int64_t, Refusal>::refuse(change.error());
      }
      mid_change = Typed<std::int64_t>{change.value(), Validity::VALID};
    }
  }

  groups_.ts_ns.push_back(ts_a.value().ns());
  groups_.ts_ms_b.push_back(ts_ms_b);
  groups_.raw_member_count.push_back(raw_members);
  groups_.structurally_valid_count.push_back(structurally_valid);
  groups_.scientific_member_count.push_back(scientific_members);
  groups_.wide_member_count.push_back(wide_members);
  groups_.rejected_member_count.push_back(rejected_members);
  groups_.has_locked_member.push_back(has_locked ? 1U : 0U);
  groups_.kind.push_back(kind);
  groups_.quality.push_back(quality);
  groups_.scientific_midpoints_u6.insert(groups_.scientific_midpoints_u6.end(),
                                         scientific_scratch_.begin(), scientific_scratch_.end());
  groups_.wide_midpoints_u6.insert(groups_.wide_midpoints_u6.end(), wide_scratch_.begin(),
                                   wide_scratch_.end());
  if (groups_.scientific_midpoints_u6.size() > UINT32_MAX ||
      groups_.wide_midpoints_u6.size() > UINT32_MAX) {
    return Expected<std::int64_t, Refusal>::refuse(Refusal(
        RefusalCode::ARITHMETIC_OVERFLOW, kPushSite, "CSR offsets no longer fit in u32", ts_ms_b));
  }
  groups_.scientific_midpoint_offsets.push_back(
      static_cast<std::uint32_t>(groups_.scientific_midpoints_u6.size()));
  groups_.wide_midpoint_offsets.push_back(
      static_cast<std::uint32_t>(groups_.wide_midpoints_u6.size()));
  groups_.group_validity.push_back(group_validity);
  groups_.mean_validity.push_back(mid.value().v);
  groups_.state_mask.push_back(state_bits);
  groups_.eligible_count.push_back(scalars.eligible_count());
  groups_.bid_u6_sum.push_back(scalars.bid_u6.sum);
  groups_.ask_u6_sum.push_back(scalars.ask_u6.sum);
  groups_.bid_shares_sum.push_back(scalars.bid_shares.sum);
  groups_.ask_shares_sum.push_back(scalars.ask_shares.sum);
  groups_.mid_u6.push_back(mid.value().value);
  groups_.mid_change_u6.push_back(mid_change.value);
  groups_.mid_change_validity.push_back(mid_change.v);
  groups_.prior_ts_ns.push_back(frozen_prior.ts_ns_a);
  groups_.prior_validity.push_back(frozen_prior.validity());

  // --- the census, at group grain ------------------------------------------
  const std::int64_t members = static_cast<std::int64_t>(rows.size());
  census_.rth_rows += members;
  census_.structurally_valid_rows += structurally_valid;
  census_.rejected_rows += rejected_members;
  census_.scientific_rows += scientific_members;
  census_.wide_rows += wide_members;
  census_.groups_with_locked_member += has_locked ? 1 : 0;
  census_.kind_groups[static_cast<std::size_t>(kind)] += 1;
  for (std::size_t flag = 0; flag < kQualityFlagCount; ++flag) {
    census_.quality_flag_groups[flag] += quality.contains(quality_flag_at(flag)) ? 1 : 0;
  }
  census_.scientific_midpoints += static_cast<std::int64_t>(scientific_scratch_.size());
  census_.wide_midpoints += static_cast<std::int64_t>(wide_scratch_.size());
  census_.group_validity[static_cast<std::size_t>(group_validity)] += 1;
  census_.eligible_rows += scalars.eligible_count();
  census_.groups_without_eligible_member += scalars.eligible_count() == 0 ? 1 : 0;
  census_.groups_without_prior_state += frozen_prior.present ? 0 : 1;
  census_.multi_member_groups += members > 1 ? 1 : 0;
  census_.max_group_multiplicity = std::max(census_.max_group_multiplicity, members);

  // --- ONLY NOW does the prior move ---------------------------------------
  // "only after the whole current group is reduced does its eligible finite
  // mean replace the prior state" — and a group with no eligible member never
  // becomes the prior, because the law names the nearest strictly-earlier
  // ELIGIBLE group.
  if (scalars.eligible_count() > 0) {
    prior_.present = true;
    prior_.ts_ms_b = ts_ms_b;
    prior_.ts_ns_a = ts_a.value().ns();
    prior_.scalars = scalars;
  }
  last_ts_ms_b_ = ts_ms_b;
  has_last_ts_ = true;
  return static_cast<std::int64_t>(groups_.size()) - 1;
}

Expected<std::int64_t, Refusal> GroupMachine::seal(std::int64_t sentinel_rows) {
  if (sealed_) {
    return Expected<std::int64_t, Refusal>::refuse(
        Refusal(RefusalCode::CONFIG, kSealSite, "the machine is already sealed"));
  }
  census_.sentinel_rows = sentinel_rows;
  census_.group_count = static_cast<std::int64_t>(groups_.size());
  // THE REGISTRY ORACLE (FINAL_PLAN section 6, correctness oracle 2), as the
  // reference's own FULL_DAY_LEGACY_COUNTS seal (reader.rs:1729-1738): two
  // numbers signed into the frozen registry, reproduced here by a stateful
  // machine that shares no code with the decoder that produced them.
  if (census_.rth_rows != pins_.raw_rth_row_count) {
    return Expected<std::int64_t, Refusal>::refuse(
        Refusal(RefusalCode::CONTENT_MISMATCH, kSealSite,
                "retained RTH rows disagree with the registry's raw_rth_row_count",
                census_.rth_rows));
  }
  if (census_.group_count != pins_.complete_group_count) {
    return Expected<std::int64_t, Refusal>::refuse(
        Refusal(RefusalCode::CONTENT_MISMATCH, kSealSite,
                "group count disagrees with the registry's complete_group_count",
                census_.group_count));
  }
  sealed_ = true;
  return census_.group_count;
}

std::vector<std::uint8_t> GroupMachine::serialize() const {
  std::vector<std::uint8_t> out;
  for (std::size_t index = 0; index < groups_.size(); ++index) {
    groups_.append_serialized(index, out);
  }
  return out;
}

qr::parquet::FileExpected<GroupMachine> run_session(qr::sources::StockQuoteReader& reader,
                                                    const DayScope& scope) {
  const std::string path = reader.path().string();
  Expected<GroupMachine, Refusal> created = GroupMachine::for_scope(scope);
  if (!created.has_value()) {
    return qr::parquet::FileExpected<GroupMachine>::refuse(
        qr::parquet::FileRefusal(created.error(), path, scope.day()));
  }
  GroupMachine machine = std::move(created).value();
  qr::sources::StockQuoteReader::Group group;
  while (true) {
    const qr::parquet::FileExpected<bool> more = reader.next_group(group);
    if (!more.has_value()) {
      return qr::parquet::FileExpected<GroupMachine>::refuse(more.error());
    }
    if (!more.value()) {
      break;
    }
    const Expected<std::int64_t, Refusal> pushed = machine.push_group(group.ts_ms_b, group.rows);
    if (!pushed.has_value()) {
      return qr::parquet::FileExpected<GroupMachine>::refuse(
          qr::parquet::FileRefusal(pushed.error(), path, scope.day()));
    }
  }
  const Expected<std::int64_t, Refusal> sealed = machine.seal(reader.sentinel_rows());
  if (!sealed.has_value()) {
    return qr::parquet::FileExpected<GroupMachine>::refuse(
        qr::parquet::FileRefusal(sealed.error(), path, kRunSite));
  }
  return machine;
}

}  // namespace qr::nbbo
