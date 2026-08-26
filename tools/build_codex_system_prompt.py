#!/usr/bin/env python3
"""Assemble Codex Sol instructions: live cache template plus always-on rules.

Does not strip OpenAI's template. Adds the project rules after it.
"""
from __future__ import annotations

import json
from pathlib import Path

CACHE = Path.home() / ".codex" / "models_cache.json"
RULES = Path("/workspace/.codex/always-on-rules.md")
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
    rules = RULES.read_text()
    body = tmpl.rstrip() + "\n\n" + rules.rstrip() + "\n"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(body)
    print(
        f"wrote {OUT} ({len(body)} bytes) "
        f"from {SLUG} cache {data.get('fetched_at')} + {RULES.name}"
    )


if __name__ == "__main__":
    main()
