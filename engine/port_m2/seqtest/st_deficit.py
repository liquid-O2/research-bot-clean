#!/usr/bin/python3
"""PORT M2 SEQTEST — push any score this lane produces through the standing
DEFICIT LEDGER, one command per score.

The redirect of 2026-08-16 makes `SEL_WRONG_MEMBER` the number to move, and the
ledger is the only instrument that measures it.  This writes the lane's
out-of-sample score column as the ledger's own score-table format (`cid`,
`score`) and calls `deficit_ledger.py --score-table`, so the decomposition comes
out of the committed code path and not a second copy of the arithmetic.

Run:
    st_deficit.py --tag RANK_PRE_A_shared_FUSED --name SEQ_RANK
    st_deficit.py --all
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np

import st_common as SC
import st_run as R

LEDGER = "/workspace/engine/port_m2/deficit_ledger.py"
TABLE_DIR = os.path.join(SC.CACHE_ROOT, "score_tables")
OUT_DIR = os.path.join(SC.CACHE_ROOT, "deficit")

# The lane's schedule, restated for the ledger in ITS vocabulary.  Identical to
# what `st_run.score_arm` applies: top-3 per asset-day, D-077 veto on, the frozen
# MATRIX_CERT contract (phase-close + the $900 wall).  EXITS ARE PARKED — the
# contract is not a variable in this pass.
# CORRECTED 2026-08-16: the first pass forced unit=session/topn=3, which
# forfeits 63-65% of its own takes (one position per asset-session).  The
# harness's own inner-selected policy is the (asset, PHASE) CELL at N=1, which
# forfeits 0.1% and pays 2.6x more on the identical score columns.  That is the
# policy the ledger's own DEFAULT_POLICY already carried; forcing session/3 was
# this lane's defect and it is repaired here.
POLICY = {"unit": "cell", "topn": 1, "deployable": True,
          "contract": "MATRIX_CERT", "scope": "scored"}


def write_table(tag, use="composed"):
    os.makedirs(TABLE_DIR, exist_ok=True)
    import m3_walk as W
    D, _p = W.load_matrix()
    z = np.load(os.path.join(R.SCORE_DIR, "%s.npz" % tag))
    champ, win = z["champ"], z["win"]
    score = np.full(D["d8"].size, np.nan)
    for era in SC.TEST_ERAS:
        ev = np.nonzero((D["era_idx"] == SC.ERA_IDX[era])
                        & np.isfinite(champ))[0]
        if ev.size == 0:
            continue
        if use == "composed" and not np.array_equal(champ[ev], win[ev]):
            score[ev] = R.composed(D, champ, win, ev)[ev]
        else:
            score[ev] = champ[ev]
    ok = np.nonzero(np.isfinite(score))[0]
    p = os.path.join(TABLE_DIR, "%s.tsv" % tag)
    with open(p, "w") as fh:
        fh.write("cid\tscore\n")
        for i in ok.tolist():
            fh.write("%s\t%.8g\n" % (D["cid"][i], score[i]))
    SC.hb("score table %s: %d rows -> %s" % (tag, ok.size, p))
    return p


def run(tag, name=None, use="composed"):
    p = write_table(tag, use=use)
    os.makedirs(OUT_DIR, exist_ok=True)
    pol = os.path.join(TABLE_DIR, "%s.policy.json" % tag)
    with open(pol, "w") as fh:
        json.dump(dict(POLICY, name=name or tag), fh, indent=1)
    out = os.path.join(OUT_DIR, tag)
    cmd = [sys.executable, LEDGER, "--score-table", p, "--policy", pol,
           "--name", name or tag, "--out-dir", out,
           "--out-prov", os.path.join(SC.OUT_DIR,
                                      "SEQTEST_DEFICIT_%s" % (name or tag))]
    SC.hb("deficit ledger: %s" % " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    sys.stderr.write(r.stderr[-4000:])
    sys.stdout.write(r.stdout[-4000:])
    if r.returncode != 0:
        raise SC.SeqTestRefusal("deficit_ledger refused (rc=%d)" % r.returncode)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default=None)
    ap.add_argument("--name", default=None)
    ap.add_argument("--use", default="composed")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if a.all:
        for f in sorted(os.listdir(R.SCORE_DIR)):
            if f.endswith(".npz") and not f.startswith("SHUFFLED"):
                run(f[:-4], name=f[:-4], use=a.use)
    elif a.tag:
        run(a.tag, name=a.name, use=a.use)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
