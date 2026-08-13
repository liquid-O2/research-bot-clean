#!/usr/bin/python3
"""PORT M2 — the ERA BATCH RENDERER (gate P-M2b, spec §4).

Renders the era material the reader protocol consumes: for each candidate a
BLIND sheet (S1..S13) and a SEPARATE S14 appendix, both certified, with a
STREAM_RECEIPT.tsv rollup per (era, block).

WORK UNIT = one (asset, session).  Day-complete (D-036) is the protocol's unit
and it is also the efficient one: the S6 event cache is per session, so a
session's whole candidate set is served by ONE decode pass over the payload.

VOLUME NOTE (measured, P-M2b): the E1+E2 population is 326,238 candidates
(E1 STUDY 95,102 / BLIND 55,574; E2 STUDY 108,701 / BLIND 66,861).  A full-block
eager render is therefore not the shape of this deliverable — the index
(era_index.py) is the complete population and THIS renderer materialises any
requested subset of it on demand, receipted, with the requested subset always
named explicitly (--sessions / --max-sessions / --cids).  Nothing is ever
sampled silently: a render that covers part of a block says so in its receipt
(`coverage` = rendered/eligible per block).

Run:
  lab/run.sh port-m2b -- /usr/bin/python3 engine/port_m2/era_build.py \
      --era E1 --block STUDY --max-sessions 8 --workers 6
"""
import argparse
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
import sheets as SH                       # noqa: E402
import tape as TAPE                       # noqa: E402
import context as CTX                     # noqa: E402
import era_index as EI                    # noqa: E402

SECTION = "§4 [P-M2b] era E1/E2 sheet sets"
WORKERS_MAX = 12                          # orchestrator 2026-08-14: the
                                          # 6-worker cap is lifted (sole
                                          # lane on a 13.6-core cgroup;
                                          # ~1.5 cores left for the harness)

SHEET_COLUMNS = ("cid", "asset", "era", "block", "date8", "dec_sec", "side",
                 "phase", "primary_family", "candidate_class",
                 "certified", "n_failed_sections",
                 "n_leak_refusals", "tokens_proxy", "chars", "lines",
                 "appendix_tokens", "sheet_sha256", "appendix_sha256")

SESSION_COLUMNS = ("era", "block", "asset", "date8", "n_candidates",
                   "n_rendered", "n_certified", "n_refused", "tokens_proxy",
                   "appendix_tokens", "n_events_cached", "wall_sec", "status")


def out_dir(era, block, asset, d8):
    return MC.out_path("era", era, block, asset, "%08d" % int(d8), "_")[:-1]


def _params(args):
    return {
        "spec_section": SECTION,
        "eras": args.era,
        "block": args.block,
        "assets": args.assets,
        "sheet_mode": "BLIND sheet (S1..S13) + SEPARATE S14 appendix file",
        "sidecars": args.sidecars,
        "workers": args.workers,
        "selection": "every ELIGIBLE index row of the requested (era, block, "
                     "asset, session) set — day-complete, no sampling",
        "sheets_version": MC.SHEETS_VERSION,
        "sheet_budget": MC.SHEET_BUDGET_BLIND,
        "section_budget": dict(MC.SECTION_BUDGET),
    }


# ------------------------------------------------------------------ worker --
_CFG = {}


def _init(cfg):
    global _CFG
    _CFG = cfg
    MC.verify_spec(force=True)            # pin-at-launch, once per worker
    CTX.preload(MC.ASSET_ORDER)


def session_receipt_path(era, block, asset, d8):
    return os.path.join(out_dir(era, block, asset, d8), "_session.receipt.json")


