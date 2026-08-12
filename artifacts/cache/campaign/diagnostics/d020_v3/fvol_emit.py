"""fvol_emit.py — FORWARD-VOL REVIVAL, step 3: the CONTEXT COLUMNS.

Turns the two daily heads into the strictly-prior context a sheet or a model can
join on, at session grain and at minute grain.

SESSION GRAIN (`_cache/fvol/sessions.tsv`) — known before the first tick:
    implied_move_bps   the range head's forecast: the day's expected high-low
    sigma_day_bps      the vol head's forecast: the day's expected sigma
    sigma_level_bps    implied_move / 2 -- the expected ONE-SIDED excursion,
                       which is the unit the level system is quoted in
    band_{1,15,2}_{up,dn}_u6   the user's level system, as prices: the open
                       displaced by 1 / 1.5 / 2 x sigma_level
    forecast_arm       which arm produced it (`stack`, else `ridge`)

MINUTE GRAIN (`_cache/fvol/minutes/s{o}.tsv`) — state as of the END of each
minute, every column a function of that second and earlier only:
    traveled_bps             signed open-to-now displacement
    move_consumed_fraction   |traveled| / implied_move
    range_consumed_fraction  (high-so-far - low-so-far) / implied_move
    remaining_move_bps       implied_move - range-so-far, floored at zero
    move_z                   traveled / sigma_level: position in the LEVEL bands
    band_state               -3..+3 bucket on move_z: inside +-1, +-1..1.5,
                             +-1.5..2, beyond
    band_z                   traveled / sigma_day: the same displacement in
                             path-volatility units.  sigma_day is the sum of the
                             day's minute moves, so a mean-reverting session
                             consumes it without ever displacing 1 sigma_day --
                             the two z's answer different questions and both are
                             emitted rather than one standing in for the other.
    sigma_now_bps            the NOWCAST (see below)
    sigma_inst_bps           a 30-minute-halflife EWMA of realised minute vol,
                             scaled to a full session
    rv_sofar_bps             realised vol accumulated so far
    var_fraction_expected    u(t): the share of a day's variance that a TYPICAL
                             prior session had realised by this minute

THE NOWCAST.  `sigma_now^2 = (1 - u) * sigma_day^2 + u * (rv_sofar^2 / u)`.
Early in the day u is small and the forecast dominates; by the close u -> 1 and
the realised path dominates.  `u(t)` is the MEDIAN cumulative variance share of
the 60 most recent STRICTLY PRIOR in-scope sessions — never this session's own
shape, and never a future session.  Where no prior pool exists the profile falls
back to the flat u(t) = t/T and `profile_priors` records the 0 so the consumer
can see it is a fallback rather than a measurement.
"""
from __future__ import annotations

import argparse
import bisect
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import packlib as P                                        # noqa: E402

FVOL = P.CACHE / "fvol"
MINUTES = FVOL / "minutes"
FORECAST = FVOL / "daily_forecast.tsv"
PROFILE_WINDOW = 60
PROFILE_MINIMUM = 10
EWMA_HALFLIFE_MIN = 30.0
BANDS = ((1.0, "1"), (1.5, "15"), (2.0, "2"))


def read_forecast() -> dict:
    lines = FORECAST.read_text().splitlines()
    names = lines[0].split("\t")
    out = {}
    for line in lines[1:]:
        parts = line.split("\t")
        row = dict(zip(names, parts))
        ordinal = int(row["session"])
        picked = None
        for arm in ("stack", "ridge"):
            if row.get(f"rng_bps__{arm}") and row.get(f"rv_bps__{arm}"):
                picked = arm
                break
        if picked is None:
            continue
        out[ordinal] = {
            "arm": picked,
            "implied_move_bps": float(np.exp(float(row[f"rng_bps__{picked}"]))),
            "sigma_day_bps": float(np.exp(float(row[f"rv_bps__{picked}"]))),
        }
    return out


