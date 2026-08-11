#include "qr_census/verdict.hpp"

#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace qr::census {
namespace {

/// A dump row plus its join key, so the join sorts once and never re-forms a
/// key inside the comparison loop.
struct KeyedRow {
  std::string key;
  const DumpRow* row;
};

[[nodiscard]] std::vector<KeyedRow> keyed(const std::vector<DumpRow>& rows) {
  std::vector<KeyedRow> out;
  out.reserve(rows.size());
  for (const DumpRow& row : rows) {
    out.push_back(KeyedRow{dump_key(row), &row});
  }
  std::sort(out.begin(), out.end(), [](const KeyedRow& left, const KeyedRow& right) {
    if (left.key != right.key) {
      return left.key < right.key;
    }
    return left.row->value < right.row->value;
  });
  return out;
}

/// THE CLOSED TABLE of metrics only the C++ side can produce. Everything here
/// is published as a CENSUS row; anything NOT here that appears on one side
/// only is a FAIL.
[[nodiscard]] bool is_cpp_only_metric(const DumpRow& row) noexcept {
  if (row.kind == "column") {
    return row.metric == "mask_null";
  }
  if (row.kind == "session") {
    return row.metric == "group_count" || row.metric == "registry_raw_rth_row_count" ||
           row.metric == "registry_complete_group_count" || row.metric == "cpp_skipped_rows" ||
           row.metric == "source_profile";
  }
  return false;
}

/// THE CLOSED TABLE of metrics only the diagnostic Rust build can produce.
[[nodiscard]] bool is_rust_only_metric(const DumpRow& row) noexcept {
  if (row.kind == "attach") {
    return row.name == "wcd_skipped";
  }
  if (row.kind == "session") {
    return row.metric == "rust_skipped_rows";
  }
  return false;
}

[[nodiscard]] std::string field_of(const DumpRow& row) {
  std::string field = "s";
  field += std::to_string(row.ordinal);
  field += '|';
  field += row.day;
  field += '|';
  field += row.stream;
  field += '|';
  field += row.name;
  field += '|';
  field += row.metric;
  return field;
}

[[nodiscard]] bool as_i64(const std::string& text, std::int64_t& out) noexcept {
  if (text.empty()) {
    return false;
  }
  char* end = nullptr;
  const long long parsed = std::strtoll(text.c_str(), &end, 10);
  if (end == nullptr || *end != '\0') {
    return false;
  }
  out = static_cast<std::int64_t>(parsed);
  return true;
}

class Builder {
 public:
  void add(std::string field, std::string oracle_value, std::string cpp_value, Verdict verdict) {
    VerdictRow row;
    row.field = std::move(field);
    row.oracle_value = std::move(oracle_value);
    row.cpp_value = std::move(cpp_value);
    row.verdict = verdict;
    rows_.push_back(std::move(row));
  }

  void add_waived(std::string field, std::string oracle_value, std::string cpp_value) {
    VerdictRow row;
    row.field = std::move(field);
    row.oracle_value = std::move(oracle_value);
    row.cpp_value = std::move(cpp_value);
    apply_waiver(row, kWcdWaiverId);
    rows_.push_back(std::move(row));
  }

  [[nodiscard]] std::vector<VerdictRow> take() { return std::move(rows_); }

 private:
  std::vector<VerdictRow> rows_;
};

/// The four numbers the registry oracle compares, per session.
struct RegistryOracleSlot {
  std::int64_t ordinal = 0;
  std::string day;
  std::string measured_rows;
  std::string measured_groups;
  std::string registry_rows;
  std::string registry_groups;
};

[[nodiscard]] RegistryOracleSlot& oracle_slot(std::vector<RegistryOracleSlot>& slots,
                                              std::int64_t ordinal, const std::string& day) {
  if (!slots.empty() && slots.back().ordinal == ordinal) {
    return slots.back();
  }
  for (RegistryOracleSlot& slot : slots) {
    if (slot.ordinal == ordinal) {
      return slot;
    }
  }
  RegistryOracleSlot fresh;
  fresh.ordinal = ordinal;
  fresh.day = day;
  slots.push_back(std::move(fresh));
  return slots.back();
}

/// One session's attachment reconciliation inputs, gathered from both dumps.
struct AttachPair {
  std::int64_t ordinal = 0;
  std::string day;
  std::int64_t cpp_total = 0;
  std::int64_t rust_total = 0;
  std::int64_t wcd_skipped = 0;
  bool have_cpp_total = false;
  bool have_rust_total = false;
  bool have_wcd = false;
};

}  // namespace

