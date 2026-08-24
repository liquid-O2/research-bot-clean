#!/usr/bin/env python3
"""Drive one installed method guard, whichever client owns it.

These primitives build the payloads a client really sends, run the installed
hook script the way the client runs it, and read back the verdict the agent
would receive. `method_canaries` says what to drive; this says how.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Callable, Sequence, TextIO

ROOT = Path(__file__).resolve().parent.parent
SCOPE = "method-canary"
CHUNK_END = "<<<METHOD_PACKET_CHUNK_END>>>"
PACKET_END = "<<<METHOD_PACKET_END"
CREATED_METHOD_SCOPES: set[Path] = set()
ENGAGED_STATE_SNAPSHOTS: dict[str, Path] = {}
ENGAGED_PACKETS: dict[str, subprocess.CompletedProcess[str]] = {}


@dataclass(frozen=True)
class Client:
    """Where one client's guard lives and how it names its inputs."""

    name: str
    guard: Path
    env_prefix: str
    write_tool: str
    spawn_tool: str
    brief_key: str
    chunked_engage: bool


CLIENTS = {
    "claude": Client("claude", ROOT / ".claude/hooks/method_guard.py", "CLAUDE_METHOD",
                     "Write", "Agent", "prompt", chunked_engage=True),
    "codex": Client("codex", ROOT / ".codex/hooks/method_guard.py", "CODEX_METHOD",
                    "apply_patch", "collaboration.spawn_agent", "message", chunked_engage=True),
}
ACTIVE = CLIENTS["claude"]
NO_MEMO = "You are a subagent. Don't run memo."
GOOD_BRIEF = (f"{NO_MEMO}\n"
              "Own: tools/scratch_canary.py\n"
              "You are not alone in the codebase.\n"
              "Do not revert others' edits.\n"
              "Acceptance check: every named test passes and the diff touches only that file.\n")


@dataclass(frozen=True)
class Canary:
    """One observable claim about what the guard permits or refuses."""

    name: str
    verb: str
    payload: dict[str, object]
    expect: str
    contains: str = ""
    setup: Callable[[Path], None] | None = None
    scope: str = ""


@dataclass
class Outcome:
    """What one canary actually produced."""

    canary: Canary
    verdict: str
    reason: str
    passed: bool = field(init=False)

    def __post_init__(self) -> None:
        self.passed = (self.verdict == self.canary.expect
                       and self.canary.contains in self.reason)


def tool_payload(tool: str, tool_input: dict[str, object], **extra: object) -> dict[str, object]:
    """Build a PreToolUse payload in the shape the client actually sends."""
    return {"hook_event_name": "PreToolUse", "session_id": "canary", "cwd": str(ROOT),
            "permission_mode": "bypassPermissions", "tool_name": tool,
            "tool_input": tool_input, **extra}


def write_payload(path: str, **extra: object) -> dict[str, object]:
    """Build a write payload in the active client's own shape."""
    if ACTIVE.write_tool == "apply_patch":
        relative = relative_to_root(path)
        return tool_payload("apply_patch",
                            {"patch": f"*** Add File: {relative}\n+canary\n"}, **extra)
    return tool_payload("Write", {"file_path": path, "content": "canary\n"}, **extra)


def relative_to_root(path: str) -> str:
    """Return a repository-relative path for a patch header."""
    candidate = Path(path)
    if candidate.is_absolute() and candidate.is_relative_to(ROOT):
        return candidate.relative_to(ROOT).as_posix()
    return candidate.as_posix()


def spawn_payload(brief: str, subagent: str = "method-worker",
                  model: str = "opus") -> dict[str, object]:
    """Build a subagent launch payload in the active client's own shape."""
    if ACTIVE.name == "codex":
        return tool_payload(ACTIVE.spawn_tool,
                            {"message": brief, "model": "gpt-5.6-sol",
                             "reasoning_effort": "medium", "task_name": "canary"})
    return tool_payload(ACTIVE.spawn_tool, {"prompt": brief, "subagent_type": subagent,
                                            "model": model, "description": "canary"})


