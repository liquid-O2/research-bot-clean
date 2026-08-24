
from __future__ import annotations

import asyncio
import json
import shutil
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from agent_harness_verify_common import (
    HARNESS_DIR,
    ROOT,
    load_install_receipt,
    refuse,
    require,
    sha256_file,
)
from agent_harness_verify_static import expected_live_hook_inventory, expected_skill_names

WORKSPACE_HOOK_PATH = str(ROOT / ".codex/hooks.json")
CODEX_CONFIG = Path("/home/algo/.codex/config.toml")


@dataclass(frozen=True)
class CodexSkillsIO:
    """Inject discovery I/O. Example: CodexSkillsIO(loader, locator, probe, names, root)."""
    receipt_loader: Callable[[], dict[str, object]]
    locator: Callable[[str], str | None]
    probe: Callable[[str], tuple[dict[str, object], bytes]]
    expected_names: list[str] | None
    receipt_root: Path


def default_codex_skills_io() -> CodexSkillsIO:
    return CodexSkillsIO(load_install_receipt, shutil.which, run_codex_skills_probe,
                         None, HARNESS_DIR)


async def read_codex_response(
    process: asyncio.subprocess.Process, request_id: int, transcript: bytearray,
    method: str,
) -> dict[str, object]:
    assert process.stdout is not None
    assert process.stderr is not None
    while True:
        raw = await asyncio.wait_for(process.stdout.readline(), timeout=30)
        if not raw:
            stderr = (await process.stderr.read()).decode(errors="replace")
            refuse("codex-app.protocol", {"method": method, "stderr": stderr},
                   f"response id {request_id}")
        transcript.extend(raw)
        try:
            response = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(response, dict) and response.get("id") == request_id:
            return cast(dict[str, object], response)


async def send_codex_request(
    process: asyncio.subprocess.Process, request_id: int,
    method: str, params: dict[str, object], transcript: bytearray,
) -> dict[str, object]:
    assert process.stdin is not None
    message = {"id": request_id, "method": method, "params": params}
    process.stdin.write(json.dumps(message).encode() + b"\n")
    await process.stdin.drain()
    return await read_codex_response(process, request_id, transcript, method)


async def stop_codex_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()


