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
    """Classify what one Codex tool call can change.

    A patch names its paths exactly, so it gets an ownership check. A shell
    command does not, so it only has to have the method in context.
    """
    patched = patch_paths(tool_input)
    if patched:
        return rules.WriteScan("paths", tuple(patched))
    command = tool_input.get("command", tool_input.get("cmd"))
    if isinstance(command, str):
        return rules.scan_command(command)
    return rules.WriteScan("none") if tool_name.lower() != "bash" else rules.WriteScan("opaque")


def check_spawn(tool_input: Mapping[str, object], state: JsonObject,
                payload: Mapping[str, object]) -> None:
    """Apply the brief and model rules to one subagent launch."""
    contract = policy.current_contract(payload, state)
    brief = tool_input.get("message", tool_input.get("prompt", tool_input.get("task")))
    rules.validate_brief(brief, policy.repo_root(payload))
    rules.validate_model_policy(tool_input, contract, "model",
                                "routine_implementation_model", "codex")
    rules.validate_model_policy(tool_input, contract, "reasoning_effort",
                                "routine_implementation_reasoning", "codex")


def check_write(paths: Sequence[str], state: JsonObject,
                payload: Mapping[str, object]) -> None:
    """Apply the route and ownership rules to one repository write."""
    if rules.bootstrap_only(paths) or rules.always_writable(paths):
        if rules.bootstrap_only(paths) and active_method_artifact(paths, state):
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
    state["written_paths"] = sorted({*state.get("written_paths", []), *paths})
    policy.save_state(payload, state)


def active_method_artifact(paths: Sequence[str], state: JsonObject) -> bool:
    scope = state.get("scope")
    if not isinstance(scope, str):
        return False
    active = {f".unlazy/{scope}/METHOD.json", f".unlazy/{scope}/GATES.md"}
    return any(path in active for path in paths)


def engage_verdict(tool_input: Mapping[str, object]) -> bool | None:
    """Return True for a bare engage, None otherwise, refusing a hidden one.

    A bare engage is always permitted. It is how a session obtains the method,
    so gating it on the method is circular, and it locked this guard out of its
    own repository.
    """
    command = tool_input.get("command", tool_input.get("cmd"))
    if not isinstance(command, str):
        return None
    if rules.hidden_engage(command):
        raise ValueError(f"engage must print into the transcript, and {command!r} sends "
                         "it elsewhere. Run it bare, with no pipe and no redirect, so "
                         "the method's exact text enters this session. A recorded digest "
                         "does not prove it was read.")
    return True if rules.bare_engage(command) else None


def pre_tool_use(payload: Mapping[str, object]) -> JsonObject:
    """Gate one tool call against the active route and its contract."""
    tool_name = str(payload.get("tool_name") or payload.get("toolName") or "")
    try:
        tool_input = rules.cast_input(payload.get("tool_input", payload.get("toolInput", {})))
        state = policy.load_state(payload)
        if spawn_input(tool_name):
            check_spawn(tool_input, state, payload)
            return {}
        if engage_verdict(tool_input) is True:
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
        state["stop_blocks"] = {}
        policy.save_state(payload, state)
        if route is not None:
            state.update({"route": route, "epoch": int(state.get("epoch", 0)) + 1})
            state.pop("ready", None)
            state.pop("rearm_reason", None)
            policy.save_state(payload, state)
        return context("UserPromptSubmit",
                       rules.turn_reminder(route, state.get("route"), ENGAGE_HINT))
    except Exception as error:  # noqa: BLE001
        return allow_with_warning(f"{type(error).__name__}: {error}")


def session_start(payload: Mapping[str, object]) -> JsonObject:
    """Re-arm the guard after a compaction or a clear."""
    return policy.session_start(payload)


def subagent_start(payload: Mapping[str, object]) -> JsonObject:
    """Give a starting subagent the complete active method."""
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
    state = policy.load_state(payload)
    scope = bound_unlazy_scope(payload, state)
    if scope is None:
        return {}
    return rules.run_unlazy_stop(payload, policy.repo_root(payload), scope)


