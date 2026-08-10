#!/usr/bin/env python3
"""Build a canonical manifest for all tracked files except the manifest itself."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = "provenance/CLEANROOM_FILE_MANIFEST.tsv"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as src:
        while chunk := src.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    paths = sorted(
        item.decode("utf-8", "surrogateescape")
        for item in raw.split(b"\0")
        if item and item.decode("utf-8", "surrogateescape") != OUTPUT
    )
    lines = ["path\tbytes\tsha256\n"]
    for relative in paths:
        path = ROOT / relative
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"non-regular tracked path: {relative}")
        lines.append(f"{relative}\t{path.stat().st_size}\t{digest(path)}\n")
    output = ROOT / OUTPUT
    output.write_text("".join(lines), encoding="utf-8")
    print(f"{len(paths)} files -> {OUTPUT} {digest(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
