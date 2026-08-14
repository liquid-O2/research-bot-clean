#!/usr/bin/python3
"""PORT M2 — render provenance/port_m2/PRECISION_FRONTIER.md from the TSVs.

Every table below is read from the committed TSVs; nothing is retyped.  The
HEADLINE and VERDICT prose blocks are written by hand into the file after this
generator has produced the tables (the numbers in them are quoted FROM these
tables, and the tables are the authority).
"""
import json
import os
import sys

PROV = "/workspace/provenance/port_m2"
M3PROV = "/workspace/provenance/port_m3"
OUT = os.path.join(PROV, "PRECISION_FRONTIER.md")
CACHE = "/workspace/artifacts/cache/port/m2/frontier"


def read(path):
    rows, hdr = [], None
    with open(path) as fh:
        for ln in fh:
            if ln.startswith("#") or not ln.strip():
                continue
            f = ln.rstrip("\n").split("\t")
            if hdr is None:
                hdr = f
                continue
            rows.append(dict(zip(hdr, f)))
    return rows


def f(v, nd=2, dollar=False, pct=False):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "."
    if x != x:
        return "."
    if pct:
        return "%.1f%%" % (100.0 * x)
    if dollar:
        return ("$%,.0f" % x).replace(",", " ") if abs(x) >= 1000 \
            else "$%.0f" % x
    return ("%%.%df" % nd) % x


def md(cols, rows):
    out = ["| " + " | ".join(cols) + " |",
           "|" + "|".join(["---"] * len(cols)) + "|"]
    for r in rows:
        # a literal pipe inside a cell ends the cell in GFM, and every operating
        # point in this report is named `family|point` — escape, never rename.
        out.append("| " + " | ".join(str(x).replace("|", "\\|") for x in r)
                   + " |")
    return "\n".join(out)


def sec_teacher():
    L = ["## 1. THE TEACHER-FEATURE INJECTION (D-078) — THE CLEAN DIFF", ""]
    rows = read(os.path.join(PROV, "TEACHER_MARGINAL.tsv"))
    body = []
    for r in rows:
        body.append([r["era"], r["notf_policy"],
                     f(r["notf_usd_per_session"], dollar=True),
                     f(r["tf_usd_per_session"], dollar=True),
                     f(r["delta_usd_per_session"], dollar=True),
                     f(r["notf_expectancy_usd"], dollar=True),
                     f(r["tf_expectancy_usd"], dollar=True),
                     f(r["delta_expectancy_usd"], dollar=True),
                     f(r["notf_capture_day_ceiling"], 4),
                     f(r["tf_capture_day_ceiling"], 4),
                     r["control_reproduces_committed"]])
    L.append(md(["era", "policy", "$/session NO teacher", "$/session WITH",
                 "Δ $/session", "$/trade NO", "$/trade WITH", "Δ $/trade",
                 "capture NO", "capture WITH", "control == committed?"], body))
    L.append("")
    # how much of the model's gain the teacher columns actually carry
    p = os.path.join("/workspace/artifacts/cache/port/m3/walk_tf",
                     "IMPORTANCE.tsv")
    if os.path.exists(p):
        imp = read(p)
        by = {}
        for r in imp:
            if r["group"] == "teacher_evidence":
                by.setdefault(r["era"], []).append(
                    (int(r["rank"]), r["feature"], float(r["gain_share"])))
        if by:
            L.append("**Where the teacher columns land in the model's own "
                     "gain ranking** (top-20 only; a group absent from an "
                     "era's top-20 is absent from this table):")
            L.append("")
            L.append(md(["era", "teacher columns in the top-20",
                         "their summed gain share"],
                        [[e, ", ".join("%s (#%d)" % (n, k)
                                       for k, n, _g in sorted(v)),
                          f(sum(g for _k, _n, g in v), 4)]
                         for e, v in sorted(by.items())]))
            L.append("")
    return "\n".join(L)


