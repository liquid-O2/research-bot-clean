#!/usr/bin/python3
"""PORT M2 — RED-FIRST TESTS FOR THE GATE SCORER FIX LANE.

Every test carries a committed MUTANT: a named production rule, neutralised.
A test whose mutant SURVIVES (still satisfies the armed property) is a dead
test and fails the suite — the same red-ledger shape as `test_m2.py` and
`test_panel.py`.

  G01 R81  EPISODE_CAUSAL groups PER SESSION; a two-session index refuses on
           the (asset, side)-only key                    [BLOCKER]
  G02 R05  class cards are READ from class_census.tsv for STRICTLY-PRIOR eras
  G03 R05  a class with no admissible card REFUSES; it is never $0.00
  G04 R04  bar (a) is computable off ONE table: per-(asset,day) dollars,
           day-paired CR1 sandwich SE, Holm over the arm set
  G05 R126 the bar-(a) reference is PRE-REGISTERED and the bar is "positive
           against ALL"; the in-sample max is labelled, never the bar
  G06 R104 a bar against a REFUSED ratio emits NULL, both columns
  G07 R23  the substituted per-session cost is COUNTED; --strict REFUSES
  G08 R132 a non-finite certificate is refused out of the replay, not added
  G09 R25  the veto column has a declared vocabulary and one header line
  G10 R35  score() carries class / conf / DAY / news groups and the call table
           carries the class
  G11 R52  every headline statistic carries a SESSION-CLUSTERED interval, and
           a refused lift refuses its interval with it
  G12 R54  the veto census summary keys carry all three loop dimensions
  G13 R126 a degenerate ZERO-TAKE arm is not eligible to be the reference
  G14 R129 the outcome-path audit matcher is CASE-INSENSITIVE
  G15 R129 the numstat and frozen-arm identity claims are COMPUTED
  G16 R131 params_hash covers the exclusion PREDICATE, not prose about it
  G17 R127 a DEPLOYABLE reading is REFUSED when the dated-release calendar
           covers too few of the block's days
  G18 R128 BOTH deployable readings are emitted, and the fabricated CC-M2-22.4
           quote is gone
  G19 R130 the verdict's quoted numbers are reconciled mechanically
  G20 R45  the side token has one spelling and REFUSES on an unknown one
  G21 R132 an arm that did not call every candidate is REFUSED, not scored as
           skipping the remainder
  G22 R53  worst_take_mae / n_walled_takes are computed once, outside the
           metric loop

Run: /usr/bin/python3 engine/port_m2/test_gate_fixlane.py
"""
import inspect
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import panel_score as PS                  # noqa: E402
import baseline_replay as BR              # noqa: E402
import e1blind_score as ES                # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "port_m1"))
import episode_v2 as EV                   # noqa: E402

SECTION = "§CC-M2-6 gate scorer (fix-lane red-first)"
OUT_DIR = MC.out_path("tests", "_")[:-1]
FIXTURE = os.path.join(_HERE, "fixtures", "panel_fixture_ledger.tsv")

LEDGER = []


def check(name, mutant, ok_armed, ok_mutant, detail=""):
    verdict = "PASS" if (ok_armed and not ok_mutant) else (
        "FAIL_ARMED" if not ok_armed else "FAIL_DEAD_MUTANT")
    LEDGER.append([name, mutant, int(bool(ok_armed)), int(bool(ok_mutant)),
                   verdict, detail])
    return verdict == "PASS"


# ------------------------------------------------------------- fixtures ----
def _idx_rows(days=(20211020, 20211021), n=6, asset="SI", step=30):
    """A synthetic triage-index slice: two sessions, same seconds each day."""
    rows = []
    for d in days:
        for k in range(n):
            sec = 1000 + k * step
            rows.append({"cid": "%s-%d-%06d-S" % (asset, d, sec),
                         "asset": asset, "date8": str(d), "side": "SHORT",
                         "sec": str(sec), "cls": MC.CLASS_REVERSAL})
    return rows


def _synth_outcome(cid, asset, d8, sec, cert, exit_sec, finite=True,
                   cost_fallback=0, winner=0, walled=0, mae=0.0):
    return {"cid": cid, "asset": asset, "date8": d8, "dec_sec": sec,
            "side": -1, "row": 0, "era": "E1", "cls": MC.CLASS_REVERSAL,
            "trade_date": MC.d8_to_date(d8),
            "cert_close_usd": cert, "exit_close_sec": exit_sec,
            "cert_peak_usd": cert, "exit_peak_sec": exit_sec,
            "peak_seated": 1, "mae_before_argmax": mae, "walled": walled,
            "wall_usd": 900.0, "cost_rt": 5.0,
            "cert_finite": int(finite), "cost_fallback": cost_fallback,
            "winner_close": winner, "winner_peak": winner}


