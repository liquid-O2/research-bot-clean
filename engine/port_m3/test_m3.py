#!/usr/bin/python3
"""PORT M3 — the harness's own tests, RED-FIRST where the brief names a red.

    "red-first (a holdout row in the matrix must be caught; a future-feature
     mutant must be caught)"                                       — the brief

THE TWO REDS, and how each is proved to have teeth
  R1  HOLDOUT ROW.  t01 plants a pre-exam-holdout session stamp in a matrix and
      asserts `m3_common.check_holdout` REFUSES.  t02 proves the guard is not
      vacuous the other way (a clean matrix passes) and t03 proves the
      ENUMERATOR itself refuses, so the guard is a second lock and not the only
      one.
  R2  FUTURE-FEATURE MUTANT.  t04 plants the walled certificate as a feature
      under an innocent NAME and asserts the VALUE guard refuses; t05 plants it
      under its OWN name and asserts the NAME guard refuses; t06 proves the
      value guard passes the real matrix's own columns (non-vacuous).
  THE RED-FIRST PROOF IS MECHANICAL, NOT PROSE.  `--red-first` replaces each
  guard with the no-op it would be if it had never been written and asserts
  that BOTH reds then FAIL — so "the test has teeth" is re-derivable at any
  commit instead of being a claim about what happened once.  It writes its own
  receipt beside the matrix.

Everything else here is formula fidelity: the harness must reproduce the
committed numbers of the modules it stands on, or it is a second definition.

Run:  test_m3.py [--fast]
"""
import argparse
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m0", "/workspace/engine/port_m1",
           "/workspace/engine/port_m2"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import m3_common as M3                    # noqa: E402
import m3_matrix as MX                    # noqa: E402
import m2_common as MC                    # noqa: E402
import pattern_lib as PL                  # noqa: E402
import assemble as A                      # noqa: E402
import batch4_census as B4                # noqa: E402
import panel_score as PS                  # noqa: E402
import c_c_roster as CC                   # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("%-4s %-46s %s" % ("PASS" if ok else "FAIL", name, detail))
    return bool(ok)


# ======================================================= R1 the holdout red ==
def t01_holdout_row_is_refused():
    d8 = np.array([20240115, 20240116, M3.HOLDOUT_FROM_D8, 20240117])
    try:
        M3.check_holdout(d8)
    except M3.HarnessRefusal as e:
        return check("t01_holdout_row_is_refused", "HOLDOUT GUARD" in str(e),
                     str(e)[:70])
    return check("t01_holdout_row_is_refused", False,
                 "the guard PASSED a holdout row — the red does not fire")


def t02_clean_matrix_passes():
    n = M3.check_holdout(np.array([20210701, 20250630]))
    return check("t02_clean_matrix_passes", n == 2, "n=%d" % n)


def t03_enumerator_refuses_holdout():
    try:
        PL.sessions(M3.ASSET_ORDER[0])
    except MC.HoldoutRefusal as e:
        keep, nq = PL.sessions_fit(M3.ASSET_ORDER[0])
        return check("t03_enumerator_refuses_holdout", nq > 0,
                     "%d quarantined; %s" % (nq, str(e)[:40]))
    return check("t03_enumerator_refuses_holdout", False,
                 "sessions() did not refuse")


# ================================================== R2 the future-feature red
def _tiny_matrix(n=4000, seed=7):
    rs = np.random.RandomState(seed)
    y = rs.normal(size=n) * 500.0
    # harmless_b is a REAL correlate of the outcome (rho ~ 0.3), not a copy of
    # it — the point of the non-vacuity test is that honest predictive signal
    # passes and only a reproduction of the outcome fails.
    X = np.column_stack([rs.normal(size=n),
                         rs.normal(size=n) + 0.3 * (y / 500.0)])
    return X.astype(np.float32), {"cert_close_usd": y, "winner": (y > 500)
                                  .astype(float)}


def t04_future_value_mutant_is_refused():
    X, out = _tiny_matrix()
    # THE MUTANT: an innocent-looking column that IS the forward certificate.
    Xm = np.column_stack([X, out["cert_close_usd"].astype(np.float32)])
    names = ["harmless_a", "harmless_b", "rv1800_usd"]
    try:
        M3.check_forward_values(names, Xm.astype(np.float32), out)
    except M3.HarnessRefusal as e:
        return check("t04_future_value_mutant_is_refused",
                     "rv1800_usd" in str(e), str(e)[:70])
    return check("t04_future_value_mutant_is_refused", False,
                 "a column identical to cert_close PASSED the value guard")