def _mrow(r):
    return [r["tier"], r["n_seated"], f(r["takes_per_week"], 1),
            "%s [%s, %s]" % (f(r["precision"], 3), f(r["precision_lo"], 3),
                             f(r["precision_hi"], 3)),
            "%s [%s, %s]" % (f(r["usd_per_trade"], 0),
                             f(r["usd_per_trade_lo"], 0),
                             f(r["usd_per_trade_hi"], 0)),
            f(r["usd_per_day"], 0), f(r["usd_per_traded_day"], 0),
            f(r["usd_per_week"], 0), f(r["usd_week_p10"], 0),
            f(r["frac_losing_weeks"], 2), f(r["usd_per_session_all"], 0)]


MHEAD = ["tier", "n takes", "takes/wk", "precision [CI]", "$/trade [CI]",
         "$/day", "$/traded-day", "$/week", "week p10", "losing wks",
         "$/session"]


def sec_threshold():
    rows = read(os.path.join(PROV, "PRECISION_FRONTIER_THRESHOLD.tsv"))
    L = ["## 2. THE THRESHOLD FRONTIER", ""]
    for grain in ("candidate", "episode"):
        L.append("### 2.%d %s grain — the best model (FULL_TF)"
                 % (1 if grain == "candidate" else 2, grain))
        L.append("")
        for era in sorted(set(r["era"] for r in rows)):
            sel = [r for r in rows if r["era"] == era and r["grain"] == grain
                   and r["score"] == "FULL_TF"]
            if not sel:
                continue
            L.append("**%s**" % era)
            L.append("")
            L.append(md(MHEAD, [_mrow(r) for r in sel]))
            L.append("")
    L.append("### 2.3 the SHUFFLED-SCORE control (candidate grain)")
    L.append("")
    L.append("A permuted score must produce a FLAT frontier.  If precision "
             "and $/trade rise with the tier here, the frontier above is an "
             "artefact of the selection arithmetic and not of the score.")
    L.append("")
    for era in sorted(set(r["era"] for r in rows)):
        sel = [r for r in rows if r["era"] == era and r["grain"] == "candidate"
               and r["score"] == "SHUFFLE"]
        if not sel:
            continue
        L.append("**%s (shuffled)**" % era)
        L.append("")
        L.append(md(MHEAD, [_mrow(r) for r in sel]))
        L.append("")
    L.append("### 2.4 the strictly-causal threshold (previous era's cut)")
    L.append("")
    L.append("The tiers above cut at a percentile of the EVAL era's own score "
             "distribution, which no deployed system knows in advance.  Here "
             "the cut is the same percentile of the PREVIOUS era's "
             "out-of-sample scores, applied unchanged.")
    L.append("")
    for era in sorted(set(r["era"] for r in rows)):
        sel = [r for r in rows if r["era"] == era and r["grain"] == "candidate"
               and r["score"] == "FULL_TF_PREVCUT"]
        if not sel:
            continue
        L.append("**%s (previous-era cut)**" % era)
        L.append("")
        L.append(md(MHEAD, [_mrow(r) for r in sel]))
        L.append("")
    return "\n".join(L)


def sec_calibration():
    rows = read(os.path.join(PROV, "PRECISION_FRONTIER_CALIBRATION.tsv"))
    L = ["## 3. CALIBRATION — predicted vs realised winner rate", "",
         "Over CANDIDATES inside each tier (not over seats): this is a "
         "statement about the score, not about the schedule.  The head is "
         "fitted with squared error on the 0/1 D-021 winner label, so its "
         "output is a predicted RATE and the two columns are directly "
         "comparable.", ""]
    for era in sorted(set(r["era"] for r in rows)):
        sel = [r for r in rows if r["era"] == era and r["score"] == "FULL_TF"]
        if not sel:
            continue
        L.append("**%s**" % era)
        L.append("")
        L.append(md(["tier", "n", "predicted", "realised [CI]", "realised −"
                     " predicted", "score range"],
                    [[r["tier"], r["n_candidates"], f(r["predicted_rate"], 4),
                      "%s [%s, %s]" % (f(r["realised_rate"], 4),
                                       f(r["realised_ci_lo"], 4),
                                       f(r["realised_ci_hi"], 4)),
                      f(r["realised_minus_predicted"], 4),
                      "%s … %s" % (f(r["score_min"], 3), f(r["score_max"], 3))]
                     for r in sel]))
        L.append("")
    return "\n".join(L)


