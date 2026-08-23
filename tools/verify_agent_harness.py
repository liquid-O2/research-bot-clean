#!/usr/bin/env python3
"""Verify the installed Codex-native repository harness."""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from collections.abc import Callable
from typing import cast

from agent_harness_verify_common import (
    HarnessVerificationError,
    ROOT,
    checkpoint_path_allowed,
    exact_object_keys,
    load_json_object,
    normalized_git_status,
    require,
    sha256_bytes,
    sha256_file,
    validate_baseline_path_classes,
    validate_baseline_status_classes,
)
import record_validation_receipt as receipt
from agent_harness_verify_runtime import (
    capture_codex_skills,
    verify_codex_skills,
    verify_hook_trust,
    verify_lifecycle,
)
from agent_harness_verify_static import (
    verify_agents,
    verify_agents_toml,
    verify_contract,
    verify_archive,
    verify_hooks,
    verify_provenance,
    verify_skills,
    verify_upstream_receipts,
)


CHECKS: dict[str, tuple[str, Callable[[], str]]] = {
    "archive": ("ARCHIVE", verify_archive),
    "skills": ("SKILLS", verify_skills),
    "codex-skills": ("CODEX SKILLS", verify_codex_skills),
    "agents": ("AGENTS", verify_agents),
    "contract": ("CONTRACT", verify_contract),
    "hooks": ("HOOKS", verify_hooks),
    "lifecycle": ("LIFECYCLE", verify_lifecycle),
    "agents-toml": ("AGENT TOML", verify_agents_toml),
    "provenance": ("PROVENANCE", verify_provenance),
    "upstream-receipts": ("UPSTREAM RECEIPTS", verify_upstream_receipts),
    "hook-trust": ("HOOK TRUST", verify_hook_trust),
    "capture-codex-skills": ("CODEX SKILLS RECEIPT", capture_codex_skills),
    "capture-cleanup-baseline": ("CLEANUP BASELINE RECEIPT", receipt.capture_cleanup_baseline),
    "cleanup-baseline": ("CLEANUP BASELINE", lambda: verify_cleanup_baseline()),
}


def baseline_records() -> tuple[list[tuple[str, str]], str]:
    receipt_name = str(receipt.BASELINE_RECEIPT.relative_to(ROOT))
    staged = receipt.staged_records()
    if receipt_name in {path for _, path in staged}:
        return staged, "INDEX"
    containing = receipt.git_output(
        "log", "-n1", "--format=%H", "--", receipt_name
    ).decode("ascii").strip()
    require(bool(containing), "baseline.containing-commit", containing,
            "commit containing the tracked baseline receipt")
    return receipt.commit_records(receipt.PLAN_COMMIT, containing), containing


def validate_captured_at(value: object) -> None:
    try:
        parsed = dt.datetime.fromisoformat(cast(str, value))
    except (TypeError, ValueError):
        parsed = None
    require(parsed is not None and parsed.tzinfo is not None,
            "baseline.captured-at", value, "timezone-aware ISO-8601 timestamp")


def validate_baseline_header(
    baseline: dict[str, object], records: list[tuple[str, str]],
) -> None:
    require(set(baseline) == receipt.BASELINE_TOP_KEYS, "baseline.keys", sorted(baseline),
            str(sorted(receipt.BASELINE_TOP_KEYS)))
    require(baseline["schema_version"] == 1, "baseline.schema-version",
            baseline["schema_version"], "1")
    validate_captured_at(baseline["captured_at"])
    checkpoint = exact_object_keys(baseline["checkpoint"], {
        "plan_commit", "pre_harness_head", "branch", "containing_commit",
    }, "baseline.checkpoint")
    expected = {"plan_commit": receipt.PLAN_COMMIT,
                "pre_harness_head": receipt.PLAN_COMMIT,
                "branch": "main", "containing_commit": "SELF"}
    require(checkpoint == expected, "baseline.checkpoint", checkpoint, str(expected))
    validate_baseline_status(baseline["status"], records)


