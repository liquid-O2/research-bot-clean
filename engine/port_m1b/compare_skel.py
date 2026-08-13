#!/usr/bin/python3
"""PORT M1.B S3 PARITY GATE — byte-exact C++ engine vs the brute-force oracle.

Selects stratified sessions per asset (short sessions, roll days, gap opens and
plain days across the eras), recomputes EVERY stored field with
oracle_skel.py's direct scans, and asserts BYTE equality — float fields compared
on their IEEE-754 bits, so a NaN against a zero, a -0.0 against a +0.0 and a
1-ulp drift are all failures.  There is no tolerance parameter.

usage: compare_skel.py [--per-asset N] [--workers N] [ASSET ...]
"""
import argparse
import datetime as dt
import json
import multiprocessing as mp
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import binpack        # noqa: E402
import oracle_skel as O  # noqa: E402

M0_ROOT = "/workspace/artifacts/cache/port/m0"
SKEL = "/workspace/artifacts/cache/port/m1/skel"
ASSETS = ("SI", "HG", "NKD")

SCALARS = [("anchor_sec", np.int32), ("observed_secs", np.int32),
           ("entry_mid", np.float64), ("f_h30", np.float64),
           ("f_h60", np.float64), ("f_h120", np.float64),
           ("f_phase_close", np.float64), ("f_sess_close", np.float64),
           ("phase_close_sec", np.int32), ("sess_close_sec", np.int32),
           ("mfe_usd", np.float64), ("mfe_argmax_sec", np.int32),
           ("mae_before_argmax_usd", np.float64),
           ("mae_unwalled_usd", np.float64), ("f_terminal_usd", np.float64),
           ("giveback_post_peak_usd", np.float64),
           ("time_to_peak_secs", np.int32), ("time_underwater_secs", np.int32),
           ("uw_share", np.float64), ("mono_steps", np.int32),
           ("monotonicity", np.float64)]


