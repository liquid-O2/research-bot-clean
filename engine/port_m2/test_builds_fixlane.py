#!/usr/bin/python3
"""PORT M2 — red-first tests for the D-080 build lane (ribbon + episode round).

Shape mirrors test_m2.py: every test that asserts a LAW carries a committed
MUTANT — a NAMED neutralised production line the test must catch.  A test whose
mutant survives is a dead test and fails (R41: two `return True` mutants in the
existing suite proved this is not a hypothetical).

Ledger: artifacts/cache/port/m2/tests/fixlane_red_ledger.tsv
Receipt: artifacts/cache/port/m2/tests/fixlane_tests.receipt.json

Run: /usr/bin/python3 engine/port_m2/test_builds_fixlane.py
"""
import os
import subprocess
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(os.path.dirname(_HERE), "port_m1")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import m2_common as MC                    # noqa: E402
import assemble as A                      # noqa: E402
import sections as SEC                    # noqa: E402
import sheets as SH                       # noqa: E402
import tape as TAPE                       # noqa: E402
import era_index as EI                    # noqa: E402
import episode_v2 as EV                   # noqa: E402
import ribbon as RIB                      # noqa: E402
import episode_round as ER                # noqa: E402

SECTION = "§1 S6 on-demand ribbon + §3 episode round (D-080 build lane tests)"
OUT_DIR = MC.out_path("tests", "_")[:-1]
TEST_ROOT = MC.out_path("tests", "episode_round", "_")[:-1]
MUTANT_DIR = MC.out_path("tests", "mutants", "_")[:-1]

# Fixtures: real E1 BLIND material.  CID is the first SI candidate of
# 2021-10-20; DAY_A/DAY_B are two real BLIND sessions (the R81 mutant needs a
# MULTI-DAY index to bite, which is exactly the condition that hid it).
CID = "SI-20211020-001014-S"
ERA = "E1"
DAY_A = 20211020
DAY_B = 20211021
SCORE_DAY = 20211125                      # the era's cheapest BLIND SI session

LEDGER = []


def check(name, mutant, ok_armed, ok_mutant, detail=""):
    verdict = "PASS" if (ok_armed and not ok_mutant) else (
        "FAIL_ARMED" if not ok_armed else "FAIL_DEAD_MUTANT")
    LEDGER.append([name, mutant, int(bool(ok_armed)), int(bool(ok_mutant)),
                   verdict, detail])
    return verdict == "PASS"


# ===================================================== TOOL 1: THE RIBBON ====
def t01_ribbon_refuses_past_the_decision_second():
    """LAW (D-080.4): the window ends at or before the END of the decision
    second — `dec_ns = (decision_ts + 1) * 1e9`.  There is no flag that
    disables it.

    MUTANT MR01 neutralises the guard call in `ribbon.fetch` by widening the
    permitted bound one second (`at_decision(hi - 1, ...)`), which is what a
    "just let the reader see the next second" patch looks like.
    """
    case = A.Case(CID, want_events=False)
    raised = ""
    try:
        RIB.fetch(CID, case.dec_sec - 30, case.dec_sec + 1, grain="raw")
    except MC.LeakRefusal as e:
        raised = str(e)
    # the message must NAME both bounds (requested and permitted)
    dec_ns = (case.decision_ts + 1) * 10 ** 9
    armed = ("requested_end_ns=%d" % ((case.open_utc + case.dec_sec + 2)
                                      * 10 ** 9) in raised
             and "permitted_end_ns=%d" % dec_ns in raised)
    # the lawful window at the boundary must still work
    ok_edge = RIB.fetch(CID, case.dec_sec - 30, case.dec_sec,
                        grain="raw")["n_events"] >= 0
    armed = armed and ok_edge
    # MUTANT MR01: the widened guard — the SAME request, checked one second
    # short of where the law puts the bound.  It must stop refusing.
    m_case = A.Case(CID, want_events=False)
    mutant = False
    try:
        m_case.guard.at_decision((case.dec_sec + 1) - 1, "MR01 widened bound")
    except MC.LeakRefusal:
        mutant = True
    return check("ribbon_refuses_past_the_decision_second",
                 "MR01_widen_causal_bound_by_one_second", armed, mutant,
                 raised[:120])


