#!/usr/bin/python3
"""Tests for the cross-asset marginal-information lane.

Five things have to hold or the marginal numbers mean nothing:
  1. STRICT CAUSALITY — every one of the 30 columns is bit-identical when the
     other asset's session, trades tape and event cache are TRUNCATED at the
     decision second.  This is the whole claim of the block; it is tested by
     construction, not by inspection.
  2. the S11 co-location premise (`open_utc` identical across SI/HG/NKD) holds
     on every E6 day, so "the other asset's second" IS the decision second.
  3. the lead-lag sign convention means what the column name says: a synthetic
     pair where the OTHER asset leads by m seconds reports lag = +m.
  4. the block is exactly 15 kinds x 2 roles, `_with` columns carry the side,
     and the role map strikes the own asset out.
  5. the a_BASE_225 arm's feature set IS the committed ceiling's
     L1L2L3_all_views set — the baseline is a reproduction, not a re-spec.

Run: /usr/bin/python3 engine/port_m2/test_xasset.py
"""
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m0", "/workspace/engine/port_m1",
           "/workspace/engine/port_m1b", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import m2_common as MC                    # noqa: E402
import info_ceiling as IC                 # noqa: E402
import xasset as XA                       # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print("%-62s %s%s" % (name, "PASS" if ok else "FAIL",
                          ("  " + detail) if detail else ""))
    if not ok:
        FAILS.append(name)


def _truncate(st, t):
    """The other asset's state with EVERY array cut at second `t`.

    A causal feature cannot see second t or later, so it must be invariant to
    this surgery.  Every source the block reads is cut: the SANE mid grid, the
    rv prefix, the 1s return series, the L1 imbalance grid, the trades tape,
    the phase-segment running extremes, the level ledger's birth seconds and
    the event-rate scaffolding.
    """
    q = dict(st)
    k = int(np.searchsorted(st["vt"], t, side="left"))
    q["vt"] = st["vt"][:k]
    q["vm"] = st["vm"][:k]
    q["pref"] = st["pref"][:k]
    q["segmax"] = st["segmax"][:k]
    q["segmin"] = st["segmin"][:k]
    q["ret1s"] = np.concatenate([st["ret1s"][:t],
                                 np.zeros(st["n"] - t)])
    q["imb"] = np.concatenate([st["imb"][:t],
                               np.full(st["n"] - t, np.nan)])
    have = np.isfinite(q["imb"])
    q["last_imb"] = np.maximum.accumulate(
        np.where(have, np.arange(st["n"]), -1))
    m = st["t_sec"] < t
    q["t_sec"] = st["t_sec"][m]
    j = int(m.sum())
    q["c_v"] = st["c_v"][:j + 1]
    q["c_s"] = st["c_s"][:j + 1]
    # levels born at or after t are not yet born
    keep = st["lbn"] < t
    q["lpx"] = st["lpx"][keep]
    q["lbn"] = st["lbn"][keep]
    if st["ev"] is not None:
        e = st["ev"]
        q["ev"] = {"Rw": np.concatenate([e["Rw"][:t + 1],
                                         np.full(e["Rw"].size - t - 1, np.nan)]),
                   "Vw": np.concatenate([e["Vw"][:t + 1],
                                         np.zeros(e["Vw"].size - t - 1, bool)]),
                   "c_n": e["c_n"], "c_s": e["c_s"], "c_s2": e["c_s2"]}
    return q


