#!/usr/bin/python3
"""PORT M2 — RED-FIRST tests for census batch 4 (CC-M2-17.5).

Every law-asserting test carries a committed MUTANT: a named neutralisation of
the production rule the test must catch.  A test whose mutant survives is a
dead test and FAILS.

  B01  the multivariate GEE reproduces episode_v2.gee_independence exactly on
       a single regressor (same beta, same CR0/CR1) — the seat model's
       estimator is the batch-1/2/3 estimator, not a new one
  B02  the V3 FUEL MAP reproduces sections.s8_flow's own integers, on the
       session the pattern was born on (SI 2021-07-08 TOKYO = 7,424 / 1,211 /
       8,635, the number quoted in PATTERN_LEDGER P031)
  B03  every cell-open feature is STRICTLY PRIOR to the cell's first decision
       second: a feature read off a LATER row must be caught
  B04  the P031 cross-asset source is strictly prior in WALL-CLOCK time and is
       never the target cell itself
  B05  the holdout quarantine is a FILTER on the job list, not a flag: no cell
       from 2025-07-01 onward can exist in the census population
  B06  AUC is orientation-honest and the walk-forward never trains on its own
       test year

THE D-001 FIX PASS (the review's §3.1 findings, each with its own mutant)
  B07  R59  the era-scale MIRROR LAW is a criterion that can PASS and FAIL:
       a paired session-clustered test with a stated power floor, graded on
       the Holm-adjusted p.  The mutant restores `lost == 0 and won > 0` as
       the grading criterion and must die.
  B08  R60/R61  ONE Holm family over every table that publishes a test, with
       the adjusted p emitted; the mutant runs two disjoint families.
  B09  R69/R74  a NO-CALL is scored as a MISS and refused rv1800 cells are a
       named band; the mutant scores agreement on called cells only and drops
       the refused band, so the shares stop summing to 1.
  B10  R75/R76  the cross-asset freshness window is CALENDAR arithmetic and
       the OWN-asset control survives a one-row cell; the mutant subtracts
       YYYYMMDD integers and rejects a month boundary.
  B11  R66  a permutation block with three items has no null to divide by:
       the degenerate case is DETECTED and the z REFUSED; the mutant divides
       by the sd of a near-constant null anyway.
  B12  R70/R71/R77  imputations are counted, the D-077 DEPLOYABLE reading is
       computed and labelled, and the cell-open claim is measured not asserted.
  B13  R57/R58  the D-058 holdout enumerator REFUSES; the mutant loads them.

Run: /usr/bin/python3 engine/port_m2/test_batch4.py
"""
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
import episode_v2 as EV                   # noqa: E402
import assemble as A                      # noqa: E402
import batch4_census as B4                # noqa: E402

SECTION = B4.SECTION + " (red-first tests)"
OUT_DIR = MC.out_path("tests", "_")[:-1]

# the session P030 and P031 were both born on
BIRTH_ASSET, BIRTH_D8 = "SI", 20210708
# PATTERN_LEDGER.tsv P031, verbatim: "SI TOKYO 7,424/1,211/8,635 (86% above)"
BIRTH_FUEL = (7424, 1211, 8635)

LEDGER = []


def check(name, mutant, ok_armed, ok_mutant, detail=""):
    verdict = "PASS" if (ok_armed and not ok_mutant) else (
        "FAIL_ARMED" if not ok_armed else "FAIL_DEAD_MUTANT")
    LEDGER.append([name, mutant, int(bool(ok_armed)), int(bool(ok_mutant)),
                   verdict, detail])
    return verdict == "PASS"


_F = {}


def birth_frame():
    if "f" not in _F:
        _F["f"] = PL.frame(BIRTH_ASSET, BIRTH_D8, with_v3=True)
    return _F["f"]


