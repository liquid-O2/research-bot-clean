#!/usr/bin/python3
"""PORT M2 — THE SESSION-SIDE STATE PROBE (CC-M2-13.3).

CC-M2-13.3 (BINDING): "winners concentrate on ONE side per session (4/4 days);
candidate-level direction has failed every test => SIDE IS A SESSION-STATE
VARIABLE.  Ordered: the SESSION-SIDE STATE probe — (a) ceiling census: given
the oracle day-side, what capture does the reader's refusal core + P025
achieve? (b) causal estimators of day-side (first-k-outcomes sign, cumulative
session return, overnight drift, release-day interaction), mirror-law-tested."

THE TWO HALVES

(a) THE CEILING CENSUS.  Every FIT session of all three assets is replayed
    under the ONE-POSITION scheduler with the reader's INHERITED FIVE-TERM
    REFUSAL CORE (E1D4-F3: the five terms that came from prior days, which
    would have made day 4 a +$4,277.50 day at capture 0.501 — the two terms
    fitted on the round's own pool are the ones excluded):

      T1 LIVE BOOK    S8 60s n >= 5 AND 60s vol >= 10        (P004 inverted)
      T2 RUNWAY       runway to the BINDING (phase-close) exit >= 12,000s
                      (P025 — 230/230 winners over four day-complete sessions)
      T3 FRESH EXTREME  trade-side phase extreme <= 3,600s old
      T4 ABSORBED AGGRESSION  S8 5m sflow OPPOSED to the trade at >= 5% of its
                      own 5m volume (P007 as an entry object)
      T5 MAGNITUDE    5m vol >= 200 AND (5m vol >= 500 OR >= 8% of phase vol)

    crossed with WHO CHOOSES THE SIDE:

      CORE                 the core alone, both sides — what the reader has
      CORE_ORACLE          the core, restricted to the ORACLE DAY-SIDE
      CORE_ORACLE_MIRROR   the core, restricted to the WRONG side
      ORACLE_ONLY          the oracle side with NO core — side knowledge alone
      ORACLE_ONLY_MIRROR   its mirror

    The ORACLE DAY-SIDE is the side of the session's D-021 winner majority
    (ties and winnerless sessions carry NO side and are reported separately).
    It is a HINDSIGHT object by construction: the gap between CORE and
    CORE_ORACLE is exactly what a perfect day-side estimator would be worth,
    which is the "ceiling" the order asks for.

(b) CAUSAL DAY-SIDE ESTIMATORS, every one of them strictly causal:

      E1 FIRST_OUTCOME   the sign of the session's FIRST RESOLVED candidate:
                         among candidates whose phase-close exit second is
                         strictly before this decision second, take the one
                         that resolved EARLIEST and read side * sign(cert).
                         A paper trade the session has already finished.
      E2 SESSION_RETURN  sign(mid at the running phase's open - mid at the
                         session open) — the cumulative session return at each
                         phase open, as the order words it.
      E3 OVERNIGHT       sign(session-open mid - the PREVIOUS session's close),
                         the prior close read from the m0 session receipt.
      each x RELEASE_DAY the interaction the order names: every table is also
                         split by whether a SCHEDULED release lands inside the
                         session (pattern_lib's D-057-lagged calendar).

    THE MIRROR LAW (CC-M2-13.1, program-wide): a direction claim must beat its
    MIRROR on every session, not merely be positive on every session.  So each
    estimator is scored against the arm that takes the OPPOSITE side on the
    same rows, per session, and the report carries: sessions won / tied / LOST
    to the mirror, the per-session mean delta with a session-clustered SE
    (the session IS the cluster, so the SE over sessions is the cluster-robust
    one), Holm-corrected over the estimator family, and the fraction of
    sessions where the estimator's side equals the oracle's.

VALUE, CAPTURE, PRECISION (panel_score's definitions, reused verbatim in form)
  * one-position chronological replay: a TAKE is seated iff its decision second
    is strictly after the open position's exit second, else FORFEITED;
  * capture = realised / the session's one-position DP ceiling over EVERY
    candidate (c_c_roster.dp_schedule, the same call panel_score makes);
  * precision = D-021 winners among SEATED takes.
  Both CC-M1-8 readings are computed; the walled PHASE-CLOSE reading is the
  adoption metric and the peak-exit companion is reported beside it.

OUTPUT (D-018: bulk under artifacts/cache/)
  artifacts/cache/port/m2/side_probe/SIDE_PROBE_REPORT.md
  artifacts/cache/port/m2/side_probe/{ARMS,SESSIONS,MIRROR,AGREEMENT}.tsv
  artifacts/cache/port/m2/side_probe/side_probe.receipt.json

Run:  lab/run.sh port-m2-sideprobe -- /usr/bin/python3 engine/port_m2/side_probe.py
"""
import argparse
import json
import math
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
import c_c_roster as CC                   # noqa: E402
import p001_census as P1                  # noqa: E402

