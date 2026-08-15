#!/usr/bin/python3
"""PORT M2 — THREE NEW DECISION OBJECTS, PRICED FROM THE EXISTING TENSORS.

THE MANDATE (user, measurement lane, ceilings first)
  The champion (`LMART_HP_NOTF`) chooses ONE THING per (asset, day, phase) CELL:
  which MEMBER gets the seat, at that member's own confirmation second, with the
  contract fixed (ride to phase close, $900 wall).  Three ENLARGED decision
  objects are priced here BEFORE any model work, so that only what shows money
  gets built:

    OBJ-1  JOINT (MEMBER x DELAY) RANKING.  The choice set becomes
           {members} x {D = 0, 60, 120, 300, 600 s}: the same member entered a
           minute later is a DIFFERENT act with a different certificate.
           ORACLE ceiling = per-cell max over the joint set vs per-cell max over
           members at D=0 — the dollar value of the timing freedom alone.
           HONEST read = the champion's own ranker refitted on the joint set.

    OBJ-2  RANK-THEN-GATE-VERIFY.  A two-stage act: the champion nominates, the
           post-window tape [t, t+D] VERIFIES, and a failed verification falls
           through to member #2 (same test) or to no seat at all.

    OBJ-3  OPTIMAL STOPPING IN FLIGHT.  Inside a cell the members ARRIVE in
           time order.  `top-1 per cell` needs the whole cell in hand; the
           stopping policy takes the first arrival whose value beats the fitted
           continuation value for the time remaining.  This prices the
           SEQUENCING freedom (and it is the causal version of the act).

  Plus two flagged loose ends from the final pass: H_TOP1 done right, and
  TabPFN at E3's full training pool.

WHERE EVERY NUMBER COMES FROM (D-006: no second version of anything)
  candidates / labels   `artifacts/cache/port/m3/matrix/matrix.npz` — the
                        committed m3 matrix at candidate grain (1,399,374 rows).
  delayed certificates  `m2_delay._paths_one` IMPORTED AND CALLED, not re-typed:
                        the same `_leg` / `_close_cert` / `_first_sane` /
                        `_post_path` arithmetic that reproduced the committed
                        roster EXACTLY at D=0 on E6 (74,816/74,817, max abs diff
                        0.0).  This lane re-fires that proof over ALL 1,399,374
                        candidates of ALL eras (`--paths` runs `verify_d0`
                        automatically and REFUSES on any mismatch).
  the seating           `m3_walk.topn_takes` / `replay_rows` verbatim at D=0;
                        `replay_delayed` for delayed entries, which is
                        `replay_rows` with the entry second and the certificate
                        read from the delayed tensor.  RED-FIRST: at D=0 it must
                        reproduce `replay_rows` seat-for-seat (`verify_replay`).
  the ranker            `st_lmart` / `st_rank.group_key` — the champion's own
                        code path, same folds, same inner-block HP discipline.
  intervals             `panel_score.cluster_mean` / `cluster_ratio`, CLUSTERED
                        BY DAY (D-036/D-073).

QUARANTINE (standing, binding)
  Everything is developed and selected on E3-E7.  E8 is opened ONCE, blind, at
  the end, and is never an input to any choice.  The 2025-H2 holdout
  (d8 >= 20250701) is sealed and is not this lane's to open.

CLI
  newobj.py --paths   [--workers 8]     the delayed-certificate tensor + verify
  newobj.py --ceilings                  OBJ-1/2/3 ORACLE ceilings + controls
  newobj.py --obj1                      OBJ-1 honest refit (joint ranker)
  newobj.py --obj2                      OBJ-2 rank-then-gate-verify
  newobj.py --obj3                      OBJ-3 optimal stopping
  newobj.py --h-top1                    loose end (a)
  newobj.py --tabpfn-e3                 loose end (b)
  newobj.py --report                    NEWOBJ_CEILINGS.md
"""
import argparse
import json
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m2/seqtest", "/workspace/engine/port_m0",
           "/workspace/engine/port_m1", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import m2_common as MC                    # noqa: E402
import m3_common as M3                    # noqa: E402
import panel_score as PS                  # noqa: E402
import m2_delay as MD                     # noqa: E402

SECTION = ("port m2 NEW DECISION OBJECTS — joint (member x delay) ranking, "
           "rank-then-gate-verify, optimal stopping (E3-E7 develop, E8 one "
           "blind read)")
LANE = "port-m2-newobj"
VERSION = "PORT-M2-NEWOBJ-V1"

SEED = M3.SEED                            # 20260813, the pinned program seed
OUT_ROOT = os.path.join(MC.M2_ROOT, "newobj")
PROV = "/workspace/provenance/port_m2"

# THE MANDATED DELAY GRID.  Not searched, not extended: the brief names it.
DELAYS = (0, 60, 120, 300, 600)
GATE_DELAYS = (60, 120)                   # OBJ-2's mandated verification points

