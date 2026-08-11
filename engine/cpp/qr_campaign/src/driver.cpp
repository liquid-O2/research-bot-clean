// qr_campaign/src/driver.cpp — the payload-free half of the campaign driver.
// Every law implemented here is stated in driver.hpp and fixtured in
// tests/test_campaign_driver.cpp.
#include "qr_campaign/driver.hpp"

#include <fcntl.h>
#include <unistd.h>

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <system_error>
#include <utility>

#include "qr_candidates/signal_root.hpp"

namespace qr::campaign {
namespace {

constexpr const char* kSite = "qr_campaign::driver";

[[nodiscard]] Refusal content(const char* detail, std::int64_t context = 0) {
  return Refusal(RefusalCode::CONTENT_MISMATCH, kSite, detail, context);
}
[[nodiscard]] Refusal io(const char* detail, std::int64_t context = 0) {
  return Refusal(RefusalCode::IO, kSite, detail, context);
}
[[nodiscard]] Refusal config(const char* detail, std::int64_t context = 0) {
  return Refusal(RefusalCode::CONFIG, kSite, detail, context);
}

/// `s0125`. Four digits exactly, as APPENDIX C4 spells it.
[[nodiscard]] std::string four_digit(std::int64_t ordinal) {
  char scratch[16];
  std::snprintf(scratch, sizeof(scratch), "s%04lld", static_cast<long long>(ordinal));
  return scratch;
}

}  // namespace

// ---------------------------------------------------------------------------
// 1. the spec gate
// ---------------------------------------------------------------------------

Status verify_frozen_spec(const std::filesystem::path& card, std::string_view expected_sha256) {
  std::error_code code;
  if (!std::filesystem::is_regular_file(card, code)) {
    return Status::refuse(io("the frozen task card is not a readable file"));
  }
  auto digest = qr::candidates::sha256_file_hex(card.string());
  if (!digest.has_value()) {
    return Status::refuse(digest.error());
  }
  if (digest.value() != expected_sha256) {
    // The offending prefix travels in `context` so the refusal names the bytes
    // it saw without carrying a dynamic string (Refusal holds static text only).
    return Status::refuse(content("the task card is not the frozen bytes this driver is "
                                  "bound to (spec gate, card §7 A8)",
                                  static_cast<std::int64_t>(
                                      std::strtoll(digest.value().substr(0, 8).c_str(), nullptr,
                                                   16))));
  }
  return ok_status();
}

// ---------------------------------------------------------------------------
// 1b. the card lineage
// ---------------------------------------------------------------------------

namespace {

/// `sha` is 64 lowercase hex characters and nothing else.
[[nodiscard]] bool is_sha256_hex(std::string_view sha) {
  if (sha.size() != 64) {
    return false;
  }
  for (const char character : sha) {
    const bool digit = character >= '0' && character <= '9';
    const bool lower = character >= 'a' && character <= 'f';
    if (!digit && !lower) {
      return false;
    }
  }
  return true;
}

/// `YYYY-MM-DD`, digits where digits belong.
[[nodiscard]] bool is_iso_date(std::string_view date) {
  if (date.size() != 10 || date[4] != '-' || date[7] != '-') {
    return false;
  }
  for (const std::size_t index : {0U, 1U, 2U, 3U, 5U, 6U, 8U, 9U}) {
    if (date[index] < '0' || date[index] > '9') {
      return false;
    }
  }
  return true;
}

/// The scope grammar. `ROOT` is legal only on the first row (it means "no
/// predecessor to diff against"); every other token names one card section.
/// An unknown token is NOT waved through: the gate cannot reason about a scope
/// it does not understand, so it refuses.
[[nodiscard]] bool is_known_scope_token(std::string_view token) {
  if (token == "ROOT" || token == "C4") {
    return true;
  }
  return token.size() == 2 && token[0] == 'S' && token[1] >= '1' && token[1] <= '9';
}

[[nodiscard]] std::vector<std::string> split(std::string_view text, char separator) {
  std::vector<std::string> parts;
  std::size_t start = 0;
  while (true) {
    const std::size_t hit = text.find(separator, start);
    if (hit == std::string_view::npos) {
      parts.emplace_back(text.substr(start));
      return parts;
    }
    parts.emplace_back(text.substr(start, hit - start));
    start = hit + 1;
  }
}

}  // namespace

bool CardLineageRow::touches_tape_read_scope() const {
  for (const std::string& token : scope) {
    for (const std::string_view read_scope : kTapeReadScope) {
      if (token == read_scope) {
        return true;
      }
    }
  }
  return false;
}

Expected<CardLineage, Refusal> CardLineage::load(const std::filesystem::path& path) {
  using Result = Expected<CardLineage, Refusal>;
  std::error_code code;
  if (!std::filesystem::is_regular_file(path, code)) {
    return Result::refuse(io("the card lineage is not a readable file"));
  }
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    return Result::refuse(io("the card lineage could not be opened"));
  }

