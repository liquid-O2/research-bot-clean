#!/usr/bin/env python3
"""Generate exact legacy branch/worktree/top-level cutover manifests."""

from __future__ import annotations

import csv
from pathlib import Path

from retirement_identity import identity


CLEAN = Path(__file__).resolve().parents[1]
LEGACY = Path("/workspace")
REF_MAP = CLEAN / "provenance/git/legacy_recovery/REF_SHA_MAP.tsv"
RECOVERY = (
    "/workspace/data/private_project_vault/"
    "git_recovery_20260810T144900Z.tar.zst.gpg"
)
MISC = "/workspace/data/private_project_vault/legacy_root_misc_20260810.tar.zst.gpg"
AUTH = "USER_REQUESTED_CLEANROOM_IMPLEMENTATION_2026-08-10"
REPLACE_NAMES = {
    ".git",
    ".gitignore",
    "AGENTS.md",
    "INDEX.md",
    "PLAN.md",
    "docs",
    "engine",
    "lab",
    "research",
    "tools",
}
CACHE_NAMES = {
    ".cache",
    ".cargo",
    ".pytest_cache",
    ".ruff_cache",
    ".tools",
    ".venvs",
}
MISC_NAMES = {
    ".claude",
    "chat-plan",
    "oracle",
    ".env",
    "-.png",
    "Downloads.zip",
    "arxiv_ib_list.xml",
    "config.toml",
    "verdicts.pkl",
}


