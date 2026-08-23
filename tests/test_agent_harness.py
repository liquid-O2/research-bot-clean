from __future__ import annotations

import re
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import agent_harness_verify_static
import agent_harness_verify_runtime
import agent_harness_verify_common
from agent_harness_verify_common import HarnessVerificationError
from agent_harness_verify_common import CODEX_HOOK_MODULES
import install_agent_harness
import verify_agent_harness


REQUIRED_SETUP_SKILLS = {"setup-pstack", "setup-matt-pocock-skills"}
UNRELATED_TRUST_CONFIG = """model = "gpt-5.6-sol"

[hooks.state]

[hooks.state."/other/.codex/hooks.json:stop:0:0"]
trusted_hash = "sha256:other"

[hooks.state."/workspace/.codex/hooks.json:stop:0:0"]
trusted_hash = "sha256:workspace"
"""
WORKSPACE_HOOK_PATH = "/workspace/.codex/hooks.json"
HOOK_EVENTS = {
    "pre_compact": "preCompact",
    "pre_tool_use": "preToolUse",
    "post_compact": "postCompact",
    "session_start": "sessionStart",
    "stop": "stop",
    "subagent_start": "subagentStart",
    "subagent_stop": "subagentStop",
    "user_prompt_submit": "userPromptSubmit",
}
HOOK_HANDLER_COUNTS = {name: 2 if name in {"session_start", "pre_compact"} else 1
                       for name in HOOK_EVENTS}
HookOwner = tuple[int, str, int | None]
HOOK_POLICY: dict[str, tuple[str | None, tuple[HookOwner, ...]]] = {
    "SessionStart": ("^(startup|resume|clear|compact)$", (
        (20, "memory_ledger_hooks.py session-start", 12000),
        (10, "method_guard.py session-start", 6000),
    )),
    "UserPromptSubmit": (None, ((10, "method_guard.py user-prompt-submit", 6000),)),
    "PreToolUse": ("^(Bash|apply_patch|Agent)$", ((15, "method_guard.py pre-tool-use", None),)),
    "SubagentStart": (None, ((10, "method_guard.py subagent-start", 6000),)),
    "SubagentStop": (None, ((15, "method_guard.py subagent-stop", None),)),
    "PreCompact": ("^(manual|auto)$", (
        (30, "optmem_lifecycle.py pre-compact", None),
        (30, "memory_ledger_hooks.py pre-compact", None),
    )),
    "PostCompact": ("^(manual|auto)$", ((10, "optmem_lifecycle.py post-compact", None),)),
    "Stop": (None, ((30, "method_guard.py stop", None),)),
}
REAL_RMTREE = shutil.rmtree


class PauseAfterRemoval:
    def __init__(self) -> None:
        self.removed = threading.Event()
        self.release = threading.Event()

    def __call__(self, path: Path) -> None:
        REAL_RMTREE(path)
        self.removed.set()
        if not self.release.wait(timeout=5):
            raise TimeoutError(f"cleanup for {path} did not receive release")


class FakeCodexSkillsProcess:
    @staticmethod
    def load_receipt() -> dict[str, object]:
        return {}

    @staticmethod
    def locate(_: str) -> str:
        return "/usr/bin/codex"

    @staticmethod
    def probe(_: str) -> tuple[dict[str, object], bytes]:
        return codex_skills_fixture(), b"raw notification"


def trusted_hook_fixture() -> tuple[dict[str, object], dict[str, str]]:
    hooks: list[dict[str, object]] = []
    trust: dict[str, str] = {}
    for identity, event in HOOK_EVENTS.items():
        for handler_index in range(HOOK_HANDLER_COUNTS[identity]):
            key = f"{WORKSPACE_HOOK_PATH}:{identity}:0:{handler_index}"
            current_hash = f"sha256:{len(hooks) + 1:064x}"
            trust[key] = current_hash
            hooks.append({
                "key": key, "eventName": event, "source": "project",
                "sourcePath": WORKSPACE_HOOK_PATH, "currentHash": current_hash,
                "trustStatus": "trusted",
            })
    return {"result": {"data": [{
        "cwd": "/workspace", "errors": [], "hooks": hooks,
    }]}}, trust


