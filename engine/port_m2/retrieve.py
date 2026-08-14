#!/usr/bin/python3
"""PORT M2 — the REFERENCE-CLASS RETRIEVAL TOOL (spec §CC-M2-5 item 3).

    "(3) REFERENCE-CLASS RETRIEVAL TOOL (build item): k-nearest already-studied
     cases by feature/skeleton distance, strictly study-tainted history only,
     surfaced with outcomes at decision time — lawful analog memory."

WHAT MAKES IT LAWFUL
  The pool is EXACTLY the STUDY rows of the D-035.2 used-case ledger
  (provenance/port_m2/USED_CASE_LEDGER.tsv): cases whose S14 outcomes the
  reader has ALREADY been shown.  Surfacing their outcomes again leaks nothing
  it does not already know.  Any other pool would be an outcome channel into a
  blind decision, so the pool builder REFUSES — it never filters:

    * a pool member the ledger does not carry as a
      STUDY row                                     -> RETRIEVAL REFUSED
    * a pool member whose (asset, date8) is not in
      used_cases.tainted_sessions()                 -> RETRIEVAL REFUSED
    * an empty pool                                 -> RETRIEVAL REFUSED

  The guard reads the LEDGER, never the pool it is validating: a taint set
  derived from the pool would certify its own poison.

  SEQUENCING CAVEAT (operational, not enforceable from the ledger): a STUDY row
  means "this case belongs to a study block", and the block's outcomes are
  revealed at ITS unblinding.  A round may register its STUDY rows BEFORE the
  S14 appendices are opened (E1-STUDY-D1 did exactly that — 1,039 rows
  registered with the theses sealed and no S14 read).  Until that round
  unblinds, retrieval must not be consulted for a case still inside it: the
  ledger cannot distinguish the two states, so the sequencing is the round
  driver's responsibility, and this note is the record of the hazard.

  A filtering guard would turn a protocol violation into a silent subsample,
  which is the exact mistake used_cases.check_blind exists to prevent.  The
  red-first mutant (test_pattern.t05) injects an untainted case and fails if it
  is not caught.

  --exclude-date8 (D11, CC-M2-10.6) puts the sequencing caveat above IN THE
  TOOL.  E1-STUDY-D2 consulted retrieval through a `scratch`-local wrapper that
  removed every 2021-07-02 row by hand; the honest form is a flag.  ORDER OF
  OPERATIONS IS THE WHOLE POINT: the taint guard runs FIRST on the unexcluded
  pool and REFUSES, and only the surviving lawful pool is then narrowed by the
  exclusion.  Excluding first would let a caller launder an untainted case past
  the guard by naming its date, i.e. turn D11 into a hole in D-035.2.  The
  red-first mutant (test_pattern.t12) ignores the flag and must be caught.

THE DISTANCE (pinned; every field comes from the committed receipts through
pattern_lib.frame, so retrieval and the censuses read ONE definition)

  block  field                     type          distance
  ----------------------------------------------------------------------------
  B01    class (D-071)             categorical   0 if equal else 1
  B02    phase (TOKYO/LONDON/NY)   categorical   0 if equal else 1
  B03    clock-of-day sin/cos      circular      chord(a,b) / 2  in [0,1]
  B04    COVERAGE_phase            numeric       scaled |a-b|
  B05    runway_frac               numeric       scaled |a-b|
  B06    ladder_position band      ordinal       scaled |a-b|
  B07    vol-regime tercile        ordinal       scaled |a-b|
  B08    spread state (x median)   numeric       scaled |a-b|
  B09    nearest kept level (ATR)  numeric       scaled |a-b|
  B10    RV ratio rv1800/rv60      numeric       scaled |a-b|
  B11    generation family tags    multi-hot     Jaccard distance

  SCALING (the "normalized feature distance"): each numeric/ordinal block is
  divided by its own robust scale s_f = max(1.4826 * MAD, floor_f) computed
  over the REFERENCE SET = the pool values plus the query's, then clipped at
  DIST_CAP scaled units and divided by DIST_CAP, so every block lands in [0,1]
  on the same footing as the categorical ones.  floor_f = max(ABS_FLOOR,
  REL_FLOOR * |median|) keeps a degenerate (all-equal) field from exploding.

  WEIGHTS are UNIFORM after that scaling — the spec's own words.  A block whose
  value is missing/REFUSED on either side is DROPPED from both the sum and the
  count (never imputed, never silently zeroed); the surviving block count is
  printed as `nb`, so a match on 7 blocks is never mistaken for a match on 11.
  This is Gower's coefficient with its standard missing-value rule, and it
  carries Gower's known bias: a neighbour with several REFUSED fields is scored
  on fewer, easier blocks and can rank artificially close.  Two things hold
  that honest — `nb` is a printed column, and a case comparable on fewer than
  MIN_BLOCKS blocks is dropped from the ranking and reported as a count.

  TIES are deterministic: the sort key is (distance rounded to 1e-9, cid).

  SIDE is deliberately NOT a block (the pinned vector is the spec's list), so a
  SHORT query can retrieve LONG analogs; `--same-side` filters the POOL for
  callers who want same-direction references, which changes what is compared,
  never how.

OUTCOMES surfaced per neighbour: BOTH CC-M1-8 readings (walled phase-close =
the adoption metric, walled peak-exit = the mandatory companion), the wall flag
and the D-021 winner flag.

CLI
  /usr/bin/python3 engine/port_m2/retrieve.py <cid> -k 8
  /usr/bin/python3 engine/port_m2/retrieve.py <cid> -k 8 --json
"""
import argparse
import json
import math
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import pattern_lib as PL                  # noqa: E402
import used_cases as UC                   # noqa: E402
import census_common as X                 # noqa: E402

