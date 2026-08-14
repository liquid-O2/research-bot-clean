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
import assemble as A                      # noqa: E402
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

# ---------------------------------------------------------------- P016 ------
# P016 NY_SHORT_ROLLOVER_CONCORDANT — "P001's successor" (PATTERN_LEDGER at
# HEAD, opened by the E1-STUDY-D1 round; orchestrator scope addition).  The
# ledger's `sheet_fields` names five clauses and one EXCLUSION:
#   X1  range EXTENSION needed for the $1,000 bar <= ~$450   (+ the phase is
#       >= 300s old: e1d1_policy T3's own guard, kept because the arithmetic
#       degenerates at a phase open)
#   X2  runway to phase close >= 20,000s with phase_close == session_close
#   X3  S8 60s n >= 5 and vol >= 10                         (a live book)
#   X4  sign(S8 phase sflow) == side and |sflow|/phase vol >= 0.05, on a phase
#       that has traded >= 200                              (flow concordance)
#   X5  S9 rv1800/rv60 < 8                                  (vol not dead)
#   --  P001's slope/accel term is DROPPED, by name ("NOT S5 mid_slope/accel")
# The thresholds inside X1/X4 are taken VERBATIM from the committed executable
# form (engine/port_m2/e1d1_policy.terms T3/T5), not re-invented here.
# The ledger scopes P016 to "all classes" and its NAME to NY/SHORT, so side and
# phase are NOT terms — they are reported as strata, which is what breaks the
# co-occurrence apart rather than baking it in.
EXT_MAX_USD = 450.0
PHASE_MIN_AGE_SEC = 300
RUNWAY_MIN_SEC_P016 = 20000
F60_MIN_N = 5
F60_MIN_VOL = 10
PHASE_MIN_VOL = 200
SFLOW_MIN_FRAC = 0.05
RV_RATIO_MAX = 8.0
TERMS_P016 = ("X1_extension", "X2_runway", "X3_book", "X4_flow_concord",
              "X5_vol_alive")

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
                   "RandomState(%d + term index); the other four terms "
                   "untouched. The destroyed quantity is the EDGE (mean cert "
                   "of the firing set minus mean cert of the non-firing rest, "
                   "both readings), not the level — a level comparison is "
                   "dominated by the population's negative mean"
                   % (DESTRUCTION_REPS, DESTRUCTION_SEED),
    "arm_P016": "PATTERN_LEDGER P016 NY_SHORT_ROLLOVER_CONCORDANT: "
                "ext_needed <= $%.0f and phase_age >= %ds; runway >= %ds with "
                "phase_close == sess_close; f60_n >= %d and f60_vol >= %d; "
                "sign(fph_sflow) == side, fph_vol >= %d, |sflow|/vol >= %.2f; "
                "rv1800/rv60 < %.1f. P001's slope/accel term is DROPPED by "
                "name. Sub-clause thresholds taken verbatim from "
                "engine/port_m2/e1d1_policy.terms (T3/T5)."
                % (EXT_MAX_USD, PHASE_MIN_AGE_SEC, RUNWAY_MIN_SEC_P016,
                   F60_MIN_N, F60_MIN_VOL, PHASE_MIN_VOL, SFLOW_MIN_FRAC,
                   RV_RATIO_MAX),
    "refused_fvol_census": "CC-M2-8.4 — per (asset, era) count/fraction of "
                           "fvol rows with no move_q* quantiles and of "
                           "candidates whose S9 ladder / S3 COVERAGE is "
                           "therefore REFUSED",
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