DEV_ERAS = ("E3", "E4", "E5", "E6", "E7")   # develop + select HERE ONLY
BLIND_ERA = "E8"                            # one labeled blind read, at the end
ALL_ERAS = DEV_ERAS + (BLIND_ERA,)

FIELDS = tuple(MD.PATH_FIELDS) + tuple(MD.PP_FIELDS)
FIDX = {f: i for i, f in enumerate(FIELDS)}


def hb(msg):
    sys.stderr.write("[newobj %s] %s\n" % (time.strftime("%H:%M:%S"), msg))
    sys.stderr.flush()


class NewObjRefusal(RuntimeError):
    """A guard fired.  Never downgraded to a warning, never silently filtered."""


# ============================================================ the fixtures ===
_ST = {}


def matrix():
    """The committed m3 matrix, through m3_walk's own loader (holdout guard
    fires at consumption)."""
    if "D" not in _ST:
        import m3_walk as W
        D, p = W.load_matrix()
        _ST["D"] = D
        _ST["path"] = p
        hb("matrix %s: %d candidates x %d features"
           % (p, D["d8"].size, D["X"].shape[1]))
    return _ST["D"]


def era_rows(D, era):
    import st_common as SC
    return np.nonzero(D["era_idx"] == SC.ERA_IDX[era])[0]


def committed_policy():
    """The per-era (unit, N) m3_walk selected on its own inner block — the
    champion spec's schedule, read out of the committed walk.summary.json."""
    if "pol" not in _ST:
        with open(os.path.join(M3.WALK_DIR, "walk.summary.json")) as fh:
            s = json.load(fh)
        _ST["pol"] = {e["era"]: (e["policy_unit"], int(e["topn"]))
                      for e in s["eras"] if e.get("status") == "OK"}
    return _ST["pol"]


# ================================================== STAGE 1: THE PATH TENSOR ==
def _jobs_from_matrix(D):
    """(asset, d8) -> [(row, dec_sec, side, cost_rt)], the shape
    `m2_delay._paths_one` consumes."""
    jobs = {}
    asset = D["asset"].tolist()
    d8 = D["d8"].tolist()
    dec = D["dec_sec"].tolist()
    side = D["side"].tolist()
    cost = D["cost_rt"].tolist()
    for i in range(len(d8)):
        jobs.setdefault((asset[i], int(d8[i])), []).append(
            (i, int(dec[i]), int(side[i]), float(cost[i])))
    return [(a, d, sorted(v)) for (a, d), v in sorted(jobs.items())]


def build_paths(workers=8, out_dir=None, limit_days=None):
    """Delayed-entry certificates + the [t, t+D] path block for EVERY candidate.

    The arithmetic is `m2_delay`'s, imported and called — this module supplies
    the universe (all eras, candidate grain) and nothing else.  `MD.DELAYS` is
    set to this lane's mandated grid before the pool forks, which is the ONLY
    way `_paths_one` is parameterised; the returned records are checked against
    the grid so a silent mismatch is impossible.
    """
    import multiprocessing as mp
    out_dir = out_dir or OUT_ROOT
    os.makedirs(out_dir, exist_ok=True)
    D = matrix()
    n = int(D["d8"].size)
    joblist = _jobs_from_matrix(D)
    if limit_days:
        joblist = joblist[:limit_days]
    MD.DELAYS = tuple(DELAYS)             # inherited by fork; asserted below
    Pm = {Dl: np.full((n, len(FIELDS)), np.nan, dtype=np.float64)
          for Dl in DELAYS}
    t0, errs, done = time.time(), [], 0
    hb("paths: %d sessions, %d candidates, delays=%s, workers=%d"
       % (len(joblist), n, list(DELAYS), workers))
    with mp.Pool(processes=int(workers)) as pool:
        for k, (asset, d8, rows, err) in enumerate(
                pool.imap_unordered(MD._paths_one, joblist, chunksize=1),
                start=1):
            if err:
                errs.append("%s %d %s" % (asset, d8, err))
            for rec in rows:
                if tuple(sorted(rec["d"])) != tuple(sorted(DELAYS)):
                    raise NewObjRefusal(
                        "DELAY GRID MISMATCH: worker returned %s, expected %s"
                        % (sorted(rec["d"]), sorted(DELAYS)))
                i = rec["i"]
                done += 1
                for Dl in DELAYS:
                    r = rec["d"][Dl]
                    Pm[Dl][i] = [r[f] for f in FIELDS]
            if k % 100 == 0 or k == len(joblist):
                el = time.time() - t0
                hb("paths %d/%d sessions %.0fs eta %.0fs filled=%d errs=%d"
                   % (k, len(joblist), el, el / k * (len(joblist) - k), done,
                      len(errs)))
    rec = {"version": VERSION, "n_candidates": n, "n_sessions": len(joblist),
           "n_rows_filled": int(done), "delays": list(DELAYS),
           "fields": list(FIELDS), "errors": errs[:50], "n_errors": len(errs),
           "wall_usd": MD.WALL_USD, "sane_search_cap_sec": MD.SANE_SEARCH_CAP,
           "arithmetic": "m2_delay._paths_one (imported, not re-typed)",
           "secs": round(time.time() - t0, 1)}
    np.savez(os.path.join(out_dir, "paths_all.npz"),
             fields=np.array(FIELDS), delays=np.array(DELAYS),
             **{"D%d" % Dl: Pm[Dl] for Dl in DELAYS})
    with open(os.path.join(out_dir, "paths_all.receipt.json"), "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    hb("paths: %d/%d rows filled, %d session errors, %.0fs"
       % (done, n, len(errs), rec["secs"]))
    return Pm