const char* verdict_name(Verdict verdict) noexcept {
  switch (verdict) {
    case Verdict::PASS:
      return "PASS";
    case Verdict::FAIL:
      return "FAIL";
    case Verdict::WAIVED:
      return "WAIVED";
    case Verdict::CENSUS:
      return "CENSUS";
    case Verdict::NOT_COMPARED:
      return "NOT_COMPARED";
  }
  return "?";
}

bool wcd_waiver_holds(std::int64_t cpp_bucket_total, std::int64_t rust_total,
                      std::int64_t wcd_count) noexcept {
  // Exact, to the unit, and only when there is something to waive. A zero
  // wcd_count with equal totals is a PASS: a waiver that also covers agreement
  // is a waiver that hides disagreement.
  if (wcd_count <= 0) {
    return false;
  }
  // Checked: the sum of two dump-supplied integers must not wrap into a match.
  std::int64_t sum = 0;
  if (__builtin_add_overflow(rust_total, wcd_count, &sum)) {
    return false;
  }
  return cpp_bucket_total == sum;
}

bool is_legal_waiver_id(std::string_view waiver_id) noexcept { return waiver_id == kWcdWaiverId; }

void apply_waiver(VerdictRow& row, std::string_view waiver_id) {
  if (!is_legal_waiver_id(waiver_id)) {
    detail::fail_fast("qr::census::apply_waiver: WCD-1 is the only legal waiver id");
  }
  row.verdict = Verdict::WAIVED;
  row.waiver_id = std::string(waiver_id);
}

// ---------------------------------------------------------------------------
// The archived verdict
// ---------------------------------------------------------------------------

Expected<std::string, Refusal> file_sha256(const std::string& path) {
  constexpr const char* kSite = "qr_census::file_sha256";
  std::FILE* file = std::fopen(path.c_str(), "rb");
  if (file == nullptr) {
    return Expected<std::string, Refusal>::refuse(
        Refusal(RefusalCode::IO, kSite, "cannot open the archived verdict", 0));
  }
  qr::candidates::Sha256 sha;
  std::vector<char> buffer(1U << 16U);
  while (true) {
    const std::size_t read = std::fread(buffer.data(), 1, buffer.size(), file);
    if (read == 0) {
      break;
    }
    sha.update(buffer.data(), read);
  }
  const bool failed = std::ferror(file) != 0;
  std::fclose(file);
  if (failed) {
    return Expected<std::string, Refusal>::refuse(
        Refusal(RefusalCode::IO, kSite, "the archived verdict could not be read to the end", 0));
  }
  return sha.finish_hex();
}

