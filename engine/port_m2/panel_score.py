#!/usr/bin/python3
"""PORT M2 — PANEL SCORER (spec §3 SCORING, gate P-M2b).

    "SCORING: ported panel_score — lift = mean(cert of takes)/mean(cert of
     skips), winner precision, one-position chronological replay capture;
     mechanical, the only judge."

This is the port of artifacts/cache/campaign/diagnostics/d020_v3/panel_score.py
onto the port substrate: outcomes come from the FROZEN v3 roster
(ORACLE_FREEZE) through c_c_roster.certificates, never from a re-derivation.

WHAT IT COMPUTES (all three, per era, per block, per asset and pooled)
  1. LIFT, on BOTH CC-M1-8 readings — the adoption metric (phase-close walled
     certificate) and its mandatory companion (peak-exit walled certificate):
         lift = mean(cert of TAKEs) / mean(cert of SKIPs)
     Both means are always reported; the ratio is reported only when the SKIP
     mean is positive (a non-positive denominator makes the ratio meaningless,
     never "infinite skill").
  2. WINNER PRECISION = share of TAKEs that are winners, where a winner clears
     the user's bar: cert >= $1,000 (D-021) AND MAE before the peak <= $300
     (D-021's MAE acceptance at that expectancy) AND the $900 wall was never
     hit (a walled candidate is a stop-out, never a winner).  Reported with the
     complementary "winners missed in SKIPs" count — the port's version of the
     old scorer's `winners missed` line.
  3. ONE-POSITION CHRONOLOGICAL REPLAY (D-046/D-036): within a session the
     TAKEs are replayed in decision order with ONE position; a TAKE whose
     decision second is not strictly after the open position's exit second is
     FORFEITED (recorded, not silently dropped).  The realised total is scored
     against the session's DP CEILING — c_c_roster.dp_schedule over EVERY
     candidate of that session — so capture = realised / ceiling.

LEDGER FORMAT (spec §3)
    `id TAKE|SKIP A|B|C evidence{primary: field+value+read, against,
     interaction, novel}`
Two spellings are accepted, both parsed by `parse_ledger`:
  * TSV with a header naming any of cid/call/conf/primary/against/interaction/
    novel (extra columns are carried through untouched);
  * the inline form `cid TAKE A primary: ...; against: ...; novel: ...`.
D-068-CORRECTION: the INTERACTION FIELD IS OPTIONAL.  A single-signal thesis is
a fully valid entry — the parser records `has_interaction` for reporting and
NEVER rejects a call for missing one.  Only `primary` is required (an evidence-
free call is not a thesis).

WHAT THE FIX PASS ADDED (R04/R23/R25/R35/R52/R53/R54/R132)
  * `--baselines ARM.tsv ...` — the CC-M2-6 bar (a) instrument.  Per (asset,
    day) realised dollars for the reader arm and EVERY baseline arm, the
    day-paired difference with a cluster-robust (Cameron-Miller CR1) sandwich
    SE, and the Holm-adjusted p over the arm set.  The bar is read off ONE
    table: "margin over the BEST mechanical baseline > 0" is scored in its
    conservative form — POSITIVE AGAINST EVERY ARM — with the pre-registered
    reference arm, the MEDIAN arm and the in-sample max-of-all-arms order
    statistic reported beside it and LABELLED as what each one is.
  * every point estimate (lift, winner precision, capture, both means) now
    carries a SESSION-CLUSTERED interval; a ratio against a non-positive
    denominator stays REFUSED and its interval is refused with it.
  * refusals became values: `n_cost_fallback` (the per-session cost that used
    to be silently replaced by `C.FEES_RT`) and `n_nonfinite_cert` are counted
    and reported, and `--strict` (the mode gate scoring runs in) REFUSES.
  * `score()` groups by class, confidence, DAY and — when a NEWS_DISTANCE file
    is supplied — minutes-since-release, so the D-077 DEPLOYABLE reading and
    the CC-M2-4.4 A|B|C calibration table are computable from its outputs.

Run:
  /usr/bin/python3 engine/port_m2/panel_score.py CALLS.tsv [--out DIR]
                                                 [--label NAME] [--strict]
                                                 [--news-distance FILE]
                                                 [--baselines ARM.tsv ...]
                                                 [--preregistered-arm NAME]
"""
import argparse
import os
import re
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import assemble as A                      # noqa: E402
import c_c_roster as CC                   # noqa: E402
import common as C                        # noqa: E402

SECTION = "§3 SCORING (P-M2b panel_score port)"

CALL_TAKE = "TAKE"
CALL_SKIP = "SKIP"
CALLS = (CALL_TAKE, CALL_SKIP)
CONFS = ("A", "B", "C")

# D-021: the winner bar the program is judged against.
WINNER_CERT_USD = 1000.0
WINNER_MAE_USD = 300.0

EVIDENCE_FIELDS = ("primary", "against", "interaction", "novel")
_INLINE = re.compile(r"^(?P<cid>\S+)\s+(?P<call>TAKE|SKIP)\s+"
                     r"(?P<conf>[ABC])\b\s*(?P<ev>.*)$", re.IGNORECASE)

# CC-M2-6 bar (a).  R126: the committed E1 run took the margin over the arm
# with the highest realised replay ON THE EVALUATION DAYS THEMSELVES, out of
# 13 — a winner's-curse reference that biases the reader's margin DOWNWARD by
# an unquoted amount.  The conservative reading of "the BEST mechanical
# baseline" is POSITIVE AGAINST ALL of them, and that is what this module
# scores; the max-of-all reading is still emitted, labelled as the in-sample
# order statistic it is, and a PRE-REGISTERED single arm is named up front.
PREREGISTERED_ARM = "BASE_EARLIEST"
BAR_A_RULE = ("positive against EVERY mechanical arm (the conservative "
              "reading of 'the BEST'); the max-of-all-arms margin is reported "
              "as an IN-SAMPLE ORDER STATISTIC, never as the bar")

PARAMS = {
    "spec_section": SECTION,
    "bar_a": BAR_A_RULE,
    "preregistered_reference_arm": PREREGISTERED_ARM,
    "inference": "Cameron-Miller CR1 cluster-robust sandwich; clusters = DAY "
                 "for the day-paired bar, SESSION (asset x date) for the "
                 "row-grain statistics; t(G-1) reference; Holm over the arm "
                 "set",
    "refusals": "n_cost_fallback and n_nonfinite_cert are COUNTED and "
                "reported; --strict refuses instead of substituting",
    "lift": "mean(cert of TAKEs)/mean(cert of SKIPs), both CC-M1-8 readings "
            "(phase-close = adoption, peak-exit = companion)",
    "winner": "cert >= $%.0f AND mae_before_argmax <= $%.0f AND not walled"
              % (WINNER_CERT_USD, WINNER_MAE_USD),
    "replay": "one position, chronological within a session, exit at the "
              "certificate's exit second; ceiling = c_c_roster.dp_schedule "
              "over every candidate of the session",
    "interaction_field": "OPTIONAL (D-068-CORRECTION); single-signal theses "
                         "are valid ledger entries",
    "outcomes": "m1/generation_v3 union roster (ORACLE_FREEZE) via "
                "c_c_roster.certificates(wall, cost_rt)",
}


# ------------------------------------------------------------------ parse ---
class LedgerError(ValueError):
    """A malformed ledger line.  Reported with its line number, never skipped
    silently: an unparsed call is a missing call, which changes the score."""


