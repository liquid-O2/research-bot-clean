"""Codex ``PreCompact`` command hook for bounded continuity capture."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from typing import Any

try:
    from .mempalace_continuity_spool import append_receipt_log
    from .mempalace_continuity_spool import capture_precompact
    from .mempalace_continuity_spool import reconcile_pending
except ImportError:  # Executed as an absolute script by Codex.
    from mempalace_continuity_spool import append_receipt_log
    from mempalace_continuity_spool import capture_precompact
    from mempalace_continuity_spool import reconcile_pending


# MemPalace's write modules protect MCP stdout at import time. Preserve the
# hook protocol fd before an eventual direct reconciliation imports them.
_HOOK_STDOUT_FD = os.dup(1)


def _emit(output: Mapping[str, Any]) -> None:
    payload = (json.dumps(dict(output), ensure_ascii=False) + "\n").encode("utf-8")
    os.write(_HOOK_STDOUT_FD, payload)


def _log_receipt(kind: str, receipt: Mapping[str, Any]) -> None:
    """Log metadata/hashes only; never log checkpoint text."""

    append_receipt_log(kind, receipt)


def run(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        _, _, receipt = capture_precompact(payload)
    except Exception as exc:
        receipt = {
            "status": "spool_failed",
            "error_type": type(exc).__name__,
            "session_id": str(payload.get("session_id") or ""),
        }
        return {
            "systemMessage": (
                "MemPalace continuity spool failed before compaction. No automatic checkpoint "
                "was persisted; use mempalace_diary_write before relying on prior context."
            ),
            "suppressOutput": False,
        }, receipt

    # This is always non-blocking on the official writer lease.  Reconciliation
    # goes only through the live HTTP hub; this hook never opens ChromaDB.
    reconciliations = reconcile_pending(limit=2)
    receipt["reconcile"] = [item.get("status") for item in reconciliations]
    receipt["palace_reconciled"] = any(
        item.get("spool_file") == receipt.get("spool_file")
        and item.get("status") == "reconciled"
        for item in reconciliations
    )
    checkpoint_sha = str(receipt.get("checkpoint_sha256") or "")[:12]
    palace_state = "hub-reconciled" if receipt["palace_reconciled"] else "spooled"
    return {
        "systemMessage": (
            "MemPalace PreCompact checkpoint captured "
            f"({palace_state}, sha256={checkpoint_sha})."
        ),
        "suppressOutput": False,
    }, receipt


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        payload = {}
    if not isinstance(payload, Mapping):
        payload = {}
    output, receipt = run(payload)
    _log_receipt("PRECOMPACT", receipt)
    _emit(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
