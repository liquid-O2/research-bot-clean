#!/usr/bin/env python3
"""Render AGENTS.md and CLAUDE.md from one set of shared blocks.

Two clients read the same method, so the method has one source. Generating both
files makes drift impossible rather than merely detectable: a shared block can
only differ between them if someone edits a generated file by hand, and
`verify_agent_harness.py contract` catches that.

Each document is four marked blocks. Memory, agent method and the Akita code
standard are byte-identical across clients. Only the client block differs.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Sequence, TextIO

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from agent_harness_verify_common import (  # noqa: E402
    AGENT_METHOD_MARKERS,
    AGENT_ROUTING,
    AKITA_MARKERS,
    CLIENT_BLOCKS,
    CLIENT_MARKERS,
    CONTRACTS,
    MEMORY_MARKERS,
    ROOT,
)

TEMPLATES = TOOLS / "harness_templates"
MEMORY_BLOCK = TEMPLATES / "memory-agent-block.md"
AKITA_ARTICLE = (
    ROOT / "vendor/agent-sources/akita/bbd8e681c14c0f57b2e5ea63e4d1c0043a6890da"
    / "content/2026/04/20/clean-code-para-agentes-de-ia/index.en.md"
)
AKITA_LINES = slice(174, 224)
MAX_CONTRACT_BYTES = 32 * 1024


def fenced(markers: tuple[str, str], body: str) -> str:
    """Wrap one block in its markers, each on its own line."""
    return f"{markers[0]}\n{body.rstrip()}\n{markers[1]}\n"


def memory_block() -> str:
    """Return the shared memory contract."""
    return MEMORY_BLOCK.read_text(encoding="utf-8")


def akita_block() -> str:
    """Return the Akita code standard, verbatim from the vendored article."""
    lines = AKITA_ARTICLE.read_bytes().splitlines(keepends=True)[AKITA_LINES]
    return b"".join(lines).decode("utf-8")


def client_block(client: str) -> str:
    """Return the one block that differs between clients."""
    if client not in CLIENT_BLOCKS:
        raise ValueError(f"unknown client {client!r}, expected one of {sorted(CLIENT_BLOCKS)}")
    return CLIENT_BLOCKS[client]


def render(client: str) -> bytes:
    """Render one client's contract."""
    document = "\n".join([
        fenced(MEMORY_MARKERS, memory_block()),
        fenced(AGENT_METHOD_MARKERS, AGENT_ROUTING),
        fenced(CLIENT_MARKERS, client_block(client)),
        fenced(AKITA_MARKERS, akita_block()),
    ])
    encoded = document.encode("utf-8")
    if len(encoded) >= MAX_CONTRACT_BYTES:
        raise ValueError(f"{CONTRACTS[client]} is {len(encoded)} bytes, "
                         f"expected under {MAX_CONTRACT_BYTES}")
    return encoded


def contract_path(client: str) -> Path:
    """Return where one client's contract lives."""
    return ROOT / CONTRACTS[client]


def write_all() -> dict[str, int]:
    """Write every client's contract and report its size."""
    sizes: dict[str, int] = {}
    for client in sorted(CONTRACTS):
        rendered = render(client)
        contract_path(client).write_bytes(rendered)
        sizes[CONTRACTS[client]] = len(rendered)
    return sizes


def main(argv: Sequence[str] | None = None, stdout: TextIO = sys.stdout) -> int:
    """Render both contracts and print their sizes."""
    sizes = write_all()
    report = " ".join(f"{name}={size}" for name, size in sorted(sizes.items()))
    stdout.write(f"CONTRACTS RENDERED {report}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