def _split_evidence(text):
    """`primary: ... ; against: ... ; interaction: ... ; novel: ...`"""
    ev = {k: "" for k in EVIDENCE_FIELDS}
    if not text:
        return ev
    t = text.strip()
    if t.startswith("evidence"):
        t = t[len("evidence"):].strip()
    if t.startswith("{") and t.endswith("}"):
        t = t[1:-1]
    # split on the field keywords themselves, so free text may contain ';'
    keys = [(m.start(), m.group(1).lower())
            for m in re.finditer(r"(?i)\b(primary|against|interaction|novel)\s*:",
                                 t)]
    if not keys:
        ev["primary"] = t.strip(" ;|")
        return ev
    for j, (pos, key) in enumerate(keys):
        end = keys[j + 1][0] if j + 1 < len(keys) else len(t)
        val = t[pos:end]
        val = val.split(":", 1)[1] if ":" in val else ""
        ev[key] = val.strip(" ;|\t")
    return ev


def parse_ledger(path):
    """-> [dict(cid, call, conf, primary, against, interaction, novel, line)]"""
    out = []
    cols = None
    with open(path) as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            fields = line.split("\t")
            low = [f.strip().lower() for f in fields]
            if cols is None and "\t" in line and (
                    "cid" in low or "id" in low or "case_id" in low):
                cols = low
                continue
            rec = None
            if cols is not None and "\t" in line:
                d = dict(zip(cols, [f.strip() for f in fields]))
                rec = {"cid": d.get("cid") or d.get("id") or d.get("case_id"),
                       "call": (d.get("call") or "").upper(),
                       "conf": (d.get("conf") or d.get("confidence")
                                or "").upper()}
                for k in EVIDENCE_FIELDS:
                    rec[k] = d.get(k, "")
                if not rec[EVIDENCE_FIELDS[0]] and d.get("evidence"):
                    rec.update(_split_evidence(d["evidence"]))
            else:
                m = _INLINE.match(line.strip())
                if m:
                    rec = {"cid": m.group("cid"), "call": m.group("call").upper(),
                           "conf": m.group("conf").upper()}
                    rec.update(_split_evidence(m.group("ev")))
            if rec is None or not rec.get("cid"):
                raise LedgerError("%s:%d unparseable ledger line: %r"
                                  % (path, lineno, line[:120]))
            if rec["call"] not in CALLS:
                raise LedgerError("%s:%d call must be TAKE or SKIP, got %r"
                                  % (path, lineno, rec["call"]))
            if rec["conf"] not in CONFS:
                raise LedgerError("%s:%d confidence must be A/B/C, got %r"
                                  % (path, lineno, rec["conf"]))
            if not rec["primary"].strip():
                raise LedgerError("%s:%d evidence.primary is required "
                                  "(interaction is NOT — D-068-CORRECTION)"
                                  % (path, lineno))
            MC.parse_cid(rec["cid"])       # raises on a malformed id
            rec["line"] = lineno
            rec["has_interaction"] = 1 if rec["interaction"].strip() else 0
            out.append(rec)
    seen = set()
    for r in out:
        if r["cid"] in seen:
            raise LedgerError("%s: duplicate call for %s (line %d)"
                              % (path, r["cid"], r["line"]))
        seen.add(r["cid"])
    return out


# --------------------------------------------------------------- outcomes ---
_OUT = {}

# R23/R132: the two silent substitutions this module used to make, turned into
# counted values.  `STRICT` is the mode the GATE runs in — there, a missing
# per-session cost or a non-finite certificate is a REFUSAL, not a fallback.
STRICT = False
COST_FALLBACK_SESSIONS = set()
NONFINITE_CERT_CIDS = set()


class OutcomeRefusal(RuntimeError):
    """An outcome that cannot be certified from the frozen roster."""


def set_strict(flag):
    """Strict mode changes what `outcome` DOES, so the cache is dropped."""
    global STRICT
    if bool(flag) != STRICT:
        STRICT = bool(flag)
        _OUT.clear()
        COST_FALLBACK_SESSIONS.clear()
        NONFINITE_CERT_CIDS.clear()
    return STRICT


def refusal_counts():
    return {"n_cost_fallback_sessions": len(COST_FALLBACK_SESSIONS),
            "cost_fallback_sessions": sorted("%s|%s" % k
                                             for k in COST_FALLBACK_SESSIONS),
            "n_nonfinite_cert": len(NONFINITE_CERT_CIDS),
            "nonfinite_cert_cids": sorted(NONFINITE_CERT_CIDS),
            "strict": int(STRICT)}


def _session_cost(asset, date):
    """The per-session round-trip cost, or a COUNTED fallback (R23).

    `cost = float(cost) if np.isfinite(cost) else C.FEES_RT` was an uncounted,
    unnamed substitution inside every certificate this scorer produced.
    """
    raw = A.cost_map().get((asset, date.isoformat()), float("nan"))
    if np.isfinite(raw):
        return float(raw), 0
    if STRICT:
        raise OutcomeRefusal(
            "no per-session cost for %s %s: the gate does not score a "
            "certificate on a substituted constant (R23)"
            % (asset, date.isoformat()))
    COST_FALLBACK_SESSIONS.add((asset, date.isoformat()))
    return float(C.FEES_RT), 1


def outcome(cid):
    """Both CC-M1-8 certificates + the winner inputs for one candidate."""
    if cid in _OUT:
        return _OUT[cid]
    asset, d8, ds, side = MC.parse_cid(cid)
    r = A.roster(asset)
    i = r["_index"][(d8, ds, side)]
    date = MC.d8_to_date(d8)
    cost, cost_fallback = _session_cost(asset, date)
    wall = float(A.walls()[asset]["wall_usd"])
    peak, close = CC.certificates(r, i, wall, cost)
    t_wall, mfe_w, argmax_sec, walled = CC._skel_query(r, i, wall)
    # R132 (the predicate GAP): a non-finite certificate is DROPPED from the DP
    # ceiling and ADDED to the replay, producing a NaN margin and an empty cell
    # indistinguishable from a legitimately-refused statistic.  It is a value
    # here: counted, excluded from every mean and from the replay, refused
    # outright in strict mode.
    finite = bool(np.isfinite(close[0]) and np.isfinite(peak[0])
                  and np.isfinite(r["mae_before_argmax"][i]))
    if not finite:
        if STRICT:
            raise OutcomeRefusal(
                "%s has a non-finite certificate (close=%r peak=%r): a "
                "refused quantity is never a number (R132)"
                % (cid, close[0], peak[0]))
        NONFINITE_CERT_CIDS.add(cid)
    o = {"cid": cid, "asset": asset, "date8": d8, "trade_date": date,
         "dec_sec": ds, "side": side, "row": int(i),
         "era": MC.era_of(d8), "cls": MC.class_of(int(r["fam_mask"][i]))[0],
         "cost_fallback": cost_fallback, "cert_finite": int(finite),
         "cert_close_usd": float(close[0]), "exit_close_sec": int(close[2]),
         "cert_peak_usd": float(peak[0]), "exit_peak_sec": int(peak[2]),
         "peak_seated": int(bool(peak[3])),
         "mae_before_argmax": float(r["mae_before_argmax"][i]),
         "walled": int(bool(walled)), "wall_usd": wall, "cost_rt": cost}
    for m, cert in (("close", o["cert_close_usd"]), ("peak", o["cert_peak_usd"])):
        o["winner_" + m] = int(finite and cert >= WINNER_CERT_USD
                               and o["mae_before_argmax"] <= WINNER_MAE_USD
                               and not o["walled"])
    _OUT[cid] = o
    return o


def dp_ceiling(asset, d8, metric="close"):
    """The one-position DP ceiling over EVERY candidate of the session."""
    key = ("dp", asset, int(d8), metric)
    if key in _OUT:
        return _OUT[key]
    r = A.roster(asset)
    date = MC.d8_to_date(int(d8))
    cost, _fb = _session_cost(asset, date)
    wall = float(A.walls()[asset]["wall_usd"])
    idx = np.nonzero(r["date8"] == int(d8))[0]
    items = []
    for i in idx.tolist():
        peak, close = CC.certificates(r, i, wall, cost)
        val, dec, exit_sec, _ = close if metric == "close" else peak
        items.append((dec, exit_sec, val, dec, int(r["iid"][i]), i))
    total, chosen = CC.dp_schedule(items)
    _OUT[key] = (float(total), len(chosen), len(idx))
    return _OUT[key]


