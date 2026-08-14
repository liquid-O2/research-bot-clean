#!/usr/bin/python3
"""PORT M2 — RED-FIRST tests for the forward-offer / regime forecaster.

Every law-asserting test carries a committed MUTANT: a named neutralisation of
the production rule that the test must catch.  A test whose mutant survives is a
dead test and FAILS.  Ledger: artifacts/cache/port/m2/regime_forecast/
red_ledger.tsv.

The three mutants the brief requires (A and B) plus the classic walk-forward
leak (C):

  A  LEAKAGE     a feature computed AT/AFTER the anchor — here the CURRENT
                 session's realised range, whose availability stamp is that
                 session's CLOSE — must be caught by the availability test
                 (Feats.add -> CausalGuard.avail -> LeakRefusal).
  B  BENCHMARK   the trailing benchmark window mutated to include the row it
                 predicts (_window_hi(i, include_current=True)).  The mutant
                 must be refused, AND the test shows the peek is MATERIAL (the
                 peeking benchmark scores better), so the guard protects a real
                 thing rather than a formality.
  C  WALK-FWD    the expanding training window mutated to include the refit
                 cutoff month (train_mask(..., include_cutoff=True)).

Run: /usr/bin/python3 engine/port_m2/test_regime.py
"""
import datetime as dt
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import regime_forecast as RF              # noqa: E402
import context as CTX                     # noqa: E402

SECTION = RF.SECTION + " (red-first tests)"
LEDGER = []
_ENV = {}


def check(name, mutant, ok_armed, ok_mutant, detail=""):
    verdict = "PASS" if (ok_armed and not ok_mutant) else (
        "FAIL_ARMED" if not ok_armed else "FAIL_DEAD_MUTANT")
    LEDGER.append([name, mutant, int(bool(ok_armed)), int(bool(ok_mutant)),
                   verdict, detail])
    return verdict == "PASS"


def env():
    """Panels for one asset, built once (the tests are read-only)."""
    if "P" not in _ENV:
        assets = ["SI", "HG", "NKD"]
        CTX.preload(assets)
        sof = RF.build_sofar(assets, 4)
        tru = RF.build_truth(assets, sof)
        sd = [dict(zip(RF.SOFAR_COLUMNS, r)) for r in sof]
        td = [dict(zip(RF.TRUTH_COLUMNS, r)) for r in tru]
        _ENV["P"] = RF.panels(assets, td, sd)
        _ENV["truth"] = td
    return _ENV["P"]


# ======================================================== MUTANT A ==========
def t01_availability_test_catches_a_post_anchor_feature():
    """A feature whose datum only exists AFTER the anchor must be refused."""
    P = env()
    panel = P["SI"]
    i = 600
    iso = panel.iso[i]
    anchor = "LONDON_OPEN"
    sf = panel.sofar[(iso, anchor)]
    guard = MC.CausalGuard(int(RF._f(sf["anchor_ts"])),
                           int(RF._f(sf["anchor_sec"])),
                           dt.date.fromisoformat(iso))
    # ARMED: the production feature row must build without any refusal.
    armed_ok = True
    try:
        fe = RF.build_features(panel, i, anchor, guard, P)
        armed_ok = len(fe.names) > 30 and not guard.refusals
    except MC.LeakRefusal:
        armed_ok = False
    # MUTANT: add TODAY's realised session range, stamped at TODAY's close.
    guard2 = MC.CausalGuard(int(RF._f(sf["anchor_ts"])),
                            int(RF._f(sf["anchor_sec"])),
                            dt.date.fromisoformat(iso))
    fe2 = RF.Feats(guard2)
    mutant_ok = True
    try:
        fe2.add("MUTANT_today_realised_range", panel.range_arr[i],
                panel.close_utc[iso])
    except MC.LeakRefusal:
        mutant_ok = False
    return check("availability_test_catches_post_anchor_feature",
                 "Feats.add(today's realised range @ today's close)",
                 armed_ok, mutant_ok,
                 "anchor_ts=%d today_close=%d"
                 % (int(RF._f(sf["anchor_ts"])), panel.close_utc[iso]))


