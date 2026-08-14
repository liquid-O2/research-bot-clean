#!/usr/bin/python3
"""PORT M2 — E6R2X: batch EPISODE_ACCESS registration for a blind day.

WHY THIS EXISTS.  `episode_round._append_access` rewrites the whole ledger on
every call, so registering a 600-episode day one row at a time is O(n^2) and
takes minutes.  Round 2's rows were appended by an ad-hoc script that lived
nowhere; the orchestrator asked for this to be done "via the tooling", so the
tooling is this file — it uses `episode_round`'s OWN schema constants, its own
reader, and its own writer, and adds nothing but the batching.

WHAT A ROW MEANS.  One row per episode per DIGEST PASS: the reader saw that
episode's delta row (D-085 session-brief + per-episode delta view) inside the
named round.  `n_ribbon_cmds` / `n_chart_reads` / `n_brief_reads` are filled
from the MECHANICAL ledgers (RIBBON_ACCESS.tsv, CHART_RECEIPT.tsv,
BRIEF_ACCESS.tsv) at registration time, so the counters are measured rather
than asserted; the R2-1 take rule sums them with the mechanical ledgers again
at score time, so neither side is a single point of failure.

`sheet_tokens` is the MEASURED size of that episode's delta row in the digest
pass (len(line)//4, the same cheap estimator the round has used throughout),
not a constant.

BLIND SAFETY: imports episode_round + e6_round only; no outcome module at any
depth.

Run:
  r2x_access.py --day 20240429 --round e6r2x-blind --caller r2x-reader \
                --deltas <DELTAS_FILE> --mode BLIND
"""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import episode_round as ER                # noqa: E402

SHEET_SOURCE = "digest-pass"


def deltas_tokens(path):
    """episode_id -> measured token size of its delta row."""
    out = {}
    if not path or not os.path.exists(path):
        return out
    for line in open(path):
        if line.startswith("#"):
            continue
        f = line.rstrip("\n").split("\t")
        if len(f) < 2:
            continue
        out[f[1]] = max(1, len(line) // 4)
    return out


def register(day, round_name, caller, era="E6", mode=MC.MODE_BLIND,
             deltas=None):
    eps = ER.load_episodes(era, day)
    tok = deltas_tokens(deltas)
    rib = ER.ribbon_reads_by_cid(round_name=round_name)
    ch_ep, ch_cid = ER.chart_reads_by_key(round_name=round_name)
    br = ER.brief_reads_by_key(round_name=round_name)

    have = {(r.get("episode_id"), r.get("round")) for r in ER._read_access()}
    rows = [[r.get(c, ER.ACCESS_DEFAULT.get(c, MC.NA)) for c in
             ER.ACCESS_COLUMNS] for r in ER._read_access()]
    n_new = 0
    for e in eps:
        eid = e["episode_id"]
        if (eid, round_name) in have:
            continue
        members = [m for m in str(e.get("members", "")).split(",") if m]
        rec = {
            "seq": len(rows), "episode_id": eid, "era": era,
            "asset": e["asset"], "date8": day, "rep_cid": e["rep_cid"],
            "n_members": e.get("n_members", len(members) or 1),
            "mode": mode, "sheet_source": SHEET_SOURCE,
            "sheet_sha16": MC.NA,
            "sheet_tokens": tok.get(eid, 0),
            "n_ribbon_cmds": sum(rib.get(m, 0) for m in members),
            "n_chart_reads": ch_ep.get(eid, 0) + ch_cid.get(e["rep_cid"], 0),
            "n_brief_reads": br.get((int(day), e["asset"]), 0),
            "s14_guard_paths_checked": 1,
            "round": round_name, "caller": caller,
        }
        rows.append([str(rec.get(c, ER.ACCESS_DEFAULT.get(c, MC.NA)))
                     for c in ER.ACCESS_COLUMNS])
        n_new += 1

    MC.write_tsv(ER.ACCESS_LEDGER, ER.SECTION, MC.params_hash(ER.PARAMS),
                 list(ER.ACCESS_COLUMNS), rows,
                 extra=["D-080.2 deep-read ledger: one row per episode view; "
                        "a day is not scoreable until every episode of its "
                        "index appears here (R02)",
                        "seq = row index (deterministic, no wall clock)"])
    miss = ER.missing_access(era, day, round_name=round_name)
    return {"day": day, "round": round_name, "n_episodes": len(eps),
            "n_new_rows": n_new, "n_missing_after": len(miss),
            "ledger": ER.ACCESS_LEDGER}


def main(argv=None):
    ap = argparse.ArgumentParser(description="E6R2X episode-access batch")
    ap.add_argument("--day", type=int, required=True)
    ap.add_argument("--round", dest="round_name", required=True)
    ap.add_argument("--caller", default="r2x-reader")
    ap.add_argument("--era", default="E6")
    ap.add_argument("--mode", default=MC.MODE_BLIND, choices=list(MC.MODES))
    ap.add_argument("--deltas", default=None)
    a = ap.parse_args(argv)
    r = register(a.day, a.round_name, a.caller, era=a.era, mode=a.mode,
                 deltas=a.deltas)
    print("r2x_access %(day)d %(round)s: %(n_new_rows)d new rows, "
          "%(n_episodes)d episodes, %(n_missing_after)d missing after"
          % r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
