#!/usr/bin/env python3
"""BUILD_WF_CACHE — extend the model-v2 per-session caches from the 398..447
block to every era block the walk-forward lane evaluates.

Three independent stages, each idempotent (an existing cache file is skipped),
each shardable so the 64-core box can run them wide:

    build_wf_cache.py w2cand  --shard i/n     qr_wave2_dump at the candidate seconds
    build_wf_cache.py sec     --shard i/n     dm.second_arrays + model_v2.extra_arrays
    build_wf_cache.py quotes  --shard i/n     build_quotes.quote_arrays (the slow one)

The session list is derived from the roster records under `sheets/`, so a new
era block dropped in as `sheets/roster_<block>.json` is picked up with no edit.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import packlib as P                                    # noqa: E402

ROOT = P.ROOT
SHEETS = ROOT / "sheets"


def rosters() -> dict:
    """{block: {session: [candidate, ...]}} over every roster record present."""
    out = {}
    for path in sorted(glob.glob(str(SHEETS / "roster_*.json"))):
        record = json.loads(pathlib.Path(path).read_text())
        out[record["block"]] = record
    return out


def session_seconds() -> dict:
    """{ordinal: sorted unique decision seconds} across every era block."""
    wanted: dict = {}
    for record in rosters().values():
        for key, candidates in record["sessions"].items():
            wanted.setdefault(int(key), set()).update(int(c["second"]) for c in candidates)
    return {ordinal: sorted(seconds) for ordinal, seconds in sorted(wanted.items())}


def shard(items: list, spec: str) -> list:
    if not spec:
        return items
    index, total = (int(part) for part in spec.split("/"))
    return [item for position, item in enumerate(items) if position % total == index]


def ensure_summaries(highest: int) -> pathlib.Path:
    """`qr_wave2_dump values` needs a summaries table covering the ordinal.

    The cached table stops at whatever the last build needed, so an era block
    beyond it (the 448+ extension) regenerates it here rather than failing —
    this is what makes a new roster a zero-code-change drop-in.
    """
    path = P.CACHE / "summaries.tsv"
    have = -1
    if path.exists():
        for line in path.read_text().splitlines():
            if line.startswith("summary\t"):
                have = max(have, int(line.split("\t")[1]))
    if have >= highest:
        return path
    print(f"summaries cover ..{have}, need ..{highest} — regenerating", flush=True)
    scratch = path.with_suffix(f".{os.getpid()}.tmp")
    subprocess.run([str(P.BIN / "qr_wave2_dump"), "summaries",
                    "--from", "0", "--to", str(highest), "--out", str(scratch)],
                   check=True)
    os.replace(scratch, path)          # atomic: parallel shards cannot half-write it
    return path


def stage_w2cand(work: dict) -> None:
    out_dir = P.CACHE / "w2cand"
    out_dir.mkdir(parents=True, exist_ok=True)
    if work:
        ensure_summaries(max(work))
    for ordinal, seconds in work.items():
        #: a day-complete roster may legitimately contain a session with ZERO
        #: confirmed extremes (s829 = 2025-03-27).  `qr_wave2_dump values`
        #: rejects an empty `--seconds` list, so that session is skipped here
        #: rather than killing the shard and every session behind it.
        if not seconds:
            print(f"s{ordinal} w2cand skipped (no candidates)", flush=True)
            continue
        out = out_dir / f"s{ordinal}.tsv"
        if out.exists():
            have = {int(line.split("\t")[1]) for line in out.read_text().splitlines()
                    if line.startswith("point\t")}
            if set(seconds) <= have:
                print(f"s{ordinal} w2cand cached", flush=True)
                continue
        subprocess.run([str(P.BIN / "qr_wave2_dump"), "values",
                        "--summaries", str(P.CACHE / "summaries.tsv"),
                        "--ordinal", str(ordinal),
                        "--seconds", ",".join(str(s) for s in seconds),
                        "--out", str(out)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"s{ordinal} w2cand {len(seconds)} seconds", flush=True)


def stage_sec(work: dict) -> None:
    import distill_model as dm
    import model_v2 as mv
    for ordinal in work:
        dm.second_arrays(ordinal)
        mv.extra_arrays(ordinal)
        print(f"s{ordinal} sec ok", flush=True)


def stage_quotes(work: dict) -> None:
    import build_quotes
    for ordinal in work:
        arrays = build_quotes.quote_arrays(ordinal)
        print(f"s{ordinal} quotes {arrays['q_n'].sum():,.0f}", flush=True)


def stage_greeks(work: dict) -> None:
    """`_cache/sec4` — the CC-013 full-greek per-second flows model_v3's `T_`
    tier reads.  Same drop-in contract as the other stages: roster-driven,
    idempotent, shardable."""
    import model_v3 as mv3
    for ordinal in work:
        mv3.greek_arrays(ordinal)
        print(f"s{ordinal} greeks ok", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("w2cand", "sec", "quotes", "greeks", "list"))
    parser.add_argument("--shard", default="")
    args = parser.parse_args()

    wanted = session_seconds()
    ordinals = shard(sorted(wanted), args.shard)
    work = {ordinal: wanted[ordinal] for ordinal in ordinals}
    if args.stage == "list":
        print(f"{len(wanted)} sessions {min(wanted)}..{max(wanted)}; "
              f"{sum(len(v) for v in wanted.values())} candidate seconds")
        return
    {"w2cand": stage_w2cand, "sec": stage_sec, "quotes": stage_quotes,
     "greeks": stage_greeks}[args.stage](work)


if __name__ == "__main__":
    main()