def t02_every_feature_carries_an_availability_stamp():
    """No feature may reach the model without passing through the guard."""
    P = env()
    ok = True
    detail = ""
    for asset in ("SI", "NKD"):
        panel = P[asset]
        for anchor in RF.ANCHORS:
            i = min(700, len(panel.iso) - 1)
            iso = panel.iso[i]
            sf = panel.sofar.get((iso, anchor))
            if sf is None:
                continue
            g = MC.CausalGuard(int(RF._f(sf["anchor_ts"])),
                               int(RF._f(sf["anchor_sec"])),
                               dt.date.fromisoformat(iso))
            before = g.checks
            fe = RF.build_features(panel, i, anchor, g, P)
            n_stamped = g.checks - before
            n_feat = len(fe.names)
            if n_stamped + fe.n_missing < n_feat:
                ok = False
                detail = "%s/%s stamped %d + missing %d < %d features" % (
                    asset, anchor, n_stamped, fe.n_missing, n_feat)
    # MUTANT: a feature added with availability_ts=None is a MISSING, and a
    # feature added with no stamp at all is impossible (add() requires it).
    mutant_ok = True
    try:
        RF.Feats(MC.CausalGuard(0, 0, dt.date(2021, 1, 1))).add("x", 1.0)
    except TypeError:
        mutant_ok = False
    return check("every_feature_carries_an_availability_stamp",
                 "Feats.add called without an availability_ts", ok, mutant_ok,
                 detail)


# ======================================================== MUTANT B ==========
def t03_trailing_benchmark_window_is_strictly_prior():
    """The trailing benchmark may never read the session it predicts."""
    P = env()
    panel = P["SI"]
    years = np.array([int(d[0:4]) for d in panel.iso])
    fit = (years >= 2021) & (years <= 2024)
    n = len(panel.iso)
    honest = np.array([RF._trail_stat(panel.range_arr, i, RF.TRAIL, "median")
                       for i in range(n)])
    # the peek, computed WITHOUT the guard, to prove the guard is material
    peek = np.full(n, np.nan)
    for i in range(n):
        w = panel.range_arr[max(0, i - RF.TRAIL):i + 1]
        w = w[np.isfinite(w)]
        if w.size >= RF.TRAIL_MIN:
            peek[i] = float(np.median(w))
    mae_h = RF.mae(panel.range_arr[fit], honest[fit])
    mae_p = RF.mae(panel.range_arr[fit], peek[fit])
    armed_ok = (RF._window_hi(5) == 5) and np.isfinite(mae_h) and \
        (mae_p < mae_h)                    # the peek IS materially better
    mutant_ok = True
    try:
        RF._window_hi(5, include_current=True)
    except AssertionError:
        mutant_ok = False
    return check("trailing_benchmark_window_is_strictly_prior",
                 "_window_hi(i, include_current=True)", armed_ok, mutant_ok,
                 "honest MAE $%.0f vs peeking MAE $%.0f (FIT)"
                 % (mae_h, mae_p))


# ======================================================== MUTANT C ==========
def t04_walk_forward_training_window_excludes_the_cutoff():
    P = env()
    panel = P["SI"]
    dates = [dt.date.fromisoformat(d) for d in panel.iso]
    cutoff = dt.date(2023, 6, 1)
    m = RF.train_mask(dates, cutoff)
    armed_ok = bool(m.any()) and all(d < cutoff for d, k in zip(dates, m) if k)
    mutant_ok = True
    try:
        RF.train_mask(dates, cutoff, include_cutoff=True)
    except AssertionError:
        mutant_ok = False
    return check("walk_forward_training_window_excludes_the_cutoff",
                 "train_mask(..., include_cutoff=True)", armed_ok, mutant_ok,
                 "n_train=%d at %s" % (int(m.sum()), cutoff))


# ================================================= supporting laws ==========
def t05_day_type_label_is_strictly_prior():
    """Recompute the committed label from prior sessions only and compare."""
    P = env()
    panel = P["NKD"]
    bad = 0
    hist = []
    for i, iso in enumerate(panel.iso):
        rng = panel.range_arr[i]
        w = np.array(hist[-RF.DAYTYPE_WINDOW:], dtype=np.float64)
        want = None
        if w.size >= RF.DAYTYPE_MIN_OBS:
            want = 1 if rng > float(np.percentile(w, RF.DAYTYPE_Q)) else 0
        got = panel.daytype_arr[i]
        got = None if not np.isfinite(got) else int(got)
        if want != got:
            bad += 1
        hist.append(rng)
    armed_ok = bad == 0
    # MUTANT: a threshold that includes today's own range
    mut_bad = 0
    hist = []
    for i, iso in enumerate(panel.iso):
        hist.append(panel.range_arr[i])
        w = np.array(hist[-RF.DAYTYPE_WINDOW:], dtype=np.float64)
        if w.size >= RF.DAYTYPE_MIN_OBS:
            want = 1 if panel.range_arr[i] > float(
                np.percentile(w, RF.DAYTYPE_Q)) else 0
            got = panel.daytype_arr[i]
            if np.isfinite(got) and int(got) != want:
                mut_bad += 1
    return check("day_type_label_is_strictly_prior",
                 "q75 threshold window includes today's own range",
                 armed_ok, mut_bad == 0,
                 "%d/%d labels differ under the mutant"
                 % (mut_bad, len(panel.iso)))


