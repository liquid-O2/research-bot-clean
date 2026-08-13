#!/usr/bin/python3
"""PORT M0 s0_inventory (spec §2) — foreground, seconds (+ sha256 streaming).

Parses the three metadata.json + condition.json + directory listings into
m0/inventory.json.  Sealed (2026-dated) payload files are listed but NEVER
opened: their sha256 is null and they appear in the refused list.
"""
import concurrent.futures as cf
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C


PARAMS = {"spec_section": "s2/§2", "seal_cutoff": C.SEAL_CUTOFF,
          "sha256_workers": 8}


def _hash_one(path):
    return path, C.sha256_file(path)


def build_asset(asset, refusals):
    d = C.asset_dir(asset)
    spec = C.ASSETS[asset]

    with open(os.path.join(d, "metadata.json")) as fh:
        md = json.load(fh)
    with open(os.path.join(d, "condition.json")) as fh:
        cond_all = json.load(fh)
    with open(os.path.join(d, "manifest.json")) as fh:
        manifest = json.load(fh)

    q = md["query"]
    cust = md["customizations"]
    symbology = {"stype_in": q["stype_in"], "symbols": q["symbols"],
                 "split_duration": cust["split_duration"],
                 "stype_out": q["stype_out"], "dataset": q["dataset"]}

    # ---- verified facts to assert (§2) -------------------------------------
    asserts = {}
    asserts["symbols"] = (q["symbols"] == [spec["symbol"]])
    asserts["stype_in"] = (q["stype_in"] == spec["stype_in"])
    asserts["split_duration"] = (cust["split_duration"] == spec["split_duration"])
    cond_keep, cond_dropped = C.drop_2026_rows(cond_all)
    asserts["first_condition_date"] = (
        bool(cond_keep) and cond_keep[0]["date"] == spec["first_date"])
    bad = [k for k, v in asserts.items() if not v]
    if bad:
        raise AssertionError("%s: §2 verified-fact assertion failed: %s (query=%s)"
                             % (asset, bad, json.dumps(md)))

    # ---- condition summary (2026 rows dropped at parse) --------------------
    degraded = sorted(r["date"] for r in cond_keep if r["condition"] != "available")
    cond_summary = {
        "n_rows_total": len(cond_all),
        "n_rows_2026_dropped": len(cond_dropped),
        "n_available": sum(1 for r in cond_keep if r["condition"] == "available"),
        "n_degraded_or_missing": len(degraded),
        "degraded_or_missing_dates": degraded,
        "first_condition_date": cond_keep[0]["date"] if cond_keep else None,
        "last_condition_date": cond_keep[-1]["date"] if cond_keep else None,
    }
    cond_dates = {r["date"] for r in cond_keep}

    # ---- manifest cross-check ---------------------------------------------
    manifest_sha = {}
    for f in manifest.get("files", []):
        h = f.get("hash", "")
        if h.startswith("sha256:"):
            manifest_sha[f["filename"]] = h[7:]

    # ---- directory listing -------------------------------------------------
    entries = []
    to_hash = []
    for name in sorted(os.listdir(d)):
        p = os.path.join(d, name)
        if not os.path.isfile(p):
            continue
        payload = name.endswith(".dbn.zst")
        sealed = C.is_sealed(name)
        if payload and sealed:
            refusals.append("%s/%s" % (asset, name))
        rng = None
        if payload:
            s, e = C.file_date_range(p)
            rng = "%s..%s" % (s.isoformat(), e.isoformat())
        ent = {"path": p, "name": name, "bytes": os.path.getsize(p),
               "payload": payload, "sealed": bool(payload and sealed),
               "date_or_range": rng, "sha256": None,
               "kind": ("trades" if ".trades." in name
                        else ("mbp-1" if payload else "admin"))}
        entries.append(ent)
        if not (payload and sealed):
            to_hash.append(ent)

    C.hb("s0 %s: hashing %d files (%.1f GiB)"
         % (asset, len(to_hash), sum(e["bytes"] for e in to_hash) / 2 ** 30))
    with cf.ThreadPoolExecutor(max_workers=PARAMS["sha256_workers"]) as ex:
        for path, digest in ex.map(_hash_one, [e["path"] for e in to_hash]):
            for e in to_hash:
                if e["path"] == path:
                    e["sha256"] = digest
                    break
    mism = [e["name"] for e in to_hash
            if e["name"] in manifest_sha and manifest_sha[e["name"]] != e["sha256"]]

    # ---- utc date map ------------------------------------------------------
    # date -> source payload basename, for unsealed mbp-1 files only, restricted
    # to dates the (2026-stripped) condition.json knows about.
    date_map = {}
    for e in entries:
        if not e["payload"] or e["sealed"] or e["kind"] != "mbp-1":
            continue
        s, en = C.file_date_range(e["path"])
        cur = s
        while cur <= en:
            iso = cur.isoformat()
            if iso in cond_dates:
                date_map[iso] = e["name"]
            cur += dt.timedelta(days=1)
    dates = sorted(date_map)

    # dates present in condition.json but with no unsealed payload file
    missing_files = sorted(x for x in cond_dates if x not in date_map)

    return {
        "asset": asset,
        "dir": d,
        "symbology": symbology,
        "constants": {k: spec[k] for k in
                      ("mult", "px_scale", "tick_px", "tick_usd", "tick_raw",
                       "band", "layout")},
        "files": entries,
        "n_files": len(entries),
        "n_payload_files": sum(1 for e in entries if e["payload"]),
        "n_sealed_refused": sum(1 for e in entries if e["sealed"]),
        "condition_summary": cond_summary,
        "manifest_sha_mismatches": mism,
        "utc_date_map": date_map,
        "n_usable_dates": len(dates),
        "first_usable_date": dates[0] if dates else None,
        "last_usable_date": dates[-1] if dates else None,
        "condition_dates_without_unsealed_file": missing_files,
    }


