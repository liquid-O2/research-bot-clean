#include "qr_w21/surface.hpp"

#include <algorithm>
#include <cmath>
#include <deque>
#include <string>

#include "qr_clock/session_clock.hpp"
#include "qr_core/checked.hpp"

namespace qr::w21 {
namespace {

constexpr const char* kSite = "qr_w21::surface";
constexpr std::int64_t kMsPerSecond = 1000;
constexpr std::int64_t kMicrosPerMs = 1000;
constexpr std::int64_t kU6PerUnit = 1'000'000;

template <class T>
Expected<T, Refusal> refuse(RefusalCode code, const char* detail, std::int64_t context = 0) {
  return Expected<T, Refusal>::refuse(Refusal(code, kSite, detail, context));
}

/// The contract identity the option-quote tape carries.
struct ContractKey {
  std::int32_t expiration_day = 0;
  std::int64_t strike_u6 = 0;
  std::uint8_t right = 0;
  friend bool operator<(const ContractKey& l, const ContractKey& r) noexcept {
    if (l.expiration_day != r.expiration_day) return l.expiration_day < r.expiration_day;
    if (l.strike_u6 != r.strike_u6) return l.strike_u6 < r.strike_u6;
    return l.right < r.right;
  }
};

struct ContractState {
  std::int64_t last_ts_ms = -1;
  std::int64_t bid_u6 = 0;
  std::int64_t ask_u6 = 0;
  std::int64_t bid_size = 0;
  std::int64_t ask_size = 0;
  std::int64_t dte_days = 0;
  qr::sources::Right right = qr::sources::Right::Other;
  std::int32_t expiration_day = 0;
  std::int64_t strike_u6 = 0;
  /// Q11: the bucket this contract occupied when pending event `slot` opened,
  /// or -1. Membership is frozen at the event second — no lookahead.
  std::array<std::int8_t, 8> event_bucket{};
  std::uint8_t counted_mask = 0;
};

/// Q11's tracker slots. Events sit on the 1s grid and live 5s, so at most six
/// are ever open; the eighth exists so "dropped" is provably zero.
constexpr std::size_t kRequoteSlots = 8;

struct PendingEvent {
  std::int64_t start_ms = 0;
  std::int64_t start_second = 0;
  std::int64_t denominator = 0;
  std::int64_t needed = 0;
  std::int64_t counted = 0;
  std::array<bool, kBuckets> bucket_seen{};
  bool any_reached = false;
  bool half_reached = false;
  std::int64_t latency_micros = 0;
  bool open = false;
};

/// A refill measurement Q9 has started but cannot finish until `t+5s`.
struct PendingRefill {
  std::int64_t measure_second = 0;
  std::int64_t bucket = 0;
  std::int64_t side = 0;  // 0 = bid, 1 = ask
  std::int64_t pre_drop_size = 0;
};

struct CompletedRefill {
  std::int64_t measure_second = 0;
  double ratio = 0.0;
};

}  // namespace

// ---------------------------------------------------------------------------
// The bucket axis (Q1, Q2).
// ---------------------------------------------------------------------------

Expected<std::int64_t, Refusal> moneyness_log_bps(std::int64_t strike_u6,
                                                  std::int64_t spot_u6) noexcept {
  if (strike_u6 <= 0 || spot_u6 <= 0) {
    return refuse<std::int64_t>(RefusalCode::CONTENT_MISMATCH,
                                "ln(K/m) needs a positive strike and a positive spot");
  }
  const double ratio = static_cast<double>(strike_u6) / static_cast<double>(spot_u6);
  const double scaled = static_cast<double>(kBpsScale) * std::log(ratio);
  if (!std::isfinite(scaled)) {
    return refuse<std::int64_t>(RefusalCode::CONTENT_MISMATCH, "ln(K/m) is not finite");
  }
  return static_cast<std::int64_t>(std::llround(scaled));
}

std::size_t moneyness_band(std::int64_t x_bps) noexcept {
  // RIGHT-OPEN, exactly as the bin carrier fixes it for this substrate: an
  // exact edge falls in the band ABOVE it.
  std::size_t band = 0;
  for (const std::int64_t edge : kMoneynessEdgesBps) {
    if (x_bps >= edge) {
      ++band;
    }
  }
  return band;
}

std::optional<std::size_t> bucket_index(std::int64_t x_bps, std::int64_t dte_days,
                                        qr::sources::Right right) noexcept {
  if (dte_days < 0 || dte_days >= static_cast<std::int64_t>(kDtePlanes)) {
    return std::nullopt;  // Q2: the quote surface has exactly the DTE 0 and 1 planes.
  }
  std::size_t right_slot = 0;
  switch (right) {
    case qr::sources::Right::Call:
      right_slot = 0;
      break;
    case qr::sources::Right::Put:
      right_slot = 1;
      break;
    case qr::sources::Right::Other:
      return std::nullopt;
  }
  const std::size_t band = moneyness_band(x_bps);
  return (band * kDtePlanes + static_cast<std::size_t>(dte_days)) * kRights + right_slot;
}

BucketKey bucket_key(std::size_t index) noexcept {
  BucketKey key;
  key.right = index % kRights;
  const std::size_t rest = index / kRights;
  key.dte_plane = rest % kDtePlanes;
  key.moneyness_band = rest / kDtePlanes;
  return key;
}

int orientation(std::size_t bucket, bool long_side) noexcept {
  const BucketKey key = bucket_key(bucket);
  const int rho = key.right == 0 ? 1 : -1;
  const int sigma = long_side ? 1 : -1;
  return sigma * rho;
}

// ---------------------------------------------------------------------------
// Q4's bucket reduction.
// ---------------------------------------------------------------------------

Typed<double> BucketSecond::bid_size_channel() const noexcept {
  return contracts > 0 ? qr::carriers::count_log1p(bid_size_sum)
                       : qr::carriers::masked(Validity::MISSING);
}
Typed<double> BucketSecond::ask_size_channel() const noexcept {
  return contracts > 0 ? qr::carriers::count_log1p(ask_size_sum)
                       : qr::carriers::masked(Validity::MISSING);
}
Typed<std::int64_t> BucketSecond::mean_spread_bps_exact() const noexcept {
  if (mean_spread_bps.v != Validity::VALID) {
    return Typed<std::int64_t>{0, mean_spread_bps.v};
  }
  return Typed<std::int64_t>{static_cast<std::int64_t>(std::llround(mean_spread_bps.value)),
                             Validity::VALID};
}

std::int64_t SurfaceSecond::valid_buckets() const noexcept {
  std::int64_t valid = 0;
  for (const BucketSecond& slot : bucket) {
    if (slot.valid) ++valid;
  }
  return valid;
}

BucketSecond reduce_bucket(std::span<const LiveQuote> members) {
  BucketSecond out;
  out.contracts = static_cast<std::int64_t>(members.size());
  if (out.contracts == 0) {
    out.mean_spread_bps = qr::carriers::masked(Validity::MISSING);
    out.stdev_spread_bps = qr::carriers::masked(Validity::MISSING);
    out.mean_log1p_age_micros = qr::carriers::masked(Validity::MISSING);
    out.two_sided_fraction = qr::carriers::masked(Validity::MISSING);
    out.valid = false;
    return out;
  }

  // Pass 1 — EXACT INTEGER accumulation. Every sum below is order-invariant, so
  // the reduction does not depend on the order the members arrive in.
  std::int64_t spread_weight = 0;
  std::int64_t spread_weighted_sum = 0;
  std::int64_t age_weight = 0;
  double age_weighted_sum = 0.0;
  for (const LiveQuote& member : members) {
    out.bid_size_sum += member.bid_size;
    out.ask_size_sum += member.ask_size;
    const std::int64_t weight = member.bid_size + member.ask_size;
    if (member.two_sided()) {
      ++out.two_sided;
      const std::int64_t mid = qr::sources::midpoint_u6(member.bid_u6, member.ask_u6);
      const auto spread = qr::carriers::displacement_bps(member.ask_u6 - member.bid_u6, mid);
      if (spread.has_value() && spread.value().v == Validity::VALID && weight > 0) {
        spread_weight += weight;
        spread_weighted_sum += weight * spread.value().value;
      }
    }
    if (weight > 0) {
      const Typed<double> age = qr::carriers::time_log1p_micros(member.age_micros);
      if (age.v == Validity::VALID) {
        age_weight += weight;
        age_weighted_sum += static_cast<double>(weight) * age.value;
      }
    }
  }

  const double mean_spread =
      spread_weight > 0 ? static_cast<double>(spread_weighted_sum) / static_cast<double>(spread_weight)
                        : 0.0;
  out.mean_spread_bps = spread_weight > 0 ? qr::carriers::present(mean_spread)
                                          : qr::carriers::masked(Validity::MISSING);
  out.mean_log1p_age_micros =
      age_weight > 0 ? qr::carriers::present(age_weighted_sum / static_cast<double>(age_weight))
                     : qr::carriers::masked(Validity::MISSING);

  // Pass 2 — the size-weighted dispersion, in the TWO-PASS form. It is never
  // negative, so it needs no clamp (range-limiting guards are banned), and it
  // is reduced over the caller's canonical member order.
  if (spread_weight > 0) {
    double dispersion = 0.0;
    for (const LiveQuote& member : members) {
      if (!member.two_sided()) continue;
      const std::int64_t weight = member.bid_size + member.ask_size;
      if (weight <= 0) continue;
      const std::int64_t mid = qr::sources::midpoint_u6(member.bid_u6, member.ask_u6);
      const auto spread = qr::carriers::displacement_bps(member.ask_u6 - member.bid_u6, mid);
      if (!spread.has_value() || spread.value().v != Validity::VALID) continue;
      const double delta = static_cast<double>(spread.value().value) - mean_spread;
      dispersion += static_cast<double>(weight) * delta * delta;
    }
    out.stdev_spread_bps =
        qr::carriers::present(std::sqrt(dispersion / static_cast<double>(spread_weight)));
  } else {
    out.stdev_spread_bps = qr::carriers::masked(Validity::MISSING);
  }

  out.two_sided_fraction = qr::carriers::fraction(out.two_sided, out.contracts);
  // Q4: "bucket VALID iff >=50% two-sided", as an exact integer test.
  out.valid = kValidTwoSidedNumerator * out.two_sided >= out.contracts;
  return out;
}

// ---------------------------------------------------------------------------
// Q3 / Q5 — the ATM straddle and PROXY_VOL.
// ---------------------------------------------------------------------------

Typed<double> years_to_expiry(std::int64_t ts_ms_b, std::int64_t expiry_epoch_day) noexcept {
  // Frame B is naive ET wall clock, so "the expiry day's 16:00 ET" is exact
  // integer arithmetic on the epoch day — no timezone rule is involved.
  const auto day_seconds = qr::checked_mul(expiry_epoch_day, 86400);
  if (!day_seconds.has_value()) return qr::carriers::masked(Validity::NONFINITE);
  const auto close_seconds = qr::checked_add(day_seconds.value(), kExpiryCloseSecondsIntoDay);
  if (!close_seconds.has_value()) return qr::carriers::masked(Validity::NONFINITE);
  const auto close_ms = qr::checked_mul(close_seconds.value(), kMsPerSecond);
  if (!close_ms.has_value()) return qr::carriers::masked(Validity::NONFINITE);
  const auto remaining_ms = qr::checked_sub(close_ms.value(), ts_ms_b);
  if (!remaining_ms.has_value()) return qr::carriers::masked(Validity::NONFINITE);
  // Q3's guard: "remaining time < 300s => PROXY_VOL typed absent".
  if (remaining_ms.value() < kProxyVolGuardSeconds * kMsPerSecond) {
    return qr::carriers::masked(Validity::MODALITY_ABSENT);
  }
  return qr::carriers::present(static_cast<double>(remaining_ms.value()) /
                               (1000.0 * kYearSeconds));
}

Typed<double> proxy_vol(std::int64_t straddle_u6, std::int64_t spot_u6,
                        Typed<double> years) noexcept {
  if (years.v != Validity::VALID || years.value <= 0.0) {
    return qr::carriers::masked(years.v == Validity::VALID ? Validity::NONPOSITIVE : years.v);
  }
  if (straddle_u6 <= 0 || spot_u6 <= 0) {
    return qr::carriers::masked(Validity::NONPOSITIVE);
  }
  const double value = (static_cast<double>(straddle_u6) / static_cast<double>(spot_u6)) /
                       std::sqrt(years.value);
  return std::isfinite(value) ? qr::carriers::present(value)
                              : qr::carriers::masked(Validity::NONFINITE);
}

StraddleSecond select_straddle(const StraddleLegs& legs, std::int64_t spot_u6,
                               std::int64_t ts_ms_b, std::int64_t expiry_epoch_day) {
  StraddleSecond out;
  out.absence = Validity::MODALITY_ABSENT;
  if (spot_u6 <= 0) {
    out.absence = Validity::MISSING;
    return out;
  }
  // Q5: nearest strike with BOTH legs two-sided (the age gate is applied by the
  // caller when it assembles `legs`), no interpolation, and nothing outside
  // |ln(K/m)| <= 150bp.
  bool found = false;
  bool tied = false;
  std::int64_t best_strike = 0;
  std::int64_t best_abs = 0;
  std::int64_t best_signed = 0;
  for (const auto& [strike, call] : legs.calls) {
    if (!call.two_sided()) continue;
    const auto put = legs.puts.find(strike);
    if (put == legs.puts.end() || !put->second.two_sided()) continue;
    const auto x = moneyness_log_bps(strike, spot_u6);
    if (!x.has_value()) continue;
    const std::int64_t distance = x.value() < 0 ? -x.value() : x.value();
    if (distance > kStraddleMaxAbsBps) continue;
    if (!found || distance < best_abs) {
      found = true;
      tied = false;
      best_abs = distance;
      best_strike = strike;
      best_signed = x.value();
    } else if (distance == best_abs) {
      // Two strikes exactly equidistant from the spot. The repository law
      // forbids breaking a scientific tie by id, hash or source order, and no
      // rule in W21-PIN-1 picks one, so the selection is UNDECIDABLE and the
      // straddle is typed absent rather than silently taking the first.
      tied = true;
    }
  }
  if (!found || tied) {
    out.absence = found ? Validity::EQUAL_TIME_UNORDERED : Validity::MODALITY_ABSENT;
    return out;
  }

  const LiveQuote& call = legs.calls.at(best_strike);
  const LiveQuote& put = legs.puts.at(best_strike);
  out.strike_u6 = best_strike;
  out.moneyness_bps = best_signed;
  out.straddle_bid_u6 = call.bid_u6 + put.bid_u6;
  out.straddle_ask_u6 = call.ask_u6 + put.ask_u6;
  out.straddle_mid_u6 = qr::sources::midpoint_u6(call.bid_u6, call.ask_u6) +
                        qr::sources::midpoint_u6(put.bid_u6, put.ask_u6);
  out.width_u6 = out.straddle_ask_u6 - out.straddle_bid_u6;
  const Typed<double> years = years_to_expiry(ts_ms_b, expiry_epoch_day);
  out.proxy_vol_mid = proxy_vol(out.straddle_mid_u6, spot_u6, years);
  out.proxy_vol_bid = proxy_vol(out.straddle_bid_u6, spot_u6, years);
  out.proxy_vol_ask = proxy_vol(out.straddle_ask_u6, spot_u6, years);
  out.present = true;
  out.absence = Validity::VALID;
  return out;
}

namespace {

/// Delta-log of a positive series over one horizon; absent unless BOTH ends are
/// present and positive.
Typed<double> dlog(const Typed<double>& now, const Typed<double>& then) noexcept {
  if (now.v != Validity::VALID || then.v != Validity::VALID) {
    return qr::carriers::masked(Validity::MISSING);
  }
  if (now.value <= 0.0 || then.value <= 0.0) {
    return qr::carriers::masked(Validity::NONPOSITIVE);
  }
  const double value = std::log(now.value) - std::log(then.value);
  return std::isfinite(value) ? qr::carriers::present(value)
                              : qr::carriers::masked(Validity::NONFINITE);
}

/// The EXACT-RANK lower median of an integer sample, the same rule the W2.0
/// census uses: the smallest observed value whose cumulative count reaches
/// ceil(n/2). It never returns a value the sample did not contain.
std::int64_t exact_rank_median(std::vector<std::int64_t>& sample) {
  std::sort(sample.begin(), sample.end());
  const std::size_t rank = (sample.size() + 1) / 2;
  return sample[rank - 1];
}

}  // namespace

// ---------------------------------------------------------------------------
// The session constructor.
// ---------------------------------------------------------------------------

Expected<SurfaceBuilder, Refusal> SurfaceBuilder::build(const DayScope& scope,
                                                        const std::filesystem::path& corpus_root,
                                                        const std::filesystem::path& tape_side_dir,
                                                        SurfaceOptions options) {
  SurfaceBuilder built;
  // Q12: MODALITY_ABSENT is exactly ordinals 125..208. The check happens BEFORE
  // any path is formed, so an absent session never touches the corpus.
  if (session_is_modality_absent(scope.ordinal())) {
    built.modality_absent_ = true;
    return built;
  }

  const Expected<SessionClock, Refusal> clock = SessionClock::from_session(scope.session());
  if (!clock.has_value()) {
    return Expected<SurfaceBuilder, Refusal>::refuse(clock.error());
  }
  const std::int64_t open_ms_b = clock.value().open_b().ns() / 1'000'000;
  const std::int64_t bar_count = clock.value().expected_bar_count();
  const std::int64_t endpoints = bar_count * 60 + 1;
  built.seconds_ = endpoints;

  Expected<w20::SpotGrid, Refusal> grid = w20::SpotGrid::open(tape_side_dir, open_ms_b, bar_count);
  if (!grid.has_value()) {
    return Expected<SurfaceBuilder, Refusal>::refuse(grid.error());
  }
  const w20::SpotGrid spot = std::move(grid).value();

  qr::parquet::FileExpected<qr::sources::OptionQuoteReader> opened =
      qr::sources::OptionQuoteReader::open(scope, corpus_root);
  if (!opened.has_value()) {
    return Expected<SurfaceBuilder, Refusal>::refuse(opened.error().refusal());
  }
  qr::sources::OptionQuoteReader reader = std::move(opened).value();

  built.latency_micros_ = w20::DenseCounter(0, kRequoteHorizonMs * kMicrosPerMs + 1);
  built.spread_bps_ = w20::DenseCounter(0, 20001);
  built.proxy_vol_ = w20::DenseCounter(0, 10001);

  std::map<ContractKey, ContractState> contracts;
  std::array<PendingEvent, kRequoteSlots> events{};
  std::array<std::vector<LiveQuote>, kBuckets> members;
  std::array<StraddleLegs, kDtePlanes> legs;
  std::vector<StraddleSecond> straddle_now(kDtePlanes);
  std::vector<std::vector<StraddleSecond>> straddle_history(kDtePlanes);
  std::array<std::deque<std::pair<std::int64_t, std::int64_t>>, kBuckets> spread_samples;
  std::array<std::array<std::int64_t, 2>, kBuckets> previous_side_size{};
  std::array<std::array<bool, 2>, kBuckets> previous_side_present{};
  std::vector<PendingRefill> pending_refill;
  std::array<std::array<std::deque<CompletedRefill>, 2>, kBuckets> refill_history;
  std::vector<double> valid_fraction(static_cast<std::size_t>(endpoints), 0.0);
  std::vector<char> valid_fraction_present(static_cast<std::size_t>(endpoints), 0);
  std::array<std::vector<std::int64_t>, kBuckets> side_size_by_second;
  for (auto& series : side_size_by_second) {
    series.assign(static_cast<std::size_t>(endpoints) * 2, 0);
  }

  if (options.retain_seconds) {
    built.surface_.resize(static_cast<std::size_t>(endpoints));
    built.straddle_channels_.resize(static_cast<std::size_t>(endpoints) * kDtePlanes);
    built.thinning_.resize(static_cast<std::size_t>(endpoints));
    built.refill_.resize(static_cast<std::size_t>(endpoints) * kBuckets);
  }
  for (auto& plane : straddle_history) {
    plane.resize(static_cast<std::size_t>(endpoints));
  }

  qr::sources::OptionQuoteReader::Group group;
  bool have_group = false;
  std::int64_t previous_spot = 0;

  const auto ingest_group = [&](const qr::sources::OptionQuoteReader::Group& current) {
    ++built.groups_;
    for (const qr::sources::OptionQuoteRow& row : current.rows) {
      const ContractKey key{row.expiration_day, row.strike_u6,
                            static_cast<std::uint8_t>(row.right)};
      ContractState& state = contracts[key];
      if (state.last_ts_ms < 0) {
        state.expiration_day = row.expiration_day;
        state.strike_u6 = row.strike_u6;
        state.right = row.right;
        state.dte_days =
            static_cast<std::int64_t>(row.expiration_day) - scope.civil_date().days_since_epoch();
        state.event_bucket.fill(-1);
        ++built.contracts_;
        if (state.dte_days < 0 || state.dte_days >= static_cast<std::int64_t>(kDtePlanes) ||
            row.right == qr::sources::Right::Other) {
          ++built.off_surface_contracts_;
        }
      }
      // Q11: a requote is a strictly-later group from a contract that was a
      // member of a frozen bucket when the event opened.
      for (std::size_t slot = 0; slot < kRequoteSlots; ++slot) {
        PendingEvent& event = events[slot];
        const std::uint8_t bit = static_cast<std::uint8_t>(1U << slot);
        if (!event.open) continue;
        const std::int8_t bucket = state.event_bucket[slot];
        if (bucket < 0) continue;
        if (current.ts_ms_b <= event.start_ms) continue;
        if (event.bucket_seen[static_cast<std::size_t>(bucket)]) continue;
        event.bucket_seen[static_cast<std::size_t>(bucket)] = true;
        ++event.counted;
        const std::int64_t latency = (current.ts_ms_b - event.start_ms) * kMicrosPerMs;
        if (!event.any_reached) {
          event.any_reached = true;
        }
        if (!event.half_reached && event.counted >= event.needed) {
          event.half_reached = true;
          event.latency_micros = latency;
        }
        state.counted_mask = static_cast<std::uint8_t>(state.counted_mask | bit);
      }
      state.last_ts_ms = current.ts_ms_b;
      state.bid_u6 = row.bid_u6;
      state.ask_u6 = row.ask_u6;
      state.bid_size = row.bid_size;
      state.ask_size = row.ask_size;
      ++built.rth_rows_;
    }
  };

  for (std::int64_t second = 0; second < endpoints; ++second) {
    const std::int64_t endpoint_ms = open_ms_b + second * kMsPerSecond;

    // --- consume every group STRICTLY BEFORE this endpoint ------------------
    while (true) {
      if (!have_group) {
        const qr::parquet::FileExpected<bool> more = reader.next_group(group);
        if (!more.has_value()) {
          return Expected<SurfaceBuilder, Refusal>::refuse(more.error().refusal());
        }
        if (!more.value()) break;
        have_group = true;
      }
      if (group.ts_ms_b >= endpoint_ms) break;
      ingest_group(group);
      have_group = false;
    }

    // --- close every event whose 5s horizon has passed ----------------------
    for (std::size_t slot = 0; slot < kRequoteSlots; ++slot) {
      PendingEvent& event = events[slot];
      if (!event.open || endpoint_ms - event.start_ms <= kRequoteHorizonMs) continue;
      RequoteEventRecord record;
      record.event_second = event.start_second;
      record.denominator_buckets = event.denominator;
      record.latency_micros = event.latency_micros;
      record.half_reached = event.half_reached;
      record.any_reached = event.any_reached;
      built.requote_events_.push_back(record);
      if (event.half_reached) {
        built.latency_micros_.add(event.latency_micros);
      } else {
        ++built.no_requote_5s_;
      }
      event.open = false;
      for (auto& [key, state] : contracts) {
        state.event_bucket[slot] = -1;
      }
    }

    // --- the surface at this endpoint --------------------------------------
    const std::int64_t spot_u6 = spot.mid_u6_endpoint(second);
    if (spot_u6 <= 0) ++built.spot_absent_seconds_;
    for (auto& bucket_members : members) bucket_members.clear();
    for (auto& plane : legs) {
      plane.calls.clear();
      plane.puts.clear();
    }
    SurfaceSecond current;
    current.spot_u6 = spot_u6;

    for (auto& [key, state] : contracts) {
      if (state.last_ts_ms < 0) continue;
      const std::int64_t age_ms = endpoint_ms - state.last_ts_ms;
      if (age_ms < 0 || age_ms > kContractAgeGateMs) continue;
      LiveQuote live;
      live.bid_u6 = state.bid_u6;
      live.ask_u6 = state.ask_u6;
      live.bid_size = state.bid_size;
      live.ask_size = state.ask_size;
      live.age_micros = age_ms * kMicrosPerMs;
      ++current.live_contracts;
      if (!live.two_sided()) ++current.one_sided_contracts;
      if (spot_u6 <= 0) continue;
      const auto x = moneyness_log_bps(state.strike_u6, spot_u6);
      if (!x.has_value()) continue;
      const std::optional<std::size_t> bucket = bucket_index(x.value(), state.dte_days, state.right);
      if (!bucket.has_value()) continue;
      members[bucket.value()].push_back(live);
      const std::size_t plane = static_cast<std::size_t>(state.dte_days);
      if (state.right == qr::sources::Right::Call) {
        legs[plane].calls.emplace(state.strike_u6, live);
      } else if (state.right == qr::sources::Right::Put) {
        legs[plane].puts.emplace(state.strike_u6, live);
      }
    }

    for (std::size_t bucket = 0; bucket < kBuckets; ++bucket) {
      current.bucket[bucket] = reduce_bucket(std::span<const LiveQuote>(members[bucket]));
      ++built.bucket_seconds_;
      if (current.bucket[bucket].valid) ++built.valid_bucket_seconds_;
      const Typed<std::int64_t> spread = current.bucket[bucket].mean_spread_bps_exact();
      if (spread.v == Validity::VALID) {
        built.spread_bps_.add(spread.value);
        if (second % kThinningSampleSeconds == 0) {
          spread_samples[bucket].emplace_back(second, spread.value);
        }
      }
    }

    // --- Q9: evaporation and refill, per bucket per side --------------------
    for (std::size_t bucket = 0; bucket < kBuckets; ++bucket) {
      const std::array<std::int64_t, 2> size{current.bucket[bucket].bid_size_sum,
                                             current.bucket[bucket].ask_size_sum};
      for (std::size_t side = 0; side < 2; ++side) {
        side_size_by_second[bucket][static_cast<std::size_t>(second) * 2 + side] = size[side];
        if (previous_side_present[bucket][side] && previous_side_size[bucket][side] > 0 &&
            2 * size[side] <= previous_side_size[bucket][side]) {
          ++built.evaporation_events_;
          pending_refill.push_back(PendingRefill{second + kRefillLookaheadSeconds,
                                                 static_cast<std::int64_t>(bucket),
                                                 static_cast<std::int64_t>(side),
                                                 previous_side_size[bucket][side]});
        }
        previous_side_size[bucket][side] = size[side];
        previous_side_present[bucket][side] = true;
      }
    }
    // Complete every refill measurement whose t+5s is THIS second — the ratio
    // becomes usable only now, so no channel ever reads ahead of its own time.
    for (std::size_t index = 0; index < pending_refill.size();) {
      if (pending_refill[index].measure_second != second) {
        ++index;
        continue;
      }
      const PendingRefill& pend = pending_refill[index];
      const std::int64_t now_size =
          side_size_by_second[static_cast<std::size_t>(pend.bucket)]
                             [static_cast<std::size_t>(second) * 2 +
                              static_cast<std::size_t>(pend.side)];
      double ratio = static_cast<double>(now_size) / static_cast<double>(pend.pre_drop_size);
      if (ratio < 0.0) ratio = 0.0;
      if (ratio > kRefillRatioCap) ratio = kRefillRatioCap;  // Q9's pinned clip [0,2]
      refill_history[static_cast<std::size_t>(pend.bucket)][static_cast<std::size_t>(pend.side)]
          .push_back(CompletedRefill{second, ratio});
      pending_refill.erase(pending_refill.begin() + static_cast<std::ptrdiff_t>(index));
    }

    // --- Q5/Q8: the per-plane straddle and its channels ---------------------
    for (std::size_t plane = 0; plane < kDtePlanes; ++plane) {
      const std::int64_t expiry_day =
          scope.civil_date().days_since_epoch() + static_cast<std::int64_t>(plane);
      straddle_now[plane] = select_straddle(legs[plane], spot_u6, endpoint_ms, expiry_day);
      straddle_history[plane][static_cast<std::size_t>(second)] = straddle_now[plane];
      if (straddle_now[plane].present) {
        ++built.straddle_present_seconds_;
        if (straddle_now[plane].proxy_vol_mid.v == Validity::VALID) {
          built.proxy_vol_.add(static_cast<std::int64_t>(
              std::llround(straddle_now[plane].proxy_vol_mid.value * 10000.0)));
        } else if (straddle_now[plane].proxy_vol_mid.v == Validity::MODALITY_ABSENT) {
          ++built.straddle_guard_seconds_;
        }
      } else if (straddle_now[plane].absence == Validity::MODALITY_ABSENT) {
        ++built.straddle_no_strike_seconds_;
      }
      if (!options.retain_seconds) continue;
      StraddleChannels channels;
      const StraddleSecond& now = straddle_now[plane];
      channels.proxy_vol_mid = now.proxy_vol_mid;
      channels.proxy_vol_bid = now.proxy_vol_bid;
      channels.proxy_vol_ask = now.proxy_vol_ask;
      channels.width_u6 = now.present ? qr::carriers::present(static_cast<double>(now.width_u6))
                                      : qr::carriers::masked(now.absence);
      for (std::size_t h = 0; h < kHorizonsSeconds.size(); ++h) {
        const std::int64_t back = second - kHorizonsSeconds[h];
        if (back < 0) {
          channels.dlog_proxy_vol_mid[h] = qr::carriers::masked(Validity::MISSING);
          channels.dlog_proxy_vol_bid[h] = qr::carriers::masked(Validity::MISSING);
          channels.dlog_proxy_vol_ask[h] = qr::carriers::masked(Validity::MISSING);
          channels.dwidth_u6[h] = qr::carriers::masked(Validity::MISSING);
          continue;
        }
        const StraddleSecond& past = straddle_history[plane][static_cast<std::size_t>(back)];
        channels.dlog_proxy_vol_mid[h] = dlog(now.proxy_vol_mid, past.proxy_vol_mid);
        channels.dlog_proxy_vol_bid[h] = dlog(now.proxy_vol_bid, past.proxy_vol_bid);
        channels.dlog_proxy_vol_ask[h] = dlog(now.proxy_vol_ask, past.proxy_vol_ask);
        channels.dwidth_u6[h] =
            now.present && past.present
                ? qr::carriers::present(static_cast<double>(now.width_u6 - past.width_u6))
                : qr::carriers::masked(Validity::MISSING);
      }
      built.straddle_channels_[static_cast<std::size_t>(second) * kDtePlanes + plane] = channels;
    }

    // --- Q10 + A2: coverage thinning ---------------------------------------
    const std::int64_t valid_now = current.valid_buckets();
    valid_fraction[static_cast<std::size_t>(second)] =
        static_cast<double>(valid_now) / static_cast<double>(kBuckets);
    valid_fraction_present[static_cast<std::size_t>(second)] = 1;
    ThinningSecond thin;
    thin.valid_bucket_fraction = qr::carriers::fraction(valid_now, kBuckets);
    const std::int64_t back = second - kThinningLookbackSeconds;
    thin.valid_bucket_fraction_delta_60s =
        back >= 0 && valid_fraction_present[static_cast<std::size_t>(back)] != 0
            ? qr::carriers::present(valid_fraction[static_cast<std::size_t>(second)] -
                                    valid_fraction[static_cast<std::size_t>(back)])
            : qr::carriers::masked(Validity::MISSING);
    thin.one_sided_fraction =
        qr::carriers::fraction(current.one_sided_contracts, current.live_contracts);
    {
      std::int64_t wide = 0;
      std::int64_t judged = 0;
      for (std::size_t bucket = 0; bucket < kBuckets; ++bucket) {
        if (!current.bucket[bucket].valid) continue;
        const Typed<std::int64_t> spread = current.bucket[bucket].mean_spread_bps_exact();
        if (spread.v != Validity::VALID) continue;
        // Q10: 900s trailing median of the 60s samples, expanding from the open
        // below 900s, typed absent below 120s of window.
        while (!spread_samples[bucket].empty() &&
               second - spread_samples[bucket].front().first > kThinningMedianWindowSeconds) {
          spread_samples[bucket].pop_front();
        }
        if (second < kThinningMinimumWindowSeconds || spread_samples[bucket].size() < 2) continue;
        std::vector<std::int64_t> sample;
        sample.reserve(spread_samples[bucket].size());
        for (const auto& entry : spread_samples[bucket]) sample.push_back(entry.second);
        const std::int64_t median = exact_rank_median(sample);
        ++judged;
        if (spread.value > 2 * median) ++wide;
      }
      thin.wide_vs_trailing_median_fraction =
          judged > 0 ? qr::carriers::fraction(wide, judged)
                     : qr::carriers::masked(Validity::MISSING);
    }

    // --- Q9's channels, from the completed refills only ---------------------
    if (options.retain_seconds) {
      for (std::size_t bucket = 0; bucket < kBuckets; ++bucket) {
        RefillSecond channels;
        std::array<Typed<double>, 2> means{};
        for (std::size_t side = 0; side < 2; ++side) {
          auto& history = refill_history[bucket][side];
          while (!history.empty() && second - history.front().measure_second > kRefillWindowSeconds) {
            history.pop_front();
          }
          if (history.empty()) {
            means[side] = qr::carriers::masked(Validity::MISSING);
            continue;
          }
          double total = 0.0;
          for (const CompletedRefill& entry : history) total += entry.ratio;
          means[side] = qr::carriers::present(total / static_cast<double>(history.size()));
        }
        channels.mean_refill_bid = means[0];
        channels.mean_refill_ask = means[1];
        channels.oriented_refill_difference =
            means[0].v == Validity::VALID && means[1].v == Validity::VALID
                ? qr::carriers::present(static_cast<double>(orientation(bucket, true)) *
                                        (means[0].value - means[1].value))
                : qr::carriers::masked(Validity::MISSING);
        built.refill_[static_cast<std::size_t>(second) * kBuckets + bucket] = channels;
      }
    }

    // --- Q11: open an event when the grid moved by >= 0.5bp ------------------
    if (second > 0 && spot_u6 > 0 && previous_spot > 0) {
      const std::int64_t delta = spot_u6 > previous_spot ? spot_u6 - previous_spot
                                                         : previous_spot - spot_u6;
      if (delta * kHalfBpDenominator >= previous_spot) {
        std::size_t slot = kRequoteSlots;
        for (std::size_t candidate = 0; candidate < kRequoteSlots; ++candidate) {
          if (!events[candidate].open) {
            slot = candidate;
            break;
          }
        }
        if (slot < kRequoteSlots && valid_now > 0) {
          PendingEvent& event = events[slot];
          event = PendingEvent{};
          event.start_ms = endpoint_ms;
          event.start_second = second;
          event.denominator = valid_now;              // FROZEN at the event second
          event.needed = (valid_now + 1) / 2;         // ">= half", exactly
          event.open = true;
          for (auto& [key, state] : contracts) {
            state.event_bucket[slot] = -1;
            if (state.last_ts_ms < 0 || spot_u6 <= 0) continue;
            const std::int64_t age_ms = endpoint_ms - state.last_ts_ms;
            if (age_ms < 0 || age_ms > kContractAgeGateMs) continue;
            const auto x = moneyness_log_bps(state.strike_u6, spot_u6);
            if (!x.has_value()) continue;
            const std::optional<std::size_t> bucket =
                bucket_index(x.value(), state.dte_days, state.right);
            if (!bucket.has_value() || !current.bucket[bucket.value()].valid) continue;
            state.event_bucket[slot] = static_cast<std::int8_t>(bucket.value());
          }
        }
      }
    }
    previous_spot = spot_u6;

    if (options.retain_seconds) {
      built.surface_[static_cast<std::size_t>(second)] = current;
      built.thinning_[static_cast<std::size_t>(second)] = thin;
    }
  }

  // Any event still open at the close never reached its half within the tape.
  for (std::size_t slot = 0; slot < kRequoteSlots; ++slot) {
    PendingEvent& event = events[slot];
    if (!event.open) continue;
    RequoteEventRecord record;
    record.event_second = event.start_second;
    record.denominator_buckets = event.denominator;
    record.latency_micros = event.latency_micros;
    record.half_reached = event.half_reached;
    record.any_reached = event.any_reached;
    built.requote_events_.push_back(record);
    if (event.half_reached) {
      built.latency_micros_.add(event.latency_micros);
    } else {
      ++built.no_requote_5s_;
    }
    event.open = false;
  }
  return built;
}

// ---------------------------------------------------------------------------
// The census audit.
// ---------------------------------------------------------------------------

void emit(w20::CensusReport& report, std::int64_t ordinal, const std::string& day,
          const SurfaceBuilder& built) {
  const std::string scope = "s" + std::to_string(ordinal);
  report.text(scope, "session", "day", day);
  report.text(scope, "session", "modality",
              built.modality_absent() ? "MODALITY_ABSENT" : "VALID");
  report.metric(scope, "session", "grid_endpoints", built.seconds());
  if (built.modality_absent()) {
    return;
  }
  report.metric(scope, "stream", "rth_rows", built.rth_rows());
  report.metric(scope, "stream", "groups", built.groups());
  report.metric(scope, "stream", "contracts", built.contracts());
  report.metric(scope, "stream", "off_surface_contracts", built.off_surface_contracts());
  report.metric(scope, "surface", "bucket_seconds", built.bucket_seconds());
  report.metric(scope, "surface", "valid_bucket_seconds", built.valid_bucket_seconds());
  report.metric(scope, "surface", "spot_absent_seconds", built.spot_absent_seconds());
  report.metric(scope, "straddle", "present_seconds", built.straddle_present_seconds());
  report.metric(scope, "straddle", "guard_seconds", built.straddle_guard_seconds());
  report.metric(scope, "straddle", "no_strike_seconds", built.straddle_no_strike_seconds());
  report.metric(scope, "requote", "events", static_cast<std::int64_t>(built.requote_events().size()));
  report.metric(scope, "requote", "no_requote_5s", built.no_requote_5s_events());
  report.metric(scope, "refill", "evaporation_events", built.evaporation_events());
  report.distribution(scope, "requote_latency_micros", built.latency_micros_census());
  report.distribution(scope, "bucket_spread_bps", built.spread_bps_census());
  report.distribution(scope, "proxy_vol_x10000", built.proxy_vol_census());
}

}  // namespace qr::w21
