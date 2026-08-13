#!/usr/bin/python3
"""PORT M1 — the spec's own self-assertions, measured.

§4(f) asks for exactly this: "constants asserted against that %-band at 2024
median prices, else spec defect".  §6's G3 statistic is specified "per second",
which only works if a per-second value has a non-degenerate robust scale; that
too is measured here rather than assumed.

Output: m1/assertions.tsv (every number in the defect list lands here).
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m1_common as M
import common as C
import census_common as X
import b3_levels as B3

SECTION = "§4(f) / §6 spec self-assertions"
BAND_LO, BAND_HI = 0.3, 1.0     # §4(f) "nearest ~0.3-1% of price"
ASSERT_YEAR = 2024              # §4(f) "at 2024 median prices"
HALFHOUR = 1800

PARAMS = {"spec_section": SECTION, "band_pct": [BAND_LO, BAND_HI],
          "price_year": ASSERT_YEAR,
          "g3_probe": "one 2024 session per asset; fraction of half-hour bins "
                      "whose robust scale (MAD) is exactly zero"}


def median_price(asset, year=ASSERT_YEAR):
    px = []
    for d, p in X.session_paths(asset, M.M0_ROOT):
        if d.year != year:
            continue
        z = np.load(p, allow_pickle=False)
        m = z["g0_mid"]
        st = z["g0_state"]
        z.close()
        v = m[st[:len(m)] == C.ST_TWO_SIDED]
        if v.size:
            px.append(float(np.median(v)))
    return float(np.median(px)) if px else float("nan")


def mad_zero_bins(arr):
    n = 0
    for b in range(86400 // HALFHOUR):
        seg = arr[b * HALFHOUR:(b + 1) * HALFHOUR]
        if seg.size == 0:
            continue
        med = np.median(seg)
        if np.median(np.abs(seg - med)) == 0:
            n += 1
    return n


def main():
    M.verify_spec()
    rows = []
    for asset in M.ASSET_ORDER:
        med = median_price(asset)
        for g in B3.ROUND_GRIDS[asset]:
            pct = 100.0 * g / med
            ok = BAND_LO <= pct <= BAND_HI
            rows.append(["ROUND_GRID_BAND", asset, "%g" % g, med, pct,
                         BAND_LO, BAND_HI, bool(ok),
                         "IN BAND" if ok else "SPEC DEFECT: outside the "
                         "%.1f-%.1f%% band §4(f) asserts" % (BAND_LO, BAND_HI)])
    for asset in M.ASSET_ORDER:
        sess = [x for x in X.session_paths(asset, M.M0_ROOT)
                if x[0].year == ASSERT_YEAR]
        d, p = sess[len(sess) // 3]
        z = np.load(p, allow_pickle=False)
        ts = z["trades_sec"].astype(np.int64)
        z.close()
        cnt = np.zeros(86400, dtype=np.int64)
        s = ts[(ts >= 0) & (ts < 86400)]
        np.add.at(cnt, s, 1)
        r60 = np.convolve(cnt, np.ones(60, dtype=np.int64))[:86400]
        z1 = mad_zero_bins(cnt)
        z60 = mad_zero_bins(r60)
        nb = 86400 // HALFHOUR
        rows.append(["G3_MAD_DEGENERACY", asset, d.isoformat(), z1, z60, nb,
                     None, bool(z1 <= nb // 2),
                     "SPEC DEFECT: %d/%d half-hour bins have MAD == 0 for the "
                     "PER-SECOND trade count (z-score undefined); the 60s "
                     "window has %d/%d" % (z1, nb, z60, nb)])
    M.write_tsv(M.out_path("assertions.tsv"), SECTION, C.params_hash(PARAMS),
                ["assertion", "asset", "subject", "value_a", "value_b",
                 "band_lo", "band_hi", "ok", "note"], rows,
                extra=["§4(f) asserts its own round-number constants against a "
                       "0.3-1%% band at 2024 median prices"])
    for r in rows:
        print("\t".join(str(x) for x in r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