async def codex_app_response(
    codex: str, method: str, params: dict[str, object],
) -> tuple[dict[str, object], bytes]:
    process = await asyncio.create_subprocess_exec(
        codex, "app-server", "--stdio", cwd=ROOT,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    transcript = bytearray()
    try:
        await send_codex_request(process, 0, "initialize", {
            "clientInfo": {"name": "harness-verifier", "version": "1"},
        }, transcript)
        response = await send_codex_request(process, 1, method, params, transcript)
    finally:
        await stop_codex_process(process)
    return response, bytes(transcript)


async def codex_skills_response(codex: str) -> tuple[dict[str, object], bytes]:
    return await codex_app_response(codex, "skills/list", {
        "cwds": [str(ROOT)], "forceReload": True,
    })


async def codex_hooks_response(codex: str) -> tuple[dict[str, object], bytes]:
    return await codex_app_response(codex, "hooks/list", {"cwd": str(ROOT)})


def workspace_result(
    response: dict[str, object], name: str, expected_result: str,
) -> dict[str, object]:
    result = response.get("result")
    valid = isinstance(result, dict) and isinstance(result.get("data"), list)
    require(valid, f"{name}.result", result, expected_result)
    rows = cast(list[object], cast(dict[str, object], result)["data"])
    workspaces = [row for row in rows
                  if isinstance(row, dict) and row.get("cwd") == str(ROOT)]
    require(len(workspaces) == 1, f"{name}.workspace", workspaces,
            "one /workspace result")
    return cast(dict[str, object], workspaces[0])


def codex_workspace_result(response: dict[str, object]) -> dict[str, object]:
    return workspace_result(response, "codex-skills", "skills/list result data array")


def hook_workspace_result(response: dict[str, object]) -> dict[str, object]:
    return workspace_result(response, "hooks.trust", "hooks/list result data array")


def load_hook_trust_state(path: Path = CODEX_CONFIG) -> dict[str, str]:
    """Parse user-owned hook trust. Example: load_hook_trust_state(config_path)."""
    if not path.is_file():
        return {}
    try:
        config = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        refuse("hooks.trust-config", f"{path}: {error}", "valid Codex TOML")
    hooks = config.get("hooks", {})
    state = hooks.get("state", {}) if isinstance(hooks, dict) else None
    require(isinstance(state, dict), "hooks.trust-config", state,
            "hooks.state table")
    rows = cast(dict[str, object], state)
    valid = all(isinstance(value, dict)
                and isinstance(value.get("trusted_hash"), str) for value in rows.values())
    require(valid, "hooks.trust-config", rows, "trusted_hash string per hook key")
    return {key: cast(str, cast(dict[str, object], value)["trusted_hash"])
            for key, value in rows.items()}


def normalize_hook_row(row: dict[str, object]) -> dict[str, str]:
    fields = ("key", "eventName", "currentHash", "trustStatus")
    values = {field: row.get(field) for field in fields}
    require(all(isinstance(value, str) and value for value in values.values()),
            "hooks.trust-row", values, "non-empty normalized hook fields")
    require(row.get("source") == "project", "hooks.trust-source",
            row.get("source"), "project")
    require(row.get("sourcePath") == WORKSPACE_HOOK_PATH, "hooks.trust-source-path",
            row.get("sourcePath"), WORKSPACE_HOOK_PATH)
    return cast(dict[str, str], values)


def workspace_hook_rows(response: dict[str, object]) -> list[dict[str, str]]:
    workspace = hook_workspace_result(response)
    require(workspace.get("errors") == [], "hooks.trust-errors",
            workspace.get("errors"), "empty error array")
    hooks = workspace.get("hooks")
    require(isinstance(hooks, list), "hooks.trust-hooks", hooks, "hook array")
    current = [normalize_hook_row(cast(dict[str, object], row))
               for row in cast(list[object], hooks)
               if isinstance(row, dict) and row.get("sourcePath") == WORKSPACE_HOOK_PATH]
    return sorted(current, key=lambda row: row["eventName"])


def workspace_trust_state(trust_state: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in trust_state.items()
            if key.startswith(f"{WORKSPACE_HOOK_PATH}:")}


def validate_hook_inventory(rows: list[dict[str, str]]) -> set[str]:
    keys = {row["key"] for row in rows}
    events = {row["eventName"] for row in rows}
    required_events, required_handlers = expected_live_hook_inventory()
    valid = len(keys) == len(rows) == required_handlers and events == required_events
    require(valid,
            "hooks.trust-current", {"keys": sorted(keys), "events": sorted(events)},
            f"{required_handlers} current handlers for {len(required_events)} events")
    return keys


def validate_hook_trust(
    response: dict[str, object], trust_state: dict[str, str],
) -> list[dict[str, str]]:
    """Check live hooks against trust state. Example: validate_hook_trust(response, state)."""
    rows = workspace_hook_rows(response)
    keys = validate_hook_inventory(rows)
    workspace_state = workspace_trust_state(trust_state)
    orphans = sorted(set(workspace_state) - keys)
    require(not orphans, "hooks.trust-orphan", orphans,
            "current /workspace hook identity")
    for row in rows:
        require(row["trustStatus"] == "trusted", "hooks.trust-status",
                row["trustStatus"], "trusted")
        stored = workspace_state.get(row["key"])
        require(stored == row["currentHash"], "hooks.trust-stale", stored,
                row["currentHash"])
    return rows


def repo_skill_rows(workspace: dict[str, object]) -> list[dict[str, object]]:
    require(workspace.get("errors") == [], "codex-skills.errors",
            workspace.get("errors"), "empty error array")
    listed = workspace.get("skills")
    require(isinstance(listed, list), "codex-skills.skills", listed, "skill array")
    prefix = str(ROOT / ".agents/skills") + "/"
    return [cast(dict[str, object], skill) for skill in cast(list[object], listed)
            if isinstance(skill, dict) and isinstance(skill.get("path"), str)
            and cast(str, skill["path"]).startswith(prefix)]


def validate_codex_skill(skill: dict[str, object]) -> None:
    name = skill["name"]
    require(isinstance(name, str), "codex-skills.name", name, "string name")
    expected_path = str(ROOT / f".agents/skills/{name}/SKILL.md")
    require(skill.get("path") == expected_path, f"codex-skills.{name}.path",
            skill.get("path"), expected_path)
    require(skill.get("enabled") is True, f"codex-skills.{name}.enabled",
            skill.get("enabled"), "true")


def run_codex_skills_probe(codex: str) -> tuple[dict[str, object], bytes]:
    try:
        return asyncio.run(codex_skills_response(codex))
    except (OSError, asyncio.TimeoutError) as error:
        refuse("codex-skills.client", str(error),
               "bounded successful Codex skills/list probe")


def run_codex_hooks_probe(codex: str) -> tuple[dict[str, object], bytes]:
    try:
        return asyncio.run(codex_hooks_response(codex))
    except (OSError, asyncio.TimeoutError) as error:
        refuse("hooks.trust-client", str(error),
               "bounded successful Codex hooks/list probe")


def validated_codex_skills(
    response: dict[str, object], expected_names: list[str] | None = None,
) -> list[dict[str, object]]:
    repo_skills = repo_skill_rows(codex_workspace_result(response))
    actual_names = sorted(cast(str, skill.get("name")) for skill in repo_skills)
    expected = expected_skill_names() if expected_names is None else expected_names
    require(actual_names == expected, "codex-skills.names", actual_names, str(expected))
    for skill in repo_skills:
        validate_codex_skill(skill)
    return sorted(repo_skills, key=lambda skill: cast(str, skill["name"]))


def live_codex_skills(
    dependencies: CodexSkillsIO | None = None,
) -> tuple[Path, list[dict[str, object]]]:
    io = default_codex_skills_io() if dependencies is None else dependencies
    io.receipt_loader()
    codex = io.locator("codex")
    require(codex is not None, "codex-skills.client", codex, "installed codex executable")
    response, _ = io.probe(cast(str, codex))
    return Path(cast(str, codex)).resolve(), validated_codex_skills(
        response, io.expected_names
    )


def capture_codex_skills(
    dependencies: CodexSkillsIO | None = None,
) -> str:
    """Write normalized live skills. Example: capture_codex_skills()."""
    io = default_codex_skills_io() if dependencies is None else dependencies
    _, rows = live_codex_skills(io)
    fields = ("enabled", "name", "path")
    normalized = [{field: row[field] for field in fields} for row in rows]
    content = "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                      for row in normalized)
    receipt = io.receipt_root / "receipts/codex-skills-list.jsonl"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(content, encoding="utf-8")
    return f"active={len(rows)} receipt={receipt}"


def verify_codex_skills(dependencies: CodexSkillsIO | None = None) -> str:
    """Check live discovery without writes. Example: verify_codex_skills()."""
    resolved_codex, repo_skills = live_codex_skills(dependencies)
    return (f"client={resolved_codex} active={len(repo_skills)} "
            "flows=plan-flow,implement-flow")


def verify_hook_trust() -> str:
    """Check live hook readiness. Example: verify_hook_trust()."""
    load_install_receipt()
    codex = shutil.which("codex")
    require(codex is not None, "hooks.trust-client", codex,
            "installed codex executable")
    response, _ = run_codex_hooks_probe(cast(str, codex))
    rows = validate_hook_trust(response, load_hook_trust_state())
    return f"handlers={len(rows)} current_hashes={len(rows)} trust=trusted"


def parse_lifecycle_events(path: Path) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            refuse("lifecycle.event-log", f"line {line_number}: {error}",
                   "JSON object per line")
        valid = isinstance(event, dict) and isinstance(event.get("payload"), dict)
        require(valid, "lifecycle.event", event, "object with payload object")
        events.append(cast(dict[str, object], event))
    require(bool(events), "lifecycle.event-log", 0, "non-empty JSONL")
    return events


def lifecycle_receipt_fields(path: Path) -> dict[str, str]:
    require(path.is_file(), "lifecycle.receipt", str(path), "existing retained receipt")
    lines = path.read_text(encoding="utf-8").splitlines()
    require(len(lines) == 5 and lines[0] == "LIFECYCLE RECEIPT 1",
            "lifecycle.receipt-envelope", lines, "exact five-line lifecycle receipt")
    fields = dict(line.split("=", 1) for line in lines[1:] if "=" in line)
    expected = {"codex_version", "event_log", "event_log_sha256", "verification"}
    require(set(fields) == expected, "lifecycle.receipt-fields", fields,
            "frozen lifecycle fields")
    require(fields["codex_version"] == "codex-cli 0.149.0", "lifecycle.codex-version",
            fields["codex_version"], "codex-cli 0.149.0")
    require(fields["verification"] == "PROBE_VERIFY_OK", "lifecycle.verification",
            fields["verification"], "PROBE_VERIFY_OK")
    return fields


def lifecycle_payloads(events: list[dict[str, object]]) -> list[dict[str, object]]:
    project = [event for event in events if event.get("configured_layer") == "project"]
    return [cast(dict[str, object], event["payload"]) for event in project]


def lifecycle_identities(
    payloads: list[dict[str, object]],
) -> tuple[object, object]:
    starts = [payload for payload in payloads
              if payload.get("hook_event_name") == "SubagentStart"]
    require(bool(starts), "lifecycle.SubagentStart", 0, "child SubagentStart event")
    agent_ids = {payload.get("agent_id") for payload in starts}
    root_ids = {payload.get("session_id") for payload in starts}
    require(len(agent_ids) == 1 and len(root_ids) == 1, "lifecycle.child-identity",
            {"agent_ids": sorted(agent_ids), "root_ids": sorted(root_ids)},
            "one child and one root session")
    return next(iter(agent_ids)), next(iter(root_ids))


def verify_lifecycle_events(
    payloads: list[dict[str, object]], agent_id: object, root_id: object,
) -> None:
    require(any(payload.get("hook_event_name") == "SubagentStop"
                and payload.get("agent_id") == agent_id for payload in payloads),
            "lifecycle.SubagentStop", agent_id, "matching child SubagentStop")
    child_starts = [payload for payload in payloads
                    if payload.get("hook_event_name") == "SessionStart"
                    and payload.get("session_id") == agent_id]
    require(not child_starts, "lifecycle.child-SessionStart", child_starts, "no event")
    require(any(payload.get("hook_event_name") == "SessionStart"
                and payload.get("session_id") == root_id
                and payload.get("source") == "startup" for payload in payloads),
            "lifecycle.root-SessionStart", root_id, "root startup SessionStart")
    require(any(payload.get("hook_event_name") == "Stop"
                and payload.get("session_id") == root_id for payload in payloads),
            "lifecycle.root-Stop", root_id, "root Stop")


def verify_compact_order(payloads: list[dict[str, object]], root_id: object) -> None:
    names = [(payload.get("hook_event_name"), payload.get("source"),
              payload.get("session_id")) for payload in payloads]
    pre = next((index for index, item in enumerate(names)
                if item[0] == "PreCompact" and item[2] == root_id), None)
    compact = next((index for index, item in enumerate(names)
                    if item[0] == "SessionStart" and item[1] == "compact"
                    and item[2] == root_id and pre is not None and index > pre), None)
    require(pre is not None and compact is not None,
            "lifecycle.compact-order", names,
            "PreCompact before SessionStart source=compact")


def verify_lifecycle() -> str:
    """Check retained event order. Example: verify_lifecycle()."""
    receipt = load_install_receipt()
    path = Path(cast(str, receipt["lifecycle_probe_receipt"]))
    fields = lifecycle_receipt_fields(path)
    event_log = Path(fields["event_log"])
    expected_log = HARNESS_DIR / "receipts/lifecycle-events.jsonl"
    require(event_log == expected_log, "lifecycle.event-log-path",
            str(event_log), str(expected_log))
    require(event_log.is_file(), "lifecycle.event-log", str(event_log), "existing file")
    actual_event_sha = sha256_file(event_log)
    require(actual_event_sha == fields["event_log_sha256"],
            "lifecycle.event-log-sha256", actual_event_sha, fields["event_log_sha256"])
    events = parse_lifecycle_events(event_log)
    payloads = lifecycle_payloads(events)
    agent_id, root_id = lifecycle_identities(payloads)
    verify_lifecycle_events(payloads, agent_id, root_id)
    verify_compact_order(payloads, root_id)
    return (f"retained_receipt={path} events={len(events)} "
            "proof=codex-0.149-event-order-only live_optmem_unlazy=not-claimed")
