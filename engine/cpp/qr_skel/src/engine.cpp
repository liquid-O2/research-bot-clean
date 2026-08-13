#include "qr_skel/engine.hpp"

#include <openssl/sha.h>

#include <algorithm>
#include <charconv>
#include <cstdio>

#include "qr_skel/binpack.hpp"
#include "qr_skel/geom.hpp"
#include "qr_skel/session.hpp"

namespace qr::skel {
namespace {

/// The frozen M1.B spec this engine implements (PORT_M1B_SPEC.md sha16). The
/// test suite recomputes it from the file: a pin nobody checks is decoration.
constexpr const char* kSpecSha16 = "2b83f9e70340a413";

/// Shortest round-trip decimal, the float convention of the CC-M1-2 addendum.
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

/// One anchor's worth of column buffers for the whole shard.
struct AnchorColumns {
  std::vector<std::int32_t> anchor_sec, observed_secs;
  std::vector<double> entry_mid;
  std::vector<std::int32_t> tau_up, tau_dn;  // row-major [n][kRungCount]
  std::vector<double> f_h30, f_h60, f_h120, f_phase_close, f_sess_close;
  std::vector<std::int32_t> phase_close_sec, sess_close_sec;
  std::vector<double> mfe_usd, mae_before_argmax_usd, mae_unwalled_usd, f_terminal_usd,
      giveback_post_peak_usd, uw_share, monotonicity;
  std::vector<std::int32_t> mfe_argmax_sec, time_to_peak_secs, time_underwater_secs, mono_steps;
  std::vector<std::int64_t> f_off, f_len, a_off, a_len;
  RecordArrays recs;

  void append(const AnchorSkeleton& a) {
    anchor_sec.push_back(a.anchor_sec);
    observed_secs.push_back(a.observed_secs);
    entry_mid.push_back(a.entry_mid);
    tau_up.insert(tau_up.end(), a.tau_up, a.tau_up + kRungCount);
    tau_dn.insert(tau_dn.end(), a.tau_dn, a.tau_dn + kRungCount);
    f_h30.push_back(a.f_mark[0]);
    f_h60.push_back(a.f_mark[1]);
    f_h120.push_back(a.f_mark[2]);
    f_phase_close.push_back(a.f_mark[3]);
    f_sess_close.push_back(a.f_mark[4]);
    phase_close_sec.push_back(a.phase_close_sec);
    sess_close_sec.push_back(a.sess_close_sec);
    mfe_usd.push_back(a.mfe_usd);
    mfe_argmax_sec.push_back(a.mfe_argmax_sec);
    mae_before_argmax_usd.push_back(a.mae_before_argmax_usd);
    mae_unwalled_usd.push_back(a.mae_unwalled_usd);
    f_terminal_usd.push_back(a.f_terminal_usd);
    giveback_post_peak_usd.push_back(a.giveback_post_peak_usd);
    time_to_peak_secs.push_back(a.time_to_peak_secs);
    time_underwater_secs.push_back(a.time_underwater_secs);
    uw_share.push_back(a.uw_share);
    mono_steps.push_back(a.mono_steps);
    monotonicity.push_back(a.monotonicity);
    f_off.push_back(a.f_off);
    f_len.push_back(a.f_len);
    a_off.push_back(a.a_off);
    a_len.push_back(a.a_len);
  }

