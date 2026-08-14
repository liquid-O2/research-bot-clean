#!/usr/bin/python3
"""PORT M2 — RED-FIRST TESTS FOR THE ROUND-2 VIEW STACK (R2-1/2/5/6/7).

Every test asserts a LAW the round-2 revisions introduce, and every one carries
a MUTANT that neutralises ONE NAMED PRODUCTION LINE of the build.  A test whose
mutant survives is a dead test and fails (`FAIL_DEAD_MUTANT`) — the shape
`test_reader_fixlane.py` establishes.

COVERED
  t01  R2-1  a TAKE with 0 ribbon reads and 0 chart reads is PROTOCOL_INVALID
  t02  R2-1  a TAKE with a ribbon read is NOT flagged (the rule is not a
             blanket refusal)
  t03  R2-1  the access ledger carries n_chart_reads, and a pre-R2-1 ledger
             migrates onto the new schema without corrupting a row
  t04  R2-6  the action grain prints EVERY event, full-ns ts_event, gap_ns and
             sequence, and NO max-rows bound thins it
  t05  R2-7  the legend's column terms ARE the ribbon's printed header terms
  t06  R2-6  gap_ns of a BACKWARD ts_event step prints N/A, not a negative
  t07  R2-2  the trajectory recomputation at the NOW anchor reproduces the
             sheet's own value (definition identity, not a second opinion)
  t08  R2-5  chart rendering is deterministic (same bytes twice) and refuses a
             non-causal series

Run: /usr/bin/python3 engine/port_m2/test_r2views_fixlane.py
"""
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                          # noqa: E402
import episode_round as ER                      # noqa: E402
import ribbon as RIB                            # noqa: E402
import e6_round as E6                           # noqa: E402

SECTION = "§3 R2 view stack — red-first tests (R2-1/2/5/6/7)"
OUT_DIR = MC.out_path("tests", "_")[:-1]
LEGEND = "/workspace/design/RIBBON_LEGEND.md"

PARAMS = {
    "lane": "port-r2-views",
    "revisions": "R2-1 R2-2 R2-5 R2-6 R2-6-CORRECTION R2-7",
    "law": "armed_pass MUST be 1 and mutant_pass MUST be 0 on every row",
}

LEDGER = []


def check(name, mutant, ok_armed, ok_mutant, detail=""):
    verdict = "PASS" if (ok_armed and not ok_mutant) else (
        "FAIL_ARMED" if not ok_armed else "FAIL_DEAD_MUTANT")
    LEDGER.append([name, mutant, int(bool(ok_armed)), int(bool(ok_mutant)),
                   verdict, detail])
    return verdict == "PASS"


# ------------------------------------------------------------- fixtures ----
EPS = [
    {"episode_id": "SI-20240118-L-E01", "era": "E6", "asset": "SI",
     "date8": 20240118, "rep_cid": "SI-20240118-001402-L",
     "members": "SI-20240118-001402-L"},
    {"episode_id": "SI-20240118-L-E02", "era": "E6", "asset": "SI",
     "date8": 20240118, "rep_cid": "SI-20240118-001588-L",
     "members": "SI-20240118-001588-L"},
]


def _write_access(path, rows):
    """An EPISODE_ACCESS ledger with exactly the given (episode, counts)."""
    out = []
    for i, (eid, n_rib, n_ch) in enumerate(rows):
        e = [x for x in EPS if x["episode_id"] == eid][0]
        rec = {"seq": i, "episode_id": eid, "era": e["era"], "asset": e["asset"],
               "date8": e["date8"], "rep_cid": e["rep_cid"], "n_members": 1,
               "mode": MC.MODE_BLIND, "sheet_source": "render",
               "sheet_sha16": "0" * 16, "sheet_tokens": 100,
               "n_ribbon_cmds": n_rib, "n_chart_reads": n_ch,
               "s14_guard_paths_checked": 1, "round": "R2TEST",
               "caller": "fixture"}
        out.append([str(rec[c]) for c in ER.ACCESS_COLUMNS])
    MC.write_tsv(path, SECTION, MC.params_hash(PARAMS),
                 list(ER.ACCESS_COLUMNS), out)
    return path