def sec_daygate():
    rows = read(os.path.join(PROV, "PRECISION_FRONTIER_DAYGATE.tsv"))
    L = ["## 4. THE DAY-ABSTENTION FRONTIER", "",
         "`causal_top3_running`: an (asset, day) qualifies the instant its "
         "RUNNING top-3 mean of already-arrived candidate scores crosses the "
         "gate; entries are allowed from that second on.  No day-end quantity "
         "is read anywhere.  `preday_forecaster`: the oracle-free variant — a "
         "walk-forward day-value model on the forecaster and overnight state "
         "as of the day's FIRST candidate second, with no candidate score in "
         "it at all.", ""]
    for gate in ("causal_top3_running", "preday_forecaster"):
        L.append("### 4.%d %s" % (1 if gate.startswith("causal") else 2, gate))
        L.append("")
        for era in sorted(set(r["era"] for r in rows)):
            sel = [r for r in rows if r["era"] == era and r["gate"] == gate]
            if not sel:
                continue
            L.append("**%s**" % era)
            L.append("")
            L.append(md(["gate pct", "sessions qualified", "tier", "n takes",
                         "takes/wk", "precision", "$/trade", "$/traded-day",
                         "$/week", "frac days traded"],
                        [[r["gate_pct"], r["n_sessions_qualified"], r["tier"],
                          r["n_seated"], f(r["takes_per_week"], 1),
                          f(r["precision"], 3), f(r["usd_per_trade"], 0),
                          f(r["usd_per_traded_day"], 0),
                          f(r["usd_per_week"], 0),
                          f(r["frac_days_traded"], 3)] for r in sel]))
            L.append("")
    return "\n".join(L)


def sec_agreement():
    rows = read(os.path.join(PROV, "PRECISION_FRONTIER_AGREEMENT.tsv"))
    L = ["## 5. AGREEMENT TIERS — three independent readers of the same second",
         "",
         "`FULL_TF` = the full model with teacher features; `TEACHER` = the 18 "
         "teacher-evidence columns alone; `SEQ` = the raw event-stream cue "
         "block alone.  All three are walk-forward fits of the same D-021 "
         "winner head on the same rows.", ""]
    for era in sorted(set(r["era"] for r in rows)):
        sel = [r for r in rows if r["era"] == era]
        if not sel:
            continue
        L.append("**%s**" % era)
        L.append("")
        L.append(md(["rule", "tier", "n takes", "takes/wk", "precision [CI]",
                     "$/trade", "$/week", "$/session"],
                    [[r["rule"], r["tier"], r["n_seated"],
                      f(r["takes_per_week"], 1),
                      "%s [%s, %s]" % (f(r["precision"], 3),
                                       f(r["precision_lo"], 3),
                                       f(r["precision_hi"], 3)),
                      f(r["usd_per_trade"], 0), f(r["usd_per_week"], 0),
                      f(r["usd_per_session_all"], 0)] for r in sel]))
        L.append("")
    return "\n".join(L)