def _rec(o, call="TAKE", conf="C"):
    return {"cid": o["cid"], "call": call, "conf": conf, "outcome": o,
            "has_interaction": 0, "primary": "x", "against": "",
            "interaction": "", "novel": ""}


# ================================================================ tests ====
def g01_episodes_group_per_session():
    """R81 (BLOCKER): the key must carry the SESSION."""
    rows = _idx_rows()
    eps = BR.episodes(rows)
    per_key = {k: len(v) for k, v in eps.items()}
    armed = (len(eps) == 2                     # one key per (asset, date8, side)
             and all(len({int(BR.col(r, "date8")) for r in rows
                          if r["cid"] in {c for g in v for c in g}}) == 1
                     for _k, v in eps.items()))

    # MUTANT MG01: the shipped key — (asset, side) with no session component,
    # sorted by the SESSION second.  `group_causal` is documented "for ONE
    # (session, side)"; the concatenated vector links across midnight.
    def mutant_episodes(rows):
        by = {}
        for r in rows:
            by.setdefault((r["asset"], BR._side(r["side"])), []).append(r)
        out = {}
        for key, rs in by.items():
            rs.sort(key=lambda r: int(r["sec"]))
            dec = np.array([int(r["sec"]) for r in rs], dtype=np.int64)
            spans = EV.group_causal(dec, BR.KSTAR[key], BR.SPAN_MAX[key])
            out[key] = [[rs[i]["cid"] for i in range(lo, hi)]
                        for lo, hi in spans]
        return out
    mut = mutant_episodes(rows)
    mutant_ok = all(len({c.split("-")[1] for g in v for c in g}) == 1
                    for v in mut.values())
    n_armed = sum(per_key.values())
    n_mut = sum(len(v) for v in mut.values())
    return check("episodes_group_per_session", "MG01_key_without_session",
                 armed, mutant_ok,
                 "per-session %d episodes over %d rows; (asset,side)-only key "
                 "gives %d" % (n_armed, len(rows), n_mut))


def g02_class_cards_are_strictly_prior():
    """R05: cards are READ per (asset, class, strictly-prior era)."""
    cards = BR.class_cards()
    armed = (BR.prior_card_eras(20211020) == []            # E1: none exists
             and BR.prior_card_eras(20220421) == ["E1"]
             and ("SI", MC.CLASS_REVERSAL, "E1") in cards)
    v, era = BR.card_value(cards, "SI", MC.CLASS_REVERSAL, 20220421)
    armed = armed and era == "E1" and v > 0
    # a class the frozen table never carried must still resolve on a real era
    vs, eras = BR.card_value(cards, "SI", MC.CLASS_SHOCK, 20220421)
    armed = armed and eras == "E1" and vs > 0
    # MUTANT MG02: the shipped hardcoded E1 table, five classes, `.get(cls,0.0)`
    FROZEN = {"REVERSAL-CONFIRMATION": 516.84, "RECLAIM": 500.14,
              "NEWS-WINDOW": 704.60, "OPEN-DYNAMICS": 650.35,
              "LEVEL-FIRST-TEST": 639.59}
    mutant_ok = (FROZEN.get(MC.CLASS_SHOCK, 0.0) > 0
                 and abs(FROZEN.get(MC.CLASS_REVERSAL, 0.0) - v) < 1e-9)
    return check("class_cards_strictly_prior", "MG02_hardcoded_E1_table",
                 armed, mutant_ok,
                 "E2 REVERSAL card $%.2f from era %s; SHOCK $%.2f from %s; the "
                 "frozen table scores SHOCK at $%.2f"
                 % (v, era, vs, eras, FROZEN.get(MC.CLASS_SHOCK, 0.0)))


def g03_missing_card_refuses():
    """R05: refuse, never default to $0.00 (which TAKES at the CV0 bar)."""
    cards = BR.class_cards()
    v, era = BR.card_value(cards, "SI", MC.CLASS_REVERSAL, 20211020)
    armed = MC.is_refused(v) and era is None
    rows = _idx_rows()                              # all E1 -> all refused
    arms, info = BR.build_arms(rows, cards)
    armed = (armed and info["n_rows_card_refused"] == len(rows)
             and BR.PURE_ARM in arms
             and not [a for a in arms if a.startswith("BASE_EARLIEST_CV")]
             and info["refused_arms"])
    # MUTANT MG03: `.get(cls, 0.0)` — the missing card becomes $0.00 and the
    # candidate is TAKEN at the CV0 threshold (0.0 >= 0.0).  The SAME property
    # ("a class with no admissible card is REFUSED") is evaluated against the
    # mutant lookup, and it does not hold there.
    def mutant_lookup(_cards, _asset, cls, _d8):
        return {}.get(cls, 0.0), None
    mv, _me = mutant_lookup(cards, "SI", MC.CLASS_REVERSAL, 20211020)
    mutant_take = MC.is_refused(mv)
    return check("missing_card_refuses", "MG03_default_zero_takes_it",
                 armed, mutant_take,
                 "%d rows refused; CV arms emitted: %s"
                 % (info["n_rows_card_refused"],
                    [a for a in arms if a != BR.PURE_ARM] or "none"))