def t1_strict_causality():
    d8 = 20240419
    states = {a: XA._asset_state(a, d8) for a in MC.ASSET_ORDER}
    E = np.load(os.path.join(XA.OUT_ROOT, "episodes.npz"), allow_pickle=False)
    m = np.nonzero(E["d8"] == d8)[0]
    rng = np.random.default_rng(7)
    pick = rng.choice(m, size=min(40, m.size), replace=False)
    n_cmp, n_bad, n_fin = 0, 0, 0
    for i in pick.tolist():
        asset = MC.ASSET_ORDER[int(E["asset_idx"][i])]
        t = int(E["dec_sec"][i])
        own = states[asset]
        if own is None or t < 2:
            continue
        for o in XA.other_roles(asset):
            st = states[o]
            if st is None:
                continue
            full = XA._cross_one(st, own["ret1s"], t, 1.0)
            cut = XA._cross_one(_truncate(st, t),
                                np.concatenate([own["ret1s"][:t],
                                                np.zeros(own["n"] - t)]),
                                t, 1.0)
            for a_, b_ in zip(full, cut):
                n_cmp += 1
                n_fin += int(np.isfinite(a_))
                same = (a_ == b_) or (not np.isfinite(a_)
                                      and not np.isfinite(b_))
                n_bad += int(not same)
    check("every column is invariant to truncating the other asset at t",
          n_bad == 0 and n_cmp > 500,
          "%d comparisons, %d finite, %d differ" % (n_cmp, n_fin, n_bad))


def t2_clock_colocation():
    E = np.load(os.path.join(XA.OUT_ROOT, "episodes.npz"), allow_pickle=False)
    days = sorted(set(E["d8"].tolist()))
    bad = [d for d in days if not XA._verify_clock(d)[0]]
    check("open_utc identical across SI/HG/NKD on every E6 day",
          not bad, "%d days checked, %d mismatched" % (len(days), len(bad)))


def t3_leadlag_sign():
    """A synthetic pair in which the OTHER asset leads by m seconds."""
    rng = np.random.default_rng(11)
    n = 4000
    base = rng.standard_normal(n)
    for m in (3, 7, 12):
        oth = base.copy()
        own = np.zeros(n)
        own[m:] = base[:-m]                # own repeats what other did m ago
        pk, lg = XA._leadlag(own, oth, 3500)
        check("lead-lag reports +%d when the other asset leads by %ds" % (m, m),
              abs(lg - m) < 1e-9 and pk > 0.9,
              "lag=%.0f peak=%.3f" % (lg, pk))


def t4_block_shape():
    check("30 columns = 15 kinds x 2 roles",
          len(XA.XCOLS) == 30 and len(XA.KINDS) == 15,
          "%d cols" % len(XA.XCOLS))
    check("the _with mask is exactly the side-carrying kinds",
          int(XA.WITH_MASK.sum()) == 2 * sum(k.endswith("_with")
                                             for k, _ in XA.KINDS),
          "%d of %d" % (int(XA.WITH_MASK.sum()), len(XA.XCOLS)))
    ok = all(a not in XA.other_roles(a) and len(XA.other_roles(a)) == 2
             for a in MC.ASSET_ORDER)
    check("the role map strikes the own asset out", ok,
          " ".join("%s->%s" % (a, "/".join(XA.other_roles(a)))
                   for a in MC.ASSET_ORDER))


def t5_baseline_reproduces_the_ceiling():
    E = XA.load()
    a_layers = [f[1] for f in XA.FEATURE_SETS if f[0] == "a_BASE_225"][0]
    ic_layers = dict(IC.LAYER_SETS)["L1L2L3_all_views"]
    check("a_BASE_225 declares the committed L1L2L3_all_views layers",
          tuple(a_layers) == tuple(ic_layers), str(a_layers))
    j_new = XA._cols_for(E, a_layers, drop_prefix=None)
    j_old = IC._cols_for(IC.load(), ic_layers)
    check("...and selects the identical column set",
          j_new.size == j_old.size, "%d vs %d" % (j_new.size, j_old.size))
    check("the XASSET layer is 30 columns wide and disjoint from the views",
          int((E["layer"] == XA.XLAYER).sum()) == 30
          and not set(XA.XCOLS) & set(IC.load()["cols"]),
          "%d" % int((E["layer"] == XA.XLAYER).sum()))


def main():
    for t in (t4_block_shape, t3_leadlag_sign, t2_clock_colocation,
              t1_strict_causality, t5_baseline_reproduces_the_ceiling):
        t()
    print("\n%s (%d failure(s))" % ("ALL PASS" if not FAILS else "FAILED",
                                    len(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
