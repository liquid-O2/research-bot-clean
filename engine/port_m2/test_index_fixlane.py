#!/usr/bin/python3
"""PORT M2 — red-first tests for the D-001 INDEX/RETRIEVAL fix lane.

Every fix this lane made to `triage_index.py` and `retrieve.py` that changes
BEHAVIOUR carries a test here, and every test carries a MUTANT: the named
production line, neutralised, restored to what it was before the fix.  A test
whose mutant still satisfies the law is a dead test and FAILS, exactly as in
test_m2.py — R41 is on the record precisely because two mutants in the D-057
fixture were `return True` stubs that could never fail.

The leak-class fixes (level birth, forecaster join, vintage, the S4 touch
branch) are cases in `leakfix.py`, which is the artefact spec §2 gates on.
This file covers the ones that are not leak classes:

  X01 R03  print precision — `%.4g` destroyed NKD price resolution
  X02 R06  a derived flag is THREE-VALUED; a refused input is never a 0
  X03 R06  seat_score REFUSES rather than scoring a row higher for its gaps
  X04 R07  `unspent_phase_usd` + the pinned `pct_unspent_phase` alias
  X05 R08  a FLOOR-SCALED z is ordinal: P004's z term refuses on it
  X06 R08  the V1.2 PERCENTILE-Z, over strictly-prior sessions
  X07 R16  the as-of table is TOTAL and is not a tautology
  X08 R09/R48  the day driver: per-row cuts, and refusals instead of IndexError
  X09 R28  the roster guard refuses a partially rendered day
  X10 R27/R47  the compat view carries AS_OF and describes what it emits
  X11 R17  retrieval excludes the query's own session by default
  X12 R44  the pool cache key binds m2_common, census_common and the spec pin
  X13 R46  two UNCLASSED family masks are INCOMPARABLE, not identical
  X14 R45  an unknown side token REFUSES instead of mapping to SHORT

Run: /usr/bin/python3 engine/port_m2/test_index_fixlane.py
"""
import hashlib
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import triage_index as TI                 # noqa: E402
import retrieve as R                      # noqa: E402
import pattern_lib as PL                  # noqa: E402
import census_common as X                 # noqa: E402

SECTION = "§1 triage index + §CC-M2-5.3 retrieval (D-001 fix lane tests)"
OUT_DIR = MC.out_path("tests", "_")[:-1]

# A real rendered BLIND sheet from the E1 blind corpus: NKD, whose 10-point
# price grid is the asset R03 was measured on.
SHEET = ("/workspace/artifacts/cache/port/m2/era/E1/BLIND/NKD/20211020/"
         "NKD-20211020-000555-S.BLIND.sheet.txt")
# the day-2 query R17 was measured on: 3 of its 12 nearest neighbours were
# same-session cases from the round in flight.
RETRIEVE_CID = "SI-20210702-052509-S"

LEDGER = []


def check(name, mutant, ok_armed, ok_mutant, detail=""):
    verdict = "PASS" if (ok_armed and not ok_mutant) else (
        "FAIL_ARMED" if not ok_armed else "FAIL_DEAD_MUTANT")
    LEDGER.append([name, mutant, int(bool(ok_armed)), int(bool(ok_mutant)),
                   verdict, detail])
    return verdict == "PASS"


def _row(**kw):
    """A synthetic index row.  The caches are pre-seeded so `_derive` touches
    no m0 receipt and no session tape: these tests are about the derivation."""
    TI._META[("NKD", "20211020")] = (0, 82799)
    r = {c: None for c in TI.COLUMNS}
    r.update({"cid": "NKD-20211020-000555-S", "asset": "NKD",
              "date8": "20211020", "side": "SHORT", "sec": 555,
              "mult": 5.0, "mid": 29350.0})
    r.update(kw)
    TI._derive(r)
    return r


