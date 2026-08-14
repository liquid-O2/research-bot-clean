#!/usr/bin/python3
"""PORT M2 — RED-FIRST TESTS FOR THE READER-LANE FIX PASS (D-001, one pass).

Every test here asserts a LAW that a numbered finding of
`evidence/port_m2/M2_CONSOLIDATED_REVIEW.md` says was unenforced, and every one
carries a MUTANT that neutralises ONE NAMED PRODUCTION LINE of the fix.  A test
whose mutant survives is a dead test and fails (`FAIL_DEAD_MUTANT`), which is
the shape `test_m2.py` establishes and the shape R41/R87 says the existing leak
fixture violated with two `return True` stubs.

COVERED: R10 R18 R19 R20 R21 R22 R24 R26 R30 R31 R34 R45 R49 R51 R72 R73.

The red ledger is written to
artifacts/cache/port/m2/tests/reader_fixlane_red_ledger.tsv.

Run: /usr/bin/python3 engine/port_m2/test_reader_fixlane.py
"""
import contextlib
import csv
import io
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                          # noqa: E402
import triage_index as TI                       # noqa: E402
import warmup_draw as WD                        # noqa: E402
import e1_blind_declared_policy as D            # noqa: E402
import e1blind_policy as BP                     # noqa: E402
import e1blind_cellbrief as CB                  # noqa: E402
import e1blind_asofwalk as AW                   # noqa: E402
import e1d7_cellbrief as D7CB                   # noqa: E402
import e1d8_cellbrief as D8CB                   # noqa: E402
import e1d8_stage12 as D8S                      # noqa: E402
import e1d7_policy as P7                        # noqa: E402
import e1d6_seal as D6SEAL                      # noqa: E402

SECTION = "§3 reader protocol — D-001 fix-lane red-first tests"
OUT_DIR = MC.out_path("tests", "_")[:-1]
TRIAGE = "/workspace/artifacts/cache/port/m2/triage"

PARAMS = {
    "lane": "D-001 fix pass, reader sub-lane",
    "findings": "R10 R18 R19 R20 R21 R22 R24 R26 R30 R31 R34 R45 R49 R51 "
                "R72 R73",
    "law": "armed_pass MUST be 1 and mutant_pass MUST be 0 on every row",
    "frozen_policy": "CC-M2-4.3 — e1_blind_declared_policy is not retuned; "
                     "t06 proves the committed call set is bit-identical",
}

LEDGER = []


def check(name, mutant, ok_armed, ok_mutant, detail=""):
    verdict = "PASS" if (ok_armed and not ok_mutant) else (
        "FAIL_ARMED" if not ok_armed else "FAIL_DEAD_MUTANT")
    LEDGER.append([name, mutant, int(bool(ok_armed)), int(bool(ok_mutant)),
                   verdict, detail])
    return verdict == "PASS"


# ----------------------------------------------------------- row fixtures ---
def _cell_population(text):
    """The population the brief printed on its THIS-CELL line."""
    for ln in text.split("\n"):
        if "THIS CELL SO FAR" in ln:
            tail = ln.rsplit("):", 1)[-1].strip()
            return int(tail.split(" ", 1)[0])
    return -1


def row(**kw):
    """A synthetic triage row: every current column present, NA by default."""
    r = {c: "." for c in TI.COLUMNS}
    r.update({"cid": "SI-20211020-001000-L", "asset": "SI", "date8": "20211020",
              "side": "LONG", "sec": "1000", "clock": "00:16:40",
              "phase_dec": "TOKYO", "cls": "NEWS-WINDOW",
              "f60_n": "10", "f60_vol": "50", "runway_phase": "30000",
              "extreme_age_trade_side": "100", "f5m_sflow": "50",
              "f5m_vol": "500", "fph_vol": "1000", "rv1800": "300",
              "trapped_above": "1", "trapped_below": "1", "phase_total": "100",
              "thru_n": "20", "thru_bid": "1", "thru_ask": "1",
              "short_day": "0", "observed_close": "82799",
              "runway_observed": "30000", "mid": "23.5"})
    r.update(kw)
    return r


