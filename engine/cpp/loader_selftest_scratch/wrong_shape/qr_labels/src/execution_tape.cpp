#include "qr_labels/execution_tape.hpp"

#include <algorithm>
#include <array>
#include <limits>
#include <utility>

#include "qr_nbbo/census.hpp"
#include "qr_nbbo/group_machine.hpp"

namespace qr::labels {
namespace {

constexpr const char* kPushSite = "qr_labels::ExecutionTapeBuilder::push_group";
constexpr const char* kSealSite = "qr_labels::ExecutionTapeBuilder::seal";
constexpr const char* kVerifySite = "qr_labels::verify_against";
constexpr const char* kRunSite = "qr_labels::build_execution_tape";

void append_i64(std::vector<std::uint8_t>& out, std::int64_t value) {
  const auto bits = static_cast<std::uint64_t>(value);
  for (std::size_t byte = 0; byte < sizeof(std::uint64_t); ++byte) {
    out.push_back(static_cast<std::uint8_t>((bits >> (8U * byte)) & 0xFFU));
  }
}

void append_metric(std::string& out, std::string_view label, std::string_view metric,
                   std::int64_t value) {
  out.append(label);
  out.push_back('\t');
  out.append(metric);
  out.push_back('\t');
  out.append(std::to_string(value));
  out.push_back('\n');
}

}  // namespace

// ---------------------------------------------------------------------------
// ExecutionTapeCensus
// ---------------------------------------------------------------------------

std::string ExecutionTapeCensus::to_tsv(std::string_view label) const {
  std::string out = "label\tmetric\tvalue\n";
  append_metric(out, label, "groups_seen", groups_seen);
  append_metric(out, label, "groups_eligible", groups_eligible);
  append_metric(out, label, "groups_without_eligible_member", groups_without_eligible_member);
  append_metric(out, label, "eligible_members", eligible_members);
  append_metric(out, label, "ineligible_members", ineligible_members);
  return out;
}

// ---------------------------------------------------------------------------
// ExecutionTape
// ---------------------------------------------------------------------------

std::int64_t ExecutionTape::first_strictly_after(std::int64_t ts) const noexcept {
  const auto found = std::upper_bound(ts_ns.begin(), ts_ns.end(), ts);
  if (found == ts_ns.end()) {
    return kNoIndex;
  }
  return static_cast<std::int64_t>(found - ts_ns.begin());
}

std::int64_t ExecutionTape::first_at_or_after(std::int64_t ts) const noexcept {
  const auto found = std::lower_bound(ts_ns.begin(), ts_ns.end(), ts);
  if (found == ts_ns.end()) {
    return kNoIndex;
  }
  return static_cast<std::int64_t>(found - ts_ns.begin());
}

std::int64_t ExecutionTape::entry_price(std::int64_t index, Side side) const {
  if (index < 0 || index >= size()) {
    detail::fail_fast("qr::labels::ExecutionTape::entry_price out of domain");
  }
  const auto slot = static_cast<std::size_t>(index);
  return side == Side::LONG ? ask_max_u6[slot] : bid_min_u6[slot];
}

std::int64_t ExecutionTape::adverse_mark(std::int64_t index, Side side) const {
  if (index < 0 || index >= size()) {
    detail::fail_fast("qr::labels::ExecutionTape::adverse_mark out of domain");
  }
  const auto slot = static_cast<std::size_t>(index);
  return side == Side::LONG ? bid_min_u6[slot] : ask_max_u6[slot];
}

std::int64_t ExecutionTape::favorable_mark(std::int64_t index, Side side) const {
  if (index < 0 || index >= size()) {
    detail::fail_fast("qr::labels::ExecutionTape::favorable_mark out of domain");
  }
  const auto slot = static_cast<std::size_t>(index);
  return side == Side::LONG ? bid_max_u6[slot] : ask_min_u6[slot];
}

void ExecutionTape::append_serialized(std::int64_t index, std::vector<std::uint8_t>& out) const {
  if (index < 0 || index >= size()) {
    detail::fail_fast("qr::labels::ExecutionTape::append_serialized out of domain");
  }
  const auto slot = static_cast<std::size_t>(index);
  append_i64(out, ts_ns[slot]);
  append_i64(out, bid_min_u6[slot]);
  append_i64(out, bid_max_u6[slot]);
  append_i64(out, ask_min_u6[slot]);
  append_i64(out, ask_max_u6[slot]);
  append_i64(out, eligible_count[slot]);
}

// ---------------------------------------------------------------------------
// ExecutionTapeBuilder
// ---------------------------------------------------------------------------

ExecutionTapeBuilder::ExecutionTapeBuilder(SessionClock clock, std::int64_t session_ordinal)
    : clock_(std::move(clock)) {
  tape_.session_ordinal = session_ordinal;
  tape_.day = std::string(clock_.day());
  tape_.session_start_ns = clock_.session_start_a().ns();
  tape_.session_end_ns = clock_.session_end_a().ns();
}

Expected<ExecutionTapeBuilder, Refusal> ExecutionTapeBuilder::for_scope(const DayScope& scope) {
  Expected<SessionClock, Refusal> clock = SessionClock::from_session(scope.session());
  if (!clock.has_value()) {
    return Expected<ExecutionTapeBuilder, Refusal>::refuse(clock.error());
  }
  ExecutionTapeBuilder builder(std::move(clock).value(), scope.ordinal());
  if (scope.session().complete_group_count > 0) {
    const auto groups = static_cast<std::size_t>(scope.session().complete_group_count);
    builder.tape_.ts_ns.reserve(groups);
    builder.tape_.bid_min_u6.reserve(groups);
    builder.tape_.bid_max_u6.reserve(groups);
    builder.tape_.ask_min_u6.reserve(groups);
    builder.tape_.ask_max_u6.reserve(groups);
    builder.tape_.eligible_count.reserve(groups);
  }
  return builder;
}

ExecutionTapeBuilder ExecutionTapeBuilder::from_clock(SessionClock clock,
                                                      std::int64_t session_ordinal) {
  return ExecutionTapeBuilder(std::move(clock), session_ordinal);
}

Expected<bool, Refusal> ExecutionTapeBuilder::push_group(
    std::int64_t ts_ms_b, std::span<const qr::sources::StockQuoteRow> rows) {
  if (sealed_) {
    return Expected<bool, Refusal>::refuse(
        Refusal(RefusalCode::CONTENT_MISMATCH, kPushSite, "the tape is already sealed", ts_ms_b));
  }
  if (rows.empty()) {
    return Expected<bool, Refusal>::refuse(
        Refusal(RefusalCode::CONTENT_MISMATCH, kPushSite, "an empty equal-time group", ts_ms_b));
  }
  if (has_last_ts_ && ts_ms_b <= last_ts_ms_b_) {
    return Expected<bool, Refusal>::refuse(
        Refusal(RefusalCode::OUT_OF_ORDER, kPushSite,
                "equal-time groups must arrive strictly increasing", ts_ms_b));
  }
  for (const qr::sources::StockQuoteRow& row : rows) {
    if (row.ts_ms_b != ts_ms_b) {
      return Expected<bool, Refusal>::refuse(
          Refusal(RefusalCode::CONTENT_MISMATCH, kPushSite,
                  "a member does not carry its own group's millisecond", row.ts_ms_b));
    }
  }
  // THE SOLE FRAME-B -> FRAME-A CONVERSION, through the one clock authority
  // (boundary conditions 3, 4 and 5). A non-RTH stamp refuses here; the tape
  // never carries an instant this clock did not authenticate.
  const Expected<FrameB, Refusal> ts_b = frame_b_from_naive_et_ms(ts_ms_b);
  if (!ts_b.has_value()) {
    return Expected<bool, Refusal>::refuse(ts_b.error());
  }
  const Expected<FrameA, Refusal> ts_a = clock_.to_frame_a(ts_b.value());
  if (!ts_a.has_value()) {
    return Expected<bool, Refusal>::refuse(ts_a.error());
  }

  // --- the four extrema over the ELIGIBLE members --------------------------
  std::int64_t bid_min = 0;
  std::int64_t bid_max = 0;
  std::int64_t ask_min = 0;
  std::int64_t ask_max = 0;
  std::int64_t eligible = 0;
  for (const qr::sources::StockQuoteRow& row : rows) {
    const Expected<qr::nbbo::MemberClass, Refusal> classified = qr::nbbo::classify_member(row);
    if (!classified.has_value()) {
      return Expected<bool, Refusal>::refuse(classified.error());
    }
    // THE ONE ELIGIBILITY AUTHORITY (qr_nbbo's typed view), used verbatim.
    if (classified.value().validity != Validity::VALID) {
      census_.ineligible_members += 1;
      continue;
    }
    if (eligible == 0) {
      bid_min = row.bid_u6;
      bid_max = row.bid_u6;
      ask_min = row.ask_u6;
      ask_max = row.ask_u6;
    } else {
      bid_min = std::min(bid_min, row.bid_u6);
      bid_max = std::max(bid_max, row.bid_u6);
      ask_min = std::min(ask_min, row.ask_u6);
      ask_max = std::max(ask_max, row.ask_u6);
    }
    eligible += 1;
    census_.eligible_members += 1;
  }

  census_.groups_seen += 1;
  last_ts_ms_b_ = ts_ms_b;
  has_last_ts_ = true;
  if (eligible == 0) {
    census_.groups_without_eligible_member += 1;
    return false;
  }
  census_.groups_eligible += 1;
  tape_.ts_ns.push_back(ts_a.value().ns());
  tape_.bid_min_u6.push_back(bid_min);
  tape_.bid_max_u6.push_back(bid_max);
  tape_.ask_min_u6.push_back(ask_min);
  tape_.ask_max_u6.push_back(ask_max);
  tape_.eligible_count.push_back(eligible);
  return true;
}

Expected<ExecutionTape, Refusal> ExecutionTapeBuilder::seal() {
  if (sealed_) {
    return Expected<ExecutionTape, Refusal>::refuse(
        Refusal(RefusalCode::CONTENT_MISMATCH, kSealSite, "the tape is already sealed"));
  }
  // Condition 6 in this module's own shape: the OUTPUT order is re-checked on
  // the output, never inferred from the input's monotone stamps.
  for (std::size_t index = 1; index < tape_.ts_ns.size(); ++index) {
    if (tape_.ts_ns[index] <= tape_.ts_ns[index - 1]) {
      return Expected<ExecutionTape, Refusal>::refuse(
          Refusal(RefusalCode::OUT_OF_ORDER, kSealSite,
                  "the sealed tape is not strictly increasing in frame-A time",
                  static_cast<std::int64_t>(index)));
    }
  }
  sealed_ = true;
  tape_.census = census_;
  return std::move(tape_);
}

qr::parquet::FileExpected<ExecutionTape> build_execution_tape(
    qr::sources::StockQuoteReader& reader, const DayScope& scope) {
  Expected<ExecutionTapeBuilder, Refusal> opened = ExecutionTapeBuilder::for_scope(scope);
  if (!opened.has_value()) {
    return qr::parquet::FileExpected<ExecutionTape>::refuse(
        qr::parquet::FileRefusal(opened.error(), reader.path().string()));
  }
  ExecutionTapeBuilder builder = std::move(opened).value();
  qr::sources::StockQuoteReader::Group group;
  while (true) {
    const qr::parquet::FileExpected<bool> more = reader.next_group(group);
    if (!more.has_value()) {
      return qr::parquet::FileExpected<ExecutionTape>::refuse(more.error());
    }
    if (!more.value()) {
      break;
    }
    const Expected<bool, Refusal> pushed = builder.push_group(group.ts_ms_b, group.rows);
    if (!pushed.has_value()) {
      return qr::parquet::FileExpected<ExecutionTape>::refuse(
          qr::parquet::FileRefusal(pushed.error(), reader.path().string()));
    }
  }
  Expected<ExecutionTape, Refusal> sealed = builder.seal();
  if (!sealed.has_value()) {
    return qr::parquet::FileExpected<ExecutionTape>::refuse(
        qr::parquet::FileRefusal(sealed.error(), reader.path().string()));
  }
  if (reader.rth_rows() != scope.session().raw_rth_row_count) {
    return qr::parquet::FileExpected<ExecutionTape>::refuse(qr::parquet::FileRefusal(
        Refusal(RefusalCode::CONTENT_MISMATCH, kRunSite,
                "the pass did not reproduce the registry's raw_rth_row_count", reader.rth_rows()),
        reader.path().string()));
  }
  if (reader.group_count() != scope.session().complete_group_count) {
    return qr::parquet::FileExpected<ExecutionTape>::refuse(qr::parquet::FileRefusal(
        Refusal(RefusalCode::CONTENT_MISMATCH, kRunSite,
                "the pass did not reproduce the registry's complete_group_count",
                reader.group_count()),
        reader.path().string()));
  }
  return std::move(sealed).value();
}

Expected<std::int64_t, Refusal> verify_against(const ExecutionTape& tape,
                                               const qr::nbbo::QuoteGroups& groups) {
  std::int64_t matched = 0;
  std::int64_t tape_index = 0;
  for (std::size_t group = 0; group < groups.size(); ++group) {
    const std::int64_t eligible = groups.eligible_count[group];
    if (eligible <= 0) {
      continue;
    }
    if (tape_index >= tape.size()) {
      return Expected<std::int64_t, Refusal>::refuse(
          Refusal(RefusalCode::CONTENT_MISMATCH, kVerifySite,
                  "the WP5 projection carries an eligible group the execution tape does not",
                  static_cast<std::int64_t>(group)));
    }
    const auto slot = static_cast<std::size_t>(tape_index);
    if (tape.ts_ns[slot] != groups.ts_ns[group]) {
      return Expected<std::int64_t, Refusal>::refuse(
          Refusal(RefusalCode::CONTENT_MISMATCH, kVerifySite,
                  "an eligible group's frame-A instant disagrees with the WP5 projection",
                  tape.ts_ns[slot]));
    }
    if (tape.eligible_count[slot] != eligible) {
      return Expected<std::int64_t, Refusal>::refuse(
          Refusal(RefusalCode::CONTENT_MISMATCH, kVerifySite,
                  "an eligible member count disagrees with the WP5 projection",
                  tape.eligible_count[slot]));
    }
    // The extrema are bounded by the projection's own exact sums: with `n`
    // eligible members, `n*min <= sum <= n*max` for both columns. This is the
    // strongest statement the sums can make about an extremum, and it catches
    // a column swap, a side swap and a stale row.
    const std::int64_t bids = groups.bid_u6_sum[group];
    const std::int64_t asks = groups.ask_u6_sum[group];
    const std::array<std::pair<std::int64_t, std::int64_t>, 4> bounds{
        std::pair<std::int64_t, std::int64_t>{tape.bid_min_u6[slot], bids},
        std::pair<std::int64_t, std::int64_t>{tape.bid_max_u6[slot], bids},
        std::pair<std::int64_t, std::int64_t>{tape.ask_min_u6[slot], asks},
        std::pair<std::int64_t, std::int64_t>{tape.ask_max_u6[slot], asks}};
    for (std::size_t which = 0; which < bounds.size(); ++which) {
      const Expected<std::int64_t, Refusal> scaled = checked_mul(bounds[which].first, eligible);
      if (!scaled.has_value()) {
        return Expected<std::int64_t, Refusal>::refuse(scaled.error());
      }
      // A minimum times the count can never exceed the exact sum, and a maximum
      // times the count can never fall short of it.
      const bool is_minimum = which == 0 || which == 2;
      if (is_minimum ? scaled.value() > bounds[which].second
                     : scaled.value() < bounds[which].second) {
        return Expected<std::int64_t, Refusal>::refuse(
            Refusal(RefusalCode::CONTENT_MISMATCH, kVerifySite,
                    "an execution extremum is outside the WP5 exact scalar sum bounds",
                    tape.ts_ns[slot]));
      }
    }
    if (tape.bid_max_u6[slot] >= tape.ask_min_u6[slot] && eligible == 1) {
      return Expected<std::int64_t, Refusal>::refuse(
          Refusal(RefusalCode::CONTENT_MISMATCH, kVerifySite,
                  "a single-member eligible group is not two-sided with ask > bid",
                  tape.ts_ns[slot]));
    }
    tape_index += 1;
    matched += 1;
  }
  if (tape_index != tape.size()) {
    return Expected<std::int64_t, Refusal>::refuse(
        Refusal(RefusalCode::CONTENT_MISMATCH, kVerifySite,
                "the execution tape carries rows the WP5 projection has no eligible group for",
                tape.size() - tape_index));
  }
  return matched;
}

// ---------------------------------------------------------------------------
// ExtremumIndex
// ---------------------------------------------------------------------------

ExtremumIndex ExtremumIndex::build(std::span<const std::int64_t> values) {
  ExtremumIndex index;
  index.count_ = static_cast<std::int64_t>(values.size());
  std::int64_t padded = 1;
  while (padded < index.count_) {
    padded *= 2;
  }
  index.padded_ = padded;
  const auto nodes = static_cast<std::size_t>(2 * padded);
  index.min_.assign(nodes, std::numeric_limits<std::int64_t>::max());
  index.max_.assign(nodes, std::numeric_limits<std::int64_t>::min());
  for (std::size_t leaf = 0; leaf < values.size(); ++leaf) {
    const std::size_t node = static_cast<std::size_t>(padded) + leaf;
    index.min_[node] = values[leaf];
    index.max_[node] = values[leaf];
  }
  for (std::size_t node = static_cast<std::size_t>(padded); node-- > 1;) {
    index.min_[node] = std::min(index.min_[2 * node], index.min_[2 * node + 1]);
    index.max_[node] = std::max(index.max_[2 * node], index.max_[2 * node + 1]);
  }
  return index;
}

void ExtremumIndex::check_range(std::int64_t lo, std::int64_t hi) const {
  if (lo < 0 || hi >= count_ || lo > hi) {
    detail::fail_fast("qr::labels::ExtremumIndex query outside the tape's domain");
  }
}

std::int64_t ExtremumIndex::range_min(std::int64_t lo, std::int64_t hi) const {
  check_range(lo, hi);
  std::int64_t out = std::numeric_limits<std::int64_t>::max();
  auto left = static_cast<std::size_t>(lo + padded_);
  auto right = static_cast<std::size_t>(hi + padded_ + 1);
  while (left < right) {
    if ((left & 1U) != 0U) {
      out = std::min(out, min_[left++]);
    }
    if ((right & 1U) != 0U) {
      out = std::min(out, min_[--right]);
    }
    left /= 2;
    right /= 2;
  }
  return out;
}

std::int64_t ExtremumIndex::range_max(std::int64_t lo, std::int64_t hi) const {
  check_range(lo, hi);
  std::int64_t out = std::numeric_limits<std::int64_t>::min();
  auto left = static_cast<std::size_t>(lo + padded_);
  auto right = static_cast<std::size_t>(hi + padded_ + 1);
  while (left < right) {
    if ((left & 1U) != 0U) {
      out = std::max(out, max_[left++]);
    }
    if ((right & 1U) != 0U) {
      out = std::max(out, max_[--right]);
    }
    left /= 2;
    right /= 2;
  }
  return out;
}

std::int64_t ExtremumIndex::descend_below(std::size_t node, std::int64_t node_lo,
                                          std::int64_t node_hi, std::int64_t lo, std::int64_t hi,
                                          std::int64_t threshold) const {
  if (node_hi < lo || hi < node_lo || min_[node] > threshold) {
    return kNoIndex;
  }
  if (node_lo == node_hi) {
    return node_lo;
  }
  const std::int64_t mid = node_lo + (node_hi - node_lo) / 2;
  const std::int64_t left = descend_below(2 * node, node_lo, mid, lo, hi, threshold);
  if (left != kNoIndex) {
    return left;
  }
  return descend_below(2 * node + 1, mid + 1, node_hi, lo, hi, threshold);
}

std::int64_t ExtremumIndex::descend_above(std::size_t node, std::int64_t node_lo,
                                          std::int64_t node_hi, std::int64_t lo, std::int64_t hi,
                                          std::int64_t threshold) const {
  if (node_hi < lo || hi < node_lo || max_[node] < threshold) {
    return kNoIndex;
  }
  if (node_lo == node_hi) {
    return node_lo;
  }
  const std::int64_t mid = node_lo + (node_hi - node_lo) / 2;
  const std::int64_t left = descend_above(2 * node, node_lo, mid, lo, hi, threshold);
  if (left != kNoIndex) {
    return left;
  }
  return descend_above(2 * node + 1, mid + 1, node_hi, lo, hi, threshold);
}

std::int64_t ExtremumIndex::first_at_or_below(std::int64_t lo, std::int64_t hi,
                                              std::int64_t threshold) const {
  check_range(lo, hi);
  return descend_below(1, 0, padded_ - 1, lo, hi, threshold);
}

std::int64_t ExtremumIndex::first_at_or_above(std::int64_t lo, std::int64_t hi,
                                              std::int64_t threshold) const {
  check_range(lo, hi);
  return descend_above(1, 0, padded_ - 1, lo, hi, threshold);
}

std::int64_t ExtremumIndex::leftmost_argmin(std::int64_t lo, std::int64_t hi) const {
  return first_at_or_below(lo, hi, range_min(lo, hi));
}

std::int64_t ExtremumIndex::leftmost_argmax(std::int64_t lo, std::int64_t hi) const {
  return first_at_or_above(lo, hi, range_max(lo, hi));
}

// ---------------------------------------------------------------------------
// SessionLabelIndex
// ---------------------------------------------------------------------------

SessionLabelIndex::SessionLabelIndex(ExecutionTape tape) : tape_(std::move(tape)) {
  bid_min_ = ExtremumIndex::build(tape_.bid_min_u6);
  bid_max_ = ExtremumIndex::build(tape_.bid_max_u6);
  ask_min_ = ExtremumIndex::build(tape_.ask_min_u6);
  ask_max_ = ExtremumIndex::build(tape_.ask_max_u6);
}

SessionLabelIndex SessionLabelIndex::build(ExecutionTape tape) {
  return SessionLabelIndex(std::move(tape));
}

}  // namespace qr::labels
