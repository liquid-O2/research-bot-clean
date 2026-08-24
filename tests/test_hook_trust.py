from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import agent_harness_verify_common
import agent_harness_verify_runtime
from agent_harness_verify_common import HarnessVerificationError
import install_agent_harness


UNRELATED_TRUST_CONFIG = """model = "gpt-5.6-sol"

[hooks.state]

[hooks.state."/other/.codex/hooks.json:stop:0:0"]
trusted_hash = "sha256:other"

[hooks.state."/workspace/.codex/hooks.json:stop:0:0"]
trusted_hash = "sha256:workspace"
"""
WORKSPACE_HOOK_PATH = "/workspace/.codex/hooks.json"
HOOK_EVENTS = dict(
    pre_compact="preCompact", pre_tool_use="preToolUse", session_end="sessionEnd",
    session_start="sessionStart", stop="stop", subagent_start="subagentStart",
    subagent_stop="subagentStop", user_prompt_submit="userPromptSubmit",
)
HOOK_HANDLER_COUNTS = {
    name: 2 if name in {"session_start", "subagent_stop"} else 1
    for name in HOOK_EVENTS
}
HookOwner = tuple[int, str, int | None]
HOOK_POLICY: dict[str, tuple[str | None, tuple[HookOwner, ...]]] = {
    "SessionStart": ("^(startup|resume|clear|compact)$", (
        (20, "memory_ledger_hooks.py session-start", 12000),
        (10, "method_guard.py session-start", 0),
    )),
    "UserPromptSubmit": (None, ((10, "method_guard.py user-prompt-submit", 6000),)),
    "PreToolUse": ("^(Bash|apply_patch|Agent)$", ((15, "method_guard.py pre-tool-use", None),)),
    "SubagentStart": (None, ((10, "method_guard.py subagent-start", 0),)),
    "SubagentStop": (None, (
        (15, "method_guard.py subagent-stop", None),
        (15, "memory_ledger_hooks.py subagent-stop", None),
    )),
    "PreCompact": ("^(manual|auto)$", ((30, "memory_ledger_hooks.py pre-compact", None),)),
    "SessionEnd": (None, ((3, "memory_ledger_hooks.py session-end", None),)),
    "Stop": (None, ((30, "method_guard.py stop", None),)),
}


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

        self.assertEqual(state["/other/.codex/hooks.json:stop:0:0"], "sha256:other")
        self.assertEqual(state["/workspace/.codex/hooks.json:stop:0:0"], "sha256:workspace")

    def test_ten_trusted_handlers_expose_eight_events(self) -> None:
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

        with self.assertRaisesRegex(HarnessVerificationError, "FAIL hooks.trust-status"):
            agent_harness_verify_runtime.validate_hook_trust(response, {})


if __name__ == "__main__":
    unittest.main()
