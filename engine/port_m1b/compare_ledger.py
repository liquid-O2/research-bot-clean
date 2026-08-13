#!/usr/bin/python3
"""PORT M1.B S2.2 — LEVEL-LEDGER differential (supporting evidence for P-M1s22).

The candidate differential (compare_gen.py) is the gate. This one localises:
it compares the C++ level ledger — the D-050 provenance record `qr_gen` builds
for the SEVEN KEPT families — against the Python ledger the S1-v3 oracle
consumed (`m1/levels_v4/{ASSET}/{YYYYMMDD}.npz`, D-053 bands + the D-054
mid-sanity mask + the CC-M1-6.1 OR_EXT family), restricted to those same seven.

Everything is compared as a MULTISET of rows keyed by the ledger's own content,
because the two implementations order levels within a session differently only
where the retired families used to sit; a level's identity is its name and its
price, never its row index.

usage: compare_ledger.py [ASSET ...] [--sessions N]
"""
import glob
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import binpack  # noqa: E402

M1 = "/workspace/artifacts/cache/port/m1"
PY_DIR = os.path.join(M1, "levels_v4")
CPP_DIR = os.path.join(M1, "gen_cpp", "roster_v3")
ASSETS = ("SI", "HG", "NKD")
KEPT = ("FVOL_LADDER", "FVOL_BAND", "NDAY", "PRIOR_DAY", "PHASE_HL", "VWAP",
        "OR_EXT")


def q(x):
    """Price comparison key: full float64 identity, NaN-safe."""
    return "nan" if not np.isfinite(x) else repr(float(x))


def py_rows(asset, date8):
    p = os.path.join(PY_DIR, asset, "%d.npz" % date8)
    if not os.path.exists(p):
        return None, None
    z = np.load(p, allow_pickle=False)
    fam = [str(x) for x in z["level_family"]]
    keep = [i for i, f in enumerate(fam) if f in KEPT]
    lv = []
    for i in keep:
        lv.append((fam[i], q(z["level_price"][i]), int(z["created_d8"][i]),
                   int(z["virgin"][i]), int(z["touch_count"][i]),
                   int(z["last_test_sec"][i]), int(z["last_test_outcome"][i]),
                   int(z["first_near_sec"][i])))
    tc = []
    t = z["touches"]
    for r in range(int(t.shape[0])):
        row = int(t[r][1])
        if row >= len(fam) or fam[row] not in KEPT:
            continue
        tc.append((fam[row], int(t[r][0]), q(t[r][2]), q(t[r][3]), int(t[r][4]),
                   int(t[r][5]), int(t[r][6]), int(t[r][7]), int(t[r][8]),
                   int(t[r][9]), int(t[r][10]), int(t[r][11])))
    z.close()
    return lv, tc


def cpp_all(asset):
    """{date8: (levels, touches)} from the QRGENL1 shards."""
    out = {}
    for stem in sorted(s[:-5] for s in
                       glob.glob(os.path.join(CPP_DIR, "%s_*_ledger.json" % asset))):
        _side, a = binpack.read(stem, "QRGENL1")
        for i in range(int(a["lv_date8"].size)):
            d = int(a["lv_date8"][i])
            out.setdefault(d, ([], []))[0].append(
                (KEPT[int(a["lv_family"][i])], q(a["lv_price"][i]),
                 int(a["lv_created_d8"][i]), int(a["lv_virgin"][i]),
                 int(a["lv_touch_count"][i]), int(a["lv_last_test_sec"][i]),
                 int(a["lv_last_test_outcome"][i]), int(a["lv_first_near_sec"][i])))
        for i in range(int(a["tc_date8"].size)):
            d = int(a["tc_date8"][i])
            out.setdefault(d, ([], []))[1].append(
                (KEPT[int(a["tc_family"][i])], int(a["tc_touch_sec"][i]),
                 q(a["tc_level_price"][i]), q(a["tc_mid"][i]),
                 int(a["tc_approach_side"][i]), int(a["tc_outcome"][i]),
                 int(a["tc_outcome_sec"][i]), int(a["tc_reject_sec"][i]),
                 int(a["tc_break_sec"][i]), int(a["tc_reclaim_sec"][i]),
                 int(a["tc_virgin"][i]), int(a["tc_touch_index"][i])))
    return out


def main():
    argv = [a for a in sys.argv[1:]]
    limit = None
    if "--sessions" in argv:
        i = argv.index("--sessions")
        limit = int(argv[i + 1])
        del argv[i:i + 2]
    assets = [a for a in argv if a in ASSETS] or list(ASSETS)
    ok = True
    for asset in assets:
        cpp = cpp_all(asset)
        dates = sorted(cpp)
        if limit:
            step = max(1, len(dates) // limit)
            dates = dates[::step][:limit]
        n_lv = n_tc = bad_lv = bad_tc = 0
        missing = 0
        for d in dates:
            plv, ptc = py_rows(asset, d)
            if plv is None:
                missing += 1
                continue
            clv, ctc = cpp[d]
            n_lv += len(plv)
            n_tc += len(ptc)
            if sorted(plv) != sorted(clv):
                bad_lv += 1
            if sorted(ptc) != sorted(ctc):
                bad_tc += 1
        verdict = "PASS" if (bad_lv == 0 and bad_tc == 0 and missing == 0) else "FAIL"
        ok = ok and (verdict == "PASS")
        print("%-4s sessions=%d levels=%d touches=%d "
              "sessions_with_level_mismatch=%d sessions_with_touch_mismatch=%d "
              "missing_python_ledger=%d  %s"
              % (asset, len(dates), n_lv, n_tc, bad_lv, bad_tc, missing, verdict))
    print("LEDGER DIFFERENTIAL %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
