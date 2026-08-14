#!/usr/bin/python3
"""PORT M3 — THE WALK-FORWARD EVALUATION (D-058 / D-084 / D-085).

    "expanding-window era models (E1->E8 through 2025-06-30), each era scored
     OUT-OF-SAMPLE on: one-position phase-close replay $/day vs the D-048 bars
     ($2,000/asset; $1,500 thin floor), per-trade stats vs D-021, capture of the
     day/oracle ceilings, the per-era curve, adaptation latencies at the D-084
     break points, per-asset AND pooled, session-clustered inference,
     mirror_paired for anything directional, one Holm family."      — the brief

THE LADDER
  Model_k is fitted on every era STRICTLY BEFORE era k and scored on era k.
  Nothing else is ever in the training block, so every reported number is
  out-of-sample by construction and the D-084 break latencies are readable off
  the ladder itself: at each named break the era's model has seen NO post-break
  data at all.  E1's training block is the PRE_E1 tape (2021-H1, out of
  protocol scope for the discretionary program) and is FLAGGED as such — an
  E1 cell built on a warm-up block is reported with its caveat, never silently.
  E8 = 2025-01-01..06-30 = THE GATE-2025H1 ECHO, the final eval cell.  The
  D-058 pre-exam holdout is never in the matrix at all (m3_matrix's guard).

THE POLICY (fixed before any era is scored)
  1. score every candidate with the era's model on the PRIMARY target;
  2. DEPLOYABLE reading: drop every candidate inside the D-077-UPDATE
     restricted window (|minutes to the nearest scheduled release| <= 10) —
     the prop-firm hard veto, applied as a veto and not as a feature;
  3. take the TOP-N per SELECTION UNIT by score — unit in {the (asset,session)
     day, the CC-M2-17.1 (asset,phase) CELL} and N in {1,2,3,5,8}, the pair
     selected on the training block's own inner validation split, never on the
     eval era.  This is the ONE design choice the brief left open and it is
     declared, FIT-selected, and shipped with its full sensitivity curve;
  4. replay one position per asset per session, chronologically, at the walled
     PHASE-CLOSE certificate (CC-M2-10.3, and CC-M2-21.4's greedy reading is
     THE LAW with the DP seat-split as its companion diagnostic).

WHAT IS COMPARED
  * the D-048 bars: $2,000/session/asset, $1,500 weak-era floor;
  * BASE_EARLIEST, the frozen zero-intelligence mechanical arm (the earliest
    member of each EPISODE_CAUSAL episode), replayed identically and paired
    per session — CC-M2-4.1's "judgment must beat rules", now "the model must
    beat rules";
  * the day ceiling (one-position DP over EVERY candidate) and the ORACLE
    ceiling (one-position DP over the day's ANCHORED oracle legs);
  * the SIDE-MIRRORED model, under m2_common.mirror_paired — the era-scale
    paired test, because any claim that the model picks the right SIDE is
    directional (R59).

Run:
  m3_walk.py --run [--matrix DIR] [--nthread N]
"""
import argparse
import json
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m0", "/workspace/engine/port_m1",
           "/workspace/engine/port_m2", "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import xgboost as xgb                     # noqa: E402
import m3_common as M3                    # noqa: E402
import m3_matrix as MX                    # noqa: E402
import m2_common as MC                    # noqa: E402
import panel_score as PS                  # noqa: E402
import assemble as A                      # noqa: E402
import baseline_replay as BR              # noqa: E402
import c_c_roster as CC                   # noqa: E402

SECTION = "M3.2 walk-forward evaluation (expanding-window era ladder)"

# ---------------------------------------------------------------- the HP ----
# THE S4 PINNED-HP DISCIPLINE, IMPORTED RATHER THAN RE-TYPED (D-006): the grid,
# the round cap and the inner fraction are `s4_confirm`'s own committed
# constants, so a drift there is a drift here and cannot be papered over by a
# second copy.  The brief's "small documented search on FIT only" is satisfied
# with room to spare — the whole 32-cell S4 grid costs ~3s per cell on this
# corpus, so the search is the S4 search, unshrunk.  It runs ONLY inside the
# training block (its last 20% of sessions is the inner validation, exactly
# s4_confirm._inner_split); the eval era is never touched by selection.
sys.path.insert(0, "/workspace/engine/port_m1b")
import s4_confirm as S4C                  # noqa: E402

HP_SEARCH = tuple(dict(c) for c in S4C.HP_GRID)
ROUNDS_MAX = int(S4C.ROUNDS_MAX)
EARLY_STOP = 20
INNER_FRACTION = float(S4C.INNER_FRACTION)
HP_FIXED = {"seed": M3.SEED}

# THE POLICY GRID, selected on the inner block only.  Two axes:
#   UNIT  the selection unit — the (asset, session) day, or the CC-M2-17.1
#         (asset, phase) CELL, which is the program's own invariant decision
#         unit (CC-M2-16.1: "the invariant unit is the (ASSET, PHASE) CELL");
#   N     how many candidates of that unit the policy takes.
# A session-unit policy can spend all its takes inside one hour; a cell-unit
# policy spreads them across the day's three cells by construction.  Which one
# banks more is measured on FIT, never assumed.
TOPN_GRID = (1, 2, 3, 5, 8)
UNIT_GRID = ("session", "cell")

PRIMARY_TARGET = "y_retg_rank_phase"
SIDE_TARGETS = ("y_winner", "y_t1_episode")

MIRROR_MIN_SESSIONS = MC.MIRROR_MIN_SESSIONS


# =============================================================== the matrix ==
def load_matrix(path=None):
    p = os.path.join(path or M3.MATRIX_DIR, "matrix.npz")
    z = np.load(p, allow_pickle=False)
    D = {k: z[k] for k in z.files}
    z.close()
    M3.check_holdout(D["d8"])              # the guard, again, at consumption
    D["asset"] = np.array([M3.ASSET_ORDER[i] for i in D["asset_idx"].tolist()])
    D["session"] = np.array(["%s|%08d" % (a, d) for a, d in
                             zip(D["asset"].tolist(), D["d8"].tolist())])
    D["cell"] = np.array(["%s|%d" % (s, p) for s, p in
                          zip(D["session"].tolist(), D["phase_dec"].tolist())])
    D["names"] = [str(x) for x in D["feature_names"].tolist()]
    return D, p


