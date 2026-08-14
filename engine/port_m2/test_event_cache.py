#!/usr/bin/python3
"""PORT M2 — red-first tests for the CORPUS EVENT CACHE (CC-M2-15.4).

The law under test is the one that can silently destroy the program: the
2025-07-01 HOLDOUT EXCLUSION (CC-M2-15.3).  A holdout session that reaches the
extractor is pre-exam exposure, so the guard is tested three ways —

  EC01  an INCLUDED 2025-08 session must be REFUSED before any payload file is
        opened (the mandate's named red case);
  EC02  the enumerated universe must contain no date at/after the boundary,
        and must still contain the last legal day (an off-by-one that ate
        2025-06-30 would also be a defect);
  EC03  the verifier must FAIL when a holdout artefact is present in the cache
        directory (the guard is asserted against the disk, not only the code);

plus the two properties that make the cache trustworthy —

  EC04  the driver's canonical window == the era renderer's construction, so a
        session already extracted by era_build is a HIT, never a re-extraction;
  EC05  two-run byte identity of a real extraction (npz + meta json).

Every test carries a committed MUTANT: a neutralised production rule the test
must catch.  A test whose mutant survives is dead and fails.

Run: /usr/bin/python3 engine/port_m2/test_event_cache.py
"""
import os
import shutil
import sys
import tempfile

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import assemble as A                      # noqa: E402
import tape as TAPE                       # noqa: E402
import event_cache as EC                  # noqa: E402

SECTION = "§CC-M2-15.4 event-cache guards (red-first)"
OUT_DIR = MC.out_path("tests", "_")[:-1]

LEDGER = []


def check(name, mutant, ok_armed, ok_mutant, detail=""):
    verdict = "PASS" if (ok_armed and not ok_mutant) else (
        "FAIL_ARMED" if not ok_armed else "FAIL_DEAD_MUTANT")
    LEDGER.append([name, mutant, int(bool(ok_armed)), int(bool(ok_mutant)),
                   verdict, detail])
    return verdict == "PASS"


def _a_holdout_session(month=8):
    """A REAL 2025-08 (holdout) session-asset that exists on disk."""
    for asset in MC.ASSET_ORDER:
        for d in sorted(A.session_index(asset)):
            if 20250000 + month * 100 <= d < 20250000 + (month + 1) * 100:
                return asset, int(d)
    raise RuntimeError("no 2025-%02d session on disk" % month)


def _a_legal_session():
    """A small pre-holdout session-asset with a cached extraction available."""
    asset = "SI"
    d8s = sorted(int(x) for x in np.unique(A.roster(asset)["date8"])
                 if int(x) < EC.HOLDOUT_START)
    return asset, d8s[0]


# ------------------------------------------------------------------ tests --
def ec01_holdout_session_is_refused():
    """EC01: an INCLUDED 2025-08 session must be caught by the guard."""
    asset, d8 = _a_holdout_session(8)
    armed = False
    try:
        EC.assert_extractable(asset, d8)
    except EC.HoldoutRefusal:
        armed = True
    # MUTANT EM01: the guard compares against the OLD (2025-09-01) boundary the
    # lane used before CC-M2-15.3 — a 2025-08 session then sails through.
    old = EC.HOLDOUT_START
    mutant_pass = False
    try:
        EC.HOLDOUT_START = 20250901
        try:
            EC.assert_extractable(asset, d8)
        except EC.HoldoutRefusal:
            mutant_pass = True
    finally:
        EC.HOLDOUT_START = old
    return check("ec01_holdout_session_is_refused",
                 "EM01 boundary reverted to 2025-09-01", armed, mutant_pass,
                 "%s %d" % (asset, d8))


def ec02_universe_excludes_holdout():
    """EC02: the enumerated work list carries no holdout date — and does carry
    the last legal one."""
    u = EC.universe()
    bad = [x for x in u if x[1] >= EC.HOLDOUT_START]
    has_legal_tail = any(20250601 <= d <= 20250630 for _a, d in u)
    armed = (not bad) and has_legal_tail and len(u) > 3000
    # MUTANT EM02: the enumeration drops its date filter.
    def _mutant_universe():
        out = []
        for asset in MC.ASSET_ORDER:
            for d in sorted(int(x) for x in
                            np.unique(A.roster(asset)["date8"])):
                out.append((asset, d))
        return out
    mu = _mutant_universe()
    mutant_pass = (not [x for x in mu if x[1] >= EC.HOLDOUT_START]
                   and any(20250601 <= d <= 20250630 for _a, d in mu))
    return check("ec02_universe_excludes_holdout",
                 "EM02 enumeration without the holdout filter", armed,
                 mutant_pass,
                 "universe=%d, holdout_rows=%d" % (len(u), len(bad)))


def ec03_verifier_catches_a_holdout_artefact():
    """EC03: a holdout npz planted in the cache tree must FAIL the verifier."""
    asset, d8 = _a_holdout_session(8)
    scratch = tempfile.mkdtemp(prefix="ec03_", dir=EC.SCRATCH_ROOT)
    old = TAPE.EVENTS_DIR
    try:
        TAPE.EVENTS_DIR = scratch
        os.makedirs(os.path.join(scratch, asset), exist_ok=True)
        p = os.path.join(scratch, asset, "%08d.npz" % d8)
        with open(p, "wb") as fh:
            fh.write(b"planted")
        cached = EC._cached_sessions()
        leaked = [(a, d) for a, ds in cached.items() for d in ds
                  if d >= EC.HOLDOUT_START]
        armed = len(leaked) == 1
        # MUTANT EM03: the exclusion assertion is made against the WORK LIST
        # (which is filtered by construction) instead of against the DISK, so a
        # planted/stale holdout artefact is invisible.
        work = EC.universe()
        mutant_leaked = [x for x in work if x[1] >= EC.HOLDOUT_START]
        mutant_pass = len(mutant_leaked) == 1
    finally:
        TAPE.EVENTS_DIR = old
        shutil.rmtree(scratch, ignore_errors=True)
    return check("ec03_verifier_catches_a_holdout_artefact",
                 "EM03 exclusion asserted against the work list, not the disk",
                 armed, mutant_pass, "%s %d" % (asset, d8))


