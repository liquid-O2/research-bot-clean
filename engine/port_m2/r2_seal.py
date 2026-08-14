#!/usr/bin/python3
"""PORT M2 — ROUND-2 BLIND DAY SEAL: the reader's ledger + ranking, per day.

Round 1's sealed ledgers were dumped by `e6_calls.py --dump` WITHOUT
`--overrides-only`, so they recorded a rubric schedule the reader had already
disowned and the adjudication scored 22 seats the reader never claimed
(E6_EXTRACTION §0.3 defect X-2).  R2-9 retires the rubric from takes entirely,
so this seal has exactly ONE channel: the hand-named takes passed in on the
command line.  Nothing else can produce a TAKE.

WHAT IT WRITES, per blind day
  provenance/port_m2/E6R2_BLIND_<date8>.tsv   the call ledger (every episode)
  artifacts/.../E6R2_RANKING_<date8>.tsv      the episode_round ranking file

THE RANKING, STATED.  `episode_round.validate_ranking` requires the WHOLE day
ranked or explicitly ABSTAIN.  The reader ranks on the one thing that survived
three HIGH-vol study days as arithmetic rather than as a cue — whether the
phase can still pay a $1,000 target before it closes:

    ep_hat = min(unspent_phase_usd, 2500) * runway_factor
    runway_factor = 0 if runway < 4800 ; 0.35 if < 9000 ; 0.7 if < 18000 ; 1.0
    hand-named TAKEs are ranked above everything else, in probability order.

That is a PRIOR, not a claim of skill: it is stated here so the ranking's
information content is auditable rather than mysterious.  Episodes whose
capacity arithmetic is dead (unspent <= 0 or runway < 4800) are ranked, not
abstained, so the day stays a full permutation and the scorer sees the whole
ordering.

BLIND SAFETY: no outcome import at any depth.
"""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import e6_round as E6                     # noqa: E402
import library_retest as LR               # noqa: E402

LEDGER_DIR = "/workspace/provenance/port_m2"
RANK_DIR = "/workspace/artifacts/cache/port/m2/episode_round/E6"


def _f(v, d=float("nan")):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def ep_hat(d):
    uns = _f(d.get("unspent_phase_usd"), 0.0)
    run = _f(d.get("runway_phase"), 0.0)
    rf = 0.0 if run < 4800 else 0.35 if run < 9000 else 0.7 if run < 18000 else 1.0
    return max(0.0, min(uns, 2500.0)) * rf


def build(day, takes, probs, whys, round_name):
    rows = LR.episode_rows(day)
    by = {eid: (asset, d) for eid, asset, d in rows}
    order = sorted(rows, key=lambda t: (-ep_hat(t[2]), t[0]))
    ranked = [eid for eid, _a, _d in order]
    for eid in takes:
        if eid not in by:
            raise SystemExit("take %s is not an episode of %d" % (eid, day))
    ranked = list(takes) + [e for e in ranked if e not in takes]

    rank_p = os.path.join(RANK_DIR, "E6R2_RANKING_%d.tsv" % day)
    with open(rank_p, "w", newline="\n") as fh:
        fh.write("# ROUND-2 BLIND RANKING %d (%s) — hand-named TAKEs first, "
                 "then the stated capacity-arithmetic prior (r2_seal.ep_hat)\n"
                 % (day, round_name))
        fh.write("rank\tepisode_id\texpected_payment_usd\tconfidence\t"
                 "evidence\tcall\tp\n")
        for i, eid in enumerate(ranked, 1):
            _a, d = by[eid]
            call = "TAKE" if eid in takes else "SKIP"
            p = probs.get(eid, 0.0)
            ev = whys.get(eid, "capacity-arithmetic prior only; not shortlisted")
            fh.write("%d\t%s\t%.0f\t%.3f\t%s\t%s\t%.3f\n"
                     % (i, eid, ep_hat(d), p, ev.replace("\t", " "), call, p))

    led_p = os.path.join(LEDGER_DIR, "E6R2_BLIND_%d.tsv" % day)
    with open(led_p, "w", newline="\n") as fh:
        fh.write("# ROUND-2 SEALED BLIND LEDGER %d (%s) — hand channel ONLY "
                 "(R2-9: the rubric never seats)\n" % (day, round_name))
        fh.write("# every TAKE carries a decision_journal entry written BEFORE "
                 "the call and a RIBBON_ACCESS row for the window it read\n")
        fh.write("ep\tasset\tsec\tside\tcall\tp\tsrc\tcompl\twhy\n")
        for eid, asset, d in rows:
            call = "TAKE" if eid in takes else "SKIP"
            p = probs.get(eid, 0.0)
            why = whys.get(eid, "-")
            fh.write("%s\t%s\t%s\t%s\t%s\t%.3f\t%s\t%s\t%s\n"
                     % (eid, asset, d.get("sec", "?"), d.get("side", "?"),
                        call, p, "HAND" if eid in probs else "-",
                        d.get("compl", "-"), why.replace("\t", " ")))
    return {"ranking": rank_p, "ledger": led_p, "n_episodes": len(rows),
            "n_takes": len(takes)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", type=int, required=True)
    ap.add_argument("--round", dest="round_name", required=True)
    ap.add_argument("--take", action="append", default=[],
                    metavar="EPISODE:P:WHY")
    ap.add_argument("--priced", action="append", default=[],
                    metavar="EPISODE:P:WHY", help="hand-priced SKIPs")
    a = ap.parse_args(argv)
    takes, probs, whys = [], {}, {}
    for spec in a.take + a.priced:
        eid, p, why = spec.split(":", 2)
        probs[eid] = float(p)
        whys[eid] = why
        if spec in a.take:
            takes.append(eid)
    r = build(a.day, takes, probs, whys, a.round_name)
    print("sealed %d: %d episodes, %d TAKEs -> %s | %s"
          % (a.day, r["n_episodes"], r["n_takes"], r["ledger"], r["ranking"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