# ============================================================ the ceilings ===
def dp_ceilings(D):
    """One-position DP ceiling per session, over EVERY candidate of it.

    Reuses the FROZEN c_c_roster.dp_schedule and the matrix's own certificate
    columns (which pattern_lib computed with c_c_roster.certificates — the same
    function panel_score.dp_ceiling calls, so this is the same number by the
    same code, computed once instead of 1.5M times).
    """
    out = {}
    order = np.lexsort((D["dec_sec"], D["session"]))
    s = D["session"][order]
    starts = [0] + (np.flatnonzero(s[1:] != s[:-1]) + 1).tolist()
    stops = starts[1:] + [s.size]
    dec_all = D["dec_sec"].astype(np.int64)
    ex_all = D["exit_close_sec"].astype(np.int64)
    cc_all = D["cert_close_usd"].astype(np.float64)
    ok_all = D["cert_refused"] == 0
    for a, b in zip(starts, stops):
        idx = order[a:b]
        keep = idx[ok_all[idx]]
        # .tolist() once per session, never numpy scalar indexing per row:
        # the per-element form spent minutes on 1.4M candidates.
        dec = dec_all[keep].tolist()
        ex = ex_all[keep].tolist()
        cv = cc_all[keep].tolist()
        rid = keep.tolist()
        items = list(zip(dec, ex, cv, dec, rid, rid))
        total, chosen = CC.dp_schedule(items)
        out[str(s[a])] = (float(total), len(chosen), int(idx.size))
    return out


_ORACLE = {}


def oracle_ceiling(asset, d8):
    """One-position DP over the day's ANCHORED oracle legs (travel $)."""
    key = (asset, int(d8))
    if key in _ORACLE:
        return _ORACLE[key]
    legs = A.oracle_legs(asset, int(d8))
    items = []
    for k, r in enumerate(legs):
        try:
            s0 = int(float(r["leg_start_sec"]))
            s1 = int(float(r["leg_end_sec"]))
            v = float(r["travel_usd"])
        except Exception:                  # noqa: BLE001 — a refused leg
            continue
        if not np.isfinite(v) or s1 < s0:
            continue
        items.append((s0, s1, v, s0, k, k))
    total, chosen = CC.dp_schedule(items) if items else (0.0, [])
    _ORACLE[key] = (float(total), len(chosen), len(legs))
    return _ORACLE[key]


# ============================================================== the replay ===
def replay_rows(D, take_idx, side_override=None):
    """One-position chronological replay of `take_idx`, per (asset, session).

    `side_override` (optional) maps a taken row to the row that should actually
    be seated instead (used by the mirror and by the side leg of the seat/side/
    moment decomposition).  The SUBSTITUTED row's own decision second drives
    both the chronological order and the occupancy check — a substitute is
    entered when IT fires, not when the row it replaced did.  A take whose
    position is already open is FORFEITED and counted; a refused certificate is
    REFUSED, never added (R132).
    """
    a = np.asarray(take_idx, dtype=np.int64)
    by = {}
    if a.size:
        sess = D["session"][a].tolist()
        for i, sk in zip(a.tolist(), sess):
            j = i if side_override is None else side_override.get(i, i)
            by.setdefault(sk, []).append((int(D["dec_sec"][j]), j))
    rows = []
    for skey in sorted(by):
        seq = sorted(by[skey])
        open_until = -1
        realised = 0.0
        seats = []
        n_forf = n_ref = 0
        for dec, j in seq:
            if D["cert_refused"][j] != 0:
                n_ref += 1
                continue
            if dec <= open_until:
                n_forf += 1
                continue
            realised += float(D["cert_close_usd"][j])
            open_until = int(D["exit_close_sec"][j])
            seats.append(j)
        rows.append({"session": skey, "realised": realised,
                     "n_takes": len(seq), "n_seated": len(seats),
                     "n_forfeited": n_forf, "n_refused": n_ref,
                     "seats": seats})
    return rows


def per_trade_stats(D, seats):
    """D-021 acceptance: expectancy, MAE, the $1,000 bar, walls."""
    if not seats:
        return {"n": 0}
    s = np.asarray(seats, dtype=np.int64)
    cert = D["cert_close_usd"][s]
    mae = D["mae_before_argmax"][s]
    return {"n": int(s.size),
            "expectancy_usd": float(np.nanmean(cert)),
            "median_usd": float(np.nanmedian(cert)),
            "win_rate": float(np.nanmean(cert > 0)),
            "frac_ge_1000": float(np.nanmean(cert >= 1000.0)),
            "frac_ge_600": float(np.nanmean(cert >= 600.0)),
            "mean_mae_usd": float(np.nanmean(mae)),
            "p90_mae_usd": float(np.nanpercentile(mae[np.isfinite(mae)], 90))
            if np.isfinite(mae).any() else float("nan"),
            "walled_rate": float(np.nanmean(D["walled"][s] > 0)),
            "d021_expectancy_ok": bool(np.nanmean(cert)
                                       >= M3.BAR_TRADE_MIN_USD),
            "d021_mae_bar_usd": (M3.BAR_MAE_AT_HIGH_USD
                                 if np.nanmean(cert)
                                 >= M3.BAR_EXPECTANCY_FOR_HIGH_MAE_USD
                                 else M3.BAR_MAE_AT_MIN_USD),
            }


def daily_drawdown(D, rows):
    """D-030: the worst intra-session drawdown of the seated P&L sequence."""
    dds = []
    for r in rows:
        if not r["seats"]:
            dds.append(0.0)
            continue
        pnl = D["cert_close_usd"][np.asarray(r["seats"], dtype=np.int64)]
        cum = np.cumsum(pnl)
        peak = np.maximum.accumulate(np.concatenate([[0.0], cum]))[:-1]
        dds.append(float(np.max(np.maximum(peak - cum, 0.0))))
    if not dds:
        return {"n_sessions": 0}
    a = np.asarray(dds)
    return {"n_sessions": int(a.size), "mean_dd_usd": float(a.mean()),
            "p90_dd_usd": float(np.percentile(a, 90)),
            "max_dd_usd": float(a.max()),
            "frac_sessions_over_bar": float((a > M3.BAR_DAILY_DD_USD).mean())}


# ================================================================= the fit ===
def inner_split(d8_train):
    """s4_confirm._inner_split: the training block's last 20% of SESSIONS."""
    u = np.unique(d8_train)
    if u.size < 10:
        return None
    cut = u[int(round(u.size * (1.0 - INNER_FRACTION))) - 1]
    return int(cut)