def sec_verdict():
    rows = read(os.path.join(PROV, "PRECISION_FRONTIER_VERDICT.tsv"))
    L = ["## 6. THE VERDICT PLANE at the user's weekly throughput floor", "",
         "Every operating point measured in §2–§5 — threshold x day-abstention "
         "x agreement — filtered to a minimum of N portfolio takes per week "
         "(all three assets together) and then maximised three ways.", ""]
    for era in sorted(set(r["era"] for r in rows)):
        sel = [r for r in rows if r["era"] == era]
        L.append("**%s**" % era)
        L.append("")
        L.append(md(["floor takes/wk", "criterion", "operating point",
                     "n takes", "takes/wk", "precision [CI]", "$/trade",
                     "$/week", "week p10", "losing wks", "$/session",
                     "vs D-048"],
                    [[r["week_floor_takes"], r["criterion"],
                      "`%s`" % r["operating_point"], r["n_seated"],
                      f(r["takes_per_week"], 1),
                      "%s [%s, %s]" % (f(r["precision"], 3),
                                       f(r["precision_lo"], 3),
                                       f(r["precision_hi"], 3)),
                      f(r["usd_per_trade"], 0), f(r["usd_per_week"], 0),
                      f(r["usd_week_p10"], 0), f(r["frac_losing_weeks"], 2),
                      f(r["usd_per_session_all"], 0), f(r["vs_D048_2000"], 0)]
                     for r in sel]))
        L.append("")
    return "\n".join(L)


HEADER = """# THE PRECISION FRONTIER

`PORT-M2-PRECISION-FRONTIER-V1` · `engine/port_m2/precision_frontier.py`
(scores, day gate, frontier) · `engine/port_m3/m3_matrix.py` (the teacher
columns) · `engine/port_m3/m3_walk.py --drop-groups` (the D-078 control) ·
`engine/port_m2/teacher_marginal.py` (the clean diff).

Matrix: 1,399,374 candidate rows x 202 features (184 pre-teacher + 18
teacher-evidence), 3,341 asset-sessions, SI/HG/NKD, holdout excluded by the
guarded enumerator.  Every model is walk-forward: model_k is fitted only on
eras strictly before era k and scored on era k.  Reported eras E3, E4, E5, E6
and E8 (the GATE-2025H1 echo); E2 and E7 are fitted so that every reported era
has a previous era's score distribution to calibrate a causal threshold from.

Intervals are CR1 sandwich intervals CLUSTERED BY CALENDAR DAY (D-036/D-073).
`takes/wk`, `$/week` and `$/day` are PORTFOLIO totals across SI+HG+NKD;
`$/session` is the D-048 denominator (realised dollars over EVERY asset-session
of the era, traded or not).

<!-- HEADLINE -->

---
"""

FOOTER = """
---

## 7. INSTRUMENT RECEIPTS

* **The D-078 control reproduces the committed curve.** `m3_walk --drop-groups
  teacher_evidence` over the new 202-column matrix returns, era for era, the
  numbers committed in `provenance/port_m3/ERA_CURVE.tsv` — same `$/session`,
  same `$/trade`, same selected policy.  The teacher group is appended at the
  end of the registry, so the dropped run's feature block is the pre-teacher
  block, column for column.  Column `control_reproduces_committed` in
  `TEACHER_MARGINAL.tsv` carries the check per era.
* **Red-first, shuffled score.**  §2.3 is the receipt: the same pipeline, the
  same replay, the same tiers, with FULL_TF's own scores permuted within the
  era under the pinned seed.
* **Guards.**  The matrix rebuild passed the D-058 holdout guard, the
  forbidden-source NAME guard and the |Spearman| > 0.98 forward-VALUE guard on
  all 202 columns (`artifacts/cache/port/m3/matrix/matrix.receipt.json`);
  `engine/port_m3/test_m3.py --fast` is 13/13 green with the D-078 instrument
  test rewritten for its fired state.
* **Sequence cues.**  1,399,374 / 1,399,374 rows covered, 0 errors, 585 s at 8
  workers, 120 s pre-decision window, `seq_cues.cues_from_window` unchanged
  (`artifacts/cache/port/m2/frontier/seq.receipt.json`).
* **Causality of the day gate.**  `day_qualification` reads only the scores of
  candidates that have ALREADY fired on that asset-day; the qualifying
  candidate is seatable at its own decision second and every later candidate of
  the day is seatable too.  The pre-day gate reads no candidate score at all.
* **What is NOT measured here.**  The trade shape is unchanged throughout
  (confirmation entry, $900 wall, ride to phase close) — the exit contract
  remains the one never-measured variant class (D-029, user-reserved).  The
  teacher columns are E6-derived definitions re-fitted inside every training
  fold (D-034); no threshold from the round is used as a fitted constant.
"""