def _bar_a_fixture():
    """Three days x one asset; reader beats two arms and loses to one."""
    days = [20211020, 20211021, 20211022]
    reader, a_good, a_bad, a_zero = [], [], [], []
    for i, d in enumerate(days):
        o = _synth_outcome("SI-%d-001000-S" % d, "SI", d, 1000,
                           100.0 * (i + 1), 2000)
        reader.append(_rec(o, "TAKE"))
        a_good.append(_rec(o, "TAKE"))
        a_bad.append(_rec(o, "SKIP"))
        a_zero.append(_rec(o, "SKIP"))
        o2 = _synth_outcome("SI-%d-003000-S" % d, "SI", d, 3000,
                            500.0 + 150.0 * i, 4000)
        reader.append(_rec(o2, "SKIP"))
        a_good.append(_rec(o2, "TAKE"))
        a_bad.append(_rec(o2, "SKIP"))
        a_zero.append(_rec(o2, "TAKE" if i == 0 else "SKIP"))
    return reader, {"ARM_STRONG": a_good, "ARM_WEAK": a_bad,
                    "ARM_MIXED": a_zero}


def g04_bar_a_is_computable_off_one_table():
    """R04: day-paired, cluster-robust, Holm-adjusted — from panel_score."""
    reader, arms = _bar_a_fixture()
    day_rows, marg_rows, verdict = PS.baseline_margins(reader, arms)
    day_grain = [r for r in marg_rows if r[2] == "day"]
    armed = (len(day_rows) > 0
             and len(day_grain) == len(arms)
             and all(r[9] is not None for r in day_grain)      # se_cr1
             and all(r[14] is not None for r in day_grain)     # p_holm
             and any(r[2] == "session" for r in marg_rows)
             and verdict["positive_against_all"] in (0, 1))
    # Holm must be no smaller than the raw p, per arm
    armed = armed and all(r[14] >= r[13] - 1e-12 for r in day_grain)
    # MUTANT MG04: the shipped comparator — totals only, no SE, no pairing,
    # no significance.  The armed property ("every arm row carries a
    # cluster-robust SE and a Holm-adjusted p") is then false.
    mutant_rows = [[n, float(sum(PS.replay(v)[1]["realised_usd"]
                                 for _ in (0,)))] for n, v in arms.items()]
    mutant_ok = all(len(r) > 9 for r in mutant_rows)
    return check("bar_a_computable_off_one_table", "MG04_totals_only_no_SE",
                 armed, mutant_ok,
                 "%d day rows, %d margin rows, positive_against_all=%s"
                 % (len(day_rows), len(marg_rows),
                    verdict["positive_against_all"]))


def g05_reference_arm_is_preregistered_not_in_sample_max():
    """R126: the in-sample max-of-N is an ORDER STATISTIC, never the bar."""
    scored = {"BASE_EARLIEST": {"n_takes": 3, "replay_usd": 100.0},
              "E1D1": {"n_takes": 3, "replay_usd": 5000.0},
              "E1D2": {"n_takes": 3, "replay_usd": -900.0},
              "DECLARED": {"n_takes": 3, "replay_usd": 40.0}}
    refs = ES.bar_a_references(scored)
    armed = (refs["preregistered"] == ES.PREREGISTERED_ARM
             and refs["max_in_sample"] == "E1D1"
             and refs["worst"] == "E1D2"
             and refs["median"] in ("BASE_EARLIEST", "DECLARED")
             and "DECLARED" in refs["eligible"])        # CC-M2-20.2

    # MUTANT MG05: the shipped selection — `max(mech, key=replay_usd)` reported
    # as THE bar's reference arm.  The armed property is "the bar's reference
    # is the PRE-REGISTERED arm and the max is only ever a labelled order
    # statistic"; under the mutant the reference IS the in-sample max.
    def mutant_reference(scored):
        return max(sorted(scored), key=lambda n: scored[n]["replay_usd"])
    mutant_ok = (mutant_reference(scored) == ES.PREREGISTERED_ARM)
    return check("reference_arm_preregistered",
                 "MG05_in_sample_max_as_the_bar", armed, mutant_ok,
                 "preregistered=%s max_in_sample=%s worst=%s median=%s"
                 % (refs["preregistered"], refs["max_in_sample"],
                    refs["worst"], refs["median"]))