def terms_p016(f):
    """The five P016 clauses for every candidate of one session frame."""
    side = f["side"].astype(np.float64)
    ext = f["ext_needed_usd"]
    x1 = (np.isfinite(ext) & (ext <= EXT_MAX_USD)
          & (f["phase_age_sec"] >= PHASE_MIN_AGE_SEC))
    x2 = (f["runway_phase_sec"] >= RUNWAY_MIN_SEC_P016) & f["session_close_exit"]
    x3 = (f["f60_n"] >= F60_MIN_N) & (f["f60_vol"] >= F60_MIN_VOL)
    vol = f["fph_vol"].astype(np.float64)
    sfl = f["fph_sflow"].astype(np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        frac = np.where(vol > 0, np.abs(sfl) / vol, 0.0)
    x4 = (vol >= PHASE_MIN_VOL) & (sfl * side > 0) & (frac >= SFLOW_MIN_FRAC)
    rv = f["rv_ratio"]
    x5 = np.isfinite(rv) & (rv < RV_RATIO_MAX)
    return np.column_stack([x1, x2, x3, x4, x5])


# The censused arms.  A/B differ ONLY in P001's T4 field (defect D-P001-1);
# P016 is the successor pattern the E1-STUDY-D1 round mutated P001 into.
ARMS = (("A", "P001 (PATTERN_LEDGER literal: T4 = phase-extreme age)", TERMS),
        ("B", "P001 (post-mortem literal: T4 = causal ZigZag pivot age)", TERMS),
        ("P016", "P016 NY_SHORT_ROLLOVER_CONCORDANT (P001's successor)",
         TERMS_P016))


def arm_terms(f, arm):
    if arm == "P016":
        return terms_p016(f)
    return terms_of(f, arm)


# --------------------------------------------------------------- the pass ---
_COLS = ("asset", "d8", "dec_sec", "side", "phase_dec", "klass",
         "cert_close", "cert_peak", "walled", "winner",
         "termsA", "termsB", "coverage_phase", "ladder_band",
         "runway_phase_sec", "extreme_age_sec", "pivot_age_sec",
         "slope_1m_usd", "accel_usd")


def _pack(f):
    def bits(t):
        out = np.zeros(t.shape[0], dtype=np.uint8)
        for k in range(t.shape[1]):
            out |= (t[:, k].astype(np.uint8) << k)
        return out
    out = {
        "asset": f["asset"], "d8": f["d8"],
        "dec_sec": f["dec_sec"].astype(np.int32),
        "side": f["side"].astype(np.int8),
        "phase_dec": f["phase_dec"].astype(np.int8),
        "klass": f["klass"],
        "cert_close": f["cert_close_usd"].astype(np.float64),
        "cert_peak": f["cert_peak_usd"].astype(np.float64),
        "walled": f["walled"], "winner": f["winner"],
        "coverage_phase": f["coverage_phase"].astype(np.float32),
        "ladder_band": f["ladder_band"].astype(np.int8),
        "runway_phase_sec": f["runway_phase_sec"].astype(np.int32),
        "extreme_age_sec": f["extreme_age_sec"].astype(np.int32),
        "pivot_age_sec": f["pivot_age_sec"].astype(np.int32),
        "slope_1m_usd": f["slope_1m_usd"].astype(np.float32),
        "accel_usd": f["accel_usd"].astype(np.float32),
        "ext_needed_usd": f["ext_needed_usd"].astype(np.float32),
        "fph_sflow": f["fph_sflow"].astype(np.int32),
        "fph_vol": f["fph_vol"].astype(np.int32),
        "f60_n": f["f60_n"].astype(np.int32),
        "rv_ratio": f["rv_ratio"].astype(np.float32),
    }
    for arm, _label, _names in ARMS:
        out["terms_" + arm] = bits(arm_terms(f, arm))
    return out


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
    for k in (("dec_sec", "side", "phase_dec", "cert_close", "cert_peak",
               "walled", "winner", "coverage_phase", "ladder_band",
               "runway_phase_sec", "extreme_age_sec", "pivot_age_sec",
               "slope_1m_usd", "accel_usd", "klass", "ext_needed_usd",
               "fph_sflow", "fph_vol", "f60_n", "rv_ratio")
              + tuple("terms_" + a for a, _l, _n in ARMS)):
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


def unbits(b, n_terms=len(TERMS)):
    return np.column_stack([((b >> k) & 1).astype(bool)
                            for k in range(n_terms)])


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


def term_rows(D, T, reading, names=TERMS):
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
        for k, name in enumerate(names):
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
                       "edge_close_mean", "edge_close_sd", "cond_close_mean",
                       "mean_peak_mean", "edge_peak_mean", "intact_n_fires",
                       "intact_mean_close", "intact_edge_close",
                       "intact_cond_close", "intact_edge_peak",
                       "edge_retention_close", "edge_retention_peak",
                       "verdict")


