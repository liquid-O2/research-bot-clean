#!/usr/bin/env python3
"""Adapt the installed OptMem CLI to Codex lifecycle hook JSON."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Sequence, TextIO


MEMO_CANDIDATES = (
    Path("/home/algo/.optmem/memo"),
    Path("/workspace/.optmem/memo"),
)
PYTHON_FALLBACK = Path("/usr/bin/python3")
HOOK_DEADLINE_SECONDS = 24.0
HEALTH_DEADLINE_SECONDS = 4.0
MAX_WAKE_CALLS = 32
NEXT_WAKE_RE = re.compile(
    r"^Not awake yet\. Run: .+? wake ([1-9][0-9]*) ([1-9][0-9]*)\s*$",
    re.MULTILINE,
)
PENDING_NAP_RE = re.compile(
    r'\ACompress memories #[0-9]+-[0-9]+ into one line of at most [0-9]+ bytes\.\n'
    r'Keep what has lasting effect, drop what does not\. Invent nothing\.\n\n'
    r'.+\nRun: .+? nap [0-9]+-[0-9]+ "<your line>"\n?\Z',
    re.DOTALL,
)


@dataclass(frozen=True)
class MemoResult:
    returncode: int
    output: str


def find_memo_executable() -> Path | None:
    """Return the first installed OptMem CLI without inspecting its memory."""
    return next((path for path in MEMO_CANDIDATES if path.is_file()), None)


def shebang_python_is_missing(result: MemoResult) -> bool:
    return (
        result.returncode == 127
        and "python3" in result.output
        and "No such file or directory" in result.output
    )


def run_process(command: Sequence[str], deadline: float) -> MemoResult:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return MemoResult(124, "OptMem lifecycle deadline expired.\n")
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=remaining,
        )
    except subprocess.TimeoutExpired as error:
        partial = error.stdout or ""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", errors="replace")
        return MemoResult(124, partial + "OptMem lifecycle command timed out.\n")
    return MemoResult(completed.returncode, completed.stdout)


def run_memo(memo: Path, arguments: Sequence[str], deadline: float) -> MemoResult:
    """Run OptMem directly, using Python only for a missing shebang interpreter."""
    try:
        direct = run_process((str(memo), *arguments), deadline)
    except FileNotFoundError:
        if not memo.is_file():
            raise
        return run_process((str(PYTHON_FALLBACK), str(memo), *arguments), deadline)
    if shebang_python_is_missing(direct):
        return run_process((str(PYTHON_FALLBACK), str(memo), *arguments), deadline)
    return direct


def session_start_context() -> str:
    memo = find_memo_executable()
    if memo is None:
        expected = ", ".join(str(path) for path in MEMO_CANDIDATES)
        return f"OptMem lifecycle error: no memo executable found; expected one of {expected}.\n"

    deadline = time.monotonic() + HOOK_DEADLINE_SECONDS
    arguments: tuple[str, ...] = ("wake",)
    outputs: list[str] = []
    seen: set[tuple[str, ...]] = set()
    for _ in range(MAX_WAKE_CALLS):
        if arguments in seen:
            outputs.append(f"OptMem lifecycle error: repeated wake arguments {arguments!r}.\n")
            break
        seen.add(arguments)
        result = run_memo(memo, arguments, deadline)
        outputs.append(result.output)
        if result.returncode != 0:
            break
        matches = list(NEXT_WAKE_RE.finditer(result.output))
        if not matches:
            break
        page, snapshot = matches[-1].groups()
        arguments = ("wake", page, snapshot)
    else:
        outputs.append(f"OptMem lifecycle error: wake exceeded {MAX_WAKE_CALLS} calls.\n")
    return "".join(outputs)


def pre_compact_response(stderr: TextIO) -> dict[str, object]:
    memo = find_memo_executable()
    if memo is None:
        stderr.write("OptMem precompact check skipped: memo executable not found.\n")
        return {}
    result = run_memo(
        memo,
        ("nap",),
        time.monotonic() + HOOK_DEADLINE_SECONDS,
    )
    if result.returncode == 0 and PENDING_NAP_RE.fullmatch(result.output):
        return {
            "continue": False,
            "stopReason": result.output,
            "systemMessage": result.output,
        }
    if result.returncode == 0 and result.output == "Nothing left to compress.\n":
        return {}
    stderr.write(
        "OptMem precompact check did not produce a recognized result "
        f"(exit {result.returncode}); compaction continues.\n"
    )
    return {}


def post_compact_health_check(stderr: TextIO) -> None:
    memo = find_memo_executable()
    if memo is None:
        stderr.write("OptMem postcompact health check skipped: memo executable not found.\n")
        return
    result = run_memo(
        memo,
        ("config",),
        time.monotonic() + HEALTH_DEADLINE_SECONDS,
    )
    if result.returncode != 0:
        stderr.write(
            "OptMem postcompact health check failed "
            f"(exit {result.returncode}); SessionStart source=compact still owns recall.\n"
        )


def write_hook_json(value: object, stdout: TextIO) -> None:
    json.dump(value, stdout, ensure_ascii=False)
    stdout.write("\n")


def main(
    argv: Sequence[str] | None = None,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    """Run one Codex lifecycle event."""
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    payload = json.load(stdin)
    if arguments == ("session-start",):
        if payload.get("hook_event_name") != "SessionStart":
            raise ValueError(
                "session-start expected hook_event_name='SessionStart', "
                f"got {payload.get('hook_event_name')!r}"
            )
        write_hook_json(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": session_start_context(),
                }
            },
            stdout,
        )
        return 0
    if arguments == ("pre-compact",):
        if payload.get("hook_event_name") != "PreCompact":
            raise ValueError(
                "pre-compact expected hook_event_name='PreCompact', "
                f"got {payload.get('hook_event_name')!r}"
            )
        write_hook_json(pre_compact_response(stderr), stdout)
        return 0
    if arguments == ("post-compact",):
        if payload.get("hook_event_name") != "PostCompact":
            raise ValueError(
                "post-compact expected hook_event_name='PostCompact', "
                f"got {payload.get('hook_event_name')!r}"
            )
        post_compact_health_check(stderr)
        write_hook_json({}, stdout)
        return 0
    raise ValueError(f"unknown lifecycle command {arguments!r}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