# ---------------------------------------------------------------------------
def b01_gee_multi_matches_the_committed_estimator():
    """The seat model needs p regressors; it must not need a new estimator."""
    rs = np.random.RandomState(7)
    n = 600
    cl = np.repeat(np.arange(60), 10)
    x = rs.normal(size=n)
    y = (rs.uniform(size=n) < 1.0 / (1.0 + np.exp(-(0.4 * x - 0.2)))).astype(
        float)
    a = EV.gee_independence(y, x, cl, link="logit")
    b = B4.gee_multi(y, x[:, None], cl, link="logit")
    same = (abs(a["beta"] - b["beta"][1]) < 1e-9
            and abs(a["se_cr0"] - b["se_cr0"][1]) < 1e-9
            and abs(a["se_cr1"] - b["se_cr1"][1]) < 1e-9
            and a["n_clusters"] == b["n_clusters"])
    # identity link too, since the value GEEs use it
    ai = EV.gee_independence(y, x, cl, link="identity")
    bi = B4.gee_multi(y, x[:, None], cl, link="identity")
    same = same and abs(ai["beta"] - bi["beta"][1]) < 1e-9 \
        and abs(ai["se_cr1"] - bi["se_cr1"][1]) < 1e-9
    # MUTANT MB01: the naive (model-based) SE passed off as the robust one.
    # Under clustering it is materially smaller, so it cannot match.
    mutant = abs(a["se_cr1"] - a["se_naive"]) < 1e-9
    return check("gee_multi_matches_committed_estimator",
                 "MB01_naive_se_as_robust", same, mutant,
                 "beta %.9f vs %.9f; se_cr1 %.9f vs %.9f; naive %.9f"
                 % (a["beta"], b["beta"][1], a["se_cr1"], b["se_cr1"][1],
                    a["se_naive"]))


def b02_fuel_map_reproduces_the_sheet():
    """The V3 fuel map is sections.s8_flow's integers, not an approximation."""
    f = birth_frame()
    ph = f["phase_dec"].astype(np.int64)
    dec = f["dec_sec"].astype(np.int64)
    m = np.nonzero(ph == 0)[0]                       # TOKYO
    last = m[np.argmax(dec[m])]
    got = (int(f["fuel_above"][last]), int(f["fuel_below"][last]),
           int(f["fuel_total"][last]))
    # and against the naive per-candidate scan on a spread of rows
    sess = A.load_session(BIRTH_ASSET, BIRTH_D8)
    tr = sess["trades"]
    ts, tp, tz = tr["sec"], tr["px_f"].astype(np.float64), \
        tr["size"].astype(np.int64)
    r = A.roster(BIRTH_ASSET)
    sel = np.nonzero(r["date8"] == BIRTH_D8)[0]
    em = r["entry_mid"][sel].astype(np.float64)
    bad = 0
    n_check = 0
    for t in range(0, f["n"], 23):
        d, p0, mid = int(dec[t]), int(f["phase_seg_start"][t]), float(em[t])
        w = (ts >= p0) & (ts < d)
        naive = (int(tz[w][tp[w] > mid].sum()), int(tz[w][tp[w] < mid].sum()),
                 int(tz[w].sum()))
        mine = (int(f["fuel_above"][t]), int(f["fuel_below"][t]),
                int(f["fuel_total"][t]))
        n_check += 1
        bad += (naive != mine)
    armed = (got == BIRTH_FUEL) and bad == 0
    # MUTANT MB02: the fuel map read at the CELL OPEN instead of the cell
    # CLOSE.  P031's source is the COMPLETED phase; an open-row reading has
    # almost no volume behind it and cannot reproduce the ledger's numbers.
    first = m[np.argmin(dec[m])]
    mutant = (int(f["fuel_above"][first]), int(f["fuel_below"][first]),
              int(f["fuel_total"][first])) == BIRTH_FUEL
    return check("fuel_map_reproduces_the_sheet", "MB02_read_at_cell_open",
                 armed, mutant,
                 "SI/TOKYO 2021-07-08 close = %s (ledger %s); %d/%d rows "
                 "match the naive scan" % (got, BIRTH_FUEL, n_check - bad,
                                           n_check))


