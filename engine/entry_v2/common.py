#!/usr/bin/env python3
"""Shared contracts, seals and lineage for the clean entry-v2 pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
import datetime as dt
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "ENTRY-V2-1"
REPO_ROOT = Path("/workspace")
SOURCE_ROOT = REPO_ROOT / "artifacts" / "reference" / "futures_mbp1"
CONTEXT_ROOT = REPO_ROOT / "artifacts" / "reference" / "port_context"
CACHE_ROOT = REPO_ROOT / "artifacts" / "cache" / "port" / "entry_v2"
PROVENANCE_ROOT = REPO_ROOT / "provenance" / "entry_v2"
QRE2_CALENDAR_PATH = (
    REPO_ROOT / "authorities" / "static" / "entry_v2_qre2_calendar.tsv"
)
QRE2_CALENDAR_SHA256 = (
    "8adc483770be9aa0663bd336e796c752c832fbc09d2778228f96c8f5297058f0"
)

ASSETS = ("SI", "HG", "NKD")
ASSET_INDEX = {a: i for i, a in enumerate(ASSETS)}
DEVELOPMENT_END_D8 = 20250630
HOLDOUT_START_D8 = 20250701
HOLDOUT_END_D8 = 20251231
SEALED_START_D8 = 20260101

ERAS = (
    ("E1", 20210701, 20211231),
    ("E2", 20220101, 20220630),
    ("E3", 20220701, 20221231),
    ("E4", 20230101, 20230630),
    ("E5", 20230701, 20231231),
    ("E6", 20240101, 20240630),
    ("E7", 20240701, 20241231),
    ("E8", 20250101, 20250630),
)

MAX_CPU_WORKERS = 16
# Position law (user ruling 2026-08-19): one concurrent mini per asset,
# unlimited sequential re-entry, and at most twelve entries across the whole
# portfolio day.  ``MAX_ENTRIES_PER_ASSET_DAY`` is retained as a compatibility
# alias for consumers whose DP has a per-asset dimension; setting it equal to
# the portfolio budget means it imposes no additional per-asset daily cap.
MAX_ENTRIES_PORTFOLIO_DAY = 12
MAX_ENTRIES_PER_ASSET_DAY = MAX_ENTRIES_PORTFOLIO_DAY
WALL_USD = 900.0
MIN_EXPECTANCY_USD = 600.0
MIN_TRADES = 10
TARGET_EXPECTANCY_USD = 1000.0
TARGET_ASSET_DAY_USD = 2000.0
# RAIL-0 ladder lower rung (design/RAIL0_LADDER_GATE_SPEC.md L1): the per-asset
# goal a block keeps when its exact ceiling cannot support $2,000/asset-day at
# the minimum capture.  Two rungs only -- the goal is never lowered further.
LADDER_FALLBACK_ASSET_DAY_USD = 1500.0
WEAK_ASSET_DAY_FLOOR_USD = 1500.0
LOW_CAPACITY_ASSET_DAY_FLOOR_USD = 1000.0
LOW_CAPACITY_MAX_DRAWDOWN_USD = 500.0
SHUFFLED_NULL_CEILING_ASSET_DAY_USD = 200.0
# Transitional aliases only. Production receipts and certification gates must
# use the explicit asset-day names from plan amendment A-001.
TARGET_SESSION_USD = TARGET_ASSET_DAY_USD
WEAK_SESSION_FLOOR_USD = WEAK_ASSET_DAY_FLOOR_USD
TARGET_MDD_USD = 1000.0

# Goal-bound tabular recovery law (user-approved 2026-08-20).  These are
# portfolio-day gates and intentionally do not replace the older per-asset
# diagnostic constants above.  Keeping the units explicit prevents another
# asset-day/session/portfolio-day denominator substitution.
RECOVERY_MIN_PORTFOLIO_DAY_USD = 3_000.0
RECOVERY_TARGET_PORTFOLIO_DAY_USD = 6_000.0
RECOVERY_MIN_CEILING_CAPTURE = 0.80
RECOVERY_TARGET_CEILING_CAPTURE = 0.90
RECOVERY_MIN_CONVERSION_RETENTION = 0.90

_D8 = re.compile(r"(?<!\d)(\d{8})(?!\d)")
_SHA256_TOKEN = re.compile(
    r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])")
# Frozen CatBoost RNG identities are path components like seed_20260820.
# They are not payload trading days and must not trip the 2026 seal.
_SEED_TOKEN = re.compile(r"seed_\d+")


class EntryV2Refusal(RuntimeError):
    """A causal, lineage, seal, or schema contract failed."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def canonical_json_value(value: Any) -> Any:
    """Convert receipt values without discarding read-only mapping contents."""
    if is_dataclass(value) and not isinstance(value, type):
        return canonical_json_value(asdict(value))
    if isinstance(value, Enum):
        return canonical_json_value(value.value)
    if isinstance(value, Mapping):
        return {key: canonical_json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [canonical_json_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [canonical_json_value(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(
            item, sort_keys=True, separators=(",", ":"), allow_nan=False))
    # Keep NumPy out of this authority module while still canonicalizing its
    # scalar/array values at receipt boundaries.
    if type(value).__module__.split(".", 1)[0] == "numpy":
        if hasattr(value, "tolist"):
            return canonical_json_value(value.tolist())
        if hasattr(value, "item"):
            return canonical_json_value(value.item())
    return value


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(canonical_json_value(value), sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def object_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: os.PathLike[str] | str, block: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for buf in iter(lambda: fh.read(block), b""):
            h.update(buf)
    return h.hexdigest()


def atomic_json(path: os.PathLike[str] | str, value: Any) -> str:
    p = Path(path)
    assert_workspace_output(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_bytes(value)
    tmp = p.with_name(p.name + f".tmp.{os.getpid()}")
    with open(tmp, "xb") as fh:
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, p)
    return hashlib.sha256(raw).hexdigest()


def assert_workspace_output(path: os.PathLike[str] | str) -> Path:
    p = Path(os.path.realpath(path))
    try:
        p.relative_to(REPO_ROOT / "artifacts")
    except ValueError:
        try:
            p.relative_to(PROVENANCE_ROOT)
        except ValueError as exc:
            raise EntryV2Refusal(
                f"bulk/receipt output must be under workspace artifacts or entry_v2 provenance: {p}"
            ) from exc
    if p in (REPO_ROOT / "artifacts", PROVENANCE_ROOT):
        raise EntryV2Refusal(f"output target is too broad: {p}")
    return p


def dates_in_basename(path: os.PathLike[str] | str) -> tuple[int, ...]:
    """Return explicit date-like tokens, excluding opaque SHA-256 identities.

    Content-addressed artifact directories are full 64-hex tokens.  Treating
    an incidental eight-digit run inside one as a date makes a lawful pre-H2
    artifact fail nondeterministically based on its hash.  Hash tokens carry
    no date authority; any separate date token in the basename remains guarded.

    ``seed_<digits>`` path identities are frozen RNG seeds (REAL_SEEDS /
    SHUFFLE_SEEDS), not session trading days.  A basename that is only a seed
    must not be sealed as 2026 payload.  A bare ``20260820.json`` still is.
    """

    name=_SEED_TOKEN.sub("",_SHA256_TOKEN.sub("",Path(path).name))
    return tuple(int(x) for x in _D8.findall(name))


def era_of(d8: int) -> str:
    d8 = int(d8)
    for name, lo, hi in ERAS:
        if lo <= d8 <= hi:
            return name
    if HOLDOUT_START_D8 <= d8 <= HOLDOUT_END_D8:
        return "HOLDOUT_2025H2"
    if d8 >= SEALED_START_D8:
        return "SEALED_2026"
    return "WARMUP"


@dataclass(frozen=True)
class FinalExamPermit:
    schema: str
    frozen_package_sha256: str
    source_manifest_sha256: str
    holdout_start_d8: int
    holdout_end_d8: int
    created_at_utc: str

    def validate(self) -> None:
        if self.schema != "entry-v2-final-exam-permit-v1":
            raise EntryV2Refusal("invalid final-exam permit schema")
        for name, val in (("frozen_package", self.frozen_package_sha256),
                          ("source_manifest", self.source_manifest_sha256)):
            if not re.fullmatch(r"[0-9a-f]{64}", val):
                raise EntryV2Refusal(f"invalid {name} hash")
        if (self.holdout_start_d8, self.holdout_end_d8) != (
                HOLDOUT_START_D8, HOLDOUT_END_D8):
            raise EntryV2Refusal("permit does not name the exact 2025H2 holdout")


def load_final_exam_permit(path: os.PathLike[str] | str) -> FinalExamPermit:
    raw = json.loads(Path(path).read_text())
    permit = FinalExamPermit(**raw)
    permit.validate()
    return permit


def guard_date(d8: int, permit: FinalExamPermit | None = None) -> str:
    """Refuse the final exam by default and 2026 unconditionally."""
    d8 = int(d8)
    if d8 >= SEALED_START_D8:
        raise EntryV2Refusal(f"2026 SEALED: refusing d8={d8}")
    if d8 >= HOLDOUT_START_D8:
        if permit is None:
            raise EntryV2Refusal(f"2025H2 HOLDOUT: refusing d8={d8} without frozen permit")
        permit.validate()
        if not (permit.holdout_start_d8 <= d8 <= permit.holdout_end_d8):
            raise EntryV2Refusal(f"date outside permit: {d8}")
    return era_of(d8)


from .common_calendar import (
    denominator_disposition, is_denominator_day, is_globex_trading_day,
    qre2_asset_coverage_start_d8, qre2_full_closures,
)




def guard_payload(path: os.PathLike[str] | str,
                  permit: FinalExamPermit | None = None) -> tuple[int, ...]:
    dates = dates_in_basename(path)
    for d8 in dates:
        guard_date(d8, permit)
    return dates


def guard_decode_window(start_d8: int, end_d8_exclusive: int,
                        permit: FinalExamPermit | None = None) -> tuple[int, int]:
    """Validate the declared window of an already-authorized source artifact.

    This date guard does not authorize opening a mixed H1/H2 container.  Such
    containers are refused before open; 2025 development inputs must be
    provider-produced H1-only artifacts whose declared end is no later than
    the holdout boundary.
    """
    lo, hi = int(start_d8), int(end_d8_exclusive)
    if hi <= lo:
        raise EntryV2Refusal(f"empty/reversed decode window: [{lo},{hi})")
    guard_date(lo, permit)
    guard_date(hi - 1, permit)
    if hi > SEALED_START_D8:
        raise EntryV2Refusal("decode window reaches sealed 2026")
    return lo, hi


def consume_final_exam_once(permit_path: os.PathLike[str] | str,
                            frozen_package_sha256: str,
                            source_manifest_sha256: str,
                            usage_path: os.PathLike[str] | str | None = None
                            ) -> FinalExamPermit:
    """Irreversibly mark the holdout spent before its first payload is read."""
    permit_path = Path(permit_path)
    permit = load_final_exam_permit(permit_path)
    if permit.frozen_package_sha256 != frozen_package_sha256:
        raise EntryV2Refusal("frozen package hash does not match permit")
    if permit.source_manifest_sha256 != source_manifest_sha256:
        raise EntryV2Refusal("source manifest hash does not match permit")
    use = Path(usage_path or PROVENANCE_ROOT / "final_exam_consumed.json")
    assert_workspace_output(use)
    use.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "entry-v2-final-exam-consumption-v1",
        "consumed_at_utc": utc_now(),
        "permit_path": str(permit_path.resolve()),
        "permit_sha256": file_sha256(permit_path),
        "frozen_package_sha256": frozen_package_sha256,
        "source_manifest_sha256": source_manifest_sha256,
    }
    try:
        fd = os.open(use, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    except FileExistsError as exc:
        raise EntryV2Refusal(f"final exam already consumed: {use}") from exc
    with os.fdopen(fd, "wb") as fh:
        fh.write(canonical_bytes(payload))
        fh.flush()
        os.fsync(fh.fileno())
    return permit


def git_state() -> Mapping[str, Any]:
    def run(*args: str) -> str:
        return subprocess.run(args, cwd=REPO_ROOT, check=True, text=True,
                              stdout=subprocess.PIPE).stdout.strip()
    return {"head": run("git", "rev-parse", "HEAD"),
            "status": run("git", "status", "--porcelain=v1").splitlines()}


@dataclass(frozen=True)
class ParentArtifact:
    path: str
    sha256: str

    @classmethod
    def from_path(cls, path: os.PathLike[str] | str) -> "ParentArtifact":
        p = Path(path).resolve()
        return cls(str(p), file_sha256(p))

    def verify(self) -> None:
        p = Path(self.path)
        if not p.is_file() or file_sha256(p) != self.sha256:
            raise EntryV2Refusal(f"parent artifact changed or missing: {p}")


@dataclass(frozen=True)
class StageReceipt:
    schema: str
    stage: str
    created_at_utc: str
    code_sha256: str
    params: Mapping[str, Any]
    parents: tuple[ParentArtifact, ...]
    outputs: tuple[ParentArtifact, ...]
    counters: Mapping[str, int | float | str]

    @classmethod
    def build(cls, stage: str, code_path: os.PathLike[str] | str,
              params: Mapping[str, Any], parents: Iterable[ParentArtifact],
              outputs: Iterable[ParentArtifact],
              counters: Mapping[str, int | float | str]) -> "StageReceipt":
        parent_t = tuple(parents)
        output_t = tuple(outputs)
        for item in parent_t + output_t:
            item.verify()
        return cls("entry-v2-stage-receipt-v1", stage, utc_now(),
                   file_sha256(code_path), dict(params), parent_t, output_t,
                   dict(counters))

    def write(self, path: os.PathLike[str] | str) -> str:
        return atomic_json(path, asdict(self))


def verify_receipt(path: os.PathLike[str] | str,
                   verify_outputs: bool = True) -> StageReceipt:
    raw = json.loads(Path(path).read_text())
    raw["parents"] = tuple(ParentArtifact(**p) for p in raw["parents"])
    raw["outputs"] = tuple(ParentArtifact(**p) for p in raw["outputs"])
    rec = StageReceipt(**raw)
    if rec.schema != "entry-v2-stage-receipt-v1":
        raise EntryV2Refusal("unknown stage receipt schema")
    for p in rec.parents:
        p.verify()
    if verify_outputs:
        for p in rec.outputs:
            p.verify()
    return rec
