#!/usr/bin/env python3
"""Watch ticket 47 stage progress and fail after twenty idle minutes."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
AUDIT_ROOT = ROOT / ".audit"
PROGRESS_PATH = AUDIT_ROOT / "ticket47-progress.json"
CORPUS_RECEIPT_PATH = AUDIT_ROOT / "ticket47-corpus.json"
WATCH_RECEIPT_PATH = AUDIT_ROOT / "ticket47-watch.json"
WATCH_SCHEMA = "QRE2TICKET47WATCH1"
PROGRESS_SCHEMA = "QRE2TICKET47PROGRESS1"
CORPUS_SCHEMA = "QRE2TICKET47CORPUS1"
STAGES = frozenset({"materialize", "assemble", "publish"})
STALL_SECONDS = 20 * 60
POLL_SECONDS = 5.0


@dataclass(slots=True)
class ObservedProgress:
    token: tuple[object, ...] | None = None
    changed_monotonic: float = 0.0
    launch_pid: int | None = None
    stage: str | None = None
    detail: str | None = None
    completed: int = 0
    total: int = 0


def _canonical_bytes(value: Mapping[str, object]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def _atomic_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _canonical_bytes(value)
    temporary = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    with temporary.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _read_json_object(path: Path) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read watcher input {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(
            f"watcher input must be an object, got {type(value).__name__} at {path}"
        )
    return value


def _write_watch(
    *,
    status: str,
    armed_epoch: float,
    armed_before_first_session: bool,
    observed: ObservedProgress,
    message: str,
) -> None:
    core: dict[str, object] = {
        "schema": WATCH_SCHEMA,
        "status": status,
        "watcher_pid": os.getpid(),
        "launch_pid": observed.launch_pid,
        "stage": observed.stage,
        "detail": observed.detail,
        "completed": observed.completed,
        "total": observed.total,
        "armed_epoch": armed_epoch,
        "armed_before_first_session": armed_before_first_session,
        "tripwire_seconds": STALL_SECONDS,
        "poll_seconds": POLL_SECONDS,
        "message": message,
        "updated_epoch": time.time(),
    }
    core["receipt_sha256"] = hashlib.sha256(_canonical_bytes(core)).hexdigest()
    _atomic_json(WATCH_RECEIPT_PATH, core)


def _progress_token(value: Mapping[str, object]) -> tuple[object, ...]:
    return (
        value.get("pid"),
        value.get("stage"),
        value.get("sequence"),
        value.get("completed"),
        value.get("detail"),
        value.get("status"),
    )


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _completed_receipt(armed_epoch: float) -> Mapping[str, object] | None:
    if not CORPUS_RECEIPT_PATH.is_file():
        return None
    value = _read_json_object(CORPUS_RECEIPT_PATH)
    if value.get("schema") != CORPUS_SCHEMA or value.get("status") != "PASS":
        raise RuntimeError(
            f"ticket 47 corpus receipt identity differs at {CORPUS_RECEIPT_PATH}"
        )
    if float(value.get("completed_epoch", -1.0)) < armed_epoch:
        return None
    return value


def _fresh_progress(armed_epoch: float) -> Mapping[str, object] | None:
    if not PROGRESS_PATH.is_file():
        return None
    value = _read_json_object(PROGRESS_PATH)
    updated = float(value.get("updated_epoch", -1.0))
    if updated < armed_epoch:
        return None
    if value.get("schema") != PROGRESS_SCHEMA:
        raise RuntimeError(
            f"ticket 47 progress schema differs at {PROGRESS_PATH}"
        )
    return value


def _observe(
    value: Mapping[str, object],
    observed: ObservedProgress,
    now: float,
) -> None:
    stage = str(value.get("stage"))
    if stage not in STAGES:
        raise RuntimeError(
            f"ticket 47 progress stage must be one of {sorted(STAGES)}, got {stage!r}"
        )
    launch_pid = int(value.get("pid", -1))
    completed = int(value.get("completed", -1))
    total = int(value.get("total", -1))
    if launch_pid <= 0 or completed < 0 or total < 0:
        raise RuntimeError(
            f"ticket 47 progress counters differ, "
            f"pid={launch_pid} completed={completed} total={total}"
        )
    token = _progress_token(value)
    if token != observed.token:
        observed.token = token
        observed.changed_monotonic = now
    observed.launch_pid = launch_pid
    observed.stage = stage
    observed.detail = str(value.get("detail"))
    observed.completed = completed
    observed.total = total


def _selftest() -> int:
    progress = {
        "schema": PROGRESS_SCHEMA,
        "status": "RUNNING",
        "pid": 123,
        "stage": "materialize",
        "detail": "HG/20220102",
        "completed": 1,
        "total": 1,
        "sequence": 2,
        "updated_epoch": 10.0,
    }
    observed = ObservedProgress(changed_monotonic=1.0)
    _observe(progress, observed, 2.0)
    if (
        observed.stage != "materialize"
        or observed.completed != 1
        or observed.changed_monotonic != 2.0
    ):
        raise AssertionError(f"watch progress selftest differs, got {observed}")
    if 1203.0 - observed.changed_monotonic <= STALL_SECONDS:
        raise AssertionError("watch tripwire selftest did not cross twenty minutes")
    with tempfile.TemporaryDirectory(
        dir=AUDIT_ROOT,
        prefix="ticket47-watch-selftest-",
    ) as raw:
        path = Path(raw) / "watch.json"
        _atomic_json(path, progress)
        stored = _read_json_object(path)
        if stored != progress:
            raise AssertionError(
                f"watch receipt strict reload selftest differs, got {stored}"
            )
    print("selftest_ok")
    return 0


def _run() -> int:
    armed_epoch = time.time()
    armed_before_first_session = _fresh_progress(armed_epoch) is None
    observed = ObservedProgress(changed_monotonic=time.monotonic())
    _write_watch(
        status="ARMED",
        armed_epoch=armed_epoch,
        armed_before_first_session=armed_before_first_session,
        observed=observed,
        message="D-074 stage tripwire is armed.",
    )
    print(
        json.dumps(
            {
                "receipt": str(WATCH_RECEIPT_PATH),
                "status": "ARMED",
                "tripwire_seconds": STALL_SECONDS,
            },
            sort_keys=True,
        ),
        flush=True,
    )

    while True:
        completed = _completed_receipt(armed_epoch)
        if completed is not None:
            _write_watch(
                status="COMPLETE",
                armed_epoch=armed_epoch,
                armed_before_first_session=armed_before_first_session,
                observed=observed,
                message=f"Ticket 47 completed at {CORPUS_RECEIPT_PATH}.",
            )
            return 0

        progress = _fresh_progress(armed_epoch)
        if progress is None:
            now = time.monotonic()
            idle_seconds = now - observed.changed_monotonic
            if idle_seconds >= STALL_SECONDS:
                message = (
                    "ticket 47 launch produced no fresh progress for "
                    f"{idle_seconds:.1f} seconds"
                )
                _write_watch(
                    status="TRIPPED",
                    armed_epoch=armed_epoch,
                    armed_before_first_session=armed_before_first_session,
                    observed=observed,
                    message=message,
                )
                print(message, file=sys.stderr, flush=True)
                return 1
            time.sleep(POLL_SECONDS)
            continue
        now = time.monotonic()
        _observe(progress, observed, now)
        progress_status = str(progress.get("status"))
        if progress_status == "FAILED":
            message = str(progress.get("error", "ticket 47 launch failed"))
            _write_watch(
                status="RUN_FAILED",
                armed_epoch=armed_epoch,
                armed_before_first_session=armed_before_first_session,
                observed=observed,
                message=message,
            )
            print(message, file=sys.stderr, flush=True)
            return 1
        if progress_status == "COMPLETE":
            message = (
                f"launch reported completion without {CORPUS_RECEIPT_PATH}"
            )
            _write_watch(
                status="RUN_FAILED",
                armed_epoch=armed_epoch,
                armed_before_first_session=armed_before_first_session,
                observed=observed,
                message=message,
            )
            print(message, file=sys.stderr, flush=True)
            return 1
        if observed.launch_pid is not None and not _pid_alive(
            observed.launch_pid
        ):
            message = (
                f"ticket 47 launch pid {observed.launch_pid} exited before "
                f"publishing {CORPUS_RECEIPT_PATH}"
            )
            _write_watch(
                status="RUN_FAILED",
                armed_epoch=armed_epoch,
                armed_before_first_session=armed_before_first_session,
                observed=observed,
                message=message,
            )
            print(message, file=sys.stderr, flush=True)
            return 1
        idle_seconds = now - observed.changed_monotonic
        if idle_seconds >= STALL_SECONDS:
            message = (
                f"ticket 47 stage {observed.stage} made no progress for "
                f"{idle_seconds:.1f} seconds at {observed.detail}"
            )
            _write_watch(
                status="TRIPPED",
                armed_epoch=armed_epoch,
                armed_before_first_session=armed_before_first_session,
                observed=observed,
                message=message,
            )
            print(message, file=sys.stderr, flush=True)
            return 1
        _write_watch(
            status="WATCHING",
            armed_epoch=armed_epoch,
            armed_before_first_session=armed_before_first_session,
            observed=observed,
            message=(
                f"Watching stage {observed.stage} at {observed.detail}."
            ),
        )
        time.sleep(POLL_SECONDS)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Watch the ticket 47 corpus build for stalled stages."
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="Run watcher contract checks without observing a live process.",
    )
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    return _run()


if __name__ == "__main__":
    raise SystemExit(main())