def fit_one(X, y, tr, va, nthread, feature_names=None):
    """The S4 discipline: search on (tr -> va), keep the best by Spearman."""
    ytr, yva = y[tr], y[va]
    dtr = xgb.DMatrix(X[tr], label=ytr, feature_names=feature_names)
    dva = xgb.DMatrix(X[va], label=yva, feature_names=feature_names)
    best, best_cfg, best_rounds = -np.inf, None, ROUNDS_MAX
    for hp in HP_SEARCH:
        cfg = dict(hp)
        cfg.update(HP_FIXED)               # the pinned seed wins
        cfg["nthread"] = int(nthread)      # ... and so does the thread budget
        b = xgb.train(cfg, dtr, ROUNDS_MAX, evals=[(dva, "inner")],
                      early_stopping_rounds=EARLY_STOP, verbose_eval=False)
        p = b.predict(dva, iteration_range=(0, b.best_iteration + 1))
        r = M3._rho(p, yva)
        if np.isfinite(r) and r > best:
            best, best_cfg, best_rounds = float(r), cfg, b.best_iteration + 1
    if best_cfg is None:
        return None
    return {"cfg": best_cfg, "rounds": int(best_rounds),
            "inner_rho": float(best)}


def select_policy(D, score, rows_idx, ceilings):
    """(unit, N) for the TOP-N policy, chosen on the inner block ONLY."""
    best, best_val = (UNIT_GRID[0], TOPN_GRID[0]), -np.inf
    curve = []
    for unit in UNIT_GRID:
        for n in TOPN_GRID:
            take = topn_takes(D, score, rows_idx, n, deployable=True,
                              unit=unit)
            rr = replay_rows(D, take)
            val = (sum(x["realised"] for x in rr) / len(rr)) if rr else None
            curve.append((unit, n,
                          (round(float(val), 2) if val is not None else None),
                          len(rr)))
            if val is not None and val > best_val:
                best, best_val = (unit, n), val
    return best, curve


def _unit_pct(D, score, idx):
    """Within-(asset, session) percentile of `score` over `idx` (NaN elsewhere)."""
    out = np.full(score.size, np.nan)
    a = np.asarray(idx, dtype=np.int64)
    sess = D["session"][a]
    order = np.argsort(sess, kind="stable")
    ao = a[order]
    so = sess[order]
    starts = [0] + (np.flatnonzero(so[1:] != so[:-1]) + 1).tolist()
    stops = starts[1:] + [so.size]
    for lo, hi in zip(starts, stops):
        sel = ao[lo:hi]
        out[sel] = MX._rank_pct(score[sel])
    return out


def topn_takes(D, score, rows_idx, n, deployable=True, unit="session"):
    """TOP-N per selection unit by score.  DEPLOYABLE = the D-077 veto on."""
    idx = np.asarray(rows_idx, dtype=np.int64)
    if deployable:
        j = D["names"].index("in_news_window")
        idx = idx[D["X"][idx, j] < 0.5]
        k = D["names"].index("nd_held_into_window")
        held = D["X"][idx, k]
        idx = idx[~(held > 0.5)]
    s = score[idx]
    ok = np.isfinite(s)
    idx, s = idx[ok], s[ok]
    if idx.size == 0:
        return np.zeros(0, dtype=np.int64)
    sess = D["session"][idx] if unit == "session" else D["cell"][idx]
    order = np.lexsort((D["dec_sec"][idx], -s, sess))
    so = sess[order]
    starts = [0] + (np.flatnonzero(so[1:] != so[:-1]) + 1).tolist()
    stops = starts[1:] + [so.size]
    out = []
    for a, b in zip(starts, stops):
        out.extend(idx[order[a:min(a + int(n), b)]].tolist())
    return np.sort(np.asarray(out, dtype=np.int64))


# ======================================================= mirrors / decomp ====
def mirror_map(D):
    """THE SIGN-FLIPPED MIRROR of every row: the nearest OPPOSITE-SIDE candidate
    inside the same (asset, session, phase) CELL.

    R59's era-scale mirror law needs "the estimator's value on that session
    MINUS its sign-flipped mirror's value on the same session".  The roster's
    dedup key is (session, decision_second, side), and long/short candidates
    almost never fire on the SAME second — an exact-second twin exists for only
    2,508 of 1,399,374 rows, which would make the mirror test vacuous.  So the
    mirror is the nearest opposite-side candidate of the SAME CELL within
    K*(asset, side) seconds, K* being the frozen EPISODE_CAUSAL link constant
    read from the committed episode_v2 receipt (baseline_replay.episode_pins).
    Rows with no mirror inside K* are UNMIRRORABLE and are counted, never
    silently paired with something further away.
    """
    kst, _spn = BR.episode_pins(check=True)
    out = {}
    n_un = 0
    cell = D["cell"]
    order = np.lexsort((D["dec_sec"], cell))
    co = cell[order]
    starts = [0] + (np.flatnonzero(co[1:] != co[:-1]) + 1).tolist()
    stops = starts[1:] + [co.size]
    for a, b in zip(starts, stops):
        idx = order[a:b]
        dec = D["dec_sec"][idx].astype(np.int64)
        side = D["side"][idx].astype(np.int64)
        asset = str(D["asset"][idx[0]])
        for want in (1, -1):
            src = np.nonzero(side == want)[0]
            dst = np.nonzero(side == -want)[0]
            if src.size == 0 or dst.size == 0:
                n_un += int(src.size)
                continue
            dd = dec[dst]
            j = np.searchsorted(dd, dec[src])
            lo = np.clip(j - 1, 0, dd.size - 1)
            hi = np.clip(j, 0, dd.size - 1)
            dlo = np.abs(dec[src] - dd[lo])
            dhi = np.abs(dec[src] - dd[hi])
            pick = np.where(dlo <= dhi, lo, hi)
            gap = np.minimum(dlo, dhi)
            tol = int(kst[(asset, int(want))])
            for s_, p_, g_ in zip(src.tolist(), pick.tolist(), gap.tolist()):
                if g_ <= tol:
                    out[int(idx[s_])] = int(idx[dst[p_]])
                else:
                    n_un += 1
    return out, n_un


def cell_majority_side(D):
    """The (asset, phase) CELL's winner-majority side (CC-M2-16.1's estimand)."""
    out = {}
    win = np.nan_to_num(D["y_winner"], nan=0.0) > 0.5
    order = np.argsort(D["cell"], kind="stable")
    c = D["cell"][order]
    starts = [0] + (np.flatnonzero(c[1:] != c[:-1]) + 1).tolist()
    stops = starts[1:] + [c.size]
    for a, b in zip(starts, stops):
        idx = order[a:b]
        w = idx[win[idx]]
        if w.size == 0:
            out[str(D["cell"][idx[0]])] = 0
            continue
        sd = D["side"][w]
        out[str(D["cell"][idx[0]])] = 1 if int((sd > 0).sum()) >= int(
            (sd < 0).sum()) else -1
    return out