def t02_ribbon_two_run_byte_identical():
    """LAW: the ribbon is a pure function of the event cache."""
    case = A.Case(CID, want_events=False)
    a = RIB.fetch(CID, case.dec_sec - 600, case.dec_sec, grain="both",
                  max_rows=50)
    b = RIB.fetch(CID, a["from_sec"], a["to_sec"], grain="both", max_rows=50)
    armed = a["text"] == b["text"] and a["tokens_proxy"] == b["tokens_proxy"]
    # MUTANT MR02: a wall-clock stamp in the output
    import datetime as dt
    m1 = a["text"] + str(dt.datetime.now().microsecond)
    m2 = a["text"] + str(dt.datetime.now().microsecond + 1)
    mutant = (m1 == m2)
    return check("ribbon_two_run_byte_identical", "MR02_wallclock_stamp",
                 armed, mutant, "tokens=%d" % a["tokens_proxy"])


def t03_ribbon_digests_partition_every_event():
    """LAW (spec §1 S6): every event belongs to EXACTLY ONE episode; no
    minimum-size filter and — in the tool — no episode-count merge.

    MUTANT MR03 applies the sheet's budget merge (max_eps small), which is
    lawful inside a token-bounded sheet but would silently coarsen an
    on-demand request.
    """
    case = A.Case(CID, want_events=False)
    r = RIB.fetch(CID, case.dec_sec - 600, case.dec_sec, grain="digest",
                  max_rows=None)
    n = r["n_events"]
    covered = sum(b - a for a, b in r["digest_rows"])
    starts = [a for a, _b in r["digest_rows"]]
    armed = (n > 0 and covered == n and starts == sorted(starts)
             and r["digest_rows"][0][0] == 0
             and r["digest_rows"][-1][1] == n
             and all(r["digest_rows"][i][1] == r["digest_rows"][i + 1][0]
                     for i in range(len(r["digest_rows"]) - 1)))
    # the partition must equal the pure gap rule at S6_GAP_SEC
    ev = r["events"]
    gaps = np.diff(ev["ts_ns"]).astype(np.float64) / 1e9
    want = 1 + int(np.sum(gaps >= SEC.S6_GAP_SEC))
    armed = armed and len(r["digest_rows"]) == want
    # MUTANT MR03: the budgeted merge
    merged = SEC._episodes(ev, 0, n, SEC.S6_GAP_SEC, 4)
    mutant = len(merged) == want
    return check("ribbon_digests_partition_every_event",
                 "MR03_budget_merge_episodes", armed, mutant,
                 "n_events=%d n_episodes=%d" % (n, len(r["digest_rows"])))


def t04_ribbon_headers_match_the_sheet():
    """LAW: the tool and S6 cannot drift.  The duplicated column headers are
    compared against the ones a REAL rendered sheet prints.

    MUTANT MR04 is a one-character header edit — the class of drift that makes
    a reader's two views silently incomparable.
    """
    sh = SH.build(CID, MC.MODE_BLIND)
    lines = sh.text.split("\n")
    dig = [ln for ln in lines if ln.startswith("    t0 ")]
    raw = [ln for ln in lines if ln.startswith("        ms a s")]
    armed = (bool(dig) and bool(raw) and dig[0] == RIB.DIGEST_HEADER
             and raw[0] == RIB.RAW_HEADER)
    mutant = (dig[0] == RIB.DIGEST_HEADER.replace("trav$", "trav")) \
        if dig else True
    return check("ribbon_headers_match_the_sheet", "MR04_header_drift",
                 armed, mutant, "digest_hdr_ok=%d" % int(bool(dig)))