def load_paths(out_dir=None):
    """The delayed tensor: {D: (n_rows, 34) float64}."""
    if "P" in _ST:
        return _ST["P"]
    p = os.path.join(out_dir or OUT_ROOT, "paths_all.npz")
    if not os.path.exists(p):
        raise NewObjRefusal("no delayed-certificate tensor at %s — run --paths"
                            % p)
    z = np.load(p, allow_pickle=False)
    P = {int(Dl): z["D%d" % Dl] for Dl in z["delays"].tolist()}
    z.close()
    _ST["P"] = P
    return P


# ------------------------------------------------------------- RED FIRST -----
def verify_d0(out_dir=None, tol=0.0):
    """THE RED-FIRST RECEIPT, fired over ALL eras and ALL candidates.

    The D=0 delayed certificate MUST equal the committed matrix certificate
    exactly — value, exit second and wall flag.  The E6 delay lane proved this
    on 74,817 episodes; this fires it on 1,399,374 candidates across E1-E8.
    Any mismatch is a REFUSAL, never a warning.
    """
    D = matrix()
    P = load_paths(out_dir)
    p0 = P[0]
    ok = D["cert_refused"] == 0
    feas = p0[:, FIDX["feasible"]] > 0.5
    cmp_ = ok & feas & np.isfinite(p0[:, FIDX["cert_close"]])
    dv = np.abs(p0[cmp_, FIDX["cert_close"]] - D["cert_close_usd"][cmp_])
    de = np.abs(p0[cmp_, FIDX["exit_sec"]] - D["exit_close_sec"][cmp_])
    # THE TWO WALL FLAGS ARE DIFFERENT QUANTITIES and both are kept (see
    # `m2_delay._close_cert`): the matrix's `walled` column is "the adverse
    # skeleton reached $900 at ANY horizon" (= `wall_hit` here), while the
    # certificate's own `walled` turns only on a wall AT OR BEFORE the phase
    # close.  The reproduction check compares like with like: `wall_hit`.
    dw = np.abs(p0[cmp_, FIDX["wall_hit"]] - D["walled"][cmp_])
    ent = np.abs(p0[cmp_, FIDX["entry_sec"]] - D["dec_sec"][cmp_])
    rec = {"n_candidates": int(D["d8"].size), "n_compared": int(cmp_.sum()),
           "n_infeasible_D0": int((~feas).sum()),
           "n_cert_refused": int((~ok).sum()),
           "max_abs_cert_diff": float(dv.max()) if dv.size else 0.0,
           "max_abs_exit_diff": float(de.max()) if de.size else 0.0,
           "max_abs_walled_diff": float(dw.max()) if dw.size else 0.0,
           "n_entry_shifted": int((ent > 0).sum()),
           "n_cert_mismatch": int((dv > tol).sum()),
           "n_exit_mismatch": int((de > tol).sum()),
           "n_walled_mismatch": int((dw > tol).sum())}
    with open(os.path.join(out_dir or OUT_ROOT, "verify_d0.receipt.json"),
              "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    hb("verify_d0: %d compared, cert mismatch %d, exit mismatch %d, "
       "walled mismatch %d (max |dcert| %.10g)"
       % (rec["n_compared"], rec["n_cert_mismatch"], rec["n_exit_mismatch"],
          rec["n_walled_mismatch"], rec["max_abs_cert_diff"]))
    if rec["n_cert_mismatch"] or rec["n_exit_mismatch"] \
            or rec["n_walled_mismatch"]:
        raise NewObjRefusal(
            "D=0 REPRODUCTION FAILED: %d cert / %d exit / %d wall mismatches "
            "against the committed matrix — the delayed arithmetic is not the "
            "roster's arithmetic and NOTHING downstream may be believed"
            % (rec["n_cert_mismatch"], rec["n_exit_mismatch"],
               rec["n_walled_mismatch"]))
    return rec