Expected<ArchiveSummary, Refusal> parse_verdict(std::string_view text) {
  constexpr const char* kSite = "qr_census::parse_verdict";
  ArchiveSummary summary;
  std::size_t line_start = 0;
  std::int64_t line_number = 0;
  bool header_seen = false;
  while (line_start <= text.size()) {
    const std::size_t line_end = text.find('\n', line_start);
    const std::string_view line = text.substr(
        line_start,
        line_end == std::string_view::npos ? std::string_view::npos : line_end - line_start);
    line_start = line_end == std::string_view::npos ? text.size() + 1 : line_end + 1;
    ++line_number;
    if (line.empty()) {
      if (line_end == std::string_view::npos) {
        break;
      }
      continue;
    }
    if (!header_seen) {
      if (line != kVerdictHeader) {
        return Expected<ArchiveSummary, Refusal>::refuse(Refusal(
            RefusalCode::SCHEMA_MISMATCH, kSite, "verdict header is not the pinned header",
            line_number));
      }
      header_seen = true;
      continue;
    }
    std::array<std::string_view, 5> fields{};
    std::size_t field = 0;
    std::size_t start = 0;
    while (field < fields.size()) {
      const std::size_t stop = line.find('\t', start);
      if (stop == std::string_view::npos) {
        fields[field] = line.substr(start);
        ++field;
        start = line.size() + 1;
        break;
      }
      fields[field] = line.substr(start, stop - start);
      ++field;
      start = stop + 1;
    }
    if (field != fields.size() || start <= line.size()) {
      return Expected<ArchiveSummary, Refusal>::refuse(
          Refusal(RefusalCode::SCHEMA_MISMATCH, kSite,
                  "verdict row does not carry exactly five tab-separated fields", line_number));
    }
    ++summary.rows;
    const std::string_view verdict = fields[3];
    const std::string_view waiver = fields[4];
    if (verdict == "PASS") {
      ++summary.pass;
    } else if (verdict == "FAIL") {
      ++summary.fail;
    } else if (verdict == "WAIVED") {
      ++summary.waived;
      if (!is_legal_waiver_id(waiver)) {
        return Expected<ArchiveSummary, Refusal>::refuse(
            Refusal(RefusalCode::CONTENT_MISMATCH, kSite,
                    "a WAIVED row carries a waiver id outside the closed set", line_number));
      }
    } else if (verdict == "CENSUS") {
      ++summary.census;
    } else if (verdict == "NOT_COMPARED") {
      ++summary.not_compared;
    } else {
      return Expected<ArchiveSummary, Refusal>::refuse(Refusal(
          RefusalCode::CONTENT_MISMATCH, kSite, "verdict row carries an unknown verdict name",
          line_number));
    }
    if (verdict != "WAIVED" && waiver != kNoWaiver) {
      return Expected<ArchiveSummary, Refusal>::refuse(
          Refusal(RefusalCode::CONTENT_MISMATCH, kSite,
                  "a non-WAIVED row carries a waiver id", line_number));
    }
  }
  if (!header_seen) {
    return Expected<ArchiveSummary, Refusal>::refuse(
        Refusal(RefusalCode::SCHEMA_MISMATCH, kSite, "verdict is empty: no header row", 0));
  }
  return summary;
}

Expected<ArchiveSummary, Refusal> verify_archive(const std::string& path,
                                                 std::string_view expected_sha256) {
  constexpr const char* kSite = "qr_census::verify_archive";
  Expected<std::string, Refusal> sha = file_sha256(path);
  if (!sha.has_value()) {
    return Expected<ArchiveSummary, Refusal>::refuse(sha.error());
  }
  if (sha.value() != expected_sha256) {
    return Expected<ArchiveSummary, Refusal>::refuse(
        Refusal(RefusalCode::SOURCE_AUTHENTICATION_FAILED, kSite,
                "the archived verdict's sha256 is not the one the run recorded", 0));
  }
  std::FILE* file = std::fopen(path.c_str(), "rb");
  if (file == nullptr) {
    return Expected<ArchiveSummary, Refusal>::refuse(
        Refusal(RefusalCode::IO, kSite, "cannot open the archived verdict", 0));
  }
  std::string text;
  std::vector<char> buffer(1U << 16U);
  while (true) {
    const std::size_t read = std::fread(buffer.data(), 1, buffer.size(), file);
    if (read == 0) {
      break;
    }
    text.append(buffer.data(), read);
  }
  const bool failed = std::ferror(file) != 0;
  std::fclose(file);
  if (failed) {
    return Expected<ArchiveSummary, Refusal>::refuse(
        Refusal(RefusalCode::IO, kSite, "the archived verdict could not be read to the end", 0));
  }
  Expected<ArchiveSummary, Refusal> summary = parse_verdict(text);
  if (!summary.has_value()) {
    return summary;
  }
  ArchiveSummary out = summary.value();
  out.sha256 = sha.value();
  return out;
}

std::string VerdictReport::to_tsv() const {
  std::string out(kVerdictHeader);
  out += '\n';
  for (const VerdictRow& row : rows) {
    out += row.field;
    out += '\t';
    out += row.oracle_value;
    out += '\t';
    out += row.cpp_value;
    out += '\t';
    out += verdict_name(row.verdict);
    out += '\t';
    out += row.waiver_id;
    out += '\n';
  }
  return out;
}

