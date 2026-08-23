"""State, contract, and source-packet support for the method guard hook."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
from typing import Mapping, cast


NO_MEMO = "You are a subagent. Don't run memo."
ROUTES = {"plan-flow", "implement-flow"}
SAFE_NAME = re.compile(r"[a-z0-9][a-z0-9-]*\Z")
CLIENTS = {"codex": ("CODEX_METHOD", ".codex/method-guard"),
           "claude": ("CLAUDE_METHOD", ".claude/method-guard")}
_CLIENT = "codex"


def configure(client: str) -> None:
    """Select which client's environment names and state directory apply.

    The policy is identical for both clients. Only where its state lives and
    which environment variables override it differ, so one module serves both
    and neither can drift from the other.
    """
    global _CLIENT
    if client not in CLIENTS:
        raise ValueError(f"unknown client {client!r}, expected one of {sorted(CLIENTS)}")
    _CLIENT = client


def client_name() -> str:
    """Return the configured client."""
    return _CLIENT


def env_name(suffix: str) -> str:
    """Return the configured client's environment variable for one setting."""
    return f"{CLIENTS[_CLIENT][0]}_{suffix}"


def default_state_root() -> Path:
    """Return where this client keeps its per-session guard state."""
    return Path.home() / CLIENTS[_CLIENT][1]
PINNED_PSTACK = Path(
    "/workspace/vendor/agent-sources/pstack/"
    "46125561306434d8a1d7745d540d8932ab0cd2a2/pstack"
)
PINNED_IMPLEMENT = Path(
    "/workspace/vendor/agent-sources/pocock/"
    "5b15a47f2d7150f545fbcacbfe381787fc0230dc/skills/engineering/implement/SKILL.md"
)
JsonObject = dict[str, object]


def digest_text(value: str) -> str:
    return sha256(value.encode()).hexdigest()[:24]


def repo_root(payload: Mapping[str, object]) -> Path:
    configured = os.environ.get(env_name("REPO_ROOT"))
    candidate = configured or cast(str, payload.get("cwd") or os.getcwd())
    return Path(candidate).resolve()


def state_root() -> Path:
    configured = os.environ.get(env_name("STATE_ROOT"))
    root = Path(configured) if configured else default_state_root()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    return root


def state_path(payload: Mapping[str, object]) -> Path:
    session = str(payload.get("session_id") or payload.get("sessionId") or "anonymous")
    directory = state_root() / digest_text(str(repo_root(payload)))
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    return directory / f"{digest_text(session)}.json"


def remember_session(payload: Mapping[str, object]) -> None:
    """Record which session owns this repository right now.

    The engage command runs as a shell call, and the agent has no way to know
    its own session id. Recording it here lets engage be a one-line command the
    denial message can quote verbatim.
    """
    session = str(payload.get("session_id") or payload.get("sessionId") or "anonymous")
    directory = state_root() / digest_text(str(repo_root(payload)))
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    (directory / "current-session").write_text(session + "\n", encoding="utf-8")


def current_session(root: Path) -> str:
    """Return the session id recorded for this repository."""
    marker = state_root() / digest_text(str(root)) / "current-session"
    try:
        return marker.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise ValueError(
            f"no session recorded for {root}; send a prompt first so the guard sees the session"
        ) from error


def load_state(payload: Mapping[str, object]) -> JsonObject:
    path = state_path(payload)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"schema_version": 1, "epoch": 0}
    return value if isinstance(value, dict) else {"schema_version": 1, "epoch": 0}


def save_state(payload: Mapping[str, object], state: Mapping[str, object]) -> None:
    path = state_path(payload)
    descriptor, raw_path = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw_path)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(json.dumps(state, sort_keys=True) + "\n")
    temporary.chmod(0o600)
    os.replace(temporary, path)


