#!/usr/bin/python3
"""PORT M1.B S2.2 — the DIFFERENTIAL GATE [P-M1s22].

The C++ generation engine `qr_gen` is accepted only if it reproduces the FROZEN
S1-v3 ENRICHED Python oracle CANDIDATE-EXACT over every session:

  * the same candidate ID SET, where an id is (trade date, decision second,
    side) — the roster's own dedup key;
  * the same ROW ORDER;
  * the same value in EVERY STORED FIELD of every candidate — including the
    enrichment's own columns (`fam_mask` now carries nine families,
    `level_fam_mask` seven kept level families including OR_EXT, and `flags`
    carries the CC-M1-7.2 F-D6 / FIRST_TEST-virgin bits) and the ragged
    prefix-maxima skeleton blocks.

ORACLE   engine/port_m1/b10_generation_v3.py at the freeze commit bec58a9,
         whose committed output is
         artifacts/cache/port/m1/generation_v3/union_roster_{ASSET}.npz
FREEZE   .../generation_v3/ORACLE_FREEZE.tsv pins the sha256 of each npz. THE
         SHA IS VERIFIED BEFORE ANY COMPARISON: a differential against an
         oracle that has drifted since the freeze proves nothing, and "the
         receipt said so" is not a check (D-010).
ENGINE   artifacts/cache/port/m1/gen_cpp/roster_v3/{ASSET}_{YYYYMM}.{bin,json}

Shard offsets (`f_off`, `a_off`) are LOCAL to a month shard, exactly as the
Python roster's own month shards were before `_merge_shards` rebased them; this
comparator rebases them the same way while concatenating, so the comparison is
against the global offsets the oracle stores.

COMPARISON RULE: exact equality, with NaN == NaN (both are "no observation")
and -0.0 == 0.0 (the S3 negative-zero finding: qr_skel normalises the sign of
zero, the m0 emitter does not; every arithmetic comparison in the program calls
them equal, so a byte comparison here would be measuring the normalisation, not
the generation).

usage: compare_gen.py [--roster SUBDIR] [ASSET ...]
"""
import glob
import hashlib
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import binpack  # noqa: E402

M1 = "/workspace/artifacts/cache/port/m1"
PY_DIR = os.path.join(M1, "generation_v3")
FREEZE = os.path.join(PY_DIR, "ORACLE_FREEZE.tsv")
CPP_SUBDIR = "roster_v3"
ASSETS = ("SI", "HG", "NKD")

# Every field the oracle stores for a candidate (c_c_roster.ROSTER_KEYS + the
# family/level/flag tags), plus the ragged skeleton arrays compared separately.
FIELDS = ("date8", "side", "rung_mask", "conf_sec", "dec_sec", "phase_conf",
          "phase_dec", "entry_mid", "spread_at_decision", "atr14_usd",
          "dom_share", "iid", "mfe_unwalled", "mfe_argmax_sec",
          "mae_before_argmax", "f_h30", "f_h60", "f_h120", "f_phase_close",
          "f_sess_close", "phase_close_sec", "sess_close_sec", "f_len",
          "a_len", "fam_mask", "level_fam_mask", "flags")
OFFSETS = ("f_off", "a_off")
RECORDS = ("skel_f_t", "skel_f_v", "skel_a_t", "skel_a_v")


def frozen_shas(path=FREEZE):
    """{asset: sha256} from the freeze receipt."""
    cols, out = None, {}
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            r = dict(zip(cols, f))
            out[r["asset"]] = r["sha256"]
    return out


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def load_cpp(asset, cpp_dir):
    """Concatenate the month shards, rebasing the ragged-array offsets."""
    stems = sorted(s[:-5] for s in glob.glob(os.path.join(cpp_dir, "%s_*.json" % asset))
                   if not s.endswith("_ledger.json"))
    if not stems:
        raise SystemExit("no C++ shards for %s under %s" % (asset, cpp_dir))
    cols, fbase, abase = {}, 0, 0
    parts = {}
    for stem in stems:
        side, arr = binpack.read(stem, "QRGEN1")
        # CC-M1-2 addendum: the params_hash is computed NATIVELY in each
        # language over the same canonical JSON. Recomputing it here is what
        # makes "natively" checkable rather than asserted.
        got = hashlib.sha256(side["params_json"].encode("utf-8")).hexdigest()
        if got != side["params_hash"]:
            raise SystemExit("%s: params_hash %s != sha256(params_json) %s"
                             % (stem, side["params_hash"], got))
        for k, v in arr.items():
            if k == "f_off":
                v = v + fbase
            elif k == "a_off":
                v = v + abase
            parts.setdefault(k, []).append(np.asarray(v))
        fbase += int(arr["skel_f_t"].size)
        abase += int(arr["skel_a_t"].size)
    for k, vs in parts.items():
        cols[k] = np.concatenate(vs) if vs else np.array([])
    cols["n_shards"] = len(stems)
    return cols


