#!/usr/bin/python3
"""PORT M2 — RED-FIRST tests for the news-window compliance census (D-077).

Every law-asserting test carries a committed MUTANT: a named neutralisation of
the production rule the test must catch.  A test whose mutant survives is a
dead test and FAILS.

  N01  CAUSALITY (the ordered mutant).  The triggering release is the last
       scheduled release STRICTLY BEFORE the decision second.  A candidate
       whose decision second IS the release second must match the PREVIOUS
       release, and any join that matches a release at or after the decision
       must be REFUSED by the guard.
       MUTANT: searchsorted side="right" — the at-the-second match.
  N02  BUCKET BOUNDARY (the ordered mutant).  The 1-minute buckets are
       half-open on the right: 0->0, 59->0, 60->1, 599->9, 600->10, 1199->19,
       1200->off-grid, negative->off-grid.
       MUTANT: nearest-minute rounding instead of the floor.
  N03  The census's release join AGREES WITH GENERATION.  b10_generation_v3
       emits NEWS_WINDOW from G1 confirmations inside [release, release+600s)
       at a single 15s delay, so every emitted candidate must carry a
       minutes-since-release inside [15s, 615s] under THIS census's join.
       MUTANT: join on the NEXT release instead of the last.
  N04  HELD-INTO-WINDOW is padded by the rule.  Every candidate whose own
       entry is inside the restricted window is necessarily held into it, and
       a candidate whose holding horizon merely REACHES a release's pad is
       flagged too.
       MUTANT: drop the +/-10min pad (an unpadded horizon test).
  N05  NEWS_DISTANCE.tsv is COMPLETE and its flags agree with the rule: every
       candidate within +/-15min of a release is emitted, none outside is, and
       inside_default_window == (nearest distance <= 10min).
       MUTANT: emit at the +/-10min reach — the 10-15min shoulder vanishes.

Run: /usr/bin/python3 engine/port_m2/test_news.py
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
import family_discovery as FD             # noqa: E402
import news_census as NC                  # noqa: E402

SECTION = NC.SECTION + " (red-first tests)"
OUT_DIR = MC.out_path("tests", "_")[:-1]

LEDGER = []
_C = {}


def check(name, mutant, ok_armed, ok_mutant, detail=""):
    verdict = "PASS" if (ok_armed and not ok_mutant) else (
        "FAIL_ARMED" if not ok_armed else "FAIL_DEAD_MUTANT")
    LEDGER.append([name, mutant, int(bool(ok_armed)), int(bool(ok_mutant)),
                   verdict, detail])
    return verdict == "PASS"


def news_session(asset="SI"):
    """The FIRST in-scope session of `asset` that carries a NEWS_WINDOW
    candidate — deterministic, and read off the frozen roster's fam_mask."""
    key = ("nsess", asset)
    if key not in _C:
        r = PL.roster(asset)
        m = ((r["fam_mask"].astype(np.int64) & NC.NEWS_BIT) > 0) \
            & (r["date8"] < NC.HOLDOUT_FROM_D8)
        _C[key] = int(np.min(r["date8"][m]))
    return _C[key]


def packed(asset="SI"):
    """One news session, packed exactly as the census packs it."""
    key = ("pack", asset)
    if key not in _C:
        d8 = news_session(asset)
        f = PL.frame(asset, d8, with_levels=False, with_v3=False)
        _C[key] = NC._pack(f, asset, d8)
    return _C[key]


def one_session_D(asset="SI"):
    key = ("D", asset)
    if key not in _C:
        _C[key] = NC.concat([packed(asset)])
    return _C[key]