  CardLineage lineage;
  std::string line;
  bool header_seen = false;
  std::int64_t line_number = 0;
  while (std::getline(input, line)) {
    ++line_number;
    if (line.empty() || line.front() == '#') {
      continue;
    }
    if (!header_seen) {
      if (line != "sha256\tdate\tamendment\tscope\tconsumers_invariant") {
        return Result::refuse(
            content("the card lineage does not carry its own header row", line_number));
      }
      header_seen = true;
      continue;
    }
    const std::vector<std::string> field = split(line, '\t');
    if (field.size() != 5) {
      return Result::refuse(
          content("a card lineage row is not five tab-separated fields", line_number));
    }
    CardLineageRow row;
    row.sha256 = field[0];
    row.date = field[1];
    row.amendment = field[2];
    row.consumers_invariant = field[4];
    if (!is_sha256_hex(row.sha256)) {
      return Result::refuse(
          content("a card lineage row does not carry a 64-hex sha256", line_number));
    }
    if (!is_iso_date(row.date)) {
      return Result::refuse(content("a card lineage row does not carry a YYYY-MM-DD date",
                                    line_number));
    }
    if (row.amendment.empty() || row.consumers_invariant.empty()) {
      return Result::refuse(content("a card lineage row leaves its amendment id or its "
                                    "consumer note empty",
                                    line_number));
    }
    for (std::string& token : split(field[3], ',')) {
      if (!is_known_scope_token(token)) {
        return Result::refuse(content("a card lineage row declares a scope token outside the "
                                      "grammar, which the gate cannot reason about",
                                      line_number));
      }
      const bool root = token == "ROOT";
      if (root && !lineage.rows_.empty()) {
        return Result::refuse(content("only the first card lineage row may be ROOT: every "
                                      "later row has a predecessor to diff against",
                                      line_number));
      }
      if (root && !row.scope.empty()) {
        return Result::refuse(
            content("a ROOT card lineage row may not also declare sections", line_number));
      }
      if (!root && !row.scope.empty() && row.scope.front() == "ROOT") {
        return Result::refuse(
            content("a ROOT card lineage row may not also declare sections", line_number));
      }
      row.scope.push_back(std::move(token));
    }
    if (row.scope.empty()) {
      return Result::refuse(content("a card lineage row declares no scope", line_number));
    }
    if (lineage.rows_.empty() && row.scope.front() != "ROOT") {
      return Result::refuse(content("the first card lineage row must be ROOT", line_number));
    }
    for (const CardLineageRow& seen : lineage.rows_) {
      if (seen.sha256 == row.sha256) {
        return Result::refuse(
            content("the card lineage names the same sha256 twice", line_number));
      }
    }
    lineage.rows_.push_back(std::move(row));
  }
  if (!header_seen) {
    return Result::refuse(content("the card lineage carries no header row"));
  }
  if (lineage.rows_.empty()) {
    return Result::refuse(content("the card lineage carries no rows"));
  }
  return lineage;
}

Status CardLineage::verify_head_card(const std::filesystem::path& card) const {
  return verify_frozen_spec(card, head().sha256);
}

Status CardLineage::verify_corpus_card_sha(std::string_view sha) const {
  std::size_t index = rows_.size();
  for (std::size_t position = 0; position < rows_.size(); ++position) {
    if (rows_[position].sha256 == sha) {
      index = position;
      break;
    }
  }
  if (index == rows_.size()) {
    return Status::refuse(content("this corpus names a task card that is not in the lineage at "
                                  "all, so nothing can be concluded about it"));
  }
  for (std::size_t later = index + 1; later < rows_.size(); ++later) {
    if (rows_[later].touches_tape_read_scope()) {
      // The amendment's own declaration retires this corpus. `context` carries
      // the row so the refusal names WHICH amendment did it.
      return Status::refuse(content("a card amendment after this corpus's card is declared "
                                    "inside the tape read scope, which retires the corpus",
                                    static_cast<std::int64_t>(later)));
    }
  }
  return ok_status();
}