# ------------------------------------------------------------- inference ----
# R52 / D-065-AMENDMENT.  lift, winner precision and capture were POINT
# ESTIMATES with no dispersion at all, so CC-M2-6 bars (b) and (c) were read
# off numbers whose uncertainty was unquoted.  Everything below is the
# Cameron-Miller CR1 cluster-robust sandwich written once: for an
# intercept-only mean it reduces to the clustered SEM, for a ratio of two
# means it is the delta method on the 2x2 clustered covariance.  Clusters are
# SESSIONS (asset x date) for row-grain statistics and DAYS for the
# day-paired bar, because within-cluster correlation is exactly what the
# episode literature says destroys a naive n (D-065-AMENDMENT).
def _cr1_factor(n, n_clusters, p):
    if n_clusters <= 1 or n <= p:
        return None
    return (n_clusters / float(n_clusters - 1)) * ((n - 1.0) / (n - p))


def _cluster_sums(infl, clusters):
    """Σ of the influence rows within each cluster -> (G, k) array."""
    infl = np.atleast_2d(np.asarray(infl, dtype=np.float64))
    if infl.shape[0] == 1 and infl.shape[1] != 1:
        infl = infl.T if len(clusters) == infl.shape[1] else infl
    keys = sorted(set(map(str, clusters)))
    idx = {k: j for j, k in enumerate(keys)}
    out = np.zeros((len(keys), infl.shape[1]), dtype=np.float64)
    for i, c in enumerate(clusters):
        out[idx[str(c)]] += infl[i]
    return out


def cluster_mean(y, clusters, alpha=0.05):
    """Clustered mean with a CR1 sandwich SE and a t(G-1) interval."""
    y = np.asarray(y, dtype=np.float64)
    cl = list(clusters)
    ok = np.isfinite(y)
    y, cl = y[ok], [c for c, k in zip(cl, ok) if k]
    n = int(y.size)
    if n == 0:
        return None
    mean = float(y.mean())
    u = _cluster_sums((y - mean).reshape(-1, 1), cl)
    G = u.shape[0]
    c = _cr1_factor(n, G, 1)
    if c is None:
        return {"mean": mean, "se_cr1": None, "t": None, "p": None,
                "ci_lo": None, "ci_hi": None, "n": n, "n_clusters": G,
                "df": max(G - 1, 0)}
    var = c * float((u[:, 0] ** 2).sum()) / (n ** 2)
    se = float(np.sqrt(var))
    df = G - 1
    tcrit = float(_t_ppf(1.0 - alpha / 2.0, df))
    t = (mean / se) if se > 0 else None
    return {"mean": mean, "se_cr1": se,
            "t": t, "p": (float(2 * _t_sf(abs(t), df)) if t is not None
                          else None),
            "ci_lo": mean - tcrit * se, "ci_hi": mean + tcrit * se,
            "n": n, "n_clusters": G, "df": df}


def cluster_ratio(num, den, clusters, alpha=0.05, require_positive=True):
    """Clustered interval for Σnum/Σden (capture) — delta method, CR1.

    `require_positive` keeps panel_score's law: a ratio against a non-positive
    denominator is REFUSED, and so is its interval.
    """
    num = np.asarray(num, dtype=np.float64)
    den = np.asarray(den, dtype=np.float64)
    sd = float(den.sum())
    if num.size == 0 or (require_positive and not sd > 0) or sd == 0:
        return None
    r = float(num.sum()) / sd
    infl = ((num - r * den) / sd).reshape(-1, 1)
    u = _cluster_sums(infl, list(clusters))
    G = u.shape[0]
    c = _cr1_factor(int(num.size), G, 1)
    if c is None:
        return {"ratio": r, "se_cr1": None, "ci_lo": None, "ci_hi": None,
                "n": int(num.size), "n_clusters": G}
    se = float(np.sqrt(c * float((u[:, 0] ** 2).sum())))
    tcrit = float(_t_ppf(1.0 - alpha / 2.0, G - 1))
    return {"ratio": r, "se_cr1": se, "ci_lo": r - tcrit * se,
            "ci_hi": r + tcrit * se, "n": int(num.size), "n_clusters": G}


def cluster_lift(y, is_take, clusters, alpha=0.05):
    """Clustered interval for mean(TAKE)/mean(SKIP) — delta method, CR1.

    REFUSED (None) whenever the SKIP mean is not positive: panel_score's rule
    that a ratio against a non-positive denominator is not a lift applies to
    the interval exactly as it applies to the point estimate.
    """
    y = np.asarray(y, dtype=np.float64)
    t = np.asarray(is_take, dtype=np.float64)
    s = 1.0 - t
    nt, ns = float(t.sum()), float(s.sum())
    if nt < 1 or ns < 1:
        return None
    mt = float((y * t).sum() / nt)
    ms = float((y * s).sum() / ns)
    if not ms > 0:
        return None
    infl = np.column_stack([t * (y - mt) / nt, s * (y - ms) / ns])
    u = _cluster_sums(infl, list(clusters))
    G = u.shape[0]
    c = _cr1_factor(int(y.size), G, 2)
    if c is None:
        return {"lift": mt / ms, "se_cr1": None, "ci_lo": None, "ci_hi": None,
                "n_clusters": G}
    V = c * (u.T @ u)
    g = np.array([1.0 / ms, -mt / (ms * ms)])
    var = float(g @ V @ g)
    se = float(np.sqrt(var)) if var >= 0 else None
    if se is None:
        return {"lift": mt / ms, "se_cr1": None, "ci_lo": None, "ci_hi": None,
                "n_clusters": G}
    tcrit = float(_t_ppf(1.0 - alpha / 2.0, G - 1))
    return {"lift": mt / ms, "se_cr1": se, "ci_lo": mt / ms - tcrit * se,
            "ci_hi": mt / ms + tcrit * se, "n_clusters": G}


def _t_sf(x, df):
    from scipy import stats as SST
    return SST.t.sf(x, max(int(df), 1))


def _t_ppf(q, df):
    from scipy import stats as SST
    return SST.t.ppf(q, max(int(df), 1))


def holm(pvals):
    """Holm-Bonferroni adjusted p-values, order preserved.  None passes through
    as None (a refused p is never adjusted into a number)."""
    idx = [i for i, p in enumerate(pvals) if p is not None]
    out = [None] * len(pvals)
    m = len(idx)
    order = sorted(idx, key=lambda i: pvals[i])
    run = 0.0
    for k, i in enumerate(order):
        adj = min(1.0, (m - k) * float(pvals[i]))
        run = max(run, adj)
        out[i] = run
    return out


def sign_test(y):
    from scipy import stats as SST
    y = np.asarray(y, dtype=np.float64)
    pos, neg = int((y > 0).sum()), int((y < 0).sum())
    nz = pos + neg
    return {"n_pos": pos, "n_neg": neg, "n_zero": int((y == 0).sum()),
            "p_sign": (float(SST.binomtest(pos, nz, 0.5).pvalue)
                       if nz else None)}