SECTION = "§CC-M2-5 item 3 — reference-class retrieval"

DIST_CAP = 4.0                            # robust-scaled units, then / DIST_CAP
ABS_FLOOR = 1e-6
REL_FLOOR = 0.01                          # of |median|
MIN_BLOCKS = 6                            # of 11; below this the case is dropped

# (block id, field in the pattern_lib frame, kind)
BLOCKS = (
    ("B01_class", "klass", "cat"),
    ("B02_phase", "phase_dec", "cat"),
    ("B03_clock", "clock_sec", "clock"),
    ("B04_coverage", "coverage_phase", "num"),
    ("B05_runway_frac", "runway_frac", "num"),
    ("B06_ladder", "ladder_band", "ord"),
    ("B07_vol_regime", "regime_tercile", "ord"),
    ("B08_spread", "spread_ratio", "num"),
    ("B09_level_dist", "level_dist_atr", "num"),
    ("B10_rv_ratio", "rv_ratio", "num"),
    ("B11_family_tags", "fam_mask", "bits"),
)

PARAMS = {
    "spec_section": SECTION,
    "pool": "STUDY rows of provenance/port_m2/USED_CASE_LEDGER.tsv by "
            "default; ANY explicit pool is validated against the ledger. "
            "REFUSAL (never a filter) on a member the ledger does not carry "
            "as STUDY, on an untainted session, or on an empty pool",
    "blocks": [b[0] + ":" + b[1] + ":" + b[2] for b in BLOCKS],
    "scaling": "per-field robust scale 1.4826*MAD over pool+query, floored at "
               "max(%g, %g*|median|); |a-b|/scale clipped at %g and divided by "
               "%g" % (ABS_FLOOR, REL_FLOOR, DIST_CAP, DIST_CAP),
    "weights": "UNIFORM over the blocks that are comparable on both sides",
    "missing": "a block missing/REFUSED on either side is dropped from the "
               "numerator AND the denominator; the count is reported as nb",
    "ties": "sort key (round(distance, 9), cid) — total and deterministic",
    "min_blocks": "a neighbour comparable on < %d blocks is dropped from the "
                  "ranking (Gower missing-block bias) and counted" % MIN_BLOCKS,
    "outcomes": "both CC-M1-8 readings (walled phase-close + walled peak-exit)",
    "exclude_date8": "D11 — an optional set of session dates removed from the "
                     "pool AFTER the taint guard has passed on the full pool; "
                     "the exclusion narrows a lawful pool and can never widen "
                     "one",
    "frame": PL.PARAMS_FRAME,
}


class PoolRefusal(RuntimeError):
    """Raised when the retrieval pool is not strictly study-tainted history."""