Expected<std::vector<std::pair<std::string, std::int64_t>>, Refusal> corpus_card_shas(
    const std::filesystem::path& run_root) {
  using Result = Expected<std::vector<std::pair<std::string, std::int64_t>>, Refusal>;
  const std::filesystem::path tapes = run_root / "tapes";
  std::error_code code;
  if (!std::filesystem::is_directory(tapes, code)) {
    return Result::refuse(io("this run root carries no tapes directory"));
  }
  std::vector<std::filesystem::path> manifests;
  for (const auto& entry : std::filesystem::recursive_directory_iterator(tapes, code)) {
    if (entry.is_regular_file(code) && entry.path().filename() == "manifest.tsv") {
      manifests.push_back(entry.path());
    }
  }
  if (manifests.empty()) {
    return Result::refuse(io("this run root carries no shard manifests"));
  }
  std::sort(manifests.begin(), manifests.end());

  std::vector<std::pair<std::string, std::int64_t>> tally;
  for (const std::filesystem::path& manifest : manifests) {
    std::ifstream input(manifest, std::ios::binary);
    if (!input) {
      return Result::refuse(io("a shard manifest could not be opened"));
    }
    std::string line;
    std::string sha;
    while (std::getline(input, line)) {
      const std::vector<std::string> field = split(line, '\t');
      if (field.size() >= 3 && field[0] == "census" && field[1] == "task_card_v4") {
        sha = field[2];
        break;
      }
    }
    if (!is_sha256_hex(sha)) {
      return Result::refuse(content("a shard manifest carries no task_card_v4 census sha, so "
                                    "the card it was built against is unknown"));
    }
    bool counted = false;
    for (auto& seen : tally) {
      if (seen.first == sha) {
        ++seen.second;
        counted = true;
        break;
      }
    }
    if (!counted) {
      tally.emplace_back(sha, 1);
    }
  }
  std::sort(tally.begin(), tally.end());
  return tally;
}

// ---------------------------------------------------------------------------
// 2. the ordinal wall
// ---------------------------------------------------------------------------

Status refuse_unless_in_scope(std::int64_t ordinal) {
  if (ordinal < kFirstScopedOrdinal || ordinal > kLastScopedOrdinal) {
    return Status::refuse(Refusal(RefusalCode::ORDINAL_OUTSIDE_SCOPE, kSite,
                                  "card §1: only sessions 125..749 are admissible, and the "
                                  "wall is applied before any path is formed",
                                  ordinal));
  }
  return ok_status();
}

Expected<std::vector<std::int64_t>, Refusal> parse_session_list(std::string_view spec) {
  using Result = Expected<std::vector<std::int64_t>, Refusal>;
  std::vector<std::int64_t> out;
  if (spec.empty()) {
    return Result::refuse(config("--sessions was given no value"));
  }
  if (spec == "all") {
    out.reserve(static_cast<std::size_t>(kScopedSessionCount));
    for (std::int64_t ordinal = kFirstScopedOrdinal; ordinal <= kLastScopedOrdinal; ++ordinal) {
      out.push_back(ordinal);
    }
    return Result(std::move(out));
  }
  std::size_t cursor = 0;
  while (cursor <= spec.size()) {
    const std::size_t comma = spec.find(',', cursor);
    const std::string_view token =
        spec.substr(cursor, comma == std::string_view::npos ? std::string_view::npos
                                                            : comma - cursor);
    if (token.empty()) {
      return Result::refuse(config("--sessions carries an empty element"));
    }
    const std::size_t dash = token.find('-');
    const auto to_ordinal = [](std::string_view text) -> Expected<std::int64_t, Refusal> {
      if (text.empty()) {
        return Expected<std::int64_t, Refusal>::refuse(config("--sessions carries an empty bound"));
      }
      std::int64_t value = 0;
      for (const char character : text) {
        if (character < '0' || character > '9') {
          return Expected<std::int64_t, Refusal>::refuse(
              config("--sessions accepts decimal ordinals, ranges and `all` only"));
        }
        value = value * 10 + (character - '0');
        if (value > 1'000'000) {
          return Expected<std::int64_t, Refusal>::refuse(config("--sessions ordinal overflows"));
        }
      }
      return Expected<std::int64_t, Refusal>(value);
    };
    std::int64_t low = 0;
    std::int64_t high = 0;
    if (dash == std::string_view::npos) {
      auto value = to_ordinal(token);
      if (!value.has_value()) {
        return Result::refuse(value.error());
      }
      low = value.value();
      high = low;
    } else {
      auto first = to_ordinal(token.substr(0, dash));
      if (!first.has_value()) {
        return Result::refuse(first.error());
      }
      auto second = to_ordinal(token.substr(dash + 1));
      if (!second.has_value()) {
        return Result::refuse(second.error());
      }
      low = first.value();
      high = second.value();
      if (high < low) {
        return Result::refuse(config("--sessions carries a descending range"));
      }
    }
    for (std::int64_t ordinal = low; ordinal <= high; ++ordinal) {
      const Status wall = refuse_unless_in_scope(ordinal);
      if (!wall.has_value()) {
        return Result::refuse(wall.error());
      }
      out.push_back(ordinal);
    }
    if (comma == std::string_view::npos) {
      break;
    }
    cursor = comma + 1;
  }
  std::sort(out.begin(), out.end());
  out.erase(std::unique(out.begin(), out.end()), out.end());
  if (out.empty()) {
    return Result::refuse(config("--sessions resolved to no session at all"));
  }
  return Result(std::move(out));
}