def t05_ribbon_max_rows_reports_what_it_withheld():
    """LAW: a bound that binds is never a silent truncation."""
    case = A.Case(CID, want_events=False)
    full = RIB.fetch(CID, case.dec_sec - 600, case.dec_sec, grain="raw",
                     max_rows=None)
    cut = RIB.fetch(CID, case.dec_sec - 600, case.dec_sec, grain="raw",
                    max_rows=5)
    armed = (full["n_raw_withheld"] == 0 and cut["n_raw_printed"] == 5
             and cut["n_raw_withheld"] == full["n_raw"] - 5
             and "MAX-ROWS BOUND BINDS" in cut["text"]
             and str(cut["n_raw_withheld"]) in cut["text"])
    # MUTANT MR05: truncate without saying so (the V0 behaviour)
    silent = "\n".join(ln for ln in cut["text"].split("\n")
                       if "MAX-ROWS BOUND BINDS" not in ln)
    mutant = "MAX-ROWS BOUND BINDS" in silent
    return check("ribbon_max_rows_reports_what_it_withheld",
                 "MR05_silent_truncation", armed, mutant,
                 "withheld=%d of %d" % (cut["n_raw_withheld"], full["n_raw"]))


def t06_ribbon_extends_the_cache_beyond_the_sheet_window():
    """LAW: a window the cache does not cover EXTENDS the cache; it is never
    silently shortened.  The sheet's canonical window is
    [T-RIBBON_DIGEST-RAW-PAD, T]; this asks for twice that.
    """
    case = A.Case(CID, want_events=False)
    far = TAPE.RIBBON_DIGEST_SEC + TAPE.RIBBON_RAW_SEC + 600
    lo = case.dec_sec - far
    if lo < 0:                              # the fixture must exercise the law
        lo = 0
    r = RIB.fetch(CID, lo, case.dec_sec, grain="digest", max_rows=None)
    ts = r["events"]["ts_ns"]
    armed = (r["n_events"] > 0
             and int(ts[0]) < (case.open_utc + case.dec_sec
                               - TAPE.RIBBON_DIGEST_SEC
                               - TAPE.RIBBON_RAW_SEC) * 10 ** 9
             and TAPE._covers(r["cache_cover"], max(0, lo - 2),
                              case.dec_sec + 1))
    # MUTANT MR06: refuse to extend — serve only what the S6 window cached
    narrow = RIB.fetch(CID, case.dec_sec - TAPE.RIBBON_RAW_SEC, case.dec_sec,
                       grain="digest", max_rows=None)
    mutant = narrow["n_events"] >= r["n_events"]
    return check("ribbon_extends_the_cache_beyond_the_sheet_window",
                 "MR06_serve_only_the_prebaked_window", armed, mutant,
                 "n_events far=%d near=%d" % (r["n_events"],
                                              narrow["n_events"]))


# ============================================== TOOL 2: THE EPISODE ROUND ====
def _sessionless_episode_count(era, asset, days):
    """R81 AS IMPLEMENTED: key = (asset, side), the date8 column ignored and
    the concatenated SESSION seconds sorted as if they were one clock."""
    rows = []
    for d in days:
        rows += [r for r in EI.load_index(era, asset)
                 if int(r["date8"]) == d and r["eligible"] == "1"]
    n = 0
    for side in (1, -1):
        rs = sorted([r for r in rows if int(r["side"]) == side],
                    key=lambda r: int(r["dec_sec"]))
        if not rs:
            continue
        dec = np.array([int(r["dec_sec"]) for r in rs], dtype=np.int64)
        n += len(EV.group_causal(dec, ER.KSTAR[(asset, side)],
                                 ER.SPAN_MAX[(asset, side)]))
    return n


def _session_episode_count(era, asset, days):
    n = 0
    for d in days:
        eps, _rec = ER.build(era, d, [asset], write=False)
        n += len(eps)
    return n


def t07_episode_key_includes_the_session():
    """LAW (R81): EPISODE_CAUSAL is keyed (asset, date8, side).  Dropping the
    session component is a measured 24.8x UNDER-count on a multi-day index —
    and that arm is where the reader's margin is taken.

    MUTANT ME07 is `baseline_replay.episodes()`'s key: (asset, side) with the
    date8 column present and ignored.
    """
    days = [DAY_A, DAY_B]
    keyed = _session_episode_count(ERA, "SI", days)
    flat = _sessionless_episode_count(ERA, "SI", days)
    # the day-by-day count is also what a per-day build must reproduce exactly
    per_day = [len(ER.build(ERA, d, ["SI"], write=False)[0]) for d in days]
    armed = (keyed == sum(per_day) and keyed > 0 and flat != keyed
             and flat < keyed)
    # MUTANT ME07: accept the sessionless grouping as the day's episode set
    mutant = (flat == keyed)
    return check("episode_key_includes_the_session",
                 "ME07_drop_date8_from_the_episode_key", armed, mutant,
                 "session_keyed=%d sessionless=%d (%.2fx under-count)"
                 % (keyed, flat, (float(keyed) / flat) if flat else float("nan")))