SECTION = "CC-M2-13.3 SESSION-SIDE STATE probe (ceiling census + causal "
SECTION += "day-side estimators, mirror-law tested)"
OUT_DIR = MC.out_path("side_probe", "_")[:-1]

FIT_YEARS = P1.FIT_YEARS
GATE_YEAR = P1.GATE_YEAR

# --- the inherited five-term refusal core (E1D4-F3, verbatim) --------------
LIVE_N_MIN = 5
LIVE_VOL_MIN = 10
RUNWAY_MIN_SEC = 12000
EXTREME_MAX_AGE_SEC = 3600
SFLOW_MIN_FRAC = 0.05
VOL_MIN = 200
VOL_ABS = 500
VOL_REL = 0.08

ESTIMATORS = ("E1_FIRST_OUTCOME", "E2_SESSION_RETURN", "E3_OVERNIGHT")
ARMS = (("CORE", None), ("CORE_ORACLE", "ORACLE"),
        ("CORE_ORACLE_MIRROR", "ORACLE_MIRROR"),
        ("ORACLE_ONLY", "ORACLE_NOCORE"),
        ("ORACLE_ONLY_MIRROR", "ORACLE_MIRROR_NOCORE"))

PARAMS = {
    "spec_section": SECTION,
    "order": "CC-M2-13.3 — session-side state probe",
    "core": "the five INHERITED terms of E1D4-F3: T1 60s n>=%d and vol>=%d; "
            "T2 runway to the binding phase-close exit >= %ds; T3 trade-side "
            "phase extreme <= %ds old; T4 5m sflow OPPOSED at >= %.2f of 5m "
            "volume; T5 5m vol >= %d AND (>= %d OR >= %.2f x phase volume)"
            % (LIVE_N_MIN, LIVE_VOL_MIN, RUNWAY_MIN_SEC, EXTREME_MAX_AGE_SEC,
               SFLOW_MIN_FRAC, VOL_MIN, VOL_ABS, VOL_REL),
    "oracle_day_side": "the side of the session's D-021 winner majority; 0 "
                       "when there are no winners or the count ties",
    "estimators": {
        "E1_FIRST_OUTCOME": "side * sign(cert_close) of the candidate that "
                            "RESOLVED earliest strictly before this decision "
                            "second (exit_close_sec < dec_sec)",
        "E2_SESSION_RETURN": "sign(phase_open_mid - sess_open_mid)",
        "E3_OVERNIGHT": "sign(sess_open_mid - previous session's m0 receipt "
                        "close price)"},
    "release_day": "a SCHEDULED release (BLS + FOMC, D-057 SCHEDULE_EXEMPT) "
                   "lands inside the session before some decision second",
    "replay": "one position, chronological; a take whose decision second is "
              "not strictly after the open position's exit second is "
              "FORFEITED (panel_score.replay)",
    "capture": "realised / c_c_roster.dp_schedule ceiling over EVERY candidate "
               "of the session (panel_score.dp_ceiling)",
    "precision": "D-021 winners among SEATED takes",
    "mirror_law": "CC-M2-13.1 — an estimator must beat the arm that takes the "
                  "OPPOSITE side on the same rows on EVERY session; sessions "
                  "won/tied/lost are counted and the per-session mean delta "
                  "carries a session-clustered SE with Holm over the family",
    "population": "frozen v3 roster, FIT %s (primary) + %d GATE echo"
                  % (list(FIT_YEARS), GATE_YEAR),
    "frame": PL.PARAMS_FRAME,
    "frame_v2": PL.PARAMS_FRAME_V2,
}


