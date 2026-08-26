#!/usr/bin/env python3
"""Show Codex Sol's live template plus the one follow-rules line.

Does not rewrite OpenAI's template. The live inject is
`model_instructions_file` in ~/.codex/config.toml pointing at
`.codex/follow-rules.md`. This script only writes a local dump for inspection.
"""
from __future__ import annotations

import json
from pathlib import Path

CACHE = Path.home() / ".codex" / "models_cache.json"
LINE = Path("/workspace/.codex/follow-rules.md")
OUT = Path("/workspace/.codex/sol-system-prompt.md")
SLUG = "gpt-5.6-sol"


def main() -> None:
    data = json.loads(CACHE.read_text())
    models = data.get("models") or []
    sol = next((m for m in models if m.get("slug") == SLUG), None)
    if sol is None:
        raise SystemExit(f"no {SLUG} in {CACHE}")
    tmpl = (sol.get("model_messages") or {}).get("instructions_template")
    if not tmpl or not str(tmpl).strip():
        raise SystemExit(f"{SLUG} has empty instructions_template")
    line = LINE.read_text().strip()
    body = tmpl.rstrip() + "\n\n" + line + "\n"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(body)
    print(
        f"wrote {OUT} ({len(body)} bytes) "
        f"from {SLUG} cache {data.get('fetched_at')} + one line"
    )


if __name__ == "__main__":
    main()
