"""Hash-pinned corpus artifact readers and schemas."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import io
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from . import common as C


def _sha_hex(text: str, name: str) -> str:
    if not (isinstance(text, str) and len(text) == 64 and all(char in "0123456789abcdef" for char in text)):
        raise C.EntryV2Refusal(f"invalid {name} sha256")
    return text


_SHA = re.compile(r"[0-9a-f]{64}")
_CANDIDATE_MANIFEST_COLUMNS = (
    "asset",
    "d8",
    "status",
    "rows",
    "raw_events",
    "two_sided_events",
    "sane_events",
    "candidate_file",
    "candidate_sha256",
    "event_pack_sha256",
    "receipt_file",
    "receipt_sha256",
)
_TEACHER_MANIFEST_COLUMNS = (
    "asset",
    "d8",
    "rows",
    "ready",
    "refused",
    "teacher_file",
    "teacher_sha256",
    "candidate_sha256",
    "event_pack_sha256",
    "receipt_file",
    "receipt_sha256",
)
_LOCK_COLUMNS = (
    "asset",
    "d8",
    "status",
    "locked_iid",
    "selection_basis_d8",
    "selection_basis_updates",
    "selection_basis_symbol",
    "open_utc",
    "close_utc",
)
_CANDIDATE_COLUMNS = (
    "candidate_id",
    "asset",
    "d8",
    "locked_iid",
    "selection_basis_d8",
    "confirmation_ts_recv_ns",
    "confirmation_event_ordinal",
    "decision_ts_ns",
    "decision_sec",
    "side",
    "phase",
    "rung_mask",
    "delay",
    "phase_open_utc",
    "phase_close_utc",
    "event_cutoff",
    "prefix_last_event_ordinal",
    "prefix_last_availability_ts_ns",
    "event_pack_sha256",
    "prefix_sha256",
    "clock_law_receipt_sha256",
    "lineage_sha256",
    "entry_bid_px",
    "entry_ask_px",
    "entry_mid2",
    "entry_spread_usd",
    "frozen_cost_usd",
    "atr14_prev_usd",
    "spread_prior_present",
    "spread_prior_usd",
    "sane_ceiling_usd",
    "compliance_status",
    "compliance_distance_sec",
    "compliance_artifact_sha256",
)
_TEACHER_COLUMNS = (
    "candidate_id",
    "asset",
    "d8",
    "decision_ts_ns",
    "exit_ts_ns",
    "phase_close_utc",
    "status",
    "cert_close_usd",
    "mfe_usd",
    "mae_usd",
    "time_to_peak_sec",
    "wall_hit",
    "payer",
    "take_target",
    "compliance_status",
)


def _sha(value: object, name: str) -> str:
    text = str(value)
    if _SHA.fullmatch(text) is None:
        raise C.EntryV2Refusal(f"invalid {name} sha256")
    return text


def _embedded_receipt(value: Mapping[str, Any], name: str) -> str:
    payload = dict(value)
    claimed = _sha(payload.pop("receipt_sha256", ""), name)
    if C.object_sha256(payload) != claimed:
        raise C.EntryV2Refusal(f"{name} content hash mismatch")
    return claimed


def _guard_path_before_open(path: Path) -> None:
    # Apply the wall to every component before is_file/stat/open/resolve follows.
    for component in path.parts:
        for d8 in C.dates_in_basename(component):
            C.guard_date(d8)


def _read_pinned(path: Path, expected_sha256: str, name: str) -> bytes:
    _guard_path_before_open(path)
    expected = _sha(expected_sha256, name)
    if not path.is_file():
        raise C.EntryV2Refusal(f"missing {name}: {path}")
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise C.EntryV2Refusal(f"{name} hash mismatch: expected={expected} actual={actual}")
    return raw


def _under(root: Path, relative: str, d8: int) -> Path:
    C.guard_date(int(d8))  # must precede resolving or opening the referenced path
    raw = Path(relative)
    _guard_path_before_open(raw)
    if raw.is_absolute():
        raise C.EntryV2Refusal("artifact manifest contains an absolute path")
    resolved_root = root.resolve()
    resolved = (root / raw).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise C.EntryV2Refusal("artifact manifest path escapes output root") from exc
    return resolved


def _table(
    raw: bytes, schema: str, columns: Sequence[str], name: str, *, d8: int | None = None
) -> list[dict[str, str]]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise C.EntryV2Refusal(f"{name} is not UTF-8") from exc
    lines = text.splitlines()
    suffix = r" d8=(\d{8})" if d8 is not None else ""
    header = re.fullmatch(
        rf"# {re.escape(schema)} start_d8=(\d{{8}}) " rf"end_d8_exclusive=(\d{{8}}){suffix}", lines[0] if lines else ""
    )
    if len(lines) < 2 or header is None:
        raise C.EntryV2Refusal(f"{name} schema mismatch")
    start_d8, end_d8 = int(header.group(1)), int(header.group(2))
    C.guard_decode_window(start_d8, end_d8)
    if d8 is not None:
        header_d8 = int(header.group(3))
        if header_d8 != int(d8) or not start_d8 <= header_d8 < end_d8:
            raise C.EntryV2Refusal(f"{name} header date/window mismatch")
    reader = csv.DictReader(io.StringIO("\n".join(lines[1:])), delimiter="\t")
    if tuple(reader.fieldnames or ()) != tuple(columns):
        raise C.EntryV2Refusal(f"{name} column schema mismatch")
    rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise C.EntryV2Refusal(f"{name} row width mismatch")
    return rows


def _int(row: Mapping[str, str], name: str) -> int:
    try:
        return int(row[name])
    except (KeyError, ValueError) as exc:
        raise C.EntryV2Refusal(f"invalid integer field {name}") from exc


def _float(
    row: Mapping[str, str],
    name: str,
    *,
    optional: bool = False,
) -> float | None:
    value = row.get(name, "")
    if optional and value == "NA":
        return None
    try:
        out = float(value)
    except ValueError as exc:
        raise C.EntryV2Refusal(f"invalid float field {name}") from exc
    if not math.isfinite(out):
        raise C.EntryV2Refusal(f"non-finite float field {name}")
    return out


def _bit(row: Mapping[str, str], name: str) -> bool:
    value = _int(row, name)
    if value not in (0, 1):
        raise C.EntryV2Refusal(f"invalid boolean field {name}")
    return bool(value)


def _json_receipt(
    raw: bytes, *, schema: str, stage: str, asset: str, manifest_sha256: str, name: str
) -> Mapping[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal(f"invalid {name} JSON") from exc
    if not isinstance(value, dict):
        raise C.EntryV2Refusal(f"invalid {name} object")
    if (value.get("schema"), value.get("stage"), value.get("asset")) != (schema, stage, asset):
        raise C.EntryV2Refusal(f"{name} identity mismatch")
    if value.get("manifest_sha256") != manifest_sha256:
        raise C.EntryV2Refusal(f"{name} manifest pin mismatch")
    try:
        start = int(value["start_d8"])
        end = int(value["end_d8_exclusive"])
    except (KeyError, TypeError, ValueError) as exc:
        raise C.EntryV2Refusal(f"{name} has an invalid record window") from exc
    C.guard_decode_window(start, end)
    if value.get("holdout_start_d8") != C.HOLDOUT_START_D8:
        raise C.EntryV2Refusal(f"{name} holdout wall mismatch")
    if value.get("final_exam_permit") is not False:
        raise C.EntryV2Refusal(f"{name} is not an ordinary development artifact")
    return value


@dataclass(frozen=True, slots=True)
class AssetArtifactSet:
    """Externally pinned artifact roots printed by the C++ G1 driver."""

    root: Path
    asset: str
    candidate_manifest_sha256: str
    teacher_manifest_sha256: str
    candidate_receipt_sha256: str
    teacher_receipt_sha256: str

    def __post_init__(self) -> None:
        root = Path(self.root)
        _guard_path_before_open(root)
        object.__setattr__(self, "root", root)
        asset = str(self.asset).upper()
        if asset not in C.ASSETS:
            raise C.EntryV2Refusal(f"unsupported artifact asset: {asset}")
        object.__setattr__(self, "asset", asset)
        for name in (
            "candidate_manifest_sha256",
            "teacher_manifest_sha256",
            "candidate_receipt_sha256",
            "teacher_receipt_sha256",
        ):
            _sha(getattr(self, name), name)


def _session_receipt(
    raw: bytes,
    *,
    schema: str,
    asset: str,
    d8: int,
    output_sha: str,
    expected_rows: int,
    name: str,
) -> Mapping[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal(f"invalid {name} JSON") from exc
    if not isinstance(value, dict) or value.get("schema") != schema:
        raise C.EntryV2Refusal(f"{name} schema mismatch")
    if (value.get("asset"), value.get("d8"), value.get("rows"), value.get("output_sha256")) != (
        asset,
        d8,
        expected_rows,
        output_sha,
    ):
        raise C.EntryV2Refusal(f"{name} identity/count/output mismatch")
    try:
        start = int(value["start_d8"])
        end = int(value["end_d8_exclusive"])
    except (KeyError, TypeError, ValueError) as exc:
        raise C.EntryV2Refusal(f"{name} has an invalid record window") from exc
    C.guard_decode_window(start, end)
    if value.get("holdout_start_d8") != C.HOLDOUT_START_D8 or value.get("final_exam_permit") is not False:
        raise C.EntryV2Refusal(f"{name} holdout contract mismatch")
    return value
