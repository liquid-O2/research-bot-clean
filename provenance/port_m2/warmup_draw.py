#!/usr/bin/python3
"""P-M2c WARM-UP DRAW (deterministic).

Rule (from the round brief):
  * per asset: the STUDY session with the MEDIAN candidate count
    (SESSIONS_STUDY.tsv, block=STUDY, era=E1; 79 sessions/asset -> odd ->
    the 40th value of the ascending n_candidates order; ties broken by
    date8 ascending so the pick is total);
  * from that session's index rows (chronological by dec_sec) take the
    candidates at time-ranks 10/30/50/70/90% using the NEAREST-RANK
    definition  idx0 = ceil(p*n) - 1  (0-based);
  * plus the chronologically FIRST STUDY case per asset in each of the class
    sub-indexes RECLAIM, NEWS-WINDOW, OPEN-DYNAMICS (fallback order
    SHOCK-RESOLUTION then LEVEL-FIRST-TEST if a class is absent for the asset).
  * ablation set = the 30% and 70% cases (6).
Output: WARMUP_DRAW.tsv (chronological), the round's canonical case list.
"""
import math
import os

ERA = "/workspace/artifacts/cache/port/m2/era/E1"
OUT = "/workspace/provenance/port_m2/WARMUP_DRAW.tsv"
ASSETS = ("SI", "HG", "NKD")
RANKS = (10, 30, 50, 70, 90)
CLASS_ORDER = ("RECLAIM", "NEWS-WINDOW", "OPEN-DYNAMICS")
FALLBACK = ("SHOCK-RESOLUTION", "LEVEL-FIRST-TEST")
CLASS_FILE = {"RECLAIM": "INDEX_STUDY_CLASS_RECLAIM.tsv",
              "NEWS-WINDOW": "INDEX_STUDY_CLASS_NEWS_WINDOW.tsv",
              "OPEN-DYNAMICS": "INDEX_STUDY_CLASS_OPEN_DYNAMICS.tsv",
              "SHOCK-RESOLUTION": "INDEX_STUDY_CLASS_SHOCK_RESOLUTION.tsv",
              "LEVEL-FIRST-TEST": "INDEX_STUDY_CLASS_LEVEL_FIRST_TEST.tsv"}


def read_tsv(path):
    rows, cols = [], None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            rows.append(dict(zip(cols, f)))
    return rows


def main():
    sess = [r for r in read_tsv(os.path.join(ERA, "SESSIONS_STUDY.tsv"))
            if r["era"] == "E1" and r["block"] == "STUDY"]
    picks = []
    for asset in ASSETS:
        s = sorted([r for r in sess if r["asset"] == asset],
                   key=lambda r: (int(r["n_candidates"]), int(r["date8"])))
        med = s[(len(s) - 1) // 2] if len(s) % 2 else s[len(s) // 2 - 1]
        d8 = med["date8"]
        idx = [r for r in read_tsv(os.path.join(ERA, "INDEX_%s.tsv" % asset))
               if r["block"] == "STUDY" and r["date8"] == d8]
        idx.sort(key=lambda r: (int(r["dec_sec"]), r["cid"]))
        n = len(idx)
        assert n == int(med["n_candidates"]), (n, med["n_candidates"])
        for p in RANKS:
            i = min(n - 1, int(math.ceil(p / 100.0 * n)) - 1)
            r = dict(idx[i])
            r["_slot"] = "TR%02d" % p
            r["_sess_n"] = n
            r["_ablation"] = "1" if p in (30, 70) else "0"
            picks.append(r)
        for cls in CLASS_ORDER:
            got = None
            for cand_cls in (cls,) + FALLBACK:
                rows = [x for x in read_tsv(os.path.join(ERA, CLASS_FILE[cand_cls]))
                        if x["asset"] == asset and x["block"] == "STUDY"]
                rows.sort(key=lambda x: (int(x["date8"]), int(x["dec_sec"]),
                                         x["cid"]))
                rows = [x for x in rows
                        if x["cid"] not in {q["cid"] for q in picks}]
                if rows:
                    got = dict(rows[0])
                    got["_slot"] = "FIRST_%s" % cls
                    if cand_cls != cls:
                        got["_slot"] += "(sub=%s)" % cand_cls
                    break
            assert got is not None, (asset, cls)
            got["_sess_n"] = ""
            got["_ablation"] = "0"
            picks.append(got)

    picks.sort(key=lambda r: (int(r["date8"]), int(r["dec_sec"]), r["cid"]))
    cols = ["cid", "asset", "date8", "dec_sec", "side", "candidate_class",
            "driver_family", "phase_dec", "entry_mid", "spread_at_decision",
            "_slot", "_sess_n", "_ablation"]
    with open(OUT, "w") as fh:
        fh.write("# P-M2c warm-up draw — deterministic; see warmup_draw.py\n")
        fh.write("\t".join(cols) + "\n")
        for r in picks:
            fh.write("\t".join(str(r.get(c, "")) for c in cols) + "\n")
    print("n=%d  unique=%d" % (len(picks), len({r["cid"] for r in picks})))
    for r in picks:
        print("%-26s %-4s %-22s %-10s abl=%s %s" %
              (r["cid"], r["asset"], r["candidate_class"], r["phase_dec"],
               r["_ablation"], r["_slot"]))


if __name__ == "__main__":
    main()
