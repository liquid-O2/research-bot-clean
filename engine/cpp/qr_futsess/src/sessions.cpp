#include "qr_futsess/sessions.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <deque>
#include <dirent.h>
#include <limits>
#include <memory>

#include "qr_futsess/dayrec.hpp"
#include "qr_futsess/json.hpp"

namespace qr::futsess {
namespace {

/// The sha256 of the frozen s3 PARAMS dict, echoed into every reference session
/// receipt (s3_sessions.py:492 via common.params_hash). It identifies WHICH
/// frozen parameter set a receipt reproduces; it is a Python-side provenance
/// string, so the port carries it as a pinned constant rather than inventing a
/// second hashing convention. Verified identical across SI/HG/NKD receipts.
constexpr const char* kS3ParamsHash =
    "f003a459bcf7d2716dea7bd7ba40771bf76427a1918aa75bb99343b07d0a2f58";

constexpr const char* kPhaseNames[3] = {"TOKYO", "LONDON", "NY"};

double nan_value() { return std::numeric_limits<double>::quiet_NaN(); }

// ------------------------------------------------------------- day cache ----
/// Keeps the last few day receipts in memory; sessions walk forward, so a
/// session touches at most three consecutive days (its two, plus the day before
/// for the end-of-day carry fill). Cache depth affects speed only — every read
/// returns the same receipt.
class DayCache {
 public:
  DayCache(std::string dir, std::size_t limit) : dir_(std::move(dir)), limit_(limit) {}

  /// The receipt for `d`, or nullptr when that day has none.
  const DayReceipt* get(const Date& d) {
    const std::int64_t key = date_to_day(d);
    for (const auto& e : entries_) {
      if (e.key == key) {
        return e.rec.get();
      }
    }
    Entry e;
    e.key = key;
    const std::string path = dir_ + "/" + d.compact() + ".qrday";
    auto rec = read_day_receipt(path);
    if (rec) {
      e.rec = std::make_unique<DayReceipt>(std::move(rec).value());
    }
    entries_.push_back(std::move(e));
    while (entries_.size() > limit_) {
      entries_.pop_front();
    }
    return entries_.back().rec.get();
  }

  /// Sorted dates of every day receipt on disk (M0 `DayCache.dates`).
  [[nodiscard]] std::vector<Date> dates() const {
    std::vector<Date> out;
    DIR* dp = ::opendir(dir_.c_str());
    if (dp == nullptr) {
      return out;
    }
    while (const dirent* de = ::readdir(dp)) {
      const std::string name = de->d_name;
      if (name.size() != 14 || name.compare(8, 6, ".qrday") != 0) {
        continue;
      }
      bool digits = true;
      for (std::size_t i = 0; i < 8; ++i) {
        digits = digits && (name[i] >= '0' && name[i] <= '9');
      }
      if (!digits) {
        continue;
      }
      out.push_back(date_from_yyyymmdd(std::stoi(name.substr(0, 8))));
    }
    ::closedir(dp);
    // Sorted directory iteration is a repository law: readdir order is not
    // reproducible, and the session calendar is built from this list.
    std::sort(out.begin(), out.end());
    return out;
  }

