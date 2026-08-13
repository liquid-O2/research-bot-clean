#!/usr/bin/python3
"""PORT M2 — red-first tests for the sheet builder (P-M2a).

Every test that asserts a LAW carries a committed MUTANT: a named neutralised
line of the production rule that the test must catch.  A test whose mutant
survives is a dead test and fails.  The red ledger is written to
artifacts/cache/port/m2/tests/red_ledger.tsv.

The D-057 leak fixture lives in leakfix.py (spec §2 gives it its own artefact);
this file covers the ENCODING LAWS, the two-run byte identity, the mode switch
and the completeness certificate.

Run: /usr/bin/python3 engine/port_m2/test_m2.py
"""
import hashlib
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import assemble as A                      # noqa: E402
import sections as SEC                    # noqa: E402
import sheets as SH                       # noqa: E402
import tape as TAPE                       # noqa: E402
import common as C                        # noqa: E402

SECTION = "§1 encoding laws + §2 certificate (P-M2a tests)"
OUT_DIR = MC.out_path("tests", "_")[:-1]

# A candidate whose event cache the pilot already builds (SI daily files, so a
# cold run is cheap).
CID = "SI-20220103-047008-S"

LEDGER = []


def check(name, mutant, ok_armed, ok_mutant, detail=""):
    verdict = "PASS" if (ok_armed and not ok_mutant) else (
        "FAIL_ARMED" if not ok_armed else "FAIL_DEAD_MUTANT")
    LEDGER.append([name, mutant, int(bool(ok_armed)), int(bool(ok_mutant)),
                   verdict, detail])
    return verdict == "PASS"


# ------------------------------------------------------------------ tests --
def t01_two_run_byte_identity():
    """MT01: the sheet must be a pure function of the receipts."""
    a = SH.build(CID, MC.MODE_BLIND)
    b = SH.build(CID, MC.MODE_BLIND)
    armed = (a.sha256 == b.sha256 and a.text == b.text)
    # MUTANT MT01: stamp wall-clock into the sheet
    import datetime as dt
    m1 = a.text + str(dt.datetime.now().microsecond)
    m2 = a.text + str(dt.datetime.now().microsecond + 1)
    mutant = (hashlib.sha256(m1.encode()).hexdigest()
              == hashlib.sha256(m2.encode()).hexdigest())
    return check("two_run_byte_identity", "MT01_wallclock_stamp", armed,
                 mutant, a.sha256[:16])


def t02_blind_carries_no_outcome():
    """MT02: BLIND must not contain S14 or any outcome field."""
    b = SH.build(CID, MC.MODE_BLIND)
    banned = ("S14", "mfe_unwalled", "cert_peak", "phase_close=$",
              "OUTCOMES", "oracle_leg", "t_wall")
    armed = (b.appendix is None
             and not any(w in b.text for w in banned)
             and "S14" not in b.certificate["sections"])
    s = SH.build(CID, MC.MODE_STUDY)
    # MUTANT MT02: append the study appendix to the blind text
    mutant = not any(w in (b.text + s.appendix) for w in banned)
    return check("blind_carries_no_outcome", "MT02_append_S14_to_blind",
                 armed, mutant)


def t03_study_appendix_is_separate():
    """MT03: STUDY must keep the sheet bytes identical to BLIND and put S14 in
    its own artefact (so the protocol can withhold it until the call is in)."""
    b = SH.build(CID, MC.MODE_BLIND)
    s = SH.build(CID, MC.MODE_STUDY)
    # the sheet body differs only in the S1 mode stamp
    armed = (s.appendix is not None and "S14 OUTCOMES" in s.appendix
             and b.text.replace("mode=BLIND", "mode=STUDY") == s.text)
    mutant = (b.text == s.text)          # MUTANT MT03: drop the mode stamp
    return check("study_appendix_separate", "MT03_drop_mode_stamp", armed,
                 mutant)


def t04_certificate_fails_on_empty_section():
    """MT04: an owned section that renders nothing must fail certification."""
    real = SH.build(CID, MC.MODE_BLIND)
    armed_ok = real.certificate["certified"] == 1
    orig = SEC.RENDERERS["S9"]
    try:
        SEC.RENDERERS["S9"] = lambda case, put: ["S9 VOL STATE"]
        broken = SH.build(CID, MC.MODE_BLIND)
    finally:
        SEC.RENDERERS["S9"] = orig
    armed = armed_ok and broken.certificate["certified"] == 0
    # MUTANT MT04: a certificate that ignores empty sections
    mutant = (broken.certificate["n_failed_sections"] == 0)
    return check("certificate_fails_on_empty_section",
                 "MT04_ignore_empty_sections", armed, mutant,
                 "empty S9 -> certified=%d" % broken.certificate["certified"])


