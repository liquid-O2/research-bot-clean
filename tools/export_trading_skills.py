#!/usr/bin/env python3
"""Export the reusable agent method into a standalone repository.

What ships is the method and the machinery that enforces it. What never ships
is this project: no trading code, no market data, no experiment artifacts, no
transcripts, no memories, no trust state, no credentials.

The pinned upstream sources ship as the exact subtrees the skills reference,
not as whole vendor checkouts. MANIFEST.json records the commit each came from,
so the full upstream is one clone away.

Re-running rebuilds the tree from scratch, so a retry converges.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import sys
from typing import Iterable, Sequence, TextIO

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET = Path.home() / "trading-skills"
VENDOR = ROOT / "vendor/agent-sources"
PINS = {
    "pstack": "46125561306434d8a1d7745d540d8932ab0cd2a2",
    "pocock": "5b15a47f2d7150f545fbcacbfe381787fc0230dc",
    "unlazy": "754d9a68109e39b836cc72a39fb9a823f9d6b613",
    "akita": "bbd8e681c14c0f57b2e5ea63e4d1c0043a6890da",
}
VENDOR_SUBTREES = {
    "pstack": ("pstack/skills/poteto-mode",),
    "pocock": ("skills/engineering/implement", "skills/engineering/tdd",
               "skills/engineering/ask-matt", "skills/productivity/teach"),
    "unlazy": ("scripts", "templates", "references"),
    "akita": ("content/2026/04/20/clean-code-para-agentes-de-ia",),
}
HOOK_MODULES = ("method_guard.py", "method_guard_support.py", "method_guard_rules.py",
                "claude_method_guard.py", "memory_ledger_hooks.py", "optmem_lifecycle.py")
TOOL_MODULES = (
    "unslop_lint.py", "unslop_rules.py", "unslop_allowlist.txt", "clean_code_lint.py",
    "brief_lint.py", "memory_ledger.py", "import_optmem_ledger.py",
    "install_claude_skills.py", "install_claude_harness.py", "render_agent_contract.py",
    "run_method_canaries.py", "export_trading_skills.py",
)
TEST_MODULES = ("test_law_lints.py", "test_memory_ledger.py", "test_agent_contract.py",
                "test_claude_method_guard.py")
ALLOWED_TOP_LEVEL = {"skills", "vendor", "hooks", "codex", "claude", "contract",
                     "tools", "tests", "MANIFEST.json", "README.md", "install.py",
                     ".git", ".gitignore"}
EXCLUDED_SOURCES = ("data", "engine", "artifacts", "provenance", "transcripts",
                    ".optmem", ".mempalace", "design", "research", "evidence", "mempalace")
SECRETS = (
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"(?i)aws_secret_access_key\s*[=:]"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
)
TEXT_SUFFIXES = {".py", ".md", ".json", ".txt", ".mjs", ".js", ".yaml", ".yml", ".toml", ".sh"}


def reset(target: Path) -> None:
    """Remove any previous export so the rebuild is exact."""
    if target.exists():
        shutil.rmtree(target / "skills", ignore_errors=True)
        shutil.rmtree(target / "vendor", ignore_errors=True)
        shutil.rmtree(target / "claude", ignore_errors=True)
        shutil.rmtree(target / "codex", ignore_errors=True)
        shutil.rmtree(target / "tools", ignore_errors=True)
        shutil.rmtree(target / "tests", ignore_errors=True)
    target.mkdir(parents=True, exist_ok=True)


def copy_tree(source: Path, destination: Path) -> int:
    """Copy one directory and report how many files landed."""
    if not source.is_dir():
        raise ValueError(f"expected a directory to export, got {source}")
    shutil.copytree(source, destination, dirs_exist_ok=True, symlinks=False)
    return sum(1 for path in destination.rglob("*") if path.is_file())


def copy_named(sources: Iterable[Path], destination: Path) -> int:
    """Copy named files into one directory."""
    destination.mkdir(parents=True, exist_ok=True)
    copied = 0
    for source in sources:
        if not source.is_file():
            raise ValueError(f"expected a file to export, got {source}")
        shutil.copy2(source, destination / source.name)
        copied += 1
    return copied


def export_skills(target: Path) -> int:
    """Copy the canonical skill bodies, dereferencing nothing."""
    return copy_tree(ROOT / ".agents/skills", target / "skills")


def export_one_vendor(name: str, commit: str, target: Path) -> int:
    """Copy one upstream's referenced subtrees and its licences."""
    base = VENDOR / name / commit
    present = [subtree for subtree in VENDOR_SUBTREES[name] if (base / subtree).is_dir()]
    copied = sum(copy_tree(base / subtree, target / "vendor" / name / subtree)
                 for subtree in present)
    return copied + copy_licenses(base, target / "vendor" / name)


