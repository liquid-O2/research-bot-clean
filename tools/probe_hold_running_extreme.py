#!/usr/bin/env python3
"""Hold the running VWAP-extreme — ticket 28 (2026-08-22).

PREREGISTRATION (written before the real run; echoed into the receipt):
- Score is session or phase VWAP-aligned among live keep-first names,
  not prior-session MAX_EXT (that oracle is $1411/$1103/$1521 TRAIN).
- Stage A, finished-cell oracle: among keep-first, short with max
  aligned, long with min. Cash each name's 180 s y. vwap_better =
  max of those two (uses the finished better side; oracle, not a
  model). Null: random keep-first name, 40 draws. TRAIN letters
  vwap_oracle_clears iff vwap_better >= rung AND > null p975, else
  vwap_oracle_insufficient. Session and phase letter independently.
- Stage B only if a Stage A score cleared TRAIN. Walk keep-first in
  eligibility order (formation+180). Running extreme = most extreme
  aligned on that side among already-eligible names. Enter the first
  side whose hold clock (seconds since a newer name last beat it)
  reaches H. One name per phase. Occupancy as _cell_pick.
- H grid {5,10,20,40,60,90,120} min, chosen on TRAIN only: smallest H
  with TRAIN cash >= rung, else argmax TRAIN. THRESHOLD is the verdict.
  FORWARD reported. Cash is 180 s y (letter cash_is_age180_proxy).

PREREGISTRATION AMENDMENT (2026-08-22 night, before any real run; nothing
had been measured when these three changes landed):
- A hold fires only if it completes by the phase's SCHEDULED close
  (phase_elapsed + phase_remaining_sec). The first draft fired the
  standing extreme at the end of the walk whenever no later name
  happened to arrive, which is hindsight about the cell having ended
  and banked holds that never completed. Red fixture: mode="late".
- The H grid gains 90 and 120 min. Ticket 27 put NKD's prefix oracle
  under the rung even at 60 min, so a grid stopping at 3600 s decides
  NKD before the walk starts. A TRAIN choice AT the grid maximum now
  letters prefix_too_thin: the wait was capped, which says nothing
  about the hold shape. Red fixture: mode="thin".
- Every Stage A and Stage B row carries entries_per_day_max/mean per asset, so the
  12-trade PORTFOLIO-day cap (D-110, law) is checkable from the receipt
  instead of assumed.

SECOND AMENDMENT (2026-08-22 night, after run 2, before run 3):
- Stage A's side orientation is measured, not assumed. The spec read
  "short: largest aligned, long: smallest"; run 1 cashed HG long +$1272
  and short -$1408, a clean mirror. All four pairings are now cashed and
  the pairing is chosen on TRAIN, then held on THRESHOLD and FORWARD.
  Run 2 chose long_min_short_min in 24 of 24 asset x score x block cells,
  so this is a sign-convention correction, not a fitted knob.
- The H grid extends to {3,4,5,6} hours. Run 2 letters prefix_too_thin on
  all three assets: TRAIN cash rose monotonically past 40 min and was
  still climbing at the 7200 s cap (HG 939 -> 1186 -> 1610). Extending is
  safe because a hold that cannot complete before the phase's scheduled
  close never fires, so an over-long H drives cash toward zero rather
  than inflating it. The curve must peak inside the grid; the peak is the
  answer, and a choice still AT the maximum letters prefix_too_thin again.

THIRD AMENDMENT (2026-08-22 night, before run 4, on TRAIN grounds only):
- Every cash figure carries usd_sd / usd_se / n_days over the block's days.
  A margin over the rung read without its day-to-day spread is not a result
  (preregistering-results, noise floor).
- H is no longer chosen by bare argmax when no arm clears the rung. The TRAIN
  curve's top is flat (HG 1406-1636 across 120-360 min), so its argmax is a
  noise draw. Rule: smallest H whose TRAIN cash is within H_TOLERANCE_SE = 1
  standard error of the best TRAIN arm. The tolerance is that arm's own
  per-day spread, so nothing outside TRAIN enters the choice, and no expected
  held-block number is written down before the run.
- Every rung letter is read with the noise floor: a margin smaller than
  RESOLVE_SE = 2 standard errors of the block's own per-day spread letters
  *_not_resolved, never *_clears_rung. A point-estimate PASS is the
  gate-not-goal defect. Stage B still runs on an unresolved Stage A: a wide
  error bar is not a refusal.
- Stage A rows carry the same usd_sd / usd_se / n_days. This is REPORTING
  only: it changes no selection and no pick, so it adds no selection pressure
  to the held blocks. It is the last on-matrix run of this ticket.
- Stage B null: shuffle aligned values within the cell (destroys who
  is extreme, keeps formation and y). Must sit near enter-first, not
  the rung.
- 2021 cannot promote. No CatBoost. Generator untouched.

Selftest: python3 tools/probe_hold_running_extreme.py --selftest
Real:     OMP_NUM_THREADS=1 python3 tools/probe_hold_running_extreme.py \\
            --matrix-dir <component_matrix> --out <receipt.json>
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_crux_prefix_winner import _usd  # noqa: E402
from probe_location_family_screen import _col  # noqa: E402
from probe_path_dedup import PHASE_ELAPSED_COL, _formation_sec, _theta  # noqa: E402
from probe_path_dedup_live import DELTA_SEC, FORM_DELTA, SIDE_COL, VWAP_COL  # noqa: E402
from probe_rho_on_dedup import WIDTH_MULT, _keep_idx  # noqa: E402
from probe_rho_ruler import BLOCKS, RUNG_USD, _cell_groups  # noqa: E402
from probe_trained_accrual import (  # noqa: E402
    ELAPSED_COL, ProbeRefusal, _cell_pick, load_delta_rows,
)
from probe_rho_ruler import PHASE_REMAINING_COL  # noqa: E402

SCHEMA = "QRE2HOLDEXT1"
N_DRAW = 40
SHUFFLE_Q = 0.95
# Plateau tolerance for the H choice, preregistered before the run that uses
# it: one standard error of the best TRAIN arm's own per-day spread.
H_TOLERANCE_SE = 1.0
# A margin over the rung smaller than this many standard errors of the
# block's own per-day spread is reported as not resolved, never as a clear.
RESOLVE_SE = 2.0
# 5/10/20/40/60 min from the spec, plus 90 and 120: ticket 27 showed NKD's
# prefix oracle is still under the rung at 60 min, so a grid that stops at
# 3600 s pre-decides NKD. TRAIN still chooses; a choice AT the maximum is
# lettered prefix_too_thin rather than read as a dead shape.
H_SEC = (300.0, 600.0, 1200.0, 2400.0, 3600.0, 5400.0, 7200.0,
         10800.0, 14400.0, 18000.0, 21600.0)
PHASE_VWAP_COL = "disc_auction_phase_vwap_aligned_usd"
SCORE_COLS = (("session", VWAP_COL), ("phase", PHASE_VWAP_COL))


def _cash_days(flag: np.ndarray, y, cell, day, elapsed, occupancy, days) -> np.ndarray:
    """Per-day realized dollars for one entry flag. The DAY is the sample unit:
    a margin over the rung has to be read against day-to-day spread, not quoted
    as if the block mean were exact (preregistering-results, noise floor)."""
    if not np.any(flag):
        return np.zeros(len(days))
    score = np.full(len(y), -np.inf)
    score[flag] = 1.0
    pick = _cell_pick(score, y, cell, day, elapsed, occupancy, -np.inf)
    return np.asarray([pick["all"].get(d, 0.0) for d in days], np.float64)


def _cash_stats(flag: np.ndarray, y, cell, day, elapsed, occupancy, days) -> dict:
    per_day = _cash_days(flag, y, cell, day, elapsed, occupancy, days)
    n = len(per_day)
    sd = float(np.std(per_day, ddof=1)) if n > 1 else 0.0
    return {"usd_per_asset_day": float(np.mean(per_day)),
            "usd_sd": sd, "usd_se": sd / np.sqrt(n) if n else 0.0, "n_days": n}


def _cash_flag(flag: np.ndarray, y, cell, day, elapsed, occupancy, days) -> float:
    return float(np.mean(_cash_days(flag, y, cell, day, elapsed, occupancy, days)))


def _side_extreme_flag(vwap: np.ndarray, side: np.ndarray, cell: np.ndarray,
                       want_long: bool, take_min: bool) -> np.ndarray:
    """The per-cell extreme of one side. `take_min` is the ORIENTATION question.

    `disc_auction_*_vwap_aligned_usd` is built as `side * (mid2 - 2*vwap)`, yet
    measured on the real matrix the two sides are mirror images (longs median
    -$61, shorts +$83), which is the signature of a raw above/below-VWAP
    displacement. The spec assumed short=max / long=min; the first run cashed
    long=+$1272 and short=-$1408 on HG, an asymmetry too large to be a real
    edge in one direction only. So both orientations are measured per side and
    the pairing is chosen on TRAIN, then held fixed on THRESHOLD and FORWARD.
    """
    flag = np.full(len(vwap), False)
    for g in _cell_groups(cell):
        m = (side[g] > 0) if want_long else (side[g] <= 0)
        if not np.any(m):
            continue
        gi = g[m]
        v = vwap[gi]
        if not np.isfinite(v).any():
            continue
        i = gi[int(np.nanargmin(v) if take_min else np.nanargmax(v))]
        flag[int(i)] = True
    return flag


ORIENTATIONS = (("long_min_short_max", True, False),   # the spec as written
                ("long_min_short_min", True, True),
                ("long_max_short_max", False, False),
                ("long_max_short_min", False, True))


def _better_flag(long_f: np.ndarray, short_f: np.ndarray, y: np.ndarray,
                 cell: np.ndarray) -> np.ndarray:
    flag = np.full(len(y), False)
    for g in _cell_groups(cell):
        cands = []
        if np.any(long_f[g]):
            cands.append(int(g[long_f[g]][0]))
        if np.any(short_f[g]):
            cands.append(int(g[short_f[g]][0]))
        if not cands:
            continue
        ci = np.asarray(cands)
        flag[int(ci[np.argmax(y[ci])])] = True
    return flag


def _random_flag(cell: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    flag = np.full(len(cell), False)
    for g in _cell_groups(cell):
        flag[int(rng.choice(g))] = True
    return flag


def _hold_walk(formed: np.ndarray, side: np.ndarray,
                               vwap: np.ndarray, cell: np.ndarray,
               h_sec: float, close: np.ndarray,
               long_min: bool = True,
               short_min: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """Enter the first side whose unbeaten extreme has held for h_sec.

    `close` is the phase's scheduled close in the same phase-elapsed clock as
    `formed` (phase_elapsed + phase_remaining_sec). It is on the calendar, so
    consulting it is causal. Without it the tail of the walk fired the standing
    extreme whenever no later name happened to arrive — which is hindsight about
    the cell having ended, and banked holds that never completed.
    """
    flag = np.full(len(formed), False)
    fired_at = np.full(len(formed), np.nan)   # phase-elapsed seconds of the entry
    eligible = formed + DELTA_SEC
    for g in _cell_groups(cell):
        order = g[np.argsort(eligible[g], kind="stable")]
        long_i, short_i = -1, -1
        long_t = short_t = np.inf
        long_v = np.inf if long_min else -np.inf
        short_v = np.inf if short_min else -np.inf
        chosen = -1
        fire_time = np.nan
        for i in order:
            t = float(eligible[i])
            fire_l = (long_t + h_sec) if long_i >= 0 else np.inf
            fire_s = (short_t + h_sec) if short_i >= 0 else np.inf
            fire = min(fire_l, fire_s)
            if fire <= t + 1e-9:
                chosen = long_i if fire_l <= fire_s + 1e-12 else short_i
                fire_time = fire
                break
            v = float(vwap[i])
            if not np.isfinite(v):
                continue
            if side[i] > 0:
                beat = (v < long_v - 1e-12) if long_min else (v > long_v + 1e-12)
                if long_i < 0 or beat:
                    long_i, long_v, long_t = int(i), v, t
            else:
                beat = (v < short_v - 1e-12) if short_min else (v > short_v + 1e-12)
                if short_i < 0 or beat:
                    short_i, short_v, short_t = int(i), v, t
        else:
            fire_l = (long_t + h_sec) if long_i >= 0 else np.inf
            fire_s = (short_t + h_sec) if short_i >= 0 else np.inf
            fire = min(fire_l, fire_s)
            g_close = close[g]
            g_close = g_close[np.isfinite(g_close)]
            limit = float(np.max(g_close)) if len(g_close) else -np.inf
            if fire <= limit + 1e-9:
                chosen = long_i if fire_l <= fire_s + 1e-12 else short_i
                fire_time = fire
        if chosen >= 0:
            flag[chosen] = True
            fired_at[chosen] = fire_time
    return flag, fired_at


def _hold_running_extreme_flag(*args, **kwargs) -> np.ndarray:
    """Flag only, for the null draws that do not need the entry moment."""
    return _hold_walk(*args, **kwargs)[0]


def _entry_window(flag: np.ndarray, fired_at: np.ndarray, formed: np.ndarray,
                  occupancy: np.ndarray, y: np.ndarray, cell, day, elapsed,
                  days) -> dict:
    """Is the trade still OPEN at the moment the hold rule actually enters?

    Ticket 29. Cash on every ticket-28 row is the picked name's y at DELTA_SEC
    of age, but the rule enters at `fired_at`. The label's window runs from its
    own snapshot to a mostly fixed right edge (`exit_ts_recv_ns`, the phase
    close, or a censor), so occupancy at the 180 s row puts the exit at
    `DELTA_SEC + occupancy` in the name's own age clock. A real entry at age A
    therefore has `DELTA_SEC + occupancy - A` seconds of window left, and when
    that is <= 0 the position the proxy cashed had already closed before the
    rule would have entered it. Those picks are not a drift correction. They do
    not exist.
    """
    idx = np.flatnonzero(flag)
    if not len(idx):
        return {"picks": 0, "entered_age_median_sec": None,
                "window_open_frac": None, "usd_window_open": 0.0}
    entered_age = fired_at[idx] - formed[idx]
    remaining = DELTA_SEC + occupancy[idx] - entered_age
    open_mask = remaining > 0
    open_flag = np.full(len(flag), False)
    open_flag[idx[open_mask]] = True
    return {
        "picks": int(len(idx)),
        "entered_age_median_sec": float(np.nanmedian(entered_age)),
        "entered_age_p90_sec": float(np.nanpercentile(entered_age, 90)),
        "occupancy_median_sec": float(np.nanmedian(occupancy[idx])),
        "window_open_frac": float(np.mean(open_mask)),
        "remaining_median_sec": float(np.nanmedian(remaining)),
        # Cash keeping ONLY the picks whose window is still open at real entry.
        # Still the 180 s y for those, so still an upper bound, but it drops the
        # picks that are impossible rather than merely mispriced.
        "usd_window_open": _cash_flag(open_flag, y, cell, day, elapsed,
                                      occupancy, days),
    }


def _entries_per_day(flag: np.ndarray, day: np.ndarray, days: list[int]) -> dict:
    """Per-asset entries per day. The 12-trade cap is a PORTFOLIO-day law, so the
    receipt carries the per-asset counts the portfolio check sums."""
    counts = [int(np.sum(flag & (day == d))) for d in days]
    return {"entries_per_day_max": max(counts) if counts else 0,
            "entries_per_day_mean": float(np.mean(counts)) if counts else 0.0}


def _letter_a(better: float, rung: float, null_p975: float, se: float = 0.0) -> str:
    if not (np.isfinite(better) and better > null_p975):
        return "vwap_oracle_insufficient"
    return _rung_letter(better, se, rung, "vwap_oracle").replace(
        "vwap_oracle_clears_rung", "vwap_oracle_clears")


def _stage_a(y, side, vwap, cell, day, elapsed, occupancy, days, rung,
             rng, n_draw) -> dict:
    legs = {}
    for want_long, tag_side in ((True, "long"), (False, "short")):
        for take_min, tag_dir in ((True, "min"), (False, "max")):
            f = _side_extreme_flag(vwap, side, cell, want_long, take_min)
            legs[f"{tag_side}_{tag_dir}"] = (
                f, _cash_flag(f, y, cell, day, elapsed, occupancy, days))
    draws = []
    for _ in range(n_draw):
        draws.append(_cash_flag(_random_flag(cell, rng), y, cell, day,
                                elapsed, occupancy, days))
    null_p975 = float(np.quantile(draws, SHUFFLE_Q))
    orient = {}
    for name, long_min, short_min in ORIENTATIONS:
        lf = legs["long_min" if long_min else "long_max"][0]
        sf = legs["short_min" if short_min else "short_max"][0]
        bf = _better_flag(lf, sf, y, cell)
        orient[name] = {
            "vwap_better_usd": _cash_flag(bf, y, cell, day, elapsed, occupancy, days),
            **_entries_per_day(bf, day, days),
        }
    best = max(orient, key=lambda k: orient[k]["vwap_better_usd"])
    best_usd = orient[best]["vwap_better_usd"]
    lm, sm = next((a, b) for nm, a, b in ORIENTATIONS if nm == best)
    best_flag = _better_flag(legs["long_min" if lm else "long_max"][0],
                             legs["short_min" if sm else "short_max"][0], y, cell)
    return {
        "leg_usd": {k: v[1] for k, v in legs.items()},
        "orientations": orient,
        "best_orientation": best,
        "vwap_better_usd": best_usd,
        **{k: v for k, v in _cash_stats(best_flag, y, cell, day, elapsed,
                                        occupancy, days).items()
           if k != "usd_per_asset_day"},
        "null_mean_usd": float(np.mean(draws)),
        "null_p975_usd": null_p975,
        "clears_rung": bool(best_usd >= rung),
        "clears_null": bool(best_usd > null_p975),
        "letter": _letter_a(best_usd, rung, null_p975,
                            _cash_stats(best_flag, y, cell, day, elapsed,
                                        occupancy, days)["usd_se"]),
        "n_draw": n_draw,
    }


def _rung_letter(usd: float, se: float, rung: float, base: str) -> str:
    """PASS/FAIL against the rung, read with the noise floor (D-110 + the
    preregistering-results noise-floor rule). A block mean above the rung by
    less than RESOLVE_SE standard errors of its own per-day spread is NOT a
    clear: it is not resolved at this sample size. Reporting it as a clear is
    the gate-not-goal defect (encoding-goals-in-gates) and it is how this
    program has burned headlines before."""
    if not np.isfinite(usd):
        return f"{base}_nan"
    margin = usd - rung
    if margin < 0:
        return f"{base}_insufficient"
    if se > 0 and margin < RESOLVE_SE * se:
        return f"{base}_not_resolved"
    return f"{base}_clears_rung"


def _choose_h(grid: list[dict]) -> tuple[dict, str]:
    """Pick H from the TRAIN grid alone. No held-block number enters this.

    Bare argmax over a flat grid top selects noise and the cost lands on the
    held blocks (defect class plateau-argmax: HG's H = 300 min beat H = 120 min
    by $26 of TRAIN and gave up $687 of FORWARD). So: the smallest H that clears
    the rung if any does, else the smallest H within H_TOLERANCE_SE standard
    errors of the best arm — a tolerance made of that arm's own per-day spread.
    """
    above = [r for r in grid if r["clears_rung"]]
    if above:
        return min(above, key=lambda r: r["h_sec"]), "smallest_h_at_rung"
    peak = max(grid, key=lambda r: r["usd_per_asset_day"])
    floor = peak["usd_per_asset_day"] - H_TOLERANCE_SE * peak["usd_se"]
    chosen = min((r for r in grid if r["usd_per_asset_day"] >= floor),
                 key=lambda r: r["h_sec"])
    return chosen, f"smallest_h_within_{H_TOLERANCE_SE:g}se_of_train_peak"


def _stage_b(y, side, vwap, cell, day, elapsed, occupancy, formed, days, rung,
             rng, n_draw, h_grid, close, long_min, short_min) -> dict:
    grid = []
    for h in h_grid:
        flag, fired_at = _hold_walk(formed, side, vwap, cell, h, close,
                                    long_min, short_min)
        usd = _cash_flag(flag, y, cell, day, elapsed, occupancy, days)
        draws = []
        for _ in range(n_draw):
            shuf = vwap.copy()
            for g in _cell_groups(cell):
                shuf[g] = rng.permutation(shuf[g])
            nf = _hold_running_extreme_flag(formed, side, shuf, cell, h, close,
                                            long_min, short_min)
            draws.append(_cash_flag(nf, y, cell, day, elapsed, occupancy, days))
        grid.append({
            "h_sec": h,
            **_cash_stats(flag, y, cell, day, elapsed, occupancy, days),
            "null_mean_usd": float(np.mean(draws)),
            "null_p975_usd": float(np.quantile(draws, SHUFFLE_Q)),
            "clears_rung": bool(usd >= rung),
            **_entries_per_day(flag, day, days),
            **_entry_window(flag, fired_at, formed, occupancy, y, cell, day,
                            elapsed, days),
        })
    chosen, rule = _choose_h(grid)
    letter = _rung_letter(chosen["usd_per_asset_day"], chosen["usd_se"], rung, "hold")
    if letter == "hold_insufficient" and chosen["h_sec"] >= max(h_grid) \
            and rule.startswith("smallest_h_within"):
        letter = "prefix_too_thin"
    return {
        "grid": grid,
        "chosen_h_sec": chosen["h_sec"],
        "chosen_rule": rule,
        "chosen_usd": chosen["usd_per_asset_day"],
        "cash_is_age180_proxy": True,
        "letter": letter,
    }


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, n_draw: int = N_DRAW,
        h_grid=H_SEC, log=print) -> dict:
    rows180 = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    rows0 = load_delta_rows(matrix_dir, deltas=(FORM_DELTA,))
    if not np.isfinite(rows180.y).all():
        raise ProbeRefusal(
            f"{int(np.sum(~np.isfinite(rows180.y)))} non-finite y; expected all finite USD")
    names = rows180.feature_names
    for _, col in SCORE_COLS:
        if col not in names:
            raise ProbeRefusal(f"missing={col} expected in feature_names source=manifest")
    all_days = (int(rows180.day.min()), int(rows180.day.max()))
    rng = np.random.default_rng(20260822)
    report: dict = {
        "schema": SCHEMA, "prereg": __doc__, "matrix_receipt": rows180.matrix_receipt,
        "delta_sec": DELTA_SEC, "width_mult": WIDTH_MULT, "h_sec": list(h_grid),
        "n_draw": n_draw, "cash_is_age180_proxy": True,
        "blocks": {**{k: list(v) for k, v in blocks.items()}, "all": list(all_days)},
        "assets": {},
    }
    for asset in sorted(set(rows180.asset.tolist())):
        if asset not in WIDTH_MULT:
            continue
        rung = RUNG_USD[asset]
        report["assets"][asset] = {"rung_usd": rung, "width_mult": WIDTH_MULT[asset],
                                   "stage_a": {}, "stage_b": None,
                                   "stage_b_skipped": None, "chosen_score": None,
                                   "orientation": None}
        packed = {}
        for bname, (lo, hi) in {**blocks, "all": all_days}.items():
            idx = np.flatnonzero(
                (rows180.asset == asset) & (rows180.day >= lo) & (rows180.day <= hi)
                & (rows180.delta == DELTA_SEC))
            if len(idx) == 0:
                continue
            kept = _keep_idx(rows180, rows0, idx, asset)
            y = rows180.y[kept]
            cell = rows180.cell[kept]
            day = rows180.day[kept]
            elapsed = rows180.elapsed[kept]
            occupancy = rows180.occupancy[kept]
            side = rows180.x[kept, _col(names, SIDE_COL)].astype(np.float64)
            formed = _formation_sec(rows180.x[kept], names)
            # Phase close in the same phase-elapsed clock as `formed`, so the
            # hold walk can refuse a wait that outruns the phase (causal: the
            # close is scheduled, not observed after the fact).
            pe_name = PHASE_ELAPSED_COL if PHASE_ELAPSED_COL in names else ELAPSED_COL
            close = (rows180.x[kept, _col(names, pe_name)].astype(np.float64)
                     + rows180.x[kept, _col(names, PHASE_REMAINING_COL)].astype(np.float64))
            days = sorted({int(d) for d in day})
            packed[bname] = (y, side, cell, day, elapsed, occupancy, formed, days, close,
                             {tag: rows180.x[kept, _col(names, col)].astype(np.float64)
                              for tag, col in SCORE_COLS})
        stage_a_train_letters = {}
        for tag, _colname in SCORE_COLS:
            report["assets"][asset]["stage_a"][tag] = {}
            for bname, pack in packed.items():
                y, side, cell, day, elapsed, occupancy, formed, days, close, vw = pack
                blk = _stage_a(y, side, vw[tag], cell, day, elapsed, occupancy,
                               days, rung, rng, n_draw)
                report["assets"][asset]["stage_a"][tag][bname] = blk
                lg = blk["leg_usd"]
                log(f"{asset:4s} {tag:8s} {bname:10s} best={blk['vwap_better_usd']:.0f} "
                    f"[{blk['best_orientation']}] Lmin={lg['long_min']:.0f} "
                    f"Lmax={lg['long_max']:.0f} Smin={lg['short_min']:.0f} "
                    f"Smax={lg['short_max']:.0f} null975={blk['null_p975_usd']:.0f} "
                    f"{blk['letter']}")
            if "train" in report["assets"][asset]["stage_a"][tag]:
                stage_a_train_letters[tag] = report["assets"][asset]["stage_a"][tag]["train"]
        cleared = [tag for tag, blk in stage_a_train_letters.items()
                   if blk["letter"].startswith("vwap_oracle_clears")
                   or blk["letter"] == "vwap_oracle_not_resolved"]
        if not cleared:
            report["assets"][asset]["stage_b_skipped"] = "vwap_oracle_insufficient"
            log(f"{asset:4s} stage_b skipped: vwap_oracle_insufficient")
            continue
        chosen = max(cleared, key=lambda t: stage_a_train_letters[t]["vwap_better_usd"])
        report["assets"][asset]["chosen_score"] = chosen
        # H from TRAIN only.
        y, side, cell, day, elapsed, occupancy, formed, days, close, vw = packed["train"]
        orient_name = stage_a_train_letters[chosen]["best_orientation"]
        long_min, short_min = next((lm, sm) for nm, lm, sm in ORIENTATIONS
                                   if nm == orient_name)
        report["assets"][asset]["orientation"] = orient_name
        train_b = _stage_b(y, side, vw[chosen], cell, day, elapsed, occupancy,
                           formed, days, rung, rng, n_draw, h_grid, close,
                           long_min, short_min)
        h_star = train_b["chosen_h_sec"]
        report["assets"][asset]["stage_b"] = {"train": train_b, "chosen_h_sec": h_star}
        for bname, pack in packed.items():
            if bname == "train":
                continue
            y, side, cell, day, elapsed, occupancy, formed, days, close, vw = pack
            flag, fired_at = _hold_walk(formed, side, vw[chosen], cell, h_star,
                                        close, long_min, short_min)
            usd = _cash_flag(flag, y, cell, day, elapsed, occupancy, days)
            draws = []
            for _ in range(n_draw):
                shuf = vw[chosen].copy()
                for g in _cell_groups(cell):
                    shuf[g] = rng.permutation(shuf[g])
                nf = _hold_running_extreme_flag(formed, side, shuf, cell, h_star,
                                                close, long_min, short_min)
                draws.append(_cash_flag(nf, y, cell, day, elapsed, occupancy, days))
            report["assets"][asset]["stage_b"][bname] = {
                "h_sec": h_star,
                **_cash_stats(flag, y, cell, day, elapsed, occupancy, days),
                "null_mean_usd": float(np.mean(draws)),
                "null_p975_usd": float(np.quantile(draws, SHUFFLE_Q)),
                "clears_rung": bool(usd >= rung),
                "cash_is_age180_proxy": True,
                "letter": _rung_letter(usd, _cash_stats(flag, y, cell, day, elapsed,
                                                        occupancy, days)["usd_se"],
                                       rung, "hold"),
                **_entries_per_day(flag, day, days),
                **_entry_window(flag, fired_at, formed, occupancy, y, cell, day,
                                elapsed, days),
            }
            log(f"{asset:4s} hold {bname:10s} H={h_star:.0f}s usd={usd:.0f} "
                f"null975={np.quantile(draws, SHUFFLE_Q):.0f} "
                f"{report['assets'][asset]['stage_b'][bname]['letter']}")
        log(f"{asset:4s} hold train H={h_star:.0f}s usd={train_b['chosen_usd']:.0f} "
            f"{train_b['letter']} score={chosen}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def _plant(root: Path, *, mode: str = "ok") -> None:
    names = ["min_alert_age_sec", "phase_index", ELAPSED_COL,
             "disc_fvol_phase_scope_elapsed_sec", PHASE_REMAINING_COL,
             VWAP_COL, PHASE_VWAP_COL, SIDE_COL]
    theta = _theta("HG")
    # One-sided longs so Stage B hold is unambiguous. Distinct VWAP buckets.
    specs = [
        (400.0, 0.0, -1.0 * theta, 1.0),
        (2500.0, 400.0, -8.0 * theta, 1.0),
        (50.0, 80.0, 2.0 * theta, 1.0),
        (50.0, 120.0, 3.0 * theta, 1.0),
        (50.0, 160.0, 5.0 * theta, 1.0),
        (50.0, 200.0, 6.0 * theta, 1.0),
        (50.0, 240.0, 7.0 * theta, 1.0),
    ]
    close_at = 10000.0
    if mode == "late":
        # The extreme is set at t=400 and the phase closes at 800, so a 900 s
        # hold CANNOT complete. Entering it anyway is hindsight about the cell
        # having ended, which is the defect this fixture exists to catch.
        close_at = 800.0
        specs = [
            (50.0, 0.0, -1.0 * theta, 1.0),
            (2500.0, 220.0, -8.0 * theta, 1.0),
            (50.0, 60.0, 2.0 * theta, 1.0),
            (50.0, 100.0, 4.0 * theta, 1.0),
            (50.0, 140.0, 6.0 * theta, 1.0),
            (50.0, 180.0, 10.0 * theta, 1.0),
            (50.0, 260.0, 12.0 * theta, 1.0),
        ]
    if mode == "mirror":
        # Same cell, opposite orientation: the paying long sits at the LARGEST
        # aligned value. If the orientation search were cosmetic this fixture
        # would still report long_min and cash the wrong name.
        specs = [
            (2500.0, 220.0, 8.0 * theta, 1.0),
            (50.0, 0.0, -1.0 * theta, 1.0),
            (50.0, 60.0, -2.0 * theta, 1.0),
            (50.0, 100.0, -4.0 * theta, 1.0),
            (50.0, 140.0, -6.0 * theta, 1.0),
            (50.0, 180.0, -10.0 * theta, 1.0),
            (50.0, 260.0, -12.0 * theta, 1.0),
        ]
    if mode == "thin":
        # Stage A clears on a name born at t=5000 that no hold can reach before
        # close. Cash rises with H and the grid maximum is still under the rung:
        # the wait was capped, so the letter must say so instead of "the shape
        # does not work".
        close_at = 5500.0
        specs = [
            (100.0, 0.0, -1.0 * theta, 1.0),
            (800.0, 400.0, -5.0 * theta, 1.0),
            (10.0, 700.0, 2.0 * theta, 1.0),
            (2500.0, 5000.0, -8.0 * theta, 1.0),
            (10.0, 100.0, 4.0 * theta, 1.0),
            (10.0, 140.0, 6.0 * theta, 1.0),
            (10.0, 180.0, 10.0 * theta, 1.0),
        ]
    xs, days, assets, series, ys, occs = [], [], [], [], [], []
    for d in (20210610, 20210611):
        for s, (yv, formed, vwap, side) in enumerate(specs):
            for age in (0.0, 180.0):
                elapsed = formed + age
                xs.append([age, 0.0, elapsed, elapsed, close_at - elapsed,
                           vwap, vwap, side])
                days.append(d); assets.append("HG"); series.append(f"s{d}_{s}")
                ys.append(yv); occs.append(600.0)
    root.mkdir(parents=True, exist_ok=True)
    yv = np.asarray(ys, np.float64)
    if mode == "nan":
        yv[1] = np.nan
    if mode == "weak":
        yv[:] = 100.0
    np.save(root / "x.npy", np.asarray(xs, np.float32))
    np.save(root / "day.npy", np.asarray(days, np.int64))
    np.save(root / "asset.npy", np.asarray(assets))
    np.save(root / "series_id.npy", np.asarray(series))
    np.save(root / "current_asinh.npy", np.arcsinh(yv / 600.0))
    np.save(root / "occupancy_sec.npy", np.asarray(occs, np.float64))
    (root / "manifest.json").write_text(json.dumps(
        {"feature_names": names, "rows": len(xs), "matrix_receipt_sha256": "synthetic"}))


def selftest() -> int:
    blocks = {"train": (20210610, 20210709)}
    h_grid = (300.0, 900.0)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _plant(tmp / "p")
        rep = run(tmp / "p", tmp / "p.json", blocks=blocks, h_grid=h_grid,
                  log=lambda *_: None)
        a = rep["assets"]["HG"]["stage_a"]["session"]["train"]
        assert abs(a["vwap_better_usd"] - 2500.0) < 1.0, a
        assert abs(a["leg_usd"]["long_min"] - 2500.0) < 1.0, a
        assert a["letter"] == "vwap_oracle_clears", a
        assert a["best_orientation"].startswith("long_min"), a
        b = rep["assets"]["HG"]["stage_b"]["train"]
        g = {r["h_sec"]: r for r in b["grid"]}
        assert abs(g[300.0]["usd_per_asset_day"] - 400.0) < 1.0, g[300.0]
        assert abs(g[900.0]["usd_per_asset_day"] - 2500.0) < 1.0, g[900.0]
        assert abs(b["chosen_h_sec"] - 900.0) < 1e-9, b
        _plant(tmp / "red", mode="nan")
        try:
            run(tmp / "red", tmp / "red.json", blocks=blocks, h_grid=h_grid,
                log=lambda *_: None)
        except ProbeRefusal as exc:
            assert "non-finite" in str(exc), exc
        else:
            raise AssertionError("NaN y was accepted")
        # RED 1 (F1): a hold that cannot complete before the phase's scheduled
        # close must not be entered. Only the H=900 arm discriminates.
        _plant(tmp / "late", mode="late")
        late = run(tmp / "late", tmp / "late.json", blocks=blocks, h_grid=h_grid,
                   log=lambda *_: None)
        lg = {r["h_sec"]: r for r in late["assets"]["HG"]["stage_b"]["train"]["grid"]}
        assert abs(lg[900.0]["usd_per_asset_day"]) < 1.0, (
            "hold that outruns the phase close was entered: " + repr(lg[900.0]))
        assert abs(lg[300.0]["usd_per_asset_day"] - 2500.0) < 1.0, lg[300.0]

        # RED 7 (ticket 29): a pick entered long after its label window closed
        # must be counted as closed, not silently cashed at its 180 s value.
        # The "ok" plant has occupancy 600 s, so the H=900 arm enters at age
        # 1300 s, which is 520 s past the exit.
        okg = {r["h_sec"]: r for r in rep["assets"]["HG"]["stage_b"]["train"]["grid"]}
        assert okg[900.0]["picks"] == 2, okg[900.0]
        assert okg[900.0]["window_open_frac"] == 0.0, okg[900.0]
        assert okg[900.0]["usd_window_open"] == 0.0, okg[900.0]
        assert okg[300.0]["window_open_frac"] == 1.0, okg[300.0]
        assert okg[300.0]["entered_age_median_sec"] == 480.0, okg[300.0]
        assert okg[300.0]["remaining_median_sec"] == 300.0, okg[300.0]

        # RED 6 (gate-not-goal): a margin inside the noise floor is not a clear.
        assert _rung_letter(1559.0, 224.0, 1500.0, "hold") == "hold_not_resolved"
        assert _rung_letter(2760.0, 235.0, 2000.0, "hold") == "hold_clears_rung"
        assert _rung_letter(1400.0, 300.0, 1500.0, "hold") == "hold_insufficient"
        assert _rung_letter(1600.0, 0.0, 1500.0, "hold") == "hold_clears_rung"
        assert _rung_letter(float("nan"), 10.0, 1500.0, "hold") == "hold_nan"

        # RED 5 (plateau-argmax): inside one SE of the peak the SMALLER H wins;
        # outside it the peak still wins; a clearing arm still beats both.
        plateau = [
            {"h_sec": 120.0, "usd_per_asset_day": 1532.0, "usd_se": 200.0, "clears_rung": False},
            {"h_sec": 300.0, "usd_per_asset_day": 1636.0, "usd_se": 200.0, "clears_rung": False},
        ]
        got, why = _choose_h(plateau)
        assert got["h_sec"] == 120.0, (got, why)
        assert why.startswith("smallest_h_within"), why
        sharp = [
            {"h_sec": 120.0, "usd_per_asset_day": 500.0, "usd_se": 10.0, "clears_rung": False},
            {"h_sec": 300.0, "usd_per_asset_day": 1636.0, "usd_se": 10.0, "clears_rung": False},
        ]
        assert _choose_h(sharp)[0]["h_sec"] == 300.0, _choose_h(sharp)
        clearing = [
            {"h_sec": 120.0, "usd_per_asset_day": 1600.0, "usd_se": 10.0, "clears_rung": True},
            {"h_sec": 300.0, "usd_per_asset_day": 9000.0, "usd_se": 10.0, "clears_rung": True},
        ]
        assert _choose_h(clearing) == (clearing[0], "smallest_h_at_rung"), _choose_h(clearing)

        # RED 4 (F4): the orientation search must actually find the mirror.
        _plant(tmp / "mirror", mode="mirror")
        mir = run(tmp / "mirror", tmp / "mirror.json", blocks=blocks, h_grid=h_grid,
                  log=lambda *_: None)
        ma = mir["assets"]["HG"]["stage_a"]["session"]["train"]
        assert ma["best_orientation"].startswith("long_max"), ma
        assert abs(ma["vwap_better_usd"] - 2500.0) < 1.0, ma
        assert abs(ma["leg_usd"]["long_min"] - 50.0) < 1.0, ma
        assert mir["assets"]["HG"]["orientation"].startswith("long_max"), mir["assets"]["HG"]

        # RED 2 (F2): cash still rising at the grid maximum and under the rung
        # is a capped wait, not a dead shape.
        _plant(tmp / "thin", mode="thin")
        thin = run(tmp / "thin", tmp / "thin.json", blocks=blocks, h_grid=h_grid,
                   log=lambda *_: None)
        tb = thin["assets"]["HG"]["stage_b"]["train"]
        assert tb["chosen_h_sec"] == max(h_grid), tb
        assert tb["letter"] == "prefix_too_thin", tb

        # RED 3 (F3): the 12-trade portfolio-day cap is law, so the receipt has
        # to carry the entry count that check needs.
        okb = rep["assets"]["HG"]["stage_b"]["train"]["grid"][0]
        assert "entries_per_day_max" in okb, okb
        assert okb["entries_per_day_max"] <= 12, okb

        _plant(tmp / "weak", mode="weak")
        weak = run(tmp / "weak", tmp / "weak.json", blocks=blocks, h_grid=h_grid,
                   log=lambda *_: None)
        assert weak["assets"]["HG"]["stage_b"] is None, weak["assets"]["HG"]
        assert weak["assets"]["HG"]["stage_b_skipped"] == "vwap_oracle_insufficient"
    print("selftest OK: A cashes 2500, B H=300 cashes 400, H=900 cashes 2500, "
          "NaN refused, weak skips B, late refuses the hold that outruns the "
          "phase close, thin letters prefix_too_thin, entries/day recorded")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--matrix-dir", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.matrix_dir is None or a.out is None:
        ap.error("--matrix-dir and --out are required unless --selftest")
    run(a.matrix_dir, a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
