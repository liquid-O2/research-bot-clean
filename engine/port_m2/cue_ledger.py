#!/usr/bin/python3
"""PORT M2 — THE CUMULATIVE TEACHER CUE LEDGER (R2-11) + CURRICULUM DERIVER (R2-10).

WHY THIS EXISTS.  Round 1 produced a one-off extraction report.  A report is
read once and then re-derived by hand, wrongly, by whoever comes next.  R2-11
replaces it with ONE cumulative, versioned artefact —
`provenance/port_m2/TEACHER_CUE_LEDGER.tsv` — carrying every named cue with
per-round columns (n, lift, p, verdict), so that:

  * every later round INHERITS every earlier round's measurement mechanically;
  * the next round's CURRICULUM FACTS (R2-10) are DERIVED from the ledger's
    current state by `--curriculum`, never retyped from prose.

VERDICT VOCABULARY (R2-11): PROVEN / SUPPORTED / FALSIFIED / INVERTED /
CONFOUNDED / NULL / HYPOTHESIS.  Grading rule is `design/TEACHER_FEATURES_V1.md`
§0, applied mechanically here:

  PROVEN     blind-block p < 0.01 AND per-day direction consistent on >= 5 of 6
  SUPPORTED  pooled(ALL) p < 0.05 AND per-day direction consistent on >= 4 of 6
  FALSIFIED  the reader named it as POSITIVE evidence and lift <= 1.0
  INVERTED   FALSIFIED and the complement predicate is significantly positive
  CONFOUNDED  measures asset/regime identity rather than the named mechanism
  NULL       lift within [0.9, 1.15] and not significant
  HYPOTHESIS named by the reader, not computable / underpowered in that round

BLIND SAFETY: this module imports no scoring module and touches no outcome
file.  It reads a committed census TSV (already public, already adjudicated)
and writes/reads the ledger.  Nothing here can reach a sealed day.

CLI
  cue_ledger.py --seed-round1        # seed from provenance/port_m2/E6_CUE_CENSUS.tsv
  cue_ledger.py --curriculum         # R2-10 curriculum facts, derived from ledger state
  cue_ledger.py --show [--verdict V] # the ledger, filtered
"""
import argparse
import os
import sys

LEDGER = "/workspace/provenance/port_m2/TEACHER_CUE_LEDGER.tsv"
CENSUS_R1 = "/workspace/provenance/port_m2/E6_CUE_CENSUS.tsv"

VERSION = "TEACHER_CUE_LEDGER v1 (R2-11)"

# The reader's own predicate for each name (E6_EXTRACTION.md §2.1, verbatim
# semantics).  A cue with no predicate here was not computable in round 1.
PRED = {
    "SEAT_LIVE": "unspent_phase_usd>=700 AND runway_phase>=18000",
    "SEAT_DEAD_TIME": "runway_phase<4800",
    "PHASE_SPENT": "cov_phase>=80",
    "COV_SWEET_20_60": "20<=cov_phase<60",
    "LEVEL_VIRGIN": "min_tc_near==0",
    "capacity_room": "unspent_phase_usd>=400",
    "capacity_big": "unspent_phase_usd>=1000",
    "capacity_spent": "unspent_phase_usd<400",
    "runway_ok": "runway_phase>=2400",
    "cov_low": "cov_phase<=40",
    "phase_open": "(sec-phase_open_sec)/(phase_close_sec-phase_open_sec)<=0.15",
    "phase_open_reset": "phase_open AND unspent_phase_usd>=400",
    "level_at_price": "abs(near_d)<=10",
    "level_near": "abs(near_d)<=60",
    "level_tested_held": "level_near AND min_tc_near>=1",
    "fresh_extreme": "extreme_age<=900",
    "stale_extreme": "extreme_age>6000",
    "flow_agree_5m": "f5m_sflow*side>0",
    "flow_against_5m": "f5m_sflow*side<0",
    "one_sided_flow": "f5m_sflow*side>0 AND fph_sflow*side>0",
    "flow_strong": "one_sided_flow AND abs(f5m_sflow)>=50",
    "flow_flip": "f60_sflow*side>0 AND f5m_sflow*side<=0 (2-window proxy)",
    "fuel_trapped": "trapped share on squeeze side >=0.65",
    "event_burst": "n_ev_60>=400 AND rv60>0.4*rv1800",
    "tmz_burst": "trades_min_z>=3",
    "wide_spread": "spread_dec>=50",
    "expanding": "ladder_pos>=q5* OR rv60>0.9*rv1800",
    "poc_magnet": "d_POC*side>0 AND abs(d_POC)>=200",
    "refill_book": "refill_frac>=0.60",
    "NAMED_TRIAD": "phase_open_reset AND level_near AND one_sided_flow",
    "NAMED_TRIAD_soft": "capacity_room AND level_near AND flow_agree_5m",
    "REFAIL_CHAIN": "pivot-chain refail on the adverse side (NOT COMPUTABLE r1)",
    "FLOW_FLIP_SEQ": "ordered S6 digest-cluster sign sequence (NOT COMPUTABLE r1)",
}

