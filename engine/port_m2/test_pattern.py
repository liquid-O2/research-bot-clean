#!/usr/bin/python3
"""PORT M2 — red-first tests for the pattern substrate, the P001 detector and
the reference-class retrieval tool.

Same law as test_m2.py: every test that asserts a LAW carries a committed
MUTANT — a named neutralised line of the production rule that the test MUST
catch.  A test whose mutant survives is a dead test and fails.  The red ledger
is written to artifacts/cache/port/m2/tests/pattern_red_ledger.tsv.

Run: /usr/bin/python3 engine/port_m2/test_pattern.py
"""
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import assemble as A                      # noqa: E402
import sections as SEC                    # noqa: E402
import pattern_lib as PL                  # noqa: E402
import p001_census as P1                  # noqa: E402
import retrieve as R                      # noqa: E402
import used_cases as UC                   # noqa: E402

SECTION = "§CC-M2-5 retrieval + §4.2 P001 detector (red-first)"
OUT_DIR = MC.out_path("tests", "_")[:-1]

# The P-M2c warm-up's own P001 support/near-miss cases: committed sheets exist
# for all five, so the renderer cross-check has a real fixture.
FIXTURES = ("HG-20210701-052246-S", "HG-20210701-055858-S",
            "HG-20210929-052330-S", "HG-20210929-058037-S",
            "HG-20210929-066533-S")
CAUSALITY_CID = "HG-20210929-052330-S"    # phase H is 1236s old at decision

LEDGER = []


def check(name, mutant, ok_armed, ok_mutant, detail=""):
    verdict = "PASS" if (ok_armed and not ok_mutant) else (
        "FAIL_ARMED" if not ok_armed else "FAIL_DEAD_MUTANT")
    LEDGER.append([name, mutant, int(bool(ok_armed)), int(bool(ok_mutant)),
                   verdict, detail])
    return verdict == "PASS"


class _Put(object):
    """Captures what a section renderer publishes to the sidecar."""

    def __init__(self):
        self.vals = {}
        self.refused = {}

    def __call__(self, key, value, source, source_key):
        self.vals[key] = value

    def refuse(self, key, why):
        self.refused[key] = why


def _at(f, cid):
    return int(np.nonzero(f["cid"] == cid)[0][0])


# ---------------------------------------------------------------- t01 ------
def t01_frame_matches_the_renderer():
    """MT_P01: the frame's COVERAGE must be the PHASE forecast, not the session.

    LAW (D-006 formula fidelity): pattern_lib is the vectorised form of
    sections.py, so every shared quantity must agree candidate by candidate.
    """
    import census_common as X
    ok_cov = ok_lad = ok_slope = True
    mut = True
    detail = []
    for cid in FIXTURES:
        asset, d8, _s, _sd = MC.parse_cid(cid)
        f = PL.frame(asset, d8)
        t = _at(f, cid)
        case = A.Case(cid, MC.MODE_BLIND, want_events=False)
        put = _Put()
        SEC.s3_path(case, put)
        put9 = _Put()
        SEC.s9_vol(case, put9)
        seg = X.PHASE_NAMES[case.phase_dec]
        cov_r = put.vals.get("S3.coverage_%s" % seg)
        cov_f = float(f["coverage_phase"][t])
        if cov_r is None:
            ok_cov &= not np.isfinite(cov_f)
        else:
            ok_cov &= abs(float(cov_r) - cov_f) < 1e-9
        lad_r = put9.vals.get("S9.ladder_position")
        lad_f = int(f["ladder_band"][t])
        if lad_r is None:
            ok_lad &= (lad_f == PL.LADDER_REFUSED)
        else:
            ok_lad &= (PL.LADDER_BANDS[lad_f] == lad_r)
        # S5 slope/accel are rendered, not published: read the rendered row
        put5 = _Put()
        txt = SEC.s5_tminus(case, put5)
        line = [ln for ln in txt if ln.strip().startswith("mid_slope_$/min")][0]
        cells = line.replace("accel(1m-5m)=", "").split()
        sl1 = float(cells[3])
        acc = float(cells[4])
        ok_slope &= (abs(sl1 - float(f["slope_1m_usd"][t])) < 0.06
                     and abs(acc - float(f["accel_usd"][t])) < 0.06)
        # MUTANT MT_P01: read COVERAGE off the SESSION row instead
        if cov_r is not None:
            mut &= abs(float(cov_r) - float(f["coverage_session"][t])) < 1e-9
        detail.append("%s cov=%.4f" % (cid, cov_f))
    armed = ok_cov and ok_lad and ok_slope
    return check("frame_matches_the_renderer", "MT_P01_coverage_from_session",
                 armed, bool(mut),
                 "cov=%s lad=%s slope=%s" % (ok_cov, ok_lad, ok_slope))


