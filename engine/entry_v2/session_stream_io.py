"""Path, hash, and sidecar-layout helpers for a pinned QRE2 session."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any, Mapping

import numpy as np

from . import common as C
from .event_pack import EVENT_DTYPE


_SHA256 = re.compile(r"[0-9a-f]{64}")


def _exact_int(value: object, name: str) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise C.EntryV2Refusal(f"{name} must be an integer, not boolean")
    try:
        out = int(value)  # NumPy integer scalars are accepted deliberately.
    except (TypeError, ValueError, OverflowError) as exc:
        raise C.EntryV2Refusal(f"invalid integer {name}") from exc
    if isinstance(value, (float, np.floating)) and not float(value).is_integer():
        raise C.EntryV2Refusal(f"invalid integer {name}")
    return out


def _sha256(value: object, name: str) -> str:
    out = str(value).lower()
    if _SHA256.fullmatch(out) is None:
        raise C.EntryV2Refusal(f"invalid {name} SHA-256")
    return out


def _guard_path_components(path: Path) -> None:
    """Apply the H2/2026 wall before any filesystem lookup or resolution."""
    for component in path.parts:
        for d8 in C.dates_in_basename(component):
            C.guard_date(d8)


def _canonical_source_path(value: os.PathLike[str] | str, d8: int) -> Path:
    path = Path(value)
    _guard_path_components(path)
    if not path.is_absolute():
        raise C.EntryV2Refusal("pinned QRE2 path must be absolute")
    if ".." in path.parts:
        raise C.EntryV2Refusal("pinned QRE2 path cannot contain parent traversal")
    if path.suffix != ".qre2":
        raise C.EntryV2Refusal("pinned event source is not a .qre2 file")
    dates = C.dates_in_basename(path)
    if dates != (int(d8),):
        raise C.EntryV2Refusal(
            "QRE2 basename must contain exactly the pinned trading day"
        )
    # normpath/abspath are lexical operations; unlike resolve(), they do not
    # follow a symlink or inspect an unauthorized payload.
    normalized = Path(os.path.abspath(os.path.normpath(os.fspath(path))))
    if normalized != path:
        raise C.EntryV2Refusal("pinned QRE2 path is not lexically canonical")
    return path


def _strict_json_object(raw: bytes, name: str) -> Mapping[str, Any]:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise C.EntryV2Refusal(f"duplicate key in {name}: {key}")
            out[key] = value
        return out

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    except C.EntryV2Refusal:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal(f"invalid {name} JSON") from exc
    if not isinstance(value, dict):
        raise C.EntryV2Refusal(f"{name} must be a JSON object")
    return value


def _identity_int(obj: Mapping[str, Any], name: str, expected: int) -> None:
    if name not in obj or _exact_int(obj[name], f"sidecar {name}") != int(expected):
        raise C.EntryV2Refusal(f"event sidecar identity drift: {name}")


def _expected_sidecar_layout() -> frozenset[tuple[str, str, int]]:
    layout: set[tuple[str, str, int]] = set()
    for name in EVENT_DTYPE.names or ():
        dtype, offset = EVENT_DTYPE.fields[name][:2]
        layout.add((name, dtype.str.removeprefix("|"), int(offset)))
    return frozenset(layout)


_SIDECAR_LAYOUT = _expected_sidecar_layout()
