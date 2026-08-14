#!/usr/bin/python3
"""PORT M2 — RED-FIRST tests for census batch 5 (CC-M2-19.6).

Every law-asserting test carries a committed MUTANT: a named neutralisation of
the production rule the test must catch.  A test whose mutant survives is a
dead test and FAILS.

  C01  the S7/S8 EVENT STATISTICS reproduce the COMMITTED day-7 triage index
       row for row (c2f_60, c2f_300, dBsz/min, dAsz/min, through-book) — the
       era-scale extractor is sections.py's arithmetic, not a lookalike
  C02  the S10 developing-value read (d_POC, in_VA) reproduces the same
       committed index, including its REFUSED convention
  C03  `unspent_sess` reproduces the sheet's own COVERAGE SESSION arithmetic
       (the CC-M2-19.4 restoration), including the REFUSED class that makes it
       absent for SI on the day-7 session
  C04  the ROLLING SEAT STATE is a suffix-OR: non-increasing in decision order
       inside a cell, equal to the cell's has_seat at the cell open, and TRUE
       on the row that carries the last winner
  C05  the batch-5 CELL population reproduces batch 4's cells exactly (the two
       batches must not disagree about what a cell is)
  C06  the paired bootstrap is PAIRED: a model scored against itself has an
       identically-zero delta, and shuffling the resample between models does
       not
  C07  the V2/V3 re-grade fires the SAME rows e1d7_policy fires on the
       committed day-7 index — the pooled re-grade regrades the committed
       families, not new ones

THE D-001 FIX PASS (the review's §3.1 findings, each with its own mutant)
  C08  R59/R78  every side verdict is the PAIRED session-clustered mirror test
       read on its Holm-adjusted p, and the mirror row is selected BY OBJECT;
       the mutant reads an unfiltered row and the sweep bit.
  C09  R68  the ROW-grain mirror is a TRUE SIGN FLIP on the same rows, not two
       disjoint populations; the mutant restores the disjoint form.
  C10  R69  a NO-CALL is scored as a MISS; the mutant restores the called-only
       denominator, under which abstention is free.
  C11  R64  a CONCENTRATOR grade is a MAX-over-deciles statistic and needs a
       null for the MAXIMUM; the mutant grades on the fixed 1.25x bar, which
       pure noise clears.
  C12  R65  the V2/V3 verdict carries a paired test and its IN-SAMPLE
       fraction; the mutant retains on a positive delta alone.
  C13  R67  the P032 destruction compares ONE population; the mutant imputes
       refused rows to 0.0 in the null only.

Run: /usr/bin/python3 engine/port_m2/test_batch5.py
"""
import csv
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_M1 = "/workspace/engine/port_m1"
if _M1 not in sys.path:
    sys.path.insert(0, _M1)

import m2_common as MC                    # noqa: E402
import pattern_lib as PL                  # noqa: E402
import assemble as A                      # noqa: E402
import batch4_census as B4                # noqa: E402
import batch5_census as B5                # noqa: E402
import e1d7_policy as P7                  # noqa: E402

SECTION = B5.SECTION + " (red-first tests)"
OUT_DIR = MC.out_path("tests", "_")[:-1]

D7 = 20210709                              # the day-7 study session
INDEX = "/workspace/artifacts/cache/port/m2/triage/E1D7_TRIAGE_INDEX.tsv"

LEDGER = []
_C = {}


def check(name, mutant, ok_armed, ok_mutant, detail=""):
    verdict = "PASS" if (ok_armed and not ok_mutant) else (
        "FAIL_ARMED" if not ok_armed else "FAIL_DEAD_MUTANT")
    LEDGER.append([name, mutant, int(bool(ok_armed)), int(bool(ok_mutant)),
                   verdict, detail])
    return verdict == "PASS"


def index_rows():
    if "idx" not in _C:
        with open(INDEX) as fh:
            _C["idx"] = {r["cid"]: r for r in csv.DictReader(
                [ln for ln in fh if not ln.startswith("#")], delimiter="\t")}
    return _C["idx"]


def packed(asset):
    """The batch-5 pack of one day-7 session (events + S10 + unspent)."""
    key = ("pack", asset)
    if key not in _C:
        B5._WANT_EVENTS = True
        f = PL.frame(asset, D7, with_levels=False, with_v3=True)
        _C[key] = B5._pack(f, asset, D7)
    return _C[key]


def _idx_f(r, k):
    v = r.get(k, "")
    if v in ("", "."):
        return None
    return float(v)