# ------------------------------------------------------------ selection ----
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


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def stratify(asset, have_dates, per_asset):
    """Short sessions, roll days, gap opens, and plain days across the eras."""
    idx = {int(r["trade_date"].replace("-", "")): r
           for r in read_tsv(os.path.join(M0_ROOT, "sessions_index_%s.tsv" % asset))}
    bars = read_tsv(os.path.join(M0_ROOT, "bars_%s.tsv" % asset))
    bars = [b for b in bars if int(b["trade_date"].replace("-", "")) in have_dates]
    bars.sort(key=lambda b: b["trade_date"])
    gap, short, roll = {}, {}, {}
    prev_c = None
    for b in bars:
        d8 = int(b["trade_date"].replace("-", ""))
        atr = _f(b.get("ATR14_prev_usd"))
        h, low, c = _f(b["H"]), _f(b["L"]), _f(b["C"])
        if prev_c is not None and np.isfinite(atr) and atr > 0:
            # A true gap: the whole session range sits away from the prior close.
            g = max(0.0, low - prev_c, prev_c - h)
            gap[d8] = g / (atr / 1.0)
        prev_c = c
        short[d8] = int(idx[d8]["n_valid_seconds"]) if d8 in idx else 10 ** 9
        roll[d8] = (idx.get(d8, {}).get("roll_window") == "1")
    picks, seen = [], set()

    def take(cands, tag, k):
        for d8 in cands:
            if len(picks) >= per_asset or k <= 0:
                return
            if d8 in seen:
                continue
            seen.add(d8)
            picks.append((d8, tag))
            k -= 1

    take(sorted(short, key=lambda d: short[d]), "SHORT_SESSION", 2)
    take([d for d in sorted(roll) if roll[d]], "ROLL_DAY", 2)
    take(sorted(gap, key=lambda d: -gap[d]), "GAP_OPEN", 2)
    # plain days, one per era-year, deterministic (the median date of the year)
    by_year = {}
    for d8 in sorted(have_dates):
        by_year.setdefault(d8 // 10000, []).append(d8)
    for y in sorted(by_year):
        take([by_year[y][len(by_year[y]) // 2]], "PLAIN_%d" % y, 1)
    return picks[:per_asset]


# ------------------------------------------------------------ comparison ---
def compare_session(job):
    asset, d8, tag = job
    stem = os.path.join(SKEL, "candidates", asset)
    _, C = binpack.read(stem, "QRCAND1")
    m = C["date8"] == d8
    cid, dec, side, atr = C["cand_id"][m], C["dec_sec"][m], C["side"][m], C["atr14_usd"][m]

    shard = os.path.join(SKEL, "shards", "%s_%06d" % (asset, d8 // 100))
    _, S = binpack.read(shard, "QRSKEL1")
    sm = S["date8"] == d8
    rows = np.nonzero(sm)[0]
    bad = []
    if not np.array_equal(S["cand_id"][rows], cid):
        # refused candidates emit no row; the oracle must refuse the same ones.
        keep = np.array([O.ladder(asset, float(a)) is not None for a in atr])
        if not np.array_equal(S["cand_id"][rows], cid[keep]):
            bad.append("cand_id set differs from the oracle's kept set")
            return asset, d8, tag, int(cid.size), bad
        cid, dec, side, atr = cid[keep], dec[keep], side[keep], atr[keep]

    ora = O.oracle_session(asset, int(d8), dec, side, atr)
    ora = [o for o in ora if o is not None]
    n = len(ora)
    if n != rows.size:
        bad.append("row count %d != oracle %d" % (rows.size, n))
        return asset, d8, tag, int(cid.size), bad

    for a in range(len(O.ANCHOR_DELAYS)):
        p = "a%d_" % a
        for name, dtype in SCALARS:
            got = np.ascontiguousarray(S[p + name][rows])
            exp = np.array([ora[i][a][name] for i in range(n)], dtype=dtype)
            if got.tobytes() != exp.tobytes():
                k = int(np.nonzero(got.view(_iview(dtype)) !=
                                   exp.view(_iview(dtype)))[0][0])
                bad.append("%s%s row %d: %r != %r" % (p, name, k, got[k], exp[k]))
        for name in ("tau_up", "tau_dn"):
            got = np.ascontiguousarray(
                S[p + name].reshape(-1, O.RUNG_COUNT)[rows])
            exp = np.stack([ora[i][a][name] for i in range(n)])
            if got.tobytes() != exp.tobytes():
                w = np.nonzero(got != exp)
                bad.append("%s%s row %d rung %d: %d != %d"
                           % (p, name, w[0][0], w[1][0] + 1,
                              got[w[0][0], w[1][0]], exp[w[0][0], w[1][0]]))
        for tag_r, off_k, len_k, t_k, v_k in (
                ("fav", "f_off", "f_len", "skel_f_t", "skel_f_v"),
                ("adv", "a_off", "a_len", "skel_a_t", "skel_a_v")):
            off = S[p + off_k][rows]
            ln = S[p + len_k][rows]
            exp_len = np.array([ora[i][a]["rec_%s_t" % tag_r[0]].size
                                for i in range(n)], dtype=np.int64)
            if ln.tobytes() != exp_len.tobytes():
                bad.append("%s%s length vector differs" % (p, len_k))
                continue
            for i in range(n):
                t = S[p + t_k][off[i]:off[i] + ln[i]]
                v = S[p + v_k][off[i]:off[i] + ln[i]]
                et = ora[i][a]["rec_%s_t" % tag_r[0]]
                ev = ora[i][a]["rec_%s_v" % tag_r[0]]
                if t.tobytes() != et.tobytes() or v.tobytes() != ev.tobytes():
                    bad.append("%s%s record block differs at row %d" % (p, tag_r, i))
                    break
    return asset, d8, tag, int(cid.size), bad


def _iview(dtype):
    return {np.float64: np.int64, np.float32: np.int32,
            np.int32: np.int32, np.int8: np.int8}[dtype]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("assets", nargs="*", default=list(ASSETS))
    ap.add_argument("--per-asset", type=int, default=8)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    if not 1 <= args.workers <= 6:
        raise SystemExit("workers must be 1..6")

    jobs = []
    for asset in (args.assets or list(ASSETS)):
        _, C = binpack.read(os.path.join(SKEL, "candidates", asset), "QRCAND1")
        have = set(int(x) for x in np.unique(C["date8"]))
        for d8, tag in stratify(asset, have, args.per_asset):
            jobs.append((asset, d8, tag))
    print("parity sessions: %d" % len(jobs))

    with mp.Pool(args.workers) as pool:
        results = pool.map(compare_session, jobs)

    fails, total_cands = 0, 0
    lines = []
    for asset, d8, tag, ncand, bad in sorted(results):
        total_cands += ncand
        status = "OK" if not bad else "MISMATCH"
        lines.append("%s\t%d\t%s\t%d\t%s\t%s"
                     % (asset, d8, tag, ncand, status, ";".join(bad[:3])))
        if bad:
            fails += 1
    out = os.path.join(SKEL, "parity")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "parity_sessions.tsv"), "w") as fh:
        fh.write("# PORT_M1B_SPEC.md S3 parity gate (design/PORT_M1B_S3_CONV.md)\n")
        fh.write("asset\tdate8\tstratum\tn_candidates\tverdict\tdetail\n")
        fh.write("\n".join(lines) + "\n")
    receipt = {"sessions": len(jobs), "candidates": total_cands,
               "anchors": total_cands * len(O.ANCHOR_DELAYS),
               "fields_per_anchor": len(SCALARS) + 2 * O.RUNG_COUNT,
               "mismatched_sessions": fails,
               "verdict": "PASS" if fails == 0 else "FAIL",
               "generated_utc": dt.datetime.now(dt.timezone.utc).replace(
                   microsecond=0, tzinfo=None).isoformat() + "Z"}
    with open(os.path.join(out, "parity.receipt.json"), "w") as fh:
        json.dump(receipt, fh, indent=1, sort_keys=True)
    for ln in lines:
        print(ln)
    print(json.dumps(receipt, sort_keys=True))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