def _write_ranking(path, rows):
    """rows = [(rank, episode_id, call)]."""
    lines = ["rank\tepisode_id\tcall\tp"]
    for rk, eid, call in rows:
        lines.append("%s\t%s\t%s\t0.20" % (rk, eid, call))
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def _empty_tsv(path, columns):
    MC.write_tsv(path, SECTION, MC.params_hash(PARAMS), list(columns), [])
    return path


def _protocol(tmp, access_rows, ranking_rows):
    """Run the R2-1 rule on a fixture day with EMPTY mechanical ledgers."""
    acc = _write_access(os.path.join(tmp, "EPISODE_ACCESS.tsv"), access_rows)
    rnk = _write_ranking(os.path.join(tmp, "RANK.tsv"), ranking_rows)
    rib = _empty_tsv(os.path.join(tmp, "RIBBON_ACCESS.tsv"),
                     RIB.ACCESS_COLUMNS)
    cha = _empty_tsv(os.path.join(tmp, "CHART_RECEIPT.tsv"),
                     ER.CHART_RECEIPT_COLUMNS)
    rank = ER.validate_ranking(EPS, ER.read_ranking(rnk))
    return ER.take_protocol(EPS, rank, round_name="R2TEST", ledger=acc,
                            ribbon_ledger=rib, chart_receipt=cha)


# ------------------------------------------------------------- the tests ----
def t01_take_without_ribbon_or_chart_is_protocol_invalid():
    """R2-1: the take that decided on the digest alone is NAMED, not scored
    as if it were lawful.  Round 1's whole defect in one row."""
    with tempfile.TemporaryDirectory() as tmp:
        got = _protocol(tmp, [("SI-20240118-L-E01", 0, 0),
                              ("SI-20240118-L-E02", 3, 0)],
                        [(1, "SI-20240118-L-E01", "TAKE"),
                         (2, "SI-20240118-L-E02", "TAKE")])
        bad = {r["episode_id"] for r in got["rows"]
               if r["protocol"] == ER.PROTOCOL_INVALID}
        armed = (bad == {"SI-20240118-L-E01"} and got["n_invalid"] == 1)

        # MUTANT: episode_round.take_protocol's zero-evidence test neutralised
        # (the `and` arm made unconditionally False, i.e. "never flag").
        real = ER._zero_evidence
        try:
            ER._zero_evidence = lambda *a, **k: False
            got_m = _protocol(tmp, [("SI-20240118-L-E01", 0, 0),
                                    ("SI-20240118-L-E02", 3, 0)],
                              [(1, "SI-20240118-L-E01", "TAKE"),
                               (2, "SI-20240118-L-E02", "TAKE")])
            mut = got_m["n_invalid"] == 1
        finally:
            ER._zero_evidence = real
    return check("t01_take_without_ribbon_or_chart_is_protocol_invalid",
                 "episode_round._zero_evidence -> False", armed, mut,
                 "flagged=%s n_invalid=%d" % (sorted(bad), got["n_invalid"]))


def t02_take_with_a_ribbon_read_is_not_flagged():
    """The rule refuses UNEVIDENCED takes, not takes."""
    with tempfile.TemporaryDirectory() as tmp:
        got = _protocol(tmp, [("SI-20240118-L-E01", 2, 0),
                              ("SI-20240118-L-E02", 0, 4)],
                        [(1, "SI-20240118-L-E01", "TAKE"),
                         (2, "SI-20240118-L-E02", "TAKE")])
        armed = got["n_invalid"] == 0 and len(got["rows"]) == 2

        # MUTANT: the chart-evidence term dropped, so a chart-only take flags.
        real = ER._zero_evidence
        try:
            ER._zero_evidence = lambda n_rib, n_ch: n_rib == 0
            got_m = _protocol(tmp, [("SI-20240118-L-E01", 2, 0),
                                    ("SI-20240118-L-E02", 0, 4)],
                              [(1, "SI-20240118-L-E01", "TAKE"),
                               (2, "SI-20240118-L-E02", "TAKE")])
            mut = got_m["n_invalid"] == 0
        finally:
            ER._zero_evidence = real
    return check("t02_take_with_a_ribbon_read_is_not_flagged",
                 "episode_round._zero_evidence drops the chart term",
                 armed, mut, "n_invalid=%d" % got["n_invalid"])