# ---------------------------------------------------------------- t02 ------
def t02_pivot_chain_is_causal():
    """MT_P02: filtering the pivot chain on pivot_sec instead of conf_sec.

    LAW: a ZigZag pivot is knowable only once CONFIRMED.  The one-scan chain
    filtered at conf_sec < dec_sec must equal sections._pivots, which rescans
    the truncated prefix.  The test is run on candidates for which the two
    rules DISAGREE (a decision second inside a pivot's confirmation lag), so
    the mutant cannot pass by coincidence.
    """
    asset, d8 = "HG", 20210929
    f = PL.frame(asset, d8, with_certs=False)
    spec = A.C.ASSETS[asset]
    sess = A.load_session(asset, d8)
    psec, pside, pconf = PL._pivot_chain(
        asset, sess["s"], sess["trade_date"], float(f["atr_usd"][0]),
        float(spec["tick_px"]), float(spec["tick_usd"]), float(spec["mult"]))
    n_conf = np.searchsorted(np.sort(pconf), f["dec_sec"], side="left")
    n_piv = np.searchsorted(np.sort(psec), f["dec_sec"], side="left")
    differ = np.nonzero(n_conf != n_piv)[0]
    armed = differ.size > 0
    mutant = True
    checked = 0
    for t in differ[:8].tolist():
        cid = str(f["cid"][t])
        dec = int(f["dec_sec"][t])
        case = A.Case(cid, MC.MODE_BLIND, want_events=False)
        ref = sorted((int(p[0]), int(p[2])) for p in SEC._pivots(case))
        got = sorted((int(psec[i]), int(pside[i]))
                     for i in range(psec.size) if pconf[i] < dec)
        mut_set = sorted((int(psec[i]), int(pside[i]))
                         for i in range(psec.size) if psec[i] < dec)
        armed &= (got == ref)
        # MUTANT MT_P02: keep pivots whose PIVOT second precedes the decision
        # regardless of when they were confirmed (a forward read of up to the
        # confirmation lag).
        mutant &= (mut_set == ref)
        checked += 1
    return check("pivot_chain_is_causal", "MT_P02_filter_on_pivot_sec",
                 bool(armed), bool(mutant),
                 "n_candidates_where_rules_differ=%d checked=%d"
                 % (int(differ.size), checked))


# ---------------------------------------------------------------- t03 ------
def _synthetic(cov):
    n = len(cov)
    return {"coverage_phase": np.array(cov, dtype=np.float64),
            "ladder_band": np.zeros(n, dtype=np.int64),
            "runway_phase_sec": np.full(n, 30000, dtype=np.int64),
            "session_close_exit": np.ones(n, dtype=bool),
            "extreme_age_sec": np.full(n, 100, dtype=np.int64),
            "pivot_age_sec": np.full(n, 100, dtype=np.int64),
            "side": np.full(n, -1, dtype=np.int64),
            "slope_1m_usd": np.full(n, -50.0),
            "accel_usd": np.full(n, -50.0)}


def _terms_strict(f, reading="A"):
    """MUTANT detector: the coverage term with a STRICT inequality."""
    T = P1.terms_of(f, reading)
    cov = f["coverage_phase"]
    T[:, 0] = np.isfinite(cov) & (cov < P1.COVERAGE_MAX)
    return T


def t03_coverage_boundary_is_inclusive():
    """MT_P03: `< 70%` instead of the ledger's `<= 70%`.

    LAW (PATTERN_LEDGER P001): `S3.COVERAGE_phase <= 70%`.  A candidate at
    EXACTLY 0.70 fires; 0.70 + 1 ulp does not.
    """
    f = _synthetic([P1.COVERAGE_MAX,
                    np.nextafter(P1.COVERAGE_MAX, 1.0),
                    P1.COVERAGE_MAX - 1e-6])
    fire = np.all(P1.terms_of(f, "A"), axis=1)
    armed = bool(fire[0]) and not bool(fire[1]) and bool(fire[2])
    mut = np.all(_terms_strict(f, "A"), axis=1)
    mutant = bool(mut[0])                  # the mutant must MISS the boundary
    return check("coverage_boundary_is_inclusive", "MT_P03_strict_less_than",
                 armed, mutant, "fire=%s mutant_fire=%s"
                 % (fire.tolist(), mut.tolist()))


