"""Pod-local advisory locks for paths that live on the network mount.

WHY (stale-network-flock, 2026-08-22): /workspace is a FUSE network volume. An
`flock` taken on one of its inodes is held by the mount's client session, so when
the pod died mid-run the lock outlived it and every successor process blocked
forever in `flock` on the same file (A1 margin-rule lanes, all six, 7+ minutes at
0.4% CPU in `request_wait_answer`). The locks this repo takes only ever serialize
processes on ONE pod, so they belong on the pod-local overlay, whose lifetime is
exactly the pod's: a restart wipes it and no stale holder can survive.

Usage (the one seam every call site uses):

    with pod_local_flock(target_path):   # target may be a file or a directory
        ...
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import os
from pathlib import Path
from typing import Iterator

LOCK_ROOT = Path("/tmp/entry_v2_pod_local_locks")


def pod_local_lock_path(target: os.PathLike[str] | str) -> Path:
    """One overlay lock file per absolute target path (sha-keyed, never on the mount)."""
    absolute = str(Path(target).resolve())
    digest = hashlib.sha256(absolute.encode()).hexdigest()[:24]
    return LOCK_ROOT / f"{digest}.lock"


@contextmanager
def pod_local_flock(target: os.PathLike[str] | str) -> Iterator[Path]:
    """Exclusive advisory lock keyed by `target`, held on the overlay, released on exit."""
    lock_path = pod_local_lock_path(target)
    LOCK_ROOT.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o666)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield lock_path
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


__all__ = ["LOCK_ROOT", "pod_local_flock", "pod_local_lock_path"]
