
from __future__ import annotations

import ast
import json
import os
import re
import shlex
import subprocess
import tomllib
from pathlib import Path
from typing import cast

from agent_harness_verify_common import (
    AKITA_BLOCK_SHA256,
    AKITA_MARKERS,
    HARNESS_DIR,
    NO_MEMO_LINE,
    OPT_MEM,
    OPT_MEM_SHA256,
    OPTMEM_BLOCK_SHA256,
    OPTMEM_MARKERS,
    PINNED_COMMITS,
    PINNED_VENDOR_HASHES,
    ROOT,
    SOURCE_PATHS,
    SOURCE_SELECTIONS,
    UNSLOP_LAW,
    UPSTREAM_NAMES,
    VENDOR_MANIFEST,
    archive_kind,
    framed_path_sha256,
    load_install_receipt,
    load_json_object,
    refuse,
    require,
    sha256_bytes,
    sha256_file,
)


UPSTREAM_RECEIPT_FIELDS = {
    "source", "commit", "status", "commands_json", "exit_codes_json", "output_sha256",
}


def archive_item_paths(
    item: dict[str, object], index: int, archive_dir: Path,
) -> tuple[Path, Path]:
    item_keys = {"original_path", "archived_path", "kind", "sha256"}
    require(set(item) == item_keys, f"archive.items[{index}]", item,
            str(sorted(item_keys)))
    original = Path(cast(str, item["original_path"]))
    archived = Path(cast(str, item["archived_path"]))
    require(original.is_absolute(), f"archive.items[{index}].original_path",
            str(original), "absolute path")
    require(archived.is_absolute(), f"archive.items[{index}].archived_path",
            str(archived), "absolute path")
    try:
        archived.relative_to(archive_dir)
    except ValueError:
        refuse(f"archive.items[{index}].archived_path", str(archived),
               f"path below {archive_dir}")
    return original, archived


def validate_archive_item(
    item: dict[str, object], index: int, archive_dir: Path,
    originals: set[str], archived_paths: set[str],
) -> None:
    original, archived = archive_item_paths(item, index, archive_dir)
    require(os.path.lexists(archived), f"archive.items[{index}].archived_path",
            str(archived), "existing archived entry")
    require(str(original) not in originals, f"archive.items[{index}].original_path",
            str(original), "unique path")
    require(str(archived) not in archived_paths, f"archive.items[{index}].archived_path",
            str(archived), "unique path")
    require(item["kind"] == archive_kind(archived), f"archive.items[{index}].kind",
            item["kind"], archive_kind(archived))
    actual = framed_path_sha256(archived)
    require(item["sha256"] == actual, f"archive.items[{index}].sha256",
            item["sha256"], actual)
    originals.add(str(original))
    archived_paths.add(str(archived))


def verify_archive() -> str:
    """Check the recovery archive. Example: verify_archive()."""
    archive_dir = Path(cast(str, load_install_receipt()["archive_dir"]))
    require(archive_dir.is_absolute() and archive_dir.is_dir(), "archive.dir",
            str(archive_dir), "existing absolute directory")
    manifest = load_json_object(archive_dir / "MANIFEST.json", "archive.manifest")
    require(set(manifest) == {"schema_version", "items"},
            "archive.manifest.keys", sorted(manifest), "['items', 'schema_version']")
    require(manifest["schema_version"] == 1, "archive.manifest.schema_version",
            manifest["schema_version"], "1")
    items = manifest["items"]
    require(isinstance(items, list) and bool(items), "archive.manifest.items",
            items, "non-empty list")
    originals: set[str] = set()
    archived_paths: set[str] = set()
    for index, item in enumerate(cast(list[object], items)):
        require(isinstance(item, dict), f"archive.items[{index}]", item, "object")
        validate_archive_item(cast(dict[str, object], item), index, archive_dir,
                              originals, archived_paths)
    return f"items={len(cast(list[object], items))} archive_dir={archive_dir}"


def frontmatter_name(skill_file: Path) -> str:
    lines = skill_file.read_text(encoding="utf-8").splitlines()
    require(lines and lines[0] == "---", "skill.frontmatter", str(skill_file),
            "frontmatter opening line '---'")
    try:
        end = lines.index("---", 1)
    except ValueError:
        refuse("skill.frontmatter", str(skill_file), "closing frontmatter line '---'")
    matches = [line.split(":", 1)[1].strip() for line in lines[1:end]
               if line.startswith("name:")]
    valid = len(matches) == 1 and re.fullmatch(r"[a-z0-9][a-z0-9-]*", matches[0])
    require(valid is not None and bool(valid), "skill.frontmatter.name", matches,
            "one lowercase kebab-case name")
    return matches[0]