# ---------------------------------------------------------------- scoring ---
def replay(records, metric="close"):
    """One-position chronological replay of the TAKEs, per session.

    -> (per-session rows, totals).  A TAKE that cannot be seated (the position
    from an earlier TAKE is still open) is FORFEITED and counted.
    """
    by = {}
    for rec in records:
        if rec["call"] != CALL_TAKE:
            continue
        o = rec["outcome"]
        by.setdefault((o["asset"], o["date8"]), []).append(o)
    rows = []
    for (asset, d8) in sorted(by):
        seq = sorted(by[(asset, d8)], key=lambda o: (o["dec_sec"], -o["side"]))
        open_until = -1
        realised = 0.0
        n_seat = n_forfeit = n_refused = 0
        for o in seq:
            # R132: a non-finite certificate is REFUSED here rather than added
            # to the realised total (the DP ceiling drops it, so adding it made
            # a NaN capture out of a missing number).
            if not o.get("cert_finite", 1):
                n_refused += 1
                continue
            if o["dec_sec"] <= open_until:
                n_forfeit += 1
                continue
            cert = o["cert_close_usd"] if metric == "close" else o["cert_peak_usd"]
            exit_sec = (o["exit_close_sec"] if metric == "close"
                        else o["exit_peak_sec"])
            realised += cert
            open_until = exit_sec
            n_seat += 1
        ceiling, n_dp, n_cand = dp_ceiling(asset, d8, metric)
        rows.append({"asset": asset, "date8": d8, "era": MC.era_of(d8),
                     "n_takes": len(seq), "n_seated": n_seat,
                     "n_forfeited": n_forfeit, "n_refused_cert": n_refused,
                     "realised_usd": realised,
                     "dp_ceiling_usd": ceiling, "dp_n_seated": n_dp,
                     "n_candidates": n_cand,
                     "capture": (realised / ceiling) if ceiling > 0 else None})
    tot_r = sum(x["realised_usd"] for x in rows)
    tot_c = sum(x["dp_ceiling_usd"] for x in rows)
    totals = {"n_sessions": len(rows),
              "realised_usd": tot_r, "dp_ceiling_usd": tot_c,
              "capture": (tot_r / tot_c) if tot_c > 0 else None,
              "realised_per_session": (tot_r / len(rows)) if rows else 0.0,
              "n_seated": sum(x["n_seated"] for x in rows),
              "n_forfeited": sum(x["n_forfeited"] for x in rows),
              "n_refused_cert": sum(x["n_refused_cert"] for x in rows)}
    # the CC-M2-6 bar (c) denominator, with its session-clustered interval
    # (R52): capture is a ratio of two session totals, so the cluster is the
    # session and the delta method gives its dispersion.
    ci = cluster_ratio([x["realised_usd"] for x in rows],
                       [x["dp_ceiling_usd"] for x in rows],
                       ["%s|%d" % (x["asset"], x["date8"]) for x in rows])
    totals["capture_se_cr1"] = ci["se_cr1"] if ci else None
    totals["capture_ci_lo"] = ci["ci_lo"] if ci else None
    totals["capture_ci_hi"] = ci["ci_hi"] if ci else None
    totals["capture_n_clusters"] = ci["n_clusters"] if ci else None
    return rows, totals


# ------------------------------------------------------- the veto census ----
# CC-M2-17.4 (BINDING): "veto censuses report the seat-spender sub-population
# separately (day-6's $0.00 replay-delta lesson)."
#
# THE LESSON.  E1 day 6: 41 of 120 core+side TAKEs carried a V2/V3 veto.  The
# vetoed pool averaged -$221.01 with 3 winners, the pool that stood averaged
# -$71.77 with 16 — a $149/row improvement, and the strongest-looking veto
# statistic of the round.  THE REPLAY DELTA WAS EXACTLY $0.00, because the
# scorer holds ONE POSITION per session and not a single veto fired on a row
# that would ever have held it.  A veto that cannot move a seat cannot move the
# money, however good its pooled row statistic looks (ERA_NOTES_E1 §67).
#
# So the census reports the vetoed and standing pools SPLIT BY WHETHER THE ROW
# WOULD HAVE SPENT A SEAT, in both readings the program uses for seating:
#
#   DP        the row is in the one-position DP schedule computed over the
#             PRE-VETO TAKE SET of its session — "would have WON a DP seat",
#             the value-optimal reading, and the one CC-M2-17.4 names.
#   REPLAY    the row is SEATED by the chronological one-position replay of the
#             same pre-veto TAKE set — the reading the scorer actually banks.
#
# Both are reported because they disagree exactly when a veto removes a row the
# greedy clock would have seated but the optimal schedule would not (or the
# reverse), and that disagreement is itself the interesting case.  The
# sub-population is computed on the PRE-VETO set on purpose: the question is
# what the veto TOOK, so the counterfactual seat must be the one the row would
# have held had the veto not fired.
def dp_seat_cids(records, metric="close"):
    """{cid} the one-position DP would seat, over the TAKEs of `records`.

    The DP runs per session over exactly the rows handed in — this is the
    counterfactual seat set of a candidate POOL, not the session ceiling
    (`dp_ceiling` is the ceiling over every candidate and answers a different
    question)."""
    by = {}
    for rec in records:
        if rec["call"] != CALL_TAKE:
            continue
        o = rec["outcome"]
        by.setdefault((o["asset"], o["date8"]), []).append(o)
    seats = set()
    for key in sorted(by):
        items = []
        for o in by[key]:
            val = o["cert_close_usd"] if metric == "close" else o["cert_peak_usd"]
            end = o["exit_close_sec"] if metric == "close" else o["exit_peak_sec"]
            items.append((o["dec_sec"], end, val, o["dec_sec"], o["row"],
                          o["cid"]))
        _total, chosen = CC.dp_schedule(items)
        seats.update(chosen)
    return seats


def replay_seat_cids(records, metric="close"):
    """{cid} the CHRONOLOGICAL one-position replay seats (the banked reading).

    Same rule as `replay`, returning WHICH rows held the position rather than
    what they were worth."""
    by = {}
    for rec in records:
        if rec["call"] != CALL_TAKE:
            continue
        o = rec["outcome"]
        by.setdefault((o["asset"], o["date8"]), []).append(o)
    seats = set()
    for key in sorted(by):
        seq = sorted(by[key], key=lambda o: (o["dec_sec"], -o["side"]))
        open_until = -1
        for o in seq:
            if o["dec_sec"] <= open_until:
                continue
            seats.add(o["cid"])
            open_until = (o["exit_close_sec"] if metric == "close"
                          else o["exit_peak_sec"])
    return seats


VETO_CENSUS_COLUMNS = ("metric", "seat_reading", "pool", "seat_class", "n",
                       "n_sessions", "mean_close_usd", "mean_peak_usd",
                       "sum_close_usd", "n_winners", "winner_rate",
                       "walled_rate", "n_would_seat")


