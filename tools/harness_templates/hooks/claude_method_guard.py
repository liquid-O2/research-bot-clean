#!/usr/bin/env python3
"""Bind the repository method to Claude Code's real hook interface.

Policy lives in `method_guard_support`, enforcement rules in
`method_guard_rules`. This file only translates between those and the payloads
Claude Code actually sends, which were captured from live hook runs rather than
taken from documentation.

Two rules shape every decision here. A policy violation denies with a reason
that names the fix. Anything unexpected allows the call and says so loudly,
because a guard that fails closed on its own bug becomes the next deadlock
(D-108).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Mapping, Sequence, TextIO, cast

sys.path.insert(0, str(Path(__file__).resolve().parent))

import method_guard_support as policy  # noqa: E402
import method_guard_rules as rules  # noqa: E402

policy.configure("claude")

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
SPAWN_TOOLS = {"Agent", "Task"}
JsonObject = dict[str, object]
ENGAGE_HINT = "python3 .claude/hooks/method_guard.py engage <scope>"


def deny(reason: str) -> JsonObject:
    """Refuse one tool call and name what clears the refusal."""
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def allow_with_warning(reason: str) -> JsonObject:
    """Let a call through after an unexpected failure, and say so."""
    return {"systemMessage": f"Method guard failed open: {reason}"}


def context(event: str, text: str) -> JsonObject:
    """Return additional context for an event that accepts it."""
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}


def block(reason: str) -> JsonObject:
    """Refuse to end the turn, and say what remains."""
    return {"decision": "block", "reason": reason, "systemMessage": reason}


def tool_name(payload: Mapping[str, object]) -> str:
    """Return the tool being called."""
    return str(payload.get("tool_name") or payload.get("toolName") or "")


def prompt_text(payload: Mapping[str, object]) -> str:
    """Return the submitted prompt, tolerating either documented field name."""
    return str(payload.get("prompt") or payload.get("prompt_text") or "")


def edit_paths(tool_input: Mapping[str, object]) -> list[str]:
    """Return every file a write tool touches, batched edits included."""
    single = tool_input.get("file_path")
    paths = [single] if isinstance(single, str) else []
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        paths.extend(row.get("file_path") for row in edits
                     if isinstance(row, dict) and isinstance(row.get("file_path"), str))
    return [path for path in paths if isinstance(path, str)]


def write_targets(name: str, tool_input: Mapping[str, object]) -> list[str] | None:
    """Return the paths this call writes, or None when it writes nothing."""
    if name in WRITE_TOOLS:
        return edit_paths(tool_input)
    if name != "Bash":
        return None
    command = tool_input.get("command")
    if not isinstance(command, str):
        return None
    if rules.readonly_command(command):
        return None
    return rules.command_write_paths(command)


def check_spawn(tool_input: Mapping[str, object], state: JsonObject,
                payload: Mapping[str, object]) -> None:
    """Apply the brief, ownership and model rules to one subagent launch."""
    root = policy.repo_root(payload)
    contract = policy.current_contract(payload, state)
    rules.validate_brief(tool_input.get("prompt"), root)
    rules.validate_model_policy(tool_input, contract, "subagent_type", "subagent_type")
    rules.validate_model_policy(tool_input, contract, "model", "routine_implementation_model")


def check_write(paths: Sequence[str], state: JsonObject,
                payload: Mapping[str, object]) -> JsonObject | None:
    """Apply the route and ownership rules to one repository write."""
    if rules.bootstrap_only(paths) or rules.always_writable(paths):
        return rearm_on_contract_edit(paths, state, payload)
    if not rules.route_selected(state):
        raise ValueError(rules.default_route_reason(paths))
    if state["route"] == "plan-flow" and not rules.planning_paths(paths):
        raise ValueError("plan-flow denies production writes. Deliver the plan and stop. "
                         "Send $implement-flow when you are ready to build.")
    contract = policy.current_contract(payload, state)
    rules.validate_write_paths(paths, contract)
    state["production_write"] = True
    policy.save_state(payload, state)
    return None


def rearm_on_contract_edit(paths: Sequence[str], state: JsonObject,
                           payload: Mapping[str, object]) -> None:
    """Clear readiness when the contract or its gates change under us."""
    if rules.bootstrap_only(paths) and "ready" in state:
        policy.rearm(payload, state, "contract or gates edit")
    return None


def pre_tool_use(payload: Mapping[str, object]) -> JsonObject:
    """Gate one tool call against the active route and its contract."""
    name = tool_name(payload)
    try:
        tool_input = rules.cast_input(payload.get("tool_input", payload.get("toolInput", {})))
        state = policy.load_state(payload)
        if name in SPAWN_TOOLS:
            check_spawn(tool_input, state, payload)
            return {}
        targets = write_targets(name, tool_input)
        if targets is None:
            return {}
        inside = rules.repository_paths(policy.repo_root(payload), targets)
        if not inside:
            return {}
        return check_write(inside, state, payload) or {}
    except ValueError as error:
        return deny(str(error))
    except Exception as error:  # noqa: BLE001
        return allow_with_warning(f"{type(error).__name__}: {error}")


def user_prompt_submit(payload: Mapping[str, object]) -> JsonObject:
    """Record the session, select a route when the prompt names one, and remind."""
    try:
        policy.remember_session(payload)
        route = rules.route_from_prompt(prompt_text(payload))
        state = policy.load_state(payload)
        if route is not None:
            select_route(payload, state, route)
        return context("UserPromptSubmit", turn_reminder(state, route))
    except Exception as error:  # noqa: BLE001
        return allow_with_warning(f"{type(error).__name__}: {error}")


def select_route(payload: Mapping[str, object], state: JsonObject, route: str) -> None:
    """Start a new route epoch, which clears any previous readiness."""
    state.update({"route": route, "epoch": int(state.get("epoch", 0)) + 1})
    state.pop("ready", None)
    state.pop("rearm_reason", None)
    policy.save_state(payload, state)


def turn_reminder(state: JsonObject, route: str | None) -> str:
    """Return the standing laws for this turn, and the route's next step."""
    laws = ("Mandatory this turn: $unslop governs every sentence you write to the user and "
            "every MEMORY.md line. $writing-for-agents governs every skill, contract, plan and "
            "subagent brief. $unlazy gates any substantial work.")
    if route is not None:
        return (f"{laws} Route {route} selected. Read .agents/skills/{route}/SKILL.md in full, "
                f"then run {ENGAGE_HINT} before the first repository write.")
    active = state.get("route")
    if active in policy.ROUTES:
        return f"{laws} Route {active} is active."
    return (f"{laws} No route is selected. A repository write will select $implement-flow and be "
            "denied until its method enters this session.")


