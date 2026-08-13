#!/usr/bin/python3
"""PORT M2 — P001 PHASE_ROLLOVER_UNDERMOVED name->count census.

The FIRST pattern through the codification loop (DISCRETIONARY_METHOD §4.2
ORCH-1: "every named pattern becomes a computable strictly-causal detector,
censused over ALL train sessions: fire rate, conditional value, per-quarter
stability, MECHANISM DESTRUCTION").  The pattern is the P-M2c warm-up's
principal product; PATTERN_LEDGER.tsv carries it as ACTIVE on n=3 and
CC-M2-7.2 rules that it "remains a HYPOTHESIS and its name->count census (on
corrected data) is its test".

THE DETECTOR (PATTERN_LEDGER P001 `sheet_fields`, five terms, ALL strictly
causal — every input is read from the V1.1-correct pattern_lib frame):

  T1 COVERAGE   S3.COVERAGE_phase <= 0.70.  REFUSED (the fvol row carries no
                move_q50) => the term is FALSE and the detector does not fire.
  T2 LADDER     S9.ladder_position in {below_q10, at_or_above_q10}.  The V1.1
                D1 law: the band is REFUSED whenever the fvol row carries no
                move_q* quantiles, and a refused band does NOT fire.  (The
                warm-up read this field off V1 sheets that printed a band
                beside five refused quantiles — that is the defect this census
                is run on corrected data to escape.)
  T3 RUNWAY     S3.runway_to_phase_close >= 26,000s AND S13.exit_default is the
                SESSION close (phase_close_sec == sess_close_sec).
  T4 AGE        the faded phase extreme is YOUNG: age <= 200s.
                TWO READINGS ARE CENSUSED (defect D-P001-1, see the report):
                  A (ledger-literal) age of S3.phase H (SHORT) / L (LONG);
                  B (reader-literal) age of the most recent CAUSAL ZigZag
                    pivot of the faded type.
                They agree on 2 of the pattern's 3 support cases and disagree
                on the third (1236s vs the 93s the post-mortem quotes), so the
                census reports both and lets the orchestrator rule.
  T5 SLOPE      S5.mid_slope_$/min (the last-minute column) AND S5.accel(1m-5m)
                are BOTH signed with the candidate's side, both non-zero.

POPULATION: every candidate of the frozen v3 roster (union_roster_{ASSET}.npz)
on every FIT session (2021-2024) of all three assets, plus the 2025 GATE year
as an EVAL-ONLY echo (D-058 era law: GATE is never fitted on).

MEASURED (CC-M1-8: BOTH certificate readings everywhere)
  * fire rate per session/day, per asset x era;
  * conditional walled certificate of the firing set vs the non-firing
    baseline — phase-close (adoption) and peak-exit (companion);
  * per-FIT-year stability + the 2025 GATE echo;
  * the co-occurrence break-out the era note demands (the support set was all
    HG / all NY / all SHORT): per-asset, per-phase and per-side rows;
  * TERM MARGINALS: what each term does alone, and what the detector does with
    that term dropped (the near-miss populations the era note asked for);
  * MECHANISM DESTRUCTION: each term individually neutralised by SHUFFLING it
    WITHIN ITS SESSION (the joint structure of the other four is preserved) —
    value that survives the destruction was never that term's;
  * CC-M1-12.4 cluster-robust inference: GEE/Liang-Zeger sandwich clustered on
    SESSION with the Cameron-Miller CR1 scaling, plus the Kish DEFF / n_eff.

OUTPUT (D-018: bulk under artifacts/cache/)
  artifacts/cache/port/m2/pattern_census/P001_CENSUS_REPORT.md
  artifacts/cache/port/m2/pattern_census/P001_{FIRES,CENSUS,TERMS,
                                              DESTRUCTION,ROBUST}.tsv
  artifacts/cache/port/m2/pattern_census/p001_census.receipt.json

Run:  lab/run.sh port-m2-p001 -- /usr/bin/python3 engine/port_m2/p001_census.py
"""
import argparse
import json
import os
import sys
import time

import multiprocessing as mp

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_M1 = "/workspace/engine/port_m1"
if _M1 not in sys.path:
    sys.path.insert(0, _M1)

import m2_common as MC                    # noqa: E402
import pattern_lib as PL                  # noqa: E402
import census_common as X                 # noqa: E402
import episode_v2 as EV                   # noqa: E402  (GEE sandwich, ICC/DEFF)

SECTION = "DISCRETIONARY_METHOD §4.2 name->count census — P001"
OUT_DIR = MC.out_path("pattern_census", "_")[:-1]

PATTERN_ID = "P001"
PATTERN_NAME = "PHASE_ROLLOVER_UNDERMOVED"

