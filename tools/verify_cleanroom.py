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
    # AGENTS.md removed 2026-08-10 by governance amendment
    # E_GOVERNANCE_OPERATOR_AMENDMENT_V1; its law lives in INDEX.md.
    "FINAL_PLAN.md",
    "STATE.md",
    "PROGRESS.md",
    "DIRECTIVES.md",
    "design/CHANGE_CONTROL.md",
    "authorities/REGISTRY.tsv",
    "knowledge/propositions.tsv",
    "knowledge/evidence.tsv",
    "research/BIBLIOGRAPHY.tsv",
    "research/RESEARCH_MAP.md",
    "transcripts/CONVERSATION.md",
    "transcripts/EXPORT_RECEIPT.json",
    "provenance/sessions/CODEX_PREFIX_MANIFEST.tsv",
    "provenance/sessions/CODEX_PREFIX_MANIFEST_INITIAL.tsv",
    "provenance/sessions/CONTINUATION_PROOF.tsv",
    "provenance/knowledge_audit/verification_v1.json",
    "provenance/CUTOVER_RECEIPT.tsv",
    "provenance/PUBLICATION_RECEIPT.tsv",
    "provenance/git/CLEAN_REMOTE.tsv",
    "engine/Cargo.toml",
    "engine/Cargo.lock",
    "retirement/REFS.tsv",
    "retirement/TEMP_CLEANUP.tsv",
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

    external_root_names = {"data", "artifacts"}
    for name in external_root_names:
        path = ROOT / name
        if path.exists() and not path.is_dir():
            fail(f"external root is not a directory: {name}")

    physical = set()
    for base, directories, files in os.walk(ROOT):
        base_path = Path(base)
        if base_path == ROOT:
            directories[:] = [
                name
                for name in directories
                if name != ".git" and name not in external_root_names
            ]
        for name in files:
            relative = (base_path / name).relative_to(ROOT).as_posix()
            physical.add(relative)
    extra_physical = sorted(physical - set(tracked))
    if extra_physical:
        fail(f"untracked/ignored physical files present: {extra_physical[:20]}")

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
    with (ROOT / "provenance/sessions/CONTINUATION_PROOF.tsv").open(
        newline="", encoding="utf-8"
    ) as src:
        continuation = list(csv.DictReader(src, delimiter="\t"))
    if not continuation or any(row["status"] != "PREFIX_CONTINUITY_PASS" for row in continuation):
        fail("transcript continuation proof is absent or not green")
    if any(int(row["new_cutoff_bytes"]) < int(row["old_cutoff_bytes"]) for row in continuation):
        fail("transcript continuation cutoff shrank")

    knowledge_verification = json.loads(
        (ROOT / "provenance/knowledge_audit/verification_v1.json").read_text(encoding="utf-8")
    )
    if knowledge_verification.get("status") != "PASS_ZERO_UNCLASSIFIED":
        fail("knowledge migration audit is not PASS_ZERO_UNCLASSIFIED")
    if knowledge_verification.get("unclassified_count") != 0:
        fail("knowledge migration audit has unclassified entries")

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
        if row["status"] == "PENDING_EXPORT":
            continue
        declared = Path(row["external_path"])
        resolved = declared if declared.is_absolute() else ROOT / declared
        if not resolved.is_file():
            fail(f"authority path is not an exact file: {row['authority_id']} -> {resolved}")
        if digest(resolved) != value:
            fail(f"authority content hash mismatch: {row['authority_id']}")

    authority_ids = set(ids)
    with (ROOT / "knowledge/evidence.tsv").open(newline="", encoding="utf-8") as src:
        evidence_rows = list(csv.DictReader(src, delimiter="\t"))
    evidence_ids = [row["evidence_id"] for row in evidence_rows]
    if len(evidence_ids) != len(set(evidence_ids)):
        fail("duplicate evidence ID")
    evidence_set = set(evidence_ids) - {"E_SCHEMA"}
    if not evidence_set:
        fail("evidence ledger has no claim evidence")
    for row in evidence_rows:
        for field in ("spec_sha256", "code_sha256", "output_sha256", "evaluator_sha256"):
            value = row[field]
            if value and not re.fullmatch(r"[0-9a-f]{64}", value):
                fail(f"invalid {field} in evidence row {row['evidence_id']}")
        inputs = {item for item in row["input_authority_ids"].split(";") if item}
        unknown = inputs - authority_ids
        if unknown:
            fail(f"unknown input authority in {row['evidence_id']}: {sorted(unknown)}")
    with (ROOT / "knowledge/propositions.tsv").open(newline="", encoding="utf-8") as src:
        propositions = list(csv.DictReader(src, delimiter="\t"))
    for row in propositions:
        linked = {item for item in row["evidence_ids"].split(";") if item}
        if not linked:
            fail(f"proposition lacks evidence/disposition link: {row['proposition_id']}")
        missing = linked - evidence_set
        if missing:
            fail(f"unknown evidence link in {row['proposition_id']}: {sorted(missing)}")

    with (ROOT / "research/BIBLIOGRAPHY.tsv").open(newline="", encoding="utf-8") as src:
        bibliography = list(csv.DictReader(src, delimiter="\t"))
    if len(bibliography) < 10:
        fail("research bibliography is not populated")
    for row in bibliography:
        if not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            fail(f"invalid research source SHA: {row['source_id']}")
        if row["status"] == "SOURCE_TEXT":
            source = Path(row["external_path"])
            if not source.is_file() or digest(source) != row["sha256"]:
                fail(f"external research source mismatch: {row['source_id']}")
    with (ROOT / "knowledge/research_assets.tsv").open(newline="", encoding="utf-8") as src:
        research_assets = list(csv.DictReader(src, delimiter="\t"))
    if not research_assets or any(
        row["status"].startswith("PENDING") or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
        for row in research_assets
    ):
        fail("research asset registry is pending or incomplete")

    recovery_refs = {}
    with (ROOT / "provenance/git/legacy_recovery/REF_SHA_MAP.tsv").open(
        newline="", encoding="utf-8"
    ) as src:
        for row in csv.reader(src, delimiter="\t"):
            if row:
                recovery_refs[row[0]] = row[1]
    with (ROOT / "retirement/REFS.tsv").open(newline="", encoding="utf-8") as src:
        retirement_refs = {
            row["ref"]: row["object_oid"] for row in csv.DictReader(src, delimiter="\t")
        }
    if retirement_refs != recovery_refs:
        fail("retirement ref disposition does not cover the exact recovery ref map")

    with (ROOT / "provenance/CUTOVER_RECEIPT.tsv").open(
        newline="", encoding="utf-8"
    ) as src:
        cutover = {
            row["field"]: row["value"] for row in csv.DictReader(src, delimiter="\t")
        }
    if cutover.get("status") != "PASS_POSTCHECK_REPAIRED":
        fail("cutover receipt is absent or not complete")
    if cutover.get("deletion_target_count") != "30":
        fail("cutover receipt deletion target count mismatch")

    with (ROOT / "provenance/PUBLICATION_RECEIPT.tsv").open(
        newline="", encoding="utf-8"
    ) as src:
        publication = {
            row["field"]: row["value"] for row in csv.DictReader(src, delimiter="\t")
        }
    if publication.get("status") != "PASS_PUBLIC":
        fail("public repository receipt is absent or not green")
    if publication.get("repository") != "https://github.com/liquid-O2/research-bot-clean":
        fail("public repository receipt names the wrong repository")
    with (ROOT / "provenance/git/CLEAN_REMOTE.tsv").open(
        newline="", encoding="utf-8"
    ) as src:
        clean_remote = {
            row["field"]: row["value"] for row in csv.DictReader(src, delimiter="\t")
        }
    if not clean_remote.get("visibility", "").startswith("PUBLIC_VERIFIED"):
        fail("clean remote registry is not marked public and verified")

    with (ROOT / "retirement/DELETIONS.tsv").open(newline="", encoding="utf-8") as src:
        deletion_rows = list(csv.DictReader(src, delimiter="\t"))
    if len(deletion_rows) != 30 or any(
        row["status"] != "COMPLETED_CUTOVER" for row in deletion_rows
    ):
        fail("deletion retirement is not complete")
    with (ROOT / "retirement/BRANCHES.tsv").open(newline="", encoding="utf-8") as src:
        branch_rows = list(csv.DictReader(src, delimiter="\t"))
    if not branch_rows or any(
        row["status"] != "RETIRED_LOCAL_RECOVERABLE" for row in branch_rows
    ):
        fail("legacy branch retirement is not complete")
    with (ROOT / "retirement/WORKTREES.tsv").open(newline="", encoding="utf-8") as src:
        worktree_rows = list(csv.DictReader(src, delimiter="\t"))
    if not worktree_rows or any(
        row["status"] != "RETIRED_LEGACY_WORKTREE_RECOVERABLE"
        for row in worktree_rows
    ):
        fail("legacy worktree retirement is not complete")
    with (ROOT / "retirement/TEMP_CLEANUP.tsv").open(
        newline="", encoding="utf-8"
    ) as src:
        temp_cleanup_rows = list(csv.DictReader(src, delimiter="\t"))
    if len(temp_cleanup_rows) != 2 or any(
        row["status"] != "COMPLETED_TEMP_CLEANUP" for row in temp_cleanup_rows
    ):
        fail("redundant clean-room temporary cleanup is not complete")
    for row in temp_cleanup_rows:
        if Path(row["target"]).exists():
            fail(f"redundant clean-room temporary still exists: {row['target']}")

    card = ROOT / "evidence/claims/native_state/TASK_CARD.md"
    addendum = ROOT / "evidence/claims/native_state/READER_ADDENDUM.md"
    if digest(card) != "3f7d1820f250e814f186f49ae5e830c9f250905561d73e01740794f6c637743d":
        fail("native task-card hash mismatch")
    if digest(addendum) != "667ff4116338573c3ffddace170862ace8950244b58ec28f3e691dad04299226":
        fail("reader-addendum hash mismatch")

    for name in sorted(external_root_names):
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", f"{name}/private-test"],
            cwd=ROOT,
            check=False,
        ).returncode
        if ignored != 0:
            fail(f"{name}/ is not ignored")

    print(
        json.dumps(
            {
                "status": "PASS",
                "tracked_files": len(tracked),
                "branches": branches,
                "authority_rows": len(rows),
                "evidence_rows": len(evidence_set),
                "research_sources": len(bibliography),
                "retired_refs": len(retirement_refs),
                "knowledge_sources": knowledge_verification["source_count"],
                "continuation_sources": len(continuation),
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
