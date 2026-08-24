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
from pathlib import Path
import re
import sys
from typing import Mapping, Sequence, TextIO, cast

sys.path.insert(0, str(Path(__file__).resolve().parent))

import method_guard_support as policy  # noqa: E402
import method_guard_rules as rules  # noqa: E402
from transcript_archive import archive_transcript  # noqa: E402

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
    """Return the exact paths this call writes, or None when it names none.

    Only the tools that carry a file path get an ownership check. A shell
    command is handled by `gate_write`, which requires the method without
    pretending to know which files the command touches.
    """
    return edit_paths(tool_input) if name in WRITE_TOOLS else None


def check_spawn(tool_input: Mapping[str, object], state: JsonObject,
                payload: Mapping[str, object]) -> None:
    """Apply the brief, ownership and model rules to one subagent launch."""
    root = policy.repo_root(payload)
    contract = policy.current_contract(payload, state)
    rules.validate_brief(tool_input.get("prompt"), root)
    require_spawn_value(tool_input, "subagent_type", "method-worker")
    model_policy = contract.get("model_policy")
    scoped = model_policy.get("claude") if isinstance(model_policy, dict) else None
    expected_model = scoped.get("routine_implementation_model", "opus") \
        if isinstance(scoped, dict) else "opus"
    require_spawn_value(tool_input, "model", expected_model)


def require_spawn_value(tool_input: Mapping[str, object], key: str, expected: object) -> None:
    """Reject a Claude child launch that bypasses its pinned worker."""
    actual = tool_input.get(key)
    if actual != expected:
        raise ValueError(f"Agent launch requires {key}={expected!r}, got {actual!r}.")


def check_write(paths: Sequence[str], state: JsonObject,
                payload: Mapping[str, object]) -> JsonObject | None:
    """Apply the route and ownership rules to one repository write."""
    if rules.bootstrap_only(paths) or rules.always_writable(paths):
        return rearm_on_contract_edit(paths, state, payload)
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
    return None


def rearm_on_contract_edit(paths: Sequence[str], state: JsonObject,
                           payload: Mapping[str, object]) -> None:
    """Clear readiness when the contract or its gates change under us."""
    if rules.bootstrap_only(paths) and active_method_artifact(paths, state):
        policy.rearm(payload, state, "contract or gates edit")
    return None


def active_method_artifact(paths: Sequence[str], state: JsonObject) -> bool:
    """Report whether paths include this session's METHOD.json or GATES.md."""
    scope = state.get("scope")
    if not isinstance(scope, str):
        return False
    active = {f".unlazy/{scope}/METHOD.json", f".unlazy/{scope}/GATES.md"}
    return any(path in active for path in paths)


def refuse_hidden_engage(command: str) -> None:
    """Refuse an engage call whose output would never reach the transcript."""
    if rules.hidden_engage(command):
        raise ValueError(f"engage must print into the transcript, and {command!r} "
                         "sends it elsewhere. Run it bare, with no pipe and no "
                         "redirect, so the method's exact text enters this session. "
                         "A recorded digest does not prove the text was read.")


def gate_command(tool_input: Mapping[str, object], state: JsonObject,
                 payload: Mapping[str, object]) -> JsonObject:
    """Let a read through, and require the method for anything else."""
    command = tool_input.get("command")
    if not isinstance(command, str):
        return {}
    refuse_hidden_engage(command)
    if rules.bare_engage(command) or rules.scan_command(command).kind == "none":
        return {}
    if not rules.route_selected(state):
        raise ValueError(f"A shell command that can change something requires an explicit "
                         f"$plan-flow or $implement-flow route, and route="
                         f"{state.get('route')!r}. Reads pass without one.")
    policy.current_contract(payload, state)
    if state["route"] == "plan-flow":
        raise ValueError("plan-flow permits reads and planning artifacts. "
                         f"Send $implement-flow to run {command.split()[0]!r}.")
    return {}


def gate_write(targets: list[str] | None, state: JsonObject,
               payload: Mapping[str, object]) -> JsonObject | None:
    """Check ownership on named paths, or require the method for a shell call."""
    if targets is None:
        return None
    inside = rules.repository_paths(policy.repo_root(payload), targets)
    return check_write(inside, state, payload) if inside else None


def pre_tool_use(payload: Mapping[str, object]) -> JsonObject:
    """Gate one tool call against the active route and its contract."""
    name = tool_name(payload)
    try:
        tool_input = rules.cast_input(payload.get("tool_input", payload.get("toolInput", {})))
        state = policy.load_state(payload)
        if name in SPAWN_TOOLS:
            check_spawn(tool_input, state, payload)
            return {}
        if name == "Bash":
            return gate_command(tool_input, state, payload)
        return gate_write(write_targets(name, tool_input), state, payload) or {}
    except ValueError as error:
        return deny(str(error))
    except Exception as error:  # noqa: BLE001
        return allow_with_warning(f"{type(error).__name__}: {error}")