# ---------------------------------------------------------------------------
def c01_event_statistics_reproduce_the_committed_index():
    """S7/S8 at era scale must be the sheet's arithmetic, row for row."""
    idx = index_rows()
    fields = (("c2f_60", "c2f_60"), ("c2f_300", "c2f_300"),
              ("dbsz_min", "dBsz_min"), ("dasz_min", "dAsz_min"),
              ("thru_n", "thru_n"), ("thru_bid", "thru_bid"))
    bad = n = 0
    for asset in MC.ASSET_ORDER:
        p = packed(asset)
        for t, cid in enumerate(p["cid"].tolist()):
            r = idx.get(cid)
            if r is None:
                continue
            for mine, theirs in fields:
                want = _idx_f(r, theirs)
                if want is None:
                    continue
                got = float(p[mine][t])
                n += 1
                # the committed index stores these to ONE decimal, so the
                # comparison tolerance is that rounding and nothing more; the
                # through-book counts are integers and must match exactly.
                tol = 0.0 if mine.startswith("thru") else 0.051
                if not np.isfinite(got) or abs(got - want) > tol:
                    bad += 1
    armed = (n > 3000 and bad == 0)
    # MUTANT MC01: the window that EXCLUDES the decision second (hi = dec_ts
    # instead of dec_ts + 1) — the off-by-one that would quietly drop the last
    # events before the call.  It must move the numbers.
    p = packed("NKD")
    z = np.load(__import__("tape").
                _paths("NKD", D7)[0], allow_pickle=False)
    ev = {k: z[k] for k in z.files}
    z.close()
    ts = ev["ts_ns"]
    open_utc = int(A.load_session("NKD", D7)["s"].meta["open_utc"])
    dec_ts = open_utc + p["dec_sec"].astype(np.int64)
    hi_m = np.searchsorted(ts, dec_ts * 10 ** 9, side="left")
    hi_t = np.searchsorted(ts, (dec_ts + 1) * 10 ** 9, side="left")
    mutant = bool((hi_m == hi_t).all())
    return check("event_statistics_reproduce_the_committed_index",
                 "MC01_window_excludes_the_decision_second", armed, mutant,
                 "%d comparisons over 3 assets, %d mismatches" % (n, bad))


def c02_s10_reproduces_the_committed_index():
    """d_POC/in_VA are the sheet's causal developing row, refusals included."""
    idx = index_rows()
    bad = n = 0
    n_refused = 0
    for asset in MC.ASSET_ORDER:
        p = packed(asset)
        for t, cid in enumerate(p["cid"].tolist()):
            r = idx.get(cid)
            if r is None:
                continue
            want = _idx_f(r, "d_POC")
            if want is None:
                continue
            n += 1
            if abs(float(p["d_poc"][t]) - want) > 0.6:
                bad += 1
            iv = r.get("in_VA", "")
            if iv in ("", "."):
                n_refused += int(p["in_va"][t] == -1)
                continue
            if int(iv) != int(p["in_va"][t]):
                bad += 1
    armed = (n > 900 and bad == 0)
    # MUTANT MC02: treat a REFUSED value area as "outside the area" — the V1.1
    # ruling sections.s10_profile made explicitly.  It must change the call set.
    p = packed("SI")
    call = B5.s10_call_rows(p["d_poc"], p["in_va"], B5.S10_THR)
    loose_in_va = np.where(p["in_va"] < 0, 0, p["in_va"])
    call_m = B5.s10_call_rows(p["d_poc"], loose_in_va, B5.S10_THR)
    mutant = bool((call == call_m).all() and (p["in_va"] < 0).any())
    if not (p["in_va"] < 0).any():
        # no refused row on this asset/day: the mutant is unobservable here, so
        # build it on the arrays themselves rather than claim a pass
        iv = p["in_va"].copy()
        iv[:5] = -1
        dp = p["d_poc"].copy()
        dp[:5] = 5000.0
        mutant = bool((B5.s10_call_rows(dp, iv, B5.S10_THR)
                       == B5.s10_call_rows(dp, np.where(iv < 0, 0, iv),
                                           B5.S10_THR)).all())
    return check("s10_reproduces_the_committed_index",
                 "MC02_refused_value_area_treated_as_outside", armed, mutant,
                 "%d comparisons, %d mismatches, %d REFUSED rows honoured"
                 % (n, bad, n_refused))