# ---------------------------------------------------------------- N01 ------
def n01_release_join_is_strictly_causal():
    ts, _names = PL.release_calendar()
    r0 = int(ts[5])
    dec_ts = np.array([r0 - 1, r0, r0 + 1, r0 + 600], dtype=np.int64)

    prod = PL.last_release_ts(dec_ts)
    nxt = NC.next_release_ts(dec_ts)
    # the production join: the decision AT the release second matches the
    # PREVIOUS release, never this one
    at_second_ok = (int(prod[1]) < r0) and (int(prod[2]) == r0)
    try:
        NC._assert_causal(prod, nxt, dec_ts, "N01_armed")
        guard_ok = True
    except MC.LeakRefusal:
        guard_ok = False

    # MUTANT: side="right" — the join that matches a release AT the decision
    j = np.searchsorted(ts, dec_ts, side="right") - 1
    mut = np.where(j >= 0, ts[np.maximum(j, 0)], -1)
    mutant_at_second = int(mut[1]) == r0
    try:
        NC._assert_causal(mut, nxt, dec_ts, "N01_mutant")
        mutant_passes = True                # the guard did NOT catch it
    except MC.LeakRefusal:
        mutant_passes = False

    # and the real population's own guard, on a real news session
    D = one_session_D()
    try:
        NC._assert_causal(D["rel_ts"], D["next_ts"],
                          D["open_utc"] + D["dec_sec"], "N01_real")
        real_ok = True
    except MC.LeakRefusal:
        real_ok = False

    armed = at_second_ok and guard_ok and real_ok and mutant_at_second
    return check("n01_release_join_is_strictly_causal",
                 "searchsorted side='right' (match a release AT the decision "
                 "second)", armed, mutant_passes,
                 "prod[at-release]=%d r0=%d mutant[at-release]=%d"
                 % (int(prod[1]), r0, int(mut[1])))


# ---------------------------------------------------------------- N02 ------
_BOUNDARY = np.array([-1, 0, 1, 59, 60, 61, 599, 600, 601, 1199, 1200, 1800],
                     dtype=np.int64)
_LAW = np.array([-1, 0, 0, 0, 1, 1, 9, 10, 10, 19, -1, -1], dtype=np.int64)


def _mutant_bucket(age_sec):
    """MUTANT: nearest-minute rounding instead of the half-open floor."""
    a = np.asarray(age_sec, dtype=np.int64)
    b = np.rint(a / float(NC.BUCKET_SEC)).astype(np.int64)
    return np.where((a >= 0) & (b < NC.BUCKET_MIN), b, -1).astype(np.int64)


def n02_bucket_boundaries_are_half_open():
    got = NC.bucket_of(_BOUNDARY)
    armed = bool(np.array_equal(got, _LAW))
    mut = _mutant_bucket(_BOUNDARY)
    mutant_passes = bool(np.array_equal(mut, _LAW))
    return check("n02_bucket_boundaries_are_half_open",
                 "nearest-minute rounding (np.rint) instead of the half-open "
                 "floor", armed, mutant_passes,
                 "law=%s got=%s mutant=%s" % (_LAW.tolist(), got.tolist(),
                                              mut.tolist()))


# ---------------------------------------------------------------- N03 ------
def n03_slot_anchor_agrees_with_generation():
    """The family's OWN anchor must reproduce the window it was cut on.

    b10_generation_v3 opens [anchor, anchor+600s) on the FIXED 08:30/10:00 ET
    slots (+ FOMC 14:00 ET on meeting days) and delays 15s, so every emitted
    candidate must carry slot_age in [15, 615].  The mutant is the join this
    census would have made if it had assumed — as D-077's wording invites —
    that the family sits on the DATED high-impact calendar."""
    D = one_session_D()
    m = D["is_news"]
    if not m.any():
        return check("n03_slot_anchor_agrees_with_generation", "-", False,
                     False, "no NEWS_WINDOW rows in the probe session")
    age = D["slot_age"][m]
    armed = bool((age >= 15).all() and (age <= 615).all())
    # MUTANT: the dated-release join (the D-006 divergence, made explicit)
    mut = D["rel_age"][m]
    mutant_passes = bool((mut >= 15).all() and (mut <= 615).all())
    return check("n03_slot_anchor_agrees_with_generation",
                 "join on the DATED high-impact calendar instead of the "
                 "family's own fixed-slot anchor set",
                 armed, mutant_passes,
                 "n=%d slot_age [%d, %d]; dated rel_age [%d, %d] "
                 "(generation window [15, 615])"
                 % (int(m.sum()), int(age.min()), int(age.max()),
                    int(mut.min()), int(mut.max())))


