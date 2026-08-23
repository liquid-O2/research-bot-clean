#!/usr/bin/env python3
"""Drive the installed method guard and check every denial and every allowance.

Unit tests prove a function returns a value. These canaries drive the installed
hook script the way the client drives it, with the payload shapes captured from
live hook runs, and check the verdict the client would actually receive.

Each canary states what it expects and why it matters, so a failure names the
law that stopped being enforced rather than a line number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Callable, Sequence, TextIO

ROOT = Path(__file__).resolve().parent.parent
SCOPE = "claude-method-port"


@dataclass(frozen=True)
class Client:
    """Where one client's guard lives and how it names its inputs."""

    name: str
    guard: Path
    env_prefix: str
    write_tool: str
    spawn_tool: str
    brief_key: str
    stdin_engage: bool


CLIENTS = {
    "claude": Client("claude", ROOT / ".claude/hooks/method_guard.py", "CLAUDE_METHOD",
                     "Write", "Agent", "prompt", stdin_engage=False),
    "codex": Client("codex", ROOT / ".codex/hooks/method_guard.py", "CODEX_METHOD",
                    "apply_patch", "collaboration.spawn_agent", "message", stdin_engage=True),
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
                            env=environment, check=False)
    if result.returncode != 0:
        return {"_error": result.stderr.strip() or f"exit {result.returncode}"}
    return json.loads(result.stdout or "{}")


def guard_environment(state: Path) -> dict[str, str]:
    """Return the environment that points one guard at this canary run."""
    return {**os.environ, f"{ACTIVE.env_prefix}_STATE_ROOT": str(state),
            f"{ACTIVE.env_prefix}_REPO_ROOT": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}


def engage(state: Path, scope: str = SCOPE) -> subprocess.CompletedProcess[str]:
    """Run the engage command the denial messages tell the agent to run."""
    environment = guard_environment(state)
    if ACTIVE.stdin_engage:
        payload = json.dumps({"hook_event_name": "Engage", "session_id": "canary",
                              "cwd": str(ROOT), "scope": scope})
        return subprocess.run((sys.executable, str(ACTIVE.guard), "engage"), input=payload,
                              text=True, capture_output=True, env=environment, check=False)
    return subprocess.run((sys.executable, str(ACTIVE.guard), "engage", scope),
                          text=True, capture_output=True, env=environment, check=False)


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


def route_canaries() -> list[Canary]:
    """Canaries for route selection and the default route."""
    return [
        Canary("plan-flow selects the planning route", "user-prompt-submit",
               prompt_payload("clean this up $plan-flow"), "context", "Route plan-flow selected"),
        Canary("implement-flow selects the implementation route", "user-prompt-submit",
               prompt_payload("build it $implement-flow"), "context",
               "Route implement-flow selected"),
        Canary("plan mode alone selects nothing", "user-prompt-submit",
               prompt_payload("please clean up the repo", mode="plan"), "context",
               "No route is selected"),
        Canary("a repository write with no route is denied", "pre-tool-use",
               write_payload(str(ROOT / "tools/canary_probe.py")), "deny",
               "selects $implement-flow"),
    ]


def escape_canaries() -> list[Canary]:
    """Canaries for the writes that must never need a route."""
    return [
        Canary("a write outside the repository passes", "pre-tool-use",
               write_payload("/tmp/scratch/plan.md"), "allow"),
        Canary("a write to MEMORY.md passes", "pre-tool-use",
               write_payload(str(ROOT / "MEMORY.md")), "allow"),
        Canary("a write to the method contract passes", "pre-tool-use",
               write_payload(str(ROOT / f".unlazy/{SCOPE}/METHOD.json")), "allow"),
        Canary("a write to the gates file passes", "pre-tool-use",
               write_payload(str(ROOT / f".unlazy/{SCOPE}/GATES.md")), "allow"),
        Canary("a read-only command passes", "pre-tool-use",
               tool_payload("Bash", {"command": "git status"}), "allow"),
    ]


def plan_route_canaries() -> list[Canary]:
    """Canaries for what the planning route may and may not write."""
    return [
        Canary("plan-flow denies a production write", "pre-tool-use",
               write_payload(str(ROOT / "tools/canary_probe.py")), "deny",
               "plan-flow denies production writes",
               setup=lambda state: select(state, "plan-flow")),
        Canary("plan-flow reaches the planning branch, then asks for its method",
               "pre-tool-use", write_payload(str(ROOT / "design/canary.md")), "deny",
               "engage", setup=lambda state: select(state, "plan-flow")),
    ]


def unengaged(state: Path) -> None:
    """Put the session on the implementation route without its method."""
    select(state, "implement-flow")


def engaged(state: Path) -> None:
    """Put the session on the implementation route with its method in context."""
    select(state, "implement-flow")
    engage(state)


def engaged_then_compacted(state: Path) -> None:
    """Engage, then take the method back out with a compaction."""
    engaged(state)
    compact(state)


