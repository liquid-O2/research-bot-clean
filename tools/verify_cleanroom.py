#!/usr/bin/env python3
"""Fail-closed structural verification for the clean-room repository."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "INDEX.md",
    "PROJECT_CONTRACT.md",
    "PROJECT_MEMORY.md",
    "PLAN.md",
    "AGENTS.md",
    "authorities/REGISTRY.tsv",
    "knowledge/propositions.tsv",
    "knowledge/evidence.tsv",
    "transcripts/CONVERSATION.md",
    "transcripts/EXPORT_RECEIPT.json",
    "provenance/sessions/CODEX_PREFIX_MANIFEST.tsv",
    "engine/Cargo.toml",
    "engine/Cargo.lock",
)
FORBIDDEN_TRACKED_PREFIXES = ("data/", "artifacts/", ".venv/", "target/")
SECRET_PATTERNS = (
    re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(rb"ghp_[A-Za-z0-9]{30,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as src:
        while chunk := src.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def fail(message: str) -> None:
    raise RuntimeError(message)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> int:
    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            fail(f"missing required file: {relative}")

    tracked = [line for line in git("ls-files", "-z").split("\0") if line]
    if not tracked:
        fail("repository has no tracked files")
    for relative in tracked:
        if relative.startswith(FORBIDDEN_TRACKED_PREFIXES):
            fail(f"forbidden tracked payload/build path: {relative}")
        path = ROOT / relative
        if path.is_symlink():
            fail(f"tracked symlink refused: {relative}")
        if path.stat().st_size > 10 * 1024 * 1024:
            fail(f"tracked file exceeds 10 MiB: {relative}")
        data = path.read_bytes()
        for pattern in SECRET_PATTERNS:
            if pattern.search(data):
                fail(f"secret-like material in tracked file: {relative}")

    branches = [line for line in git("for-each-ref", "--format=%(refname:short)", "refs/heads").splitlines() if line]
    if not branches and git("branch", "--show-current") == "main":
        branches = ["main"]
    if branches != ["main"]:
        fail(f"local branch set is not exactly main: {branches}")

    receipt_path = ROOT / "transcripts/EXPORT_RECEIPT.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if digest(ROOT / "transcripts/CONVERSATION.md") != receipt["conversation_sha256"]:
        fail("readable transcript hash mismatch")
    if digest(ROOT / "transcripts/SESSION_INDEX.tsv") != receipt["session_index_sha256"]:
        fail("transcript session index hash mismatch")
    if digest(ROOT / "transcripts/TRANSCRIPT_PARSE_ISSUES.tsv") != receipt["issues_sha256"]:
        fail("transcript issue ledger hash mismatch")
    if digest(ROOT / "provenance/sessions/CODEX_PREFIX_MANIFEST.tsv") != receipt["source_manifest_sha256"]:
        fail("transcript source manifest hash mismatch")

    with (ROOT / "authorities/REGISTRY.tsv").open(newline="", encoding="utf-8") as src:
        rows = list(csv.DictReader(src, delimiter="\t"))
    if not rows:
        fail("authority registry empty")
    ids = [row["authority_id"] for row in rows]
    if len(ids) != len(set(ids)):
        fail("duplicate authority ID")
    for row in rows:
        value = row["sha256"]
        if row["status"] != "PENDING_EXPORT" and not re.fullmatch(r"[0-9a-f]{64}", value):
            fail(f"authority has invalid SHA: {row['authority_id']}")

    card = ROOT / "evidence/claims/native_state/TASK_CARD.md"
    addendum = ROOT / "evidence/claims/native_state/READER_ADDENDUM.md"
    if digest(card) != "3f7d1820f250e814f186f49ae5e830c9f250905561d73e01740794f6c637743d":
        fail("native task-card hash mismatch")
    if digest(addendum) != "667ff4116338573c3ffddace170862ace8950244b58ec28f3e691dad04299226":
        fail("reader-addendum hash mismatch")

    ignored_data = subprocess.run(
        ["git", "check-ignore", "-q", "data/private-test"],
        cwd=ROOT,
        check=False,
    ).returncode
    if ignored_data != 0:
        fail("data/ is not ignored")

    print(
        json.dumps(
            {
                "status": "PASS",
                "tracked_files": len(tracked),
                "branches": branches,
                "authority_rows": len(rows),
                "transcript_messages": receipt["message_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"VERIFY_CLEANROOM_FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