def validate_baseline_status(value: object, records: list[tuple[str, str]]) -> None:
    status_row = exact_object_keys(value, {
        "producer_command", "normalization", "sha256", "record_count",
    }, "baseline.status")
    expected = {"producer_command": receipt.STATUS_COMMAND,
                "normalization": receipt.STATUS_NORMALIZATION,
                "sha256": sha256_bytes(normalized_git_status(records)),
                "record_count": len(records)}
    require(status_row == expected, "baseline.status", status_row, str(expected))


def validate_plan_state(value: object) -> None:
    state = exact_object_keys(value, {
        "unlazy_plan", "unlazy_runtime", "harness_archive",
    }, "baseline.ignored-state")
    plan = exact_object_keys(state["unlazy_plan"], {"path", "files"},
                             "baseline.unlazy-plan")
    expected_plan = {"path": ".unlazy/repo-cleanup-plan",
                     "files": receipt.capture_plan_files()}
    require(plan == expected_plan, "baseline.unlazy-plan", plan, str(expected_plan))
    runtime = exact_object_keys(state["unlazy_runtime"], {"path", "class", "frozen_hash"},
                                "baseline.unlazy-runtime")
    expected_runtime = {"path": ".unlazy/repo-cleanup-implementation",
                        "class": "mutable-local-execution", "frozen_hash": None}
    require(runtime == expected_runtime, "baseline.unlazy-runtime", runtime,
            str(expected_runtime))
    require(state["harness_archive"] == receipt.capture_archive(), "baseline.archive",
            state["harness_archive"], "current metadata-only archive identity")


def checked_worktree_snapshot(value: object, name: str) -> dict[str, object]:
    row = exact_object_keys(value, {
        "producer_command", "normalization", "sha256", "porcelain",
    }, name)
    require(row["producer_command"] == "git worktree list --porcelain",
            f"{name}.producer", row["producer_command"], "git worktree list --porcelain")
    require(row["normalization"] == receipt.WORKTREE_NORMALIZATION,
            f"{name}.normalization", row["normalization"], receipt.WORKTREE_NORMALIZATION)
    porcelain = row["porcelain"]
    require(isinstance(porcelain, str), f"{name}.porcelain", porcelain, "UTF-8 string")
    require(row["sha256"] == sha256_bytes(cast(str, porcelain).encode()),
            f"{name}.sha256", row["sha256"], "SHA-256 of exact porcelain bytes")
    return row


def transitioned_worktree_porcelain(porcelain: str, containing: str) -> str:
    recorded = f"worktree {ROOT}\nHEAD {receipt.PLAN_COMMIT}\nbranch refs/heads/main\n"
    require(porcelain.count(recorded) == 1, "baseline.worktree-recorded", porcelain,
            f"one main {ROOT} worktree at {receipt.PLAN_COMMIT}")
    if containing == "INDEX":
        return porcelain
    valid = len(containing) == 40 and all(character in "0123456789abcdef"
                                          for character in containing)
    require(valid, "baseline.worktree-containing", containing,
            "40-character lowercase commit SHA or INDEX")
    current = f"worktree {ROOT}\nHEAD {containing}\nbranch refs/heads/main\n"
    return porcelain.replace(recorded, current, 1)


def validate_worktree_snapshot(
    value: object, containing: str = "INDEX", current_value: object | None = None,
) -> None:
    """Allow only the checkpoint HEAD advance. Example: validate_worktree_snapshot(row)."""
    recorded = checked_worktree_snapshot(value, "baseline.worktrees")
    current = checked_worktree_snapshot(
        receipt.capture_worktrees() if current_value is None else current_value,
        "baseline.worktrees-current",
    )
    expected = transitioned_worktree_porcelain(cast(str, recorded["porcelain"]), containing)
    require(current["porcelain"] == expected, "baseline.worktree-transition",
            current["porcelain"], expected)