 private:
  struct Entry {
    std::int64_t key = 0;
    std::unique_ptr<DayReceipt> rec;
  };
  std::string dir_;
  std::size_t limit_;
  std::deque<Entry> entries_;
};

// ---------------------------------------------------------------- stitch ----
struct Grid {
  std::vector<std::int64_t> bid_px;
  std::vector<std::int64_t> ask_px;
  std::vector<std::int64_t> bid_sz;
  std::vector<std::int64_t> ask_sz;
  std::vector<std::int8_t> state;
  std::vector<std::int32_t> upd;
};

/// Session-second views of one instrument's per-day grids.
/// PRE_FIRST seconds at a UTC-day boundary are filled from the EARLIER
/// receipt's end-of-day carry for the same instrument (M0 §5 / s3 `stitch`).
Grid stitch(DayCache& cache, const Date& trade_date, std::int64_t iid, bool want_upd) {
  const auto [o, c] = session_bounds(trade_date);
  const auto n = static_cast<std::size_t>(c - o);
  Grid g;
  g.bid_px.assign(n, kUndefPrice);
  g.ask_px.assign(n, kUndefPrice);
  g.bid_sz.assign(n, 0);
  g.ask_sz.assign(n, 0);
  g.state.assign(n, kStPreFirst);
  if (want_upd) {
    g.upd.assign(n, 0);
  }

  std::int64_t t = o;
  while (t < c) {
    const std::int64_t day = t / 86400;
    const Date d = day_to_date(day);
    const std::int64_t end = std::min(c, (day + 1) * 86400);
    const auto lo = static_cast<std::size_t>(t - day * 86400);
    const auto seg = static_cast<std::size_t>(end - t);
    const auto off = static_cast<std::size_t>(t - o);
    const DayReceipt* rec = cache.get(d);
    const int row = (rec != nullptr) ? rec->row_index(iid) : -1;
    if (rec != nullptr && row >= 0) {
      const auto base = static_cast<std::size_t>(row) * static_cast<std::size_t>(kSecondsPerDay);
      std::memcpy(g.bid_px.data() + off, rec->bid_px.data() + base + lo, seg * sizeof(std::int64_t));
      std::memcpy(g.ask_px.data() + off, rec->ask_px.data() + base + lo, seg * sizeof(std::int64_t));
      std::memcpy(g.bid_sz.data() + off, rec->bid_sz.data() + base + lo, seg * sizeof(std::int64_t));
      std::memcpy(g.ask_sz.data() + off, rec->ask_sz.data() + base + lo, seg * sizeof(std::int64_t));
      std::memcpy(g.state.data() + off, rec->state.data() + base + lo, seg * sizeof(std::int8_t));
      if (want_upd) {
        std::memcpy(g.upd.data() + off, rec->upd_count.data() + base + lo,
                    seg * sizeof(std::int32_t));
      }
      // Boundary PRE_FIRST fill from the previous day's carry.
      if (seg > 0 && g.state[off] == kStPreFirst) {
        const DayReceipt* prev = cache.get(day_to_date(day - 1));
        const int j = (prev != nullptr) ? prev->carry_index(iid) : -1;
        if (j >= 0 && prev->carry_state[static_cast<std::size_t>(j)] != kStPreFirst) {
          std::size_t m = seg;
          for (std::size_t s = 0; s < seg; ++s) {
            if (g.state[off + s] != kStPreFirst) {
              m = s;
              break;
            }
          }
          const auto jj = static_cast<std::size_t>(j);
          for (std::size_t s = 0; s < m; ++s) {
            g.bid_px[off + s] = prev->carry_bid[jj];
            g.ask_px[off + s] = prev->carry_ask[jj];
            g.bid_sz[off + s] = prev->carry_bsz[jj];
            g.ask_sz[off + s] = prev->carry_asz[jj];
            g.state[off + s] = prev->carry_state[jj];
            if (want_upd) {
              g.upd[off + s] = 0;
            }
          }
        }
      }
    }
    t = end;
  }
  return g;
}

/// Session update-count total for one instrument. Same slicing as stitch()
/// with keys=["upd_count"], where the carry fill does not apply (it is gated on
/// the state array, which that call does not request).
std::int64_t session_upd_sum(DayCache& cache, const Date& trade_date, std::int64_t iid) {
  const auto [o, c] = session_bounds(trade_date);
  std::int64_t total = 0;
  std::int64_t t = o;
  while (t < c) {
    const std::int64_t day = t / 86400;
    const std::int64_t end = std::min(c, (day + 1) * 86400);
    const auto lo = static_cast<std::size_t>(t - day * 86400);
    const auto seg = static_cast<std::size_t>(end - t);
    const DayReceipt* rec = cache.get(day_to_date(day));
    const int row = (rec != nullptr) ? rec->row_index(iid) : -1;
    if (row >= 0) {
      const auto base = static_cast<std::size_t>(row) * static_cast<std::size_t>(kSecondsPerDay);
      for (std::size_t s = 0; s < seg; ++s) {
        total += rec->upd_count[base + lo + s];
      }
    }
    t = end;
  }
  return total;
}

struct Trades {
  std::vector<std::int64_t> sec;
  std::vector<std::int64_t> px;
  std::vector<std::int64_t> size;
  std::vector<std::uint8_t> side;
};

Trades session_trades(DayCache& cache, const Date& trade_date, std::int64_t iid) {
  const auto [o, c] = session_bounds(trade_date);
  Trades out;
  std::int64_t t = o;
  while (t < c) {
    const std::int64_t day = t / 86400;
    const std::int64_t end = std::min(c, (day + 1) * 86400);
    const std::int64_t lo = t - day * 86400;
    const std::int64_t hi = end - day * 86400;
    const DayReceipt* rec = cache.get(day_to_date(day));
    if (rec != nullptr) {
      const std::int64_t shift = day * 86400 - o;
      for (std::size_t k = 0; k < rec->trades_iid.size(); ++k) {
        if (rec->trades_iid[k] != iid) {
          continue;
        }
        const std::int64_t s = rec->trades_sec[k];
        if (s < lo || s >= hi) {
          continue;
        }
        out.sec.push_back(s + shift);
        out.px.push_back(rec->trades_px[k]);
        out.size.push_back(rec->trades_size[k]);
        out.side.push_back(rec->trades_side[k]);
      }
    }
    t = end;
  }
  return out;
}

// ------------------------------------------------------------- dominance ----
struct Candidates {
  std::vector<std::int64_t> ids;                    // sorted
  std::map<std::int64_t, std::string> symbols;      // first day seen wins
  std::map<std::int64_t, bool> outright;
};

Candidates candidates(DayCache& cache, const Date& trade_date) {
  const auto [o, c] = session_bounds(trade_date);
  Candidates out;
  std::vector<std::int64_t> days{o / 86400, (c - 1) / 86400};
  std::sort(days.begin(), days.end());
  days.erase(std::unique(days.begin(), days.end()), days.end());
  for (const std::int64_t day : days) {
    const DayReceipt* rec = cache.get(day_to_date(day));
    if (rec == nullptr) {
      continue;
    }
    for (const std::int64_t iid : rec->tracked_ids) {
      out.ids.push_back(iid);
    }
    for (std::size_t i = 0; i < rec->map_iid.size(); ++i) {
      out.symbols.emplace(rec->map_iid[i], rec->map_symbol[i]);
      out.outright.emplace(rec->map_iid[i], rec->map_outright[i] != 0u);
    }
  }
  std::sort(out.ids.begin(), out.ids.end());
  out.ids.erase(std::unique(out.ids.begin(), out.ids.end()), out.ids.end());
  return out;
}

struct Pick {
  std::int64_t winner = -1;      // -1 == None
  std::int64_t runner_up = -1;
  double share = 0.0;
  bool has_winner = false;
};

Pick pick_from(const std::vector<std::int64_t>& pool,
               const std::map<std::int64_t, std::int64_t>& metric) {
  std::vector<std::int64_t> live;
  for (const std::int64_t i : pool) {
    const auto it = metric.find(i);
    if (it != metric.end() && it->second > 0) {
      live.push_back(i);
    }
  }
  Pick p;
  if (live.empty()) {
    return p;
  }
  std::int64_t best = std::numeric_limits<std::int64_t>::min();
  for (const std::int64_t i : live) {
    best = std::max(best, metric.at(i));
  }
  // Winner: the best metric, ties broken by the LOWER instrument id — never by
  // arrival or source order (repository law).
  std::int64_t win = std::numeric_limits<std::int64_t>::max();
  for (const std::int64_t i : live) {
    if (metric.at(i) == best) {
      win = std::min(win, i);
    }
  }
  std::int64_t run = -1;
  bool has_run = false;
  for (const std::int64_t i : live) {
    if (i == win) {
      continue;
    }
    if (!has_run || metric.at(i) > metric.at(run) ||
        (metric.at(i) == metric.at(run) && i < run)) {
      run = i;
      has_run = true;
    }
  }
  std::int64_t tot = 0;
  for (const std::int64_t i : live) {
    tot += metric.at(i);
  }
  p.winner = win;
  p.has_winner = true;
  p.runner_up = has_run ? run : -1;
  p.share = (tot != 0) ? static_cast<double>(best) / static_cast<double>(tot) : 0.0;
  return p;
}

// -------------------------------------------------------- session records ---
struct SessionRec {
  Date trade_date;
  std::int64_t open_utc = 0;
  std::int64_t close_utc = 0;
  std::int64_t dominant_id = 0;
  std::int64_t runner_up_id = -1;
  double dominant_share = 0.0;
  std::int64_t dominant_all_id = -1;
  double dominant_all_share = 0.0;
  std::int64_t dominant_outright_id = -1;
  double dominant_outright_share = 0.0;
  std::int64_t n_instruments = 0;
  std::int64_t n_valid_seconds = 0;
  std::int64_t first_two_sided_sec = 0;
  std::int64_t last_two_sided_sec = 0;
  double H = 0.0;
  double L = 0.0;
  double Cl = 0.0;
  std::string symbol;
  bool short_day = false;
  std::int64_t prev_session_dominant = -1;
  bool instrument_change = false;
  bool roll_window = false;
  bool dying_book_week = false;
  bool whipsaw_flag = false;
  // bar-only fields; absent (null) on sessions that contribute no bar
  bool has_bar = false;
  double tr_px = 0.0;
  double atr_prev_px = 0.0;
};

// ------------------------------------------------------------ bin writer ----
struct ArrayDesc {
  std::string name;
  const char* dtype;
  std::size_t count;
  std::size_t offset;
};

class BinWriter {
 public:
  template <class T>
  void add(const std::string& name, const char* dtype, const std::vector<T>& v) {
    descs_.push_back(ArrayDesc{name, dtype, v.size(), bytes_.size()});
    const auto* p = reinterpret_cast<const std::uint8_t*>(v.data());
    bytes_.insert(bytes_.end(), p, p + v.size() * sizeof(T));
  }
  [[nodiscard]] const std::vector<ArrayDesc>& descs() const { return descs_; }
  [[nodiscard]] const std::vector<std::uint8_t>& bytes() const { return bytes_; }