def ec04_window_matches_the_era_renderer():
    """EC04: the driver's canonical window is era_build's, so an era-STUDY
    session already on disk is a cache HIT."""
    import json
    import era_build  # noqa: F401  (imported to pin the constants it uses)
    hits = miss = 0
    checked = 0
    for asset in MC.ASSET_ORDER:
        d = os.path.join(TAPE.EVENTS_DIR, asset)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".json") or checked >= 60:
                continue
            d8 = int(fn[:8])
            if d8 >= EC.HOLDOUT_START:
                continue
            with open(os.path.join(d, fn)) as fh:
                meta = json.load(fh)
            cover = [(int(a), int(b)) for a, b in meta["cover"]]
            want = TAPE._merge(EC.canonical_ranges(asset, d8))
            checked += 1
            if all(TAPE._covers(cover, a, b) for a, b in want):
                hits += 1
            else:
                miss += 1
    # The 20 PILOT sessions were extracted for ONE candidate each, so they are
    # legitimately short; the era-STUDY sessions must all be hits.
    armed = checked > 0 and hits >= checked - 20
    # MUTANT EM04: the window uses the RAW ribbon only (no 10-min digest), so
    # the cached cover would no longer be recognised as sufficient... it still
    # would (a narrower want is trivially covered).  The real mutant is the
    # opposite: a window WIDER than the renderer's, which turns every existing
    # session into a re-extraction.
    def _wide(asset, d8):
        r = A.roster(asset)
        m = r["date8"] == int(d8)
        return [(0, int(ds) + 1) for ds in np.unique(r["dec_sec"][m])]
    mhits = mchecked = 0
    for asset in MC.ASSET_ORDER:
        d = os.path.join(TAPE.EVENTS_DIR, asset)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".json") or mchecked >= 60:
                continue
            d8 = int(fn[:8])
            if d8 >= EC.HOLDOUT_START:
                continue
            with open(os.path.join(d, fn)) as fh:
                meta = json.load(fh)
            cover = [(int(a), int(b)) for a, b in meta["cover"]]
            want = TAPE._merge(_wide(asset, d8))
            mchecked += 1
            if all(TAPE._covers(cover, a, b) for a, b in want):
                mhits += 1
    mutant_pass = mchecked > 0 and mhits >= mchecked - 20
    return check("ec04_window_matches_the_era_renderer",
                 "EM04 window widened to the session open", armed, mutant_pass,
                 "checked=%d hits=%d short=%d" % (checked, hits, miss))


def ec05_two_run_byte_identity():
    """EC05: two extractions of the same session are byte-identical."""
    asset, d8 = _a_legal_session()
    s1 = tempfile.mkdtemp(prefix="ec05a_", dir=EC.SCRATCH_ROOT)   # D-018
    s2 = tempfile.mkdtemp(prefix="ec05b_", dir=EC.SCRATCH_ROOT)
    try:
        a1, m1, c1 = EC._reextract_to(s1, asset, d8)
        a2, m2, c2 = EC._reextract_to(s2, asset, d8)
        armed = (a1 == a2 and m1 == m2 and c1 == c2)
        # MUTANT EM05: the cache stamps wall-clock into its meta, so two runs
        # of the same session no longer agree — and the spec-pin normalisation
        # must NOT be wide enough to absorb it.
        import json
        p = os.path.join(s2, asset, "%08d.json" % d8)
        with open(p) as fh:
            meta = json.load(fh)
        meta["built_at"] = "2026-08-14T00:00:00Z"
        MC.write_json(p, meta)
        mutant_pass = (a1 == a2 and m1 == EC.sha256_file(p)
                       and c1 == EC._meta_data_sha(p))
    finally:
        shutil.rmtree(s1, ignore_errors=True)
        shutil.rmtree(s2, ignore_errors=True)
    return check("ec05_two_run_byte_identity",
                 "EM05 wall-clock stamped into the cache meta", armed,
                 mutant_pass, "%s %d" % (asset, d8))


TESTS = (ec01_holdout_session_is_refused,
         ec02_universe_excludes_holdout,
         ec03_verifier_catches_a_holdout_artefact,
         ec04_window_matches_the_era_renderer,
         ec05_two_run_byte_identity)


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
    MC.write_tsv(os.path.join(OUT_DIR, "red_ledger_event_cache.tsv"), SECTION,
                 MC.params_hash(EC.PARAMS),
                 ["test", "mutant", "armed_pass", "mutant_pass", "verdict",
                  "detail"], LEDGER,
                 extra=["RED-FIRST: armed_pass MUST be 1 and mutant_pass MUST "
                        "be 0 on every row"])
    MC.write_json(os.path.join(OUT_DIR, "tests_event_cache.receipt.json"),
                  {"env": MC.env_receipt(EC.PARAMS), "n_tests": len(TESTS),
                   "n_failed": n_fail,
                   "verdict": "PASS" if n_fail == 0 else "FAIL"})
    MC.hb("event-cache tests: %d/%d passed" % (len(TESTS) - n_fail, len(TESTS)))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
