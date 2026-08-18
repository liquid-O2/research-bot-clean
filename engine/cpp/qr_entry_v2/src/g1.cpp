#include "qr_entry_v2/g1.hpp"

#include <openssl/evp.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>
#include <map>
#include <set>
#include <sstream>
#include <string_view>
#include <tuple>
#include <utility>

#include "qr_futsess/constants.hpp"
#include "qr_futsess/sessions.hpp"

namespace qr::entry_v2 {
namespace {

namespace fs = std::filesystem;

constexpr std::uint64_t kNsPerSecond = 1'000'000'000ULL;
constexpr std::int64_t kSecondsPerDay = 86'400;
constexpr long double kRawPriceScale = 1.0e-9L;

struct EntryAssetGeometry {
  std::int64_t multiplier;
  double tick_px;
  double tick_usd;
};

// Frozen Entry V2 geometry, in qr::futsess::Asset enum order. Keeping this
// pure boundary local prevents the new lane from linking the legacy M1 stack.
constexpr std::array<EntryAssetGeometry, 3> kEntryGeometry = {{
    {5'000, 0.005, 25.0},
    {25'000, 0.0005, 12.5},
    {5, 5.0, 25.0},
}};

[[nodiscard]] const EntryAssetGeometry& entry_geometry(
    qr::futsess::Asset asset) noexcept {
  return kEntryGeometry[static_cast<std::size_t>(asset)];
}

[[nodiscard]] double round_half_up(double value, double step) noexcept {
  return std::floor(value / step + 0.5) * step;
}

[[nodiscard]] double rung_threshold_px(const EntryAssetGeometry& geometry,
                                       double rung, double atr_usd,
                                       double phase_median_spread_usd) noexcept {
  const double spread_floor = std::isfinite(phase_median_spread_usd)
                                  ? 2.0 * phase_median_spread_usd
                                  : 0.0;
  const double usd = std::max(
      {rung * atr_usd, 4.0 * geometry.tick_usd, spread_floor});
  return round_half_up(usd / static_cast<double>(geometry.multiplier),
                       geometry.tick_px);
}

[[nodiscard]] Refusal g1_content(const char* site, const char* detail,
                                 std::int64_t context = 0) {
  return Refusal(RefusalCode::CONTENT_MISMATCH, site, detail, context);
}

[[nodiscard]] Refusal g1_clock(const char* site, const char* detail,
                               std::int64_t context = 0) {
  return Refusal(RefusalCode::CLOCK_VIOLATION, site, detail, context);
}

[[nodiscard]] const char* asset_name(qr::futsess::Asset asset) {
  return qr::futsess::asset_spec(asset).name;
}

[[nodiscard]] std::int64_t raw_tick_px(qr::futsess::Asset asset) {
  switch (asset) {
    case qr::futsess::Asset::SI: return 5'000'000;
    case qr::futsess::Asset::HG: return 500'000;
    case qr::futsess::Asset::NKD: return 5'000'000'000;
  }
  return 0;
}

[[nodiscard]] bool add_i64(std::int64_t lhs, std::int64_t rhs,
                           std::int64_t* out) noexcept {
  if ((rhs > 0 && lhs > std::numeric_limits<std::int64_t>::max() - rhs) ||
      (rhs < 0 && lhs < std::numeric_limits<std::int64_t>::min() - rhs)) {
    return false;
  }
  *out = lhs + rhs;
  return true;
}

[[nodiscard]] bool sub_i64(std::int64_t lhs, std::int64_t rhs,
                           std::int64_t* out) noexcept {
  if ((rhs < 0 && lhs > std::numeric_limits<std::int64_t>::max() + rhs) ||
      (rhs > 0 && lhs < std::numeric_limits<std::int64_t>::min() + rhs)) {
    return false;
  }
  *out = lhs - rhs;
  return true;
}

[[nodiscard]] bool valid_sha256(std::string_view value) {
  return value.size() == 64u &&
         std::all_of(value.begin(), value.end(), [](char ch) {
           return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
         });
}

[[nodiscard]] std::string hex_digest(const unsigned char* digest,
                                     unsigned int length) {
  static constexpr char kHex[] = "0123456789abcdef";
  std::string out(static_cast<std::size_t>(length) * 2u, '0');
  for (unsigned int i = 0; i < length; ++i) {
    const std::size_t j = static_cast<std::size_t>(i) * 2u;
    out[j] = kHex[digest[i] >> 4u];
    out[j + 1u] = kHex[digest[i] & 0x0Fu];
  }
  return out;
}

[[nodiscard]] std::string sha256_bytes(std::string_view bytes) {
  std::array<unsigned char, EVP_MAX_MD_SIZE> digest{};
  unsigned int length = 0;
  if (EVP_Digest(bytes.data(), bytes.size(), digest.data(), &length,
                 EVP_sha256(), nullptr) != 1 ||
      length != 32u) {
    return {};
  }
  return hex_digest(digest.data(), length);
}

template <class T>
void append_le(std::string* out, T value) {
  static_assert(std::is_integral_v<T>);
  using U = std::make_unsigned_t<T>;
  U bits = static_cast<U>(value);
  for (std::size_t i = 0; i < sizeof(T); ++i) {
    out->push_back(static_cast<char>((bits >> (i * 8u)) & static_cast<U>(0xFFu)));
  }
}

[[nodiscard]] std::string canonical_event_bytes(const EventRow& row) {
  std::string out;
  out.reserve(kEventRowBytes);
  append_le(&out, row.ts_recv_ns);
  append_le(&out, row.ts_event_ns);
  append_le(&out, row.price);
  append_le(&out, row.bid_px);
  append_le(&out, row.ask_px);
  append_le(&out, row.size);
  append_le(&out, row.bid_sz);
  append_le(&out, row.ask_sz);
  append_le(&out, row.bid_ct);
  append_le(&out, row.ask_ct);
  append_le(&out, row.sequence);
  append_le(&out, row.ts_in_delta);
  append_le(&out, row.receive_session_sec);
  append_le(&out, row.action);
  append_le(&out, row.side);
  append_le(&out, row.flags);
  append_le(&out, row.depth);
  return out;
}

[[nodiscard]] Expected<std::map<std::uint64_t, std::string>, Refusal>
prefix_hashes(const EventPack& pack, const std::set<std::uint64_t>& requested) {
  std::map<std::uint64_t, std::string> out;
  if (requested.empty()) {
    return out;
  }
  if (*requested.rbegin() > pack.rows.size()) {
    return refuse<std::map<std::uint64_t, std::string>>(
        g1_content("qr_entry_v2::prefix_hashes", "candidate cutoff exceeds event pack"));
  }
  EVP_MD_CTX* context = EVP_MD_CTX_new();
  if (context == nullptr || EVP_DigestInit_ex(context, EVP_sha256(), nullptr) != 1) {
    EVP_MD_CTX_free(context);
    return refuse<std::map<std::uint64_t, std::string>>(Refusal(
        RefusalCode::IO, "qr_entry_v2::prefix_hashes", "cannot initialize SHA-256"));
  }
  // Versioned domain separator.  Keep the trailing version byte: this seed is
  // part of the candidate identity/receipt contract, not incidental text.
  std::string header("QRE2PREFIX2");
  append_le(&header, pack.header.asset_idx);
  append_le(&header, pack.header.d8);
  append_le(&header, pack.header.locked_iid);
  append_le(&header, pack.header.open_utc);
  append_le(&header, pack.header.close_utc);
  if (EVP_DigestUpdate(context, header.data(), header.size()) != 1) {
    EVP_MD_CTX_free(context);
    return refuse<std::map<std::uint64_t, std::string>>(Refusal(
        RefusalCode::IO, "qr_entry_v2::prefix_hashes", "cannot seed SHA-256"));
  }

  std::uint64_t consumed = 0;
  for (const std::uint64_t cutoff : requested) {
    while (consumed < cutoff) {
      const std::string bytes = canonical_event_bytes(
          pack.rows[static_cast<std::size_t>(consumed)]);
      if (EVP_DigestUpdate(context, bytes.data(), bytes.size()) != 1) {
        EVP_MD_CTX_free(context);
        return refuse<std::map<std::uint64_t, std::string>>(Refusal(
            RefusalCode::IO, "qr_entry_v2::prefix_hashes", "cannot update SHA-256"));
      }
      ++consumed;
    }
    EVP_MD_CTX* snapshot = EVP_MD_CTX_new();
    if (snapshot == nullptr || EVP_MD_CTX_copy_ex(snapshot, context) != 1) {
      EVP_MD_CTX_free(snapshot);
      EVP_MD_CTX_free(context);
      return refuse<std::map<std::uint64_t, std::string>>(Refusal(
          RefusalCode::IO, "qr_entry_v2::prefix_hashes", "cannot snapshot SHA-256"));
    }
    std::array<unsigned char, EVP_MAX_MD_SIZE> digest{};
    unsigned int length = 0;
    const int finalized = EVP_DigestFinal_ex(snapshot, digest.data(), &length);
    EVP_MD_CTX_free(snapshot);
    if (finalized != 1 || length != 32u) {
      EVP_MD_CTX_free(context);
      return refuse<std::map<std::uint64_t, std::string>>(Refusal(
          RefusalCode::IO, "qr_entry_v2::prefix_hashes", "cannot finalize SHA-256 snapshot"));
    }
    out.emplace(cutoff, hex_digest(digest.data(), length));
  }
  EVP_MD_CTX_free(context);
  return out;
}

[[nodiscard]] std::int64_t utc_second(std::uint64_t ts_ns) {
  return static_cast<std::int64_t>(ts_ns / kNsPerSecond);
}

[[nodiscard]] std::int64_t second_of_day(std::uint64_t ts_ns) {
  return utc_second(ts_ns) % kSecondsPerDay;
}

[[nodiscard]] std::array<std::int64_t, 3> phase_bounds(const PhaseRow& schedule) {
  return {schedule.boundaries[0], schedule.boundaries[1], schedule.boundaries[2]};
}

[[nodiscard]] std::uint8_t phase_at(std::uint64_t ts_ns, const PhaseRow& schedule) {
  return static_cast<std::uint8_t>(
      qr::futsess::phase_of(second_of_day(ts_ns), phase_bounds(schedule)));
}

struct PhaseClocks {
  std::int64_t open_utc = 0;
  std::int64_t close_utc = 0;
};

[[nodiscard]] PhaseClocks phase_clocks(std::uint64_t ts_ns, std::uint8_t phase,
                                       const PhaseRow& schedule,
                                       std::int64_t session_close_utc) {
  const std::array<std::int64_t, 3> bounds = phase_bounds(schedule);
  const std::array<std::int64_t, 3> opens = {bounds[2], bounds[0], bounds[1]};
  const std::array<std::int64_t, 3> closes = {bounds[0], bounds[1], bounds[2]};
  const std::int64_t sec = utc_second(ts_ns);
  const std::int64_t day = (sec / kSecondsPerDay) * kSecondsPerDay;
  const std::size_t p = static_cast<std::size_t>(phase);
  std::int64_t open = day + opens[p];
  if (open > sec) {
    open -= kSecondsPerDay;
  }
  std::int64_t close = day + closes[p];
  if (close <= sec) {
    close += kSecondsPerDay;
  }
  return PhaseClocks{open, std::min(close, session_close_utc)};
}

[[nodiscard]] Expected<SaneBookObservation, Refusal> classify_event_book(
    qr::futsess::Asset asset, const EventRow& row, const PhaseRow& schedule,
    const DayPriors& priors) {
  SaneBookObservation out;
  out.phase = phase_at(row.ts_recv_ns, schedule);
  const auto book = qr::futsess::classify_book(row.bid_px, row.ask_px);
  if (book.state != qr::futsess::kStTwoSided) {
    return out;
  }
  out.two_sided = true;
  if (!sub_i64(row.ask_px, row.bid_px, &out.spread_raw) || out.spread_raw <= 0) {
    return refuse<SaneBookObservation>(g1_content(
        "qr_entry_v2::classify_event_book", "two-sided BBO has invalid spread"));
  }
  const std::int64_t tick = raw_tick_px(asset);
  if (tick <= 0 || (out.spread_raw % tick) != 0) {
    return refuse<SaneBookObservation>(g1_content(
        "qr_entry_v2::classify_event_book", "BBO spread is off the asset tick grid",
        out.spread_raw));
  }
  out.spread_ticks = out.spread_raw / tick;
  if (!add_i64(row.bid_px, row.ask_px, &out.mid2)) {
    return refuse<SaneBookObservation>(Refusal(
        RefusalCode::ARITHMETIC_OVERFLOW, "qr_entry_v2::classify_event_book",
        "int64 mid2 overflow"));
  }
  const EntryAssetGeometry& geom = entry_geometry(asset);
  out.spread_usd = static_cast<double>(
      static_cast<long double>(out.spread_raw) * kRawPriceScale *
      static_cast<long double>(geom.multiplier));
  const double ceiling = priors.phase[static_cast<std::size_t>(out.phase)].sane_ceiling_usd;
  out.sane = std::isfinite(out.spread_usd) && out.spread_usd <= ceiling;
  return out;
}

[[nodiscard]] Expected<std::int64_t, Refusal> threshold_mid2_raw(
    qr::futsess::Asset asset, double rung, double atr14_usd,
    const PhaseSpreadPrior& spread_prior) {
  const EntryAssetGeometry& geom = entry_geometry(asset);
  const double median = spread_prior.present
                            ? spread_prior.median_spread_usd
                            : std::numeric_limits<double>::quiet_NaN();
  const double threshold_px = rung_threshold_px(
      geom, rung, atr14_usd, median);
  const long double raw = static_cast<long double>(threshold_px) /
                          kRawPriceScale * 2.0L;
  if (!std::isfinite(threshold_px) || threshold_px <= 0.0 ||
      raw > static_cast<long double>(std::numeric_limits<std::int64_t>::max())) {
    return refuse<std::int64_t>(g1_content(
        "qr_entry_v2::threshold_mid2_raw", "invalid G1 rung threshold"));
  }
  return static_cast<std::int64_t>(std::llround(raw));
}

struct EventKey {
  std::uint64_t ts_recv_ns = 0;
  std::uint64_t ordinal = 0;

  friend bool operator<(const EventKey& lhs, const EventKey& rhs) {
    return std::tie(lhs.ts_recv_ns, lhs.ordinal) <
           std::tie(rhs.ts_recv_ns, rhs.ordinal);
  }
};

struct RawZigZag {
  bool initialized = false;
  std::int64_t high = 0;
  std::int64_t low = 0;
  EventKey high_key{};
  EventKey low_key{};
  std::int8_t direction = 0;

  [[nodiscard]] std::optional<std::int8_t> observe(
      std::int64_t mid2, EventKey key, std::int64_t threshold) {
    if (!initialized) {
      initialized = true;
      high = low = mid2;
      high_key = low_key = key;
      return std::nullopt;
    }
    if (direction == 1) {
      if (mid2 > high) {
        high = mid2;
        high_key = key;
      } else if (high - mid2 >= threshold) {
        direction = -1;
        low = mid2;
        low_key = key;
        return static_cast<std::int8_t>(-1);
      }
      return std::nullopt;
    }
    if (direction == -1) {
      if (mid2 < low) {
        low = mid2;
        low_key = key;
      } else if (mid2 - low >= threshold) {
        direction = 1;
        high = mid2;
        high_key = key;
        return static_cast<std::int8_t>(1);
      }
      return std::nullopt;
    }
    if (mid2 > high) {
      high = mid2;
      high_key = key;
    }
    if (mid2 < low) {
      low = mid2;
      low_key = key;
    }
    bool down = high - mid2 >= threshold;
    bool up = mid2 - low >= threshold;
    if (down && up) {
      // Exact event identity extends the audited second-level tie law.
      if (!(low_key < high_key)) {
        up = false;  // HIGH wins an exact key tie.
      } else {
        down = false;
      }
    }
    if (down) {
      direction = -1;
      low = mid2;
      low_key = key;
      return static_cast<std::int8_t>(-1);
    }
    if (up) {
      direction = 1;
      high = mid2;
      high_key = key;
      return static_cast<std::int8_t>(1);
    }
    return std::nullopt;
  }
};

struct SaneObservation {
  std::uint64_t ordinal = 0;
  std::uint64_t ts_recv_ns = 0;
  std::uint64_t book_generation = 0;
  std::int64_t bid_px = 0;
  std::int64_t ask_px = 0;
  std::int64_t mid2 = 0;
  double spread_usd = 0.0;
};

[[nodiscard]] std::string candidate_id_impl(const CandidateRow& row) {
  std::ostringstream out;
  out << "QRE2CANDID2|" << asset_name(row.asset) << '|' << row.d8 << '|'
      << row.decision_ts_ns << '|' << row.confirmation_event_ordinal << '|'
      << static_cast<int>(row.side) << '|' << row.event_pack_sha256 << '|'
      << row.prefix_sha256 << '|' << row.clock_law_receipt_sha256;
  return "QRE2V2-" + sha256_bytes(out.str());
}

[[nodiscard]] std::string candidate_lineage_impl(const CandidateRow& row) {
  std::ostringstream out;
  out << std::setprecision(std::numeric_limits<double>::max_digits10)
      << "QRE2CAND2|" << row.candidate_id << '|' << row.locked_iid << '|'
      << row.selection_basis_d8 << '|' << row.confirmation_ts_recv_ns << '|'
      << row.confirmation_event_ordinal << '|' << row.decision_ts_ns << '|'
      << static_cast<int>(row.side) << '|' << static_cast<int>(row.phase) << '|'
      << static_cast<int>(row.rung_mask) << '|' << static_cast<int>(row.delay) << '|'
      << row.phase_open_utc << '|' << row.phase_close_utc << '|' << row.event_cutoff
      << '|' << row.event_pack_sha256 << '|' << row.prefix_sha256 << '|'
      << row.clock_law_receipt_sha256 << '|' << row.entry_bid_px << '|' << row.entry_ask_px
      << '|' << row.entry_mid2 << '|' << row.entry_spread_usd << '|'
      << row.frozen_cost_usd << '|' << row.atr14_prev_usd << '|'
      << row.spread_prior_present << '|' << row.spread_prior_usd << '|'
      << row.sane_ceiling_usd << '|' << static_cast<int>(row.compliance) << '|'
      << row.compliance_distance_sec << '|' << row.compliance_artifact_sha256;
  return sha256_bytes(out.str());
}

[[nodiscard]] double exact_net_value(qr::futsess::Asset asset,
                                     std::int8_t side,
                                     std::int64_t entry_mid2,
                                     std::int64_t current_mid2,
                                     double frozen_cost_usd) {
  const EntryAssetGeometry& geom = entry_geometry(asset);
  const long double delta_mid2 = static_cast<long double>(current_mid2) -
                                 static_cast<long double>(entry_mid2);
  const long double gross = static_cast<long double>(side) * delta_mid2 * 0.5L *
                            kRawPriceScale *
                            static_cast<long double>(geom.multiplier);
  return static_cast<double>(gross - static_cast<long double>(frozen_cost_usd));
}

[[nodiscard]] Expected<std::monostate, Refusal> validate_teacher_inputs(
    qr::futsess::Asset asset, const EventPack& pack,
    const std::vector<CandidateRow>& candidates) {
  if (pack.header.asset_idx != static_cast<std::uint8_t>(asset)) {
    return refuse<std::monostate>(g1_content(
        "qr_entry_v2::certify_teacher", "event pack asset differs from teacher asset"));
  }
  std::set<std::string> ids;
  for (const CandidateRow& row : candidates) {
    if (row.asset != asset || row.d8 != pack.header.d8 ||
        row.locked_iid != pack.header.locked_iid || !ids.insert(row.candidate_id).second) {
      return refuse<std::monostate>(g1_content(
          "qr_entry_v2::certify_teacher", "candidate/event-pack key mismatch"));
    }
    if (row.event_cutoff != event_cutoff(pack.rows, row.decision_ts_ns)) {
      return refuse<std::monostate>(g1_clock(
          "qr_entry_v2::certify_teacher", "stored cutoff is not exact lower_bound"));
    }
  }
  return std::monostate{};
}

struct Plan {
  bool valid = false;
  long double value = 0.0L;
  std::vector<std::size_t> picks;
};

[[nodiscard]] bool plan_better(const Plan& lhs, const Plan& rhs,
                               const std::vector<const TeacherRow*>& rows) {
  if (!lhs.valid) return false;
  if (!rhs.valid) return true;
  if (lhs.value != rhs.value) return lhs.value > rhs.value;
  std::vector<std::string_view> li;
  std::vector<std::string_view> ri;
  li.reserve(lhs.picks.size());
  ri.reserve(rhs.picks.size());
  for (std::size_t index : lhs.picks) li.emplace_back(rows[index]->candidate_id);
  for (std::size_t index : rhs.picks) ri.emplace_back(rows[index]->candidate_id);
  std::sort(li.begin(), li.end());
  std::sort(ri.begin(), ri.end());
  return li < ri;
}

struct AssetPlans {
  std::vector<const TeacherRow*> rows;
  std::vector<Plan> exact;
};

[[nodiscard]] AssetPlans make_asset_plans(std::vector<const TeacherRow*> rows,
                                          std::size_t cap,
                                          ScheduleUniverse universe) {
  rows.erase(std::remove_if(rows.begin(), rows.end(), [universe](const TeacherRow* row) {
               return row->status != TeacherStatus::READY || !(row->cert_close_usd > 0.0) ||
                      (universe == ScheduleUniverse::DEPLOYABLE_CLEAR_ONLY &&
                       row->compliance != ComplianceStatus::CLEAR);
             }), rows.end());
  std::sort(rows.begin(), rows.end(), [](const TeacherRow* lhs, const TeacherRow* rhs) {
    return std::tie(lhs->exit_ts_ns, lhs->decision_ts_ns, lhs->candidate_id) <
           std::tie(rhs->exit_ts_ns, rhs->decision_ts_ns, rhs->candidate_id);
  });
  const std::size_t n = rows.size();
  std::vector<std::uint64_t> exits;
  exits.reserve(n);
  for (const TeacherRow* row : rows) exits.push_back(row->exit_ts_ns);
  std::vector<std::size_t> pred(n, 0);
  for (std::size_t i = 0; i < n; ++i) {
    pred[i] = static_cast<std::size_t>(
        std::lower_bound(exits.begin(), exits.begin() + static_cast<std::ptrdiff_t>(i),
                         rows[i]->decision_ts_ns) - exits.begin());
  }
  std::vector<std::vector<Plan>> dp(n + 1u, std::vector<Plan>(cap + 1u));
  dp[0][0].valid = true;
  for (std::size_t i = 1; i <= n; ++i) {
    for (std::size_t k = 0; k <= cap; ++k) {
      dp[i][k] = dp[i - 1u][k];
      if (k == 0 || !dp[pred[i - 1u]][k - 1u].valid) continue;
      Plan take = dp[pred[i - 1u]][k - 1u];
      take.value += static_cast<long double>(rows[i - 1u]->cert_close_usd);
      take.picks.push_back(i - 1u);
      if (plan_better(take, dp[i][k], rows)) dp[i][k] = std::move(take);
    }
  }
  AssetPlans result;
  result.rows = std::move(rows);
  result.exact.resize(cap + 1u);
  for (std::size_t k = 0; k <= cap; ++k) result.exact[k] = dp[n][k];
  return result;
}

[[nodiscard]] Expected<std::monostate, Refusal> validate_schedule_inputs(
    const std::vector<TeacherRow>& teacher,
    const std::vector<ExpectedSession>& expected_sessions) {
  if (expected_sessions.empty()) {
    return refuse<std::monostate>(Refusal(
        RefusalCode::CONFIG, "qr_entry_v2::schedule", "expected-session denominator is empty"));
  }
  std::set<ExpectedSession> expected;
  for (const ExpectedSession& session : expected_sessions) {
    if (session.d8 < kDevelopmentStartD8 ||
        session.d8 >= kDevelopmentEndD8Exclusive || !expected.insert(session).second) {
      return refuse<std::monostate>(g1_content(
          "qr_entry_v2::schedule", "invalid or duplicate expected session", session.d8));
    }
  }
  std::set<std::string> ids;
  for (const TeacherRow& row : teacher) {
    if (!ids.insert(row.candidate_id).second ||
        expected.find(ExpectedSession{row.asset, row.d8}) == expected.end()) {
      return refuse<std::monostate>(g1_content(
          "qr_entry_v2::schedule", "duplicate candidate or candidate outside denominator"));
    }
    if (row.status == TeacherStatus::READY &&
        (!std::isfinite(row.cert_close_usd) || row.exit_ts_ns < row.decision_ts_ns)) {
      return refuse<std::monostate>(g1_content(
          "qr_entry_v2::schedule", "invalid ready teacher interval/value"));
    }
  }
  return std::monostate{};
}

void finish_schedule_metrics(ScheduleResult* result,
                             const std::vector<TeacherRow>& teacher,
                             const std::vector<ExpectedSession>& expected_sessions) {
  std::map<std::string, const TeacherRow*> by_id;
  for (const TeacherRow& row : teacher) by_id.emplace(row.candidate_id, &row);
  std::map<ExpectedSession, std::uint64_t> session_takes;
  for (const ExpectedSession& session : expected_sessions) session_takes.emplace(session, 0u);
  long double total = 0.0L;
  std::uint64_t count = 0;
  for (const auto& [id, selected] : result->selected) {
    if (!selected) continue;
    const TeacherRow& row = *by_id.at(id);
    total += static_cast<long double>(row.cert_close_usd);
    ++count;
    ++session_takes[ExpectedSession{row.asset, row.d8}];
  }
  result->total_usd = static_cast<double>(total);
  result->selected_count = count;
  result->expected_sessions = expected_sessions.size();
  result->zero_sessions = static_cast<std::uint64_t>(std::count_if(
      session_takes.begin(), session_takes.end(),
      [](const auto& item) { return item.second == 0u; }));
  result->usd_per_session = result->total_usd /
                            static_cast<double>(result->expected_sessions);
}

}  // namespace

std::string g1_candidate_id(const CandidateRow& row) {
  return candidate_id_impl(row);
}

std::string g1_candidate_lineage(const CandidateRow& row) {
  return candidate_lineage_impl(row);
}

Expected<std::monostate, Refusal> validate_candidate_prefixes(
    const EventPack& pack, const std::vector<CandidateRow>& candidates) {
  const std::string pack_sha = event_pack_sha256(pack);
  if (!valid_sha256(pack_sha)) {
    return refuse<std::monostate>(g1_content(
        "qr_entry_v2::validate_candidate_prefixes", "event pack has no valid identity"));
  }
  std::set<std::uint64_t> cutoffs;
  for (const CandidateRow& row : candidates) {
    if (row.event_cutoff == 0u || row.event_cutoff > pack.rows.size()) {
      return refuse<std::monostate>(g1_content(
          "qr_entry_v2::validate_candidate_prefixes", "candidate cutoff is outside pack"));
    }
    cutoffs.insert(row.event_cutoff);
  }
  auto hashes = prefix_hashes(pack, cutoffs);
  if (!hashes) return refuse<std::monostate>(hashes.error());
  for (const CandidateRow& row : candidates) {
    if (row.d8 != pack.header.d8 || row.locked_iid != pack.header.locked_iid ||
        row.event_pack_sha256 != pack_sha ||
        row.clock_law_receipt_sha256 != kClockLawReceiptSha256 ||
        row.event_cutoff != event_cutoff(pack.rows, row.decision_ts_ns) ||
        row.prefix_last_event_ordinal != row.event_cutoff - 1u ||
        row.prefix_last_availability_ts_ns !=
            pack.rows[static_cast<std::size_t>(row.event_cutoff - 1u)].ts_recv_ns ||
        row.prefix_sha256 != hashes.value().at(row.event_cutoff) ||
        row.candidate_id != candidate_id_impl(row) ||
        row.lineage_sha256 != candidate_lineage_impl(row)) {
      return refuse<std::monostate>(g1_content(
          "qr_entry_v2::validate_candidate_prefixes",
          "candidate identity/prefix/lineage does not recompute"));
    }
  }
  return std::monostate{};
}

Expected<SaneBookObservation, Refusal> classify_sane_book(
    qr::futsess::Asset asset, const EventRow& row, const PhaseRow& schedule,
    const DayPriors& priors) {
  return classify_event_book(asset, row, schedule, priors);
}

const char* candidate_session_status_name(CandidateSessionStatus status) noexcept {
  switch (status) {
    case CandidateSessionStatus::READY: return "READY";
    case CandidateSessionStatus::NO_ATR14: return "NO_ATR14";
    case CandidateSessionStatus::NO_LOCK: return "NO_LOCK";
    case CandidateSessionStatus::NO_EVENTS: return "NO_EVENTS";
    case CandidateSessionStatus::NO_SANE_BBO: return "NO_SANE_BBO";
  }
  return "UNKNOWN";
}

const char* candidate_delay_name(CandidateDelay delay) noexcept {
  switch (delay) {
    case CandidateDelay::STANDARD_120: return "STANDARD_120";
    case CandidateDelay::FAST_OPEN_15: return "FAST_OPEN_15";
  }
  return "UNKNOWN";
}

const char* compliance_status_name(ComplianceStatus status) noexcept {
  switch (status) {
    case ComplianceStatus::CLEAR: return "CLEAR";
    case ComplianceStatus::PROHIBITED: return "PROHIBITED";
    case ComplianceStatus::COMPLIANCE_UNKNOWN: return "COMPLIANCE_UNKNOWN";
  }
  return "UNKNOWN";
}

const char* teacher_status_name(TeacherStatus status) noexcept {
  switch (status) {
    case TeacherStatus::READY: return "READY";
    case TeacherStatus::NO_SANE_SUFFIX: return "NO_SANE_SUFFIX";
  }
  return "UNKNOWN";
}

CausalPriorState::CausalPriorState(qr::futsess::Asset asset) : asset_(asset) {}

Expected<DayPriors, Refusal> CausalPriorState::snapshot(std::int32_t d8) const {
  if (d8 < kDevelopmentStartD8 || d8 >= kDevelopmentEndD8Exclusive ||
      (last_committed_d8_ >= 0 && d8 <= last_committed_d8_)) {
    return refuse<DayPriors>(g1_clock(
        "qr_entry_v2::CausalPriorState::snapshot",
        "snapshot must be an uncommitted development day", d8));
  }
  DayPriors out;
  out.d8 = d8;
  out.atr14_present = atr_after_.has_value();
  out.atr14_prev_usd = atr_after_.has_value()
                               ? static_cast<double>(*atr_after_)
                               : std::numeric_limits<double>::quiet_NaN();
  for (std::size_t p = 0; p < out.phase.size(); ++p) {
    PhaseSpreadPrior& prior = out.phase[p];
    prior.completed_sessions = static_cast<std::uint32_t>(spread_sessions_.size());
    const auto& hist = spread_pool_[p];
    std::uint64_t n = 0;
    for (const auto& [ticks, count] : hist) {
      (void)ticks;
      if (std::numeric_limits<std::uint64_t>::max() - n < count) {
        return refuse<DayPriors>(Refusal(
            RefusalCode::ARITHMETIC_OVERFLOW,
            "qr_entry_v2::CausalPriorState::snapshot", "spread histogram overflow"));
      }
      n += count;
    }
    prior.observations = n;
    if (n == 0) {
      prior.present = false;
      prior.median_spread_usd = std::numeric_limits<double>::quiet_NaN();
      prior.sane_ceiling_usd = kSaneSpreadCapUsd;
      continue;
    }
    const std::uint64_t lo_rank = (n - 1u) / 2u;
    const std::uint64_t hi_rank = n / 2u;
    std::uint64_t cumulative = 0;
    std::int64_t lo_ticks = 0;
    std::int64_t hi_ticks = 0;
    bool have_lo = false;
    for (const auto& [ticks, count] : hist) {
      const std::uint64_t next = cumulative + count;
      if (!have_lo && lo_rank < next) {
        lo_ticks = ticks;
        have_lo = true;
      }
      if (hi_rank < next) {
        hi_ticks = ticks;
        break;
      }
      cumulative = next;
    }
    const EntryAssetGeometry& geom = entry_geometry(asset_);
    const long double median_ticks =
        (static_cast<long double>(lo_ticks) + static_cast<long double>(hi_ticks)) / 2.0L;
    prior.present = true;
    prior.median_spread_usd = static_cast<double>(
        median_ticks * static_cast<long double>(geom.tick_usd));
    prior.sane_ceiling_usd = std::min(
        kSaneSpreadMultiple * prior.median_spread_usd, kSaneSpreadCapUsd);
  }
  return out;
}

Expected<std::monostate, Refusal> CausalPriorState::commit(
    const CompletedSessionInput& completed) {
  if (completed.d8 < kDevelopmentStartD8 ||
      completed.d8 >= kDevelopmentEndD8Exclusive ||
      (last_committed_d8_ >= 0 && completed.d8 <= last_committed_d8_)) {
    return refuse<std::monostate>(g1_clock(
        "qr_entry_v2::CausalPriorState::commit",
        "completed sessions must be strictly chronological development days",
        completed.d8));
  }

  for (std::size_t p = 0; p < spread_pool_.size(); ++p) {
    for (const auto& [ticks, count] : completed.phase_spread_ticks[p]) {
      if (ticks < 0 || count == 0u ||
          std::numeric_limits<std::uint64_t>::max() - spread_pool_[p][ticks] < count) {
        return refuse<std::monostate>(g1_content(
            "qr_entry_v2::CausalPriorState::commit", "invalid spread histogram"));
      }
      spread_pool_[p][ticks] += count;
    }
  }
  spread_sessions_.push_back(completed.phase_spread_ticks);
  if (spread_sessions_.size() > kSpreadPriorSessions) {
    const auto& expired = spread_sessions_.front();
    for (std::size_t p = 0; p < spread_pool_.size(); ++p) {
      for (const auto& [ticks, count] : expired[p]) {
        auto found = spread_pool_[p].find(ticks);
        if (found == spread_pool_[p].end() || found->second < count) {
          return refuse<std::monostate>(g1_content(
              "qr_entry_v2::CausalPriorState::commit", "spread pool underflow"));
        }
        found->second -= count;
        if (found->second == 0u) spread_pool_[p].erase(found);
      }
    }
    spread_sessions_.pop_front();
  }

  if (completed.bar_present) {
    if (completed.locked_iid < 0 ||
        completed.bar_high_mid2 < completed.bar_low_mid2 ||
        completed.bar_close_mid2 < completed.bar_low_mid2 ||
        completed.bar_close_mid2 > completed.bar_high_mid2) {
      return refuse<std::monostate>(g1_content(
          "qr_entry_v2::CausalPriorState::commit", "invalid completed session bar"));
    }
    long double tr_mid2 = static_cast<long double>(completed.bar_high_mid2) -
                          static_cast<long double>(completed.bar_low_mid2);
    const bool continuous = have_last_bar_ &&
                            completed.locked_iid == last_bar_iid_ &&
                            completed.session_ordinal == last_bar_session_ordinal_ + 1u;
    if (continuous) {
      tr_mid2 = std::max(
          {tr_mid2,
           std::fabs(static_cast<long double>(completed.bar_high_mid2) -
                     static_cast<long double>(last_bar_close_mid2_)),
           std::fabs(static_cast<long double>(completed.bar_low_mid2) -
                     static_cast<long double>(last_bar_close_mid2_))});
    }
    const EntryAssetGeometry& geom = entry_geometry(asset_);
    const long double tr_usd = tr_mid2 * 0.5L * kRawPriceScale *
                               static_cast<long double>(geom.multiplier);
    if (!(tr_usd >= 0.0L) || !std::isfinite(static_cast<double>(tr_usd))) {
      return refuse<std::monostate>(g1_content(
          "qr_entry_v2::CausalPriorState::commit", "non-finite true range"));
    }
    ++tr_count_;
    if (tr_count_ <= kAtrPeriod) {
      atr_seed_sum_ += tr_usd;
      if (tr_count_ == kAtrPeriod) {
        atr_after_ = atr_seed_sum_ / static_cast<long double>(kAtrPeriod);
      }
    } else {
      if (!atr_after_.has_value()) {
        return refuse<std::monostate>(g1_content(
            "qr_entry_v2::CausalPriorState::commit", "ATR state lost its seed"));
      }
      atr_after_ = (*atr_after_ * static_cast<long double>(kAtrPeriod - 1u) + tr_usd) /
                   static_cast<long double>(kAtrPeriod);
    }
    have_last_bar_ = true;
    last_bar_session_ordinal_ = completed.session_ordinal;
    last_bar_iid_ = completed.locked_iid;
    last_bar_close_mid2_ = completed.bar_close_mid2;
  }
  last_committed_d8_ = completed.d8;
  return std::monostate{};
}

Expected<CandidateSession, Refusal> generate_g1_candidates(
    qr::futsess::Asset asset, const LockRow& lock, const PhaseRow& schedule,
    const EventPack& pack, const DayPriors& priors, std::size_t session_ordinal) {
  if (std::memcmp(pack.header.magic, "QRE2EVT2", 8) != 0 ||
      pack.header.version != 2u || pack.header.row_bytes != kEventRowBytes) {
    return refuse<CandidateSession>(g1_content(
        "qr_entry_v2::generate_g1_candidates", "QRE2EVT2 pack is required"));
  }
  if (lock.d8 != pack.header.d8 || lock.d8 != priors.d8 ||
      pack.header.asset_idx != static_cast<std::uint8_t>(asset) ||
      lock.d8 < kDevelopmentStartD8 || lock.d8 >= kDevelopmentEndD8Exclusive) {
    return refuse<CandidateSession>(g1_content(
        "qr_entry_v2::generate_g1_candidates", "session key or development wall mismatch"));
  }
  if (schedule.month != lock.d8 / 100) {
    return refuse<CandidateSession>(g1_content(
        "qr_entry_v2::generate_g1_candidates", "phase schedule month mismatch"));
  }
  if (pack.header.open_utc != lock.open_utc || pack.header.close_utc != lock.close_utc ||
      pack.header.locked_iid != lock.locked_iid) {
    return refuse<CandidateSession>(g1_content(
        "qr_entry_v2::generate_g1_candidates", "event pack differs from causal lock"));
  }

  CandidateSession result;
  result.priors = priors;
  result.completed.d8 = lock.d8;
  result.completed.locked_iid = lock.locked_iid;
  result.completed.session_ordinal = session_ordinal;
  result.raw_events = pack.rows.size();
  if (lock.status != LockStatus::LOCKED || lock.locked_iid < 0) {
    result.status = CandidateSessionStatus::NO_LOCK;
    return result;
  }
  if (pack.rows.empty()) {
    result.status = CandidateSessionStatus::NO_EVENTS;
    return result;
  }

  std::array<std::array<std::int64_t, kG1RungCount>, 3> thresholds{};
  if (priors.atr14_present) {
    for (std::size_t p = 0; p < thresholds.size(); ++p) {
      for (std::size_t r = 0; r < kG1RungCount; ++r) {
        auto threshold = threshold_mid2_raw(asset, kG1Rungs[r],
                                            priors.atr14_prev_usd, priors.phase[p]);
        if (!threshold) return refuse<CandidateSession>(threshold.error());
        thresholds[p][r] = threshold.value();
      }
    }
  }

  std::array<RawZigZag, kG1RungCount> machines{};
  std::map<std::tuple<std::uint64_t, std::uint64_t, std::int8_t, std::uint64_t>,
           std::uint8_t>
      confirmations;
  std::vector<SaneObservation> sane;
  sane.reserve(pack.rows.size());
  std::set<std::int64_t> sane_seconds;
  bool have_bar = false;
  std::int64_t bar_high = 0;
  std::int64_t bar_low = 0;
  std::int64_t bar_close = 0;
  std::uint64_t previous_ts_recv = 0;
  bool have_previous = false;
  BookQualityState book_quality;
  bool book_tainted = false;
  bool awaiting_snapshot_seed = false;
  bool prefix_book_trusted = false;
  std::vector<std::uint64_t> prefix_generation(pack.rows.size() + 1u, 0u);
  std::vector<bool> prefix_trusted(pack.rows.size() + 1u, false);

  for (std::size_t i = 0; i < pack.rows.size(); ++i) {
    const EventRow& row = pack.rows[i];
    if (have_previous && row.ts_recv_ns < previous_ts_recv) {
      return refuse<CandidateSession>(Refusal(
          RefusalCode::OUT_OF_ORDER, "qr_entry_v2::generate_g1_candidates",
          "event pack receive timestamps are decreasing"));
    }
    previous_ts_recv = row.ts_recv_ns;
    have_previous = true;
    auto observed = classify_event_book(asset, row, schedule, priors);
    if (!observed) return refuse<CandidateSession>(observed.error());
    auto quality = book_quality.observe(row.ts_recv_ns, row.flags,
                                       observed.value().two_sided);
    if (!quality) return refuse<CandidateSession>(quality.error());
    const BookQualityDecision& decision = quality.value();
    if (decision.reset_derived_state) {
      machines = {};
      sane.clear();
      sane_seconds.clear();
      have_bar = false;
      bar_high = bar_low = bar_close = 0;
      result.two_sided_events = 0;
      result.sane_events = 0;
      result.completed.phase_spread_ticks = {};
    }
    if (decision.maybe_bad_book_row) {
      book_tainted = true;
      awaiting_snapshot_seed = false;
      prefix_book_trusted = false;
    } else if (decision.reset_derived_state) {
      book_tainted = false;
      awaiting_snapshot_seed = true;
      prefix_book_trusted = false;
    } else if (!decision.snapshot_row && observed.value().two_sided &&
               !book_tainted) {
      // The first sane ordinary row after a clean snapshot seeds book trust
      // but remains non-economic; later rows in the generation are eligible.
      prefix_book_trusted = true;
      awaiting_snapshot_seed = false;
    }
    prefix_generation[i + 1u] = decision.generation;
    prefix_trusted[i + 1u] = prefix_book_trusted && !book_tainted &&
                             !awaiting_snapshot_seed;
    if (!decision.trusted_economic) continue;
    if (!observed.value().two_sided) continue;
    ++result.two_sided_events;
    ++result.completed.phase_spread_ticks[observed.value().phase]
                                                [observed.value().spread_ticks];
    if (!observed.value().sane) continue;
    ++result.sane_events;
    sane_seconds.insert(utc_second(row.ts_recv_ns));
    sane.push_back(SaneObservation{static_cast<std::uint64_t>(i), row.ts_recv_ns,
                                   decision.generation,
                                   row.bid_px, row.ask_px,
                                   observed.value().mid2,
                                   observed.value().spread_usd});
    if (!have_bar) {
      have_bar = true;
      bar_high = bar_low = bar_close = observed.value().mid2;
    } else {
      bar_high = std::max(bar_high, observed.value().mid2);
      bar_low = std::min(bar_low, observed.value().mid2);
      bar_close = observed.value().mid2;
    }
    if (!priors.atr14_present) continue;
    const EventKey key{row.ts_recv_ns, static_cast<std::uint64_t>(i)};
    for (std::size_t r = 0; r < machines.size(); ++r) {
      const auto side = machines[r].observe(
          observed.value().mid2, key, thresholds[observed.value().phase][r]);
      if (side.has_value()) {
        confirmations[{row.ts_recv_ns, static_cast<std::uint64_t>(i), *side,
                       decision.generation}] |=
            static_cast<std::uint8_t>(1u << r);
      }
    }
  }
  if (book_quality.unresolved_taint()) {
    result.completed.phase_spread_ticks = {};
    result.candidates.clear();
    result.confirmations = 0;
    result.two_sided_events = 0;
    result.sane_events = 0;
    result.status = CandidateSessionStatus::NO_SANE_BBO;
    return result;
  }
  if (have_bar && sane_seconds.size() >= kMinBarDistinctSeconds) {
    result.completed.bar_present = true;
    result.completed.bar_high_mid2 = bar_high;
    result.completed.bar_low_mid2 = bar_low;
    result.completed.bar_close_mid2 = bar_close;
  }
  if (!priors.atr14_present) {
    result.status = CandidateSessionStatus::NO_ATR14;
    return result;
  }
  if (sane.empty()) {
    result.status = CandidateSessionStatus::NO_SANE_BBO;
    return result;
  }

  result.confirmations = confirmations.size();
  std::map<std::tuple<std::uint64_t, std::uint64_t, std::int8_t>, CandidateRow> emitted;
  const std::uint64_t close_ns = static_cast<std::uint64_t>(lock.close_utc) * kNsPerSecond;
  for (const auto& [key, rung_mask] : confirmations) {
    const auto [confirmation_ts, confirmation_ordinal, side,
                confirmation_generation] = key;
    const std::uint8_t confirmation_phase = phase_at(confirmation_ts, schedule);
    const PhaseClocks confirmation_clocks = phase_clocks(
        confirmation_ts, confirmation_phase, schedule, lock.close_utc);
    const std::uint64_t confirmation_phase_open_ns =
        static_cast<std::uint64_t>(confirmation_clocks.open_utc) * kNsPerSecond;
    const bool fast_open = confirmation_ts >= confirmation_phase_open_ns &&
                           confirmation_ts < confirmation_phase_open_ns +
                               static_cast<std::uint64_t>(kG1FastOpenWindowSec) * kNsPerSecond;
    const std::array<CandidateDelay, 2> delay_kinds = {
        CandidateDelay::STANDARD_120, CandidateDelay::FAST_OPEN_15};
    for (const CandidateDelay delay : delay_kinds) {
      if (delay == CandidateDelay::FAST_OPEN_15 && !fast_open) continue;
      const std::int32_t delay_sec = delay == CandidateDelay::STANDARD_120
                                         ? kG1StandardDelaySec
                                         : kG1FastOpenDelaySec;
      const std::uint64_t delta = static_cast<std::uint64_t>(delay_sec) * kNsPerSecond;
      if (confirmation_ts > std::numeric_limits<std::uint64_t>::max() - delta) {
        return refuse<CandidateSession>(Refusal(
            RefusalCode::ARITHMETIC_OVERFLOW, "qr_entry_v2::generate_g1_candidates",
            "decision timestamp overflow"));
      }
      const std::uint64_t decision_ts = confirmation_ts + delta;
      if (decision_ts >= close_ns) {
        ++result.skipped_past_close;
        continue;
      }
      const std::size_t cutoff = event_cutoff(pack.rows, decision_ts);
      if (cutoff == 0u || prefix_generation[cutoff] != confirmation_generation ||
          !prefix_trusted[cutoff]) {
        ++result.skipped_no_strict_prefix_bbo;
        continue;
      }
      const auto entry_it = std::lower_bound(
          sane.begin(), sane.end(), static_cast<std::uint64_t>(cutoff),
          [](const SaneObservation& observation, std::uint64_t ordinal) {
            return observation.ordinal < ordinal;
          });
      if (entry_it == sane.begin()) {
        ++result.skipped_no_strict_prefix_bbo;
        continue;
      }
      auto matching_entry = entry_it;
      do {
        --matching_entry;
        if (matching_entry->book_generation == confirmation_generation) break;
      } while (matching_entry != sane.begin());
      if (matching_entry->book_generation != confirmation_generation) {
        ++result.skipped_no_strict_prefix_bbo;
        continue;
      }
      const SaneObservation& entry = *matching_entry;
      if (entry.ts_recv_ns >= decision_ts) {
        return refuse<CandidateSession>(g1_clock(
            "qr_entry_v2::generate_g1_candidates",
            "strict-prefix BBO is not strictly before decision"));
      }
      const std::uint8_t decision_phase = phase_at(decision_ts, schedule);
      const PhaseClocks decision_clocks = phase_clocks(
          decision_ts, decision_phase, schedule, lock.close_utc);
      if (decision_clocks.close_utc * static_cast<std::int64_t>(kNsPerSecond) <=
          static_cast<std::int64_t>(decision_ts)) {
        ++result.skipped_past_close;
        continue;
      }
      CandidateRow candidate;
      candidate.asset = asset;
      candidate.d8 = lock.d8;
      candidate.locked_iid = lock.locked_iid;
      candidate.selection_basis_d8 = lock.selection_basis_d8;
      candidate.confirmation_ts_recv_ns = confirmation_ts;
      candidate.confirmation_event_ordinal = confirmation_ordinal;
      candidate.decision_ts_ns = decision_ts;
      candidate.decision_sec = static_cast<std::int32_t>(
          utc_second(decision_ts) - lock.open_utc);
      candidate.side = side;
      candidate.phase = decision_phase;
      candidate.rung_mask = rung_mask;
      candidate.delay = delay;
      candidate.phase_open_utc = decision_clocks.open_utc;
      candidate.phase_close_utc = decision_clocks.close_utc;
      candidate.event_cutoff = cutoff;
      candidate.prefix_last_event_ordinal = static_cast<std::uint64_t>(cutoff - 1u);
      candidate.prefix_last_availability_ts_ns =
          pack.rows[cutoff - 1u].ts_recv_ns;
      candidate.entry_bid_px = entry.bid_px;
      candidate.entry_ask_px = entry.ask_px;
      candidate.entry_mid2 = entry.mid2;
      candidate.entry_spread_usd = entry.spread_usd;
      candidate.frozen_cost_usd = entry.spread_usd + kFrozenFeeUsd;
      candidate.atr14_prev_usd = priors.atr14_prev_usd;
      const PhaseSpreadPrior& spread = priors.phase[decision_phase];
      candidate.spread_prior_present = spread.present;
      candidate.spread_prior_usd = spread.median_spread_usd;
      candidate.sane_ceiling_usd = spread.sane_ceiling_usd;
      const auto emission_key = std::make_tuple(decision_ts, confirmation_ordinal, side);
      auto [found, inserted] = emitted.emplace(emission_key, candidate);
      if (!inserted) {
        found->second.rung_mask = static_cast<std::uint8_t>(found->second.rung_mask | rung_mask);
      }
    }
  }
  std::set<std::uint64_t> cutoffs;
  for (const auto& [key, candidate] : emitted) {
    (void)key;
    cutoffs.insert(candidate.event_cutoff);
  }
  auto hashes = prefix_hashes(pack, cutoffs);
  if (!hashes) return refuse<CandidateSession>(hashes.error());
  result.candidates.reserve(emitted.size());
  const std::string pack_sha = event_pack_sha256(pack);
  if (!valid_sha256(pack_sha)) {
    return refuse<CandidateSession>(g1_content(
        "qr_entry_v2::generate_g1_candidates", "event pack has no valid SHA-256 identity"));
  }
  for (auto& [key, candidate] : emitted) {
    (void)key;
    candidate.event_pack_sha256 = pack_sha;
    candidate.prefix_sha256 = hashes.value().at(candidate.event_cutoff);
    candidate.clock_law_receipt_sha256 = kClockLawReceiptSha256;
    candidate.candidate_id = candidate_id_impl(candidate);
    candidate.lineage_sha256 = candidate_lineage_impl(candidate);
    result.candidates.push_back(std::move(candidate));
  }
  result.status = CandidateSessionStatus::READY;
  return result;
}

Expected<std::monostate, Refusal> apply_candidate_compliance(
    const ComplianceCalendar* calendar, std::vector<CandidateRow>* candidates) {
  if (candidates == nullptr) {
    return refuse<std::monostate>(Refusal(
        RefusalCode::CONFIG, "qr_entry_v2::apply_candidate_compliance",
        "candidate output pointer is null"));
  }
  if (calendar != nullptr && calendar->available &&
      !valid_sha256(calendar->artifact_sha256)) {
    return refuse<std::monostate>(g1_content(
        "qr_entry_v2::apply_candidate_compliance",
        "available compliance artifact has no valid SHA-256"));
  }
  for (CandidateRow& candidate : *candidates) {
    candidate.compliance = ComplianceStatus::COMPLIANCE_UNKNOWN;
    candidate.compliance_distance_sec = std::numeric_limits<double>::quiet_NaN();
    candidate.compliance_artifact_sha256.clear();
    if (calendar != nullptr && calendar->available) {
      candidate.compliance_artifact_sha256 = calendar->artifact_sha256;
      bool covered = false;
      bool prohibited = false;
      long double nearest_ns = std::numeric_limits<long double>::infinity();
      for (const ComplianceInterval& interval : calendar->rows) {
        if (interval.availability_ts_ns >= candidate.decision_ts_ns) {
          continue;  // later-known schedules are invisible, not backfilled
        }
        const bool inside = interval.start_ts_ns <= candidate.decision_ts_ns &&
                            candidate.decision_ts_ns <= interval.end_ts_ns;
        if (interval.kind == ComplianceRowKind::COVERAGE) {
          covered = covered || inside;
          continue;
        }
        if (inside) prohibited = true;
        long double distance = 0.0L;
        if (candidate.decision_ts_ns < interval.start_ts_ns) {
          distance = static_cast<long double>(interval.start_ts_ns -
                                              candidate.decision_ts_ns);
        } else if (candidate.decision_ts_ns > interval.end_ts_ns) {
          distance = static_cast<long double>(candidate.decision_ts_ns -
                                              interval.end_ts_ns);
        }
        nearest_ns = std::min(nearest_ns, distance);
      }
      if (prohibited) {
        candidate.compliance = ComplianceStatus::PROHIBITED;
      } else if (covered) {
        candidate.compliance = ComplianceStatus::CLEAR;
      }
      if (std::isfinite(static_cast<double>(nearest_ns))) {
        candidate.compliance_distance_sec = static_cast<double>(
            nearest_ns / static_cast<long double>(kNsPerSecond));
      }
    }
    candidate.lineage_sha256 = candidate_lineage_impl(candidate);
  }
  return std::monostate{};
}

Expected<std::vector<TeacherRow>, Refusal> certify_teacher(
    qr::futsess::Asset asset, const PhaseRow& schedule, const EventPack& pack,
    const DayPriors& priors, const std::vector<CandidateRow>& candidates) {
  auto valid = validate_teacher_inputs(asset, pack, candidates);
  if (!valid) return refuse<std::vector<TeacherRow>>(valid.error());
  auto prefixes = validate_candidate_prefixes(pack, candidates);
  if (!prefixes) return refuse<std::vector<TeacherRow>>(prefixes.error());
  if (std::memcmp(pack.header.magic, "QRE2EVT2", 8) != 0 ||
      pack.header.version != 2u || pack.header.row_bytes != kEventRowBytes) {
    return refuse<std::vector<TeacherRow>>(g1_content(
        "qr_entry_v2::certify_teacher", "QRE2EVT2 pack is required"));
  }
  std::vector<std::optional<SaneBookObservation>> trusted_sane(pack.rows.size());
  std::vector<std::uint64_t> generation(pack.rows.size() + 1u, 0u);
  BookQualityState book_quality;
  std::uint64_t previous_ts_recv = 0;
  bool have_previous = false;
  for (std::size_t i = 0; i < pack.rows.size(); ++i) {
    const EventRow& event = pack.rows[i];
    if (have_previous && event.ts_recv_ns < previous_ts_recv) {
      return refuse<std::vector<TeacherRow>>(Refusal(
          RefusalCode::OUT_OF_ORDER, "qr_entry_v2::certify_teacher",
          "event pack receive timestamps are decreasing"));
    }
    previous_ts_recv = event.ts_recv_ns;
    have_previous = true;
    auto observed = classify_event_book(asset, event, schedule, priors);
    if (!observed) return refuse<std::vector<TeacherRow>>(observed.error());
    auto quality = book_quality.observe(event.ts_recv_ns, event.flags,
                                       observed.value().two_sided);
    if (!quality) return refuse<std::vector<TeacherRow>>(quality.error());
    generation[i + 1u] = quality.value().generation;
    if (quality.value().trusted_economic && observed.value().sane) {
      trusted_sane[i] = observed.value();
    }
  }
  if (book_quality.unresolved_taint()) {
    std::vector<TeacherRow> out;
    out.reserve(candidates.size());
    for (const CandidateRow& candidate : candidates) {
      TeacherRow teacher;
      teacher.candidate_id = candidate.candidate_id;
      teacher.asset = asset;
      teacher.d8 = candidate.d8;
      teacher.decision_ts_ns = candidate.decision_ts_ns;
      teacher.phase_close_utc = candidate.phase_close_utc;
      teacher.compliance = candidate.compliance;
      teacher.status = TeacherStatus::NO_SANE_SUFFIX;
      out.push_back(std::move(teacher));
    }
    return out;
  }
  std::vector<TeacherRow> out;
  out.reserve(candidates.size());
  for (const CandidateRow& candidate : candidates) {
    TeacherRow teacher;
    teacher.candidate_id = candidate.candidate_id;
    teacher.asset = asset;
    teacher.d8 = candidate.d8;
    teacher.decision_ts_ns = candidate.decision_ts_ns;
    teacher.phase_close_utc = candidate.phase_close_utc;
    // Compliance belongs to the candidate key even when no certifiable suffix
    // exists.  A teacher refusal must not silently erase its causal status.
    teacher.compliance = candidate.compliance;
    const std::uint64_t phase_close_ns =
        static_cast<std::uint64_t>(candidate.phase_close_utc) * kNsPerSecond;
    const std::uint64_t candidate_generation =
        generation[static_cast<std::size_t>(candidate.event_cutoff)];
    bool have_sane = false;
    std::uint64_t last_sane_ts = 0;
    double last_net = 0.0;
    double max_net = 0.0;
    double min_net = 0.0;
    std::uint64_t peak_ts = candidate.decision_ts_ns;
    for (std::size_t i = static_cast<std::size_t>(candidate.event_cutoff);
         i < pack.rows.size(); ++i) {
      const EventRow& event = pack.rows[i];
      if (event.ts_recv_ns > phase_close_ns) break;  // close is explicitly inclusive
      if (generation[i + 1u] != candidate_generation) break;
      if (!trusted_sane[i].has_value()) continue;
      const SaneBookObservation& observed = *trusted_sane[i];
      have_sane = true;
      const double net = exact_net_value(asset, candidate.side,
                                         candidate.entry_mid2,
                                         observed.mid2,
                                         candidate.frozen_cost_usd);
      if (!std::isfinite(net)) {
        return refuse<std::vector<TeacherRow>>(g1_content(
            "qr_entry_v2::certify_teacher", "non-finite exact teacher value"));
      }
      last_sane_ts = event.ts_recv_ns;
      last_net = net;
      if (net > max_net) {
        max_net = net;
        peak_ts = event.ts_recv_ns;  // strict: earliest equal peak keeps identity
      }
      min_net = std::min(min_net, net);
      if (net <= -kTeacherWallUsd) {
        teacher.wall_hit = true;
        break;  // first cost-inclusive wall, actual gap-through value retained
      }
    }
    if (!have_sane) {
      teacher.status = TeacherStatus::NO_SANE_SUFFIX;
      out.push_back(std::move(teacher));
      continue;
    }
    teacher.status = TeacherStatus::READY;
    teacher.exit_ts_ns = last_sane_ts;
    teacher.cert_close_usd = last_net;
    teacher.mfe_usd = std::max(0.0, max_net);
    teacher.mae_usd = std::max(0.0, -min_net);
    teacher.time_to_peak_sec = static_cast<double>(
        static_cast<long double>(peak_ts - candidate.decision_ts_ns) /
        static_cast<long double>(kNsPerSecond));
    teacher.payer = teacher.cert_close_usd > 0.0;
    teacher.take_target = teacher.cert_close_usd >= kTakeTargetUsd;
    out.push_back(std::move(teacher));
  }
  return out;
}

Expected<ScheduleResult, Refusal> exact_schedule_ceiling(
    const std::vector<TeacherRow>& teacher,
    const std::vector<ExpectedSession>& expected_sessions,
    ScheduleUniverse universe) {
  auto valid = validate_schedule_inputs(teacher, expected_sessions);
  if (!valid) return refuse<ScheduleResult>(valid.error());
  ScheduleResult result;
  result.law = universe == ScheduleUniverse::DEPLOYABLE_CLEAR_ONLY
                   ? "DEPLOYABLE_EXACT_WEIGHTED_INTERVAL_CEILING"
                   : "MECHANICAL_EXACT_WEIGHTED_INTERVAL_CEILING";
  for (const TeacherRow& row : teacher) result.selected.emplace(row.candidate_id, false);

  std::map<std::int32_t,
           std::map<qr::futsess::Asset, std::vector<const TeacherRow*>>> by_day;
  for (const TeacherRow& row : teacher) by_day[row.d8][row.asset].push_back(&row);
  for (auto& [d8, assets] : by_day) {
    (void)d8;
    std::vector<AssetPlans> choices;
    for (auto& [asset, rows] : assets) {
      (void)asset;
      choices.push_back(make_asset_plans(std::move(rows), kMaxEntriesPerAssetDay,
                                         universe));
    }
    struct PortfolioPlan {
      bool valid = false;
      long double value = 0.0L;
      std::vector<std::pair<std::size_t, std::size_t>> choices;
      std::vector<std::string> ids;
    };
    const auto better = [](const PortfolioPlan& lhs, const PortfolioPlan& rhs) {
      if (!lhs.valid) return false;
      if (!rhs.valid) return true;
      if (lhs.value != rhs.value) return lhs.value > rhs.value;
      return lhs.ids < rhs.ids;
    };
    std::vector<PortfolioPlan> dp(kMaxEntriesPerPortfolioDay + 1u);
    dp[0].valid = true;
    for (std::size_t a = 0; a < choices.size(); ++a) {
      std::vector<PortfolioPlan> next(kMaxEntriesPerPortfolioDay + 1u);
      for (std::size_t used = 0; used <= kMaxEntriesPerPortfolioDay; ++used) {
        if (!dp[used].valid) continue;
        for (std::size_t k = 0; k < choices[a].exact.size() &&
                                used + k <= kMaxEntriesPerPortfolioDay; ++k) {
          const Plan& plan = choices[a].exact[k];
          if (!plan.valid) continue;
          PortfolioPlan candidate = dp[used];
          candidate.valid = true;
          candidate.value += plan.value;
          candidate.choices.emplace_back(a, k);
          for (std::size_t pick : plan.picks) {
            candidate.ids.push_back(choices[a].rows[pick]->candidate_id);
          }
          std::sort(candidate.ids.begin(), candidate.ids.end());
          if (better(candidate, next[used + k])) next[used + k] = std::move(candidate);
        }
      }
      dp = std::move(next);
    }
    PortfolioPlan best;
    for (const PortfolioPlan& candidate : dp) {
      if (better(candidate, best)) best = candidate;
    }
    for (const std::string& id : best.ids) result.selected[id] = true;
  }
  finish_schedule_metrics(&result, teacher, expected_sessions);
  return result;
}

Expected<ScheduleResult, Refusal> chronological_truth_arrival(
    const std::vector<TeacherRow>& teacher,
    const std::vector<ExpectedSession>& expected_sessions,
    const ArrivalThresholds& thresholds) {
  auto valid = validate_schedule_inputs(teacher, expected_sessions);
  if (!valid) return refuse<ScheduleResult>(valid.error());
  if (!valid_sha256(thresholds.threshold_receipt_sha256)) {
    return refuse<ScheduleResult>(Refusal(
        RefusalCode::CONFIG, "qr_entry_v2::chronological_truth_arrival",
        "inner-frozen threshold receipt SHA-256 is required"));
  }
  std::set<qr::futsess::Asset> assets;
  for (const ExpectedSession& session : expected_sessions) assets.insert(session.asset);
  for (qr::futsess::Asset asset : assets) {
    const auto found = thresholds.min_value_usd.find(asset);
    if (found == thresholds.min_value_usd.end() || !std::isfinite(found->second)) {
      return refuse<ScheduleResult>(Refusal(
          RefusalCode::CONFIG, "qr_entry_v2::chronological_truth_arrival",
          "every asset requires an explicit finite inner-frozen threshold"));
    }
  }
  ScheduleResult result;
  result.law = "CHRONOLOGICAL_TRUTH_SCORE_ARRIVAL";
  for (const TeacherRow& row : teacher) result.selected.emplace(row.candidate_id, false);
  std::vector<const TeacherRow*> ordered;
  for (const TeacherRow& row : teacher) {
    if (row.status == TeacherStatus::READY &&
        row.compliance == ComplianceStatus::CLEAR) {
      ordered.push_back(&row);
    }
  }
  std::sort(ordered.begin(), ordered.end(), [](const TeacherRow* lhs,
                                               const TeacherRow* rhs) {
    return std::tie(lhs->decision_ts_ns, lhs->asset, lhs->candidate_id) <
           std::tie(rhs->decision_ts_ns, rhs->asset, rhs->candidate_id);
  });
  std::map<qr::futsess::Asset, std::uint64_t> open_until;
  std::map<ExpectedSession, std::size_t> asset_day_count;
  std::map<std::int32_t, std::size_t> day_count;
  std::size_t i = 0;
  while (i < ordered.size()) {
    const std::uint64_t ts = ordered[i]->decision_ts_ns;
    std::size_t j = i + 1u;
    while (j < ordered.size() && ordered[j]->decision_ts_ns == ts) ++j;
    std::map<qr::futsess::Asset, const TeacherRow*> best;
    for (std::size_t k = i; k < j; ++k) {
      const TeacherRow* row = ordered[k];
      if (row->cert_close_usd < thresholds.min_value_usd.at(row->asset)) continue;
      const auto occupied = open_until.find(row->asset);
      if (occupied != open_until.end() && ts <= occupied->second) continue;
      const ExpectedSession session{row->asset, row->d8};
      if (asset_day_count[session] >= kMaxEntriesPerAssetDay) continue;
      auto found = best.find(row->asset);
      if (found == best.end() || row->cert_close_usd > found->second->cert_close_usd ||
          (row->cert_close_usd == found->second->cert_close_usd &&
           row->candidate_id < found->second->candidate_id)) {
        best[row->asset] = row;
      }
    }
    std::vector<const TeacherRow*> choices;
    for (const auto& [asset, row] : best) {
      (void)asset;
      choices.push_back(row);
    }
    std::sort(choices.begin(), choices.end(), [](const TeacherRow* lhs,
                                                 const TeacherRow* rhs) {
      if (lhs->cert_close_usd != rhs->cert_close_usd) {
        return lhs->cert_close_usd > rhs->cert_close_usd;
      }
      return std::tie(lhs->asset, lhs->candidate_id) <
             std::tie(rhs->asset, rhs->candidate_id);
    });
    for (const TeacherRow* row : choices) {
      if (day_count[row->d8] >= kMaxEntriesPerPortfolioDay) break;
      const ExpectedSession session{row->asset, row->d8};
      if (asset_day_count[session] >= kMaxEntriesPerAssetDay) continue;
      result.selected[row->candidate_id] = true;
      open_until[row->asset] = row->exit_ts_ns;
      ++asset_day_count[session];
      ++day_count[row->d8];
    }
    i = j;
  }
  finish_schedule_metrics(&result, teacher, expected_sessions);
  return result;
}

// Artifact drivers are implemented below the pure-law section in g1_artifacts.cpp.

}  // namespace qr::entry_v2
