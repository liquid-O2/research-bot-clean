// B5 — the RUTW option-print reader, red-first.
//
// SPEC: FINAL_PLAN APPENDIX B5 ("RUTW prints: same 62-name wide profile; same
// laws; registry-session wall (W2.12)") standing on APPENDIX B3's column law,
// and design/DESIGN_SUBSTRATE APPENDIX C3 ("open refuses wrong schema
// pre-payload").
//
// Every expected number here comes from tests/fixtures/source_expected_literals.tsv,
// which make_source_fixtures.py derives from the values it ENCODES — including
// the census columns, which the generator recomputes in Python from its own
// encoded rows. The C++ side computes none of them a second way.
//
// NOT RE-TESTED HERE (the repository law forbids a second copy of an existing
// proof): the u6 rounding law (qr_sources `U6.*`), the equal-time group machine
// (`GroupTape.*`), and the 125..749 scope wall itself (qr_registry
// `ScopeWall.*`). What IS tested here is that B5's reader stands behind them.
#include <gtest/gtest.h>

#include <algorithm>
#include <cstdint>
#include <string>
#include <utility>
#include <vector>

#include "fixture_support.hpp"
#include "qr_registry/registry.hpp"
#include "qr_sources/option_prints.hpp"
#include "qr_sources/rutw_prints.hpp"
#include "qr_sources/stream_spec.hpp"

namespace {

using qr::sources::testing::fixture_root;
using qr::sources::testing::literal_int;
using qr::sources::testing::literal_text;
using qr::sources::testing::scope_125;

/// The lawful RUTW corpus root of the fixture tree: it carries the `RUTW`
/// path component, which is the modality both walls test.
std::filesystem::path rutw_fixture(const std::string& tree) {
  return fixture_root("RUTW") / tree;
}

/// Every admitted row of the fixture session, flattened in delivery order.
std::vector<qr::sources::OptionPrintRow> read_all(qr::sources::RutwPrintReader& reader,
                                                  std::vector<std::int64_t>* stamps = nullptr,
                                                  std::vector<std::size_t>* widths = nullptr) {
  std::vector<qr::sources::OptionPrintRow> rows;
  qr::sources::RutwPrintReader::Group group;
  while (true) {
    const auto more = reader.next_group(group);
    EXPECT_TRUE(more.has_value()) << more.error().message();
    if (!more.has_value() || !more.value()) {
      break;
    }
    if (stamps != nullptr) {
      stamps->push_back(group.ts_ms_b);
    }
    if (widths != nullptr) {
      widths->push_back(group.rows.size());
    }
    rows.insert(rows.end(), group.rows.begin(), group.rows.end());
  }
  return rows;
}

/// The one admitted row carrying `strike_u6`, for the per-row literal checks.
/// Rows inside an equal-millisecond group are canonically ordered, so a test
/// may not index into a group — it must look a row up by its identity.
const qr::sources::OptionPrintRow* row_with_strike(
    const std::vector<qr::sources::OptionPrintRow>& rows, std::int64_t strike_u6,
    std::int64_t condition) {
  for (const qr::sources::OptionPrintRow& row : rows) {
    if (row.strike_u6 == strike_u6 && row.condition == condition) {
      return &row;
    }
  }
  return nullptr;
}

}  // namespace

// ---------------------------------------------------------------------------
// The column law — B5 IS B3, at compile time.
// ---------------------------------------------------------------------------

