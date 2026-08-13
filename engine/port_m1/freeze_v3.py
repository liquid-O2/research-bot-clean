#!/usr/bin/python3
"""PORT M1.B S1.1/S1.2 — freeze receipt for the enriched roster npz.

The roster npz files live under artifacts/cache (D-018: bulk never enters the
overlay or the git tree), so the FREEZE is this receipt: sha256 + shape of each
`union_roster_{ASSET}.npz` that the C++ S2.2 increment must reproduce
candidate-exact, plus the params_hash of the prototype that produced them.

Run: /usr/bin/python3 engine/port_m1/freeze_v3.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m1_common as M
import common as C
import b10_generation_v3 as G3
import b10_levels_v4 as L4

SECTION = "S1.1+S1.2 oracle freeze"


def main():
    M.verify_spec_m1b()
    phash = C.params_hash(G3.PARAMS)
    rows = []
    for asset in M.ASSET_ORDER:
        p = M.out_path(G3.OUT_DIR, "union_roster_%s.npz" % asset)
        if not os.path.exists(p):
            continue
        z = np.load(p, allow_pickle=False)
        n = int(z["date8"].size)
        nf = int(z["skel_f_t"].size)
        na = int(z["skel_a_t"].size)
        fam = z["fam_mask"]
        lvl = z["level_fam_mask"]
        flg = z["flags"]
        per_fam = [int(np.sum((fam & G3.FAM_BIT[f]) != 0)) for f in G3.FAMILIES]
        n_orext = int(np.sum((lvl & (1 << (len(G3.KEPT_LEVEL_FAMILIES) - 1)))
                             != 0))
        z.close()
        rows.append([asset, os.path.relpath(p, "/workspace"),
                     C.sha256_file(p), n, nf, na, n_orext,
                     int(np.sum(flg != 0))] + per_fam)
    M.write_tsv(M.out_path(G3.OUT_DIR, "ORACLE_FREEZE.tsv"), SECTION, phash,
                ["asset", "path", "sha256", "n_candidates",
                 "n_favorable_records", "n_adverse_records",
                 "n_or_ext_born", "n_flagged"]
                + ["n_%s" % f for f in G3.FAMILIES], rows, spec="PORT_M1B",
                extra=["THE FROZEN S2.2 DIFFERENTIAL ORACLE: engine/port_m1/"
                       "b10_generation_v3.py params_hash=%s over the "
                       "m1/%s ledger" % (phash, L4.OUT_DIR),
                       "bulk npz stays under artifacts/cache (D-018); this "
                       "receipt is the freeze"])
    for r in rows:
        M.hb("freeze %s: %d candidates sha %s" % (r[0], r[3], r[2][:16]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
