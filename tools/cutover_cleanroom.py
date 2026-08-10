#!/usr/bin/env python3
"""Manifest-checked replacement of the legacy /workspace control plane."""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from retirement_identity import identity


WORKSPACE = Path("/workspace")
RETAIN = {WORKSPACE / "data", WORKSPACE / "artifacts"}


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve()
    expected_source = Path("/workspace/data/cleanroom_staging/research-bot-clean")
    if source != expected_source or not (source / ".git").is_dir():
        raise RuntimeError(f"unexpected clean source: {source}")
    if git(source, "status", "--porcelain"):
        raise RuntimeError("clean source has uncommitted changes")
    if git(source, "branch", "--show-current") != "main":
        raise RuntimeError("clean source is not on main")
    local_oid = git(source, "rev-parse", "HEAD")
    remote_line = git(source, "ls-remote", "--heads", "origin", "main").split()
    if len(remote_line) != 2 or remote_line[0] != local_oid:
        raise RuntimeError("clean source and remote main differ")
    other_remote = git(source, "ls-remote", "--heads", "origin").splitlines()
    if len(other_remote) != 1 or not other_remote[0].endswith("refs/heads/main"):
        raise RuntimeError(f"clean remote branch set is not exactly main: {other_remote}")
    subprocess.run(["python", "tools/verify_cleanroom.py"], cwd=source, check=True)

    manifest = source / "retirement/DELETIONS.tsv"
    with manifest.open(newline="", encoding="utf-8") as src:
        rows = list(csv.DictReader(src, delimiter="\t"))
    if not rows:
        raise RuntimeError("empty deletion manifest")
    targets = []
    for row in rows:
        path = Path(row["target"])
        if path.parent != WORKSPACE or path in RETAIN:
            raise RuntimeError(f"out-of-scope deletion target: {path}")
        if not path.exists() and not path.is_symlink():
            raise RuntimeError(f"missing legacy target before cutover: {path}")
        actual = identity(path)
        if actual != row["pre_identity"]:
            raise RuntimeError(
                f"legacy target identity drift: {path}\nexpected {row['pre_identity']}\nactual   {actual}"
            )
        targets.append(path)

    source_names = {path.name for path in source.iterdir()}
    if "data" in source_names or "artifacts" in source_names:
        raise RuntimeError("clean source must not contain data/artifacts roots")
    if not args.execute:
        print(
            f"DRY_RUN_PASS oid={local_oid} deletion_targets={len(targets)} "
            f"source_entries={len(source_names)}"
        )
        return 0

    for path in targets:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    for item in sorted(source.iterdir(), key=lambda path: path.name):
        destination = WORKSPACE / item.name
        if destination.exists() or destination.is_symlink():
            raise RuntimeError(f"destination unexpectedly exists after deletion: {destination}")
        if item.is_dir() and not item.is_symlink():
            shutil.copytree(item, destination, symlinks=True)
        elif item.is_symlink():
            raise RuntimeError(f"clean source symlink refused: {item}")
        else:
            shutil.copy2(item, destination)
    os.sync()
    if git(WORKSPACE, "rev-parse", "HEAD") != local_oid:
        raise RuntimeError("new workspace HEAD mismatch")
    if git(WORKSPACE, "status", "--porcelain"):
        raise RuntimeError("new workspace is dirty")
    if git(WORKSPACE, "branch", "--show-current") != "main":
        raise RuntimeError("new workspace branch mismatch")
    for retained in RETAIN:
        if not retained.is_dir():
            raise RuntimeError(f"retained root missing: {retained}")
    subprocess.run(["python", "tools/verify_cleanroom.py"], cwd=WORKSPACE, check=True)
    print(
        f"CUTOVER_PASS oid={local_oid} removed_legacy_targets={len(targets)} "
        "retained=data,artifacts"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
