#!/usr/bin/env python3
"""Build a standalone, private export of the reusable agent method."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Iterable, Sequence, TextIO


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET = Path.home() / "trading-skills"
VENDOR_ROOT = ROOT / "vendor/agent-sources"


@dataclass(frozen=True)
class SourcePin:
    """Describe one upstream selection copied under its immutable commit."""

    commit: str
    origin: str
    selection: str
    paths: tuple[str, ...]


PINS = {
    "akita": SourcePin(
        "bbd8e681c14c0f57b2e5ea63e4d1c0043a6890da",
        "https://github.com/akitaonrails/akitaonrails.github.io",
        "akita-article",
        ("README.md", "content/2026/04/20/clean-code-para-agentes-de-ia/index.en.md"),
    ),
    "bigpowers": SourcePin(
        "c0209032fb978d730a416167cd8f1e91e411650b",
        "https://github.com/danielvm-git/bigpowers",
        "ousterhout-subset",
        (
            "LICENSE", "docs/PRINCIPLES.md", "docs/references/ousterhout.md",
            "skills/deepen-architecture", "skills/design-interface",
            "skills/develop-tdd/deep-modules.md", "skills/develop-tdd/refactoring.md",
        ),
    ),
    "karpathy": SourcePin(
        "2c606141936f1eeef17fa3043a72095b4765b9c2",
        "https://github.com/multica-ai/andrej-karpathy-skills", "full", (".",),
    ),
    "pocock": SourcePin(
        "5b15a47f2d7150f545fbcacbfe381787fc0230dc",
        "https://github.com/mattpocock/skills", "method-subset",
        (
            "LICENSE", "skills/engineering/ask-matt", "skills/engineering/implement",
            "skills/engineering/tdd", "skills/productivity/teach",
        ),
    ),
    "pstack": SourcePin(
        "46125561306434d8a1d7745d540d8932ab0cd2a2",
        "https://github.com/cursor/plugins", "poteto-mode",
        ("pstack/LICENSE", "pstack/skills/poteto-mode"),
    ),
    "unlazy": SourcePin(
        "754d9a68109e39b836cc72a39fb9a823f9d6b613",
        "https://github.com/Leonxlnx/unlazy", "runtime-subset",
        ("LICENSE", "references", "scripts", "templates"),
    ),
}

CODEX_HOOK_MODULES = (
    "memory_ledger_hooks.py", "method_guard.py", "method_guard_rules.py",
    "method_guard_support.py", "shell_reading.py", "transcript_archive.py",
)
CLAUDE_HOOK_MODULES = (
    "memory_ledger_hooks.py", "method_guard.py", "method_guard_rules.py",
    "method_guard_support.py", "shell_reading.py", "transcript_archive.py",
)
TOOL_MODULES = (
    "brief_lint.py", "canary_driver.py", "clean_code_lint.py",
    "export_trading_skills.py", "memory_ledger.py", "method_canaries.py",
    "run_method_canaries.py", "unslop_allowlist.txt", "unslop_lint.py", "unslop_rules.py",
)
GENERATED_TOOL_MODULES = ("pod_local_lock.py",)
TEST_MODULES = (
    "hook_imports.py", "test_agent_method_guard.py", "test_claude_method_guard.py",
    "test_claude_method_documents.py",
    "test_export_trading_skills.py", "test_memory_hooks.py",
    "test_method_enforcement.py", "test_shell_reading.py",
)
ALLOWED_TOP_LEVEL = {
    ".agents", ".claude", ".codex", ".gitignore", "AGENTS.md", "CLAUDE.md",
    "MANIFEST.json", "README.md", "install.py", "tests", "tools", "vendor",
}
EXCLUDED_SOURCE_TREES = (
    ".codex/harness", ".unlazy", "MEMORY.md", "START_HERE.md", "artifacts", "data",
    "design", "engine", "evidence", "provenance", "research", "transcripts",
)
SECRET_PATTERNS = (
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"(?i)aws_secret_access_key\s*[=:]"),
    re.compile(
        r"(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)"
        r"\s*[=:]\s*['\"]?[A-Za-z0-9_./+=-]{16,}"
    ),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
)
SECRET_BASENAMES = {
    ".env", ".netrc", ".npmrc", ".pypirc", "credentials.json", "id_ed25519", "id_rsa",
}
TEXT_SUFFIXES = {
    ".js", ".json", ".md", ".mjs", ".py", ".sh", ".toml", ".txt", ".yaml", ".yml",
}
PORTABLE_LOCK_MODULE = '''"""Use process locks on local temporary storage."""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import os
from pathlib import Path
import tempfile
from typing import Iterator


LOCK_ROOT = Path(tempfile.gettempdir()) / "codex-method-locks"


def pod_local_lock_path(target: os.PathLike[str] | str) -> Path:
    """Return the local lock path for one absolute target path."""
    digest = hashlib.sha256(str(Path(target).resolve()).encode()).hexdigest()[:24]
    return LOCK_ROOT / f"{digest}.lock"


@contextmanager
def pod_local_flock(target: os.PathLike[str] | str) -> Iterator[Path]:
    """Hold an advisory process lock for one target path."""
    lock_path = pod_local_lock_path(target)
    LOCK_ROOT.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield lock_path
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
'''


def reset(target: Path) -> None:
    """Rebuild the target while preserving only its Git metadata."""
    resolved = target.resolve()
    if resolved in {Path.home().resolve(), ROOT.resolve(), Path("/")}:
        raise ValueError(f"export target {resolved} is unsafe; expected a dedicated directory")
    target.mkdir(parents=True, exist_ok=True)
    for entry in target.iterdir():
        if entry.name == ".git":
            continue
        shutil.rmtree(entry) if entry.is_dir() and not entry.is_symlink() else entry.unlink()


def copy_file(source: Path, destination: Path) -> int:
    """Copy one required file and fail with its missing source path."""
    if not source.is_file():
        raise ValueError(f"export source {source} is missing; expected a regular file")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return 1


def copy_tree(source: Path, destination: Path) -> int:
    """Copy one required directory and return its source file count."""
    if not source.is_dir():
        raise ValueError(f"export source {source} is missing; expected a directory")
    shutil.copytree(source, destination, dirs_exist_ok=True, symlinks=False)
    return sum(path.is_file() for path in source.rglob("*"))


def copy_named(names: Iterable[str], source: Path, destination: Path) -> int:
    """Copy named files between two directories."""
    return sum(copy_file(source / name, destination / name) for name in names)


def copy_selection(source: Path, destination: Path, relative: str) -> int:
    """Copy one pinned file or subtree without changing its relative path."""
    selected = source / relative
    target = destination if relative == "." else destination / relative
    return copy_tree(selected, target) if selected.is_dir() else copy_file(selected, target)


def export_vendor(target: Path) -> int:
    """Copy immutable upstream selections under their original commit paths."""
    copied = 0
    for name, pin in PINS.items():
        source = VENDOR_ROOT / name / pin.commit
        destination = target / "vendor/agent-sources" / name / pin.commit
        copied += sum(copy_selection(source, destination, path) for path in pin.paths)
    return copied


def portable_hooks_config() -> str:
    """Return Codex hook commands with the repository path tokenized."""
    source = ROOT / "tools/harness_templates/hooks.json"
    return source.read_text(encoding="utf-8").replace(str(ROOT), "__REPO__")


def write_hooks_config(destination: Path) -> int:
    """Write a portable Codex hook config at one bundle path."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(portable_hooks_config(), encoding="utf-8")
    return 1