def engagement_canaries() -> list[Canary]:
    """Canaries for the packet gate and its re-arm after a compaction."""
    return [
        Canary("an implementation write before engage is denied", "pre-tool-use",
               write_payload(str(ROOT / "tools/canary_probe.py")), "deny",
               "engage", setup=unengaged),
        Canary("an owned write after engage passes", "pre-tool-use",
               write_payload(str(ROOT / "tools/canary_probe.py")), "allow", setup=engaged),
        Canary("an unowned write after engage is denied", "pre-tool-use",
               write_payload(str(ROOT / "engine/canary_probe.py")), "deny",
               "outside METHOD.json owns", setup=engaged),
        Canary("a write to a canonical skill is denied", "pre-tool-use",
               write_payload(str(ROOT / ".agents/skills/unslop/SKILL.md")), "deny",
               "pinned or canonical", setup=engaged),
        Canary("a write after a compaction is denied until engage runs again", "pre-tool-use",
               write_payload(str(ROOT / "tools/canary_probe.py")), "deny",
               "after compact", setup=engaged_then_compacted),
    ]


def brief_canaries() -> list[Canary]:
    """Canaries for what every subagent brief must say."""
    return [
        Canary("a brief without the no-memo sentence is denied", "pre-tool-use",
               spawn_payload("Own: x\nAcceptance check: y\n"), "deny",
               "exactly once", setup=engaged),
        Canary("a brief without ownership is denied", "pre-tool-use",
               spawn_payload(GOOD_BRIEF.replace("Own: tools/scratch_canary.py\n", "")), "deny",
               "file ownership", setup=engaged),
        Canary("a brief without an acceptance check is denied", "pre-tool-use",
               spawn_payload(GOOD_BRIEF.split("Acceptance check")[0]), "deny",
               "Acceptance check", setup=engaged),
    ]


def shared_codebase_canaries() -> list[Canary]:
    """Canaries for the two lines that keep parallel workers out of each other."""
    return [
        Canary("a brief that assumes it is alone is denied", "pre-tool-use",
               spawn_payload(GOOD_BRIEF.replace("You are not alone in the codebase.\n", "")),
               "deny", "not alone", setup=engaged),
        Canary("a brief that may revert other agents is denied", "pre-tool-use",
               spawn_payload(GOOD_BRIEF.replace("Do not revert others' edits.\n", "")),
               "deny", "revert", setup=engaged),
        Canary("an unslopped brief is denied", "pre-tool-use",
               spawn_payload(GOOD_BRIEF + "Of course! delve into it.\n"), "deny",
               "fails unslop", setup=engaged),
    ]


def spawn_canaries() -> list[Canary]:
    """Canaries for the subagent type and model policy."""
    return [
        *([Canary("the wrong subagent type is denied", "pre-tool-use",
                  spawn_payload(GOOD_BRIEF, subagent="general-purpose"), "deny",
                  "subagent_type", setup=engaged),
           Canary("the wrong model is denied", "pre-tool-use",
                  spawn_payload(GOOD_BRIEF, model="haiku"), "deny", "model", setup=engaged)]
          if ACTIVE.name == "claude" else []),
        Canary("a well-formed spawn passes", "pre-tool-use",
               spawn_payload(GOOD_BRIEF), "allow", setup=engaged),
    ]


OPEN_SCOPE = "canary-open-gate"
DONE_SCOPE = "canary-met-gate"


def write_scope(name: str, met: bool) -> None:
    """Create a throwaway unlazy scope so the wall's verdict is ours to set."""
    directory = ROOT / ".unlazy" / name
    directory.mkdir(parents=True, exist_ok=True)
    box = "[x]" if met else "[ ]"
    evidence = "EVIDENCE: exit=0; output=OK" if met else "EVIDENCE: pending"
    (directory / "GATES.md").write_text(
        f"# Gates: {name}\n\nOWNS: tools/canary_probe.py\n\n"
        f"- {box} G1: the canary scope reports a known state\n"
        f"  CHECK: /usr/bin/python3 -c \"print('OK')\"\n  EXPECT: OK\n  CWD: .\n"
        f"  {evidence}\n", encoding="utf-8")


def drop_scope(name: str) -> None:
    """Remove a throwaway scope."""
    shutil.rmtree(ROOT / ".unlazy" / name, ignore_errors=True)


def prose_canaries() -> list[Canary]:
    """Canaries for the two walls that decide whether a turn may end."""
    return [
        Canary("Stop blocks a reply with a long dash", "stop",
               stop_payload("The guard works \N{EM DASH} mostly."), "block", "rule 13",
               scope=DONE_SCOPE),
        Canary("Stop blocks a stock chatbot phrase", "stop",
               stop_payload("Of course! The guard is installed."), "block", "rule 20",
               scope=DONE_SCOPE),
        Canary("Stop allows clean prose once every gate is met", "stop",
               stop_payload("The guard denies an unmethodded write. Every canary passed."),
               "allow", scope=DONE_SCOPE),
        Canary("Stop blocks a done claim while a gate is open", "stop",
               stop_payload("Everything is finished."), "block", "need work",
               scope=OPEN_SCOPE),
        Canary("SubagentStop holds a subagent to the same law", "subagent-stop",
               stop_payload("Done \N{EM DASH} all good.", event="SubagentStop"), "block",
               "rule 13", scope=DONE_SCOPE),
    ]