def skill_dirs(parent: Path) -> set[str]:
    require(parent.is_dir(), "skills.source", str(parent), "existing skill directory")
    return {item.name for item in parent.iterdir()
            if item.is_dir() and (item / "SKILL.md").is_file()}


def expected_skill_names() -> list[str]:
    """Derive the 76-skill inventory. Example: expected_skill_names()."""
    pstack = SOURCE_PATHS["pstack"]
    expected = skill_dirs(pstack / "pstack/skills")
    controls = skill_dirs(pstack / "cursor-team-kit/skills")
    require({"deslop", "control-cli", "control-ui"} <= controls,
            "skills.cursor-team-kit", sorted(controls),
            "deslop, control-cli, and control-ui")
    expected.update({"deslop", "control-cli", "control-ui"})
    pocock = SOURCE_PATHS["pocock"] / "skills"
    pocock_names = skill_dirs(pocock / "engineering") | skill_dirs(pocock / "productivity")
    renames = {"tdd": "pocock-tdd", "teach": "pocock-teach"}
    expected.update(renames.get(name, name) for name in pocock_names)
    expected.update({"plan-flow", "implement-flow", "clean-code-for-agents", "unlazy"})
    return sorted(expected)


def validate_public_skill(entry: Path, public_names: dict[str, str]) -> None:
    skill_file = entry / "SKILL.md"
    require(entry.is_dir() and skill_file.is_file(), "skills.entry",
            str(entry), "directory containing SKILL.md")
    require(not skill_file.is_symlink(), "skills.entrypoint-kind",
            str(skill_file), "regular SKILL.md file accepted by Codex")
    resolved = skill_file.resolve(strict=True)
    require(resolved.is_relative_to(ROOT), "skills.target", str(resolved),
            "resolved path below /workspace")
    require(not resolved.is_relative_to(ROOT / "archive"), "skills.target",
            str(resolved), "target outside /workspace/archive")
    name = frontmatter_name(skill_file)
    require(name == entry.name, "skills.directory-name", entry.name, name)
    require(name not in public_names, "skills.duplicate-frontmatter-name",
            {name: [public_names.get(name), str(skill_file)]}, "one active owner")
    public_names[name] = str(skill_file)


def user_duplicate_skills(public_names: dict[str, str]) -> list[str]:
    authorities = (Path("/home/algo/.agents/skills"),
                   Path("/home/algo/.codex/skills"),
                   Path("/home/algo/.config/opencode/skills"))
    return [str(entry) for base in authorities if base.is_dir()
            for entry in base.iterdir()
            if entry.is_symlink() and entry.name in public_names]


def validate_skill_authorities(authority: Path) -> None:
    require(authority.is_dir(), "skills.authority", str(authority),
            "existing /workspace/.agents/skills")
    for forbidden in (ROOT / ".codex/skills", ROOT / ".claude/skills"):
        require(not os.path.lexists(forbidden), "skills.forbidden-authority",
                str(forbidden), "absent path")


def validate_inventory_names(actual_names: list[str], receipt: dict[str, object]) -> None:
    receipt_names = receipt["active_skill_names"]
    require(actual_names == receipt_names, "skills.receipt-names",
            actual_names, str(receipt_names))
    expected_names = expected_skill_names()
    require(actual_names == expected_names, "skills.expected-names",
            actual_names, str(expected_names))


def verify_skills() -> str:
    """Check active skill authority. Example: verify_skills()."""
    receipt = load_install_receipt()
    authority = ROOT / ".agents/skills"
    validate_skill_authorities(authority)
    entries = sorted(authority.iterdir(), key=lambda path: path.name)
    actual_names = [entry.name for entry in entries]
    validate_inventory_names(actual_names, receipt)
    public_names: dict[str, str] = {}
    for entry in entries:
        validate_public_skill(entry, public_names)
    duplicates = user_duplicate_skills(public_names)
    require(not duplicates, "skills.user-duplicates", duplicates,
            "no user-level duplicate skill symlinks")
    return f"active={len(actual_names)} unique_frontmatter={len(public_names)}"


def marker_interior(raw: bytes, markers: tuple[str, str], name: str) -> bytes:
    begin, end = (marker.encode() for marker in markers)
    require(raw.count(begin) == 1 and raw.count(end) == 1, name,
            {"begin": raw.count(begin), "end": raw.count(end)},
            "each marker exactly once")
    opening = begin + b"\n"
    start = raw.find(opening)
    stop = raw.find(end, start + len(opening))
    require(start >= 0 and stop >= 0, name, markers, "markers on their own lines in order")
    return raw[start + len(opening):stop]


