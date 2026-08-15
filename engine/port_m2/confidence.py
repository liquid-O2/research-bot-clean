#!/usr/bin/python3
"""PORT M2 — THE CONFIDENCE-SELECTIVE ARM.

THE DISEASE, measured last round: tightening a plain score bar makes the arm
WORSE per trade in the strong eras -- E7 win rate falls 0.713 -> 0.606 and
$/trade falls $509 -> $251 as the bar rises.  The score's top decile is not its
best decile.  A confidence mechanism has to be built out of something other than
the score's own magnitude.

THREE FIXES, all on already-fitted members:

  1 AGREEMENT   (replay only) 25 members per era each pick a top-1 per cell.
                Take the cell only when enough of them AGREE.  Members disagree
                most on coin-flips, so agreement is a confidence interval built
                out of the ensemble rather than out of the score scale.
  2 RISK-ADJUSTED  a light predicted-MAE head; re-rank by
                score_pct - lambda * predicted_MAE_pct.  Hypothesis under test:
                the top-decile losers are high-vol monsters carrying wall risk
                that the dollar score cannot see.
  3 ISOTONIC    per-era isotonic calibration of score -> dollars, fitted on
                PRIOR eras and applied forward, then the curve re-cut.

THE PROP CONSTRAINTS ARE BINDING AND ARE CHECKED IN EVERY TABLE:
  * NO quick exits.  Nothing here touches the exit: the contract stays
    ride-to-phase-close with the $900 wall.  No microscalping is expressible.
  * <= 10 trades/day HARD CAP across the three books.
  * target 2-3 trades/day/asset at >= $667/trade -> $2,000/day/asset.
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

import newobj as N                        # noqa: E402
import newobj_arms as NA                  # noqa: E402
import rank_atlas as RA                   # noqa: E402
import champ_floor as CF                  # noqa: E402
import risk_panel as RP                   # noqa: E402
import stacked_final as SF                # noqa: E402
import m2_common as MC                    # noqa: E402

ERAS = N.DEV_ERAS
AGREE_TAUS = (0.0, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80)
LAMBDAS = (0.0, 0.25, 0.5, 1.0, 2.0)
DAY_CAP = 10                 # hard, across the three books
TARGET_TRADE = 667.0
TARGET_DAY_ASSET = 2000.0


def _members(era):
    fam = SF._load(era)
    return [x for v in fam.values() for x in v]


def _pct(D, rows, s):
    """Within-cell percentile of a score over `rows`."""
    out = np.full(D["d8"].size, np.nan)
    ro, blocks = N.cell_blocks(D, rows)
    v = np.asarray(s)[ro]
    for a, b in blocks:
        idx = np.arange(a, b)
        ok = idx[np.isfinite(v[idx])]
        if ok.size == 0:
            continue
        r = np.argsort(np.argsort(v[ok], kind="stable"), kind="stable")
        out[ro[ok]] = (r + 0.5) / ok.size
    return out


def agreement(D, ev, S, n_):
    """Per cell: the modal top-1 pick across members and the fraction agreeing."""
    ro, blocks = N.cell_blocks(D, ev)
    picks, frac = {}, {}
    M = np.vstack([x[ro] for x in S])
    for a, b in blocks:
        seg = M[:, a:b]
        if seg.shape[1] == 0 or not np.isfinite(seg).any():
            continue
        am = np.nanargmax(seg, axis=1)
        vals, cnt = np.unique(am, return_counts=True)
        j = int(vals[int(np.argmax(cnt))])
        picks[int(ro[a + j])] = True
        frac[int(ro[a + j])] = float(cnt.max()) / seg.shape[0]
    return picks, frac


def _read(D, P, takes, era, label):
    rep = N.replay_delayed(D, takes, P)
    a = N.read_rows(D, rep)
    g = dict(zip(RP.COLS, RP.panel_rows(D, rep, label, era, "ALL", None)))
    n_days = len(set(D["d8"][[i for i, _d in takes]].tolist())) if takes else 0
    seats = a.get("n_seated") or 0
    per_day_book = (seats / max(n_days, 1)) if n_days else 0.0
    td = [r for r in rep if r["n_seated"] > 0]
    per_traded = (sum(r["realised"] for r in td) / len(td)) if td else None
    return a, g, per_day_book, per_traded


def _row(era, arm, knob, a, g, pdb, per_traded):
    tr = a.get("usd_per_trade")
    ses = a.get("usd_per_session")
    return [era, arm, knob, a.get("n_seated"), N._r(g["takes_per_day_mean"]),
            N._r(pdb * 3.0, 2), g["win_rate"], N._r(tr), N._r(ses),
            N._r(per_traded), g["weekly_pnl_p10"],
            g["frac_sessions_dd_over_1000"],
            "OVER_DAY_CAP" if (pdb * 3.0) > DAY_CAP else "",
            "TRADE_OK" if (tr or 0) >= TARGET_TRADE else "",
            "DAY_TARGET_OK" if (ses or 0) >= TARGET_DAY_ASSET else ""]


COLS = ["era", "arm", "knob", "n_seated", "takes_per_session",
        "trades_per_day_3books", "win_rate", "usd_per_trade",
        "usd_per_session", "usd_per_traded_day", "weekly_pnl_p10",
        "frac_sessions_dd_over_1000", "cap_flag", "trade_target",
        "day_target"]
EXTRA = ["PROP CONSTRAINTS CHECKED IN EVERY ROW: <=%d trades/day across the "
         "three books (cap_flag), >=$%d/trade (trade_target), >=$%d/day/asset "
         "(day_target).  NO EXIT IS TOUCHED -- the contract remains "
         "ride-to-phase-close with the $900 wall, so no quick exit or "
         "microscalp is expressible by construction."
         % (DAY_CAP, int(TARGET_TRADE), int(TARGET_DAY_ASSET))]


def stage_agreement(eras=ERAS):
    """FIX 1 -- replay only."""
    D, P = CF.boot()
    rows = []
    for era in eras:
        S = _members(era)
        if not S:
            continue
        ev = N.deployable(D, N.era_rows(D, era))
        n_ = N.committed_policy()[era][1]
        ens = np.nanmean(np.vstack(S), axis=0)
        base = N.top_per_cell_score(D, ev, ens, n_)
        a, g, pdb, pt = _read(D, P, base, era, "RAW")
        rows.append(_row(era, "RAW", "", a, g, pdb, pt))
        _picks, frac = agreement(D, ev, S, n_)
        for tau in AGREE_TAUS:
            tk = [(i, d) for (i, d) in base if frac.get(i, 0.0) >= tau]
            if not tk:
                continue
            a2, g2, pdb2, pt2 = _read(D, P, tk, era, "AGREE")
            rows.append(_row(era, "AGREEMENT", N._r(tau, 2), a2, g2, pdb2, pt2))
        N.hb("agreement %s done (%d members)" % (era, len(S)))
    N.write_tsv("CONFIDENCE_AGREEMENT.tsv", COLS, rows,
                extra=EXTRA + [
                    "FIX 1: across the stacked arm's members, each picks a "
                    "top-1 per cell; the cell is taken only when at least "
                    "`knob` of them agree on the SAME candidate.  Members "
                    "disagree most on coin-flips, so agreement is a confidence "
                    "interval built from the ensemble rather than from the "
                    "score's magnitude -- which is the quantity that inverted."])
    return rows


def stage_autopsy(eras=ERAS):
    """FIX 2a -- what ARE the top-decile losers?"""
    D, P = CF.boot()
    cols, names = NA.feat_cols(D)
    rows = []
    for era in eras:
        S = _members(era)
        if not S:
            continue
        ens = np.nanmean(np.vstack(S), axis=0)
        ev = N.deployable(D, N.era_rows(D, era))
        n_ = N.committed_policy()[era][1]
        tk = N.top_per_cell_score(D, ev, ens, n_)
        idx = np.asarray([i for i, _d in tk], dtype=np.int64)
        sc = ens[idx]
        v = D["cert_close_usd"][idx].astype(np.float64)
        top = idx[sc >= np.quantile(sc, 0.90)]
        tv = D["cert_close_usd"][top].astype(np.float64)
        win, los = top[tv > 0], top[tv <= 0]
        for label, grp in (("TOPDEC_WIN", win), ("TOPDEC_LOSS", los),
                           ("ALL_TAKES", idx)):
            if grp.size == 0:
                continue
            rows.append([era, label, int(grp.size),
                         N._r(float(np.nanmean(D["cert_close_usd"][grp]))),
                         N._r(float(np.nanmean(D["mae_before_argmax"][grp]))),
                         N._r(float(np.nanmean(D["walled"][grp])), 4),
                         N._r(float(np.nanmean(D["cert_peak_usd"][grp]))),
                         N._r(float(np.nanmean(
                             D["exit_close_sec"][grp]
                             - D["dec_sec"][grp])))])
        N.hb("autopsy %s: top-decile %d takes, %d losers (%.1f%%)"
             % (era, top.size, los.size, 100.0 * los.size / max(top.size, 1)))
    N.write_tsv("CONFIDENCE_AUTOPSY.tsv",
                ["era", "group", "n", "mean_cert_usd", "mean_mae_usd",
                 "walled_rate", "mean_peak_usd", "mean_hold_sec"], rows,
                extra=["FIX 2a: what the top-decile LOSERS actually are.  The "
                       "hypothesis under test is that they are high-volatility "
                       "monsters carrying wall risk the dollar score cannot "
                       "see -- which would show as higher mean MAE, a higher "
                       "walled rate and a larger peak among TOPDEC_LOSS than "
                       "among TOPDEC_WIN."])
    return rows


def _selfcheck():
    for n_ in ("stage_agreement", "stage_autopsy", "agreement",
               "ceilings", "recut", "stage_riskadj", "stage_isotonic",
               "stage_combined"):
        if n_ not in globals():
            raise RuntimeError("confidence.py mis-assembled: %s" % n_)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agreement", action="store_true")
    ap.add_argument("--autopsy", action="store_true")
    ap.add_argument("--recut", action="store_true")
    ap.add_argument("--riskadj", action="store_true")
    ap.add_argument("--isotonic", action="store_true")
    ap.add_argument("--combined", action="store_true")
    ap.add_argument("--eras", default=",".join(ERAS))
    a = ap.parse_args()
    eras = tuple(e for e in a.eras.split(",") if e)
    if a.agreement:
        stage_agreement(eras)
    elif a.autopsy:
        stage_autopsy(eras)
    elif a.riskadj:
        stage_riskadj(eras)
    elif a.isotonic:
        stage_isotonic(eras)
    elif a.combined:
        stage_combined(eras)
    elif a.recut:
        ceilings(eras)
        recut("CONFIDENCE_AGREEMENT.tsv", "CONFIDENCE_AGREEMENT_CEIL.tsv")
    else:
        ap.print_help()

# ===================== THE CEILING DENOMINATOR (reporting standard) =========
# $2,000 is the FLOOR, not the aim.  Progress is read as a fraction of the
# ENTRY FORESIGHT CEILING: the per-cell oracle on the committed schedule -- the
# most any ranker could bank from this candidate pool with the answer in hand.
# Computed here per era AND per asset from the SAME replay every arm uses, so
# the numerator and denominator can never drift apart.
#
# NOTE ON PROVENANCE: this lane's own pooled entry ceiling is $3,152.31/session
# (NEWOBJ_CEILINGS.tsv, ORACLE_MEMBER_D0).  The seating-repair receipts quote
# ~$3,344 for the foresight bound; that is a different instrument on a different
# universe.  The lane-native number is used as the denominator because it is
# measured through the identical schedule and replay, and the discrepancy is
# stated rather than reconciled by preference.
CEIL_CACHE = "confidence_ceilings.json"
FLOOR_TARGET = 2000.0
AIM_LO, AIM_HI = 2500.0, 3000.0


def ceilings(eras=ERAS):
    c = N.load_json(CEIL_CACHE)
    if c:
        return c
    D, P = CF.boot()
    V = {0: N.delayed_value(P, 0, D)}
    out = {}
    for era in eras:
        ev = N.deployable(D, N.era_rows(D, era))
        n_ = N.committed_policy()[era][1]
        a = N.read_rows(D, N.replay_delayed(
            D, N.top_per_cell_joint(D, ev, V, n_, (0,)), P))
        out["%s|ALL" % era] = a["usd_per_session"]
        for ai in sorted(set(D["asset_idx"][ev].tolist())):
            sel = ev[D["asset_idx"][ev] == ai]
            aa = N.read_rows(D, N.replay_delayed(
                D, N.top_per_cell_joint(D, sel, V, n_, (0,)), P))
            out["%s|%s" % (era, MC.ASSET_ORDER[ai])] = aa["usd_per_session"]
        N.hb("ceiling %s: $%s/session (entry foresight, committed schedule)"
             % (era, N._r(out["%s|ALL" % era])))
    N.save_json(CEIL_CACHE, out)
    return out


def capture(era, usd, asset="ALL"):
    c = ceilings().get("%s|%s" % (era, asset))
    if not c or usd is None:
        return None
    return float(usd) / float(c)


def recut(src, dst):
    """Re-emit an existing confidence table with the ceiling columns added."""
    rows = [l.rstrip("\n").split("\t") for l in
            open(os.path.join(N.PROV, src)) if not l.startswith("#")]
    h = rows[0]
    ie, iu = h.index("era"), h.index("usd_per_session")
    out = []
    for r in rows[1:]:
        try:
            u = float(r[iu])
        except Exception:                               # noqa: BLE001
            u = None
        cp = capture(r[ie], u)
        cl = ceilings().get("%s|ALL" % r[ie])
        out.append(list(r) + [N._r(cl), N._r(cp, 4) if cp else "",
                              "FLOOR_OK" if (u or 0) >= FLOOR_TARGET else "",
                              "AIM_OK" if (u or 0) >= AIM_LO else ""])
    N.write_tsv(dst, h + ["entry_foresight_ceiling", "capture_of_ceiling",
                          "floor_2000", "aim_2500"], out,
                extra=EXTRA + [
                    "CAPTURE-OF-CEILING is $/session divided by the era's "
                    "ENTRY FORESIGHT CEILING (the per-cell oracle on the "
                    "committed schedule, measured through the identical "
                    "replay).  $2,000 is the FLOOR; the aim is $2,500-3,000 "
                    "per asset, i.e. a large fraction of the ceiling.",
                    "This lane's pooled entry ceiling is $3,152.31; the "
                    "seating-repair receipts quote ~$3,344 from a different "
                    "instrument.  The lane-native value is used so numerator "
                    "and denominator cannot drift; the discrepancy is stated."])
    return out

# ============ FIX 2b: RISK-ADJUSTED RE-RANK (the autopsy mandate) ===========
# THE AUTOPSY, which this implements against: E7 top-decile LOSERS are walled at
# 0.605 vs the winners' 0.067 -- 9x -- carry 2x the MAE (321 vs 158) and peak at
# a third of the winners' level.  They are high-volatility wall-risk monsters,
# and the dollar score cannot see it because MAE never enters the label.  So the
# ordering is penalised by a PREDICTED adverse excursion.
def _mae_head(D, era, seed=0):
    """A light predicted-MAE head, fitted on the training block only."""
    import xgboost as xgb
    tr, itr, iva, ev_r = NA.fold(D, era)
    cols, names = NA.feat_cols(D)
    XF = D["X"][:, cols]
    y = D["mae_before_argmax"].astype(np.float64)
    fit = tr[np.isfinite(y[tr])]
    cfg = {"objective": "reg:squarederror", "tree_method": "hist",
           "max_depth": 5, "eta": 0.08, "min_child_weight": 20,
           "subsample": 0.8, "colsample_bytree": 0.7,
           "seed": N.SEED + seed, "nthread": RA.N_THREAD}
    b = xgb.train(cfg, xgb.DMatrix(XF[fit], label=y[fit],
                                   feature_names=names), 120)
    out = np.full(D["d8"].size, np.nan)
    out[ev_r] = b.predict(xgb.DMatrix(XF[ev_r], feature_names=names))
    return out, ev_r


def stage_riskadj(eras=ERAS):
    D, P = CF.boot()
    rows = []
    for era in eras:
        S = _members(era)
        if not S:
            continue
        ens = np.nanmean(np.vstack(S), axis=0)
        ev = N.deployable(D, N.era_rows(D, era))
        n_ = N.committed_policy()[era][1]
        pm, _e = _mae_head(D, era)
        sp = _pct(D, ev, ens)
        mp = _pct(D, ev, pm)
        for lam in LAMBDAS:
            adj = sp - lam * mp
            tk = N.top_per_cell_score(D, ev, adj, n_)
            a, g, pdb, pt = _read(D, P, tk, era, "RISKADJ")
            r = _row(era, "RISKADJ", N._r(lam, 2), a, g, pdb, pt)
            cl = ceilings().get("%s|ALL" % era)
            rows.append(r + [N._r(cl),
                             N._r(capture(era, a.get("usd_per_session")), 4)])
        N.hb("riskadj %s done" % era)
    N.write_tsv("CONFIDENCE_RISKADJ.tsv",
                COLS + ["entry_foresight_ceiling", "capture_of_ceiling"], rows,
                extra=EXTRA + [
                    "FIX 2b: re-rank by within-cell score percentile MINUS "
                    "lambda x predicted-MAE percentile.  lambda=0 is the "
                    "unmodified arm, so the sweep contains its own null.",
                    "Mandated by the autopsy: top-decile losers are walled 9x "
                    "more often than top-decile winners and carry 2x the MAE, "
                    "and the dollar label cannot see either."])
    return rows


# ================= FIX 3: PER-ERA ISOTONIC CALIBRATION ======================
def stage_isotonic(eras=ERAS):
    """score percentile -> dollars, fitted on PRIOR eras, applied forward."""
    from sklearn.isotonic import IsotonicRegression
    D, P = CF.boot()
    rows, hist = [], []
    for era in eras:
        S = _members(era)
        if not S:
            continue
        ens = np.nanmean(np.vstack(S), axis=0)
        ev = N.deployable(D, N.era_rows(D, era))
        n_ = N.committed_policy()[era][1]
        sp = _pct(D, ev, ens)
        if hist:
            x = np.concatenate([h[0] for h in hist])
            y = np.concatenate([h[1] for h in hist])
            iso = IsotonicRegression(out_of_bounds="clip").fit(x, y)
            cal = np.full(D["d8"].size, np.nan)
            m = np.isfinite(sp)
            cal[m] = iso.predict(sp[m])
            note = "prior-era isotonic"
        else:
            cal = ens
            note = "NO PRIOR ERA - uncalibrated"
        tk = N.top_per_cell_score(D, ev, cal, n_)
        a, g, pdb, pt = _read(D, P, tk, era, "ISO")
        cl = ceilings().get("%s|ALL" % era)
        rows.append(_row(era, "ISOTONIC", note, a, g, pdb, pt)
                    + [N._r(cl),
                       N._r(capture(era, a.get("usd_per_session")), 4)])
        idx = np.asarray([i for i, _d in N.top_per_cell_score(D, ev, ens, n_)],
                         dtype=np.int64)
        hist.append((sp[idx], D["cert_close_usd"][idx].astype(np.float64)))
        N.hb("isotonic %s done (%s)" % (era, note))
    N.write_tsv("CONFIDENCE_ISOTONIC.tsv",
                COLS + ["entry_foresight_ceiling", "capture_of_ceiling"], rows,
                extra=EXTRA + [
                    "FIX 3: isotonic calibration of within-cell score "
                    "percentile -> realised dollars, fitted on the PRIOR eras' "
                    "takes and applied forward.  E3 has no prior era and is "
                    "reported uncalibrated and flagged."])
    return rows


def stage_combined(eras=ERAS, taus=(0.7, 0.8, 0.85, 0.9), lam=0.5):
    """THE CONFIDENCE-SELECTIVE ARM: agreement x risk-adjustment."""
    D, P = CF.boot()
    rows = []
    for era in eras:
        S = _members(era)
        if not S:
            continue
        ens = np.nanmean(np.vstack(S), axis=0)
        ev = N.deployable(D, N.era_rows(D, era))
        n_ = N.committed_policy()[era][1]
        pm, _e = _mae_head(D, era)
        adj = _pct(D, ev, ens) - lam * _pct(D, ev, pm)
        base = N.top_per_cell_score(D, ev, adj, n_)
        _p, frac = agreement(D, ev, S, n_)
        for tau in taus:
            tk = [(i, d) for (i, d) in base if frac.get(i, 0.0) >= tau]
            if not tk:
                continue
            a, g, pdb, pt = _read(D, P, tk, era, "COMBINED")
            cl = ceilings().get("%s|ALL" % era)
            rows.append(_row(era, "COMBINED", "agree=%.2f,lam=%.2f"
                             % (tau, lam), a, g, pdb, pt)
                        + [N._r(cl),
                           N._r(capture(era, a.get("usd_per_session")), 4)])
        N.hb("combined %s done" % era)
    N.write_tsv("CONFIDENCE_COMBINED.tsv",
                COLS + ["entry_foresight_ceiling", "capture_of_ceiling"], rows,
                extra=EXTRA + [
                    "THE CONFIDENCE-SELECTIVE ARM: ensemble-agreement gating on "
                    "a risk-adjusted ordering.  Targets on the face of the "
                    "table: FLOOR $%d/session/asset, AIM $%d-%d, and "
                    "capture_of_ceiling against the entry foresight bound."
                    % (int(FLOOR_TARGET), int(AIM_LO), int(AIM_HI))])
    return rows


if __name__ == "__main__":
    _selfcheck()
    main()
