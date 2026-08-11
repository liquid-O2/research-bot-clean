// The three views of one NBBO member, and the totalized domain classifier.
//
// SPEC (WP5 brief): "validity = finite, bid>0, ask>0, ask>bid, both conditions
// eligible (code 0); locked (bid==ask), crossed (bid>ask), one-sided as typed
// quality tokens with economic values MASKED (Validity states, not sentinel
// values)".
// Port reference: corpus/src/reader.rs quote_state :1193-1212, add_member's
// structural predicate :632-639, the scientific bar :649, stock_quote_domain
// :1170-1191.
#include <gtest/gtest.h>

#include <cstdint>
#include <optional>

#include "nbbo_test_support.hpp"
#include "qr_nbbo/census.hpp"
#include "qr_nbbo/group_machine.hpp"

namespace {

using qr::Validity;
using qr::nbbo::classify_domain;
using qr::nbbo::classify_member;
using qr::nbbo::classify_member_validity;
using qr::nbbo::classify_quote_state;
using qr::nbbo::is_scientific_spread;
using qr::nbbo::is_structurally_valid;
using qr::nbbo::kMaxNormalizedNbboPriceU6;
using qr::nbbo::MemberFields;
using qr::nbbo::QuoteDomain;
using qr::nbbo::QuoteState;
using qr::nbbo::testing::clock_125;
using qr::nbbo::testing::open_ms_125;
using qr::nbbo::testing::quote_row;
using qr::nbbo::testing::with_null;

MemberFields fields(std::optional<std::int64_t> bid, std::optional<std::int64_t> ask,
                    std::optional<std::int64_t> bid_shares, std::optional<std::int64_t> ask_shares,
                    std::optional<std::int64_t> bid_condition = 0,
                    std::optional<std::int64_t> ask_condition = 0) {
  MemberFields out;
  out.bid_u6 = bid;
  out.ask_u6 = ask;
  out.bid_shares = bid_shares;
  out.ask_shares = ask_shares;
  out.bid_condition = bid_condition;
  out.ask_condition = ask_condition;
  return out;
}

// --- the three views --------------------------------------------------------

TEST(MemberViews, ANormalTightTwoSidedQuoteIsValidInAllThreeViews) {
  // bid $171.000000, ask $171.010000: ask > bid, both sides sized, both
  // conditions code 0, bid+ask = 342,010,000 (even, so the midpoint is exact).
  const MemberFields f = fields(171'000'000, 171'010'000, 500, 700);
  EXPECT_EQ(classify_quote_state(f, false), QuoteState::NORMAL);
  EXPECT_EQ(classify_member_validity(f), Validity::VALID);
  EXPECT_TRUE(is_structurally_valid(f));

  const auto classified = classify_member(quote_row(0, 171'000'000, 171'010'000, 500, 700));
  ASSERT_TRUE(classified.has_value());
  EXPECT_EQ(classified.value().state, QuoteState::NORMAL);
  EXPECT_EQ(classified.value().validity, Validity::VALID);
  EXPECT_TRUE(classified.value().structurally_valid);
  EXPECT_FALSE(classified.value().locked);
  EXPECT_TRUE(classified.value().scientific);
  // (171,000,000 + 171,010,000) / 2 = 342,010,000 / 2 = 171,005,000.
  EXPECT_EQ(classified.value().midpoint_u6, 171'005'000);
}

TEST(MemberViews, LockedIsStructurallyValidForTheCsrAndAMaskedQualityTokenForTheCard) {
  // THE TWO VIEWS DISAGREE ON PURPOSE. The frozen CSR predicate is `ask >= bid`
  // (reader.rs:638), so a locked member is structurally valid there and its
  // midpoint enters the projection. The card's law is `ask > bid`, so the same
  // member is a LOCKED quality token whose economic value is masked.
  const MemberFields f = fields(171'020'000, 171'020'000, 300, 400);
  EXPECT_EQ(classify_quote_state(f, false), QuoteState::LOCKED);
  EXPECT_EQ(classify_member_validity(f), Validity::LOCKED);
  EXPECT_TRUE(is_structurally_valid(f));

  const auto classified = classify_member(quote_row(0, 171'020'000, 171'020'000, 300, 400));
  ASSERT_TRUE(classified.has_value());
  EXPECT_TRUE(classified.value().locked);
  // Spread 0 clears any bar, so a locked member is "scientific" to the CSR.
  EXPECT_TRUE(classified.value().scientific);
  EXPECT_EQ(classified.value().midpoint_u6, 171'020'000);
  EXPECT_NE(classified.value().validity, Validity::VALID)
      << "a locked quote must never be able to supply a midpoint to the card's channels";
}

TEST(MemberViews, CrossedIsRejectedByTheCsrAndTypedCrossed) {
  const MemberFields f = fields(171'050'000, 171'040'000, 100, 200);
  EXPECT_EQ(classify_quote_state(f, false), QuoteState::CROSSED);
  EXPECT_EQ(classify_member_validity(f), Validity::CROSSED);
  EXPECT_FALSE(is_structurally_valid(f)) << "ask >= bid is the frozen CSR rule";
}

TEST(MemberViews, AZeroPricedSideIsOneSidedToTheCensusAndNonpositiveToTheLattice) {
  // The reference filters prices to strictly positive before its match, so a
  // zero ask makes the member BID_ONLY there. In the C1 lattice NONPOSITIVE
  // outranks ONE_SIDED, so worst-wins names the sharper defect.
  const MemberFields f = fields(171'030'000, 0, 500, 600);
  EXPECT_EQ(classify_quote_state(f, false), QuoteState::BID_ONLY);
  EXPECT_EQ(classify_member_validity(f), Validity::NONPOSITIVE);
  EXPECT_FALSE(is_structurally_valid(f));

  const MemberFields mirrored = fields(0, 171'030'000, 500, 600);
  EXPECT_EQ(classify_quote_state(mirrored, false), QuoteState::ASK_ONLY);
  EXPECT_EQ(classify_member_validity(mirrored), Validity::NONPOSITIVE);
}

TEST(MemberViews, ANullPricedSideIsOneSidedInTheLattice) {
  // Absence is a MASK BIT, not a zero: with the ask MISSING and the bid VALID
  // the member is ONE_SIDED, the state the card names.
  const MemberFields f = fields(171'030'000, std::nullopt, 500, 600);
  EXPECT_EQ(classify_quote_state(f, false), QuoteState::BID_ONLY);
  EXPECT_EQ(classify_member_validity(f), Validity::ONE_SIDED);
  EXPECT_FALSE(is_structurally_valid(f));

  const auto classified =
      classify_member(with_null(quote_row(0, 171'030'000, 0, 500, 600), qr::sources::kQuoteSlotAsk));
  ASSERT_TRUE(classified.has_value());
  EXPECT_EQ(classified.value().validity, Validity::ONE_SIDED);
  EXPECT_EQ(classified.value().state, QuoteState::BID_ONLY);
}

TEST(MemberViews, BothSidesAbsentIsMissing) {
  const MemberFields f = fields(std::nullopt, std::nullopt, std::nullopt, std::nullopt);
  EXPECT_EQ(classify_quote_state(f, false), QuoteState::BOTH_SIDES_ABSENT);
  EXPECT_EQ(classify_member_validity(f), Validity::MISSING);
  EXPECT_FALSE(is_structurally_valid(f));
}

TEST(MemberViews, ConditionIneligibleIsNormalToTheCensusAndIneligibleToTheCard) {
  // `quote_state` never looks at conditions (reader.rs:1193-1212) — the census
  // view of this member is NORMAL. The card's eligibility contract does, so
  // the same member cannot supply a midpoint, and the CSR rejects it too.
  const MemberFields f = fields(171'060'000, 171'070'000, 400, 400, 1, 0);
  EXPECT_EQ(classify_quote_state(f, false), QuoteState::NORMAL);
  EXPECT_EQ(classify_member_validity(f), Validity::CONDITION_INELIGIBLE);
  EXPECT_FALSE(is_structurally_valid(f));

  const MemberFields ask_side = fields(171'060'000, 171'070'000, 400, 400, 0, 4);
  EXPECT_EQ(classify_member_validity(ask_side), Validity::CONDITION_INELIGIBLE);
  EXPECT_FALSE(is_structurally_valid(ask_side));
}

TEST(MemberViews, APriceAboveTheSanityCeilingIsNonfiniteAndInvalid) {
  const MemberFields f = fields(171'300'000, kMaxNormalizedNbboPriceU6 + 1, 500, 500);
  EXPECT_EQ(classify_quote_state(f, true), QuoteState::INVALID);
  EXPECT_EQ(classify_member_validity(f), Validity::NONFINITE);
  EXPECT_FALSE(is_structurally_valid(f));
  // Exactly at the ceiling is admissible, on both views.
  const MemberFields at = fields(171'300'000, kMaxNormalizedNbboPriceU6, 500, 500);
  EXPECT_EQ(classify_member_validity(at), Validity::VALID);
  EXPECT_TRUE(is_structurally_valid(at))
      << "the sanity ceiling is inclusive (1..=MAX in the reference)";
}

TEST(MemberViews, ANonpositiveSizeIsInvalidToTheCensusAndNonpositiveToTheLattice) {
  // A two-sided quote with a zero size falls through every one of the
  // reference's match arms to the catch-all: INVALID, not BID_ONLY.
  const MemberFields f = fields(171'000'000, 171'010'000, 0, 700);
  EXPECT_EQ(classify_quote_state(f, false), QuoteState::INVALID);
  EXPECT_EQ(classify_member_validity(f), Validity::NONPOSITIVE);
  EXPECT_FALSE(is_structurally_valid(f));
}

TEST(MemberViews, AnOddBidPlusAskIsStructurallyRejectedBecauseItsMidpointWouldNotBeExact) {
  // The frozen CSR predicate's last clause, `(bid + ask) % 2 == 0`
  // (reader.rs:639): a member whose midpoint is not an exact u6 integer never
  // enters the projection. It is still a perfectly eligible quote to the card.
  const MemberFields f = fields(171'000'000, 171'000'001, 500, 500);
  EXPECT_FALSE(is_structurally_valid(f));
  EXPECT_EQ(classify_member_validity(f), Validity::VALID);
  EXPECT_EQ(classify_quote_state(f, false), QuoteState::NORMAL);
}

// --- the 50 bp scientific bar ----------------------------------------------

TEST(ScientificSpread, TheFiftyBasisPointBarIsInclusiveAtItsExactBoundary) {
  // bid+ask = 342,000,000 so mid = 171,000,000; 50 bp of that mid is 855,000.
  // spread * 20,000 = 855,000 * 20,000 = 17,100,000,000
  // 50 * total      = 50 * 342,000,000 = 17,100,000,000  -> equal -> scientific.
  const auto at_bar = is_scientific_spread(170'572'500, 171'427'500);
  ASSERT_TRUE(at_bar.has_value());
  EXPECT_TRUE(at_bar.value());

  // One u6 unit wider on each side: spread 855,002, total unchanged.
  // 855,002 * 20,000 = 17,100,040,000 > 17,100,000,000 -> wide.
  const auto past_bar = is_scientific_spread(170'572'499, 171'427'501);
  ASSERT_TRUE(past_bar.has_value());
  EXPECT_FALSE(past_bar.value());
}

TEST(ScientificSpread, ADollarWideMarketIsNotScientificAndAZeroSpreadAlwaysIs) {
  // bid 170.000000 / ask 172.000000: spread 2,000,000, total 342,000,000.
  // 2,000,000 * 20,000 = 40,000,000,000 > 50 * 342,000,000 = 17,100,000,000.
  const auto wide = is_scientific_spread(170'000'000, 172'000'000);
  ASSERT_TRUE(wide.has_value());
  EXPECT_FALSE(wide.value());
  const auto locked = is_scientific_spread(171'000'000, 171'000'000);
  ASSERT_TRUE(locked.has_value());
  EXPECT_TRUE(locked.value());
}

// --- the TOTALIZED domain classifier ---------------------------------------

TEST(DomainClassifier, TheFourRegisteredDomainsOfARegularSession) {
  const qr::SessionClock clock = clock_125();
  const std::int64_t open = open_ms_125();
  constexpr std::int64_t kMinute = 60'000;
  // 04:00 is 5h30m before the 09:30 open.
  EXPECT_EQ(classify_domain(clock, open - (5 * 60 + 30) * kMinute), QuoteDomain::PREMARKET);
  EXPECT_EQ(classify_domain(clock, open - 1), QuoteDomain::PREMARKET);
  EXPECT_EQ(classify_domain(clock, open), QuoteDomain::RTH);
  EXPECT_EQ(classify_domain(clock, open + 389 * kMinute), QuoteDomain::RTH);
  // A 390-bar session's post-open boundary is open + 6h30m, i.e. its close.
  EXPECT_EQ(classify_domain(clock, open + 390 * kMinute), QuoteDomain::AFTER_HOURS);
  EXPECT_EQ(classify_domain(clock, open + (390 + 239) * kMinute), QuoteDomain::AFTER_HOURS);
  // Four hours after that boundary the domain ends.
  EXPECT_EQ(classify_domain(clock, open + (390 + 240) * kMinute), QuoteDomain::OUTSIDE_DOMAIN);
  // Before 04:00 as well.
  EXPECT_EQ(classify_domain(clock, open - (5 * 60 + 31) * kMinute), QuoteDomain::OUTSIDE_DOMAIN);
}

TEST(DomainClassifier, AnEarlyCloseUsesItsOwnCloseAsThePostOpenBoundary) {
  // 2022-11-25 is a registered 210-bar early close inside the 125..749 scope.
  const qr::Registry* const registry = qr::sources::testing::registry_or_null();
  ASSERT_NE(registry, nullptr);
  const auto scope = qr::DayScope::admit_day(*registry, "2022-11-25");
  ASSERT_TRUE(scope.has_value()) << (scope.has_value() ? "" : scope.error().message());
  const auto clock = qr::SessionClock::from_session(scope.value().session());
  ASSERT_TRUE(clock.has_value());
  ASSERT_EQ(clock.value().expected_bar_count(), 210);
  const std::int64_t open = clock.value().open_b().ns() / qr::kNanosecondsPerMillisecond;
  constexpr std::int64_t kMinute = 60'000;
  EXPECT_EQ(classify_domain(clock.value(), open + 209 * kMinute), QuoteDomain::RTH);
  // The 13:00 close, not 16:00: an early close's after-hours window opens at
  // its own close and a 390-bar window here would admit three hours of
  // post-close tape as decision-time quotes.
  EXPECT_EQ(classify_domain(clock.value(), open + 210 * kMinute), QuoteDomain::AFTER_HOURS);
  EXPECT_EQ(classify_domain(clock.value(), open + (210 + 239) * kMinute), QuoteDomain::AFTER_HOURS);
  EXPECT_EQ(classify_domain(clock.value(), open + (210 + 240) * kMinute),
            QuoteDomain::OUTSIDE_DOMAIN);
}

TEST(DomainClassifier, ItIsTotalAndNeverAbortsOnAnOffDayOrMalformedOrAbsentStamp) {
  // design/DESIGN_SUBSTRATE.md section 6: "the same latent `?`-abort shape
  // exists in production reader.rs:1173 — the port must not copy it". Every
  // one of these inputs makes the reference's `to_frame_a_same_civil_day(..)?`
  // return Err and kill the pass; here each is a census row.
  const qr::SessionClock clock = clock_125();
  const std::int64_t open = open_ms_125();
  EXPECT_EQ(classify_domain(clock, open + qr::kMillisecondsPerDay), QuoteDomain::WRONG_CIVIL_DAY);
  EXPECT_EQ(classify_domain(clock, open - qr::kMillisecondsPerDay), QuoteDomain::WRONG_CIVIL_DAY);
  EXPECT_EQ(classify_domain(clock, std::nullopt), QuoteDomain::MISSING);
  // A stamp whose own ms->ns widening overflows i64.
  EXPECT_EQ(classify_domain(clock, INT64_MAX), QuoteDomain::MALFORMED);
}

}  // namespace