# ------------------------------------------------------------- the terms ----
COVERAGE_MAX = 0.70                       # T1, inclusive (ledger: "<= 70%")
LADDER_BANDS_FIRE = (0, 1)                # T2: below_q10, at_or_above_q10
RUNWAY_MIN_SEC = 26000                    # T3, inclusive
AGE_MAX_SEC = 200                         # T4, inclusive
TERMS = ("T1_coverage", "T2_ladder", "T3_runway", "T4_age", "T5_slope")

FIT_YEARS = (2021, 2022, 2023, 2024)
GATE_YEAR = 2025

DESTRUCTION_REPS = 40
DESTRUCTION_SEED = 20260814

PARAMS = {
    "spec_section": SECTION,
    "pattern": "%s %s" % (PATTERN_ID, PATTERN_NAME),
    "definition_source": "provenance/port_m2/PATTERN_LEDGER.tsv (sheet_fields)"
                         " + provenance/port_m2/WARMUP_POSTMORTEMS.md F1",
    "T1_coverage": "pattern_lib coverage_phase <= %.2f; REFUSED => FALSE"
                   % COVERAGE_MAX,
    "T2_ladder": "pattern_lib ladder_band in %s (below_q10, at_or_above_q10); "
                 "REFUSED (-1) => FALSE (V1.1 D1)" % (LADDER_BANDS_FIRE,),
    "T3_runway": "runway_phase_sec >= %d AND phase_close_sec == sess_close_sec"
                 % RUNWAY_MIN_SEC,
    "T4_age_A": "extreme_age_sec (phase H for SHORT / L for LONG) in [0, %d]"
                % AGE_MAX_SEC,
    "T4_age_B": "pivot_age_sec (most recent causal ZigZag pivot of the faded "
                "type) in [0, %d]" % AGE_MAX_SEC,
    "T5_slope": "sign(slope_1m_usd) == side and sign(accel_usd) == side, both "
                "non-zero",
    "value": "c_c_roster.certificates — walled PHASE-CLOSE (adoption) and "
             "walled PEAK-EXIT (CC-M1-8 companion), both always reported",
    "conditional_value": "mean over POSITIVE candidates (CC-M1-7.3)",
    "winner": "cert_close >= $1000 and mae_before_argmax <= $300 and not "
              "walled (D-021)",
    "population": "frozen v3 roster, FIT years %s; %d = GATE echo, EVAL-ONLY"
                  % (list(FIT_YEARS), GATE_YEAR),
    "destruction": "each term shuffled WITHIN SESSION, %d replicates, "
                   "RandomState(%d); the other four terms untouched"
                   % (DESTRUCTION_REPS, DESTRUCTION_SEED),
    "inference": "CC-M1-12.4 — GEE independence working correlation with the "
                 "Liang-Zeger sandwich clustered on SESSION (CR0 + "
                 "Cameron-Miller CR1); Kish one-way ICC/DEFF for n_eff",
    "frame": PL.PARAMS_FRAME,
}


def terms_of(f, reading="A"):
    """The five term indicators for every candidate of one session frame."""
    cov = f["coverage_phase"]
    t1 = np.isfinite(cov) & (cov <= COVERAGE_MAX)
    band = f["ladder_band"]
    t2 = np.zeros(band.size, dtype=bool)
    for b in LADDER_BANDS_FIRE:
        t2 |= (band == b)
    t3 = (f["runway_phase_sec"] >= RUNWAY_MIN_SEC) & f["session_close_exit"]
    age = f["extreme_age_sec"] if reading == "A" else f["pivot_age_sec"]
    t4 = (age >= 0) & (age <= AGE_MAX_SEC)
    side = f["side"].astype(np.float64)
    sl = f["slope_1m_usd"]
    ac = f["accel_usd"]
    t5 = (np.isfinite(sl) & np.isfinite(ac)
          & (np.sign(sl) == np.sign(side)) & (np.sign(ac) == np.sign(side)))
    return np.column_stack([t1, t2, t3, t4, t5])


# --------------------------------------------------------------- the pass ---
_COLS = ("asset", "d8", "dec_sec", "side", "phase_dec", "klass",
         "cert_close", "cert_peak", "walled", "winner",
         "termsA", "termsB", "coverage_phase", "ladder_band",
         "runway_phase_sec", "extreme_age_sec", "pivot_age_sec",
         "slope_1m_usd", "accel_usd")


