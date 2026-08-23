
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import shutil
import stat
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn, cast


ROOT = Path("/workspace")
HARNESS_DIR = ROOT / ".codex/harness"
RECEIPT_PATH = HARNESS_DIR / "install-receipt.json"
VENDOR_MANIFEST = ROOT / "vendor/agent-sources/MANIFEST.json"
OPT_MEM = Path("/home/algo/.optmem/memo")
OPT_MEM_SHA256 = "3dc120d01be3115ef6267eab4103e7909fc830d6227b549f20991ba999ee9ffb"
PINNED_COMMITS = {
    "pstack": "46125561306434d8a1d7745d540d8932ab0cd2a2",
    "pocock": "5b15a47f2d7150f545fbcacbfe381787fc0230dc",
    "unlazy": "754d9a68109e39b836cc72a39fb9a823f9d6b613",
    "akita": "bbd8e681c14c0f57b2e5ea63e4d1c0043a6890da",
    "karpathy": "2c606141936f1eeef17fa3043a72095b4765b9c2",
    "bigpowers": "c0209032fb978d730a416167cd8f1e91e411650b",
    "optmem": "1fb164cf39028047781f72ac3bb1e5a691c1dcb0",
}
SOURCE_PATHS = {
    name: ROOT / f"vendor/agent-sources/{name}/{commit}"
    for name, commit in PINNED_COMMITS.items()
    if name != "optmem"
}
SOURCE_PATHS["optmem"] = OPT_MEM
SOURCE_SELECTIONS = {
    "pstack": "full",
    "pocock": "full",
    "unlazy": "full",
    "akita": "akita-article-and-license",
    "karpathy": "full",
    "bigpowers": "ousterhout-subset",
    "optmem": "installed-binary",
}
PINNED_VENDOR_HASHES = {
    "pstack": "dfe34e3d1e57ed3f0b4b67a7e88e3f3bab8f73780a4753349099acb1d3923490",
    "pocock": "75a8fcb3fbdbf333676485bf016dfa64a1c0d14708a1fdac01e3710d04995b1a",
    "unlazy": "8cf9591a58b46723a0f7e96ef6b2afefd6b0ed8a83b698b2cee57fe11778aaeb",
    "akita": "9db39591b9a8d157e327081b6921be5f9c16295bb806d364939ab07e62bc5c90",
    "karpathy": "a032acabec41d7666693c2c11de0a4833fa46ab5ab80f89533c95c1bd5270563",
    "bigpowers": "86090c4d86d85f69fddd1a1ce9033f034bd2776c443ea3a60bf70983c6550406",
    "optmem": "3dc120d01be3115ef6267eab4103e7909fc830d6227b549f20991ba999ee9ffb",
}
RECEIPT_KEYS = {
    "schema_version", "installed_at", "workspace", "archive_dir",
    "source_commits", "active_skill_names", "optmem_sha256",
    "upstream_receipts", "lifecycle_probe_receipt",
}
UPSTREAM_NAMES = {"pstack", "pocock", "unlazy", "optmem", "local-skills"}
HEX_SHA256 = re.compile(r"[0-9a-f]{64}")
NO_MEMO_LINE = "You are a subagent. Don't run memo."
UNSLOP_LAW = (
    "Pstack's exact `unslop` skill is mandatory for every user-visible sentence. "
    "Read and follow it before writing commentary, questions, updates, or final replies."
)
AGENT_ROUTING = f"""# Agent method

{UNSLOP_LAW}

`unslop` also governs every line you write to `MEMORY.md`. The ledger lints each line and refuses one that fails.

For substantial work, read and follow `$unlazy` before work and before any done claim. Use its file-backed gates and exact Stop hook.

Pstack owns the outer development method. Read `$poteto-mode`, its matching pristine playbook, and every applicable `principle-*` skill before planning or implementation. The 21 Pstack principles are binding when their stated condition matches.

Use `$plan-flow` for planning. It replaces the client's built-in plan mode. Pstack owns the plan. Exact Pocock planning skills resolve decisions inside that plan. Stop before implementation.

Use `$implement-flow` for implementation. Pstack owns the implementation playbook. Exact Pocock Implement, Pocock TDD, and code review run only at the playbook steps that select them.

A repository write with no declared route selects `$implement-flow`. The method guard denies that write until the route's exact sources have entered the session. Recover by writing `.unlazy/<scope>/METHOD.json` and its `GATES.md`, then running the engage command the denial names.

Compaction clears the guard's record. Those exact sources must enter the session again before the next write, whatever you still remember of them.

Pstack owns unqualified `$tdd` and `$teach`. Pocock's colliding skills are `$pocock-tdd` and `$pocock-teach`. Preserve both upstream testing methods. Do not merge them or add another test process.

Before production code, read `$clean-code-for-agents`. Akita is the primary code standard. Ousterhout adds deep modules only where a smaller interface removes knowledge from callers. Karpathy and Bigpowers add only compatible rules that fill a named gap.

Before every subagent brief, read `$writing-for-agents`. Every subagent brief must contain exactly: `{NO_MEMO_LINE}` Subagents inherit the parent's live permission mode.

Before writing a skill, a contract, or a plan, read `$writing-for-agents`. It governs every document an agent consumes.

`.agents/skills` is the only repository skill authority. Read a skill there, or through the client link pointing at it, and change neither.
"""
SHARED_HOOK_MODULES = ("method_guard_support.py", "method_guard_rules.py")
CODEX_HOOK_MODULES = (*SHARED_HOOK_MODULES, "method_guard.py", "optmem_lifecycle.py")
CLAUDE_HOOK_MODULES = (*SHARED_HOOK_MODULES, "memory_ledger_hooks.py")
CLAUDE_GUARD_TEMPLATE = "claude_method_guard.py"
CLAUDE_GUARD_INSTALLED = "method_guard.py"
MEMORY_MARKERS = ("<!-- MEMORY_BLOCK_BEGIN -->", "<!-- MEMORY_BLOCK_END -->")
AGENT_METHOD_MARKERS = ("<!-- AGENT_METHOD_BLOCK_BEGIN -->", "<!-- AGENT_METHOD_BLOCK_END -->")
CLIENT_MARKERS = ("<!-- CLIENT_BLOCK_BEGIN -->", "<!-- CLIENT_BLOCK_END -->")
AKITA_MARKERS = ("<!-- AKITA_UPSTREAM_BLOCK_BEGIN -->", "<!-- AKITA_UPSTREAM_BLOCK_END -->")
AKITA_BLOCK_SHA256 = "1a10a1a50fdb9d6c6bac1a06b056f2f8d4cbd0076aa76e72205344893e1567e6"
SHARED_MARKERS = (MEMORY_MARKERS, AGENT_METHOD_MARKERS, AKITA_MARKERS)
CONTRACTS = {"codex": "AGENTS.md", "claude": "CLAUDE.md"}
CLIENT_BLOCKS = {
    "codex": """## Codex specifics

`$name` names a skill under `.agents/skills`. Codex loads that directory
directly.

`.codex/hooks.json` is the only repository hook source. Codex `.rules` files
govern shell permissions only, so this repository does not use them for
behavior.

Routine implementation subagents run `gpt-5.6-sol` at medium reasoning. Reserve
higher reasoning for architecture, ambiguous failures, and final review.
""",
    "claude": """## Claude Code specifics

`$name` names the skill `name`. Invoke it with the Skill tool or `/name`. The
canonical skills reach Claude as symlinks at `.claude/skills`, rebuilt by
`python3 tools/install_claude_skills.py`.

Type `$plan-flow` rather than entering built-in plan mode. The guard reads the
route from your prompt and infers nothing from the permission mode.

`.claude/settings.json` is the only repository hook source.
`.claude/settings.local.json` holds personal settings and ships nothing.

Every subagent runs as `method-worker`, which pins Opus 5 at medium effort and
preloads `unslop`, `clean-code-for-agents`, `writing-for-agents` and `unlazy`.

The repository `code-review` skill replaces the bundled `/code-review` on
purpose, because `$implement-flow` selects the Pocock method at its review step.
""",
}
BASELINE_CLASS_KEYS = {
    "tracked_deletions", "tracked_modifications", "staged_additions",
    "ignored_inputs", "removed_or_quarantined_scratch",
    "unexpected_paths", "overlapping_classes",
}
BASELINE_IGNORED_INPUTS = {
    ".unlazy/repo-cleanup-plan", ".unlazy/repo-cleanup-implementation",
    "archive/agent-harness-pre-20260823",
}
BASELINE_SCRATCH_PATHS = {
    ".codex/harness/receipts/codex-skills-prompt-input.json",
    ".codex/harness/receipts/codex-skills-prompt-input.stderr",
}
CHECKPOINT_EXACT_PATHS = {
    ".gitignore", "AGENTS.md", "CLAUDE.md", "HARNESS_MANUAL.md", "SKILLS.md",
    "START_HERE.md",
    ".codex/hooks.json", ".codex/harness/install-receipt.json",
    ".codex/harness/receipts/codex-skills-list.jsonl",
    ".codex/harness/receipts/lifecycle-events.jsonl",
    ".codex/harness/receipts/lifecycle-verification.txt",
    ".codex/harness/receipts/local-skills-validation.txt",
    ".codex/harness/receipts/optmem-validation.txt",
    ".codex/harness/receipts/pocock-validation.txt",
    ".codex/harness/receipts/pstack-validation.txt",
    ".codex/harness/receipts/unlazy-validation.txt",
    ".codex/harness/receipts/repo-cleanup-baseline-v1.json",
    "design/harness_rebuild_20260823/DECISIONS.tsv",
    "design/harness_rebuild_20260823/research/pstack-pocock.md",
    "gates/harness-install.md", "tests/test_agent_harness.py",
    "tools/agent_harness_sources.py", "tools/agent_harness_verify_common.py",
    "tools/agent_harness_verify_runtime.py", "tools/agent_harness_verify_static.py",
    "tools/install_agent_harness.py", "tools/record_validation_receipt.py",
    "tools/verify_agent_harness.py", "tools/apply_skill_port_batch_20260821.py",
    "tools/install_house_skills.py", "tools/port_upstream_skills.py",
    "tools/test_skill_routing_gate.py", "tools/unlazy_gates.py",
    ".claude/hooks/mempal_hub_hook.sh", ".claude/hooks/optmem_continuity.py",
    ".claude/skills_install_receipt.json",
}
CHECKPOINT_PREFIXES = (
    ".agents/skills/", ".claude/agents/", ".claude/skills/", ".codex/agents/",
    ".codex/hooks/", ".codex/skills/", ".grok/hooks/", ".grok/skills/",
    ".grok/workflows/", ".opencode/skills/", "vendor/agent-sources/",
    "tools/harness_templates/", "design/harness_rebuild_20260823/candidates/",
)