def bound_unlazy_scope(payload: Mapping[str, object], state: JsonObject) -> str | None:
    scope = state.get("scope")
    if not isinstance(scope, str) or policy.SAFE_NAME.fullmatch(scope) is None:
        return None
    marker = policy.repo_root(payload) / ".unlazy" / scope / "session"
    try:
        owner = marker.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None
    return scope if owner == policy.payload_session_id(payload) else None


def unslop_violation(message: str) -> str | None:
    """Return the first unslop violation in a user-visible message."""
    return rules.unslop_violation(message, policy.repo_root({}))


def method_evidence_violation(payload: Mapping[str, object]) -> str | None:
    """Return the missing completion evidence, or None when the turn may end."""
    return evidence_violation(payload)


def subagent_stop(payload: Mapping[str, object]) -> JsonObject:
    """Hold a subagent to the same prose law as the parent."""
    try:
        if exhausted(payload):
            return {"systemMessage": "Subagent Stop wall released after repeated blocks."}
        violation = unslop_violation(last_message(payload))
        return record_block(payload, violation) if violation else {}
    except Exception as error:  # noqa: BLE001
        return allow_with_warning(f"{type(error).__name__}: {error}")


def evidence_violation(payload: Mapping[str, object]) -> str | None:
    """Return the missing completion evidence, or None when the turn may end."""
    state = policy.load_state(payload)
    if not rules.route_selected(state) or not state.get("production_write"):
        return None
    try:
        contract = policy.contract_on_disk(payload, state)
    except (OSError, ValueError) as error:
        return f"A production write happened, and its method contract is unreadable. {error}"
    return rules.review_receipt_violation(payload, contract)


MAX_TURN_BLOCKS = 3


def stop_actor(payload: Mapping[str, object]) -> str:
    event = str(payload.get("hook_event_name") or payload.get("hookEventName") or "")
    if event != "SubagentStop":
        return "root"
    agent = payload.get("agent_id") or payload.get("agentId") or "anonymous"
    return f"subagent:{agent}"


def actor_blocks(state: JsonObject, actor: str) -> int:
    counts = state.get("stop_blocks")
    if not isinstance(counts, dict):
        return 0
    count = counts.get(actor)
    return count if type(count) is int and count >= 0 else 0


def clean_code_violation(payload: Mapping[str, object]) -> str | None:
    """Return the Akita violations in what this session wrote."""
    state = policy.load_state(payload)
    return rules.clean_code_violation(policy.repo_root(payload),
                                      cast(list[str], state.get("written_paths", [])))


def exhausted(payload: Mapping[str, object]) -> bool:
    """Report whether this turn has been blocked too many times to keep trying."""
    state = policy.load_state(payload)
    blocks = actor_blocks(state, stop_actor(payload))
    return payload.get("stop_hook_active") is True and blocks >= MAX_TURN_BLOCKS


def record_block(payload: Mapping[str, object], reason: str) -> JsonObject:
    """Count this block against the turn, then refuse the turn."""
    state = policy.load_state(payload)
    actor = stop_actor(payload)
    counts = state.get("stop_blocks")
    if not isinstance(counts, dict):
        counts = {}
    counts[actor] = actor_blocks(state, actor) + 1
    state["stop_blocks"] = counts
    policy.save_state(payload, state)
    return block(reason)


def first_violation(payload: Mapping[str, object]) -> str | None:
    """Return the first completion check that refuses, in order."""
    for check in (method_evidence_violation, clean_code_violation):
        reason = check(payload)
        if reason:
            return reason
    return None


