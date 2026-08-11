#include "qr_candidates/rowgroup_table.hpp"

#include <algorithm>
#include <cstdio>
#include <vector>

#include "qr_candidates/parse.hpp"
#include "qr_candidates/signal_root.hpp"

namespace qr::candidates {
namespace {

constexpr const char* kIndexSite = "qr_candidates::SessionIndex";
constexpr const char* kTableSite = "qr_candidates::RowGroupTable";
constexpr std::string_view kSessionIndexHeader = "ordinal\tday\trows";

/// A civil day as the publications spell it: exactly `YYYY-MM-DD`, digits and
/// dashes only. Shape-checked here so a rowgroup statistic can be compared to
/// an index cell without either side being free-form text.
[[nodiscard]] bool is_civil_day(std::string_view text) noexcept {
  if (text.size() != 10 || text[4] != '-' || text[7] != '-') {
    return false;
  }
  for (std::size_t i : {0U, 1U, 2U, 3U, 5U, 6U, 8U, 9U}) {
    const auto byte = static_cast<unsigned char>(text[i]);
    if (byte < '0' || byte > '9') {
      return false;
    }
  }
  return true;
}

}  // namespace

// --- SessionIndex -----------------------------------------------------------

Expected<SessionIndex, Refusal> SessionIndex::load(const std::string& path,
                                                   std::string_view expected_sha256) {
  if (!expected_sha256.empty()) {
    const auto digest = sha256_file_hex(path);
    if (!digest) {
      return refuse<SessionIndex>(digest.error());
    }
    if (digest.value() != expected_sha256) {
      return refuse<SessionIndex>(Refusal(RefusalCode::SOURCE_AUTHENTICATION_FAILED, kIndexSite,
                                          "session index does not hash to its pinned digest"));
    }
  }
  std::FILE* file = std::fopen(path.c_str(), "rb");
  if (file == nullptr) {
    return refuse<SessionIndex>(
        Refusal(RefusalCode::IO, kIndexSite, "cannot open the session index"));
  }
  std::string text;
  char block[1 << 16];
  while (true) {
    const std::size_t got = std::fread(block, 1, sizeof(block), file);
    text.append(block, got);
    if (got < sizeof(block)) {
      break;
    }
  }
  std::fclose(file);
  auto parsed = parse_without_digest_gate(text);
  if (!parsed) {
    return parsed;
  }
  SessionIndex index = std::move(parsed).value();
  index.sha256_.assign(expected_sha256);
  return index;
}

Expected<SessionIndex, Refusal> SessionIndex::parse_without_digest_gate(std::string_view text) {
  SessionIndex index;
  std::size_t at = 0;
  std::uint32_t expected = 0;
  bool header_seen = false;
  while (at < text.size()) {
    const std::size_t newline = text.find('\n', at);
    const std::string_view line =
        text.substr(at, newline == std::string_view::npos ? std::string_view::npos : newline - at);
    at = newline == std::string_view::npos ? text.size() : newline + 1;
    if (line.empty()) {
      continue;
    }
    if (!header_seen) {
      if (line != kSessionIndexHeader) {
        return refuse<SessionIndex>(Refusal(RefusalCode::SCHEMA_MISMATCH, kIndexSite,
                                            "session index header is not ordinal/day/rows"));
      }
      header_seen = true;
      continue;
    }
    // ONLY ordinals 0..749 are parsed. The tail of the file describes sessions
    // this program may never read, so it is skipped without being interpreted.
    if (expected > kMaxSessionOrdinal) {
      break;
    }
    const std::size_t first = line.find('\t');
    const std::size_t second = first == std::string_view::npos
                                   ? std::string_view::npos
                                   : line.find('\t', first + 1);
    if (first == std::string_view::npos || second == std::string_view::npos ||
        line.find('\t', second + 1) != std::string_view::npos) {
      return refuse<SessionIndex>(Refusal(RefusalCode::SCHEMA_MISMATCH, kIndexSite,
                                          "session index row is not three cells",
                                          static_cast<std::int64_t>(expected)));
    }
    const auto ordinal = parse_u32(line.substr(0, first), kIndexSite);
    if (!ordinal) {
      return refuse<SessionIndex>(ordinal.error());
    }
    if (ordinal.value() != expected) {
      return refuse<SessionIndex>(Refusal(RefusalCode::OUT_OF_ORDER, kIndexSite,
                                          "session index is not the dense 0.. ladder",
                                          static_cast<std::int64_t>(ordinal.value())));
    }
    const std::string_view day = line.substr(first + 1, second - first - 1);
    if (!is_civil_day(day)) {
      return refuse<SessionIndex>(Refusal(RefusalCode::MALFORMED_CIVIL_DATE, kIndexSite,
                                          "session index day is not YYYY-MM-DD",
                                          static_cast<std::int64_t>(expected)));
    }
    const auto rows = parse_u64(line.substr(second + 1), kIndexSite);
    if (!rows) {
      return refuse<SessionIndex>(rows.error());
    }
    if (rows.value() > static_cast<std::uint64_t>(INT64_MAX)) {
      return refuse<SessionIndex>(
          Refusal(RefusalCode::ARITHMETIC_OVERFLOW, kIndexSite, "session index row count overflows"));
    }
    SessionIndexRow row;
    row.ordinal = ordinal.value();
    row.day.assign(day);
    row.rows = static_cast<std::int64_t>(rows.value());
    index.rows_.push_back(std::move(row));
    expected += 1;
  }
  if (!header_seen) {
    return refuse<SessionIndex>(
        Refusal(RefusalCode::SCHEMA_MISMATCH, kIndexSite, "session index has no header"));
  }
  return index;
}

Expected<const SessionIndexRow*, Refusal> SessionIndex::at(std::uint32_t ordinal) const noexcept {
  if (ordinal > kMaxSessionOrdinal) {
    return refuse<const SessionIndexRow*>(Refusal(RefusalCode::ORDINAL_OUTSIDE_SCOPE, kIndexSite,
                                                  "ordinal is past the 749 wall",
                                                  static_cast<std::int64_t>(ordinal)));
  }
  if (static_cast<std::size_t>(ordinal) >= rows_.size()) {
    return refuse<const SessionIndexRow*>(Refusal(RefusalCode::UNKNOWN_SESSION, kIndexSite,
                                                  "session index has no row for this ordinal",
                                                  static_cast<std::int64_t>(ordinal)));
  }
  const SessionIndexRow& row = rows_[ordinal];
  if (row.ordinal != ordinal) {
    return refuse<const SessionIndexRow*>(Refusal(RefusalCode::CONTENT_MISMATCH, kIndexSite,
                                                  "index row i does not declare ordinal i",
                                                  static_cast<std::int64_t>(row.ordinal)));
  }
  return &row;
}

// --- SessionColumns ---------------------------------------------------------

Expected<std::size_t, Refusal> SessionColumns::column(std::string_view name) const noexcept {
  for (std::size_t i = 0; i < names_.size(); ++i) {
    if (names_[i] == name) {
      return i;
    }
  }
  return refuse<std::size_t>(Refusal(RefusalCode::SCHEMA_MISMATCH, "qr_candidates::SessionColumns",
                                     "column is not in the projection allowlist",
                                     static_cast<std::int64_t>(name.size())));
}

bool SessionColumns::is_null(std::size_t column, std::int64_t row) const noexcept {
  if (column >= columns_.size() || row < 0 || row >= columns_[column].num_rows) {
    return true;
  }
  return columns_[column].is_null(row);
}

std::string_view SessionColumns::value(std::size_t column, std::int64_t row) const noexcept {
  if (column >= columns_.size() || row < 0 || row >= columns_[column].num_rows) {
    return {};
  }
  return columns_[column].byte_array(row);
}

// --- RowGroupTable ----------------------------------------------------------

RowGroupTable::RowGroupTable(RowGroupTable&&) noexcept = default;
RowGroupTable& RowGroupTable::operator=(RowGroupTable&&) noexcept = default;
RowGroupTable::~RowGroupTable() = default;

Expected<RowGroupTable, Refusal> RowGroupTable::open(
    const std::string& path, std::string_view expected_sha256, SessionIndex index,
    const std::vector<std::string_view>& allowlist,
    const std::vector<std::string_view>& forbidden, std::size_t expected_row_groups,
    std::string* refusal_detail) {
  if (refusal_detail != nullptr) {
    refusal_detail->clear();
  }
  if (allowlist.empty()) {
    return refuse<RowGroupTable>(
        Refusal(RefusalCode::CONFIG, kTableSite, "an empty projection allowlist is not a projection"));
  }
  // THE COLUMN WALL, checked before the file is even opened: a name that is
  // both allowlisted and forbidden, or a repeated name, is a defect in the
  // caller and refuses here rather than resolving to some leaf.
  for (std::size_t i = 0; i < allowlist.size(); ++i) {
    for (std::size_t j = i + 1; j < allowlist.size(); ++j) {
      if (allowlist[i] == allowlist[j]) {
        return refuse<RowGroupTable>(Refusal(RefusalCode::CONFIG, kTableSite,
                                             "projection allowlist repeats a column"));
      }
    }
    for (const std::string_view banned : forbidden) {
      if (allowlist[i] == banned) {
        return refuse<RowGroupTable>(Refusal(RefusalCode::CONFIG, kTableSite,
                                             "projection allowlist names a forbidden column"));
      }
    }
  }
  if (!expected_sha256.empty()) {
    const auto digest = sha256_file_hex(path);
    if (!digest) {
      return refuse<RowGroupTable>(digest.error());
    }
    if (digest.value() != expected_sha256) {
      return refuse<RowGroupTable>(Refusal(RefusalCode::SOURCE_AUTHENTICATION_FAILED, kTableSite,
                                           "publication does not hash to its pinned digest"));
    }
  }

  // THE PUBLICATION PROFILE (ruling CC-003). A publication reader declares the
  // family it reads; a corpus-shaped file (OPTIONAL leaves, an INT64 column)
  // is refused here exactly as loudly as a publication-shaped file is refused
  // by a corpus reader.
  auto opened = qr::parquet::File::open(path, qr::parquet::DialectProfile::PUBLICATION);
  if (!opened) {
    if (refusal_detail != nullptr) {
      *refusal_detail = opened.error().message();
    }
    return refuse<RowGroupTable>(Refusal(opened.error().code(), kTableSite,
                                         "the publication parquet refused to open",
                                         opened.error().context()));
  }
  RowGroupTable table;
  table.file_ = std::make_unique<qr::parquet::File>(std::move(opened).value());
  table.index_ = std::move(index);
  table.sha256_.assign(expected_sha256);
  table.workspace_ = std::make_unique<qr::parquet::DecodeWorkspace>();

  if (table.file_->num_row_groups() != expected_row_groups) {
    return refuse<RowGroupTable>(
        Refusal(RefusalCode::SCHEMA_MISMATCH, kTableSite,
                "publication does not carry one row group per registered session",
                static_cast<std::int64_t>(table.file_->num_row_groups())));
  }
  // Every forbidden name must EXIST in the schema and never be resolved: if a
  // rename ever made one of them disappear, this refuses rather than quietly
  // guarding nothing.
  for (const std::string_view banned : forbidden) {
    const auto leaf = table.file_->leaf_index(banned);
    if (!leaf) {
      return refuse<RowGroupTable>(Refusal(RefusalCode::SCHEMA_MISMATCH, kTableSite,
                                           "a forbidden column is missing from the schema",
                                           static_cast<std::int64_t>(banned.size())));
    }
  }
  for (const std::string_view name : allowlist) {
    const auto leaf = table.file_->leaf_index(name);
    if (!leaf) {
      return refuse<RowGroupTable>(Refusal(RefusalCode::SCHEMA_MISMATCH, kTableSite,
                                           "an allowlisted column is missing from the schema",
                                           static_cast<std::int64_t>(name.size())));
    }
    if (table.file_->leaves()[leaf.value()].type != qr::parquet::LeafType::BYTE_ARRAY) {
      return refuse<RowGroupTable>(Refusal(RefusalCode::SCHEMA_MISMATCH, kTableSite,
                                           "an allowlisted column is not a BYTE_ARRAY leaf",
                                           static_cast<std::int64_t>(leaf.value())));
    }
    table.names_.emplace_back(name);
    table.leaves_.push_back(leaf.value());
    if (name == "day") {
      table.day_leaf_ = leaf.value();
    }
  }
  const auto day_leaf = table.file_->leaf_index("day");
  if (!day_leaf) {
    return refuse<RowGroupTable>(
        Refusal(RefusalCode::SCHEMA_MISMATCH, kTableSite, "publication has no `day` column"));
  }
  table.day_leaf_ = day_leaf.value();
  if (std::find(table.names_.begin(), table.names_.end(), "day") == table.names_.end()) {
    return refuse<RowGroupTable>(Refusal(RefusalCode::CONFIG, kTableSite,
                                         "`day` must be projected: it is the session identity"));
  }
  return table;
}

Expected<SessionColumns, Refusal> RowGroupTable::read_session(std::uint32_t ordinal) const {
  // 1. THE WALL. An out-of-scope ordinal never becomes a row-group index.
  if (ordinal > kMaxSessionOrdinal) {
    return refuse<SessionColumns>(Refusal(RefusalCode::ORDINAL_OUTSIDE_SCOPE, kTableSite,
                                          "session ordinal is past the 749 wall",
                                          static_cast<std::int64_t>(ordinal)));
  }
  // 2. Index row `i` must declare ordinal `i`.
  const auto index_row = index_.at(ordinal);
  if (!index_row) {
    return refuse<SessionColumns>(index_row.error());
  }
  const SessionIndexRow& declared = *index_row.value();
  const std::size_t group = static_cast<std::size_t>(ordinal);

  // 3. The row group's own writer statistics for `day` must be a single value
  //    equal to the indexed day. Absent statistics are a refusal, never a
  //    fallback to "trust the values": the point is an INDEPENDENT witness.
  const qr::parquet::FileMeta& meta = file_->metadata();
  if (group >= meta.row_groups.size()) {
    return refuse<SessionColumns>(Refusal(RefusalCode::UNKNOWN_SESSION, kTableSite,
                                          "no physical row group for this ordinal",
                                          static_cast<std::int64_t>(ordinal)));
  }
  const qr::parquet::RowGroupMeta& row_group = meta.row_groups[group];
  if (day_leaf_ >= row_group.columns.size()) {
    return refuse<SessionColumns>(Refusal(RefusalCode::SCHEMA_MISMATCH, kTableSite,
                                          "row group has no chunk for the `day` leaf"));
  }
  const qr::parquet::ColumnChunkMeta& day_chunk = row_group.columns[day_leaf_];
  if (!day_chunk.has_statistics || !day_chunk.statistics.has_min_value ||
      !day_chunk.statistics.has_max_value) {
    return refuse<SessionColumns>(Refusal(RefusalCode::SCHEMA_MISMATCH, kTableSite,
                                          "row group carries no `day` statistics",
                                          static_cast<std::int64_t>(ordinal)));
  }
  if (day_chunk.statistics.min_value != day_chunk.statistics.max_value ||
      day_chunk.statistics.min_value != declared.day) {
    return refuse<SessionColumns>(
        Refusal(RefusalCode::WRONG_CIVIL_DAY, kTableSite,
                "row group `day` statistics are not a single value equal to the indexed day",
                static_cast<std::int64_t>(ordinal)));
  }

  // 4. Decode exactly the allowlisted leaves of exactly this row group.
  SessionColumns out;
  out.ordinal_ = ordinal;
  out.day_ = declared.day;
  out.names_ = names_;
  out.columns_.resize(names_.size());
  for (std::size_t i = 0; i < leaves_.size(); ++i) {
    const auto rows = file_->read_column(group, leaves_[i], *workspace_, out.columns_[i]);
    if (!rows) {
      return refuse<SessionColumns>(Refusal(rows.error().code(), kTableSite,
                                            "row group column failed to decode",
                                            rows.error().context()));
    }
    if (rows.value() != declared.rows) {
      return refuse<SessionColumns>(Refusal(RefusalCode::CONTENT_MISMATCH, kTableSite,
                                            "decoded row count differs from the index row count",
                                            rows.value()));
    }
  }
  out.num_rows_ = declared.rows;

  // 5. Every decoded `day` must equal the indexed day. This is the check that
  //    makes physical addressing safe: statistics are the writer's claim, these
  //    are the bytes.
  const auto day_column = out.column("day");
  if (!day_column) {
    return refuse<SessionColumns>(day_column.error());
  }
  for (std::int64_t row = 0; row < out.num_rows_; ++row) {
    if (out.is_null(day_column.value(), row) ||
        out.value(day_column.value(), row) != declared.day) {
      return refuse<SessionColumns>(Refusal(RefusalCode::WRONG_CIVIL_DAY, kTableSite,
                                            "a decoded row carries a different civil day", row));
    }
  }
  return out;
}

}  // namespace qr::candidates
