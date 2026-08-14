#!/usr/bin/python3
"""PORT M2 FIXPASS2 — the ablation-grid driver (GPU stages 3-5).

The grid is INSIDE the pass, per the D-001 selection rule: one comprehensive
evaluation -> one consolidated fix pass applying every evidence-indicated
repair together, each behind a toggle, with the component attribution run in
the same loop -> one re-evaluation.

Stage 3 (F3 + F6)  the deploy-matched neural rankers: day groups, +/- wall-pair
                   hard negatives (B3), +/- day memory (B1), context-only and
                   fused-on-the-repaired-trunk.
Stage 4 (F2)       the partial fine-tunes that retire the frozen probe.  The
                   trunk is chosen by the FROZEN-PROBE capture of stage 2 —
                   i.e. by the ablation, not by hand.
Stage 5            the shuffled-label control at the winning new configuration.

Run:  st_fix_drive.py --stage rank
      st_fix_drive.py --stage ft --steps 1500
"""
import argparse
import glob
import json
import os

import numpy as np

import st_common as SC
import st_run as R

V2_TRUNKS = ("PRE_V2_shared_NEXT", "PRE_V2_shared_MULTI_CPC0.6",
             "PRE_V2_shared_MULTI_CPC0")


def best_trunk(default="PRE_V2_shared_NEXT"):
    """The V2 trunk with the highest FROZEN-PROBE pooled capture — the
    ablation's own answer to F4 (CPC x3 vs dropped) and to F1's objective."""
    best, bt = -np.inf, default
    for t in V2_TRUNKS:
        p = os.path.join(R.RES_DIR, "PROBE2_%s_FUSED.json" % t)
        if not os.path.exists(p):
            continue
        with open(p) as fh:
            o = json.load(fh)
        c = (o.get("pooled") or {}).get("capture_oracle")
        if c is not None and c > best:
            best, bt = float(c), t
    SC.hb("ablation picks trunk %s (frozen-probe capture %.4f)" % (bt, best))
    return bt, best


def stage_rank(trunk=None):
    import st_rank2 as RK2
    t, _c = best_trunk()
    trunk = trunk or t
    cells = [
        # (trunk, mode, group, hardneg, daymem, tag)
        ("NONE", "ctx", "day", 0.0, False, "RANK2_DAY_CTX"),
        ("NONE", "ctx", "day", 1.0, False, "RANK2_DAY_CTX_HN1"),
        ("NONE", "ctx", "day", 0.0, True, "RANK2_DAY_CTX_MEM"),
        ("NONE", "ctx", "day", 1.0, True, "RANK2_DAY_CTX_HN1_MEM"),
        ("NONE", "ctx", "class", 0.0, False, "RANK2_CLASS_CTX"),
        (trunk, "fused", "day", 0.0, False, "RANK2_DAY_V2_FUSED"),
        (trunk, "fused", "day", 1.0, True, "RANK2_DAY_V2_FUSED_HN1_MEM"),
    ]
    for tr, mode, grp, hn, mem, tag in cells:
        if os.path.exists(os.path.join(R.RES_DIR, "%s.json" % tag)):
            SC.hb("skip %s (already committed)" % tag)
            continue
        RK2.run(tr, mode=mode, group=grp, hardneg=hn, daymem=mem, tag=tag)


def stage_ft(steps=1500, trunk=None):
    import st_ft2 as F2
    t, _c = best_trunk()
    trunk = trunk or t
    cells = [
        # (trunk, unfreeze, lora, pool, daymem, scratch, tag)
        # ORDER MATTERS: the headline arm and its RANDOM-TRUNK control first,
        # so a wall-clock stop can never leave a treatment without its control.
        (trunk, 4, 0, "attn", False, False, "FT2_TOP4_ATTN"),
        ("RANDOM_V2", 4, 0, "attn", False, True, "FT2_RANDOM_TOP4_ATTN"),
        (trunk, 4, 0, "attn", True, False, "FT2_TOP4_ATTN_MEM"),
        (trunk, 0, 16, "attn", False, False, "FT2_LORA16_ATTN"),
    ]
    for tr, unf, lora, pool, mem, scr, tag in cells:
        if os.path.exists(os.path.join(R.RES_DIR, "%s.json" % tag)):
            SC.hb("skip %s (already committed)" % tag)
            continue
        F2.run(tr, mode="fused", pool=pool, unfreeze=unf, lora=lora,
               daymem=mem, scratch=scr, steps=steps, tag=tag, tokver="v2")


def stage_control(steps=1500):
    """The two red-first controls at the pass's own winning configurations."""
    import st_rank2 as RK2
    RK2.run("NONE", mode="ctx", group="day", hardneg=0.0, daymem=True,
            shuffle=True, tag="RANK2_DAY_CTX_MEM_SHUFFLED")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True,
                    choices=("rank", "ft", "control", "pick"))
    ap.add_argument("--steps", type=int, default=1500)
    ap.add_argument("--trunk", default=None)
    a = ap.parse_args()
    if a.stage == "pick":
        print(json.dumps(dict(zip(("trunk", "capture"), best_trunk()))))
    elif a.stage == "rank":
        stage_rank(a.trunk)
    elif a.stage == "ft":
        stage_ft(a.steps, a.trunk)
    elif a.stage == "control":
        stage_control(a.steps)


if __name__ == "__main__":
    main()