def veto_census(records, vetoed, metric="close"):
    """The seat-spender split of a veto arm.  -> (rows, summary).

    `records`  every PRE-VETO TAKE (plus SKIPs, ignored) of the arm.
    `vetoed`   the set of cids the veto arm removed.

    Rows are (pool x seat_class) for each seat reading, where pool is VETOED /
    STOOD / ALL and seat_class is WOULD_SEAT / NO_SEAT / ALL.  The row that
    matters is (VETOED, WOULD_SEAT): a veto arm whose vetoed pool is entirely
    NO_SEAT cannot move the replay by a cent, and its pooled mean is a
    statistic about rows that were never going to be traded.
    """
    takes = [r for r in records if r["call"] == CALL_TAKE]
    vetoed = set(vetoed)
    seats = {"DP": dp_seat_cids(takes, metric),
             "REPLAY": replay_seat_cids(takes, metric)}
    rows = []
    summary = {}
    for reading, seat in sorted(seats.items()):
        for pool, sub in (("VETOED", [r for r in takes
                                      if r["outcome"]["cid"] in vetoed]),
                          ("STOOD", [r for r in takes
                                     if r["outcome"]["cid"] not in vetoed]),
                          ("ALL", takes)):
            for scls, pred in (("WOULD_SEAT", lambda o: o["cid"] in seat),
                               ("NO_SEAT", lambda o: o["cid"] not in seat),
                               ("ALL", lambda o: True)):
                sel = [r["outcome"] for r in sub if pred(r["outcome"])]
                n = len(sel)
                cl = np.array([o["cert_close_usd"] for o in sel]) if n else \
                    np.zeros(0)
                pk = np.array([o["cert_peak_usd"] for o in sel]) if n else \
                    np.zeros(0)
                nw = sum(o["winner_" + metric] for o in sel)
                nwall = sum(o["walled"] for o in sel)
                ns = len({(o["asset"], o["date8"]) for o in sel})
                rows.append([metric, reading, pool, scls, n, ns,
                             _mean(cl), _mean(pk),
                             float(cl.sum()) if n else 0.0, int(nw),
                             (nw / n) if n else None,
                             (nwall / n) if n else None,
                             sum(1 for o in sel if o["cid"] in seat)])
                # R54: the key carries ALL THREE loop dimensions, and a
                # collision RAISES rather than silently keeping the last write.
                key = "%s_%s_%s_n" % (reading, pool, scls)
                if key in summary:
                    raise ValueError("veto census summary key collision on %r"
                                     % key)
                summary[key] = n
                if scls == "ALL":
                    summary["%s_%s_n" % (reading, pool)] = n
                if pool == "VETOED" and scls == "WOULD_SEAT":
                    summary["%s_vetoed_seat_spenders" % reading] = n
                    summary["%s_vetoed_seat_value_usd" % reading] = (
                        float(cl.sum()) if n else 0.0)
    # the headline the lesson is about: a veto arm that touches no seat-spender
    # in EITHER reading is replay-inert by construction.
    summary["replay_inert"] = int(
        summary.get("DP_vetoed_seat_spenders", 0) == 0
        and summary.get("REPLAY_vetoed_seat_spenders", 0) == 0)
    summary["n_vetoed"] = len([r for r in takes
                               if r["outcome"]["cid"] in vetoed])
    return rows, summary


def _mean(v):
    return float(np.mean(v)) if len(v) else None


def _sess(o):
    return "%s|%d" % (o["asset"], o["date8"])


def score_group(records):
    """The three metrics over one group of scored records, each with its
    SESSION-CLUSTERED interval (R52)."""
    pairs = [(r["call"], r["outcome"]) for r in records]
    takes = [o for c, o in pairs if c == CALL_TAKE]
    skips = [o for c, o in pairs if c == CALL_SKIP]
    allo = [o for _c, o in pairs]
    out = {"n_calls": len(records), "n_takes": len(takes), "n_skips": len(skips),
           "take_rate": (len(takes) / len(records)) if records else None,
           "n_with_interaction": sum(r["has_interaction"] for r in records),
           "n_sessions": len({_sess(o) for o in allo}),
           "n_days": len({o["date8"] for o in allo}),
           # R23/R132 as VALUES on every certificate block this scorer emits
           "n_cost_fallback": sum(o.get("cost_fallback", 0) for o in allo),
           "n_nonfinite_cert": sum(1 for o in allo
                                   if not o.get("cert_finite", 1))}
    # R53: computed ONCE, outside the metric loop (they do not depend on it).
    out["worst_take_mae_usd"] = max((o["mae_before_argmax"] for o in takes),
                                    default=0.0)
    out["n_walled_takes"] = sum(o["walled"] for o in takes)
    for m in ("close", "peak"):
        k = "cert_%s_usd" % m
        fin = [(c, o) for c, o in pairs if o.get("cert_finite", 1)]
        t = [o[k] for o in takes if o.get("cert_finite", 1)]
        s = [o[k] for o in skips if o.get("cert_finite", 1)]
        mt, ms = _mean(t), _mean(s)
        out["mean_take_%s_usd" % m] = mt
        out["mean_skip_%s_usd" % m] = ms
        ci_t = cluster_mean([o[k] for c, o in fin if c == CALL_TAKE],
                            [_sess(o) for c, o in fin if c == CALL_TAKE])
        ci_s = cluster_mean([o[k] for c, o in fin if c == CALL_SKIP],
                            [_sess(o) for c, o in fin if c == CALL_SKIP])
        for tag, ci in (("take", ci_t), ("skip", ci_s)):
            out["mean_%s_%s_se_cr1" % (tag, m)] = ci["se_cr1"] if ci else None
            out["mean_%s_%s_ci_lo" % (tag, m)] = ci["ci_lo"] if ci else None
            out["mean_%s_%s_ci_hi" % (tag, m)] = ci["ci_hi"] if ci else None
        # a ratio against a non-positive denominator is not a lift
        out["lift_%s" % m] = (mt / ms) if (ms is not None and ms > 0
                                           and mt is not None) else None
        lci = cluster_lift([o[k] for _c, o in fin],
                           [1.0 if c == CALL_TAKE else 0.0 for c, _o in fin],
                           [_sess(o) for _c, o in fin])
        out["lift_%s_se_cr1" % m] = lci["se_cr1"] if lci else None
        out["lift_%s_ci_lo" % m] = lci["ci_lo"] if lci else None
        out["lift_%s_ci_hi" % m] = lci["ci_hi"] if lci else None
        nw = sum(o["winner_" + m] for o in takes)
        out["n_winner_takes_%s" % m] = nw
        out["winner_precision_%s" % m] = (nw / len(takes)) if takes else None
        pci = cluster_mean([float(o["winner_" + m]) for o in takes],
                           [_sess(o) for o in takes])
        out["winner_precision_%s_se_cr1" % m] = pci["se_cr1"] if pci else None
        out["winner_precision_%s_ci_lo" % m] = pci["ci_lo"] if pci else None
        out["winner_precision_%s_ci_hi" % m] = pci["ci_hi"] if pci else None
        out["n_winners_missed_in_skips_%s" % m] = sum(o["winner_" + m]
                                                      for o in skips)
    for m in ("close", "peak"):
        _, tot = replay(records, m)
        out["replay_%s" % m] = tot
    return out


# ------------------------------------------------- D-077 news distance ------
# R35/R12: nothing in this scorer carried "minutes to/from the nearest
# scheduled HIGH-IMPACT release", so the D-077-UPDATE(3) DEPLOYABLE reading was
# not computable from its outputs.  The census file is the ONE source
# (CC-M2-22.4 D-N3: compliance is read from the FLAGS, never inferred from a
# blank minutes field), and its ABSENCE is a refusal, never an empty join
# (R132's `census_flags` returning `{}` on a fresh clone).
NEWS_WINDOW_MIN = 10.0
NEWS_BUCKETS = ("INSIDE_WINDOW", "PRE_RELEASE_WINDOW", "HELD_INTO_WINDOW",
                "POST_10_20MIN", "POST_20MIN_PLUS", "NO_DATED_RELEASE_NEAR")


class NewsDistanceRefusal(RuntimeError):
    """A D-077 reading asked for without the census file that defines it."""


def read_news_distance(path):
    """{cid: row} from news_census's NEWS_DISTANCE.tsv.  REFUSES on absence."""
    if not path or not os.path.exists(path):
        raise NewsDistanceRefusal(
            "%r does not exist: the D-077 reading is REFUSED rather than "
            "computed against an empty join (R132)" % (path,))
    import csv
    with open(path) as fh:
        rows = list(csv.DictReader([l for l in fh if not l.startswith("#")],
                                   delimiter="\t"))
    out = {r["cid"]: r for r in rows}
    need = ("inside_default_window", "pre_release_window", "held_into_window",
            "minutes_since_release")
    if rows and any(c not in rows[0] for c in need):
        raise NewsDistanceRefusal(
            "%s is missing one of %s — the flag contract changed" % (path, need))
    return out


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def news_bucket(cid, nd):
    """The D-077 minutes-since-release band for one candidate.

    Rows absent from the census file are outside its +/-15min reach, which is
    a FACT about the file, so they land in NO_DATED_RELEASE_NEAR under that
    name rather than being called compliant.
    """
    r = nd.get(cid)
    if r is None:
        return NEWS_BUCKETS[-1]
    if str(r.get("inside_default_window")) == "1":
        return "INSIDE_WINDOW"
    if str(r.get("pre_release_window")) == "1":
        return "PRE_RELEASE_WINDOW"
    if str(r.get("held_into_window")) == "1":
        return "HELD_INTO_WINDOW"
    m = _f(r.get("minutes_since_release"))
    if m is None:
        return NEWS_BUCKETS[-1]
    if m < 20.0:
        return "POST_10_20MIN"
    return "POST_20MIN_PLUS"


