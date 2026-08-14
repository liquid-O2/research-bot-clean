#!/usr/bin/python3
"""E1 BLIND ROUND — THE SCORING PASS (the CC-M2-6 teacher-gate INPUTS).

This lane computes; it does NOT adjudicate.  Every number below is the
pre-registered statistic of CC-M2-6 computed exactly as registered, on the
twelve SEALED blind days, under the two D-077-UPDATE readings.  The verdict is
the orchestrator's (CC-M2-6, D-075).

WHAT IT DOES
  0. SEAL CHECK (red-first).  The scored ledger's git blob sha1 is recomputed
     from the bytes on disk and compared with `git rev-parse HEAD:<ledger>`.
     A single flipped call changes the blob and the pass REFUSES.  `--mutant`
     proves it: one TAKE row is flipped in a copy, the hash check refuses it,
     and the score of the mutant is shown to differ.
  1. THE READER ARM — panel_score on the sealed ledger: lift on BOTH CC-M1-8
     readings, winner precision at the D-021 bar, one-position chronological
     replay at PHASE-CLOSE seating (CC-M2-10.3 / CC-M2-21.4's greedy replay =
     the pooled law, DP seat-split carried as the companion), capture against
     the summed DP ceilings of the round's session-assets.
  2. MECHANICAL BASELINES on the same days and the same universe:
       * EARLIEST + class-census threshold (baseline_replay.py, frozen K*/
         SPAN_MAX + frozen D-071 class cards, swept over every threshold so the
         comparison is against the BEST arm);
       * every frozen predecessor policy e1d1..e1d8 run AS COMMITTED through
         its own CLI on the COMPAT index (CC-M2-8.2 yesterday-policy law);
       * THE FROZEN DECLARED ARM — e1_blind_declared_policy.py exactly as
         committed pre-round (CC-M2-20.2's second arm; reported beside the
         baselines and, separately, as the reader's head-to-head rival).
  3. THE THREE CC-M2-6 BARS, per reading:
       (a) margin over the BEST mechanical baseline > 0, paired by day, GEE
           independence-working-correlation sandwich, Cameron-Miller CR1;
       (b) lift >= 1.30 (phase-close = adoption; peak-exit carried);
       (c) replay capture >= 0.25 of the summed day ceilings.
  4. D-077-UPDATE READINGS.  `m2/news_compliance/NEWS_DISTANCE.tsv` has NOT
     landed (the census lane is unrun), so distances are computed here from the
     SAME dated calendar the rule speaks about — pattern_lib.release_calendar()
     = context._bls_calendar + _fomc_calendar, the availability-lagged
     SCHEDULE_EXEMPT join (D-057; release DATES are published months ahead).
     Three readings are emitted because the dated calendar and the family's
     generation anchor are two different sets (news_census PARAMS
     "two_release_sets"), and defect D31 says so out loud:
       SCIENCE            every call (learning reading).
       DEPLOYABLE         CC-M2-22.4, BINDING: compliance is read from the
                          NEWS_DISTANCE.tsv FLAGS — inside_default_window,
                          pre_release_window, held_into_window — never
                          inferred from a blank minutes field (D-N3), plus
                          the hold-crossing clause for rows outside the
                          file's +/-15min reach.
       NAME-STRUCK-       SUPERSEDED by CC-M2-22.1 and retained ONLY to
       SUPERSEDED         reconcile the sealed summary's name-based 26-of-40
                          count: DEPLOYABLE minus every row carrying the
                          family label formerly spelled NEWS-WINDOW (now
                          US_CLOCK — a fixed-clock family; only ~19% of its
                          fires sit near a dated release, so the NAME IS NOT
                          A COMPLIANCE FACT).
     A struck candidate leaves the UNIVERSE for every arm and for the DP
     ceiling alike: a policy that may not enter there must not be charged for
     the ceiling there either.  Capture against the FULL-universe ceiling is
     carried beside it.

DISCIPLINE
  /usr/bin/python3, single process (workers 1 <= 4), deterministic (no RNG
  anywhere in this file), D-018 (bulk under artifacts/cache/), the 2026 and
  2025-H1 holdout walls untouched — these are 2021 sessions.  Pins verified at
  launch and re-checked at the end through MC.pins_moved().

Run:
  lab/run.sh port-m2-blindscore -- /usr/bin/python3 engine/port_m2/e1blind_score.py
"""
import argparse
import csv
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict, OrderedDict

import numpy as np
from scipy import stats as SST

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                          # noqa: E402
import panel_score as PS                        # noqa: E402
import pattern_lib as PL                        # noqa: E402
import baseline_replay as BR                    # noqa: E402
import batch4_census as B4                      # noqa: E402  (gee_multi)
import c_c_roster as CC                         # noqa: E402

SECTION = "§CC-M2-6 (E1 BLIND SCORING PASS — teacher-gate inputs)"

REPO = os.path.dirname(os.path.dirname(_HERE))
LEDGER = os.path.join(REPO, "provenance/port_m2/E1_BLIND_LEDGER.tsv")
TRIAGE = os.path.join(REPO, "artifacts/cache/port/m2/triage")
OUT = os.path.join(REPO, "artifacts/cache/port/m2/blind_score")
EVIDENCE = os.path.join(REPO, "evidence/port_m2")

# CC-M2-6, verbatim
BAR_LIFT = 1.30
BAR_CAPTURE = 0.25
# D-077-UPDATE: the firm's restricted window
NEWS_WINDOW_SEC = 600
# CC-M2-22.1 renames this family US_CLOCK.  R102: the rename is a DISPLAY
# ALIAS and the WIRE spelling stays pinned in every join, lookup and committed
# column, because the frozen policy's HI_CLASSES and 204,737 rendered sheets
# carry it and CC-M2-4.3 forbids editing the frozen policy.
NEWS_FAMILY = MC.CLASS_NEWS                 # the WIRE spelling, always
NEWS_FAMILY_DISPLAY = MC.display_name(NEWS_FAMILY)

# R127.  The "dated scheduled high-impact release" universe the DEPLOYABLE
# reading is taken against is exactly Employment Situation / CPI / FOMC
# statement, and across the twelve E1 blind days it contains ONE event.  A
# reading built on a calendar that touches almost none of the block's days is
# an NFP/CPI/FOMC reading, not a prop-firm compliance reading — and
# D-077-UPDATE(3) calls DEPLOYABLE "the reading that counts for the goal".  So
# the coverage is MEASURED and the reading is REFUSED below a declared floor.
DEPLOYABLE_MIN_DAY_COVERAGE = 0.50

N_DAYS = 12
PREDECESSORS = tuple("e1d%d_policy" % d for d in range(1, 9))

# R126.  The reference arm for bar (a) is PRE-REGISTERED here, in code, before
# any margin is computed.  BASE_EARLIEST is the pure zero-intelligence arm
# (earliest member of every EPISODE_CAUSAL group, no census input at all), so
# it exists in every era and needs no card that could be refused.
PREREGISTERED_ARM = "BASE_EARLIEST"

PARAMS = {
    "spec_section": SECTION,
    "bars": "CC-M2-6: (a) margin over the BEST mechanical baseline > 0 "
            "day-paired GEE/CR1; (b) lift >= %.2f; (c) replay capture >= %.2f"
            % (BAR_LIFT, BAR_CAPTURE),
    "seating": "CC-M2-10.3 PHASE-CLOSE; CC-M2-21.4 pooled law = the GREEDY "
               "chronological one-position replay, DP seat-split companion",
    "lift": "mean(cert of TAKEs)/mean(cert of SKIPs), both CC-M1-8 readings",
    "winner": "D-021: cert >= $1000 AND mae_before_argmax <= $300 AND not "
              "walled",
    "outcomes": "frozen v3 ORACLE_FREEZE roster via c_c_roster.certificates "
                "(panel_score.outcome) — unblinded by THIS pass, never before",
    "news_rule": "D-077-UPDATE [-10,+10]min around a DATED scheduled "
                 "high-impact release (pattern_lib.release_calendar = BLS + "
                 "FOMC, SCHEDULE_EXEMPT); entry-in-window OR hold-crosses-"
                 "window strikes the candidate from the deployable universe",
    "inference": "GEE independence working correlation, Liang-Zeger sandwich, "
                 "Cameron-Miller CR1 (batch4_census.gee_multi, intercept-only "
                 "for the paired margin); clusters = DAY for the registered "
                 "day-paired bar, SESSION for the row-grain statistics",
    "determinism": "no RNG; single process",
    # R126: the reference arm is named BEFORE the margins are computed and the
    # bar is scored in its conservative form.
    "bar_a_reference": "PRE-REGISTERED arm %s; the bar is POSITIVE AGAINST "
                       "EVERY mechanical arm; the max-of-arms reading is "
                       "emitted labelled as the IN-SAMPLE ORDER STATISTIC it "
                       "is and is never the bar" % PREREGISTERED_ARM,
    "deployable_min_day_coverage": DEPLOYABLE_MIN_DAY_COVERAGE,
}


# R131.  `PARAMS["news_rule"]` was prose and was NOT edited when the compliance
# rule changed at 6310e71, so `params_hash` was byte-identical across two
# materially different scoring rules — the one mechanism whose job is to make
# exactly that change detectable.  The hash now covers the PREDICATE ITSELF:
# the source text of every function that decides what leaves the deployable
# universe.  Edit any of them and the hash moves.
def predicate_sha16():
    import inspect
    src = []
    for fn in (excluded_by_flags, universes, news_flags, census_flags,
               _flag_true, dated_release_calendar):
        src.append(inspect.getsource(fn))
    blob = "\n".join(src).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def params_with_predicate():
    p = dict(PARAMS)
    p["deployable_predicate_sha16"] = predicate_sha16()
    p["deployable_predicate"] = (
        "a candidate leaves the DEPLOYABLE universe iff a NEWS_DISTANCE census "
        "flag (inside_default_window | pre_release_window) is set on it; the "
        "hold-crossing clause is a SEPARATE reading (R128 / CC-M2-22.3)")
    return p


# ------------------------------------------------------------------- seal ---
class SealRefusal(RuntimeError):
    """The scored bytes are not the sealed bytes."""


def git_blob_sha1(path):
    data = open(path, "rb").read()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def committed_sha1(path):
    rel = os.path.relpath(os.path.abspath(path), REPO)
    try:
        return subprocess.check_output(
            ["git", "-C", REPO, "rev-parse", "HEAD:%s" % rel],
            stderr=subprocess.DEVNULL).decode().strip()
    except subprocess.CalledProcessError:
        raise SealRefusal("%s is not committed at HEAD — nothing to score "
                          "against" % rel)


def seal_check(path, ref=None):
    """The bytes about to be scored must BE the sealed bytes.

    `ref` names the sealed path when the bytes live elsewhere (the mutant).
    """
    got, want = git_blob_sha1(path), committed_sha1(ref or path)
    if got != want:
        raise SealRefusal("%s: scored blob %s != committed HEAD blob %s — a "
                          "post-seal edit changes the score and is refused"
                          % (os.path.relpath(path, REPO), got, want))
    return got


def git_ordering():
    """The seal commits, in order, with the outcome-access audit.

    Returns (rows, verdict_lines).  An OUTCOME-BEARING path is anything the
    scoring pass writes or any roster/truth artefact; the round's commits must
    contain NONE of them.
    """
    log = subprocess.check_output(
        ["git", "-C", REPO, "log", "--reverse", "--format=%H\t%ct\t%s",
         "99ae1d5..HEAD"]).decode().splitlines()
    rows, bad = [], []
    for line in log:
        h, ct, subj = line.split("\t", 2)
        files = subprocess.check_output(
            ["git", "-C", REPO, "show", "--format=", "--name-only", h]
        ).decode().split()
        # R129: three of the five predicates were CASE-SENSITIVE against an
        # UPPERCASE artifact tree, so `E1_BLIND_SCORE_{ARMS,BARS,MARGINS}.tsv`
        # and `E1_BLIND_SCORE_REPORT.md` — four outcome artefacts — did not
        # match "blind_score", and the same hole existed for s14_*/panel_*.
        touch = [f for f in files if OUTCOME_RE.search(f)]
        rows.append([h[:7], ct, subj[:90], len(files), ";".join(touch)])
        if touch:
            bad.append((h[:7], touch))
    return rows, bad


# every predicate case-INsensitive, and the two path spellings the review
# found missing (s14_*, panel_*) written as what they are.
OUTCOME_RE = re.compile(r"(blind_score|unblind|s14|panel_|truth)", re.I)


def ledger_numstat():
    """The seal commits' ADDED/DELETED line counts — COMPUTED (R129).

    The report claimed "twelve seal commits ADDED rows and DELETED none (git
    numstat, day1 948 -> day12 12,418)" as a HARDCODED sentence with no numstat
    run.  It is run here and the sentence is written from the result.
    """
    rel = os.path.relpath(LEDGER, REPO)
    log = subprocess.check_output(
        ["git", "-C", REPO, "log", "--reverse", "--format=%H", "--", rel]
    ).decode().split()
    rows, cum = [], 0
    for h in log:
        out = subprocess.check_output(
            ["git", "-C", REPO, "show", "--format=", "--numstat", h, "--", rel]
        ).decode().split()
        if len(out) < 3:
            continue
        add, dele = int(out[0]), int(out[1])
        cum += add - dele
        rows.append({"commit": h[:7], "added": add, "deleted": dele,
                     "rows_after": cum})
    return {"n_commits": len(rows), "commits": rows,
            "total_added": sum(r["added"] for r in rows),
            "total_deleted": sum(r["deleted"] for r in rows),
            "deleted_none": int(all(r["deleted"] == 0 for r in rows))}


def declared_identity(decl, days):
    """Does the frozen arm, re-run as committed, reproduce the SEALED DECLARED
    column?  COMPUTED (R129) — it used to be a string literal in the report and
    the comparison was never performed.
    """
    n_rows = n_agree = 0
    missing, disagree = [], []
    for d in days:
        p = os.path.join(TRIAGE, "E1BLIND_D%d_ARMS.tsv" % d)
        if not os.path.exists(p):
            missing.append(os.path.relpath(p, REPO))
            continue
        with open(p) as fh:
            for r in csv.DictReader([l for l in fh if not l.startswith("#")],
                                    delimiter="\t"):
                if "DECLARED" not in r or r["cid"] not in decl:
                    continue
                n_rows += 1
                if r["DECLARED"] == decl[r["cid"]]:
                    n_agree += 1
                else:
                    disagree.append(r["cid"])
    return {"n_rows_compared": n_rows, "n_agree": n_agree,
            "n_disagree": len(disagree), "disagree_cids": disagree[:20],
            "arms_files_missing": missing,
            "reproduces": int(n_rows > 0 and not disagree and not missing)}


