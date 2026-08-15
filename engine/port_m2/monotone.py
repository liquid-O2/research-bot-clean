#!/usr/bin/python3
"""PORT M2 — MONOTONE CONSTRAINTS FROM CENSUSED FACTS.

THE IDEA (coordinator, user-priority): the sufficiency instrument sized the
gap as **expressible-but-not-learnable** ($1,540-2,590/session, 55-75% of the
oracle) against only $390-490 of missing information.  That is a
GENERALIZATION problem, and this program already owns a large body of MEASURED,
Holm-tested directional knowledge that the ranker is currently free to ignore or
invert whenever an era's noise rewards it.

`monotone_constraints` converts that knowledge into a prior the model CANNOT
unlearn: if a feature's relationship to value is known to be monotone in a
direction, the trees may only fit it that way.  Era noise can no longer buy a
sign flip.

TWO SOURCES, both ours, both receipted:

  1. THE NAMED CENSUS FACTS.  `CREATOR_CENSUS_MAIN.tsv`, 38 Holm-significant
     detectors with measured lift: concentrators (PASSIVE_MOVE 1.838,
     TAPE_SPIKE 1.462, EXTREME_ABSORPTION 1.458, OFM 1.413, AGG_* 1.31-1.36,
     TWO_STAGE 1.355) and vetoes (TAPE_DEAD 0.607 -- the strongest single object
     in the corpus -- DIV_BOX_350 0.653, REFILL_AREA_HELD 0.856,
     WICK_ABSORBED_OPP 0.894, MICROBALANCE_BREAK 0.920).  These are FAMILY-level
     facts: flow/effort activity concentrates value, dead tape destroys it.
     They are mapped onto matrix columns by family, and every mapping is written
     into the artifact so it can be argued with.

  2. THE STABILITY RECEIPT (the causal half).  A column earns a constraint only
     if its within-cell rank correlation with the certificate dollars carries
     the SAME SIGN in EVERY training era of that fold, and its mean |rho|
     clears a floor.  Computed on TRAINING ERAS ONLY, per fold, so the
     constraint vector is causal for every era it is applied to.  A sign that is
     not stable in the past is not imposed on the future.

The intersection is deliberate: family knowledge says WHICH DIRECTION should
hold, the stability receipt says WHETHER IT ACTUALLY HELD.  A column is
constrained only where both agree, or where the stability receipt alone is
overwhelming and the censuses are silent.

Artifact: `provenance/port_m2/MONOTONE_CONSTRAINTS.tsv` (per era, per column,
with the sign, its source, the per-era rho agreement, and the reason).
"""
import argparse
import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m2/seqtest", "/workspace/engine/port_m0",
           "/workspace/engine/port_m1", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import newobj as N                        # noqa: E402
import newobj_arms as NA                  # noqa: E402
import rank_atlas as RA                   # noqa: E402
import champ_floor as CF                  # noqa: E402
import st_common as SC                    # noqa: E402

RHO_FLOOR = 0.010          # a stable-but-invisible sign is not worth a constraint
PROV = N.PROV

# FAMILY PRIORS from the censuses.  Substring -> expected sign of the
# relationship with certificate dollars.  Every entry cites the measurement.
FAMILY_PRIOR = [
    # capacity / room to travel: SEAT_LIVE replicated 1.31-1.69x across 8 eras
    ("room_with", +1, "capacity: SEAT_LIVE 1.31-1.69x, 8/8 eras"),
    ("runway", +1, "runway: room-to-travel is the capacity channel"),
    ("unspent", +1, "capacity: unspent session dollars = room left"),
    # flow / effort concentrators (creator census, Holm-significant)
    ("f30m_vol", +1, "TAPE_SPIKE 1.462 / AGG_PRINT_60 1.306 (flow concentrates)"),
    ("fuel_share", +1, "PASSIVE_MOVE 1.838 / OFM 1.413 (effort-vs-result)"),
    ("ofm", +1, "OFM 1.413 HOLM_SIGNIFICANT"),
    ("absorb", +1, "EXTREME_ABSORPTION 1.458 HOLM_SIGNIFICANT"),
    # the strongest veto in the corpus: dead tape destroys value
    ("dead", -1, "TAPE_DEAD 0.607 -- strongest single object in the corpus"),
    ("stale", -1, "TAPE_DEAD family: staleness is the veto direction"),
    # cost is always adverse
    ("cost", -1, "cost is mechanically subtracted from the certificate"),
    ("spread", -1, "wider spread = worse fill, mechanical"),
]


def family_sign(name):
    n = str(name).lower()
    for sub, sgn, why in FAMILY_PRIOR:
        if sub in n:
            return sgn, why
    return 0, ""