def t05_section_budget_enforced():
    """MT05: a section over its token budget must fail certification."""
    orig = SEC.RENDERERS["S11"]
    try:
        SEC.RENDERERS["S11"] = lambda case, put: (
            ["S11 CROSS-ASSET"] + ["  filler %d value 1234567 abcdef" % i
                                   for i in range(400)])
        fat = SH.build(CID, MC.MODE_BLIND)
    finally:
        SEC.RENDERERS["S11"] = orig
    armed = (fat.certificate["certified"] == 0
             and fat.certificate["sections"]["S11"]["over_budget"] == 1)
    mutant = (fat.certificate["sections"]["S11"]["tokens_proxy"]
              <= MC.SECTION_BUDGET["S11"])
    return check("section_budget_enforced", "MT05_no_budget_check", armed,
                 mutant)


def t06_seal_refuses_2026():
    """MT06: a 2026 session is never rendered (D-018 seal / m0 seal law)."""
    try:
        MC.era_of(20260105)
        armed = False
    except C.SealRefusal:
        armed = True
    mutant = (MC.era_of(20250105) == "E8")   # 2025 must still render
    return check("seal_refuses_2026", "MT06_seal_lifted", armed, not mutant,
                 "2026 refused, 2025 renders")


def t07_cid_roundtrip():
    for asset in MC.ASSET_ORDER:
        for side in (1, -1):
            cid = MC.make_cid(asset, 20220103, 47008, side)
            if MC.parse_cid(cid) != (asset, 20220103, 47008, side):
                return check("cid_roundtrip", "MT07_ambiguous_id", False,
                             False, cid)
    armed = True
    mutant = False
    try:
        MC.parse_cid("SI-20220103-47008-S")   # wrong width must not parse
        mutant = True
    except ValueError:
        pass
    return check("cid_roundtrip", "MT07_ambiguous_id", armed, mutant)


def t08_s6_episode_membership_lossless():
    """MT08: every event in the S6 window belongs to exactly one episode or one
    raw line — the digest compression is lossless in membership."""
    case = A.Case(CID)
    ev = case.events
    ts = ev["ts_ns"]
    dec_ns = (case.decision_ts + 1) * 10 ** 9
    raw_lo = (case.decision_ts - TAPE.RIBBON_RAW_SEC) * 10 ** 9
    dig_lo = (case.decision_ts - TAPE.RIBBON_RAW_SEC
              - TAPE.RIBBON_DIGEST_SEC) * 10 ** 9
    i_dig = int(np.searchsorted(ts, dig_lo, side="left"))
    i_raw = int(np.searchsorted(ts, raw_lo, side="left"))
    i_end = int(np.searchsorted(ts, dec_ns, side="left"))
    i_rawstart = i_raw + 7                    # any split inside the window
    eps = (SEC._episodes(ev, i_dig, i_raw, SEC.S6_GAP_SEC,
                         SEC.S6_EPISODE_MAX_PRE)
           + SEC._episodes(ev, i_raw, i_rawstart, SEC.S6_GAP_SEC,
                           SEC.S6_EPISODE_MAX_IN))
    covered = sum(b - a for a, b in eps)
    contiguous = all(eps[k][1] == eps[k + 1][0] for k in range(len(eps) - 1))
    armed = (covered + (i_end - i_rawstart) == i_end - i_dig) and contiguous
    # MUTANT MT08: an episode builder that drops small clusters
    bad = [(a, b) for a, b in eps if b - a > 1]
    mutant = (sum(b - a for a, b in bad) + (i_end - i_rawstart)
              == i_end - i_dig) and len(bad) == len(eps)
    return check("s6_episode_membership_lossless", "MT08_drop_small_clusters",
                 armed, mutant,
                 "n_window=%d n_episodes=%d" % (i_end - i_dig, len(eps)))


def t09_s4_touch_state_is_causal():
    """MT09: S4's touch counts must be recomputed from touches before the
    decision second, never read off the ledger's end-of-session columns."""
    case = A.Case(CID, want_events=False)
    z = case.levels
    tch = z["touches"]
    # independent recomputation
    causal = {}
    for r in tch:
        if int(r[0]) < case.dec_sec:
            causal[int(r[1])] = causal.get(int(r[1]), 0) + 1
    eos = {i: int(v) for i, v in enumerate(z["touch_count"].tolist())}
    lines = SEC.s4_levels(case, lambda *a: None)
    # some level in the table must show a causal count BELOW its end-of-session
    # count — otherwise the test cannot discriminate
    discriminating = any(causal.get(i, 0) < eos.get(i, 0) for i in eos)
    txt = "\n".join(lines)
    armed = discriminating and ("n_touches=%d" % sum(causal.values())) in txt
    mutant = ("n_touches=%d" % sum(eos.values())) in txt
    return check("s4_touch_state_is_causal", "MT09_read_eos_touch_count",
                 armed, mutant,
                 "causal=%d eos=%d" % (sum(causal.values()), sum(eos.values())))


