#!/usr/bin/python3
"""PORT M2 — THE NEWS-WINDOW COMPLIANCE CENSUS (D-077 + D-077-UPDATE, BINDING).

D-077 named the prop-firm rule; D-077-UPDATE (user, 2026-08-14) fixed it at
+/-10 MINUTES around every scheduled high-impact release, with AVOIDANCE the
preferred posture.  Two consequences drive this file:

  * the NEWS_WINDOW family AS CONSTRUCTED is the first 600s after a release
    (b10_generation_v3: G1 confirmations inside [release, release+600s), single
    15s delay), so EVERY candidate it emits lands inside the restricted window.
    It is struck for deployment by arithmetic, not by measurement.
  * what is still open, and what this census answers, is whether a REDEFINED
    POST-NEWS family — entries at or after +10min — carries any edge worth
    keeping, and whether the OPEN-DYNAMICS families are secretly news trades.

WHAT IS MEASURED (ROW grain: one v3-roster candidate = asset, session, decision
second, side; the compliance rule bites on the ENTRY, so every distance here is
`decision_sec` vs the release, never the confirmation second)

  1. MINUTE PROFILE of the NEWS_WINDOW family by minutes-since-release, in
     1-minute buckets [0,1) .. [19,20) and cumulative-from bands
     {>=1 .. >=8, >=10, >=12, >=15}, per asset and pooled, per era, on BOTH
     CC-M1-8 certificate readings (walled phase-close = adoption, walled
     peak-exit = companion), against three named non-news baselines.
  2. THE DEPLOYABILITY VERDICT: the class-card numbers (n/day, winner rate,
     conditional value) for the family UNCONSTRAINED, under the superseded
     [-2,+5] default, and under the binding >=+10min rule; beside them the
     REDEFINED POST-NEWS family (every roster candidate whose entry sits in
     [+10,+20)min after a release) measured the same way.
  3. THE OPENS CONFOUND CHECK: MICRO_OPEN and G1_FAST_OPEN profiled against
     THEIR OWN opens (the micro-open anchor / the phase open), plus the
     fraction of their fires inside the +/-10min restricted window and the
     fraction that would be HELD INTO one.
  4. THE SCORING HELPER: NEWS_DISTANCE.tsv — every roster candidate within
     15min either side of any scheduled release, with its signed distance, the
     inside-window flag (+/-10min) and the held-into-window flag, for the blind
     SCORING pass to join on.

CAUSALITY (the law this census can most easily break)
  The triggering release is the last scheduled release STRICTLY BEFORE the
  decision second — `pattern_lib.last_release_ts`, the same availability-lagged
  join S12 and the D10 event window use (CC-M2-1.2, D-006: one definition of
  the release set).  `next_release_ts` below is its exact complement (the first
  release AT OR AFTER the decision second) and exists ONLY to serve the
  pre-release / held-into-window flags, which are SCHEDULE facts: the release
  DATES are published months ahead, so knowing that a release is 4 minutes away
  is knowledge a trader has (D-057 SCHEDULE_EXEMPT).  Nothing about the
  release's CONTENT is read.  `_assert_causal` refuses any matched triggering
  release at or after its decision second — test_news.n01's mutant.

DISCIPLINE (restated so this file reads alone)
  * population = frozen v3 roster, every FIT session (2021-2024) + the
    GATE-2025 H1 echo; sessions with d8 >= 20250701 are NEVER LOADED.
  * BOTH CC-M1-8 readings on every value row; median beside mean.
  * INFERENCE: GEE, independence working correlation, Liang-Zeger sandwich
    clustered on SESSION (CR0 + Cameron-Miller CR1) + Kish ICC/DEFF/n_eff,
    ONE Holm-Bonferroni family over the whole sweep.
  * DESTRUCTION: the band indicator shuffled WITHIN ITS OWN SESSION, 40
    replicates, seeded; verdicts sign-aware.
  * REUSE: pattern_lib owns every field and the release calendar; the
    estimators are imported from batch4_census / episode_v2, never re-typed.

OUTPUT (D-018: bulk under artifacts/cache/)
  artifacts/cache/port/m2/news_compliance/
      NEWS_MINUTE_PROFILE.tsv   the minute + cumulative profile
      NEWS_BASELINES.tsv        the three non-news baselines, per asset/era
      NEWS_DEPLOYABILITY.tsv    the class-card readings, constrained vs not
      OPENS_PROFILE.tsv         MICRO_OPEN / G1_FAST_OPEN vs their own opens
      OPENS_CONFOUND.tsv        their release-proximity fractions
      NEWS_DISTANCE.tsv         the blind-scoring join helper
      NEWS_ROBUST.tsv           every GEE test, ONE Holm family
      NEWS_DESTRUCTION.tsv      mechanism destruction
      NEWS_COMPLIANCE_REPORT.md
      news_census.receipt.json

Run:  lab/run.sh port-m2-news -- /usr/bin/python3 engine/port_m2/news_census.py
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
import assemble as A                      # noqa: E402
import episode_v2 as EV                   # noqa: E402  (GEE sandwich, ICC)
import p001_census as P1                  # noqa: E402  (census machinery)
import batch4_census as B4                # noqa: E402  (estimators, Holm)
import family_discovery as FD             # noqa: E402  (the micro-open anchors)

SECTION = ("DISCRETIONARY_METHOD §4.2 name->count census — NEWS-WINDOW "
           "COMPLIANCE (D-077 + D-077-UPDATE: the +/-10min prop-firm rule)")
OUT_DIR = MC.out_path("news_compliance", "_")[:-1]

FIT_YEARS = P1.FIT_YEARS                  # (2021, 2022, 2023, 2024)
GATE_YEAR = P1.GATE_YEAR                  # 2025
HOLDOUT_FROM_D8 = B4.HOLDOUT_FROM_D8      # 20250701 (CC-M2-15.3)
ERAS = B4.ERAS                            # ("FIT", "GATE_2025H1")

# ---- the rule, as named constants (D-077-UPDATE; user-updatable) ------------
VETO_PRE_SEC = 600                        # 10 min BEFORE a release
VETO_POST_SEC = 600                       # 10 min AFTER a release
VETO_LEGACY = (-120, 300)                 # the SUPERSEDED D-077 default, kept
                                          # so the profile can be read under
                                          # both rules without a re-run
DEPLOY_MIN_SEC = VETO_POST_SEC            # a compliant entry is >= +10min

# ---- the profile grid ------------------------------------------------------
BUCKET_MIN = 20                           # buckets [0,1) .. [19,20)
BUCKET_SEC = 60
CUM_FROM_MIN = (1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15)
POST_NEWS_BAND = (600, 1200)              # the REDEFINED family's entry window
DIST_RADIUS_SEC = 900                     # NEWS_DISTANCE.tsv reach, +/-15min
FAR_BASELINE_SEC = 7200                   # "far from news" = >= 120min either
                                          # side of every scheduled release
MIN_N_GEE = 40                            # no inference claimed below this

BASELINES = ("SAME_DAY_FAR", "G1_UNIVERSE_FAR", "ALL_FAR",
             "SAME_DAY_SLOT_FAR")
PRIMARY_BASELINE = "SAME_DAY_FAR"
SLOT_BASELINE = "SAME_DAY_SLOT_FAR"

NEWS_BIT = MC.FAM_BIT["NEWS_WINDOW"]
MICRO_BIT = MC.FAM_BIT["MICRO_OPEN"]
FASTOPEN_BIT = MC.FAM_BIT["G1_FAST_OPEN"]
G1UNIV_BITS = MC.FAM_BIT["G1"] | MC.FAM_BIT["G1_FINE"] | FASTOPEN_BIT

DESTRUCTION_REPS = 40
DESTRUCTION_SEED = 20260814

PARAMS = {
    "spec_section": SECTION,
    "directive": "D-077 (prop-firm news rule) + D-077-UPDATE (+/-10min, "
                 "avoidance preferred, family struck for deployment)",
    "restricted_window_sec": [-VETO_PRE_SEC, VETO_POST_SEC],
    "restricted_window_superseded_sec": list(VETO_LEGACY),
    "compliant_entry": "minutes_since_release >= %d (a candidate is deployable "
                       "only if its ENTRY sits at or after this and it is not "
                       "within %ds BEFORE the next release)"
                       % (DEPLOY_MIN_SEC // 60, VETO_PRE_SEC),
    "grain": "ROW = one v3-roster candidate (asset, session, decision second, "
             "side); the rule constrains the ENTRY, so every distance is "
             "decision_sec vs the release second",
    "release_join": "pattern_lib.last_release_ts — the last SCHEDULED BLS/FOMC "
                    "release STRICTLY BEFORE decision_ts, the availability-"
                    "lagged join S12's `last_scheduled` and the D10 event "
                    "window already use (CC-M2-1.2, D-006). The calendar is "
                    "SCHEDULE_EXEMPT under D-057 (release DATES publish months "
                    "ahead); no release CONTENT is read anywhere.",
    "next_release_join": "the exact complement — first scheduled release AT OR "
                         "AFTER decision_ts — used ONLY for the pre-release "
                         "and held-into-window flags, both schedule facts",
    "buckets": "1-minute buckets [0,1) .. [%d,%d), half-open on the right; "
               "cumulative-from bands %s" % (BUCKET_MIN - 1, BUCKET_MIN,
                                             list(CUM_FROM_MIN)),
    "post_news_family": "the REDEFINED family: every roster candidate whose "
                        "ENTRY lands in [+%d,+%d)min after a scheduled release "
                        "— compliant by construction, and the only shape in "
                        "which a news family can return"
                        % (POST_NEWS_BAND[0] // 60, POST_NEWS_BAND[1] // 60),
    "baselines": {
        "SAME_DAY_FAR": "rows of the SAME (asset, session) as the band's own "
                        "sessions, >= %dmin from every release — the "
                        "day-type-controlled baseline, and the primary"
                        % (FAR_BASELINE_SEC // 60),
        "G1_UNIVERSE_FAR": "rows tagged G1 / G1_FINE / G1_FAST_OPEN (the "
                           "confirmation universe NEWS_WINDOW is drawn from), "
                           ">= %dmin from every release"
                           % (FAR_BASELINE_SEC // 60),
        "ALL_FAR": "every roster row >= %dmin from every release"
                   % (FAR_BASELINE_SEC // 60)},
    "value": "c_c_roster.certificates — walled PHASE-CLOSE (adoption) and "
             "walled PEAK-EXIT (companion), BOTH on every value row; "
             "winner = D-021 (cert_close >= $1000, MAE <= $300, unwalled)",
    "population": "frozen v3 roster, FIT years %s; %d-H1 as an EVAL-ONLY GATE "
                  "echo; sessions with d8 >= %d NEVER LOADED"
                  % (list(FIT_YEARS), GATE_YEAR, HOLDOUT_FROM_D8),
    "inference": "GEE, independence working correlation, Liang-Zeger sandwich "
                 "clustered on SESSION (CR0 + Cameron-Miller CR1) + Kish "
                 "ICC/DEFF/n_eff; ONE Holm-Bonferroni family over the whole "
                 "sweep; no inference claimed below n=%d" % MIN_N_GEE,
    "destruction": "the band indicator shuffled WITHIN ITS OWN SESSION, %d "
                   "replicates, RandomState(%d + index); the destroyed "
                   "quantity is the EDGE; verdicts sign-aware "
                   "(SURVIVES/DESTROYED/INVERTED)"
                   % (DESTRUCTION_REPS, DESTRUCTION_SEED),
    "opens_anchor": "MICRO_OPEN -> the Tokyo lunch reopen (12:30 Asia/Tokyo) / "
                    "US cash open (09:30 America/New_York) second that emitted "
                    "it (family_discovery.MICRO_OPENS, DST-correct); "
                    "G1_FAST_OPEN -> the running phase segment open "
                    "(pattern_lib phase_seg_start)",
    "generation_source": "engine/port_m1/b10_generation_v3.py — NEWS_WINDOW = "
                         "G1 confirmations inside [anchor, anchor+600s), "
                         "single 15s delay; MICRO_OPEN = first 300s after a "
                         "micro-open, 15s delay",
    "two_release_sets": "MEASURED DIVERGENCE (D-006). The family's GENERATION "
                        "anchor set is the FIXED 08:30/10:00 ET slots on EVERY "
                        "session plus FOMC 14:00 ET on meeting days "
                        "(family_discovery.NEWS_SLOTS + "
                        "b10_generation_v3.news_release_offsets). The DATED "
                        "calendar S12/D10 and the prop-firm rule speak about "
                        "is context._bls_calendar + _fomc_calendar — 202 "
                        "actual high-impact releases (Employment Situation, "
                        "CPI, FOMC statement) at 08:30/14:00 ET. The dated set "
                        "is a SUBSET of the anchor set. Both are carried on "
                        "every row: `slot_age` against the family's own "
                        "anchor (where the edge lives) and `rel_age` against "
                        "the dated release (what the rule bites on).",
    "slot_anchor": "GEN_NEWS_SLOT — the most recent generation news anchor at "
                   "or before the decision second; slot_real = that anchor "
                   "second IS a dated high-impact release",
}


# ================================================== the schedule complement ==
def next_release_ts(decision_ts):
    """Epoch second of the first scheduled release AT OR AFTER decision_ts.

    The exact complement of pattern_lib.last_release_ts (which takes the last
    release STRICTLY BEFORE).  Together they partition the calendar at every
    decision second with no double count and no gap.  -1 = none ahead.
    """
    ts, _names = PL.release_calendar()
    d = np.asarray(decision_ts, dtype=np.int64)
    j = np.searchsorted(ts, d, side="left")
    out = np.full(d.size, -1, dtype=np.int64)
    ok = j < ts.size
    if ok.any():
        out[ok] = ts[j[ok]]
    return out


def release_names_at(rel_ts):
    """The calendar name of each matched release second ('' when unmatched)."""
    ts, names = PL.release_calendar()
    r = np.asarray(rel_ts, dtype=np.int64)
    j = np.searchsorted(ts, r, side="left")
    out = []
    for k, t in zip(j.tolist(), r.tolist()):
        out.append(names[k] if (t >= 0 and k < ts.size and int(ts[k]) == t)
                   else "")
    return np.array(out)


def _assert_causal(rel_ts, nxt_ts, dec_ts, where):
    """The triggering release is STRICTLY BEFORE the decision; the next one is
    AT OR AFTER it.  A violation is a leak, not a rounding matter."""
    r = np.asarray(rel_ts, dtype=np.int64)
    n = np.asarray(nxt_ts, dtype=np.int64)
    d = np.asarray(dec_ts, dtype=np.int64)
    bad = (r >= 0) & (r >= d)
    if bad.any():
        raise MC.LeakRefusal(
            "%s: %d candidate(s) matched a triggering release AT OR AFTER the "
            "decision second (first: rel_ts=%d dec_ts=%d)"
            % (where, int(bad.sum()), int(r[bad][0]), int(d[bad][0])))
    bad2 = (n >= 0) & (n < d)
    if bad2.any():
        raise MC.LeakRefusal(
            "%s: %d candidate(s) matched a NEXT release strictly before the "
            "decision second (first: next_ts=%d dec_ts=%d)"
            % (where, int(bad2.sum()), int(n[bad2][0]), int(d[bad2][0])))
    return True


_FOMC = None


def fomc_dates():
    """The FOMC statement DATES b10_generation_v3 joins its 14:00 ET slot on."""
    global _FOMC
    if _FOMC is None:
        _FOMC = set(FD.fomc_release_dates())
    return _FOMC


def slot_anchor_offsets(open_utc, n_sec):
    """Session-second offsets of the family's OWN generation anchors.

    b10_generation_v3.news_release_offsets, verbatim in intent: the fixed
    08:30/10:00 ET slots on every session (DST-correct through the tz database,
    scanning the day before / of / after because Globex opens the previous
    evening ET) plus the FOMC 14:00 ET slot on a meeting's last day.  This is
    the set the NEWS_WINDOW family was CUT on, and it is NOT the dated
    high-impact calendar the prop-firm rule speaks about — see PARAMS
    two_release_sets."""
    rel = []
    for (_nm, tz, hh, mm) in FD.NEWS_SLOTS:
        rel.extend(FD.local_epochs(open_utc, n_sec, tz, hh, mm))
    fom = fomc_dates()
    for off in FD.local_epochs(open_utc, n_sec, FD.TZ_NY, FD.FOMC_HOUR,
                               FD.FOMC_MIN, days=(-1, 0, 1)):
        if FD.dt.datetime.fromtimestamp(int(open_utc) + off,
                                        FD.TZ_NY).date() in fom:
            rel.append(off)
    return sorted(set(int(x) for x in rel))


def bucket_of(age_sec):
    """The 1-minute bucket index of an age in seconds, half-open on the right.

    LAW: 0s -> 0, 59s -> 0, 60s -> 1, 599s -> 9, 600s -> 10, 1199s -> 19,
    1200s -> -1 (past the grid).  A negative age (no prior release) -> -1.
    Integer floor division, never a round — test_news.n02's mutant.
    """
    a = np.asarray(age_sec, dtype=np.int64)
    b = a // BUCKET_SEC
    return np.where((a >= 0) & (b < BUCKET_MIN), b, -1).astype(np.int64)


# ======================================================================= scan
_F64 = ("cert_close", "cert_peak", "mae")
_I64 = ("dec_sec", "rel_age", "rel_ts", "next_ts", "to_next", "min_dist",
        "phase_close_sec", "phase_age", "micro_age", "open_utc", "fam_mask",
        "slot_age", "slot_ts")
_I8 = ("side", "phase")
_BOOL = ("winner", "walled", "held_into", "slot_real")
_CONCAT = _F64 + _I64 + _I8 + _BOOL


def _init():
    MC.verify_spec(force=True)


def _age_since(anchors, dec_sec):
    """Seconds since the most recent anchor AT OR BEFORE each decision second.

    AT OR BEFORE, not strictly before: the family's own construction opens its
    window AT the anchor second (b10_generation_v3 `open_windows`), and the
    anchor is a SCHEDULE fact (D-057), so a decision standing on the anchor
    second has age 0, not "no anchor".  -1 = none yet in this session."""
    if not len(anchors):
        return np.full(dec_sec.size, -1, dtype=np.int64)
    o = np.asarray(anchors, dtype=np.int64)
    j = np.searchsorted(o, dec_sec, side="right") - 1
    out = np.full(dec_sec.size, -1, dtype=np.int64)
    ok = j >= 0
    if ok.any():
        out[ok] = dec_sec[ok] - o[j[ok]]
    return out


def _anchor_sec(anchors, dec_sec):
    """The anchor second itself (session clock); -1 when none has happened."""
    if not len(anchors):
        return np.full(dec_sec.size, -1, dtype=np.int64)
    o = np.asarray(anchors, dtype=np.int64)
    j = np.searchsorted(o, dec_sec, side="right") - 1
    return np.where(j >= 0, o[np.maximum(j, 0)], -1).astype(np.int64)


def _micro_age(asset, d8, open_utc, n_sec, dec_sec):
    """Seconds since the most recent MICRO-OPEN anchor at or before each
    decision second; -1 when none has happened yet in this session.

    The anchors are family_discovery.MICRO_OPENS through its own DST-correct
    `local_epochs`, i.e. exactly the seconds b10_generation_v3 opened the
    MICRO_OPEN windows on (D-006: one definition of the anchor)."""
    offs = []
    for (_nm, tz, hh, mm) in FD.MICRO_OPENS:
        offs.extend(FD.local_epochs(open_utc, n_sec, tz, hh, mm))
    if not offs:
        return np.full(dec_sec.size, -1, dtype=np.int64)
    return _age_since(sorted(set(int(x) for x in offs)), dec_sec)


def _pack(f, asset, d8):
    r = PL.roster(asset)
    dec = f["dec_sec"].astype(np.int64)
    sess = A.load_session(asset, int(d8))
    open_utc = int(sess["s"].meta["open_utc"])
    n_sec = int(sess["s"].n)
    dec_ts = open_utc + dec

    rel_ts = f["release_ts"].astype(np.int64)
    rel_age = f["release_age_sec"].astype(np.int64)
    nxt_ts = next_release_ts(dec_ts)
    _assert_causal(rel_ts, nxt_ts, dec_ts, "%s %d" % (asset, d8))
    to_next = np.where(nxt_ts >= 0, nxt_ts - dec_ts, -1).astype(np.int64)

    # the distance to the NEAREST release either side — what the rule reads
    big = np.int64(1) << np.int64(40)
    da = np.where(rel_age >= 0, rel_age, big)
    db = np.where(to_next >= 0, to_next, big)
    md = np.minimum(da, db)
    min_dist = np.where(md < big, md, -1).astype(np.int64)

    # HELD INTO the window: the walled PHASE-CLOSE certificate is the adoption
    # exit, so the holding horizon is [decision, phase close].  A candidate is
    # held into the restricted window when ANY release's [-10,+10] window
    # intersects that horizon.
    pcs = r["phase_close_sec"][f["i"]].astype(np.int64)
    exit_ts = open_utc + np.maximum(pcs, dec)
    cal, _nm = PL.release_calendar()
    lo = np.searchsorted(cal, dec_ts - VETO_POST_SEC, side="left")
    hi = np.searchsorted(cal, exit_ts + VETO_PRE_SEC, side="right")
    held = (hi - lo) > 0

    # the family's OWN anchor (generation's fixed ET slots + FOMC), and whether
    # that anchor second is a DATED high-impact release
    slots = slot_anchor_offsets(open_utc, n_sec)
    slot_age = _age_since(slots, dec)
    slot_off = _anchor_sec(slots, dec)
    slot_ts = np.where(slot_off >= 0, open_utc + slot_off, -1).astype(np.int64)
    slot_real = np.isin(slot_ts, cal) & (slot_ts >= 0)

    out = {"asset": asset, "d8": int(d8), "cid": f["cid"],
           "klass": f["klass"]}
    src = {
        "cert_close": f["cert_close_usd"], "cert_peak": f["cert_peak_usd"],
        "mae": f["mae_before_argmax"],
        "dec_sec": dec, "rel_age": rel_age, "rel_ts": rel_ts,
        "next_ts": nxt_ts, "to_next": to_next, "min_dist": min_dist,
        "phase_close_sec": pcs, "phase_age": f["phase_age_sec"],
        "micro_age": _micro_age(asset, d8, open_utc, n_sec, dec),
        "open_utc": np.full(dec.size, open_utc, dtype=np.int64),
        "fam_mask": f["fam_mask"],
        "slot_age": slot_age, "slot_ts": slot_ts,
        "side": f["side"], "phase": f["phase_dec"],
        "winner": f["winner"], "walled": f["walled"], "held_into": held,
        "slot_real": slot_real,
    }
    for k in _F64:
        out[k] = np.asarray(src[k], dtype=np.float64)
    for k in _I64:
        out[k] = np.asarray(src[k], dtype=np.int64)
    for k in _I8:
        out[k] = np.asarray(src[k], dtype=np.int64).astype(np.int8)
    for k in _BOOL:
        out[k] = np.asarray(src[k], dtype=bool)
    return out


def _one(job):
    asset, d8 = job
    try:
        f = PL.frame(asset, int(d8), with_levels=False, with_v3=False)
        if f is None:
            return ("EMPTY", asset, int(d8), "")
        p = _pack(f, asset, int(d8))
    except Exception as e:                # noqa: BLE001 — surfaced, not hidden
        return ("ERROR", asset, int(d8), repr(e)[:300])
    A._MEM.pop(("sess", asset, int(d8)), None)
    return ("OK", p)


def scan(assets=MC.ASSET_ORDER, workers=4, limit_sessions=None):
    jobs, quarantined = [], 0
    for a in assets:
        keep, nq = PL.sessions_fit(a, years=set(FIT_YEARS) | {GATE_YEAR})
        quarantined += nq
        if limit_sessions:
            keep = keep[:limit_sessions]
        jobs += [(a, d) for d in keep]
    jobs.sort()
    parts, errs = [], []
    t0 = time.time()
    if workers and workers > 1:
        with mp.Pool(processes=int(workers), initializer=_init) as pool:
            for n, res in enumerate(pool.imap(_one, jobs, chunksize=4), 1):
                if res[0] == "OK":
                    parts.append(res[1])
                elif res[0] == "ERROR":
                    errs.append((res[1], res[2], res[3]))
                if n % 200 == 0:
                    MC.hb("news scan %d/%d  %.1fs"
                          % (n, len(jobs), time.time() - t0))
    else:
        _init()
        for j in jobs:
            res = _one(j)
            if res[0] == "OK":
                parts.append(res[1])
            elif res[0] == "ERROR":
                errs.append((res[1], res[2], res[3]))
    if errs:
        raise RuntimeError("news scan: %d session(s) failed, first=%s"
                           % (len(errs), errs[0]))
    parts.sort(key=lambda p: (p["asset"], p["d8"]))
    D = concat(parts)
    D["n_quarantined"] = quarantined
    D["n_jobs"] = len(jobs)
    MC.hb("news scan: %d rows over %d sessions (%d holdout quarantined), "
          "%.1fs" % (D["dec_sec"].size, D["n_sessions"], quarantined,
                     time.time() - t0))
    return D


def concat(parts):
    """Concatenate packed sessions and derive every rule-shaped field.

    Factored out of `scan` so the red-first tests build the SAME object from a
    single session that the census builds from the population."""
    D = {}
    for k in _CONCAT:
        D[k] = np.concatenate([p[k] for p in parts])
    D["cid"] = np.concatenate([p["cid"] for p in parts])
    D["klass"] = np.concatenate([p["klass"] for p in parts])
    D["asset"] = np.concatenate([np.full(p["dec_sec"].size, p["asset"])
                                 for p in parts])
    D["d8"] = np.concatenate([np.full(p["dec_sec"].size, p["d8"],
                                      dtype=np.int64) for p in parts])
    D["year"] = (D["d8"] // 10000).astype(np.int64)
    D["session_key"] = np.array(["%s-%08d" % (a, d) for a, d in
                                 zip(D["asset"].tolist(), D["d8"].tolist())])
    _uniq, D["sess_id"] = np.unique(D["session_key"], return_inverse=True)
    D["n_sess_unique"] = int(_uniq.size)
    D["era"] = np.where(np.isin(D["year"], FIT_YEARS), ERAS[0],
                        np.where(D["year"] == GATE_YEAR, ERAS[1], "OTHER"))
    D["n_sessions"] = int(_uniq.size)
    # the whole-population causality re-assert (a per-session guard can only
    # see its own session; this one sees the concatenation)
    _assert_causal(D["rel_ts"], D["next_ts"], D["open_utc"] + D["dec_sec"],
                   "POOLED")
    D["is_news"] = (D["fam_mask"] & NEWS_BIT) > 0
    D["is_micro"] = (D["fam_mask"] & MICRO_BIT) > 0
    D["is_fastopen"] = (D["fam_mask"] & FASTOPEN_BIT) > 0
    D["is_g1univ"] = (D["fam_mask"] & G1UNIV_BITS) > 0
    D["inside_window"] = (D["min_dist"] >= 0) & (D["min_dist"] <= VETO_POST_SEC)
    D["inside_legacy"] = (((D["rel_age"] >= 0)
                           & (D["rel_age"] <= VETO_LEGACY[1]))
                          | ((D["to_next"] >= 0)
                             & (D["to_next"] <= -VETO_LEGACY[0])))
    D["pre_window"] = (D["to_next"] >= 0) & (D["to_next"] <= VETO_PRE_SEC)
    D["far"] = (D["min_dist"] < 0) | (D["min_dist"] >= FAR_BASELINE_SEC)
    D["slot_far"] = (D["slot_age"] < 0) | (D["slot_age"] >= FAR_BASELINE_SEC)
    D["bucket"] = bucket_of(D["rel_age"])
    D["slot_bucket"] = bucket_of(D["slot_age"])
    return D


# ================================================================ row stats ==
def _stats(D, m):
    """The value block every table repeats, on BOTH CC-M1-8 readings."""
    n = int(m.sum())
    out = dict(n=n, n_sessions=0, n_winners=0, winner_rate=None,
               mean_close=None, median_close=None, mean_peak=None,
               median_peak=None, cond_close=None, cond_peak=None,
               walled_rate=None, total_close=0.0)
    if n == 0:
        return out
    out["n_sessions"] = int(np.unique(D["sess_id"][m]).size)
    w = D["winner"][m]
    cc = D["cert_close"][m]
    cp = D["cert_peak"][m]
    out["n_winners"] = int(w.sum())
    out["winner_rate"] = float(w.mean())
    out["walled_rate"] = float(D["walled"][m].mean())
    if np.isfinite(cc).any():
        out["mean_close"] = float(np.nanmean(cc))
        out["median_close"] = float(np.nanmedian(cc))
        out["total_close"] = float(np.nansum(cc))
    if np.isfinite(cp).any():
        out["mean_peak"] = float(np.nanmean(cp))
        out["median_peak"] = float(np.nanmedian(cp))
    if w.any():
        cw = cc[w]
        pw = cp[w]
        out["cond_close"] = (float(np.nanmean(cw))
                             if np.isfinite(cw).any() else None)
        out["cond_peak"] = (float(np.nanmean(pw))
                            if np.isfinite(pw).any() else None)
    return out


def _sel(D, aname, ename):
    m = np.ones(D["dec_sec"].size, dtype=bool)
    if aname != "ALL":
        m &= D["asset"] == aname
    if ename != "ALL":
        m &= D["era"] == ename
    return m


def _baseline_mask(D, kind, scope, band_mask):
    """The named non-news baseline, evaluated inside `scope`.

    ALWAYS DISJOINT from the band it is compared against: an unbounded band
    ("ALL", every entry at or after the anchor) otherwise readmits far-from-
    news rows that are ALSO in the far baseline, and the contrast would be
    partly a row against itself."""
    m = scope & (D["slot_far"] if kind == SLOT_BASELINE else D["far"])
    if kind == "G1_UNIVERSE_FAR":
        m &= D["is_g1univ"]
    if kind in ("SAME_DAY_FAR", SLOT_BASELINE):
        if not band_mask.any():
            return np.zeros(D["dec_sec"].size, dtype=bool)
        sel = np.zeros(D["n_sess_unique"], dtype=bool)
        sel[np.unique(D["sess_id"][band_mask])] = True
        m &= sel[D["sess_id"]]
    return m & ~band_mask


# =============================================================== the profile
PROFILE_COLUMNS = ("family", "anchor", "asset", "era", "band", "lo_min",
                   "hi_min", "n", "n_sessions", "n_anchor_days",
                   "n_per_anchor_day", "n_winners", "winner_rate",
                   "mean_close_usd", "median_close_usd", "mean_peak_usd",
                   "median_peak_usd", "cond_close_usd", "cond_peak_usd",
                   "walled_rate", "base_kind", "base_n", "base_winner_rate",
                   "base_mean_close_usd", "base_cond_close_usd",
                   "d_winner_rate", "ratio_winner_rate", "d_mean_close_usd",
                   "compliant")


GRID_TOP_SEC = BUCKET_MIN * BUCKET_SEC     # the profile's own horizon, 20min


def _bands():
    """(band label, lo_sec, hi_sec) — the minute grid, then the cumulative-from
    bands, then the whole grid, then ALL.  Order is the render order and fixed.

    THE CUMULATIVE BANDS ARE CAPPED AT THE GRID TOP.  "cumulative-from >=k" is
    read inside the 20-minute profile; uncapped it would swallow every
    candidate of every session that ever had a release, which is a statement
    about the roster and not about news proximity.  For a family whose own
    anchor bounds it (NEWS_WINDOW tops out at 10.23min) the cap changes
    nothing; for the redefined post-news family it is the difference between a
    band and the population."""
    out = [("B%02d" % k, k * BUCKET_SEC, (k + 1) * BUCKET_SEC)
           for k in range(BUCKET_MIN)]
    out += [("CUM>=%d" % k, k * BUCKET_SEC, GRID_TOP_SEC)
            for k in CUM_FROM_MIN]
    out.append(("GRID[0,%d)" % BUCKET_MIN, 0, GRID_TOP_SEC))
    out.append(("ALL", 0, None))
    return out


def _band_mask(D, lo, hi, agekey="rel_age"):
    m = D[agekey] >= lo
    if hi is not None:
        m = m & (D[agekey] < hi)
    return m


def _n_anchor_days(D, m):
    """Distinct (asset, session) that carry at least one row of the band —
    the denominator a class card's n/day is quoted against."""
    return int(np.unique(D["sess_id"][m]).size) if m.any() else 0