TEST(RutwPrints, TheColumnLawIsByteForByteAppendixB3s) {
  // B5: "same 62-name wide profile; same laws". The spec pair asserts that at
  // COMPILE time (stream_spec.hpp); this proves the predicate is not vacuous
  // and that the two specs really are distinguishable in a refusal.
  const qr::sources::SpecView rutw = view_of(qr::sources::kRutwPrintSpec);
  const qr::sources::SpecView iwm = view_of(qr::sources::kOptionPrintSpec);
  ASSERT_EQ(rutw.names().size(), 62U);
  ASSERT_EQ(rutw.projection().size(), 31U);
  ASSERT_EQ(rutw.forbidden().size(), 20U);
  EXPECT_NE(rutw.stream(), iwm.stream());
  // THE CLOCK LEAF IS 4 IN BOTH PROFILES, and it is 4 because leaf 4 IS
  // `timestamp` in the shared 62-name layout. The wide profile changes column
  // ENCODINGS (text expiration, Float64 prices, Int64 sizes), never column
  // INDICES — measured on the real corpus in all three profiles by the CC-013
  // column census, which resolves every leaf BY NAME and reported identical
  // indices for IWM-compact, IWM-wide and RUTW-wide. Leaf 45 is the ATTACHMENT
  // clock (`quote_timestamp`), a different column with a different job, and
  // pinning both names here is what keeps the two from ever being confused.
  EXPECT_EQ(rutw.timestamp_leaf(), iwm.timestamp_leaf());
  EXPECT_EQ(rutw.timestamp_leaf(), 4U);
  EXPECT_EQ(rutw.names()[4], "timestamp");
  EXPECT_EQ(rutw.names()[45], "quote_timestamp");
  for (std::size_t index = 0; index < rutw.names().size(); ++index) {
    EXPECT_EQ(rutw.names()[index], iwm.names()[index]) << "name " << index;
  }
  for (std::size_t index = 0; index < rutw.projection().size(); ++index) {
    EXPECT_EQ(rutw.projection()[index], iwm.projection()[index]) << "projected " << index;
    EXPECT_EQ(rutw.roles()[index], iwm.roles()[index]) << "role " << index;
  }
  for (std::size_t index = 0; index < rutw.forbidden().size(); ++index) {
    EXPECT_EQ(rutw.forbidden()[index].leaf, iwm.forbidden()[index].leaf) << "walled " << index;
    EXPECT_EQ(rutw.forbidden()[index].reason, iwm.forbidden()[index].reason) << "walled " << index;
  }
  EXPECT_TRUE(specs_share_the_column_law(qr::sources::kRutwPrintSpec,
                                         qr::sources::kOptionPrintSpec));
}

TEST(RutwPrints, EveryHardRefusedColumnOfTheRutwCorpusRefusesAtTheDecodeDoor) {
  // The B3 hard refusals are the point of the print reader, and B5 inherits
  // them. Proven on REAL RUTW bytes through the RUTW spec, so the wall is not
  // merely a table this stream never consults.
  const auto opened = qr::parquet::File::open(
      (rutw_fixture("rp_wide") / "2022" / "2022-07-05.parquet").string());
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const qr::sources::SpecView spec = view_of(qr::sources::kRutwPrintSpec);
  qr::parquet::DecodeWorkspace workspace;
  qr::parquet::ColumnData column;
  int hard_refused = 0;
  for (const qr::sources::ForbiddenColumn& walled : spec.forbidden()) {
    const auto refused = read_pinned_column(spec, opened.value(), 0, walled.leaf, workspace,
                                            column);
    ASSERT_FALSE(refused.has_value()) << "leaf " << walled.leaf << " was decoded";
    EXPECT_EQ(refused.error().code(), qr::RefusalCode::COLUMN_FORBIDDEN);
    EXPECT_NE(refused.error().detail().find(std::string(spec.names()[walled.leaf])),
              std::string::npos)
        << refused.error().message();
    hard_refused += walled.reason == qr::sources::ForbidReason::HardRefused ? 1 : 0;
  }
  // B3's SURVIVING list, inherited whole (CC-013 shrank it on both readers at
  // once or on neither — `specs_share_the_column_law` is a static_assert):
  // `side`, the four `sweep_*`, `prem`, `moneyness`, the eight `*_flow`s,
  // theta/rho/epsilon/lambda and d1/d2.
  EXPECT_EQ(hard_refused, 20);
}

// ---------------------------------------------------------------------------
// The lawful read.
// ---------------------------------------------------------------------------