def main():
    C.verify_spec()
    os.makedirs(C.OUT_ROOT, exist_ok=True)
    refusals = []
    assets = {}
    for a in C.ASSET_ORDER:
        assets[a] = build_asset(a, refusals)
        s = assets[a]
        C.hb("s0 %s: %d files (%d payload, %d sealed-refused) usable %s..%s"
             % (a, s["n_files"], s["n_payload_files"], s["n_sealed_refused"],
                s["first_usable_date"], s["last_usable_date"]))

    inv = {
        "spec_section": "§2 s0_inventory",
        "generated_utc": None,          # deliberately omitted: keeps the receipt
                                        # byte-identical across reruns
        "env": C.env_receipt(PARAMS),
        "seal": {"cutoff": C.SEAL_CUTOFF,
                 "refused_2026_files": sorted(refusals),
                 "n_refused": len(refusals)},
        "assets": assets,
    }
    p = C.write_json(C.out_path("inventory.json"), inv)
    C.hb("s0 wrote %s (%d refused 2026 files)" % (p, len(refusals)))

    # small stdout summary
    for a in C.ASSET_ORDER:
        s = assets[a]
        print("%-4s files=%-5d payload=%-5d sealed_refused=%-4d degraded=%-3d "
              "usable=%s..%s (%d dates)"
              % (a, s["n_files"], s["n_payload_files"], s["n_sealed_refused"],
                 s["condition_summary"]["n_degraded_or_missing"],
                 s["first_usable_date"], s["last_usable_date"],
                 s["n_usable_dates"]))
        if s["manifest_sha_mismatches"]:
            print("     MANIFEST SHA MISMATCH: %s" % s["manifest_sha_mismatches"])
        if s["condition_dates_without_unsealed_file"]:
            print("     condition dates with no unsealed file: %s"
                  % s["condition_dates_without_unsealed_file"])
    print("refused (2026 seal): %d" % len(refusals))
    return 0


if __name__ == "__main__":
    sys.exit(main())