# ------------------------------------------------------------ prior closes --
def prior_close_map(asset):
    """{d8: previous roster session's m0 close price} for one asset."""
    ds = PL.sessions(asset)
    out = {}
    prev = None
    for d in ds:
        if prev is not None:
            out[d] = prev
        p = os.path.join(MC.M0_ROOT, "sessions", asset, "%d.npz" % d)
        px = None
        if os.path.exists(p):
            z = np.load(p, allow_pickle=False)
            try:
                px = float(json.loads(str(z["meta_json"]))["Cl"])
            except Exception:              # noqa: BLE001 — missing = no drift
                px = None
            finally:
                z.close()
        prev = px
    return out


_PRIOR = {}


# ------------------------------------------------------------------- core ---
def core_mask(f):
    side = f["side"].astype(np.float64)
    t1 = (f["f60_n"] >= LIVE_N_MIN) & (f["f60_vol"] >= LIVE_VOL_MIN)
    t2 = f["runway_phase_sec"] >= RUNWAY_MIN_SEC
    age = f["extreme_age_sec"]
    t3 = (age >= 0) & (age <= EXTREME_MAX_AGE_SEC)
    s5 = np.sign(f["f5m_sflow"].astype(np.float64))
    frac = (np.abs(f["f5m_sflow"].astype(np.float64))
            / np.maximum(f["f5m_vol"].astype(np.float64), 1.0))
    t4 = (s5 != 0) & (s5 == -side) & (frac >= SFLOW_MIN_FRAC)
    v5 = f["f5m_vol"].astype(np.float64)
    t5 = (v5 >= VOL_MIN) & ((v5 >= VOL_ABS)
                            | (v5 >= VOL_REL * np.maximum(
                                f["fph_vol"].astype(np.float64), 1.0)))
    return t1 & t2 & t3 & t4 & t5


def first_outcome_side(f):
    """E1, vectorised: for each candidate, the sign-corrected side of the
    candidate that RESOLVED earliest strictly before its decision second."""
    dec = f["dec_sec"].astype(np.int64)
    ex = f["exit_close_sec"].astype(np.int64)
    side = f["side"].astype(np.int64)
    cert = f["cert_close_usd"].astype(np.float64)
    ok = ex >= 0
    order = np.argsort(np.where(ok, ex, 1 << 60), kind="stable")
    ex_s = ex[order]
    n_ok = int(ok.sum())
    out = np.zeros(dec.size, dtype=np.int64)
    if n_ok == 0:
        return out
    ex_s = ex_s[:n_ok]
    first_side = int(side[order[0]])
    first_sign = int(np.sign(cert[order[0]]))
    # the FIRST resolved candidate is the same for every decision second that
    # is strictly after its exit; earlier decisions have no resolved outcome.
    j = np.searchsorted(ex_s, dec, side="left")     # n resolved before dec
    have = j > 0
    out[have] = first_side * (first_sign if first_sign != 0 else 0)
    return out


def session_return_side(f):
    d = f["phase_open_mid"] - f["sess_open_mid"]
    return np.where(np.isfinite(d), np.sign(d), 0).astype(np.int64)


def overnight_side(f, prior_px):
    if prior_px is None or not np.isfinite(prior_px):
        return np.zeros(f["dec_sec"].size, dtype=np.int64)
    d = f["sess_open_mid"] - float(prior_px)
    return np.where(np.isfinite(d), np.sign(d), 0).astype(np.int64)