def safe_relative(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty repository-relative path, got {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field} must stay inside the repository, got {value!r}")
    return path.as_posix()


def load_contract(root: Path, scope: object) -> tuple[Path, JsonObject]:
    if isinstance(scope, str) and SAFE_NAME.fullmatch(scope):
        candidates = [root / f".unlazy/{scope}/METHOD.json"]
    elif scope is None:
        candidates = sorted(root.glob(".unlazy/*/METHOD.json"))
    else:
        raise ValueError(f"scope must match {SAFE_NAME.pattern!r}, got {scope!r}")
    existing = [path for path in candidates if path.is_file()]
    if len(existing) != 1:
        scopes = sorted(path.parent.name for path in existing)
        raise ValueError(
            f"expected one METHOD.json, found {len(existing)} {scopes}. "
            "Name the scope: engage <scope>."
        )
    value = json.loads(existing[0].read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"METHOD.json must contain an object, got {type(value).__name__}")
    return existing[0], value


def string_list(value: object, field: str) -> list[str]:
    valid = isinstance(value, list) and value and all(isinstance(row, str) for row in value)
    if not valid:
        raise ValueError(f"{field} must be a non-empty string list, got {value!r}")
    rows = cast(list[str], value)
    if not all(SAFE_NAME.fullmatch(row) for row in rows):
        raise ValueError(f"{field} contains a non-canonical skill name, got {rows!r}")
    return rows


def path_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty path list, got {value!r}")
    return [safe_relative(row, field) for row in value]


def validate_contract(contract: JsonObject, route: object) -> None:
    selected = contract.get("route")
    if selected not in ROUTES or selected != route:
        raise ValueError(f"METHOD route must equal active route {route!r}, got {selected!r}")
    playbook = contract.get("playbook")
    if not isinstance(playbook, str) or not SAFE_NAME.fullmatch(playbook):
        raise ValueError(f"playbook must be a canonical name, got {playbook!r}")
    if selected == "plan-flow" and playbook != "multi-phase-plan":
        raise ValueError(f"plan-flow requires playbook 'multi-phase-plan', got {playbook!r}")
    expected = [selected, "poteto-mode", f"playbook:{playbook}"]
    if contract.get("outer_method") != expected:
        raise ValueError(f"outer_method must equal {expected!r}, got {contract.get('outer_method')!r}")
    string_list(contract.get("standing_laws"), "standing_laws")
    path_list(contract.get("owns"), "owns")
    validate_nested_methods(contract.get("nested_method"))


def validate_nested_methods(value: object) -> None:
    if not isinstance(value, dict) or not value:
        raise ValueError(f"nested_method must be a non-empty object, got {value!r}")
    for key, methods in value.items():
        if not isinstance(key, str) or not SAFE_NAME.fullmatch(key):
            raise ValueError(f"nested_method has a non-canonical branch, got {key!r}")
        string_list(methods, f"nested_method.{key}")


def source_names(contract: JsonObject) -> list[str]:
    names = cast(list[str], contract["outer_method"])[:]
    if contract["route"] == "plan-flow":
        names.append("reference:plan")
    names.extend(string_list(contract["standing_laws"], "standing_laws"))
    for methods in cast(dict[str, object], contract["nested_method"]).values():
        names.extend(string_list(methods, "nested_method branch"))
    principles = contract.get("principles")
    if not isinstance(principles, list) or not principles:
        raise ValueError(f"principles must be a non-empty object list, got {principles!r}")
    names.extend(principle_names(principles))
    return list(dict.fromkeys(names))


def principle_names(principles: list[object]) -> list[str]:
    names: list[str] = []
    for row in principles:
        if not isinstance(row, dict) or not all(row.get(key) for key in ("name", "decision", "evidence")):
            raise ValueError(f"principle must name decision and evidence, got {row!r}")
        name = row["name"]
        valid = isinstance(name, str) and name.startswith("principle-") and SAFE_NAME.fullmatch(name)
        if not valid:
            raise ValueError(f"principle name is not canonical, got {name!r}")
        names.append(cast(str, name))
    return names


def pinned_sources(pstack: Path, contract: JsonObject) -> dict[str, Path]:
    """Return the sources that must come from the pinned Pstack checkout."""
    poteto = pstack / "skills/poteto-mode"
    playbook = cast(str, contract["playbook"])
    return {
        "poteto-mode": poteto / "SKILL.md",
        f"playbook:{playbook}": poteto / f"playbooks/{playbook}.md",
        "reference:plan": poteto / "references/plan.md",
    }


def source_path(root: Path, pstack: Path, contract: JsonObject, name: str) -> Path:
    """Resolve one method source, refusing anything outside its canonical root."""
    pinned = pinned_sources(pstack, contract)
    path = pinned.get(name, root / f".agents/skills/{name}/SKILL.md")
    resolved = path.resolve(strict=True)
    allowed = (pstack if name in pinned else root).resolve()
    if not resolved.is_relative_to(allowed):
        raise ValueError(f"source {name!r} resolved outside {allowed}: {resolved}")
    return resolved


def source_row(name: str, path: Path) -> JsonObject:
    raw = path.read_bytes()
    return {"name": name, "path": str(path), "sha256": sha256(raw).hexdigest(),
            "content": raw.decode("utf-8")}


def method_sources(root: Path, contract: JsonObject) -> list[JsonObject]:
    configured = os.environ.get(env_name("PSTACK_ROOT"))
    pstack = Path(configured).resolve() if configured else PINNED_PSTACK
    rows: list[JsonObject] = []
    for name in source_names(contract):
        rows.append(source_row(name, source_path(root, pstack, contract, name)))
        if name == "implement" and "# Implement pointer" in cast(str, rows[-1]["content"]):
            rows.append(source_row("implement:pristine", PINNED_IMPLEMENT.resolve(strict=True)))
    return rows


def gates_path(root: Path, contract: JsonObject) -> Path:
    relative = safe_relative(contract.get("gates"), "gates")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"GATES.md does not exist inside the repository: {relative!r}")
    return path


