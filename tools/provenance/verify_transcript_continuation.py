#!/usr/bin/env python3
"""Prove that a later Codex prefix manifest extends an earlier freeze."""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path


SOURCE_ROOT = Path("/home/claude/.codex/sessions")


def read_manifest(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as src:
        rows = list(csv.DictReader(src, delimiter="\t"))
    result = {row["relative_path"]: row for row in rows}
    if not result or len(result) != len(rows):
        raise RuntimeError(f"empty or duplicate manifest: {path}")
    return result


def prefix_sha(path: Path, length: int) -> str:
    h = hashlib.sha256()
    remaining = length
    with path.open("rb") as src:
        while remaining:
            chunk = src.read(min(8 * 1024 * 1024, remaining))
            if not chunk:
                raise RuntimeError(f"short prefix read: {path}")
            h.update(chunk)
            remaining -= len(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old", required=True, type=Path)
    parser.add_argument("--new", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    old = read_manifest(args.old)
    new = read_manifest(args.new)
    rows = []
    for relative in sorted(old):
        if relative not in new:
            raise RuntimeError(f"old transcript source missing from continuation: {relative}")
        prior = old[relative]
        current = new[relative]
        old_cutoff = int(prior["cutoff_bytes"])
        new_cutoff = int(current["cutoff_bytes"])
        if new_cutoff < old_cutoff:
            raise RuntimeError(f"continuation shrank: {relative}")
        actual_old_prefix = prefix_sha(SOURCE_ROOT / relative, old_cutoff)
        if actual_old_prefix != prior["prefix_sha256"]:
            raise RuntimeError(f"old prefix drift: {relative}")
        rows.append(
            {
                "relative_path": relative,
                "old_cutoff_bytes": old_cutoff,
                "new_cutoff_bytes": new_cutoff,
                "appended_bytes": new_cutoff - old_cutoff,
                "old_prefix_sha256": prior["prefix_sha256"],
                "new_prefix_sha256": current["prefix_sha256"],
                "status": "PREFIX_CONTINUITY_PASS",
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    print(
        f"PASS old_sources={len(old)} new_sources={len(new)} "
        f"appended_bytes={sum(int(row['appended_bytes']) for row in rows)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