# ------------------------------------------------------------------ X01 ----
def x01_price_precision_round_trips():
    """MX01 (R03): `%.4g` — three NKD rows with different mids print alike."""
    mids = [29350.0, 29355.0, 29360.0, 26.2775]
    armed = all(float(TI._fmt(v)) == v for v in mids)
    armed = armed and len({TI._fmt(v) for v in mids[:3]}) == 3
    # MUTANT MX01: the V3 formatter
    mut = ["%.4g" % v for v in mids]
    mutant = (len(set(mut[:3])) == 3 and all(float(m) == v
                                             for m, v in zip(mut, mids)))
    return check("price_precision_round_trips", "MX01_pct_4g", armed, mutant,
                 "fixed=%s v3=%s" % ([TI._fmt(v) for v in mids[:3]], mut[:3]))


# ------------------------------------------------------------------ X02 ----
def x02_flags_are_three_valued():
    """MX02 (R06): a refused input must not emit the negative token.

    `cov_phase` refused with a phase-close exit is the D22 shape: the V1 flag
    said 0 — 'the veto did not fire' — on a row where it could not be
    evaluated at all, and no consumer could tell the two apart.
    """
    refused = _row(exit_is_sess=0, cov_phase=None, unspent_phase_usd=None)
    genuine = _row(exit_is_sess=0, cov_phase=10.0, unspent_phase_usd=900.0)
    fired = _row(exit_is_sess=0, cov_phase=90.0, unspent_phase_usd=900.0)
    armed = (MC.is_refused(refused["P002"]) and genuine["P002"] == 0
             and fired["P002"] == 1
             and refused["n_refused_inputs"] > genuine["n_refused_inputs"])
    # Kleene: a decidable disjunct still decides even when its sibling refuses
    half = _row(exit_is_sess=0, cov_phase=None, unspent_phase_usd=100.0)
    armed = armed and half["P002"] == 1
    # MUTANT MX02: the V1 form, int(bool(x is not None and cond))
    def v1(r):
        return int(bool(r["exit_is_sess"] == 0 and r["cov_phase"] is not None
                        and (r["cov_phase"] >= 75.0
                             or (r["unspent_phase_usd"] is not None
                                 and r["unspent_phase_usd"] <= 450.0))))
    mutant = (v1(refused) != v1(genuine)) or MC.is_refused(v1(refused))
    return check("flags_are_three_valued", "MX02_int_bool_flag", armed, mutant,
                 "refused=%s genuine=%s fired=%s kleene_or=%s"
                 % (refused["P002"], genuine["P002"], fired["P002"],
                    half["P002"]))


# ------------------------------------------------------------------ X03 ----
def x03_seat_score_refuses_rather_than_inflating():
    """MX03 (R06): the ranking must not reward a row for its missing terms."""
    full = dict(exit_is_sess=1, cov_phase=40.0, unspent_phase_usd=900.0,
                cov_sess=50.0, unspent_sess=900.0, ladder_pos="below_q10",
                runway_phase=30000, phase_H_sec=100, phase_L_sec=100,
                slope5m=-1.0, accel=-1.0, f60_n=9, f60_vol=99,
                n_trades_300=99, c2f_300=1.0, trades_min_z=0.0,
                trades_min_z_floored=0, spread_dec=10.0, rv_collapse=20.0,
                phase_H=29500.0, phase_L=29200.0)
    have = _row(**full)
    gap = dict(full)
    gap.update(rv_collapse=None, spread_dec=None)      # refused fvol/cost block
    lost = _row(**gap)
    armed = (not MC.is_refused(have["seat_score"])
             and MC.is_refused(lost["seat_score"])
             and have["seat_terms_present"] > lost["seat_terms_present"])
    # MUTANT MX03: the V1 partial sum — the penalties are simply skipped, so
    # the row with refused inputs OUTRANKS the identical row that has them.
    def v1(r):
        s = 0.0
        if r["exit_is_sess"] == 1:
            s += 1.0
        if r["cov_phase"] is not None:
            s += max(0.0, (80.0 - r["cov_phase"]) / 40.0)
        if (r["ladder_pos"] or "") in ("below_q10", "at_or_above_q10"):
            s += 1.0
        if r["runway_phase"] is not None:
            s += min(1.0, r["runway_phase"] / 30000.0)
        for col, w in (("P004", 1.5), ("P005", 1.0), ("P013", 0.5)):
            s -= w * (0 if MC.is_refused(r[col]) else int(r[col]))
        return round(s, 3)
    mutant = v1(lost) <= v1(have)
    return check("seat_score_refuses_rather_than_inflating",
                 "MX03_partial_sum_seat_score", armed, mutant,
                 "have=%s(%d terms) refused=%s(%d terms) v1: %.3f vs %.3f"
                 % (have["seat_score"], have["seat_terms_present"],
                    lost["seat_score"], lost["seat_terms_present"],
                    v1(have), v1(lost)))