# ------------------------------------------------------------------ pool ----
def assert_study_tainted(cids, entries=None, _mutant_filter=False):
    """REFUSE any pool member that is not study-tainted history.

    The check is against the LEDGER, not against the pool itself: a member is
    lawful only if the ledger carries it as a STUDY row AND its (asset, date8)
    is STUDY-tainted there.  Deriving the taint set from the candidate pool
    would make the guard vacuous — a poisoned pool would declare its own
    poison tainted (caught by test_pattern.t05's first arming failure, kept on
    record here so the shape is not lost again).

    `_mutant_filter` is the RED-FIRST mutant switch: it turns the refusal into
    a filter, which the test must catch.  Production callers never pass it.
    """
    entries = UC.read_ledger() if entries is None else entries
    study = {e["cid"] for e in entries if e.get("mode") == UC.MODE_STUDY}
    tainted = UC.tainted_sessions(entries)
    bad, out = [], []
    for cid in cids:
        asset, d8, _s, _sd = MC.parse_cid(cid)
        if cid not in study or (asset, d8) not in tainted:
            bad.append(cid)
            continue
        out.append(cid)
    if bad and not _mutant_filter:
        raise PoolRefusal(
            "retrieval pool is not study-tainted history: %d case(s) the "
            "used-case ledger does not carry as STUDY: %s"
            % (len(bad), ", ".join(sorted(bad)[:5])
               + (" ..." if len(bad) > 5 else "")))
    if not out:
        raise PoolRefusal("retrieval pool is empty — there is no study-tainted "
                          "history to retrieve from")
    return sorted(set(out))


def pool_cids(entries=None, pool=None, _mutant_filter=False):
    """The lawful retrieval pool.

    Default = every STUDY case in the used-case ledger.  An explicit `pool`
    (any candidate list a caller wants to retrieve from) goes through the same
    guard, which is where an untainted case is caught.
    """
    entries = UC.read_ledger() if entries is None else entries
    if pool is None:
        pool = [e["cid"] for e in entries if e.get("mode") == UC.MODE_STUDY]
    return assert_study_tainted(pool, entries, _mutant_filter=_mutant_filter)


# ---------------------------------------------------------------- vectors ---
_FRAMES = {}

# The record fields the pool cache stores (block inputs + the surfaced state).
REC_FIELDS = ("klass", "phase_dec", "clock_sec", "coverage_phase",
              "runway_frac", "ladder_band", "regime_tercile", "spread_ratio",
              "level_dist_atr", "rv_ratio", "fam_mask", "side",
              "runway_phase_sec", "extreme_age_sec", "pivot_age_sec",
              "slope_1m_usd", "accel_usd", "cert_close_usd", "cert_peak_usd",
              "walled", "winner")

POOL_CACHE = MC.out_path("retrieval", "pool_index.npz")
_POOL_MEM = {}


def _frame(asset, d8, with_certs=True):
    key = (asset, int(d8), bool(with_certs))
    if key not in _FRAMES:
        _FRAMES[key] = PL.frame(asset, int(d8), with_levels=True,
                                with_certs=with_certs)
    return _FRAMES[key]


def vector(cid, with_certs=True):
    """The pinned feature record for one candidate (plus its outcomes)."""
    asset, d8, sec, side = MC.parse_cid(cid)
    f = _frame(asset, d8, with_certs=with_certs)
    if f is None:
        raise RuntimeError("no roster candidates for %s %d" % (asset, d8))
    m = np.nonzero(f["cid"] == cid)[0]
    if not m.size:
        raise RuntimeError("candidate %s is not in the v3 roster" % cid)
    t = int(m[0])
    rec = {"cid": cid, "asset": asset, "d8": d8}
    for k in REC_FIELDS:
        rec[k] = f[k][t]
    rec["phase"] = X.PHASE_NAMES[int(f["phase_dec"][t])]
    return rec


# ------------------------------------------------------------- pool cache ---
def _pool_hash(cids):
    """Cache key = the pool identity AND the code that computes its features.

    Hashing only the cid list would leave the cache stale after an edit to
    pattern_lib.frame or to this module's block table, which is exactly the
    kind of silent drift D-006 exists to prevent.
    """
    import hashlib
    h = hashlib.sha256()
    h.update("\n".join(cids).encode())
    for src in (PL.__file__, __file__):
        h.update(MC.C.sha256_file(src.replace(".pyc", ".py")).encode())
    return h.hexdigest()