def eq(a, b):
    """Element-wise equality with NaN == NaN (and -0.0 == 0.0 by ==)."""
    a = np.asarray(a)
    b = np.asarray(b)
    if a.shape != b.shape:
        return None
    if a.dtype.kind == "f" or b.dtype.kind == "f":
        a = a.astype(np.float64)
        b = b.astype(np.float64)
        return (a == b) | (np.isnan(a) & np.isnan(b))
    return a.astype(np.int64) == b.astype(np.int64)


def ids_of(r):
    return np.stack([r["date8"].astype(np.int64), r["dec_sec"].astype(np.int64),
                     r["side"].astype(np.int64)], axis=1)


def compare(asset, cpp_dir, shas):
    out = []
    ok = True

    # ---- THE FREEZE CHECK, before anything is compared ---------------------
    path = os.path.join(PY_DIR, "union_roster_%s.npz" % asset)
    want = shas.get(asset)
    got = sha256_of(path)
    out.append(["%s oracle_sha256" % asset, want[:16] if want else "MISSING",
                got[:16], "", "", "PASS" if want == got else "FAIL"])
    if want != got:
        return False, out

    z = np.load(path, allow_pickle=False)
    py = {k: z[k] for k in z.files}
    z.close()
    cpp = load_cpp(asset, cpp_dir)
    n_py, n_cpp = int(py["date8"].size), int(cpp["date8"].size)

    # ---- the ID SET (the roster's own dedup key) ---------------------------
    a = set(map(tuple, ids_of(py).tolist()))
    b = set(map(tuple, ids_of(cpp).tolist()))
    only_py, only_cpp = a - b, b - a
    out.append(["%s ids" % asset, n_py, n_cpp, len(only_py), len(only_cpp),
                "PASS" if (not only_py and not only_cpp and n_py == n_cpp) else "FAIL"])
    if only_py or only_cpp:
        ok = False
        for t in sorted(only_py)[:5]:
            out.append(["  ONLY-IN-ORACLE", t[0], t[1], t[2], "", ""])
        for t in sorted(only_cpp)[:5]:
            out.append(["  ONLY-IN-ENGINE", t[0], t[1], t[2], "", ""])
        return ok, out

    # ---- ROW ORDER: the oracle emits (date, dec_sec, side); so must we ------
    if not np.array_equal(ids_of(py), ids_of(cpp)):
        out.append(["%s row_order" % asset, "", "", "", "", "FAIL"])
        return False, out

    # ---- every stored field ------------------------------------------------
    for f in FIELDS + OFFSETS:
        if f not in cpp:
            out.append(["%s.%s" % (asset, f), "", "", "", "MISSING", "FAIL"])
            ok = False
            continue
        m = eq(py[f], cpp[f])
        if m is None:
            out.append(["%s.%s" % (asset, f), py[f].size, cpp[f].size, "", "SHAPE", "FAIL"])
            ok = False
            continue
        bad = int((~m).sum())
        out.append(["%s.%s" % (asset, f), int(m.size), bad, "", "",
                    "PASS" if bad == 0 else "FAIL"])
        if bad:
            ok = False
            w = np.nonzero(~m)[0][:3]
            for i in w.tolist():
                out.append(["  first_mismatch", int(py["date8"][i]),
                            int(py["dec_sec"][i]), repr(py[f][i]), repr(cpp[f][i]), ""])

    # ---- the ragged skeleton blocks ---------------------------------------
    for f in RECORDS:
        m = eq(py[f], cpp[f])
        if m is None:
            out.append(["%s.%s" % (asset, f), int(py[f].size), int(cpp[f].size), "",
                        "SHAPE", "FAIL"])
            ok = False
            continue
        bad = int((~m).sum())
        out.append(["%s.%s" % (asset, f), int(m.size), bad, "", "",
                    "PASS" if bad == 0 else "FAIL"])
        if bad:
            ok = False
    return ok, out


def main():
    argv = list(sys.argv[1:])
    subdir = CPP_SUBDIR
    if "--roster" in argv:
        i = argv.index("--roster")
        subdir = argv[i + 1]
        del argv[i:i + 2]
    cpp_dir = os.path.join(M1, "gen_cpp", subdir)
    assets = [a for a in argv if a in ASSETS] or list(ASSETS)
    shas = frozen_shas()
    rows, all_ok = [], True
    for asset in assets:
        ok, out = compare(asset, cpp_dir, shas)
        all_ok = all_ok and ok
        rows.extend(out)
    w = max(len(str(r[0])) for r in rows)
    for r in rows:
        print("%-*s  %12s %12s %8s %-22s %s" % (w, r[0], r[1], r[2], r[3], r[4], r[5]))
    print("DIFFERENTIAL %s" % ("PASS" if all_ok else "FAIL"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