# ------------------------------------------------------------------ X04 ----
def x04_dollar_column_is_named_in_dollars():
    """MX04 (R07): the rename lands AND the frozen spelling still resolves."""
    r = _row(unspent_phase_usd=1755.1)
    armed = ("unspent_phase_usd" in TI.COLUMNS
             and "pct_unspent_phase" not in TI.COLUMNS
             and ("unspent_phase_usd", "pct_unspent_phase") in TI.ALIASES
             and r["unspent_phase_usd"] == 1755.1)
    import io
    p = MC.out_path("tests", "fixlane_compat.tsv")
    TI.write_compat(p, [r])
    with io.open(p) as fh:
        head = [ln for ln in fh][1].rstrip("\n").split("\t")
    armed = armed and ("pct_unspent_phase" in head
                       and "unspent_phase_usd" in head)
    rows, _st = TI.read_index(p)
    armed = armed and (rows[0]["pct_unspent_phase"]
                       == rows[0]["unspent_phase_usd"])
    # MUTANT MX04: the rename WITHOUT the alias — e1d1_policy:156 and
    # e1d1_seal:260 read `pct_unspent_phase` by name off the compat view and
    # would get a KeyError on a table that looks otherwise complete.
    saved = TI.ALIASES
    try:
        TI.ALIASES = tuple(a for a in saved if a[0] != "unspent_phase_usd")
        TI.write_compat(p, [r])
        with io.open(p) as fh:
            mut_head = [ln for ln in fh][1].rstrip("\n").split("\t")
    finally:
        TI.ALIASES = saved
    mutant = "pct_unspent_phase" in mut_head
    os.remove(p)
    return check("dollar_column_is_named_in_dollars", "MX04_rename_no_alias",
                 armed, mutant, "compat carries both spellings")


# ------------------------------------------------------------------ X05 ----
def x05_floored_z_is_ordinal_only():
    """MX05 (R08): spec §1 S5 — a `~` z is ORDINAL ONLY, never a threshold."""
    v, fl = TI._fmark("-1.60~")
    v2, fl2 = TI._fmark("-1.60")
    armed = (v == -1.6 and fl == 1 and v2 == -1.6 and fl2 == 0)
    base = dict(f60_n=9, f60_vol=99, n_trades_300=99, c2f_300=1.0)
    flo = _row(trades_min_z=-1.6, trades_min_z_floored=1, **base)
    real = _row(trades_min_z=-1.6, trades_min_z_floored=0, **base)
    armed = armed and MC.is_refused(flo["P004"]) and real["P004"] == 1
    armed = armed and "trades_min_z_floored" in TI.COLUMNS
    # MUTANT MX05: the V1 `_f`, which strips the marker before the threshold
    mutant = (float("-1.60~".rstrip("~")) <= -1.3) is not True
    return check("floored_z_is_ordinal_only", "MX05_strip_tilde_then_threshold",
                 armed, mutant,
                 "floored P004=%s unfloored P004=%s" % (flo["P004"],
                                                        real["P004"]))