def score(records, news_distance=None):
    """Attach outcomes, then score every group the gate readings need.

    R35: POOLED / era / asset / block were the only groups, so neither the
    D-077 DEPLOYABLE reading (needs the minutes-since-release split) nor the
    CC-M2-4.4 monotone A|B|C calibration table (needs the confidence split)
    could be produced, and there was no BY-DAY group, so the day-paired bar (a)
    could not be assembled from these outputs either.  All four exist now.
    """
    for rec in records:
        o = outcome(rec["cid"])
        rec["outcome"] = o
        rec["era"] = o["era"]
        rec["asset"] = o["asset"]
        rec["cls"] = o["cls"]
        rec["date8"] = o["date8"]
        rec["news_bucket"] = (news_bucket(rec["cid"], news_distance)
                              if news_distance is not None else None)
    groups = {"POOLED": records}
    for key in ("era", "asset", "cls", "date8", "conf"):
        for rec in records:
            groups.setdefault("%s=%s" % (key, rec[key]), []).append(rec)
    if any(r.get("block") for r in records):
        for rec in records:
            groups.setdefault("block=%s" % rec.get("block", "?"), []).append(rec)
    if news_distance is not None:
        for rec in records:
            groups.setdefault("news=%s" % rec["news_bucket"], []).append(rec)
        deploy = [r for r in records
                  if r["news_bucket"] not in ("INSIDE_WINDOW",
                                              "PRE_RELEASE_WINDOW")]
        groups["reading=DEPLOYABLE_ENTRY_VETO"] = deploy
        groups["reading=DEPLOYABLE_ENTRY_VETO_PLUS_HOLD"] = [
            r for r in deploy if r["news_bucket"] != "HELD_INTO_WINDOW"]
        groups["reading=SCIENCE"] = records
    return {g: score_group(rs) for g, rs in sorted(groups.items())}


# ----------------------------------------------------------------- output ---
CALL_COLUMNS = ("cid", "asset", "era", "cls", "trade_date", "date8", "dec_sec",
                "side", "call", "conf", "has_interaction", "news_bucket",
                "cert_close_usd", "cert_peak_usd",
                "mae_before_argmax", "walled", "winner_close", "winner_peak",
                "cost_fallback", "cert_finite",
                "primary", "against", "interaction", "novel")


def write_report(records, groups, out_dir, label):
    phash = MC.params_hash(PARAMS)
    rows = []
    for r in sorted(records, key=lambda r: (r["asset"], r["outcome"]["date8"],
                                            r["outcome"]["dec_sec"])):
        o = r["outcome"]
        rows.append([r["cid"], o["asset"], o["era"], o["cls"],
                     o["trade_date"].isoformat(), o["date8"],
                     o["dec_sec"], o["side"], r["call"], r["conf"],
                     r["has_interaction"], r.get("news_bucket"),
                     o["cert_close_usd"],
                     o["cert_peak_usd"], o["mae_before_argmax"], o["walled"],
                     o["winner_close"], o["winner_peak"],
                     o.get("cost_fallback", 0), o.get("cert_finite", 1),
                     r["primary"], r["against"], r["interaction"], r["novel"]])
    MC.write_tsv(os.path.join(out_dir, "PANEL_CALLS_%s.tsv" % label), SECTION,
                 phash, list(CALL_COLUMNS), rows,
                 extra=["one row per scored call; certificates from the frozen "
                        "v3 roster via c_c_roster.certificates"])
    srows = []
    for g in sorted(groups):
        s = groups[g]
        rp = s["replay_close"]
        srows.append([g, s["n_calls"], s["n_takes"], s["n_skips"],
                      s["n_sessions"], s["n_days"], s["n_with_interaction"],
                      s["mean_take_close_usd"], s["mean_take_close_se_cr1"],
                      s["mean_skip_close_usd"], s["mean_skip_close_se_cr1"],
                      s["lift_close"], s["lift_close_se_cr1"],
                      s["lift_close_ci_lo"], s["lift_close_ci_hi"],
                      s["winner_precision_close"],
                      s["winner_precision_close_ci_lo"],
                      s["winner_precision_close_ci_hi"],
                      s["n_winners_missed_in_skips_close"],
                      s["mean_take_peak_usd"], s["mean_skip_peak_usd"],
                      s["lift_peak"], s["winner_precision_peak"],
                      rp["realised_usd"], rp["dp_ceiling_usd"], rp["capture"],
                      rp["capture_ci_lo"], rp["capture_ci_hi"],
                      rp["realised_per_session"], rp["n_forfeited"],
                      rp["n_refused_cert"],
                      s["n_cost_fallback"], s["n_nonfinite_cert"]])
    MC.write_tsv(os.path.join(out_dir, "PANEL_SCORE_%s.tsv" % label), SECTION,
                 phash,
                 ["group", "n_calls", "n_takes", "n_skips", "n_sessions",
                  "n_days", "n_with_interaction",
                  "mean_take_close_usd", "mean_take_close_se_cr1",
                  "mean_skip_close_usd", "mean_skip_close_se_cr1",
                  "lift_close", "lift_close_se_cr1", "lift_close_ci_lo",
                  "lift_close_ci_hi",
                  "winner_precision_close", "winner_precision_close_ci_lo",
                  "winner_precision_close_ci_hi",
                  "winners_missed_in_skips_close",
                  "mean_take_peak_usd", "mean_skip_peak_usd", "lift_peak",
                  "winner_precision_peak", "replay_realised_usd",
                  "replay_dp_ceiling_usd", "replay_capture",
                  "replay_capture_ci_lo", "replay_capture_ci_hi",
                  "replay_usd_per_session", "replay_forfeited",
                  "replay_refused_cert",
                  "n_cost_fallback", "n_nonfinite_cert"], srows,
                 extra=["CC-M1-8: close = adoption metric, peak = companion",
                        "R52: every interval is a Cameron-Miller CR1 "
                        "cluster-robust 95% interval, clustered on SESSION "
                        "(asset x date); a lift interval is REFUSED (empty) "
                        "wherever the SKIP mean is not positive, exactly as "
                        "the point estimate is",
                        "R23/R132: n_cost_fallback counts certificates "
                        "computed on the substituted constant cost and "
                        "n_nonfinite_cert counts refused certificates; both "
                        "are 0 in --strict mode because it refuses instead"])
    MC.write_json(os.path.join(out_dir, "panel_score_%s.receipt.json" % label),
                  {"env": MC.env_receipt(PARAMS), "label": label,
                   "n_calls": len(records), "refusals": refusal_counts(),
                   "groups": groups})
    return groups


def render_table(groups):
    L = ["group                 calls  take  skip | mean_take$ mean_skip$  lift"
         " | winprec | replay$   dp$    capture"]
    for g in sorted(groups):
        s = groups[g]
        r = s["replay_close"]
        L.append("%-20s %6d %5d %5d | %10.0f %10.0f %5s | %6s  | %8.0f %8.0f %7s"
                 % (g[:20], s["n_calls"], s["n_takes"], s["n_skips"],
                    s["mean_take_close_usd"] or 0.0,
                    s["mean_skip_close_usd"] or 0.0,
                    "%.2f" % s["lift_close"]
                    if s["lift_close"] is not None else "NA",
                    "%.2f" % s["winner_precision_close"]
                    if s["winner_precision_close"] is not None else "NA",
                    r["realised_usd"], r["dp_ceiling_usd"],
                    "%.3f" % r["capture"] if r["capture"] is not None else "NA"))
    return "\n".join(L)


