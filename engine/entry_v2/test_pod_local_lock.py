"""Red-first fixture for the `stale-network-flock` defect class (2026-08-22).

A pod restart left `flock` locks on /workspace (a FUSE network mount) held by the
dead pod's client; every successor process blocked forever in `flock` on the same
inode. Publication/serialization locks must therefore live on the pod-local overlay,
never on the mount: the target directory itself must stay lockable while the
publication lock is held.
"""
from __future__ import annotations

import errno
import fcntl
import os
import tempfile
import unittest
from pathlib import Path

from .durable_store import DurableEntryV2Store


def _dir_lockable(path: Path) -> bool:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return True
    except OSError as exc:
        if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
            return False
        raise
    finally:
        os.close(fd)


class PodLocalPublicationLockTest(unittest.TestCase):
    def test_publication_lock_is_not_taken_on_the_target_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            with DurableEntryV2Store._publication_lock(target):
                self.assertTrue(
                    _dir_lockable(target),
                    "publication lock was taken on the target directory itself — on the "
                    "network mount that lock outlives a dead pod (stale-network-flock)")

    def test_helper_keys_by_target_and_excludes_a_second_holder(self):
        from .pod_local_lock import LOCK_ROOT, pod_local_flock, pod_local_lock_path
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a", Path(tmp) / "b"
            a.mkdir(); b.mkdir()
            self.assertNotEqual(pod_local_lock_path(a), pod_local_lock_path(b))
            self.assertTrue(str(pod_local_lock_path(a)).startswith(str(LOCK_ROOT)))
            with pod_local_flock(a) as lock_path:
                fd = os.open(lock_path, os.O_RDWR)
                try:
                    with self.assertRaises(OSError):
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                finally:
                    os.close(fd)
            fd = os.open(lock_path, os.O_RDWR)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)


if __name__ == "__main__":
    unittest.main()