# ------------------------------------------------------------------- data ---
# R129: the 12 triage COMPAT indices are UNTRACKED cache files that drive every
# mechanical arm, every compliance flag and `open_utc`, and the committed
# receipt carried `input_sha256 = {}`.  They cannot be seal-checked against
# HEAD (they are not in HEAD), so their content hash is COMPUTED and stamped
# into the receipt, which is the strongest claim their status supports.
INDEX_SHA256 = OrderedDict()


def index_path(day):
    return os.path.join(TRIAGE, "E1BLIND_D%d_TRIAGE_INDEX_COMPAT.tsv" % day)


def read_index(day):
    p = index_path(day)
    data = open(p, "rb").read()
    INDEX_SHA256[os.path.relpath(p, REPO)] = hashlib.sha256(data).hexdigest()
    with open(p) as fh:
        return list(csv.DictReader([l for l in fh if not l.startswith("#")],
                                   delimiter="\t"))


def run_policy(module, index_path_, out_path, extra=()):
    """Run a frozen policy through its OWN committed CLI (never re-typed)."""
    cmd = ["/usr/bin/python3", os.path.join(_HERE, module + ".py"),
           "--index", index_path_, "--out", out_path] + list(extra)
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        return None, r.stderr.decode()[-300:]
    with open(out_path) as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    return {x["cid"]: x["call"] for x in rows}, ""


def earliest_baselines(idx_rows):
    """baseline_replay's arms, in-process (same code, no file churn).

    R05/R132: the class card is READ AT RUN TIME per (asset, class, strictly-
    prior era) and a class with no admissible card REFUSES the arm outright —
    the old table silently scored every unrecognised class at $0.00 and TOOK
    it at the CV0 threshold.  -> ({name: {cid: call}}, info).
    """
    return BR.build_arms(idx_rows)


# --------------------------------------------------------------- readings ---
NEWS_DISTANCE = os.path.join(REPO, "artifacts/cache/port/m2/news_compliance",
                             "NEWS_DISTANCE.tsv")


def census_flags(meta):
    """CC-M2-22.4 (BINDING): compliance is READ FROM THE CENSUS FLAGS.

    `NEWS_DISTANCE.tsv` carries one row per roster candidate within +/-15min
    of a dated release, with `inside_default_window` ([-10,+10] — the binding
    rule), `pre_release_window` and `held_into_window`.  D-N3: a BLANK
    `minutes_since_release` means a release is AHEAD of the row, never that
    the row is compliant — so nothing here is inferred from that field.

    THE ONE GAP THE FILE CANNOT COVER, and how it is closed: the file's reach
    is +/-15min, so a candidate that decides HOURS before a release and holds
    its phase-close seat THROUGH the restricted window is not in the file at
    all.  CC-M2-22.4 routes compliance through the census flags "incl.
    pre-window and held-into"; the held-into state for rows outside the file's
    reach is computed here with the census's OWN definition (news_census.py:
    400-408: any release's [-600,+600] window intersecting [decision, phase
    close]) and VERIFIED to agree with the file's `held_into_window` on every
    row the file does carry.  R128: the earlier docstring attributed a
    hold-crossing clause to CC-M2-22.4 as a VERBATIM quote; no such clause
    exists in that adjudication, which says only that compliance is read from
    the NEWS_DISTANCE flags (incl. pre-window and held-into).  The substance is
    authorised; the fabricated quote was a D-010 violation and is gone.

    R132: the file lives under /artifacts/, which `.gitignore` ignores, so on a
    fresh clone this returned `{}`, the red check downstream passed trivially
    with 0 disagreements, and the report printed "matches the census file on
    every one of the 0 rows".  Its ABSENCE is now a refusal.
    """
    if not os.path.exists(NEWS_DISTANCE):
        raise SealRefusal(
            "%s does not exist: CC-M2-22.4 reads compliance FROM THE FLAGS, so "
            "a DEPLOYABLE reading without the census file is refused, never "
            "computed against an empty join (R132)"
            % os.path.relpath(NEWS_DISTANCE, REPO))
    rows = {}
    with open(NEWS_DISTANCE) as fh:
        for r in csv.DictReader([l for l in fh if not l.startswith("#")],
                                delimiter="\t"):
            if r["cid"] in meta:
                rows[r["cid"]] = r
    return rows


# R132: `r["inside_default_window"] == "1"` is string equality against ONE
# spelling of true.  The vocabulary is declared and an unknown token REFUSES.
_TRUE = ("1", "true", "TRUE", "True", "yes", "Y", "y")
_FALSE = ("0", "", "false", "FALSE", "False", "no", "N", "n", "-")


def _flag_true(row, key):
    v = str(row.get(key, "")).strip()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    raise SealRefusal("NEWS_DISTANCE flag %s carries the unrecognised token %r "
                      "for %s — a compliance flag read on a guess is not a "
                      "compliance fact" % (key, v, row.get("cid")))


def dated_release_calendar():
    """(ts, names, source) of the DATED high-impact release universe.

    R36/R127: nothing in the calendar layer classifies impact, so the universe
    the D-077 rule is scored against is whatever `pattern_lib.release_calendar`
    returns — Employment Situation / CPI / FOMC statement and nothing else.
    If the context lane has landed a widened, impact-classified calendar, it is
    CONSUMED here; otherwise the narrow universe is used and NAMED, and
    `deployable_coverage` refuses the reading when it is too thin to mean what
    its label says.
    """
    import context as CTX
    for fn in ("high_impact_calendar", "release_calendar_impact",
               "impact_calendar"):
        f = getattr(CTX, fn, None)
        if not callable(f):
            continue
        try:
            cal = sorted(f())
        except Exception as e:                       # noqa: BLE001
            raise SealRefusal("context.%s() exists but failed (%r): the "
                              "DEPLOYABLE reading will not fall back to the "
                              "narrow calendar silently" % (fn, e))
        ts = np.array([int(c[0]) for c in cal], dtype=np.int64)
        names = [str(c[1]) for c in cal]
        return ts, names, "context.%s (R36 impact-classified)" % fn
    ts, names = PL.release_calendar()
    return (np.asarray(ts, dtype=np.int64), list(names),
            "pattern_lib.release_calendar = BLS Employment Situation + CPI + "
            "FOMC statement ONLY (R127: no impact classification exists in the "
            "calendar layer)")


def deployable_coverage(meta):
    """What share of the block's DAYS the dated-release universe touches.

    -> dict with `covered_days`, `n_days`, `coverage`, `ok`, `source`.  Below
    DEPLOYABLE_MIN_DAY_COVERAGE the DEPLOYABLE reading is REFUSED rather than
    published under a label that means something else.
    """
    ts, names, source = dated_release_calendar()
    days = sorted({m["date8"] for m in meta.values()})
    # a day is covered if any release falls inside the block's own local span
    # for that date (the union of every candidate's session window that day)
    open_utc = {}
    for m in meta.values():
        d = m["date8"]
        open_utc[d] = min(open_utc.get(d, m["open_utc"]), m["open_utc"])
    covered = []
    for d in days:
        lo = open_utc[d]
        j0 = int(np.searchsorted(ts, lo, side="left"))
        j1 = int(np.searchsorted(ts, lo + 86400, side="left"))
        if j1 > j0:
            covered.append(d)
    cov = len(covered) / float(len(days)) if days else 0.0
    return {"source": source, "n_days": len(days), "covered_days": covered,
            "n_covered": len(covered), "coverage": cov,
            "min_required": DEPLOYABLE_MIN_DAY_COVERAGE,
            "n_release_events": int(ts.size),
            "distinct_release_names": sorted(set(names)),
            "ok": int(cov >= DEPLOYABLE_MIN_DAY_COVERAGE)}


def news_flags(meta):
    """Per-cid D-077 flags from the DATED calendar.

    entry_in_window : |decision - release| <= 600s
    hold_crosses    : [entry, phase-close exit] intersects [rel-600, rel+600]
    """
    ts, _names, _src = dated_release_calendar()
    ts = np.asarray(ts, dtype=np.int64)
    flags = {}
    for cid, m in meta.items():
        dec_ts = m["dec_ts"]
        # the census's holding horizon: [decision, PHASE CLOSE] (never the
        # wall) — news_census.py:400-403
        exit_ts = m["open_utc"] + max(m["phase_close_sec"], m["dec_sec"])
        j = np.searchsorted(ts, dec_ts)
        near = ts[max(j - 2, 0):min(j + 2, ts.size)]
        # MINOR at :283 — the distance was UNSIGNED, so D-077.1's ordered
        # "value profiled BY MINUTES-SINCE-RELEASE" could not be produced from
        # this pass.  Both are carried: the signed offset (decision minus the
        # NEAREST release; negative = the release is ahead) and its magnitude.
        if near.size:
            k = int(np.argmin(np.abs(near - dec_ts)))
            signed = int(dec_ts - near[k])
        else:
            signed = None
        d_entry = abs(signed) if signed is not None else 10 ** 9
        k0 = np.searchsorted(ts, dec_ts - NEWS_WINDOW_SEC, side="left")
        k1 = np.searchsorted(ts, exit_ts + NEWS_WINDOW_SEC, side="right")
        cross = bool(k1 > k0)
        flags[cid] = {"dist_entry_sec": int(d_entry),
                      "signed_entry_sec": signed,
                      "entry_in_window": int(d_entry <= NEWS_WINDOW_SEC),
                      "hold_crosses": int(cross)}
    return flags


def slot_age(meta):
    """Seconds since the family's OWN generation anchor (D-077.1's profile).

    `family_discovery.NEWS_SLOTS` = the fixed 08:30 / 10:00 ET wall-clock
    slots, DST-correct through the tz database, plus the FOMC 14:00 ET slot;
    this is the set the NEWS_WINDOW family was CUT on (b10_generation_v3.
    news_release_offsets), NOT the dated calendar the prop rule names. The
    two-set divergence IS defect D31.
    """
    import datetime as dt
    from zoneinfo import ZoneInfo
    NY = ZoneInfo("America/New_York")
    # MINOR at :310-316: the 14:00 ET slot was asserted on EVERY day, while
    # generation gates it on actual FOMC dates only
    # (b10_generation_v3.py:157-164) — so the report's "133 of 135 sit in the
    # first 10 minutes after a generation SLOT" invented a 14:00 anchor on 11
    # of the 12 days.  The FOMC dates come from the calendar itself.
    ts, names, _src = dated_release_calendar()
    fomc_dates = {dt.datetime.fromtimestamp(int(t), NY).date()
                  for t, n in zip(ts, names) if "FOMC" in str(n).upper()}
    out = {}
    for cid, m in meta.items():
        d = dt.datetime.fromtimestamp(m["dec_ts"], NY)
        best = None
        for back in (0, 1, 2):
            day = (d - dt.timedelta(days=back)).date()
            slots = [(8, 30), (10, 0)]
            if day in fomc_dates:
                slots.append((14, 0))
            for hh, mm in slots:
                t = int(dt.datetime(day.year, day.month, day.day, hh, mm,
                                    tzinfo=NY).timestamp())
                if t <= m["dec_ts"] and (best is None or t > best):
                    best = t
        out[cid] = (m["dec_ts"] - best) if best is not None else -1
    return out


def excluded_by_flags(cid, meta, flags, cflags, include_hold=True):
    """CC-M2-22.4: excluded iff a census ENTRY flag is true for the cid — and,
    in the hold reading, if the seat's hold crosses a restricted window.

    R128: the hold-crossing clause silently resolved a spec conflict in the
    direction that LOWERS the reader and was the ENTIRE SCIENCE->DEPLOYABLE
    difference.  CC-M2-22.3 rules the held-into-window exposure "a DEPLOYMENT-
    POSTURE item ... not a generation change"; the pass struck on it anyway,
    removing 622 candidates including the reader's 7 best takes.  Both
    readings are emitted now and each is labelled, so nothing is resolved
    silently in either direction.
    """
    r = cflags.get(cid)
    if r is not None and (_flag_true(r, "inside_default_window")
                          or _flag_true(r, "pre_release_window")):
        return True
    if not include_hold:
        return False
    if r is not None and _flag_true(r, "held_into_window"):
        return True
    return bool(flags[cid]["hold_crosses"])


def universes(meta, flags, cflags, deployable_ok=True):
    """The scored readings.

    SCIENCE                    every call (the learning reading).
    DEPLOYABLE_ENTRY_VETO      CC-M2-22.3/22.4: the ENTRY veto only — the rule
                               D-077-UPDATE(1) actually states.
    DEPLOYABLE_ENTRY_PLUS_HOLD the entry veto AND the held-into-window
                               exposure, i.e. the deployment POSTURE reading.
    NAME-STRUCK-SUPERSEDED     SUPERSEDED by CC-M2-22.1, retained only to
                               reconcile the sealed summary's name-based
                               26-of-40 count.

    `deployable_ok=False` (R127: the dated-release calendar does not cover
    enough of the block's days for a compliance label to mean what it says)
    REFUSES both deployable readings rather than publishing them.
    """
    allc = set(meta)
    out = OrderedDict((("SCIENCE", allc),))
    if deployable_ok:
        out["DEPLOYABLE_ENTRY_VETO"] = {
            c for c in allc
            if not excluded_by_flags(c, meta, flags, cflags, include_hold=False)}
        out["DEPLOYABLE_ENTRY_PLUS_HOLD"] = {
            c for c in allc
            if not excluded_by_flags(c, meta, flags, cflags, include_hold=True)}
        out["NAME-STRUCK-SUPERSEDED"] = {
            c for c in out["DEPLOYABLE_ENTRY_PLUS_HOLD"]
            if meta[c]["cls"] != NEWS_FAMILY}
    return out


