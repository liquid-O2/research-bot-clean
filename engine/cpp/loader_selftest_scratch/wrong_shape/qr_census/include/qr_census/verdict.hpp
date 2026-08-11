// qr_census/verdict.hpp — THE COMPARATOR AND ITS ONE LEGAL WAIVER.
//
// SPEC (WP9 brief, verbatim): "(e) comparator emits verdict.tsv (field,
//   oracle_value, cpp_value, verdict PASS/FAIL/WAIVED, waiver_id) — sole legal
//   waiver WCD-1; any other delta = FAIL nonzero exit".
// SPEC (WP9 brief, verbatim): "(d) WCD reconciliation: ... cpp_bucket_total ==
//   rust_total + wcd_count with ordinals enumerated".
// SPEC (FINAL_PLAN.md section 6, oracle 3, verbatim): "WCD reconciliation runs
//   against a separately-SHA'd diagnostic count-and-skip Rust build (the
//   production Rust build aborts on WCD days — review F15), with a WCD-injection
//   mutant proving the reconciliation path fails first."
//
// WHAT A WAIVER IS HERE. Exactly one delta in this differential is legitimate,
// and it is legitimate for a reason that is written down and arithmetic: the
// production Rust reader ABORTS the moment an attachment stamp names a
// different civil day (`corpus/src/reader.rs:1173`'s `?`), so the largest
// attachment total a production Rust build can ever report is short by exactly
// the number of wrong-civil-day attachments. This port totalizes instead
// ("WCD fix = totalize, don't catch"), so its bucket total counts them. WCD-1
// is that identity and nothing else:
//
//     cpp_bucket_total == rust_total + wcd_count,  wcd_count > 0
//
// If the identity does not hold to the unit, the row is a FAIL. If wcd_count is
// zero the row is a PASS — there is nothing to waive. No other field in the
// verdict may ever carry a waiver_id: `apply_waiver` refuses any other id, so a
// second waiver cannot be introduced by editing a table.
#ifndef QR_CENSUS_VERDICT_HPP
#define QR_CENSUS_VERDICT_HPP

#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

#include "qr_census/differential.hpp"

namespace qr::census {

/// The verdict of one compared field.
enum class Verdict : std::uint8_t {
  /// The two sides agree to the unit.
  PASS = 0,
  /// They do not, and no waiver covers it. One of these fails the gate.
  FAIL = 1,
  /// They differ by exactly the amount a written, arithmetic waiver predicts.
  WAIVED = 2,
  /// A number only one side can produce, published rather than compared.
  CENSUS = 3,
  /// A projected column outside the intersection: named, sided, and reasoned,
  /// so the oracle's coverage is a published fact.
  NOT_COMPARED = 4,
};

[[nodiscard]] const char* verdict_name(Verdict verdict) noexcept;

/// THE ONLY WAIVER ID THIS PROGRAM RECOGNISES.
inline constexpr std::string_view kWcdWaiverId = "WCD-1";
/// The waiver_id column's value when a row carries no waiver.
inline constexpr std::string_view kNoWaiver = "-";

struct VerdictRow {
  std::string field;
  std::string oracle_value;
  std::string cpp_value;
  Verdict verdict = Verdict::PASS;
  std::string waiver_id{kNoWaiver};
};

/// THE WCD-1 ARITHMETIC, as its own testable predicate. True iff the delta is
/// exactly the wrong-civil-day count and that count is positive.
[[nodiscard]] bool wcd_waiver_holds(std::int64_t cpp_bucket_total, std::int64_t rust_total,
                                    std::int64_t wcd_count) noexcept;

/// THE CLOSED WAIVER SET, as a predicate. Exactly one id is legal, and it is a
/// function rather than a table so a second waiver cannot be added by data.
[[nodiscard]] bool is_legal_waiver_id(std::string_view waiver_id) noexcept;

/// Stamps `row` as WAIVED under `waiver_id`. Any id other than WCD-1 is a
/// programmer-contract violation and fails fast: the waiver set is closed.
void apply_waiver(VerdictRow& row, std::string_view waiver_id);

/// The comparator's outcome.
struct VerdictReport {
  std::vector<VerdictRow> rows;
  std::int64_t pass = 0;
  std::int64_t fail = 0;
  std::int64_t waived = 0;
  std::int64_t census = 0;
  std::int64_t not_compared = 0;

  /// The gate's answer: any FAIL at all.
  [[nodiscard]] bool green() const noexcept { return fail == 0; }
  /// Deterministic TSV, header first, rows in the order they were produced
  /// (which is the sorted join order — never a map's iteration order).
  [[nodiscard]] std::string to_tsv() const;
};

/// The verdict TSV header, pinned so a truncated or edited archive is a parse
/// refusal rather than a silent pass.
inline constexpr std::string_view kVerdictHeader =
    "field\toracle_value\tcpp_value\tverdict\twaiver_id";

/// COMPARES THE TWO DUMPS.
///
/// * every key present on both sides is compared to the unit;
/// * the registry oracle is compared inside the C++ dump (the registry is the
///   oracle there — no Rust is needed for it, FINAL_PLAN section 6);
/// * keys only one side can produce are CENSUS rows, by a closed table;
/// * the attachment total carries the WCD-1 waiver and nothing else does;
/// * a key present on one side only, outside that closed table, is a FAIL —
///   a missing counterpart is a hole in the differential, not an absence of
///   evidence.
[[nodiscard]] VerdictReport compare_dumps(const std::vector<DumpRow>& cpp_rows,
                                          const std::vector<DumpRow>& rust_rows);

// ---------------------------------------------------------------------------
// The archived verdict, and why it is sha-checked rather than trusted.
// ---------------------------------------------------------------------------

/// The summary the gate re-checks an archived verdict against. A verdict file
/// is evidence only if it is the SAME file the full-scope run wrote: a
/// truncated archive is the exact failure mode that turns "no FAIL rows" into
/// a lie, because the FAIL rows are simply not in the bytes any more.
struct ArchiveSummary {
  std::string sha256;
  std::int64_t rows = 0;
  std::int64_t pass = 0;
  std::int64_t fail = 0;
  std::int64_t waived = 0;
  std::int64_t census = 0;
  std::int64_t not_compared = 0;
};

/// Lowercase hex sha256 of a file's bytes.
[[nodiscard]] Expected<std::string, Refusal> file_sha256(const std::string& path);

/// Re-reads an archived verdict: the sha256 must equal `expected_sha256`, the
/// header must be the pinned one, every row must carry five fields and a known
/// verdict name, and no row may carry a waiver id outside the closed set. Any
/// of those failing is a refusal — the archive is not evidence.
[[nodiscard]] Expected<ArchiveSummary, Refusal> verify_archive(const std::string& path,
                                                               std::string_view expected_sha256);

/// Parses a verdict TSV that is already in memory (the parse half of
/// `verify_archive`, exposed so a fixture can exercise it without a file).
[[nodiscard]] Expected<ArchiveSummary, Refusal> parse_verdict(std::string_view text);

}  // namespace qr::census

#endif  // QR_CENSUS_VERDICT_HPP