def t03_access_ledger_migrates_onto_n_chart_reads():
    """A pre-R2-1 ledger has no n_chart_reads column.  Reading it must not
    KeyError and must not shift a single field of a legacy row."""
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "EPISODE_ACCESS.tsv")
        legacy_cols = [c for c in ER.ACCESS_COLUMNS if c != "n_chart_reads"]
        row = ["0", "SI-20240118-L-E01", "E6", "SI", "20240118",
               "SI-20240118-001402-L", "1", "BLIND", "render", "a" * 16,
               "100", "7", "1", "R2TEST", "fixture"]
        MC.write_tsv(p, SECTION, MC.params_hash(PARAMS), legacy_cols, [row])
        rows = ER._read_access(p)
        armed = (len(rows) == 1
                 and rows[0]["n_ribbon_cmds"] == "7"        # not shifted
                 and rows[0]["caller"] == "fixture"
                 and rows[0]["n_chart_reads"] == ER.ACCESS_DEFAULT[
                     "n_chart_reads"])
        # append must round-trip the migrated row onto the new schema
        ER._append_access({c: "x" for c in ER.ACCESS_COLUMNS}, p)
        again = ER._read_access(p)
        armed = armed and len(again) == 2 and again[0]["n_ribbon_cmds"] == "7"

        # MUTANT: the named default removed, so a legacy row loses the column.
        real = dict(ER.ACCESS_DEFAULT)
        try:
            ER.ACCESS_DEFAULT.clear()
            try:
                r2 = ER._read_access(p)
                mut = "n_chart_reads" in r2[0] and r2[0]["n_chart_reads"] != ""
            except Exception:                     # noqa: BLE001
                mut = False
        finally:
            ER.ACCESS_DEFAULT.clear()
            ER.ACCESS_DEFAULT.update(real)
    return check("t03_access_ledger_migrates_onto_n_chart_reads",
                 "episode_round.ACCESS_DEFAULT emptied", armed, mut,
                 "cols=%d" % len(ER.ACCESS_COLUMNS))


def t04_action_grain_prints_every_event_and_never_thins():
    """R2-6-CORRECTION + D-092: max_rows must not bind on the action grain,
    and every printed row must carry a full-ns ts_event and a sequence."""
    cid = "SI-20240118-003151-L"
    rec = RIB.fetch(cid, "T-120", "T", grain=RIB.GRAIN_ACTION, max_rows=3)
    body = [l for l in rec["lines"] if l.startswith("  1")]
    armed = (rec["n_events"] > 3                       # the bound WOULD bind
             and rec["n_rows_printed"] == rec["n_events"]
             and rec["n_raw_withheld"] == 0
             and len(body) == rec["n_events"])
    # every ts_event is 19 digits (nanoseconds), and gap/seq are present
    for line in body[:50]:
        f = line.split()
        armed = armed and len(f[0]) == 19 and f[0].isdigit()
        armed = armed and (f[1] == "." or f[1] == "N/A" or f[1].isdigit())
        armed = armed and f[2].isdigit()

    # MUTANT: route the action grain through the row-bounding path.
    real = RIB._fetch_action
    try:
        RIB._fetch_action = lambda case, lo, hi, lo_use, cl: dict(
            real(case, lo, hi, lo_use, cl),
            n_rows_printed=3, n_raw_withheld=max(0, len(
                real(case, lo, hi, lo_use, cl)["action_rows"]) - 3))
        rec_m = RIB.fetch(cid, "T-120", "T", grain=RIB.GRAIN_ACTION,
                          max_rows=3)
        mut = (rec_m["n_rows_printed"] == rec_m["n_events"]
               and rec_m["n_raw_withheld"] == 0)
    finally:
        RIB._fetch_action = real
    return check("t04_action_grain_prints_every_event_and_never_thins",
                 "ribbon._fetch_action wrapped to thin at 3 rows", armed, mut,
                 "n_events=%d printed=%d" % (rec["n_events"],
                                             rec["n_rows_printed"]))


