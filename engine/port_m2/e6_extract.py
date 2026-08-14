#!/usr/bin/python3
"""E6 EXTRACTION — the teacher round turned into distillable evidence (D-082/D-086/D-078).

WHAT THIS IS.  The E6 round left three kinds of record: the SEALED per-episode call
ledgers (`provenance/port_m2/E6_*.tsv`), the reader's own decision function with its
hand-typed reasons (`e6_calls.py`), and the per-episode decision-second state it read
(`artifacts/cache/port/m2/episode_round/E6/DELTAS_*.txt`).  This module joins all three
to realized outcomes and emits the three committed artifacts that
`provenance/port_m2/E6_EXTRACTION.md` and `design/TEACHER_FEATURES_V1.md` are written on:

  E6_EPISODE_OUTCOMES.tsv  per-episode realized outcome, all six round days
  E6_PAIRING.tsv           the D-086 full-spectrum pairing table (168 rows)
  E6_CUE_CENSUS.tsv        the D-056 name->count census, per scope, per cue, per day

WHY THE CUES ARE PREDICATES AND NOT PROSE.  D-056 asks for name->count.  Every cue below
is one of the READER'S OWN names (from ERA_NOTES_E6.md, the rubric source, or a hand-typed
`why`), rendered as a predicate over the exact `triage_index` fields the reader read, so
the name can be counted on every episode of every day.  Where a named cue is NOT
computable from the round's reading surface (E6-H1 refail chain; E6-H2 as a digest
SEQUENCE) it is absent here and carried as a build order in TEACHER_FEATURES_V1 §6 —
never silently proxied into the census.

OUTCOME ACCESS.  This module imports panel_score and is POST-UNSEAL ONLY.  It is not on
any reading path; e6_round.py's blind fence is untouched.

CLI
  --outcomes   rebuild E6_EPISODE_OUTCOMES.tsv from panel_score (slow; ~4,227 episodes)
  --pair       rebuild E6_PAIRING.tsv
  --census     rebuild E6_CUE_CENSUS.tsv
  --all        all three, in order
"""
import argparse
import csv
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(os.path.dirname(_HERE), "port_m1")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import m2_common as MC                     # noqa: E402

ROUND_ROOT = "/workspace/artifacts/cache/port/m2/episode_round/E6"
PROV = "/workspace/provenance/port_m2"
STUDY_DATES = (20240118, 20240320, 20240416)
BLIND_DATES = (20240419, 20240422, 20240423)
DAYS = STUDY_DATES + BLIND_DATES

# The SEALED ledgers.  Study days 2-3 have none (round defect X-4) and are
# reconstructed from e6_calls at HEAD; day 3 reproduces the contemporaneous
# record exactly, day 2 does not (6 takes vs 4) because day 2 was scored under
# the pre-correction rubric.  The provenance is carried in the `ledger_src`
# column so no downstream reader can mistake one for the other.
SEALED = {20240118: PROV + "/E6_CALLS_20240118.tsv",
          20240419: PROV + "/E6_BLIND_D1_20240419.tsv",
          20240422: PROV + "/E6_BLIND_20240422.tsv",
          20240423: PROV + "/E6_BLIND_20240423.tsv"}

HDR = ("# E6 EXTRACTION companion — see provenance/port_m2/E6_EXTRACTION.md and "
       "design/TEACHER_FEATURES_V1.md\n"
       "# target = panel_score.outcome(rep_cid)['winner_close'] (D-021)\n")

OUTCOMES = PROV + "/E6_EPISODE_OUTCOMES.tsv"
PAIRING = PROV + "/E6_PAIRING.tsv"
CENSUS = PROV + "/E6_CUE_CENSUS.tsv"


# ------------------------------------------------------------------- io ------
def _rows(path):
    with open(path) as f:
        lines = [l for l in f if not l.startswith("#")]
    return list(csv.DictReader(lines, delimiter="\t"))


def episode_index(d8):
    return _rows(os.path.join(ROUND_ROOT, "EPISODE_INDEX_E6_%d.tsv" % d8))