def read_agents_document() -> bytes:
    path = ROOT / "AGENTS.md"
    require(path.is_file(), "agents.path", str(path), "existing AGENTS.md")
    return path.read_bytes()


def verify_agents() -> str:
    """Check AGENTS.md wiring. Example: verify_agents()."""
    load_install_receipt()
    raw = read_agents_document()
    require(len(raw) < 32 * 1024, "agents.bytes", len(raw), "less than 32768")
    optmem = marker_interior(raw, OPTMEM_MARKERS, "agents.optmem-markers")
    akita = marker_interior(raw, AKITA_MARKERS, "agents.akita-markers")
    require(sha256_bytes(optmem) == OPTMEM_BLOCK_SHA256, "agents.optmem-block",
            sha256_bytes(optmem), OPTMEM_BLOCK_SHA256)
    require(sha256_bytes(akita) == AKITA_BLOCK_SHA256, "agents.akita-block",
            sha256_bytes(akita), AKITA_BLOCK_SHA256)
    article = SOURCE_PATHS["akita"] / "content/2026/04/20/clean-code-para-agentes-de-ia/index.en.md"
    require(article.is_file(), "agents.akita-source", str(article), "vendored Akita article")
    source_block = b"".join(article.read_bytes().splitlines(keepends=True)[174:224])
    require(akita == source_block, "agents.akita-source-block",
            sha256_bytes(akita), sha256_bytes(source_block))
    require(raw.count(UNSLOP_LAW.encode()) == 1, "agents.unslop-law",
            raw.count(UNSLOP_LAW.encode()), "exact mandated sentence once")
    return f"bytes={len(raw)} optmem_sha256={OPTMEM_BLOCK_SHA256} akita_sha256={AKITA_BLOCK_SHA256}"


def event_commands(event: str, groups: object) -> list[str]:
    require(isinstance(groups, list), f"hooks.{event}", groups, "list")
    commands: list[str] = []
    for index, group in enumerate(cast(list[object], groups)):
        handlers = group.get("hooks") if isinstance(group, dict) else None
        require(isinstance(handlers, list), f"hooks.{event}[{index}]", group,
                "object containing hooks list")
        for handler in cast(list[object], handlers):
            valid = (isinstance(handler, dict) and handler.get("type") == "command"
                     and isinstance(handler.get("command"), str))
            require(valid, f"hooks.{event}.handler", handler,
                    "command handler with string command")
            commands.append(cast(str, cast(dict[str, object], handler)["command"]))
    return commands


def hook_commands(config: dict[str, object]) -> dict[str, list[str]]:
    require(set(config) == {"hooks"} and isinstance(config["hooks"], dict),
            "hooks.schema", sorted(config), "top-level hooks object")
    hooks = cast(dict[str, object], config["hooks"])
    required_events = {"SessionStart", "PreCompact", "PostCompact", "Stop"}
    require(required_events <= set(hooks), "hooks.events", sorted(hooks),
            f"events including {sorted(required_events)}")
    require("UserPromptSubmit" not in hooks, "hooks.semantic-router",
            "UserPromptSubmit", "absent event")
    commands = {event: event_commands(event, groups) for event, groups in hooks.items()}
    for event in required_events:
        require(commands[event], f"hooks.{event}.handlers", 0, "at least one handler")
    require(len(commands["Stop"]) == 1, "hooks.Stop.handlers",
            len(commands["Stop"]), "exactly one")
    return commands


def command_scripts(command: str) -> dict[Path, str]:
    try:
        parts = shlex.split(command)
    except ValueError as error:
        refuse("hooks.command", f"{command}: {error}", "shell-parseable command")
    executable = parts[0] if parts else ""
    require(parts and Path(executable).is_absolute() and os.access(executable, os.X_OK),
            "hooks.executable", executable if parts else parts,
            "existing executable absolute path")
    scripts: dict[Path, str] = {}
    for token in parts[1:]:
        candidate = Path(token)
        if candidate.is_absolute() and candidate.suffix in {".py", ".js", ".mjs"}:
            require(candidate.is_file(), "hooks.script", str(candidate), "existing script")
            scripts[candidate] = executable
    return scripts


def verify_script_syntax(script: Path, executable: str) -> None:
    if script.suffix == ".py":
        try:
            ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
        except (OSError, UnicodeError, SyntaxError) as error:
            refuse("hooks.script-parse", f"{script}: {error}", "valid Python")
        return
    result = subprocess.run([executable, "--check", str(script)],
                            capture_output=True, timeout=20, check=False)
    require(result.returncode == 0, "hooks.script-parse",
            f"{script}: {result.stderr.decode(errors='replace')}",
            "node --check exit 0")