  void emit(BinPackWriter& w, const std::string& p) const {
    w.add(p + "anchor_sec", "int32", anchor_sec);
    w.add(p + "observed_secs", "int32", observed_secs);
    w.add(p + "entry_mid", "float64", entry_mid);
    w.add(p + "tau_up", "int32", tau_up);
    w.add(p + "tau_dn", "int32", tau_dn);
    w.add(p + "f_h30", "float64", f_h30);
    w.add(p + "f_h60", "float64", f_h60);
    w.add(p + "f_h120", "float64", f_h120);
    w.add(p + "f_phase_close", "float64", f_phase_close);
    w.add(p + "f_sess_close", "float64", f_sess_close);
    w.add(p + "phase_close_sec", "int32", phase_close_sec);
    w.add(p + "sess_close_sec", "int32", sess_close_sec);
    w.add(p + "mfe_usd", "float64", mfe_usd);
    w.add(p + "mfe_argmax_sec", "int32", mfe_argmax_sec);
    w.add(p + "mae_before_argmax_usd", "float64", mae_before_argmax_usd);
    w.add(p + "mae_unwalled_usd", "float64", mae_unwalled_usd);
    w.add(p + "f_terminal_usd", "float64", f_terminal_usd);
    w.add(p + "giveback_post_peak_usd", "float64", giveback_post_peak_usd);
    w.add(p + "time_to_peak_secs", "int32", time_to_peak_secs);
    w.add(p + "time_underwater_secs", "int32", time_underwater_secs);
    w.add(p + "uw_share", "float64", uw_share);
    w.add(p + "mono_steps", "int32", mono_steps);
    w.add(p + "monotonicity", "float64", monotonicity);
    w.add(p + "f_off", "int64", f_off);
    w.add(p + "f_len", "int64", f_len);
    w.add(p + "a_off", "int64", a_off);
    w.add(p + "a_len", "int64", a_len);
    w.add(p + "skel_f_t", "int32", recs.f_t);
    w.add(p + "skel_f_v", "float32", recs.f_v);
    w.add(p + "skel_a_t", "int32", recs.a_t);
    w.add(p + "skel_a_v", "float32", recs.a_v);
  }
};

}  // namespace

Expected<SanityTable, Refusal> SanityTable::load(const std::string& stem) {
  auto pack = BinPack::load(stem, "QRSANE1");
  if (!pack) {
    return refuse<SanityTable>(pack.error());
  }
  auto d8 = pack.value().get<std::int32_t>("date8", "int32");
  auto med = pack.value().get<double>("phase_median_spread_usd", "float64");
  if (!d8) return refuse<SanityTable>(d8.error());
  if (!med) return refuse<SanityTable>(med.error());
  SanityTable t;
  t.date8_ = std::move(d8).value();
  t.med_ = std::move(med).value();
  if (t.med_.size() != t.date8_.size() * kPhaseCount) {
    return refuse<SanityTable>(Refusal(RefusalCode::SCHEMA_MISMATCH, "qr_skel::SanityTable::load",
                                       "median table is not n x kPhaseCount"));
  }
  for (std::size_t i = 1; i < t.date8_.size(); ++i) {
    if (t.date8_[i] <= t.date8_[i - 1]) {
      return refuse<SanityTable>(Refusal(RefusalCode::OUT_OF_ORDER, "qr_skel::SanityTable::load",
                                         "sanity table dates are not strictly ascending",
                                         t.date8_[i]));
    }
  }
  for (double v : t.med_) {
    if (!(v > 0.0) || !(v < 1e12)) {
      return refuse<SanityTable>(Refusal(RefusalCode::CONTENT_MISMATCH, "qr_skel::SanityTable::load",
                                         "a phase median spread is not a positive finite dollar value"));
    }
  }
  return t;
}

Expected<SanityPolicy, Refusal> SanityTable::policy_for(std::int32_t date8) const {
  const auto it = std::lower_bound(date8_.begin(), date8_.end(), date8);
  if (it == date8_.end() || *it != date8) {
    return refuse<SanityPolicy>(Refusal(RefusalCode::UNKNOWN_SESSION, "qr_skel::SanityTable::policy_for",
                                        "no mid-sanity medians for this trade date", date8));
  }
  const std::size_t row = static_cast<std::size_t>(it - date8_.begin());
  SanityPolicy p;
  p.enabled = true;
  for (std::size_t k = 0; k < kPhaseCount; ++k) {
    p.phase_median_spread_usd[k] = med_[row * kPhaseCount + k];
  }
  return p;
}

Expected<CandidateSet, Refusal> CandidateSet::load(const std::string& stem) {
  auto pack = BinPack::load(stem, "QRCAND1");
  if (!pack) {
    return refuse<CandidateSet>(pack.error());
  }
  const BinPack& p = pack.value();
  const qr::futsess::Json* an = p.sidecar().find("asset");
  if (an == nullptr || an->type() != qr::futsess::Json::Type::String) {
    return refuse<CandidateSet>(Refusal(RefusalCode::SCHEMA_MISMATCH, "qr_skel::CandidateSet::load",
                                        "candidate receipt names no asset"));
  }
  CandidateSet out;
  if (!qr::futsess::asset_from_name(an->str(), &out.asset)) {
    return refuse<CandidateSet>(Refusal(RefusalCode::SCHEMA_MISMATCH, "qr_skel::CandidateSet::load",
                                        "candidate receipt names an unknown asset"));
  }
  auto cid = p.get<std::int64_t>("cand_id", "int64");
  auto d8 = p.get<std::int32_t>("date8", "int32");
  auto ds = p.get<std::int32_t>("dec_sec", "int32");
  auto sd = p.get<std::int8_t>("side", "int8");
  auto at = p.get<double>("atr14_usd", "float64");
  if (!cid) return refuse<CandidateSet>(cid.error());
  if (!d8) return refuse<CandidateSet>(d8.error());
  if (!ds) return refuse<CandidateSet>(ds.error());
  if (!sd) return refuse<CandidateSet>(sd.error());
  if (!at) return refuse<CandidateSet>(at.error());
  const std::size_t n = cid.value().size();
  if (d8.value().size() != n || ds.value().size() != n || sd.value().size() != n ||
      at.value().size() != n) {
    return refuse<CandidateSet>(Refusal(RefusalCode::SCHEMA_MISMATCH, "qr_skel::CandidateSet::load",
                                        "candidate columns have unequal lengths"));
  }
  out.rows.resize(n);
  for (std::size_t i = 0; i < n; ++i) {
    out.rows[i] = Candidate{cid.value()[i], d8.value()[i], ds.value()[i], sd.value()[i],
                            at.value()[i]};
    if (i != 0 && out.rows[i].date8 < out.rows[i - 1].date8) {
      return refuse<CandidateSet>(Refusal(RefusalCode::OUT_OF_ORDER, "qr_skel::CandidateSet::load",
                                          "candidate date8 column is not non-decreasing",
                                          out.rows[i].date8));
    }
  }
  return out;
}

const char* spec_sha16_pin() noexcept { return kSpecSha16; }

Expected<std::string, Refusal> file_sha16(const std::string& path) {
  std::FILE* fh = std::fopen(path.c_str(), "rb");
  if (fh == nullptr) {
    return refuse<std::string>(Refusal(RefusalCode::IO, "qr_skel::file_sha16", "cannot open file"));
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
  std::fclose(fh);
  return hex_sha256(all).substr(0, 16);
}

std::string params_canonical_json(Asset asset, std::size_t chunk_candidates) {
  // Canonical JSON: keys SORTED, UTF-8, no whitespace, floats shortest
  // round-trip (CC-M1-2 addendum, journal 2026-08-13 09:55Z). The key order
  // below is alphabetical and is asserted by the test suite.
  std::string s = "{";
  s += "\"anchor_count\":" + std::to_string(kAnchorCount);
  s += ",\"anchor_d1_delay_secs\":" + std::to_string(kAnchorD1Delay);
  s += ",\"asset\":\"" + std::string(qr::futsess::asset_spec(asset).name) + "\"";
  s += ",\"chunk_candidates\":" + std::to_string(chunk_candidates);
  s += ",\"horizon_secs\":[" + std::to_string(kHorizonSecs[0]) + "," +
       std::to_string(kHorizonSecs[1]) + "," + std::to_string(kHorizonSecs[2]) + "]";
  s += ",\"rung_count\":" + std::to_string(kRungCount);
  s += ",\"rung_step\":" + fmt_double(kRungStep);
  s += ",\"spec_sha16\":\"" + std::string(kSpecSha16) + "\"";
  s += "}";
  return s;
}

std::string params_hash(Asset asset, std::size_t chunk_candidates) {
  return hex_sha256(params_canonical_json(asset, chunk_candidates));
}

Expected<ShardStats, Refusal> build_shard(const CandidateSet& set, std::size_t lo, std::size_t hi,
                                          const ShardOptions& opt) {
  if (lo > hi || hi > set.rows.size()) {
    return refuse<ShardStats>(Refusal(RefusalCode::CONFIG, "qr_skel::build_shard",
                                      "shard range is not inside the candidate set"));
  }
  if (opt.chunk_candidates == 0 || opt.chunk_candidates > kChunkCandidatesMax) {
    return refuse<ShardStats>(Refusal(RefusalCode::CONFIG, "qr_skel::build_shard",
                                      "chunk size outside the bounded-execution law",
                                      static_cast<std::int64_t>(opt.chunk_candidates)));
  }
  if (hi - lo > kShardCandidateCap) {
    // ATLAS §3.2.6: whole-shard collection REFUSES above the cap rather than
    // quietly buffering a multi-million-row table.
    return refuse<ShardStats>(Refusal(RefusalCode::CONFIG, "qr_skel::build_shard",
                                      "shard exceeds the whole-table collection cap",
                                      static_cast<std::int64_t>(hi - lo)));
  }

  const AssetGeom& geom = asset_geom(opt.asset);
  ShardStats st;

  std::vector<std::int64_t> cand_id;
  std::vector<std::int32_t> date8, dec_sec;
  std::vector<std::int8_t> side;
  std::vector<double> atr14;
  AnchorColumns cols[kAnchorCount];

  ChunkScratch scratch;
  // The bounded chunk buffer: kAnchorCount rows per candidate, never more.
  std::vector<AnchorSkeleton> chunk_buf;
  chunk_buf.reserve(opt.chunk_candidates * kAnchorCount);

  SessionView session;
  std::int32_t loaded_date = -1;
  bool have_session = false;
  double ladder[kRungCount];

  for (std::size_t base = lo; base < hi; base += opt.chunk_candidates) {
    const std::size_t stop = std::min(base + opt.chunk_candidates, hi);
    chunk_buf.clear();
    // Records are appended per candidate, so the chunk's candidate-level rows
    // are staged and flushed together with them below.
    for (std::size_t i = base; i < stop; ++i) {
      const Candidate& c = set.rows[i];
      if (!have_session || c.date8 != loaded_date) {
        SanityPolicy policy;
        if (!opt.sanity.empty()) {
          auto pol = opt.sanity.policy_for(c.date8);
          if (!pol) {
            return refuse<ShardStats>(pol.error());
          }
          policy = pol.value();
        }
        auto s = SessionView::load(opt.session_dir, c.date8, policy);
        if (!s) {
          return refuse<ShardStats>(s.error());
        }
        session = std::move(s).value();
        loaded_date = c.date8;
        have_session = true;
        ++st.n_sessions;
        st.n_seconds_insane += session.n_insane();
        st.n_seconds_two_sided += session.n_two_sided();
      }
      auto built = build_ladder(geom, c.atr14_usd, ladder);
      if (!built) {
        // CONV C5: a degenerate ladder emits NO row and is counted by cause.
        if (!(c.atr14_usd > 0.0) || !(c.atr14_usd == c.atr14_usd)) {
          ++st.n_refused_atr;
        } else {
          ++st.n_refused_ladder;
        }
        continue;
      }
      const std::size_t before = chunk_buf.size();
      chunk_buf.resize(before + kAnchorCount);
      for (std::size_t a = 0; a < kAnchorCount; ++a) {
        const std::int32_t anchor_sec =
            c.dec_sec + static_cast<std::int32_t>(a) * kAnchorD1Delay;
        auto r = compute_anchor(session, geom, c.side, anchor_sec, ladder, scratch,
                                cols[a].recs, &chunk_buf[before + a]);
        if (!r) {
          return refuse<ShardStats>(r.error());
        }
        if (chunk_buf[before + a].observed_secs == 0) {
          if (a == 0) {
            ++st.n_unavailable_d0;
          } else {
            ++st.n_unavailable_d1;
          }
        }
      }
      cand_id.push_back(c.cand_id);
      date8.push_back(c.date8);
      dec_sec.push_back(c.dec_sec);
      side.push_back(c.side);
      atr14.push_back(c.atr14_usd);
      for (std::size_t a = 0; a < kAnchorCount; ++a) {
        cols[a].append(chunk_buf[before + a]);
      }
      ++st.n_candidates;
    }
    st.max_live_anchor_rows =
        std::max(st.max_live_anchor_rows, static_cast<std::int64_t>(chunk_buf.size()));
  }

  BinPackWriter w;
  w.add("cand_id", "int64", cand_id);
  w.add("date8", "int32", date8);
  w.add("dec_sec", "int32", dec_sec);
  w.add("side", "int8", side);
  w.add("atr14_usd", "float64", atr14);
  for (std::size_t a = 0; a < kAnchorCount; ++a) {
    cols[a].emit(w, "a" + std::to_string(a) + "_");
    st.n_records_f += static_cast<std::int64_t>(cols[a].recs.f_t.size());
    st.n_records_a += static_cast<std::int64_t>(cols[a].recs.a_t.size());
  }
  st.stored_rows = static_cast<std::int64_t>(cand_id.size());
  st.stored_bytes = static_cast<std::int64_t>(w.byte_size());

  const std::string phash = params_hash(opt.asset, opt.chunk_candidates);
  const std::string pjson = params_canonical_json(opt.asset, opt.chunk_candidates);
  auto wrote = w.write(opt.out_stem, "QRSKEL1", [&](qr::futsess::JsonWriter& jw) {
    jw.key("asset");
    jw.value_string(qr::futsess::asset_spec(opt.asset).name);
    jw.key("month");
    jw.value_string(opt.month);
    jw.key("spec_sha16");
    jw.value_string(kSpecSha16);
    jw.key("conv_doc");
    jw.value_string("design/PORT_M1B_S3_CONV.md");
    jw.key("params_json");
    jw.value_string(pjson);
    jw.key("params_hash");
    jw.value_string(phash);
    jw.key("rung_count");
    jw.value_int(static_cast<std::int64_t>(kRungCount));
    jw.key("anchor_count");
    jw.value_int(static_cast<std::int64_t>(kAnchorCount));
    jw.key("n_candidates");
    jw.value_int(st.n_candidates);
    jw.key("n_sessions");
    jw.value_int(st.n_sessions);
    jw.key("n_refused_atr");
    jw.value_int(st.n_refused_atr);
    jw.key("n_refused_ladder");
    jw.value_int(st.n_refused_ladder);
    jw.key("n_unavailable_d0");
    jw.value_int(st.n_unavailable_d0);
    jw.key("n_unavailable_d1");
    jw.value_int(st.n_unavailable_d1);
    jw.key("max_live_anchor_rows");
    jw.value_int(st.max_live_anchor_rows);
    jw.key("chunk_candidates");
    jw.value_int(static_cast<std::int64_t>(opt.chunk_candidates));
    jw.key("mid_sanity_enabled");
    jw.value_bool(!opt.sanity.empty());
    jw.key("n_seconds_two_sided");
    jw.value_int(st.n_seconds_two_sided);
    jw.key("n_seconds_insane");
    jw.value_int(st.n_seconds_insane);
  });
  if (!wrote) {
    return refuse<ShardStats>(wrote.error());
  }
  return st;
}

}  // namespace qr::skel