def delta_rows(d8):
    """(asset, ep) -> the reader's own delta row, keyed by its own column names."""
    p = os.path.join(ROUND_ROOT, "DELTAS_%d.txt" % d8)
    with open(p) as f:
        f.readline()
        cols = f.readline().split("cols:")[1].split()
        out = {}
        for line in f:
            cells = line.rstrip("\n").split("\t")
            if len(cells) < 3:
                continue
            d = dict(zip(cols, cells))
            out[(d["as"], d["ep"])] = d
    return out


def ledger(d8):
    p = SEALED.get(d8)
    if p:
        return {r["ep"]: r for r in _rows(p)}, "SEALED"
    import e6_calls as C                    # noqa: E402 — reconstruction only
    out = {}
    for c in C.calls(d8):
        tk = C.schedule(C.calls(d8)) if not out else None
        out[c["ep"]] = c
    cl = C.calls(d8)
    tkset = {t["ep"] for t in C.schedule(cl)}
    return ({c["ep"]: {"ep": c["ep"], "asset": c["as"], "sec": c["sec"],
                       "side": c["side"], "p": "%.3f" % c["p"],
                       "call": "TAKE" if c["ep"] in tkset else "SKIP",
                       "src": c["src"], "compl": c["compl"], "why": c["why"]}
             for c in cl}, "RECONSTRUCTED")


# -------------------------------------------------------------- outcomes -----
def build_outcomes():
    """Per-episode realized outcome for every round day.  POST-UNSEAL ONLY."""
    import numpy as np
    import panel_score as PS
    import c_c_roster as CC
    import assemble as A

    with open(OUTCOMES, "w") as w:
        w.write(HDR)
        w.write("\t".join([
            "date8", "episode_id", "asset", "side", "rep_cid", "rep_class",
            "rep_phase", "first_dec_sec", "n_members", "rep_close", "rep_mae",
            "rep_walled", "rep_win", "best_close", "best_cid", "n_win",
            "oracle_seat"]) + "\n")
        for d8 in DAYS:
            by_asset = {}
            for e in episode_index(d8):
                by_asset.setdefault(e["asset"], []).append(e)
            for asset, elist in sorted(by_asset.items()):
                r = A.roster(asset)
                cost, _fb = PS._session_cost(asset, MC.d8_to_date(int(d8)))
                wall = float(A.walls()[asset]["wall_usd"])
                idx = np.nonzero(r["date8"] == int(d8))[0]
                items, cert, cid2row = [], {}, {}
                for i in idx.tolist():
                    peak, close = CC.certificates(r, i, wall, cost)
                    val, dec, exit_sec, _ = close
                    cid = "%s-%d-%06d-%s" % (asset, int(d8),
                                             int(r["dec_sec"][i]),
                                             "L" if r["side"][i] > 0 else "S")
                    mae = float(r["mae_before_argmax"][i])
                    _tw, _mfe, _am, walled = CC._skel_query(r, i, wall)
                    cert[i] = {
                        "cid": cid, "close": float(val), "mae": mae,
                        "walled": int(bool(walled)),
                        "win": int(np.isfinite(val)
                                   and val >= PS.WINNER_CERT_USD
                                   and mae <= PS.WINNER_MAE_USD
                                   and not bool(walled))}
                    cid2row[cid] = i
                    items.append((dec, exit_sec, val, dec, int(r["iid"][i]), i))
                _total, chosen = CC.dp_schedule(items)
                seat_cids = {cert[i]["cid"] for i in chosen}
                for e in elist:
                    mem = e["members"].split(",")
                    rws = [cid2row[c] for c in mem if c in cid2row]
                    if not rws:
                        continue
                    rep = cid2row.get(e["rep_cid"])
                    best = max(rws, key=lambda i: cert[i]["close"])
                    w.write("\t".join(str(x) for x in [
                        d8, e["episode_id"], asset, e["side"], e["rep_cid"],
                        e["rep_class"], e["rep_phase"], e["first_dec_sec"],
                        e["n_members"],
                        "%.2f" % cert[rep]["close"], "%.2f" % cert[rep]["mae"],
                        cert[rep]["walled"], cert[rep]["win"],
                        "%.2f" % cert[best]["close"], cert[best]["cid"],
                        sum(cert[i]["win"] for i in rws),
                        int(bool(set(mem) & seat_cids))]) + "\n")
    return OUTCOMES