// ---------------------------------------------------------------------------
// The run layout
// ---------------------------------------------------------------------------

std::filesystem::path RunLayout::root() const {
  return base / (run_index == 2 ? "run2" : "run1");
}
std::filesystem::path RunLayout::tapes() const { return root() / "tapes"; }
std::filesystem::path RunLayout::rosters() const { return root() / "rosters"; }
std::filesystem::path RunLayout::roster_dir(std::int64_t ordinal) const {
  return rosters() / four_digit(ordinal);
}
std::filesystem::path RunLayout::roster_tsv(std::int64_t ordinal) const {
  return roster_dir(ordinal) / "roster.tsv";
}
std::filesystem::path RunLayout::receipts() const { return root() / "receipts"; }
std::filesystem::path RunLayout::session_receipt(std::int64_t ordinal) const {
  return receipts() / "sessions" / (four_digit(ordinal) + ".tsv");
}
std::filesystem::path RunLayout::session_timing(std::int64_t ordinal) const {
  return receipts() / "timings" / (four_digit(ordinal) + ".tsv");
}
std::filesystem::path RunLayout::builder_census(std::int64_t ordinal) const {
  return receipts() / "builder_fd_census" / (four_digit(ordinal) + ".tsv");
}
std::filesystem::path RunLayout::truth_receipt(std::int64_t ordinal) const {
  return receipts() / "builder_fd_census" / (four_digit(ordinal) + ".truth.tsv");
}
std::filesystem::path RunLayout::builder_receipt(std::int64_t ordinal) const {
  return receipts() / "builder" / (four_digit(ordinal) + ".tsv");
}

Expected<RunLayout, Refusal> run_layout(const std::filesystem::path& base, int run_index) {
  if (run_index != 1 && run_index != 2) {
    return Expected<RunLayout, Refusal>::refuse(
        config("a campaign has exactly two runs: R1 and the --run2 identity re-run", run_index));
  }
  if (base.empty() || !base.is_absolute()) {
    return Expected<RunLayout, Refusal>::refuse(config("the campaign base root must be absolute"));
  }
  RunLayout layout;
  layout.base = base.lexically_normal();
  layout.run_index = run_index;
  return Expected<RunLayout, Refusal>(layout);
}

Expected<std::string, Refusal> session_dir_name(std::int64_t ordinal) {
  const Status wall = refuse_unless_in_scope(ordinal);
  if (!wall.has_value()) {
    return Expected<std::string, Refusal>::refuse(wall.error());
  }
  return Expected<std::string, Refusal>(four_digit(ordinal));
}

// ---------------------------------------------------------------------------
// 3. the task plan
// ---------------------------------------------------------------------------