# ---------------------------------------------------------------- scoring ---
def ceiling(meta, cids, metric="close"):
    """DP ceiling over exactly `cids`, per session-asset.  -> {(asset,d8): $}"""
    by = defaultdict(list)
    for c in sorted(cids):          # MINOR: a set iteration made the float
        m = meta[c]                 # accumulation order hash-seed dependent
        by[(m["asset"], m["date8"])].append(m)
    out = {}
    for key, ms in sorted(by.items()):
        items = []
        for m in ms:
            val = m["cert_close_usd"] if metric == "close" else m["cert_peak_usd"]
            end = (m["exit_close_sec"] if metric == "close"
                   else m["exit_peak_sec"])
            # MINOR: panel_score.dp_ceiling puts the roster IID in slot 5 and
            # this built the ROW index there, so the two could pick different
            # optimal schedules on a value tie.  Same slot, same tie-break.
            items.append((m["dec_sec"], end, val, m["dec_sec"],
                          int(PS.A.roster(m["asset"])["iid"][m["row"]]),
                          m["cid"]))
        total, _chosen = CC.dp_schedule(items)
        out[key] = float(total)
    return out


def arm_records(callmap, meta, cids):
    """panel_score-shaped records for one arm restricted to `cids`.

    R132: `callmap.get(c, "SKIP")` silently scored an arm that emitted fewer
    rows than the index as SKIPPING the remainder, and that arm fed bar (a)
    directly.  A missing call is a missing call.
    """
    missing = [c for c in cids if c not in callmap]
    if missing:
        raise SealRefusal(
            "arm did not call %d of %d candidates (e.g. %s): a policy that "
            "emitted fewer rows than the index has no day-complete replay and "
            "is not scored as skipping the remainder"
            % (len(missing), len(cids), sorted(missing)[:3]))
    return [{"cid": c, "call": callmap[c], "outcome": meta[c],
             "conf": meta[c].get("conf", "C"), "has_interaction": 0}
            for c in sorted(cids)]


def score_arm(callmap, meta, cids, ceil_map):
    recs = arm_records(callmap, meta, cids)
    takes = [r["outcome"] for r in recs if r["call"] == "TAKE"]
    skips = [r["outcome"] for r in recs if r["call"] == "SKIP"]
    o = {"n_calls": len(recs), "n_takes": len(takes), "n_skips": len(skips)}
    for m in ("close", "peak"):
        k = "cert_%s_usd" % m
        mt = float(np.mean([x[k] for x in takes])) if takes else None
        ms = float(np.mean([x[k] for x in skips])) if skips else None
        o["mean_take_%s" % m] = mt
        o["mean_skip_%s" % m] = ms
        o["lift_%s" % m] = (mt / ms) if (ms is not None and ms > 0
                                         and mt is not None) else None
        nw = sum(x["winner_" + m] for x in takes)
        o["n_winner_%s" % m] = int(nw)
        o["precision_%s" % m] = (nw / len(takes)) if takes else None
        o["missed_%s" % m] = int(sum(x["winner_" + m] for x in skips))
    rows, tot = PS.replay(recs, "close")
    per_day = defaultdict(float)
    per_sess = {}
    for r in rows:
        per_day[r["date8"]] += r["realised_usd"]
        per_sess[(r["asset"], r["date8"])] = r["realised_usd"]
    o["replay_usd"] = tot["realised_usd"]
    o["n_seated"] = tot["n_seated"]
    o["n_forfeited"] = tot["n_forfeited"]
    o["ceiling_usd"] = float(sum(ceil_map.values()))
    o["capture"] = (o["replay_usd"] / o["ceiling_usd"]) if o["ceiling_usd"] > 0 \
        else None
    # R126 MINOR: `per_day.get(d, 0.0)` scored a day the arm has no entry for
    # as exactly $0.00, which is right when the arm took no seat and silently
    # wrong if the arm was not run for that day.  The two are distinguished:
    # `days_called` is the set the arm actually decided on, and every consumer
    # of `per_day` checks it before reading a zero as a result.
    o["days_called"] = sorted({meta[c]["date8"] for c in cids
                               if c in callmap})
    o["per_day"] = {d: per_day.get(d, 0.0) for d in sorted(
        {meta[c]["date8"] for c in cids})}
    o["per_session"] = {k: per_sess.get(k, 0.0) for k in ceil_map}
    o["seat_cids"] = PS.replay_seat_cids(recs, "close")
    o["dp_seat_cids"] = PS.dp_seat_cids(recs, "close")
    o["take_cids"] = {r["cid"] for r in recs if r["call"] == "TAKE"}
    # CC-M2-21.4: the DP seat-split is the MANDATORY companion to the greedy
    # replay (the pooled law).  Value the take-pool's own optimal schedule.
    o["dp_seat_usd"] = float(sum(meta[c]["cert_close_usd"]
                                 for c in o["dp_seat_cids"]))
    o["n_dp_seats"] = len(o["dp_seat_cids"])
    # the CC-M1-8 companion reading of the same replay
    _rp, totp = PS.replay(recs, "peak")
    o["replay_peak_usd"] = totp["realised_usd"]
    # bar (b) arithmetic when the denominator is not positive: panel_score
    # refuses the ratio, so the raw ratio and the difference are both carried
    o["ratio_close_raw"] = ((o["mean_take_close"] / o["mean_skip_close"])
                            if (o["mean_skip_close"] not in (None, 0.0)
                                and o["mean_take_close"] is not None)
                            else None)
    o["take_minus_skip_close"] = ((o["mean_take_close"] - o["mean_skip_close"])
                                  if (o["mean_take_close"] is not None
                                      and o["mean_skip_close"] is not None)
                                  else None)
    return o


# ------------------------------------------------------------- inference ---
def cluster_mean(y, clusters):
    """Intercept-only GEE (identity link) — mean with a CR1 cluster sandwich.

    batch4_census.gee_multi with a ZERO-column design is exactly the
    intercept-only Liang-Zeger estimator; it is reused rather than re-typed.
    """
    y = np.asarray(y, dtype=np.float64)
    cl = np.asarray(clusters)
    if y.size < 2:
        return None
    g = B4.gee_multi(y, np.zeros((y.size, 0)), cl, link="identity")
    if g is None:
        return None
    beta = float(g["beta"][0])
    se = float(g["se_cr1"][0])
    z = (beta / se) if se > 0 else float("nan")
    df = max(g["n_clusters"] - 1, 1)
    return {"mean": beta, "se_cr1": se, "se_cr0": float(g["se_cr0"][0]),
            "z": z, "p_normal": float(2 * SST.norm.sf(abs(z))),
            "p_t": float(2 * SST.t.sf(abs(z), df)),
            "n": g["n"], "n_clusters": g["n_clusters"], "df": df}


def sign_test(y):
    y = np.asarray(y, dtype=np.float64)
    pos = int((y > 0).sum())
    neg = int((y < 0).sum())
    nz = pos + neg
    p = float(SST.binomtest(pos, nz, 0.5).pvalue) if nz else None
    return {"n_pos": pos, "n_neg": neg, "n_zero": int((y == 0).sum()),
            "p_sign": p}


def gee_row(y, x, clusters, link):
    g = B4.gee_multi(y, np.asarray(x, dtype=np.float64), clusters, link=link)
    if g is None:
        return None
    beta = float(g["beta"][1])
    se = float(g["se_cr1"][1])
    z = (beta / se) if se > 0 else float("nan")
    return {"beta": beta, "se_cr1": se, "z": z,
            "p": float(2 * SST.norm.sf(abs(z))),
            "n": g["n"], "n_clusters": g["n_clusters"]}


# ===================================================================== main ==
def build(days):
    """-> (meta, arms, idx_by_cid, holders, arm_notes)"""
    ledger = PS.parse_ledger(LEDGER)
    reader = {r["cid"]: r["call"] for r in ledger}
    conf = {r["cid"]: r["conf"] for r in ledger}
    # the reader's OWN committed seating (one position per (asset,phase) cell,
    # `seat_holder=<cid>` in the sealed interaction field) — a diagnostic, not
    # the scoring law (CC-M2-10.3 replay is the law)
    holders = set()
    for r in ledger:
        m = re.search(r"seat_holder=([^;]*)", r.get("interaction") or "")
        v = (m.group(1).strip() if m else "-")
        if v not in ("-", ""):
            holders.add(v)
    idx_rows, idx_by_cid = {}, {}
    for d in days:
        rows = read_index(d)
        idx_rows[d] = rows
        for r in rows:
            idx_by_cid[r["cid"]] = r
    if set(idx_by_cid) != set(reader):
        raise SealRefusal("index/ledger cid sets differ: index-only %d, "
                          "ledger-only %d"
                          % (len(set(idx_by_cid) - set(reader)),
                             len(set(reader) - set(idx_by_cid))))
    meta = {}
    for cid, ir in idx_by_cid.items():
        o = dict(PS.outcome(cid))
        o["cls"] = ir["cls"]
        o["phase_dec"] = ir["phase_dec"]
        o["clock"] = ir["clock"]
        o["dec_ts"] = int(float(ir["dec_ts"]))
        o["open_utc"] = o["dec_ts"] - int(float(ir["sec"]))
        # R132: the cid sets were just proven equal, so a `.get(cid, "C")`
        # default here could only ever hide a contradiction of that proof.
        o["conf"] = conf[cid]
        o["phase_close_sec"] = int(PS.A.roster(o["asset"])["phase_close_sec"]
                                   [o["row"]])
        meta[cid] = o

    arms = OrderedDict()
    arms["READER"] = reader
    # R129/R132: what each arm actually did is a RECORD, not a sentence in the
    # report.  `arm_notes` carries the per-arm outcome (ran / refused / the
    # baseline card refusals) and the report prints it from here.
    notes = OrderedDict()
    notes["READER"] = {"status": "SEALED_LEDGER", "detail": LEDGER}
    tmp = tempfile.mkdtemp(prefix="e1blindscore_", dir=OUT)
    try:
        decl, base, preds = {}, defaultdict(dict), defaultdict(dict)
        base_info = {}
        for d in days:
            ip = index_path(d)
            cm, err = run_policy("e1_blind_declared_policy", ip,
                                 os.path.join(tmp, "decl_%d.tsv" % d),
                                 ["--quiet"])
            if cm is None:
                raise RuntimeError("declared arm failed on day %d: %s" % (d, err))
            decl.update(cm)
            cmaps, info = earliest_baselines(idx_rows[d])
            base_info[d] = info
            for name, cmap in cmaps.items():
                base[name].update(cmap)
            for mod in PREDECESSORS:
                cm, err = run_policy(mod, ip,
                                     os.path.join(tmp, "%s_%d.tsv" % (mod, d)))
                if cm is None:
                    preds[mod]["__error__"] = err
                    continue
                preds[mod].update(cm)
        arms["DECLARED"] = decl
        notes["DECLARED"] = {"status": "RAN_AS_COMMITTED",
                             "detail": "e1_blind_declared_policy.py CLI on all "
                                       "%d days" % len(days)}
        # a CV arm is emitted only on the days whose cards resolved; an arm
        # that is not defined on every day is REFUSED whole rather than being
        # scored as skipping the days it never saw.
        n_ref = sum(base_info[d]["n_rows_card_refused"] for d in days)
        for name in sorted(base):
            arms[name] = base[name]
            notes[name] = {"status": "RAN", "detail": "baseline_replay arm"}
        for name, why in sorted(
                {k: v for d in days
                 for k, v in base_info[d]["refused_arms"].items()}.items()):
            notes[name] = {"status": "REFUSED", "detail": why}
        notes["__baseline_card_refusals__"] = {
            "status": "COUNT", "detail": "%d candidate-rows carry no "
            "strictly-prior class card (R01/R05)" % n_ref}
        for mod in PREDECESSORS:
            aname = mod.replace("_policy", "").upper()
            if "__error__" in preds[mod]:
                sys.stderr.write("UNRUNNABLE %s: %s\n"
                                 % (mod, preds[mod]["__error__"]))
                notes[aname] = {"status": "REFUSED",
                                "detail": "did not run: %s"
                                          % preds[mod]["__error__"][:200]}
                continue
            arms[aname] = preds[mod]
            notes[aname] = {"status": "RAN_AS_COMMITTED",
                            "detail": "%s.py CLI on all %d days"
                                      % (mod, len(days))}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # R132 (:368): every arm must have called EVERY candidate of the index.
    # An arm that emitted fewer rows was previously scored as skipping the
    # remainder, and that arm fed bar (a) directly.
    for name in list(arms):
        missing = set(idx_by_cid) - set(arms[name])
        extra = set(arms[name]) - set(idx_by_cid)
        if missing or extra:
            notes[name] = {"status": "REFUSED",
                           "detail": "cid set != index (missing %d, extra %d) "
                                     "— not scored as skipping the remainder"
                                     % (len(missing), len(extra))}
            del arms[name]
    return meta, arms, idx_by_cid, holders, notes


MECHANICAL = None          # filled in main(): the CC-M2-6 baseline set


DEPLOY_BINDING = "DEPLOYABLE_ENTRY_VETO"


def reading_sets(unis):
    """Report-side aliases for the readings (R127/R128).

    There are now TWO deployable readings and either may be REFUSED, so the
    report reads them through here: `DEPLOYABLE` names the BINDING one (the
    ENTRY veto — the rule D-077-UPDATE(1) states and the one CC-M2-22.3 leaves
    standing), and a refused reading is an EMPTY set with `_refused` set, never
    a missing key that would crash or a silent zero.
    """
    U = dict(unis)
    U.setdefault("DEPLOYABLE_ENTRY_VETO", set())
    U.setdefault("DEPLOYABLE_ENTRY_PLUS_HOLD", set())
    U.setdefault("NAME-STRUCK-SUPERSEDED", set())
    U["DEPLOYABLE"] = U[DEPLOY_BINDING]
    U["_refused"] = int(DEPLOY_BINDING not in unis)
    return U


def is_mechanical(name):
    """The CC-M2-6 mechanical baseline set.

    R126: `DECLARED` was excluded although CC-M2-20.2 calls the frozen declared
    policy "a mechanical arm beside it" — it reads no sheet and takes no
    judgement, which is the whole definition.
    """
    return (name.startswith("BASE_EARLIEST") or name.startswith("E1D")
            or name == "DECLARED")