def b03_cell_open_features_are_strictly_prior():
    """Every seat-model feature is read off the cell's FIRST row."""
    f = birth_frame()
    dec = f["dec_sec"].astype(np.int64)
    ph = f["phase_dec"].astype(np.int64)
    ok = True
    detail = []
    for p in sorted(set(ph.tolist())):
        m = np.nonzero(ph == p)[0]
        first = m[np.argmin(dec[m])]
        # the frame's own cell key must agree with the recomputed first row
        if not bool(f["cell_open"][first]):
            ok = False
        if int(f["cell_first_dec_sec"][m][0]) != int(dec[first]):
            ok = False
        if int(f["cell_open"][m].sum()) != 1:
            ok = False
        # pre_cell_range is measured over [0, phase_seg_start) — it cannot
        # know anything inside the cell
        if int(f["phase_seg_start"][first]) > int(dec[first]):
            ok = False
        detail.append("%s:first=%d" % (B4.PHASES[p], int(dec[first])))
    # the previous-phase fields must be constant inside a phase segment (they
    # are a property of the segment, not of the candidate)
    for p in sorted(set(ph.tolist())):
        m = np.nonzero(ph == p)[0]
        v = f["prev_phase_ret_usd"][m]
        v = v[np.isfinite(v)]
        if v.size and not np.allclose(v, v[0]):
            ok = False
    # MUTANT MB03: read the feature off the cell's LAST row instead (the
    # classic look-ahead).  On this session the two differ, so a census built
    # that way would carry the phase's own outcome into its predictor.
    mutant = True
    for p in sorted(set(ph.tolist())):
        m = np.nonzero(ph == p)[0]
        first, last = m[np.argmin(dec[m])], m[np.argmax(dec[m])]
        if float(f["rv1800_usd"][first]) != float(f["rv1800_usd"][last]):
            mutant = False                # the mutant IS detectable -> good
    return check("cell_open_features_strictly_prior",
                 "MB03_read_at_cell_close", ok, mutant, "; ".join(detail))


def b04_cross_asset_source_is_prior_and_foreign():
    """P031's source closed BEFORE the target opened, in wall-clock seconds."""
    cells, _ns, _nq = B4.scan(workers=2, limit_sessions=12)
    src = B4.attach_cross_asset(cells)
    n_pairs = 0
    bad_time = 0
    bad_self = 0
    for c in cells:
        for a2, s2 in src[(c["asset"], c["d8"], c["phase"])].items():
            n_pairs += 1
            if s2["close_ts"] > c["open_ts"]:
                bad_time += 1
            if (s2["asset"], s2["d8"], s2["phase"]) == \
               (c["asset"], c["d8"], c["phase"]):
                bad_self += 1
    armed = n_pairs > 0 and bad_time == 0 and bad_self == 0
    # MUTANT MB04: join on the PHASE NAME instead of wall-clock — "SI TOKYO
    # feeds HG TOKYO" — which on these grids picks sources that had not closed
    # when the target opened.
    bad_naive = 0
    by = {}
    for c in cells:
        by.setdefault((c["asset"], c["d8"], c["phase"]), c)
    for c in cells:
        for a2 in MC.ASSET_ORDER:
            s2 = by.get((a2, c["d8"], c["phase"]))
            if s2 is not None and s2 is not c and s2["close_ts"] > c["open_ts"]:
                bad_naive += 1
    mutant = (bad_naive == 0)
    return check("cross_asset_source_prior_and_foreign",
                 "MB04_join_on_phase_name", armed, mutant,
                 "%d source pairs, %d non-prior, %d self; the phase-name join "
                 "would admit %d non-prior sources"
                 % (n_pairs, bad_time, bad_self, bad_naive))


def b05_holdout_is_never_loaded():
    """CC-M2-15.3: 2025-07-01 onward is quarantined by the JOB LIST."""
    cells, n_sessions, n_quar = B4.scan(workers=2, limit_sessions=12)
    leaked = [c for c in cells if c["d8"] >= B4.HOLDOUT_FROM_D8]
    # the quarantine must be real, not vacuous: the roster HAS such sessions
    have = 0
    for a in MC.ASSET_ORDER:
        have += sum(1 for d in PL.sessions(a, years={B4.GATE_YEAR},
                                           allow_holdout=True)
                    if int(d) >= B4.HOLDOUT_FROM_D8)
    armed = (not leaked) and n_quar > 0 and have > 0
    # MUTANT MB05: quarantine as a REPORTING FLAG — load them and mark the era.
    # The rows exist in the population, which is the exposure CC-M2-15.3 stops.
    mutant = have == 0
    return check("holdout_is_never_loaded", "MB05_quarantine_as_a_flag",
                 armed, mutant,
                 "%d cells over %d sessions; %d holdout sessions refused; the "
                 "roster carries %d of them" % (len(cells), n_sessions,
                                                n_quar, have))


