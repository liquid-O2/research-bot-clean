#!/usr/bin/python3
"""PORT M2 — the 30-SHEET PILOT (spec §4 [P-M2a]).

10 candidates per asset, stratified {era x phase x family}, rendered in BLIND
mode with their S14 appendices as SEPARATE artefacts, plus a machine-readable
sidecar per sheet carrying every number on the sheet with its source receipt
path and key — the orchestrator hand-verifies the pilot against raw receipts
and the sidecar is what makes that a lookup rather than an excavation.

Selection is DETERMINISTIC and RNG-FREE (D-018 / determinism law): the strata
are enumerated in a fixed order, the target cells are walked as a diagonal over
(era, phase, family) so no axis is starved, and inside a cell the candidate at
the MEDIAN index of the (date8, dec_sec, side)-sorted list is taken.  Re-running
the pilot selects the same 30 candidates.

Run: lab/run.sh port-m2a -- /usr/bin/python3 engine/port_m2/pilot.py
"""
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import census_common as X                 # noqa: E402
import assemble as A                      # noqa: E402
import sheets as SH                       # noqa: E402
import tape as TAPE                       # noqa: E402
import context as CTX                     # noqa: E402

SECTION = "§4 [P-M2a] 30-sheet pilot"
OUT_DIR = MC.out_path("pilot", "_")[:-1]
N_PER_ASSET = 10
WORKERS = 6                               # brief cap

PARAMS = {
    "spec_section": SECTION,
    "n_per_asset": N_PER_ASSET,
    "strata": "era x phase_dec x primary_family (primary = lowest set bit of "
              "fam_mask in the generation-v3 family order)",
    "selection": "diagonal walk over (eras present, phases present, families "
                 "present); inside a cell the MEDIAN index of the candidates "
                 "sorted by (date8, dec_sec, side); no RNG anywhere",
    "eligible": "era in E1..E8 only (PRE_E1, the 2025H2 holdout and the 2026 "
                "seal are excluded); the session must carry level and profile "
                "receipts",
    "modes": "BLIND sheet + SEPARATE S14 appendix, per spec §1",
    "workers": WORKERS,
}


def primary_family(fam_mask):
    """The stratum family = the RAREST family carried by the candidate.

    Generation v3 unions family tags at a shared (decision_sec, side), so most
    NEWS_WINDOW / MICRO_OPEN / POST_SHOCK / FIRST_TEST candidates also carry
    G1.  Taking the lowest set bit would label almost everything "G1" and the
    pilot would never show the discovery families at all — which are exactly
    the families the M1 census measured the largest edge on.  MC.FAMILIES is
    ordered core-first, so the HIGHEST set bit is the rarest tag.
    """
    out = "NONE"
    for f in MC.FAMILIES:
        if int(fam_mask) & MC.FAM_BIT[f]:
            out = f
    return out


def eligible_cells(asset):
    """{(era, phase, family): [row indices sorted by (date8, dec_sec, side)]}"""
    r = A.roster(asset)
    d8 = r["date8"]
    lev_dir = os.path.join(A.LEVELS_DIR, asset)
    prof_dir = os.path.join(A.PROFILES_DIR, asset)
    have = {}
    cells = {}
    order = np.lexsort((r["side"], r["dec_sec"], r["date8"]))
    for i in order.tolist():
        d = int(d8[i])
        try:
            era = MC.era_of(d)
        except Exception:
            continue
        if not era.startswith("E") or era.startswith("ERA"):
            continue
        if era not in [e[0] for e in MC.ERAS]:
            continue
        ok = have.get(d)
        if ok is None:
            ok = (os.path.exists(os.path.join(lev_dir, "%08d.npz" % d))
                  and os.path.exists(os.path.join(prof_dir, "%08d.npz" % d))
                  and d in A.session_index(asset))
            have[d] = ok
        if not ok:
            continue
        key = (era, X.PHASE_NAMES[int(r["phase_dec"][i])],
               primary_family(int(r["fam_mask"][i])))
        cells.setdefault(key, []).append(i)
    return cells