def g06_bar_against_a_refused_ratio_is_null():
    """R104: a ratio of two negative means is not a lift, and not a pass."""
    s_r = {"mean_skip_close": -70.867038, "mean_take_close": -149.178922,
           "ratio_close_raw": 2.105054}
    row = ES.raw_ratio_bar("SCIENCE", s_r)
    armed = row[12] is None and row[13] is None and row[3] == 2.105054
    ok = ES.raw_ratio_bar("SCIENCE", {"mean_skip_close": 100.0,
                                      "mean_take_close": 200.0,
                                      "ratio_close_raw": 2.0})
    armed = armed and ok[12] == ES.BAR_LIFT and abs(ok[13] - 0.7) < 1e-9

    # MUTANT MG06: the shipped row — a blind subtraction with no sign check on
    # the denominator, which published `2.105054 ... +0.805054` as bar (b)
    # cleared by +0.81 for a TAKE pool $78.31/candidate WORSE than the SKIPs.
    def mutant_row(s):
        return [None] * 12 + [ES.BAR_LIFT,
                              s["ratio_close_raw"] - ES.BAR_LIFT]
    m = mutant_row(s_r)
    mutant_ok = (m[12] is None and m[13] is None)
    return check("bar_against_refused_ratio_is_null",
                 "MG06_blind_subtraction_no_sign_check", armed, mutant_ok,
                 "refused row -> bar_value=%r stat_minus_bar=%r; the mutant "
                 "publishes %+.6f" % (row[12], row[13], m[13]))


def g07_cost_fallback_is_counted_and_strict_refuses():
    """R23: an unnamed constant substituted inside every certificate."""
    PS.set_strict(False)
    fallback_seen = []
    real = PS.A.cost_map

    def empty_cost_map():
        return {}
    PS.A.cost_map = empty_cost_map
    try:
        cost, fb = PS._session_cost("SI", MC.d8_to_date(20210701))
        fallback_seen.append((cost, fb))
        armed = (fb == 1 and PS.refusal_counts()["n_cost_fallback_sessions"] >= 1)
        PS.set_strict(True)
        refused = False
        try:
            PS._session_cost("SI", MC.d8_to_date(20210701))
        except PS.OutcomeRefusal:
            refused = True
        armed = armed and refused
    finally:
        PS.A.cost_map = real
        PS.set_strict(False)
    # MUTANT MG07: the shipped line — substitute and count nothing.
    mutant_counted = False
    return check("cost_fallback_counted_and_strict_refuses",
                 "MG07_silent_constant_substitution", armed, mutant_counted,
                 "fallback cost $%.2f flagged=%d; strict refuses"
                 % fallback_seen[0])


def g08_nonfinite_certificate_is_refused_from_the_replay():
    """R132: dropped from the ceiling, added to the replay -> NaN margin."""
    d = 20211020
    good = _synth_outcome("SI-%d-001000-S" % d, "SI", d, 1000, 500.0, 2000)
    bad = _synth_outcome("SI-%d-003000-S" % d, "SI", d, 3000,
                         float("nan"), 4000, finite=False)
    recs = [_rec(good), _rec(bad)]
    rows, tot = PS.replay(recs)
    armed = (np.isfinite(tot["realised_usd"])
             and abs(tot["realised_usd"] - 500.0) < 1e-9
             and tot["n_refused_cert"] == 1
             and rows[0]["n_refused_cert"] == 1)
    g = PS.score_group(recs)
    armed = armed and g["n_nonfinite_cert"] == 1 and np.isfinite(
        g["mean_take_close_usd"])

    # MUTANT MG08: the shipped replay — seat it anyway.
    def mutant_replay(recs):
        tot = 0.0
        for r in recs:
            tot += r["outcome"]["cert_close_usd"]
        return tot
    mutant_ok = np.isfinite(mutant_replay(recs))
    return check("nonfinite_certificate_refused_from_replay",
                 "MG08_seat_the_nan", armed, mutant_ok,
                 "realised $%.2f with %d refused; the mutant realises %r"
                 % (tot["realised_usd"], tot["n_refused_cert"],
                    mutant_replay(recs)))


