#!/usr/bin/python3
"""PORT M0 s1_repro_si2024 (spec §3) — THE ACCEPTANCE GATE.

Reproduce artifacts/cache/campaign/diagnostics/SILVER_CENSUS_2024.txt:
  313 days, 232,077,260 updates
  FULL mean $3,537 median $3,275 p75 $4,663
  RTH  mean $2,162 median $1,925 p75 $2,613

REPRO MODE conventions (committed behavior, NOT the program conventions):
  - record kept iff bid>0 and ask>0 and ask>bid and bid<2**62 and ask<2**62
  - UTC day = ts_event//1e9//86400 ; second-of-day = (ts_event//1e9)%86400
  - last update in a second wins; no F_LAST filter; no spread exclusion
  - dominance candidate rules R1..R4 tried in order until fingerprint match
  - day kept iff dominant's populated seconds >= 100
  - mid = (bid+ask)/2 * 1e-9 ; range = (max-min)*5000
  - RTH = seconds [52200, 75600) ; needs >10 RTH seconds else NaN

Bucketing note (spec §3): the "Bucketing" bullet defines the UTC day as
ts_event//1e9//86400, while the dominance bullet asserts "Per file (= per UTC
day)".  The two do NOT coincide: every SI daily file opens with snapshot records
(SNAPSHOT | BAD_TS_RECV) whose ts_event lands on the PREVIOUS UTC day.  All three
readings are computed and all three go in the receipt:
  FILEDATE — "Per file (= per UTC day)" taken literally: the day IS the file, the
             second-of-day is (ts_event//1e9)%86400 exactly as specced.  PRIMARY.
  GLOBAL   — the ts_event day bullet taken literally: all 314 files merged into
             one ts_event-keyed day map, later file wins a shared second.
  PERFILE  — each file bucketed by ts_event day but standing alone, so foreign-day
             buckets fall under the 100-second floor and are dropped.
Only FILEDATE reproduces the committed numbers; the other two land the FULL mean
at $3,536.30 (the stale-snapshot mids that sit outside RTH are what moves it).

Exit 0 on MATCH, 2 on NO MATCH (spec §3: nothing downstream launches).
"""
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

YEAR = 2024
N_WORKERS = 10
RULES = ("R1", "R2", "R3", "R4")
BUCKETINGS = ("FILEDATE", "GLOBAL", "PERFILE")
PRIMARY_BUCKETING = "FILEDATE"
RULE_DESC = {
    "R1": "update-count winner among ALL instrument_ids (raw heredoc reading)",
    "R2": "update-count winner among OUTRIGHTS only",
    "R3": "trade-size-sum winner (action=='T') among ALL instrument_ids",
    "R4": "trade-size-sum winner (action=='T') among OUTRIGHTS only",
}
TARGET = {
    "days": 313,
    "updates": 232_077_260,
    "full_mean": 3537, "full_median": 3275, "full_p75": 4663,
    "rth_mean": 2162, "rth_median": 1925, "rth_p75": 2613,
}
PARAMS = {
    "spec_section": "§3 s1_repro_si2024", "year": YEAR, "asset": "SI",
    "mult": 5000, "px_scale": 1e-9, "rth_sec": [C.RTH_LO_SEC, C.RTH_HI_SEC],
    "min_seconds": 100, "min_rth_seconds": 11, "rules": list(RULES),
    "bucketings": list(BUCKETINGS), "primary_bucketing": PRIMARY_BUCKETING,
    "tie_break": "higher metric, then lower instrument_id",
}


