// qr_census/tests/test_verdict.cpp — the comparator, its ONE waiver, and the
// archive re-check. This is the M900 fixture block of the WP9 brief:
//
//   * the comparator FAILs on a planted non-WCD delta;
//   * the WCD-1 waiver arithmetic is proven on a synthetic fixture, and the
//     WCD-injection mutant makes the reconciliation path fail first;
//   * a truncated archived verdict is caught by the sha re-check.
#include <cstdio>
#include <string>
#include <vector>

#include <gtest/gtest.h>

#include "qr_census/verdict.hpp"

namespace {

using qr::census::DumpRow;
using qr::census::Verdict;
using qr::census::VerdictReport;
using qr::census::VerdictRow;

DumpRow make(const char* kind, std::int64_t ordinal, const char* stream, const char* name,
             const char* metric, const char* value) {
  DumpRow row;
  row.kind = kind;
  row.ordinal = ordinal;
  row.day = "2022-07-05";
  row.stream = stream;
  row.name = name;
  row.metric = metric;
  row.value = value;
  return row;
}

/// A minimal agreeing pair of dumps: one session, the quote stream, the
/// registry oracle satisfied and one compared column.
void agreeing(std::vector<DumpRow>& cpp_rows, std::vector<DumpRow>& rust_rows) {
  cpp_rows.push_back(make("session", 125, "stock_quotes", "-", "rth_rows", "14761979"));
  cpp_rows.push_back(make("session", 125, "stock_quotes", "-", "group_count", "2810589"));
  cpp_rows.push_back(
      make("session", 125, "stock_quotes", "-", "registry_raw_rth_row_count", "14761979"));
  cpp_rows.push_back(
      make("session", 125, "stock_quotes", "-", "registry_complete_group_count", "2810589"));
  cpp_rows.push_back(make("column", 125, "stock_quotes", "bid_u6", "n_nonnull", "14761979"));
  cpp_rows.push_back(make("column", 125, "stock_quotes", "bid_u6", "n_null", "0"));
  cpp_rows.push_back(make("column", 125, "stock_quotes", "bid_u6", "digest", "424242"));
  cpp_rows.push_back(make("column", 125, "stock_quotes", "bid_u6", "mask_null", "0"));

  rust_rows.push_back(make("session", 125, "stock_quotes", "-", "rth_rows", "14761979"));
  rust_rows.push_back(make("column", 125, "stock_quotes", "bid_u6", "n_nonnull", "14761979"));
  rust_rows.push_back(make("column", 125, "stock_quotes", "bid_u6", "n_null", "0"));
  rust_rows.push_back(make("column", 125, "stock_quotes", "bid_u6", "digest", "424242"));
}

/// The attachment reconciliation of one session, as the two dumps carry it.
void attachment(std::vector<DumpRow>& cpp_rows, std::vector<DumpRow>& rust_rows,
                const char* on_day, const char* wcd, const char* cpp_total, const char* rust_total,
                const char* wcd_skipped) {
  cpp_rows.push_back(make("attach", 125, "stock_trades", "ON_DAY", "count", on_day));
  cpp_rows.push_back(make("attach", 125, "stock_trades", "WRONG_CIVIL_DAY", "count", wcd));
  cpp_rows.push_back(make("attach", 125, "stock_trades", "total", "count", cpp_total));
  rust_rows.push_back(make("attach", 125, "stock_trades", "ON_DAY", "count", on_day));
  rust_rows.push_back(make("attach", 125, "stock_trades", "WRONG_CIVIL_DAY", "count", wcd));
  rust_rows.push_back(make("attach", 125, "stock_trades", "total", "count", rust_total));
  rust_rows.push_back(make("attach", 125, "stock_trades", "wcd_skipped", "count", wcd_skipped));
}

const VerdictRow* find(const VerdictReport& report, const std::string& field) {
  for (const VerdictRow& row : report.rows) {
    if (row.field == field) {
      return &row;
    }
  }
  return nullptr;
}

std::string scratch_path(const char* name) {
  return std::string(QR_TEST_SCRATCH_DIR) + "/" + name;
}

void write_file(const std::string& path, const std::string& text) {
  std::FILE* file = std::fopen(path.c_str(), "wb");
  ASSERT_NE(file, nullptr);
  std::fwrite(text.data(), 1, text.size(), file);
  ASSERT_EQ(std::fclose(file), 0);
}

}  // namespace

// ---------------------------------------------------------------------------
// The agreeing baseline — so that every FAIL below is the planted one.
// ---------------------------------------------------------------------------

