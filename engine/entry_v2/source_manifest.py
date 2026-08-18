#!/usr/bin/env python3
"""Provider-authenticated, pre-H2 source admission for Entry V2.

Databento's small ``manifest.json``/``metadata.json`` files classify every
payload before it is touched.  A provider-authenticated annual container that
starts in development and crosses the H2 wall is admitted only as a bounded
``DEVELOPMENT_PREFIX``; H2-only and 2026 payloads remain pre-open refusals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Iterable, Mapping, Sequence

from . import common as C


DIR_PREFIX = {"SI": "[Silver] ", "HG": "[Copper] ", "NKD": "[NKD] "}
PAYLOAD_SUFFIX = ".mbp-1.dbn.zst"
MANIFEST_PATH = C.PROVENANCE_ROOT / "source_manifest.json"
INPUT_LIST_ROOT = C.PROVENANCE_ROOT / "input_lists"
QRE2_INPUT_SCHEMA = "QRE2INPUT2"
SOURCE_SCHEMA = "entry-v2-source-manifest-v2"
H1_END_EXCLUSIVE_TS_RECV_NS = 1751320800000000000
READY = "READY_PRE_H2"
BLOCKED_H1 = "BLOCKED_PENDING_PROVIDER_H1_ONLY_2025"
DEVELOPMENT = "DEVELOPMENT"
DEVELOPMENT_PREFIX = "DEVELOPMENT_PREFIX"
_ADMITTED_ACCESS = frozenset((DEVELOPMENT, DEVELOPMENT_PREFIX))

_PROVIDER_SYMBOL_CONTRACT = {
    "SI": ("SI.FUT", "parent"),
    "HG": ("HG.v.0", "continuous"),
    "NKD": ("NKD.c.0", "continuous"),
}
_SHA = re.compile(r"sha256:([0-9a-f]{64})")


def asset_job_dirs(asset: str, root: Path = C.SOURCE_ROOT) -> tuple[Path, ...]:
    if asset not in C.ASSETS:
        raise C.EntryV2Refusal(f"unknown asset {asset!r}")
    if not root.is_dir():
        raise C.EntryV2Refusal(f"provider source root missing: {root}")
    hits = tuple(sorted(
        path for path in root.iterdir()
        if path.is_dir() and path.name.startswith(DIR_PREFIX[asset])
    ))
    if not hits:
        raise C.EntryV2Refusal(f"{asset}: no provider job directory")
    return hits


def asset_dir(asset: str, root: Path = C.SOURCE_ROOT) -> Path:
    """Compatibility helper; production admission supports multiple jobs."""
    hits = asset_job_dirs(asset, root)
    if len(hits) != 1:
        raise C.EntryV2Refusal(f"{asset}: expected one source directory, got {len(hits)}")
    return hits[0]


def payload_range(filename: str) -> tuple[int, int]:
    dates = tuple(int(value) for value in re.findall(
        r"(?<!\d)(\d{8})(?!\d)", filename
    ))
    if len(dates) == 1:
        return dates[0], dates[0]
    if len(dates) == 2 and dates[0] <= dates[1]:
        return dates
    raise C.EntryV2Refusal(f"payload has no unambiguous date range: {filename}")


def scope_of(start_d8: int, end_d8: int) -> str:
    if start_d8 >= C.SEALED_START_D8:
        return "SEALED_2026"
    if start_d8 >= C.HOLDOUT_START_D8:
        return "HOLDOUT_ONLY"
    if end_d8 >= C.HOLDOUT_START_D8:
        return DEVELOPMENT_PREFIX
    return DEVELOPMENT


def _provider_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise C.EntryV2Refusal(f"provider {field} must be a nonnegative integer")
    return value


def _provider_sha(row: Mapping[str, object], label: str) -> str:
    match = _SHA.fullmatch(str(row.get("hash", "")))
    if match is None:
        raise C.EntryV2Refusal(f"{label}: missing provider sha256")
    return match.group(1)


def _read_admin(path: Path, label: str) -> tuple[bytes, Mapping[str, object]]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal(f"{label}: unreadable provider admin JSON") from exc
    if not isinstance(value, dict):
        raise C.EntryV2Refusal(f"{label}: provider admin JSON must be an object")
    return raw, value


def _development_stat(path: Path, expected_size: int, label: str) -> int:
    """Stat only after the provider row has an admitted development scope."""
    try:
        info = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise C.EntryV2Refusal(f"{label}: development payload missing") from exc
    if not stat.S_ISREG(info.st_mode) or info.st_size != expected_size:
        raise C.EntryV2Refusal(
            f"{label}: development payload type/size mismatch "
            f"expected={expected_size} got={info.st_size}"
        )
    return int(info.st_size)


def audit_provider_job(asset: str, directory: Path) -> dict:
    """Audit one Databento job; excluded payloads are never touched."""
    if asset not in C.ASSETS:
        raise C.EntryV2Refusal(f"unknown asset {asset!r}")
    directory = Path(directory).resolve()
    manifest_path = directory / "manifest.json"
    metadata_path = directory / "metadata.json"
    manifest_raw, manifest = _read_admin(manifest_path, f"{asset}:manifest")
    metadata_raw, metadata = _read_admin(metadata_path, f"{asset}:metadata")
    if not manifest.get("job_id") or manifest.get("job_id") != metadata.get("job_id"):
        raise C.EntryV2Refusal(f"{asset}: provider job_id mismatch")

    files = manifest.get("files")
    if not isinstance(files, list):
        raise C.EntryV2Refusal(f"{asset}: provider manifest files must be a list")
    metadata_rows = [row for row in files if isinstance(row, dict)
                     and row.get("filename") == "metadata.json"]
    if len(metadata_rows) != 1:
        raise C.EntryV2Refusal(f"{asset}: metadata.json is not uniquely authenticated")
    metadata_row = metadata_rows[0]
    if (_provider_int(metadata_row.get("size"), "metadata size") != len(metadata_raw)
            or _provider_sha(metadata_row, f"{asset}:metadata")
            != hashlib.sha256(metadata_raw).hexdigest()):
        raise C.EntryV2Refusal(f"{asset}: provider metadata authentication failed")

    query = metadata.get("query")
    custom = metadata.get("customizations")
    if not isinstance(query, dict) or not isinstance(custom, dict):
        raise C.EntryV2Refusal(f"{asset}: provider query/customizations missing")
    symbol, stype = _PROVIDER_SYMBOL_CONTRACT[asset]
    expected = {
        "dataset": "GLBX.MDP3", "schema": "mbp-1", "symbols": [symbol],
        "stype_in": stype, "stype_out": "instrument_id", "encoding": "dbn",
        "compression": "zstd",
    }
    wrong = sorted(key for key, value in expected.items() if query.get(key) != value)
    if wrong:
        raise C.EntryV2Refusal(f"{asset}: wrong provider query fields: {','.join(wrong)}")
    query_start = _provider_int(query.get("start"), "query.start")
    query_end = _provider_int(query.get("end"), "query.end")
    if query_end <= query_start:
        raise C.EntryV2Refusal(f"{asset}: empty/reversed provider query")

    payloads: list[tuple[int, Mapping[str, object]]] = []
    for ordinal, row in enumerate(files):
        if not isinstance(row, dict):
            raise C.EntryV2Refusal(f"{asset}: provider file row is not an object")
        name = str(row.get("filename", ""))
        if name.endswith(PAYLOAD_SUFFIX) and ".trades." not in name:
            payloads.append((ordinal, row))
    if not payloads:
        raise C.EntryV2Refusal(f"{asset}: provider job has no MBP-1 payload")

    admitted: list[dict] = []
    excluded: list[dict] = []
    opaque_h1 = len(payloads) == 1 and query_end == H1_END_EXCLUSIVE_TS_RECV_NS
    for ordinal, row in payloads:
        name = str(row.get("filename", ""))
        if (not name or Path(name).name != name
                or any(char in name for char in "\t\r\n")):
            raise C.EntryV2Refusal(f"{asset}: unsafe provider payload filename")
        sha = _provider_sha(row, f"{asset}:{name}")
        size = _provider_int(row.get("size"), f"files[{ordinal}].size")
        try:
            container_lo, container_hi = payload_range(name)
            scope = scope_of(container_lo, container_hi)
            if (scope == DEVELOPMENT
                    and container_hi == C.DEVELOPMENT_END_D8
                    and query_end > H1_END_EXCLUSIVE_TS_RECV_NS):
                scope = DEVELOPMENT_PREFIX
            admission = f"manifest.files[{ordinal}].filename"
        except C.EntryV2Refusal:
            if not opaque_h1:
                raise C.EntryV2Refusal(
                    f"{asset}:{name}: opaque payload is not an exact provider H1 job"
                )
            container_lo, container_hi = (
                20250101, C.DEVELOPMENT_END_D8
            )
            scope = DEVELOPMENT
            admission = "metadata.query(exact_H1_single_payload)"
        effective_hi = min(container_hi, C.DEVELOPMENT_END_D8)
        base = {
            "path": str(directory / name), "filename": name,
            "start_d8": container_lo, "end_d8": effective_hi,
            "container_start_d8": container_lo,
            "container_end_d8": container_hi,
            "provider_sha256": sha,
            "provider_declared_bytes": size, "scope": scope,
            "provider_job_id": str(metadata["job_id"]),
            "provider_manifest_ordinal": ordinal, "admission_source": admission,
        }
        if scope not in _ADMITTED_ACCESS:
            excluded.append({
                **base, "access": "PREOPEN_REFUSAL",
                "preopen_refusal": "HOLDOUT_OR_SEALED",
            })
            continue
        # Classification is complete.  Only now may filesystem metadata for
        # this provider-authenticated development payload be inspected.
        actual_size = _development_stat(directory / name, size, f"{asset}:{name}")
        admitted.append({**base, "bytes": actual_size, "access": scope})

    return {
        "asset": asset,
        "provider_job_id": str(metadata["job_id"]),
        "provider_manifest_path": str(manifest_path),
        "provider_metadata_path": str(metadata_path),
        "admin_receipt_sha256": C.object_sha256({
            "manifest": hashlib.sha256(manifest_raw).hexdigest(),
            "metadata": hashlib.sha256(metadata_raw).hexdigest(),
        }),
        "query_start_ts_recv_ns": query_start,
        "query_end_ts_recv_ns_exclusive": query_end,
        "development_rows": admitted,
        "preopen_excluded_rows": excluded,
        "excluded_payload_filesystem_accesses": 0,
    }


def _collect_asset(asset: str, directories: Sequence[Path]) -> dict:
    audits = tuple(audit_provider_job(asset, directory) for directory in directories)
    rows = sorted(
        (row for audit in audits for row in audit["development_rows"]),
        key=lambda row: (row["start_d8"], row["end_d8"], row["path"]),
    )
    excluded = sorted(
        (row for audit in audits for row in audit["preopen_excluded_rows"]),
        key=lambda row: (row["start_d8"], row["end_d8"], row["path"]),
    )
    if not rows:
        raise C.EntryV2Refusal(f"{asset}: no admitted development payload")
    seen: set[str] = set()
    previous_hi = 0
    for row in rows:
        if row["path"] in seen:
            raise C.EntryV2Refusal(f"{asset}: duplicate provider payload path")
        if row["start_d8"] <= previous_hi:
            raise C.EntryV2Refusal(f"{asset}: overlapping development payload ranges")
        seen.add(row["path"])
        previous_hi = int(row["end_d8"])
    # Split jobs legitimately have one provider payload per trading date, so
    # readiness is the admitted development frontier, not one container that
    # spans the whole half-year.
    h1_ready = max(int(row["end_d8"]) for row in rows) >= C.DEVELOPMENT_END_D8
    blocker = None if h1_ready else {
        "code": "PROVIDER_H1_ONLY_2025_REQUIRED",
        "required_query_end_ts_recv_ns_exclusive": H1_END_EXCLUSIVE_TS_RECV_NS,
        "required_end_utc": "2025-06-30T22:00:00Z",
    }
    return {
        "provider_jobs": [{key: audit[key] for key in (
            "provider_job_id", "provider_manifest_path", "provider_metadata_path",
            "admin_receipt_sha256", "query_start_ts_recv_ns",
            "query_end_ts_recv_ns_exclusive",
        )} for audit in audits],
        "payloads": rows,
        "preopen_excluded_payloads": excluded,
        "h1_ready": h1_ready,
        "external_blocker": blocker,
    }


def build(
    root: Path = C.SOURCE_ROOT,
    out: Path = MANIFEST_PATH,
    *,
    directories: Mapping[str, Sequence[Path]] | None = None,
) -> dict:
    jobs = directories or {asset: asset_job_dirs(asset, root) for asset in C.ASSETS}
    if set(jobs) != set(C.ASSETS):
        raise C.EntryV2Refusal("source manifest requires SI, HG, and NKD")
    assets = {asset: _collect_asset(asset, jobs[asset]) for asset in C.ASSETS}
    blockers = {
        asset: row["external_blocker"] for asset, row in assets.items()
        if row["external_blocker"] is not None
    }
    manifest = {
        "schema": SOURCE_SCHEMA,
        "created_at_utc": C.utc_now(),
        "status": BLOCKED_H1 if blockers else READY,
        "policy": {
            "development_end_d8": C.DEVELOPMENT_END_D8,
            "holdout_start_d8": C.HOLDOUT_START_D8,
            "sealed_start_d8": C.SEALED_START_D8,
            "availability_clock": "Mbp1Msg::IndexTs/ts_recv",
            "input_contract": (
                "PATH<TAB>provider_sha256<TAB>"
                "DEVELOPMENT|DEVELOPMENT_PREFIX"
            ),
            "mixed_container_rule": (
                "provider-authenticated DEVELOPMENT_PREFIX stops on first "
                "IndexTs at/after H1 wall before Entry V2 state"
            ),
            "h1_end_exclusive_ts_recv_ns": H1_END_EXCLUSIVE_TS_RECV_NS,
        },
        "external_blockers": blockers,
        "assets": assets,
    }
    C.atomic_json(out, manifest)
    return manifest


def load(path: Path = MANIFEST_PATH, *, require_ready: bool = False) -> dict:
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal("source manifest missing/invalid") from exc
    if not isinstance(value, dict) or value.get("schema") != SOURCE_SCHEMA:
        raise C.EntryV2Refusal("wrong source manifest schema (V1 is blocked)")
    if require_ready and value.get("status") != READY:
        raise C.EntryV2Refusal(
            f"source manifest is not pre-H2 ready: {value.get('status')}"
        )
    return value


def collect_qre2_input2_rows(
    asset: str,
    directories: Sequence[Path] | None = None,
    *,
    manifest: Mapping[str, object] | None = None,
) -> tuple[dict, ...]:
    if directories is not None:
        rows = _collect_asset(asset, directories)["payloads"]
    else:
        source = manifest or load()
        rows = source["assets"][asset]["payloads"]  # type: ignore[index]
    return tuple(dict(row) for row in rows)


def render_qre2_input2(rows: Sequence[Mapping[str, object]]) -> bytes:
    lines: list[str] = []
    for ordinal, row in enumerate(rows):
        path = str(row.get("path", ""))
        sha = str(row.get("provider_sha256", ""))
        if not path or any(char in path for char in "\t\r\n"):
            raise C.EntryV2Refusal(f"QRE2INPUT2 row {ordinal}: unsafe path")
        if re.fullmatch(r"[0-9a-f]{64}", sha) is None:
            raise C.EntryV2Refusal(f"QRE2INPUT2 row {ordinal}: invalid provider sha256")
        access = str(row.get("access", ""))
        if access not in _ADMITTED_ACCESS:
            raise C.EntryV2Refusal(
                f"QRE2INPUT2 row {ordinal}: invalid development access"
            )
        lines.append(f"{path}\t{sha}\t{access}\n")
    if not lines:
        raise C.EntryV2Refusal("QRE2INPUT2 cannot be empty")
    return "".join(lines).encode()


def parse_qre2_input2(raw: bytes | str) -> tuple[dict, ...]:
    text = raw.decode() if isinstance(raw, bytes) else raw
    if not text or not text.endswith("\n"):
        raise C.EntryV2Refusal("QRE2INPUT2 must be nonempty and LF-terminated")
    rows = []
    for ordinal, line in enumerate(text.splitlines()):
        fields = line.split("\t")
        if len(fields) != 3:
            raise C.EntryV2Refusal(
                f"QRE2INPUT2 row {ordinal}: expected 3 columns, got {len(fields)}"
            )
        rows.append({"path": fields[0], "provider_sha256": fields[1],
                     "access": fields[2]})
    render_qre2_input2(rows)
    return tuple(rows)


def qre2_input2_aggregate_sha256(rendered: Mapping[str, bytes]) -> str:
    if tuple(rendered) != C.ASSETS:
        raise C.EntryV2Refusal("QRE2INPUT2 aggregate asset order must be SI/HG/NKD")
    return C.object_sha256({asset: rendered[asset].decode() for asset in C.ASSETS})


def write_qre2_input_lists(
    directories: Mapping[str, Sequence[Path]] | None = None,
    out: Path = INPUT_LIST_ROOT,
    *,
    manifest: Mapping[str, object] | None = None,
) -> dict:
    source = manifest
    if source is None and directories is None:
        source = load()
    if directories is not None and set(directories) != set(C.ASSETS):
        raise C.EntryV2Refusal("input-list generation requires SI, HG, and NKD")
    rendered = {
        asset: render_qre2_input2(collect_qre2_input2_rows(
            asset, None if directories is None else directories[asset], manifest=source
        )) for asset in C.ASSETS
    }
    aggregate = qre2_input2_aggregate_sha256(rendered)
    out = C.assert_workspace_output(out)
    out.mkdir(parents=True, exist_ok=True)
    for asset, raw in rendered.items():
        target = out / f"{asset}.tsv"
        temporary = target.with_name(target.name + f".tmp.{os.getpid()}")
        with open(temporary, "xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    status = source.get("status") if isinstance(source, Mapping) else None
    receipt = {
        "schema": "entry-v2-causal-input-lists-v3",
        "status": status or READY,
        "input_schema": QRE2_INPUT_SCHEMA,
        "row_format": (
            "PATH<TAB>provider_sha256<TAB>"
            "DEVELOPMENT|DEVELOPMENT_PREFIX<LF>"
        ),
        "aggregate_sha256": aggregate,
        "row_counts": {asset: rendered[asset].count(b"\n") for asset in C.ASSETS},
        "external_blockers": (
            dict(source.get("external_blockers", {}))
            if isinstance(source, Mapping) else {}
        ),
    }
    C.atomic_json(out / "receipt.json", receipt)
    return receipt


def decode_plan(
    asset: str,
    start_d8: int,
    end_d8_exclusive: int,
    manifest: Mapping[str, object] | None = None,
    permit: C.FinalExamPermit | None = None,
) -> list[dict]:
    C.guard_decode_window(start_d8, end_d8_exclusive, permit)
    source = manifest or load()
    rows = source["assets"][asset]["payloads"]  # type: ignore[index]
    selected = [dict(row) for row in rows
                if int(row["start_d8"]) < end_d8_exclusive
                and int(row["end_d8"]) >= start_d8]
    blocker = source["assets"][asset].get("external_blocker")  # type: ignore[index]
    if end_d8_exclusive > 20250101 and blocker:
        raise C.EntryV2Refusal(
            f"{asset}: provider H1-only artifact required before payload open"
        )
    if not selected:
        raise C.EntryV2Refusal(f"no payloads overlap {asset} window")
    return selected


def generate(root: Path = C.SOURCE_ROOT, out: Path = MANIFEST_PATH) -> dict:
    manifest = build(root, out)
    receipt = write_qre2_input_lists(manifest=manifest)
    return {"manifest": manifest, "input_lists": receipt}


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "build", "plan", "input-lists"))
    parser.add_argument("--asset", choices=C.ASSETS)
    parser.add_argument("--start-d8", type=int)
    parser.add_argument("--end-d8-exclusive", type=int)
    args = parser.parse_args(argv)
    if args.command == "generate":
        result = generate()
    elif args.command == "build":
        result = build()
    elif args.command == "input-lists":
        result = write_qre2_input_lists()
    else:
        if not (args.asset and args.start_d8 and args.end_d8_exclusive):
            raise C.EntryV2Refusal("plan requires asset/start/end")
        result = decode_plan(args.asset, args.start_d8, args.end_d8_exclusive)
    if args.command == "generate":
        printable: object = {
            "manifest_path": str(MANIFEST_PATH),
            "status": result["manifest"]["status"],
            "external_blockers": result["manifest"]["external_blockers"],
            "input_lists": result["input_lists"],
        }
    else:
        printable = result
    print(json.dumps(printable, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