bool side_is_published(const RunLayout& layout, std::int64_t ordinal, qr::emit::Side side) {
  const auto dir = qr::emit::c4_shard_dir(layout.tapes(), ordinal, side);
  if (!dir.has_value()) {
    return false;
  }
  std::error_code code;
  return std::filesystem::is_regular_file(dir.value() / qr::emit::kManifestName, code);
}

Expected<std::vector<SessionTask>, Refusal> plan_tasks(const RunLayout& layout,
                                                       std::span<const std::int64_t> requested,
                                                       bool resume) {
  using Result = Expected<std::vector<SessionTask>, Refusal>;
  std::vector<std::int64_t> ordinals(requested.begin(), requested.end());
  std::sort(ordinals.begin(), ordinals.end());
  ordinals.erase(std::unique(ordinals.begin(), ordinals.end()), ordinals.end());

  std::vector<SessionTask> plan;
  plan.reserve(ordinals.size());
  for (const std::int64_t ordinal : ordinals) {
    const Status wall = refuse_unless_in_scope(ordinal);
    if (!wall.has_value()) {
      return Result::refuse(wall.error());
    }
    SessionTask task;
    task.ordinal = ordinal;
    for (const qr::emit::Side side : {qr::emit::Side::LONG, qr::emit::Side::SHORT}) {
      const bool published = side_is_published(layout, ordinal, side);
      if (!published) {
        continue;
      }
      if (!resume) {
        // The no-replace law, surfaced HERE rather than after a worker has
        // spent a session rebuilding bytes it may not publish.
        return Result::refuse(content(
            "a shard is already published for this session/side; rerun with --resume to skip "
            "it, or publish into a fresh root — shards are never replaced",
            ordinal));
      }
      task.side[static_cast<std::size_t>(side)] = SideWork::ALREADY_PUBLISHED;
    }
    plan.push_back(task);
  }
  return Result(std::move(plan));
}

// ---------------------------------------------------------------------------
// Receipts
// ---------------------------------------------------------------------------

void Receipt::add(std::string_view section, std::string_view metric, std::int64_t value) {
  char scratch[32];
  std::snprintf(scratch, sizeof(scratch), "%lld", static_cast<long long>(value));
  add_text(section, metric, scratch);
}

void Receipt::add_text(std::string_view section, std::string_view metric,
                       std::string_view value) {
  std::string row(section);
  row += '\t';
  row += metric;
  row += '\t';
  row += value;
  rows_.push_back(std::move(row));
}

std::string Receipt::render() const {
  std::string text = "section\tmetric\tvalue\n";
  for (const std::string& row : rows_) {
    text += row;
    text += '\n';
  }
  return text;
}