def prompt_payload(text: str, mode: str = "bypassPermissions") -> dict[str, object]:
    """Build a UserPromptSubmit payload."""
    return {"hook_event_name": "UserPromptSubmit", "session_id": "canary", "cwd": str(ROOT),
            "permission_mode": mode, "prompt": text}


def stop_payload(message: str, event: str = "Stop") -> dict[str, object]:
    """Build a Stop or SubagentStop payload carrying a final message."""
    return {"hook_event_name": event, "session_id": "canary", "cwd": str(ROOT),
            "last_assistant_message": message, "stop_hook_active": False}


def run_guard(verb: str, payload: dict[str, object], state: Path,
              scope: str = "") -> dict[str, object]:
    """Run the installed hook script exactly as the client runs it."""
    environment = guard_environment(state)
    if scope:
        environment["UNLAZY_SCOPE"] = scope
    result = subprocess.run((sys.executable, str(ACTIVE.guard), verb),
                            input=json.dumps(payload), text=True, capture_output=True,
                            env=environment, timeout=30, check=False)
    if result.returncode != 0:
        return {"_error": result.stderr.strip() or f"exit {result.returncode}"}
    return json.loads(result.stdout or "{}")


def guard_environment(state: Path) -> dict[str, str]:
    """Return the environment that points one guard at this canary run."""
    return {**os.environ, f"{ACTIVE.env_prefix}_STATE_ROOT": str(state),
            f"{ACTIVE.env_prefix}_REPO_ROOT": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}


def method_scope_name(state: Path) -> str:
    digest = sha256(str(state.parent.resolve()).encode()).hexdigest()[:16]
    return f"method-canary-{digest}"


def method_scope_key(scope: str) -> str:
    digest = sha256()
    for name in ("METHOD.json", "GATES.md"):
        digest.update((ROOT / ".unlazy" / scope / name).read_bytes())
    return f"{scope}:{digest.hexdigest()}"


def canary_contract(scope: str) -> dict[str, object]:
    principles = ("principle-fix-root-causes", "principle-prove-it-works")
    return {
        "schema_version": 1, "route": "implement-flow", "playbook": "bug-fix",
        "outer_method": ["implement-flow", "poteto-mode", "playbook:bug-fix"],
        "nested_method": {"implementation": ["tdd", "pocock-tdd", "implement"],
                          "review": ["code-review"]},
        "standing_laws": ["unlazy", "clean-code-for-agents", "unslop",
                          "writing-for-agents"],
        "principles": [{"name": name, "decision": "exercise the installed guard",
                        "evidence": "tools/run_method_canaries.py"} for name in principles],
        "owns": ["tools/**", "CLAUDE.md"], "gates": f".unlazy/{scope}/GATES.md",
        "model_policy": {"routine_implementation_model": "gpt-5.6-sol",
                         "routine_implementation_reasoning": "medium",
                         "claude": {"routine_implementation_model": "opus"}},
    }


def write_method_scope(state: Path) -> str:
    scope = method_scope_name(state)
    directory = ROOT / ".unlazy" / scope
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "METHOD.json").write_text(
        json.dumps(canary_contract(scope), indent=2) + "\n", encoding="utf-8")
    (directory / "GATES.md").write_text(
        "# Canary gates\n\n- [x] G1: installed method fixture\n"
        "  CHECK: true\n  EXPECT: exit 0\n"
        "  EVIDENCE: isolated canary fixture\n", encoding="utf-8")
    CREATED_METHOD_SCOPES.add(directory)
    return scope


def drop_method_scopes() -> None:
    for directory in tuple(CREATED_METHOD_SCOPES):
        shutil.rmtree(directory, ignore_errors=True)
        CREATED_METHOD_SCOPES.discard(directory)
    ENGAGED_PACKETS.clear()
    ENGAGED_STATE_SNAPSHOTS.clear()


def direct_chunk_body(response: str) -> str:
    try:
        _, remainder = response.split("\n", 1)
        body, _ = remainder.split(f"\n{CHUNK_END}\n", 1)
    except ValueError as error:
        raise ValueError(f"malformed engage chunk {response!r}") from error
    return body