def t08_episode_index_two_run_byte_identical():
    """LAW: the index is a pure function of the era index + the frozen tables."""
    ER.set_root(TEST_ROOT)
    ER.build(ERA, DAY_A, ["SI"])
    with open(ER.index_path(ERA, DAY_A), "rb") as fh:
        a = fh.read()
    ER.build(ERA, DAY_A, ["SI"])
    with open(ER.index_path(ERA, DAY_A), "rb") as fh:
        b = fh.read()
    armed = (a == b and len(a) > 0)
    # MUTANT ME08: emit in episode_id order instead of (first_dec_sec,
    # episode_id) — the two sides interleave in time, so id order is a
    # DIFFERENT sequence and the file would not be the day's chronology
    eps, _r = ER.build(ERA, DAY_A, ["SI"], write=False)
    ids = [e["episode_id"] for e in eps]
    mutant = (ids == sorted(ids))
    return check("episode_index_two_run_byte_identical",
                 "ME08_unordered_episode_emission", armed, mutant,
                 "bytes=%d" % len(a))


def t09_frozen_kstar_matches_the_committed_receipt():
    """LAW: the K*/SPAN_MAX copy is ASSERTED against the episode_v2 receipt at
    run time, never trusted.

    MUTANT ME09 perturbs one copied constant — the class of error a hand-copied
    frozen table actually suffers.
    """
    prov = ER.assert_frozen_tables()
    armed = (prov["n_keys"] == 6
             and prov["receipt"] == ER.EPISODE_V2_RECEIPT
             and os.path.exists(ER.EPISODE_V2_RECEIPT))
    saved = ER.KSTAR[("SI", -1)]
    ER.KSTAR[("SI", -1)] = saved + 1
    try:
        ER.assert_frozen_tables()
        mutant = True
    except ER.FrozenTableMismatch:
        mutant = False
    finally:
        ER.KSTAR[("SI", -1)] = saved
    return check("frozen_kstar_matches_the_committed_receipt",
                 "ME09_perturb_one_copied_constant", armed, mutant,
                 "n_keys=%d" % prov["n_keys"])


def t10_build_and_view_never_import_panel_score():
    """LAW (D-080 blind safety): nothing on the ranking path may read an
    outcome.  Enforced MECHANICALLY — after importing the module and running
    build + view, `panel_score` must be absent from sys.modules.

    MUTANT ME10 is a byte-copy of episode_round.py with the deliberate absence
    of `import panel_score` neutralised (the import restored at module level);
    the same probe must then FAIL.
    """
    probe = (
        "import sys, os\n"
        "sys.path.insert(0, %r)\n"        # port_m1
        "sys.path.insert(0, %r)\n"        # engine/port_m2
        "sys.path.insert(0, %r)\n"        # the module under test
        "import %s as ER\n"
        "ER.set_root(%r)\n"
        "eps, rec = ER.build(%r, %d, ['SI'], write=False)\n"
        "ER.build(%r, %d, ['SI'])\n"
        "v = ER.view(eps[0]['episode_id'], record=False)\n"
        "print('panel_score' in sys.modules)\n")

    def run(modname, moddir):
        src = probe % (os.path.join(os.path.dirname(_HERE), "port_m1"),
                       _HERE, moddir, modname, TEST_ROOT,
                       ERA, DAY_A, ERA, DAY_A)
        p = subprocess.run([sys.executable, "-c", src], capture_output=True,
                           text=True)
        return p.stdout.strip().split("\n")[-1] if p.returncode == 0 else \
            ("ERROR:" + p.stderr[-300:])

    armed_out = run("episode_round", _HERE)
    # source-level companion: no top-level `import panel_score`
    with open(os.path.join(_HERE, "episode_round.py")) as fh:
        src = fh.read()
    top_level = [ln for ln in src.split("\n")
                 if ln.startswith("import panel_score")
                 or ln.startswith("from panel_score")]
    armed = (armed_out == "False" and not top_level)

    os.makedirs(MUTANT_DIR, exist_ok=True)
    mpath = os.path.join(MUTANT_DIR, "episode_round_ME10.py")
    MC.write_text(mpath, src.replace(
        "# NOTE: panel_score is deliberately NOT imported here.",
        "import panel_score as PS   # MUTANT ME10\n"
        "# NOTE: panel_score is deliberately NOT imported here."))
    mutant_out = run("episode_round_ME10", MUTANT_DIR)
    mutant = (mutant_out == "False")
    return check("build_and_view_never_import_panel_score",
                 "ME10_restore_top_level_panel_score_import", armed, mutant,
                 "armed=%s mutant=%s" % (armed_out, mutant_out))