# ---------------------------------------------------------------- master -----
FIELDS = ("nm range_so_far cov_phase unspent_phase_usd cov_sess runway_phase "
          "exit_is_sess n_near100 near_fam near_d min_tc_near extreme_age "
          "slope5m slope1m trades_min tm_z spread_now refill_frac f60_sflow "
          "f5m_sflow fph_sflow fph_vol trap_ab trap_bl rv60 rv300 rv1800 "
          "ladder_pos ev_ratio d_POC in_VA spread_dec n_ev_60 unspent_bind "
          "compl").split()


def master():
    """calls x delta state x outcome, one row per episode, all six days."""
    out = {r["episode_id"]: r for r in _rows(OUTCOMES)}
    rows = []
    for d8 in DAYS:
        dl = delta_rows(d8)
        lg, lsrc = ledger(d8)
        for eid, lr in lg.items():
            pp = eid.split("-")
            d = dl.get((lr["asset"], pp[2] + pp[3][1:].zfill(2)))
            o = out.get(eid)
            if d is None or o is None:
                continue
            row = {"date8": str(d8),
                   "block": "STUDY" if d8 in STUDY_DATES else "BLIND",
                   "ledger_src": lsrc, "episode_id": eid, "asset": o["asset"],
                   "side": lr["side"], "sec": lr["sec"], "phase": o["rep_phase"],
                   "cls": o["rep_class"], "call": lr["call"], "src": lr["src"],
                   "p": lr["p"], "why": lr["why"], "rep_close": o["rep_close"],
                   "rep_mae": o["rep_mae"], "rep_walled": o["rep_walled"],
                   "rep_win": o["rep_win"], "best_close": o["best_close"],
                   "n_win": o["n_win"], "oracle_seat": o["oracle_seat"]}
            for k in FIELDS:
                row[k] = d.get(k, ".")
            rows.append(row)
    _phase_elapsed(rows)
    for r in rows:
        r["_c"] = cues(r)
        r["_w"] = int(r["rep_win"])
        r["_u"] = num(r["rep_close"])
    return rows


def _phase_elapsed(rows):
    """Phase-elapsed fraction, keyed EXACTLY as e6_calls.schedule() keys phases."""
    groups = {}
    for r in rows:
        try:
            sec = int(r["sec"][:2]) * 3600 + int(r["sec"][3:5]) * 60
            rw = float(r["runway_phase"])
        except (ValueError, TypeError):
            r["_elapsed"] = float("nan")
            continue
        r["_sec"], r["_close"] = sec, sec + rw
        groups.setdefault((r["date8"], r["asset"],
                           round(r["_close"] / 60.0)), []).append(r)
    for _k, lst in groups.items():
        op = min(x["_sec"] for x in lst)
        span = max(max(x["_close"] for x in lst) - op, 1.0)
        for x in lst:
            x["_elapsed"] = (x["_sec"] - op) / span
    for r in rows:
        r.setdefault("_elapsed", float("nan"))


