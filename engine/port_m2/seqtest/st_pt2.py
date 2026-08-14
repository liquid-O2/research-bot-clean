#!/usr/bin/python3
"""PORT M2 FIXPASS2 — the RE-PRETRAINING GRID on the repaired vocabulary.

F1 (R1/R6) + F4 (R3) in one loop, three trunks, one 3-hour ceiling:

  PRE_V2_shared_NEXT            next-event only            (the winning arm's
                                                            objective, re-run on
                                                            the fixed vocab)
  PRE_V2_shared_MULTI_CPC0.6    + h60/h300 + CPC REWEIGHTED x3
  PRE_V2_shared_MULTI_CPC0      + h60/h300, CPC DROPPED

Everything else is the first pass verbatim: PRE-A causal corpus `d8 <
20240101`, asset-balanced batches, single pass, the held-out-DAY val gate
(VAL_EVERY / VAL_PATIENCE / best-val restore), the recomputed unigram and
bigram floors, the same seed.  The two MULTI arms share ONE loaded corpus (the
aux stream is ~51 GB) so the ceiling is spent on training, not on I/O.

Run:  st_pt2.py --grid --budget 2200
"""
import argparse
import json
import os
import time

import st_common as SC
import st_pretrain as P


def grid(budget=2200.0, arms=("next", "cpc3", "cpc0")):
    P.use_tokenizer("v2")
    t0 = time.time()
    out = {}
    if "next" in arms:
        P.set_cpc_weight(0.0)
        out["next"] = P.pretrain("A", "shared", budget_sec=budget, epochs=1,
                                 multi=False)
        SC.hb("GRID: NEXT done (%.0fs elapsed)" % (time.time() - t0))
    multi_arms = [a for a in arms if a in ("cpc3", "cpc0")]
    if multi_arms:
        pre = P._corpus("A", "shared", True)
        for a in multi_arms:
            P.set_cpc_weight(0.60 if a == "cpc3" else 0.0)
            out[a] = P.pretrain("A", "shared", budget_sec=budget, epochs=1,
                                multi=True, preloaded=pre)
            SC.hb("GRID: MULTI %s done (%.0fs elapsed)" % (a, time.time() - t0))
        del pre
    with open(os.path.join(SC.CACHE_ROOT, "pretrain_v2_grid.json"), "w") as fh:
        json.dump({k: {kk: vv for kk, vv in v.items() if kk != "curve"}
                   for k, v in out.items()}, fh, indent=1, default=str)
    SC.hb("PRETRAIN GRID v2 complete in %.0fs" % (time.time() - t0))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--budget", type=float, default=2200.0)
    ap.add_argument("--arms", default="next,cpc3,cpc0")
    a = ap.parse_args()
    if a.grid:
        grid(a.budget, tuple(x for x in a.arms.split(",") if x))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