TEST(RutwPrints, TheFixtureSessionMatchesEveryDerivedLiteral) {
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  auto opened = qr::sources::RutwPrintReader::open(*scope, rutw_fixture("rp_wide"));
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  qr::sources::RutwPrintReader reader = std::move(opened).value();

  std::vector<std::int64_t> stamps;
  std::vector<std::size_t> widths;
  const std::vector<qr::sources::OptionPrintRow> rows = read_all(reader, &stamps, &widths);

  EXPECT_EQ(reader.rth_rows(), literal_int("rutw_prints/*/rth_rows"));
  EXPECT_EQ(reader.group_count(), literal_int("rutw_prints/*/group_count"));
  EXPECT_EQ(reader.skipped_null_rows(), literal_int("rutw_prints/*/skipped_null_rows"));
  EXPECT_EQ(static_cast<std::int64_t>(reader.source().row_groups_total()),
            literal_int("rutw_prints/*/row_groups_total"));
  ASSERT_EQ(static_cast<std::int64_t>(stamps.size()), literal_int("rutw_prints/*/group_count"));
  for (std::size_t index = 0; index < stamps.size(); ++index) {
    const std::string key = "rutw_prints/group" + std::to_string(index) + "/";
    EXPECT_EQ(stamps[index], literal_int(key + "ts_ms_b")) << "group " << index;
    EXPECT_EQ(static_cast<std::int64_t>(widths[index]), literal_int(key + "rows"))
        << "group " << index;
  }

  // Row 2 — an ordinary wide print, every projected field against its literal.
  const qr::sources::OptionPrintRow* const row2 =
      row_with_strike(rows, literal_int("rutw_prints/row2/strike_u6"),
                      literal_int("rutw_prints/row2/condition"));
  ASSERT_NE(row2, nullptr);
  EXPECT_EQ(row2->price_u6, literal_int("rutw_prints/row2/price_u6"));
  EXPECT_EQ(row2->bid_u6, literal_int("rutw_prints/row2/bid_u6"));
  EXPECT_EQ(row2->ask_u6, literal_int("rutw_prints/row2/ask_u6"));
  EXPECT_EQ(row2->size, literal_int("rutw_prints/row2/size"));
  EXPECT_EQ(row2->bid_size, literal_int("rutw_prints/row2/bid_size"));
  EXPECT_EQ(row2->ask_size, literal_int("rutw_prints/row2/ask_size"));
  EXPECT_EQ(static_cast<std::int64_t>(row2->expiration_day),
            literal_int("rutw_prints/row2/expiration_day"));
  EXPECT_EQ(std::string(qr::sources::right_name(row2->right)),
            literal_text("rutw_prints/row2/right"));
  // B3's single-leg set is EXPOSED, not applied — B5 inherits that too.
  EXPECT_TRUE(row2->is_single_leg());
}

TEST(RutwPrints, TheWidePhysicalTypesDecodeAtTheirEdges) {
  // THE REASON B5 PINS THE WIDE PROFILE AND NOTHING ELSE. Row 4 of the fixture
  // carries values the compact profile CANNOT represent:
  //   * a RUT-scale strike whose u6 image overflows int32;
  //   * an Int64 print size past INT32_MAX, and an Int64 depth at exactly
  //     INT32_MAX + 1;
  //   * a Float64 price finer than a cent.
  // A reader that had kept any int32 pin would land on a different number.
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  auto opened = qr::sources::RutwPrintReader::open(*scope, rutw_fixture("rp_wide"));
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  qr::sources::RutwPrintReader reader = std::move(opened).value();
  const std::vector<qr::sources::OptionPrintRow> rows = read_all(reader);

  const std::int64_t strike = literal_int("rutw_prints/row4/strike_u6");
  const qr::sources::OptionPrintRow* const edge =
      row_with_strike(rows, strike, literal_int("rutw_prints/row4/condition"));
  ASSERT_NE(edge, nullptr);
  EXPECT_GT(strike, std::int64_t{2} << 30) << "the strike must exceed the int32 range";
  EXPECT_EQ(edge->size, literal_int("rutw_prints/row4/size"));
  EXPECT_GT(edge->size, std::int64_t{2147483647});
  EXPECT_EQ(edge->bid_size, literal_int("rutw_prints/row4/bid_size"));
  EXPECT_EQ(edge->bid_size, std::int64_t{2147483648});
  EXPECT_EQ(edge->ask_size, literal_int("rutw_prints/row4/ask_size"));
  // Sub-cent prices: a cent-scaled pin would have rounded these away.
  EXPECT_EQ(edge->price_u6, literal_int("rutw_prints/row4/price_u6"));
  EXPECT_NE(edge->price_u6 % qr::sources::kU6PerCent, 0);
  EXPECT_EQ(edge->bid_u6, literal_int("rutw_prints/row4/bid_u6"));
  EXPECT_EQ(edge->ask_u6, literal_int("rutw_prints/row4/ask_u6"));
  // The wide `expiration` is ISO TEXT and still lands as a day ordinal.
  EXPECT_EQ(static_cast<std::int64_t>(edge->expiration_day),
            literal_int("rutw_prints/row4/expiration_day"));
}

// ---------------------------------------------------------------------------
// The two-way wall.
// ---------------------------------------------------------------------------