def b06_walk_forward_never_trains_on_its_test_year():
    """The AUC scopes are strictly expanding, and AUC is orientation-honest."""
    y = np.array([0., 0., 1., 1.])
    perfect = np.array([0.1, 0.2, 0.8, 0.9])
    armed = (abs(B4.auc(y, perfect) - 1.0) < 1e-12
             and abs(B4.auc(y, -perfect) - 0.0) < 1e-12
             and abs(B4.auc(y, np.ones(4)) - 0.5) < 1e-12)
    # the scope construction itself: rebuild it and assert the year sets
    fake = [{"year": yr, "asset": "SI", "d8": yr * 10000 + 101, "n_win": 0}
            for yr in B4.FIT_YEARS for _ in range(300)]
    leaks = 0
    for yr in B4.FIT_YEARS:
        tr = [c for c in fake if c["year"] in B4.FIT_YEARS and c["year"] < yr]
        te = [c for c in fake if c["year"] == yr]
        if any(c["year"] >= yr for c in tr) or any(c["year"] != yr
                                                   for c in te):
            leaks += 1
    armed = armed and leaks == 0
    # MUTANT MB06: `<=` instead of `<` in the training filter — the classic
    # walk-forward leak, and the same mutant test_regime.t04 carries.
    mleaks = 0
    for yr in B4.FIT_YEARS:
        tr = [c for c in fake if c["year"] in B4.FIT_YEARS and c["year"] <= yr]
        if any(c["year"] >= yr for c in tr):
            mleaks += 1
    mutant = (mleaks == 0)
    return check("walk_forward_never_trains_on_test_year",
                 "MB06_train_includes_the_cutoff_year", armed, mutant,
                 "%d scopes, %d leaks; the <= mutant leaks in %d"
                 % (len(B4.FIT_YEARS), leaks, mleaks))


# ======================================================= the D-001 fix pass ==
def _cell(asset="SI", d8=20210701, phase=0, wl=0.0, ws=0.0, rv=200.0,
          n_cand=4, mins=None):
    """A minimal CELL for the estimator tests (the fields the graders read)."""
    n_wl = 1 if wl > 0 else 0
    n_ws = 1 if ws > 0 else 0
    return {"asset": asset, "d8": d8, "year": d8 // 10000, "phase": phase,
            "n_cand": n_cand, "n_win": n_wl + n_ws,
            "n_win_long": n_wl, "n_win_short": n_ws,
            "win_close_sum_long": wl, "win_close_sum_short": ws,
            "win_close_sum": wl + ws, "win_close_sum_deploy": wl + ws,
            "n_win_deploy": n_wl + n_ws, "n_cand_news": 0, "n_win_news": 0,
            "seat_on_first_row": 0, "rv1800_open": rv,
            "mean_close": (wl + ws) / max(n_cand, 1), "mean_peak": 0.0,
            "cond_close": float("nan"),
            "mins_to_release_open": (float("nan") if mins is None
                                     else float(mins)),
            "close_fuel_above": 900, "close_fuel_below": 100,
            "close_fuel_total": 1000, "open_ts": 0, "close_ts": 0}


