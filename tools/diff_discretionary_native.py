#!/usr/bin/env python3
"""Standing differential gate for a native port of the discretionary plane.

WHY THIS EXISTS
    engine/entry_v2/discretionary_features.py is the frozen oracle for the
    per-row query path (`CausalDiscretionaryPlane.feature_map`,
    discretionary_features.py:2389).  The 145 strict-verified shards under
    artifacts/entry_v2/tabular_recovery/dense_store ARE its corpus: a native
    (C++) rebuild is acceptable only if it reproduces those float32 bytes
    exactly (D-017).  This tool is the acceptance instrument, and it is
    deliberately built and proven BEFORE the native code exists.

WHAT IS COMPARED
    Three things, all arrays: the float32 feature values (compared as uint32
    so a single flipped mantissa bit, a signed zero and a NaN payload all
    fail), the emitted feature NAME ORDER (order is identity for the dense
    store), and the row-identity columns.

WHAT IS NOT COMPARED, EVER
    The receipt STRINGS.  A shard's `feature_receipt_sha256` column and its
    `base_config_sha256` embed `implementation_sha256` (confirmation.py:
    168-176, roster entry confirmation.py:101), which hashes the Python source
    itself.  They MUST differ the moment a native builder replaces the Python
    path; comparing them would fail every correct port and pass no incorrect
    one.  Only values, names and row identity carry the contract.

BUILDERS
    `oracle`      the frozen Python path, re-evaluated cold from the recorded
                  session inputs.  Its job here is the red-first proof: it has
                  to reproduce its own stored bytes.
    `stub-store`  returns the stored shard bytes verbatim.  It stands in for
                  the future native module so the harness is testable NOW; it
                  consumes no inputs, so only the name-swap mutant can move it.
    A native builder registers in DISC_NATIVE_BUILDERS
    (engine/entry_v2/disc_native_builders.py) and needs no change here.

USAGE
    diff_discretionary_native.py --sessions 2-per-asset --builder oracle
    diff_discretionary_native.py --all-store --builder stub-store
    diff_discretionary_native.py --refusal-fixtures --builder oracle
    diff_discretionary_native.py --mutant trade-size --expect-fail \\
        --sessions 1-per-asset --builder oracle
    diff_discretionary_native.py --f64-probe --builder oracle
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Sequence

import numpy as np

# Same root the live dense driver uses (tools/run_tabular_recovery.py:20-21):
# the engine package must resolve to ONE module tree, or a monkeypatched class
# would be installed on a second copy of confirmation.py and record nothing.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.entry_v2.disc_native_builders import (  # noqa:E402
    DISC_NATIVE_BUILDERS, DISC_NATIVE_SOURCE_ROOT, DISC_NATIVE_STORE_ROOT,
    DiscSessionCapture, StoreSession, StoredShardView, capture_disc_session,
    compare_shard_identity_columns, discover_store_sessions, read_stored_shard,
    select_store_sessions, shard_view_of_result)
from engine.entry_v2.disc_native_differential import (  # noqa:E402
    DISC_NATIVE_DIFFERENTIAL_SCHEMA, BuiltFeatures,
    compare_disc_native_features, compare_disc_native_refusals,
    mutate_max_volume_trade_size, swap_disc_native_names)
from engine.entry_v2.disc_native_fixtures import (  # noqa:E402
    build_disc_refusal_fixtures, refusal_fixture_report, run_oracle_refusal)

DEFAULT_REPORT = Path("/workspace/artifacts/entry_v2/tabular_recovery/"
                      "diagnostics/disc_native_differential.json")
MUTANTS = ("trade-size", "name-swap")


def arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--builder", default="oracle",
                        choices=sorted(DISC_NATIVE_BUILDERS))
    parser.add_argument("--sessions", default="2-per-asset",
                        help="'N-per-asset'; the quota is filled "
                             "prior-absent-first where such a day exists")
    parser.add_argument("--all-store", action="store_true",
                        help="every session present in the dense store")
    parser.add_argument("--row-limit", type=int, default=None,
                        help="compare only the first N rows of each session; "
                             "recorded in the report so nothing is overstated")
    parser.add_argument("--mutant", choices=MUTANTS, default=None)
    parser.add_argument("--expect-fail", action="store_true",
                        help="required with --mutant: exit 0 only when the "
                             "comparator FAILED on every session")
    parser.add_argument("--refusal-fixtures", action="store_true")
    parser.add_argument("--f64-probe", action="store_true")
    parser.add_argument("--store-root", type=Path, default=DISC_NATIVE_STORE_ROOT)
    parser.add_argument("--source-root", type=Path, default=DISC_NATIVE_SOURCE_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    if args.mutant and not args.expect_fail:
        parser.error("--mutant requires --expect-fail: a mutant run that is "
                     "not asserted to fail proves nothing")
    if args.expect_fail and not args.mutant:
        parser.error("--expect-fail is only meaningful with --mutant")
    return args


def _truncate(built: BuiltFeatures, rows: int | None) -> BuiltFeatures:
    if rows is None:
        return built
    return BuiltFeatures(built.names, np.ascontiguousarray(built.matrix[:rows]),
                         built.snapshot_ts_ns[:rows], built.side[:rows])


def _store_precondition(
    capture: DiscSessionCapture, stored: StoredShardView,
) -> dict[str, object] | None:
    """Did the oracle still reproduce its own stored bytes, cold?

    This runs BEFORE any candidate is judged and is independent of the mutant,
    which is applied only to the candidate's inputs.  A FAIL here is a
    CRITICAL finding: the store would no longer be a usable acceptance corpus.
    """

    if capture.shard is None:
        return None
    fresh = shard_view_of_result(capture.shard)
    values = compare_disc_native_features(stored.full_view(), fresh.full_view())
    identity = compare_shard_identity_columns(stored, fresh)
    return {"status": "PASS" if values.passed and identity.passed else "FAIL",
            "full_matrix": values.as_json(),
            "identity_columns": identity.as_json()}


def _run_sessions(args: argparse.Namespace) -> dict[str, object]:
    builder = DISC_NATIVE_BUILDERS[args.builder]
    if args.mutant == "trade-size" and not builder.consumes_inputs:
        raise SystemExit(
            f"builder {builder.name!r} ignores its session inputs, so the "
            "trade-size mutant cannot reach it; use a builder that consumes "
            "inputs (e.g. oracle) or the name-swap mutant")
    discovered = discover_store_sessions(
        source_root=args.source_root, store_root=args.store_root)
    selected = select_store_sessions(
        discovered, "all-store" if args.all_store else args.sessions)
    rows: list[dict[str, object]] = []
    for session in selected:
        rows.append(_run_one_session(session, args, builder))
        print(f"{session.label} {rows[-1]['comparison']['status']}", flush=True)
    passed = sum(1 for row in rows if row["comparison"]["status"] == "PASS")
    return {
        "mode": "sessions",
        "coverage": {
            "store_sessions": len(discovered),
            "selected": len(selected),
            "prior_present": sum(1 for s in selected if s.prior_present),
            "prior_absent": sum(1 for s in selected if not s.prior_present),
        },
        "sessions": rows,
        "summary": {"sessions": len(rows), "passed": passed,
                    "failed": len(rows) - passed},
    }


def _mutant_visibility(
    capture: DiscSessionCapture, receipt: dict[str, int],
) -> dict[str, int]:
    """Can the compared rows even see the mutated trade?

    The disc plane is prefix-causal: a snapshot at session second S folds in
    trades up to S and nothing after.  If the mutated trade lands after every
    compared row, the oracle is RIGHT to return unchanged bytes and the run
    would report MUTANT_MISSED for a reason that has nothing to do with the
    comparator.  Observed 2026-08-21 on SI/20210624 under --row-limit 500: the
    busiest tick trades at second 47144, the compared rows cover 23748-29896,
    and the correct PASS read as a missed mutant.  The run is refused instead.

    Note the compared window is not the session's first N seconds: rows are
    emitted per candidate series, so their snapshot seconds are not monotone.
    """

    rows = np.asarray(capture.construction["rows"])
    open_ns = int(capture.construction["open_ns"])
    mutated_sec = int(rows["receive_session_sec"][receipt["mutated_row_index"]])
    seconds = [(int(query["snapshot_ts_ns"]) - open_ns) // 1_000_000_000
               for query in capture.queries]
    visibility = {"mutated_event_session_sec": mutated_sec,
                  "compared_snapshot_sec_min": int(min(seconds)),
                  "compared_snapshot_sec_max": int(max(seconds))}
    if mutated_sec > max(seconds):
        raise SystemExit(
            "trade-size mutant cannot be observed on this selection: the "
            f"mutated trade is at session second {mutated_sec} but the "
            f"compared rows end at second {max(seconds)}, so every compared "
            "row's causal prefix excludes it.  Drop --row-limit and compare "
            "the whole session.")
    return visibility


def _run_one_session(
    session: StoreSession, args: argparse.Namespace, builder,
) -> dict[str, object]:
    started = time.perf_counter()
    stored = read_stored_shard(session.artifact_path)
    capture = DiscSessionCapture()
    mutant_receipt: dict[str, object] = {}
    if builder.consumes_inputs:
        capture = capture_disc_session(session, query_limit=args.row_limit)
        if args.mutant == "trade-size":
            mutated, mutant_receipt = mutate_max_volume_trade_size(
                np.asarray(capture.construction["rows"]),
                raw_tick=int(capture.construction["raw_tick"]))
            mutant_receipt.update(_mutant_visibility(capture, mutant_receipt))
            capture.construction["rows"] = mutated
    candidate = builder.build(capture, stored)
    if args.mutant == "name-swap":
        candidate = swap_disc_native_names(candidate)
        mutant_receipt = {"swapped_names": [candidate.names[0],
                                            candidate.names[1]]}
    reference = _truncate(stored.disc_view(), args.row_limit)
    candidate = _truncate(candidate, args.row_limit)
    verdict = compare_disc_native_features(reference, candidate)
    return {
        "session": session.label,
        "identity_sha256": session.identity,
        "artifact_path": str(session.artifact_path),
        "prior_present": session.prior_present,
        "rows_compared": int(reference.matrix.shape[0]),
        "disc_columns": len(reference.names),
        "store_columns": len(stored.names),
        "store_precondition": _store_precondition(capture, stored),
        "mutant_receipt": mutant_receipt,
        "comparison": verdict.as_json(),
        "seconds": round(time.perf_counter() - started, 3),
    }


def _run_refusal_fixtures(args: argparse.Namespace) -> dict[str, object]:
    """Both paths, side by side, on hand-built inputs at six refusal sites."""

    builder = DISC_NATIVE_BUILDERS[args.builder]
    discovered = discover_store_sessions(
        source_root=args.source_root, store_root=args.store_root)
    session = next(s for s in select_store_sessions(discovered, "1-per-asset")
                   if s.prior_present)
    capture = capture_disc_session(session, query_limit=1)
    fixtures = build_disc_refusal_fixtures(capture, session)
    oracle = tuple(run_oracle_refusal(fixture) for fixture in fixtures)
    # No registered builder owns an independent refusal path yet, so the
    # candidate side re-runs the oracle.  That parity is VACUOUS and is
    # flagged as such; it becomes real evidence the day a native builder
    # registers its own refusal entry point.
    candidate = oracle
    rows = refusal_fixture_report(fixtures, oracle, candidate)
    for row, fixture, observed, other in zip(rows, fixtures, oracle, candidate):
        against_hand = compare_disc_native_refusals(fixture.expected, observed)
        against_candidate = compare_disc_native_refusals(observed, other)
        row["oracle_vs_hand_written"] = against_hand.as_json()
        row["candidate_vs_oracle"] = against_candidate.as_json()
        row["status"] = ("PASS" if against_hand.passed and against_candidate.passed
                         else "FAIL")
        print(f"{row['fixture']} {row['status']} "
              f"{observed.exception_type}: {observed.message}", flush=True)
    passed = sum(1 for row in rows if row["status"] == "PASS")
    return {
        "mode": "refusal-fixtures",
        "fixture_session": session.label,
        "candidate_builder": builder.name,
        "vacuous_candidate_parity": True,
        "vacuous_reason": "no registered builder implements an independent "
                          "refusal path yet; the candidate column re-runs the "
                          "oracle",
        "fixtures": rows,
        "summary": {"fixtures": len(rows), "passed": passed,
                    "failed": len(rows) - passed},
    }


def _run_f64_probe(args: argparse.Namespace) -> dict[str, object]:
    """Advisory pre-cast comparison; inert until a second float64 emitter exists.

    The stored bytes are float32 (cast at confirmation.py:1856).  When a native
    builder disagrees, the useful question is whether it disagreed BEFORE the
    cast — a float64 divergence points at the arithmetic, a float32-only one at
    rounding.  Answering it needs two implementations that both emit their
    pre-cast float64 values; today only the oracle can, and comparing the
    oracle against itself would be a mirror assertion.  A builder opts in by
    setting `emits_float64=True` in its registry entry.
    """

    builder = DISC_NATIVE_BUILDERS[args.builder]
    return {
        "mode": "f64-probe",
        "status": "UNAVAILABLE",
        "reason": f"builder {builder.name!r} does not emit pre-cast float64 "
                  "values (emits_float64=False); the f64 probe needs a second "
                  "implementation to compare against and refuses to compare "
                  "the oracle with itself",
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = arguments(argv)
    builder = DISC_NATIVE_BUILDERS[args.builder]
    if args.refusal_fixtures:
        body = _run_refusal_fixtures(args)
    elif args.f64_probe:
        body = _run_f64_probe(args)
    else:
        body = _run_sessions(args)
    failed = int(body.get("summary", {}).get("failed", 0))
    total = int(body.get("summary", {}).get("sessions",
                body.get("summary", {}).get("fixtures", 0)))
    if args.f64_probe:
        status, code = "UNAVAILABLE", 3
    elif args.mutant:
        observed = total > 0 and failed == total
        status = "MUTANT_OBSERVED" if observed else "MUTANT_MISSED"
        code = 0 if observed else 2
    else:
        status = "PASS" if total > 0 and failed == 0 else "FAIL"
        code = 0 if status == "PASS" else 2
    report = {
        "schema": DISC_NATIVE_DIFFERENTIAL_SCHEMA,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "builder": builder.name,
        "builder_note": builder.note,
        "mutant": args.mutant,
        "expect_fail": bool(args.expect_fail),
        "row_limit": args.row_limit,
        "store_root": str(args.store_root),
        "status": status,
        "exit_code": code,
        **body,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"STATUS {status} exit={code} report={args.report}", flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
