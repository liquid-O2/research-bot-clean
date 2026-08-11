#include "qr_w20/mechanics.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <system_error>

#include "qr_clock/session_clock.hpp"
#include "qr_core/checked.hpp"
#include "qr_m25/npy.hpp"
#include "qr_parquet/reader.hpp"

namespace qr::w20 {
namespace {

constexpr const char* kSite = "qr_w20::mechanics";
constexpr std::int64_t kMsPerSecond = 1000;
/// A basis point of a midpoint m is m/10,000; half a basis point is m/20,000.
/// A2: "spot-move event = |Delta mid| >= 0.5bps".
constexpr std::int64_t kHalfBpDenominator = 20000;

template <class T>
Expected<T, Refusal> refuse(RefusalCode code, const char* detail, std::int64_t context = 0) {
  return Expected<T, Refusal>::refuse(Refusal(code, kSite, detail, context));
}

/// Integer basis points of `value` against `reference`, rounded half away from
/// zero. Both are u6 integers; `reference` must be positive.
std::int64_t bps_of(std::int64_t value, std::int64_t reference) noexcept {
  const std::int64_t scaled = value * 10000;
  const std::int64_t half = reference / 2;
  return scaled >= 0 ? (scaled + half) / reference : -((-scaled + half) / reference);
}

}  // namespace

// ---------------------------------------------------------------------------
// DenseCounter.
// ---------------------------------------------------------------------------

DenseCounter::DenseCounter(std::int64_t base, std::int64_t span)
    : counts_(static_cast<std::size_t>(span > 0 ? span : 0), 0), base_(base) {}

void DenseCounter::add_weighted(std::int64_t value, std::int64_t weight) noexcept {
  if (weight <= 0) {
    return;
  }
  // Every counter is CHECKED (FINAL_PLAN section 6: checked arithmetic via
  // __builtin_*_overflow, clamp/saturate banned). An addition that cannot be
  // represented is refused in place — the observation is dropped and the
  // counter is flagged — never wrapped and never clamped.
  std::int64_t next_total = 0;
  if (__builtin_add_overflow(total_, weight, &next_total)) {
    counts_overflowed_ = true;
    return;
  }
  total_ = next_total;
  if (!seen_) {
    min_ = value;
    max_ = value;
    seen_ = true;
  } else {
    min_ = std::min(min_, value);
    max_ = std::max(max_, value);
  }
  if (!sum_overflowed_) {
    std::int64_t product = 0;
    std::int64_t next = 0;
    if (__builtin_mul_overflow(value, weight, &product) ||
        __builtin_add_overflow(sum_, product, &next)) {
      sum_overflowed_ = true;
    } else {
      sum_ = next;
    }
  }
  std::int64_t* cell = nullptr;
  if (value < base_) {
    cell = &under_;
  } else {
    const std::int64_t offset = value - base_;
    cell = offset >= static_cast<std::int64_t>(counts_.size())
               ? &over_
               : &counts_[static_cast<std::size_t>(offset)];
  }
  std::int64_t next_cell = 0;
  if (__builtin_add_overflow(*cell, weight, &next_cell)) {
    counts_overflowed_ = true;
    return;
  }
  *cell = next_cell;
}

Expected<std::int64_t, Refusal> DenseCounter::sum() const noexcept {
  if (sum_overflowed_) {
    return refuse<std::int64_t>(RefusalCode::ARITHMETIC_OVERFLOW,
                                "census sum overflowed int64 — no saturated value is emitted");
  }
  return sum_;
}

std::int64_t DenseCounter::count_at(std::int64_t value) const noexcept {
  if (value < base_) return 0;
  const std::int64_t offset = value - base_;
  if (offset >= static_cast<std::int64_t>(counts_.size())) return 0;
  return counts_[static_cast<std::size_t>(offset)];
}

std::int64_t DenseCounter::count_le(std::int64_t value) const noexcept {
  std::int64_t seen = under_;
  if (value < base_) {
    return 0;
  }
  const std::int64_t limit =
      std::min(value - base_ + 1, static_cast<std::int64_t>(counts_.size()));
  for (std::int64_t index = 0; index < limit; ++index) {
    seen += counts_[static_cast<std::size_t>(index)];
  }
  return seen;
}

std::int64_t DenseCounter::quantile(std::int64_t q_num, std::int64_t q_den,
                                    bool& out_of_domain) const noexcept {
  out_of_domain = false;
  if (total_ == 0 || q_den <= 0) {
    out_of_domain = true;
    return 0;
  }
  // The smallest value v with count(<= v) >= ceil(q * n): an exact rank rule,
  // never an interpolation between two observed values.
  const std::int64_t target = (total_ * q_num + q_den - 1) / q_den;
  if (under_ >= target) {
    out_of_domain = true;
    return base_ - 1;
  }
  std::int64_t seen = under_;
  for (std::size_t index = 0; index < counts_.size(); ++index) {
    seen += counts_[index];
    if (seen >= target) {
      return base_ + static_cast<std::int64_t>(index);
    }
  }
  out_of_domain = true;
  return base_ + static_cast<std::int64_t>(counts_.size());
}

// ---------------------------------------------------------------------------
// CensusReport.
// ---------------------------------------------------------------------------

void CensusReport::metric(std::string scope, std::string key, std::string metric_name,
                          std::int64_t value) {
  rows_.push_back(CensusRow{std::move(scope), std::move(key), std::move(metric_name), value,
                            std::string{}, false});
}

void CensusReport::text(std::string scope, std::string key, std::string metric_name,
                        std::string value) {
  rows_.push_back(
      CensusRow{std::move(scope), std::move(key), std::move(metric_name), 0, std::move(value), true});
}

void CensusReport::distribution(const std::string& scope, const std::string& key,
                                const DenseCounter& counter) {
  metric(scope, key, "n", counter.total());
  metric(scope, key, "counts_overflowed", counter.counts_overflowed() ? 1 : 0);
  metric(scope, key, "under", counter.under());
  metric(scope, key, "over", counter.over());
  if (counter.total() > 0) {
    metric(scope, key, "min", counter.min());
    metric(scope, key, "max", counter.max());
  }
  const Expected<std::int64_t, Refusal> total = counter.sum();
  if (total.has_value()) {
    metric(scope, key, "sum", total.value());
  } else {
    text(scope, key, "sum", "ARITHMETIC_OVERFLOW");
  }
  static constexpr std::array<std::pair<const char*, std::int64_t>, 8> kQuantiles{
      std::pair<const char*, std::int64_t>{"p10", 10}, {"p25", 25}, {"p50", 50}, {"p75", 75},
      {"p90", 90},                                     {"p95", 95}, {"p99", 99}, {"p999", 999}};
  for (const auto& [name, numerator] : kQuantiles) {
    const std::int64_t denominator = numerator == 999 ? 1000 : 100;
    bool outside = false;
    const std::int64_t value = counter.quantile(numerator, denominator, outside);
    metric(scope, key, name, value);
    metric(scope, key, std::string(name) + "_out_of_domain", outside ? 1 : 0);
  }
}

void CensusReport::histogram(const std::string& scope, const std::string& key,
                             const DenseCounter& counter) {
  for (std::int64_t index = 0; index < counter.span(); ++index) {
    const std::int64_t value = counter.base() + index;
    const std::int64_t count = counter.count_at(value);
    if (count > 0) {
      metric(scope, key, "cell_" + std::to_string(value), count);
    }
  }
  metric(scope, key, "cell_under", counter.under());
  metric(scope, key, "cell_over", counter.over());
}

Expected<std::monostate, Refusal> CensusReport::write(const std::filesystem::path& path) const {
  std::FILE* out = std::fopen(path.c_str(), "wb");
  if (out == nullptr) {
    return refuse<std::monostate>(RefusalCode::IO, "cannot open the census output for writing");
  }
  std::fprintf(out, "scope\tkey\tmetric\tvalue\n");
  for (const CensusRow& row : rows_) {
    if (row.is_text) {
      std::fprintf(out, "%s\t%s\t%s\t%s\n", row.scope.c_str(), row.key.c_str(), row.metric.c_str(),
                   row.text.c_str());
    } else {
      std::fprintf(out, "%s\t%s\t%s\t%lld\n", row.scope.c_str(), row.key.c_str(),
                   row.metric.c_str(), static_cast<long long>(row.value));
    }
  }
  if (std::fclose(out) != 0) {
    return refuse<std::monostate>(RefusalCode::IO, "the census output did not close cleanly");
  }
  return std::monostate{};
}

void CensusReport::print() const {
  for (const CensusRow& row : rows_) {
    if (row.is_text) {
      std::printf("%s\t%s\t%s\t%s\n", row.scope.c_str(), row.key.c_str(), row.metric.c_str(),
                  row.text.c_str());
    } else {
      std::printf("%s\t%s\t%s\t%lld\n", row.scope.c_str(), row.key.c_str(), row.metric.c_str(),
                  static_cast<long long>(row.value));
    }
  }
}

// ---------------------------------------------------------------------------
// Coverage and dialect.
// ---------------------------------------------------------------------------

const char* era_name(Era era) noexcept {
  switch (era) {
    case Era::ABSENT:
      return "ABSENT";
    case Era::FLAT:
      return "FLAT";
    case Era::SHARD:
      return "SHARD";
  }
  return "ABSENT";
}

namespace {

/// The shard list of an admitted session, in the reader's own sorted order,
/// plus the era it came from. MODALITY_ABSENT is a VALUE here, not a refusal:
/// the coverage census exists precisely to count uncovered sessions.
struct Shards {
  Era era = Era::ABSENT;
  std::vector<std::filesystem::path> paths;
};

Shards shards_of(const DayScope& scope, const std::filesystem::path& corpus_root) {
  Shards out;
  const std::string& day = scope.day();
  const std::filesystem::path year_dir = corpus_root / day.substr(0, 4);
  const std::filesystem::path flat = year_dir / (day + ".parquet");
  std::error_code error;
  if (std::filesystem::is_regular_file(flat, error)) {
    out.era = Era::FLAT;
    out.paths.push_back(flat);
    return out;
  }
  const std::filesystem::path sharded = year_dir / day;
  if (std::filesystem::is_directory(sharded, error)) {
    for (const std::filesystem::directory_entry& entry :
         std::filesystem::directory_iterator(sharded, error)) {
      if (entry.path().extension() == ".parquet") {
        out.paths.push_back(entry.path());
      }
    }
    // Sorted iteration is a law (FINAL_PLAN section 6).
    std::sort(out.paths.begin(), out.paths.end());
    if (!out.paths.empty()) {
      out.era = Era::SHARD;
    }
  }
  return out;
}

}  // namespace

Expected<CoverageRow, Refusal> coverage_of(const DayScope& scope,
                                           const std::filesystem::path& corpus_root) {
  CoverageRow row;
  row.ordinal = scope.ordinal();
  row.day = scope.day();
  const Shards shards = shards_of(scope, corpus_root);
  row.era = shards.era;
  row.shard_count = static_cast<std::int64_t>(shards.paths.size());
  for (const std::filesystem::path& path : shards.paths) {
    std::error_code error;
    const std::uintmax_t size = std::filesystem::file_size(path, error);
    if (error) {
      return refuse<CoverageRow>(RefusalCode::IO, "cannot size a covered shard", row.ordinal);
    }
    const Expected<std::int64_t, Refusal> total =
        qr::checked_add(row.bytes, static_cast<std::int64_t>(size));
    if (!total.has_value()) {
      return Expected<CoverageRow, Refusal>::refuse(total.error());
    }
    row.bytes = total.value();
  }
  return row;
}

Expected<std::vector<DialectRow>, Refusal> option_quote_dialect(
    const DayScope& scope, const std::filesystem::path& corpus_root) {
  const Shards shards = shards_of(scope, corpus_root);
  if (shards.era == Era::ABSENT) {
    return refuse<std::vector<DialectRow>>(
        RefusalCode::MODALITY_ABSENT, "this corpus covers no option quotes for this session",
        scope.ordinal());
  }
  std::vector<DialectRow> rows;
  for (const std::filesystem::path& path : shards.paths) {
    const qr::parquet::FileExpected<qr::parquet::File> opened =
        qr::parquet::File::open(path.string());
    if (!opened.has_value()) {
      return Expected<std::vector<DialectRow>, Refusal>::refuse(opened.error().refusal());
    }
    const qr::parquet::FileExpected<qr::sources::OptionQuoteSchemaCheck> checked =
        qr::sources::check_option_quote_schema(opened.value());
    if (!checked.has_value()) {
      return Expected<std::vector<DialectRow>, Refusal>::refuse(checked.error().refusal());
    }
    DialectRow row;
    row.ordinal = scope.ordinal();
    row.day = scope.day();
    row.shard = path.filename().string();
    row.file_rows = checked.value().num_rows;
    row.row_groups = static_cast<std::int64_t>(checked.value().num_row_groups);
    for (std::size_t slot = 0; slot < row.forms.size() && slot < checked.value().forms.size();
         ++slot) {
      row.forms[slot] = static_cast<std::uint8_t>(checked.value().forms[slot]);
    }
    rows.push_back(std::move(row));
  }
  return rows;
}

// ---------------------------------------------------------------------------
// SpotGrid.
// ---------------------------------------------------------------------------

Expected<SpotGrid, Refusal> SpotGrid::open(const std::filesystem::path& tape_side_dir,
                                           std::int64_t open_ms_b, std::int64_t bar_count) {
  const std::filesystem::path leaf = tape_side_dir / "features" / "grid_1s.npy";
  Expected<qr::m25::NpyArray, Refusal> array = qr::m25::NpyArray::open(leaf);
  if (!array.has_value()) {
    return Expected<SpotGrid, Refusal>::refuse(array.error());
  }
  const qr::m25::NpyArray& grid = array.value();
  if (grid.dtype() != qr::m25::NpyDtype::F4 || grid.shape().size() != 2 || grid.shape()[1] != 4) {
    return refuse<SpotGrid>(RefusalCode::SCHEMA_MISMATCH,
                            "grid_1s is not the APPENDIX C4 [S,4] f4 leaf");
  }
  const std::int64_t expected = bar_count * 60 + 1;
  if (grid.rows() != expected) {
    return refuse<SpotGrid>(RefusalCode::CONTENT_MISMATCH,
                            "grid_1s row count disagrees with the session's own bar count",
                            grid.rows());
  }
  SpotGrid out;
  out.open_ms_b_ = open_ms_b;
  const std::span<const float> values = grid.f4();
  out.mid_u6_.reserve(static_cast<std::size_t>(grid.rows()));
  for (std::int64_t index = 0; index < grid.rows(); ++index) {
    const float mid = values[static_cast<std::size_t>(index * 4)];
    // A missing endpoint carries 0, which no valid midpoint can be (the card
    // requires it finite and POSITIVE).
    const std::int64_t mid_u6 = mid > 0.0F ? static_cast<std::int64_t>(std::llround(mid)) : 0;
    out.mid_u6_.push_back(mid_u6);
    if (mid_u6 > 0) {
      ++out.present_;
    }
  }
  for (std::size_t index = 1; index < out.mid_u6_.size(); ++index) {
    const std::int64_t previous = out.mid_u6_[index - 1];
    const std::int64_t current = out.mid_u6_[index];
    if (previous <= 0 || current <= 0) {
      continue;
    }
    const std::int64_t delta = current > previous ? current - previous : previous - current;
    // |delta| >= 0.5bp of the PRIOR endpoint, in exact integers.
    if (delta * kHalfBpDenominator >= previous) {
      out.move_endpoints_.push_back(static_cast<std::int64_t>(index));
    }
  }
  return out;
}

std::int64_t SpotGrid::mid_u6_endpoint(std::int64_t index) const noexcept {
  if (index < 0 || index >= static_cast<std::int64_t>(mid_u6_.size())) {
    return 0;
  }
  return mid_u6_[static_cast<std::size_t>(index)];
}

std::int64_t SpotGrid::mid_u6_at(std::int64_t ts_ms_b) const noexcept {
  if (ts_ms_b < open_ms_b_) {
    return 0;
  }
  // The last COMPLETE-second endpoint at or before ts: its value is by
  // construction the last eligible midpoint strictly before that endpoint, and
  // the endpoint is <= ts, so the value is strictly prior to ts.
  return mid_u6_endpoint((ts_ms_b - open_ms_b_) / kMsPerSecond);
}

// ---------------------------------------------------------------------------
// D4 — option quotes.
// ---------------------------------------------------------------------------

namespace {

struct QuoteContractState {
  std::int64_t last_ts_ms = -1;
  std::int64_t updates = 0;
  std::int64_t last_bid_u6 = 0;
  std::int64_t last_ask_u6 = 0;
  std::int64_t moneyness_bps_first = 0;
  std::int32_t expiration_day = 0;
  bool moneyness_seen = false;
  std::uint8_t eligible_mask = 0;
  std::uint8_t counted_mask = 0;
};

/// One open spot-move event.
struct RequoteEvent {
  std::int64_t start_ms = 0;
  std::int64_t live = 0;
  std::int64_t needed = 0;
  std::int64_t counted = 0;
  bool first_seen = false;
  bool half_seen = false;
  bool open = false;
};

OptionQuoteMechanicsCensus fresh_quote_census() {
  OptionQuoteMechanicsCensus census;
  // Sizes: exact to 1,024 contracts displayed, with the true max reported.
  census.bid_size = DenseCounter(0, 1025);
  census.ask_size = DenseCounter(0, 1025);
  // Width: exact to $10.24 in cents, and to 2,000bp of the midpoint.
  census.spread_cents = DenseCounter(0, 1025);
  census.spread_bps_of_mid = DenseCounter(0, 20001);
  census.size_imbalance_bp = DenseCounter(-10000, 20001);
  // Term: exact to two calendar years.
  census.dte_rows = DenseCounter(0, 731);
  census.dte_contracts = DenseCounter(0, 731);
  // Moneyness: (K - m)/m in bp, exact to +-50%.
  census.moneyness_bps_rows = DenseCounter(-5000, 10001);
  census.moneyness_bps_contracts = DenseCounter(-5000, 10001);
  census.group_size = DenseCounter(0, 4097);
  census.updates_per_second = DenseCounter(0, 65537);
  census.contract_updates = DenseCounter(0, 262145);
  census.contract_gap_ms = DenseCounter(0, 60001);
  census.first_requote_ms = DenseCounter(0, kRequoteHorizonMs + 1);
  census.half_requote_ms = DenseCounter(0, kRequoteHorizonMs + 1);
  census.live_contracts_at_event = DenseCounter(0, 65537);
  census.live_two_sided_60s = DenseCounter(0, 65537);
  census.one_sided_fraction_bp = DenseCounter(0, 10001);
  census.median_spread_bps_60s = DenseCounter(0, 20001);
  census.thinning_ratio_bp = DenseCounter(0, 40001);
  return census;
}

}  // namespace

Expected<OptionQuoteMechanicsCensus, Refusal> census_option_quotes(
    const DayScope& scope, const std::filesystem::path& corpus_root,
    const std::filesystem::path& tape_side_dir) {
  const Shards shards = shards_of(scope, corpus_root);
  OptionQuoteMechanicsCensus census = fresh_quote_census();
  census.ordinal = scope.ordinal();
  census.day = scope.day();
  census.era = shards.era;
  census.shard_count = static_cast<std::int64_t>(shards.paths.size());
  if (shards.era == Era::ABSENT) {
    // MODALITY_ABSENT is the ANSWER for these sessions, and the census says so
    // with every counter at its structural zero — never a substituted value.
    return census;
  }

  const Expected<SessionClock, Refusal> clock = SessionClock::from_session(scope.session());
  if (!clock.has_value()) {
    return Expected<OptionQuoteMechanicsCensus, Refusal>::refuse(clock.error());
  }
  const std::int64_t open_ms_b = clock.value().open_b().ns() / 1000000;
  const std::int64_t session_seconds = clock.value().expected_bar_count() * 60;

  bool have_spot = false;
  SpotGrid spot;
  if (!tape_side_dir.empty()) {
    Expected<SpotGrid, Refusal> opened =
        SpotGrid::open(tape_side_dir, open_ms_b, clock.value().expected_bar_count());
    if (!opened.has_value()) {
      return Expected<OptionQuoteMechanicsCensus, Refusal>::refuse(opened.error());
    }
    spot = std::move(opened).value();
    have_spot = true;
  }

  qr::parquet::FileExpected<qr::sources::OptionQuoteReader> opened_reader =
      qr::sources::OptionQuoteReader::open(scope, corpus_root);
  if (!opened_reader.has_value()) {
    return Expected<OptionQuoteMechanicsCensus, Refusal>::refuse(opened_reader.error().refusal());
  }
  qr::sources::OptionQuoteReader reader = std::move(opened_reader).value();

  std::map<ContractKey, std::int32_t> index_of;
  std::vector<QuoteContractState> contracts;
  std::map<std::int32_t, std::int64_t> expirations;

  std::array<RequoteEvent, kRequoteSlots> events{};
  std::size_t next_move = 0;
  static const std::vector<std::int64_t> kNoMoves;
  const std::vector<std::int64_t>& moves = have_spot ? spot.move_endpoints() : kNoMoves;
  census.move_events = static_cast<std::int64_t>(moves.size());

  std::int64_t current_second = -1;
  std::int64_t updates_this_second = 0;
  std::int64_t next_thinning_sample = 0;
  std::int64_t previous_live = -1;

  const auto close_event = [&](RequoteEvent& event) {
    if (!event.open) return;
    if (!event.first_seen) ++census.no_requote_5s_any;
    if (!event.half_seen) ++census.no_requote_5s_half;
    event.open = false;
  };

  const auto expire_events = [&](std::int64_t now_ms) {
    for (std::size_t slot = 0; slot < kRequoteSlots; ++slot) {
      RequoteEvent& event = events[slot];
      if (event.open && now_ms - event.start_ms > kRequoteHorizonMs) {
        close_event(event);
        const std::uint8_t bit = static_cast<std::uint8_t>(1U << slot);
        for (QuoteContractState& state : contracts) {
          state.eligible_mask = static_cast<std::uint8_t>(state.eligible_mask & ~bit);
          state.counted_mask = static_cast<std::uint8_t>(state.counted_mask & ~bit);
        }
      }
    }
  };

  const auto open_events_through = [&](std::int64_t now_ms) {
    while (next_move < moves.size()) {
      const std::int64_t start_ms = open_ms_b + moves[next_move] * kMsPerSecond;
      if (start_ms > now_ms) {
        break;
      }
      ++next_move;
      std::size_t slot = kRequoteSlots;
      for (std::size_t candidate = 0; candidate < kRequoteSlots; ++candidate) {
        if (!events[candidate].open) {
          slot = candidate;
          break;
        }
      }
      if (slot == kRequoteSlots) {
        ++census.move_events_dropped;
        continue;
      }
      const std::uint8_t bit = static_cast<std::uint8_t>(1U << slot);
      std::int64_t live = 0;
      for (QuoteContractState& state : contracts) {
        state.counted_mask = static_cast<std::uint8_t>(state.counted_mask & ~bit);
        const bool is_live =
            state.last_ts_ms >= 0 && state.last_ts_ms < start_ms &&
            start_ms - state.last_ts_ms <= kLiveWindowMs;
        if (is_live) {
          state.eligible_mask = static_cast<std::uint8_t>(state.eligible_mask | bit);
          ++live;
        } else {
          state.eligible_mask = static_cast<std::uint8_t>(state.eligible_mask & ~bit);
        }
      }
      census.live_contracts_at_event.add(live);
      if (live == 0) {
        ++census.move_events_no_live_contract;
        continue;
      }
      ++census.move_events_tracked;
      RequoteEvent& event = events[slot];
      event.start_ms = start_ms;
      event.live = live;
      event.needed = (live + 1) / 2;  // ">= half the live contracts", exactly.
      event.counted = 0;
      event.first_seen = false;
      event.half_seen = false;
      event.open = true;
    }
  };

  qr::sources::OptionQuoteReader::Group group;
  while (true) {
    const qr::parquet::FileExpected<bool> more = reader.next_group(group);
    if (!more.has_value()) {
      return Expected<OptionQuoteMechanicsCensus, Refusal>::refuse(more.error().refusal());
    }
    if (!more.value()) {
      break;
    }
    census.group_size.add(static_cast<std::int64_t>(group.rows.size()));

    const std::int64_t ts = group.ts_ms_b;
    const std::int64_t second = (ts - open_ms_b) / kMsPerSecond;
    if (second != current_second) {
      if (current_second >= 0) {
        census.updates_per_second.add(updates_this_second);
      }
      // Seconds with no quote group at all are part of the cadence census.
      for (std::int64_t gap = current_second + 1; gap < second; ++gap) {
        census.updates_per_second.add(0);
      }
      current_second = second;
      updates_this_second = 0;
    }
    updates_this_second += static_cast<std::int64_t>(group.rows.size());

    if (have_spot) {
      expire_events(ts);
      open_events_through(ts);
    }

    const std::int64_t spot_u6 = have_spot ? spot.mid_u6_at(ts) : 0;

    for (const qr::sources::OptionQuoteRow& row : group.rows) {
      if (row.null_mask != 0) {
        ++census.null_field_rows;
      }
      switch (row.right) {
        case qr::sources::Right::Call:
          ++census.calls;
          break;
        case qr::sources::Right::Put:
          ++census.puts;
          break;
        case qr::sources::Right::Other:
          ++census.other_right;
          break;
      }
      census.bid_size.add(row.bid_size);
      census.ask_size.add(row.ask_size);
      if (row.bid_size > 0 || row.ask_size > 0) {
        census.size_imbalance_bp.add(
            bps_of(row.ask_size - row.bid_size, row.ask_size + row.bid_size));
      }

      const bool two_sided = row.bid_u6 > 0 && row.ask_u6 > 0;
      if (row.bid_u6 <= 0) ++census.zero_bid;
      if (row.ask_u6 <= 0) ++census.zero_ask;
      if (row.bid_u6 > row.ask_u6) ++census.crossed;
      if (row.bid_u6 == row.ask_u6 && row.bid_u6 > 0) ++census.locked;
      if (two_sided && row.ask_u6 > row.bid_u6) {
        ++census.two_sided_positive;
        const std::int64_t width = row.ask_u6 - row.bid_u6;
        census.spread_cents.add(width / 10000);
        const std::int64_t mid = qr::sources::midpoint_u6(row.bid_u6, row.ask_u6);
        if (mid > 0) {
          census.spread_bps_of_mid.add(bps_of(width, mid));
        }
      }

      const std::int64_t dte =
          static_cast<std::int64_t>(row.expiration_day) - scope.civil_date().days_since_epoch();
      census.dte_rows.add(dte);

      std::int64_t moneyness = 0;
      bool moneyness_ok = false;
      if (spot_u6 > 0) {
        moneyness = bps_of(row.strike_u6 - spot_u6, spot_u6);
        census.moneyness_bps_rows.add(moneyness);
        moneyness_ok = true;
      } else if (have_spot) {
        ++census.spot_absent_rows;
      }

      const ContractKey key{row.expiration_day, row.strike_u6,
                            static_cast<std::uint8_t>(row.right)};
      auto found = index_of.find(key);
      if (found == index_of.end()) {
        const std::int32_t slot = static_cast<std::int32_t>(contracts.size());
        contracts.push_back(QuoteContractState{});
        contracts.back().expiration_day = row.expiration_day;
        found = index_of.emplace(key, slot).first;
        census.dte_contracts.add(dte);
        ++expirations[row.expiration_day];
      }
      QuoteContractState& state = contracts[static_cast<std::size_t>(found->second)];
      if (moneyness_ok && !state.moneyness_seen) {
        state.moneyness_seen = true;
        state.moneyness_bps_first = moneyness;
        census.moneyness_bps_contracts.add(moneyness);
      }
      if (state.last_ts_ms >= 0) {
        census.contract_gap_ms.add(ts - state.last_ts_ms);
      }
      const std::int64_t previous_ts = state.last_ts_ms;
      state.last_ts_ms = ts;
      ++state.updates;
      state.last_bid_u6 = row.bid_u6;
      state.last_ask_u6 = row.ask_u6;

      if (have_spot && state.eligible_mask != 0) {
        for (std::size_t slot = 0; slot < kRequoteSlots; ++slot) {
          const std::uint8_t bit = static_cast<std::uint8_t>(1U << slot);
          if ((state.eligible_mask & bit) == 0) continue;
          RequoteEvent& event = events[slot];
          if (!event.open || ts < event.start_ms) continue;
          if ((state.counted_mask & bit) != 0) continue;
          // A contract counts ONCE per event, and only for an update strictly
          // after the event instant (`previous_ts < start` was the liveness
          // condition, so this update is the requote).
          if (previous_ts >= event.start_ms) continue;
          state.counted_mask = static_cast<std::uint8_t>(state.counted_mask | bit);
          ++event.counted;
          if (!event.first_seen) {
            event.first_seen = true;
            census.first_requote_ms.add(ts - event.start_ms);
          }
          if (!event.half_seen && event.counted >= event.needed) {
            event.half_seen = true;
            census.half_requote_ms.add(ts - event.start_ms);
          }
        }
      }
    }

    // --- coverage thinning: a 60s sample of the live two-sided ladder --------
    while (second >= next_thinning_sample && next_thinning_sample <= session_seconds) {
      const std::int64_t sample_ms = open_ms_b + next_thinning_sample * kMsPerSecond;
      std::int64_t live = 0;
      std::int64_t one_sided = 0;
      DenseCounter spreads(0, 20001);
      for (const QuoteContractState& state : contracts) {
        if (state.last_ts_ms < 0 || sample_ms - state.last_ts_ms > kLiveWindowMs) {
          continue;
        }
        ++live;
        if (state.last_bid_u6 <= 0 || state.last_ask_u6 <= 0) {
          ++one_sided;
          continue;
        }
        const std::int64_t mid =
            qr::sources::midpoint_u6(state.last_bid_u6, state.last_ask_u6);
        if (mid > 0 && state.last_ask_u6 > state.last_bid_u6) {
          spreads.add(bps_of(state.last_ask_u6 - state.last_bid_u6, mid));
        }
      }
      if (next_thinning_sample > 0) {
        census.live_two_sided_60s.add(live);
        if (live > 0) {
          census.one_sided_fraction_bp.add((one_sided * 10000) / live);
        }
        if (spreads.total() > 0) {
          bool outside = false;
          census.median_spread_bps_60s.add(spreads.quantile(50, 100, outside));
        }
        if (previous_live > 0) {
          census.thinning_ratio_bp.add((live * 10000) / previous_live);
        }
      }
      previous_live = live;
      next_thinning_sample += 60;
    }
  }

  if (current_second >= 0) {
    census.updates_per_second.add(updates_this_second);
  }
  for (std::size_t slot = 0; slot < kRequoteSlots; ++slot) {
    close_event(events[slot]);
  }
  for (const QuoteContractState& state : contracts) {
    census.contract_updates.add(state.updates);
  }

  census.rth_rows = reader.rth_rows();
  census.groups = reader.group_count();
  census.skipped_null_rows = reader.skipped_null_rows();
  census.decoded_values = reader.decoded_values();
  census.contracts = static_cast<std::int64_t>(contracts.size());
  census.expirations = static_cast<std::int64_t>(expirations.size());
  return census;
}

void emit(CensusReport& report, const OptionQuoteMechanicsCensus& census) {
  const std::string scope = "s" + std::to_string(census.ordinal);
  report.text(scope, "session", "day", census.day);
  report.text(scope, "session", "era", era_name(census.era));
  report.metric(scope, "session", "shard_count", census.shard_count);
  report.metric(scope, "stream", "rth_rows", census.rth_rows);
  report.metric(scope, "stream", "groups", census.groups);
  report.metric(scope, "stream", "skipped_null_rows", census.skipped_null_rows);
  report.metric(scope, "stream", "decoded_values", census.decoded_values);
  report.metric(scope, "stream", "contracts", census.contracts);
  report.metric(scope, "stream", "expirations", census.expirations);
  report.metric(scope, "stream", "calls", census.calls);
  report.metric(scope, "stream", "puts", census.puts);
  report.metric(scope, "stream", "other_right", census.other_right);
  report.metric(scope, "stream", "null_field_rows", census.null_field_rows);
  report.metric(scope, "width", "two_sided_positive", census.two_sided_positive);
  report.metric(scope, "width", "zero_bid", census.zero_bid);
  report.metric(scope, "width", "zero_ask", census.zero_ask);
  report.metric(scope, "width", "crossed", census.crossed);
  report.metric(scope, "width", "locked", census.locked);
  report.metric(scope, "spot", "absent_rows", census.spot_absent_rows);
  report.distribution(scope, "bid_size", census.bid_size);
  report.distribution(scope, "ask_size", census.ask_size);
  report.distribution(scope, "spread_cents", census.spread_cents);
  report.distribution(scope, "spread_bps_of_mid", census.spread_bps_of_mid);
  report.distribution(scope, "size_imbalance_bp", census.size_imbalance_bp);
  report.distribution(scope, "dte_rows", census.dte_rows);
  report.distribution(scope, "dte_contracts", census.dte_contracts);
  report.histogram(scope, "dte_contracts_hist", census.dte_contracts);
  report.distribution(scope, "moneyness_bps_rows", census.moneyness_bps_rows);
  report.distribution(scope, "moneyness_bps_contracts", census.moneyness_bps_contracts);
  report.distribution(scope, "group_size", census.group_size);
  report.distribution(scope, "updates_per_second", census.updates_per_second);
  report.distribution(scope, "contract_updates", census.contract_updates);
  report.distribution(scope, "contract_gap_ms", census.contract_gap_ms);
  report.metric(scope, "requote", "move_events", census.move_events);
  report.metric(scope, "requote", "move_events_tracked", census.move_events_tracked);
  report.metric(scope, "requote", "move_events_dropped", census.move_events_dropped);
  report.metric(scope, "requote", "move_events_no_live_contract",
                census.move_events_no_live_contract);
  report.metric(scope, "requote", "no_requote_5s_any", census.no_requote_5s_any);
  report.metric(scope, "requote", "no_requote_5s_half", census.no_requote_5s_half);
  report.distribution(scope, "first_requote_ms", census.first_requote_ms);
  report.distribution(scope, "half_requote_ms", census.half_requote_ms);
  report.distribution(scope, "live_contracts_at_event", census.live_contracts_at_event);
  report.distribution(scope, "live_two_sided_60s", census.live_two_sided_60s);
  report.distribution(scope, "one_sided_fraction_bp", census.one_sided_fraction_bp);
  report.distribution(scope, "median_spread_bps_60s", census.median_spread_bps_60s);
  report.distribution(scope, "thinning_ratio_bp", census.thinning_ratio_bp);
}

// ---------------------------------------------------------------------------
// D3 — option prints.
// ---------------------------------------------------------------------------

namespace {

OptionPrintMechanicsCensus fresh_print_census() {
  OptionPrintMechanicsCensus census;
  census.quote_attach_age_ms = DenseCounter(0, 60001);
  census.attached_spread_cents = DenseCounter(0, 1025);
  census.attached_spread_bps_of_mid = DenseCounter(0, 20001);
  census.attached_bid_size = DenseCounter(0, 1025);
  census.attached_ask_size = DenseCounter(0, 1025);
  census.size_prints = DenseCounter(0, 10001);
  census.dte_prints = DenseCounter(0, 731);
  census.dte_volume = DenseCounter(0, 731);
  census.moneyness_bps_prints = DenseCounter(-5000, 10001);
  census.moneyness_bps_volume = DenseCounter(-5000, 10001);
  census.group_size = DenseCounter(0, 4097);
  census.prints_per_second = DenseCounter(0, 65537);
  census.contract_gap_ms = DenseCounter(0, 60001);
  return census;
}

bool is_single_leg(std::int64_t condition) noexcept {
  for (const std::int64_t admitted : kSingleLegConditions) {
    if (condition == admitted) return true;
  }
  return false;
}

}  // namespace

Expected<OptionPrintMechanicsCensus, Refusal> census_option_prints(
    const DayScope& scope, const std::filesystem::path& corpus_root,
    const std::filesystem::path& tape_side_dir) {
  OptionPrintMechanicsCensus census = fresh_print_census();
  census.ordinal = scope.ordinal();
  census.day = scope.day();

  const Expected<SessionClock, Refusal> clock = SessionClock::from_session(scope.session());
  if (!clock.has_value()) {
    return Expected<OptionPrintMechanicsCensus, Refusal>::refuse(clock.error());
  }
  const std::int64_t open_ms_b = clock.value().open_b().ns() / 1000000;

  bool have_spot = false;
  SpotGrid spot;
  if (!tape_side_dir.empty()) {
    Expected<SpotGrid, Refusal> opened =
        SpotGrid::open(tape_side_dir, open_ms_b, clock.value().expected_bar_count());
    if (!opened.has_value()) {
      return Expected<OptionPrintMechanicsCensus, Refusal>::refuse(opened.error());
    }
    spot = std::move(opened).value();
    have_spot = true;
  }

  qr::parquet::FileExpected<qr::sources::OptionPrintReader> opened_reader =
      qr::sources::OptionPrintReader::open(scope, corpus_root);
  if (!opened_reader.has_value()) {
    return Expected<OptionPrintMechanicsCensus, Refusal>::refuse(opened_reader.error().refusal());
  }
  qr::sources::OptionPrintReader reader = std::move(opened_reader).value();

  std::map<ContractKey, std::int64_t> last_print_ms;
  std::map<std::int32_t, std::int64_t> expirations;
  std::int64_t current_second = -1;
  std::int64_t prints_this_second = 0;

  qr::sources::OptionPrintReader::Group group;
  while (true) {
    const qr::parquet::FileExpected<bool> more = reader.next_group(group);
    if (!more.has_value()) {
      return Expected<OptionPrintMechanicsCensus, Refusal>::refuse(more.error().refusal());
    }
    if (!more.value()) {
      break;
    }
    census.group_size.add(static_cast<std::int64_t>(group.rows.size()));
    const std::int64_t ts = group.ts_ms_b;
    const std::int64_t second = (ts - open_ms_b) / kMsPerSecond;
    if (second != current_second) {
      if (current_second >= 0) {
        census.prints_per_second.add(prints_this_second);
      }
      for (std::int64_t gap = current_second + 1; gap < second; ++gap) {
        census.prints_per_second.add(0);
      }
      current_second = second;
      prints_this_second = 0;
    }
    prints_this_second += static_cast<std::int64_t>(group.rows.size());

    const std::int64_t spot_u6 = have_spot ? spot.mid_u6_at(ts) : 0;

    for (const qr::sources::OptionPrintRow& row : group.rows) {
      switch (row.right) {
        case qr::sources::Right::Call:
          ++census.calls;
          break;
        case qr::sources::Right::Put:
          ++census.puts;
          break;
        case qr::sources::Right::Other:
          ++census.other_right;
          break;
      }
      const std::int64_t size = row.is_null(qr::sources::kPrintSlotSize) ? 0 : row.size;
      census.size_prints.add(size);
      census.total_volume += size;
      if (row.right == qr::sources::Right::Call) census.call_volume += size;
      if (row.right == qr::sources::Right::Put) census.put_volume += size;

      if (!row.is_null(qr::sources::kPrintSlotCondition)) {
        ++census.condition_prints[row.condition];
        census.condition_volume[row.condition] += size;
        if (is_single_leg(row.condition)) {
          ++census.single_leg_prints;
          census.single_leg_volume += size;
        }
      }

      if (!row.is_null(qr::sources::kPrintSlotDelta)) {
        ++census.delta_present;
        if (std::isfinite(row.delta)) ++census.delta_finite;
      }
      if (!row.is_null(qr::sources::kPrintSlotGamma)) {
        ++census.gamma_present;
        if (std::isfinite(row.gamma)) ++census.gamma_finite;
      }
      if (!row.is_null(qr::sources::kPrintSlotVanna)) ++census.vanna_present;
      if (!row.is_null(qr::sources::kPrintSlotCharm)) ++census.charm_present;
      if (!row.is_null(qr::sources::kPrintSlotImpliedVol)) {
        ++census.iv_present;
        if (std::isfinite(row.implied_vol)) ++census.iv_finite;
      }
      if (!row.is_null(qr::sources::kPrintSlotUnderlyingPrice)) ++census.underlying_px_present;
      if (row.underlying_ts_text.size > 0) ++census.underlying_ts_present;

      if (!row.is_null(qr::sources::kPrintSlotQuoteTimestamp)) {
        ++census.quote_ts_present;
        if (row.quote_ts_ms_b < ts) {
          ++census.quote_ts_strictly_prior;
          census.quote_attach_age_ms.add(ts - row.quote_ts_ms_b);
        } else if (row.quote_ts_ms_b == ts) {
          ++census.quote_ts_equal;
        } else {
          ++census.quote_ts_future;
        }
      }

      const bool attached_two_sided =
          !row.is_null(qr::sources::kPrintSlotBid) && !row.is_null(qr::sources::kPrintSlotAsk);
      if (attached_two_sided) {
        if (row.bid_u6 <= 0) ++census.attached_zero_bid;
        if (row.bid_u6 > row.ask_u6) ++census.attached_crossed;
        if (row.bid_u6 == row.ask_u6 && row.bid_u6 > 0) ++census.attached_locked;
        if (row.bid_u6 > 0 && row.ask_u6 > row.bid_u6) {
          ++census.attached_two_sided_positive;
          const std::int64_t width = row.ask_u6 - row.bid_u6;
          census.attached_spread_cents.add(width / 10000);
          const std::int64_t mid = qr::sources::midpoint_u6(row.bid_u6, row.ask_u6);
          if (mid > 0) {
            census.attached_spread_bps_of_mid.add(bps_of(width, mid));
          }
          // The recomputed aggressor side (B3: "Aggressor recomputed"), as a
          // CENSUS of decidability only — no sign is published as a feature here.
          if (!row.is_null(qr::sources::kPrintSlotPrice)) {
            if (row.price_u6 >= row.ask_u6) {
              ++census.aggressor_at_or_above_ask;
            } else if (row.price_u6 <= row.bid_u6) {
              ++census.aggressor_at_or_below_bid;
            } else {
              ++census.aggressor_inside;
            }
          } else {
            ++census.aggressor_undecidable;
          }
        }
      } else {
        ++census.aggressor_undecidable;
      }
      if (!row.is_null(qr::sources::kPrintSlotBidSize)) census.attached_bid_size.add(row.bid_size);
      if (!row.is_null(qr::sources::kPrintSlotAskSize)) census.attached_ask_size.add(row.ask_size);

      const std::int64_t dte =
          static_cast<std::int64_t>(row.expiration_day) - scope.civil_date().days_since_epoch();
      census.dte_prints.add(dte);
      census.dte_volume.add_weighted(dte, size);

      if (spot_u6 > 0) {
        const std::int64_t moneyness = bps_of(row.strike_u6 - spot_u6, spot_u6);
        census.moneyness_bps_prints.add(moneyness);
        census.moneyness_bps_volume.add_weighted(moneyness, size);
      } else if (have_spot) {
        ++census.spot_absent_rows;
      }

      const ContractKey key{row.expiration_day, row.strike_u6,
                            static_cast<std::uint8_t>(row.right)};
      auto found = last_print_ms.find(key);
      if (found == last_print_ms.end()) {
        last_print_ms.emplace(key, ts);
        ++expirations[row.expiration_day];
      } else {
        census.contract_gap_ms.add(ts - found->second);
        found->second = ts;
      }
    }
  }
  if (current_second >= 0) {
    census.prints_per_second.add(prints_this_second);
  }

  census.rth_rows = reader.rth_rows();
  census.groups = reader.group_count();
  census.skipped_null_rows = reader.skipped_null_rows();
  census.decoded_values = reader.decoded_values();
  census.contracts = static_cast<std::int64_t>(last_print_ms.size());
  census.expirations = static_cast<std::int64_t>(expirations.size());
  return census;
}

void emit(CensusReport& report, const OptionPrintMechanicsCensus& census) {
  const std::string scope = "s" + std::to_string(census.ordinal);
  report.text(scope, "session", "day", census.day);
  report.metric(scope, "stream", "rth_rows", census.rth_rows);
  report.metric(scope, "stream", "groups", census.groups);
  report.metric(scope, "stream", "skipped_null_rows", census.skipped_null_rows);
  report.metric(scope, "stream", "decoded_values", census.decoded_values);
  report.metric(scope, "stream", "contracts", census.contracts);
  report.metric(scope, "stream", "expirations", census.expirations);
  report.metric(scope, "stream", "calls", census.calls);
  report.metric(scope, "stream", "puts", census.puts);
  report.metric(scope, "stream", "other_right", census.other_right);
  report.metric(scope, "volume", "total", census.total_volume);
  report.metric(scope, "volume", "call", census.call_volume);
  report.metric(scope, "volume", "put", census.put_volume);
  report.metric(scope, "volume", "single_leg", census.single_leg_volume);
  report.metric(scope, "condition", "single_leg_prints", census.single_leg_prints);
  for (const auto& [condition, prints] : census.condition_prints) {
    report.metric(scope, "condition_prints", "code_" + std::to_string(condition), prints);
  }
  for (const auto& [condition, volume] : census.condition_volume) {
    report.metric(scope, "condition_volume", "code_" + std::to_string(condition), volume);
  }
  report.metric(scope, "greeks", "delta_present", census.delta_present);
  report.metric(scope, "greeks", "delta_finite", census.delta_finite);
  report.metric(scope, "greeks", "gamma_present", census.gamma_present);
  report.metric(scope, "greeks", "gamma_finite", census.gamma_finite);
  report.metric(scope, "greeks", "vanna_present", census.vanna_present);
  report.metric(scope, "greeks", "charm_present", census.charm_present);
  report.metric(scope, "greeks", "iv_present", census.iv_present);
  report.metric(scope, "greeks", "iv_finite", census.iv_finite);
  report.metric(scope, "greeks", "underlying_px_present", census.underlying_px_present);
  report.metric(scope, "greeks", "underlying_ts_present", census.underlying_ts_present);
  report.metric(scope, "attach", "quote_ts_present", census.quote_ts_present);
  report.metric(scope, "attach", "quote_ts_strictly_prior", census.quote_ts_strictly_prior);
  report.metric(scope, "attach", "quote_ts_equal", census.quote_ts_equal);
  report.metric(scope, "attach", "quote_ts_future", census.quote_ts_future);
  report.distribution(scope, "quote_attach_age_ms", census.quote_attach_age_ms);
  report.metric(scope, "attached_quote", "two_sided_positive", census.attached_two_sided_positive);
  report.metric(scope, "attached_quote", "zero_bid", census.attached_zero_bid);
  report.metric(scope, "attached_quote", "crossed", census.attached_crossed);
  report.metric(scope, "attached_quote", "locked", census.attached_locked);
  report.distribution(scope, "attached_spread_cents", census.attached_spread_cents);
  report.distribution(scope, "attached_spread_bps_of_mid", census.attached_spread_bps_of_mid);
  report.distribution(scope, "attached_bid_size", census.attached_bid_size);
  report.distribution(scope, "attached_ask_size", census.attached_ask_size);
  report.metric(scope, "aggressor", "at_or_above_ask", census.aggressor_at_or_above_ask);
  report.metric(scope, "aggressor", "at_or_below_bid", census.aggressor_at_or_below_bid);
  report.metric(scope, "aggressor", "inside", census.aggressor_inside);
  report.metric(scope, "aggressor", "undecidable", census.aggressor_undecidable);
  report.distribution(scope, "size_prints", census.size_prints);
  report.distribution(scope, "dte_prints", census.dte_prints);
  report.histogram(scope, "dte_prints_hist", census.dte_prints);
  report.distribution(scope, "dte_volume", census.dte_volume);
  report.distribution(scope, "moneyness_bps_prints", census.moneyness_bps_prints);
  report.distribution(scope, "moneyness_bps_volume", census.moneyness_bps_volume);
  report.distribution(scope, "group_size", census.group_size);
  report.distribution(scope, "prints_per_second", census.prints_per_second);
  report.distribution(scope, "contract_gap_ms", census.contract_gap_ms);
  report.metric(scope, "spot", "absent_rows", census.spot_absent_rows);
}

}  // namespace qr::w20
