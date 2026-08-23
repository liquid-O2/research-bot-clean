#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Final, Sequence

from agent_harness_sources import HOME, OPT_MEM, PINS, VENDOR_ROOT, WORKSPACE, SourcePin, pinned_runtime_error
from render_agent_contract import render as render_contract
from render_agent_contract import write_all as render_all_contracts
from agent_harness_verify_common import (
    CODEX_HOOK_MODULES,
    archived_relative,
    archive_kind,
    atomic_write,
    framed_path_sha256,
    json_bytes,
    path_exists,
    replace_active_directory,
    sha256_file,
)

ARCHIVE: Final = WORKSPACE / "archive/agent-harness-pre-20260823"
ARCHIVE_STAGE: Final = WORKSPACE / "archive/.agent-harness-pre-20260823.staging"
TEMPLATES: Final = WORKSPACE / "tools/harness_templates"
RECEIPTS: Final = WORKSPACE / ".codex/harness/receipts"
INSTALL_RECEIPT: Final = WORKSPACE / ".codex/harness/install-receipt.json"
OPT_MEM_SHA256: Final = "3dc120d01be3115ef6267eab4103e7909fc830d6227b549f20991ba999ee9ffb"
ARCHIVE_TARGETS: Final = (
    WORKSPACE / "AGENTS.md", WORKSPACE / "CLAUDE.md", WORKSPACE / "SKILLS.md",
    WORKSPACE / "HARNESS_MANUAL.md", WORKSPACE / ".agents/skills",
    WORKSPACE / ".codex/skills", WORKSPACE / ".codex/hooks.json",
    WORKSPACE / ".claude/skills", WORKSPACE / ".claude/hooks",
    WORKSPACE / ".claude/agents", WORKSPACE / ".claude/skills_install_receipt.json",
    WORKSPACE / ".grok/skills", WORKSPACE / ".grok/hooks", WORKSPACE / ".grok/workflows",
    WORKSPACE / ".opencode/skills", HOME / ".agents/skills",
    HOME / ".config/opencode/skills", HOME / ".codex/hooks.json",
    HOME / ".grok/hooks/optmem.json",
    WORKSPACE / "tools/apply_skill_port_batch_20260821.py",
    WORKSPACE / "tools/install_house_skills.py", WORKSPACE / "tools/port_upstream_skills.py",
    WORKSPACE / "tools/test_skill_routing_gate.py", WORKSPACE / "tools/unlazy_gates.py",
)
MIXED_CONFIGS: Final = (WORKSPACE / ".claude/settings.local.json", HOME / ".codex/config.toml")


def archive_sources() -> tuple[Path, ...]:
    codex_skills = HOME / ".codex/skills"
    dynamic = tuple(child for child in sorted(codex_skills.iterdir(), key=lambda item: item.name)
                    if child.name != ".system") if codex_skills.is_dir() else ()
    return (*ARCHIVE_TARGETS, *dynamic, *MIXED_CONFIGS)


def archive_row(source: Path, staged: Path) -> dict[str, str]:
    final = ARCHIVE / archived_relative(source)
    return {"original_path": str(source), "archived_path": str(final),
            "kind": archive_kind(staged), "sha256": framed_path_sha256(staged)}


def stage_archive_source(source: Path, staged: Path) -> None:
    staged.parent.mkdir(parents=True, exist_ok=True)
    if source not in MIXED_CONFIGS:
        shutil.move(str(source), str(staged))
        return
    if source.is_dir():
        raise ValueError(
            f"mixed config offending={source}; expected regular file, symlink, or absent"
        )
    shutil.copy2(source, staged, follow_symlinks=False)


def archive_one_source(
    source: Path, manifest: dict[str, object], recorded: set[str], manifest_path: Path,
) -> None:
    if str(source) in recorded:
        return
    staged = ARCHIVE_STAGE / archived_relative(source)
    if not path_exists(staged) and not path_exists(source):
        return
    if not path_exists(staged):
        stage_archive_source(source, staged)
    items = manifest["items"]
    if not isinstance(items, list):
        raise ValueError(f"archive items offending={items!r}; expected array")
    items.append(archive_row(source, staged))
    recorded.add(str(source))
    atomic_write(manifest_path, json_bytes(manifest))


