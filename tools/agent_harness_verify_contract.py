#!/usr/bin/env python3
"""Verify the client contracts and the sources this harness never edits.

Split out of `agent_harness_verify_static` when that file passed the 500 line
cap this repository enforces on itself.
"""

from __future__ import annotations

from pathlib import Path
import subprocess

from render_agent_contract import render as render_contract
from agent_harness_verify_common import (
    AKITA_BLOCK_SHA256,
    AKITA_MARKERS,
    CANONICAL_TREES,
    CLIENT_MARKERS,
    CONTRACTS,
    ROOT,
    SHARED_MARKERS,
    SOURCE_PATHS,
    UNSLOP_LAW,
    load_install_receipt,
    require,
    sha256_bytes,
)
from agent_harness_markers import marker_interior

def read_contract(name: str) -> bytes:
    """Read one client contract, naming it exactly when it is missing."""
    path = ROOT / name
    require(path.is_file(), "contract.path", str(path), f"existing {name}")
    return path.read_bytes()


def validate_akita_source(raw: bytes) -> None:
    """Check the Akita block against its pin and against the vendored article."""
    akita = marker_interior(raw, AKITA_MARKERS, "contract.akita-markers")
    require(sha256_bytes(akita) == AKITA_BLOCK_SHA256, "contract.akita-block",
            sha256_bytes(akita), AKITA_BLOCK_SHA256)
    article = SOURCE_PATHS["akita"] / "content/2026/04/20/clean-code-para-agentes-de-ia/index.en.md"
    require(article.is_file(), "contract.akita-source", str(article), "vendored Akita article")
    source_block = b"".join(article.read_bytes().splitlines(keepends=True)[174:224])
    require(akita == source_block, "contract.akita-source-block",
            sha256_bytes(akita), sha256_bytes(source_block))


def validate_contract_document(client: str, name: str, raw: bytes) -> None:
    """Check one contract against the renderer, its size cap, and the unslop law."""
    require(len(raw) < 32 * 1024, f"contract.{client}.bytes", len(raw), "less than 32768")
    rendered = render_contract(client)
    require(raw == rendered, f"contract.{client}.rendered",
            sha256_bytes(raw), sha256_bytes(rendered))
    require(raw.count(UNSLOP_LAW.encode()) == 1, f"contract.{client}.unslop-law",
            raw.count(UNSLOP_LAW.encode()), "exact mandated sentence once")
    validate_akita_source(raw)


def shared_digests(raw: bytes, label: str) -> dict[str, str]:
    """Return the digest of every block both clients must share."""
    return {markers[0]: sha256_bytes(marker_interior(raw, markers, label))
            for markers in SHARED_MARKERS}


def validate_shared_blocks(documents: dict[str, bytes]) -> None:
    """Check the shared blocks are byte-identical and the client blocks are not."""
    digests = {name: shared_digests(raw, f"contract.{name}") for name, raw in documents.items()}
    reference = next(iter(digests.values()))
    for name, rows in digests.items():
        require(rows == reference, f"contract.{name}.shared-blocks", rows, reference)
    clients = {sha256_bytes(marker_interior(raw, CLIENT_MARKERS, f"contract.{name}"))
               for name, raw in documents.items()}
    require(len(clients) == len(documents), "contract.client-blocks", len(clients),
            f"one distinct client block per contract ({len(documents)})")


def git_tree(path: str) -> str:
    """Return the committed tree digest for one path."""
    result = subprocess.run(("git", "rev-parse", f"HEAD:{path}"), cwd=ROOT,
                            capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def worktree_changes(path: str) -> str:
    """Return any uncommitted change under one path."""
    result = subprocess.run(("git", "status", "--porcelain", "--", path), cwd=ROOT,
                            capture_output=True, text=True, check=False)
    return result.stdout.strip()


def verify_sources() -> str:
    """Check no skill body or pinned upstream file has changed.

    The whole method rests on those bodies being the ones that were reviewed.
    One tree digest covers every file under each path, so a single changed byte
    anywhere fails this.
    """
    for path, expected in CANONICAL_TREES.items():
        actual = git_tree(path)
        require(actual == expected, f"sources.{path}", actual or "(no commit)", expected)
        dirty = worktree_changes(path)
        require(not dirty, f"sources.{path}.worktree", dirty.splitlines()[:3],
                "no uncommitted change")
    return " ".join(f"{path}={digest[:12]}" for path, digest in sorted(CANONICAL_TREES.items()))


def verify_agents() -> str:
    """Check every client contract. Example: verify_agents()."""
    load_install_receipt()
    documents = {name: read_contract(name) for name in CONTRACTS.values()}
    for client, name in CONTRACTS.items():
        validate_contract_document(client, name, documents[name])
    validate_shared_blocks(documents)
    sizes = " ".join(f"{name}={len(raw)}" for name, raw in sorted(documents.items()))
    return f"{sizes} shared_blocks={len(SHARED_MARKERS)} akita_sha256={AKITA_BLOCK_SHA256}"


def verify_contract() -> str:
    """Alias so `verify_agent_harness.py contract` reads naturally."""
    return verify_agents()


WORKER = ".claude/agents/method-worker.md"
WORKER_SKILLS = ("unslop", "clean-code-for-agents", "writing-for-agents", "unlazy")
NO_MEMO_SENTENCE = "You are a subagent. Don't run memo."


def worker_frontmatter(text: str) -> dict[str, str]:
    """Return the pinned subagent's simple frontmatter fields."""
    rows = text.split("---", 2)[1].splitlines() if text.startswith("---") else []
    pairs = (row.split(":", 1) for row in rows if ":" in row and not row.startswith(" "))
    return {key.strip(): value.strip() for key, value in pairs}


def verify_worker() -> str:
    """Check the pinned subagent still pins what the law says it pins.

    The model, the effort and the preloaded laws are the whole reason this
    definition exists, and an absent `permissionMode` is what makes a subagent
    inherit the parent's, which AGENTS.md requires.
    """
    path = ROOT / WORKER
    require(path.is_file(), "worker.path", str(path), f"existing {WORKER}")
    text = path.read_text(encoding="utf-8")
    fields = worker_frontmatter(text)
    require(fields.get("model") == "opus", "worker.model", fields.get("model"), "opus")
    require(fields.get("effort") == "medium", "worker.effort", fields.get("effort"), "medium")
    require("permissionMode" not in text, "worker.permission-mode", "present",
            "absent, so the subagent inherits the parent's")
    require(text.count(NO_MEMO_SENTENCE) == 1, "worker.no-memo",
            text.count(NO_MEMO_SENTENCE), "the exact sentence once")
    missing = [name for name in WORKER_SKILLS if f"- {name}" not in text]
    require(not missing, "worker.skills", missing, f"all of {list(WORKER_SKILLS)}")
    return f"model=opus effort=medium preloaded={len(WORKER_SKILLS)}"
