"""Read the interior of one marked block, shared by the contract checks."""

from __future__ import annotations

from agent_harness_verify_common import require


def marker_interior(raw: bytes, markers: tuple[str, str], name: str) -> bytes:
    begin, end = (marker.encode() for marker in markers)
    require(raw.count(begin) == 1 and raw.count(end) == 1, name,
            {"begin": raw.count(begin), "end": raw.count(end)},
            "each marker exactly once")
    opening = begin + b"\n"
    start = raw.find(opening)
    stop = raw.find(end, start + len(opening))
    require(start >= 0 and stop >= 0, name, markers, "markers on their own lines in order")
    return raw[start + len(opening):stop]
