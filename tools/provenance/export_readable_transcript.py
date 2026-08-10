#!/usr/bin/env python3
"""Export provenance-linked user/assistant messages from frozen Codex prefixes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


SOURCE_ROOT = Path("/home/claude/.codex/sessions")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def texts(content: object) -> list[str]:
    result: list[str] = []
    if not isinstance(content, list):
        return result
    for part in content:
        if not isinstance(part, dict):
            continue
        value = part.get("text")
        if isinstance(value, str):
            result.append(value)
    return result


def thread_id_from_name(name: str) -> str:
    match = re.search(r"([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\.jsonl$", name)
    return match.group(1) if match else name


def indented(text: str) -> str:
    if not text:
        return "    [empty]\n"
    return "".join(f"    {line}\n" for line in text.splitlines()) + (
        "" if text.endswith("\n") else "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix-manifest", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    with args.prefix_manifest.open(newline="", encoding="utf-8") as src:
        rows = list(csv.DictReader(src, delimiter="\t"))
    if not rows:
        raise RuntimeError("empty prefix manifest")

    sessions: list[dict[str, object]] = []
    messages: list[dict[str, object]] = []
    issues: list[dict[str, object]] = []
    seen_message_ids: set[str] = set()

    for row in sorted(rows, key=lambda item: item["relative_path"]):
        rel = Path(row["relative_path"])
        source = SOURCE_ROOT / rel
        cutoff = int(row["cutoff_bytes"])
        expected = row["prefix_sha256"]
        data = source.read_bytes()[:cutoff]
        if len(data) != cutoff or sha256(data) != expected:
            raise RuntimeError(f"prefix drift: {source}")

        thread_id = thread_id_from_name(source.name)
        meta: dict[str, object] = {}
        offset = 0
        physical_line = 0
        valid_records = 0
        for raw_line in data.splitlines(keepends=True):
            physical_line += 1
            start = offset
            end = offset + len(raw_line)
            offset = end
            try:
                obj = json.loads(raw_line)
                valid_records += 1
            except Exception as exc:
                issues.append(
                    {
                        "relative_path": rel.as_posix(),
                        "physical_line": physical_line,
                        "start_byte": start,
                        "end_byte_exclusive": end,
                        "bytes": len(raw_line),
                        "sha256": sha256(raw_line),
                        "disposition": "RAW_PRESERVED_FRAGMENT_SKIPPED_READABLE",
                        "error": f"{type(exc).__name__}:{exc}",
                    }
                )
                continue

            if obj.get("type") == "session_meta" and not meta:
                payload = obj.get("payload")
                if isinstance(payload, dict):
                    meta = payload

            if obj.get("type") != "response_item":
                continue
            payload = obj.get("payload")
            if not isinstance(payload, dict) or payload.get("type") != "message":
                continue
            role = payload.get("role")
            if role not in {"user", "assistant"}:
                continue
            message_id = payload.get("id")
            if not isinstance(message_id, str) or not message_id:
                message_id = f"{thread_id}:{obj.get('ordinal')}:{start}"
            if message_id in seen_message_ids:
                continue
            seen_message_ids.add(message_id)
            body = "\n".join(texts(payload.get("content")))
            messages.append(
                {
                    "timestamp": str(obj.get("timestamp", "")),
                    "ordinal": obj.get("ordinal"),
                    "thread_id": thread_id,
                    "session_id": meta.get("session_id", ""),
                    "thread_source": meta.get("thread_source", ""),
                    "agent_path": (
                        (((meta.get("source") or {}).get("subagent") or {}).get("thread_spawn") or {}).get(
                            "agent_path", ""
                        )
                        if isinstance(meta.get("source"), dict)
                        else ""
                    ),
                    "role": role,
                    "message_id": message_id,
                    "source_relative_path": rel.as_posix(),
                    "physical_line": physical_line,
                    "start_byte": start,
                    "end_byte_exclusive": end,
                    "text_sha256": sha256(body.encode("utf-8")),
                    "text": body,
                }
            )

        sessions.append(
            {
                "thread_id": thread_id,
                "session_id": meta.get("session_id", ""),
                "parent_thread_id": meta.get("parent_thread_id", ""),
                "thread_source": meta.get("thread_source", ""),
                "agent_path": (
                    (((meta.get("source") or {}).get("subagent") or {}).get("thread_spawn") or {}).get(
                        "agent_path", ""
                    )
                    if isinstance(meta.get("source"), dict)
                    else ""
                ),
                "relative_path": rel.as_posix(),
                "cutoff_bytes": cutoff,
                "prefix_sha256": expected,
                "valid_json_records": valid_records,
                "malformed_physical_lines": sum(
                    1 for issue in issues if issue["relative_path"] == rel.as_posix()
                ),
            }
        )

    transcript = args.out_dir / "CONVERSATION.md"
    with transcript.open("x", encoding="utf-8") as out:
        out.write("# Readable project conversation\n\n")
        out.write(
            "This is a provenance-linked readable export of user and assistant "
            "messages from frozen Codex JSONL prefixes. Developer/system messages, "
            "reasoning ciphertext and tool payloads are excluded. Complete raw bytes "
            "are preserved in the encrypted private vault. Messages are grouped by "
            "thread; child-agent dialogue is labelled explicitly.\n\n"
        )
        by_thread: dict[str, list[dict[str, object]]] = {}
        for message in messages:
            by_thread.setdefault(str(message["thread_id"]), []).append(message)
        session_by_thread = {str(session["thread_id"]): session for session in sessions}
        for thread_id in sorted(by_thread, key=lambda key: min(
            str(item["timestamp"]) for item in by_thread[key]
        )):
            session = session_by_thread[thread_id]
            label = str(session["agent_path"] or session["thread_source"] or "unknown")
            out.write(f"## Thread {thread_id} — {label}\n\n")
            out.write(
                f"Source: `{session['relative_path']}`; prefix "
                f"`{session['prefix_sha256']}` through byte "
                f"{session['cutoff_bytes']}.\n\n"
            )
            for message in by_thread[thread_id]:
                out.write(
                    f"### {message['timestamp']} — {str(message['role']).upper()} "
                    f"(ordinal {message['ordinal']}, id {message['message_id']})\n\n"
                )
                out.write(
                    f"Provenance: line {message['physical_line']}, bytes "
                    f"[{message['start_byte']},{message['end_byte_exclusive']}), text "
                    f"SHA-256 `{message['text_sha256']}`.\n\n"
                )
                out.write(indented(str(message["text"])))
                out.write("\n")

    session_index = args.out_dir / "SESSION_INDEX.tsv"
    with session_index.open("x", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=list(sessions[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(sessions)

    issue_file = args.out_dir / "TRANSCRIPT_PARSE_ISSUES.tsv"
    fields = [
        "relative_path",
        "physical_line",
        "start_byte",
        "end_byte_exclusive",
        "bytes",
        "sha256",
        "disposition",
        "error",
    ]
    with issue_file.open("x", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(issues)

    receipt = {
        "schema": "russell_readable_transcript_v1",
        "source_manifest_sha256": sha256(args.prefix_manifest.read_bytes()),
        "session_count": len(sessions),
        "message_count": len(messages),
        "user_message_count": sum(message["role"] == "user" for message in messages),
        "assistant_message_count": sum(message["role"] == "assistant" for message in messages),
        "malformed_physical_line_count": len(issues),
        "conversation_sha256": sha256(transcript.read_bytes()),
        "session_index_sha256": sha256(session_index.read_bytes()),
        "issues_sha256": sha256(issue_file.read_bytes()),
        "raw_authority": "encrypted_private_vault",
    }
    (args.out_dir / "EXPORT_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