TEST(RutwPrints, IwmCompactBytesUnderARutwRootAreRefusedByTheProfilePin) {
  // The MODALITY pin passes here (the root names RUTW) and the PROFILE pin is
  // what refuses: B5 is the wide encoding and only the wide encoding, so a
  // compact `expiration` (a DATE ordinal against a UTF-8 pin) is refused by
  // name, before a payload byte is read.
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  const auto opened = qr::sources::RutwPrintReader::open(*scope, rutw_fixture("rp_compact"));
  ASSERT_FALSE(opened.has_value());
  EXPECT_EQ(opened.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
  EXPECT_NE(opened.error().detail().find("expiration"), std::string::npos)
      << opened.error().message();
}

TEST(RutwPrints, ARootNamingNoRutwModalityIsRefusedBeforeAPathIsFormed) {
  // The mirror of `OptionPrints.TheDeferredRutwModalityIsRefusedByNameBefore
  // APathIsFormed`. The fixture under `rp_wide_offroot` holds the SAME lawful
  // RUTW bytes, so nothing but the ROOT distinguishes this case: a RUTW reader
  // pointed anywhere else is a configuration error, not a fallback.
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  const auto opened = qr::sources::RutwPrintReader::open(*scope, fixture_root("rp_wide_offroot"));
  ASSERT_FALSE(opened.has_value());
  EXPECT_EQ(opened.error().code(), qr::RefusalCode::CONFIG);
  EXPECT_NE(opened.error().message().find("RUTW"), std::string::npos)
      << opened.error().message();
  // And the IWM print corpus root — the one that actually exists — is refused
  // by the same wall.
  const auto iwm = qr::sources::RutwPrintReader::open(
      *scope, std::filesystem::path("/workspace/data/tokens/options_prints/IWM"));
  ASSERT_FALSE(iwm.has_value());
  EXPECT_EQ(iwm.error().code(), qr::RefusalCode::CONFIG);
  EXPECT_FALSE(qr::sources::is_rutw_corpus_root(fixture_root("rp_wide_offroot")));
  EXPECT_TRUE(qr::sources::is_rutw_corpus_root(rutw_fixture("rp_wide")));
}

TEST(RutwPrints, TheIwmPrintReaderStillRefusesRutwBytesItsOwnProfilePinWouldAdmit) {
  // THE OTHER DIRECTION, ON BYTES RATHER THAN ON A NAME. `rp_wide` is written
  // in the wide encoding, which `OptionPrintReader` admits for the IWM corpus
  // (WP9's s356/s606 finding) — so the ONLY thing that can refuse it is the
  // modality wall. If that wall were removed, these bytes would be read into an
  // IWM-labelled stream, which is exactly the failure B5 exists to prevent.
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  const auto opened = qr::sources::OptionPrintReader::open(*scope, rutw_fixture("rp_wide"));
  ASSERT_FALSE(opened.has_value());
  EXPECT_EQ(opened.error().code(), qr::RefusalCode::CONFIG);
  EXPECT_NE(opened.error().message().find("RUTW"), std::string::npos)
      << opened.error().message();

  // The bytes really are readable — by the reader that owns them.
  auto lawful = qr::sources::RutwPrintReader::open(*scope, rutw_fixture("rp_wide"));
  ASSERT_TRUE(lawful.has_value()) << lawful.error().message();
  qr::sources::RutwPrintReader reader = std::move(lawful).value();
  EXPECT_FALSE(read_all(reader).empty());
}

TEST(RutwPrints, TheRegistrySessionWallFiresBeforeAnyRutwPathExists) {
  // B5: "registry-session wall (W2.12)" — and it is the SAME wall, not a
  // second calendar. `open` takes a DayScope, which only `admit` mints, so an
  // out-of-scope ordinal cannot even produce the argument.
  const qr::Registry* const registry = qr::sources::testing::registry_or_null();
  ASSERT_NE(registry, nullptr);
  // The bounds are read from the wall's OWN constants, never transcribed: the
  // scope has been amended before (and will be again), and a test that pins a
  // literal ordinal would then be testing last month's calendar.
  for (const std::int64_t ordinal :
       {qr::kScopeFirstOrdinal - 1, qr::kScopeLastOrdinal + 1, std::int64_t{-1}}) {
    const auto refused = qr::DayScope::admit(*registry, ordinal);
    ASSERT_FALSE(refused.has_value()) << "ordinal " << ordinal << " was admitted";
    EXPECT_EQ(refused.error().code(), qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE);
  }
  const auto admitted = qr::DayScope::admit(*registry, 125);
  ASSERT_TRUE(admitted.has_value()) << admitted.error().message();
  // A registered, in-scope session the RUTW corpus does not cover is a typed
  // ABSENCE of the payload, not a silent empty read.
  const auto uncovered = qr::sources::RutwPrintReader::open(admitted.value(),
                                                            rutw_fixture("rp_absent"));
  ASSERT_FALSE(uncovered.has_value());
  EXPECT_NE(uncovered.error().code(), qr::RefusalCode::CONFIG)
      << "an absent payload must not be reported as a misconfigured root";
}

// ---------------------------------------------------------------------------
// The census — counted, never applied.
// ---------------------------------------------------------------------------

TEST(RutwPrints, BothAttachmentClocksAreCensusedAndNeitherIsEverApplied) {
  // B3 (inherited by B5): "IV/Greeks need BOTH strict-prior attachments". The
  // READER retains both clocks raw and COUNTS them; nothing here drops a row on
  // an attachment, because the eligibility owner is qr_carriers. The fixture
  // carries all three states of each clock: strictly prior, not strictly prior
  // (quote_ts EQUAL to the print instant), and absent.
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  auto opened = qr::sources::RutwPrintReader::open(*scope, rutw_fixture("rp_wide"));
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  qr::sources::RutwPrintReader reader = std::move(opened).value();
  const std::vector<qr::sources::OptionPrintRow> rows = read_all(reader);
  const qr::sources::OptionPrintCensus& census = reader.census();

  EXPECT_EQ(census.quote_attachment_prior,
            literal_int("rutw_prints/census/quote_attachment_prior"));
  EXPECT_EQ(census.quote_attachment_not_prior,
            literal_int("rutw_prints/census/quote_attachment_not_prior"));
  EXPECT_EQ(census.quote_attachment_absent,
            literal_int("rutw_prints/census/quote_attachment_absent"));
  EXPECT_EQ(census.underlying_on_day, literal_int("rutw_prints/census/underlying_on_day"));
  EXPECT_EQ(census.underlying_off_day, literal_int("rutw_prints/census/underlying_off_day"));
  EXPECT_EQ(census.underlying_absent, literal_int("rutw_prints/census/underlying_absent"));
  // The three quote states partition the admitted rows exactly, and so do the
  // three underlying states: nothing is counted twice and nothing is missed.
  EXPECT_EQ(census.quote_attachment_prior + census.quote_attachment_not_prior +
                census.quote_attachment_absent,
            census.rth_rows);
  EXPECT_EQ(census.underlying_on_day + census.underlying_off_day + census.underlying_absent,
            census.rth_rows);
  // COUNTED, NOT APPLIED: every admitted row is still delivered.
  EXPECT_EQ(static_cast<std::int64_t>(rows.size()), census.rth_rows);

  // Absence is a MASK BIT and the field holds 0 — never a sentinel instant.
  int absent_rows = 0;
  for (const qr::sources::OptionPrintRow& row : rows) {
    if (row.is_null(qr::sources::kPrintSlotQuoteTimestamp)) {
      ++absent_rows;
      EXPECT_EQ(row.quote_ts_ms_b, 0);
      EXPECT_TRUE(row.is_null(qr::sources::kPrintSlotUnderlyingTimestamp));
      EXPECT_TRUE(row.underlying_ts_text.view().empty());
    }
  }
  EXPECT_EQ(absent_rows, census.quote_attachment_absent);

  EXPECT_EQ(census.fully_populated_rows, literal_int("rutw_prints/census/fully_populated_rows"));
  EXPECT_EQ(census.greek_complete_rows, literal_int("rutw_prints/census/greek_complete_rows"));
}

TEST(RutwPrints, TheJunkCensusCountsItsFourCausesAndDropsNothing) {
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  auto opened = qr::sources::RutwPrintReader::open(*scope, rutw_fixture("rp_wide"));
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  qr::sources::RutwPrintReader reader = std::move(opened).value();
  const std::vector<qr::sources::OptionPrintRow> rows = read_all(reader);
  const qr::sources::OptionPrintCensus& census = reader.census();

  EXPECT_EQ(census.junk_price_rows, literal_int("rutw_prints/census/junk_price_rows"));
  EXPECT_EQ(census.junk_size_rows, literal_int("rutw_prints/census/junk_size_rows"));
  EXPECT_EQ(census.junk_right_rows, literal_int("rutw_prints/census/junk_right_rows"));
  EXPECT_EQ(census.junk_crossed_quote_rows,
            literal_int("rutw_prints/census/junk_crossed_quote_rows"));
  EXPECT_EQ(census.junk_rows, literal_int("rutw_prints/census/junk_rows"));
  EXPECT_LT(census.junk_rows, census.rth_rows) << "the fixture must also carry clean rows";

  // The junk rows are DELIVERED. A reader that filtered them would agree with
  // the counters and disagree with the row count.
  EXPECT_EQ(static_cast<std::int64_t>(rows.size()), census.rth_rows);
  int zero_price = 0;
  int unknown_right = 0;
  int crossed = 0;
  for (const qr::sources::OptionPrintRow& row : rows) {
    zero_price += (!row.is_null(qr::sources::kPrintSlotPrice) && row.price_u6 == 0) ? 1 : 0;
    unknown_right += row.right == qr::sources::Right::Other ? 1 : 0;
    crossed += (!row.is_null(qr::sources::kPrintSlotBid) &&
                !row.is_null(qr::sources::kPrintSlotAsk) && row.ask_u6 < row.bid_u6)
                   ? 1
                   : 0;
  }
  EXPECT_EQ(zero_price, census.junk_price_rows);
  EXPECT_EQ(unknown_right, census.junk_right_rows);
  EXPECT_EQ(crossed, census.junk_crossed_quote_rows);
  // An unknown right token stays `Other` — never folded into call or put.
  EXPECT_GT(unknown_right, 0);
}

TEST(RutwPrints, CoverageCountsDistinctContractsExpiriesAndStrikes) {
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  auto opened = qr::sources::RutwPrintReader::open(*scope, rutw_fixture("rp_wide"));
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  qr::sources::RutwPrintReader reader = std::move(opened).value();
  qr::sources::OptionPrintCoverage coverage;
  for (const qr::sources::OptionPrintRow& row : read_all(reader)) {
    coverage.observe(row);
  }
  EXPECT_EQ(coverage.contracts(), literal_int("rutw_prints/coverage/contracts"));
  EXPECT_EQ(coverage.expirations(), literal_int("rutw_prints/coverage/expirations"));
  EXPECT_EQ(coverage.strikes(), literal_int("rutw_prints/coverage/strikes"));
  // The fixture repeats one contract across two prints, so the contract count
  // is strictly below the row count: coverage counts identities, not rows.
  EXPECT_LT(coverage.contracts(), reader.rth_rows());
}

TEST(RutwPrints, TwoReadsAndAPermutedTapeSerializeToIdenticalBytes) {
  // TWO-RUN identity is the weaker half; PERMUTATION identity is the law that
  // makes it worth anything. Rows sharing a millisecond have no order — the
  // tape's order among them is an artifact of the vendor's writer — so the
  // same session written with two equal-time rows swapped must serialize to
  // exactly the same bytes.
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  const auto collect = [&scope](const char* tree) {
    std::vector<std::uint8_t> bytes;
    auto opened = qr::sources::RutwPrintReader::open(*scope, rutw_fixture(tree));
    EXPECT_TRUE(opened.has_value()) << opened.error().message();
    if (!opened.has_value()) {
      return bytes;
    }
    qr::sources::RutwPrintReader reader = std::move(opened).value();
    qr::sources::RutwPrintReader::Group group;
    while (true) {
      const auto more = reader.next_group(group);
      EXPECT_TRUE(more.has_value()) << more.error().message();
      if (!more.has_value() || !more.value()) {
        break;
      }
      qr::sources::append_i64(group.ts_ms_b, bytes);
      for (const qr::sources::OptionPrintRow& row : group.rows) {
        append_serialized(row, bytes);
      }
    }
    return bytes;
  };
  const std::vector<std::uint8_t> first = collect("rp_wide");
  const std::vector<std::uint8_t> second = collect("rp_wide");
  const std::vector<std::uint8_t> permuted = collect("rp_permuted");
  ASSERT_FALSE(first.empty());
  EXPECT_EQ(first, second);
  EXPECT_EQ(first, permuted) << "an equal-time permutation changed the emitted bytes";
}