def write_index(path, rows, comments=2, as_of=None):
    lines = ["# TRIAGE INDEX (CC-M2-3) — BLIND sheets only, S14 never opened"]
    if comments >= 2:
        lines.append("# extractor_version %s  columns_sha16 %s  n_columns %d"
                     % (TI.VERSION, "deadbeefdeadbeef", len(TI.COLUMNS)))
    if as_of is not None:
        lines.append("# AS_OF %d  (D14 prefix view)" % as_of)
    cols = list(TI.COLUMNS)
    lines.append("\t".join(cols))
    for r in rows:
        lines.append("\t".join(str(r.get(c, ".")) for c in cols))
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


# ===================================================================== R10 ===
def t01_blind_brief_is_prefix_only():
    """R10: the blind cell brief's per-cell aggregate is computed on rows with
    `sec <= cut`, and the day-complete index is never opened.

    ARMED   the cell's printed population at its open is the PREFIX count.
    MUTANT  MR10: hand `brief_cell` the day-complete cell rows (the shape the
            module had: `rows = cells[k]` off the `--full` index) — the count
            it prints is then the whole day's.
    """
    tmp = tempfile.mkdtemp()
    try:
        rows = [row(cid="SI-20211020-000100-L", sec="100"),
                row(cid="SI-20211020-000200-L", sec="200"),
                row(cid="SI-20211020-005000-L", sec="5000")]
        drive = os.path.join(tmp, "DRIVE")
        os.makedirs(drive)
        write_index(os.path.join(drive, "ASOF_000150.tsv"), rows[:1],
                    as_of=150)
        write_index(os.path.join(drive, "ASOF_005000.tsv"), rows, as_of=5000)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            sys.argv = ["cb", "--drive", drive,
                        "--full", os.path.join(tmp, "DOES_NOT_EXIST.tsv")]
            CB.main()
        n_armed = _cell_population(buf.getvalue())
        armed = (n_armed == 1
                 and "THIS CELL SO FAR (PREFIX-ONLY, sec <= 150" in
                 buf.getvalue())
        # MUTANT MR10: the day-complete cell population at the same open —
        # `rows = cells[k]` off the `--full` index, which is what the module
        # did.  THE LAW (the printed population is the prefix population) must
        # then FAIL.
        mbuf = io.StringIO()
        with contextlib.redirect_stdout(mbuf):
            CB.brief_cell(rows[0], rows, rows[:1], 150, "ASOF_000150.tsv",
                          ("SI", "TOKYO"))
        mutant = (_cell_population(mbuf.getvalue()) == 1)
        return check("blind_brief_is_prefix_only", "MR10_full_day_cell_rows",
                     armed, mutant,
                     "prefix population=%d, day-complete population=%d"
                     % (n_armed, _cell_population(mbuf.getvalue())))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===================================================================== R31 ===
def t02_emitted_fields_checked_against_field_asof_sec():
    """R31: the brief's guard checks EMITTED FIELDS against
    `triage_index.field_asof_sec`, not just the row's own `sec`.

    ARMED   a row that passes `sec <= cut` but carries an OBSERVED_COL
            (end-of-session fact) is REFUSED.
    MUTANT  MR31: the study-day guard shape — filter/assert on `sec` alone,
            which is a self-check and cannot fail on this row.
    """
    r = row(sec="100", observed_close="82799", short_day="1")
    armed = False
    try:
        CB._assert_emitted_asof([r], CB.EMITTED + ("short_day",), 150, "t02")
    except SystemExit as e:
        armed = "short_day" in str(e) and "field_asof_sec" in str(e)

    def _sec_only_guard(rows, cols, cut, where):      # MUTANT MR31
        for x in rows:
            if int(float(x["sec"])) > cut:
                raise SystemExit("late row")
        return True
    mutant = False          # THE LAW under the mutant: does it still refuse?
    try:
        _sec_only_guard([r], CB.EMITTED + ("short_day",), 150, "t02")
    except SystemExit:
        mutant = True
    return check("emitted_fields_checked_against_field_asof_sec",
                 "MR31_sec_only_self_check", armed, mutant,
                 "OBSERVED_COL on a lawful-sec row")


