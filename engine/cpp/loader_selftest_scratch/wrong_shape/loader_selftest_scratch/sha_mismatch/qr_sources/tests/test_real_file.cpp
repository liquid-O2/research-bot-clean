// The authorized real-file checks.
//
// WP4 brief, REAL-FILE CHECK (payload authorized for this work package on
// EXACTLY these files): session 125 day files for stock_quotes / stock_trades /
// options_prints, and the SAME option_quotes shard WP3 opened, at the schema
// level only.
//
// The committed numbers live in engine/cpp/tests/fixtures/real_file_digests.tsv
// (written by qr_sources_probe, appended to the file WP3 started). This suite
// re-derives the two SMALL streams on every run; the 15.4M-row stock-quote
// session — the one that reproduces the registry's raw_rth_row_count and
// complete_group_count — is the artifact run in ci/wp4_sources_realfile_gate.sh,
// exactly as WP3 keeps its 704MB shard out of ctest.
#include <gtest/gtest.h>

#include <cstdlib>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#include "fixture_support.hpp"
#include "qr_sources/option_prints.hpp"
#include "qr_sources/option_quotes.hpp"
#include "qr_sources/stock_quotes.hpp"
#include "qr_sources/stock_trades.hpp"

namespace {

using qr::sources::testing::scope_125;

constexpr const char* kTradesLabel = "IWM_sources_stock_trades_2022-07-05";
constexpr const char* kPrintsLabel = "IWM_sources_options_prints_2022-07-05";
constexpr const char* kQuotesLabel = "IWM_sources_stock_quotes_2022-07-05";
constexpr const char* kOptionQuotesLabel = "IWM_sources_option_quotes_2025-01-02_exp2025-01-02";
/// WP3's own row for the same shard, cross-checked here so the two work
/// packages cannot drift apart about what that file contains.
constexpr const char* kWp3OptionQuotesLabel = "IWM_option_quotes_2025-01-02_exp2025-01-02";

using DigestRows = std::map<std::string, std::string>;

DigestRows load_committed(const std::string& label) {
  DigestRows rows;
  std::ifstream input(QR_SOURCES_REAL_DIGESTS);
  EXPECT_TRUE(input.good()) << "cannot read " << QR_SOURCES_REAL_DIGESTS;
  std::string line;
  while (std::getline(input, line)) {
    if (line.empty()) {
      continue;
    }
    std::vector<std::string> fields;
    std::string field;
    std::istringstream stream(line);
    while (std::getline(stream, field, '\t')) {
      fields.push_back(field);
    }
    if (fields.size() != 5 || fields[0] != label) {
      continue;
    }
    rows[fields[1] + "/" + fields[2] + "/" + fields[3]] = fields[4];
  }
  return rows;
}

std::string committed_text(const DigestRows& rows, const std::string& key) {
  const auto found = rows.find(key);
  EXPECT_NE(found, rows.end()) << "committed row missing: " << key;
  return found == rows.end() ? std::string() : found->second;
}

std::int64_t committed_int(const DigestRows& rows, const std::string& key) {
  const std::string text = committed_text(rows, key);
  return text.empty() ? -1 : std::strtoll(text.c_str(), nullptr, 10);
}

/// Reads a whole stream and compares every committed row for its label.
template <class Reader, class Digests, class Open>
void check_stream(const char* label, const Open& open_reader) {
  const DigestRows committed = load_committed(label);
  ASSERT_FALSE(committed.empty()) << "no committed rows for " << label;
  auto opened = open_reader(committed_text(committed, "file/-/corpus_root"));
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  Reader reader = std::move(opened).value();
  EXPECT_EQ(reader.path().string(), committed_text(committed, "file/-/path"));
  EXPECT_EQ(reader.source().file_rows(), committed_int(committed, "file/-/file_rows"));
  EXPECT_EQ(static_cast<std::int64_t>(reader.source().row_groups_total()),
            committed_int(committed, "file/-/num_row_groups"));
  EXPECT_EQ(static_cast<std::int64_t>(reader.source().row_groups_kept()),
            committed_int(committed, "file/-/row_groups_kept"));
  EXPECT_EQ(static_cast<std::int64_t>(reader.source().file().leaves().size()),
            committed_int(committed, "file/-/num_leaves"));

  Digests digests;
  typename Reader::Group group;
  std::int64_t rows_seen = 0;
  while (true) {
    const auto more = reader.next_group(group);
    ASSERT_TRUE(more.has_value()) << more.error().message();
    if (!more.value()) {
      break;
    }
    for (const auto& row : group.rows) {
      digests.fold(row);
      ++rows_seen;
      EXPECT_EQ(row.group_ts_ms(), group.ts_ms_b);
    }
  }
  EXPECT_EQ(reader.rth_rows(), committed_int(committed, "file/-/rth_rows"));
  EXPECT_EQ(reader.group_count(), committed_int(committed, "file/-/group_count"));
  EXPECT_EQ(rows_seen, reader.rth_rows()) << "every retained row must reach a group";
  EXPECT_EQ(reader.decoded_values(), committed_int(committed, "file/-/decoded_values"));
  for (std::size_t slot = 0; slot < digests.field.size(); ++slot) {
    const std::string name(Digests::field_name(slot));
    EXPECT_EQ(digests.field[slot].non_null(),
              committed_int(committed, "column/" + name + "/n_nonnull"))
        << name;
    EXPECT_EQ(digests.field[slot].nulls(), committed_int(committed, "column/" + name + "/n_null"))
        << name;
    EXPECT_EQ(digests.field[slot].digest_i64(),
              committed_int(committed, "column/" + name + "/digest_i64"))
        << name;
  }
}

TEST(RealSources, StockTradesSessionOneTwentyFiveMatchesTheCommittedDigests) {
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  check_stream<qr::sources::StockTradeReader, qr::sources::StockTradeDigests>(
      kTradesLabel, [&](const std::string& root) {
        return qr::sources::StockTradeReader::open(*scope, root);
      });
}

TEST(RealSources, OptionPrintsSessionOneTwentyFiveMatchesTheCommittedDigests) {
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  check_stream<qr::sources::OptionPrintReader, qr::sources::OptionPrintDigests>(
      kPrintsLabel, [&](const std::string& root) {
        return qr::sources::OptionPrintReader::open(*scope, root);
      });
}

TEST(RealSources, TheStockQuoteRegistryCountsAreCommittedAndAgreeWithTheRegistryItself) {
  // The full 15.4M-row pass is the artifact gate's job; what the suite asserts
  // on every run is that the COMMITTED numbers are the registry's own — so a
  // fixture edited to make the gate pass would fail here.
  const DigestRows committed = load_committed(kQuotesLabel);
  ASSERT_FALSE(committed.empty()) << "no committed rows for " << kQuotesLabel;
  const auto scope = scope_125();
  ASSERT_TRUE(scope.has_value());
  const qr::Session& session = scope->session();
  EXPECT_EQ(committed_int(committed, "file/-/rth_rows"), session.raw_rth_row_count);
  EXPECT_EQ(committed_int(committed, "file/-/group_count"), session.complete_group_count);
  EXPECT_EQ(committed_int(committed, "file/-/registry_raw_rth_row_count"),
            session.raw_rth_row_count);
  EXPECT_EQ(committed_int(committed, "file/-/registry_complete_group_count"),
            session.complete_group_count);
  EXPECT_EQ(committed_int(committed, "file/-/registry_rth_rows_match"), 1);
  EXPECT_EQ(committed_int(committed, "file/-/registry_group_count_match"), 1);
  // The session's own registry row, so the two numbers above are not free.
  EXPECT_EQ(session.raw_rth_row_count, 14'761'979);
  EXPECT_EQ(session.complete_group_count, 2'810'589);
}

TEST(RealSources, TheAuthorizedOptionQuoteShardStillMatchesItsPins) {
  // SCHEMA LEVEL ONLY (B4 is a wave-2 consumer): the footer is parsed and the
  // 19 names and 8 projected forms are checked. No page of this 704MB file is
  // decoded, and no other option-quote session is opened.
  const DigestRows committed = load_committed(kOptionQuotesLabel);
  ASSERT_FALSE(committed.empty()) << "no committed rows for " << kOptionQuotesLabel;
  const std::string path = committed_text(committed, "file/-/path");
  ASSERT_FALSE(path.empty());
  const auto opened = qr::parquet::File::open(path);
  ASSERT_TRUE(opened.has_value()) << opened.error().message();
  const auto checked = qr::sources::check_option_quote_schema(opened.value());
  ASSERT_TRUE(checked.has_value()) << checked.error().message();

  EXPECT_EQ(checked.value().num_rows, committed_int(committed, "file/-/file_rows"));
  EXPECT_EQ(static_cast<std::int64_t>(checked.value().num_row_groups),
            committed_int(committed, "file/-/num_row_groups"));
  EXPECT_EQ(static_cast<std::int64_t>(checked.value().num_leaves), 19);
  const qr::sources::SpecView spec = view_of(qr::sources::kOptionQuoteSpec);
  ASSERT_EQ(checked.value().forms.size(), 8U);
  for (std::size_t slot = 0; slot < checked.value().forms.size(); ++slot) {
    const std::string name(spec.names()[spec.projection()[slot]]);
    EXPECT_EQ(static_cast<std::int64_t>(checked.value().forms[slot]),
              committed_int(committed, "column/" + name + "/form_id"))
        << name;
  }
  // The measured wide profile of that shard.
  EXPECT_EQ(checked.value().forms[0], qr::sources::ColumnForm::DateText);
  EXPECT_EQ(checked.value().forms[1], qr::sources::ColumnForm::DollarF64);
  EXPECT_EQ(checked.value().forms[3], qr::sources::ColumnForm::TimestampMsI64);
  EXPECT_EQ(checked.value().forms[5], qr::sources::ColumnForm::DollarF64);

  // WP3 committed its own row for the same file; the two must agree.
  const DigestRows wp3 = load_committed(kWp3OptionQuotesLabel);
  ASSERT_FALSE(wp3.empty());
  EXPECT_EQ(committed_text(wp3, "file/-/path"), path);
  EXPECT_EQ(committed_int(wp3, "file/-/num_rows"), checked.value().num_rows);
  EXPECT_EQ(committed_int(wp3, "file/-/num_row_groups"),
            static_cast<std::int64_t>(checked.value().num_row_groups));
}

}  // namespace