def t06_menu_target_matches_the_committed_winner_rule():
    """The per-session menu counts must reproduce the D-021 winner rule over
    the SAME population the forecaster enumerates.

    R118 note: this used to compare against `class_census.tsv`'s era "ALL"
    row.  That artifact is itself holdout-contaminated (R58, a different lane),
    and now that the forecaster EXCLUDES the D-058 holdout the two populations
    are different by construction — so the reference is recomputed here over
    the guarded population instead of read off a contaminated file.
    """
    import assemble as AS                 # noqa: E402
    import c_c_roster as CCR              # noqa: E402
    import common as C                    # noqa: E402
    P = env()
    ok, detail = True, []
    n_mut_total, n_ref_total = 0, 0
    for asset in sorted(P):
        r = AS.roster(asset)
        wall = float(AS.walls()[asset]["wall_usd"])
        cm = AS.cost_map()
        d8 = r["date8"]
        mae = r["mae_before_argmax"]
        keep = set(int(x[0:4] + x[5:7] + x[8:10]) for x in P[asset].iso)
        n_ref = n_mut = 0
        by = {}
        for i in range(int(d8.size)):
            di = int(d8[i])
            if di in keep:
                by.setdefault(di, []).append(i)
        for d in sorted(by):
            iso = MC.d8_to_date(d).isoformat()
            cost = cm.get((asset, iso), float("nan"))
            if not np.isfinite(cost):
                cost = C.FEES_RT
            for i in by[d]:
                _pk, cl = CCR.certificates(r, i, wall, cost)
                walled = CCR._skel_query(r, i, wall)[3]
                if cl[0] >= 1000.0 and not walled:
                    n_mut += 1                       # MUTANT: no MAE clause
                    if float(mae[i]) <= 300.0:
                        n_ref += 1                   # the committed rule
        got = int(np.nansum(P[asset].menu_arr["OPEN"]))
        detail.append("%s got %d want %d" % (asset, got, n_ref))
        if got != n_ref:
            ok = False
        n_ref_total += n_ref
        n_mut_total += n_mut
    # the mutant must NOT reproduce the committed counts
    mutant_ok = (n_mut_total == n_ref_total)
    detail.append("mutant(no MAE clause) total=%d vs %d"
                  % (n_mut_total, n_ref_total))
    return check("menu_target_matches_the_committed_winner_rule",
                 "winner rule without the D-021 MAE<=$300 clause", ok,
                 mutant_ok, "; ".join(detail))


def t07_anchor_state_uses_only_seconds_before_the_anchor():
    """The stored so-far range must equal the range of the seconds STRICTLY
    BEFORE the anchor — recomputed here from the raw session grid — and the
    mutant that lets the window run 30 minutes past the anchor must differ."""
    import census_common as X             # noqa: E402
    import common as C                    # noqa: E402
    P = env()
    ok, mutant_differs, detail = True, 0, []
    paths = dict(X.session_paths("SI", MC.M0_ROOT))
    panel = P["SI"]
    for iso in panel.iso[400:440:7]:
        d = dt.date.fromisoformat(iso)
        if d not in paths:
            continue
        s = X.load_session("SI", d, paths[d])
        mult = C.ASSETS["SI"]["mult"]
        for a in RF.ANCHORS:
            sf = panel.sofar.get((iso, a))
            if sf is None:
                continue
            asec = int(RF._f(sf["anchor_sec"]))
            j0 = int(np.searchsorted(s.vt, asec, side="left"))
            pre = s.vm[:j0]
            honest = ((float(pre.max()) - float(pre.min())) * mult
                      if pre.size >= 2 else 0.0)
            j1 = int(np.searchsorted(s.vt, asec + 1800, side="left"))
            post = s.vm[:j1]
            mut = ((float(post.max()) - float(post.min())) * mult
                   if post.size >= 2 else 0.0)
            if abs(honest - RF._f(sf["sofar_range_usd"])) > 1e-6:
                ok = False
                detail.append("%s %s stored %.4f != honest %.4f"
                              % (iso, a, RF._f(sf["sofar_range_usd"]), honest))
            if mut > honest + 1e-6:
                mutant_differs += 1
    # the mutant "survives" only if peeking 30 min past the anchor changes
    # nothing anywhere — which would mean the test cannot see a leak at all
    mutant_ok = mutant_differs == 0
    return check("anchor_state_uses_only_seconds_before_the_anchor",
                 "so-far window extended 1,800s past anchor_sec", ok,
                 mutant_ok,
                 "%d anchor windows change under the mutant; %s"
                 % (mutant_differs, "; ".join(detail[:2]) or "stored==honest"))