def dp_over(D, idx):
    """One-position DP over an arbitrary candidate subset, per session."""
    a = np.asarray(idx, dtype=np.int64)
    a = a[D["cert_refused"][a] == 0]
    if a.size == 0:
        return {}
    sess = D["session"][a]
    order = np.lexsort((D["dec_sec"][a], sess))
    a = a[order]
    so = sess[order]
    starts = [0] + (np.flatnonzero(so[1:] != so[:-1]) + 1).tolist()
    stops = starts[1:] + [so.size]
    tot = {}
    for lo, hi in zip(starts, stops):
        sel = a[lo:hi]
        dec = D["dec_sec"][sel].astype(np.int64).tolist()
        ex = D["exit_close_sec"][sel].astype(np.int64).tolist()
        cv = D["cert_close_usd"][sel].astype(np.float64).tolist()
        rid = sel.tolist()
        v, _ch = CC.dp_schedule(list(zip(dec, ex, cv, dec, rid, rid)))
        tot[str(so[lo])] = float(v)
    return tot


def decompose(D, take_idx, eval_idx, ceilings, mirror, maj):
    """CC-M2-17.1's three stages, in CC-M2-19.2's measured order.

      L0  what the model banked
      L1  the same takes with the SIDE corrected to the cell's winner-majority
          side (the stage-2 estimand)                          -> SIDE gap
      L2  the best one-position schedule available INSIDE the cells the model
          chose, on the corrected side                          -> MOMENT gap
      L3  the day ceiling over every candidate                  -> SEAT gap
    """
    rows0 = replay_rows(D, take_idx)
    L0 = sum(r["realised"] for r in rows0)

    tk = np.asarray(take_idx, dtype=np.int64)
    over = {}
    for i, ck, sd in zip(tk.tolist(), D["cell"][tk].tolist(),
                         D["side"][tk].astype(np.int64).tolist()):
        want = maj.get(ck, 0)
        if want != 0 and sd != want and i in mirror:
            over[i] = mirror[i]
    rows1 = replay_rows(D, take_idx, side_override=over)
    L1 = sum(r["realised"] for r in rows1)

    cells = set(D["cell"][tk].tolist())
    ev = np.asarray(eval_idx, dtype=np.int64)
    keep = [i for i, ck, sd in zip(ev.tolist(), D["cell"][ev].tolist(),
                                   D["side"][ev].astype(np.int64).tolist())
            if ck in cells and (maj.get(ck, 0) == 0 or sd == maj.get(ck, 0))]
    L2 = sum(dp_over(D, keep).values())

    L3 = sum(ceilings[s][0] for s in set(D["session"][ev].tolist()))
    return {"L0_model_usd": L0, "L1_side_fixed_usd": L1,
            "L2_moment_fixed_usd": L2, "L3_day_ceiling_usd": L3,
            "gap_side_usd": L1 - L0, "gap_moment_usd": L2 - L1,
            "gap_seat_usd": L3 - L2,
            "n_side_corrections": len(over)}


# =================================================================== driver ==
def era_block(D, k):
    """(train rows, eval rows, flag) for era index k of the expanding ladder."""
    ev = np.nonzero(D["era_idx"] == k)[0]
    if k == 0:
        tr = np.nonzero(D["era_idx"] < 0)[0]     # PRE_E1 warm-up tape
        return tr, ev, "PRE_E1_WARMUP_TRAIN"
    tr = np.nonzero((D["era_idx"] >= 0) & (D["era_idx"] < k))[0]
    return tr, ev, "EXPANDING"