def write_tsv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    ref_rows = []
    with REF_MAP.open(newline="", encoding="utf-8") as src:
        for row in csv.reader(src, delimiter="\t"):
            if row and row[0].startswith("refs/heads/"):
                ref_rows.append(
                    {
                        "ref": row[0],
                        "status": "RETIRE_LOCAL_AFTER_CUTOVER",
                        "tip_oid": row[1],
                        "recovery_artifact": RECOVERY,
                        "recovery_command": "decrypt; git bundle unbundle archives/repository_all_refs.bundle",
                        "authorization": AUTH,
                        "postcheck": "OLD_LOCAL_REF_ABSENT_NEW_REPO_ONLY_MAIN",
                    }
                )
    ref_rows.sort(key=lambda row: str(row["ref"]))
    write_tsv(
        CLEAN / "retirement/BRANCHES.tsv",
        [
            "ref",
            "status",
            "tip_oid",
            "recovery_artifact",
            "recovery_command",
            "authorization",
            "postcheck",
        ],
        ref_rows,
    )

    all_refs = []
    with REF_MAP.open(newline="", encoding="utf-8") as src:
        for row in csv.reader(src, delimiter="\t"):
            if not row:
                continue
            all_refs.append(
                {
                    "ref": row[0],
                    "status": "RETIRED_LOCAL_RECOVERABLE",
                    "object_oid": row[1],
                    "object_type": row[2],
                    "peeled_oid": row[3] if len(row) > 3 else "",
                    "recovery_artifact": RECOVERY,
                    "authorization": AUTH,
                    "postcheck": "EXACT_REF_PRESENT_IN_RESTORE_PROOF_NEW_REPO_ONLY_MAIN",
                }
            )
    all_refs.sort(key=lambda row: str(row["ref"]))
    write_tsv(
        CLEAN / "retirement/REFS.tsv",
        [
            "ref",
            "status",
            "object_oid",
            "object_type",
            "peeled_oid",
            "recovery_artifact",
            "authorization",
            "postcheck",
        ],
        all_refs,
    )

    summary = CLEAN / "provenance/git/legacy_recovery/worktree_summary.tsv"
    worktrees = []
    path_map = {
        "main": "/workspace",
        "entries_oracle_v1": "/workspace/.worktrees/entries-oracle-v1",
        "entries_oracle_v1_source_sync": "/workspace/.worktrees/entries-oracle-v1-source-sync",
        "select3_frontier_one_sweep": "/workspace/.worktrees/select3-frontier-one-sweep",
    }
    with summary.open(newline="", encoding="utf-8") as src:
        for row in csv.DictReader(src, delimiter="\t"):
            worktrees.append(
                {
                    "path": path_map[row["worktree"]],
                    "status": "RETIRE_LEGACY_WORKTREE_AFTER_CUTOVER",
                    "head_oid": row["head_oid"],
                    "dirty_receipt": (
                        f"ordinary={row['ordinary_changes']};untracked={row['untracked_paths']};"
                        f"combined_patch_bytes={row['combined_patch_bytes']}"
                    ),
                    "recovery_artifact": RECOVERY,
                    "recovery_command": (
                        f"decrypt; follow RESTORE.md worktrees/{row['worktree']}"
                    ),
                    "authorization": AUTH,
                    "postcheck": "LEGACY_WORKTREE_ABSENT",
                }
            )
    write_tsv(
        CLEAN / "retirement/WORKTREES.tsv",
        [
            "path",
            "status",
            "head_oid",
            "dirty_receipt",
            "recovery_artifact",
            "recovery_command",
            "authorization",
            "postcheck",
        ],
        worktrees,
    )

    current = {path.name: path for path in LEGACY.iterdir()}
    expected_legacy = set(current) - {"data", "artifacts"}
    known = REPLACE_NAMES | CACHE_NAMES | MISC_NAMES | {
        ".worktrees",
        "archive",
        "CLAUDE.md",
        "CONTEXT_PACK.md",
        "HANDOFF_NEOBOX.md",
    }
    unknown = expected_legacy - known
    if unknown:
        raise RuntimeError(f"unclassified top-level legacy paths: {sorted(unknown)}")

    deletions = []
    for name in sorted(expected_legacy):
        path = current[name]
        if name in CACHE_NAMES:
            recovery = "NONE_REPRODUCIBLE_CACHE"
            command = "recreate_from_clean_lockfiles_if_needed"
        elif name in MISC_NAMES:
            recovery = MISC
            command = "decrypt legacy_root_misc archive"
        else:
            recovery = RECOVERY
            command = "decrypt legacy Git recovery; follow RESTORE.md"
        deletions.append(
            {
                "target": str(path),
                "status": "APPROVED_PENDING_CUTOVER",
                "pre_identity": identity(path),
                "recovery_artifact": recovery,
                "recovery_command": command,
                "authorization": AUTH,
                "postcheck": (
                    "REPLACED_BY_CLEAN_MAIN"
                    if name in REPLACE_NAMES
                    else "ABSENT_AFTER_CUTOVER"
                ),
            }
        )
    write_tsv(
        CLEAN / "retirement/DELETIONS.tsv",
        [
            "target",
            "status",
            "pre_identity",
            "recovery_artifact",
            "recovery_command",
            "authorization",
            "postcheck",
        ],
        deletions,
    )

    retentions = [
        {
            "target": "/workspace/data",
            "status": "RETAIN_EXTERNAL_IGNORED",
            "reason": "raw_corpora_private_vault_and_cleanroom_staging",
            "authority": "PROJECT_CONTRACT.md",
            "postcheck": "SAME_MOUNT_AND_PRE_CUTOVER_SENTINEL_IDENTITIES",
        },
        {
            "target": "/workspace/artifacts",
            "status": "RETAIN_EXTERNAL_IGNORED",
            "reason": "published_authorities_evidence_workflow_registry_and_build_pool",
            "authority": "authorities/REGISTRY.tsv",
            "postcheck": "PRESENT_IGNORED_AND_AUTHORITY_HASH_TESTS",
        },
    ]
    write_tsv(
        CLEAN / "retirement/RETENTIONS.tsv",
        ["target", "status", "reason", "authority", "postcheck"],
        retentions,
    )
    print(
        f"generated {len(ref_rows)} branches, {len(all_refs)} refs, {len(worktrees)} worktrees, "
        f"{len(deletions)} deletion targets, {len(retentions)} retentions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