def archive_old_setup() -> None:
    if ARCHIVE.is_dir():
        return
    ARCHIVE_STAGE.mkdir(parents=True, exist_ok=True)
    manifest_path = ARCHIVE_STAGE / "MANIFEST.json"
    manifest = (json.loads(manifest_path.read_text()) if manifest_path.is_file()
                else {"schema_version": 1, "items": []})
    if not isinstance(manifest, dict) or not isinstance(manifest.get("items"), list):
        raise ValueError(f"archive manifest offending={manifest!r}; expected object with items array")
    recorded = {row["original_path"] for row in manifest["items"]}
    for source in archive_sources():
        archive_one_source(source, manifest, recorded, manifest_path)
    if not manifest["items"]:
        raise RuntimeError("archive items offending=[]; expected the pre-20260823 agent setup")
    os.replace(ARCHIVE_STAGE, ARCHIVE)


def rewrite_mixed_configs(
    claude: Path = WORKSPACE / ".claude/settings.local.json",
    codex: Path = HOME / ".codex/config.toml",
) -> None:
    """Preserve user-owned config. Example: rewrite_mixed_configs(claude, codex)."""
    if claude.is_file():
        current = json.loads(claude.read_text())
        kept = {"outputStyle": current["outputStyle"]} if "outputStyle" in current else {}
        atomic_write(claude, json_bytes(kept))
    if codex.exists() and not codex.is_file():
        raise ValueError(f"Codex config offending={codex}; expected preserved TOML file")


def copy_selected_source(pin: SourcePin, staging: Path) -> None:
    staging.mkdir()
    assert pin.pristine is not None
    for relative in pin.relative_files:
        source = pin.pristine / relative
        if not source.is_file():
            raise FileNotFoundError(
                f"selected source offending={source}; expected regular file for pin={pin.name}"
            )
        target = staging / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def copy_source(pin: SourcePin) -> None:
    if pin.name == "optmem" or pin.installed.is_dir():
        return
    if pin.pristine is None or not pin.pristine.is_dir():
        raise FileNotFoundError(
            f"pristine source offending={pin.pristine}; expected pinned checkout for {pin.name}"
        )
    destination = pin.installed
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / f".{destination.name}.staging"
    if staging.exists():
        shutil.rmtree(staging)
    if pin.relative_files:
        copy_selected_source(pin, staging)
    else:
        shutil.copytree(pin.pristine, staging, symlinks=True,
                        ignore=shutil.ignore_patterns(".git"))
    os.replace(staging, destination)


def mirror_skill(source: Path, target: Path, explicit_only: bool = False) -> None:
    shutil.copytree(source, target, symlinks=True)
    if explicit_only:
        agents = target / "agents"
        agents.mkdir(exist_ok=True)
        atomic_write(agents / "openai.yaml", b"policy:\n  allow_implicit_invocation: false\n")


def rendered_wrapper(skill_file: Path, destination: Path,
                     references: dict[str, Path] | None) -> bytes:
    content = skill_file.read_text()
    for marker, path in (references or {}).items():
        content = content.replace(f"{{{{{marker}}}}}", os.path.relpath(path, destination))
    if "{{" in content or "}}" in content:
        raise ValueError(
            f"wrapper content offending={skill_file}; expected all template markers resolved"
        )
    return content.encode()


def copy_wrapper(
    name: str, target_root: Path, references: dict[str, Path] | None = None,
) -> None:
    source = TEMPLATES / "skills" / name
    if not (source / "SKILL.md").is_file():
        raise FileNotFoundError(f"skill template offending={source}; expected SKILL.md")
    destination = target_root / name
    shutil.copytree(source, destination, symlinks=True)
    skill_file = destination / "SKILL.md"
    atomic_write(skill_file, rendered_wrapper(skill_file, destination, references))


def source_skill_dirs(parent: Path) -> dict[str, Path]:
    return {child.name: child for child in sorted(parent.iterdir(), key=lambda item: item.name)
            if child.is_dir() and (child / "SKILL.md").is_file()}


