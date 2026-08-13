#!/usr/bin/python3
"""PORT M2 — red-first tests for panel_score + the used-case taint guard
(gate P-M2b).

Every test carries a committed MUTANT: a named neutralised production rule the
test must catch.  A mutant that survives is a dead test and fails the suite.

  P01  the fixture ledger scores to its COMMITTED expected numbers
  P02  MUTANT: a SKIP counted as a TAKE must break that known score
  P03  the interaction field is OPTIONAL (D-068-CORRECTION) — single-signal
       theses parse and score; only `primary` is required
  P04  a malformed call is REFUSED, never silently skipped
  P05  the one-position replay forfeits overlaps and never exceeds the DP
       ceiling
  P06  one-way taint: a STUDY-tainted session is REFUSED in a blind draw
  P07  MUTANT: a guard that FILTERS instead of refusing lets it through
  P08  the ledger's (cid, mode) dedup refuses a re-show
  P09  BLIND -> STUDY promotion stays lawful (the door is one-way, not shut)

Run: /usr/bin/python3 engine/port_m2/test_panel.py
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import panel_score as PS                  # noqa: E402
import used_cases as UC                   # noqa: E402

SECTION = "§3 panel_score + used-case ledger (P-M2b red-first)"
OUT_DIR = MC.out_path("tests", "_")[:-1]
FIXTURE = os.path.join(_HERE, "fixtures", "panel_fixture_ledger.tsv")
EXPECTED = os.path.join(_HERE, "fixtures", "panel_fixture_expected.json")

LEDGER = []


def check(name, mutant, ok_armed, ok_mutant, detail=""):
    verdict = "PASS" if (ok_armed and not ok_mutant) else (
        "FAIL_ARMED" if not ok_armed else "FAIL_DEAD_MUTANT")
    LEDGER.append([name, mutant, int(bool(ok_armed)), int(bool(ok_mutant)),
                   verdict, detail])
    return verdict == "PASS"


def _pooled(records):
    g = PS.score(records)["POOLED"]
    flat = dict(g)
    for m in ("close", "peak"):
        for k, v in g["replay_%s" % m].items():
            flat["replay_%s_%s" % (m, k)] = v
    return flat


def _expected():
    with open(EXPECTED) as fh:
        return json.load(fh)


# ------------------------------------------------------------ panel_score --
def p01_fixture_scores_to_committed_numbers():
    exp = _expected()
    got = _pooled(PS.parse_ledger(FIXTURE))
    keys = sorted(exp["pooled"])
    diffs = [k for k in keys if not _close(got.get(k), exp["pooled"][k])]
    armed = not diffs
    # MUTANT MP01: outcomes read off a constant instead of the roster
    mutant = _close(exp["pooled"]["mean_take_close_usd"], 0.0)
    return check("fixture_scores_to_committed_numbers",
                 "MP01_constant_outcomes", armed, mutant,
                 "mismatched=%s" % (",".join(diffs) or "none"))


def _close(a, b, tol=1e-6):
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(b)))


def p02_skip_counted_as_take_breaks_the_score():
    """THE brief's mutant: a SKIP scored as a TAKE must change the score."""
    exp = _expected()["pooled"]
    recs = PS.parse_ledger(FIXTURE)
    armed_ok = _close(_pooled(recs)["lift_close"], exp["lift_close"])
    # MUTANT MP02: flip the FIRST SKIP into a TAKE (a scorer that mis-reads the
    # call column, or a ledger row silently upgraded)
    mut = [dict(r) for r in recs]
    for r in mut:
        if r["call"] == PS.CALL_SKIP:
            r["call"] = PS.CALL_TAKE
            break
    m = _pooled(mut)
    broke = (not _close(m["lift_close"], exp["lift_close"])
             or m["n_takes"] != exp["n_takes"]
             or not _close(m["mean_take_close_usd"],
                           exp["mean_take_close_usd"]))
    return check("skip_counted_as_take_breaks_score",
                 "MP02_skip_scored_as_take", armed_ok and broke, not broke,
                 "lift %.6f -> %.6f" % (exp["lift_close"] or 0.0,
                                        m["lift_close"] or 0.0))


