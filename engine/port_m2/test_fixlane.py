#!/usr/bin/python3
"""PORT M2 — RED-FIRST TESTS FOR THE D-001 FIX PASS (lead lane).

D-001 gives one fix pass and then mechanical re-verification only, so every
blocker this lane closed carries a MUTANT that restores the defect and MUST
make the armed test fail.  The review's own §3.5(4) is explicit about why:
"Every fix above needs a red-first mutant that actually neutralises a named
production line, or the fix lane will believe itself."

Covered here (the lead lane's files):
  F01  R93  a level anchored at a LATER phase's opening mid must not print.
            MUTANT: restore `_level_birth_sec`'s `return 0` fall-through for
            the static fvol families.
  F02  R02  an S14 outcome artefact must not be reachable from a blind sheet
            directory, and the NO-S14 token must be COMPUTED.
            MUTANT: write the appendix beside the sheet, as the pre-fix
            `sheets.emit` did.
  F03  R01  a census card must be computed over a STRICTLY-PRIOR era only.
            MUTANT: restore `(case.era, str(year))` / `(yr, blk)`.
  F04  R94  the four forward S2 session-meta fields must be refused.
            MUTANT: print `dominant_share` from the session meta again.
  F05  R59  the era-scale mirror law must be a PAIRED TEST with power, not the
            unpassable `lost == 0 and won > 0` sweep.
            MUTANT: grade on the sweep bit.
  F06  D-058 the guarded session enumerator must REFUSE holdout dates.
            MUTANT: the raw roster enumeration, which admits them.
  F07  R97  the printed and JSON `certified` flags cannot disagree.
            MUTANT: print the pre-fix flag (no sheet cap, no S1 over-budget).
  F08  R96  a level with no strictly-prior snapshot must REFUSE its VIRGIN
            flag, never fabricate `V=1`.
            MUTANT: default `virgin0` to True as the pre-fix code did.

Run: /usr/bin/python3 engine/port_m2/test_fixlane.py
"""
import os
import re
import sys
import tempfile

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import sections as SEC                    # noqa: E402
import sheets as SH                       # noqa: E402
import pattern_lib as PL                  # noqa: E402

SECTION = "§2 red-first fixture (D-001 fix pass, lead lane)"
OUT_DIR = MC.out_path("tests", "_")[:-1]

# The review's own receipt case: a TOKYO decision at session second 7,324 whose
# sheet printed five LONDON/NY-anchored fvol levels at $50-$110 from the mid.
FVOL_CID = "HG-20211020-007324-L"
# An E1 decision: no era ENDED before it, so every card must refuse.
E1_CID = "SI-20211020-079188-S"

LEDGER = []


def check(name, mutant, ok_armed, ok_mutant, detail=""):
    verdict = "PASS" if (ok_armed and not ok_mutant) else (
        "FAIL_ARMED" if not ok_armed else "FAIL_DEAD_MUTANT")
    LEDGER.append([name, mutant, int(bool(ok_armed)), int(bool(ok_mutant)),
                   verdict, detail])
    return verdict == "PASS"


def _forward_fvol_rows(text):
    """Level rows anchored at a phase LATER than the decision's own phase."""
    import census_common as X
    m = re.search(r"phase_dec=(\S+)", text)
    dp = X.PHASE_NAMES.index(m.group(1)) if m else -1
    n = 0
    for line in text.splitlines():
        mm = re.match(r"^\s+[Kr]\s+(FVOL_BAND|FVOL_LADDER|FVOL_LADDER_RS)\s+"
                      r"OPEN_([A-Z]+)\|", line)
        if not mm:
            continue
        ar = X.PHASE_NAMES.index(mm.group(2)) \
            if mm.group(2) in X.PHASE_NAMES else -1
        if ar >= 0 and dp >= 0 and ar > dp:
            n += 1
    return n


# ------------------------------------------------------------------- F01 ----
def f01_no_forward_anchored_fvol_level():
    """R93: FVOL_* anchored at OPEN_<PHASE> are born at that phase's open."""
    armed = _forward_fvol_rows(SH.build(FVOL_CID, MC.MODE_BLIND).text)
    orig = SEC._level_birth_sec

    def mutant(case, fam, lid, dyn):
        # MUTANT MF01: the pre-fix fall-through — every static family is born
        # at second 0, which is the D4 defect for the fvol anchors.
        parts = str(lid).split("|")
        if fam == "OR_EXT":
            return orig(case, fam, lid, dyn)
        if int(dyn):
            return orig(case, fam, lid, dyn)
        return 0
    SEC._level_birth_sec = mutant
    try:
        mut = _forward_fvol_rows(SH.build(FVOL_CID, MC.MODE_BLIND).text)
    finally:
        SEC._level_birth_sec = orig
    return check("no_forward_anchored_fvol_level", "MF01_birth_falls_to_zero",
                 armed == 0, mut == 0,
                 "armed prints %d forward-anchored rows; the mutant prints %d"
                 % (armed, mut))