def b07_the_mirror_law_is_a_criterion_that_can_pass_and_fail():
    """R59 — the era-scale mirror law is a PAIRED TEST, not a clean sweep.

    `lost == 0 and won > 0` over thousands of sessions is unpassable, and it
    was the only bit `grade_p031` read.  A real, strong, session-clustered
    directional edge with a handful of losing sessions MUST be able to reach
    DIRECTION_CANDIDATE; the old criterion cannot let it."""
    rs = np.random.RandomState(3)
    n = 200
    d = rs.normal(loc=900.0, scale=600.0, size=n)      # a real +$900 edge
    r = MC.mirror_paired(d)
    null = MC.mirror_paired(rs.normal(loc=0.0, scale=600.0, size=n))
    powered = (r["verdict"] == "TESTED" and r["p"] < 0.05 and r["holds"] == 1
               and r["n_lost"] > 0 and r["sweep_clean"] == 0
               and null["holds"] == 0 and null["verdict"] == "TESTED"
               and np.isfinite(r["mde_80"]))
    # and the GRADER itself: build one mirror row + one pairs row and grade
    mrow = B4.mirror_row([B4.P031_THR, "ANY_OTHER", "ALL", "CROSS_BEST",
                          "FIT"], d)
    B4._holm_family([([mrow], B4.MIRROR_P_COL, len(B4.MIRROR_COLUMNS))])
    prow = [B4.P031_THR, "ANY_OTHER", "ALL", "CROSS_BEST", "FIT", 100, 80, 0.8,
            80, 60, 0.75, 0.20, 1, n, 0.01, 1.0, -1.0, 2.0, "-"] \
        + [None] * 7 + ["-", 5, 0.75, None]
    grade, why = B4.grade_p031([prow], [mrow])
    armed = bool(powered and grade == "DIRECTION_CANDIDATE")
    # and it must still be able to FAIL: the same grader on the null
    mnull = B4.mirror_row([B4.P031_THR, "ANY_OTHER", "ALL", "CROSS_BEST",
                           "FIT"], rs.normal(0.0, 600.0, n))
    B4._holm_family([([mnull], B4.MIRROR_P_COL, len(B4.MIRROR_COLUMNS))])
    armed = armed and B4.grade_p031([prow], [mnull])[0] != "DIRECTION_CANDIDATE"
    # and an UNPOWERED cell is NO_TEST, never a negative
    mfew = B4.mirror_row([B4.P031_THR, "ANY_OTHER", "ALL", "CROSS_BEST",
                          "FIT"], d[:5])
    B4._holm_family([([mfew], B4.MIRROR_P_COL, len(B4.MIRROR_COLUMNS))])
    armed = armed and B4.grade_p031([prow], [mfew])[0] == "NO_TEST"
    # MUTANT MB07: restore `lost == 0 and won > 0` as the GRADING criterion.
    # On a genuine +$900/session edge it is still 0, so DIRECTION_CANDIDATE
    # becomes unreachable — the defect R59 names.
    mutant = bool(MC.mirror_sweep_clean(r["n_won"], r["n_lost"]))
    return check("mirror_law_is_a_criterion_that_can_pass_and_fail",
                 "MB07_sweep_clean_restored_as_the_grading_criterion",
                 armed, mutant,
                 "n=%d won=%d lost=%d mean=%.1f p=%.2g mde80=%.1f -> %s; "
                 "sweep_clean=%d" % (r["n_sessions"], r["n_won"], r["n_lost"],
                                     r["mean_delta"], r["p"], r["mde_80"],
                                     grade, r["sweep_clean"]))


def b08_one_holm_family_and_the_label_matches():
    """R60/R61 — ONE family over every table that publishes a test."""
    # two tables, the shapes the census actually corrects
    # the model p's are never significant; the mirror family carries ONE p
    # that survives its own table alone (0.0040 <= 0.05/10) and dies in the
    # pooled family (0.0040 > 0.05/20) — the exact difference R61 is about.
    model = [["BASE", "ALL", "FIT", "t%d" % i] + [0.0] * 5
             + [0.30 + 0.01 * i] + [0.0] * 5 + [0]
             for i in range(10)]
    mirror = [[0.65, "SI", "SI", "OWN", "FIT", 100, 50, 0, 50, 0, 10.0, 1.0,
               1.0, 2.0, 0.0040 + 0.05 * i, 0.5, 5.0, 30, "TESTED", 1]
              for i in range(10)]
    m = B4._holm_family([(model, B4.MODEL_P_COL, len(B4.MODEL_COLUMNS)),
                         (mirror, B4.MIRROR_P_COL, len(B4.MIRROR_COLUMNS))])
    pooled_sig = sum(1 for r in model + mirror
                     if r[-2] == "HOLM_SIGNIFICANT")
    every_row_has_a_verdict = all(len(r) == len(B4.MODEL_COLUMNS)
                                  for r in model) and \
        all(len(r) == len(B4.MIRROR_COLUMNS) for r in mirror)
    adjusted_present = all(np.isfinite(r[-1]) for r in model + mirror)
    armed = (m == 20 and every_row_has_a_verdict and adjusted_present)
    # MUTANT MB08: two DISJOINT families, one per table — the state R61 found.
    model2 = [r[:len(B4.MODEL_COLUMNS) - B4.HOLM_TAIL] for r in model]
    mirror2 = [r[:len(B4.MIRROR_COLUMNS) - B4.HOLM_TAIL] for r in mirror]
    m1 = B4._holm_family([(model2, B4.MODEL_P_COL, len(B4.MODEL_COLUMNS))])
    m2 = B4._holm_family([(mirror2, B4.MIRROR_P_COL, len(B4.MIRROR_COLUMNS))])
    split_sig = sum(1 for r in model2 + mirror2 if r[-2] == "HOLM_SIGNIFICANT")
    mutant = (m1 + m2 == m and split_sig == pooled_sig)
    return check("one_holm_family_and_the_label_matches",
                 "MB08_two_disjoint_families_one_per_table", armed, mutant,
                 "pooled m=%d (%d significant); split m=%d+%d (%d significant)"
                 % (m, pooled_sig, m1, m2, split_sig))


