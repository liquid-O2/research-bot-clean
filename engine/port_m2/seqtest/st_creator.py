#!/usr/bin/python3
"""PORT M2 FIXPASS2 — F5(a): the 26 CENSUS-SURVIVING CREATOR DETECTORS as
matrix-ready feature columns, over the WHOLE era ladder.

`provenance/port_m2/CREATOR_MECHANICS_CENSUS.md` §1.1 (21 entry survivors) and
§1.2 (5 veto survivors) = **26** detectors that cleared Holm, survived the
within-session destruction null, and carried a day-clustered CI on one side of
1.0.  §6.1 declares them matrix-ready feature candidates ("winner concentrators,
and that is the only claim attached to them").

The committed census cache `creator/detect.npz` covers E2..E6 only
(`creator_census.ERA_LO/ERA_HI` = 20220101..20240630).  The walk-forward ladder
tests E3..E8, so the columns must exist to 20250630.  This module re-runs the
COMMITTED detector bank (`creator_census._worker`, imported, never re-typed —
D-006) over the full E2..E8 population and writes a SEPARATE cache; the census's
own artefact is never touched.

Run:
    st_creator.py --detect --workers 24
    st_creator.py --check
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in ("/workspace/engine/port_m3", "/workspace/engine/port_m2",
           "/workspace/engine/port_m1b", "/workspace/engine/port_m1",
           "/workspace/engine/port_m0", "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import st_common as SC                       # noqa: E402
import common as C                           # noqa: E402
import m2_common as MC                       # noqa: E402
import creator_census as CC                  # noqa: E402

# THE FULL LADDER: E2 (the first training era) .. E8 (the GATE echo).
ERA_LO, ERA_HI = 20220101, 20250630

CACHE = os.path.join(SC.CACHE_ROOT, "creator")
DETECT = os.path.join(CACHE, "detect_e2e8.npz")

# ---- the 26, verbatim from the census sections -----------------------------
SURV_ENTRY = ("PASSIVE_MOVE", "TAPE_SPIKE", "ONX_UNTOUCHED_AHEAD", "OFM",
              "ABSORPTION", "AGG_OPP_SIDE_60", "TWO_STAGE",
              "EXTREME_ABSORPTION", "REPEATED_FAIL_RECLAIM", "AGG_PRINT_60",
              "OFM_FAILURE_ENTRY", "AGG_WITH_SIDE_60", "REFILL_CLOCK",
              "SQUEEZE", "RETEST_NOT_BREAK", "IB_BROKEN_WITH", "BOTH_ABSORBED",
              "SQUEEZE_CATALYST_NEAR", "TOUCH_GE3", "BODY_REWARDED_WITH",
              "LOSING_STEAM")
SURV_VETO = ("TAPE_DEAD", "DIV_BOX_350", "REFILL_AREA_HELD",
             "WICK_ABSORBED_OPP", "MICROBALANCE_BREAK")
SURVIVORS = SURV_ENTRY + SURV_VETO           # 21 + 5 = 26


def load_population(lo=ERA_LO, hi=ERA_HI):
    """`creator_census.load_population`, with the era window widened to the
    whole ladder.  The holdout boundary (20250701) is above `hi` by
    construction and is asserted."""
    if hi >= MC.HOLDOUT_FROM_D8:
        raise SC.SeqTestRefusal("HOLDOUT LEAK: hi=%d >= %d"
                                % (hi, MC.HOLDOUT_FROM_D8))
    old = (CC.ERA_LO, CC.ERA_HI)
    CC.ERA_LO, CC.ERA_HI = lo, hi
    try:
        return CC.load_population()
    finally:
        CC.ERA_LO, CC.ERA_HI = old


def run_detect(workers=24, lo=ERA_LO, hi=ERA_HI):
    os.makedirs(CACHE, exist_ok=True)
    Pn = load_population(lo, hi)
    assets = [C.ASSET_ORDER[i] for i in Pn["asset_idx"]]
    key = np.array(["%s|%08d" % (a, d)
                    for a, d in zip(assets, Pn["d8"].tolist())])
    uk, inv = np.unique(key, return_inverse=True)
    idx_by_key = {k: np.nonzero(inv == gi)[0] for gi, k in enumerate(uk.tolist())}
    jobs = []
    for k in uk.tolist():
        a, d = k.split("|")
        sel = idx_by_key[k]
        jobs.append((a, int(d), Pn["dec_sec"][sel].astype(np.int64),
                     Pn["side"][sel].astype(np.int64), Pn["atr_usd"][sel]))
    SC.hb("creator-detect E2..E8: %d session-assets, %d candidates, %d workers"
          % (len(jobs), Pn["d8"].size, workers))
    nd = CC.NDET_SESSION
    Dall = np.zeros((Pn["d8"].size, nd), dtype=np.uint8)
    Dis = np.zeros((Pn["d8"].size, nd), dtype=np.uint8)
    EM = np.full(Pn["d8"].size, np.nan)
    reps, errs = [], []
    t0 = time.time()
    done = 0
    with mp.Pool(int(workers)) as pool:
        for asset, d8, D, Dd, em, rep in pool.imap_unordered(CC._worker, jobs,
                                                             chunksize=2):
            done += 1
            k = "%s|%08d" % (asset, d8)
            if D is None:
                errs.append((k, rep.get("error")))
            else:
                ix = idx_by_key[k]
                Dall[ix] = D
                Dis[ix] = Dd
                EM[ix] = em
                reps.append(rep)
            if done % 200 == 0:
                el = time.time() - t0
                SC.hb("detect %d/%d %.1f/s eta %.0fs"
                      % (done, len(jobs), done / max(el, 1e-9),
                         (len(jobs) - done) / max(done / max(el, 1e-9), 1e-9)))
    np.savez_compressed(DETECT, cid=Pn["cid"], D=Dall, D_disp=Dis,
                        entry_mid=EM, d8=Pn["d8"], dec_sec=Pn["dec_sec"],
                        det_names=np.array(CC.DET_NAMES[:nd]))
    with open(os.path.join(CACHE, "detect_e2e8.json"), "w") as fh:
        json.dump({"n_rows": int(Pn["d8"].size), "n_sessions": len(jobs),
                   "era_lo": lo, "era_hi": hi, "n_errors": len(errs),
                   "errors": errs[:50], "secs": round(time.time() - t0, 1),
                   "params": CC.P, "survivors": list(SURVIVORS),
                   "source": "creator_census._worker (imported, D-006)"},
                  fh, indent=1, default=str)
    SC.hb("creator-detect E2..E8 done in %.0fs, %d errors"
          % (time.time() - t0, len(errs)))
    return DETECT


# ------------------------------------------------------------- the columns --
_CM = {}


def creator_columns(D, names=SURVIVORS):
    """[n_matrix_rows, 26] float32 detector flags joined BY CID, plus the
    coverage mask.  Rows outside the detector population are typed-missing
    (NaN), exactly like any other matrix column, so the GBT's own missing
    handling applies and nothing is silently imputed to zero."""
    if _CM.get("names") == tuple(names):
        return _CM["A"], _CM["cols"], _CM["cov"]
    if not os.path.exists(DETECT):
        raise SC.SeqTestRefusal("creator detect cache missing: %s (run "
                                "st_creator.py --detect)" % DETECT)
    z = np.load(DETECT, allow_pickle=False)
    cid = [str(x) for x in z["cid"].tolist()]
    det = [str(x) for x in z["det_names"].tolist()]
    M = z["D"]
    em = z["entry_mid"]
    z.close()
    ix = {c: i for i, c in enumerate(cid)}
    row_of = np.full(D["d8"].size, -1, dtype=np.int64)
    for k, c in enumerate(D["cid"].tolist()):
        j = ix.get(str(c))
        if j is not None:
            row_of[k] = j
    cov = row_of >= 0
    keep = [n for n in names if n in det]
    A = np.full((D["d8"].size, len(keep)), np.nan, dtype=np.float32)
    for j, n in enumerate(keep):
        A[cov, j] = M[row_of[cov], det.index(n)].astype(np.float32)
    mid = np.full(D["d8"].size, np.nan)
    mid[cov] = em[row_of[cov]]
    _CM.update({"names": tuple(names), "A": A,
                "cols": ["cre_" + n for n in keep], "cov": cov,
                "entry_mid": mid})
    SC.hb("creator columns: %d detectors, %d/%d matrix rows covered"
          % (len(keep), int(cov.sum()), cov.size))
    return A, _CM["cols"], cov


def entry_mid(D):
    creator_columns(D)
    return _CM["entry_mid"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detect", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--workers", type=int, default=24)
    a = ap.parse_args()
    if a.detect:
        run_detect(a.workers)
    if a.check:
        import m3_walk as W
        D, _p = W.load_matrix()
        A, cols, cov = creator_columns(D)
        print(json.dumps({"cols": cols, "coverage": float(cov.mean()),
                          "rates": {c: round(float(np.nanmean(A[:, i])), 5)
                                    for i, c in enumerate(cols)}}, indent=1))
    if not (a.detect or a.check):
        ap.print_help()


if __name__ == "__main__":
    main()
