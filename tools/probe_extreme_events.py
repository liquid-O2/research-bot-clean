#!/usr/bin/env python3
"""New-extreme events — ticket 35 (2026-08-23).

WHY THIS FRAME. The score is static per name: its own DELTA_SEC row. So the name
that ends a phase as its side's extreme necessarily BEAT every earlier name when
it became eligible. The set "names that set a new running extreme at their own
eligibility moment" therefore contains ticket 28's Stage A pick with recall 1.0,
and every member is entered at DELTA_SEC of age, which is the only age this
matrix can label exactly. Ticket 28's hold identified that same name two hours
late and could not be priced (T29); ticket 34 showed the arming TIME carries
nothing on its own. This frame keeps the identity and drops the wait.

The problem reduces to: among the new-extreme events of a cell, tell the FINAL
one from the premature ones, using only each event's own row at DELTA_SEC.

PREREGISTRATION (written before the real run, TRAIN decides everything):
- Stage 1, the construction check. Every Stage A per-side extreme must appear as
  a new-extreme event. A recall below 1.0 falsifies the frame and the probe
  refuses rather than proceeding.
- Stage 2, the two numbers that can kill this cheaply.
  (a) Events per cell per side. 1-2 means the sequence collapses to
      enter-first-extreme, already dead by prior-range extension; letter
      `too_few_events`.
  (b) The event oracle: best-y event per cell, cashed at its own DELTA_SEC row.
      It bounds every stopping rule below. Under the TRAIN rung, letter
      `event_ceiling_insufficient` and stop.
- Stage 3, causal arms, only if Stage 2 clears. Each is one entry per phase,
  occupancy as `_cell_pick`, knobs from TRAIN under the plateau rule:
    FIRST         enter the first new-extreme event (the null shape)
    KTH_k         enter the k-th event
    FRACTION_f    enter the first event after fraction f of the phase has run
    MARGIN_m      enter the first event that beats the standing extreme by >= m
                  times the asset's theta
    LAST_BY_f     enter the last event that occurs before fraction f
- Null: shuffle the score within the cell, which destroys which name is an
  event while keeping formation order and y.
- Rung letters carry the noise floor (RESOLVE_SE); a margin inside the day-to-day
  spread letters *_not_resolved, never *_clears_rung.
- 2021 cannot promote. THRESHOLD is read ONCE, for the surviving arm only.

Selftest: python3 tools/probe_extreme_events.py --selftest
Real:     OMP_NUM_THREADS=1 python3 tools/probe_extreme_events.py \
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

from probe_hold_running_extreme import (  # noqa: E402
    PHASE_VWAP_COL, N_DRAW, SHUFFLE_Q, _cash_flag, _cash_stats, _cell_groups,
    _choose_h, _entries_per_day, _plant, _rung_letter, _side_extreme_flag, _stage_a,
)
from probe_crux_prefix_winner import _dawes as _dawes_scores  # noqa: E402
from probe_location_family_screen import _col  # noqa: E402
from probe_path_dedup import PHASE_ELAPSED_COL, _formation_sec, _theta  # noqa: E402
from probe_path_dedup_live import DELTA_SEC, FORM_DELTA, SIDE_COL, VWAP_COL  # noqa: E402
from probe_rho_on_dedup import WIDTH_MULT, _keep_idx  # noqa: E402
from probe_rho_ruler import BLOCKS, PHASE_REMAINING_COL, RUNG_USD  # noqa: E402
from probe_trained_accrual import ELAPSED_COL, ProbeRefusal, load_delta_rows  # noqa: E402

SCHEMA = "QRE2EXTREMEEVENTS1"
SCORE_COLS = (("session", VWAP_COL), ("phase", PHASE_VWAP_COL))
K_GRID = (1, 2, 3, 4, 5)
FRACTION_GRID = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7)
MARGIN_GRID = (0.0, 0.5, 1.0, 2.0, 4.0)
MIN_EVENTS_PER_SIDE = 2.0


def extreme_events(formed: np.ndarray, side: np.ndarray, score: np.ndarray,
                   cell: np.ndarray, long_min: bool, short_min: bool,
                   ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Mark every name that set a new running extreme on its own side.

    Returns (is_event, event_ordinal_within_side, depth_beaten). `depth_beaten`
    is how far the event moved its side's extreme, in score units; it is NaN for
    the first event of a side, which beat nothing.
    """
    is_event = np.full(len(formed), False)
    ordinal = np.full(len(formed), -1, np.int64)
    depth = np.full(len(formed), np.nan)
    eligible = formed + DELTA_SEC
    for g in _cell_groups(cell):
        order = g[np.argsort(eligible[g], kind="stable")]
        best = {1: None, -1: None}
        count = {1: 0, -1: 0}
        for i in order:
            v = float(score[i])
            if not np.isfinite(v):
                continue
            s = 1 if side[i] > 0 else -1
            take_min = long_min if s > 0 else short_min
            cur = best[s]
            if cur is None:
                beat, moved = True, np.nan
            elif take_min:
                beat, moved = v < cur - 1e-12, cur - v
            else:
                beat, moved = v > cur + 1e-12, v - cur
            if beat:
                best[s] = v
                is_event[int(i)] = True
                ordinal[int(i)] = count[s]
                depth[int(i)] = moved
                count[s] += 1
    return is_event, ordinal, depth


