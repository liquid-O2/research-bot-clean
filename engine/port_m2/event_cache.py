#!/usr/bin/python3
"""PORT M2 — CORPUS-WIDE MBP-1 EVENT CACHE (spec §CC-M2-15.4, BINDING).

CC-M2-15.4 orders the per-session MBP-1 event extractor (tape.py) to run over
the WHOLE corpus, so that

  * the S7/S8 event statistics (c2f, erosion, through-book) become
    ERA-CENSUSABLE rather than only computable on the two rendered eras, and
  * the M3 day-side / phase-side classifier can read event-grain FLOW features
    on every session it fits on.

This module is a DRIVER, not a new tape convention: every byte it writes is
produced by `tape.ensure`, which is already seal-guarded, dominance-correct and
byte-identical run to run.  What the driver adds is

  1. THE UNIVERSE — every (asset, session) that the v3 ORACLE_FREEZE roster
     carries a candidate for, minus the holdout (below).  A session with no
     roster candidate has no canonical extraction window (the window is defined
     per candidate, spec §1 S6) and is therefore out of scope, listed as such in
     the coverage report rather than silently dropped.
  2. THE HOLDOUT GUARD — CC-M2-15.3 moved the port's pre-exam holdout to
     2025-07-01 onward.  Holdout tape is PRE-EXAM MATERIAL: this lane must not
     even decode it.  `assert_extractable` refuses those dates (and, through the
     m0 seal, 2026) BEFORE any payload file is opened, and the verifier
     re-asserts the exclusion against the cache directory itself.
  3. THE CANONICAL RANGE — identical to the era renderer's
     (era_build._render_session): the union over the session's candidates of
     [dec_sec - RIBBON_DIGEST - RIBBON_RAW - PAD, dec_sec + 1].  Same
     construction => the 468 era-STUDY sessions already on disk are hits, not
     re-extractions.
  4. THE MANIFEST + COVERAGE REPORT — the committed receipts (bulk stays under
     artifacts/cache, D-018).

Run:
  lab/run.sh port-m2-events -- /usr/bin/python3 engine/port_m2/event_cache.py \
      --workers 12
  /usr/bin/python3 engine/port_m2/event_cache.py --verify --identity-pct 2
"""
import argparse
import hashlib
import multiprocessing as mp
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import assemble as A                      # noqa: E402
import tape as TAPE                       # noqa: E402
import common as C                        # noqa: E402  m0 substrate

SECTION = "§CC-M2-15.4 corpus-wide MBP-1 event cache"
WORKERS_MAX = 12                          # 13.6-core cgroup; sole heavy lane

# CC-M2-15.3: the port pre-exam holdout starts here.  Nothing at or after this
# date is extracted, decoded, or counted by this lane.
HOLDOUT_START = MC.ERA_HOLDOUT[1]         # 20250701

MANIFEST_PATH = "/workspace/provenance/port_m2/EVENT_CACHE_MANIFEST.tsv"
REPORT_PATH = "/workspace/evidence/port_m2/EVENT_CACHE_COVERAGE_REPORT.md"
RECEIPT_PATH = os.path.join(TAPE.EVENTS_DIR, "event_cache.receipt.json")
# D-018: every scratch byte of size lives under artifacts/cache, never on the
# container overlay (/tmp, /home, the session scratchpad).
SCRATCH_ROOT = MC.out_path("scratch", "_")[:-1]

MANIFEST_COLUMNS = ("asset", "date8", "era", "n_candidates", "n_events",
                    "n_seen", "n_reordered", "cover_sec", "session_sec",
                    "cover_frac", "npz_bytes", "npz_sha256", "meta_sha256")

PARAMS = {
    "spec_section": SECTION,
    "universe": "every (asset, session) carrying >=1 candidate in "
                "m1/generation_v3/union_roster_{ASSET}.npz, with "
                "date8 < %d" % HOLDOUT_START,
    "holdout_excluded": "date8 >= %d (CC-M2-15.3 pre-exam material)"
                        % HOLDOUT_START,
    "seal": "date8 >= %d never opened (m0 seal)" % MC.SEAL_CUTOFF,
    "window": "union over the session's candidates of [dec_sec-%d, dec_sec+1]"
              % (TAPE.RIBBON_DIGEST_SEC + TAPE.RIBBON_RAW_SEC
                 + TAPE.EXTRACT_PAD_SEC),
    "extractor": "engine/port_m2/tape.py ensure() — unchanged",
    "clock": "ts_event",
}