def verify_hooks() -> str:
    """Check hook definitions and scripts. Example: verify_hooks()."""
    commands = hook_commands(load_json_object(ROOT / ".codex/hooks.json", "hooks.json"))
    flattened = [command for values in commands.values() for command in values]
    require(not any(".claude" in command for command in flattened),
            "hooks.claude-command", flattened, "no active .claude command")
    require(not any("user-prompt" in command.lower() for command in flattened),
            "hooks.semantic-router", flattened, "no semantic prompt router command")
    scripts: dict[Path, str] = {}
    for command in flattened:
        scripts.update(command_scripts(command))
    for script, executable in scripts.items():
        verify_script_syntax(script, executable)
    return f"handlers={sum(map(len, commands.values()))} scripts={len(scripts)}"


def load_agent_config(path: Path) -> dict[str, object]:
    try:
        value = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        refuse("agents-toml.parse", f"{path}: {error}", "valid TOML")
    return cast(dict[str, object], value)


def validate_agent_config(path: Path, value: dict[str, object], names: set[str]) -> None:
    for field in ("name", "description", "developer_instructions"):
        field_value = value.get(field)
        require(isinstance(field_value, str) and bool(field_value.strip()),
                f"agents-toml.{path.name}.{field}", field_value, "non-empty string")
    name = cast(str, value["name"])
    require(name == path.stem, f"agents-toml.{path.name}.name", name, path.stem)
    require(name not in names, "agents-toml.duplicate-name", name, "unique name")
    configured = sorted({"model", "model_reasoning_effort", "sandbox_mode", "approval_policy"} & value.keys())
    require(not configured, f"agents-toml.{path.name}.inheritance", configured,
            "model, reasoning, sandbox, and approvals inherited from parent")
    instructions = cast(str, value["developer_instructions"])
    count = instructions.splitlines().count(NO_MEMO_LINE)
    require(count == 1, f"agents-toml.{path.name}.no-memo", count,
            f"exact line once: {NO_MEMO_LINE}")
    missing = [match for match in re.findall(r"`(/workspace/[^`]+)`", instructions)
               if not Path(match).is_file()]
    require(not missing, f"agents-toml.{path.name}.references", missing,
            "every absolute backticked source path exists")
    names.add(name)


def verify_agents_toml() -> str:
    """Check Codex agent definitions. Example: verify_agents_toml()."""
    directory = ROOT / ".codex/agents"
    require(directory.is_dir(), "agents-toml.directory", str(directory), "existing directory")
    files = sorted(directory.glob("*.toml"))
    require(bool(files), "agents-toml.files", 0, "at least one TOML file")
    names: set[str] = set()
    for path in files:
        validate_agent_config(path, load_agent_config(path), names)
    require(names == {"poteto-agent", "comment-sicko"}, "agents-toml.names", sorted(names),
            "['comment-sicko', 'poteto-agent']")
    return f"files={len(files)} names={','.join(sorted(names))}"


def validate_provenance_source(
    name: str, commit: str, row: dict[str, object], row_keys: set[str],
) -> None:
    require(set(row) == row_keys, f"provenance.{name}.keys", row,
            str(sorted(row_keys)))
    require(row["commit"] == commit, f"provenance.{name}.commit", row["commit"], commit)
    require(row["path"] == str(SOURCE_PATHS[name]), f"provenance.{name}.path",
            row["path"], str(SOURCE_PATHS[name]))
    require(row["selection"] == SOURCE_SELECTIONS[name],
            f"provenance.{name}.selection", row["selection"], SOURCE_SELECTIONS[name])
    origin = row["origin"]
    require(isinstance(origin, str) and origin.startswith("https://"),
            f"provenance.{name}.origin", origin, "HTTPS source URL")
    actual = (sha256_file(SOURCE_PATHS[name]) if name == "optmem"
              else framed_path_sha256(SOURCE_PATHS[name]))
    require(actual == PINNED_VENDOR_HASHES[name], f"provenance.{name}.bytes",
            actual, PINNED_VENDOR_HASHES[name])
    require(row["sha256"] == actual, f"provenance.{name}.manifest-sha256",
            row["sha256"], actual)


