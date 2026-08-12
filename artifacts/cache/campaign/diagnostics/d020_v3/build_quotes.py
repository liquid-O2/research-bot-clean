#!/usr/bin/env python3
"""BUILD_QUOTES — per-second NBBO-revision arrays for the MODEL-V2 quote-churn /
book-erosion tier (SNIPER_V2 T1.4).

The full-session ribbon cache (`_cache/ribbon/s*.tsv`) carries only the print and
option streams, so the quote stream is pulled once per session with the same
lawful reader (`qr_tape_ribbon --streams quotes`), reduced to per-second counters,
and the multi-hundred-MB raw pull is deleted again.  Nothing derived in C++,
nothing guessed here: every counter below is a literal comparison of consecutive
published NBBO rows.

Per-second channels (all counts/sums over the second's own revisions):
  q_n           NBBO revisions
  q_bid_sh      sum of published bid_shares      (mean = /q_n)
  q_ask_sh      sum of published ask_shares
  q_spread      sum of spread in bps
  q_spr_n       revisions with a usable spread
  q_bid_erode   revisions that CUT bid_shares at an UNCHANGED bid price
  q_ask_erode   revisions that CUT ask_shares at an UNCHANGED ask price
  q_bid_refill  revisions that ADD bid_shares at an unchanged bid price
  q_ask_refill  revisions that ADD ask_shares at an unchanged ask price
  q_bid_up      bid price increases      q_bid_dn  bid price decreases
  q_ask_up      ask price increases      q_ask_dn  ask price decreases
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import packlib  # noqa: E402

SECS = packlib.SESSION_SECONDS
QCACHE = packlib.CACHE / "qsec"
SCRATCH = packlib.CACHE / "qscratch"
KEYS = ("q_n", "q_bid_sh", "q_ask_sh", "q_spread", "q_spr_n",
        "q_bid_erode", "q_ask_erode", "q_bid_refill", "q_ask_refill",
        "q_bid_up", "q_bid_dn", "q_ask_up", "q_ask_dn")


def _bins(sec: np.ndarray, weights=None) -> np.ndarray:
    return np.bincount(sec, weights=weights, minlength=SECS)[:SECS].astype(np.float64)


def quote_arrays(ordinal: int) -> dict:
    packlib.assert_wall(ordinal, "quote_arrays")
    cached = QCACHE / f"s{ordinal}.npz"
    if cached.exists():
        with np.load(cached) as handle:
            return {key: handle[key].astype(np.float64) for key in handle.files}
    QCACHE.mkdir(parents=True, exist_ok=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)

    raw = SCRATCH / f"s{ordinal}.tsv"
    if not raw.exists():
        subprocess.run([str(packlib.BIN / "qr_tape_ribbon"), "--ordinal", str(ordinal),
                        "--from-second", "0", "--to-second", str(SECS),
                        "--streams", "quotes", "--out", str(raw)], check=True)

    out = {key: np.zeros(SECS) for key in KEYS}
    carry = None                                   # last row of the previous chunk
    reader = pd.read_csv(raw, sep="\t", header=None, names=list(range(10)),
                         comment="#", dtype=str, engine="c", na_filter=False,
                         chunksize=4_000_000)
    for chunk in reader:
        chunk = chunk[chunk[0] == "quote"]
        if not len(chunk):
            continue
        ms = pd.to_numeric(chunk[1], errors="coerce").to_numpy(np.float64)
        bid = pd.to_numeric(chunk[2], errors="coerce").to_numpy(np.float64)
        ask = pd.to_numeric(chunk[3], errors="coerce").to_numpy(np.float64)
        bsh = pd.to_numeric(chunk[4], errors="coerce").to_numpy(np.float64)
        ash = pd.to_numeric(chunk[5], errors="coerce").to_numpy(np.float64)
        if carry is not None:
            ms = np.concatenate([[carry[0]], ms])
            bid = np.concatenate([[carry[1]], bid])
            ask = np.concatenate([[carry[2]], ask])
            bsh = np.concatenate([[carry[3]], bsh])
            ash = np.concatenate([[carry[4]], ash])
        carry = (ms[-1], bid[-1], ask[-1], bsh[-1], ash[-1])

        sec = np.clip(np.nan_to_num(ms // 1000).astype(np.int64), 0, SECS - 1)
        mid = np.where((ask > bid) & np.isfinite(bid) & np.isfinite(ask),
                       bid + (ask - bid) / 2.0, np.nan)
        spread = np.where(np.isfinite(mid) & (mid > 0), (ask - bid) * 1e4 / mid, np.nan)
        out["q_n"] += _bins(sec)
        out["q_bid_sh"] += _bins(sec, np.nan_to_num(bsh))
        out["q_ask_sh"] += _bins(sec, np.nan_to_num(ash))
        out["q_spread"] += _bins(sec, np.nan_to_num(spread))
        out["q_spr_n"] += _bins(sec, np.isfinite(spread).astype(float))

        # transitions: row i versus row i-1 (the carry makes chunk borders exact)
        tail = sec[1:]
        db, da = bid[1:] - bid[:-1], ask[1:] - ask[:-1]
        dbs, das = bsh[1:] - bsh[:-1], ash[1:] - ash[:-1]
        out["q_bid_erode"] += _bins(tail, ((db == 0) & (dbs < 0)).astype(float))
        out["q_ask_erode"] += _bins(tail, ((da == 0) & (das < 0)).astype(float))
        out["q_bid_refill"] += _bins(tail, ((db == 0) & (dbs > 0)).astype(float))
        out["q_ask_refill"] += _bins(tail, ((da == 0) & (das > 0)).astype(float))
        out["q_bid_up"] += _bins(tail, (db > 0).astype(float))
        out["q_bid_dn"] += _bins(tail, (db < 0).astype(float))
        out["q_ask_up"] += _bins(tail, (da > 0).astype(float))
        out["q_ask_dn"] += _bins(tail, (da < 0).astype(float))

    np.savez_compressed(cached, **{k: v.astype(np.float32) for k, v in out.items()})
    raw.unlink(missing_ok=True)
    return out


def main():
    ordinals = [int(a) for a in sys.argv[1:]]
    for ordinal in ordinals:
        arrays = quote_arrays(ordinal)
        print(f"s{ordinal} quotes {arrays['q_n'].sum():,.0f} revisions", flush=True)


if __name__ == "__main__":
    main()