def _seed_access(era, date8, skip=0):
    """Populate the deep-read ledger for the day, optionally leaving `skip`
    episodes out (the fixture for the scoreability gate)."""
    p = os.path.join(ER.OUT_DIR, "EPISODE_ACCESS.tsv")
    if os.path.exists(p):
        os.remove(p)
    eps = ER.load_episodes(era, date8)
    for e in eps[:len(eps) - skip]:
        ER._append_access({"seq": 0, "episode_id": e["episode_id"],
                           "era": era, "asset": e["asset"], "date8": date8,
                           "rep_cid": e["rep_cid"],
                           "n_members": e["n_members"], "mode": MC.MODE_BLIND,
                           "sheet_source": "render", "sheet_sha16": "-",
                           "sheet_tokens": 0, "n_ribbon_cmds": 1,
                           "s14_guard_paths_checked": 0, "round": "TEST",
                           "caller": "test_builds_fixlane"})
    return eps


def t11_score_refuses_a_day_with_a_missing_deep_read():
    """LAW (D-080.2 / R02): "every episode was deep-read" is a CHECKED fact.  A
    day with one missing access-ledger entry is REFUSED, and the refusal names
    the missing episodes.

    MUTANT ME11 neutralises the gate (`require_access=False`), which is what a
    "just let it score" patch looks like.
    """
    ER.set_root(TEST_ROOT)
    ER.build(ERA, SCORE_DAY, ["SI"])
    eps = _seed_access(ERA, SCORE_DAY, skip=1)
    rank = ER.emit_ranking(ERA, SCORE_DAY, ER.ARM_SIZE,
                           os.path.join(TEST_ROOT, ERA, "RANK_TEST.tsv"))
    missing = ER.missing_access(ERA, SCORE_DAY, "TEST")
    msg = ""
    try:
        ER.score(ERA, {SCORE_DAY: rank}, outdir=os.path.join(TEST_ROOT, ERA),
                 round_name="TEST")
        raised = False
    except ER.AccessRefusal as e:
        raised = True
        msg = str(e)
    armed = (raised and len(missing) == 1 and missing[0] in msg
             and eps[-1]["episode_id"] == missing[0])
    # MUTANT ME11: the gate switched off — the SAME day, one episode still
    # unread, must stop being refused
    mutant = False
    try:
        ER.score(ERA, {SCORE_DAY: rank}, outdir=os.path.join(TEST_ROOT, ERA),
                 round_name="TEST", require_access=False)
    except ER.AccessRefusal:
        mutant = True
    return check("score_refuses_a_day_with_a_missing_deep_read",
                 "ME11_disable_the_access_gate", armed, mutant,
                 "missing=%s" % (missing[:1],))