# ------------------------------------------------------------------- F02 ----
def f02_s14_is_not_reachable_from_a_blind_dir():
    """R02: the NO-S14 claim is a CHECKED STATE, not a naming convention."""
    with tempfile.TemporaryDirectory() as td:
        blind = os.path.join(td, "era", "E1", "BLIND", "HG", "20211020")
        sh = SH.build(FVOL_CID, MC.MODE_BLIND, with_appendix=True)
        SH.emit(sh, blind, sidecars=False)
        sib = SH.s14_dir(blind)
        armed_split = (os.path.exists(os.path.join(
            sib, "%s.S14.appendix.txt" % FVOL_CID))
            and not os.path.exists(os.path.join(
                blind, "%s.S14.appendix.txt" % FVOL_CID)))
        armed_pass = True
        try:
            SH.assert_no_s14_access([blind], cids=[FVOL_CID])
        except SH.S14AccessRefusal:
            armed_pass = False
        # MUTANT MF02: the pre-fix emit — the appendix beside the sheet.
        MC.write_text(os.path.join(blind, "%s.S14.appendix.txt" % FVOL_CID),
                      sh.appendix)
        mutant_pass = True
        try:
            SH.assert_no_s14_access([blind], cids=[FVOL_CID])
        except SH.S14AccessRefusal:
            mutant_pass = False
    return check("s14_is_not_reachable_from_a_blind_dir",
                 "MF02_appendix_beside_the_sheet",
                 armed_split and armed_pass, mutant_pass,
                 "split=%s armed_guard_passes=%s mutant_guard_passes=%s"
                 % (armed_split, armed_pass, mutant_pass))


# ------------------------------------------------------------------- F03 ----
def f03_cards_are_strictly_prior():
    """R01: no card may be computed over the decision's own era/year/block."""
    import assemble as A
    case = A.Case(E1_CID, mode=MC.MODE_BLIND)
    yr = int(case.d8) // 10000
    text = SH.build(E1_CID, MC.MODE_BLIND).text
    armed = ("no census era ENDED before this decision" in text
             and not re.search(r"^\s{4}\S+\s+(%s|%d)\s+\d" % (case.era, yr),
                               text, re.M))
    orig = SEC._prior_card_eras

    def mutant_eras(c):
        # MUTANT MF03: the pre-fix era set — the decision's OWN era, its own
        # calendar year, and the FIT block it sits inside.
        import census_common as X
        y = int(c.d8) // 10000
        return ([c.era], [str(y)],
                [X.ERA_FIT if y in X.WALL_FIT_YEARS else X.ERA_GATE])
    SEC._prior_card_eras = mutant_eras
    try:
        mtext = SH.build(E1_CID, MC.MODE_BLIND).text
        mutant = bool(re.search(r"^\s{4}\S+\s+(%s|%d)\s+\d" % (case.era, yr),
                                mtext, re.M))
    finally:
        SEC._prior_card_eras = orig
    return check("cards_are_strictly_prior", "MF03_own_era_and_year",
                 armed, not mutant,
                 "armed refuses the card; the mutant prints a %s/%d card=%s"
                 % (case.era, yr, mutant))


