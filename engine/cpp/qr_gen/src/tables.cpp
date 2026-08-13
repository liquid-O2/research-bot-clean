#include "qr_gen/tables.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <limits>

namespace qr::gen {
namespace {

constexpr double kNaN = std::numeric_limits<double>::quiet_NaN();

const char* const kSegNames[kSegmentCount] = {"SESSION", "OVERNIGHT", "TOKYO", "LONDON", "NY"};

bool segment_from_name(const std::string& s, Segment* out) {
  for (std::size_t i = 0; i < kSegmentCount; ++i) {
    if (s == kSegNames[i]) {
      *out = static_cast<Segment>(i);
      return true;
    }
  }
  return false;
}

/// b2_fvol._pos: finite AND strictly positive.
bool pos(double v) { return std::isfinite(v) && v > 0.0; }

}  // namespace

const char* segment_name(Segment s) { return kSegNames[static_cast<std::size_t>(s)]; }

// ------------------------------------------------------------------- Tsv ----
Expected<Tsv, Refusal> Tsv::load(const std::string& path) {
  std::FILE* fh = std::fopen(path.c_str(), "rb");
  if (fh == nullptr) {
    return refuse<Tsv>(Refusal(RefusalCode::IO, "qr_gen::Tsv::load", "cannot open input table"));
  }
  std::string all;
  char buf[1 << 16];
  for (;;) {
    const std::size_t got = std::fread(buf, 1, sizeof(buf), fh);
    if (got == 0) {
      break;
    }
    all.append(buf, got);
  }
  const bool bad = (std::ferror(fh) != 0);
  std::fclose(fh);
  if (bad) {
    return refuse<Tsv>(Refusal(RefusalCode::IO, "qr_gen::Tsv::load", "read error on input table"));
  }

  Tsv t;
  std::size_t p = 0;
  while (p <= all.size()) {
    const std::size_t nl = all.find('\n', p);
    const std::size_t end = (nl == std::string::npos) ? all.size() : nl;
    if (p >= all.size()) {
      break;
    }
    std::string line = all.substr(p, end - p);
    p = (nl == std::string::npos) ? all.size() + 1 : nl + 1;
    if (!line.empty() && line.back() == '\r') {
      line.pop_back();
    }
    if (line.empty() || line[0] == '#') {
      continue;
    }
    std::vector<std::string> fields;
    std::size_t q = 0;
    for (;;) {
      const std::size_t tab = line.find('\t', q);
      if (tab == std::string::npos) {
        fields.push_back(line.substr(q));
        break;
      }
      fields.push_back(line.substr(q, tab - q));
      q = tab + 1;
    }
    if (t.header_.empty()) {
      t.header_ = std::move(fields);
    } else {
      t.rows_.push_back(std::move(fields));
    }
  }
  if (t.header_.empty()) {
    return refuse<Tsv>(
        Refusal(RefusalCode::SCHEMA_MISMATCH, "qr_gen::Tsv::load", "table carries no header row"));
  }
  return t;
}

std::int64_t Tsv::column(const std::string& name) const {
  for (std::size_t i = 0; i < header_.size(); ++i) {
    if (header_[i] == name) {
      return static_cast<std::int64_t>(i);
    }
  }
  return -1;
}

const std::string& Tsv::cell(std::size_t row, std::int64_t col) const {
  if (col < 0 || row >= rows_.size() ||
      static_cast<std::size_t>(col) >= rows_[row].size()) {
    return empty_;
  }
  return rows_[row][static_cast<std::size_t>(col)];
}

double Tsv::number(std::size_t row, std::int64_t col) const {
  const std::string& c = cell(row, col);
  if (c.empty()) {
    return kNaN;
  }
  char* endp = nullptr;
  const double v = std::strtod(c.c_str(), &endp);
  if (endp == c.c_str()) {
    return kNaN;
  }
  return v;
}

std::int32_t date8_of_iso(const std::string& iso) {
  if (iso.size() != 10 || iso[4] != '-' || iso[7] != '-') {
    return 0;
  }
  const int y = std::atoi(iso.substr(0, 4).c_str());
  const int m = std::atoi(iso.substr(5, 2).c_str());
  const int d = std::atoi(iso.substr(8, 2).c_str());
  return y * 10000 + m * 100 + d;
}

// -------------------------------------------------------------- V1History ---
Expected<V1History, Refusal> V1History::load(const std::string& path, const std::string& asset) {
  auto tsv = Tsv::load(path);
  if (!tsv) {
    return refuse<V1History>(tsv.error());
  }
  const Tsv& t = tsv.value();
  const std::int64_t c_asset = t.column("asset");
  const std::int64_t c_date = t.column("trade_date");
  const std::int64_t c_seg = t.column("segment");
  const std::int64_t c_open = t.column("open_px");
  const std::int64_t c_high = t.column("high_px");
  const std::int64_t c_low = t.column("low_px");
  const std::int64_t c_close = t.column("close_px");
  const std::int64_t c_range = t.column("range_usd");
  if (c_asset < 0 || c_date < 0 || c_seg < 0 || c_open < 0 || c_high < 0 || c_low < 0 ||
      c_close < 0 || c_range < 0) {
    return refuse<V1History>(Refusal(RefusalCode::SCHEMA_MISMATCH, "qr_gen::V1History::load",
                                     "v1_realized.tsv is missing a required column"));
  }
  std::map<std::int32_t, DayBars> by_date;
  for (std::size_t r = 0; r < t.rows(); ++r) {
    if (t.cell(r, c_asset) != asset) {
      continue;
    }
    const std::int32_t d8 = date8_of_iso(t.cell(r, c_date));
    if (d8 == 0) {
      continue;
    }
    Segment seg{};
    if (!segment_from_name(t.cell(r, c_seg), &seg)) {
      continue;
    }
    SegmentBar& b = by_date[d8].seg[static_cast<std::size_t>(seg)];
    b.open_px = t.number(r, c_open);
    b.high_px = t.number(r, c_high);
    b.low_px = t.number(r, c_low);
    b.close_px = t.number(r, c_close);
    b.range_usd = t.number(r, c_range);
    b.present = true;
  }
  V1History h;
  for (const auto& kv : by_date) {
    // The stale-book drop: b3_levels.load_v1_history removes any date whose
    // SESSION range is not strictly positive (a missing SESSION row defaults to
    // 0.0 there, so it is dropped for the same reason).
    if (!pos(kv.second.seg[static_cast<std::size_t>(Segment::SESSION)].range_usd)) {
      continue;
    }
    h.dates_.push_back(kv.first);
    h.bars_.push_back(kv.second);
  }
  return h;
}

std::int64_t V1History::index_of(std::int32_t date8) const {
  const auto it = std::lower_bound(dates_.begin(), dates_.end(), date8);
  if (it == dates_.end() || *it != date8) {
    return -1;
  }
  return static_cast<std::int64_t>(it - dates_.begin());
}

// --------------------------------------------------------- FvolForecasts ----
Expected<FvolForecasts, Refusal> FvolForecasts::load(const std::string& path,
                                                     const std::string& asset) {
  auto tsv = Tsv::load(path);
  if (!tsv) {
    return refuse<FvolForecasts>(tsv.error());
  }
  const Tsv& t = tsv.value();
  const std::int64_t c_asset = t.column("asset");
  const std::int64_t c_date = t.column("trade_date");
  const std::int64_t c_seg = t.column("segment");
  const std::int64_t c_sig = t.column("sigma_hat_usd");
  std::int64_t c_q[kLadderQCount];
  for (std::size_t i = 0; i < kLadderQCount; ++i) {
    char nm[64];
    std::snprintf(nm, sizeof(nm), "move_q%02d_usd_per_sigma", kLadderQ[i]);
    c_q[i] = t.column(nm);
    if (c_q[i] < 0) {
      return refuse<FvolForecasts>(Refusal(RefusalCode::SCHEMA_MISMATCH,
                                           "qr_gen::FvolForecasts::load",
                                           "fvol_forecasts.tsv is missing a ladder column"));
    }
  }
  if (c_asset < 0 || c_date < 0 || c_seg < 0 || c_sig < 0) {
    return refuse<FvolForecasts>(Refusal(RefusalCode::SCHEMA_MISMATCH,
                                         "qr_gen::FvolForecasts::load",
                                         "fvol_forecasts.tsv is missing a required column"));
  }
  FvolForecasts f;
  for (std::size_t r = 0; r < t.rows(); ++r) {
    if (t.cell(r, c_asset) != asset) {
      continue;
    }
    const std::int32_t d8 = date8_of_iso(t.cell(r, c_date));
    if (d8 == 0) {
      continue;
    }
    Segment seg{};
    if (!segment_from_name(t.cell(r, c_seg), &seg)) {
      continue;
    }
    FvolRow row;
    row.present = true;
    row.sigma_hat_usd = t.number(r, c_sig);
    for (std::size_t i = 0; i < kLadderQCount; ++i) {
      row.move_q[i] = t.number(r, c_q[i]);
    }
    f.rows_[{d8, static_cast<std::uint8_t>(seg)}] = row;
  }
  return f;
}

const FvolRow* FvolForecasts::find(std::int32_t date8, Segment seg) const {
  const auto it = rows_.find({date8, static_cast<std::uint8_t>(seg)});
  return (it == rows_.end()) ? nullptr : &it->second;
}

// ------------------------------------------------------------ BarsTable -----
Expected<BarsTable, Refusal> BarsTable::load(const std::string& path) {
  auto tsv = Tsv::load(path);
  if (!tsv) {
    return refuse<BarsTable>(tsv.error());
  }
  const Tsv& t = tsv.value();
  const std::int64_t c_date = t.column("trade_date");
  const std::int64_t c_atr = t.column("ATR14_prev_usd");
  if (c_date < 0 || c_atr < 0) {
    return refuse<BarsTable>(Refusal(RefusalCode::SCHEMA_MISMATCH, "qr_gen::BarsTable::load",
                                     "bars table is missing trade_date/ATR14_prev_usd"));
  }
  BarsTable b;
  for (std::size_t r = 0; r < t.rows(); ++r) {
    const std::int32_t d8 = date8_of_iso(t.cell(r, c_date));
    if (d8 == 0) {
      continue;
    }
    b.atr_[d8] = t.number(r, c_atr);
  }
  return b;
}

double BarsTable::atr14_prev_usd(std::int32_t date8) const {
  const auto it = atr_.find(date8);
  return (it == atr_.end()) ? kNaN : it->second;
}

// --------------------------------------------------- PhaseMedianSpreads -----
Expected<PhaseMedianSpreads, Refusal> PhaseMedianSpreads::load(const std::string& path,
                                                               const std::string& asset) {
  auto tsv = Tsv::load(path);
  if (!tsv) {
    return refuse<PhaseMedianSpreads>(tsv.error());
  }
  const Tsv& t = tsv.value();
  const std::int64_t c_asset = t.column("asset");
  const std::int64_t c_phase = t.column("phase");
  const std::int64_t c_era = t.column("era");
  const std::int64_t c_split = t.column("split");
  const std::int64_t c_med = t.column("spread_med_usd_pooled");
  if (c_asset < 0 || c_phase < 0 || c_era < 0 || c_split < 0 || c_med < 0) {
    return refuse<PhaseMedianSpreads>(Refusal(RefusalCode::SCHEMA_MISMATCH,
                                              "qr_gen::PhaseMedianSpreads::load",
                                              "cost rollup is missing a required column"));
  }
  static const char* const kPhases[3] = {"TOKYO", "LONDON", "NY"};
  PhaseMedianSpreads m;
  for (std::size_t r = 0; r < t.rows(); ++r) {
    if (t.cell(r, c_asset) != asset || t.cell(r, c_split) != "all") {
      continue;
    }
    const std::string& era = t.cell(r, c_era);
    bool digits = !era.empty();
    for (char ch : era) {
      digits = digits && (ch >= '0' && ch <= '9');
    }
    if (!digits) {
      continue;
    }
    const std::string& ph = t.cell(r, c_phase);
    for (std::size_t p = 0; p < 3; ++p) {
      if (ph == kPhases[p]) {
        m.med_[{static_cast<std::int32_t>(std::atoi(era.c_str())), static_cast<std::uint8_t>(p)}] =
            t.number(r, c_med);
      }
    }
  }
  return m;
}

double PhaseMedianSpreads::median_usd(std::int32_t year, std::size_t phase) const {
  const auto it = med_.find({year, static_cast<std::uint8_t>(phase)});
  return (it == med_.end()) ? kNaN : it->second;
}

}  // namespace qr::gen
