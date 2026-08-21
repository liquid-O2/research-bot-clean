"""Codex ``PreCompact`` command hook for bounded continuity capture."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from typing import Any

try:
    from .mempalace_continuity_spool import append_journal_checkpoint
    from .mempalace_continuity_spool import append_receipt_log
    from .mempalace_continuity_spool import capture_precompact
    from .mempalace_continuity_spool import reconcile_path
except ImportError:  # Executed as an absolute script by Codex.
    from mempalace_continuity_spool import append_journal_checkpoint
    from mempalace_continuity_spool import append_receipt_log
    from mempalace_continuity_spool import capture_precompact
    from mempalace_continuity_spool import reconcile_path


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
        record, spool_path, receipt = capture_precompact(payload)
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

    # The local journal is the synchronous durability boundary.  Commit it
    # before touching the network so an unavailable palace cannot consume the
    # hook budget and lose the last pre-compaction context.
    try:
        journal = append_journal_checkpoint(record)
    except Exception as exc:
        journal = {"status": "journal_failed", "error_type": type(exc).__name__}
    receipt["journal_status"] = journal.get("status")
    for key in ("journal_path", "journal_sha256", "journal_entry_sha256"):
        value = journal.get(key)
        if isinstance(value, str):
            receipt[key] = value

    # Reconcile the exact checkpoint just captured, rather than an older item
    # selected from the backlog.  The HTTP path is bounded below the Codex hook
    # timeout and never opens a second ChromaDB writer.
    reconciliation = reconcile_path(spool_path)
    receipt["reconcile"] = [reconciliation.get("status")]
    receipt["palace_reconciled"] = reconciliation.get("status") in {
        "reconciled",
        "already_reconciled",
    }
    checkpoint_sha = str(receipt.get("checkpoint_sha256") or "")[:12]
    palace_state = "hub-reconciled" if receipt["palace_reconciled"] else "spooled"
    journal_state = str(receipt.get("journal_status") or "journal-unknown")
    return {
        "systemMessage": (
            "MemPalace PreCompact checkpoint captured "
            f"({journal_state}, {palace_state}, sha256={checkpoint_sha})."
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
