#!/usr/bin/python3
"""PORT M1 TRACK A differential gate (design/PORT_M1_SPEC.md §1.3 / §7 gate A).

Loads EVERY M0 session receipt (artifacts/cache/port/m0/sessions/{ASSET}/*.npz)
and the C++ receipt written by `qr_futsess_assemble`
(artifacts/cache/port/m1/cpp_sessions/{ASSET}/{YYYYMMDD}.{bin,json}) and asserts
FIELD-EXACT equality:

  * every integer array byte-for-byte (raw 1e-9 price units included);
  * every state-code array byte-for-byte;
  * the trade arrays byte-for-byte, in order;
  * the float arrays (mid, spread_usd) byte-for-byte, so a NaN in one and a
    zero in the other can never pass, and neither can a 1-ulp drift;
  * every scalar of the session metadata, with floats compared on their exact
    IEEE-754 bits.

Any mismatch is reported per (asset, date, field) and the run exits non-zero.
There is no tolerance parameter: the gate is exactness.

usage: compare.py [ASSET ...] [--workers N] [--limit N]
"""
import argparse
import collections
import datetime as dt
import json
import multiprocessing as mp
import os
import struct
import sys

import numpy as np

M0_ROOT = "/workspace/artifacts/cache/port/m0/sessions"
M1_ROOT = "/workspace/artifacts/cache/port/m1/cpp_sessions"
OUT_ROOT = "/workspace/artifacts/cache/port/m1/diff"
ASSETS = ("SI", "HG", "NKD")

DTYPES = {
    "int64": np.dtype("<i8"),
    "int32": np.dtype("<i4"),
    "int8": np.dtype("i1"),
    "uint8": np.dtype("u1"),
    "float64": np.dtype("<f8"),
}

# Metadata keys that are integers in one receipt and may be null in both.
NULLABLE_INT_KEYS = ("runner_up_id", "prev_session_dominant", "dominant_all_id",
                     "dominant_outright_id")


def load_cpp(stem):
    """(meta, arrays, extra_scalars) from a C++ session receipt pair."""
    with open(stem + ".json") as fh:
        side = json.load(fh)
    with open(stem + ".bin", "rb") as fh:
        blob = fh.read()
    arrays = {}
    for d in side["arrays"]:
        dtype = DTYPES[d["dtype"]]
        off, cnt = d["offset"], d["count"]
        end = off + cnt * dtype.itemsize
        if end > len(blob):
            raise ValueError("array %s runs past the end of %s.bin" % (d["name"], stem))
        arrays[d["name"]] = np.frombuffer(blob, dtype=dtype, count=cnt, offset=off)
    scalars = {k: v for k, v in side.items()
               if k.endswith("_iid") and k.startswith("g")}
    return side["meta"], arrays, scalars


def float_bits(x):
    return struct.pack("<d", float(x))


def cmp_scalar(key, want, got):
    """None when equal; otherwise a short description of the difference."""
    if want is None or got is None:
        if want is None and got is None:
            return None
        return "null-mismatch want=%r got=%r" % (want, got)
    if isinstance(want, bool) or isinstance(got, bool):
        if bool(want) != bool(got):
            return "want=%r got=%r" % (want, got)
        return None
    if isinstance(want, float) or isinstance(got, float):
        if float_bits(want) != float_bits(got):
            return "float bits want=%.17g got=%.17g" % (float(want), float(got))
        return None
    if isinstance(want, (list, tuple)) or isinstance(got, (list, tuple)):
        if list(want) != list(got):
            return "want=%r got=%r" % (want, got)
        return None
    if want != got:
        return "want=%r got=%r" % (want, got)
    return None


def compare_session(task):
    """Compare one session. Returns (asset, date, [(field, detail), ...])."""
    asset, date, npz_path = task
    bad = []
    stem = os.path.join(M1_ROOT, asset, date)
    if not (os.path.exists(stem + ".bin") and os.path.exists(stem + ".json")):
        return asset, date, [("_receipt", "C++ receipt missing")]
    try:
        meta_c, arrays_c, scalars_c = load_cpp(stem)
    except Exception as exc:                       # noqa: BLE001 - reported, not raised
        return asset, date, [("_receipt", "C++ receipt unreadable: %s" % exc)]

    z = np.load(npz_path, allow_pickle=False)
    try:
        meta_p = json.loads(str(z["meta_json"]))
        # ---- arrays ------------------------------------------------------
        want_names = sorted(k for k in z.files if k != "meta_json")
        got_names = sorted(list(arrays_c) + list(scalars_c))
        if want_names != got_names:
            bad.append(("_arrays", "name set: only-m0=%r only-cpp=%r"
                        % (sorted(set(want_names) - set(got_names)),
                           sorted(set(got_names) - set(want_names)))))
        for name in want_names:
            want = z[name]
            if name in scalars_c:                  # the g{k}_iid scalars
                if int(want) != int(scalars_c[name]):
                    bad.append((name, "want=%d got=%d" % (int(want), scalars_c[name])))
                continue
            if name not in arrays_c:
                continue
            got = arrays_c[name]
            if want.dtype != got.dtype:
                bad.append((name, "dtype want=%s got=%s" % (want.dtype, got.dtype)))
                continue
            if want.shape != got.shape:
                bad.append((name, "shape want=%s got=%s" % (want.shape, got.shape)))
                continue
            if want.tobytes() == got.tobytes():
                continue
            # Byte-unequal. Say how, precisely, so a diagnosis does not need a
            # second run: NaN-vs-NaN payload drift is a different fault from a
            # wrong value.
            if want.dtype.kind == "f" and np.array_equal(want, got, equal_nan=True):
                bad.append((name, "float NaN bit-payload differs (values equal)"))
                continue
            neq = np.nonzero(want != got)[0] if want.ndim == 1 else np.array([])
            if want.dtype.kind == "f":
                neq = np.nonzero(~((want == got) | (np.isnan(want) & np.isnan(got))))[0]
            n = int(neq.size)
            first = int(neq[0]) if n else -1
            detail = "%d/%d elements differ" % (n, want.size)
            if first >= 0:
                detail += "; first at %d want=%r got=%r" % (first, want[first], got[first])
            bad.append((name, detail))
        # ---- metadata ----------------------------------------------------
        keys = sorted(set(meta_p) | set(meta_c))
        for k in keys:
            if k not in meta_p:
                bad.append(("meta." + k, "absent from the m0 receipt"))
                continue
            if k not in meta_c:
                bad.append(("meta." + k, "absent from the C++ receipt"))
                continue
            d = cmp_scalar(k, meta_p[k], meta_c[k])
            if d is not None:
                bad.append(("meta." + k, d))
    finally:
        z.close()
    return asset, date, bad


