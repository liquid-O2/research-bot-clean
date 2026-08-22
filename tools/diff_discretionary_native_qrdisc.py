#!/usr/bin/env python3
"""Run the stage-1 differential gate against the qrdisc native builder.

WHY A WRAPPER AND NOT AN EDIT
    tools/diff_discretionary_native.py builds its --builder choices from
    DISC_NATIVE_BUILDERS at argument-parse time (line 82-83), so a builder that
    registers later is invisible to it.  Registering it here, BEFORE main() is
    called, makes the existing tool work unchanged — and the stage-1 harness
    (proven: oracle-vs-store bit-identical on 3 sessions, both mutants observed,
    6/6 refusal fixtures) stays byte-for-byte the code that was proven.

USAGE
    diff_discretionary_native_qrdisc.py --builder qrdisc-native-wave2 \
        --sessions 1-per-asset
    Any flag of the underlying tool is accepted.  `--builder` is REQUIRED
    (R6 F3): the wrapper used to default to the skeleton builder, so a run that
    forgot the flag produced a green receipt for the boundary-only builder and
    read as evidence for whichever wave the operator meant.  `--report` defaults
    to a builder-suffixed path so two builders can never overwrite each other's
    receipt.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.entry_v2.qrdisc_native_loader import (  # noqa:E402
    qrdisc_register_builder)

QRDISC_REPORT_DIRECTORY = Path(
    "/workspace/artifacts/entry_v2/tabular_recovery/diagnostics")


def qrdisc_selected_builder(arguments: Sequence[str]) -> str | None:
    """The `--builder` value on this command line, or None if absent."""

    selected: str | None = None
    for position, argument in enumerate(arguments):
        if argument == "--builder" and position + 1 < len(arguments):
            selected = arguments[position + 1]
        elif argument.startswith("--builder="):
            selected = argument.split("=", 1)[1]
    return selected


def main(argv: Sequence[str] | None = None) -> int:
    qrdisc_register_builder()
    import tools.diff_discretionary_native as gate  # noqa:E402 - after register

    arguments = list(sys.argv[1:] if argv is None else argv)
    # `--session-label HG/20210621`: the underlying gate selects only by
    # `N-per-asset` or `all-store`, and the full-session receipt for ONE named
    # session (the deep gate, ~72k rows) has no selector.  Filtering the
    # discovered list leaves the comparator, the capture and the report writer
    # byte-for-byte the proven code; the chosen session is named in the report.
    if "--session-label" in arguments:
        position = arguments.index("--session-label")
        label = arguments[position + 1]
        del arguments[position:position + 2]
        discover = gate.select_store_sessions
        gate.select_store_sessions = (
            lambda sessions, selector: tuple(
                session for session in discover(sessions, "all-store")
                if session.label == label))
    builder = qrdisc_selected_builder(arguments)
    if builder is None:
        # Derived from the registry the call above just filled, never a second
        # hand-kept list: a builder added to the loader appears here for free.
        registered = sorted(name for name in gate.DISC_NATIVE_BUILDERS
                            if name.startswith("qrdisc-"))
        print("diff_discretionary_native_qrdisc.py: --builder is REQUIRED; "
              "registered qrdisc builders are " + ", ".join(registered),
              file=sys.stderr)
        return 2
    if not any(argument.startswith("--report") for argument in arguments):
        arguments += ["--report", str(
            QRDISC_REPORT_DIRECTORY /
            f"disc_native_differential_qrdisc_{builder}.json")]
    return gate.main(arguments)


if __name__ == "__main__":
    sys.exit(main())
