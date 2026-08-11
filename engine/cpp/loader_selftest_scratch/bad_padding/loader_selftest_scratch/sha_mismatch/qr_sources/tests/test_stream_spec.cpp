// The three walls of qr_sources: the compile-time spec laws, the open-time
// schema gate, and the decode-time forbidden door.
//
// SPEC: FINAL_PLAN APPENDIX B1-B4 (the projections and refusals asserted here
// are transcribed from the appendix, index by index) + design/DESIGN_SUBSTRATE
// APPENDIX C3 ("compile-time asserts", "open refuses wrong schema pre-payload").
#include <gtest/gtest.h>

#include <array>
#include <string>
#include <vector>

#include "fixture_support.hpp"
#include "qr_sources/option_prints.hpp"
#include "qr_sources/option_quotes.hpp"
#include "qr_sources/stock_quotes.hpp"
#include "qr_sources/stock_trades.hpp"
#include "qr_sources/stream_spec.hpp"

namespace {

using qr::sources::ColumnForm;
using qr::sources::ForbidReason;
using qr::sources::SpecView;
using qr::sources::testing::fixture_root;
using qr::sources::testing::scope_125;

std::filesystem::path fixture_file(const std::string& tree) {
  return fixture_root(tree) / "2022" / "2022-07-05.parquet";
}

qr::parquet::FileExpected<qr::parquet::File> open_fixture(const std::string& tree) {
  return qr::parquet::File::open(fixture_file(tree).string());
}

// --- the compile-time laws, mirrored as runtime assertions -----------------
// `spec_is_wellformed` is asserted at COMPILE time on all four specs (see
// stream_spec.hpp). These cases prove the predicate is not vacuous: each bad
// spec below is rejected, and ci/check_compile_fail.sh proves the same specs
// fail to compile when they carry a static_assert.

constexpr qr::sources::StreamSpec<4, 2, 1> kProjectsAForbiddenLeaf{
    .stream = "bad",
    .names = {"ts", "a", "b", "c"},
    .projection = {0, 2},
    .roles = {qr::sources::ColumnRole::TimestampMs, qr::sources::ColumnRole::Int},
    .forbidden = {qr::sources::ForbiddenColumn{2, ForbidReason::NeverRead}},
    .timestamp_leaf = 0,
};
constexpr qr::sources::StreamSpec<4, 2, 0> kUnsortedProjection{
    .stream = "bad",
    .names = {"ts", "a", "b", "c"},
    .projection = {2, 0},
    .roles = {qr::sources::ColumnRole::Int, qr::sources::ColumnRole::TimestampMs},
    .forbidden = {},
    .timestamp_leaf = 0,
};
constexpr qr::sources::StreamSpec<4, 2, 0> kProjectionPastTheNames{
    .stream = "bad",
    .names = {"ts", "a", "b", "c"},
    .projection = {0, 9},
    .roles = {qr::sources::ColumnRole::TimestampMs, qr::sources::ColumnRole::Int},
    .forbidden = {},
    .timestamp_leaf = 0,
};
constexpr qr::sources::StreamSpec<4, 2, 0> kDuplicateNames{
    .stream = "bad",
    .names = {"ts", "a", "a", "c"},
    .projection = {0, 1},
    .roles = {qr::sources::ColumnRole::TimestampMs, qr::sources::ColumnRole::Int},
    .forbidden = {},
    .timestamp_leaf = 0,
};
constexpr qr::sources::StreamSpec<4, 2, 0> kClockLeafNotProjected{
    .stream = "bad",
    .names = {"ts", "a", "b", "c"},
    .projection = {1, 2},
    .roles = {qr::sources::ColumnRole::Int, qr::sources::ColumnRole::Int},
    .forbidden = {},
    .timestamp_leaf = 0,
};

TEST(SpecLaws, EveryPinnedSpecIsWellformedAndEveryBrokenOneIsRejected) {
  // The four pinned specs are asserted at COMPILE time in stream_spec.hpp
  // itself; the negative half of the law ("a broken spec does not compile") is
  // ci/check_compile_fail.sh's, because a static_assert that fires produces a
  // build error rather than a test failure, and the red-ledger law needs a
  // FAILING TEST. What is checked here is that the predicate is not vacuous.
  EXPECT_FALSE(spec_is_wellformed(kProjectsAForbiddenLeaf));
  EXPECT_FALSE(spec_is_wellformed(kUnsortedProjection));
  EXPECT_FALSE(spec_is_wellformed(kProjectionPastTheNames));
  EXPECT_FALSE(spec_is_wellformed(kDuplicateNames));
  EXPECT_FALSE(spec_is_wellformed(kClockLeafNotProjected));
  // The disjointness law is the one the brief names explicitly.
  EXPECT_FALSE(projection_and_forbidden_are_disjoint(kProjectsAForbiddenLeaf));
  EXPECT_TRUE(projection_and_forbidden_are_disjoint(qr::sources::kOptionPrintSpec));
}

TEST(SpecLaws, TheFourProjectionsAreExactlyAppendixB) {
  // B1: 16 columns, project 0..8; 9-15 NEVER READ.
  const std::vector<std::size_t> quotes(qr::sources::kStockQuoteSpec.projection.begin(),
                                        qr::sources::kStockQuoteSpec.projection.end());
  EXPECT_EQ(quotes, (std::vector<std::size_t>{0, 1, 2, 3, 4, 5, 6, 7, 8}));
  EXPECT_EQ(qr::sources::kStockQuoteSpec.names.size(), 16U);

  // B2: 24 columns, V4 projects 19 (0..18).
  const std::vector<std::size_t> trades(qr::sources::kStockTradeSpec.projection.begin(),
                                        qr::sources::kStockTradeSpec.projection.end());
  EXPECT_EQ(trades, (std::vector<std::size_t>{0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
                                              16, 17, 18}));
  EXPECT_EQ(qr::sources::kStockTradeSpec.names.size(), 24U);

  // B3: 62 columns, the ADDENDUM 20.
  const std::vector<std::size_t> prints(qr::sources::kOptionPrintSpec.projection.begin(),
                                        qr::sources::kOptionPrintSpec.projection.end());
  EXPECT_EQ(prints, (std::vector<std::size_t>{1, 2, 3, 4, 5, 10, 11, 13, 14, 20, 21, 22, 34, 36, 37,
                                              39, 40, 42, 43, 45}));
  EXPECT_EQ(qr::sources::kOptionPrintSpec.names.size(), 62U);
  EXPECT_EQ(prints.size(), 20U);

  // B4: 19 columns, 8 projected.
  const std::vector<std::size_t> option_quotes(qr::sources::kOptionQuoteSpec.projection.begin(),
                                               qr::sources::kOptionQuoteSpec.projection.end());
  EXPECT_EQ(option_quotes, (std::vector<std::size_t>{1, 2, 3, 4, 5, 7, 9, 11}));
  EXPECT_EQ(qr::sources::kOptionQuoteSpec.names.size(), 19U);
}

TEST(SpecLaws, TheWalledColumnsAreExactlyAppendixB) {
  const SpecView quotes = view_of(qr::sources::kStockQuoteSpec);
  for (std::size_t leaf = 9; leaf <= 15; ++leaf) {
    ASSERT_NE(quotes.forbids(leaf), nullptr) << "B1 walls column " << leaf;
    EXPECT_EQ(quotes.forbids(leaf)->reason, ForbidReason::NeverRead);
  }
  // `mid` and `spread_bps` are in that block by name, which is what the
  // scalar-means-before-derived law is about.
  EXPECT_EQ(quotes.names()[14], "mid");
  EXPECT_EQ(quotes.names()[15], "spread_bps");

  const SpecView trades = view_of(qr::sources::kStockTradeSpec);
  for (const std::size_t leaf : {19U, 20U, 21U, 23U}) {
    ASSERT_NE(trades.forbids(leaf), nullptr);
    EXPECT_EQ(trades.forbids(leaf)->reason, ForbidReason::NeverRead);
  }
  ASSERT_NE(trades.forbids(22), nullptr);
  EXPECT_EQ(trades.forbids(22)->reason, ForbidReason::DecodeRefused);
  EXPECT_EQ(trades.names()[22], qr::sources::kPriceLead1Name);

  const SpecView prints = view_of(qr::sources::kOptionPrintSpec);
  for (const std::size_t leaf : {38U, 47U, 48U, 49U, 50U, 53U, 54U, 55U, 56U, 57U, 58U, 59U, 60U,
                                 61U}) {
    ASSERT_NE(prints.forbids(leaf), nullptr) << "B3 hard-refuses column " << leaf;
    EXPECT_EQ(prints.forbids(leaf)->reason, ForbidReason::HardRefused);
  }
  // "unlisted Greeks" — every greek B3 does not name.
  for (const std::size_t leaf : {15U, 17U, 18U, 19U, 23U, 24U, 25U, 26U, 27U, 28U, 29U, 30U, 31U,
                                 32U, 33U}) {
    EXPECT_NE(prints.forbids(leaf), nullptr) << "unlisted greek " << prints.names()[leaf];
  }
  // vega(16) is the REGISTERED W2.4 extension: unprojected, but not walled.
  EXPECT_EQ(prints.names()[16], "vega");
  EXPECT_EQ(prints.forbids(16), nullptr);
  EXPECT_FALSE(prints.projects(16));

  // B4 walls the WHOLE derived family (orchestrator ruling 2026-08-10: B1's
  // never-read law extended to the option-quote analogues), `mid` included.
  const SpecView option_quotes = view_of(qr::sources::kOptionQuoteSpec);
  const std::array<std::string_view, 6> derived{"d_bid_size", "d_ask_size", "bid_px_chg",
                                                "ask_px_chg", "dt_prev_contract_ms", "mid"};
  for (std::size_t leaf = 13; leaf <= 18; ++leaf) {
    EXPECT_EQ(option_quotes.names()[leaf], derived[leaf - 13]);
    ASSERT_NE(option_quotes.forbids(leaf), nullptr) << "B4 walls column " << leaf;
    EXPECT_EQ(option_quotes.forbids(leaf)->reason, ForbidReason::NeverRead);
    EXPECT_FALSE(option_quotes.projects(leaf));
  }
  EXPECT_EQ(option_quotes.forbidden().size(), 6U);
}

TEST(SpecLaws, TheSingleLegPrintConditionSetIsExposedAsAField) {
  // B3: "condition(10) [single-leg in {18,95,125,126}]". WP4 exposes the set;
  // WP8 applies it.
  EXPECT_EQ(qr::sources::kSingleLegPrintConditions,
            (std::array<std::int64_t, 4>{18, 95, 125, 126}));
  for (const std::int64_t admitted : {18, 95, 125, 126}) {
    EXPECT_TRUE(qr::sources::is_single_leg_print_condition(admitted));
  }
  for (const std::int64_t other : {0, 17, 19, 94, 96, 124, 127, 130}) {
    EXPECT_FALSE(qr::sources::is_single_leg_print_condition(other));
  }
}

// --- the open-time gate -----------------------------------------------------

TEST(SchemaGate, TheGoodFixtureGatesAndResolvesEveryProjectedForm) {
  const auto opened = open_fixture("sq_cent");
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const auto forms = gate_schema(view_of(qr::sources::kStockQuoteSpec), opened.value(),
                                 qr::sources::stock_quote_forms(qr::SourceProfile::CentInt32));
  ASSERT_TRUE(forms.has_value()) << forms.error().message();
  EXPECT_EQ(forms.value().size(), 9U);
  EXPECT_EQ(forms.value()[0], ColumnForm::TimestampMsI64);
  EXPECT_EQ(forms.value()[3], ColumnForm::CentI32);
  EXPECT_EQ(forms.value()[7], ColumnForm::CentI32);
}

TEST(SchemaGate, ARenamedColumnRefusesByNameBeforeAnyPayload) {
  const auto opened = open_fixture("sq_renamed");
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const auto forms = gate_schema(view_of(qr::sources::kStockQuoteSpec), opened.value(),
                                 qr::sources::stock_quote_forms(qr::SourceProfile::CentInt32));
  ASSERT_FALSE(forms.has_value());
  EXPECT_EQ(forms.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
  EXPECT_NE(forms.error().detail().find("bid_price"), std::string::npos)
      << forms.error().message();
  EXPECT_NE(forms.error().message().find("sq_renamed"), std::string::npos);
}

TEST(SchemaGate, AWrongPhysicalTypeRefusesByName) {
  // `bid_size` written as INT64 in a file whose registry row declares
  // cent_int32 (where every size is INT32).
  const auto opened = open_fixture("sq_wrongtype");
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const auto forms = gate_schema(view_of(qr::sources::kStockQuoteSpec), opened.value(),
                                 qr::sources::stock_quote_forms(qr::SourceProfile::CentInt32));
  ASSERT_FALSE(forms.has_value());
  EXPECT_EQ(forms.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
  EXPECT_NE(forms.error().detail().find("bid_size"), std::string::npos)
      << forms.error().message();
}

TEST(SchemaGate, AColumnCountDriftRefusesBeforeAnyNameIsCompared) {
  // An option-quote file (19 columns) handed to the 16-column stock-quote pin.
  const auto opened = open_fixture("oq_flat");
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const auto forms = gate_schema(view_of(qr::sources::kStockQuoteSpec), opened.value(),
                                 qr::sources::stock_quote_forms(qr::SourceProfile::CentInt32));
  ASSERT_FALSE(forms.has_value());
  EXPECT_EQ(forms.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
  EXPECT_NE(forms.error().detail().find("19 columns"), std::string::npos)
      << forms.error().message();
}

TEST(SchemaGate, TheDeclaredProfileIsTheAuthorityOverTheFilesOwnForms) {
  // A file whose PRICES are dollars while its registry row declares cents.
  // Every name matches and every other column is the cent profile, so only the
  // form pin can catch it — and the refusal names `bid`.
  const auto prices = open_fixture("sq_dollar_prices");
  ASSERT_TRUE(prices.has_value()) << prices.error().message();
  const auto price_mismatch =
      gate_schema(view_of(qr::sources::kStockQuoteSpec), prices.value(),
                  qr::sources::stock_quote_forms(qr::SourceProfile::CentInt32));
  ASSERT_FALSE(price_mismatch.has_value());
  EXPECT_EQ(price_mismatch.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
  EXPECT_NE(price_mismatch.error().detail().find("DOLLAR_F64"), std::string::npos)
      << price_mismatch.error().message();
  EXPECT_NE(price_mismatch.error().detail().find("stock_quotes.bid "), std::string::npos)
      << price_mismatch.error().message();

  // The whole dollar-profile file gated against the cent pin: the first column
  // that disagrees is the one named, and here that is `bid_size`.
  const auto opened = open_fixture("sq_dollar");
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const auto as_cent = gate_schema(view_of(qr::sources::kStockQuoteSpec), opened.value(),
                                   qr::sources::stock_quote_forms(qr::SourceProfile::CentInt32));
  ASSERT_FALSE(as_cent.has_value());
  EXPECT_EQ(as_cent.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
  EXPECT_NE(as_cent.error().detail().find("bid_size"), std::string::npos)
      << as_cent.error().message();

  const auto as_dollar = gate_schema(
      view_of(qr::sources::kStockQuoteSpec), opened.value(),
      qr::sources::stock_quote_forms(qr::SourceProfile::DollarFloat64));
  ASSERT_TRUE(as_dollar.has_value()) << as_dollar.error().message();
  EXPECT_EQ(as_dollar.value()[3], ColumnForm::DollarF64);
  EXPECT_EQ(as_dollar.value()[1], ColumnForm::IntI64);
}

TEST(SchemaGate, TheDeferredRutwWideProfileIsRefusedByTheCompactPrintReader) {
  // B5 is deferred, and the deferral is a wall: same 62 names, different forms.
  const auto opened = open_fixture("op_wide");
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const auto forms =
      gate_schema(view_of(qr::sources::kOptionPrintSpec), opened.value(),
                  std::span<const ColumnForm>(qr::sources::kOptionPrintFormsIwmCompact));
  ASSERT_FALSE(forms.has_value());
  EXPECT_EQ(forms.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
  EXPECT_NE(forms.error().detail().find("expiration"), std::string::npos)
      << forms.error().message();

  const auto compact = open_fixture("op_compact");
  ASSERT_TRUE(compact.has_value()) << compact.error().message();
  const auto good =
      gate_schema(view_of(qr::sources::kOptionPrintSpec), compact.value(),
                  std::span<const ColumnForm>(qr::sources::kOptionPrintFormsIwmCompact));
  ASSERT_TRUE(good.has_value()) << good.error().message();
}

TEST(SchemaGate, BothOptionQuoteProfilesAreDetectedFromTheFilesOwnSchema) {
  const auto flat = open_fixture("oq_flat");
  ASSERT_TRUE(flat.has_value()) << flat.error().message();
  const auto compact = qr::sources::check_option_quote_schema(flat.value());
  ASSERT_TRUE(compact.has_value()) << compact.error().message();
  EXPECT_EQ(compact.value().forms[0], ColumnForm::DateI32);
  EXPECT_EQ(compact.value().forms[1], ColumnForm::MillI32);
  EXPECT_EQ(compact.value().forms[5], ColumnForm::CentI32);
  EXPECT_EQ(compact.value().num_leaves, 19U);

  const std::filesystem::path shard =
      fixture_root("oq_sharded") / "2022" / "2022-07-05" / "exp2022-07-08.parquet";
  const auto wide_file = qr::parquet::File::open(shard.string());
  ASSERT_TRUE(wide_file.has_value()) << wide_file.error().message();
  const auto wide = qr::sources::check_option_quote_schema(wide_file.value());
  ASSERT_TRUE(wide.has_value()) << wide.error().message();
  EXPECT_EQ(wide.value().forms[0], ColumnForm::DateText);
  EXPECT_EQ(wide.value().forms[1], ColumnForm::DollarF64);
  EXPECT_EQ(wide.value().forms[5], ColumnForm::DollarF64);
}

// --- the decode-time door ---------------------------------------------------

TEST(ForbiddenDoor, PriceLeadOneRefusesByNameAndByIndexWithoutTouchingItsBytes) {
  const auto opened = open_fixture("st_good");
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const SpecView spec = view_of(qr::sources::kStockTradeSpec);
  qr::parquet::DecodeWorkspace workspace;
  qr::parquet::ColumnData column;

  const auto by_name = read_pinned_column_named(spec, opened.value(), 0,
                                                qr::sources::kPriceLead1Name, workspace, column);
  ASSERT_FALSE(by_name.has_value());
  EXPECT_EQ(by_name.error().code(), qr::RefusalCode::COLUMN_FORBIDDEN);
  EXPECT_NE(by_name.error().detail().find("price_lead_1"), std::string::npos);
  EXPECT_NE(by_name.error().detail().find("DECODE_REFUSED"), std::string::npos);
  EXPECT_EQ(column.num_rows, 0) << "a refused column must not have been decoded";

  const auto by_index = read_pinned_column(spec, opened.value(), 0, 22, workspace, column);
  ASSERT_FALSE(by_index.has_value());
  EXPECT_EQ(by_index.error().code(), qr::RefusalCode::COLUMN_FORBIDDEN);
  EXPECT_EQ(by_index.error().context(), 22);
  EXPECT_EQ(column.num_rows, 0);

  // The same door DOES open for a projected column, so the refusal above is
  // the wall and not a broken reader.
  const auto projected = read_pinned_column(spec, opened.value(), 0, 10, workspace, column);
  ASSERT_TRUE(projected.has_value()) << projected.error().message();
  EXPECT_GT(column.num_rows, 0);
}

TEST(ForbiddenDoor, EveryWalledColumnOfEveryStreamRefusesOnARealFixtureFile) {
  struct Case {
    const char* tree;
    SpecView spec;
  };
  const std::array<Case, 4> cases{
      Case{"sq_cent", view_of(qr::sources::kStockQuoteSpec)},
      Case{"st_good", view_of(qr::sources::kStockTradeSpec)},
      Case{"op_compact", view_of(qr::sources::kOptionPrintSpec)},
      Case{"oq_flat", view_of(qr::sources::kOptionQuoteSpec)},
  };
  for (const Case& one : cases) {
    const auto opened = open_fixture(one.tree);
    ASSERT_TRUE(opened.has_value()) << one.tree << ": " << opened.error().message();
    qr::parquet::DecodeWorkspace workspace;
    qr::parquet::ColumnData column;
    for (const qr::sources::ForbiddenColumn& walled : one.spec.forbidden()) {
      const auto refused =
          read_pinned_column(one.spec, opened.value(), 0, walled.leaf, workspace, column);
      ASSERT_FALSE(refused.has_value())
          << one.spec.stream() << " leaf " << walled.leaf << " was decoded";
      EXPECT_EQ(refused.error().code(), qr::RefusalCode::COLUMN_FORBIDDEN);
      EXPECT_NE(refused.error().detail().find(std::string(one.spec.names()[walled.leaf])),
                std::string::npos);
    }
  }
}

TEST(ForbiddenDoor, AnUnprojectedButUnwalledColumnIsRefusedAsOutsideTheProjection) {
  const auto opened = open_fixture("op_compact");
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const SpecView spec = view_of(qr::sources::kOptionPrintSpec);
  qr::parquet::DecodeWorkspace workspace;
  qr::parquet::ColumnData column;

  // vega(16): a registered future extension, not a wall — so the refusal says
  // "outside the projection", not COLUMN_FORBIDDEN.
  const auto vega = read_pinned_column(spec, opened.value(), 0, 16, workspace, column);
  ASSERT_FALSE(vega.has_value());
  EXPECT_EQ(vega.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
  EXPECT_NE(vega.error().detail().find("vega"), std::string::npos);

  // symbol(0): simply not projected.
  const auto symbol = read_pinned_column(spec, opened.value(), 0, 0, workspace, column);
  ASSERT_FALSE(symbol.has_value());
  EXPECT_EQ(symbol.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);

  // A leaf past the schema, and an unknown name.
  const auto past = read_pinned_column(spec, opened.value(), 0, 62, workspace, column);
  ASSERT_FALSE(past.has_value());
  EXPECT_EQ(past.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
  const auto unknown =
      read_pinned_column_named(spec, opened.value(), 0, "not_a_column", workspace, column);
  ASSERT_FALSE(unknown.has_value());
  EXPECT_EQ(unknown.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
}

}  // namespace