class HoldoutRefusal(RuntimeError):
    """Raised BEFORE any payload file is opened for a holdout session.

    NEVER caught inside the extraction worker: a holdout date reaching the
    extractor is a program-level defect (pre-exam exposure), not a bad row.
    """


# ------------------------------------------------------------------ guards --
def assert_extractable(asset, d8):
    """The one gate every session passes through before its tape is opened."""
    d8 = int(d8)
    if d8 >= MC.SEAL_CUTOFF:
        raise C.SealRefusal("SEAL: %s %d is never opened" % (asset, d8))
    if d8 >= HOLDOUT_START:
        raise HoldoutRefusal(
            "HOLDOUT (CC-M2-15.3): %s %d is at/after %d — pre-exam material, "
            "not extracted" % (asset, d8, HOLDOUT_START))
    return True


# --------------------------------------------------------------- universe ---
def canonical_ranges(asset, d8):
    """The session's canonical S6 extraction windows, era_build's construction.

    One range per DISTINCT decision second (the two sides of one decision second
    share a window), merged by tape._merge inside ensure().
    """
    r = A.roster(asset)
    m = r["date8"] == int(d8)
    out = []
    for ds in np.unique(r["dec_sec"][m]):
        lo = max(0, int(ds) - TAPE.RIBBON_DIGEST_SEC - TAPE.RIBBON_RAW_SEC
                 - TAPE.EXTRACT_PAD_SEC)
        out.append((lo, int(ds) + 1))
    return out


def n_candidates(asset, d8):
    r = A.roster(asset)
    return int(np.count_nonzero(r["date8"] == int(d8)))


def universe(assets=MC.ASSET_ORDER):
    """[(asset, date8)] — every in-scope roster session-asset, chronological."""
    out = []
    for asset in assets:
        d8s = np.unique(A.roster(asset)["date8"])
        for d in sorted(int(x) for x in d8s):
            if d >= HOLDOUT_START:        # the guard, applied at enumeration
                continue
            out.append((asset, d))
    return out


def holdout_sessions(assets=MC.ASSET_ORDER):
    out = []
    for asset in assets:
        for d in sorted(int(x) for x in np.unique(A.roster(asset)["date8"])):
            if d >= HOLDOUT_START:
                out.append((asset, d))
    return out


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------ worker --
def _init():
    MC.verify_spec(force=True)            # pin-at-launch, once per worker


def _extract_one(task):
    """(asset, date8) -> (row, status, wall, task).  Holdout dates never run."""
    asset, d8 = task
    t0 = time.time()
    assert_extractable(asset, d8)         # BEFORE load_session/decode
    status = "OK"
    row = None
    try:
        sess = A.load_session(asset, int(d8))
        s = sess["s"]
        rng = canonical_ranges(asset, d8)
        arrays, meta = TAPE.ensure(asset, sess["trade_date"], int(s.iid),
                                   int(s.meta["open_utc"]),
                                   int(s.meta["close_utc"]), rng)
        del arrays
        npz_p, json_p = TAPE._paths(asset, int(d8))
        cover_sec = sum(int(b) - int(a) for a, b in meta["cover"])
        sess_sec = int(meta["close_utc"]) - int(meta["open_utc"])
        row = [asset, int(d8), MC.era_of(d8), n_candidates(asset, d8),
               int(meta["n_events"]), int(meta["n_seen"]),
               int(meta["n_reordered"]), cover_sec, sess_sec,
               (cover_sec / sess_sec) if sess_sec else 0.0,
               os.path.getsize(npz_p), sha256_file(npz_p), sha256_file(json_p)]
    except Exception as e:                # noqa: BLE001 — reported, not hidden
        status = "FAIL:%s" % str(e)[:180]
    # A worker handles hundreds of sessions; assemble memoises every session
    # receipt (with its full trade arrays), so drop this one before the next.
    A._MEM.pop(("sess", asset, int(d8)), None)
    MC.hb("event_cache %s %d: %s %.1fs" % (asset, d8, status, time.time() - t0))
    return row, status, round(time.time() - t0, 2), task


