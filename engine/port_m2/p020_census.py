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
    "holdout": "D-058 — the population comes from pattern_lib.sessions_fit, "
               "which EXCLUDES every session >= %d and returns the excluded "
               "count for the receipt (R105). The GATE echo is a HALF year and "
               "is named GATE_%dH1." % (MC.HOLDOUT_FROM_D8, GATE_YEAR),
    "promotion": "R106 — WINNER CONCENTRATOR requires the ratio to clear "
                 "%.2fx AND a session-clustered bootstrap interval excluding "
                 "1.0 AND Holm significance in the PROMOTION family AND the "
                 "n floors (%d fires over %d sessions). The bare ratio it "
                 "replaces was the only route into the feature-candidate set."
                 % (CONCENTRATOR_MIN, P1.PROMOTE_MIN_FIRES,
                    P1.PROMOTE_MIN_CLUSTERS),
    "mirror_law": "R112 — P021's BREAKOUT-vs-REVERSION claim (both readings, "
                  "flagged and unflagged) and P022's ALIGNED-vs-OPPOSED pair "
                  "are compared WITHIN each session against their sign-flipped "
                  "twins and decided by m2_common.mirror_paired "
                  "(BATCH2_MIRROR.tsv)",
    "ext_saturation": "R111 — pattern_lib clips ext_needed at zero, so every "
                      "candidate whose extreme already offers >= $1,000 of "
                      "reach collapsed to ext == 0 and was classified "
                      "REVERSION. Those rows now sit in their own "
                      "EXT_SATURATED bucket, are EXCLUDED from the DiD "
                      "contrast, and their fraction is in the receipt.",
    "destruction_seed_use": "R116 — DESTRUCTION_SEED %d is PASSED to "
                            "P1.destruction_rows and is the seed actually "
                            "used; the stream is additionally keyed on the "
                            "READING, so p020's three patterns no longer draw "
                            "byte-identical permutations from each other, from "
                            "p001's arms, or from p025's nine readings"
                            % DESTRUCTION_SEED,
    "in_sample": "R114 — SURPRISE_MIN 0.99, DAY_TYPE_EXPANDED and "
                 "RELEASE_MAX_AGE_SEC come from the PATTERN_LEDGER "
                 "sheet_fields written off E1 study days 1/2/3, all inside "
                 "FIT; EXT_BREAKOUT_MIN_USD is e1d1_policy T3's own $450. "
                 "Every table carries FIT_EX_FITTING beside FIT and the "
                 "named-case table is a REPRODUCTION CHECK, not evidence. "
                 "None of these constants carries a sensitivity sweep.",
    "inference_floors": "R113 — no GEE below %d clusters; t(G-1) reference"
                        % P1.MIN_CLUSTERS_GEE,
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
        for n, j in enumerate(jobs, 1):
            res = _one(j)
            if res[0] == "OK":
                parts.append(res[1])
            elif res[0] == "ERROR":
                errs.append((res[1], res[2], res[3]))
            if n % 250 == 0:               # MINOR: the serial path had none
                MC.hb("batch2 scan %d/%d  %.1fs" % (n, len(jobs),
                                                    time.time() - t0))
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
    # R105: the D-058 quarantine, declared as a COUNT rather than an absence.
    out["n_quarantined_holdout"] = int(quarantined)
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
    era_sel = P1.era_selectors(D)
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
                        # MINOR (3.2b): n_sessions used to be computed on the
                        # STRATUM and reported on every cell inside it, so the
                        # column did not describe its own row.
                        nsess = len(set(D["cluster"][m].tolist()))
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


