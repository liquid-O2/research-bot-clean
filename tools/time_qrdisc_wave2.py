#!/usr/bin/env python3
"""Warmed ms/row for the R6 SHIPPED end state — ticket 40 (2026-08-23).

`tools/time_qrdisc_row_paths.py` times the wave-1 tail (three families, lane C's
assembly question). It answers "did assembling the row natively help", and on
HG/20210721 the answer is no: 7.20 ms/row native against the oracle's 7.10.

That is not R6's shipped configuration. `QRDISC_WAVE2_FAMILIES` is: wave 1 plus
the prior-reaction family, both trade/event clocks, the volume clock and the
event-micro family — eight families, the combination the production path would
run. This tool times THAT against the frozen Python oracle on the same warmed
plane state, in the same process, with no profiler attached.

The number decides the off-2021 corpus scope, so it is measured, not recalled.

  OMP_NUM_THREADS=1 python3 tools/time_qrdisc_wave2.py --session HG/20210721
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "/workspace")

from engine.entry_v2.disc_native_builders import (  # noqa: E402
    capture_disc_session, discover_store_sessions,
)
from engine.entry_v2.qrdisc_native_loader import (  # noqa: E402
    QRDISC_WAVE1_FAMILIES, QRDISC_WAVE2_FAMILIES,
)

DEFAULT_REPORT = Path(
    "/workspace/artifacts/entry_v2/tabular_recovery/diagnostics/qrdisc_wave2_rate_20260823.json")


def _time_rows(fn, queries, warmup: int) -> float:
    for q in queries[:warmup]:
        fn(q)
    t0 = time.perf_counter()
    for q in queries:
        fn(q)
    return time.perf_counter() - t0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--session", default="HG/20210721")
    ap.add_argument("--rows", type=int, default=300)
    ap.add_argument("--warmup", type=int, default=20)
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    a = ap.parse_args(argv)

    sessions = discover_store_sessions()
    match = [s for s in sessions if s.label == a.session]
    if not match:
        raise SystemExit(f"session {a.session!r} not in the store; have "
                         f"{[s.label for s in sessions]}")
    session = match[0]
    capture = capture_disc_session(session, query_limit=a.rows)
    queries = capture.queries[:a.rows]

    from engine.entry_v2.qrdisc_native_loader import qrdisc_build_native_plane
    report = {"schema": "QRDISCWAVE2RATE1", "session": session.label,
              "identity_sha256": session.identity, "rows_timed": len(queries),
              "warmup_rows": a.warmup,
              "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    # Assembly is ON for the shipped end state: R6 ships every ported family
    # native AND the port assembling the row. Measuring wave 2 without it would
    # price a configuration the production path does not run.
    for name, families, assemble in (("oracle", (), False),
                                     ("wave1", QRDISC_WAVE1_FAMILIES, False),
                                     ("wave2_shipped", QRDISC_WAVE2_FAMILIES, True)):
        native, module, py_plane = qrdisc_build_native_plane(
            capture.construction, queries, families, assemble_natively=assemble)
        if assemble and not module.assembly_available(native):
            raise SystemExit("native assembly unavailable; the run would measure "
                             "the whole-map delegate and the number would be a lie")
        if families:
            fn = (lambda q, n=native, m=module: m.feature_map_row(n, **q))
        else:
            fn = (lambda q, pl=py_plane: pl.feature_map(**q))
        secs = _time_rows(fn, queries, a.warmup)
        report[name] = {"families": list(families), "assembled_natively": assemble,
                        "seconds": round(secs, 4),
                        "ms_per_row": round(1000 * secs / len(queries), 4)}
        print(f"{name:14s} {report[name]['ms_per_row']:8.4f} ms/row "
              f"({len(families)} native families)")
    base = report["oracle"]["ms_per_row"]
    for name in ("wave1", "wave2_shipped"):
        report[name]["speedup_vs_oracle"] = round(base / report[name]["ms_per_row"], 4)
        print(f"{name:14s} speedup {report[name]['speedup_vs_oracle']:.3f}x")
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(report, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