# ---------------------------------------------------------------- t04 ------
def _future_extreme_age(asset, d8):
    """MUTANT frame field: the phase extreme taken over the WHOLE phase,
    including seconds AFTER the decision (the end-of-session column read)."""
    f = PL.frame(asset, d8)
    sess = A.load_session(asset, d8)
    s = sess["s"]
    age = np.full(f["n"], -1, dtype=np.int64)
    for t in range(f["n"]):
        a = int(np.searchsorted(s.vt, f["phase_seg_start"][t], side="left"))
        b = int(np.searchsorted(s.vt, f["phase_seg_end"][t], side="left"))
        if b <= a:
            continue
        w = s.vm[a:b]
        j = int(np.argmax(w)) if f["side"][t] < 0 else int(np.argmin(w))
        age[t] = int(f["dec_sec"][t]) - int(s.vt[a + j])
    return f, age


def t04_extreme_age_is_causal():
    """MT_P04: the phase extreme read over the WHOLE phase (a forward read).

    LAW: T4 may only see [phase_open, dec_sec).  The forward read changes the
    fire set, so a detector built on it is a different (leaking) detector.
    """
    asset, d8 = "HG", 20210929
    f, fut = _future_extreme_age(asset, d8)
    causal = f["extreme_age_sec"]
    T = P1.terms_of(f, "A")
    fire = np.all(T, axis=1)
    g = dict(f)
    g["extreme_age_sec"] = fut
    fire_fut = np.all(P1.terms_of(g, "A"), axis=1)
    armed = (not np.array_equal(causal, fut)
             and not np.array_equal(fire, fire_fut)
             and int(causal[_at(f, CAUSALITY_CID)]) == 1236)
    # MUTANT MT_P04: the production frame returns the forward age
    mutant = np.array_equal(causal, fut)
    return check("extreme_age_is_causal", "MT_P04_extreme_from_full_phase",
                 armed, bool(mutant),
                 "n_fire_causal=%d n_fire_forward=%d n_age_differs=%d"
                 % (int(fire.sum()), int(fire_fut.sum()),
                    int((causal != fut).sum())))


# ---------------------------------------------------------------- t05 ------
def t05_retrieval_refuses_untainted_pool():
    """MT_P05: a pool guard that FILTERS instead of REFUSING.

    LAW (D-035.2 shape): an untainted case in the retrieval pool is a protocol
    violation, and a violation must reach the caller as an exception — a
    silent subsample hides it.  The guard validates against the LEDGER, so a
    poisoned pool cannot certify itself.
    """
    entries = UC.read_ledger()
    study = [e["cid"] for e in entries if e.get("mode") == UC.MODE_STUDY]
    # an untainted case: a real roster candidate from a session no STUDY row
    # has ever touched.
    d8 = [d for d in PL.sessions("SI", years={2021}) if d >= 20211101][0]
    f = PL.frame("SI", d8, with_certs=False)
    bad_cid = str(f["cid"][0])
    dirty = study + [bad_cid]
    refused = False
    try:
        R.pool_cids(entries, pool=dirty)
    except R.PoolRefusal:
        refused = True
    # a lawful pool must still pass, or the guard is just "refuse everything"
    lawful = len(R.pool_cids(entries)) == len(set(study))
    # MUTANT MT_P05: the filtering guard silently drops the untainted case
    # instead of raising -- it must NOT satisfy the law.
    mut_refused = False
    got = []
    try:
        got = R.pool_cids(entries, pool=dirty, _mutant_filter=True)
    except R.PoolRefusal:
        mut_refused = True
    dropped = (not mut_refused) and (bad_cid not in got)
    return check("retrieval_refuses_untainted_pool", "MT_P05_filter_not_refuse",
                 refused and lawful and dropped, mut_refused,
                 "poison=%s n_pool_mutant=%d silently_dropped=%s"
                 % (bad_cid, len(got), dropped))