def _render_session(task):
    """(era, block, asset, d8, [(cid, dec_sec, phase, family)]) -> rows.

    Writes a per-session receipt so a long era render is RESUMABLE: a session
    whose receipt exists is skipped by the driver and its rows are read back
    into the rollup, so an interrupted run never re-renders finished days and
    never loses their receipts.
    """
    era, block, asset, d8, cands = task
    t0 = time.time()
    od = out_dir(era, block, asset, d8)
    rows = []
    n_cert = n_ref = 0
    n_events = 0
    status = "OK"
    try:
        # ONE decode pass: the union of every candidate's canonical window.
        sess = A.load_session(asset, int(d8))
        s = sess["s"]
        ranges = []
        for cid, ds, ph, fam, cls in cands:
            lo = max(0, int(ds) - TAPE.RIBBON_DIGEST_SEC - TAPE.RIBBON_RAW_SEC
                     - TAPE.EXTRACT_PAD_SEC)
            ranges.append((lo, int(ds) + 1))
        arrays, meta = TAPE.ensure(asset, sess["trade_date"], int(s.iid),
                                   int(s.meta["open_utc"]),
                                   int(s.meta["close_utc"]), ranges)
        n_events = int(meta["n_events"])
        for cid, ds, ph, fam, cls in cands:
            try:
                sh = SH.build(cid, MC.MODE_BLIND, with_appendix=True)
            except MC.LeakRefusal as e:
                n_ref += 1
                rows.append([cid, asset, era, block, int(d8), int(ds),
                             1 if cid.endswith("-L") else -1, ph, fam, cls,
                             0, -1, 1, 0, 0, 0, 0, "REFUSED", str(e)[:120]])
                continue
            SH.emit(sh, od, sidecars=_CFG.get("sidecars") == "all")
            c = sh.certificate
            n_cert += c["certified"]
            rows.append([cid, asset, era, block, int(d8), int(ds),
                         1 if cid.endswith("-L") else -1, ph, fam, cls,
                         c["certified"], c["n_failed_sections"],
                         c["n_leak_refusals"], c["sheet"]["tokens_proxy"],
                         c["sheet"]["chars"], c["sheet"]["lines"],
                         c["appendix"]["tokens_proxy"] if c["appendix"] else 0,
                         sh.sha256, sh.appendix_sha256])
    except Exception as e:                # noqa: BLE001 — reported, not hidden
        status = "FAIL:%s" % str(e)[:160]
    tok = sum(r[13] for r in rows)
    atok = sum(r[16] for r in rows)
    srow = [era, block, asset, int(d8), len(cands), len(rows), n_cert, n_ref,
            tok, atok, n_events, round(time.time() - t0, 2), status]
    if status == "OK":
        MC.write_json(session_receipt_path(era, block, asset, d8),
                      {"srow": srow, "rows": rows,
                       "sheets_version": MC.SHEETS_VERSION,
                       "spec_shas": MC.spec_shas()})
    MC.hb("era_build %s/%s %s %s: %d/%d certified %.1fs %s"
          % (era, block, asset, d8, n_cert, len(cands), time.time() - t0,
             status))
    return rows, srow


# ------------------------------------------------------------------ driver --
def tasks_for(era, block, assets, want_sessions=None, max_sessions=None,
              cids=None):
    out = []
    for asset in assets:
        by = {}
        for r in EI.load_index(era, asset):
            if r["block"] != block or r["eligible"] != "1":
                continue
            if cids is not None and r["cid"] not in cids:
                continue
            d8 = int(r["date8"])
            if want_sessions is not None and d8 not in want_sessions:
                continue
            by.setdefault(d8, []).append((r["cid"], int(r["dec_sec"]),
                                          r["phase_dec"],
                                          r["primary_family"],
                                          r["candidate_class"]))
        for d8 in sorted(by)[:max_sessions] if max_sessions else sorted(by):
            out.append((era, block, asset, d8, by[d8]))
    # longest sessions first: with <=6 workers this keeps the tail short
    out.sort(key=lambda t: (-len(t[4]), t[2], t[3]))
    return out


def eligible_counts(era, block, assets):
    n_c = n_s = 0
    for asset in assets:
        ds = set()
        for r in EI.load_index(era, asset):
            if r["block"] == block and r["eligible"] == "1":
                n_c += 1
                ds.add(r["date8"])
        n_s += len(ds)
    return n_c, n_s