def t05_future_name_mutant_is_refused():
    feats = list(MX.FEATURES) + [MX._F("innocuous", "flow", "cert_close_usd",
                                       "the mutant")]
    try:
        M3.check_forbidden_names(feats)
    except M3.HarnessRefusal as e:
        return check("t05_future_name_mutant_is_refused",
                     "innocuous" in str(e), str(e)[:70])
    return check("t05_future_name_mutant_is_refused", False,
                 "a feature sourced on cert_close_usd PASSED the name guard")


def t06_value_guard_is_not_vacuous():
    X, out = _tiny_matrix()
    hits = M3.check_forward_values(["harmless_a", "harmless_b"], X, out)
    return check("t06_value_guard_is_not_vacuous", hits == [],
                 "clean columns pass (%d hits)" % len(hits))


def t07_registry_is_clean_at_head():
    n = M3.check_forbidden_names(MX.FEATURES)
    return check("t07_registry_is_clean_at_head", n == len(MX.FEATURES),
                 "%d features, none forbidden" % n)


# =============================================== formula fidelity (D-006) ====
def t08_mfe_unwalled_is_mfe_at_sess_close():
    """The atlas champion's denominator: retg|e30|sess_close needs mfe at the
    SESSION-CLOSE mark.  The roster's `mfe_unwalled` is the running-max
    skeleton's last record, and the sess_close mark is the session's last
    second, so the two are the same object.  Proved, not assumed."""
    bad = 0
    seen = 0
    for asset in M3.ASSET_ORDER:
        r = A.roster(asset)
        idx = np.arange(0, r["date8"].size, max(1, r["date8"].size // 400))
        for i in idx.tolist():
            fo, fl = int(r["f_off"][i]), int(r["f_len"][i])
            mark = int(r["sess_close_sec"][i])
            if fl == 0:
                v = 0.0
            else:
                ft = r["skel_f_t"][fo:fo + fl]
                fv = r["skel_f_v"][fo:fo + fl]
                j = int(np.searchsorted(ft, mark, side="right")) - 1
                v = float(fv[j]) if j >= 0 else 0.0
            seen += 1
            if not np.isclose(v, float(r["mfe_unwalled"][i]), rtol=0,
                              atol=1e-9):
                bad += 1
    return check("t08_mfe_unwalled_is_mfe_at_sess_close", bad == 0,
                 "%d/%d rows disagree" % (bad, seen))


def t09_retg_matches_the_atlas_formula():
    """retg|e30 = net/max(mfe, 30*cost), NaN where mfe < 30*cost (s4_labels
    §B3, mover-gated).  Recomputed here from first principles on a real
    session and compared with the matrix builder's own column."""
    asset, d8 = "SI", 20240115
    p = MX._pack_session(asset, d8)
    R = MX._concat([p])
    ep, _r, _f, _n = MX.episode_keys(R)
    Y = MX.build_targets(R, ep)
    cost = R["cost_rt"]
    eps = 30.0 * cost
    net = R["f_sess_close"] - cost
    mfe = R["mfe_unwalled"]
    want = np.where(mfe < eps, np.nan, net / np.maximum(mfe, eps))
    got = Y["y_retg_raw"]
    m = np.isfinite(want) | np.isfinite(got)
    ok = bool(np.allclose(np.nan_to_num(want[m], nan=-9e9),
                          np.nan_to_num(got[m], nan=-9e9), rtol=0, atol=1e-12))
    gated = int(np.isnan(got).sum())
    return check("t09_retg_matches_the_atlas_formula", ok,
                 "n=%d, mover-gated out=%d" % (int(m.sum()), gated))


def t10_rank_transform_is_within_phase():
    asset, d8 = "SI", 20240115
    p = MX._pack_session(asset, d8)
    R = MX._concat([p])
    ep, _r, _f, _n = MX.episode_keys(R)
    Y = MX.build_targets(R, ep)
    rk, raw = Y["y_retg_rank_phase"], Y["y_retg_raw"]
    ok = True
    detail = ""
    for ph in sorted(set(R["phase_dec"].tolist())):
        m = (R["phase_dec"] == ph) & np.isfinite(raw)
        if int(m.sum()) < 3:
            continue
        a, b = raw[m], rk[m]
        # a strictly monotone map inside the unit, and a percentile range
        o = np.argsort(a, kind="stable")
        if not np.all(np.diff(b[o]) >= -1e-12):
            ok = False
            detail = "not monotone in phase %d" % ph
        if not (0.0 < float(b.min()) and float(b.max()) < 1.0):
            ok = False
            detail = "range %.4f..%.4f in phase %d" % (b.min(), b.max(), ph)
    return check("t10_rank_transform_is_within_phase", ok,
                 detail or "monotone + (0,1) inside every phase unit")


def t11_dp_ceiling_matches_panel_score():
    """The harness computes the day ceiling from the matrix's own certificate
    columns; panel_score computes it from the roster, candidate by candidate.
    Same frozen dp_schedule, so the two must agree exactly."""
    import m3_walk as MW
    asset, d8 = "SI", 20240115
    p = MX._pack_session(asset, d8)
    R = MX._concat([p])
    D = {"session": np.array(["%s|%08d" % (asset, d8)] * R["dec_sec"].size),
         "dec_sec": R["dec_sec"], "exit_close_sec": R["exit_close_sec"],
         "cert_close_usd": R["cert_close_usd"],
         "cert_refused": R["cert_refused"]}
    got = MW.dp_ceilings(D)["%s|%08d" % (asset, d8)]
    want = PS.dp_ceiling(asset, d8, "close")
    ok = np.isclose(got[0], want[0], rtol=0, atol=1e-6)
    return check("t11_dp_ceiling_matches_panel_score", ok,
                 "m3=%.2f panel_score=%.2f (n=%d/%d)"
                 % (got[0], want[0], got[1], want[2]))


def t12_episode_pins_hold():
    import baseline_replay as BR
    try:
        kst, spn = BR.episode_pins(check=True)
    except Exception as e:                 # noqa: BLE001
        return check("t12_episode_pins_hold", False, str(e)[:70])
    return check("t12_episode_pins_hold", len(kst) == 6 and len(spn) == 6,
                 "K*=%d SPAN=%d cells" % (len(kst), len(spn)))


def t13_day_gap_vectorised_matches_batch4():
    a = np.array([20210730, 20211231, 20240229, 20220101])
    b = np.array([20210801, 20220103, 20240301, 20211230])
    want = np.array([B4._day_gap(int(x), int(y)) for x, y in zip(a, b)])
    got = np.abs(MX._ordinal(a) - MX._ordinal(b))
    return check("t13_day_gap_vectorised_matches_batch4",
                 bool(np.array_equal(want, got)),
                 "%s vs %s" % (want.tolist(), got.tolist()))


def t14_no_feature_reads_a_forward_field():
    """Every declared source must exist on the causal frame (or be one of the
    joins), so a feature cannot quietly name a receipt column that is not in
    the causal pack at all."""
    known = set(MX.RAW_KEYS) | set(MX._RAW_STR) | {
        "asset", "d8", "open_utc", "xa_age", "xa_rv1800",
        "xa_fuel_share_above", "xa_range_so_far", "xa_slope5m",
        "xa_sflow_phase", "fc_available", "fc_anchor_age_sec",
        "nd_in_census", "ep_is_earliest", "ep_rank", "ep_age_sec",
        "cell_rank_so_far", "sess_rank_so_far", "cell_open"}
    known |= {"fc_" + c for c in MX.FC_COLS}
    known |= {"nd_" + c for c in MX.ND_COLS}
    unknown = sorted({s for f in MX.FEATURES for s in f.sources
                      if s not in known})
    return check("t14_no_feature_reads_a_forward_field", not unknown,
                 "undeclared sources: %s" % unknown[:6])


def t15_targets_exclude_refused_certificates():
    asset, d8 = "SI", 20240115
    p = MX._pack_session(asset, d8)
    R = MX._concat([p])
    ep, _r, _f, _n = MX.episode_keys(R)
    Y = MX.build_targets(R, ep)
    ref = R["cert_refused"] != 0
    ok = (not np.isfinite(Y["y_winner"][ref]).any()
          and not np.isfinite(Y["y_t1_episode"][ref]).any())
    return check("t15_targets_exclude_refused_certificates", ok,
                 "%d refused rows carry NaN in the winner/T1 targets"
                 % int(ref.sum()))


def t16_borda_is_a_preference_share():
    v = np.array([10.0, 20.0, 20.0, 5.0, 1.0])
    g = np.array([0, 0, 0, 0, 1], dtype=np.int64)
    ok_v = np.array([True] * 5)
    b = MX._borda(v, g, ok_v)
    want = np.array([1.0 / 3.0, (2 + 0.5) / 3.0, (2 + 0.5) / 3.0, 0.0, np.nan])
    ok = bool(np.allclose(b[:4], want[:4], atol=1e-12)) and np.isnan(b[4])
    return check("t16_borda_is_a_preference_share", ok,
                 "%s (singleton -> NaN)" % np.round(b[:4], 4).tolist())


def t17_determinism_two_builds_agree():
    asset, d8 = "HG", 20230612
    a = MX._pack_session(asset, d8)
    b = MX._pack_session(asset, d8)
    bad = [k for k in MX.RAW_KEYS
           if not np.array_equal(np.nan_to_num(a[k], nan=-9e9),
                                 np.nan_to_num(b[k], nan=-9e9))]
    return check("t17_determinism_two_builds_agree", not bad,
                 "%d fields, %d disagree" % (len(MX.RAW_KEYS), len(bad)))


def t18_no_teacher_flag_is_true_and_measurable():
    """The D-078 INSTRUMENT, in both of its states.

    Before the teacher round landed this asserted an EMPTY group.  The group is
    now populated, so what the test protects is the property that actually
    makes the instrument work and that a mutant would break: the flag is
    COMPUTED from the registry (never a hand-set constant), the group is
    declared, and every shipped teacher column is (a) named `tf_*`, (b) in the
    group, and (c) reads no §4-FALSIFIED cue as a standalone evidence column.
    """
    n_teacher = sum(1 for f in MX.FEATURES if f.group == "teacher_evidence")
    names = {f.name for f in MX.FEATURES if f.group == "teacher_evidence"}
    banned = {"tf_one_sided_flow", "tf_flow_agree_5m", "tf_fuel_trapped",
              "tf_expanding", "tf_level_tested_held", "tf_fresh_extreme",
              "tf_event_burst"}
    ok = ("teacher_evidence" in MX.GROUPS
          and MX.NO_TEACHER == (n_teacher == 0)
          and n_teacher == MX.N_TEACHER
          and all(n.startswith("tf_") for n in names)
          and not (names & banned))
    return check("t18_no_teacher_flag_is_true_and_measurable", ok,
                 "D-078 instrument: %d teacher column(s), NO_TEACHER=%s"
                 % (n_teacher, MX.NO_TEACHER))


def t19_news_veto_uses_census_flags():
    """CC-M2-22.4: compliance is read from the NEWS_DISTANCE flags, never
    inferred from a blank field.  The matrix must carry both the census join
    and the signed distance the veto is computed on."""
    have = set(MX.FEATURE_NAMES)
    need = {"in_news_window", "nd_in_census", "nd_held_into_window",
            "mins_to_release", "post_news_10_20"}
    return check("t19_news_veto_uses_census_flags", need <= have,
                 "missing %s" % sorted(need - have))


def t20_forecaster_is_typed_missing_pre_instrument(matrix_dir=None):
    p = os.path.join(matrix_dir or M3.MATRIX_DIR, "matrix.npz")
    if not os.path.exists(p):
        return check("t20_forecaster_is_typed_missing_pre_instrument", True,
                     "SKIPPED (no built matrix)")
    z = np.load(p, allow_pickle=False)
    names = [str(x) for x in z["feature_names"].tolist()]
    era = z["era_idx"]
    j = names.index("fc_available")
    k = names.index("fc_p_expansion")
    e1 = z["X"][era == 0, j]
    late = z["X"][era >= 2, j]
    e1p = np.isfinite(z["X"][era == 0, k])
    latep = np.isfinite(z["X"][era >= 2, k])
    z.close()
    ok = (float(np.nanmean(e1)) == 0.0 and float(np.nanmean(late)) > 0.9
          and float(e1p.mean()) == 0.0 and float(latep.mean()) > 0.9)
    return check("t20_forecaster_is_typed_missing_pre_instrument", ok,
                 "E1 avail=%.3f p_exp=%.3f | E3+ avail=%.3f p_exp=%.3f"
                 % (float(np.nanmean(e1)), float(e1p.mean()),
                    float(np.nanmean(late)), float(latep.mean())))


def t21_matrix_carries_no_holdout(matrix_dir=None):
    p = os.path.join(matrix_dir or M3.MATRIX_DIR, "matrix.npz")
    if not os.path.exists(p):
        return check("t21_matrix_carries_no_holdout", True,
                     "SKIPPED (no built matrix)")
    z = np.load(p, allow_pickle=False)
    d8 = z["d8"]
    z.close()
    try:
        n = M3.check_holdout(d8)
    except M3.HarnessRefusal as e:
        return check("t21_matrix_carries_no_holdout", False, str(e)[:70])
    return check("t21_matrix_carries_no_holdout", True, "%d clean rows" % n)


def red_first():
    """THE RED-FIRST PROOF: with the guards removed, both reds must FAIL.

    Each guard is swapped for the no-op it would have been had nobody written
    it, the two red tests are re-run, and the run PASSES only if both of them
    report FAIL.  A guard that keeps passing with its body removed is a guard
    that was never testing anything.
    """
    import json
    keep = (M3.check_holdout, M3.check_forward_values,
            M3.check_forbidden_names)
    M3.check_holdout = lambda d8: int(np.asarray(d8).size)
    M3.check_forward_values = lambda *a2, **k2: []
    M3.check_forbidden_names = lambda feats: len(list(feats))
    del RESULTS[:]
    t01_holdout_row_is_refused()
    t04_future_value_mutant_is_refused()
    t05_future_name_mutant_is_refused()
    fired = {n: ok for n, ok, _d in RESULTS}
    (M3.check_holdout, M3.check_forward_values,
     M3.check_forbidden_names) = keep
    ok = not any(fired.values())
    rec = {"mode": "red-first (guards replaced by no-ops)",
           "expectation": "every red FAILS without its guard",
           "results": fired, "red_first_proved": bool(ok)}
    os.makedirs(M3.M3_ROOT, exist_ok=True)
    M3.write_json(os.path.join(M3.M3_ROOT, "red_first.receipt.json"),
                  M3.env_receipt(rec))
    print("\nRED-FIRST: %s — %s"
          % ("PROVED" if ok else "NOT PROVED",
             ", ".join("%s=%s" % (n, "fired" if not v else "PASSED-WITHOUT-"
                                                           "GUARD")
                       for n, v in sorted(fired.items()))))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--red-first", action="store_true", dest="red_first")
    ap.add_argument("--matrix", default=None)
    a = ap.parse_args()
    MC.verify_spec(force=True)
    if a.red_first:
        return red_first()
    t01_holdout_row_is_refused()
    t02_clean_matrix_passes()
    t03_enumerator_refuses_holdout()
    t04_future_value_mutant_is_refused()
    t05_future_name_mutant_is_refused()
    t06_value_guard_is_not_vacuous()
    t07_registry_is_clean_at_head()
    t12_episode_pins_hold()
    t13_day_gap_vectorised_matches_batch4()
    t14_no_feature_reads_a_forward_field()
    t16_borda_is_a_preference_share()
    t18_no_teacher_flag_is_true_and_measurable()
    t19_news_veto_uses_census_flags()
    if not a.fast:
        t08_mfe_unwalled_is_mfe_at_sess_close()
        t09_retg_matches_the_atlas_formula()
        t10_rank_transform_is_within_phase()
        t11_dp_ceiling_matches_panel_score()
        t15_targets_exclude_refused_certificates()
        t17_determinism_two_builds_agree()
        t20_forecaster_is_typed_missing_pre_instrument(a.matrix)
        t21_matrix_carries_no_holdout(a.matrix)
    bad = [n for n, ok, _d in RESULTS if not ok]
    print("\n%d/%d passed%s" % (len(RESULTS) - len(bad), len(RESULTS),
                                ("; FAILED: " + ", ".join(bad)) if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