def portable_claude_settings() -> str:
    """Return Claude settings with the repository path tokenized."""
    source = ROOT / ".claude/settings.json"
    return source.read_text(encoding="utf-8").replace(str(ROOT), "__REPO__")


def export_codex(target: Path) -> int:
    """Copy the Codex hooks, their templates, config, and shared contract."""
    hooks = ROOT / "tools/harness_templates/hooks"
    copied = copy_named(CODEX_HOOK_MODULES, hooks, target / ".codex/hooks")
    copied += copy_named(CODEX_HOOK_MODULES, hooks, target / "tools/harness_templates/hooks")
    copied += copy_file(
        hooks / "test_transcript_archive.py",
        target / "tools/harness_templates/hooks/test_transcript_archive.py",
    )
    copied += write_hooks_config(target / "tools/harness_templates/hooks.json")
    copied += write_hooks_config(target / ".codex/hooks.json")
    copied += copy_file(ROOT / "AGENTS.md", target / "AGENTS.md")
    return copied


def export_claude(target: Path) -> int:
    """Copy Claude hooks, settings, worker, and generated contract."""
    hooks = ROOT / "tools/harness_templates/hooks"
    copied = 0
    for name in CLAUDE_HOOK_MODULES:
        source_name = "claude_method_guard.py" if name == "method_guard.py" else name
        copied += copy_file(hooks / source_name, target / ".claude/hooks" / name)
    copied += copy_file(
        hooks / "claude_method_guard.py",
        target / "tools/harness_templates/hooks/claude_method_guard.py",
    )
    settings = target / ".claude/settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(portable_claude_settings(), encoding="utf-8")
    copied += 1
    copied += copy_tree(ROOT / ".claude/agents", target / ".claude/agents")
    copied += copy_file(ROOT / "CLAUDE.md", target / "CLAUDE.md")
    return copied