def t05_legend_terms_are_the_printed_header_terms():
    """R2-7: the ribbon's column terms and the legend's column terms are ONE
    vocabulary.  A term in the header that the legend never defines is a raw
    view shipping without its dictionary."""
    if not os.path.exists(LEGEND):
        return check("t05_legend_terms_are_the_printed_header_terms",
                     "design/RIBBON_LEGEND.md absent", False, False,
                     "no legend at %s" % LEGEND)
    text = open(LEGEND).read()
    hdr = RIB.ACTION_HEADER.split()
    missing = [c for c in RIB.ACTION_COLUMNS if ("`%s`" % c) not in text]
    armed = (hdr == list(RIB.ACTION_COLUMNS) and not missing
             and "RIBBON_LEGEND" in RIB.PARAMS["legend"])
    # MUTANT: a column term renamed in the printed header only.
    real = RIB.ACTION_HEADER
    try:
        RIB.ACTION_HEADER = real.replace("sequence", "seqnum")
        hdr_m = RIB.ACTION_HEADER.split()
        mut = hdr_m == list(RIB.ACTION_COLUMNS)
    finally:
        RIB.ACTION_HEADER = real
    return check("t05_legend_terms_are_the_printed_header_terms",
                 "ribbon.ACTION_HEADER renames a column", armed, mut,
                 "undefined_in_legend=%s" % missing)


def t06_backward_ts_event_gap_prints_na():
    """Schema audit D3: a snapshot replay steps ts_event BACKWARD.  A negative
    gap would read as a speed measurement; it must print N/A."""
    rows = [{"ts_event": 1000, "sequence": 1, "action": "A", "side": "B",
             "price": 1, "size": 1, "flags": 130, "bid_px": 1, "bid_sz": 1,
             "bid_ct": 1, "ask_px": 2, "ask_sz": 1, "ask_ct": 1,
             "ts_in_delta": 5},
            {"ts_event": 400, "sequence": 2, "action": "A", "side": "B",
             "price": 1, "size": 1, "flags": 162, "bid_px": 1, "bid_sz": 1,
             "bid_ct": 1, "ask_px": 2, "ask_sz": 1, "ask_ct": 1,
             "ts_in_delta": 5}]
    lines, n_back = RIB.action_lines(rows, 900)
    armed = (n_back == 1 and "N/A" in lines[2] and "-600" not in lines[2]
             and "162=LSP" in lines[2])          # the S bit is on the row
    # MUTANT: the backward branch removed (a bare arithmetic gap).
    real = RIB.action_lines
    try:
        def _m(rr, prev):
            L = [RIB.ACTION_HEADER]
            last = prev
            for r in rr:
                g = "." if last is None else str(int(r["ts_event"]) - int(last))
                last = r["ts_event"]
                L.append("  " + g)
            return L, 0
        RIB.action_lines = _m
        lm, nm = RIB.action_lines(rows, 900)
        mut = nm == 1 and "N/A" in lm[2]
    finally:
        RIB.action_lines = real
    return check("t06_backward_ts_event_gap_prints_na",
                 "ribbon.action_lines drops the backward-step branch",
                 armed, mut, "n_back=%d line=%r" % (n_back, lines[2].strip()))


def t07_trajectory_now_point_reproduces_the_sheet():
    """R2-2: the recomputed NOW anchor IS the sheet's number, on the sheet's
    print grid.  Disagreement anywhere means the two earlier points are a
    different constructor, not an earlier reading of the same one."""
    r = E6.traj_check(20240118, assets=["SI"])
    armed = (r["n_compared"] > 200 and r["n_disagree"] == 0)
    # MUTANT: the 60s flow window widened to 120s at the NOW anchor.
    real = E6._sflow
    try:
        E6._sflow = lambda tr, lo, hi: real(tr, lo - 60, hi)
        rm = E6.traj_check(20240118, assets=["SI"])
        mut = rm["n_disagree"] == 0
    finally:
        E6._sflow = real
    return check("t07_trajectory_now_point_reproduces_the_sheet",
                 "e6_round._sflow window widened 60s->120s", armed, mut,
                 "compared=%d disagree=%d" % (r["n_compared"],
                                              r["n_disagree"]))