def reach_usd(D):
    """Dollars of reach the phase extreme already offers, recovered from
    `ext_needed_usd` — and `ext_saturated`, the rows where the recovery FAILS.

    R111: `pattern_lib` clips `ext_needed = max(0, 1000 - reach)` at zero
    (`:977-978`).  On every candidate whose extreme ALREADY offers >= $1,000 of
    reach the clip BINDS, ext collapses to exactly 0.0, and the true reach is
    unrecoverable — it could be $1,000 or $10,000.  Reading B then classified
    all of them REVERSION (`ext <= $450`) and `np.isfinite` waved them through,
    so the DiD tested its breakout claim with the most extended candidates in
    the population sitting in the opposite arm, indistinguishable from
    candidates whose extreme offers $600.

    The clip is upstream and load-bearing for other consumers, so it is not
    unclipped here.  Instead the saturated rows are IDENTIFIED and given their
    own bucket: they carry no usable reading-B contrast and are excluded from
    the DiD rather than folded into REVERSION.  The count is published.
    """
    ext = D["ext_needed_usd"].astype(np.float64)
    fin = np.isfinite(ext)
    saturated = fin & (ext <= 0.0)
    return np.where(fin, 1000.0 - ext, np.nan), saturated


REACH_BREAKOUT_MAX_USD = 1000.0 - EXT_BREAKOUT_MIN_USD   # $550 of reach


def breakout_masks(D, reading):
    """(breakout, reversion) boolean masks for one direction reading.

    Reading B's third state — EXT_SATURATED — is neither, so it falls into the
    `~(brk | rev)` bucket that `did_rows` already drops from the contrast and
    `interaction_rows` already reports separately (R111).
    """
    if reading == "A_extension_side":
        es = D["ext_side"]
        return (es != 0) & (D["side"] == es), (es != 0) & (D["side"] == -es)
    reach, sat = reach_usd(D)
    ok = np.isfinite(reach) & ~sat
    return (ok & (reach < REACH_BREAKOUT_MAX_USD),
            ok & (reach >= REACH_BREAKOUT_MAX_USD))


def ext_saturated(D):
    _reach, sat = reach_usd(D)
    return sat


def clip_binding_frac(D):
    """(fraction of finite-ext candidates on which the zero-clip BINDS, n).

    R111's blast radius as a number in the receipt rather than an assertion in
    a comment."""
    ext = D["ext_needed_usd"].astype(np.float64)
    fin = np.isfinite(ext)
    return (float((ext[fin] <= 0.0).mean()) if fin.any() else float("nan"),
            int(fin.sum()))


def interaction_rows(D, flag):
    rows = []
    era_sel = [(n, e) for n, e in P1.era_selectors(D)
               if n in ("FIT", "FIT_EX_FITTING", "GATE_%dH1" % GATE_YEAR)]
    assets = [("ALL", np.ones(flag.size, dtype=bool))]
    assets += [(a, D["asset"] == a) for a in MC.ASSET_ORDER]
    sat = ext_saturated(D)
    for reading in DIRECTION_READINGS:
        brk, rev = breakout_masks(D, reading)
        # R111: the reading-B rows on which pattern_lib's zero-clip BINDS get
        # their own bucket instead of being folded into REVERSION.
        if reading == "B_ext_needed":
            buckets = (("BREAKOUT", brk), ("REVERSION", rev),
                       ("EXT_SATURATED", sat),
                       ("NO_DIRECTION", ~(brk | rev | sat)))
        else:
            buckets = (("BREAKOUT", brk), ("REVERSION", rev),
                       ("NO_DIRECTION", ~(brk | rev)))
        for aname, asel in assets:
            for ename, esel in era_sel:
                base = asel & esel
                if not base.any():
                    continue
                nsess = len(set(D["cluster"][base].tolist()))
                for fname, fsel in (("FLAGGED", flag), ("UNFLAGGED", ~flag)):
                    for dname, dsel in buckets:
                        m = base & fsel & dsel
                        if not m.any():
                            continue
                        nsess = len(set(D["cluster"][m].tolist()))
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
    era_sel = [(n, e) for n, e in P1.era_selectors(D)
               if n in ("FIT", "FIT_EX_FITTING", "GATE_%dH1" % GATE_YEAR)]
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
                        nsess = len(set(D["cluster"][m].tolist()))
                        st = P1._stats(D["cert_close"][m], D["cert_peak"][m],
                                       D["winner"][m], nsess)
                        rows.append([wname, aname, ename, alab, sname,
                                     st["n_candidates"], nsess,
                                     st["mean_close"], st["cond_close"],
                                     st["posfrac_close"], st["mean_peak"],
                                     st["n_winners"], st["winner_frac"]])
    return rows