def t08_models_are_deterministic():
    """Two identical fits must give bit-identical predictions (no RNG)."""
    rs = np.random.default_rng(7)
    Z = rs.normal(size=(400, 12))
    y = (Z[:, 0] + 0.5 * Z[:, 1] + rs.normal(size=400) * 0.3)
    yb = (y > np.median(y)).astype(float)
    a = RF.fit_linear(Z, y, "reg", "identity")
    b = RF.fit_linear(Z, y, "reg", "identity")
    g1 = RF.fit_gbt(Z, y, "reg", "identity")
    g2 = RF.fit_gbt(Z, y, "reg", "identity")
    c1 = RF.fit_gbt(Z, yb, "class", "identity")
    c2 = RF.fit_gbt(Z, yb, "class", "identity")
    ok = (np.array_equal(RF.linear_pred(a, Z), RF.linear_pred(b, Z)) and
          np.array_equal(RF.gbt_pred(g1, Z), RF.gbt_pred(g2, Z)) and
          np.array_equal(RF.gbt_pred(c1, Z), RF.gbt_pred(c2, Z)))
    mutant_ok = np.array_equal(RF.gbt_pred(g1, Z),
                               RF.gbt_pred(RF.gbt_fit(Z, y, "reg",
                                                      n_trees=3), Z))
    return check("models_are_deterministic",
                 "a GBT truncated to 3 rounds must NOT match the fitted model",
                 ok, mutant_ok, "n=400 p=12")


def t09_gate_2025_uses_frozen_coefficients():
    """The era law: 2025 predictions must come from the LAST FIT REFIT.

    R118 note: this used to read `forecast_SI.tsv` off disk.  That artifact is
    QUARANTINED (its continuing walk-forward refit monthly THROUGH 2025-12, so
    D-058 holdout sessions were TRAINING rows) and the rebuild is blocked on
    R80, so the era law is exercised on `_era_pick` directly — the single
    function that implements it.  This is strictly stronger: it pins the
    selector rather than an artifact the selector happened to produce.
    """
    years = np.array([2023, 2024, 2025, 2025])
    pred = np.array([1.0, 2.0, 3.0, 4.0])          # continuing walk-forward
    frozen = np.array([10.0, 20.0, 30.0, 40.0])    # last FIT-refit coefficients
    got = RF._era_pick(pred, frozen, years)
    armed = (got.tolist() == [1.0, 2.0, 30.0, 40.0])
    # MUTANT: the continuing walk-forward carried into GATE — the arm that, on
    # the quarantined artifact, was fitted THROUGH the pre-exam holdout
    mut = pred.copy()
    mutant_ok = (mut.tolist() == got.tolist())
    # and the freeze cutoff must be the era boundary, not a later month
    armed &= (RF.FREEZE_CUTOFF == dt.date(2025, 1, 1))
    # the two arms must be DISTINGUISHABLE, or the law is vacuous
    armed &= bool(np.any(pred != frozen))
    # a FIT-era row must never take a frozen value
    armed &= (got[0] == pred[0] and got[1] == pred[1])
    return check("gate_2025_uses_frozen_coefficients",
                 "MT_era_pick_returns_the_continuing_walk_forward_on_GATE",
                 armed, mutant_ok,
                 "years=%s -> %s (frozen from %s); mutant -> %s"
                 % (years.tolist(), got.tolist(), frozen.tolist(),
                    mut.tolist()))