def sec_ladders():
    """The two era-ladder censuses and the redundancy test — the WHY behind §1."""
    L = ["## 1b. THE TEACHER'S CUES, RE-MEASURED ON THE WHOLE ERA LADDER", "",
         "`TEACHER_FEATURES_V1` §7 is explicit that its numbers are six days of "
         "one era and that the harness must re-derive every threshold in its "
         "own folds before any cue is allowed to carry weight.  This is that "
         "re-measurement: 1.4M candidates, eight eras, the same D-021 target, "
         "day-clustered intervals (`TEACHER_CUE_ERA_LADDER.tsv`).", ""]
    rows = read(os.path.join(PROV, "TEACHER_CUE_ERA_LADDER.tsv"))
    eras = sorted(set(r["era"] for r in rows))
    gates = []
    for r in rows:
        if r["gate"] not in gates:
            gates.append(r["gate"])
    body = []
    for g in gates:
        by = {r["era"]: r for r in rows if r["gate"] == g}
        lifts = [by[e]["lift"] for e in eras if e in by]
        pos = sum(1 for x in lifts if x not in (".", "") and float(x) > 1.0)
        body.append([g, by[eras[0]]["round1_2_verdict"]]
                    + [f(by[e]["lift"], 2) if e in by else "." for e in eras]
                    + ["%d/%d" % (pos, len(eras))])
    L.append(md(["cue", "round 1/2 verdict"] + eras + ["eras above 1x"], body))
    L.append("")
    L.append("## 1c. WAS ANY OF IT NEW INFORMATION?")
    L.append("")
    L.append("Out-of-sample R^2 of a model that predicts each TEACHER column "
             "from the 184 PRE-TEACHER columns alone.  R^2 near 1 means the "
             "column is a re-expression of what the matrix already had "
             "(`TEACHER_REDUNDANCY.tsv`).")
    L.append("")
    rr = read(os.path.join(PROV, "TEACHER_REDUNDANCY.tsv"))
    L.append(md(["teacher column", "R^2 from the pre-teacher block",
                 "reading"],
                [[r["feature"], f(r["r2_from_pre_teacher_block"], 4),
                  ("already in the matrix"
                   if float(r["r2_from_pre_teacher_block"]) >= 0.90
                   else "GENUINELY NEW")] for r in rr]))
    L.append("")
    p = os.path.join(PROV, "SEQ_CUE_ERA_LADDER.tsv")
    if os.path.exists(p):
        L.append("## 1d. THE RAW-EVENT-STREAM CUES ON THE SAME LADDER")
        L.append("")
        L.append("`reload_with_side` was the ONE cue in this programme derived "
                 "from the raw event sequence that survived a census "
                 "(1.19x on n=1,122, E6R2).  On 1.4M candidates across eight "
                 "eras it does not replicate.")
        L.append("")
        sr = read(p)
        cues = []
        for r in sr:
            if r["cue"] not in cues:
                cues.append(r["cue"])
        ee = sorted(set(r["era"] for r in sr))
        body = []
        for c in cues:
            by = {r["era"]: r for r in sr if r["cue"] == c}
            lifts = [by[e]["lift"] for e in ee if e in by]
            pos = sum(1 for x in lifts if x not in (".", "") and float(x) > 1.0)
            body.append([c] + [f(by[e]["lift"], 2) if e in by else "."
                               for e in ee] + ["%d/%d" % (pos, len(ee))])
        L.append(md(["cue"] + ee + ["eras above 1x"], body))
        L.append("")
    return "\n".join(L)