# Cues the reader named as POSITIVE evidence in round 1 (the rubric terms and
# the ERA_NOTES hypotheses).  Only these can be graded FALSIFIED — a cue the
# reader never claimed cannot be an error of the reader's.
READER_POSITIVE = {
    "level_tested_held", "fuel_trapped", "expanding", "one_sided_flow",
    "fresh_extreme", "level_at_price", "level_near", "flow_agree_5m",
    "flow_strong", "phase_open_reset", "capacity_room", "capacity_big",
    "NAMED_TRIAD", "NAMED_TRIAD_soft", "event_burst", "poc_magnet",
    "refill_book", "tmz_burst", "runway_ok", "flow_flip",
}
READER_NEGATIVE = {"wide_spread", "stale_extreme", "capacity_spent"}

# Named in the extraction as an asset/regime identity rather than a mechanism.
CONFOUNDED = {"wide_spread"}
# Named in the extraction as sign-inverted (its complement is the live cue).
INVERTED = {"level_tested_held": "LEVEL_VIRGIN"}

HDR = ("cue", "predicate", "first_named", "reader_polarity",
       "r1_blind_n", "r1_blind_lift", "r1_blind_p",
       "r1_all_n", "r1_all_lift", "r1_perday_dir", "r1_verdict", "r1_note")


def _read_census(path):
    rows = {}
    with open(path) as fh:
        hdr = None
        for ln in fh:
            if ln.startswith("#"):
                continue
            f = ln.rstrip("\n").split("\t")
            if hdr is None:
                hdr = f
                continue
            r = dict(zip(hdr, f))
            rows[(r["scope"], r["cue"])] = r
    return rows


def _perday_dir(r):
    """Count of the 6 round days on which the cue points the SAME way as its
    pooled blind direction.  Direction is lift vs 1."""
    lifts = []
    for k in ("lift_20240118", "lift_20240320", "lift_20240416",
              "lift_20240419", "lift_20240422", "lift_20240423"):
        try:
            lifts.append(float(r[k]))
        except (KeyError, ValueError):
            pass
    if not lifts:
        return 0, 0
    up = float(r["lift"]) >= 1.0
    n = sum(1 for x in lifts if (x >= 1.0) == up)
    return n, len(lifts)


def _verdict(cue, blind, alls):
    if cue in CONFOUNDED:
        return "CONFOUNDED", "direction real, mechanism is asset identity"
    lift = float(blind["lift"])
    p = float(blind["p_binom"])
    nd, tot = _perday_dir(blind)
    pa = float(alls["p_binom"]) if alls else 1.0
    if p < 0.01 and nd >= 5:
        return "PROVEN", "blind p<0.01, direction %d/%d days" % (nd, tot)
    if p < 0.01 and nd < 5 and lift > 1.0:
        return "UNSTABLE", ("blind p<0.01 but direction only %d/%d days — "
                            "pooled edge, not a per-day fact" % (nd, tot))
    if cue in INVERTED:
        return "INVERTED", "complement %s is the live cue" % INVERTED[cue]
    if cue in READER_POSITIVE and lift <= 1.0:
        return "FALSIFIED", "named as positive evidence, measured at/below base"
    if pa < 0.05 and nd >= 4:
        return "SUPPORTED", "pooled p<0.05, direction %d/%d days" % (nd, tot)
    if 0.90 <= lift <= 1.15:
        return "NULL", "at base rate, not significant"
    if int(blind["n"]) < 50:
        return "HYPOTHESIS", "underpowered (blind n=%s)" % blind["n"]
    return "NULL", "not significant (p=%.2g)" % p