def prepare_engagement(payload: Mapping[str, object]) -> tuple[JsonObject, JsonObject]:
    root = repo_root(payload)
    state = load_state(payload)
    if state.get("route") not in ROUTES:
        raise ValueError(f"engage requires an explicit $plan-flow or $implement-flow route, "
                         f"and this session has route={state.get('route')!r}")
    contract_path, contract = load_contract(root, payload.get("scope"))
    validate_contract(contract, state["route"])
    gates = gates_path(root, contract)
    require_ignored(root, (contract_path, gates))
    sources = method_sources(root, contract)
    state["ready"] = ready_record(state, contract_path, gates, sources)
    state["scope"] = contract_path.parent.name
    bind_unlazy_session(payload, contract_path.parent)
    state.pop("rearm_reason", None)
    packet = {"method_packet": {"route": state["route"], "epoch": state["epoch"],
                                "contract": contract, "sources": sources}}
    return packet, state


def bind_unlazy_session(payload: Mapping[str, object], scope_dir: Path) -> None:
    """Tell the pinned unlazy Stop wall which pipeline this session owns.

    Unlazy resolves an ambiguous set of scopes by reading `<scope>/session`.
    Writing it here means engaging a route also arms the real gates wall, with
    no second mechanism to keep in step.
    """
    session = str(payload.get("session_id") or payload.get("sessionId") or "anonymous")
    (scope_dir / "session").write_text(session + "\n", encoding="utf-8")


def require_ignored(root: Path, paths: tuple[Path, Path]) -> None:
    if not (root / ".git").exists():
        return
    tracked = [str(path.relative_to(root)) for path in paths if subprocess.run(
        ("git", "check-ignore", "--quiet", "--", str(path.relative_to(root))),
        cwd=root, check=False,
    ).returncode != 0]
    if tracked:
        raise ValueError(f"METHOD.json and GATES.md must both be ignored by Git, "
                         f"and these are tracked: {tracked}")


def ready_record(
    state: JsonObject, contract_path: Path, gates: Path, sources: list[JsonObject],
) -> JsonObject:
    hashes = {cast(str, row["name"]): cast(str, row["sha256"]) for row in sources}
    return {
        "epoch": state["epoch"], "scope": contract_path.parent.name,
        "source_hashes": hashes, "contract": str(contract_path), "gates": str(gates),
        "contract_hash": sha256(contract_path.read_bytes()).hexdigest(),
        "gates_hash": sha256(gates.read_bytes()).hexdigest(),
    }


def current_contract(payload: Mapping[str, object], state: JsonObject) -> JsonObject:
    ready = state.get("ready")
    if not isinstance(ready, dict) or ready.get("epoch") != state.get("epoch"):
        raise_unready(payload, state)
    path = Path(cast(str, ready["contract"]))
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"METHOD.json must contain an object, got {type(value).__name__}")
    validate_ready_digests(payload, state, ready, path, value)
    return value


def raise_unready(payload: Mapping[str, object], state: JsonObject) -> None:
    """Explain what is missing: the contract itself, or the engage call."""
    root = repo_root(payload)
    try:
        _, contract = load_contract(root, state.get("scope"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"METHOD.json is required before a production write. {error}") from error
    validate_contract(contract, state.get("route"))
    gates_path(root, contract)
    reason = state.get("rearm_reason")
    suffix = f" after {reason}" if reason else ""
    scope = state.get("scope") or "<scope>"
    raise ValueError(
        f"The method has not entered this session{suffix}. "
        f"Run the guard's engage {scope} command before this write."
    )


def validate_ready_digests(
    payload: Mapping[str, object], state: JsonObject, ready: JsonObject,
    contract_path: Path, contract: JsonObject,
) -> None:
    gates = gates_path(repo_root(payload), contract)
    artifacts_current = (
        sha256(contract_path.read_bytes()).hexdigest() == ready.get("contract_hash")
        and sha256(gates.read_bytes()).hexdigest() == ready.get("gates_hash")
    )
    if not artifacts_current:
        rearm(payload, state, "contract or gates digest change")
        raise ValueError(f"The METHOD.json or GATES.md digest changed under "
                         f"{contract_path.parent.name}. Run engage again.")
    current = {cast(str, row["name"]): cast(str, row["sha256"])
               for row in method_sources(repo_root(payload), contract)}
    if current != ready.get("source_hashes"):
        rearm(payload, state, "source digest change")
        raise ValueError(f"A method source digest changed under "
                         f"{state.get('scope')!r}. Run engage again.")


def rearm(payload: Mapping[str, object], state: JsonObject, reason: str) -> None:
    state.pop("ready", None)
    state["rearm_reason"] = reason
    save_state(payload, state)


def session_start(payload: Mapping[str, object]) -> JsonObject:
    source = str(payload.get("source") or "")
    if source not in {"compact", "clear"}:
        return {}
    state = load_state(payload)
    if state.get("route") in ROUTES:
        rearm(payload, state, source)
    return {}


def subagent_start(payload: Mapping[str, object]) -> JsonObject:
    state = load_state(payload)
    try:
        contract = current_contract(payload, state)
        ownership = ", ".join(path_list(contract.get("owns"), "owns"))
        context = f"Active route is {state['route']}. {NO_MEMO} Ownership is limited to {ownership}."
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        context = f"Method guard state error: {error}. Stop work and report this error to the parent."
    return {"hookSpecificOutput": {
        "hookEventName": "SubagentStart", "additionalContext": context,
    }}
