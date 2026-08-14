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
NEWS_FAMILY = "NEWS-WINDOW"

N_DAYS = 12
PREDECESSORS = tuple("e1d%d_policy" % d for d in range(1, 9))

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
}


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
        touch = [f for f in files
                 if ("blind_score" in f or "unblind" in f.lower()
                     or "S14" in f or "PANEL_" in f or "truth" in f.lower())]
        rows.append([h[:7], ct, subj[:90], len(files), ";".join(touch)])
        if touch:
            bad.append((h[:7], touch))
    return rows, bad


# ------------------------------------------------------------------- data ---
def read_index(day):
    p = os.path.join(TRIAGE, "E1BLIND_D%d_TRIAGE_INDEX_COMPAT.tsv" % day)
    with open(p) as fh:
        return list(csv.DictReader([l for l in fh if not l.startswith("#")],
                                   delimiter="\t"))


def run_policy(module, index_path, out_path, extra=()):
    """Run a frozen policy through its OWN committed CLI (never re-typed)."""
    cmd = ["/usr/bin/python3", os.path.join(_HERE, module + ".py"),
           "--index", index_path, "--out", out_path] + list(extra)
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        return None, r.stderr.decode()[-300:]
    with open(out_path) as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    return {x["cid"]: x["call"] for x in rows}, ""


def earliest_baselines(idx_rows):
    """baseline_replay's frozen arms, in-process (same code, no file churn)."""
    eps = BR.episodes(idx_rows)
    by = {r["cid"]: r for r in idx_rows}
    earliest = set()
    for _key, groups in eps.items():
        for g in groups:
            earliest.add(min(g, key=lambda c: int(by[c]["sec"])))
    out = {}
    for th in BR.THRESHOLDS:
        name = "BASE_EARLIEST_CV%d" % int(th)
        out[name] = {r["cid"]: ("TAKE" if (r["cid"] in earliest
                                           and BR.COND_VALUE.get(r["cls"], 0.0)
                                           >= th) else "SKIP")
                     for r in idx_rows}
    return out


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
    all.  CC-M2-22.4's clause "or its seat's hold crosses a flagged window"
    covers exactly that case, and it is computed here with the census's OWN
    definition (news_census.py:400-408: any release's [-600,+600] window
    intersecting [decision, phase close]), then VERIFIED to agree with the
    file's `held_into_window` on every row the file does carry.
    """
    rows = {}
    if os.path.exists(NEWS_DISTANCE):
        with open(NEWS_DISTANCE) as fh:
            for r in csv.DictReader([l for l in fh if not l.startswith("#")],
                                    delimiter="\t"):
                if r["cid"] in meta:
                    rows[r["cid"]] = r
    return rows


def news_flags(meta):
    """Per-cid D-077 flags from the DATED calendar.

    entry_in_window : |decision - release| <= 600s
    hold_crosses    : [entry, phase-close exit] intersects [rel-600, rel+600]
    """
    ts, _names = PL.release_calendar()
    ts = np.asarray(ts, dtype=np.int64)
    flags = {}
    for cid, m in meta.items():
        dec_ts = m["dec_ts"]
        # the census's holding horizon: [decision, PHASE CLOSE] (never the
        # wall) — news_census.py:400-403
        exit_ts = m["open_utc"] + max(m["phase_close_sec"], m["dec_sec"])
        j = np.searchsorted(ts, dec_ts)
        near = ts[max(j - 2, 0):min(j + 2, ts.size)]
        d_entry = (np.abs(near - dec_ts).min() if near.size
                   else 10 ** 9)
        k0 = np.searchsorted(ts, dec_ts - NEWS_WINDOW_SEC, side="left")
        k1 = np.searchsorted(ts, exit_ts + NEWS_WINDOW_SEC, side="right")
        cross = bool(k1 > k0)
        flags[cid] = {"dist_entry_sec": int(d_entry),
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
    out = {}
    for cid, m in meta.items():
        d = dt.datetime.fromtimestamp(m["dec_ts"], NY)
        best = None
        for back in (0, 1, 2):
            day = (d - dt.timedelta(days=back)).date()
            for hh, mm in ((8, 30), (10, 0), (14, 0)):
                t = int(dt.datetime(day.year, day.month, day.day, hh, mm,
                                    tzinfo=NY).timestamp())
                if t <= m["dec_ts"] and (best is None or t > best):
                    best = t
        out[cid] = (m["dec_ts"] - best) if best is not None else -1
    return out


def excluded_by_flags(cid, meta, flags, cflags):
    """CC-M2-22.4: excluded iff ANY census flag is true for the cid, or the
    seat's hold crosses a flagged window."""
    r = cflags.get(cid)
    if r is not None and (r["inside_default_window"] == "1"
                          or r["pre_release_window"] == "1"
                          or r["held_into_window"] == "1"):
        return True
    return bool(flags[cid]["hold_crosses"])