# R25.  The old reader (a) treated ANY token other than "-"/""/"none" as a
# veto mark — a stray whitespace cell or a literal `0` marked the row vetoed —
# and (b) sniffed for a header on EVERY line, so a data row whose free text
# contained "cid" or "veto" was eaten as a header.  Both are fixed here: the
# header is the FIRST non-comment line and nothing else, and the veto column is
# read against a declared vocabulary with an unknown token REFUSED.
VETO_UNMARKED = ("-", "", "none", "NONE", "None", "0", "no", "NO", "n", "N",
                 "false", "FALSE", "False")
VETO_MARKED = ("1", "yes", "YES", "y", "Y", "true", "TRUE", "True", "V2", "V3",
               "V1", "VETO", "veto")


class VetoFormatError(ValueError):
    """An unreadable veto column.  A miscounted veto arm is a wrong census."""


def _read_vetoed(path):
    """{cid} from a seal ARMS file (cid ... veto ...) or a bare cid list."""
    out = set()
    with open(path) as fh:
        hdr = None
        first = True
        for lineno, line in enumerate(fh, 1):
            if line.startswith("#") or not line.strip():
                continue
            f = [x.strip() for x in line.rstrip("\n").split("\t")]
            if first:
                first = False
                if "cid" in f or "veto" in f:      # the header, or no header
                    hdr = f
                    continue
            if hdr is not None and "veto" in hdr:
                d = dict(zip(hdr, f))
                v = d.get("veto", "-").strip()
                if v in VETO_UNMARKED:
                    continue
                if v in VETO_MARKED or v.startswith("V"):
                    out.add(d["cid"])
                    continue
                raise VetoFormatError(
                    "%s:%d unrecognised veto token %r — a veto census counted "
                    "on a guess is a wrong census (R25)" % (path, lineno, v))
            else:
                out.add(f[0])
    return out


# ------------------------------------------------------- CC-M2-6 bar (a) ----
# R04.  `score_group` computed lift, winner precision and replay totals and
# NOTHING else — no SEs, no clustering, no pairing, no significance — and
# `score()` had no BY-DAY group, so the registered bar ("margin over the BEST
# mechanical baseline, day-paired, cluster-robust") could not be assembled from
# the outputs of the module the spec calls "the only judge".  It can now, off
# ONE table.
BASELINE_DAY_COLUMNS = ("arm", "asset", "date8", "n_takes", "n_seated",
                        "n_forfeited", "n_refused_cert", "realised_usd",
                        "dp_ceiling_usd", "capture")
BASELINE_MARGIN_COLUMNS = (
    "reference", "arm", "grain", "n_pairs", "n_clusters", "reader_usd",
    "arm_usd", "sum_margin_usd", "mean_margin_usd", "se_cr1", "ci_lo", "ci_hi",
    "t", "p", "p_holm", "days_positive", "days_negative", "p_sign")


def arm_day_rows(name, records, metric="close"):
    rows, _tot = replay(records, metric)
    return [[name, r["asset"], r["date8"], r["n_takes"], r["n_seated"],
             r["n_forfeited"], r["n_refused_cert"], r["realised_usd"],
             r["dp_ceiling_usd"], r["capture"]] for r in rows]


def baseline_margins(reader_records, arms, metric="close",
                     preregistered=PREREGISTERED_ARM):
    """The bar (a) table: per-(asset, day) dollars, day-paired margins, CR1.

    `arms` is {arm_name: [records]} — every arm scored on the SAME universe as
    the reader (the caller guarantees the cid sets match; `main` asserts it).

    Returns (day_rows, margin_rows, verdict).  The verdict scores bar (a) in
    its CONSERVATIVE reading — positive against EVERY arm — and carries the
    pre-registered arm, the MEDIAN arm and the in-sample maximum beside it,
    each labelled.
    """
    reader_days = {(r[1], r[2]): r[7]
                   for r in arm_day_rows("READER", reader_records, metric)}
    day_rows = arm_day_rows("READER", reader_records, metric)
    per_arm = {}
    for name in sorted(arms):
        rr = arm_day_rows(name, arms[name], metric)
        day_rows += rr
        per_arm[name] = {(r[1], r[2]): r[7] for r in rr}

    # the pairing universe: every (asset, day) ANY arm or the reader traded.
    # A day an arm never saw is NOT a $0.00 day (R126's related MINOR: the two
    # cases were indistinguishable) — it is refused out of that arm's pairing
    # and counted.
    sessions = sorted(set(reader_days) | {k for v in per_arm.values()
                                          for k in v})
    days = sorted({d for _a, d in sessions})
    rows, pvals = [], []
    for name in sorted(per_arm):
        a_sess = per_arm[name]
        # DAY grain (the registered pairing): one observation per day.
        rd = {d: sum(reader_days.get((a, dd), 0.0)
                     for a, dd in sessions if dd == d) for d in days}
        ad = {d: sum(a_sess.get((a, dd), 0.0)
                     for a, dd in sessions if dd == d) for d in days}
        m = np.array([rd[d] - ad[d] for d in days], dtype=np.float64)
        cm = cluster_mean(m, [str(d) for d in days])
        sg = sign_test(m)
        rows.append(["EVERY_ARM", name, "day", len(days),
                     cm["n_clusters"] if cm else None,
                     float(sum(rd.values())), float(sum(ad.values())),
                     float(m.sum()), cm["mean"] if cm else None,
                     cm["se_cr1"] if cm else None, cm["ci_lo"] if cm else None,
                     cm["ci_hi"] if cm else None, cm["t"] if cm else None,
                     cm["p"] if cm else None, None,
                     sg["n_pos"], sg["n_neg"], sg["p_sign"]])
        pvals.append(cm["p"] if cm else None)
        # SESSION grain, clustered on DAY (the effective-n correction
        # D-065-AMENDMENT names).
        ms = np.array([reader_days.get(k, 0.0) - a_sess.get(k, 0.0)
                       for k in sessions], dtype=np.float64)
        cs = cluster_mean(ms, [str(d) for _a, d in sessions])
        sgs = sign_test(ms)
        rows.append(["EVERY_ARM", name, "session", len(sessions),
                     cs["n_clusters"] if cs else None,
                     float(sum(reader_days.get(k, 0.0) for k in sessions)),
                     float(sum(a_sess.get(k, 0.0) for k in sessions)),
                     float(ms.sum()), cs["mean"] if cs else None,
                     cs["se_cr1"] if cs else None, cs["ci_lo"] if cs else None,
                     cs["ci_hi"] if cs else None, cs["t"] if cs else None,
                     cs["p"] if cs else None, None,
                     sgs["n_pos"], sgs["n_neg"], sgs["p_sign"]])
        pvals.append(None)                 # Holm runs over the DAY grain only
    adj = holm(pvals)
    for r, p in zip(rows, adj):
        r[14] = p

    totals = {n: sum(v.values()) for n, v in per_arm.items()}
    reader_total = float(sum(reader_days.values()))
    day_grain = {r[1]: r for r in rows if r[2] == "day"}
    verdict = {
        "metric": metric,
        "rule": BAR_A_RULE,
        "n_arms": len(per_arm),
        "reader_realised_usd": reader_total,
        "arms_beaten": sorted(n for n in per_arm if reader_total > totals[n]),
        "arms_lost_to": sorted(n for n in per_arm if reader_total <= totals[n]),
        "positive_against_all": int(all(day_grain[n][7] > 0 for n in per_arm))
        if per_arm else None,
        "preregistered_arm": preregistered,
        "preregistered_margin_usd": (day_grain[preregistered][7]
                                     if preregistered in day_grain else None),
        "preregistered_p": (day_grain[preregistered][13]
                            if preregistered in day_grain else None),
        "median_arm_total_usd": (float(np.median(list(totals.values())))
                                 if totals else None),
        "margin_vs_median_arm_usd": (reader_total
                                     - float(np.median(list(totals.values()))))
        if totals else None,
        "max_arm_IN_SAMPLE_ORDER_STATISTIC": (
            min(sorted(totals), key=lambda n: (-totals[n], n))
            if totals else None),
        "margin_vs_max_arm_usd_IN_SAMPLE": (
            reader_total - max(totals.values())) if totals else None,
        "max_arm_caveat": "the max over arms is selected ON the evaluation "
                          "days themselves; it is an in-sample order "
                          "statistic and biases the reader's margin DOWNWARD "
                          "(R126) — it is NOT the bar",
    }
    return day_rows, rows, verdict


