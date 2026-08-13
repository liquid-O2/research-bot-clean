#!/usr/bin/python3
"""PORT M1.B S1.1 — OR_EXT level-ledger rebuild into m1/levels_v4/.

CC-M1-6.1 (BINDING): the H/L census adopted OPENING-RANGE EXTENSION levels in
six pre-registered cells — SI OR30 {TOKYO, LONDON, NY} + OR60 {TOKYO, LONDON},
NKD OR30 {LONDON}, HG none (its marginals missed the 3pp bar).  The sequencing
ruling parks the adoption in a small S1.1 prototype pass: OR_EXT enters the
LEDGER as a first-class level family, so G2-REJECT / G2-RECLAIM fire at those
prices exactly like any other kept level, and the C++ inherits it in S2.1.

METHOD (the b7_levels_v2 pattern, unchanged): `b3_levels.run` is re-run VERBATIM
with B3.OREXT_CELLS set, B3.SANE_THRESHOLDS installed (D-054) and B3.OUT_DIR
redirected, so no other family can drift and nothing is re-implemented.
m1/levels_v3/ (the S1-v2 record the frozen generation oracle stands on) is left
byte-untouched.

DIFFERENTIAL (asserted, not assumed) over EVERY session, not a sample: every
non-OR_EXT ledger row must be identical to levels_v3 (id, family, price,
virginity, touch count, last test second and outcome), and the OR_EXT rows must
carry exactly the adopted cells x the censused k ladder x both sides.  The
level state machine is per level, so adding a family may not perturb any other
— that is the invariant, and this is where it is measured.

Run: lab/run.sh port-m1-s11-levels -- /usr/bin/python3 engine/port_m1/b10_levels_v4.py
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

SECTION = "S1.1 OR_EXT ledger (CC-M1-6.1)"

OUT_DIR = "levels_v4"
REF_DIR = "levels_v3"

# CC-M1-6.1(1) verbatim.  HG adopted NO cell: its 2.2-2.8pp marginals missed the
# 3pp bar (revisit hook: the 2025 lifts rose).  The empty tuple is the adoption,
# not an omission — the family is simply never built for HG.
OREXT_ADOPTED = {
    "SI": (("TOKYO", 30), ("LONDON", 30), ("NY", 30),
           ("TOKYO", 60), ("LONDON", 60)),
    "NKD": (("LONDON", 30),),
    "HG": (),
}

PARAMS = {
    "spec_section": SECTION,
    "law": "CC-M1-6.1: OR_EXT adopted in six cells (SI OR30 TOKYO/LONDON/NY + "
           "OR60 TOKYO/LONDON; NKD OR30 LONDON; HG none)",
    "adopted_cells": {a: ["%s|OR%d" % (s, m) for (s, m) in v]
                      for a, v in sorted(OREXT_ADOPTED.items())},
    "construction": "OR = [first SANE second of the segment, +minutes x 60); "
                    "levels OR_H + k x OR_range and OR_L - k x OR_range, "
                    "k in %s (the censused ladder); active from the second the "
                    "range closes" % (list(B3.OREXT_K),),
    "scope": "SEGMENT-scoped (a level exists only inside its own phase) and "
             "SESSION-scoped (identity, virginity and touch count never cross "
             "sessions)",
    "state_machine": "the §4 arm/touch/outcome machine unchanged",
    "mask": "D-054 SANE seconds (b7_sane), as levels_v3",
    "vwap_bands": list(B3.VWAP_BANDS),
    "differential": "EVERY session: non-OR_EXT rows must be identical to "
                    "m1/%s" % REF_DIR,
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
    fam = z["level_family"]
    n_or = int(np.sum(fam == B3.OREXT_FAMILY))
    tou = z["touches"]
    n_or_touch = 0
    if tou.size:
        rows = tou[:, 1].astype(np.int64)
        n_or_touch = int(np.sum(fam[rows] == B3.OREXT_FAMILY))
    z.close()
    return out, n_touch, n_or, n_or_touch


def _same(a, b):
    """Row equality with NaN == NaN.

    DYNAMIC levels (VWAP, developing POC) store the series value AT their
    creation second, which is legitimately NaN before the first trade of the
    scope; plain tuple comparison calls those rows different from themselves.
    (b7_levels_v2._rows has the same latent hole — its 12-session sample never
    hit a NaN-priced VWAP row.  Returned as a defect, fixed here.)
    """
    if a is None or b is None:
        return a is b
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if isinstance(x, float) and isinstance(y, float):
            if np.isnan(x) and np.isnan(y):
                continue
        if x != y:
            return False
    return True


def expected_orext_keys(asset):
    out = set()
    for (seg, mn) in OREXT_ADOPTED[asset]:
        for k in B3.OREXT_K:
            for sgn in (+1, -1):
                out.add("%s|%s|OR%d|k%.1f|%+d"
                        % (B3.OREXT_FAMILY, seg, mn, k, sgn))
    return out


def differential(assets):
    """Row-for-row over every session: non-OR_EXT identical, OR_EXT well-formed."""
    rows = []
    for asset in assets:
        d_new = os.path.join(M.M1_ROOT, OUT_DIR, asset)
        exp = expected_orext_keys(asset)
        for name in sorted(n for n in os.listdir(d_new) if n.endswith(".npz")):
            p_ref = os.path.join(M.M1_ROOT, REF_DIR, asset, name)
            if not os.path.exists(p_ref):
                rows.append([asset, name[:8], 0, 0, 0, 0, 0, 0, 0, "NO_REF"])
                continue
            new, nt_new, n_or, n_or_touch = _rows(os.path.join(d_new, name))
            old, nt_old, _o1, _o2 = _rows(p_ref)
            nv_new = {k: v for k, v in new.items()
                      if v[0] != B3.OREXT_FAMILY}
            mism = sum(1 for k in set(nv_new) | set(old)
                       if not _same(nv_new.get(k), old.get(k)))
            ork = set(k for k, v in new.items() if v[0] == B3.OREXT_FAMILY)
            unexpected = len(ork - exp)
            ok = (mism == 0 and unexpected == 0
                  and (nt_new - nt_old) == n_or_touch)
            rows.append([asset, name[:8], len(nv_new), mism, n_or,
                         unexpected, nt_old, nt_new, n_or_touch,
                         "PASS" if ok else "FAIL"])
    return rows


def main():
    M.verify_spec_m1b()
    workers = int(os.environ.get("M1_WORKERS", "6"))
    assets = [a for a in sys.argv[1:] if a in M.ASSET_ORDER] or \
        list(M.ASSET_ORDER)
    if tuple(B3.VWAP_BANDS) != (0.0, 2.0, -2.0, 2.5, -2.5):
        raise RuntimeError("b3_levels.VWAP_BANDS %r is not the D-053 set"
                           % (B3.VWAP_BANDS,))
    diff_only = "--diff-only" in sys.argv
    B3.OREXT_CELLS = {a: OREXT_ADOPTED[a] for a in assets}
    B3.SANE_THRESHOLDS = {a: B7.load_thresholds(a) for a in assets}
    B3.OUT_DIR = OUT_DIR
    B3.PARAMS = dict(B3.PARAMS, families=list(B3.FAMILIES)
                     + [B3.OREXT_FAMILY],
                     orext=PARAMS["adopted_cells"],
                     orext_construction=PARAMS["construction"],
                     orext_scope=PARAMS["scope"])
    M.hb("b10 levels_v4: OR_EXT cells %r, D-054 mask installed%s"
         % (PARAMS["adopted_cells"], " (DIFF-ONLY)" if diff_only else ""))
    if not diff_only:
        B3.run(assets, workers)

    rows = differential(assets)
    M.write_tsv(M.out_path(OUT_DIR, "orext_differential.tsv"), SECTION,
                C.params_hash(PARAMS),
                ["asset", "date8", "n_non_orext_rows", "n_non_orext_mismatch",
                 "n_orext_rows", "n_orext_unexpected_keys", "n_touches_v3",
                 "n_touches_v4", "n_orext_touches", "verdict"], rows,
                spec="PORT_M1B",
                extra=["S1.1 differential vs m1/%s over EVERY session: adding "
                       "the OR_EXT family may not perturb any other level, and "
                       "every new touch must belong to OR_EXT" % REF_DIR])
    bad = [r for r in rows if r[-1] != "PASS"]
    tot_or = sum(r[4] for r in rows)
    tot_ot = sum(r[8] for r in rows)
    M.hb("b10 levels_v4: %d sessions differenced, %d FAIL; %d OR_EXT levels, "
         "%d OR_EXT touches" % (len(rows), len(bad), tot_or, tot_ot))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
