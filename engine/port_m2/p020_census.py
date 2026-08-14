#!/usr/bin/python3
"""PORT M2 — CENSUS BATCH 2: P020 / P021 / P022 name->count censuses.

CC-M2-10.2 (BINDING): "CENSUS BATCH 2 ORDERED: P020 (NY-phase winner
concentration), P021 (EXPANSION regime flag ... the round's highest-value
candidate), P022 (fossil-flow ...).  Same discipline as P001's census."

The discipline, restated from p001_census.py so this file can be read alone:
every detector is STRICTLY CAUSAL and built only from committed pattern_lib
frame fields; the population is every candidate of the frozen v3 roster on
every FIT session of all three assets, with 2025 as an EVAL-ONLY GATE echo;
BOTH CC-M1-8 certificate readings are reported everywhere; per-year stability,
per-term marginals and MECHANISM DESTRUCTION (each term shuffled within its own
session) are mandatory; inference is GEE with the Liang-Zeger sandwich
clustered on SESSION (CR1) plus Kish DEFF/n_eff; and the p-values are corrected
Holm-Bonferroni over THE WHOLE BATCH, not once per pattern.

THE THREE DETECTORS (PATTERN_LEDGER.tsv `sheet_fields`, verbatim)

P020 NY_PHASE_CONCENTRATION — "D-021 winners concentrate in the NY phase."
  T1  phase_dec == NY.
  This one is as much a BASE-RATE CENSUS as a pattern: the ledger's own
  recommendation is "winner rate by (phase_dec, asset) over the whole era, and
  check it is not an artefact of where candidates are generated".  So the
  headline object is the CONCENTRATION RATIO
      (winners in the phase / all winners) / (candidates in the phase / all
       candidates)
  which is exactly 1.00 when a phase holds winners in proportion to the
  candidates generated inside it — the artefact hypothesis, quantified.

P021 REGIME_CONDITIONAL_CAPACITY — the EXPANSION regime flag.
  T1  S2 day_type_so_far == EXPANDED   (session range so far >= range_hat)
  T2  S9 surprise >= 0.99              (phase realized range / range_hat)
  Censused BOTH ways:
   (a) as a STANDALONE CONDITIONER (does the flagged pool differ at all?), and
   (b) as an INTERACTION with trade DIRECTION — the load-bearing test, and the
       reason CC-M2-10.2 calls it the round's highest-value candidate.  The
       claim under test (E1_POSTMORTEMS §3): on EXPANSION-flagged candidates,
       BREAKOUT-direction entries outperform REVERSION-direction ones; on
       non-flagged candidates the ordering reverses.  Two readings of
       "direction", because the postmortem states it twice:
         READING A (literal, "side == range-extension side"): the phase is
           extending on the side of its MORE RECENT extreme, so
           ext_side = +1 when phase_hi is younger than phase_lo, -1 otherwise;
           BREAKOUT = side == ext_side.  Candidates whose two extremes share a
           second carry no extension side and are dropped from the interaction
           (reported as n_no_direction).
         READING B (the indicted arithmetic itself): P017's ext_needed — the
           dollars of BRAND-NEW range the $1,000 bar still needs.  BREAKOUT =
           ext_needed > $450 (P017's own refusal threshold), REVERSION =
           ext_needed <= $450.  Reading B is what the reader's T3 actually
           computed, so it is the reading that says whether T3 inverts.
  The interaction is tested as a DIFFERENCE IN DIFFERENCES with the same
  cluster-robust machinery as everything else (see `did_rows`).

P022 FLOW_HORIZON_DISAGREEMENT — the fossil-flow VETO.
  T1  sign(S8 phase sflow) disagrees with sign(S8 30m sflow), both non-zero
  T2  sign(S8 phase sflow) disagrees with sign(S8 5m sflow),  both non-zero
  T3  S12 last_scheduled release age < 90 min (5,400s)
  Censused as a VETO: the value of the FLAGGED pool against the unflagged rest,
  per side.  A veto is worth having when the pool it removes is worse than the
  pool it leaves; the per-side split is what says whether the flag is a veto or
  a COMPASS — the E1D2 diagnosis was that the shorter windows are the live
  market, so among flagged candidates the ones pointed WITH the short windows
  should beat the ones pointed with the phase fossil.  That table is
  P022_DIRECTION.tsv, and it also carries the D10 EVENT-ANCHORED window
  (flow since the release rather than since the phase open) as a third reading.

GRADING (CC-M2-9.1 vocabulary — the distinction is reported explicitly)
  ENTRY RULE          positive beta on the ADOPTION metric (walled phase-close)
                      that survives Holm over the batch.
  VETO RULE           negative beta on the adoption metric, Holm-significant:
                      the flagged pool is worth REFUSING.
  WINNER CONCENTRATOR no adoption-metric edge, but the firing set holds D-021
                      winners / conditional value at >= 1.25x its own
                      non-firing baseline.  DISPOSITION per CC-M2-9.1: the
                      FEATURE CANDIDATE SET, never the entry/veto rule set.
  NULL                neither.

OUTPUT (D-018: bulk under artifacts/cache/)
  artifacts/cache/port/m2/pattern_census/P020_P022_CENSUS_REPORT.md
  artifacts/cache/port/m2/pattern_census/BATCH2_{CENSUS,TERMS,DESTRUCTION,
      ROBUST}.tsv, P020_CONCENTRATION.tsv, P021_INTERACTION.tsv,
      P022_DIRECTION.tsv, p020_census.receipt.json

Run:  lab/run.sh port-m2-p020 -- /usr/bin/python3 engine/port_m2/p020_census.py
"""
import argparse
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
import p001_census as P1                  # noqa: E402  (the census machinery)

SECTION = "DISCRETIONARY_METHOD §4.2 name->count census — batch 2 (CC-M2-10.2)"
OUT_DIR = MC.out_path("pattern_census", "_")[:-1]

FIT_YEARS = P1.FIT_YEARS
GATE_YEAR = P1.GATE_YEAR
NY = X.PHASE_NAMES.index("NY")

# ------------------------------------------------------------- the terms ----
SURPRISE_MIN = 0.99                       # P021 T2 (ledger: "surprise>=0.99")
DAY_TYPE_EXPANDED = 2                     # PL.DAY_TYPES index of EXPANDED
RELEASE_MAX_AGE_SEC = 5400                # P022 T3 ("< 90min")
EXT_BREAKOUT_MIN_USD = P1.EXT_MAX_USD     # P017's own $450 refusal threshold