def _within_cell_rho(D, rows, x, v):
    """Mean within-cell Spearman of one column against the certificate."""
    ro, blocks = N.cell_blocks(D, rows)
    xs, vs = x[ro], v[ro]
    out = []
    for a, b in blocks:
        if b - a < 5:
            continue
        xi, vi = xs[a:b], vs[a:b]
        m = np.isfinite(xi) & np.isfinite(vi)
        if m.sum() < 5 or np.all(xi[m] == xi[m][0]):
            continue
        rx = np.argsort(np.argsort(xi[m])).astype(float)
        rv = np.argsort(np.argsort(vi[m])).astype(float)
        sx, sv = rx.std(), rv.std()
        if sx <= 0 or sv <= 0:
            continue
        out.append(float(((rx - rx.mean()) * (rv - rv.mean())).mean()
                         / (sx * sv)))
    return float(np.mean(out)) if out else 0.0


def build(eras=N.DEV_ERAS, sample_cells=1200):
    """Per-era constraint vectors + the artifact."""
    D, _P = CF.boot()
    cols, names = NA.feat_cols(D)
    X = D["X"][:, cols]
    v = D["cert_close_usd"].astype(np.float64)
    rows_out, vectors = [], {}
    for era in eras:
        tr_eras = [e for e in ("PRE_E1", "E1", "E2", "E3", "E4", "E5", "E6",
                               "E7") if e != "PRE_E1"
                   and SC.ERA_IDX.get(e, 99) < SC.ERA_IDX[era]]
        per_era_rho = {}
        for te in tr_eras:
            r = N.deployable(D, N.era_rows(D, te))
            if r.size > sample_cells * 120:
                r = r[:: max(1, r.size // (sample_cells * 120))]
            per_era_rho[te] = np.array(
                [_within_cell_rho(D, r, X[:, j], v) for j in range(X.shape[1])])
        if not per_era_rho:
            vectors[era] = [0] * X.shape[1]
            continue
        M = np.vstack([per_era_rho[te] for te in tr_eras])
        mean_rho = M.mean(axis=0)
        agree = np.all(np.sign(M) == np.sign(mean_rho)[None, :], axis=0)
        vec = []
        for j, nm in enumerate(names):
            fs, why = family_sign(nm)
            stable = bool(agree[j] and abs(mean_rho[j]) >= RHO_FLOOR)
            sgn, src = 0, ""
            if stable and fs != 0 and np.sign(mean_rho[j]) == fs:
                sgn, src = fs, "CENSUS+STABLE"
            elif stable and fs == 0:
                sgn, src = int(np.sign(mean_rho[j])), "STABLE_ONLY"
            elif fs != 0 and stable and np.sign(mean_rho[j]) != fs:
                sgn, src = 0, "CONFLICT_census_vs_measured"
            vec.append(int(sgn))
            if sgn != 0 or src:
                rows_out.append([era, nm, int(sgn), src,
                                 N._r(float(mean_rho[j]), 5),
                                 int(M.shape[0]), bool(agree[j]), why])
        vectors[era] = vec
        N.hb("monotone %s: %d/%d columns constrained (%d census+stable, "
             "%d stable-only)"
             % (era, sum(1 for z in vec if z != 0), len(vec),
                sum(1 for r in rows_out if r[0] == era
                    and r[3] == "CENSUS+STABLE"),
                sum(1 for r in rows_out if r[0] == era
                    and r[3] == "STABLE_ONLY")))
    N.write_tsv("MONOTONE_CONSTRAINTS.tsv",
                ["era", "feature", "sign", "source", "mean_rho_train_eras",
                 "n_train_eras", "sign_agreed_every_era", "census_reason"],
                rows_out,
                extra=["THE CONSTRAINT ARTIFACT.  A column is constrained only "
                       "where a NAMED CENSUS FACT and a MEASURED STABILITY "
                       "RECEIPT agree, or where the stability receipt is clean "
                       "and the censuses are silent.  Where they DISAGREE the "
                       "column is left FREE and the conflict is recorded "
                       "(source=CONFLICT_census_vs_measured) rather than "
                       "resolved by preference.",
                       "The stability receipt is computed on TRAINING ERAS "
                       "ONLY, per fold: the within-cell Spearman of the column "
                       "against `cert_close_usd` must carry the SAME SIGN in "
                       "every training era and its mean |rho| must clear %.3f. "
                       "A sign that was not stable in the past is not imposed "
                       "on the future." % RHO_FLOOR,
                       "Census sources: CREATOR_CENSUS_MAIN.tsv (38 "
                       "Holm-significant detectors; TAPE_DEAD 0.607 the "
                       "strongest veto, PASSIVE_MOVE 1.838 the strongest "
                       "concentrator), the SEAT_LIVE capacity replication "
                       "(1.31-1.69x, 8/8 eras), and mechanical facts (cost and "
                       "spread are subtracted)."])
    N.save_json("monotone_vectors.json", vectors)
    return vectors


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    a = ap.parse_args()
    if a.build:
        build()
    else:
        ap.print_help()