def select(asset, n=N_PER_ASSET):
    cells = eligible_cells(asset)
    if not cells:
        return []
    eras = [e[0] for e in MC.ERAS if any(k[0] == e[0] for k in cells)]
    phases = [p for p in X.PHASE_NAMES if any(k[1] == p for k in cells)]
    fams = [f for f in MC.FAMILIES if any(k[2] == f for k in cells)]
    r = A.roster(asset)
    chosen = []
    used = set()
    step = 0
    # diagonal walk: each pick advances all three axes, so eras, phases and
    # families are all covered before any repeats
    while len(chosen) < n and step < 4 * n * max(1, len(fams)):
        era = eras[step % len(eras)]
        ph = phases[step % len(phases)]
        fam = fams[step % len(fams)]
        step += 1
        # fallback order keeps the FAMILY axis longest: the rare families
        # (POST_SHOCK, FIRST_TEST) carry the largest measured edge, so a pilot
        # that drops them to preserve a phase would be the wrong 30 sheets.
        for key in ((era, ph, fam), (era, None, fam), (era, ph, None),
                    (era, None, None)):
            picks = []
            for k, v in cells.items():
                if k[0] != key[0]:
                    continue
                if key[1] is not None and k[1] != key[1]:
                    continue
                if key[2] is not None and k[2] != key[2]:
                    continue
                picks.extend(v)
            if not picks:
                continue
            picks.sort()
            j = len(picks) // 2
            hit = None
            for off in range(len(picks)):
                # walk outward from the median, deterministically
                for cand in (picks[(j + off) % len(picks)],):
                    if cand not in used:
                        hit = cand
                        break
                if hit is not None:
                    break
            if hit is None:
                continue
            used.add(hit)
            cid = MC.make_cid(asset, int(r["date8"][hit]),
                              int(r["dec_sec"][hit]), int(r["side"][hit]))
            chosen.append((cid, key[0],
                           X.PHASE_NAMES[int(r["phase_dec"][hit])],
                           primary_family(int(r["fam_mask"][hit])), hit))
            break
    return chosen


def _prefetch(args):
    asset, d8 = args
    t0 = time.time()
    try:
        sess = A.load_session(asset, d8)
        s = sess["s"]
        d = sess["trade_date"]
        r = A.roster(asset)
        secs = [int(x) for x in r["dec_sec"][r["date8"] == d8].tolist()]
        # only the decision seconds actually selected are needed, but the whole
        # session's selected set is passed in by the caller through `SEL`
        want = SEL.get((asset, d8), secs)
        ranges = []
        for ds in want:
            lo = max(0, ds - TAPE.RIBBON_DIGEST_SEC - TAPE.RIBBON_RAW_SEC
                     - TAPE.EXTRACT_PAD_SEC)
            ranges.append((lo, ds + 1))
        TAPE.ensure(asset, d, int(s.iid), int(s.meta["open_utc"]),
                    int(s.meta["close_utc"]), ranges)
        MC.hb("prefetch %s %d: %.1fs" % (asset, d8, time.time() - t0))
        return (asset, d8, "OK", time.time() - t0)
    except Exception as e:                # noqa: BLE001 — reported, not hidden
        MC.hb("prefetch %s %d FAILED: %s" % (asset, d8, e))
        return (asset, d8, "FAIL:%s" % e, time.time() - t0)


SEL = {}


