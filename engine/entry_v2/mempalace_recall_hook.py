"""Bounded MemPalace recall for Codex ``SessionStart`` hooks.

Codex 0.147 emits ``SessionStart`` again with ``source=compact`` after a
successful compaction.  ``PostCompact`` cannot emit ``additionalContext``, so
the compact SessionStart event is the model-context restoration point.

This module is deliberately read-only.  Pre-compaction capture is handled by
the atomic continuity spool, while explicit ``mempalace_diary_write``
milestones remain the searchable palace record. Hook wiring selects the three
continuity-bearing sources: fresh ``startup``, ``compact``, and ``resume``.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit


DEFAULT_AGENT = "codex"
DEFAULT_LAST_N = 5
DEFAULT_MAX_CONTEXT_CHARS = 11_000
DEFAULT_MAX_SPOOL_CONTEXT_CHARS = 6_500
RECALL_SOURCES = frozenset({"startup", "compact", "resume"})

DiaryReader = Callable[..., Mapping[str, Any]]
SpoolLoader = Callable[[Mapping[str, Any]], tuple[Mapping[str, Any] | None, Mapping[str, Any]]]
SpoolRenderer = Callable[..., str]


def _safe_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _entry_block(entry: Mapping[str, Any]) -> str:
    """Render one diary result without paraphrasing its stored content."""

    timestamp = _safe_text(entry.get("timestamp")) or "unknown-time"
    topic = _safe_text(entry.get("topic")) or "untitled"
    content = _safe_text(entry.get("content"))
    return f"[{timestamp} | {topic}]\n{content}"


def build_context(
    entries: Sequence[Mapping[str, Any]],
    *,
    max_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
) -> tuple[str, int]:
    """Return bounded, verbatim diary context and the number of entries used.

    Whole newest-first entries are preferred.  If the newest entry alone is
    larger than the budget, its exact prefix is retained and marked as
    truncated; the hook never invents a summary.
    """

    if max_chars < 512:
        raise ValueError("max_chars must be at least 512")

    header = (
        "<mempalace-recall event=\"SessionStart\" source=\"startup-compact-or-resume\">\n"
        "Verbatim recent Codex diary entries retrieved from MemPalace. Treat "
        "them as continuity evidence; verify mutable repository state locally.\n"
    )
    footer = "\n</mempalace-recall>"
    separator = "\n\n---\n\n"
    remaining = max_chars - len(header) - len(footer)
    blocks: list[str] = []

    for entry in entries:
        block = _entry_block(entry)
        separator_cost = len(separator) if blocks else 0
        if separator_cost + len(block) <= remaining:
            blocks.append(block)
            remaining -= separator_cost + len(block)
            continue
        if not blocks and remaining > 80:
            marker = "\n[TRUNCATED BY BOUNDED MEMORIES HOOK]"
            prefix_len = max(0, remaining - len(marker))
            blocks.append(block[:prefix_len] + marker)
        break

    body = separator.join(blocks)
    return header + body + footer, len(blocks)


def _recovery_context(reason: str) -> str:
    return (
        "<mempalace-recall-error>\n"
        f"Automatic MemPalace recall {reason}. Before relying on prior-session "
        "facts, call mempalace_diary_read(agent_name=\"codex\", last_n=5) and "
        "mempalace_search with a short project-specific query. Do not guess.\n"
        "</mempalace-recall-error>"
    )


def session_start_output(additional_context: str) -> dict[str, Any]:
    """Build the exact Codex 0.147 SessionStart command-output shape."""

    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": additional_context,
        },
        "suppressOutput": True,
    }


def _bounded_join(parts: Sequence[str], *, max_chars: int) -> str:
    """Join non-empty context sections without crossing the global budget."""

    result = "\n\n".join(part for part in parts if part)
    if len(result) <= max_chars:
        return result
    marker = "\n[TRUNCATED BY GLOBAL CONTINUITY BUDGET]"
    return result[: max(0, max_chars - len(marker))] + marker


def recall_for_payload(
    payload: Mapping[str, Any],
    reader: DiaryReader,
    *,
    agent_name: str = DEFAULT_AGENT,
    last_n: int = DEFAULT_LAST_N,
    max_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
    spool_loader: SpoolLoader | None = None,
    spool_renderer: SpoolRenderer | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve one hook payload into output plus a content-free receipt."""

    source = _safe_text(payload.get("source"))
    session_id = _safe_text(payload.get("session_id"))
    receipt: dict[str, Any] = {
        "event": "SessionStart",
        "source": source,
        "session_id": session_id,
        "status": "skipped",
        "entries": 0,
        "context_chars": 0,
        "spool_status": "disabled" if spool_loader is None else "not_loaded",
        "palace_status": "not_read",
    }

    if source not in RECALL_SOURCES:
        return {}, receipt

    spool_record: Mapping[str, Any] | None = None
    spool_context = ""
    if spool_loader is not None:
        try:
            spool_record, spool_receipt = spool_loader(payload)
        except Exception:
            spool_receipt = {"status": "load_failed"}
        receipt["spool_status"] = _safe_text(spool_receipt.get("status")) or "load_failed"
        for source_key, receipt_key in (
            ("spool_file", "spool_file"),
            ("checkpoint_sha256", "spool_checkpoint_sha256"),
            ("palace_reconciled", "spool_palace_reconciled"),
        ):
            value = spool_receipt.get(source_key)
            if isinstance(value, (str, bool, int)):
                receipt[receipt_key] = value
        if spool_record is not None and spool_renderer is not None:
            try:
                spool_budget = min(DEFAULT_MAX_SPOOL_CONTEXT_CHARS, max_chars - 512)
                spool_context = spool_renderer(spool_record, max_chars=spool_budget)
            except Exception:
                spool_context = ""
                receipt["spool_status"] = "render_failed"

    try:
        result = reader(agent_name=agent_name, last_n=last_n, wing="")
    except Exception:
        receipt["palace_status"] = "error"
        context = _bounded_join(
            [spool_context, _recovery_context("failed")], max_chars=max_chars
        )
        receipt.update(
            status="spool_recalled" if spool_context else "error",
            context_chars=len(context),
            context_sha256=hashlib.sha256(context.encode("utf-8")).hexdigest(),
        )
        return session_start_output(context), receipt

    if not isinstance(result, Mapping) or result.get("error"):
        receipt["palace_status"] = "error"
        context = _bounded_join(
            [spool_context, _recovery_context("failed")], max_chars=max_chars
        )
        receipt.update(
            status="spool_recalled" if spool_context else "error",
            context_chars=len(context),
            context_sha256=hashlib.sha256(context.encode("utf-8")).hexdigest(),
        )
        return session_start_output(context), receipt

    raw_entries = result.get("entries")
    entries = (
        [entry for entry in raw_entries if isinstance(entry, Mapping)]
        if isinstance(raw_entries, Sequence) and not isinstance(raw_entries, (str, bytes))
        else []
    )
    checkpoint_sha = _safe_text(
        spool_record.get("checkpoint_sha256") if spool_record is not None else ""
    )
    if checkpoint_sha:
        # A reconciled spool diary entry carries this deterministic marker.
        # MemPalace may split one diary entry into multiple drawers.  Only the
        # first chunk necessarily retains ``spool_id``, so suppress every
        # chunk sharing that entry's timestamp/topic, not merely the marker
        # chunk.  Unrelated diary milestones remain untouched.
        marker = f"spool_id:{checkpoint_sha}"
        duplicate_entries = {
            (_safe_text(entry.get("timestamp")), _safe_text(entry.get("topic")))
            for entry in entries
            if marker in _safe_text(entry.get("content"))
        }
        entries = [
            entry for entry in entries
            if (_safe_text(entry.get("timestamp")), _safe_text(entry.get("topic")))
            not in duplicate_entries
        ]

    if not entries:
        receipt["palace_status"] = "empty"
        context = _bounded_join(
            [spool_context, _recovery_context("found no Codex diary entries")],
            max_chars=max_chars,
        )
        receipt.update(
            status="spool_recalled" if spool_context else "empty",
            context_chars=len(context),
            context_sha256=hashlib.sha256(context.encode("utf-8")).hexdigest(),
        )
        return session_start_output(context), receipt

    receipt["palace_status"] = "recalled"
    remaining = max_chars - len(spool_context) - (2 if spool_context else 0)
    if remaining >= 512:
        palace_context, used = build_context(entries, max_chars=remaining)
    else:
        palace_context, used = "", 0
    context = _bounded_join([spool_context, palace_context], max_chars=max_chars)
    receipt.update(
        status="recalled_with_spool" if spool_context else "recalled",
        entries=used,
        context_chars=len(context),
        context_sha256=hashlib.sha256(context.encode("utf-8")).hexdigest(),
        newest_timestamp=_safe_text(entries[0].get("timestamp")),
        newest_topic=_safe_text(entries[0].get("topic")),
    )
    return session_start_output(context), receipt