def profile_rows(D, rows, family, fam_mask_sel, anchor="RELEASE",
                 agekey="rel_age", base_kind=PRIMARY_BASELINE):
    for aname in ("ALL",) + tuple(MC.ASSET_ORDER):
        for ename in ("ALL",) + ERAS:
            scope = _sel(D, aname, ename)
            fam = scope & fam_mask_sel
            if not fam.any():
                continue
            for (label, lo, hi) in _bands():
                m = fam & _band_mask(D, lo, hi, agekey)
                st = _stats(D, m)
                if st["n"] == 0:
                    continue
                nd = _n_anchor_days(D, m)
                b = _baseline_mask(D, base_kind, scope, m)
                bs = _stats(D, b)
                dw = (st["winner_rate"] - bs["winner_rate"]
                      if (st["winner_rate"] is not None
                          and bs["winner_rate"] is not None) else None)
                rw = (st["winner_rate"] / bs["winner_rate"]
                      if (st["winner_rate"] is not None and bs["winner_rate"])
                      else None)
                dm = (st["mean_close"] - bs["mean_close"]
                      if (st["mean_close"] is not None
                          and bs["mean_close"] is not None) else None)
                rows.append([family, anchor, aname, ename, label,
                             lo / 60.0, (hi / 60.0) if hi is not None else None,
                             st["n"], st["n_sessions"], nd,
                             (st["n"] / nd) if nd else None,
                             st["n_winners"], st["winner_rate"],
                             st["mean_close"], st["median_close"],
                             st["mean_peak"], st["median_peak"],
                             st["cond_close"], st["cond_peak"],
                             st["walled_rate"], base_kind, bs["n"],
                             bs["winner_rate"], bs["mean_close"],
                             bs["cond_close"], dw, rw, dm,
                             int(lo >= DEPLOY_MIN_SEC)])
    return rows