# ----------------------------------------------------------------- replay ---
def replay(dec, ex, cert, winner, take):
    """One-position chronological replay -> (n_takes, n_seated, realised,
    n_winner_seated, n_forfeited)."""
    idx = np.nonzero(take)[0]
    if not idx.size:
        return (0, 0, 0.0, 0, 0)
    idx = idx[np.argsort(dec[idx], kind="stable")]
    open_until = -1
    realised = 0.0
    n_seat = n_forf = n_win = 0
    for i in idx.tolist():
        if int(dec[i]) <= open_until:
            n_forf += 1
            continue
        realised += float(cert[i])
        open_until = int(ex[i])
        n_seat += 1
        n_win += int(bool(winner[i]))
    return (int(idx.size), n_seat, realised, n_win, n_forf)


def dp_ceiling(f, metric="close"):
    cert = (f["cert_close_usd"] if metric == "close" else f["cert_peak_usd"])
    ex = (f["exit_close_sec"] if metric == "close" else f["exit_peak_sec"])
    items = [(int(d), int(e), float(v), int(d), 0, i)
             for i, (d, e, v) in enumerate(zip(f["dec_sec"].tolist(),
                                               ex.tolist(), cert.tolist()))]
    total, chosen = CC.dp_schedule(items)
    return float(total), len(chosen)


# ------------------------------------------------------------- one session --
def _one(job):
    asset, d8 = job
    try:
        f = PL.frame(asset, int(d8), with_levels=False)
    except Exception as e:                # noqa: BLE001 — surfaced, not hidden
        return ("ERROR", asset, int(d8), repr(e)[:300])
    if f is None:
        return ("EMPTY", asset, int(d8), "")
    prior = _PRIOR.get(asset, {}).get(int(d8))
    core = core_mask(f)
    side = f["side"].astype(np.int64)
    win = f["winner"]
    n_l = int((win & (side > 0)).sum())
    n_s = int((win & (side < 0)).sum())
    oracle = 1 if n_l > n_s else (-1 if n_s > n_l else 0)
    est = {"E1_FIRST_OUTCOME": first_outcome_side(f),
           "E2_SESSION_RETURN": session_return_side(f),
           "E3_OVERNIGHT": overnight_side(f, prior)}
    dec = f["dec_sec"].astype(np.int64)
    ex = f["exit_close_sec"].astype(np.int64)
    ceil_close, n_dp = dp_ceiling(f, "close")
    ceil_peak, _ = dp_ceiling(f, "peak")

    arms = {}

    def add(name, take, metric="close"):
        cert = (f["cert_close_usd"] if metric == "close"
                else f["cert_peak_usd"])
        e = ex if metric == "close" else f["exit_peak_sec"].astype(np.int64)
        arms[name] = replay(dec, e, cert, win, take)

    add("CORE", core)
    add("CORE_PEAK", core, "peak")
    if oracle:
        add("CORE_ORACLE", core & (side == oracle))
        add("CORE_ORACLE_PEAK", core & (side == oracle), "peak")
        add("CORE_ORACLE_MIRROR", core & (side == -oracle))
        add("ORACLE_ONLY", side == oracle)
        add("ORACLE_ONLY_MIRROR", side == -oracle)
    for name, sd in est.items():
        add("CORE_%s" % name, core & (sd != 0) & (side == sd))
        add("CORE_%s_MIRROR" % name, core & (sd != 0) & (side == -sd))
    # session-level estimator side: the modal non-zero estimate of the day
    est_sess = {}
    for name, sd in est.items():
        nz = sd[sd != 0]
        est_sess[name] = (int(np.sign(nz.sum())) if nz.size else 0)

    release_day = bool(np.any(f["release_sec"] >= 0)
                       and np.any(f["event_in_phase"]))
    return ("OK", {"asset": asset, "d8": int(d8), "year": int(d8) // 10000,
                   "n_cand": int(dec.size), "n_winners": int(win.sum()),
                   "n_win_long": n_l, "n_win_short": n_s,
                   "oracle_side": oracle, "release_day": int(release_day),
                   "ceil_close": ceil_close, "ceil_peak": ceil_peak,
                   "dp_n": n_dp, "arms": arms, "est_sess": est_sess})