def b09_abstention_is_a_miss_and_refusals_are_counted():
    """R69 (abstention is not free) + R74 (refused rv1800 is a named band)."""
    # 40 cells, all with a realised winner majority; the source calls on only
    # half of them, and the calls it does make are RIGHT.
    cells, src = [], {}
    for i in range(40):
        c = _cell(d8=20210700 + i + 1, phase=i % 3, wl=1000.0,
                  rv=(float("nan") if i < 8 else 200.0))
        cells.append(c)
        key = (c["asset"], c["d8"], c["phase"])
        # a LONG call is +1: trapped BELOW -> shorts must cover
        src[key] = ({"SI": {"close_fuel_above": 0, "close_fuel_below": 1000,
                            "close_fuel_total": 1000}} if i % 2 == 0 else {})
    rows = B4.pair_rows(cells, src, [], [], full=False)
    r = [x for x in rows if x[1] == "SI" and x[2] == "SI" and x[4] == "FIT"]
    armed = bool(r)
    if armed:
        r = r[0]
        # agreement counts the 20 NO-CALL cells as misses; the old number is
        # kept beside it and is 1.0
        armed = (abs(r[10] - 0.5) < 1e-9 and abs(r[28] - 1.0) < 1e-9
                 and r[27] == 20 and r[8] == 40)
    bands = B4.band_rows(cells, [])
    ball = [b for b in bands if b[0] == "ALL" and b[1] == "FIT"]
    share = sum(b[6] for b in ball)
    refused = [b for b in ball if b[2] == B4.BAND_REFUSED]
    armed = bool(armed and abs(share - 1.0) < 1e-9 and refused
                 and refused[0][5] == 8 and ball[0][21] == 8)
    # MUTANT MB09: score agreement on the CALLED cells only and drop the
    # refused band — the two states R69 and R74 describe.  Then abstention is
    # free (agreement 1.000) and the band shares no longer sum to 1.
    mutant = (abs(r[28] - 0.5) < 1e-9
              or abs(sum(b[6] for b in ball if b[2] != B4.BAND_REFUSED)
                     - 1.0) < 1e-9)
    return check("abstention_is_a_miss_and_refusals_are_counted",
                 "MB09_called_only_denominator_and_dropped_refused_band",
                 armed, mutant,
                 "agreement %.3f over %d scoreable (%d no-call); called-only "
                 "%.3f; band shares sum %.6f with %d refused cells"
                 % (r[10], r[8], r[27], r[28], share,
                    refused[0][5] if refused else -1))