TERMS_P020 = ("T1_phase_is_NY",)
TERMS_P021 = ("T1_day_type_EXPANDED", "T2_surprise_ge_0.99")
TERMS_P022 = ("T1_disagrees_30m", "T2_disagrees_5m", "T3_release_lt_90min")

CONCENTRATOR_MIN = 1.25                   # winner-rate / cond-value ratio
DESTRUCTION_REPS = P1.DESTRUCTION_REPS
DESTRUCTION_SEED = 20260815

PARAMS = {
    "spec_section": SECTION,
    "order": "CC-M2-10.2 — census batch 2 (P020, P021, P022)",
    "definition_source": "provenance/port_m2/PATTERN_LEDGER.tsv (sheet_fields)"
                         " + provenance/port_m2/E1_POSTMORTEMS.md §2/§3/§4",
    "P020": "fire = phase_dec == NY; reported as a base-rate census "
            "(concentration ratio = winner share / candidate share, per "
            "asset x era x phase, broken out by side and by D-071 class)",
    "P021": "fire = day_type == EXPANDED AND surprise >= %.2f, both read from "
            "the DECISION PHASE's fvol row exactly as sections.s2_regime and "
            "sections.s9_vol read them" % SURPRISE_MIN,
    "P021_interaction": "BREAKOUT vs REVERSION direction x the EXPANSION flag, "
                        "difference-in-differences, session-clustered CR1. "
                        "Reading A: side == range-extension side (the more "
                        "recent phase extreme). Reading B: ext_needed > $%.0f "
                        "(P017's own threshold)" % EXT_BREAKOUT_MIN_USD,
    "P022": "fire = sign(phase sflow) disagrees with BOTH sign(30m sflow) and "
            "sign(5m sflow) (all three non-zero) AND 0 <= last_scheduled "
            "release age < %ds" % RELEASE_MAX_AGE_SEC,
    "P022_direction": "among flagged candidates: side aligned with the LIVE "
                      "short windows vs with the PHASE fossil vs with the D10 "
                      "EVENT-ANCHORED window (flow since the release)",
    "value": "c_c_roster.certificates — walled PHASE-CLOSE (adoption) and "
             "walled PEAK-EXIT (CC-M1-8 companion), both always reported",
    "conditional_value": "mean over POSITIVE candidates (CC-M1-7.3)",
    "winner": "cert_close >= $1000 and mae_before_argmax <= $300 and not "
              "walled (D-021)",
    "population": "frozen v3 roster, FIT years %s; %d = GATE echo, EVAL-ONLY"
                  % (list(FIT_YEARS), GATE_YEAR),
    "destruction": "each term shuffled WITHIN SESSION, %d replicates, "
                   "RandomState(%d + term index); the other terms untouched. "
                   "The destroyed quantity is the EDGE (mean cert of the "
                   "firing set minus mean cert of the non-firing rest)"
                   % (DESTRUCTION_REPS, DESTRUCTION_SEED),
    "inference": "CC-M1-12.4 — GEE independence working correlation with the "
                 "Liang-Zeger sandwich clustered on SESSION (CR0 + "
                 "Cameron-Miller CR1); Kish one-way ICC/DEFF for n_eff; "
                 "Holm-Bonferroni over THE WHOLE BATCH (every GEE test of all "
                 "three patterns and both interaction readings is one family)",
    "grading": "CC-M2-9.1 — ENTRY RULE / VETO RULE (Holm-significant beta on "
               "the adoption metric) vs WINNER CONCENTRATOR (>= %.2fx winner "
               "rate or conditional value with no adoption edge -> feature "
               "candidate set only) vs NULL" % CONCENTRATOR_MIN,
    "frame": PL.PARAMS_FRAME,
}


# ---------------------------------------------------------------- detectors -
def terms_p020(f):
    return np.column_stack([f["phase_dec"] == NY])


def terms_p021(f):
    t1 = f["day_type"] == DAY_TYPE_EXPANDED
    sur = f["surprise"]
    t2 = np.isfinite(sur) & (sur >= SURPRISE_MIN)
    return np.column_stack([t1, t2])


def terms_p022(f):
    sph = np.sign(f["fph_sflow"].astype(np.float64))
    s30 = np.sign(f["f30m_sflow"].astype(np.float64))
    s5 = np.sign(f["f5m_sflow"].astype(np.float64))
    t1 = (sph != 0) & (s30 != 0) & (sph != s30)
    t2 = (sph != 0) & (s5 != 0) & (sph != s5)
    age = f["release_age_sec"]
    t3 = (age >= 0) & (age < RELEASE_MAX_AGE_SEC)
    return np.column_stack([t1, t2, t3])


PATTERNS = (("P020", "NY_PHASE_CONCENTRATION", TERMS_P020, terms_p020),
            ("P021", "REGIME_CONDITIONAL_CAPACITY", TERMS_P021, terms_p021),
            ("P022", "FLOW_HORIZON_DISAGREEMENT", TERMS_P022, terms_p022))


def ext_side(f):
    """READING A's range-extension side: +1 up, -1 down, 0 = undefined.

    The phase is extending on the side of its MORE RECENT extreme.  Strictly
    causal: both extreme seconds are taken over [phase_open, dec_sec).
    """
    hi, lo = f["phase_hi_sec"], f["phase_lo_sec"]
    ok = (hi >= 0) & (lo >= 0) & (hi != lo)
    return np.where(ok, np.where(hi > lo, 1, -1), 0).astype(np.int64)


# --------------------------------------------------------------- the pass ---
def _bits(t):
    out = np.zeros(t.shape[0], dtype=np.uint8)
    for k in range(t.shape[1]):
        out |= (t[:, k].astype(np.uint8) << k)
    return out


_KEYS_F64 = ("cert_close", "cert_peak", "day_type_frac", "surprise",
             "ext_needed_usd")
_KEYS_I32 = ("dec_sec", "release_age_sec", "fph_sflow", "f5m_sflow",
             "f30m_sflow", "fev_sflow", "fev_n", "fph_vol", "f5m_vol",
             "f30m_vol")