# ------------------------------------------------------------ mirror law ----
RATIO_BOOT_SEED = 20260902                # distinct from p001's and p025's


def mirror_rows_batch2(D, flag21, flag22, rows):
    """R112 — the two DIRECTION claims in this batch, each against its own
    SIGN-FLIPPED twin, compared WITHIN each session.

    Neither had a mirror arm.  P021's claim ("on EXPANSION-flagged candidates
    BREAKOUT beats REVERSION; on unflagged candidates the ordering reverses")
    was tested by a POOLED difference-in-differences with no per-session
    component and no sign test.  P022's `p022_direction_rows` compares ALIGNED
    against OPPOSED — a mirror pair BY CONSTRUCTION — on pooled means only, so
    the one table in the file that already held a mirror never ran the test.

    Both are now paired on the session and decided by `m2_common.mirror_paired`,
    which refuses (NO_TEST) below its power floor instead of scoring an
    unpowered cell as a negative.
    """
    for reading in DIRECTION_READINGS:
        brk, rev = breakout_masks(D, reading)
        # the claim INSIDE the flagged pool: breakout beats reversion
        P1.mirror_rows(D, flag21 & brk, flag21 & rev,
                       "P021_%s" % reading, "FLAGGED_BREAKOUT",
                       "FLAGGED_REVERSION", rows)
        # and the asserted REVERSAL outside it
        P1.mirror_rows(D, (~flag21) & rev, (~flag21) & brk,
                       "P021_%s" % reading, "UNFLAGGED_REVERSION",
                       "UNFLAGGED_BREAKOUT", rows)
    side = D["side"].astype(np.float64)
    for wname, sgn in (("5m", np.sign(D["f5m_sflow"].astype(np.float64))),
                       ("30m", np.sign(D["f30m_sflow"].astype(np.float64))),
                       ("phase", np.sign(D["fph_sflow"].astype(np.float64))),
                       ("event_anchored",
                        np.where(D["event_in_phase"],
                                 np.sign(D["fev_sflow"].astype(np.float64)),
                                 0.0))):
        al = flag22 & (sgn != 0) & (side == sgn)
        op = flag22 & (sgn != 0) & (side == -sgn)
        P1.mirror_rows(D, al, op, "P022_%s" % wname, "ALIGNED", "OPPOSED",
                       rows)
    return rows