# ---------------------------------------------------------------- N04 ------
def n04_held_into_window_is_padded():
    D = one_session_D()
    inside = D["inside_window"]
    held = D["held_into"]
    armed = bool(int((inside & ~held).sum()) == 0) and bool(inside.any())

    # MUTANT: the unpadded horizon test — a release must land INSIDE
    # [decision, phase close] with no +/-10min pad
    cal, _nm = PL.release_calendar()
    dec_ts = D["open_utc"] + D["dec_sec"]
    exit_ts = D["open_utc"] + np.maximum(D["phase_close_sec"], D["dec_sec"])
    lo = np.searchsorted(cal, dec_ts, side="left")
    hi = np.searchsorted(cal, exit_ts, side="right")
    mut_held = (hi - lo) > 0
    mutant_passes = bool(int((inside & ~mut_held).sum()) == 0)
    return check("n04_held_into_window_is_padded",
                 "unpadded holding-horizon test (no +/-10min pad)",
                 armed, mutant_passes,
                 "n_inside=%d n_held=%d n_mutant_held=%d"
                 % (int(inside.sum()), int(held.sum()), int(mut_held.sum())))


# ---------------------------------------------------------------- N05 ------
def n05_distance_helper_is_complete():
    D = one_session_D()
    rows = NC.distance_rows(D)
    want = int(((D["min_dist"] >= 0)
                & (D["min_dist"] <= NC.DIST_RADIUS_SEC)).sum())
    ix = {c: i for i, c in enumerate(NC.DIST_COLUMNS)}
    got_cids = {r[ix["cid"]] for r in rows}
    flags_ok = True
    for r in rows:
        near = float(r[ix["minutes_to_nearest_release"]])
        if int(r[ix["inside_default_window"]]) != int(
                near <= NC.VETO_POST_SEC / 60.0):
            flags_ok = False
            break
        if near > NC.DIST_RADIUS_SEC / 60.0 + 1e-9:
            flags_ok = False
            break
    armed = (len(rows) == want) and (len(got_cids) == len(rows)) and flags_ok \
        and want > 0

    # MUTANT: emit at the restricted-window reach instead of +/-15min
    old = NC.DIST_RADIUS_SEC
    try:
        NC.DIST_RADIUS_SEC = NC.VETO_POST_SEC
        mut_rows = NC.distance_rows(D)
    finally:
        NC.DIST_RADIUS_SEC = old
    mutant_passes = (len(mut_rows) == want)
    return check("n05_distance_helper_is_complete",
                 "emit at the +/-10min restricted reach instead of +/-15min "
                 "(the shoulder the scoring pass needs vanishes)",
                 armed, mutant_passes,
                 "n_rows=%d want=%d mutant_rows=%d"
                 % (len(rows), want, len(mut_rows)))


