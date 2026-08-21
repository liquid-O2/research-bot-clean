#!/usr/bin/env python3
"""CLI for the single MemPalace HTTP hub. Never opens a second Chroma writer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from engine.entry_v2.mempalace_hub_client import call_tool, healthz, hub_base_url


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("health", "search", "diary-write", "diary-read"),
    )
    parser.add_argument("text", nargs="?", default="")
    parser.add_argument("--agent", default="grok")
    parser.add_argument("--topic", default="continuity")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=12.0)
    args = parser.parse_args()

    if args.command == "health":
        ok = healthz()
        print(json.dumps({"url": hub_base_url(), "healthz": ok}, indent=2))
        return 0 if ok else 2

    if args.command == "search":
        if not args.text:
            print("search requires a query", file=sys.stderr)
            return 2
        result = call_tool(
            "mempalace_search",
            {"query": args.text, "limit": args.limit},
            timeout=args.timeout,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("success") else 1

    if args.command == "diary-write":
        if not args.text:
            print("diary-write requires entry text", file=sys.stderr)
            return 2
        result = call_tool(
            "mempalace_diary_write",
            {
                "agent_name": args.agent,
                "entry": args.text,
                "topic": args.topic,
                "wing": "",
            },
            timeout=args.timeout,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("success") else 1

    result = call_tool(
        "mempalace_diary_read",
        {"agent_name": args.agent, "last_n": args.limit, "wing": ""},
        timeout=args.timeout,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