# ------------------------------------------------------------------- scan ---
def scan(years, workers=4, limit_sessions=None):
    jobs = []
    for a in MC.ASSET_ORDER:
        _PRIOR[a] = prior_close_map(a)
        ds = PL.sessions(a, years=set(years))
        if limit_sessions:
            ds = ds[:limit_sessions]
        jobs += [(a, d) for d in ds]
    jobs.sort()
    out, errs = [], []
    t0 = time.time()
    if workers and workers > 1:
        with mp.Pool(processes=int(workers),
                     initializer=_init_prior, initargs=(_PRIOR,)) as pool:
            for n, res in enumerate(pool.imap(_one, jobs, chunksize=8), 1):
                if res[0] == "OK":
                    out.append(res[1])
                elif res[0] == "ERROR":
                    errs.append(res[1:])
                if n % 250 == 0:
                    MC.hb("side probe %d/%d  %.1fs" % (n, len(jobs),
                                                       time.time() - t0))
    else:
        for j in jobs:
            res = _one(j)
            if res[0] == "OK":
                out.append(res[1])
            elif res[0] == "ERROR":
                errs.append(res[1:])
    if errs:
        raise RuntimeError("side probe: %d session(s) failed, first=%s"
                           % (len(errs), errs[0]))
    out.sort(key=lambda s: (s["asset"], s["d8"]))
    MC.hb("side probe: %d sessions, %.1fs" % (len(out), time.time() - t0))
    return out


def _init_prior(pr):
    """Pool initializer.  Under `fork` the child's `_PRIOR` IS the object that
    was passed in (copy-on-write aliasing), so a naive clear()+update() empties
    the very dict it is about to copy — the E3 estimator silently returned no
    side at all until this snapshot was taken first."""
    snap = dict(pr)
    _PRIOR.clear()
    _PRIOR.update(snap)


# -------------------------------------------------------------- aggregation -
ARM_COLUMNS = ("arm", "asset", "era", "release_day", "n_sessions", "n_takes",
               "n_seated", "n_forfeited", "realised_usd", "per_session_usd",
               "dp_ceiling_usd", "capture", "n_winner_seated", "precision",
               "takes_per_session")


def _era_of(y):
    return "FIT" if y in FIT_YEARS else ("GATE_%d" % GATE_YEAR if y == GATE_YEAR
                                         else "OTHER")


def arm_rows(S, arm_names):
    rows = []
    assets = [("ALL", None)] + [(a, a) for a in MC.ASSET_ORDER]
    for arm in arm_names:
        for aname, asel in assets:
            for ename in ("FIT", "GATE_%d" % GATE_YEAR):
                for rname, rsel in (("ALL", None), ("RELEASE", 1),
                                    ("NO_RELEASE", 0)):
                    sub = [s for s in S
                           if (asel is None or s["asset"] == asel)
                           and _era_of(s["year"]) == ename
                           and (rsel is None or s["release_day"] == rsel)
                           and arm in s["arms"]]
                    if not sub:
                        continue
                    nt = sum(s["arms"][arm][0] for s in sub)
                    ns = sum(s["arms"][arm][1] for s in sub)
                    rz = sum(s["arms"][arm][2] for s in sub)
                    nw = sum(s["arms"][arm][3] for s in sub)
                    nf = sum(s["arms"][arm][4] for s in sub)
                    ceil = sum(s["ceil_peak" if arm.endswith("_PEAK")
                                                else "ceil_close"]
                               for s in sub)
                    rows.append([arm, aname, ename, rname, len(sub), nt, ns,
                                 nf, rz, rz / len(sub),
                                 ceil, (rz / ceil) if ceil > 0 else float("nan"),
                                 nw, (float(nw) / ns) if ns else float("nan"),
                                 float(nt) / len(sub)])
    return rows