def portable_shell_test(body: str) -> str:
    """Tokenize the repository path once and accept an already-portable fixture."""
    source = 'absolute = "/usr/bin/python3 /workspace/.codex/hooks/method_guard.py engage fixture"'
    portable = ('absolute = f"/usr/bin/python3 {HOOKS.parents[2]}/.codex/hooks/'
                'method_guard.py engage fixture"')
    source_count = body.count(source)
    portable_count = body.count(portable)
    if (source_count, portable_count) == (1, 0):
        return body.replace(source, portable)
    if (source_count, portable_count) == (0, 1):
        return body
    raise ValueError(
        f"portable shell test markers source={source_count} portable={portable_count}; expected one"
    )


def distribution_source(template_name: str, installed_name: str) -> Path:
    """Select a source-tree template or its installed distribution copy."""
    template = ROOT / "tools/harness_templates" / template_name
    if template.is_file():
        return template
    installed = ROOT / installed_name
    if installed.is_file():
        return installed
    raise ValueError(
        f"distribution source missing: expected {template} or {installed}"
    )


def export_tests(target: Path) -> int:
    """Copy focused tests and make the shell test derive its installed root."""
    copied = copy_named(TEST_MODULES, ROOT / "tests", target / "tests")
    shell_test = target / "tests/test_shell_reading.py"
    body = shell_test.read_text(encoding="utf-8")
    shell_test.write_text(portable_shell_test(body), encoding="utf-8")
    copied += copy_tree(
        ROOT / "tests/fixtures/claude_hook_payloads",
        target / "tests/fixtures/claude_hook_payloads",
    )
    return copied


def export_generated_tools(target: Path) -> int:
    """Write portable helpers whose repository source contains project policy."""
    destination = target / "tools/pod_local_lock.py"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(PORTABLE_LOCK_MODULE, encoding="utf-8")
    return 1