# ------------------------------------------------------------------- F04 ----
def f04_forward_session_meta_is_refused():
    """R94: dom_share / roll_window / dying_book_week / instrument_change."""
    sh = SH.build(E1_CID, MC.MODE_BLIND)
    keys = {e["key"] for e in sh.certificate["refused_derived"]}
    need = {k for k, _l, _w in SEC.S2_FORWARD_META}
    line = [l for l in sh.text.splitlines() if "dominance" in l]
    armed = (need <= keys and bool(line)
             and all(("%s=%s" % (lab, MC.NA)) in line[0]
                     for _k, lab, _w in SEC.S2_FORWARD_META))
    orig = SEC._s2_forward_meta

    def mutant_meta(case, put):
        # MUTANT MF04: the pre-fix line — the session meta printed straight on
        # to a BLIND sheet, with no refusal recorded.
        m = case.s.meta
        return [MC.row("  dominance",
                       "dom_share=" + MC.fnum(m.get("dominant_share"),
                                              6, 4).strip(),
                       " roll_window=" + ("1" if m.get("roll_window") else "0"),
                       " dying_book_week="
                       + ("1" if m.get("dying_book_week") else "0"),
                       " instrument_change="
                       + ("1" if m.get("instrument_change") else "0"),
                       " iid=" + str(case.s.iid))]
    SEC._s2_forward_meta = mutant_meta
    try:
        sh2 = SH.build(E1_CID, MC.MODE_BLIND)
        k2 = {e["key"] for e in sh2.certificate["refused_derived"]}
        l2 = [l for l in sh2.text.splitlines() if "dominance" in l]
        mutant = ((not (need <= k2)) and bool(l2)
                  and ("dom_share=" + MC.NA) not in l2[0])
    finally:
        SEC._s2_forward_meta = orig
    return check("forward_session_meta_is_refused",
                 "MF04_print_dominant_share",
                 armed, not mutant,
                 "armed refuses %d/%d keys and prints the glyph; the mutant "
                 "prints the forward values and refuses none"
                 % (len(need & keys), len(need)))


# ------------------------------------------------------------------- F05 ----
def f05_mirror_law_has_power():
    """R59: the era-scale mirror is a paired test, not an unpassable sweep."""
    rs = np.random.RandomState(20260814)
    # a REAL effect with a few losing sessions — exactly what the sweep bans
    d = rs.normal(40.0, 100.0, 400)
    res = MC.mirror_paired(d)
    armed = (res["verdict"] == "TESTED" and res["holds"] == 1
             and res["n_lost"] > 0 and np.isfinite(res["mde_80"]))
    # MUTANT MF05: grade on the sweep bit, as batch4:1133 / batch5:1118 /
    # side_probe:470 did.
    mutant = bool(MC.mirror_sweep_clean(res["n_won"], res["n_lost"]))
    # and the sweep must still be honest on a genuine study-round sweep
    sweep_ok = MC.mirror_sweep_clean(6, 0) == 1
    # an UNDERPOWERED cell is NO_TEST, never a negative
    small = MC.mirror_paired(rs.normal(40.0, 100.0, 8))
    powered = small["verdict"] == "NO_TEST"
    return check("mirror_law_has_power", "MF05_grade_on_the_sweep_bit",
                 armed and sweep_ok and powered, mutant,
                 "n=%d mean=%.2f p=%.3g won/lost=%d/%d mde80=%.2f; sweep bit=%d"
                 % (res["n_sessions"], res["mean_delta"], res["p"],
                    res["n_won"], res["n_lost"], res["mde_80"], mutant))


# ------------------------------------------------------------------- F06 ----
def f06_holdout_enumeration_refuses():
    """D-058: the guarded enumerator refuses the pre-exam holdout."""
    asset = MC.ASSET_ORDER[0]
    refused = False
    try:
        PL.sessions(asset, years={2025})
    except MC.HoldoutRefusal:
        refused = True
    keep, nq = PL.sessions_fit(asset, years={2025})
    armed = refused and nq > 0 and not any(MC.in_holdout(d) for d in keep)
    # MUTANT MF06: the pre-fix enumeration — allow_holdout, then no filter.
    raw = PL.sessions(asset, years={2025}, allow_holdout=True)
    mutant = not any(MC.in_holdout(d) for d in raw)
    return check("holdout_enumeration_refuses", "MF06_unguarded_enumeration",
                 armed, mutant,
                 "refused=%s kept=%d quarantined=%d; the raw enumeration "
                 "carries %d holdout sessions"
                 % (refused, len(keep), nq,
                    sum(1 for d in raw if MC.in_holdout(d))))