def validate_inventory(value: object, containing: str) -> None:
    inventory = exact_object_keys(value, {
        "producer_command", "self_excluded_paths", "byte_groups",
        "tracked_symlinks", "worktrees",
    }, "baseline.inventory")
    require(inventory["producer_command"] == receipt.CAPTURE_COMMAND,
            "baseline.inventory-producer", inventory["producer_command"],
            receipt.CAPTURE_COMMAND)
    exclusions = [str(receipt.BASELINE_RECEIPT.parent.relative_to(ROOT)),
                  str(receipt.BASELINE_RECEIPT.relative_to(ROOT))]
    require(inventory["self_excluded_paths"] == exclusions,
            "baseline.inventory-self-exclusion", inventory["self_excluded_paths"],
            str(exclusions))
    require(inventory["tracked_symlinks"] == receipt.capture_tracked_symlinks(),
            "baseline.symlinks", inventory["tracked_symlinks"], "current tracked symlinks")
    validate_worktree_snapshot(inventory["worktrees"], containing)
    validate_byte_groups(inventory["byte_groups"])


def validate_byte_groups(value: object) -> None:
    require(isinstance(value, list), "baseline.byte-groups", value, "array")
    recorded = cast(list[object], value)
    current = receipt.capture_byte_groups()
    require(len(recorded) == len(current), "baseline.byte-groups", len(recorded),
            str(len(current)))
    for observed, expected in zip(recorded, current, strict=True):
        row = exact_object_keys(observed, set(expected), "baseline.byte-group")
        require(row["path"] == expected["path"], "baseline.byte-group-path",
                row["path"], str(expected["path"]))
        if row["path"] != ".unlazy/repo-cleanup-implementation":
            require(row == expected, "baseline.byte-group", row, str(expected))


def validate_gate_row(value: object, gate: str, command: str) -> None:
    row = exact_object_keys(value, {
        "gate", "command", "result", "duration_ms", "output", "output_sha256",
        "output_sha256_producer_command", "output_sha256_normalization",
    }, f"baseline.gate.{gate}")
    expected = (gate, command, "PASS", receipt.CAPTURE_COMMAND,
                receipt.GATE_OUTPUT_NORMALIZATION)
    observed = (row["gate"], row["command"], row["result"],
                row["output_sha256_producer_command"], row["output_sha256_normalization"])
    require(observed == expected, f"baseline.gate.{gate}", observed, str(expected))
    require(isinstance(row["duration_ms"], int) and row["duration_ms"] >= 0,
            f"baseline.gate.{gate}.duration", row["duration_ms"], "nonnegative integer")
    output = row["output"]
    require(isinstance(output, str) and row["output_sha256"] == sha256_bytes(output.encode()),
            f"baseline.gate.{gate}.output", row["output_sha256"], "output SHA-256")


def validate_pin_manifest(harness: dict[str, object]) -> None:
    manifest = ROOT / "vendor/agent-sources/MANIFEST.json"
    expected = (sha256_file(manifest), receipt.sha256_producer(manifest),
                receipt.FILE_SHA256_NORMALIZATION)
    observed = (harness["pin_manifest_sha256"],
                harness["pin_manifest_sha256_producer_command"],
                harness["pin_manifest_sha256_normalization"])
    require(observed == expected, "baseline.pin-manifest", observed, str(expected))


def validate_gate_receipts(value: object) -> None:
    harness = exact_object_keys(value, {
        "gates", "retained_receipts", "pin_manifest_sha256",
        "pin_manifest_sha256_producer_command", "pin_manifest_sha256_normalization",
    }, "baseline.harness")
    require(isinstance(harness["gates"], list), "baseline.gates",
            harness["gates"], "array")
    rows = cast(list[object], harness["gates"])
    require(len(rows) == len(receipt.HARNESS_GATE_COMMANDS), "baseline.gates", len(rows),
            str(len(receipt.HARNESS_GATE_COMMANDS)))
    for (gate, command), value_row in zip(receipt.HARNESS_GATE_COMMANDS.items(), rows,
                                          strict=True):
        validate_gate_row(value_row, gate, command)
    require(harness["retained_receipts"] == receipt.capture_retained_receipts(),
            "baseline.retained-receipts", harness["retained_receipts"],
            "current retained receipt hashes")
    validate_pin_manifest(harness)