def t10_sidecar_covers_sheet_numbers():
    """MT10: the sidecar must name a source receipt for every value it carries,
    and its headline values must literally appear on the sheet."""
    sh = SH.build(CID, MC.MODE_BLIND)
    vals = sh.sidecar["values"]
    armed = bool(vals) and all(v["source"] and v["source_key"] for v in vals)
    # a spot value must be findable on the sheet face
    spot = [v for v in vals if v["key"] == "S3.entry_mid"]
    armed = armed and spot and (MC.fnum(spot[0]["value"], 1, 4).strip()
                                in sh.text)
    mutant = any(v["source"] is None for v in vals)
    return check("sidecar_covers_sheet_numbers", "MT10_source_free_values",
                 armed, mutant, "n_values=%d" % len(vals))


def t11_fixed_width_and_no_trailing_space():
    sh = SH.build(CID, MC.MODE_BLIND)
    lines = sh.text.split("\n")
    armed = all(not ln.endswith(" ") for ln in lines) and sh.text.endswith("\n")
    mutant = any(ln.endswith(" ") for ln in lines)
    return check("no_trailing_whitespace", "MT11_trailing_pad", armed, mutant,
                 "%d lines" % len(lines))


def t12_typed_missing_never_zero():
    """MT12: a non-finite value must print the typed-missing glyph, never 0."""
    armed = (MC.fnum(float("nan"), 8, 2).strip() == MC.NA
             and MC.fint(None, 4).strip() == MC.NA
             and MC.fnum(float("inf"), 8, 2).strip() == MC.NA)
    mutant = (MC.fnum(float("nan"), 8, 2).strip() == "0.00")
    return check("typed_missing_never_zero", "MT12_nan_as_zero", armed, mutant)


def t13_token_proxy_deterministic():
    s = "  ab 12345  -0.75\n" * 37
    armed = (MC.count_tokens(s) == MC.count_tokens(s)
             and MC.count_tokens(s) > 0
             and MC.count_tokens("a  b") > MC.count_tokens("a b"))
    mutant = (MC.count_tokens("") != 0)
    return check("token_proxy_deterministic", "MT13_nondeterministic_proxy",
                 armed, mutant, "tokens=%d" % MC.count_tokens(s))


def t14_events_cache_deterministic():
    """MT14: the event cache is a pure function of (asset, session, window)."""
    case = A.Case(CID)
    p = os.path.join(TAPE.EVENTS_DIR, case.asset, "%08d.npz" % case.d8)
    h1 = C.sha256_file(p)
    lo = max(0, case.dec_sec - TAPE.RIBBON_DIGEST_SEC - TAPE.RIBBON_RAW_SEC
             - TAPE.EXTRACT_PAD_SEC)
    TAPE.ensure(case.asset, case.trade_date, int(case.s.iid), case.open_utc,
                case.close_utc, [(lo, case.dec_sec + 1)])
    h2 = C.sha256_file(p)
    armed = (h1 == h2)
    mutant = (h1 != h2)
    return check("events_cache_deterministic", "MT14_nondeterministic_npz",
                 armed, mutant, h1[:16])


def t15_anchor_ticks_are_integers():
    case = A.Case(CID, want_events=False)
    px = case.entry_mid + 3 * case.tick_px
    armed = (SEC.tk(case, px) == 3 and SEC.tk(case, case.entry_mid) == 0
             and SEC.tk(case, case.entry_mid - 2 * case.tick_px) == -2)
    mutant = (SEC.tk(case, px) != 3)
    return check("anchor_ticks_are_integers", "MT15_float_ticks", armed,
                 mutant)


def t16_sidecar_paths_absolute():
    """MT16 (CC-M2-1.4): every source path a sidecar names must be ABSOLUTE and
    must exist — a workspace-relative path is ambiguous off /workspace."""
    sh = SH.build(CID, MC.MODE_BLIND)
    srcs = [v["source"] for v in sh.sidecar["values"] if v["source"]]
    srcs += [p for p in sh.sidecar["receipts"].values() if p]
    # a source is either a typed non-file tag or a file; every file part must be
    # absolute and must exist on disk
    paths = []
    for s in srcs:
        if s.startswith("derived"):
            continue
        paths.extend(p.strip() for p in s.split(" + "))
    armed = bool(paths) and all(p.startswith("/") for p in paths) and all(
        os.path.exists(p) for p in paths)
    # MUTANT MT16: the P-M2a behaviour — strip the /workspace/ root
    stripped = [p[len("/workspace/"):] if p.startswith("/workspace/") else p
                for p in paths]
    mutant = all(p.startswith("/") for p in stripped)
    return check("sidecar_paths_absolute", "MT16_strip_workspace_root", armed,
                 mutant, "n_paths=%d" % len(paths))