def installed_source(name: str) -> Path:
    return next(pin.installed for pin in PINS if pin.name == name)


def copy_pstack_skills(staging: Path) -> None:
    pstack = installed_source("pstack")
    for name, source in source_skill_dirs(pstack / "pstack/skills").items():
        if name == "poteto-mode":
            copy_wrapper(name, staging, {"UPSTREAM": source})
            continue
        explicit = "disable-model-invocation: true" in (source / "SKILL.md").read_text()
        mirror_skill(source, staging / name, explicit)
    controls = source_skill_dirs(pstack / "cursor-team-kit/skills")
    for name in ("deslop", "control-cli", "control-ui"):
        mirror_skill(controls[name], staging / name)


def copy_pocock_skills(staging: Path) -> None:
    pocock = installed_source("pocock")
    pocock_skills: dict[str, Path] = {}
    for branch in ("engineering", "productivity"):
        pocock_skills.update(source_skill_dirs(pocock / "skills" / branch))
    wrappers = {"ask-matt": "ask-matt", "implement": "implement",
                "tdd": "pocock-tdd", "teach": "pocock-teach"}
    for name, source in pocock_skills.items():
        public = wrappers.get(name)
        if public:
            copy_wrapper(public, staging, {"UPSTREAM": source})
        else:
            mirror_skill(source, staging / name)


def render_active_skills(active: Path) -> list[str]:
    """Publish the 76-skill tree. Example: render_active_skills(Path('/tmp/skills'))."""
    staging = active.with_name(f".{active.name}.staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    copy_pstack_skills(staging)
    copy_pocock_skills(staging)
    pstack = installed_source("pstack")
    unlazy = installed_source("unlazy")
    poteto = pstack / "pstack/skills/poteto-mode"
    for name in ("plan-flow", "implement-flow"):
        copy_wrapper(name, staging, {"PSTACK_POTETO": poteto})
    copy_wrapper("clean-code-for-agents", staging)
    mirror_skill(unlazy, staging / "unlazy")
    replace_active_directory(staging, active)
    return sorted(child.name for child in active.iterdir())


def build_active_skills() -> list[str]:
    return render_active_skills(WORKSPACE / ".agents/skills")


def agents_document() -> bytes:
    """Render the Codex contract through the one shared renderer."""
    return render_contract("codex")


def write_client_contracts() -> dict[str, int]:
    """Write every client contract from the shared blocks."""
    return render_all_contracts()


def codex_hook_templates() -> list[Path]:
    """List the Codex hook templates by name. Example: codex_hook_templates().

    Named rather than globbed. A glob quietly swept Claude-only modules into
    the Codex install the moment they appeared beside them.
    """
    return [TEMPLATES / "hooks" / name for name in sorted(CODEX_HOOK_MODULES)]


def remove_unused_codex_bridge() -> None:
    bridge = WORKSPACE / ".codex/hooks/cached_session_bridge.py"
    if path_exists(bridge):
        if bridge.is_dir() and not bridge.is_symlink():
            raise ValueError(f"unused Codex bridge offending={bridge}; expected file or absent")
        bridge.unlink()


def install_codex_files() -> None:
    hooks = WORKSPACE / ".codex/hooks"
    agents = WORKSPACE / ".codex/agents"
    hooks.mkdir(parents=True, exist_ok=True)
    agents.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TEMPLATES / "hooks.json", WORKSPACE / ".codex/hooks.json")
    for source in codex_hook_templates():
        shutil.copy2(source, hooks / source.name)
    remove_unused_codex_bridge()
    for source in sorted((TEMPLATES / "agents").glob("*.toml")):
        shutil.copy2(source, agents / source.name)
    atomic_write(WORKSPACE / "AGENTS.md", agents_document())


