#!/usr/bin/env python3
"""Payload-free production launcher/watchdog smoke."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    run_dir = Path(tempfile.mkdtemp(prefix="russell-launcher-smoke-", dir="/tmp"))
    try:
        env = {**os.environ, "RUSSELL_RUNS_DIR": str(run_dir)}
        launch = subprocess.run(
            [
                "bash",
                str(ROOT / "tools/run.sh"),
                "smoke",
                "--",
                "bash",
                "-c",
                "echo output; echo heartbeat >&2",
            ],
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        if "launched 'smoke'" not in launch.stdout:
            raise RuntimeError(f"unexpected launch output: {launch.stdout}")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not (run_dir / "smoke.rc").is_file():
            time.sleep(0.05)
        if (run_dir / "smoke.rc").read_text().strip() != "0":
            raise RuntimeError("smoke child did not exit zero")
        if (run_dir / "smoke.log").read_text().strip() != "output":
            raise RuntimeError("stdout registry mismatch")
        if (run_dir / "smoke.hb").read_text().strip() != "heartbeat":
            raise RuntimeError("heartbeat registry mismatch")
        subprocess.run(
            ["bash", str(ROOT / "tools/watchdog.sh"), "--check"],
            env=env,
            check=True,
        )
        listing = subprocess.check_output(
            ["bash", str(ROOT / "tools/run.sh"), "--list"],
            env=env,
            text=True,
        )
        if "smoke" not in listing or "0" not in listing:
            raise RuntimeError(f"run listing mismatch: {listing}")
        print("PASS launcher/watchdog payload-free smoke")
        return 0
    finally:
        shutil.rmtree(run_dir)


if __name__ == "__main__":
    raise SystemExit(main())