def post_tool_use(payload: Mapping[str, object]) -> JsonObject:
    """Report Akita violations in the file just written, without blocking."""
    try:
        tool_input = rules.cast_input(payload.get("tool_input", {}))
        targets = write_targets(tool_name(payload), tool_input) or []
        root = policy.repo_root(payload)
        findings = rules.clean_code_findings([Path(path) for path in targets], root)
        if not findings:
            return {}
        listed = "\n".join(findings[:6])
        return {"systemMessage": f"clean-code-for-agents on the file you just wrote:\n{listed}"}
    except Exception as error:  # noqa: BLE001
        return allow_with_warning(f"{type(error).__name__}: {error}")


def user_prompt_submit(payload: Mapping[str, object]) -> JsonObject:
    """Record the session, select a route when the prompt names one, and remind."""
    try:
        policy.remember_session(payload)
        route = rules.route_from_prompt(prompt_text(payload))
        state = policy.load_state(payload)
        state["stop_blocks"] = {}
        policy.save_state(payload, state)
        if route is not None:
            select_route(payload, state, route)
        return context("UserPromptSubmit",
                       rules.turn_reminder(route, state.get("route"), ENGAGE_HINT))
    except Exception as error:  # noqa: BLE001
        return allow_with_warning(f"{type(error).__name__}: {error}")


def select_route(payload: Mapping[str, object], state: JsonObject, route: str) -> None:
    """Start a new route epoch, which clears any previous readiness."""
    state.update({"route": route, "epoch": int(state.get("epoch", 0)) + 1})
    state.pop("ready", None)
    state.pop("rearm_reason", None)
    policy.save_state(payload, state)


def session_start(payload: Mapping[str, object]) -> JsonObject:
    """Restore the exact method after compaction or clear."""
    try:
        return policy.session_start(payload)
    except Exception as error:  # noqa: BLE001
        return allow_with_warning(f"{type(error).__name__}: {error}")


def subagent_start(payload: Mapping[str, object]) -> JsonObject:
    """Give a starting subagent the complete active method."""
    try:
        return policy.subagent_start(payload)
    except Exception as error:  # noqa: BLE001
        return allow_with_warning(f"{type(error).__name__}: {error}")


MAX_TURN_BLOCKS = 3


def run_unlazy_stop(payload: Mapping[str, object]) -> JsonObject:
    """Run the pinned unlazy Stop wall for this repository."""
    state = policy.load_state(payload)
    scope = bound_unlazy_scope(payload, state)
    if scope is None:
        return {}
    return rules.run_unlazy_stop(payload, policy.repo_root(payload), scope)


def bound_unlazy_scope(payload: Mapping[str, object], state: JsonObject) -> str | None:
    """Return only the active scope whose session marker matches this session."""
    scope = state.get("scope")
    if not isinstance(scope, str) or policy.SAFE_NAME.fullmatch(scope) is None:
        return None
    marker = policy.repo_root(payload) / ".unlazy" / scope / "session"
    try:
        owner = marker.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None
    return scope if owner == policy.payload_session_id(payload) else None


def method_evidence_violation(payload: Mapping[str, object]) -> str | None:
    """Return the missing completion evidence, or None when the turn may end."""
    return evidence_violation(payload)


def clean_code_violation(payload: Mapping[str, object]) -> str | None:
    """Return the Akita violations in what this session wrote."""
    state = policy.load_state(payload)
    return rules.clean_code_violation(policy.repo_root(payload),
                                      cast(list[str], state.get("written_paths", [])))


def unslop_violation(message: str, payload: Mapping[str, object]) -> str | None:
    """Return the first unslop violation in a user-visible message."""
    return rules.unslop_violation(message, policy.repo_root(payload))


def exhausted(payload: Mapping[str, object]) -> bool:
    """Report whether this actor has been blocked too many times."""
    state = policy.load_state(payload)
    blocks = actor_blocks(state, stop_actor(payload))
    return payload.get("stop_hook_active") is True and blocks >= MAX_TURN_BLOCKS


def record_block(payload: Mapping[str, object], reason: str) -> JsonObject:
    """Count this block against one actor, then refuse the turn."""
    state = policy.load_state(payload)
    actor = stop_actor(payload)
    counts = state.get("stop_blocks")
    if not isinstance(counts, dict):
        counts = {}
    counts[actor] = actor_blocks(state, actor) + 1
    state["stop_blocks"] = counts
    policy.save_state(payload, state)
    return block(reason)


def stop_actor(payload: Mapping[str, object]) -> str:
    """Return a stable counter key for the root or one child."""
    event = str(payload.get("hook_event_name") or payload.get("hookEventName") or "")
    if event != "SubagentStop":
        return "root"
    agent = payload.get("agent_id") or payload.get("agentId") or "anonymous"
    return f"subagent:{agent}"