def stop(payload: Mapping[str, object]) -> JsonObject:
    """Refuse to end a turn that leaves the method's evidence missing.

    Unlazy owns completion, then the method's own evidence, then the code
    standard, then the prose law on the reply. Claude runs the same order.
    """
    try:
        if exhausted(payload):
            return {"systemMessage": f"Stop walls released after {MAX_TURN_BLOCKS} blocks in "
                                     "one turn. The last reasons stand and were not fixed."}
        unlazy = run_unlazy_stop(payload)
        if unlazy.get("decision") == "block":
            return record_block(payload, str(unlazy.get("reason", "unlazy gates are unmet")))
        reason = first_violation(payload)
        if reason:
            return record_block(payload, reason)
        violation = unslop_violation(last_message(payload))
        return record_block(payload, violation) if violation else unlazy
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


def direct_payload() -> JsonObject:
    root = policy.repo_root({})
    return {"cwd": str(root), "session_id": policy.current_session(root)}


def packet_chunk(text: str, start: int) -> tuple[str, int]:
    raw = text.encode()
    end = min(start + policy.ENGAGE_CHUNK_BYTES, len(raw))
    while end > start:
        try:
            return raw[start:end].decode(), end
        except UnicodeDecodeError:
            end -= 1
    raise ValueError(f"method packet cannot split UTF-8 at byte {start}")


def packet_chunks(text: str) -> tuple[str, ...]:
    chunks: list[str] = []
    offset = 0
    while offset < len(text.encode()):
        chunk, offset = packet_chunk(text, offset)
        chunks.append(chunk)
    return tuple(chunks)


def chunk_response(packet: policy.ExactMethodPacket, chunks: tuple[str, ...],
                   number: int, scope: str) -> str:
    output = f"<<<METHOD_PACKET_CHUNK {number} sha256={packet.sha256}>>>\n{chunks[number - 1]}\n"
    output += "<<<METHOD_PACKET_CHUNK_END>>>\n"
    if number < len(chunks):
        output += f"python3 .codex/hooks/method_guard.py engage {scope} {number + 1}\n"
    return output


def engage_arguments(arguments: Sequence[str]) -> tuple[str, int]:
    if len(arguments) not in (1, 2):
        raise ValueError(f"expected engage <scope> [chunk], got {tuple(arguments)!r}")
    if len(arguments) == 1:
        return arguments[0], 1
    if re.fullmatch(r"[0-9]+", arguments[1]) is None or int(arguments[1]) < 1:
        raise ValueError(f"chunk must be a positive decimal, got {arguments[1]!r}")
    return arguments[0], int(arguments[1])


def prepare_engage(
    arguments: Sequence[str],
) -> tuple[JsonObject, str, int, policy.ExactMethodPacket, JsonObject, tuple[str, ...]]:
    payload = direct_payload()
    scope, number = engage_arguments(arguments)
    payload["scope"] = scope
    packet, state = policy.prepare_engagement(payload)
    chunks = packet_chunks(packet.text)
    if number > len(chunks):
        raise ValueError(f"chunk {number} is out of range; packet has {len(chunks)} chunks")
    rules.require_contiguous_chunk(state, packet.sha256, number)
    return payload, scope, number, packet, state, chunks


def run_engage(arguments: Sequence[str], stdout: TextIO) -> int:
    try:
        payload, scope, number, packet, state, chunks = prepare_engage(arguments)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        stdout.write(f"Method guard engage rejected: {error}\n")
        return 0
    rules.record_engage_chunk(payload, state, packet.sha256, number)
    stdout.write(chunk_response(packet, chunks, number, scope))
    stdout.flush()
    if number == len(chunks):
        policy.mark_ready(payload, state)
    return 0


def main(argv: Sequence[str] | None = None, stdin: TextIO = sys.stdin,
         stdout: TextIO = sys.stdout, stderr: TextIO = sys.stderr) -> int:
    """Run one hook event, or the engage command."""
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "engage":
        return run_engage(arguments[1:], stdout)
    payload = json.load(stdin)
    if not isinstance(payload, dict):
        raise ValueError(f"hook payload must be an object, got {type(payload).__name__}")
    mapping = cast(Mapping[str, object], payload)
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
