#!/usr/bin/env python3
"""Bind the repository method to Codex's hook interface.

Policy lives in `method_guard_support`, enforcement rules in
`method_guard_rules`. This file only translates between those and the payloads
Codex sends, so a rule cannot hold on Codex and lapse on Claude Code.

A policy violation denies with a reason that names the fix. Anything unexpected
allows the call and says so loudly, because a guard that fails closed on its own
bug becomes the next deadlock (D-108).
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Mapping, Sequence, TextIO, cast

sys.path.insert(0, str(Path(__file__).resolve().parent))

import method_guard_support as policy  # noqa: E402
import method_guard_rules as rules  # noqa: E402

policy.configure("codex")

PATCH_PATH = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)
MOVE_PATH = re.compile(r"^\*\*\* Move to: (.+)$", re.MULTILINE)
NO_MEMO = policy.NO_MEMO
ROUTES = policy.ROUTES
JsonObject = dict[str, object]
ENGAGE_HINT = "method_guard.py engage"


def deny(reason: str) -> JsonObject:
    """Refuse one tool call and name what clears the refusal."""
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def block(reason: str) -> JsonObject:
    """Refuse to end the turn, and say what remains."""
    return {"decision": "block", "reason": reason}


def allow_with_warning(reason: str) -> JsonObject:
    """Let a call through after an unexpected failure, and say so."""
    return {"systemMessage": f"Method guard failed open: {reason}"}


def context(event: str, text: str) -> JsonObject:
    """Return additional context for an event that accepts it."""
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}


def patch_paths(tool_input: Mapping[str, object]) -> list[str]:
    """Return every path an apply_patch payload writes."""
    raw = tool_input.get("patch", tool_input.get("input", tool_input.get("command", "")))
    if not isinstance(raw, str):
        return []
    return [*PATCH_PATH.findall(raw), *MOVE_PATH.findall(raw)]


def spawn_input(tool_name: str) -> bool:
    """Report whether this tool launches a subagent."""
    lowered = tool_name.lower()
    return "spawn_agent" in lowered or lowered in {"agent", "task"} or "subagent" in lowered


def scan_call(tool_name: str, tool_input: Mapping[str, object]) -> rules.WriteScan:
    """Classify what one Codex tool call can change."""
    patched = patch_paths(tool_input)
    if patched:
        return rules.WriteScan("paths", tuple(patched))
    command = tool_input.get("command") if isinstance(tool_input.get("command"), str) else None
    if command is not None:
        return rules.scan_command(command)
    other = tool_input.get("cmd")
    if isinstance(other, str):
        scan = rules.scan_command(other)
        return rules.WriteScan("opaque") if scan.kind == "none" else scan
    return rules.WriteScan("none") if tool_name.lower() != "bash" else rules.WriteScan("opaque")


def check_spawn(tool_input: Mapping[str, object], state: JsonObject,
                payload: Mapping[str, object]) -> None:
    """Apply the brief and model rules to one subagent launch."""
    contract = policy.current_contract(payload, state)
    brief = tool_input.get("message", tool_input.get("prompt", tool_input.get("task")))
    rules.validate_brief(brief, policy.repo_root(payload))
    rules.validate_model_policy(tool_input, contract, "model", "routine_implementation_model")
    rules.validate_model_policy(tool_input, contract, "reasoning_effort",
                                "routine_implementation_reasoning")


def check_write(paths: Sequence[str], state: JsonObject,
                payload: Mapping[str, object]) -> None:
    """Apply the route and ownership rules to one repository write."""
    if rules.bootstrap_only(paths) or rules.always_writable(paths):
        if rules.bootstrap_only(paths) and "ready" in state:
            policy.rearm(payload, state, "contract or gates edit")
        return
    if not rules.route_selected(state):
        raise ValueError(rules.default_route_reason(paths))
    if state["route"] == "plan-flow" and not rules.planning_paths(paths):
        raise ValueError(f"plan-flow denies production writes such as {paths[0]!r}. "
                         "Deliver the plan and stop, then send $implement-flow to build.")
    contract = policy.current_contract(payload, state)
    rules.validate_write_paths(paths, contract)
    state["production_write"] = True
    policy.save_state(payload, state)


def pre_tool_use(payload: Mapping[str, object]) -> JsonObject:
    """Gate one tool call against the active route and its contract."""
    tool_name = str(payload.get("tool_name") or payload.get("toolName") or "")
    try:
        tool_input = rules.cast_input(payload.get("tool_input", payload.get("toolInput", {})))
        state = policy.load_state(payload)
        if spawn_input(tool_name):
            check_spawn(tool_input, state, payload)
            return {}
        apply_scan(scan_call(tool_name, tool_input), tool_name, state, payload)
        return {}
    except ValueError as error:
        return deny(str(error))
    except Exception as error:  # noqa: BLE001
        return allow_with_warning(f"{type(error).__name__}: {error}")


def apply_scan(scan: rules.WriteScan, tool_name: str, state: JsonObject,
               payload: Mapping[str, object]) -> None:
    """Apply the gate that matches what this call can change."""
    if scan.kind == "none":
        return
    if scan.kind == "unparsed":
        raise ValueError(f"A mutating {tool_name} command exposed no path for "
                         "ownership checks. Name the file it writes.")
    if scan.kind == "opaque":
        check_opaque(state, payload)
        return
    inside = rules.repository_paths(policy.repo_root(payload), scan.paths)
    if inside:
        check_write(inside, state, payload)


def user_prompt_submit(payload: Mapping[str, object]) -> JsonObject:
    """Select a route when the prompt names one, and state this turn's laws."""
    try:
        policy.remember_session(payload)
        route = rules.route_from_prompt(str(payload.get("prompt") or ""))
        state = policy.load_state(payload)
        if route is None:
            return {}
        state.update({"route": route, "epoch": int(state.get("epoch", 0)) + 1})
        state.pop("ready", None)
        state.pop("rearm_reason", None)
        policy.save_state(payload, state)
        router = policy.repo_root(payload) / f".agents/skills/{route}/SKILL.md"
        return context("UserPromptSubmit",
                       f"Method route {route} selected. Read {router} in full, write "
                       f".unlazy/<scope>/METHOD.json and its GATES.md, then run {ENGAGE_HINT} "
                       "before the first repository write.")
    except Exception as error:  # noqa: BLE001
        return allow_with_warning(f"{type(error).__name__}: {error}")


