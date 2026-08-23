"""Enforcement rules both clients apply, with one source per rule.

The policy in `method_guard_support` decides what the method contract means.
This module decides what a tool call is allowed to do under it. Both client
adapters call in here, so a rule cannot hold on Codex and lapse on Claude.

The unslop wall calls `tools/unslop_lint.py` rather than carrying its own copy
of the patterns. The lint is the law's single source of truth, so the wall
enforces every rule the lint knows, not the two a hand-written regex remembered.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
import json
from hashlib import sha256
import importlib.util
from pathlib import Path
import re
import shlex
import subprocess
import sys
from types import ModuleType
from typing import Mapping, Sequence, cast

from method_guard_support import (
    JsonObject,
    NO_MEMO,
    ROUTES,
    path_list,
    repo_root,
)

ROUTE_TOKEN = re.compile(r"(?<![\w-])[$/](plan-flow|implement-flow)(?![\w-])")
BOOTSTRAP = re.compile(r"\.unlazy/[a-z0-9][a-z0-9-]*/(?:METHOD\.json|GATES\.md)\Z")
ALWAYS_WRITABLE = ("MEMORY.md",)
PINNED_ROOTS = ("vendor/agent-sources/", ".agents/skills/")
MUTATING_COMMANDS = frozenset({
    "cp", "mv", "rm", "touch", "mkdir", "install", "tee", "truncate", "chmod", "dd",
})
READONLY_COMMANDS = frozenset({
    "cat", "find", "grep", "head", "ls", "pwd", "readlink", "rg", "sed", "stat",
    "tail", "test", "wc", "diff", "echo", "which",
})
READONLY_GIT = frozenset({"diff", "log", "show", "status", "branch", "blame"})
REDIRECT = re.compile(r"(?:^|\s)(?:>>?|[12]>)\s*([^\s;&|]+)")
_UNSLOP: ModuleType | None = None


@dataclass(frozen=True)
class WriteScan:
    """What a tool call can change: nothing, named paths, or something opaque."""

    kind: str
    paths: tuple[str, ...] = ()


def lint_candidates(root: Path) -> list[Path]:
    """Return where the unslop lint may live, install location first.

    The hook is installed at `<repo>/.claude/hooks/` or `<repo>/.codex/hooks/`
    and lives in the tree at `<repo>/tools/harness_templates/hooks/`. Resolving
    from the hook's own location keeps the wall working when the repository the
    guard is judging is not the repository the guard was installed from.
    """
    here = Path(__file__).resolve()
    bases = [here.parents[2], here.parents[3], root]
    return [base / "tools/unslop_lint.py" for base in bases]


def unslop_module(root: Path) -> ModuleType:
    """Load the unslop lint once per process, from wherever it is installed."""
    global _UNSLOP
    if _UNSLOP is not None:
        return _UNSLOP
    found = next((path for path in lint_candidates(root) if path.is_file()), None)
    if found is None:
        raise ValueError(f"unslop lint not found; looked in {lint_candidates(root)}")
    spec = importlib.util.spec_from_file_location("guard_unslop_lint", found)
    if spec is None or spec.loader is None:
        raise ValueError(f"unslop lint could not be loaded from {found}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["guard_unslop_lint"] = module
    spec.loader.exec_module(module)
    _UNSLOP = module
    return _UNSLOP


def unslop_violation(message: str, root: Path) -> str | None:
    """Return the first unslop violation in a user-visible message."""
    if not message.strip():
        return None
    lint = unslop_module(root)
    findings = lint.lint_text(message, "<reply>", lint.read_allowlist())
    if not findings:
        return None
    first = findings[0]
    return (f"unslop rule {first.rule} ({first.name}) in the reply: {first.message} "
            f"Offending text: {first.span!r}. Rewrite it before finishing.")


def route_from_prompt(prompt: str) -> str | None:
    """Return the route the prompt selects, or None when it names neither."""
    matches = ROUTE_TOKEN.findall(prompt)
    return matches[-1] if matches else None


def normalized_path(root: Path, value: str) -> str | None:
    """Return a repository-relative path, or None when it lies outside the repo.

    A write outside the repository is not this guard's business. Denying those
    would block the scratchpad, the plan file and the agent's own memory, which
    is how an enforcement gate turns into a deadlock.
    """
    candidate = Path(value)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    if not resolved.is_relative_to(root):
        return None
    return resolved.relative_to(root).as_posix()


def repository_paths(root: Path, values: Sequence[str]) -> list[str]:
    """Return only the write targets that land inside the repository."""
    return [path for path in (normalized_path(root, value) for value in values) if path]


def bootstrap_only(paths: Sequence[str]) -> bool:
    """Report whether every path is a method contract or its gates file.

    These stay writable without a route. They are the artifacts that unlock the
    route, so gating them would leave no way out of a denial.
    """
    return bool(paths) and all(BOOTSTRAP.fullmatch(path) for path in paths)


def always_writable(paths: Sequence[str]) -> bool:
    """Report whether every path is exempt from the route gate."""
    return bool(paths) and all(path in ALWAYS_WRITABLE for path in paths)


def planning_paths(paths: Sequence[str]) -> bool:
    """Report whether every path is a planning artifact the plan route may write."""
    return bool(paths) and all(path.startswith("design/") and path.endswith(".md")
                               for path in paths)


def owned(path: str, patterns: Sequence[str]) -> bool:
    """Report whether one path falls inside the contract's declared ownership."""
    return any(fnmatchcase(path, pattern) or
               (pattern.endswith("/**") and path == pattern[:-3]) for pattern in patterns)