def minute_returns(ordinal: int) -> tuple:
    """`(mid[T+1], r2[M])` — the carried 1s mid and its squared 1-minute returns."""
    grid = P.load_grid(ordinal)[:, 0].astype(np.float64)
    valid = grid > 0
    first = int(np.flatnonzero(valid)[0])
    mid = grid.copy()
    mid[:first] = mid[first]
    idx = np.flatnonzero(valid)
    mid[~valid] = np.interp(np.flatnonzero(~valid), idx, mid[idx])
    seconds = len(mid) - 1
    marks = mid[np.arange(0, seconds + 1, 60)]
    return mid, np.diff(np.log(marks)) ** 2


class Profile:
    """u(t): the median cumulative variance share of the prior sessions."""

    def __init__(self, sessions: list):
        self.sessions = sorted(sessions)
        self._r2 = {}
        self._cache = {}

    def shares(self, ordinal: int) -> np.ndarray:
        if ordinal not in self._r2:
            _, r2 = minute_returns(ordinal)
            total = float(np.sum(r2))
            curve = np.cumsum(r2) / total if total > 0 else np.full(len(r2), np.nan)
            #: resample every session onto the full 390-minute clock so early
            #: closes contribute their SHAPE without distorting the length.
            grid = np.linspace(0.0, 1.0, 390)
            source = np.linspace(0.0, 1.0, len(curve))
            self._r2[ordinal] = np.interp(grid, source, curve)
        return self._r2[ordinal]

    def for_session(self, ordinal: int) -> tuple:
        if ordinal in self._cache:
            return self._cache[ordinal]
        cut = bisect.bisect_left(self.sessions, ordinal)
        priors = self.sessions[max(0, cut - PROFILE_WINDOW):cut]
        if len(priors) < PROFILE_MINIMUM:
            result = (np.linspace(1.0 / 390, 1.0, 390), 0)
        else:
            stack = np.stack([self.shares(prior) for prior in priors], axis=0)
            with np.errstate(all="ignore"):
                median = np.nanmedian(stack, axis=0)
            median = np.maximum.accumulate(np.nan_to_num(median, nan=0.0))
            if median[-1] <= 0:
                result = (np.linspace(1.0 / 390, 1.0, 390), 0)
            else:
                result = (np.clip(median / median[-1], 1e-4, 1.0), len(priors))
        self._cache[ordinal] = result
        return result


COLUMNS = ("minute", "second", "mid_u6", "traveled_bps", "abs_traveled_bps",
           "move_consumed_fraction", "range_so_far_bps", "range_consumed_fraction",
           "remaining_move_bps", "move_z", "band_state", "band_z", "rv_sofar_bps",
           "var_fraction_expected", "sigma_now_bps", "sigma_inst_bps")


def band_state(z: float) -> int:
    sign = 1 if z >= 0 else -1
    magnitude = abs(z)
    if magnitude < 1.0:
        return 0
    if magnitude < 1.5:
        return sign * 1
    if magnitude < 2.0:
        return sign * 2
    return sign * 3