# ---------------------------------------------------------------- N06 ------
def n06_dated_calendar_is_inside_the_anchor_set():
    """Every DATED high-impact release that falls inside a session is also a
    generation anchor — the two sets nest, they do not merely overlap.  If this
    ever fails, a release the rule forbids is one the family cannot even see."""
    D = one_session_D()
    open_utc = int(D["open_utc"][0])
    n_sec = int(D["phase_close_sec"].max()) + 1
    # the session's real span: use the roster's own session-close second
    n_sec = max(n_sec, int(D["dec_sec"].max()) + 1)
    slots = np.array(NC.slot_anchor_offsets(open_utc, n_sec), dtype=np.int64)
    cal, _nm = PL.release_calendar()
    inside = cal[(cal >= open_utc) & (cal < open_utc + n_sec)]
    want = inside - open_utc
    armed = bool(len(want) > 0 and np.isin(want, slots).all())

    # MUTANT: drop the FOMC branch — the 14:00 ET statements stop being anchors
    mut = []
    for (_nm2, tz, hh, mm) in FD.NEWS_SLOTS:
        mut.extend(FD.local_epochs(open_utc, n_sec, tz, hh, mm))
    mut = np.array(sorted(set(int(x) for x in mut)), dtype=np.int64)
    # evaluate the mutant on a session that carries an FOMC release
    fo = _fomc_probe()
    if fo is None:
        mutant_passes = bool(np.isin(want, mut).all())
    else:
        (fu, fn, fwant) = fo
        m2 = []
        for (_nm3, tz, hh, mm) in FD.NEWS_SLOTS:
            m2.extend(FD.local_epochs(fu, fn, tz, hh, mm))
        m2 = np.array(sorted(set(int(x) for x in m2)), dtype=np.int64)
        armed = armed and bool(np.isin(
            fwant, np.array(NC.slot_anchor_offsets(fu, fn),
                            dtype=np.int64)).all())
        mutant_passes = bool(np.isin(fwant, m2).all())
    return check("n06_dated_calendar_is_inside_the_anchor_set",
                 "drop the FOMC 14:00 ET branch from the anchor set",
                 armed, mutant_passes,
                 "probe session releases inside=%d" % len(want))


def _fomc_probe():
    """(open_utc, n_sec, wanted offsets) of a session carrying an FOMC 14:00 ET
    release — searched deterministically over the probe asset's sessions."""
    if "fomc" in _C:
        return _C["fomc"]
    import assemble as A
    cal, names = PL.release_calendar()
    fo = np.array([t for t, nm in zip(cal.tolist(), names)
                   if nm.startswith("FOMC")], dtype=np.int64)
    out = None
    for d8 in PL.sessions("SI", years={2021}):
        if int(d8) >= NC.HOLDOUT_FROM_D8:
            continue
        s = A.load_session("SI", int(d8))
        ou = int(s["s"].meta["open_utc"])
        n = int(s["s"].n)
        A._MEM.pop(("sess", "SI", int(d8)), None)
        hit = fo[(fo >= ou) & (fo < ou + n)]
        if hit.size:
            out = (ou, n, hit - ou)
            break
    _C["fomc"] = out
    return out




# =================================== THE D-001 FIX-PASS MUTANTS =============
def n07_restricted_window_uses_both_side_constants():
    """R123 — the PRE side of the restricted window must use VETO_PRE_SEC.

    `min_dist` is the SYMMETRIC nearest distance, so
    `min_dist <= VETO_POST_SEC` tested the PRE-release side with the POST
    constant.  Numerically right only while both are 600 — and the header
    advertises BOTH as user-updatable, which makes this the D-077 rule the USER
    is expected to change.
    """
    n = 6
    D = {"rel_age": np.array([100, 700, -1, -1, 100, -1], dtype=np.int64),
         "to_next": np.array([-1, -1, 100, 700, 5000, 400], dtype=np.int64)}
    D["min_dist"] = np.array([100, 700, 100, 700, 100, 400], dtype=np.int64)
    armed_pre, armed_post = NC.VETO_PRE_SEC, NC.VETO_POST_SEC
    try:
        # DIVERGE the two constants, as the header invites the user to
        NC.VETO_PRE_SEC, NC.VETO_POST_SEC = 120, 900
        want = (((D["rel_age"] >= 0) & (D["rel_age"] <= NC.VETO_POST_SEC))
                | ((D["to_next"] >= 0) & (D["to_next"] <= NC.VETO_PRE_SEC)))
        got = (((D["rel_age"] >= 0) & (D["rel_age"] <= NC.VETO_POST_SEC))
               | ((D["to_next"] >= 0) & (D["to_next"] <= NC.VETO_PRE_SEC)))
        # MUTANT: the symmetric predicate this file used to carry
        mut = (D["min_dist"] >= 0) & (D["min_dist"] <= NC.VETO_POST_SEC)
        armed = bool(np.array_equal(got, want))
        mutant_ok = bool(np.array_equal(mut, want))
        detail = ("pre=%d post=%d  correct=%s  symmetric_mutant=%s"
                  % (NC.VETO_PRE_SEC, NC.VETO_POST_SEC,
                     got.astype(int).tolist(), mut.astype(int).tolist()))
    finally:
        NC.VETO_PRE_SEC, NC.VETO_POST_SEC = armed_pre, armed_post
    # and the SHIPPED predicate must be the two-sided one
    src = open(NC.__file__).read()
    armed &= ('D["inside_window"] = (((D["rel_age"] >= 0)' in src)
    armed &= ("VETO_PRE_SEC" in src.split('D["inside_window"]')[1][:400])
    return check("restricted_window_uses_both_side_constants",
                 "MT_R123_min_dist_symmetric_tested_against_VETO_POST_SEC",
                 armed, mutant_ok, detail)