BASELINE_COLUMNS = ("base_kind", "asset", "era", "n", "n_sessions",
                    "n_winners", "winner_rate", "mean_close_usd",
                    "median_close_usd", "mean_peak_usd", "cond_close_usd",
                    "walled_rate")


def baseline_rows(D, rows):
    news = D["is_news"]
    for kind in BASELINES:
        for aname in ("ALL",) + tuple(MC.ASSET_ORDER):
            for ename in ("ALL",) + ERAS:
                scope = _sel(D, aname, ename)
                b = _baseline_mask(D, kind, scope, scope & news)
                st = _stats(D, b)
                if st["n"] == 0:
                    continue
                rows.append([kind, aname, ename, st["n"], st["n_sessions"],
                             st["n_winners"], st["winner_rate"],
                             st["mean_close"], st["median_close"],
                             st["mean_peak"], st["cond_close"],
                             st["walled_rate"]])
    return rows


# ======================================================== the class-card read
DEPLOY_COLUMNS = ("family", "asset", "era", "reading", "rule", "n",
                  "n_sessions", "n_era_sessions", "n_per_day",
                  "n_per_anchor_day", "n_winners", "winner_rate",
                  "cond_close_usd", "mean_close_usd", "total_close_usd",
                  "cond_peak_usd", "walled_rate", "share_of_family",
                  "verdict")