def run_era(D, k, nthread, ceilings, mirror, maj):
    t0 = time.time()
    era = M3.ERA_NAMES[k]
    tr, ev, flag = era_block(D, k)
    out = {"era": era, "train_flag": flag, "n_train_rows": int(tr.size),
           "n_eval_rows": int(ev.size),
           "n_train_sessions": int(np.unique(D["session"][tr]).size),
           "n_eval_sessions": int(np.unique(D["session"][ev]).size)}
    if tr.size < 5000 or ev.size == 0:
        out["status"] = "NO_MODEL"
        out["why"] = ("training block too small (%d rows) — an era with no "
                      "prior history is reported, never imputed" % tr.size)
        return out
    X = D["X"]
    fn = list(D["names"])
    out["targets"] = {}
    for target in (PRIMARY_TARGET,) + SIDE_TARGETS:
        y = D[target]
        fin_tr = tr[np.isfinite(y[tr])]
        if fin_tr.size < 5000:
            out["targets"][target] = {"status": "NO_MODEL",
                                      "why": "%d finite training labels"
                                             % int(fin_tr.size)}
            continue
        cut = inner_split(D["d8"][fin_tr])
        if cut is None:
            out["targets"][target] = {
                "status": "NO_MODEL",
                "why": "training block spans fewer than 10 sessions"}
            continue
        itr = fin_tr[D["d8"][fin_tr] <= cut]
        iva = fin_tr[D["d8"][fin_tr] > cut]
        if itr.size < 500 or iva.size < 100:
            itr = iva = fin_tr
        sel = fit_one(X, y, itr, iva, nthread, feature_names=fn)
        if sel is None:
            out["targets"][target] = {"status": "NO_MODEL",
                                      "why": "every HP cell refused"}
            continue
        # the policy knob, chosen on the INNER validation block only
        b_in = xgb.train(sel["cfg"],
                         xgb.DMatrix(X[itr], label=y[itr], feature_names=fn),
                         sel["rounds"])
        s_in = np.full(D["d8"].size, np.nan)
        s_in[iva] = b_in.predict(xgb.DMatrix(X[iva], feature_names=fn))
        (punit, topn), curve = select_policy(D, s_in, iva, ceilings)
        # the era model: refit on the WHOLE training block at that config
        booster = xgb.train(sel["cfg"],
                            xgb.DMatrix(X[fin_tr], label=y[fin_tr],
                                        feature_names=fn),
                            sel["rounds"])
        score = np.full(D["d8"].size, np.nan)
        score[ev] = booster.predict(xgb.DMatrix(X[ev], feature_names=fn))
        cell = {"status": "OK",
                "hp": {k2: v for k2, v in sel["cfg"].items()
                       if k2 in ("max_depth", "eta", "min_child_weight",
                                 "colsample_bytree")},
                "rounds": sel["rounds"], "inner_rho": sel["inner_rho"],
                "policy_unit": punit, "topn": int(topn),
                "policy_curve": curve,
                "n_train_rows_finite": int(fin_tr.size)}
        for reading, deployable in (("DEPLOYABLE", True), ("SCIENCE", False)):
            take = topn_takes(D, score, ev, topn,
                              deployable=deployable, unit=punit)
            rows = replay_rows(D, take)
            seats = [j for r in rows for j in r["seats"]]
            res = {"n_takes": int(take.size), "n_sessions": len(rows),
                   "n_seated": sum(r["n_seated"] for r in rows),
                   "n_forfeited": sum(r["n_forfeited"] for r in rows),
                   "n_refused_cert": sum(r["n_refused"] for r in rows),
                   "realised_usd": sum(r["realised"] for r in rows),
                   "per_trade": per_trade_stats(D, seats),
                   "drawdown": daily_drawdown(D, rows)}
            res["per_session_usd"] = ((res["realised_usd"] / len(rows))
                                      if rows else 0.0)
            res["sessions"] = [(r["session"], r["realised"], r["n_seated"])
                               for r in rows]
            cell[reading] = res
        cell["_score"] = score
        cell["_take_idx"] = topn_takes(D, score, ev, topn,
                                       deployable=True, unit=punit)
        if target == PRIMARY_TARGET:
            cell["_importance"] = booster.get_score(importance_type="gain")
        out["targets"][target] = cell

    # ---- THE COMPOSED ARM (CC-M2-17.1: "M3 = the three stages composed") ----
    # The atlas champion is a RETENTION ratio: scale-free by construction, and
    # its mover-gate means it is FITTED only on rows that moved (mfe >= 30x
    # cost) while it is APPLIED to every row, including the ones where nothing
    # happened.  Stage 1 (does a seat exist here at all?) is exactly what the
    # walled-winner head supplies, so the composition is their product — the
    # feasibility head gates, the quality head orders.  No extra fit: both
    # scores already exist.
    pr = out["targets"].get(PRIMARY_TARGET, {})
    wn = out["targets"].get("y_winner", {})
    if pr.get("status") == "OK" and wn.get("status") == "OK":
        # both heads are put on a common, monotone scale first: a raw product
        # of a squared-error regression's outputs is not order-safe (either
        # factor may be negative), so each is converted to a within-(asset,
        # session) percentile and the two are SUMMED — the rank-sum composition.
        comp = (_unit_pct(D, pr["_score"], ev)
                + _unit_pct(D, wn["_score"], ev))
        take = topn_takes(D, comp, ev, pr["topn"], deployable=True,
                          unit=pr["policy_unit"])
        rows = replay_rows(D, take)
        seats = [j for r in rows for j in r["seats"]]
        out["COMPOSED"] = {
            "n_takes": int(take.size), "n_sessions": len(rows),
            "realised_usd": sum(r["realised"] for r in rows),
            "per_session_usd": ((sum(r["realised"] for r in rows) / len(rows))
                                if rows else 0.0),
            "per_trade": per_trade_stats(D, seats),
            "drawdown": daily_drawdown(D, rows),
            "sessions": [(r["session"], r["realised"], r["n_seated"])
                         for r in rows],
            "topn": int(pr["topn"]), "policy_unit": pr["policy_unit"],
            "definition": "score = retention-rank hat x winner-probability hat",
        }
        out["_composed_take_idx"] = take

    prim = out["targets"].get(PRIMARY_TARGET, {})
    if prim.get("status") != "OK":
        out["status"] = "NO_MODEL"
        out["why"] = prim.get("why", "the primary target produced no model")
        return out
    out["status"] = "OK"
    out["hp"] = prim["hp"]
    out["rounds"] = prim["rounds"]
    out["inner_rho"] = prim["inner_rho"]
    out["topn"] = prim["topn"]
    out["policy_curve"] = prim["policy_curve"]
    out["policy_unit"] = prim["policy_unit"]
    out["DEPLOYABLE"] = prim["DEPLOYABLE"]
    out["SCIENCE"] = prim["SCIENCE"]
    out["eval_idx"] = ev
    out["take_idx_deployable"] = prim["_take_idx"]
    out["importance"] = prim["_importance"]
    out["decomposition"] = decompose(D, out["take_idx_deployable"], ev,
                                     ceilings, mirror, maj)
    out["fit_secs"] = round(time.time() - t0, 1)
    return out


def baseline_takes(D, idx, deployable=True):
    """BASE_EARLIEST: the earliest member of each frozen episode."""
    i = np.asarray(idx, dtype=np.int64)
    j = D["names"].index("ep_is_earliest")
    keep = i[D["X"][i, j] > 0.5]
    if deployable:
        k = D["names"].index("in_news_window")
        keep = keep[D["X"][keep, k] < 0.5]
    return np.sort(keep)


def session_frame(D, rows, ceilings):
    """Per-session realised / ceiling / oracle, in session order."""
    out = []
    for r in rows:
        skey = r["session"]
        asset, d8 = skey.split("|")
        cap = ceilings.get(skey, (0.0, 0, 0))
        orc = oracle_ceiling(asset, int(d8))
        out.append({"session": skey, "asset": asset, "d8": int(d8),
                    "realised": r["realised"], "ceiling": cap[0],
                    "oracle": orc[0], "n_seated": r["n_seated"]})
    out.sort(key=lambda x: (x["asset"], x["d8"]))
    return out


def run(matrix_dir=None, nthread=8, out_dir=None):
    t0 = time.time()
    MC.verify_spec(force=True)
    D, mpath = load_matrix(matrix_dir)
    M3.hb("m3 walk: matrix %d rows x %d features" % D["X"].shape)
    ceilings = dp_ceilings(D)
    M3.hb("m3 walk: %d session ceilings" % len(ceilings))
    mirror, n_unmirrorable = mirror_map(D)
    M3.hb("m3 walk: %d mirrorable rows, %d unmirrorable (no opposite-side "
          "candidate inside K* in the same cell)" % (len(mirror), n_unmirrorable))
    maj = cell_majority_side(D)

    eras = []
    for k in range(len(M3.ERA_NAMES)):
        r = run_era(D, k, nthread, ceilings, mirror, maj)
        eras.append(r)
        M3.hb("m3 walk: %s %s %s" % (r["era"], r["status"] if "status" in r
                                     else "?",
                                     ("$%.0f/session"
                                      % r["DEPLOYABLE"]["per_session_usd"])
                                     if r.get("status") == "OK" else ""))
    res = assemble_report(D, eras, ceilings, mirror, out_dir)
    res["elapsed_sec"] = round(time.time() - t0, 1)
    M3.hb("m3 walk: done in %.1fs" % res["elapsed_sec"])
    return res


