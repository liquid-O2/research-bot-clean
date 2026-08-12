// qr_candidates/rowgroup_table.hpp — rowgroup-addressed session decoding.
//
// SPEC (evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 1, verbatim):
//
//   "The projection physically stores neither `session_ordinal` nor
//    `member_count`. A session ordinal is derived only by selecting physical
//    rowgroup `i`, requiring index row `i` to have `ordinal=i<=749`, requiring
//    that rowgroup's `day` statistics have min=max equal to the indexed day,
//    requiring every decoded `day` to equal it, and requiring decoded row count
//    equal the index row count. No predicate scan or later rowgroup is
//    permitted. Projection is restricted to `day,row_kind,candidate_id,
//    physical_event_id,stream_policy_name,stream_reversal_bps,visible_ts_ns,
//    member_signal_ids`; no side, final relation, matrix, label, score,
//    outcome, or nonexistent derived column may be opened."
//
// WHY ADDRESSING BEATS FILTERING. A predicate scan (`WHERE day = ...`) would
// make the session identity a property of the DATA — one mislabelled row and a
// session silently acquires a neighbour's candidates. Physical addressing makes
// it a property of the LAYOUT, and then proves the layout four independent
// ways: the index says ordinal i is that day, the rowgroup's own writer
// statistics say every value in it is that day, every decoded value is that
// day, and the decoded row count is the count the index declares. Any single
// disagreement refuses the session.
//
// THE COLUMN WALL. `open` takes the allowlist and resolves it BEFORE anything
// is decoded; `read_session` can only ever hand back allowlisted columns, and a
// name outside the allowlist has no code path that reaches a leaf index. The
// forbidden list is carried explicitly as well, so a reviewer reads the refusal
// rather than inferring it from an absence.
#ifndef QR_CANDIDATES_ROWGROUP_TABLE_HPP
#define QR_CANDIDATES_ROWGROUP_TABLE_HPP

#include <cstdint>
#include <memory>
#include <string>
#include <string_view>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_parquet/reader.hpp"

namespace qr::candidates {

/// The wall this module never crosses (card section 1: "Any path/session >=750
/// ... is refused before payload resolution").
inline constexpr std::uint32_t kMaxSessionOrdinal = 917;  // AMENDMENT 2026-08-12-c (was 749)
/// Every publication in this program carries one row group per calendar
/// session of the 1,003-session registry.
inline constexpr std::size_t kPublicationRowGroups = 1003;

/// One `*_session_index.tsv` row.
struct SessionIndexRow {
  std::uint32_t ordinal = 0;
  std::string day;
  std::int64_t rows = 0;
};

/// The sha-gated session index, parsed only through ordinal 749.
///
/// The file itself covers all 1,003 sessions and its whole-file digest is the
/// bound authority, so the digest is verified over every byte; but only rows
/// 0..749 are ever PARSED or exposed, so no out-of-scope session can be named
/// by anything downstream.
class SessionIndex {
 public:
  [[nodiscard]] static Expected<SessionIndex, Refusal> load(const std::string& path,
                                                            std::string_view expected_sha256);
  /// Parses caller-held text without a digest gate. Fixtures only.
  [[nodiscard]] static Expected<SessionIndex, Refusal> parse_without_digest_gate(
      std::string_view text);

  /// Index row for `ordinal`. Refuses past 917 and refuses a row whose own
  /// `ordinal` cell is not `ordinal` (card: "requiring index row `i` to have
  /// `ordinal=i<=917`").
  [[nodiscard]] Expected<const SessionIndexRow*, Refusal> at(std::uint32_t ordinal) const noexcept;
  [[nodiscard]] std::size_t size() const noexcept { return rows_.size(); }
  [[nodiscard]] const std::string& sha256() const noexcept { return sha256_; }

  /// An empty index. Every lookup refuses UNKNOWN_SESSION, so a table that was
  /// never given a real index cannot resolve a session by accident.
  SessionIndex() = default;

 private:
  std::vector<SessionIndexRow> rows_;
  std::string sha256_;
};

/// The decoded, allowlisted columns of exactly one session.
class SessionColumns {
 public:
  [[nodiscard]] std::uint32_t ordinal() const noexcept { return ordinal_; }
  [[nodiscard]] const std::string& day() const noexcept { return day_; }
  [[nodiscard]] std::int64_t num_rows() const noexcept { return num_rows_; }
  [[nodiscard]] std::size_t num_columns() const noexcept { return columns_.size(); }

  /// Column position of an allowlisted name, or a refusal. This is the ONLY
  /// way to reach a column, so an unallowlisted name cannot be read.
  [[nodiscard]] Expected<std::size_t, Refusal> column(std::string_view name) const noexcept;

  /// Cell value. A null cell is reported as absent, never as an empty string:
  /// the two are different states and the card forbids collapsing them.
  [[nodiscard]] bool is_null(std::size_t column, std::int64_t row) const noexcept;
  [[nodiscard]] std::string_view value(std::size_t column, std::int64_t row) const noexcept;

  friend class RowGroupTable;

 private:
  std::uint32_t ordinal_ = 0;
  std::string day_;
  std::int64_t num_rows_ = 0;
  std::vector<std::string> names_;
  std::vector<qr::parquet::ColumnData> columns_;
};

/// A publication parquet whose physical row group `i` IS session ordinal `i`.
class RowGroupTable {
 public:
  RowGroupTable(const RowGroupTable&) = delete;
  RowGroupTable& operator=(const RowGroupTable&) = delete;
  RowGroupTable(RowGroupTable&&) noexcept;
  RowGroupTable& operator=(RowGroupTable&&) noexcept;
  ~RowGroupTable();

  /// Opens the parquet and pins it: 1,003 row groups, every allowlisted name
  /// present, no forbidden name requested, and (when `expected_sha256` is
  /// non-empty) the pinned whole-file digest.
  ///
  /// `refusal_detail`, when non-null, receives the decoder's own full message
  /// on a refusal. `qr::Refusal` carries only static strings by design, and a
  /// dialect refusal names a column and an enum value that a reader needs to
  /// see; discarding it would turn a precise wall into a shrug.
  ///
  /// `expected_row_groups` is the layout pin: production passes
  /// `kPublicationRowGroups`, because "row group i IS session i" is only true
  /// of a file with one group per registered session. Fixtures pass their own
  /// count; a file whose count differs from the expectation refuses.
  [[nodiscard]] static Expected<RowGroupTable, Refusal> open(
      const std::string& path, std::string_view expected_sha256, SessionIndex index,
      const std::vector<std::string_view>& allowlist,
      const std::vector<std::string_view>& forbidden,
      std::size_t expected_row_groups = kPublicationRowGroups,
      std::string* refusal_detail = nullptr);

  /// Decodes physical row group `ordinal`, running all four identity checks.
  [[nodiscard]] Expected<SessionColumns, Refusal> read_session(std::uint32_t ordinal) const;

  [[nodiscard]] const SessionIndex& index() const noexcept { return index_; }
  [[nodiscard]] const std::string& sha256() const noexcept { return sha256_; }

 private:
  RowGroupTable() = default;

  std::unique_ptr<qr::parquet::File> file_;
  SessionIndex index_;
  std::string sha256_;
  std::vector<std::string> names_;
  std::vector<std::size_t> leaves_;
  std::size_t day_leaf_ = 0;
  mutable std::unique_ptr<qr::parquet::DecodeWorkspace> workspace_;
};

}  // namespace qr::candidates

#endif  // QR_CANDIDATES_ROWGROUP_TABLE_HPP