def sec_stable():
    """The plane, read honestly: stability across eras and a walk-forward
    choice of the operating point itself."""
    import collections
    import numpy as np
    plane = json.load(open(os.path.join(CACHE, "plane.json")))
    eras = sorted(set(p["era"] for p in plane))
    by = collections.defaultdict(dict)
    for p in plane:
        by[(p["family"], p["point"])][p["era"]] = p
    full = [k for k, v in by.items() if all(e in v for e in eras)]
    L = ["## 6b. THE PLANE READ HONESTLY", "",
         "§6 maximises over the plane INSIDE each era, which is selection on "
         "the evaluation data.  Two readings that are not:", ""]

    L.append("### 6b.1 operating points that survive every era at the floor")
    L.append("")
    L.append("Present in all %d reported eras AND at or above 3 portfolio "
             "takes/week in EVERY one of them, ranked by mean $/week." % len(eras))
    L.append("")
    rows = []
    for k in full:
        v = by[k]
        tw = [v[e]["takes_per_week"] for e in eras]
        if min(tw) < 3.0:
            continue
        uw = [v[e]["usd_per_week"] for e in eras]
        pr = [v[e]["precision"] for e in eras if v[e]["n_seated"] > 0]
        rows.append((float(np.mean(uw)), k, tw, uw, pr))
    rows.sort(reverse=True)
    L.append(md(["operating point", "mean $/week", "worst era $/week",
                 "eras positive", "mean takes/wk", "mean precision"]
                + ["%s $/wk" % e for e in eras],
                [["`%s|%s`" % k, f(m, 0), f(min(uw), 0),
                  "%d/%d" % (sum(1 for x in uw if x > 0), len(eras)),
                  f(float(np.mean(tw)), 1), f(float(np.mean(pr)), 3)]
                 + [f(x, 0) for x in uw] for m, k, tw, uw, pr in rows[:12]]))
    L.append("")

    L.append("### 6b.2 the operating point chosen WALK-FORWARD")
    L.append("")
    L.append("The point with the best mean $/week on the eras STRICTLY BEFORE "
             "era k (subject to >= 3 takes/week there), applied unchanged to "
             "era k.  This is the only reading in this document in which "
             "nothing about the traded era — not the model, not the threshold, "
             "not the rule — was chosen with knowledge of it.")
    L.append("")
    body = []
    for i, e in enumerate(eras):
        if i == 0:
            continue
        prev = eras[:i]
        cand = []
        for k in full:
            v = by[k]
            if min(v[p]["takes_per_week"] for p in prev) < 3.0:
                continue
            cand.append((float(np.mean([v[p]["usd_per_week"] for p in prev])),
                         k))
        if not cand:
            continue
        cand.sort(reverse=True)
        r = by[cand[0][1]][e]
        body.append(["`%s|%s`" % cand[0][1], e, f(r["takes_per_week"], 1),
                     f(r["precision"], 3), f(r["usd_per_trade"], 0),
                     f(r["usd_per_week"], 0), f(r["usd_week_p10"], 0),
                     f(r["frac_losing_weeks"], 2),
                     f(r["usd_per_session_all"], 0)])
    L.append(md(["point chosen on prior eras", "traded era", "takes/wk",
                 "precision", "$/trade", "$/week", "week p10", "losing wks",
                 "$/session"], body))
    L.append("")
    return "\n".join(L)


def keep_headline():
    """Preserve a hand-written HEADLINE block across regenerations."""
    if not os.path.exists(OUT):
        return "<!-- HEADLINE -->"
    txt = open(OUT).read()
    i = txt.find("## HEADLINE")
    if i < 0:
        return "<!-- HEADLINE -->"
    j = txt.find("\n---\n", i)
    return txt[i:j] if j > 0 else txt[i:]


def main():
    head = HEADER.replace("<!-- HEADLINE -->", keep_headline())
    parts = [head, sec_teacher(), "\n---\n", sec_ladders(), "\n---\n",
             sec_threshold(), "\n---\n",
             sec_calibration(), "\n---\n", sec_daygate(), "\n---\n",
             sec_agreement(), "\n---\n", sec_verdict(), "\n---\n",
             sec_stable(), FOOTER]
    with open(OUT + ".tmp", "w", newline="\n") as fh:
        fh.write("\n".join(parts))
    os.replace(OUT + ".tmp", OUT)
    sys.stderr.write("wrote %s\n" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