TEST(Comparator, TwoAgreeingDumpsProduceNoFailAtAll) {
  std::vector<DumpRow> cpp_rows;
  std::vector<DumpRow> rust_rows;
  agreeing(cpp_rows, rust_rows);
  const VerdictReport report = qr::census::compare_dumps(cpp_rows, rust_rows);
  EXPECT_TRUE(report.green());
  EXPECT_EQ(report.fail, 0);
  EXPECT_GT(report.pass, 0);
  // The registry oracle is compared inside the C++ dump, with no Rust at all.
  const VerdictRow* rows = find(report, "s125|2022-07-05|stock_quotes|registry|rth_rows");
  ASSERT_NE(rows, nullptr);
  EXPECT_EQ(rows->verdict, Verdict::PASS);
  const VerdictRow* groups = find(report, "s125|2022-07-05|stock_quotes|registry|group_count");
  ASSERT_NE(groups, nullptr);
  EXPECT_EQ(groups->verdict, Verdict::PASS);
}

// ---------------------------------------------------------------------------
// M900 fixture 1 — a planted non-WCD delta is a FAIL.
// ---------------------------------------------------------------------------

TEST(Comparator, APlantedNonWcdColumnDeltaIsAFailAndCarriesNoWaiver) {
  std::vector<DumpRow> cpp_rows;
  std::vector<DumpRow> rust_rows;
  agreeing(cpp_rows, rust_rows);
  // ONE digest bit moved. Nothing else changed.
  rust_rows.back().value = "424243";
  const VerdictReport report = qr::census::compare_dumps(cpp_rows, rust_rows);
  EXPECT_FALSE(report.green());
  EXPECT_EQ(report.fail, 1);
  const VerdictRow* row = find(report, "s125|2022-07-05|stock_quotes|bid_u6|digest");
  ASSERT_NE(row, nullptr);
  EXPECT_EQ(row->verdict, Verdict::FAIL);
  EXPECT_EQ(row->waiver_id, qr::census::kNoWaiver);
  EXPECT_EQ(row->oracle_value, "424243");
  EXPECT_EQ(row->cpp_value, "424242");
}

TEST(Comparator, APlantedRegistryCountDeltaIsAFail) {
  std::vector<DumpRow> cpp_rows;
  std::vector<DumpRow> rust_rows;
  agreeing(cpp_rows, rust_rows);
  cpp_rows[1].value = "2810588";  // the group machine lost one group
  const VerdictReport report = qr::census::compare_dumps(cpp_rows, rust_rows);
  EXPECT_FALSE(report.green());
  const VerdictRow* row = find(report, "s125|2022-07-05|stock_quotes|registry|group_count");
  ASSERT_NE(row, nullptr);
  EXPECT_EQ(row->verdict, Verdict::FAIL);
  EXPECT_EQ(row->oracle_value, "2810589");
  EXPECT_EQ(row->cpp_value, "2810588");
}

TEST(Comparator, AKeyOnlyOneSideCarriesIsAFailRatherThanASilentPass) {
  std::vector<DumpRow> cpp_rows;
  std::vector<DumpRow> rust_rows;
  agreeing(cpp_rows, rust_rows);
  cpp_rows.push_back(make("column", 125, "stock_quotes", "ask_u6", "digest", "99"));
  const VerdictReport report = qr::census::compare_dumps(cpp_rows, rust_rows);
  EXPECT_FALSE(report.green());
  const VerdictRow* row = find(report, "s125|2022-07-05|stock_quotes|ask_u6|digest");
  ASSERT_NE(row, nullptr);
  EXPECT_EQ(row->verdict, Verdict::FAIL);
  EXPECT_EQ(row->oracle_value, "ABSENT");
}

TEST(Comparator, TheCppOnlyCensusMetricsArePublishedRatherThanCompared) {
  std::vector<DumpRow> cpp_rows;
  std::vector<DumpRow> rust_rows;
  agreeing(cpp_rows, rust_rows);
  const VerdictReport report = qr::census::compare_dumps(cpp_rows, rust_rows);
  EXPECT_TRUE(report.green());
  const VerdictRow* mask = find(report, "s125|2022-07-05|stock_quotes|bid_u6|mask_null");
  ASSERT_NE(mask, nullptr);
  EXPECT_EQ(mask->verdict, Verdict::CENSUS);
  const VerdictRow* groups = find(report, "s125|2022-07-05|stock_quotes|-|group_count");
  ASSERT_NE(groups, nullptr);
  EXPECT_EQ(groups->verdict, Verdict::CENSUS);
}