def actor_blocks(state: JsonObject, actor: str) -> int:
    """Return one actor's valid non-negative block count."""
    counts = state.get("stop_blocks")
    if not isinstance(counts, dict):
        return 0
    count = counts.get(actor)
    return count if type(count) is int and count >= 0 else 0


def first_violation(payload: Mapping[str, object]) -> str | None:
    """Return the first completion check that refuses, in order."""
    for check in (method_evidence_violation, clean_code_violation):
        reason = check(payload)
        if reason:
            return reason
    return None


def stop(payload: Mapping[str, object]) -> JsonObject:
    """Refuse to end a turn that leaves the method's evidence missing.

    The order matches Codex exactly. Unlazy owns completion, then the method's
    own evidence, then the code standard, then the prose law on the reply.
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
        violation = unslop_violation(last_message(payload), payload)
        return record_block(payload, violation) if violation else unlazy
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


def last_message(payload: Mapping[str, object]) -> str:
    """Return the final assistant message this event reports."""
    return str(payload.get("last_assistant_message")
               or payload.get("lastAssistantMessage") or "")


def subagent_stop(payload: Mapping[str, object]) -> JsonObject:
    """Check child prose, then archive the accepted final transcript."""
    try:
        if exhausted(payload):
            archive_transcript(payload.get("agent_transcript_path"))
            return {"systemMessage": "Subagent Stop wall released after repeated blocks."}
        violation = unslop_violation(last_message(payload), payload)
        if violation:
            return record_block(payload, violation)
        archive_transcript(payload.get("agent_transcript_path"))
        return {}
    except Exception as error:  # noqa: BLE001
        return allow_with_warning(f"{type(error).__name__}: {error}")


def direct_payload() -> JsonObject:
    """Build the payload for a direct engage command."""
    root = policy.repo_root({})
    return {"cwd": str(root), "session_id": policy.current_session(root)}


def packet_chunk(text: str, start: int) -> tuple[str, int]:
    """Cut one bounded chunk without splitting a UTF-8 character."""
    raw = text.encode()
    end = min(start + policy.ENGAGE_CHUNK_BYTES, len(raw))
    while end > start:
        try:
            return raw[start:end].decode(), end
        except UnicodeDecodeError:
            end -= 1
    raise ValueError(f"method packet cannot split UTF-8 at byte {start}")


def packet_chunks(text: str) -> tuple[str, ...]:
    """Split one packet into the bounded direct-engage responses."""
    chunks: list[str] = []
    offset = 0
    while offset < len(text.encode()):
        chunk, offset = packet_chunk(text, offset)
        chunks.append(chunk)
    return tuple(chunks)


def engage_arguments(arguments: Sequence[str]) -> tuple[str, int]:
    """Parse ``engage <scope> [chunk]`` without accepting extra input."""
    if len(arguments) not in (1, 2):
        raise ValueError(f"expected engage <scope> [chunk], got {tuple(arguments)!r}")
    if len(arguments) == 1:
        return arguments[0], 1
    if re.fullmatch(r"[0-9]+", arguments[1]) is None or int(arguments[1]) < 1:
        raise ValueError(f"chunk must be a positive decimal, got {arguments[1]!r}")
    return arguments[0], int(arguments[1])


def chunk_response(packet: policy.ExactMethodPacket, chunks: tuple[str, ...],
                   number: int, scope: str) -> str:
    """Render one packet chunk and the next exact command, when needed."""
    output = f"<<<METHOD_PACKET_CHUNK {number} sha256={packet.sha256}>>>\n"
    output += f"{chunks[number - 1]}\n<<<METHOD_PACKET_CHUNK_END>>>\n"
    if number < len(chunks):
        output += f"python3 .claude/hooks/method_guard.py engage {scope} {number + 1}\n"
    return output


EVENTS = {
    "session-start": session_start,
    "user-prompt-submit": user_prompt_submit,
    "pre-tool-use": pre_tool_use,
    "post-tool-use": post_tool_use,
    "subagent-start": subagent_start,
    "subagent-stop": subagent_stop,
    "stop": stop,
}


def run_engage(arguments: Sequence[str], stdout: TextIO, _stderr: TextIO) -> int:
    """Emit one exact packet chunk and mark ready only after the final chunk."""
    try:
        payload = direct_payload()
        scope, number = engage_arguments(arguments[1:])
        payload["scope"] = scope
        packet, state = policy.prepare_engagement(payload)
        chunks = packet_chunks(packet.text)
        if number > len(chunks):
            raise ValueError(f"chunk {number} is out of range; packet has {len(chunks)} chunks")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        stdout.write(f"Method guard engage rejected: {error}\n")
        return 0
    pending_ready = state["pending_ready"]
    policy.rearm(payload, state, "engage in progress")
    state["pending_ready"] = pending_ready
    stdout.write(chunk_response(packet, chunks, number, scope))
    stdout.flush()
    if number == len(chunks):
        policy.mark_ready(payload, state)
    return 0


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