def raw_ratio_bar(uname, s_r):
    """The `b_lift_close_raw_ratio` row (R104), as a testable function.

    The raw ratio is a REFUSED statistic wherever the SKIP mean is not
    positive — it is then a ratio of two negatives and reads as a PASS for a
    take pool that lost more than the skip pool.  A bar comparison against a
    refused statistic emits NULL in BOTH the bar_value and the
    statistic_minus_bar columns, which are the two a mechanical reader keys on.
    """
    ms = s_r["mean_skip_close"]
    ratio = s_r["ratio_close_raw"]
    skip_ok = (ms is not None and ms > 0)
    return [uname, "b_lift_close_raw_ratio", "", ratio,
            None, None, None, None, None, None, None, None,
            BAR_LIFT if skip_ok else None,
            ((ratio - BAR_LIFT) if (skip_ok and ratio is not None) else None)]


def bar_a_references(scored_reading, totals=None):
    """The three LABELLED bar-(a) references (R126).

    -> {"eligible", "preregistered", "median", "max_in_sample", "worst"}.
    The BAR is `worst` (positive against all); `max_in_sample` is the order
    statistic the committed run used as the bar and is labelled as such.
    """
    mech = eligible_reference_arms(scored_reading)
    names = sorted(n for n, _v in mech)
    if not names:
        return {"eligible": [], "preregistered": None, "median": None,
                "max_in_sample": None, "worst": None}
    tot = (totals if totals is not None
           else {n: scored_reading[n]["replay_usd"] for n in names})
    order = sorted(names, key=lambda n: (tot[n], n))   # explicit tie-break
    return {"eligible": names,
            "preregistered": (PREREGISTERED_ARM if PREREGISTERED_ARM in names
                              else None),
            "median": order[(len(order) - 1) // 2],
            "max_in_sample": order[-1],
            "worst": order[0]}


def eligible_reference_arms(scored_reading):
    """The arms a bar-(a) reference may be drawn from.

    R126: a DEGENERATE ZERO-TAKE arm was eligible to be "best" — in the
    NAME-STRUCK reading `BASE_EARLIEST_CV650` had n_takes=0 and replay=0, so
    had every real arm gone negative the bar would have been set by DOING
    NOTHING.  An arm that never takes a seat is not a baseline.
    """
    return [(n, v) for n, v in scored_reading.items()
            if is_mechanical(n) and v["n_takes"] > 0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mutant", action="store_true",
                    help="red-first: flip one sealed TAKE and prove the hash "
                         "check refuses it and the score moves")
    ap.add_argument("--no-publish", action="store_true",
                    help="write only under artifacts/cache/ — do NOT copy the "
                         "report and the gate inputs into evidence/port_m2/ "
                         "(a smoke test must not overwrite committed "
                         "evidence)")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    MC.verify_spec(force=True)
    sealed_sha = seal_check(LEDGER)
    ord_rows, ord_bad = git_ordering()
    numstat = ledger_numstat()

    days = list(range(1, N_DAYS + 1))
    meta, arms, idx_by_cid, holders, arm_notes = build(days)
    flags = news_flags(meta)
    slots = slot_age(meta)
    cflags = census_flags(meta)
    # RED CHECK: our held-into recomputation must agree with the census file
    # on every row the file carries (the file's reach is only +/-15min).
    if not cflags:
        raise SealRefusal(
            "NEWS_DISTANCE.tsv carries none of the round's %d candidates: the "
            "agreement check would pass trivially on 0 rows (R132)"
            % len(meta))
    disagree = [c for c, r in cflags.items()
                if int(_flag_true(r, "held_into_window"))
                != flags[c]["hold_crosses"]]
    dis_inside = [c for c, r in cflags.items()
                  if int(_flag_true(r, "inside_default_window"))
                  != flags[c]["entry_in_window"]]
    if disagree or dis_inside:
        raise SealRefusal(
            "census-flag agreement check failed: %d held_into and %d "
            "inside_window disagreements against NEWS_DISTANCE.tsv"
            % (len(disagree), len(dis_inside)))
    # R127: is the dated-release universe wide enough for a reading labelled
    # DEPLOYABLE to mean prop-firm compliance at all?
    cover = deployable_coverage(meta)
    if not cover["ok"]:
        sys.stderr.write(
            "DEPLOYABLE READING REFUSED (R127): the dated high-impact release "
            "universe (%s) touches %d of the block's %d days (%.3f < %.2f "
            "declared minimum). A reading built on it is an %s reading, not a "
            "prop-firm compliance reading, so it is NOT published.\n"
            % (cover["source"], cover["n_covered"], cover["n_days"],
               cover["coverage"], cover["min_required"],
               "/".join(cover["distinct_release_names"][:4])))
    unis = universes(meta, flags, cflags, deployable_ok=bool(cover["ok"]))
    U = reading_sets(unis)
    decl_ident = declared_identity(arms.get("DECLARED", {}), days)

    # self-check: the SCIENCE ceiling must equal panel_score.dp_ceiling
    ceil_sci = ceiling(meta, unis["SCIENCE"])
    for (asset, d8), v in sorted(ceil_sci.items()):
        ref = PS.dp_ceiling(asset, d8, "close")[0]
        if abs(ref - v) > 1e-6:
            raise SealRefusal("ceiling self-check failed on %s %s: %.2f vs "
                              "panel_score %.2f" % (asset, d8, v, ref))

    scored = OrderedDict()
    ceils = OrderedDict()
    for uname, cids in unis.items():
        cm = ceiling(meta, cids)
        ceils[uname] = cm
        scored[uname] = OrderedDict(
            (aname, score_arm(cmap, meta, cids, cm))
            for aname, cmap in arms.items())

    # ------------------------------------------------------------ writing --
    # R131: the hash covers the exclusion PREDICATE's own source, so a
    # compliance-rule change cannot leave it byte-identical again.
    phash = MC.params_hash(params_with_predicate())
    W = lambda n, cols, rows, extra=(): MC.write_tsv(  # noqa: E731
        os.path.join(OUT, n), SECTION, phash, list(cols), rows, extra=extra)

    # 1. the arm table, per reading
    full_ceiling = float(sum(ceils["SCIENCE"].values()))
    arm_rows = []
    for uname in scored:
        for aname, s in scored[uname].items():
            arm_rows.append([uname, aname, is_mechanical(aname),
                             s["n_calls"], s["n_takes"],
                             s["mean_take_close"], s["mean_skip_close"],
                             s["lift_close"], s["ratio_close_raw"],
                             s["take_minus_skip_close"],
                             s["mean_take_peak"],
                             s["mean_skip_peak"], s["lift_peak"],
                             s["n_winner_close"], s["precision_close"],
                             s["missed_close"], s["replay_usd"],
                             s["ceiling_usd"], s["capture"],
                             (s["replay_usd"] / full_ceiling), s["n_seated"],
                             s["n_forfeited"], s["n_dp_seats"],
                             s["dp_seat_usd"], s["replay_peak_usd"]])
    W("E1_BLIND_SCORE_ARMS.tsv",
      ("reading", "arm", "is_mechanical_baseline", "n_calls", "n_takes",
       "mean_take_close_usd", "mean_skip_close_usd", "lift_close",
       "ratio_close_raw", "take_minus_skip_close_usd",
       "mean_take_peak_usd", "mean_skip_peak_usd", "lift_peak",
       "n_winner_takes", "winner_precision_close", "winners_missed_in_skips",
       "replay_realised_usd", "dp_ceiling_usd", "replay_capture",
       "capture_vs_full_universe_ceiling", "n_seated", "n_forfeited",
       "n_dp_seats", "dp_seat_value_usd", "replay_realised_peak_usd"),
      arm_rows,
      extra=["CC-M2-21.4: the GREEDY chronological one-position replay is the "
             "pooled law; the DP seat-split (n_dp_seats/dp_seat_value_usd) is "
             "its mandatory companion diagnostic; PHASE-CLOSE seating "
             "(CC-M2-10.3)",
             "lift_close is EMPTY wherever mean_skip_close <= 0: panel_score "
             "refuses a ratio against a non-positive denominator, so "
             "ratio_close_raw and take_minus_skip_close_usd carry the "
             "arithmetic instead"])

    # 2. per-day sequence + per-day margins
    d8s = sorted({meta[c]["date8"] for c in meta})
    day_rows = []
    for uname in scored:
        cm = ceils[uname]
        day_ceil = defaultdict(float)
        for (asset, d8), v in cm.items():
            day_ceil[d8] += v
        for aname, s in scored[uname].items():
            for i, d8 in enumerate(d8s, 1):
                r = s["per_day"].get(d8, 0.0)
                day_rows.append([uname, aname, i, d8, r, day_ceil[d8],
                                 (r / day_ceil[d8]) if day_ceil[d8] > 0
                                 else None])
    W("E1_BLIND_SCORE_PERDAY.tsv",
      ("reading", "arm", "day", "date8", "replay_realised_usd",
       "day_dp_ceiling_usd", "day_capture"), day_rows)

    # 3. margins + inference
    marg_rows = []
    bars = []
    for uname in scored:
        s_r = scored[uname]["READER"]
        rr = np.array([s_r["per_day"].get(d, 0.0) for d in d8s])
        for aname, s in scored[uname].items():
            if aname == "READER":
                continue
            bb = np.array([s["per_day"].get(d, 0.0) for d in d8s])
            m = rr - bb
            cmn = cluster_mean(m, np.array(d8s))
            sg = sign_test(m)
            # session grain, clustered on DAY
            keys = sorted(s_r["per_session"])
            ms = np.array([s_r["per_session"][k] - s["per_session"][k]
                           for k in keys])
            cms = cluster_mean(ms, np.array([k[1] for k in keys]))
            marg_rows.append([uname, aname, is_mechanical(aname),
                              float(m.sum()), cmn["mean"], cmn["se_cr1"],
                              cmn["z"], cmn["p_normal"], cmn["p_t"],
                              cmn["n_clusters"], sg["n_pos"], sg["n_neg"],
                              sg["p_sign"],
                              cms["mean"] if cms else None,
                              cms["se_cr1"] if cms else None,
                              cms["z"] if cms else None,
                              cms["p_normal"] if cms else None,
                              cms["n"] if cms else None,
                              cms["n_clusters"] if cms else None])
        # ---- BAR (a).  R126: the reference arm used to be the max of ~13
        # arms taken ON THE EVALUATION DAYS THEMSELVES — a winner's-curse
        # comparison that biases the reader's margin DOWNWARD by an unquoted
        # amount.  Four readings are emitted and each is labelled: the margin
        # against EVERY eligible arm, the conservative bar (positive against
        # ALL of them), the PRE-REGISTERED arm, the MEDIAN arm, and the
        # max-of-arms order statistic, which carries a NULL bar because it is
        # not a bar.
        mech = eligible_reference_arms(scored[uname])
        per_arm = {}
        for n, v in sorted(mech):
            bb = np.array([v["per_day"].get(d, 0.0) for d in d8s])
            mm = rr - bb
            per_arm[n] = (mm, cluster_mean(mm, np.array(d8s)), sign_test(mm))
            c_, g_ = per_arm[n][1], per_arm[n][2]
            bars.append([uname, "a_margin_vs_%s" % n, n, float(mm.sum()),
                         c_["mean"], c_["se_cr1"], c_["z"], c_["p_normal"],
                         c_["p_t"], g_["n_pos"], g_["n_neg"], g_["p_sign"],
                         0.0, float(mm.sum())])
        if per_arm:
            worst = min(sorted(per_arm),
                        key=lambda n: (float(per_arm[n][0].sum()), n))
            mw, cw, gw = per_arm[worst]
            bars.append([uname, "a_bar_positive_against_ALL_mechanical", worst,
                         float(mw.sum()), cw["mean"], cw["se_cr1"], cw["z"],
                         cw["p_normal"], cw["p_t"], gw["n_pos"], gw["n_neg"],
                         gw["p_sign"], 0.0, float(mw.sum())])
            if PREREGISTERED_ARM in per_arm:
                mp, cp, gp = per_arm[PREREGISTERED_ARM]
                bars.append([uname, "a_margin_over_PREREGISTERED_arm",
                             PREREGISTERED_ARM, float(mp.sum()), cp["mean"],
                             cp["se_cr1"], cp["z"], cp["p_normal"], cp["p_t"],
                             gp["n_pos"], gp["n_neg"], gp["p_sign"], 0.0,
                             float(mp.sum())])
            else:
                bars.append([uname, "a_margin_over_PREREGISTERED_arm",
                             PREREGISTERED_ARM + " (REFUSED: arm not built)",
                             None, None, None, None, None, None, None, None,
                             None, 0.0, None])
            refs = bar_a_references(scored[uname])
            med_n = refs["median"]
            mm, cm_, gm = per_arm[med_n]
            bars.append([uname, "a_margin_over_MEDIAN_mechanical_arm", med_n,
                         float(mm.sum()), cm_["mean"], cm_["se_cr1"],
                         cm_["z"], cm_["p_normal"], cm_["p_t"], gm["n_pos"],
                         gm["n_neg"], gm["p_sign"], 0.0, float(mm.sum())])
            best_n = refs["max_in_sample"]              # explicit tie-break
            mb, cb, gb = per_arm[best_n]
            bars.append([uname,
                         "a_margin_over_MAX_arm_IN_SAMPLE_ORDER_STATISTIC",
                         best_n, float(mb.sum()), cb["mean"], cb["se_cr1"],
                         cb["z"], cb["p_normal"], cb["p_t"], gb["n_pos"],
                         gb["n_neg"], gb["p_sign"], None, None])
        lift = s_r["lift_close"]
        bars.append([uname, "b_lift_close", "", lift, None, None, None, None,
                     None, None, None, None, BAR_LIFT,
                     (lift - BAR_LIFT) if lift is not None else None])
        # R104: the raw ratio is a REFUSED statistic wherever the SKIP mean is
        # not positive (it is then a ratio of two negatives, and the committed
        # table published `2.105054 ... +0.805054` for a TAKE pool $78.31 per
        # candidate WORSE than the SKIP pool).  A bar comparison against a
        # refused statistic emits NULL.
        bars.append(raw_ratio_bar(uname, s_r))
        bars.append([uname, "b_mean_take_close_usd", "",
                     s_r["mean_take_close"], None, None, None, None, None,
                     None, None, None, None, None])
        bars.append([uname, "b_mean_skip_close_usd", "",
                     s_r["mean_skip_close"], None, None, None, None, None,
                     None, None, None, None, None])
        bars.append([uname, "b_lift_peak_companion", "", s_r["lift_peak"],
                     None, None, None, None, None, None, None, None, BAR_LIFT,
                     (s_r["lift_peak"] - BAR_LIFT)
                     if s_r["lift_peak"] is not None else None])
        cap = s_r["capture"]
        bars.append([uname, "c_replay_capture", "", cap, None, None, None,
                     None, None, None, None, None, BAR_CAPTURE,
                     (cap - BAR_CAPTURE) if cap is not None else None])
        bars.append([uname, "c_replay_capture_vs_full_ceiling", "",
                     s_r["replay_usd"] / full_ceiling, None, None, None, None,
                     None, None, None, None, BAR_CAPTURE,
                     s_r["replay_usd"] / full_ceiling - BAR_CAPTURE])
        # the same three against the DECLARED arm, for the record
        sd = scored[uname]["DECLARED"]
        bd = np.array([sd["per_day"].get(d, 0.0) for d in d8s])
        md = rr - bd
        cmd = cluster_mean(md, np.array(d8s))
        sgd = sign_test(md)
        bars.append([uname, "a2_margin_over_DECLARED_arm", "DECLARED",
                     float(md.sum()), cmd["mean"], cmd["se_cr1"], cmd["z"],
                     cmd["p_normal"], cmd["p_t"], sgd["n_pos"], sgd["n_neg"],
                     sgd["p_sign"], 0.0, float(md.sum())])
        bars.append([uname, "b2_lift_close_DECLARED", "DECLARED",
                     sd["lift_close"], None, None, None, None, None, None,
                     None, None, BAR_LIFT,
                     (sd["lift_close"] - BAR_LIFT)
                     if sd["lift_close"] is not None else None])
        bars.append([uname, "c2_replay_capture_DECLARED", "DECLARED",
                     sd["capture"], None, None, None, None, None, None, None,
                     None, BAR_CAPTURE,
                     (sd["capture"] - BAR_CAPTURE)
                     if sd["capture"] is not None else None])
    W("E1_BLIND_SCORE_MARGINS.tsv",
      ("reading", "vs_arm", "is_mechanical_baseline", "sum_margin_usd",
       "mean_day_margin_usd", "se_cr1", "z", "p_normal", "p_t_df11",
       "n_day_clusters", "days_positive", "days_negative", "p_sign",
       "sess_mean_margin_usd", "sess_se_cr1", "sess_z", "sess_p", "sess_n",
       "sess_clusters"), marg_rows,
      extra=["day-paired margins of the REPLAY realised dollars; GEE "
             "intercept-only, Liang-Zeger sandwich, Cameron-Miller CR1"])
    W("E1_BLIND_SCORE_BARS.tsv",
      ("reading", "bar", "reference_arm", "statistic", "mean_day_margin_usd",
       "se_cr1", "z", "p_normal", "p_t_df11", "days_positive",
       "days_negative", "p_sign", "bar_value", "statistic_minus_bar"), bars,
      extra=["CC-M2-6 pre-registered bars, computed as registered; the "
             "VERDICT is the orchestrator's (D-075)"])

    # 4. news / D-077 census of the round's own calls
    news_rows = []
    reader_takes = {c for c in unis["SCIENCE"] if arms["READER"][c] == "TAKE"}
    reader_seats = scored["SCIENCE"]["READER"]["seat_cids"]
    for c in sorted(reader_takes):
        f = flags[c]
        m = meta[c]
        news_rows.append([c, m["asset"], m["date8"], m["clock"],
                          MC.display_name(m["cls"]), m["cls"],
                          m["side"], int(c in reader_seats), f["dist_entry_sec"],
                          f["signed_entry_sec"],
                          f["entry_in_window"], f["hold_crosses"],
                          slots[c], (slots[c] // 60 if slots[c] >= 0 else None),
                          int(c in cflags),
                          (cflags[c]["inside_default_window"] if c in cflags
                           else "0"),
                          (cflags[c]["pre_release_window"] if c in cflags
                           else "0"),
                          (cflags[c]["held_into_window"] if c in cflags
                           else str(flags[c]["hold_crosses"])),
                          (cflags[c]["release_name"] if c in cflags else ""),
                          int(c in U["DEPLOYABLE"]),
                          int(c in U["DEPLOYABLE_ENTRY_PLUS_HOLD"]),
                          int(c in U["NAME-STRUCK-SUPERSEDED"]),
                          m["cert_close_usd"], m["winner_close"]])
    news_extra = [
        "CC-M2-22.4: flag_* columns are READ FROM "
        "artifacts/cache/port/m2/news_compliance/NEWS_DISTANCE.tsv where the "
        "cid is present (in_census_NEWS_DISTANCE=1); nothing is inferred from "
        "a blank minutes field (D-N3)",
        "the file's reach is +/-15min, so flag_held_into_window for a cid "
        "OUTSIDE it is recomputed with the census's own definition "
        "(news_census.py:400-408) — verified equal on every row the file "
        "carries",
        "cls_display US_CLOCK (WIRE spelling NEWS-WINDOW, which is what every "
        "join, lookup and committed column uses — CC-M2-22.1 is a DISPLAY "
        "alias, R102) is a FIXED-CLOCK family name, NOT a compliance fact",
        "signed_dec_minus_release_sec is NEGATIVE when the release is AHEAD "
        "of the decision — D-077.1's ordered minutes-since-release profile "
        "needs the sign and the old unsigned distance could not carry it",
        "minutes_since_slot is EMPTY when no generation slot precedes the "
        "decision (the -1 sentinel used to be bucketed as if it were a real "
        "age)",
        "in_DEPLOYABLE_ENTRY_VETO = the BINDING reading (entry veto only, "
        "CC-M2-22.3); in_DEPLOYABLE_ENTRY_PLUS_HOLD adds the held-into-window "
        "deployment-posture exclusion (R128 — both are published, neither is "
        "resolved silently)"]
    W("E1_BLIND_NEWS_DISTANCE.tsv",
      ("cid", "asset", "date8", "clock", "cls_display", "cls_wire", "side",
       "is_replay_seat",
       "dist_to_dated_release_sec", "signed_dec_minus_release_sec",
       "entry_in_window_10min",
       "hold_crosses_window", "slot_age_sec", "minutes_since_slot",
       "in_census_NEWS_DISTANCE", "flag_inside_default_window",
       "flag_pre_release_window", "flag_held_into_window", "release_name",
       "in_DEPLOYABLE_ENTRY_VETO", "in_DEPLOYABLE_ENTRY_PLUS_HOLD",
       "in_NAME_STRUCK_SUPERSEDED",
       "cert_close_usd", "winner_close"), news_rows,
      extra=news_extra)

    # 5. ancillaries — class value split, RV1/RV2, grade calibration
    anc = []
    sci = scored["SCIENCE"]["READER"]
    for cls in sorted({meta[c]["cls"] for c in reader_takes}):
        sub = [meta[c] for c in reader_takes if meta[c]["cls"] == cls]
        seats = [meta[c] for c in reader_seats if meta[c]["cls"] == cls]
        anc.append(["class", cls, len(sub),
                    float(np.mean([x["cert_close_usd"] for x in sub])),
                    float(np.sum([x["cert_close_usd"] for x in sub])),
                    int(sum(x["winner_close"] for x in sub)),
                    float(np.mean([x["winner_close"] for x in sub])),
                    len(seats),
                    float(np.sum([x["cert_close_usd"] for x in seats]))])
    # D-077-UPDATE(4) ordered an OPEN-DYNAMICS release-proximity CONFOUND
    # check; the pass answered it with a frequency ("3 of 69 flagged"), which
    # is an exposure count, not a confound test.  The value-conditional split
    # is the test: does the class's value depend on release proximity?
    for cls in sorted({meta[c]["cls"] for c in reader_takes}):
        for lab, sel in (("near_dated_release",
                          [c for c in reader_takes
                           if meta[c]["cls"] == cls
                           and (flags[c]["entry_in_window"]
                                or flags[c]["hold_crosses"])]),
                         ("clear_of_release",
                          [c for c in reader_takes
                           if meta[c]["cls"] == cls
                           and not (flags[c]["entry_in_window"]
                                    or flags[c]["hold_crosses"])])):
            if not sel:
                continue
            anc.append(["release_confound", "%s|%s" % (cls, lab), len(sel),
                        float(np.mean([meta[c]["cert_close_usd"]
                                       for c in sel])),
                        float(np.sum([meta[c]["cert_close_usd"]
                                      for c in sel])),
                        int(sum(meta[c]["winner_close"] for c in sel)),
                        float(np.mean([meta[c]["winner_close"]
                                       for c in sel])),
                        len(set(sel) & reader_seats),
                        float(sum(meta[c]["cert_close_usd"]
                                  for c in set(sel) & reader_seats))])
    rv = {c: ("RV1" if meta[c]["date8"] <= 20211026 else "RV2")
          for c in meta}
    for lab in ("RV1", "RV2"):
        sub = [meta[c] for c in reader_takes if rv[c] == lab]
        seats = [meta[c] for c in reader_seats if rv[c] == lab]
        anc.append(["subperiod", lab, len(sub),
                    float(np.mean([x["cert_close_usd"] for x in sub])),
                    float(np.sum([x["cert_close_usd"] for x in sub])),
                    int(sum(x["winner_close"] for x in sub)),
                    float(np.mean([x["winner_close"] for x in sub])),
                    len(seats),
                    float(np.sum([x["cert_close_usd"] for x in seats]))])
    for g in ("A", "B", "C"):
        sub = [meta[c] for c in reader_takes if meta[c]["conf"] == g]
        seats = [meta[c] for c in reader_seats if meta[c]["conf"] == g]
        if not sub:
            continue
        anc.append(["grade_TAKE", g, len(sub),
                    float(np.mean([x["cert_close_usd"] for x in sub])),
                    float(np.sum([x["cert_close_usd"] for x in sub])),
                    int(sum(x["winner_close"] for x in sub)),
                    float(np.mean([x["winner_close"] for x in sub])),
                    len(seats),
                    float(np.sum([x["cert_close_usd"] for x in seats]))])
        skp = [meta[c] for c in unis["SCIENCE"]
               if arms["READER"][c] == "SKIP" and meta[c]["conf"] == g]
        if skp:
            anc.append(["grade_SKIP", g, len(skp),
                        float(np.mean([x["cert_close_usd"] for x in skp])),
                        float(np.sum([x["cert_close_usd"] for x in skp])),
                        int(sum(x["winner_close"] for x in skp)),
                        float(np.mean([x["winner_close"] for x in skp])),
                        0, 0.0])
    for asset in ("SI", "HG", "NKD"):
        sub = [meta[c] for c in reader_takes if meta[c]["asset"] == asset]
        seats = [meta[c] for c in reader_seats if meta[c]["asset"] == asset]
        if not sub:
            continue
        anc.append(["asset", asset, len(sub),
                    float(np.mean([x["cert_close_usd"] for x in sub])),
                    float(np.sum([x["cert_close_usd"] for x in sub])),
                    int(sum(x["winner_close"] for x in sub)),
                    float(np.mean([x["winner_close"] for x in sub])),
                    len(seats),
                    float(np.sum([x["cert_close_usd"] for x in seats]))])
    W("E1_BLIND_SCORE_ANCILLARY.tsv",
      ("cut", "level", "n_takes", "mean_cert_close_usd", "sum_cert_close_usd",
       "n_winners", "winner_rate", "n_replay_seats", "seat_value_usd"), anc)

    # 6. row-grain GEE (session clusters)
    gee_rows = []
    for uname, cids in unis.items():
        cl = np.array(["%s-%d" % (meta[c]["asset"], meta[c]["date8"])
                       for c in sorted(cids)])
        y_c = np.array([meta[c]["cert_close_usd"] for c in sorted(cids)])
        y_w = np.array([float(meta[c]["winner_close"]) for c in sorted(cids)])
        x = np.array([1.0 if arms["READER"][c] == "TAKE" else 0.0
                      for c in sorted(cids)])
        for label, y, link in (("cert_close_usd", y_c, "identity"),
                               ("winner_close", y_w, "logit")):
            g = gee_row(y, x, cl, link)
            if g:
                gee_rows.append([uname, "READER_take_vs_skip", label, link,
                                 g["beta"], g["se_cr1"], g["z"], g["p"],
                                 g["n"], g["n_clusters"]])
    W("E1_BLIND_SCORE_GEE.tsv",
      ("reading", "contrast", "outcome", "link", "beta", "se_cr1", "z", "p",
       "n", "n_session_clusters"), gee_rows,
      extra=["row grain, clustered on SESSION (asset x date)"])

    # 7. git ordering audit
    W("E1_BLIND_GIT_ORDERING.tsv",
      ("commit", "unix_time", "subject", "n_files", "outcome_bearing_paths"),
      ord_rows,
      extra=["range 99ae1d5..HEAD = prospective registration -> HEAD",
             "the outcome-path matcher is CASE-INSENSITIVE over "
             "(blind_score|unblind|s14|panel_|truth) — three of its five "
             "predicates used to be case-sensitive against an UPPERCASE "
             "artifact tree and missed four outcome artefacts (R129)",
             "%d of %d commits carry an outcome-bearing path"
             % (len(ord_bad), len(ord_rows))])

    # 8. the arm register (R129/R132): what each arm actually did, computed
    W("E1_BLIND_ARM_REGISTER.tsv", ("arm", "status", "detail"),
      [[k, v["status"], v["detail"]] for k, v in arm_notes.items()],
      extra=["the report's 'all eight frozen predecessor policies ran AS "
             "COMMITTED' sentence is written FROM this table, never asserted"])

    # 9. the R130 reconciliation of the committed verdict document
    rec_rows = verdict_reconciliation(OUT)
    W("E1_VERDICT_RECONCILIATION.tsv",
      ("verdict_line", "kind", "quoted", "resolved_to", "context", "verdict"),
      rec_rows,
      extra=["every number and reading-token the committed "
             "provenance/port_m2/E1_TEACHER_GATE_VERDICT.md quotes, checked "
             "against the tables THIS pass wrote (R130). "
             "NOT_FOUND_IN_CURRENT_SOURCE = the document quotes a number no "
             "current committed evidence file contains — D-010 says a "
             "load-bearing number must be reproducible",
             "%d of %d quoted items do not resolve"
             % (sum(1 for r in rec_rows if r[5] != "FOUND"), len(rec_rows))])

    # ------------------------------------------------------------- mutant --
    mut = None
    if a.mutant:
        mut = run_mutant(meta, unis, ceils, sealed_sha)
        W("E1_BLIND_MUTANT.tsv",
          ("check", "expected", "observed", "verdict"), mut)

    receipt = {"env": MC.env_receipt(params_with_predicate()),
               "params_hash": phash,
               "deployable_predicate_sha16": predicate_sha16(),
               "ledger_sha1_blob": sealed_sha,
               "ledger_sha256": hashlib.sha256(
                   open(LEDGER, "rb").read()).hexdigest(),
               # R129: the triage COMPAT indices drive every mechanical arm and
               # are untracked cache files; `input_sha256` used to be {}.
               "input_sha256": dict(INDEX_SHA256),
               "news_distance_sha256": hashlib.sha256(
                   open(NEWS_DISTANCE, "rb").read()).hexdigest(),
               "head": subprocess.check_output(
                   ["git", "-C", REPO, "rev-parse", "HEAD"]).decode().strip(),
               "n_calls": len(meta), "n_days": len(d8s),
               "n_sessions": len(ceil_sci),
               "arms": list(arms),
               "arm_register": arm_notes,
               "readings": {k: len(v) for k, v in unis.items()},
               "deployable_coverage": cover,
               "declared_arm_identity": decl_ident,
               "ledger_numstat": numstat,
               "outcome_bearing_commits": [b[0] for b in ord_bad],
               "n_verdict_items_unresolved": sum(1 for r in rec_rows
                                                 if r[5] != "FOUND"),
               "pins_moved": MC.pins_moved()}
    MC.write_json(os.path.join(OUT, "e1blind_score.receipt.json"), receipt)

    write_report(meta, arms, unis, ceils, scored, flags, d8s, marg_rows, bars,
                 anc, gee_rows, ord_rows, ord_bad, sealed_sha, receipt, mut,
                 idx_by_cid, holders, slots, cflags, cover, decl_ident,
                 numstat, arm_notes, rec_rows, publish=not a.no_publish)
    MC.hb("e1blind_score: %d calls, %d arms, %d readings -> %s"
          % (len(meta), len(arms), len(unis), OUT))
    return 0


# -------------------------------------------------------- R130 reconcile ----
VERDICT_DOC = os.path.join(REPO, "provenance/port_m2/E1_TEACHER_GATE_VERDICT.md")
# Only the LOAD-BEARING quotations are reconciled: dollar amounts and
# 4+-decimal statistics (a directive id like D-076 or a spec id like CC-M2-6 is
# not a number this document is quoting FROM an evidence file), plus the
# reading/arm vocabulary.
_NUM_RE = re.compile(r"[-+\u2212]?\$\s?\d[\d,]*(?:\.\d+)?"
                     r"|(?<![\w.-])\d\.\d{4,}(?![\w])")
_TOKEN_RE = re.compile(r"\b((?:DEPLOYABLE|SCIENCE|NAME-STRUCK|BASE_EARLIEST"
                       r"|E1D\d|DECLARED|READER)[A-Z0-9_-]*)\b")


def _tsv_cells(path):
    """{float value: [(file, column)]} and the set of string cells."""
    vals, strs = defaultdict(list), set()
    if not os.path.exists(path):
        return vals, strs
    with open(path) as fh:
        rows = [l.rstrip("\n").split("\t") for l in fh
                if not l.startswith("#") and l.strip()]
    if not rows:
        return vals, strs
    hdr = rows[0]
    for r in rows[1:]:
        for j, cell in enumerate(r):
            c = cell.strip()
            if not c:
                continue
            strs.add(c)
            try:
                vals[round(float(c), 2)].append(
                    (os.path.basename(path), hdr[j] if j < len(hdr) else "?"))
            except ValueError:
                pass
    return vals, strs


def verdict_reconciliation(out_dir):
    """Every number the committed VERDICT quotes, against its current source.

    R130: `E1_TEACHER_GATE_VERDICT.md:9,12` quote "deployable-strict -$4,670"
    and "(+$3,521/12d strict)"; DEPLOYABLE-STRICT appears 0 times in the
    committed `E1_BLIND_SCORE_BARS.tsv` and 11 times in the SUPERSEDED 4fff1bc
    version.  This lane may not edit that document (the orchestrator owns it),
    so the discrepancy is made MECHANICAL instead of narrative: every quoted
    token is looked up in the tables this pass just wrote and the miss is a
    row in a committed file.
    """
    rows = []
    if not os.path.exists(VERDICT_DOC):
        return [["-", "document", os.path.relpath(VERDICT_DOC, REPO), "",
                 "", "ABSENT"]]
    vals, strs = defaultdict(list), set()
    for f in ("E1_BLIND_SCORE_BARS.tsv", "E1_BLIND_SCORE_ARMS.tsv",
              "E1_BLIND_SCORE_MARGINS.tsv", "E1_BLIND_SCORE_PERDAY.tsv",
              "E1_BLIND_SCORE_ANCILLARY.tsv"):
        v, t = _tsv_cells(os.path.join(out_dir, f))
        for k, w in v.items():
            vals[k] += w
        strs |= t
    for lineno, line in enumerate(open(VERDICT_DOC).read().splitlines(), 1):
        if line.startswith("#") and not line.strip("# "):
            continue
        for m in _NUM_RE.finditer(line):
            raw = m.group(0)
            try:
                x = float(raw.replace("$", "").replace(",", "")
                          .replace("\u2212", "-").replace(" ", ""))
            except ValueError:
                continue
            hit = None
            for cand in (round(x, 2), round(-x, 2), round(x / 100.0, 4)):
                if cand in vals:
                    hit = vals[cand][0]
                    break
            rows.append([lineno, "number", raw,
                         ("%s:%s" % hit) if hit else "",
                         line.strip()[:90],
                         "FOUND" if hit else "NOT_FOUND_IN_CURRENT_SOURCE"])
        for m in _TOKEN_RE.finditer(line):
            tok = m.group(1)
            rows.append([lineno, "token", tok, "", line.strip()[:90],
                         "FOUND" if tok in strs
                         else "NOT_FOUND_IN_CURRENT_SOURCE"])
    return rows


def run_mutant(meta, unis, ceils, sealed_sha):
    """RED FIRST: flip one sealed TAKE row and prove both guards fire."""
    src = open(LEDGER).read().split("\n")
    hdr_i = next(i for i, l in enumerate(src) if l.startswith("cid\t"))
    cols = src[hdr_i].split("\t")
    ci, cc = cols.index("cid"), cols.index("call")
    victim_i = victim = None
    for i in range(hdr_i + 1, len(src)):
        f = src[i].split("\t")
        if len(f) > cc and f[cc] == "TAKE":
            victim_i, victim = i, f[ci]
            break
    f = src[victim_i].split("\t")
    f[cc] = "SKIP"
    src[victim_i] = "\t".join(f)
    tmp = os.path.join(OUT, "_MUTANT_LEDGER.tsv")
    open(tmp, "w").write("\n".join(src))
    rows = []
    try:
        seal_check(tmp, ref=LEDGER)
        rows.append(["ledger blob hash refuses a post-seal flip", "REFUSAL",
                     "accepted (blob %s)" % git_blob_sha1(tmp)[:12], "FAIL"])
    except SealRefusal:
        rows.append(["ledger blob hash refuses a post-seal flip", "REFUSAL",
                     "SealRefusal raised (mutant blob %s != sealed %s)"
                     % (git_blob_sha1(tmp)[:12], sealed_sha[:12]), "PASS"])
    except Exception as e:                       # noqa: BLE001
        rows.append(["ledger blob hash refuses a post-seal flip", "REFUSAL",
                     type(e).__name__, "FAIL"])
    base = score_arm({r["cid"]: r["call"] for r in PS.parse_ledger(LEDGER)},
                     meta, unis["SCIENCE"], ceils["SCIENCE"])
    mutm = {r["cid"]: r["call"] for r in PS.parse_ledger(tmp)}
    mut = score_arm(mutm, meta, unis["SCIENCE"], ceils["SCIENCE"])
    moved = (abs(mut["replay_usd"] - base["replay_usd"]) > 1e-9
             or mut["n_takes"] != base["n_takes"]
             or abs((mut["lift_close"] or 0) - (base["lift_close"] or 0)) > 1e-12)
    rows.append(["flipping %s TAKE->SKIP moves the score" % victim,
                 "score changes",
                 "takes %d->%d, replay $%+.2f->$%+.2f, mean TAKE "
                 "$%+.2f->$%+.2f"
                 % (base["n_takes"], mut["n_takes"], base["replay_usd"],
                    mut["replay_usd"], base["mean_take_close"],
                    mut["mean_take_close"]),
                 "PASS" if moved else "FAIL"])
    rows.append(["sealed ledger blob == committed HEAD blob", sealed_sha,
                 git_blob_sha1(LEDGER), "PASS"])
    os.remove(tmp)
    return rows


# ------------------------------------------------------------------ report --
def _f(v, fmt="%.3f"):
    return "—" if v is None else (fmt % v)


def write_report(meta, arms, unis, ceils, scored, flags, d8s, marg_rows, bars,
                 anc, gee_rows, ord_rows, ord_bad, sealed_sha, receipt, mut,
                 idx_by_cid, holders, slots, cflags, cover, decl_ident,
                 numstat, arm_notes, rec_rows, publish=True):
    U = reading_sets(unis)
    L = []
    A = L.append
    A("# E1 BLIND ROUND — SCORING PASS (CC-M2-6 TEACHER-GATE INPUTS)")
    A("")
    A("Computed by the scoring lane, 12 sealed days, %d calls. **This file "
      "reports arithmetic; the gate VERDICT is the orchestrator's "
      "(CC-M2-6 / D-075).**" % len(meta))
    A("")
    A("## 0. SEAL + GIT ORDERING (verified by this pass)")
    A("")
    A("* Scored ledger `provenance/port_m2/E1_BLIND_LEDGER.tsv`, git blob "
      "`%s`, sha256 `%s` — **identical to the blob committed at HEAD**; the "
      "on-disk bytes are the sealed bytes." % (sealed_sha[:12],
                                               receipt["ledger_sha256"][:16]))
    # R129: this used to be a hardcoded sentence with no numstat run.
    A("* The ledger's last modifying commit is `%s`. **git numstat over its %d "
      "modifying commits: %d lines added, %d deleted (deleted_none=%d), "
      "ending at %d rows.**"
      % (numstat["commits"][-1]["commit"] if numstat["commits"] else "—",
         numstat["n_commits"], numstat["total_added"],
         numstat["total_deleted"], numstat["deleted_none"],
         numstat["commits"][-1]["rows_after"] if numstat["commits"] else 0))
    # R129: the bold headline was a FIXED STRING contradicted by the %d in its
    # own sentence.  It is written from the count now, both ways.
    A("* **Outcome-artefact audit over `99ae1d5..HEAD`: %d commits, %d "
      "carrying an outcome-bearing path (case-insensitive match on "
      "blind_score / unblind / s14 / panel_ / truth).** %s"
      % (len(ord_rows), len(ord_bad),
         ("No outcome artefact exists anywhere in the range, so the seal "
          "commits precede any outcome access."
          if not ord_bad else
          "THE RANGE IS NOT CLEAN — the commits carrying such a path are %s, "
          "and each is listed with its files in "
          "`E1_BLIND_GIT_ORDERING.tsv`. This is a statement of fact, not a "
          "verdict: a scoring artefact committed AFTER the last seal does not "
          "taint the seals, and the commit ORDER in that table is what decides "
          "it."
          % ", ".join("`%s`" % b[0] for b in ord_bad))))
    # R129: this used to be a string literal; run_policy wrote to a tempdir and
    # the comparison was never performed.  It is performed now.
    A("* Frozen-arm identity check, COMPUTED: `e1_blind_declared_policy.py` "
      "re-run as committed was compared with the sealed `DECLARED` column of "
      "`E1BLIND_D*_ARMS.tsv` — %d rows compared, %d agree, %d disagree%s "
      "(reproduces=%d)."
      % (decl_ident["n_rows_compared"], decl_ident["n_agree"],
         decl_ident["n_disagree"],
         ("; %d ARMS file(s) missing" % len(decl_ident["arms_files_missing"])
          if decl_ident["arms_files_missing"] else ""),
         decl_ident["reproduces"]))
    A("* Index provenance: the 12 triage COMPAT indices are UNTRACKED cache "
      "files, so they cannot be seal-checked against HEAD; their sha256s are "
      "stamped into the receipt (`input_sha256`, %d entries) instead of the "
      "empty dict the previous receipt carried."
      % len(receipt.get("input_sha256", {})))
    A("")
    A("**R127 — DEPLOYABLE CALENDAR COVERAGE (computed).** The dated "
      "high-impact release universe is `%s`: %d events, %s. It touches **%d of "
      "the block's %d days** (coverage %.3f against the declared minimum "
      "%.2f) — **%s**."
      % (cover["source"], cover["n_release_events"],
         "/".join(cover["distinct_release_names"][:6]) or "none",
         cover["n_covered"], cover["n_days"], cover["coverage"],
         cover["min_required"],
         "the DEPLOYABLE readings are PUBLISHED" if cover["ok"] else
         "the DEPLOYABLE readings are REFUSED and NOT published: a reading "
         "built on this calendar is an NFP/CPI/FOMC reading, not a prop-firm "
         "compliance reading, and D-077-UPDATE(3) calls DEPLOYABLE 'the "
         "reading that counts for the goal'"))
    A("")
    A("## 1. THE ROUND")
    A("")
    A("| | |")
    A("|---|---|")
    A("| calls scored | %d |" % len(meta))
    A("| days / session-assets | %d / %d |" % (len(d8s),
                                               len(ceils["SCIENCE"])))
    A("| reader TAKEs | %d |" % scored["SCIENCE"]["READER"]["n_takes"])
    A("| reader replay seats | %d |"
      % scored["SCIENCE"]["READER"]["n_seated"])
    nwin = sum(m["winner_close"] for m in meta.values())
    A("| D-021 winners in the universe | %d (base rate %.4f) |"
      % (nwin, nwin / float(len(meta))))
    A("| summed DP ceiling (close) | $%.2f |"
      % scored["SCIENCE"]["READER"]["ceiling_usd"])
    A("| reader winner precision / base rate | %.4f / %.4f = %.2fx |"
      % (scored["SCIENCE"]["READER"]["precision_close"], nwin / float(len(meta)),
         scored["SCIENCE"]["READER"]["precision_close"]
         / (nwin / float(len(meta)))))
    A("")
    sc = scored["SCIENCE"]["READER"]
    A("**SEATING RECONCILIATION.** The reader's sealed record claims **%d "
      "cell-seats** (one position per (asset,phase) cell, `seat_holder=` in "
      "the sealed interaction field). The CC-M2-10.3 scoring replay seats "
      "**%d** of its TAKEs: all %d of the reader's own holders plus **%d "
      "re-seats** that open when a position is stopped out at the $900 wall "
      "before its phase close. The scoring law is therefore MORE generous "
      "than the reader's own seating, not less; %d of the 12,418 rows are "
      "walled among the seats."
      % (len(holders), len(sc["seat_cids"]), len(holders & sc["seat_cids"]),
         len(sc["seat_cids"] - holders),
         sum(meta[c]["walled"] for c in sc["seat_cids"])))
    A("")
    A("| seating | n | realised $ |")
    A("|---|---|---|")
    A("| reader's own cell-seats | %d | %+.2f |"
      % (len(holders), sum(meta[c]["cert_close_usd"] for c in holders)))
    A("| CC-M2-10.3 greedy replay (THE LAW, CC-M2-21.4) | %d | %+.2f |"
      % (len(sc["seat_cids"]), sc["replay_usd"]))
    A("| DP seat-split (companion diagnostic) | %d | %+.2f |"
      % (sc["n_dp_seats"], sc["dp_seat_usd"]))
    A("| peak-exit companion reading (CC-M1-8) | %d | %+.2f |"
      % (len(sc["seat_cids"]), sc["replay_peak_usd"]))
    A("")
    A("Universe sizes by reading: " + ", ".join(
        "%s %d" % (k, len(v)) for k, v in unis.items()) + ".")
    A("")
    A("## 2. THE THREE CC-M2-6 BARS")
    A("")
    A("| reading | bar | statistic | bar value | statistic − bar |")
    A("|---|---|---|---|---|")
    for b in bars:
        if b[1].startswith(("a2", "b2", "c2")):
            continue
        stat = ("$%.2f (sum, %s)" % (b[3], b[2]) if b[1].startswith("a")
                else _f(b[3]))
        A("| %s | %s | %s | %s | %s |"
          % (b[0], b[1], stat, _f(b[12]), _f(b[13], "%+.4f")))
    A("")
    A("Bar (a) inference (day-paired, GEE independence + Liang-Zeger sandwich, "
      "Cameron-Miller CR1, 12 day clusters):")
    A("")
    A("| reading | best mechanical arm | sum margin | mean/day | se_CR1 | z | "
      "p (normal) | p (t,df11) | days + / − | p sign |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for b in bars:
        if not b[1].startswith("a_"):
            continue
        A("| %s | %s | $%+.2f | $%+.2f | %.2f | %s | %s | %s | %d / %d | %s |"
          % (b[0], b[2], b[3], b[4], b[5], _f(b[6], "%.3f"), _f(b[7], "%.4f"),
             _f(b[8], "%.4f"), b[9], b[10], _f(b[11], "%.4f")))
    A("")
    A("## 3. ARMS")
    A("")
    for uname in scored:
        A("### %s (universe %d)" % (uname, len(unis[uname])))
        A("")
        A("| arm | mech? | takes | mean TAKE $ | mean SKIP $ | lift close | "
          "lift peak | winners | precision | replay $ | capture |")
        A("|---|---|---|---|---|---|---|---|---|---|---|")
        for aname, s in sorted(scored[uname].items(),
                               key=lambda kv: -kv[1]["replay_usd"]):
            A("| %s | %s | %d | %s | %s | %s | %s | %d | %s | %+.2f | %s |"
              % (aname, "y" if is_mechanical(aname) else "",
                 s["n_takes"], _f(s["mean_take_close"], "%+.2f"),
                 _f(s["mean_skip_close"], "%+.2f"), _f(s["lift_close"]),
                 _f(s["lift_peak"]), s["n_winner_close"],
                 _f(s["precision_close"]), s["replay_usd"], _f(s["capture"])))
        A("")
    A("## 4. READER vs THE FROZEN DECLARED ARM (CC-M2-20.2's two arms)")
    A("")
    ndiff = sum(1 for c in unis["SCIENCE"]
                if arms["READER"][c] != arms["DECLARED"][c])
    A("The two arms differ on **%d of %d rows** (the reader's single RV2 "
      "evolution); the sealed summary claims 12. Every differing row is a "
      "%s row." % (ndiff, len(unis["SCIENCE"]),
                   "/".join(sorted({"%s %s" % (meta[c]["asset"], meta[c]["cls"])
                                    for c in unis["SCIENCE"]
                                    if arms["READER"][c]
                                    != arms["DECLARED"][c]}))))
    A("")
    A("| reading | reader replay | declared replay | day-paired margin | "
      "se_CR1 | z | p (t,df11) | days + / − | reader mean TAKE $ | declared "
      "mean TAKE $ | reader precision | declared precision | reader capture | "
      "declared capture |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for uname in scored:
        r, d = scored[uname]["READER"], scored[uname]["DECLARED"]
        b = [x for x in bars if x[0] == uname and x[1].startswith("a2")][0]
        A("| %s | %+.2f | %+.2f | $%+.2f | %.2f | %s | %s | %d / %d | %s | %s "
          "| %s | %s | %s | %s |"
          % (uname, r["replay_usd"], d["replay_usd"], b[3], b[5],
             _f(b[6], "%.3f"), _f(b[8], "%.4f"), b[9], b[10],
             _f(r["mean_take_close"], "%+.2f"),
             _f(d["mean_take_close"], "%+.2f"),
             _f(r["precision_close"], "%.4f"),
             _f(d["precision_close"], "%.4f"),
             _f(r["capture"]), _f(d["capture"])))
    A("")
    A("## 5. PER-DAY SEQUENCE (SCIENCE reading, replay $ at phase close)")
    A("")
    hdr = ["day", "date", "RV", "reader", "declared", "best-mech-of-day",
           "day ceiling", "reader capture"]
    A("| " + " | ".join(hdr) + " |")
    A("|" + "---|" * len(hdr))
    cm = ceils["SCIENCE"]
    day_ceil = defaultdict(float)
    for (asset, d8), v in cm.items():
        day_ceil[d8] += v
    for i, d8 in enumerate(d8s, 1):
        r = scored["SCIENCE"]["READER"]["per_day"].get(d8, 0.0)
        d = scored["SCIENCE"]["DECLARED"]["per_day"].get(d8, 0.0)
        bm = max(s["per_day"].get(d8, 0.0)
                 for n, s in scored["SCIENCE"].items() if is_mechanical(n))
        A("| %d | %d | %s | %+.2f | %+.2f | %+.2f | %.2f | %s |"
          % (i, d8, "RV1" if d8 <= 20211026 else "RV2", r, d, bm,
             day_ceil[d8],
             _f(r / day_ceil[d8] if day_ceil[d8] > 0 else None)))
    A("")
    seq = np.array([scored["SCIENCE"]["READER"]["per_day"].get(d, 0.0)
                    for d in d8s])
    rho, prho = SST.spearmanr(np.arange(1, len(d8s) + 1), seq)
    A("Trend over the 12-day sequence (Spearman, day index vs reader replay "
      "$): rho = %+.3f, p = %.3f. Days positive %d of %d; RV1 (days 1-5) "
      "$%+.2f over 5 days, RV2 (days 6-12) $%+.2f over 7 days."
      % (rho, prho, int((seq > 0).sum()), len(seq), float(seq[:5].sum()),
         float(seq[5:].sum())))
    A("")
    A("## 6. D-077 / CC-M2-22 COMPLIANCE — READ FROM THE CENSUS FLAGS")
    A("")
    if U["_refused"]:
        # R127: a compliance reading whose calendar touches almost none of
        # the block is not published as one.
        A("**THE DEPLOYABLE READINGS ARE REFUSED FOR THIS BLOCK (R127) — see "
          "§0 for the computed coverage.** The compliance tables below are "
          "NOT published: with the dated-release universe this thin, the "
          "label would mean something other than prop-firm compliance. The "
          "SCIENCE reading and the flag census stand.")
        A("")
    else:
        A("")
        takes = {c for c in unis["SCIENCE"] if arms["READER"][c] == "TAKE"}
        seats = scored["SCIENCE"]["READER"]["seat_cids"]
        n_entry = sum(1 for c in unis["SCIENCE"] if flags[c]["entry_in_window"])
        n_hold = sum(1 for c in unis["SCIENCE"] if flags[c]["hold_crosses"])
        A("**CC-M2-22.4 is binding here and supersedes the name-based reading.** "
          "Compliance is taken from the FLAGS in "
          "`artifacts/cache/port/m2/news_compliance/NEWS_DISTANCE.tsv` "
          "(`inside_default_window`, `pre_release_window`, `held_into_window`); "
          "nothing is inferred from a blank `minutes_since_release` (D-N3 — a "
          "blank means a release is AHEAD of the row).")
        A("")
        A("* The census file carries **%d of the round's %d candidates** (its "
          "reach is ±15min of a dated release); **all %d are on day 11, "
          "2021-11-03** — the block's only dated high-impact release (FOMC "
          "statement 18:00 UTC; the CPI-named rows are pre-window rows whose "
          "LAST release was October CPI and whose NEXT is that FOMC)."
          % (len(cflags), len(meta), len(cflags)))
        A("* Flag agreement RED CHECK: this pass's own recomputation of "
          "`inside_default_window` and `held_into_window` matches the census file "
          "on **every one of the %d rows** the file carries (0 disagreements), so "
          "the hold-crossing clause applied to rows OUTSIDE the file's ±15min "
          "reach is the census's own definition (news_census.py:400-408), not a "
          "substitute. Without that clause a seat entered hours before the FOMC "
          "and held through it would be scored compliant." % len(cflags))
        A("* Flag census over the whole round: %d candidates "
          "inside_default_window, %d whose phase-close hold crosses a restricted "
          "window." % (n_entry, n_hold))
        A("")
        A("### THE FLAG-BASED EXCLUSION (the number that counts)")
        A("")
        A("| basis | takes excluded | seats excluded (reader's own 40) | "
          "seats excluded (CC-M2-10.3 replay) |")
        A("|---|---|---|---|")
        A("| **CC-M2-22.4 FLAGS (binding)** | **%d of %d** | **%d of %d** | "
          "**%d of %d** |"
          % (len(takes - U["DEPLOYABLE"]), len(takes),
             len(holders - U["DEPLOYABLE"]), len(holders),
             len(seats - U["DEPLOYABLE"]), len(seats)))
        A("| name-based `NEWS-WINDOW` label (SUPERSEDED, D-N1) | %d of %d | "
          "%d of %d | %d of %d |"
          % (sum(1 for c in takes if meta[c]["cls"] == NEWS_FAMILY), len(takes),
             sum(1 for c in holders if meta[c]["cls"] == NEWS_FAMILY),
             len(holders),
             sum(1 for c in seats if meta[c]["cls"] == NEWS_FAMILY), len(seats)))
        A("")
        nw = [c for c in takes if meta[c]["cls"] == NEWS_FAMILY]
        nw_flagged = [c for c in nw if c not in U["DEPLOYABLE"]]
        A("**D-N1 confirmed on the round's own calls.** The sealed ledger's "
          "`NEWS-WINDOW` label (CC-M2-22.1 renames it **US_CLOCK**) is a "
          "fixed-clock family name, not a release fact: of the reader's %d "
          "US_CLOCK takes only **%d (%.1f%%)** carry any compliance flag. The "
          "summary's **26-of-40 was a name-based guess and is superseded** — on "
          "the flags **%d of the reader's 40 cell-seats survive** (%d excluded), "
          "and %d of the scorer's 49 replay seats survive (%d excluded)."
          % (len(nw), len(nw_flagged), 100.0 * len(nw_flagged) / max(len(nw), 1),
             len(holders & U["DEPLOYABLE"]), len(holders - U["DEPLOYABLE"]),
             len(seats & U["DEPLOYABLE"]), len(seats - U["DEPLOYABLE"])))
        A("")
        A("### Takes RE-LABELLED BY ACTUAL FLAG STATE (not by family name)")
        A("")
        A("| actual proximity state | takes | mean cert $ | winners | "
          "replay seats | seat value $ |")
        A("|---|---|---|---|---|---|")

        def _lab(c):
            r = cflags.get(c)
            if r is not None and r["inside_default_window"] == "1":
                return "INSIDE ±10min of a dated release"
            if r is not None and r["pre_release_window"] == "1":
                return "PRE-release window (≤10min ahead)"
            if flags[c]["hold_crosses"]:
                return "HOLD crosses a restricted window"
            return "COMPLIANT (no flag)"

        for lab in ("INSIDE ±10min of a dated release",
                    "PRE-release window (≤10min ahead)",
                    "HOLD crosses a restricted window", "COMPLIANT (no flag)"):
            sub = [c for c in takes if _lab(c) == lab]
            if not sub:
                continue
            ss = set(sub) & seats
            A("| %s | %d | %+.2f | %d | %d | %+.2f |"
              % (lab, len(sub),
                 float(np.mean([meta[c]["cert_close_usd"] for c in sub])),
                 sum(meta[c]["winner_close"] for c in sub), len(ss),
                 float(sum(meta[c]["cert_close_usd"] for c in ss))))
        A("")
        A("Flagged share by family label — the D-N1 point in one line: "
          + ", ".join("%s %d of %d flagged"
                      % (k, sum(1 for c in takes
                                if meta[c]["cls"] == k
                                and c not in U["DEPLOYABLE"]),
                         sum(1 for c in takes if meta[c]["cls"] == k))
                      for k in sorted({meta[c]["cls"] for c in takes})) + ".")
        A("")
        A("### D-077.2 — US_CLOCK takes by MINUTES SINCE the GENERATION anchor")
        A("")
        A("The family's own anchor is the fixed 08:30 / 10:00 / 14:00 ET slot set "
          "(`engine/port_m1/family_discovery.py:104 NEWS_SLOTS`, consumed by "
          "`engine/port_m1/b10_generation_v3.py:143 news_release_offsets`). This "
          "is a CLOCK profile and — D-N1 — it is NOT the compliance rule.")
        A("")
        A("| minutes since 08:30/10:00/14:00 ET slot | takes | mean cert $ | "
          "winners | replay seats | of which flagged |")
        A("|---|---|---|---|---|---|")
        buckets = [(0, 1), (1, 2), (2, 3), (3, 5), (5, 8), (8, 10), (10, 15),
                   (15, 10 ** 6)]
        for lo, hi in buckets:
            sub = [c for c in nw if lo <= slots[c] // 60 < hi]
            if not sub:
                continue
            A("| [%d,%s) | %d | %+.2f | %d | %d | %d |"
              % (lo, hi if hi < 10 ** 6 else "inf", len(sub),
                 float(np.mean([meta[c]["cert_close_usd"] for c in sub])),
                 sum(meta[c]["winner_close"] for c in sub),
                 len(set(sub) & seats),
                 sum(1 for c in sub if c not in U["DEPLOYABLE"])))
        A("")
        A("Of the %d US_CLOCK takes, %d sit in the first 10 minutes after a "
          "generation SLOT, but only %d carry a compliance flag — the slot was a "
          "DATED release on only one day of the twelve. That gap IS D-N1."
          % (len(nw), sum(1 for c in nw if slots[c] // 60 < 10), len(nw_flagged)))
        A("")
        A("### 26-of-40 reconciliation (both numbers, as ordered)")
        nw_takes = sum(1 for c in takes if meta[c]["cls"] == NEWS_FAMILY)
        nw_hold = sum(1 for c in holders if meta[c]["cls"] == NEWS_FAMILY)
        nw_seats = sum(1 for c in seats if meta[c]["cls"] == NEWS_FAMILY)
        A("")
        A("The summary's 40 seats are the reader's OWN cell-seats; the scoring "
          "law's replay seats 49 (D33 below). Both bases, both rules:")
        A("")
        A("| quantity | summary claim | reader's own 40 | CC-M2-10.3 replay (49) |")
        A("|---|---|---|---|")
        A("| TAKEs US_CLOCK / OPEN-DYNAMICS | 135 / 69 | %d / %d | %d / %d |"
          % (nw_takes, len(takes) - nw_takes, nw_takes, len(takes) - nw_takes))
        A("| seats | 40 | %d | %d |" % (len(holders), len(seats)))
        A("| seats US_CLOCK / OPEN-DYNAMICS | 14 / 26 | %d / %d | %d / %d |"
          % (nw_hold, len(holders) - nw_hold, nw_seats, len(seats) - nw_seats))
        A("| deployable seats — PURE NAME strike (the summary's rule) | 26 | %d | "
          "%d |" % (len(holders) - nw_hold, len(seats) - nw_seats))
        A("| deployable seats — NAME strike AND flags "
          "(NAME-STRUCK-SUPERSEDED universe) | — | %d | %d |"
          % (len(holders & U["NAME-STRUCK-SUPERSEDED"]),
             len(seats & U["NAME-STRUCK-SUPERSEDED"])))
        A("| **deployable seats — CC-M2-22.4 FLAGS (binding)** | — | **%d** | "
          "**%d** |"
          % (len(holders & U["DEPLOYABLE"]),
             len(seats & U["DEPLOYABLE"])))
        A("")
        A("**The summary's 26-of-40 reproduces exactly on its own (pure "
          "name-strike) basis — %d of %d — and is superseded.** Under the binding "
          "flag rule **%d of the 40 stand, %d excluded** (%d of 49 on the replay "
          "basis): the name-based rule threw away %d seats that carry no "
          "compliance flag at all."
          % (len(holders) - nw_hold, len(holders),
             len(holders & U["DEPLOYABLE"]), len(holders - U["DEPLOYABLE"]),
             len(seats - U["DEPLOYABLE"]),
             len({c for c in holders if meta[c]["cls"] == NEWS_FAMILY
                  and c in U["DEPLOYABLE"]})))
        A("")
        A("")
        A("### R128 — THE TWO DEPLOYABLE READINGS, BOTH PUBLISHED")
        A("")
        A("CC-M2-22.3 rules the held-into-window exposure *a DEPLOYMENT-"
          "POSTURE item ... not a generation change*; the earlier pass struck "
          "on it anyway, and that clause alone was the ENTIRE "
          "SCIENCE->DEPLOYABLE difference. Both readings are scored:")
        A("")
        A("| reading | universe | reader takes | reader replay $ | capture | "
          "seats |")
        A("|---|---|---|---|---|---|")
        for k in ("SCIENCE", "DEPLOYABLE_ENTRY_VETO",
                  "DEPLOYABLE_ENTRY_PLUS_HOLD", "NAME-STRUCK-SUPERSEDED"):
            if k not in scored:
                continue
            sk = scored[k]["READER"]
            A("| %s | %d | %d | %+.2f | %s | %d |"
              % (k, len(unis[k]), sk["n_takes"], sk["replay_usd"],
                 _f(sk["capture"]), len(sk["seat_cids"])))
        A("")
        A("The ENTRY-VETO reading is the BINDING one (it is the rule "
          "D-077-UPDATE(1) states); the ENTRY+HOLD reading is the deployment "
          "posture. Neither is resolved silently into the other.")
    A("## 7. ANCILLARIES")
    A("")
    A("| cut | level | takes | mean cert $ | sum cert $ | winners | win rate "
      "| seats | seat value $ |")
    A("|---|---|---|---|---|---|---|---|---|")
    for r in anc:
        A("| %s | %s | %d | %+.2f | %+.2f | %d | %s | %d | %+.2f |"
          % (r[0], r[1], r[2], r[3], r[4], r[5], _f(r[6]), r[7], r[8]))
    A("")
    A("Row-grain GEE (TAKE vs SKIP, clustered on session):")
    A("")
    A("| reading | outcome | link | beta | se_CR1 | z | p | n | clusters |")
    A("|---|---|---|---|---|---|---|---|---|")
    for g in gee_rows:
        A("| %s | %s | %s | %s | %s | %s | %s | %d | %d |"
          % (g[0], g[2], g[3], _f(g[4], "%+.4f"), _f(g[5], "%.4f"),
             _f(g[6], "%.3f"), _f(g[7], "%.4f"), g[8], g[9]))
    A("")
    A("## 8. D-076 NARROWNESS CAVEAT (echoed verbatim in substance)")
    A("")
    A("> D-076.3: *the E1 blind round stands as sealed, with its consecutive-"
      "October narrowness a NAMED CAVEAT on the gate verdict (pass = "
      "provisional until E2 confirms on a stratified mix; fail = diagnosed "
      "for regime-narrowness before iterations burn fresh days).*")
    A("")
    A("The twelve days are consecutive trading days 2021-10-20..2021-11-04, "
      "one asset era, one month-and-a-half of tape, one FOMC. Whatever these "
      "bars read, they read on that mix.")
    A("")
    if mut:
        A("## 9. RED-FIRST MUTANT")
        A("")
        A("| check | expected | observed | verdict |")
        A("|---|---|---|---|")
        for r in mut:
            A("| %s | %s | %s | %s |" % tuple(r))
        A("")
    A("## 10. DEFECTS + LIMITS RAISED BY THIS PASS")
    A("")
    A("* **D32 — BAR (b) IS NOT COMPUTABLE AS REGISTERED.** CC-M2-6 defines "
      "lift as `mean(cert of TAKEs)/mean(cert of SKIPs)` at the phase-close "
      "reading, and `panel_score` refuses a ratio against a non-positive "
      "denominator (panel_score.py:444 — \"a ratio against a non-positive "
      "denominator is not a lift\"). On the blind universe mean SKIP is "
      "$%.2f, so the registered ratio is undefined for EVERY arm. The bar is "
      "reported as its two components (mean TAKE $%.2f vs mean SKIP $%.2f, "
      "difference $%+.2f), the raw signed ratio, and the peak-exit companion "
      "lift %s. This is a pre-registration defect, not a scoring choice — the "
      "same hole existed on the study block (mean SKIP -$18.76) and was not "
      "noticed because the study lift was quoted on positive-mean subsets."
      % (scored["SCIENCE"]["READER"]["mean_skip_close"],
         scored["SCIENCE"]["READER"]["mean_take_close"],
         scored["SCIENCE"]["READER"]["mean_skip_close"],
         scored["SCIENCE"]["READER"]["take_minus_skip_close"],
         _f(scored["SCIENCE"]["READER"]["lift_peak"])))
    _tk = {c for c in unis["SCIENCE"] if arms["READER"][c] == "TAKE"}
    _nflag = sum(1 for c in _tk
                 if c in cflags and (_flag_true(cflags[c],
                                                "inside_default_window")
                                     or _flag_true(cflags[c],
                                                   "pre_release_window")))
    A("* **D31 CLOSED by CC-M2-22.1/22.4, and its consequence measured.** The "
      "family label is a fixed-clock name (%s in display, %s on the wire — "
      "R102), not a release fact; compliance comes from the census flags. On "
      "the round's own calls the two rules differ by an order of magnitude: "
      "**%d of %d reader TAKEs carry an ENTRY flag**, against %d of %d that "
      "carry the family name. The name-based reading is retained only as the "
      "NAME-STRUCK-SUPERSEDED universe, for reconciling the sealed summary.%s"
      % (NEWS_FAMILY_DISPLAY, NEWS_FAMILY, _nflag,
         scored["SCIENCE"]["READER"]["n_takes"],
         sum(1 for c in _tk if meta[c]["cls"] == NEWS_FAMILY),
         scored["SCIENCE"]["READER"]["n_takes"],
         "" if not U["_refused"] else
         " (the DEPLOYABLE universes themselves are REFUSED for this block "
         "per R127, so no deployable count is quoted here.)"))
    A("* **D34 (new, to the compliance lane): `NEWS_DISTANCE.tsv` cannot "
      "express the hold-crossing case beyond its own reach.** Its population "
      "is candidates within ±15min of a dated release, but "
      "`held_into_window` is a property of a hold that can begin HOURS "
      "earlier — on this block every such row (a seat entered in the morning "
      "and held through the 18:00 UTC FOMC) is outside the file. This pass "
      "closes the gap with the census's own definition and proves 0 "
      "disagreement on the rows the file does carry, but the file alone would "
      "under-count held-into exposure. Suggest the census emit held-into rows "
      "regardless of entry distance.")
    A("* **D33 — the scoring replay re-seats after a wall stop-out.** The "
      "reader held one position per (asset,phase) cell for the whole phase; "
      "the replay frees the seat at the certificate's exit second, which for "
      "a walled candidate is the wall. That gives the reader %d seats it "
      "never claimed. Named because it moves the headline: the law is more "
      "generous than the reader's declared posture."
      % len(scored["SCIENCE"]["READER"]["seat_cids"] - holders))
    # MINOR at :1412-1414: this was hardcoded while the build loop silently
    # dropped a failed arm.  It is written from the arm register now.
    ran = [k for k, v in arm_notes.items() if v["status"] == "RAN_AS_COMMITTED"]
    ref = [k for k, v in arm_notes.items() if v["status"] == "REFUSED"]
    A("* ARM REGISTER (computed, `E1_BLIND_ARM_REGISTER.tsv`): %d arm(s) ran "
      "AS COMMITTED through their own CLIs on all twelve days (%s); %d arm(s) "
      "REFUSED (%s). A refused arm is named, never dropped."
      % (len(ran), ", ".join("`%s`" % r for r in ran) or "none", len(ref),
         ", ".join("`%s`" % r for r in ref) or "none"))
    A("* R130 VERDICT RECONCILIATION: %d of %d numbers/tokens quoted by "
      "`provenance/port_m2/E1_TEACHER_GATE_VERDICT.md` do NOT resolve against "
      "the tables this pass wrote (`E1_VERDICT_RECONCILIATION.tsv`). This "
      "lane does not edit that document; it makes the discrepancy mechanical."
      % (sum(1 for r in rec_rows if r[5] != "FOUND"), len(rec_rows)))
    A("")
    A("---")
    A("Outputs: `artifacts/cache/port/m2/blind_score/` — %s. Pins re-checked "
      "at end: %s."
      % (", ".join(sorted(f for f in os.listdir(OUT)
                          if not f.startswith("_"))),
         "HELD" if not receipt["pins_moved"] else receipt["pins_moved"]))
    txt = "\n".join(L) + "\n"
    open(os.path.join(OUT, "E1_BLIND_SCORE_REPORT.md"), "w").write(txt)
    if not publish:
        return txt
    os.makedirs(EVIDENCE, exist_ok=True)
    open(os.path.join(EVIDENCE, "E1_BLIND_SCORE_REPORT.md"), "w").write(txt)
    # the gate INPUTS themselves are small and belong in the repo beside the
    # report (D-018 keeps the BULK — per-day/per-row tables — under cache)
    for f in ("E1_BLIND_SCORE_BARS.tsv", "E1_BLIND_SCORE_MARGINS.tsv",
              "E1_BLIND_SCORE_ARMS.tsv", "E1_BLIND_ARM_REGISTER.tsv",
              "E1_VERDICT_RECONCILIATION.tsv"):
        shutil.copyfile(os.path.join(OUT, f), os.path.join(EVIDENCE, f))
    return txt


if __name__ == "__main__":
    sys.exit(main())
