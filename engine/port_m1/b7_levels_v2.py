#!/usr/bin/python3
"""PORT M1.B — D-053 level-ledger rebuild (VWAP family) into m1/levels_v2/.

D-053 (user law, both specs amended 2026-08-13): the VWAP level family is the
VWAP LINE itself (+-0) plus +-2.0 and +-2.5 x sigma_vwap, replacing the
+-1/+-2 bands the M1.A ledger was built with.  Session and phase VWAP both;
sigma = the causal running VWAP deviation, unchanged.

METHOD: the §4 ledger builder is re-run VERBATIM (b3_levels.run) with
B3.VWAP_BANDS set to the D-053 set and B3.OUT_DIR redirected, so nothing is
reimplemented and no other family can drift.  m1/levels/ (the M1.A record,
superseded bands) is left byte-untouched; the M1.B generation lane reads
m1/levels_v2/.

Rebuilding every family rather than splicing the VWAP rows is the safe form:
VWAP levels are DYNAMIC and session-scoped (ledger key carries the session
date), so their state never crosses sessions, and the non-VWAP families are a
deterministic function of inputs that did not change.  That invariant is not
assumed - `differential()` asserts it row for row on a sample of sessions:
every non-VWAP row must be identical (id, family, price, virginity, touch
count, last test) and the VWAP band set must be exactly the D-053 one.

Run: lab/run.sh port-m1b-s1-levels -- /usr/bin/python3 engine/port_m1/b7_levels_v2.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m1_common as M
import common as C
import census_common as X
import b3_levels as B3
import b7_sane as B7

SECTION = "S1 D-053 VWAP ledger rebuild"

OUT_DIR = "levels_v2"
OLD_DIR = "levels"
BANDS_D053 = (0.0, 2.0, -2.0, 2.5, -2.5)
BANDS_SUPERSEDED = (0.0, 1.0, -1.0, 2.0, -2.0)
DIFF_SESSIONS = 12              # sampled per asset for the row differential

PARAMS = {
    "spec_section": SECTION,
    "law": "D-053: VWAP family = VWAP line + {+-2.0, +-2.5} x sigma_vwap "
           "(session and phase); superseded set {0, +-1, +-2}",
    "method": "b3_levels.run re-run verbatim with the D-053 bands into "
              "m1/levels_v2/; every other family unchanged",
    "vwap_bands": list(BANDS_D053),
    "differential": "sampled sessions: non-VWAP rows must be row-identical to "
                    "m1/levels/, VWAP rows must carry exactly the D-053 bands",
}

# ------------------------------------------------------------ differential ---
def _rows(path):
    z = np.load(path, allow_pickle=False)
    out = {}
    for i in range(int(z["level_id"].size)):
        out[str(z["level_id"][i])] = (
            str(z["level_family"][i]), float(z["level_price"][i]),
            int(z["virgin"][i]), int(z["touch_count"][i]),
            int(z["last_test_sec"][i]), int(z["last_test_outcome"][i]))
    n_touch = int(z["touches"].shape[0])
    z.close()
    return out, n_touch


def differential(assets):
    """Row-for-row: non-VWAP rows identical, VWAP rows = the D-053 band set."""
    rows = []
    for asset in assets:
        d_new = os.path.join(M.M1_ROOT, OUT_DIR, asset)
        names = sorted(n for n in os.listdir(d_new) if n.endswith(".npz"))
        step = max(1, len(names) // DIFF_SESSIONS)
        for name in names[::step][:DIFF_SESSIONS]:
            p_new = os.path.join(d_new, name)
            p_old = os.path.join(M.M1_ROOT, OLD_DIR, asset, name)
            if not os.path.exists(p_old):
                continue
            new, nt_new = _rows(p_new)
            old, nt_old = _rows(p_old)
            nv_new = {k: v for k, v in new.items() if v[0] != "VWAP"}
            nv_old = {k: v for k, v in old.items() if v[0] != "VWAP"}
            mism = sum(1 for k in set(nv_new) | set(nv_old)
                       if nv_new.get(k) != nv_old.get(k))
            bands_new = sorted(set(k for k, v in new.items() if v[0] == "VWAP"))
            missing = [k for k in bands_new
                       if not any(k.endswith("|%+g" % b) for b in BANDS_D053)]
            stale = [k for k in bands_new
                     if any(k.endswith("|%+g" % b) for b in (1.0, -1.0))]
            ok = (mism == 0 and not missing and not stale)
            rows.append([asset, name[:8], len(nv_new), mism, len(bands_new),
                         len(missing), len(stale), nt_old, nt_new,
                         "PASS" if ok else "FAIL"])
    return rows


def touch_delta(assets, out="levels_v3", ref="levels_v2"):
    """Informational: how many level touches the D-054 mask removed."""
    rows = []
    for asset in assets:
        d_new = os.path.join(M.M1_ROOT, out, asset)
        names = sorted(n for n in os.listdir(d_new) if n.endswith(".npz"))
        step = max(1, len(names) // DIFF_SESSIONS)
        for name in names[::step][:DIFF_SESSIONS]:
            p_ref = os.path.join(M.M1_ROOT, ref, asset, name)
            if not os.path.exists(p_ref):
                continue
            new, nt_new = _rows(os.path.join(d_new, name))
            old, nt_old = _rows(p_ref)
            rows.append([asset, name[:8], len(old), len(new), nt_old, nt_new,
                         (100.0 * (nt_new - nt_old) / nt_old)
                         if nt_old else float("nan")])
    return rows


def main():
    """Default: the D-053 rebuild into levels_v2 (unmasked control arm).
    With `--v3`: D-053 + the D-054 MID-SANE mask into levels_v3, which is what
    the real (masked) generation arm consumes — level touches may only be born
    on sane mids."""
    M.verify_spec_m1b()
    global OUT_DIR
    workers = int(os.environ.get("M1_WORKERS", "6"))
    v3 = "--v3" in sys.argv
    assets = [a for a in sys.argv[1:] if a in M.ASSET_ORDER] or \
        list(M.ASSET_ORDER)
    if tuple(B3.VWAP_BANDS) != BANDS_D053:
        raise RuntimeError("b3_levels.VWAP_BANDS %r is not the D-053 set %r"
                           % (B3.VWAP_BANDS, BANDS_D053))
    if v3:
        OUT_DIR = "levels_v3"
        B3.SANE_THRESHOLDS = {a: B7.load_thresholds(a) for a in assets}
        M.hb("b7 levels_v3: D-054 mask installed for %d assets" % len(assets))
    B3.OUT_DIR = OUT_DIR
    B3.run(assets, workers)
    if v3:
        rows = touch_delta(assets)
        M.write_tsv(M.out_path(OUT_DIR, "sane_touch_delta.tsv"), SECTION,
                    C.params_hash(PARAMS),
                    ["asset", "date8", "n_rows_v2", "n_rows_v3",
                     "n_touches_v2", "n_touches_v3", "touch_delta_pct"], rows,
                    spec="PORT_M1B",
                    extra=["D-054 impact on the level ledger: touches that "
                           "existed only on insane mids are gone"])
        M.hb("b7 levels_v3: %d sampled sessions compared vs levels_v2"
             % len(rows))
        return 0
    rows = differential(assets)
    M.write_tsv(M.out_path(OUT_DIR, "vwap_d053_differential.tsv"), SECTION,
                C.params_hash(PARAMS),
                ["asset", "date8", "n_non_vwap_rows", "n_non_vwap_mismatch",
                 "n_vwap_rows", "n_vwap_not_d053", "n_vwap_superseded_band",
                 "n_touches_old", "n_touches_new", "verdict"], rows,
                extra=["D-053 rebuild differential vs the M1.A ledger "
                       "(m1/levels/): everything except the VWAP family must "
                       "be row-identical"], spec="PORT_M1B")
    bad = [r for r in rows if r[-1] != "PASS"]
    M.hb("b7 levels_v2: %d differential rows, %d FAIL" % (len(rows), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
