#include "qr_gen/generate.hpp"

#include <dirent.h>
#include <openssl/sha.h>

#include <algorithm>
#include <charconv>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "qr_futsess/json.hpp"
#include "qr_gen/gensession.hpp"
#include "qr_skel/binpack.hpp"
#include "qr_skel/geom.hpp"

namespace qr::gen {
namespace {

using qr::skel::AssetGeom;
using qr::skel::BinPackWriter;

/// The frozen specs this engine implements. A pin nobody checks is decoration:
/// the test suite recomputes both from the files.
constexpr const char* kSpecM1bSha16 = "d31f48b59877e44d";
// CC-M1-6.4 (the twice-bitten lesson): a CC amendment to a spec MUST bump the
// code sha pins in the SAME commit. CC-M1-6..9 were appended to PORT_M1_SPEC.md
// without the bump, which left this pin stale and the pin test RED at HEAD;
// S2.2 bumps it here.
constexpr const char* kSpecM1Sha16 = "b84832556267e703";

std::string fmt_double(double v) {
  char buf[64];
  const auto res = std::to_chars(buf, buf + sizeof(buf), v);
  return std::string(buf, res.ptr);
}

std::string hex_sha256(const std::string& s) {
  unsigned char md[SHA256_DIGEST_LENGTH];
  SHA256(reinterpret_cast<const unsigned char*>(s.data()), s.size(), md);
  static const char* kHex = "0123456789abcdef";
  std::string out;
  out.reserve(SHA256_DIGEST_LENGTH * 2);
  for (unsigned char c : md) {
    out.push_back(kHex[c >> 4]);
    out.push_back(kHex[c & 0x0F]);
  }
  return out;
}

/// The roster's columns for one month shard.
struct RosterColumns {
  std::vector<std::int32_t> date8, conf_sec, dec_sec, mfe_argmax_sec, phase_close_sec,
      sess_close_sec, level_fam_mask, fam_mask;
  std::vector<std::int8_t> side, phase_conf, phase_dec;
  std::vector<std::uint8_t> rung_mask, flags;
  std::vector<double> entry_mid, spread_at_decision, atr14_usd, dom_share, mfe_unwalled,
      mae_before_argmax, f_h30, f_h60, f_h120, f_phase_close, f_sess_close;
  std::vector<std::int64_t> iid, f_off, f_len, a_off, a_len;
  qr::skel::RecordArrays recs;

  [[nodiscard]] std::size_t size() const { return date8.size(); }

  void clear() {
    *this = RosterColumns{};
  }

  void emit(BinPackWriter& w) const {
    w.add("date8", "int32", date8);
    w.add("side", "int8", side);
    w.add("rung_mask", "uint8", rung_mask);
    w.add("conf_sec", "int32", conf_sec);
    w.add("dec_sec", "int32", dec_sec);
    w.add("phase_conf", "int8", phase_conf);
    w.add("phase_dec", "int8", phase_dec);
    w.add("entry_mid", "float64", entry_mid);
    w.add("spread_at_decision", "float64", spread_at_decision);
    w.add("atr14_usd", "float64", atr14_usd);
    w.add("dom_share", "float64", dom_share);
    w.add("iid", "int64", iid);
    w.add("mfe_unwalled", "float64", mfe_unwalled);
    w.add("mfe_argmax_sec", "int32", mfe_argmax_sec);
    w.add("mae_before_argmax", "float64", mae_before_argmax);
    w.add("f_h30", "float64", f_h30);
    w.add("f_h60", "float64", f_h60);
    w.add("f_h120", "float64", f_h120);
    w.add("f_phase_close", "float64", f_phase_close);
    w.add("f_sess_close", "float64", f_sess_close);
    w.add("phase_close_sec", "int32", phase_close_sec);
    w.add("sess_close_sec", "int32", sess_close_sec);
    w.add("f_off", "int64", f_off);
    w.add("f_len", "int64", f_len);
    w.add("a_off", "int64", a_off);
    w.add("a_len", "int64", a_len);
    w.add("skel_f_t", "int32", recs.f_t);
    w.add("skel_f_v", "float32", recs.f_v);
    w.add("skel_a_t", "int32", recs.a_t);
    w.add("skel_a_v", "float32", recs.a_v);
    // The roster's two uint16 masks; the receipt format carries no uint16, so
    // they travel as int32 and the comparator casts. Nine candidate families,
    // seven kept level families.
    w.add("fam_mask", "int32", fam_mask);
    w.add("level_fam_mask", "int32", level_fam_mask);
    w.add("flags", "uint8", flags);
  }
};

/// The level ledger of one month shard (the D-050 provenance record).
struct LedgerColumns {
  std::vector<std::int32_t> lv_date8, lv_created_d8, lv_touch_count, lv_last_test_sec,
      lv_first_near_sec;
  std::vector<std::int8_t> lv_family, lv_dynamic, lv_virgin, lv_last_test_outcome;
  std::vector<double> lv_price;
  std::vector<std::int32_t> tc_date8, tc_level_row, tc_touch_sec, tc_outcome_sec, tc_reject_sec,
      tc_break_sec, tc_reclaim_sec, tc_touch_index;
  std::vector<std::int8_t> tc_family, tc_approach_side, tc_outcome, tc_virgin;
  std::vector<double> tc_level_price, tc_mid;

  void clear() { *this = LedgerColumns{}; }