def export_vendor(target: Path) -> int:
    """Copy only the pinned subtrees the skills and hooks actually reference."""
    return sum(export_one_vendor(name, commit, target) for name, commit in PINS.items())


def copy_licenses(base: Path, destination: Path) -> int:
    """Copy every licence the upstream shipped."""
    licences = [path for path in base.glob("LICENSE*") if path.is_file()]
    return copy_named(licences, destination) if licences else 0


def export_settings(target: Path) -> int:
    """Copy the hook wiring with this repository's path replaced by a token.

    An exported settings file full of absolute paths from another machine is a
    broken settings file. The installer substitutes the token for the target.
    """
    destination = target / "claude"
    destination.mkdir(parents=True, exist_ok=True)
    body = (ROOT / ".claude/settings.json").read_text(encoding="utf-8")
    (destination / "settings.json").write_text(body.replace(str(ROOT), "__REPO__"),
                                               encoding="utf-8")
    return 1


def export_clients(target: Path) -> int:
    """Copy both clients' hooks, settings and the pinned subagent."""
    hooks = ROOT / "tools/harness_templates/hooks"
    copied = copy_named((hooks / name for name in HOOK_MODULES), target / "hooks")
    copied += copy_named([ROOT / "tools/harness_templates/hooks.json"], target / "codex")
    copied += export_settings(target)
    copied += copy_named([ROOT / ".claude/agents/method-worker.md"], target / "claude/agents")
    copied += copy_named([ROOT / "tools/harness_templates/memory-agent-block.md"],
                         target / "contract")
    copied += copy_named([ROOT / "AGENTS.md", ROOT / "CLAUDE.md"], target / "contract")
    return copied


def export_tools(target: Path) -> int:
    """Copy the lints, the ledger, the installers and the verifiers."""
    copied = copy_named((ROOT / "tools" / name for name in TOOL_MODULES), target / "tools")
    verifiers = ("agent_harness_verify_common.py", "agent_harness_verify_static.py",
                 "verify_agent_harness.py")
    copied += copy_named((ROOT / "tools" / name for name in verifiers), target / "tools")
    copied += copy_named((ROOT / "tests" / name for name in TEST_MODULES), target / "tests")
    copied += copy_tree(ROOT / "tests/fixtures/claude_hook_payloads",
                        target / "tests/fixtures/claude_hook_payloads")
    return copied


def export_guide(target: Path) -> int:
    """Copy the installer and the README that explain how to use this."""
    templates = ROOT / "tools/harness_templates"
    shutil.copy2(templates / "export_install.py", target / "install.py")
    (target / "install.py").chmod(0o755)
    shutil.copy2(templates / "export_readme.md", target / "README.md")
    shutil.copy2(ROOT / "tools/harness_templates/hooks.json", target / "codex/hooks.json")
    (target / ".gitignore").write_text(
        "__pycache__/\n*.py[cod]\n.unlazy/\nMEMORY.md\n", encoding="utf-8")
    return 4


def write_manifest(target: Path, counts: dict[str, int]) -> None:
    """Record the pins and what this export contains."""
    manifest = {
        "schema_version": 1,
        "source_repository": "private research repository, not exported",
        "pins": PINS,
        "vendor_subtrees": {name: list(paths) for name, paths in VENDOR_SUBTREES.items()},
        "file_counts": counts,
        "excluded_source_trees": list(EXCLUDED_SOURCES),
    }
    (target / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                                          encoding="utf-8")


def audit_layout(target: Path) -> list[str]:
    """Return any top-level entry this export is not supposed to contain."""
    return [entry.name for entry in target.iterdir() if entry.name not in ALLOWED_TOP_LEVEL]


def scan_secrets(target: Path) -> list[str]:
    """Return every file holding something that looks like a credential."""
    hits: list[str] = []
    for path in sorted(target.rglob("*")):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(pattern.search(text) for pattern in SECRETS):
            hits.append(str(path.relative_to(target)))
    return hits


def audit(target: Path) -> list[str]:
    """Return every reason this export must not be published yet."""
    strays = [f"unexpected top-level entry {name!r}" for name in audit_layout(target)]
    return strays + [f"credential-shaped text in {name}" for name in scan_secrets(target)]


def main(argv: Sequence[str] | None = None, stdout: TextIO = sys.stdout) -> int:
    """Build the export tree and report what it holds."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    target = Path(arguments[0]) if arguments else DEFAULT_TARGET
    reset(target)
    counts = {"skills": export_skills(target), "vendor": export_vendor(target),
              "clients": export_clients(target), "tools": export_tools(target),
              "guide": export_guide(target)}
    write_manifest(target, counts)
    strays = audit(target)
    if strays:
        raise ValueError(f"export is not publishable: {strays[:5]}")
    total = sum(1 for path in target.rglob("*") if path.is_file())
    stdout.write(f"EXPORT PASS target={target} files={total} "
                 + " ".join(f"{k}={v}" for k, v in sorted(counts.items())) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