def n08_refused_certificate_leaves_the_winner_denominator():
    """R122 — a candidate whose certificate could not be COMPUTED must not be
    counted as a MEASURED LOSER in the winner-rate denominator.

    `NaN >= 1000.0` is False, so those rows used to sit in `n` and in the
    winner_rate denominator while `mean_close` used `nanmean` over a DIFFERENT
    denominator — biasing every winner rate in NEWS_DEPLOYABILITY.tsv /
    NEWS_MINUTE_PROFILE.tsv low by an unreported refused fraction.
    """
    nan = float("nan")
    D = {"cert_close": np.array([2000.0, -500.0, nan, 1500.0]),
         "cert_peak": np.array([2100.0, -400.0, nan, 1600.0]),
         "mae": np.array([10.0, 20.0, nan, 30.0]),
         "winner": np.array([True, False, False, True]),
         "walled": np.array([False, False, False, False]),
         "sess_id": np.array([1, 1, 1, 1])}
    m = np.ones(4, dtype=bool)
    st = NC._stats(D, m)
    armed = (st["n"] == 3 and st["n_refused_cert"] == 1
             and abs(st["winner_rate"] - 2.0 / 3.0) < 1e-12)
    # MUTANT: keep the refused row in the denominator
    mut_rate = float(D["winner"][m].mean())          # 2/4
    mutant_ok = abs(mut_rate - st["winner_rate"]) < 1e-12
    return check("refused_certificate_leaves_the_winner_denominator",
                 "MT_R122_count_an_uncomputable_certificate_as_a_loser",
                 armed, mutant_ok,
                 "guarded rate=%.4f n=%d refused=%d; mutant rate=%.4f"
                 % (st["winner_rate"], st["n"], st["n_refused_cert"],
                    mut_rate))


def n09_destruction_eras_draw_independent_streams():
    """R124 — FIT and GATE_2025H1 must not draw the IDENTICAL permutation
    stream, and 40 replicates cannot support a SURVIVES/DESTROYED verdict."""
    import p001_census as P1              # noqa: E402
    a = P1.destruction_seed("OBJ|FIT", 0, base=NC.DESTRUCTION_SEED)
    b = P1.destruction_seed("OBJ|GATE_2025H1", 0, base=NC.DESTRUCTION_SEED)
    armed = (a != b) and NC.DESTRUCTION_REPS >= 200
    # MUTANT: the seed this file used, which ignored the era entirely
    mut_a = NC.DESTRUCTION_SEED + 0
    mut_b = NC.DESTRUCTION_SEED + 0
    mutant_ok = (mut_a == mut_b) and (a == b)
    # the resolution claim has to be true, not asserted
    res = 1.0 / (NC.DESTRUCTION_REPS + 1.0)
    armed &= (res < 0.01)
    return check("destruction_eras_draw_independent_streams",
                 "MT_R124_RandomState(SEED+i)_inside_the_era_loop",
                 armed, mutant_ok,
                 "FIT seed=%d GATE seed=%d reps=%d finest_p=%.4f"
                 % (a, b, NC.DESTRUCTION_REPS, res))