def validate_write_paths(paths: Sequence[str], contract: JsonObject) -> None:
    """Refuse a write to pinned sources or outside the contract's ownership."""
    patterns = path_list(contract.get("owns"), "owns")
    for path in paths:
        if path.startswith(PINNED_ROOTS):
            raise ValueError(f"Direct writes to pinned or canonical sources are denied: {path}")
        if not owned(path, patterns):
            raise ValueError(f"Write path {path!r} is outside METHOD.json owns {patterns!r}")


def command_words(command: str) -> list[str] | None:
    """Split a shell command, or None when it cannot be parsed."""
    try:
        return shlex.split(command)
    except ValueError:
        return None


def command_write_paths(command: str) -> list[str] | None:
    """Return the paths a shell command writes, or None when it names none."""
    words = command_words(command)
    if words is None:
        return []
    executable = Path(words[0]).name if words else ""
    redirects = REDIRECT.findall(command)
    if executable in MUTATING_COMMANDS or (executable == "sed" and "-i" in words):
        return [word for word in words[1:] if not word.startswith("-")] + redirects
    if redirects:
        return redirects
    return [] if ">" in command else None


def scan_command(command: str) -> WriteScan:
    """Classify one shell command by what it can change.

    Three outcomes, not two. A read changes nothing and needs no route. A write
    with named targets is checked against ownership. Anything else is opaque:
    `python build.py` may write, so it needs the method in context even though
    no path can be checked.
    """
    if readonly_command(command):
        return WriteScan("none")
    paths = command_write_paths(command)
    if paths is None:
        return WriteScan("opaque")
    if not paths:
        return WriteScan("unparsed")
    return WriteScan("paths", tuple(paths))


def readonly_command(command: str) -> bool:
    """Report whether a command is a plain read that needs no route."""
    if re.search(r"[;&|><`]", command):
        return False
    words = command_words(command)
    if not words:
        return False
    executable = Path(words[0]).name
    if executable in READONLY_COMMANDS:
        return True
    return executable == "git" and len(words) > 1 and words[1] in READONLY_GIT


def brief_rules() -> tuple[tuple[re.Pattern[str], str], ...]:
    """Return the structural rules every subagent brief must satisfy.

    Ownership and the acceptance check come from writing-for-agents: a vague
    completion bound is what produces a half-done leaf. The two shared-codebase
    lines come from separate-before-serializing-shared-state, because a worker
    that assumes it is alone reverts another agent's edits.
    """
    return (
        (re.compile(r"(?im)^\s*(?:Own|Ownership)\b[^\n]+"),
         "Agent brief must state explicit file ownership."),
        (re.compile(r"(?im)^\s*Acceptance check\s*:"),
         "Agent brief must state an Acceptance check with a checkable bound."),
        (re.compile(r"(?i)you are not alone in (?:the )?codebase"),
         "Agent brief must say the worker is not alone in the codebase."),
        (re.compile(r"(?i)do not revert (?:others'|other agents')? ?edits"),
         "Agent brief must say not to revert other agents' edits."),
    )