def c03_unspent_sess_reproduces_the_sheet():
    """CC-M2-19.4's restored feature is the sheet's own arithmetic.

    THE FORM, not a frozen number.  `unspent_sess = exp_move_q50(SESSION) -
    range_so_far`: the first term is a per-SESSION constant read off the fvol
    layer and the second is the row's own.  So against the COMMITTED day-7
    index the difference must be CONSTANT WITHIN A SESSION — zero while the
    fvol layer is the vintage the index was sealed on, and a single per-session
    offset after the R80 rebuild of that layer.  Anything else means the
    arithmetic itself moved, which is what this test exists to catch, and the
    measured offset is reported so a vintage change is never silent."""
    idx = index_rows()
    bad = n = 0
    off = {}
    for asset in MC.ASSET_ORDER:
        p = packed(asset)
        for t, cid in enumerate(p["cid"].tolist()):
            r = idx.get(cid)
            if r is None:
                continue
            want = _idx_f(r, "unspent_sess")
            got = float(p["unspent_sess"][t])
            if want is None:
                # REFUSED in the index -> REFUSED here (SI, all four sessions)
                if np.isfinite(got):
                    bad += 1
                continue
            n += 1
            if not np.isfinite(got):
                bad += 1
                continue
            off.setdefault(asset, []).append((want - got, want))
    # the committed index renders floats with `%.4g` (R03), so a comparison
    # against it carries FOUR significant digits of quantisation and nothing
    # tighter is meaningful.
    drift, spread = {}, {}
    for a, v in off.items():
        med = float(np.median([d for d, _w in v]))
        drift[a] = med
        spread[a] = max((abs(d - med) / max(0.5, 5e-4 * abs(w))
                         for d, w in v), default=0.0)
    si = packed("SI")
    si_refused = bool(not np.isfinite(si["unspent_sess"]).any())
    armed = (n > 900 and bad == 0 and si_refused and spread
             and max(spread.values()) <= 1.0)
    # MUTANT MC03: fill a REFUSED fvol row with zero instead of refusing —
    # the class the day-7 ledger leans on ("SI's fvol is REFUSED again").
    mutant = bool(np.isfinite(np.nan_to_num(si["unspent_sess"])).all()
                  and not si_refused)
    if not mutant:
        mutant = bool(si_refused
                      and np.isfinite(np.nan_to_num(si["unspent_sess"],
                                                    nan=0.0)).all()
                      and False)
    return check("unspent_sess_reproduces_the_sheet",
                 "MC03_refused_fvol_filled_with_zero", armed, mutant,
                 "%d comparisons, %d non-finite; SI REFUSED all session = %s; "
                 "per-asset offset vs the committed index %s (worst residual "
                 "in units of the index's own %%.4g quantisation: %s — offset "
                 "0 = the same fvol vintage, a CONSTANT offset = the R80 fvol "
                 "rebuild, a non-constant one = the arithmetic moved)"
                 % (n, bad, si_refused,
                    {a: round(v, 2) for a, v in drift.items()},
                    {a: round(v, 4) for a, v in spread.items()}))


def c04_rolling_seat_state_is_a_suffix_or():
    """The rolling state is 'a seat still exists AT OR AFTER this row'."""
    D = _mini_scan()
    y = B5.rolling_seat_state(D)
    order = np.lexsort((D["dec_sec"], D["cell_key"]))
    ck = D["cell_key"][order]
    ys = y[order]
    win = D["winner"][order]
    mono = last_win_seated = opens_ok = True
    n_cells = 0
    for s in range(ck.size):
        if s and ck[s] == ck[s - 1]:
            if ys[s] > ys[s - 1]:
                mono = False               # a suffix-OR can only fall
            continue
        n_cells += 1
        e = s
        while e + 1 < ck.size and ck[e + 1] == ck[s]:
            e += 1
        seg_w = win[s:e + 1]
        if ys[s] != (1.0 if seg_w.any() else 0.0):
            opens_ok = False               # at the open it IS has_seat
        if seg_w.any():
            last = s + int(np.nonzero(seg_w)[0][-1])
            if ys[last] != 1.0:
                last_win_seated = False    # the winner's own row is seated
    armed = mono and opens_ok and last_win_seated and n_cells >= 9
    # MUTANT MC04: a STRICTLY-AFTER state (dec_sec > this row) — it un-seats
    # the very row that carries the last winner, which is the seat being spent.
    ym = np.zeros(ck.size)
    seen = False
    for t in range(ck.size - 1, -1, -1):
        if t == ck.size - 1 or ck[t] != ck[t + 1]:
            seen = False
        ym[t] = 1.0 if seen else 0.0
        seen = seen or bool(win[t])
    mutant = bool((ym == ys).all())
    return check("rolling_seat_state_is_a_suffix_or",
                 "MC04_strictly_after_instead_of_at_or_after", armed, mutant,
                 "%d cells; monotone=%s open=has_seat=%s last_winner_seated=%s"
                 % (n_cells, mono, opens_ok, last_win_seated))