def b10_freshness_is_calendar_arithmetic_and_the_own_leg_survives():
    """R75 (YYYYMMDD subtraction) + R76 (the one-row cell's OWN leg)."""
    # SI closes on 2021-07-30, HG opens on 2021-08-02: two calendar days.
    a = B4._cell(asset="SI", d8=20210730) if hasattr(B4, "_cell") else None
    gap = B4._day_gap(20210730, 20210801)
    armed = (gap == 2 and gap <= B4.P031_SRC_MAX_AGE_DAYS
             and B4._day_gap(20210701, 20210706) == 5)
    # the OWN leg on a ONE-ROW cell: close_ts == open_ts, so the searchsorted
    # lands on the target itself and must step BACK, not abandon the leg.
    c1 = _cell(asset="SI", d8=20210701, phase=0)
    c2 = _cell(asset="SI", d8=20210701, phase=1)
    c1["open_ts"], c1["close_ts"] = 100, 100          # one-row cell
    c2["open_ts"], c2["close_ts"] = 200, 300
    src = B4.attach_cross_asset([c1, c2])
    own = src[("SI", 20210701, 1)].get("SI")
    armed = armed and (own is not None and own is c1)
    # MUTANT MB10: the old YYYYMMDD subtraction rejects the month boundary.
    mutant = (abs(20210801 - 20210730) <= B4.P031_SRC_MAX_AGE_DAYS)
    return check("freshness_is_calendar_arithmetic_and_own_leg_survives",
                 "MB10_yyyymmdd_subtraction_as_a_day_gap", armed, mutant,
                 "calendar gap 20210730->20210801 = %d day(s); the YYYYMMDD "
                 "difference is %d; own-leg source on the one-row cell = %s"
                 % (gap, abs(20210801 - 20210730),
                    "kept" if own is not None else "DROPPED"))


def b11_the_destruction_null_refuses_a_degenerate_block():
    """R66 — a 3-item permutation block cannot produce a null to divide by."""
    rs = np.random.RandomState(5)
    # 300 sessions x 3 cells: the within-session block holds three values
    groups = np.repeat(np.array(["S%03d" % i for i in range(300)]), 3)
    fire = np.tile(np.array([True, False, False]), 300)
    ng, med, ninfo = B4.perm_support(groups, fire)
    # a null that barely moves: 40 reps of a near-constant statistic
    null = [0.10 + 1e-9 * (i % 3) for i in range(40)]
    row = B4._destr_row("P030_test", "FIT", "rv (within session)", 0.30, null,
                        block="SESSION", groups=groups, fire=fire, thr=150.0)
    armed = (med == 3.0 and row[10].startswith("DEGENERATE_NULL")
             and not np.isfinite(row[9]))
    # a null WITH support must still produce a z and a real verdict
    good = list(rs.normal(0.0, 0.05, 40))
    g_groups = np.repeat(np.array(["W%02d" % i for i in range(30)]), 30)
    g_fire = rs.uniform(size=g_groups.size) < 0.4
    grow = B4._destr_row("P030_test", "FIT", "rv (within week)", 0.30, good,
                         block="ASSET_WEEK", groups=g_groups, fire=g_fire,
                         thr=150.0)
    armed = armed and np.isfinite(grow[9]) and grow[10] in (
        "SURVIVES", "DESTROYED", "INVERTED")
    # MUTANT MB11: divide by the sd of the near-constant null anyway.
    n = np.array(null)
    z_naive = (0.30 - n.mean()) / n.std(ddof=1)
    mutant = bool(not np.isfinite(z_naive))
    return check("destruction_null_refuses_a_degenerate_block",
                 "MB11_emit_a_z_over_a_near_constant_null", armed, mutant,
                 "%d blocks, median size %.1f, %d informative -> %s; the naive "
                 "z would have been %.1f" % (ng, med, ninfo, row[10][:24],
                                             z_naive))