def validate_brief(brief: object, root: Path) -> None:
    """Check a subagent brief against writing-for-agents and the no-memo law."""
    if not isinstance(brief, str):
        raise ValueError(f"Agent brief must be a string, got {brief!r}")
    if brief.count(NO_MEMO) != 1:
        raise ValueError(f"Agent brief must contain this sentence exactly once: {NO_MEMO}")
    for pattern, reason in brief_rules():
        if not pattern.search(brief):
            raise ValueError(reason)
    violation = unslop_violation(brief, root)
    if violation:
        raise ValueError(f"Agent brief fails unslop. {violation}")


def validate_model_policy(tool_input: Mapping[str, object], contract: JsonObject,
                          key: str, expected_field: str) -> None:
    """Check a spawn matches the contract's model policy for this client."""
    policy = contract.get("model_policy")
    if not isinstance(policy, dict):
        raise ValueError(f"METHOD.json model_policy must be an object, got {policy!r}")
    expected = policy.get(expected_field)
    actual = tool_input.get(key)
    if expected and actual != expected:
        raise ValueError(f"Agent launch requires {key}={expected!r}, got {actual!r}.")


def diff_digest(root: Path) -> str | None:
    """Return a digest of the working-tree diff, or None when it is empty."""
    result = subprocess.run(("git", "diff", "--binary", "HEAD"), cwd=root,
                            check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return sha256(result.stdout).hexdigest() if result.returncode == 0 and result.stdout else None


def review_receipt_violation(payload: Mapping[str, object], contract: JsonObject) -> str | None:
    """Report production code that changed with no matching review receipt."""
    current = diff_digest(repo_root(payload))
    receipt = contract.get("review_receipt")
    if current and (not isinstance(receipt, dict) or receipt.get("diff_sha256") != current):
        return ("Production code changed without a current review_receipt.diff_sha256 in "
                "METHOD.json. Run the review step, then record the diff digest.")
    return None


def route_selected(state: Mapping[str, object]) -> bool:
    """Report whether a route is active for this session."""
    return state.get("route") in ROUTES


def default_route_reason(paths: Sequence[str]) -> str:
    """Explain the denial when a repository write arrives with no route."""
    targets = ", ".join(paths[:3]) or "the repository"
    return (f"A repository write ({targets}) selects $implement-flow, and its method has not "
            "entered this session. Write .unlazy/<scope>/METHOD.json and its GATES.md, then run "
            "the guard's engage command. Both files stay writable without a route.")


def cast_input(tool_input: object) -> Mapping[str, object]:
    """Return a tool input mapping, or say exactly what arrived instead."""
    if not isinstance(tool_input, dict):
        raise ValueError(f"tool_input must be an object, got {tool_input!r}")
    return cast(Mapping[str, object], tool_input)


UNLAZY_STOP = Path(
    "/workspace/vendor/agent-sources/unlazy/"
    "754d9a68109e39b836cc72a39fb9a823f9d6b613/scripts/stop-hook.mjs"
)
PINNED_NODE = Path("/home/algo/.local/share/fnm/node-versions/v24.19.0/installation/bin/node")


def run_unlazy_stop(payload: Mapping[str, object], root: Path) -> JsonObject:
    """Run the pinned unlazy Stop wall and return its own decision.

    Unlazy owns completion discipline, so its wall is reused rather than
    reimplemented. A missing runtime is reported, never silently skipped.
    """
    if not PINNED_NODE.is_file() or not UNLAZY_STOP.is_file():
        return {"systemMessage": "unlazy Stop wall is not installed; completion is unguarded."}
    try:
        completed = subprocess.run(
            (str(PINNED_NODE), str(UNLAZY_STOP), "--unlazy"), cwd=root,
            input=json.dumps(dict(payload)), text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"systemMessage": f"unlazy Stop wall failed to run: {error}"}
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if completed.returncode != 0:
        return {"systemMessage": f"unlazy Stop wall exited {completed.returncode}: "
                                 f"{completed.stderr.strip()[:200]}"}
    if not lines:
        return {}
    try:
        value = json.loads(lines[-1])
    except json.JSONDecodeError as error:
        return {"systemMessage": f"unlazy Stop wall returned invalid JSON: {error}"}
    return value if isinstance(value, dict) else {}
