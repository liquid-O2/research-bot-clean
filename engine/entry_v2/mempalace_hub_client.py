"""HTTP JSON-RPC client for the single MemPalace writer at 127.0.0.1:8765.

Hooks and CLI must never open a second ChromaDB writer.  All palace I/O goes
through this client.  Failures return a dict; they do not raise into a hook.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib import error, request


DEFAULT_HUB_URL = "http://127.0.0.1:8765"
DEFAULT_TOKEN_PATH = Path(
    "/workspace/.mempalace/daemon/e577205b40c9f52808786a28/token"
)
Transport = Callable[..., Mapping[str, Any]]


class HubCallError(RuntimeError):
    """Raised only when a caller explicitly wants a hard failure."""


def hub_base_url() -> str:
    override = os.environ.get("MEMPALACE_HUB_URL", "").strip()
    return override.rstrip("/") if override else DEFAULT_HUB_URL


def hub_token() -> str:
    override = os.environ.get("MEMPALACE_HUB_TOKEN", "").strip()
    if override:
        return override
    try:
        return DEFAULT_TOKEN_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def parse_tool_result(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Decode an MCP tools/call JSON-RPC envelope into a plain dict."""

    if not isinstance(payload, Mapping):
        return {"success": False, "status": "bad_payload"}
    if payload.get("error"):
        err = payload.get("error")
        message = ""
        if isinstance(err, Mapping):
            message = str(err.get("message") or "")
        return {"success": False, "status": "rpc_error", "error": message}
    result = payload.get("result")
    if not isinstance(result, Mapping):
        return {"success": False, "status": "missing_result"}
    content = result.get("content")
    if isinstance(content, list) and content:
        first = content[0]
        text = first.get("text") if isinstance(first, Mapping) else None
        if isinstance(text, str):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "status": "unparsed_text",
                    "text": text[:2000],
                }
            if isinstance(parsed, Mapping):
                output = dict(parsed)
                if "success" not in output:
                    output["success"] = True
                return output
    return {"success": True, "status": "ok", "result": result}


def _default_transport(
    url: str,
    body: bytes,
    headers: Mapping[str, str],
    timeout: float,
) -> Mapping[str, Any]:
    req = request.Request(url, data=body, headers=dict(headers), method="POST")
    with request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw)


def call_tool(
    name: str,
    arguments: Mapping[str, Any] | None = None,
    *,
    timeout: float = 8.0,
    transport: Transport | None = None,
) -> dict[str, Any]:
    """Call one hub MCP tool.  Never raises for network/parse failures."""

    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    token = hub_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": dict(arguments or {})},
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    sender = transport or _default_transport
    try:
        response = sender(f"{hub_base_url()}/mcp", body, headers, timeout)
        if not isinstance(response, Mapping):
            return {"success": False, "status": "bad_transport_response"}
        parsed = parse_tool_result(response)
        parsed.setdefault("tool", name)
        return parsed
    except Exception as exc:
        return {
            "success": False,
            "status": "hub_unavailable",
            "error_type": type(exc).__name__,
            "tool": name,
        }


def healthz(*, timeout: float = 2.0) -> bool:
    try:
        req = request.Request(f"{hub_base_url()}/healthz", method="GET")
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8").strip().lower()
        return body in {"ok", "healthy"} or bool(body)
    except Exception:
        return False