def t10_forecast_file_carries_no_realised_target():
    """DEFECT D19 (CC-M2-17.3): forecast_*.tsv is PREDICTIONS ONLY.

    The realised targets live in truth_*.tsv.  A y_* column in a forecast file
    puts the session's realised range / day type / phase shares in front of any
    reader who opens it — the exposure that stamped every E1 day-6 TAKE row
    FORECAST-TRUTH-EXPOSED.

    ARMED   no name in RF.Y_COLUMNS appears in FORECAST_COLUMNS, and none
            appears in the header of any forecast_*.tsv on disk.
    MUTANT  a header that re-admits one y_* column must be caught.
    """
    leaked = [c for c in RF.Y_COLUMNS if c in RF.FORECAST_COLUMNS]
    on_disk = []
    n_files = 0
    for asset in MC.ASSET_ORDER:
        path = RF.out_path("forecast_%s.tsv" % asset)
        if not os.path.exists(path):
            continue
        n_files += 1
        with open(path) as fh:
            hdr = None
            for line in fh:
                if line.startswith("#"):
                    continue
                hdr = line.rstrip("\n").split("\t")
                break
        on_disk += ["%s:%s" % (asset, c) for c in (hdr or [])
                    if c in RF.Y_COLUMNS or c.startswith("y_")]
    # R118 note: the forecast artifacts are QUARANTINED pending the rebuild,
    # so the ARMED condition is the REGISTER — the `assert not (set(Y_COLUMNS)
    # & set(FORECAST_COLUMNS))` that executes at import — plus the on-disk
    # headers of whatever files exist.  The register is the guard; the files
    # are its output.
    armed_ok = (not leaked) and (not on_disk)
    armed_ok &= bool(RF.Y_COLUMNS) and bool(RF.FORECAST_COLUMNS)
    # the import-time assertion must actually be present and executable
    src = open(RF.__file__).read()
    armed_ok &= ('assert not (set(Y_COLUMNS) & set(FORECAST_COLUMNS))' in src)
    # the mutant is the header this defect actually shipped
    mutant_hdr = list(RF.FORECAST_COLUMNS) + ["y_range_usd"]
    mutant_ok = not any(c in RF.Y_COLUMNS or c.startswith("y_")
                        for c in mutant_hdr)
    return check("forecast_file_carries_no_realised_target",
                 "a forecast header that re-admits y_range_usd",
                 armed_ok, mutant_ok,
                 "%d forecast file(s) scanned; leaked_in_columns=%s; "
                 "leaked_on_disk=%s"
                 % (n_files, ",".join(leaked) or "-",
                    ",".join(on_disk) or "-"))




# =================================== THE D-001 FIX-PASS MUTANTS =============
def t11_holdout_sessions_are_never_enumerated():
    """R118 — a mutant that loads a D-058 holdout session MUST fail.

    LAW (D-058): 2025-07-01..2025-12-31 is the PRE-EXAM HOLDOUT, blind-only,
    touched ONCE after freeze.  This file had NO guard anywhere: build_sofar
    walked X.session_paths with no date filter, so 471 holdout-dated rows
    reached sofar_SI.tsv and the continuing walk-forward TRAINED on them.
    """
    import census_common as X             # noqa: E402
    armed = True
    detail = []
    n_raw_holdout = 0
    for asset in ("SI", "HG", "NKD"):
        guarded, nq = MC.guarded_session_paths(asset, MC.M0_ROOT)
        bad = [d for d, _p in guarded if MC.in_holdout(int(d.strftime("%Y%m%d")))]
        armed &= (not bad) and nq > 0
        # MUTANT: the ungated enumerator this module used to call
        raw = X.session_paths(asset, MC.M0_ROOT)
        n_raw_holdout += sum(1 for d, _p in raw
                             if MC.in_holdout(int(d.strftime("%Y%m%d"))))
        detail.append("%s guarded=%d quarantined=%d" % (asset, len(guarded), nq))
    # and the panels the forecaster actually builds carry no holdout date
    P = env()
    leaked = [d for a in P for d in P[a].iso
              if RF._d8_of_iso(d) >= RF.HOLDOUT_FROM_D8]
    armed &= not leaked
    # the mutant (raw X.session_paths) DOES see holdout sessions -> it fails
    mutant_ok = (n_raw_holdout == 0)
    detail.append("mutant(raw session_paths) holdout sessions=%d; panel leaks=%d"
                  % (n_raw_holdout, len(leaked)))
    return check("holdout_sessions_are_never_enumerated",
                 "MT_R118_raw_X.session_paths_without_the_D058_filter",
                 armed, mutant_ok, "; ".join(detail))