def _era_sessions(D, aname, ename):
    m = _sel(D, aname, ename)
    return int(np.unique(D["sess_id"][m]).size) if m.any() else 0


def _deploy_verdict(st, base):
    if st["n"] == 0:
        return "EXTINCT_UNDER_RULE"
    if st["n_winners"] == 0:
        return "NO_WINNERS"
    if base is None or base["winner_rate"] is None:
        return "REPORTED"
    if st["winner_rate"] > base["winner_rate"]:
        return "ABOVE_BASELINE"
    return "AT_OR_BELOW_BASELINE"


def deployability_rows(D, rows):
    """The class card, three ways: as the family was built, under the
    SUPERSEDED [-2,+5] default, and under the BINDING +/-10min rule."""
    readings = (
        ("UNCONSTRAINED", "no news rule (the family as built)",
         lambda D: np.ones(D["dec_sec"].size, dtype=bool)),
        ("LEGACY_D077", "superseded D-077 default [-2,+5]min (entries >=+5min "
                        "and not within 2min before a release)",
         lambda D: ~D["inside_legacy"]),
        ("COMPLIANT_D077U", "binding D-077-UPDATE [-10,+10]min (entries "
                            ">=+10min and not within 10min before a release)",
         lambda D: ~D["inside_window"]),
    )
    fams = (("NEWS_WINDOW", lambda D: D["is_news"]),
            ("NEWS_WINDOW@DATED_RELEASE",
             lambda D: D["is_news"] & D["slot_real"]),
            ("NEWS_WINDOW@FIXED_SLOT_ONLY",
             lambda D: D["is_news"] & ~D["slot_real"]),
            ("POST_NEWS_REDEFINED",
             lambda D: (D["rel_age"] >= POST_NEWS_BAND[0])
             & (D["rel_age"] < POST_NEWS_BAND[1])),
            ("POST_NEWS_REDEFINED@SLOT",
             lambda D: (D["slot_age"] >= POST_NEWS_BAND[0])
             & (D["slot_age"] < POST_NEWS_BAND[1])),
            ("MICRO_OPEN", lambda D: D["is_micro"]),
            ("G1_FAST_OPEN", lambda D: D["is_fastopen"]))
    for (fname, fsel) in fams:
        fmask_all = fsel(D)
        for aname in ("ALL",) + tuple(MC.ASSET_ORDER):
            for ename in ("ALL",) + ERAS:
                scope = _sel(D, aname, ename)
                fam = scope & fmask_all
                n_fam = int(fam.sum())
                if n_fam == 0:
                    continue
                nsess = _era_sessions(D, aname, ename)
                base = _stats(D, _baseline_mask(D, PRIMARY_BASELINE, scope,
                                                fam))
                for (rname, rule, rsel) in readings:
                    m = fam & rsel(D)
                    st = _stats(D, m)
                    nd = _n_anchor_days(D, m)
                    rows.append([fname, aname, ename, rname, rule, st["n"],
                                 st["n_sessions"], nsess,
                                 (st["n"] / nsess) if nsess else None,
                                 (st["n"] / nd) if nd else None,
                                 st["n_winners"], st["winner_rate"],
                                 st["cond_close"], st["mean_close"],
                                 st["total_close"], st["cond_peak"],
                                 st["walled_rate"],
                                 (st["n"] / float(n_fam)) if n_fam else None,
                                 _deploy_verdict(st, base)])
    return rows