def _pack(f):
    ta = terms_of(f, "A")
    tb = terms_of(f, "B")
    def bits(t):
        out = np.zeros(t.shape[0], dtype=np.uint8)
        for k in range(t.shape[1]):
            out |= (t[:, k].astype(np.uint8) << k)
        return out
    return {
        "asset": f["asset"], "d8": f["d8"],
        "dec_sec": f["dec_sec"].astype(np.int32),
        "side": f["side"].astype(np.int8),
        "phase_dec": f["phase_dec"].astype(np.int8),
        "klass": f["klass"],
        "cert_close": f["cert_close_usd"].astype(np.float64),
        "cert_peak": f["cert_peak_usd"].astype(np.float64),
        "walled": f["walled"], "winner": f["winner"],
        "termsA": bits(ta), "termsB": bits(tb),
        "coverage_phase": f["coverage_phase"].astype(np.float32),
        "ladder_band": f["ladder_band"].astype(np.int8),
        "runway_phase_sec": f["runway_phase_sec"].astype(np.int32),
        "extreme_age_sec": f["extreme_age_sec"].astype(np.int32),
        "pivot_age_sec": f["pivot_age_sec"].astype(np.int32),
        "slope_1m_usd": f["slope_1m_usd"].astype(np.float32),
        "accel_usd": f["accel_usd"].astype(np.float32),
    }


def _one(job):
    asset, d8 = job
    try:
        f = PL.frame(asset, int(d8), with_levels=False)
    except Exception as e:                # noqa: BLE001 — surfaced, not hidden
        return ("ERROR", asset, int(d8), repr(e)[:300])
    if f is None:
        return ("EMPTY", asset, int(d8), "")
    return ("OK", _pack(f))