TEST(Comparator, EveryNonComparedColumnIsEnumeratedInTheVerdictWithItsSideAndReason) {
  std::vector<DumpRow> cpp_rows;
  std::vector<DumpRow> rust_rows;
  agreeing(cpp_rows, rust_rows);
  const VerdictReport report = qr::census::compare_dumps(cpp_rows, rust_rows);
  // 4 + 9 + 17 + 0 projected columns sit outside the intersection.
  EXPECT_EQ(report.not_compared, 30);
  const VerdictRow* side = find(report, "options_prints|side|projection");
  ASSERT_NE(side, nullptr);
  EXPECT_EQ(side->verdict, Verdict::NOT_COMPARED);
  EXPECT_EQ(side->oracle_value, "rust_only");
  EXPECT_FALSE(side->cpp_value.empty());
  const VerdictRow* exchange = find(report, "stock_quotes|bid_exchange|projection");
  ASSERT_NE(exchange, nullptr);
  EXPECT_EQ(exchange->oracle_value, "cpp_only");
}

// ---------------------------------------------------------------------------
// M900 fixture 2 — the WCD-1 arithmetic.
// ---------------------------------------------------------------------------

TEST(WcdWaiver, TheArithmeticIsExactAndOnlyAppliesWhenThereIsSomethingToWaive) {
  EXPECT_TRUE(qr::census::wcd_waiver_holds(1000, 993, 7));
  EXPECT_FALSE(qr::census::wcd_waiver_holds(1000, 993, 6));   // one short
  EXPECT_FALSE(qr::census::wcd_waiver_holds(1000, 993, 8));   // one over
  EXPECT_FALSE(qr::census::wcd_waiver_holds(1000, 1000, 0));  // nothing to waive
  EXPECT_FALSE(qr::census::wcd_waiver_holds(1000, 1001, -1));
}

TEST(WcdWaiver, WcdOneIsTheOnlyLegalWaiverId) {
  EXPECT_TRUE(qr::census::is_legal_waiver_id("WCD-1"));
  EXPECT_FALSE(qr::census::is_legal_waiver_id("WCD-2"));
  EXPECT_FALSE(qr::census::is_legal_waiver_id("-"));
  EXPECT_FALSE(qr::census::is_legal_waiver_id(""));
}

TEST(WcdWaiver, AnInjectedWrongCivilDayAttachmentIsWaivedByExactlyItsOwnCount) {
  std::vector<DumpRow> cpp_rows;
  std::vector<DumpRow> rust_rows;
  agreeing(cpp_rows, rust_rows);
  // THE INJECTION: seven attachments name another civil day. This port
  // totalizes them into its bucket total; the production Rust reader would have
  // aborted, and the diagnostic build counts and skips them.
  attachment(cpp_rows, rust_rows, "993", "7", "1000", "993", "7");
  const VerdictReport report = qr::census::compare_dumps(cpp_rows, rust_rows);
  EXPECT_TRUE(report.green());
  EXPECT_EQ(report.waived, 1);
  const VerdictRow* row = find(report, "s125|2022-07-05|stock_trades|attach|total");
  ASSERT_NE(row, nullptr);
  EXPECT_EQ(row->verdict, Verdict::WAIVED);
  EXPECT_EQ(row->waiver_id, "WCD-1");
  EXPECT_EQ(row->oracle_value, "993");
  EXPECT_EQ(row->cpp_value, "1000");
}

TEST(WcdWaiver, ADeltaThatIsNotExactlyTheWrongCivilDayCountIsAFail) {
  std::vector<DumpRow> cpp_rows;
  std::vector<DumpRow> rust_rows;
  agreeing(cpp_rows, rust_rows);
  // Same injection, but the totals are off by one more than the WCD count.
  attachment(cpp_rows, rust_rows, "993", "7", "1001", "993", "7");
  const VerdictReport report = qr::census::compare_dumps(cpp_rows, rust_rows);
  EXPECT_FALSE(report.green());
  const VerdictRow* row = find(report, "s125|2022-07-05|stock_trades|attach|total");
  ASSERT_NE(row, nullptr);
  EXPECT_EQ(row->verdict, Verdict::FAIL);
  EXPECT_EQ(row->waiver_id, qr::census::kNoWaiver);
}

TEST(WcdWaiver, WithoutAnyWrongCivilDayAttachmentTheTotalsMustAgreeOutright) {
  std::vector<DumpRow> cpp_rows;
  std::vector<DumpRow> rust_rows;
  agreeing(cpp_rows, rust_rows);
  attachment(cpp_rows, rust_rows, "1000", "0", "1000", "1000", "0");
  const VerdictReport report = qr::census::compare_dumps(cpp_rows, rust_rows);
  EXPECT_TRUE(report.green());
  EXPECT_EQ(report.waived, 0);
  const VerdictRow* row = find(report, "s125|2022-07-05|stock_trades|attach|total");
  ASSERT_NE(row, nullptr);
  EXPECT_EQ(row->verdict, Verdict::PASS);
}

