#!/usr/bin/env python3
"""Run every canary against one installed guard, and report what it decided.

Unit tests prove a function returns a value. A canary drives the installed hook
the way the client drives it and checks the verdict the agent would receive, so
a failure names the law that stopped being enforced rather than a line number.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Sequence, TextIO

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from canary_driver import (  # noqa: E402
    CLIENTS,
    Canary,
    Outcome,
    ROOT,
    drop_method_scopes,
    engage,
    read_verdict,
    run_guard,
    select,
    select_client,
    write_payload,
)
from method_canaries import (  # noqa: E402
    DONE_SCOPE,
    OPEN_SCOPE,
    all_canaries,
    drop_probe,
    drop_scope,
    engaged,
    write_scope,
)

def run_one(canary: Canary, state_root: Path) -> Outcome:
    """Run one canary in a fresh session state."""
    state = state_root / canary.name.replace(" ", "-")[:60]
    state.mkdir(parents=True, exist_ok=True)
    if canary.setup is not None:
        canary.setup(state)
    elif canary.scope:
        engaged(state, canary.scope)
    verdict, reason = read_verdict(
        run_guard(canary.verb, canary.payload, state, canary.scope))
    return Outcome(canary, verdict, reason)


def packet_outcome(state_root: Path) -> Outcome:
    """Check engage prints the exact sources with digests that match the files."""
    state = state_root / "engage-packet"
    state.mkdir(parents=True, exist_ok=True)
    select(state, "implement-flow")
    result = engage(state)
    canary = Canary("engage prints every source with a matching digest", "engage", {}, "allow")
    if result.returncode != 0:
        return Outcome(canary, "error", result.stderr.strip())
    return Outcome(canary, *verify_packet(result.stdout))


def verify_json_packet(packet: dict[str, object]) -> tuple[str, str]:
    """Check every packet source matches the bytes on disk."""
    sources = packet["method_packet"]["sources"]  # type: ignore[index]
    for row in sources:  # type: ignore[union-attr]
        raw = Path(str(row["path"])).read_bytes()
        if sha256(raw).hexdigest() != row["sha256"] or raw.decode() != row["content"]:
            return "error", f"packet source {row['name']} does not match its file"
    return "allow", f"{len(sources)} sources verified"  # type: ignore[arg-type]


SOURCE_BLOCK = re.compile(
    r"<<<METHOD_SOURCE_START name=([^ ]+) path=(.*?) sha256=([0-9a-f]{64})>>>\n"
    r"(.*?)\n<<<METHOD_SOURCE_END name=\1 sha256=\3>>>", re.DOTALL)


def verify_text_packet(packet: str) -> tuple[str, str]:
    rows = SOURCE_BLOCK.findall(packet)
    if not rows:
        return "error", "direct packet has no source blocks"
    for name, path, digest, content in rows:
        raw = Path(path).read_bytes()
        if sha256(raw).hexdigest() != digest or raw.decode() != content:
            return "error", f"packet source {name} does not match its file"
    prefix, marker = packet.rsplit("<<<METHOD_PACKET_END sha256=", 1)
    if sha256(prefix.encode()).hexdigest() != marker.removesuffix(">>>"):
        return "error", "method packet digest does not match its contents"
    return "allow", f"{len(rows)} sources verified"


def verify_packet(packet: str) -> tuple[str, str]:
    if packet.lstrip().startswith("{"):
        return verify_json_packet(json.loads(packet))
    return verify_text_packet(packet)


def unchanged_outcome(state_root: Path) -> Outcome:
    """Check a denied write leaves its target byte-identical."""
    from hashlib import sha256
    target = ROOT / "engine/canary_untouched.py"
    canary = Canary("a denied write leaves the target unchanged", "pre-tool-use", {}, "allow")
    if target.exists():
        return Outcome(canary, "error", f"{target} already exists")
    state = state_root / "unchanged"
    state.mkdir(parents=True, exist_ok=True)
    select(state, "implement-flow")
    engage(state)
    before = sorted(p.name for p in target.parent.iterdir())
    run_guard("pre-tool-use", write_payload(str(target)), state)
    after = sorted(p.name for p in target.parent.iterdir())
    digest = sha256(str(after).encode()).hexdigest()[:12]
    if before != after or target.exists():
        return Outcome(canary, "error", "the denied write created a file")
    return Outcome(canary, "allow", f"directory listing unchanged ({digest})")


def report(outcomes: Sequence[Outcome], stdout: TextIO) -> int:
    """Print one line per canary and a verdict for the run."""
    for outcome in outcomes:
        mark = "ok  " if outcome.passed else "FAIL"
        stdout.write(f"{mark} {outcome.canary.name}\n")
        if not outcome.passed:
            stdout.write(f"       expected={outcome.canary.expect!r} "
                         f"got={outcome.verdict!r} reason={outcome.reason[:160]!r}\n")
    failures = [row for row in outcomes if not row.passed]
    if failures:
        stdout.write(f"\nCANARIES FAIL {len(failures)} of {len(outcomes)}\n")
        return 1
    stdout.write(f"\nCANARIES PASS {len(outcomes)} checks\n")
    return 0


def run_all(client: object, stdout: TextIO) -> int:
    """Run every canary in a throwaway state, then clean up whatever it made."""
    state_root = Path(tempfile.mkdtemp(prefix="method-canaries-"))
    write_scope(OPEN_SCOPE, met=False)
    write_scope(DONE_SCOPE, met=True)
    try:
        outcomes = [run_one(canary, state_root) for canary in all_canaries()]
        outcomes.append(packet_outcome(state_root))
        outcomes.append(unchanged_outcome(state_root))
        stdout.write(f"client: {getattr(client, 'name', '?')} "
                     f"guard: {getattr(client, 'guard', '?')}\n")
        return report(outcomes, stdout)
    finally:
        drop_method_scopes()
        shutil.rmtree(state_root, ignore_errors=True)
        drop_scope(OPEN_SCOPE)
        drop_scope(DONE_SCOPE)
        drop_probe()


def main(argv: Sequence[str] | None = None, stdout: TextIO = sys.stdout) -> int:
    """Run every canary against one installed guard."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    name = arguments[1] if len(arguments) > 1 and arguments[0] == "--client" else "claude"
    if name not in CLIENTS:
        raise ValueError(f"unknown client {name!r}, expected one of {sorted(CLIENTS)}")
    client = select_client(name)
    if not client.guard.is_file():
        raise ValueError(f"no installed guard at {client.guard}")
    return run_all(client, stdout)


if __name__ == "__main__":
    raise SystemExit(main())