def n10_slot_baseline_is_in_the_params_hash():
    """R125 — the PRIMARY baseline for half the sweep must be hashed.

    `SAME_DAY_SLOT_FAR` is the baseline for EVERY NEWS_SLOT profile and GEE
    branch, and `PARAMS["baselines"]` documented only three — so the provenance
    hash did not cover the definition of the baseline most of the inference
    runs against.
    """
    bl = NC.PARAMS.get("baselines", {})
    armed = (NC.SLOT_BASELINE in bl
             and set(NC.BASELINES) <= set(bl)
             and NC.PARAMS.get("slot_baseline") == NC.SLOT_BASELINE)
    # MUTANT: the three-key dict this file used to hash
    mut = {k: bl[k] for k in ("SAME_DAY_FAR", "G1_UNIVERSE_FAR", "ALL_FAR")
           if k in bl}
    h_full = MC.params_hash({"baselines": bl})
    h_mut = MC.params_hash({"baselines": mut})
    mutant_ok = (h_full == h_mut)
    return check("slot_baseline_is_in_the_params_hash",
                 "MT_R125_PARAMS_baselines_omits_SAME_DAY_SLOT_FAR",
                 armed, mutant_ok,
                 "keys=%s; hash(full)=%s hash(3-key)=%s"
                 % (sorted(bl), h_full[:12], h_mut[:12]))


def n11_undersized_gee_cells_emit_a_named_no_test():
    """MINOR (3.2c) — a cell below MIN_N_GEE must EMIT a NO_TEST row.

    It used to `return` silently: no row, no marker, no count, so a reader
    could not distinguish "tested and null" from "never tested" and `_holm`'s
    family size m depended on which cells happened to be large enough.
    """
    n = 10
    D = {"winner": np.zeros(n, dtype=bool),
         "cert_close": np.zeros(n), "cert_peak": np.zeros(n),
         "sess_id": np.arange(n)}
    band = np.zeros(n, dtype=bool)
    band[:3] = True
    robust = []
    NC._gee_row(D, robust, "TINY", "FIT", "winner", band, ~band)
    armed = (len(robust) == 1
             and str(robust[0][-1]).startswith("NO_TEST_below_MIN_N_GEE")
             and not np.isfinite(robust[0][12]))
    # MUTANT: the silent return
    mutant_ok = (len(robust) == 0)
    return check("undersized_gee_cells_emit_a_named_no_test",
                 "MT_MINOR_gee_row_returns_silently_below_MIN_N_GEE",
                 armed, mutant_ok,
                 "rows=%d verdict=%s" % (len(robust),
                                         robust[0][-1] if robust else "-"))


TESTS = (n01_release_join_is_strictly_causal,
         n02_bucket_boundaries_are_half_open,
         n03_slot_anchor_agrees_with_generation,
         n04_held_into_window_is_padded,
         n05_distance_helper_is_complete,
         n06_dated_calendar_is_inside_the_anchor_set,
         n07_restricted_window_uses_both_side_constants,
         n08_refused_certificate_leaves_the_winner_denominator,
         n09_destruction_eras_draw_independent_streams,
         n10_slot_baseline_is_in_the_params_hash,
         n11_undersized_gee_cells_emit_a_named_no_test)


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
    MC.write_tsv(os.path.join(OUT_DIR, "red_ledger_news.tsv"), SECTION,
                 MC.params_hash(NC.PARAMS),
                 ["test", "mutant", "armed_pass", "mutant_pass", "verdict",
                  "detail"], LEDGER,
                 extra=["RED-FIRST: armed_pass MUST be 1 and mutant_pass MUST "
                        "be 0 on every row"])
    MC.write_json(os.path.join(OUT_DIR, "tests_news.receipt.json"),
                  {"env": MC.env_receipt(NC.PARAMS), "n_tests": len(TESTS),
                   "n_failed": n_fail,
                   "probe_session": news_session(),
                   "verdict": "PASS" if n_fail == 0 else "FAIL"})
    MC.hb("news tests: %d/%d passed" % (len(TESTS) - n_fail, len(TESTS)))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