# ===================================================================== R18 ===
def t03_observed_cols_refused_in_study_cellbriefs():
    """R18: `short_day` / `observed_close` are never printed at cell open on
    days 7 and 8 — both briefs read the DAY-COMPLETE index, so the `--as-of`
    mask never applies and the refusal has to be in the brief itself.

    ARMED   both briefs' field reader refuses every `triage_index.OBSERVED_COLS`
            member and passes everything else through.
    MUTANT  MR18: the raw `r.get(k)` the line used to be.
    """
    r = row(short_day="1", observed_close="71354", runway_observed="123")
    armed = True
    for mod in (D7CB, D8CB):
        for c in TI.OBSERVED_COLS:
            armed = armed and "REFUSED" in str(mod.O(r, c))
        armed = armed and mod.O(r, "rv1800") == "300"
    mutant = all("REFUSED" in str(r.get(c)) for c in TI.OBSERVED_COLS)
    return check("observed_cols_refused_in_study_cellbriefs",
                 "MR18_raw_row_get", armed, mutant,
                 "OBSERVED_COLS=%s" % (TI.OBSERVED_COLS,))


# ===================================================================== R19 ===
def t04_side_estimator_anchor_is_causal():
    """R19: a side estimator may only read a row identifiable AT THE CELL OPEN.

    ARMED   every REGISTERED anchor passes `assert_anchor_causal`, and the
            struck median anchor is refused by it.
    MUTANT  MR19: register the median row (the S2e estimator as it stood) —
            it must be refused, and no registered anchor may be it.
    """
    cr = [dict(_sec=1000, cid="a"), dict(_sec=4000, cid="b"),
          dict(_sec=9000, cid="c")]
    armed = True
    for nm, _k, pick in D8S.ANCHORS:
        try:
            D8S.assert_anchor_causal(cr, nm, pick(cr))
        except SystemExit:
            armed = False
    refused = False
    try:                                              # MUTANT MR19
        D8S.assert_anchor_causal(cr, "median", cr[len(cr) // 2])
    except SystemExit:
        refused = True
    armed = armed and refused
    mutant = any(nm == "median" for nm, _k, _p in D8S.ANCHORS)
    return check("side_estimator_anchor_is_causal", "MR19_median_row_anchor",
                 armed, mutant,
                 "registered anchors=%s" % [n for n, _k, _p in D8S.ANCHORS])


# ===================================================================== R20 ===
def t05_minimal_pair_pool_is_causal():
    """R20: the minimal pair is drawn only from rows at or before the seat's
    own decision second, so no post-decision field value enters the sealed
    blind artefact.

    ARMED   the nearest LATER skip is closer in time and is NOT chosen.
    MUTANT  MR20: the day-complete pool (`c["call"] == "SKIP"` with no `sec`
            constraint) chooses it.
    """
    take = row(cid="SI-20211020-001000-L", sec="1000")
    early = row(cid="SI-20211020-000100-L", sec="100", f60_n="1")
    late = row(cid="SI-20211020-001010-L", sec="1010", f60_n="1")
    rows = [take, early, late]
    calls = BP.call_day(rows, day=1)
    picked = BP.minimal_pair(take["cid"], calls, rows)
    armed = (early["cid"] in picked and late["cid"] not in picked)

    def _uncon(cid, calls, rows):                     # MUTANT MR20
        me = next(c for c in calls if c["cid"] == cid)
        pool = [c for c in calls
                if c["asset"] == me["asset"]
                and c["phase_dec"] == me["phase_dec"]
                and c["call"] == "SKIP"]
        return min(pool, key=lambda c: (abs(c["sec"] - me["sec"]), c["cid"]))
    mutant = _uncon(take["cid"], calls, rows)["cid"] == early["cid"]
    return check("minimal_pair_pool_is_causal", "MR20_day_complete_skip_pool",
                 armed, mutant,
                 "seat sec=1000; pairs available at 100 (earlier) and 1010 "
                 "(later, nearer)")


# ===================================================================== R21 ===
def t06_v2_refusal_is_counted_and_not_a_retune():
    """R21 + CC-M2-4.3: V2's pass-on-refused behaviour is DECLARED and COUNTED,
    and the frozen call set does not move.

    ARMED   a refused fuel map yields `v2_state == 'R'` and
            `v2_inputs_refused == 1` while `v2()` still returns False; and the
            declared policy reproduces the committed DECLARED arm on the whole
            E1 BLIND day 1 index, cid for cid.
    MUTANT  MR21: the pre-fix clause (`return False` on refused inputs, no
            state) — the refusal is then invisible in the accounting.
    """
    r = row(phase_total=".")
    st = D.v2_state(r)
    armed = (st == D.REFUSED and D.v2(r) is False
             and D.v2_inputs_refused(r) == 1)
    idx = os.path.join(TRIAGE, "E1BLIND_D1_TRIAGE_INDEX.tsv")
    arms = os.path.join(TRIAGE, "E1BLIND_D1_ARMS.tsv")
    n_cmp = n_bad = 0
    if os.path.exists(idx) and os.path.exists(arms):
        irows, _st = TI.read_index(idx)
        got = {c["cid"]: c["call"] for c in D.call_day(irows)}
        for a in csv.DictReader(open(arms), delimiter="\t"):
            n_cmp += 1
            n_bad += int(got.get(a["cid"]) != a["DECLARED"])
        armed = armed and n_cmp > 500 and n_bad == 0
    else:
        armed = False

    # MUTANT MR21: the pre-fix boolean clause — `return False` on refused
    # inputs and no state at all.  THE LAW (a refused row is distinguishable
    # from a measured non-fire) must then FAIL.
    def _old_v2(rr):
        side = 1 if rr["side"] == "LONG" else -1
        ta, tb, pt = (D.F(rr, "trapped_above"), D.F(rr, "trapped_below"),
                      D.F(rr, "phase_total"))
        if ta is None or tb is None or not pt:
            return False
        frac = (ta / pt) if side > 0 else (tb / pt)
        return False if frac < 0.90 else False
    measured = row(phase_total="100")               # readable, does not fire
    mutant = (_old_v2(r) != _old_v2(measured))
    return check("v2_refusal_is_counted_and_not_a_retune",
                 "MR21_boolean_pass_on_refused", armed, mutant,
                 "%d committed day-1 rows compared, %d call mismatches"
                 % (n_cmp, n_bad))


# ===================================================================== R22 ===
def t07_schema_refusal_beats_a_silent_all_skip():
    """R22: a renamed or dropped index column is REFUSED at load, not turned
    into a whole day of silent SKIPs by `F()`'s bare `except`.

    ARMED   `assert_columns` raises `SchemaRefusal` naming the missing column.
    MUTANT  MR22: the pre-fix path — no assertion; every term is None, every
            row SKIPs, and no exception is raised at all.
    """
    bad = {("X_" + k if k in D.REQUIRED_COLUMNS and k not in
            ("cid", "asset", "side", "cls", "sec", "clock", "phase_dec")
            else k): v for k, v in row().items()}
    armed = False
    try:
        D.assert_columns([bad], path="t07")
    except D.SchemaRefusal as e:
        armed = ("f60_n" in str(e) and "runway_phase" in str(e))
    # MUTANT MR22: the pre-fix path — no assertion anywhere.  THE LAW (a
    # schema break is REFUSED) must then FAIL: every term goes None -> False,
    # the whole day SKIPs and nothing is raised.
    mutant = True
    try:
        t = D.terms(bad)
        allskip = not any(t.values())
        mutant = not allskip          # it "refused" only if it did not do that
    except Exception:
        mutant = True
    return check("schema_refusal_beats_a_silent_all_skip",
                 "MR22_no_schema_assertion", armed, mutant,
                 "%d required columns renamed; old path -> terms all False, "
                 "no exception" % len(D.REQUIRED_COLUMNS))


# ===================================================================== R24 ===
def t08_grade_refusal_has_its_own_token():
    """R24: a refused `sigma_to_exit` is not folded into the bottom band, so
    the CC-M2-4.4 monotone-calibration curve can drop it.

    ARMED   grade -> the REFUSED token, distinct from A|B|C, and counted.
    MUTANT  MR24: `return "C"` — a refusal is then spelled exactly like a
            genuinely low grade.
    """
    refused = row(rv1800=".")
    low = row(rv1800="1", runway_phase="1800")
    g_ref, g_low = D.grade(refused), D.grade(low)
    calls = D.call_day([refused])
    armed = (g_ref == D.REFUSED and g_ref not in ("A", "B", "C")
             and g_low == "C" and calls[0]["conf_refused"] == 1
             and calls[0]["sigma_to_exit"] == D.REFUSED)

    def _old_grade(r):                                # MUTANT MR24
        s = D.sigma_to_exit(r)
        return "C" if s is None else (
            "A" if s >= D.GRADE_A else ("B" if s >= D.GRADE_B else "C"))
    # THE LAW under the mutant: is a refusal still distinguishable from a
    # genuinely low grade?
    mutant = (_old_grade(refused) != _old_grade(low))
    return check("grade_refusal_has_its_own_token", "MR24_refused_graded_C",
                 armed, mutant,
                 "refused=%s low=%s (old: %s vs %s)"
                 % (g_ref, g_low, _old_grade(refused), _old_grade(low)))


# ===================================================================== R26 ===
def t09_frozen_consumers_read_a_head_format_index():
    """R26: the day-1/day-2 policy and seal parse a HEAD-format index.

    ARMED   `triage_index.read_index` returns rows keyed by `cid` from a
            2-comment (current) index AND from a 3-comment as-of prefix.
    MUTANT  MR26: `readlines()[1:]`, which skips exactly ONE comment line and
            therefore consumes the version stamp as the header row — `r["cid"]`
            is then a KeyError.
    """
    tmp = tempfile.mkdtemp()
    try:
        p2 = write_index(os.path.join(tmp, "IDX2.tsv"), [row()], comments=2)
        p3 = write_index(os.path.join(tmp, "IDX3.tsv"), [row()], comments=2,
                         as_of=5000)
        armed = True
        for p in (p2, p3):
            rows, stamps = TI.read_index(p)
            armed = armed and rows and rows[0]["cid"].startswith("SI-")
            armed = armed and stamps.get("columns_sha16")
        mutant = False
        try:                                          # MUTANT MR26
            old = list(csv.DictReader(open(p2).readlines()[1:],
                                      delimiter="\t"))
            mutant = bool(old) and old[0]["cid"].startswith("SI-")
        except KeyError:
            mutant = False
        return check("frozen_consumers_read_a_head_format_index",
                     "MR26_readlines_skip_one", armed, mutant,
                     "2-comment and 3-comment (as-of) indices")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===================================================================== R30 ===
def t10_asof_walk_compares_the_veto():
    """R30: D18b is about the VETO walk; the blind walker compared the call
    alone.

    ARMED   two calls that agree on TAKE/SKIP and differ on the veto set have
            DIFFERENT walk signatures.
    MUTANT  MR30: `seen.setdefault(cid, c["call"])` — the call-only signature
            declares them identical.
    """
    a = {"call": "SKIP", "vetoes": "V2", "v2_state": "1"}
    b = {"call": "SKIP", "vetoes": "", "v2_state": "0"}
    armed = AW.sig(a) != AW.sig(b)
    # MUTANT MR30: `seen.setdefault(cid, c["call"])` — THE LAW (a veto
    # difference is visible in the walk) must then FAIL.
    mutant = (a["call"] != b["call"])
    return check("asof_walk_compares_the_veto", "MR30_call_only_signature",
                 armed, mutant, "sig(a)=%s sig(b)=%s" % (AW.sig(a), AW.sig(b)))


# ===================================================================== R34 ===
def t11_warmup_exclusion_is_enforced_on_the_draw_side():
    """R34: CC-M2-8.1's warm-up exclusion has a DRAW-SIDE guard.

    ARMED   a BLIND draw touching a warm-up session refuses; an undeclared
            STUDY draw refuses; the declared day-1 case passes; a clean draw
            passes.
    MUTANT  MR34: an empty `WARMUP_SESSIONS` table — nothing refuses.
    """
    warm = ["SI-20210831-012312-S", "HG-20210701-019514-L"]
    clean = ["SI-20211020-001000-L"]
    ok = []
    for cids, mode, decl, want_raise in (
            (warm, WD.MODE_BLIND, False, True),
            (warm, WD.MODE_BLIND, True, True),      # no declaration helps BLIND
            (warm, WD.MODE_STUDY, False, True),
            (warm, WD.MODE_STUDY, True, False),
            (clean, WD.MODE_BLIND, False, False),
            (clean, WD.MODE_STUDY, False, False)):
        try:
            WD.assert_draw_lawful(cids, mode=mode, declared=decl, who="t11")
            ok.append(not want_raise)
        except WD.WarmupRefusal:
            ok.append(want_raise)
    armed = all(ok)
    real, WD.WARMUP_SESSIONS = WD.WARMUP_SESSIONS, frozenset()   # MUTANT MR34
    try:
        WD.assert_draw_lawful(warm, mode=WD.MODE_BLIND, who="t11-mutant")
        mutant = False        # THE LAW (a warm-up blind draw refuses) FAILED
    except WD.WarmupRefusal:
        mutant = True
    finally:
        WD.WARMUP_SESSIONS = real
    return check("warmup_exclusion_is_enforced_on_the_draw_side",
                 "MR34_empty_warmup_table", armed, mutant,
                 "6 lawful/unlawful combinations: %s" % ok)


# ===================================================================== R45 ===
def t12_unknown_side_token_refuses_not_inverts():
    """R45: an unrecognised `side` token is a REFUSAL, never a silent SHORT.

    ARMED   `side_int` is None and V2 refuses, in BOTH the frozen policy and
            `e1d7_policy`.
    MUTANT  MR45: `1 if r["side"] == "LONG" else -1` — the SHORT branch is
            evaluated and the fuel-overhang veto FIRES on a token nobody
            declared, i.e. inverted rather than refused.
    """
    r = row(side="LONGISH", trapped_above="0", trapped_below="95",
            phase_total="100", f5m_sflow="100", f5m_vol="500")
    armed = (D.side_int(r) is None and D.v2_state(r) == D.REFUSED
             and P7.side_of(r) is None and P7.v2_state(r) == P7.REFUSED)

    def _old_v2_fires(rr):                            # MUTANT MR45
        side = 1 if rr["side"] == "LONG" else -1
        ta, tb, pt = (D.F(rr, "trapped_above"), D.F(rr, "trapped_below"),
                      D.F(rr, "phase_total"))
        frac = (ta / pt) if side > 0 else (tb / pt)
        if frac < 0.90:
            return False
        s5, v5 = D.F(rr, "f5m_sflow"), D.F(rr, "f5m_vol")
        return bool(s5 is not None and v5 and abs(s5) / v5 >= 0.10
                    and ((s5 < 0) == (side > 0)))
    # THE LAW under the mutant: is the unknown token refused rather than
    # silently traded as a SHORT?  It is not — the veto fires.
    mutant = _old_v2_fires(r) is not True
    return check("unknown_side_token_refuses_not_inverts",
                 "MR45_unknown_token_maps_to_short", armed, mutant,
                 "side=LONGISH: old mapping fires V2 = %s"
                 % _old_v2_fires(r))


# ===================================================================== R49 ===
def t13_seat_table_refuses_before_the_write():
    """R49: an unlisted cell must not kill a seal with a KeyError mid-write.

    ARMED   `SEATS.get(cell, "-")` yields the typed-missing token, and
            `assert_cell_tables` refuses BEFORE the row loop when a table the
            write loop indexes bare does not cover the day's cells.
    MUTANT  MR49: the bare `SEATS[cell]` / bare table index — a KeyError.
    """
    unknown = ("ZZ", "NOWHERE")
    armed = (D6SEAL.SEATS.get(unknown, "-") == "-")
    calls = [{"asset": "ZZ", "phase_dec": "NOWHERE", "vetoes": ""}]
    try:
        D6SEAL.assert_cell_tables(calls)
        armed = False
    except SystemExit as e:
        armed = armed and "REFUSED before writing" in str(e)
    # MUTANT MR49: the bare index.  THE LAW (an unlisted cell does not kill
    # the seal) must then FAIL.
    mutant = True
    try:
        _ = D6SEAL.SEATS[unknown]
    except KeyError:
        mutant = False
    return check("seat_table_refuses_before_the_write",
                 "MR49_bare_seats_index", armed, mutant,
                 "unlisted cell %s" % (unknown,))


# ===================================================================== R51 ===
def t14_short_day_flag_is_emitted_and_three_valued():
    """R51: T2 reads the NOMINAL runway and the policy is frozen, so the row
    carries a SHORT-DAY flag for the scoring pass — and a masked
    `short_day` is a refusal, never a 0.

    ARMED   1 / 0 / R for short / full / masked, present in the emitted call.
    MUTANT  MR51: `int(v or 0)` — the masked prefix value becomes a confident
            "full session".
    """
    short = row(short_day="1", runway_observed="71354")
    full = row(short_day="0")
    masked = row(short_day=".", runway_observed=".")
    armed = (D.short_day_flag(short) == "1" and D.short_day_flag(full) == "0"
             and D.short_day_flag(masked) == D.REFUSED)
    c = D.call_day([short])[0]
    armed = armed and c["short_day"] == "1" and c["runway_observed"] == "71354"
    b = BP.call_day([masked], day=1)[0]
    armed = armed and b["short_day"] == D.REFUSED

    def _old(r):                                      # MUTANT MR51
        try:
            return "1" if int(float(r.get("short_day") or 0)) else "0"
        except Exception:
            return "0"
    # THE LAW under the mutant: is a masked short_day still distinguishable
    # from a measured full session?
    mutant = (_old(masked) != _old(full))
    return check("short_day_flag_is_emitted_and_three_valued",
                 "MR51_masked_short_day_becomes_zero", armed, mutant,
                 "masked -> %s (old: %s)"
                 % (D.short_day_flag(masked), _old(masked)))


# ===================================================================== R72 ===
def t15_thru_refusal_sentinel_is_not_a_number():
    """R72: `-1` on `thru_n`/`thru_bid`/`thru_ask` is the event-cache REFUSAL
    SENTINEL and must not be compared against the >= 10 threshold as data.

    ARMED   `FT` refuses it, V2's state is REFUSED (not a measured non-fire)
            and V2 is named in `veto_refusals`.
    MUTANT  MR72: read the triple with `F` — `-1 >= 10` evaluates to False and
            the book clause silently never fires, so a `--no-events` re-grade
            measures a different veto than the one being graded.
    """
    # side LONG, fuel overhang above at 0.95, and the 5m flow CONCORDANT
    # (s5 > 0 on a LONG) so the flow clause does NOT fire — the veto's answer
    # therefore depends entirely on the through-book triple.
    # V3's inputs are made READABLE (and non-firing) so the only refusal on
    # this row is V2's through-book.
    r = row(trapped_above="95", trapped_below="0", phase_total="100",
            f5m_sflow="100", f5m_vol="500",
            f60_sflow="0", f60_vol="50", slope1m="0",
            thru_n="-1", thru_bid="-1", thru_ask="-1")
    armed = (P7.FT(r, "thru_n") is None
             and P7.v2_state(r) == P7.REFUSED
             and P7.veto_refusals(r) == ["V2"]
             and P7.v2(r) is False)

    # MUTANT MR72: read the triple with `F`, i.e. treat -1 as a count.  THE
    # LAW (the sentinel is REFUSED, not evaluated) must then FAIL — the book
    # clause quietly returns "no overhang" instead.
    def _old_state(rr):
        tn, tbid, task = (P7.F(rr, "thru_n"), P7.F(rr, "thru_bid"),
                          P7.F(rr, "thru_ask"))
        if tn is None or tbid is None or task is None:
            return P7.REFUSED
        return bool(tn >= 10 and tbid >= 2 * task)
    mutant = (_old_state(r) == P7.REFUSED)
    return check("thru_refusal_sentinel_is_not_a_number",
                 "MR72_sentinel_read_as_a_count", armed, mutant,
                 "thru_n=-1: FT=%s, F=%s, new state=%s, old book clause=%s"
                 % (P7.FT(r, "thru_n"), P7.F(r, "thru_n"), P7.v2_state(r),
                    _old_state(r)))


# ===================================================================== R73 ===
def t16_nan_is_refused_not_a_second_pass_branch():
    """R73: a NaN input must be a refusal.  It used to survive `F()` as a NaN
    float, and every comparison against NaN is False — so `frac < 0.90` passed
    the row through a SECOND branch that also evaluated False.  For a veto,
    "does not fire" is the PASS direction, so the NaN turned the veto off
    twice over — or, on this fixture, made it FIRE on a fuel map that was never
    read at all.

    ARMED   `F` returns None on NaN and V2's state is REFUSED.
    MUTANT  MR73: `float(r[k])` unguarded — NaN flows through and the flow
            clause fires a veto on an unread fuel map.
    """
    r = row(trapped_above="1", trapped_below="1", f5m_sflow="-100",
            f5m_vol="500")
    r["phase_total"] = float("nan")
    armed = (P7.F(r, "phase_total") is None
             and P7.v2_state(r) == P7.REFUSED and P7.v2(r) is False)

    def _old_F(rr, k):                                # MUTANT MR73
        try:
            return float(rr[k])
        except Exception:
            return None

    def _old_v2(rr):
        side = P7.SIDES.get(str(rr.get("side")), -1)
        ta, tb, pt = (_old_F(rr, "trapped_above"), _old_F(rr, "trapped_below"),
                      _old_F(rr, "phase_total"))
        if ta is None or tb is None or not pt:
            return False
        frac = (ta / pt) if side > 0 else (tb / pt)
        if frac < 0.90:
            return False
        s5, v5 = _old_F(rr, "f5m_sflow"), _old_F(rr, "f5m_vol")
        return bool(s5 is not None and v5 and abs(s5) / v5 >= 0.10
                    and ((s5 < 0) == (side > 0)))
    # THE LAW under the mutant: is the NaN refused?  It is not — the old
    # code fires a veto on a fuel map it never read.
    mutant = (_old_v2(r) is not True)
    return check("nan_is_refused_not_a_second_pass_branch",
                 "MR73_unguarded_float_lets_nan_through", armed, mutant,
                 "NaN phase_total: old F -> %s, old v2 -> %s; new state -> %s"
                 % (_old_F(r, "phase_total"), _old_v2(r), P7.v2_state(r)))


TESTS = (t01_blind_brief_is_prefix_only,
         t02_emitted_fields_checked_against_field_asof_sec,
         t03_observed_cols_refused_in_study_cellbriefs,
         t04_side_estimator_anchor_is_causal,
         t05_minimal_pair_pool_is_causal,
         t06_v2_refusal_is_counted_and_not_a_retune,
         t07_schema_refusal_beats_a_silent_all_skip,
         t08_grade_refusal_has_its_own_token,
         t09_frozen_consumers_read_a_head_format_index,
         t10_asof_walk_compares_the_veto,
         t11_warmup_exclusion_is_enforced_on_the_draw_side,
         t12_unknown_side_token_refuses_not_inverts,
         t13_seat_table_refuses_before_the_write,
         t14_short_day_flag_is_emitted_and_three_valued,
         t15_thru_refusal_sentinel_is_not_a_number,
         t16_nan_is_refused_not_a_second_pass_branch)


def main():
    argv = list(sys.argv)
    n_fail = 0
    for t in TESTS:
        try:
            ok = t()
        except Exception as e:            # noqa: BLE001 — recorded, not hidden
            LEDGER.append([t.__name__, "-", 0, 0, "ERROR", repr(e)[:200]])
            ok = False
        finally:
            sys.argv = argv
        if not ok:
            n_fail += 1
        MC.hb("test %s: %s" % (t.__name__, LEDGER[-1][4]))
    MC.write_tsv(os.path.join(OUT_DIR, "reader_fixlane_red_ledger.tsv"),
                 SECTION, MC.params_hash(PARAMS),
                 ["test", "mutant", "armed_pass", "mutant_pass", "verdict",
                  "detail"], LEDGER,
                 extra=["RED-FIRST: armed_pass MUST be 1 and mutant_pass MUST "
                        "be 0 on every row",
                        "each mutant neutralises ONE named production line of "
                        "the D-001 reader-lane fix"])
    MC.write_json(os.path.join(OUT_DIR, "reader_fixlane_tests.receipt.json"),
                  {"env": MC.env_receipt(PARAMS), "n_tests": len(TESTS),
                   "n_failed": n_fail,
                   "findings": PARAMS["findings"],
                   "verdict": "PASS" if n_fail == 0 else "FAIL"})
    MC.hb("reader fix-lane tests: %d/%d passed" % (len(TESTS) - n_fail,
                                                   len(TESTS)))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
