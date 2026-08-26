#!/usr/bin/env python3
"""G4: local plugin symlink points at the repo plugin."""
from pathlib import Path

SRC = Path("/workspace/.cursor/plugins/pstack-lab").resolve()
LINK = Path("/home/algo/.cursor/plugins/local/pstack-lab")


def main() -> None:
    if not LINK.exists():
        raise SystemExit("missing ~/.cursor/plugins/local/pstack-lab")
    dest = LINK.resolve()
    if dest != SRC:
        raise SystemExit(f"symlink {dest} != {SRC}")
    print("install_ok")


if __name__ == "__main__":
    main()