def codex_skills_fixture() -> dict[str, object]:
    return {"result": {"data": [{
        "cwd": "/workspace",
        "errors": [],
        "skills": [{
            "name": "plan-flow",
            "path": "/workspace/.agents/skills/plan-flow/SKILL.md",
            "enabled": True,
        }],
    }]}}


def baseline_path_classes_fixture() -> dict[str, list[str]]:
    return {
        "tracked_deletions": ["CLAUDE.md"],
        "tracked_modifications": [".gitignore"],
        "staged_additions": ["tests/test_agent_harness.py"],
        "ignored_inputs": sorted([
            ".unlazy/repo-cleanup-plan",
            ".unlazy/repo-cleanup-implementation",
            "archive/agent-harness-pre-20260823",
        ]),
        "removed_or_quarantined_scratch": [
            ".codex/harness/receipts/codex-skills-prompt-input.json",
            ".codex/harness/receipts/codex-skills-prompt-input.stderr",
        ],
        "unexpected_paths": [],
        "overlapping_classes": [],
    }


def baseline_changed_paths() -> set[str]:
    classes = baseline_path_classes_fixture()
    return set(classes["tracked_deletions"] + classes["tracked_modifications"]
               + classes["staged_additions"])


def worktree_snapshot(porcelain: str) -> dict[str, object]:
    return {
        "producer_command": "git worktree list --porcelain",
        "normalization": "exact stdout bytes",
        "sha256": agent_harness_verify_common.sha256_bytes(porcelain.encode()),
        "porcelain": porcelain,
    }


def start_atomic_replacement(
    root: Path,
) -> tuple[PauseAfterRemoval, threading.Thread, Path, Path]:
    active = root / "skills"
    staging = root / ".skills.staging"
    old_entrypoint = active / "principle-prove-it-works/SKILL.md"
    new_entrypoint = staging / "principle-prove-it-works/SKILL.md"
    old_entrypoint.parent.mkdir(parents=True)
    new_entrypoint.parent.mkdir(parents=True)
    old_entrypoint.write_text("old", encoding="utf-8")
    new_entrypoint.write_text("new", encoding="utf-8")
    cleanup = PauseAfterRemoval()
    replacement = threading.Thread(
        target=install_agent_harness.replace_active_directory,
        args=(staging, active, cleanup),
    )
    replacement.start()
    return cleanup, replacement, active, staging


def worktree_transition_fixture() -> tuple[str, str, dict[str, str]]:
    containing = "1" * 40
    recorded = (
        "worktree /workspace\n"
        "HEAD 747c9c45698226db70e85c65fe29d71d58210dd0\n"
        "branch refs/heads/main\n\n"
    )
    expected = recorded.replace(
        "747c9c45698226db70e85c65fe29d71d58210dd0", containing
    )
    drifted = {
        "path": expected.replace("/workspace", "/tmp/workspace"),
        "branch": expected.replace("refs/heads/main", "refs/heads/topic"),
        "sha": expected.replace(containing, "2" * 40),
        "extra": expected + "worktree /tmp/extra\nHEAD " + "3" * 40 + "\ndetached\n\n",
    }
    return containing, recorded, drifted