VerdictReport compare_dumps(const std::vector<DumpRow>& cpp_rows,
                            const std::vector<DumpRow>& rust_rows) {
  Builder builder;

  // --- 1. the coverage statement: every column outside the intersection -----
  for (std::size_t index = 0; index < kDiffStreamCount; ++index) {
    const auto stream = static_cast<DiffStream>(index);
    for (const UncomparedColumn& column : uncompared_columns(stream)) {
      std::string field = diff_stream_name(stream);
      field += '|';
      field.append(column.name);
      field += "|projection";
      builder.add(std::move(field), std::string(column_side_name(column.side)),
                  std::string(column.reason), Verdict::NOT_COMPARED);
    }
  }

  // --- 2. THE REGISTRY ORACLE, inside the C++ dump -------------------------
  // The registry is the oracle for these two numbers; no Rust is needed
  // (FINAL_PLAN section 6, oracle 2: "free, no Rust needed"). One indexed pass
  // gathers the four numbers per session so the join below stays linear.
  {
    std::vector<RegistryOracleSlot> slots;
    for (const DumpRow& row : cpp_rows) {
      if (row.kind != "session" || row.stream != "stock_quotes") {
        continue;
      }
      const bool wanted = row.metric == "rth_rows" || row.metric == "group_count" ||
                          row.metric == "registry_raw_rth_row_count" ||
                          row.metric == "registry_complete_group_count";
      if (!wanted) {
        continue;
      }
      RegistryOracleSlot& slot = oracle_slot(slots, row.ordinal, row.day);
      if (row.metric == "rth_rows") {
        slot.measured_rows = row.value;
      } else if (row.metric == "group_count") {
        slot.measured_groups = row.value;
      } else if (row.metric == "registry_raw_rth_row_count") {
        slot.registry_rows = row.value;
      } else {
        slot.registry_groups = row.value;
      }
    }
    std::sort(slots.begin(), slots.end(),
              [](const RegistryOracleSlot& lhs, const RegistryOracleSlot& rhs) {
                return lhs.ordinal < rhs.ordinal;
              });
    for (const RegistryOracleSlot& slot : slots) {
      const std::array<std::pair<std::string_view, std::pair<const std::string*, const std::string*>>, 2>
          pairs{std::make_pair(std::string_view("rth_rows"),
                               std::make_pair(&slot.registry_rows, &slot.measured_rows)),
                std::make_pair(std::string_view("group_count"),
                               std::make_pair(&slot.registry_groups, &slot.measured_groups))};
      for (const auto& entry : pairs) {
        std::string field = "s";
        field += std::to_string(slot.ordinal);
        field += '|';
        field += slot.day;
        field += "|stock_quotes|registry|";
        field.append(entry.first);
        const std::string& oracle = *entry.second.first;
        const std::string& measured = *entry.second.second;
        if (oracle.empty() || measured.empty()) {
          builder.add(std::move(field), oracle.empty() ? "ABSENT" : oracle,
                      measured.empty() ? "ABSENT" : measured, Verdict::FAIL);
          continue;
        }
        builder.add(std::move(field), oracle, measured,
                    oracle == measured ? Verdict::PASS : Verdict::FAIL);
      }
    }
  }

  // --- 3. the cross-side join ----------------------------------------------
  const std::vector<KeyedRow> left = keyed(cpp_rows);
  const std::vector<KeyedRow> right = keyed(rust_rows);
  std::vector<AttachPair> attach;

  auto attach_slot = [&attach](std::int64_t ordinal, const std::string& day) -> AttachPair& {
    for (AttachPair& pair : attach) {
      if (pair.ordinal == ordinal) {
        return pair;
      }
    }
    AttachPair fresh;
    fresh.ordinal = ordinal;
    fresh.day = day;
    attach.push_back(std::move(fresh));
    return attach.back();
  };

  std::size_t li = 0;
  std::size_t ri = 0;
  while (li < left.size() || ri < right.size()) {
    const bool take_left =
        ri >= right.size() || (li < left.size() && left[li].key <= right[ri].key);
    const bool take_right =
        li >= left.size() || (ri < right.size() && right[ri].key <= left[li].key);

    if (take_left && take_right && left[li].key == right[ri].key) {
      const DumpRow& lhs = *left[li].row;
      const DumpRow& rhs = *right[ri].row;
      // The attachment TOTAL is the one row a waiver can reach; it is compared
      // after the whole join, when wcd_skipped is known.
      if (lhs.kind == "attach" && lhs.name == "total") {
        AttachPair& pair = attach_slot(lhs.ordinal, lhs.day);
        pair.have_cpp_total = as_i64(lhs.value, pair.cpp_total);
        pair.have_rust_total = as_i64(rhs.value, pair.rust_total);
      } else {
        builder.add(field_of(lhs), rhs.value, lhs.value,
                    lhs.value == rhs.value ? Verdict::PASS : Verdict::FAIL);
      }
      ++li;
      ++ri;
      continue;
    }
    if (take_left) {
      const DumpRow& lhs = *left[li].row;
      if (is_cpp_only_metric(lhs)) {
        builder.add(field_of(lhs), "-", lhs.value, Verdict::CENSUS);
      } else if (lhs.kind == "attach" && lhs.name == "total") {
        AttachPair& pair = attach_slot(lhs.ordinal, lhs.day);
        pair.have_cpp_total = as_i64(lhs.value, pair.cpp_total);
      } else {
        builder.add(field_of(lhs), "ABSENT", lhs.value, Verdict::FAIL);
      }
      ++li;
      continue;
    }
    const DumpRow& rhs = *right[ri].row;
    if (rhs.kind == "attach" && rhs.name == "wcd_skipped") {
      AttachPair& pair = attach_slot(rhs.ordinal, rhs.day);
      pair.have_wcd = as_i64(rhs.value, pair.wcd_skipped);
      builder.add(field_of(rhs), rhs.value, "-", Verdict::CENSUS);
    } else if (is_rust_only_metric(rhs)) {
      builder.add(field_of(rhs), rhs.value, "-", Verdict::CENSUS);
    } else if (rhs.kind == "attach" && rhs.name == "total") {
      AttachPair& pair = attach_slot(rhs.ordinal, rhs.day);
      pair.have_rust_total = as_i64(rhs.value, pair.rust_total);
    } else {
      builder.add(field_of(rhs), rhs.value, "ABSENT", Verdict::FAIL);
    }
    ++ri;
  }

  // --- 4. THE WCD RECONCILIATION, one row per session ----------------------
  std::sort(attach.begin(), attach.end(),
            [](const AttachPair& lhs, const AttachPair& rhs) { return lhs.ordinal < rhs.ordinal; });
  for (const AttachPair& pair : attach) {
    std::string field = "s";
    field += std::to_string(pair.ordinal);
    field += '|';
    field += pair.day;
    field += "|stock_trades|attach|total";
    if (!pair.have_cpp_total || !pair.have_rust_total) {
      builder.add(std::move(field), pair.have_rust_total ? std::to_string(pair.rust_total) : "ABSENT",
                  pair.have_cpp_total ? std::to_string(pair.cpp_total) : "ABSENT", Verdict::FAIL);
      continue;
    }
    const std::int64_t wcd = pair.have_wcd ? pair.wcd_skipped : 0;
    if (pair.cpp_total == pair.rust_total && wcd == 0) {
      builder.add(std::move(field), std::to_string(pair.rust_total),
                  std::to_string(pair.cpp_total), Verdict::PASS);
      continue;
    }
    if (wcd_waiver_holds(pair.cpp_total, pair.rust_total, wcd)) {
      builder.add_waived(std::move(field), std::to_string(pair.rust_total),
                         std::to_string(pair.cpp_total));
      continue;
    }
    builder.add(std::move(field), std::to_string(pair.rust_total), std::to_string(pair.cpp_total),
                Verdict::FAIL);
  }

  VerdictReport report;
  report.rows = builder.take();
  for (const VerdictRow& row : report.rows) {
    switch (row.verdict) {
      case Verdict::PASS:
        ++report.pass;
        break;
      case Verdict::FAIL:
        ++report.fail;
        break;
      case Verdict::WAIVED:
        ++report.waived;
        break;
      case Verdict::CENSUS:
        ++report.census;
        break;
      case Verdict::NOT_COMPARED:
        ++report.not_compared;
        break;
    }
  }
  return report;
}

}  // namespace qr::census