def export_runtime(target: Path) -> int:
    """Copy canonical skills, public tools, tests, installer, and guide."""
    copied = copy_tree(ROOT / ".agents/skills", target / ".agents/skills")
    copied += copy_named(TOOL_MODULES, ROOT / "tools", target / "tools")
    copied += export_generated_tools(target)
    copied += export_tests(target)
    copied += copy_file(distribution_source("export_install.py", "install.py"),
                        target / "install.py")
    copied += copy_file(distribution_source("export_readme.md", "README.md"),
                        target / "README.md")
    (target / "install.py").chmod(0o755)
    (target / ".gitignore").write_text(
        "__pycache__/\n*.py[cod]\n.unlazy/\nMEMORY.md\n", encoding="utf-8",
    )
    return copied + 1


def sha256_file(path: Path) -> str:
    """Return one file's content digest."""
    return sha256(path.read_bytes()).hexdigest()


def exported_files(target: Path) -> dict[str, str]:
    """Return the exact pre-manifest file inventory and content digests."""
    files = {}
    for path in sorted(candidate for candidate in target.rglob("*") if candidate.is_file()):
        relative = path.relative_to(target)
        if ".git" not in relative.parts and relative.name != "MANIFEST.json":
            files[str(relative)] = sha256_file(path)
    return files


def source_pin_manifest() -> dict[str, dict[str, object]]:
    """Return the exact provenance fields for every selected upstream source."""
    return {
        name: {"commit": pin.commit, "origin": pin.origin, "selection": pin.selection,
               "paths": list(pin.paths)}
        for name, pin in PINS.items()
    }


def write_manifest(target: Path, counts: dict[str, int]) -> None:
    """Record every exported file, source pin, and distribution exclusion."""
    manifest = {
        "schema_version": 2,
        "source_repository": "private research repository, not exported",
        "pins": source_pin_manifest(),
        "claude_hook_modules": list(CLAUDE_HOOK_MODULES),
        "codex_hook_modules": list(CODEX_HOOK_MODULES),
        "tool_modules": list((*TOOL_MODULES, *GENERATED_TOOL_MODULES)),
        "test_modules": list(TEST_MODULES),
        "file_counts": counts,
        "files": exported_files(target),
        "excluded_source_trees": list(EXCLUDED_SOURCE_TREES),
    }
    (target / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )


def scan_secrets(target: Path) -> list[str]:
    """Return paths containing credential-shaped text without returning the text."""
    hits = []
    for path in sorted(candidate for candidate in target.rglob("*") if candidate.is_file()):
        relative = path.relative_to(target)
        if ".git" in relative.parts:
            continue
        if path.name in SECRET_BASENAMES:
            hits.append(str(relative))
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        if any(pattern.search(body) for pattern in SECRET_PATTERNS):
            hits.append(str(relative))
    return hits


def audit(target: Path) -> list[str]:
    """Return every condition that makes an export unsafe to install."""
    unexpected = sorted(entry.name for entry in target.iterdir()
                        if entry.name not in ALLOWED_TOP_LEVEL and entry.name != ".git")
    errors = [f"unexpected top-level entry {name!r}" for name in unexpected]
    errors.extend(f"credential-shaped text in {name}" for name in scan_secrets(target))
    return errors


def build_export(target: Path) -> dict[str, int]:
    """Copy every export category and write its exact manifest."""
    reset(target)
    counts = {
        "claude": export_claude(target),
        "codex": export_codex(target),
        "runtime": export_runtime(target),
        "vendor": export_vendor(target),
    }
    write_manifest(target, counts)
    return counts


def main(argv: Sequence[str] | None = None, stdout: TextIO = sys.stdout) -> int:
    """Build and audit one deterministic agent-method export."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) > 1:
        raise ValueError(f"export arguments {arguments!r} are invalid; expected at most one target")
    target = Path(arguments[0]) if arguments else DEFAULT_TARGET
    counts = build_export(target)
    errors = audit(target)
    if errors:
        raise ValueError(f"export is not publishable: {errors[:5]}")
    stdout.write(
        f"EXPORT PASS target={target} files={len(exported_files(target)) + 1} "
        + " ".join(f"{name}={count}" for name, count in sorted(counts.items()))
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