def _arm_records(path, universe):
    """A baseline arm's calls, restricted to the reader's own universe.

    R132: `callmap.get(c, "SKIP")` silently scored an arm that emitted fewer
    rows than the universe as skipping the remainder.  The cid sets must MATCH.
    """
    recs = parse_ledger(path)
    have = {r["cid"] for r in recs}
    if have != set(universe):
        raise LedgerError(
            "%s: arm cid set differs from the scored universe (arm-only %d, "
            "universe-only %d) — an arm that did not call every candidate has "
            "no day-complete replay (R132)"
            % (path, len(have - set(universe)), len(set(universe) - have)))
    for r in recs:
        r["outcome"] = outcome(r["cid"])
    return recs


def main():
    p = argparse.ArgumentParser()
    p.add_argument("ledger")
    p.add_argument("--out", default=MC.out_path("panel", "_")[:-1])
    p.add_argument("--label", default=None)
    p.add_argument("--strict", action="store_true",
                   help="gate mode: REFUSE on a missing per-session cost or a "
                        "non-finite certificate instead of substituting")
    p.add_argument("--news-distance", default=None,
                   help="news_census NEWS_DISTANCE.tsv; enables the D-077 "
                        "minutes-since-release groups and the two DEPLOYABLE "
                        "readings.  Absent, the reading is REFUSED, never "
                        "computed against an empty join")
    p.add_argument("--baselines", nargs="*", default=None,
                   help="mechanical arm call files; emits the CC-M2-6 bar (a) "
                        "table (per-(asset,day) dollars + day-paired "
                        "cluster-robust margins, Holm-adjusted)")
    p.add_argument("--preregistered-arm", default=PREREGISTERED_ARM)
    p.add_argument("--veto-arms", default=None,
                   help="a seal ARMS tsv (cid/veto columns) or a cid list; "
                        "emits PANEL_VETO_CENSUS_<label>.tsv with the "
                        "CC-M2-17.4 seat-spender split")
    a = p.parse_args()
    MC.verify_spec(force=True)
    set_strict(a.strict)
    label = a.label or os.path.basename(a.ledger).split(".")[0]
    records = parse_ledger(a.ledger)
    nd = read_news_distance(a.news_distance) if a.news_distance else None
    groups = score(records, news_distance=nd)
    write_report(records, groups, a.out, label)
    sys.stdout.write(render_table(groups) + "\n")
    if a.baselines:
        universe = [r["cid"] for r in records]
        arms = {}
        for path in a.baselines:
            name = os.path.basename(path).split(".")[0]
            arms[name] = _arm_records(path, universe)
        day_rows, marg_rows, verdict = baseline_margins(
            records, arms, "close", a.preregistered_arm)
        phash = MC.params_hash(PARAMS)
        MC.write_tsv(os.path.join(a.out, "PANEL_BASELINE_DAYS_%s.tsv" % label),
                     SECTION, phash, list(BASELINE_DAY_COLUMNS), day_rows,
                     extra=["per (asset, day) realised dollars of the reader "
                            "arm and every mechanical arm, one-position "
                            "chronological replay at the phase-close reading"])
        MC.write_tsv(os.path.join(a.out,
                                  "PANEL_BASELINE_MARGINS_%s.tsv" % label),
                     SECTION, phash, list(BASELINE_MARGIN_COLUMNS), marg_rows,
                     extra=["CC-M2-6 bar (a): " + BAR_A_RULE,
                            "day grain = the REGISTERED pairing (one "
                            "observation per day); session grain is the same "
                            "difference at (asset, day) grain clustered on "
                            "DAY (D-065-AMENDMENT effective-n)",
                            "p_holm is Holm-Bonferroni over the DAY-grain "
                            "arm set; the session rows carry no adjusted p",
                            verdict["max_arm_caveat"]])
        MC.write_json(os.path.join(a.out, "panel_bar_a_%s.json" % label),
                      {"env": MC.env_receipt(PARAMS), "label": label,
                       "refusals": refusal_counts(), **verdict})
        sys.stdout.write(
            "bar (a) [%s]: reader $%.2f; positive against all %s arms: %s; "
            "vs pre-registered %s $%+.2f (p=%s); vs MEDIAN arm $%+.2f; vs "
            "max-of-arms (IN-SAMPLE) $%+.2f\n"
            % (verdict["metric"], verdict["reader_realised_usd"],
               verdict["n_arms"], verdict["positive_against_all"],
               verdict["preregistered_arm"],
               verdict["preregistered_margin_usd"] or 0.0,
               verdict["preregistered_p"],
               verdict["margin_vs_median_arm_usd"] or 0.0,
               verdict["margin_vs_max_arm_usd_IN_SAMPLE"] or 0.0))
    if a.veto_arms:
        vetoed = _read_vetoed(a.veto_arms)
        rows, summ = [], {}
        for metric in ("close", "peak"):
            rr, ss = veto_census(records, vetoed, metric)
            rows += rr
            summ[metric] = ss
        MC.write_tsv(os.path.join(a.out, "PANEL_VETO_CENSUS_%s.tsv" % label),
                     SECTION, MC.params_hash(PARAMS),
                     list(VETO_CENSUS_COLUMNS), rows,
                     extra=["CC-M2-17.4 seat-spender split: the (VETOED, "
                            "WOULD_SEAT) row is the only one that can move a "
                            "replay; a veto arm with n=0 there is REPLAY-INERT "
                            "whatever its pooled mean says (ERA_NOTES_E1 §67)",
                            "seat_reading DP = the one-position DP schedule "
                            "over the PRE-VETO take set; REPLAY = the "
                            "chronological one-position seating of the same "
                            "set"])
        for metric in ("close", "peak"):
            s = summ[metric]
            sys.stdout.write(
                "veto census [%s]: %d vetoed; seat-spenders DP=%d ($%.2f) "
                "REPLAY=%d ($%.2f); replay_inert=%d\n"
                % (metric, s["n_vetoed"], s["DP_vetoed_seat_spenders"],
                   s["DP_vetoed_seat_value_usd"],
                   s["REPLAY_vetoed_seat_spenders"],
                   s["REPLAY_vetoed_seat_value_usd"], s["replay_inert"]))
    rc = refusal_counts()
    if rc["n_cost_fallback_sessions"] or rc["n_nonfinite_cert"]:
        sys.stdout.write(
            "REFUSALS COUNTED (R23/R132): %d session(s) scored on the "
            "substituted constant cost, %d non-finite certificate(s) excluded "
            "from every mean and from the replay — re-run with --strict to "
            "refuse instead\n" % (rc["n_cost_fallback_sessions"],
                                  rc["n_nonfinite_cert"]))
    MC.hb("panel_score %s: %d calls scored -> %s" % (label, len(records), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
