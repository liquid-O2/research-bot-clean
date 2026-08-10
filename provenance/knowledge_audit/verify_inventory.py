#!/usr/bin/env python3
"""Distrustful verifier for the knowledge provenance publication."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from collections import Counter, defaultdict
from pathlib import Path


WORK = Path("/workspace/data/cleanroom_work/knowledge_audit")
DEFAULT_PUBLICATION = WORK / "publication_v1"
DEFAULT_RECEIPT = WORK / "verification_v1.json"
CHUNK = 4 * 1024 * 1024
HASHED_STATES = {"FULL_PREFIX_SHA256", "JSONL_PREFIX_SHA256"}
METADATA_STATES = {
    "METADATA_ONLY_CLASSIFIED", "SECRET_METADATA_ONLY",
    "PROHIBITED_DATA_WALL_METADATA_ONLY", "SYMLINK_METADATA_ONLY",
    "MISSING_AT_SCAN",
}
PROPOSITION_DISPOSITIONS = {
    "EVIDENCE_SUPPORTED", "CONTEXT_ONLY", "REFUTED", "UNVERIFIED",
    "PROHIBITED", "SUPERSEDED",
}
ADMISSIBLE_EVIDENCE_TIERS = {
    "RECEIPT_AUTHORITY", "CODE_AUTHORITY", "PRIMARY_RESEARCH_INPUT",
    "SPEC_AUTHORITY", "REVIEW_EVIDENCE",
}


class GateError(RuntimeError):
    pass


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(CHUNK):
            h.update(block)
    return h.hexdigest()


def sha_prefix(path: Path, size: int) -> str:
    h = hashlib.sha256()
    remaining = size
    with path.open("rb", buffering=0) as handle:
        while remaining:
            block = handle.read(min(CHUNK, remaining))
            if not block:
                raise GateError(f"source shortened: {path}")
            h.update(block)
            remaining -= len(block)
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("rb") as handle:
        for line_number, raw in enumerate(handle, 1):
            try:
                value = json.loads(raw)
            except Exception as exc:
                raise GateError(f"invalid publication JSONL {path}:{line_number}: {exc}") from exc
            if not isinstance(value, dict):
                raise GateError(f"non-object publication JSONL {path}:{line_number}")
            rows.append(value)
    return rows


def unique(rows: list[dict], field: str, label: str) -> dict[str, dict]:
    out = {}
    for row in rows:
        value = row.get(field)
        if not isinstance(value, str) or not value:
            raise GateError(f"{label} missing {field}")
        if value in out:
            raise GateError(f"duplicate {label} {field}: {value}")
        out[value] = row
    return out


def require_classified(value: object, label: str) -> None:
    if not isinstance(value, str) or not value or "UNCLASSIFIED" in value.upper() or value.upper() == "UNKNOWN":
        raise GateError(f"unclassified {label}: {value!r}")


def validate_source(row: dict) -> None:
    required = {
        "schema_version", "snapshot_id", "source_id", "universe_id",
        "absolute_path", "relative_path", "entry_kind", "snapshot_size",
        "mtime_ns", "mode_octal", "content_state", "source_role",
        "authority_tier", "privacy_class", "license_class", "redistribution",
        "evidence_disposition", "classification_rule", "current_codex_thread",
        "raw_content_copied",
    }
    missing = required - row.keys()
    if missing:
        raise GateError(f"source {row.get('source_id')} missing {sorted(missing)}")
    if row["raw_content_copied"] is not False:
        raise GateError("raw content copy flag is not false")
    for field in ("source_role", "authority_tier", "privacy_class", "license_class", "redistribution", "evidence_disposition", "classification_rule", "content_state"):
        require_classified(row[field], f"source {field}")
    if row["content_state"] not in HASHED_STATES | METADATA_STATES:
        raise GateError(f"unknown content state {row['content_state']}")
    if row["content_state"] in HASHED_STATES:
        digest = row.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise GateError(f"hashed source lacks SHA {row['source_id']}")
    elif row.get("sha256") is not None:
        raise GateError(f"metadata-only source unexpectedly has content SHA {row['source_id']}")
    if row["privacy_class"] in {"SECRET", "PRIVATE_CONVERSATION"} and row["redistribution"] != "REFUSE":
        raise GateError(f"private source marked redistributable {row['source_id']}")
    if "THIRD_PARTY" in row["license_class"] and row["redistribution"] == "INTERNAL_CONTENT_OK":
        raise GateError(f"third-party source marked content-copyable {row['source_id']}")
    if row["source_role"] in {"CODEX_TRANSCRIPT", "CLAUDE_TRANSCRIPT", "CLAUDE_TOOL_RESULT"} and row["authority_tier"] not in {"LINEAGE_SOURCE"}:
        raise GateError(f"conversation promoted to evidence authority {row['source_id']}")
    if row["absolute_path"].startswith("/workspace/data/tokens/"):
        raise GateError("raw token payload entered inventory content universe")


def validate_segment(row: dict, sources: dict[str, dict]) -> None:
    required = {
        "schema_version", "snapshot_id", "segment_id", "source_id", "ordinal",
        "segment_kind", "byte_start", "byte_end", "parse_state",
        "evidence_disposition", "raw_content_copied",
    }
    missing = required - row.keys()
    if missing:
        raise GateError(f"segment {row.get('segment_id')} missing {sorted(missing)}")
    source = sources.get(row["source_id"])
    if source is None:
        raise GateError(f"segment source FK missing {row['source_id']}")
    if row["raw_content_copied"] is not False:
        raise GateError("segment copied raw content")
    if not (0 <= row["byte_start"] <= row["byte_end"] <= source["snapshot_size"]):
        raise GateError(f"segment byte bounds invalid {row['segment_id']}")
    require_classified(row["parse_state"], "segment parse state")
    require_classified(row["evidence_disposition"], "segment disposition")
    if row["segment_kind"] == "METADATA_ONLY" and row.get("segment_sha256") is not None:
        raise GateError(f"metadata segment carries content hash {row['segment_id']}")
    if row["segment_kind"] != "METADATA_ONLY":
        digest = row.get("segment_sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise GateError(f"content segment lacks SHA {row['segment_id']}")


def validate_propositions(propositions: list[dict], evidence_links: list[dict], segments: dict[str, dict], sources: dict[str, dict]) -> None:
    props = unique(propositions, "proposition_id", "proposition")
    for row in propositions:
        disposition = row.get("disposition")
        if disposition not in PROPOSITION_DISPOSITIONS:
            raise GateError(f"proposition disposition invalid {disposition}")
        source_ids = row.get("source_segment_ids")
        evidence_ids = row.get("evidence_segment_ids")
        if not isinstance(source_ids, list) or not source_ids or len(source_ids) != len(set(source_ids)):
            raise GateError("proposition source segments missing/duplicate")
        if not isinstance(evidence_ids, list) or len(evidence_ids) != len(set(evidence_ids)):
            raise GateError("proposition evidence segments malformed")
        for sid in source_ids + evidence_ids:
            if sid not in segments:
                raise GateError(f"proposition segment FK missing {sid}")
            if segments[sid]["evidence_disposition"] == "MALFORMED_FRAGMENT_QUARANTINE":
                raise GateError("proposition references malformed JSONL fragment")
        if disposition == "EVIDENCE_SUPPORTED":
            if not evidence_ids:
                raise GateError("supported proposition lacks evidence")
            admissible = False
            for segment_key in evidence_ids:
                source = sources[segments[segment_key]["source_id"]]
                if source["authority_tier"] in ADMISSIBLE_EVIDENCE_TIERS and source["source_role"] not in {"CODEX_TRANSCRIPT", "CLAUDE_TRANSCRIPT", "CLAUDE_TOOL_RESULT", "PROJECT_REPORT_OR_PLAN"}:
                    admissible = True
            if not admissible:
                raise GateError("supported proposition has only context/conversation evidence")
    for link in evidence_links:
        if link.get("proposition_id") not in props:
            raise GateError("evidence link proposition FK missing")
        if link.get("segment_id") not in segments:
            raise GateError("evidence link segment FK missing")


def verify_content(source_rows: list[dict]) -> Counter:
    states: Counter = Counter()
    for row in source_rows:
        path = Path(row["absolute_path"])
        if row["content_state"] in HASHED_STATES:
            if not path.is_file() or path.is_symlink():
                raise GateError(f"hashed source disappeared or redirected {path}")
            actual = sha_prefix(path, row["snapshot_size"])
            if actual != row["sha256"]:
                raise GateError(f"source prefix hash drift {path}")
            current = os.lstat(path)
            if current.st_size < row["snapshot_size"]:
                raise GateError(f"source shrank {path}")
            states["HASH_PREFIX_PASS"] += 1
            if current.st_size > row["snapshot_size"]:
                states["APPENDED_AFTER_SNAPSHOT"] += 1
        elif row["entry_kind"] == "SYMLINK":
            if not path.is_symlink() or os.readlink(path) != row.get("symlink_target"):
                states["METADATA_DRIFT_AFTER_SNAPSHOT"] += 1
            else:
                states["SYMLINK_METADATA_PASS"] += 1
        else:
            states["CLASSIFIED_METADATA_ONLY"] += 1
    return states


def self_test() -> dict:
    passes = []
    base_source = {
        "source_id": "src_" + "1" * 32,
        "authority_tier": "LINEAGE_SOURCE",
        "source_role": "CODEX_TRANSCRIPT",
    }
    base_segment = {
        "segment_id": "seg_" + "2" * 40,
        "source_id": base_source["source_id"],
        "evidence_disposition": "CONTEXT_ONLY",
    }
    def refused(name: str, proposition: dict, source=base_source, segment=base_segment) -> None:
        try:
            validate_propositions([proposition], [], {segment["segment_id"]: segment}, {source["source_id"]: source})
        except GateError:
            passes.append(name)
            return
        raise GateError(f"self-test did not refuse {name}")
    common = {
        "proposition_id": "prop_" + "3" * 32,
        "normalized_text_sha256": "4" * 64,
        "claim_class": "EMPIRICAL",
        "source_segment_ids": [base_segment["segment_id"]],
        "privacy_class": "PRIVATE_WORKSPACE",
        "license_class": "PROJECT_AUTHORED",
    }
    refused("supported_without_evidence", {**common, "disposition": "EVIDENCE_SUPPORTED", "evidence_segment_ids": []})
    refused("conversation_only_evidence", {**common, "disposition": "EVIDENCE_SUPPORTED", "evidence_segment_ids": [base_segment["segment_id"]]})
    malformed = {**base_segment, "evidence_disposition": "MALFORMED_FRAGMENT_QUARANTINE"}
    refused("malformed_segment_reference", {**common, "disposition": "UNVERIFIED", "evidence_segment_ids": []}, segment=malformed)
    refused("missing_segment_fk", {**common, "disposition": "UNVERIFIED", "source_segment_ids": ["seg_" + "9" * 40], "evidence_segment_ids": []})
    if len(passes) != 4:
        raise GateError("self-test census mismatch")
    return {"status": "PASS", "mutation_count": len(passes), "mutations": passes}


def write_noreplace(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("publication", nargs="?", type=Path, default=DEFAULT_PUBLICATION)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    publication = args.publication.resolve()
    if publication.parent != WORK.resolve() or not publication.is_dir():
        raise SystemExit("publication must be an existing direct child of the fixed audit directory")
    build_receipt = json.loads((publication / "build_receipt.json").read_bytes())
    for name, expected in build_receipt["output_hashes"].items():
        actual = sha_file(publication / name)
        if actual != expected:
            raise GateError(f"publication hash mismatch {name}: {actual} != {expected}")
    source_rows = load_jsonl(publication / "source_inventory.jsonl")
    segment_rows = load_jsonl(publication / "segments.jsonl")
    fragment_rows = load_jsonl(publication / "jsonl_fragments.jsonl")
    proposition_rows = load_jsonl(publication / "propositions.jsonl")
    evidence_links = load_jsonl(publication / "evidence_links.jsonl")
    sources = unique(source_rows, "source_id", "source")
    segments = unique(segment_rows, "segment_id", "segment")
    for row in source_rows:
        validate_source(row)
    for row in segment_rows:
        validate_segment(row, sources)
    by_source: defaultdict[str, int] = defaultdict(int)
    for row in segment_rows:
        by_source[row["source_id"]] += 1
    missing_segments = sorted(set(sources) - set(by_source))
    if missing_segments:
        raise GateError(f"sources without segments: {missing_segments[:10]}")
    fragment_keys = {row["segment_id"] for row in fragment_rows}
    expected_fragments = {row["segment_id"] for row in segment_rows if row["evidence_disposition"] == "MALFORMED_FRAGMENT_QUARANTINE"}
    if fragment_keys != expected_fragments:
        raise GateError("JSONL fragment ledger is not exact")
    for row in fragment_rows:
        if row.get("raw_content_copied") is not False or row.get("source_id") not in sources:
            raise GateError("fragment privacy/FK violation")
    validate_propositions(proposition_rows, evidence_links, segments, sources)
    content_states = verify_content(source_rows)
    test = self_test()
    summary = json.loads((publication / "summary.json").read_bytes())
    if summary["source_count"] != len(source_rows) or summary["segment_count"] != len(segment_rows) or summary["jsonl_fragment_count"] != len(fragment_rows):
        raise GateError("summary census mismatch")
    unclassified = sum("UNCLASSIFIED" in json.dumps(row).upper() for row in source_rows + segment_rows + proposition_rows)
    if unclassified:
        raise GateError(f"unclassified rows remain: {unclassified}")
    receipt = {
        "schema_version": "knowledge_audit_verification_v1",
        "status": "PASS_ZERO_UNCLASSIFIED",
        "publication": str(publication),
        "snapshot_id": build_receipt["snapshot_id"],
        "publication_build_receipt_sha256": sha_file(publication / "build_receipt.json"),
        "verifier_sha256": sha_file(Path(__file__)),
        "source_count": len(source_rows),
        "segment_count": len(segment_rows),
        "jsonl_fragment_count": len(fragment_rows),
        "proposition_count": len(proposition_rows),
        "evidence_link_count": len(evidence_links),
        "unclassified_count": 0,
        "sources_without_segments": 0,
        "content_verification_counts": dict(sorted(content_states.items())),
        "gate_self_test": test,
        "raw_content_copied": False,
        "market_payload_copied": False,
    }
    data = canonical_json(receipt)
    write_noreplace(args.receipt.resolve(), data)
    print(json.dumps(receipt, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GateError as exc:
        print(f"KNOWLEDGE_AUDIT_REFUSAL: {exc}", file=sys.stderr)
        raise SystemExit(2)