def b12_imputation_and_the_deployable_reading_are_declared():
    """R71 (imputation counted) + R77 (the D-077 split) + R70 (the honest
    cell-open claim is MEASURED, not asserted)."""
    Xm = np.array([[1.0, np.nan], [2.0, 2.0], [np.nan, 3.0], [4.0, 4.0]])
    cnt, by = B4.imputed_counts(Xm, ("a", "b"))
    armed = (by == {"a": 1, "b": 1} and int(cnt.sum()) == 2)
    # the DEPLOYABLE reading: a cell whose only winner sits inside the
    # restricted window carries NO deployable seat
    c = _cell(wl=1200.0)
    c["n_win_news"], c["n_win_deploy"], c["win_close_sum_deploy"] = 1, 0, 0.0
    armed = armed and (B4.has_seat_of(c, "SCIENCE") == 1
                       and B4.has_seat_of(c, "DEPLOYABLE") == 0)
    base = B4.base_rate_rows([c, _cell(d8=20210702, wl=1500.0)], [])
    readings = {r[17] for r in base}
    armed = armed and readings == set(B4.READINGS)
    # R70: the claim is now a measured count, and PARAMS says so
    armed = armed and ("CONTEMPORANEOUS" in B4.PARAMS["cell_open"].upper())
    # MUTANT MB12: the docstring's old claim — imputation "recorded" with
    # nothing recorded, and one unlabelled reading.
    mutant = (int(cnt.sum()) == 0 or len(readings) == 1
              or B4.has_seat_of(c, "DEPLOYABLE") == 1)
    return check("imputation_and_deployable_reading_are_declared",
                 "MB12_undeclared_imputation_and_one_unlabelled_reading",
                 armed, mutant,
                 "imputed %s; seat SCIENCE=%d DEPLOYABLE=%d; readings %s"
                 % (by, B4.has_seat_of(c, "SCIENCE"),
                    B4.has_seat_of(c, "DEPLOYABLE"), sorted(readings)))


def b13_the_holdout_enumerator_refuses():
    """R57/R58 — the D-058 boundary is a REFUSAL in the enumerator itself."""
    raised = 0
    have = 0
    for a in MC.ASSET_ORDER:
        try:
            PL.sessions(a, years={B4.GATE_YEAR})
        except MC.HoldoutRefusal:
            raised += 1
        keep, nq = PL.sessions_fit(a, years={B4.GATE_YEAR})
        have += nq
        if any(MC.in_holdout(d) for d in keep):
            raised = -99
    armed = (raised == len(MC.ASSET_ORDER) and have > 0)
    # MUTANT MB13: load them anyway (allow_holdout=True) — the population then
    # CONTAINS holdout sessions, which is the exposure D-058 forbids.
    leaked = 0
    for a in MC.ASSET_ORDER:
        leaked += sum(1 for d in PL.sessions(a, years={B4.GATE_YEAR},
                                             allow_holdout=True)
                      if MC.in_holdout(d))
    mutant = (leaked == 0)
    return check("holdout_enumerator_refuses", "MB13_allow_holdout_enumeration",
                 armed, mutant,
                 "%d/%d assets refuse a holdout-bearing year; %d sessions "
                 "quarantined; the unguarded enumerator would admit %d"
                 % (raised, len(MC.ASSET_ORDER), have, leaked))


TESTS = (b01_gee_multi_matches_the_committed_estimator,
         b02_fuel_map_reproduces_the_sheet,
         b03_cell_open_features_are_strictly_prior,
         b04_cross_asset_source_is_prior_and_foreign,
         b05_holdout_is_never_loaded,
         b06_walk_forward_never_trains_on_its_test_year,
         b07_the_mirror_law_is_a_criterion_that_can_pass_and_fail,
         b08_one_holm_family_and_the_label_matches,
         b09_abstention_is_a_miss_and_refusals_are_counted,
         b10_freshness_is_calendar_arithmetic_and_the_own_leg_survives,
         b11_the_destruction_null_refuses_a_degenerate_block,
         b12_imputation_and_the_deployable_reading_are_declared,
         b13_the_holdout_enumerator_refuses)


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
    MC.write_tsv(os.path.join(OUT_DIR, "red_ledger_batch4.tsv"), SECTION,
                 MC.params_hash(B4.PARAMS),
                 ["test", "mutant", "armed_pass", "mutant_pass", "verdict",
                  "detail"], LEDGER,
                 extra=["RED-FIRST: armed_pass MUST be 1 and mutant_pass MUST "
                        "be 0 on every row"])
    MC.write_json(os.path.join(OUT_DIR, "tests_batch4.receipt.json"),
                  {"env": MC.env_receipt(B4.PARAMS), "n_tests": len(TESTS),
                   "n_failed": n_fail,
                   "verdict": "PASS" if n_fail == 0 else "FAIL"})
    MC.hb("batch4 tests: %d/%d passed" % (len(TESTS) - n_fail, len(TESTS)))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
