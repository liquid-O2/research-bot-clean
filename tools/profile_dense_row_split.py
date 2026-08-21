#!/usr/bin/env python3
"""Split one dense row's cost: discretionary feature_map vs the REST.

WHY
    The R6 port replaces only the discretionary per-row query path
    (`CausalDiscretionaryPlane.feature_map`, discretionary_features.py:2389).
    Everything else in the row — the windows, ladders, context blocks and the
    float32 cast in `_SessionPlane.feature_map` (confirmation.py:1165-1848) —
    stays in Python unless it is ported too.  Amdahl therefore decides the
    scope: if the disc call is 75% of the row the disc-only port caps near
    x4, and the non-disc remainder has to ride the same identity transition;
    if it is >90% the disc-only port already clears the ruled x6-x17 band and
    the remainder can stay where it is.

HOW
    Two passes over the same session, both bounded to the same first N rows:
      1. cProfile, read for the two functions' cumulative time.  A profiler
         inflates Python-heavy call trees more than numpy-heavy ones, so it
         is used for attribution, not for the headline ratio.
      2. no profiler, wall-clocked at the two call boundaries by the same
         recorder the differential harness uses.  This is the headline.
    Both numbers are published; a large gap between them is itself a finding.

    Session setup (event pack load, plane construction, prior session) is not
    part of either number: only the two per-row calls are timed.
"""

from __future__ import annotations

import argparse
import cProfile
import json
import pstats
import sys
import time
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.entry_v2.disc_native_builders import (  # noqa:E402
    DISC_NATIVE_MAX_DELAY_SEC, DISC_NATIVE_SOURCE_ROOT, DISC_NATIVE_STORE_ROOT,
    DiscCaptureComplete, DiscSessionCapture, capture_disc_session,
    discover_store_sessions, recording_disc_plane)
from engine.entry_v2.tabular_campaign import (  # noqa:E402
    materialize_runtime_dense_feature_session)

DEFAULT_REPORT = Path("/workspace/artifacts/entry_v2/tabular_recovery/"
                      "diagnostics/dense_row_profile_20260821.json")
DISC_FEATURE_MAP_SITE = ("discretionary_features.py", 2389, "feature_map")
SESSION_PLANE_MAP_SITE = ("confirmation.py", 1165, "feature_map")


def arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--session", default="HG/20210621",
                        help="ASSET/YYYYMMDD present in the dense store")
    parser.add_argument("--rows", type=int, default=200,
                        help="rows profiled; the pass aborts after them")
    parser.add_argument("--store-root", type=Path, default=DISC_NATIVE_STORE_ROOT)
    parser.add_argument("--source-root", type=Path, default=DISC_NATIVE_SOURCE_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args(argv)


def _site_stats(stats: pstats.Stats, site: tuple[str, int, str]
                ) -> dict[str, float]:
    """Find one function's entry by (file tail, first line, name)."""

    filename, line, name = site
    matches = [(key, value) for key, value in stats.stats.items()
               if key[0].endswith(filename) and key[1] == line and key[2] == name]
    if len(matches) != 1:
        raise SystemExit(
            f"profile has {len(matches)} entries for {filename}:{line} {name}; "
            "the anchor moved — re-read the source before trusting this split")
    _, value = matches[0]
    # pstats value tuple is (primitive_calls, total_calls, tottime, cumtime, ...)
    return {"calls": int(value[1]), "cumulative_seconds": float(value[3])}


def main(argv: Sequence[str] | None = None) -> int:
    args = arguments(argv)
    sessions = discover_store_sessions(
        source_root=args.source_root, store_root=args.store_root)
    session = next(s for s in sessions if s.label == args.session)

    walled = capture_disc_session(session, query_limit=args.rows,
                                  time_outer=True)
    rows = len(walled.queries)
    wall_disc = walled.disc_seconds
    wall_outer = walled.outer_seconds

    profiled = DiscSessionCapture()
    profiler = cProfile.Profile()
    started = time.perf_counter()
    with recording_disc_plane(profiled, query_limit=args.rows):
        profiler.enable()
        try:
            materialize_runtime_dense_feature_session(
                session.spec, max_delay_sec=DISC_NATIVE_MAX_DELAY_SEC)
        except DiscCaptureComplete:
            pass
        finally:
            profiler.disable()
    profile_wall = time.perf_counter() - started
    stats = pstats.Stats(profiler)
    disc = _site_stats(stats, DISC_FEATURE_MAP_SITE)
    outer = _site_stats(stats, SESSION_PLANE_MAP_SITE)
    rest_profiled = outer["cumulative_seconds"] - disc["cumulative_seconds"]
    disc_share = disc["cumulative_seconds"] / outer["cumulative_seconds"]
    wall_share = wall_disc / wall_outer

    report = {
        "schema": "QRE2DENSEROWSPLIT1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session": session.label,
        "identity_sha256": session.identity,
        "rows_measured": rows,
        "anchors": {
            "discretionary": "engine/entry_v2/discretionary_features.py:2389 "
                             "CausalDiscretionaryPlane.feature_map",
            "outer_row_map": "engine/entry_v2/confirmation.py:1165-1848 "
                             "_SessionPlane.feature_map",
            "disc_call_site": "engine/entry_v2/confirmation.py:1259-1270",
            "float32_cast": "engine/entry_v2/confirmation.py:1856",
        },
        "wall_clock": {
            "note": "no profiler attached; the headline split",
            "disc_seconds": round(wall_disc, 6),
            "outer_seconds": round(wall_outer, 6),
            "rest_seconds": round(wall_outer - wall_disc, 6),
            "disc_ms_per_row": round(1000 * wall_disc / rows, 4),
            "rest_ms_per_row": round(1000 * (wall_outer - wall_disc) / rows, 4),
            "outer_ms_per_row": round(1000 * wall_outer / rows, 4),
            "disc_share_of_row": round(wall_share, 5),
            "rest_share_of_row": round(1 - wall_share, 5),
        },
        "cprofile": {
            "note": "attribution only; a profiler inflates Python-heavy trees",
            "wall_seconds": round(profile_wall, 3),
            "disc": disc,
            "outer_row_map": outer,
            "rest_cumulative_seconds": round(rest_profiled, 6),
            "disc_share_of_row": round(disc_share, 5),
        },
        "amdahl_at_the_row_map": {
            "note": "ceiling on the per-row map if ONLY the disc call is "
                    "ported; the REST stays interpreted",
            "disc_only_infinite_speedup": round(1.0 / (1.0 - wall_share), 2),
            "disc_only_native_x20": round(
                1.0 / ((1.0 - wall_share) + wall_share / 20.0), 2),
            "disc_only_native_x50": round(
                1.0 / ((1.0 - wall_share) + wall_share / 50.0), 2),
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report["wall_clock"], indent=2, sort_keys=True))
    print(json.dumps(report["cprofile"], indent=2, sort_keys=True))
    print(json.dumps(report["amdahl_at_the_row_map"], indent=2, sort_keys=True))
    print(f"REPORT {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