def _pack(f):
    out = {"asset": f["asset"], "d8": f["d8"],
           "side": f["side"].astype(np.int8),
           "phase_dec": f["phase_dec"].astype(np.int8),
           "day_type": f["day_type"].astype(np.int8),
           "ext_side": ext_side(f).astype(np.int8),
           "klass": f["klass"],
           "walled": f["walled"], "winner": f["winner"],
           "event_in_phase": f["event_in_phase"]}
    out["cert_close"] = f["cert_close_usd"].astype(np.float64)
    out["cert_peak"] = f["cert_peak_usd"].astype(np.float64)
    for k in ("day_type_frac", "surprise", "ext_needed_usd"):
        out[k] = f[k].astype(np.float64)
    for k in _KEYS_I32:
        out[k] = f[k].astype(np.int32)
    for pid, _name, _terms, fn in PATTERNS:
        out["terms_" + pid] = _bits(fn(f))
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


_CONCAT = (("cert_close", "cert_peak", "day_type_frac", "surprise",
            "ext_needed_usd", "side", "phase_dec", "day_type", "ext_side",
            "klass", "walled", "winner", "event_in_phase")
           + _KEYS_I32 + tuple("terms_" + p[0] for p in PATTERNS))


def scan(assets=MC.ASSET_ORDER, years=FIT_YEARS + (GATE_YEAR,), workers=4,
         limit_sessions=None):
    jobs, quarantined = [], 0
    for a in assets:
        # R105: this census pooled the D-058 pre-exam holdout into every GATE
        # row.  The guarded enumerator excludes it and declares the count.
        ds, nq = PL.sessions_fit(a, years=set(years))
        quarantined += nq
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
                    MC.hb("batch2 scan %d/%d  %.1fs" % (n, len(jobs),
                                                        time.time() - t0))
    else:
        for j in jobs:
            res = _one(j)
            if res[0] == "OK":
                parts.append(res[1])
            elif res[0] == "ERROR":
                errs.append((res[1], res[2], res[3]))
    if errs:
        raise RuntimeError("batch2 scan: %d session(s) failed, first=%s"
                           % (len(errs), errs[0]))
    parts.sort(key=lambda p: (p["asset"], p["d8"]))
    out = {}
    for k in _CONCAT:
        out[k] = np.concatenate([p[k] for p in parts])
    out["asset"] = np.concatenate([np.full(p["dec_sec"].size, p["asset"])
                                   for p in parts])
    out["d8"] = np.concatenate([np.full(p["dec_sec"].size, p["d8"],
                                        dtype=np.int32) for p in parts])
    out["year"] = (out["d8"] // 10000).astype(np.int32)
    keys = np.array(["%s-%08d" % (a, d) for a, d in
                     zip(out["asset"].tolist(), out["d8"].tolist())])
    uniq, out["cluster"] = np.unique(keys, return_inverse=True)
    out["n_sessions_total"] = int(uniq.size)
    MC.hb("batch2 scan: %d candidates over %d sessions, %.1fs"
          % (out["dec_sec"].size, uniq.size, time.time() - t0))
    return out


# ------------------------------------------------- P020 concentration table --
CONC_COLUMNS = ("asset", "era", "strata_kind", "strata", "phase",
                "n_sessions", "n_candidates", "cand_share", "n_winners",
                "winner_share", "conc_ratio", "winner_rate",
                "base_winner_rate", "winner_rate_lift", "mean_close",
                "cond_close", "mean_peak", "cond_peak")


def concentration_rows(D):
    """The base-rate object P020 actually is.

    conc_ratio = (winners in the cell / winners in its stratum) /
                 (candidates in the cell / candidates in its stratum).
    A phase that merely holds more CANDIDATES scores 1.00 — which is the
    "is it an artefact of where candidates are generated?" test the ledger
    demanded, written as one number.
    """
    rows = []
    era_sel = [("FIT", np.isin(D["year"], FIT_YEARS)),
               ("GATE_%d" % GATE_YEAR, D["year"] == GATE_YEAR)]
    era_sel += [(str(y), D["year"] == y) for y in FIT_YEARS]
    assets = [("ALL", np.ones(D["winner"].size, dtype=bool))]
    assets += [(a, D["asset"] == a) for a in MC.ASSET_ORDER]
    strata = [("ALL", [("ALL", np.ones(D["winner"].size, dtype=bool))]),
              ("SIDE", [("LONG", D["side"] == 1), ("SHORT", D["side"] == -1)]),
              ("CLASS", [(k, D["klass"] == k)
                         for k in sorted(set(D["klass"].tolist()))])]
    for aname, asel in assets:
        for ename, esel in era_sel:
            for kind, groups in strata:
                for gname, gsel in groups:
                    base = asel & esel & gsel
                    nb = int(base.sum())
                    if not nb:
                        continue
                    wb = int(D["winner"][base].sum())
                    nsess = len(set(D["cluster"][base].tolist()))
                    base_rate = float(wb) / nb
                    for p in range(X.N_PHASES):
                        m = base & (D["phase_dec"] == p)
                        n = int(m.sum())
                        if not n:
                            continue
                        w = int(D["winner"][m].sum())
                        cs = float(n) / nb
                        ws = (float(w) / wb) if wb else float("nan")
                        st = P1._stats(D["cert_close"][m], D["cert_peak"][m],
                                       D["winner"][m], nsess)
                        rows.append([
                            aname, ename, kind, gname, X.PHASE_NAMES[p],
                            nsess, n, cs, w, ws,
                            (ws / cs) if (cs > 0 and wb) else float("nan"),
                            st["winner_frac"], base_rate,
                            (st["winner_frac"] / base_rate) if base_rate > 0
                            else float("nan"),
                            st["mean_close"], st["cond_close"],
                            st["mean_peak"], st["cond_peak"]])
    return rows


# -------------------------------------------------- P021 interaction tables --
INTER_COLUMNS = ("reading", "asset", "era", "flag", "direction", "n",
                 "n_sessions", "mean_close", "cond_close", "posfrac_close",
                 "mean_peak", "n_winners", "winner_frac")

DIRECTION_READINGS = ("A_extension_side", "B_ext_needed")


def breakout_masks(D, reading):
    """(breakout, reversion) boolean masks for one direction reading."""
    if reading == "A_extension_side":
        es = D["ext_side"]
        return (es != 0) & (D["side"] == es), (es != 0) & (D["side"] == -es)
    ext = D["ext_needed_usd"]
    ok = np.isfinite(ext)
    return ok & (ext > EXT_BREAKOUT_MIN_USD), ok & (ext <= EXT_BREAKOUT_MIN_USD)


def interaction_rows(D, flag):
    rows = []
    era_sel = [("FIT", np.isin(D["year"], FIT_YEARS)),
               ("GATE_%d" % GATE_YEAR, D["year"] == GATE_YEAR)]
    assets = [("ALL", np.ones(flag.size, dtype=bool))]
    assets += [(a, D["asset"] == a) for a in MC.ASSET_ORDER]
    for reading in DIRECTION_READINGS:
        brk, rev = breakout_masks(D, reading)
        for aname, asel in assets:
            for ename, esel in era_sel:
                base = asel & esel
                if not base.any():
                    continue
                nsess = len(set(D["cluster"][base].tolist()))
                for fname, fsel in (("FLAGGED", flag), ("UNFLAGGED", ~flag)):
                    for dname, dsel in (("BREAKOUT", brk), ("REVERSION", rev),
                                        ("NO_DIRECTION", ~(brk | rev))):
                        m = base & fsel & dsel
                        if not m.any():
                            continue
                        st = P1._stats(D["cert_close"][m], D["cert_peak"][m],
                                       D["winner"][m], nsess)
                        rows.append([reading, aname, ename, fname, dname,
                                     st["n_candidates"], nsess,
                                     st["mean_close"], st["cond_close"],
                                     st["posfrac_close"], st["mean_peak"],
                                     st["n_winners"], st["winner_frac"]])
    return rows


def _did(y, flag, brk, cl):
    """Difference in differences with the CR1 sandwich, clustered on session.

    Model: y = b0 + b1*(flag x breakout) + b2*flag + b3*breakout.  b1 IS the
    interaction — how much MORE a breakout-direction entry is worth on an
    EXPANSION-flagged candidate than on an unflagged one.  gee_independence
    reports column 1, so the interaction is passed FIRST by construction.
    """
    x = np.column_stack([flag * brk, flag, brk]).astype(np.float64)
    if x.shape[0] <= 4 or not np.any(x[:, 0] > 0) or np.all(x[:, 0] > 0):
        return None
    return EV.gee_independence(y, x, cl, link="identity")


def did_rows(D, flag):
    """The load-bearing test, in P001's ROBUST column layout (so the whole
    batch goes through ONE Holm correction)."""
    rows = []
    fit = np.isin(D["year"], FIT_YEARS)
    assets = [("ALL", np.ones(flag.size, dtype=bool))]
    assets += [(a, D["asset"] == a) for a in MC.ASSET_ORDER]
    for reading in DIRECTION_READINGS:
        brk, rev = breakout_masks(D, reading)
        keep = brk | rev                   # NO_DIRECTION rows carry no contrast
        for aname, asel in assets:
            m = asel & fit & keep
            if not m.any():
                continue
            fl = flag[m].astype(np.float64)
            bk = brk[m].astype(np.float64)
            cl = D["cluster"][m]
            for metric, y in (("cert_close", D["cert_close"][m]),
                              ("cert_peak", D["cert_peak"][m])):
                g = _did(y, fl, bk, cl)
                ic = EV.icc_oneway(y, cl)
                tag = "P021_DID_" + reading[0]
                if g is None:
                    rows.append([tag, aname, "FIT", metric, int(y.size),
                                 int(len(set(cl.tolist()))),
                                 int((fl * bk).sum())]
                                + [float("nan")] * 6
                                + [ic["rho"] if ic else float("nan"),
                                   ic["deff"] if ic else float("nan"),
                                   ic["n_eff"] if ic else float("nan"),
                                   "NO_VARIATION"])
                    continue
                z = (g["beta"] / g["se_cr1"]) if g["se_cr1"] > 0 else float("nan")
                p = P1._p_two_sided(z)
                rows.append([tag, aname, "FIT", metric, g["n"],
                             g["n_clusters"], int((fl * bk).sum()),
                             g["beta"], g["se_naive"], g["se_cr0"],
                             g["se_cr1"], z, p,
                             ic["rho"] if ic else float("nan"),
                             ic["deff"] if ic else float("nan"),
                             ic["n_eff"] if ic else float("nan"),
                             ("SIGNIFICANT_p<0.05" if np.isfinite(p) and p < 0.05
                              else "NOT_SIGNIFICANT")])
    return rows


# --------------------------------------------------- P022 direction table ----
DIR_COLUMNS = ("window", "asset", "era", "alignment", "side", "n",
               "n_sessions", "mean_close", "cond_close", "posfrac_close",
               "mean_peak", "n_winners", "winner_frac")


def p022_direction_rows(D, flag):
    """Is the fossil-flow flag a VETO or a COMPASS?

    Among FLAGGED candidates the phase window and the short windows point in
    opposite directions by construction, so every flagged candidate is aligned
    with exactly one of them.  If the short windows are the live market (the
    E1D2 diagnosis) the LIVE-aligned half must beat the FOSSIL-aligned half.
    The D10 EVENT-ANCHORED window is reported as a third reading — flow
    accumulated since the release rather than since the phase open.
    """
    rows = []
    era_sel = [("FIT", np.isin(D["year"], FIT_YEARS)),
               ("GATE_%d" % GATE_YEAR, D["year"] == GATE_YEAR)]
    assets = [("ALL", np.ones(flag.size, dtype=bool))]
    assets += [(a, D["asset"] == a) for a in MC.ASSET_ORDER]
    side = D["side"].astype(np.float64)
    windows = (("5m", np.sign(D["f5m_sflow"].astype(np.float64))),
               ("30m", np.sign(D["f30m_sflow"].astype(np.float64))),
               ("phase", np.sign(D["fph_sflow"].astype(np.float64))),
               ("event_anchored", np.where(
                   D["event_in_phase"],
                   np.sign(D["fev_sflow"].astype(np.float64)), 0.0)))
    for wname, sgn in windows:
        for aname, asel in assets:
            for ename, esel in era_sel:
                base = asel & esel & flag
                if not base.any():
                    continue
                nsess = len(set(D["cluster"][base].tolist()))
                for alab, amask in (("ALIGNED", (sgn != 0) & (side == sgn)),
                                    ("OPPOSED", (sgn != 0) & (side == -sgn)),
                                    ("NO_SIGN", sgn == 0)):
                    for sname, ssel in (("ALL", np.ones(flag.size, dtype=bool)),
                                        ("LONG", D["side"] == 1),
                                        ("SHORT", D["side"] == -1)):
                        m = base & amask & ssel
                        if not m.any():
                            continue
                        st = P1._stats(D["cert_close"][m], D["cert_peak"][m],
                                       D["winner"][m], nsess)
                        rows.append([wname, aname, ename, alab, sname,
                                     st["n_candidates"], nsess,
                                     st["mean_close"], st["cond_close"],
                                     st["posfrac_close"], st["mean_peak"],
                                     st["n_winners"], st["winner_frac"]])
    return rows


# ----------------------------------------------------------------- grading --
def grade(res, cen):
    """(verdict, evidence) in the CC-M2-9.1 vocabulary."""
    fF = cen.get(("ALL", "FIT", "ALL", "ALL", "FIRE"))
    fN = cen.get(("ALL", "FIT", "ALL", "ALL", "NOFIRE"))
    rb = [x for x in res["robust"]
          if x[1] == "ALL" and x[2] == "FIT" and x[3] == "cert_close"]
    if fF is None or fN is None or fF[7] == 0:
        return "NULL_never_fires", {}
    beta = rb[0][7] if rb else float("nan")
    holm = rb[0][19] if rb and len(rb[0]) > 19 else "NO_TEST"
    wr = (fF[16] / fN[16]) if fN[16] else float("nan")
    cv = (fF[10] / fN[10]) if fN[10] else float("nan")
    ev = {"beta_close": beta, "holm": holm, "winner_rate_ratio": wr,
          "cond_value_ratio": cv}
    sig = (holm == "HOLM_SIGNIFICANT")
    if sig and np.isfinite(beta) and beta > 0:
        return "ENTRY RULE (adoption-metric edge, Holm-significant)", ev
    if sig and np.isfinite(beta) and beta < 0:
        return "VETO RULE (flagged pool is worth refusing, Holm-significant)", ev
    if ((np.isfinite(wr) and wr >= CONCENTRATOR_MIN)
            or (np.isfinite(cv) and cv >= CONCENTRATOR_MIN)):
        return ("WINNER CONCENTRATOR (feature candidate set only — CC-M2-9.1 "
                "disposition)"), ev
    return "NULL (no adoption edge, no concentration)", ev


# ------------------------------------------------------------------ report --
_fmt = P1._fmt

SUPPORT_CASES = (
    ("SI-20210702-051810-L", "P021 proof case (+$1,707.50; ext_needed $512.5)"),
    ("SI-20210702-052297-L", "P021 proof case (+$1,682.50; ext_needed $537.5)"),
    ("SI-20210702-057352-L", "the seat the reader READ THE REGIME ON "
                             "(EXPANDED, 112.1% of range_hat, surprise 0.993)"),
    ("SI-20210702-052509-S", "P022 birth case (-$930; think-aloud committed)"),
    ("SI-20210702-054009-S", "P022 companion (-$930)"),
)


def report(D, res, elapsed, pins):
    L = []
    A = L.append
    A("# CENSUS BATCH 2 — P020 / P021 / P022 name->count censuses")
    A("")
    A("Ordered by CC-M2-10.2. Population: the frozen v3 roster, %d candidates "
      "over %d sessions (FIT %d-%d + the %d GATE echo, eval-only), all three "
      "assets. Detectors are strictly causal and read only committed "
      "pattern_lib frame fields."
      % (int(D["dec_sec"].size), int(D["n_sessions_total"]), FIT_YEARS[0],
         FIT_YEARS[-1], GATE_YEAR))
    A("")
    A("MULTIPLICITY: every GEE test of all three patterns AND both P021 "
      "interaction readings is corrected Holm-Bonferroni as ONE family (%d "
      "tests). A raw p<0.05 that fails Holm is noise and the tables say which "
      "is which." % len([r for r in res["robust_all"]
                         if np.isfinite(r[12])]))
    A("")

    A("## HEADLINE VERDICTS (CC-M2-9.1 vocabulary)")
    A("")
    for pid, name, _terms, _fn in PATTERNS:
        r = res[pid]
        cen = r["cen"]
        fF = cen.get(("ALL", "FIT", "ALL", "ALL", "FIRE"))
        fN = cen.get(("ALL", "FIT", "ALL", "ALL", "NOFIRE"))
        verdict, ev = grade(r, cen)
        rb = [x for x in r["robust"]
              if x[1] == "ALL" and x[2] == "FIT" and x[3] == "cert_close"]
        rp = [x for x in r["robust"]
              if x[1] == "ALL" and x[2] == "FIT" and x[3] == "cert_peak"]
        if fF is None or fF[7] == 0:
            A("* **%s %s** — the detector never fires on FIT." % (pid, name))
            continue
        A("* **%s %s** — fires on %d of %d FIT candidates (%s%%). ADOPTION "
          "METRIC (walled phase-close): mean $%s for the firing set vs $%s for "
          "the rest, session-clustered difference $%s (CR1 se $%s, p=%s, %s). "
          "PEAK-EXIT companion: $%s (p=%s). CONDITIONAL value $%s vs $%s = "
          "%sx. D-021 winner rate %s%% vs %s%% = %sx. **VERDICT: %s**"
          % (pid, name, fF[7], fF[7] + fN[7],
             _fmt(100.0 * fF[7] / max(fF[7] + fN[7], 1), 2),
             _fmt(fF[9]), _fmt(fN[9]),
             _fmt(rb[0][7]) if rb else ".", _fmt(rb[0][10]) if rb else ".",
             _fmt(rb[0][12], 5) if rb else ".",
             (rb[0][19] if rb and len(rb[0]) > 19 else "NO_TEST"),
             _fmt(rp[0][7]) if rp else ".",
             _fmt(rp[0][12], 5) if rp else ".",
             _fmt(fF[10]), _fmt(fN[10]), _fmt(ev.get("cond_value_ratio"), 2),
             _fmt(100.0 * fF[16], 2), _fmt(100.0 * fN[16], 2),
             _fmt(ev.get("winner_rate_ratio"), 2), verdict))
    A("")

    # ---------------------------------------------------------------- P020 --
    A("## P020 NY_PHASE_CONCENTRATION — the base-rate census")
    A("")
    A("The ledger's own instruction: 'winner rate by (phase_dec, asset) over "
      "the whole era, and check it is not an artefact of where candidates are "
      "generated'. `conc_ratio` is that check: winners' share of a phase "
      "divided by candidates' share of it. 1.00 = the phase holds winners in "
      "exact proportion to the candidates generated inside it.")
    A("")
    A("| asset | era | phase | candidates | cand share | winners | winner "
      "share | conc_ratio | winner rate % | mean close $ | cond close $ |")
    A("|---|---|---|---|---|---|---|---|---|---|---|")
    for x in res["conc"]:
        if x[2] != "ALL" or x[1] not in ("FIT", "GATE_%d" % GATE_YEAR):
            continue
        A("| %s | %s | %s | %d | %s | %d | %s | %s | %s | %s | %s |"
          % (x[0], x[1], x[4], x[6], _fmt(x[7], 4), x[8], _fmt(x[9], 4),
             _fmt(x[10], 3), _fmt(100.0 * x[11], 3), _fmt(x[14]), _fmt(x[15])))
    A("")
    A("Per-year stability of the NY concentration ratio (ALL assets):")
    A("")
    A("| year | NY candidates | NY cand share | NY winners | NY winner share "
      "| conc_ratio | NY winner rate % |")
    A("|---|---|---|---|---|---|---|")
    for y in [str(v) for v in FIT_YEARS] + ["GATE_%d" % GATE_YEAR]:
        for x in res["conc"]:
            if (x[0] == "ALL" and x[1] == y and x[2] == "ALL"
                    and x[4] == "NY"):
                A("| %s%s | %d | %s | %d | %s | %s | %s |"
                  % (y, " (eval-only)" if y.startswith("GATE") else "",
                     x[6], _fmt(x[7], 4), x[8], _fmt(x[9], 4), _fmt(x[10], 3),
                     _fmt(100.0 * x[11], 3)))
    A("")
    A("Side and class break-out (FIT, ALL assets, NY phase) — the E1D2 finding "
      "was that the SIDE term is a session property and must never be encoded, "
      "while the PHASE term is 86-for-86; these rows are that claim at era "
      "scale:")
    A("")
    A("| stratum | candidates | conc_ratio | winner rate % | base rate % | "
      "lift | mean close $ |")
    A("|---|---|---|---|---|---|---|")
    for x in res["conc"]:
        if (x[0] == "ALL" and x[1] == "FIT" and x[4] == "NY"
                and x[2] in ("SIDE", "CLASS")):
            A("| %s %s | %d | %s | %s | %s | %s | %s |"
              % (x[2], x[3], x[6], _fmt(x[10], 3), _fmt(100.0 * x[11], 3),
                 _fmt(100.0 * x[12], 3), _fmt(x[13], 2), _fmt(x[14])))
    A("")

    # ---------------------------------------------------------------- P021 --
    A("## P021 REGIME_CONDITIONAL_CAPACITY — the interaction is the point")
    A("")
    A("THE CLAIM UNDER TEST (E1_POSTMORTEMS §3): on EXPANSION-flagged "
      "candidates, BREAKOUT-direction entries outperform REVERSION-direction "
      "entries; on non-flagged candidates the ordering reverses. Two readings "
      "of direction (A = side equals the range-extension side; B = P017's own "
      "ext_needed > $%.0f). The 2x2 is the evidence; the difference in "
      "differences is the test." % EXT_BREAKOUT_MIN_USD)
    A("")
    for reading in DIRECTION_READINGS:
        A("### direction reading %s (FIT, ALL assets)" % reading)
        A("")
        A("| flag | direction | n | mean close $ | cond close $ | mean peak $ "
          "| winners | winner rate % |")
        A("|---|---|---|---|---|---|---|---|")
        cells = {}
        for x in res["inter"]:
            if x[0] == reading and x[1] == "ALL" and x[2] == "FIT":
                cells[(x[3], x[4])] = x
                A("| %s | %s | %d | %s | %s | %s | %d | %s |"
                  % (x[3], x[4], x[5], _fmt(x[7]), _fmt(x[8]), _fmt(x[10]),
                     x[11], _fmt(100.0 * x[12], 3)))
        A("")
        d_fl = d_un = float("nan")
        if ("FLAGGED", "BREAKOUT") in cells and ("FLAGGED", "REVERSION") in cells:
            d_fl = cells[("FLAGGED", "BREAKOUT")][7] - cells[("FLAGGED", "REVERSION")][7]
        if (("UNFLAGGED", "BREAKOUT") in cells
                and ("UNFLAGGED", "REVERSION") in cells):
            d_un = (cells[("UNFLAGGED", "BREAKOUT")][7]
                    - cells[("UNFLAGGED", "REVERSION")][7])
        A("breakout - reversion, FLAGGED: **$%s**; UNFLAGGED: **$%s**; "
          "difference in differences: **$%s**."
          % (_fmt(d_fl), _fmt(d_un), _fmt(d_fl - d_un)))
        A("")
    # WHEN the flag fires is part of what it is worth: a regime state that only
    # prints EXPANDED after the day has already expanded is a LAGGING
    # conditioner, and a lagging conditioner cannot admit the breakout it was
    # invented to admit.  Two medians on the session clock say it in one line.
    fit = np.isin(D["year"], FIT_YEARS)
    fl = res["P021"]["fire"]
    win = D["winner"]

    def _med(m):
        return (float(np.median(D["dec_sec"][m])) if m.any() else float("nan"))
    A("WHEN THE FLAG FIRES (FIT, session clock in seconds from the session "
      "open): median decision second of FLAGGED candidates %s vs UNFLAGGED "
      "%s; median decision second of all D-021 WINNERS %s, and of the winners "
      "the flag covers %s. A conditioner that only prints EXPANDED after the "
      "day has expanded arrives LATE by construction, which is the mechanism "
      "behind the interaction result below."
      % (_fmt(_med(fit & fl), 0), _fmt(_med(fit & ~fl), 0),
         _fmt(_med(fit & win), 0), _fmt(_med(fit & win & fl), 0)))
    A("")
    A("Difference-in-differences, session-clustered (CR1), FIT only. beta = "
      "the INTERACTION coefficient: the extra dollars a breakout-direction "
      "entry is worth on an EXPANSION-flagged candidate over an unflagged one.")
    A("")
    A("| test | asset | metric | n | beta $ | se CR1 | z | p | DEFF | n_eff | "
      "raw | Holm |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for x in res["did"]:
        A("| %s | %s | %s | %d | %s | %s | %s | %s | %s | %s | %s | %s |"
          % (x[0], x[1], x[3], x[4], _fmt(x[7]), _fmt(x[10]),
             _fmt(x[11], 2), _fmt(x[12], 5), _fmt(x[14], 2), _fmt(x[15], 1),
             x[16], x[19] if len(x) > 19 else "NO_TEST"))
    A("")

    # ---------------------------------------------------------------- P022 --
    A("## P022 FLOW_HORIZON_DISAGREEMENT — veto or compass?")
    A("")
    A("Among FLAGGED candidates the phase window and the short windows point "
      "opposite ways by construction, so every flagged candidate is aligned "
      "with exactly one of them. If the short windows are the live market, the "
      "LIVE-aligned half beats the FOSSIL-aligned half. The D10 "
      "EVENT-ANCHORED window (flow since the release, never across it) is the "
      "third reading.")
    A("")
    A("| window | alignment | side | n | mean close $ | cond close $ | mean "
      "peak $ | winners | winner rate % |")
    A("|---|---|---|---|---|---|---|---|---|")
    for x in res["dir22"]:
        if x[1] != "ALL" or x[2] != "FIT" or x[3] == "NO_SIGN":
            continue
        A("| %s | %s | %s | %d | %s | %s | %s | %d | %s |"
          % (x[0], x[3], x[4], x[5], _fmt(x[7]), _fmt(x[8]), _fmt(x[10]),
             x[11], _fmt(100.0 * x[12], 3)))
    A("")

    # ------------------------------------------------- per-pattern detail ----
    for pid, name, terms, _fn in PATTERNS:
        r = res[pid]
        cen = r["cen"]
        fitF = cen.get(("ALL", "FIT", "ALL", "ALL", "FIRE"))
        fitN = cen.get(("ALL", "FIT", "ALL", "ALL", "NOFIRE"))
        A("## %s %s — detail" % (pid, name))
        A("")
        if fitF is None or fitF[7] == 0:
            A("**The detector never fires on FIT.**")
            A("")
            continue
        A("| | fires | per session | mean close $ | cond. close $ | mean peak "
          "$ | cond. peak $ | winners |")
        A("|---|---|---|---|---|---|---|---|")
        for tag, x in (("FIRE", fitF), ("NOFIRE", fitN)):
            A("| %s | %d | %s | %s | %s | %s | %s | %d (%s%%) |"
              % (tag, x[7], _fmt(x[8], 3), _fmt(x[9]), _fmt(x[10]),
                 _fmt(x[12]), _fmt(x[13]), x[15], _fmt(100.0 * x[16], 3)))
        A("")
        A("Per-year stability (ALL assets):")
        A("")
        A("| year | fires | mean close $ | cond close $ | winner rate % | "
          "baseline mean $ | baseline winner rate % |")
        A("|---|---|---|---|---|---|---|")
        for y in [str(v) for v in FIT_YEARS] + ["GATE_%d" % GATE_YEAR]:
            x = cen.get(("ALL", y, "ALL", "ALL", "FIRE"))
            n = cen.get(("ALL", y, "ALL", "ALL", "NOFIRE"))
            if x is None or n is None:
                continue
            A("| %s%s | %d | %s | %s | %s | %s | %s |"
              % (y, " (eval-only)" if y.startswith("GATE") else "",
                 x[7], _fmt(x[9]), _fmt(x[10]), _fmt(100.0 * x[16], 3),
                 _fmt(n[9]), _fmt(100.0 * n[16], 3)))
        A("")
        A("Per-asset / per-side (FIT):")
        A("")
        A("| stratum | fires | mean close $ | cond close $ | winner rate % | "
          "baseline mean $ |")
        A("|---|---|---|---|---|---|")
        for key in sorted(cen):
            an, en, pn, sn, gp = key
            if gp != "FIRE" or en != "FIT" or cen[key][7] == 0:
                continue
            if an == "ALL" and pn == "ALL" and sn == "ALL":
                continue
            if pn != "ALL" and pid == "P020":
                continue               # phase strata are P020's own term
            x = cen[key]
            b = cen.get((an, en, pn, sn, "NOFIRE"))
            A("| %s / %s / %s | %d | %s | %s | %s | %s |"
              % (an, pn, sn, x[7], _fmt(x[9]), _fmt(x[10]),
                 _fmt(100.0 * x[16], 3), _fmt(b[9]) if b else "."))
        A("")
        A("Mechanism destruction (FIT, ALL assets; each term shuffled within "
          "its session, %d replicates). EDGE = mean close of the firing set "
          "minus the non-firing rest; retention = destroyed edge / intact "
          "edge. High retention means the term was not carrying the value."
          % DESTRUCTION_REPS)
        A("")
        A("| neutralised term | fires (mean) | mean close $ | edge close $ | "
          "intact edge $ | retention close | retention peak | verdict |")
        A("|---|---|---|---|---|---|---|---|")
        for x in r["destr"]:
            if x[1] != "ALL":
                continue
            A("| %s | %s | %s | %s | %s | %s | %s | %s |"
              % (x[2], _fmt(x[3], 1), _fmt(x[5]), _fmt(x[7]), _fmt(x[14]),
                 _fmt(x[17], 3), _fmt(x[18], 3), x[19]))
        A("")
        A("Term marginals (FIT, ALL assets):")
        A("")
        A("| term | alone: n / mean close $ | detector without it: n / mean "
          "close $ | near-miss (only this fails): n / mean close $ |")
        A("|---|---|---|---|")
        for name_t in terms:
            cells = {}
            for x in r["terms"]:
                if x[1] == "ALL" and x[3] == name_t:
                    cells[x[2]] = x

            def cell(sc):
                x = cells.get(sc)
                return "." if x is None else "%d / %s" % (x[4], _fmt(x[6]))
            A("| %s | %s | %s | %s |"
              % (name_t, cell("TERM_ALONE"), cell("DETECTOR_MINUS_TERM"),
                 cell("NEAR_MISS_ONLY_THIS_TERM_FAILS")))
        A("")
        A("Cluster-robust inference (GEE identity link, Liang-Zeger sandwich "
          "clustered on SESSION, CR1; Holm over the whole batch):")
        A("")
        A("| asset | era | metric | beta $ | se naive | se CR1 | z | p | DEFF "
          "| n_eff | raw verdict | Holm |")
        A("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for x in r["robust"]:
            A("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |"
              % (x[1], x[2], x[3], _fmt(x[7]), _fmt(x[8]), _fmt(x[10]),
                 _fmt(x[11], 2), _fmt(x[12], 5), _fmt(x[14], 2), _fmt(x[15], 1),
                 x[16], x[19] if len(x) > 19 else "NO_TEST"))
        A("")

    A("## Named-case check (the E1D2 cases these patterns were written from)")
    A("")
    A("| case | note | P020 | P021 | P022 | day_type | surprise | ext_needed $ "
      "| release age s | cert close $ |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for cid, note in SUPPORT_CASES:
        a, d8, sec, side = MC.parse_cid(cid)
        m = ((D["asset"] == a) & (D["d8"] == d8) & (D["dec_sec"] == sec)
             & (D["side"] == side))
        if not m.any():
            A("| %s | %s | . | . | . | . | . | . | . | . |" % (cid, note))
            continue
        t = int(np.nonzero(m)[0][0])
        fires = []
        for pid, _n, terms, _fn in PATTERNS:
            T = P1.unbits(D["terms_" + pid], len(terms))
            fires.append("YES" if bool(np.all(T[t])) else "no")
        A("| %s | %s | %s | %s | %s | %s | %s | %s | %d | %s |"
          % (cid, note, fires[0], fires[1], fires[2],
             (PL.DAY_TYPES[int(D["day_type"][t])]
              if D["day_type"][t] >= 0 else "REFUSED"),
             _fmt(float(D["surprise"][t]), 3),
             _fmt(float(D["ext_needed_usd"][t]), 1),
             int(D["release_age_sec"][t]), _fmt(float(D["cert_close"][t]))))
    A("")
    A("## Provenance")
    A("")
    A("* engine: `engine/port_m2/p020_census.py` (census machinery reused from "
      "`p001_census.py`; frame from `pattern_lib.py`)")
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
    census, terms, destr = [], [], []
    robust_nc = []                        # un-Holmed; one family for the batch
    for pid, _name, tnames, _fn in PATTERNS:
        T = P1.unbits(D["terms_" + pid], len(tnames))
        fire = np.all(T, axis=1)
        rows_c = P1.census_rows(D, fire, pid)
        rows_t = P1.term_rows(D, T, pid, tnames)
        # P020's single term IS the detector, so its leave-one-out marginals
        # are the whole population; they are still emitted (cheap, and the
        # TERM_ALONE row is the census row) but the destruction test is the
        # informative one.
        rows_d = P1.destruction_rows(D, T, pid, tnames)
        rows_r = P1.robust_rows(D, fire, pid, holm=False)
        res[pid] = {"fire": fire, "terms": rows_t, "destr": rows_d,
                    "robust": rows_r, "n_fires": int(fire.sum()),
                    "cen": {(x[1], x[2], x[3], x[4], x[5]): x for x in rows_c}}
        census += rows_c
        terms += rows_t
        destr += rows_d
        robust_nc += rows_r
        MC.hb("batch2 %s: %d fires" % (pid, int(fire.sum())))

    flag21 = res["P021"]["fire"]
    res["conc"] = concentration_rows(D)
    res["inter"] = interaction_rows(D, flag21)
    did = did_rows(D, flag21)
    robust_nc += did
    res["dir22"] = p022_direction_rows(D, res["P022"]["fire"])
    # ONE Holm family over the whole batch (CC-M2-10.2's "Holm over the batch")
    P1._holm(robust_nc)
    res["robust_all"] = robust_nc
    res["did"] = [r for r in robust_nc if str(r[0]).startswith("P021_DID_")]
    for pid, _n, _t, _f in PATTERNS:
        res[pid]["robust"] = [r for r in robust_nc if r[0] == pid]

    phash = MC.params_hash(PARAMS)
    extra = ["CC-M2-10.2 census batch 2 — P020/P021/P022, strictly causal "
             "detectors over the frozen v3 roster",
             "BOTH CC-M1-8 certificate readings are reported on every row",
             "Holm-Bonferroni is applied over the WHOLE batch, not per pattern"]
    MC.write_tsv(os.path.join(OUT_DIR, "BATCH2_CENSUS.tsv"), SECTION, phash,
                 list(P1.CENSUS_COLUMNS), census, extra=extra)
    MC.write_tsv(os.path.join(OUT_DIR, "BATCH2_TERMS.tsv"), SECTION, phash,
                 list(P1.TERM_COLUMNS), terms, extra=extra)
    MC.write_tsv(os.path.join(OUT_DIR, "BATCH2_DESTRUCTION.tsv"), SECTION,
                 phash, list(P1.DESTRUCTION_COLUMNS), destr, extra=extra)
    MC.write_tsv(os.path.join(OUT_DIR, "BATCH2_ROBUST.tsv"), SECTION, phash,
                 list(P1.ROBUST_COLUMNS), robust_nc, extra=extra)
    MC.write_tsv(os.path.join(OUT_DIR, "P020_CONCENTRATION.tsv"), SECTION,
                 phash, list(CONC_COLUMNS), res["conc"],
                 extra=["conc_ratio = winner share / candidate share; 1.00 "
                        "means the phase holds winners in proportion to the "
                        "candidates generated inside it"])
    MC.write_tsv(os.path.join(OUT_DIR, "P021_INTERACTION.tsv"), SECTION, phash,
                 list(INTER_COLUMNS), res["inter"],
                 extra=["the load-bearing 2x2: EXPANSION flag x trade "
                        "direction, two readings of direction"])
    MC.write_tsv(os.path.join(OUT_DIR, "P022_DIRECTION.tsv"), SECTION, phash,
                 list(DIR_COLUMNS), res["dir22"],
                 extra=["FLAGGED candidates only: is the flag a veto or a "
                        "compass? ALIGNED = the trade side agrees with that "
                        "window's flow sign"])
    pins = MC.pins_moved()
    el = time.time() - t0
    MC.write_text(os.path.join(OUT_DIR, "P020_P022_CENSUS_REPORT.md"),
                  report(D, res, el, pins))
    MC.write_json(os.path.join(OUT_DIR, "p020_census.receipt.json"),
                  {"env": MC.env_receipt(PARAMS),
                   "n_candidates": int(D["dec_sec"].size),
                   "n_sessions": int(D["n_sessions_total"]),
                   "n_fires": {p[0]: res[p[0]]["n_fires"] for p in PATTERNS},
                   "n_gee_tests": int(len([r for r in robust_nc
                                           if np.isfinite(r[12])])),
                   "elapsed_sec": el, "pins_moved": pins, "out_dir": OUT_DIR})
    MC.hb("batch2 census: %s, %.1fs"
          % (", ".join("%s=%d" % (p[0], res[p[0]]["n_fires"])
                       for p in PATTERNS), el))
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