def validate_mutable_runtime(value: object) -> None:
    runtime = exact_object_keys(value, {
        "pstack_runtime", "pstack_runtime_oracle", "scratch_quarantine",
        "quarantined_scratch", "pinned_node_modules_absent",
    }, "baseline.mutable-runtime")
    expected_paths = (str(receipt.PSTACK_RUNTIME), str(receipt.PSTACK_ORACLE),
                      str(receipt.SCRATCH_QUARANTINE))
    observed_paths = (runtime["pstack_runtime"], runtime["pstack_runtime_oracle"],
                      runtime["scratch_quarantine"])
    require(observed_paths == expected_paths, "baseline.mutable-runtime-paths",
            observed_paths, str(expected_paths))
    require(receipt.PSTACK_RUNTIME.is_dir() and receipt.PSTACK_ORACLE.is_file(),
            "baseline.pstack-runtime", observed_paths[:2], "existing runtime and oracle")
    require(runtime["quarantined_scratch"] == receipt.capture_quarantined_scratch(),
            "baseline.scratch-quarantine", runtime["quarantined_scratch"],
            "current hash-bound quarantine")
    absent = not receipt.PINNED_NODE_MODULES.exists()
    require(runtime["pinned_node_modules_absent"] is True and absent,
            "baseline.pinned-runtime", runtime["pinned_node_modules_absent"], "absent")


def verify_cleanup_baseline() -> str:
    """Verify staged or committed evidence. Example: verify_cleanup_baseline()."""
    baseline = load_json_object(receipt.BASELINE_RECEIPT, "baseline.receipt")
    records, containing = baseline_records()
    validate_baseline_header(baseline, records)
    classes = cast(dict[str, object], baseline["path_classes"])
    validate_baseline_path_classes(classes, {path for _, path in records})
    validate_baseline_status_classes(classes, records)
    validate_plan_state(baseline["ignored_state"])
    validate_inventory(baseline["inventory"], containing)
    validate_gate_receipts(baseline["harness"])
    validate_mutable_runtime(baseline["mutable_runtime"])
    return f"schema=1 paths={len(records)} tree={containing}"


def verify_checkpoint_scope(parent: str, head: str) -> str:
    """Reject unaudited paths. Example: verify_checkpoint_scope(parent, head)."""
    resolved_parent = receipt.git_output(
        "rev-parse", "--verify", f"{parent}^{{commit}}"
    ).decode().strip()
    resolved_head = receipt.git_output(
        "rev-parse", "--verify", f"{head}^{{commit}}"
    ).decode().strip()
    records = receipt.commit_records(resolved_parent, resolved_head)
    outside = sorted(path for _, path in records if not checkpoint_path_allowed(path))
    require(not outside, "checkpoint-scope.paths", outside, "audited U02 allowlist")
    return f"parent={resolved_parent} head={resolved_head} paths={len(records)}"


def run_check(command: str) -> int:
    """Print one check verdict. Example: run_check('skills')."""
    label, check = CHECKS[command]
    try:
        detail = check()
    except HarnessVerificationError as error:
        print(error, file=sys.stderr)
        return 1
    except (OSError, RuntimeError, UnicodeError, TypeError, ValueError,
            subprocess.SubprocessError) as error:
        print(f"FAIL {command} offending={error!r} "
              "expected='valid installed harness state'", file=sys.stderr)
        return 1
    print(f"{label} PASS {detail}")
    return 0


def run_checkpoint_scope(parent: str, head: str) -> int:
    """Print one scope verdict. Example: run_checkpoint_scope(parent, head)."""
    try:
        detail = verify_checkpoint_scope(parent, head)
    except (HarnessVerificationError, OSError, RuntimeError, UnicodeError, TypeError, ValueError,
            subprocess.SubprocessError) as error:
        print(error, file=sys.stderr)
        return 1
    print(f"HARNESS CHECKPOINT SCOPE PASS {detail}")
    return 0


def main() -> int:
    """Dispatch the verifier CLI. Example: main()."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=(*CHECKS, "checkpoint-scope"))
    parser.add_argument("references", nargs="*")
    arguments = parser.parse_args()
    if arguments.command == "checkpoint-scope":
        if len(arguments.references) != 2:
            parser.error(
                f"checkpoint references offending={arguments.references!r}; expected PARENT and HEAD"
            )
        return run_checkpoint_scope(*arguments.references)
    if arguments.references:
        parser.error(
            f"references offending={arguments.references!r}; expected none for {arguments.command}"
        )
    return run_check(arguments.command)


if __name__ == "__main__":
    raise SystemExit(main())
