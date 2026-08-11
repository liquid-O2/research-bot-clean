// qr_census_dump — THE C++ HALF OF THE WP9 DIFFERENTIAL.
//
// SPEC (WP9 brief): "(a) registry-count oracle: C++ full pass reproduces
//   raw_rth_row_count AND complete_group_count for ALL 625 scoped sessions
//   (125..749); (b) column-sum differential vs Rust on all 625 ... emitting per
//   session x stream x projected column: (n_nonnull, n_null, digest) under
//   WP3's digest rule; (c) byte differential on the 33-session ordinal ladder
//   {125+20k} u {646,647}: canonical fixed-width LE row serialization from both
//   sides, sha256 compare; (d) WCD reconciliation ... cpp_bucket_total ==
//   rust_total + wcd_count with ordinals enumerated."
// SPEC (WP9 brief, budgets): "full-625 C++ pass (decode+groups) target <=180s
//   at 12 workers ... Parallelize across sessions with ordinal-ordered merge
//   (deterministic outputs)."
//
// DETERMINISM. Sessions are processed by a pool of workers in whatever order
// they finish, and each worker writes its session's lines into that session's
// OWN slot. The file is assembled by walking the slots in ordinal order, so the
// output is byte-identical whatever the thread interleaving was — the same law
// every other artifact run in this substrate obeys ("ordinal-only merge").
//
// usage:
//   qr_census_dump --root DIR --out PATH [--ordinals SPEC] [--streams LIST]
//                  [--bytes] [--workers N]
//     SPEC   := "A-B" | "A,B,C" | "ladder"   (default 125-749)
//     LIST   := comma separated stream names (default the three full-coverage
//               streams: stock_quotes,stock_trades,options_prints)
//     ladder := {125+20k, k=0..30} u {500} u {646,647}  — ordinal arithmetic,
//               never hash selection (FINAL_PLAN section 6, oracle 3; s500 is
//               the extra ordinal that section names alongside the ladder).
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <optional>
#include <string>
#include <thread>
#include <vector>

#include "qr_census/differential.hpp"
#include "qr_clock/session_clock.hpp"
#include "qr_sources/option_prints.hpp"
#include "qr_sources/option_quotes.hpp"
#include "qr_sources/stock_quotes.hpp"
#include "qr_sources/stock_trades.hpp"

namespace {

using qr::census::DiffCell;
using qr::census::DiffStream;
using qr::census::SessionDiff;
using qr::census::compared_columns;
using qr::census::diff_stream_name;

/// The three probe ordinals the merge gate reruns live: first, exact midpoint,
/// last. Ordinal arithmetic, never hash selection.
constexpr std::int64_t kProbeOrdinals[3] = {125, 437, 749};

// ---------------------------------------------------------------------------
// TSV emission
// ---------------------------------------------------------------------------

class Lines {
 public:
  Lines(std::int64_t ordinal, std::string day) : ordinal_(ordinal), day_(std::move(day)) {}

  void row(const char* kind, DiffStream stream, std::string_view name, std::string_view metric,
           const std::string& value) {
    char ordinal[24];
    std::snprintf(ordinal, sizeof(ordinal), "%lld", static_cast<long long>(ordinal_));
    text_ += kind;
    text_ += '\t';
    text_ += ordinal;
    text_ += '\t';
    text_ += day_;
    text_ += '\t';
    text_ += diff_stream_name(stream);
    text_ += '\t';
    text_.append(name);
    text_ += '\t';
    text_.append(metric);
    text_ += '\t';
    text_ += value;
    text_ += '\n';
  }

  void metric(const char* kind, DiffStream stream, std::string_view name, std::string_view metric,
              std::int64_t value) {
    row(kind, stream, name, metric, std::to_string(value));
  }

  void unsigned_metric(const char* kind, DiffStream stream, std::string_view name,
                       std::string_view metric, std::uint64_t value) {
    row(kind, stream, name, metric, std::to_string(value));
  }

  [[nodiscard]] const std::string& text() const noexcept { return text_; }
  [[nodiscard]] std::string&& take() noexcept { return std::move(text_); }