 private:
  std::vector<ArrayDesc> descs_;
  std::vector<std::uint8_t> bytes_;
};

Expected<std::monostate, Refusal> write_file(const std::string& path, const void* data,
                                             std::size_t n) {
  const std::string tmp = path + ".tmp";
  std::FILE* fh = std::fopen(tmp.c_str(), "wb");
  if (fh == nullptr) {
    return refuse<std::monostate>(
        Refusal(RefusalCode::IO, "qr_futsess::write_file", "cannot create output file"));
  }
  const bool ok = (n == 0) || (std::fwrite(data, 1, n, fh) == n);
  const bool closed = (std::fclose(fh) == 0);
  if (!ok || !closed) {
    std::remove(tmp.c_str());
    return refuse<std::monostate>(
        Refusal(RefusalCode::IO, "qr_futsess::write_file", "short write on output file"));
  }
  if (std::rename(tmp.c_str(), path.c_str()) != 0) {
    return refuse<std::monostate>(
        Refusal(RefusalCode::IO, "qr_futsess::write_file", "cannot rename output file"));
  }
  return std::monostate{};
}

}  // namespace

// ------------------------------------------------------------ public bits ---
bool in_cyclic(std::int64_t x, std::int64_t lo, std::int64_t hi) {
  if (lo <= hi) {
    return lo <= x && x < hi;
  }
  return x >= lo || x < hi;
}

std::int8_t phase_of(std::int64_t sec_of_day, const std::array<std::int64_t, 3>& bounds) {
  const std::int64_t tl = bounds[0];
  const std::int64_t ln = bounds[1];
  const std::int64_t nt = bounds[2];
  if (in_cyclic(sec_of_day, nt, tl)) {
    return 0;  // TOKYO
  }
  if (in_cyclic(sec_of_day, tl, ln)) {
    return 1;  // LONDON
  }
  return 2;    // NY
}

std::vector<double> wilder_atr(const std::vector<double>& trs, int period) {
  std::vector<double> out(trs.size(), nan_value());
  const auto p = static_cast<std::size_t>(period);
  if (trs.size() < p) {
    return out;
  }
  // Left-to-right summation, matching Python's builtin sum() exactly.
  double acc = 0.0;
  for (std::size_t i = 0; i < p; ++i) {
    acc += trs[i];
  }
  double prev = acc / static_cast<double>(period);
  out[p - 1] = prev;
  for (std::size_t i = p; i < trs.size(); ++i) {
    prev = (prev * static_cast<double>(period - 1) + trs[i]) / static_cast<double>(period);
    out[i] = prev;
  }
  return out;
}

Expected<PhaseTable, Refusal> load_phase_table(const std::string& path) {
  auto doc = json_parse_file(path);
  if (!doc) {
    return refuse<PhaseTable>(doc.error());
  }
  const Json& root = doc.value();
  const Json* years = root.find("years");
  if (years == nullptr || years->type() != Json::Type::Object) {
    return refuse<PhaseTable>(Refusal(RefusalCode::CONTENT_MISMATCH,
                                      "qr_futsess::load_phase_table",
                                      "frozen phase table has no `years` object"));
  }
  PhaseTable out;
  for (const auto& [year_str, node] : years->fields()) {
    const Json* b = node.find("boundaries_utc_sec");
    if (b == nullptr || b->type() != Json::Type::Object) {
      return refuse<PhaseTable>(Refusal(RefusalCode::CONTENT_MISMATCH,
                                        "qr_futsess::load_phase_table",
                                        "a year has no boundaries_utc_sec object"));
    }
    const char* keys[3] = {"TOKYO|LONDON", "LONDON|NY", "NY|TOKYO"};
    std::array<std::int64_t, 3> bounds{};
    for (int i = 0; i < 3; ++i) {
      const Json* v = b->find(keys[i]);
      if (v == nullptr || v->type() != Json::Type::Number) {
        return refuse<PhaseTable>(Refusal(RefusalCode::CONTENT_MISMATCH,
                                          "qr_futsess::load_phase_table",
                                          "a phase boundary is missing or not a number"));
      }
      bounds[static_cast<std::size_t>(i)] = static_cast<std::int64_t>(v->number());
    }
    out.by_year.emplace(std::stoi(year_str), bounds);
  }
  return out;
}

Expected<DominanceRule, Refusal> load_pinned_rule(const std::string& receipt_path) {
  auto doc = json_parse_file(receipt_path);
  if (!doc) {
    return refuse<DominanceRule>(doc.error());
  }
  const Json* verdict = doc.value().find("verdict");
  if (verdict == nullptr || verdict->str() != "MATCH") {
    return refuse<DominanceRule>(Refusal(RefusalCode::CONTENT_MISMATCH,
                                         "qr_futsess::load_pinned_rule",
                                         "s1 did not MATCH; §5 has no pinned dominance rule"));
  }
  const Json* rule = doc.value().find("winning_rule");
  if (rule == nullptr || rule->type() != Json::Type::String) {
    return refuse<DominanceRule>(Refusal(RefusalCode::CONTENT_MISMATCH,
                                         "qr_futsess::load_pinned_rule",
                                         "s1 receipt carries no winning_rule"));
  }
  const std::string& s = rule->str();
  const std::size_t slash = s.find_last_of('/');
  const std::string tail = (slash == std::string::npos) ? s : s.substr(slash + 1);
  if (tail == "R1") {
    return DominanceRule::R1;
  }
  if (tail == "R2") {
    return DominanceRule::R2;
  }
  if (tail == "R3") {
    return DominanceRule::R3;
  }
  if (tail == "R4") {
    return DominanceRule::R4;
  }
  return refuse<DominanceRule>(Refusal(RefusalCode::CONTENT_MISMATCH,
                                       "qr_futsess::load_pinned_rule",
                                       "s1 receipt names an unknown dominance rule"));
}

// ----------------------------------------------------------------- driver ---
Expected<AssembleResult, Refusal> assemble_asset(const AssembleOptions& opt) {
  const AssetSpec& spec = asset_spec(opt.asset);
  auto phases = load_phase_table(opt.phases_path);
  if (!phases) {
    return refuse<AssembleResult>(phases.error());
  }
  const PhaseTable& ptab = phases.value();

  DayCache cache(opt.day_dir, 4);
  const std::vector<Date> calendar = cache.dates();
  if (calendar.empty()) {
    return refuse<AssembleResult>(Refusal(RefusalCode::UNKNOWN_SESSION,
                                          "qr_futsess::assemble_asset",
                                          "no day receipts for this asset"));
  }
  std::map<std::int32_t, int> cal_index;
  for (std::size_t i = 0; i < calendar.size(); ++i) {
    cal_index.emplace(calendar[i].yyyymmdd(), static_cast<int>(i));
  }

  // ---------------------------------------------------------------- pass 1
  std::vector<SessionRec> sess;
  std::vector<std::string> sess_symbol_of_dominant;
  for (std::size_t ci = 0; ci < calendar.size(); ++ci) {
    const Date& td = calendar[ci];
    const Candidates cand = candidates(cache, td);
    if (cand.ids.empty()) {
      continue;
    }
    std::map<std::int64_t, std::int64_t> metric;
    for (const std::int64_t iid : cand.ids) {
      if (opt.rule == DominanceRule::R1 || opt.rule == DominanceRule::R2) {
        metric[iid] = session_upd_sum(cache, td, iid);
      } else {
        const Trades t = session_trades(cache, td, iid);
        std::int64_t total = 0;
        for (const std::int64_t z : t.size) {
          total += z;
        }
        metric[iid] = total;
      }
    }
    std::vector<std::int64_t> outrights;
    for (const std::int64_t iid : cand.ids) {
      const auto it = cand.outright.find(iid);
      if (it != cand.outright.end() && it->second) {
        outrights.push_back(iid);
      }
    }
    const Pick all = pick_from(cand.ids, metric);
    const Pick outr = pick_from(outrights, metric);
    // Session dominance is the PINNED OUTRIGHTS-ONLY rule; the all-instrument
    // winner is only the fallback when no outright traded (M0 §5).
    const bool use_outright = outr.has_winner;
    if (!use_outright && !all.has_winner) {
      continue;
    }
    const std::int64_t dom = use_outright ? outr.winner : all.winner;

    const Grid g = stitch(cache, td, dom, false);
    std::int64_t n_valid = 0;
    std::int64_t first_ts = -1;
    std::int64_t last_ts = -1;
    double hi = 0.0;
    double lo = 0.0;
    double last_mid = 0.0;
    for (std::size_t s = 0; s < g.state.size(); ++s) {
      if (g.state[s] != kStTwoSided) {
        continue;
      }
      const double mid = (static_cast<double>(g.bid_px[s]) + static_cast<double>(g.ask_px[s])) / 2 *
                         spec.px_scale;
      if (n_valid == 0) {
        hi = mid;
        lo = mid;
        first_ts = static_cast<std::int64_t>(s);
      } else {
        hi = std::max(hi, mid);
        lo = std::min(lo, mid);
      }
      last_mid = mid;
      last_ts = static_cast<std::int64_t>(s);
      ++n_valid;
    }
    if (n_valid == 0) {
      continue;
    }

    const auto [o, c] = session_bounds(td);
    SessionRec r;
    r.trade_date = td;
    r.open_utc = o;
    r.close_utc = c;
    r.dominant_id = dom;
    r.runner_up_id = use_outright ? outr.runner_up : all.runner_up;
    r.dominant_share = use_outright ? outr.share : all.share;
    r.dominant_all_id = all.has_winner ? all.winner : -1;
    r.dominant_all_share = all.share;
    r.dominant_outright_id = outr.has_winner ? outr.winner : -1;
    r.dominant_outright_share = outr.share;
    r.n_instruments = static_cast<std::int64_t>(cand.ids.size());
    r.n_valid_seconds = n_valid;
    r.first_two_sided_sec = first_ts;
    r.last_two_sided_sec = last_ts;
    r.H = hi;
    r.L = lo;
    r.Cl = last_mid;
    const auto sit = cand.symbols.find(dom);
    r.symbol = (sit == cand.symbols.end()) ? std::string() : sit->second;
    r.short_day = (last_ts - first_ts) < static_cast<std::int64_t>(kShortDayHours) * 3600;
    sess.push_back(std::move(r));
    if ((ci + 1) % 100 == 0) {
      std::fprintf(stderr, "[qr_futsess] %s pass1 %zu/%zu (%s)\n", spec.name, ci + 1,
                   calendar.size(), td.iso().c_str());
    }
  }

  // ------------------------------------------------------------ roll flags
  std::vector<std::size_t> changes;
  for (std::size_t i = 0; i < sess.size(); ++i) {
    sess[i].prev_session_dominant = (i != 0) ? sess[i - 1].dominant_id : -1;
    sess[i].instrument_change = (i != 0) && (sess[i].dominant_id != sess[i - 1].dominant_id);
    if (sess[i].instrument_change) {
      changes.push_back(i);
    }
  }
  for (std::size_t i = 0; i < sess.size(); ++i) {
    bool in_window = false;
    bool dying = false;
    for (const std::size_t ci : changes) {
      const auto d = static_cast<std::int64_t>(ci) - static_cast<std::int64_t>(i);
      if (std::llabs(d) <= kRollWindowSessions) {
        in_window = true;
      }
      if (d >= 0 && d <= kRollWindowSessions) {
        dying = true;
      }
    }
    sess[i].roll_window = in_window;
    sess[i].dying_book_week = (opt.asset == Asset::NKD) && dying;
    sess[i].whipsaw_flag = false;
  }
  for (const std::size_t ci : changes) {
    const std::int64_t a = (ci != 0) ? sess[ci - 1].dominant_id : -1;
    const std::int64_t b = sess[ci].dominant_id;
    for (const std::size_t cj : changes) {
      const auto gap = static_cast<std::int64_t>(cj) - static_cast<std::int64_t>(ci);
      if (gap > 0 && gap <= kWhipsawWindowSessions && sess[cj].dominant_id == a &&
          sess[cj - 1].dominant_id == b) {
        for (std::size_t k = ci; k <= cj; ++k) {
          sess[k].whipsaw_flag = true;
        }
      }
    }
  }

  // -------------------------------------------------------- bars and ATR14
  std::vector<std::size_t> bars;
  for (std::size_t i = 0; i < sess.size(); ++i) {
    if (sess[i].n_valid_seconds >= kMinBarSeconds) {
      bars.push_back(i);
    }
  }
  std::vector<double> trs(bars.size(), 0.0);
  for (std::size_t i = 0; i < bars.size(); ++i) {
    const SessionRec& r = sess[bars[i]];
    bool drop = true;
    if (i != 0) {
      const SessionRec& p = sess[bars[i - 1]];
      const bool same = (p.dominant_id == r.dominant_id);
      const auto ri = cal_index.find(r.trade_date.yyyymmdd());
      const auto pi = cal_index.find(p.trade_date.yyyymmdd());
      const int rv = (ri == cal_index.end()) ? -1 : ri->second;
      const int pv = (pi == cal_index.end()) ? -99 : pi->second;
      drop = !(same && (rv - pv == 1));
    }
    if (drop) {
      trs[i] = r.H - r.L;
    } else {
      const double cprev = sess[bars[i - 1]].Cl;
      trs[i] = std::max({r.H - r.L, std::abs(r.H - cprev), std::abs(r.L - cprev)});
    }
  }
  const std::vector<double> atr = wilder_atr(trs, kAtrPeriod);
  for (std::size_t i = 0; i < bars.size(); ++i) {
    SessionRec& r = sess[bars[i]];
    r.has_bar = true;
    r.tr_px = trs[i];
    r.atr_prev_px = (i != 0) ? atr[i - 1] : nan_value();
  }

  // ------------------------------------------------- pass 2: the receipts
  std::map<std::array<std::int64_t, 3>, std::vector<std::int8_t>> phase_luts;
  AssembleResult result;
  result.n_bars = static_cast<std::int64_t>(bars.size());

  for (std::size_t si = 0; si < sess.size(); ++si) {
    const SessionRec& r = sess[si];
    const auto yit = ptab.by_year.find(r.trade_date.year);
    if (yit == ptab.by_year.end()) {
      return refuse<AssembleResult>(Refusal(RefusalCode::CONTENT_MISMATCH,
                                            "qr_futsess::assemble_asset",
                                            "no frozen phase boundaries for this session's year",
                                            r.trade_date.year));
    }
    const std::array<std::int64_t, 3>& bounds = yit->second;

    std::vector<std::int64_t> keep{r.dominant_id};
    if (r.runner_up_id >= 0 && (opt.asset == Asset::HG || opt.asset == Asset::NKD) &&
        r.roll_window) {
      keep.push_back(r.runner_up_id);
    }

    BinWriter bw;
    std::vector<std::int64_t> slot_iids;
    for (std::size_t slot = 0; slot < keep.size(); ++slot) {
      const Grid g = stitch(cache, r.trade_date, keep[slot], true);
      const std::size_t n = g.state.size();
      std::vector<double> mid(n, nan_value());
      std::vector<double> spr(n, nan_value());
      for (std::size_t s = 0; s < n; ++s) {
        if (g.state[s] != kStTwoSided) {
          continue;
        }
        const double b = static_cast<double>(g.bid_px[s]);
        const double a = static_cast<double>(g.ask_px[s]);
        mid[s] = (b + a) / 2 * spec.px_scale;
        spr[s] = (a - b) * spec.px_scale * static_cast<double>(spec.mult);
      }
      const std::string pre = "g" + std::to_string(slot) + "_";
      bw.add(pre + "bid_px", "int64", g.bid_px);
      bw.add(pre + "ask_px", "int64", g.ask_px);
      bw.add(pre + "bid_sz", "int64", g.bid_sz);
      bw.add(pre + "ask_sz", "int64", g.ask_sz);
      bw.add(pre + "state", "int8", g.state);
      bw.add(pre + "upd_count", "int32", g.upd);
      bw.add(pre + "mid", "float64", mid);
      bw.add(pre + "spread_usd", "float64", spr);
      slot_iids.push_back(keep[slot]);
    }

    const Trades tr = session_trades(cache, r.trade_date, r.dominant_id);
    auto lit = phase_luts.find(bounds);
    if (lit == phase_luts.end()) {
      std::vector<std::int8_t> lut(static_cast<std::size_t>(kSecondsPerDay));
      for (std::int64_t s = 0; s < kSecondsPerDay; ++s) {
        lut[static_cast<std::size_t>(s)] = phase_of(s, bounds);
      }
      lit = phase_luts.emplace(bounds, std::move(lut)).first;
    }
    std::vector<std::int8_t> tag(static_cast<std::size_t>(kSessionSeconds));
    for (std::int64_t s = 0; s < kSessionSeconds; ++s) {
      tag[static_cast<std::size_t>(s)] =
          lit->second[static_cast<std::size_t>((r.open_utc + s) % 86400)];
    }
    bw.add("phase_tag", "int8", tag);
    bw.add("trades_sec", "int64", tr.sec);
    bw.add("trades_px", "int64", tr.px);
    bw.add("trades_size", "int64", tr.size);
    bw.add("trades_side", "uint8", tr.side);

    const std::string stem = opt.out_dir + "/" + r.trade_date.compact();
    auto wrote = write_file(stem + ".bin", bw.bytes().data(), bw.bytes().size());
    if (!wrote) {
      return refuse<AssembleResult>(wrote.error());
    }

    JsonWriter jw;
    jw.begin_object();
    jw.key("format");
    jw.value_string("QRSESS1");
    jw.key("bin");
    jw.value_string(r.trade_date.compact() + ".bin");
    jw.key("arrays");
    jw.begin_array();
    for (const ArrayDesc& d : bw.descs()) {
      jw.begin_object();
      jw.key("name");
      jw.value_string(d.name);
      jw.key("dtype");
      jw.value_string(d.dtype);
      jw.key("count");
      jw.value_int(static_cast<std::int64_t>(d.count));
      jw.key("offset");
      jw.value_int(static_cast<std::int64_t>(d.offset));
      jw.end_object();
    }
    jw.end_array();
    for (std::size_t slot = 0; slot < slot_iids.size(); ++slot) {
      jw.key("g" + std::to_string(slot) + "_iid");
      jw.value_int(slot_iids[slot]);
    }
    jw.key("meta");
    jw.begin_object();
    jw.key("ATR14_prev_px");
    if (r.has_bar) {
      jw.value_double(r.atr_prev_px);
    } else {
      jw.value_null();
    }
    jw.key("Cl");
    jw.value_double(r.Cl);
    jw.key("H");
    jw.value_double(r.H);
    jw.key("L");
    jw.value_double(r.L);
    jw.key("TR_px");
    if (r.has_bar) {
      jw.value_double(r.tr_px);
    } else {
      jw.value_null();
    }
    jw.key("asset");
    jw.value_string(spec.name);
    jw.key("close_utc");
    jw.value_int(r.close_utc);
    jw.key("dominant_all_id");
    if (r.dominant_all_id >= 0) {
      jw.value_int(r.dominant_all_id);
    } else {
      jw.value_null();
    }
    jw.key("dominant_all_share");
    jw.value_double(r.dominant_all_share);
    jw.key("dominant_id");
    jw.value_int(r.dominant_id);
    jw.key("dominant_outright_id");
    if (r.dominant_outright_id >= 0) {
      jw.value_int(r.dominant_outright_id);
    } else {
      jw.value_null();
    }
    jw.key("dominant_outright_share");
    jw.value_double(r.dominant_outright_share);
    jw.key("dominant_share");
    jw.value_double(r.dominant_share);
    jw.key("dying_book_week");
    jw.value_bool(r.dying_book_week);
    jw.key("first_two_sided_sec");
    jw.value_int(r.first_two_sided_sec);
    jw.key("grid_slots");
    jw.begin_array();
    for (const std::int64_t iid : slot_iids) {
      jw.value_int(iid);
    }
    jw.end_array();
    jw.key("instrument_change");
    jw.value_bool(r.instrument_change);
    jw.key("last_two_sided_sec");
    jw.value_int(r.last_two_sided_sec);
    jw.key("n_instruments");
    jw.value_int(r.n_instruments);
    jw.key("n_valid_seconds");
    jw.value_int(r.n_valid_seconds);
    jw.key("open_utc");
    jw.value_int(r.open_utc);
    jw.key("params_hash");
    jw.value_string(kS3ParamsHash);
    jw.key("phase_boundaries_utc_sec");
    jw.begin_array();
    for (const std::int64_t b : bounds) {
      jw.value_int(b);
    }
    jw.end_array();
    jw.key("phase_names");
    jw.begin_array();
    for (const char* n : kPhaseNames) {
      jw.value_string(n);
    }
    jw.end_array();
    jw.key("prev_session_dominant");
    if (r.prev_session_dominant >= 0) {
      jw.value_int(r.prev_session_dominant);
    } else {
      jw.value_null();
    }
    jw.key("roll_window");
    jw.value_bool(r.roll_window);
    jw.key("runner_up_id");
    if (r.runner_up_id >= 0) {
      jw.value_int(r.runner_up_id);
    } else {
      jw.value_null();
    }
    jw.key("short_day");
    jw.value_bool(r.short_day);
    jw.key("symbol");
    jw.value_string(r.symbol);
    jw.key("trade_date");
    jw.value_string(r.trade_date.iso());
    jw.key("whipsaw_flag");
    jw.value_bool(r.whipsaw_flag);
    jw.end_object();
    jw.end_object();
    const std::string text = jw.text() + "\n";
    auto wrote_json = write_file(stem + ".json", text.data(), text.size());
    if (!wrote_json) {
      return refuse<AssembleResult>(wrote_json.error());
    }
    ++result.n_sessions;
    if ((si + 1) % 100 == 0) {
      std::fprintf(stderr, "[qr_futsess] %s pass2 %zu/%zu (%s)\n", spec.name, si + 1, sess.size(),
                   r.trade_date.iso().c_str());
    }
  }
  return result;
}

}  // namespace qr::futsess