# ----------------------------------------------------------------- grading --
def grade(res, cen, promo, era="FIT_EX_FITTING"):
    """(verdict, evidence) in the CC-M2-9.1 vocabulary.

    R106: WINNER CONCENTRATOR used to be a BARE RATIO — `fF[16]/fN[16] >= 1.25`
    with no SE, no CI, no cluster adjustment and NO MINIMUM-N GUARD on the
    numerator — and it was the ONLY route by which P020/P021/P022 reached the
    feature-candidate set.  It now requires, all four: the ratio clears the
    declared bar; its SESSION-CLUSTERED bootstrap interval EXCLUDES 1.0; it
    survives Holm over the declared PROMOTION family; and the firing set
    cleared the n floors.  Anything short of that is NO_TEST, not a promotion.

    R114: the ratios are read on FIT_EX_FITTING — FIT is in-sample with respect
    to the thresholds this file declares.
    """
    fF = cen.get(("ALL", "FIT", "ALL", "ALL", "FIRE"))
    fN = cen.get(("ALL", "FIT", "ALL", "ALL", "NOFIRE"))
    rb = [x for x in res["robust"]
          if x[1] == "ALL" and x[2] == "FIT" and x[3] == "cert_close"]
    if fF is None or fN is None or fF[7] == 0:
        return "NULL_never_fires", {}
    beta = rb[0][7] if rb else float("nan")
    holm = rb[0][19] if rb and len(rb[0]) > 19 else "NO_TEST"
    mine = [r for r in promo if r[0] == res["pid"] and r[1] == era]
    ev = {"beta_close": beta, "holm": holm, "promotion_era": era}
    for r in mine:
        ev[r[2]] = r[3]
        ev[r[2] + "_ci"] = (r[4], r[5])
        ev[r[2] + "_verdict"] = r[9]
        ev[r[2] + "_holm"] = r[10]
    sig = (holm == "HOLM_SIGNIFICANT")
    if sig and np.isfinite(beta) and beta > 0:
        return "ENTRY RULE (adoption-metric edge, Holm-significant)", ev
    if sig and np.isfinite(beta) and beta < 0:
        return "VETO RULE (flagged pool is worth refusing, Holm-significant)", ev
    hits = P1.promotion_verdict(promo, res["pid"], era=era,
                                minimum=CONCENTRATOR_MIN)
    if hits:
        return ("WINNER CONCENTRATOR (feature candidate set only — CC-M2-9.1 "
                "disposition; ratio >= %.2f with a session-clustered interval "
                "excluding 1.0, Holm-significant in the promotion family, "
                "above the n floor)" % CONCENTRATOR_MIN), ev
    untested = [r for r in mine if r[9] != "TESTED"]
    if untested and not [r for r in mine if r[9] == "TESTED"]:
        return ("NO_TEST (promotion ratios below the n floor: %d fires over %d "
                "sessions, floors %d/%d)"
                % (untested[0][6], untested[0][7], P1.PROMOTE_MIN_FIRES,
                   P1.PROMOTE_MIN_CLUSTERS)), ev
    return "NULL (no adoption edge, no inferentially supported concentration)", ev


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
    A("MULTIPLICITY: THREE DECLARED FAMILIES, corrected separately and named "
      "on their own tables (R107). (1) GEE — every GEE test of all three "
      "patterns AND both P021 interaction readings, %d tests. (2) MIRROR — "
      "BATCH2_MIRROR.tsv, %d tested rows. (3) PROMOTION — "
      "BATCH2_PROMOTION.tsv, %d tested rows. A raw p<0.05 that fails Holm is "
      "noise and the tables say which is which."
      % (len([r for r in res["robust_all"] if np.isfinite(r[12])]),
         len([r for r in res["mirror"] if r[20] == "TESTED"]),
         len([r for r in res["promotion"] if r[9] == "TESTED"])))
    A("")
    A("D-058 PRE-EXAM HOLDOUT (R105, closed). **%d holdout sessions (>= %d) "
      "were QUARANTINED out of this census.** The previous run pooled 2025-H2 "
      "with H1 through `concentration_rows`, `interaction_rows` and "
      "`p022_direction_rows`. The GATE echo is named `GATE_%dH1` here because "
      "it is a half-year."
      % (int(D.get("n_quarantined_holdout", 0)), MC.HOLDOUT_FROM_D8,
         GATE_YEAR))
    A("")
    A("IN-SAMPLE OPTIMISM (R114). Every threshold here was fitted on E1 study "
      "sessions inside FIT. Every table carries a `FIT_EX_FITTING` era that "
      "drops the %d threshold-fitting sessions, and the named-case table at "
      "the end is a REPRODUCTION CHECK, not corroboration."
      % len(P1.THRESHOLD_FITTING_SESSIONS))
    A("")
    A("READING B's CLIP (R111, closed). `ext_needed_usd` is clipped at zero "
      "upstream, so every candidate whose extreme already offers >= $1,000 of "
      "reach collapses to exactly 0.0 and used to be classified REVERSION — "
      "the DiD tested its breakout claim with the most extended candidates in "
      "the population sitting in the opposite arm. The clip BINDS on %s%% of "
      "the %d candidates with a finite ext_needed; those rows now sit in an "
      "EXT_SATURATED bucket and are EXCLUDED from the DiD contrast."
      % (_fmt(100.0 * clip_binding_frac(D)[0], 2), clip_binding_frac(D)[1]))
    A("")

    A("## HEADLINE VERDICTS (CC-M2-9.1 vocabulary)")
    A("")
    for pid, name, _terms, _fn in PATTERNS:
        r = res[pid]
        cen = r["cen"]
        fF = cen.get(("ALL", "FIT", "ALL", "ALL", "FIRE"))
        fN = cen.get(("ALL", "FIT", "ALL", "ALL", "NOFIRE"))
        verdict, ev = grade(r, cen, res["promotion"])
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
        if x[2] != "ALL" or x[1] not in ("FIT", "GATE_%dH1" % GATE_YEAR):
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
    for y in [str(v) for v in FIT_YEARS] + ["GATE_%dH1" % GATE_YEAR]:
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
        for y in [str(v) for v in FIT_YEARS] + ["GATE_%dH1" % GATE_YEAR]:
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

    A("## Named-case REPRODUCTION CHECK (the E1D2 cases these patterns were "
      "written from)")
    A("")
    A("R114: these sessions are inside FIT and are among the sessions the "
      "thresholds were fitted on. This is a reproduction check — 'do the "
      "detectors still fire on the cases they were written from?' — and is "
      "NOT evidence. Read the FIT_EX_FITTING era rows for that.")
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
    A("## MIRROR LAW (R112) — direction claims against their sign-flipped twins")
    A("")
    A("P021's claim and P022's ALIGNED-vs-OPPOSED pair are DIRECTION claims. "
      "P021 was tested by a pooled difference-in-differences with no "
      "per-session component and no sign test; P022's own direction table "
      "compares a mirror pair BY CONSTRUCTION and reported pooled means only. "
      "Both are now paired WITHIN the session and decided by "
      "`m2_common.mirror_paired`.")
    A("")
    A("| claim | detector | mirror | era | metric | sessions | mean delta $ | "
      "t | p | sign p | MDE(80%) | verdict | Holm |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for x in res["mirror"]:
        if x[3] != "ALL" or x[4] != "FIT" or x[5] != "cert_close":
            continue
        A("| %s | %s | %s | %s | %s | %d | %s | %s | %s | %s | %s | %s | %s |"
          % (x[0], x[1], x[2], x[4], x[5], x[6], _fmt(x[9]), _fmt(x[12], 2),
             _fmt(x[13], 5), _fmt(x[17], 5), _fmt(x[18]), x[20], x[24]))
    A("")
    A("## PROMOTION INTERVALS (R106) — no bare ratios")
    A("")
    A("`CONCENTRATOR_MIN = %.2f` used to be graded off a bare ratio of two "
      "noisy means with no SE, no CI, no cluster adjustment and no minimum-n "
      "guard on the numerator — the only route by which these patterns reached "
      "the feature-candidate set. Each ratio now carries a %d-replicate "
      "session-clustered bootstrap interval and refuses below %d fires "
      "spanning %d sessions."
      % (CONCENTRATOR_MIN, P1.RATIO_BOOT_REPS, P1.PROMOTE_MIN_FIRES,
         P1.PROMOTE_MIN_CLUSTERS))
    A("")
    A("| pattern | era | statistic | ratio | 95% CI | fires | sessions | "
      "excludes 1.0 | verdict | Holm |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for x in res["promotion"]:
        A("| %s | %s | %s | %s | [%s, %s] | %d | %d | %s | %s | %s |"
          % (x[0], x[1], x[2], _fmt(x[3], 3), _fmt(x[4], 3), _fmt(x[5], 3),
             x[6], x[7], "YES" if x[8] else "no", x[9], x[10]))
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
def build(workers=4, limit_sessions=None, out_dir=None):
    t0 = time.time()
    MC.verify_spec(force=True)
    OUT = out_dir or OUT_DIR
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    D = scan(workers=workers, limit_sessions=limit_sessions)
    res = {}
    census, terms, destr = [], [], []
    robust_nc = []                        # un-Holmed; one family for the batch
    promo, mirror = [], []                # two FURTHER declared families
    for pid, _name, tnames, _fn in PATTERNS:
        T = P1.unbits(D["terms_" + pid], len(tnames))
        fire = np.all(T, axis=1)
        rows_c = P1.census_rows(D, fire, pid)
        rows_t = P1.term_rows(D, T, pid, tnames)
        # P020's single term IS the detector, so its leave-one-out marginals
        # are the whole population; they are still emitted (cheap, and the
        # TERM_ALONE row is the census row) but the destruction test is the
        # informative one.
        # R116: the DECLARED seed is the seed actually USED.  This file
        # declared DESTRUCTION_SEED = 20260815, interpolated it into PARAMS and
        # hashed it into params_hash, while P1.destruction_rows hardcoded
        # P1.DESTRUCTION_SEED — so the receipt asserted a provenance that did
        # not match the computation and re-running with the declared seed
        # reproduced different numbers under the same hash.  The seed is passed
        # in, and P1.destruction_seed additionally keys the stream on the
        # READING so p020's three patterns no longer share one draw with each
        # other, with p001's arms, or with p025's nine readings.
        rows_d = P1.destruction_rows(D, T, pid, tnames, seed=DESTRUCTION_SEED)
        rows_r = P1.robust_rows(D, fire, pid, holm=False)
        P1.promotion_rows(D, fire, pid, promo, seed=RATIO_BOOT_SEED)
        res[pid] = {"pid": pid, "fire": fire, "terms": rows_t, "destr": rows_d,
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
    mirror_rows_batch2(D, flag21, res["P022"]["fire"], mirror)
    # ONE Holm family over the whole batch (CC-M2-10.2's "Holm over the batch")
    P1._holm(robust_nc)
    P1.holm_mirror(mirror)
    P1.holm_promotion(promo)
    res["robust_all"] = robust_nc
    res["mirror"] = mirror
    res["promotion"] = promo
    res["did"] = [r for r in robust_nc if str(r[0]).startswith("P021_DID_")]
    for pid, _n, _t, _f in PATTERNS:
        res[pid]["robust"] = [r for r in robust_nc if r[0] == pid]

    phash = MC.params_hash(PARAMS)
    extra = ["CC-M2-10.2 census batch 2 — P020/P021/P022, strictly causal "
             "detectors over the frozen v3 roster",
             "BOTH CC-M1-8 certificate readings are reported on every row",
             "Holm-Bonferroni is applied over the WHOLE batch, not per pattern"]
    MC.write_tsv(os.path.join(OUT, "BATCH2_CENSUS.tsv"), SECTION, phash,
                 list(P1.CENSUS_COLUMNS), census, extra=extra)
    MC.write_tsv(os.path.join(OUT, "BATCH2_TERMS.tsv"), SECTION, phash,
                 list(P1.TERM_COLUMNS), terms, extra=extra)
    MC.write_tsv(os.path.join(OUT, "BATCH2_DESTRUCTION.tsv"), SECTION,
                 phash, list(P1.DESTRUCTION_COLUMNS), destr, extra=extra)
    MC.write_tsv(os.path.join(OUT, "BATCH2_ROBUST.tsv"), SECTION, phash,
                 list(P1.ROBUST_COLUMNS), robust_nc, extra=extra)
    MC.write_tsv(os.path.join(OUT, "P020_CONCENTRATION.tsv"), SECTION,
                 phash, list(CONC_COLUMNS), res["conc"],
                 extra=["conc_ratio = winner share / candidate share; 1.00 "
                        "means the phase holds winners in proportion to the "
                        "candidates generated inside it"])
    MC.write_tsv(os.path.join(OUT, "P021_INTERACTION.tsv"), SECTION, phash,
                 list(INTER_COLUMNS), res["inter"],
                 extra=["the load-bearing 2x2: EXPANSION flag x trade "
                        "direction, two readings of direction"])
    MC.write_tsv(os.path.join(OUT, "P022_DIRECTION.tsv"), SECTION, phash,
                 list(DIR_COLUMNS), res["dir22"],
                 extra=["FLAGGED candidates only: is the flag a veto or a "
                        "compass? ALIGNED = the trade side agrees with that "
                        "window's flow sign",
                        "these are POOLED means and decide nothing on their "
                        "own — ALIGNED vs OPPOSED is a mirror pair by "
                        "construction and the TEST is in BATCH2_MIRROR.tsv "
                        "(R112)"])
    MC.write_tsv(os.path.join(OUT, "BATCH2_MIRROR.tsv"), SECTION, phash,
                 list(P1.MIRROR_COLUMNS), res["mirror"],
                 extra=["R112 MIRROR LAW: every direction claim in this batch "
                        "against its own SIGN-FLIPPED twin, paired WITHIN the "
                        "session and decided by m2_common.mirror_paired",
                        "verdict=NO_TEST below the power floor — an unpowered "
                        "cell is never scored as a negative",
                        "this table is its OWN declared Holm family"])
    MC.write_tsv(os.path.join(OUT, "BATCH2_PROMOTION.tsv"), SECTION, phash,
                 list(P1.PROMOTION_COLUMNS), res["promotion"],
                 extra=["R106: WINNER CONCENTRATOR is no longer a bare ratio. "
                        "Each ratio carries a session-clustered bootstrap "
                        "interval, an n floor on the NUMERATOR and Holm "
                        "membership in this table's own declared family",
                        "read FIT_EX_FITTING — FIT is in-sample with respect "
                        "to the thresholds this file declares (R114)"])
    pins = MC.pins_moved()
    el = time.time() - t0
    MC.write_text(os.path.join(OUT, "P020_P022_CENSUS_REPORT.md"),
                  report(D, res, el, pins))
    MC.write_json(os.path.join(OUT, "p020_census.receipt.json"),
                  {"env": MC.env_receipt(PARAMS),
                   "n_candidates": int(D["dec_sec"].size),
                   "n_sessions": int(D["n_sessions_total"]),
                   "holdout_from_d8": int(MC.HOLDOUT_FROM_D8),
                   "n_holdout_sessions_quarantined":
                       int(D.get("n_quarantined_holdout", 0)),
                   "ext_clip_binding_frac": clip_binding_frac(D)[0],
                   "n_ext_finite": clip_binding_frac(D)[1],
                   "holm_families": {
                       "GEE": int(len([r for r in robust_nc
                                       if np.isfinite(r[12])])),
                       "MIRROR": int(len([r for r in mirror
                                          if r[20] == "TESTED"])),
                       "PROMOTION": int(len([r for r in promo
                                             if r[9] == "TESTED"]))},
                   "destruction_seed_declared": DESTRUCTION_SEED,
                   "n_fires": {p[0]: res[p[0]]["n_fires"] for p in PATTERNS},
                   "n_gee_tests": int(len([r for r in robust_nc
                                           if np.isfinite(r[12])])),
                   "elapsed_sec": el, "pins_moved": pins, "out_dir": OUT})
    MC.hb("batch2 census: %s, %.1fs"
          % (", ".join("%s=%d" % (p[0], res[p[0]]["n_fires"])
                       for p in PATTERNS), el))
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--limit-sessions", type=int, default=None)
    # A --limit-sessions SMOKE RUN must never overwrite the committed census.
    # The default out dir is refused whenever the population is truncated;
    # --out-dir is how a development run says where its scratch goes.
    p.add_argument("--out-dir", default=None)
    a = p.parse_args()
    if a.workers > 4:
        raise SystemExit("workers capped at 4 (a reader lane is live)")
    if a.limit_sessions and not a.out_dir:
        raise SystemExit("--limit-sessions is a SMOKE RUN and must be given "
                         "--out-dir: it would otherwise overwrite the "
                         "committed census with a truncated population")
    build(workers=a.workers, limit_sessions=a.limit_sessions,
          out_dir=a.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