  void append(std::int32_t date8, const SessionLedger& led) {
    for (const LedgerRow& r : led.rows) {
      lv_date8.push_back(date8);
      lv_family.push_back(static_cast<std::int8_t>(r.family));
      lv_price.push_back(r.price);
      lv_created_d8.push_back(r.created_d8);
      lv_dynamic.push_back(r.dynamic);
      lv_virgin.push_back(r.virgin);
      lv_touch_count.push_back(r.touch_count);
      lv_last_test_sec.push_back(r.last_test_sec);
      lv_last_test_outcome.push_back(r.last_test_outcome);
      lv_first_near_sec.push_back(r.first_near_sec);
    }
    for (const Touch& t : led.touches) {
      tc_date8.push_back(date8);
      tc_level_row.push_back(t.level_row);
      tc_family.push_back(static_cast<std::int8_t>(t.family));
      tc_touch_sec.push_back(t.touch_sec);
      tc_level_price.push_back(t.level_price);
      tc_mid.push_back(t.mid);
      tc_approach_side.push_back(t.approach_side);
      tc_outcome.push_back(static_cast<std::int8_t>(t.outcome));
      tc_outcome_sec.push_back(t.outcome_sec);
      tc_reject_sec.push_back(t.reject_sec);
      tc_break_sec.push_back(t.break_sec);
      tc_reclaim_sec.push_back(t.reclaim_sec);
      tc_virgin.push_back(t.virgin_at_touch);
      tc_touch_index.push_back(t.touch_index);
    }
  }