def provenance_rows() -> dict[str, object]:
    manifest = load_json_object(VENDOR_MANIFEST, "provenance.manifest")
    require(set(manifest) == {"schema_version", "sources"},
            "provenance.manifest.keys", sorted(manifest), "['schema_version', 'sources']")
    require(manifest["schema_version"] == 1, "provenance.manifest.schema_version",
            manifest["schema_version"], "1")
    sources = manifest["sources"]
    require(isinstance(sources, dict) and set(sources) == set(PINNED_COMMITS),
            "provenance.sources", sorted(sources) if isinstance(sources, dict) else sources,
            str(sorted(PINNED_COMMITS)))
    return cast(dict[str, object], sources)


def verify_provenance() -> str:
    """Check pinned-source provenance. Example: verify_provenance()."""
    receipt = load_install_receipt()
    require(set(PINNED_VENDOR_HASHES) == set(PINNED_COMMITS),
            "provenance.pinned-hashes", sorted(PINNED_VENDOR_HASHES),
            str(sorted(PINNED_COMMITS)))
    rows = provenance_rows()
    row_keys = {"commit", "origin", "path", "selection", "sha256"}
    for name, commit in PINNED_COMMITS.items():
        require(isinstance(rows[name], dict), f"provenance.{name}", rows[name], "object")
        validate_provenance_source(name, commit,
                                   cast(dict[str, object], rows[name]), row_keys)
    actual_optmem = sha256_file(OPT_MEM)
    require(receipt["optmem_sha256"] == actual_optmem,
            "provenance.optmem-receipt", receipt["optmem_sha256"], actual_optmem)
    return f"sources={len(rows)} optmem_sha256={OPT_MEM_SHA256}"


def upstream_receipt_fields(path: Path, source: str) -> tuple[dict[str, str], bytes]:
    header, separator, output = path.read_bytes().partition(b"--- output ---\n")
    require(bool(separator), f"upstream.{source}.separator", False,
            "line '--- output ---'")
    try:
        lines = header.decode("utf-8").splitlines()
    except UnicodeError as error:
        refuse(f"upstream.{source}.header", str(error), "UTF-8 header")
    require(len(lines) == 7 and lines[0] == "UPSTREAM VALIDATION RECEIPT 1",
            f"upstream.{source}.envelope", lines,
            "exact seven-line upstream receipt header")
    return dict(line.split("=", 1) for line in lines[1:] if "=" in line), output


def validate_upstream_commands(fields: dict[str, str], source: str) -> None:
    try:
        commands = json.loads(fields["commands_json"])
        exit_codes = json.loads(fields["exit_codes_json"])
    except json.JSONDecodeError as error:
        refuse(f"upstream.{source}.commands", str(error),
               "JSON string and integer arrays")
    valid_commands = (isinstance(commands, list) and bool(commands)
                      and all(isinstance(item, str) and item for item in commands))
    require(valid_commands, f"upstream.{source}.commands", commands,
            "non-empty string array")
    valid_codes = (isinstance(exit_codes, list) and len(exit_codes) == len(commands)
                   and all(type(item) is int and item == 0 for item in exit_codes))
    require(valid_codes, f"upstream.{source}.exit-codes", exit_codes,
            f"{len(commands)} zero integers")


def parse_upstream_receipt(path: Path, expected_source: str) -> None:
    require(path.is_file(), f"upstream.{expected_source}.path", str(path),
            "existing receipt")
    fields, output = upstream_receipt_fields(path, expected_source)
    require(set(fields) == UPSTREAM_RECEIPT_FIELDS, f"upstream.{expected_source}.fields",
            fields, str(sorted(UPSTREAM_RECEIPT_FIELDS)))
    expected_commit = ("local" if expected_source == "local-skills"
                       else PINNED_COMMITS[expected_source])
    require(fields["source"] == expected_source, f"upstream.{expected_source}.source",
            fields["source"], expected_source)
    require(fields["commit"] == expected_commit, f"upstream.{expected_source}.commit",
            fields["commit"], expected_commit)
    require(fields["status"] == "PASS", f"upstream.{expected_source}.status",
            fields["status"], "PASS")
    validate_upstream_commands(fields, expected_source)
    require(fields["output_sha256"] == sha256_bytes(output),
            f"upstream.{expected_source}.output-sha256",
            fields["output_sha256"], sha256_bytes(output))


def verify_upstream_receipts() -> str:
    """Check retained upstream evidence. Example: verify_upstream_receipts()."""
    paths = load_install_receipt()["upstream_receipts"]
    receipt_paths = cast(dict[str, str], paths)
    for source in sorted(UPSTREAM_NAMES):
        parse_upstream_receipt(Path(receipt_paths[source]), source)
    return (f"receipts={len(receipt_paths)} status=PASS "
            "proof=retained-receipts-only upstream_suites=not-rerun")
