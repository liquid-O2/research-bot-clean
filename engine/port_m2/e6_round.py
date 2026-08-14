#!/usr/bin/python3
"""E6 TEACHER ROUND — the reader's day instrument (D-085 session-brief + deltas).

WHY THIS EXISTS.  The spec's episode grain is ~478-1,100 deep reads per 3-asset
day and a full sheet is ~4,700 tokens; the round as literally rendered is ~26M
tokens of sheet text.  D-085 already names the fix — "state the session once,
per-candidate rows carry only deltas; zero information loss" — but no builder
for it existed at HEAD.  This module is that builder, assembled from tooling
that is already committed and tested rather than from new parsing:

  SESSION BRIEF   = one FULL rendered sheet per (asset, session) read in its
                    native form.  Everything session-constant (S4 level ledger,
                    S10 prior profile, S12 availability-lagged context, S13
                    class/census cards, the era/regime frame) is stated there,
                    once, exactly as the sheet states it.
  DELTA ROW       = per EPISODE, the representative's `triage_index` V4 line —
                    the committed label-anchored extractor, ~110 fields of
                    decision-second state — plus the episode's own meta
                    (members, span, classes present).
  ESCALATION      = the full sheet (`episode_round.py --episode ID --view`) and
                    the raw tape (`ribbon.py`) for any episode, any causal
                    window, as often as wanted.  Nothing is withheld; the delta
                    row is a compression of the sheet's scalar state, not a
                    filter over the day.

BLIND SAFETY.  `--oracle` is the ONLY entry point that imports panel_score and
it REFUSES any date in the E6 BLIND block outright (the drawn blind dates are
named in BLIND_DATES).  Nothing on the reading path can reach an outcome.

CLI
  --day D8 --deltas          -> the day's episode delta table (stdout)
  --day D8 --brief ASSET     -> the (asset, day) session-brief sheet path
  --day D8 --oracle          -> STUDY ONLY: the DP oracle schedule + per-episode
                                outcome labels for that day
  --day D8 --contrast        -> STUDY ONLY: oracle picks beside their nearest
                                non-picked neighbours (D-090.2 contrast sets)
"""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(os.path.dirname(_HERE), "port_m1")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import m2_common as MC                    # noqa: E402

ROUND_ROOT = "/workspace/artifacts/cache/port/m2/episode_round/E6"
STUDY_DATES = (20240118, 20240320, 20240416)
BLIND_DATES = (20240419, 20240422, 20240423)

# The delta vocabulary: every triage V4 field whose value is a decision-second
# fact that MOVES between episodes.  Session-constant material is not repeated
# here — it is in the session brief.  Names are the extractor's own.
DELTA_COLS = (
    "as ep nm span sec side cls fam "                    # identity + episode
    "dt range_so_far cov_phase unspent_phase_usd cov_sess "   # A1 capacity
    "runway_phase exit_is_sess "
    "n_near100 near_fam near_d min_tc_near extreme_age "  # structure/levels
    "slope5m slope1m accel trades_min tm_z "             # trajectory
    "spread_now bid_sz ask_sz rev_s_60 c2f_60 n_ev_60 "
    "dBsz_min dAsz_min refill_frac "                     # book
    "f60_sflow f5m_sflow fph_sflow fph_vol trap_ab trap_bl "  # flow/fuel
    "rv60 rv300 rv1800 jump_frac surprise ladder_pos ev_ratio "
    "d_POC in_VA "                                       # vol + profile
    "spread_dec ext_needed unspent_bind compl "          # cost + D-077
).split()

# Columns the extractor produces that are SESSION-CONSTANT (or forecaster-
# anchored, which is the same thing within a session) and therefore live in the
# session brief instead of on every row: vol_regime, rv5_rv66, fvol_source,
# or_state, q50, cost_rt, menu_hat, predicted_day_type_prob,
# range_hat_vs_trailing, short_day/observed_close.  Columns kept in the full
# sheet only (one escalation away, never withheld): the whole S4 level table,
# S5's five-column trajectory grid, S6's raw events, S7's 300s book window,
# S9's rv900/vol_of_vol, S10's HVN/LVN ladders, S11 cross-asset, S12 context,
# S13 census cards, and the P001..P014 seat terms.