def session_minutes(ordinal: int, forecast: dict, profile: Profile) -> tuple:
    """`(context, rows)` — the session header and its 390 minute rows."""
    head = forecast[ordinal]
    implied = head["implied_move_bps"]
    sigma = head["sigma_day_bps"]
    mid, r2 = minute_returns(ordinal)
    seconds = len(mid) - 1
    open_mid = float(mid[0]) if mid[0] > 0 else float(mid[np.flatnonzero(mid > 0)[0]])
    share, priors = profile.for_session(ordinal)

    context = {
        "session": ordinal, "forecast_arm": head["arm"],
        "implied_move_bps": implied, "sigma_day_bps": sigma,
        "open_u6": open_mid, "profile_priors": priors,
        "session_seconds": seconds,
    }
    level = implied / 2.0
    context["sigma_level_bps"] = level
    for multiple, tag in BANDS:
        context[f"band_{tag}_up_u6"] = open_mid * (1.0 + multiple * level / 1e4)
        context[f"band_{tag}_dn_u6"] = open_mid * (1.0 - multiple * level / 1e4)

    decay = 0.5 ** (1.0 / EWMA_HALFLIFE_MIN)
    ewma_state = ewma_weight = 0.0
    running = 0.0
    rows = []
    high = low = open_mid
    total_minutes = len(r2)
    for minute in range(total_minutes):
        end = min((minute + 1) * 60, seconds)
        window = mid[:end + 1]
        high, low = float(window.max()), float(window.min())
        now = float(mid[end])
        running += float(r2[minute])
        ewma_state = ewma_state * decay + float(r2[minute])
        ewma_weight = ewma_weight * decay + 1.0

        traveled = (now - open_mid) * 1e4 / open_mid
        range_so_far = (high - low) * 1e4 / open_mid
        rv_sofar = float(np.sqrt(running)) * 1e4
        # u(t) is indexed on the 390-minute clock; an early close still maps its
        # own minute onto the same normalised position.
        position = int(round((minute + 1) / total_minutes * 390)) - 1
        u = float(share[min(max(position, 0), 389)])
        extrapolated = rv_sofar / np.sqrt(u) if u > 0 else sigma
        sigma_now = float(np.sqrt((1.0 - u) * sigma ** 2 + u * extrapolated ** 2))
        inst = float(np.sqrt(ewma_state / ewma_weight * 390.0)) * 1e4 if ewma_weight > 0 else np.nan
        move_z = traveled / level if level > 0 else 0.0
        z = traveled / sigma if sigma > 0 else 0.0
        rows.append({
            "minute": minute, "second": end, "mid_u6": now,
            "traveled_bps": traveled, "abs_traveled_bps": abs(traveled),
            "move_consumed_fraction": abs(traveled) / implied,
            "range_so_far_bps": range_so_far,
            "range_consumed_fraction": range_so_far / implied,
            "remaining_move_bps": max(0.0, implied - range_so_far),
            "move_z": move_z, "band_state": band_state(move_z), "band_z": z,
            "rv_sofar_bps": rv_sofar, "var_fraction_expected": u,
            "sigma_now_bps": sigma_now, "sigma_inst_bps": inst,
        })
    return context, rows


def state_at(ordinal: int, second: int, forecast: dict, profile: Profile) -> dict:
    """The context row in force at `second` — the last minute row at or before it."""
    context, rows = session_minutes(ordinal, forecast, profile)
    chosen = None
    for row in rows:
        if row["second"] <= second:
            chosen = row
        else:
            break
    return dict(context, **(chosen or {}))


CONTEXT_COLUMNS = ("session", "forecast_arm", "implied_move_bps", "sigma_day_bps",
                   "sigma_level_bps", "open_u6", "profile_priors", "session_seconds",
                   "band_1_up_u6", "band_1_dn_u6", "band_15_up_u6", "band_15_dn_u6",
                   "band_2_up_u6", "band_2_dn_u6")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="start", type=int, default=125)
    parser.add_argument("--to", dest="stop", type=int, default=447)
    args = parser.parse_args()

    forecast = read_forecast()
    profile = Profile([o for o in range(125, 448)])
    MINUTES.mkdir(parents=True, exist_ok=True)
    contexts = []
    for ordinal in range(args.start, args.stop + 1):
        if ordinal not in forecast:
            continue
        context, rows = session_minutes(ordinal, forecast, profile)
        contexts.append(context)
        with (MINUTES / f"s{ordinal}.tsv").open("w") as handle:
            handle.write("\t".join(COLUMNS) + "\n")
            for row in rows:
                handle.write("\t".join(
                    str(row[name]) if isinstance(row[name], int) else f"{row[name]:.6f}"
                    for name in COLUMNS) + "\n")
    with (FVOL / "sessions.tsv").open("w") as handle:
        handle.write("\t".join(CONTEXT_COLUMNS) + "\n")
        for context in contexts:
            handle.write("\t".join(
                str(context[name]) if isinstance(context[name], (int, str))
                else f"{context[name]:.6f}" for name in CONTEXT_COLUMNS) + "\n")
    summary = {
        "sessions": len(contexts),
        "range": [contexts[0]["session"], contexts[-1]["session"]] if contexts else None,
        "arms": {arm: sum(1 for c in contexts if c["forecast_arm"] == arm)
                 for arm in ("stack", "ridge")},
        "minute_files": len(list(MINUTES.glob("s*.tsv"))),
    }
    (FVOL / "emit_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
