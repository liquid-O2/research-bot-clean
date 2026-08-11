#include "qr_candidates/roster.hpp"

#include <algorithm>
#include <cstdio>

#include "qr_candidates/parse.hpp"

namespace qr::candidates {
namespace {

constexpr const char* kSite = "qr_candidates::build_session_roster";
constexpr std::string_view kCandidateRowKind = "CANDIDATE";
/// A policy that IS primitive, used only where `classify_admission` is asked
/// nothing but the row_kind question (the CANDIDATE-row filter): passing a
/// nonprimitive name there would answer a question that was not being asked.
constexpr std::string_view kPrimitiveProbePolicy = "dc001";
constexpr std::string_view kUnionPolicy = "UNION";

/// One row of a candidate-id index into a decoded row group.
struct KeyedRow {
  std::string_view candidate_id;
  std::int64_t row = 0;
};

/// Builds the ascending candidate-id index of the CANDIDATE rows of a decoded
/// row group. Sorted, never hashed: the order is an output and unordered
/// containers are banned on output paths.
[[nodiscard]] Expected<std::vector<KeyedRow>, Refusal> index_candidate_rows(
    const SessionColumns& columns, std::size_t row_kind_column, std::size_t candidate_id_column,
    std::uint64_t& candidate_rows, std::uint64_t& duplicates, const char* what) {
  std::vector<KeyedRow> index;
  index.reserve(static_cast<std::size_t>(columns.num_rows()));
  for (std::int64_t row = 0; row < columns.num_rows(); ++row) {
    if (columns.is_null(row_kind_column, row)) {
      return refuse<std::vector<KeyedRow>>(
          Refusal(RefusalCode::DECODE_FAILED, kSite, "row_kind is null", row));
    }
    if (classify_admission(columns.value(row_kind_column, row), kPrimitiveProbePolicy, true,
                           true) == AdmissionClass::NOT_A_CANDIDATE_ROW) {
      continue;
    }
    candidate_rows += 1;
    if (columns.is_null(candidate_id_column, row)) {
      return refuse<std::vector<KeyedRow>>(
          Refusal(RefusalCode::DECODE_FAILED, kSite, "candidate_id is null on a CANDIDATE row", row));
    }
    index.push_back(KeyedRow{columns.value(candidate_id_column, row), row});
  }
  std::sort(index.begin(), index.end(),
            [](const KeyedRow& lhs, const KeyedRow& rhs) { return lhs.candidate_id < rhs.candidate_id; });
  for (std::size_t i = 1; i < index.size(); ++i) {
    if (index[i - 1].candidate_id == index[i].candidate_id) {
      duplicates += 1;
      return refuse<std::vector<KeyedRow>>(Refusal(RefusalCode::CONTENT_MISMATCH, kSite,
                                                   what, index[i].row));
    }
  }
  return index;
}

[[nodiscard]] const KeyedRow* find_row(const std::vector<KeyedRow>& index,
                                       std::string_view candidate_id) noexcept {
  const auto at = std::lower_bound(
      index.begin(), index.end(), candidate_id,
      [](const KeyedRow& row, std::string_view key) { return row.candidate_id < key; });
  if (at == index.end() || at->candidate_id != candidate_id) {
    return nullptr;
  }
  return &*at;
}

/// Resolves one allowlisted column position, refusing by name if it is absent.
[[nodiscard]] Expected<std::size_t, Refusal> column_of(const SessionColumns& columns,
                                                       std::string_view name) {
  const auto index = columns.column(name);
  if (!index) {
    return refuse<std::size_t>(Refusal(RefusalCode::SCHEMA_MISMATCH, kSite,
                                       "a required projected column is absent",
                                       static_cast<std::int64_t>(name.size())));
  }
  return index.value();
}

void append_u64(std::string& out, std::uint64_t value) {
  char scratch[32];
  std::snprintf(scratch, sizeof(scratch), "%llu", static_cast<unsigned long long>(value));
  out += scratch;
}

void append_i64(std::string& out, std::int64_t value) {
  char scratch[32];
  std::snprintf(scratch, sizeof(scratch), "%lld", static_cast<long long>(value));
  out += scratch;
}

}  // namespace

bool is_primitive_policy(std::string_view name) noexcept {
  for (const std::string_view policy : kPrimitivePolicies) {
    if (policy == name) {
      return true;
    }
  }
  return false;
}

AdmissionClass classify_admission(std::string_view row_kind, std::string_view policy_name,
                                  bool event_scorable, bool has_own_visibility) noexcept {
  if (row_kind != kCandidateRowKind) {
    return AdmissionClass::NOT_A_CANDIDATE_ROW;
  }
  if (!is_primitive_policy(policy_name)) {
    // UNION and every unknown policy: "typed census only ... creates no watch,
    // action, prefix membership, feature, sampler, denominator, fit or score".
    return AdmissionClass::NONPRIMITIVE_CENSUS_ONLY;
  }
  if (!event_scorable || !has_own_visibility) {
    return AdmissionClass::PRIMITIVE_NOT_ADMITTED;
  }
  return AdmissionClass::ADMITTED_PRIMITIVE;
}

const char* admission_class_name(AdmissionClass value) noexcept {
  switch (value) {
    case AdmissionClass::NOT_A_CANDIDATE_ROW:
      return "NOT_A_CANDIDATE_ROW";
    case AdmissionClass::ADMITTED_PRIMITIVE:
      return "ADMITTED_PRIMITIVE";
    case AdmissionClass::PRIMITIVE_NOT_ADMITTED:
      return "PRIMITIVE_NOT_ADMITTED";
    case AdmissionClass::NONPRIMITIVE_CENSUS_ONLY:
      return "NONPRIMITIVE_CENSUS_ONLY";
  }
  return "UNKNOWN";
}

const char* side_state_name(SideState value) noexcept {
  switch (value) {
    case SideState::LONG:
      return "LONG";
    case SideState::SHORT:
      return "SHORT";
    case SideState::SIDE_UNAVAILABLE:
      return "SIDE_UNAVAILABLE";
  }
  return "UNKNOWN";
}

const char* side_unavailable_cause_name(SideUnavailableCause value) noexcept {
  switch (value) {
    case SideUnavailableCause::NONE:
      return "NONE";
    case SideUnavailableCause::MEMBER_UNRESOLVED:
      return "MEMBER_UNRESOLVED";
    case SideUnavailableCause::MIXED_MEMBER_SIDE:
      return "MIXED_MEMBER_SIDE";
    case SideUnavailableCause::MEMBER_POLICY_OR_REVERSAL_MISMATCH:
      return "MEMBER_POLICY_OR_REVERSAL_MISMATCH";
    case SideUnavailableCause::MEMBER_VISIBILITY_IN_FUTURE:
      return "MEMBER_VISIBILITY_IN_FUTURE";
  }
  return "UNKNOWN";
}

Expected<std::vector<std::string_view>, Refusal> parse_member_signal_ids(std::string_view cell) {
  constexpr const char* kParseSite = "qr_candidates::parse_member_signal_ids";
  if (cell.empty()) {
    return refuse<std::vector<std::string_view>>(
        Refusal(RefusalCode::DECODE_FAILED, kParseSite, "member_signal_ids is empty"));
  }
  std::vector<std::string_view> ids;
  std::size_t at = 0;
  while (true) {
    const std::size_t comma = cell.find(',', at);
    const std::string_view token =
        cell.substr(at, comma == std::string_view::npos ? std::string_view::npos : comma - at);
    if (token.empty()) {
      return refuse<std::vector<std::string_view>>(Refusal(
          RefusalCode::DECODE_FAILED, kParseSite, "member_signal_ids has an empty token",
          static_cast<std::int64_t>(ids.size())));
    }
    if (!is_canonical_digest_hex(token)) {
      // Covers uppercase hex, wrong length, and any whitespace byte: none of
      // them is a lowercase 64-hex digit.
      return refuse<std::vector<std::string_view>>(Refusal(
          RefusalCode::DECODE_FAILED, kParseSite,
          "member id is not a canonical lowercase 64-hex digest",
          static_cast<std::int64_t>(ids.size())));
    }
    if (!ids.empty()) {
      if (token == ids.back()) {
        return refuse<std::vector<std::string_view>>(
            Refusal(RefusalCode::CONTENT_MISMATCH, kParseSite, "member_signal_ids repeats an id",
                    static_cast<std::int64_t>(ids.size())));
      }
      if (token < ids.back()) {
        return refuse<std::vector<std::string_view>>(
            Refusal(RefusalCode::OUT_OF_ORDER, kParseSite,
                    "member_signal_ids is not in ascending lexicographic order",
                    static_cast<std::int64_t>(ids.size())));
      }
    }
    ids.push_back(token);
    if (comma == std::string_view::npos) {
      break;
    }
    at = comma + 1;
  }
  return ids;
}

Expected<SessionRoster, Refusal> build_session_roster(std::uint32_t ordinal,
                                                      const SessionColumns& registry,
                                                      const SessionColumns& projection,
                                                      const SessionSignals& signals) {
  if (ordinal > kMaxSessionOrdinal) {
    return refuse<SessionRoster>(Refusal(RefusalCode::ORDINAL_OUTSIDE_SCOPE, kSite,
                                         "session ordinal is past the 749 wall",
                                         static_cast<std::int64_t>(ordinal)));
  }
  if (registry.ordinal() != ordinal || projection.ordinal() != ordinal ||
      signals.ordinal() != ordinal) {
    return refuse<SessionRoster>(Refusal(RefusalCode::CONTENT_MISMATCH, kSite,
                                         "the three authorities are not the same session",
                                         static_cast<std::int64_t>(ordinal)));
  }
  if (registry.day() != projection.day()) {
    return refuse<SessionRoster>(Refusal(RefusalCode::WRONG_CIVIL_DAY, kSite,
                                         "registry and projection disagree on the civil day",
                                         static_cast<std::int64_t>(ordinal)));
  }

  // --- column positions ------------------------------------------------------
  const auto reg_row_kind = column_of(registry, "row_kind");
  const auto reg_candidate_id = column_of(registry, "candidate_id");
  const auto reg_policy = column_of(registry, "stream_policy_name");
  const auto reg_reversal = column_of(registry, "stream_reversal_bps");
  const auto reg_members = column_of(registry, "member_signal_ids");
  const auto reg_member_count = column_of(registry, "member_count");
  const auto reg_visible = column_of(registry, "visible_ts_ns");
  const auto reg_scorable = column_of(registry, "event_scorable");
  const auto reg_session = column_of(registry, "session_ordinal");
  const auto raw_row_kind = column_of(projection, "row_kind");
  const auto raw_candidate_id = column_of(projection, "candidate_id");
  const auto raw_policy = column_of(projection, "stream_policy_name");
  const auto raw_reversal = column_of(projection, "stream_reversal_bps");
  const auto raw_members = column_of(projection, "member_signal_ids");
  const auto raw_visible = column_of(projection, "visible_ts_ns");
  const auto raw_physical = column_of(projection, "physical_event_id");
  for (const auto* step : {&reg_row_kind, &reg_candidate_id, &reg_policy, &reg_reversal,
                           &reg_members, &reg_member_count, &reg_visible, &reg_scorable,
                           &reg_session, &raw_row_kind, &raw_candidate_id, &raw_policy,
                           &raw_reversal, &raw_members, &raw_visible, &raw_physical}) {
    if (!*step) {
      return refuse<SessionRoster>(step->error());
    }
  }

  SessionRoster roster;
  roster.session_ordinal = ordinal;
  roster.day = registry.day();
  roster.census.registry_row_group_rows = static_cast<std::uint64_t>(registry.num_rows());
  roster.census.projection_rows = static_cast<std::uint64_t>(projection.num_rows());

  // --- the raw side of the exact join ---------------------------------------
  const auto raw_index =
      index_candidate_rows(projection, raw_row_kind.value(), raw_candidate_id.value(),
                           roster.census.projection_candidate_rows,
                           roster.census.duplicate_candidate_ids,
                           "the raw projection carries two CANDIDATE rows with one candidate_id");
  if (!raw_index) {
    return refuse<SessionRoster>(raw_index.error());
  }
  const auto registry_index =
      index_candidate_rows(registry, reg_row_kind.value(), reg_candidate_id.value(),
                           roster.census.registry_candidate_rows,
                           roster.census.duplicate_candidate_ids,
                           "the candidate registry repeats a candidate_id in one session");
  if (!registry_index) {
    return refuse<SessionRoster>(registry_index.error());
  }

  roster.candidates.reserve(registry_index.value().size());
  for (const KeyedRow& keyed : registry_index.value()) {
    const std::int64_t row = keyed.row;
    // The registry states its own session ordinal; it must be this one.
    if (registry.is_null(reg_session.value(), row)) {
      return refuse<SessionRoster>(
          Refusal(RefusalCode::DECODE_FAILED, kSite, "session_ordinal is null", row));
    }
    const auto declared_session = parse_u32(registry.value(reg_session.value(), row), kSite);
    if (!declared_session) {
      return refuse<SessionRoster>(declared_session.error());
    }
    if (declared_session.value() != ordinal) {
      return refuse<SessionRoster>(Refusal(RefusalCode::CONTENT_MISMATCH, kSite,
                                           "registry row group carries a substituted session",
                                           static_cast<std::int64_t>(declared_session.value())));
    }

    // --- admission ----------------------------------------------------------
    if (registry.is_null(reg_policy.value(), row)) {
      return refuse<SessionRoster>(
          Refusal(RefusalCode::DECODE_FAILED, kSite, "stream_policy_name is null", row));
    }
    const std::string_view policy = registry.value(reg_policy.value(), row);
    if (!is_primitive_policy(policy)) {
      // Typed census only. It creates nothing and is never zero-coded into a
      // primitive denominator.
      if (policy == kUnionPolicy) {
        roster.census.nonprimitive_union_census_only_rows += 1;
      } else {
        roster.census.nonprimitive_unknown_census_only_rows += 1;
      }
      continue;
    }
    roster.census.primitive_candidate_rows += 1;

    // THE STRICT PARSE (consolidated review L2-F1). `cell == "true"` mapped
    // `TRUE`, `1`, and every other spelling onto "not scorable", so a drift in
    // the publication's vocabulary would silently shrink the population instead
    // of stopping the run. A null is refused for the same reason: an absent
    // scorability is not a false one.
    if (registry.is_null(reg_scorable.value(), row)) {
      return refuse<SessionRoster>(
          Refusal(RefusalCode::DECODE_FAILED, kSite, "event_scorable is null", row));
    }
    const auto scorable = parse_bool(registry.value(reg_scorable.value(), row), kSite);
    if (!scorable) {
      return refuse<SessionRoster>(scorable.error());
    }
    const bool has_visibility = !registry.is_null(reg_visible.value(), row) &&
                                registry.value(reg_visible.value(), row) != kAbsentCell;
    const AdmissionClass admission =
        classify_admission(kCandidateRowKind, policy, scorable.value(), has_visibility);
    if (admission == AdmissionClass::PRIMITIVE_NOT_ADMITTED) {
      // Primitive, counted, NOT admitted — and never merged into the admitted
      // set or silently dropped from the primitive census. The two reasons stay
      // apart; a row can carry both.
      if (!scorable.value()) {
        roster.census.primitive_not_admitted_unscorable += 1;
      }
      if (!has_visibility) {
        roster.census.primitive_not_admitted_no_visibility += 1;
      }
      continue;
    }
    roster.census.admitted_rows += 1;

    const auto visible = parse_i64(registry.value(reg_visible.value(), row), kSite);
    if (!visible) {
      return refuse<SessionRoster>(visible.error());
    }
    const auto reversal = parse_u64(registry.value(reg_reversal.value(), row), kSite);
    if (!reversal) {
      return refuse<SessionRoster>(reversal.error());
    }
    if (registry.is_null(reg_members.value(), row)) {
      return refuse<SessionRoster>(Refusal(RefusalCode::DECODE_FAILED, kSite,
                                           "an admitted candidate has a null member list", row));
    }
    const auto registry_members = parse_member_signal_ids(registry.value(reg_members.value(), row));
    if (!registry_members) {
      return refuse<SessionRoster>(registry_members.error());
    }
    // `member_count` is DERIVED from the parsed list; the stored cell is only
    // ever a cross-check against that derivation.
    if (registry.is_null(reg_member_count.value(), row)) {
      return refuse<SessionRoster>(
          Refusal(RefusalCode::DECODE_FAILED, kSite, "member_count is null", row));
    }
    const auto stored_count = parse_u64(registry.value(reg_member_count.value(), row), kSite);
    if (!stored_count) {
      return refuse<SessionRoster>(stored_count.error());
    }
    if (stored_count.value() != registry_members.value().size()) {
      roster.census.member_count_mismatch_candidates += 1;
      return refuse<SessionRoster>(
          Refusal(RefusalCode::CONTENT_MISMATCH, kSite,
                  "stored member_count differs from the derived member count", row));
    }

    // --- the exact join ------------------------------------------------------
    const KeyedRow* raw = find_row(raw_index.value(), keyed.candidate_id);
    if (raw == nullptr) {
      return refuse<SessionRoster>(
          Refusal(RefusalCode::CONTENT_MISMATCH, kSite,
                  "an admitted candidate has no raw CANDIDATE projection row", row));
    }
    const std::int64_t raw_row = raw->row;
    if (projection.is_null(raw_policy.value(), raw_row) ||
        projection.value(raw_policy.value(), raw_row) != policy) {
      return refuse<SessionRoster>(Refusal(RefusalCode::CONTENT_MISMATCH, kSite,
                                           "registry and raw rows disagree on the policy", raw_row));
    }
    if (projection.is_null(raw_reversal.value(), raw_row) ||
        projection.value(raw_reversal.value(), raw_row) !=
            registry.value(reg_reversal.value(), row)) {
      return refuse<SessionRoster>(Refusal(RefusalCode::CONTENT_MISMATCH, kSite,
                                           "registry and raw rows disagree on the reversal", raw_row));
    }
    if (projection.is_null(raw_visible.value(), raw_row) ||
        projection.value(raw_visible.value(), raw_row) !=
            registry.value(reg_visible.value(), row)) {
      return refuse<SessionRoster>(Refusal(RefusalCode::CONTENT_MISMATCH, kSite,
                                           "registry and raw rows disagree on the visibility",
                                           raw_row));
    }
    if (projection.is_null(raw_members.value(), raw_row)) {
      return refuse<SessionRoster>(Refusal(RefusalCode::DECODE_FAILED, kSite,
                                           "the raw CANDIDATE row has a null member list", raw_row));
    }
    const auto raw_members_parsed =
        parse_member_signal_ids(projection.value(raw_members.value(), raw_row));
    if (!raw_members_parsed) {
      return refuse<SessionRoster>(raw_members_parsed.error());
    }
    if (raw_members_parsed.value().size() != registry_members.value().size()) {
      return refuse<SessionRoster>(Refusal(RefusalCode::CONTENT_MISMATCH, kSite,
                                           "registry and raw rows disagree on the member count",
                                           raw_row));
    }
    for (std::size_t i = 0; i < raw_members_parsed.value().size(); ++i) {
      if (raw_members_parsed.value()[i] != registry_members.value()[i]) {
        return refuse<SessionRoster>(Refusal(RefusalCode::CONTENT_MISMATCH, kSite,
                                             "registry and raw rows disagree on a member id",
                                             raw_row));
      }
    }

    // --- the candidate physical key -----------------------------------------
    if (projection.is_null(raw_physical.value(), raw_row)) {
      return refuse<SessionRoster>(Refusal(RefusalCode::CONTENT_MISMATCH, kSite,
                                           "the raw CANDIDATE row has no physical_event_id",
                                           raw_row));
    }
    const std::string_view candidate_key = projection.value(raw_physical.value(), raw_row);
    if (!is_canonical_digest_hex(candidate_key)) {
      return refuse<SessionRoster>(
          Refusal(RefusalCode::DECODE_FAILED, kSite,
                  "physical_event_id is not a canonical lowercase 64-hex digest", raw_row));
    }

    CandidateRecord record;
    record.session_ordinal = ordinal;
    record.candidate_id.assign(keyed.candidate_id);
    record.policy_name.assign(policy);
    record.reversal_bps = reversal.value();
    record.visible_ts_ns = visible.value();
    record.member_count = registry_members.value().size();
    record.candidate_physical_key.assign(candidate_key);

    // --- side authentication from the sealed prefix --------------------------
    std::vector<const SignalAuth*> members;
    members.reserve(registry_members.value().size());
    bool unresolved = false;
    for (const std::string_view id : registry_members.value()) {
      const SignalAuth* member = signals.find(id);
      if (member == nullptr) {
        roster.census.missing_member_references += 1;
        unresolved = true;
        continue;
      }
      members.push_back(member);
    }
    if (unresolved) {
      // Self-consistent, but unauthenticatable: typed, retained, ENTER barred.
      record.side = SideState::SIDE_UNAVAILABLE;
      record.cause = SideUnavailableCause::MEMBER_UNRESOLVED;
      record.enter_forbidden = true;
      roster.census.side_unavailable_candidates += 1;
      roster.candidates.push_back(std::move(record));
      continue;
    }

    // The member set's physical identity. Cardinality other than one is fatal:
    // a candidate whose members are two different physical events has no
    // physical identity at all, and no downstream object may pretend otherwise.
    const std::string_view member_key = members.front()->physical_event_id;
    for (const SignalAuth* member : members) {
      if (member->physical_event_id != member_key) {
        return refuse<SessionRoster>(
            Refusal(RefusalCode::CONTENT_MISMATCH, kSite,
                    "the member set spans more than one physical event", raw_row));
      }
    }
    if (member_key != candidate_key) {
      return refuse<SessionRoster>(
          Refusal(RefusalCode::CONTENT_MISMATCH, kSite,
                  "the member physical event is not the candidate row's physical key", raw_row));
    }
    roster.census.physical_key_authenticated_candidates += 1;

    const ExtremeSide first_side = members.front()->extreme_side;
    bool mixed = false;
    bool policy_mismatch = false;
    bool future_member = false;
    for (const SignalAuth* member : members) {
      mixed = mixed || member->extreme_side != first_side;
      policy_mismatch = policy_mismatch || member->policy_name != policy ||
                        member->reversal_bps != reversal.value();
      future_member = future_member || member->causal_visible_ts_ns > visible.value();
    }
    if (mixed) {
      roster.census.mixed_side_candidates += 1;
      record.cause = SideUnavailableCause::MIXED_MEMBER_SIDE;
    } else if (policy_mismatch) {
      roster.census.primitive_member_policy_or_reversal_mismatch_candidates += 1;
      record.cause = SideUnavailableCause::MEMBER_POLICY_OR_REVERSAL_MISMATCH;
    } else if (future_member) {
      roster.census.future_member_candidates += 1;
      record.cause = SideUnavailableCause::MEMBER_VISIBILITY_IN_FUTURE;
    }
    if (record.cause != SideUnavailableCause::NONE) {
      record.side = SideState::SIDE_UNAVAILABLE;
      record.enter_forbidden = true;
      roster.census.side_unavailable_candidates += 1;
      roster.candidates.push_back(std::move(record));
      continue;
    }

    // LOW -> LONG, HIGH -> SHORT. The whole side authentication is this line
    // plus everything above that earns the right to reach it.
    record.side = first_side == ExtremeSide::LOW ? SideState::LONG : SideState::SHORT;
    record.cause = SideUnavailableCause::NONE;
    record.enter_forbidden = false;
    roster.census.resolved_rows += 1;
    if (record.side == SideState::LONG) {
      roster.census.resolved_long += 1;
    } else {
      roster.census.resolved_short += 1;
    }
    roster.candidates.push_back(std::move(record));
  }
  return roster;
}

std::string render_roster(const SessionRoster& roster) {
  std::string out =
      "session_ordinal\tday\tcandidate_id\tpolicy_name\treversal_bps\tvisible_ts_ns\t"
      "member_count\tcandidate_physical_key\tside\tcause\tenter_forbidden\n";
  for (const CandidateRecord& record : roster.candidates) {
    append_u64(out, record.session_ordinal);
    out += '\t';
    out += roster.day;
    out += '\t';
    out += record.candidate_id;
    out += '\t';
    out += record.policy_name;
    out += '\t';
    append_u64(out, record.reversal_bps);
    out += '\t';
    append_i64(out, record.visible_ts_ns);
    out += '\t';
    append_u64(out, record.member_count);
    out += '\t';
    out += record.candidate_physical_key;
    out += '\t';
    out += side_state_name(record.side);
    out += '\t';
    out += side_unavailable_cause_name(record.cause);
    out += '\t';
    out += record.enter_forbidden ? "true" : "false";
    out += '\n';
  }
  return out;
}

std::string render_census(const RosterCensus& census) {
  std::string out;
  const auto line = [&out](const char* name, std::uint64_t value) {
    out += name;
    out += '\t';
    append_u64(out, value);
    out += '\n';
  };
  line("registry_row_group_rows", census.registry_row_group_rows);
  line("registry_candidate_rows", census.registry_candidate_rows);
  line("primitive_candidate_rows", census.primitive_candidate_rows);
  line("nonprimitive_union_census_only_rows", census.nonprimitive_union_census_only_rows);
  line("nonprimitive_unknown_census_only_rows", census.nonprimitive_unknown_census_only_rows);
  line("admitted_rows", census.admitted_rows);
  line("resolved_rows", census.resolved_rows);
  line("missing_member_references", census.missing_member_references);
  line("mixed_side_candidates", census.mixed_side_candidates);
  line("primitive_member_policy_or_reversal_mismatch_candidates",
       census.primitive_member_policy_or_reversal_mismatch_candidates);
  line("future_member_candidates", census.future_member_candidates);
  line("member_count_mismatch_candidates", census.member_count_mismatch_candidates);
  line("duplicate_candidate_ids", census.duplicate_candidate_ids);
  line("resolved_long", census.resolved_long);
  line("resolved_short", census.resolved_short);
  line("projection_rows", census.projection_rows);
  line("projection_candidate_rows", census.projection_candidate_rows);
  line("side_unavailable_candidates", census.side_unavailable_candidates);
  line("physical_key_authenticated_candidates", census.physical_key_authenticated_candidates);
  line("primitive_not_admitted_unscorable", census.primitive_not_admitted_unscorable);
  line("primitive_not_admitted_no_visibility", census.primitive_not_admitted_no_visibility);
  return out;
}

}  // namespace qr::candidates