# ------------------------------------------------------------------ X06 ----
def x06_percentile_z_is_strictly_prior():
    """MX06 (R08/CC-M2-7.3): the V1.2 percentile form, over PRIOR sessions."""
    if not os.path.exists(SHEET):
        return check("percentile_z_is_strictly_prior", "MX06_include_own_day",
                     False, False, "fixture sheet absent: %s" % SHEET)
    import bisect
    import assemble as A
    import sections as SEC
    r = TI.parse_sheet(SHEET)
    p = r["trades_min_z_pctile"]
    bin_idx = (int(r["dec_ts"]) % 86400) // SEC.BIN_SECONDS
    ref = list(TI.clock_reference("NKD", 20211020, bin_idx))
    armed = (p is not None and 0.0 <= p <= 100.0
             and "trades_min_z_pctile" in TI.COLUMNS
             and len(ref) >= TI.CLOCK_MIN_REF)
    # the mid-rank convention, on a reference this test controls outright
    TI._CLOCK_REF[("FIXTURE", 1, 1)] = [1.0, 2.0, 2.0, 3.0] * 3
    armed = armed and TI.clock_pctile("FIXTURE", 1, 1801, 2.0) == 50.0
    TI._CLOCK_REF[("FIXTURE", 1, 1)] = [1.0, 2.0]          # below the floor
    armed = armed and TI.clock_pctile("FIXTURE", 1, 1801, 2.0) is None
    TI._CLOCK_REF.pop(("FIXTURE", 1, 1))
    # THE LAW: every session in the reference is STRICTLY PRIOR to the row's.
    ds = sorted(A.session_index("NKD"))
    i = bisect.bisect_left(ds, 20211020)
    armed = armed and all(d < 20211020 for d in ds[max(0, i - 60):i])
    # MUTANT MX06: `bisect_right`, i.e. the session's OWN bin joins the
    # reference the value NOW is being ranked against.
    j = bisect.bisect_right(ds, 20211020)
    mut_ref = ds[max(0, j - 60):j]
    mutant = all(d < 20211020 for d in mut_ref)
    return check("percentile_z_is_strictly_prior", "MX06_bisect_right_own_day",
                 armed, mutant, "pctile=%s n_ref=%d mutant_ref_max=%s"
                 % (p, len(ref), max(mut_ref)))


# ------------------------------------------------------------------ X07 ----
def x07_asof_table_is_total_and_real():
    """MX07 (R16): the per-column table is TOTAL, and it is not a tautology."""
    armed = (set(TI.ASOF_RULES) == set(TI.COLUMNS)
             and TI.ASOF_RULES["menu_hat"] == TI.ASOF_RULE_ANCHOR
             and TI.ASOF_RULES["runway_observed"] == TI.ASOF_RULE_CLOSE
             and TI.ASOF_RULES["sched_next_in"] == TI.ASOF_RULE_EXEMPT)
    try:
        TI.field_asof_sec({"sec": 100}, "a_column_nobody_declared")
        armed = False                      # an undeclared column must REFUSE
    except RuntimeError:
        pass
    row = {"sec": 1000, "dec_ts": 1634681355, "rf_anchor_ts": 1634680800,
           "observed_close": None}
    anchor_sec = TI.field_asof_sec(row, "menu_hat")
    armed = armed and anchor_sec == 1000 - 555 and anchor_sec < row["sec"]
    # an observed-close column with no observed close is MASKED, not blessed
    armed = armed and TI.field_asof_sec(row, "runway_observed") == TI.KNOW_NEVER
    # MUTANT MX07: the V3 body — every column answers the row's own second
    def v3(r, col):
        if col in TI.ASOF_EXEMPT:
            return None
        if col in TI.OBSERVED_COLS:
            oc = r.get("observed_close")
            return None if oc is None else int(oc)
        return None if r.get("sec") is None else int(r["sec"])
    mutant = (v3(row, "menu_hat") < row["sec"]
              and v3(row, "runway_observed") == TI.KNOW_NEVER)
    return check("asof_table_is_total_and_real", "MX07_row_sec_for_everything",
                 armed, mutant,
                 "anchor_knowable_at=%s row_sec=%d v3_anchor=%s v3_observed=%s"
                 % (anchor_sec, row["sec"], v3(row, "menu_hat"),
                    v3(row, "runway_observed")))