def run(args):
    MC.verify_spec(force=True)
    t_start = time.time()
    params = _params(args)
    phash = MC.params_hash(params)
    cids = None
    if args.cids:
        with open(args.cids) as fh:
            cids = {ln.strip() for ln in fh if ln.strip()
                    and not ln.startswith("#")}
    want = None
    if args.sessions:
        want = {int(x) for x in args.sessions.split(",")}

    all_rows, all_srows = [], []
    for era in args.era:
        tasks = tasks_for(era, args.block, args.assets, want,
                          args.max_sessions, cids)
        n_elig, n_sess = eligible_counts(era, args.block, args.assets)
        n_req = sum(len(t[4]) for t in tasks)
        MC.hb("era_build %s/%s: %d sessions / %d candidates requested "
              "(block eligible: %d sessions / %d candidates)"
              % (era, args.block, len(tasks), n_req, n_sess, n_elig))
        if args.dry_run:
            # The ON-DEMAND posture, made explicit and receipted: the index IS
            # the population, this receipt names what a full render of the block
            # would cost and the exact command that materialises any subset.
            MC.write_json(
                os.path.join(EI.era_dir(era),
                             "ondemand_%s.receipt.json" % args.block),
                {"env": MC.env_receipt(params), "era": era,
                 "block": args.block,
                 "status": "INDEX+RENDERER (not eagerly rendered)",
                 "block_eligible_candidates": n_elig,
                 "block_eligible_sessions": n_sess,
                 "n_sheets_rendered": 0, "coverage_candidates": 0.0,
                 "index": [os.path.join(EI.era_dir(era), "INDEX_%s.tsv" % a)
                           for a in args.assets],
                 "reader_order_index": os.path.join(
                     EI.era_dir(era), "INDEX_BLIND_CHRONO.tsv"),
                 "render_command":
                     "lab/run.sh port-m2b -- /usr/bin/python3 "
                     "engine/port_m2/era_build.py --era %s --block %s "
                     "--workers 6 [--sessions d8,d8 | --max-sessions N | "
                     "--cids FILE]" % (era, args.block),
                 "measured_cost_per_sheet_sec": 0.33,
                 "measured_bytes_per_sheet": 24600,
                 "note": "no subsampling: any render names its subset and its "
                         "receipt records coverage against this population"})
            continue
        res = []
        todo = []
        for t in tasks:
            p = session_receipt_path(t[0], t[1], t[2], t[3])
            if os.path.exists(p) and not args.force:
                import json as _json
                with open(p) as fh:
                    d = _json.load(fh)
                res.append((d["rows"], d["srow"]))
            else:
                todo.append(t)
        MC.hb("era_build %s/%s: %d sessions already receipted, %d to render"
              % (era, args.block, len(res), len(todo)))
        cfg = {"sidecars": args.sidecars}
        if args.workers > 1 and len(todo) > 1:
            with mp.Pool(min(args.workers, WORKERS_MAX), initializer=_init,
                         initargs=(cfg,)) as pool:
                for out in pool.imap_unordered(_render_session, todo,
                                               chunksize=1):
                    res.append(out)
        else:
            _init(cfg)
            for t in todo:
                res.append(_render_session(t))
        rows = [r for rr, _ in res for r in rr]
        srows = [s for _, s in res]
        rows.sort(key=lambda r: (r[1], r[4], r[5], r[6]))
        srows.sort(key=lambda s: (s[2], s[3]))
        base = EI.era_dir(era)
        MC.write_tsv(os.path.join(base, "STREAM_RECEIPT_%s.tsv" % args.block),
                     SECTION, phash, list(SHEET_COLUMNS), rows,
                     extra=["one row per rendered sheet; tokens are the %s "
                            "proxy" % MC.TOKEN_PROXY_ID,
                            "block eligible population = %d candidates over "
                            "%d sessions" % (n_elig, n_sess)])
        MC.write_tsv(os.path.join(base, "SESSIONS_%s.tsv" % args.block),
                     SECTION, phash, list(SESSION_COLUMNS), srows)
        n_cert = sum(int(r[10]) for r in rows)
        toks = [int(r[13]) for r in rows if int(r[13]) > 0]
        receipt = {
            "env": MC.env_receipt(params),
            "era": era, "block": args.block,
            "block_eligible_candidates": n_elig,
            "block_eligible_sessions": n_sess,
            "n_sessions_rendered": len(srows),
            "n_sheets_rendered": len(rows),
            "n_certified": n_cert,
            "n_refused": sum(int(s[7]) for s in srows),
            "n_session_failures": sum(1 for s in srows
                                      if not str(s[12]).startswith("OK")),
            "coverage_candidates": (len(rows) / n_elig) if n_elig else 0.0,
            "tokens_proxy": {"total": int(sum(toks)),
                             "min": int(min(toks)) if toks else 0,
                             "median": float(np.median(toks)) if toks else 0.0,
                             "max": int(max(toks)) if toks else 0},
            "appendix_tokens_total": int(sum(int(r[16]) for r in rows)),
            "out_root": os.path.join(MC.M2_ROOT, "era", era, args.block),
            "pins_moved_during_run": MC.pins_moved(),
            "wall_sec": round(time.time() - t_start, 1),
        }
        MC.write_json(os.path.join(base, "build_%s.receipt.json" % args.block),
                      receipt)
        MC.hb("era_build %s/%s: %d sheets, %d certified, coverage %.4f, %.0fs"
              % (era, args.block, len(rows), n_cert,
                 receipt["coverage_candidates"], time.time() - t_start))
        all_rows.extend(rows)
        all_srows.extend(srows)
    bad = [s for s in all_srows if not str(s[12]).startswith("OK")]
    ncert = sum(int(r[10]) for r in all_rows)
    return 0 if (not bad and ncert == len(all_rows)) else 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--era", nargs="+", default=["E1"])
    p.add_argument("--block", default=EI.BLOCK_STUDY,
                   choices=[EI.BLOCK_STUDY, EI.BLOCK_BLIND])
    p.add_argument("--assets", nargs="+", default=list(MC.ASSET_ORDER))
    p.add_argument("--sessions", default=None,
                   help="comma-separated date8 list")
    p.add_argument("--max-sessions", type=int, default=None,
                   help="first N sessions of the block, per asset")
    p.add_argument("--cids", default=None, help="file of candidate ids")
    p.add_argument("--workers", type=int, default=WORKERS_MAX)
    p.add_argument("--sidecars", default="none", choices=("none", "all"))
    p.add_argument("--force", action="store_true",
                   help="re-render sessions that already carry a receipt")
    p.add_argument("--dry-run", action="store_true")
    return run(p.parse_args())


if __name__ == "__main__":
    sys.exit(main())