def pool_records(entries=None, pool=None, refresh=False,
                 _mutant_filter=False):
    """Feature records for the whole study-tainted pool.

    The pool is now era-corpus sized (the E1 STUDY day-1 block alone recorded
    ~1,030 cases), and rebuilding it from receipts costs seconds, so it is
    cached under artifacts/cache/port/m2/retrieval/ (D-018) KEYED BY THE SHA256
    OF THE POOL CID LIST: the ledger growing by one case invalidates the cache
    automatically, and nothing else can make it stale (every input field is a
    pure function of frozen receipts).
    """
    cids = [c for c in pool_cids(entries, pool=pool,
                                 _mutant_filter=_mutant_filter)]
    h = _pool_hash(cids)
    if h in _POOL_MEM and not refresh:
        return _POOL_MEM[h]
    if not refresh and os.path.exists(POOL_CACHE):
        try:
            z = np.load(POOL_CACHE, allow_pickle=False)
            if str(z["pool_sha256"]) == h:
                # materialise every member ONCE: NpzFile decompresses on each
                # __getitem__, so indexing inside the row loop would decompress
                # 21 arrays per row (measured: 4.8s for 1,054 rows).
                cols = {k: z[k] for k in
                        (("cid", "asset", "d8", "phase") + REC_FIELDS)}
                z.close()
                recs = [dict([("cid", str(cols["cid"][t])),
                              ("asset", str(cols["asset"][t])),
                              ("d8", int(cols["d8"][t])),
                              ("phase", str(cols["phase"][t]))]
                             + [(k, cols[k][t]) for k in REC_FIELDS])
                        for t in range(int(cols["cid"].size))]
                _POOL_MEM[h] = recs
                return recs
            z.close()
        except (OSError, KeyError, ValueError):
            pass
    recs = [vector(c) for c in cids]
    payload = {"pool_sha256": np.array(h),
               "cid": np.array([r["cid"] for r in recs]),
               "asset": np.array([r["asset"] for r in recs]),
               "d8": np.array([r["d8"] for r in recs], dtype=np.int64),
               "phase": np.array([r["phase"] for r in recs])}
    for k in REC_FIELDS:
        payload[k] = np.array([r[k] for r in recs])
    os.makedirs(os.path.dirname(POOL_CACHE), exist_ok=True)
    tmp = POOL_CACHE + ".tmp"
    with open(tmp, "wb") as fh:            # a file object keeps the exact name
        np.savez(fh, **payload)            # (np.savez appends .npz to a path)
    os.replace(tmp, POOL_CACHE)
    MC.write_json(MC.out_path("retrieval", "pool_index.receipt.json"),
                  {"env": MC.env_receipt(PARAMS), "pool_sha256": h,
                   "n_pool": len(recs),
                   "ledger": UC.LEDGER, "cache": POOL_CACHE})
    _POOL_MEM[h] = recs
    return recs


def _finite(v):
    try:
        return bool(np.isfinite(float(v)))
    except (TypeError, ValueError):
        return False


def _present(field, kind, v):
    if kind == "cat":
        return str(v) not in ("", "UNCLASSED")
    if kind == "bits":
        return True
    if kind == "ord":
        return int(v) >= 0                 # -1 = REFUSED / missing
    return _finite(v)


def scales(records, _mutant_unscaled=False):
    """Per-field robust scale over the reference set (pool + query).

    `_mutant_unscaled` is the RED-FIRST mutant switch (test_pattern.t06):
    every scale becomes 1.0, i.e. raw units, so dollars-per-minute and
    ATR-fractions compete on their own magnitudes.  Production never sets it.
    """
    out = {}
    for _bid, field, kind in BLOCKS:
        if kind not in ("num", "ord"):
            continue
        if _mutant_unscaled:
            out[field] = 1.0
            continue
        vals = np.array([float(r[field]) for r in records
                         if _present(field, kind, r[field])], dtype=np.float64)
        if vals.size < 2:
            out[field] = 1.0
            continue
        med = float(np.median(vals))
        mad = float(np.median(np.abs(vals - med)))
        out[field] = max(1.4826 * mad, ABS_FLOOR, REL_FLOOR * abs(med))
    return out


def _bit_jaccard(a, b):
    a, b = int(a), int(b)
    inter = bin(a & b).count("1")
    union = bin(a | b).count("1")
    return 0.0 if union == 0 else 1.0 - float(inter) / union