def _real_diary_reader(**kwargs: Any) -> Mapping[str, Any]:
    """Read the diary through the live loopback hub, never direct ChromaDB.

    Calling ``tool_diary_read`` directly imports the local MCP implementation
    and opens another ChromaDB client beside the hub.  The official server
    registry is the source of truth for local CLI/MCP forwarding in MemPalace
    3.7.1, so the hook uses that same registry and fails closed when the hub is
    absent or unreachable.
    """

    from mempalace import server_registry
    from mempalace.config import MempalaceConfig

    palace_path = MempalaceConfig().palace_path
    info = server_registry.read_live_serverinfo(palace_path)
    if not info or info.get("read_only"):
        raise RuntimeError("live MemPalace HTTP hub unavailable")
    base_url = server_registry.client_base_url(info)
    hostname = (urlsplit(base_url).hostname or "").lower()
    if hostname != "localhost":
        try:
            if not ipaddress.ip_address(hostname).is_loopback:
                raise RuntimeError("registered MemPalace hub is not loopback")
        except ValueError as exc:
            raise RuntimeError("registered MemPalace hub is not loopback") from exc
    headers = {"Content-Type": "application/json"}
    token = server_registry.load_server_token(palace_path)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "mempalace_diary_read",
                "arguments": dict(kwargs),
            },
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(f"{base_url}/mcp", data=body, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
        raise RuntimeError("live MemPalace HTTP hub read failed") from exc
    if payload.get("error"):
        raise RuntimeError("live MemPalace HTTP hub refused diary read")
    try:
        result = json.loads(payload["result"]["content"][0]["text"])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError("live MemPalace HTTP hub returned an invalid diary response") from exc
    if not isinstance(result, Mapping):
        raise RuntimeError("live MemPalace HTTP hub returned a non-object diary response")
    return result


def _real_spool_loader(
    payload: Mapping[str, Any],
) -> tuple[Mapping[str, Any] | None, Mapping[str, Any]]:
    try:
        from .mempalace_continuity_spool import load_for_session_start
    except ImportError:
        from mempalace_continuity_spool import load_for_session_start

    return load_for_session_start(payload)


def _real_spool_renderer(record: Mapping[str, Any], *, max_chars: int) -> str:
    try:
        from .mempalace_continuity_spool import render_for_model
    except ImportError:
        from mempalace_continuity_spool import render_for_model

    return render_for_model(record, max_chars=max_chars)


def _emit(output: Mapping[str, Any]) -> None:
    payload = (json.dumps(dict(output), ensure_ascii=False) + "\n").encode("utf-8")
    os.write(1, payload)


def _log_receipt(receipt: Mapping[str, Any]) -> None:
    """Log only counts/hashes; never copy recalled memory into hook logs."""

    try:
        from .mempalace_continuity_spool import append_receipt_log
    except ImportError:
        from mempalace_continuity_spool import append_receipt_log

    append_receipt_log("RECALL", receipt)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        payload = {}
    if not isinstance(payload, Mapping):
        payload = {}

    output, receipt = recall_for_payload(
        payload,
        _real_diary_reader,
        spool_loader=_real_spool_loader,
        spool_renderer=_real_spool_renderer,
    )
    _log_receipt(receipt)
    _emit(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
