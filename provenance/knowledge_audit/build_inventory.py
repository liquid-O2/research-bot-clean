#!/usr/bin/env python3
"""Build a content-free, bounded provenance inventory.

Only metadata, hashes, byte ranges, JSON record kinds, and dispositions are
published.  No source text or binary payload is copied.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable, Iterator


SCHEMA_VERSION = "knowledge_audit_v1"
WORK = Path("/workspace/data/cleanroom_work/knowledge_audit")
DEFAULT_OUTPUT = WORK / "publication_v1"
CURRENT_THREAD = os.environ.get("CODEX_THREAD_ID", "")
CHUNK = 4 * 1024 * 1024
MAX_CACHE_TEXT_HASH = 64 * 1024 * 1024

TEXT_SUFFIXES = {
    ".md", ".txt", ".rst", ".json", ".jsonl", ".yaml", ".yml",
    ".toml", ".tsv", ".csv", ".py", ".rs", ".sh", ".bash", ".zsh",
    ".js", ".ts", ".sql", ".ini", ".cfg", ".lock", ".log", ".tex",
}
PAYLOAD_SUFFIXES = {
    ".parquet", ".arrow", ".feather", ".npy", ".npz", ".pt", ".pth",
    ".safetensors", ".bin", ".dat", ".db", ".sqlite", ".wal", ".shm",
    ".so", ".o", ".a", ".rlib", ".rmeta", ".pyc", ".pkl", ".pickle",
    ".tar", ".gz", ".bz2", ".xz", ".zst", ".zip", ".7z", ".png",
    ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov", ".wav",
}
AUTHORITY_RE = re.compile(
    r"(?:^|[_\-.])(manifest|receipt|task[_-]?card|prereg|contract|schema|"
    r"source[_-]?closure|red[_-]?declaration|proof|audit|index)(?:$|[_\-.])",
    re.IGNORECASE,
)
REPORT_RE = re.compile(r"(?:^|[_\-.])(report|memo|plan|summary)(?:$|[_\-.])", re.I)
SECRET_RE = re.compile(r"(?:^|/)(auth\.json|credentials?|secrets?|.*\.pem|.*\.key)$", re.I)
YEAR_2026_DATA_RE = re.compile(r"(?:^|[/_.-])2026(?:[/_.-]|$)")


@dataclass(frozen=True)
class Universe:
    universe_id: str
    root: Path
    recursive: bool = True
    include_top_level_only: bool = False


UNIVERSES = (
    Universe("codex_local", Path("/home/claude/.codex")),
    Universe("claude_workspace_history", Path("/home/claude/.claude/projects/-workspace")),
    Universe("workspace_top_contracts", Path("/workspace"), recursive=False, include_top_level_only=True),
    Universe("workspace_docs", Path("/workspace/docs")),
    Universe("workspace_research", Path("/workspace/research")),
    Universe("workspace_chat_plans", Path("/workspace/chat-plan")),
    Universe("workflow_memory", Path("/workspace/artifacts/workflow_memory")),
    Universe("review_logs", Path("/workspace/artifacts/review_logs")),
    Universe("published_runs", Path("/workspace/artifacts/runs")),
    Universe("cache_census", Path("/workspace/artifacts/cache")),
    Universe("manual_papers", Path("/workspace/data/manual_papers")),
    Universe("manual_refs", Path("/workspace/data/manual_refs")),
    Universe("research_v2", Path("/workspace/data/research_v2")),
)


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def digest_text(value: str, n: int = 32) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:n]


def source_id(universe_id: str, relative: str) -> str:
    return "src_" + digest_text(universe_id + "\0" + relative)


def segment_id(source: str, ordinal: int, start: int, end: int) -> str:
    key = f"{source}\0{ordinal}\0{start}\0{end}"
    return "seg_" + hashlib.sha256(key.encode()).hexdigest()[:40]


def iter_entries(universe: Universe) -> Iterator[tuple[Path, str]]:
    root = universe.root
    if not root.exists():
        return
    if universe.include_top_level_only:
        for child in sorted(root.iterdir(), key=lambda p: os.fsencode(p.name)):
            if child.is_file() or child.is_symlink():
                if child.name in {"AGENTS.md", "INDEX.md", "PROJECT_GOAL.md", "README.md", "CLAUDE.md"} or child.suffix.lower() in {".md", ".json", ".tsv"}:
                    yield child, child.name
        return
    if not universe.recursive:
        return
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            children = sorted(os.scandir(directory), key=lambda x: os.fsencode(x.name), reverse=True)
        except (FileNotFoundError, PermissionError):
            continue
        for entry in children:
            path = Path(entry.path)
            relative = os.path.relpath(path, root)
            try:
                if entry.is_dir(follow_symlinks=False):
                    if path == WORK or WORK in path.parents:
                        continue
                    stack.append(path)
                else:
                    yield path, relative
            except FileNotFoundError:
                yield path, relative


def roster() -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    roots: list[dict] = []
    seen_paths: set[str] = set()
    for universe in UNIVERSES:
        root_row = {
            "universe_id": universe.universe_id,
            "root": str(universe.root),
            "exists": universe.root.exists(),
            "recursive": universe.recursive,
            "top_level_filter": universe.include_top_level_only,
            "entry_count": 0,
        }
        for path, relative in iter_entries(universe):
            absolute = str(path)
            # Exact-path de-duplication across overlapping roots is explicit.
            duplicate_of = absolute if absolute in seen_paths else None
            if duplicate_of is None:
                seen_paths.add(absolute)
            try:
                st = os.lstat(path)
                kind = "SYMLINK" if stat.S_ISLNK(st.st_mode) else "REGULAR" if stat.S_ISREG(st.st_mode) else "OTHER"
                row = {
                    "universe_id": universe.universe_id,
                    "root": str(universe.root),
                    "absolute_path": absolute,
                    "relative_path": relative,
                    "entry_kind": kind,
                    "snapshot_size": st.st_size,
                    "mtime_ns": st.st_mtime_ns,
                    "mode_octal": f"{stat.S_IMODE(st.st_mode):04o}",
                    "device": st.st_dev,
                    "inode": st.st_ino,
                    "duplicate_path_of": duplicate_of,
                }
            except FileNotFoundError:
                row = {
                    "universe_id": universe.universe_id,
                    "root": str(universe.root),
                    "absolute_path": absolute,
                    "relative_path": relative,
                    "entry_kind": "MISSING_AT_SCAN",
                    "snapshot_size": 0,
                    "mtime_ns": 0,
                    "mode_octal": "0000",
                    "device": 0,
                    "inode": 0,
                    "duplicate_path_of": duplicate_of,
                }
            rows.append(row)
            root_row["entry_count"] += 1
        roots.append(root_row)
    rows.sort(key=lambda x: (x["universe_id"], os.fsencode(x["relative_path"])))
    return rows, roots


def classify(row: dict) -> dict:
    universe = row["universe_id"]
    path = row["absolute_path"]
    rel = row["relative_path"]
    name = Path(path).name
    suffix = Path(path).suffix.lower()
    lower = path.lower()
    size = row["snapshot_size"]
    result = {
        "source_role": "PROJECT_CONTEXT",
        "authority_tier": "CONTEXT_ONLY",
        "privacy_class": "PRIVATE_WORKSPACE",
        "license_class": "PROJECT_AUTHORED_OR_UNKNOWN",
        "redistribution": "REFUSE",
        "evidence_disposition": "CONTEXT_ONLY",
        "classification_rule": "default_private_context",
        "content_state": "FULL_PREFIX_SHA256",
    }
    if row["entry_kind"] == "SYMLINK":
        result.update(source_role="SYMLINK_REFERENCE", authority_tier="NONE", evidence_disposition="METADATA_ONLY", classification_rule="symlink_no_follow", content_state="SYMLINK_METADATA_ONLY")
        return result
    if row["entry_kind"] != "REGULAR":
        result.update(source_role="NONREGULAR_ENTRY", authority_tier="NONE", evidence_disposition="METADATA_ONLY", classification_rule="nonregular", content_state="METADATA_ONLY_CLASSIFIED")
        return result
    if SECRET_RE.search(path):
        result.update(source_role="POTENTIAL_SECRET", authority_tier="PROHIBITED", privacy_class="SECRET", license_class="PRIVATE_SECRET", redistribution="REFUSE", evidence_disposition="SECRET_EXCLUDED", classification_rule="secret_filename", content_state="SECRET_METADATA_ONLY")
        return result
    if universe == "codex_local":
        result.update(privacy_class="PRIVATE_CONVERSATION", license_class="PRIVATE_NO_REDISTRIBUTION")
        if "/sessions/" in path or name == "history.jsonl":
            result.update(source_role="CODEX_TRANSCRIPT", authority_tier="LINEAGE_SOURCE", evidence_disposition="CONTEXT_ONLY", classification_rule="codex_transcript")
            result["content_state"] = "JSONL_PREFIX_SHA256"
        elif re.search(r"(?:thread_history|state|queue|goals|logs|memories)_\d+\.sqlite(?:-(?:wal|shm))?$", name):
            result.update(source_role="CODEX_STATE_DATABASE", authority_tier="LINEAGE_SOURCE", evidence_disposition="PRIVATE_LINEAGE_METADATA", classification_rule="codex_state_db", content_state="METADATA_ONLY_CLASSIFIED")
        elif "/shell_snapshots/" in path:
            result.update(source_role="CODEX_SHELL_CONTEXT", authority_tier="LINEAGE_SOURCE", evidence_disposition="CONTEXT_ONLY", classification_rule="codex_shell_snapshot")
        else:
            result.update(source_role="CODEX_TOOL_INSTALLATION", authority_tier="NONE", evidence_disposition="TOOLING_OUT_OF_SCOPE", classification_rule="codex_non_lineage_tooling", content_state="METADATA_ONLY_CLASSIFIED")
        return result
    if universe == "claude_workspace_history":
        result.update(privacy_class="PRIVATE_CONVERSATION", license_class="PRIVATE_NO_REDISTRIBUTION", authority_tier="LINEAGE_SOURCE")
        if suffix == ".jsonl":
            result.update(source_role="CLAUDE_TRANSCRIPT", evidence_disposition="CONTEXT_ONLY", classification_rule="claude_jsonl", content_state="JSONL_PREFIX_SHA256")
        elif "/tool-results/" in path:
            result.update(source_role="CLAUDE_TOOL_RESULT", evidence_disposition="CONTEXT_ONLY_UNVERIFIED", classification_rule="claude_tool_result")
        elif "/memory/" in path:
            result.update(source_role="CLAUDE_MEMORY", evidence_disposition="CONTEXT_ONLY", classification_rule="claude_memory")
        else:
            result.update(source_role="CLAUDE_HISTORY_AUX", evidence_disposition="CONTEXT_ONLY", classification_rule="claude_aux")
        return result
    if YEAR_2026_DATA_RE.search(lower) and (suffix in PAYLOAD_SUFFIXES or universe == "cache_census"):
        result.update(source_role="POTENTIAL_2026_DATA", authority_tier="PROHIBITED", privacy_class="MARKET_OR_DERIVED_DATA", license_class="VENDOR_OR_PROJECT_DATA_RESTRICTED", evidence_disposition="DATA_WALL_METADATA_ONLY", classification_rule="2026_data_wall", content_state="PROHIBITED_DATA_WALL_METADATA_ONLY")
        return result
    if universe in {"manual_papers", "manual_refs"} or suffix == ".pdf" or "/papers/" in lower:
        result.update(source_role="THIRD_PARTY_RESEARCH", authority_tier="PRIMARY_RESEARCH_INPUT", privacy_class="PRIVATE_WORKSPACE", license_class="THIRD_PARTY_COPYRIGHT_RESTRICTED", redistribution="METADATA_ONLY", evidence_disposition="RESEARCH_INPUT_RESTRICTED", classification_rule="third_party_research")
        return result
    if universe == "cache_census":
        result.update(privacy_class="PRIVATE_WORKSPACE")
        if suffix in PAYLOAD_SUFFIXES or "/target/" in lower or "/__pycache__/" in lower or size > MAX_CACHE_TEXT_HASH:
            result.update(source_role="DERIVED_OR_BUILD_PAYLOAD", authority_tier="DATA_ARTIFACT", license_class="VENDOR_OR_PROJECT_DATA_RESTRICTED", evidence_disposition="DERIVED_PAYLOAD_METADATA_ONLY", classification_rule="cache_payload_or_oversize", content_state="METADATA_ONLY_CLASSIFIED")
        elif AUTHORITY_RE.search(name):
            result.update(source_role="CACHE_AUTHORITY_ARTIFACT", authority_tier="RECEIPT_AUTHORITY", license_class="PROJECT_AUTHORED", evidence_disposition="EVIDENCE_CANDIDATE_REQUIRES_RECOMPUTE", classification_rule="cache_authority_name")
        elif suffix in {".py", ".rs", ".sh", ".js", ".ts", ".toml"}:
            result.update(source_role="CACHE_SOURCE_CODE", authority_tier="CODE_AUTHORITY", license_class="PROJECT_AUTHORED_OR_VENDORED", evidence_disposition="CODE_EVIDENCE_CANDIDATE", classification_rule="cache_source")
        elif suffix in TEXT_SUFFIXES:
            result.update(source_role="CACHE_TEXT_CONTEXT", authority_tier="CONTEXT_ONLY", evidence_disposition="CONTEXT_ONLY", classification_rule="cache_text")
        else:
            result.update(source_role="CACHE_ARTIFACT", authority_tier="DATA_ARTIFACT", evidence_disposition="DERIVED_PAYLOAD_METADATA_ONLY", classification_rule="cache_other_metadata", content_state="METADATA_ONLY_CLASSIFIED")
        return result
    if universe in {"workflow_memory", "review_logs", "published_runs"}:
        if AUTHORITY_RE.search(name) or suffix in {".json", ".tsv"}:
            result.update(source_role="WORKFLOW_RECEIPT", authority_tier="RECEIPT_AUTHORITY", license_class="PROJECT_AUTHORED", evidence_disposition="EVIDENCE_CANDIDATE_REQUIRES_RECOMPUTE", classification_rule="workflow_receipt")
        elif suffix in {".pid", ".hb", ".rc"}:
            result.update(source_role="OPERATIONAL_RUN_STATE", authority_tier="OPERATIONAL_ONLY", evidence_disposition="OPERATIONAL_ONLY", classification_rule="run_state", content_state="METADATA_ONLY_CLASSIFIED")
        else:
            result.update(source_role="WORKFLOW_CONTEXT", authority_tier="CONTEXT_ONLY", evidence_disposition="CONTEXT_ONLY", classification_rule="workflow_context")
        return result
    if universe in {"workspace_docs", "workspace_top_contracts", "workspace_chat_plans"}:
        if name in {"INDEX.md", "AGENTS.md", "PROJECT_GOAL.md"} or AUTHORITY_RE.search(name):
            result.update(source_role="PROJECT_CONTRACT", authority_tier="SPEC_AUTHORITY", license_class="PROJECT_AUTHORED", evidence_disposition="PROCEDURAL_AUTHORITY", classification_rule="project_contract")
        elif REPORT_RE.search(name) or universe == "workspace_chat_plans":
            result.update(source_role="PROJECT_REPORT_OR_PLAN", authority_tier="CONTEXT_ONLY", evidence_disposition="CONTEXT_ONLY_UNVERIFIED", classification_rule="report_plan_context")
        else:
            result.update(source_role="PROJECT_DOCUMENT", authority_tier="CONTEXT_ONLY", evidence_disposition="CONTEXT_ONLY", classification_rule="project_document")
        return result
    if universe in {"workspace_research", "research_v2"}:
        if "/review_records/" in path:
            result.update(source_role="RESEARCH_REVIEW_RECORD", authority_tier="REVIEW_EVIDENCE", license_class="PROJECT_AUTHORED_OR_THIRD_PARTY_MIXED", evidence_disposition="REVIEW_CONTEXT_REQUIRES_SOURCE", classification_rule="review_record")
        elif AUTHORITY_RE.search(name):
            result.update(source_role="RESEARCH_AUTHORITY_ARTIFACT", authority_tier="RECEIPT_AUTHORITY", evidence_disposition="EVIDENCE_CANDIDATE_REQUIRES_RECOMPUTE", classification_rule="research_authority")
        else:
            result.update(source_role="RESEARCH_CONTEXT", authority_tier="CONTEXT_ONLY", evidence_disposition="CONTEXT_ONLY_UNVERIFIED", classification_rule="research_context")
        return result
    return result


def hash_prefix(file: BinaryIO, length: int) -> str:
    h = hashlib.sha256()
    remaining = length
    while remaining:
        block = file.read(min(CHUNK, remaining))
        if not block:
            raise EOFError(f"source shortened with {remaining} snapshot bytes unread")
        h.update(block)
        remaining -= len(block)
    return h.hexdigest()


def jsonl_segments(file: BinaryIO, length: int, source: str, snapshot: str) -> tuple[str, list[dict], list[dict]]:
    whole = hashlib.sha256()
    segments: list[dict] = []
    fragments: list[dict] = []
    buffer = bytearray()
    consumed = 0
    line_start = 0
    line_number = 0

    def emit(raw: bytes, terminated: bool) -> None:
        nonlocal line_start, line_number
        line_number += 1
        end = line_start + len(raw)
        body = raw[:-1] if terminated and raw.endswith(b"\n") else raw
        if body.endswith(b"\r"):
            body = body[:-1]
        state = "VALID_OBJECT"
        record_type = None
        error_class = None
        try:
            text = body.decode("utf-8")
            if not text.strip():
                state = "BLANK_LINE"
                error_class = "blank"
            else:
                value = json.loads(text)
                if isinstance(value, dict):
                    candidate = value.get("type", value.get("role"))
                    record_type = candidate if isinstance(candidate, str) and len(candidate) <= 128 else None
                else:
                    state = "VALID_NONOBJECT"
        except UnicodeDecodeError:
            state = "INVALID_UTF8"
            error_class = "utf8"
        except json.JSONDecodeError as exc:
            state = "MALFORMED_JSON"
            error_class = f"json:{exc.msg[:80]}"
        if not terminated:
            state = "VALID_JSON_UNTERMINATED_TAIL" if state in {"VALID_OBJECT", "VALID_NONOBJECT"} else "MALFORMED_JSON_UNTERMINATED_TAIL"
            error_class = error_class or "unterminated_tail"
        disposition = "CONTEXT_ONLY" if state in {"VALID_OBJECT", "VALID_NONOBJECT"} else "MALFORMED_FRAGMENT_QUARANTINE"
        seg = {
            "schema_version": "segment_inventory_v1",
            "snapshot_id": snapshot,
            "segment_id": segment_id(source, line_number - 1, line_start, end),
            "source_id": source,
            "ordinal": line_number - 1,
            "segment_kind": "JSONL_RECORD" if disposition == "CONTEXT_ONLY" else "JSONL_FRAGMENT",
            "byte_start": line_start,
            "byte_end": end,
            "segment_sha256": hashlib.sha256(raw).hexdigest(),
            "line_number": line_number,
            "parse_state": state,
            "record_type": record_type,
            "evidence_disposition": disposition,
            "raw_content_copied": False,
        }
        segments.append(seg)
        if disposition == "MALFORMED_FRAGMENT_QUARANTINE":
            fragments.append({
                "schema_version": "jsonl_fragment_v1",
                "snapshot_id": snapshot,
                "source_id": source,
                "segment_id": seg["segment_id"],
                "line_number": line_number,
                "byte_start": line_start,
                "byte_end": end,
                "fragment_sha256": seg["segment_sha256"],
                "parse_state": state,
                "error_class": error_class,
                "raw_content_copied": False,
            })
        line_start = end

    remaining = length
    while remaining:
        chunk = file.read(min(CHUNK, remaining))
        if not chunk:
            raise EOFError(f"JSONL source shortened with {remaining} bytes unread")
        whole.update(chunk)
        buffer.extend(chunk)
        remaining -= len(chunk)
        consumed += len(chunk)
        while True:
            index = buffer.find(b"\n")
            if index < 0:
                break
            raw = bytes(buffer[: index + 1])
            del buffer[: index + 1]
            emit(raw, True)
    if buffer:
        emit(bytes(buffer), False)
    if not segments:
        segments.append({
            "schema_version": "segment_inventory_v1", "snapshot_id": snapshot,
            "segment_id": segment_id(source, 0, 0, 0), "source_id": source,
            "ordinal": 0, "segment_kind": "WHOLE_FILE", "byte_start": 0,
            "byte_end": 0, "segment_sha256": hashlib.sha256(b"").hexdigest(),
            "line_number": None, "parse_state": "EMPTY_JSONL", "record_type": None,
            "evidence_disposition": "CONTEXT_ONLY", "raw_content_copied": False,
        })
    return whole.hexdigest(), segments, fragments


def post_state(path: Path, row: dict) -> tuple[int, str]:
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return 0, "DRIFTED"
    identity = (st.st_dev, st.st_ino)
    if identity != (row["device"], row["inode"]) or st.st_size < row["snapshot_size"]:
        return st.st_size, "DRIFTED"
    if st.st_size > row["snapshot_size"] or st.st_mtime_ns != row["mtime_ns"]:
        return st.st_size, "APPENDED_AFTER_SNAPSHOT"
    return st.st_size, "STABLE"


def scan_one(row: dict, snapshot: str) -> tuple[dict, list[dict], list[dict]]:
    c = classify(row)
    path = Path(row["absolute_path"])
    sid = source_id(row["universe_id"], row["relative_path"])
    out = {
        "schema_version": "source_inventory_v1", "snapshot_id": snapshot,
        "source_id": sid, "universe_id": row["universe_id"],
        "absolute_path": row["absolute_path"], "relative_path": row["relative_path"],
        "entry_kind": row["entry_kind"], "snapshot_size": row["snapshot_size"],
        "mtime_ns": row["mtime_ns"], "mode_octal": row["mode_octal"],
        "device": row["device"], "inode": row["inode"], "symlink_target": None,
        "content_state": c["content_state"], "sha256": None,
        "post_size": row["snapshot_size"], "scan_state": "NOT_READ",
        "source_role": c["source_role"], "authority_tier": c["authority_tier"],
        "privacy_class": c["privacy_class"], "license_class": c["license_class"],
        "redistribution": c["redistribution"], "evidence_disposition": c["evidence_disposition"],
        "classification_rule": c["classification_rule"],
        "current_codex_thread": bool(CURRENT_THREAD and CURRENT_THREAD in row["absolute_path"]),
        "raw_content_copied": False,
    }
    segments: list[dict] = []
    fragments: list[dict] = []
    if row["entry_kind"] == "SYMLINK":
        try:
            out["symlink_target"] = os.readlink(path)
        except OSError:
            out["symlink_target"] = "<unreadable>"
        segments.append(metadata_segment(sid, snapshot, row["snapshot_size"], c["evidence_disposition"]))
        return out, segments, fragments
    if row["entry_kind"] != "REGULAR" or c["content_state"] in {"METADATA_ONLY_CLASSIFIED", "SECRET_METADATA_ONLY", "PROHIBITED_DATA_WALL_METADATA_ONLY"}:
        segments.append(metadata_segment(sid, snapshot, row["snapshot_size"], c["evidence_disposition"]))
        return out, segments, fragments
    try:
        with path.open("rb", buffering=0) as handle:
            if c["content_state"] == "JSONL_PREFIX_SHA256":
                digest, segments, fragments = jsonl_segments(handle, row["snapshot_size"], sid, snapshot)
            else:
                digest = hash_prefix(handle, row["snapshot_size"])
                segments = [whole_segment(sid, snapshot, row["snapshot_size"], digest, c["evidence_disposition"])]
        out["sha256"] = digest
        out["post_size"], out["scan_state"] = post_state(path, row)
    except (OSError, EOFError) as exc:
        out["scan_state"] = "DRIFTED"
        out["evidence_disposition"] = "LIVE_MUTABLE_CONTEXT_ONLY"
        out["classification_rule"] += "+read_drift"
        segments = [metadata_segment(sid, snapshot, row["snapshot_size"], "LIVE_MUTABLE_CONTEXT_ONLY")]
        fragments.append({
            "schema_version": "jsonl_fragment_v1", "snapshot_id": snapshot,
            "source_id": sid, "segment_id": segments[0]["segment_id"],
            "line_number": None, "byte_start": 0, "byte_end": row["snapshot_size"],
            "fragment_sha256": None, "parse_state": "SOURCE_DRIFT_DURING_SCAN",
            "error_class": type(exc).__name__, "raw_content_copied": False,
        })
    return out, segments, fragments


def metadata_segment(sid: str, snapshot: str, size: int, disposition: str) -> dict:
    return {
        "schema_version": "segment_inventory_v1", "snapshot_id": snapshot,
        "segment_id": segment_id(sid, 0, 0, size), "source_id": sid, "ordinal": 0,
        "segment_kind": "METADATA_ONLY", "byte_start": 0, "byte_end": size,
        "segment_sha256": None, "line_number": None, "parse_state": "NOT_PARSED_CLASSIFIED",
        "record_type": None, "evidence_disposition": disposition, "raw_content_copied": False,
    }


def whole_segment(sid: str, snapshot: str, size: int, digest: str, disposition: str) -> dict:
    return {
        "schema_version": "segment_inventory_v1", "snapshot_id": snapshot,
        "segment_id": segment_id(sid, 0, 0, size), "source_id": sid, "ordinal": 0,
        "segment_kind": "WHOLE_FILE", "byte_start": 0, "byte_end": size,
        "segment_sha256": digest, "line_number": None, "parse_state": "WHOLE_FILE_HASHED",
        "record_type": None, "evidence_disposition": disposition, "raw_content_copied": False,
    }


def write_jsonl(path: Path, rows: Iterable[dict]) -> str:
    h = hashlib.sha256()
    with path.open("xb") as handle:
        for row in rows:
            encoded = canonical_json(row)
            handle.write(encoded)
            h.update(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    return h.hexdigest()


def write_bytes(path: Path, data: bytes) -> str:
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    return hashlib.sha256(data).hexdigest()


def git_lineage(stage: Path) -> dict[str, str]:
    commands = {
        "git_head.txt": ["git", "-C", "/workspace", "rev-parse", "HEAD"],
        "git_refs.tsv": ["git", "-C", "/workspace", "for-each-ref", "--format=%(refname)\t%(objectname)\t%(objecttype)"],
        "git_worktrees.txt": ["git", "-C", "/workspace", "worktree", "list", "--porcelain"],
        "git_status_v2.txt": ["git", "-C", "/workspace", "status", "--porcelain=v2", "--branch", "--untracked-files=no"],
    }
    hashes = {}
    for name, command in commands.items():
        proc = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        hashes[name] = write_bytes(stage / name, proc.stdout)
    return hashes


def rename_noreplace(source: Path, destination: Path) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise RuntimeError("renameat2 unavailable")
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    rc = renameat2(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    if rc != 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err), str(destination))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.parent != WORK.resolve() or output.exists():
        raise SystemExit("output must be a new direct child of the fixed audit directory")
    stage = WORK / f".{output.name}.stage-{os.getpid()}"
    stage.mkdir(mode=0o700)
    start = time.monotonic()
    rows, roots = roster()
    roster_material = "".join(
        f"{r['universe_id']}\0{r['relative_path']}\0{r['device']}\0{r['inode']}\0{r['snapshot_size']}\0{r['mtime_ns']}\n"
        for r in rows
    )
    snapshot = hashlib.sha256(roster_material.encode()).hexdigest()
    roster_rows = [{"schema_version": "snapshot_roster_v1", "snapshot_id": snapshot, **r} for r in rows]
    hashes: dict[str, str] = {}
    hashes["snapshot_roster.jsonl"] = write_jsonl(stage / "snapshot_roster.jsonl", roster_rows)
    sources: list[dict] = []
    segments: list[dict] = []
    fragments: list[dict] = []
    for index, row in enumerate(rows, 1):
        source, source_segments, source_fragments = scan_one(row, snapshot)
        sources.append(source)
        segments.extend(source_segments)
        fragments.extend(source_fragments)
        if index % 10_000 == 0:
            print(f"scanned {index}/{len(rows)}", file=sys.stderr, flush=True)
    sources.sort(key=lambda x: x["source_id"])
    segments.sort(key=lambda x: (x["source_id"], x["ordinal"]))
    fragments.sort(key=lambda x: (x["source_id"], x.get("line_number") or 0, x["byte_start"]))
    hashes["source_inventory.jsonl"] = write_jsonl(stage / "source_inventory.jsonl", sources)
    hashes["segments.jsonl"] = write_jsonl(stage / "segments.jsonl", segments)
    hashes["jsonl_fragments.jsonl"] = write_jsonl(stage / "jsonl_fragments.jsonl", fragments)
    codex_lineage = [s for s in sources if s["universe_id"] == "codex_local" and s["authority_tier"] == "LINEAGE_SOURCE"]
    claude_history = [s for s in sources if s["universe_id"] == "claude_workspace_history"]
    hashes["codex_lineage_manifest.jsonl"] = write_jsonl(stage / "codex_lineage_manifest.jsonl", codex_lineage)
    hashes["claude_history_manifest.jsonl"] = write_jsonl(stage / "claude_history_manifest.jsonl", claude_history)
    hashes["propositions.jsonl"] = write_bytes(stage / "propositions.jsonl", b"")
    hashes["evidence_links.jsonl"] = write_bytes(stage / "evidence_links.jsonl", b"")
    authorities = [s for s in sources if s["authority_tier"] not in {"NONE", "CONTEXT_ONLY", "OPERATIONAL_ONLY", "DATA_ARTIFACT"}]
    hashes["authority_manifest.jsonl"] = write_jsonl(stage / "authority_manifest.jsonl", authorities)
    duplicate_map: defaultdict[str, list[str]] = defaultdict(list)
    for source in sources:
        if source["sha256"]:
            duplicate_map[source["sha256"]].append(source["source_id"])
    duplicate_rows = [
        {"sha256": digest, "source_ids": sorted(ids), "count": len(ids)}
        for digest, ids in sorted(duplicate_map.items()) if len(ids) > 1
    ]
    hashes["duplicate_groups.jsonl"] = write_jsonl(stage / "duplicate_groups.jsonl", duplicate_rows)
    git_hashes = git_lineage(stage)
    hashes.update(git_hashes)
    role_counts = Counter(s["source_role"] for s in sources)
    privacy_counts = Counter(s["privacy_class"] for s in sources)
    license_counts = Counter(s["license_class"] for s in sources)
    content_counts = Counter(s["content_state"] for s in sources)
    parse_counts = Counter(s["parse_state"] for s in segments)
    segment_counts = Counter(s["source_id"] for s in segments)
    coverage_lines = [
        "coverage_kind\tcoverage_key\tsource_count\tsegment_count\tproposition_count\tevidence_link_count\tunclassified_count\tstatus\n"
    ]
    for universe_id in sorted({s["universe_id"] for s in sources}):
        selected = [s for s in sources if s["universe_id"] == universe_id]
        coverage_lines.append(
            f"universe\t{universe_id}\t{len(selected)}\t{sum(segment_counts[s['source_id']] for s in selected)}\t0\t0\t0\tPASS\n"
        )
    coverage_lines.extend([
        f"lineage\tcodex\t{len(codex_lineage)}\t{sum(segment_counts[s['source_id']] for s in codex_lineage)}\t0\t0\t0\tPASS\n",
        f"lineage\tclaude_recursive\t{len(claude_history)}\t{sum(segment_counts[s['source_id']] for s in claude_history)}\t0\t0\t0\tPASS\n",
        f"gate\tproposition_registry\t{len(sources)}\t{len(segments)}\t0\t0\t0\tPASS_EMPTY_NOT_EXTRACTED\n",
        f"gate\tmalformed_jsonl\t{len(sources)}\t{len(fragments)}\t0\t0\t0\tPASS_ALL_QUARANTINED\n",
    ])
    hashes["coverage.tsv"] = write_bytes(stage / "coverage.tsv", "".join(coverage_lines).encode())
    summary = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_id": snapshot,
        "source_count": len(sources),
        "segment_count": len(segments),
        "jsonl_fragment_count": len(fragments),
        "authority_count": len(authorities),
        "proposition_count": 0,
        "evidence_link_count": 0,
        "unclassified_source_count": sum("UNCLASSIFIED" in json.dumps(s) for s in sources),
        "unclassified_segment_count": sum("UNCLASSIFIED" in json.dumps(s) for s in segments),
        "current_codex_thread_id": CURRENT_THREAD or None,
        "current_codex_thread_sources": [s["source_id"] for s in sources if s["current_codex_thread"]],
        "codex_lineage_source_count": len(codex_lineage),
        "claude_recursive_source_count": len(claude_history),
        "root_census": roots,
        "source_role_counts": dict(sorted(role_counts.items())),
        "privacy_counts": dict(sorted(privacy_counts.items())),
        "license_counts": dict(sorted(license_counts.items())),
        "content_state_counts": dict(sorted(content_counts.items())),
        "parse_state_counts": dict(sorted(parse_counts.items())),
        "raw_content_copied": False,
        "market_payload_copied": False,
        "elapsed_seconds_operational": round(time.monotonic() - start, 3),
    }
    hashes["summary.json"] = write_bytes(stage / "summary.json", canonical_json(summary))
    receipt = {
        "schema_version": "knowledge_audit_receipt_v1",
        "status": "BUILT_PENDING_INDEPENDENT_VERIFY",
        "snapshot_id": snapshot,
        "builder_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "contract_sha256": hashlib.sha256((WORK / "AUDIT_CONTRACT.md").read_bytes()).hexdigest(),
        "source_schema_sha256": hashlib.sha256((WORK / "source_inventory.schema.json").read_bytes()).hexdigest(),
        "segment_schema_sha256": hashlib.sha256((WORK / "segment.schema.json").read_bytes()).hexdigest(),
        "proposition_schema_sha256": hashlib.sha256((WORK / "proposition.schema.json").read_bytes()).hexdigest(),
        "output_hashes": dict(sorted(hashes.items())),
        "raw_content_copied": False,
        "market_payload_copied": False,
    }
    write_bytes(stage / "build_receipt.json", canonical_json(receipt))
    dirfd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY)
    os.fsync(dirfd)
    os.close(dirfd)
    rename_noreplace(stage, output)
    parent_fd = os.open(WORK, os.O_RDONLY | os.O_DIRECTORY)
    os.fsync(parent_fd)
    os.close(parent_fd)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