Status Receipt::write(const std::filesystem::path& path) const {
  std::error_code code;
  std::filesystem::create_directories(path.parent_path(), code);
  if (code) {
    return Status::refuse(io("cannot create the receipt directory", code.value()));
  }
  // THE STAGED NAME CARRIES NO PID. Exactly one process ever writes a given
  // receipt path (one worker per session, one dispatcher per run), so a pid adds
  // no safety — and it WOULD break determinism, because the tagged constructor
  // phase's fd census records the path of its own staged receipt: a pid in that
  // name puts a per-run random number inside a published census.
  const std::filesystem::path staged =
      path.parent_path() / ("." + path.filename().string() + ".staging");
  const std::string text = render();
  const int fd = ::open(staged.c_str(), O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
  if (fd < 0) {
    return Status::refuse(io("cannot create the staged receipt"));
  }
  std::size_t written = 0;
  while (written < text.size()) {
    const ssize_t chunk = ::write(fd, text.data() + written, text.size() - written);
    if (chunk <= 0) {
      ::close(fd);
      return Status::refuse(io("short write to the staged receipt"));
    }
    written += static_cast<std::size_t>(chunk);
  }
  if (::fsync(fd) != 0) {
    ::close(fd);
    return Status::refuse(io("cannot fsync the staged receipt"));
  }
  ::close(fd);
  std::filesystem::rename(staged, path, code);
  if (code) {
    return Status::refuse(io("cannot rename the staged receipt into place", code.value()));
  }
  return ok_status();
}

Expected<std::vector<ReceiptRow>, Refusal> parse_receipt(const std::filesystem::path& path) {
  using Result = Expected<std::vector<ReceiptRow>, Refusal>;
  std::ifstream input(path);
  if (!input) {
    return Result::refuse(io("cannot open a receipt"));
  }
  std::string line;
  if (!std::getline(input, line) || line != "section\tmetric\tvalue") {
    return Result::refuse(content("a receipt does not carry the driver's own header"));
  }
  std::vector<ReceiptRow> rows;
  while (std::getline(input, line)) {
    if (line.empty()) {
      continue;
    }
    const std::size_t first = line.find('\t');
    if (first == std::string::npos) {
      return Result::refuse(content("a receipt row is not three tab-separated fields"));
    }
    const std::size_t second = line.find('\t', first + 1);
    if (second == std::string::npos) {
      return Result::refuse(content("a receipt row is not three tab-separated fields"));
    }
    ReceiptRow row;
    row.section = line.substr(0, first);
    row.metric = line.substr(first + 1, second - first - 1);
    row.value = line.substr(second + 1);
    rows.push_back(std::move(row));
  }
  return Result(std::move(rows));
}

Expected<std::string, Refusal> receipt_value(std::span<const ReceiptRow> rows,
                                             std::string_view section, std::string_view metric) {
  for (const ReceiptRow& row : rows) {
    if (row.section == section && row.metric == metric) {
      return Expected<std::string, Refusal>(row.value);
    }
  }
  return Expected<std::string, Refusal>::refuse(
      content("a receipt is missing a row the campaign ledger requires"));
}

// ---------------------------------------------------------------------------
// 4. the ordinal-ordered merge
// ---------------------------------------------------------------------------

std::string sha256_hex(std::string_view text) {
  qr::candidates::Sha256 hasher;
  hasher.update(text);
  return hasher.finish_hex();
}

Expected<std::string, Refusal> render_campaign_receipt(const RunLayout& layout,
                                                       std::span<const std::int64_t> ordinals) {
  using Result = Expected<std::string, Refusal>;
  std::vector<std::int64_t> sorted(ordinals.begin(), ordinals.end());
  std::sort(sorted.begin(), sorted.end());
  sorted.erase(std::unique(sorted.begin(), sorted.end()), sorted.end());

  if (layout.card_sha256.empty()) {
    // Never name a card nobody verified: an unbound layout means the spec gate
    // did not run, and a receipt is a claim about which frozen bytes produced
    // these tapes.
    return Result::refuse(config("this run layout was never bound to a verified card sha, so "
                                 "the campaign receipt would name a card nobody checked"));
  }
  Receipt out;
  out.add_text("campaign", "schema", "qr_campaign_receipt_v1");
  out.add_text("campaign", "card_sha256", layout.card_sha256);
  // NO RUN INDEX. This receipt describes the CAMPAIGN, and the two runs of one
  // campaign must be byte-identical down to it; which run slot produced it is a
  // property of its path and is recorded in campaign_timing.tsv.
  out.add("campaign", "sessions", static_cast<std::int64_t>(sorted.size()));

  // The root-hash preimage: one line per published shard, in ordinal order,
  // side-major LONG then SHORT. Nothing about the worker count or the
  // completion order can reach it.
  std::string preimage;
  std::int64_t leaves = 0;
  std::int64_t bytes = 0;
  std::int64_t action_rows = 0;
  std::int64_t label_ok = 0;
  for (const std::int64_t ordinal : sorted) {
    auto rows = parse_receipt(layout.session_receipt(ordinal));
    if (!rows.has_value()) {
      return Result::refuse(rows.error());
    }
    const auto number = [&rows](std::string_view section,
                                std::string_view metric) -> Expected<std::int64_t, Refusal> {
      auto text = receipt_value(rows.value(), section, metric);
      if (!text.has_value()) {
        return Expected<std::int64_t, Refusal>::refuse(text.error());
      }
      return Expected<std::int64_t, Refusal>(std::strtoll(text.value().c_str(), nullptr, 10));
    };
    for (const char side : {'L', 'S'}) {
      const std::string section = std::string("shard.") + side;
      auto manifest = receipt_value(rows.value(), section, "manifest_sha256");
      if (!manifest.has_value()) {
        return Result::refuse(manifest.error());
      }
      preimage += four_digit(ordinal);
      preimage += '\t';
      preimage += side;
      preimage += '\t';
      preimage += manifest.value();
      preimage += '\n';
      auto leaf_count = number(section, "leaves");
      if (!leaf_count.has_value()) {
        return Result::refuse(leaf_count.error());
      }
      leaves += leaf_count.value();
      auto leaf_bytes = number(section, "bytes");
      if (!leaf_bytes.has_value()) {
        return Result::refuse(leaf_bytes.error());
      }
      bytes += leaf_bytes.value();
      out.add_text(std::string("manifest.") + four_digit(ordinal), std::string(1, side),
                   manifest.value());
    }
    auto actions = number("actions", "rows");
    if (!actions.has_value()) {
      return Result::refuse(actions.error());
    }
    action_rows += actions.value();
    auto ok_rows = number("label_state", "OK");
    if (!ok_rows.has_value()) {
      return Result::refuse(ok_rows.error());
    }
    label_ok += ok_rows.value();
  }
  out.add("campaign", "shards", static_cast<std::int64_t>(sorted.size()) * 2);
  out.add("campaign", "leaves", leaves);
  out.add("campaign", "leaf_bytes", bytes);
  out.add("campaign", "action_rows", action_rows);
  out.add("campaign", "label_state_ok", label_ok);
  out.add_text("campaign", "manifest_root_sha256", sha256_hex(preimage));
  return Result(out.render());
}

// ---------------------------------------------------------------------------
// The shard emitter
// ---------------------------------------------------------------------------

Expected<std::int64_t, Refusal> clear_stale_stages(const RunLayout& layout, std::int64_t ordinal,
                                                   qr::emit::Side side) {
  using Result = Expected<std::int64_t, Refusal>;
  const auto shard = qr::emit::c4_shard_dir(layout.tapes(), ordinal, side);
  if (!shard.has_value()) {
    return Result::refuse(shard.error());
  }
  const std::filesystem::path session_dir = shard.value().parent_path();
  const std::string prefix = std::string(".") + qr::emit::side_letter(side) + ".stage-";
  std::error_code code;
  if (!std::filesystem::is_directory(session_dir, code)) {
    return Result(0);
  }
  // Sorted, because directory order is not an output the repo permits.
  std::vector<std::filesystem::path> stale;
  for (const std::filesystem::directory_entry& entry :
       std::filesystem::directory_iterator(session_dir, code)) {
    if (code) {
      return Result::refuse(io("cannot scan the session directory for stale stages"));
    }
    const std::string name = entry.path().filename().string();
    if (name.rfind(prefix, 0) == 0) {
      stale.push_back(entry.path());
    }
  }
  std::sort(stale.begin(), stale.end());
  std::int64_t removed = 0;
  for (const std::filesystem::path& path : stale) {
    std::filesystem::remove_all(path, code);
    if (code) {
      return Result::refuse(io("cannot remove a stale stage directory", code.value()));
    }
    ++removed;
  }
  return Result(removed);
}

Expected<std::unique_ptr<ShardEmitter>, Refusal> ShardEmitter::open(
    const RunLayout& layout, std::int64_t ordinal, qr::emit::Side side, std::string build_id,
    std::vector<qr::emit::SourceRow> sources, std::vector<qr::emit::CensusRow> census) {
  using Result = Expected<std::unique_ptr<ShardEmitter>, Refusal>;
  const Status wall = refuse_unless_in_scope(ordinal);
  if (!wall.has_value()) {
    return Result::refuse(wall.error());
  }
  const auto cleared = clear_stale_stages(layout, ordinal, side);
  if (!cleared.has_value()) {
    return Result::refuse(cleared.error());
  }
  const auto dir = qr::emit::c4_shard_dir(layout.tapes(), ordinal, side);
  if (!dir.has_value()) {
    return Result::refuse(dir.error());
  }
  qr::emit::ShardSpec spec;
  spec.publish_dir = dir.value();
  spec.session_ordinal = ordinal;
  spec.side = side;
  spec.build_id = std::move(build_id);
  spec.sources = std::move(sources);
  spec.census = std::move(census);
  auto begun = qr::emit::ShardWriter::begin(std::move(spec));
  if (!begun.has_value()) {
    return Result::refuse(begun.error());
  }
  return Result(std::unique_ptr<ShardEmitter>(new ShardEmitter(std::move(begun).value())));
}

Expected<qr::emit::ShardReceipt, Refusal> ShardEmitter::publish() { return writer_->publish(); }

const std::filesystem::path& ShardEmitter::stage_dir() const noexcept {
  return writer_->stage_dir();
}

}  // namespace qr::campaign