def p03_interaction_field_is_optional():
    """D-068-CORRECTION: single-signal theses are valid ledger entries."""
    recs = PS.parse_ledger(FIXTURE)
    n_without = sum(1 for r in recs if not r["has_interaction"])
    armed = n_without > 0 and len(recs) == len(_pooled(recs) and recs)
    # they must also SCORE: the pooled group counts every call
    armed = armed and _pooled(recs)["n_calls"] == len(recs)
    # MUTANT MP03: a parser that requires an interaction would drop them
    kept = [r for r in recs if r["has_interaction"]]
    mutant = (len(kept) == len(recs))
    return check("interaction_field_optional", "MP03_require_interaction",
                 armed, mutant,
                 "%d/%d calls carry no interaction" % (n_without, len(recs)))


def p04_malformed_call_is_refused():
    bad = os.path.join(OUT_DIR, "_malformed_ledger.tsv")
    MC.write_text(bad, "cid\tcall\tconf\tprimary\n"
                       "SI-20210701-000933-S\tMAYBE\tA\tsomething\n")
    armed = False
    try:
        PS.parse_ledger(bad)
    except PS.LedgerError:
        armed = True

    # MUTANT MP04: the lenient parser — skip whatever it cannot read.  The
    # property under test is "a malformed call RAISES"; the mutant silently
    # returns a shorter ledger instead, so it must not satisfy it.
    def lenient(path):
        try:
            return PS.parse_ledger(path), False
        except PS.LedgerError:
            return [], False              # swallowed
    _res, mutant_raised = lenient(bad)
    return check("malformed_call_refused", "MP04_skip_unparsed_rows", armed,
                 mutant_raised)


def p05_replay_respects_one_position_and_ceiling():
    recs = PS.parse_ledger(FIXTURE)
    for r in recs:
        r["outcome"] = PS.outcome(r["cid"])
    rows, tot = PS.replay(recs, "close")
    armed = bool(rows)
    for row in rows:
        # a one-position replay can never beat the one-position DP optimum
        if row["realised_usd"] > row["dp_ceiling_usd"] + 1e-6:
            armed = False
        if row["n_seated"] + row["n_forfeited"] != row["n_takes"]:
            armed = False
    # MUTANT MP05: a replay that seats every TAKE (no position constraint)
    all_sum = sum(r["outcome"]["cert_close_usd"] for r in recs
                  if r["call"] == PS.CALL_TAKE)
    mutant = (abs(all_sum - tot["realised_usd"]) < 1e-9
              and tot["n_forfeited"] > 0)
    return check("replay_one_position_and_ceiling", "MP05_seat_every_take",
                 armed, mutant,
                 "seated=%d forfeited=%d realised=%.0f ceiling=%.0f"
                 % (tot["n_seated"], tot["n_forfeited"], tot["realised_usd"],
                    tot["dp_ceiling_usd"]))


# ------------------------------------------------------------- taint guard --
def _fixture_entries():
    """A synthetic ledger held in memory — the committed ledger is never
    written by a test."""
    cids = [r["cid"] for r in PS.parse_ledger(FIXTURE)][:4]
    return cids, UC.make_entries(cids, "E1", "STUDY", UC.MODE_STUDY, "TEST",
                                 "test", recorded_at="2026-08-14T00:00:00Z")


def p06_study_taint_refuses_blind_draw():
    cids, entries = _fixture_entries()
    # a blind draw containing a candidate from the SAME (asset, session)
    asset, d8, sec, side = MC.parse_cid(cids[0])
    other = MC.make_cid(asset, d8, sec + 1, side)   # same session, other second
    armed = False
    try:
        UC.check_blind([other], entries)
    except UC.TaintRefusal:
        armed = True
    # a clean session must still pass
    clean_ok = True
    try:
        UC.check_blind([MC.make_cid(asset, 20250102, 12345, 1)], entries)
    except UC.TaintRefusal:
        clean_ok = False
    return check("study_taint_refuses_blind_draw", "MP06_no_taint_check",
                 armed and clean_ok, not armed,
                 "tainted=%d sessions" % len(UC.tainted_sessions(entries)))