def num(v, default=float("nan")):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ------------------------------------------------------------------ cues -----
def cues(r):
    """The reader's OWN vocabulary, made countable.  Sources named per line."""
    def g(k):
        return num(r.get(k))
    s = 1.0 if r["side"] == "L" else -1.0
    un, rw, el = g("unspent_phase_usd"), g("runway_phase"), r["_elapsed"]
    nd, tc, age = g("near_d"), g("min_tc_near"), g("extreme_age")
    f5, f60, fph = g("f5m_sflow"), g("f60_sflow"), g("fph_sflow")
    ta, tb, nev = g("trap_ab"), g("trap_bl"), g("n_ev_60")
    rv60, rv1800, tmz = g("rv60"), g("rv1800"), g("tm_z")
    sp, dpoc, rf, cov = g("spread_dec"), g("d_POC"), g("refill_frac"), g("cov_phase")
    lad = str(r.get("ladder_pos", ""))
    c = {}
    # ERA_NOTES §1.3 "the phase-open reset is the single richest moment"
    c["phase_open"] = el == el and el <= 0.15
    # ERA_NOTES §1.2 "unspent_phase_usd is the live number"; rubric room_ok
    c["capacity_room"] = un == un and un >= 400.0
    c["capacity_big"] = un == un and un >= 1000.0
    c["capacity_spent"] = un == un and un < 400.0
    c["phase_open_reset"] = bool(c["phase_open"] and c["capacity_room"])
    c["runway_ok"] = rw == rw and rw >= 2400.0            # rubric time_ok
    # E6-H3 level confluence at the entry price
    c["level_at_price"] = nd == nd and abs(nd) <= 10.0
    c["level_near"] = nd == nd and abs(nd) <= 60.0
    c["level_tested_held"] = bool(c["level_near"] and tc == tc and tc >= 1)
    c["fresh_extreme"] = age == age and age <= 900.0      # rubric fresh
    c["stale_extreme"] = age == age and age > 6000.0      # rubric stale
    c["flow_agree_5m"] = f5 == f5 and f5 * s > 0          # rubric flow
    c["flow_against_5m"] = f5 == f5 and f5 * s < -20
    # ERA_NOTES §6 "signed flow one-sided with the trade at BOTH windows"
    c["one_sided_flow"] = bool(f5 == f5 and fph == fph and f5 * s > 0 and fph * s > 0)
    c["flow_strong"] = bool(c["one_sided_flow"] and abs(f5) >= 50)
    # E6-H2 PROXY ONLY — the true form is a digest SEQUENCE (see features doc §6)
    c["flow_flip"] = bool(f60 == f60 and f5 == f5 and f60 * s > 0 and f5 * s <= 0)
    c["fuel_trapped"] = bool(ta == ta and tb == tb and (ta + tb) > 0
                             and ((ta if s > 0 else tb) / (ta + tb)) >= 0.65)
    # E6-H4 event burst
    c["event_burst"] = bool(nev == nev and nev >= 400 and rv60 == rv60
                            and rv1800 == rv1800 and rv1800 > 0
                            and rv60 > 0.4 * rv1800)
    c["tmz_burst"] = tmz == tmz and tmz >= 3.0
    c["wide_spread"] = sp == sp and sp >= 50.0            # rubric wide (negative)
    c["expanding"] = bool(lad.startswith("at_or_above_q5")
                          or lad.startswith("at_or_above_q7")
                          or lad.startswith("at_or_above_q9")
                          or (rv60 == rv60 and rv1800 == rv1800 and rv1800 > 0
                              and rv60 > 0.9 * rv1800))   # the day-2 correction
    c["poc_magnet"] = bool(dpoc == dpoc and dpoc * s > 0 and abs(dpoc) >= 200.0)
    c["refill_book"] = rf == rf and rf >= 0.60
    c["cov_low"] = cov == cov and cov <= 40.0
    # ERA_NOTES §6, the reader's stated blind rule, verbatim
    c["NAMED_TRIAD"] = bool(c["phase_open_reset"] and c["level_near"]
                            and c["one_sided_flow"])
    c["NAMED_TRIAD_soft"] = bool(c["capacity_room"] and c["level_near"]
                                 and c["one_sided_flow"])
    return c


CUE_ORDER = ["phase_open", "capacity_room", "capacity_big", "capacity_spent",
             "phase_open_reset", "runway_ok", "level_at_price", "level_near",
             "level_tested_held", "fresh_extreme", "stale_extreme",
             "flow_agree_5m", "flow_against_5m", "one_sided_flow", "flow_strong",
             "flow_flip", "fuel_trapped", "event_burst", "tmz_burst",
             "wide_spread", "expanding", "poc_magnet", "refill_book", "cov_low",
             "NAMED_TRIAD", "NAMED_TRIAD_soft"]