def _one_per_cell(mask: np.ndarray, formed: np.ndarray, cell: np.ndarray,
                  last: bool = False) -> np.ndarray:
    """Keep one flagged name per cell: the earliest eligible, or the latest."""
    out = np.full(len(mask), False)
    eligible = formed + DELTA_SEC
    for g in _cell_groups(cell):
        gi = g[mask[g]]
        if not len(gi):
            continue
        pick = gi[int(np.argmax(eligible[gi]) if last else np.argmin(eligible[gi]))]
        out[int(pick)] = True
    return out


def arm_flags(is_event, ordinal, depth, formed, cell, close, theta) -> dict:
    """Every causal arm, each one entry per phase, all prefix-legal."""
    eligible = formed + DELTA_SEC
    phase_frac = np.full(len(formed), np.nan)
    for g in _cell_groups(cell):
        c = close[g][np.isfinite(close[g])]
        limit = float(np.max(c)) if len(c) else np.nan
        if np.isfinite(limit) and limit > 0:
            phase_frac[g] = eligible[g] / limit
    arms = {"FIRST": _one_per_cell(is_event & (ordinal == 0), formed, cell)}
    for k in K_GRID:
        arms[f"KTH_{k}"] = _one_per_cell(is_event & (ordinal == k - 1), formed, cell)
    for f in FRACTION_GRID:
        arms[f"FRACTION_{f:g}"] = _one_per_cell(
            is_event & (phase_frac >= f), formed, cell)
        arms[f"LAST_BY_{f:g}"] = _one_per_cell(
            is_event & (phase_frac <= f), formed, cell, last=True)
    for m in MARGIN_GRID:
        arms[f"MARGIN_{m:g}"] = _one_per_cell(
            is_event & np.isfinite(depth) & (depth >= m * theta), formed, cell)
    return arms


def _zscore_within_cell(v: np.ndarray, cell: np.ndarray) -> np.ndarray:
    """Standardise inside the cell, because only within-phase order matters."""
    out = np.full(len(v), np.nan)
    for g in _cell_groups(cell):
        x = v[g]
        m = np.isfinite(x)
        if m.sum() < 2:
            continue
        sd = float(np.std(x[m]))
        out[g] = (x - float(np.mean(x[m]))) / sd if sd > 0 else 0.0
    return out


def _survivors_from_scan(path: Path | None) -> dict[str, list[tuple[str, float]]]:
    """Top non-clock survivors per asset from the ticket-36 scan receipt.

    `direction` is +1 when a HIGH value marks the winner and -1 when a LOW one
    does, taken from the TRAIN AUC's side of 0.5. No receipt means no Stage 5,
    never a guessed column list.
    """
    if path is None or not path.exists():
        return {}
    data = json.loads(path.read_text())
    out: dict[str, list[tuple[str, float]]] = {}
    for asset, blk in (data.get("assets") or {}).items():
        picks = []
        for row in blk.get("survivors") or []:
            if row.get("clock_family"):
                continue
            picks.append((row["column"], 1.0 if row["train_auc"] > 0.5 else -1.0))
        out[asset] = picks[:8]
    return out