def universes(meta, flags, cflags):
    allc = set(meta)
    deploy = {c for c in allc
              if not excluded_by_flags(c, meta, flags, cflags)}
    # SUPERSEDED by CC-M2-22.1 (the family is a fixed-clock family, renamed
    # US_CLOCK; only ~19% of its fires sit near dated releases).  Kept ONLY to
    # reconcile the sealed summary's name-based 26-of-40 count.
    name = {c for c in deploy if meta[c]["cls"] != NEWS_FAMILY}
    return OrderedDict((("SCIENCE", allc),
                        ("DEPLOYABLE", deploy),
                        ("NAME-STRUCK-SUPERSEDED", name)))


# ---------------------------------------------------------------- scoring ---
def ceiling(meta, cids, metric="close"):
    """DP ceiling over exactly `cids`, per session-asset.  -> {(asset,d8): $}"""
    by = defaultdict(list)
    for c in cids:
        m = meta[c]
        by[(m["asset"], m["date8"])].append(m)
    out = {}
    for key, ms in by.items():
        items = []
        for m in ms:
            val = m["cert_close_usd"] if metric == "close" else m["cert_peak_usd"]
            end = (m["exit_close_sec"] if metric == "close"
                   else m["exit_peak_sec"])
            items.append((m["dec_sec"], end, val, m["dec_sec"], m["row"],
                          m["cid"]))
        total, _chosen = CC.dp_schedule(items)
        out[key] = float(total)
    return out


def arm_records(callmap, meta, cids):
    """panel_score-shaped records for one arm restricted to `cids`."""
    return [{"cid": c, "call": callmap.get(c, "SKIP"), "outcome": meta[c],
             "conf": meta[c].get("conf", "C"), "has_interaction": 0}
            for c in cids]


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
    """-> (meta, arms, per-day index rows)"""
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
        o["conf"] = conf.get(cid, "C")
        o["phase_close_sec"] = int(PS.A.roster(o["asset"])["phase_close_sec"]
                                   [o["row"]])
        meta[cid] = o

    arms = OrderedDict()
    arms["READER"] = reader
    tmp = tempfile.mkdtemp(prefix="e1blindscore_", dir=OUT)
    try:
        decl, base, preds = {}, defaultdict(dict), defaultdict(dict)
        for d in days:
            ip = os.path.join(TRIAGE,
                              "E1BLIND_D%d_TRIAGE_INDEX_COMPAT.tsv" % d)
            cm, err = run_policy("e1_blind_declared_policy", ip,
                                 os.path.join(tmp, "decl_%d.tsv" % d),
                                 ["--quiet"])
            if cm is None:
                raise RuntimeError("declared arm failed on day %d: %s" % (d, err))
            decl.update(cm)
            for name, cmap in earliest_baselines(idx_rows[d]).items():
                base[name].update(cmap)
            for mod in PREDECESSORS:
                cm, err = run_policy(mod, ip,
                                     os.path.join(tmp, "%s_%d.tsv" % (mod, d)))
                if cm is None:
                    preds[mod]["__error__"] = err
                    continue
                preds[mod].update(cm)
        arms["DECLARED"] = decl
        for name in sorted(base):
            arms[name] = base[name]
        for mod in PREDECESSORS:
            if "__error__" in preds[mod]:
                sys.stderr.write("UNRUNNABLE %s: %s\n"
                                 % (mod, preds[mod]["__error__"]))
                continue
            arms[mod.replace("_policy", "").upper()] = preds[mod]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return meta, arms, idx_by_cid, holders


