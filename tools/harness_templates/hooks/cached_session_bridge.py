#!/usr/bin/env python3
"""Forward hook commands cached by one live Codex session to new owners."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from typing import Sequence, TextIO


PYTHON_PATH = Path("/usr/bin/python3")
NEW_ADAPTER_PATH = Path("/workspace/.codex/hooks/optmem_lifecycle.py")
NODE_PATH = Path(
    "/home/algo/.local/share/fnm/node-versions/v24.19.0/installation/bin/node"
)
UNLAZY_STOP_PATH = Path(
    "/workspace/vendor/agent-sources/unlazy/"
    "754d9a68109e39b836cc72a39fb9a823f9d6b613/scripts/stop-hook.mjs"
)
SESSIONSTART_TIMEOUT_SECONDS = 19.0
STOP_TIMEOUT_SECONDS = 14.0
LIFECYCLE_ROUTES = {
    "sessionstart": ("session-start", SESSIONSTART_TIMEOUT_SECONDS),
    "wake": ("session-start", SESSIONSTART_TIMEOUT_SECONDS),
    "precompact": ("pre-compact", 29.0),
    "postcompact": ("post-compact", 19.0),
}
NOOP_VERBS = frozenset({"userprompt", "pretooluse", "subagentstart", "sessionend"})


def forward_hook_process(
    command: Sequence[str],
    payload: str,
    timeout: float,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    try:
        result = subprocess.run(
            command,
            input=payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        stderr.write(f"cached session bridge could not run {command[0]!r}: {error}.\n")
        return 1
    stdout.write(result.stdout)
    stderr.write(result.stderr)
    return result.returncode


def main(
    argv: Sequence[str] | None = None,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    route = LIFECYCLE_ROUTES.get(arguments[0]) if len(arguments) == 1 else None
    if route is not None:
        target_verb, timeout = route
        return forward_hook_process(
            (str(PYTHON_PATH), str(NEW_ADAPTER_PATH), target_verb),
            stdin.read(),
            timeout,
            stdout,
            stderr,
        )
    if arguments == ("stop",):
        return forward_hook_process(
            (str(NODE_PATH), str(UNLAZY_STOP_PATH), "--unlazy"),
            stdin.read(),
            STOP_TIMEOUT_SECONDS,
            stdout,
            stderr,
        )
    if len(arguments) == 1 and arguments[0] in NOOP_VERBS:
        return 0
    stderr.write(f"cached session bridge does not recognize {arguments!r}.\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