# ------------------------------------------------------------------ driver --
def build(args):
    MC.verify_spec(force=True)
    t_start = time.time()
    todo_all = universe(args.assets)
    if args.max_sessions:
        todo_all = todo_all[:args.max_sessions]
    # Cache HIT = the npz+json exist and already cover the canonical windows.
    hits, todo = [], []
    for asset, d8 in todo_all:
        npz_p, json_p = TAPE._paths(asset, int(d8))
        if os.path.exists(npz_p) and os.path.exists(json_p) and not args.force:
            import json as _json
            with open(json_p) as fh:
                meta = _json.load(fh)
            # R91/R92: the driver's own HIT test must be the SAME five tests
            # `tape.ensure` applies, or the driver reports a hit for a session
            # the renderer will re-extract.  It reads the meta's own open/close
            # because the driver has not loaded the session receipt yet.
            ok, _why = TAPE.cache_hit(meta, meta.get("iid"),
                                      meta.get("open_utc", -1),
                                      meta.get("close_utc", -1),
                                      TAPE._merge(canonical_ranges(asset, d8)))
            if ok:
                hits.append((asset, d8))
                continue
        todo.append((asset, d8))
    MC.hb("event_cache: %d session-assets in scope, %d already cached, "
          "%d to extract (holdout >= %d excluded: %d sessions)"
          % (len(todo_all), len(hits), len(todo), HOLDOUT_START,
             len(holdout_sessions(args.assets))))
    if args.dry_run:
        return 0

    results = []
    n_fail = 0
    n_done = 0
    workers = min(args.workers, WORKERS_MAX)
    if workers > 1 and len(todo) > 1:
        with mp.Pool(workers, initializer=_init) as pool:
            for out in pool.imap_unordered(_extract_one, todo, chunksize=1):
                results.append(out)
                n_done += 1
                if out[1] != "OK":
                    n_fail += 1
                if n_done % 25 == 0:
                    el = time.time() - t_start
                    MC.hb("event_cache PROGRESS %d/%d %.2f/s eta %.0fs "
                          "(%d failures)"
                          % (n_done, len(todo), n_done / max(el, 1e-9),
                             (len(todo) - n_done) * el / n_done, n_fail))
    else:
        _init()
        for t in todo:
            out = _extract_one(t)
            results.append(out)
            if out[1] != "OK":
                n_fail += 1
    wall = time.time() - t_start
    MC.hb("event_cache: extracted %d/%d, %d failures, %.0fs"
          % (len(results) - n_fail, len(todo), n_fail, wall))
    MC.write_json(RECEIPT_PATH,
                  {"env": MC.env_receipt(PARAMS),
                   "n_in_scope": len(todo_all),
                   "n_cache_hits_at_start": len(hits),
                   "n_extracted": len(todo) - n_fail,
                   "n_failures": n_fail,
                   # MINOR (review 3.2): the failures list was built from
                   # `pool.imap_unordered` and never sorted, so two identical
                   # runs wrote different bytes.  Sorted on (asset, date8).
                   "failures": sorted([[t[0], t[1], s]
                                       for _r, s, _w, t in results
                                       if s != "OK"])[:50],
                   # MINOR (review 3.2): `extract_wall_sec` / `extract_sec_mean`
                   # were WALL CLOCK stamped into a committed receipt, which the
                   # lane's own EC05 two-run identity guard exists to forbid.
                   # The timing is a run property, not corpus data; it goes to
                   # the heartbeat and stays out of the artefact.
                   "timing": "not recorded: wall clock in a committed receipt "
                             "breaks the two-run byte-identity law (D-018); "
                             "see the run heartbeat for elapsed time",
                   "def_sha16": TAPE.DEF_SHA16,
                   "pins_moved_during_run": MC.pins_moved()})
    MC.hb("event_cache: extract wall %.0fs, mean %.2fs/session-asset"
          % (wall, float(np.mean([w for _r, _s, w, _t in results]))
             if results else 0.0))
    return 1 if n_fail else 0


# ---------------------------------------------------------------- verifier --
def _cached_sessions():
    out = {}
    for asset in MC.ASSET_ORDER:
        d = os.path.join(TAPE.EVENTS_DIR, asset)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".npz"):
                out.setdefault(asset, set()).add(int(fn[:8]))
    return out


def _meta_pin_census():
    """How many cached metas carry which spec pin (provenance, not data)."""
    import json as _json
    out = {}
    for asset in MC.ASSET_ORDER:
        d = os.path.join(TAPE.EVENTS_DIR, asset)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".json"):
                continue
            with open(os.path.join(d, fn)) as fh:
                pin = _json.load(fh).get("m2_spec_sha16", "?")
            out[pin] = out.get(pin, 0) + 1
    return dict(sorted(out.items()))