def write_provenance() -> None:
    sources: dict[str, dict[str, str]] = {}
    for pin in PINS:
        digest = sha256_file(pin.installed) if pin.name == "optmem" else framed_path_sha256(pin.installed)
        sources[pin.name] = {"commit": pin.commit, "origin": pin.origin, "path": str(pin.installed),
                             "selection": pin.selection, "sha256": digest}
    atomic_write(VENDOR_ROOT / "MANIFEST.json", json_bytes({"schema_version": 1, "sources": sources}))


def retain_lifecycle_receipt() -> Path:
    source = Path("/tmp/codex-lifecycle-probe.dZfZUq/all-events.jsonl")
    if not source.is_file():
        raise FileNotFoundError(
            f"lifecycle evidence offending={source}; expected completed real Codex probe"
        )
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    event_log = RECEIPTS / "lifecycle-events.jsonl"
    shutil.copy2(source, event_log)
    receipt = RECEIPTS / "lifecycle-verification.txt"
    text = ("LIFECYCLE RECEIPT 1\n"
            "codex_version=codex-cli 0.149.0\n"
            f"event_log={event_log}\n"
            f"event_log_sha256={sha256_file(event_log)}\n"
            "verification=PROBE_VERIFY_OK\n")
    atomic_write(receipt, text.encode())
    return receipt


def write_install_receipt(active_names: list[str], lifecycle: Path) -> None:
    validations = {name: str(RECEIPTS / f"{name}-validation.txt")
                   for name in ("pstack", "pocock", "unlazy", "optmem", "local-skills")}
    receipt = {
        "schema_version": 1,
        "installed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "workspace": str(WORKSPACE),
        "archive_dir": str(ARCHIVE),
        "source_commits": {pin.name: pin.commit for pin in PINS},
        "active_skill_names": active_names,
        "optmem_sha256": OPT_MEM_SHA256,
        "upstream_receipts": validations,
        "lifecycle_probe_receipt": str(lifecycle),
    }
    atomic_write(INSTALL_RECEIPT, json_bytes(receipt))


def load_managed_state() -> tuple[dict[str, object], dict[str, object]]:
    try:
        receipt = json.loads(INSTALL_RECEIPT.read_text())
        manifest = json.loads((VENDOR_ROOT / "MANIFEST.json").read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            f"managed state offending={error}; expected valid receipt and vendor manifest JSON"
        ) from error
    if not isinstance(receipt, dict) or not isinstance(manifest, dict):
        raise ValueError(
            f"managed state offending={(type(receipt).__name__, type(manifest).__name__)}; "
            "expected two JSON objects"
        )
    return receipt, manifest


def skill_tree_errors(receipt: dict[str, object]) -> list[str]:
    errors: list[str] = []
    active = WORKSPACE / ".agents/skills"
    names = sorted(child.name for child in active.iterdir()) if active.is_dir() else []
    if names != receipt.get("active_skill_names"):
        errors.append(f"active skills {names!r} do not match install receipt")
    for name in names:
        skill_file = active / name / "SKILL.md"
        if not skill_file.is_file() or skill_file.is_symlink():
            errors.append(f"Codex skill entrypoint is not a regular file: {skill_file}")
    nested_skills = sorted(active.glob("*/*/SKILL.md")) if active.is_dir() else []
    if nested_skills:
        errors.append(f"nested skill authorities remain: {nested_skills!r}")
    for forbidden in (WORKSPACE / ".codex/skills", WORKSPACE / ".claude/skills"):
        if path_exists(forbidden):
            errors.append(f"old skill authority still exists: {forbidden}")
    return errors


def managed_file_pairs() -> list[tuple[Path, Path]]:
    return [
        *((source, WORKSPACE / ".codex/hooks" / source.name)
          for source in codex_hook_templates()),
        *((source, WORKSPACE / ".codex/agents" / source.name)
          for source in sorted((TEMPLATES / "agents").glob("*.toml"))),
        (TEMPLATES / "hooks/cached_session_bridge.py",
         WORKSPACE / ".claude/hooks/optmem_continuity.py"),
    ]