# ---------------------------------------------------------------- t06 ------
def t06_retrieval_scaling_binds():
    """MT_P06: the distance without per-field robust scaling.

    LAW: blocks are commensurable only AFTER per-field robust scaling; raw
    units let runway (tens of thousands of seconds) swamp every other block,
    so the unscaled ranking must differ from the production one.
    """
    cid = FIXTURES[0]
    _q, hits, sc, _m = R.retrieve(cid, k=8)
    _q2, hits2, sc2, _m2 = R.retrieve(cid, k=8, _mutant_unscaled=True)
    armed = (all(v == 1.0 for v in sc2.values())
             and any(v != 1.0 for v in sc.values())
             and len(hits) == 8)
    # MUTANT MT_P06: an unscaled distance that ranks the same anyway would mean
    # the scaling law is decorative.
    mutant = ([h["cid"] for h in hits] == [h["cid"] for h in hits2])
    return check("retrieval_scaling_binds", "MT_P06_unscaled_distance",
                 armed, mutant,
                 "top1=%s top1_unscaled=%s" % (hits[0]["cid"],
                                               hits2[0]["cid"]))


# ---------------------------------------------------------------- t07 ------
def t07_retrieval_is_deterministic():
    """MT_P07: a non-total tie-break.

    LAW: two runs return the identical ordered list, and equal distances are
    ordered by cid.
    """
    cid = FIXTURES[0]
    _q, a, _s, _m = R.retrieve(cid, k=12)
    _q2, b, _s2, _m2 = R.retrieve(cid, k=12)
    armed = [h["cid"] for h in a] == [h["cid"] for h in b]
    ties = 0
    for i in range(1, len(a)):
        if round(a[i - 1]["dist"], 9) == round(a[i]["dist"], 9):
            ties += 1
            armed &= a[i - 1]["cid"] < a[i]["cid"]
    # MUTANT MT_P07: order by distance alone (Python's sort is stable, so the
    # tie order would follow the pool's file order rather than the cid) —
    # detected by comparing against a deliberately reversed input order.
    # DEFECT D13 (found by this round): the reconstruction below must drop the
    # QUERY from the pool BEFORE computing the scales, exactly as retrieve()
    # does — the query is itself a study-tainted pool member, and counting it
    # twice in the reference set shifts every robust scale slightly.  With the
    # E1D2 pool that shift flipped one near-tie and the test failed at HEAD
    # against a production path that was never wrong.
    recs = [r for r in reversed(R.pool_records()) if r["cid"] != cid]
    sc = R.scales(recs + [R.vector(cid, with_certs=False)])
    q = R.vector(cid, with_certs=False)
    scored = []
    for c in recs:
        if c["cid"] == cid:
            continue
        d, nb, _p = R.distance(q, c, sc)
        if nb >= R.MIN_BLOCKS and np.isfinite(d):
            scored.append((round(d, 9), c["cid"]))
    mut = sorted(scored, key=lambda r: r[0])[:12]
    mutant = ([m[1] for m in mut] != [h["cid"] for h in a]) and ties == 0
    ok_total = [m[1] for m in sorted(scored)[:12]] == [h["cid"] for h in a]
    return check("retrieval_is_deterministic", "MT_P07_distance_only_sort",
                 armed and ok_total, bool(mutant),
                 "n_ties=%d" % ties)


# ---------------------------------------------------------------- t08 ------
TRIAGE = "/workspace/artifacts/cache/port/m2/triage/E1D1_TRIAGE_INDEX.tsv"

# triage_index.py parses the RENDERED sheets; pattern_lib recomputes from the
# receipts.  Two independent implementations of the same 12 quantities, over
# the 1,039 day-complete E1-STUDY-D1 candidates.  NOTE the column-name defect
# on record: triage_index's `slope5m` is parsed as the LAST printed column of
# the S5 mid_slope row, which is the ONE-MINUTE slope, not the 5-minute one.
_XCHECK = (("f60_n", "f60_n", 1e-6), ("f60_vol", "f60_vol", 1e-6),
           ("f60_sflow", "f60_sflow", 1e-6),
           ("fph_sflow", "fph_sflow", 1e-6), ("fph_vol", "fph_vol", 1e-6),
           ("ext_needed", "ext_needed_usd", 3.0),
           ("runway_phase", "runway_phase_sec", 1e-6),
           ("extreme_age_trade_side", "extreme_age_sec", 1e-6),
           ("slope5m", "slope_1m_usd", 0.06), ("accel", "accel_usd", 0.06),
           ("rv_collapse", "rv_ratio", 0.10))