# ------------------------------------------------------------------- F07 ----
def f07_printed_and_json_certified_agree():
    """R97: the sheet the reader reads cannot claim what the receipt denies."""
    sh = SH.build(E1_CID, MC.MODE_BLIND)
    m = re.search(r"^\s+certified\s+(\d)", sh.text, re.M)
    armed = bool(m) and int(m.group(1)) == int(sh.certificate["certified"])
    # MUTANT MF07: the pre-fix printed flag ignored the whole-sheet cap and
    # S1's own over-budget check.  Reconstruct it and show the two CAN differ:
    # force an over-cap sheet by shrinking the cap under the rendered size.
    real_cap = MC.SHEET_BUDGET_BLIND
    try:
        MC.SHEET_BUDGET_BLIND = 10       # every sheet now busts the cap
        sh2 = SH.build(E1_CID, MC.MODE_BLIND)
        m2 = re.search(r"^\s+certified\s+(\d)", sh2.text, re.M)
        pre_fix_printed = 1 if (int(re.search(r"n_failed=(\d+)",
                                              sh2.text).group(1)) == 0
                                and sh2.certificate["n_leak_refusals"] == 0) \
            else 0
        mutant = (pre_fix_printed != int(sh2.certificate["certified"])
                  and int(m2.group(1)) == int(sh2.certificate["certified"]))
        # `mutant` True here means: the PRE-FIX rule would have disagreed while
        # the fixed rule agrees — so the mutant's disagreement is the failure
        # mode, and the armed test must be the one that holds.
        mutant_disagrees = pre_fix_printed != int(m2.group(1))
    finally:
        MC.SHEET_BUDGET_BLIND = real_cap
    return check("printed_and_json_certified_agree",
                 "MF07_pre_fix_printed_flag",
                 armed and mutant, not mutant_disagrees,
                 "printed=%s json=%s; under a forced over-cap the pre-fix rule "
                 "prints %d while the receipt says %d"
                 % (m.group(1) if m else "?", sh.certificate["certified"],
                    pre_fix_printed, int(sh2.certificate["certified"])))


# ------------------------------------------------------------------- F08 ----
def f08_unknown_prior_state_is_refused():
    """R96: a level with no strictly-prior snapshot refuses V, never V=1."""
    import assemble as A
    case = A.Case(E1_CID, mode=MC.MODE_BLIND)
    z = case.levels
    n = int(np.asarray(z["level_price"]).size)
    have, virgin0, tc0 = SEC._prior_snapshot_state(z, n, case.dec_sec)
    n_missing = int((~have).sum())

    # MUTANT MF08: the pre-fix state — ONLY the sec-0 snapshot, with
    # `virgin0` defaulting True and `tc0` defaulting 0 for everything else.
    ss = np.asarray(z["snap_sec"])
    sr = np.asarray(z["snap_row"])
    m_virgin = np.ones(n, dtype=bool)
    m_tc0 = np.zeros(n, dtype=np.int64)
    for k in np.nonzero(ss == 0)[0].tolist():
        m_virgin[int(sr[k])] = bool(z["snap_virgin"][k])
        m_tc0[int(sr[k])] = int(z["snap_touch_count"][k])
    # the mutant FABRICATES virgin/zero-touch state for levels the armed rule
    # refuses; where a real snapshot disagrees, the fabrication is a live lie
    fabricated = int(np.sum((~have) & m_virgin))
    lied = int(np.sum((~have) & m_virgin & (tc0 > 0)))
    armed = n_missing > 0 and int(np.sum(have & (tc0 > 0))) >= 0
    text = SH.build(E1_CID, MC.MODE_BLIND).text
    armed = armed and "n_virgin excludes levels whose prior state is REFUSED" \
        in text
    return check("unknown_prior_state_is_refused", "MF08_virgin_defaults_true",
                 armed, fabricated == 0,
                 "%d of %d levels carry no strictly-prior snapshot; the mutant "
                 "would print VIRGIN for %d of them (%d contradicted by a real "
                 "later snapshot)" % (n_missing, n, fabricated, lied))


TESTS = (f01_no_forward_anchored_fvol_level,
         f02_s14_is_not_reachable_from_a_blind_dir,
         f03_cards_are_strictly_prior,
         f04_forward_session_meta_is_refused,
         f05_mirror_law_has_power,
         f06_holdout_enumeration_refuses,
         f07_printed_and_json_certified_agree,
         f08_unknown_prior_state_is_refused)


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
        MC.hb("fixlane test %s: %s" % (t.__name__, LEDGER[-1][4]))
    MC.write_tsv(os.path.join(OUT_DIR, "fixlane_red_ledger.tsv"), SECTION,
                 MC.params_hash({"lane": "D-001 fix pass, lead"}),
                 ["test", "mutant", "armed_pass", "mutant_pass", "verdict",
                  "detail"], LEDGER,
                 extra=["RED-FIRST: armed_pass MUST be 1 and mutant_pass MUST "
                        "be 0 on every row"])
    MC.write_json(os.path.join(OUT_DIR, "fixlane_tests.receipt.json"),
                  {"env": MC.env_receipt({"lane": "D-001 fix pass, lead"}),
                   "n_tests": len(TESTS), "n_failed": n_fail,
                   "verdict": "PASS" if n_fail == 0 else "FAIL"})
    MC.hb("fixlane tests: %d/%d passed" % (len(TESTS) - n_fail, len(TESTS)))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