def distance(q, c, sc):
    """(distance in [0,1], n_comparable_blocks, per-block contributions)."""
    tot = 0.0
    n = 0
    per = {}
    for bid, field, kind in BLOCKS:
        qv, cv = q[field], c[field]
        if not (_present(field, kind, qv) and _present(field, kind, cv)):
            continue
        if kind == "cat":
            d = 0.0 if str(qv) == str(cv) else 1.0
        elif kind == "bits":
            d = _bit_jaccard(qv, cv)
        elif kind == "clock":
            aa = 2.0 * math.pi * (float(qv) % 86400) / 86400.0
            bb = 2.0 * math.pi * (float(cv) % 86400) / 86400.0
            d = math.hypot(math.sin(aa) - math.sin(bb),
                           math.cos(aa) - math.cos(bb)) / 2.0
        else:
            s = sc.get(field, 1.0)
            d = min(abs(float(qv) - float(cv)) / (s if s > 0 else 1.0),
                    DIST_CAP) / DIST_CAP
        per[bid] = d
        tot += d
        n += 1
    return (tot / n if n else float("nan")), n, per


def parse_exclude_date8(spec):
    """`--exclude-date8 20210702,20210705` -> a set of int date8s."""
    out = set()
    for tok in (spec or "").replace(" ", "").split(","):
        if not tok:
            continue
        if not (tok.isdigit() and len(tok) == 8):
            raise SystemExit("--exclude-date8: %r is not a YYYYMMDD date8"
                             % tok)
        out.add(int(tok))
    return out


def retrieve(cid, k=8, entries=None, pool=None, same_side=False,
             exclude_date8=(), _mutant_filter=False, _mutant_unscaled=False,
             _mutant_ignore_exclude=False):
    """k nearest study-tainted cases to `cid`, nearest first.

    `exclude_date8` (D11) drops whole SESSIONS from the pool — the round-driver
    duty documented above, made mechanical.  It is applied AFTER pool_records
    has run the taint guard on the undiminished pool, so it can only ever
    narrow a pool the ledger already certified.
    """
    _a, _d, _s, qside = MC.parse_cid(cid)
    ex = set(int(d) for d in exclude_date8)
    if _mutant_ignore_exclude:             # MUTANT MT_P12 (test_pattern.t12)
        ex = set()
    recs = [r for r in pool_records(entries, pool=pool,
                                    _mutant_filter=_mutant_filter)
            if r["cid"] != cid
            and int(r["d8"]) not in ex
            and (not same_side or int(r["side"]) == int(qside))]
    if not recs:
        raise PoolRefusal(
            "retrieval pool is empty after --exclude-date8 %s: there is no "
            "study-tainted history left to retrieve from"
            % ",".join(str(d) for d in sorted(ex)))
    # the QUERY never needs its own outcome (it is the thing being decided), so
    # its frame is built without the skeleton arrays.
    q = vector(cid, with_certs=False)
    sc = scales(recs + [q], _mutant_unscaled=_mutant_unscaled)
    scored = []
    n_thin = 0
    for c in recs:
        d, nb, per = distance(q, c, sc)
        if nb < MIN_BLOCKS or not np.isfinite(d):
            n_thin += 1
            continue
        scored.append({"cid": c["cid"], "dist": d, "n_blocks": nb,
                       "blocks": per, "rec": c,
                       "same_session": (str(c["asset"]) == q["asset"]
                                        and int(c["d8"]) == q["d8"])})
    scored.sort(key=lambda r: (round(r["dist"], 9), r["cid"]))
    return q, scored[:int(k)], sc, {"n_pool": len(recs), "n_dropped_thin": n_thin,
                                    "excluded_date8": sorted(ex)}


# ----------------------------------------------------------------- render ---
def _n(v, dec=2):
    if v is None:
        return "."
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    return "." if not np.isfinite(v) else ("%%.%df" % dec) % v