def collect_chunked_engage(command: tuple[str, ...], environment: dict[str, str]
                           ) -> subprocess.CompletedProcess[str]:
    chunks: list[str] = []
    for number in range(1, 33):
        arguments = command if number == 1 else (*command, str(number))
        result = subprocess.run(arguments, text=True, capture_output=True,
                                env=environment, timeout=30, check=False)
        if result.returncode != 0:
            return result
        chunks.append(direct_chunk_body(result.stdout))
        if PACKET_END in result.stdout:
            return subprocess.CompletedProcess(command, 0, "".join(chunks), result.stderr)
    return subprocess.CompletedProcess(command, 1, "", "engage exceeded 32 chunks")


def restore_engaged_state(state: Path, key: str) -> subprocess.CompletedProcess[str] | None:
    snapshot = ENGAGED_STATE_SNAPSHOTS.get(key)
    packet = ENGAGED_PACKETS.get(key)
    if snapshot is None or packet is None:
        return None
    shutil.copytree(snapshot, state, dirs_exist_ok=True)
    return packet


def remember_engaged_state(
    state: Path, key: str, result: subprocess.CompletedProcess[str],
) -> None:
    suffix = sha256(key.encode()).hexdigest()[:16]
    snapshot = state.parent / f".engaged-{suffix}"
    shutil.copytree(state, snapshot)
    ENGAGED_STATE_SNAPSHOTS[key] = snapshot
    ENGAGED_PACKETS[key] = result


def run_engage_command(
    command: tuple[str, ...], environment: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    if ACTIVE.chunked_engage:
        return collect_chunked_engage(command, environment)
    return subprocess.run(
        command, text=True, capture_output=True,
        env=environment, timeout=30, check=False,
    )


def require_engage_success(
    result: subprocess.CompletedProcess[str],
) -> None:
    if result.returncode == 0:
        return
    detail = result.stderr.strip() or result.stdout.strip() or "no output"
    raise RuntimeError(f"engage failed with exit {result.returncode}: {detail}")


def engage(state: Path, scope: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run the engage command the denial messages tell the agent to run."""
    selected_scope = scope or method_scope_name(state)
    if scope is None and not (ROOT / ".unlazy" / selected_scope).exists():
        write_method_scope(state)
    key = method_scope_key(selected_scope)
    cached = restore_engaged_state(state, key)
    if cached is not None:
        return cached
    environment = guard_environment(state)
    command = (sys.executable, str(ACTIVE.guard), "engage", selected_scope)
    result = run_engage_command(command, environment)
    require_engage_success(result)
    remember_engaged_state(state, key, result)
    return result


def read_verdict(response: dict[str, object]) -> tuple[str, str]:
    """Reduce a hook response to a verdict and the reason the agent would see."""
    if "_error" in response:
        return "error", str(response["_error"])
    specific = response.get("hookSpecificOutput")
    if isinstance(specific, dict):
        decision = specific.get("permissionDecision")
        if decision:
            return str(decision), str(specific.get("permissionDecisionReason", ""))
        return "context", str(specific.get("additionalContext", ""))
    if response.get("decision") == "block":
        return "block", str(response.get("reason", ""))
    if "systemMessage" in response:
        return "warn", str(response["systemMessage"])
    return "allow", ""


def select(state: Path, route: str) -> None:
    """Put the session on one route, as a user prompt would."""
    run_guard("user-prompt-submit", prompt_payload(f"please ${route} now"), state)


def compact(state: Path) -> None:
    """Simulate the SessionStart the client sends after a compaction."""
    run_guard("session-start", {"hook_event_name": "SessionStart", "session_id": "canary",
                                "cwd": str(ROOT), "source": "compact"}, state)




def command_payload(command: str) -> dict[str, object]:
    """Build a shell-command payload in the active client's own shape."""
    return tool_payload("Bash" if ACTIVE.name == "claude" else "shell", {"command": command})


def active() -> Client:
    """Return the client every primitive is currently pointed at.

    Read through a function, never imported by value. A value import froze the
    Codex run on the Claude client and it passed anyway, which is the quietest
    kind of wrong.
    """
    return ACTIVE


def select_client(name: str) -> Client:
    """Point every primitive at one client's installed guard."""
    global ACTIVE
    ACTIVE = CLIENTS[name]
    return ACTIVE