class HarnessVerificationError(RuntimeError):
    """Report a failed harness contract. Example: raise HarnessVerificationError('FAIL')."""
    pass


def refuse(name: str, offending: object, expected: str) -> NoReturn:
    """Raise a contextual contract failure. Example: refuse('gate', value, 'PASS')."""
    raise HarnessVerificationError(
        f"FAIL {name} offending={offending!r} expected={expected!r}"
    )


def require(condition: bool, name: str, offending: object, expected: str) -> None:
    """Enforce one contract. Example: require(count == 76, 'skills', count, '76')."""
    if not condition:
        refuse(name, offending, expected)


def path_exists(path: Path) -> bool:
    """Detect paths without following links. Example: path_exists(Path('/tmp/link'))."""
    return os.path.lexists(path)


def atomic_write(path: Path, content: bytes) -> None:
    """Replace a file atomically. Example: atomic_write(path, b'content')."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def json_bytes(value: object) -> bytes:
    """Serialize stable JSON bytes. Example: json_bytes({'schema_version': 1})."""
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def atomic_exchange_directories(staging: Path, active: Path) -> None:
    """Exchange sibling trees atomically. Example: atomic_exchange_directories(new, live)."""
    renameat2 = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if renameat2 is None:
        raise OSError(f"renameat2 offending=unavailable for staging={staging},active={active}; "
                      "expected Linux atomic directory exchange")
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                          ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    if renameat2(-100, os.fsencode(staging), -100, os.fsencode(active), 2):
        error = ctypes.get_errno()
        raise OSError(error, f"atomic exchange offending=staging:{staging},active:{active}; "
                      "expected successful RENAME_EXCHANGE")


def replace_active_directory(
    staging: Path, active: Path, cleanup: Callable[[Path], None] = shutil.rmtree,
) -> None:
    """Publish one complete tree. Example: replace_active_directory(new, live)."""
    if not path_exists(active):
        os.replace(staging, active)
        return
    atomic_exchange_directories(staging, active)
    cleanup(staging)


def archived_relative(
    path: Path, workspace: Path = ROOT, home: Path = Path("/home/algo"),
) -> Path:
    """Map a managed path into the archive. Example: archived_relative(ROOT / 'AGENTS.md')."""
    try:
        return Path("workspace") / path.relative_to(workspace)
    except ValueError:
        try:
            return Path("home/algo") / path.relative_to(home)
        except ValueError as error:
            raise ValueError(
                f"archive target offending={path}; expected path under {workspace} or {home}"
            ) from error


def exact_object_keys(value: object, expected: set[str], name: str) -> dict[str, object]:
    """Require an exact object schema. Example: exact_object_keys(row, {'id'}, 'row')."""
    require(isinstance(value, dict), name, type(value).__name__, "object")
    row = cast(dict[str, object], value)
    require(set(row) == expected, name, sorted(row), str(sorted(expected)))
    return row


def parse_git_status_records(raw: bytes) -> list[tuple[str, str]]:
    """Parse NUL-delimited status pairs. Example: parse_git_status_records(b'A\\0x\\0')."""
    fields = raw.decode("utf-8").split("\0")
    if fields and fields[-1] == "":
        fields.pop()
    if len(fields) % 2:
        raise ValueError(f"Git status field count offending={len(fields)}; expected even pairs")
    return sorted(zip(fields[::2], fields[1::2]), key=lambda row: row[1])


def normalized_git_status(records: list[tuple[str, str]]) -> bytes:
    """Serialize stable status rows. Example: normalized_git_status([('A', 'x')])."""
    return "".join(f"{status_name}\t{path}\n" for status_name, path in records).encode()


def checkpoint_path_allowed(path: str) -> bool:
    """Check the U02 allowlist. Example: checkpoint_path_allowed('START_HERE.md')."""
    pure = Path(path)
    if pure.is_absolute() or ".." in pure.parts:
        return False
    if "__pycache__" in pure.parts or "node_modules" in pure.parts:
        return False
    return path in CHECKPOINT_EXACT_PATHS or path.startswith(CHECKPOINT_PREFIXES)


def baseline_class_lists(classes: dict[str, object]) -> dict[str, list[str]]:
    require(set(classes) == BASELINE_CLASS_KEYS, "baseline.path-classes",
            sorted(classes), str(sorted(BASELINE_CLASS_KEYS)))
    valid = all(isinstance(value, list)
                and all(isinstance(path, str) and path for path in value)
                for value in classes.values())
    require(valid, "baseline.path-classes", classes, "string path arrays")
    return cast(dict[str, list[str]], classes)


def validate_class_disjointness(rows: dict[str, list[str]]) -> None:
    for name, paths in rows.items():
        require(len(paths) == len(set(paths)), "baseline.path-duplicate",
                {name: paths}, "each path once per class")
    owners: dict[str, list[str]] = {}
    for name, paths in rows.items():
        for path in paths:
            owners.setdefault(path, []).append(name)
    overlaps = {path: names for path, names in owners.items() if len(names) > 1}
    require(not overlaps, "baseline.path-overlap", overlaps, "disjoint path classes")


def classified_changed_paths(rows: dict[str, list[str]]) -> set[str]:
    return set().union(*(set(rows[name]) for name in (
        "tracked_deletions", "tracked_modifications", "staged_additions")))


def validate_baseline_boundaries(rows: dict[str, list[str]]) -> None:
    require(set(rows["ignored_inputs"]) == BASELINE_IGNORED_INPUTS,
            "baseline.ignored-inputs", rows["ignored_inputs"],
            str(sorted(BASELINE_IGNORED_INPUTS)))
    require(set(rows["removed_or_quarantined_scratch"]) == BASELINE_SCRATCH_PATHS,
            "baseline.scratch-paths", rows["removed_or_quarantined_scratch"],
            str(sorted(BASELINE_SCRATCH_PATHS)))
    require(rows["unexpected_paths"] == rows["overlapping_classes"] == [],
            "baseline.zero-path-errors", rows, "empty unexpected and overlap arrays")


def validate_baseline_path_classes(
    classes: dict[str, object], changed_paths: set[str],
) -> None:
    """Check path-class completeness. Example: validate_baseline_path_classes(rows, paths)."""
    rows = baseline_class_lists(classes)
    validate_class_disjointness(rows)
    classified = classified_changed_paths(rows)
    require(classified == changed_paths, "baseline.path-classification",
            sorted(classified ^ changed_paths), "every changed path classified exactly once")
    outside = sorted(path for path in changed_paths if not checkpoint_path_allowed(path))
    require(not outside, "baseline.commit-scope", outside, "audited U02 allowlist")
    validate_baseline_boundaries(rows)


def validate_baseline_status_classes(
    classes: dict[str, object], records: list[tuple[str, str]],
) -> None:
    """Match classes to Git status. Example: validate_baseline_status_classes(rows, status)."""
    rows = baseline_class_lists(classes)
    expected = {
        "D": rows["tracked_deletions"],
        "M": rows["tracked_modifications"],
        "A": rows["staged_additions"],
    }
    actual = {status_name: [] for status_name in expected}
    for status_name, path in records:
        require(status_name in actual, "baseline.git-status", status_name,
                "A, D, or M without rename detection")
        actual[status_name].append(path)
    require(actual == expected, "baseline.status-classes", actual, str(expected))


def load_json_object(path: Path, name: str) -> dict[str, object]:
    """Load one JSON object. Example: load_json_object(path, 'receipt')."""
    require(path.is_file(), name, str(path), "existing JSON file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        refuse(name, f"{path}: {error}", "valid UTF-8 JSON object")
    require(isinstance(value, dict), name, type(value).__name__, "JSON object")
    return cast(dict[str, object], value)


def validate_receipt_identity(receipt: dict[str, object]) -> None:
    require(set(receipt) == RECEIPT_KEYS, "install-receipt.keys",
            sorted(receipt), str(sorted(RECEIPT_KEYS)))
    require(receipt["schema_version"] == 1, "install-receipt.schema_version",
            receipt["schema_version"], "1")
    require(receipt["workspace"] == str(ROOT), "install-receipt.workspace",
            receipt["workspace"], str(ROOT))
    require(receipt["source_commits"] == PINNED_COMMITS,
            "install-receipt.source_commits", receipt["source_commits"],
            str(PINNED_COMMITS))
    require(receipt["optmem_sha256"] == OPT_MEM_SHA256,
            "install-receipt.optmem_sha256", receipt["optmem_sha256"],
            OPT_MEM_SHA256)


def validate_receipt_skill_names(receipt: dict[str, object]) -> None:
    names = receipt["active_skill_names"]
    valid = isinstance(names, list) and all(isinstance(item, str) for item in names)
    require(valid, "install-receipt.active_skill_names", names,
            "sorted unique string list")
    require(names == sorted(set(cast(list[str], names))),
            "install-receipt.active_skill_names", names,
            "sorted unique string list")


def validate_receipt_paths(receipt: dict[str, object]) -> None:
    paths = receipt["upstream_receipts"]
    valid = isinstance(paths, dict) and set(paths) == UPSTREAM_NAMES
    require(valid, "install-receipt.upstream_receipts", paths,
            f"mapping with keys {sorted(UPSTREAM_NAMES)}")
    for key, value in cast(dict[str, object], paths).items():
        require(isinstance(value, str) and Path(value).is_absolute(),
                f"install-receipt.upstream_receipts.{key}", value, "absolute path")
    lifecycle = receipt["lifecycle_probe_receipt"]
    require(isinstance(lifecycle, str) and Path(lifecycle).is_absolute(),
            "install-receipt.lifecycle_probe_receipt", lifecycle, "absolute path")


def load_install_receipt() -> dict[str, object]:
    """Load the validated install receipt. Example: load_install_receipt()."""
    receipt = load_json_object(RECEIPT_PATH, "install-receipt")
    validate_receipt_identity(receipt)
    validate_receipt_skill_names(receipt)
    validate_receipt_paths(receipt)
    return receipt


def sha256_bytes(value: bytes) -> str:
    """Hash exact bytes. Example: sha256_bytes(b'content')."""
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    """Hash exact file bytes. Example: sha256_file(Path('AGENTS.md'))."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def path_entries(root: Path) -> list[tuple[str, Path]]:
    entries: list[tuple[str, Path]] = [(".", root)]
    cursor = 0
    while cursor < len(entries):
        relative, path = entries[cursor]
        cursor += 1
        if stat.S_ISDIR(path.lstat().st_mode):
            children = sorted(path.iterdir(), key=lambda item: item.name)
            entries.extend((f"{relative.rstrip('.')}/{item.name}".lstrip("/"), item)
                           for item in children)
    return sorted(entries, key=lambda item: item[0])


