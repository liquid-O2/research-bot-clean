"""Detached Codex ``SessionEnd`` continuity capture for MemPalace.

The foreground hook only copies its small JSON payload into a detached worker
and returns.  The worker atomically captures the final bounded continuity
spool, reconciles it through the live HTTP hub, archives the exact authoritative
Codex JSONL under ``/workspace``, then runs the official conversation mine over
that stable archive.  MemPalace's Codex adapter admits only authored messages;
tool/reasoning telemetry remains available in the raw audit archive without
entering semantic drawers.  MemPalace 3.7.1 auto-forwards the CLI mine to the
hub, which remains the sole owner of the ChromaDB writer lease.
"""

from __future__ import annotations

import ipaddress
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:
    from .mempalace_continuity_spool import capture_precompact
    from .mempalace_continuity_spool import reconcile_path
    from .mempalace_continuity_spool import validate_transcript_path
except ImportError:  # Executed as an absolute script by Codex.
    from mempalace_continuity_spool import capture_precompact
    from mempalace_continuity_spool import reconcile_path
    from mempalace_continuity_spool import validate_transcript_path


MEMPALACE_WORKSPACE_ROOT = Path("/workspace/.mempalace")
STATE_DIR = MEMPALACE_WORKSPACE_ROOT / "hook_state"
LOG_PATH = STATE_DIR / "hook.log"
ARCHIVE_ROOT = MEMPALACE_WORKSPACE_ROOT / "sources" / "codex"
ARCHIVE_SCHEMA_VERSION = 1
_ARCHIVE_SLUG_RE = re.compile(r"[^A-Za-z0-9_-]+")

Capture = Callable[..., tuple[dict[str, Any], Path, dict[str, Any]]]
Reconciler = Callable[[Path], Mapping[str, Any]]
HubProbe = Callable[[], Mapping[str, Any] | None]
Runner = Callable[..., Any]
Archiver = Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]


def _reject_symlink_components(path: Path) -> None:
    """Reject an existing symlink anywhere in an archive target path."""

    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode):
            raise ValueError("archive path contains a symlink")


