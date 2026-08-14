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
    """The per-session menu counts must sum to the class census's n_winners."""
    census = os.path.join(MC.M2_ROOT, "class_census.tsv")
    if not os.path.exists(census):
        return check("menu_target_matches_the_committed_winner_rule",
                     "-", False, False, "class_census.tsv absent")
    want = {}
    for r in RF.read_tsv(census):
        if r["class"] == "ALL_CLASSES" and r["era"] == "ALL":
            want[r["asset"]] = int(r["n_winners"])
    P = env()
    ok, detail = True, []
    for asset, w in sorted(want.items()):
        if asset not in P:
            continue
        got = int(np.nansum(P[asset].menu_arr["OPEN"]))
        detail.append("%s got %d want %d" % (asset, got, w))
        if got != w:
            ok = False
    # MUTANT: drop the MAE<=$300 clause from the winner rule -> a bigger count
    mutant_ok = True
    if ok:
        r = __import__("assemble").roster("NKD")
        import c_c_roster as CCR
        wall = float(__import__("assemble").walls()["NKD"]["wall_usd"])
        cm = __import__("assemble").cost_map()
        import common as C
        n_mut = 0
        d8 = r["date8"]
        by = {}
        for i in range(int(d8.size)):
            by.setdefault(int(d8[i]), []).append(i)
        for d in sorted(by):
            iso = MC.d8_to_date(d).isoformat()
            cost = cm.get(("NKD", iso), float("nan"))
            if not np.isfinite(cost):
                cost = C.FEES_RT
            for i in by[d]:
                _pk, cl = CCR.certificates(r, i, wall, cost)
                if cl[0] >= 1000.0 and not CCR._skel_query(r, i, wall)[3]:
                    n_mut += 1
        mutant_ok = (n_mut == want.get("NKD"))
        detail.append("mutant(no MAE clause) NKD=%d" % n_mut)
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
    """The era law: 2025 predictions must come from the last FIT refit."""
    path = RF.out_path("forecast_SI.tsv")
    if not os.path.exists(path):
        return check("gate_2025_uses_frozen_coefficients", "-", False, False,
                     "forecast_SI.tsv absent (run the driver first)")
    rows = RF.read_tsv(path)
    g = [r for r in rows if r["year"] == "2025" and r["anchor"] == "OPEN"]
    f = [r for r in rows if r["year"] == "2024" and r["anchor"] == "OPEN"]
    n_diff = sum(1 for r in g
                 if r["p_expansion_wfcont"] and r["p_expansion"] and
                 abs(RF._f(r["p_expansion_wfcont"]) -
                     RF._f(r["p_expansion"])) > 1e-9)
    armed_ok = len(g) > 100 and n_diff > 0
    # MUTANT: 2024 rows must NOT carry a continuing-walk-forward column at all
    mutant_ok = any(r["p_expansion_wfcont"] for r in f)
    return check("gate_2025_uses_frozen_coefficients",
                 "a FIT-era row carrying a 2025-only diagnostic column",
                 armed_ok, mutant_ok,
                 "%d/%d GATE rows differ from the continuing walk-forward"
                 % (n_diff, len(g)))


TESTS = (t01_availability_test_catches_a_post_anchor_feature,
         t02_every_feature_carries_an_availability_stamp,
         t03_trailing_benchmark_window_is_strictly_prior,
         t04_walk_forward_training_window_excludes_the_cutoff,
         t05_day_type_label_is_strictly_prior,
         t06_menu_target_matches_the_committed_winner_rule,
         t07_anchor_state_uses_only_seconds_before_the_anchor,
         t08_models_are_deterministic,
         t09_gate_2025_uses_frozen_coefficients)


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
