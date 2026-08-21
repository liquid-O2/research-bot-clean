"""Durable, source-bound cache for the full causal feature-roster audit.

The authoritative audit scans every causal feature value twice: once to hash
columns and once to prove digest collisions are exact duplicates.  That work is
part of the real-data boundary, but it must not be repeated after a later model
or publication interruption.  This module persists the exact audit result
without changing the feature implementation receipt used by existing shards.
"""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from types import MappingProxyType
from typing import Final, Mapping, Sequence

import numpy as np

from . import common as C
from .tabular_delayed_corpus import (
    FEATURE_AUDIT_SCHEMA, FEATURE_SHARD_SCHEMA,
    audit_causal_feature_roster_paths,
)
from .tabular_recovery_contracts import (
    CausalFeatureSchema, RecoveryRefusal,
)


FEATURE_AUDIT_STORE_SCHEMA: Final = "QRE2TABFEATUREAUDITSTORE1"


def _sha(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def _schema_from_mapping(value: Mapping[str, object]) -> CausalFeatureSchema:
    row = dict(value)
    row["names"] = tuple(map(str, row["names"]))
    row["removed_constants"] = tuple(map(str, row["removed_constants"]))
    row["removed_duplicates"] = tuple(
        tuple(map(str, pair)) for pair in row["removed_duplicates"])
    row["removed_proven_leaks"] = tuple(
        map(str, row["removed_proven_leaks"]))
    row["relation_source_features"] = tuple(
        map(str, row.get("relation_source_features", ())))
    result = CausalFeatureSchema(**row)
    result.__post_init__()
    return result


def _source_metadata(paths: Sequence[str | Path]) -> tuple[
        tuple[Path, ...], tuple[str, ...], tuple[str, ...]]:
    sources = tuple(sorted(Path(path).resolve() for path in paths))
    if not sources or len(sources) != len(set(sources)):
        raise RecoveryRefusal("feature audit source roster is empty/repeated")
    names: tuple[str, ...] | None = None
    representations = []
    for source in sources:
        C.guard_payload(source)
        try:
            with np.load(source, allow_pickle=False) as values:
                if str(values["schema"][0]) != FEATURE_SHARD_SCHEMA:
                    raise RecoveryRefusal("feature audit source schema differs")
                local_names = tuple(values["feature_names"].astype(str).tolist())
                representation = str(values["representation_sha256"][0])
                days = np.unique(values["day"].astype(np.int64, copy=False))
        except (OSError, ValueError, KeyError) as exc:
            raise RecoveryRefusal("cannot read feature audit source metadata") from exc
        if (not _sha(representation) or len(days) != 1
                or (names is not None and local_names != names)):
            raise RecoveryRefusal("feature audit source metadata drifts")
        C.guard_date(int(days[0]))
        names = local_names if names is None else names
        representations.append(representation)
    assert names is not None
    return sources, tuple(representations), names


def _identity(*, representations: tuple[str, ...],
              feature_names: tuple[str, ...],
              proven_leaks: tuple[str, ...]) -> tuple[str, str]:
    implementation = C.file_sha256(
        Path(__file__).with_name("tabular_delayed_corpus.py"))
    identity = C.object_sha256({
        "schema": FEATURE_AUDIT_STORE_SCHEMA,
        "source_representations": representations,
        "source_feature_names": feature_names,
        "proven_leaks": proven_leaks,
        "audit_implementation_sha256": implementation,
    })
    return identity, implementation


def _load(path: Path, *, identity: str, implementation: str,
          representations: tuple[str, ...], feature_names: tuple[str, ...],
          proven_leaks: tuple[str, ...]) -> tuple[
              CausalFeatureSchema, Mapping[str, object]]:
    C.guard_payload(path)
    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RecoveryRefusal("cannot strict-load feature audit store") from exc
    core = {key: item for key, item in value.items()
            if key != "receipt_sha256"}
    if (value.get("schema") != FEATURE_AUDIT_STORE_SCHEMA
            or value.get("h2_open_count") != 0
            or value.get("input_receipt_sha256") != identity
            or value.get("audit_implementation_sha256") != implementation
            or tuple(value.get("source_representations", ()))
               != representations
            or tuple(value.get("source_feature_names", ())) != feature_names
            or tuple(value.get("proven_leaks", ())) != proven_leaks
            or C.object_sha256(core) != value.get("receipt_sha256")):
        raise RecoveryRefusal("feature audit store identity differs")
    schema = _schema_from_mapping(value["feature_schema"])
    raw_audit = dict(value["feature_audit"])
    audit_core = {key: item for key, item in raw_audit.items()
                  if key != "receipt_sha256"}
    expected_source = C.object_sha256({
        "schema": FEATURE_AUDIT_SCHEMA,
        "source_feature_names": feature_names,
        "source_representations": representations,
    })
    if (C.object_sha256(audit_core) != raw_audit.get("receipt_sha256")
            or raw_audit.get("source_schema_sha256") != expected_source
            or raw_audit.get("feature_schema_receipt_sha256")
               != schema.receipt_sha256):
        raise RecoveryRefusal("feature audit store result differs")
    return schema, MappingProxyType(raw_audit)


def load_or_audit_causal_feature_roster_paths(
        paths: Sequence[str | Path], *, proven_leaks: Sequence[str] = (),
        cache_root: str | Path | None = None,
        ) -> tuple[CausalFeatureSchema, Mapping[str, object], Path]:
    """Strict-load the exact audit, or execute and atomically publish it once."""

    leaks = tuple(map(str, proven_leaks))
    if len(leaks) != len(set(leaks)):
        raise RecoveryRefusal("feature audit proven-leak roster repeats")
    sources, representations, names = _source_metadata(paths)
    identity, implementation = _identity(
        representations=representations, feature_names=names,
        proven_leaks=leaks)
    root = C.assert_workspace_output(
        cache_root or (C.CACHE_ROOT / "feature_audits"))
    target = root / identity / "audit.json"
    if not target.is_file():
        schema, audit = audit_causal_feature_roster_paths(
            sources, proven_leaks=leaks)
        core = {
            "schema": FEATURE_AUDIT_STORE_SCHEMA,
            "input_receipt_sha256": identity,
            "audit_implementation_sha256": implementation,
            "source_representations": representations,
            "source_feature_names": names,
            "proven_leaks": leaks,
            "feature_schema": asdict(schema),
            "feature_audit": dict(audit),
            "strict_reload": True,
            "h2_open_count": 0,
        }
        artifact = {**core, "receipt_sha256": C.object_sha256(core)}
        C.atomic_json(target, artifact)
    schema, audit = _load(target, identity=identity,
                          implementation=implementation,
                          representations=representations,
                          feature_names=names, proven_leaks=leaks)
    return schema, audit, target


def load_feature_audit_store(
        path: str | Path, *, source_paths: Sequence[str | Path],
        proven_leaks: Sequence[str] = (),
        ) -> tuple[CausalFeatureSchema, Mapping[str, object]]:
    """Strict-load a named audit store without executing the expensive audit."""

    leaks = tuple(map(str, proven_leaks))
    sources, representations, names = _source_metadata(source_paths)
    del sources
    identity, implementation = _identity(
        representations=representations, feature_names=names,
        proven_leaks=leaks)
    source = Path(path).resolve()
    expected = (C.CACHE_ROOT / "feature_audits" / identity / "audit.json").resolve()
    if source != expected:
        raise RecoveryRefusal("feature audit store path is not canonical")
    return _load(source, identity=identity, implementation=implementation,
                 representations=representations, feature_names=names,
                 proven_leaks=leaks)


__all__ = [
    "FEATURE_AUDIT_STORE_SCHEMA", "load_feature_audit_store",
    "load_or_audit_causal_feature_roster_paths",
]
