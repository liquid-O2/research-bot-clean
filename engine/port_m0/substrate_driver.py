#!/usr/bin/python3
"""PORT M0 substrate driver — ONE detached run.sh job carrying s2 + s3.

Stages (sequential, stderr-logged):
  1  s2  SI                     8 worker processes over the daily files
  2  s2  HG + NKD               2 + 2 workers, one streaming reader per year file
  3  integrity_flags.tsv        merged, sorted, deterministic
  4  byte-identity check A      fixed 2% day sample + all of 2024-06, re-decoded
                                at a DIFFERENT chunk size; receipt sha256 must match
  5  s3  SI, HG, NKD            sessions, phases, bars
  6  yahoo spot-check (§11.3)   3 sessions/asset vs port_context/yahoo_*_daily.csv

Spec §0 named separate run names for s2/s3; a single driver job is the accepted
operational topology (orchestrator ruling).  Per-stage receipt files are exactly
as specced.  Total worker processes never exceed 12.
"""
import csv
import datetime as dt
import json
import os
import shutil
import sys
import threading
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import s2_decode as S2
import s3_sessions as S3

SI_WORKERS = 8
YEARLY_WORKERS = 2               # per asset; HG and NKD run concurrently
BYTEID_SAMPLE_STRIDE = 50        # a fixed 2% sample of days
BYTEID_MONTH = "2024-06"
BYTEID_CHUNK = 1 << 20           # 1 MiB, deliberately != the 4 MiB production chunk
YAHOO_SESSIONS = 3
YAHOO_PCT = 0.005                # max(0.5%, 2 ticks)


def stage(n, msg):
    C.hb("=== STAGE %s: %s" % (n, msg))


# ------------------------------------------------------------------ stage 2 --
def run_yearly_pair():
    out = {}
    lock = threading.Lock()

    def work(asset):
        idx, flags = S2.run_asset(asset, YEARLY_WORKERS)
        with lock:
            out[asset] = (idx, flags)

    ts = [threading.Thread(target=work, args=(a,)) for a in ("HG", "NKD")]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return out


# ------------------------------------------------------------------ stage 4 --
def sample_dates(asset):
    d = os.path.join(C.OUT_ROOT, "receipts", asset)
    days = sorted(n[:-4] for n in os.listdir(d) if n.endswith(".npz"))
    iso = ["%s-%s-%s" % (x[:4], x[4:6], x[6:8]) for x in days]
    sample = {iso[i] for i in range(0, len(iso), BYTEID_SAMPLE_STRIDE)}
    sample |= {x for x in iso if x.startswith(BYTEID_MONTH)}
    return sorted(sample)


def byte_identity_a():
    rows = []
    tmp_root = os.path.join(C.OUT_ROOT, "_byteid")
    for asset in C.ASSET_ORDER:
        dates = sample_dates(asset)
        out_dir = os.path.join(tmp_root, asset)
        shutil.rmtree(out_dir, ignore_errors=True)
        os.makedirs(out_dir, exist_ok=True)
        files = None
        if C.ASSETS[asset]["layout"] == "daily":
            want = {d.replace("-", "") for d in dates}
            files = [p for p in C.si_daily_files()
                     if os.path.basename(p).split("-")[2].split(".")[0] in want]
            workers = SI_WORKERS
        else:
            workers = YEARLY_WORKERS
        C.hb("byte-id A %s: %d sampled days, chunk=%d" % (asset, len(dates),
                                                          BYTEID_CHUNK))
        idx, _ = S2.run_asset(asset, workers, only_dates=set(dates),
                              out_dir=out_dir, chunk=BYTEID_CHUNK,
                              write_index=False, files=files)
        got = {d: sha for (d, _p, sha) in idx}
        base = {}
        with open(os.path.join(C.OUT_ROOT, "receipts_index_%s.tsv" % asset)) as fh:
            for line in fh:
                if line.startswith("#") or line.startswith("date\t"):
                    continue
                d, _p, sha = line.rstrip("\n").split("\t")
                base[d] = sha
        for d in dates:
            a, b = base.get(d), got.get(d)
            rows.append([asset, d, a or "", b or "",
                         "MATCH" if (a and a == b) else "MISMATCH"])
        shutil.rmtree(out_dir, ignore_errors=True)
    shutil.rmtree(tmp_root, ignore_errors=True)
    n_bad = sum(1 for r in rows if r[4] != "MATCH")
    C.write_tsv(C.out_path("byte_identity_A.tsv"), "§4 byte-identity check A",
                C.params_hash({"stride": BYTEID_SAMPLE_STRIDE,
                               "month": BYTEID_MONTH, "chunk": BYTEID_CHUNK}),
                ["asset", "date", "sha256_run1", "sha256_run2", "verdict"], rows,
                extra=["rerun chunk size = %d bytes (production = %d)"
                       % (BYTEID_CHUNK, C.CHUNK)])
    C.hb("byte-id A: %d sampled receipts, %d mismatches" % (len(rows), n_bad))
    return n_bad


