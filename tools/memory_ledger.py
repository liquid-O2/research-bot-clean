#!/usr/bin/env python3
"""Append-only markdown memory for every agent working in this repository.

Replaces OptMem as primary memory (D-101 amendment). OptMem stays installed and
callable, but nothing gates on it, because its PreCompact hook refused
compaction while a compression was pending and deadlocked a full session.

This ledger has no compression step by design. There is no chore that can block
a session, and no state a hook has to settle before work continues.

Every new `note` line passes the unslop lint before it lands. Imported history
is exempt: those lines are the record of what earlier sessions wrote, and
rewriting them would falsify it.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
import sys
from typing import Sequence, TextIO

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ROOT / "engine/entry_v2"))

from pod_local_lock import pod_local_flock  # noqa: E402
from unslop_lint import format_finding, lint_text, read_allowlist  # noqa: E402

LEDGER_PATH = ROOT / "MEMORY.md"
LEDGER_HEADING = "## Ledger"
IMPORTED_HEADING = "## Imported history"
CHECKPOINT_HEADING = "## Checkpoints"
ENTRY = re.compile(r"^- (\d{4}-\d{2}-\d{2}) #(\d+) (.*)$")
INDEX_TOKEN = re.compile(r"#(\d+)\b")
MAX_ENTRY_BYTES = 280
DEFAULT_TAIL = 40


def ledger_path() -> Path:
    """Return the ledger location, overridable for tests."""
    configured = os.environ.get("MEMORY_LEDGER_PATH")
    return Path(configured) if configured else LEDGER_PATH


def read_lines(path: Path) -> list[str]:
    """Read the ledger as lines, or raise a message naming the missing file."""
    if not path.is_file():
        raise ValueError(f"memory ledger is missing, expected {path}")
    return path.read_text(encoding="utf-8").splitlines()


def heading_index(lines: Sequence[str], heading: str) -> int:
    """Return the line number of a required section heading."""
    for index, line in enumerate(lines):
        if line.strip() == heading:
            return index
    raise ValueError(f"ledger is missing its {heading!r} section")


def next_index(lines: Sequence[str]) -> int:
    """Return one past the highest entry number anywhere in the ledger."""
    numbers = [int(match) for line in lines for match in INDEX_TOKEN.findall(line)]
    return max(numbers) + 1 if numbers else 0


def insertion_point(lines: Sequence[str]) -> int:
    """Return the line where a new ledger entry belongs, after the last one.

    Imported history sits above the live ledger so that file order stays
    chronological and `tail` means what it says.
    """
    start = heading_index(lines, LEDGER_HEADING)
    end = heading_index(lines, CHECKPOINT_HEADING)
    body = range(start + 1, end)
    entries = [index for index in body if ENTRY.match(lines[index])]
    return entries[-1] + 1 if entries else last_filled(lines, body) + 1


def last_filled(lines: Sequence[str], body: range) -> int:
    """Return the last non-blank line of a section, or the heading above it."""
    filled = [index for index in body if lines[index].strip()]
    return filled[-1] if filled else body.start - 1


def today() -> str:
    """Return the UTC date stamp used by every entry."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def validate_note(text: str) -> str:
    """Reject an empty, multi-line, oversized, or unslopped memory line."""
    line = text.strip()
    if not line or "\n" in line:
        raise ValueError(f"a memory is one non-empty line, got {text!r}")
    size = len(line.encode("utf-8"))
    if size > MAX_ENTRY_BYTES:
        raise ValueError(f"a memory is at most {MAX_ENTRY_BYTES} bytes, got {size}")
    findings = lint_text(line, "<memory>", read_allowlist())
    if findings:
        detail = "\n".join(format_finding(row) for row in findings)
        raise ValueError(f"unslop rejected this memory line.\n{detail}")
    return line


def append_note(text: str, path: Path) -> str:
    """Validate and append one memory, returning the rendered entry."""
    line = validate_note(text)
    with pod_local_flock(path):
        lines = read_lines(path)
        entry = f"- {today()} #{next_index(lines)} {line}"
        lines.insert(insertion_point(lines), entry)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return entry


def append_checkpoint(body: str, path: Path) -> str:
    """Append a compaction checkpoint. Never linted, never able to block."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    block = f"\n### {stamp}\n\n{body.rstrip()}\n"
    with pod_local_flock(path):
        lines = read_lines(path)
        heading_index(lines, CHECKPOINT_HEADING)
        path.write_text("\n".join(lines).rstrip("\n") + "\n" + block, encoding="utf-8")
    return block


def ledger_entries(lines: Sequence[str]) -> list[str]:
    """Return every entry line, live and imported, in file order."""
    return [line for line in lines if ENTRY.match(line)]


def tail(count: int, path: Path) -> list[str]:
    """Return the most recent entries, newest last."""
    entries = ledger_entries(read_lines(path))
    return entries[-count:] if count > 0 else entries


def recall(expression: str, path: Path) -> list[str]:
    """Return every line matching a regular expression, case-insensitively."""
    pattern = re.compile(expression, re.IGNORECASE)
    return [line for line in read_lines(path) if pattern.search(line)]


def run_note(arguments: Sequence[str], stdout: TextIO, path: Path) -> int:
    """Handle `note "<line>"`."""
    if len(arguments) != 1:
        raise ValueError('note takes one quoted line, got ' f'{list(arguments)!r}')
    stdout.write(append_note(arguments[0], path) + "\n")
    return 0


def run_tail(arguments: Sequence[str], stdout: TextIO, path: Path) -> int:
    """Handle `tail [count]`."""
    count = int(arguments[0]) if arguments else DEFAULT_TAIL
    stdout.writelines(line + "\n" for line in tail(count, path))
    return 0


def run_recall(arguments: Sequence[str], stdout: TextIO, path: Path) -> int:
    """Handle `recall <regex>`."""
    if len(arguments) != 1:
        raise ValueError(f"recall takes one regular expression, got {list(arguments)!r}")
    matches = recall(arguments[0], path)
    stdout.writelines(line + "\n" for line in matches)
    return 0 if matches else 1


def run_checkpoint(arguments: Sequence[str], stdout: TextIO, path: Path) -> int:
    """Handle `checkpoint <body>`, or read the body from stdin when omitted."""
    body = arguments[0] if arguments else sys.stdin.read()
    stdout.write(append_checkpoint(body, path))
    return 0


COMMANDS = {"note": run_note, "tail": run_tail,
            "recall": run_recall, "checkpoint": run_checkpoint}
USAGE = "usage: memory_ledger.py {note|tail|recall|checkpoint} [argument]"


def main(argv: Sequence[str] | None = None, stdout: TextIO = sys.stdout) -> int:
    """Dispatch one ledger command."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] not in COMMANDS:
        raise ValueError(f"{USAGE}, got {arguments!r}")
    return COMMANDS[arguments[0]](arguments[1:], stdout, ledger_path())


def cli(stderr: TextIO = sys.stderr) -> int:
    """Run one command, reporting a rejected memory without a traceback."""
    try:
        return main()
    except (ValueError, OSError) as error:
        stderr.write(f"memory_ledger: {error}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(cli())