def destruction_rows(D, T, reading, names=TERMS):
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

    def _edge(vals, m):
        """Mean certificate of the firing set MINUS the non-firing baseline.

        The raw mean of a firing set is not "the value": most candidates lose,
        so a level comparison is dominated by the population's negative mean.
        The pattern's claim is an EDGE over the candidates it does not fire on,
        so that difference is what destruction has to erase.
        """
        if not m.any() or m.all():
            return float("nan")
        return float(vals[m].mean() - vals[~m].mean())

    for k, name in enumerate(names):
        rs = np.random.RandomState(DESTRUCTION_SEED + k)
        others = np.all(np.delete(Tf, k, axis=1), axis=1)
        acc = {aname: {"n": [], "mc": [], "ed": [], "cd": [], "mp": [],
                       "edp": []} for aname, _ in assets}
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
                sub_c, sub_p = cc[asel], cp[asel]
                sm = fired[asel]
                if m.any():
                    v = cc[m]
                    a["mc"].append(float(v.mean()))
                    a["mp"].append(float(cp[m].mean()))
                    pv = v[v > 0]
                    a["cd"].append(float(pv.mean()) if pv.size else np.nan)
                    a["ed"].append(_edge(sub_c, sm))
                    a["edp"].append(_edge(sub_p, sm))
                else:
                    for key in ("mc", "mp", "cd", "ed", "edp"):
                        a[key].append(np.nan)

        def _m(v):
            return (float(np.nanmean(v)) if np.any(np.isfinite(v))
                    else float("nan"))

        for aname, asel in assets:
            im = intact & asel
            i_st = _stats(cc[im], cp[im], wn[im], nsess) if im.any() else None
            a = acc[aname]
            i_mc = i_st["mean_close"] if i_st else float("nan")
            i_cd = i_st["cond_close"] if i_st else float("nan")
            i_ed = _edge(cc[asel], intact[asel])
            i_edp = _edge(cp[asel], intact[asel])
            ret = (_m(a["ed"]) / i_ed
                   if np.isfinite(i_ed) and i_ed != 0 else float("nan"))
            retp = (_m(a["edp"]) / i_edp
                    if np.isfinite(i_edp) and i_edp != 0 else float("nan"))
            if not (i_st and i_st["n_candidates"]):
                verdict = "UNDECIDED_no_intact_fires"
            elif not np.isfinite(i_ed) or i_ed <= 0:
                # nothing to destroy: the intact detector has no positive edge
                # over its own non-firing baseline, so the destruction test is
                # VOID for this term (the pattern failed one step earlier).
                verdict = "VOID_no_intact_edge"
            elif not np.isfinite(ret):
                verdict = "UNDECIDED_no_intact_fires"
            elif ret >= 0.80:
                verdict = "TERM_NOT_LOAD_BEARING"
            elif ret <= 0.50:
                verdict = "TERM_LOAD_BEARING"
            else:
                verdict = "PARTIAL"
            rows.append([reading, aname, name, float(np.mean(a["n"])),
                         float(np.std(a["n"])), _m(a["mc"]),
                         float(np.nanstd(a["mc"])), _m(a["ed"]),
                         float(np.nanstd(a["ed"])), _m(a["cd"]),
                         _m(a["mp"]), _m(a["edp"]),
                         int(i_st["n_candidates"]) if i_st else 0,
                         i_mc, i_ed, i_cd, i_edp, ret, retp, verdict])
    return rows


ROBUST_COLUMNS = ("reading", "asset", "era", "metric", "n", "n_clusters",
                  "n_fires", "beta_usd", "se_naive", "se_cr0", "se_cr1",
                  "z_cr1", "p_cr1", "icc_rho", "deff", "n_eff", "verdict",
                  "holm_rank", "holm_threshold", "holm_verdict")


def _p_two_sided(z):
    import math
    if not np.isfinite(z):
        return float("nan")
    return math.erfc(abs(z) / math.sqrt(2.0))