# ==================================================== the delayed-entry seat ==
def deployable(D, idx):
    """`m3_walk.topn_takes`' OWN two veto columns, extracted so every arm in
    this file is filtered identically: the D-077-UPDATE news window and the
    held-into-window flag.  A vetoed row can never be seated, so it is removed
    from the choice set BEFORE any ranking or oracle."""
    idx = np.asarray(idx, dtype=np.int64)
    j = D["names"].index("in_news_window")
    idx = idx[D["X"][idx, j] < 0.5]
    k = D["names"].index("nd_held_into_window")
    idx = idx[~(D["X"][idx, k] > 0.5)]
    return idx


def cell_blocks(D, rows):
    """`rows` sorted by (cell, decision second) + the per-cell block bounds."""
    r = np.asarray(rows, dtype=np.int64)
    cell = D["cell"][r]
    order = np.lexsort((D["dec_sec"][r], cell))
    ro, co = r[order], cell[order]
    if ro.size == 0:
        return ro, []
    starts = [0] + (np.flatnonzero(co[1:] != co[:-1]) + 1).tolist()
    stops = starts[1:] + [co.size]
    return ro, list(zip(starts, stops))


def delayed_value(P, dl, D=None):
    """The delayed certificate as a value column over ALL matrix rows; NaN
    wherever the delayed seat does not exist (no SANE second inside the cap, or
    the delay runs past the phase close) or the certificate was refused."""
    v = P[int(dl)][:, FIDX["cert_close"]].copy()
    v[P[int(dl)][:, FIDX["feasible"]] <= 0.5] = np.nan
    if D is not None:
        v[D["cert_refused"] != 0] = np.nan
    return v


def top_per_cell_joint(D, rows, val_by_delay, n, delays=None):
    """TOP-N per (asset, day, phase) CELL over the JOINT choice set
    {members} x {delays}, by `val_by_delay`.

    A MEMBER MAY BE SEATED ONLY ONCE: the joint set enlarges the ACT, it does
    not multiply the seats.  With that rule, top-N over (member, delay) is
    exactly "the N best members, each at its own best delay".

    Returns [(row, delay), ...].
    """
    delays = tuple(delays if delays is not None else sorted(val_by_delay))
    ro, blocks = cell_blocks(D, rows)
    if ro.size == 0:
        return []
    V = np.vstack([np.asarray(val_by_delay[int(d)])[ro] for d in delays])
    V = np.where(np.isfinite(V), V, -np.inf)
    kbest = np.argmax(V, axis=0)
    vbest = V[kbest, np.arange(ro.size)]
    out = []
    for a, b in blocks:
        idx = np.arange(a, b)
        good = idx[np.isfinite(vbest[idx])]
        if good.size == 0:
            continue
        order = good[np.argsort(-vbest[good], kind="stable")][:int(n)]
        for j in order:
            out.append((int(ro[j]), int(delays[int(kbest[j])])))
    return out


def top_per_cell_score(D, rows, score, n):
    """TOP-N per cell by `score`, at D=0 — `m3_walk.topn_takes(unit='cell')`
    expressed as (row, delay) pairs so it replays through the same function."""
    ro, blocks = cell_blocks(D, rows)
    if ro.size == 0:
        return []
    s = np.asarray(score)[ro]
    out = []
    for a, b in blocks:
        idx = np.arange(a, b)
        good = idx[np.isfinite(s[idx])]
        if good.size == 0:
            continue
        order = good[np.lexsort((D["dec_sec"][ro[good]], -s[good]))][:int(n)]
        for j in order:
            out.append((int(ro[j]), 0))
    return out


def replay_delayed(D, seats, P=None, val_by_delay=None):
    """`m3_walk.replay_rows`, with the entry second, the exit second and the
    certificate read from the DELAYED tensor.

    `seats` = iterable of (row, delay).  At delay 0 this is `replay_rows`
    exactly — proved by `verify_replay`, which is red-first for every delayed
    number in this file.

    THE CONTRACT IS UNCHANGED: one position per asset-session, chronological by
    the second the seat is actually TAKEN (the delayed entry second), ride to
    the ORIGINAL phase close, $900 wall re-measured from the new entry.  A take
    whose position is already open is FORFEITED and counted; an infeasible or
    refused certificate is REFUSED, never added.
    """
    P = P if P is not None else load_paths()
    by = {}
    for i, dl in seats:
        i = int(i)
        by.setdefault(str(D["session"][i]), []).append((i, int(dl)))
    ci, ei, xi, fi = (FIDX["cert_close"], FIDX["entry_sec"], FIDX["exit_sec"],
                      FIDX["feasible"])
    rows = []
    for skey in sorted(by):
        cand = []
        for i, dl in by[skey]:
            row = P[dl][i]
            v = (float(val_by_delay[dl][i]) if val_by_delay is not None
                 else float(row[ci]))
            cand.append((int(row[ei]) if row[fi] > 0.5 else -1, i, dl, row, v))
        cand.sort(key=lambda z: (z[0], z[1]))
        open_until = -1
        realised = 0.0
        seated, n_forf, n_ref = [], 0, 0
        for ent, i, dl, row, v in cand:
            if ent < 0 or not np.isfinite(v) or D["cert_refused"][i] != 0:
                n_ref += 1
                continue
            if ent <= open_until:
                n_forf += 1
                continue
            realised += v
            open_until = int(row[xi])
            seated.append((i, dl, v))
        rows.append({"session": skey, "realised": realised,
                     "n_takes": len(cand), "n_seated": len(seated),
                     "n_forfeited": n_forf, "n_refused": n_ref,
                     "seats": seated})
    return rows