# ------------------------------------------------------------------ worker --
def scan_file(path):
    """One SI daily file -> compact per-(UTC day, instrument) pieces."""
    name = os.path.basename(path)
    fdate = C.file_date_range(path)[0]
    counts = {}      # (day, iid) -> valid update count
    tsz = {}         # (day, iid) -> trade size sum over valid records
    secmap = {}      # (day, iid) -> {sec: mid}   (last-in-file wins)
    inv = {}
    n_records = 0
    n_kept = 0
    for rec in C.iter_dbn(path):
        if isinstance(rec, C.databento_dbn.Metadata):
            inv = C.invert_mappings(rec)
            continue
        lv = getattr(rec, "levels", None)
        if not lv:
            continue
        n_records += 1
        bid = lv[0].bid_px
        ask = lv[0].ask_px
        if not C.two_sided(bid, ask):          # guard order per §0
            continue
        n_kept += 1
        ts = rec.ts_event // 1_000_000_000
        key = (ts // 86400, rec.instrument_id)
        counts[key] = counts.get(key, 0) + 1
        if rec.action == "T":
            tsz[key] = tsz.get(key, 0) + int(rec.size)
        sm = secmap.get(key)
        if sm is None:
            sm = secmap[key] = {}
        sm[ts % 86400] = (bid + ask) / 2 * 1e-9

    packed = {}
    for key, sm in secmap.items():
        secs = sorted(sm)
        packed[key] = (np.fromiter(secs, dtype=np.int32, count=len(secs)),
                       np.fromiter((sm[s] for s in secs), dtype=np.float64,
                                   count=len(secs)))
    outright = {}
    for _, iid in counts:
        if iid not in outright:
            outright[iid] = C.is_outright(C.symbol_for(inv, iid, fdate))
    return {"file": name, "fday": C.date_to_day(fdate),
            "n_records": n_records, "n_kept": n_kept,
            "counts": counts, "tsz": tsz, "packed": packed,
            "outright": outright}


# ------------------------------------------------------------------ parent --
def _rekey(key, f, bucketing):
    """(ts_event_day, iid) -> the bucket key for this bucketing."""
    if bucketing == "FILEDATE":
        return (f["fday"], key[1])
    if bucketing == "PERFILE":
        return (key[0], key[1], f["file"])
    return key


def merge(per_file, bucketing):
    """-> counts, tsz, packed, outright keyed by (day, iid)."""
    counts, tsz, outright = {}, {}, {}
    chunks = {}
    for f in per_file:                      # per_file is sorted by filename
        outright.update(f["outright"])
        for k, v in f["counts"].items():
            k = _rekey(k, f, bucketing)
            counts[k] = counts.get(k, 0) + v
        for k, v in f["tsz"].items():
            k = _rekey(k, f, bucketing)
            tsz[k] = tsz.get(k, 0) + v
        # ascending ts_event day inside a file == stream order (the leading
        # snapshot records are the only ones carrying an earlier day), so
        # last-occurrence-wins below resolves a shared second correctly.
        for k in sorted(f["packed"]):
            chunks.setdefault(_rekey(k, f, bucketing), []).append(f["packed"][k])
    packed = {}
    for k, lst in chunks.items():
        secs = np.concatenate([a[0] for a in lst])
        mids = np.concatenate([a[1] for a in lst])
        order = np.argsort(secs, kind="stable")       # arrival order preserved
        secs, mids = secs[order], mids[order]
        keep = np.empty(len(secs), dtype=bool)
        keep[:-1] = secs[:-1] != secs[1:]             # last occurrence wins
        keep[-1] = True
        packed[k] = (secs[keep], mids[keep])
    return counts, tsz, packed, outright


def rounded(x):
    return None if not np.isfinite(x) else int(round(float(x)))


def fingerprint(rule, bucketing, counts, tsz, packed, outright, total_kept_all):
    buckets = {}
    for key in counts:
        buckets.setdefault(key[:1] + key[2:], []).append(key[1])
    rows = {}
    for bkey, iids in buckets.items():
        iids = sorted(iids)
        day = bkey[0]
        if rule in ("R1", "R2"):
            pool = [i for i in iids if rule == "R1" or outright.get(i, False)]
            metric = {i: counts[(day, i) + bkey[1:]] for i in pool}
        else:
            pool = [i for i in iids if rule == "R3" or outright.get(i, False)]
            metric = {i: tsz.get((day, i) + bkey[1:], 0) for i in pool}
        if not pool:
            continue
        best = max(metric.values())
        if best <= 0:
            continue
        dom = min(i for i in pool if metric[i] == best)
        secs, mids = packed[(day, dom) + bkey[1:]]
        if len(secs) < 100:
            continue
        full = (mids.max() - mids.min()) * 5000
        sel = (secs >= C.RTH_LO_SEC) & (secs < C.RTH_HI_SEC)
        nr = int(sel.sum())
        rth = ((mids[sel].max() - mids[sel].min()) * 5000
               if nr > 10 else float("nan"))
        rows[bkey] = {"day": day, "dom": dom, "n_sec": len(secs),
                      "dom_updates": counts[(day, dom) + bkey[1:]],
                      "bucket_updates": sum(counts[(day, i) + bkey[1:]]
                                            for i in iids),
                      "full": float(full), "rth": float(rth)}
    keys = sorted(rows)
    full = np.array([rows[k]["full"] for k in keys], dtype=float)
    rth = np.array([rows[k]["rth"] for k in keys], dtype=float)
    fp = {
        "rule": rule, "bucketing": bucketing, "desc": RULE_DESC[rule],
        "kept_days": len(keys),
        "updates_all_records": total_kept_all,
        "updates_kept_days_all_instruments": int(sum(rows[k]["bucket_updates"]
                                                     for k in keys)),
        "updates_kept_days_dominant": int(sum(rows[k]["dom_updates"] for k in keys)),
        "full_mean_raw": float(np.nanmean(full)) if len(full) else None,
        "full_median_raw": float(np.nanmedian(full)) if len(full) else None,
        "full_p75_raw": float(np.nanpercentile(full, 75)) if len(full) else None,
        "rth_mean_raw": float(np.nanmean(rth)) if len(rth) else None,
        "rth_median_raw": float(np.nanmedian(rth)) if len(rth) else None,
        "rth_p75_raw": float(np.nanpercentile(rth, 75)) if len(rth) else None,
    }
    for k in ("full_mean", "full_median", "full_p75",
              "rth_mean", "rth_median", "rth_p75"):
        fp[k] = rounded(fp[k + "_raw"]) if fp[k + "_raw"] is not None else None
    fp["first_day"] = C.day_to_date(rows[keys[0]]["day"]).isoformat() if keys else None
    fp["last_day"] = C.day_to_date(rows[keys[-1]]["day"]).isoformat() if keys else None
    fp["updates_variants_matching_target"] = sorted(
        k for k in ("updates_all_records", "updates_kept_days_all_instruments",
                    "updates_kept_days_dominant")
        if fp[k] == TARGET["updates"])
    fp["stats_match"] = all(fp[k] == TARGET[k] for k in
                            ("full_mean", "full_median", "full_p75",
                             "rth_mean", "rth_median", "rth_p75"))
    fp["days_match"] = (fp["kept_days"] == TARGET["days"])
    fp["updates_match"] = bool(fp["updates_variants_matching_target"])
    fp["MATCH"] = bool(fp["stats_match"] and fp["days_match"] and fp["updates_match"])
    return fp, rows


def main():
    C.verify_spec()
    files = C.si_daily_files(YEAR)
    C.hb("s1: %d SI %d daily files, %d workers" % (len(files), YEAR, N_WORKERS))
    if len(files) != 314:
        C.hb("s1 WARNING: spec §3 says 314 files, found %d" % len(files))

    inv_path = os.path.join(C.OUT_ROOT, "inventory.json")
    input_sha = {}
    if os.path.exists(inv_path):
        with open(inv_path) as fh:
            inv = json.load(fh)
        want = {os.path.basename(p) for p in files}
        for e in inv["assets"]["SI"]["files"]:
            if e["name"] in want:
                input_sha[e["name"]] = e["sha256"]

    t0 = time.time()
    per_file = []
    with mp.Pool(N_WORKERS) as pool:
        for i, res in enumerate(pool.imap_unordered(scan_file, files, chunksize=4), 1):
            per_file.append(res)
            if i % 50 == 0 or i == len(files):
                el = time.time() - t0
                C.hb("s1 decode %d/%d  %.1f files/s  eta %.0fs"
                     % (i, len(files), i / el, (len(files) - i) / (i / el)))
    per_file.sort(key=lambda f: f["file"])          # determinism

    total_records = sum(f["n_records"] for f in per_file)
    total_kept = sum(f["n_kept"] for f in per_file)
    C.hb("s1: %d records, %d kept (two-sided)" % (total_records, total_kept))

    fps = {}
    winner = None
    winner_rows = None
    for bucketing in BUCKETINGS:
        counts, tsz, packed, outright = merge(per_file, bucketing)
        for rule in RULES:
            fp, rows = fingerprint(rule, bucketing, counts, tsz, packed,
                                   outright, total_kept)
            fps["%s/%s" % (bucketing, rule)] = fp
            C.hb("s1 %-7s %s: days=%s upd(all=%s keptdays=%s dom=%s) "
                 "FULL %s/%s/%s RTH %s/%s/%s MATCH=%s"
                 % (bucketing, rule, fp["kept_days"], fp["updates_all_records"],
                    fp["updates_kept_days_all_instruments"],
                    fp["updates_kept_days_dominant"],
                    fp["full_mean"], fp["full_median"], fp["full_p75"],
                    fp["rth_mean"], fp["rth_median"], fp["rth_p75"], fp["MATCH"]))
            if (winner is None and fp["MATCH"]
                    and bucketing == PRIMARY_BUCKETING):
                winner = "%s/%s" % (bucketing, rule)
                winner_rows = rows
        del counts, tsz, packed

    receipt = {
        "spec_section": "§3 s1_repro_si2024",
        "env": C.env_receipt(PARAMS, input_sha256=input_sha),
        "target": TARGET,
        "n_files": len(files),
        "n_records_total": total_records,
        "n_kept_records_total": total_kept,
        "winning_rule": winner,
        "primary_bucketing": PRIMARY_BUCKETING,
        "fingerprints": fps,
        "order_tried": ["%s/%s" % (b, r) for b in BUCKETINGS for r in RULES],
        "verdict": "MATCH" if winner else "NO_MATCH",
    }
    if winner:
        receipt["winner_days"] = [
            {"date": C.day_to_date(winner_rows[k]["day"]).isoformat(),
             "dominant_id": winner_rows[k]["dom"],
             "dominant_updates": winner_rows[k]["dom_updates"],
             "bucket_updates": winner_rows[k]["bucket_updates"],
             "n_seconds": winner_rows[k]["n_sec"],
             "full_range": winner_rows[k]["full"],
             "rth_range": winner_rows[k]["rth"]}
            for k in sorted(winner_rows)]
    p = C.write_json(C.out_path("repro_si2024.receipt.json"), receipt)
    C.hb("s1 receipt -> %s verdict=%s" % (p, receipt["verdict"]))

    print("%-14s %-5s %-14s %-14s %-14s %-19s %-19s %s"
          % ("bucketing/rule", "days", "upd_all", "upd_keptdays", "upd_dom",
             "FULL mean/med/p75", "RTH mean/med/p75", "MATCH"))
    for k in receipt["order_tried"]:
        f = fps[k]
        print("%-14s %-5s %-14s %-14s %-14s %-6s/%-6s/%-5s %-6s/%-6s/%-5s %s"
              % (k, f["kept_days"], f["updates_all_records"],
                 f["updates_kept_days_all_instruments"],
                 f["updates_kept_days_dominant"],
                 f["full_mean"], f["full_median"], f["full_p75"],
                 f["rth_mean"], f["rth_median"], f["rth_p75"], f["MATCH"]))
    print("%-14s %-5s %-14s %-14s %-14s %-6s/%-6s/%-5s %-6s/%-6s/%-5s"
          % ("TARGET", TARGET["days"], TARGET["updates"], TARGET["updates"],
             TARGET["updates"], TARGET["full_mean"], TARGET["full_median"],
             TARGET["full_p75"], TARGET["rth_mean"], TARGET["rth_median"],
             TARGET["rth_p75"]))
    print("VERDICT: %s%s" % (receipt["verdict"],
                             (" rule=%s" % winner) if winner else ""))
    return 0 if winner else 2


if __name__ == "__main__":
    sys.exit(main())