def _holm(rows, alpha=0.05):
    """Holm-Bonferroni over the family of tests inside ONE reading.

    16 GEE tests are run per reading (4 asset groups x 2 eras x 2 certificate
    readings).  Reporting each at alpha=0.05 would manufacture roughly one
    'significant' row by construction, so the family is corrected — the same
    Holm discipline the M1 atlas screen uses.
    """
    idx = [i for i, r in enumerate(rows) if np.isfinite(r[12])]
    order = sorted(idx, key=lambda i: rows[i][12])
    m = len(order)
    still = True
    for rank, i in enumerate(order, 1):
        thr = alpha / (m - rank + 1)
        ok = still and rows[i][12] <= thr
        still = still and ok
        rows[i] += [rank, thr,
                    "HOLM_SIGNIFICANT" if ok else "HOLM_NOT_SIGNIFICANT"]
    for i, r in enumerate(rows):
        if len(r) == len(ROBUST_COLUMNS) - 3:
            rows[i] += [0, float("nan"), "NO_TEST"]
    return rows


def robust_rows(D, fire, reading, holm=True):
    """CC-M1-12.4: GEE (identity link) of the certificate on the fire flag,
    Liang-Zeger sandwich clustered on SESSION, + Kish DEFF / n_eff.

    `holm=False` returns the rows WITHOUT the three Holm columns, so a caller
    running several patterns in one batch can correct over the whole batch
    family instead of once per pattern (CC-M2-10.2's census batch 2 does this;
    P001's own call keeps the default and is unchanged).
    """
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
                                 int(len(set(cl.tolist()))), nf]
                                + [float("nan")] * 6
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
    return _holm(rows) if holm else rows


FIRE_COLUMNS = ("arm", "cid", "asset", "d8", "year", "era", "phase",
                "side", "class", "coverage_phase", "ladder_band",
                "runway_phase_sec", "extreme_age_sec", "pivot_age_sec",
                "slope_1m_usd", "accel_usd", "ext_needed_usd", "fph_sflow",
                "fph_vol", "f60_n", "rv_ratio", "cert_close_usd",
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
                     float(D["ext_needed_usd"][t]), int(D["fph_sflow"][t]),
                     int(D["fph_vol"][t]), int(D["f60_n"][t]),
                     float(D["rv_ratio"][t]),
                     float(D["cert_close"][t]), float(D["cert_peak"][t]),
                     bool(D["walled"][t]), bool(D["winner"][t])])
    rows.sort(key=lambda r: (r[0], r[2], r[3], r[1]))
    return rows


REFUSED_COLUMNS = ("asset", "era", "n_fvol_rows", "n_rows_no_quantiles",
                   "frac_rows_no_quantiles", "n_rows_atr_fallback",
                   "frac_rows_atr_fallback", "n_sessions",
                   "n_sessions_any_segment_refused",
                   "frac_sessions_any_refused", "n_candidates",
                   "n_candidates_ladder_refused", "frac_ladder_refused",
                   "n_candidates_coverage_refused", "frac_coverage_refused")

_QS = ("q10", "q25", "q50", "q75", "q90")