# ============================================== the opens confound check ====
CONFOUND_COLUMNS = ("family", "asset", "era", "n", "n_sessions",
                    "n_inside_window", "frac_inside_window",
                    "n_inside_legacy", "frac_inside_legacy",
                    "n_post_release_le10min", "frac_post_release_le10min",
                    "n_pre_release_le10min", "frac_pre_release_le10min",
                    "n_held_into_window", "frac_held_into_window",
                    "n_far", "frac_far", "verdict")

CONFOUND_THR = 0.05                        # a family is CLEAN below this


def confound_rows(D, rows):
    fams = (("MICRO_OPEN", D["is_micro"]), ("G1_FAST_OPEN", D["is_fastopen"]),
            ("NEWS_WINDOW", D["is_news"]),
            ("ALL_CANDIDATES", np.ones(D["dec_sec"].size, dtype=bool)))
    post10 = (D["rel_age"] >= 0) & (D["rel_age"] <= VETO_POST_SEC)
    for (fname, fsel) in fams:
        for aname in ("ALL",) + tuple(MC.ASSET_ORDER):
            for ename in ("ALL",) + ERAS:
                m = _sel(D, aname, ename) & fsel
                n = int(m.sum())
                if n == 0:
                    continue
                ni = int(D["inside_window"][m].sum())
                nl = int(D["inside_legacy"][m].sum())
                npo = int(post10[m].sum())
                npr = int(D["pre_window"][m].sum())
                nh = int(D["held_into"][m].sum())
                nf = int(D["far"][m].sum())
                frac = ni / float(n)
                rows.append([fname, aname, ename, n,
                             int(np.unique(D["sess_id"][m]).size),
                             ni, frac, nl, nl / float(n), npo, npo / float(n),
                             npr, npr / float(n), nh, nh / float(n),
                             nf, nf / float(n),
                             "CLEAN" if frac < CONFOUND_THR
                             else ("FULLY_INSIDE" if frac > 0.999
                                   else "PROXIMITY_PRESENT")])
    return rows


def opens_profile_rows(D, rows):
    """MICRO_OPEN and G1_FAST_OPEN profiled against THEIR OWN opens — the same
    estimator as the release profile, re-anchored (D-006: one profile)."""
    profile_rows(D, rows, "MICRO_OPEN", D["is_micro"],
                 anchor="MICRO_OPEN_SECOND", agekey="micro_age")
    profile_rows(D, rows, "G1_FAST_OPEN", D["is_fastopen"],
                 anchor="PHASE_OPEN", agekey="phase_age")
    return rows


# ================================================================= inference
# (branch, band label, lo_sec, hi_sec).  BRANCH says which population the band
# is cut out of and against which anchor:
#   NEWS_SLOT   the family as built, against ITS OWN generation anchor — the
#               D-077 "where does the edge live" sweep
#   NEWS_WINDOW the family, against the DATED high-impact release — what the
#               prop-firm rule actually bites on
#   POST_NEWS   EVERY roster candidate at that distance from a DATED release,
#               the only shape a redefined post-news family could take
GEE_BRANCH = {"NEWS_SLOT": ("family", "slot_age", SLOT_BASELINE),
              "NEWS_WINDOW": ("family", "rel_age", PRIMARY_BASELINE),
              "POST_NEWS": ("all", "rel_age", PRIMARY_BASELINE)}