def verify_replay(D, ev, score, unit="cell", n=1):
    """RED-FIRST: `replay_delayed` at D=0 must reproduce `m3_walk.replay_rows`
    seat-for-seat and dollar-for-dollar on the same takes."""
    import m3_walk as W
    take = W.topn_takes(D, score, ev, n, deployable=True, unit=unit)
    ref = W.replay_rows(D, take)
    mine = replay_delayed(D, [(int(i), 0) for i in take.tolist()])
    if len(ref) != len(mine):
        raise NewObjRefusal("replay session count %d != %d"
                            % (len(ref), len(mine)))
    dmax = 0.0
    nseat = 0
    for a, b in zip(ref, mine):
        if a["session"] != b["session"]:
            raise NewObjRefusal("replay session order mismatch")
        if [x for x in a["seats"]] != [x[0] for x in b["seats"]]:
            raise NewObjRefusal("replay SEAT mismatch on %s" % a["session"])
        dmax = max(dmax, abs(a["realised"] - b["realised"]))
        nseat += len(a["seats"])
    if dmax > 0.0:
        raise NewObjRefusal("replay realised mismatch, max |diff| %.10g" % dmax)
    hb("verify_replay: %d sessions, %d seats, max |diff| %.10g — "
       "replay_delayed(D=0) == m3_walk.replay_rows" % (len(ref), nseat, dmax))
    return {"n_sessions": len(ref), "n_seats": nseat, "max_abs_diff": dmax}


# ================================================================ scoring =====
_CEIL = {}


def ceilings(D):
    """`m3_walk.dp_ceilings`, cached — the same file the seqtest lane uses."""
    if not _CEIL:
        p = os.path.join(MC.M2_ROOT, "seqtest", "ceilings.json")
        if os.path.exists(p):
            with open(p) as fh:
                _CEIL.update({k: tuple(v) for k, v in json.load(fh).items()})
        else:
            import m3_walk as W
            _CEIL.update(W.dp_ceilings(D))
    return _CEIL


_ORC = {}


def oracle_of(session):
    if session not in _ORC:
        import m3_walk as W
        asset, d8 = session.split("|")
        _ORC[session] = W.oracle_ceiling(asset, int(d8))[0]
    return _ORC[session]


def read_rows(D, rows):
    """`st_run.score_arm`'s reading of a replay, on delayed seats: $/session and
    $/trade with CR1 intervals CLUSTERED BY DAY, plus the capture ratios."""
    if not rows:
        return {"n_sessions": 0}
    y = [r["realised"] for r in rows]
    cl = [int(r["session"].split("|")[1]) for r in rows]
    den_c = [ceilings(D).get(r["session"], (0.0, 0, 0))[0] for r in rows]
    den_o = [oracle_of(r["session"]) for r in rows]
    seats = [s for r in rows for s in r["seats"]]
    cm = PS.cluster_mean(y, cl)
    cap = PS.cluster_ratio(y, den_c, cl)
    orc = PS.cluster_ratio(y, den_o, cl)
    tv = [s[2] for s in seats]
    tcl = [int(D["session"][s[0]].split("|")[1]) for s in seats]
    tm = PS.cluster_mean(tv, tcl) if tv else None
    return {"n_sessions": len(rows),
            "n_takes": int(sum(r["n_takes"] for r in rows)),
            "n_seated": len(seats),
            "n_forfeited": int(sum(r["n_forfeited"] for r in rows)),
            "n_refused": int(sum(r["n_refused"] for r in rows)),
            "usd_per_session": cm["mean"], "ps_lo": cm["ci_lo"],
            "ps_hi": cm["ci_hi"],
            "usd_per_trade": float(np.mean(tv)) if tv else None,
            "pt_lo": tm["ci_lo"] if tm else None,
            "pt_hi": tm["ci_hi"] if tm else None,
            "frac_ge_1000": float(np.mean(np.asarray(tv) >= 1000.0))
            if tv else None,
            "capture_day": cap["ratio"], "cd_lo": cap["ci_lo"],
            "cd_hi": cap["ci_hi"],
            "capture_oracle": orc["ratio"], "co_lo": orc["ci_lo"],
            "co_hi": orc["ci_hi"],
            "delay_mix": {int(d): int(c) for d, c in
                          zip(*np.unique([s[1] for s in seats],
                                         return_counts=True))} if seats else {},
            "_y": y, "_cl": cl, "_den_c": den_c, "_den_o": den_o,
            "_seats": seats}