def t12_gate_selector_is_h1_only():
    """R118 — the GATE selector must be 2025-H1, never `years == 2025`."""
    iso = ["2024-12-31", "2025-01-02", "2025-06-30", "2025-07-01",
           "2025-12-31"]
    got = RF.gate_mask(iso).tolist()
    armed = got == [False, True, True, False, False]
    # MUTANT: the selector this file used everywhere
    years = np.array([int(d[0:4]) for d in iso])
    mut = (years == 2025).tolist()
    mutant_ok = (mut == got)
    return check("gate_selector_is_h1_only",
                 "MT_R118_sel_years_eq_2025_pools_H1_and_the_holdout",
                 armed, mutant_ok,
                 "guarded=%s mutant=%s era_of_iso(2025-08-01)=%s"
                 % (got, mut, RF.era_of_iso("2025-08-01")))


def t13_anchor_features_run_on_sane_mids():
    """R88 — the anchor state must be built on D-054 SANE mids.

    This was the ONLY M2 module that loaded a session outside
    assemble.load_session (which applies b7_sane), so anchor_mid, the
    pre-anchor range/return/efficiency, the mean spread and the valid fraction
    all ran on RAW, INSANE mids.
    """
    import census_common as X             # noqa: E402
    import b7_sane as B7                  # noqa: E402
    paths, _nq = MC.guarded_session_paths("NKD", MC.M0_ROOT)
    rows, _nref = RF._sofar_shard(("NKD", paths[:6]))
    got = {(r[1], r[2]): r for r in rows}
    armed, mutant_ok, detail = True, False, []
    thr = B7.load_thresholds("NKD")
    n_diff = 0
    for trade_date, path in paths[:6]:
        s_raw = X.load_session("NKD", trade_date, path)      # MUTANT: no mask
        raw_n = int(s_raw.vt.size)
        s_sane = X.load_session("NKD", trade_date, path)
        B7.apply_for(s_sane, thr, "NKD", int(trade_date.strftime("%Y%m%d")))
        sane_n = int(s_sane.vt.size)
        if raw_n != sane_n:
            n_diff += 1
        r = got.get((trade_date.isoformat(), "NY_OPEN"))
        if r is None:
            continue
        # the committed row's n_valid_before must be the SANE count before the
        # anchor, never the raw one
        a = int(r[3])
        n_sane_before = int(np.searchsorted(s_sane.vt, a, side="left"))
        n_raw_before = int(np.searchsorted(s_raw.vt, a, side="left"))
        armed &= (int(r[8]) == n_sane_before)
        if n_raw_before != n_sane_before:
            mutant_ok = mutant_ok or (int(r[8]) == n_raw_before)
        detail.append("%s sane=%d raw=%d stored=%d"
                      % (trade_date, n_sane_before, n_raw_before, int(r[8])))
    # the fixture must be REAL: the mask has to actually remove seconds here
    armed &= (n_diff > 0)
    return check("anchor_features_run_on_sane_mids",
                 "MT_R88_X.load_session_without_b7_sane.apply_for",
                 armed, mutant_ok,
                 "sessions where the mask binds=%d; %s"
                 % (n_diff, "; ".join(detail[:3])))