def t08_chart_render_is_deterministic():
    """R2-5: two renders of the same panel are byte-identical, and a panel is
    refused (never approximated) when its causal series is empty."""
    import chart_panel as CP
    v = CP.verify_deterministic("SI-20240118-003151-L", CP.PANEL_APPROACH)
    armed = bool(v["identical"]) and v["bytes"] > 20000

    # the refusal half: a case with no SANE mid before the decision second
    class _Empty(object):
        pass
    import assemble as A
    import numpy as np
    case = A.Case("SI-20240118-003151-L", want_events=False)
    real_mids = CP._causal_mids
    try:
        CP._causal_mids = lambda c, lo_sec=0: (np.zeros(0, dtype=np.int64),
                                               np.zeros(0))
        try:
            CP.session_panel(case, [])
            refused = False
        except CP.ChartRefusal:
            refused = True
    finally:
        CP._causal_mids = real_mids
    armed = armed and refused

    # MUTANT: the PNG metadata block gains a render timestamp.
    real_md = dict(CP.PNG_METADATA)
    try:
        import itertools
        ctr = itertools.count()
        CP.PNG_METADATA["Creation Time"] = "x"

        real_save = CP.build

        def _mut_build(cid, panel, **kw):
            CP.PNG_METADATA["Creation Time"] = "t%d" % next(ctr)
            return real_save(cid, panel, **kw)
        CP.build = _mut_build
        vm = CP.verify_deterministic("SI-20240118-003151-L",
                                     CP.PANEL_APPROACH)
        mut = bool(vm["identical"])
    finally:
        CP.build = real_save
        CP.PNG_METADATA.clear()
        CP.PNG_METADATA.update(real_md)
    return check("t08_chart_render_is_deterministic",
                 "chart_panel PNG metadata gains a render timestamp",
                 armed, mut, "sha=%s bytes=%d refused_empty=%d"
                 % (v["sha_a"], v["bytes"], int(refused)))


TESTS = (t01_take_without_ribbon_or_chart_is_protocol_invalid,
         t02_take_with_a_ribbon_read_is_not_flagged,
         t03_access_ledger_migrates_onto_n_chart_reads,
         t04_action_grain_prints_every_event_and_never_thins,
         t05_legend_terms_are_the_printed_header_terms,
         t06_backward_ts_event_gap_prints_na,
         t07_trajectory_now_point_reproduces_the_sheet,
         t08_chart_render_is_deterministic)


def main():
    argv = list(sys.argv)
    n_fail = 0
    for t in TESTS:
        try:
            ok = t()
        except Exception as e:              # noqa: BLE001 — recorded, not hidden
            LEDGER.append([t.__name__, "-", 0, 0, "ERROR", repr(e)[:300]])
            ok = False
        finally:
            sys.argv = argv
        if not ok:
            n_fail += 1
        MC.hb("test %s: %s" % (t.__name__, LEDGER[-1][4]))
    MC.write_tsv(os.path.join(OUT_DIR, "r2views_fixlane_red_ledger.tsv"),
                 SECTION, MC.params_hash(PARAMS),
                 ["test", "mutant", "armed_pass", "mutant_pass", "verdict",
                  "detail"], LEDGER,
                 extra=["RED-FIRST: armed_pass MUST be 1 and mutant_pass MUST "
                        "be 0 on every row",
                        "each mutant neutralises ONE named production line of "
                        "the round-2 view stack"])
    MC.write_json(os.path.join(OUT_DIR, "r2views_fixlane_tests.receipt.json"),
                  {"env": MC.env_receipt(PARAMS), "n_tests": len(TESTS),
                   "n_failed": n_fail,
                   "revisions": PARAMS["revisions"],
                   "verdict": "PASS" if n_fail == 0 else "FAIL"})
    MC.hb("r2 views fix-lane tests: %d/%d passed"
          % (len(TESTS) - n_fail, len(TESTS)))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