class SkillInventoryTests(unittest.TestCase):
    def test_expected_inventory_keeps_setup_skills(self) -> None:
        names = set(agent_harness_verify_static.expected_skill_names())

        self.assertTrue(REQUIRED_SETUP_SKILLS <= names, names)

    def test_active_inventory_keeps_setup_skills(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            active = Path(raw_directory) / "skills"

            names = set(install_agent_harness.render_active_skills(active))

        self.assertEqual(len(names), 76)
        self.assertTrue(REQUIRED_SETUP_SKILLS <= names, names)


class InstallerTrustTests(unittest.TestCase):
    def test_live_skill_tree_remains_complete_during_old_tree_cleanup(self) -> None:
        with tempfile.TemporaryDirectory(dir="/workspace/.agents") as raw_directory:
            cleanup, replacement, active, staging = start_atomic_replacement(
                Path(raw_directory)
            )
            self.assertTrue(cleanup.removed.wait(timeout=5))
            live_entrypoint = active / "principle-prove-it-works/SKILL.md"
            self.assertEqual(live_entrypoint.read_text(encoding="utf-8"), "new")
            cleanup.release.set()
            replacement.join(timeout=5)

            self.assertFalse(replacement.is_alive())
            self.assertFalse(staging.exists())

    def test_config_rewrite_preserves_unrelated_repository_trust(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            codex_config = directory / "config.toml"
            codex_config.write_text(UNRELATED_TRUST_CONFIG, encoding="utf-8")

            install_agent_harness.rewrite_mixed_configs(
                directory / "settings.local.json", codex_config
            )

            self.assertEqual(codex_config.read_text(encoding="utf-8"),
                             UNRELATED_TRUST_CONFIG)

    def test_codex_hook_install_follows_the_manifest(self) -> None:
        names = [path.name for path in install_agent_harness.codex_hook_templates()]

        self.assertEqual(names, sorted(CODEX_HOOK_MODULES))
        self.assertNotIn("cached_session_bridge.py", names)
        self.assertNotIn("claude_method_guard.py", names)
        for path in install_agent_harness.codex_hook_templates():
            self.assertTrue(path.is_file(), path)

    def test_pinned_pstack_runtime_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            runtime = Path(raw_directory) / "node_modules"
            runtime.mkdir()

            error = install_agent_harness.pinned_runtime_error(runtime)

        self.assertIn(str(runtime), error)
        self.assertIn("expected absent mutable runtime", error)


class HookTrustTests(unittest.TestCase):
    def test_pre_tool_matcher_covers_canonical_codex_aliases(self) -> None:
        matcher = HOOK_POLICY["PreToolUse"][0]
        self.assertIsNotNone(matcher)
        for tool_name in ("Bash", "apply_patch", "Agent"):
            self.assertIsNotNone(re.fullmatch(str(matcher), tool_name), tool_name)
        for tool_name in ("exec_command", "write_stdin", "spawn_agent"):
            self.assertIsNone(re.fullmatch(str(matcher), tool_name), tool_name)

    def test_hook_configs_have_exact_policy_owners_and_bounds(self) -> None:
        paths = [Path(WORKSPACE_HOOK_PATH), TOOLS / "harness_templates/hooks.json"]
        for path in paths:
            configured = agent_harness_verify_common.load_json_object(path, path.name)["hooks"]
            self.assertEqual(set(configured), set(HOOK_POLICY), path)
            handler_count = sum(len(group["hooks"]) for groups in configured.values()
                                for group in groups)
            self.assertEqual(handler_count, 10, path)
            for event, (matcher, owners) in HOOK_POLICY.items():
                with self.subTest(path=path, event=event):
                    self.assertEqual(len(configured[event]), 1)
                    group = configured[event][0]
                    self.assertEqual(group.get("matcher"), matcher)
                    self.assertEqual(len(group["hooks"]), len(owners))
                    for owner, (timeout, suffix, context_limit) in zip(group["hooks"], owners):
                        self.assertTrue(owner["command"].endswith(suffix), owner)
                        self.assertEqual(owner["timeout"], timeout)
                        self.assertEqual(owner.get("additionalContextLimit"), context_limit)

    def test_trust_state_parser_reads_named_hook_entries(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            path = Path(raw_directory) / "config.toml"
            path.write_text(UNRELATED_TRUST_CONFIG, encoding="utf-8")

            state = agent_harness_verify_runtime.load_hook_trust_state(path)

        self.assertEqual(state["/other/.codex/hooks.json:stop:0:0"],
                         "sha256:other")
        self.assertEqual(state["/workspace/.codex/hooks.json:stop:0:0"],
                         "sha256:workspace")

    def test_nine_trusted_handlers_expose_eight_events(self) -> None:
        response, trust = trusted_hook_fixture()

        rows = agent_harness_verify_runtime.validate_hook_trust(response, trust)

        expected = [event for identity, event in HOOK_EVENTS.items()
                    for _ in range(HOOK_HANDLER_COUNTS[identity])]
        self.assertEqual([row["eventName"] for row in rows], sorted(expected))

    def test_stale_stored_hash_reports_offending_and_current_values(self) -> None:
        response, trust = trusted_hook_fixture()
        key = sorted(trust)[0]
        current_hash = trust[key]
        trust[key] = "sha256:stale"

        with self.assertRaises(HarnessVerificationError) as caught:
            agent_harness_verify_runtime.validate_hook_trust(response, trust)

        message = str(caught.exception)
        self.assertIn("FAIL hooks.trust-stale", message)
        self.assertIn("sha256:stale", message)
        self.assertIn(current_hash, message)

    def test_orphan_workspace_trust_key_fails(self) -> None:
        response, trust = trusted_hook_fixture()
        orphan = f"{WORKSPACE_HOOK_PATH}:orphan:0:0"
        trust[orphan] = "sha256:orphan"

        with self.assertRaisesRegex(HarnessVerificationError,
                                    "FAIL hooks.trust-orphan") as caught:
            agent_harness_verify_runtime.validate_hook_trust(response, trust)

        self.assertIn(orphan, str(caught.exception))

    def test_unrelated_repository_trust_key_is_ignored(self) -> None:
        response, trust = trusted_hook_fixture()
        trust["/other/.codex/hooks.json:stop:0:0"] = "sha256:unrelated"

        rows = agent_harness_verify_runtime.validate_hook_trust(response, trust)

        self.assertEqual(len(rows), sum(HOOK_HANDLER_COUNTS.values()))

    def test_absent_state_keeps_static_rewrite_green_but_live_is_untrusted(self) -> None:
        response, _ = trusted_hook_fixture()
        hooks = response["result"]["data"][0]["hooks"]
        for row in hooks:
            row["trustStatus"] = "untrusted"
        with tempfile.TemporaryDirectory() as raw_directory:
            missing = Path(raw_directory) / "missing.toml"
            install_agent_harness.rewrite_mixed_configs(missing, missing)
            self.assertFalse(missing.exists())

        with self.assertRaisesRegex(HarnessVerificationError,
                                    "FAIL hooks.trust-status"):
            agent_harness_verify_runtime.validate_hook_trust(response, {})


class CodexSkillsTests(unittest.TestCase):
    def test_verification_leaves_retained_receipt_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            harness = Path(raw_directory)
            receipts = harness / "receipts"
            receipts.mkdir()
            receipt = receipts / "codex-skills-list.jsonl"
            original = b'{"name":"retained"}\n'
            receipt.write_bytes(original)
            fake_io = agent_harness_verify_runtime.CodexSkillsIO(
                FakeCodexSkillsProcess.load_receipt,
                FakeCodexSkillsProcess.locate,
                FakeCodexSkillsProcess.probe,
                ["plan-flow"],
                harness,
            )

            agent_harness_verify_runtime.verify_codex_skills(fake_io)

            self.assertEqual(receipt.read_bytes(), original)

    def test_explicit_capture_records_only_normalized_skill_fields(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            harness = Path(raw_directory)
            fake_io = agent_harness_verify_runtime.CodexSkillsIO(
                FakeCodexSkillsProcess.load_receipt,
                FakeCodexSkillsProcess.locate,
                FakeCodexSkillsProcess.probe,
                ["plan-flow"],
                harness,
            )

            agent_harness_verify_runtime.capture_codex_skills(fake_io)

            rows = (harness / "receipts/codex-skills-list.jsonl").read_text().splitlines()
            self.assertEqual(rows, [
                '{"enabled":true,"name":"plan-flow","path":"/workspace/.agents/skills/plan-flow/SKILL.md"}'
            ])


class LifecycleClaimTests(unittest.TestCase):
    def test_retained_receipt_claims_only_codex_event_order(self) -> None:
        detail = agent_harness_verify_runtime.verify_lifecycle()

        self.assertIn("proof=codex-0.149-event-order-only", detail)
        self.assertIn("live_optmem_unlazy=not-claimed", detail)

    def test_upstream_receipt_claim_does_not_claim_suite_reruns(self) -> None:
        detail = agent_harness_verify_static.verify_upstream_receipts()

        self.assertIn("proof=retained-receipts-only", detail)
        self.assertIn("upstream_suites=not-rerun", detail)


class CleanupBaselinePathTests(unittest.TestCase):
    def test_byte_metrics_exclude_directory_allocator_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as raw_directory:
            root = Path(raw_directory)
            nested = root / "nested"
            nested.mkdir()
            payload = nested / "payload.txt"
            payload.write_bytes(b"payload")
            link = nested / "link"
            link.symlink_to("payload.txt")
            expected_apparent = payload.lstat().st_size + link.lstat().st_size
            expected_allocated = (payload.lstat().st_blocks + link.lstat().st_blocks) * 512

            metrics = agent_harness_verify_common.path_tree_metrics(root)

        self.assertEqual(metrics["apparent_bytes"], expected_apparent)
        self.assertEqual(metrics["allocated_bytes"], expected_allocated)

    def test_worktree_snapshot_remains_valid_after_live_head_advances(self) -> None:
        containing = "1" * 40
        porcelain = (
            "worktree /workspace\n"
            "HEAD 747c9c45698226db70e85c65fe29d71d58210dd0\n"
            "branch refs/heads/main\n\n"
        )
        current = porcelain.replace(
            "747c9c45698226db70e85c65fe29d71d58210dd0", containing
        )

        verify_agent_harness.validate_worktree_snapshot(
            worktree_snapshot(porcelain), containing, worktree_snapshot(current)
        )

    def test_worktree_transition_rejects_path_branch_sha_and_extra_tree_drift(self) -> None:
        containing, recorded, drifted = worktree_transition_fixture()

        for name, current in drifted.items():
            with self.subTest(name=name), self.assertRaisesRegex(
                HarnessVerificationError, "FAIL baseline.worktree-transition"
            ):
                verify_agent_harness.validate_worktree_snapshot(
                    worktree_snapshot(recorded), containing, worktree_snapshot(current)
                )

    def test_status_classes_match_git_status(self) -> None:
        classes = baseline_path_classes_fixture()
        records = [
            ("M", ".gitignore"),
            ("D", "CLAUDE.md"),
            ("A", "tests/test_agent_harness.py"),
        ]

        agent_harness_verify_common.validate_baseline_status_classes(
            classes, records
        )

    def test_path_classes_reject_missing_path(self) -> None:
        classes = baseline_path_classes_fixture()
        classes["staged_additions"] = []

        with self.assertRaisesRegex(HarnessVerificationError,
                                    "FAIL baseline.path-classification"):
            agent_harness_verify_common.validate_baseline_path_classes(
                classes, baseline_changed_paths()
            )

    def test_path_classes_reject_duplicate_path(self) -> None:
        classes = baseline_path_classes_fixture()
        classes["tracked_modifications"].append(".gitignore")

        with self.assertRaisesRegex(HarnessVerificationError,
                                    "FAIL baseline.path-duplicate"):
            agent_harness_verify_common.validate_baseline_path_classes(
                classes, baseline_changed_paths()
            )

    def test_path_classes_reject_overlapping_classes(self) -> None:
        classes = baseline_path_classes_fixture()
        classes["staged_additions"].append(".gitignore")

        with self.assertRaisesRegex(HarnessVerificationError,
                                    "FAIL baseline.path-overlap"):
            agent_harness_verify_common.validate_baseline_path_classes(
                classes, baseline_changed_paths()
            )

    def test_path_classes_reject_out_of_scope_path(self) -> None:
        classes = baseline_path_classes_fixture()
        classes["staged_additions"].append("src/out-of-scope.py")
        changed = baseline_changed_paths() | {"src/out-of-scope.py"}

        with self.assertRaisesRegex(HarnessVerificationError,
                                    "FAIL baseline.commit-scope"):
            agent_harness_verify_common.validate_baseline_path_classes(classes, changed)


if __name__ == "__main__":
    unittest.main()