def pool_reads(parts):
    """Pooled over eras, still clustered by DAY."""
    parts = [p for p in parts if p.get("n_sessions")]
    if not parts:
        return {"n_sessions": 0}
    y = [v for p in parts for v in p["_y"]]
    cl = [v for p in parts for v in p["_cl"]]
    dc = [v for p in parts for v in p["_den_c"]]
    do = [v for p in parts for v in p["_den_o"]]
    seats = [s for p in parts for s in p["_seats"]]
    cm = PS.cluster_mean(y, cl)
    cap = PS.cluster_ratio(y, dc, cl)
    orc = PS.cluster_ratio(y, do, cl)
    tv = [s[2] for s in seats]
    return {"n_sessions": len(y), "n_seated": len(seats),
            "usd_per_session": cm["mean"], "ps_lo": cm["ci_lo"],
            "ps_hi": cm["ci_hi"],
            "usd_per_trade": float(np.mean(tv)) if tv else None,
            "frac_ge_1000": float(np.mean(np.asarray(tv) >= 1000.0))
            if tv else None,
            "capture_day": cap["ratio"], "cd_lo": cap["ci_lo"],
            "cd_hi": cap["ci_hi"],
            "capture_oracle": orc["ratio"], "co_lo": orc["ci_lo"],
            "co_hi": orc["ci_hi"],
            "delay_mix": {int(d): int(c) for d, c in
                          zip(*np.unique([s[1] for s in seats],
                                         return_counts=True))} if seats else {},
            "_y": y, "_cl": cl}


def paired_sessions(rows_a, rows_b):
    """Paired per-session (a - b) over the sessions BOTH arms replayed."""
    A = {r["session"]: r["realised"] for r in rows_a}
    B = {r["session"]: r["realised"] for r in rows_b}
    keys = sorted(set(A) & set(B))
    d = [A[k] - B[k] for k in keys]
    cl = [int(k.split("|")[1]) for k in keys]
    if not d:
        return {"n": 0}
    cm = PS.cluster_mean(d, cl)
    return {"n": len(d), "delta": cm["mean"], "lo": cm["ci_lo"],
            "hi": cm["ci_hi"]}


# ================================================================== output ===
def _r(v, nd=2):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return ""
    return round(float(v), nd)


def write_tsv(name, columns, rows, extra=()):
    os.makedirs(PROV, exist_ok=True)
    p = os.path.join(PROV, name)
    with open(p, "w") as fh:
        fh.write("# PORT M2 %s (lane=%s; version=%s; seed=%d)\n"
                 % (SECTION, LANE, VERSION, SEED))
        fh.write("# E8 QUARANTINE: every fit, threshold and selection in this "
                 "file is made on E3-E7 only; E8 rows are ONE labeled blind "
                 "read and were never an input to any choice.\n")
        for e in extra:
            fh.write("# %s\n" % e)
        fh.write("\t".join(str(c) for c in columns) + "\n")
        for r in rows:
            fh.write("\t".join("" if v is None else str(v) for v in r) + "\n")
    hb("wrote %s (%d rows)" % (p, len(rows)))
    return p


def save_json(name, obj):
    os.makedirs(OUT_ROOT, exist_ok=True)
    p = os.path.join(OUT_ROOT, name)
    with open(p, "w") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True, default=str)
    return p


def load_json(name):
    p = os.path.join(OUT_ROOT, name)
    if not os.path.exists(p):
        return None
    with open(p) as fh:
        return json.load(fh)


# ============================================== STAGE 2: THE ORACLE CEILINGS ==
CHAMP_TAG = "LMART_HP_NOTF"


def champ_score(tag=CHAMP_TAG):
    """The committed champion's out-of-sample score column, as saved by the arm
    that produced `CHAMPION_FREEZE_CANDIDATE.md`."""
    p = os.path.join(MC.M2_ROOT, "seqtest", "scores", "%s.npz" % tag)
    z = np.load(p, allow_pickle=False)
    champ, win = z["champ"], z["win"]
    z.close()
    if not np.array_equal(np.nan_to_num(champ), np.nan_to_num(win)):
        raise NewObjRefusal("%s is a two-head arm; this lane expects the "
                            "single-column champion" % tag)
    return champ


def displaced_profile(D, V, rng):
    """THE RED-FIRST CONTROL FOR THE TIMING FREEDOM.

    An oracle over a JOINT set is larger than an oracle over its D=0 slice by
    construction — part of that gain is nothing but the maximum of five noisy
    variates.  This control isolates that part: every candidate keeps its OWN
    D=0 certificate and its own feasibility, but its DELAY INCREMENTS
    (v[D] - v[0]) are those of a DIFFERENT candidate drawn from the same
    (era, asset).  If the joint ceiling is only max-of-five selection noise, the
    displaced ceiling matches it; if the timing freedom is real structure that
    the cell's own tape carries, the real ceiling stands above the displaced one.
    """
    n = D["d8"].size
    out = {0: V[0].copy()}
    for d in DELAYS[1:]:
        out[int(d)] = np.full(n, np.nan)
    key = D["era_idx"].astype(np.int64) * 100 + D["asset_idx"].astype(np.int64)
    for k in np.unique(key):
        idx = np.nonzero(key == k)[0]
        perm = idx[rng.permutation(idx.size)]
        for d in DELAYS[1:]:
            inc = V[int(d)][perm] - V[0][perm]
            out[int(d)][idx] = V[0][idx] + inc
    return out