def all_canaries() -> list[Canary]:
    """Every canary, grouped by the law it checks."""
    return [*route_canaries(), *escape_canaries(), *plan_route_canaries(),
            *engagement_canaries(), *brief_canaries(), *shared_codebase_canaries(),
            *spawn_canaries(), *prose_canaries()]


def run_one(canary: Canary, state_root: Path) -> Outcome:
    """Run one canary in a fresh session state."""
    state = state_root / canary.name.replace(" ", "-")[:60]
    state.mkdir(parents=True, exist_ok=True)
    if canary.setup is not None:
        canary.setup(state)
    verdict, reason = read_verdict(
        run_guard(canary.verb, canary.payload, state, canary.scope))
    return Outcome(canary, verdict, reason)


def packet_outcome(state_root: Path) -> Outcome:
    """Check engage prints the exact sources with digests that match the files."""
    state = state_root / "engage-packet"
    state.mkdir(parents=True, exist_ok=True)
    select(state, "implement-flow")
    result = engage(state)
    canary = Canary("engage prints every source with a matching digest", "engage", {}, "allow")
    if result.returncode != 0:
        return Outcome(canary, "error", result.stderr.strip())
    return Outcome(canary, *verify_packet(json.loads(result.stdout)))


def verify_packet(packet: dict[str, object]) -> tuple[str, str]:
    """Check every packet source matches the bytes on disk."""
    from hashlib import sha256
    sources = packet["method_packet"]["sources"]  # type: ignore[index]
    for row in sources:  # type: ignore[union-attr]
        raw = Path(str(row["path"])).read_bytes()
        if sha256(raw).hexdigest() != row["sha256"] or raw.decode() != row["content"]:
            return "error", f"packet source {row['name']} does not match its file"
    return "allow", f"{len(sources)} sources verified"  # type: ignore[arg-type]


def unchanged_outcome(state_root: Path) -> Outcome:
    """Check a denied write leaves its target byte-identical."""
    from hashlib import sha256
    target = ROOT / "engine/canary_untouched.py"
    canary = Canary("a denied write leaves the target unchanged", "pre-tool-use", {}, "allow")
    if target.exists():
        return Outcome(canary, "error", f"{target} already exists")
    state = state_root / "unchanged"
    state.mkdir(parents=True, exist_ok=True)
    select(state, "implement-flow")
    engage(state)
    before = sorted(p.name for p in target.parent.iterdir())
    run_guard("pre-tool-use", write_payload(str(target)), state)
    after = sorted(p.name for p in target.parent.iterdir())
    digest = sha256(str(after).encode()).hexdigest()[:12]
    if before != after or target.exists():
        return Outcome(canary, "error", "the denied write created a file")
    return Outcome(canary, "allow", f"directory listing unchanged ({digest})")


def report(outcomes: Sequence[Outcome], stdout: TextIO) -> int:
    """Print one line per canary and a verdict for the run."""
    for outcome in outcomes:
        mark = "ok  " if outcome.passed else "FAIL"
        stdout.write(f"{mark} {outcome.canary.name}\n")
        if not outcome.passed:
            stdout.write(f"       expected={outcome.canary.expect!r} "
                         f"got={outcome.verdict!r} reason={outcome.reason[:160]!r}\n")
    failures = [row for row in outcomes if not row.passed]
    if failures:
        stdout.write(f"\nCANARIES FAIL {len(failures)} of {len(outcomes)}\n")
        return 1
    stdout.write(f"\nCANARIES PASS {len(outcomes)} checks\n")
    return 0


def main(argv: Sequence[str] | None = None, stdout: TextIO = sys.stdout) -> int:
    """Run every canary against one installed guard."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    global ACTIVE
    name = arguments[1] if len(arguments) > 1 and arguments[0] == "--client" else "claude"
    ACTIVE = CLIENTS[name]
    if not ACTIVE.guard.is_file():
        raise ValueError(f"no installed guard at {ACTIVE.guard}")
    state_root = Path(tempfile.mkdtemp(prefix="method-canaries-"))
    write_scope(OPEN_SCOPE, met=False)
    write_scope(DONE_SCOPE, met=True)
    try:
        outcomes = [run_one(canary, state_root) for canary in all_canaries()]
        outcomes.append(packet_outcome(state_root))
        outcomes.append(unchanged_outcome(state_root))
        stdout.write(f"client: {ACTIVE.name} guard: {ACTIVE.guard}\n")
        return report(outcomes, stdout)
    finally:
        shutil.rmtree(state_root, ignore_errors=True)
        drop_scope(OPEN_SCOPE)
        drop_scope(DONE_SCOPE)


if __name__ == "__main__":
    raise SystemExit(main())