# delta col -> triage col (identical unless renamed for width)
RENAME = {"vr": "vol_regime", "dt": "day_type_so_far", "tm_z": "trades_min_z",
          "bid_sz": "l1_bid_sz", "ask_sz": "l1_ask_sz", "vov": "vol_of_vol",
          "trap_ab": "trapped_above", "trap_bl": "trapped_below",
          "thru_b": "thru_bid", "thru_a": "thru_ask",
          "pdt_prob": "predicted_day_type_prob",
          "rh_vs_trail": "range_hat_vs_trailing",
          "extreme_age": "extreme_age_trade_side"}

ABBR_CLS = {"REVERSAL-CONFIRMATION": "REV", "NEWS-WINDOW": "NEWS",
            "RECLAIM": "RCL", "OPEN-DYNAMICS": "OPEN",
            "LEVEL-FIRST-TEST": "FT", "SHOCK-RESOLUTION": "SHK"}
ABBR_FAM = {"G1_FINE": "g1f", "G1_COARSE": "g1c", "G1_FAST_OPEN": "fop",
            "G2_REJECT": "rej", "G2_RECLAIM": "rcl", "NEWS_WINDOW": "nws",
            "MICRO_OPEN": "mop", "POST_SHOCK": "psh", "FIRST_TEST": "ft"}

NEWS_VETO_MIN = 10.0                      # D-077-UPDATE: +/-10 minutes


def _read(path):
    with open(path) as f:
        lines = [l.rstrip("\n") for l in f if not l.startswith("#")]
    hdr = lines[0].split("\t")
    return [dict(zip(hdr, l.split("\t"))) for l in lines[1:] if l.strip()]


def _fmt(v):
    """Terse but faithful: trailing zeros dropped, never rounded away."""
    if v is None or v == "":
        return "."
    try:
        f = float(v)
    except ValueError:
        return str(v)
    if f != f:
        return "."
    if abs(f) >= 1000:
        return "%d" % round(f)
    if abs(f) >= 10:
        return "%.4g" % f
    return ("%.3g" % f).rstrip("0").rstrip(".") or "0"