def _arm_rows(D, era, name, rows, extra=None):
    a = read_rows(D, rows)
    a["era"] = era
    a["arm"] = name
    if extra:
        a.update(extra)
    return a


def stage_ceilings(eras=ALL_ERAS):
    """OBJ-1 and OBJ-2 ORACLE ceilings, per era, on the champion's own schedule.

    Every arm is seated through `replay_delayed` on the per-era (unit, N) that
    `m3_walk` selected on its own inner block — the champion spec's schedule.
    Nothing here is fitted, so nothing here can leak; the ORACLE arms are
    hindsight bounds by construction and are labelled as such.
    """
    import m3_walk as W
    D = matrix()
    P = load_paths()
    pol = committed_policy()
    s = champ_score()
    V = {int(d): delayed_value(P, d, D) for d in DELAYS}
    rng = np.random.RandomState(SEED)
    VD = displaced_profile(D, V, rng)
    rnd_score = np.random.RandomState(SEED + 7).rand(D["d8"].size)

    verify = None
    rows_tsv, per_arm, delta_tsv = [], {}, []
    for era in eras:
        ev = deployable(D, era_rows(D, era))
        u, n = pol.get(era, ("cell", 1))
        if u != "cell":
            raise NewObjRefusal("unexpected committed unit %r for %s" % (u, era))
        if verify is None:
            verify = verify_replay(D, era_rows(D, era), s, unit=u, n=n)
        takes = {}
        takes["CHAMP_D0"] = top_per_cell_score(D, ev, s, n)
        takes["RANDOM_MEMBER_D0"] = top_per_cell_score(D, ev, rnd_score, n)
        takes["ORACLE_MEMBER_D0"] = top_per_cell_joint(D, ev, V, n, (0,))
        for d in DELAYS[1:]:
            takes["ORACLE_MEMBER_D%d" % d] = top_per_cell_joint(
                D, ev, V, n, (int(d),))
        takes["ORACLE_JOINT"] = top_per_cell_joint(D, ev, V, n, DELAYS)
        takes["ORACLE_JOINT_DISPLACED"] = top_per_cell_joint(
            D, ev, VD, n, DELAYS)
        # OBJ-2's ceiling: the champion nominates the top TWO members of the
        # cell; a PERFECT verifier then picks the better of {m1@D, m2@D} or
        # takes no seat at all.  This is the exact bound on the two-stage act.
        top2 = _top2_by_score(D, ev, s)
        for d in (0,) + GATE_DELAYS:
            # the full two-stage act: {m1@D, m2@D, no seat}
            takes["ORACLE_GATE_D%d" % d] = _oracle_gate_takes(
                top2, V, int(d), members=2, abstain=True)
            # DECOMPOSITION: abstention alone (no fall-through), and the
            # fall-through alone (no abstention).  D=0 isolates how much of the
            # gate ceiling is the DELAY and how much is just being allowed to
            # decline or to swap to member #2.
            takes["ORACLE_ABSTAIN_D%d" % d] = _oracle_gate_takes(
                top2, V, int(d), members=1, abstain=True)
            takes["ORACLE_PICK2_D%d" % d] = _oracle_gate_takes(
                top2, V, int(d), members=2, abstain=False)
        rep = {}
        for name, tk in takes.items():
            vb = VD if name.endswith("_DISPLACED") else None
            rep[name] = replay_delayed(D, tk, P, val_by_delay=vb)
            a = _arm_rows(D, era, name, rep[name])
            per_arm.setdefault(name, []).append(a)
            rows_tsv.append([name, era, n, a["n_takes"], a["n_seated"],
                             _r(a["usd_per_session"]), _r(a["ps_lo"]),
                             _r(a["ps_hi"]), _r(a["usd_per_trade"]),
                             _r(a["frac_ge_1000"], 4),
                             _r(a["capture_oracle"], 4),
                             json.dumps(a["delay_mix"])])
        for x, y in (("ORACLE_JOINT", "ORACLE_MEMBER_D0"),
                     ("ORACLE_JOINT_DISPLACED", "ORACLE_MEMBER_D0"),
                     ("ORACLE_MEMBER_D0", "CHAMP_D0"),
                     ("ORACLE_GATE_D0", "CHAMP_D0"),
                     ("ORACLE_GATE_D60", "CHAMP_D0"),
                     ("ORACLE_GATE_D120", "CHAMP_D0"),
                     ("ORACLE_ABSTAIN_D0", "CHAMP_D0"),
                     ("ORACLE_PICK2_D0", "CHAMP_D0"),
                     ("ORACLE_GATE_D60", "ORACLE_GATE_D0"),
                     ("ORACLE_GATE_D120", "ORACLE_GATE_D0")):
            pd = paired_sessions(rep[x], rep[y])
            delta_tsv.append([era, x, y, pd.get("n"), _r(pd.get("delta")),
                              _r(pd.get("lo")), _r(pd.get("hi"))])
        hb("ceilings %s: champ %s | member-oracle %s | joint-oracle %s | "
           "displaced %s"
           % (era, _r(per_arm["CHAMP_D0"][-1]["usd_per_session"]),
              _r(per_arm["ORACLE_MEMBER_D0"][-1]["usd_per_session"]),
              _r(per_arm["ORACLE_JOINT"][-1]["usd_per_session"]),
              _r(per_arm["ORACLE_JOINT_DISPLACED"][-1]["usd_per_session"])))
    for name, parts in sorted(per_arm.items()):
        dev = pool_reads([a for a in parts if a["era"] in DEV_ERAS])
        rows_tsv.append([name, "POOLED_E3-E7", "", "", dev.get("n_seated"),
                         _r(dev.get("usd_per_session")), _r(dev.get("ps_lo")),
                         _r(dev.get("ps_hi")), _r(dev.get("usd_per_trade")),
                         _r(dev.get("frac_ge_1000"), 4),
                         _r(dev.get("capture_oracle"), 4),
                         json.dumps(dev.get("delay_mix", {}))])
    write_tsv("NEWOBJ_CEILINGS.tsv",
              ["arm", "era", "topn", "n_takes", "n_seated", "usd_per_session",
               "ps_lo", "ps_hi", "usd_per_trade", "frac_ge_1000",
               "capture_oracle", "delay_mix"], rows_tsv,
              extra=["ORACLE_* arms are HINDSIGHT BOUNDS: the per-cell choice "
                     "is made with the realised certificate in hand.  They are "
                     "ceilings, never results.",
                     "CHAMP_D0 is the committed champion LMART_HP_NOTF, "
                     "re-seated here through replay_delayed at D=0 (proved "
                     "seat-for-seat identical to m3_walk.replay_rows).",
                     "ORACLE_JOINT_DISPLACED is the red-first control for the "
                     "timing freedom: own D=0 certificate, ANOTHER candidate's "
                     "delay increments.  The part of the joint ceiling it "
                     "reproduces is max-of-five selection noise, not timing."])
    write_tsv("NEWOBJ_CEILING_DELTAS.tsv",
              ["era", "arm", "vs", "n_sessions", "delta_usd_per_session",
               "lo", "hi"], delta_tsv,
              extra=["Paired per-session differences (same session list both "
                     "sides), CR1 intervals clustered by DAY."])
    save_json("ceilings.json",
              {"verify_replay": verify,
               "per_arm": {k: [{kk: vv for kk, vv in a.items()
                                if not kk.startswith("_")} for a in v]
                           for k, v in per_arm.items()}})
    return per_arm