# The screens TEACHER_FEATURES_V1 proposes, censused beside the reader's names.
SCREENS = {
    "SEAT_LIVE": lambda r: (num(r["unspent_phase_usd"]) >= 700
                            and num(r["runway_phase"]) >= 18000),
    "SEAT_DEAD_TIME": lambda r: num(r["runway_phase"]) < 4800,
    "PHASE_SPENT": lambda r: num(r["cov_phase"]) >= 80,
    "COV_SWEET_20_60": lambda r: 20 <= num(r["cov_phase"]) < 60,
    "LEVEL_VIRGIN": lambda r: r["min_tc_near"] in ("0", ""),
}


def _pv(k, n, p):
    try:
        from scipy.stats import binomtest
        return binomtest(k, n, p, alternative="two-sided").pvalue
    except Exception:                       # noqa: BLE001 — declared fallback
        if not n:
            return 1.0
        z = (k / n - p) / math.sqrt(p * (1 - p) / n)
        return math.erfc(abs(z) / math.sqrt(2))


# --------------------------------------------------------------- pairing -----
POS = ["phase_open_reset", "capacity_big", "level_at_price", "level_tested_held",
       "one_sided_flow", "flow_strong", "flow_flip", "fresh_extreme",
       "event_burst", "fuel_trapped", "poc_magnet", "tmz_burst", "expanding",
       "capacity_spent", "wide_spread", "stale_extreme", "NAMED_TRIAD"]


def build_pairing(rows):
    """D-086 full spectrum: takes, hand calls, conviction skips, skipped winners,
    and the FALSE sample (cued losers, clean and walled)."""
    B = [r for r in rows if r["block"] == "BLIND"]
    S = [r for r in rows if r["block"] == "STUDY"]
    sel, seen = [], set()

    def add(stratum, R):
        for r in R:
            if r["episode_id"] in seen:
                continue
            seen.add(r["episode_id"])
            sel.append((stratum, r))

    key = lambda r: (r["date8"], r["sec"])                # noqa: E731
    cued = lambda r: (r["_c"]["NAMED_TRIAD"]              # noqa: E731
                      or (r["_c"]["phase_open_reset"] and r["_c"]["capacity_big"]))
    add("BLIND_TAKE", sorted([r for r in B if r["call"] == "TAKE"], key=key))
    add("STUDY_TAKE", sorted([r for r in S if r["call"] == "TAKE"], key=key))
    add("STUDY_HAND_SKIP", sorted([r for r in S if r["src"] == "OVERRIDE"
                                   and r["call"] == "SKIP"], key=key))
    add("BLIND_HAND_SKIP", [r for r in B if r["src"] == "OVERRIDE"
                            and r["call"] == "SKIP"])
    add("BLIND_SKIP_CONVICTION",
        sorted([r for r in B if r["call"] == "SKIP" and float(r["p"]) >= 0.18],
               key=lambda r: (-float(r["p"]), -r["_u"])))
    add("BLIND_SKIPPED_WINNER",
        sorted([r for r in B if r["call"] == "SKIP" and r["_w"]],
               key=lambda r: -r["_u"])[:20])
    add("BLIND_SKIP_CUED_CLEAN_LOSER",
        sorted([r for r in B if r["call"] == "SKIP" and r["_u"] < 0
                and r["rep_walled"] == "0" and cued(r)],
               key=lambda r: r["_u"])[:15])
    add("BLIND_SKIP_CUED_WALLED_LOSER",
        sorted([r for r in B if r["call"] == "SKIP" and r["rep_walled"] == "1"
                and cued(r)], key=lambda r: (-float(r["p"]), r["_u"]))[:15])

    cols = ["stratum", "date8", "block", "episode_id", "asset", "side", "sec",
            "phase", "cls", "call", "src", "p", "reader_stated_reason",
            "cert_close_usd", "mae", "walled", "winner", "oracle_seat",
            "cues_present", "unspent_phase_usd", "cov_phase", "runway_phase",
            "near_d", "min_tc_near", "extreme_age", "f5m_sflow", "fph_sflow",
            "n_ev_60", "rv60", "rv1800", "trap_ab", "trap_bl", "spread_dec",
            "ladder_pos"]
    with open(PAIRING, "w") as w:
        w.write(HDR)
        w.write("\t".join(cols) + "\n")
        for st, r in sel:
            w.write("\t".join(str(x) for x in [
                st, r["date8"], r["block"], r["episode_id"], r["asset"],
                r["side"], r["sec"], r["phase"], r["cls"], r["call"], r["src"],
                r["p"], r["why"].replace("\t", " "), r["rep_close"],
                r["rep_mae"], r["rep_walled"], r["rep_win"], r["oracle_seat"],
                ",".join(k for k in POS if r["_c"][k]) or "-",
                r["unspent_phase_usd"], r["cov_phase"], r["runway_phase"],
                r["near_d"], r["min_tc_near"], r["extreme_age"],
                r["f5m_sflow"], r["fph_sflow"], r["n_ev_60"], r["rv60"],
                r["rv1800"], r["trap_ab"], r["trap_bl"], r["spread_dec"],
                r["ladder_pos"]]) + "\n")
    return len(sel)


