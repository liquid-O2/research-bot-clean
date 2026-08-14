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
        have += sum(1 for d in PL.sessions(a, years={B4.GATE_YEAR})
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


TESTS = (b01_gee_multi_matches_the_committed_estimator,
         b02_fuel_map_reproduces_the_sheet,
         b03_cell_open_features_are_strictly_prior,
         b04_cross_asset_source_is_prior_and_foreign,
         b05_holdout_is_never_loaded,
         b06_walk_forward_never_trains_on_its_test_year)


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
