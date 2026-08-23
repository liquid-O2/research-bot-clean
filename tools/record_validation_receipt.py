#!/usr/bin/env python3
"""Retain already-run validation output in the harness receipt format."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
from typing import cast

from agent_harness_verify_common import (
    BASELINE_IGNORED_INPUTS,
    BASELINE_SCRATCH_PATHS,
    ROOT,
    framed_path_sha256,
    normalized_git_status,
    parse_git_status_records,
    path_tree_metrics,
    sha256_bytes,
    sha256_file,
)


PLAN_COMMIT = "747c9c45698226db70e85c65fe29d71d58210dd0"
BASELINE_RECEIPT = ROOT / ".codex/harness/receipts/repo-cleanup-baseline-v1.json"
PLAN_ROOT = ROOT / ".unlazy/repo-cleanup-plan"
ARCHIVE_ROOT = ROOT / "archive/agent-harness-pre-20260823"
SCRATCH_QUARANTINE = Path("/home/algo/.codex/orchestrate/recovery/repo-cleanup/U02")
PSTACK_RUNTIME = Path(
    "/home/algo/.codex/orchestrate/runtime/"
    "pstack-46125561306434d8a1d7745d540d8932ab0cd2a2/scripts"
)
PSTACK_ORACLE = Path(
    "/home/algo/.codex/orchestrate/repo-cleanup/reports/U02-pstack-runtime-oracle.md"
)
PINNED_NODE_MODULES = ROOT / (
    "vendor/agent-sources/pstack/46125561306434d8a1d7745d540d8932ab0cd2a2/"
    "pstack/skills/poteto-mode/scripts/node_modules"
)
HARNESS_GATE_COMMANDS = {
    "H1": "PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_agent_harness.py archive",
    "H2": "PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_agent_harness.py skills",
    "H3": "PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_agent_harness.py codex-skills",
    "H4": "PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_agent_harness.py agents",
    "H5": "PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_agent_harness.py hooks",
    "H6": "PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_agent_harness.py lifecycle",
    "H7": "PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_agent_harness.py agents-toml",
    "H8": "PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_agent_harness.py provenance",
    "H9": "PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_agent_harness.py upstream-receipts",
    "H10": "PYTHONDONTWRITEBYTECODE=1 python3 tools/install_agent_harness.py --check",
    "hook-trust": "PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_agent_harness.py hook-trust",
}
RETAINED_RECEIPTS = (
    "codex-skills-list.jsonl", "lifecycle-events.jsonl", "lifecycle-verification.txt",
    "local-skills-validation.txt", "optmem-validation.txt", "pocock-validation.txt",
    "pstack-validation.txt", "unlazy-validation.txt",
)
STATUS_COMMAND = "git diff --cached --name-status --no-renames -z"
STATUS_NORMALIZATION = "sort by UTF-8 path; emit STATUS, tab, PATH, newline"
FILE_SHA256_NORMALIZATION = (
    "sha256sum first field over exact file bytes; discard path suffix and newline"
)
FRAMED_TREE_NORMALIZATION = (
    "sort relative paths; append NUL-delimited kind, UTF-8 surrogateescape path, "
    "four-digit mode, payload byte length, payload, and trailing NUL"
)
GATE_OUTPUT_NORMALIZATION = (
    "concatenate decoded stdout then stderr; strip leading and trailing Unicode "
    "whitespace; encode UTF-8; SHA-256 exact remaining bytes"
)
WORKTREE_NORMALIZATION = "exact stdout bytes"
CAPTURE_COMMAND = (
    "PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_agent_harness.py "
    "capture-cleanup-baseline"
)
BASELINE_TOP_KEYS = {
    "schema_version", "captured_at", "checkpoint", "status", "path_classes",
    "ignored_state", "inventory", "harness", "mutable_runtime",
}


def sha256_producer(path: Path) -> str:
    """Render a digest command. Example: sha256_producer(ROOT / 'AGENTS.md')."""
    display = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)
    return f"sha256sum -- {shlex.quote(display)}"


def file_hash_evidence(path: Path) -> dict[str, str]:
    return {
        "sha256": sha256_file(path),
        "sha256_producer_command": sha256_producer(path),
        "sha256_normalization": FILE_SHA256_NORMALIZATION,
    }


def run_command(command: str) -> tuple[str, int]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.perf_counter_ns()
    result = subprocess.run(shlex.split(command.replace("PYTHONDONTWRITEBYTECODE=1 ", "")),
                            cwd=ROOT, env=environment, capture_output=True,
                            text=True, check=False, timeout=180)
    duration_ms = (time.perf_counter_ns() - started) // 1_000_000
    output = result.stdout + result.stderr
    if result.returncode:
        raise RuntimeError(
            f"capture command={command!r} returncode={result.returncode} "
            f"offending={output.strip()!r}; expected returncode=0"
        )
    return output.strip(), duration_ms


def git_output(*arguments: str) -> bytes:
    """Capture exact Git stdout. Example: git_output('rev-parse', 'HEAD')."""
    result = subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True,
                            check=False, timeout=60)
    if result.returncode:
        stderr = result.stderr.decode(errors="replace").strip()
        raise RuntimeError(
            f"git arguments={arguments!r} failed returncode={result.returncode} "
            f"offending={stderr!r}; expected returncode=0"
        )
    return result.stdout


def staged_records() -> list[tuple[str, str]]:
    """List staged U02 rows. Example: staged_records()."""
    raw = git_output("diff", "--cached", "--name-status", "--no-renames", "-z")
    return parse_git_status_records(raw)


def commit_records(parent: str, head: str) -> list[tuple[str, str]]:
    """List commit-delta rows. Example: commit_records(parent, head)."""
    raw = git_output("diff", "--name-status", "--no-renames", "-z", parent, head)
    return parse_git_status_records(raw)


def capture_path_classes(records: list[tuple[str, str]]) -> dict[str, list[str]]:
    by_status = {"A": [], "D": [], "M": []}
    for status_name, path in records:
        if status_name not in by_status:
            raise ValueError(
                f"staged status offending={(status_name, path)!r}; expected A, D, or M"
            )
        by_status[status_name].append(path)
    return {
        "tracked_deletions": by_status["D"],
        "tracked_modifications": by_status["M"],
        "staged_additions": by_status["A"],
        "ignored_inputs": sorted(BASELINE_IGNORED_INPUTS),
        "removed_or_quarantined_scratch": sorted(BASELINE_SCRATCH_PATHS),
        "unexpected_paths": [],
        "overlapping_classes": [],
    }


def capture_plan_files() -> list[dict[str, object]]:
    """Hash frozen plan files. Example: capture_plan_files()."""
    rows = []
    for path in sorted(PLAN_ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(PLAN_ROOT).as_posix()
        preserve = relative in {"PLAN.md", "decisions.tsv"} or relative.startswith("evidence/")
        rows.append({"path": relative,
                     "class": "preserve" if preserve else "dispose-after-ledger",
                     **file_hash_evidence(path)})
    return rows


def capture_archive() -> dict[str, object]:
    """Measure archive identity. Example: capture_archive()."""
    manifest_path = ARCHIVE_ROOT / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    kinds = {kind: 0 for kind in ("directory", "file", "symlink")}
    for row in cast(list[dict[str, object]], manifest["items"]):
        kinds[cast(str, row["kind"])] += 1
    return {
        "path": str(ARCHIVE_ROOT), "manifest_sha256": sha256_file(manifest_path),
        "manifest_sha256_producer_command": sha256_producer(manifest_path),
        "manifest_sha256_normalization": FILE_SHA256_NORMALIZATION,
        "framed_tree_sha256": framed_path_sha256(ARCHIVE_ROOT),
        "framed_tree_sha256_producer_command": CAPTURE_COMMAND,
        "framed_tree_sha256_normalization": FRAMED_TREE_NORMALIZATION,
        "manifest_entries": len(cast(list[object], manifest["items"])),
        "manifest_kinds": kinds, "tree": path_tree_metrics(ARCHIVE_ROOT),
    }


def capture_byte_groups() -> list[dict[str, object]]:
    """Measure baseline byte groups. Example: capture_byte_groups()."""
    paths = (
        ROOT / ".agents", ROOT / ".claude", ROOT / ".codex",
        ROOT / "vendor/agent-sources", ROOT / "design/harness_rebuild_20260823",
        ROOT / "tools/harness_templates", PLAN_ROOT,
        ROOT / ".unlazy/repo-cleanup-implementation", ARCHIVE_ROOT,
    )
    excluded = frozenset({BASELINE_RECEIPT, BASELINE_RECEIPT.parent})
    return [{"path": str(path.relative_to(ROOT)), **path_tree_metrics(path, excluded)}
            for path in paths if path.exists()]


def capture_tracked_symlinks() -> list[dict[str, str]]:
    """Record tracked symlinks. Example: capture_tracked_symlinks()."""
    raw = git_output("ls-files", "-s", "-z").decode("utf-8")
    rows = []
    for entry in raw.rstrip("\0").split("\0"):
        metadata, path_name = entry.split("\t", 1)
        mode, object_id, _ = metadata.split()
        path = ROOT / path_name
        if mode == "120000":
            rows.append({"path": path_name, "object_id": object_id,
                         "target": os.readlink(path)})
    return rows


def capture_worktrees() -> dict[str, object]:
    """Record exact worktree porcelain. Example: capture_worktrees()."""
    raw = git_output("worktree", "list", "--porcelain")
    return {"producer_command": "git worktree list --porcelain",
            "normalization": WORKTREE_NORMALIZATION,
            "sha256": sha256_bytes(raw), "porcelain": raw.decode("utf-8")}


def capture_gate_results() -> list[dict[str, object]]:
    rows = []
    for gate, command in HARNESS_GATE_COMMANDS.items():
        output, duration_ms = run_command(command)
        rows.append({"gate": gate, "command": command, "result": "PASS",
                     "duration_ms": duration_ms, "output": output,
                     "output_sha256": sha256_bytes(output.encode()),
                     "output_sha256_producer_command": CAPTURE_COMMAND,
                     "output_sha256_normalization": GATE_OUTPUT_NORMALIZATION})
    return rows


def capture_retained_receipts() -> list[dict[str, str]]:
    """Hash retained evidence. Example: capture_retained_receipts()."""
    root = ROOT / ".codex/harness/receipts"
    return [{"path": str((root / name).relative_to(ROOT)),
             **file_hash_evidence(root / name)} for name in RETAINED_RECEIPTS]


def capture_quarantined_scratch() -> list[dict[str, str]]:
    """Hash quarantined scratch. Example: capture_quarantined_scratch()."""
    rows = []
    for source in sorted(BASELINE_SCRATCH_PATHS):
        destination = SCRATCH_QUARANTINE / Path(source).name
        if not destination.is_file():
            raise FileNotFoundError(
                f"quarantined scratch offending={destination}; expected regular file"
            )
        rows.append({"source": source, "destination": str(destination),
                     **file_hash_evidence(destination)})
    return rows


def capture_ignored_state() -> dict[str, object]:
    return {
        "unlazy_plan": {"path": ".unlazy/repo-cleanup-plan",
                        "files": capture_plan_files()},
        "unlazy_runtime": {"path": ".unlazy/repo-cleanup-implementation",
                           "class": "mutable-local-execution", "frozen_hash": None},
        "harness_archive": capture_archive(),
    }


def capture_harness_state() -> dict[str, object]:
    manifest = ROOT / "vendor/agent-sources/MANIFEST.json"
    return {
        "gates": capture_gate_results(),
        "retained_receipts": capture_retained_receipts(),
        "pin_manifest_sha256": sha256_file(manifest),
        "pin_manifest_sha256_producer_command": sha256_producer(manifest),
        "pin_manifest_sha256_normalization": FILE_SHA256_NORMALIZATION,
    }


def capture_inventory_state() -> dict[str, object]:
    return {
        "producer_command": CAPTURE_COMMAND,
        "self_excluded_paths": [str(BASELINE_RECEIPT.parent.relative_to(ROOT)),
                                str(BASELINE_RECEIPT.relative_to(ROOT))],
        "byte_groups": capture_byte_groups(),
        "tracked_symlinks": capture_tracked_symlinks(),
        "worktrees": capture_worktrees(),
    }


def capture_mutable_runtime() -> dict[str, object]:
    return {
        "pstack_runtime": str(PSTACK_RUNTIME),
        "pstack_runtime_oracle": str(PSTACK_ORACLE),
        "scratch_quarantine": str(SCRATCH_QUARANTINE),
        "quarantined_scratch": capture_quarantined_scratch(),
        "pinned_node_modules_absent": not PINNED_NODE_MODULES.exists(),
    }


def cleanup_baseline_payload() -> dict[str, object]:
    records = staged_records()
    status = normalized_git_status(records)
    return {
        "schema_version": 1,
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "checkpoint": {"plan_commit": PLAN_COMMIT, "pre_harness_head": PLAN_COMMIT,
                       "branch": "main", "containing_commit": "SELF"},
        "status": {"producer_command": STATUS_COMMAND,
                   "normalization": STATUS_NORMALIZATION,
                   "sha256": sha256_bytes(status), "record_count": len(records)},
        "path_classes": capture_path_classes(records),
        "ignored_state": capture_ignored_state(),
        "harness": capture_harness_state(),
        "inventory": capture_inventory_state(),
        "mutable_runtime": capture_mutable_runtime(),
    }


def capture_cleanup_baseline() -> str:
    """Write normalized cleanup evidence. Example: capture_cleanup_baseline()."""
    payload = cleanup_baseline_payload()
    BASELINE_RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    temporary = BASELINE_RECEIPT.with_name(f".{BASELINE_RECEIPT.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    os.replace(temporary, BASELINE_RECEIPT)
    return f"schema=1 paths={payload['status']['record_count']} receipt={BASELINE_RECEIPT}"


def validation_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument(
        "--result",
        action="append",
        nargs=3,
        required=True,
        metavar=("COMMAND", "EXIT_CODE", "LOG"),
    )
    return parser


def validation_results(
    raw_results: list[list[str]], parser: argparse.ArgumentParser,
) -> tuple[list[str], list[int], bytes]:
    commands: list[str] = []
    exit_codes: list[int] = []
    output = bytearray()
    for command, raw_exit_code, raw_log in raw_results:
        if not (log := Path(raw_log)).is_file():
            parser.error(f"validation log offending={log}; expected regular file")
        try:
            exit_code = int(raw_exit_code)
        except ValueError:
            parser.error(f"exit code offending={raw_exit_code!r}; expected integer")
        commands.append(command)
        exit_codes.append(exit_code)
        output.extend(f"$ {command}\n".encode())
        output.extend(log.read_bytes())
        if not output.endswith(b"\n"):
            output.extend(b"\n")
    return commands, exit_codes, bytes(output)


def upstream_receipt_bytes(
    source: str, commit: str, commands: list[str], exit_codes: list[int], output: bytes,
) -> tuple[str, bytes]:
    status = "PASS" if all(code == 0 for code in exit_codes) else "FAIL"
    header = (
        "UPSTREAM VALIDATION RECEIPT 1\n"
        f"source={source}\n"
        f"commit={commit}\n"
        f"status={status}\n"
        f"commands_json={json.dumps(commands, separators=(',', ':'))}\n"
        f"exit_codes_json={json.dumps(exit_codes, separators=(',', ':'))}\n"
        f"output_sha256={hashlib.sha256(output).hexdigest()}\n"
        "--- output ---\n"
    ).encode()
    return status, header + output


def write_upstream_receipt(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def main() -> int:
    """Record prior validation output. Example: main() parses the receipt CLI."""
    parser = validation_parser()
    arguments = parser.parse_args()
    commands, exit_codes, output = validation_results(arguments.result, parser)
    status, content = upstream_receipt_bytes(
        arguments.source, arguments.commit, commands, exit_codes, output
    )
    write_upstream_receipt(arguments.receipt, content)
    print(f"{arguments.source} receipt {status}: {arguments.receipt}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