def session_start(payload: Mapping[str, object]) -> JsonObject:
    """Re-arm the guard after a compaction or a clear."""
    return policy.session_start(payload)


def subagent_start(payload: Mapping[str, object]) -> JsonObject:
    """Tell a starting subagent the route and its ownership."""
    return policy.subagent_start(payload)


def last_message(payload: Mapping[str, object]) -> str:
    """Return the final assistant message this event reports."""
    return str(payload.get("last_assistant_message")
               or payload.get("lastAssistantMessage") or "")


def check_opaque(state: JsonObject, payload: Mapping[str, object]) -> None:
    """Require the method for a command whose effects cannot be read."""
    if not rules.route_selected(state):
        raise ValueError(f"A command whose effects cannot be read requires an explicit "
                         f"$plan-flow or $implement-flow route, and route={state.get('route')!r}.")
    policy.current_contract(payload, state)
    if state["route"] == "plan-flow":
        raise ValueError(f"plan-flow permits only read-only commands and planning "
                         f"artifacts, and route={state['route']!r} is active.")


def run_unlazy_stop(payload: Mapping[str, object]) -> JsonObject:
    """Run the pinned unlazy Stop wall for this repository."""
    return rules.run_unlazy_stop(payload, policy.repo_root(payload))


def unslop_violation(message: str) -> str | None:
    """Return the first unslop violation in a user-visible message."""
    return rules.unslop_violation(message, policy.repo_root({}))


def method_evidence_violation(payload: Mapping[str, object]) -> str | None:
    """Return the missing completion evidence, or None when the turn may end."""
    return evidence_violation(payload)


def subagent_stop(payload: Mapping[str, object]) -> JsonObject:
    """Hold a subagent to the same prose law as the parent."""
    violation = rules.unslop_violation(last_message(payload), policy.repo_root(payload))
    return block(violation) if violation else {}


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


def stop(payload: Mapping[str, object]) -> JsonObject:
    """Refuse to end a turn that leaves the method's evidence missing."""
    if payload.get("stop_hook_active"):
        return {}
    try:
        unlazy = run_unlazy_stop(payload)
        if unlazy.get("decision") == "block":
            return unlazy
        evidence = method_evidence_violation(payload)
        if evidence:
            return block(evidence)
        akita = rules.clean_code_violation(policy.repo_root(payload))
        if akita:
            return block(akita)
        violation = unslop_violation(last_message(payload))
        return block(violation) if violation else unlazy
    except Exception as error:  # noqa: BLE001
        return allow_with_warning(f"{type(error).__name__}: {error}")


EVENTS = {
    "user-prompt-submit": user_prompt_submit,
    "pre-tool-use": pre_tool_use,
    "session-start": session_start,
    "subagent-start": subagent_start,
    "subagent-stop": subagent_stop,
    "stop": stop,
}


def write_json(value: object, stdout: TextIO) -> None:
    """Emit one hook response."""
    json.dump(value, stdout, ensure_ascii=False)
    stdout.write("\n")


def run_engage(payload: Mapping[str, object], stdout: TextIO) -> int:
    """Print the exact method packet and record its digests for this session."""
    try:
        response, state = policy.prepare_engagement(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        write_json(block(str(error)), stdout)
        return 0
    write_json(response, stdout)
    stdout.flush()
    policy.save_state(payload, state)
    return 0


def main(argv: Sequence[str] | None = None, stdin: TextIO = sys.stdin,
         stdout: TextIO = sys.stdout, stderr: TextIO = sys.stderr) -> int:
    """Run one hook event, or the engage command."""
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    payload = json.load(stdin)
    if not isinstance(payload, dict):
        raise ValueError(f"hook payload must be an object, got {type(payload).__name__}")
    mapping = cast(Mapping[str, object], payload)
    if arguments == ("engage",):
        return run_engage(mapping, stdout)
    if len(arguments) != 1 or arguments[0] not in EVENTS:
        raise ValueError(f"unknown method guard command {arguments!r}")
    try:
        response = EVENTS[arguments[0]](mapping)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        response = block(str(error))
    write_json(response, stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