# ---------------------------------------------------------------- census -----
def build_census(rows):
    days = sorted({r["date8"] for r in rows})
    scopes = [("BLIND", [r for r in rows if r["block"] == "BLIND"]),
              ("STUDY", [r for r in rows if r["block"] == "STUDY"]),
              ("ALL", rows)]
    with open(CENSUS, "w") as w:
        w.write(HDR)
        w.write("\t".join(
            ["scope", "cue", "n", "winners", "win_rate", "base_rate", "lift",
             "p_binom", "n_take", "take_wins", "take_prec", "take_usd",
             "take_mean_usd", "n_take_loss", "n_take_walled",
             "n_skipped_winners"] + ["lift_%s" % d for d in days]) + "\n")
        for scope, R in scopes:
            base = sum(x["_w"] for x in R) / len(R)
            for cue in CUE_ORDER + list(SCREENS):
                fn = SCREENS.get(cue) or (lambda r, c=cue: r["_c"][c])
                C = [r for r in R if fn(r)]
                n, k = len(C), sum(x["_w"] for x in C)
                CT = [r for r in C if r["call"] == "TAKE"]
                nt, wt = len(CT), sum(x["_w"] for x in CT)
                ut = sum(x["_u"] for x in CT)
                per = []
                for d in days:
                    D = [r for r in rows if r["date8"] == d]
                    b = sum(x["_w"] for x in D) / len(D)
                    L = [r for r in D if fn(r)]
                    per.append("%.3f" % ((sum(x["_w"] for x in L) / len(L)) / b)
                               if L else ".")
                w.write("\t".join(str(x) for x in [
                    scope, cue, n, k,
                    "%.5f" % (k / n) if n else ".", "%.5f" % base,
                    "%.3f" % ((k / n) / base) if n else ".",
                    "%.3e" % _pv(k, n, base) if n else ".",
                    nt, wt, "%.4f" % (wt / nt) if nt else ".", "%.2f" % ut,
                    "%.2f" % (ut / nt) if nt else ".", nt - wt,
                    sum(1 for x in CT if x["rep_walled"] == "1"),
                    sum(1 for x in C if x["call"] != "TAKE" and x["_w"])]
                    + per) + "\n")
    return CENSUS


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--outcomes", action="store_true")
    ap.add_argument("--pair", action="store_true")
    ap.add_argument("--census", action="store_true")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)
    MC.verify_spec()
    if a.all or a.outcomes:
        print("outcomes ->", build_outcomes())
    if a.all or a.pair or a.census:
        rows = master()
        print("master rows:", len(rows))
        if a.all or a.pair:
            print("pairing rows:", build_pairing(rows), "->", PAIRING)
        if a.all or a.census:
            print("census ->", build_census(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