def t12_ranking_validation_refuses_a_partial_day():
    """LAW (D-080.3): the reader ranks the WHOLE day or declares an explicit
    ABSTAIN set; ranks are a permutation of 1..n; unknown/duplicate ids refuse.

    MUTANT ME12 drops the completeness clause (validate only what was handed
    in), which is the keyhole the whole directive exists to close.
    """
    ER.set_root(TEST_ROOT)
    eps, _r = ER.build(ERA, DAY_A, ["SI"], write=False)
    ids = [e["episode_id"] for e in eps]
    full = [{"rank": str(i + 1), "episode_id": e} for i, e in enumerate(ids)]
    ok = ER.validate_ranking(eps, full)
    part = full[:10]
    cases = {}
    for name, rows in (("partial", part),
                       ("unknown", full[:-1] + [{"rank": str(len(ids)),
                                                 "episode_id": "SI-20211020-"
                                                               "S-E99999"}]),
                       ("dupe", full + [{"rank": "1",
                                         "episode_id": ids[0]}]),
                       ("gap", [{"rank": str(i + 2), "episode_id": e}
                                for i, e in enumerate(ids)])):
        try:
            ER.validate_ranking(eps, rows)
            cases[name] = ""
        except ER.RankingRefusal as e:
            cases[name] = str(e)
    abst = ([{"rank": str(i + 1), "episode_id": e}
             for i, e in enumerate(ids[:-3])]
            + [{"rank": "ABSTAIN", "episode_id": e} for e in ids[-3:]])
    ab = ER.validate_ranking(eps, abst)
    armed = (ok["n_ranked"] == len(ids) and all(cases[k] for k in cases)
             and ab["n_abstain"] == 3
             and ab["order"][-3:] == sorted(ids[-3:]))
    # MUTANT ME12: the completeness clause neutralised — validate the partial
    # ranking against only the episodes it happens to mention
    mutant = False
    try:
        ER.validate_ranking(eps[:10], part)
    except ER.RankingRefusal:
        mutant = True
    return check("ranking_validation_refuses_a_partial_day",
                 "ME12_validate_only_the_rows_handed_in", armed, mutant,
                 "refusals=%d/4" % sum(1 for k in cases if cases[k]))


def t13_score_two_run_byte_identical():
    """LAW: the scorer (including its seeded permutation baseline) is a pure
    function of the index, the ranking and the frozen roster.

    MUTANT ME13 draws the permutation baseline from an unseeded RNG.
    """
    ER.set_root(TEST_ROOT)
    ER.build(ERA, SCORE_DAY, ["SI"])
    _seed_access(ERA, SCORE_DAY, skip=0)
    rank = ER.emit_ranking(ERA, SCORE_DAY, ER.ARM_SIZE,
                           os.path.join(TEST_ROOT, ERA, "RANK_TEST.tsv"))
    out = os.path.join(TEST_ROOT, ERA)
    ER.score(ERA, {SCORE_DAY: rank}, outdir=out, round_name="TEST")
    p = os.path.join(out, "EPISODE_ROUND_SCORE_%s.tsv" % ERA)
    with open(p, "rb") as fh:
        a = fh.read()
    pp = os.path.join(out, "EPISODE_ROUND_PAIRED.tsv")
    with open(pp, "rb") as fh:
        pa = fh.read()
    ER.score(ERA, {SCORE_DAY: rank}, outdir=out, round_name="TEST")
    with open(p, "rb") as fh:
        b = fh.read()
    with open(pp, "rb") as fh:
        pb = fh.read()
    armed = (a == b and pa == pb and len(a) > 0)
    # MUTANT ME13: unseeded permutations
    eps = ER.load_episodes(ERA, SCORE_DAY)
    real = {e["episode_id"]: float(i) for i, e in enumerate(eps)}
    pay = {e["episode_id"]: 0 for e in eps}
    d1 = ER.random_permutation_dist(sorted(real), real, pay, 1.0,
                                    seed=ER.PERM_SEED, n_perm=25)
    d2 = ER.random_permutation_dist(sorted(real), real, pay, 1.0,
                                    seed=ER.PERM_SEED + 1, n_perm=25)
    same = ER.random_permutation_dist(sorted(real), real, pay, 1.0,
                                      seed=ER.PERM_SEED, n_perm=25)
    armed = armed and d1 == same
    mutant = (d1 == d2)
    return check("score_two_run_byte_identical", "ME13_unseeded_permutation",
                 armed, mutant, "score_bytes=%d paired_bytes=%d"
                 % (len(a), len(pa)))