def _triage_rows():
    with open(TRIAGE) as fh:
        lines = [ln for ln in fh if not ln.startswith("#")]
    cols = lines[0].rstrip("\n").split("\t")
    return [dict(zip(cols, ln.rstrip("\n").split("\t"))) for ln in lines[1:]]


def t08_frame_matches_the_day1_triage_index():
    """MT_P08: the S8 phase window measured from second 0 instead of the phase.

    LAW (D-006): the frame's flow/capacity fields must equal what the day-1
    lane independently parsed off the rendered sheets, candidate by candidate.
    """
    if not os.path.exists(TRIAGE):
        return check("frame_matches_the_day1_triage_index", "MT_P08_session_"
                     "window_for_phase_flow", False, False, "no triage index")
    rows = _triage_rows()
    frames = {}
    bad = {k: 0 for k, _f, _t in _XCHECK}
    mut_hits = 0
    n = 0
    for r in rows:
        a, d8, _s, _sd = MC.parse_cid(r["cid"])
        if (a, d8) not in frames:
            frames[(a, d8)] = PL.frame(a, d8, with_certs=False)
        f = frames[(a, d8)]
        t = _at(f, r["cid"])
        n += 1
        for key, field, tol in _XCHECK:
            try:
                want = float(r[key])
            except (KeyError, ValueError):
                continue
            got = float(f[field][t])
            if not np.isfinite(got) or abs(want - got) > tol:
                bad[key] += 1
        # MUTANT MT_P08: read the phase flow window from session second 0
        sess = A.load_session(a, d8)
        tr = sess["trades"]
        hi = int(np.searchsorted(tr["sec"], int(f["dec_sec"][t]), side="left"))
        sess_vol = int(tr["size"][:hi].astype(np.int64).sum())
        if sess_vol == int(f["fph_vol"][t]):
            mut_hits += 1
    armed = all(v <= 1 for v in bad.values())     # <=1 = print-rounding only
    mutant = (mut_hits == n)
    return check("frame_matches_the_day1_triage_index",
                 "MT_P08_session_window_for_phase_flow", armed, mutant,
                 "n=%d mismatches=%s mutant_agrees=%d" % (n, bad, mut_hits))


# ---------------------------------------------------------------- t09 ------
def _synth_p016(ext, frac):
    n = len(ext)
    return {"ext_needed_usd": np.array(ext, dtype=np.float64),
            "phase_age_sec": np.full(n, 1000, dtype=np.int64),
            "runway_phase_sec": np.full(n, 25000, dtype=np.int64),
            "session_close_exit": np.ones(n, dtype=bool),
            "f60_n": np.full(n, 10, dtype=np.int64),
            "f60_vol": np.full(n, 40, dtype=np.int64),
            "fph_vol": np.full(n, 1000, dtype=np.int64),
            "fph_sflow": np.array([-1000.0 * x for x in frac]),
            "side": np.full(n, -1, dtype=np.int64),
            "rv_ratio": np.full(n, 3.0)}


def t09_p016_boundaries_are_inclusive():
    """MT_P09: strict inequalities on P016's extension and flow-fraction terms.

    LAW (PATTERN_LEDGER P016 / e1d1_policy T3+T5): `ext <= $450` and
    `|sflow|/vol >= 0.05` are INCLUSIVE at their stated edges.
    """
    f = _synth_p016([P1.EXT_MAX_USD, P1.EXT_MAX_USD + 0.01, 100.0,
                     P1.EXT_MAX_USD],
                    [0.20, 0.20, P1.SFLOW_MIN_FRAC, P1.SFLOW_MIN_FRAC - 1e-6])
    fire = np.all(P1.terms_p016(f), axis=1)
    armed = (bool(fire[0]) and not bool(fire[1]) and bool(fire[2])
             and not bool(fire[3]))
    T = P1.terms_p016(f)
    T[:, 0] = (np.isfinite(f["ext_needed_usd"])
               & (f["ext_needed_usd"] < P1.EXT_MAX_USD)
               & (f["phase_age_sec"] >= P1.PHASE_MIN_AGE_SEC))
    frac = np.abs(f["fph_sflow"]) / f["fph_vol"]
    T[:, 3] = ((f["fph_vol"] >= P1.PHASE_MIN_VOL)
               & (f["fph_sflow"] * f["side"] > 0)
               & (frac > P1.SFLOW_MIN_FRAC))
    mut = np.all(T, axis=1)
    mutant = bool(mut[0]) and bool(mut[2])
    return check("p016_boundaries_are_inclusive", "MT_P09_strict_inequalities",
                 armed, mutant,
                 "fire=%s mutant=%s" % (fire.tolist(), mut.tolist()))


