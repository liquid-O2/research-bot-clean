// The candidate roster and side authentication.
//
// The two load-bearing tests are the card's own fail-firsts:
//   * `ASingletonCandidateRowKeyFlipRefusesTheCandidateAndSession` — only the
//     candidate ROW's physical key moves;
//   * `AMultiMemberSplitRefusesTheCandidateAndSession` — one MEMBER's physical
//     id moves, and the census root is recomputed so the prefix seal still
//     passes, which means nothing but the member-physical-key check can catch it.
#include <gtest/gtest.h>

#include <algorithm>
#include <optional>
#include <string>
#include <vector>

#include "candidates_test_support.hpp"
#include "qr_candidates/roster.hpp"
#include "qr_candidates/rowgroup_table.hpp"

namespace {

using namespace qr::candidates;          // NOLINT(build/namespaces)
using namespace qr::candidates::testing;  // NOLINT(build/namespaces)
using qr::Expected;

constexpr std::size_t kFixtureRowGroups = 6;
constexpr std::uint32_t kSession = 2;
constexpr std::uint32_t kStop = 3;

std::vector<std::string_view> as_vector(const auto& array) {
  return std::vector<std::string_view>(array.begin(), array.end());
}

SessionIndex load_index(const std::string& name) {
  auto index = SessionIndex::parse_without_digest_gate(read_whole_file(fixture_path(name)));
  EXPECT_TRUE(index.has_value()) << (index.has_value() ? "" : index.error().message());
  return index.has_value() ? std::move(index).value() : SessionIndex{};
}

/// Everything one roster build needs, kept alive together: the two decoded row
/// groups own the bytes the record views point into.
struct Fixture {
  std::optional<RowGroupTable> registry_table;
  std::optional<RowGroupTable> projection_table;
  std::optional<SessionColumns> registry;
  std::optional<SessionColumns> projection;
  SessionSignals signals;

