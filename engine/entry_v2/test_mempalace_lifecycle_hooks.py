from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

from engine.entry_v2 import mempalace_precompact_hook as precompact
from engine.entry_v2 import mempalace_session_end_hook as session_end


def test_precompact_success_is_visible_and_hub_reconciled(monkeypatch):
    receipt = {
        "status": "spooled",
        "spool_file": "session.hash.json",
        "checkpoint_sha256": "1234567890abcdef",
    }

    monkeypatch.setattr(
        precompact,
        "capture_precompact",
        lambda payload: ({}, Path("unused"), dict(receipt)),
    )
    monkeypatch.setattr(
        precompact,
        "reconcile_pending",
        lambda limit: [
            {
                "status": "reconciled",
                "spool_file": "session.hash.json",
            }
        ],
    )

    output, actual = precompact.run({"session_id": "session"})

    assert output["suppressOutput"] is False
    assert "MemPalace PreCompact checkpoint captured" in output["systemMessage"]
    assert "hub-reconciled" in output["systemMessage"]
    assert "1234567890ab" in output["systemMessage"]
    assert actual["palace_reconciled"] is True


def test_session_end_worker_spools_then_uses_exact_hub_forwarded_mine(tmp_path, monkeypatch):
    monkeypatch.setattr(session_end, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(session_end, "LOG_PATH", tmp_path / "state" / "hook.log")
    transcript = tmp_path / "rollout.jsonl"
    transcript.write_text("{}\n", encoding="utf-8")
    spool_path = tmp_path / "spool.json"
    archived_transcript = tmp_path / "archive" / "session.jsonl"
    seen = {}

    def capture(payload):
        seen["capture_payload"] = dict(payload)
        return (
            {"transcript_path": str(transcript)},
            spool_path,
            {
                "status": "spooled",
                "spool_file": spool_path.name,
                "checkpoint_sha256": "abc",
            },
        )

    def reconcile(path):
        seen["reconcile_path"] = path
        return {"status": "reconciled"}

    def runner(command, **kwargs):
        seen["command"] = command
        seen["runner_kwargs"] = kwargs
        return SimpleNamespace(returncode=0)

    def archive(payload, record):
        seen["archive_payload"] = dict(payload)
        seen["archive_record"] = dict(record)
        return {
            "archive_path": str(archived_transcript),
            "archive_receipt_path": str(archived_transcript) + ".receipt.json",
            "archive_sha256": "def",
            "archive_bytes": 3,
            "continuity_scan_match": True,
            "replaced_existing": False,
        }

    receipt = session_end.worker_run(
        {
            "session_id": "session-1",
            "transcript_path": str(transcript),
            "reason": "other",
        },
        capture=capture,
        reconcile=reconcile,
        hub_probe=lambda: {"pid": 42},
        runner=runner,
        archive=archive,
    )

    assert seen["capture_payload"]["hook_event_name"] == "SessionEnd"
    assert seen["capture_payload"]["trigger"] == "other"
    assert seen["reconcile_path"] == spool_path
    assert seen["command"] == [
        session_end.sys.executable,
        "-m",
        "mempalace",
        "mine",
        str(archived_transcript),
        "--mode",
        "convos",
        "--wing",
        "sessions",
        "--agent",
        "codex",
    ]
    assert seen["runner_kwargs"]["env"]["MEMPALACE_HUB_FORWARD"] == "1"
    assert seen["archive_payload"]["session_id"] == "session-1"
    assert seen["archive_record"]["transcript_path"] == str(transcript)
    assert receipt["status"] == "complete"
    assert receipt["palace_reconciled"] is True
    assert receipt["mine_status"] == "complete"
    assert receipt["hub_pid"] == 42
    assert receipt["archive_path"] == str(archived_transcript)
    assert receipt["archive_sha256"] == "def"


def test_session_end_worker_fails_closed_without_hub(tmp_path, monkeypatch):
    monkeypatch.setattr(session_end, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(session_end, "LOG_PATH", tmp_path / "state" / "hook.log")

    def runner(*args, **kwargs):
        raise AssertionError("a hub-less hook must not start a direct ChromaDB mine")

    receipt = session_end.worker_run(
        {"session_id": "session-1", "transcript_path": str(tmp_path / "rollout.jsonl")},
        capture=lambda payload: (
            {"transcript_path": str(tmp_path / "rollout.jsonl")},
            tmp_path / "spool.json",
            {"status": "spooled", "checkpoint_sha256": "abc"},
        ),
        reconcile=lambda path: {"status": "http_hub_unavailable"},
        hub_probe=lambda: None,
        runner=runner,
        archive=lambda payload, record: {
            "archive_path": str(tmp_path / "archive.jsonl"),
            "archive_receipt_path": str(tmp_path / "archive.jsonl.receipt.json"),
            "archive_sha256": "def",
            "archive_bytes": 3,
            "continuity_scan_match": True,
            "replaced_existing": False,
        },
    )

    assert receipt["status"] == "spooled_hub_unavailable"
    assert receipt["mine_status"] == "not_started"
    assert receipt["palace_reconciled"] is False
    assert receipt["archive_status"] == "complete"


def test_session_end_exact_archive_hash_stable_path_and_atomic_replace(
    tmp_path, monkeypatch
):
    source_root = tmp_path / "codex-home"
    source_root.mkdir()
    source = source_root / "rollout.jsonl"
    first_bytes = b'{"type":"session_meta"}\n\x00raw-tool-evidence\n'
    source.write_bytes(first_bytes)
    archive_root = tmp_path / "workspace-palace" / "sources" / "codex"
    monkeypatch.setattr(session_end, "ARCHIVE_ROOT", archive_root)
    monkeypatch.setenv("MEMPALACE_CONTINUITY_ALLOWED_ROOTS", str(source_root))
    payload = {
        "session_id": "../../unsafe session/id",
        "transcript_path": str(source),
    }

    first = session_end.archive_transcript(
        payload,
        {"transcript_sha256": hashlib.sha256(first_bytes).hexdigest()},
    )
    archived_path = Path(first["archive_path"])
    assert archived_path.parent == archive_root
    assert ".." not in archived_path.name
    assert archived_path.read_bytes() == first_bytes
    assert first["archive_sha256"] == hashlib.sha256(first_bytes).hexdigest()
    assert first["archive_bytes"] == len(first_bytes)
    assert first["continuity_scan_match"] is True
    assert first["replaced_existing"] is False
    receipt = json.loads(Path(first["archive_receipt_path"]).read_text(encoding="utf-8"))
    assert receipt["archive_sha256"] == first["archive_sha256"]
    assert receipt["archive_bytes"] == len(first_bytes)

    second_bytes = b'{"type":"session_meta"}\nreplacement snapshot\n'
    source.write_bytes(second_bytes)
    second = session_end.archive_transcript(
        payload,
        {"transcript_sha256": hashlib.sha256(second_bytes).hexdigest()},
    )
    assert second["archive_path"] == first["archive_path"]
    assert archived_path.read_bytes() == second_bytes
    assert second["archive_sha256"] == hashlib.sha256(second_bytes).hexdigest()
    assert second["replaced_existing"] is True
    assert not list(archive_root.glob("*.tmp"))
    assert not [name for name in os.listdir(archive_root) if name.startswith(".")]


def test_session_end_archive_rejects_source_and_target_symlinks(tmp_path, monkeypatch):
    source_root = tmp_path / "codex-home"
    source_root.mkdir()
    real_source = source_root / "real.jsonl"
    real_source.write_text("{}\n", encoding="utf-8")
    linked_source = source_root / "linked.jsonl"
    linked_source.symlink_to(real_source)
    monkeypatch.setenv("MEMPALACE_CONTINUITY_ALLOWED_ROOTS", str(source_root))
    monkeypatch.setattr(
        session_end,
        "ARCHIVE_ROOT",
        tmp_path / "workspace-palace" / "sources" / "codex",
    )

    try:
        session_end.archive_transcript(
            {"session_id": "session", "transcript_path": str(linked_source)}, {}
        )
    except ValueError as exc:
        assert "symlink" in str(exc)
    else:
        raise AssertionError("source symlink must be rejected")

    target_parent = tmp_path / "target-parent"
    target_parent.mkdir()
    redirected = tmp_path / "redirected"
    redirected.mkdir()
    (target_parent / "sources").symlink_to(redirected, target_is_directory=True)
    monkeypatch.setattr(session_end, "ARCHIVE_ROOT", target_parent / "sources" / "codex")

    try:
        session_end.archive_transcript(
            {"session_id": "session", "transcript_path": str(real_source)}, {}
        )
    except ValueError as exc:
        assert "symlink" in str(exc)
    else:
        raise AssertionError("target path symlink must be rejected")


def test_session_end_archive_distinguishes_two_sources_with_same_session_id(
    tmp_path, monkeypatch
):
    source_root = tmp_path / "codex-home"
    source_root.mkdir()
    root_source = source_root / "root.jsonl"
    child_source = source_root / "child.jsonl"
    root_source.write_bytes(b"root transcript\n")
    child_source.write_bytes(b"child transcript\n")
    archive_root = tmp_path / "workspace-palace" / "sources" / "codex"
    monkeypatch.setattr(session_end, "ARCHIVE_ROOT", archive_root)
    monkeypatch.setenv("MEMPALACE_CONTINUITY_ALLOWED_ROOTS", str(source_root))

    root_receipt = session_end.archive_transcript(
        {"session_id": "shared-session", "transcript_path": str(root_source)}, {}
    )
    child_receipt = session_end.archive_transcript(
        {"session_id": "shared-session", "transcript_path": str(child_source)}, {}
    )

    assert root_receipt["archive_path"] != child_receipt["archive_path"]
    assert Path(root_receipt["archive_path"]).read_bytes() == b"root transcript\n"
    assert Path(child_receipt["archive_path"]).read_bytes() == b"child transcript\n"


def test_session_end_archive_retries_one_unstable_snapshot(tmp_path, monkeypatch):
    source_root = tmp_path / "codex-home"
    source_root.mkdir()
    source = source_root / "rollout.jsonl"
    source_bytes = b"stable bytes after retry\n"
    source.write_bytes(source_bytes)
    archive_root = tmp_path / "workspace-palace" / "sources" / "codex"
    monkeypatch.setattr(session_end, "ARCHIVE_ROOT", archive_root)
    monkeypatch.setenv("MEMPALACE_CONTINUITY_ALLOWED_ROOTS", str(source_root))
    real_fstat = session_end.os.fstat
    source_fstat_calls = 0

    def one_unstable_fstat(fd):
        nonlocal source_fstat_calls
        info = real_fstat(fd)
        if stat_is_regular(info.st_mode):
            source_fstat_calls += 1
            if source_fstat_calls == 2:
                return SimpleNamespace(
                    st_mode=info.st_mode,
                    st_dev=info.st_dev,
                    st_ino=info.st_ino,
                    st_size=info.st_size,
                    st_mtime_ns=info.st_mtime_ns + 1,
                    st_ctime_ns=info.st_ctime_ns,
                )
        return info

    # Avoid importing stat solely in the test; the production module owns the
    # exact regular-file predicate being exercised.
    stat_is_regular = session_end.stat.S_ISREG
    monkeypatch.setattr(session_end.os, "fstat", one_unstable_fstat)

    receipt = session_end.archive_transcript(
        {"session_id": "session", "transcript_path": str(source)}, {}
    )

    assert source_fstat_calls == 4
    assert Path(receipt["archive_path"]).read_bytes() == source_bytes
    assert not [name for name in os.listdir(archive_root) if name.startswith(".")]


def test_session_end_archive_refuses_two_unstable_snapshots(tmp_path, monkeypatch):
    source_root = tmp_path / "codex-home"
    source_root.mkdir()
    source = source_root / "rollout.jsonl"
    source.write_bytes(b"changing transcript\n")
    archive_root = tmp_path / "workspace-palace" / "sources" / "codex"
    monkeypatch.setattr(session_end, "ARCHIVE_ROOT", archive_root)
    monkeypatch.setenv("MEMPALACE_CONTINUITY_ALLOWED_ROOTS", str(source_root))
    real_fstat = session_end.os.fstat
    source_fstat_calls = 0

    def always_unstable_fstat(fd):
        nonlocal source_fstat_calls
        info = real_fstat(fd)
        if session_end.stat.S_ISREG(info.st_mode):
            source_fstat_calls += 1
            if source_fstat_calls % 2 == 0:
                return SimpleNamespace(
                    st_mode=info.st_mode,
                    st_dev=info.st_dev,
                    st_ino=info.st_ino,
                    st_size=info.st_size,
                    st_mtime_ns=info.st_mtime_ns + 1,
                    st_ctime_ns=info.st_ctime_ns,
                )
        return info

    monkeypatch.setattr(session_end.os, "fstat", always_unstable_fstat)

    try:
        session_end.archive_transcript(
            {"session_id": "session", "transcript_path": str(source)}, {}
        )
    except RuntimeError as exc:
        assert "changed during archive copy" in str(exc)
    else:
        raise AssertionError("two unstable snapshots must fail closed")

    assert source_fstat_calls == 4
    assert not list(archive_root.glob("*.jsonl"))
    assert not [name for name in os.listdir(archive_root) if name.startswith(".")]
