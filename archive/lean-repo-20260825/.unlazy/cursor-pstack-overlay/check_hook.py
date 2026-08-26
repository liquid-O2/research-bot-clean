#!/usr/bin/env python3
"""G3: nudge hook emits JSON additional_context without a principle catalog."""
import json
import subprocess
from pathlib import Path

HOOK = Path("/workspace/.cursor/hooks/nudge.py")
CONFIG = Path("/workspace/.cursor/hooks.json")
BANNED = (
    "principle-laziness-protocol",
    "principle-foundational-thinking",
    "plan-flow",
    "implement-flow",
    "MUST evaluate the complete principle catalog",
)


def run(event: str) -> dict:
    payload = json.dumps({"hook_event_name": event, "session_id": "gate"}).encode()
    proc = subprocess.run(
        ["python3", str(HOOK)],
        input=payload,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"{event} exit {proc.returncode}: {proc.stderr!r}")
    data = json.loads(proc.stdout.decode())
    text = data.get("additional_context")
    if not isinstance(text, str) or len(text) < 20:
        raise SystemExit(f"{event} missing additional_context: {data!r}")
    for token in BANNED:
        if token in text:
            raise SystemExit(f"{event} catalog dump: {token}")
    return data


def main() -> None:
    if not HOOK.is_file():
        raise SystemExit("missing nudge.py")
    cfg = json.loads(CONFIG.read_text())
    hooks = cfg.get("hooks", {})
    for name in ("sessionStart", "beforeSubmitPrompt", "stop"):
        cmds = hooks.get(name) or []
        if not any(".cursor/hooks/nudge.py" in str(item.get("command", "")) for item in cmds):
            raise SystemExit(f"hooks.json missing {name}")
    for event in ("sessionStart", "beforeSubmitPrompt", "stop"):
        run(event)
    print("hook_ok")


if __name__ == "__main__":
    main()