  [[nodiscard]] Expected<SessionRoster, qr::Refusal> build() {
    if (!registry.has_value() || !projection.has_value()) {
      return qr::refuse<SessionRoster>(
          qr::Refusal(qr::RefusalCode::CONFIG, "test", "a fixture authority did not open"));
    }
    return build_session_roster(kSession, *registry, *projection, signals);
  }
};

/// Builds the three authorities of session 2 from the named fixture files.
Fixture make_fixture(const std::string& registry_parquet = "registry_good.parquet",
                     const std::string& projection_parquet = "projection_good.parquet",
                     const std::string& events = "event_signals_good.tsv",
                     const std::string& census = "t14_bounds_good.tsv",
                     const std::string& registry_index = "registry_index.tsv",
                     const std::string& projection_index = "projection_index.tsv") {
  Fixture fixture;
  auto registry_table = RowGroupTable::open(fixture_path(registry_parquet), {},
                                            load_index(registry_index),
                                            as_vector(kRegistryAllowlist),
                                            as_vector(kRegistryForbidden), kFixtureRowGroups);
  EXPECT_TRUE(registry_table.has_value())
      << (registry_table.has_value() ? "" : registry_table.error().message());
  auto projection_table = RowGroupTable::open(fixture_path(projection_parquet), {},
                                              load_index(projection_index),
                                              as_vector(kProjectionAllowlist),
                                              as_vector(kProjectionForbidden), kFixtureRowGroups);
  EXPECT_TRUE(projection_table.has_value())
      << (projection_table.has_value() ? "" : projection_table.error().message());
  if (!registry_table.has_value() || !projection_table.has_value()) {
    return fixture;
  }
  fixture.registry_table.emplace(std::move(registry_table).value());
  fixture.projection_table.emplace(std::move(projection_table).value());
  auto registry = fixture.registry_table->read_session(kSession);
  EXPECT_TRUE(registry.has_value()) << (registry.has_value() ? "" : registry.error().message());
  auto projection = fixture.projection_table->read_session(kSession);
  EXPECT_TRUE(projection.has_value())
      << (projection.has_value() ? "" : projection.error().message());
  if (registry.has_value()) {
    fixture.registry.emplace(std::move(registry).value());
  }
  if (projection.has_value()) {
    fixture.projection.emplace(std::move(projection).value());
  }

  const auto bounds = load_fixture_bounds(census, kStop);
  MemorySource source(read_whole_file(fixture_path(events)));
  PrefixSealOptions options;
  options.stop_ordinal = kStop;
  options.retain_from = kSession;
  options.retain_to = kSession;
  options.require_pinned_event_bytes = false;
  options.require_full_row_census = false;
  CollectingSink sink;
  const auto seal = seal_prefix(source, bounds, options, sink.sink());
  EXPECT_TRUE(seal.has_value()) << (seal.has_value() ? "" : seal.error().message());
  if (!sink.sessions.empty()) {
    fixture.signals.begin(sink.sessions[0].ordinal());
    for (const SignalAuth& row : sink.sessions[0].rows()) {
      fixture.signals.append(row);
    }
    EXPECT_TRUE(fixture.signals.seal().has_value());
  }
  return fixture;
}

const CandidateRecord* find(const SessionRoster& roster, const std::string& candidate_id) {
  for (const CandidateRecord& record : roster.candidates) {
    if (record.candidate_id == candidate_id) {
      return &record;
    }
  }
  return nullptr;
}

// --- the strict member-id parse ----------------------------------------------

TEST(MemberParse, AcceptsTheCanonicalAscendingUniqueLowercaseList) {
  const std::string a(64, 'a');
  const std::string b(64, 'b');
  const std::string cell = a + "," + b;  // named: the views point into it
  const auto ids = parse_member_signal_ids(cell);
  ASSERT_TRUE(ids.has_value()) << (ids.has_value() ? "" : ids.error().message());
  ASSERT_EQ(ids.value().size(), 2U);
  EXPECT_EQ(ids.value()[0], a);
  EXPECT_EQ(ids.value()[1], b);
}

TEST(MemberParse, AnEmptyCellRefuses) {
  const auto ids = parse_member_signal_ids("");
  ASSERT_FALSE(ids.has_value());
  EXPECT_EQ(ids.error().code(), qr::RefusalCode::DECODE_FAILED);
}

TEST(MemberParse, AnEmptyTokenRefuses) {
  const std::string a(64, 'a');
  EXPECT_FALSE(parse_member_signal_ids(a + ",").has_value());
  EXPECT_FALSE(parse_member_signal_ids("," + a).has_value());
  EXPECT_FALSE(parse_member_signal_ids(a + ",," + a).has_value());
}

TEST(MemberParse, UppercaseHexIsRefusedNotFolded) {
  const auto ids = parse_member_signal_ids(std::string(64, 'A'));
  ASSERT_FALSE(ids.has_value());
  EXPECT_EQ(ids.error().code(), qr::RefusalCode::DECODE_FAILED);
}

TEST(MemberParse, WhitespaceAnywhereRefuses) {
  const std::string a(64, 'a');
  const std::string b(64, 'b');
  EXPECT_FALSE(parse_member_signal_ids(a + ", " + b).has_value());
  EXPECT_FALSE(parse_member_signal_ids(" " + a).has_value());
  EXPECT_FALSE(parse_member_signal_ids(a + " ").has_value());
}

TEST(MemberParse, ADescendingListRefusesInsteadOfBeingSorted) {
  const std::string a(64, 'a');
  const std::string b(64, 'b');
  const auto ids = parse_member_signal_ids(b + "," + a);
  ASSERT_FALSE(ids.has_value());
  EXPECT_EQ(ids.error().code(), qr::RefusalCode::OUT_OF_ORDER);
}

TEST(MemberParse, ARepeatedIdRefuses) {
  const std::string a(64, 'a');
  const auto ids = parse_member_signal_ids(a + "," + a);
  ASSERT_FALSE(ids.has_value());
  EXPECT_EQ(ids.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}

TEST(MemberParse, AWrongLengthTokenRefuses) {
  EXPECT_FALSE(parse_member_signal_ids(std::string(63, 'a')).has_value());
  EXPECT_FALSE(parse_member_signal_ids(std::string(65, 'a')).has_value());
}

// --- the policy vocabulary ----------------------------------------------------

TEST(PolicyVocabulary, AdmitsExactlyTheTwelvePrimitivePolicies) {
  EXPECT_EQ(kPrimitivePolicies.size(), 12U);
  for (const std::string_view policy : kPrimitivePolicies) {
    EXPECT_TRUE(is_primitive_policy(policy)) << policy;
  }
  // The gaps are real: these spellings exist upstream and are NOT primitive.
  for (const std::string_view policy :
       {"dc009", "dc011", "dc013", "dc014", "dc016", "dc019", "UNION", "", "DC001", "dc0010"}) {
    EXPECT_FALSE(is_primitive_policy(policy)) << policy;
  }
}

// --- the happy path -----------------------------------------------------------

TEST(Roster, AuthenticatesLowAsLongAndHighAsShort) {
  const Literals literals;
  Fixture fixture = make_fixture();
  const auto roster = fixture.build();
  ASSERT_TRUE(roster.has_value()) << (roster.has_value() ? "" : roster.error().message());
  const CandidateRecord* a = find(roster.value(), literals.text("candidate_id", "cand_A"));
  ASSERT_NE(a, nullptr);
  EXPECT_EQ(a->side, SideState::LONG);  // its member is LOW
  EXPECT_FALSE(a->enter_forbidden);
  EXPECT_EQ(a->candidate_physical_key, literals.text("physical", "P1"));
  EXPECT_EQ(a->member_count, 1U);

  const CandidateRecord* b = find(roster.value(), literals.text("candidate_id", "cand_B"));
  ASSERT_NE(b, nullptr);
  EXPECT_EQ(b->side, SideState::SHORT);  // both members are HIGH
  EXPECT_EQ(b->member_count, 2U);
  EXPECT_EQ(b->candidate_physical_key, literals.text("physical", "P2"));
}

TEST(Roster, TheCensusCountsEveryTypedClassSeparately) {
  Fixture fixture = make_fixture();
  const auto roster = fixture.build();
  ASSERT_TRUE(roster.has_value()) << (roster.has_value() ? "" : roster.error().message());
  const RosterCensus& census = roster.value().census;
  EXPECT_EQ(census.registry_candidate_rows, 11U);
  EXPECT_EQ(census.primitive_candidate_rows, 9U);         // 11 rows less UNION and dc009
  EXPECT_EQ(census.nonprimitive_union_census_only_rows, 1U);
  EXPECT_EQ(census.nonprimitive_unknown_census_only_rows, 1U);
  EXPECT_EQ(census.admitted_rows, 7U);                    // less the unscorable and the visibility-less
  EXPECT_EQ(census.resolved_rows, 3U);                    // A, B and F authenticate
  EXPECT_EQ(census.resolved_long, 2U);
  EXPECT_EQ(census.resolved_short, 1U);
  EXPECT_EQ(census.side_unavailable_candidates, 4U);      // C, D, E, G
  EXPECT_EQ(census.resolved_rows + census.side_unavailable_candidates, census.admitted_rows);
  // Every admitted candidate whose members all resolve has its physical key
  // authenticated, INCLUDING the ones whose side is then unavailable: an
  // authenticated identity and an authenticated side are different facts.
  EXPECT_EQ(census.physical_key_authenticated_candidates, 6U);
  EXPECT_EQ(census.physical_key_authenticated_candidates + 1U, census.admitted_rows);
  // The projection carries a TRUTH row that never enters the join.
  EXPECT_EQ(census.projection_rows, census.projection_candidate_rows + 1U);
}

TEST(Roster, EveryAdmittedCandidateStaysInTheDenominatorIncludingTheUnauthenticated) {
  Fixture fixture = make_fixture();
  const auto roster = fixture.build();
  ASSERT_TRUE(roster.has_value());
  EXPECT_EQ(roster.value().candidates.size(), roster.value().census.admitted_rows);
}

TEST(Roster, NonprimitiveRowsCreateNoRecordAtAll) {
  const Literals literals;
  Fixture fixture = make_fixture();
  const auto roster = fixture.build();
  ASSERT_TRUE(roster.has_value());
  EXPECT_EQ(find(roster.value(), literals.text("candidate_id", "cand_U")), nullptr);
  EXPECT_EQ(find(roster.value(), literals.text("candidate_id", "cand_X")), nullptr);
}

TEST(Roster, APrimitiveRowWithNoVisibilityOrNoScorabilityIsNotAdmitted) {
  const Literals literals;
  Fixture fixture = make_fixture();
  const auto roster = fixture.build();
  ASSERT_TRUE(roster.has_value());
  EXPECT_EQ(find(roster.value(), literals.text("candidate_id", "cand_N")), nullptr);
  EXPECT_EQ(find(roster.value(), literals.text("candidate_id", "cand_S")), nullptr);
}

TEST(AdmissionClassLaw, TheFourClassesAreDecidedInOnePlaceAndPrimitiveNotAdmittedIsOneOfThem) {
  EXPECT_EQ(classify_admission("TRUTH", "dc001", true, true), AdmissionClass::NOT_A_CANDIDATE_ROW);
  EXPECT_EQ(classify_admission("CANDIDATE", "UNION", true, true),
            AdmissionClass::NONPRIMITIVE_CENSUS_ONLY);
  EXPECT_EQ(classify_admission("CANDIDATE", "dc009", true, true),
            AdmissionClass::NONPRIMITIVE_CENSUS_ONLY);
  EXPECT_EQ(classify_admission("CANDIDATE", "dc001", false, true),
            AdmissionClass::PRIMITIVE_NOT_ADMITTED);
  EXPECT_EQ(classify_admission("CANDIDATE", "dc001", true, false),
            AdmissionClass::PRIMITIVE_NOT_ADMITTED);
  EXPECT_EQ(classify_admission("CANDIDATE", "dc001", false, false),
            AdmissionClass::PRIMITIVE_NOT_ADMITTED);
  EXPECT_EQ(classify_admission("CANDIDATE", "dc001", true, true),
            AdmissionClass::ADMITTED_PRIMITIVE);
}

TEST(Roster, AnEventScorableCellThatIsNotExactlyTrueOrFalseRefusesInsteadOfNotAdmitting) {
  // Review L2-F1. Under `cell == "true"` each of these spellings read as "not
  // scorable" and cand_A left the population without a word; the strict parse
  // stops the run instead.
  const std::vector<std::string> variants = {"registry_scorable_upper.parquet",
                                             "registry_scorable_one.parquet",
                                             "registry_scorable_garbage.parquet"};
  for (const std::string& variant : variants) {
    Fixture fixture = make_fixture(variant);
    const auto roster = fixture.build();
    ASSERT_FALSE(roster.has_value())
        << variant << ": the unlawful event_scorable cell was silently read as 'not scorable' — "
        << roster.value().census.admitted_rows << " admitted rows (instead of "
        << roster.value().census.admitted_rows + 1 << ") and no refusal at all";
    EXPECT_EQ(roster.error().code(), qr::RefusalCode::DECODE_FAILED) << variant;
  }
}

TEST(Roster, TheNotAdmittedCensusKeepsUnscorableAndVisibilityLessApart) {
  Fixture fixture = make_fixture();
  const auto roster = fixture.build();
  ASSERT_TRUE(roster.has_value()) << (roster.has_value() ? "" : roster.error().message());
  const RosterCensus& census = roster.value().census;
  // cand_S carries event_scorable=false; cand_N has no own visibility. Two
  // different reasons, two different counters, never one merged bucket.
  EXPECT_EQ(census.primitive_not_admitted_unscorable, 1U);
  EXPECT_EQ(census.primitive_not_admitted_no_visibility, 1U);
  // The primitive denominator accounts for every row it counted.
  EXPECT_EQ(census.primitive_candidate_rows,
            census.admitted_rows + census.primitive_not_admitted_unscorable +
                census.primitive_not_admitted_no_visibility);
  EXPECT_NE(render_census(census).find("primitive_not_admitted_unscorable\t1\n"),
            std::string::npos);
  EXPECT_NE(render_census(census).find("primitive_not_admitted_no_visibility\t1\n"),
            std::string::npos);
}

TEST(Roster, RecordsAreOrderedByCandidateIdNotByRowOrder) {
  Fixture fixture = make_fixture();
  const auto roster = fixture.build();
  ASSERT_TRUE(roster.has_value());
  for (std::size_t i = 1; i < roster.value().candidates.size(); ++i) {
    EXPECT_LT(roster.value().candidates[i - 1].candidate_id,
              roster.value().candidates[i].candidate_id);
  }
}

// --- typed side unavailability ------------------------------------------------

TEST(Roster, MixedMemberSidesAreTypedUnavailableAndRetained) {
  const Literals literals;
  Fixture fixture = make_fixture();
  const auto roster = fixture.build();
  ASSERT_TRUE(roster.has_value());
  const CandidateRecord* c = find(roster.value(), literals.text("candidate_id", "cand_C"));
  ASSERT_NE(c, nullptr);
  EXPECT_EQ(c->side, SideState::SIDE_UNAVAILABLE);
  EXPECT_EQ(c->cause, SideUnavailableCause::MIXED_MEMBER_SIDE);
  EXPECT_TRUE(c->enter_forbidden);
  EXPECT_EQ(roster.value().census.mixed_side_candidates, 1U);
}

TEST(Roster, AMemberVisibleAfterTheCandidateIsTypedUnavailable) {
  const Literals literals;
  Fixture fixture = make_fixture();
  const auto roster = fixture.build();
  ASSERT_TRUE(roster.has_value());
  const CandidateRecord* d = find(roster.value(), literals.text("candidate_id", "cand_D"));
  ASSERT_NE(d, nullptr);
  EXPECT_EQ(d->cause, SideUnavailableCause::MEMBER_VISIBILITY_IN_FUTURE);
  EXPECT_TRUE(d->enter_forbidden);
  EXPECT_EQ(roster.value().census.future_member_candidates, 1U);
}

TEST(Roster, AMemberWhosePolicyOrReversalDiffersIsTypedUnavailable) {
  const Literals literals;
  Fixture fixture = make_fixture();
  const auto roster = fixture.build();
  ASSERT_TRUE(roster.has_value());
  const CandidateRecord* e = find(roster.value(), literals.text("candidate_id", "cand_E"));
  ASSERT_NE(e, nullptr);
  EXPECT_EQ(e->cause, SideUnavailableCause::MEMBER_POLICY_OR_REVERSAL_MISMATCH);
  EXPECT_EQ(roster.value().census.primitive_member_policy_or_reversal_mismatch_candidates, 1U);
}

TEST(Roster, AMemberThatDoesNotResolveInSessionIsTypedUnavailable) {
  const Literals literals;
  Fixture fixture = make_fixture();
  const auto roster = fixture.build();
  ASSERT_TRUE(roster.has_value());
  const CandidateRecord* g = find(roster.value(), literals.text("candidate_id", "cand_G"));
  ASSERT_NE(g, nullptr);
  EXPECT_EQ(g->cause, SideUnavailableCause::MEMBER_UNRESOLVED);
  EXPECT_EQ(roster.value().census.missing_member_references, 1U);
}

// --- THE TWO PHYSICAL-EVENT FAIL-FIRSTS ---------------------------------------

TEST(Roster, ASingletonCandidateRowKeyFlipRefusesTheCandidateAndSession) {
  // Only the candidate ROW's physical_event_id moves. The member still resolves,
  // still agrees on side, and still carries a lawful key — but it is no longer
  // the candidate's key.
  Fixture fixture = make_fixture("registry_good.parquet",
                                 "projection_singleton_key_flip.parquet");
  const auto roster = fixture.build();
  ASSERT_FALSE(roster.has_value()) << "the flipped candidate key was accepted";
  EXPECT_EQ(roster.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}

TEST(Roster, AMultiMemberSplitRefusesTheCandidateAndSession) {
  // One MEMBER's physical id moves to a second physical event, and the census
  // root is recomputed so the prefix seal still passes. Nothing but the
  // member-set cardinality check can catch this.
  Fixture fixture = make_fixture("registry_good.parquet", "projection_good.parquet",
                                 "event_signals_member_split.tsv",
                                 "t14_bounds_member_split.tsv");
  const auto roster = fixture.build();
  ASSERT_FALSE(roster.has_value()) << "a member set spanning two physical events was accepted";
  EXPECT_EQ(roster.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}

TEST(Roster, TheMultiMemberSplitFixtureStillPassesThePrefixSeal) {
  // Proves the previous test measures the ROSTER check and not the root check:
  // the mutated prefix seals cleanly against its own recomputed census.
  const auto bounds = load_fixture_bounds("t14_bounds_member_split.tsv", kStop);
  MemorySource source(read_whole_file(fixture_path("event_signals_member_split.tsv")));
  PrefixSealOptions options;
  options.stop_ordinal = kStop;
  options.retain_from = kSession;
  options.retain_to = kSession;
  options.require_pinned_event_bytes = false;
  options.require_full_row_census = false;
  CollectingSink sink;
  const auto seal = seal_prefix(source, bounds, options, sink.sink());
  ASSERT_TRUE(seal.has_value()) << (seal.has_value() ? "" : seal.error().message());
  EXPECT_EQ(seal.value().roots_verified, kStop + 1U);
}

TEST(Roster, AnEmptyPhysicalKeyOnTheRawRowRefuses) {
  // A REQUIRED leaf has no null state, so "missing" arrives as an empty cell.
  // It must be refused on its shape rather than carried as a physical identity.
  Fixture fixture = make_fixture("registry_good.parquet",
                                 "projection_join_physical_empty.parquet");
  const auto roster = fixture.build();
  ASSERT_FALSE(roster.has_value());
  EXPECT_EQ(roster.error().code(), qr::RefusalCode::DECODE_FAILED);
}

// --- the exact join -----------------------------------------------------------

TEST(Roster, ARawRowThatDisagreesOnPolicyReversalVisibilityOrMembersRefuses) {
  for (const char* name : {"projection_join_policy.parquet", "projection_join_reversal.parquet",
                           "projection_join_visible.parquet", "projection_join_members.parquet"}) {
    Fixture fixture = make_fixture("registry_good.parquet", name);
    const auto roster = fixture.build();
    ASSERT_FALSE(roster.has_value()) << name;
    EXPECT_EQ(roster.error().code(), qr::RefusalCode::CONTENT_MISMATCH) << name;
  }
}

TEST(Roster, AStoredMemberCountThatContradictsTheDerivedCountRefuses) {
  Fixture fixture = make_fixture("registry_member_count_mismatch.parquet");
  const auto roster = fixture.build();
  ASSERT_FALSE(roster.has_value());
  EXPECT_EQ(roster.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}

TEST(Roster, ARepeatedCandidateIdInOneSessionRefuses) {
  Fixture fixture = make_fixture("registry_duplicate_candidate.parquet",
                                 "projection_good.parquet", "event_signals_good.tsv",
                                 "t14_bounds_good.tsv",
                                 "registry_index_duplicate_candidate.tsv");
  const auto roster = fixture.build();
  ASSERT_FALSE(roster.has_value());
  EXPECT_EQ(roster.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}

TEST(Roster, EveryMalformedMemberCellShapeIsTypedRefused) {
  for (const char* name :
       {"registry_member_empty_token.parquet", "registry_member_uppercase.parquet",
        "registry_member_unsorted.parquet", "registry_member_duplicate.parquet",
        "registry_member_whitespace.parquet"}) {
    Fixture fixture = make_fixture(name);
    const auto roster = fixture.build();
    ASSERT_FALSE(roster.has_value()) << name;
    const qr::RefusalCode code = roster.error().code();
    EXPECT_TRUE(code == qr::RefusalCode::DECODE_FAILED ||
                code == qr::RefusalCode::OUT_OF_ORDER ||
                code == qr::RefusalCode::CONTENT_MISMATCH)
        << name << " gave " << qr::refusal_code_name(code);
  }
}

TEST(Roster, TheThreeAuthoritiesMustBeTheSameSession) {
  Fixture fixture = make_fixture();
  ASSERT_TRUE(fixture.registry.has_value());
  ASSERT_TRUE(fixture.projection.has_value());
  const auto roster = build_session_roster(1, *fixture.registry, *fixture.projection,
                                           fixture.signals);
  ASSERT_FALSE(roster.has_value());
  EXPECT_EQ(roster.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}

TEST(Roster, AnOrdinalPastTheWallRefusesBeforeAnythingIsJoined) {
  Fixture fixture = make_fixture();
  ASSERT_TRUE(fixture.registry.has_value());
  ASSERT_TRUE(fixture.projection.has_value());
  const auto roster = build_session_roster(918, *fixture.registry, *fixture.projection,
                                           fixture.signals);
  ASSERT_FALSE(roster.has_value());
  EXPECT_EQ(roster.error().code(), qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE);
}

// --- the late-sibling invariance ----------------------------------------------

TEST(Roster, DeletingTheLatestVisibleSiblingLeavesEveryEarlierRecordBitUnchanged) {
  const Literals literals;
  Fixture full = make_fixture();
  const auto complete = full.build();
  ASSERT_TRUE(complete.has_value()) << (complete.has_value() ? "" : complete.error().message());

  Fixture pruned = make_fixture("registry_late_sibling_deleted.parquet",
                                "projection_late_sibling_deleted.parquet",
                                "event_signals_good.tsv", "t14_bounds_good.tsv",
                                "registry_index_late_sibling_deleted.tsv",
                                "projection_index_late_sibling_deleted.tsv");
  const auto shorter = pruned.build();
  ASSERT_TRUE(shorter.has_value()) << (shorter.has_value() ? "" : shorter.error().message());

  // The deleted sibling really was the strictly-latest-visible candidate.
  const CandidateRecord* late = find(complete.value(), literals.text("candidate_id", "cand_F"));
  ASSERT_NE(late, nullptr);
  for (const CandidateRecord& record : complete.value().candidates) {
    if (record.candidate_id != late->candidate_id) {
      EXPECT_LT(record.visible_ts_ns, late->visible_ts_ns);
    }
  }
  ASSERT_EQ(find(shorter.value(), literals.text("candidate_id", "cand_F")), nullptr);

  // Every earlier record, rendered byte for byte, is unchanged.
  SessionRoster expected = complete.value();
  expected.candidates.erase(
      std::remove_if(expected.candidates.begin(), expected.candidates.end(),
                     [&](const CandidateRecord& record) {
                       return record.candidate_id == late->candidate_id;
                     }),
      expected.candidates.end());
  EXPECT_EQ(render_roster(expected), render_roster(shorter.value()));
  EXPECT_EQ(expected.candidates.size() + 1U, complete.value().candidates.size());
}

TEST(Roster, TwoBuildsOfOneSessionRenderByteIdenticalOutput) {
  Fixture first = make_fixture();
  Fixture second = make_fixture();
  const auto a = first.build();
  const auto b = second.build();
  ASSERT_TRUE(a.has_value());
  ASSERT_TRUE(b.has_value());
  EXPECT_EQ(render_roster(a.value()), render_roster(b.value()));
  EXPECT_EQ(render_census(a.value().census), render_census(b.value().census));
}

}  // namespace