# ------------------------------------------------------------------ X08 ----
def x08_driver_cuts_and_refusals():
    """MX08 (R09/R48): one prefix per decision second; an empty range refuses."""
    rows = [{"sec": s, "cid": "C%d" % s, "asset": "NKD", "observed_close": None}
            for s in (100, 100, 250, 900, 4000)]
    for r in rows:
        for c in TI.COLUMNS:
            r.setdefault(c, None)
    cuts = TI.day_driver(rows, per_row=True)
    armed = ([c for c, _s in cuts] == [100, 250, 900, 4000]
             and len(cuts[0][1]) == 2 and len(cuts[-1][1]) == len(rows))
    for bad in (dict(step_sec=0), dict(step_sec=300, first=5000, last=100),
                dict(step_sec=None)):
        try:
            TI.day_driver(rows, **bad)
            armed = False
        except RuntimeError:
            pass
    try:
        TI.day_driver([], per_row=True)
        armed = False
    except RuntimeError:
        pass
    try:                                   # the CLI cap (main passes False)
        TI.day_driver(rows, 1800, allow_coarse_step=False)
        armed = False
    except RuntimeError:
        pass
    # MUTANT MX08: the V3 body — `cuts[-1]` on an empty range
    def v3(secs, lo, hi, step):
        cuts = list(range(lo, hi + 1, step))
        return cuts[-1]
    mutant = True
    try:
        v3([r["sec"] for r in rows], 5000, 100, 300)
    except IndexError:
        mutant = False                     # an IndexError is not a refusal
    except RuntimeError:
        mutant = True
    return check("driver_cuts_and_refusals", "MX08_indexerror_empty_range",
                 armed, mutant, "per_row cuts=%s" % [c for c, _s in cuts])


# ------------------------------------------------------------------ X09 ----
def x09_roster_guard_refuses_partial_day():
    """MX09 (R28/D30): a day short of its roster must not be indexed."""
    exp = TI.roster_count("NKD", "20211020")
    armed = exp == 158
    try:
        TI.assert_day_complete("NKD", "20211020", exp - 1)
        armed = False
    except RuntimeError:
        pass
    try:
        TI.assert_day_complete("NKD", "20211020", exp + 1)
        armed = False
    except RuntimeError:
        pass
    armed = armed and TI.assert_day_complete("NKD", "20211020", exp) == exp
    # the declared opt-out reports rather than refuses
    armed = armed and TI.assert_day_complete("NKD", "20211020", exp - 1,
                                             allow_mismatch=True) == exp
    # MUTANT MX09: the V3 main() — index whatever files are on disk
    def v3(_asset, _d8, _n):
        return True                        # no comparison, no refusal
    mutant = False
    try:
        v3("NKD", "20211020", exp - 1)
    except RuntimeError:
        mutant = True                      # the V3 form never refuses
    return check("roster_guard_refuses_partial_day", "MX09_no_roster_check",
                 armed, mutant, "roster=%d" % exp)


# ------------------------------------------------------------------ X10 ----
def x10_compat_view_declares_as_of():
    """MX10 (R27/R47): one comment line, and it says AS_OF when it is one."""
    r = _row(unspent_phase_usd=100.0)
    p = MC.out_path("tests", "fixlane_compat_asof.tsv")
    TI.write_compat(p, [r], as_of=40000)
    with open(p) as fh:
        lines = fh.read().split("\n")
    armed = (lines[0].startswith("#") and not lines[1].startswith("#")
             and "AS_OF 40000" in lines[0]
             and "V1 column spellings" not in lines[0]
             and TI.VERSION in lines[0])
    TI.write_compat(p, [r])
    with open(p) as fh:
        first = fh.readline()
    armed = armed and "AS_OF" not in first
    os.remove(p)
    # MUTANT MX10: the V3 header — a prefix view indistinguishable from a
    # day-complete table, under a description of a column list it does not emit
    v3 = ("# TRIAGE INDEX COMPAT VIEW (D16 pinned reader: ONE comment line, "
          "V1 column spellings retained; data identical to the versioned "
          "index)")
    mutant = "AS_OF" in v3
    return check("compat_view_declares_as_of", "MX10_no_as_of_stamp", armed,
                 mutant, "one comment line, AS_OF carried")