def table(q, hits, k, meta):
    L = []
    A = L.append
    A("REFERENCE-CLASS RETRIEVAL  (%s, k=%d)  pool = %d STUDY-tainted cases "
      "(used-case ledger, STUDY rows only); %d dropped as comparable on < %d "
      "blocks%s" % (SECTION, k, meta["n_pool"], meta["n_dropped_thin"],
                    MIN_BLOCKS,
                    ("; EXCLUDED sessions " + ",".join(
                        str(d) for d in meta.get("excluded_date8") or []))
                    if meta.get("excluded_date8") else ""))
    A("QUERY %-22s %-22s %-6s %-6s  cov=%s%%  ladder=%-16s  runway=%ss  "
      "age(ph/piv)=%s/%s  slope1=%s  accel=%s  rv1800/60=%s  spread=%sx  "
      "lvl=%sxATR"
      % (q["cid"], q["klass"], "LONG" if q["side"] > 0 else "SHORT", q["phase"],
         _n(100.0 * float(q["coverage_phase"]), 1),
         PL.LADDER_BANDS[int(q["ladder_band"])] if int(q["ladder_band"]) >= 0
         else "REFUSED",
         int(q["runway_phase_sec"]), int(q["extreme_age_sec"]),
         int(q["pivot_age_sec"]), _n(q["slope_1m_usd"], 1),
         _n(q["accel_usd"], 1), _n(q["rv_ratio"]), _n(q["spread_ratio"]),
         _n(q["level_dist_atr"], 3)))
    A("")
    A("  # dist  nb  case                    class                  sd  phase "
      "  cov%   ladder            runway  age_ph  age_pv   slope1    accel  "
      "rv_r  spr_x  lvl_atr    close$     peak$  W  D021")
    for n, h in enumerate(hits, 1):
        c = h["rec"]
        A("%3d %.3f %3d  %-22s %-22s %-3s %-6s %6s  %-16s %7d %7d %7d %8s %8s "
          "%5s %6s %8s %9s %9s  %s  %s"
          % (n, h["dist"], h["n_blocks"], c["cid"], c["klass"],
             "L" if c["side"] > 0 else "S", c["phase"],
             _n(100.0 * float(c["coverage_phase"]), 1),
             PL.LADDER_BANDS[int(c["ladder_band"])]
             if int(c["ladder_band"]) >= 0 else "REFUSED",
             int(c["runway_phase_sec"]), int(c["extreme_age_sec"]),
             int(c["pivot_age_sec"]), _n(c["slope_1m_usd"], 1),
             _n(c["accel_usd"], 1), _n(c["rv_ratio"], 1),
             _n(c["spread_ratio"], 2), _n(c["level_dist_atr"], 3),
             _n(c["cert_close_usd"], 2), _n(c["cert_peak_usd"], 2),
             "1" if bool(c["walled"]) else ".",
             "WIN" if bool(c["winner"]) else "."))
    A("")
    A("close$ = walled PHASE-CLOSE certificate (adoption); peak$ = walled "
      "PEAK-EXIT companion (CC-M1-8). W = wall hit. D021 = winner "
      "(close>=$1000, mae<=$300, unwalled).")
    A("nb = comparable blocks out of %d; a REFUSED field is dropped from the "
      "distance, never imputed." % len(BLOCKS))
    return "\n".join(L) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("cid")
    p.add_argument("-k", type=int, default=8)
    p.add_argument("--json", action="store_true")
    p.add_argument("--refresh-pool", action="store_true",
                   help="rebuild the pool cache even if its hash matches")
    p.add_argument("--same-side", action="store_true",
                   help="restrict the pool to the query's side (pool filter, "
                        "not a change to the pinned distance)")
    p.add_argument("--exclude-date8", default="",
                   help="comma-separated YYYYMMDD sessions to drop from the "
                        "pool (D11: the CC-M2-9.4 sequencing duty, in the "
                        "tool). Applied AFTER the taint guard, never before.")
    a = p.parse_args()
    MC.verify_spec(force=True)
    if a.refresh_pool:
        pool_records(refresh=True)
    q, hits, sc, meta = retrieve(a.cid, a.k, same_side=a.same_side,
                                 exclude_date8=parse_exclude_date8(
                                     a.exclude_date8))
    if a.json:
        sys.stdout.write(json.dumps(
            {"query": a.cid, "k": a.k, "scales": sc, "meta": meta,
             "hits": [{"cid": h["cid"], "dist": h["dist"],
                       "n_blocks": h["n_blocks"], "blocks": h["blocks"],
                       "cert_close_usd": float(h["rec"]["cert_close_usd"]),
                       "cert_peak_usd": float(h["rec"]["cert_peak_usd"])}
                      for h in hits]}, indent=1, sort_keys=True) + "\n")
    else:
        sys.stdout.write(table(q, hits, a.k, meta))
    return 0


if __name__ == "__main__":
    sys.exit(main())