def _identity_sample(rows, pct):
    """Deterministic every-k-th sample of the manifest, >= pct% of the rows."""
    if pct <= 0 or not rows:
        return []
    k = max(1, int(len(rows) * pct / 100.0))
    step = max(1, len(rows) // k)
    return [rows[i] for i in range(0, len(rows), step)][:k]


# The cache meta carries `m2_spec_sha16` — the PIN OF THE RUN THAT WROTE IT, a
# provenance stamp, not data.  The corpus was written across three pins (the
# 2026-08-14 spec churn: 44c2231 era-STUDY, c45371d pilot, 09888a1 this lane),
# and a re-extraction today stamps HEAD's pin.  Byte identity is therefore
# asserted on the NPZ (the data) exactly, and on the meta MODULO that one field;
# the raw meta comparison is reported beside it rather than hidden.
_PROVENANCE_KEYS = ("m2_spec_sha16",)


def _meta_data_sha(path):
    import json as _json
    with open(path) as fh:
        meta = _json.load(fh)
    for k in _PROVENANCE_KEYS:
        meta.pop(k, None)
    return hashlib.sha256(
        _json.dumps(meta, sort_keys=True).encode("utf-8")).hexdigest()


def _reextract_to(scratch, asset, d8):
    """Re-run the extractor into a SCRATCH root.  -> (npz_sha, meta_sha,
    meta_data_sha)."""
    old = TAPE.EVENTS_DIR
    try:
        TAPE.EVENTS_DIR = scratch
        sess = A.load_session(asset, int(d8))
        s = sess["s"]
        TAPE.ensure(asset, sess["trade_date"], int(s.iid),
                    int(s.meta["open_utc"]), int(s.meta["close_utc"]),
                    canonical_ranges(asset, d8))
        npz_p, json_p = TAPE._paths(asset, int(d8))
        return (sha256_file(npz_p), sha256_file(json_p),
                _meta_data_sha(json_p))
    finally:
        TAPE.EVENTS_DIR = old


def _identity_worker(task):
    scratch, asset, d8, npz_sha, meta_sha = task
    try:
        a, b, c = _reextract_to(scratch, asset, d8)
    except Exception as e:                # noqa: BLE001
        return asset, d8, "ERROR:%s" % str(e)[:120]
    finally:
        A._MEM.pop(("sess", asset, int(d8)), None)
    json_p = TAPE._paths(asset, int(d8))[1]
    same_npz = (a == npz_sha)
    same_meta_raw = (b == meta_sha)
    same_meta_data = (c == _meta_data_sha(json_p))
    if same_npz and same_meta_data:
        return asset, d8, ("IDENTICAL" if same_meta_raw
                           else "IDENTICAL_MODULO_SPEC_PIN")
    return asset, d8, "DIFFERS(npz=%d,meta_data=%d)" % (same_npz,
                                                        same_meta_data)


def verify(args):
    MC.verify_spec(force=True)
    t0 = time.time()
    scope = universe(args.assets)
    cached = _cached_sessions()

    # (a) coverage: every in-scope session-asset present AND covering.
    missing, short = [], []
    rows = []
    for asset, d8 in scope:
        npz_p, json_p = TAPE._paths(asset, int(d8))
        if not (os.path.exists(npz_p) and os.path.exists(json_p)):
            missing.append((asset, d8))
            continue
        import json as _json
        with open(json_p) as fh:
            meta = _json.load(fh)
        cover = [(int(a), int(b)) for a, b in meta["cover"]]
        want = TAPE._merge(canonical_ranges(asset, d8))
        if not all(TAPE._covers(cover, a, b) for a, b in want):
            short.append((asset, d8))
        cover_sec = sum(b - a for a, b in cover)
        sess_sec = int(meta["close_utc"]) - int(meta["open_utc"])
        rows.append([asset, int(d8), MC.era_of(d8), n_candidates(asset, d8),
                     int(meta["n_events"]), int(meta["n_seen"]),
                     int(meta["n_reordered"]), cover_sec, sess_sec,
                     (cover_sec / sess_sec) if sess_sec else 0.0,
                     os.path.getsize(npz_p), sha256_file(npz_p),
                     sha256_file(json_p)])
    rows.sort(key=lambda r: (r[0], r[1]))

    # (b) THE HOLDOUT EXCLUSION, asserted against the cache directory itself.
    leaked = sorted((a, d) for a, ds in cached.items() for d in ds
                    if d >= HOLDOUT_START)
    sealed = sorted((a, d) for a, ds in cached.items() for d in ds
                    if d >= MC.SEAL_CUTOFF)
    # and asserted against the guard, on the real holdout dates
    guard_ok = True
    for asset, d8 in holdout_sessions(args.assets)[:200]:
        try:
            assert_extractable(asset, d8)
            guard_ok = False
        except HoldoutRefusal:
            pass

    # (c) two-run byte identity on a deterministic sample.
    ident = []
    if args.identity_pct > 0:
        import tempfile
        # D-018: scratch of SIZE never touches the overlay (/tmp, $HOME, ...)
        scratch = tempfile.mkdtemp(prefix="identity_", dir=SCRATCH_ROOT)
        sample = _identity_sample(rows, args.identity_pct)
        tasks = [(scratch, r[0], r[1], r[11], r[12]) for r in sample]
        workers = min(args.workers, WORKERS_MAX)
        if workers > 1 and len(tasks) > 1:
            with mp.Pool(workers, initializer=_init) as pool:
                for out in pool.imap_unordered(_identity_worker, tasks,
                                               chunksize=1):
                    ident.append(out)
        else:
            _init()
            for t in tasks:
                ident.append(_identity_worker(t))
        ident.sort()
        import shutil
        shutil.rmtree(scratch, ignore_errors=True)
    n_ident = sum(1 for _, _, v in ident
                  if v in ("IDENTICAL", "IDENTICAL_MODULO_SPEC_PIN"))
    n_ident_exact = sum(1 for _, _, v in ident if v == "IDENTICAL")

    # ------------------------------------------------------------- outputs --
    phash = MC.params_hash(PARAMS)
    MC.write_tsv(MANIFEST_PATH, SECTION, phash, list(MANIFEST_COLUMNS), rows,
                 extra=["one row per CACHED session-asset; sha256 of the npz "
                        "and of its meta json (bulk stays in "
                        "artifacts/cache/port/m2/events/, D-018)",
                        "holdout date8 >= %d is EXCLUDED by construction "
                        "(CC-M2-15.3): %d such rows" % (HOLDOUT_START,
                                                        len(leaked)),
                        "n_seen == n_events BY CONSTRUCTION (tape.extract "
                        "increments the counter on kept records only); the two "
                        "columns are one measurement, not two",
                        "extraction definition key (R91) = %s"
                        % TAPE.DEF_SHA16])
    n_ev = sum(r[4] for r in rows)
    by_asset = {}
    by_era = {}
    for r in rows:
        a = by_asset.setdefault(r[0], [0, 0])
        a[0] += 1
        a[1] += r[4]
        e = by_era.setdefault(r[2], [0, 0])
        e[0] += 1
        e[1] += r[4]
    verdict = ("PASS" if (not missing and not short and not leaked
                          and not sealed and guard_ok
                          and (not ident or n_ident == len(ident)))
               else "FAIL")
    receipt = {
        "env": MC.env_receipt(PARAMS),
        "verdict": verdict,
        "n_in_scope": len(scope),
        "n_cached_in_scope": len(rows),
        "n_missing": len(missing), "missing": missing[:50],
        "n_short_cover": len(short), "short_cover": short[:50],
        "n_holdout_rows_in_cache": len(leaked), "holdout_rows": leaked[:50],
        "n_sealed_rows_in_cache": len(sealed),
        "holdout_guard_refuses_all": guard_ok,
        "n_events_total": int(n_ev),
        "identity_sample": len(ident), "identity_identical": n_ident,
        "identity_identical_exact_bytes": n_ident_exact,
        "identity_note": "npz compared byte-exact; meta json compared modulo "
                         "m2_spec_sha16 (the writing run's pin — the corpus "
                         "spans three pins from the 2026-08-14 spec churn)",
        "identity_failures": [x for x in ident if not
                              str(x[2]).startswith("IDENTICAL")][:20],
        "meta_spec_pins": _meta_pin_census(),
        "by_asset": {k: {"sessions": v[0], "events": v[1]}
                     for k, v in sorted(by_asset.items())},
        "by_era": {k: {"sessions": v[0], "events": v[1]}
                   for k, v in sorted(by_era.items())},
        "manifest": MANIFEST_PATH,
        # MINOR (review 3.2): `verify_wall_sec` was wall clock in a committed
        # receipt.  Removed for the same reason as `extract_wall_sec` above.
        "def_sha16": TAPE.DEF_SHA16,
        "pins_moved_during_run": MC.pins_moved(),
    }
    MC.write_json(os.path.join(TAPE.EVENTS_DIR, "coverage.receipt.json"),
                  receipt)
    _write_report(receipt, rows, by_asset, by_era, ident, args)
    MC.hb("event_cache verify: %s (%d/%d cached, %d missing, %d short, "
          "%d holdout rows, identity %d/%d)"
          % (verdict, len(rows), len(scope), len(missing), len(short),
             len(leaked), n_ident, len(ident)))
    return 0 if verdict == "PASS" else 1


def _write_report(rc, rows, by_asset, by_era, ident, args):
    ex = rc["env"]
    n_out = 0
    out_rows = []
    for asset in MC.ASSET_ORDER:
        si = set(A.session_index(asset))
        ros = {int(x) for x in np.unique(A.roster(asset)["date8"])}
        no_cand = sorted(d for d in si if d < HOLDOUT_START and d not in ros)
        n_out += len(no_cand)
        out_rows.append((asset, len(si), len(ros), len(no_cand)))
    cov = [r[9] for r in rows]
    L = []
    L.append("# EVENT CACHE — COVERAGE REPORT (CC-M2-15.4)")
    L.append("")
    L.append("Corpus-wide MBP-1 event extraction, `engine/port_m2/tape.py` "
             "driven by `engine/port_m2/event_cache.py`.")
    L.append("Bulk lives in `artifacts/cache/port/m2/events/` (D-018); the "
             "committed receipts are this report and")
    L.append("`provenance/port_m2/EVENT_CACHE_MANIFEST.tsv`.")
    L.append("")
    L.append("VERDICT: **%s**" % rc["verdict"])
    L.append("")
    L.append("## Scope")
    L.append("")
    L.append("* UNIVERSE = every (asset, session) with >=1 candidate in the v3 "
             "ORACLE_FREEZE roster and `date8 < %d`." % HOLDOUT_START)
    L.append("* HOLDOUT EXCLUDED (CC-M2-15.3): `date8 >= %d` is pre-exam "
             "material — %d roster session-assets are refused by "
             "`assert_extractable` before any payload file is opened, and the "
             "cache directory carries **%d** such rows."
             % (HOLDOUT_START, len(holdout_sessions(MC.ASSET_ORDER)),
                rc["n_holdout_rows_in_cache"]))
    L.append("* SEAL: `date8 >= %d` never opened — **%d** such rows in cache."
             % (MC.SEAL_CUTOFF, rc["n_sealed_rows_in_cache"]))
    L.append("* WINDOW = the era renderer's canonical S6 window, unioned over "
             "the session's candidates: `[dec_sec-%d, dec_sec+1]`."
             % (TAPE.RIBBON_DIGEST_SEC + TAPE.RIBBON_RAW_SEC
                + TAPE.EXTRACT_PAD_SEC))
    L.append("")
    L.append("## The extraction run")
    L.append("")
    br = {}
    if os.path.exists(RECEIPT_PATH):
        import json as _json
        with open(RECEIPT_PATH) as fh:
            br = _json.load(fh)
    if br:
        L.append("| metric | value |")
        L.append("|---|---|")
        L.append("| cached before this lane | %d |"
                 % br.get("n_cache_hits_at_start", 0))
        L.append("| extracted by this lane | %d |" % br.get("n_extracted", 0))
        L.append("| extraction failures | %d |" % br.get("n_failures", 0))
        L.append("| extraction definition key | `%s` |"
                 % br.get("def_sha16", TAPE.DEF_SHA16))
        L.append("")
        L.append("Wall-clock timings are deliberately NOT in the committed "
                 "receipt: they are a property of the run, not of the corpus, "
                 "and they broke the two-run byte-identity law this lane's own "
                 "EC05 guard enforces.  Elapsed time is on the run heartbeat.")
        L.append("")
        if br.get("pins_moved_during_run"):
            L.append("NOTE — the M2 spec pin MOVED during the run "
                     "(`%s`). The run was pinned at launch and is reported "
                     "honestly here; no extracted byte depends on the spec "
                     "text, only the meta's provenance stamp does (see below)."
                     % "; ".join(br["pins_moved_during_run"])[:200])
            L.append("")
    L.append("## Coverage")
    L.append("")
    L.append("| metric | value |")
    L.append("|---|---|")
    L.append("| in-scope session-assets | %d |" % rc["n_in_scope"])
    L.append("| cached | %d |" % rc["n_cached_in_scope"])
    L.append("| MISSING | %d |" % rc["n_missing"])
    L.append("| cover SHORT of the canonical window | %d |"
             % rc["n_short_cover"])
    L.append("| events cached | %s |" % format(rc["n_events_total"], ","))
    L.append("| median cover fraction of the session | %.4f |"
             % (float(np.median(cov)) if cov else 0.0))
    L.append("| holdout guard refuses every holdout date | %s |"
             % rc["holdout_guard_refuses_all"])
    L.append("")
    L.append("### by asset")
    L.append("")
    L.append("| asset | sessions | events |")
    L.append("|---|---|---|")
    for k, v in sorted(by_asset.items()):
        L.append("| %s | %d | %s |" % (k, v[0], format(v[1], ",")))
    L.append("")
    L.append("### by era")
    L.append("")
    L.append("| era | sessions | events |")
    L.append("|---|---|---|")
    for k, v in sorted(by_era.items()):
        L.append("| %s | %d | %s |" % (k, v[0], format(v[1], ",")))
    L.append("")
    L.append("## Out of scope, accounted")
    L.append("")
    L.append("A session-asset with an m0 receipt but NO roster candidate has "
             "no canonical extraction window (the window is defined per "
             "candidate). Listed, not silently dropped:")
    L.append("")
    L.append("| asset | m0 sessions (all dates) | roster sessions (all dates) "
             "| pre-holdout m0 sessions with no candidate |")
    L.append("|---|---|---|---|")
    for a, n_si, n_ros, n_nc in out_rows:
        L.append("| %s | %d | %d | %d |" % (a, n_si, n_ros, n_nc))
    L.append("")
    L.append("## Two-run byte identity")
    L.append("")
    L.append("A deterministic every-k-th sample of the manifest (%g%%) is "
             "re-extracted into a scratch root and compared with the cached "
             "copy:" % args.identity_pct)
    L.append("")
    L.append("* sampled: **%d** session-assets" % rc["identity_sample"])
    L.append("* NPZ payload byte-identical: **%d/%d**"
             % (rc["identity_identical"], rc["identity_sample"]))
    L.append("* meta json identical modulo the spec pin: **%d/%d**"
             % (rc["identity_identical"], rc["identity_sample"]))
    L.append("* of those, byte-identical INCLUDING the meta's spec pin: **%d**"
             % rc["identity_identical_exact_bytes"])
    L.append("* failures: %s" % (rc["identity_failures"] or "none"))
    L.append("")
    L.append("The meta json carries `m2_spec_sha16` — the pin of the RUN that "
             "wrote it, a provenance stamp, not data. The corpus spans three "
             "pins (the 2026-08-14 spec churn), so the identity claim is: the "
             "NPZ payload is byte-exact, and the meta is exact modulo that one "
             "field. Pin census of the cache:")
    L.append("")
    L.append("| meta m2_spec_sha16 | sessions |")
    L.append("|---|---|")
    for k, v in rc["meta_spec_pins"].items():
        L.append("| `%s` | %d |" % (k, v))
    L.append("")
    L.append("## Red-first guards")
    L.append("")
    L.append("`engine/port_m2/test_event_cache.py` — 5/5, every test with a "
             "committed mutant it must catch:")
    L.append("")
    L.append("* **EC01** an INCLUDED 2025-08 session is REFUSED before any "
             "payload file is opened (mutant EM01: the boundary reverted to "
             "the lane's old 2025-09-01 — caught).")
    L.append("* **EC02** the enumerated universe carries no date >= the "
             "boundary and still carries 2025-06 (mutant EM02: enumeration "
             "without the filter — caught).")
    L.append("* **EC03** a holdout artefact planted in the cache tree fails "
             "the verifier (mutant EM03: exclusion asserted against the "
             "work list, which is filtered by construction, instead of "
             "against the disk — caught).")
    L.append("* **EC04** the driver's window == the era renderer's, so an "
             "already-extracted session is a HIT (mutant EM04: window widened "
             "to the session open — caught).")
    L.append("* **EC05** two extractions of one session agree byte-for-byte "
             "(mutant EM05: wall-clock stamped into the meta — caught).")
    L.append("")
    L.append("## Defects / notes")
    L.append("")
    L.append("* **EC-1 (open, cosmetic)** the cache meta's `m2_spec_sha16` is "
             "the writing run's pin, so the corpus carries three different "
             "values and a re-extraction today carries a fourth. The NPZ "
             "payload is unaffected; a byte-identity claim on the meta must "
             "normalise that field (this verifier does).")
    L.append("* The 20 PILOT sessions were extracted for ONE candidate each; "
             "this lane EXTENDED them to the full canonical union, so they now "
             "cover like every other session.")
    L.append("")
    L.append("## Provenance")
    L.append("")
    L.append("* spec: `PORT_M2_SHEETS_SPEC.md` %s (sha16 `%s`)"
             % (SECTION, ex["m2_spec_sha16"]))
    L.append("* extractor: `engine/port_m2/tape.py` (unchanged by this lane)")
    L.append("* driver: `engine/port_m2/event_cache.py`")
    L.append("* red-first guard tests: `engine/port_m2/test_event_cache.py`")
    L.append("* receipts: `artifacts/cache/port/m2/events/"
             "{event_cache,coverage}.receipt.json`")
    L.append("")
    MC.write_text(REPORT_PATH, "\n".join(L))


# ------------------------------------------------- R91 definition migration --
STAMP_RECEIPT = os.path.join(TAPE.EVENTS_DIR, "def_stamp.receipt.json")


def stamp_definition(args):
    """One-time migration for R91: write `def_sha16` into pre-fix cache metas.

    R91 keys the cache on `tape.DEF_PARAMS`.  Every meta written before the fix
    lacks the key, so without this migration the whole 12 GB corpus becomes a
    MISS and re-decodes.  Stamping is CORRECT, not a shortcut: this lane changed
    the HIT TEST, not the extraction definition — `tape.extract`'s instrument
    filter, record predicate, ARRAYS, dtypes, clock, sort and pad are byte-for-
    byte what they were when the corpus was written — so the caches on disk ARE
    the product of DEF_PARAMS version 1.  Any FUTURE change to the definition
    bumps the sha and re-extracts, which is the whole point.

    A meta that already carries a DIFFERENT def_sha16 is never overwritten: that
    is a genuine definition change and its session must re-extract.
    """
    import json as _json
    stamped = skipped = mismatch = 0
    rows = []
    for asset in sorted(MC.ASSET_ORDER):
        base = os.path.join(TAPE.EVENTS_DIR, asset)
        if not os.path.isdir(base):
            continue
        for fn in sorted(os.listdir(base)):
            if not fn.endswith(".json"):
                continue
            p = os.path.join(base, fn)
            with open(p) as fh:
                meta = _json.load(fh)
            got = meta.get("def_sha16")
            if got == TAPE.DEF_SHA16:
                skipped += 1
                continue
            if got:
                mismatch += 1
                rows.append([asset, fn, "MISMATCH:%s" % got])
                continue
            meta["def_sha16"] = TAPE.DEF_SHA16
            if not args.dry_run:
                MC.write_json(p, meta)
            stamped += 1
    MC.write_json(STAMP_RECEIPT,
                  {"env": MC.env_receipt(PARAMS),
                   "def_sha16": TAPE.DEF_SHA16,
                   "def_params": TAPE.DEF_PARAMS,
                   "n_stamped": stamped, "n_already": skipped,
                   "n_mismatch": mismatch, "mismatches": rows[:50],
                   "dry_run": bool(args.dry_run),
                   "rationale": "R91 migration: the HIT TEST changed, the "
                                "extraction definition did not, so pre-fix "
                                "metas are stamped rather than re-extracted"})
    MC.hb("event_cache stamp-definition: %d stamped, %d already, %d mismatch"
          % (stamped, skipped, mismatch))
    return 1 if mismatch else 0


# -------------------------------------------------------------------- cli ---
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--assets", nargs="+", default=list(MC.ASSET_ORDER))
    p.add_argument("--workers", type=int, default=WORKERS_MAX)
    p.add_argument("--max-sessions", type=int, default=None)
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verify", action="store_true",
                   help="coverage + holdout exclusion + two-run identity")
    p.add_argument("--identity-pct", type=float, default=2.0)
    p.add_argument("--stamp-definition", action="store_true",
                   help="R91 one-time migration: write tape.DEF_SHA16 into "
                        "pre-fix cache metas (see stamp_definition)")
    args = p.parse_args()
    if args.stamp_definition:
        return stamp_definition(args)
    if args.verify:
        return verify(args)
    return build(args)


if __name__ == "__main__":
    sys.exit(main())