# ------------------------------------------------------------------ stage 6 --
def yahoo_spotcheck():
    rows = []
    for asset in C.ASSET_ORDER:
        path = "/workspace/artifacts/reference/port_context/yahoo_%s_daily.csv" % asset
        ref = {}
        if os.path.exists(path):
            with open(path) as fh:
                for r in csv.DictReader(fh):
                    try:
                        ref[r["date"]] = (float(r["high"]), float(r["low"]))
                    except (ValueError, KeyError):
                        pass
        bars = []
        bp = os.path.join(C.OUT_ROOT, "bars_%s.tsv" % asset)
        if not os.path.exists(bp):
            continue
        with open(bp) as fh:
            for line in fh:
                if line.startswith("#") or line.startswith("trade_date\t"):
                    continue
                f = line.rstrip("\n").split("\t")
                bars.append((f[0], float(f[4]), float(f[5])))
        # a fixed, deterministic pick: the first bar of 2022, 2023 and 2024
        picks = []
        for yr in (2022, 2023, 2024):
            for d, h, lo in bars:
                if d.startswith(str(yr)) and d in ref:
                    picks.append((d, h, lo))
                    break
        tick = C.ASSETS[asset]["tick_px"]
        for d, h, lo in picks[:YAHOO_SESSIONS]:
            yh, yl = ref[d]
            tol_h = max(YAHOO_PCT * abs(yh), 2 * tick)
            tol_l = max(YAHOO_PCT * abs(yl), 2 * tick)
            ok = abs(h - yh) <= tol_h and abs(lo - yl) <= tol_l
            rows.append([asset, d, "%.6f" % h, "%.6f" % yh, "%.6f" % lo,
                         "%.6f" % yl, "%.6f" % tol_h, "%.6f" % tol_l,
                         "OK" if ok else "FLAG"])
    C.write_tsv(C.out_path("yahoo_spotcheck.tsv"), "§11.3 yahoo spot-check",
                C.params_hash({"pct": YAHOO_PCT, "n": YAHOO_SESSIONS}),
                ["asset", "trade_date", "grid_H", "yahoo_H", "grid_L", "yahoo_L",
                 "tol_H", "tol_L", "verdict"], rows,
                extra=["session H/L are Globex-session mids of the dominant "
                       "instrument; Yahoo bars are RTH continuous-front settle "
                       "series (FX/roll basis caveats apply)"])
    C.hb("yahoo spot-check: %d rows, %d flagged"
         % (len(rows), sum(1 for r in rows if r[8] != "OK")))
    return rows


# --------------------------------------------------------------------- main --
def main():
    C.verify_spec()
    t_all = time.time()
    rp = os.path.join(C.OUT_ROOT, "repro_si2024.receipt.json")
    with open(rp) as fh:
        repro = json.load(fh)
    if repro.get("verdict") != "MATCH":
        C.hb("driver ABORT: s1 verdict is %s" % repro.get("verdict"))
        return 2
    rule = repro["winning_rule"].split("/")[-1]
    C.hb("driver start; s1 pinned rule %s (%s)" % (repro["winning_rule"], rule))

    all_flags = []

    stage(1, "s2 decode SI (%d workers)" % SI_WORKERS)
    t = time.time()
    _, f = S2.run_asset("SI", SI_WORKERS)
    all_flags += f
    C.hb("stage 1 done in %.0fs" % (time.time() - t))

    stage(2, "s2 decode HG + NKD (%d + %d workers)" % (YEARLY_WORKERS,
                                                        YEARLY_WORKERS))
    t = time.time()
    for asset, (_idx, f) in sorted(run_yearly_pair().items()):
        all_flags += f
    C.hb("stage 2 done in %.0fs" % (time.time() - t))

    stage(3, "integrity flags")
    n = S2.write_flags(all_flags)
    C.hb("stage 3: %d integrity flag rows" % n)

    stage(4, "byte-identity check A")
    t = time.time()
    n_bad = byte_identity_a()
    C.hb("stage 4 done in %.0fs (%d mismatches)" % (time.time() - t, n_bad))

    stage(5, "s3 session assemble")
    for asset in C.ASSET_ORDER:
        t = time.time()
        S3.run_asset(asset, rule)
        C.hb("stage 5 %s done in %.0fs" % (asset, time.time() - t))

    stage(6, "yahoo spot-check")
    yahoo_spotcheck()

    C.hb("driver COMPLETE in %.0fs" % (time.time() - t_all))
    return 0


if __name__ == "__main__":
    sys.exit(main())