def refused_rows(D):
    """CC-M2-8.4 — how big is the ladder-refusal hole, per (asset, era)?

    Two grains, because they answer different questions:
      * FVOL ROW grain (m1/fvol/fvol_forecasts.tsv): how often the forecaster
        published no move_q* quantiles for a (session, segment), and how often
        it fell back to raw ATR14 at all (the fallback can still carry
        quantiles — 868 of HG's 988 ATR14_RAW_FILL rows do);
      * CANDIDATE grain (the frame): how many DECISIONS therefore carry a
        REFUSED S9 ladder / S3 COVERAGE, which is what a ladder-dependent
        pattern actually loses.  SI 2021-07-01 was 391/391 refused, which is
        why this census was ordered.
    """
    rows = []
    fv = A.fvol_rows()
    # the row grain must cover EXACTLY the sessions the candidate grain covers,
    # or the two halves of the table describe different populations.
    sess_of = {}
    for a, d in zip(D["asset"].tolist(), D["d8"].tolist()):
        sess_of.setdefault(a, set()).add(int(d))
    era_of = {}

    def _eras(d8):
        if d8 not in era_of:
            y = d8 // 10000
            out = ["ALL"]
            out.append("FIT" if y in FIT_YEARS else
                       ("GATE_%d" % GATE_YEAR if y == GATE_YEAR else "OTHER"))
            out.append(str(y))
            out.append(MC.era_of(d8))
            era_of[d8] = out
        return era_of[d8]

    # --- fvol row grain
    acc = {}
    for (asset, iso, _seg), row in fv.items():
        d8 = int(iso[0:4] + iso[5:7] + iso[8:10])
        if d8 not in sess_of.get(asset, ()):      # roster sessions only
            continue
        no_q = not all(np.isfinite(A._f(row.get("move_%s_usd_per_sigma" % q)))
                       for q in _QS)
        fallback = str(row.get("sigma_source", "")) != "FVOL"
        for era in _eras(d8) + ["ALL"]:
            for an in (asset, "ALL"):
                e = acc.setdefault((an, era), [0, 0, 0, set(), set()])
                e[0] += 1
                e[1] += int(no_q)
                e[2] += int(fallback)
                e[3].add((asset, d8))
                if no_q:
                    e[4].add((asset, d8))
    # --- candidate grain
    cand = {}
    for an in list(MC.ASSET_ORDER) + ["ALL"]:
        asel = (np.ones(D["dec_sec"].size, dtype=bool) if an == "ALL"
                else (D["asset"] == an))
        for era, esel in (("FIT", np.isin(D["year"], FIT_YEARS)),
                          ("GATE_%d" % GATE_YEAR, D["year"] == GATE_YEAR),
                          ("ALL", np.ones(D["dec_sec"].size, dtype=bool))) + \
                         tuple((str(y), D["year"] == y) for y in
                               FIT_YEARS + (GATE_YEAR,)):
            m = asel & esel
            if not m.any():
                continue
            cand[(an, era)] = (int(m.sum()),
                               int((D["ladder_band"][m] < 0).sum()),
                               int((~np.isfinite(D["coverage_phase"][m])).sum()))
    for key in sorted(set(list(acc) + list(cand))):
        an, era = key
        a_e = acc.get(key, [0, 0, 0, set(), set()])
        c_e = cand.get(key, (0, 0, 0))
        n_rows = a_e[0]
        rows.append([an, era, n_rows, a_e[1],
                     (float(a_e[1]) / n_rows) if n_rows else float("nan"),
                     a_e[2],
                     (float(a_e[2]) / n_rows) if n_rows else float("nan"),
                     len(a_e[3]), len(a_e[4]),
                     (float(len(a_e[4])) / len(a_e[3])) if a_e[3]
                     else float("nan"),
                     c_e[0], c_e[1],
                     (float(c_e[1]) / c_e[0]) if c_e[0] else float("nan"),
                     c_e[2],
                     (float(c_e[2]) / c_e[0]) if c_e[0] else float("nan")])
    return rows


# ---------------------------------------------------------------- report ----
def _fmt(v, dec=2):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "."
    if isinstance(v, float):
        return ("%%.%df" % dec) % v
    return str(v)


