// The value normalizations: u6 prices, the lot/share era, rights, retained
// text, date ordinals.
//
// SPEC: WP4 brief ("u6 normalization: cent->x10,000, dollar->round(x1e6)";
// "lot->share era law: NBBO sizes x100 before 2025-11-03 ... implement the law
// with SYNTHETIC two-era fixtures only") + reference semantics
// select_v2/src/sources/mod.rs:269-399 and corpus/src/reader.rs:1337-1351.
#include <gtest/gtest.h>

#include <cmath>
#include <limits>
#include <string>

#include "fixture_support.hpp"
#include "qr_sources/normalize.hpp"

namespace {

using qr::sources::ColumnForm;
using qr::sources::testing::literal_int;

TEST(U6, CentsAndMillsScaleByTheirOwnFactorAndDollarsRoundTiesEven) {
  // cent -> x10,000
  EXPECT_EQ(qr::sources::price_to_u6(ColumnForm::CentI32, 17139, 0.0).value(), 171'390'000);
  EXPECT_EQ(qr::sources::price_to_u6(ColumnForm::CentI64, 1, 0.0).value(), 10'000);
  EXPECT_EQ(qr::sources::price_to_u6(ColumnForm::CentI32, 0, 0.0).value(), 0);
  EXPECT_EQ(qr::sources::price_to_u6(ColumnForm::CentI32, -5, 0.0).value(), -50'000);
  // mill -> x1,000 (the strike convention: 169000 mills == $169.00)
  EXPECT_EQ(qr::sources::price_to_u6(ColumnForm::MillI32, 169'000, 0.0).value(), 169'000'000);
  // dollar -> round(x1e6)
  EXPECT_EQ(qr::sources::dollars_to_u6(171.39).value(), 171'390'000);
  EXPECT_EQ(qr::sources::dollars_to_u6(0.0).value(), 0);
  EXPECT_EQ(qr::sources::dollars_to_u6(-1.5).value(), -1'500'000);
  // A price with more precision than u6 carries rounds; it never truncates.
  EXPECT_EQ(qr::sources::dollars_to_u6(171.3900004).value(), 171'390'000);
  EXPECT_EQ(qr::sources::dollars_to_u6(171.3900006).value(), 171'390'001);
}

TEST(U6, TheRoundingLawIsTiesToEvenAndIsIndependentOfTheFpuMode) {
  // No dollar value can make `value * 1e6` land EXACTLY on a half-integer (the
  // scale is 2^7 * 15625, so the required operand is not a binary fraction), so
  // the tie law is asserted on the primitive itself, at exactly representable
  // inputs.
  EXPECT_EQ(qr::sources::round_ties_even(0.5), 0.0);
  EXPECT_EQ(qr::sources::round_ties_even(1.5), 2.0);
  EXPECT_EQ(qr::sources::round_ties_even(2.5), 2.0);
  EXPECT_EQ(qr::sources::round_ties_even(3.5), 4.0);
  EXPECT_EQ(qr::sources::round_ties_even(-0.5), -0.0);
  EXPECT_EQ(qr::sources::round_ties_even(-1.5), -2.0);
  EXPECT_EQ(qr::sources::round_ties_even(-2.5), -2.0);
  EXPECT_EQ(qr::sources::round_ties_even(2.4999999999999996), 2.0);
  EXPECT_EQ(qr::sources::round_ties_even(2.5000000000000004), 3.0);
  EXPECT_EQ(qr::sources::round_ties_even(7.0), 7.0);
}

TEST(U6, NonFiniteAndUnrepresentableDollarsRefuseInsteadOfSubstituting) {
  for (const double bad : {std::numeric_limits<double>::quiet_NaN(),
                           std::numeric_limits<double>::infinity(),
                           -std::numeric_limits<double>::infinity(), 1e300, -1e300}) {
    const auto refused = qr::sources::dollars_to_u6(bad);
    ASSERT_FALSE(refused.has_value()) << bad;
    EXPECT_EQ(refused.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
  }
  // A form that is not a price form is a programmer error, and it refuses too.
  EXPECT_FALSE(qr::sources::price_to_u6(ColumnForm::TextUtf8, 1, 1.0).has_value());
}

TEST(ShareEra, TheBreakIsExactlyTwoThousandTwentyFiveNovemberThird) {
  // The synthetic two-era pair. FINAL_PLAN B7 puts the real era-break sessions
  // past the scope wall, so the LAW is proven here and no payload from it is
  // ever opened.
  EXPECT_EQ(qr::sources::kShareEraFirstDay, "2025-11-03");
  for (const char* day : {"2022-07-05", "2025-10-31"}) {
    EXPECT_EQ(qr::sources::nbbo_size_to_shares(7, day).value(),
              literal_int(std::string("share_era/") + day + "/lots7"))
        << day;
    EXPECT_EQ(qr::sources::nbbo_size_to_shares(7, day).value(), 700) << day;
  }
  for (const char* day : {"2025-11-03", "2025-12-31"}) {
    EXPECT_EQ(qr::sources::nbbo_size_to_shares(7, day).value(),
              literal_int(std::string("share_era/") + day + "/lots7"))
        << day;
    EXPECT_EQ(qr::sources::nbbo_size_to_shares(7, day).value(), 7) << day;
  }
  // The boundary is the first SHARE day, so the day before it is still lots.
  EXPECT_EQ(qr::sources::nbbo_size_to_shares(1, "2025-11-02").value(), 100);
  EXPECT_EQ(qr::sources::nbbo_size_to_shares(1, "2025-11-03").value(), 1);
}

TEST(ShareEra, NegativeSizesPassThroughAndOverflowRefusesInsteadOfSaturating) {
  EXPECT_EQ(qr::sources::nbbo_size_to_shares(-3, "2022-07-05").value(), -3);
  EXPECT_EQ(qr::sources::nbbo_size_to_shares(-3, "2025-12-31").value(), -3);
  EXPECT_EQ(qr::sources::nbbo_size_to_shares(0, "2022-07-05").value(), 0);

  // The reference saturates here; FINAL_PLAN section 6 bans that, so the port
  // REFUSES. Saturation would have produced i64::MAX — a number, silently.
  const auto refused =
      qr::sources::nbbo_size_to_shares(std::numeric_limits<std::int64_t>::max(), "2022-07-05");
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::ARITHMETIC_OVERFLOW);
}

TEST(Rights, ParseTheFrozenTokenSetAndKeepUnknownTokensOther) {
  EXPECT_EQ(qr::sources::parse_right("CALL"), qr::sources::Right::Call);
  EXPECT_EQ(qr::sources::parse_right("C"), qr::sources::Right::Call);
  EXPECT_EQ(qr::sources::parse_right("call"), qr::sources::Right::Call);
  EXPECT_EQ(qr::sources::parse_right("PUT"), qr::sources::Right::Put);
  EXPECT_EQ(qr::sources::parse_right("P"), qr::sources::Right::Put);
  EXPECT_EQ(qr::sources::parse_right("put"), qr::sources::Right::Put);
  // Anything else stays Other rather than being folded into a side.
  for (const char* token : {"", "CAL", "Call", "PUTS", "X", "0", "1"}) {
    EXPECT_EQ(qr::sources::parse_right(token), qr::sources::Right::Other) << token;
  }
}

TEST(RetainedText, FitsTheMeasuredStampAndRefusesRatherThanTruncate) {
  // The measured underlying_timestamp of the compact print profile.
  const auto stamp = qr::sources::inline_text("2022-07-05T09:30:00.000");
  ASSERT_TRUE(stamp.has_value());
  EXPECT_EQ(stamp.value().view(), "2022-07-05T09:30:00.000");
  EXPECT_EQ(stamp.value().size, 23);

  const auto empty = qr::sources::inline_text("");
  ASSERT_TRUE(empty.has_value());
  EXPECT_EQ(empty.value().view(), "");

  const std::string at_capacity(qr::sources::kInlineTextCapacity, 'x');
  EXPECT_TRUE(qr::sources::inline_text(at_capacity).has_value());
  const std::string too_long(qr::sources::kInlineTextCapacity + 1, 'x');
  const auto refused = qr::sources::inline_text(too_long);
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}

TEST(Dates, TheOrdinalAndTheIsoTextFormsAgreeAndMalformedTextRefuses) {
  // 2022-07-08 is day ordinal 19181 (the fixture's expiry A).
  EXPECT_EQ(qr::sources::date_to_day_ordinal(ColumnForm::DateI32, 19181, {}).value(), 19181);
  EXPECT_EQ(qr::sources::date_to_day_ordinal(ColumnForm::DateText, 0, "2022-07-08").value(),
            19181);
  EXPECT_EQ(qr::sources::date_to_day_ordinal(ColumnForm::DateText, 0, "1970-01-01").value(), 0);
  for (const char* bad : {"2022-7-8", "20220708", "2022-13-01", "2022-02-30", "", "not-a-date"}) {
    const auto refused = qr::sources::date_to_day_ordinal(ColumnForm::DateText, 0, bad);
    ASSERT_FALSE(refused.has_value()) << bad;
    EXPECT_EQ(refused.error().code(), qr::RefusalCode::MALFORMED_CIVIL_DATE) << bad;
  }
}

TEST(Midpoint, IsComputedFromBothSidesAndNeverReadFromTheVendorColumn) {
  // The vendor `mid` is bid+ask in the compact profile and the true midpoint in
  // the wide one, which is why it is walled in every spec that has it.
  EXPECT_EQ(qr::sources::midpoint_u6(171'390'000, 171'490'000), 171'440'000);
  EXPECT_EQ(qr::sources::midpoint_u6(1, 2), 1);
  EXPECT_EQ(qr::sources::midpoint_u6(0, 0), 0);
  EXPECT_EQ(qr::sources::midpoint_u6(-4, 2), -1);
}

}  // namespace