def scan(assets=MC.ASSET_ORDER, years=FIT_YEARS + (GATE_YEAR,), workers=4,
         limit_sessions=None):
    jobs = []
    for a in assets:
        ds = PL.sessions(a, years=set(years))
        if limit_sessions:
            ds = ds[:limit_sessions]
        jobs += [(a, d) for d in ds]
    jobs.sort()
    parts, errs = [], []
    t0 = time.time()
    if workers and workers > 1:
        with mp.Pool(processes=int(workers)) as pool:
            for n, res in enumerate(pool.imap(_one, jobs, chunksize=8), 1):
                if res[0] == "OK":
                    parts.append(res[1])
                elif res[0] == "ERROR":
                    errs.append((res[1], res[2], res[3]))
                if n % 250 == 0:
                    MC.hb("p001 scan %d/%d  %.1fs" % (n, len(jobs),
                                                      time.time() - t0))
    else:
        for n, j in enumerate(jobs, 1):
            res = _one(j)
            if res[0] == "OK":
                parts.append(res[1])
            elif res[0] == "ERROR":
                errs.append((res[1], res[2], res[3]))
    if errs:
        raise RuntimeError("p001 scan: %d session(s) failed, first=%s"
                           % (len(errs), errs[0]))
    parts.sort(key=lambda p: (p["asset"], p["d8"]))
    out = {}
    for k in ("dec_sec", "side", "phase_dec", "cert_close", "cert_peak",
              "walled", "winner", "termsA", "termsB", "coverage_phase",
              "ladder_band", "runway_phase_sec", "extreme_age_sec",
              "pivot_age_sec", "slope_1m_usd", "accel_usd", "klass"):
        out[k] = np.concatenate([p[k] for p in parts])
    out["asset"] = np.concatenate([np.full(p["dec_sec"].size, p["asset"])
                                   for p in parts])
    out["d8"] = np.concatenate([np.full(p["dec_sec"].size, p["d8"],
                                        dtype=np.int32) for p in parts])
    out["year"] = (out["d8"] // 10000).astype(np.int32)
    # session cluster id, stable and deterministic (sorted asset, then d8)
    keys = np.array(["%s-%08d" % (a, d) for a, d in
                     zip(out["asset"].tolist(), out["d8"].tolist())])
    uniq, out["cluster"] = np.unique(keys, return_inverse=True)
    out["n_sessions_total"] = int(uniq.size)
    MC.hb("p001 scan: %d candidates over %d sessions, %.1fs"
          % (out["dec_sec"].size, uniq.size, time.time() - t0))
    return out


def unbits(b):
    return np.column_stack([((b >> k) & 1).astype(bool)
                            for k in range(len(TERMS))])


# ------------------------------------------------------------ aggregation ---
def _stats(cert_close, cert_peak, winner, n_sessions):
    n = int(cert_close.size)
    pos_c = cert_close[cert_close > 0]
    pos_p = cert_peak[cert_peak > 0]
    return {
        "n_candidates": n,
        "n_sessions": int(n_sessions),
        "per_session": (float(n) / n_sessions) if n_sessions else float("nan"),
        "mean_close": float(cert_close.mean()) if n else float("nan"),
        "cond_close": float(pos_c.mean()) if pos_c.size else float("nan"),
        "posfrac_close": (float(pos_c.size) / n) if n else float("nan"),
        "mean_peak": float(cert_peak.mean()) if n else float("nan"),
        "cond_peak": float(pos_p.mean()) if pos_p.size else float("nan"),
        "posfrac_peak": (float(pos_p.size) / n) if n else float("nan"),
        "n_winners": int(winner.sum()),
        "winner_frac": (float(winner.sum()) / n) if n else float("nan"),
    }


CENSUS_COLUMNS = ("reading", "asset", "era", "phase", "side", "group",
                  "n_sessions", "n_candidates", "per_session", "mean_close",
                  "cond_close", "posfrac_close", "mean_peak", "cond_peak",
                  "posfrac_peak", "n_winners", "winner_frac")


def _row(reading, asset, era, phase, side, group, st):
    return [reading, asset, era, phase, side, group,
            st["n_sessions"], st["n_candidates"], st["per_session"],
            st["mean_close"], st["cond_close"], st["posfrac_close"],
            st["mean_peak"], st["cond_peak"], st["posfrac_peak"],
            st["n_winners"], st["winner_frac"]]


def census_rows(D, fire, reading):
    rows = []
    era_sel = [("FIT", np.isin(D["year"], FIT_YEARS)),
               ("GATE_%d" % GATE_YEAR, D["year"] == GATE_YEAR)]
    era_sel += [(str(y), D["year"] == y) for y in FIT_YEARS]
    assets = [("ALL", np.ones(fire.size, dtype=bool))]
    assets += [(a, D["asset"] == a) for a in MC.ASSET_ORDER]
    fit = np.isin(D["year"], FIT_YEARS)

    def emit(asel, aname, esel, ename, psel, pname, ssel, sname):
        base = asel & esel & psel & ssel
        if not base.any():
            return
        nsess = len(set(D["cluster"][base].tolist()))
        for group, m in (("FIRE", base & fire), ("NOFIRE", base & ~fire)):
            if not m.any():
                rows.append(_row(reading, aname, ename, pname, sname, group,
                                 {"n_candidates": 0, "n_sessions": nsess,
                                  "per_session": 0.0, "mean_close": float("nan"),
                                  "cond_close": float("nan"),
                                  "posfrac_close": float("nan"),
                                  "mean_peak": float("nan"),
                                  "cond_peak": float("nan"),
                                  "posfrac_peak": float("nan"),
                                  "n_winners": 0,
                                  "winner_frac": float("nan")}))
                continue
            rows.append(_row(reading, aname, ename, pname, sname, group,
                             _stats(D["cert_close"][m], D["cert_peak"][m],
                                    D["winner"][m], nsess)))

    allm = np.ones(fire.size, dtype=bool)
    for aname, asel in assets:
        for ename, esel in era_sel:
            emit(asel, aname, esel, ename, allm, "ALL", allm, "ALL")
        for p in range(X.N_PHASES):
            emit(asel, aname, fit, "FIT", D["phase_dec"] == p,
                 X.PHASE_NAMES[p], allm, "ALL")
        for sv, sn in ((1, "LONG"), (-1, "SHORT")):
            emit(asel, aname, fit, "FIT", allm, "ALL", D["side"] == sv, sn)
    return rows


TERM_COLUMNS = ("reading", "asset", "scope", "term", "n_candidates",
                "per_session", "mean_close", "cond_close", "posfrac_close",
                "mean_peak", "cond_peak", "n_winners", "winner_frac")


def term_rows(D, T, reading):
    """What each term does ALONE, and what the detector does with it DROPPED
    (the leave-one-out near-miss populations the E1 era note asked for)."""
    rows = []
    fit = np.isin(D["year"], FIT_YEARS)
    assets = [("ALL", np.ones(fit.size, dtype=bool))]
    assets += [(a, D["asset"] == a) for a in MC.ASSET_ORDER]
    for aname, asel in assets:
        base = asel & fit
        if not base.any():
            continue
        nsess = len(set(D["cluster"][base].tolist()))
        for k, name in enumerate(TERMS):
            for scope, m in (("TERM_ALONE", base & T[:, k]),
                             ("DETECTOR_MINUS_TERM",
                              base & np.all(np.delete(T, k, axis=1), axis=1)),
                             ("NEAR_MISS_ONLY_THIS_TERM_FAILS",
                              base & ~T[:, k]
                              & np.all(np.delete(T, k, axis=1), axis=1))):
                if not m.any():
                    continue
                st = _stats(D["cert_close"][m], D["cert_peak"][m],
                            D["winner"][m], nsess)
                rows.append([reading, aname, scope, name, st["n_candidates"],
                             st["per_session"], st["mean_close"],
                             st["cond_close"], st["posfrac_close"],
                             st["mean_peak"], st["cond_peak"],
                             st["n_winners"], st["winner_frac"]])
    return rows


DESTRUCTION_COLUMNS = ("reading", "asset", "neutralised_term", "n_fires_mean",
                       "n_fires_sd", "mean_close_mean", "mean_close_sd",
                       "cond_close_mean", "cond_close_sd", "mean_peak_mean",
                       "cond_peak_mean", "intact_n_fires",
                       "intact_mean_close", "intact_cond_close",
                       "value_retention_mean_close", "verdict")


def destruction_rows(D, T, reading):
    """Neutralise each term by SHUFFLING IT WITHIN ITS SESSION.

    Within-session shuffling preserves the session's regime, its clock, its
    term base rates and the joint structure of the other four terms, and
    destroys only the alignment of THIS term with the candidate.  Value that
    survives was never this term's contribution.
    """
    rows = []
    fit = np.isin(D["year"], FIT_YEARS)
    cluster = D["cluster"]
    order = np.argsort(cluster[fit], kind="stable")
    idx_fit = np.nonzero(fit)[0][order]
    cl = cluster[idx_fit]
    edges = np.flatnonzero(cl[1:] != cl[:-1]) + 1
    starts = np.concatenate(([0], edges))
    stops = np.concatenate((edges, [cl.size]))
    Tf = T[idx_fit]
    cc = D["cert_close"][idx_fit]
    cp = D["cert_peak"][idx_fit]
    wn = D["winner"][idx_fit]
    asset_f = D["asset"][idx_fit]
    nsess = int(starts.size)

    assets = [("ALL", np.ones(idx_fit.size, dtype=bool))]
    assets += [(a, asset_f == a) for a in MC.ASSET_ORDER]
    intact = np.all(Tf, axis=1)

    for k, name in enumerate(TERMS):
        rs = np.random.RandomState(DESTRUCTION_SEED + k)
        others = np.all(np.delete(Tf, k, axis=1), axis=1)
        acc = {aname: {"n": [], "mc": [], "cd": [], "mp": [], "cdp": []}
               for aname, _ in assets}
        for _rep in range(DESTRUCTION_REPS):
            perm = Tf[:, k].copy()
            for s, e in zip(starts.tolist(), stops.tolist()):
                if e - s > 1:
                    perm[s:e] = perm[s:e][rs.permutation(e - s)]
            fired = others & perm
            for aname, asel in assets:
                m = fired & asel
                a = acc[aname]
                a["n"].append(int(m.sum()))
                if m.any():
                    v = cc[m]
                    p = cp[m]
                    a["mc"].append(float(v.mean()))
                    a["mp"].append(float(p.mean()))
                    pv = v[v > 0]
                    pp = p[p > 0]
                    a["cd"].append(float(pv.mean()) if pv.size else np.nan)
                    a["cdp"].append(float(pp.mean()) if pp.size else np.nan)
                else:
                    a["mc"].append(np.nan)
                    a["mp"].append(np.nan)
                    a["cd"].append(np.nan)
                    a["cdp"].append(np.nan)
        for aname, asel in assets:
            im = intact & asel
            i_st = _stats(cc[im], cp[im], wn[im], nsess) if im.any() else None
            a = acc[aname]
            nm = float(np.mean(a["n"]))
            mc = float(np.nanmean(a["mc"])) if np.any(np.isfinite(a["mc"])) else float("nan")
            cd = float(np.nanmean(a["cd"])) if np.any(np.isfinite(a["cd"])) else float("nan")
            i_mc = i_st["mean_close"] if i_st else float("nan")
            i_cd = i_st["cond_close"] if i_st else float("nan")
            ret = (mc / i_mc) if (i_st and np.isfinite(i_mc) and i_mc != 0
                                  and np.isfinite(mc)) else float("nan")
            if not np.isfinite(ret):
                verdict = "UNDECIDED_no_intact_fires"
            elif ret >= 0.80:
                verdict = "TERM_NOT_LOAD_BEARING"
            elif ret <= 0.50:
                verdict = "TERM_LOAD_BEARING"
            else:
                verdict = "PARTIAL"
            rows.append([reading, aname, name, nm, float(np.std(a["n"])),
                         mc, float(np.nanstd(a["mc"])), cd,
                         float(np.nanstd(a["cd"])),
                         float(np.nanmean(a["mp"])) if np.any(np.isfinite(a["mp"])) else float("nan"),
                         float(np.nanmean(a["cdp"])) if np.any(np.isfinite(a["cdp"])) else float("nan"),
                         int(i_st["n_candidates"]) if i_st else 0,
                         i_mc, i_cd, ret, verdict])
    return rows


ROBUST_COLUMNS = ("reading", "asset", "era", "metric", "n", "n_clusters",
                  "n_fires", "beta_usd", "se_naive", "se_cr0", "se_cr1",
                  "z_cr1", "p_cr1", "icc_rho", "deff", "n_eff", "verdict")


def _p_two_sided(z):
    import math
    if not np.isfinite(z):
        return float("nan")
    return math.erfc(abs(z) / math.sqrt(2.0))


def robust_rows(D, fire, reading):
    """CC-M1-12.4: GEE (identity link) of the certificate on the fire flag,
    Liang-Zeger sandwich clustered on SESSION, + Kish DEFF / n_eff."""
    rows = []
    era_sel = [("FIT", np.isin(D["year"], FIT_YEARS)),
               ("GATE_%d" % GATE_YEAR, D["year"] == GATE_YEAR)]
    assets = [("ALL", np.ones(fire.size, dtype=bool))]
    assets += [(a, D["asset"] == a) for a in MC.ASSET_ORDER]
    for aname, asel in assets:
        for ename, esel in era_sel:
            m = asel & esel
            if not m.any():
                continue
            x = fire[m].astype(np.float64)
            cl = D["cluster"][m]
            nf = int(x.sum())
            for metric, y in (("cert_close", D["cert_close"][m]),
                              ("cert_peak", D["cert_peak"][m])):
                g = (EV.gee_independence(y, x, cl, link="identity")
                     if nf > 0 and nf < x.size else None)
                ic = EV.icc_oneway(y, cl)
                if g is None:
                    rows.append([reading, aname, ename, metric, int(y.size),
                                 int(len(set(cl.tolist()))), nf,
                                 float("nan")] + [float("nan")] * 6
                                + [ic["rho"] if ic else float("nan"),
                                   ic["deff"] if ic else float("nan"),
                                   ic["n_eff"] if ic else float("nan"),
                                   "NO_VARIATION"])
                    continue
                z = (g["beta"] / g["se_cr1"]) if g["se_cr1"] > 0 else float("nan")
                p = _p_two_sided(z)
                verdict = ("SIGNIFICANT_p<0.05" if np.isfinite(p) and p < 0.05
                           else "NOT_SIGNIFICANT")
                rows.append([reading, aname, ename, metric, g["n"],
                             g["n_clusters"], nf, g["beta"], g["se_naive"],
                             g["se_cr0"], g["se_cr1"], z, p,
                             ic["rho"] if ic else float("nan"),
                             ic["deff"] if ic else float("nan"),
                             ic["n_eff"] if ic else float("nan"), verdict])
    return rows


FIRE_COLUMNS = ("reading", "cid", "asset", "d8", "year", "era", "phase",
                "side", "class", "coverage_phase", "ladder_band",
                "runway_phase_sec", "extreme_age_sec", "pivot_age_sec",
                "slope_1m_usd", "accel_usd", "cert_close_usd",
                "cert_peak_usd", "walled", "winner")


def fire_rows(D, fire, reading):
    rows = []
    idx = np.nonzero(fire)[0]
    for t in idx.tolist():
        a = str(D["asset"][t])
        d8 = int(D["d8"][t])
        rows.append([reading,
                     MC.make_cid(a, d8, int(D["dec_sec"][t]), int(D["side"][t])),
                     a, d8, int(D["year"][t]), MC.era_of(d8),
                     X.PHASE_NAMES[int(D["phase_dec"][t])],
                     "LONG" if D["side"][t] > 0 else "SHORT",
                     str(D["klass"][t]),
                     float(D["coverage_phase"][t]),
                     PL.LADDER_BANDS[int(D["ladder_band"][t])]
                     if D["ladder_band"][t] >= 0 else "REFUSED",
                     int(D["runway_phase_sec"][t]),
                     int(D["extreme_age_sec"][t]), int(D["pivot_age_sec"][t]),
                     float(D["slope_1m_usd"][t]), float(D["accel_usd"][t]),
                     float(D["cert_close"][t]), float(D["cert_peak"][t]),
                     bool(D["walled"][t]), bool(D["winner"][t])])
    rows.sort(key=lambda r: (r[0], r[2], r[3], r[1]))
    return rows


# ---------------------------------------------------------------- report ----
def _fmt(v, dec=2):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "."
    if isinstance(v, float):
        return ("%%.%df" % dec) % v
    return str(v)


def report(D, res, elapsed, pins):
    L = []
    A = L.append
    A("# P001 PHASE_ROLLOVER_UNDERMOVED — name->count census")
    A("")
    A("Pattern: `%s %s` (provenance/port_m2/PATTERN_LEDGER.tsv). The first "
      "pattern through the DISCRETIONARY_METHOD §4.2 codification loop, run on "
      "V1.1-correct data per CC-M2-7.2." % (PATTERN_ID, PATTERN_NAME))
    A("")
    A("Population: the frozen v3 roster, %d candidates over %d sessions "
      "(FIT %s + the %d GATE echo), all three assets."
      % (int(D["dec_sec"].size), int(D["n_sessions_total"]),
         "-".join(str(y) for y in (FIT_YEARS[0], FIT_YEARS[-1])), GATE_YEAR))
    A("")

    for reading in ("A", "B"):
        r = res[reading]
        cen = {(x[1], x[2], x[3], x[4], x[5]): x for x in r["census"]}
        fitF = cen.get(("ALL", "FIT", "ALL", "ALL", "FIRE"))
        fitN = cen.get(("ALL", "FIT", "ALL", "ALL", "NOFIRE"))
        A("## READING %s — T4 age = %s" % (
            reading,
            "the phase extreme (PATTERN_LEDGER literal)" if reading == "A"
            else "the most recent causal ZigZag pivot (post-mortem literal)"))
        A("")
        if fitF is None or fitF[7] == 0:
            A("**The detector never fires on FIT.**")
            A("")
            continue
        A("| | fires | per session | mean close $ | cond. close $ | "
          "mean peak $ | cond. peak $ | winners |")
        A("|---|---|---|---|---|---|---|---|")
        for tag, x in (("FIRE", fitF), ("NOFIRE", fitN)):
            A("| %s | %d | %s | %s | %s | %s | %s | %d (%s%%) |"
              % (tag, x[7], _fmt(x[8], 3), _fmt(x[9]), _fmt(x[10]),
                 _fmt(x[12]), _fmt(x[13]), x[15], _fmt(100.0 * x[16], 2)))
        A("")
        A("Per-year stability (ALL assets, FIRE group):")
        A("")
        A("| year | fires | per session | mean close $ | cond. close $ | "
          "mean peak $ |")
        A("|---|---|---|---|---|---|")
        for y in [str(v) for v in FIT_YEARS] + ["GATE_%d" % GATE_YEAR]:
            x = cen.get(("ALL", y, "ALL", "ALL", "FIRE"))
            n = cen.get(("ALL", y, "ALL", "ALL", "NOFIRE"))
            if x is None:
                continue
            A("| %s%s | %d | %s | %s | %s | %s |"
              % (y, " (eval-only)" if y.startswith("GATE") else "",
                 x[7], _fmt(x[8], 3), _fmt(x[9]), _fmt(x[10]), _fmt(x[12])))
            A("| %s baseline | %d | %s | %s | %s | %s |"
              % (y, n[7], _fmt(n[8], 3), _fmt(n[9]), _fmt(n[10]), _fmt(n[12])))
        A("")
        A("Co-occurrence break-out (FIT, FIRE group) — the E1 note flagged the "
          "support set as all-HG / all-NY / all-SHORT:")
        A("")
        A("| stratum | fires | mean close $ | cond. close $ | baseline mean $ |")
        A("|---|---|---|---|---|")
        for key in sorted(cen):
            an, en, pn, sn, gp = key
            if gp != "FIRE" or en != "FIT":
                continue
            if an == "ALL" and pn == "ALL" and sn == "ALL":
                continue
            x = cen[key]
            b = cen.get((an, en, pn, sn, "NOFIRE"))
            if x[7] == 0:
                continue
            A("| %s / %s / %s | %d | %s | %s | %s |"
              % (an, pn, sn, x[7], _fmt(x[9]), _fmt(x[10]),
                 _fmt(b[9]) if b else "."))
        A("")
        A("Mechanism destruction (FIT, ALL assets; each term shuffled within "
          "its session, %d replicates). `value_retention` = destroyed mean "
          "close / intact mean close: high retention means the term was not "
          "carrying the value." % DESTRUCTION_REPS)
        A("")
        A("| neutralised term | fires (mean) | mean close $ | retention | "
          "verdict |")
        A("|---|---|---|---|---|")
        for x in r["destruction"]:
            if x[1] != "ALL":
                continue
            A("| %s | %s | %s | %s | %s |"
              % (x[2], _fmt(x[3], 1), _fmt(x[5]), _fmt(x[14], 3), x[15]))
        A("")
        A("Cluster-robust inference (CC-M1-12.4; GEE identity link, "
          "Liang-Zeger sandwich clustered on SESSION, CR1 scaling):")
        A("")
        A("| asset | era | metric | beta $ | se naive | se CR1 | z | p | "
          "DEFF | n_eff | verdict |")
        A("|---|---|---|---|---|---|---|---|---|---|---|")
        for x in r["robust"]:
            A("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |"
              % (x[1], x[2], x[3], _fmt(x[7]), _fmt(x[8]), _fmt(x[10]),
                 _fmt(x[11], 2), _fmt(x[12], 5), _fmt(x[14], 2),
                 _fmt(x[15], 1), x[16]))
        A("")
        A("Term marginals (FIT, ALL assets):")
        A("")
        A("| term | alone: n / mean close $ | detector without it: n / mean "
          "close $ | near-miss (only this fails): n / mean close $ |")
        A("|---|---|---|---|")
        for k, name in enumerate(TERMS):
            cells = {}
            for x in r["terms"]:
                if x[1] == "ALL" and x[3] == name:
                    cells[x[2]] = x
            def cell(sc):
                x = cells.get(sc)
                return "." if x is None else "%d / %s" % (x[4], _fmt(x[6]))
            A("| %s | %s | %s | %s |"
              % (name, cell("TERM_ALONE"), cell("DETECTOR_MINUS_TERM"),
                 cell("NEAR_MISS_ONLY_THIS_TERM_FAILS")))
        A("")

    A("## Support-set check (the 3 PATTERN_LEDGER cases)")
    A("")
    A("| case | reading A fires | reading B fires | cert close $ |")
    A("|---|---|---|---|")
    for cid in ("HG-20210701-052246-S", "HG-20210701-055858-S",
                "HG-20210929-052330-S"):
        a, d8, sec, side = MC.parse_cid(cid)
        m = ((D["asset"] == a) & (D["d8"] == d8) & (D["dec_sec"] == sec)
             & (D["side"] == side))
        if not m.any():
            A("| %s | . | . | . |" % cid)
            continue
        t = int(np.nonzero(m)[0][0])
        A("| %s | %s | %s | %s |"
          % (cid, bool(np.all(unbits(D["termsA"])[t])),
             bool(np.all(unbits(D["termsB"])[t])),
             _fmt(float(D["cert_close"][t]))))
    A("")
    A("## Provenance")
    A("")
    A("* engine: `engine/port_m2/p001_census.py` + `engine/port_m2/pattern_lib.py`")
    A("* red-first mutants: `engine/port_m2/test_pattern.py` "
      "(artifacts/cache/port/m2/tests/pattern_red_ledger.tsv)")
    A("* runtime %.1fs; pins %s" % (elapsed, "HELD" if not pins else
                                    "MOVED: " + "; ".join(pins)))
    A("* params_hash `%s`" % MC.params_hash(PARAMS))
    A("")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ main ----
def build(workers=4, limit_sessions=None):
    t0 = time.time()
    MC.verify_spec(force=True)
    D = scan(workers=workers, limit_sessions=limit_sessions)
    res = {}
    fires, census, terms, destr, robust = [], [], [], [], []
    for reading, key in (("A", "termsA"), ("B", "termsB")):
        T = unbits(D[key])
        fire = np.all(T, axis=1)
        r = {"census": census_rows(D, fire, reading),
             "terms": term_rows(D, T, reading),
             "destruction": destruction_rows(D, T, reading),
             "robust": robust_rows(D, fire, reading),
             "fires": fire_rows(D, fire, reading),
             "n_fires": int(fire.sum())}
        res[reading] = r
        census += r["census"]
        terms += r["terms"]
        destr += r["destruction"]
        robust += r["robust"]
        fires += r["fires"]
        MC.hb("p001 reading %s: %d fires" % (reading, r["n_fires"]))
    phash = MC.params_hash(PARAMS)
    extra = ["%s %s — five strictly-causal terms; readings A/B differ ONLY in "
             "the T4 age field (see the report)" % (PATTERN_ID, PATTERN_NAME),
             "BOTH CC-M1-8 certificate readings are reported on every row"]
    MC.write_tsv(os.path.join(OUT_DIR, "P001_FIRES.tsv"), SECTION, phash,
                 list(FIRE_COLUMNS), fires, extra=extra)
    MC.write_tsv(os.path.join(OUT_DIR, "P001_CENSUS.tsv"), SECTION, phash,
                 list(CENSUS_COLUMNS), census, extra=extra)
    MC.write_tsv(os.path.join(OUT_DIR, "P001_TERMS.tsv"), SECTION, phash,
                 list(TERM_COLUMNS), terms, extra=extra)
    MC.write_tsv(os.path.join(OUT_DIR, "P001_DESTRUCTION.tsv"), SECTION, phash,
                 list(DESTRUCTION_COLUMNS), destr, extra=extra)
    MC.write_tsv(os.path.join(OUT_DIR, "P001_ROBUST.tsv"), SECTION, phash,
                 list(ROBUST_COLUMNS), robust, extra=extra)
    pins = MC.pins_moved()
    el = time.time() - t0
    MC.write_text(os.path.join(OUT_DIR, "P001_CENSUS_REPORT.md"),
                  report(D, res, el, pins))
    MC.write_json(os.path.join(OUT_DIR, "p001_census.receipt.json"),
                  {"env": MC.env_receipt(PARAMS),
                   "n_candidates": int(D["dec_sec"].size),
                   "n_sessions": int(D["n_sessions_total"]),
                   "n_fires": {k: res[k]["n_fires"] for k in res},
                   "elapsed_sec": el, "pins_moved": pins,
                   "out_dir": OUT_DIR})
    MC.hb("p001 census: A=%d B=%d fires, %.1fs"
          % (res["A"]["n_fires"], res["B"]["n_fires"], el))
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--limit-sessions", type=int, default=None)
    a = p.parse_args()
    if a.workers > 4:
        raise SystemExit("workers capped at 4 (a reader lane is live)")
    build(workers=a.workers, limit_sessions=a.limit_sessions)
    return 0


if __name__ == "__main__":
    sys.exit(main())