# =================================================================== report ==
def assemble_report(D, eras, ceilings, mirror, out_dir=None):
    out_dir = out_dir or M3.WALK_DIR
    os.makedirs(out_dir, exist_ok=True)
    pvals, ptags = [], []

    era_rows, asset_rows = [], []
    per_session_all = []
    for e in eras:
        if e.get("status") != "OK":
            era_rows.append([e["era"], e["train_flag"], e.get("status"),
                             e["n_train_rows"], e["n_eval_rows"]]
                            + [""] * 14)
            continue
        dep = e["DEPLOYABLE"]
        rows = [{"session": s, "realised": v, "n_seated": n}
                for s, v, n in dep["sessions"]]
        sf = session_frame(D, [{"session": s, "realised": v, "n_seated": n,
                                "seats": []} for s, v, n in dep["sessions"]],
                           ceilings)
        per_session_all.append((e["era"], sf))

        y = [x["realised"] for x in sf]
        cl = [x["session"] for x in sf]
        cm = PS.cluster_mean(y, cl)
        # the D-048 bar test: is the per-session mean above $2,000?
        vs_bar = PS.cluster_mean([v - M3.BAR_PER_SESSION_USD for v in y], cl)
        vs_floor = PS.cluster_mean([v - M3.BAR_THIN_FLOOR_USD for v in y], cl)
        cap = PS.cluster_ratio([x["realised"] for x in sf],
                               [x["ceiling"] for x in sf], cl)
        ocap = PS.cluster_ratio([x["realised"] for x in sf],
                                [x["oracle"] for x in sf], cl)

        # the mechanical arm, paired per session
        base = baseline_takes(D, e["eval_idx"])
        brows = replay_rows(D, base)
        bmap = {r["session"]: r["realised"] for r in brows}
        deltas = [x["realised"] - bmap.get(x["session"], 0.0) for x in sf]
        dm = PS.cluster_mean(deltas, cl)

        pvals += [vs_bar["p"] if vs_bar else None, dm["p"] if dm else None]
        ptags += ["%s vs_D048_bar" % e["era"], "%s vs_BASE_EARLIEST" % e["era"]]

        pt = dep["per_trade"]
        comp = e.get("COMPOSED") or {}
        era_rows.append([
            e["era"], e["train_flag"], "OK", e["n_train_rows"],
            e["n_eval_rows"], e["n_eval_sessions"],
            "%s/%d" % (e["policy_unit"], e["topn"]),
            round(cm["mean"], 2) if cm else None,
            round(cm["ci_lo"], 2) if cm else None,
            round(cm["ci_hi"], 2) if cm else None,
            round(vs_bar["mean"], 2) if vs_bar else None,
            round(vs_floor["mean"], 2) if vs_floor else None,
            round(dm["mean"], 2) if dm else None,
            round(cap["ratio"], 4) if cap else None,
            round(ocap["ratio"], 4) if ocap else None,
            round(pt.get("expectancy_usd", float("nan")), 2),
            round(comp.get("per_session_usd", float("nan")), 2),
            round(sum(x[1] for x in comp.get("sessions", []))
                  / max(len(comp.get("sessions", [])), 1)
                  - M3.BAR_PER_SESSION_USD, 2) if comp else None,
            round(comp.get("per_trade", {}).get("expectancy_usd",
                                                float("nan")), 2)
            if comp else None])

        for asset in M3.ASSET_ORDER:
            sub = [x for x in sf if x["asset"] == asset]
            if not sub:
                continue
            cla = [x["session"] for x in sub]
            cma = PS.cluster_mean([x["realised"] for x in sub], cla)
            capa = PS.cluster_ratio([x["realised"] for x in sub],
                                    [x["ceiling"] for x in sub], cla)
            tk = e["take_idx_deployable"]
            arows = replay_rows(D, tk[D["asset_idx"][tk]
                                      == M3.ASSET_ORDER.index(asset)])
            seats = [j for r in arows for j in r["seats"]]
            pta = per_trade_stats(D, seats)
            dda = daily_drawdown(D, arows)
            asset_rows.append([
                e["era"], asset, len(sub),
                round(cma["mean"], 2) if cma else None,
                round(cma["ci_lo"], 2) if cma else None,
                round(cma["ci_hi"], 2) if cma else None,
                int(cma["mean"] >= M3.BAR_PER_SESSION_USD) if cma else None,
                int(cma["mean"] >= M3.BAR_THIN_FLOOR_USD) if cma else None,
                round(capa["ratio"], 4) if capa else None,
                pta.get("n", 0),
                round(pta.get("expectancy_usd", float("nan")), 2),
                round(pta.get("mean_mae_usd", float("nan")), 2),
                round(pta.get("frac_ge_1000", float("nan")), 4),
                round(dda.get("p90_dd_usd", float("nan")), 2),
                round(dda.get("frac_sessions_over_bar", float("nan")), 4)])

    # ---- the directional claim, under the era-scale mirror law -------------
    mirror_rows = []
    for e in eras:
        if e.get("status") != "OK":
            continue
        take = e["take_idx_deployable"]
        over = {i: mirror[i] for i in take.tolist() if i in mirror}
        r0 = {r["session"]: r["realised"] for r in replay_rows(D, take)}
        r1 = {r["session"]: r["realised"]
              for r in replay_rows(D, take, side_override=over)}
        keys = sorted(set(r0) | set(r1))
        deltas = [r0.get(k, 0.0) - r1.get(k, 0.0) for k in keys]
        st = MC.mirror_paired(deltas)
        mirror_rows.append([e["era"], st["n_sessions"], round(st["mean_delta"], 2),
                            round(st["mde_80"], 2), st["verdict"], st["p"],
                            st["p_sign"], len(over)])
        pvals.append(st["p"] if st["verdict"] == "TESTED" else None)
        ptags.append("%s mirror_paired" % e["era"])

    # ---- ONE Holm family over every p-value the round reports -------------
    adj = PS.holm(pvals)
    holm_rows = [[t, (None if p is None else float(p)),
                  (None if q is None else float(q)),
                  (None if q is None else int(q < 0.05))]
                 for t, p, q in zip(ptags, pvals, adj)]

    # ---- D-084 adaptation latencies ---------------------------------------
    lat_rows = []
    per_era = dict(per_session_all)
    for name, era in M3.BREAKS:
        sf = per_era.get(era)
        if not sf:
            lat_rows.append([name, era, "NO_MODEL", None, None, None, None])
            continue
        for scope in ("POOLED",) + M3.ASSET_ORDER:
            sub = sf if scope == "POOLED" else [x for x in sf
                                                if x["asset"] == scope]
            sub = sorted(sub, key=lambda x: (x["d8"], x["asset"]))
            num = np.array([x["realised"] for x in sub], dtype=np.float64)
            den = np.array([x["ceiling"] for x in sub], dtype=np.float64)
            tot = float(den.sum())
            target = (float(num.sum()) / tot) if tot > 0 else float("nan")
            w = M3.LATENCY_WINDOW_SESSIONS
            first, full = None, None
            for t in range(len(sub)):
                lo = max(0, t - w + 1)
                dd = float(den[lo:t + 1].sum())
                if dd <= 0:
                    continue
                hit = float(num[lo:t + 1].sum()) / dd >= target
                if hit and first is None:
                    first = t + 1
                if hit and full is None and (t + 1) >= w:
                    full = t + 1
            lat_rows.append([
                name, era, scope, len(sub),
                round(target, 4) if np.isfinite(target) else None,
                first if first is not None else "CENSORED>%d" % len(sub),
                full if full is not None else "CENSORED>%d" % len(sub)])

    # ---- feature-importance stability -------------------------------------
    imp_rows, stab_rows = [], []
    prev = None
    for e in eras:
        if e.get("status") != "OK":
            continue
        imp = e["importance"]
        tot = sum(imp.values()) or 1.0
        top = sorted(imp.items(), key=lambda kv: (-kv[1], kv[0]))[:20]
        for rank, (f, g) in enumerate(top, 1):
            imp_rows.append([e["era"], rank, f, MX.FEATURE_GROUP.get(f, "?"),
                             round(g / tot, 6)])
        cur = {f: g / tot for f, g in imp.items()}
        if prev is not None:
            keys = sorted(set(prev) | set(cur))
            a = np.array([prev.get(k, 0.0) for k in keys])
            b = np.array([cur.get(k, 0.0) for k in keys])
            stab_rows.append([prev_era, e["era"], len(keys),
                              round(M3._rho(a, b), 4)])
        prev, prev_era = cur, e["era"]

    # ---- decomposition -----------------------------------------------------
    dec_rows = []
    for e in eras:
        if e.get("status") != "OK":
            continue
        d = e["decomposition"]
        dec_rows.append([e["era"], round(d["L0_model_usd"], 2),
                         round(d["L1_side_fixed_usd"], 2),
                         round(d["L2_moment_fixed_usd"], 2),
                         round(d["L3_day_ceiling_usd"], 2),
                         round(d["gap_side_usd"], 2),
                         round(d["gap_moment_usd"], 2),
                         round(d["gap_seat_usd"], 2),
                         d["n_side_corrections"]])

    phash = M3.params_hash(PARAMS)
    W = lambda nm, cols, rows, extra=(): M3.write_tsv(   # noqa: E731
        os.path.join(out_dir, nm), SECTION, phash, cols, rows, extra)
    W("ERA_CURVE.tsv",
      ["era", "train_block", "status", "n_train_rows", "n_eval_rows",
       "n_eval_sessions", "policy", "usd_per_session", "ci_lo", "ci_hi",
       "vs_D048_2000", "vs_thin_floor_1500", "vs_BASE_EARLIEST",
       "capture_day_ceiling", "capture_oracle", "expectancy_usd",
       "composed_usd_per_session", "composed_vs_D048_2000",
       "composed_expectancy_usd"], era_rows,
      ["THE deliverable: per-era out-of-sample $/session vs the D-048 bars",
       "DEPLOYABLE reading (D-077-UPDATE +/-10min veto applied)",
       "usd_per_session = the PRIMARY (atlas-champion) arm; composed_* = the "
       "CC-M2-17.1 composition (retention-rank hat + winner-probability hat, "
       "rank-summed within the session)"])
    W("ERA_ASSET.tsv",
      ["era", "asset", "n_sessions", "usd_per_session", "ci_lo", "ci_hi",
       "clears_2000", "clears_1500", "capture_day_ceiling", "n_trades",
       "expectancy_usd", "mean_mae_usd", "frac_ge_1000", "p90_daily_dd",
       "frac_sessions_dd_over_1000"],
      asset_rows, ["D-048 is a PER-ASSET bar; this is the per-asset reading",
                   "D-021: expectancy >= $600 minimum / $1,000 target, MAE "
                   "<= $300; D-030: daily drawdown < $1,000"])
    W("MIRROR.tsv",
      ["era", "n_sessions", "mean_delta_usd", "mde_80_usd", "verdict", "p",
       "p_sign", "n_mirrorable_takes"], mirror_rows,
      ["R59 era-scale mirror law (m2_common.mirror_paired): the model's own "
       "takes vs the SAME takes side-flipped, paired per session",
       "WHAT THIS DOES AND DOES NOT SHOW.  The corpus has no exact-second "
       "opposite-side twin (2,508 rows of 1,399,374), so the flip substitutes "
       "the nearest opposite-side candidate of the same CELL within K*.  The "
       "substitute therefore differs from the take in BOTH side and (by up to "
       "K* seconds) moment, and it is by construction a candidate the model "
       "did NOT rank first.  A positive delta says the model's chosen "
       "(side, moment) beats the nearest opposite-side alternative — it is "
       "NOT a clean side-only contrast, and must not be quoted as one."])
    W("HOLM.tsv", ["test", "p_raw", "p_holm", "significant_05"], holm_rows,
      ["ONE Holm family over every p-value this round reports"])
    W("ADAPTATION_LATENCY.tsv",
      ["break", "era", "scope", "n_sessions", "era_achievable_capture",
       "sessions_to_recover", "sessions_to_recover_full_window"], lat_rows,
      ["D-084(b): the era's model is FROZEN at the break (it was fitted on "
       "pre-break eras only), so this measures the ADAPTATION DEBT — how many "
       "sessions of the post-break era pass before the pre-break model's "
       "trailing capture reaches the level it eventually sustains there",
       "sessions_to_recover uses a trailing window of min(t, %d) sessions; "
       "sessions_to_recover_full_window requires the full %d-session window, "
       "so its floor is %d by construction"
       % (M3.LATENCY_WINDOW_SESSIONS, M3.LATENCY_WINDOW_SESSIONS,
          M3.LATENCY_WINDOW_SESSIONS)])
    W("IMPORTANCE.tsv", ["era", "rank", "feature", "group", "gain_share"],
      imp_rows)
    W("IMPORTANCE_STABILITY.tsv",
      ["era_a", "era_b", "n_features", "spearman_gain_share"], stab_rows)
    W("DECOMPOSITION.tsv",
      ["era", "L0_model", "L1_side_fixed", "L2_moment_fixed", "L3_day_ceiling",
       "gap_side", "gap_moment", "gap_seat", "n_side_corrections"], dec_rows,
      ["CC-M2-17.1 three stages, in CC-M2-19.2's measured order "
       "(side first, feasibility second, moment not free)"])

    # ---- the three targets, side by side ----------------------------------
    tgt_rows = []
    for e in eras:
        for t in (PRIMARY_TARGET,) + SIDE_TARGETS:
            c = (e.get("targets") or {}).get(t)
            if not c:
                continue
            if c.get("status") != "OK":
                tgt_rows.append([e["era"], t, c.get("status"), None, None,
                                 None, None, None, c.get("why", "")])
                continue
            dep = c["DEPLOYABLE"]
            pt = dep["per_trade"]
            tgt_rows.append([
                e["era"], t, "OK", "%s/%d" % (c["policy_unit"], c["topn"]),
                round(c["inner_rho"], 5),
                round(dep["per_session_usd"], 2), pt.get("n", 0),
                round(pt.get("expectancy_usd", float("nan")), 2),
                "primary" if t == PRIMARY_TARGET else "secondary"])
        comp = e.get("COMPOSED")
        if comp:
            tgt_rows.append([e["era"], "COMPOSED_rank_sum", "OK",
                             "%s/%d" % (comp["policy_unit"], comp["topn"]),
                             None,
                             round(comp["per_session_usd"], 2),
                             comp["per_trade"].get("n", 0),
                             round(comp["per_trade"].get(
                                 "expectancy_usd", float("nan")), 2),
                             "composition (CC-M2-17.1)"])
    W("TARGET_COMPARE.tsv",
      ["era", "target", "status", "policy", "inner_rho", "usd_per_session",
       "n_trades", "expectancy_usd", "role"], tgt_rows,
      ["the atlas champion is the PRIMARY; the walled winner indicator and "
       "the CC-M2-2 T1 pairwise preference are fitted on the same harness so "
       "the target choice is measured, not asserted"])

    sess_rows = []
    for era, sf in per_session_all:
        for x in sf:
            sess_rows.append([era, x["asset"], x["d8"], round(x["realised"], 2),
                              round(x["ceiling"], 2), round(x["oracle"], 2),
                              x["n_seated"]])
    W("PER_SESSION.tsv",
      ["era", "asset", "d8", "realised_usd", "day_ceiling_usd",
       "oracle_ceiling_usd", "n_seated"], sess_rows)

    def _clean(e):
        out = {k: v for k, v in e.items()
               if k not in ("score_eval", "eval_idx", "take_idx_deployable",
                            "importance") and not k.startswith("_")}
        if "targets" in out:
            out["targets"] = {t: {k: v for k, v in c.items()
                                  if not k.startswith("_")}
                              for t, c in out["targets"].items()}
        return out

    summary = {"eras": [_clean(e) for e in eras],
               "holm": holm_rows, "latency": lat_rows,
               "no_teacher": bool(MX.NO_TEACHER),
               "gate_2025h1_echo": "E8"}
    rec = M3.env_receipt(dict(PARAMS, summary_counts={
        "n_eras_scored": sum(1 for e in eras if e.get("status") == "OK"),
        "n_pvalues": len(pvals)}))
    rec["params_hash"] = phash
    M3.write_json(os.path.join(out_dir, "walk.receipt.json"), rec)
    M3.write_json(os.path.join(out_dir, "walk.summary.json"),
                  json.loads(json.dumps(summary, default=_jsafe)))
    return summary