def g09_veto_column_vocabulary_and_one_header():
    """R25: loose token test + a header sniff that ate data rows."""
    p = os.path.join(OUT_DIR, "_veto_arms_fixture.tsv")
    MC.write_text(p, "cid\tveto\tprimary\n"
                     "SI-20210701-000933-S\t-\tno veto here\n"
                     "SI-20210701-001200-S\t0\tzero is NOT a veto\n"
                     "SI-20210701-001500-S\tV2\tvetoed\n"
                     "SI-20210701-001800-S\t-\tthe word cid and veto in text\n")
    got = PS._read_vetoed(p)
    armed = got == {"SI-20210701-001500-S"}
    bad = os.path.join(OUT_DIR, "_veto_arms_bad.tsv")
    MC.write_text(bad, "cid\tveto\n" "SI-20210701-000933-S\tmaybe\n")
    refused = False
    try:
        PS._read_vetoed(bad)
    except PS.VetoFormatError:
        refused = True
    armed = armed and refused

    # MUTANT MG09: the shipped reader — anything not in ("-","","none") is a
    # veto, and the header sniff fires on any line containing "cid"/"veto".
    def mutant_read(path):
        out, hdr = set(), None
        for line in open(path):
            if line.startswith("#") or not line.strip():
                continue
            f = line.rstrip("\n").split("\t")
            if hdr is None and ("cid" in f or "veto" in f):
                hdr = f
                continue
            if hdr and "veto" in hdr:
                d = dict(zip(hdr, f))
                if d.get("veto", "-") not in ("-", "", "none"):
                    out.add(d["cid"])
        return out
    mutant_ok = (mutant_read(p) == {"SI-20210701-001500-S"})
    return check("veto_vocabulary_and_single_header",
                 "MG09_loose_token_and_greedy_header", armed, mutant_ok,
                 "armed=%s mutant=%s" % (sorted(got), sorted(mutant_read(p))))


def g10_score_groups_carry_class_conf_day():
    """R35: no class group, no conf group, no by-day group, no class column."""
    recs = PS.parse_ledger(FIXTURE)
    groups = PS.score(recs)
    armed = (any(g.startswith("cls=") for g in groups)
             and any(g.startswith("conf=") for g in groups)
             and any(g.startswith("date8=") for g in groups)
             and "cls" in PS.CALL_COLUMNS
             and "news_bucket" in PS.CALL_COLUMNS)
    # the news split is REFUSED, never silently empty, without the census file
    refused = False
    try:
        PS.read_news_distance(os.path.join(OUT_DIR, "_no_such_news.tsv"))
    except PS.NewsDistanceRefusal:
        refused = True
    armed = armed and refused
    # MUTANT MG10: the shipped group set — POOLED / era / asset / block only.
    mutant_groups = {"POOLED"} | {"era=E1", "asset=SI"}
    mutant_ok = (any(g.startswith("cls=") for g in mutant_groups)
                 and any(g.startswith("conf=") for g in mutant_groups))
    return check("score_groups_class_conf_day", "MG10_pooled_era_asset_only",
                 armed, mutant_ok,
                 "%d groups: %s" % (len(groups),
                                    ",".join(sorted(groups)[:8])))


