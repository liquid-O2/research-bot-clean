#!/usr/bin/env python3
"""Warmed ms/row for the three qrdisc row paths, on one dense-store session.

WHY THIS EXISTS
    Stage 4 wave 1 could only SPLICE: the whole-map delegate assembled every row
    in Python and native families were written over it, so a native family added
    cost and saved nothing.  Wave 2 lane C assembles the row natively
    (engine/cpp/qr_entry_v2/src/qrdisc_assembly.cpp).  Whether that is actually
    faster is a measurement, not an argument, and this is the instrument.

WHAT IS TIMED
    oracle    `CausalDiscretionaryPlane.feature_map`, the frozen Python path.
    splice    `feature_map_row` with the wave-1 families native and the
              whole-map delegate still assembling (`assemble_natively=False`).
    assembly  the same families, but the port assembling the row.

    All three run on the SAME warmed plane state, in the same process, under the
    same thread pinning, after the same warm-up.  The reported number is wall
    clock with no profiler attached: a profiler inflates Python-heavy trees and
    would flatter the native path.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from threadpoolctl import threadpool_limits  # noqa:E402

from engine.entry_v2.disc_native_builders import (  # noqa:E402
    capture_disc_session, discover_store_sessions)
from engine.entry_v2.discretionary_features import (  # noqa:E402
    CausalDiscretionaryPlane)
from engine.entry_v2.qrdisc_native_loader import (  # noqa:E402
    QRDISC_TAIL_FAMILIES, QrdiscNativeRefusal, qrdisc_build_native_plane)
from engine.entry_v2.qrdisc_state_marshal import (  # noqa:E402
    qrdisc_warm_plane_caches)
from engine.entry_v2.tabular_campaign import (  # noqa:E402
    NATIVE_THREADS_PER_CORPUS_WORKER)

DEFAULT_REPORT = Path("/workspace/artifacts/entry_v2/tabular_recovery/"
                      "diagnostics/qrdisc_row_path_timing.json")


def _timed(call, queries, warmup: int) -> tuple[float, int]:
    for query in queries[:warmup]:
        call(query)
    started = time.perf_counter()
    for query in queries:
        call(query)
    return time.perf_counter() - started, len(queries)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default="HG/20210621")
    parser.add_argument("--rows", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=25)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    session = next(s for s in discover_store_sessions()
                   if s.label == args.session)
    # The capture is a COLD recompute of the session, so it is limited to the
    # rows that will be timed; the plane is then warmed on exactly those rows,
    # which is what the caches would hold at this point of a real session.
    capture = capture_disc_session(session, query_limit=args.rows)
    queries = capture.queries[:args.rows]
    report: dict[str, object] = {
        "schema": "QRDISCROWPATH1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session": session.label,
        "identity_sha256": session.identity,
        "rows_timed": len(queries),
        "warmup_rows": args.warmup,
        "native_families": list(QRDISC_TAIL_FAMILIES),
    }
    with threadpool_limits(limits=NATIVE_THREADS_PER_CORPUS_WORKER):
        plane = CausalDiscretionaryPlane(**capture.construction)
        qrdisc_warm_plane_caches(plane, capture.queries)
        seconds, rows = _timed(lambda query: plane.feature_map(**query),
                               queries, args.warmup)
        report["oracle"] = {"seconds": round(seconds, 4),
                            "ms_per_row": round(1000.0 * seconds / rows, 4)}
        for label, assemble in (("splice", False), ("assembly", True)):
            native, module, _plane = qrdisc_build_native_plane(
                capture.construction, capture.queries, QRDISC_TAIL_FAMILIES,
                assemble_natively=assemble)
            available = bool(module.assembly_available(native))
            if available != assemble:
                raise QrdiscNativeRefusal(
                    f"the {label!r} path reports assembly_available="
                    f"{available}; the timing would measure the wrong path")
            seconds, rows = _timed(
                lambda query, n=native, m=module: m.feature_map_row(n, **query),
                queries, args.warmup)
            report[label] = {
                "seconds": round(seconds, 4),
                "ms_per_row": round(1000.0 * seconds / rows, 4),
                "assembly_available": available,
            }
    oracle_ms = float(report["oracle"]["ms_per_row"])  # type: ignore[index]
    for label in ("splice", "assembly"):
        entry = report[label]  # type: ignore[assignment]
        entry["speedup_vs_oracle"] = round(
            oracle_ms / float(entry["ms_per_row"]), 4)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print(json.dumps(report, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
