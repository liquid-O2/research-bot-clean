#!/usr/bin/python3
"""PORT M2 — RED-FIRST tests for the p001 / p020 / p025 census trio.

THE ONE D-001 FIX PASS, census sub-lane.  Same law as test_m2.py: every test
that asserts a LAW carries a committed MUTANT — a named neutralised line of the
production rule that the test MUST catch.  A test whose mutant SURVIVES is a
dead test and FAILS.  Red ledger:
artifacts/cache/port/m2/tests/pcensus_fixlane_red_ledger.tsv.

The findings closed here, one test each (M2_CONSOLIDATED_REVIEW §3.2b):

  R105  the D-058 pre-exam holdout was loaded by all three censuses; p025
        flagged it at the WRONG boundary (>= 20250901) and stamped that
        understated figure into its receipt and report.  A MUTANT THAT LOADS A
        HOLDOUT SESSION MUST FAIL.
  R106  every promotion was a BARE RATIO — no SE, no CI, no cluster
        adjustment, no minimum-n guard on the numerator.
  R107  p001 Holm-corrected PER ARM, screening 48 tests as three families of
        16, although arms A/B/P016 are three readings of the same object; p025
        pooled 192 nuisance re-expressions into the deciding family.
  R108  p025's `runway_binding_sec` is a WHOLE-SESSION aggregate and was
        eligible for "ENTRY RULE".
  R109  `_frac` clamped the denominator to 1.0, so a 1-lot window was a 100%
        aggression signal; LIVE_N_MIN served as both a count and a volume.
  R110  refused and NEGATIVE runways were deposited in the LOWEST band.
  R111  `ext_needed_usd` is clipped at zero, so the most extended candidates
        were classified REVERSION.
  R112  the MIRROR LAW was not implemented in any of the three files.
  R113  no cluster-count floor before fitting a GEE, and a normal reference
        under a CR1 sandwich.
  R114  every threshold was fitted inside FIT and the same files printed those
        sessions' firing as corroboration.
  R115  REFUSED_FVOL_CENSUS.tsv published every ALL-era count at exactly 2x.
  R116  the destruction seed depended only on the term index, so every
        detector in every file drew BYTE-IDENTICAL permutations — and the
        seeds p020/p025 DECLARED and hashed were dead.
  R117  within-session shuffling has ZERO power against a within-session
        constant term, and the code stamped those TERM_NOT_LOAD_BEARING by
        construction.

Run: /usr/bin/python3 engine/port_m2/test_pcensus_fixlane.py
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
import p001_census as P1                  # noqa: E402
import p020_census as P20                 # noqa: E402
import p025_census as P25                 # noqa: E402

SECTION = ("D-001 fix pass — p001/p020/p025 census trio (red-first, "
           "R105-R117)")
OUT_DIR = MC.out_path("tests", "_")[:-1]

LEDGER = []
_C = {}


def check(name, mutant, ok_armed, ok_mutant, detail=""):
    verdict = "PASS" if (ok_armed and not ok_mutant) else (
        "FAIL_ARMED" if not ok_armed else "FAIL_DEAD_MUTANT")
    LEDGER.append([name, mutant, int(bool(ok_armed)), int(bool(ok_mutant)),
                   verdict, detail])
    return verdict == "PASS"


def synth(n_sessions=90, n_per=12, seed=7):
    """A deterministic synthetic D-panel in the census's own layout.

    The aggregation machinery is pure numpy over packed arrays, so the laws
    below are exercised on a panel this file builds rather than on a full
    re-census (which takes hours).  The FIXTURES that need real tape — the
    holdout enumerator, the frame's own fields — use the real roster.
    """
    key = (n_sessions, n_per, seed)
    if key in _C:
        return _C[key]
    rng = np.random.default_rng(seed)
    n = n_sessions * n_per
    assets = np.array([MC.ASSET_ORDER[i % len(MC.ASSET_ORDER)]
                       for i in range(n_sessions)])
    d8 = np.array([20210701 + (i * 3) for i in range(n_sessions)],
                  dtype=np.int64)
    D = {
        "asset": np.repeat(assets, n_per),
        "d8": np.repeat(d8, n_per).astype(np.int32),
        "dec_sec": np.tile(np.arange(n_per) * 600, n_sessions).astype(np.int32),
        "side": rng.choice([1, -1], size=n).astype(np.int64),
        "phase_dec": rng.integers(0, 3, size=n).astype(np.int8),
        "cert_close": rng.normal(-50.0, 400.0, size=n),
        "cert_peak": rng.normal(60.0, 420.0, size=n),
        "mae": np.abs(rng.normal(150.0, 80.0, size=n)),
        "klass": np.full(n, "REVERSAL-CONFIRMATION"),
        "walled": np.zeros(n, dtype=bool),
    }
    D["year"] = (D["d8"] // 10000).astype(np.int32)
    D["winner"] = (D["cert_close"] >= 500.0)
    keys = np.array(["%s-%08d" % (a, d) for a, d in
                     zip(D["asset"].tolist(), D["d8"].tolist())])
    uniq, D["cluster"] = np.unique(keys, return_inverse=True)
    D["n_sessions_total"] = int(uniq.size)
    _C[key] = D
    return D


# ---------------------------------------------------------------- c01 ------
def c01_a_mutant_that_loads_a_holdout_session_fails():
    """R105 — the D-058 pre-exam holdout must never be enumerated.

    LAW (D-058): 2025-07-01..2025-12-31 is the PRE-EXAM HOLDOUT, blind-only,
    touched ONCE after entries/features/model freeze.  All three censuses
    enumerated `FIT_YEARS + (GATE_YEAR,)` with no date filter, so every
    GATE_2025 census row, GEE row and Holm member pooled 2025-H2 with H1.
    """
    armed, detail = True, []
    total_q = 0
    for asset in MC.ASSET_ORDER:
        ds, nq = PL.sessions_fit(asset, years={2024, 2025})
        armed &= all(not MC.in_holdout(d) for d in ds)
        armed &= nq > 0
        total_q += nq
        detail.append("%s kept=%d quarantined=%d" % (asset, len(ds), nq))
    # THE MUTANT: the raw enumerator the censuses used to call.  It must
    # REFUSE, loudly, rather than hand back holdout sessions.
    mutant_ok = False
    try:
        bad = PL.sessions("SI", years={2025})
        mutant_ok = any(MC.in_holdout(d) for d in bad)
    except MC.HoldoutRefusal:
        mutant_ok = False
    # and the opt-out has to be explicit AND still visible
    opt = PL.sessions("SI", years={2025}, allow_holdout=True)
    armed &= any(MC.in_holdout(d) for d in opt)
    return check("a_mutant_that_loads_a_holdout_session_fails",
                 "MT_R105_PL.sessions_without_the_D058_refusal",
                 armed, mutant_ok,
                 "%s; unguarded enumerator refuses=%s"
                 % ("; ".join(detail), not mutant_ok))


# ---------------------------------------------------------------- c02 ------
def c02_p025_holdout_boundary_is_20250701_not_20250901():
    """R105 — p025 flagged the holdout at `>= 20250901`.

    That is the number its receipt stamped and its report printed ("sessions
    from 2025-09-01 onward"), omitting July and August 2025, so the
    adjudicator was handed an UNDERSTATED contamination figure — the one
    number the "flag, not a filter" defence rested on.  This is the exact
    20250901-vs-20250701 error CC-M2-15.3 corrected, surviving in the flag.
    """
    src = open(P25.__file__).read()
    # the literal survives in the REPORT PROSE, which now names the old
    # boundary as the defect; what must be gone is the FILTER that used it
    code = "\n".join(ln for ln in src.split("\n")
                     if not ln.lstrip().startswith("#"))
    armed = ("int(j[1]) >= 20250901" not in code)
    armed &= ("d8 >= 20250901" not in code)
    armed &= ("n_holdout_sessions_in_gate" not in code)
    armed &= (MC.HOLDOUT_FROM_D8 == 20250701)
    armed &= ("MC.in_holdout" in code or "sessions_fit" in code)
    # the era vocabulary must no longer carry a POOLED GATE year
    D = synth()
    D2 = dict(D)
    D2["d8"] = np.where(D["d8"] > 20220101, 20250601, D["d8"]).astype(np.int32)
    D2["year"] = (D2["d8"] // 10000).astype(np.int32)
    names = [n for n, _m in P25._era_masks(D2)]
    armed &= ("GATE_2025H1" in names) and ("GATE_2025" not in names)
    armed &= "FIT_EX_FITTING" in names
    # MUTANT: the boundary the file used to flag at.  Every session in
    # [20250701, 20250901) is contamination it could not see.
    july_aug = [d for d in range(20250701, 20250901)
                if MC.in_holdout(d) and not (d >= 20250901)]
    mutant_ok = (len(july_aug) == 0)
    return check("p025_holdout_boundary_is_20250701_not_20250901",
                 "MT_R105_holdout_flagged_at_20250901",
                 armed, mutant_ok,
                 "eras=%s; dates the 20250901 flag missed=%d"
                 % (names, len(july_aug)))


# ---------------------------------------------------------------- c03 ------
def c03_promotion_carries_an_interval_an_n_floor_and_a_family():
    """R106 — a promotion criterion must carry inference.

    `CONCENTRATOR_MIN = 1.25` graded a detector "WINNER CONCENTRATOR" off
    `fF[16]/fN[16]` — a ratio of two means with no SE, no CI, no cluster
    adjustment and NO MINIMUM-N GUARD on the numerator.  This was the ONLY
    route by which P020/P021/P022/P023/P024/P007 reached the
    feature-candidate set.
    """
    D = synth()
    # a firing set that is BIG in rows but drawn from THREE sessions: a bare
    # ratio promotes it; a session-clustered interval with an n floor must not
    D = dict(D)
    fire = np.isin(D["cluster"], np.unique(D["cluster"])[:3])
    # make the firing set look SPECTACULAR on a bare ratio: it must clear
    # CONCENTRATOR_MIN comfortably, so the ONLY thing standing between it and
    # a promotion is the inference the fix pass added
    D["winner"] = np.where(fire, np.arange(fire.size) % 2 == 0,
                           np.arange(fire.size) % 20 == 0)
    r = P1.ratio_ci(P1.rate_vals(D["winner"]), fire, D["cluster"])
    armed = (r["verdict"] == "NO_TEST_below_floor"
             and r["n_fires"] >= 30 and r["n_clusters_fire"] < 20)
    # MUTANT: the bare ratio.  It happily returns a number to compare to 1.25.
    fF = float(D["winner"][fire].mean())
    fN = float(D["winner"][~fire].mean())
    bare = fF / fN if fN else float("nan")
    # the mutant PASSES the law only if it also declines to promote; it does
    # not — it reads a ratio far above the bar off 3 sessions and promotes
    mutant_ok = not (np.isfinite(bare) and bare >= P20.CONCENTRATOR_MIN)
    # a WELL-POWERED cell must actually be tested and carry an interval
    fire2 = D["dec_sec"] < 3600
    r2 = P1.ratio_ci(P1.rate_vals(D["winner"]), fire2, D["cluster"])
    armed &= (r2["verdict"] == "TESTED" and np.isfinite(r2["lo"])
              and np.isfinite(r2["hi"]) and r2["lo"] <= r2["ratio"] <= r2["hi"])
    return check("promotion_carries_an_interval_an_n_floor_and_a_family",
                 "MT_R106_bare_ratio_fF/fN_with_no_n_floor_and_no_interval",
                 armed, bool(mutant_ok),
                 "3-session cell: n_fires=%d clusters=%d verdict=%s; "
                 "bare ratio would report %.3f; powered cell CI=[%.3f, %.3f]"
                 % (r["n_fires"], r["n_clusters_fire"], r["verdict"], bare,
                    r2["lo"], r2["hi"]))


# ---------------------------------------------------------------- c04 ------
def c04_holm_family_is_the_whole_run_not_one_arm():
    """R107 — p001 Holm-corrected PER ARM.

    48 GEE tests were screened as three families of 16, although arms A and B
    are two readings of the SAME T4 term and P016 is a third mutation of the
    same pattern.  An arm-A-only hit at p ~ 0.004 clears Holm at m=16 and
    FAILS at m=48.
    """
    def mk(p, tag):
        return [tag, "ALL", "FIT", "cert_close", 100, 40, 20] + \
            [0.0] * 5 + [float(p)] + [0.0, 0.0, 0.0, "SIGNIFICANT_p<0.05"]

    # one arm's 16 tests, with a single hit at p = 0.004
    arm = [mk(0.002, "A")] + [mk(0.30 + 0.01 * i, "A") for i in range(15)]
    P1._holm([list(r) for r in arm])       # warm-up, no state
    per_arm = [list(r) for r in arm]
    P1._holm(per_arm)
    hit_per_arm = per_arm[0][19]
    # the HONEST family: all three arms
    whole = ([list(r) for r in arm]
             + [mk(0.30 + 0.01 * i, "B") for i in range(16)]
             + [mk(0.30 + 0.01 * i, "P016") for i in range(16)])
    P1._holm(whole)
    hit_whole = whole[0][19]
    armed = (hit_per_arm == "HOLM_SIGNIFICANT"
             and hit_whole == "HOLM_NOT_SIGNIFICANT")
    # the SHIPPED build must correct once over every arm: robust_rows is called
    # with holm=False and _holm runs on the concatenation
    src = open(P1.__file__).read()
    armed &= 'robust_rows(D, fire, arm, holm=False)' in src
    armed &= "_holm(robust_nc)" in src
    # MUTANT: the per-arm call this file used to make
    mutant_ok = "robust_rows(D, fire, arm)," in src
    # p025's deciding family must exclude the algebraic re-expressions
    s25 = open(P25.__file__).read()
    armed &= 'if str(r[0]).startswith("P025_NY_ADJ_")' in s25
    armed &= "diagnostic_nc" in s25
    return check("holm_family_is_the_whole_run_not_one_arm",
                 "MT_R107_holm_per_arm_and_nuisance_variants_in_the_family",
                 armed, bool(mutant_ok),
                 "p=0.002 at m=16 -> %s; at m=48 -> %s"
                 % (hit_per_arm, hit_whole))


# ---------------------------------------------------------------- c05 ------
def c05_whole_session_aggregate_is_ineligible_for_promotion():
    """R108 — `runway_binding_sec` is built from `last_two_sided_sec`.

    That is the last two-sided second of the WHOLE SESSION
    (port_m0/s3_sessions.py writes it as `idx[-1]`), unknowable at dec_sec —
    the same field `triage_index.py` correctly masks under `--as-of`.  Reading
    B_observed was nonetheless run through the full CC-M2-9.1 grading pipeline
    and appeared in the headline verdict table eligible for ENTRY RULE, and it
    drives P025_RUNWAY.tsv, P025_PHASE_GIVEN_RUNWAY.tsv and the B_observed half
    of the deciding NY-adjusted GEE.
    """
    armed = "P025_B_observed" in P25.NOT_PROMOTABLE
    res = {"tag": "P025_B_observed", "robust": [], "reading": "B_observed",
           "pid": "P025"}
    cen = {("ALL", "FIT", "ALL", "ALL", "FIRE"):
           ["t", "ALL", "FIT", "ALL", "ALL", "FIRE", 90, 500, 5.0] + [0.0] * 8
           + [0.5],
           ("ALL", "FIT", "ALL", "ALL", "NOFIRE"):
           ["t", "ALL", "FIT", "ALL", "ALL", "NOFIRE", 90, 500, 5.0]
           + [0.0] * 8 + [0.1]}
    v, ev = P25.grade(res, cen, [])
    armed &= v.startswith("DIAGNOSTIC ONLY")
    armed &= "ineligible_reason" in ev
    # the A reading is still promotable — the guard is specificity, not a ban
    res_a = dict(res, tag="P025_A_nominal", reading="A_nominal")
    va, _eva = P25.grade(res_a, cen, [])
    armed &= not va.startswith("DIAGNOSTIC ONLY")
    # MUTANT: no ineligibility list -> a whole-session aggregate reaches the
    # entry-rule vocabulary, which is exactly what the old grade() did
    saved = dict(P25.NOT_PROMOTABLE)
    try:
        P25.NOT_PROMOTABLE.clear()
        vm, _evm = P25.grade(res, cen, [])
        # the mutant PASSES the law only if it ALSO refuses to promote; it
        # does not — without the list a whole-session aggregate re-enters the
        # ENTRY RULE / CONCENTRATOR / NULL vocabulary
        mutant_ok = vm.startswith("DIAGNOSTIC ONLY")
    finally:
        P25.NOT_PROMOTABLE.update(saved)
    return check("whole_session_aggregate_is_ineligible_for_promotion",
                 "MT_R108_B_observed_graded_as_an_entry_rule_candidate",
                 armed, bool(mutant_ok),
                 "B_observed -> %s; A_nominal -> %s; without the list -> %s"
                 % (v.split(" (")[0], va.split(" (")[0], vm.split(" (")[0]))


# ---------------------------------------------------------------- c06 ------
def c06_aggression_fraction_has_a_volume_floor():
    """R109 — `_frac` clamped the denominator to 1.0.

    A single 1-lot opposing trade in an otherwise empty 60s window set the term
    true; a 2-lot phase with a 2-lot 5m window satisfied "flow concordant at
    >= 5%".  p001's own P016 X4 does it correctly — `np.where(vol > 0,
    |sfl|/vol, 0.0)` PLUS `vol >= PHASE_MIN_VOL` — so p025 was a regression
    against a pattern already in the codebase.
    """
    num = np.array([1, 1, 300, 60], dtype=np.int64)
    den = np.array([1, 0, 500, 100], dtype=np.int64)
    got = P25._frac(num, den, P25.FRAC_MIN_VOL_5M)
    # rows 0 and 1 are BELOW the floor -> the term cannot fire
    armed = (got[0] == 0.0 and got[1] == 0.0
             and abs(got[2] - 0.6) < 1e-12 and abs(got[3] - 0.6) < 1e-12)
    armed &= (got[0] < P25.SFLOW_MIN_FRAC) and (got[1] < P25.SFLOW_MIN_FRAC)
    # MUTANT: the clamped denominator.  A 1-lot window becomes 100%.
    mut = np.abs(num.astype(np.float64)) / np.maximum(den.astype(np.float64),
                                                      1.0)
    mutant_ok = bool((mut[0] >= P25.SFLOW_MIN_FRAC)
                     == (got[0] >= P25.SFLOW_MIN_FRAC))
    # and LIVE_N_MIN must no longer serve as both a trade COUNT and a VOLUME
    src = open(P25.__file__).read()
    armed &= "LIVE_VOL_MIN" in src
    armed &= '(f["f60_vol"] >= LIVE_N_MIN)' not in src
    return check("aggression_fraction_has_a_volume_floor",
                 "MT_R109_np.maximum(den,1.0)_clamped_denominator",
                 armed, mutant_ok,
                 "floored=%s clamped_mutant=%s (SFLOW_MIN_FRAC=%.2f)"
                 % (got.round(4).tolist(), mut.round(4).tolist(),
                    P25.SFLOW_MIN_FRAC))


# ---------------------------------------------------------------- c07 ------
def c07_refused_runways_get_their_own_band():
    """R110 — refused and NEGATIVE runways were deposited in the LOWEST band.

    `out` was np.zeros-initialised and ended with `out[v < 0] = 0`, so a
    refused or negative runway landed in `b0_lt15m`, indistinguishable from a
    genuine sub-15-minute runway, with no refusal band and no refusal count —
    contaminating P025_RUNWAY.tsv and P025_PHASE_GIVEN_RUNWAY.tsv, the
    artefact-control tables the whole P025 ruling turns on.
    """
    v = np.array([-1, -900, 0, 600, 1000, 40000], dtype=np.int64)
    band = P25.band_index(v)
    armed = (band[0] == P25.BAND_REFUSED and band[1] == P25.BAND_REFUSED
             and band[2] == 0 and band[3] == 0 and band[4] == 1
             and band[5] == 8)
    cnt = P25.band_counts(band)
    armed &= (cnt["n_refused"] == 2 and cnt["n_banded"] == 4)
    # the extra refusal mask (reading B's silent degeneration) must also band
    refused = np.array([False, False, True, False, False, False])
    band_b = P25.band_index(v, refused=refused)
    armed &= (band_b[2] == P25.BAND_REFUSED)
    # MUTANT: the zeros-initialised bander.  Refusals land in b0 with the
    # genuine sub-15-minute runways.
    mut = np.zeros(v.size, dtype=np.int64)
    for k, (lo, hi) in enumerate(P25.BANDS):
        mut[(v >= lo) & (v < hi)] = k
    mut[v < 0] = 0
    mutant_ok = bool((mut[0] == P25.BAND_REFUSED)
                     and (mut[1] == P25.BAND_REFUSED))
    return check("refused_runways_get_their_own_band",
                 "MT_R110_zeros_initialised_band_index_with_out[v<0]=0",
                 armed, mutant_ok,
                 "guarded=%s refused=%d; mutant=%s (refusals in band 0)"
                 % (band.tolist(), cnt["n_refused"], mut.tolist()))


# ---------------------------------------------------------------- c08 ------
def c08_saturated_ext_leaves_the_breakout_reversion_contrast():
    """R111 — `ext_needed_usd` is clipped at zero.

    Every candidate whose extreme ALREADY offers >= $1,000 of reach collapses
    to exactly 0.0, and reading B classified all of them REVERSION
    (`ext <= $450`), so the DiD tested its breakout claim with the most
    extended candidates in the population sitting in the opposite arm —
    indistinguishable from candidates whose extreme offers $600.
    """
    D = {"ext_needed_usd": np.array([0.0, 100.0, 449.0, 451.0, 900.0,
                                     float("nan")]),
         "ext_side": np.zeros(6, dtype=np.int64),
         "side": np.ones(6, dtype=np.int64)}
    brk, rev = P20.breakout_masks(D, "B_ext_needed")
    sat = P20.ext_saturated(D)
    armed = (sat.tolist() == [True, False, False, False, False, False]
             and not brk[0] and not rev[0])      # saturated: neither arm
    armed &= rev[1] and rev[2] and brk[3] and brk[4]
    armed &= not brk[5] and not rev[5]           # NaN: neither arm
    # MUTANT: the split this file used to take, on the clipped value
    ok = np.isfinite(D["ext_needed_usd"])
    mut_rev = ok & (D["ext_needed_usd"] <= P20.EXT_BREAKOUT_MIN_USD)
    mutant_ok = bool(mut_rev[0] == rev[0])       # does the mutant also exclude?
    frac, n = P20.clip_binding_frac(D)
    armed &= (n == 5 and abs(frac - 0.2) < 1e-12)
    return check("saturated_ext_leaves_the_breakout_reversion_contrast",
                 "MT_R111_classify_the_zero_clipped_rows_as_REVERSION",
                 armed, mutant_ok,
                 "saturated=%s breakout=%s reversion=%s; mutant puts the "
                 "saturated row in REVERSION=%s"
                 % (sat.tolist(), brk.tolist(), rev.tolist(),
                    bool(mut_rev[0])))


# ---------------------------------------------------------------- c09 ------
def c09_direction_claims_face_their_mirror():
    """R112 — the MIRROR LAW was not implemented in any of the three files.

    P023 and P007 assert an OPPOSED-flow direction claim and P024 a CONCORDANT
    one; no arm anywhere computed the sign-flipped detector and there was no
    per-session comparison, so a direction claim could be graded ENTRY RULE
    without ever facing its mirror.  p020's DiD is a pooled contrast with no
    per-session component and no sign test, and `p022_direction_rows` compares
    ALIGNED vs OPPOSED — a mirror pair BY CONSTRUCTION — on pooled means only.
    """
    D = synth(n_sessions=120, n_per=10, seed=11)
    # a detector that is GENUINELY better than its mirror, per session
    fire = D["dec_sec"] < 3000
    mirror = ~fire
    D2 = dict(D)
    D2["cert_close"] = D["cert_close"] + np.where(fire, 220.0, 0.0)
    rows = []
    P1.mirror_rows(D2, fire, mirror, "FIXTURE", "det", "det_flipped", rows,
                   metrics=("cert_close",))
    P1.holm_mirror(rows)
    top = [r for r in rows if r[3] == "ALL"][0]
    armed = (top[20] == "TESTED" and top[6] >= MC.MIRROR_MIN_SESSIONS
             and top[9] > 0 and top[13] < 0.05 and top[21] == 1
             and top[24] == "HOLM_SIGNIFICANT")
    # a NULL direction claim must NOT hold
    rows_null = []
    P1.mirror_rows(D, fire, mirror, "NULL", "det", "det_flipped", rows_null,
                   metrics=("cert_close",))
    P1.holm_mirror(rows_null)
    tn = [r for r in rows_null if r[3] == "ALL"][0]
    armed &= (tn[21] == 0)
    # and an UNDERPOWERED cell is NO_TEST, never a negative
    small = synth(n_sessions=8, n_per=10, seed=3)
    rs = []
    P1.mirror_rows(small, small["dec_sec"] < 3000, small["dec_sec"] >= 3000,
                   "SMALL", "det", "det_flipped", rs,
                   metrics=("cert_close",))
    armed &= ([r for r in rs if r[3] == "ALL"][0][20] == "NO_TEST")
    # MUTANT: the POOLED contrast the files used — no pairing, no sign test.
    # It reports a difference on the NULL fixture too, so it cannot separate
    # the two cases the paired test does.
    pooled_true = float(D2["cert_close"][fire].mean()
                        - D2["cert_close"][mirror].mean())
    pooled_null = float(D["cert_close"][fire].mean()
                        - D["cert_close"][mirror].mean())
    # the pooled mutant PASSES the law only if it reports NO edge on the null
    # fixture, which is exactly what it cannot do: with no pairing and no sign
    # test it reports a positive difference on both
    mutant_ok = not (pooled_null > 0)
    # the three files must all CALL it
    armed &= "mirror_rows" in open(P1.__file__).read()
    armed &= "mirror_rows_batch2" in open(P20.__file__).read()
    armed &= "mirror_rows_batch3" in open(P25.__file__).read()
    return check("direction_claims_face_their_mirror",
                 "MT_R112_pooled_contrast_with_no_per_session_pairing",
                 armed, bool(mutant_ok),
                 "real: n=%d delta=%.1f p=%.5f holds=%d holm=%s | null "
                 "holds=%d | pooled mutant true=%.1f null=%.1f"
                 % (top[6], top[9], top[13], top[21], top[24], tn[21],
                    pooled_true, pooled_null))


# ---------------------------------------------------------------- c10 ------
def c10_gee_refuses_below_a_cluster_floor():
    """R113 — no cluster-count floor before fitting a GEE.

    `x.shape[0] > x.shape[1] + 2 and np.ptp(x[:,0]) > 0` was the ONLY guard, so
    a 5-row cell drawn from ONE session passed it; `gee_independence` then
    returned n_clusters=1, the sandwich meat was a single outer product,
    se_cr1 was near-degenerate and `_p_two_sided` returned a spuriously tiny p
    that entered the Holm family.  `phase_in_band_rows` runs over 9 runway
    bands and hit this directly.
    """
    n = 5
    y = np.array([1000.0, 1100.0, -20.0, -30.0, -25.0])
    x = np.array([1.0, 1.0, 0.0, 0.0, 0.0])
    cl_one = np.zeros(n, dtype=np.int64)        # ONE session
    row = P25._gee_row("TINY", "ALL", "FIT", "cert_close", y, [x], cl_one, 2)
    armed = (row[16] == "NO_TEST_below_cluster_floor"
             and not np.isfinite(row[12]))
    # MUTANT: the old guard.  It FITS, and returns a p.
    import episode_v2 as EV                # noqa: E402
    g = None
    if x.size > 1 + 2 and np.ptp(x) > 0:
        g = EV.gee_independence(y, np.column_stack([x]), cl_one,
                                link="identity")
    mut_p = float("nan")
    if g is not None and g["se_cr1"] > 0:
        mut_p = P1._p_two_sided(g["beta"] / g["se_cr1"])
    mutant_ok = not np.isfinite(mut_p)
    # the reference must be t(G-1), not the normal — and they must DIFFER at
    # the cluster counts these cells actually have
    z = 2.10
    p_norm = P1._p_two_sided(z)
    p_t = P1._p_two_sided(z, df=29)
    armed &= (p_t > p_norm)                # t is CONSERVATIVE, as intended
    return check("gee_refuses_below_a_cluster_floor",
                 "MT_R113_fit_a_GEE_on_one_cluster_and_use_the_normal",
                 armed, bool(mutant_ok),
                 "1-cluster cell -> %s; old guard fits and returns p=%s; "
                 "z=2.10 normal p=%.5f vs t(29) p=%.5f"
                 % (row[16], "%.6f" % mut_p if np.isfinite(mut_p) else "none",
                    p_norm, p_t))


# ---------------------------------------------------------------- c11 ------
def c11_in_sample_thresholds_are_quantified_not_asserted():
    """R114 — every threshold was fitted on sessions INSIDE FIT, and the same
    files then printed those sessions' firing as CORROBORATION."""
    D = synth()
    names = [n for n, _m in P1.era_selectors(D)]
    armed = ("FIT" in names and "FIT_EX_FITTING" in names)
    fm = P1.fitting_mask(D)
    sel = dict(P1.era_selectors(D))
    armed &= bool(np.all(sel["FIT_EX_FITTING"] == (sel["FIT"] & ~fm)))
    # the fixture must actually BITE: the panel contains fitting sessions
    armed &= bool(fm.any())
    armed &= int(sel["FIT_EX_FITTING"].sum()) < int(sel["FIT"].sum())
    # MUTANT: FIT only, no ex-fitting row -> the optimism is unquantifiable
    mutant_ok = bool(np.array_equal(sel["FIT"], sel["FIT_EX_FITTING"]))
    # and the reports must call the birth-case tables REPRODUCTION CHECKS
    armed &= "REPRODUCTION CHECK" in open(P1.__file__).read()
    armed &= "REPRODUCTION CHECK" in open(P20.__file__).read()
    armed &= "REPRODUCTION CHECK" in open(P25.__file__).read()
    return check("in_sample_thresholds_are_quantified_not_asserted",
                 "MT_R114_report_FIT_only_and_print_the_birth_cases_as_evidence",
                 armed, mutant_ok,
                 "FIT=%d FIT_EX_FITTING=%d (fitting rows dropped=%d)"
                 % (int(sel["FIT"].sum()), int(sel["FIT_EX_FITTING"].sum()),
                    int((sel["FIT"] & fm).sum())))


# ---------------------------------------------------------------- c12 ------
def c12_all_era_counts_are_not_doubled():
    """R115 — `for era in _eras(d8) + ["ALL"]` where `_eras` ALREADY returns
    "ALL", so every ALL-era count in REFUSED_FVOL_CENSUS.tsv was published at
    exactly 2x.  Fractions survived (both halves doubled) and the session sets
    are `set`s, which is precisely why it was invisible on inspection."""
    src = open(P1.__file__).read()
    code = "\n".join(ln for ln in src.split("\n")
                     if not ln.lstrip().startswith("#"))
    armed = ('for era in _eras(d8) + ["ALL"]:' not in code)
    armed &= ("for era in _eras(d8):" in code)
    # the arithmetic, made explicit on a stand-in accumulator
    eras = ["ALL", "FIT", "2021", "E1"]
    acc = {}
    for era in eras:                       # the CORRECT loop
        acc[era] = acc.get(era, 0) + 1
    mut = {}
    for era in eras + ["ALL"]:             # MUTANT: the loop that shipped
        mut[era] = mut.get(era, 0) + 1
    armed &= (acc["ALL"] == 1)
    mutant_ok = (mut["ALL"] == acc["ALL"])
    return check("all_era_counts_are_not_doubled",
                 "MT_R115_eras(d8)_plus_ALL_double_counts_the_ALL_bucket",
                 armed, mutant_ok,
                 "correct ALL count=%d; mutant ALL count=%d"
                 % (acc["ALL"], mut["ALL"]))


# ---------------------------------------------------------------- c13 ------
def c13_every_detector_draws_its_own_permutation_stream():
    """R116 — the destruction seed depended only on the TERM INDEX.

    `RandomState(DESTRUCTION_SEED + k)` meant arms A, B and P016 drew
    BYTE-IDENTICAL permutations against an identical session partition — and
    the partition is identical across files, so p020's three patterns and all
    nine of p025's readings reused the same draws.  The batch-level destruction
    evidence was ONE experiment reported many times.  Worse, p020 and p025
    DECLARED their own DESTRUCTION_SEED, interpolated it into PARAMS and hashed
    it into params_hash while `P1.destruction_rows` hardcoded p001's — the
    declared seeds were DEAD.
    """
    seeds = {}
    for tag in ("A", "B", "P016", "P020", "P021", "P025_A_nominal",
                "P023_ABS", "P007_A_60s_ledger"):
        for k in range(3):
            seeds[(tag, k)] = P1.destruction_seed(tag, k)
    armed = (len(set(seeds.values())) == len(seeds))
    # MUTANT: the term-index-only seed.  Every tag collides.
    mut = {(tag, k): P1.DESTRUCTION_SEED + k
           for tag, k in seeds}
    mutant_ok = (len(set(mut.values())) == len(mut))
    # the DECLARED seed must be the one actually USED
    s20 = open(P20.__file__).read()
    s25 = open(P25.__file__).read()
    armed &= "seed=DESTRUCTION_SEED" in s20
    armed &= "seed=DESTRUCTION_SEED" in s25
    armed &= (P20.DESTRUCTION_SEED != P1.DESTRUCTION_SEED)
    armed &= (P25.DESTRUCTION_SEED != P1.DESTRUCTION_SEED)
    a20 = P1.destruction_seed("P020", 0, base=P20.DESTRUCTION_SEED)
    a01 = P1.destruction_seed("P020", 0, base=P1.DESTRUCTION_SEED)
    armed &= (a20 != a01)
    return check("every_detector_draws_its_own_permutation_stream",
                 "MT_R116_RandomState(SEED+term_index)_shared_by_every_detector",
                 armed, mutant_ok,
                 "%d distinct seeds over %d (tag, term) pairs; term-index-only "
                 "mutant gives %d distinct; declared p020 seed changes the "
                 "stream (%d vs %d)"
                 % (len(set(seeds.values())), len(seeds),
                    len(set(mut.values())), a20, a01))


# ---------------------------------------------------------------- c14 ------
def c14_within_session_constant_terms_are_reported_degenerate():
    """R117 — within-session shuffling has ZERO power against a term that is
    constant within its session.

    Where the column is all-True the permutation is a LITERAL NO-OP, retention
    is exactly 1.0, and the code stamped TERM_NOT_LOAD_BEARING by construction
    — so the verdict was unfalsifiable for precisely the terms most likely to
    matter (P021 T1 `day_type == EXPANDED` and P024 T2 are near-constant within
    a session), and nothing detected or reported the degenerate case.
    """
    D = synth(n_sessions=60, n_per=10, seed=5)
    # T0 varies within a session; T1 is a SESSION PROPERTY (constant within it)
    n = D["dec_sec"].size
    t0 = (D["dec_sec"] % 1200) == 0
    t1 = np.repeat((np.arange(60) % 2 == 0), 10)
    T = np.column_stack([t0, t1])
    rows = P1.destruction_rows(D, T, "FIXTURE", names=("T0_varies",
                                                       "T1_session_constant"))
    by = {r[2]: r for r in rows if r[1] == "ALL"}
    deg = by["T1_session_constant"]
    var = by["T0_varies"]
    armed = (deg[19] == "DEGENERATE_within_session_constant"
             and deg[24] == 0)             # n_sessions_term_varies
    armed &= (var[24] > 0
              and var[19] != "DEGENERATE_within_session_constant")
    # the permutation really IS a no-op on the degenerate term
    cl = D["cluster"]
    order = np.argsort(cl, kind="stable")
    rs = np.random.default_rng(1)
    shuffled = P1._shuffle_within(t1[order], cl[order], rs)
    armed &= bool(np.array_equal(shuffled, t1[order]))
    # MUTANT: no degeneracy detection -> the retention band decides, and the
    # retention of a no-op is exactly 1.0, which the bands call NOT_LOAD_BEARING
    mutant_ok = (deg[19] in ("TERM_NOT_LOAD_BEARING", "PARTIAL",
                             "TERM_LOAD_BEARING"))
    # and the permutation-noise column must be NAMED as such
    armed &= ("edge_close_permutation_sd" in P1.DESTRUCTION_COLUMNS)
    armed &= ("edge_close_sd" not in P1.DESTRUCTION_COLUMNS)
    armed &= ("perm_p_close" in P1.DESTRUCTION_COLUMNS)
    return check("within_session_constant_terms_are_reported_degenerate",
                 "MT_R117_stamp_a_no_op_permutation_TERM_NOT_LOAD_BEARING",
                 armed, mutant_ok,
                 "constant term -> %s (sessions varying=%d); varying term -> "
                 "%s (sessions varying=%d); shuffle is a literal no-op=%s"
                 % (deg[19], deg[24], var[19], var[24],
                    bool(np.array_equal(shuffled, t1[order]))))


# ---------------------------------------------------------------- c15 ------
def c15_holdout_identities_can_never_be_exported():
    """R105 — `fire_rows` wrote `MC.era_of(d8)` = the literal "HOLDOUT_2025H2"
    cid-by-cid into the PUBLISHED P001_FIRES.tsv: holdout candidate IDENTITIES,
    exported.  The population is guarded now; this is the belt to that braces,
    because the failure was SILENT and the artifact was committed."""
    D = synth(n_sessions=40, n_per=5, seed=9)
    D = dict(D)
    D["d8"] = np.where(np.arange(D["d8"].size) < 5, 20250801,
                       D["d8"]).astype(np.int32)
    D["year"] = (D["d8"] // 10000).astype(np.int32)
    for k in ("coverage_phase", "slope_1m_usd", "accel_usd", "rv_ratio",
              "ext_needed_usd"):
        D[k] = np.zeros(D["d8"].size)
    for k in ("runway_phase_sec", "extreme_age_sec", "pivot_age_sec",
              "fph_sflow", "fph_vol", "f60_n", "ladder_band"):
        D[k] = np.zeros(D["d8"].size, dtype=np.int64)
    fire = np.arange(D["d8"].size) < 5      # only holdout rows fire
    raised = False
    try:
        P1.fire_rows(D, fire, "A")
    except MC.HoldoutRefusal:
        raised = True
    armed = raised
    # MUTANT: the export without the assertion.  It happily emits the cids,
    # stamped with the holdout era name.
    mut_rows = [MC.era_of(int(d)) for d in D["d8"][fire].tolist()]
    mutant_ok = not any(e == "HOLDOUT_2025H2" for e in mut_rows)
    # and a guarded population must still export normally
    D2 = dict(D)
    D2["d8"] = np.full(D["d8"].size, 20220103, dtype=np.int32)
    D2["year"] = (D2["d8"] // 10000).astype(np.int32)
    out = P1.fire_rows(D2, fire, "A")
    armed &= (len(out) == 5)
    return check("holdout_identities_can_never_be_exported",
                 "MT_R105_fire_rows_without_the_holdout_assertion",
                 armed, mutant_ok,
                 "export refused=%s; unguarded mutant would stamp %s"
                 % (raised, sorted(set(mut_rows))))


TESTS = (c01_a_mutant_that_loads_a_holdout_session_fails,
         c02_p025_holdout_boundary_is_20250701_not_20250901,
         c03_promotion_carries_an_interval_an_n_floor_and_a_family,
         c04_holm_family_is_the_whole_run_not_one_arm,
         c05_whole_session_aggregate_is_ineligible_for_promotion,
         c06_aggression_fraction_has_a_volume_floor,
         c07_refused_runways_get_their_own_band,
         c08_saturated_ext_leaves_the_breakout_reversion_contrast,
         c09_direction_claims_face_their_mirror,
         c10_gee_refuses_below_a_cluster_floor,
         c11_in_sample_thresholds_are_quantified_not_asserted,
         c12_all_era_counts_are_not_doubled,
         c13_every_detector_draws_its_own_permutation_stream,
         c14_within_session_constant_terms_are_reported_degenerate,
         c15_holdout_identities_can_never_be_exported)


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
    MC.write_tsv(os.path.join(OUT_DIR, "pcensus_fixlane_red_ledger.tsv"),
                 SECTION, MC.params_hash(P1.PARAMS),
                 ["test", "mutant", "armed_pass", "mutant_pass", "verdict",
                  "detail"], LEDGER,
                 extra=["RED-FIRST: armed_pass MUST be 1 and mutant_pass MUST "
                        "be 0 on every row",
                        "one row per numbered finding of "
                        "M2_CONSOLIDATED_REVIEW §3.2b (R105-R117)"])
    MC.write_json(os.path.join(OUT_DIR, "pcensus_fixlane.receipt.json"),
                  {"env": MC.env_receipt(P1.PARAMS), "n_tests": len(TESTS),
                   "n_failed": n_fail,
                   "holdout_from_d8": int(MC.HOLDOUT_FROM_D8),
                   "verdict": "PASS" if n_fail == 0 else "FAIL"})
    MC.hb("pcensus fix-lane tests: %d/%d passed"
          % (len(TESTS) - n_fail, len(TESTS)))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
