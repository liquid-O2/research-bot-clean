// The four readers, end to end over the generated fixture sessions.
//
// SPEC: FINAL_PLAN APPENDIX B1-B4 + design/DESIGN_SUBSTRATE APPENDIX C3.
// Every expected number here comes from tests/fixtures/source_expected_literals.tsv,
// which make_source_fixtures.py derives from the values it ENCODES — the C++
// side computes none of them a second way.
#include <gtest/gtest.h>

#include <cmath>

#include <algorithm>

#include <string>
#include <utility>
#include <vector>

#include "fixture_support.hpp"
#include "qr_registry/registry.hpp"
#include "qr_sources/option_prints.hpp"
#include "qr_sources/option_quotes.hpp"
#include "qr_sources/stock_quotes.hpp"
#include "qr_sources/stock_trades.hpp"

namespace {

using qr::sources::testing::fixture_root;
using qr::sources::testing::literal_int;
using qr::sources::testing::literal_text;
using qr::sources::testing::scope_125;

// --- B1 stock quotes --------------------------------------------------------

TEST(StockQuotes, TheFixtureSessionMatchesEveryDerivedLiteral) {
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  auto opened = qr::sources::StockQuoteReader::open(*scope, fixture_root("sq_cent"),
                                                    scope->profile());
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  qr::sources::StockQuoteReader reader = std::move(opened).value();

  std::vector<qr::sources::StockQuoteReader::Group> seen;
  std::vector<std::vector<qr::sources::StockQuoteRow>> rows;
  qr::sources::StockQuoteReader::Group group;
  while (true) {
    const auto more = reader.next_group(group);
    ASSERT_TRUE(more.has_value()) << more.error().message();
    if (!more.value()) {
      break;
    }
    seen.push_back(group);
    rows.emplace_back(group.rows.begin(), group.rows.end());
  }

  EXPECT_EQ(reader.rth_rows(), literal_int("stock_quotes/*/rth_rows"));
  EXPECT_EQ(reader.group_count(), literal_int("stock_quotes/*/group_count"));
  EXPECT_EQ(reader.sentinel_rows(), literal_int("stock_quotes/*/sentinel_rows"));
  ASSERT_EQ(static_cast<std::int64_t>(seen.size()), literal_int("stock_quotes/*/group_count"));
  for (std::size_t index = 0; index < seen.size(); ++index) {
    const std::string key = "stock_quotes/group" + std::to_string(index) + "/";
    EXPECT_EQ(seen[index].ts_ms_b, literal_int(key + "ts_ms_b")) << "group " << index;
    EXPECT_EQ(static_cast<std::int64_t>(rows[index].size()), literal_int(key + "rows"))
        << "group " << index;
  }

  // Row values: u6 prices and share sizes, matched by their fixture row index.
  // Fixture rows 2..12 are the admitted ones; group 0 holds rows 2 and 3.
  const qr::sources::StockQuoteRow& first = rows[0][0];
  EXPECT_EQ(first.bid_u6, literal_int("stock_quotes/row2/bid_u6"));
  EXPECT_EQ(first.ask_u6, literal_int("stock_quotes/row2/ask_u6"));
  EXPECT_EQ(first.bid_shares, literal_int("stock_quotes/row2/bid_shares"));
  EXPECT_EQ(first.ask_shares, literal_int("stock_quotes/row2/ask_shares"));
  EXPECT_EQ(first.bid_condition, 0);
  EXPECT_FALSE(first.is_null(qr::sources::kQuoteSlotBidExchange));
  // The midpoint is computed from both sides; the vendor `mid` column is walled.
  EXPECT_EQ(first.mid_u6(), (first.bid_u6 + first.ask_u6) / 2);

  // Fixture row 11 carries a NULL bid_exchange: a null FIELD, not a broken row.
  bool saw_null_exchange = false;
  for (const auto& group_rows : rows) {
    for (const qr::sources::StockQuoteRow& row : group_rows) {
      if (row.is_null(qr::sources::kQuoteSlotBidExchange)) {
        saw_null_exchange = true;
        EXPECT_EQ(row.bid_exchange, 0) << "a null field carries 0, never a sentinel";
        EXPECT_NE(row.ask_exchange, 0);
      }
    }
  }
  EXPECT_TRUE(saw_null_exchange) << "the null-exchange fixture row was not delivered";
  EXPECT_EQ(literal_int("stock_quotes/row11/bid_exchange_null"), 1);
}

TEST(StockQuotes, RowGroupsOutsideTheWindowArePrunedAndNeverDecoded) {
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  auto opened = qr::sources::StockQuoteReader::open(*scope, fixture_root("sq_cent"),
                                                    scope->profile());
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  qr::sources::StockQuoteReader reader = std::move(opened).value();
  EXPECT_EQ(static_cast<std::int64_t>(reader.source().row_groups_total()),
            literal_int("stock_quotes/*/row_groups_total"));
  EXPECT_EQ(static_cast<std::int64_t>(reader.source().row_groups_kept()),
            literal_int("stock_quotes/*/row_groups_kept"));

  qr::sources::StockQuoteReader::Group group;
  while (true) {
    const auto more = reader.next_group(group);
    ASSERT_TRUE(more.has_value()) << more.error().message();
    if (!more.value()) {
      break;
    }
  }
  // 16 rows in the two kept row groups x 9 projected columns. The four rows of
  // the pruned group were never touched.
  EXPECT_EQ(reader.decoded_values(), 16 * 9);
}

TEST(StockQuotes, TheRegistryRowDecidesTheProfileAndACallerCannotOverrideIt) {
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  ASSERT_EQ(scope->profile(), qr::SourceProfile::CentInt32) << "session 125 is a cent session";

  // Asking for the other profile is refused BEFORE the file is even consulted:
  // the registry row is the authority, and the caller is not.
  const auto overridden = qr::sources::StockQuoteReader::open(
      *scope, fixture_root("sq_cent"), qr::SourceProfile::DollarFloat64);
  ASSERT_FALSE(overridden.has_value());
  EXPECT_EQ(overridden.error().code(), qr::RefusalCode::CONFIG);
  EXPECT_NE(overridden.error().detail().find("cent_int32"), std::string::npos)
      << overridden.error().message();
}

TEST(StockQuotes, AFileDisagreeingWithItsRegistryProfileIsRefusedNotAdapted) {
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  // Same session, same registry row (cent_int32), dollar prices on disk.
  const auto opened = qr::sources::StockQuoteReader::open(
      *scope, fixture_root("sq_dollar_prices"), scope->profile());
  ASSERT_FALSE(opened.has_value());
  EXPECT_EQ(opened.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
  EXPECT_NE(opened.error().detail().find("DOLLAR_F64"), std::string::npos)
      << opened.error().message();
  // And the whole dollar-profile payload is refused too.
  const auto whole = qr::sources::StockQuoteReader::open(*scope, fixture_root("sq_dollar"),
                                                         scope->profile());
  ASSERT_FALSE(whole.has_value());
  EXPECT_EQ(whole.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
}

TEST(StockQuotes, TheDollarProfileSessionNormalizesToTheSameU6AndShareValues) {
  // THE OTHER HALF OF THE DUAL PROFILE LAW, end to end. Session 187
  // (2022-09-30) is inside the 125..749 scope and its OWN registry row declares
  // `dollar_float64` — which is the only lawful way to read a dollar session,
  // since the profile is not chronological. The fixture carries the same prices
  // and sizes as the cent session in the other encoding, so every normalized
  // value must come out identical.
  const qr::Registry* const registry = qr::sources::testing::registry_or_null();
  ASSERT_NE(registry, nullptr);
  const auto scope = qr::DayScope::admit_day(*registry, literal_text("stock_quotes_dollar/*/day"));
  ASSERT_TRUE(scope.has_value()) << scope.error().message();
  ASSERT_EQ(scope.value().profile(), qr::SourceProfile::DollarFloat64);

  auto opened = qr::sources::StockQuoteReader::open(
      scope.value(), fixture_root("sq_dollar_session187"), scope.value().profile());
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  qr::sources::StockQuoteReader reader = std::move(opened).value();
  EXPECT_EQ(reader.profile(), qr::SourceProfile::DollarFloat64);

  std::vector<std::vector<qr::sources::StockQuoteRow>> rows;
  std::vector<std::int64_t> stamps;
  qr::sources::StockQuoteReader::Group group;
  while (true) {
    const auto more = reader.next_group(group);
    ASSERT_TRUE(more.has_value()) << more.error().message();
    if (!more.value()) {
      break;
    }
    stamps.push_back(group.ts_ms_b);
    rows.emplace_back(group.rows.begin(), group.rows.end());
  }

  // Identical counts and identical NORMALIZED values, on the other encoding.
  EXPECT_EQ(reader.rth_rows(), literal_int("stock_quotes/*/rth_rows"));
  EXPECT_EQ(reader.group_count(), literal_int("stock_quotes/*/group_count"));
  EXPECT_EQ(reader.sentinel_rows(), literal_int("stock_quotes/*/sentinel_rows"));
  ASSERT_FALSE(rows.empty());
  const qr::sources::StockQuoteRow& first = rows[0][0];
  EXPECT_EQ(first.bid_u6, literal_int("stock_quotes/row2/bid_u6"));
  EXPECT_EQ(first.ask_u6, literal_int("stock_quotes/row2/ask_u6"));
  EXPECT_EQ(first.bid_shares, literal_int("stock_quotes/row2/bid_shares"));
  EXPECT_EQ(first.ask_shares, literal_int("stock_quotes/row2/ask_shares"));
  // Only the CLOCK differs: this session's own frame-B open, from its own row.
  const std::int64_t open_ms = literal_int("stock_quotes_dollar/*/open_ms_b");
  ASSERT_EQ(static_cast<std::int64_t>(stamps.size()),
            literal_int("stock_quotes/*/group_count"));
  for (std::size_t index = 0; index < stamps.size(); ++index) {
    const std::string key = "stock_quotes/group" + std::to_string(index) + "/";
    const std::int64_t cent_offset =
        literal_int(key + "ts_ms_b") - literal_int("stock_quotes/group0/ts_ms_b");
    EXPECT_EQ(stamps[index] - open_ms, cent_offset) << "group " << index;
  }

  // And the cent encoding of the SAME session's registry row is refused.
  const auto as_cent = qr::sources::StockQuoteReader::open(
      scope.value(), fixture_root("sq_dollar_session187"), qr::SourceProfile::CentInt32);
  ASSERT_FALSE(as_cent.has_value());
  EXPECT_EQ(as_cent.error().code(), qr::RefusalCode::CONFIG);
}

TEST(StockQuotes, ARowMixingNullAndNonNullNbboFieldsRefusesAndTheSentinelIsCounted) {
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  auto opened = qr::sources::StockQuoteReader::open(*scope, fixture_root("sq_partial_null"),
                                                    scope->profile());
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  qr::sources::StockQuoteReader reader = std::move(opened).value();
  qr::sources::StockQuoteReader::Group group;
  bool refused = false;
  for (int guard = 0; guard < 100; ++guard) {
    const auto more = reader.next_group(group);
    if (!more.has_value()) {
      refused = true;
      EXPECT_EQ(more.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
      EXPECT_NE(more.error().refusal().detail(), nullptr);
      break;
    }
    if (!more.value()) {
      break;
    }
  }
  EXPECT_TRUE(refused) << "a half-null NBBO row must refuse, never be half-trusted";
  // The all-null sentinel row is a different thing entirely: skipped, counted.
  EXPECT_EQ(reader.sentinel_rows(), 1);
}

TEST(StockQuotes, ADescendingTapeRefusesInsteadOfBeingSortedIntoSilence) {
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  auto opened = qr::sources::StockQuoteReader::open(*scope, fixture_root("sq_descending"),
                                                    scope->profile());
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  qr::sources::StockQuoteReader reader = std::move(opened).value();
  qr::sources::StockQuoteReader::Group group;
  bool refused = false;
  for (int guard = 0; guard < 100; ++guard) {
    const auto more = reader.next_group(group);
    if (!more.has_value()) {
      refused = true;
      EXPECT_EQ(more.error().code(), qr::RefusalCode::OUT_OF_ORDER);
      break;
    }
    if (!more.value()) {
      break;
    }
  }
  EXPECT_TRUE(refused) << "the equal-time group machine requires a non-decreasing tape";
}

TEST(StockQuotes, PageVersionTwoDecodesToTheSameSession) {
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  std::vector<std::int64_t> counts;
  for (const char* tree : {"sq_cent", "sq_cent_v2"}) {
    auto opened =
        qr::sources::StockQuoteReader::open(*scope, fixture_root(tree), scope->profile());
    ASSERT_TRUE(opened.has_value()) << tree << ": " << opened.error().message();
    qr::sources::StockQuoteReader reader = std::move(opened).value();
    qr::sources::StockQuoteReader::Group group;
    while (true) {
      const auto more = reader.next_group(group);
      ASSERT_TRUE(more.has_value()) << more.error().message();
      if (!more.value()) {
        break;
      }
    }
    counts.push_back(reader.rth_rows());
    counts.push_back(reader.group_count());
  }
  ASSERT_EQ(counts.size(), 4U);
  EXPECT_EQ(counts[0], counts[2]);
  EXPECT_EQ(counts[1], counts[3]);
}

// --- B2 stock trades --------------------------------------------------------

TEST(StockTrades, TheFixtureSessionMatchesEveryDerivedLiteral) {
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  auto opened = qr::sources::StockTradeReader::open(*scope, fixture_root("st_good"));
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  qr::sources::StockTradeReader reader = std::move(opened).value();

  std::vector<std::vector<qr::sources::StockTradeRow>> rows;
  std::vector<std::int64_t> stamps;
  qr::sources::StockTradeReader::Group group;
  while (true) {
    const auto more = reader.next_group(group);
    ASSERT_TRUE(more.has_value()) << more.error().message();
    if (!more.value()) {
      break;
    }
    stamps.push_back(group.ts_ms_b);
    rows.emplace_back(group.rows.begin(), group.rows.end());
  }

  EXPECT_EQ(reader.rth_rows(), literal_int("stock_trades/*/rth_rows"));
  EXPECT_EQ(reader.group_count(), literal_int("stock_trades/*/group_count"));
  ASSERT_EQ(static_cast<std::int64_t>(stamps.size()), literal_int("stock_trades/*/group_count"));
  for (std::size_t index = 0; index < stamps.size(); ++index) {
    const std::string key = "stock_trades/group" + std::to_string(index) + "/";
    EXPECT_EQ(stamps[index], literal_int(key + "ts_ms_b"));
    EXPECT_EQ(static_cast<std::int64_t>(rows[index].size()), literal_int(key + "rows"));
  }

  // Fixture row 1 is the first admitted print.
  const qr::sources::StockTradeRow& first = rows[0][0];
  EXPECT_EQ(first.price_u6, literal_int("stock_trades/row1/price_u6"));
  EXPECT_TRUE(first.quote_present());
  EXPECT_EQ(first.bid_shares, literal_int("stock_trades/row1/bid_shares"));
  EXPECT_EQ(first.bid_u6, literal_int("stock_trades/row1/bid_u6"));
  EXPECT_EQ(first.ext_condition[0], 255);
  EXPECT_EQ(first.quote_ts_ms_b, first.ts_ms_b - 3);

  // Fixture row 3 carries NO attached quote at all: absence is not zero.
  bool saw_absent_quote = false;
  bool saw_cancel_condition = false;
  for (const auto& group_rows : rows) {
    for (const qr::sources::StockTradeRow& row : group_rows) {
      if (!row.quote_present()) {
        saw_absent_quote = true;
        EXPECT_EQ(row.bid_u6, 0);
        EXPECT_EQ(row.ask_shares, 0);
        EXPECT_TRUE(row.is_null(qr::sources::kTradeSlotBid));
        EXPECT_TRUE(row.is_null(qr::sources::kTradeSlotBidCondition));
      }
      if (row.condition == 40) {
        // B2's CANCEL code is RETAINED here; applying it is downstream work.
        saw_cancel_condition = true;
      }
    }
  }
  EXPECT_TRUE(saw_absent_quote);
  EXPECT_TRUE(saw_cancel_condition);
}

TEST(StockTrades, APriceColumnOutsideTheMeasuredProfileRefuses) {
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  const auto opened = qr::sources::StockTradeReader::open(*scope, fixture_root("st_wrongtype"));
  ASSERT_FALSE(opened.has_value());
  EXPECT_EQ(opened.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
  EXPECT_NE(opened.error().detail().find("price"), std::string::npos)
      << opened.error().message();
}

// --- B3 option prints -------------------------------------------------------

TEST(OptionPrints, TheFixtureSessionMatchesEveryDerivedLiteral) {
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  auto opened = qr::sources::OptionPrintReader::open(*scope, fixture_root("op_compact"));
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  qr::sources::OptionPrintReader reader = std::move(opened).value();

  std::vector<std::vector<qr::sources::OptionPrintRow>> rows;
  std::vector<std::int64_t> stamps;
  qr::sources::OptionPrintReader::Group group;
  while (true) {
    const auto more = reader.next_group(group);
    ASSERT_TRUE(more.has_value()) << more.error().message();
    if (!more.value()) {
      break;
    }
    stamps.push_back(group.ts_ms_b);
    rows.emplace_back(group.rows.begin(), group.rows.end());
  }

  EXPECT_EQ(reader.rth_rows(), literal_int("options_prints/*/rth_rows"));
  EXPECT_EQ(reader.group_count(), literal_int("options_prints/*/group_count"));
  EXPECT_EQ(reader.skipped_null_rows(),
            literal_int("options_prints/*/skipped_null_rows"));
  for (std::size_t index = 0; index < stamps.size(); ++index) {
    const std::string key = "options_prints/group" + std::to_string(index) + "/";
    EXPECT_EQ(stamps[index], literal_int(key + "ts_ms_b"));
    EXPECT_EQ(static_cast<std::int64_t>(rows[index].size()), literal_int(key + "rows"));
  }

  // Fixture rows 2 and 3 form the first admitted group; both are asserted
  // field by field against the derived literals.
  ASSERT_GE(rows.size(), 1U);
  ASSERT_EQ(rows[0].size(), 2U);
  std::vector<std::int64_t> strikes;
  for (const qr::sources::OptionPrintRow& row : rows[0]) {
    strikes.push_back(row.strike_u6);
  }
  EXPECT_NE(std::find(strikes.begin(), strikes.end(),
                      literal_int("options_prints/row2/strike_u6")),
            strikes.end());
  EXPECT_NE(std::find(strikes.begin(), strikes.end(),
                      literal_int("options_prints/row3/strike_u6")),
            strikes.end());

  // The two attachment clocks and the retained text.
  int single_leg = 0;
  bool saw_call = false;
  bool saw_put = false;
  for (const auto& group_rows : rows) {
    for (const qr::sources::OptionPrintRow& row : group_rows) {
      EXPECT_GT(row.quote_ts_ms_b, 0);
      EXPECT_EQ(row.underlying_ts_text.view().substr(0, 10), "2022-07-05");
      EXPECT_GT(row.implied_vol, 0.0);
      saw_call |= row.right == qr::sources::Right::Call;
      saw_put |= row.right == qr::sources::Right::Put;
      single_leg += row.is_single_leg() ? 1 : 0;
    }
  }
  EXPECT_TRUE(saw_call);
  EXPECT_TRUE(saw_put);
  // All five admitted prints carry a single-leg condition (18 twice, then 95,
  // 125 and 126): the field is EXPOSED and nothing was filtered on it.
  EXPECT_EQ(single_leg, 5);
  std::vector<std::int64_t> conditions;
  for (const auto& group_rows : rows) {
    for (const qr::sources::OptionPrintRow& row : group_rows) {
      conditions.push_back(row.condition);
    }
  }
  for (const std::int64_t code : qr::sources::kSingleLegPrintConditions) {
    EXPECT_NE(std::find(conditions.begin(), conditions.end(), code), conditions.end())
        << "single-leg condition " << code << " is not exercised by the fixture";
  }
  EXPECT_EQ(literal_text("options_prints/row2/right"), "CALL");
}

// ---------------------------------------------------------------------------
// CC-013 (2026-08-12, change control): the eleven newly projected columns.
// ---------------------------------------------------------------------------
//
// These are the amendment's own fixtures. The census that authorized CC-013
// (artifacts/cache/ivx/cc013_column_census.tsv) could only read the parquet
// FOOTER, so it proved the columns are populated and could not prove the
// reader decodes them correctly. That is what the three cases below are for:
// the VALUE, the ABSENCE and the NON-FINITE, each asserted against a literal
// this suite does not compute.

namespace {

/// Reads the whole compact print fixture into one flat vector of rows, in tape
/// order, so a case can index the fixture's own row numbering.
std::vector<qr::sources::OptionPrintRow> read_compact_prints() {
  std::vector<qr::sources::OptionPrintRow> flat;
  const auto scope = qr::sources::testing::scope_125();
  EXPECT_TRUE(scope.has_value());
  if (!scope.has_value()) {
    return flat;
  }
  auto opened = qr::sources::OptionPrintReader::open(*scope, fixture_root("op_compact"));
  EXPECT_TRUE(opened.has_value()) << opened.error().message();
  if (!opened.has_value()) {
    return flat;
  }
  qr::sources::OptionPrintReader reader = std::move(opened).value();
  qr::sources::OptionPrintReader::Group group;
  while (true) {
    const auto more = reader.next_group(group);
    EXPECT_TRUE(more.has_value()) << more.error().message();
    if (!more.has_value() || !more.value()) {
      break;
    }
    flat.insert(flat.end(), group.rows.begin(), group.rows.end());
  }
  return flat;
}

/// The fixture's admitted rows are file rows 2..6, so admitted index i is file
/// row i + 2 — the numbering the derived literals use.
constexpr std::size_t kFirstAdmittedFixtureRow = 2;

double cc013_value(const qr::sources::OptionPrintRow& row, std::string_view name) {
  if (name == "vega") return row.vega;
  if (name == "vomma") return row.vomma;
  if (name == "veta") return row.veta;
  if (name == "vera") return row.vera;
  if (name == "speed") return row.speed;
  if (name == "zomma") return row.zomma;
  if (name == "color") return row.color;
  if (name == "ultima") return row.ultima;
  if (name == "dual_delta") return row.dual_delta;
  if (name == "dual_gamma") return row.dual_gamma;
  if (name == "iv_error") return row.iv_error;
  ADD_FAILURE() << "unknown CC-013 column " << name;
  return 0.0;
}

std::size_t cc013_slot(std::string_view name) {
  if (name == "vega") return qr::sources::kPrintSlotVega;
  if (name == "vomma") return qr::sources::kPrintSlotVomma;
  if (name == "veta") return qr::sources::kPrintSlotVeta;
  if (name == "vera") return qr::sources::kPrintSlotVera;
  if (name == "speed") return qr::sources::kPrintSlotSpeed;
  if (name == "zomma") return qr::sources::kPrintSlotZomma;
  if (name == "color") return qr::sources::kPrintSlotColor;
  if (name == "ultima") return qr::sources::kPrintSlotUltima;
  if (name == "dual_delta") return qr::sources::kPrintSlotDualDelta;
  if (name == "dual_gamma") return qr::sources::kPrintSlotDualGamma;
  if (name == "iv_error") return qr::sources::kPrintSlotIvError;
  ADD_FAILURE() << "unknown CC-013 column " << name;
  return 0;
}

constexpr std::array<std::string_view, 11> kCc013Columns{
    "vega",  "vomma",      "veta",       "vera",     "speed", "zomma",
    "color", "ultima",     "dual_delta", "dual_gamma", "iv_error"};

}  // namespace

TEST(OptionPrints, EveryCc013ColumnDecodesToItsOwnDerivedLiteral) {
  const std::vector<qr::sources::OptionPrintRow> rows = read_compact_prints();
  ASSERT_FALSE(rows.empty());
  int compared = 0;
  for (std::size_t index = 0; index < rows.size(); ++index) {
    const std::string key =
        "options_prints/row" + std::to_string(index + kFirstAdmittedFixtureRow) + "/";
    for (const std::string_view name : kCc013Columns) {
      const std::string expected = literal_text(key + std::string(name));
      ASSERT_FALSE(expected.empty()) << key << name;
      const std::size_t slot = cc013_slot(name);
      const double value = cc013_value(rows[index], name);
      if (expected == "NULL") {
        EXPECT_TRUE(rows[index].is_null(slot)) << key << name;
        continue;
      }
      EXPECT_FALSE(rows[index].is_null(slot)) << key << name;
      if (expected == "NAN") {
        EXPECT_TRUE(std::isnan(value)) << key << name;
      } else if (expected == "INF") {
        EXPECT_TRUE(std::isinf(value) && value > 0.0) << key << name;
      } else {
        EXPECT_DOUBLE_EQ(value, std::strtod(expected.c_str(), nullptr)) << key << name;
      }
      ++compared;
    }
  }
  // The case is only evidence if it actually compared the whole block on every
  // admitted row: 5 rows x 11 columns, minus the one deliberate NULL.
  EXPECT_EQ(compared, 54);
}

TEST(OptionPrints, ACc013ColumnsAbsenceSetsExactlyItsOwnMaskBit) {
  const std::vector<qr::sources::OptionPrintRow> rows = read_compact_prints();
  ASSERT_GE(rows.size(), 2U);
  // Fixture row 3 (admitted index 1) carries a NULL `vomma` and nothing else
  // null. The mask is per SLOT precisely so one absent greek cannot mute its
  // neighbours, and CC-013 renumbered every slot after delta — an off-by-one in
  // that renumbering would show up here and nowhere else.
  const qr::sources::OptionPrintRow& row = rows[1];
  ASSERT_TRUE(row.is_null(qr::sources::kPrintSlotVomma));
  for (std::size_t slot = 0; slot < qr::sources::kOptionPrintSpec.projection.size(); ++slot) {
    if (slot == qr::sources::kPrintSlotVomma) {
      continue;
    }
    EXPECT_FALSE(row.is_null(slot))
        << "slot " << slot << " (" << qr::sources::OptionPrintDigests::field_name(slot)
        << ") was muted by another column's absence";
  }
}

TEST(OptionPrints, ANonFiniteCc013ValueIsRetainedRawAndIsNotAnAbsence) {
  const std::vector<qr::sources::OptionPrintRow> rows = read_compact_prints();
  ASSERT_GE(rows.size(), 3U);
  // ABSENT and NON-FINITE are different states and the reader keeps them
  // different: it retains the raw bits and sets NO mask bit. Judging a value
  // is a downstream job (the typed lattice), never the reader's.
  const qr::sources::OptionPrintRow& infinite = rows[1];   // fixture row 3: color = +Inf
  EXPECT_FALSE(infinite.is_null(qr::sources::kPrintSlotColor));
  EXPECT_TRUE(std::isinf(infinite.color));
  EXPECT_GT(infinite.color, 0.0);

  const qr::sources::OptionPrintRow& not_a_number = rows[2];  // fixture row 4: ultima = NaN
  EXPECT_FALSE(not_a_number.is_null(qr::sources::kPrintSlotUltima));
  EXPECT_TRUE(std::isnan(not_a_number.ultima));
}

TEST(OptionPrints, TheThirdOrderCompletenessCounterCountsTheCc013BlockAlone) {
  const auto scope = qr::sources::testing::scope_125();
  ASSERT_TRUE(scope.has_value());
  auto opened = qr::sources::OptionPrintReader::open(*scope, fixture_root("op_compact"));
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  qr::sources::OptionPrintReader reader = std::move(opened).value();
  qr::sources::OptionPrintReader::Group group;
  while (true) {
    const auto more = reader.next_group(group);
    ASSERT_TRUE(more.has_value()) << more.error().message();
    if (!more.value()) {
      break;
    }
  }
  // The pre-CC-013 counter must be UNCHANGED by the amendment — that is what
  // makes every census taken before it still comparable — while the new one
  // sees the single absent `vomma`.
  EXPECT_EQ(reader.census().greek_complete_rows, reader.rth_rows());
  EXPECT_EQ(reader.census().third_order_complete_rows, reader.rth_rows() - 1);
}

// THE SECOND ADMITTED PRINT ENCODING (WP9 full-scope finding). Two of the 625
// scoped IWM print sessions — s356 2023-06-05 and s606 2024-06-03 — are written
// in the WIDE encoding of the same 62 names. The reader admits exactly two
// vectors, chosen from the file's own schema, and both must normalize to the
// SAME u6 prices, u6 strikes, day ordinals and share sizes: that is what "u6
// prices / share sizes" at this boundary means.
TEST(OptionPrints, TheWideEncodingOfTheSameCorpusNormalisesToTheCompactValues) {
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());

  const auto collect = [&scope](const char* fixture) {
    std::vector<std::uint8_t> bytes;
    auto opened = qr::sources::OptionPrintReader::open(*scope, fixture_root(fixture));
    EXPECT_TRUE(opened.has_value()) << opened.error().message();
    if (!opened.has_value()) {
      return bytes;
    }
    qr::sources::OptionPrintReader reader = std::move(opened).value();
    qr::sources::OptionPrintReader::Group group;
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

  const std::vector<std::uint8_t> compact = collect("op_compact");
  const std::vector<std::uint8_t> wide = collect("op_wide");
  ASSERT_FALSE(compact.empty());
  EXPECT_EQ(wide, compact) << "the two admitted encodings do not normalize to the same rows";
}

// B5 IS STILL DEFERRED, AND THE DEFERRAL IS STILL A WALL — now on the modality
// instead of on the encoding, so it holds whatever encoding RUTW is written in.
TEST(OptionPrints, TheDeferredRutwModalityIsRefusedByNameBeforeAPathIsFormed) {
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  const std::filesystem::path rutw_root =
      std::filesystem::path("/workspace/data/tokens") / "RUTW" / "options_prints";
  const auto opened = qr::sources::OptionPrintReader::open(*scope, rutw_root);
  ASSERT_FALSE(opened.has_value());
  EXPECT_EQ(opened.error().code(), qr::RefusalCode::CONFIG);
  EXPECT_NE(opened.error().message().find("RUTW"), std::string::npos)
      << opened.error().message();
}

// --- B4 option quotes -------------------------------------------------------

TEST(OptionQuotes, TheFlatLayoutIsOneShardAndTheShardedLayoutIsChainedInSortedOrder) {
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());

  auto flat_opened = qr::sources::OptionQuoteReader::open(*scope, fixture_root("oq_flat"));
  ASSERT_TRUE(flat_opened.has_value()) << flat_opened.error().message();
  qr::sources::OptionQuoteReader flat = std::move(flat_opened).value();
  EXPECT_EQ(flat.shards().size(), 1U);
  qr::sources::OptionQuoteReader::Group group;
  std::vector<qr::sources::OptionQuoteRow> flat_rows;
  while (true) {
    const auto more = flat.next_group(group);
    ASSERT_TRUE(more.has_value()) << more.error().message();
    if (!more.value()) {
      break;
    }
    flat_rows.insert(flat_rows.end(), group.rows.begin(), group.rows.end());
  }
  EXPECT_EQ(flat.rth_rows(), literal_int("option_quotes/*/rth_rows"));
  ASSERT_FALSE(flat_rows.empty());
  EXPECT_EQ(flat_rows[0].bid_u6, literal_int("option_quotes/row1/bid_u6"));
  EXPECT_EQ(flat_rows[0].strike_u6, literal_int("option_quotes/row1/strike_u6"));
  EXPECT_EQ(flat_rows[0].expiration_day, literal_int("option_quotes/row1/expiration_day"));
  // The midpoint is COMPUTED. The fixture writes the vendor `mid` column as
  // `bid + ask` (the compact vendor's meaning), so a reader that had touched
  // that walled column would land on a visibly different number.
  EXPECT_EQ(flat_rows[0].mid_u6(), (flat_rows[0].bid_u6 + flat_rows[0].ask_u6) / 2);
  EXPECT_NE(flat_rows[0].mid_u6(), flat_rows[0].bid_u6 + flat_rows[0].ask_u6);

  auto sharded_opened = qr::sources::OptionQuoteReader::open(*scope, fixture_root("oq_sharded"));
  ASSERT_TRUE(sharded_opened.has_value()) << sharded_opened.error().message();
  qr::sources::OptionQuoteReader sharded = std::move(sharded_opened).value();
  ASSERT_EQ(sharded.shards().size(), 2U);
  EXPECT_LT(sharded.shards()[0].filename().string(),
            sharded.shards()[1].filename().string())
      << "shards must be chained in sorted order";
  // The wide profile decodes to the SAME normalized values as the compact one.
  std::vector<qr::sources::OptionQuoteRow> wide_rows;
  std::vector<std::int64_t> group_stamps;
  while (true) {
    const auto more = sharded.next_group(group);
    ASSERT_TRUE(more.has_value()) << more.error().message();
    if (!more.value()) {
      break;
    }
    group_stamps.push_back(group.ts_ms_b);
    wide_rows.insert(wide_rows.end(), group.rows.begin(), group.rows.end());
  }
  EXPECT_EQ(sharded.rth_rows(), 2 * literal_int("option_quotes/*/rth_rows"));
  ASSERT_FALSE(wide_rows.empty());
  EXPECT_EQ(wide_rows[0].bid_u6, literal_int("option_quotes/row1/bid_u6"));
  EXPECT_EQ(wide_rows[0].strike_u6, literal_int("option_quotes/row1/strike_u6"));
  EXPECT_EQ(wide_rows[0].expiration_day, literal_int("option_quotes/row1/expiration_day"));

  // A SHARD BOUNDARY CLOSES THE GROUP: the same millisecond appearing in two
  // shards is two groups, never one merged cross-contract group.
  std::vector<std::int64_t> repeated;
  for (std::size_t index = 1; index < group_stamps.size(); ++index) {
    if (group_stamps[index] <= group_stamps[index - 1]) {
      repeated.push_back(group_stamps[index]);
    }
  }
  EXPECT_FALSE(repeated.empty()) << "the second shard must restart the clock, not extend a group";
}

TEST(OptionQuotes, ASessionTheCorpusDoesNotCoverIsModalityAbsent) {
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  const auto opened = qr::sources::OptionQuoteReader::open(*scope, fixture_root("oq_absent"));
  ASSERT_FALSE(opened.has_value());
  // Distinct from being outside the calendar, which is the scope wall's answer.
  EXPECT_EQ(opened.error().code(), qr::RefusalCode::MODALITY_ABSENT);
}

}  // namespace
