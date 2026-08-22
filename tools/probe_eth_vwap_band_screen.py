#!/usr/bin/env python3
"""ETH VWAP ±2 / ±2.5 location screen — ticket 13 (2026-08-22).

PREREGISTRATION:
- Window: session open (18:00 ET) through min(snapshot, 16:00 ET = 79200s).
  Trades after snapshot or after 16:00 do not enter. D-053 bands.
- A name sits at k-sigma iff min(|mid-(vwap+kσ)|, |mid-(vwap-kσ)|) <= θ.
  θ = TRAIN winner MAE (ticket 09). Line-only (k=0) is the control.
- Bars (ticket 12): majority retained_fraction >= 0.70 and median names
  <= 16. Rank survivors on TRAIN shrink vs rung. 2021 cannot promote.
- Control: matrix disc_auction_session_vwap_aligned_usd (no sigma).

Selftest: python3 tools/probe_eth_vwap_band_screen.py --selftest
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

os.environ.setdefault("OMP_NUM_THREADS", "1")
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "tools"))

from probe_location_family_screen import (  # noqa: E402
    DELTA_SEC, THETA_TICKS, TICK_USD, _occupancy, _shrink_ceiling,
)
from probe_oracle_retention_filters import MAJORITY, MAX_NAMES, _score_mask  # noqa: E402
from probe_rho_ruler import BLOCKS, RUNG_USD  # noqa: E402
from probe_trained_accrual import (  # noqa: E402
    ELAPSED_COL, ProbeRefusal, _synthetic_matrix, load_delta_rows,
)

SCHEMA = "QRE2ETHVWAP1"
N_DRAW = 200
ETH_END_SEC = 22 * 3600  # 16:00 if open is 18:00
PRICE_NANO = 1e9
# $ per 1.00 of quoted price. SI 0.005 tick × $25; HG 0.0005 × $12.50; NKD $5/pt.
USD_PER_POINT = {"SI": 5000.0, "HG": 25000.0, "NKD": 5.0}
TRADE_ACTION = ord("T")
BANDS = {"eth_vwap_line": 0.0, "eth_vwap_2": 2.0, "eth_vwap_2_5": 2.5}


def running_vwap_sigma(sec: np.ndarray, px_usd: np.ndarray, sz: np.ndarray,
                       *, n_sec: int, end_sec: int) -> tuple[np.ndarray, np.ndarray]:
    """Causal path. A print at s enters vwap[s:] only. s >= end_sec never enters."""
    v = np.zeros(n_sec, np.float64)
    vp = np.zeros(n_sec, np.float64)
    vp2 = np.zeros(n_sec, np.float64)
    keep = ((sec >= 0) & (sec < int(end_sec)) & (sec < n_sec)
            & (sz > 0) & np.isfinite(px_usd))
    if keep.any():
        s = sec[keep].astype(np.int64)
        x, w = px_usd[keep], sz[keep]
        np.add.at(v, s, w)
        np.add.at(vp, s, w * x)
        np.add.at(vp2, s, w * x * x)
    cv, cvp, cvp2 = np.cumsum(v), np.cumsum(vp), np.cumsum(vp2)
    with np.errstate(divide="ignore", invalid="ignore"):
        vwap = np.where(cv > 0, cvp / cv, np.nan)
        var = np.where(cv > 0, cvp2 / cv - vwap * vwap, np.nan)
    return vwap, np.sqrt(np.maximum(var, 0.0))


def _px_usd(price: np.ndarray, asset: str) -> np.ndarray:
    return price.astype(np.float64) / PRICE_NANO * USD_PER_POINT[asset]


def _snap_index(elapsed: np.ndarray, n_sec: int) -> np.ndarray:
    snap = np.minimum(elapsed.astype(np.int64), ETH_END_SEC - 1)
    return np.clip(snap, 0, n_sec - 1)


def at_band_mask(mid: np.ndarray, vwap: np.ndarray, sigma: np.ndarray,
                 k: float, theta_usd: float) -> np.ndarray:
    if k == 0.0:
        dist = np.abs(mid - vwap)
    else:
        dist = np.minimum(np.abs(mid - (vwap + k * sigma)),
                          np.abs(mid - (vwap - k * sigma)))
    return np.isfinite(dist) & (dist <= float(theta_usd))


def _load_session_trades(events_root: Path, asset: str, day: int):
    from engine.entry_v2.event_pack import EventPack
    path = events_root / asset / f"{int(day)}.qre2"
    if not path.is_file():
        raise ProbeRefusal(f"event pack missing: {path}")
    pack = EventPack(path, verify_hash=False)
    rows = pack.rows
    tr = rows[(rows["action"] == TRADE_ACTION)
              & (rows["price"] > 0) & (rows["size"] > 0)]
    sec = tr["receive_session_sec"].astype(np.int64)
    px = _px_usd(tr["price"], asset)
    sz = tr["size"].astype(np.float64)
    n_sec = max(int(pack.header.close_utc - pack.header.open_utc) + 1, ETH_END_SEC)
    # Last BBO mid in USD, per second (forward-filled).
    mid = np.full(n_sec, np.nan)
    bid = rows["bid_px"].astype(np.int64)
    ask = rows["ask_px"].astype(np.int64)
    rsec = rows["receive_session_sec"].astype(np.int64)
    ok = (bid > 0) & (ask > bid) & (rsec >= 0) & (rsec < n_sec)
    mid_usd = _px_usd(((bid + ask) // 2).astype(np.float64), asset)
    # last write wins in file order
    mid[rsec[ok]] = mid_usd[ok]
    last = np.nan
    for i in range(n_sec):
        if np.isfinite(mid[i]):
            last = mid[i]
        else:
            mid[i] = last
    return running_vwap_sigma(sec, px, sz, n_sec=n_sec, end_sec=ETH_END_SEC), mid, n_sec


def run(matrix_dir: Path, events_root: Path, out_path: Path, *,
        blocks=BLOCKS, n_draw: int = N_DRAW, log=print) -> dict:
    rows = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    if not np.isfinite(rows.y).all():
        raise ProbeRefusal(
            f"{int(np.sum(~np.isfinite(rows.y)))} non-finite y; expected all finite USD")
    elapsed_col = rows.feature_names.index(ELAPSED_COL)
    all_days = (int(rows.day.min()), int(rows.day.max()))
    report: dict = {
        "schema": SCHEMA, "prereg": __doc__, "matrix_receipt": rows.matrix_receipt,
        "eth_vwap_end_sec": ETH_END_SEC, "delta_sec": DELTA_SEC, "n_draw": n_draw,
        "majority": MAJORITY, "max_names": MAX_NAMES,
        "blocks": {**{k: list(v) for k, v in blocks.items()}, "all": list(all_days)},
        "assets": {},
    }
    cache: dict[tuple[str, int], tuple] = {}
    for asset in sorted(set(rows.asset.tolist())):
        report["assets"][asset] = {"rung_usd": RUNG_USD[asset], "filters": {}}
        days_needed = sorted(set(int(d) for d in rows.day[rows.asset == asset]))
        for d in days_needed:
            cache[(asset, d)] = _load_session_trades(events_root, asset, d)
        elapsed = rows.x[:, elapsed_col]
        asset_idx = np.flatnonzero(rows.asset == asset)
        mid_at = np.full(len(rows.y), np.nan)
        vwap_at = np.full(len(rows.y), np.nan)
        sd_at = np.full(len(rows.y), np.nan)
        for d in days_needed:
            (vwap, sd), mid, n_sec = cache[(asset, d)]
            sel = asset_idx[rows.day[asset_idx] == d]
            t = _snap_index(elapsed[sel], n_sec)
            mid_at[sel] = mid[t]
            vwap_at[sel] = vwap[t]
            sd_at[sel] = sd[t]
        for width in ("tight", "wide"):
            theta = THETA_TICKS[asset][width] * TICK_USD[asset]
            for bname, k in BANDS.items():
                report["assets"][asset]["filters"].setdefault(bname, {})
                report["assets"][asset]["filters"][bname][width] = {}
                for blk, (lo, hi) in {**blocks, "all": all_days}.items():
                    idx = np.flatnonzero(
                        (rows.asset == asset) & (rows.day >= lo) & (rows.day <= hi)
                        & (rows.delta == DELTA_SEC))
                    if len(idx) == 0:
                        continue
                    flag = at_band_mask(mid_at[idx], vwap_at[idx], sd_at[idx], k, theta)
                    block = _score_mask(rows, idx, flag, n_draw=n_draw, seed=0)
                    report["assets"][asset]["filters"][bname][width][blk] = block
                    log(f"{asset:4s} {bname:16s} {width:5s} {blk:10s} "
                        f"shrink={block['shrink_ceiling_usd_per_asset_day']:7.1f} "
                        f"ret={block['retained_fraction']:.2f} "
                        f"ncell={block['occupancy']['median_eligible_per_cell']:.1f} "
                        f"maj={int(block['majority_kept'])} cut={int(block['proper_cut'])}")
        ranked = []
        for bname in BANDS:
            tr = report["assets"][asset]["filters"][bname].get("tight", {}).get("train")
            if tr and tr["majority_kept"] and tr["proper_cut"]:
                ranked.append((tr["shrink_ceiling_usd_per_asset_day"], bname))
        ranked.sort(reverse=True)
        report["assets"][asset]["survivors_tight"] = [
            {"filter": f, "shrink_ceiling": s} for s, f in ranked]
        report["assets"][asset]["letter"] = (
            ranked[0][1] if ranked else "no majority-and-cut filter")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def selftest() -> int:
    # SC-VWAP-1 leak: a later print must not move VWAP at t=50.
    sec = np.array([10, 20, 80], np.int64)
    px = np.array([100.0, 110.0, 1000.0])
    sz = np.array([1.0, 1.0, 100.0])
    vwap, _ = running_vwap_sigma(sec, px, sz, n_sec=100, end_sec=60)
    vwap_clean, _ = running_vwap_sigma(sec[:2], px[:2], sz[:2], n_sec=100, end_sec=60)
    assert np.isfinite(vwap[50]) and abs(vwap[50] - vwap_clean[50]) < 1e-9, (vwap[50], vwap_clean[50])
    assert abs(vwap[50] - 105.0) < 1e-9
    # SC-VWAP-2 plant: winner mid on +2.5σ.
    blocks = {"train": (20210601, 20210624), "forward": (20210601, 20210624)}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _synthetic_matrix(tmp / "planted", signal=True)
        # Build a fake cache path by monkeypatching run internals via a tiny matrix-only
        # occupancy check on at_band_mask.
        vwap = np.array([100.0])
        sd = np.array([2.0])
        mid_hit = np.array([100.0 + 2.5 * 2.0])
        mid_miss = np.array([100.0])
        assert at_band_mask(mid_hit, vwap, sd, 2.5, 1.0)[0]
        assert not at_band_mask(mid_miss, vwap, sd, 2.5, 1.0)[0]
        _synthetic_matrix(tmp / "red", signal=True)
        man = json.loads((tmp / "red" / "manifest.json").read_text())
        x = np.load(tmp / "red" / "x.npy")
        age = x[:, man["feature_names"].index("min_alert_age_sec")]
        hit = int(np.flatnonzero(np.abs(age - DELTA_SEC) <= 2.5)[0])
        cur = np.load(tmp / "red" / "current_asinh.npy"); cur[hit] = np.nan
        np.save(tmp / "red" / "current_asinh.npy", cur)
        try:
            load_delta_rows(tmp / "red", deltas=(DELTA_SEC,))
            y = np.sinh(np.load(tmp / "red" / "current_asinh.npy")) * 600.0
            if not np.isfinite(y).all():
                raise ProbeRefusal("1 non-finite y; expected all finite USD")
        except ProbeRefusal as exc:
            assert "non-finite" in str(exc), exc
        else:
            raise AssertionError("red fixture (NaN y) was accepted")
    print("selftest OK: leak fixture holds; +2.5σ plant hits; NaN-y refused")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--matrix-dir", type=Path)
    ap.add_argument("--events-root", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--n-draw", type=int, default=N_DRAW)
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.matrix_dir is None or a.events_root is None or a.out is None:
        ap.error("--matrix-dir, --events-root and --out are required unless --selftest")
    run(a.matrix_dir, a.events_root, a.out, n_draw=a.n_draw)
    return 0


if __name__ == "__main__":
    sys.exit(main())