def _prepare_archive_root() -> Path:
    root = ARCHIVE_ROOT
    if not root.is_absolute():
        raise ValueError("archive root must be absolute")
    _reject_symlink_components(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    _reject_symlink_components(root)
    os.chmod(root, 0o700)
    return root.resolve(strict=True)


def _archive_basename(payload: Mapping[str, Any], source: Path) -> str:
    session_id = payload.get("session_id")
    raw_session_id = session_id if isinstance(session_id, str) else ""
    # Subagents can reuse the root session_id while writing distinct rollout
    # files.  Bind both values so no child transcript can replace its parent.
    identity = f"session:{raw_session_id}\0source:{source}"
    label = raw_session_id or source.stem
    slug = _ARCHIVE_SLUG_RE.sub("-", label).strip("-_")[:64] or "codex-session"
    identity_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"{slug}.{identity_hash}.jsonl"


class _TranscriptChangedDuringCopy(RuntimeError):
    pass


def _source_fingerprint(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        int(info.st_dev),
        int(info.st_ino),
        int(info.st_size),
        int(info.st_mtime_ns),
        int(info.st_ctime_ns),
    )


def _copy_stable_once(source: Path, destination: Path, root: Path) -> tuple[str, int]:
    """Copy one source snapshot, refusing replacement if it changed mid-read."""

    source_fd = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    temp_fd = -1
    temp_name = ""
    digest = hashlib.sha256()
    bytes_archived = 0
    try:
        before = os.fstat(source_fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("transcript is not a regular file")
        temp_fd, temp_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=root
        )
        os.fchmod(temp_fd, 0o600)
        with os.fdopen(source_fd, "rb", closefd=True) as source_handle:
            source_fd = -1
            with os.fdopen(temp_fd, "wb", closefd=True) as archive_handle:
                temp_fd = -1
                for chunk in iter(lambda: source_handle.read(1024 * 1024), b""):
                    archive_handle.write(chunk)
                    digest.update(chunk)
                    bytes_archived += len(chunk)
                after = os.fstat(source_handle.fileno())
                path_after = source.lstat()
                if (
                    _source_fingerprint(before) != _source_fingerprint(after)
                    or _source_fingerprint(after) != _source_fingerprint(path_after)
                    or bytes_archived != before.st_size
                ):
                    raise _TranscriptChangedDuringCopy(
                        "transcript changed during archive copy"
                    )
                archive_handle.flush()
                os.fsync(archive_handle.fileno())
        os.replace(temp_name, destination)
        temp_name = ""
        os.chmod(destination, 0o600)
        return digest.hexdigest(), bytes_archived
    finally:
        if source_fd != -1:
            os.close(source_fd)
        if temp_fd != -1:
            os.close(temp_fd)
        if temp_name:
            try:
                os.unlink(temp_name)
            except OSError:
                pass


def _atomic_write_receipt(path: Path, value: Mapping[str, Any]) -> None:
    encoded = (json.dumps(dict(value), sort_keys=True) + "\n").encode("utf-8")
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=True) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def archive_transcript(
    payload: Mapping[str, Any],
    continuity_record: Mapping[str, Any],
) -> dict[str, Any]:
    """Atomically archive an exact, unhashed-by-content Codex JSONL snapshot.

    The destination identity is stable per Codex session, so a retry replaces
    the same source instead of creating duplicate MemPalace source identities.
    Source and destination symlinks are rejected; the caller mines only the
    returned archive path.
    """

    raw_source = payload.get("transcript_path") or continuity_record.get("transcript_path")
    if not isinstance(raw_source, str) or not raw_source:
        raise ValueError("missing transcript path")
    unresolved_source = Path(raw_source).expanduser()
    if ".." in unresolved_source.parts:
        raise ValueError("unsafe transcript path")
    _reject_symlink_components(unresolved_source)
    source_info = unresolved_source.lstat()
    if stat.S_ISLNK(source_info.st_mode) or not stat.S_ISREG(source_info.st_mode):
        raise ValueError("transcript must be a non-symlink regular file")
    source = validate_transcript_path(raw_source)

    root = _prepare_archive_root()
    destination = root / _archive_basename(payload, source)
    if destination.parent != root or destination.name in {"", ".", ".."}:
        raise ValueError("unsafe archive destination")
    if destination.is_symlink():
        raise ValueError("archive destination is a symlink")

    replaced_existing = destination.exists()
    for attempt in range(2):
        try:
            archive_sha256, bytes_archived = _copy_stable_once(
                source, destination, root
            )
            break
        except _TranscriptChangedDuringCopy:
            if attempt == 1:
                raise
    expected_sha256 = continuity_record.get("transcript_sha256")
    source_hash_match = (
        expected_sha256 == archive_sha256
        if isinstance(expected_sha256, str) and expected_sha256
        else None
    )
    receipt_path = destination.with_name(destination.name + ".receipt.json")
    if receipt_path.is_symlink():
        raise ValueError("archive receipt destination is a symlink")
    receipt = {
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "storage": "codex_raw_archive",
        "archived_at": datetime.now().astimezone().isoformat(),
        "session_key": destination.stem,
        "source_basename": source.name,
        "source_path_sha256": hashlib.sha256(str(source).encode("utf-8")).hexdigest(),
        "archive_path": str(destination),
        "archive_sha256": archive_sha256,
        "archive_bytes": bytes_archived,
        "continuity_scan_sha256": expected_sha256,
        "continuity_scan_match": source_hash_match,
        "replaced_existing": replaced_existing,
    }
    _atomic_write_receipt(receipt_path, receipt)
    try:
        directory_fd = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError:
        pass
    receipt["archive_receipt_path"] = str(receipt_path)
    return receipt


def _log_receipt(kind: str, receipt: Mapping[str, Any]) -> None:
    """Append content-free lifecycle evidence without touching ChromaDB."""

    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(STATE_DIR, 0o700)
        encoded = (
            f"[{datetime.now().strftime('%H:%M:%S')}] CONTINUITY {kind} "
            + json.dumps(dict(receipt), sort_keys=True)
            + "\n"
        ).encode("utf-8")
        fd = os.open(LOG_PATH, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, encoded)
        finally:
            os.close(fd)
    except OSError:
        pass


def _live_loopback_hub() -> Mapping[str, Any] | None:
    """Return the official live writable loopback-hub record, else ``None``."""

    from mempalace import server_registry
    from mempalace.config import MempalaceConfig

    palace_path = MempalaceConfig().palace_path
    info = server_registry.read_live_serverinfo(palace_path)
    if not info or info.get("read_only"):
        return None
    base_url = server_registry.client_base_url(info)
    hostname = (urlsplit(base_url).hostname or "").lower()
    if hostname != "localhost":
        try:
            if not ipaddress.ip_address(hostname).is_loopback:
                return None
        except ValueError:
            return None
    try:
        request = urllib.request.Request(f"{base_url}/healthz")
        with urllib.request.urlopen(request, timeout=0.75) as response:
            if response.status != 200:
                return None
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        return None
    return info


