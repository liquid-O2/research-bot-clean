"""Crash-durable atomic directory publication for Entry V2 artifacts."""

from __future__ import annotations

import os
from pathlib import Path

from . import common as C
from .tabular_recovery_contracts import RecoveryRefusal


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_replace_directory(stage: str | Path, target: str | Path) -> None:
    """Fsync a complete staged tree, rename it, then fsync the parent."""

    staged = C.assert_workspace_output(stage)
    destination = C.assert_workspace_output(target)
    if (not staged.is_dir() or destination.exists()
            or staged.parent != destination.parent):
        raise RecoveryRefusal("atomic directory publication inputs differ")
    directories = []
    for root, names, files in os.walk(staged):
        directory = Path(root);directories.append(directory)
        for name in files:
            with (directory / name).open("rb") as handle:
                os.fsync(handle.fileno())
    for directory in reversed(directories):
        _fsync_directory(directory)
    os.replace(staged, destination)
    _fsync_directory(destination.parent)


__all__ = ["atomic_replace_directory"]