def main():
    MC.verify_spec()
    t_start = time.time()
    phash = MC.params_hash(PARAMS)
    CTX.preload(MC.ASSET_ORDER)

    picks = []
    for asset in MC.ASSET_ORDER:
        got = select(asset)
        MC.hb("pilot select %s: %d candidates" % (asset, len(got)))
        picks.extend((asset,) + g for g in got)

    for asset, cid, era, ph, fam, row in picks:
        _, d8, ds, _ = MC.parse_cid(cid)
        SEL.setdefault((asset, d8), []).append(ds)

    tasks = sorted(SEL)
    MC.hb("pilot prefetch: %d sessions, %d workers" % (len(tasks), WORKERS))
    if WORKERS > 1 and len(tasks) > 1:
        with mp.Pool(WORKERS, initializer=_init, initargs=(SEL,)) as pool:
            pre = list(pool.imap_unordered(_prefetch, tasks, chunksize=1))
    else:
        pre = [_prefetch(t) for t in tasks]
    pre_fail = [p for p in pre if not p[2].startswith("OK")]

    rows = []
    idx = []
    n_cert = 0
    for asset, cid, era, ph, fam, row in picks:
        t0 = time.time()
        blind = SH.build(cid, MC.MODE_BLIND)
        SH.emit(blind, OUT_DIR)
        study = SH.build(cid, MC.MODE_STUDY)
        SH.emit(study, OUT_DIR)
        c = blind.certificate
        n_cert += c["certified"]
        sec = c["sections"]
        rows.append([cid, asset, era, ph, fam, c["trade_date"],
                     c["decision_ts"], c["certified"], c["n_failed_sections"],
                     c["n_leak_refusals"], c["sheet"]["tokens_proxy"],
                     c["sheet"]["chars"], c["sheet"]["lines"],
                     study.certificate["appendix"]["tokens_proxy"],
                     blind.sha256, study.appendix_sha256,
                     "%.2f" % (time.time() - t0)]
                    + [sec[s]["tokens_proxy"] for s in MC.BLIND_SECTIONS]
                    + [sec[s]["rows"] for s in MC.BLIND_SECTIONS])
        v = {x["key"]: x["value"] for x in blind.sidecar["values"]}
        idx.append([cid, asset, era, ph, fam,
                    v.get("S6.n_events_90s"), v.get("S6.n_events_raw_shown"),
                    v.get("S6.raw_cover_sec"), v.get("S6.n_episodes"),
                    v.get("S4.n_active_in_band"), v.get("S12.n_series_joined"),
                    v.get("S12.n_series_refused"), v.get("S3.n_pivots")])
        MC.hb("pilot %s certified=%d tokens=%d" %
              (cid, c["certified"], c["sheet"]["tokens_proxy"]))

    cols = (["cid", "asset", "era", "phase", "family", "trade_date",
             "decision_ts", "certified", "n_failed_sections",
             "n_leak_refusals", "tokens_proxy", "chars", "lines",
             "appendix_tokens", "sheet_sha256", "appendix_sha256",
             "wall_sec"]
            + ["tok_%s" % s for s in MC.BLIND_SECTIONS]
            + ["rows_%s" % s for s in MC.BLIND_SECTIONS])
    MC.write_tsv(os.path.join(OUT_DIR, "STREAM_RECEIPT.tsv"), SECTION, phash,
                 cols, rows,
                 extra=["one row per pilot sheet; tokens are the %s proxy "
                        "(no BPE tokenizer on this host)" % MC.TOKEN_PROXY_ID])
    MC.write_tsv(os.path.join(OUT_DIR, "PILOT_INDEX.tsv"), SECTION, phash,
                 ["cid", "asset", "era", "phase", "family", "s6_n_events_90s",
                  "s6_n_raw_shown", "s6_raw_cover_sec", "s6_n_episodes",
                  "s4_n_in_band", "s12_n_joined", "s12_n_refused",
                  "s3_n_pivots"], idx)
    toks = [r[10] for r in rows]
    receipt = {
        "env": MC.env_receipt(PARAMS),
        "n_sheets": len(rows),
        "n_certified": int(n_cert),
        "n_prefetch_failed": len(pre_fail),
        "prefetch_failures": [list(p) for p in pre_fail],
        "tokens_proxy": {"min": int(min(toks)) if toks else 0,
                         "median": float(np.median(toks)) if toks else 0,
                         "max": int(max(toks)) if toks else 0},
        "section_tokens": {s: {
            "min": int(min(r[17 + i] for r in rows)),
            "median": float(np.median([r[17 + i] for r in rows])),
            "max": int(max(r[17 + i] for r in rows))}
            for i, s in enumerate(MC.BLIND_SECTIONS)} if rows else {},
        "out_dir": OUT_DIR,
        "wall_sec": round(time.time() - t_start, 1),
    }
    MC.write_json(os.path.join(OUT_DIR, "pilot.receipt.json"), receipt)
    MC.hb("pilot: %d sheets, %d certified, %.0fs"
          % (len(rows), n_cert, time.time() - t_start))
    return 0 if (n_cert == len(rows) and not pre_fail) else 1


def _init(sel):
    global SEL
    SEL = sel


if __name__ == "__main__":
    sys.exit(main())