MIRROR_COLUMNS = ("estimator", "asset", "era", "release_day", "n_sessions",
                  "n_sessions_active", "sessions_won", "sessions_tied",
                  "sessions_lost", "mirror_law_holds", "mean_delta_usd",
                  "se_session", "z", "p", "est_usd", "mirror_usd",
                  "agree_with_oracle", "n_oracle_sessions",
                  "holm_rank", "holm_threshold", "holm_verdict")


def mirror_rows(S):
    rows = []
    assets = [("ALL", None)] + [(a, a) for a in MC.ASSET_ORDER]
    for est in ESTIMATORS:
        a_arm, m_arm = "CORE_%s" % est, "CORE_%s_MIRROR" % est
        for aname, asel in assets:
            for ename in ("FIT", "GATE_%d" % GATE_YEAR):
                for rname, rsel in (("ALL", None), ("RELEASE", 1),
                                    ("NO_RELEASE", 0)):
                    sub = [s for s in S
                           if (asel is None or s["asset"] == asel)
                           and _era_of(s["year"]) == ename
                           and (rsel is None or s["release_day"] == rsel)]
                    if not sub:
                        continue
                    d = np.array([s["arms"][a_arm][2] - s["arms"][m_arm][2]
                                  for s in sub])
                    act = np.array([(s["arms"][a_arm][0]
                                     + s["arms"][m_arm][0]) > 0 for s in sub])
                    won = int((d > 0).sum())
                    tie = int((d == 0).sum())
                    lost = int((d < 0).sum())
                    da = d[act] if act.any() else d
                    mu = float(da.mean()) if da.size else float("nan")
                    se = (float(da.std(ddof=1) / math.sqrt(da.size))
                          if da.size > 1 else float("nan"))
                    z = mu / se if (np.isfinite(se) and se > 0) else float("nan")
                    p = P1._p_two_sided(z)
                    ors = [s for s in sub if s["oracle_side"]]
                    agree = (float(np.mean([s["est_sess"][est]
                                            == s["oracle_side"] for s in ors]))
                             if ors else float("nan"))
                    rows.append([est, aname, ename, rname, len(sub),
                                 int(act.sum()), won, tie, lost,
                                 int(lost == 0 and won > 0), mu, se, z, p,
                                 float(sum(s["arms"][a_arm][2] for s in sub)),
                                 float(sum(s["arms"][m_arm][2] for s in sub)),
                                 agree, len(ors)])
    return rows


def _holm(rows, pcol, alpha=0.05):
    idx = [i for i, r in enumerate(rows) if np.isfinite(r[pcol])]
    order = sorted(idx, key=lambda i: rows[i][pcol])
    m = len(order)
    still = True
    for rank, i in enumerate(order, 1):
        thr = alpha / (m - rank + 1)
        ok = still and rows[i][pcol] <= thr
        still = still and ok
        rows[i] += [rank, thr,
                    "HOLM_SIGNIFICANT" if ok else "HOLM_NOT_SIGNIFICANT"]
    for i, r in enumerate(rows):
        if len(r) == len(MIRROR_COLUMNS) - 3:
            rows[i] += [0, float("nan"), "NO_TEST"]
    return rows


SESSION_COLUMNS = ("asset", "d8", "era", "n_candidates", "n_winners",
                   "n_win_long", "n_win_short", "oracle_side", "release_day",
                   "dp_ceiling_usd", "core_realised", "core_oracle_realised",
                   "core_oracle_mirror_realised", "e1_side", "e2_side",
                   "e3_side")


def session_rows(S):
    rows = []
    for s in S:
        rows.append([s["asset"], s["d8"], _era_of(s["year"]), s["n_cand"],
                     s["n_winners"], s["n_win_long"], s["n_win_short"],
                     s["oracle_side"], s["release_day"], s["ceil_close"],
                     s["arms"]["CORE"][2],
                     s["arms"].get("CORE_ORACLE", (0, 0, float("nan")))[2],
                     s["arms"].get("CORE_ORACLE_MIRROR",
                                   (0, 0, float("nan")))[2],
                     s["est_sess"]["E1_FIRST_OUTCOME"],
                     s["est_sess"]["E2_SESSION_RETURN"],
                     s["est_sess"]["E3_OVERNIGHT"]])
    return rows