def t14_anchor_mid_is_never_a_post_anchor_mid():
    """R121 — anchor_mid must be a mid AT OR BEFORE the anchor, and its
    availability stamp must be the OBSERVED second, not `anchor_ts - 1`.

    The old code took `searchsorted(vt, a, "left")` — the first SANE second AT
    OR AFTER the anchor — and then hand-stamped availability one second BEFORE
    the anchor, so CausalGuard could not catch it by construction.
    """
    paths, _nq = MC.guarded_session_paths("SI", MC.M0_ROOT)
    rows, _nr = RF._sofar_shard(("SI", paths[300:312]))
    ci = {c: i for i, c in enumerate(RF.SOFAR_COLUMNS)}
    armed = bool(rows)
    for r in rows:
        a = int(r[ci["anchor_sec"]])
        ams = int(r[ci["anchor_mid_sec"]])
        if ams >= 0:
            armed &= (ams <= a)           # AT OR BEFORE, never after
        else:
            armed &= not np.isfinite(float(r[ci["anchor_mid"]]))
    # MUTANT: the hand-stamped constant cannot fail the guard, so a
    # POST-anchor observed second would sail through it
    g = MC.CausalGuard(1_700_000_000, 1000, dt.date(2024, 1, 2))
    fe = RF.Feats(g)
    hand_stamped_ok = g.avail(1_700_000_000 - 1, "anchor_mid")
    caught = False
    try:
        fe.add_at_anchor("anchor_mid", 1.0, 1_700_000_000 + 5)
    except MC.LeakRefusal:
        caught = True
    armed &= caught
    mutant_ok = bool(hand_stamped_ok) and not caught
    return check("anchor_mid_is_never_a_post_anchor_mid",
                 "MT_R121_av_anchor_hardcoded_to_anchor_ts_minus_1",
                 armed, mutant_ok,
                 "hand-stamp passes avail=%s; add_at_anchor caught a "
                 "post-anchor stamp=%s" % (hand_stamped_ok, caught))


def t15_refused_release_age_is_not_a_number():
    """R122 — "no release in the last 24h" must REFUSE, not become 48.0.

    A refused input that becomes a real-valued measurement is a fabricated
    observation the model fits on, and `coverage_keep` counted it as finite
    coverage so the feature could never be dropped for sparsity.
    """
    src = open(RF.__file__).read()
    armed = ("else 48.0" not in src) and "release_since_refused" in src
    # MUTANT: the imputation this file used to carry
    mutant_ok = "else 48.0" in src
    # and the refusal must be visible to coverage_keep as NON-finite
    names = ["release_since_h"]
    X = np.array([[float("nan")], [1.0]])
    keep, rep = RF.coverage_keep(
        type("P", (), {"asset": "SI", "iso": ["2021-01-04", "2021-01-05"]})(),
        "OPEN", X, names)
    armed &= (float(rep[0][3]) < 1.0)
    return check("refused_release_age_is_not_a_number",
                 "MT_R122_impute_no_release_in_24h_as_the_number_48.0",
                 armed, mutant_ok,
                 "coverage of a refused column=%s" % rep[0][3])


TESTS = (t01_availability_test_catches_a_post_anchor_feature,
         t02_every_feature_carries_an_availability_stamp,
         t03_trailing_benchmark_window_is_strictly_prior,
         t04_walk_forward_training_window_excludes_the_cutoff,
         t05_day_type_label_is_strictly_prior,
         t06_menu_target_matches_the_committed_winner_rule,
         t07_anchor_state_uses_only_seconds_before_the_anchor,
         t08_models_are_deterministic,
         t09_gate_2025_uses_frozen_coefficients,
         t10_forecast_file_carries_no_realised_target,
         t11_holdout_sessions_are_never_enumerated,
         t12_gate_selector_is_h1_only,
         t13_anchor_features_run_on_sane_mids,
         t14_anchor_mid_is_never_a_post_anchor_mid,
         t15_refused_release_age_is_not_a_number)


def main():
    MC.verify_spec(force=True)
    n_fail = 0
    for t in TESTS:
        try:
            ok = t()
        except Exception as e:             # noqa: BLE001 — recorded, not hidden
            LEDGER.append([t.__name__, "-", 0, 0, "ERROR", repr(e)[:200]])
            ok = False
        if not ok:
            n_fail += 1
        MC.hb("test %s: %s" % (t.__name__, LEDGER[-1][4]))
    MC.write_tsv(RF.out_path("red_ledger.tsv"), SECTION,
                 MC.params_hash(RF.PARAMS),
                 ["test", "mutant", "armed_pass", "mutant_pass", "verdict",
                  "detail"], LEDGER,
                 extra=["RED-FIRST: armed_pass MUST be 1 and mutant_pass MUST "
                        "be 0 on every row"])
    MC.write_json(RF.out_path("tests.receipt.json"),
                  {"env": MC.env_receipt(RF.PARAMS), "n_tests": len(TESTS),
                   "n_failed": n_fail,
                   "verdict": "PASS" if n_fail == 0 else "FAIL"})
    MC.hb("regime tests: %d/%d passed" % (len(TESTS) - n_fail, len(TESTS)))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