# ---------------------------------------------------------------- t10 ------
# The D9/D10 triage columns are cross-checked against pattern_lib on the
# committed E1-STUDY-D2 sheets: triage_index PARSES the rendered text and the
# frame RECOMPUTES from the receipts, so agreement is two independent
# implementations of one quantity (D-006).  20210702 is the session the whole
# batch-2 census is about (12:30Z Employment Situation inside the NY phase).
REGIME_SESSION = ("SI", 20210702)
ERA_SHEETS = "/workspace/artifacts/cache/port/m2/era/E1/STUDY"


def _sheet_paths(asset, d8, limit=40):
    d = os.path.join(ERA_SHEETS, asset, str(d8))
    if not os.path.isdir(d):
        return []
    fs = sorted(f for f in os.listdir(d) if f.endswith(".BLIND.sheet.txt"))
    step = max(1, len(fs) // limit)
    return [os.path.join(d, f) for f in fs[::step]][:limit]


def _mut_regime(text):
    """MUTANT MT_P10: the regime cells parsed WITHOUT their own column names.

    The D8 defect in its D9 clothes: an extractor that anchors the regime
    percentage on the `range_hat` label alone lands on the vol_regime row's
    `range_hat=$2542.7` — the DENOMINATOR — instead of the `% of range_hat`
    ratio, and a bare `surprise=` search takes whatever prints first.  Both
    produce a plausible-looking number in the right column.
    """
    import re as _re
    out = {}
    m = _re.search(r"day_type_so_far\s+(\S+)", text)
    out["day_type_so_far"] = m.group(1) if m else None
    m = _re.search(r"range_hat=\$(\S+)", text)
    out["range_vs_hat_pct"] = float(m.group(1)) if m else None
    m = _re.search(r"surprise=(\S+)", text)
    try:
        out["surprise"] = float(m.group(1)) if m else None
    except ValueError:
        out["surprise"] = None
    return out


def t10_triage_regime_columns_match_the_frame():
    """MT_P10: regime columns parsed off unnamed neighbours (a misparse).

    LAW (CC-M2-10.6 D9): `day_type_so_far`, `range_vs_hat_pct` and `surprise`
    are read by EXPLICIT COLUMN NAME and must equal the frame's causal
    recomputation candidate by candidate; the D10 flow/schedule columns
    (f5m/f30m/sflow, last-release age) must too.
    """
    import triage_index as TI
    asset, d8 = REGIME_SESSION
    paths = _sheet_paths(asset, d8)
    if not paths:
        return check("triage_regime_columns_match_the_frame",
                     "MT_P10_regime_misparse", False, False, "no sheets")
    f = PL.frame(asset, d8, with_certs=False)
    bad = {}
    mut_agrees = 0
    n = 0
    for p in paths:
        r = TI.parse_sheet(p)
        t = _at(f, r["cid"])
        n += 1
        want = {
            "day_type_so_far": (PL.DAY_TYPES[int(f["day_type"][t])]
                                if int(f["day_type"][t]) >= 0 else None),
            "range_vs_hat_pct": (100.0 * float(f["day_type_frac"][t])
                                 if np.isfinite(f["day_type_frac"][t])
                                 else None),
            "surprise": (float(f["surprise"][t])
                         if np.isfinite(f["surprise"][t]) else None),
            "f5m_sflow": int(f["f5m_sflow"][t]),
            "f5m_vol": int(f["f5m_vol"][t]),
            "f30m_sflow": int(f["f30m_sflow"][t]),
            "f30m_vol": int(f["f30m_vol"][t]),
            # S12 shows `last_scheduled` only inside context.recent_release's
            # 24h display window; the FRAME field is deliberately unwindowed
            # (P022's clause is `< 90min`, and a windowed field would refuse
            # rather than answer), so the expectation is windowed here.
            "sched_last_age": (float(f["release_age_sec"][t])
                               if 0 <= int(f["release_age_sec"][t]) <= 86400
                               else None),
        }
        for key, w in want.items():
            g = r.get(key)
            if w is None:
                ok = g is None
            elif g is None:
                ok = False
            elif key in ("day_type_so_far",):
                ok = str(g) == w
            else:
                # the sheet prints 1 decimal for the percentage and 3 for
                # surprise; the tolerance is the print quantum, nothing more.
                tol = 0.06 if key == "range_vs_hat_pct" else (
                    0.0006 if key == "surprise" else 1e-9)
                ok = abs(float(g) - float(w)) <= tol
            if not ok:
                bad[key] = bad.get(key, 0) + 1
        with open(p) as fh:
            mut = _mut_regime(fh.read())
        same = True
        for key in ("day_type_so_far", "range_vs_hat_pct", "surprise"):
            w = want[key]
            g = mut[key]
            if w is None or g is None:
                same &= (w is None and g is None)
            elif key == "day_type_so_far":
                same &= str(g) == w
            else:
                same &= abs(float(g) - float(w)) <= 0.06
        mut_agrees += int(same)
    armed = (not bad) and n > 0
    mutant = (mut_agrees == n)             # the misparse must NOT satisfy it
    return check("triage_regime_columns_match_the_frame",
                 "MT_P10_regime_misparse", armed, bool(mutant),
                 "n=%d mismatches=%s mutant_agrees=%d version=%s/%s"
                 % (n, bad or "{}", mut_agrees, TI.VERSION,
                    TI.columns_sha16()))


# ---------------------------------------------------------------- t11 ------
def _event_window_bruteforce(asset, d8, back_sec=0):
    """(n, vol, sflow) over [release_sec - back_sec, dec) per candidate.

    back_sec = 0 is the law; back_sec > 0 is the mutant that SPANS the release
    boundary and therefore mixes the pre-release market into the post-release
    window — the exact fossil P022 exists to name.
    """
    f = PL.frame(asset, d8, with_certs=False)
    sess = A.load_session(asset, d8)
    tr = sess["trades"]
    sec = tr["sec"]
    sz = tr["size"].astype(np.int64)
    sd = tr["side"]
    n = np.full(f["n"], -1, dtype=np.int64)
    vol = np.full(f["n"], -1, dtype=np.int64)
    sfl = np.zeros(f["n"], dtype=np.int64)
    for t in range(f["n"]):
        if not bool(f["event_in_phase"][t]):
            continue
        lo = max(0, int(f["release_sec"][t]) - back_sec)
        m = (sec >= lo) & (sec < int(f["dec_sec"][t]))
        n[t] = int(m.sum())
        vol[t] = int(sz[m].sum())
        sfl[t] = int(sz[m & (sd == ord("B"))].sum()
                     - sz[m & (sd == ord("A"))].sum())
    return f, n, vol, sfl


def t11_event_window_starts_at_the_release():
    """MT_P11: an event window that SPANS the release second.

    LAW (D10 / E1D2-F3): the event-anchored flow window is [release_sec,
    dec_sec) — flow accumulated SINCE the release.  A window that starts before
    it carries the pre-release market, which is the fossil the whole repair is
    about; and on 2021-07-02 the two answers disagree in SIGN.
    """
    asset, d8 = REGIME_SESSION
    f, n, vol, sfl = _event_window_bruteforce(asset, d8, back_sec=0)
    have = np.nonzero(f["event_in_phase"])[0]
    ok = bool(have.size) and bool(
        np.array_equal(f["fev_n"][have], n[have])
        and np.array_equal(f["fev_vol"][have], vol[have])
        and np.array_equal(f["fev_sflow"][have], sfl[have]))
    # the window has to be a DIFFERENT object from the phase window, or D10
    # bought nothing: on this session the signs must actually disagree.
    disagree = int(np.sum(np.sign(f["fev_sflow"][have])
                          != np.sign(f["fph_sflow"][have])))
    refused = np.nonzero(~f["event_in_phase"])[0]
    refused_ok = bool(np.all(f["fev_n"][refused] == -1)
                      and np.all(f["fev_vol"][refused] == -1))
    armed = ok and refused_ok and disagree > 0
    # MUTANT MT_P11: start the window 60s BEFORE the release
    _f2, _n2, _v2, sfl2 = _event_window_bruteforce(asset, d8, back_sec=60)
    mutant = bool(np.array_equal(f["fev_sflow"][have], sfl2[have]))
    return check("event_window_starts_at_the_release",
                 "MT_P11_window_spans_the_release", armed, mutant,
                 "n_event_candidates=%d sign_disagreements_vs_phase=%d "
                 "refused=%d" % (int(have.size), disagree, int(refused.size)))


# ---------------------------------------------------------------- t12 ------
def t12_retrieval_exclude_date8_binds():
    """MT_P12: the --exclude-date8 flag ignored.

    LAW (CC-M2-10.6 D11 + CC-M2-9.4): the flag must actually remove the named
    sessions from the pool, AND it must run AFTER the taint guard — excluding a
    date may never launder an untainted case into a lawful pool.
    """
    entries = UC.read_ledger()
    cid = "SI-20210702-052509-S"           # the case the day-2 wrapper queried
    _q, base, _s, m0 = R.retrieve(cid, k=12, entries=entries)
    _q, cut, _s, m1 = R.retrieve(cid, k=12, entries=entries,
                                 exclude_date8={20210702})
    same_day_base = sum(1 for h in base if int(h["rec"]["d8"]) == 20210702)
    same_day_cut = sum(1 for h in cut if int(h["rec"]["d8"]) == 20210702)
    # the guard still binds when the poisoned case's own date is excluded
    d8 = [d for d in PL.sessions("SI", years={2021}) if d >= 20211101][0]
    fr = PL.frame("SI", d8, with_certs=False)
    bad_cid = str(fr["cid"][0])
    study = [e["cid"] for e in entries if e.get("mode") == UC.MODE_STUDY]
    laundered = False
    try:
        R.retrieve(cid, k=4, entries=entries, pool=study + [bad_cid],
                   exclude_date8={d8})
    except R.PoolRefusal:
        laundered = True
    armed = (same_day_base > 0 and same_day_cut == 0
             and m1["n_pool"] < m0["n_pool"] and laundered
             and m1["excluded_date8"] == [20210702])
    # MUTANT MT_P12: the flag is accepted and ignored
    _q, ign, _s, _m = R.retrieve(cid, k=12, entries=entries,
                                 exclude_date8={20210702},
                                 _mutant_ignore_exclude=True)
    mutant = (sum(1 for h in ign if int(h["rec"]["d8"]) == 20210702) == 0)
    return check("retrieval_exclude_date8_binds", "MT_P12_exclude_ignored",
                 armed, mutant,
                 "pool %d->%d same_day_hits %d->%d guard_still_refuses=%s"
                 % (m0["n_pool"], m1["n_pool"], same_day_base, same_day_cut,
                    laundered))


TESTS = (t01_frame_matches_the_renderer, t02_pivot_chain_is_causal,
         t03_coverage_boundary_is_inclusive, t04_extreme_age_is_causal,
         t05_retrieval_refuses_untainted_pool, t06_retrieval_scaling_binds,
         t07_retrieval_is_deterministic,
         t08_frame_matches_the_day1_triage_index,
         t09_p016_boundaries_are_inclusive,
         t10_triage_regime_columns_match_the_frame,
         t11_event_window_starts_at_the_release,
         t12_retrieval_exclude_date8_binds)


def main():
    MC.verify_spec(force=True)
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
    MC.write_tsv(os.path.join(OUT_DIR, "pattern_red_ledger.tsv"), SECTION,
                 MC.params_hash(P1.PARAMS),
                 ["test", "mutant", "armed_pass", "mutant_pass", "verdict",
                  "detail"], LEDGER,
                 extra=["RED-FIRST: armed_pass MUST be 1 and mutant_pass MUST "
                        "be 0 on every row"])
    MC.write_json(os.path.join(OUT_DIR, "pattern_tests.receipt.json"),
                  {"env": MC.env_receipt(P1.PARAMS), "n_tests": len(TESTS),
                   "n_failed": n_fail,
                   "verdict": "PASS" if n_fail == 0 else "FAIL"})
    MC.hb("pattern tests: %d/%d passed" % (len(TESTS) - n_fail, len(TESTS)))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