# ------------------------------------------------------------------ report --
_fmt = P1._fmt


def _pick(rows, cols, **kw):
    idx = {c: i for i, c in enumerate(cols)}
    want = [(idx[k], v) for k, v in kw.items()]
    for r in rows:
        if all(r[i] == v for i, v in want):
            return r
    return None


def report(S, arms, mirror, elapsed, pins):
    L = []
    A = L.append
    fit = [s for s in S if _era_of(s["year"]) == "FIT"]
    n_or = len([s for s in fit if s["oracle_side"]])
    A("# THE SESSION-SIDE STATE PROBE (CC-M2-13.3)")
    A("")
    A("%d sessions (%d FIT), all three assets, frozen v3 roster. The refusal "
      "core is E1D4-F3's FIVE INHERITED TERMS; the side is supplied in turn by "
      "the oracle (hindsight), by nothing, and by three strictly causal "
      "estimators. Every arm is replayed one-position and scored against the "
      "session's DP ceiling." % (len(S), len(fit)))
    A("")
    A("Oracle day-side exists on %d of %d FIT sessions (%.1f%%); the rest have "
      "no D-021 winner or a tied count and carry no side."
      % (n_or, len(fit), 100.0 * n_or / max(len(fit), 1)))
    A("")

    A("## (a) THE CEILING CENSUS — who chooses the side (ALL assets, FIT)")
    A("")
    A("| arm | sessions | takes/session | seated | realised $ | $/session | "
      "capture | precision |")
    A("|---|---|---|---|---|---|---|---|")
    for arm in ("CORE", "CORE_ORACLE", "CORE_ORACLE_MIRROR", "ORACLE_ONLY",
                "ORACLE_ONLY_MIRROR", "CORE_E1_FIRST_OUTCOME",
                "CORE_E1_FIRST_OUTCOME_MIRROR", "CORE_E2_SESSION_RETURN",
                "CORE_E2_SESSION_RETURN_MIRROR", "CORE_E3_OVERNIGHT",
                "CORE_E3_OVERNIGHT_MIRROR"):
        r = _pick(arms, ARM_COLUMNS, arm=arm, asset="ALL", era="FIT",
                  release_day="ALL")
        if r is None:
            continue
        A("| %s | %d | %s | %d | %s | %s | %s | %s |"
          % (arm, r[4], _fmt(r[14], 2), r[6], _fmt(r[8], 0), _fmt(r[9], 1),
             _fmt(r[11], 4), _fmt(r[13], 4)))
    A("")
    A("PER ASSET (FIT), core vs core+oracle:")
    A("")
    A("| asset | arm | sessions | realised $ | $/session | capture | "
      "precision |")
    A("|---|---|---|---|---|---|---|")
    for aname in MC.ASSET_ORDER:
        for arm in ("CORE", "CORE_ORACLE"):
            r = _pick(arms, ARM_COLUMNS, arm=arm, asset=aname, era="FIT",
                      release_day="ALL")
            if r is None:
                continue
            A("| %s | %s | %d | %s | %s | %s | %s |"
              % (aname, arm, r[4], _fmt(r[8], 0), _fmt(r[9], 1),
                 _fmt(r[11], 4), _fmt(r[13], 4)))
    A("")
    A("GATE echo (eval-only) for the two headline arms:")
    A("")
    A("| arm | sessions | realised $ | $/session | capture | precision |")
    A("|---|---|---|---|---|---|")
    for arm in ("CORE", "CORE_ORACLE"):
        r = _pick(arms, ARM_COLUMNS, arm=arm, asset="ALL",
                  era="GATE_%d" % GATE_YEAR, release_day="ALL")
        if r is None:
            continue
        A("| %s | %d | %s | %s | %s | %s |"
          % (arm, r[4], _fmt(r[8], 0), _fmt(r[9], 1), _fmt(r[11], 4),
             _fmt(r[13], 4)))
    A("")

    A("## (b) THE CAUSAL ESTIMATORS UNDER THE MIRROR LAW (CC-M2-13.1)")
    A("")
    A("An estimator PASSES only if it beats its own mirror on EVERY session "
      "(`sessions_lost` = 0). `agree` is the fraction of oracle-bearing "
      "sessions where the estimator's session-level side equals the oracle's.")
    A("")
    A("| estimator | era | split | sessions active | won | tied | LOST | "
      "mirror law | mean delta $ | z | p | Holm | agree |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for est in ESTIMATORS:
        for ename in ("FIT", "GATE_%d" % GATE_YEAR):
            for rname in ("ALL", "RELEASE", "NO_RELEASE"):
                r = _pick(mirror, MIRROR_COLUMNS, estimator=est, asset="ALL",
                          era=ename, release_day=rname)
                if r is None:
                    continue
                A("| %s | %s | %s | %d | %d | %d | %d | %s | %s | %s | %s | "
                  "%s | %s |"
                  % (est, ename, rname, r[5], r[6], r[7], r[8],
                     "PASS" if r[9] else "**FAIL**", _fmt(r[10], 1),
                     _fmt(r[12], 2), _fmt(r[13], 6),
                     r[20] if len(r) > 20 else ".", _fmt(r[16], 3)))
    A("")

    A("## PROVENANCE")
    A("")
    A("* elapsed %.1fs; pins %s" % (elapsed, "HELD" if not pins else pins))
    A("* outputs: ARMS.tsv, SESSIONS.tsv, MIRROR.tsv")
    A("")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------- main ---
def build(workers=4, limit_sessions=None):
    t0 = time.time()
    MC.verify_spec(force=True)
    S = scan(FIT_YEARS + (GATE_YEAR,), workers=workers,
             limit_sessions=limit_sessions)
    arm_names = sorted({a for s in S for a in s["arms"]})
    arms = arm_rows(S, arm_names)
    mirror = _holm(mirror_rows(S), MIRROR_COLUMNS.index("p"))
    sess = session_rows(S)
    phash = MC.params_hash(PARAMS)
    extra = ["CC-M2-13.3 session-side state probe",
             "capture = realised / one-position DP ceiling over every "
             "candidate of the session",
             "the ORACLE arms are HINDSIGHT by construction — they are the "
             "concept's ceiling, never a rule"]
    MC.write_tsv(os.path.join(OUT_DIR, "ARMS.tsv"), SECTION, phash,
                 list(ARM_COLUMNS), arms, extra=extra)
    MC.write_tsv(os.path.join(OUT_DIR, "MIRROR.tsv"), SECTION, phash,
                 list(MIRROR_COLUMNS), mirror,
                 extra=extra + ["mirror_law_holds = 1 iff the estimator loses "
                                "to its mirror on ZERO sessions"])
    MC.write_tsv(os.path.join(OUT_DIR, "SESSIONS.tsv"), SECTION, phash,
                 list(SESSION_COLUMNS), sess, extra=extra)
    pins = MC.pins_moved()
    el = time.time() - t0
    MC.write_text(os.path.join(OUT_DIR, "SIDE_PROBE_REPORT.md"),
                  report(S, arms, mirror, el, pins))
    MC.write_json(os.path.join(OUT_DIR, "side_probe.receipt.json"),
                  {"env": MC.env_receipt(PARAMS), "n_sessions": len(S),
                   "n_candidates": int(sum(s["n_cand"] for s in S)),
                   "arms": arm_names, "elapsed_sec": el, "pins_moved": pins,
                   "out_dir": OUT_DIR})
    MC.hb("side probe done: %d sessions, %.1fs" % (len(S), el))
    return S, arms, mirror


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