 private:
  std::int64_t ordinal_;
  std::string day_;
  std::string text_;
};

void emit_columns(Lines& lines, DiffStream stream, const SessionDiff& diff) {
  const std::span<const qr::census::DiffColumn> columns = compared_columns(stream);
  for (std::size_t index = 0; index < columns.size(); ++index) {
    const qr::sources::ValueDigest& digest = diff.column(index);
    lines.metric("column", stream, columns[index].name, "n_nonnull", digest.non_null());
    lines.metric("column", stream, columns[index].name, "n_null", digest.nulls());
    lines.unsigned_metric("column", stream, columns[index].name, "digest", digest.digest());
    lines.metric("column", stream, columns[index].name, "mask_null", diff.mask_null(index));
  }
}

void emit_bytes(Lines& lines, DiffStream stream, const SessionDiff& diff) {
  lines.row("bytes", stream, "-", "row_sha256", diff.row_sha256());
  lines.metric("bytes", stream, "-", "row_count", diff.rows());
}

// ---------------------------------------------------------------------------
// Per-stream passes
// ---------------------------------------------------------------------------

struct StreamOutcome {
  bool ok = false;
  std::string refusal;
};

StreamOutcome pass_stock_quotes(const qr::DayScope& scope, const std::string& tokens_root,
                                bool byte_mode, Lines& lines) {
  namespace src = qr::sources;
  const std::filesystem::path root = std::filesystem::path(tokens_root) / "stock_quotes" / "IWM";
  auto opened = src::StockQuoteReader::open(scope, root, scope.profile());
  if (!opened.has_value()) {
    return StreamOutcome{false, opened.error().message()};
  }
  src::StockQuoteReader reader = std::move(opened).value();
  SessionDiff diff(DiffStream::StockQuotes, scope.day(), byte_mode);
  std::array<DiffCell, 5> cells{};
  std::array<bool, 5> mask{};
  src::StockQuoteReader::Group group;
  while (true) {
    auto more = reader.next_group(group);
    if (!more.has_value()) {
      return StreamOutcome{false, more.error().message()};
    }
    if (!more.value()) {
      break;
    }
    for (const src::StockQuoteRow& row : group.rows) {
      // Compared order: ts_ms_b, bid_shares, bid_u6, ask_shares, ask_u6.
      // Every compared column is RowAdmission: the reader refuses a row that
      // mixes null and non-null NBBO fields, so a retained row has all five.
      cells[0] = DiffCell{row.ts_ms_b, 0.0, false};
      cells[1] = DiffCell{row.bid_shares, 0.0, false};
      cells[2] = DiffCell{row.bid_u6, 0.0, false};
      cells[3] = DiffCell{row.ask_shares, 0.0, false};
      cells[4] = DiffCell{row.ask_u6, 0.0, false};
      mask[0] = row.is_null(src::kQuoteSlotTimestamp);
      mask[1] = row.is_null(src::kQuoteSlotBidSize);
      mask[2] = row.is_null(src::kQuoteSlotBid);
      mask[3] = row.is_null(src::kQuoteSlotAskSize);
      mask[4] = row.is_null(src::kQuoteSlotAsk);
      diff.push(cells, mask);
    }
  }
  diff.finish();
  lines.metric("session", DiffStream::StockQuotes, "-", "rth_rows", reader.rth_rows());
  lines.metric("session", DiffStream::StockQuotes, "-", "group_count", reader.group_count());
  lines.metric("session", DiffStream::StockQuotes, "-", "cpp_skipped_rows", reader.sentinel_rows());
  lines.metric("session", DiffStream::StockQuotes, "-", "registry_raw_rth_row_count",
               scope.session().raw_rth_row_count);
  lines.metric("session", DiffStream::StockQuotes, "-", "registry_complete_group_count",
               scope.session().complete_group_count);
  lines.row("session", DiffStream::StockQuotes, "-", "source_profile",
            std::string(qr::source_profile_name(scope.profile())));
  emit_columns(lines, DiffStream::StockQuotes, diff);
  if (byte_mode) {
    emit_bytes(lines, DiffStream::StockQuotes, diff);
  }
  return StreamOutcome{true, {}};
}

StreamOutcome pass_stock_trades(const qr::DayScope& scope, const std::string& tokens_root,
                                bool byte_mode, Lines& lines) {
  namespace src = qr::sources;
  const std::filesystem::path root = std::filesystem::path(tokens_root) / "stock_trades" / "IWM";
  auto clock = qr::SessionClock::from_session(scope.session());
  if (!clock.has_value()) {
    return StreamOutcome{false, clock.error().message()};
  }
  auto opened = src::StockTradeReader::open(scope, root);
  if (!opened.has_value()) {
    return StreamOutcome{false, opened.error().message()};
  }
  src::StockTradeReader reader = std::move(opened).value();
  SessionDiff diff(DiffStream::StockTrades, scope.day(), byte_mode);
  std::array<DiffCell, 10> cells{};
  std::array<bool, 10> mask{};

  // THE ATTACHMENT CENSUS — the totalized classifier over every retained
  // print's `quote_timestamp`, which is where the wrong-civil-day fact lives.
  std::array<std::int64_t, 4> attach_buckets{};
  std::vector<std::pair<std::int64_t, std::int64_t>> delta_days;  // (delta, count), ordinal-free

  src::StockTradeReader::Group group;
  while (true) {
    auto more = reader.next_group(group);
    if (!more.has_value()) {
      return StreamOutcome{false, more.error().message()};
    }
    if (!more.value()) {
      break;
    }
    for (const src::StockTradeRow& row : group.rows) {
      const bool block_absent = !row.quote_present();
      // Compared order: ts_ms_b, sequence, condition, size, exchange, price_u6,
      // bid_shares, bid_u6, ask_shares, ask_u6.
      cells[0] = DiffCell{row.ts_ms_b, 0.0, false};
      cells[1] = DiffCell{row.sequence, 0.0, row.is_null(src::kTradeSlotSequence)};
      cells[2] = DiffCell{row.condition, 0.0, row.is_null(src::kTradeSlotCondition)};
      cells[3] = DiffCell{row.size, 0.0, row.is_null(src::kTradeSlotSize)};
      cells[4] = DiffCell{row.exchange, 0.0, row.is_null(src::kTradeSlotExchange)};
      cells[5] = DiffCell{row.price_u6, 0.0, false};
      // The frozen reader folds the whole attached block behind ONE flag and
      // writes zeros for all four when it is absent; the shared model does the
      // same, and the per-column truth travels in `mask_null`.
      cells[6] = DiffCell{block_absent ? 0 : row.bid_shares, 0.0, block_absent};
      cells[7] = DiffCell{block_absent ? 0 : row.bid_u6, 0.0, block_absent};
      cells[8] = DiffCell{block_absent ? 0 : row.ask_shares, 0.0, block_absent};
      cells[9] = DiffCell{block_absent ? 0 : row.ask_u6, 0.0, block_absent};
      mask[0] = row.is_null(src::kTradeSlotTradeTimestamp);
      mask[1] = row.is_null(src::kTradeSlotSequence);
      mask[2] = row.is_null(src::kTradeSlotCondition);
      mask[3] = row.is_null(src::kTradeSlotSize);
      mask[4] = row.is_null(src::kTradeSlotExchange);
      mask[5] = row.is_null(src::kTradeSlotPrice);
      mask[6] = row.is_null(src::kTradeSlotBidSize);
      mask[7] = row.is_null(src::kTradeSlotBid);
      mask[8] = row.is_null(src::kTradeSlotAskSize);
      mask[9] = row.is_null(src::kTradeSlotAsk);
      diff.push(cells, mask);

      const std::optional<std::int64_t> attachment =
          row.is_null(src::kTradeSlotQuoteTimestamp) ? std::nullopt
                                                     : std::optional<std::int64_t>(row.quote_ts_ms_b);
      const qr::AttachClass attach = clock.value().classify_attach_ms(attachment);
      ++attach_buckets[static_cast<std::size_t>(attach.kind())];
      if (attach.kind() == qr::AttachKind::WRONG_CIVIL_DAY) {
        const std::int64_t delta = attach.delta_days();
        bool found = false;
        for (auto& entry : delta_days) {
          if (entry.first == delta) {
            ++entry.second;
            found = true;
            break;
          }
        }
        if (!found) {
          delta_days.emplace_back(delta, 1);
        }
      }
    }
  }
  diff.finish();
  lines.metric("session", DiffStream::StockTrades, "-", "rth_rows", reader.rth_rows());
  lines.metric("session", DiffStream::StockTrades, "-", "group_count", reader.group_count());
  lines.metric("session", DiffStream::StockTrades, "-", "cpp_skipped_rows",
               reader.skipped_null_rows());
  emit_columns(lines, DiffStream::StockTrades, diff);
  if (byte_mode) {
    emit_bytes(lines, DiffStream::StockTrades, diff);
  }

  std::int64_t total = 0;
  for (std::size_t index = 0; index < attach_buckets.size(); ++index) {
    lines.metric("attach", DiffStream::StockTrades,
                 qr::attach_kind_name(static_cast<qr::AttachKind>(index)), "count",
                 attach_buckets[index]);
    total += attach_buckets[index];
  }
  std::sort(delta_days.begin(), delta_days.end());
  for (const auto& entry : delta_days) {
    lines.metric("attach", DiffStream::StockTrades,
                 std::string("delta_days:") + std::to_string(entry.first), "count", entry.second);
  }
  lines.metric("attach", DiffStream::StockTrades, "total", "count", total);
  return StreamOutcome{true, {}};
}

StreamOutcome pass_option_prints(const qr::DayScope& scope, const std::string& tokens_root,
                                 bool byte_mode, Lines& lines) {
  namespace src = qr::sources;
  const std::filesystem::path root = std::filesystem::path(tokens_root) / "options_prints" / "IWM";
  auto opened = src::OptionPrintReader::open(scope, root);
  if (!opened.has_value()) {
    return StreamOutcome{false, opened.error().message()};
  }
  src::OptionPrintReader reader = std::move(opened).value();
  SessionDiff diff(DiffStream::OptionPrints, scope.day(), byte_mode);
  std::array<DiffCell, 14> cells{};
  std::array<bool, 14> mask{};
  src::OptionPrintReader::Group group;
  while (true) {
    auto more = reader.next_group(group);
    if (!more.has_value()) {
      return StreamOutcome{false, more.error().message()};
    }
    if (!more.value()) {
      break;
    }
    for (const src::OptionPrintRow& row : group.rows) {
      // Compared order: expiration_day, strike_u6, right, ts_ms_b, size,
      // price_u6, delta, gamma, vanna, charm, implied_vol, underlying_price,
      // bid_u6, ask_u6.
      cells[0] = DiffCell{static_cast<std::int64_t>(row.expiration_day), 0.0,
                          row.is_null(src::kPrintSlotExpiration)};
      cells[1] = DiffCell{row.strike_u6, 0.0, row.is_null(src::kPrintSlotStrike)};
      // `right` is FoldedToValue: the frozen reader turns a null right into
      // Right::Other and cannot report the null, so both sides compare the
      // folded code and the C++ mask count travels as census.
      cells[2] = DiffCell{static_cast<std::int64_t>(row.right), 0.0, false};
      cells[3] = DiffCell{row.ts_ms_b, 0.0, false};
      cells[4] = DiffCell{row.size, 0.0, row.is_null(src::kPrintSlotSize)};
      cells[5] = DiffCell{row.price_u6, 0.0, row.is_null(src::kPrintSlotPrice)};
      cells[6] = DiffCell{0, row.delta, row.is_null(src::kPrintSlotDelta)};
      cells[7] = DiffCell{0, row.gamma, row.is_null(src::kPrintSlotGamma)};
      cells[8] = DiffCell{0, row.vanna, row.is_null(src::kPrintSlotVanna)};
      cells[9] = DiffCell{0, row.charm, row.is_null(src::kPrintSlotCharm)};
      cells[10] = DiffCell{0, row.implied_vol, row.is_null(src::kPrintSlotImpliedVol)};
      cells[11] = DiffCell{0, row.underlying_price, row.is_null(src::kPrintSlotUnderlyingPrice)};
      cells[12] = DiffCell{row.bid_u6, 0.0, row.is_null(src::kPrintSlotBid)};
      cells[13] = DiffCell{row.ask_u6, 0.0, row.is_null(src::kPrintSlotAsk)};
      mask[0] = row.is_null(src::kPrintSlotExpiration);
      mask[1] = row.is_null(src::kPrintSlotStrike);
      mask[2] = row.is_null(src::kPrintSlotRight);
      mask[3] = row.is_null(src::kPrintSlotTimestamp);
      mask[4] = row.is_null(src::kPrintSlotSize);
      mask[5] = row.is_null(src::kPrintSlotPrice);
      mask[6] = row.is_null(src::kPrintSlotDelta);
      mask[7] = row.is_null(src::kPrintSlotGamma);
      mask[8] = row.is_null(src::kPrintSlotVanna);
      mask[9] = row.is_null(src::kPrintSlotCharm);
      mask[10] = row.is_null(src::kPrintSlotImpliedVol);
      mask[11] = row.is_null(src::kPrintSlotUnderlyingPrice);
      mask[12] = row.is_null(src::kPrintSlotBid);
      mask[13] = row.is_null(src::kPrintSlotAsk);
      diff.push(cells, mask);
    }
  }
  diff.finish();
  lines.metric("session", DiffStream::OptionPrints, "-", "rth_rows", reader.rth_rows());
  lines.metric("session", DiffStream::OptionPrints, "-", "group_count", reader.group_count());
  lines.metric("session", DiffStream::OptionPrints, "-", "cpp_skipped_rows",
               reader.skipped_null_rows());
  emit_columns(lines, DiffStream::OptionPrints, diff);
  if (byte_mode) {
    emit_bytes(lines, DiffStream::OptionPrints, diff);
  }
  return StreamOutcome{true, {}};
}

StreamOutcome pass_option_quotes(const qr::DayScope& scope, const std::string& tokens_root,
                                 bool byte_mode, Lines& lines) {
  namespace src = qr::sources;
  const std::filesystem::path root = std::filesystem::path(tokens_root) / "option_quotes" / "IWM";
  auto opened = src::OptionQuoteReader::open(scope, root);
  if (!opened.has_value()) {
    return StreamOutcome{false, opened.error().message()};
  }
  src::OptionQuoteReader reader = std::move(opened).value();
  SessionDiff diff(DiffStream::OptionQuotes, scope.day(), byte_mode);
  std::array<DiffCell, 8> cells{};
  std::array<bool, 8> mask{};
  src::OptionQuoteReader::Group group;
  while (true) {
    auto more = reader.next_group(group);
    if (!more.has_value()) {
      return StreamOutcome{false, more.error().message()};
    }
    if (!more.value()) {
      break;
    }
    for (const src::OptionQuoteRow& row : group.rows) {
      // Compared order: expiration_day, strike_u6, right, ts_ms_b, bid_size,
      // bid_u6, ask_size, ask_u6.
      cells[0] = DiffCell{static_cast<std::int64_t>(row.expiration_day), 0.0,
                          row.is_null(src::kOptionQuoteSlotExpiration)};
      cells[1] = DiffCell{row.strike_u6, 0.0, row.is_null(src::kOptionQuoteSlotStrike)};
      cells[2] = DiffCell{static_cast<std::int64_t>(row.right), 0.0, false};
      cells[3] = DiffCell{row.ts_ms_b, 0.0, false};
      cells[4] = DiffCell{row.bid_size, 0.0, row.is_null(src::kOptionQuoteSlotBidSize)};
      cells[5] = DiffCell{row.bid_u6, 0.0, false};
      cells[6] = DiffCell{row.ask_size, 0.0, row.is_null(src::kOptionQuoteSlotAskSize)};
      cells[7] = DiffCell{row.ask_u6, 0.0, false};
      mask[0] = row.is_null(src::kOptionQuoteSlotExpiration);
      mask[1] = row.is_null(src::kOptionQuoteSlotStrike);
      mask[2] = row.is_null(src::kOptionQuoteSlotRight);
      mask[3] = row.is_null(src::kOptionQuoteSlotTimestamp);
      mask[4] = row.is_null(src::kOptionQuoteSlotBidSize);
      mask[5] = row.is_null(src::kOptionQuoteSlotBid);
      mask[6] = row.is_null(src::kOptionQuoteSlotAskSize);
      mask[7] = row.is_null(src::kOptionQuoteSlotAsk);
      diff.push(cells, mask);
    }
  }
  diff.finish();
  lines.metric("session", DiffStream::OptionQuotes, "-", "rth_rows", reader.rth_rows());
  lines.metric("session", DiffStream::OptionQuotes, "-", "group_count", reader.group_count());
  lines.metric("session", DiffStream::OptionQuotes, "-", "cpp_skipped_rows",
               reader.skipped_null_rows());
  emit_columns(lines, DiffStream::OptionQuotes, diff);
  if (byte_mode) {
    emit_bytes(lines, DiffStream::OptionQuotes, diff);
  }
  return StreamOutcome{true, {}};
}

// ---------------------------------------------------------------------------
// Driver
// ---------------------------------------------------------------------------

int usage() {
  std::fprintf(stderr,
               "usage: qr_census_dump --root DIR --out PATH [--ordinals A-B|A,B,C|ladder] "
               "[--streams LIST] [--bytes] [--workers N]\n");
  return 2;
}

[[nodiscard]] bool parse_ordinals(const std::string& spec, std::vector<std::int64_t>& out) {
  if (spec == "ladder") {
    for (std::int64_t k = 0; k <= 30; ++k) {
      out.push_back(125 + (20 * k));
    }
    out.push_back(500);
    out.push_back(646);
    out.push_back(647);
    std::sort(out.begin(), out.end());
    out.erase(std::unique(out.begin(), out.end()), out.end());
    return true;
  }
  if (spec == "probe") {
    for (const std::int64_t ordinal : kProbeOrdinals) {
      out.push_back(ordinal);
    }
    return true;
  }
  const std::size_t dash = spec.find('-');
  if (dash != std::string::npos && spec.find(',') == std::string::npos) {
    const std::int64_t first = std::strtoll(spec.substr(0, dash).c_str(), nullptr, 10);
    const std::int64_t last = std::strtoll(spec.substr(dash + 1).c_str(), nullptr, 10);
    if (first > last) {
      return false;
    }
    for (std::int64_t ordinal = first; ordinal <= last; ++ordinal) {
      out.push_back(ordinal);
    }
    return true;
  }
  std::size_t start = 0;
  while (start <= spec.size()) {
    const std::size_t stop = spec.find(',', start);
    const std::string piece =
        spec.substr(start, stop == std::string::npos ? std::string::npos : stop - start);
    if (piece.empty()) {
      return false;
    }
    out.push_back(std::strtoll(piece.c_str(), nullptr, 10));
    if (stop == std::string::npos) {
      break;
    }
    start = stop + 1;
  }
  std::sort(out.begin(), out.end());
  out.erase(std::unique(out.begin(), out.end()), out.end());
  return !out.empty();
}

[[nodiscard]] bool parse_streams(const std::string& spec, std::vector<DiffStream>& out) {
  std::size_t start = 0;
  while (start <= spec.size()) {
    const std::size_t stop = spec.find(',', start);
    const std::string piece =
        spec.substr(start, stop == std::string::npos ? std::string::npos : stop - start);
    DiffStream stream = DiffStream::StockQuotes;
    if (piece.empty() || !qr::census::parse_diff_stream(piece, stream)) {
      return false;
    }
    out.push_back(stream);
    if (stop == std::string::npos) {
      break;
    }
    start = stop + 1;
  }
  return !out.empty();
}

}  // namespace

