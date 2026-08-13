#include "qr_futsess/decode.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <memory>
#include <numeric>

#include "qr_dbn/dbn.hpp"
#include "qr_futsess/calendar.hpp"
#include "qr_futsess/dayrec.hpp"
#include "qr_futsess/seal.hpp"

namespace qr::futsess {
namespace {

constexpr std::uint8_t kActionTrade = 'T';

struct SecEntry {
  std::int64_t bid = kUndefPrice;
  std::int64_t ask = kUndefPrice;
  std::int64_t bsz = 0;
  std::int64_t asz = 0;
  std::uint8_t has_flast = 0u;
  std::int8_t state = kStEmpty;
};

struct TradeRec {
  std::int32_t sec;
  std::int64_t px;
  std::int64_t size;
  std::uint8_t side;
};

/// Per-instrument accumulation for one UTC day. `slot` maps second-of-day to an
/// index in `entries`, so the "last record of the second, F_LAST preferred"
/// rule is applied in O(1) with no dependence on record arrival order.
struct InstAccum {
  std::vector<std::int32_t> upd;
  std::vector<std::int32_t> slot;
  std::vector<SecEntry> entries;
  std::vector<std::int32_t> entry_sec;
  std::int64_t updates = 0;
  std::int64_t n_trades = 0;
  std::int64_t trade_size_sum = 0;
  std::int64_t prev_bid = 0;
  std::int64_t prev_ask = 0;
  bool has_prev_bid = false;
  bool has_prev_ask = false;
  std::int64_t px_gcd = 0;
  std::vector<TradeRec> trades;

  InstAccum()
      : upd(static_cast<std::size_t>(kSecondsPerDay), 0),
        slot(static_cast<std::size_t>(kSecondsPerDay), -1) {}
};

/// One UTC day of records for one asset (s2_decode.DayAccum).
class DayAccum {
 public:
  explicit DayAccum(std::int64_t day) : day_(day) {}

  [[nodiscard]] std::int64_t day() const { return day_; }
  [[nodiscard]] const std::vector<std::int64_t>& iids() const { return iids_; }
  [[nodiscard]] const InstAccum& inst(std::size_t i) const { return *insts_[i]; }
  [[nodiscard]] std::int64_t n_records() const { return n_records_; }
  [[nodiscard]] std::int64_t n_dropped_sentinel() const { return n_dropped_sentinel_; }

  void add(std::int64_t iid, std::int32_t sec, std::int64_t bid, std::int64_t ask,
           std::int64_t bsz, std::int64_t asz, bool flast, std::uint8_t action, std::int64_t price,
           std::int64_t size, std::uint8_t side) {
    ++n_records_;
    InstAccum& in = *find_or_create(iid);
    ++in.updates;
    ++in.upd[static_cast<std::size_t>(sec)];

    // §0 SENTINEL LAW: classify BEFORE any price arithmetic.
    const BookState bs = classify_book(bid, ask);
    if (bs.state != kStTwoSided) {
      ++n_dropped_sentinel_;
    }

    std::int32_t& sl = in.slot[static_cast<std::size_t>(sec)];
    if (sl < 0) {
      sl = static_cast<std::int32_t>(in.entries.size());
      in.entries.push_back(SecEntry{bs.bid, bs.ask, bsz, asz, static_cast<std::uint8_t>(flast ? 1 : 0), bs.state});
      in.entry_sec.push_back(sec);
    } else if (flast || in.entries[static_cast<std::size_t>(sl)].has_flast == 0u) {
      in.entries[static_cast<std::size_t>(sl)] =
          SecEntry{bs.bid, bs.ask, bsz, asz, static_cast<std::uint8_t>(flast ? 1 : 0), bs.state};
    }

    // Empirical tick: GCD of |successive valid price changes| per instrument.
    if (bs.bid != kUndefPrice) {
      if (in.has_prev_bid && bs.bid != in.prev_bid) {
        in.px_gcd = std::gcd(in.px_gcd, std::abs(bs.bid - in.prev_bid));
      }
      in.prev_bid = bs.bid;
      in.has_prev_bid = true;
    }
    if (bs.ask != kUndefPrice) {
      if (in.has_prev_ask && bs.ask != in.prev_ask) {
        in.px_gcd = std::gcd(in.px_gcd, std::abs(bs.ask - in.prev_ask));
      }
      in.prev_ask = bs.ask;
      in.has_prev_ask = true;
    }

    if (action == kActionTrade) {
      ++in.n_trades;
      in.trade_size_sum += size;
      if (price > 0 && price < kSentHi) {
        in.trades.push_back(TradeRec{sec, price, size, side});
      }
    }
  }