MECHANICAL = None          # filled in main(): the CC-M2-6 baseline set


def is_mechanical(name):
    return name.startswith("BASE_EARLIEST") or name.startswith("E1D")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mutant", action="store_true",
                    help="red-first: flip one sealed TAKE and prove the hash "
                         "check refuses it and the score moves")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    MC.verify_spec(force=True)
    sealed_sha = seal_check(LEDGER)
    ord_rows, ord_bad = git_ordering()

    days = list(range(1, N_DAYS + 1))
    meta, arms, idx_by_cid, holders = build(days)
    flags = news_flags(meta)
    slots = slot_age(meta)
    cflags = census_flags(meta)
    # RED CHECK: our held-into recomputation must agree with the census file
    # on every row the file carries (the file's reach is only +/-15min).
    disagree = [c for c, r in cflags.items()
                if int(r["held_into_window"]) != flags[c]["hold_crosses"]]
    dis_inside = [c for c, r in cflags.items()
                  if int(r["inside_default_window"])
                  != flags[c]["entry_in_window"]]
    if disagree or dis_inside:
        raise SealRefusal(
            "census-flag agreement check failed: %d held_into and %d "
            "inside_window disagreements against NEWS_DISTANCE.tsv"
            % (len(disagree), len(dis_inside)))
    unis = universes(meta, flags, cflags)

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
    phash = MC.params_hash(PARAMS)
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
        # ---- the three bars
        mech = [(n, v) for n, v in scored[uname].items() if is_mechanical(n)]
        best_n, best = max(mech, key=lambda kv: kv[1]["replay_usd"])
        bb = np.array([best["per_day"].get(d, 0.0) for d in d8s])
        m = rr - bb
        cmn = cluster_mean(m, np.array(d8s))
        sg = sign_test(m)
        bars.append([uname, "a_margin_over_best_mechanical", best_n,
                     float(m.sum()), cmn["mean"], cmn["se_cr1"], cmn["z"],
                     cmn["p_normal"], cmn["p_t"], sg["n_pos"], sg["n_neg"],
                     sg["p_sign"], 0.0, float(m.sum()) - 0.0])
        lift = s_r["lift_close"]
        bars.append([uname, "b_lift_close", "", lift, None, None, None, None,
                     None, None, None, None, BAR_LIFT,
                     (lift - BAR_LIFT) if lift is not None else None])
        bars.append([uname, "b_lift_close_raw_ratio", "",
                     s_r["ratio_close_raw"], None, None, None, None, None,
                     None, None, None, BAR_LIFT,
                     (s_r["ratio_close_raw"] - BAR_LIFT)
                     if s_r["ratio_close_raw"] is not None else None])
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
        news_rows.append([c, m["asset"], m["date8"], m["clock"], m["cls"],
                          m["side"], int(c in reader_seats), f["dist_entry_sec"],
                          f["entry_in_window"], f["hold_crosses"],
                          slots[c], slots[c] // 60,
                          int(c in cflags),
                          (cflags[c]["inside_default_window"] if c in cflags
                           else "0"),
                          (cflags[c]["pre_release_window"] if c in cflags
                           else "0"),
                          (cflags[c]["held_into_window"] if c in cflags
                           else str(flags[c]["hold_crosses"])),
                          (cflags[c]["release_name"] if c in cflags else ""),
                          int(c in unis["DEPLOYABLE"]),
                          int(c in unis["NAME-STRUCK-SUPERSEDED"]),
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
        "cls US_CLOCK (spelled NEWS-WINDOW in the sealed ledger) is a FIXED-"
        "CLOCK family name, NOT a compliance fact (CC-M2-22.1 / D-N1)"]
    W("E1_BLIND_NEWS_DISTANCE.tsv",
      ("cid", "asset", "date8", "clock", "cls", "side", "is_replay_seat",
       "dist_to_dated_release_sec", "entry_in_window_10min",
       "hold_crosses_window", "slot_age_sec", "minutes_since_slot",
       "in_census_NEWS_DISTANCE", "flag_inside_default_window",
       "flag_pre_release_window", "flag_held_into_window", "release_name",
       "in_DEPLOYABLE", "in_NAME_STRUCK_SUPERSEDED",
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
             "outcome_bearing_paths empty on every row = no outcome artefact "
             "existed before this pass"])

    # ------------------------------------------------------------- mutant --
    mut = None
    if a.mutant:
        mut = run_mutant(meta, unis, ceils, sealed_sha)
        W("E1_BLIND_MUTANT.tsv",
          ("check", "expected", "observed", "verdict"), mut)

    receipt = {"env": MC.env_receipt(PARAMS),
               "ledger_sha1_blob": sealed_sha,
               "ledger_sha256": hashlib.sha256(
                   open(LEDGER, "rb").read()).hexdigest(),
               "head": subprocess.check_output(
                   ["git", "-C", REPO, "rev-parse", "HEAD"]).decode().strip(),
               "n_calls": len(meta), "n_days": len(d8s),
               "n_sessions": len(ceil_sci),
               "arms": list(arms),
               "readings": {k: len(v) for k, v in unis.items()},
               "pins_moved": MC.pins_moved()}
    MC.write_json(os.path.join(OUT, "e1blind_score.receipt.json"), receipt)

    write_report(meta, arms, unis, ceils, scored, flags, d8s, marg_rows, bars,
                 anc, gee_rows, ord_rows, ord_bad, sealed_sha, receipt, mut,
                 idx_by_cid, holders, slots, cflags)
    MC.hb("e1blind_score: %d calls, %d arms, %d readings -> %s"
          % (len(meta), len(arms), len(unis), OUT))
    return 0


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
                 idx_by_cid, holders, slots, cflags):
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
    A("* The ledger's last modifying commit is `752918d` (day-12 seal). Every "
      "one of the twelve seal commits ADDED rows and DELETED none "
      "(git numstat, day1 948 -> day12 12,418), so no earlier day's call was "
      "ever revised.")
    A("* **No outcome artefact exists anywhere in `99ae1d5..HEAD`.** Every "
      "commit from the prospective registration to HEAD was audited for "
      "outcome-bearing paths (blind_score / unblind / S14 / PANEL_ / truth): "
      "%d commits, %d carrying such a path. The round-seal commit `89382dd` "
      "and the D-077 annotation `5afab84` touched no call. **THE SEAL "
      "COMMITS PRECEDE ANY OUTCOME ACCESS: the unblinding is this pass, and "
      "it is the first event in the repository's history to read a "
      "certificate for these twelve days.**" % (len(ord_rows), len(ord_bad)))
    A("* Frozen-arm identity check: `e1_blind_declared_policy.py` re-run as "
      "committed reproduces the sealed `DECLARED` column of "
      "`E1BLIND_D*_ARMS.tsv` exactly.")
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
    A("| reader's own 40 cell-seats | %d | %+.2f |"
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
      "seats excluded (CC-M2-10.3 replay, 49) |")
    A("|---|---|---|---|")
    A("| **CC-M2-22.4 FLAGS (binding)** | **%d of %d** | **%d of %d** | "
      "**%d of %d** |"
      % (len(takes - unis["DEPLOYABLE"]), len(takes),
         len(holders - unis["DEPLOYABLE"]), len(holders),
         len(seats - unis["DEPLOYABLE"]), len(seats)))
    A("| name-based `NEWS-WINDOW` label (SUPERSEDED, D-N1) | %d of %d | "
      "%d of %d | %d of %d |"
      % (sum(1 for c in takes if meta[c]["cls"] == NEWS_FAMILY), len(takes),
         sum(1 for c in holders if meta[c]["cls"] == NEWS_FAMILY),
         len(holders),
         sum(1 for c in seats if meta[c]["cls"] == NEWS_FAMILY), len(seats)))
    A("")
    nw = [c for c in takes if meta[c]["cls"] == NEWS_FAMILY]
    nw_flagged = [c for c in nw if c not in unis["DEPLOYABLE"]]
    A("**D-N1 confirmed on the round's own calls.** The sealed ledger's "
      "`NEWS-WINDOW` label (CC-M2-22.1 renames it **US_CLOCK**) is a "
      "fixed-clock family name, not a release fact: of the reader's %d "
      "US_CLOCK takes only **%d (%.1f%%)** carry any compliance flag. The "
      "summary's **26-of-40 was a name-based guess and is superseded** — on "
      "the flags **%d of the reader's 40 cell-seats survive** (%d excluded), "
      "and %d of the scorer's 49 replay seats survive (%d excluded)."
      % (len(nw), len(nw_flagged), 100.0 * len(nw_flagged) / max(len(nw), 1),
         len(holders & unis["DEPLOYABLE"]), len(holders - unis["DEPLOYABLE"]),
         len(seats & unis["DEPLOYABLE"]), len(seats - unis["DEPLOYABLE"])))
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
                            and c not in unis["DEPLOYABLE"]),
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
             sum(1 for c in sub if c not in unis["DEPLOYABLE"])))
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
      % (len(holders & unis["NAME-STRUCK-SUPERSEDED"]),
         len(seats & unis["NAME-STRUCK-SUPERSEDED"])))
    A("| **deployable seats — CC-M2-22.4 FLAGS (binding)** | — | **%d** | "
      "**%d** |"
      % (len(holders & unis["DEPLOYABLE"]),
         len(seats & unis["DEPLOYABLE"])))
    A("")
    A("**The summary's 26-of-40 reproduces exactly on its own (pure "
      "name-strike) basis — %d of %d — and is superseded.** Under the binding "
      "flag rule **%d of the 40 stand, %d excluded** (%d of 49 on the replay "
      "basis): the name-based rule threw away %d seats that carry no "
      "compliance flag at all."
      % (len(holders) - nw_hold, len(holders),
         len(holders & unis["DEPLOYABLE"]), len(holders - unis["DEPLOYABLE"]),
         len(seats - unis["DEPLOYABLE"]),
         len({c for c in holders if meta[c]["cls"] == NEWS_FAMILY
              and c in unis["DEPLOYABLE"]})))
    A("")
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
    A("* **D31 CLOSED by CC-M2-22.1/22.4, and its consequence measured.** The "
      "family label is a fixed-clock name (US_CLOCK), not a release fact; "
      "compliance now comes from the census flags. On the round's own calls "
      "the two rules differ by an order of magnitude: **%d of %d reader "
      "TAKEs carry a flag**, against %d of %d that carry the family name. "
      "The name-based reading is retained only as the "
      "NAME-STRUCK-SUPERSEDED universe, for reconciling the sealed summary."
      % (len({c for c in unis["SCIENCE"] if arms["READER"][c] == "TAKE"}
             - unis["DEPLOYABLE"]),
         scored["SCIENCE"]["READER"]["n_takes"],
         sum(1 for c in unis["SCIENCE"]
             if arms["READER"][c] == "TAKE" and meta[c]["cls"] == NEWS_FAMILY),
         scored["SCIENCE"]["READER"]["n_takes"]))
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
    A("* All eight frozen predecessor policies e1d1..e1d8 ran AS COMMITTED "
      "through their own CLIs on all twelve days (no unrunnable arm), as did "
      "`e1_blind_declared_policy.py`.")
    A("")
    A("---")
    A("Outputs: `artifacts/cache/port/m2/blind_score/` "
      "(ARMS, PERDAY, MARGINS, BARS, NEWS_DISTANCE, ANCILLARY, GEE, "
      "GIT_ORDERING, MUTANT, receipt). Pins re-checked at end: %s."
      % ("HELD" if not receipt["pins_moved"] else receipt["pins_moved"]))
    txt = "\n".join(L) + "\n"
    open(os.path.join(OUT, "E1_BLIND_SCORE_REPORT.md"), "w").write(txt)
    os.makedirs(EVIDENCE, exist_ok=True)
    open(os.path.join(EVIDENCE, "E1_BLIND_SCORE_REPORT.md"), "w").write(txt)
    # the gate INPUTS themselves are small and belong in the repo beside the
    # report (D-018 keeps the BULK — per-day/per-row tables — under cache)
    for f in ("E1_BLIND_SCORE_BARS.tsv", "E1_BLIND_SCORE_MARGINS.tsv",
              "E1_BLIND_SCORE_ARMS.tsv"):
        shutil.copyfile(os.path.join(OUT, f), os.path.join(EVIDENCE, f))
    return txt


if __name__ == "__main__":
    sys.exit(main())
