"""fvol_build.py — FORWARD-VOL REVIVAL, step 1: the per-session DAILY TABLE.

Rebuilt from scratch (D-010: the archived model is reference only; every number
here is recomputed from our own substrate).  One row per session in 125..447:

  TARGETS (this session's realised outcome, RTH only, from our own 1s grid)
    rng_bps   RTH high-low range, bps of the session's first valid mid
    rv_bps    realised volatility = sqrt(sum of squared 1-minute log returns),
              expressed in bps (a daily sigma, not annualised)

  RAW PRIOR-DAY MATERIAL (this session's own values; the model only ever reads
  them SHIFTED, see fvol_model.py)
    proxy_vol_close_bid / _ask   last valid per-minute W2.1 straddle PROXY_VOL
                                 of the session (typed-absent = NaN pre-s209)
    rvx_close                    RVX close on this session's calendar day
    atr14_bps                    packlib session_meta (already a prior-only stat)

No fits, no walls crossed: `packlib.assert_wall` gates every read and the sweep
range is pinned to 125..447.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import packlib as P                                        # noqa: E402

OUT = P.CACHE / "fvol"
VOL_DIR = pathlib.Path("/workspace/artifacts/reference/vol_indices")
#: The three published close series we own.  RVX is the Russell-native one; VIX
#: and VXD carry the market-wide level, and their spread to RVX is the
#: small-cap vol premium (a real, prior-only regime descriptor).
VOL_INDICES = {"rvx": ("FRED_RVXCLS.csv", "RVXCLS"),
               "vix": ("FRED_VIXCLS.csv", "VIXCLS"),
               "vxd": ("FRED_VXDCLS.csv", "VXDCLS")}
FIRST, LAST = 125, 447


def index_tables() -> dict:
    out = {}
    for name, (filename, column) in VOL_INDICES.items():
        table = {}
        with (VOL_DIR / filename).open() as handle:
            for row in csv.DictReader(handle):
                try:
                    table[row["observation_date"]] = float(row[column])
                except (TypeError, ValueError):
                    continue
        out[name] = table
    return out


def session_row(ordinal: int, indices: dict) -> dict:
    meta = P.session_meta(ordinal)
    grid = P.load_grid(ordinal)[:, 0].astype(np.float64)
    valid = grid > 0
    if valid.sum() < 600:
        raise RuntimeError(f"s{ordinal}: only {int(valid.sum())} valid grid seconds")
    mid = grid.copy()
    # carry-forward the pre-open zeros so the minute sampler never divides by 0
    first = int(np.flatnonzero(valid)[0])
    mid[:first] = mid[first]
    idx = np.flatnonzero(valid)
    mid[~valid] = np.interp(np.flatnonzero(~valid), idx, mid[idx])

    open_mid = float(mid[first])
    rng_bps = (float(mid[valid].max()) - float(mid[valid].min())) * 1e4 / open_mid

    # 1-minute log returns over the session's RTH minutes.  Half sessions (early
    # closes) carry a shorter grid; the realised sum runs over what exists and the
    # session length is emitted so the model can scale rather than mis-compare.
    seconds = len(mid) - 1
    marks = mid[np.arange(0, seconds + 1, 60)]
    logret = np.diff(np.log(marks))
    rv_bps = float(np.sqrt(np.sum(logret ** 2)) * 1e4)

    minutes = P.minute_aggregates(ordinal)
    pv_bid = minutes[:, P.TRAJECTORY_KEYS.index("proxy_vol_bid")]
    pv_ask = minutes[:, P.TRAJECTORY_KEYS.index("proxy_vol_ask")]

    def last_valid(series: np.ndarray) -> float:
        rows = np.flatnonzero(~np.isnan(series))
        return float(series[rows[-1]]) if rows.size else float("nan")

    day = meta["day"]
    return {
        "session": ordinal,
        "day": day,
        "session_seconds": float(seconds),
        "open_u6": open_mid,
        "rng_bps": rng_bps,
        "rv_bps": rv_bps,
        "proxy_vol_close_bid": last_valid(pv_bid),
        "proxy_vol_close_ask": last_valid(pv_ask),
        "rvx_close": indices["rvx"].get(day, float("nan")),
        "vix_close": indices["vix"].get(day, float("nan")),
        "vxd_close": indices["vxd"].get(day, float("nan")),
        "atr14_bps": float(meta["atr14_bps"]) if int(meta.get("atr_present", "0")) else float("nan"),
        "rv_prior_rate": (float(meta["rv_prior_rate"])
                          if int(meta.get("rv_prior_present", "0")) else float("nan")),
        "prior_close_u6": (float(meta["prior_close_u6"])
                           if int(meta.get("prior_present", "0")) else float("nan")),
        "prior_high_u6": (float(meta["prior_high_u6"])
                          if int(meta.get("prior_present", "0")) else float("nan")),
        "prior_low_u6": (float(meta["prior_low_u6"])
                         if int(meta.get("prior_present", "0")) else float("nan")),
    }


COLUMNS = ("session", "day", "session_seconds", "open_u6", "rng_bps", "rv_bps", "proxy_vol_close_bid",
           "proxy_vol_close_ask", "rvx_close", "vix_close", "vxd_close", "atr14_bps", "rv_prior_rate",
           "prior_close_u6", "prior_high_u6", "prior_low_u6")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    indices = index_tables()
    rows, missing = [], []
    for ordinal in range(FIRST, LAST + 1):
        try:
            rows.append(session_row(ordinal, indices))
        except Exception as error:                       # noqa: BLE001
            missing.append((ordinal, repr(error)))
    path = OUT / "daily_table.tsv"
    with path.open("w") as handle:
        handle.write("\t".join(COLUMNS) + "\n")
        for row in rows:
            handle.write("\t".join(
                row[name] if name == "day" else f"{row[name]:.6f}" if isinstance(row[name], float)
                else str(row[name]) for name in COLUMNS) + "\n")
    stats = {
        "sessions": len(rows), "missing": missing,
        "rvx_present": sum(1 for r in rows if r["rvx_close"] == r["rvx_close"]),
        "proxy_present": sum(1 for r in rows if r["proxy_vol_close_bid"] == r["proxy_vol_close_bid"]),
        "first_proxy_session": next((r["session"] for r in rows
                                     if r["proxy_vol_close_bid"] == r["proxy_vol_close_bid"]), None),
    }
    (OUT / "daily_table_build.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))
    print(path)
    build_prior_daily()




# --- the PRIOR-DAILY warm-up table -------------------------------------------
#
# `_cache/w2sum/s{o}.tsv` is the engine's own SessionSummary dump (high, low,
# close, vwap, RTH sum of squared 1s returns) and it exists for ordinals 0..917.
# Reading the ordinals BELOW the draw wall is what makes an honest HAR possible
# at the start of the scope: they are the substrate's own warm-up sessions (the
# same ones `prior_state.cpp` already folds into `atr14_bps` and `rv_prior_rate`
# at s125), they carry no future information by construction, and nothing but
# these five daily scalars is read from them.  Nothing at or above LAST is ever
# touched here, so the test-block wall is untouched.
WARMUP_FIRST = 59                     # 66 sessions of HAR history before s125

SUMMARY_COLUMNS = ("session", "day", "w_rng_bps", "w_rv_bps", "w_atr14_bps",
                   "w_close_u6", "w_high_u6", "w_low_u6", "w_vwap_u6")


def summary_row(ordinal: int) -> dict | None:
    path = P.CACHE / "w2sum" / f"s{ordinal}.tsv"
    if not path.exists():
        return None
    for line in path.read_text().splitlines():
        if not line.startswith("summary\t"):
            continue
        parts = line.split("\t")
        high, low, close = float(parts[3]), float(parts[4]), float(parts[5])
        if not (close > 0 and high >= low > 0):
            return None
        return {
            "session": ordinal, "day": parts[2],
            "w_rng_bps": (high - low) * 1e4 / close,
            "w_rv_bps": float(parts[9]) ** 0.5,
            "w_close_u6": close, "w_high_u6": high, "w_low_u6": low,
            "w_vwap_u6": float(parts[7]) if parts[8] == "1" else float("nan"),
        }
    return None


def build_prior_daily() -> pathlib.Path:
    """One row per ordinal WARMUP_FIRST..LAST of the engine's daily summaries.

    `w_atr14_bps` is the textbook ATR14 recomputed here from those summaries
    (true range = max(H-L, |H-C_prev|, |L-C_prev|), 14-session mean, bps of
    close) so that the same definition is available for every warm-up row, not
    only for the 125+ rows w2meta covers.
    """
    rows = [row for row in (summary_row(o) for o in range(WARMUP_FIRST, LAST + 1)) if row]
    for index, row in enumerate(rows):
        ranges = []
        for back in range(index - 14, index):
            if back < 1:
                ranges = []
                break
            prev_close = rows[back - 1]["w_close_u6"]
            ranges.append(max(rows[back]["w_high_u6"] - rows[back]["w_low_u6"],
                              abs(rows[back]["w_high_u6"] - prev_close),
                              abs(rows[back]["w_low_u6"] - prev_close)) * 1e4 / prev_close)
        row["w_atr14_bps"] = float(np.mean(ranges)) if len(ranges) == 14 else float("nan")
    path = OUT / "prior_daily.tsv"
    with path.open("w") as handle:
        handle.write("\t".join(SUMMARY_COLUMNS) + "\n")
        for row in rows:
            handle.write("\t".join(
                row[name] if name == "day" else str(row[name]) if name == "session"
                else f"{row[name]:.6f}" for name in SUMMARY_COLUMNS) + "\n")
    print(f"prior_daily: {len(rows)} rows {rows[0]['session']}..{rows[-1]['session']} -> {path}")
    return path


if __name__ == "__main__":
    main()