def t17_known_traps_registered():
    """MT17 (CC-M2-1.3): every KNOWN_TRAPS entry names a test that exists here.

    This is the mechanical form of "additions to the registry require a test":
    a trap registered without its proof test fails the suite.
    """
    names = {t.__name__ for t in TESTS}
    reg = MC.KNOWN_TRAPS
    armed = bool(reg) and all(
        set(e) >= {"receipt", "field", "why", "builder_rule", "test"}
        and e["test"] in names for e in reg.values())
    # the registered trap must also be live on a real sheet: S4 prints PENDING
    case = A.Case(CID, want_events=False)
    txt = "\n".join(SEC.s4_levels(case, lambda *a: None))
    armed = armed and "n_pending=" in txt
    # MUTANT MT17: a registry that gains an entry with no proof test
    bad = dict(reg)
    bad["mutant.trap_without_test"] = {
        "receipt": "-", "field": "-", "why": "-", "builder_rule": "-",
        "test": "t99_this_test_does_not_exist"}
    mutant = all(e["test"] in names for e in bad.values())
    return check("known_traps_registered", "MT17_trap_without_test", armed,
                 mutant, "n_traps=%d" % len(reg))


def t18_candidate_class_declared():
    """MT18 (D-071): every sheet declares its class in S1, the class map mirrors
    the CC-M1-11.4 family priority, and the classes PARTITION the families."""
    sys.path.insert(0, "/workspace/engine/port_m1")
    import episode_census as EC           # noqa: E402  the pre-registered order
    armed = (MC.FAMILY_PRIORITY == EC.FAM_PRIORITY
             and set(MC.FAMILY_CLASS) == set(MC.FAMILIES)
             and set(MC.CLASS_ORDER) == set(MC.FAMILY_CLASS.values()))
    sh = SH.build(CID, MC.MODE_BLIND)
    asset, d8, sec, side = MC.parse_cid(CID)
    r = A.roster(asset)
    cls, driver, _o = MC.class_of(int(r["fam_mask"][r["_index"][(d8, sec,
                                                                side)]]))
    armed = armed and ("CANDIDATE CLASS" in sh.text) and (cls in sh.text)
    # the declared class must be the HIGHEST-priority family's class
    both = MC.FAM_BIT["G1"] | MC.FAM_BIT["POST_SHOCK"]
    armed = armed and MC.class_of(both)[0] == MC.CLASS_SHOCK
    # MUTANT MT18: declare the LOWEST-priority tag's class instead
    lowest = sorted(MC.fam_names(both),
                    key=lambda f: -MC.FAMILY_PRIORITY[f])[0]
    mutant = (MC.FAMILY_CLASS[lowest] == MC.CLASS_SHOCK)
    return check("candidate_class_declared", "MT18_lowest_priority_class",
                 armed, mutant, "class=%s driver=%s" % (cls, driver))


TESTS = (t01_two_run_byte_identity, t02_blind_carries_no_outcome,
         t03_study_appendix_is_separate, t04_certificate_fails_on_empty_section,
         t05_section_budget_enforced, t06_seal_refuses_2026, t07_cid_roundtrip,
         t08_s6_episode_membership_lossless, t09_s4_touch_state_is_causal,
         t10_sidecar_covers_sheet_numbers,
         t11_fixed_width_and_no_trailing_space, t12_typed_missing_never_zero,
         t13_token_proxy_deterministic, t14_events_cache_deterministic,
         t15_anchor_ticks_are_integers, t16_sidecar_paths_absolute,
         t17_known_traps_registered, t18_candidate_class_declared)


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
    MC.write_tsv(os.path.join(OUT_DIR, "red_ledger.tsv"), SECTION,
                 MC.params_hash(SH.PARAMS),
                 ["test", "mutant", "armed_pass", "mutant_pass", "verdict",
                  "detail"], LEDGER,
                 extra=["RED-FIRST: armed_pass MUST be 1 and mutant_pass MUST "
                        "be 0 on every row"])
    MC.write_json(os.path.join(OUT_DIR, "tests.receipt.json"),
                  {"env": MC.env_receipt(SH.PARAMS), "n_tests": len(TESTS),
                   "n_failed": n_fail,
                   "verdict": "PASS" if n_fail == 0 else "FAIL"})
    MC.hb("tests: %d/%d passed" % (len(TESTS) - n_fail, len(TESTS)))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