def enumerate_tasks(assets, limit):
    tasks = []
    for asset in assets:
        d = os.path.join(M0_ROOT, asset)
        if not os.path.isdir(d):
            continue
        names = sorted(n for n in os.listdir(d) if n.endswith(".npz"))
        if limit:
            names = names[:limit]
        for n in names:
            tasks.append((asset, n[:-4], os.path.join(d, n)))
    return tasks


def orphan_cpp_receipts(assets, expected):
    """C++ receipts with no M0 counterpart — an extra session is a mismatch too."""
    out = []
    for asset in assets:
        d = os.path.join(M1_ROOT, asset)
        if not os.path.isdir(d):
            continue
        for n in sorted(os.listdir(d)):
            if n.endswith(".json") and (asset, n[:-5]) not in expected:
                out.append((asset, n[:-5]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("assets", nargs="*", default=None)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    assets = args.assets or list(ASSETS)
    workers = max(1, min(args.workers, 6))       # shared box: the lane cap is 6

    tasks = enumerate_tasks(assets, args.limit)
    if not tasks:
        sys.stderr.write("no M0 session receipts found for %r\n" % (assets,))
        return 2
    sys.stderr.write("[m1-diff] %d sessions, %d workers\n" % (len(tasks), workers))

    results = []
    if workers <= 1:
        results = [compare_session(t) for t in tasks]
    else:
        with mp.Pool(workers) as pool:
            for i, r in enumerate(pool.imap_unordered(compare_session, tasks, chunksize=8), 1):
                results.append(r)
                if i % 250 == 0:
                    nbad = sum(1 for x in results if x[2])
                    sys.stderr.write("[m1-diff] %d/%d compared, %d mismatching sessions\n"
                                     % (i, len(tasks), nbad))
                    sys.stderr.flush()
    results.sort()

    expected = {(a, d) for a, d, _ in tasks}
    orphans = orphan_cpp_receipts(assets, expected)

    by_field = collections.Counter()
    by_asset = collections.Counter()
    bad_sessions = 0
    os.makedirs(OUT_ROOT, exist_ok=True)
    rows_path = os.path.join(OUT_ROOT, "mismatches.tsv")
    with open(rows_path, "w") as fh:
        fh.write("# PORT_M1_SPEC.md §1.3 field-exact differential\n")
        fh.write("asset\ttrade_date\tfield\tdetail\n")
        for asset, date, bad in results:
            if not bad:
                continue
            bad_sessions += 1
            by_asset[asset] += 1
            for field, detail in bad:
                by_field[field] += 1
                fh.write("%s\t%s\t%s\t%s\n" % (asset, date, field, detail))
        for asset, date in orphans:
            bad_sessions += 1
            by_asset[asset] += 1
            by_field["_orphan"] += 1
            fh.write("%s\t%s\t_orphan\tC++ receipt has no M0 counterpart\n" % (asset, date))

    receipt = {
        "spec": "design/PORT_M1_SPEC.md §1.3 (gate A)",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "assets": assets,
        "n_sessions_compared": len(tasks),
        "n_sessions_mismatching": bad_sessions,
        "n_orphan_cpp_receipts": len(orphans),
        "mismatches_by_field": dict(sorted(by_field.items())),
        "mismatching_sessions_by_asset": dict(sorted(by_asset.items())),
        "verdict": "PASS" if bad_sessions == 0 else "FAIL",
        "mismatch_rows": rows_path,
    }
    with open(os.path.join(OUT_ROOT, "differential.receipt.json"), "w") as fh:
        json.dump(receipt, fh, indent=1, sort_keys=True)
        fh.write("\n")

    sys.stderr.write("[m1-diff] VERDICT %s: %d/%d sessions field-exact\n"
                     % (receipt["verdict"], len(tasks) - bad_sessions, len(tasks)))
    if bad_sessions:
        for field, n in by_field.most_common(20):
            sys.stderr.write("[m1-diff]   %-28s %d\n" % (field, n))
    return 0 if bad_sessions == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