def _best_by_score_per_cell(mask: np.ndarray, rank: np.ndarray,
                            cell: np.ndarray) -> np.ndarray:
    """Enter the highest-ranked flagged name per cell. NOT causal on its own —
    it is the ceiling a live ranker of the same quantity could reach."""
    out = np.full(len(mask), False)
    for g in _cell_groups(cell):
        gi = g[mask[g] & np.isfinite(rank[g])]
        if len(gi):
            out[int(gi[int(np.argmax(rank[gi]))])] = True
    return out


def _recall_up_to_ties(legs: np.ndarray, is_event: np.ndarray, score: np.ndarray,
                       cell: np.ndarray) -> float:
    """Fraction of Stage A leg picks whose score is matched by some event."""
    hit = total = 0
    for g in _cell_groups(cell):
        ev_scores = score[g][is_event[g]]
        for i in g[legs[g]]:
            total += 1
            v = float(score[i])
            if is_event[i] or (len(ev_scores) and np.min(np.abs(ev_scores - v)) <= 1e-9):
                hit += 1
    return float(hit / total) if total else 0.0


def _event_stats(is_event, ordinal, side, cell) -> dict:
    per_side = []
    for g in _cell_groups(cell):
        for s in (1, -1):
            m = g[(side[g] > 0) if s > 0 else (side[g] <= 0)]
            if len(m):
                per_side.append(int(np.sum(is_event[m])))
    arr = np.asarray(per_side) if per_side else np.zeros(1)
    return {"events_per_cell_side_mean": float(np.mean(arr)),
            "events_per_cell_side_median": float(np.median(arr)),
            "events_per_cell_side_p90": float(np.percentile(arr, 90)),
            "event_frac_of_names": float(np.mean(is_event)),
            "n_cell_sides": len(per_side)}