TEST(WcdWaiver, TheBucketHistogramItselfIsComparedExactlyAndNeverWaived) {
  std::vector<DumpRow> cpp_rows;
  std::vector<DumpRow> rust_rows;
  agreeing(cpp_rows, rust_rows);
  attachment(cpp_rows, rust_rows, "993", "7", "1000", "993", "7");
  // The two sides disagree about WHICH rows were wrong-civil-day, while the
  // totals still reconcile. That is a FAIL: the waiver covers the abort, not
  // the classification.
  rust_rows[rust_rows.size() - 3].value = "6";  // WRONG_CIVIL_DAY bucket
  const VerdictReport report = qr::census::compare_dumps(cpp_rows, rust_rows);
  EXPECT_FALSE(report.green());
  const VerdictRow* bucket =
      find(report, "s125|2022-07-05|stock_trades|WRONG_CIVIL_DAY|count");
  ASSERT_NE(bucket, nullptr);
  EXPECT_EQ(bucket->verdict, Verdict::FAIL);
}

// ---------------------------------------------------------------------------
// M900 fixture 3 — the archived verdict is re-checked, not trusted.
// ---------------------------------------------------------------------------

TEST(Archive, AnIntactVerdictVerifiesAgainstItsRecordedSha) {
  std::vector<DumpRow> cpp_rows;
  std::vector<DumpRow> rust_rows;
  agreeing(cpp_rows, rust_rows);
  attachment(cpp_rows, rust_rows, "993", "7", "1000", "993", "7");
  const std::string text = qr::census::compare_dumps(cpp_rows, rust_rows).to_tsv();
  const std::string path = scratch_path("wp9_archive_intact.tsv");
  write_file(path, text);
  const auto sha = qr::census::file_sha256(path);
  ASSERT_TRUE(sha.has_value()) << sha.error().message();
  const auto summary = qr::census::verify_archive(path, sha.value());
  ASSERT_TRUE(summary.has_value()) << summary.error().message();
  EXPECT_EQ(summary.value().fail, 0);
  EXPECT_EQ(summary.value().waived, 1);
}

TEST(Archive, ATruncatedVerdictIsCaughtByTheShaRecheck) {
  std::vector<DumpRow> cpp_rows;
  std::vector<DumpRow> rust_rows;
  agreeing(cpp_rows, rust_rows);
  rust_rows.back().value = "424243";  // one real FAIL row lives in this verdict
  const std::string text = qr::census::compare_dumps(cpp_rows, rust_rows).to_tsv();
  const std::string path = scratch_path("wp9_archive_truncated.tsv");
  write_file(path, text);
  const auto sha = qr::census::file_sha256(path);
  ASSERT_TRUE(sha.has_value()) << sha.error().message();

  // THE ATTACK: drop the tail — which is where the FAIL rows are — and leave a
  // file that still parses and still says "no failures".
  const std::size_t keep = text.find('\n', text.find('\n') + 1) + 1;
  write_file(path, text.substr(0, keep));
  const auto truncated_summary = qr::census::parse_verdict(text.substr(0, keep));
  ASSERT_TRUE(truncated_summary.has_value());
  EXPECT_EQ(truncated_summary.value().fail, 0) << "the truncation really does hide the failure";

  const auto refused = qr::census::verify_archive(path, sha.value());
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::SOURCE_AUTHENTICATION_FAILED);
}

TEST(Archive, AnEditedVerdictHeaderIsARefusal) {
  const std::string path = scratch_path("wp9_archive_header.tsv");
  const std::string text = "field\toracle\tcpp\tverdict\twaiver\nx\ty\tz\tPASS\t-\n";
  write_file(path, text);
  const auto sha = qr::census::file_sha256(path);
  ASSERT_TRUE(sha.has_value());
  const auto refused = qr::census::verify_archive(path, sha.value());
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
}

TEST(Archive, AWaiverIdOutsideTheClosedSetIsARefusalEvenWithAMatchingSha) {
  const std::string path = scratch_path("wp9_archive_waiver.tsv");
  std::string text(qr::census::kVerdictHeader);
  text += "\nsomething|else\t1\t2\tWAIVED\tWCD-2\n";
  write_file(path, text);
  const auto sha = qr::census::file_sha256(path);
  ASSERT_TRUE(sha.has_value());
  const auto refused = qr::census::verify_archive(path, sha.value());
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}

TEST(Archive, ANonWaivedRowMayNotSmuggleAWaiverId) {
  std::string text(qr::census::kVerdictHeader);
  text += "\nsomething|else\t1\t2\tFAIL\tWCD-1\n";
  const auto refused = qr::census::parse_verdict(text);
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}