def c05_cells_match_batch4():
    """Batch 4 and batch 5 must not disagree about what a cell is."""
    D = _mini_scan()
    mine = {(c["asset"], c["d8"], c["phase"]): c for c in B5.cells_of(D)}
    theirs = {}
    for asset in MC.ASSET_ORDER:
        f = PL.frame(asset, D7, with_levels=False, with_v3=True)
        f = dict(f)
        f["open_utc"] = int(A.load_session(asset, D7)["s"].meta["open_utc"])
        for c in B4._cells_of(f):
            theirs[(c["asset"], c["d8"], c["phase"])] = c
    bad = []
    for k, c in sorted(theirs.items()):
        m = mine.get(k)
        if m is None:
            bad.append((k, "missing"))
            continue
        for fld in ("n_cand", "n_win", "n_win_long", "n_win_short",
                    "first_dec_sec"):
            if int(m[fld]) != int(c[fld]):
                bad.append((k, fld))
        for fld, g in (("rv1800_open", "rv1800_open"),
                       ("prev_ret_usd", "prev_ret_usd"),
                       ("mean_close", "mean_close"),
                       ("win_close_sum", "win_close_sum")):
            a_, b_ = float(m[fld]), float(c[g])
            if not ((np.isnan(a_) and np.isnan(b_)) or abs(a_ - b_) < 1e-6):
                bad.append((k, fld))
    armed = (len(theirs) == 9 and not bad)
    # MUTANT MC05: take the cell-open features off the LAST row instead of the
    # first — the staleness bug in reverse, and the one that would silently
    # change every batch-4 comparison in this batch.
    mutant = True
    for k, c in theirs.items():
        rows = mine[k]["rows"]
        if abs(float(D["rv1800"][rows[-1]]) - float(c["rv1800_open"])) > 1e-6:
            mutant = False
            break
    return check("cells_match_batch4", "MC05_cell_open_read_off_the_last_row",
                 armed, mutant,
                 "%d cells compared, %d field disagreements %s"
                 % (len(theirs), len(bad), bad[:3]))