def run(matrix_dir: Path, out_path: Path, *, blocks=BLOCKS, n_draw: int = N_DRAW,
        survivor_cols: dict | None = None, log=print) -> dict:
    rows180 = load_delta_rows(matrix_dir, deltas=(DELTA_SEC,))
    rows0 = load_delta_rows(matrix_dir, deltas=(FORM_DELTA,))
    if not np.isfinite(rows180.y).all():
        raise ProbeRefusal(
            f"{int(np.sum(~np.isfinite(rows180.y)))} non-finite y; expected all finite USD")
    names = rows180.feature_names
    rng = np.random.default_rng(20260823)
    report: dict = {"schema": SCHEMA, "prereg": __doc__,
                    "matrix_receipt": rows180.matrix_receipt,
                    "delta_sec": DELTA_SEC, "n_draw": n_draw, "assets": {}}

    for asset in sorted(set(rows180.asset.tolist())):
        if asset not in WIDTH_MULT:
            continue
        rung = RUNG_USD[asset]
        theta = _theta(asset)
        entry: dict = {"rung_usd": rung, "theta": theta}
        report["assets"][asset] = entry
        packed = {}
        for bname, (lo, hi) in blocks.items():
            idx = np.flatnonzero((rows180.asset == asset) & (rows180.day >= lo)
                                 & (rows180.day <= hi) & (rows180.delta == DELTA_SEC))
            if len(idx) == 0:
                continue
            kept = _keep_idx(rows180, rows0, idx, asset)
            if bname == "train":
                train_kept = kept
            pe = PHASE_ELAPSED_COL if PHASE_ELAPSED_COL in names else ELAPSED_COL
            packed[bname] = dict(
                y=rows180.y[kept], cell=rows180.cell[kept], day=rows180.day[kept],
                elapsed=rows180.elapsed[kept], occupancy=rows180.occupancy[kept],
                side=rows180.x[kept, _col(names, SIDE_COL)].astype(np.float64),
                formed=_formation_sec(rows180.x[kept], names),
                close=(rows180.x[kept, _col(names, pe)].astype(np.float64)
                       + rows180.x[kept, _col(names, PHASE_REMAINING_COL)].astype(np.float64)),
                days=sorted({int(d) for d in rows180.day[kept]}),
                vw={t: rows180.x[kept, _col(names, c)].astype(np.float64)
                    for t, c in SCORE_COLS})
        train = packed.get("train")
        if train is None:
            continue

        best = None
        for tag, _c in SCORE_COLS:
            blk = _stage_a(train["y"], train["side"], train["vw"][tag], train["cell"],
                           train["day"], train["elapsed"], train["occupancy"],
                           train["days"], rung, rng, n_draw)
            if best is None or blk["vwap_better_usd"] > best[1]["vwap_better_usd"]:
                best = (tag, blk)
        tag, a_blk = best
        long_min = a_blk["best_orientation"].startswith("long_min")
        short_min = a_blk["best_orientation"].endswith("short_min")
        entry.update(chosen_score=tag, orientation=a_blk["best_orientation"],
                     stage_a_better_usd=a_blk["vwap_better_usd"])

        # Stage 1 — the construction claim, checked on real data.
        ev, ordn, dep = extreme_events(train["formed"], train["side"], train["vw"][tag],
                                       train["cell"], long_min, short_min)
        legs = (_side_extreme_flag(train["vw"][tag], train["side"], train["cell"],
                                   True, long_min)
                | _side_extreme_flag(train["vw"][tag], train["side"], train["cell"],
                                     False, short_min))
        # Recall UP TO TIES. `_side_extreme_flag` breaks an exact score tie by
        # array index; the event walk requires a strict beat, so on a tie it
        # keeps the earlier-eligible name. Both are the extreme. Comparing
        # identities scores that as a miss (0.99 HG / 0.96 NKD) and would
        # falsify a construction claim that is actually true, so compare the
        # SCORE the two constructions land on.
        recall = _recall_up_to_ties(legs, ev, train["vw"][tag], train["cell"])
        entry["stage1_recall_of_stage_a_legs"] = recall
        if recall < 1.0 - 1e-9:
            entry["letter"] = "construction_falsified"
            log(f"{asset:4s} STAGE1 FALSIFIED recall={recall:.4f}")
            continue

        # Stage 2 — the two numbers that can kill this cheaply.
        stats = _event_stats(ev, ordn, train["side"], train["cell"])
        oracle_flag = np.full(len(ev), False)
        for g in _cell_groups(train["cell"]):
            gi = g[ev[g]]
            if len(gi):
                oracle_flag[int(gi[int(np.argmax(train["y"][gi]))])] = True
        oracle = _cash_stats(oracle_flag, train["y"], train["cell"], train["day"],
                             train["elapsed"], train["occupancy"], train["days"])
        entry["stage2"] = {**stats, "event_oracle": oracle,
                           "event_oracle_letter": _rung_letter(
                               oracle["usd_per_asset_day"], oracle["usd_se"], rung, "event")}
        log(f"{asset:4s} events/cell-side mean={stats['events_per_cell_side_mean']:.2f} "
            f"median={stats['events_per_cell_side_median']:.0f} | event oracle "
            f"${oracle['usd_per_asset_day']:.0f} se ${oracle['usd_se']:.0f} "
            f"{entry['stage2']['event_oracle_letter']} | recall {recall:.3f}")
        if stats["events_per_cell_side_mean"] < MIN_EVENTS_PER_SIDE:
            entry["letter"] = "too_few_events"
            continue
        if oracle["usd_per_asset_day"] < rung:
            entry["letter"] = "event_ceiling_insufficient"
            continue

        # Stage 3-5 — every arm family behind ONE builder, so the null pass and
        # the real pass can never disagree about what an arm means.
        col_specs = []
        for name, direction in (survivor_cols or {}).get(asset, []):
            base = name.replace(" * side", "")
            if base not in names:
                continue
            v = rows180.x[train_kept, _col(names, base)].astype(np.float64)
            if name.endswith(" * side"):
                v = v * train["side"]
            col_specs.append((name, direction * v))
        dawes = _dawes_scores(rows180.x[train_kept], names)

        def build_arms(ev_, ordn_, dep_):
            out = arm_flags(ev_, ordn_, dep_, train["formed"], train["cell"],
                            train["close"], theta)
            if dawes is not None:
                out["DAWES_PICK"] = _best_by_score_per_cell(ev_, dawes, train["cell"])
            out["DEPTH_PICK"] = _best_by_score_per_cell(
                ev_, np.where(np.isfinite(dep_), dep_, -np.inf), train["cell"])
            zs = []
            for name, v in col_specs:
                out[f"COL[{name}]"] = _best_by_score_per_cell(ev_, v, train["cell"])
                zs.append(_zscore_within_cell(v, train["cell"]))
            if len(zs) >= 2:
                out["LOC_DAWES"] = _best_by_score_per_cell(
                    ev_, np.nanmean(np.vstack(zs), axis=0), train["cell"])
            return out

        arms = build_arms(ev, ordn, dep)
        rows = []
        for name, flag in arms.items():
            st = _cash_stats(flag, train["y"], train["cell"], train["day"],
                             train["elapsed"], train["occupancy"], train["days"])
            rows.append({"arm": name, "h_sec": 0.0, **st,
                         "clears_rung": bool(st["usd_per_asset_day"] >= rung),
                         **_entries_per_day(flag, train["day"], train["days"])})
        rows.append({"arm": "ORACLE_PICK", "h_sec": 0.0,
                     **_cash_stats(oracle_flag, train["y"], train["cell"], train["day"],
                                   train["elapsed"], train["occupancy"], train["days"]),
                     "clears_rung": True,
                     **_entries_per_day(oracle_flag, train["day"], train["days"])})
        rows.sort(key=lambda r: -r["usd_per_asset_day"])
        entry["stage3_train"] = rows
        for r in rows[:10]:
            log(f"{asset:4s} arm {r['arm'][:34]:34s} ${r['usd_per_asset_day']:7.0f} "
                f"se ${r['usd_se']:5.0f} ent/d {r['entries_per_day_max']}")
        live = [r for r in rows if r["arm"] != "ORACLE_PICK"]
        top = live[0]     # ORACLE_PICK is hindsight and may never be promoted
        draws = []
        for _ in range(n_draw):
            shuf = train["vw"][tag].copy()
            for g in _cell_groups(train["cell"]):
                shuf[g] = rng.permutation(shuf[g])
            e2, o2, d2 = extreme_events(train["formed"], train["side"], shuf,
                                        train["cell"], long_min, short_min)
            nf = build_arms(e2, o2, d2)[top["arm"]]
            draws.append(_cash_flag(nf, train["y"], train["cell"], train["day"],
                                    train["elapsed"], train["occupancy"], train["days"]))
        entry["stage3_top"] = {**top, "null_mean_usd": float(np.mean(draws)),
                               "null_p975_usd": float(np.quantile(draws, SHUFFLE_Q)),
                               "letter": _rung_letter(top["usd_per_asset_day"],
                                                      top["usd_se"], rung, "arm")}
        log(f"{asset:4s} TOP {top['arm']} ${top['usd_per_asset_day']:.0f} vs null975 "
            f"${np.quantile(draws, SHUFFLE_Q):.0f} {entry['stage3_top']['letter']}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


def selftest() -> int:
    formed = np.array([0.0, 100.0, 200.0, 300.0])
    side = np.ones(4)
    score = np.array([-1.0, -5.0, -2.0, -9.0])       # events at 0, 1, 3
    cell = np.array([7, 7, 7, 7])
    ev, ordn, dep = extreme_events(formed, side, score, cell, True, True)
    assert ev.tolist() == [True, True, False, True], ev
    assert ordn.tolist() == [0, 1, -1, 2], ordn
    assert np.isnan(dep[0]) and abs(dep[1] - 4.0) < 1e-9 and abs(dep[3] - 4.0) < 1e-9, dep

    # THE CONSTRUCTION CLAIM: the final per-side extreme is always an event.
    for seed in range(40):
        r = np.random.default_rng(seed)
        n = int(r.integers(2, 12))
        f = np.sort(r.uniform(0, 5000, n))
        sd = np.where(r.random(n) > 0.5, 1.0, -1.0)
        sc = r.normal(0, 100, n)
        cl = np.zeros(n, np.int64)
        e, _, _ = extreme_events(f, sd, sc, cl, True, True)
        legs = (_side_extreme_flag(sc, sd, cl, True, True)
                | _side_extreme_flag(sc, sd, cl, False, True))
        assert e[legs].all(), (seed, sc, sd, e, legs)

    # Opposite orientation must be honoured on each side independently.
    e2, _, _ = extreme_events(formed, side, score, cell, False, False)
    assert e2.tolist() == [True, False, False, False], e2

    # Arms: one entry per cell, and the shapes differ.
    close = np.full(4, 1000.0)
    arms = arm_flags(ev, ordn, dep, formed, cell, close, theta=1.0)
    for name, flag in arms.items():
        assert int(flag.sum()) <= 1, (name, flag)
    assert arms["FIRST"].tolist() == [True, False, False, False], arms["FIRST"]
    assert arms["KTH_2"].tolist() == [False, True, False, False], arms["KTH_2"]
    assert arms["LAST_BY_0.5"].tolist() == [False, False, False, True], arms["LAST_BY_0.5"]
    assert arms["MARGIN_4"].tolist() == [False, True, False, False], arms["MARGIN_4"]
    assert not arms["MARGIN_0"][0], "the first event beat nothing and has no margin"

    # A shorter phase moves the fraction boundary, so the gate arms must move
    # with it. eligible=[180,280,380,480] over a 800 s phase is frac
    # [0.225, 0.35, 0.475, 0.6]; events are at 0, 1, 3.
    tight = arm_flags(ev, ordn, dep, formed, cell, np.full(4, 800.0), theta=1.0)
    assert tight["LAST_BY_0.5"].tolist() == [False, True, False, False], tight["LAST_BY_0.5"]
    assert tight["FRACTION_0.5"].tolist() == [False, False, False, True], tight["FRACTION_0.5"]
    assert not tight["FRACTION_0.7"].any(), tight["FRACTION_0.7"]

    # Recall up to ties: a tied leg pick that the walk did not mark must still
    # count, because both names ARE the extreme. A mutant that compares
    # identities instead of scores scores this 0.0.
    tie_score = np.array([-5.0, -5.0])
    tie_cell = np.array([3, 3])
    tie_ev = np.array([True, False])
    assert _recall_up_to_ties(np.array([False, True]), tie_ev, tie_score, tie_cell) == 1.0
    assert _recall_up_to_ties(np.array([False, True]), tie_ev,
                              np.array([-5.0, -4.0]), tie_cell) == 0.0

    # The composite picker takes the highest-ranked EVENT, never a non-event.
    rank = np.array([1.0, 2.0, 9.0, 3.0])
    got = _best_by_score_per_cell(ev, rank, cell)
    assert got.tolist() == [False, False, False, True], got

    # Within-cell z-score, and the survivor reader that must not invent columns.
    z = _zscore_within_cell(np.array([1.0, 3.0, 5.0, 10.0]), np.array([1, 1, 2, 2]))
    assert abs(z[0] + 1.0) < 1e-9 and abs(z[1] - 1.0) < 1e-9, z
    assert _survivors_from_scan(None) == {}, "a missing scan receipt must yield nothing"

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _plant(tmp / "p")
        rep = run(tmp / "p", tmp / "p.json", blocks={"train": (20210610, 20210709)},
                  n_draw=4, log=lambda *_: None)
        hg = rep["assets"]["HG"]
        assert hg["stage1_recall_of_stage_a_legs"] == 1.0, hg
        assert "stage2" in hg, hg
    print("selftest OK: events marked and ordinalled, the final per-side extreme is an "
          "event on 40 random cells, arms are one-per-cell and distinct, recall 1.0 on the plant")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--matrix-dir", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--scan-receipt", type=Path, default=None,
                    help="ticket-36 scan receipt; supplies Stage 5's survivor columns")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.matrix_dir is None or a.out is None:
        ap.error("--matrix-dir and --out are required unless --selftest")
    run(a.matrix_dir, a.out, survivor_cols=_survivors_from_scan(a.scan_receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