def _jsafe(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


PARAMS = {
    "section": SECTION,
    "harness": M3.HARNESS_VERSION,
    "ladder": "expanding window; model_k is fitted on every era strictly "
              "before era k and scored on era k; E1's block is the PRE_E1 "
              "warm-up tape and is FLAGGED; E8 = the GATE-2025H1 echo",
    "primary_target": PRIMARY_TARGET,
    "objective": "reg:squarederror on the RANK-transformed label — "
                 "LABEL_ATLAS_V2 §2.5: the rank TRANSFORM wins, the ranking "
                 "OBJECTIVE lost every matched cell",
    "hp_discipline": "s4_confirm.HP_GRID, searched on the depth x eta face "
                     "(%d cells) at the S4 modal mcw/colsample, inner split = "
                     "the training block's last %d%% of sessions "
                     "(s4_confirm._inner_split), early stopping %d, "
                     "rounds_max %d, seed %d — FIT ONLY"
                     % (len(HP_SEARCH), int(INNER_FRACTION * 100), EARLY_STOP,
                        ROUNDS_MAX, M3.SEED),
    "policy": "TOP-N per SELECTION UNIT by model score; unit in %s and N in "
              "%s, the pair selected on the training block's inner validation "
              "ONLY; D-077-UPDATE restricted-window veto applied in the "
              "DEPLOYABLE reading (|mins to nearest scheduled release| <= %g, "
              "plus the held-into-window flag).  THE ONE DESIGN CHOICE THE "
              "BRIEF LEFT OPEN — declared here with its own FIT-side selection "
              "and its full sensitivity curve in the receipt."
              % (list(UNIT_GRID), list(TOPN_GRID), M3.NEWS_WINDOW_MIN),
    "replay": "one position per asset per session, chronological, walled "
              "PHASE-CLOSE certificate (CC-M2-10.3; CC-M2-21.4 makes the "
              "greedy reading THE LAW)",
    "bars": {"per_session_usd": M3.BAR_PER_SESSION_USD,
             "thin_floor_usd": M3.BAR_THIN_FLOOR_USD,
             "trade_min_usd": M3.BAR_TRADE_MIN_USD,
             "trade_target_usd": M3.BAR_TRADE_TARGET_USD,
             "daily_dd_usd": M3.BAR_DAILY_DD_USD},
    "inference": "session-clustered CR1 (panel_score.cluster_mean / "
                 "cluster_ratio); directional claims under "
                 "m2_common.mirror_paired (R59); ONE Holm family",
    "mirror_caveat": "the sign-flip substitutes the NEAREST opposite-side "
                     "candidate of the same cell within K* (no exact-second "
                     "twin exists in this corpus), so the contrast carries a "
                     "moment component and a not-top-ranked component beside "
                     "the side component; it is not a clean side-only test",
    "ceilings": "day = one-position DP over EVERY candidate "
                "(c_c_roster.dp_schedule); oracle = one-position DP over the "
                "day's ANCHORED oracle legs",
    "breaks": [list(b) for b in M3.BREAKS],
    "latency_window_sessions": M3.LATENCY_WINDOW_SESSIONS,
    "no_teacher": bool(MX.NO_TEACHER),
    "d078_instrument": "every feature of this matrix is census/generic-derived; "
                       "the teacher_evidence group is declared and EMPTY, so "
                       "the coming teacher round's marginal value is a "
                       "difference measured on THIS harness",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--matrix", default=None)
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--nthread", type=int, default=8)
    a = ap.parse_args()
    if not a.run:
        ap.print_help()
        return 2
    run(matrix_dir=a.matrix, nthread=a.nthread, out_dir=a.outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