int main(int argc, char** argv) {
  std::string root = "/workspace/data/tokens";
  std::string out_path;
  std::string ordinal_spec = "125-749";
  std::string stream_spec = "stock_quotes,stock_trades,options_prints";
  bool byte_mode = false;
  int workers = 12;
  for (int index = 1; index < argc; ++index) {
    const std::string flag = argv[index];
    const bool has_value = index + 1 < argc;
    if (flag == "--root" && has_value) {
      root = argv[++index];
    } else if (flag == "--out" && has_value) {
      out_path = argv[++index];
    } else if (flag == "--ordinals" && has_value) {
      ordinal_spec = argv[++index];
    } else if (flag == "--streams" && has_value) {
      stream_spec = argv[++index];
    } else if (flag == "--bytes") {
      byte_mode = true;
    } else if (flag == "--workers" && has_value) {
      workers = static_cast<int>(std::strtol(argv[++index], nullptr, 10));
    } else {
      return usage();
    }
  }
  if (out_path.empty() || workers <= 0) {
    return usage();
  }

  std::vector<std::int64_t> ordinals;
  if (!parse_ordinals(ordinal_spec, ordinals)) {
    std::fprintf(stderr, "cannot parse --ordinals '%s'\n", ordinal_spec.c_str());
    return 2;
  }
  std::vector<DiffStream> streams;
  if (!parse_streams(stream_spec, streams)) {
    std::fprintf(stderr, "cannot parse --streams '%s'\n", stream_spec.c_str());
    return 2;
  }

  auto registry = qr::Registry::load_embedded();
  if (!registry.has_value()) {
    std::fprintf(stderr, "REFUSED: %s\n", registry.error().message().c_str());
    return 1;
  }

  const std::size_t count = ordinals.size();
  std::vector<std::string> slots(count);
  std::vector<std::string> failures(count);
  std::atomic<std::size_t> next{0};
  std::atomic<std::size_t> done{0};
  const auto started = std::chrono::steady_clock::now();

  auto work = [&]() {
    while (true) {
      const std::size_t index = next.fetch_add(1);
      if (index >= count) {
        return;
      }
      const std::int64_t ordinal = ordinals[index];
      auto scope = qr::DayScope::admit(registry.value(), ordinal);
      if (!scope.has_value()) {
        failures[index] = "s" + std::to_string(ordinal) + ": " + scope.error().message();
        continue;
      }
      Lines lines(ordinal, scope.value().day());
      for (const DiffStream stream : streams) {
        StreamOutcome outcome;
        switch (stream) {
          case DiffStream::StockQuotes:
            outcome = pass_stock_quotes(scope.value(), root, byte_mode, lines);
            break;
          case DiffStream::StockTrades:
            outcome = pass_stock_trades(scope.value(), root, byte_mode, lines);
            break;
          case DiffStream::OptionPrints:
            outcome = pass_option_prints(scope.value(), root, byte_mode, lines);
            break;
          case DiffStream::OptionQuotes:
            outcome = pass_option_quotes(scope.value(), root, byte_mode, lines);
            break;
        }
        if (!outcome.ok) {
          failures[index] = "s" + std::to_string(ordinal) + " " + diff_stream_name(stream) + ": " +
                            outcome.refusal;
        }
      }
      slots[index] = lines.take();
      const std::size_t finished = done.fetch_add(1) + 1;
      if (finished % 25 == 0 || finished == count) {
        const double seconds =
            std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
        std::fprintf(stderr, "%zu/%zu sessions %.1fs\n", finished, count, seconds);
        std::fflush(stderr);
      }
    }
  };

  const std::size_t thread_count =
      std::min<std::size_t>(static_cast<std::size_t>(workers), count == 0 ? 1 : count);
  std::vector<std::thread> pool;
  pool.reserve(thread_count);
  for (std::size_t index = 0; index < thread_count; ++index) {
    pool.emplace_back(work);
  }
  for (std::thread& thread : pool) {
    thread.join();
  }
  const double wall =
      std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();

  // --- ORDINAL-ORDERED MERGE ------------------------------------------------
  std::FILE* out = std::fopen(out_path.c_str(), "wb");
  if (out == nullptr) {
    std::fprintf(stderr, "cannot write %s\n", out_path.c_str());
    return 1;
  }
  std::fprintf(out, "%s\n", std::string(qr::census::kDumpHeader).c_str());
  for (std::size_t index = 0; index < count; ++index) {
    if (!slots[index].empty()) {
      std::fwrite(slots[index].data(), 1, slots[index].size(), out);
    }
  }
  const bool write_failed = std::ferror(out) != 0;
  if (std::fclose(out) != 0 || write_failed) {
    std::fprintf(stderr, "the dump could not be written to the end\n");
    return 1;
  }

  int status = 0;
  for (const std::string& failure : failures) {
    if (!failure.empty()) {
      std::fprintf(stderr, "REFUSED: %s\n", failure.c_str());
      status = 1;
    }
  }
  std::printf("sessions %zu\nstreams %zu\nworkers %zu\nwall_seconds %.3f\n", count, streams.size(),
              thread_count, wall);
  return status;
}