def path_tree_metrics(root: Path, excluded: frozenset[Path] = frozenset()) -> dict[str, int]:
    """Measure one path tree. Example: path_tree_metrics(ROOT / '.agents')."""
    metrics = {"directories": 0, "regular_files": 0, "symlinks": 0,
               "regular_file_bytes": 0, "apparent_bytes": 0, "allocated_bytes": 0}
    for _, path in path_entries(root):
        if path in excluded:
            continue
        details = path.lstat()
        if stat.S_ISDIR(details.st_mode):
            metrics["directories"] += 1
            continue
        metrics["apparent_bytes"] += details.st_size
        metrics["allocated_bytes"] += details.st_blocks * 512
        if stat.S_ISREG(details.st_mode):
            metrics["regular_files"] += 1
            metrics["regular_file_bytes"] += details.st_size
        elif stat.S_ISLNK(details.st_mode):
            metrics["symlinks"] += 1
    return metrics


def framed_path_payload(path: Path) -> tuple[str, bytes]:
    mode = path.lstat().st_mode
    if stat.S_ISDIR(mode):
        return "d", b""
    if stat.S_ISREG(mode):
        return "f", path.read_bytes()
    if stat.S_ISLNK(mode):
        return "l", os.readlink(path).encode("utf-8", "surrogateescape")
    refuse("path-hash.kind", f"{path}: {stat.S_IFMT(mode):o}",
           "regular file, directory, or symlink")


def framed_path_sha256(root: Path) -> str:
    """Hash a typed path tree. Example: framed_path_sha256(ROOT / '.agents')."""
    require(os.path.lexists(root), "path-hash.root", str(root), "existing path")
    digest = hashlib.sha256()
    for relative, path in path_entries(root):
        kind, payload = framed_path_payload(path)
        mode = path.lstat().st_mode
        fields = (kind.encode(), relative.encode("utf-8", "surrogateescape"),
                  f"{stat.S_IMODE(mode):04o}".encode(), str(len(payload)).encode(), payload)
        digest.update(b"\0".join(fields) + b"\0")
    return digest.hexdigest()


def archive_kind(path: Path) -> str:
    """Name an archive entry kind. Example: archive_kind(Path('AGENTS.md'))."""
    mode = path.lstat().st_mode
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISLNK(mode):
        return "symlink"
    refuse("archive.kind", f"{path}: {stat.S_IFMT(mode):o}",
           "file, directory, or symlink")