GEE_BANDS = ([("NEWS_SLOT", "ALL", 0, None)]
             + [("NEWS_SLOT", "CUM>=%d" % k, k * BUCKET_SEC, GRID_TOP_SEC)
                for k in (1, 2, 3, 4, 5, 6, 7, 8, 10)]
             + [("NEWS_WINDOW", "GRID[0,20)", 0, GRID_TOP_SEC)]
             + [("NEWS_WINDOW", "CUM>=%d" % k, k * BUCKET_SEC, GRID_TOP_SEC)
                for k in (5, 10)]
             + [("POST_NEWS", "CUM>=%d" % k, k * BUCKET_SEC, GRID_TOP_SEC)
                for k in (10, 12, 15)]
             + [("POST_NEWS", "[10,20)", POST_NEWS_BAND[0],
                 POST_NEWS_BAND[1])])


def _gee_row(D, robust, obj, ename, metric, band_mask, base_mask):
    y_all = {"winner": D["winner"].astype(np.float64),
             "cert_close": D["cert_close"],
             "cert_peak": D["cert_peak"]}[metric]
    link = "logit" if metric == "winner" else "identity"
    m = band_mask | base_mask
    if metric != "winner":
        m = m & np.isfinite(y_all)
    n_band = int((band_mask & m).sum())
    if n_band < MIN_N_GEE or int((base_mask & m).sum()) < MIN_N_GEE:
        return
    y = y_all[m]
    x = band_mask[m].astype(np.float64)
    cl = D["sess_id"][m]
    gi = np.unique(cl, return_inverse=True)[1]
    g = EV.gee_independence(y, x, cl, link=link)
    if g is None:
        return
    ic = EV.icc_oneway(y, gi)
    z = (g["beta"] / g["se_cr1"]) if g["se_cr1"] > 0 else float("nan")
    p = P1._p_two_sided(z)
    robust.append([obj, ename, metric, "SESSION", g["n"], g["n_clusters"],
                   n_band, g["beta"], g["se_naive"], g["se_cr0"], g["se_cr1"],
                   z, p,
                   ic["rho"] if ic else float("nan"),
                   ic["deff"] if ic else float("nan"),
                   ic["n_eff"] if ic else float("nan"),
                   "SIGNIFICANT_p<0.05" if (np.isfinite(p) and p < 0.05)
                   else "NOT_SIGNIFICANT"])


def robust_rows(D, robust):
    """One Holm family over the whole sweep: every band, every asset, both
    eras, both value metrics + the winner indicator."""
    news = D["is_news"]
    for (branch, label, lo, hi) in GEE_BANDS:
        pop, agekey, bkind = GEE_BRANCH[branch]
        for aname in ("ALL",) + tuple(MC.ASSET_ORDER):
            for ename in ERAS:
                scope = _sel(D, aname, ename)
                band = scope & _band_mask(D, lo, hi, agekey)
                if pop == "family":
                    band = band & news
                obj = "%s_%s_%s" % (branch, label, aname)
                if not band.any():
                    continue
                base = _baseline_mask(D, bkind, scope, band)
                for metric in ("winner", "cert_close"):
                    _gee_row(D, robust, obj, ename, metric, band, base)
    # the opens confound, tested rather than eyeballed: is a family's
    # release-proximity share different from the population's?
    for (fname, fsel) in (("MICRO_OPEN", D["is_micro"]),
                          ("G1_FAST_OPEN", D["is_fastopen"])):
        for ename in ERAS:
            scope = _sel(D, "ALL", ename)
            band = scope & fsel & D["inside_window"]
            base = scope & fsel & ~D["inside_window"]
            _gee_row(D, robust, "OPENS_%s_inside_window" % fname, ename,
                     "winner", band, base)
    return robust


def destruction_rows(D, rows):
    """The band indicator shuffled WITHIN ITS OWN SESSION.  The edge is the
    winner-rate difference the band claims; a shuffle that reproduces it means
    the claim was a session-stratum artefact."""
    news = D["is_news"]
    objs = (("NEWS_SLOT_ALL", news, SLOT_BASELINE),
            ("NEWS_SLOT_CUM>=5", news & (D["slot_age"] >= 5 * BUCKET_SEC),
             SLOT_BASELINE),
            ("NEWS_WINDOW_dated_ALL", news & (D["rel_age"] >= 0)
             & (D["rel_age"] < POST_NEWS_BAND[0]), PRIMARY_BASELINE),
            ("POST_NEWS[10,20)", _band_mask(D, *POST_NEWS_BAND),
             PRIMARY_BASELINE))
    for i, (oname, sel, bkind) in enumerate(objs):
        for ename in ERAS:
            scope = _sel(D, "ALL", ename)
            band = scope & sel
            base = _baseline_mask(D, bkind, scope, band)
            pool = band | base
            if int(band.sum()) < MIN_N_GEE or int(base.sum()) < MIN_N_GEE:
                continue
            call = band[pool].astype(np.float64)
            y = D["winner"][pool].astype(np.float64)
            sess = D["sess_id"][pool]
            real = float(y[call > 0].mean() - y[call <= 0].mean())
            rs = np.random.RandomState(DESTRUCTION_SEED + i)
            null = []
            for _ in range(DESTRUCTION_REPS):
                c2 = B4._shuffle_within(call, sess, rs)
                if (c2 > 0).any() and (c2 <= 0).any():
                    null.append(float(y[c2 > 0].mean() - y[c2 <= 0].mean()))
            rows.append(B4._destr_row(oname, ename,
                                      "band indicator (within session)",
                                      real, null))
    return rows


# ============================================== the blind-scoring join helper
DIST_COLUMNS = ("cid", "family", "minutes_since_release",
                "inside_default_window", "asset", "d8", "dec_sec", "side",
                "era", "klass", "driver_family", "minutes_to_next_release",
                "minutes_to_nearest_release", "release_ts", "release_name",
                "next_release_ts", "next_release_name", "pre_release_window",
                "held_into_window", "inside_superseded_window",
                "phase_close_sec", "minutes_since_gen_anchor",
                "gen_anchor_is_dated_release",
                "minutes_since_last_release_any")


def distance_rows(D):
    """Every roster candidate within DIST_RADIUS_SEC either side of a release."""
    m = (D["min_dist"] >= 0) & (D["min_dist"] <= DIST_RADIUS_SEC)
    idx = np.nonzero(m)[0]
    order = idx[np.lexsort((D["dec_sec"][idx], D["d8"][idx],
                            D["asset"][idx]))]
    rname = release_names_at(D["rel_ts"][order])
    nname = release_names_at(D["next_ts"][order])
    rows = []
    for k, i in enumerate(order.tolist()):
        fam = MC.fam_names(int(D["fam_mask"][i]))
        cls, driver, _oth = MC.class_of(int(D["fam_mask"][i]))
        ra = int(D["rel_age"][i])
        tn = int(D["to_next"][i])
        rows.append([D["cid"][i], "|".join(fam),
                     (ra / 60.0) if (0 <= ra <= DIST_RADIUS_SEC) else None,
                     int(bool(D["inside_window"][i])),
                     D["asset"][i], int(D["d8"][i]), int(D["dec_sec"][i]),
                     int(D["side"][i]), D["era"][i], cls, driver or "",
                     (tn / 60.0) if tn >= 0 else None,
                     int(D["min_dist"][i]) / 60.0,
                     int(D["rel_ts"][i]), rname[k],
                     int(D["next_ts"][i]), nname[k],
                     int(bool(D["pre_window"][i])),
                     int(bool(D["held_into"][i])),
                     int(bool(D["inside_legacy"][i])),
                     int(D["phase_close_sec"][i]),
                     (int(D["slot_age"][i]) / 60.0
                      if int(D["slot_age"][i]) >= 0 else None),
                     int(bool(D["slot_real"][i])),
                     (ra / 60.0) if ra >= 0 else None])
    return rows


# ==================================================================== report
def _pick(rows, cols, **kw):
    ix = {c: i for i, c in enumerate(cols)}
    out = []
    for r in rows:
        if all(r[ix[k]] == v for k, v in kw.items()):
            out.append(r)
    return out