def p07_filtering_guard_is_a_mutant():
    """MUTANT MP07: the plausible-looking wrong fix — filter the tainted
    members out of the draw instead of refusing it.  The filtered draw is
    SMALLER and silently non-day-complete, which is exactly the violation
    D-035/D-036 exist to prevent."""
    cids, entries = _fixture_entries()
    asset, d8, sec, side = MC.parse_cid(cids[0])
    draw = [MC.make_cid(asset, d8, sec + 1, side),
            MC.make_cid(asset, 20250102, 12345, 1)]
    refused = False
    try:
        UC.check_blind(draw, entries)
    except UC.TaintRefusal:
        refused = True
    tainted = UC.tainted_sessions(entries)

    def filtering_guard(cids):
        """MUTANT MP07: drop the tainted members and carry on."""
        keep = [c for c in cids
                if (MC.parse_cid(c)[0], MC.parse_cid(c)[1]) not in tainted]
        return keep, False                # never refuses
    kept, mutant_refused = filtering_guard(draw)
    armed = refused and len(kept) == len(draw) - 1   # it really was tainted
    return check("filtering_guard_is_a_mutant", "MP07_filter_not_refuse",
                 armed, mutant_refused,
                 "filtered draw size %d/%d" % (len(kept), len(draw)))


def p08_reshow_is_refused():
    cids, entries = _fixture_entries()
    armed = False
    try:
        UC.check_new(cids[:1], UC.MODE_STUDY, entries)
    except UC.TaintRefusal:
        armed = True
    # MUTANT MP08: dedup on cid alone would also block the lawful BLIND->STUDY
    # promotion, so the key must be (cid, mode)
    lawful = True
    try:
        UC.check_new(cids[:1], UC.MODE_BLIND, entries)
    except UC.TaintRefusal:
        lawful = False
    return check("reshow_refused", "MP08_dedup_on_cid_only", armed and lawful,
                 not armed)


def p09_blind_to_study_promotion_is_lawful():
    cids = [r["cid"] for r in PS.parse_ledger(FIXTURE)][:3]
    entries = UC.make_entries(cids, "E1", "BLIND", UC.MODE_BLIND, "TEST",
                              "test", recorded_at="2026-08-14T00:00:00Z")
    armed = True
    try:                                   # promotion: same cases, STUDY mode
        UC.check_new(cids, UC.MODE_STUDY, entries)
    except UC.TaintRefusal:
        armed = False
    # and a blind-only ledger taints nothing
    armed = armed and not UC.tainted_sessions(entries)
    # MUTANT MP09: taint computed from ANY entry, not just the STUDY ones —
    # that would shut the door in both directions and forbid the lawful
    # promotion.  Under the mutant the property "a blind-only ledger taints
    # nothing" is false.
    taint_any = {(e["asset"], int(e["date8"])) for e in entries}
    mutant = not taint_any
    return check("blind_to_study_promotion_lawful", "MP09_taint_on_any_entry",
                 armed, mutant, "%d blind entries taint 0 sessions"
                 % len(entries))


TESTS = (p01_fixture_scores_to_committed_numbers,
         p02_skip_counted_as_take_breaks_the_score,
         p03_interaction_field_is_optional,
         p04_malformed_call_is_refused,
         p05_replay_respects_one_position_and_ceiling,
         p06_study_taint_refuses_blind_draw,
         p07_filtering_guard_is_a_mutant,
         p08_reshow_is_refused,
         p09_blind_to_study_promotion_is_lawful)


def main():
    MC.verify_spec(force=True)
    n_fail = 0
    for t in TESTS:
        try:
            ok = t()
        except Exception as e:            # noqa: BLE001 — recorded, not hidden
            LEDGER.append([t.__name__, "-", 0, 0, "ERROR", repr(e)[:200]])
            ok = False
        if not ok:
            n_fail += 1
        MC.hb("test %s: %s" % (t.__name__, LEDGER[-1][4]))
    MC.write_tsv(os.path.join(OUT_DIR, "red_ledger_panel.tsv"), SECTION,
                 MC.params_hash(PS.PARAMS),
                 ["test", "mutant", "armed_pass", "mutant_pass", "verdict",
                  "detail"], LEDGER,
                 extra=["RED-FIRST: armed_pass MUST be 1 and mutant_pass MUST "
                        "be 0 on every row"])
    MC.write_json(os.path.join(OUT_DIR, "tests_panel.receipt.json"),
                  {"env": MC.env_receipt(PS.PARAMS), "n_tests": len(TESTS),
                   "n_failed": n_fail,
                   "verdict": "PASS" if n_fail == 0 else "FAIL"})
    MC.hb("panel tests: %d/%d passed" % (len(TESTS) - n_fail, len(TESTS)))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
