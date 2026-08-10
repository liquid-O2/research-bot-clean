#!/usr/bin/env python3
"""No-follow recursive content identity for manifest-authorized retirement.

The identity is intentionally expensive: every regular file beneath a
directory is hashed from a stable file descriptor, every path/type/mode and
lstat identity enters a canonical Merkle stream, and every directory must be
unchanged across its scan. This prevents a nested post-vault write from being
silently deleted merely because a top-level inode and child count stayed the
same.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path


def _stat_tuple(st: os.stat_result) -> tuple[int, ...]:
    return (
        st.st_mode,
        st.st_uid,
        st.st_gid,
        st.st_size,
        st.st_dev,
        st.st_ino,
        st.st_nlink,
        st.st_mtime_ns,
        st.st_ctime_ns,
    )


def _sha256_regular(path: Path, expected: os.stat_result) -> str:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or _stat_tuple(before) != _stat_tuple(expected):
            raise RuntimeError(f"regular-file identity changed before read: {path}")
        h = hashlib.sha256()
        while chunk := os.read(fd, 8 * 1024 * 1024):
            h.update(chunk)
        after = os.fstat(fd)
        if _stat_tuple(after) != _stat_tuple(before):
            raise RuntimeError(f"regular-file identity changed during read: {path}")
        return h.hexdigest()
    finally:
        os.close(fd)


def identity(path: Path) -> str:
    path = Path(path)
    root = path.lstat()
    if stat.S_ISREG(root.st_mode):
        return (
            f"file:bytes={root.st_size}:sha256={_sha256_regular(path, root)}:"
            f"mode={stat.S_IMODE(root.st_mode):o}:dev={root.st_dev}:ino={root.st_ino}:"
            f"mtime_ns={root.st_mtime_ns}:ctime_ns={root.st_ctime_ns}"
        )
    if stat.S_ISLNK(root.st_mode):
        return (
            f"symlink:target={os.readlink(path)}:mode={stat.S_IMODE(root.st_mode):o}:"
            f"dev={root.st_dev}:ino={root.st_ino}:mtime_ns={root.st_mtime_ns}:"
            f"ctime_ns={root.st_ctime_ns}"
        )
    if not stat.S_ISDIR(root.st_mode):
        return (
            f"other:mode={root.st_mode:o}:dev={root.st_dev}:ino={root.st_ino}:"
            f"mtime_ns={root.st_mtime_ns}:ctime_ns={root.st_ctime_ns}"
        )

    stream = hashlib.sha256()
    entries = 0
    regular_bytes = 0
    file_hash_cache: dict[tuple[int, ...], str] = {}

    def emit(fields: list[object]) -> None:
        nonlocal entries
        encoded = json.dumps(fields, ensure_ascii=True, separators=(",", ":")) + "\n"
        stream.update(encoded.encode("ascii"))
        entries += 1

    def visit(directory: Path, relative: str) -> None:
        nonlocal regular_bytes
        before = directory.lstat()
        if not stat.S_ISDIR(before.st_mode):
            raise RuntimeError(f"directory replaced before scan: {directory}")
        emit(
            [
                "D",
                relative or ".",
                f"{stat.S_IMODE(before.st_mode):o}",
                before.st_uid,
                before.st_gid,
                before.st_dev,
                before.st_ino,
                before.st_nlink,
                before.st_mtime_ns,
                before.st_ctime_ns,
            ]
        )
        with os.scandir(directory) as iterator:
            children = sorted(list(iterator), key=lambda item: os.fsencode(item.name))
        for child in children:
            child_path = directory / child.name
            child_rel = child.name if not relative else f"{relative}/{child.name}"
            st = child_path.lstat()
            mode = stat.S_IMODE(st.st_mode)
            if stat.S_ISDIR(st.st_mode):
                visit(child_path, child_rel)
            elif stat.S_ISREG(st.st_mode):
                key = _stat_tuple(st)
                content_sha = file_hash_cache.get(key)
                if content_sha is None:
                    content_sha = _sha256_regular(child_path, st)
                    file_hash_cache[key] = content_sha
                regular_bytes += st.st_size
                emit(
                    [
                        "F",
                        child_rel,
                        f"{mode:o}",
                        st.st_uid,
                        st.st_gid,
                        st.st_size,
                        st.st_dev,
                        st.st_ino,
                        st.st_nlink,
                        st.st_mtime_ns,
                        st.st_ctime_ns,
                        content_sha,
                    ]
                )
            elif stat.S_ISLNK(st.st_mode):
                emit(
                    [
                        "L",
                        child_rel,
                        f"{mode:o}",
                        st.st_uid,
                        st.st_gid,
                        st.st_dev,
                        st.st_ino,
                        st.st_mtime_ns,
                        st.st_ctime_ns,
                        os.readlink(child_path),
                    ]
                )
            else:
                emit(
                    [
                        "O",
                        child_rel,
                        f"{st.st_mode:o}",
                        st.st_uid,
                        st.st_gid,
                        st.st_rdev,
                        st.st_dev,
                        st.st_ino,
                        st.st_mtime_ns,
                        st.st_ctime_ns,
                    ]
                )
        after = directory.lstat()
        if _stat_tuple(after) != _stat_tuple(before):
            raise RuntimeError(f"directory changed during scan: {directory}")

    visit(path, "")
    after_root = path.lstat()
    if _stat_tuple(after_root) != _stat_tuple(root):
        raise RuntimeError(f"root directory changed during identity scan: {path}")
    return (
        f"directory:entries={entries}:regular_bytes={regular_bytes}:"
        f"tree_sha256={stream.hexdigest()}:mode={stat.S_IMODE(root.st_mode):o}:"
        f"dev={root.st_dev}:ino={root.st_ino}:mtime_ns={root.st_mtime_ns}:"
        f"ctime_ns={root.st_ctime_ns}"
    )