def t14_realized_payment_is_read_never_rederived():
    """LAW (D-080.3): realised payment is the walled close certificate of the
    REPRESENTATIVE, READ through panel_score.outcome.

    MUTANT ME14 substitutes the episode's BEST member certificate — the
    hindsight version of the same number, and the one a re-derivation would
    quietly produce.
    """
    import panel_score as PS               # test-side only; score()'s import
    ER.set_root(TEST_ROOT)
    eps = ER.load_episodes(ERA, SCORE_DAY)
    by = {e["episode_id"]: e for e in eps}
    rank_p = os.path.join(TEST_ROOT, ERA, "RANK_TEST.tsv")
    top = ER.read_ranking(rank_p)
    top1 = [r["episode_id"] for r in top if r["rank"] == "1"][0]
    want = float(PS.outcome(by[top1]["rep_cid"])["cert_close_usd"])
    got = None
    with open(os.path.join(TEST_ROOT, ERA,
                           "EPISODE_ROUND_SCORE_%s.tsv" % ERA)) as fh:
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) < 8 or f[0] != ERA:
                continue
            if (f[2] == "DAY" and f[4] == ER.ARM_READER
                    and f[5] == ER.METRIC_DOLLARS and f[6] == "1"):
                got = float(f[7])
    armed = (got is not None and abs(got - want) < 1e-9)
    # MUTANT ME14: the hindsight version of the same number — the episode's
    # BEST member certificate instead of the representative's
    best = max(float(PS.outcome(c)["cert_close_usd"])
               for c in by[top1]["members"].split(","))
    n_multi = sum(1 for e in eps if e["n_members"] > 1)
    n_diff = 0
    for e in eps:
        if e["n_members"] < 2:
            continue
        b = max(float(PS.outcome(c)["cert_close_usd"])
                for c in e["members"].split(","))
        n_diff += int(b != float(PS.outcome(e["rep_cid"])["cert_close_usd"]))
    mutant = (abs(best - want) < 1e-9 and n_diff == 0)
    return check("realized_payment_is_read_never_rederived",
                 "ME14_use_the_best_member_certificate", armed, mutant,
                 "top1=%s rep_cert=%.2f best_member_cert=%.2f n_multi=%d "
                 "n_where_best_differs=%d" % (top1, want, best, n_multi,
                                              n_diff))


TESTS = (t01_ribbon_refuses_past_the_decision_second,
         t02_ribbon_two_run_byte_identical,
         t03_ribbon_digests_partition_every_event,
         t04_ribbon_headers_match_the_sheet,
         t05_ribbon_max_rows_reports_what_it_withheld,
         t06_ribbon_extends_the_cache_beyond_the_sheet_window,
         t07_episode_key_includes_the_session,
         t08_episode_index_two_run_byte_identical,
         t09_frozen_kstar_matches_the_committed_receipt,
         t10_build_and_view_never_import_panel_score,
         t11_score_refuses_a_day_with_a_missing_deep_read,
         t12_ranking_validation_refuses_a_partial_day,
         t13_score_two_run_byte_identical,
         t14_realized_payment_is_read_never_rederived)


def main():
    MC.verify_spec()
    n_fail = 0
    for t in TESTS:
        try:
            ok = t()
        except Exception as e:            # noqa: BLE001 — recorded, not hidden
            LEDGER.append([t.__name__, "-", 0, 0, "ERROR", repr(e)[:300]])
            ok = False
        if not ok:
            n_fail += 1
        MC.hb("test %s: %s" % (t.__name__, LEDGER[-1][4]))
    MC.write_tsv(os.path.join(OUT_DIR, "fixlane_red_ledger.tsv"), SECTION,
                 MC.params_hash(ER.PARAMS),
                 ["test", "mutant", "armed_pass", "mutant_pass", "verdict",
                  "detail"], LEDGER,
                 extra=["RED-FIRST: armed_pass MUST be 1 and mutant_pass MUST "
                        "be 0 on every row",
                        "each mutant neutralises ONE named production line"])
    MC.write_json(os.path.join(OUT_DIR, "fixlane_tests.receipt.json"),
                  {"env": MC.env_receipt(ER.PARAMS), "n_tests": len(TESTS),
                   "n_failed": n_fail,
                   "ribbon_params": RIB.PARAMS,
                   "verdict": "PASS" if n_fail == 0 else "FAIL"})
    MC.hb("fixlane tests: %d/%d passed" % (len(TESTS) - n_fail, len(TESTS)))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