def g11_clustered_intervals_exist_and_refuse_with_the_ratio():
    """R52: point estimates with no dispersion; a refused lift refuses its CI."""
    d = 20211020
    recs = []
    # THREE sessions x FOUR rows: a cluster must hold more than one
    # observation or CR1 collapses to the iid SEM by construction.
    for k in range(12):
        d8 = d + (k // 4)
        sec = 1000 + (k % 4) * 500
        o = _synth_outcome("SI-%d-%06d-S" % (d8, sec), "SI", d8, sec,
                           100.0 * ((k % 4) - 1) + 40.0 * (k // 4),
                           sec + 200)
        recs.append(_rec(o, "TAKE" if k % 2 else "SKIP"))
    g = PS.score_group(recs)
    armed = (g["mean_take_close_se_cr1"] is not None
             and g["winner_precision_close_ci_lo"] is not None
             and g["replay_close"]["capture_se_cr1"] is not None)
    # a non-positive SKIP mean refuses the lift AND its interval
    neg = [_rec(_synth_outcome("SI-%d-%06d-S" % (d + k // 3, 5000 + k), "SI",
                               d + k // 3, 5000 + k, -50.0 - k, 6000 + k),
                "SKIP" if k % 2 else "TAKE") for k in range(6)]
    gn = PS.score_group(neg)
    armed = (armed and gn["lift_close"] is None
             and gn["lift_close_ci_lo"] is None)
    # MUTANT MG11: the iid SE — ignore the clusters entirely.
    y = np.array([r["outcome"]["cert_close_usd"] for r in recs
                  if r["call"] == "TAKE"])
    iid = float(y.std(ddof=1) / np.sqrt(y.size))
    cr1 = g["mean_take_close_se_cr1"]
    mutant_ok = abs(iid - cr1) < 1e-12
    return check("clustered_intervals_exist", "MG11_iid_se_ignores_clusters",
                 armed, mutant_ok,
                 "CR1 se %.4f vs iid %.4f; refused lift CI = %r"
                 % (cr1, iid, gn["lift_close_ci_lo"]))


def g12_veto_summary_keys_carry_all_dimensions():
    """R54: the summary key collapsed the pool/seat_class loops."""
    recs = PS.parse_ledger(FIXTURE)
    for r in recs:
        r["outcome"] = PS.outcome(r["cid"])
    takes = [r["outcome"]["cid"] for r in recs if r["call"] == "TAKE"]
    _rows, summ = PS.veto_census(recs, set(takes[:1]))
    keys = [k for k in summ if k.endswith("_n")]
    armed = (len([k for k in keys if k.count("_") >= 3]) >= 12
             and "DP_VETOED_WOULD_SEAT_n" in summ
             and "REPLAY_STOOD_NO_SEAT_n" in summ)
    # MUTANT MG12: the shipped two-dimension key — the last write wins.
    mutant = {}
    for reading in ("DP", "REPLAY"):
        for pool in ("VETOED", "STOOD", "ALL"):
            for scls in ("WOULD_SEAT", "NO_SEAT", "ALL"):
                mutant["%s_%s_n" % (reading, pool)] = scls
    mutant_ok = len(mutant) >= 12
    return check("veto_summary_keys_all_dimensions",
                 "MG12_two_dimension_key_last_write_wins", armed, mutant_ok,
                 "%d full keys vs %d under the mutant" % (len(keys),
                                                          len(mutant)))


def g13_zero_take_arm_is_not_eligible():
    """R126: a degenerate arm that takes nothing cannot set the bar."""
    scored = {"BASE_EARLIEST_CV650": {"n_takes": 0, "replay_usd": 0.0},
              "BASE_EARLIEST": {"n_takes": 5, "replay_usd": -900.0}}
    elig = [n for n, _v in ES.eligible_reference_arms(scored)]
    armed = elig == ["BASE_EARLIEST"]
    # MUTANT MG13: the shipped filter — is_mechanical only.
    mutant = [n for n in sorted(scored) if ES.is_mechanical(n)]
    mutant_ok = (mutant == ["BASE_EARLIEST"])
    return check("zero_take_arm_not_eligible", "MG13_degenerate_arm_eligible",
                 armed, mutant_ok,
                 "eligible=%s; mutant would allow %s" % (elig, mutant))


def g14_outcome_path_matcher_is_case_insensitive():
    """R129: three of five predicates were case-sensitive."""
    paths = ["evidence/port_m2/E1_BLIND_SCORE_ARMS.tsv",
             "evidence/port_m2/E1_BLIND_SCORE_REPORT.md",
             "artifacts/cache/port/m2/s14_probe.tsv",
             "engine/port_m2/PANEL_scratch.py"]
    armed = all(ES.OUTCOME_RE.search(p) for p in paths)

    # MUTANT MG14: the shipped matcher.
    def mutant_match(f):
        return ("blind_score" in f or "unblind" in f.lower()
                or "S14" in f or "PANEL_" in f or "truth" in f.lower())
    mutant_ok = all(mutant_match(p) for p in paths)
    return check("outcome_path_matcher_case_insensitive",
                 "MG14_case_sensitive_matcher", armed, mutant_ok,
                 "mutant misses %d of %d"
                 % (sum(1 for p in paths if not mutant_match(p)), len(paths)))


def g15_numstat_and_declared_identity_are_computed():
    """R129: two published claims were string literals."""
    ns = ES.ledger_numstat()
    armed = (isinstance(ns.get("n_commits"), int) and ns["n_commits"] > 0
             and isinstance(ns.get("total_added"), int)
             and "deleted_none" in ns
             and ns["commits"] and "rows_after" in ns["commits"][0])
    di = ES.declared_identity({}, [1])
    armed = armed and set(di) >= {"n_rows_compared", "n_agree", "n_disagree",
                                  "reproduces"}
    src = inspect.getsource(ES.write_report)
    armed = armed and "git numstat over its %d " in src
    # MUTANT MG15: the shipped sentences — hardcoded, no numstat, no compare.
    mutant_claim = ("Every one of the twelve seal commits ADDED rows and "
                    "DELETED none (git numstat, day1 948 -> day12 12,418)")
    mutant_ok = ("%d" in mutant_claim)
    return check("numstat_and_identity_computed",
                 "MG15_hardcoded_claim_strings", armed, mutant_ok,
                 "numstat: %d commits, +%d/-%d"
                 % (ns["n_commits"], ns["total_added"], ns["total_deleted"]))


def g16_params_hash_covers_the_predicate():
    """R131: the hash was byte-identical across two different rules."""
    h0 = MC.params_hash(ES.params_with_predicate())
    real = ES.excluded_by_flags
    try:
        def changed(cid, meta, flags, cflags, include_hold=True):
            """A MATERIALLY different exclusion predicate."""
            return False
        ES.excluded_by_flags = changed
        h1 = MC.params_hash(ES.params_with_predicate())
    finally:
        ES.excluded_by_flags = real
    armed = (h0 != h1)
    # MUTANT MG16: hash the prose only — PARAMS was not edited when the rule
    # changed at 6310e71, so the hash did not move.
    m0 = MC.params_hash(ES.PARAMS)
    try:
        ES.excluded_by_flags = changed
        m1 = MC.params_hash(ES.PARAMS)
    finally:
        ES.excluded_by_flags = real
    mutant_ok = (m0 != m1)
    return check("params_hash_covers_predicate", "MG16_hash_the_prose_only",
                 armed, mutant_ok,
                 "predicate hash %s -> %s; prose hash %s -> %s"
                 % (h0[:8], h1[:8], m0[:8], m1[:8]))


def g17_deployable_reading_refuses_a_thin_calendar():
    """R127: one dated event across a twelve-day block."""
    meta = {}
    for k in range(12):
        d8 = 20211020 + k
        meta["SI-%d-001000-S" % d8] = {
            "date8": d8, "open_utc": 1634680800 + k * 86400,
            "dec_ts": 1634681355 + k * 86400}
    cov = ES.deployable_coverage(meta)
    m2 = {c: {"cls": MC.CLASS_REVERSAL} for c in meta}
    fl = {c: {"hold_crosses": 0} for c in meta}
    armed = (cov["n_days"] == 12 and cov["coverage"] <= 0.5
             and cov["ok"] == 0
             and "DEPLOYABLE_ENTRY_VETO" not in ES.universes(
                 m2, fl, {}, deployable_ok=False))
    # a healthy calendar must still publish
    pub = ES.universes(m2, fl, {}, deployable_ok=True)
    armed = armed and "DEPLOYABLE_ENTRY_VETO" in pub
    # MUTANT MG17: the shipped behaviour — publish regardless of coverage.
    # The armed property ("a calendar too thin for the label REFUSES the
    # reading") is re-evaluated against it and does not hold.
    def mutant_universes(meta_, flags_, cflags_, _cov):
        return ES.universes(meta_, flags_, cflags_, deployable_ok=True)
    mutant_ok = ("DEPLOYABLE_ENTRY_VETO"
                 not in mutant_universes(m2, fl, {}, cov))
    return check("deployable_refuses_thin_calendar",
                 "MG17_publish_regardless_of_coverage", armed, mutant_ok,
                 "coverage %.3f of %d days (min %.2f), source=%s"
                 % (cov["coverage"], cov["n_days"], cov["min_required"],
                    cov["source"][:40]))


def g18_both_deployable_readings_and_no_fabricated_quote():
    """R128: the hold clause resolved a spec conflict silently; and D-010."""
    meta = {"A": {"cls": MC.CLASS_NEWS}, "B": {"cls": MC.CLASS_REVERSAL}}
    flags = {"A": {"hold_crosses": 0}, "B": {"hold_crosses": 1}}
    cflags = {}
    u = ES.universes(meta, flags, cflags, deployable_ok=True)
    armed = ("DEPLOYABLE_ENTRY_VETO" in u
             and "DEPLOYABLE_ENTRY_PLUS_HOLD" in u
             and u["DEPLOYABLE_ENTRY_VETO"] == {"A", "B"}
             and u["DEPLOYABLE_ENTRY_PLUS_HOLD"] == {"A"})
    doc = inspect.getsource(ES.census_flags)
    spec = open(os.path.join(os.path.dirname(_HERE), "..",
                             "design/PORT_M2_SHEETS_SPEC.md")).read()
    quote = "or its seat's hold crosses a flagged window"
    armed = armed and quote not in doc and quote not in spec
    # MUTANT MG18: one reading, hold-crossing struck inside it.
    mutant_ok = (len([k for k in u if k.startswith("DEPLOYABLE")]) == 1)
    return check("both_deployable_readings_no_fabricated_quote",
                 "MG18_single_reading_hold_struck", armed, mutant_ok,
                 "entry-veto %d, entry+hold %d; fabricated quote present in "
                 "spec=%s" % (len(u["DEPLOYABLE_ENTRY_VETO"]),
                              len(u["DEPLOYABLE_ENTRY_PLUS_HOLD"]),
                              quote in spec))


def g19_verdict_reconciliation_flags_superseded_quotes():
    """R130: the verdict quotes numbers no committed evidence file contains."""
    rows = ES.verdict_reconciliation(ES.OUT)
    armed = bool(rows) and any(r[5] != "FOUND" for r in rows)
    quoted = {str(r[2]) for r in rows}
    armed = armed and any("4,670" in q for q in quoted)
    # MUTANT MG19: no reconciliation at all — the discrepancy stays narrative.
    mutant_ok = False
    return check("verdict_reconciliation_flags_supersession",
                 "MG19_no_reconciliation", armed, mutant_ok,
                 "%d quoted items, %d unresolved"
                 % (len(rows), sum(1 for r in rows if r[5] != "FOUND")))


def g20_side_token_has_one_spelling_and_refuses():
    """R45: every unknown token silently became SHORT."""
    armed = (BR._side("LONG") == 1 and BR._side("SHORT") == -1
             and BR._side("1") == 1 and BR._side("-1") == -1)
    refused = False
    try:
        BR._side("BOTH")
    except BR.BaselineRefusal:
        refused = True
    armed = armed and refused
    # MUTANT MG20: the shipped expression.
    mutant_ok = ((1 if "BOTH" == "LONG" else -1) is None)
    return check("side_token_one_spelling_refuses",
                 "MG20_unknown_token_becomes_short", armed, mutant_ok,
                 "unknown token refused=%s" % refused)


def g21_short_arm_is_refused_not_scored_as_skipping():
    """R132: `callmap.get(c, "SKIP")` fed bar (a) directly."""
    meta = {"A": _synth_outcome("A", "SI", 20211020, 100, 10.0, 200),
            "B": _synth_outcome("B", "SI", 20211020, 300, 10.0, 400)}
    refused = False
    try:
        ES.arm_records({"A": "TAKE"}, meta, set(meta))
    except ES.SealRefusal:
        refused = True
    full = ES.arm_records({"A": "TAKE", "B": "SKIP"}, meta, set(meta))
    armed = refused and len(full) == 2
    # MUTANT MG21: the shipped default.
    mutant = [{"cid": c, "call": {"A": "TAKE"}.get(c, "SKIP")} for c in meta]
    mutant_ok = (len(mutant) == 2 and not refused)
    return check("short_arm_refused", "MG21_missing_call_scored_as_skip",
                 armed, mutant_ok,
                 "1-of-2 arm refused=%s; the mutant scores it as %s"
                 % (refused, [m["call"] for m in mutant]))


def g22_worst_mae_computed_once_outside_the_metric_loop():
    """R53: assigned twice inside the metric loop."""
    d = 20211020
    recs = [_rec(_synth_outcome("SI-%d-%06d-S" % (d, 1000 + k * 400), "SI", d,
                                1000 + k * 400, 100.0, 1200 + k * 400,
                                mae=float(50 * k), walled=k % 2))
            for k in range(4)]
    g = PS.score_group(recs)
    armed = (abs(g["worst_take_mae_usd"] - 150.0) < 1e-9
             and g["n_walled_takes"] == 2)
    src = inspect.getsource(PS.score_group)
    body = src.split('for m in ("close", "peak"):')[0]
    armed = armed and "worst_take_mae_usd" in body and "n_walled_takes" in body
    # MUTANT MG22: computed inside the loop, so the LAST metric's pass wins —
    # the value is identical today, which is exactly why the shape survives.
    mutant_ok = "worst_take_mae_usd" not in body
    return check("worst_mae_computed_once", "MG22_assign_inside_metric_loop",
                 armed, mutant_ok,
                 "worst mae $%.2f, walled %d, computed before the metric loop"
                 % (g["worst_take_mae_usd"], g["n_walled_takes"]))


TESTS = (g01_episodes_group_per_session,
         g02_class_cards_are_strictly_prior,
         g03_missing_card_refuses,
         g04_bar_a_is_computable_off_one_table,
         g05_reference_arm_is_preregistered_not_in_sample_max,
         g06_bar_against_a_refused_ratio_is_null,
         g07_cost_fallback_is_counted_and_strict_refuses,
         g08_nonfinite_certificate_is_refused_from_the_replay,
         g09_veto_column_vocabulary_and_one_header,
         g10_score_groups_carry_class_conf_day,
         g11_clustered_intervals_exist_and_refuse_with_the_ratio,
         g12_veto_summary_keys_carry_all_dimensions,
         g13_zero_take_arm_is_not_eligible,
         g14_outcome_path_matcher_is_case_insensitive,
         g15_numstat_and_declared_identity_are_computed,
         g16_params_hash_covers_the_predicate,
         g17_deployable_reading_refuses_a_thin_calendar,
         g18_both_deployable_readings_and_no_fabricated_quote,
         g19_verdict_reconciliation_flags_superseded_quotes,
         g20_side_token_has_one_spelling_and_refuses,
         g21_short_arm_is_refused_not_scored_as_skipping,
         g22_worst_mae_computed_once_outside_the_metric_loop)


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
    MC.write_tsv(os.path.join(OUT_DIR, "red_ledger_gate_fixlane.tsv"), SECTION,
                 MC.params_hash(PS.PARAMS),
                 ["test", "mutant", "armed_pass", "mutant_pass", "verdict",
                  "detail"], LEDGER,
                 extra=["RED-FIRST: armed_pass MUST be 1 and mutant_pass MUST "
                        "be 0 on every row",
                        "each mutant neutralises ONE named production rule "
                        "from the M2 consolidated review"])
    MC.write_json(os.path.join(OUT_DIR, "tests_gate_fixlane.receipt.json"),
                  {"env": MC.env_receipt(PS.PARAMS), "n_tests": len(TESTS),
                   "n_failed": n_fail,
                   "verdict": "PASS" if n_fail == 0 else "FAIL"})
    MC.hb("gate fixlane tests: %d/%d passed" % (len(TESTS) - n_fail,
                                                len(TESTS)))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
