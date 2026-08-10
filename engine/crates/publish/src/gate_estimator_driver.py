#!/usr/bin/env python3
"""Gate-verifier estimator driver -- NOT the pinned law file itself.

`crate::gate::StageGate` (A1: "the verifier recomputes the LCB via the
pinned estimator and requires exact unrounded agreement with the published
gate result") shells out to `python3 <this file> <estimator_laws.py path>
<session_recall.tsv path>`. This driver never re-implements or modifies
`year_stratified_session_block_lcb`: it sha-verifies (in Rust, before
invoking this script) and then dynamically loads the pinned
`estimator_laws.py` by path and calls its frozen function verbatim on the
sessions parsed from the published `session_recall.tsv` (A1's exact
schema: `year, ordinal, hits, truths`, header then one data row per
session).

Stdout contract (exactly two lines on success, nothing else):
  1. `repr(lcb)` -- Python's own canonical shortest round-tripping decimal
     string for the float, e.g. `0.7959869969734334`. Never scientific
     notation for any realistic LCB value in [0, 1]; this driver refuses
     (nonzero exit) rather than emit one, since
     `metrics::bank::validate_lcb_canonical`'s registered grammar excludes
     exponent notation.
  2. `PASS` if `lcb >= 0.80` else `FAIL` -- the estimator's own inclusive
     floor decision (mirrors `metrics::bank::EstimatorVerdict::passes_floor`).

Any estimator error (fail-closed binding-point refusal, malformed input,
etc.) is printed to stderr and this script exits nonzero -- the caller
(Rust) treats that as a hard verification failure, never a silent pass.
"""
from __future__ import annotations

import importlib.util
import sys


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(
            "usage: gate_estimator_driver.py <estimator_laws.py> <session_recall.tsv>",
            file=sys.stderr,
        )
        return 2
    estimator_path, session_recall_path = argv[1], argv[2]

    spec = importlib.util.spec_from_file_location("estimator_laws", estimator_path)
    if spec is None or spec.loader is None:
        print(f"could not load estimator module from {estimator_path}", file=sys.stderr)
        return 2
    estimator_laws = importlib.util.module_from_spec(spec)
    # Register the module under its own name BEFORE executing it: the
    # pinned file uses module-level `@dataclass(frozen=True)` decorators,
    # and CPython's dataclasses implementation resolves type hints via
    # `sys.modules[cls.__module__]` while the class body executes -- if the
    # module is not yet registered, that lookup returns `None` and
    # dataclass construction raises. This registration is a Python import
    # mechanics requirement, not a modification of the pinned file itself.
    sys.modules["estimator_laws"] = estimator_laws
    spec.loader.exec_module(estimator_laws)

    sessions = []
    try:
        with open(session_recall_path, "r", encoding="utf-8") as handle:
            header = handle.readline()
            if header.rstrip("\n") != "year\tordinal\thits\ttruths":
                print(
                    f"unexpected session_recall.tsv header: {header!r}",
                    file=sys.stderr,
                )
                return 2
            for line_number, line in enumerate(handle, start=2):
                line = line.rstrip("\n")
                if line == "":
                    continue
                fields = line.split("\t")
                if len(fields) != 4:
                    print(
                        f"session_recall.tsv line {line_number}: expected 4 columns, "
                        f"got {len(fields)}",
                        file=sys.stderr,
                    )
                    return 2
                year_s, ordinal_s, hits_s, truths_s = fields
                sessions.append(
                    estimator_laws.SessionRecall(
                        int(year_s), int(ordinal_s), int(hits_s), int(truths_s)
                    )
                )
    except OSError as error:
        print(f"could not read session_recall.tsv: {error}", file=sys.stderr)
        return 2

    try:
        lcb = estimator_laws.year_stratified_session_block_lcb(sessions)
    except Exception as error:  # noqa: BLE001 -- any estimator failure is a hard verifier error
        print(f"estimator error: {error}", file=sys.stderr)
        return 1

    canonical = repr(lcb)
    if "e" in canonical or "E" in canonical or "n" in canonical.lower():
        # "n" catches nan/inf spellings; the registered canonical grammar
        # (metrics::bank::validate_lcb_canonical) is plain digits/'.'/'-'
        # only.
        print(f"non-canonical lcb repr, refusing to publish it: {canonical}", file=sys.stderr)
        return 1

    print(canonical)
    print("PASS" if lcb >= 0.80 else "FAIL")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