def _top2_by_score(D, ev, s):
    """The champion's ranked top TWO members of every cell — OBJ-2's nominee
    and its fall-through."""
    ro, blocks = cell_blocks(D, ev)
    sc = np.asarray(s)[ro]
    out = []
    for a, b in blocks:
        idx = np.arange(a, b)
        good = idx[np.isfinite(sc[idx])]
        if good.size == 0:
            continue
        order = good[np.lexsort((D["dec_sec"][ro[good]], -sc[good]))]
        out.append((int(ro[order[0]]),
                    int(ro[order[1]]) if order.size > 1 else None))
    return out


def _oracle_gate_takes(top2, V, dl, members=2, abstain=True):
    """A PERFECT verifier over the champion's own top-`members` of each cell,
    with (`abstain=True`) or without the option of taking no seat at all —
    OBJ-2's ceiling and its decomposition."""
    out = []
    for pair in top2:
        cand = [m for m in pair[:members] if m is not None]
        best, who = (0.0 if abstain else -np.inf), None
        for m in cand:
            v = V[dl][m]
            if np.isfinite(v) and v > best:
                best, who = float(v), m
        if who is not None:
            out.append((who, dl))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit-days", type=int, default=None)
    ap.add_argument("--ceilings", action="store_true")
    ap.add_argument("--eras", default=",".join(ALL_ERAS))
    a = ap.parse_args()
    eras = tuple(e for e in a.eras.split(",") if e)
    if a.paths:
        build_paths(workers=a.workers, limit_days=a.limit_days)
        _ST.pop("P", None)
        verify_d0()
    elif a.verify:
        verify_d0()
    elif a.ceilings:
        stage_ceilings(eras=eras)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