def seed_round1(out=LEDGER):
    cen = _read_census(CENSUS_R1)
    cues = sorted({c for (s, c) in cen if s == "BLIND"})
    lines = [
        "# %s" % VERSION,
        "# ONE cumulative ledger: every named cue, every round, forever (R2-11).",
        "# Each round appends a column block rN_*; NOTHING is ever deleted, a "
        "cue that dies stays with its verdict.",
        "# round 1 = E6 TEACHER ROUND (2024-H1, 6 days: 3 study + 3 sealed "
        "blind; 4,227 episodes; blind base 0.0715, all-days base 0.0660).",
        "# source: provenance/port_m2/E6_CUE_CENSUS.tsv (+ E6_EXTRACTION.md, "
        "design/TEACHER_FEATURES_V1.md); target = winner_close (D-021).",
        "# verdicts: PROVEN/SUPPORTED/FALSIFIED/INVERTED/CONFOUNDED/NULL/"
        "HYPOTHESIS, graded by TEACHER_FEATURES_V1 §0 applied mechanically here.",
        "\t".join(HDR),
    ]
    for cue in cues:
        b = cen[("BLIND", cue)]
        a = cen.get(("ALL", cue))
        v, note = _verdict(cue, b, a)
        nd, tot = _perday_dir(b)
        pol = ("POSITIVE" if cue in READER_POSITIVE else
               "NEGATIVE" if cue in READER_NEGATIVE else "DERIVED")
        lines.append("\t".join([
            cue, PRED.get(cue, "-"), "R1_E6", pol,
            b["n"], "%.3f" % float(b["lift"]), "%.2g" % float(b["p_binom"]),
            a["n"] if a else "-", "%.3f" % float(a["lift"]) if a else "-",
            "%d/%d" % (nd, tot), v, note]))
    # The two mechanisms the reader named and the round could not measure.
    for cue, why in (("REFAIL_CHAIN",
                      "E6-H1; no pivot chain in the reading surface — build order in TEACHER_FEATURES_V1 TF-H2"),
                     ("FLOW_FLIP_SEQ",
                      "E6-H2; only 2-window proxy existed (0.96x); true ordered form not built (TF-H3)")):
        lines.append("\t".join([cue, PRED[cue], "R1_E6", "POSITIVE",
                                "0", "-", "-", "0", "-", "0/6",
                                "HYPOTHESIS", why]))
    with open(out, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    return len(cues) + 2


def read_ledger(path=LEDGER):
    rows = []
    with open(path) as fh:
        hdr = None
        for ln in fh:
            if ln.startswith("#"):
                continue
            f = ln.rstrip("\n").split("\t")
            if hdr is None:
                hdr = f
                continue
            rows.append(dict(zip(hdr, f)))
    return rows


def curriculum(path=LEDGER):
    """R2-10: the next round's curriculum facts, DERIVED from ledger state."""
    rows = read_ledger(path)
    by = {}
    for r in rows:
        by.setdefault(r["r1_verdict"], []).append(r)
    out = []
    out.append("CURRICULUM FACTS, DERIVED FROM %s (R2-10/R2-11)" % os.path.basename(path))
    out.append("=" * 78)
    out.append("")
    out.append("A. TEACH AS MEASURED FACT (verdict PROVEN — carry the number, not the story):")
    for r in sorted(by.get("PROVEN", []), key=lambda r: -abs(float(r["r1_blind_lift"]) - 1)):
        out.append("   %-18s %-52s blind n=%-5s lift=%-6s p=%-9s days %s"
                   % (r["cue"], r["predicate"], r["r1_blind_n"],
                      r["r1_blind_lift"], r["r1_blind_p"], r["r1_perday_dir"]))
    out.append("")
    out.append("B. TEACH AS FALSIFIED — these are the reader's OWN round-1 evidence, measured at or")
    out.append("   below base rate.  Using them again re-imports a known error.  A cue here may NEVER")
    out.append("   be a reason FOR a take; naming it for a take is a defect:")
    for r in sorted(by.get("FALSIFIED", []) + by.get("INVERTED", []),
                    key=lambda r: float(r["r1_blind_lift"])):
        out.append("   %-18s lift=%-6s (n=%-5s) %-10s %s"
                   % (r["cue"], r["r1_blind_lift"], r["r1_blind_n"],
                      r["r1_verdict"], r["r1_note"]))
    out.append("")
    out.append("C. LOSER-SIGNATURE VETO (R2-4) — the wrong-side signature, from the same census:")
    ded = [r for r in rows if r["cue"] == "SEAT_DEAD_TIME"]
    spent = [r for r in rows if r["cue"] == "capacity_spent"]
    psp = [r for r in rows if r["cue"] == "PHASE_SPENT"]
    exp = [r for r in rows if r["cue"] == "expanding"]
    for r in ded + spent + psp + exp:
        out.append("   VETO %-16s lift=%-6s (blind n=%s) %s"
                   % (r["cue"], r["r1_blind_lift"], r["r1_blind_n"], r["r1_note"]))
    out.append("")
    out.append("D. SUPPORTED — usable, weaker evidence (must not carry a take alone):")
    for r in sorted(by.get("SUPPORTED", []), key=lambda r: -float(r["r1_blind_lift"])):
        out.append("   %-18s lift=%-6s (n=%-5s) %s"
                   % (r["cue"], r["r1_blind_lift"], r["r1_blind_n"], r["r1_note"]))
    out.append("")
    out.append("E2. UNSTABLE — pooled-significant, per-day direction unstable (a regime artefact risk;")
    out.append("    it may be named, but it may never be the WHOLE reason):")
    for r in sorted(by.get("UNSTABLE", []), key=lambda r: -float(r["r1_blind_lift"])):
        out.append("   %-18s lift=%-6s (n=%-5s) %s"
                   % (r["cue"], r["r1_blind_lift"], r["r1_blind_n"], r["r1_note"]))
    out.append("")
    out.append("E. NULL — no information in round 1; naming one of these is naming nothing:")
    out.append("   " + ", ".join(sorted(r["cue"] for r in by.get("NULL", []))))
    out.append("")
    out.append("F. CONFOUNDED — real direction, wrong mechanism:")
    for r in by.get("CONFOUNDED", []):
        out.append("   %-18s lift=%-6s %s" % (r["cue"], r["r1_blind_lift"], r["r1_note"]))
    out.append("")
    out.append("G. OPEN HYPOTHESES — named by the round-1 reader, never measured.  Round 2 can only")
    out.append("   test these by READING THE RAW SEQUENCE (they were invisible in the digest):")
    for r in by.get("HYPOTHESIS", []):
        out.append("   %-18s %s" % (r["cue"], r["r1_note"]))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-round1", dest="seed", action="store_true")
    ap.add_argument("--curriculum", action="store_true")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--verdict", default=None)
    ap.add_argument("--ledger", default=LEDGER)
    a = ap.parse_args(argv)
    if a.seed:
        n = seed_round1(a.ledger)
        print("seeded %s with %d cues from %s" % (a.ledger, n, CENSUS_R1))
    if a.curriculum:
        print(curriculum(a.ledger))
    if a.show:
        for r in read_ledger(a.ledger):
            if a.verdict and r["r1_verdict"] != a.verdict:
                continue
            print("%-18s %-10s blind n=%-5s lift=%-6s p=%-9s %s"
                  % (r["cue"], r["r1_verdict"], r["r1_blind_n"],
                     r["r1_blind_lift"], r["r1_blind_p"], r["r1_note"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