def _fmt(v, dec=3):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "-"
    if isinstance(v, float):
        return ("%%.%df" % dec) % v
    return str(v)


def report(D, res, elapsed, pins):
    L = []
    A_ = L.append
    A_("# PORT M2 — THE NEWS-WINDOW COMPLIANCE CENSUS (D-077 + D-077-UPDATE)")
    A_("")
    A_("Population: %d roster candidates over %d (asset, session) pairs, FIT "
       "%s + GATE-%dH1; %d holdout sessions refused (d8 >= %d, never loaded). "
       "Elapsed %.1fs."
       % (D["dec_sec"].size, D["n_sessions"], list(FIT_YEARS), GATE_YEAR,
          D["n_quarantined"], HOLDOUT_FROM_D8, elapsed))
    A_("")
    A_("THE RULE: no entry inside [-%dmin, +%dmin] of a scheduled release "
       "(D-077-UPDATE, binding; the [-2,+5] default of D-077 is superseded and "
       "kept only as a second reading). Avoidance is the preferred posture."
       % (VETO_PRE_SEC // 60, VETO_POST_SEC // 60))
    A_("")

    # --- 1. the two release sets -------------------------------------------
    news = D["is_news"]
    n_news = int(news.sum())
    sages = D["slot_age"][news]
    rages = D["rel_age"][news]
    inside = int(D["inside_window"][news].sum())
    n_real = int((news & D["slot_real"]).sum())
    A_("## 1. TWO RELEASE SETS — THE FAMILY IS NOT CUT ON THE RULE'S CALENDAR")
    A_("")
    A_("NEWS_WINDOW rows: %d." % n_news)
    A_("")
    A_("* against the family's OWN generation anchor (fixed 08:30/10:00 ET "
       "slots on EVERY session + FOMC 14:00 ET on meeting days): age range "
       "[%.2f, %.2f] min — the [15s, 615s] window b10_generation_v3 cut, "
       "confirmed."
       % (float(sages.min()) / 60.0, float(sages.max()) / 60.0))
    A_("* against the DATED high-impact calendar the prop-firm rule speaks "
       "about (context BLS + FOMC, %d releases): only %d of %d rows (%.2f%%) "
       "sit on an anchor that IS a dated release; the family's age-since-dated-"
       "release ranges [%.2f, %.2f] min."
       % (PL.release_calendar()[0].size, n_real, n_news,
          100.0 * n_real / max(n_news, 1), float(rages.min()) / 60.0,
          float(rages.max()) / 60.0))
    A_("* inside the binding +/-%dmin restricted window: %d of %d rows "
       "(%.2f%%)."
       % (VETO_POST_SEC // 60, inside, n_news, 100.0 * inside / max(n_news, 1)))
    A_("")
    A_("This is a D-006 divergence and it is the whole shape of the answer: "
       "the family is a FIXED-CLOCK family wearing a news name. The rule "
       "strikes the part of it that really does sit on a release; the rest is "
       "an 08:30/10:00 ET clock effect and is unaffected by the news rule.")
    A_("")

    # --- 2. the minute profile ---------------------------------------------
    A_("## 2. THE MINUTE PROFILE — WHERE THE EDGE LIVES")
    A_("")
    P = res["profile"]
    for (fam, anch, base) in (
            ("NEWS_WINDOW", "GEN_NEWS_SLOT", SLOT_BASELINE),
            ("NEWS_WINDOW@DATED_RELEASE", "GEN_NEWS_SLOT", SLOT_BASELINE),
            ("NEWS_WINDOW", "DATED_RELEASE", PRIMARY_BASELINE),
            ("POST_NEWS_REDEFINED", "DATED_RELEASE", PRIMARY_BASELINE)):
        sub = _pick(P, PROFILE_COLUMNS, family=fam, anchor=anch, asset="ALL",
                    era=ERAS[0])
        if not sub:
            continue
        A_("### %s vs %s (pooled assets, era %s, baseline %s)"
           % (fam, anch, ERAS[0], base))
        A_("")
        A_("| band | n | n/day | winners | win rate | base win rate | ratio | "
           "mean close $ | median close $ | mean peak $ | cond close $ |")
        A_("|---|---|---|---|---|---|---|---|---|---|---|")
        for r in sub:
            A_("| %s | %d | %s | %d | %s | %s | %s | %s | %s | %s | %s |"
               % (r[4], r[7], _fmt(r[10], 2), r[11], _fmt(r[12], 4),
                  _fmt(r[22], 4), _fmt(r[26], 2), _fmt(r[13], 1),
                  _fmt(r[14], 1), _fmt(r[15], 1), _fmt(r[17], 1)))
        A_("")
    A_("The same tables for the GATE echo and per asset are in "
       "NEWS_MINUTE_PROFILE.tsv; the four baselines are in "
       "NEWS_BASELINES.tsv.")
    A_("")

    # --- 3. deployability ---------------------------------------------------
    A_("## 3. THE DEPLOYABILITY VERDICT (D-077 item 2)")
    A_("")
    A_("| family | era | reading | n | n/day | win rate | cond close $ | "
       "total close $ | share of family | verdict |")
    A_("|---|---|---|---|---|---|---|---|---|---|")
    for r in _pick(res["deploy"], DEPLOY_COLUMNS, asset="ALL"):
        if r[2] == "ALL":
            continue
        A_("| %s | %s | %s | %d | %s | %s | %s | %s | %s | %s |"
           % (r[0], r[2], r[3], r[5], _fmt(r[8], 3), _fmt(r[11], 4),
              _fmt(r[12], 1), _fmt(r[14], 0), _fmt(r[17], 4), r[18]))
    A_("")

    # --- 4. opens -----------------------------------------------------------
    A_("## 4. THE OPENS CONFOUND CHECK (informational)")
    A_("")
    A_("| family | asset | era | n | inside +/-10min | frac | held into "
       "window | frac | verdict |")
    A_("|---|---|---|---|---|---|---|---|---|")
    for r in _pick(res["confound"], CONFOUND_COLUMNS, era="ALL"):
        A_("| %s | %s | %s | %d | %d | %s | %d | %s | %s |"
           % (r[0], r[1], r[2], r[3], r[5], _fmt(r[6], 4), r[13],
              _fmt(r[14], 4), r[17]))
    A_("")

    # --- 5. inference -------------------------------------------------------
    rb = res["robust"]
    n_test = len([r for r in rb if np.isfinite(r[12])])
    n_sig = len([r for r in rb if r[19] == "HOLM_SIGNIFICANT"])
    A_("## 5. INFERENCE — %d GEE tests, ONE Holm family, %d survive"
       % (n_test, n_sig))
    A_("")
    if n_sig:
        A_("| object | era | metric | n | clusters | beta | se_cr1 | p_cr1 | "
           "holm |")
        A_("|---|---|---|---|---|---|---|---|---|")
        for r in sorted([r for r in rb if r[19] == "HOLM_SIGNIFICANT"],
                        key=lambda r: r[12])[:40]:
            A_("| %s | %s | %s | %d | %d | %s | %s | %s | %s |"
               % (r[0], r[1], r[2], r[4], r[5], _fmt(r[7], 4), _fmt(r[10], 4),
                  _fmt(r[12], 6), r[19]))
    else:
        A_("No test survives Holm over the sweep.")
    A_("")
    A_("## 6. DESTRUCTION")
    A_("")
    A_("| object | era | edge real | null mean | null sd | z | verdict |")
    A_("|---|---|---|---|---|---|---|")
    for r in res["destr"]:
        A_("| %s | %s | %s | %s | %s | %s | %s |"
           % (r[0], r[1], _fmt(r[4], 4), _fmt(r[5], 4), _fmt(r[6], 4),
              _fmt(r[9], 2), r[10]))
    A_("")
    A_("## 7. THE SCORING HELPER")
    A_("")
    A_("NEWS_DISTANCE.tsv: %d rows — every roster candidate within +/-%dmin of "
       "a scheduled release, carrying its signed distance, the "
       "inside_default_window flag (+/-%dmin, the binding rule), the "
       "pre_release_window flag and the held_into_window flag."
       % (len(res["dist"]), DIST_RADIUS_SEC // 60, VETO_POST_SEC // 60))
    A_("")
    A_("PINS: %s" % ("all held at HEAD" if not pins else "; ".join(pins)))
    A_("")
    return "\n".join(L) + "\n"


# ====================================================================== build
def build(workers=4, limit_sessions=None):
    t0 = time.time()
    MC.verify_spec(force=True)
    D = scan(workers=workers, limit_sessions=limit_sessions)

    res = {}
    prof = []
    # (a) the family against ITS OWN generation anchor — where the edge lives
    profile_rows(D, prof, "NEWS_WINDOW", D["is_news"], anchor="GEN_NEWS_SLOT",
                 agekey="slot_age", base_kind=SLOT_BASELINE)
    profile_rows(D, prof, "NEWS_WINDOW@DATED_RELEASE",
                 D["is_news"] & D["slot_real"], anchor="GEN_NEWS_SLOT",
                 agekey="slot_age", base_kind=SLOT_BASELINE)
    profile_rows(D, prof, "NEWS_WINDOW@FIXED_SLOT_ONLY",
                 D["is_news"] & ~D["slot_real"], anchor="GEN_NEWS_SLOT",
                 agekey="slot_age", base_kind=SLOT_BASELINE)
    # (b) the family against the DATED release — what the rule bites on
    profile_rows(D, prof, "NEWS_WINDOW", D["is_news"], anchor="DATED_RELEASE")
    # (c) every candidate against the DATED release — the redefined family's
    #     population
    profile_rows(D, prof, "POST_NEWS_REDEFINED",
                 np.ones(D["dec_sec"].size, dtype=bool),
                 anchor="DATED_RELEASE")
    res["profile"] = prof
    MC.hb("news: minute profile done (%d rows)" % len(prof))
    res["baselines"] = baseline_rows(D, [])
    res["deploy"] = deployability_rows(D, [])
    res["opens"] = opens_profile_rows(D, [])
    res["confound"] = confound_rows(D, [])
    MC.hb("news: profiles + confound done")
    robust = robust_rows(D, [])
    B4._holm(robust, 12, len(B4.ROBUST_COLUMNS))
    res["robust"] = robust
    res["destr"] = destruction_rows(D, [])
    MC.hb("news: %d GEE tests, %d destruction rows"
          % (len(robust), len(res["destr"])))
    res["dist"] = distance_rows(D)
    MC.hb("news: NEWS_DISTANCE %d rows" % len(res["dist"]))

    phash = MC.params_hash(PARAMS)
    extra = ["D-077-UPDATE: the restricted window is [-%dmin, +%dmin] and "
             "AVOIDANCE is the preferred posture"
             % (VETO_PRE_SEC // 60, VETO_POST_SEC // 60),
             "ROW grain: one v3-roster candidate; distances are decision_sec "
             "vs the release second (the rule constrains the ENTRY)",
             "BOTH CC-M1-8 certificate readings are reported on every value "
             "row",
             "HOLDOUT: no session with d8 >= %d was loaded (CC-M2-15.3)"
             % HOLDOUT_FROM_D8]
    W = MC.write_tsv
    W(os.path.join(OUT_DIR, "NEWS_MINUTE_PROFILE.tsv"), SECTION, phash,
      list(PROFILE_COLUMNS), res["profile"],
      extra=extra + ["bands B00..B%02d are 1-minute buckets half-open on the "
                     "right; CUM>=k is every entry at or after k minutes; "
                     "`compliant` = 1 when the whole band sits at or after "
                     "+%dmin" % (BUCKET_MIN - 1, DEPLOY_MIN_SEC // 60),
                     "family POST_NEWS_REDEFINED profiles EVERY roster "
                     "candidate by minutes-since-release, whatever family tag "
                     "it carries — the population a redefined post-news family "
                     "would be drawn from"])
    W(os.path.join(OUT_DIR, "NEWS_BASELINES.tsv"), SECTION, phash,
      list(BASELINE_COLUMNS), res["baselines"],
      extra=extra + ["SAME_DAY_FAR is the primary baseline: same sessions, "
                     ">= %dmin from every release, so day type is controlled"
                     % (FAR_BASELINE_SEC // 60)])
    W(os.path.join(OUT_DIR, "NEWS_DEPLOYABILITY.tsv"), SECTION, phash,
      list(DEPLOY_COLUMNS), res["deploy"],
      extra=extra + ["n_per_day divides by EVERY session of the era (the class "
                     "card's rate); n_per_anchor_day divides by the sessions "
                     "that actually carry a row of the reading"])
    W(os.path.join(OUT_DIR, "OPENS_PROFILE.tsv"), SECTION, phash,
      list(PROFILE_COLUMNS), res["opens"],
      extra=extra + ["the anchor here is the family's OWN open, not a "
                     "release: MICRO_OPEN_SECOND or PHASE_OPEN"])
    W(os.path.join(OUT_DIR, "OPENS_CONFOUND.tsv"), SECTION, phash,
      list(CONFOUND_COLUMNS), res["confound"],
      extra=extra + ["frac_inside_window is the D-077-UPDATE item-4 check: an "
                     "open family with a material share inside the window is "
                     "partly a news family"])
    W(os.path.join(OUT_DIR, "NEWS_DISTANCE.tsv"), SECTION, phash,
      list(DIST_COLUMNS), res["dist"],
      extra=extra + ["one row per roster candidate within +/-%dmin of a "
                     "scheduled release; join on cid"
                     % (DIST_RADIUS_SEC // 60),
                     "minutes_since_release is EMPTY when no release precedes "
                     "the decision INSIDE THE REACH (the row is then in the "
                     "table because a release is AHEAD) — read "
                     "minutes_to_next_release, or "
                     "minutes_since_last_release_any for the unbounded age",
                     "held_into_window = the walled phase-close holding "
                     "horizon [decision, phase close] intersects some "
                     "release's [-%dmin, +%dmin] window"
                     % (VETO_PRE_SEC // 60, VETO_POST_SEC // 60)])
    W(os.path.join(OUT_DIR, "NEWS_ROBUST.tsv"), SECTION, phash,
      list(B4.ROBUST_COLUMNS), res["robust"],
      extra=extra + ["ONE Holm-Bonferroni family over the WHOLE sweep"])
    W(os.path.join(OUT_DIR, "NEWS_DESTRUCTION.tsv"), SECTION, phash,
      list(B4.DESTR_COLUMNS), res["destr"], extra=extra)

    pins = MC.pins_moved()
    el = time.time() - t0
    MC.write_text(os.path.join(OUT_DIR, "NEWS_COMPLIANCE_REPORT.md"),
                  report(D, res, el, pins))
    news = D["is_news"]
    n_news = int(news.sum())
    comp = int((news & ~D["inside_window"]).sum())
    MC.write_json(os.path.join(OUT_DIR, "news_census.receipt.json"),
                  {"env": MC.env_receipt(PARAMS),
                   "n_rows": int(D["dec_sec"].size),
                   "n_sessions": D["n_sessions"],
                   "n_holdout_sessions_quarantined": D["n_quarantined"],
                   "holdout_from_d8": HOLDOUT_FROM_D8,
                   "restricted_window_sec": [-VETO_PRE_SEC, VETO_POST_SEC],
                   "n_news_window": n_news,
                   "news_slot_min_age_sec": int(D["slot_age"][news].min()),
                   "news_slot_max_age_sec": int(D["slot_age"][news].max()),
                   "n_news_window_on_dated_release":
                       int((news & D["slot_real"]).sum()),
                   "n_dated_releases": int(PL.release_calendar()[0].size),
                   "news_min_age_sec": int(D["rel_age"][news].min()),
                   "news_max_age_sec": int(D["rel_age"][news].max()),
                   "n_news_window_compliant": comp,
                   "frac_news_window_inside_restricted":
                       float(int((news & D["inside_window"]).sum())
                             / max(n_news, 1)),
                   "n_post_news_redefined":
                       int(_band_mask(D, *POST_NEWS_BAND).sum()),
                   "n_distance_rows": len(res["dist"]),
                   "n_gee_tests": int(len([r for r in res["robust"]
                                           if np.isfinite(r[12])])),
                   "n_holm_significant":
                       int(len([r for r in res["robust"]
                                if r[19] == "HOLM_SIGNIFICANT"])),
                   "elapsed_sec": el, "pins_moved": pins,
                   "out_dir": OUT_DIR})
    MC.hb("news census: %d rows, NEWS_WINDOW %d (%d compliant), %.1fs"
          % (D["dec_sec"].size, n_news, comp, el))
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--limit-sessions", type=int, default=None)
    a = p.parse_args()
    if a.workers > 4:
        raise SystemExit("workers capped at 4 (the E1 BLIND reader lane is "
                         "live — D-002 lane discipline)")
    build(workers=a.workers, limit_sessions=a.limit_sessions)
    return 0


if __name__ == "__main__":
    sys.exit(main())