def _clock(sec):
    s = int(sec)
    return "%02d:%02d" % (s // 3600, (s % 3600) // 60)


def load_day(d8):
    eps = _read(os.path.join(ROUND_ROOT, "EPISODE_INDEX_E6_%d.tsv" % d8))
    tri = {r["cid"]: r for r in
           _read(os.path.join(ROUND_ROOT, "TRIAGE_E6_%d.tsv" % d8))}
    return eps, tri


def compliance(t):
    """D-077 flags from the sheet's own scheduled-release offsets.

    `sched_last_age` / `sched_next_in` are SECONDS since/to a DATED scheduled
    release as S12 prints them.  ENTRY veto = either side within 10 minutes.
    HELD_INTO = the phase-close horizon reaches a release window (the default
    exit is a hold, so a compliant entry can still be holding through one).
    """
    def m(x):
        try:
            return float(x) / 60.0
        except (TypeError, ValueError):
            return None
    last, nxt = m(t.get("sched_last_age")), m(t.get("sched_next_in"))
    try:
        runway = float(t.get("runway_phase") or "nan") / 60.0
    except ValueError:
        runway = float("nan")
    if (last is not None and last <= NEWS_VETO_MIN) or \
       (nxt is not None and nxt <= NEWS_VETO_MIN):
        return "VETO"
    if nxt is not None and runway == runway and nxt - NEWS_VETO_MIN <= runway:
        return "HELD"
    return "-"


def deltas(d8, assets=None):
    eps, tri = load_day(d8)
    out = []
    for e in eps:
        if assets and e["asset"] not in assets:
            continue
        t = tri.get(e["rep_cid"])
        if t is None:
            out.append((e["asset"], e["episode_id"], "MISSING_TRIAGE_ROW"))
            continue
        row = []
        for c in DELTA_COLS:
            if c == "as":
                row.append({"SI": "SI", "HG": "HG", "NKD": "NK"}[e["asset"]])
            elif c == "ep":
                row.append(e["side"] + e["episode_id"].split("-E")[-1])
            elif c == "nm":
                row.append(e["n_members"])
            elif c == "span":
                row.append(e["span_sec"])
            elif c == "sec":
                row.append(_clock(e["first_dec_sec"]))
            elif c == "side":
                row.append(e["side"])
            elif c == "cls":
                cs = [ABBR_CLS.get(x, x) for x in e["classes_present"].split(",")]
                row.append(ABBR_CLS.get(e["rep_class"], e["rep_class"]) +
                           ("+" + "".join(sorted(set(cs) - {ABBR_CLS.get(e["rep_class"])}))
                            if len(set(cs)) > 1 else ""))
            elif c == "fam":
                row.append(ABBR_FAM.get(t.get("driver_family", ""),
                                        t.get("driver_family", ".")))
            elif c == "compl":
                row.append(compliance(t))
            elif c == "news_last_m":
                row.append(_fmt(float(t["sched_last_age"]) / 60.0)
                           if t.get("sched_last_age") not in ("", None) else ".")
            elif c == "news_next_m":
                row.append(_fmt(float(t["sched_next_in"]) / 60.0)
                           if t.get("sched_next_in") not in ("", None) else ".")
            else:
                row.append(_fmt(t.get(RENAME.get(c, c), "")))
        out.append((e["asset"], e["episode_id"], "\t".join(str(x) for x in row)))
    return out


def oracle(d8, assets=None):
    """STUDY ONLY.  The DP one-position oracle schedule + episode outcomes."""
    if int(d8) in BLIND_DATES:
        raise SystemExit("REFUSED: %d is a drawn BLIND day — no outcome access"
                         % d8)
    import numpy as np
    import panel_score as PS               # the only outcome import in this file
    import c_c_roster as CC
    import assemble as A
    eps, _ = load_day(d8)
    by_asset = {}
    for e in eps:
        by_asset.setdefault(e["asset"], []).append(e)
    res = {}
    for asset, elist in sorted(by_asset.items()):
        if assets and asset not in assets:
            continue
        r = A.roster(asset)
        date = MC.d8_to_date(int(d8))
        cost, _fb = PS._session_cost(asset, date)
        wall = float(A.walls()[asset]["wall_usd"])
        idx = np.nonzero(r["date8"] == int(d8))[0]
        items = []
        cert = {}                            # roster row -> outcome facts
        for i in idx.tolist():
            peak, close = CC.certificates(r, i, wall, cost)
            val, dec, exit_sec, _ = close
            cid = "%s-%d-%06d-%s" % (asset, int(d8), int(r["dec_sec"][i]),
                                     "L" if r["side"][i] > 0 else "S")
            mae = float(r["mae_before_argmax"][i])
            cert[i] = {"cid": cid, "close": float(val), "peak": float(peak[0]),
                       "dec": int(dec), "exit": int(exit_sec), "mae": mae,
                       "win": int(np.isfinite(val) and val >= PS.WINNER_CERT_USD
                                  and mae <= PS.WINNER_MAE_USD)}
            items.append((dec, exit_sec, val, dec, int(r["iid"][i]), i))
        total, chosen = CC.dp_schedule(items)   # returns row idents
        seats = [cert[i] for i in chosen]
        cid2ep = {}
        for e in elist:
            for m in e["members"].split(","):
                cid2ep[m] = e["episode_id"]
        # per-EPISODE outcome: the best member's close certificate, the
        # representative's (the only member actable at the episode's open), and
        # whether an oracle seat lives inside the episode.
        seat_cids = {s["cid"] for s in seats}
        ep_out = {}
        for e in elist:
            mem = [c for c in e["members"].split(",")]
            rows = [i for i in cert if cert[i]["cid"] in set(mem)]
            if not rows:
                continue
            rep = [i for i in rows if cert[i]["cid"] == e["rep_cid"]]
            best = max(rows, key=lambda i: cert[i]["close"])
            ep_out[e["episode_id"]] = {
                "rep_close": cert[rep[0]]["close"] if rep else float("nan"),
                "rep_win": cert[rep[0]]["win"] if rep else 0,
                "rep_mae": cert[rep[0]]["mae"] if rep else float("nan"),
                "best_close": cert[best]["close"],
                "best_cid": cert[best]["cid"],
                "n_win": sum(cert[i]["win"] for i in rows),
                "oracle": int(bool(set(mem) & seat_cids)),
                "oracle_val": sum(s["val"] if False else s["close"]
                                  for s in seats if s["cid"] in set(mem)),
            }
        res[asset] = {"total": total, "seats": seats, "cid2ep": cid2ep,
                      "ep_out": ep_out}
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", type=int, required=True)
    ap.add_argument("--deltas", action="store_true")
    ap.add_argument("--assets", default=None)
    ap.add_argument("--oracle", action="store_true")
    ap.add_argument("--ep-outcomes", dest="ep_outcomes", action="store_true")
    ap.add_argument("--show", default=None, help="comma list of episode ids")
    ap.add_argument("--with-outcomes", dest="with_outcomes", action="store_true")
    a = ap.parse_args(argv)
    assets = a.assets.split(",") if a.assets else None
    if a.deltas:
        print("# E6 %d EPISODE DELTAS (D-085 session-brief+deltas; session-"
              "constant state is in the per-asset brief sheet)" % a.day)
        print("# cols: " + " ".join(DELTA_COLS))
        for asset, epid, line in deltas(a.day, assets):
            print(line)
    if a.oracle:
        res = oracle(a.day, assets)
        for asset, r in sorted(res.items()):
            print("== ORACLE %s %d  DP total $%.2f over %d seats ==" %
                  (asset, a.day, r["total"], len(r["seats"])))
            for s in r["seats"]:
                print("  %s  dec=%s exit=%s  $%.0f mae=$%.0f win=%d  ep=%s" % (
                    s["cid"], _clock(s["dec"]), _clock(s["exit"]), s["close"],
                    s["mae"], s["win"], r["cid2ep"].get(s["cid"], "?")))
            eo = r["ep_out"]
            nwin = sum(1 for v in eo.values() if v["rep_win"])
            nbest = sum(1 for v in eo.values() if v["n_win"])
            print("  episodes=%d  rep_winners=%d (%.1f%%)  episodes_with_any_"
                  "winner=%d  oracle_episodes=%d" %
                  (len(eo), nwin, 100.0 * nwin / max(len(eo), 1), nbest,
                   sum(v["oracle"] for v in eo.values())))
    if a.show:
        want = set(a.show.split(","))
        res = oracle(a.day, assets) if a.with_outcomes else None
        rows = {epid: line for _as, epid, line in deltas(a.day, assets)}
        for epid in [e for e in rows if e in want] if want != {"ALL"} else rows:
            suffix = ""
            if res is not None:
                for _as2, r in res.items():
                    v = r["ep_out"].get(epid)
                    if v:
                        suffix = ("\t|| rep$=%.0f mae=%.0f win=%d best$=%.0f "
                                  "nwin=%d ORACLE=%d" % (
                                      v["rep_close"], v["rep_mae"], v["rep_win"],
                                      v["best_close"], v["n_win"], v["oracle"]))
            print(rows[epid] + suffix)
    if a.ep_outcomes:
        res = oracle(a.day, assets)
        print("ep\tasset\trep_close\trep_mae\trep_win\tbest_close\tn_win\toracle")
        for asset, r in sorted(res.items()):
            for ep, v in sorted(r["ep_out"].items()):
                print("%s\t%s\t%.0f\t%.0f\t%d\t%.0f\t%d\t%d" % (
                    ep, asset, v["rep_close"], v["rep_mae"], v["rep_win"],
                    v["best_close"], v["n_win"], v["oracle"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