def worker_run(
    payload: Mapping[str, Any],
    *,
    capture: Capture = capture_precompact,
    reconcile: Reconciler = reconcile_path,
    hub_probe: HubProbe = _live_loopback_hub,
    runner: Runner = subprocess.run,
    archive: Archiver = archive_transcript,
) -> dict[str, Any]:
    """Capture, hub-reconcile, archive, and mine one ended Codex transcript."""

    final_payload = dict(payload)
    final_payload["hook_event_name"] = "SessionEnd"
    final_payload["trigger"] = str(payload.get("reason") or payload.get("trigger") or "other")

    try:
        record, spool_path, receipt = capture(final_payload)
    except Exception as exc:
        return {
            "status": "spool_failed",
            "error_type": type(exc).__name__,
            "session_id": str(payload.get("session_id") or ""),
            "mine_status": "not_started",
        }

    try:
        reconciliation = dict(reconcile(spool_path))
    except Exception as exc:
        reconciliation = {
            "status": "reconcile_failed",
            "error_type": type(exc).__name__,
        }
    receipt.update(
        event="SessionEnd",
        reconcile_status=str(reconciliation.get("status") or "unknown"),
        palace_reconciled=reconciliation.get("status") in {
            "reconciled",
            "already_reconciled",
        },
    )

    try:
        archive_receipt = dict(archive(payload, record))
    except Exception as exc:
        receipt.update(
            status="archive_failed",
            archive_status="failed",
            archive_error_type=type(exc).__name__,
            mine_status="not_started",
        )
        return receipt
    receipt.update(
        archive_status="complete",
        archive_path=archive_receipt.get("archive_path"),
        archive_receipt_path=archive_receipt.get("archive_receipt_path"),
        archive_sha256=archive_receipt.get("archive_sha256"),
        archive_bytes=archive_receipt.get("archive_bytes"),
        archive_replaced_existing=archive_receipt.get("replaced_existing"),
        archive_continuity_scan_match=archive_receipt.get("continuity_scan_match"),
    )

    try:
        hub = hub_probe()
    except Exception:
        hub = None
    if hub is None:
        receipt.update(status="spooled_hub_unavailable", mine_status="not_started")
        return receipt

    transcript_path = str(archive_receipt["archive_path"])
    command = [
        sys.executable,
        "-m",
        "mempalace",
        "mine",
        transcript_path,
        "--mode",
        "convos",
        "--wing",
        "sessions",
        "--agent",
        "codex",
    ]
    child_env = os.environ.copy()
    # Any false-like value disables 3.7.1's official CLI hub forwarder.
    child_env["MEMPALACE_HUB_FORWARD"] = "1"
    # The raw Codex audit stream can exceed MemPalace's conservative 500 MB
    # default even when the clean authored-message view is tiny.  This host has
    # ample RAM and archives a stable copy first, so permit up to 4 GiB.
    child_env["MEMPALACE_MAX_CONVO_FILE_BYTES"] = str(4 * 1024 * 1024 * 1024)
    STATE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        with LOG_PATH.open("ab") as log_file:
            try:
                os.chmod(LOG_PATH, 0o600)
            except OSError:
                pass
            completed = runner(
                command,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=log_file,
                env=child_env,
                check=False,
            )
    except Exception as exc:
        receipt.update(
            status="mine_launch_failed",
            mine_status="not_started",
            mine_error_type=type(exc).__name__,
            hub_pid=hub.get("pid"),
        )
        return receipt
    return_code = int(getattr(completed, "returncode", 1))
    receipt.update(
        status="complete" if return_code == 0 else "mine_failed",
        mine_status="complete" if return_code == 0 else "failed",
        mine_returncode=return_code,
        hub_pid=hub.get("pid"),
    )
    return receipt


def _launch_worker(payload: Mapping[str, Any]) -> int:
    """Start a detached worker after copying the hook payload into its pipe."""

    STATE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    with LOG_PATH.open("ab") as log_file:
        try:
            os.chmod(LOG_PATH, 0o600)
        except OSError:
            pass
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--worker"],
            stdin=subprocess.PIPE,
            stdout=log_file,
            stderr=log_file,
            close_fds=True,
            start_new_session=True,
        )
        assert process.stdin is not None
        try:
            process.stdin.write(json.dumps(dict(payload), ensure_ascii=False).encode("utf-8"))
            process.stdin.close()
        except Exception:
            process.stdin.close()
            raise
    return process.pid


def _emit(output: Mapping[str, Any]) -> None:
    encoded = (json.dumps(dict(output), ensure_ascii=False) + "\n").encode("utf-8")
    os.write(1, encoded)


def _read_payload() -> Mapping[str, Any]:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return {}
    return payload if isinstance(payload, Mapping) else {}


def main() -> int:
    payload = _read_payload()
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        receipt = worker_run(payload)
        _log_receipt("SESSIONEND", receipt)
        return 0 if receipt.get("status") == "complete" else 1

    try:
        pid = _launch_worker(payload)
    except Exception as exc:
        receipt = {
            "status": "worker_launch_failed",
            "error_type": type(exc).__name__,
            "session_id": str(payload.get("session_id") or ""),
        }
        _log_receipt("SESSIONEND-LAUNCH", receipt)
        _emit(
            {
                "systemMessage": "MemPalace final checkpoint worker failed to launch.",
                "suppressOutput": False,
            }
        )
        return 1

    _log_receipt(
        "SESSIONEND-LAUNCH",
        {
            "status": "worker_launched",
            "session_id": str(payload.get("session_id") or ""),
            "worker_pid": pid,
        },
    )
    _emit({"suppressOutput": True})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
