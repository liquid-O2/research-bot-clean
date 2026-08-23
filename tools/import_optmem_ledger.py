#!/usr/bin/env python3
"""Build MEMORY.md once from the OptMem store, losslessly and idempotently.

Every OptMem entry and every node of its summary tree lands verbatim under
`## Imported history`. Those lines were written before the unslop discipline
existed, so the lint exempts them: they are the record of what earlier sessions
wrote, and rewriting them would falsify it.

Re-running this rebuilds the imported section and leaves the live ledger and the
checkpoints untouched, so a retry converges instead of duplicating.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys
from typing import Sequence, TextIO

OPTMEM = Path.home() / ".optmem/memory"
LEDGER = Path(__file__).resolve().parent.parent / "MEMORY.md"
ENTRY = re.compile(r"^#(\d+) (\d{4}-\d{2}-\d{2}) (.*)$")
TREE_SPANS = (128, 64, 32, 16, 8, 4, 2)
IGNORE_START = "<!-- unslop:ignore-start -->"
IGNORE_END = "<!-- unslop:ignore-end -->"

PREAMBLE = """# Memory

Primary durable memory for every agent working in this repository. Append-only,
tracked in Git, and read at the start of every session.

Add a line whenever something lasting happens. A decision you made, a fact the
user taught you, a result that closes a question, an event with lasting effect.

    python3 tools/memory_ledger.py note "<one line, 280 bytes max>"
    python3 tools/memory_ledger.py tail 40
    python3 tools/memory_ledger.py recall '<regex>'

Every new line passes `tools/unslop_lint.py` before it lands. There is no
compression step, so no memory chore can ever block a session or a compaction.

OptMem stays installed and callable at `~/.optmem/memo`, but nothing gates on
it. Its history is imported below.
"""
IMPORT_NOTE = """## Imported history

Verbatim from OptMem, entries #0 to #185 plus every node of its summary tree.
Exempt from the unslop lint because it is a record, not new writing.
"""
TREE_NOTE = """### OptMem summary tree

Each line summarises a span of the entries above. Span 128 is the whole history
in one line; span 2 is the finest pairing OptMem built.
"""
LEDGER_NOTE = """## Ledger

New memories land here, newest last.
"""
CHECKPOINT_NOTE = """## Checkpoints

Written by the PreCompact hook so a compaction loses nothing. Newest last.
"""


def read_entries(store: Path) -> list[str]:
    """Return every OptMem entry rendered in ledger format."""
    raw = (store / "LOG.txt").read_text(encoding="utf-8").splitlines()
    matches = (ENTRY.match(line.rstrip()) for line in raw)
    return [f"- {row.group(2)} #{row.group(1)} {row.group(3).rstrip()}"
            for row in matches if row is not None]


def read_tree_span(store: Path, span: int) -> list[str]:
    """Return one summary level, labelled with the entry range each line covers."""
    path = store / f"TREE/{span}"
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [f"- #{index * span}-{index * span + span - 1} {line.rstrip()}"
            for index, line in enumerate(lines) if line.strip()]


def tree_sections(store: Path) -> list[str]:
    """Return every summary level, coarsest first."""
    blocks: list[str] = []
    for span in TREE_SPANS:
        rows = read_tree_span(store, span)
        if rows:
            blocks.append(f"#### Span {span}\n\n" + "\n".join(rows) + "\n")
    return blocks


def imported_section(store: Path) -> str:
    """Render the whole imported block, fenced by the lint ignore markers."""
    entries = "\n".join(read_entries(store))
    parts = [IMPORT_NOTE, IGNORE_START, "", "### Entries", "", entries, "",
             TREE_NOTE, *tree_sections(store), IGNORE_END]
    return "\n".join(parts)


def existing_section(text: str, heading: str, following: str) -> str:
    """Return one section of an existing ledger, so a rebuild preserves it."""
    start = text.find(heading)
    if start < 0:
        return ""
    end = text.find(following, start + len(heading))
    return text[start:end if end > 0 else len(text)].rstrip() + "\n"


def preserved(path: Path) -> tuple[str, str]:
    """Return the live ledger and checkpoint sections of an existing file."""
    if not path.is_file():
        return LEDGER_NOTE, CHECKPOINT_NOTE
    text = path.read_text(encoding="utf-8")
    ledger = existing_section(text, "## Ledger", "## Checkpoints") or LEDGER_NOTE
    checkpoints = existing_section(text, "## Checkpoints", "\0") or CHECKPOINT_NOTE
    return ledger, checkpoints


def build(store: Path, path: Path) -> str:
    """Render the whole ledger file."""
    ledger, checkpoints = preserved(path)
    return "\n".join([PREAMBLE, imported_section(store), ledger, checkpoints])


def main(argv: Sequence[str] | None = None, stdout: TextIO = sys.stdout) -> int:
    """Write MEMORY.md from the OptMem store."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    store = Path(arguments[0]) if arguments else OPTMEM
    target = Path(arguments[1]) if len(arguments) > 1 else LEDGER
    target.write_text(build(store, target), encoding="utf-8")
    count = len(read_entries(store))
    stdout.write(f"imported {count} entries and {len(tree_sections(store))} tree spans "
                 f"into {target}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