  void emit(BinPackWriter& w) const {
    w.add("lv_date8", "int32", lv_date8);
    w.add("lv_family", "int8", lv_family);
    w.add("lv_price", "float64", lv_price);
    w.add("lv_created_d8", "int32", lv_created_d8);
    w.add("lv_dynamic", "int8", lv_dynamic);
    w.add("lv_virgin", "int8", lv_virgin);
    w.add("lv_touch_count", "int32", lv_touch_count);
    w.add("lv_last_test_sec", "int32", lv_last_test_sec);
    w.add("lv_last_test_outcome", "int8", lv_last_test_outcome);
    w.add("lv_first_near_sec", "int32", lv_first_near_sec);
    w.add("tc_date8", "int32", tc_date8);
    w.add("tc_level_row", "int32", tc_level_row);
    w.add("tc_family", "int8", tc_family);
    w.add("tc_touch_sec", "int32", tc_touch_sec);
    w.add("tc_level_price", "float64", tc_level_price);
    w.add("tc_mid", "float64", tc_mid);
    w.add("tc_approach_side", "int8", tc_approach_side);
    w.add("tc_outcome", "int8", tc_outcome);
    w.add("tc_outcome_sec", "int32", tc_outcome_sec);
    w.add("tc_reject_sec", "int32", tc_reject_sec);
    w.add("tc_break_sec", "int32", tc_break_sec);
    w.add("tc_reclaim_sec", "int32", tc_reclaim_sec);
    w.add("tc_virgin", "int8", tc_virgin);
    w.add("tc_touch_index", "int32", tc_touch_index);
  }
};

}  // namespace

// ================================================================ pieces =====
double rung_threshold_px(const AssetGeom& geom, double rung, double atr_usd,
                         double phase_median_spread_usd) {
  const double floor_spread =
      std::isfinite(phase_median_spread_usd) ? kRungFloorSpreadMult * phase_median_spread_usd : 0.0;
  const double usd = std::max({rung * atr_usd, kRungFloorTicks * geom.tick_usd, floor_spread});
  return qr::skel::round_half_up(usd / static_cast<double>(geom.mult), geom.tick_px);
}

std::vector<Pivot> zigzag_scan(const std::vector<std::int32_t>& secs,
                               const std::vector<double>& mids, const std::vector<double>& thr) {
  std::vector<Pivot> out;
  const std::size_t n = secs.size();
  if (n < 2) {
    return out;
  }
  double hi = mids[0];
  double lo = mids[0];
  std::int32_t hi_s = secs[0];
  std::int32_t lo_s = secs[0];
  int d = 0;
  for (std::size_t i = 1; i < n; ++i) {
    const double m = mids[i];
    const std::int32_t s = secs[i];
    const double t = thr[i];
    if (d == 1) {
      if (m > hi) {
        hi = m;
        hi_s = s;
      } else if ((hi - m) >= t) {
        out.push_back(Pivot{hi, hi_s, s, -1});
        d = -1;
        lo = m;
        lo_s = s;
      }
    } else if (d == -1) {
      if (m < lo) {
        lo = m;
        lo_s = s;
      } else if ((m - lo) >= t) {
        out.push_back(Pivot{lo, lo_s, s, 1});
        d = 1;
        hi = m;
        hi_s = s;
      }
    } else {
      if (m > hi) {
        hi = m;
        hi_s = s;
      }
      if (m < lo) {
        lo = m;
        lo_s = s;
      }
      bool dn = (hi - m) >= t;
      bool up = (m - lo) >= t;
      if (dn && up) {
        // Unreachable under a constant threshold; deterministic anyway: the
        // extreme that formed EARLIER is confirmed first, HIGH on a tie.
        if (hi_s <= lo_s) {
          up = false;
        } else {
          dn = false;
        }
      }
      if (dn) {
        out.push_back(Pivot{hi, hi_s, s, -1});
        d = -1;
        lo = m;
        lo_s = s;
      } else if (up) {
        out.push_back(Pivot{lo, lo_s, s, 1});
        d = 1;
        hi = m;
        hi_s = s;
      }
    }
  }
  return out;
}

std::vector<std::int32_t> phase_open_secs(const std::vector<std::int8_t>& phase_tag) {
  std::vector<std::int32_t> out;
  out.push_back(0);
  for (std::size_t t = 1; t < phase_tag.size(); ++t) {
    if (phase_tag[t] != phase_tag[t - 1]) {
      out.push_back(static_cast<std::int32_t>(t));
    }
  }
  return out;
}

bool in_fast_open(std::int32_t conf_sec, const std::vector<std::int32_t>& opens) {
  const auto it = std::upper_bound(opens.begin(), opens.end(), conf_sec);
  if (it == opens.begin()) {
    return false;
  }
  return (conf_sec - *(it - 1)) < kFastOpenWindow;
}

bool reclaim_within_bound(std::int32_t break_sec, std::int32_t reclaim_sec) {
  if (reclaim_sec < 0 || break_sec < 0) {
    return false;
  }
  return (reclaim_sec - break_sec) <= kReclaimBoundSec;
}

std::vector<Emission> g1_emissions(const std::vector<Confirmation>& confs,
                                   const std::vector<std::int32_t>& opens) {
  std::vector<Emission> out;
  for (const Confirmation& c : confs) {
    std::uint8_t fam = 0;
    if ((c.rung_mask & kCoarseMask) != 0) {
      fam = static_cast<std::uint8_t>(fam | kFamG1);
    }
    if ((c.rung_mask & kFineBit) != 0) {
      fam = static_cast<std::uint8_t>(fam | kFamG1Fine);
    }
    if (fam != 0) {
      out.push_back(Emission{c.conf_sec + kTauStar, c.side, fam, 0, c.rung_mask, c.conf_sec});
    }
    if (in_fast_open(c.conf_sec, opens)) {
      out.push_back(Emission{c.conf_sec + kFastOpenDelay, c.side, kFamG1FastOpen, 0, c.rung_mask,
                             c.conf_sec});
    }
  }
  return out;
}

std::vector<G2Conf> g2_confirmations(const std::vector<Touch>& touches,
                                     std::int64_t* n_dropped_reclaim_bound) {
  std::vector<G2Conf> out;
  for (const Touch& t : touches) {
    if (t.reject_sec >= 0) {
      out.push_back(G2Conf{t.reject_sec, t.approach_side, kFamG2Reject, t.family});
    }
    if (t.reclaim_sec >= 0) {
      if (reclaim_within_bound(t.break_sec, t.reclaim_sec)) {
        out.push_back(G2Conf{t.reclaim_sec, t.approach_side, kFamG2Reclaim, t.family});
      } else if (n_dropped_reclaim_bound != nullptr) {
        ++*n_dropped_reclaim_bound;
      }
    }
  }
  return out;
}

std::vector<Emission> g2_emissions_of(const std::vector<G2Conf>& g2) {
  std::vector<Emission> out;
  out.reserve(g2.size());
  for (const G2Conf& c : g2) {
    const std::uint16_t lvl = static_cast<std::uint16_t>(1u << static_cast<unsigned>(c.family));
    // CC-M1-5 D14: G2 keeps tau* everywhere; only G1 has a FAST-OPEN delay.
    out.push_back(Emission{c.conf_sec + kTauStar, c.side, c.fam_bit, lvl, 0, c.conf_sec, 0});
  }
  return out;
}

std::vector<Emission> g2_emissions(const std::vector<Touch>& touches,
                                   std::int64_t* n_dropped_reclaim_bound) {
  return g2_emissions_of(g2_confirmations(touches, n_dropped_reclaim_bound));
}

std::vector<FirstTest> first_test_confirmations(const std::vector<G2Conf>& g2) {
  // One entry per KEPT LEVEL FAMILY, keyed by the family so the result is
  // ordered by the family's own bit order (the oracle iterates its dict sorted
  // by family name; the merge that consumes this is order-independent).
  std::map<std::uint8_t, FirstTest> first;
  for (const G2Conf& c : g2) {
    const std::uint8_t k = static_cast<std::uint8_t>(c.family);
    const auto it = first.find(k);
    // STRICTLY less: a later equal second never displaces the earlier arrival.
    if (it == first.end() || c.conf_sec < it->second.conf_sec) {
      first[k] = FirstTest{c.family, c.conf_sec, c.side};
    }
  }
  std::vector<FirstTest> out;
  out.reserve(first.size());
  for (const auto& kv : first) {
    out.push_back(kv.second);
  }
  return out;
}

std::vector<std::int32_t> virgin_confirmation_secs(const std::vector<Touch>& touches) {
  std::vector<std::int32_t> out;
  for (const Touch& t : touches) {
    if (t.virgin_at_touch != 1 || t.family == LevelFamily::OR_EXT) {
      continue;
    }
    if (t.reject_sec >= 0) {
      out.push_back(t.reject_sec);
    }
    if (t.reclaim_sec >= 0 && reclaim_within_bound(t.break_sec, t.reclaim_sec)) {
      out.push_back(t.reclaim_sec);
    }
  }
  std::sort(out.begin(), out.end());
  out.erase(std::unique(out.begin(), out.end()), out.end());
  return out;
}

std::vector<Emission> dedup(const std::vector<Emission>& in) {
  std::map<std::pair<std::int32_t, std::int8_t>, Emission> merged;
  for (const Emission& e : in) {
    const auto key = std::make_pair(e.dec_sec, e.side);
    const auto it = merged.find(key);
    if (it == merged.end()) {
      merged.emplace(key, e);
      continue;
    }
    Emission& cur = it->second;
    cur.fam_bits = static_cast<std::uint16_t>(cur.fam_bits | e.fam_bits);
    cur.level_bits = static_cast<std::uint16_t>(cur.level_bits | e.level_bits);
    cur.rung_mask = static_cast<std::uint8_t>(cur.rung_mask | e.rung_mask);
    cur.flags = static_cast<std::uint8_t>(cur.flags | e.flags);
    cur.conf_sec = std::min(cur.conf_sec, e.conf_sec);
  }
  std::vector<Emission> out;
  out.reserve(merged.size());
  for (const auto& kv : merged) {
    out.push_back(kv.second);
  }
  return out;
}

const char* family_name(std::size_t bit_index) {
  static const char* const kNames[kFamilyCount] = {
      "G1",        "G1_FINE",   "G1_FAST_OPEN", "G2_REJECT",  "G2_RECLAIM",
      "NEWS_WINDOW", "MICRO_OPEN", "POST_SHOCK", "FIRST_TEST"};
  return (bit_index < kFamilyCount) ? kNames[bit_index] : "?";
}

bool first_test_is_a_family(Asset asset) { return asset == Asset::NKD; }

std::vector<std::int32_t> news_release_offsets(std::int64_t open_utc, std::int32_t n,
                                               const std::vector<std::int32_t>& fomc_dates) {
  std::vector<std::int32_t> rel;
  for (std::size_t i = 0; i < kNewsSlotCount; ++i) {
    const std::vector<std::int32_t> o =
        local_epoch_offsets(open_utc, n, kNewsSlots[i].tz, kNewsSlots[i].hh, kNewsSlots[i].mm);
    rel.insert(rel.end(), o.begin(), o.end());
  }
  for (std::int32_t off : local_epoch_offsets(open_utc, n, kTzNewYork, kFomcHour, kFomcMin)) {
    // V3-3: the join is on the ET calendar day the RELEASE SECOND falls on,
    // never on the session's own trade_date.
    const std::int32_t d8 = local_date8(open_utc + off, kTzNewYork);
    if (std::binary_search(fomc_dates.begin(), fomc_dates.end(), d8)) {
      rel.push_back(off);
    }
  }
  std::sort(rel.begin(), rel.end());
  rel.erase(std::unique(rel.begin(), rel.end()), rel.end());
  return rel;
}

std::vector<std::int32_t> micro_open_offsets(std::int64_t open_utc, std::int32_t n) {
  std::vector<std::int32_t> out;
  for (std::size_t i = 0; i < kMicroOpenCount; ++i) {
    const std::vector<std::int32_t> o =
        local_epoch_offsets(open_utc, n, kMicroOpens[i].tz, kMicroOpens[i].hh, kMicroOpens[i].mm);
    out.insert(out.end(), o.begin(), o.end());
  }
  std::sort(out.begin(), out.end());
  out.erase(std::unique(out.begin(), out.end()), out.end());
  return out;
}

// ================================================================ driver =====
Expected<std::vector<std::int32_t>, Refusal> session_dates(const std::string& dir) {
  DIR* d = ::opendir(dir.c_str());
  if (d == nullptr) {
    return refuse<std::vector<std::int32_t>>(
        Refusal(RefusalCode::IO, "qr_gen::session_dates", "cannot open session directory"));
  }
  std::vector<std::int32_t> out;
  for (;;) {
    const struct dirent* e = ::readdir(d);
    if (e == nullptr) {
      break;
    }
    const std::string name = e->d_name;
    if (name.size() != 13 || name.compare(8, 5, ".json") != 0) {
      continue;
    }
    bool digits = true;
    for (std::size_t i = 0; i < 8; ++i) {
      digits = digits && (name[i] >= '0' && name[i] <= '9');
    }
    if (!digits) {
      continue;
    }
    out.push_back(static_cast<std::int32_t>(std::atoi(name.substr(0, 8).c_str())));
  }
  ::closedir(d);
  std::sort(out.begin(), out.end());
  return out;
}

std::string params_canonical_json(Asset asset) {
  std::string s = "{";
  s += "\"arm_seconds\":" + std::to_string(kArmSeconds);
  s += ",\"asset\":\"" + std::string(qr::futsess::asset_spec(asset).name) + "\"";
  s += ",\"break_hold_sec\":" + std::to_string(kBreakHold);
  s += ",\"dedup\":\"(session,decision_sec,side); family/rung/level/flag tags"
       " unioned; confirmation_sec = the earliest confirmation mapping to it\"";
  s += ",\"families\":[";
  for (std::size_t i = 0; i < kFamilyCount; ++i) {
    s += std::string(i ? "," : "") + "\"" + family_name(i) + "\"";
  }
  s += "]";
  s += ",\"fast_close\":\"RETIRED (CC-M1-7.2), never generated\"";
  s += ",\"fast_open_delay_sec\":" + std::to_string(kFastOpenDelay);
  s += ",\"fast_open_family\":\"ADDITIVE, G1 rungs only (CC-M1-5 D13/D14)\"";
  s += ",\"fast_open_window_sec\":" + std::to_string(kFastOpenWindow);
  s += ",\"first_test\":\"";
  s += first_test_is_a_family(asset)
           ? "earliest confirming touch per (session, kept level family), delay tau*;"
             " VIRGIN carried as a flag"
           : "FEATURE, not a family, on this asset (CC-M1-7.1)";
  s += "\"";
  s += ",\"flags\":\"bit0 = entry mid beyond a live same-segment ADOPTED OR_EXT"
       " k>=1.5 level, bit1 = the same over ALL cells, bit2 = FIRST_TEST on the"
       " level's first-ever touch (CC-M1-7.2: flags, never families)\"";
  s += ",\"fvol_k\":[";
  for (std::size_t i = 0; i < kFvolKCount; ++i) {
    s += (i ? "," : "") + fmt_double(kFvolK[i]);
  }
  s += "]";
  s += ",\"kept_level_families\":[";
  for (std::size_t i = 0; i < kLevelFamilyCount; ++i) {
    s += std::string(i ? "," : "") + "\"" +
         level_family_name(static_cast<LevelFamily>(i)) + "\"";
  }
  s += "]";
  s += ",\"ladder_q\":[";
  for (std::size_t i = 0; i < kLadderQCount; ++i) {
    s += (i ? "," : "") + std::to_string(kLadderQ[i]);
  }
  s += "]";
  s += ",\"micro_open\":\"first " + std::to_string(kMicroWindow) +
       "s after the Tokyo lunch reopen (12:30 Asia/Tokyo) and the US cash open"
       " (09:30 America/New_York, DST-correct); " +
       std::to_string(kMicroDelay) + "s delay; G1 confirmations only\"";
  s += ",\"mid_sanity\":\"D-054 SANE seconds only (b7_sane thresholds)\"";
  s += ",\"nday_lookbacks\":[";
  for (std::size_t i = 0; i < kNdayCount; ++i) {
    s += (i ? "," : "") + std::to_string(kNdayLookbacks[i]);
  }
  s += "]";
  s += ",\"news_window\":\"first " + std::to_string(kNewsWindow) +
       "s after FOMC 14:00 ET (meeting last day, joined on the ET calendar day"
       " of the release second) and the fixed 08:30/10:00 ET slots; SINGLE " +
       std::to_string(kNewsDelay) +
       "s delay; G1 confirmations only (CC-M1-5 D14 precedent); BOJ deferred\"";
  s += ",\"or_ext\":[";
  {
    const std::vector<std::pair<int, int>> cells = orext_adopted_cells(asset);
    static const char* const kSeg[3] = {"TOKYO", "LONDON", "NY"};
    for (std::size_t i = 0; i < cells.size(); ++i) {
      s += std::string(i ? "," : "") + "\"" + kSeg[cells[i].first] + "|OR" +
           std::to_string(cells[i].second) + "\"";
    }
  }
  s += "]";
  s += ",\"phase_lookbacks\":[";
  for (std::size_t i = 0; i < kPhaseLbCount; ++i) {
    s += (i ? "," : "") + std::to_string(kPhaseLookbacks[i]);
  }
  s += "]";
  s += ",\"post_shock\":\"first confirmation (G1 or G2) strictly after a causal"
       " shock episode ends: trailing-" + std::to_string(kShockSpan) +
       "s SANE mid range >= $1000, or a run of >= " + std::to_string(kInsaneMinSec) +
       "s wide-but-two-sided (D-054 insane) seconds; delay tau*\"";
  s += ",\"reclaim_bound_sec\":" + std::to_string(kReclaimBoundSec);
  s += ",\"reclaim_hold_sec\":" + std::to_string(kReclaimHold);
  s += ",\"reject_window_sec\":" + std::to_string(kRejectWindow);
  s += ",\"rung_floor\":\"max(4 x tick_$, 2 x phase-median spread_$)\"";
  s += ",\"rungs\":[";
  for (std::size_t i = 0; i < kRungCount4; ++i) {
    s += (i ? "," : "") + fmt_double(kRungs[i]);
  }
  s += "]";
  s += ",\"spec_m1_sha16\":\"" + std::string(kSpecM1Sha16) + "\"";
  s += ",\"spec_m1b_sha16\":\"" + std::string(kSpecM1bSha16) + "\"";
  s += ",\"tau_star_sec\":" + std::to_string(kTauStar);
  s += ",\"tolerance\":\"max(2 x tick_$, 0.05 x ATR14_$) / mult\"";
  s += ",\"vwap_bands\":[";
  for (std::size_t i = 0; i < kVwapBandCount; ++i) {
    s += (i ? "," : "") + fmt_double(kVwapBands[i]);
  }
  s += "]";
  s += "}";
  return s;
}

std::string params_hash(Asset asset) { return hex_sha256(params_canonical_json(asset)); }

const char* spec_sha16_pin() noexcept { return kSpecM1bSha16; }

namespace {

std::string month_of(std::int32_t date8) {
  char buf[16];
  std::snprintf(buf, sizeof(buf), "%06d", date8 / 100);
  return buf;
}

Expected<std::monostate, Refusal> flush_shard(const GenConfig& cfg, const std::string& month,
                                              const RosterColumns& cols, const LedgerColumns& led,
                                              GenStats* st) {
  const std::string name = std::string(qr::futsess::asset_spec(cfg.asset).name) + "_" + month;
  BinPackWriter w;
  cols.emit(w);
  const std::string phash = params_hash(cfg.asset);
  const std::string pjson = params_canonical_json(cfg.asset);
  auto wrote = w.write(cfg.out_dir + "/" + name, "QRGEN1",
                       [&](qr::futsess::JsonWriter& jw) {
                         jw.key("asset");
                         jw.value_string(qr::futsess::asset_spec(cfg.asset).name);
                         jw.key("month");
                         jw.value_string(month);
                         jw.key("spec_m1b_sha16");
                         jw.value_string(kSpecM1bSha16);
                         jw.key("spec_m1_sha16");
                         jw.value_string(kSpecM1Sha16);
                         jw.key("params_json");
                         jw.value_string(pjson);
                         jw.key("params_hash");
                         jw.value_string(phash);
                         jw.key("n_candidates");
                         jw.value_int(static_cast<std::int64_t>(cols.size()));
                         jw.key("n_records_f");
                         jw.value_int(static_cast<std::int64_t>(cols.recs.f_t.size()));
                         jw.key("n_records_a");
                         jw.value_int(static_cast<std::int64_t>(cols.recs.a_t.size()));
                         jw.key("mid_sanity_enabled");
                         jw.value_bool(!cfg.sanity_stem.empty());
                       });
  if (!wrote) {
    return refuse<std::monostate>(wrote.error());
  }
  BinPackWriter lw;
  led.emit(lw);
  auto wrote2 = lw.write(cfg.out_dir + "/" + name + "_ledger", "QRGENL1",
                         [&](qr::futsess::JsonWriter& jw) {
                           jw.key("asset");
                           jw.value_string(qr::futsess::asset_spec(cfg.asset).name);
                           jw.key("month");
                           jw.value_string(month);
                           jw.key("kept_level_families");
                           jw.begin_array();
                           for (std::size_t i = 0; i < kLevelFamilyCount; ++i) {
                             jw.value_string(level_family_name(static_cast<LevelFamily>(i)));
                           }
                           jw.end_array();
                           jw.key("n_levels");
                           jw.value_int(static_cast<std::int64_t>(led.lv_date8.size()));
                           jw.key("n_touches");
                           jw.value_int(static_cast<std::int64_t>(led.tc_date8.size()));
                         });
  if (!wrote2) {
    return refuse<std::monostate>(wrote2.error());
  }
  st->stored_bytes += static_cast<std::int64_t>(w.byte_size() + lw.byte_size());
  st->n_records_f += static_cast<std::int64_t>(cols.recs.f_t.size());
  st->n_records_a += static_cast<std::int64_t>(cols.recs.a_t.size());
  ++st->n_shards;
  return std::monostate{};
}

}  // namespace

Expected<GenStats, Refusal> generate_asset(const GenConfig& cfg) {
  const std::string asset_name = qr::futsess::asset_spec(cfg.asset).name;
  const AssetGeom& geom = qr::skel::asset_geom(cfg.asset);
  const double px_scale = qr::futsess::asset_spec(cfg.asset).px_scale;

  auto bars = BarsTable::load(cfg.bars_path);
  if (!bars) {
    return refuse<GenStats>(bars.error());
  }
  auto medians = PhaseMedianSpreads::load(cfg.cost_rollup_path, asset_name);
  if (!medians) {
    return refuse<GenStats>(medians.error());
  }
  auto hist = V1History::load(cfg.v1_path, asset_name);
  if (!hist) {
    return refuse<GenStats>(hist.error());
  }
  auto fvol = FvolForecasts::load(cfg.fvol_path, asset_name);
  if (!fvol) {
    return refuse<GenStats>(fvol.error());
  }
  qr::skel::SanityTable sanity;
  if (!cfg.sanity_stem.empty()) {
    auto t = qr::skel::SanityTable::load(cfg.sanity_stem);
    if (!t) {
      return refuse<GenStats>(t.error());
    }
    sanity = std::move(t).value();
  }
  std::vector<std::int32_t> dates = cfg.dates;
  if (dates.empty()) {
    auto d = session_dates(cfg.session_dir);
    if (!d) {
      return refuse<GenStats>(d.error());
    }
    dates = std::move(d).value();
  }
  // The NEWS-WINDOW calendar is read ONCE for the whole asset: it is a frozen
  // reference file, not a per-session input. A missing one is a refusal — the
  // NEWS family would silently degrade to the fixed slots alone.
  auto fomc = fomc_release_dates(cfg.fomc_csv_path);
  if (!fomc) {
    return refuse<GenStats>(fomc.error());
  }
  const std::vector<std::int32_t> fomc_dates = std::move(fomc).value();

  GenStats st;
  LevelRegistry registry;
  RosterColumns cols;
  LedgerColumns led;
  qr::skel::ChunkScratch scratch;
  double ladder[qr::skel::kRungCount];
  std::string cur_month;

  for (std::int32_t date8 : dates) {
    const std::string month = month_of(date8);
    if (!cur_month.empty() && month != cur_month) {
      auto f = flush_shard(cfg, cur_month, cols, led, &st);
      if (!f) {
        return refuse<GenStats>(f.error());
      }
      cols.clear();
      led.clear();
    }
    cur_month = month;

    qr::skel::SanityPolicy policy;
    if (!sanity.empty()) {
      auto p = sanity.policy_for(date8);
      if (!p) {
        return refuse<GenStats>(p.error());
      }
      policy = p.value();
    }
    auto sess = GenSession::load(cfg.session_dir, date8, policy);
    if (!sess) {
      return refuse<GenStats>(sess.error());
    }
    const GenSession& s = sess.value();
    ++st.n_sessions;
    st.n_seconds_insane += s.view().n_insane();
    st.n_seconds_two_sided += s.view().n_two_sided();

    const double atr = bars.value().atr14_prev_usd(date8);
    const std::int64_t hi = hist.value().index_of(date8);
    const bool usable = (s.vt().size() >= 2) && std::isfinite(atr);

    // ---- the level ledger (only for sessions the V1 history calls sessions) --
    std::vector<Touch> touches;
    if (hi >= 0 && usable) {
      const std::vector<LevelDef> levels =
          build_levels(cfg.asset, geom, px_scale, s, date8, hist.value(), hi, fvol.value());
      SessionLedger ledger = run_ledger(geom, s, date8, atr, levels, &registry);
      st.n_levels += static_cast<std::int64_t>(ledger.rows.size());
      st.n_touches += static_cast<std::int64_t>(ledger.touches.size());
      for (const LedgerRow& r : ledger.rows) {
        st.n_orext_levels += (r.family == LevelFamily::OR_EXT) ? 1 : 0;
      }
      for (const Touch& t : ledger.touches) {
        st.n_orext_touches += (t.family == LevelFamily::OR_EXT) ? 1 : 0;
      }
      ++st.n_sessions_with_ledger;
      led.append(date8, ledger);
      touches = std::move(ledger.touches);
    }
    if (!usable) {
      continue;
    }

    // ---- G1 confirmations over the four-rung ladder -------------------------
    const std::vector<std::int32_t>& vt = s.vt();
    const std::vector<double>& vm = s.vm();
    const std::int32_t year = date8 / 10000;
    std::vector<double> thr(vt.size());
    std::map<std::pair<std::int32_t, std::int8_t>, std::uint8_t> conf_map;
    for (std::size_t r = 0; r < kRungCount4; ++r) {
      double per_phase[qr::skel::kPhaseCount];
      for (std::size_t p = 0; p < qr::skel::kPhaseCount; ++p) {
        per_phase[p] = rung_threshold_px(geom, kRungs[r], atr, medians.value().median_usd(year, p));
      }
      for (std::size_t k = 0; k < vt.size(); ++k) {
        const std::int8_t ph = s.phase_tag()[static_cast<std::size_t>(vt[k])];
        if (ph < 0 || static_cast<std::size_t>(ph) >= qr::skel::kPhaseCount) {
          return refuse<GenStats>(Refusal(RefusalCode::CONTENT_MISMATCH, "qr_gen::generate_asset",
                                          "session second carries an unknown phase tag", date8));
        }
        thr[k] = per_phase[static_cast<std::size_t>(ph)];
      }
      for (const Pivot& p : zigzag_scan(vt, vm, thr)) {
        const auto key = std::make_pair(p.conf_sec, p.side);
        conf_map[key] = static_cast<std::uint8_t>(conf_map[key] | (1u << r));
      }
    }
    std::vector<Confirmation> confs;
    confs.reserve(conf_map.size());
    for (const auto& kv : conf_map) {
      confs.push_back(Confirmation{kv.first.first, kv.first.second, kv.second});
    }
    st.n_g1_confirmations += static_cast<std::int64_t>(confs.size());

    // ---- emissions, dedup, roster rows -------------------------------------
    const std::vector<std::int32_t> opens = phase_open_secs(s.phase_tag());
    std::vector<Emission> emissions = g1_emissions(confs, opens);
    const std::vector<G2Conf> g2 = g2_confirmations(touches, &st.n_g2_dropped_reclaim_bound);
    const std::vector<Emission> g2em = g2_emissions_of(g2);
    st.n_g2_events += static_cast<std::int64_t>(g2em.size());
    emissions.insert(emissions.end(), g2em.begin(), g2em.end());

    // ---- NEWS_WINDOW / MICRO_OPEN: the G1 confirmation universe (D14) ------
    const std::int64_t open_utc = s.open_utc();
    const std::vector<Interval> news_iv =
        open_windows(news_release_offsets(open_utc, s.n(), fomc_dates), kNewsWindow);
    const std::vector<Interval> micro_iv =
        open_windows(micro_open_offsets(open_utc, s.n()), kMicroWindow);
    for (const Confirmation& c : confs) {
      if (in_intervals(c.conf_sec, news_iv)) {
        ++st.n_news_conf;
        emissions.push_back(Emission{c.conf_sec + kNewsDelay, c.side, kFamNewsWindow, 0,
                                     c.rung_mask, c.conf_sec, 0});
      }
      if (in_intervals(c.conf_sec, micro_iv)) {
        ++st.n_micro_conf;
        emissions.push_back(Emission{c.conf_sec + kMicroDelay, c.side, kFamMicroOpen, 0,
                                     c.rung_mask, c.conf_sec, 0});
      }
    }

    // ---- POST_SHOCK: the first confirmation AFTER an episode ends ----------
    // The confirmation universe here is G1 **and** G2 — a shock can resolve on
    // a level test just as well as on a ZigZag pivot.
    std::vector<std::pair<std::int32_t, std::int8_t>> all_conf;
    all_conf.reserve(confs.size() + g2.size());
    for (const Confirmation& c : confs) {
      all_conf.emplace_back(c.conf_sec, c.side);
    }
    for (const G2Conf& c : g2) {
      all_conf.emplace_back(c.conf_sec, c.side);
    }
    std::sort(all_conf.begin(), all_conf.end());
    all_conf.erase(std::unique(all_conf.begin(), all_conf.end()), all_conf.end());
    std::vector<std::int32_t> conf_secs;
    conf_secs.reserve(all_conf.size());
    for (const auto& c : all_conf) {
      conf_secs.push_back(c.first);
    }
    std::vector<Interval> episodes = shock_episodes(s.vt(), s.vm(), static_cast<double>(geom.mult));
    st.n_shock_episodes += static_cast<std::int64_t>(episodes.size());
    std::vector<std::uint8_t> sane_flag(static_cast<std::size_t>(s.n()), 0);
    for (std::int32_t t = 0; t < s.n(); ++t) {
      sane_flag[static_cast<std::size_t>(t)] = s.view().is_valid_second(t) ? 1 : 0;
    }
    const std::vector<Interval> ins = insane_episodes(s.view().state(), sane_flag);
    st.n_insane_episodes += static_cast<std::int64_t>(ins.size());
    episodes.insert(episodes.end(), ins.begin(), ins.end());
    for (const Interval& ep : episodes) {
      for (std::size_t i : first_confirmations_after(conf_secs, ep.b)) {
        ++st.n_post_shock;
        emissions.push_back(Emission{all_conf[i].first + kTauStar, all_conf[i].second,
                                     kFamPostShock, 0, 0, all_conf[i].first, 0});
      }
    }

    // ---- FIRST_TEST (NKD only; a feature, not a family, elsewhere) ---------
    if (first_test_is_a_family(cfg.asset)) {
      const std::vector<std::int32_t> virgin = virgin_confirmation_secs(touches);
      for (const FirstTest& ft : first_test_confirmations(g2)) {
        const bool is_virgin =
            std::binary_search(virgin.begin(), virgin.end(), ft.conf_sec);
        ++st.n_first_test;
        emissions.push_back(Emission{ft.conf_sec + kTauStar, ft.side, kFamFirstTest, 0, 0,
                                     ft.conf_sec,
                                     static_cast<std::uint8_t>(is_virgin ? kFlagFirstTestVirgin
                                                                         : 0)});
      }
    }

    std::vector<Emission> rows = dedup(emissions);

    // ---- the F-D6 flag (CC-M1-7.2: a flag on the DEDUPED candidate, never a
    // family). It reads the entry mid, so it lands after the merge and before
    // the roster rows, exactly where the oracle puts it.
    std::vector<OrExtLevel> cells_all;
    std::vector<OrExtLevel> cells_adopted;
    {
      const std::vector<std::pair<int, int>> adopted = orext_adopted_cells(cfg.asset);
      std::vector<std::int8_t> phase_at_vt(s.vt().size());
      for (std::size_t k = 0; k < s.vt().size(); ++k) {
        phase_at_vt[k] = s.phase_tag()[static_cast<std::size_t>(s.vt()[k])];
      }
      // ALL (segment x OR-minutes) cells feed bit 1; only the ADOPTED ones feed
      // bit 0 — two readings of the same construction, as CC-M1-7.2 asks.
      for (int ph = 0; ph < static_cast<int>(qr::skel::kPhaseCount); ++ph) {
        for (std::size_t mi = 0; mi < kOrMinutesCount; ++mi) {
          const int mn = kOrMinutes[mi];
          const std::vector<OrExtLevel> lv =
              orext_flag_levels(opening_range(s.vt(), s.vm(), phase_at_vt, ph, mn));
          cells_all.insert(cells_all.end(), lv.begin(), lv.end());
          for (const auto& c : adopted) {
            if (c.first == ph && c.second == mn) {
              cells_adopted.insert(cells_adopted.end(), lv.begin(), lv.end());
              break;
            }
          }
        }
      }
    }
    for (Emission& e : rows) {
      if (e.dec_sec >= s.n() || !s.view().is_valid_second(e.dec_sec)) {
        continue;
      }
      const double mid = s.view().mid()[static_cast<std::size_t>(e.dec_sec)];
      const std::int8_t ph = s.phase_tag()[static_cast<std::size_t>(e.dec_sec)];
      std::uint8_t f = 0;
      if (!cells_adopted.empty() && beyond_extension(mid, e.dec_sec, ph, cells_adopted)) {
        f = static_cast<std::uint8_t>(f | kFlagOrExtBeyond);
      }
      if (!cells_all.empty() && beyond_extension(mid, e.dec_sec, ph, cells_all)) {
        f = static_cast<std::uint8_t>(f | kFlagOrExtBeyondAny);
      }
      if (f != 0) {
        e.flags = static_cast<std::uint8_t>(e.flags | f);
        ++st.n_orext_beyond_flags;
      }
    }

    // The rung ladder compute_anchor needs is a function of the SESSION's ATR,
    // so it is built once per session. A degenerate ladder is a refusal, never
    // a silent substitution (qr_skel CONV C5).
    auto built = qr::skel::build_ladder(geom, atr, ladder);
    if (!built) {
      return refuse<GenStats>(built.error());
    }

    const std::int32_t n = s.n();
    for (const Emission& e : rows) {
      if (e.dec_sec >= n) {
        ++st.n_skip_past_close;
        continue;
      }
      // D-054: the DECISION second must be MID-SANE, not merely two-sided.
      if (!s.view().is_valid_second(e.dec_sec)) {
        ++st.n_skip_not_sane;
        continue;
      }
      qr::skel::AnchorSkeleton sk;
      auto ok = qr::skel::compute_anchor(s.view(), geom, e.side, e.dec_sec, ladder, scratch,
                                         cols.recs, &sk);
      if (!ok) {
        return refuse<GenStats>(ok.error());
      }
      cols.date8.push_back(date8);
      cols.side.push_back(e.side);
      cols.rung_mask.push_back(e.rung_mask);
      cols.conf_sec.push_back(e.conf_sec);
      cols.dec_sec.push_back(e.dec_sec);
      cols.phase_conf.push_back(s.phase_tag()[static_cast<std::size_t>(e.conf_sec)]);
      cols.phase_dec.push_back(s.phase_tag()[static_cast<std::size_t>(e.dec_sec)]);
      cols.entry_mid.push_back(sk.entry_mid);
      cols.spread_at_decision.push_back(
          s.view().spread_usd()[static_cast<std::size_t>(e.dec_sec)]);
      cols.atr14_usd.push_back(atr);
      cols.dom_share.push_back(s.dominant_share());
      cols.iid.push_back(s.iid());
      cols.mfe_unwalled.push_back(sk.mfe_usd);
      cols.mfe_argmax_sec.push_back(sk.mfe_argmax_sec);
      cols.mae_before_argmax.push_back(sk.mae_before_argmax_usd);
      cols.f_h30.push_back(sk.f_mark[0]);
      cols.f_h60.push_back(sk.f_mark[1]);
      cols.f_h120.push_back(sk.f_mark[2]);
      cols.f_phase_close.push_back(sk.f_mark[3]);
      cols.f_sess_close.push_back(sk.f_mark[4]);
      cols.phase_close_sec.push_back(sk.phase_close_sec);
      cols.sess_close_sec.push_back(sk.sess_close_sec);
      cols.f_off.push_back(sk.f_off);
      cols.f_len.push_back(sk.f_len);
      cols.a_off.push_back(sk.a_off);
      cols.a_len.push_back(sk.a_len);
      cols.fam_mask.push_back(static_cast<std::int32_t>(e.fam_bits));
      cols.level_fam_mask.push_back(static_cast<std::int32_t>(e.level_bits));
      cols.flags.push_back(e.flags);
      if ((e.fam_bits & kFamG1FastOpen) != 0) {
        ++st.n_fast_open_candidates;
      }
      for (std::size_t b = 0; b < kFamilyCount; ++b) {
        if ((e.fam_bits & static_cast<std::uint16_t>(1u << b)) != 0) {
          ++st.n_by_family[b];
        }
      }
      ++st.n_candidates;
    }
  }
  if (!cur_month.empty()) {
    auto f = flush_shard(cfg, cur_month, cols, led, &st);
    if (!f) {
      return refuse<GenStats>(f.error());
    }
  }
  return st;
}

}  // namespace qr::gen