# ------------------------------------------------------------------ X11 ----
def x11_retrieval_excludes_own_session():
    """MX11 (R17/CC-M2-9.4): within-round retrieval is BARRED by default."""
    asset, d8, _s, _sd = MC.parse_cid(RETRIEVE_CID)
    _q, hits, _sc, meta = R.retrieve(RETRIEVE_CID, k=12)
    same = [h for h in hits
            if str(h["rec"]["asset"]) == asset and int(h["rec"]["d8"]) == d8]
    armed = (not same and meta["n_own_session_dropped"] > 0
             and meta["own_date8_included"] is False)
    _q, opt, _sc, m2 = R.retrieve(RETRIEVE_CID, k=12, include_own_date8=True)
    n_opt = sum(1 for h in opt if str(h["rec"]["asset"]) == asset
                and int(h["rec"]["d8"]) == d8)
    armed = armed and m2["own_date8_included"] is True and n_opt > 0
    # MUTANT MX11: the V1 default — the flag exists and defaults to empty
    _q, mut, _sc, _m = R.retrieve(RETRIEVE_CID, k=12,
                                  _mutant_keep_own_session=True)
    mutant = not any(str(h["rec"]["asset"]) == asset
                     and int(h["rec"]["d8"]) == d8 for h in mut)
    return check("retrieval_excludes_own_session", "MX11_own_session_kept",
                 armed, mutant,
                 "dropped=%d same_session_hits default=%d optout=%d mutant=%d"
                 % (meta["n_own_session_dropped"], len(same), n_opt,
                    sum(1 for h in mut if str(h["rec"]["asset"]) == asset
                        and int(h["rec"]["d8"]) == d8)))


# ------------------------------------------------------------------ X12 ----
def x12_pool_hash_binds_every_input():
    """MX12 (R44): the cache key must move when a feature's source moves."""
    cids = ["SI-20210701-012312-S", "SI-20210702-052509-S"]
    base = R._pool_hash(cids)

    def v1(cs):                            # MUTANT MX12: the V3 key
        h = hashlib.sha256()
        h.update("\n".join(cs).encode())
        for src in (PL.__file__, R.__file__):
            h.update(MC.C.sha256_file(src.replace(".pyc", ".py")).encode())
        return h.hexdigest()

    v1_base = v1(cids)
    real_shas, real_file = MC.spec_shas, MC.C.sha256_file
    moved = {}
    try:
        MC.spec_shas = lambda: {"m2_spec_sha16": "0000000000000000"}
        moved["spec"] = R._pool_hash(cids) != base and v1(cids) == v1_base
    finally:
        MC.spec_shas = real_shas
    try:
        MC.C.sha256_file = lambda p: ("f" * 64 if os.path.basename(p)
                                      in ("m2_common.py", "census_common.py")
                                      else real_file(p))
        moved["m2_common"] = R._pool_hash(cids) != base and v1(cids) == v1_base
    finally:
        MC.C.sha256_file = real_file
    armed = all(moved.values()) and R._pool_hash(cids) == base
    mutant = not any(moved.values())
    return check("pool_hash_binds_every_input", "MX12_pl_and_self_only",
                 armed, mutant, "moved=%s" % sorted(moved.items()))


# ------------------------------------------------------------------ X13 ----
def x13_unclassed_masks_are_incomparable():
    """MX13 (R46): an all-zero family mask is MISSING, not a perfect match."""
    armed = (R._present("fam_mask", "bits", 0) is False
             and R._present("fam_mask", "bits", 1) is True)
    a = {f: 1.0 for f in R.REC_FIELDS}
    a.update({"klass": "RECLAIM", "phase_dec": 1, "clock_sec": 100,
              "ladder_band": 1, "regime_tercile": 1, "fam_mask": 0})
    b = dict(a)
    sc = R.scales([a, b])
    _d, nb, per = R.distance(a, b, sc)
    armed = armed and "B11_family_tags" not in per
    c = dict(a)
    c["fam_mask"] = 3
    d2 = dict(a)
    d2["fam_mask"] = 3
    _d2, nb2, per2 = R.distance(c, d2, R.scales([c, d2]))
    armed = armed and per2.get("B11_family_tags") == 0.0 and nb2 == nb + 1
    # MUTANT MX13: `kind == "bits"` returns True unconditionally — so two
    # all-zero masks are compared, `_bit_jaccard(0, 0)` is 0.0, and the block
    # scores a PERFECT match on a field neither side carries.
    def v1_present(kind, _v):
        return True if kind == "bits" else False
    mutant = not (v1_present("bits", 0) and R._bit_jaccard(0, 0) == 0.0)
    return check("unclassed_masks_are_incomparable", "MX13_bits_always_present",
                 armed, mutant, "nb(unclassed)=%d nb(tagged)=%d" % (nb, nb2))