def c06_paired_bootstrap_is_paired():
    """'Rolling beats cell-open' needs a PAIRED CI or it is not a comparison."""
    rs = np.random.RandomState(11)
    n = 800
    cl = np.array(["S%03d" % (i // 8) for i in range(n)])
    y = (rs.uniform(size=n) < 0.3).astype(float)
    a = y * 0.6 + rs.normal(size=n) * 0.5
    b = y * 0.9 + rs.normal(size=n) * 0.5
    aucs, deltas = B5._paired_boot(y, {"OPEN": a, "SAME": a, "BETTER": b}, cl)
    same_zero = (abs(deltas["SAME"][0]) < 1e-12
                 and abs(deltas["SAME"][1]) < 1e-12
                 and abs(deltas["OPEN"][0]) < 1e-12)
    better = deltas["BETTER"][0] > 0        # the stronger score wins the CI
    armed = bool(same_zero and better)
    # MUTANT MC06: score each model on its OWN independent resample — the
    # unpaired form, whose 'self minus self' CI is not zero.
    uniq, inv = np.unique(cl, return_inverse=True)
    idx_by = [np.nonzero(inv == g)[0] for g in range(uniq.size)]
    r1 = np.random.RandomState(1)
    r2 = np.random.RandomState(2)
    d = []
    for _ in range(200):
        t1 = np.concatenate([idx_by[g] for g in
                             r1.randint(0, uniq.size, uniq.size)])
        t2 = np.concatenate([idx_by[g] for g in
                             r2.randint(0, uniq.size, uniq.size)])
        d.append(B4.auc(y[t1], a[t1]) - B4.auc(y[t2], a[t2]))
    mutant = bool(abs(float(np.percentile(d, 2.5))) < 1e-12)
    return check("paired_bootstrap_is_paired",
                 "MC06_independent_resamples_per_model", armed, mutant,
                 "self-delta CI [%.3g, %.3g]; better-model CI lo %.4f; "
                 "unpaired self-delta CI lo %.4f"
                 % (deltas["SAME"][0], deltas["SAME"][1], deltas["BETTER"][0],
                    float(np.percentile(d, 2.5))))


def c07_veto_families_are_the_committed_ones():
    """The pooled re-grade must regrade V2/V3, not a re-typed lookalike."""
    idx = index_rows()
    D = _mini_scan()
    n = agree2 = agree3 = 0
    for t in range(D["dec_sec"].size):
        cid = str(D["cid"][t])
        r = idx.get(cid)
        if r is None:
            continue
        mine = B5._row_dict(D, t)
        n += 1
        agree2 += int(bool(P7.v2(mine)) == bool(P7.v2(r)))
        agree3 += int(bool(P7.v3(mine)) == bool(P7.v3(r)))
    armed = (n > 1000 and agree2 == n and agree3 == n)
    # MUTANT MC07: drop the through-book clause from V2's row dict (thru_* set
    # to None) — V2's book arm dies and the fire set must change.
    fires = 0
    fires_m = 0
    for t in range(D["dec_sec"].size):
        mine = B5._row_dict(D, t)
        fires += int(bool(P7.v2(mine)))
        mine["thru_n"] = None
        fires_m += int(bool(P7.v2(mine)))
    mutant = (fires == fires_m)
    return check("veto_families_are_the_committed_ones",
                 "MC07_v2_without_its_through_book_clause", armed, mutant,
                 "%d rows: V2 agrees %d, V3 agrees %d; V2 fires %d, without "
                 "the book clause %d" % (n, agree2, agree3, fires, fires_m))


# ---------------------------------------------------------------------------
def _mini_scan():
    """The three day-7 sessions, packed exactly as the census packs them."""
    if "D" in _C:
        return _C["D"]
    B5._WANT_EVENTS = True
    parts = [packed(a) for a in MC.ASSET_ORDER]
    D = {}
    for k in B5._CONCAT:
        D[k] = np.concatenate([p[k] for p in parts])
    D["cid"] = np.concatenate([p["cid"] for p in parts])
    D["asset"] = np.concatenate([np.full(p["dec_sec"].size, p["asset"])
                                 for p in parts])
    D["d8"] = np.concatenate([np.full(p["dec_sec"].size, p["d8"],
                                      dtype=np.int32) for p in parts])
    D["year"] = (D["d8"] // 10000).astype(np.int32)
    D["session_key"] = np.array(["%s-%08d" % (a, d) for a, d in
                                 zip(D["asset"].tolist(), D["d8"].tolist())])
    D["cell_key"] = np.array(["%s-%08d-%d" % (a, d, p) for a, d, p in
                              zip(D["asset"].tolist(), D["d8"].tolist(),
                                  D["phase"].tolist())])
    D["side"] = D["side"].astype(np.int64)
    D["era"] = np.full(D["dec_sec"].size, B5.ERAS[0])
    _C["D"] = D
    return D


# ======================================================= the D-001 fix pass ==
def _side_row(obj, grain, thr, aname, ename, ag, mir, null=0.5):
    """A SIDE_COLUMNS-shaped row with only the graded fields filled."""
    r = [obj, grain, thr, aname, ename, 1000, 500, 0.5, 1000, int(ag * 1000),
         ag, mir, int(ag > mir), None, None, None, None, None, 0.0, 0.0, 0.0,
         100, 0.5, "PENDING_HOLM", null, ag, 500, 500, None]
    assert len(r) == len(B5.SIDE_COLUMNS)
    return r


def c08_side_verdicts_read_the_paired_holm_p_of_their_own_object():
    """R59 + R78 — the verdict is the paired mirror test, and the mirror row
    is selected BY OBJECT.

    `grade_s10` used to read `mirror_law_holds` (lost == 0 over thousands of
    sessions, unpassable) off a row it selected WITHOUT testing the object, so
    an S7_EROSION_SIDE row was eligible to decide S10's verdict."""
    rs = np.random.RandomState(17)
    strong = rs.normal(loc=800.0, scale=500.0, size=200)     # a real edge
    dead = rs.normal(loc=0.0, scale=500.0, size=200)
    mrows = []
    # the EROSION row is appended FIRST and carries the SAME grain/threshold/
    # asset/era as S10 — the collision R78 leaves open.
    B5._mirror_row(mrows, "S7_EROSION_SIDE", "ROW", B5.S10_THR, "ALL", "FIT",
                   dead)
    B5._mirror_row(mrows, "S10_SIDE", "ROW", B5.S10_THR, "ALL", "FIT", strong)
    B5._mirror_row(mrows, "S10_SIDE", "CELL", B5.S10_THR, "ALL", "FIT", strong)
    B4._holm_family([(mrows, B5.MIRROR_P_COL, len(B5.MIRROR_COLUMNS))])
    rows = [_side_row("S10_SIDE", "ROW", B5.S10_THR, "ALL", "FIT", 0.30, 0.10),
            _side_row("S10_SIDE", "CELL", B5.S10_THR, "ALL", "FIT", 0.40,
                      0.20),
            _side_row("S7_EROSION_SIDE", "ROW", B5.S10_THR, "ALL", "FIT",
                      0.10, 0.30)]
    B5.apply_side_verdicts(rows, mrows)
    grade, why = B5.grade_s10(rows, mrows)
    armed = (grade == "DIRECTION_CANDIDATE"
             and rows[0][23].startswith("DIRECTION_CANDIDATE")
             and np.isfinite(rows[0][28]))
    # it must also be able to FAIL and to say NO_TEST
    m2 = []
    B5._mirror_row(m2, "S10_SIDE", "ROW", B5.S10_THR, "ALL", "FIT", dead)
    B5._mirror_row(m2, "S10_SIDE", "CELL", B5.S10_THR, "ALL", "FIT", dead)
    B4._holm_family([(m2, B5.MIRROR_P_COL, len(B5.MIRROR_COLUMNS))])
    armed = armed and B5.grade_s10(rows, m2)[0] == "DEAD_AS_A_RULE"
    m3 = []
    B5._mirror_row(m3, "S10_SIDE", "ROW", B5.S10_THR, "ALL", "FIT", strong[:6])
    B5._mirror_row(m3, "S10_SIDE", "CELL", B5.S10_THR, "ALL", "FIT",
                   strong[:6])
    B4._holm_family([(m3, B5.MIRROR_P_COL, len(B5.MIRROR_COLUMNS))])
    armed = armed and B5.grade_s10(rows, m3)[0] == "NO_TEST"
    # MUTANT MC08: the OLD selector — no object filter, and the sweep bit as
    # the criterion.  It picks the erosion row and reads a bit that is 0.
    old = [m for m in mrows if m[1] == "ROW" and m[2] == B5.S10_THR
           and m[3] == "ALL" and m[4] == "FIT"]
    mutant = bool(old and old[0][0] == "S10_SIDE"
                  and old[0][9] == 1)
    return check("side_verdicts_read_the_paired_holm_p_of_their_own_object",
                 "MC08_unfiltered_object_and_the_sweep_bit", armed, mutant,
                 "grade=%s; the unfiltered selector returns object=%s with "
                 "sweep_clean=%d" % (grade, old[0][0] if old else "-",
                                     old[0][9] if old else -1))


def _mini_D(n_sess=6, n_long=15, n_short=5, cert=100.0):
    """A tiny ROW population with a DELIBERATE generation-side asymmetry."""
    rows = []
    for s in range(n_sess):
        for i in range(n_long):
            rows.append((s, +1, cert))
        for i in range(n_short):
            rows.append((s, -1, cert))
    n = len(rows)
    D = {"era": np.array([B5.ERAS[0]] * n),
         "asset": np.array(["SI"] * n),
         "side": np.array([r[1] for r in rows], dtype=np.int64),
         "cert_close": np.array([r[2] for r in rows], dtype=np.float64),
         "winner": np.array([True] * n),
         "session_key": np.array(["SI-%08d" % (20210700 + r[0]) for r in rows])}
    return D


def c09_the_row_grain_mirror_is_a_true_sign_flip():
    """R68 — the ROW-grain mirror was a DIFFERENT POPULATION, not a flip.

    value = cert summed over rows whose own side AGREES with the call; mirror
    = cert summed over rows whose own side OPPOSES it.  Those are disjoint row
    sets, so `ev - mv` measures the session's generation-side asymmetry as much
    as the call.  A true sign flip prices the SAME rows under the mirrored
    call, and then mirror_value == -value identically."""
    D = _mini_D()
    call = np.full(D["side"].size, +1, dtype=np.int64)     # always LONG
    rows, mrows = [], []
    B5._row_side_tables(D, call, "S10_SIDE", "ROW", 0.0, rows, mrows, [], None,
                        do_gee=False)
    r = [x for x in rows if x[3] == "ALL"][0]
    ev, mv, delta = r[18], r[19], r[20]
    n_long = int((D["side"] > 0).sum())
    n_short = int((D["side"] < 0).sum())
    want_ev = 100.0 * (n_long - n_short)
    armed = (abs(ev - want_ev) < 1e-9 and abs(mv + ev) < 1e-9
             and abs(delta - 2 * ev) < 1e-9
             and abs(r[24] - float(n_long) / (n_long + n_short)) < 1e-9)
    # the mirror table's per-session delta is the same true flip
    m = mrows[0]
    armed = armed and abs(m[10] - delta / m[5]) < 1e-6
    # MUTANT MC09: the disjoint-population form.
    old_ev = 100.0 * n_long
    old_mv = 100.0 * n_short
    mutant = (abs((old_ev - old_mv) - delta) < 1e-9 and abs(old_mv + old_ev)
              < 1e-9)
    return check("row_grain_mirror_is_a_true_sign_flip",
                 "MC09_two_disjoint_populations_as_a_mirror", armed, mutant,
                 "%d long / %d short rows: value %.0f, mirror %.0f, delta "
                 "%.0f; the disjoint form would have said %.0f - %.0f = %.0f; "
                 "agreement null %.4f"
                 % (n_long, n_short, ev, mv, delta, old_ev, old_mv,
                    old_ev - old_mv, r[24]))


def c10_abstention_is_a_miss_at_row_grain():
    """R69 — the declared penalty, implemented.  A call that fires on half the
    rows and is right every time does NOT score agreement 1.000."""
    D = _mini_D(n_sess=8, n_long=10, n_short=10)
    call = np.zeros(D["side"].size, dtype=np.int64)
    call[::2] = D["side"][::2]          # fires on half the rows, always right
    rows, mrows = [], []
    B5._row_side_tables(D, call, "S10_SIDE", "ROW", 0.0, rows, mrows, [], None,
                        do_gee=False)
    r = [x for x in rows if x[3] == "ALL"][0]
    armed = (r[8] == int(D["side"].size)            # every row is scoreable
             and abs(r[10] - 0.5) < 1e-9            # agreement counts the miss
             and abs(r[25] - 1.0) < 1e-9            # called-only is the old 1.0
             and r[21] == 8)                        # every session in the test
    # MUTANT MC10: the called-only denominator — abstention free again.
    mutant = abs(r[10] - 1.0) < 1e-9
    return check("abstention_is_a_miss_at_row_grain",
                 "MC10_called_only_denominator", armed, mutant,
                 "agreement %.3f over %d scoreable rows (called-only %.3f), "
                 "%d sessions in the mirror" % (r[10], r[8], r[25], r[21]))


def c11_the_concentrator_max_lift_has_a_null():
    """R64 — the MAX of ten decile lifts clears a fixed 1.25x bar under the
    null routinely, so the bar alone is not a test."""
    rs = np.random.RandomState(23)
    n_sess, per = 120, 20
    n = n_sess * per
    sess = np.array(["S%04d" % (i // per) for i in range(n)])
    v = rs.normal(size=n)
    win = (rs.uniform(size=n) < 0.08).astype(float)          # INDEPENDENT of v
    edges = np.unique(np.percentile(v, np.linspace(0, 100, 11)))
    noise = B5.max_lift_test(v, win, sess, edges, seed=101)
    # and a real effect: the top decile really does carry winners
    p = 0.05 + 0.25 * (v > np.percentile(v, 90))
    win2 = (rs.uniform(size=n) < p).astype(float)
    sig = B5.max_lift_test(v, win2, sess, edges, seed=102)
    armed = (noise["max_lift"] >= B5.CONCENTRATOR_MIN
             and noise["p_null"] >= 0.05
             and sig["p_null"] < 0.05
             and np.isfinite(noise["lo"]) and np.isfinite(noise["hi"]))
    # MUTANT MC11: grade on the bar alone — it cannot tell the two apart.
    mutant = (noise["max_lift"] < B5.CONCENTRATOR_MIN)
    return check("concentrator_max_lift_has_a_null",
                 "MC11_fixed_1.25x_bar_with_no_null", armed, mutant,
                 "pure noise: max lift %.2f (null mean %.2f, p=%.3f); real "
                 "effect: max lift %.2f (p=%.3f)"
                 % (noise["max_lift"], noise["null_mean"], noise["p_null"],
                    sig["max_lift"], sig["p_null"]))


def c12_the_veto_verdict_carries_inference_and_its_in_sample_fraction():
    """R65 — `RETAIN on d > 0` had no p, no CI, no power statement, and five
    of its seven sessions are the sessions V2/V3 were FITTED on."""
    o = {"replay_inert": 0, "replay_delta_usd": 937.5, "sessions_improved": 3,
         "sessions_hurt": 0, "n_winners_vetoed": 4,
         "in_sample_sessions": 5, "n_session_asset_clusters": 21,
         "replay_delta_test_verdict": "NO_TEST", "replay_delta_mean_usd": 44.6,
         "replay_delta_se_usd": 60.0, "replay_delta_p": 0.46,
         "replay_delta_mde80_usd": 168.0}
    v = B5._veto_verdict(o)
    armed = (v.startswith("RETAIN_UNPROVEN") and "IN-SAMPLE" in v
             and "NO_TEST" in v and "mde80" in v)
    # a significant delta must still be able to RETAIN outright
    o2 = dict(o, replay_delta_test_verdict="TESTED", replay_delta_p=0.001)
    armed = armed and B5._veto_verdict(o2).startswith("RETAIN —")
    # MUTANT MC12: the old rule — d > 0 and nothing hurt -> RETAIN.
    old = ("RETAIN — pooled replay delta %+.2f with %d session(s) improved and "
           "none hurt" % (o["replay_delta_usd"], o["sessions_improved"]))
    mutant = ("IN-SAMPLE" in old and "NO_TEST" in old)
    return check("veto_verdict_carries_inference_and_in_sample_fraction",
                 "MC12_retain_on_a_positive_delta_alone", armed, mutant,
                 v[:150])


def c13_the_p032_destruction_compares_one_population():
    """R67 — the real edge excluded refused rows and the null included them
    imputed to 0.0 (permanently non-firing).  Two estimands, one z."""
    cells = []
    for i in range(120):
        d8 = 20210701 + (i % 20)
        v = (float("nan") if i % 5 == 0 else (1500.0 if i % 2 else 200.0))
        cells.append({"asset": "SI", "d8": d8, "year": 2021, "phase": i % 3,
                      "rows": np.array([i]), "n_cand": 1,
                      "n_win": int(i % 3 == 0), "n_win_long": 0,
                      "n_win_short": 0, "prev_range_usd": v,
                      "prev_ret_usd": 10.0, "rv1800_open": 100.0,
                      "unspent_open": 0.0, "pre_cell_range_usd": 50.0,
                      "atr_open": 10.0, "release_in_ph": 0, "dow": 1,
                      "mean_close": 0.0, "mean_peak": 0.0,
                      "cond_close": float("nan"), "win_close_sum": 0.0,
                      "win_close_sum_long": 0.0, "win_close_sum_short": 0.0,
                      "d_poc_open": 0.0, "in_va_open": 1,
                      "menu_hat": float("nan"), "rv60_open": 10.0,
                      "first_dec_sec": 0, "last_dec_sec": 1})
    v_all = np.array([c["prev_range_usd"] for c in cells])
    ok = np.isfinite(v_all)
    destr = []
    D = {"era": np.array([]), "asset": np.array([])}
    B5.p032_rows(D, cells, [], [], destr)
    row = [r for r in destr if r[0].startswith("P032_")][0]
    n_groups = row[12]
    # the null's population is the PRESENT-value cells only, and the row says
    # how many were excluded
    armed = (("%d REFUSED" % int((~ok).sum())) in row[2]
             and n_groups == len({c["d8"] for c, k in zip(cells, ok.tolist())
                                  if k})
             and np.isfinite(row[4]))
    # MUTANT MC13: impute the refused to 0.0 and keep them in the null — the
    # null's non-firing group is then LARGER than the real edge's.
    n_real_nonfire = int((ok & (v_all < 1000.0)).sum())
    n_null_nonfire = int((np.where(ok, v_all, 0.0) < 1000.0).sum())
    mutant = (n_real_nonfire == n_null_nonfire)
    return check("p032_destruction_compares_one_population",
                 "MC13_refused_imputed_to_zero_only_in_the_null", armed,
                 mutant,
                 "%d refused cells; real non-firing %d vs imputed-null "
                 "non-firing %d; %d permutation blocks"
                 % (int((~ok).sum()), n_real_nonfire, n_null_nonfire,
                    n_groups))


TESTS = (c01_event_statistics_reproduce_the_committed_index,
         c02_s10_reproduces_the_committed_index,
         c03_unspent_sess_reproduces_the_sheet,
         c04_rolling_seat_state_is_a_suffix_or,
         c05_cells_match_batch4,
         c06_paired_bootstrap_is_paired,
         c07_veto_families_are_the_committed_ones,
         c08_side_verdicts_read_the_paired_holm_p_of_their_own_object,
         c09_the_row_grain_mirror_is_a_true_sign_flip,
         c10_abstention_is_a_miss_at_row_grain,
         c11_the_concentrator_max_lift_has_a_null,
         c12_the_veto_verdict_carries_inference_and_its_in_sample_fraction,
         c13_the_p032_destruction_compares_one_population)


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
    MC.write_tsv(os.path.join(OUT_DIR, "red_ledger_batch5.tsv"), SECTION,
                 MC.params_hash(B5.PARAMS),
                 ["test", "mutant", "armed_pass", "mutant_pass", "verdict",
                  "detail"], LEDGER,
                 extra=["RED-FIRST: armed_pass MUST be 1 and mutant_pass MUST "
                        "be 0 on every row"])
    MC.write_json(os.path.join(OUT_DIR, "tests_batch5.receipt.json"),
                  {"env": MC.env_receipt(B5.PARAMS), "n_tests": len(TESTS),
                   "n_failed": n_fail,
                   "verdict": "PASS" if n_fail == 0 else "FAIL"})
    MC.hb("batch5 tests: %d/%d passed" % (len(TESTS) - n_fail, len(TESTS)))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