def report(D, res, refused, elapsed, pins):
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

    A("## HEADLINE")
    A("")
    for reading, _label, _names in ARMS:
        r = res[reading]
        cen = {(x[1], x[2], x[3], x[4], x[5]): x for x in r["census"]}
        fF = cen.get(("ALL", "FIT", "ALL", "ALL", "FIRE"))
        fN = cen.get(("ALL", "FIT", "ALL", "ALL", "NOFIRE"))
        rb = [x for x in r["robust"]
              if x[1] == "ALL" and x[2] == "FIT" and x[3] == "cert_close"]
        rp = [x for x in r["robust"]
              if x[1] == "ALL" and x[2] == "FIT" and x[3] == "cert_peak"]
        if fF is None or fN is None or fF[7] == 0:
            A("* **Reading %s** — the detector never fires on FIT." % reading)
            continue
        A("* **Reading %s** — fires %s/session (%d fires, %d sessions). "
          "ADOPTION METRIC (walled phase-close): mean $%s for the firing set "
          "vs $%s for everything it does not fire on, a session-clustered "
          "difference of $%s (CR1 se $%s, p=%s) -> **%s**. "
          "PEAK-EXIT companion: $%s (p=%s). "
          "CONDITIONAL value (mean over the winners it does produce): $%s vs "
          "$%s = %sx. D-021 winner rate %s%% vs %s%% = %sx."
          % (reading, _fmt(fF[8], 2), fF[7], fF[6],
             _fmt(fF[9]), _fmt(fN[9]),
             _fmt(rb[0][7]) if rb else ".", _fmt(rb[0][10]) if rb else ".",
             _fmt(rb[0][12], 4) if rb else ".",
             ("NO MEAN-VALUE EDGE" if (rb and rb[0][7] <= 0)
              else "positive but see the p-value"),
             _fmt(rp[0][7]) if rp else ".",
             _fmt(rp[0][12], 4) if rp else ".",
             _fmt(fF[10]), _fmt(fN[10]),
             _fmt(fF[10] / fN[10], 2) if fN[10] else ".",
             _fmt(100.0 * fF[16], 2), _fmt(100.0 * fN[16], 2),
             _fmt(fF[16] / fN[16], 2) if fN[16] else "."))
    A("")
    A("DEFECT D-P001-1 (the T4 ambiguity, found by this census). "
      "PATTERN_LEDGER names the age term as `age of S3.phase H (SHORT) or L "
      "(LONG) <= 200s`, but that field does NOT reproduce the post-mortem's "
      "own table: on HG-20210929-052330-S the phase H is 1,236s old at the "
      "decision second while the post-mortem quotes 93s. 93s is the age of "
      "the most recent CAUSAL ZigZag HIGH pivot (14:30:37, confirmed "
      "14:31:48, decision 14:32:10). The two readings agree on the other two "
      "support cases. Both are censused here: READING A is the ledger "
      "literal, READING B the post-mortem literal. The orchestrator rules "
      "which one P001 means; the ledger's `sheet_fields` text needs the fix "
      "either way.")
    A("")
    A("MULTIPLICITY: 16 GEE tests are run per reading (4 asset groups x 2 "
      "eras x 2 certificate readings). Every robust table therefore carries "
      "Holm-Bonferroni columns; an uncorrected p<0.05 row that fails Holm is "
      "noise, and the tables say which is which.")
    A("")

    for reading, label, _names in ARMS:
        r = res[reading]
        cen = {(x[1], x[2], x[3], x[4], x[5]): x for x in r["census"]}
        fitF = cen.get(("ALL", "FIT", "ALL", "ALL", "FIRE"))
        fitN = cen.get(("ALL", "FIT", "ALL", "ALL", "NOFIRE"))
        A("## ARM %s — %s" % (reading, label))
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
        A("Co-occurrence break-out (FIT, FIRE group) — the E1 note flagged "
          "P001's support set as all-HG / all-NY / all-SHORT, and P016's name "
          "carries NY/SHORT too; neither is a term here, so these strata are "
          "what breaks the co-occurrence apart:")
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
          "its session, %d replicates). EDGE = mean close of the firing set "
          "minus mean close of the non-firing rest; `retention` = destroyed "
          "edge / intact edge. High retention means the term was not carrying "
          "the value. Intact edge = $%s (close), $%s (peak)."
          % (DESTRUCTION_REPS,
             _fmt(r["destruction"][0][14]) if r["destruction"] else ".",
             _fmt(r["destruction"][0][16]) if r["destruction"] else "."))
        A("")
        A("| neutralised term | fires (mean) | mean close $ | edge close $ | "
          "retention close | retention peak | verdict |")
        A("|---|---|---|---|---|---|---|")
        for x in r["destruction"]:
            if x[1] != "ALL":
                continue
            A("| %s | %s | %s | %s | %s | %s | %s |"
              % (x[2], _fmt(x[3], 1), _fmt(x[5]), _fmt(x[7]), _fmt(x[17], 3),
                 _fmt(x[18], 3), x[19]))
        A("")
        A("Cluster-robust inference (CC-M1-12.4; GEE identity link, "
          "Liang-Zeger sandwich clustered on SESSION, CR1 scaling):")
        A("")
        A("| asset | era | metric | beta $ | se naive | se CR1 | z | p | "
          "DEFF | n_eff | raw verdict | Holm |")
        A("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for x in r["robust"]:
            A("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |"
              % (x[1], x[2], x[3], _fmt(x[7]), _fmt(x[8]), _fmt(x[10]),
                 _fmt(x[11], 2), _fmt(x[12], 5), _fmt(x[14], 2),
                 _fmt(x[15], 1), x[16], x[19]))
        A("")
        A("Term marginals (FIT, ALL assets):")
        A("")
        A("| term | alone: n / mean close $ | detector without it: n / mean "
          "close $ | near-miss (only this fails): n / mean close $ |")
        A("|---|---|---|---|")
        for k, name in enumerate(r["names"]):
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

    A("## REFUSED-FVOL CENSUS (CC-M2-8.4) — the size of the ladder hole")
    A("")
    A("A REFUSED S9 ladder is not a missing number, it is a term that cannot "
      "fire: any pattern with a ladder or COVERAGE clause is structurally "
      "blind on those candidates. Row grain = fvol forecast rows "
      "(session x segment); candidate grain = decisions. Note the two are "
      "different questions — the ATR14 FALLBACK is common (a fifth of rows) "
      "and mostly still carries quantiles; only the no-move_q* rows refuse.")
    A("")
    A("| asset | era | fvol rows | no move_q* | % | ATR fallback % | sessions "
      "with a refused segment % | candidates | ladder REFUSED % | COVERAGE "
      "REFUSED % |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    keep = ("ALL", "FIT", "GATE_%d" % GATE_YEAR) + tuple(
        str(y) for y in FIT_YEARS + (GATE_YEAR,))
    for x in refused:
        if x[1] not in keep:
            continue
        A("| %s | %s | %d | %d | %s | %s | %s | %d | %s | %s |"
          % (x[0], x[1], x[2], x[3], _fmt(100.0 * x[4], 2),
             _fmt(100.0 * x[6], 2), _fmt(100.0 * x[9], 2), x[10],
             _fmt(100.0 * x[12], 2), _fmt(100.0 * x[14], 2)))
    A("")
    A("## Support-set check (the 3 P001 PATTERN_LEDGER cases)")
    A("")
    A("| case | %s | cert close $ |"
      % " | ".join("arm %s" % a for a, _l, _n in ARMS))
    A("|---|" + "---|" * (len(ARMS) + 1))
    for cid in ("HG-20210701-052246-S", "HG-20210701-055858-S",
                "HG-20210929-052330-S"):
        a, d8, sec, side = MC.parse_cid(cid)
        m = ((D["asset"] == a) & (D["d8"] == d8) & (D["dec_sec"] == sec)
             & (D["side"] == side))
        if not m.any():
            A("| %s |%s . |" % (cid, " . |" * len(ARMS)))
            continue
        t = int(np.nonzero(m)[0][0])
        cells = [str(bool(np.all(unbits(D["terms_" + arm], len(nm))[t])))
                 for arm, _l, nm in ARMS]
        A("| %s | %s | %s |" % (cid, " | ".join(cells),
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
    for arm, _label, names in ARMS:
        T = unbits(D["terms_" + arm], len(names))
        fire = np.all(T, axis=1)
        r = {"census": census_rows(D, fire, arm),
             "terms": term_rows(D, T, arm, names),
             "destruction": destruction_rows(D, T, arm, names),
             "robust": robust_rows(D, fire, arm),
             "fires": fire_rows(D, fire, arm),
             "n_fires": int(fire.sum()), "names": names}
        res[arm] = r
        census += r["census"]
        terms += r["terms"]
        destr += r["destruction"]
        robust += r["robust"]
        fires += r["fires"]
        MC.hb("p001 arm %s: %d fires" % (arm, r["n_fires"]))
    refused = refused_rows(D)
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
    MC.write_tsv(os.path.join(OUT_DIR, "REFUSED_FVOL_CENSUS.tsv"), SECTION,
                 phash, list(REFUSED_COLUMNS), refused,
                 extra=["CC-M2-8.4 — the size of the fvol ladder-refusal hole",
                        "row grain = m1/fvol/fvol_forecasts.tsv (session x "
                        "segment); candidate grain = the decision views"])
    pins = MC.pins_moved()
    el = time.time() - t0
    MC.write_text(os.path.join(OUT_DIR, "P001_CENSUS_REPORT.md"),
                  report(D, res, refused, el, pins))
    MC.write_json(os.path.join(OUT_DIR, "p001_census.receipt.json"),
                  {"env": MC.env_receipt(PARAMS),
                   "n_candidates": int(D["dec_sec"].size),
                   "n_sessions": int(D["n_sessions_total"]),
                   "n_fires": {k: res[k]["n_fires"] for k in res},
                   "arms": [a for a, _l, _n in ARMS],
                   "elapsed_sec": el, "pins_moved": pins,
                   "out_dir": OUT_DIR})
    MC.hb("p001 census: %s, %.1fs"
          % (", ".join("%s=%d" % (a, res[a]["n_fires"])
                       for a, _l, _n in ARMS), el))
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