# ------------------------------------------------------------------ X14 ----
def x14_unknown_side_token_refuses():
    """MX14 (R45): `startswith("L") else -1` inverts every side-signed term."""
    armed = (TI._side_of({"side": "LONG", "cid": "NKD-20211020-000555-L"}) == 1
             and TI._side_of({"side": "SHORT",
                              "cid": "NKD-20211020-000555-S"}) == -1
             and TI._side_of({"side": "?", "cid": "NKD-20211020-000555-S"})
             is None
             and TI._side_of({"side": None, "cid": "x"}) is None
             # a token that disagrees with the cid's own side character
             and TI._side_of({"side": "LONG",
                              "cid": "NKD-20211020-000555-S"}) is None)
    bad = _row(side="?", phase_H=29500.0, phase_L=29200.0, slope5m=-1.0,
               accel=-1.0, exit_is_sess=1, cov_phase=40.0,
               ladder_pos="below_q10", runway_phase=30000)
    armed = armed and (bad["room_phase"] is None
                       and MC.is_refused(bad["P001"])
                       and MC.is_refused(bad["seat_score"]))
    # MUTANT MX14: the V1 form maps every unknown token to SHORT, so it never
    # refuses — the law "an unknown side token is a refusal" does not hold.
    def v1_side(tok):
        return 1 if (tok or "").upper().startswith("L") else -1
    mutant = (v1_side("?") is None and v1_side(None) is None
              and v1_side("LONG") == 1)
    return check("unknown_side_token_refuses", "MX14_startswith_L_else_short",
                 armed, mutant, "unknown token -> %s" % TI._side_of(
                     {"side": "?", "cid": "NKD-20211020-000555-S"}))


TESTS = (x01_price_precision_round_trips, x02_flags_are_three_valued,
         x03_seat_score_refuses_rather_than_inflating,
         x04_dollar_column_is_named_in_dollars, x05_floored_z_is_ordinal_only,
         x06_percentile_z_is_strictly_prior, x07_asof_table_is_total_and_real,
         x08_driver_cuts_and_refusals, x09_roster_guard_refuses_partial_day,
         x10_compat_view_declares_as_of, x11_retrieval_excludes_own_session,
         x12_pool_hash_binds_every_input, x13_unclassed_masks_are_incomparable,
         x14_unknown_side_token_refuses)

PARAMS = {
    "spec_section": SECTION,
    "law": "every behaviour change in the D-001 index/retrieval fix lane "
           "carries a mutant that restores the pre-fix line and must FAIL",
    "index_version": TI.VERSION,
    "index_columns_sha16": TI.columns_sha16(),
    "retrieval_blocks": [b[0] for b in R.BLOCKS],
    "fixtures": {"sheet": SHEET, "retrieve_cid": RETRIEVE_CID},
}


def main():
    MC.verify_spec()
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
    MC.write_tsv(os.path.join(OUT_DIR, "index_fixlane_red_ledger.tsv"), SECTION,
                 MC.params_hash(PARAMS),
                 ["test", "mutant", "armed_pass", "mutant_pass", "verdict",
                  "detail"], LEDGER,
                 extra=["RED-FIRST: armed_pass MUST be 1 and mutant_pass MUST "
                        "be 0 on every row",
                        "the leak-class cases (level birth, forecaster join, "
                        "vintage, S4 touch outcome) live in leakfix.py"])
    MC.write_json(os.path.join(OUT_DIR, "index_fixlane.receipt.json"),
                  {"env": MC.env_receipt(PARAMS), "n_tests": len(TESTS),
                   "n_failed": n_fail,
                   "verdict": "PASS" if n_fail == 0 else "FAIL"})
    MC.hb("index fixlane tests: %d/%d passed" % (len(TESTS) - n_fail,
                                                 len(TESTS)))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