 private:
  InstAccum* find_or_create(std::int64_t iid) {
    // Consecutive records overwhelmingly come from the same instrument.
    if (cached_ >= 0 && iids_[static_cast<std::size_t>(cached_)] == iid) {
      return insts_[static_cast<std::size_t>(cached_)].get();
    }
    const auto it = std::lower_bound(iids_.begin(), iids_.end(), iid);
    const auto pos = static_cast<std::size_t>(it - iids_.begin());
    if (it != iids_.end() && *it == iid) {
      cached_ = static_cast<int>(pos);
      return insts_[pos].get();
    }
    // Sorted insert: the id vector IS the receipt's row order, so it is kept
    // ordered here rather than sorted later from an arrival-ordered container.
    iids_.insert(it, iid);
    insts_.insert(insts_.begin() + static_cast<std::ptrdiff_t>(pos),
                  std::make_unique<InstAccum>());
    cached_ = static_cast<int>(pos);
    return insts_[pos].get();
  }

  std::int64_t day_;
  std::vector<std::int64_t> iids_;
  std::vector<std::unique_ptr<InstAccum>> insts_;
  std::int64_t n_records_ = 0;
  std::int64_t n_dropped_sentinel_ = 0;
  int cached_ = -1;
};

/// numpy's median: mean of the two central order statistics on even counts.
double median_of(std::vector<double>& v) {
  if (v.empty()) {
    return std::nan("");
  }
  const std::size_t n = v.size();
  const std::size_t mid = n / 2;
  std::nth_element(v.begin(), v.begin() + static_cast<std::ptrdiff_t>(mid), v.end());
  const double hi = v[mid];
  if (n % 2 == 1) {
    return hi;
  }
  const double lo = *std::max_element(v.begin(), v.begin() + static_cast<std::ptrdiff_t>(mid));
  return (lo + hi) / 2.0;
}

/// Forward-filled 1s grids for the tracked instruments (s2_decode.build_grids).
void build_grids(const DayAccum& acc, const std::vector<std::size_t>& tracked_pos,
                 DayReceipt& out) {
  const std::size_t n = tracked_pos.size();
  const auto secs = static_cast<std::size_t>(kSecondsPerDay);
  out.bid_px.assign(n * secs, kUndefPrice);
  out.ask_px.assign(n * secs, kUndefPrice);
  out.bid_sz.assign(n * secs, 0);
  out.ask_sz.assign(n * secs, 0);
  out.state.assign(n * secs, kStPreFirst);
  out.upd_count.assign(n * secs, 0);
  out.carry_bid.assign(n, kUndefPrice);
  out.carry_ask.assign(n, kUndefPrice);
  out.carry_bsz.assign(n, 0);
  out.carry_asz.assign(n, 0);
  out.carry_state.assign(n, kStPreFirst);
  out.carry_last_sec.assign(n, -1);
  out.n_no_flast_seconds = 0;

  std::vector<std::int32_t> order;
  for (std::size_t i = 0; i < n; ++i) {
    const InstAccum& in = acc.inst(tracked_pos[i]);
    const std::size_t base = i * secs;
    for (std::size_t s = 0; s < secs; ++s) {
      out.upd_count[base + s] = in.upd[s];
    }
    if (in.entry_sec.empty()) {
      continue;
    }
    order.assign(in.entry_sec.begin(), in.entry_sec.end());
    std::sort(order.begin(), order.end());
    for (const std::int32_t s : order) {
      if (in.entries[static_cast<std::size_t>(in.slot[static_cast<std::size_t>(s)])].has_flast ==
          0u) {
        ++out.n_no_flast_seconds;
      }
    }
    // Forward fill from the instrument's first record of the day to midnight:
    // state persists between events; PRE_FIRST before the first record.
    for (std::size_t k = 0; k < order.size(); ++k) {
      const auto from = static_cast<std::size_t>(order[k]);
      const std::size_t to = (k + 1 < order.size()) ? static_cast<std::size_t>(order[k + 1]) : secs;
      const SecEntry& e = in.entries[static_cast<std::size_t>(in.slot[from])];
      for (std::size_t s = from; s < to; ++s) {
        out.bid_px[base + s] = e.bid;
        out.ask_px[base + s] = e.ask;
        out.bid_sz[base + s] = e.bsz;
        out.ask_sz[base + s] = e.asz;
        out.state[base + s] = e.state;
      }
    }
    const auto last = static_cast<std::size_t>(order.back());
    const SecEntry& e = in.entries[static_cast<std::size_t>(in.slot[last])];
    out.carry_bid[i] = e.bid;
    out.carry_ask[i] = e.ask;
    out.carry_bsz[i] = e.bsz;
    out.carry_asz[i] = e.asz;
    out.carry_state[i] = e.state;
    out.carry_last_sec[i] = static_cast<std::int64_t>(last);
  }
}

/// Turn one DayAccum into a receipt on disk (s2_decode.finish_day).
Expected<bool, Refusal> finish_day(Asset asset, const DayAccum& acc,
                                   const qr::dbn::SymbolIndex& symidx, const std::string& out_dir,
                                   std::vector<IntegrityFlag>* flags) {
  const std::vector<std::int64_t>& iids = acc.iids();
  if (iids.empty()) {
    return false;
  }
  const AssetSpec& spec = asset_spec(asset);
  const Date date = day_to_date(acc.day());
  const std::int32_t ymd = date.yyyymmdd();

  DayReceipt rec;
  rec.date = date;
  rec.n_records = acc.n_records();
  rec.n_dropped_sentinel = acc.n_dropped_sentinel();

  const std::size_t k = iids.size();
  rec.tally_iid = iids;
  rec.map_iid = iids;
  rec.tally_updates.resize(k);
  rec.tally_trades.resize(k);
  rec.tally_trade_size_sum.resize(k);
  rec.map_symbol.resize(k);
  rec.map_outright.resize(k);
  for (std::size_t i = 0; i < k; ++i) {
    const InstAccum& in = acc.inst(i);
    rec.tally_updates[i] = in.updates;
    rec.tally_trades[i] = in.n_trades;
    rec.tally_trade_size_sum[i] = in.trade_size_sum;
    rec.map_symbol[i] = symidx.symbol_for(static_cast<std::uint32_t>(iids[i]), ymd);
    rec.map_outright[i] = qr::dbn::SymbolIndex::is_outright(rec.map_symbol[i]) ? 1u : 0u;
  }

  // Tracked set: SI = top 3 by day update count (ties -> lower id), then
  // sorted; HG/NKD = every instrument that appears.
  std::vector<std::size_t> tracked_pos;
  if (asset == Asset::SI) {
    std::vector<std::size_t> ranked(k);
    std::iota(ranked.begin(), ranked.end(), std::size_t{0});
    std::sort(ranked.begin(), ranked.end(), [&](std::size_t a, std::size_t b) {
      if (rec.tally_updates[a] != rec.tally_updates[b]) {
        return rec.tally_updates[a] > rec.tally_updates[b];
      }
      return iids[a] < iids[b];
    });
    const std::size_t take = std::min(kSiTrackTop, ranked.size());
    tracked_pos.assign(ranked.begin(), ranked.begin() + static_cast<std::ptrdiff_t>(take));
    std::sort(tracked_pos.begin(), tracked_pos.end());
  } else {
    tracked_pos.resize(k);
    std::iota(tracked_pos.begin(), tracked_pos.end(), std::size_t{0});
    if (tracked_pos.size() > 2 && flags != nullptr) {
      std::string detail;
      for (std::size_t i = 0; i < tracked_pos.size(); ++i) {
        if (i != 0) {
          detail += ';';
        }
        detail += std::to_string(iids[tracked_pos[i]]);
      }
      flags->push_back(
          IntegrityFlag{spec.name, date.iso(), "MORE_THAN_2_INSTRUMENTS", std::move(detail)});
    }
  }

  rec.tracked_ids.reserve(tracked_pos.size());
  rec.carry_iid.reserve(tracked_pos.size());
  for (const std::size_t p : tracked_pos) {
    rec.tracked_ids.push_back(iids[p]);
    rec.carry_iid.push_back(iids[p]);
  }
  build_grids(acc, tracked_pos, rec);

  // Integrity: empirical tick GCD over OUTRIGHT instruments only.
  std::int64_t g = 0;
  for (std::size_t i = 0; i < k; ++i) {
    if (rec.map_outright[i] != 0u) {
      g = std::gcd(g, acc.inst(i).px_gcd);
    }
  }
  rec.tick_gcd_raw = g;
  const double tick_usd =
      (g != 0) ? static_cast<double>(g) * spec.px_scale * static_cast<double>(spec.mult) : 0.0;
  if (flags != nullptr && !(g != 0 && std::abs(tick_usd - spec.tick_usd) < 1e-9)) {
    char buf[160];
    std::snprintf(buf, sizeof(buf), "gcd=%lld tick_$=%.6f expected=%.2f",
                  static_cast<long long>(g), tick_usd, spec.tick_usd);
    flags->push_back(IntegrityFlag{spec.name, date.iso(), "TICK_GCD_MISMATCH", buf});
  }

  // Trades of the tracked instruments, in tracked-row order.
  for (const std::size_t p : tracked_pos) {
    const InstAccum& in = acc.inst(p);
    for (const TradeRec& t : in.trades) {
      rec.trades_iid.push_back(iids[p]);
      rec.trades_sec.push_back(t.sec);
      rec.trades_px.push_back(t.px);
      rec.trades_size.push_back(t.size);
      rec.trades_side.push_back(t.side);
    }
  }

  // Integrity: sane-band assert on the daily median mid of the busiest tracked
  // instrument (ties -> lower id).
  if (flags != nullptr && !tracked_pos.empty()) {
    std::size_t top = 0;
    for (std::size_t i = 1; i < tracked_pos.size(); ++i) {
      const std::int64_t ui = rec.tally_updates[tracked_pos[i]];
      const std::int64_t ub = rec.tally_updates[tracked_pos[top]];
      if (ui > ub || (ui == ub && iids[tracked_pos[i]] < iids[tracked_pos[top]])) {
        top = i;
      }
    }
    std::vector<double> mids;
    const auto secs = static_cast<std::size_t>(kSecondsPerDay);
    const std::size_t base = top * secs;
    for (std::size_t s = 0; s < secs; ++s) {
      if (rec.state[base + s] == kStTwoSided) {
        mids.push_back((static_cast<double>(rec.bid_px[base + s]) +
                        static_cast<double>(rec.ask_px[base + s])) /
                       2 * spec.px_scale);
      }
    }
    const double med = median_of(mids);
    const bool band_ok = std::isfinite(med) && spec.band_lo <= med && med <= spec.band_hi;
    if (!band_ok) {
      char buf[160];
      std::snprintf(buf, sizeof(buf), "median_mid=%.6f band=(%.1f, %.1f)", med, spec.band_lo,
                    spec.band_hi);
      flags->push_back(IntegrityFlag{spec.name, date.iso(), "MID_OUT_OF_BAND", buf});
    }
  }

  const std::string path = out_dir + "/" + date.compact() + ".qrday";
  auto wrote = write_day_receipt(path, rec);
  if (!wrote) {
    return refuse<bool>(wrote.error());
  }
  return true;
}

}  // namespace

Expected<DecodeResult, Refusal> decode_payload_file(Asset asset, const std::string& path,
                                                    const std::string& out_dir) {
  DecodeResult out;
  const std::size_t slash = path.find_last_of('/');
  out.file = (slash == std::string::npos) ? path : path.substr(slash + 1);

  auto sealed = guard_seal(path, nullptr);
  if (!sealed) {
    return refuse<DecodeResult>(sealed.error());
  }

  const std::vector<int> dates = filename_dates(path);
  if (dates.size() != 1 && dates.size() != 2) {
    return refuse<DecodeResult>(Refusal(RefusalCode::REGISTRY_MALFORMED,
                                        "qr_futsess::decode_payload_file",
                                        "cannot read a date range from the payload filename",
                                        static_cast<std::int64_t>(dates.size())));
  }
  const std::int64_t day0 = date_to_day(date_from_yyyymmdd(dates.front()));
  const std::int64_t day1 = date_to_day(date_from_yyyymmdd(dates.back()));

  qr::dbn::DbnStream stream;
  auto opened = stream.open(path);
  if (!opened) {
    return refuse<DecodeResult>(opened.error());
  }
  qr::dbn::SymbolIndex symidx;
  symidx.build(stream.metadata());

  std::unique_ptr<DayAccum> acc;
  std::int64_t cur_day = 0;
  const AssetSpec& spec = asset_spec(asset);

  for (;;) {
    auto next = stream.next_mbp1();
    if (!next) {
      return refuse<DecodeResult>(next.error());
    }
    const qr::dbn::Mbp1Msg* rec = next.value();
    if (rec == nullptr) {
      break;
    }
    ++out.n_records;
    const std::uint64_t ts = rec->hd.ts_event / 1000000000ull;
    const std::uint64_t day_u = ts / 86400ull;
    const auto day = static_cast<std::int64_t>(day_u);
    if (day_u > static_cast<std::uint64_t>(INT64_MAX) || day < day0 || day > day1) {
      ++out.n_foreign;
      continue;
    }
    if (acc == nullptr) {
      acc = std::make_unique<DayAccum>(day);
      cur_day = day;
    } else if (day > cur_day) {
      auto done = finish_day(asset, *acc, symidx, out_dir, &out.flags);
      if (!done) {
        return refuse<DecodeResult>(done.error());
      }
      if (done.value()) {
        out.days_written.push_back(day_to_date(cur_day).compact());
      }
      acc = std::make_unique<DayAccum>(day);
      cur_day = day;
    } else if (day < cur_day) {
      // ts_event went backwards across a day boundary: that day's receipt is
      // already written, so the record cannot be folded in. Log and drop.
      out.flags.push_back(IntegrityFlag{spec.name, day_to_date(day).iso(),
                                        "OUT_OF_ORDER_DAY_RECORD_DROPPED", out.file});
      continue;
    }
    const auto sec = static_cast<std::int32_t>(ts % 86400ull);
    const qr::dbn::BidAskPair& lv = rec->levels[0];
    acc->add(static_cast<std::int64_t>(rec->hd.instrument_id), sec, lv.bid_px, lv.ask_px,
             static_cast<std::int64_t>(lv.bid_sz), static_cast<std::int64_t>(lv.ask_sz),
             (rec->flags & kFLast) != 0u, rec->action, rec->price,
             static_cast<std::int64_t>(rec->size), rec->side);
  }
  if (acc != nullptr) {
    auto done = finish_day(asset, *acc, symidx, out_dir, &out.flags);
    if (!done) {
      return refuse<DecodeResult>(done.error());
    }
    if (done.value()) {
      out.days_written.push_back(day_to_date(cur_day).compact());
    }
  }
  if (out.n_foreign != 0) {
    out.flags.push_back(IntegrityFlag{
        spec.name, day_to_date(day0).iso() + ".." + day_to_date(day1).iso(),
        "FOREIGN_DAY_RECORDS_DROPPED", std::to_string(out.n_foreign) + " in " + out.file});
  }
  return out;
}

}  // namespace qr::futsess