def session_start(payload: Mapping[str, object]) -> JsonObject:
    """Re-arm the guard after a compaction or a clear, and say what that means."""
    try:
        policy.remember_session(payload)
        source = str(payload.get("source") or "")
        state = policy.load_state(payload)
        if source not in {"compact", "clear"} or not rules.route_selected(state):
            return {}
        policy.rearm(payload, state, source)
        return context("SessionStart", rearm_notice(str(state["route"]), source))
    except Exception as error:  # noqa: BLE001
        return allow_with_warning(f"{type(error).__name__}: {error}")


def rearm_notice(route: str, source: str) -> str:
    """Explain that the method left context and must return before any write."""
    return (f"Method guard re-armed after {source}. Route {route} is still selected, but its "
            f"exact sources are no longer in this session. Run {ENGAGE_HINT} before the next "
            "repository write. What you remember of the method does not count.")


def stop(payload: Mapping[str, object]) -> JsonObject:
    """Refuse to end a turn that leaves the method's evidence missing."""
    if payload.get("stop_hook_active"):
        return {}
    try:
        root = policy.repo_root(payload)
        violation = rules.unslop_violation(last_message(payload), root)
        if violation:
            return block(violation)
        unlazy = rules.run_unlazy_stop(payload, root)
        if unlazy.get("decision") == "block":
            return unlazy
        evidence = evidence_violation(payload)
        return block(evidence) if evidence else unlazy
    except Exception as error:  # noqa: BLE001
        return allow_with_warning(f"{type(error).__name__}: {error}")


def evidence_violation(payload: Mapping[str, object]) -> str | None:
    """Return the missing completion evidence, or None when the turn may end."""
    state = policy.load_state(payload)
    if not rules.route_selected(state) or not state.get("production_write"):
        return None
    try:
        contract = policy.current_contract(payload, state)
    except ValueError as error:
        return str(error)
    return rules.review_receipt_violation(payload, contract)


def last_message(payload: Mapping[str, object]) -> str:
    """Return the final assistant message this event reports."""
    return str(payload.get("last_assistant_message")
               or payload.get("lastAssistantMessage") or "")


def subagent_stop(payload: Mapping[str, object]) -> JsonObject:
    """Hold a subagent to the same prose law as the parent."""
    if payload.get("stop_hook_active"):
        return {}
    try:
        violation = rules.unslop_violation(last_message(payload), policy.repo_root(payload))
        return block(violation) if violation else {}
    except Exception as error:  # noqa: BLE001
        return allow_with_warning(f"{type(error).__name__}: {error}")


def engage(scope: str | None, root: Path, stdout: TextIO) -> int:
    """Print the exact method packet and record its digests for this session."""
    payload = {"session_id": policy.current_session(root), "cwd": str(root), "scope": scope}
    response, state = policy.prepare_engagement(payload)
    json.dump(response, stdout, ensure_ascii=False, indent=2)
    stdout.write("\n")
    policy.save_state(payload, state)
    return 0


EVENTS = {
    "session-start": session_start,
    "user-prompt-submit": user_prompt_submit,
    "pre-tool-use": pre_tool_use,
    "subagent-stop": subagent_stop,
    "stop": stop,
}


def run_engage(arguments: Sequence[str], stdout: TextIO, stderr: TextIO) -> int:
    """Handle the engage verb, which the agent calls as a shell command."""
    scope = arguments[1] if len(arguments) > 1 else None
    root = Path(os.environ.get(policy.env_name("REPO_ROOT")) or Path.cwd()).resolve()
    try:
        return engage(scope, root, stdout)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        stderr.write(f"engage refused: {error}\n")
        return 1


def main(argv: Sequence[str] | None = None, stdin: TextIO = sys.stdin,
         stdout: TextIO = sys.stdout, stderr: TextIO = sys.stderr) -> int:
    """Run one hook event, or the engage command."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        raise ValueError(f"expected one of {sorted([*EVENTS, 'engage'])}, got no argument")
    if arguments[0] == "engage":
        return run_engage(arguments, stdout, stderr)
    if arguments[0] not in EVENTS:
        raise ValueError(f"unknown event {arguments[0]!r}, expected one of {sorted(EVENTS)}")
    payload = json.load(stdin)
    if not isinstance(payload, dict):
        raise ValueError(f"hook payload must be an object, got {type(payload).__name__}")
    json.dump(EVENTS[arguments[0]](cast(Mapping[str, object], payload)), stdout,
              ensure_ascii=False)
    stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