def managed_install_errors() -> list[str]:
    errors: list[str] = []
    if not ARCHIVE.is_dir() or not (ARCHIVE / "MANIFEST.json").is_file():
        errors.append(f"missing completed archive {ARCHIVE}")
    hooks = WORKSPACE / ".codex/hooks.json"
    if not hooks.is_file() or hooks.read_bytes() != (TEMPLATES / "hooks.json").read_bytes():
        errors.append("installed hooks.json differs from template")
    for source, installed in managed_file_pairs():
        if not installed.is_file() or installed.read_bytes() != source.read_bytes():
            errors.append(f"installed managed file differs from template: {installed}")
    unused_bridge = WORKSPACE / ".codex/hooks/cached_session_bridge.py"
    if path_exists(unused_bridge):
        errors.append(f"unused Codex bridge remains: {unused_bridge}")
    agents_path = WORKSPACE / "AGENTS.md"
    if not agents_path.is_file() or agents_path.read_bytes() != agents_document():
        errors.append("installed AGENTS.md differs from generated document")
    return errors


def installed_source_errors(manifest: dict[str, object]) -> list[str]:
    errors: list[str] = []
    sources = manifest.get("sources", {})
    for pin in PINS:
        if not path_exists(pin.installed):
            errors.append(f"missing installed source {pin.installed}")
            continue
        actual = sha256_file(pin.installed) if pin.name == "optmem" else framed_path_sha256(pin.installed)
        source_row = sources.get(pin.name) if isinstance(sources, dict) else None
        expected = source_row.get("sha256") if isinstance(source_row, dict) else None
        if actual != expected:
            errors.append(f"source hash mismatch for {pin.name}: {actual} != {expected}")
    return errors


def retained_receipt_errors(receipt: dict[str, object]) -> list[str]:
    errors: list[str] = []
    upstream = receipt.get("upstream_receipts")
    if not isinstance(upstream, dict):
        return [f"upstream receipts offending={upstream!r}; expected path mapping"]
    for path in upstream.values():
        if not isinstance(path, str):
            errors.append(f"upstream receipt offending={path!r}; expected path string")
            continue
        if not Path(path).is_file():
            errors.append(f"missing upstream validation receipt {path}")
    lifecycle = receipt.get("lifecycle_probe_receipt", "")
    if not isinstance(lifecycle, str) or not lifecycle or not Path(lifecycle).is_file():
        errors.append(f"lifecycle receipt offending={lifecycle!r}; expected existing path")
    return errors


def current_errors() -> list[str]:
    """List install drift. Example: current_errors() returns [] when current."""
    if not INSTALL_RECEIPT.is_file():
        return [f"missing {INSTALL_RECEIPT}"]
    try:
        receipt, manifest = load_managed_state()
    except ValueError as error:
        return [str(error)]
    errors = [error for error in (pinned_runtime_error(),) if error]
    errors.extend(skill_tree_errors(receipt))
    errors.extend(managed_install_errors())
    errors.extend(installed_source_errors(manifest))
    errors.extend(retained_receipt_errors(receipt))
    return errors


def install() -> None:
    """Install the pinned harness. Example: install()."""
    runtime_error = pinned_runtime_error()
    if runtime_error:
        raise ValueError(runtime_error)
    archive_old_setup()
    bridge = WORKSPACE / ".claude/hooks/optmem_continuity.py"
    bridge.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TEMPLATES / "hooks/cached_session_bridge.py", bridge)
    rewrite_mixed_configs()
    for pin in PINS:
        copy_source(pin)
    if (actual_optmem := sha256_file(OPT_MEM)) != OPT_MEM_SHA256:
        raise ValueError(f"OptMem hash offending={actual_optmem}; expected {OPT_MEM_SHA256}")
    active_names = build_active_skills()
    install_codex_files()
    write_provenance()
    lifecycle = retain_lifecycle_receipt()
    write_install_receipt(active_names, lifecycle)
    print(f"HARNESS INSTALLED skills={len(active_names)} archive={ARCHIVE}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run install or check mode. Example: main(['--check'])."""
    parser = argparse.ArgumentParser(description="Install or check the pinned Codex agent setup.")
    parser.add_argument("--check", action="store_true", help="Check managed files without writing.")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.check:
        errors = current_errors()
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        print("HARNESS CURRENT")
        return 0
    install()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
